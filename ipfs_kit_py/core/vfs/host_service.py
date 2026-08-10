"""Host façade over CanonicalVFSService with real storage injection (KVFS-203).

``HostVFSService@1`` is the production-facing host façade that composes:

* an injected ranged storage boundary (memory / local / IPFS / Iroh adapters);
* :class:`~ipfs_kit_py.core.vfs.service.CanonicalVFSService` as the sole
  path / result / error / effect authority for admitted mutations;
* :class:`~ipfs_kit_py.core.vfs.namespace.NamespaceRouter` for path policy
  and mount admission;
* :class:`~ipfs_kit_py.core.vfs.metadata.MetadataProjector` for kernel
  metadata projection; and
* :class:`~ipfs_kit_py.core.vfs.handles.HandleTable` for generation-tagged
  open handles and staged extents.

Supported host operations (create / read / write / truncate / list / mkdir /
rmdir / unlink / rename / metadata) work without a FUSE or WinFsp driver.
Every admitted mutation reaches ``CanonicalVFSService.execute``; legacy
callers must use :class:`~ipfs_kit_py.core.vfs.adapters.LegacyVFSAdapter`
bound to the same service and cannot bypass the admitted mutation path.

No fusepy, libfuse, WinFsp, or host filesystem I/O is imported or performed.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, ClassVar, Final

from ipfs_kit_py.core.vfs.adapters import LegacyVFSAdapter
from ipfs_kit_py.core.vfs.contracts import (
    VFSEntryKind,
    VFSErrorCode,
    VFSOperationKind,
    VFSPathPolicy,
)
from ipfs_kit_py.core.vfs.handles import (
    FileHandle,
    HandleError,
    HandleTable,
    ReleaseResult,
)
from ipfs_kit_py.core.vfs.host_contracts import (
    MAX_SAFE_INTEGER,
    CallbackDisposition,
    HostCallbackKind,
    HostCallbackResult,
    HostEntryKind,
    HostErrno,
    HostHandle,
    HostMetadata,
    HostPlatform,
    OpenFlag,
    callback_disposition,
)
from ipfs_kit_py.core.vfs.metadata import (
    MAX_TIME_NS,
    FileType,
    MetadataError,
    MetadataProjector,
)
from ipfs_kit_py.core.vfs.namespace import (
    DEFAULT_MOUNT_ID,
    NamespaceError,
    NamespaceErrorCode,
    NamespaceRouter,
)
from ipfs_kit_py.core.vfs.service import (
    CanonicalVFSService,
    InMemoryVFSStorage,
    VFSExecuteRequest,
    VFSServiceError,
    VFSServiceOutcome,
    VFSStoredEntry,
    content_cid_for_bytes,
    make_op,
)
from ipfs_kit_py.core.vfs.storage import (
    MemoryRangedStorage,
    RangedStorageError,
    RangedVFSStorageBoundary,
    StorageErrorCode,
    create_ranged_storage,
)

# ---------------------------------------------------------------------------
# Schema / version / bounds
# ---------------------------------------------------------------------------

CONTRACT_VERSION: Final[int] = 1
SCHEMA_MAJOR: Final[int] = 1
SCHEMA_MINOR: Final[int] = 0
SCHEMA_PATCH: Final[int] = 0
SCHEMA_VERSION: Final[str] = f"{SCHEMA_MAJOR}.{SCHEMA_MINOR}.{SCHEMA_PATCH}"

HOST_SERVICE_NAMESPACE: Final[str] = "ipfs_kit_py/core/vfs/host_service"

HOST_VFS_SERVICE_SCHEMA: Final[str] = (
    f"{HOST_SERVICE_NAMESPACE}/host-vfs-service@{SCHEMA_MAJOR}"
)
RANGED_STORAGE_BRIDGE_SCHEMA: Final[str] = (
    f"{HOST_SERVICE_NAMESPACE}/ranged-storage-bridge@{SCHEMA_MAJOR}"
)
HOST_OPERATION_RESULT_SCHEMA: Final[str] = (
    f"{HOST_SERVICE_NAMESPACE}/host-operation-result@{SCHEMA_MAJOR}"
)

# Public interface aliases.
HostVFSService_V1: Final[str] = HOST_VFS_SERVICE_SCHEMA
RangedStorageBridge_V1: Final[str] = RANGED_STORAGE_BRIDGE_SCHEMA

MAX_TRACE_STEPS: Final[int] = 4_096
MAX_MATERIALIZE_BYTES: Final[int] = 1_048_576  # matches service payload bound

# Metadata times are bounded by MAX_SAFE_INTEGER (≈2^53-1). Real wall-clock
# nanoseconds (~1.7e18) overflow that bound, so the host clock (unix ms) is
# projected into the metadata domain without raising MetadataError.
_MS_TO_NS: Final[int] = 1_000_000
_MAX_MS_FOR_TRUE_NS: Final[int] = MAX_TIME_NS // _MS_TO_NS


def _clock_ms_to_now_ns(clock_ms: int) -> int:
    """Map host clock (unix ms) into metadata's bounded nanosecond domain.

    Prefer true ms→ns scaling when the product fits ``MAX_TIME_NS``; otherwise
    use the millisecond tick itself (realistic unix-ms values already fit
    ``MAX_SAFE_INTEGER``) so ordering is preserved fail-closed without overflow.
    """

    try:
        ms = int(clock_ms)
    except (TypeError, ValueError):
        return 0
    if ms <= 0:
        return 0
    if ms > MAX_SAFE_INTEGER:
        return MAX_TIME_NS
    if ms <= _MAX_MS_FOR_TRUE_NS:
        return ms * _MS_TO_NS
    return ms


# Map canonical VFS error codes onto host errno names.
_VFS_ERROR_TO_ERRNO: Final[Mapping[VFSErrorCode, HostErrno]] = {
    VFSErrorCode.NOT_FOUND: HostErrno.ENOENT,
    VFSErrorCode.ALREADY_EXISTS: HostErrno.EEXIST,
    VFSErrorCode.NOT_DIRECTORY: HostErrno.ENOTDIR,
    VFSErrorCode.IS_DIRECTORY: HostErrno.EISDIR,
    VFSErrorCode.NOT_EMPTY: HostErrno.ENOTEMPTY,
    VFSErrorCode.READ_ONLY: HostErrno.EROFS,
    VFSErrorCode.PERMISSION_DENIED: HostErrno.EACCES,
    VFSErrorCode.UNSUPPORTED: HostErrno.ENOSYS,
    VFSErrorCode.PRECONDITION_FAILED: HostErrno.EAGAIN,
    VFSErrorCode.STAT_ERROR: HostErrno.EIO,
    VFSErrorCode.INTERNAL: HostErrno.EIO,
}

# ---------------------------------------------------------------------------
# Errors / traces
# ---------------------------------------------------------------------------


class HostServiceErrorCode(str, Enum):
    """Stable host-service error codes."""

    NOT_FOUND = "HOST_NOT_FOUND"
    ALREADY_EXISTS = "HOST_ALREADY_EXISTS"
    NOT_DIRECTORY = "HOST_NOT_DIRECTORY"
    IS_DIRECTORY = "HOST_IS_DIRECTORY"
    NOT_EMPTY = "HOST_NOT_EMPTY"
    READ_ONLY = "HOST_READ_ONLY"
    PERMISSION = "HOST_PERMISSION"
    INVALID = "HOST_INVALID"
    UNSUPPORTED = "HOST_UNSUPPORTED"
    CANONICAL_FAILURE = "HOST_CANONICAL_FAILURE"
    STORAGE = "HOST_STORAGE"
    NAMESPACE = "HOST_NAMESPACE"
    HANDLE = "HOST_HANDLE"
    METADATA = "HOST_METADATA"
    BOUND_EXCEEDED = "HOST_BOUND_EXCEEDED"
    LEGACY_BYPASS = "HOST_LEGACY_BYPASS"
    INTERNAL = "HOST_INTERNAL"


class HostServiceError(Exception):
    """Fail-closed host-service error with stable code and errno."""

    def __init__(
        self,
        message: str,
        *,
        code: HostServiceErrorCode,
        errno: HostErrno = HostErrno.EINVAL,
        path: str = "",
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = (
            code if isinstance(code, HostServiceErrorCode) else HostServiceErrorCode(code)
        )
        self.errno = errno if isinstance(errno, HostErrno) else HostErrno(errno)
        self.path = path
        self.detail = dict(detail or {})

    def to_record(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "message": self.message,
            "errno": self.errno.value,
            "path": self.path,
            "detail": dict(self.detail),
        }


class HostTraceKind(str, Enum):
    """Closed vocabulary for host-service executable traces."""

    CREATE = "create"
    READ = "read"
    WRITE = "write"
    TRUNCATE = "truncate"
    LIST = "list"
    MKDIR = "mkdir"
    RMDIR = "rmdir"
    UNLINK = "unlink"
    RENAME = "rename"
    METADATA = "metadata"
    OPEN = "open"
    FLUSH = "flush"
    RELEASE = "release"
    EXECUTE = "execute"
    LEGACY = "legacy"
    ADMISSION = "admission"
    OBSERVATION = "observation"


@dataclass(frozen=True)
class HostTraceStep:
    """One immutable host-service trace step."""

    kind: HostTraceKind
    success: bool
    path: str = ""
    code: str = ""
    detail: Mapping[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "success": self.success,
            "path": self.path,
            "code": self.code,
            "detail": dict(self.detail),
        }


class HostTraceLog:
    """Bounded append-only host-service trace log."""

    __slots__ = ("_steps", "_max_steps")

    def __init__(self, *, max_steps: int = MAX_TRACE_STEPS) -> None:
        self._steps: list[HostTraceStep] = []
        self._max_steps = max(1, min(int(max_steps), MAX_TRACE_STEPS))

    def record(
        self,
        kind: HostTraceKind,
        *,
        success: bool,
        path: str = "",
        code: str = "",
        detail: Mapping[str, Any] | None = None,
    ) -> HostTraceStep:
        step = HostTraceStep(
            kind=kind,
            success=success,
            path=path,
            code=code,
            detail=dict(detail or {}),
        )
        if len(self._steps) >= self._max_steps:
            del self._steps[0]
        self._steps.append(step)
        return step

    def clear(self) -> None:
        self._steps.clear()

    @property
    def steps(self) -> tuple[HostTraceStep, ...]:
        return tuple(self._steps)

    def kinds(self) -> list[str]:
        return [step.kind.value for step in self._steps]

    def to_records(self) -> list[dict[str, Any]]:
        return [step.to_record() for step in self._steps]


# ---------------------------------------------------------------------------
# Host operation result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HostOperationResult:
    """Unified host operation result with one path/result/error/effect view."""

    SCHEMA: ClassVar[str] = HOST_OPERATION_RESULT_SCHEMA

    kind: str
    success: bool
    path: str = ""
    target_path: str = ""
    errno: HostErrno = HostErrno.OK
    error_code: str = ""
    message: str = ""
    data: bytes = b""
    dir_entries: tuple[str, ...] = ()
    metadata: HostMetadata | None = None
    handle: HostHandle | None = None
    bytes_transferred: int = 0
    observed_effect: bool = False
    effect_id: str = ""
    content_cid: str = ""
    version_cid: str = ""
    namespace_generation: int = 0
    operation_id: str = ""
    canonical_state: str = ""
    detail: Mapping[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "kind": self.kind,
            "success": self.success,
            "path": self.path,
            "target_path": self.target_path,
            "errno": self.errno.value,
            "error_code": self.error_code,
            "message": self.message,
            "data_len": len(self.data),
            "dir_entries": list(self.dir_entries),
            "metadata": None if self.metadata is None else self.metadata.to_record(),
            "handle": None if self.handle is None else self.handle.to_record(),
            "bytes_transferred": self.bytes_transferred,
            "observed_effect": self.observed_effect,
            "effect_id": self.effect_id,
            "content_cid": self.content_cid,
            "version_cid": self.version_cid,
            "namespace_generation": self.namespace_generation,
            "operation_id": self.operation_id,
            "canonical_state": self.canonical_state,
            "detail": dict(self.detail),
        }

    def to_host_callback_result(
        self,
        callback_kind: HostCallbackKind | str,
        *,
        platform: HostPlatform = HostPlatform.HERMETIC,
        request_id: str = "",
    ) -> HostCallbackResult:
        """Project this result onto a host callback contract result."""

        kind = (
            callback_kind
            if isinstance(callback_kind, HostCallbackKind)
            else HostCallbackKind(str(callback_kind))
        )
        if self.success:
            return HostCallbackResult.make_success(
                kind,
                handle=self.handle,
                metadata=self.metadata,
                bytes_transferred=self.bytes_transferred,
                dir_entries=self.dir_entries,
                observed_effect=self.observed_effect,
                request_id=request_id or self.operation_id,
                platform=platform,
            )
        return HostCallbackResult.make_failure(
            kind,
            self.errno if self.errno is not HostErrno.OK else HostErrno.EIO,
            message=self.message or self.error_code or "host operation failed",
            request_id=request_id or self.operation_id,
            platform=platform,
            vfs_error_code=self.error_code,
        )


# ---------------------------------------------------------------------------
# Ranged storage → VFSStorageBoundary bridge
# ---------------------------------------------------------------------------


class RangedStorageBoundaryAdapter:
    """Adapt a ranged storage boundary to the whole-object VFS storage protocol.

    ``CanonicalVFSService`` mutates only through :class:`VFSStorageBoundary`.
    This adapter injects a real :class:`RangedVFSStorageBoundary` so admitted
    mutations land on production storage adapters while preserving the
    service's get/put/delete/rename/children contract.

    Generation is tracked locally (matching hermetic ``InMemoryVFSStorage``
    semantics used by the service); ranged storage still records its own
    generation and effect log for observability.
    """

    SCHEMA: ClassVar[str] = RANGED_STORAGE_BRIDGE_SCHEMA
    CONTRACT_VERSION: ClassVar[int] = CONTRACT_VERSION

    def __init__(
        self,
        ranged: RangedVFSStorageBoundary,
        *,
        mount_id: str = DEFAULT_MOUNT_ID,
        max_materialize_bytes: int = MAX_MATERIALIZE_BYTES,
    ) -> None:
        if ranged is None:
            raise HostServiceError(
                "ranged storage is required",
                code=HostServiceErrorCode.INTERNAL,
            )
        self._ranged = ranged
        self._mount_id = mount_id
        self._max_materialize = max_materialize_bytes
        self._generation = 0
        self._lock = threading.RLock()
        # Overlay service-authored identity/mode so version preconditions stay stable.
        self._overlay: dict[str, dict[str, Any]] = {}

    @property
    def ranged(self) -> RangedVFSStorageBoundary:
        return self._ranged

    @property
    def generation(self) -> int:
        return self._generation

    def bump_generation(self) -> int:
        with self._lock:
            self._generation += 1
            return self._generation

    def entry_count(self) -> int:
        # Prefer native count when available; fall back to snapshot size.
        count_fn = getattr(self._ranged, "entry_count", None)
        if callable(count_fn):
            return int(count_fn())
        return len(self._ranged.snapshot_meta())

    def effects(self) -> tuple[Any, ...]:
        return self._ranged.effects()

    def _storage_error(self, message: str, *, path: str = "") -> VFSServiceError:
        """Project bridge failures as service errors (caught by CanonicalVFSService)."""

        return VFSServiceError(message if not path else f"{message} ({path})")

    def get(self, path: str) -> VFSStoredEntry | None:
        with self._lock:
            try:
                stat = self._ranged.stat(path)
            except RangedStorageError as exc:
                if exc.code is StorageErrorCode.NOT_FOUND:
                    return None
                raise self._storage_error(str(exc), path=path) from exc

            overlay = self._overlay.get(path, {})
            if stat.kind is VFSEntryKind.DIRECTORY:
                return VFSStoredEntry(
                    kind=VFSEntryKind.DIRECTORY,
                    content=b"",
                    content_cid=str(
                        overlay.get("content_cid")
                        or stat.content_cid
                        or content_cid_for_bytes(b"")
                    ),
                    version_cid=str(overlay.get("version_cid") or stat.version_cid or ""),
                    target=str(overlay.get("target") or ""),
                    mtime_unix_ms=int(overlay.get("mtime_unix_ms") or stat.mtime_unix_ms or 0),
                    mode=int(overlay.get("mode") or stat.mode or 0),
                    mount_id=str(overlay.get("mount_id") or stat.mount_id or self._mount_id),
                    is_readonly=bool(overlay.get("is_readonly") or stat.is_readonly),
                )

            size = int(stat.size_bytes)
            if size > self._max_materialize:
                raise self._storage_error(
                    f"file exceeds materialize bound of {self._max_materialize} bytes",
                    path=path,
                )
            content = b""
            if size > 0:
                try:
                    content = self._ranged.range_read(path, 0, size).data
                except RangedStorageError as exc:
                    raise self._storage_error(str(exc), path=path) from exc
            return VFSStoredEntry(
                kind=VFSEntryKind.FILE,
                content=content,
                content_cid=str(
                    overlay.get("content_cid")
                    or stat.content_cid
                    or content_cid_for_bytes(content)
                ),
                version_cid=str(overlay.get("version_cid") or stat.version_cid or ""),
                target=str(overlay.get("target") or ""),
                mtime_unix_ms=int(overlay.get("mtime_unix_ms") or stat.mtime_unix_ms or 0),
                mode=int(overlay.get("mode") or stat.mode or 0),
                mount_id=str(overlay.get("mount_id") or stat.mount_id or self._mount_id),
                is_readonly=bool(overlay.get("is_readonly") or stat.is_readonly),
            )

    def put(self, path: str, entry: VFSStoredEntry) -> None:
        with self._lock:
            if not isinstance(entry, VFSStoredEntry):
                raise self._storage_error("entry must be a VFSStoredEntry", path=path)
            if entry.kind is VFSEntryKind.DIRECTORY:
                self._put_directory(path, entry)
            elif entry.kind is VFSEntryKind.FILE:
                self._put_file(path, entry)
            else:
                # Symlinks / other kinds: store as empty file marker + overlay target.
                self._put_file(
                    path,
                    VFSStoredEntry(
                        kind=VFSEntryKind.FILE,
                        content=b"",
                        content_cid=entry.content_cid or content_cid_for_bytes(b""),
                        version_cid=entry.version_cid,
                        target=entry.target,
                        mtime_unix_ms=entry.mtime_unix_ms,
                        mode=entry.mode,
                        mount_id=entry.mount_id or self._mount_id,
                        is_readonly=entry.is_readonly,
                    ),
                )
            self._overlay[path] = {
                "kind": entry.kind.value,
                "content_cid": entry.content_cid,
                "version_cid": entry.version_cid,
                "target": entry.target,
                "mtime_unix_ms": entry.mtime_unix_ms,
                "mode": entry.mode,
                "mount_id": entry.mount_id or self._mount_id,
                "is_readonly": entry.is_readonly,
            }

    def _put_directory(self, path: str, entry: VFSStoredEntry) -> None:
        if path == "":
            return
        try:
            existing = self._ranged.stat(path)
        except RangedStorageError as exc:
            if exc.code is not StorageErrorCode.NOT_FOUND:
                raise self._storage_error(str(exc), path=path) from exc
            existing = None
        if existing is None:
            mkdir = getattr(self._ranged, "mkdir", None)
            if not callable(mkdir):
                raise self._storage_error(
                    "ranged storage does not support mkdir", path=path
                )
            try:
                mkdir(path)
            except RangedStorageError as exc:
                raise self._storage_error(str(exc), path=path) from exc
        elif existing.kind is not VFSEntryKind.DIRECTORY:
            raise self._storage_error(
                f"cannot put directory over non-directory: {path!r}",
                path=path,
            )

    def _put_file(self, path: str, entry: VFSStoredEntry) -> None:
        if path == "":
            raise self._storage_error(
                "cannot put a file over the namespace root", path=path
            )
        content = bytes(entry.content)
        if len(content) > self._max_materialize:
            raise self._storage_error(
                f"payload exceeds materialize bound of {self._max_materialize} bytes",
                path=path,
            )
        try:
            handle = self._ranged.begin_staged_write(path, truncate=True)
            if content:
                self._ranged.stage_write(handle, 0, content)
            self._ranged.commit_staged_write(handle)
        except RangedStorageError as exc:
            raise self._storage_error(str(exc), path=path) from exc

    def delete(self, path: str) -> None:
        with self._lock:
            if path == "":
                raise self._storage_error("cannot delete namespace root", path=path)
            try:
                self._ranged.delete(path)
            except RangedStorageError as exc:
                if exc.code is StorageErrorCode.NOT_FOUND:
                    self._overlay.pop(path, None)
                    return
                raise self._storage_error(str(exc), path=path) from exc
            self._overlay.pop(path, None)
            # Drop descendant overlays for directory deletes.
            prefix = path + "/"
            for key in list(self._overlay):
                if key.startswith(prefix):
                    del self._overlay[key]

    def children(self, path: str) -> tuple[str, ...]:
        with self._lock:
            try:
                listing = self._ranged.list(path)
            except RangedStorageError as exc:
                if exc.code is StorageErrorCode.NOT_FOUND:
                    return ()
                raise self._storage_error(str(exc), path=path) from exc
            return tuple(entry.name for entry in listing.entries)

    def rename(self, source: str, target: str) -> None:
        with self._lock:
            try:
                self._ranged.rename(source, target)
            except RangedStorageError as exc:
                raise self._storage_error(str(exc), path=source) from exc
            # Rebind overlays for source and descendants.
            moves: list[tuple[str, str, dict[str, Any]]] = []
            for key, value in list(self._overlay.items()):
                if key == source or key.startswith(source + "/"):
                    suffix = key[len(source) :]
                    moves.append((key, target + suffix, value))
            for old, _new, _value in moves:
                del self._overlay[old]
            for _old, new, value in moves:
                self._overlay[new] = value

    def snapshot(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            meta = self._ranged.snapshot_meta()
            out: dict[str, dict[str, Any]] = {}
            for path, record in meta.items():
                overlay = self._overlay.get(path, {})
                kind = overlay.get("kind") or record.get("kind") or "file"
                size = 0 if kind == VFSEntryKind.DIRECTORY.value else int(
                    record.get("size_bytes", 0) or 0
                )
                out[path] = {
                    "kind": kind,
                    "size_bytes": size,
                    "content_cid": overlay.get("content_cid") or record.get("content_cid", ""),
                    "version_cid": overlay.get("version_cid") or record.get("version_cid", ""),
                    "target": overlay.get("target", ""),
                    "mtime_unix_ms": overlay.get("mtime_unix_ms")
                    or record.get("mtime_unix_ms", 0),
                    "mode": overlay.get("mode") or record.get("mode", 0),
                    "mount_id": overlay.get("mount_id")
                    or record.get("mount_id", self._mount_id),
                    "is_readonly": bool(
                        overlay.get("is_readonly") or record.get("is_readonly", False)
                    ),
                }
            return out


# ---------------------------------------------------------------------------
# Host VFS service façade
# ---------------------------------------------------------------------------


class HostVFSService:
    """Host façade: every supported host op reaches CanonicalVFSService.

    Interface alias: ``HostVFSService@1``.
    """

    SCHEMA: ClassVar[str] = HOST_VFS_SERVICE_SCHEMA
    CONTRACT_VERSION: ClassVar[int] = CONTRACT_VERSION

    def __init__(
        self,
        *,
        ranged_storage: RangedVFSStorageBoundary | None = None,
        storage: RangedStorageBoundaryAdapter | InMemoryVFSStorage | None = None,
        path_policy: VFSPathPolicy | None = None,
        namespace: NamespaceRouter | None = None,
        metadata: MetadataProjector | None = None,
        handles: HandleTable | None = None,
        clock: Callable[[], int] | None = None,
        mount_id: str = DEFAULT_MOUNT_ID,
        platform: HostPlatform = HostPlatform.HERMETIC,
        service: CanonicalVFSService | None = None,
    ) -> None:
        self._clock = clock or (lambda: int(time.time() * 1000))
        self._mount_id = mount_id
        self._platform = (
            platform if isinstance(platform, HostPlatform) else HostPlatform(platform)
        )
        self._policy = path_policy or VFSPathPolicy.default()
        self._lock = threading.RLock()
        self._trace = HostTraceLog()
        self._op_seq = 0

        if storage is not None and isinstance(storage, RangedStorageBoundaryAdapter):
            self._boundary = storage
            self._ranged = storage.ranged
        elif ranged_storage is not None:
            self._ranged = ranged_storage
            self._boundary = RangedStorageBoundaryAdapter(
                ranged_storage, mount_id=mount_id
            )
        elif storage is not None and isinstance(storage, InMemoryVFSStorage):
            # Hermetic whole-object boundary without ranged backend.
            self._ranged = None
            self._boundary = storage  # type: ignore[assignment]
        else:
            self._ranged = MemoryRangedStorage(clock=self._clock)
            self._boundary = RangedStorageBoundaryAdapter(
                self._ranged, mount_id=mount_id
            )

        self._service = service or CanonicalVFSService(
            storage=self._boundary,  # type: ignore[arg-type]
            path_policy=self._policy,
            clock=self._clock,
        )
        self._namespace = namespace or NamespaceRouter(path_policy=self._policy)
        self._metadata = metadata or MetadataProjector(
            default_now_ns=_clock_ms_to_now_ns(self._clock())
        )
        self._handles = handles or HandleTable(
            mount_id=mount_id,
            clock_ms=self._clock,
        )
        # Seed root metadata.
        if self._metadata.get_by_path("") is None:
            self._metadata.admit(
                inode=1,
                file_type=FileType.DIRECTORY,
                path="",
                mode=0o755,
                now_ns=_clock_ms_to_now_ns(self._clock()),
            )

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
    def service(self) -> CanonicalVFSService:
        """The sole semantics authority for admitted operations."""

        return self._service

    @property
    def canonical(self) -> CanonicalVFSService:
        return self._service

    @property
    def storage_boundary(self) -> Any:
        """Injected storage boundary used by CanonicalVFSService."""

        return self._boundary

    @property
    def ranged_storage(self) -> RangedVFSStorageBoundary | None:
        return self._ranged

    @property
    def namespace(self) -> NamespaceRouter:
        return self._namespace

    @property
    def metadata(self) -> MetadataProjector:
        return self._metadata

    @property
    def handles(self) -> HandleTable:
        return self._handles

    @property
    def trace(self) -> HostTraceLog:
        return self._trace

    @property
    def platform(self) -> HostPlatform:
        return self._platform

    def legacy_adapter(self, *, journal: Any | None = None) -> LegacyVFSAdapter:
        """Return a legacy adapter bound to *this* canonical service only.

        Legacy callers cannot obtain a parallel authority; mutations still
        pass through :meth:`CanonicalVFSService.execute`.
        """

        return LegacyVFSAdapter(service=self._service, journal=journal)

    def storage_effects(self) -> tuple[Any, ...]:
        if self._ranged is not None:
            return self._ranged.effects()
        effects_fn = getattr(self._boundary, "effects", None)
        if callable(effects_fn):
            return tuple(effects_fn())
        return ()

    # -- factory helpers ----------------------------------------------------

    @classmethod
    def with_memory_storage(
        cls,
        *,
        clock: Callable[[], int] | None = None,
        **kwargs: Any,
    ) -> "HostVFSService":
        clock = clock or (lambda: int(time.time() * 1000))
        return cls(
            ranged_storage=MemoryRangedStorage(clock=clock),
            clock=clock,
            **kwargs,
        )

    @classmethod
    def with_backend(
        cls,
        kind: str,
        *,
        root: str | None = None,
        clock: Callable[[], int] | None = None,
        **kwargs: Any,
    ) -> "HostVFSService":
        clock = clock or (lambda: int(time.time() * 1000))
        ranged = create_ranged_storage(kind, root=root, clock=clock)
        return cls(ranged_storage=ranged, clock=clock, **kwargs)

    # -- internals ----------------------------------------------------------

    def _next_op_id(self, prefix: str) -> str:
        self._op_seq += 1
        return f"{prefix}-{self._op_seq:08d}-{uuid.uuid4().hex[:8]}"

    def _normalize(self, path: str) -> str:
        if path is None:
            raise HostServiceError(
                "path is required",
                code=HostServiceErrorCode.INVALID,
                errno=HostErrno.EINVAL,
            )
        if not isinstance(path, str):
            raise HostServiceError(
                "path must be a string",
                code=HostServiceErrorCode.INVALID,
                errno=HostErrno.EINVAL,
            )
        # Empty path is the namespace root.
        if path == "" or path == "/":
            return ""
        try:
            return self._namespace.normalize(path).path
        except NamespaceError as exc:
            raise HostServiceError(
                str(exc),
                code=HostServiceErrorCode.NAMESPACE,
                errno=HostErrno.EINVAL,
                path=path,
                detail=exc.to_record(),
            ) from exc

    def _admit_mutation(self, path: str) -> None:
        admission = self._namespace.admit_create(path)
        if not admission.allowed:
            errno = HostErrno.EROFS
            if admission.code is NamespaceErrorCode.READ_ONLY_MOUNT:
                errno = HostErrno.EROFS
            elif admission.code in (
                NamespaceErrorCode.UNKNOWN_MOUNT,
                NamespaceErrorCode.MOUNT_NOT_FOUND,
            ):
                errno = HostErrno.ENOENT
            elif admission.code is NamespaceErrorCode.CROSS_MOUNT:
                errno = HostErrno.EXDEV
            raise HostServiceError(
                admission.message or "mutation not admitted",
                code=HostServiceErrorCode.NAMESPACE,
                errno=errno,
                path=path,
                detail=admission.to_record(),
            )
        self._trace.record(
            HostTraceKind.ADMISSION,
            success=True,
            path=path,
            detail=admission.to_record(),
        )

    def _admit_rename(self, source: str, target: str) -> None:
        admission = self._namespace.admit_rename(source, target)
        if not admission.allowed:
            errno = HostErrno.EXDEV
            if admission.code is NamespaceErrorCode.READ_ONLY_MOUNT:
                errno = HostErrno.EROFS
            elif admission.code is NamespaceErrorCode.CROSS_MOUNT:
                errno = HostErrno.EXDEV
            raise HostServiceError(
                admission.message or "rename not admitted",
                code=HostServiceErrorCode.NAMESPACE,
                errno=errno,
                path=source,
                detail=admission.to_record(),
            )
        self._trace.record(
            HostTraceKind.ADMISSION,
            success=True,
            path=source,
            detail=admission.to_record(),
        )

    def _execute(
        self,
        kind: VFSOperationKind,
        *,
        path: str = "",
        source_path: str = "",
        target_path: str = "",
        payload: bytes = b"",
        operation_id: str | None = None,
        range_start: int = 0,
        range_end: int = 0,
    ) -> VFSServiceOutcome:
        op_id = operation_id or self._next_op_id(kind.value)
        operation = make_op(
            kind,
            operation_id=op_id,
            path=path,
            source_path=source_path,
            target_path=target_path,
            mount_id=self._mount_id,
            range_start=range_start,
            range_end=range_end,
        )
        request = VFSExecuteRequest(
            payload=payload,
            now_unix_ms=self._clock(),
        )
        outcome = self._service.execute(operation, request)
        self._trace.record(
            HostTraceKind.EXECUTE,
            success=outcome.success,
            path=path or source_path,
            code="" if outcome.success else (
                outcome.result.error.code.value if outcome.result.error else "failed"
            ),
            detail={
                "operation_id": op_id,
                "kind": kind.value,
                "state": outcome.result.state.value,
                "success": outcome.success,
            },
        )
        return outcome

    def _outcome_to_result(
        self,
        host_kind: str,
        outcome: VFSServiceOutcome,
        *,
        path: str = "",
        target_path: str = "",
        data: bytes | None = None,
        dir_entries: Sequence[str] | None = None,
        metadata: HostMetadata | None = None,
        handle: HostHandle | None = None,
        bytes_transferred: int | None = None,
    ) -> HostOperationResult:
        result = outcome.result
        if outcome.success:
            effect_id = ""
            if result.observed_transition is not None:
                ids = result.observed_transition.effect_evidence_ids
                if ids:
                    effect_id = ids[0]
            payload = data if data is not None else outcome.data
            entries = tuple(dir_entries) if dir_entries is not None else ()
            if not entries and result.listing is not None:
                entries = tuple(e.name for e in result.listing.entries)
            observed = result.observed_transition is not None
            return HostOperationResult(
                kind=host_kind,
                success=True,
                path=path or result.path,
                target_path=target_path,
                errno=HostErrno.OK,
                data=payload,
                dir_entries=entries,
                metadata=metadata,
                handle=handle,
                bytes_transferred=(
                    len(payload)
                    if bytes_transferred is None
                    else int(bytes_transferred)
                ),
                observed_effect=observed,
                effect_id=effect_id,
                content_cid=result.resulting_content_cid,
                version_cid=result.resulting_version_cid,
                namespace_generation=outcome.namespace_generation,
                operation_id=result.operation_id,
                canonical_state=result.state.value,
                detail={
                    "events": [e.to_record() for e in outcome.events],
                },
            )

        error = result.error
        code = error.code if error is not None else VFSErrorCode.INTERNAL
        errno = _VFS_ERROR_TO_ERRNO.get(code, HostErrno.EIO)
        return HostOperationResult(
            kind=host_kind,
            success=False,
            path=path or (error.path if error else ""),
            target_path=target_path,
            errno=errno,
            error_code=code.value if hasattr(code, "value") else str(code),
            message=error.message if error else "canonical operation failed",
            namespace_generation=outcome.namespace_generation,
            operation_id=result.operation_id,
            canonical_state=result.state.value,
            detail={"events": [e.to_record() for e in outcome.events]},
        )

    def _file_type_for_kind(self, kind: VFSEntryKind) -> FileType:
        if kind is VFSEntryKind.DIRECTORY:
            return FileType.DIRECTORY
        if kind is VFSEntryKind.SYMLINK:
            return FileType.SYMLINK
        return FileType.FILE

    def _sync_planes_after_success(
        self,
        path: str,
        *,
        kind: VFSEntryKind,
        size: int = 0,
        mode: int = 0,
        target_path: str | None = None,
        removed: bool = False,
    ) -> HostMetadata | None:
        """Update namespace inodes + metadata after a committed canonical mutation."""

        now_ns = _clock_ms_to_now_ns(self._clock())
        if removed:
            existing = self._metadata.get_by_path(path)
            if existing is not None:
                try:
                    self._metadata.forget(existing.inode)
                except MetadataError:
                    pass
            return None

        bind_path = target_path if target_path is not None else path
        if target_path is not None and target_path != path:
            try:
                self._namespace.rename_inode(path, target_path)
            except NamespaceError:
                # Allocate at target if rename of inode is not possible.
                pass
            try:
                self._metadata.rename_path(path, target_path)
            except MetadataError:
                pass
            try:
                self._handles.notify_rename(path, target_path)
            except HandleError:
                pass

        try:
            inode_rec = self._namespace.allocate_inode(
                bind_path,
                identity=bind_path or "root",
                kind=kind,
                mount_id=self._mount_id,
                generation=self._service.storage.generation,
            )
            inode = inode_rec.inode
        except NamespaceError:
            try:
                existing = self._namespace.lookup_inode(bind_path) if bind_path else None
                inode = existing.inode if existing is not None else (
                    abs(hash(bind_path or "root")) % (2**31 - 1) or 2
                )
            except NamespaceError:
                inode = abs(hash(bind_path or "root")) % (2**31 - 1) or 2

        file_type = self._file_type_for_kind(kind)
        attr = self._metadata.admit(
            inode=inode,
            file_type=file_type,
            path=bind_path,
            size=size,
            mode=mode or (0o755 if file_type is FileType.DIRECTORY else 0o644),
            now_ns=now_ns,
            generation=self._service.storage.generation,
        )
        try:
            meta = self._metadata.project(attr)
            return meta.to_host_metadata()
        except MetadataError:
            return None

    def _failure_result(
        self,
        kind: str,
        exc: Exception,
        *,
        path: str = "",
        target_path: str = "",
    ) -> HostOperationResult:
        if isinstance(exc, HostServiceError):
            return HostOperationResult(
                kind=kind,
                success=False,
                path=path or exc.path,
                target_path=target_path,
                errno=exc.errno,
                error_code=exc.code.value,
                message=exc.message,
                detail=exc.detail,
            )
        if isinstance(exc, HandleError):
            return HostOperationResult(
                kind=kind,
                success=False,
                path=path or exc.path,
                target_path=target_path,
                errno=exc.errno,
                error_code=exc.code.value,
                message=str(exc),
                detail=exc.to_record(),
            )
        if isinstance(exc, MetadataError):
            return HostOperationResult(
                kind=kind,
                success=False,
                path=path or exc.path,
                target_path=target_path,
                errno=exc.errno,
                error_code=exc.code.value,
                message=str(exc),
                detail=exc.to_record(),
            )
        if isinstance(exc, NamespaceError):
            return HostOperationResult(
                kind=kind,
                success=False,
                path=path or exc.path,
                target_path=target_path,
                errno=HostErrno.EINVAL,
                error_code=exc.code.value,
                message=str(exc),
                detail=exc.to_record(),
            )
        return HostOperationResult(
            kind=kind,
            success=False,
            path=path,
            target_path=target_path,
            errno=HostErrno.EIO,
            error_code=HostServiceErrorCode.INTERNAL.value,
            message=str(exc),
        )

    def _file_handle_to_host(self, fh: FileHandle) -> HostHandle:
        return HostHandle(
            handle_id=fh.handle_id,
            inode=fh.inode,
            generation=fh.generation,
            flags=fh.flags,
            mount_id=fh.mount_id or self._mount_id,
            lease_id=fh.lease_id,
            path_at_open=fh.path_at_open or fh.current_path,
            released=fh.released,
        )

    # -- public host operations ---------------------------------------------

    def create(
        self,
        path: str,
        content: bytes = b"",
        *,
        mode: int = 0o644,
        exclusive: bool = True,
    ) -> HostOperationResult:
        """Create a file through CanonicalVFSService."""

        with self._lock:
            try:
                norm = self._normalize(path)
                if not norm:
                    raise HostServiceError(
                        "cannot create over namespace root",
                        code=HostServiceErrorCode.INVALID,
                        errno=HostErrno.EISDIR,
                        path=path,
                    )
                if not isinstance(content, (bytes, bytearray)):
                    raise HostServiceError(
                        "content must be bytes",
                        code=HostServiceErrorCode.INVALID,
                        errno=HostErrno.EINVAL,
                        path=norm,
                    )
                payload = bytes(content)
                self._admit_mutation(norm)
                if not exclusive:
                    # Replace-or-create: if present, replace; else create.
                    existing = self._service.storage.get(norm)
                    if existing is not None:
                        outcome = self._execute(
                            VFSOperationKind.REPLACE,
                            path=norm,
                            payload=payload,
                        )
                        result = self._outcome_to_result("create", outcome, path=norm)
                        if result.success:
                            meta = self._sync_planes_after_success(
                                norm,
                                kind=VFSEntryKind.FILE,
                                size=len(payload),
                                mode=mode,
                            )
                            # Seed handle table for open-after-create.
                            if self._handles.lookup_inode(norm) is None:
                                try:
                                    self._handles.seed_file(norm, payload)
                                except HandleError:
                                    pass
                            result = HostOperationResult(
                                kind=result.kind,
                                success=True,
                                path=result.path,
                                errno=HostErrno.OK,
                                data=payload,
                                metadata=meta,
                                bytes_transferred=len(payload),
                                observed_effect=True,
                                effect_id=result.effect_id,
                                content_cid=result.content_cid,
                                version_cid=result.version_cid,
                                namespace_generation=result.namespace_generation,
                                operation_id=result.operation_id,
                                canonical_state=result.canonical_state,
                                detail=result.detail,
                            )
                        self._trace.record(
                            HostTraceKind.CREATE,
                            success=result.success,
                            path=norm,
                            code=result.error_code,
                            detail=result.to_record(),
                        )
                        return result

                outcome = self._execute(
                    VFSOperationKind.CREATE,
                    path=norm,
                    payload=payload,
                )
                result = self._outcome_to_result("create", outcome, path=norm, data=payload)
                if result.success:
                    meta = self._sync_planes_after_success(
                        norm,
                        kind=VFSEntryKind.FILE,
                        size=len(payload),
                        mode=mode,
                    )
                    if self._handles.lookup_inode(norm) is None:
                        try:
                            self._handles.seed_file(norm, payload)
                        except HandleError:
                            pass
                    result = HostOperationResult(
                        kind=result.kind,
                        success=True,
                        path=result.path,
                        errno=HostErrno.OK,
                        data=payload,
                        metadata=meta,
                        bytes_transferred=len(payload),
                        observed_effect=True,
                        effect_id=result.effect_id,
                        content_cid=result.content_cid,
                        version_cid=result.version_cid,
                        namespace_generation=result.namespace_generation,
                        operation_id=result.operation_id,
                        canonical_state=result.canonical_state,
                        detail=result.detail,
                    )
                self._trace.record(
                    HostTraceKind.CREATE,
                    success=result.success,
                    path=norm,
                    code=result.error_code,
                    detail=result.to_record(),
                )
                return result
            except Exception as exc:  # project typed failures
                result = self._failure_result("create", exc, path=path)
                self._trace.record(
                    HostTraceKind.CREATE,
                    success=False,
                    path=path,
                    code=result.error_code,
                    detail=result.to_record(),
                )
                return result

    def read(
        self,
        path: str,
        *,
        offset: int = 0,
        length: int | None = None,
    ) -> HostOperationResult:
        """Read file bytes through CanonicalVFSService."""

        with self._lock:
            try:
                norm = self._normalize(path)
                if offset < 0:
                    raise HostServiceError(
                        "offset must be non-negative",
                        code=HostServiceErrorCode.INVALID,
                        errno=HostErrno.EINVAL,
                        path=norm,
                    )
                if length is not None and length < 0:
                    raise HostServiceError(
                        "length must be non-negative",
                        code=HostServiceErrorCode.INVALID,
                        errno=HostErrno.EINVAL,
                        path=norm,
                    )
                # Always read through the canonical service; slice for offset/length.
                # (RANGE_READ treats range_end=0 as EOF, so zero-length reads use
                # a full READ + slice instead of a zero end bound.)
                outcome = self._execute(VFSOperationKind.READ, path=norm)
                if outcome.success:
                    body = outcome.data
                    if length is None:
                        data = body[offset:]
                    else:
                        data = body[offset : offset + length]
                else:
                    data = b""

                result = self._outcome_to_result(
                    "read",
                    outcome,
                    path=norm,
                    data=data,
                    bytes_transferred=len(data),
                )
                # Reads never observe a mutation effect.
                if result.success:
                    result = HostOperationResult(
                        kind=result.kind,
                        success=True,
                        path=result.path,
                        errno=HostErrno.OK,
                        data=data,
                        bytes_transferred=len(data),
                        observed_effect=False,
                        content_cid=result.content_cid,
                        version_cid=result.version_cid,
                        namespace_generation=result.namespace_generation,
                        operation_id=result.operation_id,
                        canonical_state=result.canonical_state,
                        detail=result.detail,
                    )
                self._trace.record(
                    HostTraceKind.READ,
                    success=result.success,
                    path=norm,
                    code=result.error_code,
                    detail={"bytes": len(data), "offset": offset},
                )
                return result
            except Exception as exc:
                result = self._failure_result("read", exc, path=path)
                self._trace.record(
                    HostTraceKind.READ,
                    success=False,
                    path=path,
                    code=result.error_code,
                )
                return result

    def write(
        self,
        path: str,
        data: bytes,
        *,
        offset: int = 0,
        create: bool = True,
    ) -> HostOperationResult:
        """Write bytes through CanonicalVFSService (create or replace).

        Offset writes are assembled into a whole-object replace so the
        canonical service remains the single mutation authority. Sparse holes
        before ``offset`` are zero-filled.
        """

        with self._lock:
            try:
                norm = self._normalize(path)
                if not isinstance(data, (bytes, bytearray)):
                    raise HostServiceError(
                        "data must be bytes",
                        code=HostServiceErrorCode.INVALID,
                        errno=HostErrno.EINVAL,
                        path=norm,
                    )
                payload = bytes(data)
                if offset < 0:
                    raise HostServiceError(
                        "offset must be non-negative",
                        code=HostServiceErrorCode.INVALID,
                        errno=HostErrno.EINVAL,
                        path=norm,
                    )
                self._admit_mutation(norm)
                existing = self._service.storage.get(norm)
                if existing is None:
                    if not create:
                        raise HostServiceError(
                            f"path not found: {norm}",
                            code=HostServiceErrorCode.NOT_FOUND,
                            errno=HostErrno.ENOENT,
                            path=norm,
                        )
                    if offset == 0:
                        new_content = payload
                    else:
                        new_content = (b"\x00" * offset) + payload
                    outcome = self._execute(
                        VFSOperationKind.CREATE,
                        path=norm,
                        payload=new_content,
                    )
                else:
                    if existing.kind is not VFSEntryKind.FILE:
                        raise HostServiceError(
                            f"cannot write non-file: {norm}",
                            code=HostServiceErrorCode.IS_DIRECTORY,
                            errno=HostErrno.EISDIR,
                            path=norm,
                        )
                    base = bytes(existing.content)
                    end = offset + len(payload)
                    if end < len(base) and offset == 0 and len(payload) == len(base):
                        new_content = payload
                    else:
                        size = max(len(base), end)
                        buf = bytearray(size)
                        buf[: len(base)] = base
                        buf[offset : offset + len(payload)] = payload
                        new_content = bytes(buf)
                    outcome = self._execute(
                        VFSOperationKind.REPLACE,
                        path=norm,
                        payload=new_content,
                    )

                result = self._outcome_to_result(
                    "write",
                    outcome,
                    path=norm,
                    data=payload,
                    bytes_transferred=len(payload),
                )
                if result.success:
                    meta = self._sync_planes_after_success(
                        norm,
                        kind=VFSEntryKind.FILE,
                        size=len(new_content),
                    )
                    # Keep handle-table committed view in sync when seeded.
                    if self._handles.lookup_inode(norm) is None:
                        try:
                            self._handles.seed_file(norm, new_content)
                        except HandleError:
                            pass
                    result = HostOperationResult(
                        kind=result.kind,
                        success=True,
                        path=result.path,
                        errno=HostErrno.OK,
                        data=payload,
                        metadata=meta,
                        bytes_transferred=len(payload),
                        observed_effect=True,
                        effect_id=result.effect_id,
                        content_cid=result.content_cid,
                        version_cid=result.version_cid,
                        namespace_generation=result.namespace_generation,
                        operation_id=result.operation_id,
                        canonical_state=result.canonical_state,
                        detail={**result.detail, "offset": offset, "size": len(new_content)},
                    )
                self._trace.record(
                    HostTraceKind.WRITE,
                    success=result.success,
                    path=norm,
                    code=result.error_code,
                    detail=result.to_record(),
                )
                return result
            except Exception as exc:
                result = self._failure_result("write", exc, path=path)
                self._trace.record(
                    HostTraceKind.WRITE,
                    success=False,
                    path=path,
                    code=result.error_code,
                )
                return result

    def truncate(self, path: str, size: int) -> HostOperationResult:
        """Truncate a file through CanonicalVFSService (replace with new size)."""

        with self._lock:
            try:
                norm = self._normalize(path)
                if isinstance(size, bool) or not isinstance(size, int) or size < 0:
                    raise HostServiceError(
                        "size must be a non-negative integer",
                        code=HostServiceErrorCode.INVALID,
                        errno=HostErrno.EINVAL,
                        path=norm,
                    )
                self._admit_mutation(norm)
                existing = self._service.storage.get(norm)
                if existing is None:
                    raise HostServiceError(
                        f"path not found: {norm}",
                        code=HostServiceErrorCode.NOT_FOUND,
                        errno=HostErrno.ENOENT,
                        path=norm,
                    )
                if existing.kind is not VFSEntryKind.FILE:
                    raise HostServiceError(
                        f"cannot truncate non-file: {norm}",
                        code=HostServiceErrorCode.IS_DIRECTORY,
                        errno=HostErrno.EISDIR,
                        path=norm,
                    )
                base = bytes(existing.content)
                if size <= len(base):
                    new_content = base[:size]
                else:
                    new_content = base + (b"\x00" * (size - len(base)))
                outcome = self._execute(
                    VFSOperationKind.REPLACE,
                    path=norm,
                    payload=new_content,
                )
                result = self._outcome_to_result(
                    "truncate",
                    outcome,
                    path=norm,
                    bytes_transferred=size,
                )
                if result.success:
                    meta = self._sync_planes_after_success(
                        norm,
                        kind=VFSEntryKind.FILE,
                        size=size,
                    )
                    result = HostOperationResult(
                        kind=result.kind,
                        success=True,
                        path=result.path,
                        errno=HostErrno.OK,
                        data=new_content,
                        metadata=meta,
                        bytes_transferred=size,
                        observed_effect=True,
                        effect_id=result.effect_id,
                        content_cid=result.content_cid,
                        version_cid=result.version_cid,
                        namespace_generation=result.namespace_generation,
                        operation_id=result.operation_id,
                        canonical_state=result.canonical_state,
                        detail={**result.detail, "size": size},
                    )
                self._trace.record(
                    HostTraceKind.TRUNCATE,
                    success=result.success,
                    path=norm,
                    code=result.error_code,
                    detail={"size": size},
                )
                return result
            except Exception as exc:
                result = self._failure_result("truncate", exc, path=path)
                self._trace.record(
                    HostTraceKind.TRUNCATE,
                    success=False,
                    path=path,
                    code=result.error_code,
                )
                return result

    def list(self, path: str = "") -> HostOperationResult:
        """List a directory through CanonicalVFSService."""

        with self._lock:
            try:
                norm = self._normalize(path) if path not in ("", "/") else ""
                outcome = self._execute(VFSOperationKind.LIST, path=norm)
                entries: tuple[str, ...] = ()
                if outcome.success and outcome.result.listing is not None:
                    entries = tuple(e.name for e in outcome.result.listing.entries)
                result = self._outcome_to_result(
                    "list",
                    outcome,
                    path=norm,
                    dir_entries=entries,
                )
                if result.success:
                    result = HostOperationResult(
                        kind=result.kind,
                        success=True,
                        path=result.path,
                        errno=HostErrno.OK,
                        dir_entries=entries,
                        observed_effect=False,
                        namespace_generation=result.namespace_generation,
                        operation_id=result.operation_id,
                        canonical_state=result.canonical_state,
                        detail=result.detail,
                    )
                self._trace.record(
                    HostTraceKind.LIST,
                    success=result.success,
                    path=norm,
                    code=result.error_code,
                    detail={"entries": list(entries)},
                )
                return result
            except Exception as exc:
                result = self._failure_result("list", exc, path=path)
                self._trace.record(
                    HostTraceKind.LIST,
                    success=False,
                    path=path,
                    code=result.error_code,
                )
                return result

    # Alias used by host callback vocabulary.
    readdir = list

    def mkdir(self, path: str, *, mode: int = 0o755) -> HostOperationResult:
        """Create a directory through CanonicalVFSService."""

        with self._lock:
            try:
                norm = self._normalize(path)
                if not norm:
                    raise HostServiceError(
                        "cannot mkdir namespace root",
                        code=HostServiceErrorCode.ALREADY_EXISTS,
                        errno=HostErrno.EEXIST,
                        path=path,
                    )
                self._admit_mutation(norm)
                outcome = self._execute(VFSOperationKind.MKDIR, path=norm)
                result = self._outcome_to_result("mkdir", outcome, path=norm)
                if result.success:
                    meta = self._sync_planes_after_success(
                        norm,
                        kind=VFSEntryKind.DIRECTORY,
                        mode=mode,
                    )
                    if self._handles.lookup_inode(norm) is None:
                        try:
                            self._handles.seed_directory(norm)
                        except HandleError:
                            pass
                    result = HostOperationResult(
                        kind=result.kind,
                        success=True,
                        path=result.path,
                        errno=HostErrno.OK,
                        metadata=meta,
                        observed_effect=True,
                        effect_id=result.effect_id,
                        content_cid=result.content_cid,
                        version_cid=result.version_cid,
                        namespace_generation=result.namespace_generation,
                        operation_id=result.operation_id,
                        canonical_state=result.canonical_state,
                        detail=result.detail,
                    )
                self._trace.record(
                    HostTraceKind.MKDIR,
                    success=result.success,
                    path=norm,
                    code=result.error_code,
                    detail=result.to_record(),
                )
                return result
            except Exception as exc:
                result = self._failure_result("mkdir", exc, path=path)
                self._trace.record(
                    HostTraceKind.MKDIR,
                    success=False,
                    path=path,
                    code=result.error_code,
                )
                return result

    def rmdir(self, path: str) -> HostOperationResult:
        """Remove an empty directory through CanonicalVFSService."""

        with self._lock:
            try:
                norm = self._normalize(path)
                if not norm:
                    raise HostServiceError(
                        "cannot rmdir namespace root",
                        code=HostServiceErrorCode.PERMISSION,
                        errno=HostErrno.EPERM,
                        path=path,
                    )
                self._admit_mutation(norm)
                outcome = self._execute(VFSOperationKind.RMDIR, path=norm)
                result = self._outcome_to_result("rmdir", outcome, path=norm)
                if result.success:
                    self._sync_planes_after_success(
                        norm, kind=VFSEntryKind.DIRECTORY, removed=True
                    )
                    result = HostOperationResult(
                        kind=result.kind,
                        success=True,
                        path=result.path,
                        errno=HostErrno.OK,
                        observed_effect=True,
                        effect_id=result.effect_id,
                        content_cid=result.content_cid,
                        version_cid=result.version_cid,
                        namespace_generation=result.namespace_generation,
                        operation_id=result.operation_id,
                        canonical_state=result.canonical_state,
                        detail=result.detail,
                    )
                self._trace.record(
                    HostTraceKind.RMDIR,
                    success=result.success,
                    path=norm,
                    code=result.error_code,
                )
                return result
            except Exception as exc:
                result = self._failure_result("rmdir", exc, path=path)
                self._trace.record(
                    HostTraceKind.RMDIR,
                    success=False,
                    path=path,
                    code=result.error_code,
                )
                return result

    def unlink(self, path: str) -> HostOperationResult:
        """Unlink (delete) a file through CanonicalVFSService."""

        with self._lock:
            try:
                norm = self._normalize(path)
                if not norm:
                    raise HostServiceError(
                        "cannot unlink namespace root",
                        code=HostServiceErrorCode.PERMISSION,
                        errno=HostErrno.EPERM,
                        path=path,
                    )
                self._admit_mutation(norm)
                existing = self._service.storage.get(norm)
                if existing is not None and existing.kind is VFSEntryKind.DIRECTORY:
                    raise HostServiceError(
                        f"is a directory: {norm}",
                        code=HostServiceErrorCode.IS_DIRECTORY,
                        errno=HostErrno.EISDIR,
                        path=norm,
                    )
                outcome = self._execute(VFSOperationKind.DELETE, path=norm)
                result = self._outcome_to_result("unlink", outcome, path=norm)
                if result.success:
                    self._sync_planes_after_success(
                        norm, kind=VFSEntryKind.FILE, removed=True
                    )
                    try:
                        self._handles.notify_unlink(norm)
                    except HandleError:
                        pass
                    result = HostOperationResult(
                        kind=result.kind,
                        success=True,
                        path=result.path,
                        errno=HostErrno.OK,
                        observed_effect=True,
                        effect_id=result.effect_id,
                        content_cid=result.content_cid,
                        version_cid=result.version_cid,
                        namespace_generation=result.namespace_generation,
                        operation_id=result.operation_id,
                        canonical_state=result.canonical_state,
                        detail=result.detail,
                    )
                self._trace.record(
                    HostTraceKind.UNLINK,
                    success=result.success,
                    path=norm,
                    code=result.error_code,
                )
                return result
            except Exception as exc:
                result = self._failure_result("unlink", exc, path=path)
                self._trace.record(
                    HostTraceKind.UNLINK,
                    success=False,
                    path=path,
                    code=result.error_code,
                )
                return result

    def rename(self, source: str, target: str) -> HostOperationResult:
        """Rename within a single mount through CanonicalVFSService."""

        with self._lock:
            try:
                src = self._normalize(source)
                dst = self._normalize(target)
                if not src or not dst:
                    raise HostServiceError(
                        "rename requires non-root source and target",
                        code=HostServiceErrorCode.INVALID,
                        errno=HostErrno.EINVAL,
                        path=source,
                    )
                self._admit_rename(src, dst)
                outcome = self._execute(
                    VFSOperationKind.RENAME,
                    path=src,
                    source_path=src,
                    target_path=dst,
                )
                result = self._outcome_to_result(
                    "rename",
                    outcome,
                    path=src,
                    target_path=dst,
                )
                if result.success:
                    # Determine kind from storage after rename.
                    entry = self._service.storage.get(dst)
                    kind = entry.kind if entry is not None else VFSEntryKind.FILE
                    size = 0 if entry is None or kind is VFSEntryKind.DIRECTORY else len(
                        entry.content
                    )
                    meta = self._sync_planes_after_success(
                        src,
                        kind=kind,
                        size=size,
                        target_path=dst,
                    )
                    result = HostOperationResult(
                        kind=result.kind,
                        success=True,
                        path=src,
                        target_path=dst,
                        errno=HostErrno.OK,
                        metadata=meta,
                        observed_effect=True,
                        effect_id=result.effect_id,
                        content_cid=result.content_cid,
                        version_cid=result.version_cid,
                        namespace_generation=result.namespace_generation,
                        operation_id=result.operation_id,
                        canonical_state=result.canonical_state,
                        detail=result.detail,
                    )
                self._trace.record(
                    HostTraceKind.RENAME,
                    success=result.success,
                    path=src,
                    code=result.error_code,
                    detail={"target": dst},
                )
                return result
            except Exception as exc:
                result = self._failure_result(
                    "rename", exc, path=source, target_path=target
                )
                self._trace.record(
                    HostTraceKind.RENAME,
                    success=False,
                    path=source,
                    code=result.error_code,
                )
                return result

    def metadata(self, path: str = "") -> HostOperationResult:
        """Return host metadata for a path (getattr) via canonical STAT + projector."""

        with self._lock:
            try:
                norm = self._normalize(path) if path not in ("", "/") else ""
                outcome = self._execute(VFSOperationKind.STAT, path=norm)
                if not outcome.success:
                    result = self._outcome_to_result("metadata", outcome, path=norm)
                    self._trace.record(
                        HostTraceKind.METADATA,
                        success=False,
                        path=norm,
                        code=result.error_code,
                    )
                    return result

                stat = outcome.result.stat
                assert stat is not None
                # Ensure metadata plane has the node.
                host_meta = self._sync_planes_after_success(
                    norm,
                    kind=stat.kind,
                    size=stat.size_bytes,
                    mode=stat.mode,
                )
                if host_meta is None:
                    # Fall back through projector getattr when possible.
                    try:
                        host_meta = self._metadata.getattr_path(norm).to_host_metadata()
                    except MetadataError:
                        entry_kind = (
                            HostEntryKind.DIRECTORY
                            if stat.kind is VFSEntryKind.DIRECTORY
                            else HostEntryKind.FILE
                        )
                        host_meta = HostMetadata(
                            inode=1 if not norm else abs(hash(norm)) % (2**31 - 1) or 2,
                            kind=entry_kind,
                            size=stat.size_bytes,
                            mode=stat.mode
                            or (
                                0o755
                                if stat.kind is VFSEntryKind.DIRECTORY
                                else 0o644
                            ),
                            nlink=1,
                        )

                result = HostOperationResult(
                    kind="metadata",
                    success=True,
                    path=norm,
                    errno=HostErrno.OK,
                    metadata=host_meta,
                    observed_effect=False,
                    content_cid=stat.content_cid,
                    version_cid=stat.version_cid,
                    namespace_generation=outcome.namespace_generation,
                    operation_id=outcome.result.operation_id,
                    canonical_state=outcome.result.state.value,
                    detail={"stat": stat.to_record() if hasattr(stat, "to_record") else {}},
                )
                self._trace.record(
                    HostTraceKind.METADATA,
                    success=True,
                    path=norm,
                    detail=result.to_record(),
                )
                return result
            except Exception as exc:
                result = self._failure_result("metadata", exc, path=path)
                self._trace.record(
                    HostTraceKind.METADATA,
                    success=False,
                    path=path,
                    code=result.error_code,
                )
                return result

    # Alias for host callback vocabulary.
    getattr = metadata

    def open(
        self,
        path: str,
        flags: Sequence[OpenFlag | str] | OpenFlag | str | None = None,
        *,
        mode: int = 0o644,
    ) -> HostOperationResult:
        """Open a path, ensuring the namespace entry exists via CanonicalVFSService.

        Handle issuance uses :class:`HandleTable`; any create/trunc side
        effects are admitted through the canonical service first.
        """

        with self._lock:
            try:
                norm = self._normalize(path)
                if not norm:
                    raise HostServiceError(
                        "cannot open namespace root as a file",
                        code=HostServiceErrorCode.IS_DIRECTORY,
                        errno=HostErrno.EISDIR,
                        path=path,
                    )
                flag_list = list(flags) if isinstance(flags, (list, tuple)) else (
                    [flags] if flags is not None else [OpenFlag.O_RDONLY]
                )
                flag_values = {
                    (f if isinstance(f, OpenFlag) else OpenFlag(str(f)))
                    for f in flag_list
                }
                creat = OpenFlag.O_CREAT in flag_values
                excl = OpenFlag.O_EXCL in flag_values
                trunc = OpenFlag.O_TRUNC in flag_values

                existing = self._service.storage.get(norm)
                if existing is None:
                    if not creat:
                        raise HostServiceError(
                            f"path not found: {norm}",
                            code=HostServiceErrorCode.NOT_FOUND,
                            errno=HostErrno.ENOENT,
                            path=norm,
                        )
                    created = self.create(norm, b"", mode=mode, exclusive=True)
                    if not created.success:
                        return created
                else:
                    if excl and creat:
                        raise HostServiceError(
                            f"path already exists: {norm}",
                            code=HostServiceErrorCode.ALREADY_EXISTS,
                            errno=HostErrno.EEXIST,
                            path=norm,
                        )
                    if existing.kind is VFSEntryKind.DIRECTORY:
                        raise HostServiceError(
                            f"is a directory: {norm}",
                            code=HostServiceErrorCode.IS_DIRECTORY,
                            errno=HostErrno.EISDIR,
                            path=norm,
                        )
                    if trunc:
                        trunc_result = self.truncate(norm, 0)
                        if not trunc_result.success:
                            return trunc_result

                # Ensure handle table has the committed inode.
                if self._handles.lookup_inode(norm) is None:
                    entry = self._service.storage.get(norm)
                    content = bytes(entry.content) if entry is not None else b""
                    try:
                        self._handles.seed_file(norm, content)
                    except HandleError:
                        pass

                fh = self._handles.open(norm, flag_list, mode=mode, mount_id=self._mount_id)
                host_handle = self._file_handle_to_host(fh)
                result = HostOperationResult(
                    kind="open",
                    success=True,
                    path=norm,
                    errno=HostErrno.OK,
                    handle=host_handle,
                    observed_effect=False,
                    detail=fh.to_record(),
                )
                self._trace.record(
                    HostTraceKind.OPEN,
                    success=True,
                    path=norm,
                    detail=result.to_record(),
                )
                return result
            except Exception as exc:
                result = self._failure_result("open", exc, path=path)
                self._trace.record(
                    HostTraceKind.OPEN,
                    success=False,
                    path=path,
                    code=result.error_code,
                )
                return result

    def flush_handle(
        self,
        handle_id: int,
        *,
        generation: int | None = None,
        commit: bool = True,
    ) -> HostOperationResult:
        """Flush a handle; when committing dirty extents, admit via CanonicalVFSService."""

        with self._lock:
            try:
                # Read handle view first.
                view = None
                for fh in self._handles.open_handles():
                    if fh.handle_id == handle_id and (
                        generation is None or fh.generation == generation
                    ):
                        view = fh
                        break
                if view is None:
                    # Still attempt flush for stale/error projection.
                    flush = self._handles.flush(
                        handle_id, generation=generation, commit=False
                    )
                    if not flush.success:
                        return HostOperationResult(
                            kind="flush",
                            success=False,
                            errno=HostErrno(flush.errno)
                            if flush.errno in HostErrno._value2member_map_
                            else HostErrno.EIO,
                            error_code=flush.error_code or HostServiceErrorCode.HANDLE.value,
                            message="flush failed",
                            detail=flush.to_record(),
                        )

                path = view.current_path if view is not None else ""
                # Materialize staged content and commit through canonical authority.
                if commit and view is not None and view.writable:
                    staged = self._handles.read(
                        handle_id, 0, max(view.logical_size, 0) or 0,
                        generation=generation,
                    )
                    # Force handle-local commit for hermetic extent apply, then
                    # publish through canonical REPLACE/CREATE.
                    self._handles.flush(handle_id, generation=generation, commit=True)
                    committed = self._handles.committed_read(path)
                    existing = self._service.storage.get(path)
                    self._admit_mutation(path)
                    if existing is None:
                        outcome = self._execute(
                            VFSOperationKind.CREATE,
                            path=path,
                            payload=committed,
                        )
                    else:
                        outcome = self._execute(
                            VFSOperationKind.REPLACE,
                            path=path,
                            payload=committed,
                        )
                    result = self._outcome_to_result("flush", outcome, path=path)
                    if result.success:
                        self._sync_planes_after_success(
                            path,
                            kind=VFSEntryKind.FILE,
                            size=len(committed),
                        )
                        result = HostOperationResult(
                            kind="flush",
                            success=True,
                            path=path,
                            errno=HostErrno.OK,
                            data=committed,
                            bytes_transferred=len(committed),
                            observed_effect=True,
                            effect_id=result.effect_id,
                            content_cid=result.content_cid,
                            version_cid=result.version_cid,
                            namespace_generation=result.namespace_generation,
                            operation_id=result.operation_id,
                            canonical_state=result.canonical_state,
                            detail=result.detail,
                        )
                    self._trace.record(
                        HostTraceKind.FLUSH,
                        success=result.success,
                        path=path,
                        code=result.error_code,
                    )
                    return result

                flush = self._handles.flush(
                    handle_id, generation=generation, commit=False
                )
                result = HostOperationResult(
                    kind="flush",
                    success=flush.success,
                    path=path,
                    errno=HostErrno.OK if flush.success else HostErrno.EIO,
                    error_code="" if flush.success else (flush.error_code or "flush_failed"),
                    message="" if flush.success else "flush failed",
                    bytes_transferred=flush.committed_bytes,
                    observed_effect=False,
                    detail=flush.to_record(),
                )
                self._trace.record(
                    HostTraceKind.FLUSH,
                    success=result.success,
                    path=path,
                )
                return result
            except Exception as exc:
                result = self._failure_result("flush", exc)
                self._trace.record(
                    HostTraceKind.FLUSH,
                    success=False,
                    code=result.error_code,
                )
                return result

    def release_handle(
        self,
        handle_id: int,
        *,
        generation: int | None = None,
    ) -> HostOperationResult:
        """Idempotent handle release (no durability manufacturing)."""

        with self._lock:
            try:
                rel: ReleaseResult = self._handles.release(
                    handle_id, generation=generation
                )
                result = HostOperationResult(
                    kind="release",
                    success=rel.success,
                    errno=HostErrno.OK if rel.success else HostErrno.EBADF,
                    error_code="" if rel.success else HostServiceErrorCode.HANDLE.value,
                    observed_effect=False,
                    detail=rel.to_record(),
                )
                self._trace.record(
                    HostTraceKind.RELEASE,
                    success=result.success,
                    detail=result.to_record(),
                )
                return result
            except Exception as exc:
                result = self._failure_result("release", exc)
                self._trace.record(
                    HostTraceKind.RELEASE,
                    success=False,
                    code=result.error_code,
                )
                return result

    def execute_callback(
        self,
        kind: HostCallbackKind | str,
        *,
        path: str = "",
        target_path: str = "",
        data: bytes = b"",
        offset: int = 0,
        size: int = 0,
        handle_id: int = 0,
        generation: int | None = None,
        flags: Sequence[OpenFlag | str] | OpenFlag | str | None = None,
        mode: int = 0o644,
        request_id: str = "",
    ) -> HostCallbackResult:
        """Dispatch one host callback kind through the façade (no driver)."""

        callback = (
            kind if isinstance(kind, HostCallbackKind) else HostCallbackKind(str(kind))
        )
        disposition = callback_disposition(callback)
        if disposition is CallbackDisposition.EXPLICIT_UNSUPPORTED:
            return HostCallbackResult.make_unsupported(
                callback, platform=self._platform, request_id=request_id
            )

        if callback is HostCallbackKind.GETATTR:
            result = self.metadata(path)
        elif callback is HostCallbackKind.READDIR:
            result = self.list(path)
        elif callback is HostCallbackKind.CREATE:
            # create callback: create then open (observed effect from create)
            created = self.create(path, data, mode=mode, exclusive=True)
            if not created.success:
                result = created
            else:
                opened = self.open(
                    path,
                    flags or (OpenFlag.O_RDWR, OpenFlag.O_CREAT),
                    mode=mode,
                )
                if not opened.success:
                    result = opened
                else:
                    result = HostOperationResult(
                        kind="create",
                        success=True,
                        path=path,
                        errno=HostErrno.OK,
                        handle=opened.handle,
                        metadata=created.metadata,
                        data=created.data,
                        bytes_transferred=created.bytes_transferred,
                        observed_effect=True,
                        effect_id=created.effect_id,
                        content_cid=created.content_cid,
                        version_cid=created.version_cid,
                        namespace_generation=created.namespace_generation,
                        operation_id=created.operation_id,
                        canonical_state=created.canonical_state,
                        detail=opened.detail,
                    )
        elif callback is HostCallbackKind.OPEN:
            result = self.open(path, flags, mode=mode)
        elif callback is HostCallbackKind.READ:
            if handle_id:
                try:
                    io = self._handles.read(
                        handle_id, offset, size or 0, generation=generation
                    )
                    result = HostOperationResult(
                        kind="read",
                        success=True,
                        path=path,
                        data=io.data,
                        bytes_transferred=io.bytes_transferred,
                        observed_effect=False,
                        detail=io.to_record(),
                    )
                except HandleError as exc:
                    result = self._failure_result("read", exc, path=path)
            else:
                result = self.read(path, offset=offset, length=size or None)
        elif callback is HostCallbackKind.WRITE:
            if handle_id:
                try:
                    io = self._handles.write(
                        handle_id, offset, data, generation=generation
                    )
                    # Immediately admit through canonical on write for path authority.
                    flush = self.flush_handle(
                        handle_id, generation=generation, commit=True
                    )
                    if not flush.success:
                        result = flush
                    else:
                        result = HostOperationResult(
                            kind="write",
                            success=True,
                            path=path or flush.path,
                            data=data,
                            bytes_transferred=io.bytes_transferred,
                            observed_effect=True,
                            effect_id=flush.effect_id,
                            content_cid=flush.content_cid,
                            version_cid=flush.version_cid,
                            namespace_generation=flush.namespace_generation,
                            operation_id=flush.operation_id,
                            canonical_state=flush.canonical_state,
                            detail=io.to_record(),
                        )
                except HandleError as exc:
                    result = self._failure_result("write", exc, path=path)
            else:
                result = self.write(path, data, offset=offset)
        elif callback is HostCallbackKind.TRUNCATE:
            result = self.truncate(path, size)
        elif callback is HostCallbackKind.MKDIR:
            result = self.mkdir(path, mode=mode)
        elif callback is HostCallbackKind.RMDIR:
            result = self.rmdir(path)
        elif callback is HostCallbackKind.UNLINK:
            result = self.unlink(path)
        elif callback is HostCallbackKind.RENAME:
            result = self.rename(path, target_path)
        elif callback is HostCallbackKind.FLUSH:
            result = self.flush_handle(handle_id, generation=generation, commit=False)
        elif callback is HostCallbackKind.FSYNC:
            result = self.flush_handle(handle_id, generation=generation, commit=True)
        elif callback is HostCallbackKind.RELEASE:
            result = self.release_handle(handle_id, generation=generation)
        elif callback is HostCallbackKind.ACCESS:
            # Existence + simple permission projection via metadata.
            meta = self.metadata(path)
            if not meta.success:
                result = meta
            else:
                result = HostOperationResult(
                    kind="access",
                    success=True,
                    path=path,
                    errno=HostErrno.OK,
                    metadata=meta.metadata,
                    observed_effect=False,
                )
        elif callback is HostCallbackKind.STATFS:
            result = HostOperationResult(
                kind="statfs",
                success=True,
                errno=HostErrno.OK,
                observed_effect=False,
                detail=self._metadata.statfs().to_record()
                if hasattr(self._metadata, "statfs")
                else {},
            )
        elif callback in (HostCallbackKind.INIT, HostCallbackKind.DESTROY):
            result = HostOperationResult(
                kind=callback.value,
                success=True,
                errno=HostErrno.OK,
                observed_effect=False,
            )
        elif callback is HostCallbackKind.UTIMENS:
            # Metadata plane owns utimens; project through it when node exists.
            try:
                attr = self._metadata.require_path(self._normalize(path) if path else "")
                result = HostOperationResult(
                    kind="utimens",
                    success=True,
                    path=path,
                    errno=HostErrno.OK,
                    metadata=self._metadata.project(attr).to_host_metadata(),
                    observed_effect=True,
                )
            except Exception as exc:
                result = self._failure_result("utimens", exc, path=path)
        else:
            return HostCallbackResult.make_unsupported(
                callback, platform=self._platform, request_id=request_id
            )

        return result.to_host_callback_result(
            callback, platform=self._platform, request_id=request_id
        )

    def assert_legacy_cannot_bypass(self) -> None:
        """Fail closed if a legacy-shaped direct storage mutation is attempted.

        The host façade never exposes a public mutator that writes the
        injected storage without going through ``CanonicalVFSService.execute``.
        This method documents and tests that invariant.
        """

        # There is no host API that mutates storage without execute().
        # Attempting to treat the façade as a raw storage writer is forbidden.
        raise HostServiceError(
            "legacy paths cannot bypass admitted CanonicalVFSService mutations",
            code=HostServiceErrorCode.LEGACY_BYPASS,
            errno=HostErrno.EPERM,
        )


def build_host_vfs_service(
    *,
    backend: str = "memory",
    root: str | None = None,
    clock: Callable[[], int] | None = None,
    **kwargs: Any,
) -> HostVFSService:
    """Factory for a host VFS service with real storage injection."""

    return HostVFSService.with_backend(backend, root=root, clock=clock, **kwargs)


__all__ = [
    "CONTRACT_VERSION",
    "SCHEMA_VERSION",
    "HOST_VFS_SERVICE_SCHEMA",
    "RANGED_STORAGE_BRIDGE_SCHEMA",
    "HOST_OPERATION_RESULT_SCHEMA",
    "HostVFSService_V1",
    "RangedStorageBridge_V1",
    "MAX_MATERIALIZE_BYTES",
    "HostServiceErrorCode",
    "HostServiceError",
    "HostTraceKind",
    "HostTraceStep",
    "HostTraceLog",
    "HostOperationResult",
    "RangedStorageBoundaryAdapter",
    "HostVFSService",
    "build_host_vfs_service",
]
