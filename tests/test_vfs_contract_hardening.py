#!/usr/bin/env python3
"""Focused VFS contract tests for explicit resolve behavior and non-silent failures."""

import sys
from pathlib import Path


repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from ipfs_kit_py.ipfs_fsspec import get_vfs, vfs_list_mounts, vfs_mount, vfs_resolve_path, vfs_unmount


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
