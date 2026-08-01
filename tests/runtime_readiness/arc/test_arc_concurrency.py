"""Concurrency and differential tests for the production ARC wrapper."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock
from time import monotonic

import pytest

from ipfs_kit_py.cache.arc.cache import AdaptiveReplacementCache
from ipfs_kit_py.cache.arc.concurrency import (
    CacheFillCancelled,
    CacheFillError,
    FillStatus,
    SingleFlightARC,
)
from ipfs_kit_py.cache.arc.contracts import ARCConfig, ARCOperation, ARCOperationKind
from ipfs_kit_py.cache.arc.reference import ARCReferenceModel, minimal_trace_strategy


def _wait_until(predicate, *, timeout: float = 5.0) -> bool:
    """Wait without busy spinning for a thread to reach a tested boundary."""

    deadline = monotonic() + timeout
    sleeper = Event()
    while monotonic() < deadline:
        if predicate():
            return True
        sleeper.wait(0.001)
    return predicate()


def test_random_sequential_traces_match_the_reference_model() -> None:
    for seed in range(96):
        config, operations = minimal_trace_strategy(seed, max_ops=48)
        expected = ARCReferenceModel(config)
        actual = AdaptiveReplacementCache(config)

        assert actual.run_trace(operations) == expected.run_trace(operations)
        assert actual.snapshot() == expected.snapshot()
        assert actual.metrics() == expected.metrics()
        assert actual.trace == expected.trace
        actual.assert_invariants()


def test_updates_ghost_hits_and_evictions_keep_exact_byte_accounting() -> None:
    config = ARCConfig(capacity_bytes=10, max_live_entries=4, max_ghost_entries=2)
    operations = [
        ARCOperation(ARCOperationKind.PUT, "a", b"aaaa"),
        ARCOperation(ARCOperationKind.PUT, "b", b"bbbb"),
        ARCOperation(ARCOperationKind.GET, "a"),
        ARCOperation(ARCOperationKind.PUT, "c", b"cccc"),
        ARCOperation(ARCOperationKind.PUT, "b", b"bb"),
        ARCOperation(ARCOperationKind.PUT, "d", b"dddd"),
        ARCOperation(ARCOperationKind.PUT, "c", b"cccccc"),
        ARCOperation(ARCOperationKind.PUT, "e", b"eeee"),
    ]
    expected = ARCReferenceModel(config)
    actual = AdaptiveReplacementCache(config)

    assert actual.run_trace(operations) == expected.run_trace(operations)
    assert actual.snapshot() == expected.snapshot()
    assert actual.metrics() == expected.metrics()
    snapshot = actual.snapshot()
    assert snapshot.current_size == snapshot.t1_size + snapshot.t2_size
    assert snapshot.current_size <= snapshot.capacity_bytes
    assert snapshot.ghost_entries <= config.max_ghost_entries
    actual.assert_invariants()


def test_concurrent_operations_produce_a_replayable_linear_history() -> None:
    cache = AdaptiveReplacementCache(ARCConfig(capacity_bytes=24, max_live_entries=8))
    start = Event()

    # Each key is used once, so the cache trace identifies the exact operation
    # order chosen by the lock and can be replayed independently.
    operations = [
        ARCOperation(ARCOperationKind.PUT, f"key-{index}", bytes([index]) * 4)
        for index in range(8)
    ]

    def apply(operation: ARCOperation):
        start.wait()
        return operation, cache.apply(operation)

    with ThreadPoolExecutor(max_workers=len(operations)) as pool:
        futures = [pool.submit(apply, operation) for operation in operations]
        start.set()
        returned = [future.result(timeout=5) for future in futures]

    assert len(returned) == len(operations)
    by_key = {operation.key: operation for operation in operations}
    replay = ARCReferenceModel(cache.config)
    replayed = [
        replay.apply(by_key[record["outcome"]["key"]]) for record in cache.trace
    ]
    assert len(replayed) == len(operations)
    assert replay.snapshot() == cache.snapshot()
    assert replay.metrics() == cache.metrics()
    cache.assert_invariants()


def test_single_flight_runs_one_filler_and_returns_one_shared_result() -> None:
    cache = AdaptiveReplacementCache(ARCConfig(capacity_bytes=32))
    coordinator = SingleFlightARC(cache)
    entered = Event()
    release = Event()
    calls = 0
    calls_lock = Lock()

    def filler() -> bytes:
        nonlocal calls
        with calls_lock:
            calls += 1
        entered.set()
        assert release.wait(timeout=5)
        return b"payload"

    with ThreadPoolExecutor(max_workers=6) as pool:
        leader = pool.submit(coordinator.get_or_fill_result, "same", filler)
        assert entered.wait(timeout=5)
        waiters = [pool.submit(coordinator.get_or_fill_result, "same", filler) for _ in range(5)]
        assert _wait_until(lambda: coordinator.waiting_count == len(waiters))
        release.set()
        results = [leader.result(timeout=5)] + [future.result(timeout=5) for future in waiters]

    assert calls == 1
    assert {result.value for result in results} == {b"payload"}
    assert {result.status for result in results} <= {FillStatus.FILLED, FillStatus.HIT}
    assert cache.get("same") == b"payload"
    assert coordinator.inflight_count == 0


def test_failing_and_cancelled_fillers_wake_waiters_with_typed_results() -> None:
    cache = AdaptiveReplacementCache(ARCConfig(capacity_bytes=32))
    coordinator = SingleFlightARC(cache)
    entered = Event()
    release = Event()

    def failing_filler() -> bytes:
        entered.set()
        assert release.wait(timeout=5)
        raise ValueError("source unavailable")

    with ThreadPoolExecutor(max_workers=2) as pool:
        leader = pool.submit(coordinator.get_or_fill_result, "failed", failing_filler)
        assert entered.wait(timeout=5)
        waiter = pool.submit(coordinator.get_or_fill_result, "failed", failing_filler)
        assert _wait_until(lambda: coordinator.waiting_count == 1)
        release.set()
        results = [leader.result(timeout=5), waiter.result(timeout=5)]

    assert {result.status for result in results} == {FillStatus.FAILED}
    for result in results:
        with pytest.raises(CacheFillError) as error:
            result.unwrap()
        assert isinstance(error.value.__cause__, ValueError)

    entered.clear()
    release.clear()

    def cancelled_filler() -> bytes:
        entered.set()
        assert release.wait(timeout=5)
        raise asyncio.CancelledError("upstream task cancelled")

    with ThreadPoolExecutor(max_workers=2) as pool:
        leader = pool.submit(
            coordinator.get_or_fill_result, "filler-cancelled", cancelled_filler
        )
        assert entered.wait(timeout=5)
        waiter = pool.submit(
            coordinator.get_or_fill_result, "filler-cancelled", cancelled_filler
        )
        assert _wait_until(lambda: coordinator.waiting_count == 1)
        release.set()
        results = [leader.result(timeout=5), waiter.result(timeout=5)]

    assert {result.status for result in results} == {FillStatus.CANCELLED}
    for result in results:
        with pytest.raises(CacheFillCancelled):
            result.unwrap()

    entered.clear()
    release.clear()
    calls = 0
    calls_lock = Lock()

    def blocked_filler() -> bytes:
        nonlocal calls
        with calls_lock:
            calls += 1
        entered.set()
        assert release.wait(timeout=5)
        return b"late"

    with ThreadPoolExecutor(max_workers=2) as pool:
        leader = pool.submit(coordinator.get_or_fill_result, "cancelled", blocked_filler)
        assert entered.wait(timeout=5)
        waiter = pool.submit(coordinator.get_or_fill_result, "cancelled", blocked_filler)
        assert _wait_until(lambda: coordinator.waiting_count == 1)
        assert coordinator.cancel("cancelled")
        # A cancellation wakes current waiters immediately but the original
        # filler is still blocked.  A late caller must observe that same typed
        # result, not elect a second leader before the first one returns.
        late_waiter = pool.submit(
            coordinator.get_or_fill_result, "cancelled", blocked_filler
        )
        late_result = late_waiter.result(timeout=5)
        release.set()
        results = [leader.result(timeout=5), waiter.result(timeout=5), late_result]

    assert {result.status for result in results} == {FillStatus.CANCELLED}
    assert calls == 1
    for result in results:
        with pytest.raises(CacheFillCancelled):
            result.unwrap()
    assert cache.get("cancelled") is None
    assert coordinator.inflight_count == 0
