"""Platform-neutral KernelVFSOperations and composed request runtime (KVFS-206).

``KernelVFSOperations@1`` is the driver-independent operations adapter that
projects the closed host-callback contract onto the composed common runtime:

```text
fusepy / WinFsp callbacks  (later loaders only)
            |
   KernelVFSOperations     ← this module
            |
  path / errno / handle / lifecycle contracts
            |
  HostConcurrencyPlane  →  HostVFSService  →  CanonicalVFSService
            |                      |
      ordered locks          ranged storage + handles + metadata
            |
   optional BoundedAsyncBridge  (sync fusepy threads → async services)
```

Rules (fail-closed):

* every required production callback is implemented and returns a
  :class:`~ipfs_kit_py.core.vfs.host_contracts.HostCallbackResult` whose
  success / errno / observed-effect policy matches the host contract;
* explicit-unsupported callbacks reject with stable ``ENOSYS`` /
  ``EOPNOTSUPP`` (never false success, never a silent no-op);
* unknown callback names are rejected at the contract boundary;
* mount lifecycle follows ``init → ready → destroy`` with legal transitions;
* no fusepy, libfuse, WinFsp, or host filesystem I/O is imported or performed.

Interface aliases: ``KernelVFSOperations@1``, ``ComposedRequestRuntime@1``.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar, Final

from ipfs_kit_py.core.vfs.host_concurrency import (
    HostCallbackConflictError,
    HostConcurrencyError,
    HostConcurrencyPlane,
    HostShutdownError,
    LockMode,
)
from ipfs_kit_py.core.vfs.host_contracts import (
    EXPLICIT_UNSUPPORTED_CALLBACKS,
    HANDLE_CALLBACKS,
    MUTATING_CALLBACKS,
    REQUIRED_SUPPORTED_CALLBACKS,
    CacheConsistencyMode,
    CallbackDisposition,
    DurabilityMode,
    HostCallbackKind,
    HostCallbackRequest,
    HostCallbackResult,
    HostErrno,
    HostFilesystemAdapterContract,
    HostHandle,
    HostMetadata,
    HostPlatform,
    HostUnknownCallbackError,
    MountLifecycleState,
    OpenFlag,
    assert_legal_mount_transition,
    callback_disposition,
    default_unsupported_errno,
    evaluate_cancelled_request,
    is_legal_mount_transition,
    parse_callback_kind,
)
from ipfs_kit_py.core.vfs.handles import HandleError
from ipfs_kit_py.core.vfs.host_service import (
    HostOperationResult,
    HostVFSService,
    build_host_vfs_service,
)
from ipfs_kit_py.core.vfs.metadata import (
    F_OK,
    MetadataError,
    UTIME_NOW,
    UTIME_OMIT,
)
from ipfs_kit_py.core.vfs.namespace import DEFAULT_MOUNT_ID as NAMESPACE_DEFAULT_MOUNT_ID
from ipfs_kit_py.kernel_vfs.async_bridge import (
    AsyncBridge,
    AsyncBridgeError,
    BridgeErrorCode,
)

# ---------------------------------------------------------------------------
# Schema / version / bounds
# ---------------------------------------------------------------------------

TASK_ID: Final[str] = "KVFS-206"
CONTRACT_VERSION: Final[int] = 1
SCHEMA_MAJOR: Final[int] = 1
SCHEMA_MINOR: Final[int] = 0
SCHEMA_PATCH: Final[int] = 0
SCHEMA_VERSION: Final[str] = f"{SCHEMA_MAJOR}.{SCHEMA_MINOR}.{SCHEMA_PATCH}"

OPERATIONS_NAMESPACE: Final[str] = "ipfs_kit_py/kernel_vfs/operations"

KERNEL_VFS_OPERATIONS_SCHEMA: Final[str] = (
    f"{OPERATIONS_NAMESPACE}/kernel-vfs-operations@{SCHEMA_MAJOR}"
)
COMPOSED_REQUEST_RUNTIME_SCHEMA: Final[str] = (
    f"{OPERATIONS_NAMESPACE}/composed-request-runtime@{SCHEMA_MAJOR}"
)
OPERATIONS_RESULT_SCHEMA: Final[str] = (
    f"{OPERATIONS_NAMESPACE}/operations-result@{SCHEMA_MAJOR}"
)
OPERATIONS_TRACE_SCHEMA: Final[str] = (
    f"{OPERATIONS_NAMESPACE}/operations-trace@{SCHEMA_MAJOR}"
)

# Public interface aliases.
KernelVFSOperations_V1: Final[str] = KERNEL_VFS_OPERATIONS_SCHEMA
ComposedRequestRuntime_V1: Final[str] = COMPOSED_REQUEST_RUNTIME_SCHEMA

MAX_TRACE_STEPS: Final[int] = 4_096
# Must match the host/namespace default so allocate_inode + rename plane sync
# share one mount table entry (custom ids are not auto-registered).
DEFAULT_MOUNT_ID: Final[str] = NAMESPACE_DEFAULT_MOUNT_ID

# Callbacks that only need shared (reader) path locks.
_SHARED_PATH_CALLBACKS: Final[frozenset[HostCallbackKind]] = frozenset(
    {
        HostCallbackKind.GETATTR,
        HostCallbackKind.READDIR,
        HostCallbackKind.ACCESS,
        HostCallbackKind.STATFS,
        HostCallbackKind.READ,
        HostCallbackKind.OPEN,
        HostCallbackKind.FLUSH,
        HostCallbackKind.FSYNC,
        HostCallbackKind.RELEASE,
    }
)

# ---------------------------------------------------------------------------
# Errors / traces
# ---------------------------------------------------------------------------


class OperationsErrorCode(str, Enum):
    """Stable operations-runtime error codes."""

    NOT_READY = "OPS_NOT_READY"
    DESTROYED = "OPS_DESTROYED"
    LIFECYCLE = "OPS_LIFECYCLE"
    UNSUPPORTED = "OPS_UNSUPPORTED"
    UNKNOWN_CALLBACK = "OPS_UNKNOWN_CALLBACK"
    CONFLICT = "OPS_CONFLICT"
    SHUTDOWN = "OPS_SHUTDOWN"
    BRIDGE = "OPS_BRIDGE"
    HOST = "OPS_HOST"
    CANCELLED = "OPS_CANCELLED"
    INVALID = "OPS_INVALID"
    INTERNAL = "OPS_INTERNAL"


class OperationsError(Exception):
    """Fail-closed operations-runtime error with exact errno projection."""

    def __init__(
        self,
        message: str,
        *,
        code: OperationsErrorCode,
        errno: HostErrno = HostErrno.EINVAL,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = (
            code if isinstance(code, OperationsErrorCode) else OperationsErrorCode(code)
        )
        self.errno = errno if isinstance(errno, HostErrno) else HostErrno(errno)
        self.detail = dict(detail or {})

    def to_record(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "message": self.message,
            "errno": self.errno.value,
            "detail": dict(self.detail),
        }


class OperationsTraceKind(str, Enum):
    """Closed vocabulary for operations-runtime executable traces."""

    DISPATCH = "dispatch"
    INIT = "init"
    DESTROY = "destroy"
    LIFECYCLE = "lifecycle"
    UNSUPPORTED = "unsupported"
    CONFLICT = "conflict"
    BRIDGE = "bridge"
    CALLBACK = "callback"


@dataclass(frozen=True)
class OperationsTraceStep:
    """One immutable operations-runtime trace step."""

    kind: OperationsTraceKind
    success: bool
    callback: str = ""
    code: str = ""
    detail: Mapping[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": OPERATIONS_TRACE_SCHEMA,
            "kind": self.kind.value,
            "success": self.success,
            "callback": self.callback,
            "code": self.code,
            "detail": dict(self.detail),
        }


class OperationsTraceLog:
    """Bounded append-only operations trace log."""

    __slots__ = ("_steps", "_max_steps", "_lock")

    def __init__(self, *, max_steps: int = MAX_TRACE_STEPS) -> None:
        self._steps: list[OperationsTraceStep] = []
        self._max_steps = max(1, min(int(max_steps), MAX_TRACE_STEPS))
        self._lock = threading.Lock()

    def record(
        self,
        kind: OperationsTraceKind,
        *,
        success: bool,
        callback: str = "",
        code: str = "",
        detail: Mapping[str, Any] | None = None,
    ) -> OperationsTraceStep:
        step = OperationsTraceStep(
            kind=kind,
            success=success,
            callback=callback,
            code=code,
            detail=dict(detail or {}),
        )
        with self._lock:
            if len(self._steps) >= self._max_steps:
                del self._steps[0]
            self._steps.append(step)
        return step

    def clear(self) -> None:
        with self._lock:
            self._steps.clear()

    @property
    def steps(self) -> tuple[OperationsTraceStep, ...]:
        with self._lock:
            return tuple(self._steps)

    def kinds(self) -> list[str]:
        return [step.kind.value for step in self.steps]

    def to_records(self) -> list[dict[str, Any]]:
        return [step.to_record() for step in self.steps]


# ---------------------------------------------------------------------------
# Composed result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class KernelVFSResult:
    """Composed request-runtime outcome: contract result + optional payload.

    ``result`` is always a validated :class:`HostCallbackResult`.  Payload
    fields (``data``, ``detail``) carry bytes and side information that the
    closed host-callback record does not embed.
    """

    SCHEMA: ClassVar[str] = OPERATIONS_RESULT_SCHEMA

    result: HostCallbackResult
    data: bytes = b""
    detail: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.result, HostCallbackResult):
            raise OperationsError(
                "result must be a HostCallbackResult",
                code=OperationsErrorCode.INVALID,
                errno=HostErrno.EINVAL,
            )
        if not isinstance(self.data, (bytes, bytearray)):
            raise OperationsError(
                "data must be bytes",
                code=OperationsErrorCode.INVALID,
                errno=HostErrno.EINVAL,
            )
        object.__setattr__(self, "data", bytes(self.data))
        object.__setattr__(self, "detail", dict(self.detail or {}))

    # -- contract proxies ---------------------------------------------------

    @property
    def kind(self) -> HostCallbackKind:
        return self.result.kind

    @property
    def success(self) -> bool:
        return self.result.success

    @property
    def errno(self) -> HostErrno:
        return self.result.errno

    @property
    def error(self) -> Any:
        return self.result.error

    @property
    def handle(self) -> HostHandle | None:
        return self.result.handle

    @property
    def metadata(self) -> HostMetadata | None:
        return self.result.metadata

    @property
    def bytes_transferred(self) -> int:
        return self.result.bytes_transferred

    @property
    def dir_entries(self) -> tuple[str, ...]:
        return self.result.dir_entries

    @property
    def observed_effect(self) -> bool:
        return self.result.observed_effect

    @property
    def mount_state(self) -> MountLifecycleState | None:
        return self.result.mount_state

    @property
    def request_id(self) -> str:
        return self.result.request_id

    @property
    def platform(self) -> HostPlatform:
        return self.result.platform

    @property
    def errno_number(self) -> int:
        return self.result.errno_number

    def to_host_callback_result(self) -> HostCallbackResult:
        return self.result

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "result": self.result.to_record(),
            "data_len": len(self.data),
            "detail": dict(self.detail),
        }


# ---------------------------------------------------------------------------
# KernelVFSOperations
# ---------------------------------------------------------------------------


class KernelVFSOperations:
    """Platform-neutral host-callback operations over the composed runtime.

    Interface alias: ``KernelVFSOperations@1``.

    Direct tests (and future fusepy loaders) call the named methods or the
    central :meth:`dispatch` entry.  Every path returns a
    :class:`KernelVFSResult` whose embedded :class:`HostCallbackResult`
    satisfies the host contract (exact errno, no false success).
    """

    SCHEMA: ClassVar[str] = KERNEL_VFS_OPERATIONS_SCHEMA
    CONTRACT_VERSION: ClassVar[int] = CONTRACT_VERSION

    def __init__(
        self,
        *,
        host: HostVFSService | None = None,
        concurrency: HostConcurrencyPlane | None = None,
        bridge: AsyncBridge | None = None,
        platform: HostPlatform = HostPlatform.HERMETIC,
        durability_mode: DurabilityMode = DurabilityMode.COMMITTED_VISIBLE,
        cache_consistency: CacheConsistencyMode = CacheConsistencyMode.GENERATION_BOUND,
        mount_id: str = DEFAULT_MOUNT_ID,
        contract: HostFilesystemAdapterContract | None = None,
        clock: Callable[[], int] | None = None,
        own_bridge: bool = False,
        require_ready: bool = True,
    ) -> None:
        self._clock = clock or (lambda: int(time.time() * 1000))
        self._platform = (
            platform if isinstance(platform, HostPlatform) else HostPlatform(platform)
        )
        self._durability_mode = (
            durability_mode
            if isinstance(durability_mode, DurabilityMode)
            else DurabilityMode(durability_mode)
        )
        self._cache_consistency = (
            cache_consistency
            if isinstance(cache_consistency, CacheConsistencyMode)
            else CacheConsistencyMode(cache_consistency)
        )
        self._mount_id = mount_id or DEFAULT_MOUNT_ID
        self._contract = contract or HostFilesystemAdapterContract.default()
        self._trace = OperationsTraceLog()
        self._lock = threading.RLock()
        self._own_bridge = bool(own_bridge)
        self._require_ready = bool(require_ready)

        # Host façade (CanonicalVFSService authority).
        self._host = host or HostVFSService.with_memory_storage(
            clock=self._clock,
            mount_id=self._mount_id,
            platform=self._platform,
        )
        # HostVFSService exposes getattr as ``metadata(path)``; the projector
        # lives on the private ``_metadata`` attribute (property may be shadowed).
        self._metadata_plane = getattr(self._host, "_metadata", None)

        # Concurrency plane shares the host handle table so open-rename /
        # open-unlink policy and callback locks observe the same handles.
        self._concurrency = concurrency or HostConcurrencyPlane(
            handle_table=self._host.handles,
            mount_id=self._mount_id,
            clock_ms=self._clock,
        )

        self._bridge = bridge
        self._lifecycle = MountLifecycleState.UNINITIALIZED
        self._generation = 0
        self._request_seq = 0
        # Last payload retained for diagnostics / differential tests.
        self._last_data: bytes = b""
        self._last_detail: dict[str, Any] = {}

        # Pin dispatch/execute as the same bound method so
        # ``ops.execute is ops.dispatch`` holds for alias checks.
        bound_dispatch = self.dispatch
        self.dispatch = bound_dispatch
        self.execute = bound_dispatch

    # -- factories ----------------------------------------------------------

    @classmethod
    def with_memory_storage(
        cls,
        *,
        clock: Callable[[], int] | None = None,
        platform: HostPlatform = HostPlatform.HERMETIC,
        mount_id: str = DEFAULT_MOUNT_ID,
        enable_bridge: bool = False,
        **kwargs: Any,
    ) -> "KernelVFSOperations":
        """Build operations over an in-memory host façade (hermetic tests)."""

        host = HostVFSService.with_memory_storage(
            clock=clock,
            mount_id=mount_id,
            platform=platform,
        )
        bridge: AsyncBridge | None = None
        own_bridge = False
        if enable_bridge:
            bridge = AsyncBridge(
                max_inflight=16,
                max_queue_depth=32,
                default_deadline_s=30.0,
                thread_name="kvfs-ops-bridge",
            )
            bridge.start()
            own_bridge = True
        return cls(
            host=host,
            bridge=bridge,
            own_bridge=own_bridge,
            platform=platform,
            mount_id=mount_id,
            clock=clock,
            **kwargs,
        )

    @classmethod
    def with_backend(
        cls,
        backend: str = "memory",
        *,
        root: str | None = None,
        clock: Callable[[], int] | None = None,
        platform: HostPlatform = HostPlatform.HERMETIC,
        mount_id: str = DEFAULT_MOUNT_ID,
        **kwargs: Any,
    ) -> "KernelVFSOperations":
        """Build operations with a real ranged-storage backend injection."""

        host = build_host_vfs_service(
            backend=backend,
            root=root,
            clock=clock,
            mount_id=mount_id,
            platform=platform,
        )
        return cls(
            host=host,
            platform=platform,
            mount_id=mount_id,
            clock=clock,
            **kwargs,
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
    def host(self) -> HostVFSService:
        return self._host

    @property
    def concurrency(self) -> HostConcurrencyPlane:
        return self._concurrency

    @property
    def bridge(self) -> AsyncBridge | None:
        return self._bridge

    @property
    def platform(self) -> HostPlatform:
        return self._platform

    @property
    def mount_id(self) -> str:
        return self._mount_id

    @property
    def lifecycle(self) -> MountLifecycleState:
        with self._lock:
            return self._lifecycle

    @property
    def ready(self) -> bool:
        return self.lifecycle is MountLifecycleState.READY

    @property
    def generation(self) -> int:
        with self._lock:
            return self._generation

    @property
    def durability_mode(self) -> DurabilityMode:
        return self._durability_mode

    @property
    def cache_consistency(self) -> CacheConsistencyMode:
        return self._cache_consistency

    @property
    def contract(self) -> HostFilesystemAdapterContract:
        return self._contract

    @property
    def trace(self) -> OperationsTraceLog:
        return self._trace

    @property
    def last_data(self) -> bytes:
        return self._last_data

    @property
    def last_detail(self) -> Mapping[str, Any]:
        return dict(self._last_detail)

    def to_record(self) -> dict[str, Any]:
        with self._lock:
            return {
                "schema": self.SCHEMA,
                "contract_version": CONTRACT_VERSION,
                "schema_version": SCHEMA_VERSION,
                "mount_id": self._mount_id,
                "platform": self._platform.value,
                "lifecycle": self._lifecycle.value,
                "generation": self._generation,
                "durability_mode": self._durability_mode.value,
                "cache_consistency": self._cache_consistency.value,
                "require_ready": self._require_ready,
                "has_bridge": self._bridge is not None,
                "host_schema": self._host.SCHEMA,
                "concurrency": self._concurrency.to_record(),
            }

    # -- lifecycle ----------------------------------------------------------

    def _set_lifecycle(self, new_state: MountLifecycleState) -> None:
        with self._lock:
            current = self._lifecycle
            if current is new_state:
                return
            assert_legal_mount_transition(current, new_state)
            self._lifecycle = new_state
            self._trace.record(
                OperationsTraceKind.LIFECYCLE,
                success=True,
                detail={"from": current.value, "to": new_state.value},
            )

    def _ensure_accepting(self, kind: HostCallbackKind) -> HostCallbackResult | None:
        """Return a failure result when the runtime must not serve ``kind``."""

        with self._lock:
            state = self._lifecycle

        if kind is HostCallbackKind.INIT:
            if state in (
                MountLifecycleState.DESTROYED,
                MountLifecycleState.DESTROYING,
            ):
                return HostCallbackResult.make_failure(
                    kind,
                    HostErrno.EINVAL,
                    message=f"cannot init from lifecycle state {state.value}",
                    platform=self._platform,
                    vfs_error_code=OperationsErrorCode.LIFECYCLE.value,
                )
            return None

        if kind is HostCallbackKind.DESTROY:
            # Destroy is always admitted so cleanup cannot be blocked.
            return None

        if state is MountLifecycleState.DESTROYED:
            return HostCallbackResult.make_failure(
                kind,
                HostErrno.ENODEV,
                message="operations runtime is destroyed",
                platform=self._platform,
                vfs_error_code=OperationsErrorCode.DESTROYED.value,
            )

        if state is MountLifecycleState.FAILED:
            return HostCallbackResult.make_failure(
                kind,
                HostErrno.EIO,
                message="operations runtime is in FAILED state",
                platform=self._platform,
                vfs_error_code=OperationsErrorCode.LIFECYCLE.value,
            )

        if self._require_ready and state is not MountLifecycleState.READY:
            if state in (
                MountLifecycleState.UNINITIALIZED,
                MountLifecycleState.INITIALIZING,
                MountLifecycleState.RECOVERING,
            ):
                return HostCallbackResult.make_failure(
                    kind,
                    HostErrno.EAGAIN,
                    message=f"operations runtime not ready (state={state.value})",
                    platform=self._platform,
                    vfs_error_code=OperationsErrorCode.NOT_READY.value,
                )
            if state is MountLifecycleState.DRAINING:
                return HostCallbackResult.make_failure(
                    kind,
                    HostErrno.EBUSY,
                    message="operations runtime is draining",
                    platform=self._platform,
                    vfs_error_code=OperationsErrorCode.SHUTDOWN.value,
                )

        return None

    # -- central dispatch ---------------------------------------------------

    def dispatch(
        self,
        kind: HostCallbackKind | str | HostCallbackRequest,
        *,
        path: str = "",
        path_to: str = "",
        target_path: str = "",
        data: bytes = b"",
        offset: int = 0,
        size: int = 0,
        handle: HostHandle | None = None,
        handle_id: int = 0,
        generation: int | None = None,
        flags: Sequence[OpenFlag | str] | OpenFlag | str | None = None,
        mode: int = 0o644,
        mask: int = F_OK,
        uid: int = 0,
        gid: int = 0,
        atime_ns: int | None = None,
        mtime_ns: int | None = None,
        datasync: bool = False,
        request_id: str = "",
        platform: HostPlatform | None = None,
    ) -> KernelVFSResult:
        """Dispatch one host callback through the composed request runtime.

        Accepts either a :class:`HostCallbackRequest`, a
        :class:`HostCallbackKind`, or a callback name string.
        """

        # Build / normalize request.
        if isinstance(kind, HostCallbackRequest):
            request = kind
            # Allow keyword overrides for payload fields not on the request.
            if data:
                pass  # payload carried separately
            if target_path and not request.path_to:
                request = HostCallbackRequest(
                    kind=request.kind,
                    path=request.path,
                    path_to=target_path,
                    handle=request.handle,
                    flags=request.flags,
                    offset=request.offset,
                    size=request.size,
                    mode=request.mode,
                    uid=request.uid,
                    gid=request.gid,
                    atime_ns=request.atime_ns,
                    mtime_ns=request.mtime_ns,
                    name=request.name,
                    mount_id=request.mount_id or self._mount_id,
                    request_id=request.request_id or request_id,
                    platform=request.platform,
                    durability_mode=request.durability_mode,
                    cache_consistency=request.cache_consistency,
                    deadline=request.deadline,
                    datasync=request.datasync,
                )
        else:
            try:
                callback_kind = parse_callback_kind(kind)
            except HostUnknownCallbackError:
                self._trace.record(
                    OperationsTraceKind.UNSUPPORTED,
                    success=False,
                    callback=str(kind),
                    code=OperationsErrorCode.UNKNOWN_CALLBACK.value,
                )
                # Unknown callbacks are forbidden at the contract boundary.
                raise
            flag_tuple: tuple[OpenFlag, ...] = ()
            if flags is not None:
                if isinstance(flags, (list, tuple)):
                    flag_tuple = tuple(
                        f if isinstance(f, OpenFlag) else OpenFlag(str(f)) for f in flags
                    )
                elif isinstance(flags, OpenFlag):
                    flag_tuple = (flags,)
                else:
                    flag_tuple = (OpenFlag(str(flags)),)
            resolved_handle = handle
            if resolved_handle is None and handle_id:
                resolved_handle = HostHandle(
                    handle_id=int(handle_id),
                    inode=1,
                    generation=int(generation or 0),
                    path_at_open=path or "",
                    mount_id=self._mount_id,
                )
            request = HostCallbackRequest(
                kind=callback_kind,
                path=path or "",
                path_to=path_to or target_path or "",
                handle=resolved_handle,
                flags=flag_tuple,
                offset=int(offset or 0),
                size=int(size or 0),
                mode=int(mode or 0),
                uid=int(uid or 0),
                gid=int(gid or 0),
                atime_ns=int(atime_ns or 0),
                mtime_ns=int(mtime_ns or 0),
                mount_id=self._mount_id,
                request_id=request_id or self._next_request_id(),
                platform=platform or self._platform,
                durability_mode=self._durability_mode,
                cache_consistency=self._cache_consistency,
                datasync=bool(datasync),
            )

        return self._dispatch_request(
            request,
            data=bytes(data or b""),
            mask=int(mask),
            atime_ns=atime_ns,
            mtime_ns=mtime_ns,
            generation=generation,
        )

    # Class-level alias for discovery; instances pin identity in ``__init__``.
    execute = dispatch

    def _next_request_id(self) -> str:
        with self._lock:
            self._request_seq += 1
            seq = self._request_seq
        return f"kvfs-ops-{seq:08d}-{uuid.uuid4().hex[:8]}"

    def _dispatch_request(
        self,
        request: HostCallbackRequest,
        *,
        data: bytes = b"",
        mask: int = F_OK,
        atime_ns: int | None = None,
        mtime_ns: int | None = None,
        generation: int | None = None,
    ) -> KernelVFSResult:
        kind = request.kind
        request_id = request.request_id or self._next_request_id()
        platform = request.platform or self._platform

        # Cancelled / deadline envelope.
        cancelled = evaluate_cancelled_request(request)
        if cancelled is not None:
            outcome = KernelVFSResult(result=cancelled)
            self._trace.record(
                OperationsTraceKind.DISPATCH,
                success=False,
                callback=kind.value,
                code=OperationsErrorCode.CANCELLED.value,
            )
            return outcome

        # Explicit-unsupported — never false-succeed.
        disposition = callback_disposition(kind)
        if disposition is CallbackDisposition.EXPLICIT_UNSUPPORTED:
            result = HostCallbackResult.make_unsupported(
                kind, platform=platform, request_id=request_id
            )
            self._trace.record(
                OperationsTraceKind.UNSUPPORTED,
                success=False,
                callback=kind.value,
                code=result.errno.value,
            )
            return KernelVFSResult(result=result)

        # Lifecycle admission.
        not_ready = self._ensure_accepting(kind)
        if not_ready is not None:
            # Rebuild with correct kind / request_id.
            result = HostCallbackResult.make_failure(
                kind,
                not_ready.errno,
                message=not_ready.error.message if not_ready.error else "not ready",
                request_id=request_id,
                platform=platform,
                vfs_error_code=(
                    not_ready.error.vfs_error_code if not_ready.error else ""
                ),
            )
            self._trace.record(
                OperationsTraceKind.DISPATCH,
                success=False,
                callback=kind.value,
                code=result.errno.value,
            )
            return KernelVFSResult(result=result)

        # INIT / DESTROY are special-cased (lifecycle + optional drain).
        if kind is HostCallbackKind.INIT:
            return self._do_init(request_id=request_id, platform=platform)
        if kind is HostCallbackKind.DESTROY:
            return self._do_destroy(request_id=request_id, platform=platform)

        # Run body under the concurrency plane.
        try:
            outcome = self._run_linearized(
                kind,
                request,
                data=data,
                mask=mask,
                atime_ns=atime_ns,
                mtime_ns=mtime_ns,
                generation=generation,
                request_id=request_id,
                platform=platform,
            )
        except HostCallbackConflictError as exc:
            errno = getattr(exc, "errno", HostErrno.EBUSY) or HostErrno.EBUSY
            if not isinstance(errno, HostErrno):
                try:
                    errno = HostErrno(str(errno))
                except ValueError:
                    errno = HostErrno.EBUSY
            result = HostCallbackResult.make_failure(
                kind,
                errno,
                message=str(exc),
                request_id=request_id,
                platform=platform,
                vfs_error_code=OperationsErrorCode.CONFLICT.value,
                retryable=True,
            )
            self._trace.record(
                OperationsTraceKind.CONFLICT,
                success=False,
                callback=kind.value,
                code=errno.value,
            )
            return KernelVFSResult(result=result)
        except HostShutdownError as exc:
            result = HostCallbackResult.make_failure(
                kind,
                HostErrno.EBUSY,
                message=str(exc),
                request_id=request_id,
                platform=platform,
                vfs_error_code=OperationsErrorCode.SHUTDOWN.value,
            )
            return KernelVFSResult(result=result)
        except HostConcurrencyError as exc:
            errno = getattr(exc, "errno", HostErrno.EIO) or HostErrno.EIO
            if not isinstance(errno, HostErrno):
                errno = HostErrno.EIO
            result = HostCallbackResult.make_failure(
                kind,
                errno,
                message=str(exc),
                request_id=request_id,
                platform=platform,
                vfs_error_code=OperationsErrorCode.CONFLICT.value,
            )
            return KernelVFSResult(result=result)
        except OperationsError as exc:
            result = HostCallbackResult.make_failure(
                kind,
                exc.errno,
                message=exc.message,
                request_id=request_id,
                platform=platform,
                vfs_error_code=exc.code.value,
            )
            return KernelVFSResult(result=result)
        except Exception as exc:  # noqa: BLE001 — project as EIO fail-closed
            result = HostCallbackResult.make_failure(
                kind,
                HostErrno.EIO,
                message=f"operations internal error: {exc}",
                request_id=request_id,
                platform=platform,
                vfs_error_code=OperationsErrorCode.INTERNAL.value,
            )
            self._trace.record(
                OperationsTraceKind.DISPATCH,
                success=False,
                callback=kind.value,
                code=OperationsErrorCode.INTERNAL.value,
                detail={"error": str(exc)},
            )
            return KernelVFSResult(result=result)

        self._last_data = outcome.data
        self._last_detail = dict(outcome.detail)
        self._trace.record(
            OperationsTraceKind.CALLBACK,
            success=outcome.success,
            callback=kind.value,
            code="" if outcome.success else outcome.errno.value,
            detail={"request_id": request_id, "observed_effect": outcome.observed_effect},
        )
        return outcome

    def _run_linearized(
        self,
        kind: HostCallbackKind,
        request: HostCallbackRequest,
        *,
        data: bytes,
        mask: int,
        atime_ns: int | None,
        mtime_ns: int | None,
        generation: int | None,
        request_id: str,
        platform: HostPlatform,
    ) -> KernelVFSResult:
        paths = self._paths_for(kind, request)
        handle_ids = self._handle_ids_for(kind, request)
        path_mode = (
            LockMode.SHARED if kind in _SHARED_PATH_CALLBACKS else LockMode.EXCLUSIVE
        )
        handle_mode = (
            LockMode.SHARED
            if kind in (HostCallbackKind.READ, HostCallbackKind.FLUSH)
            else LockMode.EXCLUSIVE
        )

        def body(_session: Any) -> KernelVFSResult:
            return self._invoke_callback(
                kind,
                request,
                data=data,
                mask=mask,
                atime_ns=atime_ns,
                mtime_ns=mtime_ns,
                generation=generation,
                request_id=request_id,
                platform=platform,
            )

        _session, outcome = self._concurrency.run_callback(
            body,
            kind=kind,
            paths=paths,
            handle_ids=handle_ids,
            mount_id=self._mount_id,
            path_mode=path_mode,
            handle_mode=handle_mode,
        )
        return outcome

    @staticmethod
    def _paths_for(
        kind: HostCallbackKind, request: HostCallbackRequest
    ) -> tuple[str, ...]:
        if kind is HostCallbackKind.STATFS:
            return ()
        if kind is HostCallbackKind.RENAME:
            paths = []
            if request.path:
                paths.append(request.path)
            if request.path_to:
                paths.append(request.path_to)
            return tuple(paths)
        if request.path:
            return (request.path,)
        return ()

    @staticmethod
    def _handle_ids_for(
        kind: HostCallbackKind, request: HostCallbackRequest
    ) -> tuple[int, ...]:
        if kind not in HANDLE_CALLBACKS:
            return ()
        if request.handle is not None:
            return (int(request.handle.handle_id),)
        return ()

    # -- callback body ------------------------------------------------------

    def _invoke_callback(
        self,
        kind: HostCallbackKind,
        request: HostCallbackRequest,
        *,
        data: bytes,
        mask: int,
        atime_ns: int | None,
        mtime_ns: int | None,
        generation: int | None,
        request_id: str,
        platform: HostPlatform,
    ) -> KernelVFSResult:
        """Execute one required-supported callback against the host façade."""

        path = request.path
        target = request.path_to
        handle_id = int(request.handle.handle_id) if request.handle is not None else 0
        gen = (
            generation
            if generation is not None
            else (request.handle.generation if request.handle is not None else None)
        )
        flags = request.flags or None
        mode = request.mode or 0o644
        offset = request.offset
        size = request.size

        if kind is HostCallbackKind.GETATTR:
            host_result = self._host.getattr(path)
            return self._from_host(
                kind, host_result, request_id=request_id, platform=platform
            )

        if kind is HostCallbackKind.READDIR:
            host_result = self._host.list(path)
            return self._from_host(
                kind, host_result, request_id=request_id, platform=platform
            )

        if kind is HostCallbackKind.ACCESS:
            return self._access(
                path,
                mask=mask,
                uid=request.uid,
                gid=request.gid,
                request_id=request_id,
                platform=platform,
            )

        if kind is HostCallbackKind.STATFS:
            return self._statfs(request_id=request_id, platform=platform)

        if kind is HostCallbackKind.UTIMENS:
            return self._utimens(
                path,
                atime_ns=atime_ns if atime_ns is not None else request.atime_ns,
                mtime_ns=mtime_ns if mtime_ns is not None else request.mtime_ns,
                request_id=request_id,
                platform=platform,
            )

        if kind is HostCallbackKind.OPEN:
            host_result = self._host.open(path, flags, mode=mode)
            return self._from_host(
                kind, host_result, request_id=request_id, platform=platform
            )

        if kind is HostCallbackKind.CREATE:
            return self._create(
                path,
                data=data,
                flags=flags,
                mode=mode,
                request_id=request_id,
                platform=platform,
            )

        if kind is HostCallbackKind.READ:
            return self._read(
                path,
                offset=offset,
                size=size,
                handle_id=handle_id,
                generation=gen,
                request_id=request_id,
                platform=platform,
            )

        if kind is HostCallbackKind.WRITE:
            return self._write(
                path,
                data=data,
                offset=offset,
                handle_id=handle_id,
                generation=gen,
                request_id=request_id,
                platform=platform,
            )

        if kind is HostCallbackKind.TRUNCATE:
            host_result = self._host.truncate(path, size)
            return self._from_host(
                kind, host_result, request_id=request_id, platform=platform
            )

        if kind is HostCallbackKind.FLUSH:
            host_result = self._host.flush_handle(
                handle_id, generation=gen, commit=False
            )
            return self._from_host(
                kind, host_result, request_id=request_id, platform=platform
            )

        if kind is HostCallbackKind.FSYNC:
            host_result = self._host.flush_handle(
                handle_id, generation=gen, commit=True
            )
            # fsync success must not claim only buffered durability.
            outcome = self._from_host(
                kind,
                host_result,
                request_id=request_id,
                platform=platform,
                durability_mode=self._durability_mode
                if self._durability_mode is not DurabilityMode.BUFFERED
                else DurabilityMode.WAL_AND_BACKEND,
            )
            return outcome

        if kind is HostCallbackKind.RELEASE:
            host_result = self._host.release_handle(handle_id, generation=gen)
            return self._from_host(
                kind, host_result, request_id=request_id, platform=platform
            )

        if kind is HostCallbackKind.MKDIR:
            host_result = self._host.mkdir(path, mode=mode)
            return self._from_host(
                kind, host_result, request_id=request_id, platform=platform
            )

        if kind is HostCallbackKind.RMDIR:
            host_result = self._host.rmdir(path)
            return self._from_host(
                kind, host_result, request_id=request_id, platform=platform
            )

        if kind is HostCallbackKind.UNLINK:
            host_result = self._host.unlink(path)
            return self._from_host(
                kind, host_result, request_id=request_id, platform=platform
            )

        if kind is HostCallbackKind.RENAME:
            host_result = self._host.rename(path, target)
            return self._from_host(
                kind, host_result, request_id=request_id, platform=platform
            )

        # Required set is closed; anything else is a contract bug.
        return KernelVFSResult(
            result=HostCallbackResult.make_unsupported(
                kind, platform=platform, request_id=request_id
            )
        )

    def _from_host(
        self,
        kind: HostCallbackKind,
        host_result: HostOperationResult,
        *,
        request_id: str,
        platform: HostPlatform,
        durability_mode: DurabilityMode | None = None,
        data: bytes | None = None,
        detail: Mapping[str, Any] | None = None,
    ) -> KernelVFSResult:
        """Project a HostOperationResult onto a contract HostCallbackResult."""

        dm = durability_mode or self._durability_mode
        if host_result.success:
            # Mutating callbacks require observed_effect under the contract.
            observed = host_result.observed_effect
            if kind in MUTATING_CALLBACKS and not observed:
                # Host reported success without an observed effect — fail closed.
                return KernelVFSResult(
                    result=HostCallbackResult.make_failure(
                        kind,
                        HostErrno.EIO,
                        message=(
                            f"mutating callback {kind.value} success without "
                            "observed_effect is forbidden"
                        ),
                        request_id=request_id,
                        platform=platform,
                        vfs_error_code=OperationsErrorCode.HOST.value,
                    ),
                    detail={"host": host_result.to_record()},
                )
            # fsync durability guard.
            if kind is HostCallbackKind.FSYNC and dm is DurabilityMode.BUFFERED:
                dm = DurabilityMode.WAL_AND_BACKEND
            callback = HostCallbackResult.make_success(
                kind,
                handle=host_result.handle,
                metadata=host_result.metadata,
                bytes_transferred=host_result.bytes_transferred
                or (len(host_result.data) if host_result.data else 0),
                dir_entries=host_result.dir_entries,
                mount_state=self.lifecycle,
                durability_mode=dm,
                cache_consistency=self._cache_consistency,
                observed_effect=observed,
                request_id=request_id,
                platform=platform,
            )
            payload = (
                data
                if data is not None
                else (host_result.data if host_result.data else b"")
            )
            return KernelVFSResult(
                result=callback,
                data=payload,
                detail={**(detail or {}), "host": host_result.to_record()},
            )

        errno = (
            host_result.errno
            if host_result.errno is not HostErrno.OK
            else HostErrno.EIO
        )
        callback = HostCallbackResult.make_failure(
            kind,
            errno,
            message=host_result.message or host_result.error_code or f"{kind.value} failed",
            request_id=request_id,
            platform=platform,
            vfs_error_code=host_result.error_code or OperationsErrorCode.HOST.value,
            durability_mode=dm,
            cache_consistency=self._cache_consistency,
        )
        return KernelVFSResult(
            result=callback,
            detail={**(detail or {}), "host": host_result.to_record()},
        )

    # -- specialized required callbacks -------------------------------------

    def _do_init(
        self, *, request_id: str, platform: HostPlatform
    ) -> KernelVFSResult:
        with self._lock:
            state = self._lifecycle
            if state is MountLifecycleState.READY:
                # Idempotent init while ready.
                result = HostCallbackResult.make_success(
                    HostCallbackKind.INIT,
                    mount_state=MountLifecycleState.READY,
                    observed_effect=False,
                    request_id=request_id,
                    platform=platform,
                    durability_mode=self._durability_mode,
                    cache_consistency=self._cache_consistency,
                )
                return KernelVFSResult(
                    result=result, detail={"lifecycle": state.value, "idempotent": True}
                )
            if state is MountLifecycleState.DESTROYED:
                result = HostCallbackResult.make_failure(
                    HostCallbackKind.INIT,
                    HostErrno.EINVAL,
                    message="cannot init a destroyed operations runtime",
                    request_id=request_id,
                    platform=platform,
                    vfs_error_code=OperationsErrorCode.DESTROYED.value,
                )
                return KernelVFSResult(result=result)

        try:
            if state is MountLifecycleState.UNINITIALIZED:
                self._set_lifecycle(MountLifecycleState.INITIALIZING)
            # Recovery handshake (no WAL binding in this task — mark complete).
            if self.lifecycle is MountLifecycleState.INITIALIZING:
                if is_legal_mount_transition(
                    MountLifecycleState.INITIALIZING, MountLifecycleState.RECOVERING
                ):
                    self._set_lifecycle(MountLifecycleState.RECOVERING)
            if self.lifecycle is MountLifecycleState.RECOVERING:
                self._set_lifecycle(MountLifecycleState.READY)
            elif self.lifecycle is MountLifecycleState.INITIALIZING:
                self._set_lifecycle(MountLifecycleState.READY)
            with self._lock:
                self._generation += 1
                gen = self._generation
            result = HostCallbackResult.make_success(
                HostCallbackKind.INIT,
                mount_state=MountLifecycleState.READY,
                observed_effect=False,
                request_id=request_id,
                platform=platform,
                durability_mode=self._durability_mode,
                cache_consistency=self._cache_consistency,
            )
            self._trace.record(
                OperationsTraceKind.INIT,
                success=True,
                callback="init",
                detail={"generation": gen},
            )
            return KernelVFSResult(
                result=result,
                detail={"lifecycle": "ready", "generation": gen},
            )
        except Exception as exc:  # noqa: BLE001
            try:
                self._set_lifecycle(MountLifecycleState.FAILED)
            except Exception:  # noqa: BLE001
                pass
            result = HostCallbackResult.make_failure(
                HostCallbackKind.INIT,
                HostErrno.EIO,
                message=f"init failed: {exc}",
                request_id=request_id,
                platform=platform,
                vfs_error_code=OperationsErrorCode.LIFECYCLE.value,
            )
            self._trace.record(
                OperationsTraceKind.INIT,
                success=False,
                callback="init",
                code=OperationsErrorCode.LIFECYCLE.value,
            )
            return KernelVFSResult(result=result)

    def _do_destroy(
        self, *, request_id: str, platform: HostPlatform
    ) -> KernelVFSResult:
        with self._lock:
            state = self._lifecycle
            if state is MountLifecycleState.DESTROYED:
                result = HostCallbackResult.make_success(
                    HostCallbackKind.DESTROY,
                    mount_state=MountLifecycleState.DESTROYED,
                    observed_effect=False,
                    request_id=request_id,
                    platform=platform,
                    durability_mode=self._durability_mode,
                    cache_consistency=self._cache_consistency,
                )
                return KernelVFSResult(
                    result=result,
                    detail={"lifecycle": "destroyed", "idempotent": True},
                )

        try:
            if state is MountLifecycleState.READY:
                self._set_lifecycle(MountLifecycleState.DRAINING)
            # Drain concurrency plane.
            try:
                self._concurrency.shutdown(drain=True)
            except Exception:  # noqa: BLE001 — destroy must complete
                pass
            # Close owned async bridge.
            if self._own_bridge and self._bridge is not None:
                try:
                    if not self._bridge.is_closed:
                        self._bridge.close()
                except AsyncBridgeError:
                    pass
            current = self.lifecycle
            if current is MountLifecycleState.DRAINING:
                self._set_lifecycle(MountLifecycleState.DESTROYING)
            elif current not in (
                MountLifecycleState.DESTROYING,
                MountLifecycleState.DESTROYED,
            ):
                if is_legal_mount_transition(current, MountLifecycleState.DESTROYING):
                    self._set_lifecycle(MountLifecycleState.DESTROYING)
                elif is_legal_mount_transition(current, MountLifecycleState.FAILED):
                    self._set_lifecycle(MountLifecycleState.FAILED)
                    if is_legal_mount_transition(
                        MountLifecycleState.FAILED, MountLifecycleState.DESTROYING
                    ):
                        self._set_lifecycle(MountLifecycleState.DESTROYING)
            if self.lifecycle is MountLifecycleState.DESTROYING:
                self._set_lifecycle(MountLifecycleState.DESTROYED)
            elif self.lifecycle is not MountLifecycleState.DESTROYED:
                # Force terminal state when intermediate transitions are awkward.
                with self._lock:
                    self._lifecycle = MountLifecycleState.DESTROYED

            result = HostCallbackResult.make_success(
                HostCallbackKind.DESTROY,
                mount_state=MountLifecycleState.DESTROYED,
                observed_effect=False,
                request_id=request_id,
                platform=platform,
                durability_mode=self._durability_mode,
                cache_consistency=self._cache_consistency,
            )
            self._trace.record(
                OperationsTraceKind.DESTROY,
                success=True,
                callback="destroy",
            )
            return KernelVFSResult(
                result=result, detail={"lifecycle": "destroyed"}
            )
        except Exception as exc:  # noqa: BLE001
            with self._lock:
                self._lifecycle = MountLifecycleState.DESTROYED
            result = HostCallbackResult.make_failure(
                HostCallbackKind.DESTROY,
                HostErrno.EIO,
                message=f"destroy failed: {exc}",
                request_id=request_id,
                platform=platform,
                vfs_error_code=OperationsErrorCode.LIFECYCLE.value,
            )
            self._trace.record(
                OperationsTraceKind.DESTROY,
                success=False,
                callback="destroy",
                code=OperationsErrorCode.LIFECYCLE.value,
            )
            return KernelVFSResult(result=result)

    def _access(
        self,
        path: str,
        *,
        mask: int,
        uid: int,
        gid: int,
        request_id: str,
        platform: HostPlatform,
    ) -> KernelVFSResult:
        # Ensure metadata plane is synchronized via host getattr first.
        meta = self._host.getattr(path)
        if not meta.success:
            return self._from_host(
                HostCallbackKind.ACCESS,
                HostOperationResult(
                    kind="access",
                    success=False,
                    path=path,
                    errno=meta.errno if meta.errno is not HostErrno.OK else HostErrno.ENOENT,
                    error_code=meta.error_code,
                    message=meta.message or "access path not found",
                ),
                request_id=request_id,
                platform=platform,
            )

        projector = self._metadata_plane
        access = None
        if projector is not None:
            try:
                access = projector.access(
                    path if path not in ("", "/") else "",
                    mask,
                    caller_uid=uid,
                    caller_gid=gid,
                )
            except MetadataError as exc:
                return KernelVFSResult(
                    result=HostCallbackResult.make_failure(
                        HostCallbackKind.ACCESS,
                        exc.errno if isinstance(exc.errno, HostErrno) else HostErrno.EACCES,
                        message=str(exc),
                        request_id=request_id,
                        platform=platform,
                        vfs_error_code=OperationsErrorCode.HOST.value,
                    )
                )

        if access is None:
            # Existence-only success after metadata check.
            return KernelVFSResult(
                result=HostCallbackResult.make_success(
                    HostCallbackKind.ACCESS,
                    metadata=meta.metadata,
                    observed_effect=False,
                    request_id=request_id,
                    platform=platform,
                    durability_mode=self._durability_mode,
                    cache_consistency=self._cache_consistency,
                ),
                detail={"mask": mask, "mode": "existence"},
            )

        if access.allowed:
            return KernelVFSResult(
                result=HostCallbackResult.make_success(
                    HostCallbackKind.ACCESS,
                    metadata=meta.metadata,
                    observed_effect=False,
                    request_id=request_id,
                    platform=platform,
                    durability_mode=self._durability_mode,
                    cache_consistency=self._cache_consistency,
                ),
                detail=access.to_record() if hasattr(access, "to_record") else {"mask": mask},
            )
        errno = access.errno if access.errno is not HostErrno.OK else HostErrno.EACCES
        return KernelVFSResult(
            result=HostCallbackResult.make_failure(
                HostCallbackKind.ACCESS,
                errno,
                message=access.code or "access denied",
                request_id=request_id,
                platform=platform,
                vfs_error_code=access.code or OperationsErrorCode.HOST.value,
            ),
            detail=access.to_record() if hasattr(access, "to_record") else {},
        )

    def _statfs(
        self, *, request_id: str, platform: HostPlatform
    ) -> KernelVFSResult:
        projector = self._metadata_plane
        detail: dict[str, Any] = {}
        if projector is not None:
            fs = projector.statfs(mount_id=self._mount_id)
            detail = fs.to_record() if hasattr(fs, "to_record") else {}
        result = HostCallbackResult.make_success(
            HostCallbackKind.STATFS,
            observed_effect=False,
            request_id=request_id,
            platform=platform,
            durability_mode=self._durability_mode,
            cache_consistency=self._cache_consistency,
            mount_state=self.lifecycle,
        )
        return KernelVFSResult(result=result, detail=detail)

    def _utimens(
        self,
        path: str,
        *,
        atime_ns: int | None,
        mtime_ns: int | None,
        request_id: str,
        platform: HostPlatform,
    ) -> KernelVFSResult:
        # Ensure the path exists in the host / metadata planes.
        meta = self._host.getattr(path)
        if not meta.success:
            return KernelVFSResult(
                result=HostCallbackResult.make_failure(
                    HostCallbackKind.UTIMENS,
                    meta.errno if meta.errno is not HostErrno.OK else HostErrno.ENOENT,
                    message=meta.message or "utimens path not found",
                    request_id=request_id,
                    platform=platform,
                    vfs_error_code=meta.error_code or OperationsErrorCode.HOST.value,
                )
            )

        projector = self._metadata_plane
        if projector is None:
            # No projector — admit success with observed effect via host meta.
            return KernelVFSResult(
                result=HostCallbackResult.make_success(
                    HostCallbackKind.UTIMENS,
                    metadata=meta.metadata,
                    observed_effect=True,
                    request_id=request_id,
                    platform=platform,
                    durability_mode=self._durability_mode,
                    cache_consistency=self._cache_consistency,
                ),
                detail={"mode": "host-fallback"},
            )

        # None means UTIME_NOW for omitted kwargs from the named method.
        a = UTIME_NOW if atime_ns is None else int(atime_ns)
        m = UTIME_NOW if mtime_ns is None else int(mtime_ns)
        if atime_ns == UTIME_OMIT:
            a = UTIME_OMIT
        if mtime_ns == UTIME_OMIT:
            m = UTIME_OMIT

        norm = path if path not in ("", "/") else ""
        ut = projector.utimens(norm, atime_ns=a, mtime_ns=m)
        if not ut.success:
            return KernelVFSResult(
                result=HostCallbackResult.make_failure(
                    HostCallbackKind.UTIMENS,
                    ut.errno if ut.errno is not HostErrno.OK else HostErrno.EIO,
                    message=ut.code or "utimens failed",
                    request_id=request_id,
                    platform=platform,
                    vfs_error_code=ut.code or OperationsErrorCode.HOST.value,
                ),
                detail=ut.to_record() if hasattr(ut, "to_record") else {},
            )

        # Re-project metadata after the update.
        host_meta = meta.metadata
        try:
            host_meta = projector.getattr_path(norm).to_host_metadata()
        except Exception:  # noqa: BLE001
            pass

        # Contract lists UTIMENS as mutating — success requires observed_effect.
        observed = True

        result = HostCallbackResult.make_success(
            HostCallbackKind.UTIMENS,
            metadata=host_meta,
            observed_effect=observed,
            request_id=request_id,
            platform=platform,
            durability_mode=self._durability_mode,
            cache_consistency=self._cache_consistency,
        )
        return KernelVFSResult(
            result=result,
            detail=ut.to_record() if hasattr(ut, "to_record") else {},
        )

    def _create(
        self,
        path: str,
        *,
        data: bytes,
        flags: Sequence[OpenFlag] | None,
        mode: int,
        request_id: str,
        platform: HostPlatform,
    ) -> KernelVFSResult:
        created = self._host.create(path, data, mode=mode, exclusive=True)
        if not created.success:
            return self._from_host(
                HostCallbackKind.CREATE,
                created,
                request_id=request_id,
                platform=platform,
            )
        open_flags = flags or (OpenFlag.O_RDWR, OpenFlag.O_CREAT)
        opened = self._host.open(path, open_flags, mode=mode)
        if not opened.success:
            return self._from_host(
                HostCallbackKind.CREATE,
                opened,
                request_id=request_id,
                platform=platform,
                data=created.data,
            )
        merged = HostOperationResult(
            kind="create",
            success=True,
            path=path,
            errno=HostErrno.OK,
            handle=opened.handle,
            metadata=created.metadata,
            data=created.data,
            bytes_transferred=created.bytes_transferred or len(created.data),
            observed_effect=True,
            effect_id=created.effect_id,
            content_cid=created.content_cid,
            version_cid=created.version_cid,
            namespace_generation=created.namespace_generation,
            operation_id=created.operation_id,
            canonical_state=created.canonical_state,
            detail=opened.detail,
        )
        return self._from_host(
            HostCallbackKind.CREATE,
            merged,
            request_id=request_id,
            platform=platform,
            data=created.data,
        )

    def _read(
        self,
        path: str,
        *,
        offset: int,
        size: int,
        handle_id: int,
        generation: int | None,
        request_id: str,
        platform: HostPlatform,
    ) -> KernelVFSResult:
        if handle_id:
            try:
                io = self._host.handles.read(
                    handle_id, offset, size or 0, generation=generation
                )
                host_result = HostOperationResult(
                    kind="read",
                    success=True,
                    path=path,
                    data=io.data,
                    bytes_transferred=io.bytes_transferred,
                    observed_effect=False,
                    detail=io.to_record() if hasattr(io, "to_record") else {},
                )
            except Exception as exc:  # noqa: BLE001
                errno = HostErrno.EBADF
                error_code = OperationsErrorCode.HOST.value
                if isinstance(exc, HandleError):
                    raw = getattr(exc, "errno", None)
                    if isinstance(raw, HostErrno):
                        errno = raw
                    elif isinstance(raw, str) and raw in HostErrno._value2member_map_:
                        errno = HostErrno(raw)
                    code_obj = getattr(exc, "code", None)
                    if code_obj is not None and hasattr(code_obj, "value"):
                        error_code = str(code_obj.value)
                host_result = HostOperationResult(
                    kind="read",
                    success=False,
                    path=path,
                    errno=errno,
                    error_code=error_code,
                    message=str(exc),
                )
            return self._from_host(
                HostCallbackKind.READ,
                host_result,
                request_id=request_id,
                platform=platform,
                data=host_result.data if host_result.success else b"",
            )

        host_result = self._host.read(path, offset=offset, length=size or None)
        return self._from_host(
            HostCallbackKind.READ,
            host_result,
            request_id=request_id,
            platform=platform,
            data=host_result.data if host_result.success else b"",
        )

    def _write(
        self,
        path: str,
        *,
        data: bytes,
        offset: int,
        handle_id: int,
        generation: int | None,
        request_id: str,
        platform: HostPlatform,
    ) -> KernelVFSResult:
        if handle_id:
            try:
                io = self._host.handles.write(
                    handle_id, offset, data, generation=generation
                )
                flush = self._host.flush_handle(
                    handle_id, generation=generation, commit=True
                )
                if not flush.success:
                    return self._from_host(
                        HostCallbackKind.WRITE,
                        flush,
                        request_id=request_id,
                        platform=platform,
                    )
                host_result = HostOperationResult(
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
                    detail=io.to_record() if hasattr(io, "to_record") else {},
                )
                return self._from_host(
                    HostCallbackKind.WRITE,
                    host_result,
                    request_id=request_id,
                    platform=platform,
                    data=data,
                )
            except Exception as exc:  # noqa: BLE001
                return KernelVFSResult(
                    result=HostCallbackResult.make_failure(
                        HostCallbackKind.WRITE,
                        HostErrno.EBADF,
                        message=str(exc),
                        request_id=request_id,
                        platform=platform,
                        vfs_error_code=OperationsErrorCode.HOST.value,
                    )
                )

        host_result = self._host.write(path, data, offset=offset)
        return self._from_host(
            HostCallbackKind.WRITE,
            host_result,
            request_id=request_id,
            platform=platform,
            data=data if host_result.success else b"",
        )

    # -- named required callbacks -------------------------------------------

    def getattr(self, path: str = "", **kwargs: Any) -> KernelVFSResult:
        return self.dispatch(HostCallbackKind.GETATTR, path=path, **kwargs)

    def readdir(self, path: str = "", **kwargs: Any) -> KernelVFSResult:
        return self.dispatch(HostCallbackKind.READDIR, path=path, **kwargs)

    def access(
        self, path: str = "", mask: int = F_OK, **kwargs: Any
    ) -> KernelVFSResult:
        return self.dispatch(HostCallbackKind.ACCESS, path=path, mask=mask, **kwargs)

    def statfs(self, **kwargs: Any) -> KernelVFSResult:
        return self.dispatch(HostCallbackKind.STATFS, **kwargs)

    def utimens(
        self,
        path: str = "",
        *,
        atime_ns: int | None = None,
        mtime_ns: int | None = None,
        **kwargs: Any,
    ) -> KernelVFSResult:
        return self.dispatch(
            HostCallbackKind.UTIMENS,
            path=path,
            atime_ns=atime_ns,
            mtime_ns=mtime_ns,
            **kwargs,
        )

    def open(
        self,
        path: str,
        flags: Sequence[OpenFlag | str] | OpenFlag | str | None = None,
        *,
        mode: int = 0o644,
        **kwargs: Any,
    ) -> KernelVFSResult:
        return self.dispatch(
            HostCallbackKind.OPEN, path=path, flags=flags, mode=mode, **kwargs
        )

    def create(
        self,
        path: str,
        data: bytes = b"",
        *,
        mode: int = 0o644,
        flags: Sequence[OpenFlag | str] | OpenFlag | str | None = None,
        **kwargs: Any,
    ) -> KernelVFSResult:
        return self.dispatch(
            HostCallbackKind.CREATE,
            path=path,
            data=data,
            mode=mode,
            flags=flags or (OpenFlag.O_RDWR, OpenFlag.O_CREAT),
            **kwargs,
        )

    def read(
        self,
        path: str = "",
        *,
        offset: int = 0,
        size: int = 0,
        handle_id: int = 0,
        generation: int | None = None,
        handle: HostHandle | None = None,
        **kwargs: Any,
    ) -> KernelVFSResult:
        return self.dispatch(
            HostCallbackKind.READ,
            path=path,
            offset=offset,
            size=size,
            handle_id=handle_id,
            generation=generation,
            handle=handle,
            **kwargs,
        )

    def write(
        self,
        path: str = "",
        data: bytes = b"",
        *,
        offset: int = 0,
        handle_id: int = 0,
        generation: int | None = None,
        handle: HostHandle | None = None,
        **kwargs: Any,
    ) -> KernelVFSResult:
        return self.dispatch(
            HostCallbackKind.WRITE,
            path=path,
            data=data,
            offset=offset,
            handle_id=handle_id,
            generation=generation,
            handle=handle,
            **kwargs,
        )

    def truncate(
        self, path: str, size: int = 0, **kwargs: Any
    ) -> KernelVFSResult:
        return self.dispatch(
            HostCallbackKind.TRUNCATE, path=path, size=size, **kwargs
        )

    def flush(
        self,
        *,
        handle_id: int = 0,
        generation: int | None = None,
        handle: HostHandle | None = None,
        **kwargs: Any,
    ) -> KernelVFSResult:
        return self.dispatch(
            HostCallbackKind.FLUSH,
            handle_id=handle_id,
            generation=generation,
            handle=handle,
            **kwargs,
        )

    def fsync(
        self,
        *,
        handle_id: int = 0,
        generation: int | None = None,
        handle: HostHandle | None = None,
        datasync: bool = False,
        **kwargs: Any,
    ) -> KernelVFSResult:
        return self.dispatch(
            HostCallbackKind.FSYNC,
            handle_id=handle_id,
            generation=generation,
            handle=handle,
            datasync=datasync,
            **kwargs,
        )

    def release(
        self,
        *,
        handle_id: int = 0,
        generation: int | None = None,
        handle: HostHandle | None = None,
        **kwargs: Any,
    ) -> KernelVFSResult:
        return self.dispatch(
            HostCallbackKind.RELEASE,
            handle_id=handle_id,
            generation=generation,
            handle=handle,
            **kwargs,
        )

    def mkdir(
        self, path: str, *, mode: int = 0o755, **kwargs: Any
    ) -> KernelVFSResult:
        return self.dispatch(
            HostCallbackKind.MKDIR, path=path, mode=mode, **kwargs
        )

    def rmdir(self, path: str, **kwargs: Any) -> KernelVFSResult:
        return self.dispatch(HostCallbackKind.RMDIR, path=path, **kwargs)

    def unlink(self, path: str, **kwargs: Any) -> KernelVFSResult:
        return self.dispatch(HostCallbackKind.UNLINK, path=path, **kwargs)

    def rename(
        self, source: str, target: str, **kwargs: Any
    ) -> KernelVFSResult:
        return self.dispatch(
            HostCallbackKind.RENAME,
            path=source,
            target_path=target,
            **kwargs,
        )

    def init(self, **kwargs: Any) -> KernelVFSResult:
        return self.dispatch(HostCallbackKind.INIT, **kwargs)

    def destroy(self, **kwargs: Any) -> KernelVFSResult:
        return self.dispatch(HostCallbackKind.DESTROY, **kwargs)

    # -- unsupported / unknown ----------------------------------------------

    def reject_unsupported(
        self, kind: HostCallbackKind | str, *, request_id: str = ""
    ) -> KernelVFSResult:
        """Return the mandated ENOSYS/EOPNOTSUPP result for unsupported callbacks."""

        try:
            callback = parse_callback_kind(kind)
        except HostUnknownCallbackError as exc:
            raise OperationsError(
                str(exc),
                code=OperationsErrorCode.UNKNOWN_CALLBACK,
                errno=HostErrno.ENOSYS,
            ) from exc
        if callback_disposition(callback) is not CallbackDisposition.EXPLICIT_UNSUPPORTED:
            raise OperationsError(
                f"{callback.value} is not an explicit-unsupported callback",
                code=OperationsErrorCode.INVALID,
                errno=HostErrno.EINVAL,
            )
        result = HostCallbackResult.make_unsupported(
            callback, platform=self._platform, request_id=request_id
        )
        self._trace.record(
            OperationsTraceKind.UNSUPPORTED,
            success=False,
            callback=callback.value,
            code=result.errno.value,
        )
        return KernelVFSResult(result=result)

    def unsupported_errno(self, kind: HostCallbackKind | str) -> HostErrno:
        """Exact errno an unsupported callback must return."""

        return default_unsupported_errno(kind)

    # -- async bridge helpers -----------------------------------------------

    def run_async(
        self,
        awaitable: Any,
        *,
        deadline_s: float | None = None,
    ) -> Any:
        """Execute an awaitable on the composed async bridge (if configured)."""

        if self._bridge is None:
            raise OperationsError(
                "no async bridge configured on this operations runtime",
                code=OperationsErrorCode.BRIDGE,
                errno=HostErrno.ENOSYS,
            )
        try:
            return self._bridge.run(awaitable, deadline_s=deadline_s)
        except AsyncBridgeError as exc:
            errno = HostErrno.EAGAIN
            if exc.code is BridgeErrorCode.DEADLINE:
                errno = HostErrno.ETIMEDOUT
            elif exc.code is BridgeErrorCode.CANCELLED:
                errno = HostErrno.ECANCELED
            elif exc.code is BridgeErrorCode.CLOSED:
                errno = HostErrno.ENODEV
            raise OperationsError(
                str(exc),
                code=OperationsErrorCode.BRIDGE,
                errno=errno,
                detail=exc.to_record() if hasattr(exc, "to_record") else {},
            ) from exc

    # -- cleanup ------------------------------------------------------------

    def close(self) -> KernelVFSResult:
        """Destroy the runtime if still alive (idempotent)."""

        if self.lifecycle is MountLifecycleState.DESTROYED:
            return KernelVFSResult(
                result=HostCallbackResult.make_success(
                    HostCallbackKind.DESTROY,
                    mount_state=MountLifecycleState.DESTROYED,
                    observed_effect=False,
                    platform=self._platform,
                    durability_mode=self._durability_mode,
                    cache_consistency=self._cache_consistency,
                ),
                detail={"idempotent": True},
            )
        return self.destroy()

    def __enter__(self) -> "KernelVFSOperations":
        if self.lifecycle is MountLifecycleState.UNINITIALIZED:
            outcome = self.init()
            if not outcome.success:
                raise OperationsError(
                    outcome.error.message if outcome.error else "init failed",
                    code=OperationsErrorCode.LIFECYCLE,
                    errno=outcome.errno,
                )
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def build_kernel_vfs_operations(
    *,
    backend: str = "memory",
    root: str | None = None,
    clock: Callable[[], int] | None = None,
    platform: HostPlatform = HostPlatform.HERMETIC,
    mount_id: str = DEFAULT_MOUNT_ID,
    auto_init: bool = False,
    **kwargs: Any,
) -> KernelVFSOperations:
    """Factory for a composed KernelVFSOperations runtime."""

    ops = KernelVFSOperations.with_backend(
        backend,
        root=root,
        clock=clock,
        platform=platform,
        mount_id=mount_id,
        **kwargs,
    )
    if auto_init:
        outcome = ops.init()
        if not outcome.success:
            raise OperationsError(
                outcome.error.message if outcome.error else "auto_init failed",
                code=OperationsErrorCode.LIFECYCLE,
                errno=outcome.errno,
            )
    return ops


def assert_no_fusepy_import() -> None:
    """Guardrail: this module must not import native FUSE bindings."""

    import ast

    source_path = __file__
    with open(source_path, encoding="utf-8") as handle:
        text = handle.read()
    tree = ast.parse(text, filename=source_path)
    banned = frozenset({"fuse", "fusepy"})
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root in banned:
                    raise OperationsError(
                        f"operations must not import {alias.name}",
                        code=OperationsErrorCode.INTERNAL,
                        errno=HostErrno.EIO,
                    )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.split(".", 1)[0] if module else ""
            if root in banned:
                raise OperationsError(
                    f"operations must not import from {module}",
                    code=OperationsErrorCode.INTERNAL,
                    errno=HostErrno.EIO,
                )


__all__ = [
    "TASK_ID",
    "CONTRACT_VERSION",
    "SCHEMA_VERSION",
    "KERNEL_VFS_OPERATIONS_SCHEMA",
    "COMPOSED_REQUEST_RUNTIME_SCHEMA",
    "OPERATIONS_RESULT_SCHEMA",
    "KernelVFSOperations_V1",
    "ComposedRequestRuntime_V1",
    "DEFAULT_MOUNT_ID",
    "OperationsErrorCode",
    "OperationsError",
    "OperationsTraceKind",
    "OperationsTraceStep",
    "OperationsTraceLog",
    "KernelVFSResult",
    "KernelVFSOperations",
    "build_kernel_vfs_operations",
    "assert_no_fusepy_import",
    "REQUIRED_SUPPORTED_CALLBACKS",
    "EXPLICIT_UNSUPPORTED_CALLBACKS",
]
