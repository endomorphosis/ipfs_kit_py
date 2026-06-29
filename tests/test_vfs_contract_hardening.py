#!/usr/bin/env python3
"""Focused VFS contract tests for explicit resolve behavior and non-silent failures."""

import sys
from pathlib import Path


repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from ipfs_kit_py.ipfs_fsspec import (
    get_vfs,
    vfs_list_mounts,
    vfs_mount,
    vfs_resolve_path,
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
    assert write_result["integration"]["dataset"]["fallback_order"][0] == "record_ipfs_operation"
    assert write_result["integration"]["accelerate"]["attempted"] is True
    assert write_result["integration"]["accelerate"]["success"] is True
    assert write_result["integration"]["accelerate"]["fallback_order"][0] == "discover_embedding_models"
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
