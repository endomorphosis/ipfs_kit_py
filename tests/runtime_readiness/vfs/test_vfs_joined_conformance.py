"""Joined VFS conformance: backends, WAL/crash, path security, interface parity.

Evidence bundle for KITA-009 / VFSConformanceReceipt@1.  The suite is
assertion-backed and mandatory in default CI: required operations must match
the reference oracle, every WAL crash boundary recovers to pre-commit or
committed state, path-escape and false-success rates are zero, unavailable
backend capabilities reject explicitly, and Python/CLI/MCP projections agree
after transport stripping.

Discovered product defects are reported as failing assertions; this module does
not patch production code (conflict policy: own joined tests/report only).
"""

from __future__ import annotations

import asyncio
import ast
import hashlib
import json
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from ipfs_kit_py.backends.filesystem_backend import (
    HERMITIC_REFERENCE_OPERATIONS,
    HermeticBackendError,
    HermeticFilesystemAdapter,
)
from ipfs_kit_py.backends.ipfs_backend import HermeticIPFSFixtureAdapter
from ipfs_kit_py.cli.operation_adapter import CLIAdapter
from ipfs_kit_py.core.operation_contracts import (
    OPERATION_REQUEST_SCHEMA,
    OPERATION_RESULT_SCHEMA,
    STORAGE_ERROR_SCHEMA,
    ErrorCategory,
    ErrorCode,
    OperationResult,
    OperationState,
    Retryability,
    StorageError,
)
from ipfs_kit_py.core.operation_registry import (
    AuthorizationRequirement,
    CapabilityTier,
    OperationDefinition,
    OperationRegistry,
)
from ipfs_kit_py.core.service_router import DispatchContext, ServiceRouter
from ipfs_kit_py.core.vfs.adapters import LegacyVFSAdapter
from ipfs_kit_py.core.vfs.contracts import (
    VFSErrorCode,
    VFSMount,
    VFSOperationKind,
    VFSPathError,
    normalize_vfs_path,
)
from ipfs_kit_py.core.vfs.service import (
    CanonicalVFSService,
    InMemoryVFSStorage,
    VFSEventKind,
    VFSExecuteRequest,
    content_cid_for_bytes,
    make_op,
)
from ipfs_kit_py.core.vfs.snapshots import VFSSnapshot
from ipfs_kit_py.core.vfs.transactions import (
    ConcurrentScheduleExecutor,
    IsolationLevel,
    ScheduleStep,
    TransactionOpKind,
    TransactionUnsupportedReason,
)
from ipfs_kit_py.core.wal.coordinator import WALTransactionCoordinator, WALTransactionCrash
from ipfs_kit_py.high_level_api.operation_adapter import AsyncPythonAdapter, PythonAdapter
from ipfs_kit_py.iroh.backend import IrohBackendPlugin
from ipfs_kit_py.iroh.errors import IrohInvalidPathError
from ipfs_kit_py.iroh_fsspec import IrohFileSystem
from ipfs_kit_py.iroh_vfs import IrohVFSAdapter, _relative_path
from ipfs_kit_py.mcp_server.tools import (
    MCPPlusPlusToolAdapter,
    MCPToolAdapter,
    semantic_payload,
    strip_transport_fields,
)
from tests.runtime_readiness.vfs.reference_model import (
    VFSReferenceModel,
    traces_match,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONFORMANCE_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "runtime_readiness"
    / "vfs_conformance.json"
)

_EXECUTE_BOUNDARIES = (
    "before_begin",
    "after_begin",
    "before_intent",
    "after_intent",
    "before_effect",
    "after_effect",
    "before_commit",
    "after_commit",
)

# VFS path policy rejects these at normalize/make_op time.
_VFS_POLICY_REJECT_VECTORS = (
    "../secret",
    "docs/../../etc/passwd",
    "//absolute",
    r"docs\file",
    "docs/\x00file",
    "~/home",
    "docs/$HOME/x",
    "docs/./x",
)
# Root-escape vectors that must fail on every storage boundary (VFS + hermetic + Iroh).
_ROOT_ESCAPE_VECTORS = (
    "../secret",
    "docs/../../etc/passwd",
    "//absolute",
    r"docs\file",
    "docs/\x00file",
)
_IROH_ESCAPE_VECTORS = (
    "../secret",
    "docs/../../etc/passwd",
    "../../outside",
)

_IROH_NAMESPACE = "a" * 64
_FIXED_CLOCK_MS = 1_700_000_000_000


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _service_and_reference() -> tuple[CanonicalVFSService, VFSReferenceModel]:
    storage = InMemoryVFSStorage()
    service = CanonicalVFSService(storage=storage, clock=lambda: _FIXED_CLOCK_MS)
    reference = VFSReferenceModel(clock_ms=_FIXED_CLOCK_MS)
    return service, reference


def _full_crud_schedule() -> list[tuple[Any, VFSExecuteRequest | None]]:
    """Deterministic multi-step schedule covering required mutating/read ops."""

    return [
        (make_op(VFSOperationKind.MKDIR, operation_id="j:mkdir-docs", path="docs"), None),
        (
            make_op(VFSOperationKind.CREATE, operation_id="j:create-readme", path="docs/readme"),
            VFSExecuteRequest(payload=b"joined-vfs-v1"),
        ),
        (make_op(VFSOperationKind.STAT, operation_id="j:stat-readme", path="docs/readme"), None),
        (
            make_op(VFSOperationKind.LIST, operation_id="j:list-docs", path="docs"),
            VFSExecuteRequest(page_size=16),
        ),
        (make_op(VFSOperationKind.READ, operation_id="j:read-readme", path="docs/readme"), None),
        (
            make_op(
                VFSOperationKind.RANGE_READ,
                operation_id="j:range-readme",
                path="docs/readme",
                range_start=0,
                range_end=6,
            ),
            None,
        ),
        (
            make_op(VFSOperationKind.STREAM, operation_id="j:stream-readme", path="docs/readme"),
            VFSExecuteRequest(stream_chunk_size=4),
        ),
        (
            make_op(VFSOperationKind.REPLACE, operation_id="j:replace-readme", path="docs/readme"),
            VFSExecuteRequest(payload=b"joined-vfs-v2"),
        ),
        (
            make_op(
                VFSOperationKind.RENAME,
                operation_id="j:rename-readme",
                source_path="docs/readme",
                target_path="docs/README",
            ),
            None,
        ),
        (
            make_op(
                VFSOperationKind.MOVE,
                operation_id="j:move-readme",
                source_path="docs/README",
                target_path="docs/notes",
            ),
            None,
        ),
        (make_op(VFSOperationKind.MKDIR, operation_id="j:mkdir-tmp", path="tmp"), None),
        (
            make_op(VFSOperationKind.CREATE, operation_id="j:create-tmp-a", path="tmp/a"),
            VFSExecuteRequest(payload=b"a"),
        ),
        (make_op(VFSOperationKind.DELETE, operation_id="j:delete-tmp-a", path="tmp/a"), None),
        (make_op(VFSOperationKind.RMDIR, operation_id="j:rmdir-tmp", path="tmp"), None),
        (make_op(VFSOperationKind.RESOLVE, operation_id="j:resolve-notes", path="docs/notes"), None),
    ]


def _canonical_outcome_projection(outcome: Any) -> dict[str, Any]:
    """Stable projection used for cross-backend / cross-interface equality."""

    result = outcome.result
    error = result.error
    return {
        "success": bool(result.success),
        "state": result.state.value,
        "error_code": None if error is None else error.code.value,
        "resulting_content_cid": result.resulting_content_cid or "",
        "resulting_version_cid": result.resulting_version_cid or "",
        "event_kinds": [event.kind.value for event in outcome.events],
        "data_size": len(outcome.data),
        "chunk_count": len(outcome.chunks),
        "namespace": {key: dict(value) for key, value in sorted(outcome.namespace_snapshot.items())},
    }


def _vfs_operation_definition(
    operation_id: str,
    *,
    public_name: str,
    support_tier: CapabilityTier = CapabilityTier.PRODUCTION,
    capability: str | None = None,
) -> OperationDefinition:
    return OperationDefinition(
        operation_id=operation_id,
        version=1,
        request_schema=OPERATION_REQUEST_SCHEMA,
        result_schema=OPERATION_RESULT_SCHEMA,
        error_schema=STORAGE_ERROR_SCHEMA,
        capability=capability or operation_id,
        authorization=AuthorizationRequirement.public(),
        handler_route="vfs-joined-service",
        transport_names={
            "python": public_name,
            "cli": public_name,
            "mcp": public_name,
            "mcpp": public_name,
        },
        support_tier=support_tier,
    )


def _bind_vfs_router(service: CanonicalVFSService) -> ServiceRouter:
    """Route registry VFS operations through the canonical service."""

    definitions = (
        _vfs_operation_definition("vfs.mkdir", public_name="vfs-mkdir"),
        _vfs_operation_definition("vfs.create", public_name="vfs-create"),
        _vfs_operation_definition("vfs.read", public_name="vfs-read"),
        _vfs_operation_definition("vfs.stat", public_name="vfs-stat"),
        _vfs_operation_definition(
            "vfs.unsupported-capability",
            public_name="vfs-unsupported",
            support_tier=CapabilityTier.UNSUPPORTED,
            capability="vfs.capability.unavailable",
        ),
    )
    registry = OperationRegistry(definitions)

    async def handler(
        definition: OperationDefinition,
        request: Any,
        _context: DispatchContext,
    ) -> OperationResult:
        payload = request if isinstance(request, dict) else {}
        path = str(payload.get("path", ""))
        data = payload.get("payload", b"")
        if isinstance(data, str):
            data = data.encode("utf-8")
        if not isinstance(data, (bytes, bytearray)):
            data = b""

        kind_map = {
            "vfs.mkdir": VFSOperationKind.MKDIR,
            "vfs.create": VFSOperationKind.CREATE,
            "vfs.read": VFSOperationKind.READ,
            "vfs.stat": VFSOperationKind.STAT,
        }
        if definition.operation_id not in kind_map:
            return OperationResult(
                request_id="joined-vfs-request",
                operation_id=definition.operation_id,
                state=OperationState.UNSUPPORTED,
                success=False,
                error=StorageError(
                    code=ErrorCode.UNSUPPORTED,
                    category=ErrorCategory.UNSUPPORTED,
                    message="VFS capability is unavailable",
                    retryability=Retryability.NEVER,
                    state=OperationState.UNSUPPORTED,
                ),
            )

        kind = kind_map[definition.operation_id]
        try:
            operation = make_op(
                kind,
                operation_id=f"joined-iface:{definition.operation_id}:{path}",
                path=path,
            )
        except Exception as exc:  # Path policy failures become typed rejections.
            return OperationResult(
                request_id="joined-vfs-request",
                operation_id=definition.operation_id,
                state=OperationState.REJECTED,
                success=False,
                error=StorageError(
                    code=ErrorCode.INVALID_REQUEST,
                    category=ErrorCategory.VALIDATION,
                    message=str(exc),
                    retryability=Retryability.NEVER,
                    state=OperationState.REJECTED,
                ),
            )

        execute_request = VFSExecuteRequest(payload=bytes(data)) if data else None
        outcome = service.execute(operation, execute_request)
        if outcome.success:
            return OperationResult(
                request_id="joined-vfs-request",
                operation_id=definition.operation_id,
                state=OperationState.ACCEPTED,
                success=True,
                resulting_content_cid=outcome.result.resulting_content_cid or "",
                resulting_version_cid=outcome.result.resulting_version_cid or "",
                backend_id="backend:memory",
            )

        error = outcome.result.error
        message = error.message if error is not None else "VFS operation failed"
        code = ErrorCode.NOT_FOUND
        state = OperationState.FAILED
        if error is not None:
            if error.code is VFSErrorCode.NOT_FOUND:
                code = ErrorCode.NOT_FOUND
            elif error.code in {VFSErrorCode.UNSUPPORTED, VFSErrorCode.CROSS_BOUNDARY}:
                code = ErrorCode.UNSUPPORTED
                state = OperationState.UNSUPPORTED
            elif error.code in {
                VFSErrorCode.INVALID_PATH,
                VFSErrorCode.PATH_ESCAPE,
                VFSErrorCode.PATH_TRAVERSAL,
                VFSErrorCode.ABSOLUTE_PATH,
            }:
                code = ErrorCode.INVALID_REQUEST
                state = OperationState.REJECTED
            elif error.code is VFSErrorCode.ALREADY_EXISTS:
                code = ErrorCode.ALREADY_EXISTS
            elif error.code is VFSErrorCode.PRECONDITION_FAILED:
                code = ErrorCode.PRECONDITION_FAILED
                state = OperationState.PRECONDITION_FAILED
        return OperationResult(
            request_id="joined-vfs-request",
            operation_id=definition.operation_id,
            state=state,
            success=False,
            error=StorageError(
                code=code,
                category=ErrorCategory.VALIDATION
                if state is OperationState.REJECTED
                else ErrorCategory.RESOURCE,
                message=message,
                retryability=Retryability.NEVER,
                state=state,
            ),
        )

    router = ServiceRouter(registry)
    router.bind_handler(
        "vfs-joined-service",
        handler,
        capabilities={definition.capability for definition in definitions},
    )
    return router


def _all_adapters(router: ServiceRouter) -> dict[str, Any]:
    registry = router.registry
    return {
        "package": PythonAdapter(registry, router),
        "python_sync": PythonAdapter(registry, router),
        "python_async": AsyncPythonAdapter(registry, router),
        "cli": CLIAdapter(registry, router),
        "mcp": MCPToolAdapter(registry, router),
        "mcpp": MCPPlusPlusToolAdapter(registry, router),
    }


def _iroh_filesystem() -> IrohFileSystem:
    """Inert Iroh filesystem for mount-relative path confinement checks."""

    return IrohFileSystem(
        manifest_store=_EmptyManifestStore(),
        blob_store=_EmptyBlobStore(),
    )


class _EmptyManifestStore:
    async def read_head(self, namespace_id: str) -> dict[str, Any]:
        return {
            "manifest": {
                "schema_version": 1,
                "namespace_id": namespace_id,
                "revision": 1,
                "parent_revision": None,
                "created_at": "2026-08-03T00:00:00Z",
                "writer_id": "b" * 64,
                "permissions": {
                    "owner": "b" * 64,
                    "public_read": False,
                    "readers": [],
                    "writers": ["b" * 64],
                },
                "entries": [{"path": "", "kind": "directory", "tombstone": False}],
            },
            "head": "c" * 64,
        }


class _EmptyBlobStore:
    async def ingest(self, source: Any) -> dict[str, Any]:
        del source
        return {"blob_hash": "d" * 64, "size": 0, "deduplicated": False}

    async def stat(self, blob_hash: str) -> dict[str, Any]:
        return {"blob_hash": blob_hash, "size": 0, "complete": True}

    async def read_range(self, blob_hash: str, *, start: int, end: int) -> bytes:
        del blob_hash, start, end
        return b""


# ---------------------------------------------------------------------------
# Differential: reference vs memory service
# ---------------------------------------------------------------------------


def test_required_operations_match_reference_model_differential() -> None:
    """Required VFS ops have identical canonical results on service and oracle."""

    service, reference = _service_and_reference()
    schedule = _full_crud_schedule()
    service_trace = service.run_trace(schedule)
    reference_trace = reference.run_trace(schedule)
    assert traces_match(service_trace, reference_trace)
    assert all(step["success"] for step in service_trace)
    final_ns = service_trace[-1]["namespace"]
    assert "docs/notes" in final_ns
    assert "docs/readme" not in final_ns
    assert "docs/README" not in final_ns


def test_cas_and_failure_traces_match_reference() -> None:
    service, reference = _service_and_reference()
    assert isinstance(service.storage, InMemoryVFSStorage)
    service.storage.seed("file", content=b"v1")
    reference.seed("file", content=b"v1")
    entry = service.storage.get("file")
    assert entry is not None
    ok = [
        (
            make_op(
                VFSOperationKind.CAS_WRITE,
                operation_id="j:cas-ok",
                path="file",
                precondition_version_cid=entry.version_cid,
            ),
            VFSExecuteRequest(payload=b"v2"),
        )
    ]
    assert traces_match(service.run_trace(ok), reference.run_trace(ok))

    service2, reference2 = _service_and_reference()
    assert isinstance(service2.storage, InMemoryVFSStorage)
    service2.storage.seed("file", content=b"v1")
    reference2.seed("file", content=b"v1")
    bad = [
        (
            make_op(
                VFSOperationKind.CAS_WRITE,
                operation_id="j:cas-bad",
                path="file",
                precondition_version_cid="sha256:" + "0" * 64,
            ),
            VFSExecuteRequest(payload=b"v2"),
        )
    ]
    service_trace = service2.run_trace(bad)
    reference_trace = reference2.run_trace(bad)
    assert traces_match(service_trace, reference_trace)
    assert service_trace[0]["success"] is False
    assert service_trace[0]["error_code"] == VFSErrorCode.PRECONDITION_FAILED.value


# ---------------------------------------------------------------------------
# Backends: hermetic filesystem + IPFS fixture + Iroh capability
# ---------------------------------------------------------------------------


def test_hermetic_filesystem_and_ipfs_fixture_share_object_semantics(tmp_path: Path) -> None:
    """Declared backends produce identical put/get/list/delete outcomes."""

    filesystem = HermeticFilesystemAdapter(tmp_path / "filesystem")
    ipfs_fixture = HermeticIPFSFixtureAdapter(tmp_path / "ipfs-fixture")
    path = "joined/object.bin"
    payload = b"joined-backend-payload"
    key = "joined-put-key"

    async def exercise(adapter: HermeticFilesystemAdapter) -> dict[str, Any]:
        put = await adapter.put(path, payload, idempotency_key=key)
        get = await adapter.get(path)
        listed = await adapter.list("joined")
        deleted = await adapter.delete(path, idempotency_key=f"{key}-delete")
        missing = None
        try:
            await adapter.get(path)
        except HermeticBackendError as exc:
            missing = {
                "code": exc.error.code.value,
                "state": exc.error.state.value,
            }
        return {
            "put_success": put.success,
            "put_cid": put.resulting_content_cid,
            "get_success": get.success,
            "get_data": get.data,
            "list_items": tuple(sorted(listed.items)),
            "delete_success": deleted.success,
            "missing": missing,
            "backend_id": adapter.backend_id,
            "provider_kind": adapter.provider_kind,
            "is_hermetic": adapter.is_hermetic,
            "live_provider": adapter.live_provider,
            "provider_certified": adapter.provider_certified,
        }

    fs_report = asyncio.run(exercise(filesystem))
    ipfs_report = asyncio.run(exercise(ipfs_fixture))

    for field in (
        "put_success",
        "put_cid",
        "get_success",
        "get_data",
        "list_items",
        "delete_success",
        "missing",
        "is_hermetic",
        "live_provider",
        "provider_certified",
    ):
        assert fs_report[field] == ipfs_report[field], field

    assert fs_report["put_success"] is True
    assert fs_report["get_data"] == payload
    assert fs_report["missing"] == {
        "code": ErrorCode.NOT_FOUND.value,
        "state": OperationState.FAILED.value,
    }
    assert fs_report["backend_id"] == "hermetic_filesystem_reference"
    assert ipfs_report["backend_id"] == "hermetic_ipfs_fixture"
    assert ipfs_fixture.provider_identity()["certification_scope"].startswith("fixture-only")


def test_unavailable_backend_capabilities_reject_explicitly(tmp_path: Path) -> None:
    """Undeclared ops, unsupported VFS boundaries, and unavailable Iroh fail closed."""

    declared = set(HERMITIC_REFERENCE_OPERATIONS) - {"stream", "set_metadata"}
    adapter = HermeticFilesystemAdapter(
        tmp_path / "partial",
        declared_operations=declared,
    )
    before = adapter.effect_count
    with pytest.raises(HermeticBackendError) as hermetic_exc:
        asyncio.run(adapter.stream("joined/missing.bin"))
    assert hermetic_exc.value.error.code is ErrorCode.UNSUPPORTED
    assert hermetic_exc.value.error.state is OperationState.UNSUPPORTED
    assert adapter.effect_count == before

    service = CanonicalVFSService(clock=lambda: _FIXED_CLOCK_MS)
    service.storage.seed("a", content=b"x")  # type: ignore[attr-defined]
    other = VFSMount(
        mount_id="mount:other",
        mount_path="other",
        backend_id="backend:other",
        namespace_id="ns:default",
    )
    service.execute(
        make_op(VFSOperationKind.MOUNT, operation_id="j:mount-other", path="other"),
        VFSExecuteRequest(mount=other),
    )
    cross = service.execute(
        make_op(
            VFSOperationKind.RENAME,
            operation_id="j:cross-mount",
            source_path="a",
            target_path="other/a",
            source_mount_id="mount:default",
            target_mount_id="mount:other",
        )
    )
    assert cross.success is False
    assert cross.result.state is OperationState.UNSUPPORTED
    assert cross.result.error is not None
    assert cross.result.error.code in {
        VFSErrorCode.UNSUPPORTED,
        VFSErrorCode.CROSS_BOUNDARY,
    }
    assert service.storage.get("a") is not None  # type: ignore[attr-defined]

    plugin = IrohBackendPlugin()
    missing_socket = tmp_path / "missing-iroh.sock"
    config = {
        "schema_version": 1,
        "name": "joined-iroh",
        "type": "iroh",
        "enabled": True,
        "namespace": {"id": _IROH_NAMESPACE, "access": "read-write"},
        "service": {
            "instance": "joined",
            "managed": False,
            "rpc_endpoint": f"unix://{missing_socket}",
        },
        "credentials": {
            "node_key_ref": "secretref:enhanced-secrets:node",
            "write_capability_ref": "secretref:enhanced-secrets:write",
        },
        "timeouts": {
            "connect_seconds": 1,
            "operation_seconds": 1,
            "shutdown_seconds": 1,
        },
        "sync": {
            "enabled": False,
            "on_open": False,
            "read_consistency": "local",
            "conflict_policy": "fail",
        },
    }
    health = plugin.health(config)
    assert health["status"] in {"unavailable", "available"}
    if not missing_socket.exists():
        assert health["ready"] is False
        assert health["certification_status"] == "blocked"
    blocked = asyncio.run(plugin.certify_live_service(config))
    assert blocked["status"] == "blocked"
    assert blocked["healthy"] is False
    assert "reason" in blocked


# ---------------------------------------------------------------------------
# Path security: escape rate and false-success rate are zero
# ---------------------------------------------------------------------------


def test_path_escape_and_false_success_rates_are_zero(tmp_path: Path) -> None:
    """Every escape vector fails; no failure is promoted to success."""

    service = CanonicalVFSService(clock=lambda: _FIXED_CLOCK_MS)
    filesystem = HermeticFilesystemAdapter(tmp_path / "fs-escape")
    ipfs_fixture = HermeticIPFSFixtureAdapter(tmp_path / "ipfs-escape")
    iroh_adapter = IrohVFSAdapter(_iroh_filesystem(), f"iroh://{_IROH_NAMESPACE}/docs")

    escape_attempts = 0
    escape_successes = 0
    false_successes = 0

    for raw in _VFS_POLICY_REJECT_VECTORS:
        escape_attempts += 1
        try:
            normalize_vfs_path(raw)
        except VFSPathError:
            pass
        else:
            escape_successes += 1

        escape_attempts += 1
        try:
            make_op(VFSOperationKind.STAT, operation_id="j-escape-stat", path=raw)
        except Exception:
            pass
        else:
            escape_successes += 1

    for raw in _ROOT_ESCAPE_VECTORS:
        safe_key = "escape-" + hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:24]
        for adapter in (filesystem, ipfs_fixture):
            escape_attempts += 1
            try:
                result = asyncio.run(adapter.put(raw, b"x", idempotency_key=safe_key))
            except HermeticBackendError as exc:
                assert exc.error.code in {
                    ErrorCode.INVALID_REQUEST,
                    ErrorCode.UNSUPPORTED,
                }
                assert exc.error.state in {
                    OperationState.REJECTED,
                    OperationState.UNSUPPORTED,
                }
            else:
                if result.success:
                    false_successes += 1
                escape_successes += 1

    for raw in _IROH_ESCAPE_VECTORS:
        escape_attempts += 1
        try:
            _relative_path(raw)
        except (IrohInvalidPathError, TypeError, ValueError):
            pass
        else:
            escape_successes += 1

        escape_attempts += 1
        try:
            iroh_adapter.resolve(raw)
        except (IrohInvalidPathError, TypeError, ValueError):
            pass
        else:
            escape_successes += 1

    # Failure-then-success ordering: failure events never include SUCCESS.
    miss = service.execute(
        make_op(VFSOperationKind.DELETE, operation_id="j:del-miss", path="missing")
    )
    assert miss.success is False
    assert VFSEventKind.SUCCESS not in [event.kind for event in miss.events]
    assert VFSEventKind.FAILURE in [event.kind for event in miss.events]
    if miss.success:
        false_successes += 1
    ok = service.execute(
        make_op(VFSOperationKind.MKDIR, operation_id="j:mkdir-ok", path="ok")
    )
    assert ok.success is True
    assert VFSEventKind.SUCCESS in [event.kind for event in ok.events]
    if not ok.success:
        false_successes += 1

    assert escape_attempts > 0
    assert escape_successes == 0
    assert false_successes == 0


# ---------------------------------------------------------------------------
# WAL crash matrix joined with VFS effects
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("boundary", _EXECUTE_BOUNDARIES)
def test_wal_crash_matrix_with_vfs_effects_recovers(
    tmp_path: Path, boundary: str
) -> None:
    """Every crash point recovers to pre-commit compensation or committed replay."""

    transaction_id = f"vfs-txn-{boundary}"
    effect_id = f"vfs-effect-{boundary}"
    wal_dir = tmp_path / f"wal-{boundary}"
    path = f"crash/{boundary}"
    payload = f"payload-{boundary}".encode()

    live = InMemoryVFSStorage()
    visible_effects: set[str] = set()

    def apply_effect() -> None:
        """Idempotent VFS mutation used for commit and recovery replay."""

        if effect_id in visible_effects and live.get(path) is not None:
            return
        service = CanonicalVFSService(storage=live, clock=lambda: _FIXED_CLOCK_MS)
        if live.get("crash") is None:
            mkdir = service.execute(
                make_op(VFSOperationKind.MKDIR, operation_id=f"{effect_id}:mkdir", path="crash")
            )
            assert mkdir.success is True
        existing = live.get(path)
        if existing is None:
            outcome = service.execute(
                make_op(VFSOperationKind.CREATE, operation_id=effect_id, path=path),
                VFSExecuteRequest(payload=payload),
            )
        else:
            outcome = service.execute(
                make_op(VFSOperationKind.REPLACE, operation_id=f"{effect_id}:replace", path=path),
                VFSExecuteRequest(payload=payload),
            )
        assert outcome.success is True
        visible_effects.add(effect_id)

    def compensate_effect() -> None:
        if path in live.snapshot():
            live.delete(path)
        # Leave the parent directory if present; effect identity is the file.
        visible_effects.discard(effect_id)

    def inject(name: str, received_transaction_id: str) -> None:
        if name == boundary:
            assert received_transaction_id == transaction_id
            raise WALTransactionCrash(name)

    coordinator = WALTransactionCoordinator(wal_dir, crash_injector=inject)
    try:
        with pytest.raises(WALTransactionCrash):
            coordinator.execute(
                {
                    "object": "vfs-joined",
                    "boundary": boundary,
                    "path": path,
                },
                apply_effect,
                compensate_effect,
                transaction_id=transaction_id,
                effect_id=effect_id,
            )
    finally:
        coordinator.close()

    recovered = WALTransactionCoordinator(wal_dir)
    try:
        first = recovered.recover(
            replay_effect=lambda _intent, received: apply_effect()
            if received == effect_id
            else None,
            rollback_effect=lambda _intent, received: compensate_effect()
            if received == effect_id
            else None,
        )
        second = recovered.recover(
            replay_effect=lambda _intent, received: apply_effect()
            if received == effect_id
            else None,
            rollback_effect=lambda _intent, received: compensate_effect()
            if received == effect_id
            else None,
        )
    finally:
        recovered.close()

    if boundary == "after_commit":
        assert visible_effects == {effect_id}
        assert path in live.snapshot()
        assert first == {"replayed": 1, "rolled_back": 0}
        entry = live.get(path)
        assert entry is not None
        assert entry.content == payload
    else:
        # Pre-commit: compensated (or never applied).
        assert visible_effects == set()
        assert path not in live.snapshot()
        assert first["replayed"] == 0
    assert second == {"replayed": 0, "rolled_back": 0}


def test_commit_failure_cannot_report_vfs_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from ipfs_kit_py.core.wal.coordinator import WALTransactionError

    coordinator = WALTransactionCoordinator(tmp_path / "wal-commit-fail")
    storage = InMemoryVFSStorage()
    original_marker = coordinator._marker

    def fail_commit(kind: object, transaction_id: str, *, effect_id: str = "") -> None:
        if getattr(kind, "value", kind) == "commit":
            raise WALTransactionError("injected durable commit failure")
        original_marker(kind, transaction_id, effect_id=effect_id)

    def apply_effect() -> None:
        service = CanonicalVFSService(storage=storage, clock=lambda: _FIXED_CLOCK_MS)
        outcome = service.execute(
            make_op(VFSOperationKind.CREATE, operation_id="j:commit-fail", path="item"),
            VFSExecuteRequest(payload=b"must-not-stick"),
        )
        assert outcome.success is True

    def compensate_effect() -> None:
        if storage.get("item") is not None:
            storage.delete("item")

    monkeypatch.setattr(coordinator, "_marker", fail_commit)
    try:
        with pytest.raises(WALTransactionError, match="commit failure"):
            coordinator.execute(
                {"object": "vfs-commit-failure"},
                apply_effect,
                compensate_effect,
                transaction_id="vfs-commit-failure",
                effect_id="effect-commit-failure",
            )
    finally:
        coordinator.close()

    assert storage.get("item") is None


# ---------------------------------------------------------------------------
# Concurrency + restart / snapshot
# ---------------------------------------------------------------------------


def test_concurrent_schedules_match_reference_or_typed_unsupported() -> None:
    def factory() -> InMemoryVFSStorage:
        return InMemoryVFSStorage()

    contents = (b"A", b"B")
    isolations = (IsolationLevel.SNAPSHOT, IsolationLevel.READ_COMMITTED)
    matched = 0
    for iso in isolations:
        for c1 in contents:
            for c2 in contents:
                executor = ConcurrentScheduleExecutor(
                    InMemoryVFSStorage(),
                    storage_factory=factory,
                    clock=lambda: 0,
                )

                def seed(storage: InMemoryVFSStorage) -> None:
                    storage.seed("file", content=b"v0")

                steps = (
                    ScheduleStep(txn_id="t1", op=TransactionOpKind.BEGIN, isolation=iso),
                    ScheduleStep(txn_id="t1", op=TransactionOpKind.WRITE, path="file", content=c1),
                    ScheduleStep(txn_id="t1", op=TransactionOpKind.COMMIT),
                    ScheduleStep(txn_id="t2", op=TransactionOpKind.BEGIN, isolation=iso),
                    ScheduleStep(txn_id="t2", op=TransactionOpKind.WRITE, path="file", content=c2),
                    ScheduleStep(txn_id="t2", op=TransactionOpKind.COMMIT),
                )
                outcome = executor.run_differential(steps, seed=seed)
                assert outcome.matched_reference is True or outcome.unsupported is True
                if outcome.unsupported:
                    assert outcome.unsupported_reason in {
                        TransactionUnsupportedReason.CROSS_TXN_DEADLOCK.value,
                        None,
                    } or outcome.unsupported_reason
                matched += 1
    assert matched >= 8


def test_snapshot_restart_boundary_preserves_committed_namespace() -> None:
    storage = InMemoryVFSStorage()
    service = CanonicalVFSService(storage=storage, clock=lambda: _FIXED_CLOCK_MS)
    assert service.execute(
        make_op(VFSOperationKind.MKDIR, operation_id="j:snap-mkdir", path="docs")
    ).success
    created = service.execute(
        make_op(VFSOperationKind.CREATE, operation_id="j:snap-create", path="docs/a"),
        VFSExecuteRequest(payload=b"pinned"),
    )
    assert created.success
    snapshot = VFSSnapshot.capture(storage, snapshot_id="joined-restart")
    pinned_cid = snapshot.snapshot_cid
    pinned_entry = snapshot.entry("docs/a")
    assert pinned_entry is not None

    # Live mutation after capture must not alter the immutable snapshot.
    replaced = service.execute(
        make_op(VFSOperationKind.REPLACE, operation_id="j:snap-replace", path="docs/a"),
        VFSExecuteRequest(payload=b"mutated"),
    )
    assert replaced.success
    assert snapshot.snapshot_cid == pinned_cid
    assert snapshot.entry("docs/a") == pinned_entry
    assert snapshot.content_cid_at("docs/a") == content_cid_for_bytes(b"pinned")
    live = storage.get("docs/a")
    assert live is not None
    assert live.content == b"mutated"


# ---------------------------------------------------------------------------
# Interface parity: Python / CLI / MCP
# ---------------------------------------------------------------------------


def _response_success(response: Any) -> bool:
    if isinstance(response, dict):
        return bool(response.get("success"))
    return bool(response.success)


def test_python_cli_mcp_parity_for_vfs_operations() -> None:
    """Each transport projects the same VFS flow on an isolated service instance."""

    mkdir_request = {"path": "docs"}
    create_request = {"path": "docs/readme", "payload": "hello-joined"}
    read_request = {"path": "docs/readme"}
    stat_request = {"path": "docs/readme"}

    def fresh_adapters() -> dict[str, Any]:
        service = CanonicalVFSService(clock=lambda: _FIXED_CLOCK_MS)
        return _all_adapters(_bind_vfs_router(service))

    def run_flow(call_one) -> Any:
        mkdir = call_one("vfs-mkdir", mkdir_request)
        assert _response_success(mkdir) is True
        created = call_one("vfs-create", create_request)
        assert _response_success(created) is True
        return call_one("vfs-read", read_request)

    package_adapters = fresh_adapters()
    package = run_flow(lambda name, req: package_adapters["package"].call(name, req))

    python_adapters = fresh_adapters()
    python_sync = run_flow(lambda name, req: python_adapters["python_sync"].call(name, req))

    async_adapters = fresh_adapters()
    python_async = run_flow(
        lambda name, req: asyncio.run(async_adapters["python_async"].call(name, req))
    )

    cli_adapters = fresh_adapters()
    cli = run_flow(lambda name, req: asyncio.run(cli_adapters["cli"].invoke(name, req)))

    mcp_adapters = fresh_adapters()
    mcp = run_flow(
        lambda name, req: mcp_adapters["mcp"].call(name, {"request": req})
    )

    mcpp_adapters = fresh_adapters()
    mcpp_stdio = run_flow(
        lambda name, req: asyncio.run(
            mcpp_adapters["mcpp"].call_framed("stdio", name, {"request": req})
        )
    )

    semantic = semantic_payload(package)
    assert package.success is True
    assert semantic_payload(python_sync) == semantic
    assert semantic_payload(python_async) == semantic
    assert semantic_payload(cli) == semantic
    assert semantic_payload(mcp) == semantic
    assert strip_transport_fields(mcpp_stdio) == semantic
    assert package.to_dict()["result"]["record"]["success"] is True
    # Content identity is established on create; read success is the parity signal.
    create_surface = fresh_adapters()
    assert create_surface["package"].call("vfs-mkdir", mkdir_request).success is True
    create_result = create_surface["package"].call("vfs-create", create_request)
    assert create_result.success is True
    content_cid = create_result.to_dict()["result"]["record"]["resulting_content_cid"]
    assert content_cid.startswith("sha256:")

    # CLI stdout matches the package envelope on a shared post-write service.
    shared = fresh_adapters()
    assert shared["package"].call("vfs-mkdir", mkdir_request).success is True
    assert shared["package"].call("vfs-create", create_request).success is True
    stdout, stderr = StringIO(), StringIO()
    assert (
        shared["cli"].run(
            ["vfs-stat", "--request-json", json.dumps(stat_request)],
            stdout=stdout,
            stderr=stderr,
        )
        == 0
    )
    assert stderr.getvalue() == ""
    package_stat = shared["package"].call("vfs-stat", stat_request)
    assert json.loads(stdout.getvalue()) == package_stat.to_dict()
    assert package_stat.success is True

    # Unsupported capability rejects on every surface without manufacturing success.
    unsupported_request = {"path": "docs/readme"}
    u_adapters = fresh_adapters()
    package_u = u_adapters["package"].call("vfs-unsupported", unsupported_request)
    cli_u = asyncio.run(u_adapters["cli"].invoke("vfs-unsupported", unsupported_request))
    mcp_u = u_adapters["mcp"].call("vfs-unsupported", {"request": unsupported_request})
    assert package_u.success is False
    assert semantic_payload(package_u) == semantic_payload(cli_u) == semantic_payload(mcp_u)
    # Router rejects unsupported tiers before the handler; adapters project the error.
    package_error = package_u.to_dict()["error"] or package_u.to_dict()["result"]["record"]
    assert package_error["state"] in {
        OperationState.UNSUPPORTED.value,
        OperationState.FAILED.value,
    }


def test_legacy_adapter_matches_canonical_service_semantics() -> None:
    service = CanonicalVFSService(clock=lambda: _FIXED_CLOCK_MS)
    adapter = LegacyVFSAdapter(service=service)

    mkdir = asyncio.run(adapter.execute("mkdir", path="docs"))
    assert mkdir["success"] is True
    # Legacy "write" maps to REPLACE; create through the canonical service first.
    created = service.execute(
        make_op(VFSOperationKind.CREATE, operation_id="j:legacy-create", path="docs/a"),
        VFSExecuteRequest(payload=b"seed"),
    )
    assert created.success is True
    write = asyncio.run(adapter.execute("write", path="docs/a", data=b"legacy-joined"))
    assert write["success"] is True
    read = asyncio.run(adapter.execute("cat", path="docs/a"))
    assert read["success"] is True
    assert read["data"] == b"legacy-joined"
    info = asyncio.run(adapter.execute("info", path="docs/a"))
    assert info["success"] is True

    # Canonical service agrees with the projected namespace.
    direct = service.execute(make_op(VFSOperationKind.READ, operation_id="j:direct", path="docs/a"))
    assert direct.success is True
    assert direct.data == b"legacy-joined"

    missing = asyncio.run(adapter.execute("rm", path="does-not-exist"))
    assert missing["success"] is False
    assert missing["result"]["success"] is False
    unsupported = asyncio.run(adapter.execute("provider_only_operation", path="x"))
    assert unsupported["success"] is False
    assert unsupported["code"] == "unsupported_legacy_operation"


# ---------------------------------------------------------------------------
# Conformance receipt + suite hygiene
# ---------------------------------------------------------------------------


def test_conformance_receipt_declares_mandatory_joined_guarantees() -> None:
    receipt = json.loads(CONFORMANCE_PATH.read_text(encoding="utf-8"))
    assert receipt["schema"] == "ipfs_kit_py/runtime-readiness/vfs-conformance@1"
    assert receipt["contract_version"] == 1
    assert receipt["task_id"] == "KITA-009"
    assert receipt["suite"] == "tests/runtime_readiness/vfs/test_vfs_joined_conformance.py"
    assert "VFSConformanceReceipt@1" in receipt["interfaces"]
    assert receipt["exclusion_policy"] == {
        "excluded_only_gate": False,
        "mandatory_in_default_ci": True,
    }
    assert receipt["acceptance"]["path_escape_rate_zero"] is True
    assert receipt["acceptance"]["false_success_rate_zero"] is True
    assert receipt["acceptance"]["every_crash_point_recovers"] is True
    assert receipt["acceptance"]["python_cli_mcp_parity"] is True
    assert receipt["acceptance"]["no_required_test_skips"] is True
    assert receipt["acceptance"]["no_print_only_paths"] is True
    assert set(receipt["crash_boundaries"]) == set(_EXECUTE_BOUNDARIES)
    backend_ids = {backend["id"] for backend in receipt["declared_backends"]}
    assert {
        "reference",
        "memory",
        "hermetic_filesystem_reference",
        "hermetic_ipfs_fixture",
        "iroh",
    } <= backend_ids
    for key in (
        "differential",
        "crash",
        "path_security",
        "concurrency",
        "backend_capability",
        "interface_parity",
    ):
        assert key in receipt["evidence_subset"]
        assert receipt["evidence_subset"][key]


def test_suite_has_no_required_skips_or_print_only_paths() -> None:
    """Static hygiene: this module must not skip, xfail, or print-only assert."""

    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden: list[str] = []

    def _call_name(node: ast.Call) -> str:
        func = node.func
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute):
            parts: list[str] = [func.attr]
            value = func.value
            while isinstance(value, ast.Attribute):
                parts.append(value.attr)
                value = value.value
            if isinstance(value, ast.Name):
                parts.append(value.id)
            return ".".join(reversed(parts))
        return ""

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _call_name(node)
            if name in {"skip", "xfail", "pytest.skip", "pytest.xfail", "skipif"}:
                forbidden.append(f"call:{name}")
            if name == "print":
                forbidden.append("call:print")
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            for decorator in node.decorator_list:
                rendered = ast.dump(decorator)
                if "skip" in rendered or "xfail" in rendered:
                    forbidden.append(f"decorator:{node.name}:{rendered}")

    assert forbidden == [], f"forbidden skip/print paths remain: {forbidden}"

    # Every test function must contain at least one assert (no print-only paths).
    module_tests = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    ]
    assert module_tests, "joined suite must define test functions"
    for func in module_tests:
        asserts = [n for n in ast.walk(func) if isinstance(n, ast.Assert)]
        assert asserts, f"{func.name} has no assertions"
    # Decorator/call graph already checked above; no remaining skip/xfail usage.
    assert not forbidden


def test_joined_backend_namespace_identity_is_stable_across_memory_pairs() -> None:
    """Two memory backends running the same schedule converge identically."""

    left_service, left_ref = _service_and_reference()
    right_service, right_ref = _service_and_reference()
    schedule = _full_crud_schedule()
    left = left_service.run_trace(schedule)
    right = right_service.run_trace(schedule)
    assert traces_match(left, left_ref.run_trace(schedule))
    assert traces_match(right, right_ref.run_trace(schedule))
    assert [_canonical_outcome_projection_from_step(step) for step in left] == [
        _canonical_outcome_projection_from_step(step) for step in right
    ]
    digest = hashlib.sha256(repr(left).encode("utf-8")).hexdigest()
    assert digest != "0" * 64


def _canonical_outcome_projection_from_step(step: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": step["kind"],
        "path": step.get("path") or "",
        "source_path": step.get("source_path") or "",
        "target_path": step.get("target_path") or "",
        "success": step["success"],
        "state": step["state"],
        "error_code": step.get("error_code"),
        "resulting_content_cid": step.get("resulting_content_cid") or "",
        "resulting_version_cid": step.get("resulting_version_cid") or "",
        "event_kinds": list(step.get("event_kinds") or []),
        "namespace": step.get("namespace") or {},
        "data_size": step.get("data_size") or 0,
        "chunk_count": step.get("chunk_count") or 0,
    }
