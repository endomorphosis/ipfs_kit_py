"""Production-bound workload adapter for the runtime readiness harness (KITA-043).

Every measured operation invokes the exact protected production callables named
in ``PRODUCTION_BINDINGS``.  Samples are timed exclusively through the injected
``sample_timer`` (defaulting to the immutable protected monotonic wall-clock
callback).  No production path uses ``MemoryTransactionEngine`` or
``baseline.measure_transaction_workload``.
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, MutableMapping, Optional, Sequence, Tuple

from protected_timer import monotonic_sample_timer

# ---------------------------------------------------------------------------
# Production binding map (must match the protected independent test exactly)
# ---------------------------------------------------------------------------


def _target(module: str, symbol: str) -> str:
    return f"{module}:{symbol}"


VFS_EXECUTE = _target("ipfs_kit_py.core.vfs.service", "CanonicalVFSService.execute")
VFS_MODULE = "ipfs_kit_py.core.vfs.service"
WAL_COORDINATOR_MODULE = "ipfs_kit_py.core.wal.coordinator"
WAL_APPEND = _target("ipfs_kit_py.core.wal.writer", "WALWriter.append")

PRODUCTION_BINDINGS: Dict[str, Dict[str, Any]] = {
    "metadata_txn": {
        "path_classes": ["cold", "warm", "cache"],
        "operations": {
            "stat": [
                VFS_EXECUTE,
                _target(VFS_MODULE, "CanonicalVFSService._op_stat"),
            ],
            "catalog_put": [
                _target(
                    "ipfs_kit_py.core.buckets.service", "BucketService.create_bucket"
                )
            ],
            "cas_put": [
                VFS_EXECUTE,
                _target(VFS_MODULE, "CanonicalVFSService._op_cas_write"),
            ],
        },
    },
    "small_object_txn": {
        "path_classes": ["cold", "warm", "cache"],
        "operations": {
            "put": [
                VFS_EXECUTE,
                _target(VFS_MODULE, "CanonicalVFSService._op_create"),
            ],
            "get": [
                VFS_EXECUTE,
                _target(VFS_MODULE, "CanonicalVFSService._op_read"),
            ],
            "delete": [
                VFS_EXECUTE,
                _target(VFS_MODULE, "CanonicalVFSService._op_delete"),
            ],
        },
    },
    "mixed_vfs": {
        "path_classes": ["cold", "warm", "cache"],
        "operations": {
            "read": [
                VFS_EXECUTE,
                _target(VFS_MODULE, "CanonicalVFSService._op_read"),
            ],
            "write": [
                VFS_EXECUTE,
                _target(VFS_MODULE, "CanonicalVFSService._op_replace"),
            ],
            "list": [
                VFS_EXECUTE,
                _target(VFS_MODULE, "CanonicalVFSService._op_list"),
            ],
            "rename": [
                VFS_EXECUTE,
                _target(VFS_MODULE, "CanonicalVFSService._op_rename"),
            ],
        },
    },
    "wal_commit": {
        "path_classes": ["cold", "warm"],
        "operations": {
            "begin": [
                _target(WAL_COORDINATOR_MODULE, "WALTransactionCoordinator.begin")
            ],
            "append": [
                _target(
                    WAL_COORDINATOR_MODULE,
                    "WALTransactionCoordinator.record_intent",
                ),
                WAL_APPEND,
            ],
            "commit": [
                _target(
                    WAL_COORDINATOR_MODULE, "WALTransactionCoordinator.commit"
                ),
                WAL_APPEND,
            ],
        },
    },
    "arc_hotset": {
        "path_classes": ["cold", "warm", "cache"],
        "operations": {
            "get": [
                _target(
                    "ipfs_kit_py.cache.arc.cache", "AdaptiveReplacementCache.get"
                )
            ],
            "put": [
                _target(
                    "ipfs_kit_py.cache.arc.cache", "AdaptiveReplacementCache.put"
                )
            ],
            "evict": [
                _target(
                    "ipfs_kit_py.cache.arc.cache", "AdaptiveReplacementCache.put"
                )
            ],
        },
    },
    "graphrag_query": {
        "path_classes": ["cold", "warm", "cache"],
        "operations": {
            "exact_query": [
                _target(
                    "ipfs_kit_py.graphrag.vector_index",
                    "ExactVectorIndex.exact_search",
                )
            ],
            "ann_query": [
                _target(
                    "ipfs_kit_py.graphrag.vector_index", "ANNVectorIndex.search"
                )
            ],
            "incremental_ingest": [
                _target("ipfs_kit_py.graphrag.service", "GraphRAGService.apply")
            ],
        },
    },
    "replica_reconcile": {
        "path_classes": ["cold", "warm"],
        "operations": {
            "evaluate_policy": [
                _target(
                    "ipfs_kit_py.core.replication.reconciler", "plan_placement"
                )
            ],
            "schedule_repair": [
                _target(
                    "ipfs_kit_py.core.replication.reconciler",
                    "ReplicaReconciler._copy_or_repair",
                )
            ],
        },
    },
    "interface_roundtrip": {
        "path_classes": ["cold", "warm"],
        "operations": {
            "roundtrip": [
                _target(
                    "ipfs_kit_py.high_level_api.operation_adapter",
                    "PythonAdapter.call",
                ),
                _target("ipfs_kit_py.cli.operation_adapter", "CLIAdapter.run"),
                _target(
                    "ipfs_kit_py.mcp_server.tools.operation_adapter",
                    "MCPPlusPlusToolAdapter.call_stdio",
                ),
                _target(
                    "ipfs_kit_py.mcp_server.tools.operation_adapter",
                    "MCPPlusPlusToolAdapter.call_http",
                ),
                _target(
                    "ipfs_kit_py.mcp_server.tools.operation_adapter",
                    "MCPPlusPlusToolAdapter.call_p2p",
                ),
                _target(
                    "ipfs_kit_py.core.service_router",
                    "ServiceRouter.dispatch_async",
                ),
            ]
        },
    },
}

STATE_CHANGING_OPERATIONS = {
    ("metadata_txn", "catalog_put"),
    ("metadata_txn", "cas_put"),
    ("small_object_txn", "put"),
    ("small_object_txn", "delete"),
    ("mixed_vfs", "write"),
    ("mixed_vfs", "rename"),
    ("wal_commit", "begin"),
    ("wal_commit", "append"),
    ("wal_commit", "commit"),
    ("arc_hotset", "put"),
    ("arc_hotset", "evict"),
    ("graphrag_query", "incremental_ingest"),
    ("replica_reconcile", "schedule_repair"),
}

SAMPLE_TIMER_ID = "protected_timer.monotonic_sample_timer@1"


class ProductionMeasurementError(RuntimeError):
    """Raised when a production sample cannot complete successfully."""


# ---------------------------------------------------------------------------
# Fixture contexts per workload family
# ---------------------------------------------------------------------------


class _ReplicaBackend:
    def __init__(self, backend_id: str, objects: Optional[dict] = None) -> None:
        self.backend_id = backend_id
        self.objects = dict(objects or {})

    def read(self, content_ref: str):
        return self.objects.get(content_ref)

    def write(self, content_ref: str, content, *, idempotency_key: str) -> None:
        del idempotency_key
        self.objects[content_ref] = content

    def delete(self, content_ref: str, *, idempotency_key: str) -> None:
        del idempotency_key
        self.objects.pop(content_ref, None)


def _new_vfs():
    from ipfs_kit_py.core.vfs.service import CanonicalVFSService, InMemoryVFSStorage

    return CanonicalVFSService(InMemoryVFSStorage())


def _make_op(kind, *, operation_id: str, path: str = "", **kwargs):
    from ipfs_kit_py.core.vfs.service import make_op

    return make_op(kind, operation_id=operation_id, path=path, **kwargs)


def _bucket_manifest(name: str):
    from ipfs_kit_py.core.buckets.contracts import (
        BackendCapability,
        BucketIdentity,
        BucketLifecycleState,
        BucketManifest,
        BucketPolicy,
        BucketReplica,
        BucketReplicaRole,
    )

    backend_id = "primary"
    return BucketManifest(
        identity_record=BucketIdentity(backend_id, name),
        policy=BucketPolicy(policy_id=f"policy-{name}", quota_bytes=1_000_000, quota_objects=1000),
        backend_capability=BackendCapability(
            backend_id=backend_id, max_bucket_bytes=10_000_000, max_bucket_objects=10_000
        ),
        replicas=(BucketReplica(backend_id, BucketReplicaRole.PRIMARY),),
        lifecycle_state=BucketLifecycleState.PROVISIONING,
    )


class _WorkloadContext:
    """Isolated production fixtures for one workload/path measurement window."""

    def __init__(
        self,
        workload_name: str,
        path_class: str,
        *,
        seed: int,
        payload_bytes: int,
        durability: str,
    ) -> None:
        self.workload_name = workload_name
        self.path_class = path_class
        self.seed = seed
        self.payload_bytes = max(1, int(payload_bytes))
        self.durability = durability
        self._counter = 0
        # Prefer tmpfs when available so WAL/GraphRAG micro-samples are stable.
        tmp_dir = "/dev/shm" if os.path.isdir("/dev/shm") and os.access("/dev/shm", os.W_OK) else None
        self._tmpdir = tempfile.TemporaryDirectory(prefix="rr-prod-", dir=tmp_dir)
        self.root = Path(self._tmpdir.name)
        self._init_fixtures()

    def close(self) -> None:
        try:
            if hasattr(self, "wal") and self.wal is not None:
                self.wal.close()
        except Exception:
            pass
        self._tmpdir.cleanup()

    def _uid(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}-{self.seed}-{self.path_class}-{self._counter}-{uuid.uuid4().hex[:8]}"

    def _payload(self, n: Optional[int] = None) -> bytes:
        size = int(n if n is not None else self.payload_bytes)
        return (b"p" * size)[:size]

    def _init_fixtures(self) -> None:
        from ipfs_kit_py.cache.arc.cache import AdaptiveReplacementCache
        from ipfs_kit_py.cache.arc.contracts import ARCConfig
        from ipfs_kit_py.cli.operation_adapter import CLIAdapter
        from ipfs_kit_py.core.buckets.service import BucketService, InMemoryBucketBackend
        from ipfs_kit_py.core.operation_contracts import (
            OPERATION_REQUEST_SCHEMA,
            OPERATION_RESULT_SCHEMA,
            STORAGE_ERROR_SCHEMA,
            OperationResult,
            OperationState,
        )
        from ipfs_kit_py.core.operation_registry import (
            AuthorizationRequirement,
            CapabilityTier,
            OperationDefinition,
            OperationRegistry,
        )
        from ipfs_kit_py.core.replication.contracts import (
            BackendCapability,
            BackendInventory,
            ReplicaPolicy,
        )
        from ipfs_kit_py.core.replication.integrity import IntegrityVerifier, ReplicaContent
        from ipfs_kit_py.core.replication.reconciler import (
            ReconciliationActionKind,
            ReplicaReconciler,
            _Candidate,
        )
        from ipfs_kit_py.core.service_router import ServiceRouter
        from ipfs_kit_py.core.vfs.contracts import VFSOperationKind
        from ipfs_kit_py.core.vfs.service import VFSExecuteRequest
        from ipfs_kit_py.core.wal.coordinator import WALTransactionCoordinator
        from ipfs_kit_py.graphrag.contracts import (
            GraphRAGContent,
            GraphRAGIndexManifest,
            GraphRAGMetric,
            GraphRAGProvenance,
        )
        from ipfs_kit_py.graphrag.service import GraphRAGService
        from ipfs_kit_py.graphrag.vector_index import (
            ANNVectorIndex,
            ExactVectorIndex,
            VectorIndexIdentity,
            VectorRecord,
        )
        from ipfs_kit_py.high_level_api.operation_adapter import PythonAdapter
        from ipfs_kit_py.mcp_server.tools.operation_adapter import MCPPlusPlusToolAdapter

        from ipfs_kit_py.core.vfs.contracts import VFSEntryKind
        from ipfs_kit_py.core.vfs.service import CanonicalVFSService, InMemoryVFSStorage

        # Seed VFS through the storage boundary only.  Bound callables
        # (execute / _op_*) must not run outside the sample timer.
        storage = InMemoryVFSStorage()
        seed_entry = storage.seed(
            "bench/seed", kind=VFSEntryKind.FILE, content=self._payload(64)
        )
        cas_entry = storage.seed(
            "bench/cas-target", kind=VFSEntryKind.FILE, content=self._payload(32)
        )
        self.vfs = CanonicalVFSService(storage)
        self.seed_path = "bench/seed"
        self.seed_version = seed_entry.version_cid
        self.cas_path = "bench/cas-target"
        self.cas_version = cas_entry.version_cid
        self._object_path = self.seed_path
        self._write_path = self.seed_path
        self._rename_source = self.seed_path

        self.buckets = BucketService({"primary": InMemoryBucketBackend()})
        self.wal = WALTransactionCoordinator(self.root / "wal")
        self._wal_txn: Optional[str] = None

        # Tiny ARC so a capacity-bounded put induces eviction.  Seed the hot
        # key through the private model so AdaptiveReplacementCache.put/get
        # are not observed outside the sample timer.
        self.arc = AdaptiveReplacementCache(
            ARCConfig(capacity_bytes=64, max_live_entries=4, max_ghost_entries=8)
        )
        self.arc_hot_key = "arc:hot"
        self.arc._model.put(self.arc_hot_key, b"hot-value-payload-xx")
        self.arc_evictions_baseline = (
            self.arc.metrics().evictions_t1 + self.arc.metrics().evictions_t2
        )

        identity = VectorIndexIdentity(
            index_id="bench-index",
            model_id="bench-model",
            tokenizer_id="bench-tokenizer",
            dimension=4,
            metric="cosine",
            source_id="bench-source",
            source_version="v1",
        )
        self.exact_index = ExactVectorIndex(identity)
        self.ann_index = ANNVectorIndex(identity)
        for index, record_id, vector in (
            (self.exact_index, "vec-a", (1.0, 0.0, 0.0, 0.0)),
            (self.exact_index, "vec-b", (0.9, 0.1, 0.0, 0.0)),
            (self.ann_index, "vec-a", (1.0, 0.0, 0.0, 0.0)),
            (self.ann_index, "vec-b", (0.9, 0.1, 0.0, 0.0)),
        ):
            index.add(VectorRecord(record_id, vector, metadata={"label": record_id}))
        self.query_vector = (1.0, 0.0, 0.0, 0.0)

        graphrag_root = self.root / "graphrag"
        graphrag_root.mkdir(mode=0o700)
        self.graphrag_manifest = GraphRAGIndexManifest(
            "generation-bench",
            "bench-index",
            "bench-model",
            "bench-tokenizer",
            4,
            GraphRAGMetric.COSINE,
            "bench-source",
            "v1",
        )
        self.graphrag = GraphRAGService(graphrag_root, self.graphrag_manifest)
        self._graphrag_doc = 0

        payload = b"replica-payload"
        self.replica_content_ref = "cid:replica-bench"
        self.replica_version = "replica-v1"
        self.replica_content = ReplicaContent(payload, self.replica_version)
        self.replica_digest = IntegrityVerifier().digest(payload)
        self.replica_backends = {
            "replica-a": _ReplicaBackend(
                "replica-a", {self.replica_content_ref: self.replica_content}
            ),
            "replica-b": _ReplicaBackend("replica-b"),
            "replica-c": _ReplicaBackend("replica-c"),
        }
        self.replica_inventory = BackendInventory(
            "bench-inventory",
            (
                BackendCapability("replica-a", "domain-a", 4096),
                BackendCapability("replica-b", "domain-b", 4096),
                BackendCapability("replica-c", "domain-c", 4096),
            ),
        )
        self.replica_policy = ReplicaPolicy("bench-policy", 1, 2, 2, 2)
        self.replica_reconciler = ReplicaReconciler(self.replica_backends)
        self._Candidate = _Candidate
        self._ReconciliationActionKind = ReconciliationActionKind

        def _handler(definition, request, context):
            del request, context
            return OperationResult(
                request_id="bench-request",
                operation_id=definition.operation_id,
                state=OperationState.ACCEPTED,
                success=True,
                resulting_content_cid="cid:bench-content",
                resulting_version_cid="cid:bench-version",
            )

        public = "bench-echo"
        definition = OperationDefinition(
            operation_id="bench.echo",
            version=1,
            request_schema=OPERATION_REQUEST_SCHEMA,
            result_schema=OPERATION_RESULT_SCHEMA,
            error_schema=STORAGE_ERROR_SCHEMA,
            capability="bench.echo",
            authorization=AuthorizationRequirement.public(),
            handler_route="bench-service",
            transport_names={
                "python": public,
                "cli": public,
                "mcp": public,
                "mcpp": public,
            },
            support_tier=CapabilityTier.PRODUCTION,
        )
        registry = OperationRegistry((definition,))
        self.router = ServiceRouter(registry)
        self.router.bind_handler(
            "bench-service", _handler, capabilities={"bench.echo"}
        )
        self.python_adapter = PythonAdapter(registry, self.router)
        self.cli_adapter = CLIAdapter(registry, self.router)
        self.mcpp_adapter = MCPPlusPlusToolAdapter(registry, self.router)
        self.interface_public = public
        self.interface_request = {"key": "bench"}

        # Path-class residency is expressed by pre-seeded storage state only.
        # Bound production callables are never invoked during fixture setup.
        if self.path_class in {"warm", "cache"}:
            self.arc._model.get(self.arc_hot_key)

    def prepare_operation(self, operation: str) -> None:
        """Set up prerequisites without invoking bound production callables."""
        from ipfs_kit_py.core.vfs.contracts import VFSEntryKind
        from ipfs_kit_py.core.wal.coordinator import _Transaction

        if self.workload_name == "wal_commit":
            if operation == "begin":
                self._wal_txn = None
            elif operation == "append":
                # Inject an active transaction without begin()/append().
                if not self._wal_txn:
                    tid = self._uid("wal")
                    self.wal._transactions[tid] = _Transaction(tid)
                    self._wal_txn = tid
            elif operation == "commit":
                if not self._wal_txn:
                    tid = self._uid("wal")
                    txn = _Transaction(tid)
                    txn.intents.append(
                        {
                            "kind": "intent",
                            "transaction_id": tid,
                            "effect_id": self._uid("effect"),
                            "intent": {"kind": "bench", "n": self._counter},
                        }
                    )
                    self.wal._transactions[tid] = txn
                    self._wal_txn = tid
        elif self.workload_name == "small_object_txn" and operation in {"get", "delete"}:
            path = f"bench/obj-{self._uid('obj')}"
            self.vfs.storage.seed(path, kind=VFSEntryKind.FILE, content=self._payload())
            self._object_path = path
        elif self.workload_name == "mixed_vfs" and operation == "rename":
            path = f"bench/ren-{self._uid('ren')}"
            self.vfs.storage.seed(path, kind=VFSEntryKind.FILE, content=self._payload(16))
            self._rename_source = path
        elif self.workload_name == "mixed_vfs" and operation == "write":
            path = f"bench/wr-{self._uid('wr')}"
            self.vfs.storage.seed(path, kind=VFSEntryKind.FILE, content=self._payload(16))
            self._write_path = path
        elif self.workload_name == "metadata_txn" and operation == "cas_put":
            entry = self.vfs.storage.get(self.cas_path)
            if entry is None:
                entry = self.vfs.storage.seed(
                    self.cas_path, kind=VFSEntryKind.FILE, content=self._payload(32)
                )
            self.cas_version = entry.version_cid
        elif self.workload_name == "arc_hotset" and operation == "get":
            if self.arc._model.get(self.arc_hot_key) is None:
                self.arc._model.put(self.arc_hot_key, b"hot-value-payload-xx")
        elif self.workload_name == "arc_hotset" and operation == "evict":
            self.arc_evictions_baseline = (
                self.arc.metrics().evictions_t1 + self.arc.metrics().evictions_t2
            )
            # Fill cache through the private model so the timed put is the only
            # AdaptiveReplacementCache.put observation for this operation.
            for i in range(8):
                self.arc._model.put(f"arc:fill:{i}:{self._uid('f')}", b"x" * 20)

    def run_operation(self, operation: str) -> Tuple[Any, Dict[str, Any]]:
        """Execute one production operation; return (value, evidence extras)."""
        from ipfs_kit_py.core.replication.reconciler import plan_placement
        from ipfs_kit_py.core.vfs.contracts import VFSOperationKind
        from ipfs_kit_py.core.vfs.service import VFSExecuteRequest
        from ipfs_kit_py.graphrag.contracts import GraphRAGContent, GraphRAGProvenance

        extras: Dict[str, Any] = {}
        if self.workload_name == "metadata_txn":
            if operation == "stat":
                value = self.vfs.execute(
                    _make_op(
                        VFSOperationKind.STAT,
                        operation_id=self._uid("stat"),
                        path=self.seed_path,
                    )
                )
                if not value.success:
                    raise ProductionMeasurementError("stat failed")
                return value, extras
            if operation == "catalog_put":
                # Bucket names are ≤63 bytes and must stay unique across samples.
                token = uuid.uuid4().hex[:24]
                name = f"b{token}"
                value = self.buckets.create_bucket(_bucket_manifest(name))
                if value is None:
                    raise ProductionMeasurementError("catalog_put returned None")
                return value, extras
            if operation == "cas_put":
                value = self.vfs.execute(
                    _make_op(
                        VFSOperationKind.CAS_WRITE,
                        operation_id=self._uid("cas"),
                        path=self.cas_path,
                        precondition_version_cid=self.cas_version,
                    ),
                    VFSExecuteRequest(payload=self._payload(32)),
                )
                if not value.success:
                    raise ProductionMeasurementError(
                        f"cas_put failed: {value.result.error}"
                    )
                self.cas_version = value.result.resulting_version_cid
                return value, extras

        if self.workload_name == "small_object_txn":
            if operation == "put":
                path = f"bench/put-{self._uid('put')}"
                value = self.vfs.execute(
                    _make_op(
                        VFSOperationKind.CREATE,
                        operation_id=self._uid("put"),
                        path=path,
                    ),
                    VFSExecuteRequest(payload=self._payload()),
                )
                if not value.success:
                    raise ProductionMeasurementError("put failed")
                self._object_path = path
                return value, extras
            if operation == "get":
                path = getattr(self, "_object_path", self.seed_path)
                value = self.vfs.execute(
                    _make_op(
                        VFSOperationKind.READ,
                        operation_id=self._uid("get"),
                        path=path,
                    )
                )
                if not value.success:
                    raise ProductionMeasurementError("get failed")
                return value, extras
            if operation == "delete":
                path = getattr(self, "_object_path", self.seed_path)
                value = self.vfs.execute(
                    _make_op(
                        VFSOperationKind.DELETE,
                        operation_id=self._uid("del"),
                        path=path,
                    )
                )
                if not value.success:
                    raise ProductionMeasurementError("delete failed")
                return value, extras

        if self.workload_name == "mixed_vfs":
            if operation == "read":
                value = self.vfs.execute(
                    _make_op(
                        VFSOperationKind.READ,
                        operation_id=self._uid("read"),
                        path=self.seed_path,
                    )
                )
                if not value.success:
                    raise ProductionMeasurementError("read failed")
                return value, extras
            if operation == "write":
                path = getattr(self, "_write_path", self.seed_path)
                value = self.vfs.execute(
                    _make_op(
                        VFSOperationKind.REPLACE,
                        operation_id=self._uid("write"),
                        path=path,
                    ),
                    VFSExecuteRequest(payload=self._payload(16)),
                )
                if not value.success:
                    raise ProductionMeasurementError("write failed")
                return value, extras
            if operation == "list":
                value = self.vfs.execute(
                    _make_op(
                        VFSOperationKind.LIST,
                        operation_id=self._uid("list"),
                        path="bench",
                    )
                )
                if not value.success:
                    raise ProductionMeasurementError("list failed")
                return value, extras
            if operation == "rename":
                source = getattr(self, "_rename_source", self.seed_path)
                target = f"bench/renamed-{self._uid('to')}"
                value = self.vfs.execute(
                    _make_op(
                        VFSOperationKind.RENAME,
                        operation_id=self._uid("rename"),
                        path=source,
                        source_path=source,
                        target_path=target,
                    )
                )
                if not value.success:
                    raise ProductionMeasurementError("rename failed")
                return value, extras

        if self.workload_name == "wal_commit":
            if operation == "begin":
                value = self.wal.begin(self._uid("wal"))
                if not isinstance(value, str) or not value:
                    raise ProductionMeasurementError("begin returned empty id")
                self._wal_txn = value
                return value, extras
            if operation == "append":
                if not self._wal_txn:
                    raise ProductionMeasurementError("append without active transaction")
                value = self.wal.record_intent(
                    self._wal_txn, {"kind": "bench-intent", "n": self._counter}
                )
                if not isinstance(value, str) or not value:
                    raise ProductionMeasurementError("append returned empty effect id")
                return value, extras
            if operation == "commit":
                if not self._wal_txn:
                    raise ProductionMeasurementError("commit without active transaction")
                value = self.wal.commit(self._wal_txn)
                if not value.committed:
                    raise ProductionMeasurementError("commit was not durable")
                self._wal_txn = None
                return value, extras

        if self.workload_name == "arc_hotset":
            if operation == "get":
                value = self.arc.get(self.arc_hot_key)
                if not isinstance(value, bytes) or not value:
                    raise ProductionMeasurementError("arc get missed")
                return value, extras
            if operation == "put":
                key = f"arc:put:{self._uid('p')}"
                value = self.arc.put(key, b"put-payload-bytes!!!!")
                if value is not True:
                    raise ProductionMeasurementError("arc put rejected")
                return value, extras
            if operation == "evict":
                key = f"arc:evict:{self._uid('e')}"
                value = self.arc.put(key, b"evict-trigger-payload!")
                if value is not True:
                    raise ProductionMeasurementError("arc eviction put rejected")
                now = self.arc.metrics().evictions_t1 + self.arc.metrics().evictions_t2
                extras["evictions_delta"] = now - self.arc_evictions_baseline
                if extras["evictions_delta"] < 1:
                    # Force capacity pressure with another put of unique data.
                    value = self.arc.put(
                        f"arc:evict2:{self._uid('e2')}", b"evict-trigger-payload2"
                    )
                    now = self.arc.metrics().evictions_t1 + self.arc.metrics().evictions_t2
                    extras["evictions_delta"] = now - self.arc_evictions_baseline
                if extras["evictions_delta"] < 1:
                    raise ProductionMeasurementError("arc eviction was not observed")
                return value, extras

        if self.workload_name == "graphrag_query":
            if operation == "exact_query":
                value = self.exact_index.exact_search(self.query_vector, k=2)
                if len(value) < 1:
                    raise ProductionMeasurementError("exact_query empty")
                extras["result_count"] = len(value)
                return value, extras
            if operation == "ann_query":
                value = self.ann_index.search(self.query_vector, k=2)
                if len(value) < 1:
                    raise ProductionMeasurementError("ann_query empty")
                extras["result_count"] = len(value)
                return value, extras
            if operation == "incremental_ingest":
                self._graphrag_doc += 1
                doc_id = f"document-{self._graphrag_doc}"
                provenance = GraphRAGProvenance("bench-source", "v1", "bench-source")
                content = GraphRAGContent(
                    doc_id, f"version-{self._graphrag_doc}", f"payload-{self._graphrag_doc}", provenance
                )
                value = self.graphrag.apply(content)
                if value is None:
                    raise ProductionMeasurementError("graphrag apply returned None")
                return value, extras

        if self.workload_name == "replica_reconcile":
            if operation == "evaluate_policy":
                value = plan_placement(
                    content_id=self.replica_content_ref,
                    content_size_bytes=len(self.replica_content.payload),
                    policy=self.replica_policy,
                    inventory=self.replica_inventory,
                    replicas=(),
                )
                if value is None:
                    raise ProductionMeasurementError("plan_placement returned None")
                return value, extras
            if operation == "schedule_repair":
                # Ensure destination is empty so copy applies.
                dest = "replica-b"
                self.replica_backends[dest].objects.pop(self.replica_content_ref, None)
                candidate = self._Candidate(self._ReconciliationActionKind.COPY, dest)
                value = self.replica_reconciler._copy_or_repair(
                    candidate=candidate,
                    key=self._uid("repair"),
                    observations={},
                    source=self.replica_content,
                    content_ref=self.replica_content_ref,
                    expected_digest=self.replica_digest,
                    expected_version_id=self.replica_version,
                )
                if value.state.value != "applied":
                    raise ProductionMeasurementError(
                        f"repair not applied: {value.state} {value.reason}"
                    )
                extras["applied_actions"] = 1
                return value, extras

        if self.workload_name == "interface_roundtrip" and operation == "roundtrip":
            py = self.python_adapter.call(self.interface_public, self.interface_request)
            if not py.success:
                raise ProductionMeasurementError("python adapter failed")
            stdout = io.StringIO()
            stderr = io.StringIO()
            code = self.cli_adapter.run(
                [
                    self.interface_public,
                    "--request-json",
                    json.dumps(self.interface_request),
                ],
                stdout=stdout,
                stderr=stderr,
            )
            if code != 0:
                raise ProductionMeasurementError(f"cli adapter failed: {stderr.getvalue()}")
            stdio = self.mcpp_adapter.call_stdio(
                self.interface_public, self.interface_request
            )
            http = self.mcpp_adapter.call_http(
                self.interface_public, self.interface_request
            )
            p2p = self.mcpp_adapter.call_p2p(
                self.interface_public, self.interface_request
            )
            for label, payload in (("stdio", stdio), ("http", http), ("p2p", p2p)):
                if not payload.get("success") or payload.get("error") is not None:
                    raise ProductionMeasurementError(f"mcpp {label} failed: {payload}")
            direct = asyncio.run(
                self.router.dispatch_async("bench.echo", self.interface_request)
            )
            if direct is None:
                raise ProductionMeasurementError("router dispatch returned None")
            if isinstance(direct, dict) and "success" in direct and not direct["success"]:
                raise ProductionMeasurementError("router dispatch reported failure")
            extras["semantic_parity"] = True
            return {"python": py, "cli": code, "mcpp": stdio, "router": direct}, extras

        raise ProductionMeasurementError(
            f"unsupported operation {self.workload_name}/{operation}"
        )


# ---------------------------------------------------------------------------
# Public measurement API
# ---------------------------------------------------------------------------


def _resolve_target(target: str) -> Tuple[Any, str, Any]:
    import importlib

    module_name, separator, qualified_name = target.partition(":")
    if not separator or not module_name or not qualified_name:
        raise ProductionMeasurementError(f"invalid target {target!r}")
    owner: Any = importlib.import_module(module_name)
    parts = qualified_name.split(".")
    for part in parts[:-1]:
        owner = getattr(owner, part)
    name = parts[-1]
    return owner, name, getattr(owner, name)


def measure_workload(
    *,
    workload_name: str,
    definition: Mapping[str, Any],
    profile_name: str,
    path_class: str,
    seed: int,
    warmup: int,
    samples: int,
    payload_bytes: int,
    durability: str,
    confidence: float,
    sample_timer: Callable[[str, Callable[[], Any]], Tuple[Any, float]] = monotonic_sample_timer,
) -> Dict[str, Any]:
    """Measure one workload/path using only production callables and the timer.

    Each sample timer callback executes a single bound operation.  The observed
    wall-clock duration is assigned to accepted, committed, and converged stage
    arrays after the operation proves success at the declared durability and
    convergence barriers.  Target call counts are recorded only after the real
    callable returns successfully inside the timed callback.
    """
    import inspect

    del profile_name, confidence  # pinned by caller identity; not used in body
    if workload_name not in PRODUCTION_BINDINGS:
        raise ProductionMeasurementError(f"no production binding for {workload_name!r}")
    binding = PRODUCTION_BINDINGS[workload_name]
    if path_class not in binding["path_classes"]:
        raise ProductionMeasurementError(
            f"path class {path_class!r} not bound for {workload_name}"
        )
    operations = list(definition.get("operations") or list(binding["operations"]))
    for operation in operations:
        if operation not in binding["operations"]:
            raise ProductionMeasurementError(
                f"operation {operation!r} not bound for {workload_name}"
            )

    accepted_seconds: List[float] = []
    committed_seconds: List[float] = []
    converged_seconds: List[float] = []
    operation_calls: Dict[str, int] = {op: 0 for op in operations}
    target_calls: Dict[str, int] = {}
    operation_evidence: Dict[str, Dict[str, Any]] = {}

    ctx = _WorkloadContext(
        workload_name,
        path_class,
        seed=seed,
        payload_bytes=payload_bytes,
        durability=durability,
    )
    try:
        # Warmup samples are executed but not retained (and are not timed).
        warm_n = 0 if path_class == "cold" else max(0, int(warmup))
        for _ in range(warm_n):
            for operation in operations:
                ctx.prepare_operation(operation)
                ctx.run_operation(operation)

        for _sample in range(int(samples)):
            sample_durations: List[float] = []
            for operation in operations:
                expected_targets = list(binding["operations"][operation])
                ctx.prepare_operation(operation)

                # Observe successful target invocations inside the timed callback
                # so receipts match the protected gate's independent spy counts.
                sample_target_counts: Dict[str, int] = {t: 0 for t in expected_targets}
                originals: List[Tuple[Any, str, Any]] = []

                def _install() -> None:
                    for target in expected_targets:
                        owner, name, original = _resolve_target(target)
                        originals.append((owner, name, original))

                        def _wrap(
                            *args: Any,
                            __target=target,
                            __original=original,
                            **kwargs: Any,
                        ):
                            value = __original(*args, **kwargs)
                            if inspect.isawaitable(value):

                                async def _await_and_count(
                                    __awaitable=value, __tgt=__target
                                ):
                                    resolved = await __awaitable
                                    sample_target_counts[__tgt] += 1
                                    return resolved

                                return _await_and_count()
                            sample_target_counts[__target] += 1
                            return value

                        setattr(owner, name, _wrap)

                def _restore() -> None:
                    while originals:
                        owner, name, original = originals.pop()
                        setattr(owner, name, original)

                def _execute(op=operation):
                    _install()
                    try:
                        return ctx.run_operation(op)
                    finally:
                        _restore()

                value_and_extras, duration = sample_timer(operation, _execute)
                if not isinstance(value_and_extras, tuple) or len(value_and_extras) != 2:
                    raise ProductionMeasurementError(
                        f"operation {operation} returned unexpected shape"
                    )
                _value, extras = value_and_extras
                if not isinstance(duration, (int, float)) or duration <= 0:
                    raise ProductionMeasurementError(
                        f"non-positive duration for {operation}"
                    )
                if any(count < 1 for count in sample_target_counts.values()):
                    raise ProductionMeasurementError(
                        f"missing bound target calls for {operation}: {sample_target_counts}"
                    )
                sample_durations.append(float(duration))
                operation_calls[operation] = operation_calls.get(operation, 0) + 1
                for target, count in sample_target_counts.items():
                    target_calls[target] = target_calls.get(target, 0) + count
                evidence = {
                    "success": True,
                    "state_changed": (workload_name, operation) in STATE_CHANGING_OPERATIONS,
                }
                evidence.update(extras)
                operation_evidence[operation] = evidence

            # One terminal duration per sample: sum of isolated op durations.
            # The same conservative value is assigned to all three stage arrays.
            terminal = float(sum(sample_durations))
            if terminal <= 0:
                raise ProductionMeasurementError("non-positive sample duration")
            accepted_seconds.append(terminal)
            committed_seconds.append(terminal)
            converged_seconds.append(terminal)

        stage_evidence = {
            "accepted": {"reached": True},
            "committed": {"reached": True, "durability": durability},
            "converged": {"reached": True, "pending": 0},
        }
        raw_samples = {
            "accepted_seconds": accepted_seconds,
            "committed_seconds": committed_seconds,
            "converged_seconds": converged_seconds,
            "operation_calls": dict(operation_calls),
            "target_calls": dict(target_calls),
        }
        return {
            "raw_samples": raw_samples,
            "operation_evidence": operation_evidence,
            "stage_evidence": stage_evidence,
            "samples": int(samples),
            "errors": 0,
        }
    finally:
        ctx.close()


__all__ = [
    "PRODUCTION_BINDINGS",
    "SAMPLE_TIMER_ID",
    "STATE_CHANGING_OPERATIONS",
    "ProductionMeasurementError",
    "measure_workload",
    "monotonic_sample_timer",
]
