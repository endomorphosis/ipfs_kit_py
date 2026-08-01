"""Canonical VFS service with deterministic state machine (KITA-006).

``CanonicalVFSService@1`` is the sole authority for admitted VFS operations
against an *injected* storage boundary. It:

* exposes the closed ``VFSOperationKind`` vocabulary from
  :mod:`ipfs_kit_py.core.vfs.contracts`;
* never claims success without an observed admitted state transition;
* records failure events without ever emitting a success event on failure;
* renames/moves with a real namespace mutation inside the supported atomic
  boundary (typed unsupported for cross-mount/backend/namespace);
* bounds path, payload, page, and stream sizes;
* is cancellation- and deadline-aware before commit; and
* has no side effects outside the injected :class:`VFSStorageBoundary`.

No daemon, host filesystem, or network I/O is performed by this module.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable, Mapping, MutableMapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar, Final, Protocol, runtime_checkable

from ipfs_kit_py.core.operation_contracts import (
    ErrorCategory,
    ErrorCode,
    OperationState,
    Retryability,
)
from ipfs_kit_py.core.vfs.contracts import (
    MAX_LISTING_PAGE_SIZE,
    MAX_PATH_BYTES,
    MUTATING_OPERATIONS,
    AtomicBoundary,
    ListingOrder,
    ObservedStateTransition,
    UnsupportedReason,
    VFSDirEntry,
    VFSEntryKind,
    VFSError,
    VFSErrorCode,
    VFSListing,
    VFSMount,
    VFSOperation,
    VFSOperationKind,
    VFSOperationResult,
    VFSPathError,
    VFSPathPolicy,
    VFSStat,
    VFSUnsupportedError,
    assert_atomic_boundary_supported,
    classify_mount_pair,
    content_identity,
    make_failure,
    make_mutating_success,
    make_read_success,
    normalize_vfs_path,
    path_error_to_vfs_error,
    unsupported_to_vfs_error,
)

# ---------------------------------------------------------------------------
# Schema / bounds
# ---------------------------------------------------------------------------

SERVICE_CONTRACT_VERSION: Final[int] = 1
SERVICE_SCHEMA_MAJOR: Final[int] = 1
SERVICE_SCHEMA_MINOR: Final[int] = 0
SERVICE_SCHEMA_PATCH: Final[int] = 0
SERVICE_SCHEMA_VERSION: Final[str] = (
    f"{SERVICE_SCHEMA_MAJOR}.{SERVICE_SCHEMA_MINOR}.{SERVICE_SCHEMA_PATCH}"
)
CANONICAL_VFS_SERVICE_SCHEMA: Final[str] = (
    f"ipfs_kit_py/core/vfs/service/canonical@{SERVICE_SCHEMA_MAJOR}"
)
CanonicalVFSService_V1: Final[str] = CANONICAL_VFS_SERVICE_SCHEMA

MAX_PAYLOAD_BYTES: Final[int] = 1_048_576
MAX_STREAM_CHUNK_BYTES: Final[int] = 65_536
MAX_STREAM_CHUNKS: Final[int] = 256
MAX_NAMESPACE_ENTRIES: Final[int] = 65_536
MAX_TRACE_STEPS: Final[int] = 4_096
MAX_IDEMPOTENCY_CACHE: Final[int] = 1_024
DEFAULT_PAGE_SIZE: Final[int] = 256

_DEFAULT_MOUNT_ID: Final[str] = "mount:default"
_DEFAULT_NAMESPACE_ID: Final[str] = "ns:default"
_DEFAULT_BACKEND_ID: Final[str] = "backend:memory"


# ---------------------------------------------------------------------------
# Events / cancellation
# ---------------------------------------------------------------------------


class VFSEventKind(str, Enum):
    """Closed event vocabulary for VFS execution traces."""

    SUCCESS = "success"
    FAILURE = "failure"
    OBSERVATION = "observation"
    CANCELLED = "cancelled"
    DEADLINE = "deadline"


@dataclass(frozen=True)
class VFSEvent:
    """One immutable execution event (success never accompanies failure)."""

    kind: VFSEventKind
    operation_id: str
    op_kind: str
    code: str = ""
    path: str = ""
    detail: Mapping[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "operation_id": self.operation_id,
            "op_kind": self.op_kind,
            "code": self.code,
            "path": self.path,
            "detail": dict(self.detail),
        }


class CancellationToken:
    """Cooperative cancellation token checked at admission and pre-commit."""

    __slots__ = ("_cancelled",)

    def __init__(self, *, cancelled: bool = False) -> None:
        self._cancelled = bool(cancelled)

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    def raise_if_cancelled(self) -> None:
        if self._cancelled:
            raise VFSCancelledError("operation cancelled")


class VFSCancelledError(Exception):
    """Raised when a cooperative cancellation is observed."""


class VFSDeadlineExceededError(Exception):
    """Raised when the operation deadline is exceeded before commit."""


class VFSServiceError(Exception):
    """Internal service error (projected to VFSError)."""


# ---------------------------------------------------------------------------
# Storage boundary (side effects only here)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VFSStoredEntry:
    """One namespace entry stored behind the injected boundary."""

    kind: VFSEntryKind
    content: bytes = b""
    content_cid: str = ""
    version_cid: str = ""
    target: str = ""
    mtime_unix_ms: int = 0
    mode: int = 0
    mount_id: str = _DEFAULT_MOUNT_ID
    is_readonly: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.kind, VFSEntryKind):
            object.__setattr__(self, "kind", VFSEntryKind(self.kind))
        if not isinstance(self.content, (bytes, bytearray)):
            raise TypeError("content must be bytes")
        object.__setattr__(self, "content", bytes(self.content))

    def to_public_record(self) -> dict[str, Any]:
        """Compact, content-addressable public snapshot (no raw bodies)."""

        return {
            "kind": self.kind.value,
            "size_bytes": 0 if self.kind is VFSEntryKind.DIRECTORY else len(self.content),
            "content_cid": self.content_cid,
            "version_cid": self.version_cid,
            "target": self.target,
            "mtime_unix_ms": self.mtime_unix_ms,
            "mode": self.mode,
            "mount_id": self.mount_id,
            "is_readonly": self.is_readonly,
        }


@runtime_checkable
class VFSStorageBoundary(Protocol):
    """Injected storage boundary; the only admitted side-effect surface."""

    def get(self, path: str) -> VFSStoredEntry | None: ...

    def put(self, path: str, entry: VFSStoredEntry) -> None: ...

    def delete(self, path: str) -> None: ...

    def children(self, path: str) -> tuple[str, ...]: ...

    def rename(self, source: str, target: str) -> None: ...

    def snapshot(self) -> dict[str, dict[str, Any]]: ...

    @property
    def generation(self) -> int: ...

    def bump_generation(self) -> int: ...

    def entry_count(self) -> int: ...


def content_cid_for_bytes(data: bytes) -> str:
    """Deterministic content identity for file bytes."""

    digest = hashlib.sha256(data).hexdigest()
    return f"sha256:{digest}"


def version_cid_for(
    path: str,
    *,
    kind: VFSEntryKind,
    content_cid: str,
    generation: int,
    target: str = "",
) -> str:
    """Deterministic version identity for a namespace entry."""

    return content_identity(
        {
            "path": path,
            "kind": kind.value,
            "content_cid": content_cid,
            "generation": generation,
            "target": target,
        }
    )


class InMemoryVFSStorage:
    """Hermetic in-memory storage boundary (tests / reference wiring)."""

    def __init__(self, *, max_entries: int = MAX_NAMESPACE_ENTRIES) -> None:
        self._entries: dict[str, VFSStoredEntry] = {
            "": VFSStoredEntry(
                kind=VFSEntryKind.DIRECTORY,
                content_cid=content_cid_for_bytes(b""),
                version_cid=version_cid_for(
                    "", kind=VFSEntryKind.DIRECTORY, content_cid="", generation=0
                ),
                mount_id=_DEFAULT_MOUNT_ID,
            )
        }
        self._generation = 0
        self._max_entries = max_entries

    @property
    def generation(self) -> int:
        return self._generation

    def bump_generation(self) -> int:
        self._generation += 1
        return self._generation

    def entry_count(self) -> int:
        return len(self._entries)

    def get(self, path: str) -> VFSStoredEntry | None:
        return self._entries.get(path)

    def put(self, path: str, entry: VFSStoredEntry) -> None:
        if path not in self._entries and len(self._entries) >= self._max_entries:
            raise VFSServiceError("namespace entry bound exceeded")
        self._entries[path] = entry

    def delete(self, path: str) -> None:
        if path == "":
            raise VFSServiceError("cannot delete namespace root")
        self._entries.pop(path, None)

    def children(self, path: str) -> tuple[str, ...]:
        prefix = "" if path == "" else path + "/"
        names: set[str] = set()
        for key in self._entries:
            if key == path or key == "":
                continue
            if path == "":
                # top-level names only
                if "/" not in key:
                    names.add(key)
                else:
                    names.add(key.split("/", 1)[0])
            elif key.startswith(prefix):
                rest = key[len(prefix) :]
                if not rest:
                    continue
                names.add(rest.split("/", 1)[0])
        return tuple(sorted(names, key=lambda n: n.encode("utf-8")))

    def rename(self, source: str, target: str) -> None:
        if source == "":
            raise VFSServiceError("cannot rename namespace root")
        if source not in self._entries:
            raise KeyError(source)
        # Move source and all descendants.
        moves: list[tuple[str, str, VFSStoredEntry]] = []
        for key, entry in list(self._entries.items()):
            if key == source or key.startswith(source + "/"):
                suffix = key[len(source) :]
                new_key = target + suffix
                moves.append((key, new_key, entry))
        for old, _new, _entry in moves:
            del self._entries[old]
        for _old, new, entry in moves:
            if new not in self._entries and len(self._entries) >= self._max_entries:
                raise VFSServiceError("namespace entry bound exceeded during rename")
            self._entries[new] = entry

    def snapshot(self) -> dict[str, dict[str, Any]]:
        return {path: entry.to_public_record() for path, entry in sorted(self._entries.items())}

    def seed(
        self,
        path: str,
        *,
        kind: VFSEntryKind = VFSEntryKind.FILE,
        content: bytes = b"",
        target: str = "",
        mount_id: str = _DEFAULT_MOUNT_ID,
        ensure_parents: bool = True,
    ) -> VFSStoredEntry:
        """Seed an entry for tests (still confined to this boundary)."""

        path = normalize_vfs_path(path).path if path else ""
        if ensure_parents and path:
            self._ensure_parents(path)
        cid = content_cid_for_bytes(content) if kind is VFSEntryKind.FILE else content_cid_for_bytes(b"")
        gen = self.bump_generation()
        entry = VFSStoredEntry(
            kind=kind,
            content=content if kind is VFSEntryKind.FILE else b"",
            content_cid=cid,
            version_cid=version_cid_for(
                path, kind=kind, content_cid=cid, generation=gen, target=target
            ),
            target=target,
            mtime_unix_ms=gen,
            mount_id=mount_id,
        )
        self.put(path, entry)
        return entry

    def _ensure_parents(self, path: str) -> None:
        segments = path.split("/") if path else []
        acc: list[str] = []
        for seg in segments[:-1]:
            acc.append(seg)
            parent = "/".join(acc)
            existing = self.get(parent)
            if existing is None:
                gen = self.generation
                self.put(
                    parent,
                    VFSStoredEntry(
                        kind=VFSEntryKind.DIRECTORY,
                        content_cid=content_cid_for_bytes(b""),
                        version_cid=version_cid_for(
                            parent,
                            kind=VFSEntryKind.DIRECTORY,
                            content_cid="",
                            generation=gen,
                        ),
                        mount_id=_DEFAULT_MOUNT_ID,
                    ),
                )
            elif existing.kind is not VFSEntryKind.DIRECTORY:
                raise VFSServiceError(f"parent {parent!r} is not a directory")


# ---------------------------------------------------------------------------
# Service outcome / request context
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VFSServiceOutcome:
    """Full outcome of one service execution (result + side-channel data)."""

    result: VFSOperationResult
    data: bytes = b""
    chunks: tuple[bytes, ...] = ()
    events: tuple[VFSEvent, ...] = ()
    namespace_generation: int = 0
    namespace_snapshot: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.result.success

    def to_record(self) -> dict[str, Any]:
        return {
            "result": self.result.to_record(),
            "data_size": len(self.data),
            "chunk_count": len(self.chunks),
            "events": [event.to_record() for event in self.events],
            "namespace_generation": self.namespace_generation,
            "namespace_snapshot": {k: dict(v) for k, v in self.namespace_snapshot.items()},
        }

    def trace_step_record(self, index: int, operation: VFSOperation) -> dict[str, Any]:
        """Compact differential-trace step (stable across service/reference)."""

        err = self.result.error
        return {
            "index": index,
            "operation_id": operation.operation_id,
            "kind": operation.kind.value,
            "path": operation.path or operation.source_path,
            "source_path": operation.source_path,
            "target_path": operation.target_path,
            "success": self.result.success,
            "state": self.result.state.value,
            "error_code": None if err is None else err.code.value,
            "resulting_content_cid": self.result.resulting_content_cid,
            "resulting_version_cid": self.result.resulting_version_cid,
            "event_kinds": [e.kind.value for e in self.events],
            "namespace": {k: dict(v) for k, v in sorted(self.namespace_snapshot.items())},
            "data_size": len(self.data),
            "chunk_count": len(self.chunks),
        }


@dataclass(frozen=True)
class VFSExecuteRequest:
    """Optional execution context attached to a VFSOperation."""

    payload: bytes = b""
    page_size: int = 0
    cursor: str = ""
    stream_chunk_size: int = MAX_STREAM_CHUNK_BYTES
    cancel: CancellationToken | None = None
    deadline_unix_ms: int = 0
    now_unix_ms: int = 0
    mount: VFSMount | None = None
    symlink_target: str = ""


# ---------------------------------------------------------------------------
# Canonical service
# ---------------------------------------------------------------------------


class CanonicalVFSService:
    """Deterministic canonical VFS service (``CanonicalVFSService@1``).

    All mutations go through ``storage``. No other I/O is performed.
    """

    SCHEMA: ClassVar[str] = CANONICAL_VFS_SERVICE_SCHEMA
    CONTRACT_VERSION: ClassVar[int] = SERVICE_CONTRACT_VERSION

    def __init__(
        self,
        storage: VFSStorageBoundary | None = None,
        *,
        path_policy: VFSPathPolicy | None = None,
        default_mount: VFSMount | None = None,
        clock: Callable[[], int] | None = None,
        max_payload_bytes: int = MAX_PAYLOAD_BYTES,
    ) -> None:
        self._storage: VFSStorageBoundary = storage or InMemoryVFSStorage()
        self._policy = path_policy or VFSPathPolicy.default()
        self._clock = clock or (lambda: int(time.time() * 1000))
        self._max_payload = max_payload_bytes
        self._mounts: dict[str, VFSMount] = {}
        self._default_mount = default_mount or VFSMount(
            mount_id=_DEFAULT_MOUNT_ID,
            mount_path="",
            backend_id=_DEFAULT_BACKEND_ID,
            namespace_id=_DEFAULT_NAMESPACE_ID,
            read_only=False,
            atomic_boundary=AtomicBoundary.SINGLE_MOUNT,
        )
        self._mounts[self._default_mount.mount_id] = self._default_mount
        self._idempotency: MutableMapping[str, VFSServiceOutcome] = {}
        self._obs_seq = 0
        self._event_log: list[VFSEvent] = []

    # -- public surface -----------------------------------------------------

    @property
    def storage(self) -> VFSStorageBoundary:
        return self._storage

    @property
    def mounts(self) -> Mapping[str, VFSMount]:
        return dict(self._mounts)

    @property
    def event_log(self) -> tuple[VFSEvent, ...]:
        return tuple(self._event_log)

    def clear_event_log(self) -> None:
        self._event_log.clear()

    def execute(
        self,
        operation: VFSOperation,
        request: VFSExecuteRequest | None = None,
    ) -> VFSServiceOutcome:
        """Execute one operation; never raises for admitted semantic failures.

        Contract and bounds violations that prevent building a typed result
        still project to a failed :class:`VFSOperationResult`. Cancellation
        and deadline produce failure outcomes with no success event.
        """

        req = request or VFSExecuteRequest()
        try:
            return self._execute_inner(operation, req)
        except VFSCancelledError:
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.INTERNAL,
                    message="operation cancelled",
                    category=ErrorCategory.CANCELLATION,
                    storage_code=ErrorCode.CANCELLED,
                    retryability=Retryability.NEVER,
                    state=OperationState.CANCELLED,
                    path=operation.path,
                ),
                event_kind=VFSEventKind.CANCELLED,
            )
        except VFSDeadlineExceededError:
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.INTERNAL,
                    message="operation deadline exceeded",
                    category=ErrorCategory.TIMEOUT,
                    storage_code=ErrorCode.DEADLINE_EXCEEDED,
                    retryability=Retryability.NEVER,
                    state=OperationState.DEADLINE_EXCEEDED,
                    path=operation.path,
                ),
                event_kind=VFSEventKind.DEADLINE,
            )
        except VFSPathError as exc:
            return self._fail(operation, path_error_to_vfs_error(exc))
        except VFSUnsupportedError as exc:
            return self._fail(operation, unsupported_to_vfs_error(exc))
        except VFSServiceError as exc:
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.INTERNAL,
                    message=str(exc),
                    category=ErrorCategory.INTERNAL,
                    storage_code=ErrorCode.INTERNAL,
                    retryability=Retryability.NEVER,
                    state=OperationState.FAILED,
                    path=operation.path,
                ),
            )
        except (TypeError, ValueError) as exc:
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.INTERNAL,
                    message=f"invalid operation: {exc}",
                    category=ErrorCategory.VALIDATION,
                    storage_code=ErrorCode.INVALID_REQUEST,
                    retryability=Retryability.NEVER,
                    state=OperationState.REJECTED,
                    path=getattr(operation, "path", "") or "",
                ),
            )

    def run_trace(
        self,
        operations: Sequence[tuple[VFSOperation, VFSExecuteRequest | None]],
    ) -> list[dict[str, Any]]:
        """Execute a bounded sequence and return differential-trace steps."""

        if len(operations) > MAX_TRACE_STEPS:
            raise VFSServiceError(f"trace exceeds MAX_TRACE_STEPS ({MAX_TRACE_STEPS})")
        steps: list[dict[str, Any]] = []
        for index, item in enumerate(operations):
            op, req = item if isinstance(item, tuple) else (item, None)
            outcome = self.execute(op, req)
            steps.append(outcome.trace_step_record(index, op))
            if not outcome.success and outcome.result.state in (
                OperationState.CANCELLED,
                OperationState.DEADLINE_EXCEEDED,
            ):
                # Cooperative stop after cancel/deadline; remaining ops not run.
                break
        return steps

    # -- internals ----------------------------------------------------------

    def _execute_inner(
        self, operation: VFSOperation, req: VFSExecuteRequest
    ) -> VFSServiceOutcome:
        self._check_cancel_deadline(req)

        if operation.idempotency_key:
            cached = self._idempotency.get(operation.idempotency_key)
            if cached is not None:
                return cached

        if len(req.payload) > self._max_payload:
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.INTERNAL,
                    message=f"payload exceeds bound of {self._max_payload} bytes",
                    category=ErrorCategory.VALIDATION,
                    storage_code=ErrorCode.UNBOUNDED_FIELD,
                    retryability=Retryability.NEVER,
                    state=OperationState.REJECTED,
                    path=operation.path,
                ),
            )

        # Normalize paths via policy (also rejects traversal / absolute).
        self._normalize_operation_paths(operation)

        # Atomic boundary gate for mutations that declare unsupported bounds.
        if operation.kind in MUTATING_OPERATIONS:
            try:
                assert_atomic_boundary_supported(operation.atomic_boundary)
            except VFSUnsupportedError as exc:
                return self._fail(operation, unsupported_to_vfs_error(exc))

        # Read-only mount gate.
        mount = self._resolve_mount(operation)
        if operation.kind in MUTATING_OPERATIONS and mount is not None and mount.read_only:
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.READ_ONLY,
                    message="mount is read-only",
                    category=ErrorCategory.AUTHORIZATION,
                    storage_code=ErrorCode.FORBIDDEN,
                    retryability=Retryability.NEVER,
                    state=OperationState.AUTHORIZATION_DENIED,
                    path=operation.path,
                    mount_id=mount.mount_id,
                ),
            )

        handlers: dict[VFSOperationKind, Callable[..., VFSServiceOutcome]] = {
            VFSOperationKind.STAT: self._op_stat,
            VFSOperationKind.LIST: self._op_list,
            VFSOperationKind.READ: self._op_read,
            VFSOperationKind.RANGE_READ: self._op_range_read,
            VFSOperationKind.STREAM: self._op_stream,
            VFSOperationKind.CREATE: self._op_create,
            VFSOperationKind.REPLACE: self._op_replace,
            VFSOperationKind.MKDIR: self._op_mkdir,
            VFSOperationKind.RMDIR: self._op_rmdir,
            VFSOperationKind.RENAME: self._op_rename,
            VFSOperationKind.MOVE: self._op_move,
            VFSOperationKind.DELETE: self._op_delete,
            VFSOperationKind.CAS_WRITE: self._op_cas_write,
            VFSOperationKind.MOUNT: self._op_mount,
            VFSOperationKind.UNMOUNT: self._op_unmount,
            VFSOperationKind.RESOLVE: self._op_resolve,
        }
        handler = handlers.get(operation.kind)
        if handler is None:
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.UNSUPPORTED,
                    message=f"unsupported operation kind {operation.kind.value}",
                    category=ErrorCategory.UNSUPPORTED,
                    storage_code=ErrorCode.UNSUPPORTED,
                    retryability=Retryability.NEVER,
                    state=OperationState.UNSUPPORTED,
                    unsupported_reason=UnsupportedReason.OPERATION_KIND.value,
                ),
            )

        outcome = handler(operation, req)
        if operation.idempotency_key and len(self._idempotency) < MAX_IDEMPOTENCY_CACHE:
            self._idempotency[operation.idempotency_key] = outcome
        return outcome

    def _normalize_operation_paths(self, operation: VFSOperation) -> None:
        # VFSOperation already normalizes on construction; re-validate policy.
        for attr in ("path", "source_path", "target_path"):
            value = getattr(operation, attr)
            if value:
                normalize_vfs_path(value, policy=self._policy)

    def _check_cancel_deadline(self, req: VFSExecuteRequest) -> None:
        if req.cancel is not None and req.cancel.is_cancelled:
            raise VFSCancelledError("operation cancelled")
        now = req.now_unix_ms or self._clock()
        if req.deadline_unix_ms and now > req.deadline_unix_ms:
            raise VFSDeadlineExceededError("deadline exceeded")

    def _pre_commit(self, req: VFSExecuteRequest) -> None:
        """Cancellation/deadline gate immediately before a mutating commit."""

        self._check_cancel_deadline(req)

    def _resolve_mount(self, operation: VFSOperation) -> VFSMount | None:
        if operation.mount_id and operation.mount_id in self._mounts:
            return self._mounts[operation.mount_id]
        return self._default_mount

    def _next_obs(self, prefix: str = "obs") -> str:
        self._obs_seq += 1
        return f"{prefix}:{self._obs_seq}"

    def _emit(self, event: VFSEvent) -> None:
        self._event_log.append(event)

    def _parent_path(self, path: str) -> str:
        if not path or "/" not in path:
            return ""
        return path.rsplit("/", 1)[0]

    def _require_parent_dir(self, path: str) -> VFSError | None:
        parent = self._parent_path(path)
        entry = self._storage.get(parent)
        if entry is None:
            return VFSError(
                code=VFSErrorCode.NOT_FOUND,
                message=f"parent directory not found: {parent or '/'}",
                category=ErrorCategory.STORAGE,
                storage_code=ErrorCode.NOT_FOUND,
                retryability=Retryability.NEVER,
                state=OperationState.FAILED,
                path=parent,
            )
        if entry.kind is not VFSEntryKind.DIRECTORY:
            return VFSError(
                code=VFSErrorCode.NOT_DIRECTORY,
                message=f"parent is not a directory: {parent or '/'}",
                category=ErrorCategory.VALIDATION,
                storage_code=ErrorCode.INVALID_REQUEST,
                retryability=Retryability.NEVER,
                state=OperationState.REJECTED,
                path=parent,
            )
        return None

    def _entry_to_stat(self, path: str, entry: VFSStoredEntry) -> VFSStat:
        size = 0 if entry.kind is VFSEntryKind.DIRECTORY else len(entry.content)
        return VFSStat(
            path=path,
            kind=entry.kind,
            size_bytes=size,
            mtime_unix_ms=entry.mtime_unix_ms,
            mode=entry.mode,
            content_cid=entry.content_cid,
            version_cid=entry.version_cid,
            target=entry.target,
            mount_id=entry.mount_id,
            generation_id=f"gen:{self._storage.generation}",
            observed=True,
            is_readonly=entry.is_readonly,
        )

    def _success_mutating(
        self,
        operation: VFSOperation,
        *,
        from_version_cid: str,
        to_version_cid: str,
        effect_id: str,
        resulting_content_cid: str = "",
        mount_id: str = "",
        path: str = "",
        data: bytes = b"",
        chunks: tuple[bytes, ...] = (),
        detail: Mapping[str, Any] | None = None,
    ) -> VFSServiceOutcome:
        obs = self._next_obs("obs-mut")
        result = make_mutating_success(
            operation,
            from_version_cid=from_version_cid,
            to_version_cid=to_version_cid,
            effect_evidence_ids=(effect_id,),
            observation_id=obs,
            resulting_content_cid=resulting_content_cid,
            mount_id=mount_id or operation.mount_id or _DEFAULT_MOUNT_ID,
        )
        # Path may be target for rename.
        if path:
            # Reconstruct with explicit path if needed (frozen dataclass).
            result = VFSOperationResult(
                operation_id=result.operation_id,
                kind=result.kind,
                success=True,
                state=result.state,
                observed_transition=result.observed_transition,
                resulting_content_cid=result.resulting_content_cid,
                resulting_version_cid=result.resulting_version_cid,
                mount_id=result.mount_id,
                path=path,
                request_id=result.request_id,
            )
        event = VFSEvent(
            kind=VFSEventKind.SUCCESS,
            operation_id=operation.operation_id,
            op_kind=operation.kind.value,
            code=OperationState.COMMITTED.value,
            path=path or operation.path or operation.target_path,
            detail=dict(detail or {}),
        )
        self._emit(event)
        return VFSServiceOutcome(
            result=result,
            data=data,
            chunks=chunks,
            events=(event,),
            namespace_generation=self._storage.generation,
            namespace_snapshot=self._storage.snapshot(),
        )

    def _success_read(
        self,
        operation: VFSOperation,
        *,
        stat: VFSStat | None = None,
        listing: VFSListing | None = None,
        data: bytes = b"",
        chunks: tuple[bytes, ...] = (),
        detail: Mapping[str, Any] | None = None,
    ) -> VFSServiceOutcome:
        obs = self._next_obs("obs-read")
        result = make_read_success(
            operation,
            observation_id=obs,
            stat=stat,
            listing=listing,
            mount_id=operation.mount_id or _DEFAULT_MOUNT_ID,
        )
        event = VFSEvent(
            kind=VFSEventKind.SUCCESS,
            operation_id=operation.operation_id,
            op_kind=operation.kind.value,
            code=OperationState.COMMITTED.value,
            path=operation.path,
            detail=dict(detail or {}),
        )
        # Observation event is secondary; success is primary for reads.
        obs_event = VFSEvent(
            kind=VFSEventKind.OBSERVATION,
            operation_id=operation.operation_id,
            op_kind=operation.kind.value,
            code=obs,
            path=operation.path,
        )
        self._emit(event)
        self._emit(obs_event)
        return VFSServiceOutcome(
            result=result,
            data=data,
            chunks=chunks,
            events=(event, obs_event),
            namespace_generation=self._storage.generation,
            namespace_snapshot=self._storage.snapshot(),
        )

    def _fail(
        self,
        operation: VFSOperation,
        error: VFSError,
        *,
        event_kind: VFSEventKind = VFSEventKind.FAILURE,
    ) -> VFSServiceOutcome:
        result = make_failure(operation, error)
        event = VFSEvent(
            kind=event_kind,
            operation_id=operation.operation_id,
            op_kind=operation.kind.value,
            code=error.code.value,
            path=error.path or operation.path,
            detail={"state": error.state.value, "message": error.message},
        )
        self._emit(event)
        # Invariant: no success event on failure.
        assert event.kind is not VFSEventKind.SUCCESS
        assert not result.success
        return VFSServiceOutcome(
            result=result,
            events=(event,),
            namespace_generation=self._storage.generation,
            namespace_snapshot=self._storage.snapshot(),
        )

    # -- operation handlers -------------------------------------------------

    def _op_stat(
        self, operation: VFSOperation, req: VFSExecuteRequest
    ) -> VFSServiceOutcome:
        path = operation.path
        entry = self._storage.get(path)
        if entry is None:
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.NOT_FOUND,
                    message=f"path not found: {path or '/'}",
                    category=ErrorCategory.STORAGE,
                    storage_code=ErrorCode.NOT_FOUND,
                    retryability=Retryability.NEVER,
                    state=OperationState.FAILED,
                    path=path,
                ),
            )
        return self._success_read(operation, stat=self._entry_to_stat(path, entry))

    def _op_list(
        self, operation: VFSOperation, req: VFSExecuteRequest
    ) -> VFSServiceOutcome:
        path = operation.path
        entry = self._storage.get(path)
        if entry is None:
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.NOT_FOUND,
                    message=f"path not found: {path or '/'}",
                    category=ErrorCategory.STORAGE,
                    storage_code=ErrorCode.NOT_FOUND,
                    retryability=Retryability.NEVER,
                    state=OperationState.FAILED,
                    path=path,
                ),
            )
        if entry.kind is not VFSEntryKind.DIRECTORY:
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.NOT_DIRECTORY,
                    message=f"not a directory: {path or '/'}",
                    category=ErrorCategory.VALIDATION,
                    storage_code=ErrorCode.INVALID_REQUEST,
                    retryability=Retryability.NEVER,
                    state=OperationState.REJECTED,
                    path=path,
                ),
            )
        page_size = req.page_size or DEFAULT_PAGE_SIZE
        if page_size < 0 or page_size > MAX_LISTING_PAGE_SIZE:
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.INTERNAL,
                    message=f"page_size must be 0..{MAX_LISTING_PAGE_SIZE}",
                    category=ErrorCategory.VALIDATION,
                    storage_code=ErrorCode.INVALID_REQUEST,
                    retryability=Retryability.NEVER,
                    state=OperationState.REJECTED,
                    path=path,
                ),
            )
        names = list(self._storage.children(path))
        if req.cursor:
            try:
                start = names.index(req.cursor) + 1
            except ValueError:
                start = 0
            names = names[start:]
        entries: list[VFSDirEntry] = []
        for name in names:
            child_path = name if path == "" else f"{path}/{name}"
            child = self._storage.get(child_path)
            if child is None:
                # Intermediate path prefix from nested keys.
                child_kind = VFSEntryKind.DIRECTORY
                stat = VFSStat(
                    path=child_path,
                    kind=child_kind,
                    generation_id=f"gen:{self._storage.generation}",
                    observed=True,
                    mount_id=operation.mount_id or _DEFAULT_MOUNT_ID,
                )
            else:
                child_kind = child.kind
                stat = self._entry_to_stat(child_path, child)
            entries.append(VFSDirEntry(name=name, kind=child_kind, stat=stat))
        listing = VFSListing.from_entries(
            path,
            entries,
            cursor=req.cursor,
            page_size=page_size if page_size else len(entries),
            generation_id=f"gen:{self._storage.generation}",
            mount_id=operation.mount_id or _DEFAULT_MOUNT_ID,
        )
        return self._success_read(operation, listing=listing)

    def _op_read(
        self, operation: VFSOperation, req: VFSExecuteRequest
    ) -> VFSServiceOutcome:
        path = operation.path
        entry = self._storage.get(path)
        if entry is None:
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.NOT_FOUND,
                    message=f"path not found: {path}",
                    category=ErrorCategory.STORAGE,
                    storage_code=ErrorCode.NOT_FOUND,
                    retryability=Retryability.NEVER,
                    state=OperationState.FAILED,
                    path=path,
                ),
            )
        if entry.kind is not VFSEntryKind.FILE:
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.IS_DIRECTORY
                    if entry.kind is VFSEntryKind.DIRECTORY
                    else VFSErrorCode.STAT_ERROR,
                    message=f"not a file: {path}",
                    category=ErrorCategory.VALIDATION,
                    storage_code=ErrorCode.INVALID_REQUEST,
                    retryability=Retryability.NEVER,
                    state=OperationState.REJECTED,
                    path=path,
                ),
            )
        if len(entry.content) > self._max_payload:
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.INTERNAL,
                    message="file exceeds read bound",
                    category=ErrorCategory.VALIDATION,
                    storage_code=ErrorCode.UNBOUNDED_FIELD,
                    retryability=Retryability.NEVER,
                    state=OperationState.REJECTED,
                    path=path,
                ),
            )
        return self._success_read(
            operation,
            stat=self._entry_to_stat(path, entry),
            data=entry.content,
            detail={"bytes": len(entry.content)},
        )

    def _op_range_read(
        self, operation: VFSOperation, req: VFSExecuteRequest
    ) -> VFSServiceOutcome:
        path = operation.path
        entry = self._storage.get(path)
        if entry is None or entry.kind is not VFSEntryKind.FILE:
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.NOT_FOUND
                    if entry is None
                    else VFSErrorCode.IS_DIRECTORY,
                    message=f"range read requires a file: {path}",
                    category=ErrorCategory.STORAGE
                    if entry is None
                    else ErrorCategory.VALIDATION,
                    storage_code=ErrorCode.NOT_FOUND
                    if entry is None
                    else ErrorCode.INVALID_REQUEST,
                    retryability=Retryability.NEVER,
                    state=OperationState.FAILED
                    if entry is None
                    else OperationState.REJECTED,
                    path=path,
                ),
            )
        start = operation.range_start
        end = operation.range_end if operation.range_end else len(entry.content)
        if start > len(entry.content):
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.UNSUPPORTED,
                    message="range_start beyond EOF",
                    category=ErrorCategory.UNSUPPORTED,
                    storage_code=ErrorCode.UNSUPPORTED,
                    retryability=Retryability.NEVER,
                    state=OperationState.UNSUPPORTED,
                    path=path,
                    unsupported_reason=UnsupportedReason.RANGE_BEYOND_EOF.value,
                ),
            )
        end = min(end, len(entry.content))
        if end < start:
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.INTERNAL,
                    message="invalid range",
                    category=ErrorCategory.VALIDATION,
                    storage_code=ErrorCode.INVALID_REQUEST,
                    retryability=Retryability.NEVER,
                    state=OperationState.REJECTED,
                    path=path,
                ),
            )
        data = entry.content[start:end]
        return self._success_read(
            operation,
            stat=self._entry_to_stat(path, entry),
            data=data,
            detail={"range_start": start, "range_end": end, "bytes": len(data)},
        )

    def _op_stream(
        self, operation: VFSOperation, req: VFSExecuteRequest
    ) -> VFSServiceOutcome:
        path = operation.path
        entry = self._storage.get(path)
        if entry is None or entry.kind is not VFSEntryKind.FILE:
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.NOT_FOUND
                    if entry is None
                    else VFSErrorCode.IS_DIRECTORY,
                    message=f"stream requires a file: {path}",
                    category=ErrorCategory.STORAGE
                    if entry is None
                    else ErrorCategory.VALIDATION,
                    storage_code=ErrorCode.NOT_FOUND
                    if entry is None
                    else ErrorCode.INVALID_REQUEST,
                    retryability=Retryability.NEVER,
                    state=OperationState.FAILED
                    if entry is None
                    else OperationState.REJECTED,
                    path=path,
                ),
            )
        chunk_size = req.stream_chunk_size or MAX_STREAM_CHUNK_BYTES
        if chunk_size < 1 or chunk_size > MAX_STREAM_CHUNK_BYTES:
            chunk_size = MAX_STREAM_CHUNK_BYTES
        chunks: list[bytes] = []
        data = entry.content
        offset = 0
        while offset < len(data) and len(chunks) < MAX_STREAM_CHUNKS:
            chunks.append(data[offset : offset + chunk_size])
            offset += chunk_size
        if offset < len(data):
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.UNSUPPORTED,
                    message="stream exceeds chunk bound",
                    category=ErrorCategory.UNSUPPORTED,
                    storage_code=ErrorCode.UNSUPPORTED,
                    retryability=Retryability.NEVER,
                    state=OperationState.UNSUPPORTED,
                    path=path,
                    unsupported_reason=UnsupportedReason.STREAM_UNAVAILABLE.value,
                ),
            )
        return self._success_read(
            operation,
            stat=self._entry_to_stat(path, entry),
            data=data,
            chunks=tuple(chunks),
            detail={"chunk_count": len(chunks), "bytes": len(data)},
        )

    def _op_create(
        self, operation: VFSOperation, req: VFSExecuteRequest
    ) -> VFSServiceOutcome:
        path = operation.path
        if path == "":
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.ALREADY_EXISTS,
                    message="cannot create over namespace root",
                    category=ErrorCategory.VALIDATION,
                    storage_code=ErrorCode.ALREADY_EXISTS,
                    retryability=Retryability.NEVER,
                    state=OperationState.CONFLICT,
                    path=path,
                ),
            )
        if self._storage.get(path) is not None:
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.ALREADY_EXISTS,
                    message=f"path already exists: {path}",
                    category=ErrorCategory.STORAGE,
                    storage_code=ErrorCode.ALREADY_EXISTS,
                    retryability=Retryability.NEVER,
                    state=OperationState.CONFLICT,
                    path=path,
                ),
            )
        parent_err = self._require_parent_dir(path)
        if parent_err is not None:
            return self._fail(operation, parent_err)
        self._pre_commit(req)
        gen = self._storage.bump_generation()
        cid = operation.content_cid or content_cid_for_bytes(req.payload)
        version = version_cid_for(
            path, kind=VFSEntryKind.FILE, content_cid=cid, generation=gen
        )
        entry = VFSStoredEntry(
            kind=VFSEntryKind.FILE,
            content=req.payload,
            content_cid=cid,
            version_cid=version,
            mtime_unix_ms=req.now_unix_ms or gen,
            mount_id=operation.mount_id or _DEFAULT_MOUNT_ID,
        )
        self._storage.put(path, entry)
        effect = f"effect:create:{path}:{gen}"
        return self._success_mutating(
            operation,
            from_version_cid="",
            to_version_cid=version,
            effect_id=effect,
            resulting_content_cid=cid,
            path=path,
            detail={"created": path},
        )

    def _op_replace(
        self, operation: VFSOperation, req: VFSExecuteRequest
    ) -> VFSServiceOutcome:
        path = operation.path
        existing = self._storage.get(path)
        if existing is None:
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.NOT_FOUND,
                    message=f"path not found: {path}",
                    category=ErrorCategory.STORAGE,
                    storage_code=ErrorCode.NOT_FOUND,
                    retryability=Retryability.NEVER,
                    state=OperationState.FAILED,
                    path=path,
                ),
            )
        if existing.kind is not VFSEntryKind.FILE:
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.IS_DIRECTORY,
                    message=f"cannot replace non-file: {path}",
                    category=ErrorCategory.VALIDATION,
                    storage_code=ErrorCode.INVALID_REQUEST,
                    retryability=Retryability.NEVER,
                    state=OperationState.REJECTED,
                    path=path,
                ),
            )
        self._pre_commit(req)
        from_v = existing.version_cid
        gen = self._storage.bump_generation()
        cid = operation.content_cid or content_cid_for_bytes(req.payload)
        version = version_cid_for(
            path, kind=VFSEntryKind.FILE, content_cid=cid, generation=gen
        )
        self._storage.put(
            path,
            VFSStoredEntry(
                kind=VFSEntryKind.FILE,
                content=req.payload,
                content_cid=cid,
                version_cid=version,
                mtime_unix_ms=req.now_unix_ms or gen,
                mount_id=existing.mount_id,
            ),
        )
        return self._success_mutating(
            operation,
            from_version_cid=from_v,
            to_version_cid=version,
            effect_id=f"effect:replace:{path}:{gen}",
            resulting_content_cid=cid,
            path=path,
        )

    def _op_mkdir(
        self, operation: VFSOperation, req: VFSExecuteRequest
    ) -> VFSServiceOutcome:
        path = operation.path
        if path == "":
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.ALREADY_EXISTS,
                    message="namespace root already exists",
                    category=ErrorCategory.STORAGE,
                    storage_code=ErrorCode.ALREADY_EXISTS,
                    retryability=Retryability.NEVER,
                    state=OperationState.CONFLICT,
                    path=path,
                ),
            )
        if self._storage.get(path) is not None:
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.ALREADY_EXISTS,
                    message=f"path already exists: {path}",
                    category=ErrorCategory.STORAGE,
                    storage_code=ErrorCode.ALREADY_EXISTS,
                    retryability=Retryability.NEVER,
                    state=OperationState.CONFLICT,
                    path=path,
                ),
            )
        parent_err = self._require_parent_dir(path)
        if parent_err is not None:
            return self._fail(operation, parent_err)
        self._pre_commit(req)
        gen = self._storage.bump_generation()
        cid = content_cid_for_bytes(b"")
        version = version_cid_for(
            path, kind=VFSEntryKind.DIRECTORY, content_cid=cid, generation=gen
        )
        self._storage.put(
            path,
            VFSStoredEntry(
                kind=VFSEntryKind.DIRECTORY,
                content_cid=cid,
                version_cid=version,
                mtime_unix_ms=req.now_unix_ms or gen,
                mount_id=operation.mount_id or _DEFAULT_MOUNT_ID,
            ),
        )
        return self._success_mutating(
            operation,
            from_version_cid="",
            to_version_cid=version,
            effect_id=f"effect:mkdir:{path}:{gen}",
            resulting_content_cid=cid,
            path=path,
        )

    def _op_rmdir(
        self, operation: VFSOperation, req: VFSExecuteRequest
    ) -> VFSServiceOutcome:
        path = operation.path
        if path == "":
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.PERMISSION_DENIED,
                    message="cannot remove namespace root",
                    category=ErrorCategory.AUTHORIZATION,
                    storage_code=ErrorCode.FORBIDDEN,
                    retryability=Retryability.NEVER,
                    state=OperationState.AUTHORIZATION_DENIED,
                    path=path,
                ),
            )
        entry = self._storage.get(path)
        if entry is None:
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.NOT_FOUND,
                    message=f"path not found: {path}",
                    category=ErrorCategory.STORAGE,
                    storage_code=ErrorCode.NOT_FOUND,
                    retryability=Retryability.NEVER,
                    state=OperationState.FAILED,
                    path=path,
                ),
            )
        if entry.kind is not VFSEntryKind.DIRECTORY:
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.NOT_DIRECTORY,
                    message=f"not a directory: {path}",
                    category=ErrorCategory.VALIDATION,
                    storage_code=ErrorCode.INVALID_REQUEST,
                    retryability=Retryability.NEVER,
                    state=OperationState.REJECTED,
                    path=path,
                ),
            )
        if self._storage.children(path):
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.NOT_EMPTY,
                    message=f"directory not empty: {path}",
                    category=ErrorCategory.STORAGE,
                    storage_code=ErrorCode.CONFLICT,
                    retryability=Retryability.NEVER,
                    state=OperationState.CONFLICT,
                    path=path,
                ),
            )
        self._pre_commit(req)
        from_v = entry.version_cid
        gen = self._storage.bump_generation()
        self._storage.delete(path)
        return self._success_mutating(
            operation,
            from_version_cid=from_v,
            to_version_cid="",
            effect_id=f"effect:rmdir:{path}:{gen}",
            path=path,
        )

    def _op_delete(
        self, operation: VFSOperation, req: VFSExecuteRequest
    ) -> VFSServiceOutcome:
        path = operation.path
        if path == "":
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.PERMISSION_DENIED,
                    message="cannot delete namespace root",
                    category=ErrorCategory.AUTHORIZATION,
                    storage_code=ErrorCode.FORBIDDEN,
                    retryability=Retryability.NEVER,
                    state=OperationState.AUTHORIZATION_DENIED,
                    path=path,
                ),
            )
        entry = self._storage.get(path)
        if entry is None:
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.NOT_FOUND,
                    message=f"path not found: {path}",
                    category=ErrorCategory.STORAGE,
                    storage_code=ErrorCode.NOT_FOUND,
                    retryability=Retryability.NEVER,
                    state=OperationState.FAILED,
                    path=path,
                ),
            )
        if entry.kind is VFSEntryKind.DIRECTORY and self._storage.children(path):
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.NOT_EMPTY,
                    message=f"directory not empty: {path}",
                    category=ErrorCategory.STORAGE,
                    storage_code=ErrorCode.CONFLICT,
                    retryability=Retryability.NEVER,
                    state=OperationState.CONFLICT,
                    path=path,
                ),
            )
        self._pre_commit(req)
        from_v = entry.version_cid
        gen = self._storage.bump_generation()
        self._storage.delete(path)
        return self._success_mutating(
            operation,
            from_version_cid=from_v,
            to_version_cid="",
            effect_id=f"effect:delete:{path}:{gen}",
            path=path,
        )

    def _op_rename(
        self, operation: VFSOperation, req: VFSExecuteRequest
    ) -> VFSServiceOutcome:
        return self._rename_or_move(operation, req, kind_label="rename")

    def _op_move(
        self, operation: VFSOperation, req: VFSExecuteRequest
    ) -> VFSServiceOutcome:
        return self._rename_or_move(operation, req, kind_label="move")

    def _rename_or_move(
        self,
        operation: VFSOperation,
        req: VFSExecuteRequest,
        *,
        kind_label: str,
    ) -> VFSServiceOutcome:
        source = operation.source_path
        target = operation.target_path
        if not source or not target:
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.INVALID_PATH,
                    message=f"{kind_label} requires source_path and target_path",
                    category=ErrorCategory.VALIDATION,
                    storage_code=ErrorCode.INVALID_REQUEST,
                    retryability=Retryability.NEVER,
                    state=OperationState.REJECTED,
                ),
            )
        if source == target:
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.NO_STATE_CHANGE,
                    message=f"{kind_label} source and target are identical",
                    category=ErrorCategory.VALIDATION,
                    storage_code=ErrorCode.INVALID_REQUEST,
                    retryability=Retryability.NEVER,
                    state=OperationState.REJECTED,
                    path=source,
                ),
            )
        # Cross-mount classification.
        src_mount_id = operation.source_mount_id or operation.mount_id or _DEFAULT_MOUNT_ID
        dst_mount_id = operation.target_mount_id or operation.mount_id or _DEFAULT_MOUNT_ID
        src_mount = self._mounts.get(src_mount_id, self._default_mount)
        dst_mount = self._mounts.get(dst_mount_id, self._default_mount)
        boundary, disposition = classify_mount_pair(src_mount, dst_mount)
        if disposition is not None and boundary in (
            AtomicBoundary.CROSS_MOUNT,
            AtomicBoundary.CROSS_BACKEND,
            AtomicBoundary.CROSS_NAMESPACE,
        ):
            try:
                assert_atomic_boundary_supported(boundary)
            except VFSUnsupportedError as exc:
                return self._fail(operation, unsupported_to_vfs_error(exc))

        entry = self._storage.get(source)
        if entry is None:
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.NOT_FOUND,
                    message=f"source not found: {source}",
                    category=ErrorCategory.STORAGE,
                    storage_code=ErrorCode.NOT_FOUND,
                    retryability=Retryability.NEVER,
                    state=OperationState.FAILED,
                    path=source,
                ),
            )
        if self._storage.get(target) is not None:
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.ALREADY_EXISTS,
                    message=f"target already exists: {target}",
                    category=ErrorCategory.STORAGE,
                    storage_code=ErrorCode.ALREADY_EXISTS,
                    retryability=Retryability.NEVER,
                    state=OperationState.CONFLICT,
                    path=target,
                ),
            )
        parent_err = self._require_parent_dir(target)
        if parent_err is not None:
            return self._fail(operation, parent_err)
        # Refuse to move a directory into its own descendant.
        if entry.kind is VFSEntryKind.DIRECTORY and (
            target == source or target.startswith(source + "/")
        ):
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.INVALID_PATH,
                    message="cannot move directory into its descendant",
                    category=ErrorCategory.VALIDATION,
                    storage_code=ErrorCode.INVALID_REQUEST,
                    retryability=Retryability.NEVER,
                    state=OperationState.REJECTED,
                    path=target,
                ),
            )
        self._pre_commit(req)
        from_v = entry.version_cid
        gen = self._storage.bump_generation()
        self._storage.rename(source, target)
        # Refresh version identity at target.
        moved = self._storage.get(target)
        assert moved is not None
        new_version = version_cid_for(
            target,
            kind=moved.kind,
            content_cid=moved.content_cid,
            generation=gen,
            target=moved.target,
        )
        self._storage.put(
            target,
            VFSStoredEntry(
                kind=moved.kind,
                content=moved.content,
                content_cid=moved.content_cid,
                version_cid=new_version,
                target=moved.target,
                mtime_unix_ms=req.now_unix_ms or gen,
                mode=moved.mode,
                mount_id=moved.mount_id,
                is_readonly=moved.is_readonly,
            ),
        )
        # Prove mutation: source gone, target present.
        assert self._storage.get(source) is None
        assert self._storage.get(target) is not None
        return self._success_mutating(
            operation,
            from_version_cid=from_v,
            to_version_cid=new_version,
            effect_id=f"effect:{kind_label}:{source}:to:{target}:{gen}",
            resulting_content_cid=moved.content_cid,
            path=target,
            detail={"source": source, "target": target, "mutated": True},
        )

    def _op_cas_write(
        self, operation: VFSOperation, req: VFSExecuteRequest
    ) -> VFSServiceOutcome:
        path = operation.path
        existing = self._storage.get(path)
        if existing is None:
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.NOT_FOUND,
                    message=f"path not found: {path}",
                    category=ErrorCategory.STORAGE,
                    storage_code=ErrorCode.NOT_FOUND,
                    retryability=Retryability.NEVER,
                    state=OperationState.FAILED,
                    path=path,
                ),
            )
        if existing.kind is not VFSEntryKind.FILE:
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.IS_DIRECTORY,
                    message=f"cas_write requires a file: {path}",
                    category=ErrorCategory.VALIDATION,
                    storage_code=ErrorCode.INVALID_REQUEST,
                    retryability=Retryability.NEVER,
                    state=OperationState.REJECTED,
                    path=path,
                ),
            )
        if existing.version_cid != operation.precondition_version_cid:
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.PRECONDITION_FAILED,
                    message="precondition version mismatch",
                    category=ErrorCategory.PRECONDITION,
                    storage_code=ErrorCode.PRECONDITION_FAILED,
                    retryability=Retryability.NEVER,
                    state=OperationState.PRECONDITION_FAILED,
                    path=path,
                ),
            )
        self._pre_commit(req)
        from_v = existing.version_cid
        gen = self._storage.bump_generation()
        cid = operation.content_cid or content_cid_for_bytes(req.payload)
        version = version_cid_for(
            path, kind=VFSEntryKind.FILE, content_cid=cid, generation=gen
        )
        self._storage.put(
            path,
            VFSStoredEntry(
                kind=VFSEntryKind.FILE,
                content=req.payload,
                content_cid=cid,
                version_cid=version,
                mtime_unix_ms=req.now_unix_ms or gen,
                mount_id=existing.mount_id,
            ),
        )
        return self._success_mutating(
            operation,
            from_version_cid=from_v,
            to_version_cid=version,
            effect_id=f"effect:cas:{path}:{gen}",
            resulting_content_cid=cid,
            path=path,
        )

    def _op_mount(
        self, operation: VFSOperation, req: VFSExecuteRequest
    ) -> VFSServiceOutcome:
        mount = req.mount
        if mount is None:
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.MOUNT_ERROR,
                    message="mount operation requires a VFSMount payload",
                    category=ErrorCategory.VALIDATION,
                    storage_code=ErrorCode.INVALID_REQUEST,
                    retryability=Retryability.NEVER,
                    state=OperationState.REJECTED,
                ),
            )
        if mount.mount_id in self._mounts:
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.ALREADY_EXISTS,
                    message=f"mount already registered: {mount.mount_id}",
                    category=ErrorCategory.STORAGE,
                    storage_code=ErrorCode.ALREADY_EXISTS,
                    retryability=Retryability.NEVER,
                    state=OperationState.CONFLICT,
                    mount_id=mount.mount_id,
                ),
            )
        self._pre_commit(req)
        gen = self._storage.bump_generation()
        self._mounts[mount.mount_id] = mount
        # Represent mount point in namespace when path is free.
        path = mount.mount_path
        if path and self._storage.get(path) is None:
            parent_err = self._require_parent_dir(path) if path else None
            if parent_err is None:
                cid = mount.root_content_cid or content_cid_for_bytes(b"")
                version = version_cid_for(
                    path,
                    kind=VFSEntryKind.MOUNT_POINT,
                    content_cid=cid,
                    generation=gen,
                )
                self._storage.put(
                    path,
                    VFSStoredEntry(
                        kind=VFSEntryKind.MOUNT_POINT,
                        content_cid=cid,
                        version_cid=version,
                        mount_id=mount.mount_id,
                        is_readonly=mount.read_only,
                        mtime_unix_ms=gen,
                    ),
                )
                to_v = version
                content_cid = cid
            else:
                to_v = f"sha256:{hashlib.sha256(mount.mount_id.encode()).hexdigest()}"
                content_cid = ""
        else:
            to_v = f"sha256:{hashlib.sha256(f'{mount.mount_id}:{gen}'.encode()).hexdigest()}"
            content_cid = mount.root_content_cid
        return self._success_mutating(
            operation,
            from_version_cid="",
            to_version_cid=to_v,
            effect_id=f"effect:mount:{mount.mount_id}:{gen}",
            resulting_content_cid=content_cid,
            mount_id=mount.mount_id,
            path=path,
            detail={"mount_id": mount.mount_id},
        )

    def _op_unmount(
        self, operation: VFSOperation, req: VFSExecuteRequest
    ) -> VFSServiceOutcome:
        mount_id = operation.mount_id
        if not mount_id or mount_id not in self._mounts:
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.MOUNT_ERROR,
                    message=f"mount not found: {mount_id}",
                    category=ErrorCategory.STORAGE,
                    storage_code=ErrorCode.NOT_FOUND,
                    retryability=Retryability.NEVER,
                    state=OperationState.FAILED,
                    mount_id=mount_id,
                ),
            )
        if mount_id == self._default_mount.mount_id:
            return self._fail(
                operation,
                VFSError(
                    code=VFSErrorCode.PERMISSION_DENIED,
                    message="cannot unmount the default mount",
                    category=ErrorCategory.AUTHORIZATION,
                    storage_code=ErrorCode.FORBIDDEN,
                    retryability=Retryability.NEVER,
                    state=OperationState.AUTHORIZATION_DENIED,
                    mount_id=mount_id,
                ),
            )
        mount = self._mounts[mount_id]
        self._pre_commit(req)
        gen = self._storage.bump_generation()
        from_v = ""
        if mount.mount_path:
            existing = self._storage.get(mount.mount_path)
            if existing is not None and existing.kind is VFSEntryKind.MOUNT_POINT:
                from_v = existing.version_cid
                self._storage.delete(mount.mount_path)
        del self._mounts[mount_id]
        return self._success_mutating(
            operation,
            from_version_cid=from_v,
            to_version_cid="",
            effect_id=f"effect:unmount:{mount_id}:{gen}",
            mount_id=mount_id,
            path=mount.mount_path,
        )

    def _op_resolve(
        self, operation: VFSOperation, req: VFSExecuteRequest
    ) -> VFSServiceOutcome:
        """Resolve a path to a normalized form + stat when present."""

        try:
            norm = normalize_vfs_path(operation.path, policy=self._policy)
        except VFSPathError as exc:
            return self._fail(operation, path_error_to_vfs_error(exc))
        entry = self._storage.get(norm.path)
        stat = self._entry_to_stat(norm.path, entry) if entry is not None else None
        if entry is None:
            # Resolve still succeeds with observation when path is valid but
            # missing — callers use NOT_FOUND via STAT. RESOLVE reports the
            # normalized path identity.
            obs = self._next_obs("obs-resolve")
            # Empty synthetic stat is not used; use observation-only success.
            result = make_read_success(
                operation,
                observation_id=obs,
                mount_id=operation.mount_id or _DEFAULT_MOUNT_ID,
            )
            event = VFSEvent(
                kind=VFSEventKind.SUCCESS,
                operation_id=operation.operation_id,
                op_kind=operation.kind.value,
                code="resolved_missing",
                path=norm.path,
                detail={"exists": False, "normalized": norm.path},
            )
            self._emit(event)
            return VFSServiceOutcome(
                result=result,
                events=(event,),
                namespace_generation=self._storage.generation,
                namespace_snapshot=self._storage.snapshot(),
            )
        return self._success_read(
            operation,
            stat=stat,
            detail={"exists": True, "normalized": norm.path},
        )


# ---------------------------------------------------------------------------
# Helpers for building operations (tests / callers)
# ---------------------------------------------------------------------------


def make_op(
    kind: VFSOperationKind | str,
    *,
    operation_id: str,
    path: str = "",
    source_path: str = "",
    target_path: str = "",
    mount_id: str = "",
    source_mount_id: str = "",
    target_mount_id: str = "",
    precondition_version_cid: str = "",
    content_cid: str = "",
    range_start: int = 0,
    range_end: int = 0,
    atomic_boundary: AtomicBoundary = AtomicBoundary.SINGLE_MOUNT,
    request_id: str = "",
    idempotency_key: str = "",
    namespace_id: str = "",
) -> VFSOperation:
    """Build a validated VFSOperation (convenience for callers/tests)."""

    return VFSOperation(
        operation_id=operation_id,
        kind=kind,
        path=path,
        source_path=source_path,
        target_path=target_path,
        mount_id=mount_id,
        source_mount_id=source_mount_id,
        target_mount_id=target_mount_id,
        namespace_id=namespace_id,
        precondition_version_cid=precondition_version_cid,
        content_cid=content_cid,
        range_start=range_start,
        range_end=range_end,
        atomic_boundary=atomic_boundary,
        request_id=request_id,
        idempotency_key=idempotency_key,
    )


__all__ = [
    "SERVICE_CONTRACT_VERSION",
    "SERVICE_SCHEMA_VERSION",
    "CANONICAL_VFS_SERVICE_SCHEMA",
    "CanonicalVFSService_V1",
    "MAX_PAYLOAD_BYTES",
    "MAX_STREAM_CHUNK_BYTES",
    "MAX_STREAM_CHUNKS",
    "MAX_NAMESPACE_ENTRIES",
    "MAX_TRACE_STEPS",
    "VFSEventKind",
    "VFSEvent",
    "CancellationToken",
    "VFSCancelledError",
    "VFSDeadlineExceededError",
    "VFSServiceError",
    "VFSStoredEntry",
    "VFSStorageBoundary",
    "InMemoryVFSStorage",
    "VFSServiceOutcome",
    "VFSExecuteRequest",
    "CanonicalVFSService",
    "content_cid_for_bytes",
    "version_cid_for",
    "make_op",
]
