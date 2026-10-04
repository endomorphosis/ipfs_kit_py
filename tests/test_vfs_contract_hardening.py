#!/usr/bin/env python3
"""Focused VFS contract tests for explicit resolve behavior and non-silent failures."""

import sys
import time
from pathlib import Path

import pytest


repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from ipfs_kit_py.ipfs_fsspec import (
    VFSCore,
    get_vfs,
    vfs_list_mounts,
    vfs_mount,
    vfs_resolve_path,
    vfs_sync_from_ipfs,
    vfs_sync_to_ipfs,
    vfs_unmount,
    vfs_write,
)



def test_vfs_mount_and_resolve_path_success():
    vfs = get_vfs()

    # Keep test isolated from existing state in shared singleton.
    for mount in list(vfs.mounts.keys()):
        vfs.unmount(mount)

    mount_result = vfs_mount("/ipfs/QmContractCid", "/tmp/vfs-contract-mount", read_only=True)
    assert mount_result["success"] is True
    assert mount_result["mounted"] is True

    resolved = vfs_resolve_path("/tmp/vfs-contract-mount/sub/entry.txt")
    assert resolved["success"] is True
    assert resolved["resolved"] is True
    assert resolved["resolved_path"] == "/ipfs/QmContractCid/sub/entry.txt"


def test_vfs_unmount_nonexistent_is_explicit_failure():
    vfs = get_vfs()
    result = vfs.unmount("/tmp/nonexistent-vfs-mount")
    assert result["success"] is False
    assert result["unmounted"] is False



def test_vfs_mount_invalid_backend_fails_explicitly():
    vfs = get_vfs()
    result = vfs.mount("/tmp/invalid-backend", "unsupported_backend", "/")
    assert result["success"] is False
    assert "unsupported backend" in result["error"]



def test_vfs_observability_snapshot_tracks_operations():
    vfs = get_vfs()
    snapshot = vfs.observability_snapshot()
    assert "metrics" in snapshot
    assert "mount" in snapshot["metrics"]
    assert "resolve_path" in snapshot["metrics"]



def test_vfs_list_mounts_shape():
    result = vfs_list_mounts()
    assert "success" in result
    assert "count" in result
    assert "mounts" in result


def test_vfs_write_triggers_dataset_and_accelerate_hooks():
    class FakeDatasetsManager:
        def __init__(self):
            self.event_log = []

    class FakeAccelerate:
        @staticmethod
        def discover_embedding_models():
            return ["mini-embed-v1", "e5-small"]

    vfs = get_vfs()
    for mount in list(vfs.mounts.keys()):
        vfs.unmount(mount)

    vfs.configure_integrations(
        datasets_manager=FakeDatasetsManager(),
        accelerate_module=FakeAccelerate(),
    )
    vfs.mount("/tmp/vfs-hooks", "memory", "/")

    write_result = vfs_write("/tmp/vfs-hooks/doc.txt", "hello")
    assert write_result["success"] is True
    assert write_result["integration"]["dataset"]["attempted"] is True
    assert write_result["integration"]["dataset"]["success"] is True
    assert write_result["integration"]["dataset"]["adapter"] == "datasets_notifier_v1"
    assert write_result["integration"]["dataset"]["fallback_order"][0] == "record_ipfs_operation"
    assert write_result["integration"]["accelerate"]["attempted"] is True
    assert write_result["integration"]["accelerate"]["success"] is True
    assert write_result["integration"]["accelerate"]["adapter"] == "accelerate_discovery_v1"
    assert write_result["integration"]["accelerate"]["fallback_order"][0] == "discover_embedding_models"
    assert "operation_id" in write_result["integration"]["metadata"]
    assert write_result["integration"]["metadata"]["operation_id"].startswith("op-")
    assert "accelerate_models" in write_result["integration"]["metadata"]

    snapshot = vfs.observability_snapshot()
    assert snapshot["metrics"]["dataset_events"] >= 1
    assert snapshot["metrics"]["accelerate_enrichment"] >= 1


def test_vfs_write_graceful_when_accelerate_unavailable():
    class FakeDatasetsManager:
        def __init__(self):
            self.event_log = []

    vfs = get_vfs()
    for mount in list(vfs.mounts.keys()):
        vfs.unmount(mount)

    vfs.configure_integrations(
        datasets_manager=FakeDatasetsManager(),
        accelerate_module=None,
    )
    vfs.mount("/tmp/vfs-hooks-fallback", "memory", "/")

    write_result = vfs_write("/tmp/vfs-hooks-fallback/doc.txt", "hello")
    assert write_result["success"] is True
    assert write_result["integration"]["dataset"]["attempted"] is True
    assert write_result["integration"]["dataset"]["success"] is True
    assert write_result["integration"]["accelerate"]["attempted"] is False
    assert write_result["integration"]["accelerate"]["reason"] == "ipfs_accelerate_unavailable"
    assert write_result["integration"]["accelerate"]["fallback_order"][1] == "search_models"


def test_vfs_write_accelerate_timeout_is_bounded(monkeypatch):
    class FakeDatasetsManager:
        def __init__(self):
            self.event_log = []

    class FakeAccelerate:
        @staticmethod
        def discover_embedding_models():
            return ["would-have-worked"]

    vfs = get_vfs()
    for mount in list(vfs.mounts.keys()):
        vfs.unmount(mount)

    vfs.configure_integrations(
        datasets_manager=FakeDatasetsManager(),
        accelerate_module=FakeAccelerate(),
    )
    vfs.mount("/tmp/vfs-hooks-timeout", "memory", "/")

    monkeypatch.setattr(vfs, "_call_with_timeout", lambda func, *args: (True, None))

    write_result = vfs_write("/tmp/vfs-hooks-timeout/doc.txt", "hello")
    assert write_result["success"] is True
    assert write_result["integration"]["accelerate"]["attempted"] is True
    assert write_result["integration"]["accelerate"]["success"] is False
    assert write_result["integration"]["accelerate"]["reason"] == "accelerate_timeout"

    snapshot = vfs.observability_snapshot()
    assert snapshot["metrics"]["accelerate_timeouts"] >= 1


def test_vfs_write_respects_accelerate_disabled_mode(monkeypatch):
    class FakeDatasetsManager:
        def __init__(self):
            self.event_log = []

    class FakeAccelerate:
        @staticmethod
        def discover_embedding_models():
            return ["should-not-be-called"]

    monkeypatch.setenv("IPFS_KIT_VFS_ACCELERATE_MODE", "disabled")

    vfs = get_vfs()
    for mount in list(vfs.mounts.keys()):
        vfs.unmount(mount)

    vfs.configure_integrations(
        datasets_manager=FakeDatasetsManager(),
        accelerate_module=FakeAccelerate(),
    )
    original_mode = vfs._vfs_accelerate_mode
    vfs._vfs_accelerate_mode = "disabled"
    vfs.mount("/tmp/vfs-hooks-accelerate-disabled", "memory", "/")

    try:
        write_result = vfs_write("/tmp/vfs-hooks-accelerate-disabled/doc.txt", "hello")
        assert write_result["success"] is True
        assert write_result["integration"]["accelerate"]["attempted"] is False
        assert write_result["integration"]["accelerate"]["reason"] == "vfs_accelerate_disabled"
        assert write_result["integration"]["accelerate"]["adapter"] == "accelerate_discovery_v1"
    finally:
        vfs._vfs_accelerate_mode = original_mode


def test_vfs_write_skips_accelerate_when_datasets_async_enrichment_enabled():
    class FakeDatasetsManager:
        def __init__(self):
            self.event_log = []
            self._async_enrich = True

    class FakeAccelerate:
        @staticmethod
        def discover_embedding_models():
            return ["should-not-run"]

    vfs = get_vfs()
    for mount in list(vfs.mounts.keys()):
        vfs.unmount(mount)

    vfs.configure_integrations(
        datasets_manager=FakeDatasetsManager(),
        accelerate_module=FakeAccelerate(),
    )
    vfs.mount("/tmp/vfs-hooks-ownership", "memory", "/")

    write_result = vfs_write("/tmp/vfs-hooks-ownership/doc.txt", "hello")
    assert write_result["success"] is True
    assert write_result["integration"]["dataset"]["success"] is True
    assert write_result["integration"]["accelerate"]["attempted"] is False
    assert write_result["integration"]["accelerate"]["reason"] == "datasets_async_enrichment_owner"


def test_vfs_copy_and_move_emit_lineage_fields_in_metadata_envelope():
    vfs = get_vfs()
    for mount in list(vfs.mounts.keys()):
        vfs.unmount(mount)

    vfs.mount("/tmp/vfs-lineage", "memory", "/")
    write = vfs_write("/tmp/vfs-lineage/original.txt", "seed")
    assert write["success"] is True

    copied = vfs.copy("/tmp/vfs-lineage/original.txt", "/tmp/vfs-lineage/copied.txt")
    assert copied["success"] is True
    copy_meta = copied["copy_integration"]["metadata"]
    assert "source_operation_id" in copy_meta
    assert "source_cid" in copy_meta
    assert "cid" in copy_meta

    moved = vfs.move("/tmp/vfs-lineage/copied.txt", "/tmp/vfs-lineage/moved.txt")
    assert moved["success"] is True
    move_meta = moved["integration"]["metadata"]
    assert "source_operation_id" in move_meta
    assert "source_cid" in move_meta
    assert "cid" in move_meta


def test_vfs_sync_roundtrip_for_memory_mount():
    vfs = get_vfs()
    original_policy = vfs._sync_conflict_policy
    for mount in list(vfs.mounts.keys()):
        vfs.unmount(mount)

    try:
        vfs._sync_conflict_policy = "overwrite"

        vfs.mount("/tmp/sync-memory", "memory", "/")
        vfs.write("/tmp/sync-memory/doc.txt", "original")

        to_ipfs = vfs_sync_to_ipfs("/tmp/sync-memory")
        assert to_ipfs["success"] is True
        assert to_ipfs["cid"].startswith("cidv1-")

        vfs.write("/tmp/sync-memory/doc.txt", "changed")
        from_ipfs = vfs_sync_from_ipfs("/tmp/sync-memory")
        assert from_ipfs["success"] is True
        assert from_ipfs["cid"] == to_ipfs["cid"]
        assert from_ipfs["restored_count"] >= 1

        read_result = vfs.read("/tmp/sync-memory/doc.txt")
        assert read_result["success"] is True
        assert read_result["content"] == "original"
        assert from_ipfs["policy"] in {"overwrite", "skip", "strict"}
        assert "skipped_count" in from_ipfs
    finally:
        vfs._sync_conflict_policy = original_policy


def test_vfs_sync_from_ipfs_without_prior_sync_is_explicit_failure():
    vfs = get_vfs()
    for mount in list(vfs.mounts.keys()):
        vfs.unmount(mount)

    vfs.mount("/tmp/sync-missing", "memory", "/")
    result = vfs_sync_from_ipfs("/tmp/sync-missing")

    assert result["success"] is False
    assert result["code"] == "missing_sync_state"


def test_vfs_timeout_helper_returns_within_budget():
    vfs = get_vfs()
    original_timeout = vfs._accelerate_timeout_sec
    vfs._accelerate_timeout_sec = 0.05

    try:
        start = time.perf_counter()
        timed_out, value = vfs._call_with_timeout(lambda: (time.sleep(0.25), "done")[1])
        elapsed = time.perf_counter() - start

        assert timed_out is True
        assert value is None
        assert elapsed < 0.20
    finally:
        vfs._accelerate_timeout_sec = original_timeout


def test_vfs_sync_conflict_policy_strict_fails_on_conflict(monkeypatch):
    vfs = get_vfs()
    original_policy = vfs._sync_conflict_policy
    for mount in list(vfs.mounts.keys()):
        vfs.unmount(mount)

    try:
        vfs._sync_conflict_policy = "strict"
        vfs.mount("/tmp/sync-strict", "memory", "/")
        vfs.write("/tmp/sync-strict/doc.txt", "base")
        to_ipfs = vfs_sync_to_ipfs("/tmp/sync-strict")
        assert to_ipfs["success"] is True

        # Create a conflicting local version before restore.
        vfs.write("/tmp/sync-strict/doc.txt", "local-diverged")
        from_ipfs = vfs_sync_from_ipfs("/tmp/sync-strict")
        assert from_ipfs["success"] is False
        assert from_ipfs["code"] == "sync_conflict"
        assert from_ipfs["policy"] == "strict"
    finally:
        vfs._sync_conflict_policy = original_policy


def test_vfs_startup_rejects_unknown_sync_conflict_policy(monkeypatch):
    monkeypatch.setenv("IPFS_KIT_SYNC_CONFLICT_POLICY", "invalid_policy")
    with pytest.raises(ValueError, match="IPFS_KIT_SYNC_CONFLICT_POLICY"):
        VFSCore()


def test_vfs_sync_from_ipfs_strict_rejects_manifest_integrity_mismatch():
    vfs = get_vfs()
    original_policy = vfs._sync_conflict_policy
    for mount in list(vfs.mounts.keys()):
        vfs.unmount(mount)

    try:
        vfs._sync_conflict_policy = "strict"
        vfs.mount("/tmp/sync-strict-integrity", "memory", "/")
        vfs.write("/tmp/sync-strict-integrity/doc.txt", "base")

        to_ipfs = vfs_sync_to_ipfs("/tmp/sync-strict-integrity")
        assert to_ipfs["success"] is True

        # Simulate corrupted/incorrect stored state hash before restore.
        vfs._sync_state_by_path["/tmp/sync-strict-integrity"]["manifest_hash"] = "deadbeef"

        restored = vfs_sync_from_ipfs("/tmp/sync-strict-integrity")
        assert restored["success"] is False
        assert restored["code"] == "sync_integrity_mismatch"
        assert restored["policy"] == "strict"
        assert restored["error"] == "strict_restore_integrity_mismatch"
    finally:
        vfs._sync_conflict_policy = original_policy


def test_vfs_sync_from_ipfs_restores_via_transport_when_snapshot_missing(tmp_path):
    class FakeDatasetsManager:
        def load(self, identifier, target_path=None):
            root = Path(target_path or tmp_path / "restore")
            root.mkdir(parents=True, exist_ok=True)
            restored_file = root / "doc.txt"
            restored_file.write_text("restored-from-transport", encoding="utf-8")
            return {
                "success": True,
                "id": identifier,
                "path": str(root),
            }

    vfs = get_vfs()
    for mount in list(vfs.mounts.keys()):
        vfs.unmount(mount)

    vfs.configure_integrations(datasets_manager=FakeDatasetsManager(), accelerate_module=None)
    vfs.mount("/tmp/sync-transport", "memory", "/")
    vfs.write("/tmp/sync-transport/doc.txt", "base")

    to_ipfs = vfs_sync_to_ipfs("/tmp/sync-transport")
    assert to_ipfs["success"] is True
    cid = to_ipfs["cid"]

    # Simulate restart/host boundary where in-memory snapshot cache is absent.
    vfs._sync_snapshots.pop(cid, None)

    from_ipfs = vfs_sync_from_ipfs("/tmp/sync-transport")
    assert from_ipfs["success"] is True
    assert from_ipfs["cid"] == cid

    read_result = vfs.read("/tmp/sync-transport/doc.txt")
    assert read_result["success"] is True
    assert read_result["content"] == "restored-from-transport"


def test_vfs_sync_snapshot_retention_prunes_to_max_count():
    vfs = get_vfs()
    original_max_count = vfs._sync_snapshot_max_count
    original_max_age_sec = vfs._sync_snapshot_max_age_sec

    try:
        vfs._sync_snapshot_max_count = 1
        vfs._sync_snapshot_max_age_sec = 0

        vfs._sync_snapshots = {
            "cid-old": {
                "cid": "cid-old",
                "synced_at": "2020-01-01T00:00:00+00:00",
                "blobs": {},
            },
            "cid-new": {
                "cid": "cid-new",
                "synced_at": "2030-01-01T00:00:00+00:00",
                "blobs": {},
            },
        }
        vfs._sync_state_by_path = {
            "/tmp/old": {"cid": "cid-old", "manifest_hash": "m1"},
            "/tmp/new": {"cid": "cid-new", "manifest_hash": "m2"},
        }

        vfs._prune_sync_snapshots()

        assert set(vfs._sync_snapshots.keys()) == {"cid-new"}
        assert set(vfs._sync_state_by_path.keys()) == {"/tmp/new"}
    finally:
        vfs._sync_snapshot_max_count = original_max_count
        vfs._sync_snapshot_max_age_sec = original_max_age_sec


def test_vfs_observability_snapshot_includes_sync_retention_state():
    vfs = get_vfs()
    snapshot = vfs.observability_snapshot()

    assert "sync_state" in snapshot
    assert "snapshot_count" in snapshot["sync_state"]
    assert "snapshot_max_count" in snapshot["sync_state"]
