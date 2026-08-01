"""Conformance tests for the legacy replication entry-point migration."""

from __future__ import annotations

import re
import threading
from pathlib import Path

import pytest

from ipfs_kit_py.backend_policies import (
    LegacyPolicyMigrationError,
    LegacyReplicationAdapter,
    LegacyReplicationCleanupBlockedError,
    ReplicationPolicy,
    migrate_legacy_replication_policy,
)
from ipfs_kit_py.core.replication.contracts import (
    BackendCapability,
    BackendInventory,
    ReplicaObservation,
    ReplicaPolicy,
    ReplicaState,
)
from ipfs_kit_py.core.replication.integrity import IntegrityVerifier, ReplicaContent
from ipfs_kit_py.core.replication.reconciler import (
    ReconciliationActionKind,
    ReplicaReconciler,
)
from ipfs_kit_py.fs_journal_replication import MetadataReplicationManager
from ipfs_kit_py.tiered_cache_manager import TieredCacheManager


class MemoryBackend:
    """A backend whose reads make reconciliation evidence independently checkable."""

    def __init__(self, backend_id: str, content: ReplicaContent | None = None) -> None:
        self.backend_id = backend_id
        self.objects: dict[str, ReplicaContent] = {}
        if content is not None:
            self.objects["cid:legacy-object"] = content
        self.writes: list[str] = []
        self.deletes: list[str] = []

    def read(self, content_ref: str) -> ReplicaContent | None:
        return self.objects.get(content_ref)

    def write(
        self, content_ref: str, content: ReplicaContent, *, idempotency_key: str
    ) -> None:
        self.writes.append(content_ref)
        self.objects[content_ref] = content

    def delete(self, content_ref: str, *, idempotency_key: str) -> None:
        self.deletes.append(content_ref)
        self.objects.pop(content_ref, None)


def content() -> tuple[ReplicaContent, str]:
    payload = b"legacy adapter authoritative payload"
    digest = IntegrityVerifier().digest(payload)
    return ReplicaContent(payload, "version:legacy", digest), digest


def adapter(
    *, desired: int = 2, minimum: int = 1, maximum: int = 3
) -> tuple[LegacyReplicationAdapter, dict[str, MemoryBackend]]:
    backends = {
        backend_id: MemoryBackend(backend_id)
        for backend_id in ("backend:a", "backend:b", "backend:c")
    }
    inventory = BackendInventory(
        "snapshot:legacy",
        tuple(
            BackendCapability(backend_id, f"domain:{index}", 4096)
            for index, backend_id in enumerate(backends)
        ),
    )
    policy = ReplicaPolicy("policy:legacy", minimum, desired, maximum, maximum)
    return LegacyReplicationAdapter(ReplicaReconciler(backends), policy, inventory), backends


def test_legacy_policy_migration_preserves_supported_fields_and_refuses_others() -> None:
    migrated = migrate_legacy_replication_policy(
        ReplicationPolicy(
            min_redundancy=1,
            max_redundancy=3,
            critical_redundancy=3,
            preferred_backends=["backend:a"],
            excluded_backends=["backend:c"],
        ),
        policy_id="policy:migrated",
    )

    assert migrated.policy_id == "policy:migrated"
    assert (migrated.min_replicas, migrated.desired_replicas, migrated.max_replicas) == (1, 1, 3)
    assert migrated.preferred_backends == ("backend:a",)
    assert migrated.excluded_backends == ("backend:c",)

    with pytest.raises(LegacyPolicyMigrationError) as exc_info:
        migrate_legacy_replication_policy(
            {"min_redundancy": 1, "max_redundancy": 3, "critical_redundancy": 3, "geo_distribution": True}
        )
    assert exc_info.value.unsupported_fields == {"geo_distribution": True}


def test_queued_replica_and_pending_metadata_do_not_augment_verified_redundancy() -> None:
    bridge, backends = adapter()
    source, digest = content()
    queued = ReplicaObservation(
        "replica:queued",
        "cid:legacy-object",
        "backend:a",
        ReplicaState.QUEUED,
    )

    receipt = bridge.reconcile(
        content_ref="cid:legacy-object",
        content_size_bytes=len(source.payload),
        expected_digest=digest,
        expected_version_id=source.version_id,
        replicas=(queued,),
        source=source,
    )

    assert receipt.converged
    assert len(receipt.verified_backend_ids) == 2
    assert sum(bool(backend.writes) for backend in backends.values()) == 2

    cache_bridge, cache_backends = adapter()
    manager = object.__new__(TieredCacheManager)
    manager.config = {"legacy_replication_adapter": cache_bridge}
    manager.get_metadata = lambda key: {
        "content_digest": digest,
        "content_version_id": source.version_id,
        "pending_replication": {"backend:c": "queued"},
    }
    manager.get = lambda key: source.payload
    metadata_probe = {"pending_replication": "must remain advisory"}
    assert manager._augment_with_replication_info("test_cid_3", metadata_probe) is None
    assert metadata_probe == {"pending_replication": "must remain advisory"}

    result = manager.ensure_replication("cid:legacy-object", target_redundancy=2)
    assert result["success"]
    assert result["verified_redundancy"] == 2
    assert "pending_replication" not in result
    assert sum(bool(backend.writes) for backend in cache_backends.values()) == 2


def test_destructive_cleanup_stays_blocked_until_dynamic_callers_are_migrated() -> None:
    bridge, backends = adapter(desired=1, maximum=3)
    source, digest = content()
    for backend in backends.values():
        backend.objects["cid:legacy-object"] = source

    with pytest.raises(LegacyReplicationCleanupBlockedError) as exc_info:
        bridge.reconcile(
            content_ref="cid:legacy-object",
            content_size_bytes=len(source.payload),
            expected_digest=digest,
            expected_version_id=source.version_id,
            source=source,
        )

    assert any(action.kind is ReconciliationActionKind.REMOVE for action in exc_info.value.receipt.actions)
    assert all("cid:legacy-object" in backend.objects for backend in backends.values())
    assert not any(backend.deletes for backend in backends.values())


def test_legacy_journal_entry_point_uses_receipt_evidence() -> None:
    bridge, _ = adapter()
    manager = object.__new__(MetadataReplicationManager)
    manager.config = {"legacy_replication_adapter": bridge}
    manager.replication_status = {}
    manager._locks = {"status": threading.RLock()}

    result = manager.replicate_journal_entry({"entry_id": "entry:legacy", "kind": "update"})

    assert result["success"]
    assert result["verified_redundancy"] == 2
    assert manager.replication_status["entry:legacy"]["status"] == "complete"


def test_each_legacy_entry_point_has_one_active_implementation() -> None:
    sources = {
        "ensure_replication": TieredCacheManager,
        "replicate_journal_entry": MetadataReplicationManager,
    }
    for method_name, owner in sources.items():
        source = Path(__import__(owner.__module__, fromlist=["_"]).__file__).read_text()
        assert len(re.findall(rf"^    def {method_name}\(", source, flags=re.MULTILINE)) == 1
