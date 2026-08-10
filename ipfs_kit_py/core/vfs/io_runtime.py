"""Offset I/O runtime: sparse/partial write assembly, truncate, and append (KVFS-205).

This module owns the *data-plane assembly* for kernel-shaped file I/O:

* offset reads that load only the requested ranges from ranged storage;
* overlapping / random / short / sparse write assembly into dirty extents;
* holes (sparse past-EOF writes) that read as zeroes without materialising;
* ``O_APPEND`` serialization so concurrent appends never interleave bytes;
* grow / shrink truncate, zero-length I/O, and EOF short reads;
* large-file partial I/O without whole-object loading;
* partial backend failures that never leak dirty bytes into committed storage;
* an executable reference trace that the runtime must match exactly.

Dirty extents live only in per-session staging. Shared ARC admission and WAL
durability remain out of scope (KVFS-300 / KVFS-400). This module does not
import fusepy, open host mounts, or perform network I/O.

Interfaces (plan aliases): ``OffsetIORuntime@1``, ``IOReferenceModel@1``,
``DirtyExtent@1``.
"""

from __future__ import annotations

import hashlib
import threading
import time
from collections.abc import Mapping, MutableMapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, ClassVar, Final, Protocol, runtime_checkable

from ipfs_kit_py.core.vfs.contracts import VFSEntryKind
from ipfs_kit_py.core.vfs.host_contracts import (
    MAX_IO_LENGTH,
    MAX_OFFSET,
    MAX_SIZE_BYTES,
    HostErrno,
    OpenFlag,
)
from ipfs_kit_py.core.vfs.storage import (
    DEFAULT_CHUNK_BYTES as STORAGE_DEFAULT_CHUNK_BYTES,
)
from ipfs_kit_py.core.vfs.storage import (
    WHOLE_OBJECT_THRESHOLD_BYTES,
    MemoryRangedStorage,
    RangeReadResult,
    RangedStorageError,
    RangedVFSStorageBoundary,
    StageHandle,
    StorageErrorCode,
    StorageStat,
)

# ---------------------------------------------------------------------------
# Schema / version / bounds
# ---------------------------------------------------------------------------

CONTRACT_VERSION: Final[int] = 1
SCHEMA_MAJOR: Final[int] = 1
SCHEMA_MINOR: Final[int] = 0
SCHEMA_PATCH: Final[int] = 0
SCHEMA_VERSION: Final[str] = f"{SCHEMA_MAJOR}.{SCHEMA_MINOR}.{SCHEMA_PATCH}"

IO_RUNTIME_MODULE_NAMESPACE: Final[str] = "ipfs_kit_py/core/vfs/io_runtime"

OFFSET_IO_RUNTIME_SCHEMA: Final[str] = (
    f"{IO_RUNTIME_MODULE_NAMESPACE}/offset-io-runtime@{SCHEMA_MAJOR}"
)
IO_REFERENCE_MODEL_SCHEMA: Final[str] = (
    f"{IO_RUNTIME_MODULE_NAMESPACE}/io-reference-model@{SCHEMA_MAJOR}"
)
DIRTY_EXTENT_SCHEMA: Final[str] = (
    f"{IO_RUNTIME_MODULE_NAMESPACE}/dirty-extent@{SCHEMA_MAJOR}"
)
IO_TRACE_SCHEMA: Final[str] = (
    f"{IO_RUNTIME_MODULE_NAMESPACE}/io-trace@{SCHEMA_MAJOR}"
)
IO_SESSION_SCHEMA: Final[str] = (
    f"{IO_RUNTIME_MODULE_NAMESPACE}/io-session@{SCHEMA_MAJOR}"
)

# Public interface aliases.
OffsetIORuntime_V1: Final[str] = OFFSET_IO_RUNTIME_SCHEMA
IOReferenceModel_V1: Final[str] = IO_REFERENCE_MODEL_SCHEMA
DirtyExtent_V1: Final[str] = DIRTY_EXTENT_SCHEMA

DEFAULT_CHUNK_BYTES: Final[int] = 4_096
DEFAULT_MAX_OPEN_SESSIONS: Final[int] = 1_024
DEFAULT_MAX_DIRTY_BYTES: Final[int] = 64 * 1024 * 1024
DEFAULT_MAX_DIRTY_BYTES_PER_SESSION: Final[int] = 16 * 1024 * 1024
DEFAULT_MAX_EXTENTS_PER_SESSION: Final[int] = 4_096
MAX_TRACE_STEPS: Final[int] = 8_192
MAX_OPEN_SESSIONS_HARD: Final[int] = 65_536
MIN_SESSION_ID: Final[int] = 1

# Schedule op names for the closed reference-trace vocabulary.
TRACE_OP_SEED = "seed"
TRACE_OP_OPEN = "open"
TRACE_OP_READ = "read"
TRACE_OP_WRITE = "write"
TRACE_OP_TRUNCATE = "truncate"
TRACE_OP_FLUSH = "flush"
TRACE_OP_RELEASE = "release"
TRACE_OP_STAT = "stat"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class IOErrorCode(str, Enum):
    """Stable offset-I/O data-plane error codes."""

    NOT_FOUND = "IO_NOT_FOUND"
    ALREADY_EXISTS = "IO_ALREADY_EXISTS"
    IS_DIRECTORY = "IO_IS_DIRECTORY"
    BAD_FLAGS = "IO_BAD_FLAGS"
    PERMISSION = "IO_PERMISSION"
    INVALID_OFFSET = "IO_INVALID_OFFSET"
    INVALID_LENGTH = "IO_INVALID_LENGTH"
    INVALID_SIZE = "IO_INVALID_SIZE"
    BOUND_EXCEEDED = "IO_BOUND_EXCEEDED"
    STALE = "IO_STALE"
    RELEASED = "IO_RELEASED"
    NOT_OPEN = "IO_NOT_OPEN"
    BACKEND = "IO_BACKEND"
    PARTIAL_FAILURE = "IO_PARTIAL_FAILURE"
    DEFERRED = "IO_DEFERRED"
    PRESSURE = "IO_PRESSURE"
    INTERNAL = "IO_INTERNAL"


class IOError(Exception):
    """Fail-closed offset-I/O error with stable code and optional errno."""

    def __init__(
        self,
        message: str,
        *,
        code: IOErrorCode,
        errno: HostErrno = HostErrno.EINVAL,
        session_id: int = 0,
        generation: int = 0,
        path: str = "",
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code if isinstance(code, IOErrorCode) else IOErrorCode(code)
        self.errno = errno if isinstance(errno, HostErrno) else HostErrno(errno)
        self.session_id = int(session_id)
        self.generation = int(generation)
        self.path = path
        self.detail = dict(detail or {})

    def to_record(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "message": self.message,
            "errno": self.errno.value,
            "session_id": self.session_id,
            "generation": self.generation,
            "path": self.path,
            "detail": dict(self.detail),
        }


# ---------------------------------------------------------------------------
# Trace
# ---------------------------------------------------------------------------


class IOTraceKind(str, Enum):
    """Executable offset-I/O trace step kinds."""

    SEED = "seed"
    OPEN = "open"
    CREATE = "create"
    READ = "read"
    WRITE = "write"
    TRUNCATE = "truncate"
    FLUSH = "flush"
    RELEASE = "release"
    APPEND = "append"
    ASSEMBLE = "assemble"
    BACKEND_LOAD = "backend_load"
    BACKEND_COMMIT = "backend_commit"
    HOLE = "hole"
    EOF = "eof"
    ZERO_LENGTH = "zero_length"
    PARTIAL_FAILURE = "partial_failure"
    DEFERRED = "deferred"
    STAT = "stat"
    OBSERVATION = "observation"


@dataclass(frozen=True)
class IOTraceStep:
    """One immutable, executable offset-I/O trace step."""

    SCHEMA: ClassVar[str] = IO_TRACE_SCHEMA

    kind: IOTraceKind
    success: bool
    session_id: int = 0
    generation: int = 0
    path: str = ""
    code: str = ""
    detail: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.kind, IOTraceKind):
            object.__setattr__(self, "kind", IOTraceKind(self.kind))
        if not isinstance(self.success, bool):
            raise IOError(
                "trace step success must be a boolean",
                code=IOErrorCode.INTERNAL,
            )
        object.__setattr__(self, "detail", dict(self.detail or {}))

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "kind": self.kind.value,
            "success": self.success,
            "session_id": self.session_id,
            "generation": self.generation,
            "path": self.path,
            "code": self.code,
            "detail": dict(self.detail),
        }

    def canonical(self) -> dict[str, Any]:
        """Canonical form used for reference-trace equality."""

        return {
            "kind": self.kind.value,
            "success": self.success,
            "path": self.path,
            "code": self.code,
            "detail": _canonical_detail(self.detail),
        }


def _canonical_detail(detail: Mapping[str, Any]) -> dict[str, Any]:
    """Project detail keys that participate in reference-trace matching."""

    # Exclude non-deterministic / implementation-private fields.
    skip = {
        "backend_id",
        "stage_id",
        "effect_id",
        "content_cid",
        "version_cid",
        "at_ms",
        "lease_id",
        "session_id",
        "generation",
        "handle_id",
    }
    out: dict[str, Any] = {}
    for key in sorted(detail):
        if key in skip:
            continue
        value = detail[key]
        if isinstance(value, bytes):
            out[key] = {
                "encoding": "sha256_prefix",
                "sha256_prefix": _sha256_prefix(value),
                "length": len(value),
            }
        elif isinstance(value, Mapping):
            out[key] = _canonical_detail(value)
        elif isinstance(value, (list, tuple)):
            out[key] = [
                _canonical_detail(v) if isinstance(v, Mapping) else v for v in value
            ]
        else:
            out[key] = value
    return out


class IOTraceLog:
    """Bounded append-only trace log for offset-I/O evidence."""

    __slots__ = ("_steps", "_max_steps")

    def __init__(self, *, max_steps: int = MAX_TRACE_STEPS) -> None:
        if max_steps < 1 or max_steps > MAX_TRACE_STEPS:
            raise IOError(
                f"max_steps must be in [1, {MAX_TRACE_STEPS}]",
                code=IOErrorCode.INTERNAL,
            )
        self._steps: list[IOTraceStep] = []
        self._max_steps = max_steps

    def append(self, step: IOTraceStep) -> IOTraceStep:
        if len(self._steps) >= self._max_steps:
            del self._steps[0]
        self._steps.append(step)
        return step

    def record(
        self,
        kind: IOTraceKind,
        *,
        success: bool,
        session_id: int = 0,
        generation: int = 0,
        path: str = "",
        code: str = "",
        detail: Mapping[str, Any] | None = None,
    ) -> IOTraceStep:
        return self.append(
            IOTraceStep(
                kind=kind,
                success=success,
                session_id=session_id,
                generation=generation,
                path=path,
                code=code,
                detail=dict(detail or {}),
            )
        )

    def clear(self) -> None:
        self._steps.clear()

    @property
    def steps(self) -> tuple[IOTraceStep, ...]:
        return tuple(self._steps)

    def to_records(self) -> list[dict[str, Any]]:
        return [step.to_record() for step in self._steps]

    def canonical_records(self) -> list[dict[str, Any]]:
        return [step.canonical() for step in self._steps]

    def kinds(self) -> list[str]:
        return [step.kind.value for step in self._steps]


# ---------------------------------------------------------------------------
# Public records
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DirtyExtent:
    """One dirty byte range staged on a single open I/O session.

    Holes are represented by absence of dirty coverage within the logical size;
    sparse writes past EOF extend size without materialising intermediate
    bytes until read (zero-fill).
    """

    SCHEMA: ClassVar[str] = DIRTY_EXTENT_SCHEMA

    offset: int
    length: int
    data: bytes
    sequence: int = 0

    def __post_init__(self) -> None:
        if isinstance(self.offset, bool) or not isinstance(self.offset, int) or self.offset < 0:
            raise IOError(
                "dirty extent offset must be a non-negative integer",
                code=IOErrorCode.INVALID_OFFSET,
            )
        if self.offset > MAX_OFFSET:
            raise IOError(
                "dirty extent offset exceeds bound",
                code=IOErrorCode.BOUND_EXCEEDED,
            )
        if not isinstance(self.data, (bytes, bytearray)):
            raise IOError(
                "dirty extent data must be bytes",
                code=IOErrorCode.INTERNAL,
            )
        payload = bytes(self.data)
        if len(payload) != self.length:
            object.__setattr__(self, "length", len(payload))
        else:
            object.__setattr__(self, "length", int(self.length))
        object.__setattr__(self, "data", payload)
        if self.length > MAX_IO_LENGTH:
            raise IOError(
                "dirty extent length exceeds I/O bound",
                code=IOErrorCode.BOUND_EXCEEDED,
            )
        object.__setattr__(self, "sequence", int(self.sequence))

    @property
    def end(self) -> int:
        return self.offset + self.length

    def overlaps(self, offset: int, length: int) -> bool:
        if length <= 0:
            return False
        other_end = offset + length
        return self.offset < other_end and offset < self.end

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "offset": self.offset,
            "length": self.length,
            "sequence": self.sequence,
            "data_sha256_prefix": _sha256_prefix(self.data),
        }


@dataclass(frozen=True)
class IOSession:
    """Generation-tagged open I/O session identity (immutable view)."""

    SCHEMA: ClassVar[str] = IO_SESSION_SCHEMA

    session_id: int
    generation: int
    path: str
    flags: tuple[OpenFlag, ...]
    append: bool = False
    readable: bool = True
    writable: bool = False
    released: bool = False
    dirty_bytes: int = 0
    logical_size: int = 0
    deferred_error_code: str = ""

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "session_id": self.session_id,
            "generation": self.generation,
            "path": self.path,
            "flags": [f.value for f in self.flags],
            "append": self.append,
            "readable": self.readable,
            "writable": self.writable,
            "released": self.released,
            "dirty_bytes": self.dirty_bytes,
            "logical_size": self.logical_size,
            "deferred_error_code": self.deferred_error_code,
        }


@dataclass(frozen=True)
class IOResult:
    """Result of a read or write against a live I/O session."""

    session_id: int
    generation: int
    offset: int
    length: int
    bytes_transferred: int
    data: bytes = b""
    logical_size: int = 0
    staged: bool = False
    sparse: bool = False
    hole_before: int = 0
    dirty_in_session_only: bool = False
    read_own_writes: bool = False
    ranges_loaded: tuple[tuple[int, int], ...] = ()
    chunks_touched: int = 0
    eof: bool = False
    zero_length: bool = False
    short_read: bool = False

    def to_record(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "generation": self.generation,
            "offset": self.offset,
            "length": self.length,
            "bytes_transferred": self.bytes_transferred,
            "logical_size": self.logical_size,
            "staged": self.staged,
            "sparse": self.sparse,
            "hole_before": self.hole_before,
            "dirty_in_session_only": self.dirty_in_session_only,
            "read_own_writes": self.read_own_writes,
            "ranges_loaded": [list(r) for r in self.ranges_loaded],
            "chunks_touched": self.chunks_touched,
            "eof": self.eof,
            "zero_length": self.zero_length,
            "short_read": self.short_read,
            "data_len": len(self.data),
        }


@dataclass(frozen=True)
class TruncateResult:
    """Result of a truncate against a live I/O session."""

    session_id: int
    generation: int
    size: int
    previous_size: int
    grew: bool
    shrank: bool
    dirty_in_session_only: bool = True

    def to_record(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "generation": self.generation,
            "size": self.size,
            "previous_size": self.previous_size,
            "grew": self.grew,
            "shrank": self.shrank,
            "dirty_in_session_only": self.dirty_in_session_only,
        }


@dataclass(frozen=True)
class FlushAssemblyResult:
    """Result of assembling dirty extents into a backend staged write."""

    session_id: int
    generation: int
    success: bool
    committed_bytes: int = 0
    extents_assembled: int = 0
    ranges_written: tuple[tuple[int, int], ...] = ()
    deferred_error: bool = False
    error_code: str = ""
    errno: str = HostErrno.OK.value
    dirty_leaked: bool = False
    durable: bool = False
    detail: Mapping[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "generation": self.generation,
            "success": self.success,
            "committed_bytes": self.committed_bytes,
            "extents_assembled": self.extents_assembled,
            "ranges_written": [list(r) for r in self.ranges_written],
            "deferred_error": self.deferred_error,
            "error_code": self.error_code,
            "errno": self.errno,
            "dirty_leaked": self.dirty_leaked,
            "durable": self.durable,
            "detail": dict(self.detail),
        }


@dataclass(frozen=True)
class LoadedRange:
    """One backend range load observation."""

    path: str
    offset: int
    length: int
    chunks_touched: int

    def to_record(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "offset": self.offset,
            "length": self.length,
            "chunks_touched": self.chunks_touched,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256_prefix(data: bytes, *, n: int = 16) -> str:
    return hashlib.sha256(data).hexdigest()[:n]


def _require_non_negative_int(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise IOError(
            f"{name} must be a non-negative integer",
            code=IOErrorCode.INVALID_OFFSET if name == "offset" else IOErrorCode.INVALID_LENGTH,
            detail={"field": name, "value": value},
        )
    return value


def _chunk_index(offset: int, chunk_bytes: int) -> int:
    return offset // chunk_bytes


def _chunk_span(offset: int, length: int, chunk_bytes: int) -> tuple[int, int]:
    if length <= 0:
        return (0, -1)
    first = _chunk_index(offset, chunk_bytes)
    last = _chunk_index(offset + length - 1, chunk_bytes)
    return first, last


def _write_into_chunks(
    chunks: MutableMapping[int, bytes],
    *,
    size_bytes: int,
    offset: int,
    data: bytes,
    chunk_bytes: int,
) -> int:
    if not data:
        return max(size_bytes, offset)
    end = offset + len(data)
    first, last = _chunk_span(offset, len(data), chunk_bytes)
    for index in range(first, last + 1):
        chunk_start = index * chunk_bytes
        chunk_end = chunk_start + chunk_bytes
        rel_start = max(offset, chunk_start) - chunk_start
        rel_end = min(end, chunk_end) - chunk_start
        src_start = max(offset, chunk_start) - offset
        src_end = src_start + (rel_end - rel_start)
        existing = chunks.get(index)
        if existing is None:
            buf = bytearray(chunk_bytes)
        else:
            buf = bytearray(existing)
            if len(buf) < chunk_bytes:
                buf.extend(b"\x00" * (chunk_bytes - len(buf)))
        buf[rel_start:rel_end] = data[src_start:src_end]
        chunks[index] = bytes(buf)
    return max(size_bytes, end)


def _read_from_chunks(
    chunks: Mapping[int, bytes],
    *,
    size_bytes: int,
    offset: int,
    length: int,
    chunk_bytes: int,
) -> tuple[bytes, int]:
    if offset >= size_bytes or length <= 0:
        return b"", 0
    end = min(size_bytes, offset + length)
    need = end - offset
    first, last = _chunk_span(offset, need, chunk_bytes)
    out = bytearray()
    touched = 0
    for index in range(first, last + 1):
        chunk_start = index * chunk_bytes
        chunk_end = chunk_start + chunk_bytes
        rel_start = max(offset, chunk_start) - chunk_start
        rel_end = min(end, chunk_end) - chunk_start
        existing = chunks.get(index)
        touched += 1
        if existing is None:
            out.extend(b"\x00" * (rel_end - rel_start))
            continue
        piece = existing[rel_start:rel_end]
        if len(piece) < (rel_end - rel_start):
            piece = piece + b"\x00" * ((rel_end - rel_start) - len(piece))
        out.extend(piece)
    return bytes(out), touched


def _trim_chunks_to_size(
    chunks: MutableMapping[int, bytes],
    *,
    size_bytes: int,
    chunk_bytes: int,
) -> None:
    if size_bytes <= 0:
        chunks.clear()
        return
    last_index = _chunk_index(size_bytes - 1, chunk_bytes)
    for key in list(chunks):
        if key > last_index:
            del chunks[key]
    last_live = size_bytes - last_index * chunk_bytes
    if last_index in chunks:
        chunks[last_index] = chunks[last_index][:last_live]


def _normalize_flags(flags: OpenFlag | Sequence[OpenFlag] | int) -> tuple[OpenFlag, ...]:
    if isinstance(flags, OpenFlag):
        return (flags,)
    if isinstance(flags, int) and not isinstance(flags, bool):
        # Accept raw bitmasks by matching known flag values when possible.
        matched = [f for f in OpenFlag if f.value & flags]
        if not matched:
            raise IOError(
                "unrecognized open flags",
                code=IOErrorCode.BAD_FLAGS,
                errno=HostErrno.EINVAL,
            )
        return tuple(matched)
    if isinstance(flags, Sequence) and not isinstance(flags, (str, bytes)):
        out: list[OpenFlag] = []
        for item in flags:
            if isinstance(item, OpenFlag):
                out.append(item)
            else:
                raise IOError(
                    "open flags must be OpenFlag values",
                    code=IOErrorCode.BAD_FLAGS,
                    errno=HostErrno.EINVAL,
                )
        return tuple(out)
    raise IOError(
        "open flags must be OpenFlag or a sequence of OpenFlag",
        code=IOErrorCode.BAD_FLAGS,
        errno=HostErrno.EINVAL,
    )


def _access_mode(flags: Sequence[OpenFlag]) -> tuple[bool, bool]:
    if OpenFlag.O_RDONLY in flags:
        return True, False
    if OpenFlag.O_WRONLY in flags:
        return False, True
    if OpenFlag.O_RDWR in flags:
        return True, True
    return True, False


def _merge_dirty_over_base(
    base: bytes,
    *,
    base_offset: int,
    dirty: Sequence[DirtyExtent],
    read_offset: int,
    read_length: int,
    logical_size: int,
) -> bytes:
    """Overlay dirty extents onto a base range (holes → zero outside base)."""

    if read_length <= 0 or read_offset >= logical_size:
        return b""
    end = min(logical_size, read_offset + read_length)
    need = end - read_offset
    out = bytearray(need)

    # Fill from base where it covers the range.
    base_end = base_offset + len(base)
    for i in range(need):
        abs_off = read_offset + i
        if base_offset <= abs_off < base_end:
            out[i] = base[abs_off - base_offset]
        # else remains zero (hole or past base)

    # Apply dirty extents in sequence order (later overwrites earlier).
    ordered = sorted(dirty, key=lambda e: e.sequence)
    for ext in ordered:
        if not ext.overlaps(read_offset, need):
            continue
        start = max(ext.offset, read_offset)
        stop = min(ext.end, end)
        if start >= stop:
            continue
        src = start - ext.offset
        dst = start - read_offset
        out[dst : dst + (stop - start)] = ext.data[src : src + (stop - start)]
    return bytes(out)


def _coalesce_dirty_ranges(extents: Sequence[DirtyExtent]) -> list[tuple[int, int, bytes]]:
    """Coalesce dirty extents into non-overlapping (offset, length, data) runs.

    Later sequence wins on overlap. Returns ranges sorted by offset.
    """

    if not extents:
        return []
    # Build a sparse map via a simple ordered merge of sequence-sorted extents.
    ordered = sorted(extents, key=lambda e: e.sequence)
    # Use a dict of absolute offset -> byte for simplicity within bounds;
    # practical extents are small relative to MAX_IO_LENGTH.
    total = 0
    for e in ordered:
        total += e.length
    if total > DEFAULT_MAX_DIRTY_BYTES_PER_SESSION:
        # Fall back to non-coalesced emission when extreme.
        return [(e.offset, e.length, e.data) for e in ordered]

    spans: dict[int, int] = {}  # offset -> byte
    for e in ordered:
        for i, b in enumerate(e.data):
            spans[e.offset + i] = b
    if not spans:
        return []
    keys = sorted(spans)
    runs: list[tuple[int, int, bytes]] = []
    run_start = keys[0]
    run_bytes = bytearray([spans[keys[0]]])
    prev = keys[0]
    for k in keys[1:]:
        if k == prev + 1:
            run_bytes.append(spans[k])
        else:
            runs.append((run_start, len(run_bytes), bytes(run_bytes)))
            run_start = k
            run_bytes = bytearray([spans[k]])
        prev = k
    runs.append((run_start, len(run_bytes), bytes(run_bytes)))
    return runs


def ranges_cover_only_requested(
    loaded: Sequence[tuple[int, int]],
    *,
    offset: int,
    length: int,
    chunk_bytes: int,
) -> bool:
    """Return True when every loaded range is within the chunk-aligned request."""

    if length <= 0:
        return len(loaded) == 0
    first, last = _chunk_span(offset, length, chunk_bytes)
    if last < first:
        allowed_start, allowed_end = offset, offset
    else:
        allowed_start = first * chunk_bytes
        allowed_end = (last + 1) * chunk_bytes
    for loff, llen in loaded:
        if llen <= 0:
            continue
        if loff < allowed_start or loff + llen > allowed_end:
            return False
    return True


def traces_match(
    left: Sequence[Mapping[str, Any]],
    right: Sequence[Mapping[str, Any]],
) -> bool:
    """Structural equality for canonical reference-trace records."""

    if len(left) != len(right):
        return False
    for a, b in zip(left, right):
        if dict(a) != dict(b):
            return False
    return True


# ---------------------------------------------------------------------------
# Instrumenting storage proxy
# ---------------------------------------------------------------------------


@runtime_checkable
class _StorageSurface(Protocol):
    def stat(self, path: str) -> StorageStat: ...

    def range_read(self, path: str, offset: int, length: int) -> RangeReadResult: ...

    def begin_staged_write(
        self, path: str, *, truncate: bool = True
    ) -> StageHandle: ...

    def stage_write(self, handle: StageHandle, offset: int, data: bytes) -> None: ...

    def commit_staged_write(self, handle: StageHandle) -> Any: ...

    def abort_staged_write(self, handle: StageHandle) -> None: ...

    def seed_file(self, path: str, **kwargs: Any) -> Any: ...


class InstrumentingStorage:
    """Wrap a ranged storage backend to record range loads and inject faults."""

    def __init__(
        self,
        backend: RangedVFSStorageBoundary,
        *,
        fail_range_read_after: int | None = None,
        fail_stage_write_after: int | None = None,
        fail_commit_after: int | None = None,
    ) -> None:
        self._backend = backend
        self._lock = threading.RLock()
        self.loaded_ranges: list[LoadedRange] = []
        self.stage_writes: list[tuple[str, int, int]] = []
        self.commits: list[str] = []
        self.aborts: list[str] = []
        self._range_reads = 0
        self._stage_writes = 0
        self._commits = 0
        self._fail_range_read_after = fail_range_read_after
        self._fail_stage_write_after = fail_stage_write_after
        self._fail_commit_after = fail_commit_after

    @property
    def backend(self) -> RangedVFSStorageBoundary:
        return self._backend

    @property
    def chunk_bytes(self) -> int:
        return int(getattr(self._backend, "chunk_bytes", STORAGE_DEFAULT_CHUNK_BYTES))

    @property
    def generation(self) -> int:
        return int(self._backend.generation)

    @property
    def backend_id(self) -> str:
        return str(self._backend.backend_id)

    def clear_observations(self) -> None:
        with self._lock:
            self.loaded_ranges.clear()
            self.stage_writes.clear()
            self.commits.clear()
            self.aborts.clear()

    def configure_failures(
        self,
        *,
        fail_range_read_after: int | None = None,
        fail_stage_write_after: int | None = None,
        fail_commit_after: int | None = None,
    ) -> None:
        with self._lock:
            if fail_range_read_after is not None:
                self._fail_range_read_after = fail_range_read_after
                self._range_reads = 0
            if fail_stage_write_after is not None:
                self._fail_stage_write_after = fail_stage_write_after
                self._stage_writes = 0
            if fail_commit_after is not None:
                self._fail_commit_after = fail_commit_after
                self._commits = 0

    def stat(self, path: str) -> StorageStat:
        return self._backend.stat(path)

    def range_read(self, path: str, offset: int, length: int) -> RangeReadResult:
        with self._lock:
            self._range_reads += 1
            if (
                self._fail_range_read_after is not None
                and self._range_reads > self._fail_range_read_after
            ):
                raise RangedStorageError(
                    "injected range_read failure",
                    code=StorageErrorCode.UNAVAILABLE,
                    path=path,
                    backend_id=self.backend_id,
                    detail={"injected": True, "op": "range_read"},
                )
            result = self._backend.range_read(path, offset, length)
            self.loaded_ranges.append(
                LoadedRange(
                    path=result.path,
                    offset=result.offset,
                    length=result.length,
                    chunks_touched=result.chunks_touched,
                )
            )
            return result

    def begin_staged_write(self, path: str, *, truncate: bool = True) -> StageHandle:
        return self._backend.begin_staged_write(path, truncate=truncate)

    def stage_write(self, handle: StageHandle, offset: int, data: bytes) -> None:
        with self._lock:
            self._stage_writes += 1
            if (
                self._fail_stage_write_after is not None
                and self._stage_writes > self._fail_stage_write_after
            ):
                raise RangedStorageError(
                    "injected stage_write failure",
                    code=StorageErrorCode.UNAVAILABLE,
                    path=handle.path,
                    backend_id=self.backend_id,
                    detail={"injected": True, "op": "stage_write"},
                )
            self._backend.stage_write(handle, offset, data)
            self.stage_writes.append((handle.path, offset, len(data)))

    def commit_staged_write(self, handle: StageHandle) -> Any:
        with self._lock:
            self._commits += 1
            if (
                self._fail_commit_after is not None
                and self._commits > self._fail_commit_after
            ):
                raise RangedStorageError(
                    "injected commit failure",
                    code=StorageErrorCode.UNAVAILABLE,
                    path=handle.path,
                    backend_id=self.backend_id,
                    detail={"injected": True, "op": "commit"},
                )
            effect = self._backend.commit_staged_write(handle)
            self.commits.append(handle.path)
            return effect

    def abort_staged_write(self, handle: StageHandle) -> None:
        with self._lock:
            self._backend.abort_staged_write(handle)
            self.aborts.append(handle.path)

    def seed_file(self, path: str, **kwargs: Any) -> Any:
        return self._backend.seed_file(path, **kwargs)

    def effects(self) -> tuple[Any, ...]:
        return self._backend.effects()

    def set_available(self, available: bool) -> None:
        setter = getattr(self._backend, "set_available", None)
        if callable(setter):
            setter(available)


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------


@dataclass
class _SessionState:
    session_id: int
    generation: int
    path: str
    flags: tuple[OpenFlag, ...]
    append: bool
    readable: bool
    writable: bool
    released: bool = False
    dirty: dict[int, bytes] = field(default_factory=dict)  # chunk map
    dirty_size: int = 0
    base_size: int = 0
    extents: list[DirtyExtent] = field(default_factory=list)
    extent_seq: int = 0
    dirty_bytes: int = 0
    deferred_code: str = ""
    deferred_errno: str = ""
    deferred_message: str = ""
    # True when dirty map is a full overlay (includes base snapshot for RMW).
    has_base_snapshot: bool = False

    def view(self) -> IOSession:
        return IOSession(
            session_id=self.session_id,
            generation=self.generation,
            path=self.path,
            flags=self.flags,
            append=self.append,
            readable=self.readable,
            writable=self.writable,
            released=self.released,
            dirty_bytes=self.dirty_bytes,
            logical_size=self.dirty_size,
            deferred_error_code=self.deferred_code,
        )


# ---------------------------------------------------------------------------
# Offset I/O runtime
# ---------------------------------------------------------------------------


class OffsetIORuntime:
    """Data-plane assembly for offset reads/writes, truncate, and append.

    Composes a ranged storage backend with per-session dirty extents. Reads
    load only the requested chunk span from the backend and overlay dirty
    extents. Writes never enter the backend until :meth:`flush` assembles and
    commits dirty ranges. Append is serialized under a dedicated lock.
    """

    SCHEMA: ClassVar[str] = OFFSET_IO_RUNTIME_SCHEMA
    CONTRACT_VERSION: ClassVar[int] = CONTRACT_VERSION

    def __init__(
        self,
        storage: RangedVFSStorageBoundary | InstrumentingStorage | None = None,
        *,
        chunk_bytes: int = DEFAULT_CHUNK_BYTES,
        max_open_sessions: int = DEFAULT_MAX_OPEN_SESSIONS,
        max_dirty_bytes: int = DEFAULT_MAX_DIRTY_BYTES,
        max_dirty_bytes_per_session: int = DEFAULT_MAX_DIRTY_BYTES_PER_SESSION,
        max_extents_per_session: int = DEFAULT_MAX_EXTENTS_PER_SESSION,
        clock_ms: Callable[[], int] | None = None,
        instrument: bool = True,
    ) -> None:
        if chunk_bytes < 1:
            raise IOError("chunk_bytes must be positive", code=IOErrorCode.INTERNAL)
        if (
            not isinstance(max_open_sessions, int)
            or max_open_sessions < 1
            or max_open_sessions > MAX_OPEN_SESSIONS_HARD
        ):
            raise IOError(
                f"max_open_sessions must be in [1, {MAX_OPEN_SESSIONS_HARD}]",
                code=IOErrorCode.INTERNAL,
            )
        raw = storage if storage is not None else MemoryRangedStorage(
            clock=lambda: 1_700_000_000_000
        )
        if isinstance(raw, InstrumentingStorage):
            self._storage: InstrumentingStorage = raw
        elif instrument:
            self._storage = InstrumentingStorage(raw)
        else:
            # Always keep the instrumenting surface so load observations work;
            # callers that pass instrument=False still get a thin wrapper.
            self._storage = InstrumentingStorage(raw)

        self._chunk_bytes = chunk_bytes
        self._max_open = max_open_sessions
        self._max_dirty = max_dirty_bytes
        self._max_dirty_per = max_dirty_bytes_per_session
        self._max_extents = max_extents_per_session
        self._clock_ms = clock_ms or (lambda: int(time.time() * 1000))

        self._lock = threading.RLock()
        self._append_lock = threading.RLock()
        self._sessions: dict[int, _SessionState] = {}
        self._generations: dict[int, int] = {}
        self._next_session_id = MIN_SESSION_ID
        self._total_dirty = 0
        self._trace = IOTraceLog()
        # path -> committed logical size cache (refreshed on open/flush)
        self._size_cache: dict[str, int] = {}

    # -- properties ---------------------------------------------------------

    @property
    def schema(self) -> str:
        return self.SCHEMA

    @property
    def contract_version(self) -> int:
        return self.CONTRACT_VERSION

    @property
    def schema_version(self) -> str:
        return SCHEMA_VERSION

    @property
    def chunk_bytes(self) -> int:
        return self._chunk_bytes

    @property
    def storage(self) -> InstrumentingStorage:
        return self._storage

    @property
    def trace(self) -> IOTraceLog:
        return self._trace

    @property
    def open_count(self) -> int:
        with self._lock:
            return sum(1 for s in self._sessions.values() if not s.released)

    @property
    def dirty_bytes(self) -> int:
        with self._lock:
            return self._total_dirty

    def loaded_ranges(self) -> tuple[LoadedRange, ...]:
        return tuple(self._storage.loaded_ranges)

    def clear_loaded_ranges(self) -> None:
        self._storage.clear_observations()

    # -- seed / setup -------------------------------------------------------

    def seed_file(
        self,
        path: str,
        data: bytes | None = None,
        *,
        size_bytes: int | None = None,
        pattern: bytes = b"\x00",
    ) -> dict[str, Any]:
        """Install committed content via the backend (setup / tests)."""

        if not isinstance(path, str) or not path:
            raise IOError(
                "path must be a non-empty relative VFS path",
                code=IOErrorCode.INTERNAL,
                path=path or "",
            )
        with self._lock:
            if data is not None:
                if not isinstance(data, (bytes, bytearray)):
                    raise IOError(
                        "data must be bytes",
                        code=IOErrorCode.INTERNAL,
                        path=path,
                    )
                payload = bytes(data)
                effect = self._storage.seed_file(path, data=payload)
                size = len(payload)
            else:
                size = int(size_bytes or 0)
                effect = self._storage.seed_file(
                    path, size_bytes=size, pattern=pattern
                )
            self._size_cache[path] = size
            self._trace.record(
                IOTraceKind.SEED,
                success=True,
                path=path,
                detail={
                    "size_bytes": size,
                    "op": TRACE_OP_SEED,
                },
            )
            return {
                "path": path,
                "size_bytes": size,
                "generation": getattr(effect, "generation", self._storage.generation),
            }

    # -- open / create ------------------------------------------------------

    def open(
        self,
        path: str,
        flags: OpenFlag | Sequence[OpenFlag] = OpenFlag.O_RDONLY,
    ) -> IOSession:
        """Open a path for offset I/O, returning a generation-tagged session."""

        norm_flags = _normalize_flags(flags)
        access = [f for f in norm_flags if f in {
            OpenFlag.O_RDONLY, OpenFlag.O_WRONLY, OpenFlag.O_RDWR
        }]
        if len(access) != 1:
            raise IOError(
                "exactly one of O_RDONLY/O_WRONLY/O_RDWR is required",
                code=IOErrorCode.BAD_FLAGS,
                errno=HostErrno.EINVAL,
                path=path,
            )
        creat = OpenFlag.O_CREAT in norm_flags
        excl = OpenFlag.O_EXCL in norm_flags
        trunc = OpenFlag.O_TRUNC in norm_flags
        append = OpenFlag.O_APPEND in norm_flags
        if excl and not creat:
            raise IOError(
                "O_EXCL requires O_CREAT",
                code=IOErrorCode.BAD_FLAGS,
                errno=HostErrno.EINVAL,
                path=path,
            )
        readable, writable = _access_mode(norm_flags)
        if append and not writable:
            raise IOError(
                "O_APPEND requires a writable access mode",
                code=IOErrorCode.BAD_FLAGS,
                errno=HostErrno.EINVAL,
                path=path,
            )

        with self._lock:
            open_n = sum(1 for s in self._sessions.values() if not s.released)
            if open_n >= self._max_open:
                raise IOError(
                    "open session bound exceeded",
                    code=IOErrorCode.PRESSURE,
                    errno=HostErrno.EMFILE,
                    path=path,
                    detail={"max_open_sessions": self._max_open},
                )

            exists = False
            base_size = 0
            try:
                st = self._storage.stat(path)
                exists = True
                if st.kind is VFSEntryKind.DIRECTORY:
                    raise IOError(
                        f"is a directory: {path!r}",
                        code=IOErrorCode.IS_DIRECTORY,
                        errno=HostErrno.EISDIR,
                        path=path,
                    )
                base_size = int(st.size_bytes)
            except RangedStorageError as exc:
                if exc.code is StorageErrorCode.NOT_FOUND:
                    exists = False
                else:
                    raise IOError(
                        str(exc),
                        code=IOErrorCode.BACKEND,
                        errno=HostErrno.EIO,
                        path=path,
                        detail=exc.to_record(),
                    ) from exc
            except IOError:
                raise

            if exists and excl:
                raise IOError(
                    f"file exists: {path!r}",
                    code=IOErrorCode.ALREADY_EXISTS,
                    errno=HostErrno.EEXIST,
                    path=path,
                )
            if not exists and not creat:
                raise IOError(
                    f"path not found: {path!r}",
                    code=IOErrorCode.NOT_FOUND,
                    errno=HostErrno.ENOENT,
                    path=path,
                )

            if not exists and creat:
                # Create empty committed file so subsequent range reads work.
                self._storage.seed_file(path, data=b"")
                base_size = 0
                kind = IOTraceKind.CREATE
            else:
                kind = IOTraceKind.OPEN

            if trunc and writable and exists:
                # Truncate committed content immediately (O_TRUNC semantics).
                handle = self._storage.begin_staged_write(path, truncate=True)
                self._storage.commit_staged_write(handle)
                base_size = 0

            sid = self._alloc_session_id()
            gen = self._generations.get(sid, 0) + 1
            self._generations[sid] = gen
            state = _SessionState(
                session_id=sid,
                generation=gen,
                path=path,
                flags=norm_flags,
                append=append,
                readable=readable,
                writable=writable,
                dirty_size=base_size,
                base_size=base_size,
            )
            self._sessions[sid] = state
            self._size_cache[path] = base_size
            self._trace.record(
                kind,
                success=True,
                session_id=sid,
                generation=gen,
                path=path,
                detail={
                    "op": TRACE_OP_OPEN,
                    "append": append,
                    "truncate": trunc,
                    "create": creat and not exists,
                    "logical_size": base_size,
                    "flags": [f.value for f in norm_flags],
                },
            )
            return state.view()

    def create(
        self,
        path: str,
        flags: OpenFlag | Sequence[OpenFlag] = OpenFlag.O_RDWR,
    ) -> IOSession:
        """Create-or-open helper that implies ``O_CREAT``."""

        norm = list(_normalize_flags(flags))
        if OpenFlag.O_CREAT not in norm:
            norm.append(OpenFlag.O_CREAT)
        if not any(f in norm for f in (OpenFlag.O_RDONLY, OpenFlag.O_WRONLY, OpenFlag.O_RDWR)):
            norm.insert(0, OpenFlag.O_RDWR)
        return self.open(path, tuple(norm))

    def _alloc_session_id(self) -> int:
        # Prefer recycling released slots to exercise generation bumps.
        for sid, state in self._sessions.items():
            if state.released:
                return sid
        sid = self._next_session_id
        self._next_session_id += 1
        return sid

    def _require_session(
        self,
        session_id: int,
        generation: int | None,
        *,
        for_write: bool = False,
        for_read: bool = False,
    ) -> _SessionState:
        state = self._sessions.get(session_id)
        if state is None:
            raise IOError(
                f"unknown session: {session_id}",
                code=IOErrorCode.NOT_OPEN,
                errno=HostErrno.EBADF,
                session_id=session_id,
            )
        if state.released:
            raise IOError(
                f"session released: {session_id}",
                code=IOErrorCode.RELEASED,
                errno=HostErrno.EBADF,
                session_id=session_id,
                generation=state.generation,
            )
        if generation is not None and state.generation != generation:
            raise IOError(
                f"stale session generation: {session_id}@{generation}",
                code=IOErrorCode.STALE,
                errno=HostErrno.ESTALE,
                session_id=session_id,
                generation=int(generation),
                detail={"live_generation": state.generation},
            )
        if for_write and not state.writable:
            raise IOError(
                "session is not writable",
                code=IOErrorCode.PERMISSION,
                errno=HostErrno.EBADF,
                session_id=session_id,
                generation=state.generation,
            )
        if for_read and not state.readable:
            raise IOError(
                "session is not readable",
                code=IOErrorCode.PERMISSION,
                errno=HostErrno.EBADF,
                session_id=session_id,
                generation=state.generation,
            )
        return state

    # -- write --------------------------------------------------------------

    def write(
        self,
        session_id: int,
        offset: int,
        data: bytes,
        *,
        generation: int | None = None,
    ) -> IOResult:
        """Stage a (possibly sparse/random/short) write on the session.

        Writes never enter shared ARC or the backend. With append mode the
        offset is ignored and data is appended under the append serialization
        lock.
        """

        if not isinstance(data, (bytes, bytearray)):
            raise IOError(
                "write data must be bytes",
                code=IOErrorCode.INTERNAL,
                session_id=session_id,
            )
        payload = bytes(data)
        off = _require_non_negative_int(offset, "offset")
        if len(payload) > MAX_IO_LENGTH:
            raise IOError(
                "write length exceeds I/O bound",
                code=IOErrorCode.BOUND_EXCEEDED,
                errno=HostErrno.EINVAL,
                session_id=session_id,
            )

        # Append serialization: hold append lock around the whole critical section
        # for append-mode sessions so concurrent appends never interleave.
        append_guard = self._append_lock

        with self._lock:
            state = self._require_session(
                session_id, generation, for_write=True
            )
            use_append = state.append
            if use_append:
                # Re-enter under append lock while still holding table lock is
                # safe (RLock); acquire append lock first for external order.
                pass

        if use_append:
            with append_guard:
                return self._write_locked(session_id, off, payload, generation)
        return self._write_locked(session_id, off, payload, generation)

    def _write_locked(
        self,
        session_id: int,
        offset: int,
        payload: bytes,
        generation: int | None,
    ) -> IOResult:
        with self._lock:
            state = self._require_session(session_id, generation, for_write=True)
            write_offset = state.dirty_size if state.append else offset
            if write_offset > MAX_OFFSET or write_offset + len(payload) > MAX_SIZE_BYTES:
                raise IOError(
                    "write would exceed size bound",
                    code=IOErrorCode.BOUND_EXCEEDED,
                    errno=HostErrno.EFBIG,
                    session_id=session_id,
                    generation=state.generation,
                )

            new_dirty = state.dirty_bytes + len(payload)
            if new_dirty > self._max_dirty_per:
                raise IOError(
                    "per-session dirty byte bound exceeded",
                    code=IOErrorCode.PRESSURE,
                    errno=HostErrno.ENOSPC,
                    session_id=session_id,
                    generation=state.generation,
                    detail={
                        "dirty_bytes": new_dirty,
                        "max_dirty_bytes_per_session": self._max_dirty_per,
                    },
                )
            projected = self._total_dirty - state.dirty_bytes + new_dirty
            if projected > self._max_dirty:
                raise IOError(
                    "runtime dirty byte bound exceeded",
                    code=IOErrorCode.PRESSURE,
                    errno=HostErrno.ENOSPC,
                    session_id=session_id,
                    generation=state.generation,
                    detail={
                        "dirty_bytes": projected,
                        "max_dirty_bytes": self._max_dirty,
                    },
                )
            if len(state.extents) >= self._max_extents:
                raise IOError(
                    "per-session extent bound exceeded",
                    code=IOErrorCode.PRESSURE,
                    errno=HostErrno.ENOSPC,
                    session_id=session_id,
                    generation=state.generation,
                )

            hole_before = max(0, write_offset - state.dirty_size)
            sparse = write_offset > state.dirty_size
            prev_size = state.dirty_size
            state.dirty_size = _write_into_chunks(
                state.dirty,
                size_bytes=state.dirty_size,
                offset=write_offset,
                data=payload,
                chunk_bytes=self._chunk_bytes,
            )
            if not payload and write_offset > prev_size:
                state.dirty_size = write_offset

            state.extent_seq += 1
            extent = DirtyExtent(
                offset=write_offset,
                length=len(payload),
                data=payload,
                sequence=state.extent_seq,
            )
            state.extents.append(extent)
            delta = new_dirty - state.dirty_bytes
            state.dirty_bytes = new_dirty
            self._total_dirty += delta

            zero_length = len(payload) == 0
            if sparse:
                self._trace.record(
                    IOTraceKind.HOLE,
                    success=True,
                    session_id=session_id,
                    generation=state.generation,
                    path=state.path,
                    detail={
                        "hole_before": hole_before,
                        "offset": write_offset,
                        "logical_size": state.dirty_size,
                    },
                )
            if zero_length:
                self._trace.record(
                    IOTraceKind.ZERO_LENGTH,
                    success=True,
                    session_id=session_id,
                    generation=state.generation,
                    path=state.path,
                    detail={"op": TRACE_OP_WRITE, "offset": write_offset},
                )
            kind = IOTraceKind.APPEND if state.append else IOTraceKind.WRITE
            self._trace.record(
                kind,
                success=True,
                session_id=session_id,
                generation=state.generation,
                path=state.path,
                detail={
                    "op": TRACE_OP_WRITE,
                    "offset": write_offset,
                    "length": len(payload),
                    "append": state.append,
                    "sparse": sparse,
                    "hole_before": hole_before,
                    "logical_size": state.dirty_size,
                    "dirty_in_session_only": True,
                    "sequence": extent.sequence,
                    "zero_length": zero_length,
                },
            )
            return IOResult(
                session_id=session_id,
                generation=state.generation,
                offset=write_offset,
                length=len(payload),
                bytes_transferred=len(payload),
                logical_size=state.dirty_size,
                staged=True,
                sparse=sparse,
                hole_before=hole_before,
                dirty_in_session_only=True,
                zero_length=zero_length,
            )

    # -- read ---------------------------------------------------------------

    def read(
        self,
        session_id: int,
        offset: int,
        length: int,
        *,
        generation: int | None = None,
    ) -> IOResult:
        """Read bytes observing this session's own staged writes.

        Backend loads are confined to the chunk-aligned span covering
        ``[offset, offset+length)`` that is not fully satisfied by dirty
        extents. Unrelated ranges are never loaded.
        """

        off = _require_non_negative_int(offset, "offset")
        length = _require_non_negative_int(length, "length")
        if length > MAX_IO_LENGTH:
            raise IOError(
                "read length exceeds I/O bound",
                code=IOErrorCode.BOUND_EXCEEDED,
                errno=HostErrno.EINVAL,
                session_id=session_id,
            )

        with self._lock:
            # Read-own-writes is allowed for writable-only sessions.
            state = self._require_session(session_id, generation)
            logical = state.dirty_size
            zero_length = length == 0
            if zero_length:
                self._trace.record(
                    IOTraceKind.ZERO_LENGTH,
                    success=True,
                    session_id=session_id,
                    generation=state.generation,
                    path=state.path,
                    detail={"op": TRACE_OP_READ, "offset": off},
                )
                self._trace.record(
                    IOTraceKind.READ,
                    success=True,
                    session_id=session_id,
                    generation=state.generation,
                    path=state.path,
                    detail={
                        "op": TRACE_OP_READ,
                        "offset": off,
                        "length": 0,
                        "bytes": 0,
                        "logical_size": logical,
                        "zero_length": True,
                        "ranges_loaded": [],
                        "chunks_touched": 0,
                    },
                )
                return IOResult(
                    session_id=session_id,
                    generation=state.generation,
                    offset=off,
                    length=0,
                    bytes_transferred=0,
                    data=b"",
                    logical_size=logical,
                    staged=bool(state.extents),
                    dirty_in_session_only=bool(state.extents),
                    read_own_writes=True,
                    zero_length=True,
                    eof=off >= logical,
                )

            if off >= logical:
                self._trace.record(
                    IOTraceKind.EOF,
                    success=True,
                    session_id=session_id,
                    generation=state.generation,
                    path=state.path,
                    detail={"offset": off, "logical_size": logical},
                )
                self._trace.record(
                    IOTraceKind.READ,
                    success=True,
                    session_id=session_id,
                    generation=state.generation,
                    path=state.path,
                    detail={
                        "op": TRACE_OP_READ,
                        "offset": off,
                        "length": length,
                        "bytes": 0,
                        "logical_size": logical,
                        "eof": True,
                        "ranges_loaded": [],
                        "chunks_touched": 0,
                    },
                )
                return IOResult(
                    session_id=session_id,
                    generation=state.generation,
                    offset=off,
                    length=length,
                    bytes_transferred=0,
                    data=b"",
                    logical_size=logical,
                    staged=bool(state.extents),
                    dirty_in_session_only=bool(state.extents),
                    read_own_writes=True,
                    eof=True,
                    short_read=True,
                )

            need_end = min(logical, off + length)
            need_len = need_end - off
            short_read = need_len < length

            # Determine sub-ranges not fully covered by dirty extents so we
            # only load those from the backend.
            load_ranges = self._uncovered_ranges(state, off, need_len)
            ranges_loaded: list[tuple[int, int]] = []
            chunks_touched = 0
            base_buf = bytearray(need_len)

            for loff, llen in load_ranges:
                # Clamp to committed base size — past-base holes are zeroes.
                if loff >= state.base_size:
                    continue
                take = min(llen, state.base_size - loff)
                if take <= 0:
                    continue
                try:
                    rr = self._storage.range_read(state.path, loff, take)
                except RangedStorageError as exc:
                    self._trace.record(
                        IOTraceKind.PARTIAL_FAILURE,
                        success=False,
                        session_id=session_id,
                        generation=state.generation,
                        path=state.path,
                        code=IOErrorCode.PARTIAL_FAILURE.value,
                        detail={
                            "op": "range_read",
                            "offset": loff,
                            "length": take,
                            "backend_code": exc.code.value,
                        },
                    )
                    raise IOError(
                        f"backend range_read failed: {exc}",
                        code=IOErrorCode.PARTIAL_FAILURE,
                        errno=HostErrno.EIO,
                        session_id=session_id,
                        generation=state.generation,
                        path=state.path,
                        detail=exc.to_record(),
                    ) from exc
                ranges_loaded.append((rr.offset, rr.length))
                chunks_touched += rr.chunks_touched
                self._trace.record(
                    IOTraceKind.BACKEND_LOAD,
                    success=True,
                    session_id=session_id,
                    generation=state.generation,
                    path=state.path,
                    detail={
                        "offset": rr.offset,
                        "length": rr.length,
                        "chunks_touched": rr.chunks_touched,
                    },
                )
                dst = loff - off
                base_buf[dst : dst + len(rr.data)] = rr.data

            # Overlay dirty chunk map (authoritative for dirty regions).
            dirty_view, _ = _read_from_chunks(
                state.dirty,
                size_bytes=state.dirty_size,
                offset=off,
                length=need_len,
                chunk_bytes=self._chunk_bytes,
            )
            # Merge: dirty bytes win where the dirty map has coverage; for
            # simplicity the dirty map already includes written bytes and
            # zeros for holes. We need base for non-dirty regions.
            # Reconstruct by starting from base then applying extents.
            data = _merge_dirty_over_base(
                bytes(base_buf),
                base_offset=off,
                dirty=state.extents,
                read_offset=off,
                read_length=need_len,
                logical_size=logical,
            )
            # If no extents, data is pure base (possibly short).
            if not state.extents:
                data = bytes(base_buf[:need_len])
                # Holes past base_size already zero in base_buf.
                if state.dirty_size > state.base_size and need_end > state.base_size:
                    # Ensure zeros past base (already zero-initialized).
                    pass
            else:
                # When dirty map has explicit chunk data for a region that
                # was written, prefer dirty_view for those bytes that were
                # actually staged. Using extent merge is authoritative.
                _ = dirty_view  # retained for potential future RMW path

            # Invariant: no unrelated ranges.
            if not ranges_cover_only_requested(
                ranges_loaded,
                offset=off,
                length=need_len,
                chunk_bytes=self._chunk_bytes,
            ):
                raise IOError(
                    "loaded unrelated ranges",
                    code=IOErrorCode.INTERNAL,
                    session_id=session_id,
                    generation=state.generation,
                    detail={"ranges_loaded": ranges_loaded, "offset": off, "length": need_len},
                )

            if short_read or off + need_len >= logical:
                if short_read:
                    self._trace.record(
                        IOTraceKind.EOF,
                        success=True,
                        session_id=session_id,
                        generation=state.generation,
                        path=state.path,
                        detail={
                            "offset": off,
                            "requested": length,
                            "returned": need_len,
                            "logical_size": logical,
                        },
                    )

            own = any(ext.overlaps(off, need_len) for ext in state.extents)
            self._trace.record(
                IOTraceKind.READ,
                success=True,
                session_id=session_id,
                generation=state.generation,
                path=state.path,
                detail={
                    "op": TRACE_OP_READ,
                    "offset": off,
                    "length": length,
                    "bytes": len(data),
                    "logical_size": logical,
                    "read_own_writes": own or bool(state.extents),
                    "ranges_loaded": [list(r) for r in ranges_loaded],
                    "chunks_touched": chunks_touched,
                    "short_read": short_read,
                    "eof": short_read,
                    "dirty_in_session_only": bool(state.extents),
                },
            )
            return IOResult(
                session_id=session_id,
                generation=state.generation,
                offset=off,
                length=length,
                bytes_transferred=len(data),
                data=data,
                logical_size=logical,
                staged=bool(state.extents),
                dirty_in_session_only=bool(state.extents),
                read_own_writes=True,
                ranges_loaded=tuple(ranges_loaded),
                chunks_touched=chunks_touched,
                eof=short_read,
                short_read=short_read,
            )

    def _uncovered_ranges(
        self,
        state: _SessionState,
        offset: int,
        length: int,
    ) -> list[tuple[int, int]]:
        """Return sub-ranges of [offset, offset+length) not covered by dirty extents.

        Covered means a dirty extent fully supplies those bytes. Partial
        coverage still requires a base load for the remainder; for simplicity
        we load the full requested span when any hole exists relative to the
        dirty extent set, but only within the requested range.
        """

        if length <= 0:
            return []
        end = offset + length
        # Build coverage mask via extents.
        covered = bytearray(length)  # 1 = covered by dirty
        for ext in state.extents:
            if not ext.overlaps(offset, length):
                continue
            start = max(ext.offset, offset)
            stop = min(ext.end, end)
            for i in range(start, stop):
                covered[i - offset] = 1
        ranges: list[tuple[int, int]] = []
        i = 0
        while i < length:
            if covered[i]:
                i += 1
                continue
            j = i + 1
            while j < length and not covered[j]:
                j += 1
            ranges.append((offset + i, j - i))
            i = j
        return ranges

    # -- truncate -----------------------------------------------------------

    def truncate(
        self,
        session_id: int,
        size: int,
        *,
        generation: int | None = None,
    ) -> TruncateResult:
        """Grow or shrink the session's logical (staged) size."""

        size = _require_non_negative_int(size, "size")
        if size > MAX_SIZE_BYTES:
            raise IOError(
                "truncate size exceeds bound",
                code=IOErrorCode.BOUND_EXCEEDED,
                errno=HostErrno.EFBIG,
                session_id=session_id,
            )
        with self._lock:
            state = self._require_session(session_id, generation, for_write=True)
            prev = state.dirty_size
            if size < prev:
                _trim_chunks_to_size(
                    state.dirty,
                    size_bytes=size,
                    chunk_bytes=self._chunk_bytes,
                )
                kept: list[DirtyExtent] = []
                for ext in state.extents:
                    if ext.offset >= size:
                        continue
                    if ext.end <= size:
                        kept.append(ext)
                    else:
                        clipped = ext.data[: max(0, size - ext.offset)]
                        kept.append(
                            DirtyExtent(
                                offset=ext.offset,
                                length=len(clipped),
                                data=clipped,
                                sequence=ext.sequence,
                            )
                        )
                # Recompute dirty_bytes from kept extents.
                old_dirty = state.dirty_bytes
                state.extents = kept
                state.dirty_bytes = sum(e.length for e in kept)
                self._total_dirty = max(0, self._total_dirty - old_dirty + state.dirty_bytes)
            state.dirty_size = size
            # Truncate is always a dirty operation until flush.
            if size != prev or True:
                # Ensure shrink/grow is visible as dirty even if no extents.
                pass
            result = TruncateResult(
                session_id=session_id,
                generation=state.generation,
                size=size,
                previous_size=prev,
                grew=size > prev,
                shrank=size < prev,
                dirty_in_session_only=True,
            )
            self._trace.record(
                IOTraceKind.TRUNCATE,
                success=True,
                session_id=session_id,
                generation=state.generation,
                path=state.path,
                detail={
                    "op": TRACE_OP_TRUNCATE,
                    "size": size,
                    "previous_size": prev,
                    "grew": result.grew,
                    "shrank": result.shrank,
                    "dirty_in_session_only": True,
                },
            )
            return result

    # -- flush / assemble / release -----------------------------------------

    def flush(
        self,
        session_id: int,
        *,
        generation: int | None = None,
        commit: bool = True,
    ) -> FlushAssemblyResult:
        """Assemble dirty extents into a backend staged write and optionally commit.

        On partial backend failure the staged write is aborted, dirty extents
        remain in the session, and no dirty bytes leak into committed storage.
        """

        with self._lock:
            state = self._require_session(session_id, generation)
            if state.deferred_code:
                result = FlushAssemblyResult(
                    session_id=session_id,
                    generation=state.generation,
                    success=False,
                    deferred_error=True,
                    error_code=state.deferred_code,
                    errno=state.deferred_errno or HostErrno.EIO.value,
                    dirty_leaked=False,
                    detail={"message": state.deferred_message},
                )
                self._trace.record(
                    IOTraceKind.DEFERRED,
                    success=False,
                    session_id=session_id,
                    generation=state.generation,
                    path=state.path,
                    code=state.deferred_code,
                    detail=result.to_record(),
                )
                return result

            if not state.extents and state.dirty_size == state.base_size:
                result = FlushAssemblyResult(
                    session_id=session_id,
                    generation=state.generation,
                    success=True,
                    committed_bytes=0,
                    extents_assembled=0,
                    dirty_leaked=False,
                    durable=False,
                    detail={"noop": True},
                )
                self._trace.record(
                    IOTraceKind.FLUSH,
                    success=True,
                    session_id=session_id,
                    generation=state.generation,
                    path=state.path,
                    detail=result.to_record(),
                )
                return result

            if not commit:
                result = FlushAssemblyResult(
                    session_id=session_id,
                    generation=state.generation,
                    success=True,
                    committed_bytes=0,
                    extents_assembled=len(state.extents),
                    dirty_leaked=False,
                    durable=False,
                    detail={"commit": False, "dirty_bytes": state.dirty_bytes},
                )
                self._trace.record(
                    IOTraceKind.FLUSH,
                    success=True,
                    session_id=session_id,
                    generation=state.generation,
                    path=state.path,
                    detail=result.to_record(),
                )
                return result

            return self._assemble_and_commit_locked(state)

    def _assemble_and_commit_locked(self, state: _SessionState) -> FlushAssemblyResult:
        path = state.path
        # For truncate-to-smaller or full rewrite we use truncate=True when
        # logical size is less than base or we have a complete dirty image.
        truncate = state.dirty_size < state.base_size or (
            state.dirty_size == 0 and state.base_size > 0
        )
        # When growing or partial overwriting, use non-truncate stage and
        # write only dirty ranges (plus explicit size extension if needed).
        runs = _coalesce_dirty_ranges(state.extents)
        ranges_written: list[tuple[int, int]] = []
        stage: StageHandle | None = None
        try:
            stage = self._storage.begin_staged_write(path, truncate=truncate)
            if truncate and state.dirty_size > 0:
                # Emit full logical content from dirty map (base was truncated).
                data, _ = _read_from_chunks(
                    state.dirty,
                    size_bytes=state.dirty_size,
                    offset=0,
                    length=state.dirty_size,
                    chunk_bytes=self._chunk_bytes,
                )
                if data:
                    self._storage.stage_write(stage, 0, data)
                    ranges_written.append((0, len(data)))
            else:
                # Partial assembly: only dirty ranges.
                max_end = 0
                for off, length, data in runs:
                    if length <= 0:
                        continue
                    self._storage.stage_write(stage, off, data)
                    ranges_written.append((off, length))
                    max_end = max(max_end, off + length)
                # Ensure logical size is preserved on grow (holes past last dirty
                # byte must extend committed size without loading whole objects).
                if state.dirty_size > max(state.base_size, max_end):
                    # Write a single zero at the last logical byte to extend size.
                    self._storage.stage_write(
                        stage, state.dirty_size - 1, b"\x00"
                    )
                    ranges_written.append((state.dirty_size - 1, 1))

            self._trace.record(
                IOTraceKind.ASSEMBLE,
                success=True,
                session_id=state.session_id,
                generation=state.generation,
                path=path,
                detail={
                    "extents_assembled": len(state.extents),
                    "ranges_written": [list(r) for r in ranges_written],
                    "truncate": truncate,
                    "logical_size": state.dirty_size,
                },
            )
            effect = self._storage.commit_staged_write(stage)
            stage = None  # committed
            committed = state.dirty_bytes
            self._trace.record(
                IOTraceKind.BACKEND_COMMIT,
                success=True,
                session_id=state.session_id,
                generation=state.generation,
                path=path,
                detail={
                    "committed_bytes": committed,
                    "size_bytes": state.dirty_size,
                    "generation": getattr(effect, "generation", 0),
                },
            )
            # Clear dirty; base catches up.
            self._total_dirty = max(0, self._total_dirty - state.dirty_bytes)
            state.extents.clear()
            state.dirty.clear()
            state.dirty_bytes = 0
            state.base_size = state.dirty_size
            self._size_cache[path] = state.dirty_size
            result = FlushAssemblyResult(
                session_id=state.session_id,
                generation=state.generation,
                success=True,
                committed_bytes=committed,
                extents_assembled=len(ranges_written),
                ranges_written=tuple(ranges_written),
                dirty_leaked=False,
                durable=True,
                detail={"logical_size": state.dirty_size},
            )
            self._trace.record(
                IOTraceKind.FLUSH,
                success=True,
                session_id=state.session_id,
                generation=state.generation,
                path=path,
                detail=result.to_record(),
            )
            return result
        except RangedStorageError as exc:
            if stage is not None:
                try:
                    self._storage.abort_staged_write(stage)
                except RangedStorageError:
                    pass
            # Dirty remains in session — no leak.
            state.deferred_code = IOErrorCode.PARTIAL_FAILURE.value
            state.deferred_errno = HostErrno.EIO.value
            state.deferred_message = str(exc)
            self._trace.record(
                IOTraceKind.PARTIAL_FAILURE,
                success=False,
                session_id=state.session_id,
                generation=state.generation,
                path=path,
                code=IOErrorCode.PARTIAL_FAILURE.value,
                detail={
                    "op": "flush_assemble",
                    "backend_code": exc.code.value,
                    "dirty_leaked": False,
                    "dirty_bytes_retained": state.dirty_bytes,
                },
            )
            result = FlushAssemblyResult(
                session_id=state.session_id,
                generation=state.generation,
                success=False,
                committed_bytes=0,
                extents_assembled=0,
                deferred_error=True,
                error_code=IOErrorCode.PARTIAL_FAILURE.value,
                errno=HostErrno.EIO.value,
                dirty_leaked=False,
                detail={
                    "message": str(exc),
                    "dirty_bytes_retained": state.dirty_bytes,
                },
            )
            self._trace.record(
                IOTraceKind.FLUSH,
                success=False,
                session_id=state.session_id,
                generation=state.generation,
                path=path,
                code=result.error_code,
                detail=result.to_record(),
            )
            return result

    def release(
        self,
        session_id: int,
        *,
        generation: int | None = None,
        discard_dirty: bool = True,
    ) -> dict[str, Any]:
        """Idempotent release. Does not manufacture durability or leak dirty."""

        with self._lock:
            state = self._sessions.get(session_id)
            if state is None:
                rec = {
                    "session_id": session_id,
                    "success": True,
                    "already_released": True,
                    "unknown": True,
                }
                self._trace.record(
                    IOTraceKind.RELEASE,
                    success=True,
                    session_id=session_id,
                    detail=rec,
                )
                return rec
            if generation is not None and state.generation != generation:
                raise IOError(
                    f"stale session on release: {session_id}@{generation}",
                    code=IOErrorCode.STALE,
                    errno=HostErrno.ESTALE,
                    session_id=session_id,
                    generation=int(generation),
                )
            if state.released:
                rec = {
                    "session_id": session_id,
                    "generation": state.generation,
                    "success": True,
                    "already_released": True,
                }
                self._trace.record(
                    IOTraceKind.RELEASE,
                    success=True,
                    session_id=session_id,
                    generation=state.generation,
                    path=state.path,
                    detail=rec,
                )
                return rec
            if discard_dirty and state.dirty_bytes:
                self._total_dirty = max(0, self._total_dirty - state.dirty_bytes)
                state.extents.clear()
                state.dirty.clear()
                state.dirty_bytes = 0
            state.released = True
            rec = {
                "session_id": session_id,
                "generation": state.generation,
                "success": True,
                "already_released": False,
                "discarded_dirty": bool(discard_dirty),
                "dirty_leaked": False,
            }
            self._trace.record(
                IOTraceKind.RELEASE,
                success=True,
                session_id=session_id,
                generation=state.generation,
                path=state.path,
                detail=rec,
            )
            return rec

    def dirty_extents(
        self,
        session_id: int,
        *,
        generation: int | None = None,
    ) -> tuple[DirtyExtent, ...]:
        with self._lock:
            state = self._require_session(session_id, generation)
            return tuple(state.extents)

    def committed_read(self, path: str, offset: int = 0, length: int | None = None) -> bytes:
        """Read committed backend bytes only (never dirty session bytes)."""

        st = self._storage.stat(path)
        size = int(st.size_bytes)
        off = _require_non_negative_int(offset, "offset")
        if length is None:
            length = max(0, size - off)
        length = _require_non_negative_int(length, "length")
        if off >= size or length == 0:
            return b""
        take = min(length, size - off)
        return self._storage.range_read(path, off, take).data

    def set_deferred_error(
        self,
        session_id: int,
        *,
        generation: int | None = None,
        code: IOErrorCode | str = IOErrorCode.DEFERRED,
        errno: HostErrno | str = HostErrno.EIO,
        message: str = "deferred write error",
    ) -> IOSession:
        with self._lock:
            state = self._require_session(session_id, generation)
            state.deferred_code = (
                code.value if isinstance(code, IOErrorCode) else str(code)
            )
            state.deferred_errno = (
                errno.value if isinstance(errno, HostErrno) else str(errno)
            )
            state.deferred_message = message
            self._trace.record(
                IOTraceKind.DEFERRED,
                success=False,
                session_id=session_id,
                generation=state.generation,
                path=state.path,
                code=state.deferred_code,
                detail={"errno": state.deferred_errno, "message": message},
            )
            return state.view()

    def get(self, session_id: int, generation: int | None = None) -> IOSession:
        with self._lock:
            return self._require_session(session_id, generation).view()

    # -- trace suite / schedule ---------------------------------------------

    def run_trace(
        self,
        schedule: Sequence[Mapping[str, Any]],
        *,
        clear_trace: bool = True,
    ) -> list[dict[str, Any]]:
        """Execute a closed schedule of I/O ops and return canonical trace records."""

        if clear_trace:
            self._trace.clear()
            self.clear_loaded_ranges()
        sessions: dict[str, IOSession] = {}
        for step in schedule:
            op = str(step.get("op", ""))
            path = str(step.get("path", ""))
            key = str(step.get("session", path or "s0"))
            try:
                if op == TRACE_OP_SEED:
                    data = step.get("data", b"")
                    if isinstance(data, str):
                        data = data.encode("utf-8")
                    size_bytes = step.get("size_bytes")
                    pattern = step.get("pattern", b"\x00")
                    if isinstance(pattern, str):
                        pattern = pattern.encode("utf-8")
                    if size_bytes is not None:
                        self.seed_file(
                            path,
                            size_bytes=int(size_bytes),
                            pattern=bytes(pattern),
                        )
                    else:
                        self.seed_file(path, data=bytes(data))
                elif op == TRACE_OP_OPEN:
                    flags = step.get("flags", (OpenFlag.O_RDWR,))
                    if isinstance(flags, str):
                        flags = (OpenFlag(flags),)
                    sessions[key] = self.open(path, flags)
                elif op == TRACE_OP_WRITE:
                    sess = sessions[key]
                    data = step.get("data", b"")
                    if isinstance(data, str):
                        data = data.encode("utf-8")
                    self.write(
                        sess.session_id,
                        int(step.get("offset", 0)),
                        bytes(data),
                        generation=sess.generation,
                    )
                elif op == TRACE_OP_READ:
                    sess = sessions[key]
                    self.read(
                        sess.session_id,
                        int(step.get("offset", 0)),
                        int(step.get("length", 0)),
                        generation=sess.generation,
                    )
                elif op == TRACE_OP_TRUNCATE:
                    sess = sessions[key]
                    self.truncate(
                        sess.session_id,
                        int(step.get("size", 0)),
                        generation=sess.generation,
                    )
                elif op == TRACE_OP_FLUSH:
                    sess = sessions[key]
                    self.flush(
                        sess.session_id,
                        generation=sess.generation,
                        commit=bool(step.get("commit", True)),
                    )
                elif op == TRACE_OP_RELEASE:
                    sess = sessions[key]
                    self.release(sess.session_id, generation=sess.generation)
                elif op == TRACE_OP_STAT:
                    st = self._storage.stat(path)
                    self._trace.record(
                        IOTraceKind.STAT,
                        success=True,
                        path=path,
                        detail={
                            "op": TRACE_OP_STAT,
                            "size_bytes": st.size_bytes,
                        },
                    )
                else:
                    raise IOError(
                        f"unknown schedule op: {op!r}",
                        code=IOErrorCode.INTERNAL,
                    )
            except IOError as exc:
                self._trace.record(
                    IOTraceKind.OBSERVATION,
                    success=False,
                    path=path,
                    code=exc.code.value,
                    detail={"op": op, "error": exc.to_record()},
                )
        return self._trace.canonical_records()

    def run_reference_trace_suite(self) -> list[dict[str, Any]]:
        """Run the closed acceptance schedule and return canonical traces."""

        return self.run_trace(REFERENCE_IO_SCHEDULE)

    def to_record(self) -> dict[str, Any]:
        with self._lock:
            return {
                "schema": self.SCHEMA,
                "contract_version": self.CONTRACT_VERSION,
                "schema_version": SCHEMA_VERSION,
                "chunk_bytes": self._chunk_bytes,
                "open_sessions": self.open_count,
                "dirty_bytes": self._total_dirty,
                "trace": self._trace.to_records(),
            }


# ---------------------------------------------------------------------------
# Pure reference model (oracle)
# ---------------------------------------------------------------------------


@dataclass
class _RefFile:
    content: bytearray = field(default_factory=bytearray)


@dataclass
class _RefSession:
    session_id: int
    generation: int
    path: str
    append: bool
    readable: bool
    writable: bool
    released: bool = False
    dirty: bytearray = field(default_factory=bytearray)
    dirty_size: int = 0
    base_size: int = 0
    extents: list[DirtyExtent] = field(default_factory=list)
    extent_seq: int = 0
    dirty_bytes: int = 0


class OffsetIOReferenceModel:
    """Pure in-memory oracle for offset I/O reference traces.

    Does not use ranged storage. Produces the same *canonical* trace detail
    shapes as :class:`OffsetIORuntime` for the closed schedule vocabulary so
    acceptance tests can match traces without depending on backend identity.
    """

    SCHEMA: ClassVar[str] = IO_REFERENCE_MODEL_SCHEMA
    CONTRACT_VERSION: ClassVar[int] = CONTRACT_VERSION

    def __init__(self, *, chunk_bytes: int = DEFAULT_CHUNK_BYTES) -> None:
        self._chunk_bytes = chunk_bytes
        self._files: dict[str, _RefFile] = {}
        self._sessions: dict[int, _RefSession] = {}
        self._next_id = MIN_SESSION_ID
        self._generations: dict[int, int] = {}
        self._trace = IOTraceLog()
        self._lock = threading.RLock()

    @property
    def trace(self) -> IOTraceLog:
        return self._trace

    @property
    def chunk_bytes(self) -> int:
        return self._chunk_bytes

    def run_trace(
        self,
        schedule: Sequence[Mapping[str, Any]],
        *,
        clear_trace: bool = True,
    ) -> list[dict[str, Any]]:
        if clear_trace:
            self._trace.clear()
            self._files.clear()
            self._sessions.clear()
            self._next_id = MIN_SESSION_ID
            self._generations.clear()
        aliases: dict[str, int] = {}
        for step in schedule:
            op = str(step.get("op", ""))
            path = str(step.get("path", ""))
            key = str(step.get("session", path or "s0"))
            try:
                if op == TRACE_OP_SEED:
                    data = step.get("data", b"")
                    if isinstance(data, str):
                        data = data.encode("utf-8")
                    size_bytes = step.get("size_bytes")
                    pattern = step.get("pattern", b"\x00")
                    if isinstance(pattern, str):
                        pattern = pattern.encode("utf-8")
                    if size_bytes is not None:
                        pat = bytes(pattern) or b"\x00"
                        body = (pat * ((int(size_bytes) // len(pat)) + 1))[: int(size_bytes)]
                    else:
                        body = bytes(data)
                    self._files[path] = _RefFile(content=bytearray(body))
                    self._trace.record(
                        IOTraceKind.SEED,
                        success=True,
                        path=path,
                        detail={"size_bytes": len(body), "op": TRACE_OP_SEED},
                    )
                elif op == TRACE_OP_OPEN:
                    flags = step.get("flags", (OpenFlag.O_RDWR,))
                    if isinstance(flags, str):
                        flags = (OpenFlag(flags),)
                    norm = _normalize_flags(flags)
                    append = OpenFlag.O_APPEND in norm
                    creat = OpenFlag.O_CREAT in norm
                    trunc = OpenFlag.O_TRUNC in norm
                    readable, writable = _access_mode(norm)
                    exists = path in self._files
                    if not exists and not creat:
                        raise IOError(
                            f"path not found: {path!r}",
                            code=IOErrorCode.NOT_FOUND,
                            errno=HostErrno.ENOENT,
                            path=path,
                        )
                    if not exists:
                        self._files[path] = _RefFile()
                        kind = IOTraceKind.CREATE
                    else:
                        kind = IOTraceKind.OPEN
                    base = self._files[path]
                    if trunc and writable:
                        base.content = bytearray()
                    base_size = len(base.content)
                    sid = self._next_id
                    self._next_id += 1
                    gen = self._generations.get(sid, 0) + 1
                    self._generations[sid] = gen
                    sess = _RefSession(
                        session_id=sid,
                        generation=gen,
                        path=path,
                        append=append,
                        readable=readable,
                        writable=writable,
                        dirty=bytearray(base.content),
                        dirty_size=base_size,
                        base_size=base_size,
                    )
                    self._sessions[sid] = sess
                    aliases[key] = sid
                    self._trace.record(
                        kind,
                        success=True,
                        session_id=sid,
                        generation=gen,
                        path=path,
                        detail={
                            "op": TRACE_OP_OPEN,
                            "append": append,
                            "truncate": trunc,
                            "create": creat and not exists,
                            "logical_size": base_size,
                            "flags": [f.value for f in norm],
                        },
                    )
                elif op == TRACE_OP_WRITE:
                    sid = aliases[key]
                    sess = self._sessions[sid]
                    data = step.get("data", b"")
                    if isinstance(data, str):
                        data = data.encode("utf-8")
                    payload = bytes(data)
                    write_offset = sess.dirty_size if sess.append else int(step.get("offset", 0))
                    hole_before = max(0, write_offset - sess.dirty_size)
                    sparse = write_offset > sess.dirty_size
                    # Extend dirty buffer.
                    end = write_offset + len(payload)
                    if end > len(sess.dirty):
                        sess.dirty.extend(b"\x00" * (end - len(sess.dirty)))
                    if write_offset > sess.dirty_size:
                        # hole already zero-filled by extend
                        pass
                    if payload:
                        sess.dirty[write_offset:end] = payload
                    sess.dirty_size = max(sess.dirty_size, end if payload else max(sess.dirty_size, write_offset))
                    if not payload and write_offset > sess.dirty_size:
                        sess.dirty_size = write_offset
                    sess.extent_seq += 1
                    sess.extents.append(
                        DirtyExtent(
                            offset=write_offset,
                            length=len(payload),
                            data=payload,
                            sequence=sess.extent_seq,
                        )
                    )
                    sess.dirty_bytes += len(payload)
                    zero_length = len(payload) == 0
                    if sparse:
                        self._trace.record(
                            IOTraceKind.HOLE,
                            success=True,
                            session_id=sid,
                            generation=sess.generation,
                            path=path,
                            detail={
                                "hole_before": hole_before,
                                "offset": write_offset,
                                "logical_size": sess.dirty_size,
                            },
                        )
                    if zero_length:
                        self._trace.record(
                            IOTraceKind.ZERO_LENGTH,
                            success=True,
                            session_id=sid,
                            generation=sess.generation,
                            path=path,
                            detail={"op": TRACE_OP_WRITE, "offset": write_offset},
                        )
                    kind = IOTraceKind.APPEND if sess.append else IOTraceKind.WRITE
                    self._trace.record(
                        kind,
                        success=True,
                        session_id=sid,
                        generation=sess.generation,
                        path=path,
                        detail={
                            "op": TRACE_OP_WRITE,
                            "offset": write_offset,
                            "length": len(payload),
                            "append": sess.append,
                            "sparse": sparse,
                            "hole_before": hole_before,
                            "logical_size": sess.dirty_size,
                            "dirty_in_session_only": True,
                            "sequence": sess.extent_seq,
                            "zero_length": zero_length,
                        },
                    )
                elif op == TRACE_OP_READ:
                    sid = aliases[key]
                    sess = self._sessions[sid]
                    off = int(step.get("offset", 0))
                    length = int(step.get("length", 0))
                    logical = sess.dirty_size
                    if length == 0:
                        self._trace.record(
                            IOTraceKind.ZERO_LENGTH,
                            success=True,
                            session_id=sid,
                            generation=sess.generation,
                            path=path,
                            detail={"op": TRACE_OP_READ, "offset": off},
                        )
                        self._trace.record(
                            IOTraceKind.READ,
                            success=True,
                            session_id=sid,
                            generation=sess.generation,
                            path=path,
                            detail={
                                "op": TRACE_OP_READ,
                                "offset": off,
                                "length": 0,
                                "bytes": 0,
                                "logical_size": logical,
                                "zero_length": True,
                                "ranges_loaded": [],
                                "chunks_touched": 0,
                            },
                        )
                        continue
                    if off >= logical:
                        self._trace.record(
                            IOTraceKind.EOF,
                            success=True,
                            session_id=sid,
                            generation=sess.generation,
                            path=path,
                            detail={"offset": off, "logical_size": logical},
                        )
                        self._trace.record(
                            IOTraceKind.READ,
                            success=True,
                            session_id=sid,
                            generation=sess.generation,
                            path=path,
                            detail={
                                "op": TRACE_OP_READ,
                                "offset": off,
                                "length": length,
                                "bytes": 0,
                                "logical_size": logical,
                                "eof": True,
                                "ranges_loaded": [],
                                "chunks_touched": 0,
                            },
                        )
                        continue
                    need = min(logical, off + length) - off
                    short_read = need < length
                    # Reference model: "load" only uncovered ranges (simulated).
                    covered = bytearray(need)
                    for ext in sess.extents:
                        if not ext.overlaps(off, need):
                            continue
                        start = max(ext.offset, off)
                        stop = min(ext.end, off + need)
                        for i in range(start, stop):
                            covered[i - off] = 1
                    ranges_loaded: list[list[int]] = []
                    chunks_touched = 0
                    i = 0
                    while i < need:
                        if covered[i]:
                            i += 1
                            continue
                        j = i + 1
                        while j < need and not covered[j]:
                            j += 1
                        loff, llen = off + i, j - i
                        # Only load within base_size.
                        if loff < sess.base_size:
                            take = min(llen, sess.base_size - loff)
                            if take > 0:
                                first, last = _chunk_span(loff, take, self._chunk_bytes)
                                ct = max(0, last - first + 1)
                                ranges_loaded.append([loff, take])
                                chunks_touched += ct
                                self._trace.record(
                                    IOTraceKind.BACKEND_LOAD,
                                    success=True,
                                    session_id=sid,
                                    generation=sess.generation,
                                    path=path,
                                    detail={
                                        "offset": loff,
                                        "length": take,
                                        "chunks_touched": ct,
                                    },
                                )
                        i = j
                    data = bytes(sess.dirty[off : off + need])
                    if short_read:
                        self._trace.record(
                            IOTraceKind.EOF,
                            success=True,
                            session_id=sid,
                            generation=sess.generation,
                            path=path,
                            detail={
                                "offset": off,
                                "requested": length,
                                "returned": need,
                                "logical_size": logical,
                            },
                        )
                    own = any(ext.overlaps(off, need) for ext in sess.extents)
                    self._trace.record(
                        IOTraceKind.READ,
                        success=True,
                        session_id=sid,
                        generation=sess.generation,
                        path=path,
                        detail={
                            "op": TRACE_OP_READ,
                            "offset": off,
                            "length": length,
                            "bytes": len(data),
                            "logical_size": logical,
                            "read_own_writes": own or bool(sess.extents),
                            "ranges_loaded": ranges_loaded,
                            "chunks_touched": chunks_touched,
                            "short_read": short_read,
                            "eof": short_read,
                            "dirty_in_session_only": bool(sess.extents),
                        },
                    )
                elif op == TRACE_OP_TRUNCATE:
                    sid = aliases[key]
                    sess = self._sessions[sid]
                    size = int(step.get("size", 0))
                    prev = sess.dirty_size
                    if size < prev:
                        sess.dirty = sess.dirty[:size]
                        kept: list[DirtyExtent] = []
                        for ext in sess.extents:
                            if ext.offset >= size:
                                continue
                            if ext.end <= size:
                                kept.append(ext)
                            else:
                                clipped = ext.data[: max(0, size - ext.offset)]
                                kept.append(
                                    DirtyExtent(
                                        offset=ext.offset,
                                        length=len(clipped),
                                        data=clipped,
                                        sequence=ext.sequence,
                                    )
                                )
                        sess.extents = kept
                        sess.dirty_bytes = sum(e.length for e in kept)
                    elif size > len(sess.dirty):
                        sess.dirty.extend(b"\x00" * (size - len(sess.dirty)))
                    sess.dirty_size = size
                    self._trace.record(
                        IOTraceKind.TRUNCATE,
                        success=True,
                        session_id=sid,
                        generation=sess.generation,
                        path=path,
                        detail={
                            "op": TRACE_OP_TRUNCATE,
                            "size": size,
                            "previous_size": prev,
                            "grew": size > prev,
                            "shrank": size < prev,
                            "dirty_in_session_only": True,
                        },
                    )
                elif op == TRACE_OP_FLUSH:
                    sid = aliases[key]
                    sess = self._sessions[sid]
                    commit = bool(step.get("commit", True))
                    if not commit:
                        result = {
                            "session_id": sid,
                            "generation": sess.generation,
                            "success": True,
                            "committed_bytes": 0,
                            "extents_assembled": len(sess.extents),
                            "ranges_written": [],
                            "deferred_error": False,
                            "error_code": "",
                            "errno": HostErrno.OK.value,
                            "dirty_leaked": False,
                            "durable": False,
                            "detail": {
                                "commit": False,
                                "dirty_bytes": sess.dirty_bytes,
                            },
                        }
                        self._trace.record(
                            IOTraceKind.FLUSH,
                            success=True,
                            session_id=sid,
                            generation=sess.generation,
                            path=path,
                            detail=result,
                        )
                        continue
                    if not sess.extents and sess.dirty_size == sess.base_size:
                        result = {
                            "session_id": sid,
                            "generation": sess.generation,
                            "success": True,
                            "committed_bytes": 0,
                            "extents_assembled": 0,
                            "ranges_written": [],
                            "deferred_error": False,
                            "error_code": "",
                            "errno": HostErrno.OK.value,
                            "dirty_leaked": False,
                            "durable": False,
                            "detail": {"noop": True},
                        }
                        self._trace.record(
                            IOTraceKind.FLUSH,
                            success=True,
                            session_id=sid,
                            generation=sess.generation,
                            path=path,
                            detail=result,
                        )
                        continue
                    runs = _coalesce_dirty_ranges(sess.extents)
                    truncate = sess.dirty_size < sess.base_size or (
                        sess.dirty_size == 0 and sess.base_size > 0
                    )
                    ranges_written: list[list[int]] = []
                    if truncate and sess.dirty_size > 0:
                        ranges_written.append([0, sess.dirty_size])
                    else:
                        max_end = 0
                        for off, length, _data in runs:
                            if length > 0:
                                ranges_written.append([off, length])
                                max_end = max(max_end, off + length)
                        if sess.dirty_size > max(sess.base_size, max_end):
                            ranges_written.append([sess.dirty_size - 1, 1])
                    self._trace.record(
                        IOTraceKind.ASSEMBLE,
                        success=True,
                        session_id=sid,
                        generation=sess.generation,
                        path=path,
                        detail={
                            "extents_assembled": len(sess.extents),
                            "ranges_written": ranges_written,
                            "truncate": truncate,
                            "logical_size": sess.dirty_size,
                        },
                    )
                    # Commit into reference file.
                    file = self._files.setdefault(sess.path, _RefFile())
                    if truncate:
                        file.content = bytearray(sess.dirty[: sess.dirty_size])
                    else:
                        if sess.dirty_size > len(file.content):
                            file.content.extend(
                                b"\x00" * (sess.dirty_size - len(file.content))
                            )
                        for off, length, data in runs:
                            end = off + length
                            if end > len(file.content):
                                file.content.extend(b"\x00" * (end - len(file.content)))
                            file.content[off:end] = data
                        file.content = file.content[: sess.dirty_size]
                    committed = sess.dirty_bytes
                    self._trace.record(
                        IOTraceKind.BACKEND_COMMIT,
                        success=True,
                        session_id=sid,
                        generation=sess.generation,
                        path=path,
                        detail={
                            "committed_bytes": committed,
                            "size_bytes": sess.dirty_size,
                            "generation": 0,
                        },
                    )
                    sess.extents.clear()
                    sess.dirty_bytes = 0
                    sess.base_size = sess.dirty_size
                    sess.dirty = bytearray(file.content)
                    result = {
                        "session_id": sid,
                        "generation": sess.generation,
                        "success": True,
                        "committed_bytes": committed,
                        "extents_assembled": len(ranges_written),
                        "ranges_written": ranges_written,
                        "deferred_error": False,
                        "error_code": "",
                        "errno": HostErrno.OK.value,
                        "dirty_leaked": False,
                        "durable": True,
                        "detail": {"logical_size": sess.dirty_size},
                    }
                    self._trace.record(
                        IOTraceKind.FLUSH,
                        success=True,
                        session_id=sid,
                        generation=sess.generation,
                        path=path,
                        detail=result,
                    )
                elif op == TRACE_OP_RELEASE:
                    sid = aliases[key]
                    sess = self._sessions[sid]
                    sess.released = True
                    sess.extents.clear()
                    sess.dirty_bytes = 0
                    rec = {
                        "session_id": sid,
                        "generation": sess.generation,
                        "success": True,
                        "already_released": False,
                        "discarded_dirty": True,
                        "dirty_leaked": False,
                    }
                    self._trace.record(
                        IOTraceKind.RELEASE,
                        success=True,
                        session_id=sid,
                        generation=sess.generation,
                        path=path,
                        detail=rec,
                    )
                elif op == TRACE_OP_STAT:
                    body = self._files.get(path, _RefFile()).content
                    self._trace.record(
                        IOTraceKind.STAT,
                        success=True,
                        path=path,
                        detail={"op": TRACE_OP_STAT, "size_bytes": len(body)},
                    )
                else:
                    raise IOError(
                        f"unknown schedule op: {op!r}",
                        code=IOErrorCode.INTERNAL,
                    )
            except IOError as exc:
                self._trace.record(
                    IOTraceKind.OBSERVATION,
                    success=False,
                    path=path,
                    code=exc.code.value,
                    detail={"op": op, "error": exc.to_record()},
                )
        return self._trace.canonical_records()

    def run_reference_trace_suite(self) -> list[dict[str, Any]]:
        return self.run_trace(REFERENCE_IO_SCHEDULE)


# ---------------------------------------------------------------------------
# Closed acceptance schedule (shared by runtime + reference model)
# ---------------------------------------------------------------------------

REFERENCE_IO_SCHEDULE: Final[tuple[dict[str, Any], ...]] = (
    # Seed a small base file.
    {"op": TRACE_OP_SEED, "path": "io/base.bin", "data": b"ABCDEFGH"},
    # Offset read of mid-range only.
    {
        "op": TRACE_OP_OPEN,
        "path": "io/base.bin",
        "session": "r0",
        "flags": (OpenFlag.O_RDONLY,),
    },
    {
        "op": TRACE_OP_READ,
        "path": "io/base.bin",
        "session": "r0",
        "offset": 2,
        "length": 4,
    },
    {"op": TRACE_OP_RELEASE, "path": "io/base.bin", "session": "r0"},
    # Overlapping / random / short writes + read-own-writes.
    {
        "op": TRACE_OP_OPEN,
        "path": "io/rand.bin",
        "session": "w0",
        "flags": (OpenFlag.O_RDWR, OpenFlag.O_CREAT),
    },
    {
        "op": TRACE_OP_WRITE,
        "path": "io/rand.bin",
        "session": "w0",
        "offset": 0,
        "data": b"AAAA",
    },
    {
        "op": TRACE_OP_WRITE,
        "path": "io/rand.bin",
        "session": "w0",
        "offset": 10,
        "data": b"BBBB",
    },
    {
        "op": TRACE_OP_WRITE,
        "path": "io/rand.bin",
        "session": "w0",
        "offset": 4,
        "data": b"CC",
    },
    {
        "op": TRACE_OP_READ,
        "path": "io/rand.bin",
        "session": "w0",
        "offset": 0,
        "length": 14,
    },
    # Sparse hole past EOF.
    {
        "op": TRACE_OP_WRITE,
        "path": "io/rand.bin",
        "session": "w0",
        "offset": 100,
        "data": b"Z",
    },
    {
        "op": TRACE_OP_READ,
        "path": "io/rand.bin",
        "session": "w0",
        "offset": 50,
        "length": 4,
    },
    # Zero-length write + read.
    {
        "op": TRACE_OP_WRITE,
        "path": "io/rand.bin",
        "session": "w0",
        "offset": 0,
        "data": b"",
    },
    {
        "op": TRACE_OP_READ,
        "path": "io/rand.bin",
        "session": "w0",
        "offset": 0,
        "length": 0,
    },
    # Truncate shrink then grow.
    {
        "op": TRACE_OP_TRUNCATE,
        "path": "io/rand.bin",
        "session": "w0",
        "size": 6,
    },
    {
        "op": TRACE_OP_READ,
        "path": "io/rand.bin",
        "session": "w0",
        "offset": 0,
        "length": 10,
    },
    {
        "op": TRACE_OP_TRUNCATE,
        "path": "io/rand.bin",
        "session": "w0",
        "size": 12,
    },
    {
        "op": TRACE_OP_READ,
        "path": "io/rand.bin",
        "session": "w0",
        "offset": 6,
        "length": 6,
    },
    # Flush assembly commit.
    {
        "op": TRACE_OP_FLUSH,
        "path": "io/rand.bin",
        "session": "w0",
        "commit": True,
    },
    # EOF short read after commit.
    {
        "op": TRACE_OP_READ,
        "path": "io/rand.bin",
        "session": "w0",
        "offset": 100,
        "length": 4,
    },
    {"op": TRACE_OP_RELEASE, "path": "io/rand.bin", "session": "w0"},
    # Append serialization path.
    {"op": TRACE_OP_SEED, "path": "io/app.bin", "data": b"base"},
    {
        "op": TRACE_OP_OPEN,
        "path": "io/app.bin",
        "session": "a0",
        "flags": (OpenFlag.O_WRONLY, OpenFlag.O_APPEND),
    },
    {
        "op": TRACE_OP_WRITE,
        "path": "io/app.bin",
        "session": "a0",
        "offset": 0,
        "data": b"!",
    },
    {
        "op": TRACE_OP_WRITE,
        "path": "io/app.bin",
        "session": "a0",
        "offset": 999,
        "data": b"?",
    },
    {
        "op": TRACE_OP_FLUSH,
        "path": "io/app.bin",
        "session": "a0",
        "commit": True,
    },
    {"op": TRACE_OP_RELEASE, "path": "io/app.bin", "session": "a0"},
)


def build_reference_trace() -> list[dict[str, Any]]:
    """Build the canonical reference trace from the pure oracle."""

    return OffsetIOReferenceModel().run_reference_trace_suite()


# ---------------------------------------------------------------------------
# Module exports
# ---------------------------------------------------------------------------

__all__ = [
    "CONTRACT_VERSION",
    "SCHEMA_VERSION",
    "OFFSET_IO_RUNTIME_SCHEMA",
    "IO_REFERENCE_MODEL_SCHEMA",
    "DIRTY_EXTENT_SCHEMA",
    "IO_TRACE_SCHEMA",
    "IO_SESSION_SCHEMA",
    "OffsetIORuntime_V1",
    "IOReferenceModel_V1",
    "DirtyExtent_V1",
    "DEFAULT_CHUNK_BYTES",
    "DEFAULT_MAX_OPEN_SESSIONS",
    "DEFAULT_MAX_DIRTY_BYTES",
    "WHOLE_OBJECT_THRESHOLD_BYTES",
    "REFERENCE_IO_SCHEDULE",
    "IOErrorCode",
    "IOError",
    "IOTraceKind",
    "IOTraceStep",
    "IOTraceLog",
    "DirtyExtent",
    "IOSession",
    "IOResult",
    "TruncateResult",
    "FlushAssemblyResult",
    "LoadedRange",
    "InstrumentingStorage",
    "OffsetIORuntime",
    "OffsetIOReferenceModel",
    "build_reference_trace",
    "traces_match",
    "ranges_cover_only_requested",
]
