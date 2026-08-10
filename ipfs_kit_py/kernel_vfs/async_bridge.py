"""Bounded async bridge for synchronous fusepy callbacks (KVFS-210).

Fusepy (and the WinFsp FUSE-compat path) deliver host callbacks on ordinary
worker threads.  Canonical VFS services may be async.  This module owns the
**single** sync→async seam between those worlds:

* exactly **one owner thread** runs **one** asyncio event loop for the life of
  the bridge (no per-call ``asyncio.run`` / ``new_event_loop``);
* concurrent synchronous callers submit awaitables to that loop and block for
  a result, deadline, cancellation, or typed refusal;
* admission is **bounded** (inflight + waiter queue) so FUSE storms apply
  backpressure instead of unbounded task growth;
* calls re-entering from the owner thread are **rejected** (deadlock-safe);
* exceptions and ``contextvars`` context from the caller are preserved across
  the thread boundary;
* ``close()`` is deterministic: refuse new work, cancel inflight tasks, stop
  the loop, join the owner thread, and leave **no orphan tasks or threads**.

Importing this module is inert: no loop, thread, fusepy, or network I/O.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import contextvars
import enum
import threading
import time
import uuid
import weakref
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any, ClassVar, Final, Generic, TypeVar, Union

# ---------------------------------------------------------------------------
# Schema / version / bounds
# ---------------------------------------------------------------------------

TASK_ID: Final[str] = "KVFS-210"
CONTRACT_VERSION: Final[int] = 1
SCHEMA_MAJOR: Final[int] = 1
SCHEMA_MINOR: Final[int] = 0
SCHEMA_PATCH: Final[int] = 0
SCHEMA_VERSION: Final[str] = f"{SCHEMA_MAJOR}.{SCHEMA_MINOR}.{SCHEMA_PATCH}"

ASYNC_BRIDGE_NAMESPACE: Final[str] = "ipfs_kit_py/kernel_vfs/async_bridge"

ASYNC_BRIDGE_SCHEMA: Final[str] = (
    f"{ASYNC_BRIDGE_NAMESPACE}/async-bridge@{SCHEMA_MAJOR}"
)
ASYNC_BRIDGE_CALL_SCHEMA: Final[str] = (
    f"{ASYNC_BRIDGE_NAMESPACE}/async-bridge-call@{SCHEMA_MAJOR}"
)
ASYNC_BRIDGE_STATS_SCHEMA: Final[str] = (
    f"{ASYNC_BRIDGE_NAMESPACE}/async-bridge-stats@{SCHEMA_MAJOR}"
)

# Public interface aliases.
AsyncBridge_V1: Final[str] = ASYNC_BRIDGE_SCHEMA
BoundedAsyncBridge_V1: Final[str] = ASYNC_BRIDGE_SCHEMA

DEFAULT_MAX_INFLIGHT: Final[int] = 64
DEFAULT_MAX_QUEUE_DEPTH: Final[int] = 128
DEFAULT_DEADLINE_S: Final[float] = 30.0
DEFAULT_CLOSE_TIMEOUT_S: Final[float] = 10.0
DEFAULT_START_TIMEOUT_S: Final[float] = 5.0
DEFAULT_THREAD_NAME: Final[str] = "kvfs-async-bridge"

MAX_INFLIGHT_HARD: Final[int] = 4_096
MAX_QUEUE_DEPTH_HARD: Final[int] = 8_192
MAX_DEADLINE_S: Final[float] = 3_600.0
MAX_CLOSE_TIMEOUT_S: Final[float] = 120.0

T = TypeVar("T")
_CoroLike = Union[Coroutine[Any, Any, T], Awaitable[T]]


# ---------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------


class BridgeState(str, enum.Enum):
    """Lifecycle of the owner loop."""

    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    CLOSING = "closing"
    CLOSED = "closed"


class BridgeErrorCode(str, enum.Enum):
    """Typed refusal / failure codes for bridge operations."""

    NOT_STARTED = "not_started"
    CLOSED = "closed"
    CLOSING = "closing"
    DEADLINE = "deadline"
    CANCELLED = "cancelled"
    BACKPRESSURE = "backpressure"
    REENTRANT = "reentrant"
    INVALID_ARGUMENT = "invalid_argument"
    START_FAILED = "start_failed"
    CLOSE_TIMEOUT = "close_timeout"
    INTERNAL = "internal"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class AsyncBridgeError(Exception):
    """Base error for the sync/async bridge."""

    def __init__(
        self,
        message: str,
        *,
        code: BridgeErrorCode = BridgeErrorCode.INTERNAL,
        call_id: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.call_id = call_id
        self.detail = dict(detail or {})

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": f"{ASYNC_BRIDGE_NAMESPACE}/error@{SCHEMA_MAJOR}",
            "message": self.message,
            "code": self.code.value,
            "call_id": self.call_id,
            "detail": dict(self.detail),
        }


class AsyncBridgeNotStartedError(AsyncBridgeError):
    def __init__(self, message: str = "async bridge is not started", **kw: Any) -> None:
        kw.setdefault("code", BridgeErrorCode.NOT_STARTED)
        super().__init__(message, **kw)


class AsyncBridgeClosedError(AsyncBridgeError):
    def __init__(self, message: str = "async bridge is closed", **kw: Any) -> None:
        kw.setdefault("code", BridgeErrorCode.CLOSED)
        super().__init__(message, **kw)


class AsyncBridgeDeadlineError(AsyncBridgeError):
    def __init__(
        self,
        message: str = "async bridge call exceeded deadline",
        **kw: Any,
    ) -> None:
        kw.setdefault("code", BridgeErrorCode.DEADLINE)
        super().__init__(message, **kw)


class AsyncBridgeCancelledError(AsyncBridgeError):
    def __init__(
        self,
        message: str = "async bridge call was cancelled",
        **kw: Any,
    ) -> None:
        kw.setdefault("code", BridgeErrorCode.CANCELLED)
        super().__init__(message, **kw)


class AsyncBridgeBackpressureError(AsyncBridgeError):
    def __init__(
        self,
        message: str = "async bridge admission bound exceeded",
        **kw: Any,
    ) -> None:
        kw.setdefault("code", BridgeErrorCode.BACKPRESSURE)
        super().__init__(message, **kw)


class AsyncBridgeReentrantError(AsyncBridgeError):
    def __init__(
        self,
        message: str = "reentrant async bridge call from owner loop rejected",
        **kw: Any,
    ) -> None:
        kw.setdefault("code", BridgeErrorCode.REENTRANT)
        super().__init__(message, **kw)


# ---------------------------------------------------------------------------
# Call bookkeeping
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class BridgeCallRecord:
    """Observability record for one bridged call."""

    SCHEMA: ClassVar[str] = ASYNC_BRIDGE_CALL_SCHEMA

    call_id: str
    submitted_at_s: float
    started_at_s: float | None = None
    finished_at_s: float | None = None
    deadline_s: float | None = None
    cancelled: bool = False
    deadline_exceeded: bool = False
    error_code: str | None = None
    error_type: str | None = None

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "call_id": self.call_id,
            "submitted_at_s": self.submitted_at_s,
            "started_at_s": self.started_at_s,
            "finished_at_s": self.finished_at_s,
            "deadline_s": self.deadline_s,
            "cancelled": self.cancelled,
            "deadline_exceeded": self.deadline_exceeded,
            "error_code": self.error_code,
            "error_type": self.error_type,
        }


@dataclass
class _PendingCall(Generic[T]):
    """Internal handle for one in-flight bridged call."""

    call_id: str
    coro: _CoroLike[T]
    context: contextvars.Context
    deadline_s: float | None
    cancel_event: threading.Event | None
    result_future: concurrent.futures.Future[T] = field(
        default_factory=concurrent.futures.Future
    )
    task: asyncio.Task[Any] | None = None
    record: BridgeCallRecord = field(default=None)  # type: ignore[assignment]
    admitted: bool = False
    # True once ``call_soon_threadsafe`` has queued the owner-loop callback.
    # After that, only the owner loop may close/await the coroutine.
    submitted_to_loop: bool = False

    def __post_init__(self) -> None:
        if self.record is None:
            self.record = BridgeCallRecord(
                call_id=self.call_id,
                submitted_at_s=time.monotonic(),
                deadline_s=self.deadline_s,
            )


# ---------------------------------------------------------------------------
# Bridge implementation
# ---------------------------------------------------------------------------


class AsyncBridge:
    """One bounded owner loop serving concurrent synchronous callbacks.

    Typical fusepy usage::

        bridge = AsyncBridge()
        bridge.start()
        try:
            result = bridge.run(service.read(path, ...), deadline_s=5.0)
        finally:
            bridge.close()

    Thread-safety: ``run`` / ``cancel`` are safe from many caller threads.
    ``start`` / ``close`` are serialized and idempotent where specified.
    """

    SCHEMA: ClassVar[str] = ASYNC_BRIDGE_SCHEMA

    def __init__(
        self,
        *,
        max_inflight: int = DEFAULT_MAX_INFLIGHT,
        max_queue_depth: int = DEFAULT_MAX_QUEUE_DEPTH,
        default_deadline_s: float | None = DEFAULT_DEADLINE_S,
        close_timeout_s: float = DEFAULT_CLOSE_TIMEOUT_S,
        start_timeout_s: float = DEFAULT_START_TIMEOUT_S,
        thread_name: str = DEFAULT_THREAD_NAME,
        loop_factory: Callable[[], asyncio.AbstractEventLoop] | None = None,
    ) -> None:
        if not (1 <= int(max_inflight) <= MAX_INFLIGHT_HARD):
            raise AsyncBridgeError(
                f"max_inflight must be in [1, {MAX_INFLIGHT_HARD}]",
                code=BridgeErrorCode.INVALID_ARGUMENT,
                detail={"max_inflight": max_inflight},
            )
        if not (0 <= int(max_queue_depth) <= MAX_QUEUE_DEPTH_HARD):
            raise AsyncBridgeError(
                f"max_queue_depth must be in [0, {MAX_QUEUE_DEPTH_HARD}]",
                code=BridgeErrorCode.INVALID_ARGUMENT,
                detail={"max_queue_depth": max_queue_depth},
            )
        if default_deadline_s is not None:
            if not (0.0 < float(default_deadline_s) <= MAX_DEADLINE_S):
                raise AsyncBridgeError(
                    f"default_deadline_s must be in (0, {MAX_DEADLINE_S}]",
                    code=BridgeErrorCode.INVALID_ARGUMENT,
                    detail={"default_deadline_s": default_deadline_s},
                )
        if not (0.0 < float(close_timeout_s) <= MAX_CLOSE_TIMEOUT_S):
            raise AsyncBridgeError(
                f"close_timeout_s must be in (0, {MAX_CLOSE_TIMEOUT_S}]",
                code=BridgeErrorCode.INVALID_ARGUMENT,
                detail={"close_timeout_s": close_timeout_s},
            )
        if not (0.0 < float(start_timeout_s) <= MAX_CLOSE_TIMEOUT_S):
            raise AsyncBridgeError(
                f"start_timeout_s must be in (0, {MAX_CLOSE_TIMEOUT_S}]",
                code=BridgeErrorCode.INVALID_ARGUMENT,
                detail={"start_timeout_s": start_timeout_s},
            )

        self._max_inflight = int(max_inflight)
        self._max_queue_depth = int(max_queue_depth)
        self._default_deadline_s = (
            None if default_deadline_s is None else float(default_deadline_s)
        )
        self._close_timeout_s = float(close_timeout_s)
        self._start_timeout_s = float(start_timeout_s)
        self._thread_name = str(thread_name) or DEFAULT_THREAD_NAME
        self._loop_factory = loop_factory or asyncio.new_event_loop

        self._guard = threading.RLock()
        self._admit_cond = threading.Condition(self._guard)
        self._state = BridgeState.CREATED
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._owner_ident: int | None = None
        self._ready = threading.Event()
        self._start_error: BaseException | None = None

        self._inflight: dict[str, _PendingCall[Any]] = {}
        self._queued: list[str] = []  # call_ids waiting for admission
        self._tasks: set[asyncio.Task[Any]] = set()
        self._total_submitted = 0
        self._total_completed = 0
        self._total_failed = 0
        self._total_cancelled = 0
        self._total_deadline = 0
        self._total_rejected = 0
        self._loop_creations = 0  # must stay 1 for the bridge lifetime after start

        # Track live bridges for test / diagnostics (weak, never keeps alive).
        _LIVE_BRIDGES.add(self)

    # -- properties ---------------------------------------------------------

    @property
    def state(self) -> BridgeState:
        with self._guard:
            return self._state

    @property
    def is_running(self) -> bool:
        with self._guard:
            return self._state is BridgeState.RUNNING

    @property
    def is_closed(self) -> bool:
        with self._guard:
            return self._state is BridgeState.CLOSED

    @property
    def max_inflight(self) -> int:
        return self._max_inflight

    @property
    def max_queue_depth(self) -> int:
        return self._max_queue_depth

    @property
    def default_deadline_s(self) -> float | None:
        return self._default_deadline_s

    @property
    def inflight_count(self) -> int:
        with self._guard:
            return len(self._inflight)

    @property
    def queue_depth(self) -> int:
        with self._guard:
            return len(self._queued)

    @property
    def owner_thread_id(self) -> int | None:
        with self._guard:
            return self._owner_ident

    @property
    def loop(self) -> asyncio.AbstractEventLoop | None:
        """The single owner loop, or ``None`` when not running.

        Callers must not stop, close, or replace this loop.
        """
        with self._guard:
            return self._loop if self._state is BridgeState.RUNNING else None

    @property
    def loop_creation_count(self) -> int:
        """How many times this instance created an event loop (must be ≤ 1)."""
        with self._guard:
            return self._loop_creations

    def stats(self) -> dict[str, Any]:
        with self._guard:
            return {
                "schema": ASYNC_BRIDGE_STATS_SCHEMA,
                "state": self._state.value,
                "inflight": len(self._inflight),
                "queue_depth": len(self._queued),
                "max_inflight": self._max_inflight,
                "max_queue_depth": self._max_queue_depth,
                "total_submitted": self._total_submitted,
                "total_completed": self._total_completed,
                "total_failed": self._total_failed,
                "total_cancelled": self._total_cancelled,
                "total_deadline": self._total_deadline,
                "total_rejected": self._total_rejected,
                "loop_creations": self._loop_creations,
                "owner_thread_id": self._owner_ident,
                "thread_alive": bool(
                    self._thread is not None and self._thread.is_alive()
                ),
                "tracked_tasks": len(self._tasks),
            }

    # -- lifecycle ----------------------------------------------------------

    def start(self) -> "AsyncBridge":
        """Start the single owner thread and event loop.

        Idempotent while already ``RUNNING``.  Raises if ``CLOSED``/``CLOSING``.
        """
        with self._guard:
            if self._state is BridgeState.RUNNING:
                return self
            if self._state is BridgeState.STARTING:
                # Another thread is starting; wait outside for readiness.
                pass
            elif self._state in (BridgeState.CLOSING, BridgeState.CLOSED):
                raise AsyncBridgeClosedError(
                    "cannot start a closed async bridge",
                    code=BridgeErrorCode.CLOSED,
                )
            elif self._state is BridgeState.CREATED:
                self._state = BridgeState.STARTING
                self._ready.clear()
                self._start_error = None
                thread = threading.Thread(
                    target=self._owner_main,
                    name=self._thread_name,
                    daemon=False,
                )
                self._thread = thread
                thread.start()
            else:
                raise AsyncBridgeError(
                    f"cannot start from state {self._state.value}",
                    code=BridgeErrorCode.INTERNAL,
                )

        if not self._ready.wait(timeout=self._start_timeout_s):
            # Best-effort teardown if the owner never signalled ready.
            self._force_fail_start("owner loop did not become ready in time")
            raise AsyncBridgeError(
                "async bridge start timed out",
                code=BridgeErrorCode.START_FAILED,
                detail={"start_timeout_s": self._start_timeout_s},
            )

        with self._guard:
            start_error = self._start_error
            state = self._state
            thread = self._thread

        if start_error is not None:
            if thread is not None:
                thread.join(timeout=self._close_timeout_s)
            with self._guard:
                self._state = BridgeState.CLOSED
                self._thread = None
                self._loop = None
                self._owner_ident = None
            raise AsyncBridgeError(
                f"async bridge start failed: {start_error}",
                code=BridgeErrorCode.START_FAILED,
                detail={"cause_type": type(start_error).__name__},
            ) from start_error
        if state is not BridgeState.RUNNING:
            if thread is not None:
                thread.join(timeout=self._close_timeout_s)
            with self._guard:
                self._state = BridgeState.CLOSED
                self._thread = None
                self._loop = None
                self._owner_ident = None
            raise AsyncBridgeError(
                f"async bridge failed to reach RUNNING (state={state.value})",
                code=BridgeErrorCode.START_FAILED,
            )
        return self

    def close(self, *, timeout_s: float | None = None) -> dict[str, Any]:
        """Deterministically stop the owner loop and join the owner thread.

        * refuses new ``run`` calls;
        * cancels all inflight tasks;
        * wakes admission waiters;
        * stops the loop and joins the owner thread within ``timeout_s``.

        Idempotent: repeated ``close`` after success is a no-op that returns
        the terminal snapshot.
        """
        timeout = (
            self._close_timeout_s if timeout_s is None else float(timeout_s)
        )
        if timeout <= 0 or timeout > MAX_CLOSE_TIMEOUT_S:
            raise AsyncBridgeError(
                f"timeout_s must be in (0, {MAX_CLOSE_TIMEOUT_S}]",
                code=BridgeErrorCode.INVALID_ARGUMENT,
                detail={"timeout_s": timeout},
            )

        with self._admit_cond:
            if self._state is BridgeState.CLOSED:
                return self.stats()
            if self._state is BridgeState.CREATED:
                self._state = BridgeState.CLOSED
                return self.stats()
            if self._state is BridgeState.CLOSING:
                # Another closer is in progress; fall through to join.
                pass
            else:
                self._state = BridgeState.CLOSING
            # Fail waiters and mark pending calls cancelled.
            pending = list(self._inflight.values())
            self._queued.clear()
            self._admit_cond.notify_all()

        for call in pending:
            self._cancel_pending(call, reason="bridge_closing")

        loop: asyncio.AbstractEventLoop | None
        thread: threading.Thread | None
        with self._guard:
            loop = self._loop
            thread = self._thread

        if loop is not None and thread is not None and thread.is_alive():
            try:
                loop.call_soon_threadsafe(self._stop_loop_safe, loop)
            except RuntimeError:
                # Loop already closed / stopped.
                pass

        if thread is not None:
            thread.join(timeout=timeout)
            if thread.is_alive():
                raise AsyncBridgeError(
                    "async bridge close timed out waiting for owner thread",
                    code=BridgeErrorCode.CLOSE_TIMEOUT,
                    detail={"timeout_s": timeout, "thread_name": thread.name},
                )

        with self._admit_cond:
            # Drain any stragglers that completed during join.
            for call in list(self._inflight.values()):
                if not call.result_future.done():
                    self._fail_future(
                        call,
                        AsyncBridgeClosedError(
                            "async bridge closed before call completed",
                            call_id=call.call_id,
                        ),
                    )
                self._inflight.pop(call.call_id, None)
            self._tasks.clear()
            self._loop = None
            self._owner_ident = None
            self._thread = None
            self._state = BridgeState.CLOSED
            self._admit_cond.notify_all()
            return self.stats()

    def __enter__(self) -> "AsyncBridge":
        return self.start()

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    # -- call path ----------------------------------------------------------

    def run(
        self,
        coro: _CoroLike[T],
        *,
        deadline_s: float | None = ...,  # type: ignore[assignment]
        cancel_event: threading.Event | None = None,
        call_id: str | None = None,
    ) -> T:
        """Execute *coro* on the owner loop and return its result.

        Parameters
        ----------
        coro:
            Coroutine / awaitable produced by the caller.  Ownership transfers
            to the bridge; do not await it elsewhere.
        deadline_s:
            Absolute wall-time budget for this call.  ``None`` means no
            deadline.  Omitting the argument uses ``default_deadline_s``.
        cancel_event:
            Optional ``threading.Event``; when set, the call is cancelled.
        call_id:
            Optional stable id for diagnostics; a uuid is generated otherwise.
        """
        try:
            if deadline_s is ...:  # type: ignore[comparison-overlap]
                effective_deadline: float | None = self._default_deadline_s
            else:
                effective_deadline = deadline_s
            if effective_deadline is not None:
                effective_deadline = float(effective_deadline)
                if effective_deadline <= 0:
                    raise AsyncBridgeError(
                        "deadline_s must be positive when provided",
                        code=BridgeErrorCode.INVALID_ARGUMENT,
                        detail={"deadline_s": effective_deadline},
                    )
                if effective_deadline > MAX_DEADLINE_S:
                    raise AsyncBridgeError(
                        f"deadline_s must be <= {MAX_DEADLINE_S}",
                        code=BridgeErrorCode.INVALID_ARGUMENT,
                        detail={"deadline_s": effective_deadline},
                    )

            if not asyncio.iscoroutine(coro) and not hasattr(coro, "__await__"):
                raise AsyncBridgeError(
                    "coro must be a coroutine or awaitable",
                    code=BridgeErrorCode.INVALID_ARGUMENT,
                    detail={"type": type(coro).__name__},
                )

            cid = call_id or f"call:{uuid.uuid4().hex}"
            ctx = contextvars.copy_context()
            pending: _PendingCall[T] = _PendingCall(
                call_id=cid,
                coro=coro,
                context=ctx,
                deadline_s=effective_deadline,
                cancel_event=cancel_event,
            )

            self._admit(pending)
        except BaseException:
            # Validation / admission refused: never schedule; close the
            # coroutine so it is not left as an orphan "was never awaited".
            self._close_coro_sync(coro)
            raise
        try:
            self._schedule(pending)
            return self._wait_result(pending)
        finally:
            self._release(pending)

    def cancel(self, call_id: str, *, reason: str = "caller_cancel") -> bool:
        """Cancel one inflight call by id.  Returns whether it was found."""
        with self._guard:
            call = self._inflight.get(call_id)
        if call is None:
            return False
        self._cancel_pending(call, reason=reason)
        return True

    def cancel_all(self, *, reason: str = "cancel_all") -> int:
        """Cancel every inflight call.  Returns the number cancelled."""
        with self._guard:
            calls = list(self._inflight.values())
        for call in calls:
            self._cancel_pending(call, reason=reason)
        return len(calls)

    # -- admission / schedule / wait ----------------------------------------

    def _admit(self, pending: _PendingCall[Any]) -> None:
        """Block until an inflight slot is available or refuse with backpressure."""
        with self._admit_cond:
            if self._state is BridgeState.CLOSED:
                self._total_rejected += 1
                raise AsyncBridgeClosedError(call_id=pending.call_id)
            if self._state is BridgeState.CLOSING:
                self._total_rejected += 1
                raise AsyncBridgeClosedError(
                    "async bridge is closing",
                    code=BridgeErrorCode.CLOSING,
                    call_id=pending.call_id,
                )
            if self._state is not BridgeState.RUNNING:
                self._total_rejected += 1
                raise AsyncBridgeNotStartedError(call_id=pending.call_id)

            # Reentrancy: never block the owner thread on itself.
            if (
                self._owner_ident is not None
                and threading.get_ident() == self._owner_ident
            ):
                self._total_rejected += 1
                raise AsyncBridgeReentrantError(call_id=pending.call_id)

            # Fast path: free slot.
            if len(self._inflight) < self._max_inflight:
                self._inflight[pending.call_id] = pending
                pending.admitted = True
                self._total_submitted += 1
                return

            # Need to queue.
            if len(self._queued) >= self._max_queue_depth:
                self._total_rejected += 1
                raise AsyncBridgeBackpressureError(
                    f"async bridge queue exceeds max_queue_depth ({self._max_queue_depth})",
                    call_id=pending.call_id,
                    detail={
                        "bound": "queue",
                        "max_queue_depth": self._max_queue_depth,
                        "max_inflight": self._max_inflight,
                        "inflight": len(self._inflight),
                    },
                )

            self._queued.append(pending.call_id)
            # Wait for a slot, respecting the call deadline for admission too.
            deadline_mono: float | None = None
            if pending.deadline_s is not None:
                deadline_mono = time.monotonic() + pending.deadline_s

            try:
                while True:
                    if self._state is not BridgeState.RUNNING:
                        self._total_rejected += 1
                        raise AsyncBridgeClosedError(
                            "async bridge closed while queued",
                            call_id=pending.call_id,
                        )
                    if (
                        pending.cancel_event is not None
                        and pending.cancel_event.is_set()
                    ):
                        self._total_rejected += 1
                        self._total_cancelled += 1
                        raise AsyncBridgeCancelledError(
                            "async bridge call cancelled while queued",
                            call_id=pending.call_id,
                        )
                    if len(self._inflight) < self._max_inflight:
                        # Our turn if we are still the head-or-any queued id.
                        if pending.call_id in self._queued:
                            # Fairness: only admit when we are at the front.
                            if self._queued[0] != pending.call_id:
                                pass
                            else:
                                self._queued.pop(0)
                                self._inflight[pending.call_id] = pending
                                pending.admitted = True
                                self._total_submitted += 1
                                return
                        else:
                            # Removed by close/cancel.
                            self._total_rejected += 1
                            raise AsyncBridgeClosedError(
                                "async bridge call dropped from queue",
                                call_id=pending.call_id,
                            )

                    wait_s: float | None = None
                    if deadline_mono is not None:
                        wait_s = deadline_mono - time.monotonic()
                        if wait_s <= 0:
                            self._total_rejected += 1
                            self._total_deadline += 1
                            raise AsyncBridgeDeadlineError(
                                "async bridge admission exceeded deadline",
                                call_id=pending.call_id,
                                detail={"phase": "admission"},
                            )
                    # Also poll cancel_event with a short bound so we remain responsive.
                    if pending.cancel_event is not None:
                        poll = 0.05 if wait_s is None else min(0.05, wait_s)
                        self._admit_cond.wait(timeout=poll)
                    else:
                        self._admit_cond.wait(timeout=wait_s)
            finally:
                # Ensure we are not left on the queue if we raised.
                if not pending.admitted and pending.call_id in self._queued:
                    self._queued = [c for c in self._queued if c != pending.call_id]

    def _schedule(self, pending: _PendingCall[Any]) -> None:
        loop = self.loop
        if loop is None:
            raise AsyncBridgeClosedError(call_id=pending.call_id)

        def _on_loop() -> None:
            if pending.result_future.done():
                # Cancelled / closed before the owner ran the call: drop the
                # coroutine here so the caller-side ``_release`` does not race.
                self._close_coro_sync(pending.coro)
                return
            # Re-check bridge state on the owner thread.
            with self._guard:
                if self._state is not BridgeState.RUNNING:
                    self._fail_future(
                        pending,
                        AsyncBridgeClosedError(
                            "async bridge closed before schedule",
                            call_id=pending.call_id,
                        ),
                    )
                    self._close_coro_sync(pending.coro)
                    return
            pending.record.started_at_s = time.monotonic()
            # Python 3.11+: run the task under the caller's copied contextvars.
            task = loop.create_task(
                self._execute(pending), context=pending.context
            )
            pending.task = task
            with self._guard:
                self._tasks.add(task)

            def _done(t: asyncio.Task[Any]) -> None:
                with self._guard:
                    self._tasks.discard(t)
                # Consume exception to avoid "Task exception was never retrieved"
                # when the result future already carries it.
                try:
                    t.exception()
                except (asyncio.CancelledError, concurrent.futures.CancelledError):
                    pass
                except Exception:
                    pass

            task.add_done_callback(_done)

        try:
            pending.submitted_to_loop = True
            loop.call_soon_threadsafe(_on_loop)
        except RuntimeError as exc:
            pending.submitted_to_loop = False
            raise AsyncBridgeClosedError(
                "async bridge loop is not accepting work",
                call_id=pending.call_id,
            ) from exc

    async def _execute(self, pending: _PendingCall[Any]) -> None:
        """Owner-loop body: await the user coroutine under optional deadline."""
        if pending.result_future.done():
            # Already cancelled / closed from the outside.
            await self._close_coro_quietly(pending.coro)
            return

        # Cooperative cancel via threading.Event: poll as a sibling task.
        cancel_watcher: asyncio.Task[Any] | None = None
        try:
            if pending.cancel_event is not None:
                cancel_watcher = asyncio.create_task(
                    self._watch_cancel_event(pending)
                )

            if pending.deadline_s is not None:
                # Budget is measured from submission, not from schedule time.
                elapsed = time.monotonic() - pending.record.submitted_at_s
                remaining = pending.deadline_s - elapsed
                if remaining <= 0:
                    raise AsyncBridgeDeadlineError(
                        "async bridge call exceeded deadline before start",
                        call_id=pending.call_id,
                    )
                result = await asyncio.wait_for(
                    self._await_user(pending), timeout=remaining
                )
            else:
                result = await self._await_user(pending)

            if not pending.result_future.done():
                pending.result_future.set_result(result)
                pending.record.finished_at_s = time.monotonic()
                with self._guard:
                    self._total_completed += 1
        except asyncio.TimeoutError:
            pending.record.deadline_exceeded = True
            pending.record.error_code = BridgeErrorCode.DEADLINE.value
            pending.record.error_type = "AsyncBridgeDeadlineError"
            pending.record.finished_at_s = time.monotonic()
            with self._guard:
                self._total_deadline += 1
                self._total_failed += 1
            self._fail_future(
                pending,
                AsyncBridgeDeadlineError(
                    "async bridge call exceeded deadline",
                    call_id=pending.call_id,
                ),
            )
        except asyncio.CancelledError:
            pending.record.cancelled = True
            pending.record.error_code = BridgeErrorCode.CANCELLED.value
            pending.record.error_type = "AsyncBridgeCancelledError"
            pending.record.finished_at_s = time.monotonic()
            with self._guard:
                self._total_cancelled += 1
                self._total_failed += 1
            self._fail_future(
                pending,
                AsyncBridgeCancelledError(
                    "async bridge call was cancelled",
                    call_id=pending.call_id,
                ),
            )
            # Propagate so the task is marked cancelled cleanly.
            raise
        except AsyncBridgeError as exc:
            pending.record.error_code = exc.code.value
            pending.record.error_type = type(exc).__name__
            pending.record.finished_at_s = time.monotonic()
            with self._guard:
                self._total_failed += 1
            self._fail_future(pending, exc)
        except BaseException as exc:
            # Preserve the original exception type for the sync caller.
            pending.record.error_type = type(exc).__name__
            pending.record.error_code = BridgeErrorCode.INTERNAL.value
            pending.record.finished_at_s = time.monotonic()
            with self._guard:
                self._total_failed += 1
            self._fail_future(pending, exc)
        finally:
            if cancel_watcher is not None:
                cancel_watcher.cancel()
                try:
                    await cancel_watcher
                except (asyncio.CancelledError, Exception):
                    pass

    async def _await_user(self, pending: _PendingCall[Any]) -> Any:
        """Await the user awaitable (coroutine or general awaitable)."""
        coro = pending.coro
        if asyncio.iscoroutine(coro):
            return await coro
        return await coro  # type: ignore[misc]

    async def _watch_cancel_event(self, pending: _PendingCall[Any]) -> None:
        """Poll a threading.Event and cancel the call's task when set."""
        assert pending.cancel_event is not None
        while not pending.cancel_event.is_set():
            if pending.result_future.done():
                return
            await asyncio.sleep(0.01)
        task = pending.task
        if task is not None and not task.done():
            task.cancel()
        else:
            # We may be racing schedule; mark cancelled via result future.
            self._fail_future(
                pending,
                AsyncBridgeCancelledError(
                    "async bridge call was cancelled",
                    call_id=pending.call_id,
                ),
            )

    def _wait_result(self, pending: _PendingCall[T]) -> T:
        """Block the caller thread for the bridged result."""
        # Compute remaining budget for the blocking wait.
        timeout: float | None = None
        if pending.deadline_s is not None:
            elapsed = time.monotonic() - pending.record.submitted_at_s
            timeout = max(0.0, pending.deadline_s - elapsed)

        # Poll cancel_event while waiting so cancellation is prompt even if
        # the owner loop is busy.
        future = pending.result_future
        if pending.cancel_event is None and timeout is None:
            return self._result_from_future(pending, future, timeout=None)

        end = None if timeout is None else (time.monotonic() + timeout)
        while True:
            if pending.cancel_event is not None and pending.cancel_event.is_set():
                self._cancel_pending(pending, reason="cancel_event")
            remaining: float | None
            if end is None:
                remaining = 0.05 if pending.cancel_event is not None else None
            else:
                remaining = end - time.monotonic()
                if remaining <= 0:
                    # Prefer whatever already landed (owner-loop deadline,
                    # success race, or an earlier cancel_event).
                    if future.done():
                        return self._result_from_future(
                            pending, future, timeout=0
                        )
                    # Expire on the waiter side: cancel the owner task for
                    # cleanup, but always surface DEADLINE to the caller —
                    # never CancelledError from our own cleanup cancel.
                    pending.record.deadline_exceeded = True
                    pending.record.cancelled = True
                    task = pending.task
                    if task is not None and not task.done():
                        loop = self._loop
                        if loop is not None:
                            try:
                                loop.call_soon_threadsafe(task.cancel)
                            except RuntimeError:
                                pass
                    with self._guard:
                        self._total_deadline += 1
                        self._total_failed += 1
                    deadline_exc = AsyncBridgeDeadlineError(
                        "async bridge call exceeded deadline",
                        call_id=pending.call_id,
                    )
                    self._fail_future(pending, deadline_exc)
                    raise deadline_exc
                if pending.cancel_event is not None:
                    remaining = min(remaining, 0.05)
            try:
                return self._result_from_future(
                    pending, future, timeout=remaining
                )
            except concurrent.futures.TimeoutError:
                continue

    def _result_from_future(
        self,
        pending: _PendingCall[T],
        future: concurrent.futures.Future[T],
        *,
        timeout: float | None,
    ) -> T:
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.CancelledError as exc:
            raise AsyncBridgeCancelledError(
                "async bridge call was cancelled",
                call_id=pending.call_id,
            ) from exc
        except AsyncBridgeError:
            raise
        except Exception:
            # Original user exception — re-raise with its type and traceback.
            raise

    def _release(self, pending: _PendingCall[Any]) -> None:
        """Drop admission and wake a waiter."""
        with self._admit_cond:
            self._inflight.pop(pending.call_id, None)
            if pending.call_id in self._queued:
                self._queued = [c for c in self._queued if c != pending.call_id]
            self._admit_cond.notify_all()
        # Close the user coroutine only when the owner loop never received it.
        # If ``submitted_to_loop`` is set, the owner callback owns closure.
        if pending.task is None and not pending.submitted_to_loop:
            self._close_coro_sync(pending.coro)

    # -- cancellation helpers -----------------------------------------------

    def _cancel_pending(self, pending: _PendingCall[Any], *, reason: str) -> None:
        pending.record.cancelled = True
        task = pending.task
        if task is not None and not task.done():
            loop = self._loop
            if loop is not None:
                try:
                    loop.call_soon_threadsafe(task.cancel)
                except RuntimeError:
                    pass
        self._fail_future(
            pending,
            AsyncBridgeCancelledError(
                f"async bridge call was cancelled ({reason})",
                call_id=pending.call_id,
                detail={"reason": reason},
            ),
        )

    def _fail_future(
        self, pending: _PendingCall[Any], exc: BaseException
    ) -> None:
        if pending.result_future.done():
            return
        if isinstance(exc, AsyncBridgeError) and pending.record.error_code is None:
            pending.record.error_code = exc.code.value
            pending.record.error_type = type(exc).__name__
        if pending.record.finished_at_s is None:
            pending.record.finished_at_s = time.monotonic()
        pending.result_future.set_exception(exc)

    # -- owner thread -------------------------------------------------------

    def _owner_main(self) -> None:
        """Entry point for the single owner thread."""
        loop: asyncio.AbstractEventLoop | None = None
        try:
            loop = self._loop_factory()
            with self._guard:
                self._loop_creations += 1
                self._loop = loop
                self._owner_ident = threading.get_ident()
            asyncio.set_event_loop(loop)
            with self._guard:
                self._state = BridgeState.RUNNING
            self._ready.set()
            loop.run_forever()
        except BaseException as exc:  # noqa: BLE001 — surface via start()
            with self._guard:
                self._start_error = exc
                if self._state is BridgeState.STARTING:
                    self._state = BridgeState.CLOSED
            self._ready.set()
        finally:
            self._shutdown_loop(loop)
            with self._guard:
                if self._state is not BridgeState.CLOSED:
                    # close() may still be joining; mark terminal.
                    if self._state is BridgeState.CLOSING:
                        pass
                    self._loop = None
                    self._owner_ident = None

    def _shutdown_loop(self, loop: asyncio.AbstractEventLoop | None) -> None:
        if loop is None:
            return
        try:
            # Cancel all remaining tasks owned by this loop.
            try:
                pending = asyncio.all_tasks(loop)
            except RuntimeError:
                pending = set()
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
            loop.run_until_complete(loop.shutdown_asyncgens())
            try:
                loop.run_until_complete(loop.shutdown_default_executor())
            except (AttributeError, RuntimeError):
                pass
        finally:
            try:
                loop.close()
            except Exception:
                pass
            try:
                asyncio.set_event_loop(None)
            except Exception:
                pass

    @staticmethod
    def _stop_loop_safe(loop: asyncio.AbstractEventLoop) -> None:
        if loop.is_running():
            loop.stop()

    def _force_fail_start(self, message: str) -> None:
        with self._guard:
            self._start_error = RuntimeError(message)
            thread = self._thread
            loop = self._loop
        if loop is not None:
            try:
                loop.call_soon_threadsafe(self._stop_loop_safe, loop)
            except Exception:
                pass
        if thread is not None:
            thread.join(timeout=self._close_timeout_s)
        with self._guard:
            self._state = BridgeState.CLOSED
            self._loop = None
            self._thread = None
            self._owner_ident = None
            self._ready.set()

    @staticmethod
    async def _close_coro_quietly(coro: Any) -> None:
        if asyncio.iscoroutine(coro):
            coro.close()

    @staticmethod
    def _close_coro_sync(coro: Any) -> None:
        if asyncio.iscoroutine(coro):
            try:
                coro.close()
            except Exception:
                pass


# Back-compat / plan alias.
BoundedAsyncBridge = AsyncBridge

# Weak registry so tests can assert no orphan bridges hold threads.
_LIVE_BRIDGES: weakref.WeakSet[AsyncBridge] = weakref.WeakSet()


def live_bridge_count() -> int:
    """Number of live :class:`AsyncBridge` instances (diagnostic)."""
    return len(_LIVE_BRIDGES)


__all__ = [
    "TASK_ID",
    "CONTRACT_VERSION",
    "SCHEMA_VERSION",
    "SCHEMA_MAJOR",
    "SCHEMA_MINOR",
    "SCHEMA_PATCH",
    "ASYNC_BRIDGE_NAMESPACE",
    "ASYNC_BRIDGE_SCHEMA",
    "ASYNC_BRIDGE_CALL_SCHEMA",
    "ASYNC_BRIDGE_STATS_SCHEMA",
    "AsyncBridge_V1",
    "BoundedAsyncBridge_V1",
    "DEFAULT_MAX_INFLIGHT",
    "DEFAULT_MAX_QUEUE_DEPTH",
    "DEFAULT_DEADLINE_S",
    "DEFAULT_CLOSE_TIMEOUT_S",
    "DEFAULT_START_TIMEOUT_S",
    "DEFAULT_THREAD_NAME",
    "MAX_INFLIGHT_HARD",
    "MAX_QUEUE_DEPTH_HARD",
    "MAX_DEADLINE_S",
    "MAX_CLOSE_TIMEOUT_S",
    "BridgeState",
    "BridgeErrorCode",
    "AsyncBridgeError",
    "AsyncBridgeNotStartedError",
    "AsyncBridgeClosedError",
    "AsyncBridgeDeadlineError",
    "AsyncBridgeCancelledError",
    "AsyncBridgeBackpressureError",
    "AsyncBridgeReentrantError",
    "BridgeCallRecord",
    "AsyncBridge",
    "BoundedAsyncBridge",
    "live_bridge_count",
]
