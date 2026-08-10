"""KVFS-400: Generation-bound range/chunk ARC keys and generation-aware single-flight.

Acceptance coverage:

* keys bind namespace, inode/content/version, generation, serializer, offset,
  and length;
* overlapping and exact-range policy is deterministic;
* concurrent misses single-flight only under equal generation;
* cancellation/error fan-out is bounded; and
* ARC byte and ghost invariants remain valid after range admissions.
"""

from __future__ import annotations

import asyncio
import ast
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event, Lock
from time import monotonic

import pytest

from ipfs_kit_py.cache.arc.cache import AdaptiveReplacementCache
from ipfs_kit_py.cache.arc.contracts import ARCConfig
from ipfs_kit_py.cache.arc.range_bindings import (
    CONTRACT_VERSION,
    MAX_INFLIGHT_FLIGHTS,
    MAX_RANGE_LENGTH,
    RANGE_BINDING_SCHEMA,
    RANGE_SINGLE_FLIGHT_SCHEMA,
    SCHEMA_VERSION,
    CacheFillCancelled,
    CacheFillError,
    FillStatus,
    GenerationAwareRangeSingleFlight,
    RangeBinding,
    RangeExtentError,
    RangeIdentityError,
    RangeLookupDisposition,
    RangeMatchPolicy,
    RangeRelation,
    classify_range_relation,
    ranges_overlap,
    resolve_range_lookup,
    single_flight_compatible,
)

# test file: .../tests/kernel_vfs/arc/test_range_bindings.py
PACKAGE_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = PACKAGE_ROOT / "ipfs_kit_py" / "cache" / "arc" / "range_bindings.py"


def _wait_until(predicate, *, timeout: float = 5.0) -> bool:
    deadline = monotonic() + timeout
    sleeper = Event()
    while monotonic() < deadline:
        if predicate():
            return True
        sleeper.wait(0.001)
    return predicate()


def _binding(
    *,
    namespace: str = "ns-a",
    content_id: str = "inode:42",
    version: str = "v1",
    generation: str = "g1",
    serializer: str = "bytes@1",
    offset: int = 0,
    length: int = 8,
    policy: str = "public",
) -> RangeBinding:
    return RangeBinding(
        namespace=namespace,
        content_id=content_id,
        version=version,
        generation=generation,
        serializer=serializer,
        offset=offset,
        length=length,
        policy=policy,
    )


# ---------------------------------------------------------------------------
# Artifact / schema
# ---------------------------------------------------------------------------


def test_declared_module_exists() -> None:
    assert MODULE_PATH.is_file()
    assert MODULE_PATH.stat().st_size > 0


def test_schema_versions_and_aliases() -> None:
    assert CONTRACT_VERSION == 1
    assert SCHEMA_VERSION.startswith("1.")
    assert RANGE_BINDING_SCHEMA.endswith("@1")
    assert RANGE_SINGLE_FLIGHT_SCHEMA.endswith("@1")
    assert MAX_RANGE_LENGTH == 16 * 1024 * 1024
    assert MAX_INFLIGHT_FLIGHTS == 256


def test_module_has_no_fusepy_dependency() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    banned = frozenset({"fuse", "fusepy"})
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in banned
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".")[0] not in banned


# ---------------------------------------------------------------------------
# Key binding dimensions
# ---------------------------------------------------------------------------


def test_keys_bind_namespace_inode_content_version_generation_serializer_offset_length() -> None:
    by_inode = RangeBinding.create(
        namespace="tenant-a",
        inode=7,
        version="cid-v1",
        generation="gen-3",
        serializer="raw@1",
        offset=4096,
        length=64,
        policy="authz-v2",
    )
    by_content = RangeBinding.create(
        namespace="tenant-a",
        content_id="QmContent",
        version="cid-v1",
        generation="gen-3",
        serializer="raw@1",
        offset=4096,
        length=64,
        policy="authz-v2",
    )

    assert by_inode.inode == "7"
    assert by_inode.content_id == "7"
    assert by_inode.namespace == "tenant-a"
    assert by_inode.version == "cid-v1"
    assert by_inode.generation == "gen-3"
    assert by_inode.serializer == "raw@1"
    assert by_inode.offset == 4096
    assert by_inode.length == 64
    assert by_inode.end == 4160

    # Every dimension participates in the cache key.
    base = _binding()
    variants = [
        base.__class__(**{**base.to_dict(), "namespace": "other-ns"}),
        base.__class__(**{**base.to_dict(), "content_id": "inode:99"}),
        base.__class__(**{**base.to_dict(), "version": "v2"}),
        base.__class__(**{**base.to_dict(), "generation": "g2"}),
        base.__class__(**{**base.to_dict(), "serializer": "cbor@1"}),
        base.__class__(**{**base.to_dict(), "offset": 1}),
        base.__class__(**{**base.to_dict(), "length": 7}),
        base.__class__(**{**base.to_dict(), "policy": "restricted"}),
    ]
    keys = {base.cache_key, *(item.cache_key for item in variants)}
    assert len(keys) == 1 + len(variants)
    assert base.cache_key.startswith("arc-range:")
    assert base.flight_key == base.cache_key
    assert by_inode.cache_key != by_content.cache_key


def test_binding_rejects_invalid_identity_and_extent() -> None:
    with pytest.raises(RangeIdentityError):
        RangeBinding.create(version="v", offset=0, length=1)
    with pytest.raises(RangeIdentityError):
        RangeBinding.create(
            content_id="a", inode=1, version="v", offset=0, length=1
        )
    with pytest.raises(RangeIdentityError):
        _binding(namespace="")
    with pytest.raises(RangeIdentityError):
        _binding(content_id="has space")
    with pytest.raises(RangeExtentError):
        _binding(offset=-1)
    with pytest.raises(RangeExtentError):
        _binding(length=0)
    with pytest.raises(RangeExtentError):
        _binding(length=MAX_RANGE_LENGTH + 1)
    with pytest.raises(RangeIdentityError):
        RangeBinding.from_dict({"namespace": "n"})


def test_cache_key_is_stable_and_round_trips_through_dict() -> None:
    first = _binding(offset=128, length=32)
    second = RangeBinding.from_dict(first.to_dict())
    assert first == second
    assert first.cache_key == second.cache_key
    again = _binding(offset=128, length=32)
    assert again.cache_key == first.cache_key


# ---------------------------------------------------------------------------
# Deterministic exact / overlapping policy
# ---------------------------------------------------------------------------


def test_exact_and_overlapping_policy_is_deterministic() -> None:
    exact_a = _binding(offset=100, length=50)
    exact_b = _binding(offset=100, length=50)
    overlap = _binding(offset=120, length=50)
    contains = _binding(offset=90, length=80)
    contained = _binding(offset=110, length=10)
    disjoint = _binding(offset=200, length=10)
    gen_skew = _binding(offset=100, length=50, generation="g2")
    ns_skew = _binding(offset=100, length=50, namespace="other")

    assert classify_range_relation(exact_a, exact_b) is RangeRelation.EXACT
    assert classify_range_relation(exact_a, overlap) is RangeRelation.OVERLAPS
    assert classify_range_relation(exact_a, contains) is RangeRelation.CONTAINED
    assert classify_range_relation(contains, exact_a) is RangeRelation.CONTAINS
    assert classify_range_relation(exact_a, contained) is RangeRelation.CONTAINS
    assert classify_range_relation(exact_a, disjoint) is RangeRelation.DISJOINT
    assert (
        classify_range_relation(exact_a, gen_skew) is RangeRelation.IDENTITY_MISMATCH
    )
    assert classify_range_relation(exact_a, ns_skew) is RangeRelation.IDENTITY_MISMATCH

    assert ranges_overlap(100, 50, 120, 50)
    assert not ranges_overlap(100, 50, 200, 10)
    assert single_flight_compatible(exact_a, exact_b)
    assert not single_flight_compatible(exact_a, overlap)
    assert not single_flight_compatible(exact_a, gen_skew)

    candidates = [overlap, contains, contained, disjoint, exact_b, gen_skew]
    decision = resolve_range_lookup(exact_a, candidates)
    assert decision.disposition is RangeLookupDisposition.EXACT_HIT
    assert decision.policy is RangeMatchPolicy.EXACT_ONLY
    assert decision.relation is RangeRelation.EXACT
    assert decision.matched == exact_b

    miss = resolve_range_lookup(exact_a, [overlap, contains, contained, disjoint])
    assert miss.disposition is RangeLookupDisposition.MISS
    assert miss.matched is None
    # First non-identity geometric relation is reported for diagnostics.
    assert miss.relation is RangeRelation.OVERLAPS

    # Candidate order must not change exact-hit correctness.
    reversed_decision = resolve_range_lookup(exact_a, list(reversed(candidates)))
    assert reversed_decision.disposition is RangeLookupDisposition.EXACT_HIT
    assert reversed_decision.matched == exact_b


# ---------------------------------------------------------------------------
# Generation-aware single-flight
# ---------------------------------------------------------------------------


def test_concurrent_misses_single_flight_only_under_equal_generation() -> None:
    cache = AdaptiveReplacementCache(ARCConfig(capacity_bytes=256))
    coordinator = GenerationAwareRangeSingleFlight(cache)
    same = _binding(generation="g1", offset=0, length=8)
    other_gen = same.with_generation("g2")

    same_entered = Event()
    same_release = Event()
    other_entered = Event()
    other_release = Event()
    same_calls = 0
    other_calls = 0
    lock = Lock()

    def same_filler() -> bytes:
        nonlocal same_calls
        with lock:
            same_calls += 1
        same_entered.set()
        assert same_release.wait(timeout=5)
        return b"same-gen"

    def other_filler() -> bytes:
        nonlocal other_calls
        with lock:
            other_calls += 1
        other_entered.set()
        assert other_release.wait(timeout=5)
        return b"next-gen"

    with ThreadPoolExecutor(max_workers=8) as pool:
        same_leader = pool.submit(coordinator.get_or_fill_result, same, same_filler)
        assert same_entered.wait(timeout=5)
        same_waiters = [
            pool.submit(coordinator.get_or_fill_result, same, same_filler)
            for _ in range(4)
        ]
        other_leader = pool.submit(
            coordinator.get_or_fill_result, other_gen, other_filler
        )
        assert other_entered.wait(timeout=5)
        other_waiters = [
            pool.submit(coordinator.get_or_fill_result, other_gen, other_filler)
            for _ in range(2)
        ]
        assert _wait_until(lambda: coordinator.waiting_count >= 6)
        # Two independent flights: equal-generation coalesced, skew independent.
        assert coordinator.inflight_count == 2
        same_release.set()
        other_release.set()
        same_results = [same_leader.result(timeout=5)] + [
            future.result(timeout=5) for future in same_waiters
        ]
        other_results = [other_leader.result(timeout=5)] + [
            future.result(timeout=5) for future in other_waiters
        ]

    assert same_calls == 1
    assert other_calls == 1
    assert {result.value for result in same_results} == {b"same-gen"}
    assert {result.value for result in other_results} == {b"next-gen"}
    assert {result.status for result in same_results} <= {
        FillStatus.FILLED,
        FillStatus.HIT,
    }
    assert cache.get(same.cache_key) == b"same-gen"
    assert cache.get(other_gen.cache_key) == b"next-gen"
    assert same.cache_key != other_gen.cache_key
    assert coordinator.inflight_count == 0
    cache.assert_invariants()


def test_overlapping_ranges_do_not_single_flight_together() -> None:
    cache = AdaptiveReplacementCache(ARCConfig(capacity_bytes=256))
    coordinator = GenerationAwareRangeSingleFlight(cache)
    left = _binding(offset=0, length=8)
    right = _binding(offset=4, length=8)
    assert not single_flight_compatible(left, right)

    left_entered = Event()
    right_entered = Event()
    release = Event()
    calls = 0
    lock = Lock()

    def left_filler() -> bytes:
        nonlocal calls
        with lock:
            calls += 1
        left_entered.set()
        assert release.wait(timeout=5)
        return b"leftleft"

    def right_filler() -> bytes:
        nonlocal calls
        with lock:
            calls += 1
        right_entered.set()
        assert release.wait(timeout=5)
        return b"rightright"[:8]

    with ThreadPoolExecutor(max_workers=4) as pool:
        left_future = pool.submit(coordinator.get_or_fill_result, left, left_filler)
        right_future = pool.submit(coordinator.get_or_fill_result, right, right_filler)
        assert left_entered.wait(timeout=5)
        assert right_entered.wait(timeout=5)
        assert coordinator.inflight_count == 2
        release.set()
        left_result = left_future.result(timeout=5)
        right_result = right_future.result(timeout=5)

    assert calls == 2
    assert left_result.value == b"leftleft"
    assert right_result.value == b"rightright"[:8]
    cache.assert_invariants()


def test_cancellation_and_error_fan_out_are_bounded_to_the_flight() -> None:
    cache = AdaptiveReplacementCache(ARCConfig(capacity_bytes=256))
    coordinator = GenerationAwareRangeSingleFlight(cache)
    failed = _binding(content_id="fail", offset=0, length=4)
    cancelled = _binding(content_id="cancel", offset=0, length=4)
    independent = _binding(content_id="other", offset=0, length=4)

    entered = Event()
    release = Event()

    def failing_filler() -> bytes:
        entered.set()
        assert release.wait(timeout=5)
        raise ValueError("source unavailable")

    with ThreadPoolExecutor(max_workers=4) as pool:
        leader = pool.submit(coordinator.get_or_fill_result, failed, failing_filler)
        assert entered.wait(timeout=5)
        waiters = [
            pool.submit(coordinator.get_or_fill_result, failed, failing_filler)
            for _ in range(3)
        ]
        # An independent binding must not observe the failed flight.
        independent_future = pool.submit(
            coordinator.get_or_fill,
            independent,
            lambda: b"ok!!",
        )
        assert _wait_until(lambda: coordinator.waiting_count == 3)
        release.set()
        results = [leader.result(timeout=5)] + [
            future.result(timeout=5) for future in waiters
        ]
        independent_value = independent_future.result(timeout=5)

    assert independent_value == b"ok!!"
    assert {result.status for result in results} == {FillStatus.FAILED}
    for result in results:
        with pytest.raises(CacheFillError) as error:
            result.unwrap()
        assert isinstance(error.value.__cause__, ValueError)
    assert cache.get(failed.cache_key) is None
    assert cache.get(independent.cache_key) == b"ok!!"

    entered.clear()
    release.clear()
    calls = 0
    lock = Lock()

    def blocked_filler() -> bytes:
        nonlocal calls
        with lock:
            calls += 1
        entered.set()
        assert release.wait(timeout=5)
        return b"late"

    with ThreadPoolExecutor(max_workers=4) as pool:
        leader = pool.submit(
            coordinator.get_or_fill_result, cancelled, blocked_filler
        )
        assert entered.wait(timeout=5)
        waiters = [
            pool.submit(coordinator.get_or_fill_result, cancelled, blocked_filler)
            for _ in range(2)
        ]
        assert _wait_until(lambda: coordinator.waiting_count == 2)
        assert coordinator.cancel(cancelled)
        # Fan-out is only to this flight's waiters; independent key remains live.
        assert cache.get(independent.cache_key) == b"ok!!"
        late = pool.submit(
            coordinator.get_or_fill_result, cancelled, blocked_filler
        )
        late_result = late.result(timeout=5)
        release.set()
        results = [leader.result(timeout=5)] + [
            future.result(timeout=5) for future in waiters
        ] + [late_result]

    assert calls == 1
    assert {result.status for result in results} == {FillStatus.CANCELLED}
    for result in results:
        with pytest.raises(CacheFillCancelled):
            result.unwrap()
    assert cache.get(cancelled.cache_key) is None
    assert coordinator.inflight_count == 0
    cache.assert_invariants()


def test_asyncio_cancelled_filler_fans_out_typed_cancellation() -> None:
    cache = AdaptiveReplacementCache(ARCConfig(capacity_bytes=64))
    coordinator = GenerationAwareRangeSingleFlight(cache)
    binding = _binding(content_id="async-cancel", length=4)
    entered = Event()
    release = Event()

    def cancelled_filler() -> bytes:
        entered.set()
        assert release.wait(timeout=5)
        raise asyncio.CancelledError("upstream cancelled")

    with ThreadPoolExecutor(max_workers=2) as pool:
        leader = pool.submit(coordinator.get_or_fill_result, binding, cancelled_filler)
        assert entered.wait(timeout=5)
        waiter = pool.submit(coordinator.get_or_fill_result, binding, cancelled_filler)
        assert _wait_until(lambda: coordinator.waiting_count == 1)
        release.set()
        results = [leader.result(timeout=5), waiter.result(timeout=5)]

    assert {result.status for result in results} == {FillStatus.CANCELLED}
    cache.assert_invariants()


# ---------------------------------------------------------------------------
# ARC byte / ghost invariants under range admissions
# ---------------------------------------------------------------------------


def test_range_admissions_preserve_arc_byte_and_ghost_invariants() -> None:
    config = ARCConfig(capacity_bytes=32, max_live_entries=4, max_ghost_entries=4)
    cache = AdaptiveReplacementCache(config)
    coordinator = GenerationAwareRangeSingleFlight(cache)

    bindings = [
        _binding(content_id=f"inode:{index}", offset=index * 8, length=8)
        for index in range(6)
    ]
    for index, binding in enumerate(bindings):
        payload = bytes([index + 1]) * binding.length
        result = coordinator.get_or_fill_result(binding, lambda p=payload: p)
        assert result.ok
        assert result.value == payload

    snapshot = cache.snapshot()
    assert snapshot.current_size == snapshot.t1_size + snapshot.t2_size
    assert snapshot.current_size <= config.capacity_bytes
    assert snapshot.live_entries <= config.max_live_entries
    assert snapshot.ghost_entries <= config.max_ghost_entries
    assert set(snapshot.t1_keys).isdisjoint(snapshot.t2_keys)
    assert set(snapshot.b1_keys).isdisjoint(snapshot.b2_keys)
    live = set(snapshot.t1_keys) | set(snapshot.t2_keys)
    ghosts = set(snapshot.b1_keys) | set(snapshot.b2_keys)
    assert live.isdisjoint(ghosts)
    cache.assert_invariants()

    # Exact hit path revalidates without disturbing invariants.
    hit = coordinator.get_or_fill_result(
        bindings[-1], lambda: b"should-not-run"
    )
    assert hit.status is FillStatus.HIT
    assert hit.value == bytes([6]) * 8
    cache.assert_invariants()


def test_put_and_get_require_exact_binding_length() -> None:
    cache = AdaptiveReplacementCache(ARCConfig(capacity_bytes=64))
    coordinator = GenerationAwareRangeSingleFlight(cache)
    binding = _binding(length=4)

    assert coordinator.put(binding, b"abcd")
    assert coordinator.get(binding) == b"abcd"
    assert coordinator.contains(binding)

    with pytest.raises(RangeExtentError):
        coordinator.put(binding, b"abc")

    miss = _binding(content_id="inode:length-check", length=4)
    bad = coordinator.get_or_fill_result(miss, lambda: b"toolong!")
    assert bad.status is FillStatus.FAILED
    assert isinstance(bad.error, RangeExtentError)
    with pytest.raises(CacheFillError):
        bad.unwrap()

    # Different generation is a miss even with identical extent.
    assert coordinator.get(binding.with_generation("g9")) is None
    assert coordinator.delete(binding)
    assert coordinator.get(binding) is None
    cache.assert_invariants()


def test_lookup_policy_exposed_on_coordinator() -> None:
    cache = AdaptiveReplacementCache(ARCConfig(capacity_bytes=64))
    coordinator = GenerationAwareRangeSingleFlight(cache)
    requested = _binding(offset=0, length=8)
    overlap = requested.with_extent(offset=4, length=8)
    decision = coordinator.lookup(requested, [overlap])
    assert decision.disposition is RangeLookupDisposition.MISS
    assert decision.relation is RangeRelation.OVERLAPS
