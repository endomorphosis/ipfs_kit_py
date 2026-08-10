"""Pre-ready mount recovery, idempotent replay, orphan reclamation, and leases (KVFS-301).

This module owns *recovery/startup and state leases* for the kernel VFS host
path:

* a **single-writer state lease** fences concurrent mounts on the same state
  directory;
* **recovery completes before ready** — the mount lifecycle may not enter
  ``READY`` / advertise readiness until WAL replay and orphan reclamation
  finish successfully;
* **repeated restart** applies committed effects exactly once and resolves
  incomplete transactions per policy (default: compensate / roll back);
* **only provably orphaned** stages and handles are reclaimed;
* recovery **preserves evidence** on error; and
* recovery **terminates within a declared bound**.

Native FUSE/WinFsp launchers call this API later (KVFS-500+).  Conflict policy:
own recovery/startup and state leases only; do not change native lifecycle.

Interfaces (plan aliases): ``MountRecoveryCoordinator@1``,
``StateLease@1``, ``MountRecoveryReceipt@1``.
"""

from __future__ import annotations

import errno as errno_mod
import json
import os
import threading
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar, Final

from ipfs_kit_py.core.vfs.handles import HandleTable, ReclaimResult
from ipfs_kit_py.core.vfs.host_contracts import (
    HostMountLifecycle,
    HostPlatform,
    MountLifecycleState,
    assert_legal_mount_transition,
    is_legal_mount_transition,
)
from ipfs_kit_py.kernel_vfs.durable_mutation import (
    DurableMutationCoordinator,
    MutationEffectBackend,
)

# ---------------------------------------------------------------------------
# Schema / version / bounds
# ---------------------------------------------------------------------------

TASK_ID: Final[str] = "KVFS-301"
CONTRACT_VERSION: Final[int] = 1
SCHEMA_MAJOR: Final[int] = 1
SCHEMA_MINOR: Final[int] = 0
SCHEMA_PATCH: Final[int] = 0
SCHEMA_VERSION: Final[str] = f"{SCHEMA_MAJOR}.{SCHEMA_MINOR}.{SCHEMA_PATCH}"

RECOVERY_NAMESPACE: Final[str] = "ipfs_kit_py/kernel_vfs/wal_recovery"

MOUNT_RECOVERY_COORDINATOR_SCHEMA: Final[str] = (
    f"{RECOVERY_NAMESPACE}/mount-recovery-coordinator@{SCHEMA_MAJOR}"
)
STATE_LEASE_SCHEMA: Final[str] = (
    f"{RECOVERY_NAMESPACE}/state-lease@{SCHEMA_MAJOR}"
)
MOUNT_RECOVERY_RECEIPT_SCHEMA: Final[str] = (
    f"{RECOVERY_NAMESPACE}/mount-recovery-receipt@{SCHEMA_MAJOR}"
)
ORPHAN_RECLAIM_RECEIPT_SCHEMA: Final[str] = (
    f"{RECOVERY_NAMESPACE}/orphan-reclaim-receipt@{SCHEMA_MAJOR}"
)
RECOVERY_EVIDENCE_SCHEMA: Final[str] = (
    f"{RECOVERY_NAMESPACE}/recovery-evidence@{SCHEMA_MAJOR}"
)
RECOVERY_TRACE_SCHEMA: Final[str] = (
    f"{RECOVERY_NAMESPACE}/recovery-trace@{SCHEMA_MAJOR}"
)

# Public interface aliases.
MountRecoveryCoordinator_V1: Final[str] = MOUNT_RECOVERY_COORDINATOR_SCHEMA
StateLease_V1: Final[str] = STATE_LEASE_SCHEMA
MountRecoveryReceipt_V1: Final[str] = MOUNT_RECOVERY_RECEIPT_SCHEMA

LEASE_FILENAME: Final[str] = "mount.lease"
LEASE_HOLDER_FILENAME: Final[str] = "mount.lease.holder.json"
EVIDENCE_DIRNAME: Final[str] = "recovery-evidence"
STAGES_DIRNAME: Final[str] = "stages"
STAGE_INDEX_FILENAME: Final[str] = "stage-index.jsonl"
DEFAULT_MOUNT_ID: Final[str] = "mount:default"
DEFAULT_GENERATION_ID: Final[str] = "wal-gen:recovery-1"
DEFAULT_RECOVERY_TIMEOUT_SECONDS: Final[float] = 30.0
DEFAULT_LEASE_TTL_SECONDS: Final[float] = 60.0
MAX_TRACE_EVENTS: Final[int] = 4_096
MAX_TEXT_BYTES: Final[int] = 4_096
MAX_PATH_BYTES: Final[int] = 4_096
MAX_SAFE_INTEGER: Final[int] = (1 << 53) - 1


# ---------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------


class RecoveryPhase(str, Enum):
    """Ordered phases of pre-ready mount recovery."""

    ACQUIRE_LEASE = "acquire_lease"
    ENTER_RECOVERING = "enter_recovering"
    REPLAY_WAL = "replay_wal"
    RESOLVE_INCOMPLETE = "resolve_incomplete"
    RECLAIM_ORPHANS = "reclaim_orphans"
    MARK_COMPLETE = "mark_complete"
    ENTER_READY = "enter_ready"
    PRESERVE_EVIDENCE = "preserve_evidence"
    RELEASE_LEASE = "release_lease"
    FAILED = "failed"


class IncompleteTransactionPolicy(str, Enum):
    """How durable non-committed intents are resolved during recovery."""

    COMPENSATE = "compensate"
    """Roll back / compensate incomplete transactions (default, fail-closed)."""

    RETAIN = "retain"
    """Leave incomplete transactions for a later operator decision (no apply)."""


class RecoveryDisposition(str, Enum):
    """Terminal disposition of one recovery attempt."""

    READY = "ready"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    LEASE_HELD = "lease_held"
    IDEMPOTENT = "idempotent"


class RecoveryErrorCode(str, Enum):
    """Stable error codes for the recovery façade."""

    LEASE_HELD = "RECOVERY_LEASE_HELD"
    LEASE_LOST = "RECOVERY_LEASE_LOST"
    TIMEOUT = "RECOVERY_TIMEOUT"
    WAL_REPLAY = "RECOVERY_WAL_REPLAY"
    ORPHAN_RECLAIM = "RECOVERY_ORPHAN_RECLAIM"
    LIFECYCLE = "RECOVERY_LIFECYCLE"
    VALIDATION = "RECOVERY_VALIDATION"
    PROTOCOL = "RECOVERY_PROTOCOL"
    EVIDENCE = "RECOVERY_EVIDENCE"
    INTERNAL = "RECOVERY_INTERNAL"
    BOUND_EXCEEDED = "RECOVERY_BOUND_EXCEEDED"


class RecoveryTraceKind(str, Enum):
    """Closed trace kinds for recovery evidence."""

    LEASE_ACQUIRE = "lease_acquire"
    LEASE_RELEASE = "lease_release"
    LEASE_HEARTBEAT = "lease_heartbeat"
    LEASE_FENCE = "lease_fence"
    PHASE = "phase"
    REPLAY = "replay"
    COMPENSATE = "compensate"
    ORPHAN_STAGE = "orphan_stage"
    ORPHAN_HANDLE = "orphan_handle"
    READY = "ready"
    FAILED = "failed"
    EVIDENCE = "evidence"
    BOUND = "bound"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class MountRecoveryError(Exception):
    """Base error for mount recovery failures that must not be ignored."""

    def __init__(
        self,
        message: str,
        *,
        code: RecoveryErrorCode = RecoveryErrorCode.INTERNAL,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code if isinstance(code, RecoveryErrorCode) else RecoveryErrorCode(code)
        self.detail = dict(detail or {})

    def to_record(self) -> dict[str, Any]:
        return {
            "error": type(self).__name__,
            "message": self.message,
            "code": self.code.value,
            "detail": dict(self.detail),
        }


class StateLeaseError(MountRecoveryError):
    """State lease acquisition or ownership failure."""


class StateLeaseHeldError(StateLeaseError):
    """Another mount already holds the single-writer state lease."""

    def __init__(
        self,
        message: str = "state lease is held by another mount",
        *,
        holder: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code=RecoveryErrorCode.LEASE_HELD,
            detail={"holder": dict(holder or {})},
        )
        self.holder = dict(holder or {})


class RecoveryTimeoutError(MountRecoveryError):
    """Recovery exceeded the declared time bound."""

    def __init__(
        self,
        message: str = "recovery exceeded declared time bound",
        *,
        timeout_seconds: float = 0.0,
        elapsed_seconds: float = 0.0,
        phase: str = "",
    ) -> None:
        super().__init__(
            message,
            code=RecoveryErrorCode.TIMEOUT,
            detail={
                "timeout_seconds": timeout_seconds,
                "elapsed_seconds": elapsed_seconds,
                "phase": phase,
            },
        )


class RecoveryLifecycleError(MountRecoveryError):
    """Illegal mount lifecycle transition during recovery."""

    def __init__(
        self,
        message: str,
        *,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code=RecoveryErrorCode.LIFECYCLE,
            detail=detail,
        )


class RecoveryProtocolError(MountRecoveryError):
    """Protocol / readiness invariant violation."""

    def __init__(
        self,
        message: str,
        *,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code=RecoveryErrorCode.PROTOCOL,
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
        raise MountRecoveryError(
            f"{name} exceeds {limit} bytes",
            code=RecoveryErrorCode.VALIDATION,
            detail={"field": name},
        )
    return text


def _bool(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise MountRecoveryError(
            f"{name} must be a bool",
            code=RecoveryErrorCode.VALIDATION,
            detail={"field": name, "value": value},
        )
    return value


def _nonneg_float(value: Any, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise MountRecoveryError(
            f"{name} must be a non-negative number",
            code=RecoveryErrorCode.VALIDATION,
            detail={"field": name, "value": value},
        ) from exc
    if number < 0 or number != number:  # NaN
        raise MountRecoveryError(
            f"{name} must be a non-negative number",
            code=RecoveryErrorCode.VALIDATION,
            detail={"field": name, "value": value},
        )
    return number


def _monotonic() -> float:
    return time.monotonic()


def _unix_ms() -> int:
    return int(time.time() * 1000)


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{uuid.uuid4().hex[:8]}")
    data = json.dumps(dict(payload), sort_keys=True, separators=(",", ":"))
    tmp.write_text(data + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(raw) if isinstance(raw, Mapping) else {}


def _try_flock_exclusive(fd: int) -> bool:
    """Attempt a non-blocking exclusive flock. Returns True if acquired."""

    try:
        import fcntl
    except ImportError:
        return _try_msvcrt_lock(fd)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except BlockingIOError:
        return False
    except OSError as exc:
        if exc.errno in (errno_mod.EACCES, errno_mod.EAGAIN, errno_mod.EWOULDBLOCK):
            return False
        raise


def _try_msvcrt_lock(fd: int) -> bool:
    try:
        import msvcrt
    except ImportError:
        # Last-resort cooperative lock via exclusive holder file semantics.
        return True
    try:
        # Lock one byte at start of file.
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        return True
    except OSError:
        return False


def _unlock_fd(fd: int) -> None:
    try:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_UN)
        return
    except ImportError:
        pass
    try:
        import msvcrt

        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    except (ImportError, OSError):
        pass


# ---------------------------------------------------------------------------
# State lease (single-writer fence)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StateLeaseHolder:
    """Identity of the mount that holds the single-writer state lease."""

    SCHEMA: ClassVar[str] = STATE_LEASE_SCHEMA

    mount_id: str
    holder_id: str
    pid: int
    generation: int = 0
    acquired_at_unix_ms: int = 0
    heartbeat_unix_ms: int = 0
    ttl_seconds: float = DEFAULT_LEASE_TTL_SECONDS
    state_directory: str = ""

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "mount_id": self.mount_id,
            "holder_id": self.holder_id,
            "pid": self.pid,
            "generation": self.generation,
            "acquired_at_unix_ms": self.acquired_at_unix_ms,
            "heartbeat_unix_ms": self.heartbeat_unix_ms,
            "ttl_seconds": self.ttl_seconds,
            "state_directory": self.state_directory,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "StateLeaseHolder":
        return cls(
            mount_id=str(payload.get("mount_id") or ""),
            holder_id=str(payload.get("holder_id") or ""),
            pid=int(payload.get("pid") or 0),
            generation=int(payload.get("generation") or 0),
            acquired_at_unix_ms=int(payload.get("acquired_at_unix_ms") or 0),
            heartbeat_unix_ms=int(payload.get("heartbeat_unix_ms") or 0),
            ttl_seconds=float(payload.get("ttl_seconds") or DEFAULT_LEASE_TTL_SECONDS),
            state_directory=str(payload.get("state_directory") or ""),
        )


class StateLease:
    """Single-writer exclusive lease over a mount state directory.

    Concurrent mounts on the same state directory are fenced: only one holder
    may acquire the lease.  The lease is process-local (open fd + flock) and
    records a durable holder manifest for diagnostics and stale detection.
    """

    SCHEMA: ClassVar[str] = STATE_LEASE_SCHEMA
    CONTRACT_VERSION: ClassVar[int] = CONTRACT_VERSION

    def __init__(
        self,
        state_directory: str | Path,
        *,
        mount_id: str = DEFAULT_MOUNT_ID,
        holder_id: str | None = None,
        generation: int = 0,
        ttl_seconds: float = DEFAULT_LEASE_TTL_SECONDS,
        pid: int | None = None,
    ) -> None:
        self.state_directory = Path(state_directory)
        self.state_directory.mkdir(parents=True, exist_ok=True)
        self.mount_id = _text(mount_id, "mount_id") or DEFAULT_MOUNT_ID
        self.holder_id = _text(holder_id or f"holder:{uuid.uuid4().hex}", "holder_id")
        self.generation = int(generation)
        self.ttl_seconds = _nonneg_float(ttl_seconds, "ttl_seconds") or DEFAULT_LEASE_TTL_SECONDS
        self.pid = int(os.getpid() if pid is None else pid)
        self._lease_path = self.state_directory / LEASE_FILENAME
        self._holder_path = self.state_directory / LEASE_HOLDER_FILENAME
        self._fd: int | None = None
        self._held = False
        self._lock = threading.RLock()
        self._holder: StateLeaseHolder | None = None
        self._acquired_at_unix_ms = 0

    # -- properties ---------------------------------------------------------

    @property
    def held(self) -> bool:
        with self._lock:
            return self._held

    @property
    def holder(self) -> StateLeaseHolder | None:
        with self._lock:
            return self._holder

    @property
    def lease_path(self) -> Path:
        return self._lease_path

    # -- acquire / release --------------------------------------------------

    def try_acquire(self) -> StateLeaseHolder:
        """Non-blocking exclusive acquire. Raises :class:`StateLeaseHeldError`."""

        with self._lock:
            if self._held and self._holder is not None:
                return self._holder

            # Open (create) the lease file then take a non-blocking exclusive
            # flock.  Holder metadata is written only after the fence is held so
            # concurrent contenders always observe either a live flock or a
            # durable holder identity for diagnostics.
            fd = os.open(
                str(self._lease_path),
                os.O_RDWR | os.O_CREAT,
                0o644,
            )
            # Track ownership carefully: never double-close ``fd``. A second
            # close can free a recycled descriptor belonging to the winner's
            # flock and silently drop the single-writer fence under contention.
            owned = False
            try:
                if not _try_flock_exclusive(fd):
                    existing = _read_json(self._holder_path)
                    if not existing:
                        # Winner may still be writing the holder manifest; one
                        # brief re-read improves diagnostic fidelity under race.
                        time.sleep(0.001)
                        existing = _read_json(self._holder_path)
                    raise StateLeaseHeldError(holder=existing)

                now = _unix_ms()
                holder = StateLeaseHolder(
                    mount_id=self.mount_id,
                    holder_id=self.holder_id,
                    pid=self.pid,
                    generation=self.generation,
                    acquired_at_unix_ms=now,
                    heartbeat_unix_ms=now,
                    ttl_seconds=self.ttl_seconds,
                    state_directory=str(self.state_directory),
                )
                _atomic_write_json(self._holder_path, holder.to_record())
                self._fd = fd
                self._held = True
                self._holder = holder
                self._acquired_at_unix_ms = now
                owned = True
                return holder
            finally:
                if not owned:
                    try:
                        os.close(fd)
                    except OSError:
                        pass

    def acquire(self, *, timeout_seconds: float = 0.0) -> StateLeaseHolder:
        """Acquire with optional wait. ``timeout_seconds=0`` is non-blocking."""

        deadline = _monotonic() + max(0.0, float(timeout_seconds))
        while True:
            try:
                return self.try_acquire()
            except StateLeaseHeldError:
                if timeout_seconds <= 0 or _monotonic() >= deadline:
                    raise
                time.sleep(0.01)

    def heartbeat(self) -> StateLeaseHolder:
        """Refresh lease heartbeat; fails if lease is not held by this process."""

        with self._lock:
            if not self._held or self._holder is None or self._fd is None:
                raise StateLeaseError(
                    "cannot heartbeat a lease that is not held",
                    code=RecoveryErrorCode.LEASE_LOST,
                )
            now = _unix_ms()
            holder = StateLeaseHolder(
                mount_id=self._holder.mount_id,
                holder_id=self._holder.holder_id,
                pid=self._holder.pid,
                generation=self._holder.generation,
                acquired_at_unix_ms=self._holder.acquired_at_unix_ms,
                heartbeat_unix_ms=now,
                ttl_seconds=self._holder.ttl_seconds,
                state_directory=self._holder.state_directory,
            )
            _atomic_write_json(self._holder_path, holder.to_record())
            self._holder = holder
            return holder

    def release(self) -> bool:
        """Release the lease if held. Idempotent."""

        with self._lock:
            if not self._held:
                return False
            fd = self._fd
            self._fd = None
            self._held = False
            released_holder = self._holder
            self._holder = None
            if fd is not None:
                try:
                    _unlock_fd(fd)
                finally:
                    try:
                        os.close(fd)
                    except OSError:
                        pass
            # Clear holder manifest only if we still own the recorded identity.
            existing = _read_json(self._holder_path)
            if (
                released_holder is not None
                and existing.get("holder_id") == released_holder.holder_id
            ):
                try:
                    self._holder_path.unlink(missing_ok=True)  # type: ignore[call-arg]
                except TypeError:
                    # Python <3.8 style; still safe under 3.12.
                    if self._holder_path.exists():
                        self._holder_path.unlink()
                except OSError:
                    pass
            return True

    def read_holder(self) -> StateLeaseHolder | None:
        raw = _read_json(self._holder_path)
        if not raw:
            return None
        return StateLeaseHolder.from_dict(raw)

    def close(self) -> None:
        self.release()

    def __enter__(self) -> "StateLease":
        self.try_acquire()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


# ---------------------------------------------------------------------------
# Receipts / evidence
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OrphanReclaimReceipt:
    """Receipt for reclaiming only provably orphaned stages and handles."""

    SCHEMA: ClassVar[str] = ORPHAN_RECLAIM_RECEIPT_SCHEMA

    reclaimed_stages: int = 0
    retained_stages: int = 0
    reclaimed_handles: int = 0
    reclaimed_inodes: int = 0
    expired_leases: int = 0
    stage_ids_reclaimed: tuple[str, ...] = ()
    stage_ids_retained: tuple[str, ...] = ()
    detail: Mapping[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "reclaimed_stages": self.reclaimed_stages,
            "retained_stages": self.retained_stages,
            "reclaimed_handles": self.reclaimed_handles,
            "reclaimed_inodes": self.reclaimed_inodes,
            "expired_leases": self.expired_leases,
            "stage_ids_reclaimed": list(self.stage_ids_reclaimed),
            "stage_ids_retained": list(self.stage_ids_retained),
            "detail": dict(self.detail),
        }


@dataclass(frozen=True)
class MountRecoveryReceipt:
    """Exact receipt for one pre-ready recovery attempt.

    Ready success requires ``recovery_complete=True`` and a held (or
    deliberately released-after-ready) lease fence during recovery.  Failed
    receipts never claim readiness.
    """

    SCHEMA: ClassVar[str] = MOUNT_RECOVERY_RECEIPT_SCHEMA

    receipt_id: str
    disposition: RecoveryDisposition
    success: bool
    recovery_complete: bool
    ready: bool
    mount_id: str
    generation_id: str = DEFAULT_GENERATION_ID
    lifecycle_state: MountLifecycleState = MountLifecycleState.UNINITIALIZED
    phases: tuple[str, ...] = ()
    replayed: int = 0
    rolled_back: int = 0
    incomplete_resolved: int = 0
    incomplete_policy: IncompleteTransactionPolicy = IncompleteTransactionPolicy.COMPENSATE
    orphan_reclaim: OrphanReclaimReceipt | None = None
    lease_holder: StateLeaseHolder | None = None
    elapsed_seconds: float = 0.0
    timeout_seconds: float = DEFAULT_RECOVERY_TIMEOUT_SECONDS
    error_code: str = ""
    message: str = ""
    evidence_path: str = ""
    detail: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.disposition, RecoveryDisposition):
            object.__setattr__(
                self, "disposition", RecoveryDisposition(self.disposition)
            )
        if not isinstance(self.lifecycle_state, MountLifecycleState):
            object.__setattr__(
                self, "lifecycle_state", MountLifecycleState(self.lifecycle_state)
            )
        if not isinstance(self.incomplete_policy, IncompleteTransactionPolicy):
            object.__setattr__(
                self,
                "incomplete_policy",
                IncompleteTransactionPolicy(self.incomplete_policy),
            )
        object.__setattr__(self, "success", bool(self.success))
        object.__setattr__(self, "recovery_complete", bool(self.recovery_complete))
        object.__setattr__(self, "ready", bool(self.ready))
        self._assert_policy()

    def _assert_policy(self) -> None:
        if self.ready:
            if not self.success:
                raise RecoveryProtocolError(
                    "ready receipt cannot claim success=False",
                    detail=self.to_record_unsafe(),
                )
            if not self.recovery_complete:
                raise RecoveryProtocolError(
                    "ready requires recovery_complete",
                    detail={"receipt_id": self.receipt_id},
                )
            if self.lifecycle_state is not MountLifecycleState.READY:
                raise RecoveryProtocolError(
                    "ready requires lifecycle_state READY",
                    detail={
                        "receipt_id": self.receipt_id,
                        "lifecycle_state": self.lifecycle_state.value,
                    },
                )
        if self.success and self.disposition is RecoveryDisposition.FAILED:
            raise RecoveryProtocolError(
                "success cannot pair with FAILED disposition",
                detail={"receipt_id": self.receipt_id},
            )
        if self.disposition is RecoveryDisposition.READY and not self.ready:
            raise RecoveryProtocolError(
                "READY disposition requires ready=True",
                detail={"receipt_id": self.receipt_id},
            )

    def to_record_unsafe(self) -> dict[str, Any]:
        record: dict[str, Any] = {
            "schema": self.SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "receipt_id": self.receipt_id,
            "disposition": self.disposition.value,
            "success": self.success,
            "recovery_complete": self.recovery_complete,
            "ready": self.ready,
            "mount_id": self.mount_id,
            "generation_id": self.generation_id,
            "lifecycle_state": self.lifecycle_state.value,
            "phases": list(self.phases),
            "replayed": self.replayed,
            "rolled_back": self.rolled_back,
            "incomplete_resolved": self.incomplete_resolved,
            "incomplete_policy": self.incomplete_policy.value,
            "elapsed_seconds": self.elapsed_seconds,
            "timeout_seconds": self.timeout_seconds,
            "error_code": self.error_code,
            "message": self.message,
            "evidence_path": self.evidence_path,
            "detail": dict(self.detail),
        }
        if self.orphan_reclaim is not None:
            record["orphan_reclaim"] = self.orphan_reclaim.to_record()
        if self.lease_holder is not None:
            record["lease_holder"] = self.lease_holder.to_record()
        return record

    def to_record(self) -> dict[str, Any]:
        self._assert_policy()
        return self.to_record_unsafe()


@dataclass(frozen=True)
class RecoveryTraceEvent:
    SCHEMA: ClassVar[str] = RECOVERY_TRACE_SCHEMA

    kind: RecoveryTraceKind
    success: bool
    phase: str = ""
    code: str = ""
    detail: Mapping[str, Any] = field(default_factory=dict)
    unix_ms: int = 0

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "kind": self.kind.value if isinstance(self.kind, RecoveryTraceKind) else self.kind,
            "success": self.success,
            "phase": self.phase,
            "code": self.code,
            "detail": dict(self.detail),
            "unix_ms": self.unix_ms,
        }


class RecoveryTrace:
    """Bounded ring of recovery evidence events."""

    def __init__(self, *, capacity: int = MAX_TRACE_EVENTS) -> None:
        self._capacity = max(1, int(capacity))
        self._events: list[RecoveryTraceEvent] = []
        self._lock = threading.RLock()

    def record(
        self,
        kind: RecoveryTraceKind | str,
        *,
        success: bool,
        phase: str = "",
        code: str = "",
        detail: Mapping[str, Any] | None = None,
    ) -> RecoveryTraceEvent:
        if not isinstance(kind, RecoveryTraceKind):
            kind = RecoveryTraceKind(kind)
        event = RecoveryTraceEvent(
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

    def events(self) -> tuple[RecoveryTraceEvent, ...]:
        with self._lock:
            return tuple(self._events)

    def kinds(self) -> list[str]:
        return [e.kind.value for e in self.events()]

    def phases(self) -> list[str]:
        return [e.phase for e in self.events() if e.phase]

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


# ---------------------------------------------------------------------------
# Stage index / orphan stage reclamation
# ---------------------------------------------------------------------------


def stage_path_for(stages_dir: Path, stage_id: str) -> Path:
    safe = stage_id.replace("/", "_").replace("\\", "_").replace(":", "_")
    return stages_dir / f"{safe}.stage"


def write_stage(
    stages_dir: Path,
    stage_id: str,
    content: bytes,
    *,
    referenced: bool = True,
    effect_id: str = "",
    transaction_id: str = "",
) -> Path:
    """Materialize a stage blob and append an index entry.

    Stages with ``referenced=True`` are retained during orphan reclamation
    unless recovery proves they are no longer live.  Unreferenced stages are
    candidates for reclamation once no durable intent references them.
    """

    stages_dir.mkdir(parents=True, exist_ok=True)
    path = stage_path_for(stages_dir, stage_id)
    path.write_bytes(content)
    index_path = stages_dir / STAGE_INDEX_FILENAME
    entry = {
        "stage_id": stage_id,
        "path": path.name,
        "size": len(content),
        "referenced": bool(referenced),
        "effect_id": effect_id,
        "transaction_id": transaction_id,
        "created_unix_ms": _unix_ms(),
        "checksum": f"sha256:{__import__('hashlib').sha256(content).hexdigest()}",
    }
    with open(index_path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n")
    return path


def _load_stage_index(stages_dir: Path) -> list[dict[str, Any]]:
    index_path = stages_dir / STAGE_INDEX_FILENAME
    if not index_path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in index_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(raw, Mapping):
            entries.append(dict(raw))
    return entries


def _referenced_stage_ids_from_wal(wal_directory: Path) -> set[str]:
    """Collect stage ids still referenced by durable intent records."""

    referenced: set[str] = set()
    decisions = wal_directory / "transaction-decisions.jsonl"
    if not decisions.exists():
        return referenced
    for line in decisions.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, Mapping):
            continue
        if entry.get("kind") != "intent":
            continue
        intent = entry.get("intent") or {}
        if not isinstance(intent, Mapping):
            continue
        for key in ("staging_path_ref", "stage_id", "staged_content_cid"):
            value = intent.get(key)
            if value:
                referenced.add(str(value))
        detail = intent.get("intent_detail") or {}
        if isinstance(detail, Mapping):
            for key in ("staging_path_ref", "stage_id", "staged_content_cid"):
                value = detail.get(key)
                if value:
                    referenced.add(str(value))
            content = detail.get("content") or {}
            if isinstance(content, Mapping):
                for key in ("staging_path_ref", "stage_id", "staged_content_cid"):
                    value = content.get(key)
                    if value:
                        referenced.add(str(value))
    return referenced


def reclaim_orphan_stages(
    stages_dir: Path,
    *,
    wal_directory: Path | None = None,
    live_stage_ids: Sequence[str] | None = None,
) -> OrphanReclaimReceipt:
    """Reclaim only stages that are provably unreferenced.

    A stage is reclaimed only when:

    * the index marks it ``referenced=False``, **or**
    * it is absent from both the live set and WAL intent references; and
    * the stage file still exists under the stages directory.

    Referenced / live stages are always retained.
    """

    if not stages_dir.exists():
        return OrphanReclaimReceipt(detail={"stages_dir_missing": True})

    live = set(str(s) for s in (live_stage_ids or ()))
    wal_refs = (
        _referenced_stage_ids_from_wal(wal_directory)
        if wal_directory is not None
        else set()
    )
    # Expand refs to include bare stage ids and path basenames.
    expanded_refs: set[str] = set(wal_refs)
    for ref in list(wal_refs):
        expanded_refs.add(ref)
        if ref.startswith("stage:"):
            expanded_refs.add(ref[len("stage:") :])
        expanded_refs.add(Path(ref).name)

    entries = _load_stage_index(stages_dir)
    reclaimed: list[str] = []
    retained: list[str] = []
    seen_files: set[str] = set()

    for entry in entries:
        stage_id = str(entry.get("stage_id") or "")
        path_name = str(entry.get("path") or "")
        referenced = bool(entry.get("referenced", True))
        effect_id = str(entry.get("effect_id") or "")
        candidates = {
            stage_id,
            path_name,
            effect_id,
            f"stage:{stage_id}" if stage_id else "",
        }
        candidates.discard("")
        is_live = bool(candidates & live) or bool(candidates & expanded_refs)
        path = stages_dir / path_name if path_name else stage_path_for(stages_dir, stage_id)
        seen_files.add(path.name)

        # Fail closed: live / WAL-referenced / still-marked-referenced stages
        # are retained. Only explicitly unreferenced + non-live stages reclaim.
        if is_live or referenced:
            retained.append(stage_id or path_name)
            continue
        if path.exists():
            try:
                path.unlink()
            except OSError:
                retained.append(stage_id or path_name)
                continue
        reclaimed.append(stage_id or path_name)

    # Also scan unindexed *.stage files that are not live/WAL-referenced —
    # only reclaim when no index entry claims them as referenced.
    indexed_names = {str(e.get("path") or "") for e in entries}
    for path in stages_dir.glob("*.stage"):
        if path.name in indexed_names or path.name in seen_files:
            continue
        stage_id = path.stem
        candidates = {stage_id, path.name, f"stage:{stage_id}"}
        if candidates & live or candidates & expanded_refs:
            retained.append(stage_id)
            continue
        # Unindexed + unreferenced → provable orphan after crash of index append.
        try:
            path.unlink()
            reclaimed.append(stage_id)
        except OSError:
            retained.append(stage_id)

    return OrphanReclaimReceipt(
        reclaimed_stages=len(reclaimed),
        retained_stages=len(retained),
        stage_ids_reclaimed=tuple(reclaimed),
        stage_ids_retained=tuple(retained),
        detail={
            "wal_refs": sorted(expanded_refs)[:64],
            "live": sorted(live)[:64],
        },
    )


# ---------------------------------------------------------------------------
# Mount recovery coordinator
# ---------------------------------------------------------------------------


DeadlineChecker = Callable[[str], None]
CrashInjector = Callable[[str], Any]


class MountRecoveryCoordinator:
    """Pre-ready recovery coordinator with single-writer state lease.

    Production entry point for mount startup recovery (KVFS-301).  Recovery
    always runs under the exclusive state lease and must finish before the
    lifecycle may advertise ``READY``.
    """

    SCHEMA: ClassVar[str] = MOUNT_RECOVERY_COORDINATOR_SCHEMA
    CONTRACT_VERSION: ClassVar[int] = CONTRACT_VERSION

    RECOVERY_PHASES: Final[tuple[str, ...]] = tuple(p.value for p in RecoveryPhase)

    def __init__(
        self,
        state_directory: str | Path,
        *,
        mount_id: str = DEFAULT_MOUNT_ID,
        generation_id: str = DEFAULT_GENERATION_ID,
        platform: HostPlatform | str = HostPlatform.HERMETIC,
        mutations: DurableMutationCoordinator | None = None,
        handles: HandleTable | None = None,
        incomplete_policy: IncompleteTransactionPolicy
        | str = IncompleteTransactionPolicy.COMPENSATE,
        recovery_timeout_seconds: float = DEFAULT_RECOVERY_TIMEOUT_SECONDS,
        lease_ttl_seconds: float = DEFAULT_LEASE_TTL_SECONDS,
        recovery_required: bool = True,
        crash_injector: CrashInjector | None = None,
        live_stage_ids: Sequence[str] | None = None,
        holder_id: str | None = None,
    ) -> None:
        # Validate bounds before creating any on-disk state.
        timeout = _nonneg_float(recovery_timeout_seconds, "recovery_timeout_seconds")
        if timeout <= 0:
            raise MountRecoveryError(
                "recovery_timeout_seconds must be positive",
                code=RecoveryErrorCode.VALIDATION,
            )
        self.recovery_timeout_seconds = timeout
        self.state_directory = Path(state_directory)
        self.state_directory.mkdir(parents=True, exist_ok=True)
        self.mount_id = _text(mount_id, "mount_id") or DEFAULT_MOUNT_ID
        self.generation_id = _text(generation_id, "generation_id") or DEFAULT_GENERATION_ID
        if not isinstance(platform, HostPlatform):
            platform = HostPlatform(platform)
        self.platform = platform
        if not isinstance(incomplete_policy, IncompleteTransactionPolicy):
            incomplete_policy = IncompleteTransactionPolicy(incomplete_policy)
        self.incomplete_policy = incomplete_policy
        self.recovery_required = bool(recovery_required)
        self._crash_injector = crash_injector
        self._live_stage_ids = tuple(str(s) for s in (live_stage_ids or ()))
        self._owns_mutations = mutations is None
        self._mutations = mutations or DurableMutationCoordinator(
            self.state_directory / "durable",
            generation_id=self.generation_id,
        )
        self._handles = handles if handles is not None else HandleTable(mount_id=self.mount_id)
        self._lease = StateLease(
            self.state_directory,
            mount_id=self.mount_id,
            holder_id=holder_id,
            ttl_seconds=lease_ttl_seconds,
        )
        self._lifecycle = HostMountLifecycle(
            mount_id=self.mount_id,
            state=MountLifecycleState.UNINITIALIZED,
            platform=self.platform,
            recovery_required=self.recovery_required,
            recovery_complete=False,
            ready=False,
        )
        self._trace = RecoveryTrace()
        self._lock = threading.RLock()
        self._last_receipt: MountRecoveryReceipt | None = None
        self._receipts: list[MountRecoveryReceipt] = []
        self._phases: list[str] = []
        self._closed = False
        self.stages_directory = self.state_directory / STAGES_DIRNAME
        self.stages_directory.mkdir(parents=True, exist_ok=True)
        self.evidence_directory = self.state_directory / EVIDENCE_DIRNAME
        self.evidence_directory.mkdir(parents=True, exist_ok=True)

    # -- properties ---------------------------------------------------------

    @property
    def lease(self) -> StateLease:
        return self._lease

    @property
    def mutations(self) -> DurableMutationCoordinator:
        return self._mutations

    @property
    def handles(self) -> HandleTable:
        return self._handles

    @property
    def lifecycle(self) -> HostMountLifecycle:
        with self._lock:
            return self._lifecycle

    @property
    def ready(self) -> bool:
        return self.lifecycle.ready and self.lifecycle.recovery_complete

    @property
    def recovery_complete(self) -> bool:
        return self.lifecycle.recovery_complete

    @property
    def trace(self) -> RecoveryTrace:
        return self._trace

    @property
    def last_receipt(self) -> MountRecoveryReceipt | None:
        return self._last_receipt

    @property
    def receipts(self) -> tuple[MountRecoveryReceipt, ...]:
        with self._lock:
            return tuple(self._receipts)

    # -- lifecycle helpers --------------------------------------------------

    def _set_lifecycle(self, to_state: MountLifecycleState) -> HostMountLifecycle:
        with self._lock:
            current = self._lifecycle
            if current.state is to_state:
                return current
            try:
                assert_legal_mount_transition(current.state, to_state)
                updated = current.transition_to(to_state)
            except Exception as exc:  # noqa: BLE001
                # Host lifecycle errors are protocol failures for recovery.
                raise RecoveryLifecycleError(
                    str(exc),
                    detail={
                        "from_state": current.state.value,
                        "to_state": to_state.value
                        if isinstance(to_state, MountLifecycleState)
                        else str(to_state),
                    },
                ) from exc
            self._lifecycle = updated
            return updated

    def _phase(self, phase: RecoveryPhase | str, *, started: float | None = None) -> None:
        name = phase.value if isinstance(phase, RecoveryPhase) else str(phase)
        self._phases.append(name)
        self._trace.record(RecoveryTraceKind.PHASE, success=True, phase=name)
        self._boundary(name)
        if started is not None:
            self._check_deadline(started, name)

    def _boundary(self, name: str) -> None:
        if self._crash_injector is None:
            return
        self._crash_injector(name)

    def _check_deadline(self, started: float, phase: str) -> None:
        elapsed = _monotonic() - started
        if elapsed > self.recovery_timeout_seconds:
            self._trace.record(
                RecoveryTraceKind.BOUND,
                success=False,
                phase=phase,
                code=RecoveryErrorCode.TIMEOUT.value,
                detail={
                    "elapsed_seconds": elapsed,
                    "timeout_seconds": self.recovery_timeout_seconds,
                },
            )
            raise RecoveryTimeoutError(
                timeout_seconds=self.recovery_timeout_seconds,
                elapsed_seconds=elapsed,
                phase=phase,
            )

    # -- evidence -----------------------------------------------------------

    def preserve_evidence(
        self,
        *,
        error: BaseException | None = None,
        receipt: MountRecoveryReceipt | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> Path:
        """Persist recovery evidence. Never deletes prior evidence."""

        self._phase(RecoveryPhase.PRESERVE_EVIDENCE)
        stamp = _unix_ms()
        receipt_id = (
            receipt.receipt_id
            if receipt is not None
            else f"evidence:{uuid.uuid4().hex}"
        )
        safe_id = receipt_id.replace("/", "_").replace(":", "_")
        path = self.evidence_directory / f"{stamp}-{safe_id}.json"
        payload: dict[str, Any] = {
            "schema": RECOVERY_EVIDENCE_SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "task_id": TASK_ID,
            "mount_id": self.mount_id,
            "generation_id": self.generation_id,
            "unix_ms": stamp,
            "lifecycle": self.lifecycle.to_record(),
            "phases": list(self._phases),
            "trace": [e.to_record() for e in self._trace.events()],
            "lease_held": self._lease.held,
            "lease_holder": (
                self._lease.holder.to_record() if self._lease.holder is not None else None
            ),
            "extra": dict(extra or {}),
        }
        if error is not None:
            if isinstance(error, MountRecoveryError):
                payload["error"] = error.to_record()
            else:
                payload["error"] = {
                    "error": type(error).__name__,
                    "message": str(error),
                }
        if receipt is not None:
            payload["receipt"] = receipt.to_record_unsafe()
        _atomic_write_json(path, payload)
        self._trace.record(
            RecoveryTraceKind.EVIDENCE,
            success=True,
            phase=RecoveryPhase.PRESERVE_EVIDENCE.value,
            detail={"path": str(path)},
        )
        return path

    # -- recovery core ------------------------------------------------------

    def _recover_mutations(self) -> dict[str, int]:
        """Replay committed effects; resolve incomplete intents per policy.

        * ``COMPENSATE`` (default): full durable recover — replay commits and
          roll back non-committed intents.
        * ``RETAIN``: still apply committed effects exactly once, but leave
          incomplete intents untouched for an operator decision.
        """

        if self.incomplete_policy is IncompleteTransactionPolicy.COMPENSATE:
            return dict(self._mutations.recover())

        # RETAIN incomplete: reuse the same idempotent apply path as recover(),
        # but pass no rollback handler so non-committed intents are skipped.
        # Import the intent rebuild helper from the mutation façade (same package
        # lane) so recovery stays exact without re-implementing request decode.
        from ipfs_kit_py.kernel_vfs import durable_mutation as dm

        backend = self._mutations.backend

        def replay(intent: Mapping[str, Any], effect_id: str) -> Any:
            request = dm._request_from_intent(intent, effect_id=effect_id)
            meta, _receipt = backend.apply(request, effect_id=effect_id)
            return meta

        return dict(
            self._mutations.wal.recover(replay_effect=replay, rollback_effect=None)
        )

    def recover(self) -> MountRecoveryReceipt:
        """Run pre-ready recovery under the single-writer state lease.

        On success the lifecycle is ``READY`` with ``recovery_complete=True``.
        On failure evidence is preserved, lifecycle moves to ``FAILED`` when
        legal, and the lease is released.
        """

        with self._lock:
            if self._closed:
                raise MountRecoveryError(
                    "recovery coordinator is closed",
                    code=RecoveryErrorCode.PROTOCOL,
                )
            # Idempotent: already ready after successful recovery.
            if (
                self._lifecycle.ready
                and self._lifecycle.recovery_complete
                and self._lifecycle.state is MountLifecycleState.READY
            ):
                receipt = MountRecoveryReceipt(
                    receipt_id=f"receipt:idempotent:{uuid.uuid4().hex[:12]}",
                    disposition=RecoveryDisposition.IDEMPOTENT,
                    success=True,
                    recovery_complete=True,
                    ready=True,
                    mount_id=self.mount_id,
                    generation_id=self.generation_id,
                    lifecycle_state=MountLifecycleState.READY,
                    phases=("idempotent",),
                    incomplete_policy=self.incomplete_policy,
                    lease_holder=self._lease.holder,
                    timeout_seconds=self.recovery_timeout_seconds,
                    message="recovery already complete; mount is ready",
                )
                self._last_receipt = receipt
                self._receipts.append(receipt)
                return receipt

        started = _monotonic()
        receipt_id = f"receipt:recovery:{uuid.uuid4().hex}"
        phases: list[str] = []
        self._phases = phases
        replayed = 0
        rolled_back = 0
        incomplete_resolved = 0
        orphan_receipt: OrphanReclaimReceipt | None = None
        lease_holder: StateLeaseHolder | None = None
        evidence_path = ""
        second: dict[str, int] = {"replayed": 0, "rolled_back": 0}

        try:
            # 1. Acquire single-writer lease (fence concurrent mounts).
            self._phase(RecoveryPhase.ACQUIRE_LEASE, started=started)
            try:
                lease_holder = self._lease.try_acquire()
            except StateLeaseHeldError as exc:
                self._trace.record(
                    RecoveryTraceKind.LEASE_FENCE,
                    success=False,
                    phase=RecoveryPhase.ACQUIRE_LEASE.value,
                    code=RecoveryErrorCode.LEASE_HELD.value,
                    detail=exc.detail,
                )
                provisional = MountRecoveryReceipt(
                    receipt_id=receipt_id,
                    disposition=RecoveryDisposition.LEASE_HELD,
                    success=False,
                    recovery_complete=False,
                    ready=False,
                    mount_id=self.mount_id,
                    generation_id=self.generation_id,
                    lifecycle_state=self.lifecycle.state,
                    phases=tuple(phases),
                    incomplete_policy=self.incomplete_policy,
                    elapsed_seconds=_monotonic() - started,
                    timeout_seconds=self.recovery_timeout_seconds,
                    error_code=RecoveryErrorCode.LEASE_HELD.value,
                    message=str(exc),
                    detail=exc.detail,
                )
                evidence_path = str(
                    self.preserve_evidence(error=exc, receipt=provisional)
                )
                receipt = MountRecoveryReceipt(
                    receipt_id=provisional.receipt_id,
                    disposition=provisional.disposition,
                    success=False,
                    recovery_complete=False,
                    ready=False,
                    mount_id=provisional.mount_id,
                    generation_id=provisional.generation_id,
                    lifecycle_state=provisional.lifecycle_state,
                    phases=provisional.phases,
                    incomplete_policy=provisional.incomplete_policy,
                    elapsed_seconds=provisional.elapsed_seconds,
                    timeout_seconds=provisional.timeout_seconds,
                    error_code=provisional.error_code,
                    message=provisional.message,
                    evidence_path=evidence_path,
                    detail=provisional.detail,
                )
                with self._lock:
                    self._last_receipt = receipt
                    self._receipts.append(receipt)
                return receipt

            self._trace.record(
                RecoveryTraceKind.LEASE_ACQUIRE,
                success=True,
                phase=RecoveryPhase.ACQUIRE_LEASE.value,
                detail=lease_holder.to_record(),
            )
            self._check_deadline(started, RecoveryPhase.ACQUIRE_LEASE.value)

            # 2. Enter recovering lifecycle.
            self._phase(RecoveryPhase.ENTER_RECOVERING, started=started)
            state = self.lifecycle.state
            if state is MountLifecycleState.UNINITIALIZED:
                self._set_lifecycle(MountLifecycleState.INITIALIZING)
                state = MountLifecycleState.INITIALIZING
            if state is MountLifecycleState.INITIALIZING:
                self._set_lifecycle(MountLifecycleState.RECOVERING)
            elif state is MountLifecycleState.RECOVERING:
                pass
            elif state is MountLifecycleState.FAILED:
                # Allow re-attempt from FAILED → only via DESTROYING path is
                # legal for HostMountLifecycle; treat as protocol error unless
                # still uninitialized-like.  Failed mounts must be reconstructed.
                raise RecoveryLifecycleError(
                    "cannot recover a FAILED mount in-place; construct a new coordinator",
                    detail={"state": state.value},
                )
            elif state is MountLifecycleState.READY:
                # Should have been handled by idempotent path above.
                pass
            else:
                if is_legal_mount_transition(state, MountLifecycleState.RECOVERING):
                    self._set_lifecycle(MountLifecycleState.RECOVERING)
                else:
                    raise RecoveryLifecycleError(
                        f"cannot enter RECOVERING from {state.value}",
                        detail={"state": state.value},
                    )

            # Ready must remain false until recovery finishes.
            if self.lifecycle.ready or self.lifecycle.recovery_complete:
                raise RecoveryProtocolError(
                    "lifecycle must not be ready before recovery finishes",
                    detail=self.lifecycle.to_record(),
                )

            # 3. Replay WAL / resolve incomplete transactions.
            self._phase(RecoveryPhase.REPLAY_WAL, started=started)
            self._lease.heartbeat()

            self._phase(RecoveryPhase.RESOLVE_INCOMPLETE, started=started)
            stats = self._recover_mutations()
            replayed = int(stats.get("replayed") or 0)
            rolled_back = int(stats.get("rolled_back") or 0)
            incomplete_resolved = rolled_back
            self._trace.record(
                RecoveryTraceKind.REPLAY,
                success=True,
                phase=RecoveryPhase.REPLAY_WAL.value,
                detail={
                    "replayed": replayed,
                    "rolled_back": rolled_back,
                    "policy": self.incomplete_policy.value,
                },
            )
            if self.incomplete_policy is IncompleteTransactionPolicy.COMPENSATE:
                self._trace.record(
                    RecoveryTraceKind.COMPENSATE,
                    success=True,
                    phase=RecoveryPhase.RESOLVE_INCOMPLETE.value,
                    detail={"incomplete_resolved": incomplete_resolved},
                )
            else:
                # RETAIN: committed effects were replayed; incomplete left intact.
                self._trace.record(
                    RecoveryTraceKind.REPLAY,
                    success=True,
                    phase=RecoveryPhase.RESOLVE_INCOMPLETE.value,
                    detail={"retained_incomplete": True, "policy": "retain"},
                )

            # Second recovery is a pure no-op (idempotence of effect ledger).
            second = self._recover_mutations()
            if second.get("replayed", 0) or second.get("rolled_back", 0):
                # Ledger should suppress; if not, still safe if handlers are
                # idempotent — record for evidence but do not fail.
                self._trace.record(
                    RecoveryTraceKind.REPLAY,
                    success=True,
                    phase=RecoveryPhase.REPLAY_WAL.value,
                    detail={"second_pass": second},
                )
            self._check_deadline(started, RecoveryPhase.RESOLVE_INCOMPLETE.value)

            # 4. Reclaim only provably orphaned stages and handles.
            self._phase(RecoveryPhase.RECLAIM_ORPHANS, started=started)
            self._lease.heartbeat()
            wal_dir = self._mutations.directory / "wal"
            stage_receipt = reclaim_orphan_stages(
                self.stages_directory,
                wal_directory=wal_dir if wal_dir.exists() else None,
                live_stage_ids=self._live_stage_ids,
            )
            handle_receipt: ReclaimResult = self._handles.reclaim_orphans()
            orphan_receipt = OrphanReclaimReceipt(
                reclaimed_stages=stage_receipt.reclaimed_stages,
                retained_stages=stage_receipt.retained_stages,
                reclaimed_handles=handle_receipt.reclaimed_handles,
                reclaimed_inodes=handle_receipt.reclaimed_inodes,
                expired_leases=handle_receipt.expired_leases,
                stage_ids_reclaimed=stage_receipt.stage_ids_reclaimed,
                stage_ids_retained=stage_receipt.stage_ids_retained,
                detail={
                    "stages": stage_receipt.detail,
                    "handles": handle_receipt.to_record(),
                },
            )
            self._trace.record(
                RecoveryTraceKind.ORPHAN_STAGE,
                success=True,
                phase=RecoveryPhase.RECLAIM_ORPHANS.value,
                detail=stage_receipt.to_record(),
            )
            self._trace.record(
                RecoveryTraceKind.ORPHAN_HANDLE,
                success=True,
                phase=RecoveryPhase.RECLAIM_ORPHANS.value,
                detail=handle_receipt.to_record(),
            )
            self._check_deadline(started, RecoveryPhase.RECLAIM_ORPHANS.value)

            # 5. Mark complete and enter READY — recovery before ready.
            self._phase(RecoveryPhase.MARK_COMPLETE, started=started)
            if self.lifecycle.state is not MountLifecycleState.RECOVERING:
                # If recovery_required is False and we skipped RECOVERING.
                if (
                    not self.recovery_required
                    and self.lifecycle.state is MountLifecycleState.INITIALIZING
                ):
                    if is_legal_mount_transition(
                        MountLifecycleState.INITIALIZING, MountLifecycleState.RECOVERING
                    ):
                        self._set_lifecycle(MountLifecycleState.RECOVERING)
            self._phase(RecoveryPhase.ENTER_READY, started=started)
            life = self._set_lifecycle(MountLifecycleState.READY)
            if not life.ready or not life.recovery_complete:
                raise RecoveryProtocolError(
                    "READY transition did not mark recovery_complete/ready",
                    detail=life.to_record(),
                )

            elapsed = _monotonic() - started
            receipt = MountRecoveryReceipt(
                receipt_id=receipt_id,
                disposition=RecoveryDisposition.READY,
                success=True,
                recovery_complete=True,
                ready=True,
                mount_id=self.mount_id,
                generation_id=self.generation_id,
                lifecycle_state=MountLifecycleState.READY,
                phases=tuple(phases),
                replayed=replayed,
                rolled_back=rolled_back,
                incomplete_resolved=incomplete_resolved,
                incomplete_policy=self.incomplete_policy,
                orphan_reclaim=orphan_receipt,
                lease_holder=lease_holder,
                elapsed_seconds=elapsed,
                timeout_seconds=self.recovery_timeout_seconds,
                message="recovery complete; mount ready",
                detail={
                    "second_recover": second,
                    "incomplete_policy": self.incomplete_policy.value,
                },
            )
            self._trace.record(
                RecoveryTraceKind.READY,
                success=True,
                phase=RecoveryPhase.ENTER_READY.value,
                detail=receipt.to_record(),
            )
            with self._lock:
                self._last_receipt = receipt
                self._receipts.append(receipt)
            return receipt

        except StateLeaseHeldError:
            raise  # already handled above
        except Exception as exc:  # noqa: BLE001
            elapsed = _monotonic() - started
            if isinstance(exc, RecoveryTimeoutError):
                disposition = RecoveryDisposition.TIMED_OUT
                error_code = RecoveryErrorCode.TIMEOUT.value
            elif isinstance(exc, MountRecoveryError):
                disposition = RecoveryDisposition.FAILED
                error_code = exc.code.value
            else:
                disposition = RecoveryDisposition.FAILED
                error_code = RecoveryErrorCode.INTERNAL.value

            # Best-effort FAILED transition (legal from RECOVERING / INITIALIZING).
            try:
                current = self.lifecycle.state
                if is_legal_mount_transition(current, MountLifecycleState.FAILED):
                    self._set_lifecycle(MountLifecycleState.FAILED)
            except Exception:  # noqa: BLE001
                pass

            self._phase(RecoveryPhase.FAILED)
            self._trace.record(
                RecoveryTraceKind.FAILED,
                success=False,
                phase=RecoveryPhase.FAILED.value,
                code=error_code,
                detail={"error": str(exc), "type": type(exc).__name__},
            )

            receipt = MountRecoveryReceipt(
                receipt_id=receipt_id,
                disposition=disposition,
                success=False,
                recovery_complete=False,
                ready=False,
                mount_id=self.mount_id,
                generation_id=self.generation_id,
                lifecycle_state=self.lifecycle.state,
                phases=tuple(phases),
                replayed=replayed,
                rolled_back=rolled_back,
                incomplete_resolved=incomplete_resolved,
                incomplete_policy=self.incomplete_policy,
                orphan_reclaim=orphan_receipt,
                lease_holder=lease_holder or self._lease.holder,
                elapsed_seconds=elapsed,
                timeout_seconds=self.recovery_timeout_seconds,
                error_code=error_code,
                message=str(exc),
                detail=(
                    exc.detail
                    if isinstance(exc, MountRecoveryError)
                    else {"error_type": type(exc).__name__}
                ),
            )
            try:
                evidence_path = str(
                    self.preserve_evidence(error=exc, receipt=receipt)
                )
            except Exception as evidence_exc:  # noqa: BLE001
                evidence_path = ""
                self._trace.record(
                    RecoveryTraceKind.EVIDENCE,
                    success=False,
                    code=RecoveryErrorCode.EVIDENCE.value,
                    detail={"error": str(evidence_exc)},
                )
            receipt = MountRecoveryReceipt(
                receipt_id=receipt.receipt_id,
                disposition=receipt.disposition,
                success=False,
                recovery_complete=False,
                ready=False,
                mount_id=receipt.mount_id,
                generation_id=receipt.generation_id,
                lifecycle_state=receipt.lifecycle_state,
                phases=receipt.phases,
                replayed=receipt.replayed,
                rolled_back=receipt.rolled_back,
                incomplete_resolved=receipt.incomplete_resolved,
                incomplete_policy=receipt.incomplete_policy,
                orphan_reclaim=receipt.orphan_reclaim,
                lease_holder=receipt.lease_holder,
                elapsed_seconds=receipt.elapsed_seconds,
                timeout_seconds=receipt.timeout_seconds,
                error_code=receipt.error_code,
                message=receipt.message,
                evidence_path=evidence_path,
                detail=receipt.detail,
            )
            # Release lease on failure so a subsequent mount can recover.
            try:
                self._lease.release()
                self._phase(RecoveryPhase.RELEASE_LEASE)
            except Exception:  # noqa: BLE001
                pass
            with self._lock:
                self._last_receipt = receipt
                self._receipts.append(receipt)
            return receipt

    # -- readiness gate -----------------------------------------------------

    def assert_ready(self) -> None:
        """Fail closed if callers attempt work before recovery completes."""

        life = self.lifecycle
        if not life.ready or not life.recovery_complete:
            raise RecoveryProtocolError(
                "mount is not ready; recovery must complete before ready",
                detail=life.to_record(),
            )
        if life.state is not MountLifecycleState.READY:
            raise RecoveryProtocolError(
                "mount lifecycle is not READY",
                detail=life.to_record(),
            )

    def host_mount_lifecycle(self) -> HostMountLifecycle:
        """Return the current host lifecycle record (contract-compatible)."""

        return self.lifecycle

    # -- shutdown -----------------------------------------------------------

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
        try:
            self._lease.release()
        finally:
            if self._owns_mutations:
                self._mutations.close()

    def __enter__(self) -> "MountRecoveryCoordinator":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


# Plan aliases.
MountRecoveryFacade = MountRecoveryCoordinator


def build_mount_recovery_coordinator(
    state_directory: str | Path,
    **kwargs: Any,
) -> MountRecoveryCoordinator:
    """Factory for :class:`MountRecoveryCoordinator`."""

    return MountRecoveryCoordinator(state_directory, **kwargs)


def recovery_phases() -> tuple[str, ...]:
    return tuple(p.value for p in RecoveryPhase)


def incomplete_policies() -> tuple[str, ...]:
    return tuple(p.value for p in IncompleteTransactionPolicy)


def recovery_dispositions() -> tuple[str, ...]:
    return tuple(d.value for d in RecoveryDisposition)


__all__ = [
    "TASK_ID",
    "CONTRACT_VERSION",
    "SCHEMA_VERSION",
    "DEFAULT_RECOVERY_TIMEOUT_SECONDS",
    "DEFAULT_LEASE_TTL_SECONDS",
    "MountRecoveryCoordinator_V1",
    "StateLease_V1",
    "MountRecoveryReceipt_V1",
    "RecoveryPhase",
    "IncompleteTransactionPolicy",
    "RecoveryDisposition",
    "RecoveryErrorCode",
    "RecoveryTraceKind",
    "MountRecoveryError",
    "StateLeaseError",
    "StateLeaseHeldError",
    "RecoveryTimeoutError",
    "RecoveryLifecycleError",
    "RecoveryProtocolError",
    "StateLeaseHolder",
    "StateLease",
    "OrphanReclaimReceipt",
    "MountRecoveryReceipt",
    "RecoveryTraceEvent",
    "RecoveryTrace",
    "MountRecoveryCoordinator",
    "MountRecoveryFacade",
    "build_mount_recovery_coordinator",
    "write_stage",
    "stage_path_for",
    "reclaim_orphan_stages",
    "recovery_phases",
    "incomplete_policies",
    "recovery_dispositions",
]
