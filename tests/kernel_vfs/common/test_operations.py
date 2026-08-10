"""KVFS-206: Platform-neutral KernelVFSOperations and composed request runtime.

Acceptance coverage:

* direct tests exercise getattr / readdir / access / statfs / utimens /
  open / create / read / write / truncate / flush / fsync / release /
  mkdir / rmdir / unlink / rename / init / destroy;
* every result and errno matches the host callback contract;
* unsupported callbacks reject with ENOSYS / EOPNOTSUPP;
* no fuse import or native side effect occurs.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ipfs_kit_py.core.vfs.host_contracts import (
    EXPLICIT_UNSUPPORTED_CALLBACKS,
    REQUIRED_SUPPORTED_CALLBACKS,
    HostCallbackKind,
    HostCallbackRequest,
    HostCallbackResult,
    HostErrno,
    HostPlatform,
    HostUnknownCallbackError,
    MountLifecycleState,
    OpenFlag,
    callback_disposition,
    default_unsupported_errno,
    errno_number,
)
from ipfs_kit_py.core.vfs.metadata import F_OK, R_OK, UTIME_NOW, W_OK
from ipfs_kit_py.kernel_vfs.operations import (
    COMPOSED_REQUEST_RUNTIME_SCHEMA,
    CONTRACT_VERSION,
    KERNEL_VFS_OPERATIONS_SCHEMA,
    SCHEMA_VERSION,
    TASK_ID,
    ComposedRequestRuntime_V1,
    KernelVFSOperations,
    KernelVFSOperations_V1,
    KernelVFSResult,
    OperationsError,
    OperationsErrorCode,
    assert_no_fusepy_import,
    build_kernel_vfs_operations,
)

# test file: ipfs_kit_py/tests/kernel_vfs/common/test_operations.py
PACKAGE_ROOT = Path(__file__).resolve().parents[3]
OPERATIONS_PATH = PACKAGE_ROOT / "ipfs_kit_py" / "kernel_vfs" / "operations.py"


# ---------------------------------------------------------------------------
# Artifact / schema / inertness
# ---------------------------------------------------------------------------


def test_declared_operations_module_exists() -> None:
    assert OPERATIONS_PATH.is_file()
    assert OPERATIONS_PATH.stat().st_size > 0


def test_schema_versions_and_interface_aliases() -> None:
    assert TASK_ID == "KVFS-206"
    assert CONTRACT_VERSION == 1
    assert SCHEMA_VERSION.startswith("1.")
    assert KERNEL_VFS_OPERATIONS_SCHEMA == KernelVFSOperations_V1
    assert COMPOSED_REQUEST_RUNTIME_SCHEMA == ComposedRequestRuntime_V1
    assert KernelVFSOperations_V1.endswith("@1")
    assert ComposedRequestRuntime_V1.endswith("@1")
    assert KernelVFSOperations.SCHEMA == KERNEL_VFS_OPERATIONS_SCHEMA


def test_module_has_no_fusepy_dependency() -> None:
    assert_no_fusepy_import()
    source = OPERATIONS_PATH.read_text(encoding="utf-8")
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
    # Import must not pull native FUSE into sys.modules as a hard dep of this module.
    import ipfs_kit_py.kernel_vfs.operations as ops_mod

    assert "fuse" not in getattr(ops_mod, "__dict__", {})
    assert "fusepy" not in getattr(ops_mod, "__dict__", {})


def test_exports_are_importable() -> None:
    assert callable(KernelVFSOperations.getattr)
    assert callable(KernelVFSOperations.readdir)
    assert callable(KernelVFSOperations.access)
    assert callable(KernelVFSOperations.statfs)
    assert callable(KernelVFSOperations.utimens)
    assert callable(KernelVFSOperations.open)
    assert callable(KernelVFSOperations.create)
    assert callable(KernelVFSOperations.read)
    assert callable(KernelVFSOperations.write)
    assert callable(KernelVFSOperations.truncate)
    assert callable(KernelVFSOperations.flush)
    assert callable(KernelVFSOperations.fsync)
    assert callable(KernelVFSOperations.release)
    assert callable(KernelVFSOperations.mkdir)
    assert callable(KernelVFSOperations.rmdir)
    assert callable(KernelVFSOperations.unlink)
    assert callable(KernelVFSOperations.rename)
    assert callable(KernelVFSOperations.init)
    assert callable(KernelVFSOperations.destroy)
    assert callable(KernelVFSOperations.dispatch)
    assert callable(build_kernel_vfs_operations)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ops() -> KernelVFSOperations:
    runtime = KernelVFSOperations.with_memory_storage(
        clock=lambda: 1_700_000_000_000,
        platform=HostPlatform.HERMETIC,
    )
    init = runtime.init()
    assert init.success is True, init.to_record()
    assert runtime.ready is True
    try:
        yield runtime
    finally:
        runtime.close()


def _assert_contract_result(outcome: KernelVFSResult, kind: HostCallbackKind) -> None:
    """Every operations result must embed a valid HostCallbackResult."""

    assert isinstance(outcome, KernelVFSResult)
    assert isinstance(outcome.result, HostCallbackResult)
    assert outcome.kind is kind
    # Re-validate contract invariants by reconstructing from the record.
    rebuilt = HostCallbackResult.from_dict(outcome.result.to_record())
    assert rebuilt.success is outcome.success
    assert rebuilt.errno is outcome.errno
    if outcome.success:
        assert outcome.errno is HostErrno.OK
        assert outcome.error is None
        assert outcome.errno_number == 0
    else:
        assert outcome.errno is not HostErrno.OK
        assert outcome.error is not None
        assert outcome.error.errno is outcome.errno
        assert outcome.errno_number == errno_number(outcome.errno, outcome.platform)
        assert outcome.observed_effect is False


# ---------------------------------------------------------------------------
# Lifecycle: init / destroy
# ---------------------------------------------------------------------------


def test_init_and_destroy_lifecycle() -> None:
    runtime = KernelVFSOperations.with_memory_storage(clock=lambda: 1)
    assert runtime.lifecycle is MountLifecycleState.UNINITIALIZED

    init = runtime.init()
    _assert_contract_result(init, HostCallbackKind.INIT)
    assert init.success is True
    assert init.errno is HostErrno.OK
    assert runtime.lifecycle is MountLifecycleState.READY
    assert init.mount_state is MountLifecycleState.READY

    # Idempotent init while ready.
    again = runtime.init()
    assert again.success is True

    destroy = runtime.destroy()
    _assert_contract_result(destroy, HostCallbackKind.DESTROY)
    assert destroy.success is True
    assert runtime.lifecycle is MountLifecycleState.DESTROYED

    # Idempotent destroy.
    destroy2 = runtime.destroy()
    assert destroy2.success is True


def test_callbacks_reject_before_init() -> None:
    runtime = KernelVFSOperations.with_memory_storage(clock=lambda: 1)
    result = runtime.mkdir("too-early")
    _assert_contract_result(result, HostCallbackKind.MKDIR)
    assert result.success is False
    assert result.errno is HostErrno.EAGAIN
    runtime.close()


def test_callbacks_reject_after_destroy(ops: KernelVFSOperations) -> None:
    ops.destroy()
    result = ops.getattr("anything")
    _assert_contract_result(result, HostCallbackKind.GETATTR)
    assert result.success is False
    assert result.errno is HostErrno.ENODEV


def test_context_manager_init_destroy() -> None:
    with KernelVFSOperations.with_memory_storage(clock=lambda: 42) as runtime:
        assert runtime.ready is True
        assert runtime.mkdir("ctx").success is True
    assert runtime.lifecycle is MountLifecycleState.DESTROYED


def test_build_factory_auto_init() -> None:
    runtime = build_kernel_vfs_operations(
        backend="memory", clock=lambda: 7, auto_init=True
    )
    try:
        assert runtime.ready is True
        assert runtime.statfs().success is True
    finally:
        runtime.close()


# ---------------------------------------------------------------------------
# Full required callback surface
# ---------------------------------------------------------------------------


def test_all_required_callbacks_exercise_contract(ops: KernelVFSOperations) -> None:
    """Direct exercise of every required production callback."""

    # init already done by fixture; re-check.
    init = ops.init()
    _assert_contract_result(init, HostCallbackKind.INIT)
    assert init.success is True

    # mkdir
    mk = ops.mkdir("docs", mode=0o755)
    _assert_contract_result(mk, HostCallbackKind.MKDIR)
    assert mk.success is True
    assert mk.observed_effect is True
    assert mk.errno is HostErrno.OK

    # create
    created = ops.create("docs/note.txt", b"hello", mode=0o644)
    _assert_contract_result(created, HostCallbackKind.CREATE)
    assert created.success is True
    assert created.observed_effect is True
    assert created.handle is not None
    assert created.handle.handle_id >= 1
    create_handle = created.handle

    # getattr
    st = ops.getattr("docs/note.txt")
    _assert_contract_result(st, HostCallbackKind.GETATTR)
    assert st.success is True
    assert st.metadata is not None
    assert st.metadata.size >= 5

    # readdir
    listing = ops.readdir("docs")
    _assert_contract_result(listing, HostCallbackKind.READDIR)
    assert listing.success is True
    assert "note.txt" in listing.dir_entries

    # access
    acc = ops.access("docs/note.txt", mask=F_OK | R_OK)
    _assert_contract_result(acc, HostCallbackKind.ACCESS)
    assert acc.success is True

    # statfs
    fs = ops.statfs()
    _assert_contract_result(fs, HostCallbackKind.STATFS)
    assert fs.success is True
    assert fs.detail  # projector volume stats

    # utimens
    ut = ops.utimens("docs/note.txt", atime_ns=UTIME_NOW, mtime_ns=UTIME_NOW)
    _assert_contract_result(ut, HostCallbackKind.UTIMENS)
    assert ut.success is True
    assert ut.observed_effect is True

    # open
    opened = ops.open("docs/note.txt", (OpenFlag.O_RDWR,))
    _assert_contract_result(opened, HostCallbackKind.OPEN)
    assert opened.success is True
    assert opened.handle is not None
    handle = opened.handle

    # write (path form)
    written = ops.write("docs/note.txt", b"!!", offset=5)
    _assert_contract_result(written, HostCallbackKind.WRITE)
    assert written.success is True
    assert written.observed_effect is True
    assert written.bytes_transferred == 2

    # read (path form)
    read = ops.read("docs/note.txt", offset=0, size=16)
    _assert_contract_result(read, HostCallbackKind.READ)
    assert read.success is True
    assert read.data.startswith(b"hello")
    assert read.bytes_transferred >= 5

    # write via handle
    hw = ops.write(
        "docs/note.txt",
        b"Z",
        offset=0,
        handle_id=handle.handle_id,
        generation=handle.generation,
    )
    _assert_contract_result(hw, HostCallbackKind.WRITE)
    assert hw.success is True

    # read via handle
    hr = ops.read(
        "docs/note.txt",
        offset=0,
        size=8,
        handle_id=handle.handle_id,
        generation=handle.generation,
    )
    _assert_contract_result(hr, HostCallbackKind.READ)
    assert hr.success is True
    assert hr.data[:1] == b"Z"

    # truncate
    trunc = ops.truncate("docs/note.txt", 1)
    _assert_contract_result(trunc, HostCallbackKind.TRUNCATE)
    assert trunc.success is True
    assert trunc.observed_effect is True

    # flush
    flushed = ops.flush(handle_id=handle.handle_id, generation=handle.generation)
    _assert_contract_result(flushed, HostCallbackKind.FLUSH)
    assert flushed.success is True

    # fsync
    synced = ops.fsync(handle_id=handle.handle_id, generation=handle.generation)
    _assert_contract_result(synced, HostCallbackKind.FSYNC)
    assert synced.success is True
    # fsync must not claim only buffered durability.
    assert synced.result.durability_mode.value != "buffered"

    # release (idempotent)
    rel = ops.release(handle_id=handle.handle_id, generation=handle.generation)
    _assert_contract_result(rel, HostCallbackKind.RELEASE)
    assert rel.success is True
    rel2 = ops.release(handle_id=handle.handle_id, generation=handle.generation)
    assert rel2.success is True

    # Also release the create handle.
    ops.release(
        handle_id=create_handle.handle_id, generation=create_handle.generation
    )

    # rename
    renamed = ops.rename("docs/note.txt", "docs/renamed.txt")
    _assert_contract_result(renamed, HostCallbackKind.RENAME)
    assert renamed.success is True
    assert renamed.observed_effect is True

    # unlink
    unlinked = ops.unlink("docs/renamed.txt")
    _assert_contract_result(unlinked, HostCallbackKind.UNLINK)
    assert unlinked.success is True
    assert unlinked.observed_effect is True

    # rmdir
    removed = ops.rmdir("docs")
    _assert_contract_result(removed, HostCallbackKind.RMDIR)
    assert removed.success is True
    assert removed.observed_effect is True

    # destroy
    destroyed = ops.destroy()
    _assert_contract_result(destroyed, HostCallbackKind.DESTROY)
    assert destroyed.success is True


def test_dispatch_by_callback_kind_and_request(ops: KernelVFSOperations) -> None:
    assert ops.mkdir("by-kind").success
    assert ops.dispatch(HostCallbackKind.CREATE, path="by-kind/a", data=b"x").success

    request = HostCallbackRequest(
        kind=HostCallbackKind.GETATTR,
        path="by-kind/a",
        platform=HostPlatform.HERMETIC,
    )
    outcome = ops.dispatch(request)
    _assert_contract_result(outcome, HostCallbackKind.GETATTR)
    assert outcome.success is True

    # String name dispatch.
    listing = ops.dispatch("readdir", path="by-kind")
    assert listing.success is True
    assert "a" in listing.dir_entries


# ---------------------------------------------------------------------------
# Exact errno projection
# ---------------------------------------------------------------------------


def test_exact_errno_on_missing_and_conflict(ops: KernelVFSOperations) -> None:
    missing = ops.getattr("no-such-path")
    _assert_contract_result(missing, HostCallbackKind.GETATTR)
    assert missing.success is False
    assert missing.errno is HostErrno.ENOENT

    assert ops.create("dup.txt", b"a").success
    again = ops.create("dup.txt", b"b")
    _assert_contract_result(again, HostCallbackKind.CREATE)
    assert again.success is False
    assert again.errno is HostErrno.EEXIST

    assert ops.mkdir("adir").success
    # Opening a directory as a file.
    opened = ops.open("adir", (OpenFlag.O_RDONLY,))
    assert opened.success is False
    assert opened.errno is HostErrno.EISDIR

    missing_unlink = ops.unlink("ghost")
    assert missing_unlink.success is False
    assert missing_unlink.errno is HostErrno.ENOENT

    missing_access = ops.access("ghost", mask=F_OK)
    assert missing_access.success is False
    assert missing_access.errno is HostErrno.ENOENT


def test_false_success_is_impossible_for_supported(ops: KernelVFSOperations) -> None:
    ok = ops.mkdir("ok-dir")
    assert ok.success is True
    assert ok.errno is HostErrno.OK
    # HostCallbackResult construction already forbids success+nonzero errno.
    with pytest.raises(Exception):
        HostCallbackResult(
            kind=HostCallbackKind.MKDIR,
            success=True,
            errno=HostErrno.EIO,
            observed_effect=True,
        )


# ---------------------------------------------------------------------------
# Unsupported callbacks reject
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", sorted(EXPLICIT_UNSUPPORTED_CALLBACKS, key=lambda k: k.value))
def test_unsupported_callbacks_reject(
    ops: KernelVFSOperations, kind: HostCallbackKind
) -> None:
    outcome = ops.dispatch(kind, path="x", target_path="y")
    _assert_contract_result(outcome, kind)
    assert outcome.success is False
    assert outcome.errno in (HostErrno.ENOSYS, HostErrno.EOPNOTSUPP)
    assert outcome.errno is default_unsupported_errno(kind)
    assert outcome.observed_effect is False
    assert callback_disposition(kind) is callback_disposition(kind.value)


def test_reject_unsupported_helper(ops: KernelVFSOperations) -> None:
    outcome = ops.reject_unsupported(HostCallbackKind.SYMLINK)
    assert outcome.success is False
    assert outcome.errno is HostErrno.ENOSYS

    with pytest.raises(OperationsError) as excinfo:
        ops.reject_unsupported(HostCallbackKind.GETATTR)
    assert excinfo.value.code is OperationsErrorCode.INVALID


def test_unknown_callback_raises(ops: KernelVFSOperations) -> None:
    with pytest.raises(HostUnknownCallbackError):
        ops.dispatch("not_a_real_callback")


def test_required_set_matches_plan() -> None:
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
    assert {k.value for k in REQUIRED_SUPPORTED_CALLBACKS} == expected


# ---------------------------------------------------------------------------
# Composed runtime wiring
# ---------------------------------------------------------------------------


def test_composed_runtime_wires_host_and_concurrency(ops: KernelVFSOperations) -> None:
    assert ops.host is not None
    assert ops.concurrency is not None
    # Shared handle table identity.
    assert ops.concurrency.handles is ops.host.handles
    assert ops.platform is HostPlatform.HERMETIC
    record = ops.to_record()
    assert record["schema"] == KERNEL_VFS_OPERATIONS_SCHEMA
    assert record["lifecycle"] == MountLifecycleState.READY.value
    assert record["host_schema"]


def test_open_write_flush_fsync_release_handle_path(ops: KernelVFSOperations) -> None:
    assert ops.create("h.bin", b"base").success
    opened = ops.open("h.bin", (OpenFlag.O_RDWR,))
    assert opened.success is True
    assert opened.handle is not None
    hid = opened.handle.handle_id
    gen = opened.handle.generation

    written = ops.write(data=b"ZZ", offset=0, handle_id=hid, generation=gen, path="h.bin")
    assert written.success is True
    assert written.observed_effect is True

    flushed = ops.flush(handle_id=hid, generation=gen)
    assert flushed.success is True

    synced = ops.fsync(handle_id=hid, generation=gen)
    assert synced.success is True

    read = ops.read(path="h.bin", offset=0, size=4)
    assert read.success is True
    assert read.data.startswith(b"ZZ")

    assert ops.release(handle_id=hid, generation=gen).success is True
    assert ops.release(handle_id=hid, generation=gen).success is True  # idempotent


def test_namespace_crud_roundtrip(ops: KernelVFSOperations) -> None:
    assert ops.mkdir("tree").success
    assert ops.mkdir("tree/sub").success
    assert ops.create("tree/sub/f.txt", b"payload").success

    listing = ops.readdir("tree/sub")
    assert "f.txt" in listing.dir_entries

    assert ops.rename("tree/sub/f.txt", "tree/sub/g.txt").success
    assert ops.unlink("tree/sub/g.txt").success
    assert ops.rmdir("tree/sub").success
    assert ops.rmdir("tree").success

    gone = ops.getattr("tree")
    assert gone.success is False
    assert gone.errno is HostErrno.ENOENT


def test_access_write_mask_on_file(ops: KernelVFSOperations) -> None:
    assert ops.create("rw.txt", b"x", mode=0o644).success
    ok = ops.access("rw.txt", mask=R_OK | W_OK)
    # Default projector ownership is root/caller-friendly in hermetic mode.
    assert ok.success is True or ok.errno in (HostErrno.EACCES, HostErrno.EPERM)


def test_result_records_are_serializable(ops: KernelVFSOperations) -> None:
    outcome = ops.create("rec.txt", b"payload")
    record = outcome.to_record()
    assert record["schema"]
    assert record["result"]["success"] is True
    assert record["data_len"] == len(b"payload")
    host_cb = outcome.to_host_callback_result()
    assert host_cb.success is True
    assert host_cb.kind is HostCallbackKind.CREATE


def test_trace_records_callbacks(ops: KernelVFSOperations) -> None:
    ops.mkdir("traced")
    ops.create("traced/f", b"1")
    ops.getattr("traced/f")
    kinds = set(ops.trace.kinds())
    assert "callback" in kinds or "init" in kinds
    assert ops.trace.steps


# ---------------------------------------------------------------------------
# Platform projection / hermetic profile
# ---------------------------------------------------------------------------


def test_platform_errno_numbers_are_linux_for_hermetic(ops: KernelVFSOperations) -> None:
    missing = ops.getattr("missing")
    assert missing.errno_number == errno_number(HostErrno.ENOENT, HostPlatform.HERMETIC)
    assert missing.errno_number == 2


def test_execute_alias(ops: KernelVFSOperations) -> None:
    assert ops.execute is ops.dispatch
    assert ops.execute(HostCallbackKind.STATFS).success is True
