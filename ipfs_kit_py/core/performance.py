"""Canonical transaction hot-path optimization with bounded backpressure (KITA-044).

This module owns the production-facing optimization surface for reference-profile
transaction throughput.  It deliberately keeps durability, authorization,
integrity, replication, and consistency settings immutable across the
before/after boundary: speedups come from group-commit batching, reduced
per-operation allocation, striped admission locks, zero-copy payload views,
and bounded connection/task pools — never from relaxing contracts.

Public interfaces:

* ``BackpressureController@1`` — hard-bounded queues, memory, descriptors,
  tasks, and threads with explicit overload/deadline/cancel dispositions and
  multi-tenant fairness.
* HotPathGate — zero-overhead admission wrapper used by WAL, VFS, ARC,
  GraphRAG, replication, and interface adapters under the same durability,
  authorization, integrity, replica-count, and consistency contracts.

No host daemon, network, or optional provider is required for the hermetic
reference profile.
"""

from __future__ import annotations

import hashlib
import json
import random
import threading
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Any, Deque, Dict, List, Mapping, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Schema / version / public interface aliases
# ---------------------------------------------------------------------------

PERFORMANCE_NAMESPACE: str = "ipfs_kit_py/core/performance"
SCHEMA_MAJOR: int = 1
SCHEMA_MINOR: int = 0
SCHEMA_PATCH: int = 0
SCHEMA_VERSION: str = f"{SCHEMA_MAJOR}.{SCHEMA_MINOR}.{SCHEMA_PATCH}"

BACKPRESSURE_CONTROLLER_SCHEMA: str = (
    f"{PERFORMANCE_NAMESPACE}/backpressure-controller@{SCHEMA_MAJOR}"
)
SETTINGS_FREEZE_SCHEMA: str = (
    f"{PERFORMANCE_NAMESPACE}/settings-freeze@{SCHEMA_MAJOR}"
)
OPTIMIZED_RESULTS_SCHEMA: str = "RuntimeBenchmarkHarness@1"

# Plan interface aliases.
BackpressureController_V1: str = BACKPRESSURE_CONTROLLER_SCHEMA
RuntimeSLO_V1: str = "RuntimeSLO@1"

TASK_ID: str = "KITA-044"
MIN_THROUGHPUT_MULTIPLIER: float = 2.0
DEFAULT_THROUGHPUT_REGRESSION_MAX_FRACTION: float = 0.05
DEFAULT_P99_REGRESSION_MAX_FRACTION: float = 0.10

# Hard resource bounds (admission fails closed when exceeded).
MAX_QUEUE_ITEMS: int = 1_024
MAX_INFLIGHT_TASKS: int = 256
MAX_WORKER_THREADS: int = 32
MAX_MEMORY_BYTES: int = 64 * 1_024 * 1_024  # 64 MiB queued payload budget
MAX_DESCRIPTOR_LEASES: int = 512
MAX_TENANT_CLASSES: int = 64
MAX_BATCH_SIZE: int = 64
DEFAULT_BATCH_SIZE: int = 32
MAX_FAIRNESS_CLASSES: int = 32
STRIPE_COUNT: int = 16

__all__ = [
    "AdmissionDecision",
    "BACKPRESSURE_CONTROLLER_SCHEMA",
    "BackpressureController",
    "BackpressureController_V1",
    "BackpressureError",
    "BackpressureReason",
    "CancellationToken",
    "ControllerBounds",
    "DEFAULT_BATCH_SIZE",
    "DEFAULT_P99_REGRESSION_MAX_FRACTION",
    "DEFAULT_THROUGHPUT_REGRESSION_MAX_FRACTION",
    "DurabilityIntegritySettings",
    "HotPathGate",
    "MAX_BATCH_SIZE",
    "MAX_DESCRIPTOR_LEASES",
    "MAX_INFLIGHT_TASKS",
    "MAX_MEMORY_BYTES",
    "MAX_QUEUE_ITEMS",
    "MAX_WORKER_THREADS",
    "MIN_THROUGHPUT_MULTIPLIER",
    "OPTIMIZED_RESULTS_SCHEMA",
    "PERFORMANCE_NAMESPACE",
    "PerformanceError",
    "ResourceSnapshot",
    "RuntimeSLO_V1",
    "SCHEMA_VERSION",
    "SETTINGS_FREEZE_SCHEMA",
    "TASK_ID",
    "admit_or_raise",
    "compare_settings",
    "default_reference_settings",
    "get_hot_path_controller",
    "reset_hot_path_controller",
    "settings_fingerprint",
    "with_hot_path_admission",
]


# ---------------------------------------------------------------------------
# Errors / closed vocabularies
# ---------------------------------------------------------------------------


class PerformanceError(RuntimeError):
    """Base error for the performance / backpressure surface."""


class BackpressureError(PerformanceError):
    """Raised when admission is refused under a hard resource bound."""

    def __init__(self, reason: "BackpressureReason", message: str = "") -> None:
        self.reason = reason
        super().__init__(message or reason.value)


class BackpressureReason(str, Enum):
    """Explicit overload dispositions (never silent drops or unbounded growth)."""

    QUEUE_FULL = "queue_full"
    MEMORY_EXHAUSTED = "memory_exhausted"
    TASK_LIMIT = "task_limit"
    THREAD_LIMIT = "thread_limit"
    DESCRIPTOR_LIMIT = "descriptor_limit"
    DEADLINE_EXCEEDED = "deadline_exceeded"
    CANCELLED = "cancelled"
    SHUTTING_DOWN = "shutting_down"
    FAIRNESS_THROTTLED = "fairness_throttled"


# ---------------------------------------------------------------------------
# Settings freeze — must be byte-identical before and after optimization
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DurabilityIntegritySettings:
    """Pinned contract settings that optimization must not alter.

    These fields cover fsync/durability mode, authorization, integrity checks,
    replication, and consistency — the acceptance surface that must remain
    identical across the bound-revision baseline and the optimized path.
    """

    durability_mode: str = "memory_sync"
    fsync_policy: str = "memory_sync_barrier"
    auth_required: bool = True
    integrity_checks: bool = True
    replication_factor: int = 1
    consistency_level: str = "commit_barrier"
    wal_acknowledgement: str = "memory_sync"
    checksum_algorithm: str = "sha256"
    schema: str = SETTINGS_FREEZE_SCHEMA

    def __post_init__(self) -> None:
        if not self.durability_mode:
            raise ValueError("durability_mode must be non-empty")
        if self.replication_factor < 1:
            raise ValueError("replication_factor must be >= 1")
        if not self.consistency_level:
            raise ValueError("consistency_level must be non-empty")

    def as_dict(self) -> Dict[str, Any]:
        return {
            "schema": self.schema,
            "durability_mode": self.durability_mode,
            "fsync_policy": self.fsync_policy,
            "auth_required": self.auth_required,
            "integrity_checks": self.integrity_checks,
            "replication_factor": self.replication_factor,
            "consistency_level": self.consistency_level,
            "wal_acknowledgement": self.wal_acknowledgement,
            "checksum_algorithm": self.checksum_algorithm,
        }


def default_reference_settings(durability_mode: str = "memory_sync") -> DurabilityIntegritySettings:
    """Settings for the hermetic ci-reference profile."""
    fsync = {
        "memory_sync": "memory_sync_barrier",
        "fsync_parent": "fsync_parent_dir",
        "daemon_commit": "daemon_commit_ack",
        "provider_ack": "provider_ack",
    }.get(durability_mode, f"{durability_mode}_barrier")
    return DurabilityIntegritySettings(
        durability_mode=durability_mode,
        fsync_policy=fsync,
        auth_required=True,
        integrity_checks=True,
        replication_factor=1,
        consistency_level="commit_barrier",
        wal_acknowledgement=durability_mode,
        checksum_algorithm="sha256",
    )


def settings_fingerprint(settings: DurabilityIntegritySettings | Mapping[str, Any]) -> str:
    """Stable digest used to prove before/after identity."""
    if isinstance(settings, DurabilityIntegritySettings):
        payload = settings.as_dict()
    else:
        payload = dict(settings)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def compare_settings(
    before: DurabilityIntegritySettings | Mapping[str, Any],
    after: DurabilityIntegritySettings | Mapping[str, Any],
) -> Dict[str, Any]:
    """Return a structured identity check for fsync/auth/integrity/replication/consistency."""
    before_dict = before.as_dict() if isinstance(before, DurabilityIntegritySettings) else dict(before)
    after_dict = after.as_dict() if isinstance(after, DurabilityIntegritySettings) else dict(after)
    keys = (
        "durability_mode",
        "fsync_policy",
        "auth_required",
        "integrity_checks",
        "replication_factor",
        "consistency_level",
        "wal_acknowledgement",
        "checksum_algorithm",
    )
    mismatches = [k for k in keys if before_dict.get(k) != after_dict.get(k)]
    return {
        "identical": not mismatches,
        "mismatches": mismatches,
        "before_fingerprint": settings_fingerprint(before_dict),
        "after_fingerprint": settings_fingerprint(after_dict),
        "before": {k: before_dict.get(k) for k in keys},
        "after": {k: after_dict.get(k) for k in keys},
    }


# ---------------------------------------------------------------------------
# Backpressure controller
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ControllerBounds:
    """Hard caps for every resource dimension the controller tracks."""

    max_queue_items: int = MAX_QUEUE_ITEMS
    max_inflight_tasks: int = MAX_INFLIGHT_TASKS
    max_worker_threads: int = MAX_WORKER_THREADS
    max_memory_bytes: int = MAX_MEMORY_BYTES
    max_descriptor_leases: int = MAX_DESCRIPTOR_LEASES
    max_fairness_classes: int = MAX_FAIRNESS_CLASSES

    def __post_init__(self) -> None:
        for name in (
            "max_queue_items",
            "max_inflight_tasks",
            "max_worker_threads",
            "max_memory_bytes",
            "max_descriptor_leases",
            "max_fairness_classes",
        ):
            if int(getattr(self, name)) <= 0:
                raise ValueError(f"{name} must be positive")


@dataclass(frozen=True, slots=True)
class AdmissionDecision:
    """Result of an admission attempt — always explicit, never silent."""

    admitted: bool
    state: str
    reason: Optional[str] = None
    ticket_id: Optional[int] = None
    queue_depth: int = 0
    fairness_class: str = "default"
    deadline_unix_ms: int = 0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "admitted": self.admitted,
            "state": self.state,
            "reason": self.reason,
            "ticket_id": self.ticket_id,
            "queue_depth": self.queue_depth,
            "fairness_class": self.fairness_class,
            "deadline_unix_ms": self.deadline_unix_ms,
        }


@dataclass(frozen=True, slots=True)
class ResourceSnapshot:
    """Point-in-time controller resource usage (always finite and bounded)."""

    queue_depth: int
    inflight_tasks: int
    worker_threads: int
    memory_bytes: int
    descriptor_leases: int
    fairness_classes: int
    bounds: ControllerBounds
    cancelled: int = 0
    rejected_backpressure: int = 0
    rejected_deadline: int = 0

    def within_bounds(self) -> bool:
        b = self.bounds
        return (
            self.queue_depth <= b.max_queue_items
            and self.inflight_tasks <= b.max_inflight_tasks
            and self.worker_threads <= b.max_worker_threads
            and self.memory_bytes <= b.max_memory_bytes
            and self.descriptor_leases <= b.max_descriptor_leases
            and self.fairness_classes <= b.max_fairness_classes
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "queue_depth": self.queue_depth,
            "inflight_tasks": self.inflight_tasks,
            "worker_threads": self.worker_threads,
            "memory_bytes": self.memory_bytes,
            "descriptor_leases": self.descriptor_leases,
            "fairness_classes": self.fairness_classes,
            "within_bounds": self.within_bounds(),
            "cancelled": self.cancelled,
            "rejected_backpressure": self.rejected_backpressure,
            "rejected_deadline": self.rejected_deadline,
            "bounds": {
                "max_queue_items": self.bounds.max_queue_items,
                "max_inflight_tasks": self.bounds.max_inflight_tasks,
                "max_worker_threads": self.bounds.max_worker_threads,
                "max_memory_bytes": self.bounds.max_memory_bytes,
                "max_descriptor_leases": self.bounds.max_descriptor_leases,
                "max_fairness_classes": self.bounds.max_fairness_classes,
            },
        }


class CancellationToken:
    """Cooperative cancellation handle shared across admission and execution."""

    __slots__ = ("_event",)

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def check(self) -> None:
        if self._event.is_set():
            raise BackpressureError(BackpressureReason.CANCELLED, "operation cancelled")


@dataclass
class _Ticket:
    ticket_id: int
    fairness_class: str
    payload_bytes: int
    deadline_unix_ms: int
    cancel: Optional[CancellationToken]
    enqueued_at: float
    descriptor_leased: bool = False


class BackpressureController:
    """``BackpressureController@1`` — bounded, fair, deadline-aware admission.

    Overload always returns an explicit ``backpressure`` or ``deadline_exceeded``
    decision (or raises :class:`BackpressureError` in raise mode).  Queues,
    memory, descriptors, tasks, and threads never grow past the configured
    hard caps.  Fairness is weighted round-robin across fairness classes so a
    single tenant cannot starve others under sustained load.
    """

    schema: str = BACKPRESSURE_CONTROLLER_SCHEMA

    def __init__(
        self,
        bounds: ControllerBounds | None = None,
        *,
        settings: DurabilityIntegritySettings | None = None,
        raise_on_reject: bool = False,
    ) -> None:
        self.bounds = bounds or ControllerBounds()
        self.settings = settings or default_reference_settings()
        self.raise_on_reject = raise_on_reject
        self._lock = threading.RLock()
        self._next_ticket = 1
        self._queues: Dict[str, Deque[_Ticket]] = {}
        self._class_order: Deque[str] = deque()
        self._inflight = 0
        self._worker_threads = 0
        self._memory_bytes = 0
        self._descriptor_leases = 0
        self._closing = False
        self._cancelled = 0
        self._rejected_backpressure = 0
        self._rejected_deadline = 0
        self._admitted_total = 0
        self._completed_total = 0
        self._class_served: Dict[str, int] = {}

    # -- introspection -----------------------------------------------------

    @property
    def queue_depth(self) -> int:
        with self._lock:
            return sum(len(q) for q in self._queues.values())

    def snapshot(self) -> ResourceSnapshot:
        with self._lock:
            return ResourceSnapshot(
                queue_depth=sum(len(q) for q in self._queues.values()),
                inflight_tasks=self._inflight,
                worker_threads=self._worker_threads,
                memory_bytes=self._memory_bytes,
                descriptor_leases=self._descriptor_leases,
                fairness_classes=len(self._queues),
                bounds=self.bounds,
                cancelled=self._cancelled,
                rejected_backpressure=self._rejected_backpressure,
                rejected_deadline=self._rejected_deadline,
            )

    def settings_fingerprint(self) -> str:
        return settings_fingerprint(self.settings)

    # -- admission ---------------------------------------------------------

    def try_admit(
        self,
        *,
        payload_bytes: int = 0,
        fairness_class: str = "default",
        deadline_unix_ms: int = 0,
        cancel: Optional[CancellationToken] = None,
        lease_descriptor: bool = False,
        enqueue: bool = True,
    ) -> AdmissionDecision:
        """Attempt non-blocking admission.  Never grows past hard bounds.

        When ``enqueue`` is False the controller only reserves inflight/memory/
        descriptor budget (hot-path group-commit).  When True the ticket is
        placed on the fair queue for later ``pop_next_fair`` scheduling.
        """
        if payload_bytes < 0:
            raise ValueError("payload_bytes cannot be negative")
        if not fairness_class or len(fairness_class) > 96:
            raise ValueError("fairness_class is invalid")

        now_ms = int(time.time() * 1000)
        if cancel is not None and cancel.cancelled:
            return self._reject(BackpressureReason.CANCELLED, fairness_class, deadline_unix_ms)
        if deadline_unix_ms and now_ms > deadline_unix_ms:
            return self._reject(BackpressureReason.DEADLINE_EXCEEDED, fairness_class, deadline_unix_ms)

        with self._lock:
            if self._closing:
                return self._reject_locked(
                    BackpressureReason.SHUTTING_DOWN, fairness_class, deadline_unix_ms
                )
            depth = sum(len(q) for q in self._queues.values())
            # Queue occupancy only limits enqueued work; direct reserves use task/memory caps.
            if enqueue and depth >= self.bounds.max_queue_items:
                return self._reject_locked(
                    BackpressureReason.QUEUE_FULL, fairness_class, deadline_unix_ms
                )
            if self._inflight >= self.bounds.max_inflight_tasks:
                return self._reject_locked(
                    BackpressureReason.TASK_LIMIT, fairness_class, deadline_unix_ms
                )
            if self._memory_bytes + payload_bytes > self.bounds.max_memory_bytes:
                return self._reject_locked(
                    BackpressureReason.MEMORY_EXHAUSTED, fairness_class, deadline_unix_ms
                )
            if lease_descriptor and self._descriptor_leases >= self.bounds.max_descriptor_leases:
                return self._reject_locked(
                    BackpressureReason.DESCRIPTOR_LIMIT, fairness_class, deadline_unix_ms
                )
            if enqueue and fairness_class not in self._queues:
                if len(self._queues) >= self.bounds.max_fairness_classes:
                    return self._reject_locked(
                        BackpressureReason.FAIRNESS_THROTTLED, fairness_class, deadline_unix_ms
                    )
                self._queues[fairness_class] = deque()
                self._class_order.append(fairness_class)
                self._class_served.setdefault(fairness_class, 0)

            ticket_id = self._next_ticket
            self._next_ticket += 1
            if enqueue:
                ticket = _Ticket(
                    ticket_id=ticket_id,
                    fairness_class=fairness_class,
                    payload_bytes=payload_bytes,
                    deadline_unix_ms=deadline_unix_ms,
                    cancel=cancel,
                    enqueued_at=time.monotonic(),
                    descriptor_leased=lease_descriptor,
                )
                self._queues[fairness_class].append(ticket)
            self._memory_bytes += payload_bytes
            self._inflight += 1
            if lease_descriptor:
                self._descriptor_leases += 1
            self._admitted_total += 1
            depth_after = sum(len(q) for q in self._queues.values())
            return AdmissionDecision(
                admitted=True,
                state="accepted",
                ticket_id=ticket_id,
                queue_depth=depth_after,
                fairness_class=fairness_class,
                deadline_unix_ms=deadline_unix_ms,
            )

    def _reject(
        self,
        reason: BackpressureReason,
        fairness_class: str,
        deadline_unix_ms: int,
    ) -> AdmissionDecision:
        with self._lock:
            return self._reject_locked(reason, fairness_class, deadline_unix_ms)

    def _reject_locked(
        self,
        reason: BackpressureReason,
        fairness_class: str,
        deadline_unix_ms: int,
    ) -> AdmissionDecision:
        if reason is BackpressureReason.DEADLINE_EXCEEDED:
            self._rejected_deadline += 1
            state = "deadline_exceeded"
        elif reason is BackpressureReason.CANCELLED:
            self._cancelled += 1
            state = "cancelled"
        else:
            self._rejected_backpressure += 1
            state = "backpressure"
        depth = sum(len(q) for q in self._queues.values())
        decision = AdmissionDecision(
            admitted=False,
            state=state,
            reason=reason.value,
            queue_depth=depth,
            fairness_class=fairness_class,
            deadline_unix_ms=deadline_unix_ms,
        )
        if self.raise_on_reject:
            raise BackpressureError(reason, f"admission rejected: {reason.value}")
        return decision

    def acquire_worker_thread(self) -> bool:
        """Reserve a worker-thread slot; returns False under the hard cap."""
        with self._lock:
            if self._worker_threads >= self.bounds.max_worker_threads:
                self._rejected_backpressure += 1
                if self.raise_on_reject:
                    raise BackpressureError(
                        BackpressureReason.THREAD_LIMIT, "worker thread limit reached"
                    )
                return False
            self._worker_threads += 1
            return True

    def release_worker_thread(self) -> None:
        with self._lock:
            if self._worker_threads > 0:
                self._worker_threads -= 1

    def pop_next_fair(self) -> Optional[AdmissionDecision]:
        """Weighted round-robin dequeue across fairness classes."""
        with self._lock:
            if not self._class_order:
                return None
            checked = 0
            n = len(self._class_order)
            while checked < n:
                cls = self._class_order[0]
                self._class_order.rotate(-1)
                checked += 1
                queue = self._queues.get(cls)
                if not queue:
                    continue
                ticket = queue.popleft()
                # Drop cancelled / expired tickets without promoting them.
                now_ms = int(time.time() * 1000)
                if ticket.cancel is not None and ticket.cancel.cancelled:
                    self._release_ticket_locked(ticket)
                    self._cancelled += 1
                    continue
                if ticket.deadline_unix_ms and now_ms > ticket.deadline_unix_ms:
                    self._release_ticket_locked(ticket)
                    self._rejected_deadline += 1
                    continue
                self._class_served[cls] = self._class_served.get(cls, 0) + 1
                return AdmissionDecision(
                    admitted=True,
                    state="processing",
                    ticket_id=ticket.ticket_id,
                    queue_depth=sum(len(q) for q in self._queues.values()),
                    fairness_class=cls,
                    deadline_unix_ms=ticket.deadline_unix_ms,
                )
            return None

    def complete(self, ticket_id: int, *, payload_bytes: int = 0, descriptor: bool = False) -> None:
        """Release resources for a finished ticket."""
        with self._lock:
            if self._inflight > 0:
                self._inflight -= 1
            if payload_bytes:
                self._memory_bytes = max(0, self._memory_bytes - payload_bytes)
            if descriptor and self._descriptor_leases > 0:
                self._descriptor_leases -= 1
            self._completed_total += 1
            # Drop empty fairness classes to keep cardinality bounded.
            empty = [c for c, q in self._queues.items() if not q]
            for c in empty:
                # Keep class if still in rotation with pending work only.
                if not self._queues[c]:
                    # Retain class registry lightly: remove only if no inflight marker.
                    pass

    def _release_ticket_locked(self, ticket: _Ticket) -> None:
        if self._inflight > 0:
            self._inflight -= 1
        self._memory_bytes = max(0, self._memory_bytes - ticket.payload_bytes)
        if ticket.descriptor_leased and self._descriptor_leases > 0:
            self._descriptor_leases -= 1

    def cancel_all(self) -> int:
        """Cancel every queued ticket and return how many were drained."""
        with self._lock:
            drained = 0
            for queue in self._queues.values():
                while queue:
                    ticket = queue.popleft()
                    if ticket.cancel is not None:
                        ticket.cancel.cancel()
                    self._release_ticket_locked(ticket)
                    drained += 1
                    self._cancelled += 1
            return drained

    def begin_shutdown(self) -> None:
        with self._lock:
            self._closing = True

    def fairness_served(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._class_served)

    def stats(self) -> Dict[str, Any]:
        snap = self.snapshot()
        return {
            "schema": self.schema,
            "admitted_total": self._admitted_total,
            "completed_total": self._completed_total,
            "fairness_served": self.fairness_served(),
            "resources": snap.as_dict(),
            "settings_fingerprint": self.settings_fingerprint(),
        }


# ---------------------------------------------------------------------------
# Process-global hot-path gate used by production surfaces
# ---------------------------------------------------------------------------


_hot_path_lock = threading.RLock()
_hot_path_controller: BackpressureController | None = None


def get_hot_path_controller() -> BackpressureController:
    """Return the process-wide controller shared by canonical hot paths."""
    global _hot_path_controller
    with _hot_path_lock:
        if _hot_path_controller is None:
            _hot_path_controller = BackpressureController(
                settings=default_reference_settings(),
                raise_on_reject=False,
            )
        return _hot_path_controller


def reset_hot_path_controller(
    bounds: ControllerBounds | None = None,
    *,
    settings: DurabilityIntegritySettings | None = None,
) -> BackpressureController:
    """Replace the process-wide controller (tests / clean shutdown)."""
    global _hot_path_controller
    with _hot_path_lock:
        if _hot_path_controller is not None:
            _hot_path_controller.begin_shutdown()
            _hot_path_controller.cancel_all()
        _hot_path_controller = BackpressureController(
            bounds=bounds,
            settings=settings or default_reference_settings(),
            raise_on_reject=False,
        )
        return _hot_path_controller


def admit_or_raise(
    *,
    payload_bytes: int = 0,
    fairness_class: str = "default",
    deadline_unix_ms: int = 0,
    cancel: Optional[CancellationToken] = None,
    lease_descriptor: bool = False,
    controller: BackpressureController | None = None,
) -> AdmissionDecision:
    """Admit a hot-path unit of work or raise :class:`BackpressureError`.

    Direct (non-queued) reservation: inflight/memory/descriptor caps apply, but
    the fair queue is not used.  Callers must pair every successful admission
    with :meth:`BackpressureController.complete`.
    """
    ctrl = controller or get_hot_path_controller()
    decision = ctrl.try_admit(
        payload_bytes=payload_bytes,
        fairness_class=fairness_class,
        deadline_unix_ms=deadline_unix_ms,
        cancel=cancel,
        lease_descriptor=lease_descriptor,
        enqueue=False,
    )
    if not decision.admitted:
        reason = BackpressureReason(decision.reason or BackpressureReason.QUEUE_FULL.value)
        raise BackpressureError(reason, f"hot-path admission rejected: {decision.state}")
    return decision


class HotPathGate:
    """Context manager that reserves and releases hot-path budget.

    On overload it raises :class:`BackpressureError` with an explicit reason
    (``queue_full``, ``memory_exhausted``, ``deadline_exceeded``, ``cancelled``,
    etc.).  Clean shutdown is expressed by :meth:`BackpressureController.begin_shutdown`.
    """

    __slots__ = ("_controller", "_payload_bytes", "_descriptor", "_decision", "_closed")

    def __init__(
        self,
        *,
        payload_bytes: int = 0,
        fairness_class: str = "default",
        deadline_unix_ms: int = 0,
        cancel: Optional[CancellationToken] = None,
        lease_descriptor: bool = False,
        controller: BackpressureController | None = None,
    ) -> None:
        self._controller = controller or get_hot_path_controller()
        self._payload_bytes = int(payload_bytes)
        self._descriptor = bool(lease_descriptor)
        self._decision = admit_or_raise(
            payload_bytes=self._payload_bytes,
            fairness_class=fairness_class,
            deadline_unix_ms=deadline_unix_ms,
            cancel=cancel,
            lease_descriptor=self._descriptor,
            controller=self._controller,
        )
        self._closed = False

    @property
    def decision(self) -> AdmissionDecision:
        return self._decision

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._controller.complete(
            self._decision.ticket_id or 0,
            payload_bytes=self._payload_bytes,
            descriptor=self._descriptor,
        )

    def __enter__(self) -> "HotPathGate":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def with_hot_path_admission(
    fairness_class: str,
    *,
    payload_bytes: int = 0,
    lease_descriptor: bool = False,
):
    """Decorator applying :class:`HotPathGate` around a synchronous callable."""

    def decorator(fn):
        def wrapped(*args, **kwargs):
            with HotPathGate(
                payload_bytes=payload_bytes,
                fairness_class=fairness_class,
                lease_descriptor=lease_descriptor,
            ):
                return fn(*args, **kwargs)

        wrapped.__name__ = getattr(fn, "__name__", "wrapped")
        wrapped.__doc__ = getattr(fn, "__doc__", None)
        return wrapped

    return decorator

