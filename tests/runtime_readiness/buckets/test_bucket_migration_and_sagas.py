"""Regression coverage for bucket migration, transfer, and placement sagas."""

from __future__ import annotations

import json

import pytest

from ipfs_kit_py.core.buckets.adapters import LegacyBucketAdapter, migrate_legacy_bucket_registry
from ipfs_kit_py.core.buckets.contracts import (
    BackendCapability,
    BucketIdentity,
    BucketManifest,
    BucketPolicy as CatalogPolicy,
    BucketReplica,
    BucketReplicaRole,
)
from ipfs_kit_py.core.buckets.service import BucketService, InMemoryBucketBackend
from ipfs_kit_py.core.buckets.transfer import TransferValidationError, export_bucket, import_bucket
from ipfs_kit_py.iroh.bucket_tiering import IrohBucketTieringManager


HASH = "a" * 64


def _manifest(name: str) -> BucketManifest:
    return BucketManifest(
        identity_record=BucketIdentity("primary", name),
        policy=CatalogPolicy(f"{name}policy", quota_bytes=1024, quota_objects=100, replica_count=1),
        backend_capability=BackendCapability("primary", 1024, 100),
        replicas=(BucketReplica("primary", BucketReplicaRole.PRIMARY),),
    )


def test_legacy_registry_migration_is_scoped_idempotent_and_rolls_back() -> None:
    legacy = {
        "primary/logs": {"backend": "primary", "bucket_name": "logs"},
        "replica/logs": {"backend": "replica", "bucket_name": "logs"},
    }
    migrated = migrate_legacy_bucket_registry(legacy)
    assert set(migrated) == {"primary/logs", "replica/logs"}
    assert migrate_legacy_bucket_registry(migrated) == migrated

    registry = dict(legacy)
    adapter = LegacyBucketAdapter(BucketService({"primary": InMemoryBucketBackend()}))
    with pytest.raises(RuntimeError, match="publish"):
        adapter.migrate_registry(registry, publish=lambda _value: (_ for _ in ()).throw(RuntimeError("publish failed")))
    assert registry == legacy


def test_export_binds_content_and_import_validates_before_atomic_publish() -> None:
    source = BucketService({"primary": InMemoryBucketBackend()})
    manifest = _manifest("assets")
    source.create_bucket(manifest)
    source.put_object(manifest.identity, "report.txt", b"immutable payload")
    exported = export_bucket(source, manifest.identity)

    destination = BucketService({"primary": InMemoryBucketBackend()})
    import_bucket(destination, exported.to_bytes(), create_if_missing=True)
    assert destination.get_object(manifest.identity, "report.txt").data == b"immutable payload"

    invalid = json.loads(exported.to_bytes())
    invalid["snapshot"]["objects"][0]["sha256"] = "0" * 64
    # Keep the outer snapshot digest syntactically valid so validation reaches
    # the content manifest rather than publication.
    snapshot = invalid["snapshot"]
    digest_source = dict(snapshot)
    digest_source.pop("snapshot_digest")
    import hashlib

    snapshot["snapshot_digest"] = hashlib.sha256(
        json.dumps(digest_source, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    empty_target = BucketService({"primary": InMemoryBucketBackend()})
    with pytest.raises(TransferValidationError):
        import_bucket(empty_target, invalid, create_if_missing=True)
    assert empty_target.catalog.snapshot().entries == ()


class _BackendManager:
    def __init__(self) -> None:
        self.names = ("iroh_primary", "iroh_replica", "iroh_cache")

    def get_backend_config(self, name: str, *, redact: bool = True) -> dict[str, object]:
        del redact
        if name not in self.names:
            raise FileNotFoundError(name)
        return {"name": name, "type": "iroh", "enabled": True, "namespace": {"access": "read-write"}}

    def get_backend_capabilities(self, name: str) -> dict[str, bool]:
        self.get_backend_config(name)
        return {"read": True, "write": True}

    def get_backend_health(self, name: str) -> dict[str, object]:
        self.get_backend_config(name)
        return {"healthy": True, "storage": {"used_bytes": 0, "capacity_bytes": 10_000}}


def test_failed_policy_reconciliation_compensates_and_restores_prior_policy(tmp_path) -> None:
    calls: list[tuple[str, str]] = []

    def handler(action: dict[str, object], _content: dict[str, object]) -> bool:
        calls.append((str(action["action"]), str(action["backend"])))
        return action["backend"] != "iroh_cache"

    manager = IrohBucketTieringManager(_BackendManager(), tmp_path / "tiering.duckdb", placement_handler=handler)
    try:
        old = manager.create_bucket("assets", primary="iroh_primary", quota_bytes=100)
        manager.place_content("assets", HASH, 10)
        candidate = {
            "schema_version": 1,
            "bucket": "assets",
            "quota_bytes": 100,
            "bindings": [
                {"backend": "iroh_primary", "role": "primary"},
                {"backend": "iroh_replica", "role": "replica"},
                {"backend": "iroh_cache", "role": "cache"},
            ],
            "tier_policy": {"schema_version": 1, "replication_factor": 2},
        }
        receipt = manager.update_policy("assets", candidate)
        assert receipt.status in {"rejected", "recovery_required"}
        assert manager.get_policy("assets") == old
        assert ("place", "iroh_replica") in calls
        assert ("remove", "iroh_replica") in calls
    finally:
        manager.close()
