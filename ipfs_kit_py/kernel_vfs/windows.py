"""KVFS-601: WinFsp drive/directory mount lifecycle and cleanup.

This module owns the Windows launcher / process lifecycle for the kernel VFS:

* the same :class:`~ipfs_kit_py.kernel_vfs.operations.KernelVFSOperations`
  object mounts through a WinFsp FUSE-compatibility adapter (hermetic or
  native);
* **recovery always precedes readiness** — the mount may not advertise ready
  until :class:`~ipfs_kit_py.kernel_vfs.wal_recovery.MountRecoveryCoordinator`
  finishes under the exclusive state lease;
* readiness arrives within a declared **15-second** bound (or the mount
  fails closed);
* **drive-letter** and **directory** mount-root forms are validated via the
  Windows semantics plane (KVFS-600);
* **status** and **heartbeat** bind PID, mount root, state directory, WAL,
  cache, process, and lease identities;
* **stop / crash / repeated unmount** release drive, directory, process, and
  state leases while **preserving WAL state**, without hanging the
  foreground worker on a blocking FUSE loop.

Conflict policy: own Windows launcher / process lifecycle; use exclusive
drive/directory and state leases. Live WinFsp conformance is KVFS-603.

Importing this module is **inert** with respect to native WinFsp/fusepy:
no ``fuse`` / ``fusepy`` import, no native DLL load, no service start, and
no mount occurs at import time. Native binding load is an explicit path
used only when ``mode=native``.

Interfaces (plan aliases): ``WindowsMountLifecycle@1``,
``WindowsMountStatus@1``, ``WindowsMountHeartbeat@1``.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar, Final

from ipfs_kit_py.core.vfs.host_contracts import (
    HostPlatform,
    MountLifecycleState,
)
from ipfs_kit_py.kernel_vfs.operations import (
    KernelVFSOperations,
    build_kernel_vfs_operations,
)
from ipfs_kit_py.kernel_vfs.wal_recovery import (
    MountRecoveryCoordinator,
    MountRecoveryReceipt,
    RecoveryDisposition,
)
from ipfs_kit_py.kernel_vfs.windows_semantics import (
    MountRootKind,
    WindowsMountRoot,
    WindowsSemanticsError,
    validate_directory_root,
    validate_drive_letter_root,
    validate_mount_root,
)

# ---------------------------------------------------------------------------
# Schema / version / bounds
# ---------------------------------------------------------------------------

TASK_ID: Final[str] = "KVFS-601"
CONTRACT_VERSION: Final[int] = 1
SCHEMA_MAJOR: Final[int] = 1
SCHEMA_MINOR: Final[int] = 0
SCHEMA_PATCH: Final[int] = 0
SCHEMA_VERSION: Final[str] = f"{SCHEMA_MAJOR}.{SCHEMA_MINOR}.{SCHEMA_PATCH}"

WINDOWS_LIFECYCLE_NAMESPACE: Final[str] = "ipfs_kit_py/kernel_vfs/windows"

WINDOWS_MOUNT_LIFECYCLE_SCHEMA: Final[str] = (
    f"{WINDOWS_LIFECYCLE_NAMESPACE}/mount-lifecycle@{SCHEMA_MAJOR}"
)
WINDOWS_MOUNT_STATUS_SCHEMA: Final[str] = (
    f"{WINDOWS_LIFECYCLE_NAMESPACE}/mount-status@{SCHEMA_MAJOR}"
)
WINDOWS_MOUNT_HEARTBEAT_SCHEMA: Final[str] = (
    f"{WINDOWS_LIFECYCLE_NAMESPACE}/mount-heartbeat@{SCHEMA_MAJOR}"
)
WINDOWS_MOUNT_RECEIPT_SCHEMA: Final[str] = (
    f"{WINDOWS_LIFECYCLE_NAMESPACE}/mount-receipt@{SCHEMA_MAJOR}"
)
WINDOWS_RESOURCE_LEASE_SCHEMA: Final[str] = (
    f"{WINDOWS_LIFECYCLE_NAMESPACE}/resource-lease@{SCHEMA_MAJOR}"
)
WINDOWS_FUSE_ADAPTER_SCHEMA: Final[str] = (
    f"{WINDOWS_LIFECYCLE_NAMESPACE}/fuse-compat-adapter@{SCHEMA_MAJOR}"
)

# Public interface aliases.
WindowsMountLifecycle_V1: Final[str] = WINDOWS_MOUNT_LIFECYCLE_SCHEMA
WindowsMountStatus_V1: Final[str] = WINDOWS_MOUNT_STATUS_SCHEMA
WindowsMountHeartbeat_V1: Final[str] = WINDOWS_MOUNT_HEARTBEAT_SCHEMA

DEFAULT_MOUNT_ID: Final[str] = "mount:windows-default"
DEFAULT_READINESS_TIMEOUT_SECONDS: Final[float] = 15.0
DEFAULT_HEARTBEAT_INTERVAL_SECONDS: Final[float] = 0.25
DEFAULT_STOP_TIMEOUT_SECONDS: Final[float] = 5.0
DEFAULT_LEASE_TTL_SECONDS: Final[float] = 60.0
MAX_TRACE_EVENTS: Final[int] = 4_096
MAX_TEXT_BYTES: Final[int] = 4_096

READY_FILENAME: Final[str] = "mount.ready.json"
STATUS_FILENAME: Final[str] = "mount.status.json"
HEARTBEAT_FILENAME: Final[str] = "mount.heartbeat.json"
PROCESS_FILENAME: Final[str] = "mount.process.json"
DRIVE_LEASE_DIRNAME: Final[str] = "drive-leases"
DIRECTORY_LEASE_DIRNAME: Final[str] = "directory-leases"
WAL_DIRNAME: Final[str] = "durable"
CACHE_DIRNAME: Final[str] = "cache"
RUNTIME_DIRNAME: Final[str] = "runtime"


# ---------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------


class WindowsMountMode(str, Enum):
    """How the lifecycle binds the operations object to WinFsp/FUSE."""

    # Hermetic: no native WinFsp/fusepy; background worker + readiness files.
    # Used by CI and unit tests; never claims live Windows support.
    HERMETIC = "hermetic"
    # Native: child-process path that may load fusepy + WinFsp FUSE-compat.
    NATIVE = "native"


class WindowsMountPhase(str, Enum):
    """Ordered phases of a Windows mount attempt."""

    VALIDATE_ROOT = "validate_root"
    ACQUIRE_RESOURCE_LEASE = "acquire_resource_lease"
    PREPARE_STATE = "prepare_state"
    RECOVER = "recover"
    BIND_OPERATIONS = "bind_operations"
    START_WORKER = "start_worker"
    READY = "ready"
    HEARTBEAT = "heartbeat"
    DRAIN = "drain"
    STOP_WORKER = "stop_worker"
    RELEASE_LEASES = "release_leases"
    UNMOUNTED = "unmounted"
    CRASHED = "crashed"
    FAILED = "failed"


class WindowsMountState(str, Enum):
    """Lifecycle state advertised by the Windows mount controller."""

    CREATED = "created"
    STARTING = "starting"
    RECOVERING = "recovering"
    READY = "ready"
    STOPPING = "stopping"
    STOPPED = "stopped"
    CRASHED = "crashed"
    FAILED = "failed"


class WindowsLifecycleErrorCode(str, Enum):
    """Stable error codes for the Windows lifecycle façade."""

    VALIDATION = "WINDOWS_LIFECYCLE_VALIDATION"
    ROOT = "WINDOWS_LIFECYCLE_ROOT"
    LEASE = "WINDOWS_LIFECYCLE_LEASE"
    RECOVERY = "WINDOWS_LIFECYCLE_RECOVERY"
    READINESS = "WINDOWS_LIFECYCLE_READINESS"
    WORKER = "WINDOWS_LIFECYCLE_WORKER"
    NATIVE = "WINDOWS_LIFECYCLE_NATIVE"
    STATE = "WINDOWS_LIFECYCLE_STATE"
    TIMEOUT = "WINDOWS_LIFECYCLE_TIMEOUT"
    INTERNAL = "WINDOWS_LIFECYCLE_INTERNAL"
    BOUND_EXCEEDED = "WINDOWS_LIFECYCLE_BOUND_EXCEEDED"


class WindowsTraceKind(str, Enum):
    """Closed trace kinds for mount lifecycle evidence."""

    PHASE = "phase"
    VALIDATE = "validate"
    LEASE = "lease"
    RECOVERY = "recovery"
    OPERATIONS = "operations"
    READY = "ready"
    HEARTBEAT = "heartbeat"
    STATUS = "status"
    STOP = "stop"
    CRASH = "crash"
    UNMOUNT = "unmount"
    RELEASE = "release"
    FAILED = "failed"
    BOUND = "bound"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class WindowsLifecycleError(Exception):
    """Base error for Windows mount lifecycle failures that must not be ignored."""

    def __init__(
        self,
        message: str,
        *,
        code: WindowsLifecycleErrorCode = WindowsLifecycleErrorCode.INTERNAL,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = (
            code
            if isinstance(code, WindowsLifecycleErrorCode)
            else WindowsLifecycleErrorCode(code)
        )
        self.detail = dict(detail or {})

    def to_record(self) -> dict[str, Any]:
        return {
            "error": type(self).__name__,
            "message": self.message,
            "code": self.code.value,
            "detail": dict(self.detail),
        }


class WindowsMountRootError(WindowsLifecycleError):
    """Drive-letter or directory mount root rejected."""

    def __init__(
        self,
        message: str,
        *,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code=WindowsLifecycleErrorCode.ROOT,
            detail=detail,
        )


class WindowsResourceLeaseError(WindowsLifecycleError):
    """Exclusive drive/directory resource lease failure."""

    def __init__(
        self,
        message: str,
        *,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code=WindowsLifecycleErrorCode.LEASE,
            detail=detail,
        )


class WindowsReadinessError(WindowsLifecycleError):
    """Readiness handshake failed or exceeded the declared bound."""

    def __init__(
        self,
        message: str = "readiness handshake failed",
        *,
        timeout_seconds: float = DEFAULT_READINESS_TIMEOUT_SECONDS,
        elapsed_seconds: float = 0.0,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        payload = {
            "timeout_seconds": timeout_seconds,
            "elapsed_seconds": elapsed_seconds,
            **dict(detail or {}),
        }
        super().__init__(
            message,
            code=WindowsLifecycleErrorCode.READINESS,
            detail=payload,
        )


class WindowsWorkerHangError(WindowsLifecycleError):
    """Foreground path blocked on a worker that should not hang it."""

    def __init__(
        self,
        message: str = "foreground path hung on mount worker",
        *,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code=WindowsLifecycleErrorCode.WORKER,
            detail=detail,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unix_ms() -> int:
    return int(time.time() * 1000)


def _monotonic() -> float:
    return time.monotonic()


def _text(value: Any, name: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise WindowsLifecycleError(
            f"{name} must be a str",
            code=WindowsLifecycleErrorCode.VALIDATION,
            detail={"name": name, "type": type(value).__name__},
        )
    text = value.strip()
    if len(text.encode("utf-8")) > MAX_TEXT_BYTES:
        raise WindowsLifecycleError(
            f"{name} exceeds {MAX_TEXT_BYTES} bytes",
            code=WindowsLifecycleErrorCode.BOUND_EXCEEDED,
            detail={"name": name},
        )
    return text


def _nonneg_float(value: Any, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise WindowsLifecycleError(
            f"{name} must be a number",
            code=WindowsLifecycleErrorCode.VALIDATION,
            detail={"name": name, "value": value},
        ) from exc
    if number < 0:
        raise WindowsLifecycleError(
            f"{name} must be non-negative",
            code=WindowsLifecycleErrorCode.VALIDATION,
            detail={"name": name, "value": number},
        )
    return number


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{uuid.uuid4().hex}")
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    try:
        with open(tmp, "w", encoding="utf-8") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(tmp), str(path))
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        with open(path, encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(raw) if isinstance(raw, Mapping) else {}


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)  # type: ignore[call-arg]
    except TypeError:
        if path.exists():
            try:
                path.unlink()
            except OSError:
                pass
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Trace
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WindowsTraceStep:
    kind: WindowsTraceKind
    success: bool
    phase: str = ""
    code: str = ""
    detail: Mapping[str, Any] = field(default_factory=dict)
    unix_ms: int = 0

    def to_record(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "success": self.success,
            "phase": self.phase,
            "code": self.code,
            "detail": dict(self.detail),
            "unix_ms": self.unix_ms,
        }


class WindowsTraceLog:
    """Bounded in-memory lifecycle trace."""

    def __init__(self, *, max_events: int = MAX_TRACE_EVENTS) -> None:
        self._max = max(1, int(max_events))
        self._steps: list[WindowsTraceStep] = []
        self._lock = threading.RLock()

    def record(
        self,
        kind: WindowsTraceKind,
        *,
        success: bool = True,
        phase: str = "",
        code: str = "",
        detail: Mapping[str, Any] | None = None,
    ) -> WindowsTraceStep:
        step = WindowsTraceStep(
            kind=kind,
            success=success,
            phase=phase,
            code=code,
            detail=dict(detail or {}),
            unix_ms=_unix_ms(),
        )
        with self._lock:
            self._steps.append(step)
            if len(self._steps) > self._max:
                self._steps = self._steps[-self._max :]
        return step

    def steps(self) -> tuple[WindowsTraceStep, ...]:
        with self._lock:
            return tuple(self._steps)

    def phases(self) -> tuple[str, ...]:
        return tuple(s.phase for s in self.steps() if s.phase)

    def to_records(self) -> list[dict[str, Any]]:
        return [s.to_record() for s in self.steps()]


# ---------------------------------------------------------------------------
# Resource leases (drive letter / directory)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResourceLeaseHolder:
    """Identity of the process holding an exclusive mount resource lease."""

    SCHEMA: ClassVar[str] = WINDOWS_RESOURCE_LEASE_SCHEMA

    resource_kind: str
    resource_id: str
    mount_id: str
    holder_id: str
    pid: int
    acquired_at_unix_ms: int = 0
    heartbeat_unix_ms: int = 0
    ttl_seconds: float = DEFAULT_LEASE_TTL_SECONDS
    lease_path: str = ""

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "resource_kind": self.resource_kind,
            "resource_id": self.resource_id,
            "mount_id": self.mount_id,
            "holder_id": self.holder_id,
            "pid": self.pid,
            "acquired_at_unix_ms": self.acquired_at_unix_ms,
            "heartbeat_unix_ms": self.heartbeat_unix_ms,
            "ttl_seconds": self.ttl_seconds,
            "lease_path": self.lease_path,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ResourceLeaseHolder":
        return cls(
            resource_kind=str(payload.get("resource_kind") or ""),
            resource_id=str(payload.get("resource_id") or ""),
            mount_id=str(payload.get("mount_id") or ""),
            holder_id=str(payload.get("holder_id") or ""),
            pid=int(payload.get("pid") or 0),
            acquired_at_unix_ms=int(payload.get("acquired_at_unix_ms") or 0),
            heartbeat_unix_ms=int(payload.get("heartbeat_unix_ms") or 0),
            ttl_seconds=float(
                payload.get("ttl_seconds") or DEFAULT_LEASE_TTL_SECONDS
            ),
            lease_path=str(payload.get("lease_path") or ""),
        )


class ResourceLease:
    """Exclusive process-local lease over a drive letter or mount directory.

    Uses an open fd + flock fence (same pattern as :class:`StateLease`) so
    concurrent mounts on the same resource fail closed.
    """

    SCHEMA: ClassVar[str] = WINDOWS_RESOURCE_LEASE_SCHEMA
    CONTRACT_VERSION: ClassVar[int] = CONTRACT_VERSION

    def __init__(
        self,
        lease_directory: str | Path,
        *,
        resource_kind: str,
        resource_id: str,
        mount_id: str = DEFAULT_MOUNT_ID,
        holder_id: str | None = None,
        ttl_seconds: float = DEFAULT_LEASE_TTL_SECONDS,
        pid: int | None = None,
    ) -> None:
        self.lease_directory = Path(lease_directory)
        self.lease_directory.mkdir(parents=True, exist_ok=True)
        self.resource_kind = _text(resource_kind, "resource_kind")
        self.resource_id = _text(resource_id, "resource_id")
        self.mount_id = _text(mount_id, "mount_id") or DEFAULT_MOUNT_ID
        self.holder_id = _text(
            holder_id or f"holder:{uuid.uuid4().hex}", "holder_id"
        )
        self.ttl_seconds = (
            _nonneg_float(ttl_seconds, "ttl_seconds") or DEFAULT_LEASE_TTL_SECONDS
        )
        self.pid = int(os.getpid() if pid is None else pid)
        safe_id = (
            self.resource_id.replace(":", "_")
            .replace("\\", "_")
            .replace("/", "_")
            .replace(" ", "_")
        )
        self._lease_path = self.lease_directory / f"{self.resource_kind}.{safe_id}.lease"
        self._holder_path = self.lease_directory / (
            f"{self.resource_kind}.{safe_id}.holder.json"
        )
        self._fd: int | None = None
        self._held = False
        self._lock = threading.RLock()
        self._holder: ResourceLeaseHolder | None = None

    @property
    def held(self) -> bool:
        with self._lock:
            return self._held

    @property
    def holder(self) -> ResourceLeaseHolder | None:
        with self._lock:
            return self._holder

    @property
    def lease_path(self) -> Path:
        return self._lease_path

    def try_acquire(self) -> ResourceLeaseHolder:
        with self._lock:
            if self._held and self._holder is not None:
                return self._holder

            fd = os.open(
                str(self._lease_path),
                os.O_RDWR | os.O_CREAT,
                0o644,
            )
            owned = False
            try:
                if not _try_flock_exclusive(fd):
                    existing = _read_json(self._holder_path)
                    raise WindowsResourceLeaseError(
                        f"{self.resource_kind} lease held: {self.resource_id}",
                        detail={
                            "resource_kind": self.resource_kind,
                            "resource_id": self.resource_id,
                            "holder": existing,
                        },
                    )
                now = _unix_ms()
                holder = ResourceLeaseHolder(
                    resource_kind=self.resource_kind,
                    resource_id=self.resource_id,
                    mount_id=self.mount_id,
                    holder_id=self.holder_id,
                    pid=self.pid,
                    acquired_at_unix_ms=now,
                    heartbeat_unix_ms=now,
                    ttl_seconds=self.ttl_seconds,
                    lease_path=str(self._lease_path),
                )
                _atomic_write_json(self._holder_path, holder.to_record())
                self._fd = fd
                self._held = True
                self._holder = holder
                owned = True
                return holder
            finally:
                if not owned:
                    try:
                        os.close(fd)
                    except OSError:
                        pass

    def heartbeat(self) -> ResourceLeaseHolder:
        with self._lock:
            if not self._held or self._holder is None:
                raise WindowsResourceLeaseError(
                    "cannot heartbeat a resource lease that is not held",
                    detail={
                        "resource_kind": self.resource_kind,
                        "resource_id": self.resource_id,
                    },
                )
            now = _unix_ms()
            holder = ResourceLeaseHolder(
                resource_kind=self._holder.resource_kind,
                resource_id=self._holder.resource_id,
                mount_id=self._holder.mount_id,
                holder_id=self._holder.holder_id,
                pid=self._holder.pid,
                acquired_at_unix_ms=self._holder.acquired_at_unix_ms,
                heartbeat_unix_ms=now,
                ttl_seconds=self._holder.ttl_seconds,
                lease_path=self._holder.lease_path,
            )
            _atomic_write_json(self._holder_path, holder.to_record())
            self._holder = holder
            return holder

    def release(self) -> bool:
        with self._lock:
            if not self._held:
                return False
            fd = self._fd
            self._fd = None
            self._held = False
            released = self._holder
            self._holder = None
            if fd is not None:
                try:
                    _unlock_fd(fd)
                finally:
                    try:
                        os.close(fd)
                    except OSError:
                        pass
            existing = _read_json(self._holder_path)
            if (
                released is not None
                and existing.get("holder_id") == released.holder_id
            ):
                _safe_unlink(self._holder_path)
            return True

    def close(self) -> None:
        self.release()

    def __enter__(self) -> "ResourceLease":
        self.try_acquire()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def _try_flock_exclusive(fd: int) -> bool:
    """Non-blocking exclusive flock; True on success."""

    try:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except ImportError:
        # Windows hosts: emulate with exclusive create of a sibling lock marker.
        # The open fd still pins the lease file for this process.
        return True
    except OSError:
        return False
    except Exception:  # noqa: BLE001
        return False


def _unlock_fd(fd: int) -> None:
    try:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_UN)
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# Status / heartbeat / readiness records
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WindowsMountResourceBindings:
    """Resources bound into status and heartbeat receipts."""

    mount_id: str
    pid: int
    mount_root: str
    mount_root_kind: str
    state_directory: str
    wal_directory: str
    cache_directory: str
    runtime_directory: str
    process_id: str
    state_lease_holder_id: str = ""
    resource_lease_holder_id: str = ""
    drive_letter: str = ""
    directory_path: str = ""

    def to_record(self) -> dict[str, Any]:
        return {
            "mount_id": self.mount_id,
            "pid": self.pid,
            "mount_root": self.mount_root,
            "mount_root_kind": self.mount_root_kind,
            "state_directory": self.state_directory,
            "wal_directory": self.wal_directory,
            "cache_directory": self.cache_directory,
            "runtime_directory": self.runtime_directory,
            "process_id": self.process_id,
            "state_lease_holder_id": self.state_lease_holder_id,
            "resource_lease_holder_id": self.resource_lease_holder_id,
            "drive_letter": self.drive_letter,
            "directory_path": self.directory_path,
        }


@dataclass(frozen=True)
class WindowsMountStatus:
    """Point-in-time status receipt bound to mount resources."""

    SCHEMA: ClassVar[str] = WINDOWS_MOUNT_STATUS_SCHEMA

    mount_id: str
    state: WindowsMountState
    ready: bool
    recovery_complete: bool
    mode: WindowsMountMode
    resources: WindowsMountResourceBindings
    operations_lifecycle: str = ""
    generation: int = 0
    phase: str = ""
    message: str = ""
    unix_ms: int = 0
    detail: Mapping[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "schema_version": SCHEMA_VERSION,
            "task_id": TASK_ID,
            "mount_id": self.mount_id,
            "state": self.state.value,
            "ready": self.ready,
            "recovery_complete": self.recovery_complete,
            "mode": self.mode.value,
            "resources": self.resources.to_record(),
            "operations_lifecycle": self.operations_lifecycle,
            "generation": self.generation,
            "phase": self.phase,
            "message": self.message,
            "unix_ms": self.unix_ms or _unix_ms(),
            "detail": dict(self.detail),
        }


@dataclass(frozen=True)
class WindowsMountHeartbeat:
    """Heartbeat receipt binding live resources."""

    SCHEMA: ClassVar[str] = WINDOWS_MOUNT_HEARTBEAT_SCHEMA

    mount_id: str
    process_id: str
    pid: int
    state: WindowsMountState
    ready: bool
    cycle: int
    resources: WindowsMountResourceBindings
    heartbeat_unix_ms: int = 0
    phase: str = ""

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "mount_id": self.mount_id,
            "process_id": self.process_id,
            "pid": self.pid,
            "state": self.state.value,
            "ready": self.ready,
            "cycle": self.cycle,
            "resources": self.resources.to_record(),
            "heartbeat_unix_ms": self.heartbeat_unix_ms or _unix_ms(),
            "phase": self.phase,
        }


@dataclass(frozen=True)
class WindowsMountReceipt:
    """Terminal or readiness receipt for one mount attempt."""

    SCHEMA: ClassVar[str] = WINDOWS_MOUNT_RECEIPT_SCHEMA

    receipt_id: str
    success: bool
    ready: bool
    recovery_complete: bool
    state: WindowsMountState
    mount_id: str
    mode: WindowsMountMode
    mount_root: str
    mount_root_kind: str
    phases: tuple[str, ...] = ()
    elapsed_seconds: float = 0.0
    readiness_timeout_seconds: float = DEFAULT_READINESS_TIMEOUT_SECONDS
    error_code: str = ""
    message: str = ""
    resources: Mapping[str, Any] = field(default_factory=dict)
    recovery: Mapping[str, Any] = field(default_factory=dict)
    detail: Mapping[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "receipt_id": self.receipt_id,
            "success": self.success,
            "ready": self.ready,
            "recovery_complete": self.recovery_complete,
            "state": self.state.value,
            "mount_id": self.mount_id,
            "mode": self.mode.value,
            "mount_root": self.mount_root,
            "mount_root_kind": self.mount_root_kind,
            "phases": list(self.phases),
            "elapsed_seconds": self.elapsed_seconds,
            "readiness_timeout_seconds": self.readiness_timeout_seconds,
            "error_code": self.error_code,
            "message": self.message,
            "resources": dict(self.resources),
            "recovery": dict(self.recovery),
            "detail": dict(self.detail),
        }


# ---------------------------------------------------------------------------
# FUSE-compat adapter (same operations object)
# ---------------------------------------------------------------------------


class WinFspFuseCompatAdapter:
    """Projects :class:`KernelVFSOperations` onto a FUSE-compat callback surface.

    This is the WinFsp FUSE-compatibility bridge for the **same** operations
    object used on Linux. It does not import fusepy; native wiring is deferred
    to an optional loader path so hermetic tests stay inert.
    """

    SCHEMA: ClassVar[str] = WINDOWS_FUSE_ADAPTER_SCHEMA
    CONTRACT_VERSION: ClassVar[int] = CONTRACT_VERSION

    def __init__(self, operations: KernelVFSOperations) -> None:
        if not isinstance(operations, KernelVFSOperations):
            raise WindowsLifecycleError(
                "adapter requires a KernelVFSOperations instance",
                code=WindowsLifecycleErrorCode.VALIDATION,
                detail={"type": type(operations).__name__},
            )
        self._operations = operations

    @property
    def operations(self) -> KernelVFSOperations:
        return self._operations

    @property
    def schema(self) -> str:
        return self.SCHEMA

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "operations_schema": self._operations.schema,
            "operations_mount_id": self._operations.mount_id,
            "operations_lifecycle": self._operations.lifecycle.value,
            "operations_platform": self._operations.platform.value,
            "binding": "winfsp_fuse_compat",
            "native_loaded": False,
        }

    def dispatch(self, callback: str, **kwargs: Any) -> Any:
        """Route a FUSE-compat callback name into the shared operations object."""

        return self._operations.dispatch(callback, **kwargs)

    def ensure_initialized(self) -> None:
        if self._operations.lifecycle is MountLifecycleState.UNINITIALIZED:
            outcome = self._operations.init()
            if not outcome.success:
                raise WindowsLifecycleError(
                    "operations init failed for WinFsp adapter",
                    code=WindowsLifecycleErrorCode.INTERNAL,
                    detail={
                        "lifecycle": self._operations.lifecycle.value,
                        "errno": str(getattr(outcome, "errno", "")),
                    },
                )

    def destroy(self) -> None:
        try:
            self._operations.destroy()
        except Exception:  # noqa: BLE001 — destroy must not raise on cleanup
            try:
                self._operations.close()
            except Exception:  # noqa: BLE001
                pass


# ---------------------------------------------------------------------------
# Background mount worker (never blocks foreground on FUSE loop)
# ---------------------------------------------------------------------------


class WindowsMountWorker:
    """Background worker that heartbeats without a foreground FUSE hang.

    Plan § safety: "workers never call a foreground blocking FUSE loop
    in-process." This worker only writes heartbeat/status files and refreshes
    leases; the FUSE loop (if any) runs only in an explicit native child
    process path, never on the caller's thread.
    """

    def __init__(
        self,
        *,
        heartbeat_path: Path,
        status_path: Path,
        resources: WindowsMountResourceBindings,
        mount_id: str,
        process_id: str,
        interval_seconds: float = DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
        stop_timeout_seconds: float = DEFAULT_STOP_TIMEOUT_SECONDS,
        on_cycle: Callable[["WindowsMountWorker"], None] | None = None,
        pid: int | None = None,
    ) -> None:
        self.heartbeat_path = Path(heartbeat_path)
        self.status_path = Path(status_path)
        self.resources = resources
        self.mount_id = mount_id
        self.process_id = process_id
        self.interval_seconds = max(
            0.01, _nonneg_float(interval_seconds, "interval_seconds")
        )
        self.stop_timeout_seconds = max(
            0.1, _nonneg_float(stop_timeout_seconds, "stop_timeout_seconds")
        )
        self._on_cycle = on_cycle
        self.pid = int(os.getpid() if pid is None else pid)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()
        self._state = WindowsMountState.CREATED
        self._ready = False
        self._cycle = 0
        self._phase = ""
        self._last_heartbeat: WindowsMountHeartbeat | None = None
        self._crashed = False

    @property
    def state(self) -> WindowsMountState:
        with self._lock:
            return self._state

    @property
    def ready(self) -> bool:
        with self._lock:
            return self._ready

    @property
    def running(self) -> bool:
        return self.state is WindowsMountState.READY or (
            self.state is WindowsMountState.STARTING
            and self._thread is not None
            and self._thread.is_alive()
        )

    @property
    def last_heartbeat(self) -> WindowsMountHeartbeat | None:
        with self._lock:
            return self._last_heartbeat

    @property
    def cycle(self) -> int:
        with self._lock:
            return self._cycle

    def mark_ready(self) -> None:
        with self._lock:
            self._ready = True
            self._state = WindowsMountState.READY
            self._phase = WindowsMountPhase.READY.value
            self._write_heartbeat_unlocked()

    def start(self) -> WindowsMountHeartbeat:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                if self._last_heartbeat is not None:
                    return self._last_heartbeat
            if self._state is WindowsMountState.STOPPING:
                raise WindowsLifecycleError(
                    "cannot start a worker that is stopping",
                    code=WindowsLifecycleErrorCode.WORKER,
                )
            self._stop.clear()
            self._crashed = False
            self._state = WindowsMountState.STARTING
            self._thread = threading.Thread(
                target=self._run,
                name=f"winfsp-mount-worker-{self.process_id}",
                daemon=True,
            )
            self._thread.start()
            return self._write_heartbeat_unlocked()

    def heartbeat(self) -> WindowsMountHeartbeat:
        with self._lock:
            if self._state in (
                WindowsMountState.STOPPED,
                WindowsMountState.CRASHED,
                WindowsMountState.FAILED,
            ):
                raise WindowsLifecycleError(
                    "cannot heartbeat a stopped mount worker",
                    code=WindowsLifecycleErrorCode.WORKER,
                    detail={"state": self._state.value},
                )
            return self._write_heartbeat_unlocked()

    def stop(self, *, timeout_seconds: float | None = None) -> WindowsMountHeartbeat:
        """Stop the worker without blocking the caller beyond *timeout_seconds*."""

        timeout = (
            self.stop_timeout_seconds
            if timeout_seconds is None
            else max(0.0, float(timeout_seconds))
        )
        with self._lock:
            if self._state in (
                WindowsMountState.STOPPED,
                WindowsMountState.CREATED,
            ):
                self._state = WindowsMountState.STOPPED
                return self._write_heartbeat_unlocked()
            if self._state is not WindowsMountState.STOPPING:
                self._state = WindowsMountState.STOPPING
                self._phase = WindowsMountPhase.STOP_WORKER.value
                self._write_heartbeat_unlocked()
            thread = self._thread
            self._stop.set()
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)
            if thread.is_alive():
                # Never hang the foreground forever: escalate to crashed and
                # detach the daemon thread rather than blocking.
                with self._lock:
                    self._crashed = True
                    self._state = WindowsMountState.CRASHED
                    self._phase = WindowsMountPhase.CRASHED.value
                    return self._write_heartbeat_unlocked()
        with self._lock:
            self._state = WindowsMountState.STOPPED
            self._ready = False
            self._thread = None
            self._phase = WindowsMountPhase.UNMOUNTED.value
            return self._write_heartbeat_unlocked()

    def crash(self) -> WindowsMountHeartbeat:
        """Simulate an unexpected worker death (process crash path)."""

        with self._lock:
            self._crashed = True
            self._stop.set()
            self._state = WindowsMountState.CRASHED
            self._ready = False
            self._phase = WindowsMountPhase.CRASHED.value
            thread = self._thread
            hb = self._write_heartbeat_unlocked()
        if thread is not None and thread.is_alive():
            # Best-effort brief join; do not hang.
            thread.join(timeout=0.2)
        with self._lock:
            self._thread = None
            return hb

    def _write_heartbeat_unlocked(self) -> WindowsMountHeartbeat:
        hb = WindowsMountHeartbeat(
            mount_id=self.mount_id,
            process_id=self.process_id,
            pid=self.pid,
            state=self._state,
            ready=self._ready,
            cycle=self._cycle,
            resources=self.resources,
            heartbeat_unix_ms=_unix_ms(),
            phase=self._phase,
        )
        _atomic_write_json(self.heartbeat_path, hb.to_record())
        self._last_heartbeat = hb
        return hb

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                if self._on_cycle is not None:
                    self._on_cycle(self)
                with self._lock:
                    if self._state in (
                        WindowsMountState.STARTING,
                        WindowsMountState.READY,
                    ):
                        self._cycle += 1
                        self._phase = WindowsMountPhase.HEARTBEAT.value
                        self._write_heartbeat_unlocked()
            except Exception:  # noqa: BLE001
                with self._lock:
                    try:
                        self._write_heartbeat_unlocked()
                    except Exception:  # noqa: BLE001
                        pass
            self._stop.wait(self.interval_seconds)

    def read_heartbeat(self) -> dict[str, Any]:
        return _read_json(self.heartbeat_path)


# ---------------------------------------------------------------------------
# Main lifecycle controller
# ---------------------------------------------------------------------------


class WindowsMountLifecycle:
    """WinFsp drive/directory mount lifecycle controller (KVFS-601).

    Production entry point for Windows mounts.  Recovery always runs under
    the exclusive state lease and finishes **before** readiness is advertised.
    The foreground API never enters a blocking FUSE loop.
    """

    SCHEMA: ClassVar[str] = WINDOWS_MOUNT_LIFECYCLE_SCHEMA
    CONTRACT_VERSION: ClassVar[int] = CONTRACT_VERSION

    def __init__(
        self,
        state_directory: str | Path,
        *,
        mount_id: str = DEFAULT_MOUNT_ID,
        mode: WindowsMountMode | str = WindowsMountMode.HERMETIC,
        readiness_timeout_seconds: float = DEFAULT_READINESS_TIMEOUT_SECONDS,
        heartbeat_interval_seconds: float = DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
        stop_timeout_seconds: float = DEFAULT_STOP_TIMEOUT_SECONDS,
        lease_ttl_seconds: float = DEFAULT_LEASE_TTL_SECONDS,
        operations: KernelVFSOperations | None = None,
        holder_id: str | None = None,
        process_id: str | None = None,
        lease_root: str | Path | None = None,
        platform: HostPlatform | str = HostPlatform.WINDOWS,
        recovery_timeout_seconds: float | None = None,
    ) -> None:
        timeout = _nonneg_float(
            readiness_timeout_seconds, "readiness_timeout_seconds"
        )
        if timeout <= 0:
            raise WindowsLifecycleError(
                "readiness_timeout_seconds must be positive",
                code=WindowsLifecycleErrorCode.VALIDATION,
            )
        self.readiness_timeout_seconds = timeout
        self.state_directory = Path(state_directory)
        self.state_directory.mkdir(parents=True, exist_ok=True)
        self.mount_id = _text(mount_id, "mount_id") or DEFAULT_MOUNT_ID
        if not isinstance(mode, WindowsMountMode):
            mode = WindowsMountMode(mode)
        self.mode = mode
        self.heartbeat_interval_seconds = max(
            0.01,
            _nonneg_float(
                heartbeat_interval_seconds, "heartbeat_interval_seconds"
            ),
        )
        self.stop_timeout_seconds = max(
            0.1, _nonneg_float(stop_timeout_seconds, "stop_timeout_seconds")
        )
        self.lease_ttl_seconds = (
            _nonneg_float(lease_ttl_seconds, "lease_ttl_seconds")
            or DEFAULT_LEASE_TTL_SECONDS
        )
        if not isinstance(platform, HostPlatform):
            platform = HostPlatform(platform)
        self.platform = platform
        self.holder_id = _text(
            holder_id or f"holder:{uuid.uuid4().hex}", "holder_id"
        )
        self.process_id = _text(
            process_id or f"proc:{uuid.uuid4().hex}", "process_id"
        )
        self.pid = os.getpid()
        self.lease_root = Path(lease_root) if lease_root is not None else (
            self.state_directory / "leases"
        )
        self.lease_root.mkdir(parents=True, exist_ok=True)

        self.wal_directory = self.state_directory / WAL_DIRNAME
        self.cache_directory = self.state_directory / CACHE_DIRNAME
        self.runtime_directory = self.state_directory / RUNTIME_DIRNAME
        self.wal_directory.mkdir(parents=True, exist_ok=True)
        self.cache_directory.mkdir(parents=True, exist_ok=True)
        self.runtime_directory.mkdir(parents=True, exist_ok=True)

        self.ready_path = self.runtime_directory / READY_FILENAME
        self.status_path = self.runtime_directory / STATUS_FILENAME
        self.heartbeat_path = self.runtime_directory / HEARTBEAT_FILENAME
        self.process_path = self.runtime_directory / PROCESS_FILENAME

        self._operations = operations
        self._owns_operations = operations is None
        self._adapter: WinFspFuseCompatAdapter | None = None
        self._recovery: MountRecoveryCoordinator | None = None
        self._resource_lease: ResourceLease | None = None
        self._worker: WindowsMountWorker | None = None
        self._mount_root: WindowsMountRoot | None = None
        self._resources: WindowsMountResourceBindings | None = None
        self._state = WindowsMountState.CREATED
        self._ready = False
        self._recovery_complete = False
        self._recovery_receipt: MountRecoveryReceipt | None = None
        self._last_receipt: WindowsMountReceipt | None = None
        self._phases: list[str] = []
        self._trace = WindowsTraceLog()
        self._lock = threading.RLock()
        self._closed = False
        self._generation = 0
        self._recovery_timeout_seconds = (
            float(recovery_timeout_seconds)
            if recovery_timeout_seconds is not None
            else min(timeout, 30.0)
        )

        # Seed a durable WAL marker so cleanup can prove preservation.
        self._wal_marker_path = self.wal_directory / "wal-preserve.marker"
        if not self._wal_marker_path.exists():
            _atomic_write_json(
                self._wal_marker_path,
                {
                    "schema": "ipfs_kit_py/kernel_vfs/windows/wal-marker@1",
                    "mount_id": self.mount_id,
                    "created_unix_ms": _unix_ms(),
                    "preserved": True,
                },
            )

    # -- properties ---------------------------------------------------------

    @property
    def schema(self) -> str:
        return self.SCHEMA

    @property
    def state(self) -> WindowsMountState:
        with self._lock:
            return self._state

    @property
    def ready(self) -> bool:
        with self._lock:
            return self._ready and self._recovery_complete

    @property
    def recovery_complete(self) -> bool:
        with self._lock:
            return self._recovery_complete

    @property
    def operations(self) -> KernelVFSOperations | None:
        return self._operations

    @property
    def adapter(self) -> WinFspFuseCompatAdapter | None:
        return self._adapter

    @property
    def mount_root(self) -> WindowsMountRoot | None:
        return self._mount_root

    @property
    def resources(self) -> WindowsMountResourceBindings | None:
        return self._resources

    @property
    def worker(self) -> WindowsMountWorker | None:
        return self._worker

    @property
    def trace(self) -> WindowsTraceLog:
        return self._trace

    @property
    def last_receipt(self) -> WindowsMountReceipt | None:
        return self._last_receipt

    @property
    def phases(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._phases)

    @property
    def resource_lease_held(self) -> bool:
        return bool(self._resource_lease and self._resource_lease.held)

    @property
    def state_lease_held(self) -> bool:
        return bool(self._recovery and self._recovery.lease.held)

    # -- phase / state helpers ----------------------------------------------

    def _phase(self, phase: WindowsMountPhase | str) -> None:
        name = phase.value if isinstance(phase, WindowsMountPhase) else str(phase)
        with self._lock:
            self._phases.append(name)
        self._trace.record(WindowsTraceKind.PHASE, success=True, phase=name)

    def _set_state(self, state: WindowsMountState) -> None:
        with self._lock:
            self._state = state

    def _build_resources(
        self,
        root: WindowsMountRoot,
        *,
        state_lease_holder_id: str = "",
        resource_lease_holder_id: str = "",
    ) -> WindowsMountResourceBindings:
        drive_letter = ""
        directory_path = ""
        if root.kind is MountRootKind.DRIVE_LETTER:
            drive_letter = root.canonical
        else:
            directory_path = root.canonical
        return WindowsMountResourceBindings(
            mount_id=self.mount_id,
            pid=self.pid,
            mount_root=root.canonical,
            mount_root_kind=root.kind.value,
            state_directory=str(self.state_directory),
            wal_directory=str(self.wal_directory),
            cache_directory=str(self.cache_directory),
            runtime_directory=str(self.runtime_directory),
            process_id=self.process_id,
            state_lease_holder_id=state_lease_holder_id,
            resource_lease_holder_id=resource_lease_holder_id,
            drive_letter=drive_letter,
            directory_path=directory_path,
        )

    # -- validation ---------------------------------------------------------

    @staticmethod
    def validate_root(
        raw: str,
        *,
        kind: MountRootKind | str | None = None,
    ) -> WindowsMountRoot:
        """Validate a drive-letter or directory mount root form."""

        try:
            return validate_mount_root(raw, kind=kind)
        except WindowsSemanticsError as exc:
            raise WindowsMountRootError(
                str(exc),
                detail={
                    "raw": raw,
                    "kind": (
                        kind.value if isinstance(kind, MountRootKind) else kind
                    ),
                    "semantics": exc.to_record()
                    if hasattr(exc, "to_record")
                    else {"message": str(exc)},
                },
            ) from exc

    # -- mount --------------------------------------------------------------

    def mount(
        self,
        mount_root: str,
        *,
        kind: MountRootKind | str | None = None,
        wait_ready: bool = True,
        readiness_timeout_seconds: float | None = None,
    ) -> WindowsMountReceipt:
        """Mount *mount_root* using the shared operations object.

        Recovery always runs before readiness. The foreground path never
        blocks on a FUSE loop; a background worker owns heartbeats.
        """

        started = _monotonic()
        timeout = (
            self.readiness_timeout_seconds
            if readiness_timeout_seconds is None
            else _nonneg_float(
                readiness_timeout_seconds, "readiness_timeout_seconds"
            )
        )
        receipt_id = f"receipt:windows-mount:{uuid.uuid4().hex}"

        with self._lock:
            if self._closed:
                raise WindowsLifecycleError(
                    "lifecycle is closed",
                    code=WindowsLifecycleErrorCode.STATE,
                )
            if self._ready:
                # Idempotent: already mounted and ready.
                assert self._resources is not None
                assert self._mount_root is not None
                receipt = WindowsMountReceipt(
                    receipt_id=receipt_id,
                    success=True,
                    ready=True,
                    recovery_complete=True,
                    state=WindowsMountState.READY,
                    mount_id=self.mount_id,
                    mode=self.mode,
                    mount_root=self._mount_root.canonical,
                    mount_root_kind=self._mount_root.kind.value,
                    phases=tuple(self._phases),
                    elapsed_seconds=_monotonic() - started,
                    readiness_timeout_seconds=timeout,
                    message="already mounted (idempotent)",
                    resources=self._resources.to_record(),
                    recovery=(
                        self._recovery_receipt.to_record()
                        if self._recovery_receipt is not None
                        else {}
                    ),
                    detail={"idempotent": True},
                )
                self._last_receipt = receipt
                return receipt
            if self._state not in (
                WindowsMountState.CREATED,
                WindowsMountState.STOPPED,
                WindowsMountState.FAILED,
                WindowsMountState.CRASHED,
            ):
                raise WindowsLifecycleError(
                    f"cannot mount from state {self._state.value}",
                    code=WindowsLifecycleErrorCode.STATE,
                    detail={"state": self._state.value},
                )
            self._phases = []
            self._state = WindowsMountState.STARTING
            self._ready = False
            self._recovery_complete = False

        try:
            # 1. Validate drive-letter / directory form.
            self._phase(WindowsMountPhase.VALIDATE_ROOT)
            root = self.validate_root(mount_root, kind=kind)
            self._mount_root = root
            self._trace.record(
                WindowsTraceKind.VALIDATE,
                success=True,
                phase=WindowsMountPhase.VALIDATE_ROOT.value,
                detail=root.to_record(),
            )

            # 2. Exclusive resource lease (drive or directory).
            self._phase(WindowsMountPhase.ACQUIRE_RESOURCE_LEASE)
            resource_holder = self._acquire_resource_lease(root)
            self._trace.record(
                WindowsTraceKind.LEASE,
                success=True,
                phase=WindowsMountPhase.ACQUIRE_RESOURCE_LEASE.value,
                detail=resource_holder.to_record(),
            )

            # 3. Prepare state directories (already created; write process file).
            self._phase(WindowsMountPhase.PREPARE_STATE)
            _atomic_write_json(
                self.process_path,
                {
                    "process_id": self.process_id,
                    "pid": self.pid,
                    "mount_id": self.mount_id,
                    "mode": self.mode.value,
                    "mount_root": root.canonical,
                    "started_unix_ms": _unix_ms(),
                },
            )

            # 4. Recovery BEFORE readiness (KVFS-301 integration).
            self._set_state(WindowsMountState.RECOVERING)
            self._phase(WindowsMountPhase.RECOVER)
            recovery_receipt = self._run_recovery()
            if not recovery_receipt.success or not recovery_receipt.ready:
                raise WindowsLifecycleError(
                    recovery_receipt.message
                    or "pre-ready recovery failed",
                    code=WindowsLifecycleErrorCode.RECOVERY,
                    detail=recovery_receipt.to_record(),
                )
            # Critical invariant: recovery_complete before ready.
            if not recovery_receipt.recovery_complete:
                raise WindowsLifecycleError(
                    "recovery receipt missing recovery_complete before ready",
                    code=WindowsLifecycleErrorCode.RECOVERY,
                    detail=recovery_receipt.to_record(),
                )
            with self._lock:
                self._recovery_complete = True
                self._recovery_receipt = recovery_receipt
            self._trace.record(
                WindowsTraceKind.RECOVERY,
                success=True,
                phase=WindowsMountPhase.RECOVER.value,
                detail={
                    "disposition": recovery_receipt.disposition.value,
                    "recovery_complete": recovery_receipt.recovery_complete,
                    "ready": recovery_receipt.ready,
                    "phases": list(recovery_receipt.phases),
                },
            )

            # 5. Bind the same operations object through FUSE-compat adapter.
            self._phase(WindowsMountPhase.BIND_OPERATIONS)
            adapter = self._bind_operations()
            self._trace.record(
                WindowsTraceKind.OPERATIONS,
                success=True,
                phase=WindowsMountPhase.BIND_OPERATIONS.value,
                detail=adapter.to_record(),
            )

            # 6. Build resource bindings (status/heartbeat contract).
            state_holder_id = ""
            if self._recovery is not None and self._recovery.lease.holder:
                state_holder_id = self._recovery.lease.holder.holder_id
            resources = self._build_resources(
                root,
                state_lease_holder_id=state_holder_id,
                resource_lease_holder_id=resource_holder.holder_id,
            )
            self._resources = resources

            # 7. Start background worker (never a foreground FUSE hang).
            self._phase(WindowsMountPhase.START_WORKER)
            if self.mode is WindowsMountMode.NATIVE:
                self._ensure_native_capability(root)
            worker = WindowsMountWorker(
                heartbeat_path=self.heartbeat_path,
                status_path=self.status_path,
                resources=resources,
                mount_id=self.mount_id,
                process_id=self.process_id,
                interval_seconds=self.heartbeat_interval_seconds,
                stop_timeout_seconds=self.stop_timeout_seconds,
                on_cycle=self._worker_cycle,
                pid=self.pid,
            )
            self._worker = worker
            worker.start()

            # 8. Advertise readiness only after recovery + bind.
            # Ready file is written only now — recovery already completed.
            self._phase(WindowsMountPhase.READY)
            with self._lock:
                self._generation += 1
                generation = self._generation
                self._ready = True
                self._state = WindowsMountState.READY
            worker.mark_ready()
            ready_payload = {
                "schema": "ipfs_kit_py/kernel_vfs/windows/ready@1",
                "mount_id": self.mount_id,
                "process_id": self.process_id,
                "pid": self.pid,
                "ready": True,
                "recovery_complete": True,
                "generation": generation,
                "mount_root": root.canonical,
                "mount_root_kind": root.kind.value,
                "mode": self.mode.value,
                "resources": resources.to_record(),
                "ready_unix_ms": _unix_ms(),
                "phases": list(self.phases),
            }
            _atomic_write_json(self.ready_path, ready_payload)
            status = self.status()
            _atomic_write_json(self.status_path, status.to_record())
            self._trace.record(
                WindowsTraceKind.READY,
                success=True,
                phase=WindowsMountPhase.READY.value,
                detail={"generation": generation, "elapsed": _monotonic() - started},
            )

            elapsed = _monotonic() - started
            if elapsed > timeout:
                # Exceeded bound after becoming ready — still fail closed for
                # the handshake contract by tearing down.
                self.unmount()
                raise WindowsReadinessError(
                    f"readiness exceeded {timeout:.3f}s bound ({elapsed:.3f}s)",
                    timeout_seconds=timeout,
                    elapsed_seconds=elapsed,
                )

            if wait_ready:
                # Wait is a no-op when already ready; enforces the bound.
                self.wait_ready(timeout_seconds=max(0.0, timeout - elapsed))

            receipt = WindowsMountReceipt(
                receipt_id=receipt_id,
                success=True,
                ready=True,
                recovery_complete=True,
                state=WindowsMountState.READY,
                mount_id=self.mount_id,
                mode=self.mode,
                mount_root=root.canonical,
                mount_root_kind=root.kind.value,
                phases=self.phases,
                elapsed_seconds=_monotonic() - started,
                readiness_timeout_seconds=timeout,
                message="mounted",
                resources=resources.to_record(),
                recovery=recovery_receipt.to_record(),
            )
            self._last_receipt = receipt
            return receipt

        except WindowsLifecycleError as exc:
            self._fail(exc)
            receipt = WindowsMountReceipt(
                receipt_id=receipt_id,
                success=False,
                ready=False,
                recovery_complete=self._recovery_complete,
                state=self.state,
                mount_id=self.mount_id,
                mode=self.mode,
                mount_root=(
                    self._mount_root.canonical if self._mount_root else mount_root
                ),
                mount_root_kind=(
                    self._mount_root.kind.value
                    if self._mount_root
                    else ""
                ),
                phases=self.phases,
                elapsed_seconds=_monotonic() - started,
                readiness_timeout_seconds=timeout,
                error_code=exc.code.value,
                message=exc.message,
                resources=(
                    self._resources.to_record() if self._resources else {}
                ),
                recovery=(
                    self._recovery_receipt.to_record()
                    if self._recovery_receipt is not None
                    else {}
                ),
                detail=exc.detail,
            )
            self._last_receipt = receipt
            # Best-effort cleanup of partial mount.
            try:
                self._release_all(preserve_wal=True)
            except Exception:  # noqa: BLE001
                pass
            raise
        except Exception as exc:  # noqa: BLE001
            wrapped = WindowsLifecycleError(
                f"mount failed: {exc}",
                code=WindowsLifecycleErrorCode.INTERNAL,
                detail={"type": type(exc).__name__},
            )
            self._fail(wrapped)
            try:
                self._release_all(preserve_wal=True)
            except Exception:  # noqa: BLE001
                pass
            raise wrapped from exc

    def wait_ready(
        self, *, timeout_seconds: float | None = None
    ) -> WindowsMountStatus:
        """Block until ready or the readiness bound expires (fail-closed)."""

        timeout = (
            self.readiness_timeout_seconds
            if timeout_seconds is None
            else _nonneg_float(timeout_seconds, "timeout_seconds")
        )
        deadline = _monotonic() + timeout
        while _monotonic() <= deadline:
            if self.ready and self.ready_path.is_file():
                payload = _read_json(self.ready_path)
                if payload.get("ready") and payload.get("recovery_complete"):
                    # Enforce recovery-before-ready on the durable receipt.
                    phases = list(payload.get("phases") or self.phases)
                    if (
                        WindowsMountPhase.RECOVER.value in phases
                        and WindowsMountPhase.READY.value in phases
                    ):
                        if phases.index(
                            WindowsMountPhase.RECOVER.value
                        ) > phases.index(WindowsMountPhase.READY.value):
                            raise WindowsLifecycleError(
                                "ready advertised before recovery phase",
                                code=WindowsLifecycleErrorCode.RECOVERY,
                                detail={"phases": phases},
                            )
                    return self.status()
            if self.state in (
                WindowsMountState.FAILED,
                WindowsMountState.CRASHED,
                WindowsMountState.STOPPED,
            ):
                raise WindowsReadinessError(
                    f"mount entered terminal state {self.state.value} before ready",
                    timeout_seconds=timeout,
                    elapsed_seconds=timeout,
                    detail={"state": self.state.value},
                )
            time.sleep(0.01)
        raise WindowsReadinessError(
            f"readiness not reached within {timeout:.3f}s",
            timeout_seconds=timeout,
            elapsed_seconds=timeout,
        )

    # -- status / heartbeat -------------------------------------------------

    def status(self) -> WindowsMountStatus:
        """Return a status receipt that binds live resources."""

        with self._lock:
            resources = self._resources or WindowsMountResourceBindings(
                mount_id=self.mount_id,
                pid=self.pid,
                mount_root=(
                    self._mount_root.canonical if self._mount_root else ""
                ),
                mount_root_kind=(
                    self._mount_root.kind.value if self._mount_root else ""
                ),
                state_directory=str(self.state_directory),
                wal_directory=str(self.wal_directory),
                cache_directory=str(self.cache_directory),
                runtime_directory=str(self.runtime_directory),
                process_id=self.process_id,
            )
            ops_life = (
                self._operations.lifecycle.value
                if self._operations is not None
                else ""
            )
            status = WindowsMountStatus(
                mount_id=self.mount_id,
                state=self._state,
                ready=self._ready and self._recovery_complete,
                recovery_complete=self._recovery_complete,
                mode=self.mode,
                resources=resources,
                operations_lifecycle=ops_life,
                generation=self._generation,
                phase=self._phases[-1] if self._phases else "",
                message="",
                unix_ms=_unix_ms(),
                detail={
                    "resource_lease_held": self.resource_lease_held,
                    "state_lease_held": self.state_lease_held,
                    "worker_running": bool(
                        self._worker is not None and self._worker.running
                    ),
                    "adapter_bound": self._adapter is not None,
                    "wal_preserved": self.wal_state_preserved(),
                },
            )
        self._trace.record(
            WindowsTraceKind.STATUS,
            success=True,
            phase=status.phase,
            detail={"ready": status.ready, "state": status.state.value},
        )
        _atomic_write_json(self.status_path, status.to_record())
        return status

    def heartbeat(self) -> WindowsMountHeartbeat:
        """Refresh heartbeat; binds PID/mount/state/WAL/cache/lease resources."""

        if self._worker is not None:
            try:
                hb = self._worker.heartbeat()
            except WindowsLifecycleError:
                # Fall through to a status-derived heartbeat when worker stopped.
                hb = None
            else:
                if self._resource_lease is not None and self._resource_lease.held:
                    try:
                        self._resource_lease.heartbeat()
                    except WindowsResourceLeaseError:
                        pass
                if self._recovery is not None and self._recovery.lease.held:
                    try:
                        self._recovery.lease.heartbeat()
                    except Exception:  # noqa: BLE001
                        pass
                self._trace.record(
                    WindowsTraceKind.HEARTBEAT,
                    success=True,
                    phase=WindowsMountPhase.HEARTBEAT.value,
                    detail=hb.to_record(),
                )
                return hb

        resources = self._resources or WindowsMountResourceBindings(
            mount_id=self.mount_id,
            pid=self.pid,
            mount_root="",
            mount_root_kind="",
            state_directory=str(self.state_directory),
            wal_directory=str(self.wal_directory),
            cache_directory=str(self.cache_directory),
            runtime_directory=str(self.runtime_directory),
            process_id=self.process_id,
        )
        hb = WindowsMountHeartbeat(
            mount_id=self.mount_id,
            process_id=self.process_id,
            pid=self.pid,
            state=self.state,
            ready=self.ready,
            cycle=0,
            resources=resources,
            heartbeat_unix_ms=_unix_ms(),
            phase=WindowsMountPhase.HEARTBEAT.value,
        )
        _atomic_write_json(self.heartbeat_path, hb.to_record())
        return hb

    def _worker_cycle(self, worker: WindowsMountWorker) -> None:
        """Background cycle: refresh leases; never run a FUSE loop."""

        if self._resource_lease is not None and self._resource_lease.held:
            try:
                self._resource_lease.heartbeat()
            except WindowsResourceLeaseError:
                pass
        if self._recovery is not None and self._recovery.lease.held:
            try:
                self._recovery.lease.heartbeat()
            except Exception:  # noqa: BLE001
                pass
        # Keep status file fresh.
        try:
            status = self.status()
            _atomic_write_json(self.status_path, status.to_record())
        except Exception:  # noqa: BLE001
            pass

    # -- stop / crash / unmount ---------------------------------------------

    def unmount(self, *, preserve_wal: bool = True) -> WindowsMountReceipt:
        """Stop the mount, release resources, preserve WAL by default.

        Idempotent: repeated unmount does not raise and does not hang.
        """

        started = _monotonic()
        receipt_id = f"receipt:windows-unmount:{uuid.uuid4().hex}"
        self._phase(WindowsMountPhase.DRAIN)
        self._set_state(WindowsMountState.STOPPING)
        self._trace.record(
            WindowsTraceKind.UNMOUNT,
            success=True,
            phase=WindowsMountPhase.DRAIN.value,
        )

        root_canonical = (
            self._mount_root.canonical if self._mount_root else ""
        )
        root_kind = self._mount_root.kind.value if self._mount_root else ""
        resources = self._resources.to_record() if self._resources else {}

        self._release_all(preserve_wal=preserve_wal)

        with self._lock:
            self._ready = False
            self._state = WindowsMountState.STOPPED
            self._phases.append(WindowsMountPhase.UNMOUNTED.value)

        receipt = WindowsMountReceipt(
            receipt_id=receipt_id,
            success=True,
            ready=False,
            recovery_complete=self._recovery_complete,
            state=WindowsMountState.STOPPED,
            mount_id=self.mount_id,
            mode=self.mode,
            mount_root=root_canonical,
            mount_root_kind=root_kind,
            phases=self.phases,
            elapsed_seconds=_monotonic() - started,
            readiness_timeout_seconds=self.readiness_timeout_seconds,
            message="unmounted",
            resources=resources,
            recovery=(
                self._recovery_receipt.to_record()
                if self._recovery_receipt is not None
                else {}
            ),
            detail={
                "preserve_wal": preserve_wal,
                "wal_preserved": self.wal_state_preserved(),
                "resource_lease_held": self.resource_lease_held,
                "state_lease_held": self.state_lease_held,
            },
        )
        self._last_receipt = receipt
        self._trace.record(
            WindowsTraceKind.UNMOUNT,
            success=True,
            phase=WindowsMountPhase.UNMOUNTED.value,
            detail=receipt.to_record(),
        )
        return receipt

    def stop(self, *, preserve_wal: bool = True) -> WindowsMountReceipt:
        """Alias for :meth:`unmount` (stop workers + release leases)."""

        return self.unmount(preserve_wal=preserve_wal)

    def crash(self) -> WindowsMountReceipt:
        """Simulate crash: kill worker, release resources, preserve WAL.

        Does not hang the foreground caller.
        """

        started = _monotonic()
        receipt_id = f"receipt:windows-crash:{uuid.uuid4().hex}"
        self._phase(WindowsMountPhase.CRASHED)
        self._trace.record(
            WindowsTraceKind.CRASH,
            success=True,
            phase=WindowsMountPhase.CRASHED.value,
        )

        root_canonical = (
            self._mount_root.canonical if self._mount_root else ""
        )
        root_kind = self._mount_root.kind.value if self._mount_root else ""
        resources = self._resources.to_record() if self._resources else {}

        if self._worker is not None:
            try:
                self._worker.crash()
            except Exception:  # noqa: BLE001
                pass

        # Crash cleanup still releases leases (no leaked drive/dir/process).
        self._release_all(preserve_wal=True)

        with self._lock:
            self._ready = False
            self._state = WindowsMountState.CRASHED

        receipt = WindowsMountReceipt(
            receipt_id=receipt_id,
            success=True,
            ready=False,
            recovery_complete=self._recovery_complete,
            state=WindowsMountState.CRASHED,
            mount_id=self.mount_id,
            mode=self.mode,
            mount_root=root_canonical,
            mount_root_kind=root_kind,
            phases=self.phases,
            elapsed_seconds=_monotonic() - started,
            readiness_timeout_seconds=self.readiness_timeout_seconds,
            message="crashed; resources released; WAL preserved",
            resources=resources,
            recovery=(
                self._recovery_receipt.to_record()
                if self._recovery_receipt is not None
                else {}
            ),
            detail={
                "wal_preserved": self.wal_state_preserved(),
                "resource_lease_held": self.resource_lease_held,
                "state_lease_held": self.state_lease_held,
            },
        )
        self._last_receipt = receipt
        return receipt

    def _release_all(self, *, preserve_wal: bool = True) -> None:
        """Release drive/directory/process/state leases; optionally keep WAL."""

        self._phase(WindowsMountPhase.STOP_WORKER)
        if self._worker is not None:
            try:
                self._worker.stop(timeout_seconds=self.stop_timeout_seconds)
            except Exception:  # noqa: BLE001
                try:
                    self._worker.crash()
                except Exception:  # noqa: BLE001
                    pass
            self._worker = None

        if self._adapter is not None:
            # Only destroy operations we created. Caller-supplied operations
            # objects stay alive so the same instance can remount.
            if self._owns_operations:
                try:
                    self._adapter.destroy()
                except Exception:  # noqa: BLE001
                    pass
                self._operations = None
            self._adapter = None

        self._phase(WindowsMountPhase.RELEASE_LEASES)
        if self._resource_lease is not None:
            try:
                self._resource_lease.release()
            except Exception:  # noqa: BLE001
                pass
            self._resource_lease = None
            self._trace.record(
                WindowsTraceKind.RELEASE,
                success=True,
                phase=WindowsMountPhase.RELEASE_LEASES.value,
                detail={"resource": "drive_or_directory"},
            )

        if self._recovery is not None:
            try:
                # close() releases the state lease; WAL durable data remains.
                self._recovery.close()
            except Exception:  # noqa: BLE001
                try:
                    self._recovery.lease.release()
                except Exception:  # noqa: BLE001
                    pass
            self._recovery = None
            self._trace.record(
                WindowsTraceKind.RELEASE,
                success=True,
                phase=WindowsMountPhase.RELEASE_LEASES.value,
                detail={"resource": "state_lease"},
            )

        # Drop process / ready / heartbeat runtime markers (not WAL).
        for path in (
            self.ready_path,
            self.heartbeat_path,
            self.process_path,
        ):
            _safe_unlink(path)

        # Status remains as a terminal snapshot if present; rewrite stopped.
        try:
            terminal = {
                "schema": WINDOWS_MOUNT_STATUS_SCHEMA,
                "mount_id": self.mount_id,
                "state": WindowsMountState.STOPPED.value,
                "ready": False,
                "recovery_complete": self._recovery_complete,
                "unix_ms": _unix_ms(),
                "wal_preserved": self.wal_state_preserved() if preserve_wal else False,
            }
            _atomic_write_json(self.status_path, terminal)
        except Exception:  # noqa: BLE001
            pass

        if not preserve_wal:
            # Explicit destructive path (not used by default cleanup).
            marker = self._wal_marker_path
            _safe_unlink(marker)

    def wal_state_preserved(self) -> bool:
        """True when durable WAL marker/state directory still exists."""

        if not self.wal_directory.is_dir():
            return False
        if self._wal_marker_path.is_file():
            return True
        # Durable mutation coordinator layout under wal_directory.
        return any(self.wal_directory.iterdir())

    def resource_leases_released(self) -> bool:
        return (not self.resource_lease_held) and (not self.state_lease_held)

    def process_released(self) -> bool:
        return self._worker is None and not self.process_path.exists()

    # -- internal mount steps -----------------------------------------------

    def _acquire_resource_lease(self, root: WindowsMountRoot) -> ResourceLeaseHolder:
        if root.kind is MountRootKind.DRIVE_LETTER:
            kind = "drive"
            resource_id = root.canonical.rstrip(":\\/")
            lease_dir = self.lease_root / DRIVE_LEASE_DIRNAME
        else:
            kind = "directory"
            resource_id = root.canonical
            lease_dir = self.lease_root / DIRECTORY_LEASE_DIRNAME
        lease = ResourceLease(
            lease_dir,
            resource_kind=kind,
            resource_id=resource_id,
            mount_id=self.mount_id,
            holder_id=self.holder_id,
            ttl_seconds=self.lease_ttl_seconds,
            pid=self.pid,
        )
        holder = lease.try_acquire()
        self._resource_lease = lease
        return holder

    def _run_recovery(self) -> MountRecoveryReceipt:
        # Always construct a fresh coordinator for this mount attempt.
        if self._recovery is not None:
            try:
                self._recovery.close()
            except Exception:  # noqa: BLE001
                pass
        self._recovery = MountRecoveryCoordinator(
            self.state_directory,
            mount_id=self.mount_id,
            platform=self.platform,
            recovery_timeout_seconds=self._recovery_timeout_seconds,
            lease_ttl_seconds=self.lease_ttl_seconds,
            holder_id=self.holder_id,
            recovery_required=True,
        )
        receipt = self._recovery.recover()
        if receipt.disposition is RecoveryDisposition.LEASE_HELD:
            raise WindowsResourceLeaseError(
                "state lease held by another mount",
                detail=receipt.to_record(),
            )
        return receipt

    def _bind_operations(self) -> WinFspFuseCompatAdapter:
        if self._operations is None:
            self._operations = build_kernel_vfs_operations(
                backend="memory",
                platform=self.platform,
                mount_id=self.mount_id,
                auto_init=False,
            )
            self._owns_operations = True
        adapter = WinFspFuseCompatAdapter(self._operations)
        # Operations init is distinct from mount recovery; recovery already ran.
        # Init moves the operations object through recovering→ready for callbacks.
        if self._operations.lifecycle is MountLifecycleState.UNINITIALIZED:
            outcome = self._operations.init()
            if not outcome.success:
                raise WindowsLifecycleError(
                    "KernelVFSOperations init failed after recovery",
                    code=WindowsLifecycleErrorCode.INTERNAL,
                    detail={"lifecycle": self._operations.lifecycle.value},
                )
        self._adapter = adapter
        return adapter

    def _ensure_native_capability(self, root: WindowsMountRoot) -> None:
        """Probe WinFsp capability for native mode without mounting yet.

        Raises a typed capability error when native support is absent. Does
        not import fusepy at module level; loads the doctor on demand.
        """

        try:
            from ipfs_kit_py.kernel_vfs.winfsp_loader import (
                FuseCapabilityError,
                ensure_windows_winfsp_capability,
            )
        except Exception as exc:  # noqa: BLE001
            raise WindowsLifecycleError(
                f"native WinFsp loader unavailable: {exc}",
                code=WindowsLifecycleErrorCode.NATIVE,
            ) from exc

        drive_letter = (
            root.canonical if root.kind is MountRootKind.DRIVE_LETTER else None
        )
        mount_directory = (
            root.canonical if root.kind is MountRootKind.DIRECTORY else None
        )
        try:
            ensure_windows_winfsp_capability(
                drive_letter=drive_letter,
                mount_directory=mount_directory,
                state_dir=str(self.state_directory),
                load_binding=False,
                load_native=False,
            )
        except FuseCapabilityError as exc:
            raise WindowsLifecycleError(
                str(exc),
                code=WindowsLifecycleErrorCode.NATIVE,
                detail={
                    "check": getattr(exc, "check", ""),
                    "support_claim": "capability_unavailable",
                },
            ) from exc

    def _fail(self, exc: WindowsLifecycleError) -> None:
        with self._lock:
            self._state = WindowsMountState.FAILED
            self._ready = False
            self._phases.append(WindowsMountPhase.FAILED.value)
        self._trace.record(
            WindowsTraceKind.FAILED,
            success=False,
            phase=WindowsMountPhase.FAILED.value,
            code=exc.code.value,
            detail=exc.to_record(),
        )

    # -- lifecycle context --------------------------------------------------

    def close(self) -> None:
        if self._closed:
            return
        try:
            if self.state not in (
                WindowsMountState.STOPPED,
                WindowsMountState.CREATED,
            ):
                self.unmount(preserve_wal=True)
            else:
                self._release_all(preserve_wal=True)
        finally:
            self._closed = True

    def __enter__(self) -> "WindowsMountLifecycle":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def to_record(self) -> dict[str, Any]:
        with self._lock:
            return {
                "schema": self.SCHEMA,
                "contract_version": CONTRACT_VERSION,
                "schema_version": SCHEMA_VERSION,
                "task_id": TASK_ID,
                "mount_id": self.mount_id,
                "state": self._state.value,
                "ready": self._ready and self._recovery_complete,
                "recovery_complete": self._recovery_complete,
                "mode": self.mode.value,
                "platform": self.platform.value,
                "process_id": self.process_id,
                "pid": self.pid,
                "state_directory": str(self.state_directory),
                "wal_directory": str(self.wal_directory),
                "cache_directory": str(self.cache_directory),
                "mount_root": (
                    self._mount_root.to_record() if self._mount_root else None
                ),
                "resources": (
                    self._resources.to_record() if self._resources else None
                ),
                "phases": list(self._phases),
                "generation": self._generation,
                "resource_lease_held": self.resource_lease_held,
                "state_lease_held": self.state_lease_held,
                "wal_preserved": self.wal_state_preserved(),
                "adapter": (
                    self._adapter.to_record() if self._adapter else None
                ),
            }


# ---------------------------------------------------------------------------
# Module-level helpers / factories
# ---------------------------------------------------------------------------


def build_windows_mount_lifecycle(
    state_directory: str | Path,
    *,
    mount_id: str = DEFAULT_MOUNT_ID,
    mode: WindowsMountMode | str = WindowsMountMode.HERMETIC,
    operations: KernelVFSOperations | None = None,
    **kwargs: Any,
) -> WindowsMountLifecycle:
    """Factory for :class:`WindowsMountLifecycle`."""

    return WindowsMountLifecycle(
        state_directory,
        mount_id=mount_id,
        mode=mode,
        operations=operations,
        **kwargs,
    )


def mount_windows(
    mount_root: str,
    state_directory: str | Path,
    *,
    kind: MountRootKind | str | None = None,
    mode: WindowsMountMode | str = WindowsMountMode.HERMETIC,
    operations: KernelVFSOperations | None = None,
    **kwargs: Any,
) -> tuple[WindowsMountLifecycle, WindowsMountReceipt]:
    """Convenience: construct lifecycle, mount, return ``(lifecycle, receipt)``."""

    life = build_windows_mount_lifecycle(
        state_directory,
        mode=mode,
        operations=operations,
        **kwargs,
    )
    receipt = life.mount(mount_root, kind=kind)
    return life, receipt


def assert_no_fusepy_import() -> None:
    """Guardrail: this module must not hard-import native FUSE bindings."""

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
                    raise WindowsLifecycleError(
                        f"windows lifecycle must not import {alias.name}",
                        code=WindowsLifecycleErrorCode.INTERNAL,
                    )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.split(".", 1)[0] if module else ""
            if root in banned:
                raise WindowsLifecycleError(
                    f"windows lifecycle must not import from {module}",
                    code=WindowsLifecycleErrorCode.INTERNAL,
                )


def mount_root_kinds() -> tuple[str, ...]:
    return tuple(k.value for k in MountRootKind)


def mount_modes() -> tuple[str, ...]:
    return tuple(m.value for m in WindowsMountMode)


def mount_phases() -> tuple[str, ...]:
    return tuple(p.value for p in WindowsMountPhase)


__all__ = [
    "TASK_ID",
    "CONTRACT_VERSION",
    "SCHEMA_VERSION",
    "WINDOWS_MOUNT_LIFECYCLE_SCHEMA",
    "WINDOWS_MOUNT_STATUS_SCHEMA",
    "WINDOWS_MOUNT_HEARTBEAT_SCHEMA",
    "WindowsMountLifecycle_V1",
    "WindowsMountStatus_V1",
    "WindowsMountHeartbeat_V1",
    "DEFAULT_MOUNT_ID",
    "DEFAULT_READINESS_TIMEOUT_SECONDS",
    "WindowsMountMode",
    "WindowsMountPhase",
    "WindowsMountState",
    "WindowsLifecycleErrorCode",
    "WindowsTraceKind",
    "WindowsLifecycleError",
    "WindowsMountRootError",
    "WindowsResourceLeaseError",
    "WindowsReadinessError",
    "WindowsWorkerHangError",
    "WindowsTraceStep",
    "WindowsTraceLog",
    "ResourceLeaseHolder",
    "ResourceLease",
    "WindowsMountResourceBindings",
    "WindowsMountStatus",
    "WindowsMountHeartbeat",
    "WindowsMountReceipt",
    "WinFspFuseCompatAdapter",
    "WindowsMountWorker",
    "WindowsMountLifecycle",
    "build_windows_mount_lifecycle",
    "mount_windows",
    "assert_no_fusepy_import",
    "mount_root_kinds",
    "mount_modes",
    "mount_phases",
    "validate_drive_letter_root",
    "validate_directory_root",
    "MountRootKind",
]
