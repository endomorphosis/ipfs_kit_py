"""KVFS-203: Host façade over CanonicalVFSService with real storage injection.

Acceptance coverage:

* every supported host operation reaches CanonicalVFSService contracts with
  one path/result/error/effect authority;
* real (ranged) storage is injected;
* create/read/write/truncate/list/mkdir/rmdir/unlink/rename/metadata work
  without a FUSE/WinFsp driver; and
* legacy paths cannot bypass admitted mutations.
"""

from __future__ import annotations

import ast
from pathlib import Path

import anyio
import pytest

from ipfs_kit_py.core.vfs.adapters import LegacyVFSAdapter
from ipfs_kit_py.core.vfs.host_contracts import (
    HostCallbackKind,
    HostErrno,
    HostEntryKind,
    OpenFlag,
)
from ipfs_kit_py.core.vfs.host_service import (
    CONTRACT_VERSION,
    HOST_VFS_SERVICE_SCHEMA,
    RANGED_STORAGE_BRIDGE_SCHEMA,
    SCHEMA_VERSION,
    HostOperationResult,
    HostServiceError,
    HostServiceErrorCode,
    HostTraceKind,
    HostVFSService,
    HostVFSService_V1,
    RangedStorageBoundaryAdapter,
    RangedStorageBridge_V1,
    _clock_ms_to_now_ns,
    build_host_vfs_service,
)
from ipfs_kit_py.core.vfs.metadata import MAX_TIME_NS
from ipfs_kit_py.core.vfs.service import CanonicalVFSService, VFSEventKind
from ipfs_kit_py.core.vfs.storage import (
    MemoryRangedStorage,
    StorageOp,
    create_ranged_storage,
)

# test file: ipfs_kit_py/tests/kernel_vfs/common/test_host_service.py
PACKAGE_ROOT = Path(__file__).resolve().parents[3]
HOST_SERVICE_PATH = PACKAGE_ROOT / "ipfs_kit_py" / "core" / "vfs" / "host_service.py"


# ---------------------------------------------------------------------------
# Artifact / schema / inertness
# ---------------------------------------------------------------------------


def test_declared_host_service_module_exists() -> None:
    assert HOST_SERVICE_PATH.is_file()
    assert HOST_SERVICE_PATH.stat().st_size > 0


def test_schema_versions_and_interface_aliases() -> None:
    assert CONTRACT_VERSION == 1
    assert SCHEMA_VERSION.startswith("1.")
    assert HOST_VFS_SERVICE_SCHEMA == HostVFSService_V1
    assert RANGED_STORAGE_BRIDGE_SCHEMA == RangedStorageBridge_V1
    assert HostVFSService_V1.endswith("@1")
    assert RangedStorageBridge_V1.endswith("@1")


def test_module_has_no_fusepy_dependency() -> None:
    source = HOST_SERVICE_PATH.read_text(encoding="utf-8")
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


def test_exports_are_importable() -> None:
    assert HostVFSService.SCHEMA == HOST_VFS_SERVICE_SCHEMA
    assert callable(HostVFSService.create)
    assert callable(HostVFSService.read)
    assert callable(HostVFSService.write)
    assert callable(HostVFSService.truncate)
    assert callable(HostVFSService.list)
    assert callable(HostVFSService.mkdir)
    assert callable(HostVFSService.rmdir)
    assert callable(HostVFSService.unlink)
    assert callable(HostVFSService.rename)
    assert callable(HostVFSService.metadata)
    assert callable(build_host_vfs_service)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def host() -> HostVFSService:
    return HostVFSService.with_memory_storage(clock=lambda: 1_700_000_000_000)


def test_clock_ms_to_now_ns_stays_within_metadata_bound() -> None:
    """Host unix-ms clocks must not overflow MetadataProjector's time bound."""

    # Small synthetic clocks scale to true nanoseconds.
    assert _clock_ms_to_now_ns(1) == 1_000_000
    assert _clock_ms_to_now_ns(42) == 42_000_000
    # Realistic wall-clock ms (and the suite fixture) stay within MAX_TIME_NS.
    wall_ms = 1_700_000_000_000
    projected = _clock_ms_to_now_ns(wall_ms)
    assert 0 <= projected <= MAX_TIME_NS
    assert projected == wall_ms
    # Host construction + mutation with a realistic clock must not raise.
    service = HostVFSService.with_memory_storage(clock=lambda: wall_ms)
    assert service.mkdir("bounded-clock").success is True


# ---------------------------------------------------------------------------
# Real storage injection
# ---------------------------------------------------------------------------


def test_real_ranged_storage_is_injected(host: HostVFSService) -> None:
    assert host.ranged_storage is not None
    assert isinstance(host.ranged_storage, MemoryRangedStorage)
    assert isinstance(host.storage_boundary, RangedStorageBoundaryAdapter)
    assert host.service.storage is host.storage_boundary
    assert isinstance(host.canonical, CanonicalVFSService)


def test_factory_builds_with_backend_kinds(tmp_path: Path) -> None:
    mem = build_host_vfs_service(backend="memory", clock=lambda: 1)
    assert mem.ranged_storage is not None
    local = build_host_vfs_service(
        backend="local",
        root=str(tmp_path / "root"),
        clock=lambda: 1,
    )
    assert local.ranged_storage is not None
    assert local.mkdir("docs").success is True


def test_bridge_materializes_put_get_roundtrip() -> None:
    ranged = MemoryRangedStorage(clock=lambda: 42)
    bridge = RangedStorageBoundaryAdapter(ranged)
    from ipfs_kit_py.core.vfs.contracts import VFSEntryKind
    from ipfs_kit_py.core.vfs.service import VFSStoredEntry, content_cid_for_bytes

    gen = bridge.bump_generation()
    entry = VFSStoredEntry(
        kind=VFSEntryKind.FILE,
        content=b"hello-bridge",
        content_cid=content_cid_for_bytes(b"hello-bridge"),
        version_cid=f"v:{gen}",
        mtime_unix_ms=gen,
    )
    bridge.put("a.txt", entry)
    got = bridge.get("a.txt")
    assert got is not None
    assert got.content == b"hello-bridge"
    assert "a.txt" in bridge.children("")
    assert bridge.entry_count() >= 2  # root + file
    effects = bridge.effects()
    assert any(e.op is StorageOp.STAGED_WRITE for e in effects)


# ---------------------------------------------------------------------------
# Host operations without a driver
# ---------------------------------------------------------------------------


def test_mkdir_create_read_write_truncate_list_rename_unlink(host: HostVFSService) -> None:
    mk = host.mkdir("docs")
    assert mk.success is True
    assert mk.observed_effect is True
    assert mk.errno is HostErrno.OK

    created = host.create("docs/note.txt", b"hello")
    assert created.success is True
    assert created.observed_effect is True
    assert created.data == b"hello"

    read = host.read("docs/note.txt")
    assert read.success is True
    assert read.data == b"hello"
    assert read.observed_effect is False

    written = host.write("docs/note.txt", b"!", offset=5)
    assert written.success is True
    assert written.observed_effect is True
    assert host.read("docs/note.txt").data == b"hello!"

    trunc = host.truncate("docs/note.txt", 3)
    assert trunc.success is True
    assert host.read("docs/note.txt").data == b"hel"

    listing = host.list("docs")
    assert listing.success is True
    assert "note.txt" in listing.dir_entries

    renamed = host.rename("docs/note.txt", "docs/renamed.txt")
    assert renamed.success is True
    assert host.read("docs/renamed.txt").data == b"hel"
    missing = host.read("docs/note.txt")
    assert missing.success is False
    assert missing.errno is HostErrno.ENOENT

    unlinked = host.unlink("docs/renamed.txt")
    assert unlinked.success is True
    assert host.list("docs").dir_entries == ()

    rmdir = host.rmdir("docs")
    assert rmdir.success is True


def test_metadata_getattr_projection(host: HostVFSService) -> None:
    assert host.mkdir("meta").success
    assert host.create("meta/f.bin", b"abcd").success

    file_meta = host.metadata("meta/f.bin")
    assert file_meta.success is True
    assert file_meta.metadata is not None
    assert file_meta.metadata.kind is HostEntryKind.FILE
    assert file_meta.metadata.size == 4
    assert file_meta.observed_effect is False

    dir_meta = host.getattr("meta")
    assert dir_meta.success is True
    assert dir_meta.metadata is not None
    assert dir_meta.metadata.kind is HostEntryKind.DIRECTORY


def test_write_creates_missing_file(host: HostVFSService) -> None:
    result = host.write("spawned.txt", b"new")
    assert result.success is True
    assert host.read("spawned.txt").data == b"new"


def test_offset_write_zero_fills_sparse_prefix(host: HostVFSService) -> None:
    result = host.write("sparse.bin", b"XY", offset=4)
    assert result.success is True
    data = host.read("sparse.bin").data
    assert data == b"\x00\x00\x00\x00XY"


def test_errors_project_exact_errno(host: HostVFSService) -> None:
    missing = host.read("nope")
    assert missing.success is False
    assert missing.errno is HostErrno.ENOENT

    assert host.create("dup.txt", b"a").success
    again = host.create("dup.txt", b"b")
    assert again.success is False
    assert again.errno is HostErrno.EEXIST

    assert host.mkdir("adir").success
    write_dir = host.write("adir", b"x", create=False)
    assert write_dir.success is False
    assert write_dir.errno is HostErrno.EISDIR


def test_all_ops_emit_host_and_canonical_traces(host: HostVFSService) -> None:
    host.mkdir("t")
    host.create("t/f", b"1")
    host.read("t/f")
    host.write("t/f", b"2")
    host.truncate("t/f", 1)
    host.list("t")
    host.metadata("t/f")
    host.rename("t/f", "t/g")
    host.unlink("t/g")
    host.rmdir("t")

    kinds = set(host.trace.kinds())
    for expected in (
        HostTraceKind.MKDIR.value,
        HostTraceKind.CREATE.value,
        HostTraceKind.READ.value,
        HostTraceKind.WRITE.value,
        HostTraceKind.TRUNCATE.value,
        HostTraceKind.LIST.value,
        HostTraceKind.METADATA.value,
        HostTraceKind.RENAME.value,
        HostTraceKind.UNLINK.value,
        HostTraceKind.RMDIR.value,
        HostTraceKind.EXECUTE.value,
    ):
        assert expected in kinds

    # Canonical authority recorded success events for mutations.
    event_kinds = {e.kind for e in host.service.event_log}
    assert VFSEventKind.SUCCESS in event_kinds


# ---------------------------------------------------------------------------
# Authority: every mutation goes through CanonicalVFSService
# ---------------------------------------------------------------------------


def test_mutations_reach_canonical_service_only(host: HostVFSService) -> None:
    before = len(host.service.event_log)
    assert host.mkdir("auth").success
    assert host.create("auth/x", b"z").success
    after = host.service.event_log[before:]
    assert after
    assert all(
        e.kind in (VFSEventKind.SUCCESS, VFSEventKind.OBSERVATION, VFSEventKind.FAILURE)
        for e in after
    )
    # Real storage observed effects.
    effects = host.storage_effects()
    assert effects
    ops = {e.op for e in effects}
    assert StorageOp.MKDIR in ops or StorageOp.STAGED_WRITE in ops


def test_result_records_are_finite_and_serializable(host: HostVFSService) -> None:
    result = host.create("rec.txt", b"payload")
    assert isinstance(result, HostOperationResult)
    record = result.to_record()
    assert record["schema"]
    assert record["success"] is True
    assert record["kind"] == "create"
    assert "data_len" in record


# ---------------------------------------------------------------------------
# Legacy paths cannot bypass admitted mutations
# ---------------------------------------------------------------------------


def test_legacy_adapter_uses_same_canonical_service(host: HostVFSService) -> None:
    adapter = host.legacy_adapter()
    assert isinstance(adapter, LegacyVFSAdapter)
    assert adapter.service is host.service

    # Unsupported legacy op rejected — cannot invent a bypass.
    unsupported = anyio.run(lambda: adapter.execute("provider_only_operation", path="x"))
    assert unsupported["success"] is False
    assert unsupported["code"] == "unsupported_legacy_operation"

    # Admitted legacy mkdir still hits the same service/storage.
    ok = anyio.run(lambda: adapter.execute("mkdir", path="legacy-dir"))
    assert ok["success"] is True
    listing = host.list("")
    assert "legacy-dir" in listing.dir_entries


def test_assert_legacy_cannot_bypass_raises(host: HostVFSService) -> None:
    with pytest.raises(HostServiceError) as excinfo:
        host.assert_legacy_cannot_bypass()
    assert excinfo.value.code is HostServiceErrorCode.LEGACY_BYPASS
    assert excinfo.value.errno is HostErrno.EPERM


def test_host_has_no_raw_storage_mutator_api() -> None:
    source = HOST_SERVICE_PATH.read_text(encoding="utf-8")
    # Public host surface must not expose a direct put/delete that skips execute.
    # The bridge implements put for the service; HostVFSService must not.
    tree = ast.parse(source)
    host_class = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "HostVFSService":
            host_class = node
            break
    assert host_class is not None
    method_names = {
        n.name
        for n in host_class.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    # Forbidden direct-mutation names on the host façade.
    for banned in ("put_entry", "raw_put", "direct_delete", "bypass_write"):
        assert banned not in method_names


# ---------------------------------------------------------------------------
# Callback dispatch without driver
# ---------------------------------------------------------------------------


def test_execute_callback_required_ops(host: HostVFSService) -> None:
    init = host.execute_callback(HostCallbackKind.INIT)
    assert init.success is True

    mkdir = host.execute_callback(HostCallbackKind.MKDIR, path="cb")
    assert mkdir.success is True
    assert mkdir.observed_effect is True

    create = host.execute_callback(
        HostCallbackKind.CREATE,
        path="cb/f.txt",
        data=b"hi",
        flags=(OpenFlag.O_RDWR, OpenFlag.O_CREAT),
    )
    assert create.success is True
    assert create.handle is not None

    getattr_r = host.execute_callback(HostCallbackKind.GETATTR, path="cb/f.txt")
    assert getattr_r.success is True
    assert getattr_r.metadata is not None

    readdir = host.execute_callback(HostCallbackKind.READDIR, path="cb")
    assert readdir.success is True
    assert "f.txt" in readdir.dir_entries

    write = host.execute_callback(
        HostCallbackKind.WRITE,
        path="cb/f.txt",
        data=b"!!",
        offset=2,
    )
    assert write.success is True

    read = host.execute_callback(
        HostCallbackKind.READ,
        path="cb/f.txt",
        offset=0,
        size=4,
    )
    assert read.success is True
    assert read.bytes_transferred >= 2

    trunc = host.execute_callback(HostCallbackKind.TRUNCATE, path="cb/f.txt", size=1)
    assert trunc.success is True

    rename = host.execute_callback(
        HostCallbackKind.RENAME,
        path="cb/f.txt",
        target_path="cb/g.txt",
    )
    assert rename.success is True

    unlink = host.execute_callback(HostCallbackKind.UNLINK, path="cb/g.txt")
    assert unlink.success is True

    rmdir = host.execute_callback(HostCallbackKind.RMDIR, path="cb")
    assert rmdir.success is True

    destroy = host.execute_callback(HostCallbackKind.DESTROY)
    assert destroy.success is True


def test_execute_callback_unsupported_is_enotsupp_or_enosys(
    host: HostVFSService,
) -> None:
    result = host.execute_callback(HostCallbackKind.SYMLINK, path="a", target_path="b")
    assert result.success is False
    assert result.errno in (HostErrno.ENOSYS, HostErrno.EOPNOTSUPP)
    assert result.observed_effect is False


def test_open_flush_release_handle_path(host: HostVFSService) -> None:
    assert host.create("h.bin", b"base").success
    opened = host.open("h.bin", (OpenFlag.O_RDWR,))
    assert opened.success is True
    assert opened.handle is not None
    handle_id = opened.handle.handle_id
    generation = opened.handle.generation

    # Stage via handle table then flush through canonical authority.
    host.handles.write(handle_id, 0, b"Z", generation=generation)
    flushed = host.flush_handle(handle_id, generation=generation, commit=True)
    assert flushed.success is True
    assert flushed.observed_effect is True
    assert host.read("h.bin").data.startswith(b"Z")

    released = host.release_handle(handle_id, generation=generation)
    assert released.success is True
    # Idempotent release.
    again = host.release_handle(handle_id, generation=generation)
    assert again.success is True


def test_namespace_and_metadata_planes_are_wired(host: HostVFSService) -> None:
    assert host.namespace is not None
    assert host.metadata is not None
    assert host.handles is not None
    assert host.mkdir("wired").success
    meta = host.metadata("wired")
    assert meta.success is True
    # Stable inode allocated for the path.
    inode = host.namespace.inodes.get_by_path("wired")
    assert inode is not None
    assert inode.inode >= 1


def test_with_explicit_ranged_storage_injection() -> None:
    ranged = create_ranged_storage("memory", clock=lambda: 99)
    host = HostVFSService(ranged_storage=ranged, clock=lambda: 99)
    assert host.ranged_storage is ranged
    assert host.create("injected.txt", b"ok").success
    # Effect landed on the caller-provided ranged instance.
    assert any(e.path == "injected.txt" for e in ranged.effects())
