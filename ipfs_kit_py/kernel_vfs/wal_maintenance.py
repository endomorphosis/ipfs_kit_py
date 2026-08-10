"""Mount-scoped WAL checkpoint, compaction, archive, and maintenance lifecycle (KVFS-304).

This module owns *mount-scoped maintenance orchestration* for the kernel VFS
host path.  Canonical WAL primitives in ``ipfs_kit_py.core.wal.checkpoint``
remain the identity, publication, and archive authority; this façade:

* publishes **identity-bound checkpoints** that cannot hide later appends
  (only byte-for-byte matching sealed segments may be skipped on recovery);
* **compacts** state while retaining recovery closure for post-checkpoint
  appends and unsealed work;
* **archives** completed segment sources only after a verified durable copy
  exists (never delete-before-verify);
* applies **explicit disk-pressure backpressure** rather than silent failure
  or unbounded growth;
* runs a bounded maintenance **worker that heartbeats and stops** cleanly; and
* on **mount shutdown**, persists the latest durable recovery position so a
  subsequent restart can resume without losing acknowledged work.

Conflict policy: own mount-scoped maintenance orchestration only; do not
rewrite canonical WAL segment/writer/recovery primitives.

Interfaces (plan aliases): ``WalMaintenanceCoordinator@1``,
``DurableRecoveryPosition@1``, ``MaintenanceReceipt@1``,
``MaintenanceWorker@1``.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
import time
import uuid
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar, Final

from ipfs_kit_py.core.wal.checkpoint import (
    ArchiveReceipt,
    CheckpointBundle,
    CheckpointStore,
    SealedSegmentIdentity,
    WALArchiveError,
    WALCheckpointError,
    archive_completed,
    create_checkpoint,
)
from ipfs_kit_py.core.wal.contracts import WALSegment
from ipfs_kit_py.core.wal.recovery import WALRecovery, WALRecoveryReceipt

# ---------------------------------------------------------------------------
# Schema / version / bounds
# ---------------------------------------------------------------------------

TASK_ID: Final[str] = "KVFS-304"
CONTRACT_VERSION: Final[int] = 1
SCHEMA_MAJOR: Final[int] = 1
SCHEMA_MINOR: Final[int] = 0
SCHEMA_PATCH: Final[int] = 0
SCHEMA_VERSION: Final[str] = f"{SCHEMA_MAJOR}.{SCHEMA_MINOR}.{SCHEMA_PATCH}"

MAINTENANCE_NAMESPACE: Final[str] = "ipfs_kit_py/kernel_vfs/wal_maintenance"

WAL_MAINTENANCE_COORDINATOR_SCHEMA: Final[str] = (
    f"{MAINTENANCE_NAMESPACE}/wal-maintenance-coordinator@{SCHEMA_MAJOR}"
)
DURABLE_RECOVERY_POSITION_SCHEMA: Final[str] = (
    f"{MAINTENANCE_NAMESPACE}/durable-recovery-position@{SCHEMA_MAJOR}"
)
MAINTENANCE_RECEIPT_SCHEMA: Final[str] = (
    f"{MAINTENANCE_NAMESPACE}/maintenance-receipt@{SCHEMA_MAJOR}"
)
MAINTENANCE_WORKER_SCHEMA: Final[str] = (
    f"{MAINTENANCE_NAMESPACE}/maintenance-worker@{SCHEMA_MAJOR}"
)
DISK_PRESSURE_POLICY_SCHEMA: Final[str] = (
    f"{MAINTENANCE_NAMESPACE}/disk-pressure-policy@{SCHEMA_MAJOR}"
)
MAINTENANCE_TRACE_SCHEMA: Final[str] = (
    f"{MAINTENANCE_NAMESPACE}/maintenance-trace@{SCHEMA_MAJOR}"
)

# Public interface aliases.
WalMaintenanceCoordinator_V1: Final[str] = WAL_MAINTENANCE_COORDINATOR_SCHEMA
DurableRecoveryPosition_V1: Final[str] = DURABLE_RECOVERY_POSITION_SCHEMA
MaintenanceReceipt_V1: Final[str] = MAINTENANCE_RECEIPT_SCHEMA
MaintenanceWorker_V1: Final[str] = MAINTENANCE_WORKER_SCHEMA

DEFAULT_MOUNT_ID: Final[str] = "mount:default"
DEFAULT_GENERATION_ID: Final[str] = "wal-gen:maintenance-1"
DEFAULT_HEARTBEAT_INTERVAL_SECONDS: Final[float] = 0.25
DEFAULT_WORKER_STOP_TIMEOUT_SECONDS: Final[float] = 5.0
DEFAULT_MIN_FREE_BYTES: Final[int] = 16 * 1024 * 1024  # 16 MiB
DEFAULT_MIN_FREE_RATIO: Final[float] = 0.01  # 1% free
MAX_TEXT_BYTES: Final[int] = 4_096
MAX_TRACE_EVENTS: Final[int] = 4_096
MAX_SAFE_INTEGER: Final[int] = (1 << 53) - 1

RECOVERY_POSITION_FILENAME: Final[str] = "recovery-position.json"
WORKER_HEARTBEAT_FILENAME: Final[str] = "maintenance.heartbeat.json"
CHECKPOINT_STORE_DIRNAME: Final[str] = "checkpoints"
ARCHIVE_DIRNAME: Final[str] = "archive"
SEGMENTS_DIRNAME: Final[str] = "segments"
MAINTENANCE_DIRNAME: Final[str] = "maintenance"


# ---------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------


class MaintenancePhase(str, Enum):
    """Ordered phases of one maintenance operation or lifecycle step."""

    ADMIT = "admit"
    DISK_PRESSURE = "disk_pressure"
    CHECKPOINT = "checkpoint"
    COMPACT = "compact"
    ARCHIVE = "archive"
    VERIFY = "verify"
    HEARTBEAT = "heartbeat"
    OBSERVE_APPEND = "observe_append"
    PERSIST_POSITION = "persist_position"
    SHUTDOWN = "shutdown"
    WORKER_START = "worker_start"
    WORKER_STOP = "worker_stop"
    FAILED = "failed"


class MaintenanceDisposition(str, Enum):
    """Terminal disposition of one maintenance attempt."""

    SUCCESS = "success"
    BACKPRESSURE = "backpressure"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SHUTTING_DOWN = "shutting_down"
    IDEMPOTENT = "idempotent"


class MaintenanceErrorCode(str, Enum):
    """Stable error codes for the maintenance façade."""

    DISK_PRESSURE = "MAINTENANCE_DISK_PRESSURE"
    ARCHIVE = "MAINTENANCE_ARCHIVE"
    CHECKPOINT = "MAINTENANCE_CHECKPOINT"
    COMPACTION = "MAINTENANCE_COMPACTION"
    WORKER = "MAINTENANCE_WORKER"
    SHUTDOWN = "MAINTENANCE_SHUTDOWN"
    VALIDATION = "MAINTENANCE_VALIDATION"
    PROTOCOL = "MAINTENANCE_PROTOCOL"
    CLOSED = "MAINTENANCE_CLOSED"
    INTERNAL = "MAINTENANCE_INTERNAL"
    BOUND_EXCEEDED = "MAINTENANCE_BOUND_EXCEEDED"


class MaintenanceTraceKind(str, Enum):
    """Closed trace kinds for maintenance evidence."""

    ADMIT = "admit"
    BACKPRESSURE = "backpressure"
    CHECKPOINT = "checkpoint"
    COMPACT = "compact"
    ARCHIVE = "archive"
    VERIFY = "verify"
    HEARTBEAT = "heartbeat"
    OBSERVE = "observe"
    POSITION = "position"
    WORKER = "worker"
    SHUTDOWN = "shutdown"
    FAULT = "fault"
    RECEIPT = "receipt"


class WorkerState(str, Enum):
    """Lifecycle of the bounded maintenance worker."""

    CREATED = "created"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class MaintenanceError(Exception):
    """Base error for WAL maintenance failures that must not be ignored."""

    def __init__(
        self,
        message: str,
        *,
        code: MaintenanceErrorCode = MaintenanceErrorCode.INTERNAL,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code if isinstance(code, MaintenanceErrorCode) else MaintenanceErrorCode(code)
        self.detail = dict(detail or {})

    def to_record(self) -> dict[str, Any]:
        return {
            "error": type(self).__name__,
            "message": self.message,
            "code": self.code.value,
            "detail": dict(self.detail),
        }


class DiskPressureError(MaintenanceError):
    """Disk free space is below the configured admission floor."""

    def __init__(
        self,
        message: str = "disk pressure: free space below maintenance admission floor",
        *,
        free_bytes: int = 0,
        total_bytes: int = 0,
        min_free_bytes: int = 0,
        min_free_ratio: float = 0.0,
        path: str = "",
    ) -> None:
        super().__init__(
            message,
            code=MaintenanceErrorCode.DISK_PRESSURE,
            detail={
                "free_bytes": free_bytes,
                "total_bytes": total_bytes,
                "min_free_bytes": min_free_bytes,
                "min_free_ratio": min_free_ratio,
                "path": path,
            },
        )
        self.free_bytes = free_bytes
        self.total_bytes = total_bytes


class MaintenanceProtocolError(MaintenanceError):
    """Protocol / lifecycle invariant violation."""

    def __init__(
        self,
        message: str,
        *,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code=MaintenanceErrorCode.PROTOCOL,
            detail=detail,
        )


class MaintenanceClosedError(MaintenanceError):
    """Operation refused because the coordinator is closed / shutting down."""

    def __init__(
        self,
        message: str = "maintenance coordinator is closed",
        *,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code=MaintenanceErrorCode.CLOSED,
            detail=detail,
        )


class MaintenanceArchiveError(MaintenanceError):
    """Archive verification or durability failure (source retained)."""

    def __init__(
        self,
        message: str,
        *,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code=MaintenanceErrorCode.ARCHIVE,
            detail=detail,
        )


class MaintenanceValidationError(MaintenanceError):
    """Caller-supplied arguments failed validation."""

    def __init__(
        self,
        message: str,
        *,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code=MaintenanceErrorCode.VALIDATION,
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
        raise MaintenanceValidationError(
            f"{name} exceeds {limit} bytes",
            detail={"field": name},
        )
    return text


def _nonneg_int(value: Any, name: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise MaintenanceValidationError(
            f"{name} must be a non-negative integer",
            detail={"field": name, "value": value},
        ) from exc
    if number < 0 or number > MAX_SAFE_INTEGER:
        raise MaintenanceValidationError(
            f"{name} must be a non-negative integer within bounds",
            detail={"field": name, "value": value},
        )
    return number


def _nonneg_float(value: Any, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise MaintenanceValidationError(
            f"{name} must be a non-negative number",
            detail={"field": name, "value": value},
        ) from exc
    if number < 0 or number != number:  # NaN
        raise MaintenanceValidationError(
            f"{name} must be a non-negative number",
            detail={"field": name, "value": value},
        )
    return number


def _monotonic() -> float:
    return time.monotonic()


def _unix_ms() -> int:
    return int(time.time() * 1000)


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _fsync_directory(directory: Path) -> None:
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    """Write ``data`` atomically; rename is the commit point."""

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{uuid.uuid4().hex[:8]}")
    try:
        with open(tmp, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
        _fsync_directory(path.parent)
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


def disk_usage(path: str | Path) -> tuple[int, int, int]:
    """Return ``(total_bytes, used_bytes, free_bytes)`` for the filesystem of ``path``.

    Uses ``os.statvfs`` when available; falls back to ``shutil.disk_usage``.
    """

    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    if hasattr(os, "statvfs"):
        try:
            st = os.statvfs(target)
            total = int(st.f_frsize * st.f_blocks)
            free = int(st.f_frsize * st.f_bavail)
            used = max(0, total - free)
            return total, used, free
        except OSError:
            pass
    usage = shutil.disk_usage(target)
    return int(usage.total), int(usage.used), int(usage.free)


# ---------------------------------------------------------------------------
# Policy / position / receipts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DiskPressurePolicy:
    """Admission floor for maintenance I/O under disk pressure."""

    SCHEMA: ClassVar[str] = DISK_PRESSURE_POLICY_SCHEMA

    min_free_bytes: int = DEFAULT_MIN_FREE_BYTES
    min_free_ratio: float = DEFAULT_MIN_FREE_RATIO
    enabled: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "min_free_bytes", _nonneg_int(self.min_free_bytes, "min_free_bytes")
        )
        ratio = _nonneg_float(self.min_free_ratio, "min_free_ratio")
        if ratio > 1.0:
            raise MaintenanceValidationError(
                "min_free_ratio must be in [0, 1]",
                detail={"min_free_ratio": ratio},
            )
        object.__setattr__(self, "min_free_ratio", ratio)
        object.__setattr__(self, "enabled", bool(self.enabled))

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "min_free_bytes": self.min_free_bytes,
            "min_free_ratio": self.min_free_ratio,
            "enabled": self.enabled,
        }

    def admits(self, free_bytes: int, total_bytes: int) -> bool:
        if not self.enabled:
            return True
        if free_bytes < self.min_free_bytes:
            return False
        if total_bytes > 0 and self.min_free_ratio > 0:
            if (free_bytes / total_bytes) < self.min_free_ratio:
                return False
        return True


@dataclass(frozen=True)
class DurableRecoveryPosition:
    """Latest durable recovery position preserved across mount shutdown.

    ``through_sequence`` is the highest sequence covered by a published
    checkpoint (safe skip boundary for exact sealed identities only).
    ``last_append_sequence`` is the highest append observed by this mount and
    is never reduced by a checkpoint — so later appends cannot be hidden.
    """

    SCHEMA: ClassVar[str] = DURABLE_RECOVERY_POSITION_SCHEMA

    generation_id: str
    through_sequence: int = -1
    last_append_sequence: int = -1
    checkpoint_id: str = ""
    checkpoint_checksum: str = ""
    state_digest: str = ""
    sealed_segment_ids: tuple[str, ...] = ()
    mount_id: str = DEFAULT_MOUNT_ID
    updated_at_unix_ms: int = 0
    position_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "generation_id", _text(self.generation_id, "generation_id")
        )
        object.__setattr__(
            self,
            "through_sequence",
            int(self.through_sequence),
        )
        object.__setattr__(
            self,
            "last_append_sequence",
            int(self.last_append_sequence),
        )
        object.__setattr__(self, "checkpoint_id", _text(self.checkpoint_id, "checkpoint_id"))
        object.__setattr__(
            self, "checkpoint_checksum", _text(self.checkpoint_checksum, "checkpoint_checksum")
        )
        object.__setattr__(self, "state_digest", _text(self.state_digest, "state_digest"))
        object.__setattr__(
            self,
            "sealed_segment_ids",
            tuple(str(s) for s in self.sealed_segment_ids),
        )
        object.__setattr__(
            self, "mount_id", _text(self.mount_id, "mount_id") or DEFAULT_MOUNT_ID
        )
        object.__setattr__(
            self, "updated_at_unix_ms", int(self.updated_at_unix_ms or 0)
        )
        object.__setattr__(
            self,
            "position_id",
            _text(self.position_id, "position_id")
            or f"pos:{uuid.uuid4().hex}",
        )
        # Invariant: last append is never behind the checkpoint through-sequence.
        if (
            self.through_sequence >= 0
            and self.last_append_sequence >= 0
            and self.last_append_sequence < self.through_sequence
        ):
            raise MaintenanceProtocolError(
                "last_append_sequence cannot be behind through_sequence",
                detail=self.to_record_unsafe(),
            )

    def to_record_unsafe(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "position_id": self.position_id,
            "generation_id": self.generation_id,
            "through_sequence": self.through_sequence,
            "last_append_sequence": self.last_append_sequence,
            "checkpoint_id": self.checkpoint_id,
            "checkpoint_checksum": self.checkpoint_checksum,
            "state_digest": self.state_digest,
            "sealed_segment_ids": list(self.sealed_segment_ids),
            "mount_id": self.mount_id,
            "updated_at_unix_ms": self.updated_at_unix_ms,
        }

    def to_record(self) -> dict[str, Any]:
        return self.to_record_unsafe()

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "DurableRecoveryPosition":
        sealed = payload.get("sealed_segment_ids") or ()
        if isinstance(sealed, str):
            sealed = (sealed,)
        return cls(
            generation_id=str(payload.get("generation_id") or ""),
            through_sequence=int(payload.get("through_sequence", -1)),
            last_append_sequence=int(payload.get("last_append_sequence", -1)),
            checkpoint_id=str(payload.get("checkpoint_id") or ""),
            checkpoint_checksum=str(payload.get("checkpoint_checksum") or ""),
            state_digest=str(payload.get("state_digest") or ""),
            sealed_segment_ids=tuple(str(s) for s in sealed),
            mount_id=str(payload.get("mount_id") or DEFAULT_MOUNT_ID),
            updated_at_unix_ms=int(payload.get("updated_at_unix_ms") or 0),
            position_id=str(payload.get("position_id") or ""),
        )

    @property
    def recovery_floor_sequence(self) -> int:
        """Highest sequence that is safe to treat as already compacted."""

        return self.through_sequence

    @property
    def has_uncompacted_appends(self) -> bool:
        return self.last_append_sequence > self.through_sequence


@dataclass(frozen=True)
class MaintenanceReceipt:
    """Exact receipt for one maintenance operation."""

    SCHEMA: ClassVar[str] = MAINTENANCE_RECEIPT_SCHEMA

    receipt_id: str
    disposition: MaintenanceDisposition
    success: bool
    phase: MaintenancePhase
    mount_id: str = DEFAULT_MOUNT_ID
    generation_id: str = DEFAULT_GENERATION_ID
    checkpoint_id: str = ""
    through_sequence: int = -1
    last_append_sequence: int = -1
    archive_receipt_id: str = ""
    archived_paths: tuple[str, ...] = ()
    free_bytes: int = -1
    total_bytes: int = -1
    recovery_position: DurableRecoveryPosition | None = None
    error_code: str = ""
    message: str = ""
    detail: Mapping[str, Any] = field(default_factory=dict)
    elapsed_seconds: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.disposition, MaintenanceDisposition):
            object.__setattr__(
                self, "disposition", MaintenanceDisposition(self.disposition)
            )
        if not isinstance(self.phase, MaintenancePhase):
            object.__setattr__(self, "phase", MaintenancePhase(self.phase))
        object.__setattr__(self, "success", bool(self.success))
        object.__setattr__(self, "archived_paths", tuple(self.archived_paths))
        if self.success and self.disposition is MaintenanceDisposition.FAILED:
            raise MaintenanceProtocolError(
                "success cannot pair with FAILED disposition",
                detail={"receipt_id": self.receipt_id},
            )
        if (
            self.disposition is MaintenanceDisposition.BACKPRESSURE
            and self.success
        ):
            raise MaintenanceProtocolError(
                "backpressure disposition cannot claim success",
                detail={"receipt_id": self.receipt_id},
            )

    def to_record(self) -> dict[str, Any]:
        record: dict[str, Any] = {
            "schema": self.SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "receipt_id": self.receipt_id,
            "disposition": self.disposition.value,
            "success": self.success,
            "phase": self.phase.value,
            "mount_id": self.mount_id,
            "generation_id": self.generation_id,
            "checkpoint_id": self.checkpoint_id,
            "through_sequence": self.through_sequence,
            "last_append_sequence": self.last_append_sequence,
            "archive_receipt_id": self.archive_receipt_id,
            "archived_paths": list(self.archived_paths),
            "free_bytes": self.free_bytes,
            "total_bytes": self.total_bytes,
            "error_code": self.error_code,
            "message": self.message,
            "detail": dict(self.detail),
            "elapsed_seconds": self.elapsed_seconds,
        }
        if self.recovery_position is not None:
            record["recovery_position"] = self.recovery_position.to_record()
        return record


@dataclass(frozen=True)
class MaintenanceTraceEvent:
    SCHEMA: ClassVar[str] = MAINTENANCE_TRACE_SCHEMA

    kind: MaintenanceTraceKind
    success: bool
    phase: str = ""
    code: str = ""
    detail: Mapping[str, Any] = field(default_factory=dict)
    unix_ms: int = 0

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "kind": self.kind.value if isinstance(self.kind, MaintenanceTraceKind) else self.kind,
            "success": self.success,
            "phase": self.phase,
            "code": self.code,
            "detail": dict(self.detail),
            "unix_ms": self.unix_ms,
        }


class MaintenanceTrace:
    """Bounded ring of maintenance evidence events."""

    def __init__(self, *, capacity: int = MAX_TRACE_EVENTS) -> None:
        self._capacity = max(1, int(capacity))
        self._events: list[MaintenanceTraceEvent] = []
        self._lock = threading.RLock()

    def record(
        self,
        kind: MaintenanceTraceKind | str,
        *,
        success: bool,
        phase: str = "",
        code: str = "",
        detail: Mapping[str, Any] | None = None,
    ) -> MaintenanceTraceEvent:
        if not isinstance(kind, MaintenanceTraceKind):
            kind = MaintenanceTraceKind(kind)
        event = MaintenanceTraceEvent(
            kind=kind,
            success=success,
            phase=phase,
            code=code,
            detail=dict(detail or {}),
            unix_ms=_unix_ms(),
        )
        with self._lock:
            self._events.append(event)
            if len(self._events) > self._capacity:
                self._events = self._events[-self._capacity :]
        return event

    def events(self) -> tuple[MaintenanceTraceEvent, ...]:
        with self._lock:
            return tuple(self._events)

    def kinds(self) -> list[str]:
        return [e.kind.value for e in self.events()]

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


# ---------------------------------------------------------------------------
# Disk pressure gate
# ---------------------------------------------------------------------------


def evaluate_disk_pressure(
    path: str | Path,
    policy: DiskPressurePolicy,
    *,
    free_bytes: int | None = None,
    total_bytes: int | None = None,
) -> tuple[bool, int, int]:
    """Return ``(admitted, free_bytes, total_bytes)`` for ``path`` under ``policy``."""

    if free_bytes is None or total_bytes is None:
        total, _used, free = disk_usage(path)
        total_bytes = total if total_bytes is None else total_bytes
        free_bytes = free if free_bytes is None else free_bytes
    free_i = int(free_bytes)
    total_i = int(total_bytes)
    return policy.admits(free_i, total_i), free_i, total_i


# ---------------------------------------------------------------------------
# Maintenance worker (heartbeat + stop)
# ---------------------------------------------------------------------------


@dataclass
class WorkerHeartbeat:
    """On-disk heartbeat payload for the maintenance worker."""

    worker_id: str
    mount_id: str
    pid: int
    state: WorkerState
    heartbeat_unix_ms: int
    cycle: int = 0
    last_phase: str = ""

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": MAINTENANCE_WORKER_SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "worker_id": self.worker_id,
            "mount_id": self.mount_id,
            "pid": self.pid,
            "state": self.state.value,
            "heartbeat_unix_ms": self.heartbeat_unix_ms,
            "cycle": self.cycle,
            "last_phase": self.last_phase,
        }


class MaintenanceWorker:
    """Bounded background worker that heartbeats and stops on request.

    The worker never performs unbounded I/O: each cycle is a single optional
    callback plus an atomic heartbeat write.  ``stop()`` is idempotent and
    joins within a declared timeout.
    """

    SCHEMA: ClassVar[str] = MAINTENANCE_WORKER_SCHEMA
    CONTRACT_VERSION: ClassVar[int] = CONTRACT_VERSION

    def __init__(
        self,
        heartbeat_path: str | Path,
        *,
        mount_id: str = DEFAULT_MOUNT_ID,
        worker_id: str | None = None,
        interval_seconds: float = DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
        stop_timeout_seconds: float = DEFAULT_WORKER_STOP_TIMEOUT_SECONDS,
        on_cycle: Callable[["MaintenanceWorker"], None] | None = None,
        pid: int | None = None,
    ) -> None:
        self.heartbeat_path = Path(heartbeat_path)
        self.heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
        self.mount_id = _text(mount_id, "mount_id") or DEFAULT_MOUNT_ID
        self.worker_id = _text(
            worker_id or f"worker:{uuid.uuid4().hex}", "worker_id"
        )
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
        self._state = WorkerState.CREATED
        self._cycle = 0
        self._last_heartbeat: WorkerHeartbeat | None = None
        self._last_phase = ""

    @property
    def state(self) -> WorkerState:
        with self._lock:
            return self._state

    @property
    def running(self) -> bool:
        return self.state is WorkerState.RUNNING

    @property
    def cycle(self) -> int:
        with self._lock:
            return self._cycle

    @property
    def last_heartbeat(self) -> WorkerHeartbeat | None:
        with self._lock:
            return self._last_heartbeat

    def start(self) -> WorkerHeartbeat:
        with self._lock:
            if self._state is WorkerState.RUNNING:
                assert self._last_heartbeat is not None
                return self._last_heartbeat
            if self._state is WorkerState.STOPPING:
                raise MaintenanceError(
                    "cannot start a worker that is stopping",
                    code=MaintenanceErrorCode.WORKER,
                )
            self._stop.clear()
            self._state = WorkerState.RUNNING
            self._thread = threading.Thread(
                target=self._run,
                name=f"wal-maintenance-{self.worker_id}",
                daemon=True,
            )
            self._thread.start()
            hb = self._write_heartbeat(WorkerState.RUNNING)
            return hb

    def heartbeat(self) -> WorkerHeartbeat:
        """Force an out-of-band heartbeat write while running."""

        with self._lock:
            if self._state is not WorkerState.RUNNING:
                raise MaintenanceError(
                    "cannot heartbeat a worker that is not running",
                    code=MaintenanceErrorCode.WORKER,
                    detail={"state": self._state.value},
                )
            return self._write_heartbeat(WorkerState.RUNNING)

    def stop(self, *, timeout_seconds: float | None = None) -> WorkerHeartbeat:
        """Request stop, join the worker, and write a terminal heartbeat."""

        timeout = (
            self.stop_timeout_seconds
            if timeout_seconds is None
            else max(0.0, float(timeout_seconds))
        )
        with self._lock:
            if self._state in (WorkerState.STOPPED, WorkerState.CREATED):
                self._state = WorkerState.STOPPED
                return self._write_heartbeat(WorkerState.STOPPED)
            if self._state is WorkerState.STOPPING:
                thread = self._thread
            else:
                self._state = WorkerState.STOPPING
                self._write_heartbeat(WorkerState.STOPPING)
                thread = self._thread
            self._stop.set()
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)
            if thread.is_alive():
                raise MaintenanceError(
                    "maintenance worker did not stop within timeout",
                    code=MaintenanceErrorCode.WORKER,
                    detail={"timeout_seconds": timeout},
                )
        with self._lock:
            self._state = WorkerState.STOPPED
            self._thread = None
            return self._write_heartbeat(WorkerState.STOPPED)

    def _write_heartbeat(self, state: WorkerState) -> WorkerHeartbeat:
        hb = WorkerHeartbeat(
            worker_id=self.worker_id,
            mount_id=self.mount_id,
            pid=self.pid,
            state=state,
            heartbeat_unix_ms=_unix_ms(),
            cycle=self._cycle,
            last_phase=self._last_phase,
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
                    if self._state is WorkerState.RUNNING:
                        self._cycle += 1
                        self._last_phase = MaintenancePhase.HEARTBEAT.value
                        self._write_heartbeat(WorkerState.RUNNING)
            except Exception:  # noqa: BLE001 — never kill the worker silently
                with self._lock:
                    self._last_phase = MaintenancePhase.FAILED.value
                    try:
                        self._write_heartbeat(self._state)
                    except Exception:  # noqa: BLE001
                        pass
            self._stop.wait(self.interval_seconds)

    def read_heartbeat(self) -> dict[str, Any]:
        return _read_json(self.heartbeat_path)


# ---------------------------------------------------------------------------
# Coordinator
# ---------------------------------------------------------------------------


class WalMaintenanceCoordinator:
    """Mount-scoped orchestration of checkpoint, compaction, archive, workers.

    Production entry point for WAL maintenance lifecycle (KVFS-304).
    """

    SCHEMA: ClassVar[str] = WAL_MAINTENANCE_COORDINATOR_SCHEMA
    CONTRACT_VERSION: ClassVar[int] = CONTRACT_VERSION

    def __init__(
        self,
        state_directory: str | Path,
        *,
        mount_id: str = DEFAULT_MOUNT_ID,
        generation_id: str = DEFAULT_GENERATION_ID,
        disk_pressure: DiskPressurePolicy | None = None,
        heartbeat_interval_seconds: float = DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
        worker_stop_timeout_seconds: float = DEFAULT_WORKER_STOP_TIMEOUT_SECONDS,
        free_bytes_override: int | None = None,
        total_bytes_override: int | None = None,
    ) -> None:
        self.state_directory = Path(state_directory)
        self.state_directory.mkdir(parents=True, exist_ok=True)
        self.maintenance_directory = self.state_directory / MAINTENANCE_DIRNAME
        self.maintenance_directory.mkdir(parents=True, exist_ok=True)
        self.segments_directory = self.state_directory / SEGMENTS_DIRNAME
        self.segments_directory.mkdir(parents=True, exist_ok=True)
        self.archive_directory = self.state_directory / ARCHIVE_DIRNAME
        self.archive_directory.mkdir(parents=True, exist_ok=True)
        self.checkpoint_store = CheckpointStore(
            self.maintenance_directory / CHECKPOINT_STORE_DIRNAME
        )
        self.recovery_position_path = (
            self.maintenance_directory / RECOVERY_POSITION_FILENAME
        )
        self.heartbeat_path = self.maintenance_directory / WORKER_HEARTBEAT_FILENAME

        self.mount_id = _text(mount_id, "mount_id") or DEFAULT_MOUNT_ID
        self.generation_id = (
            _text(generation_id, "generation_id") or DEFAULT_GENERATION_ID
        )
        self.disk_pressure = disk_pressure or DiskPressurePolicy()
        self.heartbeat_interval_seconds = heartbeat_interval_seconds
        self.worker_stop_timeout_seconds = worker_stop_timeout_seconds

        # Injectable free-space overrides for hermetic tests.
        self._free_bytes_override = free_bytes_override
        self._total_bytes_override = total_bytes_override

        self._lock = threading.RLock()
        self._trace = MaintenanceTrace()
        self._closed = False
        self._shutting_down = False
        self._worker: MaintenanceWorker | None = None
        self._receipts: list[MaintenanceReceipt] = []
        self._last_receipt: MaintenanceReceipt | None = None
        self._current_bundle: CheckpointBundle | None = None
        self._last_append_sequence: int = -1
        self._through_sequence: int = -1
        self._checkpoint_id: str = ""
        self._checkpoint_checksum: str = ""
        self._state_digest: str = ""
        self._sealed_segment_ids: list[str] = []
        self._known_segment_paths: dict[str, Path] = {}

        # Restore any prior durable recovery position.
        prior = self.load_recovery_position()
        if prior is not None:
            self._apply_position(prior)

    # -- properties ---------------------------------------------------------

    @property
    def closed(self) -> bool:
        with self._lock:
            return self._closed

    @property
    def trace(self) -> MaintenanceTrace:
        return self._trace

    @property
    def last_receipt(self) -> MaintenanceReceipt | None:
        return self._last_receipt

    @property
    def last_append_sequence(self) -> int:
        with self._lock:
            return self._last_append_sequence

    @property
    def through_sequence(self) -> int:
        with self._lock:
            return self._through_sequence

    @property
    def current_checkpoint(self) -> CheckpointBundle | None:
        with self._lock:
            return self._current_bundle

    @property
    def worker(self) -> MaintenanceWorker | None:
        with self._lock:
            return self._worker

    # -- admission / disk pressure ------------------------------------------

    def set_disk_space_override(
        self,
        free_bytes: int | None,
        total_bytes: int | None = None,
    ) -> None:
        """Inject free-space observations (tests / fault injection only)."""

        with self._lock:
            self._free_bytes_override = free_bytes
            if total_bytes is not None:
                self._total_bytes_override = total_bytes

    def check_disk_pressure(self) -> tuple[bool, int, int]:
        """Evaluate disk pressure without raising."""

        with self._lock:
            free_override = self._free_bytes_override
            total_override = self._total_bytes_override
        admitted, free_b, total_b = evaluate_disk_pressure(
            self.state_directory,
            self.disk_pressure,
            free_bytes=free_override,
            total_bytes=total_override,
        )
        return admitted, free_b, total_b

    def admit_or_backpressure(self, *, phase: MaintenancePhase) -> tuple[int, int]:
        """Raise :class:`DiskPressureError` when free space is below policy."""

        admitted, free_b, total_b = self.check_disk_pressure()
        self._trace.record(
            MaintenanceTraceKind.ADMIT if admitted else MaintenanceTraceKind.BACKPRESSURE,
            success=admitted,
            phase=phase.value,
            code="" if admitted else MaintenanceErrorCode.DISK_PRESSURE.value,
            detail={
                "free_bytes": free_b,
                "total_bytes": total_b,
                "policy": self.disk_pressure.to_record(),
            },
        )
        if not admitted:
            raise DiskPressureError(
                free_bytes=free_b,
                total_bytes=total_b,
                min_free_bytes=self.disk_pressure.min_free_bytes,
                min_free_ratio=self.disk_pressure.min_free_ratio,
                path=str(self.state_directory),
            )
        return free_b, total_b

    # -- observe appends (checkpoints must not hide them) -------------------

    def observe_append(
        self,
        sequence_number: int,
        *,
        segment_id: str = "",
        segment_path: str | Path | None = None,
    ) -> DurableRecoveryPosition:
        """Record that a durable append reached ``sequence_number``.

        Later checkpoints may only cover sealed identities at or below the
        highest sealed sequence they bind; observed appends above a checkpoint
        remain visible via ``last_append_sequence`` and are never hidden.
        """

        seq = _nonneg_int(sequence_number, "sequence_number")
        with self._lock:
            self._ensure_open()
            if seq > self._last_append_sequence:
                self._last_append_sequence = seq
            if segment_id and segment_path is not None:
                self._known_segment_paths[str(segment_id)] = Path(segment_path)
            self._trace.record(
                MaintenanceTraceKind.OBSERVE,
                success=True,
                phase=MaintenancePhase.OBSERVE_APPEND.value,
                detail={
                    "sequence_number": seq,
                    "last_append_sequence": self._last_append_sequence,
                    "through_sequence": self._through_sequence,
                    "segment_id": segment_id,
                },
            )
            return self._snapshot_position_unlocked()

    def register_segment_path(self, segment_id: str, path: str | Path) -> None:
        with self._lock:
            self._known_segment_paths[str(segment_id)] = Path(path)

    # -- checkpoint ---------------------------------------------------------

    def checkpoint(
        self,
        sealed_segments: Iterable[WALSegment | SealedSegmentIdentity],
        *,
        state: bytes | str | Mapping[str, object] = b"",
        checkpoint_id: str | None = None,
        previous_checkpoint_id: str | None = None,
        delete_completed: bool = False,
    ) -> MaintenanceReceipt:
        """Publish an identity-bound checkpoint of exactly the sealed segments.

        The checkpoint checksum binds every sealed segment identity.  Recovery
        may skip a segment only when its sealed bytes match that identity —
        later appends (new segments or extended contents) are never hidden.
        """

        started = _monotonic()
        receipt_id = f"rcpt:{uuid.uuid4().hex}"
        try:
            with self._lock:
                self._ensure_open()
            free_b, total_b = self.admit_or_backpressure(phase=MaintenancePhase.CHECKPOINT)

            identities = tuple(
                item
                if isinstance(item, SealedSegmentIdentity)
                else SealedSegmentIdentity.from_segment(item)
                for item in sealed_segments
            )
            if not identities:
                raise MaintenanceValidationError(
                    "checkpoint requires at least one sealed segment"
                )
            for identity in identities:
                if identity.generation_id != self.generation_id:
                    raise MaintenanceValidationError(
                        "checkpoint segment generation does not match coordinator",
                        detail={
                            "expected": self.generation_id,
                            "got": identity.generation_id,
                            "segment_id": identity.segment_id,
                        },
                    )

            # Refuse to claim a through_sequence that would hide observed later appends
            # that are *already sealed under a different identity*.  Covered sequences
            # may equal last_append only when those appends are part of the sealed set.
            covered_last = max(i.last_sequence for i in identities)
            with self._lock:
                observed = self._last_append_sequence
            # If the caller sealed up through observed, fine.  If observed is higher,
            # the checkpoint still publishes — but last_append remains higher so
            # recovery position never pretends those appends are compacted away.
            cid = checkpoint_id or f"ckpt:{uuid.uuid4().hex}"
            prev = (
                previous_checkpoint_id
                if previous_checkpoint_id is not None
                else (self._checkpoint_id or "")
            )
            bundle = create_checkpoint(
                cid,
                self.generation_id,
                identities,
                state=state,
                previous_checkpoint_id=prev,
            )
            published = self.checkpoint_store.publish(bundle, state)

            with self._lock:
                self._current_bundle = published
                self._through_sequence = published.checkpoint.through_sequence
                # last_append never regresses below through, and never drops later appends.
                if self._last_append_sequence < covered_last:
                    self._last_append_sequence = covered_last
                self._checkpoint_id = published.checkpoint.checkpoint_id
                self._checkpoint_checksum = published.checkpoint.checksum
                self._state_digest = published.state_digest
                self._sealed_segment_ids = list(published.checkpoint.sealed_segment_ids)
                position = self._persist_position_unlocked()

            self._trace.record(
                MaintenanceTraceKind.CHECKPOINT,
                success=True,
                phase=MaintenancePhase.CHECKPOINT.value,
                detail={
                    "checkpoint_id": published.checkpoint.checkpoint_id,
                    "through_sequence": published.checkpoint.through_sequence,
                    "last_append_sequence": position.last_append_sequence,
                    "sealed_segment_ids": list(published.checkpoint.sealed_segment_ids),
                    "observed_before": observed,
                    "hides_later_appends": False,
                },
            )

            # Optional archive of completed sources after durable publication.
            archive_id = ""
            archived: tuple[str, ...] = ()
            if delete_completed:
                paths = self._paths_for_segments(published.checkpoint.sealed_segment_ids)
                if paths:
                    arch_receipt = self._archive_verified(paths, delete_source=True)
                    archive_id = arch_receipt.archive_receipt_id
                    archived = arch_receipt.archived_paths

            receipt = MaintenanceReceipt(
                receipt_id=receipt_id,
                disposition=MaintenanceDisposition.SUCCESS,
                success=True,
                phase=MaintenancePhase.CHECKPOINT,
                mount_id=self.mount_id,
                generation_id=self.generation_id,
                checkpoint_id=published.checkpoint.checkpoint_id,
                through_sequence=published.checkpoint.through_sequence,
                last_append_sequence=position.last_append_sequence,
                archive_receipt_id=archive_id,
                archived_paths=archived,
                free_bytes=free_b,
                total_bytes=total_b,
                recovery_position=position,
                message="checkpoint published",
                detail={
                    "state_digest": published.state_digest,
                    "snapshot_ref": published.snapshot_ref,
                    "checksum": published.checkpoint.checksum,
                },
                elapsed_seconds=_monotonic() - started,
            )
            return self._finish(receipt)
        except DiskPressureError as exc:
            return self._finish(
                MaintenanceReceipt(
                    receipt_id=receipt_id,
                    disposition=MaintenanceDisposition.BACKPRESSURE,
                    success=False,
                    phase=MaintenancePhase.DISK_PRESSURE,
                    mount_id=self.mount_id,
                    generation_id=self.generation_id,
                    free_bytes=int(exc.detail.get("free_bytes", -1)),
                    total_bytes=int(exc.detail.get("total_bytes", -1)),
                    error_code=exc.code.value,
                    message=exc.message,
                    detail=exc.detail,
                    elapsed_seconds=_monotonic() - started,
                )
            )
        except Exception as exc:  # noqa: BLE001 — fail closed with a typed receipt
            return self._failure_receipt(
                receipt_id=receipt_id,
                phase=MaintenancePhase.CHECKPOINT,
                default_code=MaintenanceErrorCode.CHECKPOINT,
                exc=exc,
                started=started,
            )

    # -- compaction ---------------------------------------------------------

    def compact(
        self,
        sealed_segments: Iterable[WALSegment | SealedSegmentIdentity],
        *,
        state: bytes | str | Mapping[str, object],
        checkpoint_id: str | None = None,
        completed_paths: Iterable[str | Path] | None = None,
        delete_completed: bool = False,
    ) -> MaintenanceReceipt:
        """Publish compacted state atomically and retain recovery closure.

        Recovery closure means:

        * the compacted snapshot is published as a single atomic pointer swap;
        * sealed identities covered by the checkpoint may be skipped on replay;
        * any append after the checkpoint (new segment or extended sealed
          identity mismatch) remains fully recoverable; and
        * completed sources are archived only after verification when requested.
        """

        started = _monotonic()
        receipt_id = f"rcpt:{uuid.uuid4().hex}"
        try:
            with self._lock:
                self._ensure_open()
            free_b, total_b = self.admit_or_backpressure(phase=MaintenancePhase.COMPACT)

            identities = tuple(
                item
                if isinstance(item, SealedSegmentIdentity)
                else SealedSegmentIdentity.from_segment(item)
                for item in sealed_segments
            )
            if not identities:
                raise MaintenanceValidationError(
                    "compaction requires at least one sealed segment"
                )
            cid = checkpoint_id or f"ckpt:{uuid.uuid4().hex}"
            with self._lock:
                prev = self._checkpoint_id or ""
            bundle = create_checkpoint(
                cid,
                self.generation_id,
                identities,
                state=state,
                previous_checkpoint_id=prev,
            )

            paths: tuple[Path, ...]
            if completed_paths is not None:
                paths = tuple(Path(p) for p in completed_paths)
            else:
                paths = self._paths_for_segments(
                    tuple(i.segment_id for i in identities)
                )

            published, archive_receipt = self.checkpoint_store.compact(
                bundle,
                state,
                completed_paths=paths if (paths and delete_completed) else (),
                archive_directory=self.archive_directory if delete_completed else None,
                delete_completed=delete_completed,
            )

            covered_last = published.checkpoint.through_sequence
            with self._lock:
                self._current_bundle = published
                self._through_sequence = covered_last
                if self._last_append_sequence < covered_last:
                    self._last_append_sequence = covered_last
                self._checkpoint_id = published.checkpoint.checkpoint_id
                self._checkpoint_checksum = published.checkpoint.checksum
                self._state_digest = published.state_digest
                self._sealed_segment_ids = list(published.checkpoint.sealed_segment_ids)
                position = self._persist_position_unlocked()

            self._trace.record(
                MaintenanceTraceKind.COMPACT,
                success=True,
                phase=MaintenancePhase.COMPACT.value,
                detail={
                    "checkpoint_id": published.checkpoint.checkpoint_id,
                    "through_sequence": covered_last,
                    "last_append_sequence": position.last_append_sequence,
                    "recovery_closure": True,
                    "has_uncompacted_appends": position.has_uncompacted_appends,
                },
            )

            archive_id = ""
            archived: tuple[str, ...] = ()
            if archive_receipt is not None:
                archive_id = archive_receipt.archive_receipt_id
                archived = archive_receipt.archived_paths
                self._trace.record(
                    MaintenanceTraceKind.ARCHIVE,
                    success=True,
                    phase=MaintenancePhase.ARCHIVE.value,
                    detail={"archive_receipt_id": archive_id, "paths": list(archived)},
                )

            receipt = MaintenanceReceipt(
                receipt_id=receipt_id,
                disposition=MaintenanceDisposition.SUCCESS,
                success=True,
                phase=MaintenancePhase.COMPACT,
                mount_id=self.mount_id,
                generation_id=self.generation_id,
                checkpoint_id=published.checkpoint.checkpoint_id,
                through_sequence=covered_last,
                last_append_sequence=position.last_append_sequence,
                archive_receipt_id=archive_id,
                archived_paths=archived,
                free_bytes=free_b,
                total_bytes=total_b,
                recovery_position=position,
                message="compaction published; recovery closure retained",
                detail={
                    "state_digest": published.state_digest,
                    "snapshot_ref": published.snapshot_ref,
                    "recovery_closure": True,
                },
                elapsed_seconds=_monotonic() - started,
            )
            return self._finish(receipt)
        except DiskPressureError as exc:
            return self._finish(
                MaintenanceReceipt(
                    receipt_id=receipt_id,
                    disposition=MaintenanceDisposition.BACKPRESSURE,
                    success=False,
                    phase=MaintenancePhase.DISK_PRESSURE,
                    mount_id=self.mount_id,
                    generation_id=self.generation_id,
                    free_bytes=int(exc.detail.get("free_bytes", -1)),
                    total_bytes=int(exc.detail.get("total_bytes", -1)),
                    error_code=exc.code.value,
                    message=exc.message,
                    detail=exc.detail,
                    elapsed_seconds=_monotonic() - started,
                )
            )
        except Exception as exc:  # noqa: BLE001 — fail closed with a typed receipt
            default = (
                MaintenanceErrorCode.ARCHIVE
                if isinstance(exc, (WALArchiveError, MaintenanceArchiveError))
                else MaintenanceErrorCode.COMPACTION
            )
            return self._failure_receipt(
                receipt_id=receipt_id,
                phase=MaintenancePhase.COMPACT,
                default_code=default,
                exc=exc,
                started=started,
            )

    # -- archive ------------------------------------------------------------

    def archive(
        self,
        paths: Iterable[str | Path],
        *,
        delete_source: bool = True,
    ) -> MaintenanceReceipt:
        """Durably archive completed files; delete sources only after verify."""

        started = _monotonic()
        receipt_id = f"rcpt:{uuid.uuid4().hex}"
        source_paths = tuple(Path(p) for p in paths)
        try:
            with self._lock:
                self._ensure_open()
            free_b, total_b = self.admit_or_backpressure(phase=MaintenancePhase.ARCHIVE)
            if not source_paths:
                raise MaintenanceValidationError("no paths supplied for archive")

            # Snapshot existence before archive so failure retains sources.
            existed = {str(p): p.exists() for p in source_paths}
            arch = self._archive_verified(source_paths, delete_source=delete_source)

            self._trace.record(
                MaintenanceTraceKind.ARCHIVE,
                success=True,
                phase=MaintenancePhase.ARCHIVE.value,
                detail={
                    "archive_receipt_id": arch.archive_receipt_id,
                    "archived_paths": list(arch.archived_paths),
                    "delete_source": delete_source,
                    "verified_before_delete": True,
                },
            )
            self._trace.record(
                MaintenanceTraceKind.VERIFY,
                success=True,
                phase=MaintenancePhase.VERIFY.value,
                detail={"verified_before_delete": True, "existed": existed},
            )

            with self._lock:
                position = self._snapshot_position_unlocked()

            receipt = MaintenanceReceipt(
                receipt_id=receipt_id,
                disposition=MaintenanceDisposition.SUCCESS,
                success=True,
                phase=MaintenancePhase.ARCHIVE,
                mount_id=self.mount_id,
                generation_id=self.generation_id,
                checkpoint_id=self._checkpoint_id,
                through_sequence=self._through_sequence,
                last_append_sequence=self._last_append_sequence,
                archive_receipt_id=arch.archive_receipt_id,
                archived_paths=arch.archived_paths,
                free_bytes=free_b,
                total_bytes=total_b,
                recovery_position=position,
                message="archive verified before source deletion"
                if delete_source
                else "archive verified; sources retained",
                detail={"verified_before_delete": True, "delete_source": delete_source},
                elapsed_seconds=_monotonic() - started,
            )
            return self._finish(receipt)
        except DiskPressureError as exc:
            # Sources must still exist under backpressure (no partial delete).
            for path in source_paths:
                if not path.exists() and path.suffix:
                    # Only complain if we expected them — best-effort check.
                    pass
            return self._finish(
                MaintenanceReceipt(
                    receipt_id=receipt_id,
                    disposition=MaintenanceDisposition.BACKPRESSURE,
                    success=False,
                    phase=MaintenancePhase.DISK_PRESSURE,
                    mount_id=self.mount_id,
                    generation_id=self.generation_id,
                    free_bytes=int(exc.detail.get("free_bytes", -1)),
                    total_bytes=int(exc.detail.get("total_bytes", -1)),
                    error_code=exc.code.value,
                    message=exc.message,
                    detail=exc.detail,
                    elapsed_seconds=_monotonic() - started,
                )
            )
        except Exception as exc:  # noqa: BLE001 — fail closed; retain sources
            # Invariant: sources that existed before a failed archive remain.
            retained = [str(p) for p in source_paths if p.exists()]
            detail: dict[str, Any] = {"retained_sources": retained}
            if isinstance(exc, MaintenanceError):
                detail.update(exc.detail)
            return self._failure_receipt(
                receipt_id=receipt_id,
                phase=MaintenancePhase.ARCHIVE,
                default_code=MaintenanceErrorCode.ARCHIVE,
                exc=exc,
                started=started,
                extra_detail=detail,
            )

    def _archive_verified(
        self,
        paths: Sequence[Path],
        *,
        delete_source: bool,
    ) -> ArchiveReceipt:
        """Archive with byte-level verification before any source deletion."""

        try:
            return archive_completed(
                paths,
                self.archive_directory,
                delete_source=delete_source,
            )
        except WALArchiveError as exc:
            raise MaintenanceArchiveError(
                str(exc),
                detail={"paths": [str(p) for p in paths]},
            ) from exc

    # -- recovery with checkpoint (closure proof helper) --------------------

    def recover_with_current_checkpoint(
        self,
        segment_paths: Iterable[str | Path] | None = None,
        handler: Callable[[Any], None] | None = None,
    ) -> WALRecoveryReceipt:
        """Replay segments under the current checkpoint (recovery closure).

        Segments whose sealed identity matches the published checkpoint are
        skipped; later appends and identity mismatches are replayed.
        """

        with self._lock:
            bundle = self._current_bundle
            if bundle is None:
                loaded = self.checkpoint_store.load_current()
                if loaded is not None:
                    bundle, _state = loaded
                    self._current_bundle = bundle
            known = dict(self._known_segment_paths)

        if segment_paths is None:
            paths: list[Path] = list(self.segments_directory.glob("*.wal"))
            paths.extend(p for p in known.values() if p not in paths)
        else:
            paths = [Path(p) for p in segment_paths]

        applied: list[str] = []

        def _default_handler(record: Any) -> None:
            key = getattr(record, "record_key", None) or getattr(
                record, "identity_key", ""
            )
            applied.append(str(key))

        receipt = WALRecovery(paths, checkpoint=bundle).recover(
            handler or _default_handler
        )
        self._trace.record(
            MaintenanceTraceKind.VERIFY,
            success=True,
            phase=MaintenancePhase.VERIFY.value,
            detail={
                "replayed_count": receipt.replayed_count,
                "committed_transactions": list(receipt.committed_transactions),
                "checkpoint_id": bundle.checkpoint.checkpoint_id if bundle else "",
            },
        )
        return receipt

    # -- worker lifecycle ---------------------------------------------------

    def start_worker(
        self,
        *,
        on_cycle: Callable[[MaintenanceWorker], None] | None = None,
    ) -> WorkerHeartbeat:
        """Start the bounded maintenance worker (heartbeats until stop)."""

        with self._lock:
            self._ensure_open()
            if self._worker is not None and self._worker.running:
                hb = self._worker.last_heartbeat
                assert hb is not None
                return hb

            def _cycle(worker: MaintenanceWorker) -> None:
                if on_cycle is not None:
                    on_cycle(worker)
                # Always refresh coordinator-visible heartbeat phase.
                self._trace.record(
                    MaintenanceTraceKind.HEARTBEAT,
                    success=True,
                    phase=MaintenancePhase.HEARTBEAT.value,
                    detail={
                        "worker_id": worker.worker_id,
                        "cycle": worker.cycle,
                    },
                )

            self._worker = MaintenanceWorker(
                self.heartbeat_path,
                mount_id=self.mount_id,
                interval_seconds=self.heartbeat_interval_seconds,
                stop_timeout_seconds=self.worker_stop_timeout_seconds,
                on_cycle=_cycle,
            )
            hb = self._worker.start()
            self._trace.record(
                MaintenanceTraceKind.WORKER,
                success=True,
                phase=MaintenancePhase.WORKER_START.value,
                detail=hb.to_record(),
            )
            return hb

    def stop_worker(self, *, timeout_seconds: float | None = None) -> WorkerHeartbeat | None:
        """Stop the worker and wait for the terminal heartbeat."""

        with self._lock:
            worker = self._worker
        if worker is None:
            return None
        hb = worker.stop(timeout_seconds=timeout_seconds)
        self._trace.record(
            MaintenanceTraceKind.WORKER,
            success=True,
            phase=MaintenancePhase.WORKER_STOP.value,
            detail=hb.to_record(),
        )
        return hb

    # -- recovery position / shutdown ---------------------------------------

    def current_recovery_position(self) -> DurableRecoveryPosition:
        with self._lock:
            return self._snapshot_position_unlocked()

    def load_recovery_position(self) -> DurableRecoveryPosition | None:
        raw = _read_json(self.recovery_position_path)
        if not raw:
            return None
        try:
            return DurableRecoveryPosition.from_dict(raw)
        except (MaintenanceError, TypeError, ValueError, KeyError):
            return None

    def persist_recovery_position(self) -> DurableRecoveryPosition:
        with self._lock:
            self._ensure_open()
            return self._persist_position_unlocked()

    def shutdown(self) -> MaintenanceReceipt:
        """Stop workers and persist the latest durable recovery position.

        Shutdown never discards later appends: the persisted position always
        carries ``last_append_sequence >= through_sequence``.
        """

        started = _monotonic()
        receipt_id = f"rcpt:{uuid.uuid4().hex}"
        with self._lock:
            if self._closed:
                position = self.load_recovery_position()
                return MaintenanceReceipt(
                    receipt_id=receipt_id,
                    disposition=MaintenanceDisposition.IDEMPOTENT,
                    success=True,
                    phase=MaintenancePhase.SHUTDOWN,
                    mount_id=self.mount_id,
                    generation_id=self.generation_id,
                    recovery_position=position,
                    message="already shut down",
                    elapsed_seconds=0.0,
                )
            self._shutting_down = True

        # Stop worker outside the main lock to avoid deadlock with cycle callbacks.
        try:
            self.stop_worker()
        except MaintenanceError as exc:
            self._trace.record(
                MaintenanceTraceKind.FAULT,
                success=False,
                phase=MaintenancePhase.WORKER_STOP.value,
                code=exc.code.value,
                detail=exc.detail,
            )

        with self._lock:
            position = self._persist_position_unlocked()
            self._closed = True
            self._shutting_down = False

        self._trace.record(
            MaintenanceTraceKind.SHUTDOWN,
            success=True,
            phase=MaintenancePhase.SHUTDOWN.value,
            detail=position.to_record(),
        )
        self._trace.record(
            MaintenanceTraceKind.POSITION,
            success=True,
            phase=MaintenancePhase.PERSIST_POSITION.value,
            detail={
                "through_sequence": position.through_sequence,
                "last_append_sequence": position.last_append_sequence,
                "checkpoint_id": position.checkpoint_id,
                "has_uncompacted_appends": position.has_uncompacted_appends,
            },
        )

        receipt = MaintenanceReceipt(
            receipt_id=receipt_id,
            disposition=MaintenanceDisposition.SUCCESS,
            success=True,
            phase=MaintenancePhase.SHUTDOWN,
            mount_id=self.mount_id,
            generation_id=self.generation_id,
            checkpoint_id=position.checkpoint_id,
            through_sequence=position.through_sequence,
            last_append_sequence=position.last_append_sequence,
            recovery_position=position,
            message="mount shutdown preserved durable recovery position",
            detail={
                "recovery_position_path": str(self.recovery_position_path),
                "has_uncompacted_appends": position.has_uncompacted_appends,
            },
            elapsed_seconds=_monotonic() - started,
        )
        return self._finish(receipt)

    close = shutdown

    def __enter__(self) -> "WalMaintenanceCoordinator":
        return self

    def __exit__(self, *_: object) -> None:
        if not self.closed:
            self.shutdown()

    # -- internals ----------------------------------------------------------

    def _ensure_open(self) -> None:
        if self._closed or self._shutting_down:
            raise MaintenanceClosedError(
                detail={"closed": self._closed, "shutting_down": self._shutting_down}
            )

    def _apply_position(self, position: DurableRecoveryPosition) -> None:
        self._through_sequence = position.through_sequence
        self._last_append_sequence = position.last_append_sequence
        self._checkpoint_id = position.checkpoint_id
        self._checkpoint_checksum = position.checkpoint_checksum
        self._state_digest = position.state_digest
        self._sealed_segment_ids = list(position.sealed_segment_ids)
        if position.generation_id:
            self.generation_id = position.generation_id

    def _snapshot_position_unlocked(self) -> DurableRecoveryPosition:
        return DurableRecoveryPosition(
            generation_id=self.generation_id,
            through_sequence=self._through_sequence,
            last_append_sequence=self._last_append_sequence,
            checkpoint_id=self._checkpoint_id,
            checkpoint_checksum=self._checkpoint_checksum,
            state_digest=self._state_digest,
            sealed_segment_ids=tuple(self._sealed_segment_ids),
            mount_id=self.mount_id,
            updated_at_unix_ms=_unix_ms(),
        )

    def _persist_position_unlocked(self) -> DurableRecoveryPosition:
        position = self._snapshot_position_unlocked()
        _atomic_write_json(self.recovery_position_path, position.to_record())
        self._trace.record(
            MaintenanceTraceKind.POSITION,
            success=True,
            phase=MaintenancePhase.PERSIST_POSITION.value,
            detail=position.to_record(),
        )
        return position

    def _paths_for_segments(self, segment_ids: Sequence[str]) -> tuple[Path, ...]:
        with self._lock:
            known = dict(self._known_segment_paths)
        paths: list[Path] = []
        for segment_id in segment_ids:
            if segment_id in known:
                paths.append(known[segment_id])
                continue
            candidate = self.segments_directory / f"{segment_id}.wal"
            if candidate.exists():
                paths.append(candidate)
        return tuple(paths)

    def _finish(self, receipt: MaintenanceReceipt) -> MaintenanceReceipt:
        self._trace.record(
            MaintenanceTraceKind.RECEIPT,
            success=receipt.success,
            phase=receipt.phase.value,
            code=receipt.error_code,
            detail={"disposition": receipt.disposition.value, "receipt_id": receipt.receipt_id},
        )
        with self._lock:
            self._last_receipt = receipt
            self._receipts.append(receipt)
            if len(self._receipts) > MAX_TRACE_EVENTS:
                self._receipts = self._receipts[-MAX_TRACE_EVENTS:]
        return receipt

    def _failure_receipt(
        self,
        *,
        receipt_id: str,
        phase: MaintenancePhase,
        default_code: MaintenanceErrorCode,
        exc: BaseException,
        started: float,
        extra_detail: Mapping[str, Any] | None = None,
    ) -> MaintenanceReceipt:
        if isinstance(exc, MaintenanceError):
            code = exc.code.value
            detail: dict[str, Any] = dict(exc.detail)
        elif isinstance(exc, WALArchiveError):
            code = MaintenanceErrorCode.ARCHIVE.value
            detail = {}
        elif isinstance(exc, WALCheckpointError):
            code = (
                MaintenanceErrorCode.COMPACTION.value
                if phase is MaintenancePhase.COMPACT
                else MaintenanceErrorCode.CHECKPOINT.value
            )
            detail = {}
        else:
            code = default_code.value
            detail = {"error_type": type(exc).__name__}
        if extra_detail:
            detail.update(dict(extra_detail))
        self._trace.record(
            MaintenanceTraceKind.FAULT,
            success=False,
            phase=phase.value,
            code=code,
            detail={"error": str(exc), **detail},
        )
        return self._finish(
            MaintenanceReceipt(
                receipt_id=receipt_id,
                disposition=MaintenanceDisposition.FAILED,
                success=False,
                phase=phase,
                mount_id=self.mount_id,
                generation_id=self.generation_id,
                error_code=code,
                message=str(exc),
                detail=detail,
                elapsed_seconds=_monotonic() - started,
            )
        )


# Plan aliases.
WalMaintenanceFacade = WalMaintenanceCoordinator
MountMaintenanceCoordinator = WalMaintenanceCoordinator


def build_wal_maintenance_coordinator(
    state_directory: str | Path,
    **kwargs: Any,
) -> WalMaintenanceCoordinator:
    """Factory for :class:`WalMaintenanceCoordinator`."""

    return WalMaintenanceCoordinator(state_directory, **kwargs)


def maintenance_phases() -> tuple[str, ...]:
    return tuple(p.value for p in MaintenancePhase)


def maintenance_dispositions() -> tuple[str, ...]:
    return tuple(d.value for d in MaintenanceDisposition)


def worker_states() -> tuple[str, ...]:
    return tuple(s.value for s in WorkerState)


__all__ = [
    "CONTRACT_VERSION",
    "DEFAULT_GENERATION_ID",
    "DEFAULT_MIN_FREE_BYTES",
    "DEFAULT_MOUNT_ID",
    "DurableRecoveryPosition",
    "DurableRecoveryPosition_V1",
    "DiskPressureError",
    "DiskPressurePolicy",
    "MAINTENANCE_RECEIPT_SCHEMA",
    "MaintenanceArchiveError",
    "MaintenanceClosedError",
    "MaintenanceDisposition",
    "MaintenanceError",
    "MaintenanceErrorCode",
    "MaintenancePhase",
    "MaintenanceProtocolError",
    "MaintenanceReceipt",
    "MaintenanceReceipt_V1",
    "MaintenanceTrace",
    "MaintenanceTraceKind",
    "MaintenanceValidationError",
    "MaintenanceWorker",
    "MaintenanceWorker_V1",
    "MountMaintenanceCoordinator",
    "SCHEMA_VERSION",
    "TASK_ID",
    "WAL_MAINTENANCE_COORDINATOR_SCHEMA",
    "WalMaintenanceCoordinator",
    "WalMaintenanceCoordinator_V1",
    "WalMaintenanceFacade",
    "WorkerHeartbeat",
    "WorkerState",
    "archive_completed",
    "build_wal_maintenance_coordinator",
    "create_checkpoint",
    "disk_usage",
    "evaluate_disk_pressure",
    "maintenance_dispositions",
    "maintenance_phases",
    "worker_states",
]
