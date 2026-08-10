"""Linux mount lifecycle: readiness, heartbeat, signal, and unmount (KVFS-500).

This module owns the **Linux launcher / process lifecycle** for kernel VFS
mounts.  Production rules (fail-closed):

* Mount work runs in a **child process**.  Callers never enter a foreground
  blocking FUSE loop in-process.
* **Foreground child recovery precedes ready** — the child runs
  :class:`~ipfs_kit_py.kernel_vfs.wal_recovery.MountRecoveryCoordinator`
  recovery before advertising readiness.
* **Readiness arrives within 15 seconds** or the parent tears down the child
  and exits nonzero / raises a typed error.
* **Heartbeat and status** bind PID, mountpoint, state directory, WAL, and
  cache identity.
* **SIGINT / SIGTERM** and **repeated unmount** drain bounded callbacks, stop
  workers, release mount/lease, **preserve recovery state**, and report stale
  mounts **without blocking**.

Importing this module is inert with respect to fusepy/libfuse: it never loads
native FUSE bindings and never mounts.  Live kernel mount wiring is owned by
later conformance tasks; this module provides a hermetic child daemon that
exercises the full process lifecycle contract.

Interfaces (plan aliases): ``LinuxMountLifecycle@1``, ``LinuxMountDaemon@1``,
``MountReadiness@1``, ``MountHeartbeat@1``, ``MountStatus@1``,
``UnmountReceipt@1``.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar, Final

from ipfs_kit_py.core.vfs.host_contracts import (
    HostMountLifecycle,
    HostPlatform,
    MountLifecycleState,
    assert_legal_mount_transition,
    is_legal_mount_transition,
)
from ipfs_kit_py.kernel_vfs.wal_recovery import (
    MountRecoveryCoordinator,
    MountRecoveryReceipt,
    RecoveryDisposition,
    StateLeaseHeldError,
)

# ---------------------------------------------------------------------------
# Schema / version / bounds
# ---------------------------------------------------------------------------

TASK_ID: Final[str] = "KVFS-500"
CONTRACT_VERSION: Final[int] = 1
SCHEMA_MAJOR: Final[int] = 1
SCHEMA_MINOR: Final[int] = 0
SCHEMA_PATCH: Final[int] = 0
SCHEMA_VERSION: Final[str] = f"{SCHEMA_MAJOR}.{SCHEMA_MINOR}.{SCHEMA_PATCH}"

LINUX_NAMESPACE: Final[str] = "ipfs_kit_py/kernel_vfs/linux"

LINUX_MOUNT_LIFECYCLE_SCHEMA: Final[str] = (
    f"{LINUX_NAMESPACE}/linux-mount-lifecycle@{SCHEMA_MAJOR}"
)
LINUX_MOUNT_DAEMON_SCHEMA: Final[str] = (
    f"{LINUX_NAMESPACE}/linux-mount-daemon@{SCHEMA_MAJOR}"
)
MOUNT_READINESS_SCHEMA: Final[str] = f"{LINUX_NAMESPACE}/mount-readiness@{SCHEMA_MAJOR}"
MOUNT_HEARTBEAT_SCHEMA: Final[str] = f"{LINUX_NAMESPACE}/mount-heartbeat@{SCHEMA_MAJOR}"
MOUNT_STATUS_SCHEMA: Final[str] = f"{LINUX_NAMESPACE}/mount-status@{SCHEMA_MAJOR}"
UNMOUNT_RECEIPT_SCHEMA: Final[str] = f"{LINUX_NAMESPACE}/unmount-receipt@{SCHEMA_MAJOR}"
STALE_MOUNT_REPORT_SCHEMA: Final[str] = (
    f"{LINUX_NAMESPACE}/stale-mount-report@{SCHEMA_MAJOR}"
)
CHILD_CONFIG_SCHEMA: Final[str] = f"{LINUX_NAMESPACE}/child-config@{SCHEMA_MAJOR}"

# Public interface aliases.
LinuxMountLifecycle_V1: Final[str] = LINUX_MOUNT_LIFECYCLE_SCHEMA
LinuxMountDaemon_V1: Final[str] = LINUX_MOUNT_DAEMON_SCHEMA
MountReadiness_V1: Final[str] = MOUNT_READINESS_SCHEMA
MountHeartbeat_V1: Final[str] = MOUNT_HEARTBEAT_SCHEMA
MountStatus_V1: Final[str] = MOUNT_STATUS_SCHEMA
UnmountReceipt_V1: Final[str] = UNMOUNT_RECEIPT_SCHEMA

DEFAULT_MOUNT_ID: Final[str] = "mount:linux-default"
DEFAULT_GENERATION_ID: Final[str] = "wal-gen:linux-1"
DEFAULT_READINESS_TIMEOUT_SECONDS: Final[float] = 15.0
DEFAULT_HEARTBEAT_INTERVAL_SECONDS: Final[float] = 0.25
DEFAULT_UNMOUNT_TIMEOUT_SECONDS: Final[float] = 5.0
DEFAULT_DRAIN_TIMEOUT_SECONDS: Final[float] = 2.0
DEFAULT_WORKER_STOP_TIMEOUT_SECONDS: Final[float] = 2.0
DEFAULT_CALLBACK_DRAIN_BOUND: Final[int] = 64
DEFAULT_STALE_HEARTBEAT_SECONDS: Final[float] = 5.0
MAX_TEXT_BYTES: Final[int] = 4_096
MAX_PATH_BYTES: Final[int] = 4_096
MAX_TRACE_EVENTS: Final[int] = 4_096
MAX_SAFE_INTEGER: Final[int] = (1 << 53) - 1

READY_FILENAME: Final[str] = "ready.json"
HEARTBEAT_FILENAME: Final[str] = "heartbeat.json"
STATUS_FILENAME: Final[str] = "status.json"
CHILD_CONFIG_FILENAME: Final[str] = "child-config.json"
CHILD_PID_FILENAME: Final[str] = "child.pid"
UNMOUNT_REQUEST_FILENAME: Final[str] = "unmount.request"
SHUTDOWN_RECEIPT_FILENAME: Final[str] = "shutdown.json"
STALE_REPORT_FILENAME: Final[str] = "stale-mounts.json"
RECOVERY_DIRNAME: Final[str] = "recovery"
CACHE_DIRNAME: Final[str] = "cache"
WAL_DIRNAME: Final[str] = "wal"


# ---------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------


class LifecyclePhase(str, Enum):
    """Ordered phases of Linux mount process lifecycle."""

    ADMIT = "admit"
    SPAWN_CHILD = "spawn_child"
    CHILD_RECOVER = "child_recover"
    CHILD_READY = "child_ready"
    PARENT_WAIT_READY = "parent_wait_ready"
    HEARTBEAT = "heartbeat"
    STATUS = "status"
    SIGNAL = "signal"
    DRAIN_CALLBACKS = "drain_callbacks"
    STOP_WORKERS = "stop_workers"
    RELEASE_MOUNT = "release_mount"
    RELEASE_LEASE = "release_lease"
    PRESERVE_RECOVERY = "preserve_recovery"
    UNMOUNT = "unmount"
    STALE_REPORT = "stale_report"
    FAILED = "failed"
    DESTROYED = "destroyed"


class LifecycleDisposition(str, Enum):
    """Terminal disposition of a lifecycle operation."""

    READY = "ready"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    IDEMPOTENT = "idempotent"
    STALE = "stale"
    SIGNALLED = "signalled"


class LifecycleErrorCode(str, Enum):
    """Stable error codes for the Linux lifecycle façade."""

    VALIDATION = "LINUX_LIFECYCLE_VALIDATION"
    READINESS_TIMEOUT = "LINUX_LIFECYCLE_READINESS_TIMEOUT"
    CHILD_EXIT = "LINUX_LIFECYCLE_CHILD_EXIT"
    CHILD_SPAWN = "LINUX_LIFECYCLE_CHILD_SPAWN"
    RECOVERY = "LINUX_LIFECYCLE_RECOVERY"
    LEASE = "LINUX_LIFECYCLE_LEASE"
    UNMOUNT = "LINUX_LIFECYCLE_UNMOUNT"
    SIGNAL = "LINUX_LIFECYCLE_SIGNAL"
    PROTOCOL = "LINUX_LIFECYCLE_PROTOCOL"
    NOT_RUNNING = "LINUX_LIFECYCLE_NOT_RUNNING"
    ALREADY_RUNNING = "LINUX_LIFECYCLE_ALREADY_RUNNING"
    BOUND_EXCEEDED = "LINUX_LIFECYCLE_BOUND_EXCEEDED"
    INTERNAL = "LINUX_LIFECYCLE_INTERNAL"


class LifecycleTraceKind(str, Enum):
    """Closed trace kinds for lifecycle evidence."""

    ADMIT = "admit"
    SPAWN = "spawn"
    RECOVERY = "recovery"
    READY = "ready"
    HEARTBEAT = "heartbeat"
    STATUS = "status"
    SIGNAL = "signal"
    DRAIN = "drain"
    WORKER = "worker"
    UNMOUNT = "unmount"
    LEASE = "lease"
    STALE = "stale"
    FAULT = "fault"
    RECEIPT = "receipt"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class LinuxLifecycleError(Exception):
    """Base error for Linux mount lifecycle failures that must not be ignored."""

    def __init__(
        self,
        message: str,
        *,
        code: LifecycleErrorCode = LifecycleErrorCode.INTERNAL,
        detail: Mapping[str, Any] | None = None,
        exit_code: int = 1,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = (
            code if isinstance(code, LifecycleErrorCode) else LifecycleErrorCode(code)
        )
        self.detail = dict(detail or {})
        self.exit_code = int(exit_code)

    def to_record(self) -> dict[str, Any]:
        return {
            "error": type(self).__name__,
            "message": self.message,
            "code": self.code.value,
            "detail": dict(self.detail),
            "exit_code": self.exit_code,
        }


class ReadinessTimeoutError(LinuxLifecycleError):
    """Child did not advertise readiness within the declared budget."""

    def __init__(
        self,
        message: str = "mount readiness exceeded declared time bound",
        *,
        timeout_seconds: float = DEFAULT_READINESS_TIMEOUT_SECONDS,
        elapsed_seconds: float = 0.0,
        pid: int = 0,
    ) -> None:
        super().__init__(
            message,
            code=LifecycleErrorCode.READINESS_TIMEOUT,
            detail={
                "timeout_seconds": timeout_seconds,
                "elapsed_seconds": elapsed_seconds,
                "pid": pid,
            },
            exit_code=1,
        )


class ChildProcessError(LinuxLifecycleError):
    """Child process failed to start, exited early, or returned nonzero."""

    def __init__(
        self,
        message: str,
        *,
        code: LifecycleErrorCode = LifecycleErrorCode.CHILD_EXIT,
        pid: int = 0,
        returncode: int | None = None,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        payload = dict(detail or {})
        payload.setdefault("pid", pid)
        if returncode is not None:
            payload.setdefault("returncode", returncode)
        super().__init__(
            message,
            code=code,
            detail=payload,
            exit_code=int(returncode if returncode not in (None, 0) else 1),
        )


class LifecycleProtocolError(LinuxLifecycleError):
    """Protocol / readiness invariant violation."""

    def __init__(
        self,
        message: str,
        *,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code=LifecycleErrorCode.PROTOCOL,
            detail=detail,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _text(value: Any, name: str, *, limit: int = MAX_TEXT_BYTES) -> str:
    if value is None:
        return ""
    text = str(value)
    if len(text.encode("utf-8", errors="replace")) > limit:
        raise LinuxLifecycleError(
            f"{name} exceeds {limit} bytes",
            code=LifecycleErrorCode.VALIDATION,
            detail={"field": name},
        )
    return text


def _path_text(value: Any, name: str) -> str:
    return _text(value, name, limit=MAX_PATH_BYTES)


def _bool(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise LinuxLifecycleError(
            f"{name} must be a bool",
            code=LifecycleErrorCode.VALIDATION,
            detail={"field": name, "value": value},
        )
    return value


def _nonneg_float(value: Any, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise LinuxLifecycleError(
            f"{name} must be a non-negative number",
            code=LifecycleErrorCode.VALIDATION,
            detail={"field": name, "value": value},
        ) from exc
    if number < 0 or number != number:  # NaN
        raise LinuxLifecycleError(
            f"{name} must be a non-negative number",
            code=LifecycleErrorCode.VALIDATION,
            detail={"field": name, "value": value},
        )
    return number


def _positive_float(value: Any, name: str) -> float:
    number = _nonneg_float(value, name)
    if number <= 0:
        raise LinuxLifecycleError(
            f"{name} must be positive",
            code=LifecycleErrorCode.VALIDATION,
            detail={"field": name, "value": value},
        )
    return number


def _bounded_int(
    value: Any,
    name: str,
    *,
    minimum: int = 0,
    maximum: int = MAX_SAFE_INTEGER,
) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise LinuxLifecycleError(
            f"{name} must be an integer",
            code=LifecycleErrorCode.VALIDATION,
            detail={"field": name, "value": value},
        ) from exc
    if number < minimum or number > maximum:
        raise LinuxLifecycleError(
            f"{name} out of bounds [{minimum}, {maximum}]",
            code=LifecycleErrorCode.VALIDATION,
            detail={"field": name, "value": number},
        )
    return number


def _monotonic() -> float:
    return time.monotonic()


def _unix_ms() -> int:
    return int(time.time() * 1000)


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{uuid.uuid4().hex[:8]}")
    try:
        with open(tmp, "wb") as stream:
            stream.write(data)
            stream.flush()
            try:
                os.fsync(stream.fileno())
            except OSError:
                pass
        os.replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink(missing_ok=True)  # type: ignore[call-arg]
        except TypeError:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        raise


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    data = json.dumps(dict(payload), sort_keys=True, separators=(",", ":"))
    _atomic_write_bytes(path, (data + "\n").encode("utf-8"))


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(raw) if isinstance(raw, Mapping) else {}


def _pid_alive(pid: int) -> bool:
    """Return True if ``pid`` appears to be a live process (non-blocking)."""

    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but we cannot signal it.
        return True
    except OSError:
        return False
    return True


def _safe_unlink(path: Path) -> bool:
    try:
        path.unlink(missing_ok=True)  # type: ignore[call-arg]
        return True
    except TypeError:
        if path.exists():
            try:
                path.unlink()
                return True
            except OSError:
                return False
        return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Trace
# ---------------------------------------------------------------------------


@dataclass
class LifecycleTraceEvent:
    kind: LifecycleTraceKind
    success: bool = True
    phase: str = ""
    code: str = ""
    detail: dict[str, Any] = field(default_factory=dict)
    unix_ms: int = field(default_factory=_unix_ms)

    def to_record(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "success": self.success,
            "phase": self.phase,
            "code": self.code,
            "detail": dict(self.detail),
            "unix_ms": self.unix_ms,
        }


class LifecycleTrace:
    """Bounded in-memory lifecycle trace."""

    def __init__(self, *, max_events: int = MAX_TRACE_EVENTS) -> None:
        self._max = max(1, int(max_events))
        self._events: list[LifecycleTraceEvent] = []
        self._lock = threading.RLock()

    def record(
        self,
        kind: LifecycleTraceKind | str,
        *,
        success: bool = True,
        phase: str = "",
        code: str = "",
        detail: Mapping[str, Any] | None = None,
    ) -> LifecycleTraceEvent:
        if not isinstance(kind, LifecycleTraceKind):
            kind = LifecycleTraceKind(kind)
        event = LifecycleTraceEvent(
            kind=kind,
            success=success,
            phase=phase,
            code=code,
            detail=dict(detail or {}),
        )
        with self._lock:
            self._events.append(event)
            if len(self._events) > self._max:
                self._events = self._events[-self._max :]
        return event

    def events(self) -> tuple[LifecycleTraceEvent, ...]:
        with self._lock:
            return tuple(self._events)

    def to_records(self) -> list[dict[str, Any]]:
        return [e.to_record() for e in self.events()]


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MountReadiness:
    """On-disk readiness handshake written only after recovery completes."""

    SCHEMA: ClassVar[str] = MOUNT_READINESS_SCHEMA

    mount_id: str
    pid: int
    mountpoint: str
    state_directory: str
    recovery_complete: bool
    ready: bool
    lifecycle_state: str
    wal_generation: str = ""
    cache_generation: int = 0
    ready_unix_ms: int = 0
    holder_id: str = ""
    recovery_phases: tuple[str, ...] = ()

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "task_id": TASK_ID,
            "mount_id": self.mount_id,
            "pid": self.pid,
            "mountpoint": self.mountpoint,
            "state_directory": self.state_directory,
            "recovery_complete": self.recovery_complete,
            "ready": self.ready,
            "lifecycle_state": self.lifecycle_state,
            "wal": {
                "generation": self.wal_generation,
            },
            "cache": {
                "generation": self.cache_generation,
            },
            "ready_unix_ms": self.ready_unix_ms,
            "holder_id": self.holder_id,
            "recovery_phases": list(self.recovery_phases),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "MountReadiness":
        wal = payload.get("wal") if isinstance(payload.get("wal"), Mapping) else {}
        cache = payload.get("cache") if isinstance(payload.get("cache"), Mapping) else {}
        phases = payload.get("recovery_phases") or ()
        return cls(
            mount_id=str(payload.get("mount_id") or ""),
            pid=int(payload.get("pid") or 0),
            mountpoint=str(payload.get("mountpoint") or ""),
            state_directory=str(payload.get("state_directory") or ""),
            recovery_complete=bool(payload.get("recovery_complete")),
            ready=bool(payload.get("ready")),
            lifecycle_state=str(payload.get("lifecycle_state") or ""),
            wal_generation=str(wal.get("generation") or payload.get("wal_generation") or ""),
            cache_generation=int(cache.get("generation") or payload.get("cache_generation") or 0),
            ready_unix_ms=int(payload.get("ready_unix_ms") or 0),
            holder_id=str(payload.get("holder_id") or ""),
            recovery_phases=tuple(str(p) for p in phases),
        )


@dataclass(frozen=True)
class MountHeartbeat:
    """Periodic liveness record binding PID / mount / state / WAL / cache."""

    SCHEMA: ClassVar[str] = MOUNT_HEARTBEAT_SCHEMA

    mount_id: str
    pid: int
    mountpoint: str
    state_directory: str
    lifecycle_state: str
    wal_generation: str
    wal_position: str
    cache_generation: int
    cache_entries: int
    heartbeat_unix_ms: int
    sequence: int = 0
    open_callbacks: int = 0
    workers_running: int = 0

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "task_id": TASK_ID,
            "mount_id": self.mount_id,
            "pid": self.pid,
            "mountpoint": self.mountpoint,
            "state_directory": self.state_directory,
            "lifecycle_state": self.lifecycle_state,
            "wal": {
                "generation": self.wal_generation,
                "position": self.wal_position,
            },
            "cache": {
                "generation": self.cache_generation,
                "entries": self.cache_entries,
            },
            "heartbeat_unix_ms": self.heartbeat_unix_ms,
            "sequence": self.sequence,
            "open_callbacks": self.open_callbacks,
            "workers_running": self.workers_running,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "MountHeartbeat":
        wal = payload.get("wal") if isinstance(payload.get("wal"), Mapping) else {}
        cache = payload.get("cache") if isinstance(payload.get("cache"), Mapping) else {}
        return cls(
            mount_id=str(payload.get("mount_id") or ""),
            pid=int(payload.get("pid") or 0),
            mountpoint=str(payload.get("mountpoint") or ""),
            state_directory=str(payload.get("state_directory") or ""),
            lifecycle_state=str(payload.get("lifecycle_state") or ""),
            wal_generation=str(wal.get("generation") or payload.get("wal_generation") or ""),
            wal_position=str(wal.get("position") or payload.get("wal_position") or ""),
            cache_generation=int(cache.get("generation") or payload.get("cache_generation") or 0),
            cache_entries=int(cache.get("entries") or payload.get("cache_entries") or 0),
            heartbeat_unix_ms=int(payload.get("heartbeat_unix_ms") or 0),
            sequence=int(payload.get("sequence") or 0),
            open_callbacks=int(payload.get("open_callbacks") or 0),
            workers_running=int(payload.get("workers_running") or 0),
        )


@dataclass(frozen=True)
class MountStatus:
    """Authoritative status snapshot (PID/mount/state/WAL/cache + lifecycle)."""

    SCHEMA: ClassVar[str] = MOUNT_STATUS_SCHEMA

    mount_id: str
    pid: int
    mountpoint: str
    state_directory: str
    lifecycle_state: str
    ready: bool
    recovery_complete: bool
    lease_held: bool
    holder_id: str
    wal: Mapping[str, Any]
    cache: Mapping[str, Any]
    workers: Mapping[str, Any]
    open_callbacks: int
    mounted: bool
    status_unix_ms: int
    heartbeat_unix_ms: int = 0
    exit_code: int | None = None

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "task_id": TASK_ID,
            "mount_id": self.mount_id,
            "pid": self.pid,
            "mountpoint": self.mountpoint,
            "state_directory": self.state_directory,
            "lifecycle_state": self.lifecycle_state,
            "ready": self.ready,
            "recovery_complete": self.recovery_complete,
            "lease_held": self.lease_held,
            "holder_id": self.holder_id,
            "wal": dict(self.wal),
            "cache": dict(self.cache),
            "workers": dict(self.workers),
            "open_callbacks": self.open_callbacks,
            "mounted": self.mounted,
            "status_unix_ms": self.status_unix_ms,
            "heartbeat_unix_ms": self.heartbeat_unix_ms,
            "exit_code": self.exit_code,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "MountStatus":
        exit_raw = payload.get("exit_code", None)
        exit_code = None if exit_raw is None else int(exit_raw)
        return cls(
            mount_id=str(payload.get("mount_id") or ""),
            pid=int(payload.get("pid") or 0),
            mountpoint=str(payload.get("mountpoint") or ""),
            state_directory=str(payload.get("state_directory") or ""),
            lifecycle_state=str(payload.get("lifecycle_state") or ""),
            ready=bool(payload.get("ready")),
            recovery_complete=bool(payload.get("recovery_complete")),
            lease_held=bool(payload.get("lease_held")),
            holder_id=str(payload.get("holder_id") or ""),
            wal=dict(payload.get("wal") or {}),
            cache=dict(payload.get("cache") or {}),
            workers=dict(payload.get("workers") or {}),
            open_callbacks=int(payload.get("open_callbacks") or 0),
            mounted=bool(payload.get("mounted")),
            status_unix_ms=int(payload.get("status_unix_ms") or 0),
            heartbeat_unix_ms=int(payload.get("heartbeat_unix_ms") or 0),
            exit_code=exit_code,
        )


@dataclass(frozen=True)
class UnmountReceipt:
    """Receipt for a bounded unmount / signalled shutdown."""

    SCHEMA: ClassVar[str] = UNMOUNT_RECEIPT_SCHEMA

    mount_id: str
    disposition: LifecycleDisposition
    success: bool
    pid: int
    callbacks_drained: int
    workers_stopped: int
    lease_released: bool
    mount_released: bool
    recovery_preserved: bool
    lifecycle_state: str
    signal_name: str = ""
    idempotent: bool = False
    elapsed_seconds: float = 0.0
    exit_code: int = 0
    detail: Mapping[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "task_id": TASK_ID,
            "mount_id": self.mount_id,
            "disposition": self.disposition.value,
            "success": self.success,
            "pid": self.pid,
            "callbacks_drained": self.callbacks_drained,
            "workers_stopped": self.workers_stopped,
            "lease_released": self.lease_released,
            "mount_released": self.mount_released,
            "recovery_preserved": self.recovery_preserved,
            "lifecycle_state": self.lifecycle_state,
            "signal_name": self.signal_name,
            "idempotent": self.idempotent,
            "elapsed_seconds": self.elapsed_seconds,
            "exit_code": self.exit_code,
            "detail": dict(self.detail),
        }


@dataclass(frozen=True)
class StaleMountReport:
    """Non-blocking report of stale / orphaned mount state directories."""

    SCHEMA: ClassVar[str] = STALE_MOUNT_REPORT_SCHEMA

    scanned: int
    stale: tuple[Mapping[str, Any], ...]
    live: tuple[Mapping[str, Any], ...]
    blocked: bool
    report_unix_ms: int

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "task_id": TASK_ID,
            "scanned": self.scanned,
            "stale": [dict(item) for item in self.stale],
            "live": [dict(item) for item in self.live],
            "blocked": self.blocked,
            "report_unix_ms": self.report_unix_ms,
        }


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class LinuxMountConfig:
    """Configuration for a Linux mount daemon launch."""

    mountpoint: str | Path
    state_directory: str | Path
    mount_id: str = DEFAULT_MOUNT_ID
    generation_id: str = DEFAULT_GENERATION_ID
    readiness_timeout_seconds: float = DEFAULT_READINESS_TIMEOUT_SECONDS
    heartbeat_interval_seconds: float = DEFAULT_HEARTBEAT_INTERVAL_SECONDS
    unmount_timeout_seconds: float = DEFAULT_UNMOUNT_TIMEOUT_SECONDS
    drain_timeout_seconds: float = DEFAULT_DRAIN_TIMEOUT_SECONDS
    worker_stop_timeout_seconds: float = DEFAULT_WORKER_STOP_TIMEOUT_SECONDS
    callback_drain_bound: int = DEFAULT_CALLBACK_DRAIN_BOUND
    stale_heartbeat_seconds: float = DEFAULT_STALE_HEARTBEAT_SECONDS
    # Hermetic mode: child simulates FUSE lifecycle without native mount.
    hermetic: bool = True
    # Optional deliberate recovery delay (tests / diagnostics only).
    recovery_delay_seconds: float = 0.0
    # Optional deliberate readiness failure (tests).
    fail_before_ready: bool = False
    # Optional fail readiness timeout simulation (child never writes ready).
    suppress_ready: bool = False
    # Initial cache generation advertised in status/heartbeat.
    cache_generation: int = 1
    cache_entries: int = 0
    holder_id: str | None = None
    python_executable: str | None = None
    env: Mapping[str, str] | None = None

    def __post_init__(self) -> None:
        self.mountpoint = Path(_path_text(self.mountpoint, "mountpoint")).resolve()
        self.state_directory = Path(
            _path_text(self.state_directory, "state_directory")
        ).resolve()
        self.mount_id = _text(self.mount_id, "mount_id") or DEFAULT_MOUNT_ID
        self.generation_id = (
            _text(self.generation_id, "generation_id") or DEFAULT_GENERATION_ID
        )
        self.readiness_timeout_seconds = _positive_float(
            self.readiness_timeout_seconds, "readiness_timeout_seconds"
        )
        self.heartbeat_interval_seconds = _positive_float(
            self.heartbeat_interval_seconds, "heartbeat_interval_seconds"
        )
        self.unmount_timeout_seconds = _positive_float(
            self.unmount_timeout_seconds, "unmount_timeout_seconds"
        )
        self.drain_timeout_seconds = _positive_float(
            self.drain_timeout_seconds, "drain_timeout_seconds"
        )
        self.worker_stop_timeout_seconds = _positive_float(
            self.worker_stop_timeout_seconds, "worker_stop_timeout_seconds"
        )
        self.callback_drain_bound = _bounded_int(
            self.callback_drain_bound, "callback_drain_bound", minimum=1
        )
        self.stale_heartbeat_seconds = _positive_float(
            self.stale_heartbeat_seconds, "stale_heartbeat_seconds"
        )
        self.hermetic = _bool(self.hermetic, "hermetic")
        self.recovery_delay_seconds = _nonneg_float(
            self.recovery_delay_seconds, "recovery_delay_seconds"
        )
        self.fail_before_ready = _bool(self.fail_before_ready, "fail_before_ready")
        self.suppress_ready = _bool(self.suppress_ready, "suppress_ready")
        self.cache_generation = _bounded_int(
            self.cache_generation, "cache_generation", minimum=0
        )
        self.cache_entries = _bounded_int(
            self.cache_entries, "cache_entries", minimum=0
        )
        if self.holder_id is not None:
            self.holder_id = _text(self.holder_id, "holder_id") or None
        if self.python_executable is not None:
            self.python_executable = _path_text(
                self.python_executable, "python_executable"
            )

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": CHILD_CONFIG_SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "task_id": TASK_ID,
            "mountpoint": str(self.mountpoint),
            "state_directory": str(self.state_directory),
            "mount_id": self.mount_id,
            "generation_id": self.generation_id,
            "readiness_timeout_seconds": self.readiness_timeout_seconds,
            "heartbeat_interval_seconds": self.heartbeat_interval_seconds,
            "unmount_timeout_seconds": self.unmount_timeout_seconds,
            "drain_timeout_seconds": self.drain_timeout_seconds,
            "worker_stop_timeout_seconds": self.worker_stop_timeout_seconds,
            "callback_drain_bound": self.callback_drain_bound,
            "stale_heartbeat_seconds": self.stale_heartbeat_seconds,
            "hermetic": self.hermetic,
            "recovery_delay_seconds": self.recovery_delay_seconds,
            "fail_before_ready": self.fail_before_ready,
            "suppress_ready": self.suppress_ready,
            "cache_generation": self.cache_generation,
            "cache_entries": self.cache_entries,
            "holder_id": self.holder_id,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "LinuxMountConfig":
        return cls(
            mountpoint=str(payload["mountpoint"]),
            state_directory=str(payload["state_directory"]),
            mount_id=str(payload.get("mount_id") or DEFAULT_MOUNT_ID),
            generation_id=str(payload.get("generation_id") or DEFAULT_GENERATION_ID),
            readiness_timeout_seconds=float(
                payload.get("readiness_timeout_seconds")
                or DEFAULT_READINESS_TIMEOUT_SECONDS
            ),
            heartbeat_interval_seconds=float(
                payload.get("heartbeat_interval_seconds")
                or DEFAULT_HEARTBEAT_INTERVAL_SECONDS
            ),
            unmount_timeout_seconds=float(
                payload.get("unmount_timeout_seconds")
                or DEFAULT_UNMOUNT_TIMEOUT_SECONDS
            ),
            drain_timeout_seconds=float(
                payload.get("drain_timeout_seconds") or DEFAULT_DRAIN_TIMEOUT_SECONDS
            ),
            worker_stop_timeout_seconds=float(
                payload.get("worker_stop_timeout_seconds")
                or DEFAULT_WORKER_STOP_TIMEOUT_SECONDS
            ),
            callback_drain_bound=int(
                payload.get("callback_drain_bound") or DEFAULT_CALLBACK_DRAIN_BOUND
            ),
            stale_heartbeat_seconds=float(
                payload.get("stale_heartbeat_seconds")
                or DEFAULT_STALE_HEARTBEAT_SECONDS
            ),
            hermetic=bool(payload.get("hermetic", True)),
            recovery_delay_seconds=float(payload.get("recovery_delay_seconds") or 0.0),
            fail_before_ready=bool(payload.get("fail_before_ready", False)),
            suppress_ready=bool(payload.get("suppress_ready", False)),
            cache_generation=int(payload.get("cache_generation") or 1),
            cache_entries=int(payload.get("cache_entries") or 0),
            holder_id=payload.get("holder_id"),
        )


# ---------------------------------------------------------------------------
# Bounded callback drain + workers (child-side)
# ---------------------------------------------------------------------------


class BoundedCallbackQueue:
    """Bounded in-flight callback tracker used during drain on unmount."""

    def __init__(self, bound: int = DEFAULT_CALLBACK_DRAIN_BOUND) -> None:
        self.bound = max(1, int(bound))
        self._lock = threading.RLock()
        self._inflight: dict[str, float] = {}
        self._draining = False
        self._drained = 0

    @property
    def open_count(self) -> int:
        with self._lock:
            return len(self._inflight)

    @property
    def drained(self) -> int:
        with self._lock:
            return self._drained

    def begin(self, callback_id: str | None = None) -> str:
        with self._lock:
            if self._draining:
                raise LinuxLifecycleError(
                    "callback queue is draining; new callbacks rejected",
                    code=LifecycleErrorCode.UNMOUNT,
                )
            if len(self._inflight) >= self.bound:
                raise LinuxLifecycleError(
                    "callback drain bound exceeded",
                    code=LifecycleErrorCode.BOUND_EXCEEDED,
                    detail={"bound": self.bound},
                )
            cid = callback_id or f"cb:{uuid.uuid4().hex[:12]}"
            self._inflight[cid] = _monotonic()
            return cid

    def end(self, callback_id: str) -> None:
        with self._lock:
            if self._inflight.pop(callback_id, None) is not None:
                self._drained += 1

    def start_drain(self) -> None:
        with self._lock:
            self._draining = True

    def drain(self, *, timeout_seconds: float) -> int:
        """Wait up to ``timeout_seconds`` for inflight callbacks to finish.

        Remaining callbacks after the bound are forcibly abandoned so unmount
        never blocks indefinitely.
        """

        self.start_drain()
        deadline = _monotonic() + max(0.0, float(timeout_seconds))
        while _monotonic() < deadline:
            with self._lock:
                if not self._inflight:
                    return self._drained
            time.sleep(0.005)
        with self._lock:
            abandoned = list(self._inflight.keys())
            for cid in abandoned:
                self._inflight.pop(cid, None)
                self._drained += 1
            return self._drained


class BoundedWorker:
    """Simple heartbeat worker that stops cleanly on request."""

    def __init__(
        self,
        name: str,
        *,
        interval_seconds: float = DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
        on_cycle: Callable[["BoundedWorker"], None] | None = None,
    ) -> None:
        self.name = name
        self.interval_seconds = max(0.01, float(interval_seconds))
        self.on_cycle = on_cycle
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.cycle = 0
        self.running = False

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self.running = True
        self._thread = threading.Thread(
            target=self._loop,
            name=f"kvfs-linux-worker-{self.name}",
            daemon=True,
        )
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop.is_set():
            self.cycle += 1
            if self.on_cycle is not None:
                try:
                    self.on_cycle(self)
                except Exception:  # noqa: BLE001 — worker must not die on cycle errors
                    pass
            self._stop.wait(self.interval_seconds)
        self.running = False

    def stop(self, *, timeout_seconds: float = DEFAULT_WORKER_STOP_TIMEOUT_SECONDS) -> bool:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=max(0.0, float(timeout_seconds)))
        self.running = False
        return not (thread is not None and thread.is_alive())


# ---------------------------------------------------------------------------
# Child daemon
# ---------------------------------------------------------------------------


def _child_paths(state_directory: Path) -> dict[str, Path]:
    return {
        "ready": state_directory / READY_FILENAME,
        "heartbeat": state_directory / HEARTBEAT_FILENAME,
        "status": state_directory / STATUS_FILENAME,
        "pid": state_directory / CHILD_PID_FILENAME,
        "unmount_request": state_directory / UNMOUNT_REQUEST_FILENAME,
        "shutdown": state_directory / SHUTDOWN_RECEIPT_FILENAME,
        "config": state_directory / CHILD_CONFIG_FILENAME,
        "recovery": state_directory / RECOVERY_DIRNAME,
        "cache": state_directory / CACHE_DIRNAME,
        "wal": state_directory / WAL_DIRNAME,
    }


def run_child_daemon(config_path: str | Path) -> int:
    """Child-process entry point. Recovery precedes ready; then heartbeat.

    Returns a process exit code (0 success, nonzero failure).
    """

    config_path = Path(config_path)
    raw = _read_json(config_path)
    if not raw:
        return 2
    config = LinuxMountConfig.from_dict(raw)
    return _ChildDaemon(config).run()


class _ChildDaemon:
    """Foreground child implementing recovery → ready → heartbeat → drain."""

    def __init__(self, config: LinuxMountConfig) -> None:
        self.config = config
        self.state_directory = Path(config.state_directory)
        self.mountpoint = Path(config.mountpoint)
        self.paths = _child_paths(self.state_directory)
        self.pid = os.getpid()
        self.trace = LifecycleTrace()
        self.callbacks = BoundedCallbackQueue(config.callback_drain_bound)
        self.workers: list[BoundedWorker] = []
        self._stop = threading.Event()
        self._signal_name = ""
        self._lifecycle = HostMountLifecycle(
            mount_id=config.mount_id,
            state=MountLifecycleState.UNINITIALIZED,
            platform=HostPlatform.LINUX,
            recovery_required=True,
            recovery_complete=False,
            ready=False,
        )
        self._recovery: MountRecoveryCoordinator | None = None
        self._recovery_receipt: MountRecoveryReceipt | None = None
        self._wal_position = "0"
        self._cache_generation = int(config.cache_generation)
        self._cache_entries = int(config.cache_entries)
        self._sequence = 0
        self._lock = threading.RLock()
        self._mounted = False  # hermetic: never true for native mount
        self._shutdown_written = False

    def run(self) -> int:
        self.state_directory.mkdir(parents=True, exist_ok=True)
        self.mountpoint.mkdir(parents=True, exist_ok=True)
        self.paths["recovery"].mkdir(parents=True, exist_ok=True)
        self.paths["cache"].mkdir(parents=True, exist_ok=True)
        self.paths["wal"].mkdir(parents=True, exist_ok=True)
        _atomic_write_json(self.paths["pid"], {"pid": self.pid, "unix_ms": _unix_ms()})
        self._install_signals()

        try:
            # 1. Foreground recovery — MUST complete before ready.
            if not self._recover():
                return 1

            # 2. Optional deliberate failure paths for tests.
            if self.config.fail_before_ready:
                self.trace.record(
                    LifecycleTraceKind.FAULT,
                    success=False,
                    phase=LifecyclePhase.FAILED.value,
                    code=LifecycleErrorCode.RECOVERY.value,
                )
                # Must close recovery before exit: DurableMutationCoordinator /
                # WALWriter starts a non-daemon group-commit thread that would
                # otherwise keep the child process alive after return, causing
                # the parent to observe readiness timeout instead of CHILD_EXIT.
                self._close_recovery()
                try:
                    self._write_status(ready=False, exit_code=1)
                except Exception:  # noqa: BLE001
                    pass
                # Hard-exit so a leaked non-daemon worker cannot block process
                # termination after the deliberate pre-ready failure.
                os._exit(1)

            if self.config.suppress_ready:
                # Stay alive without advertising ready (parent readiness timeout).
                while not self._stop.is_set():
                    self._stop.wait(0.05)
                return self._shutdown(signal_name=self._signal_name or "suppress_ready")

            # 3. Advertise readiness only after recovery_complete.
            self._advertise_ready()

            # 4. Start bounded workers + heartbeat loop.
            self._start_workers()
            return self._serve_loop()
        except Exception as exc:  # noqa: BLE001
            self.trace.record(
                LifecycleTraceKind.FAULT,
                success=False,
                phase=LifecyclePhase.FAILED.value,
                code=LifecycleErrorCode.INTERNAL.value,
                detail={"error": str(exc)},
            )
            try:
                self._write_status(ready=False, exit_code=1)
            except Exception:  # noqa: BLE001
                pass
            try:
                self._shutdown(signal_name="exception", force=True)
            except Exception:  # noqa: BLE001
                pass
            return 1

    def _install_signals(self) -> None:
        def _handler(signum: int, _frame: Any) -> None:
            try:
                self._signal_name = signal.Signals(signum).name
            except (ValueError, AttributeError):
                self._signal_name = str(signum)
            self.trace.record(
                LifecycleTraceKind.SIGNAL,
                success=True,
                phase=LifecyclePhase.SIGNAL.value,
                detail={"signal": self._signal_name},
            )
            self._stop.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, _handler)
            except (ValueError, OSError):
                # Not main thread / unsupported — unmount.request still works.
                pass

    def _set_lifecycle(self, to_state: MountLifecycleState) -> None:
        with self._lock:
            current = self._lifecycle
            if current.state is to_state:
                return
            if not is_legal_mount_transition(current.state, to_state):
                assert_legal_mount_transition(current.state, to_state)
            self._lifecycle = current.transition_to(to_state)

    def _close_recovery(self) -> None:
        """Release lease and stop owned WAL workers so the process can exit."""

        recovery = self._recovery
        self._recovery = None
        if recovery is None:
            return
        try:
            recovery.close()
        except Exception:  # noqa: BLE001 — exit paths must not hang on close
            pass

    def _recover(self) -> bool:
        self.trace.record(
            LifecycleTraceKind.RECOVERY,
            success=True,
            phase=LifecyclePhase.CHILD_RECOVER.value,
        )
        if self.config.recovery_delay_seconds > 0:
            # Cooperative delay that still respects stop.
            deadline = _monotonic() + self.config.recovery_delay_seconds
            while _monotonic() < deadline and not self._stop.is_set():
                time.sleep(min(0.05, deadline - _monotonic()))
            if self._stop.is_set():
                return False

        recovery_root = self.paths["recovery"]
        try:
            self._recovery = MountRecoveryCoordinator(
                recovery_root,
                mount_id=self.config.mount_id,
                generation_id=self.config.generation_id,
                platform=HostPlatform.LINUX,
                holder_id=self.config.holder_id,
                recovery_timeout_seconds=min(
                    30.0, max(1.0, self.config.readiness_timeout_seconds)
                ),
            )
            # Lifecycle: uninitialized → initializing → recovering via coordinator.
            receipt = self._recovery.recover()
            self._recovery_receipt = receipt
            if not receipt.success or not receipt.ready or not receipt.recovery_complete:
                self.trace.record(
                    LifecycleTraceKind.RECOVERY,
                    success=False,
                    phase=LifecyclePhase.CHILD_RECOVER.value,
                    code=LifecycleErrorCode.RECOVERY.value,
                    detail=receipt.to_record() if hasattr(receipt, "to_record") else {},
                )
                self._write_status(ready=False, exit_code=1)
                self._close_recovery()
                return False

            # Mirror recovery lifecycle onto child host lifecycle.
            with self._lock:
                self._lifecycle = HostMountLifecycle(
                    mount_id=self.config.mount_id,
                    state=MountLifecycleState.READY,
                    platform=HostPlatform.LINUX,
                    recovery_required=True,
                    recovery_complete=True,
                    ready=True,
                    generation=self._cache_generation,
                )
            self._wal_position = (
                f"gen={self.config.generation_id};replayed={receipt.replayed}"
            )
            # Preserve a recovery receipt copy under state (never delete).
            evidence = self.state_directory / "recovery-preserved"
            evidence.mkdir(parents=True, exist_ok=True)
            _atomic_write_json(
                evidence / f"recovery-{_unix_ms()}.json",
                receipt.to_record(),
            )
            self.trace.record(
                LifecycleTraceKind.RECOVERY,
                success=True,
                phase=LifecyclePhase.CHILD_RECOVER.value,
                detail={
                    "recovery_complete": True,
                    "phases": list(receipt.phases),
                    "disposition": receipt.disposition.value
                    if isinstance(receipt.disposition, RecoveryDisposition)
                    else str(receipt.disposition),
                },
            )
            return True
        except StateLeaseHeldError as exc:
            self.trace.record(
                LifecycleTraceKind.FAULT,
                success=False,
                phase=LifecyclePhase.CHILD_RECOVER.value,
                code=LifecycleErrorCode.LEASE.value,
                detail=exc.to_record(),
            )
            self._write_status(ready=False, exit_code=1)
            self._close_recovery()
            return False
        except Exception as exc:  # noqa: BLE001
            self.trace.record(
                LifecycleTraceKind.FAULT,
                success=False,
                phase=LifecyclePhase.CHILD_RECOVER.value,
                code=LifecycleErrorCode.RECOVERY.value,
                detail={"error": str(exc)},
            )
            self._write_status(ready=False, exit_code=1)
            self._close_recovery()
            return False

    def _advertise_ready(self) -> None:
        # Invariant: recovery_complete must be true before ready file exists.
        life = self._lifecycle
        if not life.recovery_complete or not life.ready:
            raise LifecycleProtocolError(
                "cannot advertise ready before recovery completes",
                detail=life.to_record(),
            )
        phases: tuple[str, ...] = ()
        if self._recovery_receipt is not None:
            phases = tuple(self._recovery_receipt.phases)
            # Explicit ordering: recovery phases precede ready advertisement.
            if "enter_ready" in phases:
                idx_ready = phases.index("enter_ready")
                if "replay_wal" in phases and phases.index("replay_wal") > idx_ready:
                    raise LifecycleProtocolError(
                        "recovery phase ordering violated: replay_wal after enter_ready",
                        detail={"phases": list(phases)},
                    )
                if (
                    "acquire_lease" in phases
                    and phases.index("acquire_lease") > idx_ready
                ):
                    raise LifecycleProtocolError(
                        "recovery phase ordering violated: acquire_lease after enter_ready",
                        detail={"phases": list(phases)},
                    )

        holder_id = ""
        if self._recovery is not None and self._recovery.lease.holder is not None:
            holder_id = self._recovery.lease.holder.holder_id

        readiness = MountReadiness(
            mount_id=self.config.mount_id,
            pid=self.pid,
            mountpoint=str(self.mountpoint),
            state_directory=str(self.state_directory),
            recovery_complete=True,
            ready=True,
            lifecycle_state=MountLifecycleState.READY.value,
            wal_generation=self.config.generation_id,
            cache_generation=self._cache_generation,
            ready_unix_ms=_unix_ms(),
            holder_id=holder_id,
            recovery_phases=phases,
        )
        # Heartbeat + status first so observers never see ready without binds.
        self._write_heartbeat()
        self._write_status(ready=True)
        _atomic_write_json(self.paths["ready"], readiness.to_record())
        self.trace.record(
            LifecycleTraceKind.READY,
            success=True,
            phase=LifecyclePhase.CHILD_READY.value,
            detail=readiness.to_record(),
        )

    def _start_workers(self) -> None:
        def _on_cycle(_worker: BoundedWorker) -> None:
            # Simulated cache/WAL progress for status binding.
            with self._lock:
                self._cache_entries = max(self._cache_entries, _worker.cycle)

        worker = BoundedWorker(
            "status",
            interval_seconds=self.config.heartbeat_interval_seconds,
            on_cycle=_on_cycle,
        )
        worker.start()
        self.workers.append(worker)
        self.trace.record(
            LifecycleTraceKind.WORKER,
            success=True,
            phase=LifecyclePhase.HEARTBEAT.value,
            detail={"workers": len(self.workers)},
        )

    def _serve_loop(self) -> int:
        interval = self.config.heartbeat_interval_seconds
        while not self._stop.is_set():
            if self.paths["unmount_request"].exists():
                self._signal_name = self._signal_name or "unmount_request"
                self._stop.set()
                break
            self._write_heartbeat()
            self._write_status(ready=True)
            self._stop.wait(interval)
        return self._shutdown(signal_name=self._signal_name or "stop")

    def _write_heartbeat(self) -> MountHeartbeat:
        with self._lock:
            self._sequence += 1
            life = self._lifecycle
            hb = MountHeartbeat(
                mount_id=self.config.mount_id,
                pid=self.pid,
                mountpoint=str(self.mountpoint),
                state_directory=str(self.state_directory),
                lifecycle_state=life.state.value,
                wal_generation=self.config.generation_id,
                wal_position=self._wal_position,
                cache_generation=self._cache_generation,
                cache_entries=self._cache_entries,
                heartbeat_unix_ms=_unix_ms(),
                sequence=self._sequence,
                open_callbacks=self.callbacks.open_count,
                workers_running=sum(1 for w in self.workers if w.running),
            )
        _atomic_write_json(self.paths["heartbeat"], hb.to_record())
        self.trace.record(
            LifecycleTraceKind.HEARTBEAT,
            success=True,
            phase=LifecyclePhase.HEARTBEAT.value,
            detail={"sequence": hb.sequence, "pid": hb.pid},
        )
        return hb

    def _write_status(
        self,
        *,
        ready: bool,
        exit_code: int | None = None,
    ) -> MountStatus:
        with self._lock:
            life = self._lifecycle
            lease_held = bool(
                self._recovery is not None and self._recovery.lease.held
            )
            holder_id = ""
            if (
                self._recovery is not None
                and self._recovery.lease.holder is not None
            ):
                holder_id = self._recovery.lease.holder.holder_id
            status = MountStatus(
                mount_id=self.config.mount_id,
                pid=self.pid,
                mountpoint=str(self.mountpoint),
                state_directory=str(self.state_directory),
                lifecycle_state=life.state.value,
                ready=ready and life.ready,
                recovery_complete=life.recovery_complete,
                lease_held=lease_held,
                holder_id=holder_id,
                wal={
                    "generation": self.config.generation_id,
                    "position": self._wal_position,
                    "directory": str(self.paths["wal"]),
                },
                cache={
                    "generation": self._cache_generation,
                    "entries": self._cache_entries,
                    "directory": str(self.paths["cache"]),
                },
                workers={
                    "running": sum(1 for w in self.workers if w.running),
                    "names": [w.name for w in self.workers],
                },
                open_callbacks=self.callbacks.open_count,
                mounted=self._mounted and ready,
                status_unix_ms=_unix_ms(),
                heartbeat_unix_ms=_unix_ms(),
                exit_code=exit_code,
            )
        _atomic_write_json(self.paths["status"], status.to_record())
        self.trace.record(
            LifecycleTraceKind.STATUS,
            success=True,
            phase=LifecyclePhase.STATUS.value,
            detail={"ready": status.ready, "pid": status.pid},
        )
        return status

    def _shutdown(self, *, signal_name: str = "", force: bool = False) -> int:
        if self._shutdown_written and not force:
            return 0
        started = _monotonic()
        self.trace.record(
            LifecycleTraceKind.UNMOUNT,
            success=True,
            phase=LifecyclePhase.UNMOUNT.value,
            detail={"signal": signal_name},
        )

        # Drain bounded callbacks (never block unbounded).
        self.callbacks.start_drain()
        drained = self.callbacks.drain(
            timeout_seconds=self.config.drain_timeout_seconds
        )
        self.trace.record(
            LifecycleTraceKind.DRAIN,
            success=True,
            phase=LifecyclePhase.DRAIN_CALLBACKS.value,
            detail={"callbacks_drained": drained},
        )

        # Stop workers.
        workers_stopped = 0
        for worker in list(self.workers):
            if worker.stop(timeout_seconds=self.config.worker_stop_timeout_seconds):
                workers_stopped += 1
        self.trace.record(
            LifecycleTraceKind.WORKER,
            success=True,
            phase=LifecyclePhase.STOP_WORKERS.value,
            detail={"workers_stopped": workers_stopped},
        )

        # Transition lifecycle: ready → draining → destroying → destroyed.
        with self._lock:
            state = self._lifecycle.state
        try:
            if state is MountLifecycleState.READY:
                self._set_lifecycle(MountLifecycleState.DRAINING)
            state = self._lifecycle.state
            if state is MountLifecycleState.DRAINING:
                self._set_lifecycle(MountLifecycleState.DESTROYING)
            state = self._lifecycle.state
            if state is MountLifecycleState.DESTROYING:
                self._set_lifecycle(MountLifecycleState.DESTROYED)
            elif state is not MountLifecycleState.DESTROYED:
                if is_legal_mount_transition(state, MountLifecycleState.DESTROYED):
                    self._set_lifecycle(MountLifecycleState.DESTROYED)
                elif is_legal_mount_transition(state, MountLifecycleState.DESTROYING):
                    self._set_lifecycle(MountLifecycleState.DESTROYING)
                    self._set_lifecycle(MountLifecycleState.DESTROYED)
                else:
                    with self._lock:
                        self._lifecycle = HostMountLifecycle(
                            mount_id=self.config.mount_id,
                            state=MountLifecycleState.DESTROYED,
                            platform=HostPlatform.LINUX,
                            recovery_required=True,
                            recovery_complete=self._lifecycle.recovery_complete,
                            ready=False,
                            generation=self._cache_generation,
                        )
        except Exception:  # noqa: BLE001 — shutdown must complete
            with self._lock:
                self._lifecycle = HostMountLifecycle(
                    mount_id=self.config.mount_id,
                    state=MountLifecycleState.DESTROYED,
                    platform=HostPlatform.LINUX,
                    recovery_required=True,
                    recovery_complete=True,
                    ready=False,
                )

        # Release mount (hermetic: clear mounted flag; never delete state).
        self._mounted = False
        mount_released = True
        self.trace.record(
            LifecycleTraceKind.UNMOUNT,
            success=True,
            phase=LifecyclePhase.RELEASE_MOUNT.value,
        )

        # Preserve recovery state BEFORE releasing lease (never delete WAL/evidence).
        preserved = self._preserve_recovery_state()
        self.trace.record(
            LifecycleTraceKind.RECEIPT,
            success=preserved,
            phase=LifecyclePhase.PRESERVE_RECOVERY.value,
            detail={"preserved": preserved},
        )

        # Release lease last.
        lease_released = False
        if self._recovery is not None:
            try:
                lease_released = bool(self._recovery.lease.release())
                # Close coordinator without wiping recovery data.
                try:
                    self._recovery.close()
                except Exception:  # noqa: BLE001
                    pass
            except Exception:  # noqa: BLE001
                lease_released = False
        self.trace.record(
            LifecycleTraceKind.LEASE,
            success=True,
            phase=LifecyclePhase.RELEASE_LEASE.value,
            detail={"lease_released": lease_released},
        )

        receipt = UnmountReceipt(
            mount_id=self.config.mount_id,
            disposition=LifecycleDisposition.STOPPED,
            success=True,
            pid=self.pid,
            callbacks_drained=drained,
            workers_stopped=workers_stopped,
            lease_released=lease_released,
            mount_released=mount_released,
            recovery_preserved=preserved,
            lifecycle_state=self._lifecycle.state.value,
            signal_name=signal_name,
            idempotent=False,
            elapsed_seconds=_monotonic() - started,
            exit_code=0,
            detail={"hermetic": self.config.hermetic},
        )
        _atomic_write_json(self.paths["shutdown"], receipt.to_record())
        self._write_status(ready=False, exit_code=0)
        # Remove ready marker so parents do not treat us as live.
        _safe_unlink(self.paths["ready"])
        _safe_unlink(self.paths["unmount_request"])
        self._shutdown_written = True
        return 0

    def _preserve_recovery_state(self) -> bool:
        """Ensure recovery/WAL/cache directories remain after unmount."""

        try:
            preserve_dir = self.state_directory / "recovery-preserved"
            preserve_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "schema": f"{LINUX_NAMESPACE}/recovery-preserve@{SCHEMA_MAJOR}",
                "mount_id": self.config.mount_id,
                "pid": self.pid,
                "unix_ms": _unix_ms(),
                "wal_directory": str(self.paths["wal"]),
                "cache_directory": str(self.paths["cache"]),
                "recovery_directory": str(self.paths["recovery"]),
                "wal_generation": self.config.generation_id,
                "wal_position": self._wal_position,
                "cache_generation": self._cache_generation,
                "lifecycle": self._lifecycle.to_record(),
                "trace": self.trace.to_records()[-32:],
            }
            if self._recovery_receipt is not None:
                payload["last_recovery_receipt"] = self._recovery_receipt.to_record()
            _atomic_write_json(
                preserve_dir / f"shutdown-preserve-{_unix_ms()}.json", payload
            )
            # Hard invariant: recovery root must still exist.
            return self.paths["recovery"].exists() and self.paths["wal"].exists()
        except Exception:  # noqa: BLE001
            return False


# ---------------------------------------------------------------------------
# Parent launcher / lifecycle controller
# ---------------------------------------------------------------------------


class LinuxMountLifecycle:
    """Parent-side Linux mount lifecycle controller (launcher).

    Spawns a child process, waits for readiness within the declared budget,
    exposes heartbeat/status, and performs bounded signal/unmount cleanup.
    """

    SCHEMA: ClassVar[str] = LINUX_MOUNT_LIFECYCLE_SCHEMA
    CONTRACT_VERSION: ClassVar[int] = CONTRACT_VERSION

    def __init__(self, config: LinuxMountConfig) -> None:
        if not isinstance(config, LinuxMountConfig):
            raise LinuxLifecycleError(
                "config must be a LinuxMountConfig",
                code=LifecycleErrorCode.VALIDATION,
            )
        self.config = config
        self.state_directory = Path(config.state_directory)
        self.mountpoint = Path(config.mountpoint)
        self.paths = _child_paths(self.state_directory)
        self.trace = LifecycleTrace()
        self._proc: subprocess.Popen[Any] | None = None
        self._lock = threading.RLock()
        self._started = False
        self._stopped = False
        self._readiness: MountReadiness | None = None
        self._last_unmount: UnmountReceipt | None = None
        self._lifecycle_state = MountLifecycleState.UNINITIALIZED

    # -- properties ---------------------------------------------------------

    @property
    def pid(self) -> int | None:
        with self._lock:
            if self._proc is None:
                return None
            return self._proc.pid

    @property
    def running(self) -> bool:
        with self._lock:
            return (
                self._proc is not None
                and self._proc.poll() is None
                and not self._stopped
            )

    @property
    def ready(self) -> bool:
        readiness = self.read_readiness()
        return bool(readiness and readiness.ready and readiness.recovery_complete)

    @property
    def lifecycle_state(self) -> MountLifecycleState:
        with self._lock:
            return self._lifecycle_state

    @property
    def last_unmount(self) -> UnmountReceipt | None:
        with self._lock:
            return self._last_unmount

    # -- start / wait ready -------------------------------------------------

    def start(self, *, wait_ready: bool = True) -> MountReadiness:
        """Spawn the child daemon and optionally wait for readiness.

        When readiness does not arrive within
        ``config.readiness_timeout_seconds``, the child is terminated and a
        :class:`ReadinessTimeoutError` is raised (nonzero exit semantics).
        """

        with self._lock:
            if self._started and self.running:
                raise LinuxLifecycleError(
                    "mount lifecycle already running",
                    code=LifecycleErrorCode.ALREADY_RUNNING,
                    detail={"pid": self.pid},
                )
            if self._stopped and self._proc is not None and self._proc.poll() is None:
                raise LinuxLifecycleError(
                    "previous child still shutting down",
                    code=LifecycleErrorCode.PROTOCOL,
                )

        self.state_directory.mkdir(parents=True, exist_ok=True)
        self.mountpoint.mkdir(parents=True, exist_ok=True)
        # Clear prior ready marker so we do not observe a stale handshake.
        _safe_unlink(self.paths["ready"])
        _safe_unlink(self.paths["unmount_request"])
        _safe_unlink(self.paths["shutdown"])

        _atomic_write_json(self.paths["config"], self.config.to_record())
        self.trace.record(
            LifecycleTraceKind.ADMIT,
            success=True,
            phase=LifecyclePhase.ADMIT.value,
            detail={"mount_id": self.config.mount_id},
        )
        self._lifecycle_state = MountLifecycleState.INITIALIZING

        python = self.config.python_executable or sys.executable
        # Invoke child via -c so we do not depend on package __main__.
        # Config path is passed through the environment to avoid shell/quoting
        # issues with arbitrary filesystem paths.
        env = os.environ.copy()
        if self.config.env:
            env.update({str(k): str(v) for k, v in self.config.env.items()})
        env["KVFS_LINUX_CHILD_CONFIG"] = str(self.paths["config"])
        code = (
            "import os,sys;"
            "from ipfs_kit_py.kernel_vfs.linux import run_child_daemon;"
            "sys.exit(run_child_daemon(os.environ['KVFS_LINUX_CHILD_CONFIG']))"
        )
        # Ensure package import path includes the nested package root when needed.
        try:
            import ipfs_kit_py as _pkg

            pkg_root = str(Path(_pkg.__file__).resolve().parent.parent)
            existing = env.get("PYTHONPATH", "")
            parts = [p for p in existing.split(os.pathsep) if p]
            if pkg_root not in parts:
                env["PYTHONPATH"] = (
                    pkg_root if not parts else pkg_root + os.pathsep + existing
                )
        except Exception:  # noqa: BLE001
            pass

        # Optional child log for diagnostics (never required for readiness).
        child_log = self.state_directory / "child.stderr.log"
        log_fh = None
        try:
            log_fh = open(child_log, "wb")
            stderr_target: Any = log_fh
        except OSError:
            stderr_target = subprocess.DEVNULL

        try:
            proc = subprocess.Popen(
                [python, "-c", code],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=stderr_target,
                start_new_session=True,
            )
        except OSError as exc:
            self._lifecycle_state = MountLifecycleState.FAILED
            raise ChildProcessError(
                f"failed to spawn mount child: {exc}",
                code=LifecycleErrorCode.CHILD_SPAWN,
                detail={"error": str(exc)},
            ) from exc
        finally:
            # Parent does not retain the log handle; child inherits the fd.
            if log_fh is not None:
                try:
                    log_fh.close()
                except Exception:  # noqa: BLE001
                    pass

        with self._lock:
            self._proc = proc
            self._started = True
            self._stopped = False
            self._readiness = None
            self._last_unmount = None

        self.trace.record(
            LifecycleTraceKind.SPAWN,
            success=True,
            phase=LifecyclePhase.SPAWN_CHILD.value,
            detail={"pid": proc.pid},
        )

        if not wait_ready:
            return MountReadiness(
                mount_id=self.config.mount_id,
                pid=proc.pid or 0,
                mountpoint=str(self.mountpoint),
                state_directory=str(self.state_directory),
                recovery_complete=False,
                ready=False,
                lifecycle_state=MountLifecycleState.INITIALIZING.value,
            )

        return self.wait_ready()

    def wait_ready(
        self,
        *,
        timeout_seconds: float | None = None,
    ) -> MountReadiness:
        """Block until readiness or fail with nonzero-exit semantics."""

        timeout = (
            self.config.readiness_timeout_seconds
            if timeout_seconds is None
            else _positive_float(timeout_seconds, "timeout_seconds")
        )
        started = _monotonic()
        self.trace.record(
            LifecycleTraceKind.READY,
            success=True,
            phase=LifecyclePhase.PARENT_WAIT_READY.value,
            detail={"timeout_seconds": timeout},
        )
        while True:
            elapsed = _monotonic() - started

            # Prefer CHILD_EXIT over readiness timeout: check process first.
            child_error = self._child_exit_before_ready(elapsed_seconds=elapsed)
            if child_error is not None:
                raise child_error

            readiness = self.read_readiness()
            if readiness is not None and readiness.ready and readiness.recovery_complete:
                # Enforce recovery-before-ready ordering in the handshake.
                phases = readiness.recovery_phases
                if phases:
                    if "enter_ready" in phases and "acquire_lease" in phases:
                        if phases.index("acquire_lease") > phases.index("enter_ready"):
                            self._fail_child_after_protocol(
                                "recovery phase ordering violated: lease after ready"
                            )
                            raise LifecycleProtocolError(
                                "recovery phase ordering violated",
                                detail={"phases": list(phases)},
                            )
                    if "enter_ready" in phases and "replay_wal" in phases:
                        if phases.index("replay_wal") > phases.index("enter_ready"):
                            self._fail_child_after_protocol(
                                "recovery phase ordering violated: replay after ready"
                            )
                            raise LifecycleProtocolError(
                                "recovery phase ordering violated",
                                detail={"phases": list(phases)},
                            )
                with self._lock:
                    self._readiness = readiness
                    self._lifecycle_state = MountLifecycleState.READY
                self.trace.record(
                    LifecycleTraceKind.READY,
                    success=True,
                    phase=LifecyclePhase.CHILD_READY.value,
                    detail=readiness.to_record(),
                )
                return readiness

            if elapsed > timeout:
                # Final re-poll so a child that exited at the deadline is not
                # misreported as a readiness timeout.
                child_error = self._child_exit_before_ready(elapsed_seconds=elapsed)
                if child_error is not None:
                    raise child_error
                pid = self.pid or 0
                self._terminate_child(reason="readiness_timeout")
                self._lifecycle_state = MountLifecycleState.FAILED
                self.trace.record(
                    LifecycleTraceKind.FAULT,
                    success=False,
                    phase=LifecyclePhase.FAILED.value,
                    code=LifecycleErrorCode.READINESS_TIMEOUT.value,
                    detail={
                        "timeout_seconds": timeout,
                        "elapsed_seconds": elapsed,
                        "pid": pid,
                    },
                )
                raise ReadinessTimeoutError(
                    timeout_seconds=timeout,
                    elapsed_seconds=elapsed,
                    pid=pid,
                )
            time.sleep(0.01)

    def _child_exit_before_ready(
        self, *, elapsed_seconds: float
    ) -> ChildProcessError | None:
        """Return a CHILD_EXIT error if the child already terminated."""

        proc = self._proc
        if proc is None:
            return None
        rc = proc.poll()
        if rc is None:
            return None
        self._lifecycle_state = MountLifecycleState.FAILED
        self.trace.record(
            LifecycleTraceKind.FAULT,
            success=False,
            phase=LifecyclePhase.FAILED.value,
            code=LifecycleErrorCode.CHILD_EXIT.value,
            detail={"returncode": rc, "elapsed_seconds": elapsed_seconds},
        )
        return ChildProcessError(
            f"mount child exited before ready (code={rc})",
            pid=proc.pid or 0,
            returncode=rc,
            detail={"elapsed_seconds": elapsed_seconds},
        )

    def _fail_child_after_protocol(self, reason: str) -> None:
        self.trace.record(
            LifecycleTraceKind.FAULT,
            success=False,
            phase=LifecyclePhase.FAILED.value,
            code=LifecycleErrorCode.PROTOCOL.value,
            detail={"reason": reason},
        )
        self._terminate_child(reason=reason)

    # -- status / heartbeat -------------------------------------------------

    def read_readiness(self) -> MountReadiness | None:
        raw = _read_json(self.paths["ready"])
        if not raw:
            return None
        try:
            return MountReadiness.from_dict(raw)
        except Exception:  # noqa: BLE001
            return None

    def read_heartbeat(self) -> MountHeartbeat | None:
        raw = _read_json(self.paths["heartbeat"])
        if not raw:
            return None
        try:
            return MountHeartbeat.from_dict(raw)
        except Exception:  # noqa: BLE001
            return None

    def read_status(self) -> MountStatus | None:
        raw = _read_json(self.paths["status"])
        if not raw:
            return None
        try:
            return MountStatus.from_dict(raw)
        except Exception:  # noqa: BLE001
            return None

    def heartbeat(self) -> MountHeartbeat:
        """Return the latest child heartbeat; refresh from disk."""

        hb = self.read_heartbeat()
        if hb is None:
            raise LinuxLifecycleError(
                "heartbeat not available",
                code=LifecycleErrorCode.NOT_RUNNING,
                detail={"path": str(self.paths["heartbeat"])},
            )
        # Bindings required by acceptance: PID/mount/state/WAL/cache.
        if not hb.pid or not hb.mountpoint or not hb.state_directory:
            raise LifecycleProtocolError(
                "heartbeat missing pid/mount/state bindings",
                detail=hb.to_record(),
            )
        if "generation" not in (hb.to_record().get("wal") or {}):
            raise LifecycleProtocolError(
                "heartbeat missing WAL binding",
                detail=hb.to_record(),
            )
        if "generation" not in (hb.to_record().get("cache") or {}):
            raise LifecycleProtocolError(
                "heartbeat missing cache binding",
                detail=hb.to_record(),
            )
        self.trace.record(
            LifecycleTraceKind.HEARTBEAT,
            success=True,
            phase=LifecyclePhase.HEARTBEAT.value,
            detail={"sequence": hb.sequence, "pid": hb.pid},
        )
        return hb

    def status(self) -> MountStatus:
        """Return the latest child status with required bindings."""

        st = self.read_status()
        if st is None:
            raise LinuxLifecycleError(
                "status not available",
                code=LifecycleErrorCode.NOT_RUNNING,
                detail={"path": str(self.paths["status"])},
            )
        if not st.pid or not st.mountpoint or not st.state_directory:
            raise LifecycleProtocolError(
                "status missing pid/mount/state bindings",
                detail=st.to_record(),
            )
        if not isinstance(st.wal, Mapping) or "generation" not in st.wal:
            raise LifecycleProtocolError(
                "status missing WAL binding",
                detail=st.to_record(),
            )
        if not isinstance(st.cache, Mapping) or "generation" not in st.cache:
            raise LifecycleProtocolError(
                "status missing cache binding",
                detail=st.to_record(),
            )
        self.trace.record(
            LifecycleTraceKind.STATUS,
            success=True,
            phase=LifecyclePhase.STATUS.value,
            detail={"ready": st.ready, "pid": st.pid},
        )
        return st

    # -- signal / unmount ---------------------------------------------------

    def signal_child(self, sig: signal.Signals | int = signal.SIGTERM) -> bool:
        """Deliver a signal to the child process (non-blocking)."""

        proc = self._proc
        if proc is None or proc.poll() is not None:
            return False
        signum = int(sig)
        try:
            os.kill(proc.pid, signum)
        except ProcessLookupError:
            return False
        except OSError as exc:
            raise LinuxLifecycleError(
                f"failed to signal child: {exc}",
                code=LifecycleErrorCode.SIGNAL,
                detail={"pid": proc.pid, "signal": signum},
            ) from exc
        try:
            name = signal.Signals(signum).name
        except (ValueError, AttributeError):
            name = str(signum)
        self.trace.record(
            LifecycleTraceKind.SIGNAL,
            success=True,
            phase=LifecyclePhase.SIGNAL.value,
            detail={"signal": name, "pid": proc.pid},
        )
        return True

    def unmount(
        self,
        *,
        timeout_seconds: float | None = None,
        sig: signal.Signals | int = signal.SIGTERM,
    ) -> UnmountReceipt:
        """Bounded unmount: signal/request stop, wait, preserve recovery.

        Repeated calls are idempotent and never block indefinitely.
        """

        started = _monotonic()
        timeout = (
            self.config.unmount_timeout_seconds
            if timeout_seconds is None
            else _positive_float(timeout_seconds, "timeout_seconds")
        )

        with self._lock:
            if self._stopped and self._last_unmount is not None:
                # Idempotent repeated unmount.
                prior = self._last_unmount
                receipt = UnmountReceipt(
                    mount_id=prior.mount_id,
                    disposition=LifecycleDisposition.IDEMPOTENT,
                    success=True,
                    pid=prior.pid,
                    callbacks_drained=prior.callbacks_drained,
                    workers_stopped=prior.workers_stopped,
                    lease_released=prior.lease_released,
                    mount_released=prior.mount_released,
                    recovery_preserved=prior.recovery_preserved,
                    lifecycle_state=prior.lifecycle_state,
                    signal_name=prior.signal_name,
                    idempotent=True,
                    elapsed_seconds=_monotonic() - started,
                    exit_code=0,
                    detail={"repeated": True},
                )
                self.trace.record(
                    LifecycleTraceKind.UNMOUNT,
                    success=True,
                    phase=LifecyclePhase.UNMOUNT.value,
                    detail={"idempotent": True},
                )
                return receipt

        proc = self._proc
        pid = int(proc.pid) if proc is not None and proc.pid else 0

        if proc is None or (proc.poll() is not None and not self.paths["shutdown"].exists()):
            # Nothing running — still report a successful idempotent unmount.
            receipt = UnmountReceipt(
                mount_id=self.config.mount_id,
                disposition=LifecycleDisposition.IDEMPOTENT,
                success=True,
                pid=pid,
                callbacks_drained=0,
                workers_stopped=0,
                lease_released=True,
                mount_released=True,
                recovery_preserved=self._recovery_state_present(),
                lifecycle_state=MountLifecycleState.DESTROYED.value,
                signal_name="",
                idempotent=True,
                elapsed_seconds=_monotonic() - started,
                exit_code=0,
                detail={"not_running": True},
            )
            with self._lock:
                self._stopped = True
                self._last_unmount = receipt
                self._lifecycle_state = MountLifecycleState.DESTROYED
            return receipt

        # Request cooperative unmount first (file + signal).
        try:
            _atomic_write_json(
                self.paths["unmount_request"],
                {
                    "unix_ms": _unix_ms(),
                    "signal": int(sig),
                    "mount_id": self.config.mount_id,
                },
            )
        except Exception:  # noqa: BLE001
            pass

        try:
            name = signal.Signals(int(sig)).name
        except (ValueError, AttributeError):
            name = str(int(sig))

        if proc.poll() is None:
            self.signal_child(sig)

        # Wait for child exit within bound.
        deadline = started + timeout
        while proc.poll() is None and _monotonic() < deadline:
            time.sleep(0.01)

        if proc.poll() is None:
            # Escalate: SIGKILL after bound (still finite).
            try:
                os.kill(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, OSError):
                pass
            try:
                proc.wait(timeout=min(1.0, max(0.1, timeout)))
            except Exception:  # noqa: BLE001
                pass

        # Collect child shutdown receipt if present.
        shutdown_raw = _read_json(self.paths["shutdown"])
        callbacks_drained = int(shutdown_raw.get("callbacks_drained") or 0)
        workers_stopped = int(shutdown_raw.get("workers_stopped") or 0)
        lease_released = bool(shutdown_raw.get("lease_released", True))
        mount_released = bool(shutdown_raw.get("mount_released", True))
        recovery_preserved = bool(
            shutdown_raw.get("recovery_preserved", self._recovery_state_present())
        )
        # Always verify recovery state still exists (never auto-deleted).
        recovery_preserved = recovery_preserved and self._recovery_state_present()

        exit_code = int(proc.returncode if proc.returncode is not None else 0)
        receipt = UnmountReceipt(
            mount_id=self.config.mount_id,
            disposition=LifecycleDisposition.STOPPED,
            success=True,
            pid=pid,
            callbacks_drained=callbacks_drained,
            workers_stopped=workers_stopped,
            lease_released=lease_released,
            mount_released=mount_released,
            recovery_preserved=recovery_preserved,
            lifecycle_state=MountLifecycleState.DESTROYED.value,
            signal_name=name,
            idempotent=False,
            elapsed_seconds=_monotonic() - started,
            exit_code=exit_code,
            detail={
                "shutdown": shutdown_raw,
                "ready_removed": not self.paths["ready"].exists(),
            },
        )
        with self._lock:
            self._stopped = True
            self._last_unmount = receipt
            self._lifecycle_state = MountLifecycleState.DESTROYED
            self._readiness = None
        self.trace.record(
            LifecycleTraceKind.UNMOUNT,
            success=True,
            phase=LifecyclePhase.UNMOUNT.value,
            detail=receipt.to_record(),
        )
        return receipt

    def stop(self, **kwargs: Any) -> UnmountReceipt:
        """Alias for :meth:`unmount`."""

        return self.unmount(**kwargs)

    def _terminate_child(self, *, reason: str) -> None:
        proc = self._proc
        if proc is None:
            return
        if proc.poll() is None:
            try:
                os.kill(proc.pid, signal.SIGTERM)
            except (ProcessLookupError, OSError):
                pass
            deadline = _monotonic() + min(2.0, self.config.unmount_timeout_seconds)
            while proc.poll() is None and _monotonic() < deadline:
                time.sleep(0.01)
            if proc.poll() is None:
                try:
                    os.kill(proc.pid, signal.SIGKILL)
                except (ProcessLookupError, OSError):
                    pass
                try:
                    proc.wait(timeout=1.0)
                except Exception:  # noqa: BLE001
                    pass
        with self._lock:
            self._stopped = True
            self._lifecycle_state = MountLifecycleState.FAILED
        self.trace.record(
            LifecycleTraceKind.SIGNAL,
            success=True,
            phase=LifecyclePhase.FAILED.value,
            detail={"reason": reason, "pid": proc.pid},
        )

    def _recovery_state_present(self) -> bool:
        recovery = self.state_directory / RECOVERY_DIRNAME
        preserved = self.state_directory / "recovery-preserved"
        # Recovery state is preserved if either the recovery tree or an explicit
        # preserve receipt exists (child writes both).
        return recovery.exists() or preserved.exists()

    # -- stale mount reporting (non-blocking) -------------------------------

    def report_stale_mounts(
        self,
        *,
        search_roots: Sequence[str | Path] | None = None,
        stale_heartbeat_seconds: float | None = None,
    ) -> StaleMountReport:
        """Scan for stale mount state directories without blocking on leases.

        A mount is *stale* when a readiness or heartbeat file references a
        dead PID, or the heartbeat is older than the stale threshold while the
        process is gone.  This method never waits on flock/lease acquisition.
        """

        started = _monotonic()
        threshold = (
            self.config.stale_heartbeat_seconds
            if stale_heartbeat_seconds is None
            else _positive_float(stale_heartbeat_seconds, "stale_heartbeat_seconds")
        )
        roots: list[Path]
        if search_roots is None:
            roots = [self.state_directory]
        else:
            roots = [Path(r) for r in search_roots]

        stale: list[dict[str, Any]] = []
        live: list[dict[str, Any]] = []
        scanned = 0

        candidates: list[Path] = []
        seen: set[str] = set()

        def _maybe_add(path: Path) -> None:
            key = str(path)
            if key in seen:
                return
            if (path / READY_FILENAME).exists() or (path / HEARTBEAT_FILENAME).exists():
                seen.add(key)
                candidates.append(path)

        for root in roots:
            root = Path(root)
            if not root.exists():
                continue
            # Direct state directory.
            if root.is_dir():
                _maybe_add(root)
            # Bounded non-blocking walk (depth <= 2) — never follows mounts deeply.
            try:
                for child in root.iterdir():
                    if not child.is_dir():
                        continue
                    _maybe_add(child)
                    try:
                        for grand in child.iterdir():
                            if grand.is_dir():
                                _maybe_add(grand)
                    except OSError:
                        continue
            except OSError:
                continue

        now_ms = _unix_ms()
        for state_dir in candidates:
            scanned += 1
            ready_raw = _read_json(state_dir / READY_FILENAME)
            hb_raw = _read_json(state_dir / HEARTBEAT_FILENAME)
            status_raw = _read_json(state_dir / STATUS_FILENAME)
            pid = int(
                hb_raw.get("pid")
                or ready_raw.get("pid")
                or status_raw.get("pid")
                or 0
            )
            hb_ms = int(hb_raw.get("heartbeat_unix_ms") or 0)
            age_seconds = (now_ms - hb_ms) / 1000.0 if hb_ms else float("inf")
            alive = _pid_alive(pid) if pid else False
            item = {
                "state_directory": str(state_dir),
                "pid": pid,
                "alive": alive,
                "heartbeat_age_seconds": age_seconds if hb_ms else None,
                "mount_id": str(
                    hb_raw.get("mount_id")
                    or ready_raw.get("mount_id")
                    or status_raw.get("mount_id")
                    or ""
                ),
                "mountpoint": str(
                    hb_raw.get("mountpoint")
                    or ready_raw.get("mountpoint")
                    or status_raw.get("mountpoint")
                    or ""
                ),
            }
            # Stale when the recorded PID is dead, or heartbeat is older than
            # the threshold *and* the process is not alive. Live processes with
            # fresh heartbeats are reported as live.
            if not alive:
                item["stale"] = True
                stale.append(item)
            elif hb_ms and age_seconds > threshold:
                item["stale"] = True
                item["reason"] = "heartbeat_expired"
                stale.append(item)
            else:
                item["stale"] = False
                live.append(item)

        report = StaleMountReport(
            scanned=scanned,
            stale=tuple(stale),
            live=tuple(live),
            blocked=False,  # never blocks
            report_unix_ms=_unix_ms(),
        )
        # Optional durable report for operators (best-effort, non-blocking).
        try:
            _atomic_write_json(
                self.state_directory / STALE_REPORT_FILENAME, report.to_record()
            )
        except Exception:  # noqa: BLE001
            pass
        self.trace.record(
            LifecycleTraceKind.STALE,
            success=True,
            phase=LifecyclePhase.STALE_REPORT.value,
            detail={
                "scanned": scanned,
                "stale": len(stale),
                "live": len(live),
                "elapsed_seconds": _monotonic() - started,
                "blocked": False,
            },
        )
        return report

    # -- context manager ----------------------------------------------------

    def close(self) -> UnmountReceipt:
        return self.unmount()

    def __enter__(self) -> "LinuxMountLifecycle":
        self.start(wait_ready=True)
        return self

    def __exit__(self, *_: object) -> None:
        self.unmount()


# Alias used by packaging / CLI callers.
LinuxMountDaemon = LinuxMountLifecycle


def build_linux_mount_lifecycle(
    mountpoint: str | Path,
    state_directory: str | Path,
    **kwargs: Any,
) -> LinuxMountLifecycle:
    """Convenience constructor for :class:`LinuxMountLifecycle`."""

    config = LinuxMountConfig(
        mountpoint=mountpoint,
        state_directory=state_directory,
        **kwargs,
    )
    return LinuxMountLifecycle(config)


def report_stale_mounts(
    *search_roots: str | Path,
    stale_heartbeat_seconds: float = DEFAULT_STALE_HEARTBEAT_SECONDS,
) -> StaleMountReport:
    """Module-level non-blocking stale mount scan."""

    if not search_roots:
        raise LinuxLifecycleError(
            "at least one search root is required",
            code=LifecycleErrorCode.VALIDATION,
        )
    # Use a throwaway lifecycle bound to the first root for scan utilities.
    first = Path(search_roots[0])
    config = LinuxMountConfig(
        mountpoint=first / ".mnt",
        state_directory=first,
        stale_heartbeat_seconds=stale_heartbeat_seconds,
    )
    life = LinuxMountLifecycle(config)
    return life.report_stale_mounts(
        search_roots=search_roots,
        stale_heartbeat_seconds=stale_heartbeat_seconds,
    )


def lifecycle_phases() -> tuple[str, ...]:
    return tuple(p.value for p in LifecyclePhase)


def lifecycle_dispositions() -> tuple[str, ...]:
    return tuple(d.value for d in LifecycleDisposition)


def lifecycle_error_codes() -> tuple[str, ...]:
    return tuple(c.value for c in LifecycleErrorCode)


__all__ = [
    "TASK_ID",
    "CONTRACT_VERSION",
    "SCHEMA_VERSION",
    "LINUX_MOUNT_LIFECYCLE_SCHEMA",
    "LINUX_MOUNT_DAEMON_SCHEMA",
    "MOUNT_READINESS_SCHEMA",
    "MOUNT_HEARTBEAT_SCHEMA",
    "MOUNT_STATUS_SCHEMA",
    "UNMOUNT_RECEIPT_SCHEMA",
    "LinuxMountLifecycle_V1",
    "LinuxMountDaemon_V1",
    "MountReadiness_V1",
    "MountHeartbeat_V1",
    "MountStatus_V1",
    "UnmountReceipt_V1",
    "DEFAULT_MOUNT_ID",
    "DEFAULT_READINESS_TIMEOUT_SECONDS",
    "DEFAULT_HEARTBEAT_INTERVAL_SECONDS",
    "DEFAULT_UNMOUNT_TIMEOUT_SECONDS",
    "READY_FILENAME",
    "HEARTBEAT_FILENAME",
    "STATUS_FILENAME",
    "LifecyclePhase",
    "LifecycleDisposition",
    "LifecycleErrorCode",
    "LifecycleTraceKind",
    "LinuxLifecycleError",
    "ReadinessTimeoutError",
    "ChildProcessError",
    "LifecycleProtocolError",
    "MountReadiness",
    "MountHeartbeat",
    "MountStatus",
    "UnmountReceipt",
    "StaleMountReport",
    "LinuxMountConfig",
    "LinuxMountLifecycle",
    "LinuxMountDaemon",
    "BoundedCallbackQueue",
    "BoundedWorker",
    "run_child_daemon",
    "build_linux_mount_lifecycle",
    "report_stale_mounts",
    "lifecycle_phases",
    "lifecycle_dispositions",
    "lifecycle_error_codes",
]
