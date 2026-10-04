"""Virtual bucket and tiered-storage contract coverage for Iroh."""

from __future__ import annotations

import json
import stat
from pathlib import Path
from typing import Any

import pytest

from ipfs_kit_py.backend_registry import BackendConfigError
from ipfs_kit_py.iroh.bucket_tiering import (
    BindingRole,
    BucketPolicy,
    IrohBucketTieringManager,
    bucket_policy_schema,
    migrate_bucket_policy,
    reconciliation_receipt_schema,
    tier_policy_schema,
    verify_reconciliation_receipt,
)
from ipfs_kit_py.iroh.errors import IrohConflictError, IrohIntegrityError


HASH_A = "a" * 64
HASH_B = "b" * 64
NAMESPACE = "c" * 64


class BackendManagerDouble:
    def __init__(self) -> None:
        self.configs = {
            name: {
                "name": name,
                "type": "iroh" if name.startswith("iroh") else "local",
                "enabled": True,
                "namespace": {"id": NAMESPACE, "access": "read-write"},
            }
            for name in ("iroh_primary", "iroh_replica", "iroh_cache", "local_archive")
        }

    def get_backend_config(self, name: str, *, redact: bool = True) -> dict[str, Any]:
        del redact
        if name not in self.configs:
            raise FileNotFoundError(name)
        return self.configs[name]

    def get_backend_capabilities(self, name: str) -> dict[str, Any]:
        config = self.get_backend_config(name)
        return {"read": True, "write": config["namespace"]["access"] == "read-write"}

    def get_backend_health(self, name: str) -> dict[str, Any]:
        self.get_backend_config(name)
        return {"healthy": True, "storage": {"used_bytes": 10, "capacity_bytes": 10_000}}


@pytest.fixture
def manager(tmp_path: Path) -> IrohBucketTieringManager:
    value = IrohBucketTieringManager(BackendManagerDouble(), tmp_path / "tiering.duckdb")
    yield value
    value.close()


def make_bucket(manager: IrohBucketTieringManager, *, quota: int = 100) -> BucketPolicy:
    return manager.create_bucket(
        "assets",
        primary="iroh_primary",
        replicas=["iroh_replica"],
        cache="iroh_cache",
        archive="local_archive",
        quota_bytes=quota,
    )


def test_schema_resources_and_role_complete_policy(manager: IrohBucketTieringManager) -> None:
    assert bucket_policy_schema()["properties"]["bindings"]["items"]["$ref"] == "#/$defs/binding"
    assert tier_policy_schema()["properties"]["replication_factor"]["minimum"] == 1
    assert reconciliation_receipt_schema()["properties"]["kind"]["const"].endswith("reconciliation-receipt")

    policy = make_bucket(manager)
    assert policy.tier_policy.replication_factor == 2
    assert {item.role for item in policy.bindings} == set(BindingRole)
    assert manager.list_buckets() == ("assets",)


def test_iroh_is_valid_for_primary_replica_cache_and_archive_bindings(
    manager: IrohBucketTieringManager,
) -> None:
    policy = manager.create_bucket(
        {
            "schema_version": 1,
            "bucket": "all_iroh",
            "quota_bytes": None,
            "bindings": [
                {"backend": "iroh_primary", "role": "primary"},
                {"backend": "iroh_replica", "role": "replica"},
                {"backend": "iroh_cache", "role": "cache"},
                {"backend": "local_archive", "role": "archive"},
            ],
            "tier_policy": {"schema_version": 1, "replication_factor": 2},
        }
    )
    assert policy.bucket == "all_iroh"
    assert [item.backend for item in manager.select_placement("all_iroh", 1)] == [
        "iroh_primary", "iroh_replica", "iroh_cache", "local_archive"
    ]


def test_duplicate_content_is_counted_once_and_not_written_twice(
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, str]] = []

    def place(action: dict[str, Any], content: dict[str, Any]) -> bool:
        calls.append((action["backend"], content["iroh_hash"]))
        return True

    manager = IrohBucketTieringManager(
        BackendManagerDouble(), tmp_path / "dedupe.duckdb", placement_handler=place
    )
    make_bucket(manager)
    first = manager.place_content("assets", HASH_A, 40)
    second = manager.place_content("assets", HASH_A, 40)

    assert first.status == "converged"
    assert len(calls) == 4
    assert second.duplicate_objects == 1
    assert second.duplicate_bytes == 40
    assert {item.action for item in second.actions} == {"noop"}
    assert manager.logical_usage("assets") == 40
    assert len(calls) == 4
    manager.close()


def test_duplicate_iroh_blob_across_buckets_uses_backend_capacity_once(tmp_path: Path) -> None:
    calls: list[str] = []

    def place(action: dict[str, Any], _content: dict[str, Any]) -> bool:
        calls.append(action["backend"])
        return True

    manager = IrohBucketTieringManager(
        BackendManagerDouble(), tmp_path / "cross-bucket.duckdb", placement_handler=place
    )
    make_bucket(manager)
    manager.create_bucket(
        "mirrored", primary="iroh_primary", replicas=["iroh_replica"],
        cache="iroh_cache", archive="local_archive", quota_bytes=100,
    )
    manager.place_content("assets", HASH_A, 40)
    second = manager.place_content("mirrored", HASH_A, 40)

    assert calls == ["iroh_primary", "iroh_replica", "iroh_cache", "local_archive"]
    assert second.duplicate_objects == 1
    assert {item.reason for item in second.actions} == {"content_already_on_backend"}
    assert manager.logical_usage("assets") == manager.logical_usage("mirrored") == 40
    assert {item["placement_bytes"] for item in manager.capacity_report()["backends"]} == {40}
    manager.close()


def test_quota_rejection_is_atomic_and_has_a_durable_receipt(
    manager: IrohBucketTieringManager,
) -> None:
    make_bucket(manager, quota=50)
    manager.place_content("assets", HASH_A, 40)

    with pytest.raises(IrohConflictError) as caught:
        manager.place_content("assets", HASH_B, 20)

    assert caught.value.metadata["reason"] == "bucket_quota_exceeded"
    receipt = manager.get_receipt(caught.value.metadata["receipt_id"])
    assert receipt.status == "rejected"
    assert receipt.logical_bytes_before == receipt.logical_bytes_after == 40
    assert receipt.actions[0].reason == "bucket_quota_exceeded"
    assert manager.logical_usage("assets") == 40


def test_capacity_reporting_and_backend_capacity_rejection(tmp_path: Path) -> None:
    capacity = {
        "iroh_primary": {"healthy": True, "used_bytes": 90, "capacity_bytes": 100},
        "iroh_replica": {"healthy": True, "used_bytes": 0, "capacity_bytes": 100},
        "iroh_cache": {"healthy": True, "used_bytes": 0, "capacity_bytes": 100},
        "local_archive": {"healthy": True, "used_bytes": 0, "capacity_bytes": 100},
    }
    manager = IrohBucketTieringManager(
        BackendManagerDouble(), tmp_path / "capacity.duckdb", capacity_provider=capacity
    )
    make_bucket(manager)
    report = manager.capacity_report("assets")
    assert report["backends"][0]["available_bytes"] is not None
    with pytest.raises(IrohConflictError, match="placement was rejected"):
        manager.place_content("assets", HASH_A, 11)
    assert manager.last_receipt is not None
    assert any(item.reason == "backend_capacity_exceeded" for item in manager.last_receipt.actions)
    manager.close()


def test_legacy_policy_migration_and_reconciliation_receipt(
    manager: IrohBucketTieringManager,
) -> None:
    legacy = {
        "name": "assets",
        "backend": "iroh_primary",
        "replication_targets": ["iroh_replica"],
        "cache_backend": "iroh_cache",
        "archive_backend": "local_archive",
        "max_size": 1_000,
        "cache_policy": "memory",
        "retention_days": 7,
    }
    migrated = migrate_bucket_policy(legacy)
    assert migrated["schema_version"] == 1
    assert migrated["tier_policy"]["replication_factor"] == 2
    assert migrated["tier_policy"]["archive_after_seconds"] == 7 * 86400
    policy = manager.create_bucket(legacy)
    manager.place_content("assets", HASH_A, 10)

    changed = dict(legacy)
    changed["max_size"] = 2_000
    receipt = manager.update_policy("assets", changed)
    assert receipt.operation == "policy_migration"
    assert receipt.status == "converged"
    assert receipt.policy_digest == manager.get_policy("assets").policy_digest
    assert manager.get_policy("assets").quota_bytes == 2_000
    assert all(item.action == "noop" for item in receipt.actions)
    assert policy.bucket == "assets"


def test_receipts_are_owner_only_tamper_evident_and_restart_safe(
    tmp_path: Path,
) -> None:
    state = tmp_path / "persistent.duckdb"
    manager = IrohBucketTieringManager(BackendManagerDouble(), state)
    make_bucket(manager)
    receipt = manager.place_content("assets", HASH_A, 5)
    destination = receipt.write(tmp_path / "receipts" / "placement.json")
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    assert verify_reconciliation_receipt(destination) == receipt

    damaged = json.loads(destination.read_text())
    damaged["logical_bytes_after"] = 6
    with pytest.raises(IrohIntegrityError, match="digest"):
        verify_reconciliation_receipt(damaged)
    manager.close()

    restarted = IrohBucketTieringManager(BackendManagerDouble(), state)
    assert restarted.get_policy("assets").policy_digest == receipt.policy_digest
    assert restarted.get_receipt(receipt.receipt_id) == receipt
    assert restarted.logical_usage("assets") == 5
    restarted.close()


def test_invalid_or_read_only_bindings_fail_before_persistence(
    tmp_path: Path,
) -> None:
    backends = BackendManagerDouble()
    backends.configs["iroh_primary"]["namespace"]["access"] = "read-only"
    manager = IrohBucketTieringManager(backends, tmp_path / "invalid.duckdb")
    with pytest.raises(BackendConfigError, match="read-only"):
        manager.create_bucket("assets", primary="iroh_primary")
    assert manager.list_buckets() == ()
    manager.close()
