"""Bounded generation-tagged file handles and per-handle staged extents (KVFS-204).

This module owns the kernel-shaped *handle plane* for the common VFS runtime:

* generation-tagged, bounded open-file identities (handles, not paths);
* open/create flag semantics for ``O_CREAT`` / ``O_EXCL`` / ``O_TRUNC`` /
  ``O_APPEND``;
* per-handle dirty staged extents (never admitted to shared ARC);
* read-own-writes over staged extents merged with committed base content;
* deferred write errors returned consistently by ``flush``;
* idempotent ``flush`` / ``release``;
* stale-handle rejection by generation mismatch or release;
* rename / unlink while open without invalidating live handles;
* orphan reclamation (expired leases, released slots, unlinked zero-nlink
  inodes); and
* explicit pressure behaviour when open-handle or stage-byte bounds are hit.

Shared cache admission and WAL durability effects remain out of scope
(KVFS-300 / KVFS-400). This module does not import fusepy, open host mounts,
or perform network I/O.

Interfaces (plan aliases): ``HandleTable@1``, ``FileHandle@1``,
``StagedExtent@1``.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Mapping, MutableMapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar, Final

from ipfs_kit_py.core.vfs.host_contracts import (
    MAX_HANDLE_ID,
    MAX_IO_LENGTH,
    MAX_OFFSET,
    MAX_SAFE_INTEGER,
    MAX_SIZE_BYTES,
    HostErrno,
    OpenFlag,
)

# ---------------------------------------------------------------------------
# Schema / version / bounds
# ---------------------------------------------------------------------------

CONTRACT_VERSION: Final[int] = 1
SCHEMA_MAJOR: Final[int] = 1
SCHEMA_MINOR: Final[int] = 0
SCHEMA_PATCH: Final[int] = 0
SCHEMA_VERSION: Final[str] = f"{SCHEMA_MAJOR}.{SCHEMA_MINOR}.{SCHEMA_PATCH}"

HANDLES_MODULE_NAMESPACE: Final[str] = "ipfs_kit_py/core/vfs/handles"

HANDLE_TABLE_SCHEMA: Final[str] = (
    f"{HANDLES_MODULE_NAMESPACE}/handle-table@{SCHEMA_MAJOR}"
)
FILE_HANDLE_SCHEMA: Final[str] = (
    f"{HANDLES_MODULE_NAMESPACE}/file-handle@{SCHEMA_MAJOR}"
)
STAGED_EXTENT_SCHEMA: Final[str] = (
    f"{HANDLES_MODULE_NAMESPACE}/staged-extent@{SCHEMA_MAJOR}"
)
HANDLE_TRACE_SCHEMA: Final[str] = (
    f"{HANDLES_MODULE_NAMESPACE}/handle-trace@{SCHEMA_MAJOR}"
)
HANDLE_PRESSURE_SCHEMA: Final[str] = (
    f"{HANDLES_MODULE_NAMESPACE}/handle-pressure@{SCHEMA_MAJOR}"
)
INODE_RECORD_SCHEMA: Final[str] = (
    f"{HANDLES_MODULE_NAMESPACE}/inode-record@{SCHEMA_MAJOR}"
)

# Public interface aliases.
HandleTable_V1: Final[str] = HANDLE_TABLE_SCHEMA
FileHandle_V1: Final[str] = FILE_HANDLE_SCHEMA
StagedExtent_V1: Final[str] = STAGED_EXTENT_SCHEMA

DEFAULT_CHUNK_BYTES: Final[int] = 4_096
DEFAULT_MAX_OPEN_HANDLES: Final[int] = 1_024
DEFAULT_MAX_STAGED_BYTES: Final[int] = 64 * 1024 * 1024  # 64 MiB total dirty
DEFAULT_MAX_STAGED_BYTES_PER_HANDLE: Final[int] = 16 * 1024 * 1024  # 16 MiB
DEFAULT_MAX_EXTENTS_PER_HANDLE: Final[int] = 4_096
DEFAULT_LEASE_MS: Final[int] = 300_000
MAX_TRACE_STEPS: Final[int] = 4_096
MAX_OPEN_HANDLES_HARD: Final[int] = 65_536
MAX_INODES: Final[int] = 1_048_576
MIN_HANDLE_ID: Final[int] = 1
MIN_INODE: Final[int] = 1
ROOT_INODE: Final[int] = 1

# Access-mode flags (exactly one required).
_ACCESS_FLAGS: Final[frozenset[OpenFlag]] = frozenset(
    {OpenFlag.O_RDONLY, OpenFlag.O_WRONLY, OpenFlag.O_RDWR}
)
_CREATE_FLAGS: Final[frozenset[OpenFlag]] = frozenset(
    {
        OpenFlag.O_CREAT,
        OpenFlag.O_EXCL,
        OpenFlag.O_TRUNC,
        OpenFlag.O_APPEND,
        OpenFlag.O_NONBLOCK,
        OpenFlag.O_SYNC,
        OpenFlag.O_DIRECTORY,
        OpenFlag.O_NOFOLLOW,
    }
)
_ADMITTED_FLAGS: Final[frozenset[OpenFlag]] = _ACCESS_FLAGS | _CREATE_FLAGS


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class HandleErrorCode(str, Enum):
    """Stable handle-plane error codes."""

    NOT_FOUND = "HANDLE_NOT_FOUND"
    STALE = "HANDLE_STALE"
    RELEASED = "HANDLE_RELEASED"
    ALREADY_EXISTS = "HANDLE_ALREADY_EXISTS"
    IS_DIRECTORY = "HANDLE_IS_DIRECTORY"
    NOT_DIRECTORY = "HANDLE_NOT_DIRECTORY"
    BAD_FLAGS = "HANDLE_BAD_FLAGS"
    PERMISSION = "HANDLE_PERMISSION"
    INVALID_OFFSET = "HANDLE_INVALID_OFFSET"
    INVALID_LENGTH = "HANDLE_INVALID_LENGTH"
    BOUND_EXCEEDED = "HANDLE_BOUND_EXCEEDED"
    PRESSURE = "HANDLE_PRESSURE"
    DEFERRED_ERROR = "HANDLE_DEFERRED_ERROR"
    LEASE_EXPIRED = "HANDLE_LEASE_EXPIRED"
    INODE_EXHAUSTED = "HANDLE_INODE_EXHAUSTED"
    HANDLE_EXHAUSTED = "HANDLE_HANDLE_EXHAUSTED"
    PATH_CONFLICT = "HANDLE_PATH_CONFLICT"
    INTERNAL = "HANDLE_INTERNAL"


class HandleError(Exception):
    """Fail-closed handle-plane error with stable code and optional errno."""

    def __init__(
        self,
        message: str,
        *,
        code: HandleErrorCode,
        errno: HostErrno = HostErrno.EINVAL,
        handle_id: int = 0,
        generation: int = 0,
        path: str = "",
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code if isinstance(code, HandleErrorCode) else HandleErrorCode(code)
        self.errno = errno if isinstance(errno, HostErrno) else HostErrno(errno)
        self.handle_id = int(handle_id)
        self.generation = int(generation)
        self.path = path
        self.detail = dict(detail or {})

    def to_record(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "message": self.message,
            "errno": self.errno.value,
            "handle_id": self.handle_id,
            "generation": self.generation,
            "path": self.path,
            "detail": dict(self.detail),
        }


# ---------------------------------------------------------------------------
# Trace / pressure observations
# ---------------------------------------------------------------------------


class HandleTraceKind(str, Enum):
    """Closed vocabulary for handle-plane executable traces."""

    OPEN = "open"
    CREATE = "create"
    READ = "read"
    WRITE = "write"
    TRUNCATE = "truncate"
    FLUSH = "flush"
    FSYNC = "fsync"
    RELEASE = "release"
    RENAME = "rename"
    UNLINK = "unlink"
    RECLAIM = "reclaim"
    PRESSURE = "pressure"
    DEFERRED = "deferred"
    STALE = "stale"
    STAGE = "stage"
    COMMIT = "commit"
    OBSERVATION = "observation"


@dataclass(frozen=True)
class HandleTraceStep:
    """One immutable, executable handle-plane trace step."""

    SCHEMA: ClassVar[str] = HANDLE_TRACE_SCHEMA

    kind: HandleTraceKind
    success: bool
    handle_id: int = 0
    generation: int = 0
    path: str = ""
    code: str = ""
    detail: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.kind, HandleTraceKind):
            object.__setattr__(self, "kind", HandleTraceKind(self.kind))
        if not isinstance(self.success, bool):
            raise HandleError(
                "trace step success must be a boolean",
                code=HandleErrorCode.INTERNAL,
            )
        if not isinstance(self.detail, Mapping):
            raise HandleError(
                "trace step detail must be a mapping",
                code=HandleErrorCode.INTERNAL,
            )
        object.__setattr__(self, "detail", dict(self.detail))

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "kind": self.kind.value,
            "success": self.success,
            "handle_id": self.handle_id,
            "generation": self.generation,
            "path": self.path,
            "code": self.code,
            "detail": dict(self.detail),
        }


class HandleTraceLog:
    """Bounded append-only trace log for handle evidence."""

    __slots__ = ("_steps", "_max_steps")

    def __init__(self, *, max_steps: int = MAX_TRACE_STEPS) -> None:
        if max_steps < 1 or max_steps > MAX_TRACE_STEPS:
            raise HandleError(
                f"max_steps must be in [1, {MAX_TRACE_STEPS}]",
                code=HandleErrorCode.INTERNAL,
            )
        self._steps: list[HandleTraceStep] = []
        self._max_steps = max_steps

    def append(self, step: HandleTraceStep) -> HandleTraceStep:
        if len(self._steps) >= self._max_steps:
            # Drop oldest under pressure rather than failing I/O paths.
            del self._steps[0]
        self._steps.append(step)
        return step

    def record(
        self,
        kind: HandleTraceKind,
        *,
        success: bool,
        handle_id: int = 0,
        generation: int = 0,
        path: str = "",
        code: str = "",
        detail: Mapping[str, Any] | None = None,
    ) -> HandleTraceStep:
        return self.append(
            HandleTraceStep(
                kind=kind,
                success=success,
                handle_id=handle_id,
                generation=generation,
                path=path,
                code=code,
                detail=dict(detail or {}),
            )
        )

    def clear(self) -> None:
        self._steps.clear()

    @property
    def steps(self) -> tuple[HandleTraceStep, ...]:
        return tuple(self._steps)

    def to_records(self) -> list[dict[str, Any]]:
        return [step.to_record() for step in self._steps]

    def kinds(self) -> list[str]:
        return [step.kind.value for step in self._steps]


@dataclass(frozen=True)
class HandlePressureState:
    """Explicit pressure observation for open handles and staged bytes."""

    SCHEMA: ClassVar[str] = HANDLE_PRESSURE_SCHEMA

    open_handles: int
    max_open_handles: int
    staged_bytes: int
    max_staged_bytes: int
    pressure: bool
    open_ratio: float
    staged_ratio: float
    reason: str = ""

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "open_handles": self.open_handles,
            "max_open_handles": self.max_open_handles,
            "staged_bytes": self.staged_bytes,
            "max_staged_bytes": self.max_staged_bytes,
            "pressure": self.pressure,
            "open_ratio": self.open_ratio,
            "staged_ratio": self.staged_ratio,
            "reason": self.reason,
        }


# ---------------------------------------------------------------------------
# Public records
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StagedExtent:
    """One dirty byte range staged on a single open handle.

    Holes are represented by absence of staged coverage over a range within
    the logical size; sparse writes past EOF extend size without materialising
    intermediate bytes until read (zero-fill).
    """

    SCHEMA: ClassVar[str] = STAGED_EXTENT_SCHEMA

    offset: int
    length: int
    data: bytes
    sequence: int = 0

    def __post_init__(self) -> None:
        if isinstance(self.offset, bool) or not isinstance(self.offset, int) or self.offset < 0:
            raise HandleError(
                "staged extent offset must be a non-negative integer",
                code=HandleErrorCode.INVALID_OFFSET,
            )
        if self.offset > MAX_OFFSET:
            raise HandleError(
                "staged extent offset exceeds bound",
                code=HandleErrorCode.BOUND_EXCEEDED,
            )
        if not isinstance(self.data, (bytes, bytearray)):
            raise HandleError(
                "staged extent data must be bytes",
                code=HandleErrorCode.INTERNAL,
            )
        payload = bytes(self.data)
        if len(payload) != self.length:
            object.__setattr__(self, "length", len(payload))
        else:
            object.__setattr__(self, "length", int(self.length))
        object.__setattr__(self, "data", payload)
        if self.length > MAX_IO_LENGTH:
            raise HandleError(
                "staged extent length exceeds I/O bound",
                code=HandleErrorCode.BOUND_EXCEEDED,
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
class FileHandle:
    """Generation-tagged open file handle identity (immutable view).

    Handles, not paths, identify open instances. Rename or unlink must not
    invalidate an already-open handle. ``release`` is idempotent.
    """

    SCHEMA: ClassVar[str] = FILE_HANDLE_SCHEMA

    handle_id: int
    generation: int
    inode: int
    flags: tuple[OpenFlag, ...]
    path_at_open: str
    current_path: str
    mount_id: str = "mount:default"
    lease_id: str = ""
    lease_expires_at_ms: int = 0
    released: bool = False
    unlinked: bool = False
    append: bool = False
    readable: bool = True
    writable: bool = False
    created: bool = False
    truncated_on_open: bool = False
    staged_bytes: int = 0
    logical_size: int = 0
    deferred_error_code: str = ""
    deferred_errno: str = ""

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "handle_id": self.handle_id,
            "generation": self.generation,
            "inode": self.inode,
            "flags": [f.value for f in self.flags],
            "path_at_open": self.path_at_open,
            "current_path": self.current_path,
            "mount_id": self.mount_id,
            "lease_id": self.lease_id,
            "lease_expires_at_ms": self.lease_expires_at_ms,
            "released": self.released,
            "unlinked": self.unlinked,
            "append": self.append,
            "readable": self.readable,
            "writable": self.writable,
            "created": self.created,
            "truncated_on_open": self.truncated_on_open,
            "staged_bytes": self.staged_bytes,
            "logical_size": self.logical_size,
            "deferred_error_code": self.deferred_error_code,
            "deferred_errno": self.deferred_errno,
        }


@dataclass(frozen=True)
class HandleIOResult:
    """Result of a read or write against a live handle."""

    handle_id: int
    generation: int
    offset: int
    length: int
    bytes_transferred: int
    data: bytes = b""
    logical_size: int = 0
    staged: bool = False
    sparse: bool = False
    hole_before: int = 0
    dirty_in_handle_only: bool = False
    read_own_writes: bool = False

    def to_record(self) -> dict[str, Any]:
        return {
            "handle_id": self.handle_id,
            "generation": self.generation,
            "offset": self.offset,
            "length": self.length,
            "bytes_transferred": self.bytes_transferred,
            "logical_size": self.logical_size,
            "staged": self.staged,
            "sparse": self.sparse,
            "hole_before": self.hole_before,
            "dirty_in_handle_only": self.dirty_in_handle_only,
            "read_own_writes": self.read_own_writes,
            "data_len": len(self.data),
        }


@dataclass(frozen=True)
class FlushResult:
    """Result of flush / fsync. Deferred errors surface here consistently."""

    handle_id: int
    generation: int
    success: bool
    committed_bytes: int = 0
    deferred_error: bool = False
    error_code: str = ""
    errno: str = HostErrno.OK.value
    idempotent: bool = False
    durable: bool = False
    detail: Mapping[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return {
            "handle_id": self.handle_id,
            "generation": self.generation,
            "success": self.success,
            "committed_bytes": self.committed_bytes,
            "deferred_error": self.deferred_error,
            "error_code": self.error_code,
            "errno": self.errno,
            "idempotent": self.idempotent,
            "durable": self.durable,
            "detail": dict(self.detail),
        }


@dataclass(frozen=True)
class ReleaseResult:
    """Result of release. Always safe to call more than once."""

    handle_id: int
    generation: int
    success: bool
    already_released: bool = False
    reclaimed: bool = False
    orphaned_inode_reclaimed: bool = False
    deferred_error_cleared: bool = False
    detail: Mapping[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return {
            "handle_id": self.handle_id,
            "generation": self.generation,
            "success": self.success,
            "already_released": self.already_released,
            "reclaimed": self.reclaimed,
            "orphaned_inode_reclaimed": self.orphaned_inode_reclaimed,
            "deferred_error_cleared": self.deferred_error_cleared,
            "detail": dict(self.detail),
        }


@dataclass(frozen=True)
class ReclaimResult:
    """Bulk orphan / lease reclamation receipt."""

    reclaimed_handles: int
    reclaimed_inodes: int
    expired_leases: int
    detail: Mapping[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return {
            "reclaimed_handles": self.reclaimed_handles,
            "reclaimed_inodes": self.reclaimed_inodes,
            "expired_leases": self.expired_leases,
            "detail": dict(self.detail),
        }


# ---------------------------------------------------------------------------
# Internal mutable state
# ---------------------------------------------------------------------------


def _sha256_prefix(data: bytes, n: int = 16) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()[:n]


def _require_non_negative_int(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise HandleError(
            f"{name} must be a non-negative integer",
            code=HandleErrorCode.INVALID_OFFSET,
            detail={"field": name, "value": value},
        )
    return value


def _normalize_flags(flags: Sequence[OpenFlag | str] | OpenFlag | str | int | None) -> tuple[OpenFlag, ...]:
    """Normalize open flags into a sorted tuple of :class:`OpenFlag`."""

    if flags is None:
        raw: list[Any] = [OpenFlag.O_RDONLY]
    elif isinstance(flags, (OpenFlag, str)):
        raw = [flags]
    elif isinstance(flags, int):
        # Integer bitmasks are not admitted; require symbolic flags.
        raise HandleError(
            "integer open flags are not admitted; pass OpenFlag names",
            code=HandleErrorCode.BAD_FLAGS,
            errno=HostErrno.EINVAL,
            detail={"flags": flags},
        )
    else:
        raw = list(flags)

    parsed: list[OpenFlag] = []
    seen: set[OpenFlag] = set()
    for item in raw:
        if isinstance(item, OpenFlag):
            flag = item
        elif isinstance(item, str):
            try:
                flag = OpenFlag(item if item.startswith("O_") else f"O_{item}")
            except ValueError as exc:
                raise HandleError(
                    f"unknown open flag: {item!r}",
                    code=HandleErrorCode.BAD_FLAGS,
                    errno=HostErrno.EINVAL,
                    detail={"flag": item},
                ) from exc
        else:
            raise HandleError(
                f"invalid open flag type: {type(item).__name__}",
                code=HandleErrorCode.BAD_FLAGS,
                errno=HostErrno.EINVAL,
            )
        if flag not in _ADMITTED_FLAGS:
            raise HandleError(
                f"open flag not admitted: {flag.value}",
                code=HandleErrorCode.BAD_FLAGS,
                errno=HostErrno.EINVAL,
                detail={"flag": flag.value},
            )
        if flag not in seen:
            seen.add(flag)
            parsed.append(flag)

    access = [f for f in parsed if f in _ACCESS_FLAGS]
    if len(access) == 0:
        parsed.insert(0, OpenFlag.O_RDONLY)
    elif len(access) > 1:
        raise HandleError(
            "exactly one of O_RDONLY/O_WRONLY/O_RDWR is required",
            code=HandleErrorCode.BAD_FLAGS,
            errno=HostErrno.EINVAL,
            detail={"access_flags": [f.value for f in access]},
        )

    if OpenFlag.O_EXCL in parsed and OpenFlag.O_CREAT not in parsed:
        raise HandleError(
            "O_EXCL requires O_CREAT",
            code=HandleErrorCode.BAD_FLAGS,
            errno=HostErrno.EINVAL,
        )

    # Stable order: access first, then create flags alphabetically.
    access_flag = next(f for f in parsed if f in _ACCESS_FLAGS)
    others = sorted((f for f in parsed if f not in _ACCESS_FLAGS), key=lambda f: f.value)
    return (access_flag, *others)


def _access_mode(flags: Sequence[OpenFlag]) -> tuple[bool, bool]:
    """Return ``(readable, writable)`` from normalized flags."""

    if OpenFlag.O_RDONLY in flags:
        return True, False
    if OpenFlag.O_WRONLY in flags:
        return False, True
    if OpenFlag.O_RDWR in flags:
        return True, True
    return True, False


def _chunk_index(offset: int, chunk_bytes: int) -> int:
    return offset // chunk_bytes


def _write_into_chunks(
    chunks: MutableMapping[int, bytes],
    *,
    size_bytes: int,
    offset: int,
    data: bytes,
    chunk_bytes: int,
) -> int:
    """Write ``data`` at ``offset`` into a sparse chunk map; return new size."""

    if not data:
        return max(size_bytes, offset)
    end = offset + len(data)
    first = _chunk_index(offset, chunk_bytes)
    last = _chunk_index(end - 1, chunk_bytes)
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
) -> bytes:
    """Read a range from a sparse chunk map (holes → zero)."""

    if offset >= size_bytes or length <= 0:
        return b""
    end = min(size_bytes, offset + length)
    need = end - offset
    first = _chunk_index(offset, chunk_bytes)
    last = _chunk_index(offset + need - 1, chunk_bytes)
    out = bytearray()
    for index in range(first, last + 1):
        chunk_start = index * chunk_bytes
        chunk_end = chunk_start + chunk_bytes
        rel_start = max(offset, chunk_start) - chunk_start
        rel_end = min(end, chunk_end) - chunk_start
        existing = chunks.get(index)
        if existing is None:
            out.extend(b"\x00" * (rel_end - rel_start))
            continue
        piece = existing[rel_start:rel_end]
        if len(piece) < (rel_end - rel_start):
            piece = piece + b"\x00" * ((rel_end - rel_start) - len(piece))
        out.extend(piece)
    return bytes(out)


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


@dataclass
class _InodeState:
    """Committed inode content and namespace binding."""

    inode: int
    path: str
    is_directory: bool = False
    nlink: int = 1
    size_bytes: int = 0
    chunks: dict[int, bytes] = field(default_factory=dict)
    generation: int = 0  # content generation (bumped on commit)
    mount_id: str = "mount:default"
    unlinked: bool = False
    mode: int = 0o644
    open_count: int = 0

    def clone_chunks(self) -> dict[int, bytes]:
        return dict(self.chunks)


@dataclass
class _HandleState:
    """Mutable per-handle state including staged extents."""

    handle_id: int
    generation: int
    inode: int
    flags: tuple[OpenFlag, ...]
    path_at_open: str
    current_path: str
    mount_id: str
    lease_id: str
    lease_expires_at_ms: int
    readable: bool
    writable: bool
    append: bool
    created: bool
    truncated_on_open: bool
    released: bool = False
    unlinked: bool = False
    # Staged dirty state (never in shared ARC).
    staged: dict[int, bytes] = field(default_factory=dict)
    staged_size: int = 0  # logical size including staged writes
    staged_dirty_bytes: int = 0  # approximate dirty payload bytes
    extents: list[StagedExtent] = field(default_factory=list)
    extent_seq: int = 0
    dirty: bool = False
    # Deferred write error (returned consistently by flush).
    deferred_code: str = ""
    deferred_errno: str = ""
    deferred_message: str = ""
    flush_count: int = 0
    release_count: int = 0
    last_flush_committed: int = 0

    def view(self) -> FileHandle:
        return FileHandle(
            handle_id=self.handle_id,
            generation=self.generation,
            inode=self.inode,
            flags=self.flags,
            path_at_open=self.path_at_open,
            current_path=self.current_path,
            mount_id=self.mount_id,
            lease_id=self.lease_id,
            lease_expires_at_ms=self.lease_expires_at_ms,
            released=self.released,
            unlinked=self.unlinked,
            append=self.append,
            readable=self.readable,
            writable=self.writable,
            created=self.created,
            truncated_on_open=self.truncated_on_open,
            staged_bytes=self.staged_dirty_bytes,
            logical_size=self.staged_size,
            deferred_error_code=self.deferred_code,
            deferred_errno=self.deferred_errno,
        )


# ---------------------------------------------------------------------------
# Handle table
# ---------------------------------------------------------------------------


class HandleTable:
    """Bounded generation-tagged handle table with per-handle staged extents.

    This is the primary runtime surface for KVFS-204. Callers obtain handles
    via :meth:`open` / :meth:`create`, perform offset I/O, and finish with
    :meth:`flush` / :meth:`fsync` / :meth:`release`. Namespace mutations
    (:meth:`notify_rename`, :meth:`notify_unlink`) update path bindings without
    invalidating live handles.
    """

    SCHEMA: ClassVar[str] = HANDLE_TABLE_SCHEMA

    def __init__(
        self,
        *,
        max_open_handles: int = DEFAULT_MAX_OPEN_HANDLES,
        max_staged_bytes: int = DEFAULT_MAX_STAGED_BYTES,
        max_staged_bytes_per_handle: int = DEFAULT_MAX_STAGED_BYTES_PER_HANDLE,
        max_extents_per_handle: int = DEFAULT_MAX_EXTENTS_PER_HANDLE,
        chunk_bytes: int = DEFAULT_CHUNK_BYTES,
        default_lease_ms: int = DEFAULT_LEASE_MS,
        mount_id: str = "mount:default",
        clock_ms: Any | None = None,
        auto_commit_on_fsync: bool = True,
    ) -> None:
        if (
            not isinstance(max_open_handles, int)
            or max_open_handles < 1
            or max_open_handles > MAX_OPEN_HANDLES_HARD
        ):
            raise HandleError(
                f"max_open_handles must be in [1, {MAX_OPEN_HANDLES_HARD}]",
                code=HandleErrorCode.INTERNAL,
            )
        if chunk_bytes < 1:
            raise HandleError(
                "chunk_bytes must be positive",
                code=HandleErrorCode.INTERNAL,
            )
        self._max_open = max_open_handles
        self._max_staged = max_staged_bytes
        self._max_staged_per_handle = max_staged_bytes_per_handle
        self._max_extents = max_extents_per_handle
        self._chunk_bytes = chunk_bytes
        self._default_lease_ms = default_lease_ms
        self._mount_id = mount_id
        self._clock_ms = clock_ms or (lambda: int(time.time() * 1000))
        self._auto_commit_on_fsync = bool(auto_commit_on_fsync)

        self._lock = threading.RLock()
        self._handles: dict[int, _HandleState] = {}
        self._generations: dict[int, int] = {}  # handle_id -> next generation
        self._next_handle_id = MIN_HANDLE_ID
        self._inodes: dict[int, _InodeState] = {}
        self._path_index: dict[str, int] = {}  # path -> inode
        self._next_inode = MIN_INODE + 1  # reserve 1 as root-ish
        self._total_staged_bytes = 0
        self._trace = HandleTraceLog()
        self._pressure_events: list[dict[str, Any]] = []
        self._reclaim_count = 0

        # Seed empty root directory for path parent checks (optional).
        self._inodes[ROOT_INODE] = _InodeState(
            inode=ROOT_INODE,
            path="",
            is_directory=True,
            nlink=1,
            mode=0o755,
            mount_id=mount_id,
        )

    # -- properties ---------------------------------------------------------

    @property
    def schema(self) -> str:
        return self.SCHEMA

    @property
    def contract_version(self) -> int:
        return CONTRACT_VERSION

    @property
    def schema_version(self) -> str:
        return SCHEMA_VERSION

    @property
    def max_open_handles(self) -> int:
        return self._max_open

    @property
    def open_count(self) -> int:
        with self._lock:
            return sum(1 for h in self._handles.values() if not h.released)

    @property
    def staged_bytes(self) -> int:
        with self._lock:
            return self._total_staged_bytes

    @property
    def trace(self) -> HandleTraceLog:
        return self._trace

    @property
    def chunk_bytes(self) -> int:
        return self._chunk_bytes

    # -- pressure -----------------------------------------------------------

    def pressure_state(self) -> HandlePressureState:
        with self._lock:
            open_n = sum(1 for h in self._handles.values() if not h.released)
            staged = self._total_staged_bytes
            open_ratio = open_n / self._max_open if self._max_open else 1.0
            staged_ratio = (
                staged / self._max_staged if self._max_staged else 0.0
            )
            reasons: list[str] = []
            if open_n >= self._max_open:
                reasons.append("open_handles_exhausted")
            elif open_ratio >= 0.9:
                reasons.append("open_handles_high")
            if staged >= self._max_staged:
                reasons.append("staged_bytes_exhausted")
            elif staged_ratio >= 0.9:
                reasons.append("staged_bytes_high")
            pressure = bool(reasons)
            return HandlePressureState(
                open_handles=open_n,
                max_open_handles=self._max_open,
                staged_bytes=staged,
                max_staged_bytes=self._max_staged,
                pressure=pressure,
                open_ratio=open_ratio,
                staged_ratio=staged_ratio,
                reason=",".join(reasons),
            )

    def pressure_events(self) -> tuple[dict[str, Any], ...]:
        with self._lock:
            return tuple(self._pressure_events)

    def _record_pressure(self, reason: str, **detail: Any) -> None:
        event = {
            "reason": reason,
            "at_ms": int(self._clock_ms()),
            "open_handles": sum(1 for h in self._handles.values() if not h.released),
            "max_open_handles": self._max_open,
            "staged_bytes": self._total_staged_bytes,
            "max_staged_bytes": self._max_staged,
            **detail,
        }
        self._pressure_events.append(event)
        if len(self._pressure_events) > 256:
            del self._pressure_events[0]
        self._trace.record(
            HandleTraceKind.PRESSURE,
            success=False,
            code=HandleErrorCode.PRESSURE.value,
            detail=event,
        )

    # -- inode / path helpers -----------------------------------------------

    def seed_file(
        self,
        path: str,
        content: bytes = b"",
        *,
        inode: int | None = None,
        mount_id: str | None = None,
    ) -> int:
        """Install committed file content for hermetic tests / setup."""

        if not isinstance(path, str) or not path or path.startswith("/"):
            raise HandleError(
                "path must be a non-empty relative VFS path",
                code=HandleErrorCode.INTERNAL,
                path=path or "",
            )
        if not isinstance(content, (bytes, bytearray)):
            raise HandleError(
                "content must be bytes",
                code=HandleErrorCode.INTERNAL,
                path=path,
            )
        payload = bytes(content)
        with self._lock:
            if path in self._path_index:
                raise HandleError(
                    f"path already seeded: {path!r}",
                    code=HandleErrorCode.ALREADY_EXISTS,
                    path=path,
                    errno=HostErrno.EEXIST,
                )
            ino = self._alloc_inode(inode)
            chunks: dict[int, bytes] = {}
            size = _write_into_chunks(
                chunks,
                size_bytes=0,
                offset=0,
                data=payload,
                chunk_bytes=self._chunk_bytes,
            ) if payload else 0
            state = _InodeState(
                inode=ino,
                path=path,
                is_directory=False,
                nlink=1,
                size_bytes=size,
                chunks=chunks,
                generation=1 if payload else 0,
                mount_id=mount_id or self._mount_id,
            )
            self._inodes[ino] = state
            self._path_index[path] = ino
            return ino

    def seed_directory(self, path: str, *, inode: int | None = None) -> int:
        """Install a directory inode for path-policy tests."""

        if not isinstance(path, str) or (path.startswith("/") if path else False):
            raise HandleError(
                "path must be a relative VFS path",
                code=HandleErrorCode.INTERNAL,
                path=path or "",
            )
        with self._lock:
            if path in self._path_index:
                raise HandleError(
                    f"path already seeded: {path!r}",
                    code=HandleErrorCode.ALREADY_EXISTS,
                    path=path,
                    errno=HostErrno.EEXIST,
                )
            ino = self._alloc_inode(inode)
            state = _InodeState(
                inode=ino,
                path=path,
                is_directory=True,
                nlink=1,
                mode=0o755,
                mount_id=self._mount_id,
            )
            self._inodes[ino] = state
            if path:
                self._path_index[path] = ino
            return ino

    def _alloc_inode(self, requested: int | None = None) -> int:
        if requested is not None:
            if (
                isinstance(requested, bool)
                or not isinstance(requested, int)
                or requested < MIN_INODE
                or requested > MAX_SAFE_INTEGER
            ):
                raise HandleError(
                    "inode out of range",
                    code=HandleErrorCode.INTERNAL,
                    detail={"inode": requested},
                )
            if requested in self._inodes:
                raise HandleError(
                    f"inode already allocated: {requested}",
                    code=HandleErrorCode.INTERNAL,
                    detail={"inode": requested},
                )
            if requested >= self._next_inode:
                self._next_inode = requested + 1
            return requested
        if len(self._inodes) >= MAX_INODES:
            raise HandleError(
                "inode table exhausted",
                code=HandleErrorCode.INODE_EXHAUSTED,
                errno=HostErrno.ENOSPC,
            )
        while self._next_inode in self._inodes:
            self._next_inode += 1
            if self._next_inode > MAX_SAFE_INTEGER:
                raise HandleError(
                    "inode space exhausted",
                    code=HandleErrorCode.INODE_EXHAUSTED,
                    errno=HostErrno.ENOSPC,
                )
        ino = self._next_inode
        self._next_inode += 1
        return ino

    def lookup_inode(self, path: str) -> int | None:
        with self._lock:
            return self._path_index.get(path)

    def inode_stat(self, path: str) -> dict[str, Any] | None:
        with self._lock:
            ino = self._path_index.get(path)
            if ino is None:
                return None
            state = self._inodes[ino]
            return {
                "schema": INODE_RECORD_SCHEMA,
                "inode": state.inode,
                "path": state.path,
                "is_directory": state.is_directory,
                "nlink": state.nlink,
                "size_bytes": state.size_bytes,
                "generation": state.generation,
                "unlinked": state.unlinked,
                "open_count": state.open_count,
                "mount_id": state.mount_id,
            }

    def committed_read(self, path: str, offset: int = 0, length: int | None = None) -> bytes:
        """Read committed (non-staged) bytes for cross-handle visibility tests."""

        with self._lock:
            ino = self._path_index.get(path)
            if ino is None:
                raise HandleError(
                    f"path not found: {path!r}",
                    code=HandleErrorCode.NOT_FOUND,
                    path=path,
                    errno=HostErrno.ENOENT,
                )
            state = self._inodes[ino]
            if state.is_directory:
                raise HandleError(
                    "cannot read a directory",
                    code=HandleErrorCode.IS_DIRECTORY,
                    path=path,
                    errno=HostErrno.EISDIR,
                )
            off = _require_non_negative_int(offset, "offset")
            if length is None:
                length = max(0, state.size_bytes - off)
            length = _require_non_negative_int(length, "length")
            return _read_from_chunks(
                state.chunks,
                size_bytes=state.size_bytes,
                offset=off,
                length=length,
                chunk_bytes=self._chunk_bytes,
            )

    # -- open / create ------------------------------------------------------

    def open(
        self,
        path: str,
        flags: Sequence[OpenFlag | str] | OpenFlag | str | None = None,
        *,
        mode: int = 0o644,
        mount_id: str | None = None,
        lease_ms: int | None = None,
        inode: int | None = None,
    ) -> FileHandle:
        """Open an existing path, or create when ``O_CREAT`` is set."""

        return self._open_or_create(
            path,
            flags,
            mode=mode,
            mount_id=mount_id,
            lease_ms=lease_ms,
            inode=inode,
            create_entrypoint=False,
        )

    def create(
        self,
        path: str,
        flags: Sequence[OpenFlag | str] | OpenFlag | str | None = None,
        *,
        mode: int = 0o644,
        mount_id: str | None = None,
        lease_ms: int | None = None,
        inode: int | None = None,
    ) -> FileHandle:
        """Create-or-open entrypoint. Implies ``O_CREAT`` when absent."""

        normalized = list(_normalize_flags(flags if flags is not None else (OpenFlag.O_WRONLY,)))
        if OpenFlag.O_CREAT not in normalized:
            # Preserve access mode; append O_CREAT.
            access = [f for f in normalized if f in _ACCESS_FLAGS]
            rest = [f for f in normalized if f not in _ACCESS_FLAGS]
            normalized = [*access, OpenFlag.O_CREAT, *rest]
        return self._open_or_create(
            path,
            normalized,
            mode=mode,
            mount_id=mount_id,
            lease_ms=lease_ms,
            inode=inode,
            create_entrypoint=True,
        )

    def _open_or_create(
        self,
        path: str,
        flags: Sequence[OpenFlag | str] | OpenFlag | str | None,
        *,
        mode: int,
        mount_id: str | None,
        lease_ms: int | None,
        inode: int | None,
        create_entrypoint: bool,
    ) -> FileHandle:
        if not isinstance(path, str) or not path or path.startswith("/"):
            raise HandleError(
                "path must be a non-empty relative VFS path",
                code=HandleErrorCode.INTERNAL,
                path=path or "",
                errno=HostErrno.EINVAL,
            )
        norm_flags = _normalize_flags(flags)
        readable, writable = _access_mode(norm_flags)
        creat = OpenFlag.O_CREAT in norm_flags
        excl = OpenFlag.O_EXCL in norm_flags
        trunc = OpenFlag.O_TRUNC in norm_flags
        append = OpenFlag.O_APPEND in norm_flags

        if trunc and not writable:
            raise HandleError(
                "O_TRUNC requires a writable access mode",
                code=HandleErrorCode.BAD_FLAGS,
                path=path,
                errno=HostErrno.EACCES,
            )
        if append and not writable:
            raise HandleError(
                "O_APPEND requires a writable access mode",
                code=HandleErrorCode.BAD_FLAGS,
                path=path,
                errno=HostErrno.EACCES,
            )

        with self._lock:
            open_n = sum(1 for h in self._handles.values() if not h.released)
            if open_n >= self._max_open:
                self._record_pressure(
                    "open_handles_exhausted",
                    path=path,
                    attempted_flags=[f.value for f in norm_flags],
                )
                raise HandleError(
                    f"open handle bound exceeded ({self._max_open})",
                    code=HandleErrorCode.PRESSURE,
                    path=path,
                    errno=HostErrno.EMFILE,
                    detail={
                        "open_handles": open_n,
                        "max_open_handles": self._max_open,
                        "pressure": True,
                    },
                )

            existing_ino = self._path_index.get(path)
            created = False

            if existing_ino is not None:
                inode_state = self._inodes[existing_ino]
                if inode_state.is_directory:
                    raise HandleError(
                        f"path is a directory: {path!r}",
                        code=HandleErrorCode.IS_DIRECTORY,
                        path=path,
                        errno=HostErrno.EISDIR,
                    )
                if excl and creat:
                    raise HandleError(
                        f"file exists (O_EXCL): {path!r}",
                        code=HandleErrorCode.ALREADY_EXISTS,
                        path=path,
                        errno=HostErrno.EEXIST,
                    )
                if trunc:
                    inode_state.chunks.clear()
                    inode_state.size_bytes = 0
                    inode_state.generation += 1
            else:
                if not creat:
                    raise HandleError(
                        f"path not found: {path!r}",
                        code=HandleErrorCode.NOT_FOUND,
                        path=path,
                        errno=HostErrno.ENOENT,
                    )
                existing_ino = self._alloc_inode(inode)
                inode_state = _InodeState(
                    inode=existing_ino,
                    path=path,
                    is_directory=False,
                    nlink=1,
                    size_bytes=0,
                    chunks={},
                    generation=1,
                    mount_id=mount_id or self._mount_id,
                    mode=int(mode) & 0o777777,
                )
                self._inodes[existing_ino] = inode_state
                self._path_index[path] = existing_ino
                created = True

            handle_id = self._alloc_handle_id()
            generation = self._generations.get(handle_id, 0) + 1
            self._generations[handle_id] = generation
            now = int(self._clock_ms())
            lease = self._default_lease_ms if lease_ms is None else int(lease_ms)
            if lease < 0:
                raise HandleError(
                    "lease_ms must be non-negative",
                    code=HandleErrorCode.INTERNAL,
                    path=path,
                )
            expires = 0 if lease == 0 else now + lease
            lease_id = f"lease:{handle_id}:{generation}"

            base_size = 0 if trunc else inode_state.size_bytes
            # Snapshot committed base into staged map for non-truncate opens so
            # partial staged writes preserve prior bytes (read-own-writes).
            if trunc:
                staged_chunks: dict[int, bytes] = {}
            else:
                staged_chunks = inode_state.clone_chunks()

            state = _HandleState(
                handle_id=handle_id,
                generation=generation,
                inode=existing_ino,
                flags=norm_flags,
                path_at_open=path,
                current_path=path,
                mount_id=mount_id or inode_state.mount_id,
                lease_id=lease_id,
                lease_expires_at_ms=expires,
                readable=readable,
                writable=writable,
                append=append,
                created=created,
                truncated_on_open=trunc and not created,
                staged=staged_chunks,
                staged_size=base_size,
            )
            self._handles[handle_id] = state
            inode_state.open_count += 1

            kind = HandleTraceKind.CREATE if create_entrypoint or created else HandleTraceKind.OPEN
            self._trace.record(
                kind,
                success=True,
                handle_id=handle_id,
                generation=generation,
                path=path,
                detail={
                    "flags": [f.value for f in norm_flags],
                    "inode": existing_ino,
                    "created": created,
                    "truncated": trunc,
                    "append": append,
                    "o_creat": creat,
                    "o_excl": excl,
                    "lease_id": lease_id,
                    "lease_expires_at_ms": expires,
                },
            )
            return state.view()

    def _alloc_handle_id(self) -> int:
        # Prefer recycling released slots; otherwise allocate new ids.
        for hid, state in self._handles.items():
            if state.released:
                # Slot free for reuse with bumped generation.
                del self._handles[hid]
                return hid
        # Scan for free id starting at next.
        start = self._next_handle_id
        for _ in range(MAX_OPEN_HANDLES_HARD + 1):
            candidate = self._next_handle_id
            self._next_handle_id += 1
            if self._next_handle_id > MAX_HANDLE_ID:
                self._next_handle_id = MIN_HANDLE_ID
            if candidate not in self._handles:
                return candidate
            if self._next_handle_id == start:
                break
        raise HandleError(
            "handle id space exhausted",
            code=HandleErrorCode.HANDLE_EXHAUSTED,
            errno=HostErrno.ENFILE,
        )

    # -- lookup / validation ------------------------------------------------

    def get(
        self,
        handle_id: int,
        generation: int | None = None,
        *,
        allow_released: bool = False,
    ) -> FileHandle:
        """Return an immutable view of a live handle; reject stale generations."""

        with self._lock:
            state = self._require_handle(
                handle_id, generation, allow_released=allow_released, check_lease=False
            )
            return state.view()

    def _require_handle(
        self,
        handle_id: int,
        generation: int | None,
        *,
        allow_released: bool = False,
        check_lease: bool = True,
        for_write: bool = False,
        for_read: bool = False,
    ) -> _HandleState:
        if isinstance(handle_id, bool) or not isinstance(handle_id, int) or handle_id < MIN_HANDLE_ID:
            raise HandleError(
                "invalid handle_id",
                code=HandleErrorCode.STALE,
                errno=HostErrno.EBADF,
                handle_id=int(handle_id) if isinstance(handle_id, int) else 0,
            )
        state = self._handles.get(handle_id)
        if state is None:
            raise HandleError(
                f"unknown handle: {handle_id}",
                code=HandleErrorCode.NOT_FOUND,
                errno=HostErrno.EBADF,
                handle_id=handle_id,
            )
        if generation is not None and state.generation != generation:
            self._trace.record(
                HandleTraceKind.STALE,
                success=False,
                handle_id=handle_id,
                generation=int(generation),
                code=HandleErrorCode.STALE.value,
                detail={
                    "expected_generation": state.generation,
                    "provided_generation": generation,
                },
            )
            raise HandleError(
                f"stale handle generation: {handle_id}@{generation} "
                f"(live is {state.generation})",
                code=HandleErrorCode.STALE,
                errno=HostErrno.ESTALE,
                handle_id=handle_id,
                generation=int(generation),
                detail={"live_generation": state.generation},
            )
        if state.released and not allow_released:
            raise HandleError(
                f"handle already released: {handle_id}",
                code=HandleErrorCode.RELEASED,
                errno=HostErrno.EBADF,
                handle_id=handle_id,
                generation=state.generation,
            )
        if check_lease and not state.released and state.lease_expires_at_ms > 0:
            now = int(self._clock_ms())
            if now > state.lease_expires_at_ms:
                # Lease expiry invalidates the handle (orphan candidate).
                self._trace.record(
                    HandleTraceKind.STALE,
                    success=False,
                    handle_id=handle_id,
                    generation=state.generation,
                    code=HandleErrorCode.LEASE_EXPIRED.value,
                    detail={
                        "lease_expires_at_ms": state.lease_expires_at_ms,
                        "now_ms": now,
                    },
                )
                raise HandleError(
                    f"handle lease expired: {handle_id}",
                    code=HandleErrorCode.LEASE_EXPIRED,
                    errno=HostErrno.EBADF,
                    handle_id=handle_id,
                    generation=state.generation,
                    detail={
                        "lease_expires_at_ms": state.lease_expires_at_ms,
                        "now_ms": now,
                    },
                )
        if for_write and not state.writable:
            raise HandleError(
                "handle is not writable",
                code=HandleErrorCode.PERMISSION,
                errno=HostErrno.EBADF,
                handle_id=handle_id,
                generation=state.generation,
            )
        if for_read and not state.readable:
            raise HandleError(
                "handle is not readable",
                code=HandleErrorCode.PERMISSION,
                errno=HostErrno.EBADF,
                handle_id=handle_id,
                generation=state.generation,
            )
        return state

    # -- I/O ----------------------------------------------------------------

    def write(
        self,
        handle_id: int,
        offset: int,
        data: bytes,
        *,
        generation: int | None = None,
        defer_errors: bool = False,
    ) -> HandleIOResult:
        """Stage a (possibly sparse/random) write on the handle.

        Writes never enter shared ARC. With ``O_APPEND``, ``offset`` is ignored
        and data is appended at the current logical size. Sparse writes past
        EOF extend the logical size; intermediate holes read as zeroes.
        """

        if not isinstance(data, (bytes, bytearray)):
            raise HandleError(
                "write data must be bytes",
                code=HandleErrorCode.INTERNAL,
                handle_id=handle_id,
            )
        payload = bytes(data)
        off = _require_non_negative_int(offset, "offset")
        if len(payload) > MAX_IO_LENGTH:
            raise HandleError(
                "write length exceeds I/O bound",
                code=HandleErrorCode.BOUND_EXCEEDED,
                errno=HostErrno.EINVAL,
                handle_id=handle_id,
            )

        with self._lock:
            state = self._require_handle(
                handle_id, generation, for_write=True, check_lease=True
            )

            write_offset = state.staged_size if state.append else off
            if write_offset > MAX_OFFSET or write_offset + len(payload) > MAX_SIZE_BYTES:
                err = HandleError(
                    "write would exceed size bound",
                    code=HandleErrorCode.BOUND_EXCEEDED,
                    errno=HostErrno.EFBIG,
                    handle_id=handle_id,
                    generation=state.generation,
                )
                if defer_errors:
                    return self._defer(state, err)
                raise err

            new_dirty = state.staged_dirty_bytes + len(payload)
            if new_dirty > self._max_staged_per_handle:
                self._record_pressure(
                    "staged_bytes_per_handle",
                    handle_id=handle_id,
                    staged_dirty_bytes=new_dirty,
                )
                err = HandleError(
                    "per-handle staged byte bound exceeded",
                    code=HandleErrorCode.PRESSURE,
                    errno=HostErrno.ENOSPC,
                    handle_id=handle_id,
                    generation=state.generation,
                    detail={
                        "staged_dirty_bytes": new_dirty,
                        "max_staged_bytes_per_handle": self._max_staged_per_handle,
                        "pressure": True,
                    },
                )
                if defer_errors:
                    return self._defer(state, err)
                raise err

            projected_total = self._total_staged_bytes - state.staged_dirty_bytes + new_dirty
            if projected_total > self._max_staged:
                self._record_pressure(
                    "staged_bytes_exhausted",
                    handle_id=handle_id,
                    staged_bytes=projected_total,
                )
                err = HandleError(
                    "table staged byte bound exceeded",
                    code=HandleErrorCode.PRESSURE,
                    errno=HostErrno.ENOSPC,
                    handle_id=handle_id,
                    generation=state.generation,
                    detail={
                        "staged_bytes": projected_total,
                        "max_staged_bytes": self._max_staged,
                        "pressure": True,
                    },
                )
                if defer_errors:
                    return self._defer(state, err)
                raise err

            if len(state.extents) >= self._max_extents:
                self._record_pressure(
                    "extents_per_handle",
                    handle_id=handle_id,
                    extents=len(state.extents),
                )
                err = HandleError(
                    "per-handle extent bound exceeded",
                    code=HandleErrorCode.PRESSURE,
                    errno=HostErrno.ENOSPC,
                    handle_id=handle_id,
                    generation=state.generation,
                    detail={"max_extents_per_handle": self._max_extents, "pressure": True},
                )
                if defer_errors:
                    return self._defer(state, err)
                raise err

            hole_before = max(0, write_offset - state.staged_size)
            sparse = write_offset > state.staged_size or (
                write_offset > 0 and state.staged_size == 0 and write_offset > 0
            )

            prev_size = state.staged_size
            state.staged_size = _write_into_chunks(
                state.staged,
                size_bytes=state.staged_size,
                offset=write_offset,
                data=payload,
                chunk_bytes=self._chunk_bytes,
            )
            # Empty payload at offset past EOF still extends size (truncate-like hole).
            if not payload and write_offset > prev_size:
                state.staged_size = write_offset

            state.extent_seq += 1
            extent = StagedExtent(
                offset=write_offset,
                length=len(payload),
                data=payload,
                sequence=state.extent_seq,
            )
            state.extents.append(extent)
            delta = new_dirty - state.staged_dirty_bytes
            state.staged_dirty_bytes = new_dirty
            self._total_staged_bytes += delta
            state.dirty = True

            self._trace.record(
                HandleTraceKind.WRITE,
                success=True,
                handle_id=handle_id,
                generation=state.generation,
                path=state.current_path,
                detail={
                    "offset": write_offset,
                    "length": len(payload),
                    "append": state.append,
                    "sparse": sparse,
                    "hole_before": hole_before,
                    "logical_size": state.staged_size,
                    "dirty_in_handle_only": True,
                    "sequence": extent.sequence,
                },
            )
            self._trace.record(
                HandleTraceKind.STAGE,
                success=True,
                handle_id=handle_id,
                generation=state.generation,
                path=state.current_path,
                detail={
                    "offset": write_offset,
                    "length": len(payload),
                    "staged_bytes": state.staged_dirty_bytes,
                },
            )
            return HandleIOResult(
                handle_id=handle_id,
                generation=state.generation,
                offset=write_offset,
                length=len(payload),
                bytes_transferred=len(payload),
                data=b"",
                logical_size=state.staged_size,
                staged=True,
                sparse=sparse,
                hole_before=hole_before,
                dirty_in_handle_only=True,
            )

    def _defer(self, state: _HandleState, err: HandleError) -> HandleIOResult:
        state.deferred_code = err.code.value
        state.deferred_errno = err.errno.value
        state.deferred_message = err.message
        self._trace.record(
            HandleTraceKind.DEFERRED,
            success=False,
            handle_id=state.handle_id,
            generation=state.generation,
            path=state.current_path,
            code=err.code.value,
            detail={"errno": err.errno.value, "message": err.message, **err.detail},
        )
        # Buffered write path reports transfer success; error surfaces on flush.
        return HandleIOResult(
            handle_id=state.handle_id,
            generation=state.generation,
            offset=0,
            length=0,
            bytes_transferred=0,
            logical_size=state.staged_size,
            staged=False,
            dirty_in_handle_only=True,
        )

    def set_deferred_error(
        self,
        handle_id: int,
        *,
        generation: int | None = None,
        code: HandleErrorCode | str = HandleErrorCode.DEFERRED_ERROR,
        errno: HostErrno | str = HostErrno.EIO,
        message: str = "deferred write error",
    ) -> FileHandle:
        """Explicitly attach a deferred write error (fault-injection / adapter)."""

        with self._lock:
            state = self._require_handle(handle_id, generation, for_write=False)
            code_s = code.value if isinstance(code, HandleErrorCode) else str(code)
            errno_s = errno.value if isinstance(errno, HostErrno) else str(errno)
            state.deferred_code = code_s
            state.deferred_errno = errno_s
            state.deferred_message = message
            self._trace.record(
                HandleTraceKind.DEFERRED,
                success=False,
                handle_id=handle_id,
                generation=state.generation,
                path=state.current_path,
                code=code_s,
                detail={"errno": errno_s, "message": message},
            )
            return state.view()

    def read(
        self,
        handle_id: int,
        offset: int,
        length: int,
        *,
        generation: int | None = None,
    ) -> HandleIOResult:
        """Read bytes observing this handle's own staged writes.

        Cross-handle visibility of uncommitted staged bytes is intentionally
        not provided (read-own-writes / generation-bound consistency).
        Sparse holes return zeroes without fabricating content identity.

        This is the handle-plane *read-own-writes* path over the per-handle
        staged snapshot (including the committed base snapshotted at open).
        It is available for any live handle — including ``O_WRONLY`` /
        ``O_APPEND`` writers verifying their own staged extents — and is not
        a POSIX access-mode gate.
        """

        off = _require_non_negative_int(offset, "offset")
        length = _require_non_negative_int(length, "length")
        if length > MAX_IO_LENGTH:
            raise HandleError(
                "read length exceeds I/O bound",
                code=HandleErrorCode.BOUND_EXCEEDED,
                errno=HostErrno.EINVAL,
                handle_id=handle_id,
            )

        with self._lock:
            # Read-own-writes is generation-bound staged observation, not a
            # POSIX readable-mode check: O_WRONLY + O_APPEND writers may
            # verify their own staged extents on the same handle.
            state = self._require_handle(
                handle_id, generation, for_read=False, check_lease=True
            )
            data = _read_from_chunks(
                state.staged,
                size_bytes=state.staged_size,
                offset=off,
                length=length,
                chunk_bytes=self._chunk_bytes,
            )
            # Detect whether any staged dirty extent covers this range.
            own = any(ext.overlaps(off, length) for ext in state.extents) if state.dirty else False
            self._trace.record(
                HandleTraceKind.READ,
                success=True,
                handle_id=handle_id,
                generation=state.generation,
                path=state.current_path,
                detail={
                    "offset": off,
                    "length": length,
                    "bytes": len(data),
                    "read_own_writes": own or state.dirty,
                    "logical_size": state.staged_size,
                },
            )
            return HandleIOResult(
                handle_id=handle_id,
                generation=state.generation,
                offset=off,
                length=length,
                bytes_transferred=len(data),
                data=data,
                logical_size=state.staged_size,
                staged=state.dirty,
                read_own_writes=True,
                dirty_in_handle_only=state.dirty,
            )

    def truncate(
        self,
        handle_id: int,
        size: int,
        *,
        generation: int | None = None,
    ) -> FileHandle:
        """Truncate the handle's logical (staged) size."""

        size = _require_non_negative_int(size, "size")
        if size > MAX_SIZE_BYTES:
            raise HandleError(
                "truncate size exceeds bound",
                code=HandleErrorCode.BOUND_EXCEEDED,
                errno=HostErrno.EFBIG,
                handle_id=handle_id,
            )
        with self._lock:
            state = self._require_handle(
                handle_id, generation, for_write=True, check_lease=True
            )
            if size < state.staged_size:
                _trim_chunks_to_size(
                    state.staged,
                    size_bytes=size,
                    chunk_bytes=self._chunk_bytes,
                )
                # Drop extents fully past the new size; clip those that straddle.
                kept: list[StagedExtent] = []
                for ext in state.extents:
                    if ext.offset >= size:
                        continue
                    if ext.end <= size:
                        kept.append(ext)
                    else:
                        clipped = ext.data[: max(0, size - ext.offset)]
                        kept.append(
                            StagedExtent(
                                offset=ext.offset,
                                length=len(clipped),
                                data=clipped,
                                sequence=ext.sequence,
                            )
                        )
                state.extents = kept
            state.staged_size = size
            state.dirty = True
            self._trace.record(
                HandleTraceKind.TRUNCATE,
                success=True,
                handle_id=handle_id,
                generation=state.generation,
                path=state.current_path,
                detail={"size": size},
            )
            return state.view()

    def staged_extents(
        self,
        handle_id: int,
        *,
        generation: int | None = None,
    ) -> tuple[StagedExtent, ...]:
        with self._lock:
            state = self._require_handle(
                handle_id, generation, allow_released=False, check_lease=False
            )
            return tuple(state.extents)

    # -- flush / fsync / release --------------------------------------------

    def flush(
        self,
        handle_id: int,
        *,
        generation: int | None = None,
        commit: bool = False,
    ) -> FlushResult:
        """Flush the handle. Returns prior deferred write errors consistently.

        ``flush`` does not manufacture durability. When ``commit`` is True the
        staged extents are applied to the committed inode (hermetic stand-in
        for a later WAL-bound commit). Repeated flushes are idempotent with
        respect to already-committed staged state and deferred errors.
        """

        with self._lock:
            state = self._require_handle(
                handle_id, generation, allow_released=False, check_lease=True
            )
            state.flush_count += 1
            idempotent = state.flush_count > 1

            if state.deferred_code:
                result = FlushResult(
                    handle_id=handle_id,
                    generation=state.generation,
                    success=False,
                    committed_bytes=0,
                    deferred_error=True,
                    error_code=state.deferred_code,
                    errno=state.deferred_errno or HostErrno.EIO.value,
                    idempotent=idempotent,
                    durable=False,
                    detail={"message": state.deferred_message, "flush_count": state.flush_count},
                )
                self._trace.record(
                    HandleTraceKind.FLUSH,
                    success=False,
                    handle_id=handle_id,
                    generation=state.generation,
                    path=state.current_path,
                    code=state.deferred_code,
                    detail=result.to_record(),
                )
                return result

            committed = 0
            if commit and state.dirty:
                committed = self._commit_handle_locked(state)
            elif not state.dirty:
                committed = state.last_flush_committed

            result = FlushResult(
                handle_id=handle_id,
                generation=state.generation,
                success=True,
                committed_bytes=committed,
                deferred_error=False,
                error_code="",
                errno=HostErrno.OK.value,
                idempotent=idempotent,
                durable=False,
                detail={"flush_count": state.flush_count, "dirty": state.dirty},
            )
            self._trace.record(
                HandleTraceKind.FLUSH,
                success=True,
                handle_id=handle_id,
                generation=state.generation,
                path=state.current_path,
                detail=result.to_record(),
            )
            return result

    def fsync(
        self,
        handle_id: int,
        *,
        generation: int | None = None,
        datasync: bool = False,
    ) -> FlushResult:
        """Commit staged extents to the inode (hermetic durability stand-in).

        Real WAL/backend durability is owned by KVFS-300. Here ``fsync``
        applies staged bytes to committed inode content so cross-handle reads
        observe them after a successful call.
        """

        with self._lock:
            state = self._require_handle(
                handle_id, generation, allow_released=False, check_lease=True
            )
            if state.deferred_code:
                result = FlushResult(
                    handle_id=handle_id,
                    generation=state.generation,
                    success=False,
                    committed_bytes=0,
                    deferred_error=True,
                    error_code=state.deferred_code,
                    errno=state.deferred_errno or HostErrno.EIO.value,
                    idempotent=False,
                    durable=False,
                    detail={
                        "message": state.deferred_message,
                        "datasync": datasync,
                    },
                )
                self._trace.record(
                    HandleTraceKind.FSYNC,
                    success=False,
                    handle_id=handle_id,
                    generation=state.generation,
                    path=state.current_path,
                    code=state.deferred_code,
                    detail=result.to_record(),
                )
                return result

            committed = 0
            if self._auto_commit_on_fsync and state.dirty:
                committed = self._commit_handle_locked(state)
            result = FlushResult(
                handle_id=handle_id,
                generation=state.generation,
                success=True,
                committed_bytes=committed,
                deferred_error=False,
                errno=HostErrno.OK.value,
                durable=True,
                detail={"datasync": datasync, "auto_commit": self._auto_commit_on_fsync},
            )
            self._trace.record(
                HandleTraceKind.FSYNC,
                success=True,
                handle_id=handle_id,
                generation=state.generation,
                path=state.current_path,
                detail=result.to_record(),
            )
            return result

    def _commit_handle_locked(self, state: _HandleState) -> int:
        inode_state = self._inodes.get(state.inode)
        if inode_state is None:
            raise HandleError(
                f"inode missing for handle {state.handle_id}",
                code=HandleErrorCode.INTERNAL,
                handle_id=state.handle_id,
                generation=state.generation,
            )
        # Replace committed content with staged snapshot.
        inode_state.chunks = dict(state.staged)
        inode_state.size_bytes = state.staged_size
        inode_state.generation += 1
        committed = state.staged_dirty_bytes
        self._total_staged_bytes = max(0, self._total_staged_bytes - state.staged_dirty_bytes)
        state.staged_dirty_bytes = 0
        state.extents.clear()
        state.dirty = False
        state.last_flush_committed = committed
        # Keep staged map as the new base for further read-own-writes.
        state.staged = inode_state.clone_chunks()
        state.staged_size = inode_state.size_bytes
        self._trace.record(
            HandleTraceKind.COMMIT,
            success=True,
            handle_id=state.handle_id,
            generation=state.generation,
            path=state.current_path,
            detail={
                "inode": state.inode,
                "size_bytes": inode_state.size_bytes,
                "content_generation": inode_state.generation,
                "committed_bytes": committed,
            },
        )
        return committed

    def release(
        self,
        handle_id: int,
        *,
        generation: int | None = None,
        discard_dirty: bool = False,
    ) -> ReleaseResult:
        """Idempotent release. Does not manufacture durability.

        On first release the handle is marked released and the open_count on
        its inode is decremented. Unlinked inodes with zero open handles are
        reclaimed as orphans. Subsequent releases succeed as no-ops.
        """

        with self._lock:
            state = self._handles.get(handle_id)
            if state is None:
                # Completely unknown — treat as idempotent success for reclaim races.
                result = ReleaseResult(
                    handle_id=handle_id,
                    generation=int(generation or 0),
                    success=True,
                    already_released=True,
                    reclaimed=False,
                    detail={"unknown": True},
                )
                self._trace.record(
                    HandleTraceKind.RELEASE,
                    success=True,
                    handle_id=handle_id,
                    generation=int(generation or 0),
                    detail=result.to_record(),
                )
                return result

            if generation is not None and state.generation != generation:
                raise HandleError(
                    f"stale handle generation on release: {handle_id}@{generation}",
                    code=HandleErrorCode.STALE,
                    errno=HostErrno.ESTALE,
                    handle_id=handle_id,
                    generation=int(generation),
                    detail={"live_generation": state.generation},
                )

            if state.released:
                state.release_count += 1
                result = ReleaseResult(
                    handle_id=handle_id,
                    generation=state.generation,
                    success=True,
                    already_released=True,
                    reclaimed=False,
                    detail={"release_count": state.release_count},
                )
                self._trace.record(
                    HandleTraceKind.RELEASE,
                    success=True,
                    handle_id=handle_id,
                    generation=state.generation,
                    path=state.current_path,
                    detail=result.to_record(),
                )
                return result

            deferred_cleared = bool(state.deferred_code)
            if discard_dirty and state.dirty:
                self._total_staged_bytes = max(
                    0, self._total_staged_bytes - state.staged_dirty_bytes
                )
                state.staged_dirty_bytes = 0
                state.extents.clear()
                state.dirty = False
            elif state.dirty:
                # Drop uncommitted dirty on release (flush/fsync must precede
                # if durability is required). Matches "release cannot manufacture
                # durability".
                self._total_staged_bytes = max(
                    0, self._total_staged_bytes - state.staged_dirty_bytes
                )
                state.staged_dirty_bytes = 0
                state.extents.clear()
                state.dirty = False

            state.released = True
            state.release_count += 1
            state.deferred_code = ""
            state.deferred_errno = ""
            state.deferred_message = ""

            orphaned = False
            inode_state = self._inodes.get(state.inode)
            if inode_state is not None:
                inode_state.open_count = max(0, inode_state.open_count - 1)
                if inode_state.unlinked and inode_state.open_count == 0:
                    orphaned = self._reclaim_inode_locked(inode_state.inode)

            result = ReleaseResult(
                handle_id=handle_id,
                generation=state.generation,
                success=True,
                already_released=False,
                reclaimed=True,
                orphaned_inode_reclaimed=orphaned,
                deferred_error_cleared=deferred_cleared,
                detail={"release_count": state.release_count},
            )
            self._trace.record(
                HandleTraceKind.RELEASE,
                success=True,
                handle_id=handle_id,
                generation=state.generation,
                path=state.current_path,
                detail=result.to_record(),
            )
            return result

    # -- rename / unlink while open -----------------------------------------

    def notify_rename(self, source: str, target: str) -> dict[str, Any]:
        """Update path binding for an inode. Open handles remain valid.

        Handles keep their ``handle_id`` / ``generation`` and continue I/O
        against the same inode. ``current_path`` is updated for observability;
        ``path_at_open`` is preserved.
        """

        if not isinstance(source, str) or not isinstance(target, str):
            raise HandleError(
                "rename paths must be strings",
                code=HandleErrorCode.INTERNAL,
                errno=HostErrno.EINVAL,
            )
        if not source or not target:
            raise HandleError(
                "rename paths must be non-empty",
                code=HandleErrorCode.INTERNAL,
                path=source or target,
                errno=HostErrno.EINVAL,
            )
        if source == target:
            return {"source": source, "target": target, "noop": True, "handles_updated": 0}

        with self._lock:
            ino = self._path_index.get(source)
            if ino is None:
                raise HandleError(
                    f"rename source not found: {source!r}",
                    code=HandleErrorCode.NOT_FOUND,
                    path=source,
                    errno=HostErrno.ENOENT,
                )
            if target in self._path_index and self._path_index[target] != ino:
                raise HandleError(
                    f"rename target exists: {target!r}",
                    code=HandleErrorCode.PATH_CONFLICT,
                    path=target,
                    errno=HostErrno.EEXIST,
                )
            inode_state = self._inodes[ino]
            del self._path_index[source]
            self._path_index[target] = ino
            inode_state.path = target
            updated = 0
            for handle in self._handles.values():
                if handle.inode == ino and not handle.released:
                    handle.current_path = target
                    updated += 1
            detail = {
                "source": source,
                "target": target,
                "inode": ino,
                "handles_updated": updated,
                "handle_still_valid": True,
            }
            self._trace.record(
                HandleTraceKind.RENAME,
                success=True,
                path=target,
                detail=detail,
            )
            return detail

    def notify_unlink(self, path: str) -> dict[str, Any]:
        """Unlink a path. Open handles remain usable until last release.

        Removes the path from the namespace index and marks the inode unlinked.
        When no handles remain open, the inode is reclaimed immediately.
        """

        if not isinstance(path, str) or not path:
            raise HandleError(
                "unlink path must be a non-empty string",
                code=HandleErrorCode.INTERNAL,
                path=path or "",
                errno=HostErrno.EINVAL,
            )
        with self._lock:
            ino = self._path_index.get(path)
            if ino is None:
                raise HandleError(
                    f"unlink path not found: {path!r}",
                    code=HandleErrorCode.NOT_FOUND,
                    path=path,
                    errno=HostErrno.ENOENT,
                )
            inode_state = self._inodes[ino]
            if inode_state.is_directory:
                raise HandleError(
                    f"cannot unlink directory via notify_unlink: {path!r}",
                    code=HandleErrorCode.IS_DIRECTORY,
                    path=path,
                    errno=HostErrno.EISDIR,
                )
            del self._path_index[path]
            inode_state.nlink = max(0, inode_state.nlink - 1)
            inode_state.unlinked = inode_state.nlink == 0
            for handle in self._handles.values():
                if handle.inode == ino and not handle.released:
                    handle.unlinked = True
            reclaimed = False
            if inode_state.unlinked and inode_state.open_count == 0:
                reclaimed = self._reclaim_inode_locked(ino)
            detail = {
                "path": path,
                "inode": ino,
                "nlink": inode_state.nlink if ino in self._inodes else 0,
                "open_count": inode_state.open_count if ino in self._inodes else 0,
                "unlinked": True,
                "inode_reclaimed": reclaimed,
                "handle_still_valid": (inode_state.open_count > 0) if ino in self._inodes else False,
            }
            self._trace.record(
                HandleTraceKind.UNLINK,
                success=True,
                path=path,
                detail=detail,
            )
            return detail

    # -- orphan reclamation -------------------------------------------------

    def reclaim_orphans(self, *, now_ms: int | None = None) -> ReclaimResult:
        """Reclaim expired-lease handles and unlinked zero-open inodes.

        Released handle slots are recycled on subsequent open. This method
        force-releases handles whose leases have expired and drops orphaned
        inode content that is no longer reachable.
        """

        now = int(self._clock_ms()) if now_ms is None else int(now_ms)
        with self._lock:
            expired = 0
            reclaimed_handles = 0
            for handle_id, state in list(self._handles.items()):
                if state.released:
                    continue
                if state.lease_expires_at_ms > 0 and now > state.lease_expires_at_ms:
                    # Force-release expired lease without double-free.
                    if state.dirty:
                        self._total_staged_bytes = max(
                            0, self._total_staged_bytes - state.staged_dirty_bytes
                        )
                        state.staged_dirty_bytes = 0
                        state.extents.clear()
                        state.dirty = False
                    state.released = True
                    state.release_count += 1
                    inode_state = self._inodes.get(state.inode)
                    if inode_state is not None:
                        inode_state.open_count = max(0, inode_state.open_count - 1)
                    expired += 1
                    reclaimed_handles += 1
                    self._trace.record(
                        HandleTraceKind.RECLAIM,
                        success=True,
                        handle_id=handle_id,
                        generation=state.generation,
                        path=state.current_path,
                        detail={
                            "reason": "lease_expired",
                            "lease_expires_at_ms": state.lease_expires_at_ms,
                            "now_ms": now,
                            "double_free": False,
                        },
                    )

            reclaimed_inodes = 0
            for ino, inode_state in list(self._inodes.items()):
                if ino == ROOT_INODE:
                    continue
                if inode_state.unlinked and inode_state.open_count == 0:
                    if self._reclaim_inode_locked(ino):
                        reclaimed_inodes += 1

            # Drop released handle records so ids can recycle cleanly.
            recycled_slots = 0
            for handle_id, state in list(self._handles.items()):
                if state.released:
                    del self._handles[handle_id]
                    recycled_slots += 1

            self._reclaim_count += 1
            result = ReclaimResult(
                reclaimed_handles=reclaimed_handles,
                reclaimed_inodes=reclaimed_inodes,
                expired_leases=expired,
                detail={
                    "pass": self._reclaim_count,
                    "now_ms": now,
                    "recycled_slots": recycled_slots,
                },
            )
            self._trace.record(
                HandleTraceKind.RECLAIM,
                success=True,
                detail=result.to_record(),
            )
            return result

    def _reclaim_inode_locked(self, inode: int) -> bool:
        state = self._inodes.get(inode)
        if state is None or inode == ROOT_INODE:
            return False
        if state.open_count > 0:
            return False
        # Remove any residual path index entry.
        if state.path in self._path_index and self._path_index[state.path] == inode:
            del self._path_index[state.path]
        del self._inodes[inode]
        return True

    # -- snapshots / records ------------------------------------------------

    def open_handles(self) -> tuple[FileHandle, ...]:
        with self._lock:
            return tuple(
                h.view() for h in self._handles.values() if not h.released
            )

    def to_record(self) -> dict[str, Any]:
        with self._lock:
            pressure = self.pressure_state()
            return {
                "schema": self.SCHEMA,
                "contract_version": CONTRACT_VERSION,
                "schema_version": SCHEMA_VERSION,
                "open_handles": self.open_count,
                "max_open_handles": self._max_open,
                "staged_bytes": self._total_staged_bytes,
                "max_staged_bytes": self._max_staged,
                "inode_count": len(self._inodes),
                "path_count": len(self._path_index),
                "pressure": pressure.to_record(),
                "reclaim_passes": self._reclaim_count,
            }


# ---------------------------------------------------------------------------
# Module exports
# ---------------------------------------------------------------------------

__all__ = [
    "CONTRACT_VERSION",
    "SCHEMA_VERSION",
    "HandleTable_V1",
    "FileHandle_V1",
    "StagedExtent_V1",
    "HANDLE_TABLE_SCHEMA",
    "FILE_HANDLE_SCHEMA",
    "STAGED_EXTENT_SCHEMA",
    "DEFAULT_CHUNK_BYTES",
    "DEFAULT_MAX_OPEN_HANDLES",
    "DEFAULT_MAX_STAGED_BYTES",
    "DEFAULT_MAX_STAGED_BYTES_PER_HANDLE",
    "DEFAULT_LEASE_MS",
    "HandleErrorCode",
    "HandleError",
    "HandleTraceKind",
    "HandleTraceStep",
    "HandleTraceLog",
    "HandlePressureState",
    "StagedExtent",
    "FileHandle",
    "HandleIOResult",
    "FlushResult",
    "ReleaseResult",
    "ReclaimResult",
    "HandleTable",
]
