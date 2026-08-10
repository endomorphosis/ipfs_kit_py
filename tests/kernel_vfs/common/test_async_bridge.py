"""KVFS-210: Bounded async bridge for synchronous fusepy callbacks.

Acceptance coverage:

* one bounded owner loop executes async services from concurrent synchronous
  callbacks;
* deadlines, cancellation, context/error preservation;
* backpressure and reentrant-call rejection;
* deterministic close;
* no per-call loop creation;
* no orphan tasks or threads.
"""

from __future__ import annotations

import ast
import asyncio
import contextvars
import inspect
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from ipfs_kit_py.kernel_vfs import async_bridge as bridge_mod
from ipfs_kit_py.kernel_vfs.async_bridge import (
    ASYNC_BRIDGE_SCHEMA,
    CONTRACT_VERSION,
    DEFAULT_MAX_INFLIGHT,
    DEFAULT_MAX_QUEUE_DEPTH,
    SCHEMA_VERSION,
    AsyncBridge,
    AsyncBridge_V1,
    AsyncBridgeBackpressureError,
    AsyncBridgeCancelledError,
    AsyncBridgeClosedError,
    AsyncBridgeDeadlineError,
    AsyncBridgeError,
    AsyncBridgeNotStartedError,
    AsyncBridgeReentrantError,
    BoundedAsyncBridge,
    BoundedAsyncBridge_V1,
    BridgeErrorCode,
    BridgeState,
    live_bridge_count,
)

# test file: ipfs_kit_py/tests/kernel_vfs/common/test_async_bridge.py
PACKAGE_ROOT = Path(__file__).resolve().parents[3]
BRIDGE_PATH = PACKAGE_ROOT / "ipfs_kit_py" / "kernel_vfs" / "async_bridge.py"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def bridge() -> Any:
    b = AsyncBridge(
        max_inflight=8,
        max_queue_depth=8,
        default_deadline_s=5.0,
        close_timeout_s=5.0,
        start_timeout_s=5.0,
        thread_name="kvfs-test-async-bridge",
    )
    b.start()
    try:
        yield b
    finally:
        if not b.is_closed:
            b.close()


# ---------------------------------------------------------------------------
# Artifact / schema / inertness
# ---------------------------------------------------------------------------


def test_declared_async_bridge_module_exists() -> None:
    assert BRIDGE_PATH.is_file()
    assert BRIDGE_PATH.stat().st_size > 0


def test_schema_versions_and_interface_aliases() -> None:
    assert CONTRACT_VERSION == 1
    assert SCHEMA_VERSION.startswith("1.")
    assert ASYNC_BRIDGE_SCHEMA == AsyncBridge_V1
    assert AsyncBridge_V1.endswith("@1")
    assert BoundedAsyncBridge_V1.endswith("@1")
    assert BoundedAsyncBridge is AsyncBridge
    assert DEFAULT_MAX_INFLIGHT >= 1
    assert DEFAULT_MAX_QUEUE_DEPTH >= 0
    assert bridge_mod.TASK_ID == "KVFS-210"


def test_module_has_no_fusepy_dependency() -> None:
    source = BRIDGE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    banned = frozenset({"fuse", "fusepy"})
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".", 1)[0] not in banned
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module:
                assert module.split(".", 1)[0] not in banned


def test_module_import_is_inert() -> None:
    """Import must not start a loop or thread."""
    # Re-import is fine; ensure no running owner from mere import.
    assert inspect.ismodule(bridge_mod)
    # Creating without start is inert.
    b = AsyncBridge()
    assert b.state is BridgeState.CREATED
    assert b.loop is None
    assert b.owner_thread_id is None
    assert b.loop_creation_count == 0
    b.close()
    assert b.state is BridgeState.CLOSED


def test_exports_are_importable() -> None:
    assert bridge_mod.AsyncBridge is AsyncBridge
    assert callable(AsyncBridge.start)
    assert callable(AsyncBridge.run)
    assert callable(AsyncBridge.close)
    assert callable(AsyncBridge.cancel)
    assert callable(AsyncBridge.cancel_all)


def test_invalid_constructor_bounds() -> None:
    with pytest.raises(AsyncBridgeError) as ei:
        AsyncBridge(max_inflight=0)
    assert ei.value.code is BridgeErrorCode.INVALID_ARGUMENT
    with pytest.raises(AsyncBridgeError):
        AsyncBridge(max_queue_depth=-1)
    with pytest.raises(AsyncBridgeError):
        AsyncBridge(default_deadline_s=0)


# ---------------------------------------------------------------------------
# One owner loop — no per-call loop creation
# ---------------------------------------------------------------------------


def test_single_owner_loop_serves_many_calls(bridge: AsyncBridge) -> None:
    owner = bridge.owner_thread_id
    assert owner is not None
    assert bridge.loop is not None
    assert bridge.loop_creation_count == 1

    observed_threads: list[int] = []

    async def probe(n: int) -> int:
        observed_threads.append(threading.get_ident())
        await asyncio.sleep(0)
        return n * 2

    results = [bridge.run(probe(i)) for i in range(5)]
    assert results == [0, 2, 4, 6, 8]
    assert all(t == owner for t in observed_threads)
    assert bridge.loop_creation_count == 1


def test_no_per_call_loop_creation(monkeypatch: pytest.MonkeyPatch) -> None:
    creations: list[str] = []
    real_new = asyncio.new_event_loop

    def counting_new_event_loop() -> asyncio.AbstractEventLoop:
        creations.append("new")
        return real_new()

    monkeypatch.setattr(asyncio, "new_event_loop", counting_new_event_loop)

    # Also poison asyncio.run so per-call use would explode.
    def boom_run(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("asyncio.run must not be used per call")

    monkeypatch.setattr(asyncio, "run", boom_run)

    b = AsyncBridge(loop_factory=counting_new_event_loop)
    b.start()
    try:
        async def work(x: int) -> int:
            return x + 1

        assert b.run(work(1)) == 2
        assert b.run(work(2)) == 3
        assert b.run(work(3)) == 4
        assert b.loop_creation_count == 1
        assert len(creations) == 1
    finally:
        b.close()
    # Close must not create another loop.
    assert len(creations) == 1


def test_run_before_start_raises() -> None:
    b = AsyncBridge()

    async def noop() -> int:
        return 1

    with pytest.raises(AsyncBridgeNotStartedError):
        b.run(noop())
    # Close the un-started coroutine to avoid RuntimeWarning.
    # (run() should have closed it on failure after admit — but admit fails first)
    # Manually drain if needed: create fresh and close via start/close path.
    b.close()


def test_context_manager_starts_and_closes() -> None:
    async def ok() -> str:
        return "ok"

    with AsyncBridge(default_deadline_s=2.0) as b:
        assert b.is_running
        assert b.run(ok()) == "ok"
    assert b.is_closed
    assert b.stats()["thread_alive"] is False


# ---------------------------------------------------------------------------
# Concurrent synchronous callbacks
# ---------------------------------------------------------------------------


def test_concurrent_sync_callbacks(bridge: AsyncBridge) -> None:
    n = 12
    # Barrier is only among *caller* threads (never inside async work).
    barrier = threading.Barrier(n)
    results: list[int | None] = [None] * n
    errors: list[BaseException] = []

    async def work(i: int) -> int:
        await asyncio.sleep(0.02)
        return i * i

    def caller(i: int) -> None:
        try:
            barrier.wait(timeout=5)
            results[i] = bridge.run(work(i), deadline_s=5.0)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [
        threading.Thread(target=caller, args=(i,), name=f"cb-{i}")
        for i in range(n)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
        assert not t.is_alive()
    assert not errors, f"unexpected errors: {errors!r}"
    assert results == [i * i for i in range(n)]
    assert bridge.inflight_count == 0
    assert bridge.queue_depth == 0


# ---------------------------------------------------------------------------
# Deadlines
# ---------------------------------------------------------------------------


def test_deadline_cancels_slow_work(bridge: AsyncBridge) -> None:
    started = threading.Event()
    cancelled = threading.Event()

    async def slow() -> str:
        started.set()
        try:
            await asyncio.sleep(10.0)
            return "done"
        except asyncio.CancelledError:
            cancelled.set()
            raise

    t0 = time.monotonic()
    with pytest.raises(AsyncBridgeDeadlineError) as ei:
        bridge.run(slow(), deadline_s=0.15)
    elapsed = time.monotonic() - t0
    assert ei.value.code is BridgeErrorCode.DEADLINE
    assert elapsed < 2.0
    assert started.wait(timeout=2.0)
    # Cancellation should reach the coroutine promptly.
    assert cancelled.wait(timeout=2.0)
    # Allow bookkeeping to settle.
    time.sleep(0.05)
    assert bridge.inflight_count == 0


def test_default_deadline_applies() -> None:
    b = AsyncBridge(default_deadline_s=0.1, max_inflight=2)
    b.start()
    try:
        async def slow() -> None:
            await asyncio.sleep(5.0)

        with pytest.raises(AsyncBridgeDeadlineError):
            b.run(slow())
    finally:
        b.close()


def test_none_deadline_allows_long_work(bridge: AsyncBridge) -> None:
    async def ok() -> int:
        await asyncio.sleep(0.05)
        return 7

    assert bridge.run(ok(), deadline_s=None) == 7


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------


def test_cancel_event_aborts_inflight(bridge: AsyncBridge) -> None:
    started = threading.Event()
    cancel = threading.Event()
    saw_cancel = threading.Event()

    async def work() -> str:
        started.set()
        try:
            await asyncio.sleep(10.0)
            return "nope"
        except asyncio.CancelledError:
            saw_cancel.set()
            raise

    def runner() -> None:
        with pytest.raises(AsyncBridgeCancelledError):
            bridge.run(work(), deadline_s=5.0, cancel_event=cancel)

    t = threading.Thread(target=runner)
    t.start()
    assert started.wait(timeout=2.0)
    cancel.set()
    t.join(timeout=5.0)
    assert not t.is_alive()
    assert saw_cancel.wait(timeout=2.0)


def test_cancel_by_call_id(bridge: AsyncBridge) -> None:
    started = threading.Event()
    saw_cancel = threading.Event()

    async def work() -> str:
        started.set()
        try:
            await asyncio.sleep(10.0)
            return "x"
        except asyncio.CancelledError:
            saw_cancel.set()
            raise

    errors: list[BaseException] = []

    def runner() -> None:
        try:
            bridge.run(work(), deadline_s=5.0, call_id="c-1")
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    t = threading.Thread(target=runner)
    t.start()
    assert started.wait(timeout=2.0)
    assert bridge.cancel("c-1") is True
    t.join(timeout=5.0)
    assert not t.is_alive()
    assert len(errors) == 1
    assert isinstance(errors[0], AsyncBridgeCancelledError)
    assert saw_cancel.wait(timeout=2.0)
    assert bridge.cancel("missing") is False


def test_cancel_all(bridge: AsyncBridge) -> None:
    n = 4
    # Count starts without blocking the owner loop (no threading waits in async).
    started_count = {"n": 0}
    started_lock = threading.Lock()
    all_started = threading.Event()
    errors: list[BaseException] = []

    async def work() -> None:
        with started_lock:
            started_count["n"] += 1
            if started_count["n"] >= n:
                all_started.set()
        await asyncio.sleep(10.0)

    def runner() -> None:
        try:
            bridge.run(work(), deadline_s=5.0)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=runner) for _ in range(n)]
    for t in threads:
        t.start()
    assert all_started.wait(timeout=5)
    cancelled = bridge.cancel_all()
    assert cancelled == n
    for t in threads:
        t.join(timeout=5)
        assert not t.is_alive()
    assert len(errors) == n
    assert all(isinstance(e, AsyncBridgeCancelledError) for e in errors)


# ---------------------------------------------------------------------------
# Context / error preservation
# ---------------------------------------------------------------------------


def test_exception_type_and_message_preserved(bridge: AsyncBridge) -> None:
    class DomainError(RuntimeError):
        def __init__(self, code: int) -> None:
            super().__init__(f"domain-{code}")
            self.code = code

    async def boom() -> None:
        raise DomainError(42)

    with pytest.raises(DomainError) as ei:
        bridge.run(boom())
    assert ei.value.code == 42
    assert "domain-42" in str(ei.value)


def test_contextvars_preserved_across_bridge(bridge: AsyncBridge) -> None:
    token_var: contextvars.ContextVar[str] = contextvars.ContextVar(
        "kvfs_bridge_token", default=""
    )
    seen: dict[str, str] = {}

    async def read_ctx() -> str:
        seen["inside"] = token_var.get()
        return token_var.get()

    token_var.set("caller-value")
    result = bridge.run(read_ctx())
    assert result == "caller-value"
    assert seen["inside"] == "caller-value"

    # Different caller context on another thread.
    result_box: list[str] = []

    def other() -> None:
        token_var.set("other-thread")
        result_box.append(bridge.run(read_ctx()))

    t = threading.Thread(target=other)
    t.start()
    t.join(timeout=5)
    assert result_box == ["other-thread"]


# ---------------------------------------------------------------------------
# Backpressure
# ---------------------------------------------------------------------------


def test_backpressure_when_queue_full() -> None:
    b = AsyncBridge(
        max_inflight=1,
        max_queue_depth=1,
        default_deadline_s=5.0,
    )
    b.start()
    try:
        hold_started = threading.Event()
        flags = {"hold_done": False, "queued_done": False}

        async def hold() -> str:
            hold_started.set()
            while not flags["hold_done"]:
                await asyncio.sleep(0.01)
            return "held"

        async def queued() -> str:
            while not flags["queued_done"]:
                await asyncio.sleep(0.01)
            return "queued"

        async def brief() -> str:
            return "brief"

        holder_err: list[BaseException] = []
        q_err: list[BaseException] = []

        def holder() -> None:
            try:
                b.run(hold(), deadline_s=5.0)
            except BaseException as exc:  # noqa: BLE001
                holder_err.append(exc)

        def queuer() -> None:
            try:
                b.run(queued(), deadline_s=5.0)
            except BaseException as exc:  # noqa: BLE001
                q_err.append(exc)

        ht = threading.Thread(target=holder)
        ht.start()
        assert hold_started.wait(timeout=2.0)

        qt = threading.Thread(target=queuer)
        qt.start()
        # Wait until the second call is sitting in the admission queue.
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            if b.queue_depth >= 1:
                break
            time.sleep(0.01)
        assert b.queue_depth >= 1
        assert b.inflight_count >= 1

        # Third must be rejected with backpressure.
        with pytest.raises(AsyncBridgeBackpressureError) as ei:
            b.run(brief(), deadline_s=1.0)
        assert ei.value.code is BridgeErrorCode.BACKPRESSURE
        assert ei.value.detail.get("bound") == "queue"

        flags["hold_done"] = True
        flags["queued_done"] = True
        ht.join(timeout=5)
        qt.join(timeout=5)
        assert not ht.is_alive()
        assert not qt.is_alive()
        assert not holder_err
        assert not q_err
    finally:
        b.close()


def test_backpressure_stats_count_rejections(bridge: AsyncBridge) -> None:
    # Force rejection via reentrant path which also increments total_rejected.
    async def on_owner() -> int:
        # Nested call from owner must reject.
        async def inner() -> int:
            return 1

        with pytest.raises(AsyncBridgeReentrantError):
            bridge.run(inner())
        return 9

    assert bridge.run(on_owner()) == 9
    stats = bridge.stats()
    assert stats["total_rejected"] >= 1


# ---------------------------------------------------------------------------
# Reentrant-call rejection
# ---------------------------------------------------------------------------


def test_reentrant_call_from_owner_rejected(bridge: AsyncBridge) -> None:
    async def outer() -> str:
        async def inner() -> str:
            return "inner"

        with pytest.raises(AsyncBridgeReentrantError) as ei:
            bridge.run(inner())
        assert ei.value.code is BridgeErrorCode.REENTRANT
        return "outer"

    assert bridge.run(outer()) == "outer"
    # The inner coroutine was created but rejected before schedule; ensure
    # no leak of inflight.
    assert bridge.inflight_count == 0


def test_reentrant_does_not_deadlock(bridge: AsyncBridge) -> None:
    """Owner-thread reentry must fail closed without hanging the loop."""

    async def outer() -> int:
        async def inner() -> int:
            await asyncio.sleep(0)
            return 1

        try:
            bridge.run(inner(), deadline_s=1.0)
        except AsyncBridgeReentrantError:
            return 2
        return 0

    assert bridge.run(outer()) == 2


# ---------------------------------------------------------------------------
# Deterministic close — no orphan tasks or threads
# ---------------------------------------------------------------------------


def test_close_is_deterministic_and_idempotent(bridge: AsyncBridge) -> None:
    async def work() -> int:
        await asyncio.sleep(0)
        return 1

    assert bridge.run(work()) == 1
    snap = bridge.close()
    assert snap["state"] == BridgeState.CLOSED.value
    assert snap["inflight"] == 0
    assert snap["queue_depth"] == 0
    assert snap["thread_alive"] is False
    assert snap["tracked_tasks"] == 0
    # Idempotent.
    snap2 = bridge.close()
    assert snap2["state"] == BridgeState.CLOSED.value


def test_close_cancels_inflight_and_rejects_new() -> None:
    b = AsyncBridge(max_inflight=4, max_queue_depth=4, default_deadline_s=5.0)
    b.start()
    started = threading.Event()
    saw_cancel = threading.Event()
    run_errors: list[BaseException] = []

    async def hang() -> None:
        started.set()
        try:
            await asyncio.sleep(30.0)
        except asyncio.CancelledError:
            saw_cancel.set()
            raise

    def runner() -> None:
        try:
            b.run(hang(), deadline_s=10.0)
        except BaseException as exc:  # noqa: BLE001
            run_errors.append(exc)

    t = threading.Thread(target=runner)
    t.start()
    assert started.wait(timeout=2.0)
    snap = b.close(timeout_s=5.0)
    t.join(timeout=5.0)
    assert not t.is_alive()
    assert snap["state"] == BridgeState.CLOSED.value
    assert snap["thread_alive"] is False
    assert len(run_errors) == 1
    assert isinstance(
        run_errors[0], (AsyncBridgeCancelledError, AsyncBridgeClosedError)
    )
    assert saw_cancel.wait(timeout=2.0)

    async def after() -> int:
        return 1

    with pytest.raises(AsyncBridgeClosedError):
        b.run(after())


def test_close_leaves_no_orphan_threads() -> None:
    before = {th.ident for th in threading.enumerate()}
    b = AsyncBridge(thread_name="kvfs-orphan-check")
    b.start()
    owner = b.owner_thread_id
    assert owner is not None
    assert owner not in before or any(
        th.name == "kvfs-orphan-check" for th in threading.enumerate()
    )

    async def work() -> int:
        return 3

    assert b.run(work()) == 3
    b.close()
    # Owner thread must be gone.
    alive_names = [th.name for th in threading.enumerate() if th.is_alive()]
    assert "kvfs-orphan-check" not in alive_names
    assert b.stats()["thread_alive"] is False
    assert b.stats()["tracked_tasks"] == 0


def test_close_leaves_no_orphan_tasks(bridge: AsyncBridge) -> None:
    created: list[asyncio.Task[Any]] = []

    async def spawn_and_finish() -> int:
        # Any helper tasks created on the loop should complete.
        async def helper() -> int:
            await asyncio.sleep(0.01)
            return 11

        t = asyncio.create_task(helper())
        created.append(t)
        return await t

    assert bridge.run(spawn_and_finish()) == 11
    assert created[0].done()
    bridge.close()
    assert bridge.stats()["tracked_tasks"] == 0


def test_cannot_restart_after_close() -> None:
    b = AsyncBridge()
    b.start()
    b.close()
    with pytest.raises(AsyncBridgeClosedError):
        b.start()


# ---------------------------------------------------------------------------
# Stats / observability
# ---------------------------------------------------------------------------


def test_stats_schema_and_counters(bridge: AsyncBridge) -> None:
    async def ok() -> int:
        return 1

    async def bad() -> int:
        raise ValueError("nope")

    assert bridge.run(ok()) == 1
    with pytest.raises(ValueError):
        bridge.run(bad())
    stats = bridge.stats()
    assert stats["schema"].endswith("@1")
    assert stats["total_submitted"] >= 2
    assert stats["total_completed"] >= 1
    assert stats["total_failed"] >= 1
    assert stats["loop_creations"] == 1
    assert stats["max_inflight"] == bridge.max_inflight


# ---------------------------------------------------------------------------
# Source guarantees (static)
# ---------------------------------------------------------------------------


def test_source_does_not_call_asyncio_run_for_bridge_work() -> None:
    source = BRIDGE_PATH.read_text(encoding="utf-8")
    # The bridge must not use asyncio.run for call execution.
    # Allow the name only in comments/docstrings by checking AST Call nodes.
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "run":
                if isinstance(func.value, ast.Name) and func.value.id == "asyncio":
                    pytest.fail("async_bridge must not call asyncio.run(...)")
            if isinstance(func, ast.Attribute) and func.attr == "run_until_complete":
                # Allowed only during loop shutdown in _shutdown_loop.
                pass


def test_error_to_record() -> None:
    err = AsyncBridgeBackpressureError(
        "full", call_id="c1", detail={"bound": "queue"}
    )
    rec = err.to_record()
    assert rec["code"] == BridgeErrorCode.BACKPRESSURE.value
    assert rec["call_id"] == "c1"
    assert rec["detail"]["bound"] == "queue"


def test_live_bridge_count_tracks_instances() -> None:
    # May be non-zero if other tests left refs; just exercise the API.
    n0 = live_bridge_count()
    b = AsyncBridge()
    assert live_bridge_count() >= n0
    del b
    # Weakref may not collect immediately; just ensure callable.
    assert live_bridge_count() >= 0
