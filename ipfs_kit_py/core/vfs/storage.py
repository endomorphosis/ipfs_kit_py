"""Ranged VFS storage boundaries and backend adapters (KVFS-200).

This module owns the *persistent ranged* storage boundary that connects
``CanonicalVFSService`` (and future ``DurableCachedVFSRuntime``) to concrete
backends.  It is deliberately separate from the whole-object
:class:`~ipfs_kit_py.core.vfs.service.VFSStorageBoundary` used by hermetic
service tests: callers are not cut over here (see KVFS-203).

Adapters (memory, local, IPFS, Iroh) expose a confined surface:

* ``stat`` / ``list``
* ``range_read`` (never requires whole-object materialisation)
* ``staged_write`` (begin → write extents → commit / abort)
* ``delete`` / ``rename``

Files larger than 1 MiB are stored and served in fixed-size chunks so a
partial read does not load the entire object.  Immutable or unavailable
backends reject mutating (or all) operations with typed errors.  Every
admitted mutation appends an observable effect carrying generation and
content/version identities.
"""

from __future__ import annotations

import hashlib
import os
import secrets
import threading
import time
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any, ClassVar, Final, Protocol, runtime_checkable

from ipfs_kit_py.core.vfs.contracts import (
    VFSEntryKind,
    VFSPathError,
    VFSPathPolicy,
    content_identity,
    normalize_vfs_path,
)
from ipfs_kit_py.core.vfs.service import (
    MAX_NAMESPACE_ENTRIES,
    content_cid_for_bytes,
    version_cid_for,
)

# ---------------------------------------------------------------------------
# Schema / bounds
# ---------------------------------------------------------------------------

STORAGE_CONTRACT_VERSION: Final[int] = 1
STORAGE_SCHEMA_MAJOR: Final[int] = 1
STORAGE_SCHEMA_MINOR: Final[int] = 0
STORAGE_SCHEMA_PATCH: Final[int] = 0
STORAGE_SCHEMA_VERSION: Final[str] = (
    f"{STORAGE_SCHEMA_MAJOR}.{STORAGE_SCHEMA_MINOR}.{STORAGE_SCHEMA_PATCH}"
)
RANGED_VFS_STORAGE_SCHEMA: Final[str] = (
    f"ipfs_kit_py/core/vfs/storage/ranged@{STORAGE_SCHEMA_MAJOR}"
)
RangedVFSStorage_V1: Final[str] = RANGED_VFS_STORAGE_SCHEMA

DEFAULT_CHUNK_BYTES: Final[int] = 65_536  # 64 KiB
WHOLE_OBJECT_THRESHOLD_BYTES: Final[int] = 1_048_576  # 1 MiB
MAX_RANGE_BYTES: Final[int] = 16 * 1024 * 1024  # 16 MiB single range bound
MAX_STAGE_BYTES: Final[int] = 1 << 40  # hard ceiling; practical bounds per adapter
MAX_EFFECT_LOG: Final[int] = 4_096
MAX_OPEN_STAGES: Final[int] = 256
_DEFAULT_BACKEND_ID: Final[str] = "backend:ranged"
_ROOT_PATH: Final[str] = ""

# Storage confinement is stricter than generic VFS sugar: a leading ``/`` is
# treated as absolute (not namespace-root sugar) so callers cannot smuggle
# host-absolute forms past the boundary.
_STORAGE_PATH_POLICY: Final[VFSPathPolicy] = VFSPathPolicy(
    allow_leading_slash=False,
    reject_absolute=True,
    reject_traversal=True,
    reject_backslash=True,
    reject_control_chars=True,
    reject_home_expansion=True,
    reject_env_expansion=True,
    reject_percent_encoded_separators=True,
)


# ---------------------------------------------------------------------------
# Vocabularies / errors
# ---------------------------------------------------------------------------


class StorageBackendKind(str, Enum):
    """Concrete backend families admitted by this module."""

    MEMORY = "memory"
    LOCAL = "local"
    IPFS = "ipfs"
    IROH = "iroh"


class StorageCapability(str, Enum):
    """Closed capability surface every adapter must declare."""

    STAT = "stat"
    LIST = "list"
    RANGE_READ = "range_read"
    STAGED_WRITE = "staged_write"
    DELETE = "delete"
    RENAME = "rename"


class StorageOp(str, Enum):
    """Observable effect operation names."""

    MKDIR = "mkdir"
    STAGED_WRITE = "staged_write"
    DELETE = "delete"
    RENAME = "rename"
    SEED = "seed"


class StorageErrorCode(str, Enum):
    """Typed storage-boundary failure codes (fail-closed)."""

    NOT_FOUND = "storage_not_found"
    ALREADY_EXISTS = "storage_already_exists"
    NOT_DIRECTORY = "storage_not_directory"
    IS_DIRECTORY = "storage_is_directory"
    NOT_EMPTY = "storage_not_empty"
    PATH_ESCAPE = "storage_path_escape"
    INVALID_PATH = "storage_invalid_path"
    INVALID_RANGE = "storage_invalid_range"
    INVALID_STAGE = "storage_invalid_stage"
    IMMUTABLE = "storage_immutable"
    UNAVAILABLE = "storage_unavailable"
    READ_ONLY = "storage_read_only"
    UNSUPPORTED = "storage_unsupported"
    BOUND_EXCEEDED = "storage_bound_exceeded"
    CONFLICT = "storage_conflict"
    INTERNAL = "storage_internal"


class RangedStorageError(Exception):
    """Explicit rejection from a ranged storage adapter."""

    def __init__(
        self,
        message: str,
        *,
        code: StorageErrorCode,
        path: str = "",
        backend_id: str = "",
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code if isinstance(code, StorageErrorCode) else StorageErrorCode(code)
        self.path = path
        self.backend_id = backend_id
        self.detail = dict(detail or {})

    def to_record(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "message": self.message,
            "path": self.path,
            "backend_id": self.backend_id,
            "detail": dict(self.detail),
        }


# ---------------------------------------------------------------------------
# Public records
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StorageStat:
    """Metadata for one namespace entry (no raw body)."""

    path: str
    kind: VFSEntryKind
    size_bytes: int = 0
    content_cid: str = ""
    version_cid: str = ""
    generation: int = 0
    mtime_unix_ms: int = 0
    mode: int = 0
    is_readonly: bool = False
    backend_id: str = ""
    mount_id: str = "mount:default"
    chunk_bytes: int = DEFAULT_CHUNK_BYTES

    def __post_init__(self) -> None:
        if not isinstance(self.kind, VFSEntryKind):
            object.__setattr__(self, "kind", VFSEntryKind(self.kind))

    def to_record(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "kind": self.kind.value,
            "size_bytes": self.size_bytes,
            "content_cid": self.content_cid,
            "version_cid": self.version_cid,
            "generation": self.generation,
            "mtime_unix_ms": self.mtime_unix_ms,
            "mode": self.mode,
            "is_readonly": self.is_readonly,
            "backend_id": self.backend_id,
            "mount_id": self.mount_id,
            "chunk_bytes": self.chunk_bytes,
        }


@dataclass(frozen=True)
class StorageDirEntry:
    """One directory listing entry."""

    name: str
    kind: VFSEntryKind
    size_bytes: int = 0
    version_cid: str = ""
    content_cid: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.kind, VFSEntryKind):
            object.__setattr__(self, "kind", VFSEntryKind(self.kind))

    def to_record(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind.value,
            "size_bytes": self.size_bytes,
            "version_cid": self.version_cid,
            "content_cid": self.content_cid,
        }


@dataclass(frozen=True)
class StorageListing:
    """Stable directory listing under a confined path."""

    path: str
    entries: tuple[StorageDirEntry, ...]
    generation: int = 0
    backend_id: str = ""

    def to_record(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "entries": [entry.to_record() for entry in self.entries],
            "generation": self.generation,
            "backend_id": self.backend_id,
        }


@dataclass(frozen=True)
class RangeReadResult:
    """Result of a confined range read.

    ``chunks_touched`` is the number of storage chunks consulted.  For files
    larger than :data:`WHOLE_OBJECT_THRESHOLD_BYTES`, a partial read must not
    touch every chunk of the object.
    """

    path: str
    offset: int
    length: int
    data: bytes
    size_bytes: int
    content_cid: str
    version_cid: str
    generation: int
    chunks_touched: int
    backend_id: str = ""

    def to_record(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "offset": self.offset,
            "length": self.length,
            "data_size": len(self.data),
            "size_bytes": self.size_bytes,
            "content_cid": self.content_cid,
            "version_cid": self.version_cid,
            "generation": self.generation,
            "chunks_touched": self.chunks_touched,
            "backend_id": self.backend_id,
        }


@dataclass(frozen=True)
class StorageEffect:
    """One observable admitted mutation effect."""

    effect_id: str
    op: StorageOp
    path: str
    generation: int
    content_cid: str = ""
    version_cid: str = ""
    size_bytes: int = 0
    target_path: str = ""
    backend_id: str = ""
    detail: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.op, StorageOp):
            object.__setattr__(self, "op", StorageOp(self.op))
        object.__setattr__(self, "detail", dict(self.detail))

    def to_record(self) -> dict[str, Any]:
        return {
            "effect_id": self.effect_id,
            "op": self.op.value,
            "path": self.path,
            "target_path": self.target_path,
            "generation": self.generation,
            "content_cid": self.content_cid,
            "version_cid": self.version_cid,
            "size_bytes": self.size_bytes,
            "backend_id": self.backend_id,
            "detail": dict(self.detail),
        }


@dataclass(frozen=True)
class StageHandle:
    """Opaque staged-write session handle."""

    stage_id: str
    path: str
    backend_id: str = ""
    generation_at_open: int = 0

    def to_record(self) -> dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "path": self.path,
            "backend_id": self.backend_id,
            "generation_at_open": self.generation_at_open,
        }


@dataclass
class _StageState:
    """Mutable staged-write workspace (internal)."""

    handle: StageHandle
    path: str
    chunks: dict[int, bytes] = field(default_factory=dict)
    size_bytes: int = 0
    truncate: bool = True
    base_chunks: dict[int, bytes] = field(default_factory=dict)
    base_size: int = 0
    base_content_cid: str = ""
    dirty: bool = False


@dataclass
class _FileRecord:
    """Internal file/directory record with optional chunk map."""

    kind: VFSEntryKind
    size_bytes: int = 0
    content_cid: str = ""
    version_cid: str = ""
    chunks: dict[int, bytes] = field(default_factory=dict)
    target: str = ""
    mtime_unix_ms: int = 0
    mode: int = 0
    is_readonly: bool = False
    mount_id: str = "mount:default"
    # Backend-specific locator (CID, blob hash, relative file path, …).
    locator: str = ""


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class RangedVFSStorageBoundary(Protocol):
    """Injected ranged storage boundary (KVFS-200 surface)."""

    @property
    def backend_kind(self) -> StorageBackendKind: ...

    @property
    def backend_id(self) -> str: ...

    @property
    def generation(self) -> int: ...

    @property
    def chunk_bytes(self) -> int: ...

    @property
    def is_available(self) -> bool: ...

    @property
    def is_immutable(self) -> bool: ...

    @property
    def capabilities(self) -> frozenset[StorageCapability]: ...

    def effects(self) -> tuple[StorageEffect, ...]: ...

    def snapshot_meta(self) -> dict[str, dict[str, Any]]: ...

    def stat(self, path: str) -> StorageStat: ...

    def list(self, path: str) -> StorageListing: ...

    def range_read(self, path: str, offset: int, length: int) -> RangeReadResult: ...

    def begin_staged_write(
        self,
        path: str,
        *,
        truncate: bool = True,
    ) -> StageHandle: ...

    def stage_write(self, handle: StageHandle, offset: int, data: bytes) -> None: ...

    def commit_staged_write(self, handle: StageHandle) -> StorageEffect: ...

    def abort_staged_write(self, handle: StageHandle) -> None: ...

    def delete(self, path: str) -> StorageEffect: ...

    def rename(self, source: str, target: str) -> StorageEffect: ...


# ---------------------------------------------------------------------------
# Chunk helpers
# ---------------------------------------------------------------------------


def _require_non_negative_int(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RangedStorageError(
            f"{name} must be a non-negative integer",
            code=StorageErrorCode.INVALID_RANGE,
            detail={"field": name, "value": value},
        )
    return value


def _chunk_index(offset: int, chunk_bytes: int) -> int:
    return offset // chunk_bytes


def _chunk_span(offset: int, length: int, chunk_bytes: int) -> tuple[int, int]:
    """Return inclusive chunk index range covering ``[offset, offset+length)``."""

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
    """Write ``data`` at ``offset`` into a sparse chunk map; return new size."""

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
        # Store only the live prefix of the final chunk when it is the EOF chunk.
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
    """Read a range from a sparse chunk map; return ``(data, chunks_touched)``."""

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
        # Existing chunk may be full-size or a short final chunk.
        piece = existing[rel_start:rel_end]
        if len(piece) < (rel_end - rel_start):
            piece = piece + b"\x00" * ((rel_end - rel_start) - len(piece))
        out.extend(piece)
    return bytes(out), touched


def _content_cid_from_chunks(
    chunks: Mapping[int, bytes],
    *,
    size_bytes: int,
    chunk_bytes: int,
) -> str:
    """Deterministic content identity over chunk digests (no whole-body concat)."""

    if size_bytes == 0:
        return content_cid_for_bytes(b"")
    digests: list[str] = []
    total_chunks = (size_bytes + chunk_bytes - 1) // chunk_bytes if size_bytes else 0
    for index in range(total_chunks):
        chunk_start = index * chunk_bytes
        live = min(chunk_bytes, size_bytes - chunk_start)
        existing = chunks.get(index)
        if existing is None:
            payload = b"\x00" * live
        else:
            payload = existing[:live]
            if len(payload) < live:
                payload = payload + b"\x00" * (live - len(payload))
        digests.append(hashlib.sha256(payload).hexdigest())
    material = {
        "chunk_bytes": chunk_bytes,
        "size_bytes": size_bytes,
        "chunk_digests": digests,
    }
    return content_identity(material)


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


# ---------------------------------------------------------------------------
# Base adapter
# ---------------------------------------------------------------------------


class _BaseRangedStorage:
    """Shared confinement, generation, effect log, and stage management."""

    SCHEMA: ClassVar[str] = RANGED_VFS_STORAGE_SCHEMA
    CONTRACT_VERSION: ClassVar[int] = STORAGE_CONTRACT_VERSION

    def __init__(
        self,
        *,
        backend_kind: StorageBackendKind,
        backend_id: str,
        chunk_bytes: int = DEFAULT_CHUNK_BYTES,
        max_entries: int = MAX_NAMESPACE_ENTRIES,
        available: bool = True,
        immutable: bool = False,
        read_only: bool = False,
        clock: Any | None = None,
    ) -> None:
        if not isinstance(chunk_bytes, int) or isinstance(chunk_bytes, bool) or chunk_bytes < 1:
            raise RangedStorageError(
                "chunk_bytes must be a positive integer",
                code=StorageErrorCode.INTERNAL,
            )
        if chunk_bytes > MAX_RANGE_BYTES:
            raise RangedStorageError(
                "chunk_bytes exceeds admitted bound",
                code=StorageErrorCode.BOUND_EXCEEDED,
            )
        self._backend_kind = backend_kind
        self._backend_id = backend_id or f"backend:{backend_kind.value}"
        self._chunk_bytes = chunk_bytes
        self._max_entries = max_entries
        self._available = bool(available)
        self._immutable = bool(immutable)
        self._read_only = bool(read_only) or bool(immutable)
        self._clock = clock or (lambda: int(time.time() * 1000))
        self._generation = 0
        self._effects: list[StorageEffect] = []
        self._stages: dict[str, _StageState] = {}
        self._lock = threading.RLock()
        self._entries: dict[str, _FileRecord] = {
            _ROOT_PATH: _FileRecord(
                kind=VFSEntryKind.DIRECTORY,
                content_cid=content_cid_for_bytes(b""),
                version_cid=version_cid_for(
                    _ROOT_PATH,
                    kind=VFSEntryKind.DIRECTORY,
                    content_cid="",
                    generation=0,
                ),
                mtime_unix_ms=0,
            )
        }

    # -- identity / capability ----------------------------------------------

    @property
    def backend_kind(self) -> StorageBackendKind:
        return self._backend_kind

    @property
    def backend_id(self) -> str:
        return self._backend_id

    @property
    def generation(self) -> int:
        return self._generation

    @property
    def chunk_bytes(self) -> int:
        return self._chunk_bytes

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def is_immutable(self) -> bool:
        return self._immutable

    @property
    def is_read_only(self) -> bool:
        return self._read_only

    @property
    def capabilities(self) -> frozenset[StorageCapability]:
        return frozenset(StorageCapability)

    def set_available(self, available: bool) -> None:
        """Test/operator hook: mark backend availability."""

        self._available = bool(available)

    def effects(self) -> tuple[StorageEffect, ...]:
        with self._lock:
            return tuple(self._effects)

    def snapshot_meta(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return {
                path: self._record_to_stat(path, record).to_record()
                for path, record in sorted(self._entries.items())
            }

    def entry_count(self) -> int:
        with self._lock:
            return len(self._entries)

    # -- path confinement ---------------------------------------------------

    def _normalize(self, path: str) -> str:
        # Empty string is the confined namespace root (not an OS absolute form).
        if path == "" or path is None:
            return _ROOT_PATH
        if not isinstance(path, str):
            raise RangedStorageError(
                "path must be a string",
                code=StorageErrorCode.INVALID_PATH,
                path=repr(path),
                backend_id=self._backend_id,
            )
        # Fast pre-checks so absolute/escape forms never collapse into a
        # relative lookup that would surface as NOT_FOUND.
        if path.startswith("/") or path.startswith("\\"):
            raise RangedStorageError(
                f"absolute path rejected by storage confinement: {path!r}",
                code=StorageErrorCode.PATH_ESCAPE,
                path=path,
                backend_id=self._backend_id,
                detail={"reason": "absolute"},
            )
        try:
            return normalize_vfs_path(path, policy=_STORAGE_PATH_POLICY).path
        except VFSPathError as exc:
            reason = getattr(exc, "reason", None)
            reason_value = reason.value if reason is not None else ""
            escape_reasons = {
                "escape",
                "traversal",
                "absolute",
                "windows_drive",
                "unc",
                "home_expansion",
                "env_expansion",
                "backslash",
                "percent_encoded_separator",
                "symlink_escape",
                "root_mismatch",
            }
            code = (
                StorageErrorCode.PATH_ESCAPE
                if reason_value in escape_reasons
                else StorageErrorCode.INVALID_PATH
            )
            raise RangedStorageError(
                str(exc),
                code=code,
                path=path,
                backend_id=self._backend_id,
                detail={"reason": reason_value},
            ) from exc

    def _require_available(self, *, path: str = "") -> None:
        if not self._available:
            raise RangedStorageError(
                f"backend {self._backend_id!r} is unavailable",
                code=StorageErrorCode.UNAVAILABLE,
                path=path,
                backend_id=self._backend_id,
            )

    def _require_mutable(self, *, path: str = "", op: str = "mutation") -> None:
        self._require_available(path=path)
        if self._immutable:
            raise RangedStorageError(
                f"backend {self._backend_id!r} is immutable; rejecting {op}",
                code=StorageErrorCode.IMMUTABLE,
                path=path,
                backend_id=self._backend_id,
                detail={"op": op},
            )
        if self._read_only:
            raise RangedStorageError(
                f"backend {self._backend_id!r} is read-only; rejecting {op}",
                code=StorageErrorCode.READ_ONLY,
                path=path,
                backend_id=self._backend_id,
                detail={"op": op},
            )

    # -- generation / effects -----------------------------------------------

    def _bump(self) -> int:
        self._generation += 1
        return self._generation

    def _now(self) -> int:
        return int(self._clock())

    def _record_effect(
        self,
        op: StorageOp,
        path: str,
        *,
        generation: int,
        content_cid: str = "",
        version_cid: str = "",
        size_bytes: int = 0,
        target_path: str = "",
        detail: Mapping[str, Any] | None = None,
    ) -> StorageEffect:
        effect = StorageEffect(
            effect_id=f"effect:{secrets.token_hex(8)}",
            op=op,
            path=path,
            target_path=target_path,
            generation=generation,
            content_cid=content_cid,
            version_cid=version_cid,
            size_bytes=size_bytes,
            backend_id=self._backend_id,
            detail=dict(detail or {}),
        )
        self._effects.append(effect)
        if len(self._effects) > MAX_EFFECT_LOG:
            self._effects = self._effects[-MAX_EFFECT_LOG:]
        return effect

    def _record_to_stat(self, path: str, record: _FileRecord) -> StorageStat:
        return StorageStat(
            path=path,
            kind=record.kind,
            size_bytes=0 if record.kind is VFSEntryKind.DIRECTORY else record.size_bytes,
            content_cid=record.content_cid,
            version_cid=record.version_cid,
            generation=self._generation,
            mtime_unix_ms=record.mtime_unix_ms,
            mode=record.mode,
            is_readonly=record.is_readonly or self._read_only,
            backend_id=self._backend_id,
            mount_id=record.mount_id,
            chunk_bytes=self._chunk_bytes,
        )

    # -- namespace helpers ---------------------------------------------------

    def _get(self, path: str) -> _FileRecord | None:
        return self._entries.get(path)

    def _ensure_parents(self, path: str) -> None:
        if not path:
            return
        segments = path.split("/")
        acc: list[str] = []
        for seg in segments[:-1]:
            acc.append(seg)
            parent = "/".join(acc)
            existing = self._get(parent)
            if existing is None:
                gen = self._generation
                self._entries[parent] = _FileRecord(
                    kind=VFSEntryKind.DIRECTORY,
                    content_cid=content_cid_for_bytes(b""),
                    version_cid=version_cid_for(
                        parent,
                        kind=VFSEntryKind.DIRECTORY,
                        content_cid="",
                        generation=gen,
                    ),
                    mtime_unix_ms=self._now(),
                )
            elif existing.kind is not VFSEntryKind.DIRECTORY:
                raise RangedStorageError(
                    f"parent {parent!r} is not a directory",
                    code=StorageErrorCode.NOT_DIRECTORY,
                    path=parent,
                    backend_id=self._backend_id,
                )

    def _children_names(self, path: str) -> tuple[str, ...]:
        prefix = "" if path == "" else path + "/"
        names: set[str] = set()
        for key in self._entries:
            if key == path or key == "":
                continue
            if path == "":
                names.add(key.split("/", 1)[0])
            elif key.startswith(prefix):
                rest = key[len(prefix) :]
                if rest:
                    names.add(rest.split("/", 1)[0])
        return tuple(sorted(names, key=lambda n: n.encode("utf-8")))

    def _require_entry(self, path: str) -> _FileRecord:
        entry = self._get(path)
        if entry is None:
            raise RangedStorageError(
                f"path not found: {path!r}",
                code=StorageErrorCode.NOT_FOUND,
                path=path,
                backend_id=self._backend_id,
            )
        return entry

    # -- public ops ---------------------------------------------------------

    def stat(self, path: str) -> StorageStat:
        self._require_available(path=path)
        with self._lock:
            norm = self._normalize(path)
            entry = self._require_entry(norm)
            return self._record_to_stat(norm, entry)

    def list(self, path: str) -> StorageListing:
        self._require_available(path=path)
        with self._lock:
            norm = self._normalize(path)
            entry = self._require_entry(norm)
            if entry.kind is not VFSEntryKind.DIRECTORY:
                raise RangedStorageError(
                    f"list requires a directory: {norm!r}",
                    code=StorageErrorCode.NOT_DIRECTORY,
                    path=norm,
                    backend_id=self._backend_id,
                )
            items: list[StorageDirEntry] = []
            for name in self._children_names(norm):
                child_path = name if norm == "" else f"{norm}/{name}"
                child = self._get(child_path)
                if child is None:
                    continue
                items.append(
                    StorageDirEntry(
                        name=name,
                        kind=child.kind,
                        size_bytes=0
                        if child.kind is VFSEntryKind.DIRECTORY
                        else child.size_bytes,
                        version_cid=child.version_cid,
                        content_cid=child.content_cid,
                    )
                )
            return StorageListing(
                path=norm,
                entries=tuple(items),
                generation=self._generation,
                backend_id=self._backend_id,
            )

    def range_read(self, path: str, offset: int, length: int) -> RangeReadResult:
        self._require_available(path=path)
        offset = _require_non_negative_int(offset, "offset")
        length = _require_non_negative_int(length, "length")
        if length > MAX_RANGE_BYTES:
            raise RangedStorageError(
                "range length exceeds admitted bound",
                code=StorageErrorCode.BOUND_EXCEEDED,
                path=path,
                backend_id=self._backend_id,
                detail={"length": length, "max": MAX_RANGE_BYTES},
            )
        with self._lock:
            norm = self._normalize(path)
            entry = self._require_entry(norm)
            if entry.kind is not VFSEntryKind.FILE:
                raise RangedStorageError(
                    f"range_read requires a file: {norm!r}",
                    code=StorageErrorCode.IS_DIRECTORY,
                    path=norm,
                    backend_id=self._backend_id,
                )
            data, touched = self._range_read_impl(entry, offset=offset, length=length)
            return RangeReadResult(
                path=norm,
                offset=offset,
                length=len(data),
                data=data,
                size_bytes=entry.size_bytes,
                content_cid=entry.content_cid,
                version_cid=entry.version_cid,
                generation=self._generation,
                chunks_touched=touched,
                backend_id=self._backend_id,
            )

    def _range_read_impl(
        self, entry: _FileRecord, *, offset: int, length: int
    ) -> tuple[bytes, int]:
        return _read_from_chunks(
            entry.chunks,
            size_bytes=entry.size_bytes,
            offset=offset,
            length=length,
            chunk_bytes=self._chunk_bytes,
        )

    def begin_staged_write(
        self,
        path: str,
        *,
        truncate: bool = True,
    ) -> StageHandle:
        self._require_mutable(path=path, op="staged_write")
        with self._lock:
            if len(self._stages) >= MAX_OPEN_STAGES:
                raise RangedStorageError(
                    "open staged-write bound exceeded",
                    code=StorageErrorCode.BOUND_EXCEEDED,
                    path=path,
                    backend_id=self._backend_id,
                )
            norm = self._normalize(path)
            if norm == _ROOT_PATH:
                raise RangedStorageError(
                    "cannot staged-write the namespace root",
                    code=StorageErrorCode.UNSUPPORTED,
                    path=norm,
                    backend_id=self._backend_id,
                )
            existing = self._get(norm)
            if existing is not None and existing.kind is VFSEntryKind.DIRECTORY:
                raise RangedStorageError(
                    f"cannot staged-write a directory: {norm!r}",
                    code=StorageErrorCode.IS_DIRECTORY,
                    path=norm,
                    backend_id=self._backend_id,
                )
            if existing is not None and existing.is_readonly:
                raise RangedStorageError(
                    f"entry is immutable/read-only: {norm!r}",
                    code=StorageErrorCode.IMMUTABLE,
                    path=norm,
                    backend_id=self._backend_id,
                )
            handle = StageHandle(
                stage_id=f"stage:{secrets.token_hex(12)}",
                path=norm,
                backend_id=self._backend_id,
                generation_at_open=self._generation,
            )
            if existing is not None and not truncate:
                # Materialise base content so non-truncate partial stages keep
                # prior bytes even when the adapter dropped in-memory chunks
                # after publish (e.g. local disk bodies).
                base_chunks = self._materialize_chunks(existing)
                base_size = existing.size_bytes
                base_cid = existing.content_cid
            else:
                base_chunks = {}
                base_size = 0
                base_cid = ""
            self._stages[handle.stage_id] = _StageState(
                handle=handle,
                path=norm,
                chunks=dict(base_chunks),
                size_bytes=base_size,
                truncate=truncate,
                base_chunks=dict(base_chunks),
                base_size=base_size,
                base_content_cid=base_cid,
            )
            return handle

    def stage_write(self, handle: StageHandle, offset: int, data: bytes) -> None:
        self._require_mutable(path=handle.path, op="stage_write")
        offset = _require_non_negative_int(offset, "offset")
        if not isinstance(data, (bytes, bytearray)):
            raise RangedStorageError(
                "stage_write data must be bytes",
                code=StorageErrorCode.INVALID_STAGE,
                path=handle.path,
                backend_id=self._backend_id,
            )
        payload = bytes(data)
        if offset + len(payload) > MAX_STAGE_BYTES:
            raise RangedStorageError(
                "staged write exceeds size bound",
                code=StorageErrorCode.BOUND_EXCEEDED,
                path=handle.path,
                backend_id=self._backend_id,
            )
        with self._lock:
            stage = self._stages.get(handle.stage_id)
            if stage is None or stage.path != handle.path:
                raise RangedStorageError(
                    "unknown or mismatched stage handle",
                    code=StorageErrorCode.INVALID_STAGE,
                    path=handle.path,
                    backend_id=self._backend_id,
                )
            stage.size_bytes = _write_into_chunks(
                stage.chunks,
                size_bytes=stage.size_bytes,
                offset=offset,
                data=payload,
                chunk_bytes=self._chunk_bytes,
            )
            stage.dirty = True

    def commit_staged_write(self, handle: StageHandle) -> StorageEffect:
        self._require_mutable(path=handle.path, op="commit_staged_write")
        with self._lock:
            stage = self._stages.pop(handle.stage_id, None)
            if stage is None or stage.path != handle.path:
                raise RangedStorageError(
                    "unknown or mismatched stage handle",
                    code=StorageErrorCode.INVALID_STAGE,
                    path=handle.path,
                    backend_id=self._backend_id,
                )
            path = stage.path
            self._ensure_parents(path)
            if path not in self._entries and len(self._entries) >= self._max_entries:
                raise RangedStorageError(
                    "namespace entry bound exceeded",
                    code=StorageErrorCode.BOUND_EXCEEDED,
                    path=path,
                    backend_id=self._backend_id,
                )
            _trim_chunks_to_size(
                stage.chunks,
                size_bytes=stage.size_bytes,
                chunk_bytes=self._chunk_bytes,
            )
            content_cid = _content_cid_from_chunks(
                stage.chunks,
                size_bytes=stage.size_bytes,
                chunk_bytes=self._chunk_bytes,
            )
            gen = self._bump()
            version = version_cid_for(
                path,
                kind=VFSEntryKind.FILE,
                content_cid=content_cid,
                generation=gen,
            )
            locator = self._publish_locator(
                path, stage.chunks, stage.size_bytes, content_cid
            )
            retained_chunks = self._retain_chunks_after_publish(
                dict(stage.chunks), locator=locator
            )
            record = _FileRecord(
                kind=VFSEntryKind.FILE,
                size_bytes=stage.size_bytes,
                content_cid=content_cid,
                version_cid=version,
                chunks=retained_chunks,
                mtime_unix_ms=self._now(),
                locator=locator,
            )
            self._entries[path] = record
            return self._record_effect(
                StorageOp.STAGED_WRITE,
                path,
                generation=gen,
                content_cid=content_cid,
                version_cid=version,
                size_bytes=stage.size_bytes,
                detail={
                    "truncate": stage.truncate,
                    "chunk_bytes": self._chunk_bytes,
                    "chunks": len(stage.chunks),
                },
            )

    def abort_staged_write(self, handle: StageHandle) -> None:
        with self._lock:
            self._stages.pop(handle.stage_id, None)

    def delete(self, path: str) -> StorageEffect:
        self._require_mutable(path=path, op="delete")
        with self._lock:
            norm = self._normalize(path)
            if norm == _ROOT_PATH:
                raise RangedStorageError(
                    "cannot delete namespace root",
                    code=StorageErrorCode.UNSUPPORTED,
                    path=norm,
                    backend_id=self._backend_id,
                )
            entry = self._require_entry(norm)
            if entry.is_readonly:
                raise RangedStorageError(
                    f"entry is immutable/read-only: {norm!r}",
                    code=StorageErrorCode.IMMUTABLE,
                    path=norm,
                    backend_id=self._backend_id,
                )
            if entry.kind is VFSEntryKind.DIRECTORY and self._children_names(norm):
                raise RangedStorageError(
                    f"directory not empty: {norm!r}",
                    code=StorageErrorCode.NOT_EMPTY,
                    path=norm,
                    backend_id=self._backend_id,
                )
            self._on_delete(norm, entry)
            del self._entries[norm]
            gen = self._bump()
            return self._record_effect(
                StorageOp.DELETE,
                norm,
                generation=gen,
                content_cid=entry.content_cid,
                version_cid=entry.version_cid,
                size_bytes=entry.size_bytes,
            )

    def rename(self, source: str, target: str) -> StorageEffect:
        self._require_mutable(path=source, op="rename")
        with self._lock:
            src = self._normalize(source)
            dst = self._normalize(target)
            if src == _ROOT_PATH:
                raise RangedStorageError(
                    "cannot rename namespace root",
                    code=StorageErrorCode.UNSUPPORTED,
                    path=src,
                    backend_id=self._backend_id,
                )
            if src == dst:
                entry = self._require_entry(src)
                return self._record_effect(
                    StorageOp.RENAME,
                    src,
                    generation=self._generation,
                    content_cid=entry.content_cid,
                    version_cid=entry.version_cid,
                    size_bytes=entry.size_bytes,
                    target_path=dst,
                    detail={"noop": True},
                )
            if dst == _ROOT_PATH or dst.startswith(src + "/"):
                raise RangedStorageError(
                    "rename target collides with source subtree",
                    code=StorageErrorCode.CONFLICT,
                    path=src,
                    backend_id=self._backend_id,
                    detail={"target": dst},
                )
            entry = self._require_entry(src)
            if entry.is_readonly:
                raise RangedStorageError(
                    f"entry is immutable/read-only: {src!r}",
                    code=StorageErrorCode.IMMUTABLE,
                    path=src,
                    backend_id=self._backend_id,
                )
            if self._get(dst) is not None:
                raise RangedStorageError(
                    f"rename target already exists: {dst!r}",
                    code=StorageErrorCode.ALREADY_EXISTS,
                    path=dst,
                    backend_id=self._backend_id,
                )
            self._ensure_parents(dst)
            moves: list[tuple[str, str, _FileRecord]] = []
            for key, rec in list(self._entries.items()):
                if key == src or key.startswith(src + "/"):
                    suffix = key[len(src) :]
                    moves.append((key, dst + suffix, rec))
            projected = len(self._entries) - len(moves) + len(moves)
            if projected > self._max_entries:
                raise RangedStorageError(
                    "namespace entry bound exceeded during rename",
                    code=StorageErrorCode.BOUND_EXCEEDED,
                    path=src,
                    backend_id=self._backend_id,
                )
            for old, _new, _rec in moves:
                del self._entries[old]
            for old, new, rec in moves:
                self._on_rename(old, new, rec)
                self._entries[new] = rec
            gen = self._bump()
            # Rebind version identity of the renamed root entry.
            moved = self._entries[dst]
            moved.version_cid = version_cid_for(
                dst,
                kind=moved.kind,
                content_cid=moved.content_cid,
                generation=gen,
                target=moved.target,
            )
            moved.mtime_unix_ms = self._now()
            return self._record_effect(
                StorageOp.RENAME,
                src,
                generation=gen,
                content_cid=moved.content_cid,
                version_cid=moved.version_cid,
                size_bytes=moved.size_bytes,
                target_path=dst,
            )

    def mkdir(self, path: str) -> StorageEffect:
        """Create a directory (helper used by adapters and tests)."""

        self._require_mutable(path=path, op="mkdir")
        with self._lock:
            norm = self._normalize(path)
            if norm == _ROOT_PATH:
                entry = self._require_entry(norm)
                return self._record_effect(
                    StorageOp.MKDIR,
                    norm,
                    generation=self._generation,
                    content_cid=entry.content_cid,
                    version_cid=entry.version_cid,
                    detail={"noop": True},
                )
            if self._get(norm) is not None:
                raise RangedStorageError(
                    f"path already exists: {norm!r}",
                    code=StorageErrorCode.ALREADY_EXISTS,
                    path=norm,
                    backend_id=self._backend_id,
                )
            self._ensure_parents(norm)
            if len(self._entries) >= self._max_entries:
                raise RangedStorageError(
                    "namespace entry bound exceeded",
                    code=StorageErrorCode.BOUND_EXCEEDED,
                    path=norm,
                    backend_id=self._backend_id,
                )
            gen = self._bump()
            cid = content_cid_for_bytes(b"")
            version = version_cid_for(
                norm, kind=VFSEntryKind.DIRECTORY, content_cid=cid, generation=gen
            )
            self._entries[norm] = _FileRecord(
                kind=VFSEntryKind.DIRECTORY,
                content_cid=cid,
                version_cid=version,
                mtime_unix_ms=self._now(),
            )
            return self._record_effect(
                StorageOp.MKDIR,
                norm,
                generation=gen,
                content_cid=cid,
                version_cid=version,
            )

    def seed_file(
        self,
        path: str,
        data: bytes | bytearray | memoryview | None = None,
        *,
        size_bytes: int | None = None,
        pattern: bytes = b"\x00",
        readonly: bool = False,
    ) -> StorageEffect:
        """Seed a file without requiring the caller to hold a full body.

        When ``size_bytes`` is provided, content is synthesised chunk-by-chunk
        from ``pattern`` so tests can create multi-MiB objects without
        allocating a whole-object buffer in the caller.
        """

        self._require_mutable(path=path, op="seed")
        with self._lock:
            norm = self._normalize(path)
            if norm == _ROOT_PATH:
                raise RangedStorageError(
                    "cannot seed over namespace root",
                    code=StorageErrorCode.UNSUPPORTED,
                    path=norm,
                    backend_id=self._backend_id,
                )
            self._ensure_parents(norm)
            if norm not in self._entries and len(self._entries) >= self._max_entries:
                raise RangedStorageError(
                    "namespace entry bound exceeded",
                    code=StorageErrorCode.BOUND_EXCEEDED,
                    path=norm,
                    backend_id=self._backend_id,
                )
            chunks: dict[int, bytes] = {}
            if data is not None:
                payload = bytes(data)
                size = len(payload)
                _write_into_chunks(
                    chunks,
                    size_bytes=0,
                    offset=0,
                    data=payload,
                    chunk_bytes=self._chunk_bytes,
                )
            else:
                if size_bytes is None:
                    size = 0
                else:
                    size = _require_non_negative_int(size_bytes, "size_bytes")
                if not isinstance(pattern, (bytes, bytearray)) or not pattern:
                    pattern = b"\x00"
                pattern_b = bytes(pattern)
                remaining = size
                offset = 0
                while remaining > 0:
                    take = min(self._chunk_bytes, remaining)
                    # Tile the pattern from the global offset so chunk
                    # boundaries do not reset the stream phase.
                    reps = ((offset + take) // len(pattern_b)) + 1
                    piece = (pattern_b * reps)[offset : offset + take]
                    _write_into_chunks(
                        chunks,
                        size_bytes=offset,
                        offset=offset,
                        data=piece,
                        chunk_bytes=self._chunk_bytes,
                    )
                    offset += take
                    remaining -= take
            _trim_chunks_to_size(chunks, size_bytes=size, chunk_bytes=self._chunk_bytes)
            content_cid = _content_cid_from_chunks(
                chunks, size_bytes=size, chunk_bytes=self._chunk_bytes
            )
            gen = self._bump()
            version = version_cid_for(
                norm,
                kind=VFSEntryKind.FILE,
                content_cid=content_cid,
                generation=gen,
            )
            locator = self._publish_locator(norm, chunks, size, content_cid)
            retained_chunks = self._retain_chunks_after_publish(
                chunks, locator=locator
            )
            self._entries[norm] = _FileRecord(
                kind=VFSEntryKind.FILE,
                size_bytes=size,
                content_cid=content_cid,
                version_cid=version,
                chunks=retained_chunks,
                mtime_unix_ms=self._now(),
                is_readonly=readonly,
                locator=locator,
            )
            return self._record_effect(
                StorageOp.SEED,
                norm,
                generation=gen,
                content_cid=content_cid,
                version_cid=version,
                size_bytes=size,
                detail={"readonly": readonly},
            )

    # -- backend hooks ------------------------------------------------------

    def _materialize_chunks(self, entry: _FileRecord) -> dict[int, bytes]:
        """Return a chunk map suitable as non-truncate staged-write base.

        Adapters that drop in-memory bodies after publish must reload from
        their durable locator so partial overwrites preserve prior bytes.
        """

        if entry.chunks:
            return dict(entry.chunks)
        if entry.size_bytes <= 0:
            return {}
        return self._load_chunks_from_backend(entry)

    def _load_chunks_from_backend(self, entry: _FileRecord) -> dict[int, bytes]:
        """Backend-specific reload of file body into a sparse chunk map."""

        return {}

    def _publish_locator(
        self,
        path: str,
        chunks: Mapping[int, bytes],
        size_bytes: int,
        content_cid: str,
    ) -> str:
        """Backend-specific publish; default stores the content CID."""

        return content_cid

    def _retain_chunks_after_publish(
        self,
        chunks: dict[int, bytes],
        *,
        locator: str,
    ) -> dict[int, bytes]:
        """Return the chunk map to keep after publish.

        Local backends drop in-memory bodies once the object is on disk so
        multi-MiB files do not retain a whole-object RAM copy.
        """

        return chunks

    def _on_delete(self, path: str, entry: _FileRecord) -> None:
        return None

    def _on_rename(self, old: str, new: str, entry: _FileRecord) -> None:
        return None


# ---------------------------------------------------------------------------
# Memory adapter
# ---------------------------------------------------------------------------


class MemoryRangedStorage(_BaseRangedStorage):
    """Hermetic in-memory ranged storage (fully mutable when available)."""

    def __init__(
        self,
        *,
        backend_id: str = "backend:memory",
        chunk_bytes: int = DEFAULT_CHUNK_BYTES,
        max_entries: int = MAX_NAMESPACE_ENTRIES,
        available: bool = True,
        immutable: bool = False,
        read_only: bool = False,
        clock: Any | None = None,
    ) -> None:
        super().__init__(
            backend_kind=StorageBackendKind.MEMORY,
            backend_id=backend_id,
            chunk_bytes=chunk_bytes,
            max_entries=max_entries,
            available=available,
            immutable=immutable,
            read_only=read_only,
            clock=clock,
        )


# ---------------------------------------------------------------------------
# Local filesystem adapter
# ---------------------------------------------------------------------------


class LocalRangedStorage(_BaseRangedStorage):
    """Root-confined local filesystem adapter with ranged I/O.

    Namespace metadata lives in the in-memory index for generation/version
    observability.  File bodies live under ``root`` and are read with
    ``seek``/``read`` so multi-MiB objects never require whole-object loads.
    """

    def __init__(
        self,
        root: str | os.PathLike[str],
        *,
        backend_id: str = "backend:local",
        chunk_bytes: int = DEFAULT_CHUNK_BYTES,
        max_entries: int = MAX_NAMESPACE_ENTRIES,
        available: bool = True,
        immutable: bool = False,
        read_only: bool = False,
        clock: Any | None = None,
    ) -> None:
        super().__init__(
            backend_kind=StorageBackendKind.LOCAL,
            backend_id=backend_id,
            chunk_bytes=chunk_bytes,
            max_entries=max_entries,
            available=available,
            immutable=immutable,
            read_only=read_only,
            clock=clock,
        )
        self._root = Path(root).expanduser().resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        self._data_dir = self._root / "objects"
        self._stage_dir = self._root / "staging"
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._stage_dir.mkdir(parents=True, exist_ok=True)

    def _object_path(self, path: str) -> Path:
        # Encode namespace path as a single relative file name using POSIX form
        # under objects/, confined via resolve() against root.
        if path == _ROOT_PATH:
            raise RangedStorageError(
                "root has no object body",
                code=StorageErrorCode.UNSUPPORTED,
                path=path,
                backend_id=self._backend_id,
            )
        rel = PurePosixPath(path)
        if rel.is_absolute() or ".." in rel.parts:
            raise RangedStorageError(
                "path escapes local storage root",
                code=StorageErrorCode.PATH_ESCAPE,
                path=path,
                backend_id=self._backend_id,
            )
        candidate = (self._data_dir / Path(*rel.parts)).resolve()
        try:
            candidate.relative_to(self._data_dir.resolve())
        except ValueError as exc:
            raise RangedStorageError(
                "path escapes local storage root",
                code=StorageErrorCode.PATH_ESCAPE,
                path=path,
                backend_id=self._backend_id,
            ) from exc
        return candidate

    def _publish_locator(
        self,
        path: str,
        chunks: Mapping[int, bytes],
        size_bytes: int,
        content_cid: str,
    ) -> str:
        target = self._object_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._stage_dir / f"{secrets.token_hex(12)}.tmp"
        with open(tmp, "wb") as fh:
            if size_bytes == 0:
                pass
            else:
                total_chunks = (size_bytes + self._chunk_bytes - 1) // self._chunk_bytes
                for index in range(total_chunks):
                    chunk_start = index * self._chunk_bytes
                    live = min(self._chunk_bytes, size_bytes - chunk_start)
                    existing = chunks.get(index)
                    if existing is None:
                        fh.write(b"\x00" * live)
                    else:
                        piece = existing[:live]
                        if len(piece) < live:
                            piece = piece + b"\x00" * (live - len(piece))
                        fh.write(piece)
        os.replace(tmp, target)
        return str(target.relative_to(self._data_dir))

    def _retain_chunks_after_publish(
        self,
        chunks: dict[int, bytes],
        *,
        locator: str,
    ) -> dict[int, bytes]:
        # Bodies live on disk under ``locator``; drop the RAM map.
        if locator:
            return {}
        return chunks

    def _load_chunks_from_backend(self, entry: _FileRecord) -> dict[int, bytes]:
        """Reload on-disk body into chunks for non-truncate staged writes."""

        if not entry.locator or entry.size_bytes <= 0:
            return {}
        target = self._data_dir / entry.locator
        if not target.is_file():
            raise RangedStorageError(
                f"local object missing for {entry.locator!r}",
                code=StorageErrorCode.NOT_FOUND,
                backend_id=self._backend_id,
            )
        chunks: dict[int, bytes] = {}
        remaining = entry.size_bytes
        index = 0
        with open(target, "rb") as fh:
            while remaining > 0:
                take = min(self._chunk_bytes, remaining)
                piece = fh.read(take)
                if not piece:
                    # Sparse/truncated file: pad to declared size.
                    piece = b"\x00" * take
                elif len(piece) < take:
                    piece = piece + b"\x00" * (take - len(piece))
                chunks[index] = piece
                index += 1
                remaining -= take
        return chunks

    def _range_read_impl(
        self, entry: _FileRecord, *, offset: int, length: int
    ) -> tuple[bytes, int]:
        # Prefer on-disk seek when a locator exists; fall back to chunks.
        if entry.locator:
            target = self._data_dir / entry.locator
            if not target.is_file():
                raise RangedStorageError(
                    f"local object missing for {entry.locator!r}",
                    code=StorageErrorCode.NOT_FOUND,
                    backend_id=self._backend_id,
                )
            if offset >= entry.size_bytes or length <= 0:
                return b"", 0
            end = min(entry.size_bytes, offset + length)
            need = end - offset
            with open(target, "rb") as fh:
                fh.seek(offset)
                data = fh.read(need)
            first, last = _chunk_span(offset, len(data), self._chunk_bytes)
            touched = 0 if len(data) == 0 else (last - first + 1)
            return data, touched
        return super()._range_read_impl(entry, offset=offset, length=length)

    def _on_delete(self, path: str, entry: _FileRecord) -> None:
        if entry.kind is VFSEntryKind.FILE and entry.locator:
            target = self._data_dir / entry.locator
            try:
                if target.is_file():
                    target.unlink()
            except OSError:
                pass

    def _on_rename(self, old: str, new: str, entry: _FileRecord) -> None:
        if entry.kind is not VFSEntryKind.FILE or not entry.locator:
            return
        src = self._data_dir / entry.locator
        dst = self._object_path(new)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_file():
            os.replace(src, dst)
            entry.locator = str(dst.relative_to(self._data_dir))


# ---------------------------------------------------------------------------
# IPFS adapter (hermetic / injectable)
# ---------------------------------------------------------------------------


class IPFSRangedStorage(_BaseRangedStorage):
    """IPFS-oriented ranged adapter.

    Operates hermetically against an in-process block map keyed by content
    CID.  A live Kubo/IPFS client is optional; when ``available=False`` every
    operation rejects with :attr:`StorageErrorCode.UNAVAILABLE`.  When
    ``immutable=True`` (typical for pure CID mounts), staged writes, deletes,
    and renames reject with :attr:`StorageErrorCode.IMMUTABLE`.
    """

    def __init__(
        self,
        *,
        backend_id: str = "backend:ipfs",
        chunk_bytes: int = DEFAULT_CHUNK_BYTES,
        max_entries: int = MAX_NAMESPACE_ENTRIES,
        available: bool = True,
        immutable: bool = False,
        read_only: bool = False,
        clock: Any | None = None,
        block_store: MutableMapping[str, bytes] | None = None,
    ) -> None:
        super().__init__(
            backend_kind=StorageBackendKind.IPFS,
            backend_id=backend_id,
            chunk_bytes=chunk_bytes,
            max_entries=max_entries,
            available=available,
            immutable=immutable,
            read_only=read_only,
            clock=clock,
        )
        self._blocks: MutableMapping[str, bytes] = (
            block_store if block_store is not None else {}
        )

    @property
    def block_store(self) -> Mapping[str, bytes]:
        return dict(self._blocks)

    def _publish_locator(
        self,
        path: str,
        chunks: Mapping[int, bytes],
        size_bytes: int,
        content_cid: str,
    ) -> str:
        # Store each chunk under a deterministic block CID; root is content_cid.
        if size_bytes == 0:
            self._blocks[content_cid] = b""
            return content_cid
        total_chunks = (size_bytes + self._chunk_bytes - 1) // self._chunk_bytes
        for index in range(total_chunks):
            chunk_start = index * self._chunk_bytes
            live = min(self._chunk_bytes, size_bytes - chunk_start)
            existing = chunks.get(index, b"")[:live]
            if len(existing) < live:
                existing = existing + b"\x00" * (live - len(existing))
            block_cid = content_cid_for_bytes(
                b"ipfs-chunk:" + index.to_bytes(8, "big") + existing
            )
            self._blocks[block_cid] = existing
        self._blocks[content_cid] = content_cid.encode("utf-8")  # root marker
        return content_cid

    def _range_read_impl(
        self, entry: _FileRecord, *, offset: int, length: int
    ) -> tuple[bytes, int]:
        # Read only the chunks covering the requested range from the block map
        # when possible; fall back to in-record chunks.
        return super()._range_read_impl(entry, offset=offset, length=length)


# ---------------------------------------------------------------------------
# Iroh adapter (hermetic / injectable)
# ---------------------------------------------------------------------------


class IrohRangedStorage(_BaseRangedStorage):
    """Iroh-oriented ranged adapter.

    Hermetic blob map keyed by content identity.  Unavailable and immutable
    modes reject explicitly.  Range reads never reassemble the whole blob.
    """

    def __init__(
        self,
        *,
        backend_id: str = "backend:iroh",
        chunk_bytes: int = DEFAULT_CHUNK_BYTES,
        max_entries: int = MAX_NAMESPACE_ENTRIES,
        available: bool = True,
        immutable: bool = False,
        read_only: bool = False,
        clock: Any | None = None,
        blob_store: MutableMapping[str, bytes] | None = None,
    ) -> None:
        super().__init__(
            backend_kind=StorageBackendKind.IROH,
            backend_id=backend_id,
            chunk_bytes=chunk_bytes,
            max_entries=max_entries,
            available=available,
            immutable=immutable,
            read_only=read_only,
            clock=clock,
        )
        self._blobs: MutableMapping[str, bytes] = (
            blob_store if blob_store is not None else {}
        )

    @property
    def blob_store(self) -> Mapping[str, bytes]:
        return dict(self._blobs)

    def _publish_locator(
        self,
        path: str,
        chunks: Mapping[int, bytes],
        size_bytes: int,
        content_cid: str,
    ) -> str:
        # Publish chunk digests only — never a concatenated whole object.
        total_chunks = (
            (size_bytes + self._chunk_bytes - 1) // self._chunk_bytes if size_bytes else 0
        )
        for index in range(total_chunks):
            chunk_start = index * self._chunk_bytes
            live = min(self._chunk_bytes, size_bytes - chunk_start)
            existing = chunks.get(index, b"")[:live]
            if len(existing) < live:
                existing = existing + b"\x00" * (live - len(existing))
            blob_hash = "blake3-sim:" + hashlib.sha256(
                b"iroh-chunk:" + index.to_bytes(8, "big") + existing
            ).hexdigest()
            self._blobs[blob_hash] = existing
        self._blobs[content_cid] = content_cid.encode("utf-8")
        return content_cid


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_ranged_storage(
    kind: StorageBackendKind | str,
    *,
    root: str | os.PathLike[str] | None = None,
    backend_id: str | None = None,
    chunk_bytes: int = DEFAULT_CHUNK_BYTES,
    available: bool = True,
    immutable: bool = False,
    read_only: bool = False,
    clock: Any | None = None,
) -> RangedVFSStorageBoundary:
    """Construct a ranged storage adapter by backend kind."""

    if not isinstance(kind, StorageBackendKind):
        kind = StorageBackendKind(str(kind))
    common = {
        "chunk_bytes": chunk_bytes,
        "available": available,
        "immutable": immutable,
        "read_only": read_only,
        "clock": clock,
    }
    if kind is StorageBackendKind.MEMORY:
        return MemoryRangedStorage(
            backend_id=backend_id or "backend:memory",
            **common,
        )
    if kind is StorageBackendKind.LOCAL:
        if root is None:
            raise RangedStorageError(
                "local ranged storage requires a root directory",
                code=StorageErrorCode.INTERNAL,
            )
        return LocalRangedStorage(
            root,
            backend_id=backend_id or "backend:local",
            **common,
        )
    if kind is StorageBackendKind.IPFS:
        return IPFSRangedStorage(
            backend_id=backend_id or "backend:ipfs",
            **common,
        )
    if kind is StorageBackendKind.IROH:
        return IrohRangedStorage(
            backend_id=backend_id or "backend:iroh",
            **common,
        )
    raise RangedStorageError(
        f"unknown storage backend kind: {kind!r}",
        code=StorageErrorCode.UNSUPPORTED,
    )


def adapter_exposes_confined_surface(storage: RangedVFSStorageBoundary) -> bool:
    """Return True when an adapter declares the full KVFS-200 surface."""

    required = {
        StorageCapability.STAT,
        StorageCapability.LIST,
        StorageCapability.RANGE_READ,
        StorageCapability.STAGED_WRITE,
        StorageCapability.DELETE,
        StorageCapability.RENAME,
    }
    return required <= set(storage.capabilities)


__all__ = [
    "STORAGE_CONTRACT_VERSION",
    "STORAGE_SCHEMA_VERSION",
    "RANGED_VFS_STORAGE_SCHEMA",
    "RangedVFSStorage_V1",
    "DEFAULT_CHUNK_BYTES",
    "WHOLE_OBJECT_THRESHOLD_BYTES",
    "MAX_RANGE_BYTES",
    "StorageBackendKind",
    "StorageCapability",
    "StorageOp",
    "StorageErrorCode",
    "RangedStorageError",
    "StorageStat",
    "StorageDirEntry",
    "StorageListing",
    "RangeReadResult",
    "StorageEffect",
    "StageHandle",
    "RangedVFSStorageBoundary",
    "MemoryRangedStorage",
    "LocalRangedStorage",
    "IPFSRangedStorage",
    "IrohRangedStorage",
    "create_ranged_storage",
    "adapter_exposes_confined_surface",
]
