"""KVFS-205: Offset I/O, sparse/partial write assembly, truncate, and append.

Acceptance coverage:

* offset reads load only requested ranges;
* overlapping / random / short writes;
* holes (sparse past-EOF);
* append serialization;
* grow / shrink truncate;
* zero length, EOF, large files;
* partial backend failures;
* reference-trace match without leaking dirty bytes.
"""

from __future__ import annotations

import ast
import threading
from pathlib import Path

import pytest

from ipfs_kit_py.core.vfs import io_runtime as io_mod
from ipfs_kit_py.core.vfs.host_contracts import HostErrno, OpenFlag
from ipfs_kit_py.core.vfs.io_runtime import (
    CONTRACT_VERSION,
    DEFAULT_CHUNK_BYTES,
    DIRTY_EXTENT_SCHEMA,
    IO_REFERENCE_MODEL_SCHEMA,
    OFFSET_IO_RUNTIME_SCHEMA,
    REFERENCE_IO_SCHEDULE,
    SCHEMA_VERSION,
    WHOLE_OBJECT_THRESHOLD_BYTES,
    DirtyExtent,
    DirtyExtent_V1,
    FlushAssemblyResult,
    InstrumentingStorage,
    IOError,
    IOErrorCode,
    IOReferenceModel_V1,
    IOResult,
    IOTraceKind,
    OffsetIOReferenceModel,
    OffsetIORuntime,
    OffsetIORuntime_V1,
    TruncateResult,
    build_reference_trace,
    ranges_cover_only_requested,
    traces_match,
)
from ipfs_kit_py.core.vfs.storage import (
    MemoryRangedStorage,
)

# test file: ipfs_kit_py/tests/kernel_vfs/common/test_offset_io.py
PACKAGE_ROOT = Path(__file__).resolve().parents[3]
IO_RUNTIME_PATH = PACKAGE_ROOT / "ipfs_kit_py" / "core" / "vfs" / "io_runtime.py"

LARGE_SIZE = WHOLE_OBJECT_THRESHOLD_BYTES + (256 * 1024)  # 1.25 MiB
PARTIAL_LENGTH = 4_096


# ---------------------------------------------------------------------------
# Artifact / schema / inertness
# ---------------------------------------------------------------------------


def test_declared_io_runtime_module_exists() -> None:
    assert IO_RUNTIME_PATH.is_file()
    assert IO_RUNTIME_PATH.stat().st_size > 0


def test_schema_versions_and_interface_aliases() -> None:
    assert CONTRACT_VERSION == 1
    assert SCHEMA_VERSION.startswith("1.")
    assert OFFSET_IO_RUNTIME_SCHEMA == OffsetIORuntime_V1
    assert IO_REFERENCE_MODEL_SCHEMA == IOReferenceModel_V1
    assert DIRTY_EXTENT_SCHEMA == DirtyExtent_V1
    assert OffsetIORuntime_V1.endswith("@1")
    assert DEFAULT_CHUNK_BYTES == 4_096
    assert WHOLE_OBJECT_THRESHOLD_BYTES == 1_048_576


def test_module_has_no_fusepy_dependency() -> None:
    source = IO_RUNTIME_PATH.read_text(encoding="utf-8")
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
    assert io_mod.OffsetIORuntime is OffsetIORuntime
    assert io_mod.OffsetIOReferenceModel is OffsetIOReferenceModel
    assert callable(OffsetIORuntime.open)
    assert callable(OffsetIORuntime.read)
    assert callable(OffsetIORuntime.write)
    assert callable(OffsetIORuntime.truncate)
    assert callable(OffsetIORuntime.flush)
    assert callable(OffsetIORuntime.release)
    assert callable(OffsetIORuntime.run_reference_trace_suite)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def runtime() -> OffsetIORuntime:
    return OffsetIORuntime(
        MemoryRangedStorage(clock=lambda: 1_700_000_000_000),
        clock_ms=lambda: 1_700_000_000_000,
    )


@pytest.fixture
def seeded(runtime: OffsetIORuntime) -> OffsetIORuntime:
    runtime.seed_file("ns/file.bin", b"hello-world-content")
    return runtime


# ---------------------------------------------------------------------------
# Offset reads without loading unrelated ranges
# ---------------------------------------------------------------------------


def test_offset_read_loads_only_requested_range(seeded: OffsetIORuntime) -> None:
    fh = seeded.open("ns/file.bin", OpenFlag.O_RDONLY)
    seeded.clear_loaded_ranges()
    result = seeded.read(fh.session_id, 6, 5, generation=fh.generation)
    assert isinstance(result, IOResult)
    assert result.data == b"world"
    assert result.bytes_transferred == 5
    assert result.ranges_loaded
    assert ranges_cover_only_requested(
        result.ranges_loaded,
        offset=6,
        length=5,
        chunk_bytes=seeded.chunk_bytes,
    )
    # No load of the head or tail beyond the chunk-aligned request window.
    for loff, llen in result.ranges_loaded:
        assert loff >= 0
        assert loff + llen <= len(b"hello-world-content")
        # Must not load the entire object for a short mid-file read.
        assert llen < len(b"hello-world-content")


def test_zero_length_read_and_write(runtime: OffsetIORuntime) -> None:
    fh = runtime.create("ns/z.bin", (OpenFlag.O_RDWR, OpenFlag.O_CREAT))
    wr = runtime.write(fh.session_id, 0, b"", generation=fh.generation)
    assert wr.zero_length is True
    assert wr.bytes_transferred == 0
    rd = runtime.read(fh.session_id, 0, 0, generation=fh.generation)
    assert rd.zero_length is True
    assert rd.data == b""
    assert rd.ranges_loaded == ()
    assert IOTraceKind.ZERO_LENGTH.value in runtime.trace.kinds()


def test_eof_short_read(seeded: OffsetIORuntime) -> None:
    fh = seeded.open("ns/file.bin", OpenFlag.O_RDONLY)
    past = seeded.read(fh.session_id, 10_000, 8, generation=fh.generation)
    assert past.eof is True
    assert past.bytes_transferred == 0
    assert past.data == b""
    assert past.ranges_loaded == ()

    short = seeded.read(fh.session_id, 14, 32, generation=fh.generation)
    # "hello-world-content" length 19; offset 14 → 5 bytes ("ntent").
    assert short.short_read is True
    assert short.data == b"ntent"
    assert short.bytes_transferred == 5
    assert IOTraceKind.EOF.value in seeded.trace.kinds()


# ---------------------------------------------------------------------------
# Overlapping / random / short writes + holes
# ---------------------------------------------------------------------------


def test_overlapping_random_short_writes_and_read_own_writes(
    runtime: OffsetIORuntime,
) -> None:
    fh = runtime.create("ns/rand.bin", (OpenFlag.O_RDWR, OpenFlag.O_CREAT))
    runtime.write(fh.session_id, 0, b"AAAA", generation=fh.generation)
    runtime.write(fh.session_id, 10, b"BBBB", generation=fh.generation)
    runtime.write(fh.session_id, 4, b"CC", generation=fh.generation)

    full = runtime.read(fh.session_id, 0, 14, generation=fh.generation)
    assert full.data[:4] == b"AAAA"
    assert full.data[4:6] == b"CC"
    assert full.data[10:14] == b"BBBB"
    # Hole between 6 and 10 is zeroes.
    assert full.data[6:10] == b"\x00" * 4
    assert full.read_own_writes is True
    assert full.dirty_in_session_only is True

    # Dirty must not be visible in committed backend yet.
    assert runtime.committed_read("ns/rand.bin") == b""


def test_sparse_write_beyond_eof_creates_hole(runtime: OffsetIORuntime) -> None:
    fh = runtime.create("ns/sparse.bin", (OpenFlag.O_RDWR, OpenFlag.O_CREAT))
    result = runtime.write(fh.session_id, 4096, b"X" * 128, generation=fh.generation)
    assert result.sparse is True
    assert result.hole_before == 4096
    assert result.logical_size == 4096 + 128
    assert result.dirty_in_session_only is True

    extents = runtime.dirty_extents(fh.session_id, generation=fh.generation)
    assert len(extents) == 1
    assert extents[0].offset == 4096
    assert extents[0].length == 128

    hole = runtime.read(fh.session_id, 0, 64, generation=fh.generation)
    assert hole.data == b"\x00" * 64
    tail = runtime.read(fh.session_id, 4096, 128, generation=fh.generation)
    assert tail.data == b"X" * 128
    assert IOTraceKind.HOLE.value in runtime.trace.kinds()


def test_partial_overwrite_of_dirty_extent(runtime: OffsetIORuntime) -> None:
    fh = runtime.create("ns/ov.bin", (OpenFlag.O_RDWR, OpenFlag.O_CREAT))
    runtime.write(fh.session_id, 0, b"0123456789", generation=fh.generation)
    runtime.write(fh.session_id, 3, b"ABC", generation=fh.generation)
    data = runtime.read(fh.session_id, 0, 10, generation=fh.generation).data
    assert data == b"012ABC6789"


# ---------------------------------------------------------------------------
# Append serialization
# ---------------------------------------------------------------------------


def test_o_append_ignores_offset_and_serializes(seeded: OffsetIORuntime) -> None:
    fh = seeded.open("ns/file.bin", (OpenFlag.O_WRONLY, OpenFlag.O_APPEND))
    r1 = seeded.write(fh.session_id, 0, b"!", generation=fh.generation)
    assert r1.offset == len(b"hello-world-content")
    r2 = seeded.write(fh.session_id, 9999, b"?", generation=fh.generation)
    assert r2.offset == len(b"hello-world-content") + 1
    assert IOTraceKind.APPEND.value in seeded.trace.kinds()

    # Read-own-writes via a second RDWR session would not see dirty; verify
    # through flush + committed read.
    flush = seeded.flush(fh.session_id, generation=fh.generation, commit=True)
    assert flush.success is True
    assert flush.dirty_leaked is False
    body = seeded.committed_read("ns/file.bin")
    assert body.endswith(b"!?")
    assert body.startswith(b"hello-world-content")


def test_concurrent_append_serialization(runtime: OffsetIORuntime) -> None:
    runtime.seed_file("ns/app.bin", b"BASE")
    fh = runtime.open("ns/app.bin", (OpenFlag.O_RDWR, OpenFlag.O_APPEND))
    errors: list[BaseException] = []
    results: list[IOResult] = []
    barrier = threading.Barrier(8)

    def worker(tag: bytes) -> None:
        try:
            barrier.wait(timeout=5)
            res = runtime.write(
                fh.session_id, 0, tag, generation=fh.generation
            )
            results.append(res)
        except BaseException as exc:  # noqa: BLE001 — collect for assertion
            errors.append(exc)

    threads = [
        threading.Thread(target=worker, args=(bytes([ord("A") + i]),))
        for i in range(8)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert not errors
    assert len(results) == 8
    offsets = sorted(r.offset for r in results)
    # Appends must be contiguous non-overlapping positions after BASE.
    assert offsets[0] == 4
    for i in range(1, 8):
        assert offsets[i] == offsets[i - 1] + 1
    runtime.flush(fh.session_id, generation=fh.generation, commit=True)
    body = runtime.committed_read("ns/app.bin")
    assert body.startswith(b"BASE")
    assert len(body) == 4 + 8
    # All eight distinct tags present exactly once.
    assert sorted(body[4:]) == list(range(ord("A"), ord("A") + 8))


# ---------------------------------------------------------------------------
# Truncate grow / shrink
# ---------------------------------------------------------------------------


def test_truncate_shrink_and_grow(runtime: OffsetIORuntime) -> None:
    fh = runtime.create("ns/trunc.bin", (OpenFlag.O_RDWR, OpenFlag.O_CREAT))
    runtime.write(fh.session_id, 0, b"0123456789", generation=fh.generation)
    shrink = runtime.truncate(fh.session_id, 4, generation=fh.generation)
    assert isinstance(shrink, TruncateResult)
    assert shrink.shrank is True
    assert shrink.grew is False
    assert shrink.size == 4
    data = runtime.read(fh.session_id, 0, 10, generation=fh.generation)
    assert data.data == b"0123"
    assert data.short_read is True

    grow = runtime.truncate(fh.session_id, 10, generation=fh.generation)
    assert grow.grew is True
    assert grow.size == 10
    data2 = runtime.read(fh.session_id, 0, 10, generation=fh.generation)
    assert data2.data == b"0123" + b"\x00" * 6


def test_truncate_zero(runtime: OffsetIORuntime) -> None:
    fh = runtime.create("ns/ztrunc.bin", (OpenFlag.O_RDWR, OpenFlag.O_CREAT))
    runtime.write(fh.session_id, 0, b"abc", generation=fh.generation)
    runtime.truncate(fh.session_id, 0, generation=fh.generation)
    data = runtime.read(fh.session_id, 0, 3, generation=fh.generation)
    assert data.data == b""
    assert data.eof is True


# ---------------------------------------------------------------------------
# Flush assembly / dirty isolation
# ---------------------------------------------------------------------------


def test_flush_assembles_partial_writes_without_leaking_dirty(
    runtime: OffsetIORuntime,
) -> None:
    fh = runtime.create("ns/asm.bin", (OpenFlag.O_RDWR, OpenFlag.O_CREAT))
    runtime.write(fh.session_id, 0, b"HEAD", generation=fh.generation)
    runtime.write(fh.session_id, 100, b"TAIL", generation=fh.generation)
    # Before flush: committed empty.
    assert runtime.committed_read("ns/asm.bin") == b""
    assert runtime.dirty_bytes > 0

    result = runtime.flush(fh.session_id, generation=fh.generation, commit=True)
    assert isinstance(result, FlushAssemblyResult)
    assert result.success is True
    assert result.dirty_leaked is False
    assert result.committed_bytes > 0
    assert result.ranges_written

    body = runtime.committed_read("ns/asm.bin", 0, 104)
    assert body[:4] == b"HEAD"
    assert body[100:104] == b"TAIL"
    assert body[4:100] == b"\x00" * 96
    # Dirty cleared after successful commit.
    assert runtime.dirty_bytes == 0
    assert runtime.dirty_extents(fh.session_id, generation=fh.generation) == ()


def test_release_discards_dirty_without_leak(runtime: OffsetIORuntime) -> None:
    fh = runtime.create("ns/discard.bin", (OpenFlag.O_RDWR, OpenFlag.O_CREAT))
    runtime.write(fh.session_id, 0, b"should-not-persist", generation=fh.generation)
    rel = runtime.release(fh.session_id, generation=fh.generation)
    assert rel["success"] is True
    assert rel["dirty_leaked"] is False
    assert runtime.committed_read("ns/discard.bin") == b""
    assert runtime.dirty_bytes == 0


# ---------------------------------------------------------------------------
# Large files
# ---------------------------------------------------------------------------


def test_large_file_partial_read_does_not_load_unrelated_ranges(
    runtime: OffsetIORuntime,
) -> None:
    pattern = b"KVFS-205-pattern-"
    runtime.seed_file(
        "large/blob.bin",
        size_bytes=LARGE_SIZE,
        pattern=pattern,
    )
    fh = runtime.open("large/blob.bin", OpenFlag.O_RDONLY)
    runtime.clear_loaded_ranges()
    offset = WHOLE_OBJECT_THRESHOLD_BYTES // 2
    result = runtime.read(
        fh.session_id, offset, PARTIAL_LENGTH, generation=fh.generation
    )
    assert len(result.data) == PARTIAL_LENGTH
    assert result.chunks_touched >= 1
    # Must not touch every chunk of the large object.
    storage_chunk = runtime.storage.chunk_bytes
    total_chunks = (LARGE_SIZE + storage_chunk - 1) // storage_chunk
    assert result.chunks_touched < total_chunks
    assert result.chunks_touched <= (PARTIAL_LENGTH // storage_chunk) + 2
    assert ranges_cover_only_requested(
        result.ranges_loaded,
        offset=offset,
        length=PARTIAL_LENGTH,
        chunk_bytes=runtime.chunk_bytes,
    )
    tiled = (pattern * ((offset + PARTIAL_LENGTH) // len(pattern) + 2))[
        offset : offset + PARTIAL_LENGTH
    ]
    assert result.data == tiled


def test_large_file_sparse_write_and_partial_flush(runtime: OffsetIORuntime) -> None:
    runtime.seed_file(
        "large/w.bin",
        size_bytes=LARGE_SIZE,
        pattern=b"L",
    )
    fh = runtime.open("large/w.bin", (OpenFlag.O_RDWR,))
    mid = LARGE_SIZE // 2
    runtime.write(fh.session_id, mid, b"PATCH", generation=fh.generation)
    # Dirty only — backend still has original mid bytes.
    before = runtime.committed_read("large/w.bin", mid, 5)
    assert before == b"L" * 5
    flush = runtime.flush(fh.session_id, generation=fh.generation, commit=True)
    assert flush.success is True
    assert flush.dirty_leaked is False
    # Only the patched range needed to be staged (not the whole 1.25 MiB as one
    # unrelated head/tail load on the write path).
    assert any(off == mid for off, _ in flush.ranges_written)
    after = runtime.committed_read("large/w.bin", mid, 5)
    assert after == b"PATCH"


# ---------------------------------------------------------------------------
# Partial backend failures
# ---------------------------------------------------------------------------


def test_partial_backend_failure_on_flush_retains_dirty_no_leak() -> None:
    backend = MemoryRangedStorage(clock=lambda: 1)
    instr = InstrumentingStorage(backend, fail_commit_after=0)
    runtime = OffsetIORuntime(instr, instrument=False, clock_ms=lambda: 1)
    # fail_commit_after=0 means first commit fails (commits counter > 0).
    # seed_file may not commit via staged write — seed is direct.
    # Create via open+write then flush.
    fh = runtime.create("ns/fail.bin", (OpenFlag.O_RDWR, OpenFlag.O_CREAT))
    # create seeds empty via seed_file — no staged commit.
    runtime.write(fh.session_id, 0, b"dirty-bytes", generation=fh.generation)
    assert runtime.dirty_bytes > 0

    # Force commit failures: configure after create so seed is fine.
    instr.configure_failures(fail_commit_after=0)
    result = runtime.flush(fh.session_id, generation=fh.generation, commit=True)
    assert result.success is False
    assert result.deferred_error is True
    assert result.error_code == IOErrorCode.PARTIAL_FAILURE.value
    assert result.dirty_leaked is False
    # Dirty retained in session.
    assert runtime.dirty_bytes > 0
    extents = runtime.dirty_extents(fh.session_id, generation=fh.generation)
    assert extents
    # Backend must not have received the dirty payload.
    committed = runtime.committed_read("ns/fail.bin")
    assert b"dirty-bytes" not in committed
    assert IOTraceKind.PARTIAL_FAILURE.value in runtime.trace.kinds()


def test_partial_backend_failure_on_range_read() -> None:
    backend = MemoryRangedStorage(clock=lambda: 1)
    backend.seed_file("ns/rfail.bin", data=b"ABCDEFGH")
    instr = InstrumentingStorage(backend, fail_range_read_after=0)
    runtime = OffsetIORuntime(instr, instrument=False, clock_ms=lambda: 1)
    fh = runtime.open("ns/rfail.bin", OpenFlag.O_RDONLY)
    with pytest.raises(IOError) as excinfo:
        runtime.read(fh.session_id, 0, 4, generation=fh.generation)
    assert excinfo.value.code is IOErrorCode.PARTIAL_FAILURE
    assert excinfo.value.errno is HostErrno.EIO
    assert IOTraceKind.PARTIAL_FAILURE.value in runtime.trace.kinds()


def test_stage_write_failure_aborts_without_leak() -> None:
    backend = MemoryRangedStorage(clock=lambda: 1)
    instr = InstrumentingStorage(backend, fail_stage_write_after=0)
    runtime = OffsetIORuntime(instr, instrument=False, clock_ms=lambda: 1)
    fh = runtime.create("ns/swfail.bin", (OpenFlag.O_RDWR, OpenFlag.O_CREAT))
    runtime.write(fh.session_id, 0, b"payload", generation=fh.generation)
    instr.configure_failures(fail_stage_write_after=0)
    result = runtime.flush(fh.session_id, generation=fh.generation, commit=True)
    assert result.success is False
    assert result.dirty_leaked is False
    assert runtime.dirty_bytes > 0
    assert runtime.committed_read("ns/swfail.bin") == b""


# ---------------------------------------------------------------------------
# Reference trace match
# ---------------------------------------------------------------------------


def test_runtime_matches_reference_trace() -> None:
    runtime = OffsetIORuntime(
        MemoryRangedStorage(clock=lambda: 42),
        clock_ms=lambda: 42,
    )
    ref = OffsetIOReferenceModel()
    left = runtime.run_reference_trace_suite()
    right = ref.run_reference_trace_suite()
    assert left, "runtime produced empty trace"
    assert right, "reference produced empty trace"
    assert traces_match(left, right), (
        f"trace mismatch at first difference:\n"
        f" runtime len={len(left)} ref len={len(right)}\n"
        f" runtime={left[:8]!r}\n"
        f" ref={right[:8]!r}"
    )


def test_build_reference_trace_is_stable() -> None:
    a = build_reference_trace()
    b = build_reference_trace()
    assert traces_match(a, b)
    assert len(a) == len(REFERENCE_IO_SCHEDULE) or len(a) > len(REFERENCE_IO_SCHEDULE) // 2


def test_reference_schedule_covers_required_kinds() -> None:
    runtime = OffsetIORuntime(
        MemoryRangedStorage(clock=lambda: 1),
        clock_ms=lambda: 1,
    )
    runtime.run_reference_trace_suite()
    kinds = set(runtime.trace.kinds())
    required = {
        IOTraceKind.SEED.value,
        IOTraceKind.OPEN.value,
        IOTraceKind.READ.value,
        IOTraceKind.WRITE.value,
        IOTraceKind.TRUNCATE.value,
        IOTraceKind.FLUSH.value,
        IOTraceKind.RELEASE.value,
        IOTraceKind.APPEND.value,
        IOTraceKind.HOLE.value,
        IOTraceKind.ZERO_LENGTH.value,
        IOTraceKind.EOF.value,
        IOTraceKind.ASSEMBLE.value,
    }
    missing = required - kinds
    assert not missing, f"missing trace kinds: {missing}"


# ---------------------------------------------------------------------------
# Records / bounds / stale
# ---------------------------------------------------------------------------


def test_dirty_extent_record_and_overlap() -> None:
    ext = DirtyExtent(offset=10, length=4, data=b"abcd", sequence=1)
    assert ext.end == 14
    assert ext.overlaps(12, 4) is True
    assert ext.overlaps(14, 1) is False
    rec = ext.to_record()
    assert rec["offset"] == 10
    assert "data_sha256_prefix" in rec


def test_stale_and_released_session_rejected(runtime: OffsetIORuntime) -> None:
    fh = runtime.create("ns/stale.bin", (OpenFlag.O_RDWR, OpenFlag.O_CREAT))
    runtime.release(fh.session_id, generation=fh.generation)
    with pytest.raises(IOError) as excinfo:
        runtime.read(fh.session_id, 0, 1, generation=fh.generation)
    assert excinfo.value.code in {IOErrorCode.RELEASED, IOErrorCode.NOT_OPEN}

    live = runtime.create("ns/live.bin", (OpenFlag.O_RDWR, OpenFlag.O_CREAT))
    with pytest.raises(IOError) as excinfo:
        runtime.read(live.session_id, 0, 1, generation=live.generation + 99)
    assert excinfo.value.code is IOErrorCode.STALE
    assert excinfo.value.errno is HostErrno.ESTALE


def test_write_on_readonly_rejected(seeded: OffsetIORuntime) -> None:
    fh = seeded.open("ns/file.bin", OpenFlag.O_RDONLY)
    with pytest.raises(IOError) as excinfo:
        seeded.write(fh.session_id, 0, b"nope", generation=fh.generation)
    assert excinfo.value.code is IOErrorCode.PERMISSION


def test_runtime_to_record(runtime: OffsetIORuntime) -> None:
    runtime.create("ns/snap.bin", (OpenFlag.O_RDWR, OpenFlag.O_CREAT))
    rec = runtime.to_record()
    assert rec["schema"] == OFFSET_IO_RUNTIME_SCHEMA
    assert rec["contract_version"] == 1
    assert rec["open_sessions"] == 1
    assert "trace" in rec


def test_o_trunc_on_open(seeded: OffsetIORuntime) -> None:
    fh = seeded.open("ns/file.bin", (OpenFlag.O_RDWR, OpenFlag.O_TRUNC))
    assert fh.logical_size == 0
    assert seeded.committed_read("ns/file.bin") == b""
