"""VFS reference model — pure deterministic state machine (KITA-006).

``VFSReferenceModel@1`` is an independent oracle for the canonical VFS
service. It applies the same closed operation vocabulary and produces
differential traces that the service must match:

* full CRUD, directories, streams/ranges, rename/move, versions, errors;
* failure never emits a success event;
* rename/move always mutates the namespace on success;
* return and error types are the stable contract types;
* operations are bounded and cancellation/deadline aware;
* no side effects outside the model's own in-memory namespace.

The reference model does **not** import :class:`CanonicalVFSService`. Shared
helpers (CID hashing, path policy) come only from contracts / pure utils
mirrored here for content identity alignment.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar, Final

from ipfs_kit_py.core.operation_contracts import (
    ErrorCategory,
    ErrorCode,
    OperationState,
    Retryability,
)
from ipfs_kit_py.core.vfs.contracts import (
    MAX_LISTING_PAGE_SIZE,
    MUTATING_OPERATIONS,
    AtomicBoundary,
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
from ipfs_kit_py.core.vfs.service import (
    MAX_NAMESPACE_ENTRIES,
    MAX_PAYLOAD_BYTES,
    MAX_STREAM_CHUNK_BYTES,
    MAX_STREAM_CHUNKS,
    MAX_TRACE_STEPS,
    CancellationToken,
    VFSEvent,
    VFSEventKind,
    VFSExecuteRequest,
    VFSServiceOutcome,
    content_cid_for_bytes,
    version_cid_for,
)

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

REFERENCE_MODEL_CONTRACT_VERSION: Final[int] = 1
REFERENCE_MODEL_SCHEMA: Final[str] = (
    f"ipfs_kit_py/runtime-readiness/vfs/reference-model@{REFERENCE_MODEL_CONTRACT_VERSION}"
)
VFSReferenceModel_V1: Final[str] = REFERENCE_MODEL_SCHEMA

_DEFAULT_MOUNT_ID: Final[str] = "mount:default"
_DEFAULT_NAMESPACE_ID: Final[str] = "ns:default"
_DEFAULT_BACKEND_ID: Final[str] = "backend:memory"
DEFAULT_PAGE_SIZE: Final[int] = 256


@dataclass(frozen=True)
class RefEntry:
    """One namespace entry in the pure reference model."""

    kind: VFSEntryKind
    content: bytes = b""
    content_cid: str = ""
    version_cid: str = ""
    target: str = ""
    mtime_unix_ms: int = 0
    mode: int = 0
    mount_id: str = _DEFAULT_MOUNT_ID
    is_readonly: bool = False

    def public(self) -> dict[str, Any]:
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


class VFSReferenceModel:
    """Pure deterministic VFS state machine (``VFSReferenceModel@1``).

    Independent of the service implementation path except for shared CID
    helpers and the common outcome/event record shapes used for differential
    comparison.
    """

    SCHEMA: ClassVar[str] = REFERENCE_MODEL_SCHEMA
    CONTRACT_VERSION: ClassVar[int] = REFERENCE_MODEL_CONTRACT_VERSION

    def __init__(
        self,
        *,
        path_policy: VFSPathPolicy | None = None,
        max_payload_bytes: int = MAX_PAYLOAD_BYTES,
        max_entries: int = MAX_NAMESPACE_ENTRIES,
        clock_ms: int = 0,
    ) -> None:
        self._policy = path_policy or VFSPathPolicy.default()
        self._max_payload = max_payload_bytes
        self._max_entries = max_entries
        self._clock_ms = clock_ms
        self._generation = 0
        self._obs_seq = 0
        self._entries: dict[str, RefEntry] = {
            "": RefEntry(
                kind=VFSEntryKind.DIRECTORY,
                content_cid=content_cid_for_bytes(b""),
                version_cid=version_cid_for(
                    "", kind=VFSEntryKind.DIRECTORY, content_cid="", generation=0
                ),
            )
        }
        self._default_mount = VFSMount(
            mount_id=_DEFAULT_MOUNT_ID,
            mount_path="",
            backend_id=_DEFAULT_BACKEND_ID,
            namespace_id=_DEFAULT_NAMESPACE_ID,
            read_only=False,
            atomic_boundary=AtomicBoundary.SINGLE_MOUNT,
        )
        self._mounts: dict[str, VFSMount] = {
            self._default_mount.mount_id: self._default_mount
        }
        self._event_log: list[VFSEvent] = []
        self._idempotency: dict[str, VFSServiceOutcome] = {}

    # -- inspection ---------------------------------------------------------

    @property
    def generation(self) -> int:
        return self._generation

    @property
    def event_log(self) -> tuple[VFSEvent, ...]:
        return tuple(self._event_log)

    def snapshot(self) -> dict[str, dict[str, Any]]:
        return {path: entry.public() for path, entry in sorted(self._entries.items())}

    def get(self, path: str) -> RefEntry | None:
        path = normalize_vfs_path(path).path if path else ""
        return self._entries.get(path)

    def seed(
        self,
        path: str,
        *,
        kind: VFSEntryKind = VFSEntryKind.FILE,
        content: bytes = b"",
        target: str = "",
        mount_id: str = _DEFAULT_MOUNT_ID,
        ensure_parents: bool = True,
    ) -> RefEntry:
        path = normalize_vfs_path(path).path if path else ""
        if ensure_parents and path:
            self._ensure_parents(path)
        self._generation += 1
        cid = content_cid_for_bytes(content) if kind is VFSEntryKind.FILE else content_cid_for_bytes(b"")
        entry = RefEntry(
            kind=kind,
            content=content if kind is VFSEntryKind.FILE else b"",
            content_cid=cid,
            version_cid=version_cid_for(
                path, kind=kind, content_cid=cid, generation=self._generation, target=target
            ),
            target=target,
            mtime_unix_ms=self._generation,
            mount_id=mount_id,
        )
        self._put(path, entry)
        return entry

    # -- execution ----------------------------------------------------------

    def apply(
        self,
        operation: VFSOperation,
        request: VFSExecuteRequest | None = None,
    ) -> VFSServiceOutcome:
        """Apply one operation and return a service-compatible outcome."""

        req = request or VFSExecuteRequest()
        try:
            return self._apply_inner(operation, req)
        except _Cancel:
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
        except _Deadline:
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

    def run_trace(
        self,
        operations: Sequence[tuple[VFSOperation, VFSExecuteRequest | None]],
    ) -> list[dict[str, Any]]:
        if len(operations) > MAX_TRACE_STEPS:
            raise ValueError(f"trace exceeds MAX_TRACE_STEPS ({MAX_TRACE_STEPS})")
        steps: list[dict[str, Any]] = []
        for index, item in enumerate(operations):
            op, req = item if isinstance(item, tuple) else (item, None)
            outcome = self.apply(op, req)
            steps.append(outcome.trace_step_record(index, op))
            if not outcome.success and outcome.result.state in (
                OperationState.CANCELLED,
                OperationState.DEADLINE_EXCEEDED,
            ):
                break
        return steps

    def clone_state_from_snapshot(self, snapshot: Mapping[str, Mapping[str, Any]]) -> None:
        """Replace namespace from a public snapshot (content bodies empty)."""

        self._entries.clear()
        for path, rec in snapshot.items():
            kind = VFSEntryKind(rec["kind"])
            self._entries[path] = RefEntry(
                kind=kind,
                content=b"",
                content_cid=str(rec.get("content_cid") or ""),
                version_cid=str(rec.get("version_cid") or ""),
                target=str(rec.get("target") or ""),
                mtime_unix_ms=int(rec.get("mtime_unix_ms") or 0),
                mode=int(rec.get("mode") or 0),
                mount_id=str(rec.get("mount_id") or _DEFAULT_MOUNT_ID),
                is_readonly=bool(rec.get("is_readonly") or False),
            )
        if "" not in self._entries:
            self._entries[""] = RefEntry(kind=VFSEntryKind.DIRECTORY)

    # -- internals ----------------------------------------------------------

    def _apply_inner(
        self, operation: VFSOperation, req: VFSExecuteRequest
    ) -> VFSServiceOutcome:
        self._check_cancel_deadline(req)
        if operation.idempotency_key and operation.idempotency_key in self._idempotency:
            return self._idempotency[operation.idempotency_key]

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

        for attr in ("path", "source_path", "target_path"):
            value = getattr(operation, attr)
            if value:
                normalize_vfs_path(value, policy=self._policy)

        if operation.kind in MUTATING_OPERATIONS:
            try:
                assert_atomic_boundary_supported(operation.atomic_boundary)
            except VFSUnsupportedError as exc:
                return self._fail(operation, unsupported_to_vfs_error(exc))

        mount = self._mounts.get(
            operation.mount_id or _DEFAULT_MOUNT_ID, self._default_mount
        )
        if operation.kind in MUTATING_OPERATIONS and mount.read_only:
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

        dispatch = {
            VFSOperationKind.STAT: self._stat,
            VFSOperationKind.LIST: self._list,
            VFSOperationKind.READ: self._read,
            VFSOperationKind.RANGE_READ: self._range_read,
            VFSOperationKind.STREAM: self._stream,
            VFSOperationKind.CREATE: self._create,
            VFSOperationKind.REPLACE: self._replace,
            VFSOperationKind.MKDIR: self._mkdir,
            VFSOperationKind.RMDIR: self._rmdir,
            VFSOperationKind.RENAME: self._rename,
            VFSOperationKind.MOVE: self._move,
            VFSOperationKind.DELETE: self._delete,
            VFSOperationKind.CAS_WRITE: self._cas,
            VFSOperationKind.MOUNT: self._mount,
            VFSOperationKind.UNMOUNT: self._unmount,
            VFSOperationKind.RESOLVE: self._resolve,
        }
        handler = dispatch.get(operation.kind)
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
        if operation.idempotency_key:
            self._idempotency[operation.idempotency_key] = outcome
        return outcome

    def _check_cancel_deadline(self, req: VFSExecuteRequest) -> None:
        if req.cancel is not None and req.cancel.is_cancelled:
            raise _Cancel()
        now = req.now_unix_ms if req.now_unix_ms else self._clock_ms
        if req.deadline_unix_ms and now > req.deadline_unix_ms:
            raise _Deadline()

    def _pre_commit(self, req: VFSExecuteRequest) -> None:
        self._check_cancel_deadline(req)

    def _next_obs(self, prefix: str = "obs") -> str:
        self._obs_seq += 1
        return f"{prefix}:{self._obs_seq}"

    def _put(self, path: str, entry: RefEntry) -> None:
        if path not in self._entries and len(self._entries) >= self._max_entries:
            raise ValueError("namespace entry bound exceeded")
        self._entries[path] = entry

    def _drop_entry(self, path: str) -> None:
        if path == "":
            raise ValueError("cannot delete root")
        self._entries.pop(path, None)

    def _children(self, path: str) -> tuple[str, ...]:
        prefix = "" if path == "" else path + "/"
        names: set[str] = set()
        for key in self._entries:
            if key == path or key == "":
                continue
            if path == "":
                if "/" not in key:
                    names.add(key)
                else:
                    names.add(key.split("/", 1)[0])
            elif key.startswith(prefix):
                rest = key[len(prefix) :]
                if rest:
                    names.add(rest.split("/", 1)[0])
        return tuple(sorted(names, key=lambda n: n.encode("utf-8")))

    def _rename_keys(self, source: str, target: str) -> None:
        moves: list[tuple[str, str, RefEntry]] = []
        for key, entry in list(self._entries.items()):
            if key == source or key.startswith(source + "/"):
                suffix = key[len(source) :]
                moves.append((key, target + suffix, entry))
        for old, _new, _e in moves:
            del self._entries[old]
        for _old, new, entry in moves:
            self._put(new, entry)

    def _parent(self, path: str) -> str:
        if not path or "/" not in path:
            return ""
        return path.rsplit("/", 1)[0]

    def _require_parent_dir(self, path: str) -> VFSError | None:
        parent = self._parent(path)
        entry = self._entries.get(parent)
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

    def _ensure_parents(self, path: str) -> None:
        segments = path.split("/") if path else []
        acc: list[str] = []
        for seg in segments[:-1]:
            acc.append(seg)
            parent = "/".join(acc)
            existing = self._entries.get(parent)
            if existing is None:
                self._put(
                    parent,
                    RefEntry(
                        kind=VFSEntryKind.DIRECTORY,
                        content_cid=content_cid_for_bytes(b""),
                        version_cid=version_cid_for(
                            parent,
                            kind=VFSEntryKind.DIRECTORY,
                            content_cid="",
                            generation=self._generation,
                        ),
                    ),
                )
            elif existing.kind is not VFSEntryKind.DIRECTORY:
                raise ValueError(f"parent {parent!r} is not a directory")

    def _to_stat(self, path: str, entry: RefEntry) -> VFSStat:
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
            generation_id=f"gen:{self._generation}",
            observed=True,
            is_readonly=entry.is_readonly,
        )

    def _success_mut(
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
        if path:
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
        self._event_log.append(event)
        return VFSServiceOutcome(
            result=result,
            data=data,
            chunks=chunks,
            events=(event,),
            namespace_generation=self._generation,
            namespace_snapshot=self.snapshot(),
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
        obs_event = VFSEvent(
            kind=VFSEventKind.OBSERVATION,
            operation_id=operation.operation_id,
            op_kind=operation.kind.value,
            code=obs,
            path=operation.path,
        )
        self._event_log.append(event)
        self._event_log.append(obs_event)
        return VFSServiceOutcome(
            result=result,
            data=data,
            chunks=chunks,
            events=(event, obs_event),
            namespace_generation=self._generation,
            namespace_snapshot=self.snapshot(),
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
        self._event_log.append(event)
        assert event.kind is not VFSEventKind.SUCCESS
        assert not result.success
        return VFSServiceOutcome(
            result=result,
            events=(event,),
            namespace_generation=self._generation,
            namespace_snapshot=self.snapshot(),
        )

    # -- ops ----------------------------------------------------------------

    def _stat(self, operation: VFSOperation, req: VFSExecuteRequest) -> VFSServiceOutcome:
        path = operation.path
        entry = self._entries.get(path)
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
        return self._success_read(operation, stat=self._to_stat(path, entry))

    def _list(self, operation: VFSOperation, req: VFSExecuteRequest) -> VFSServiceOutcome:
        path = operation.path
        entry = self._entries.get(path)
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
        names = list(self._children(path))
        if req.cursor:
            try:
                start = names.index(req.cursor) + 1
            except ValueError:
                start = 0
            names = names[start:]
        entries: list[VFSDirEntry] = []
        for name in names:
            child_path = name if path == "" else f"{path}/{name}"
            child = self._entries.get(child_path)
            if child is None:
                child_kind = VFSEntryKind.DIRECTORY
                stat = VFSStat(
                    path=child_path,
                    kind=child_kind,
                    generation_id=f"gen:{self._generation}",
                    observed=True,
                    mount_id=operation.mount_id or _DEFAULT_MOUNT_ID,
                )
            else:
                child_kind = child.kind
                stat = self._to_stat(child_path, child)
            entries.append(VFSDirEntry(name=name, kind=child_kind, stat=stat))
        listing = VFSListing.from_entries(
            path,
            entries,
            cursor=req.cursor,
            page_size=page_size if page_size else len(entries),
            generation_id=f"gen:{self._generation}",
            mount_id=operation.mount_id or _DEFAULT_MOUNT_ID,
        )
        return self._success_read(operation, listing=listing)

    def _read(self, operation: VFSOperation, req: VFSExecuteRequest) -> VFSServiceOutcome:
        path = operation.path
        entry = self._entries.get(path)
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
            stat=self._to_stat(path, entry),
            data=entry.content,
            detail={"bytes": len(entry.content)},
        )

    def _range_read(
        self, operation: VFSOperation, req: VFSExecuteRequest
    ) -> VFSServiceOutcome:
        path = operation.path
        entry = self._entries.get(path)
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
            stat=self._to_stat(path, entry),
            data=data,
            detail={"range_start": start, "range_end": end, "bytes": len(data)},
        )

    def _stream(self, operation: VFSOperation, req: VFSExecuteRequest) -> VFSServiceOutcome:
        path = operation.path
        entry = self._entries.get(path)
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
            stat=self._to_stat(path, entry),
            data=data,
            chunks=tuple(chunks),
            detail={"chunk_count": len(chunks), "bytes": len(data)},
        )

    def _create(self, operation: VFSOperation, req: VFSExecuteRequest) -> VFSServiceOutcome:
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
        if path in self._entries:
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
        self._generation += 1
        gen = self._generation
        cid = operation.content_cid or content_cid_for_bytes(req.payload)
        version = version_cid_for(
            path, kind=VFSEntryKind.FILE, content_cid=cid, generation=gen
        )
        self._put(
            path,
            RefEntry(
                kind=VFSEntryKind.FILE,
                content=req.payload,
                content_cid=cid,
                version_cid=version,
                mtime_unix_ms=req.now_unix_ms or gen,
                mount_id=operation.mount_id or _DEFAULT_MOUNT_ID,
            ),
        )
        return self._success_mut(
            operation,
            from_version_cid="",
            to_version_cid=version,
            effect_id=f"effect:create:{path}:{gen}",
            resulting_content_cid=cid,
            path=path,
            detail={"created": path},
        )

    def _replace(self, operation: VFSOperation, req: VFSExecuteRequest) -> VFSServiceOutcome:
        path = operation.path
        existing = self._entries.get(path)
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
        self._generation += 1
        gen = self._generation
        cid = operation.content_cid or content_cid_for_bytes(req.payload)
        version = version_cid_for(
            path, kind=VFSEntryKind.FILE, content_cid=cid, generation=gen
        )
        self._put(
            path,
            RefEntry(
                kind=VFSEntryKind.FILE,
                content=req.payload,
                content_cid=cid,
                version_cid=version,
                mtime_unix_ms=req.now_unix_ms or gen,
                mount_id=existing.mount_id,
            ),
        )
        return self._success_mut(
            operation,
            from_version_cid=from_v,
            to_version_cid=version,
            effect_id=f"effect:replace:{path}:{gen}",
            resulting_content_cid=cid,
            path=path,
        )

    def _mkdir(self, operation: VFSOperation, req: VFSExecuteRequest) -> VFSServiceOutcome:
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
        if path in self._entries:
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
        self._generation += 1
        gen = self._generation
        cid = content_cid_for_bytes(b"")
        version = version_cid_for(
            path, kind=VFSEntryKind.DIRECTORY, content_cid=cid, generation=gen
        )
        self._put(
            path,
            RefEntry(
                kind=VFSEntryKind.DIRECTORY,
                content_cid=cid,
                version_cid=version,
                mtime_unix_ms=req.now_unix_ms or gen,
                mount_id=operation.mount_id or _DEFAULT_MOUNT_ID,
            ),
        )
        return self._success_mut(
            operation,
            from_version_cid="",
            to_version_cid=version,
            effect_id=f"effect:mkdir:{path}:{gen}",
            resulting_content_cid=cid,
            path=path,
        )

    def _rmdir(self, operation: VFSOperation, req: VFSExecuteRequest) -> VFSServiceOutcome:
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
        entry = self._entries.get(path)
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
        if self._children(path):
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
        self._generation += 1
        gen = self._generation
        self._drop_entry(path)
        return self._success_mut(
            operation,
            from_version_cid=from_v,
            to_version_cid="",
            effect_id=f"effect:rmdir:{path}:{gen}",
            path=path,
        )

    def _delete(self, operation: VFSOperation, req: VFSExecuteRequest) -> VFSServiceOutcome:
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
        entry = self._entries.get(path)
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
        if entry.kind is VFSEntryKind.DIRECTORY and self._children(path):
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
        self._generation += 1
        gen = self._generation
        self._drop_entry(path)
        return self._success_mut(
            operation,
            from_version_cid=from_v,
            to_version_cid="",
            effect_id=f"effect:delete:{path}:{gen}",
            path=path,
        )

    def _rename(self, operation: VFSOperation, req: VFSExecuteRequest) -> VFSServiceOutcome:
        return self._rename_or_move(operation, req, "rename")

    def _move(self, operation: VFSOperation, req: VFSExecuteRequest) -> VFSServiceOutcome:
        return self._rename_or_move(operation, req, "move")

    def _rename_or_move(
        self, operation: VFSOperation, req: VFSExecuteRequest, kind_label: str
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
        src_mount_id = operation.source_mount_id or operation.mount_id or _DEFAULT_MOUNT_ID
        dst_mount_id = operation.target_mount_id or operation.mount_id or _DEFAULT_MOUNT_ID
        src_mount = self._mounts.get(src_mount_id, self._default_mount)
        dst_mount = self._mounts.get(dst_mount_id, self._default_mount)
        boundary, _disp = classify_mount_pair(src_mount, dst_mount)
        if boundary in (
            AtomicBoundary.CROSS_MOUNT,
            AtomicBoundary.CROSS_BACKEND,
            AtomicBoundary.CROSS_NAMESPACE,
        ):
            try:
                assert_atomic_boundary_supported(boundary)
            except VFSUnsupportedError as exc:
                return self._fail(operation, unsupported_to_vfs_error(exc))

        entry = self._entries.get(source)
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
        if target in self._entries:
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
        self._generation += 1
        gen = self._generation
        self._rename_keys(source, target)
        moved = self._entries[target]
        new_version = version_cid_for(
            target,
            kind=moved.kind,
            content_cid=moved.content_cid,
            generation=gen,
            target=moved.target,
        )
        self._put(
            target,
            RefEntry(
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
        assert source not in self._entries
        assert target in self._entries
        return self._success_mut(
            operation,
            from_version_cid=from_v,
            to_version_cid=new_version,
            effect_id=f"effect:{kind_label}:{source}:to:{target}:{gen}",
            resulting_content_cid=moved.content_cid,
            path=target,
            detail={"source": source, "target": target, "mutated": True},
        )

    def _cas(self, operation: VFSOperation, req: VFSExecuteRequest) -> VFSServiceOutcome:
        path = operation.path
        existing = self._entries.get(path)
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
        self._generation += 1
        gen = self._generation
        cid = operation.content_cid or content_cid_for_bytes(req.payload)
        version = version_cid_for(
            path, kind=VFSEntryKind.FILE, content_cid=cid, generation=gen
        )
        self._put(
            path,
            RefEntry(
                kind=VFSEntryKind.FILE,
                content=req.payload,
                content_cid=cid,
                version_cid=version,
                mtime_unix_ms=req.now_unix_ms or gen,
                mount_id=existing.mount_id,
            ),
        )
        return self._success_mut(
            operation,
            from_version_cid=from_v,
            to_version_cid=version,
            effect_id=f"effect:cas:{path}:{gen}",
            resulting_content_cid=cid,
            path=path,
        )

    def _mount(self, operation: VFSOperation, req: VFSExecuteRequest) -> VFSServiceOutcome:
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
        self._generation += 1
        gen = self._generation
        self._mounts[mount.mount_id] = mount
        path = mount.mount_path
        if path and path not in self._entries:
            parent_err = self._require_parent_dir(path) if path else None
            if parent_err is None:
                cid = mount.root_content_cid or content_cid_for_bytes(b"")
                version = version_cid_for(
                    path,
                    kind=VFSEntryKind.MOUNT_POINT,
                    content_cid=cid,
                    generation=gen,
                )
                self._put(
                    path,
                    RefEntry(
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
        return self._success_mut(
            operation,
            from_version_cid="",
            to_version_cid=to_v,
            effect_id=f"effect:mount:{mount.mount_id}:{gen}",
            resulting_content_cid=content_cid,
            mount_id=mount.mount_id,
            path=path,
            detail={"mount_id": mount.mount_id},
        )

    def _unmount(self, operation: VFSOperation, req: VFSExecuteRequest) -> VFSServiceOutcome:
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
        self._generation += 1
        gen = self._generation
        from_v = ""
        if mount.mount_path:
            existing = self._entries.get(mount.mount_path)
            if existing is not None and existing.kind is VFSEntryKind.MOUNT_POINT:
                from_v = existing.version_cid
                self._drop_entry(mount.mount_path)
        del self._mounts[mount_id]
        return self._success_mut(
            operation,
            from_version_cid=from_v,
            to_version_cid="",
            effect_id=f"effect:unmount:{mount_id}:{gen}",
            mount_id=mount_id,
            path=mount.mount_path,
        )

    def _resolve(self, operation: VFSOperation, req: VFSExecuteRequest) -> VFSServiceOutcome:
        try:
            norm = normalize_vfs_path(operation.path, policy=self._policy)
        except VFSPathError as exc:
            return self._fail(operation, path_error_to_vfs_error(exc))
        entry = self._entries.get(norm.path)
        if entry is None:
            obs = self._next_obs("obs-resolve")
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
            self._event_log.append(event)
            return VFSServiceOutcome(
                result=result,
                events=(event,),
                namespace_generation=self._generation,
                namespace_snapshot=self.snapshot(),
            )
        return self._success_read(
            operation,
            stat=self._to_stat(norm.path, entry),
            detail={"exists": True, "normalized": norm.path},
        )


class _Cancel(Exception):
    pass


class _Deadline(Exception):
    pass


def canonical_trace_step(step: Mapping[str, Any]) -> dict[str, Any]:
    """Project a trace step to fields used for service↔reference equality.

    Observation IDs and absolute event codes that embed sequence numbers may
    differ; comparison uses semantic fields only.
    """

    return {
        "index": step["index"],
        "kind": step["kind"],
        "path": step.get("path") or "",
        "source_path": step.get("source_path") or "",
        "target_path": step.get("target_path") or "",
        "success": step["success"],
        "state": step["state"],
        "error_code": step.get("error_code"),
        "resulting_content_cid": step.get("resulting_content_cid") or "",
        "resulting_version_cid": step.get("resulting_version_cid") or "",
        "event_kinds": list(step.get("event_kinds") or []),
        "namespace": step.get("namespace") or {},
        "data_size": step.get("data_size") or 0,
        "chunk_count": step.get("chunk_count") or 0,
    }


def traces_match(
    service_trace: Sequence[Mapping[str, Any]],
    reference_trace: Sequence[Mapping[str, Any]],
) -> bool:
    """Return True when differential traces agree on semantic fields."""

    if len(service_trace) != len(reference_trace):
        return False
    for left, right in zip(service_trace, reference_trace):
        if canonical_trace_step(left) != canonical_trace_step(right):
            return False
    return True


__all__ = [
    "REFERENCE_MODEL_CONTRACT_VERSION",
    "REFERENCE_MODEL_SCHEMA",
    "VFSReferenceModel_V1",
    "RefEntry",
    "VFSReferenceModel",
    "canonical_trace_step",
    "traces_match",
]
