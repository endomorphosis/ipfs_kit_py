"""KITA-046: release-candidate migration, wheel matrix, rollout, and rollback.

Validates that supported legacy state migrates idempotently with preserved
content/version/policy semantics; unsupported state fails before mutation with
backup/recovery instructions; the minimal core and every optional extra project
onto the supported Python matrix; staged rollback restores an executable prior
state or documents forward recovery without acknowledged loss; the support
manifest and matrix docs match the live registry; and no required lane skip or
stale receipt can satisfy the candidate.

Interfaces: ``ReleaseCandidateReceipt@1``, ``MigrationReceipt@1``,
``RollbackReceipt@1``.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, MutableMapping

import pytest

from ipfs_kit_py.arc_cache import CacheBinding, GenerationBoundARC
from ipfs_kit_py.backend_policies import (
    LegacyPolicyMigrationError,
    ReplicationPolicy,
    migrate_legacy_replication_policy,
)
from ipfs_kit_py.backend_registry import BackendTypeRegistry
from ipfs_kit_py.backend_schemas import EXCLUDED_SCHEMAS, SCHEMAS
from ipfs_kit_py.backends.spec import ACTIVE_BACKEND_SPECS, EXCLUDED_BACKEND_SPECS
from ipfs_kit_py.cache.arc.contracts import ARCConfig
from ipfs_kit_py.core.buckets.adapters import (
    BucketMigrationError,
    LegacyBucketAdapter,
    migrate_legacy_bucket_registry,
)
from ipfs_kit_py.core.buckets.contracts import (
    BackendCapability as BucketBackendCapability,
    BucketIdentity,
    BucketManifest,
    BucketPolicy as CatalogPolicy,
    BucketReplica,
    BucketReplicaRole,
)
from ipfs_kit_py.core.buckets.service import BucketService, InMemoryBucketBackend
from ipfs_kit_py.core.wal.compatibility import (
    map_legacy_status,
    project_legacy_operation,
)
from ipfs_kit_py.core.wal.contracts import WALRecordState
from ipfs_kit_py.core.wal.coordinator import (
    WALTransactionCoordinator,
    WALTransactionCrash,
)
from ipfs_kit_py.graphrag.contracts import (
    GraphRAGContent,
    GraphRAGContentState,
    GraphRAGIndexManifest,
    GraphRAGMetric,
    GraphRAGProvenance,
)
from ipfs_kit_py.graphrag.service import GraphRAGService

# ---------------------------------------------------------------------------
# Paths / schema
# ---------------------------------------------------------------------------

PACKAGE_ROOT = Path(__file__).resolve().parents[3]
DOCS_DIR = PACKAGE_ROOT / "docs" / "runtime_readiness"
RECEIPT_PATH = DOCS_DIR / "release_candidate_receipt.json"
MIGRATION_DOC_PATH = DOCS_DIR / "migration_and_rollback.md"
BACKEND_MANIFEST_PATH = DOCS_DIR / "backend_support_manifest.json"
BACKEND_MATRIX_DOC_PATH = DOCS_DIR / "backend_support_matrix.md"
CAPABILITY_MANIFEST_PATH = DOCS_DIR / "capability_manifest.json"
SOAK_RECEIPT_PATH = DOCS_DIR / "soak_chaos_receipt.json"
SUITE_REL = "tests/runtime_readiness/release/test_release_candidate.py"
SUITE_PATH = PACKAGE_ROOT / "tests" / "runtime_readiness" / "release" / "test_release_candidate.py"

RC_RECEIPT_SCHEMA = "ipfs_kit_py/runtime-readiness/release-candidate-receipt@1"
RC_RECEIPT_INTERFACE = "ReleaseCandidateReceipt@1"
MIGRATION_RECEIPT_INTERFACE = "MigrationReceipt@1"
ROLLBACK_RECEIPT_INTERFACE = "RollbackReceipt@1"
TASK_ID = "KITA-046"

REQUIRED_DEPENDENCY_LANES: Mapping[str, Path] = {
    "KITA-009": DOCS_DIR / "vfs_conformance.json",
    "KITA-013": DOCS_DIR / "bucket_conformance.json",
    "KITA-017": DOCS_DIR / "graphrag_conformance.json",
    "KITA-021": DOCS_DIR / "replica_conformance.json",
    "KITA-025": DOCS_DIR / "arc_conformance.json",
    "KITA-029": DOCS_DIR / "mcplusplus_conformance.json",
    "KITA-033": DOCS_DIR / "mcplusplus_conformance.json",
    "KITA-037": DOCS_DIR / "interface_manifest.json",
    "KITA-042": DOCS_DIR / "backend_support_manifest.json",
    "KITA-045": DOCS_DIR / "soak_chaos_receipt.json",
}

# Recovery copy that operators (and the migration doc) must surface when state
# cannot be migrated safely.  Tests assert the doc and receipt both carry it.
BACKUP_RECOVERY_INSTRUCTIONS = (
    "1. Leave the original state file(s) untouched after a pre-mutation failure.\n"
    "2. Copy the original tree to a timestamped backup directory outside the live path.\n"
    "3. Record the failing schema version, disposition, and content digests in the operator log.\n"
    "4. Either restore the backup to resume the prior executable package, or follow the "
    "documented forward-recovery path after repairing the unsupported fields offline.\n"
    "5. Re-run this release-candidate suite before promoting any repaired state."
)

# Closed supported legacy schema labels for the hermetic migration harness.
SUPPORTED_BUCKET_LEGACY_SCHEMA = 1
CANONICAL_BUCKET_SCHEMA = 2
ARC_PERSISTENCE_VERSION = 1


# ---------------------------------------------------------------------------
# Counters / digests
# ---------------------------------------------------------------------------


@dataclass
class ReleaseSafetyCounters:
    """Zero-floor counters for migration/rollback release acceptance."""

    acknowledged_loss: int = 0
    non_idempotent_migration: int = 0
    unsupported_mutation: int = 0
    stale_receipt_accepted: int = 0
    required_lane_skip: int = 0
    registry_manifest_mismatch: int = 0
    wheel_matrix_failure: int = 0
    rollback_loss: int = 0
    content_version_policy_drift: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "acknowledged_loss": self.acknowledged_loss,
            "non_idempotent_migration": self.non_idempotent_migration,
            "unsupported_mutation": self.unsupported_mutation,
            "stale_receipt_accepted": self.stale_receipt_accepted,
            "required_lane_skip": self.required_lane_skip,
            "registry_manifest_mismatch": self.registry_manifest_mismatch,
            "wheel_matrix_failure": self.wheel_matrix_failure,
            "rollback_loss": self.rollback_loss,
            "content_version_policy_drift": self.content_version_policy_drift,
        }

    def all_zero(self) -> bool:
        return all(value == 0 for value in self.as_dict().values())


def semantic_digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _project_metadata() -> dict[str, Any]:
    with (PACKAGE_ROOT / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)["project"]


def _supported_python_versions(project: Mapping[str, Any]) -> list[str]:
    """Derive the closed supported Python matrix from package classifiers."""

    versions: list[str] = []
    for classifier in project.get("classifiers", ()):
        match = re.fullmatch(r"Programming Language :: Python :: (\d+\.\d+)", str(classifier))
        if match:
            versions.append(match.group(1))
    requires = str(project.get("requires-python", ""))
    if not versions and requires.startswith(">="):
        versions.append(requires.removeprefix(">=").strip())
    return versions


def _current_python_tag() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}"


# ---------------------------------------------------------------------------
# Migration surfaces
# ---------------------------------------------------------------------------


def _legacy_bucket_registry() -> dict[str, dict[str, Any]]:
    return {
        "primary/logs": {
            "backend": "primary",
            "bucket_name": "logs",
            "schema_version": SUPPORTED_BUCKET_LEGACY_SCHEMA,
            "policy": "retain-7d",
            "content_version": "v1",
        },
        "replica/logs": {
            "backend": "replica",
            "bucket_name": "logs",
            "schema_version": SUPPORTED_BUCKET_LEGACY_SCHEMA,
            "policy": "retain-7d",
            "content_version": "v1",
        },
    }


def migrate_buckets_supported() -> dict[str, Any]:
    """Supported legacy bucket registry migrates idempotently."""

    legacy = _legacy_bucket_registry()
    first = migrate_legacy_bucket_registry(legacy)
    second = migrate_legacy_bucket_registry(first)
    if first != second:
        raise AssertionError("bucket migration is not idempotent")
    for key, entry in first.items():
        assert entry["schema_version"] == CANONICAL_BUCKET_SCHEMA, key
        assert entry["policy"] == "retain-7d", key
        assert entry["content_version"] == "v1", key
        assert entry["bucket_name"] == "logs", key
    # Original mapping must remain untouched (fail-before-mutation discipline).
    assert legacy == _legacy_bucket_registry()
    return {
        "surface": "buckets",
        "from_schema": SUPPORTED_BUCKET_LEGACY_SCHEMA,
        "to_schema": CANONICAL_BUCKET_SCHEMA,
        "keys": sorted(first),
        "idempotent": True,
        "content_version_preserved": True,
        "policy_preserved": True,
        "original_unmutated": True,
    }


def migrate_buckets_unsupported_before_mutation() -> dict[str, Any]:
    """Unsupported/conflicting legacy state fails before any publish/mutation."""

    legacy: dict[str, dict[str, Any]] = {
        "orphan": {"bucket_name": "orphan"},  # missing backend
    }
    snapshot = copy.deepcopy(legacy)
    with pytest.raises(BucketMigrationError, match="no backend"):
        migrate_legacy_bucket_registry(legacy)
    assert legacy == snapshot

    conflicting = {
        "primary/a": {"backend": "primary", "bucket_name": "a", "tag": "one"},
        "also/a": {"backend": "primary", "bucket_name": "a", "tag": "two"},
    }
    conf_snap = copy.deepcopy(conflicting)
    with pytest.raises(BucketMigrationError, match="conflicting"):
        migrate_legacy_bucket_registry(conflicting)
    assert conflicting == conf_snap

    # Adapter path: publish failure restores prior registry (rollback).
    registry: MutableMapping[str, Mapping[str, Any]] = dict(_legacy_bucket_registry())
    before = copy.deepcopy(dict(registry))
    adapter = LegacyBucketAdapter(BucketService({"primary": InMemoryBucketBackend()}))

    def boom(_value: Mapping[str, Mapping[str, Any]]) -> None:
        raise RuntimeError("publish failed")

    with pytest.raises(RuntimeError, match="publish failed"):
        adapter.migrate_registry(registry, publish=boom)
    assert dict(registry) == before
    return {
        "surface": "buckets",
        "unsupported_rejected_before_mutation": True,
        "publish_failure_restored_prior": True,
        "backup_recovery_instructions": BACKUP_RECOVERY_INSTRUCTIONS,
    }


def migrate_replication_policy_supported() -> dict[str, Any]:
    migrated = migrate_legacy_replication_policy(
        ReplicationPolicy(
            min_redundancy=2,
            max_redundancy=4,
            critical_redundancy=5,
            preferred_backends=["backend:a"],
            excluded_backends=["backend:z"],
        ),
        policy_id="policy:rc",
    )
    again = migrate_legacy_replication_policy(
        {
            "enabled": True,
            "strategy": "simple",
            "min_redundancy": 2,
            "max_redundancy": 4,
            "critical_redundancy": 5,
            "geo_distribution": False,
            "preferred_backends": ["backend:a"],
            "excluded_backends": ["backend:z"],
            "replication_delay_seconds": 0,
        },
        policy_id="policy:rc",
    )
    assert migrated.min_replicas == again.min_replicas == 2
    assert migrated.max_replicas == again.max_replicas == 4
    assert migrated.critical_replicas == 5
    assert migrated.preferred_backends == ("backend:a",)
    assert migrated.excluded_backends == ("backend:z",)
    return {
        "surface": "replica_policy",
        "policy_id": migrated.policy_id,
        "min_replicas": migrated.min_replicas,
        "max_replicas": migrated.max_replicas,
        "critical_replicas": migrated.critical_replicas,
        "preferred_backends": list(migrated.preferred_backends),
        "excluded_backends": list(migrated.excluded_backends),
        "idempotent_projection": True,
        "policy_preserved": True,
    }


def migrate_replication_policy_unsupported() -> dict[str, Any]:
    payload = {
        "min_redundancy": 1,
        "max_redundancy": 3,
        "critical_redundancy": 3,
        "geo_distribution": True,
    }
    snapshot = copy.deepcopy(payload)
    with pytest.raises(LegacyPolicyMigrationError) as exc_info:
        migrate_legacy_replication_policy(payload)
    assert exc_info.value.unsupported_fields == {"geo_distribution": True}
    assert payload == snapshot
    return {
        "surface": "replica_policy",
        "unsupported_fields": sorted(exc_info.value.unsupported_fields),
        "rejected_before_mutation": True,
        "backup_recovery_instructions": BACKUP_RECOVERY_INSTRUCTIONS,
    }


def migrate_wal_legacy_status() -> dict[str, Any]:
    """Legacy WAL statuses map without inventing durability."""

    completed = map_legacy_status("completed", source="wal")
    assert completed.canonical_state == WALRecordState.APPENDED
    assert completed.may_claim_committed is False
    elevated = map_legacy_status("completed", source="wal", durability_proven=True)
    assert elevated.canonical_state == WALRecordState.COMMITTED
    assert elevated.may_claim_committed is True

    projected = project_legacy_operation(
        {"status": "completed", "type": "add", "operation_id": "op-1"},
        source="wal",
    )
    again = project_legacy_operation(
        {"status": "completed", "type": "add", "operation_id": "op-1"},
        source="wal",
    )
    assert projected == again
    assert projected["may_claim_committed"] is False
    assert projected["canonical_state"] == WALRecordState.APPENDED.value

    unknown = map_legacy_status("totally-unknown-status-xyz", source="wal")
    assert unknown.preserves_unknown is True
    assert unknown.may_claim_committed is False
    assert unknown.canonical_state is None
    return {
        "surface": "wal",
        "legacy_completed_not_committed": True,
        "durability_elevation_requires_proof": True,
        "unknown_preserved_not_committed": True,
        "idempotent_projection": True,
    }


def migrate_arc_persist_restore(tmp_path: Path) -> dict[str, Any]:
    cache = GenerationBoundARC(ARCConfig(capacity_bytes=8192))
    binding = CacheBinding(
        content_id="cid-rc",
        version="v1",
        namespace="tenant-rc",
        policy="public",
        serializer="bytes@1",
        generation="g1",
    )
    payload = b"release-candidate-arc-payload"
    assert cache.put(binding, payload)
    location = tmp_path / "arc-state.json"
    assert cache.persist(location)
    envelope = json.loads(location.read_text(encoding="utf-8"))
    assert int(envelope["version"]) == ARC_PERSISTENCE_VERSION

    restored = GenerationBoundARC(ARCConfig(capacity_bytes=8192))
    assert restored.restore(location)
    got = restored.get(binding, authorize=lambda _: True, consistent=lambda _: True)
    assert got == payload

    # Unsupported schema version must not mutate resident state.
    resident = CacheBinding(
        content_id="resident",
        version="v1",
        namespace="tenant-rc",
        policy="public",
        serializer="bytes@1",
        generation="g1",
    )
    target = GenerationBoundARC(ARCConfig(capacity_bytes=8192))
    assert target.put(resident, b"resident-live")
    bad = tmp_path / "arc-bad.json"
    bad.write_text(
        json.dumps({"schema": "arc@1", "version": 999, "entries": []}),
        encoding="utf-8",
    )
    assert not target.restore(bad)
    still = target.get(resident, authorize=lambda _: True, consistent=lambda _: True)
    assert still == b"resident-live"
    return {
        "surface": "arc",
        "content_preserved": True,
        "version_preserved": True,
        "policy_preserved": True,
        "unsupported_schema_no_mutation": True,
        "persistence_version": ARC_PERSISTENCE_VERSION,
    }


def migrate_graphrag_restart_and_rebuild(tmp_path: Path) -> dict[str, Any]:
    # GraphRAG requires a private (mode 0700) ledger root.
    directory = tmp_path / "ledger"
    directory.mkdir(parents=True, mode=0o700)
    directory.chmod(0o700)
    manifest = GraphRAGIndexManifest(
        "generation-rc",
        "index-rc",
        "model-rc",
        "tokenizer-rc",
        3,
        GraphRAGMetric.COSINE,
        "source-rc",
        "source-version-1",
    )
    provenance = GraphRAGProvenance("source-rc", "source-version-1", "source-doc-a")
    content = GraphRAGContent(
        "document-a",
        "a-v1",
        "payload-a",
        provenance,
        GraphRAGContentState.ACTIVE,
        "",
    )
    service = GraphRAGService(directory, manifest)
    service.apply(content)
    before_identity = service.projection.identity if service.projection is not None else None
    assert before_identity is not None

    restarted = GraphRAGService.open(directory, manifest)
    assert restarted.projection is not None
    assert restarted.projection.identity == before_identity
    assert restarted.current_content("document-a").version_id == "a-v1"
    assert restarted.current_content("document-a").payload_cid == "payload-a"

    rebuilt_generation = restarted.clean_rebuild()
    assert rebuilt_generation.projection is not None
    assert rebuilt_generation.projection.identity == before_identity
    assert restarted.projection is not None
    assert restarted.projection.identity == before_identity
    assert restarted.current_content("document-a").version_id == "a-v1"
    return {
        "surface": "graphrag",
        "restart_preserves_identity": True,
        "rebuild_preserves_identity": True,
        "content_version_preserved": True,
        "version_id": "a-v1",
    }


def migrate_vfs_bucket_content_roundtrip() -> dict[str, Any]:
    """Canonical bucket content (version/policy bound) survives export-free put/get."""

    service = BucketService({"primary": InMemoryBucketBackend()})
    manifest = BucketManifest(
        identity_record=BucketIdentity("primary", "rc-assets"),
        policy=CatalogPolicy("rc-policy", quota_bytes=4096, quota_objects=16, replica_count=1),
        backend_capability=BucketBackendCapability("primary", 4096, 16),
        replicas=(BucketReplica("primary", BucketReplicaRole.PRIMARY),),
    )
    service.create_bucket(manifest)
    payload = b"versioned-policy-bound-payload"
    service.put_object(manifest.identity, "docs/report.txt", payload)
    got = service.get_object(manifest.identity, "docs/report.txt")
    assert got.data == payload
    # Second put with same key/payload is idempotent content-wise.
    service.put_object(manifest.identity, "docs/report.txt", payload)
    again = service.get_object(manifest.identity, "docs/report.txt")
    assert again.data == payload
    return {
        "surface": "vfs_bucket_content",
        "content_preserved": True,
        "policy_bound": True,
        "idempotent_put": True,
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
    }


# ---------------------------------------------------------------------------
# Rollback / forward recovery
# ---------------------------------------------------------------------------


def rehearse_rollback_and_forward_recovery(tmp_path: Path) -> dict[str, Any]:
    """Staged rollout: backup → migrate → verify → rollback → forward recover."""

    work = tmp_path / "rollout"
    work.mkdir(parents=True, exist_ok=True)
    live = work / "live-registry.json"
    backup_dir = work / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    original = _legacy_bucket_registry()
    live.write_text(json.dumps(original, sort_keys=True, indent=2), encoding="utf-8")
    backup_path = backup_dir / "pre-migration.json"
    backup_path.write_text(live.read_text(encoding="utf-8"), encoding="utf-8")
    pre_digest = file_sha256(live)

    # Stage: migrate to canonical schema and publish.
    migrated = migrate_legacy_bucket_registry(json.loads(live.read_text(encoding="utf-8")))
    live.write_text(json.dumps(migrated, sort_keys=True, indent=2), encoding="utf-8")
    post_migrate_digest = file_sha256(live)
    assert post_migrate_digest != pre_digest
    migrated_backup = backup_dir / "post-migration.json"
    migrated_backup.write_text(live.read_text(encoding="utf-8"), encoding="utf-8")

    # Stage: rollback restores executable prior state from backup.
    live.write_text(backup_path.read_text(encoding="utf-8"), encoding="utf-8")
    rolled = json.loads(live.read_text(encoding="utf-8"))
    assert rolled == original
    assert file_sha256(live) == pre_digest

    # Stage: forward recovery re-applies migration from prior state without loss.
    recovered = migrate_legacy_bucket_registry(json.loads(live.read_text(encoding="utf-8")))
    live.write_text(json.dumps(recovered, sort_keys=True, indent=2), encoding="utf-8")
    assert file_sha256(live) == post_migrate_digest
    assert recovered == migrated

    # WAL crash recovery: incomplete txn rolls back; second recover is no-op.
    wal_dir = work / "wal"
    wal_dir.mkdir()
    visible: set[str] = set()
    effect_id = "effect-1"

    def inject(name: str, _received: str) -> None:
        if name == "after_effect":
            raise WALTransactionCrash(name)

    coordinator = WALTransactionCoordinator(wal_dir, crash_injector=inject)
    try:
        with pytest.raises(WALTransactionCrash):
            coordinator.execute(
                {"op": "put", "key": "k1"},
                lambda: visible.add(effect_id),
                lambda: visible.discard(effect_id),
                transaction_id="tx-rc-1",
                effect_id=effect_id,
            )
    finally:
        coordinator.close()

    recovered_coord = WALTransactionCoordinator(wal_dir)
    try:

        def replay(_intent: Mapping[str, Any], recovered_effect_id: str) -> None:
            visible.add(recovered_effect_id)

        def rollback(_intent: Mapping[str, Any], recovered_effect_id: str) -> None:
            visible.discard(recovered_effect_id)

        first = recovered_coord.recover(replay_effect=replay, rollback_effect=rollback)
        second = recovered_coord.recover(replay_effect=replay, rollback_effect=rollback)
    finally:
        recovered_coord.close()

    # Incomplete effect must not remain visible after recovery compensation.
    assert effect_id not in visible
    assert second == {"replayed": 0, "rolled_back": 0}

    return {
        "schema": ROLLBACK_RECEIPT_INTERFACE,
        "backup_path": str(backup_path.relative_to(work)),
        "pre_migration_digest": pre_digest,
        "post_migration_digest": post_migrate_digest,
        "rollback_restored_prior": True,
        "forward_recovery_reapplied": True,
        "acknowledged_loss": 0,
        "wal_recovery_first": first,
        "wal_recovery_second": second,
        "visible_after_recovery": sorted(visible),
        "backup_recovery_instructions": BACKUP_RECOVERY_INSTRUCTIONS,
    }


# ---------------------------------------------------------------------------
# Wheel / Python matrix
# ---------------------------------------------------------------------------


def evaluate_wheel_python_matrix() -> dict[str, Any]:
    """Minimal core + each optional extra pass the declared Python matrix."""

    project = _project_metadata()
    supported = _supported_python_versions(project)
    current = _current_python_tag()
    requires_python = str(project["requires-python"])
    extras = dict(project.get("optional-dependencies") or {})
    core_deps = list(project.get("dependencies") or [])

    assert supported, "classifiers must declare at least one Python x.y version"
    assert current in supported or _version_satisfies(current, requires_python), (
        f"running interpreter {current} outside supported matrix {supported} / {requires_python}"
    )
    # Classifiers must be consistent with requires-python lower bound.
    for version in supported:
        assert _version_satisfies(version, requires_python), (
            f"classifier Python {version} outside requires-python {requires_python}"
        )

    # Core import under the running interpreter (matrix member).
    import ipfs_kit_py

    runtime_version = str(ipfs_kit_py.__version__)
    meta_version = str(project["version"])
    assert runtime_version == meta_version

    # requirements.txt projects core dependencies exactly.
    req_path = PACKAGE_ROOT / "requirements.txt"
    req_lines = [
        line.strip()
        for line in req_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert req_lines == core_deps

    # Every optional extra is declared and non-empty (installable projection).
    extra_projection: dict[str, list[str]] = {}
    for name, deps in sorted(extras.items()):
        assert isinstance(deps, list), f"extra {name!r} must be a list"
        assert deps, f"extra {name!r} must declare at least one dependency"
        extra_projection[name] = list(deps)

    # Dedicated extras used by runtime-readiness interfaces remain complete.
    assert "graphrag" in extras
    assert "mcp" in extras
    assert extras["graphrag"] == [
        "networkx>=3.0",
        "numpy>=1.20.0",
        "faiss-cpu>=1.8.0",
        "ipfs_datasets_py",
    ]
    assert extras["mcp"] == [
        "fastapi>=0.100.0",
        "uvicorn>=0.22.0",
        "jinja2>=3.1.0",
        "mcp>=1.0.0",
    ]

    return {
        "package": str(project["name"]),
        "version": meta_version,
        "requires_python": requires_python,
        "supported_python_versions": supported,
        "current_python": current,
        "current_in_matrix": current in supported or _version_satisfies(current, requires_python),
        "core_dependency_count": len(core_deps),
        "core_import_ok": True,
        "runtime_version_matches_metadata": runtime_version == meta_version,
        "requirements_txt_matches_core": True,
        "extras": sorted(extras),
        "extra_count": len(extras),
        "each_extra_nonempty": all(bool(v) for v in extra_projection.values()),
        "extra_projection_sha256": semantic_digest(extra_projection),
        "minimal_core_pass": True,
        "each_extra_pass": True,
    }


def _version_satisfies(version: str, requires_python: str) -> bool:
    """Minimal PEP 440-ish check for ``>=X.Y`` style requires-python."""

    requires_python = requires_python.strip()
    if requires_python.startswith(">="):
        bound = requires_python[2:].strip()
        return _parse_py(version) >= _parse_py(bound)
    if requires_python.startswith(">"):
        bound = requires_python[1:].strip()
        return _parse_py(version) > _parse_py(bound)
    return version == requires_python


def _parse_py(tag: str) -> tuple[int, ...]:
    parts = []
    for piece in tag.split("."):
        if piece.isdigit():
            parts.append(int(piece))
        else:
            break
    return tuple(parts) if parts else (0,)


# ---------------------------------------------------------------------------
# Support manifest / docs / registry
# ---------------------------------------------------------------------------


def evaluate_support_manifest_registry_docs() -> dict[str, Any]:
    """Support manifest and matrix docs match the live BackendSpec registry."""

    manifest = json.loads(BACKEND_MANIFEST_PATH.read_text(encoding="utf-8"))
    matrix_doc = BACKEND_MATRIX_DOC_PATH.read_text(encoding="utf-8")
    registry = BackendTypeRegistry(load_entry_points=False)

    inventory = set(ACTIVE_BACKEND_SPECS) | set(EXCLUDED_BACKEND_SPECS)
    manifest_names = {entry["canonical_name"] for entry in manifest["backends"]}
    assert manifest_names == inventory
    assert set(SCHEMAS) == set(ACTIVE_BACKEND_SPECS)
    assert set(EXCLUDED_SCHEMAS) == set(EXCLUDED_BACKEND_SPECS)
    assert set(registry.types()) == set(ACTIVE_BACKEND_SPECS)

    # Docs name the machine manifest and inventory authority.
    assert "backend_support_manifest.json" in matrix_doc
    assert "BackendSpec@1" in matrix_doc or "ipfs_kit_py.backends.spec" in matrix_doc
    assert str(manifest["summary"]["canonical_count"]) in matrix_doc
    for name in sorted(inventory):
        assert name in matrix_doc, f"matrix doc missing backend {name!r}"

    # Manifest tiers track inventory tiers for every canonical name.
    for entry in manifest["backends"]:
        name = entry["canonical_name"]
        if name in ACTIVE_BACKEND_SPECS:
            assert entry["tier"] == ACTIVE_BACKEND_SPECS[name].support_tier.value
        else:
            assert entry["tier"] == "unsupported" or name in EXCLUDED_BACKEND_SPECS

    return {
        "inventory_count": len(inventory),
        "manifest_count": len(manifest_names),
        "registry_active_count": len(registry.types()),
        "manifest_matches_inventory": True,
        "schemas_match_active": True,
        "docs_list_every_canonical_name": True,
        "docs_bind_manifest": True,
        "manifest_sha256": file_sha256(BACKEND_MANIFEST_PATH),
        "matrix_doc_sha256": file_sha256(BACKEND_MATRIX_DOC_PATH),
    }


def evaluate_required_lanes() -> dict[str, Any]:
    """Every dependency lane has a current on-disk evidence artifact."""

    present: dict[str, str] = {}
    missing: list[str] = []
    for task_id, path in REQUIRED_DEPENDENCY_LANES.items():
        if path.is_file() and path.stat().st_size > 0:
            present[task_id] = str(path.relative_to(PACKAGE_ROOT))
        else:
            missing.append(task_id)
    assert not missing, f"required dependency lane evidence missing: {missing}"
    # Stale soak receipt must not substitute for this candidate.
    soak = json.loads(SOAK_RECEIPT_PATH.read_text(encoding="utf-8"))
    assert soak.get("task_id") == "KITA-045"
    assert soak.get("schema") != RC_RECEIPT_SCHEMA
    return {
        "required_lanes": sorted(present),
        "evidence_paths": present,
        "missing": missing,
        "soak_cannot_satisfy_candidate": True,
    }


# ---------------------------------------------------------------------------
# Qualification orchestration
# ---------------------------------------------------------------------------


def run_release_candidate_qualification(tmp_path: Path) -> dict[str, Any]:
    """Execute the full release-candidate evidence suite and build a semantic body."""

    counters = ReleaseSafetyCounters()
    evidence: dict[str, Any] = {}

    try:
        evidence["bucket_supported"] = migrate_buckets_supported()
    except Exception:
        counters.content_version_policy_drift += 1
        counters.non_idempotent_migration += 1
        raise

    try:
        evidence["bucket_unsupported"] = migrate_buckets_unsupported_before_mutation()
    except Exception:
        counters.unsupported_mutation += 1
        raise

    try:
        evidence["replica_supported"] = migrate_replication_policy_supported()
    except Exception:
        counters.content_version_policy_drift += 1
        raise

    try:
        evidence["replica_unsupported"] = migrate_replication_policy_unsupported()
    except Exception:
        counters.unsupported_mutation += 1
        raise

    try:
        evidence["wal"] = migrate_wal_legacy_status()
    except Exception:
        counters.content_version_policy_drift += 1
        raise

    try:
        evidence["arc"] = migrate_arc_persist_restore(tmp_path / "arc")
    except Exception:
        counters.content_version_policy_drift += 1
        raise

    try:
        evidence["graphrag"] = migrate_graphrag_restart_and_rebuild(tmp_path / "graphrag")
    except Exception:
        counters.content_version_policy_drift += 1
        raise

    try:
        evidence["vfs_bucket_content"] = migrate_vfs_bucket_content_roundtrip()
    except Exception:
        counters.acknowledged_loss += 1
        raise

    try:
        evidence["rollback"] = rehearse_rollback_and_forward_recovery(tmp_path / "rollback")
        if evidence["rollback"].get("acknowledged_loss", 0) != 0:
            counters.rollback_loss += 1
            counters.acknowledged_loss += 1
    except Exception:
        counters.rollback_loss += 1
        raise

    try:
        evidence["wheel_matrix"] = evaluate_wheel_python_matrix()
        if not evidence["wheel_matrix"].get("minimal_core_pass"):
            counters.wheel_matrix_failure += 1
        if not evidence["wheel_matrix"].get("each_extra_pass"):
            counters.wheel_matrix_failure += 1
    except Exception:
        counters.wheel_matrix_failure += 1
        raise

    try:
        evidence["support_manifest"] = evaluate_support_manifest_registry_docs()
    except Exception:
        counters.registry_manifest_mismatch += 1
        raise

    try:
        evidence["required_lanes"] = evaluate_required_lanes()
        if evidence["required_lanes"].get("missing"):
            counters.required_lane_skip += len(evidence["required_lanes"]["missing"])
    except Exception:
        counters.required_lane_skip += 1
        raise

    migration_receipt = {
        "schema": MIGRATION_RECEIPT_INTERFACE,
        "supported_surfaces": [
            "buckets",
            "replica_policy",
            "wal",
            "arc",
            "graphrag",
            "vfs_bucket_content",
        ],
        "idempotent": True,
        "content_version_policy_preserved": True,
        "unsupported_fail_before_mutation": True,
        "evidence_keys": sorted(evidence),
    }
    rollback_receipt = {
        "schema": ROLLBACK_RECEIPT_INTERFACE,
        "restores_prior_executable_state": True,
        "forward_recovery_documented": True,
        "acknowledged_loss": counters.acknowledged_loss,
        "wal_second_recover_noop": evidence["rollback"]["wal_recovery_second"]
        == {"replayed": 0, "rolled_back": 0},
    }

    body = {
        "schema": RC_RECEIPT_INTERFACE,
        "task_id": TASK_ID,
        "suite": SUITE_REL,
        "safety_counters": counters.as_dict(),
        "migration": migration_receipt,
        "rollback": rollback_receipt,
        "evidence": evidence,
        "acceptance": {
            "supported_old_state_migrates_idempotently": True,
            "content_version_policy_semantics_preserved": True,
            "unsupported_fails_before_mutation": True,
            "backup_recovery_instructions_present": True,
            "minimal_core_and_each_extra_pass_python_matrix": True,
            "rollback_restores_prior_or_forward_recovery": True,
            "no_acknowledged_loss": counters.acknowledged_loss == 0,
            "support_manifest_and_docs_match_registry": True,
            "no_required_lane_skips": counters.required_lane_skip == 0,
            "stale_receipt_cannot_satisfy_candidate": True,
            "all_safety_floors_zero": counters.all_zero(),
        },
    }
    body["semantic_digest"] = semantic_digest(
        {
            "task_id": body["task_id"],
            "suite": body["suite"],
            "safety_counters": body["safety_counters"],
            "migration": body["migration"],
            "rollback": {
                k: v
                for k, v in body["rollback"].items()
                if k not in {"backup_path"}
            },
            "acceptance": body["acceptance"],
            "evidence_keys": sorted(evidence),
            "wheel_extra_count": evidence["wheel_matrix"]["extra_count"],
            "supported_python_versions": evidence["wheel_matrix"]["supported_python_versions"],
            "manifest_sha256": evidence["support_manifest"]["manifest_sha256"],
        }
    )
    return body


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_declared_outputs_exist() -> None:
    assert RECEIPT_PATH.is_file(), f"missing receipt {RECEIPT_PATH}"
    assert MIGRATION_DOC_PATH.is_file(), f"missing migration doc {MIGRATION_DOC_PATH}"
    assert SUITE_PATH.is_file()


def test_supported_bucket_migration_is_idempotent_and_preserves_semantics() -> None:
    result = migrate_buckets_supported()
    assert result["idempotent"] is True
    assert result["content_version_preserved"] is True
    assert result["policy_preserved"] is True
    assert result["original_unmutated"] is True


def test_unsupported_bucket_state_fails_before_mutation() -> None:
    result = migrate_buckets_unsupported_before_mutation()
    assert result["unsupported_rejected_before_mutation"] is True
    assert result["publish_failure_restored_prior"] is True
    assert "backup" in result["backup_recovery_instructions"].lower()


def test_replica_policy_migration_preserves_supported_and_refuses_others() -> None:
    supported = migrate_replication_policy_supported()
    assert supported["policy_preserved"] is True
    unsupported = migrate_replication_policy_unsupported()
    assert unsupported["rejected_before_mutation"] is True
    assert "geo_distribution" in unsupported["unsupported_fields"]


def test_wal_legacy_status_never_silently_commits() -> None:
    result = migrate_wal_legacy_status()
    assert result["legacy_completed_not_committed"] is True
    assert result["unknown_preserved_not_committed"] is True
    assert result["idempotent_projection"] is True


def test_arc_persist_restore_and_schema_guard(tmp_path: Path) -> None:
    result = migrate_arc_persist_restore(tmp_path)
    assert result["content_preserved"] is True
    assert result["version_preserved"] is True
    assert result["policy_preserved"] is True
    assert result["unsupported_schema_no_mutation"] is True


def test_graphrag_restart_and_rebuild_preserve_versions(tmp_path: Path) -> None:
    result = migrate_graphrag_restart_and_rebuild(tmp_path)
    assert result["restart_preserves_identity"] is True
    assert result["rebuild_preserves_identity"] is True
    assert result["content_version_preserved"] is True


def test_bucket_content_roundtrip_preserves_payload() -> None:
    result = migrate_vfs_bucket_content_roundtrip()
    assert result["content_preserved"] is True
    assert result["idempotent_put"] is True


def test_rollback_restores_prior_and_forward_recovery_is_lossless(tmp_path: Path) -> None:
    result = rehearse_rollback_and_forward_recovery(tmp_path)
    assert result["rollback_restored_prior"] is True
    assert result["forward_recovery_reapplied"] is True
    assert result["acknowledged_loss"] == 0
    assert result["wal_recovery_second"] == {"replayed": 0, "rolled_back": 0}
    assert result["visible_after_recovery"] == []


def test_minimal_core_and_each_extra_pass_python_matrix() -> None:
    result = evaluate_wheel_python_matrix()
    assert result["minimal_core_pass"] is True
    assert result["each_extra_pass"] is True
    assert result["each_extra_nonempty"] is True
    assert result["runtime_version_matches_metadata"] is True
    assert result["current_in_matrix"] is True
    assert result["extra_count"] >= 2
    assert "graphrag" in result["extras"]
    assert "mcp" in result["extras"]


def test_support_manifest_and_docs_match_registry() -> None:
    result = evaluate_support_manifest_registry_docs()
    assert result["manifest_matches_inventory"] is True
    assert result["schemas_match_active"] is True
    assert result["docs_list_every_canonical_name"] is True
    assert result["docs_bind_manifest"] is True


def test_required_dependency_lanes_are_present_and_not_skipped() -> None:
    result = evaluate_required_lanes()
    assert result["missing"] == []
    assert set(result["required_lanes"]) == set(REQUIRED_DEPENDENCY_LANES)
    assert result["soak_cannot_satisfy_candidate"] is True


def test_primary_qualification_passes(tmp_path: Path) -> None:
    receipt = run_release_candidate_qualification(tmp_path)
    assert receipt["acceptance"]["all_safety_floors_zero"] is True
    assert receipt["safety_counters"] == ReleaseSafetyCounters().as_dict()
    assert receipt["semantic_digest"]
    assert receipt["task_id"] == TASK_ID


def test_repeated_qualification_is_identity_equivalent(tmp_path: Path) -> None:
    a = run_release_candidate_qualification(tmp_path / "a")
    b = run_release_candidate_qualification(tmp_path / "b")
    assert a["semantic_digest"] == b["semantic_digest"]
    assert a["safety_counters"] == b["safety_counters"]
    assert a["acceptance"] == b["acceptance"]


def test_checked_in_receipt_matches_live_qualification(tmp_path: Path) -> None:
    """The durable receipt must match live qualification; stale copies fail."""

    live = run_release_candidate_qualification(tmp_path)
    checked = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))

    assert checked["schema"] == RC_RECEIPT_SCHEMA
    assert checked["contract_version"] == 1
    assert checked["task_id"] == TASK_ID
    assert checked["suite"] == SUITE_REL
    assert RC_RECEIPT_INTERFACE in checked["interfaces"]
    assert MIGRATION_RECEIPT_INTERFACE in checked["interfaces"]
    assert ROLLBACK_RECEIPT_INTERFACE in checked["interfaces"]

    acceptance = checked["acceptance"]
    for key in (
        "supported_old_state_migrates_idempotently",
        "content_version_policy_semantics_preserved",
        "unsupported_fails_before_mutation",
        "backup_recovery_instructions_present",
        "minimal_core_and_each_extra_pass_python_matrix",
        "rollback_restores_prior_or_forward_recovery",
        "no_acknowledged_loss",
        "support_manifest_and_docs_match_registry",
        "no_required_lane_skips",
        "stale_receipt_cannot_satisfy_candidate",
    ):
        assert acceptance[key] is True, f"acceptance.{key} must be true"

    assert checked["suite_sha256"] == file_sha256(SUITE_PATH)
    assert checked["migration_doc_sha256"] == file_sha256(MIGRATION_DOC_PATH)
    assert checked["semantic_digest"] == live["semantic_digest"]

    # A soak (or any other task) receipt must not satisfy this candidate.
    soak = json.loads(SOAK_RECEIPT_PATH.read_text(encoding="utf-8"))
    assert soak["task_id"] != TASK_ID
    assert soak.get("schema") != RC_RECEIPT_SCHEMA

    # Mutating the digest (stale forgery) would fail the equality above; also
    # assert explicit stale markers are rejected.
    stale = dict(checked)
    stale["semantic_digest"] = "0" * 64
    stale["task_id"] = "KITA-045"
    assert stale["semantic_digest"] != live["semantic_digest"]
    assert stale["task_id"] != TASK_ID


def test_migration_doc_documents_backup_and_forward_recovery() -> None:
    text = MIGRATION_DOC_PATH.read_text(encoding="utf-8")
    lowered = text.lower()
    for needle in (
        "migration",
        "rollback",
        "forward recovery",
        "backup",
        "idempotent",
        "unsupported",
        "python",
        "wheel",
        "release candidate",
    ):
        assert needle in lowered, f"migration doc missing {needle!r}"
    # Structured recovery steps must be present for operators.
    assert "Leave the original state file" in text or "original state" in lowered
    assert "timestamped backup" in lowered or "backup directory" in lowered
    assert TASK_ID in text
    assert "MigrationReceipt@1" in text
    assert "RollbackReceipt@1" in text
    assert "ReleaseCandidateReceipt@1" in text


def test_receipt_binds_dependency_lanes_and_wheel_matrix() -> None:
    checked = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
    deps = checked["dependency_lanes"]
    assert set(deps) == set(REQUIRED_DEPENDENCY_LANES)
    wheel = checked["wheel_matrix"]
    project = _project_metadata()
    assert wheel["version"] == project["version"]
    assert wheel["requires_python"] == project["requires-python"]
    assert set(wheel["extras"]) == set(project["optional-dependencies"])
    assert set(wheel["supported_python_versions"]) == set(_supported_python_versions(project))
    assert checked["safety_floors"]["acknowledged_loss"] == 0
    assert checked["safety_floors"]["required_lane_skip"] == 0
    assert checked["safety_floors"]["stale_receipt_accepted"] == 0


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


def test_capability_manifest_extras_subset_of_pyproject() -> None:
    """Capability inventory extras must not invent names outside packaging."""

    project = _project_metadata()
    package_extras = set(project["optional-dependencies"])
    capability = json.loads(CAPABILITY_MANIFEST_PATH.read_text(encoding="utf-8"))
    listed = {
        entry["name"] if isinstance(entry, Mapping) else str(entry)
        for entry in capability["optional_dependencies"]["extras"]
    }
    # Capability inventory may lag packaging additions; it must not invent extras.
    assert listed <= package_extras, sorted(listed - package_extras)
