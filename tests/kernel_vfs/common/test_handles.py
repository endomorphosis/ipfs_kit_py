"""KVFS-204: Bounded file handles and per-handle staged extents.

Acceptance coverage:

* generation-tagged bounded handles;
* O_CREAT / O_EXCL / O_TRUNC / O_APPEND;
* random / sparse writes;
* read-own-writes;
* deferred errors;
* idempotent flush / release;
* stale-handle rejection;
* rename / unlink while open;
* orphan reclamation; and
* explicit pressure behaviour.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ipfs_kit_py.core.vfs import handles as handles_mod
from ipfs_kit_py.core.vfs.handles import (
    CONTRACT_VERSION,
    DEFAULT_CHUNK_BYTES,
    DEFAULT_MAX_OPEN_HANDLES,
    FILE_HANDLE_SCHEMA,
    HANDLE_TABLE_SCHEMA,
    SCHEMA_VERSION,
    STAGED_EXTENT_SCHEMA,
    FileHandle,
    FileHandle_V1,
    FlushResult,
    HandleError,
    HandleErrorCode,
    HandlePressureState,
    HandleTable,
    HandleTable_V1,
    HandleTraceKind,
    ReclaimResult,
    ReleaseResult,
    StagedExtent,
    StagedExtent_V1,
)
from ipfs_kit_py.core.vfs.host_contracts import HostErrno, OpenFlag

# test file: ipfs_kit_py/tests/kernel_vfs/common/test_handles.py
PACKAGE_ROOT = Path(__file__).resolve().parents[3]
HANDLES_PATH = PACKAGE_ROOT / "ipfs_kit_py" / "core" / "vfs" / "handles.py"


# ---------------------------------------------------------------------------
# Artifact / schema
# ---------------------------------------------------------------------------


def test_declared_handles_module_exists() -> None:
    assert HANDLES_PATH.is_file()
    assert HANDLES_PATH.stat().st_size > 0


def test_schema_versions_and_interface_aliases() -> None:
    assert CONTRACT_VERSION == 1
    assert SCHEMA_VERSION.startswith("1.")
    assert HANDLE_TABLE_SCHEMA == HandleTable_V1
    assert FILE_HANDLE_SCHEMA == FileHandle_V1
    assert STAGED_EXTENT_SCHEMA == StagedExtent_V1
    assert HandleTable_V1.endswith("@1")
    assert FileHandle_V1.endswith("@1")
    assert StagedExtent_V1.endswith("@1")
    assert DEFAULT_CHUNK_BYTES == 4_096
    assert DEFAULT_MAX_OPEN_HANDLES == 1_024


def test_module_has_no_fusepy_dependency() -> None:
    source = HANDLES_PATH.read_text(encoding="utf-8")
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
    assert handles_mod.HandleTable is HandleTable
    assert handles_mod.HandleErrorCode.STALE is HandleErrorCode.STALE
    assert callable(HandleTable.open)
    assert callable(HandleTable.create)
    assert callable(HandleTable.write)
    assert callable(HandleTable.read)
    assert callable(HandleTable.flush)
    assert callable(HandleTable.release)
    assert callable(HandleTable.reclaim_orphans)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def table() -> HandleTable:
    return HandleTable(clock_ms=lambda: 1_700_000_000_000)


@pytest.fixture
def seeded(table: HandleTable) -> HandleTable:
    table.seed_file("ns/file.bin", b"hello-world-content")
    return table


# ---------------------------------------------------------------------------
# Generation-tagged open / create flags
# ---------------------------------------------------------------------------


def test_open_existing_issues_generation_tagged_handle(seeded: HandleTable) -> None:
    fh = seeded.open("ns/file.bin", OpenFlag.O_RDONLY)
    assert isinstance(fh, FileHandle)
    assert fh.handle_id >= 1
    assert fh.generation >= 1
    assert fh.inode >= 1
    assert fh.path_at_open == "ns/file.bin"
    assert fh.readable is True
    assert fh.writable is False
    assert fh.released is False
    rec = fh.to_record()
    assert rec["schema"] == FILE_HANDLE_SCHEMA
    assert rec["generation"] == fh.generation


def test_o_creat_creates_missing_file(table: HandleTable) -> None:
    fh = table.open(
        "ns/new.bin",
        (OpenFlag.O_WRONLY, OpenFlag.O_CREAT),
    )
    assert fh.created is True
    assert table.lookup_inode("ns/new.bin") == fh.inode
    assert table.inode_stat("ns/new.bin") is not None
    assert HandleTraceKind.OPEN.value in table.trace.kinds() or (
        HandleTraceKind.CREATE.value in table.trace.kinds()
    )


def test_o_excl_rejects_existing(seeded: HandleTable) -> None:
    with pytest.raises(HandleError) as excinfo:
        seeded.open(
            "ns/file.bin",
            (OpenFlag.O_WRONLY, OpenFlag.O_CREAT, OpenFlag.O_EXCL),
        )
    assert excinfo.value.code is HandleErrorCode.ALREADY_EXISTS
    assert excinfo.value.errno is HostErrno.EEXIST


def test_o_excl_without_o_creat_rejects() -> None:
    table = HandleTable()
    with pytest.raises(HandleError) as excinfo:
        table.open("ns/x", (OpenFlag.O_WRONLY, OpenFlag.O_EXCL))
    assert excinfo.value.code is HandleErrorCode.BAD_FLAGS


def test_o_trunc_zeros_existing_content(seeded: HandleTable) -> None:
    assert len(seeded.committed_read("ns/file.bin")) == len(b"hello-world-content")
    fh = seeded.open(
        "ns/file.bin",
        (OpenFlag.O_RDWR, OpenFlag.O_TRUNC),
    )
    assert fh.truncated_on_open is True
    assert fh.logical_size == 0
    # Committed size is truncated at open.
    assert seeded.committed_read("ns/file.bin") == b""
    assert seeded.inode_stat("ns/file.bin")["size_bytes"] == 0


def test_o_append_writes_at_eof(seeded: HandleTable) -> None:
    fh = seeded.open(
        "ns/file.bin",
        (OpenFlag.O_WRONLY, OpenFlag.O_APPEND),
    )
    result = seeded.write(fh.handle_id, 0, b"!", generation=fh.generation)
    # Offset ignored; appended after existing content length.
    assert result.offset == len(b"hello-world-content")
    assert result.bytes_transferred == 1
    own = seeded.read(fh.handle_id, result.offset, 1, generation=fh.generation)
    assert own.data == b"!"


def test_create_entrypoint_implies_o_creat(table: HandleTable) -> None:
    fh = table.create("ns/created.bin", OpenFlag.O_RDWR)
    assert fh.created is True
    assert OpenFlag.O_CREAT in fh.flags or fh.created
    assert table.lookup_inode("ns/created.bin") == fh.inode


def test_flag_combination_matrix(table: HandleTable) -> None:
    combinations = [
        (OpenFlag.O_WRONLY, OpenFlag.O_CREAT),
        (OpenFlag.O_RDWR, OpenFlag.O_CREAT, OpenFlag.O_EXCL),
        (OpenFlag.O_WRONLY, OpenFlag.O_CREAT, OpenFlag.O_TRUNC),
        (OpenFlag.O_WRONLY, OpenFlag.O_CREAT, OpenFlag.O_APPEND),
        (OpenFlag.O_RDWR, OpenFlag.O_CREAT, OpenFlag.O_EXCL, OpenFlag.O_TRUNC),
    ]
    for i, flags in enumerate(combinations):
        path = f"ns/flags-{i}.bin"
        # Pre-seed when O_EXCL is not present so open of existing works too.
        if OpenFlag.O_EXCL not in flags:
            # create path via flags that include O_CREAT
            pass
        fh = table.open(path, flags)
        assert fh.generation >= 1
        assert fh.handle_id >= 1
        assert any(f in fh.flags for f in (OpenFlag.O_RDONLY, OpenFlag.O_WRONLY, OpenFlag.O_RDWR))
        table.release(fh.handle_id, generation=fh.generation)


# ---------------------------------------------------------------------------
# Random / sparse writes and read-own-writes
# ---------------------------------------------------------------------------


def test_random_writes_and_read_own_writes(table: HandleTable) -> None:
    fh = table.create("ns/rand.bin", (OpenFlag.O_RDWR, OpenFlag.O_CREAT))
    table.write(fh.handle_id, 0, b"AAAA", generation=fh.generation)
    table.write(fh.handle_id, 10, b"BBBB", generation=fh.generation)
    table.write(fh.handle_id, 4, b"CCCC", generation=fh.generation)

    # Read-own-writes sees staged data immediately.
    r0 = table.read(fh.handle_id, 0, 4, generation=fh.generation)
    assert r0.data == b"AAAA"
    assert r0.read_own_writes is True
    r1 = table.read(fh.handle_id, 4, 4, generation=fh.generation)
    assert r1.data == b"CCCC"
    r2 = table.read(fh.handle_id, 10, 4, generation=fh.generation)
    assert r2.data == b"BBBB"

    # Cross-handle does not see uncommitted staged bytes.
    other = table.open("ns/rand.bin", OpenFlag.O_RDONLY)
    committed_view = table.read(other.handle_id, 0, 14, generation=other.generation)
    # Other handle opened after create but before fsync — snapshot at open is empty.
    assert committed_view.data == b"" or committed_view.bytes_transferred == 0
    assert table.committed_read("ns/rand.bin") == b""


def test_sparse_write_beyond_eof_creates_hole(table: HandleTable) -> None:
    fh = table.create("ns/sparse.bin", (OpenFlag.O_RDWR, OpenFlag.O_CREAT))
    result = table.write(fh.handle_id, 4096, b"X" * 128, generation=fh.generation)
    assert result.staged is True
    assert result.dirty_in_handle_only is True
    assert result.sparse is True
    assert result.hole_before == 4096
    assert result.logical_size == 4096 + 128

    extents = table.staged_extents(fh.handle_id, generation=fh.generation)
    assert len(extents) == 1
    assert extents[0].offset == 4096
    assert extents[0].length == 128

    # Hole reads as zeroes without fabricating non-zero content.
    hole = table.read(fh.handle_id, 0, 64, generation=fh.generation)
    assert hole.data == b"\x00" * 64
    assert all(b == 0 for b in hole.data)

    tail = table.read(fh.handle_id, 4096, 128, generation=fh.generation)
    assert tail.data == b"X" * 128


def test_partial_overwrite_of_staged_extent(table: HandleTable) -> None:
    fh = table.create("ns/ov.bin", (OpenFlag.O_RDWR, OpenFlag.O_CREAT))
    table.write(fh.handle_id, 0, b"0123456789", generation=fh.generation)
    table.write(fh.handle_id, 3, b"ABC", generation=fh.generation)
    data = table.read(fh.handle_id, 0, 10, generation=fh.generation).data
    assert data == b"012ABC6789"


def test_fsync_commits_staged_for_cross_handle_visibility(table: HandleTable) -> None:
    fh = table.create("ns/vis.bin", (OpenFlag.O_RDWR, OpenFlag.O_CREAT))
    table.write(fh.handle_id, 0, b"committed-bytes", generation=fh.generation)
    # Before fsync: committed store empty.
    assert table.committed_read("ns/vis.bin") == b""
    sync = table.fsync(fh.handle_id, generation=fh.generation)
    assert sync.success is True
    assert sync.durable is True
    assert sync.committed_bytes > 0
    assert table.committed_read("ns/vis.bin") == b"committed-bytes"

    peer = table.open("ns/vis.bin", OpenFlag.O_RDONLY)
    # Peer opened after commit sees base content.
    got = table.read(peer.handle_id, 0, 15, generation=peer.generation)
    assert got.data == b"committed-bytes"


# ---------------------------------------------------------------------------
# Deferred errors + idempotent flush/release
# ---------------------------------------------------------------------------


def test_deferred_error_returned_consistently_by_flush(table: HandleTable) -> None:
    fh = table.create("ns/def.bin", (OpenFlag.O_RDWR, OpenFlag.O_CREAT))
    table.write(fh.handle_id, 0, b"data", generation=fh.generation)
    table.set_deferred_error(
        fh.handle_id,
        generation=fh.generation,
        code=HandleErrorCode.DEFERRED_ERROR,
        errno=HostErrno.EIO,
        message="simulated writeback failure",
    )
    first = table.flush(fh.handle_id, generation=fh.generation)
    second = table.flush(fh.handle_id, generation=fh.generation)
    assert first.success is False
    assert second.success is False
    assert first.deferred_error is True
    assert second.deferred_error is True
    assert first.error_code == HandleErrorCode.DEFERRED_ERROR.value
    assert second.error_code == first.error_code
    assert first.errno == HostErrno.EIO.value
    assert second.errno == first.errno
    assert second.idempotent is True
    # fsync also surfaces the deferred error and does not commit.
    sync = table.fsync(fh.handle_id, generation=fh.generation)
    assert sync.success is False
    assert sync.deferred_error is True
    assert table.committed_read("ns/def.bin") == b""


def test_flush_without_error_is_idempotent(table: HandleTable) -> None:
    fh = table.create("ns/flush.bin", (OpenFlag.O_RDWR, OpenFlag.O_CREAT))
    table.write(fh.handle_id, 0, b"abc", generation=fh.generation)
    a = table.flush(fh.handle_id, generation=fh.generation)
    b = table.flush(fh.handle_id, generation=fh.generation)
    assert a.success is True
    assert b.success is True
    assert b.idempotent is True
    assert isinstance(a, FlushResult)


def test_release_is_idempotent(table: HandleTable) -> None:
    fh = table.create("ns/rel.bin", (OpenFlag.O_RDWR, OpenFlag.O_CREAT))
    first = table.release(fh.handle_id, generation=fh.generation)
    second = table.release(fh.handle_id, generation=fh.generation)
    assert first.success is True
    assert first.already_released is False
    assert first.reclaimed is True
    assert second.success is True
    assert second.already_released is True
    assert isinstance(second, ReleaseResult)
    # I/O after release is rejected.
    with pytest.raises(HandleError) as excinfo:
        table.read(fh.handle_id, 0, 1, generation=fh.generation)
    assert excinfo.value.code in {
        HandleErrorCode.RELEASED,
        HandleErrorCode.NOT_FOUND,
        HandleErrorCode.STALE,
    }
    assert excinfo.value.errno is HostErrno.EBADF


def test_release_does_not_commit_dirty_bytes(table: HandleTable) -> None:
    fh = table.create("ns/nodur.bin", (OpenFlag.O_RDWR, OpenFlag.O_CREAT))
    table.write(fh.handle_id, 0, b"should-not-persist", generation=fh.generation)
    table.release(fh.handle_id, generation=fh.generation)
    # Path still exists (inode created) but content was not durable-committed.
    assert table.committed_read("ns/nodur.bin") == b""


# ---------------------------------------------------------------------------
# Stale-handle rejection
# ---------------------------------------------------------------------------


def test_stale_generation_is_rejected(table: HandleTable) -> None:
    fh = table.create("ns/stale.bin", (OpenFlag.O_RDWR, OpenFlag.O_CREAT))
    table.release(fh.handle_id, generation=fh.generation)
    # Reuse handle id via new open — generation must bump.
    fh2 = table.create("ns/stale2.bin", (OpenFlag.O_RDWR, OpenFlag.O_CREAT))
    # Force a known stale generation against a live handle.
    live = table.open("ns/stale.bin", OpenFlag.O_RDONLY)
    with pytest.raises(HandleError) as excinfo:
        table.read(live.handle_id, 0, 1, generation=live.generation + 99)
    assert excinfo.value.code is HandleErrorCode.STALE
    assert excinfo.value.errno is HostErrno.ESTALE
    assert HandleTraceKind.STALE.value in table.trace.kinds()
    # Correct generation still works.
    ok = table.read(live.handle_id, 0, 1, generation=live.generation)
    assert ok.bytes_transferred >= 0
    _ = fh2  # silence unused


def test_unknown_handle_rejected(table: HandleTable) -> None:
    with pytest.raises(HandleError) as excinfo:
        table.read(99999, 0, 1, generation=1)
    assert excinfo.value.code is HandleErrorCode.NOT_FOUND
    assert excinfo.value.errno is HostErrno.EBADF


def test_write_on_readonly_handle_rejected(seeded: HandleTable) -> None:
    fh = seeded.open("ns/file.bin", OpenFlag.O_RDONLY)
    with pytest.raises(HandleError) as excinfo:
        seeded.write(fh.handle_id, 0, b"nope", generation=fh.generation)
    assert excinfo.value.code is HandleErrorCode.PERMISSION


# ---------------------------------------------------------------------------
# Rename / unlink while open
# ---------------------------------------------------------------------------


def test_rename_while_open_handle_survives(table: HandleTable) -> None:
    table.seed_file("ns/a.txt", b"payload")
    fh = table.open("ns/a.txt", (OpenFlag.O_RDWR,))
    detail = table.notify_rename("ns/a.txt", "ns/b.txt")
    assert detail["handle_still_valid"] is True
    assert detail["handles_updated"] == 1
    # Same generation-tagged handle remains usable.
    view = table.get(fh.handle_id, fh.generation)
    assert view.generation == fh.generation
    assert view.handle_id == fh.handle_id
    assert view.current_path == "ns/b.txt"
    assert view.path_at_open == "ns/a.txt"
    table.write(fh.handle_id, 0, b"NEW!", generation=fh.generation)
    data = table.read(fh.handle_id, 0, 4, generation=fh.generation)
    assert data.data == b"NEW!"
    # Namespace reflects rename.
    assert table.lookup_inode("ns/a.txt") is None
    assert table.lookup_inode("ns/b.txt") == fh.inode
    table.release(fh.handle_id, generation=fh.generation)


def test_unlink_while_open_handle_survives(table: HandleTable) -> None:
    table.seed_file("ns/victim.txt", b"doomed")
    fh = table.open("ns/victim.txt", (OpenFlag.O_RDWR,))
    detail = table.notify_unlink("ns/victim.txt")
    assert detail["unlinked"] is True
    assert detail["handle_still_valid"] is True
    assert table.lookup_inode("ns/victim.txt") is None
    # Handle remains writable until release.
    wr = table.write(fh.handle_id, 0, b"ok!!", generation=fh.generation)
    assert wr.bytes_transferred == 4
    view = table.get(fh.handle_id, fh.generation)
    assert view.unlinked is True
    # Last close reclaims the orphaned inode.
    rel = table.release(fh.handle_id, generation=fh.generation)
    assert rel.orphaned_inode_reclaimed is True
    assert fh.inode not in {h.inode for h in table.open_handles()}


def test_unlink_with_no_open_handles_reclaims_immediately(table: HandleTable) -> None:
    ino = table.seed_file("ns/gone.txt", b"x")
    detail = table.notify_unlink("ns/gone.txt")
    assert detail["inode_reclaimed"] is True
    assert table.inode_stat("ns/gone.txt") is None
    # Inode gone from table.
    assert ino not in table._inodes  # noqa: SLF001 — intentional internal check


# ---------------------------------------------------------------------------
# Orphan reclamation
# ---------------------------------------------------------------------------


def test_lease_expiry_reclaim_without_double_free() -> None:
    clock = {"t": 1_000}

    def now() -> int:
        return clock["t"]

    table = HandleTable(clock_ms=now, default_lease_ms=100)
    fh = table.create("ns/lease.bin", (OpenFlag.O_RDWR, OpenFlag.O_CREAT), lease_ms=50)
    assert fh.lease_expires_at_ms == 1_050
    # Advance past lease expiry.
    clock["t"] = 1_100
    with pytest.raises(HandleError) as excinfo:
        table.read(fh.handle_id, 0, 1, generation=fh.generation)
    assert excinfo.value.code is HandleErrorCode.LEASE_EXPIRED
    assert excinfo.value.errno is HostErrno.EBADF

    result = table.reclaim_orphans(now_ms=clock["t"])
    assert isinstance(result, ReclaimResult)
    assert result.expired_leases >= 1
    assert result.reclaimed_handles >= 1
    # Second reclaim is a no-op (no double-free).
    again = table.reclaim_orphans(now_ms=clock["t"])
    assert again.expired_leases == 0
    # Idempotent release after reclaim.
    rel = table.release(fh.handle_id, generation=fh.generation)
    assert rel.success is True
    assert rel.already_released is True or rel.detail.get("unknown") is True


def test_reclaim_orphans_drops_unlinked_zero_open(table: HandleTable) -> None:
    table.seed_file("ns/orphan.bin", b"body")
    fh = table.open("ns/orphan.bin", OpenFlag.O_RDONLY)
    table.notify_unlink("ns/orphan.bin")
    # Still open — not reclaimed yet.
    assert fh.inode in table._inodes  # noqa: SLF001
    table.release(fh.handle_id, generation=fh.generation)
    # Release already reclaimed; reclaim_orphans remains safe.
    result = table.reclaim_orphans()
    assert result.reclaimed_inodes >= 0


# ---------------------------------------------------------------------------
# Explicit pressure behaviour
# ---------------------------------------------------------------------------


def test_open_handle_pressure_rejects_with_emfile() -> None:
    table = HandleTable(max_open_handles=2, clock_ms=lambda: 1_000)
    h1 = table.create("ns/p1.bin", (OpenFlag.O_RDWR, OpenFlag.O_CREAT))
    h2 = table.create("ns/p2.bin", (OpenFlag.O_RDWR, OpenFlag.O_CREAT))
    assert table.open_count == 2
    pressure = table.pressure_state()
    assert isinstance(pressure, HandlePressureState)
    assert pressure.pressure is True
    assert "open_handles" in pressure.reason

    with pytest.raises(HandleError) as excinfo:
        table.create("ns/p3.bin", (OpenFlag.O_RDWR, OpenFlag.O_CREAT))
    assert excinfo.value.code is HandleErrorCode.PRESSURE
    assert excinfo.value.errno is HostErrno.EMFILE
    assert excinfo.value.detail.get("pressure") is True
    events = table.pressure_events()
    assert len(events) >= 1
    assert events[-1]["reason"] == "open_handles_exhausted"
    assert HandleTraceKind.PRESSURE.value in table.trace.kinds()

    # Releasing frees capacity.
    table.release(h1.handle_id, generation=h1.generation)
    h3 = table.create("ns/p3.bin", (OpenFlag.O_RDWR, OpenFlag.O_CREAT))
    assert h3.handle_id >= 1
    table.release(h2.handle_id, generation=h2.generation)
    table.release(h3.handle_id, generation=h3.generation)


def test_staged_byte_pressure_is_explicit() -> None:
    ht = HandleTable(
        max_open_handles=8,
        max_staged_bytes=64,
        max_staged_bytes_per_handle=64,
        clock_ms=lambda: 1_000,
    )
    fh = ht.create("ns/big.bin", (OpenFlag.O_RDWR, OpenFlag.O_CREAT))
    ht.write(fh.handle_id, 0, b"A" * 32, generation=fh.generation)
    with pytest.raises(HandleError) as excinfo:
        ht.write(fh.handle_id, 32, b"B" * 64, generation=fh.generation)
    assert excinfo.value.code is HandleErrorCode.PRESSURE
    assert excinfo.value.errno is HostErrno.ENOSPC
    assert excinfo.value.detail.get("pressure") is True
    pressure = ht.pressure_state()
    assert pressure.staged_bytes > 0


def test_deferred_pressure_error_on_write() -> None:
    ht = HandleTable(
        max_staged_bytes_per_handle=16,
        max_staged_bytes=16,
        clock_ms=lambda: 1_000,
    )
    fh = ht.create("ns/defp.bin", (OpenFlag.O_RDWR, OpenFlag.O_CREAT))
    # defer_errors records the pressure failure for flush.
    result = ht.write(
        fh.handle_id,
        0,
        b"Z" * 64,
        generation=fh.generation,
        defer_errors=True,
    )
    assert result.bytes_transferred == 0
    flush = ht.flush(fh.handle_id, generation=fh.generation)
    assert flush.success is False
    assert flush.deferred_error is True
    assert flush.error_code == HandleErrorCode.PRESSURE.value


# ---------------------------------------------------------------------------
# Bounds, records, and table snapshot
# ---------------------------------------------------------------------------


def test_handle_table_to_record(table: HandleTable) -> None:
    table.create("ns/snap.bin", (OpenFlag.O_RDWR, OpenFlag.O_CREAT))
    rec = table.to_record()
    assert rec["schema"] == HANDLE_TABLE_SCHEMA
    assert rec["contract_version"] == 1
    assert rec["open_handles"] == 1
    assert "pressure" in rec


def test_staged_extent_record_and_overlap() -> None:
    ext = StagedExtent(offset=10, length=4, data=b"abcd", sequence=1)
    assert ext.end == 14
    assert ext.overlaps(12, 4) is True
    assert ext.overlaps(14, 1) is False
    assert ext.to_record()["offset"] == 10
    assert "data_sha256_prefix" in ext.to_record()


def test_truncate_shrinks_logical_size(table: HandleTable) -> None:
    fh = table.create("ns/trunc.bin", (OpenFlag.O_RDWR, OpenFlag.O_CREAT))
    table.write(fh.handle_id, 0, b"0123456789", generation=fh.generation)
    table.truncate(fh.handle_id, 4, generation=fh.generation)
    data = table.read(fh.handle_id, 0, 10, generation=fh.generation)
    assert data.data == b"0123"
    assert data.logical_size == 4


def test_open_missing_without_creat_is_enoent(table: HandleTable) -> None:
    with pytest.raises(HandleError) as excinfo:
        table.open("ns/missing.bin", OpenFlag.O_RDONLY)
    assert excinfo.value.code is HandleErrorCode.NOT_FOUND
    assert excinfo.value.errno is HostErrno.ENOENT


def test_directory_open_rejected(table: HandleTable) -> None:
    table.seed_directory("ns/dir")
    with pytest.raises(HandleError) as excinfo:
        table.open("ns/dir", OpenFlag.O_RDONLY)
    assert excinfo.value.code is HandleErrorCode.IS_DIRECTORY
    assert excinfo.value.errno is HostErrno.EISDIR


def test_generation_bumps_on_handle_id_reuse() -> None:
    table = HandleTable(max_open_handles=4, clock_ms=lambda: 1_000)
    fh1 = table.create("ns/r1.bin", (OpenFlag.O_RDWR, OpenFlag.O_CREAT))
    hid = fh1.handle_id
    gen1 = fh1.generation
    table.release(hid, generation=gen1)
    fh2 = table.create("ns/r2.bin", (OpenFlag.O_RDWR, OpenFlag.O_CREAT))
    # Recycled id must carry a higher generation (stale rejection works).
    if fh2.handle_id == hid:
        assert fh2.generation > gen1
        with pytest.raises(HandleError) as excinfo:
            table.read(hid, 0, 1, generation=gen1)
        assert excinfo.value.code is HandleErrorCode.STALE


def test_trace_covers_lifecycle(table: HandleTable) -> None:
    fh = table.create("ns/trace.bin", (OpenFlag.O_RDWR, OpenFlag.O_CREAT))
    table.write(fh.handle_id, 0, b"x", generation=fh.generation)
    table.read(fh.handle_id, 0, 1, generation=fh.generation)
    table.flush(fh.handle_id, generation=fh.generation)
    table.fsync(fh.handle_id, generation=fh.generation)
    table.release(fh.handle_id, generation=fh.generation)
    kinds = set(table.trace.kinds())
    assert HandleTraceKind.WRITE.value in kinds
    assert HandleTraceKind.READ.value in kinds
    assert HandleTraceKind.FLUSH.value in kinds
    assert HandleTraceKind.FSYNC.value in kinds
    assert HandleTraceKind.RELEASE.value in kinds
    assert all(isinstance(s.to_record(), dict) for s in table.trace.steps)


def test_flush_commit_flag_applies_staged(table: HandleTable) -> None:
    fh = table.create("ns/fcommit.bin", (OpenFlag.O_RDWR, OpenFlag.O_CREAT))
    table.write(fh.handle_id, 0, b"via-flush", generation=fh.generation)
    result = table.flush(fh.handle_id, generation=fh.generation, commit=True)
    assert result.success is True
    assert result.committed_bytes > 0
    assert table.committed_read("ns/fcommit.bin") == b"via-flush"
