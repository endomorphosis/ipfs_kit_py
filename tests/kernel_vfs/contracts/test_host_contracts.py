"""KVFS-101: HostFilesystemAdapter callback, error, and lifecycle contracts.

Acceptance coverage:

* finite records for callback inputs/results;
* exact errno projection (Linux/Windows numbers);
* open flags, metadata, and generation-tagged handles;
* durability modes and cache consistency modes;
* mount lifecycle (init → recover → ready → drain → destroy);
* cancellation / deadline envelopes;
* Linux/Windows platform differences; and
* explicit ENOSYS/EOPNOTSUPP without false success.

Conflict policy: inert versioned contract and tests only — no fusepy import
and no CanonicalVFSService mutation.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

from ipfs_kit_py.core.vfs import host_contracts as hc

# test file: .../tests/kernel_vfs/contracts/test_host_contracts.py
PACKAGE_ROOT = Path(__file__).resolve().parents[3]
HOST_CONTRACTS_PATH = (
    PACKAGE_ROOT / "ipfs_kit_py" / "core" / "vfs" / "host_contracts.py"
)


# ---------------------------------------------------------------------------
# Artifact / import inertness
# ---------------------------------------------------------------------------


def test_declared_host_contracts_module_exists() -> None:
    assert HOST_CONTRACTS_PATH.is_file(), f"missing {HOST_CONTRACTS_PATH}"
    assert HOST_CONTRACTS_PATH.stat().st_size > 0


def test_module_is_inert_no_fusepy_dependency() -> None:
    # Re-import to ensure the module loads without native FUSE bindings.
    import ast

    mod = importlib.reload(hc)
    assert mod.CONTRACT_VERSION == 1
    assert mod.HostFilesystemAdapter_V1.endswith("@1")
    hc.assert_no_fusepy_import()
    source = HOST_CONTRACTS_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    banned = frozenset({"fuse", "fusepy"})
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".", 1)[0] not in banned
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module:
                assert module.split(".", 1)[0] not in banned
    # Must not pull a native FUSE binding as a hard dependency of this module.
    assert "fuse" not in getattr(mod, "__dict__", {})
    assert "fusepy" not in getattr(mod, "__dict__", {})


def test_schema_aliases_and_versions() -> None:
    assert hc.SCHEMA_VERSION == "1.0.0"
    assert hc.HOST_FILESYSTEM_ADAPTER_SCHEMA == hc.HostFilesystemAdapter_V1
    assert hc.HOST_CALLBACK_SCHEMA == hc.HostCallback_V1
    assert hc.HOST_CALLBACK_RESULT_SCHEMA == hc.HostCallbackResult_V1
    assert hc.HOST_HANDLE_SCHEMA == hc.HostHandle_V1
    assert hc.HOST_MOUNT_LIFECYCLE_SCHEMA == hc.HostMountLifecycle_V1
    for schema in (
        hc.HOST_FILESYSTEM_ADAPTER_SCHEMA,
        hc.HOST_CALLBACK_SCHEMA,
        hc.HOST_CALLBACK_RESULT_SCHEMA,
        hc.HOST_HANDLE_SCHEMA,
        hc.HOST_METADATA_SCHEMA,
        hc.HOST_MOUNT_LIFECYCLE_SCHEMA,
        hc.HOST_ERROR_SCHEMA,
        hc.HOST_DEADLINE_SCHEMA,
        hc.HOST_PLATFORM_DIFF_SCHEMA,
    ):
        assert schema.startswith("ipfs_kit_py/core/vfs/host_contracts/")
        assert schema.endswith("@1")


# ---------------------------------------------------------------------------
# Callback catalogue — required vs explicit-unsupported
# ---------------------------------------------------------------------------


def test_required_supported_callbacks_match_plan_minimum() -> None:
    expected = {
        "getattr",
        "readdir",
        "access",
        "statfs",
        "utimens",
        "open",
        "create",
        "read",
        "write",
        "truncate",
        "flush",
        "fsync",
        "release",
        "mkdir",
        "rmdir",
        "unlink",
        "rename",
        "init",
        "destroy",
    }
    actual = {k.value for k in hc.REQUIRED_SUPPORTED_CALLBACKS}
    assert actual == expected
    for name in expected:
        assert hc.callback_disposition(name) is hc.CallbackDisposition.REQUIRED_SUPPORTED


def test_explicit_unsupported_callbacks_cover_plan_set() -> None:
    expected = {
        "readlink",
        "symlink",
        "link",
        "mknod",
        "chmod",
        "chown",
        "getxattr",
        "setxattr",
        "listxattr",
        "removexattr",
        "fallocate",
        "flock",
        "ioctl",
        "poll",
    }
    actual = {k.value for k in hc.EXPLICIT_UNSUPPORTED_CALLBACKS}
    assert actual == expected
    for name in expected:
        assert (
            hc.callback_disposition(name)
            is hc.CallbackDisposition.EXPLICIT_UNSUPPORTED
        )


def test_required_and_unsupported_are_disjoint_and_cover_closed_set() -> None:
    required = hc.REQUIRED_SUPPORTED_CALLBACKS
    unsupported = hc.EXPLICIT_UNSUPPORTED_CALLBACKS
    assert required.isdisjoint(unsupported)
    closed = required | unsupported
    assert closed == set(hc.HostCallbackKind)


def test_unknown_callback_is_forbidden() -> None:
    with pytest.raises(hc.HostUnknownCallbackError):
        hc.parse_callback_kind("not_a_real_callback")
    with pytest.raises(hc.HostUnknownCallbackError):
        hc.HostCallbackRequest(kind="mystery_op")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Exact errno — no false success
# ---------------------------------------------------------------------------


def test_linux_and_windows_errno_numbers_are_exact() -> None:
    assert hc.errno_number(hc.HostErrno.OK, hc.HostPlatform.LINUX) == 0
    assert hc.errno_number(hc.HostErrno.ENOENT, hc.HostPlatform.LINUX) == 2
    assert hc.errno_number(hc.HostErrno.ENOSYS, hc.HostPlatform.LINUX) == 38
    assert hc.errno_number(hc.HostErrno.EOPNOTSUPP, hc.HostPlatform.LINUX) == 95
    assert hc.errno_number(hc.HostErrno.ECANCELED, hc.HostPlatform.LINUX) == 125
    assert hc.errno_number(hc.HostErrno.ETIMEDOUT, hc.HostPlatform.LINUX) == 110
    # Windows table shares POSIX names with documented numbers.
    assert hc.errno_number(hc.HostErrno.ENOSYS, hc.HostPlatform.WINDOWS) == 38
    assert hc.errno_number(hc.HostErrno.EOPNOTSUPP, hc.HostPlatform.WINDOWS) == 95
    assert set(hc.LINUX_ERRNO_NUMBERS) == set(hc.HostErrno)
    assert set(hc.WINDOWS_ERRNO_NUMBERS) == set(hc.HostErrno)


def test_success_with_nonzero_errno_is_false_success() -> None:
    with pytest.raises(hc.HostFalseSuccessError):
        hc.HostCallbackResult(
            kind=hc.HostCallbackKind.GETATTR,
            success=True,
            errno=hc.HostErrno.ENOENT,
        )


def test_success_with_error_payload_is_false_success() -> None:
    with pytest.raises(hc.HostFalseSuccessError):
        hc.HostCallbackResult(
            kind=hc.HostCallbackKind.GETATTR,
            success=True,
            errno=hc.HostErrno.OK,
            error=hc.HostError(errno=hc.HostErrno.EIO, message="nope"),
        )


def test_mutating_success_requires_observed_effect() -> None:
    with pytest.raises(hc.HostFalseSuccessError):
        hc.HostCallbackResult(
            kind=hc.HostCallbackKind.WRITE,
            success=True,
            errno=hc.HostErrno.OK,
            observed_effect=False,
            bytes_transferred=4,
        )
    ok = hc.HostCallbackResult.make_success(
        hc.HostCallbackKind.WRITE,
        bytes_transferred=4,
        observed_effect=True,
    )
    assert ok.success is True
    assert ok.errno is hc.HostErrno.OK
    assert ok.observed_effect is True


def test_failure_requires_nonzero_errno_and_error() -> None:
    with pytest.raises(hc.HostContractError):
        hc.HostCallbackResult(
            kind=hc.HostCallbackKind.GETATTR,
            success=False,
            errno=hc.HostErrno.OK,
        )
    with pytest.raises(hc.HostContractError):
        hc.HostCallbackResult(
            kind=hc.HostCallbackKind.GETATTR,
            success=False,
            errno=hc.HostErrno.ENOENT,
            error=None,
        )
    failure = hc.HostCallbackResult.make_failure(
        hc.HostCallbackKind.GETATTR,
        hc.HostErrno.ENOENT,
        message="missing",
    )
    assert failure.success is False
    assert failure.errno is hc.HostErrno.ENOENT
    assert failure.error is not None
    assert failure.error.errno_number == 2
    assert failure.errno_number == 2


def test_explicit_unsupported_must_not_succeed() -> None:
    for kind in hc.EXPLICIT_UNSUPPORTED_CALLBACKS:
        with pytest.raises(hc.HostFalseSuccessError):
            hc.HostCallbackResult(
                kind=kind,
                success=True,
                errno=hc.HostErrno.OK,
                observed_effect=kind in hc.MUTATING_CALLBACKS,
            )


def test_explicit_unsupported_returns_enosys_or_eopnotsupp() -> None:
    for kind in hc.EXPLICIT_UNSUPPORTED_CALLBACKS:
        result = hc.HostCallbackResult.make_unsupported(kind)
        assert result.success is False
        assert result.errno in (hc.HostErrno.ENOSYS, hc.HostErrno.EOPNOTSUPP)
        assert result.error is not None
        assert result.error.errno is result.errno
        assert result.observed_effect is False
        # Wrong errno for unsupported is rejected.
        with pytest.raises(hc.HostContractError):
            hc.HostCallbackResult(
                kind=kind,
                success=False,
                errno=hc.HostErrno.ENOENT,
                error=hc.HostError(errno=hc.HostErrno.ENOENT, message="wrong"),
            )


def test_default_unsupported_errno_policy() -> None:
    assert hc.default_unsupported_errno(hc.HostCallbackKind.SYMLINK) is hc.HostErrno.ENOSYS
    assert (
        hc.default_unsupported_errno(hc.HostCallbackKind.GETXATTR)
        is hc.HostErrno.EOPNOTSUPP
    )
    forced = hc.HostCallbackResult.make_unsupported(
        hc.HostCallbackKind.SYMLINK,
        policy=hc.UnsupportedErrnoPolicy.EOPNOTSUPP,
    )
    assert forced.errno is hc.HostErrno.EOPNOTSUPP


def test_fsync_success_cannot_claim_only_buffered_durability() -> None:
    with pytest.raises(hc.HostFalseSuccessError):
        hc.HostCallbackResult.make_success(
            hc.HostCallbackKind.FSYNC,
            durability_mode=hc.DurabilityMode.BUFFERED,
            observed_effect=False,
        )
    ok = hc.HostCallbackResult.make_success(
        hc.HostCallbackKind.FSYNC,
        durability_mode=hc.DurabilityMode.WAL_AND_BACKEND,
        observed_effect=False,
    )
    assert ok.durability_mode is hc.DurabilityMode.WAL_AND_BACKEND


# ---------------------------------------------------------------------------
# Flags, metadata, handles
# ---------------------------------------------------------------------------


def test_open_flags_are_closed_and_deduplicated() -> None:
    handle = hc.HostHandle(
        handle_id=1,
        inode=42,
        generation=7,
        flags=(
            hc.OpenFlag.O_RDWR,
            hc.OpenFlag.O_CREAT,
            hc.OpenFlag.O_CREAT,
            hc.OpenFlag.O_EXCL,
            "O_TRUNC",
        ),
        path_at_open="dir/file",
        mount_id="mount-1",
        lease_id="lease-1",
    )
    assert handle.flags == (
        hc.OpenFlag.O_RDWR,
        hc.OpenFlag.O_CREAT,
        hc.OpenFlag.O_EXCL,
        hc.OpenFlag.O_TRUNC,
    )
    record = handle.to_record()
    assert record["schema"] == hc.HOST_HANDLE_SCHEMA
    restored = hc.HostHandle.from_dict(record)
    assert restored == handle


def test_metadata_record_round_trip() -> None:
    meta = hc.HostMetadata(
        inode=10,
        kind=hc.HostEntryKind.FILE,
        size=4096,
        mode=0o644,
        nlink=1,
        uid=1000,
        gid=1000,
        atime_ns=1,
        mtime_ns=2,
        ctime_ns=3,
        generation=5,
        display_name="readme.txt",
    )
    restored = hc.HostMetadata.from_dict(meta.to_record())
    assert restored == meta
    assert restored.kind is hc.HostEntryKind.FILE


def test_handle_survives_rename_unlink_semantics_fields() -> None:
    """Contract: handles identify open instances independent of path."""

    handle = hc.HostHandle(
        handle_id=99,
        inode=1001,
        generation=3,
        flags=(hc.OpenFlag.O_RDWR,),
        path_at_open="old/name",
        released=False,
    )
    # Path at open is historical; rename does not clear handle identity.
    assert handle.handle_id == 99
    assert handle.inode == 1001
    assert handle.path_at_open == "old/name"
    released = hc.HostHandle(
        handle_id=handle.handle_id,
        inode=handle.inode,
        generation=handle.generation,
        flags=handle.flags,
        path_at_open=handle.path_at_open,
        released=True,
    )
    # Idempotent release: already-released handle may still report success.
    first = hc.HostCallbackResult.make_success(
        hc.HostCallbackKind.RELEASE,
        handle=released,
        observed_effect=False,
    )
    second = hc.HostCallbackResult.make_success(
        hc.HostCallbackKind.RELEASE,
        handle=released,
        observed_effect=False,
    )
    assert first.success and second.success


def test_callback_request_covers_inputs() -> None:
    handle = hc.HostHandle(
        handle_id=1,
        inode=2,
        generation=1,
        flags=(hc.OpenFlag.O_RDWR, hc.OpenFlag.O_APPEND),
    )
    req = hc.HostCallbackRequest(
        kind=hc.HostCallbackKind.WRITE,
        path="data.bin",
        handle=handle,
        flags=(hc.OpenFlag.O_RDWR, hc.OpenFlag.O_APPEND),
        offset=100,
        size=32,
        mount_id="m1",
        request_id="req-1",
        platform=hc.HostPlatform.LINUX,
        durability_mode=hc.DurabilityMode.WAL_FILE_SYNC,
        cache_consistency=hc.CacheConsistencyMode.READ_OWN_WRITES,
        deadline=hc.HostDeadline(deadline_ms=15_000),
        datasync=False,
    )
    assert req.disposition is hc.CallbackDisposition.REQUIRED_SUPPORTED
    record = req.to_record()
    assert record["kind"] == "write"
    assert record["offset"] == 100
    assert record["durability_mode"] == "wal_file_sync"
    assert record["cache_consistency"] == "read_own_writes"
    restored = hc.HostCallbackRequest.from_dict(record)
    assert restored.kind is hc.HostCallbackKind.WRITE
    assert restored.handle is not None
    assert restored.handle.handle_id == 1
    assert restored.deadline.deadline_ms == 15_000


def test_all_required_callbacks_accept_request_and_success_or_lifecycle() -> None:
    for kind in sorted(hc.REQUIRED_SUPPORTED_CALLBACKS, key=lambda k: k.value):
        req = hc.HostCallbackRequest(kind=kind, path="x" if kind not in (
            hc.HostCallbackKind.INIT,
            hc.HostCallbackKind.DESTROY,
            hc.HostCallbackKind.STATFS,
        ) else "")
        assert req.kind is kind
        if kind in hc.MUTATING_CALLBACKS:
            result = hc.HostCallbackResult.make_success(kind, observed_effect=True)
        elif kind is hc.HostCallbackKind.INIT:
            result = hc.HostCallbackResult.make_success(
                kind,
                mount_state=hc.MountLifecycleState.READY,
                observed_effect=False,
            )
        elif kind is hc.HostCallbackKind.DESTROY:
            result = hc.HostCallbackResult.make_success(
                kind,
                mount_state=hc.MountLifecycleState.DESTROYED,
                observed_effect=False,
            )
        else:
            result = hc.HostCallbackResult.make_success(kind, observed_effect=False)
        assert result.success is True
        assert result.errno is hc.HostErrno.OK


# ---------------------------------------------------------------------------
# Durability and cache consistency
# ---------------------------------------------------------------------------


def test_durability_and_cache_modes_are_closed() -> None:
    durability = {m.value for m in hc.DurabilityMode}
    assert durability == {
        "buffered",
        "wal_file_sync",
        "wal_parent_sync",
        "wal_and_backend",
        "committed_visible",
    }
    cache = {m.value for m in hc.CacheConsistencyMode}
    assert cache == {
        "read_own_writes",
        "committed_reads",
        "generation_bound",
    }
    contract = hc.HostFilesystemAdapterContract.default()
    assert contract.default_durability_mode is hc.DurabilityMode.COMMITTED_VISIBLE
    assert (
        contract.default_cache_consistency is hc.CacheConsistencyMode.GENERATION_BOUND
    )


# ---------------------------------------------------------------------------
# Mount lifecycle
# ---------------------------------------------------------------------------


def test_mount_lifecycle_happy_path() -> None:
    life = hc.HostMountLifecycle(
        mount_id="mount-a",
        state=hc.MountLifecycleState.UNINITIALIZED,
        recovery_required=True,
        recovery_complete=False,
        ready=False,
    )
    life = life.transition_to(hc.MountLifecycleState.INITIALIZING)
    life = life.transition_to(hc.MountLifecycleState.RECOVERING)
    assert life.recovery_complete is False
    life = life.transition_to(hc.MountLifecycleState.READY)
    assert life.ready is True
    assert life.recovery_complete is True
    life = life.transition_to(hc.MountLifecycleState.DRAINING)
    assert life.ready is False
    life = life.transition_to(hc.MountLifecycleState.DESTROYING)
    life = life.transition_to(hc.MountLifecycleState.DESTROYED)
    assert life.state is hc.MountLifecycleState.DESTROYED
    assert life.open_handles == 0


def test_mount_readiness_requires_recovery_when_required() -> None:
    with pytest.raises(hc.HostLifecycleError):
        hc.HostMountLifecycle(
            mount_id="mount-b",
            state=hc.MountLifecycleState.READY,
            recovery_required=True,
            recovery_complete=False,
            ready=True,
        )
    ok = hc.HostMountLifecycle(
        mount_id="mount-b",
        state=hc.MountLifecycleState.READY,
        recovery_required=True,
        recovery_complete=True,
        ready=True,
    )
    assert ok.ready is True


def test_illegal_mount_transitions_rejected() -> None:
    assert not hc.is_legal_mount_transition(
        hc.MountLifecycleState.UNINITIALIZED,
        hc.MountLifecycleState.READY,
    )
    with pytest.raises(hc.HostLifecycleError):
        hc.assert_legal_mount_transition(
            hc.MountLifecycleState.DESTROYED,
            hc.MountLifecycleState.READY,
        )
    life = hc.HostMountLifecycle(
        mount_id="mount-c",
        state=hc.MountLifecycleState.DESTROYED,
        recovery_required=False,
        recovery_complete=True,
        ready=False,
    )
    with pytest.raises(hc.HostLifecycleError):
        life.transition_to(hc.MountLifecycleState.READY)


def test_mount_lifecycle_round_trip() -> None:
    life = hc.HostMountLifecycle(
        mount_id="mount-d",
        state=hc.MountLifecycleState.READY,
        platform=hc.HostPlatform.WINDOWS,
        recovery_required=True,
        recovery_complete=True,
        ready=True,
        open_handles=3,
        generation=9,
    )
    restored = hc.HostMountLifecycle.from_dict(life.to_record())
    assert restored == life


# ---------------------------------------------------------------------------
# Cancellation / deadline
# ---------------------------------------------------------------------------


def test_deadline_and_cancellation_never_succeed() -> None:
    deadline = hc.HostDeadline(deadline_ms=5_000, cancelled=True, cancel_reason="user")
    assert deadline.cancelled is True
    req = hc.HostCallbackRequest(
        kind=hc.HostCallbackKind.READ,
        path="f",
        deadline=deadline,
        request_id="c1",
    )
    cancelled = hc.evaluate_cancelled_request(req)
    assert cancelled is not None
    assert cancelled.success is False
    assert cancelled.errno is hc.HostErrno.ECANCELED

    timed = hc.HostCallbackResult.make_cancelled(
        hc.HostCallbackKind.WRITE, timed_out=True, request_id="t1"
    )
    assert timed.errno is hc.HostErrno.ETIMEDOUT
    assert timed.success is False

    active = hc.HostCallbackRequest(
        kind=hc.HostCallbackKind.READ,
        path="f",
        deadline=hc.HostDeadline(deadline_ms=60_000, cancelled=False),
    )
    assert hc.evaluate_cancelled_request(active) is None


def test_deadline_bounds() -> None:
    with pytest.raises(hc.HostBoundsError):
        hc.HostDeadline(deadline_ms=0)
    with pytest.raises(hc.HostBoundsError):
        hc.HostDeadline(deadline_ms=hc.MAX_CALLBACK_DEADLINE_MS + 1)


# ---------------------------------------------------------------------------
# Linux / Windows differences
# ---------------------------------------------------------------------------


def test_platform_differences_are_documented_and_fail_closed() -> None:
    topics = {diff.topic for diff in hc.PLATFORM_DIFFERENCES}
    assert {
        "case_identity",
        "reserved_names",
        "mount_root",
        "delete_while_open",
        "uid_gid_mode",
        "loader",
    } <= topics
    for diff in hc.PLATFORM_DIFFERENCES:
        assert diff.fail_closed is True
        assert diff.linux_behavior
        assert diff.windows_behavior
        record = diff.to_record()
        assert record["schema"] == hc.HOST_PLATFORM_DIFF_SCHEMA


def test_platform_specific_request_projection() -> None:
    linux_req = hc.HostCallbackRequest(
        kind=hc.HostCallbackKind.GETATTR,
        path="a/b",
        platform=hc.HostPlatform.LINUX,
    )
    win_req = hc.HostCallbackRequest(
        kind=hc.HostCallbackKind.GETATTR,
        path="a/b",
        platform=hc.HostPlatform.WINDOWS,
    )
    assert linux_req.platform is hc.HostPlatform.LINUX
    assert win_req.platform is hc.HostPlatform.WINDOWS
    # Same symbolic errno, platform carried on error/result.
    err_l = hc.HostError(errno=hc.HostErrno.ENOENT, platform=hc.HostPlatform.LINUX)
    err_w = hc.HostError(errno=hc.HostErrno.ENOENT, platform=hc.HostPlatform.WINDOWS)
    assert err_l.errno_number == err_w.errno_number == 2


# ---------------------------------------------------------------------------
# Adapter catalogue
# ---------------------------------------------------------------------------


def test_default_adapter_contract_catalogue() -> None:
    contract = hc.HostFilesystemAdapterContract.default()
    assert contract.contract_version == 1
    assert contract.schema_version == hc.SCHEMA_VERSION
    assert set(contract.required_callbacks) == hc.REQUIRED_SUPPORTED_CALLBACKS
    assert set(contract.unsupported_callbacks) == hc.EXPLICIT_UNSUPPORTED_CALLBACKS
    assert contract.release_is_idempotent is True
    assert contract.unknown_callbacks_forbidden is True
    assert contract.false_success_forbidden is True
    record = contract.to_record()
    assert record["schema"] == hc.HOST_FILESYSTEM_ADAPTER_SCHEMA
    cid = contract.content_id()
    assert cid.startswith("sha256:")
    assert len(cid) == len("sha256:") + 64
    # Content identity is stable for the default catalogue.
    assert hc.HostFilesystemAdapterContract.default().content_id() == cid


def test_adapter_projects_unsupported_callbacks() -> None:
    contract = hc.HostFilesystemAdapterContract.default()
    for kind in contract.unsupported_callbacks:
        result = contract.project_unsupported(kind, platform=hc.HostPlatform.LINUX)
        assert result.success is False
        assert result.errno in (hc.HostErrno.ENOSYS, hc.HostErrno.EOPNOTSUPP)
    with pytest.raises(hc.HostContractError):
        contract.project_unsupported(hc.HostCallbackKind.GETATTR)


def test_adapter_rejects_weakening_invariants() -> None:
    with pytest.raises(hc.HostContractError):
        hc.HostFilesystemAdapterContract(release_is_idempotent=False)
    with pytest.raises(hc.HostContractError):
        hc.HostFilesystemAdapterContract(unknown_callbacks_forbidden=False)
    with pytest.raises(hc.HostContractError):
        hc.HostFilesystemAdapterContract(false_success_forbidden=False)
    # Missing a required callback from the catalogue is rejected.
    reduced = tuple(
        k
        for k in hc.REQUIRED_SUPPORTED_CALLBACKS
        if k is not hc.HostCallbackKind.FSYNC
    )
    with pytest.raises(hc.HostContractError):
        hc.HostFilesystemAdapterContract(required_callbacks=reduced)


def test_result_round_trip_and_content_identity() -> None:
    meta = hc.HostMetadata(inode=1, kind=hc.HostEntryKind.DIRECTORY, mode=0o755)
    result = hc.HostCallbackResult.make_success(
        hc.HostCallbackKind.GETATTR,
        metadata=meta,
        request_id="r-9",
        platform=hc.HostPlatform.HERMETIC,
    )
    restored = hc.HostCallbackResult.from_dict(result.to_record())
    assert restored.kind is result.kind
    assert restored.metadata is not None
    assert restored.metadata.inode == 1
    assert restored.success is True
    payload = result.to_record()
    assert hc.content_identity(payload).startswith("sha256:")


def test_host_error_rejects_ok_errno() -> None:
    with pytest.raises(hc.HostContractError):
        hc.HostError(errno=hc.HostErrno.OK, message="not an error")


def test_handle_and_io_bounds() -> None:
    with pytest.raises(hc.HostBoundsError):
        hc.HostHandle(handle_id=0, inode=1, generation=0)
    with pytest.raises(hc.HostBoundsError):
        hc.HostCallbackRequest(
            kind=hc.HostCallbackKind.READ,
            size=hc.MAX_IO_LENGTH + 1,
        )


def test_canonical_json_rejects_non_finite_structures() -> None:
    with pytest.raises(hc.HostContractError):
        hc.canonical_json_bytes({"x": object()})  # type: ignore[dict-item]


def test_module_not_in_sys_path_side_effects() -> None:
    """Importing host_contracts must not require native libraries on PATH."""

    import ast

    # The validation environment PATH is sealed; ensure import still works.
    assert "ipfs_kit_py.core.vfs.host_contracts" in sys.modules
    source = HOST_CONTRACTS_PATH.read_text(encoding="utf-8")
    # Module-level imports only (exclude function-local imports inside guards).
    module_tree = ast.parse(source)
    module_level_roots: set[str] = set()
    all_import_roots: set[str] = set()
    for node in ast.walk(module_tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                all_import_roots.add(alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                all_import_roots.add(node.module.split(".", 1)[0])
    for node in module_tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_level_roots.add(alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                module_level_roots.add(node.module.split(".", 1)[0])
    assert module_level_roots <= {
        "__future__",
        "hashlib",
        "json",
        "re",
        "collections",
        "dataclasses",
        "enum",
        "typing",
    }, f"unexpected module-level imports: {sorted(module_level_roots)}"
    # Function-local imports may use stdlib (ast) for the inertness guard only.
    assert "fuse" not in all_import_roots
    assert "fusepy" not in all_import_roots
    assert "ipfs_kit_py" not in module_level_roots
