"""KVFS-401: Committed read-through and bounded range admission.

Acceptance coverage:

* cache hits revalidate exact bindings;
* misses fetch only requested bounded ranges;
* dirty staged bytes never enter shared ARC;
* policy/authorization-sensitive scopes cannot alias;
* oversized ranges bypass or segment predictably; and
* errors and corrupt entries become safe misses.
"""

from __future__ import annotations

import ast
from pathlib import Path
from threading import Lock

import pytest

from ipfs_kit_py.cache.arc.cache import AdaptiveReplacementCache
from ipfs_kit_py.cache.arc.contracts import ARCConfig
from ipfs_kit_py.cache.arc.range_bindings import (
    MAX_RANGE_LENGTH,
    RangeBinding,
    RangeExtentError,
    RangeLookupDisposition,
    RangeMatchPolicy,
)
from ipfs_kit_py.kernel_vfs import cached_storage as cs_mod
from ipfs_kit_py.kernel_vfs.cached_storage import (
    ADMISSION_METRICS_SCHEMA,
    BOUNDED_RANGE_ADMISSION_SCHEMA,
    CACHED_STORAGE_SCHEMA,
    COMMITTED_READ_THROUGH_SCHEMA,
    CONTRACT_VERSION,
    DEFAULT_CAPACITY_BYTES,
    DEFAULT_SEGMENT_BYTES,
    MAX_SEGMENTS_PER_READ,
    SCHEMA_VERSION,
    TASK_ID,
    AdmissionDisposition,
    AdmissionMetrics,
    BoundedRangeAdmission,
    BoundedRangeAdmission_V1,
    CachedStorage,
    CachedStorage_V1,
    CommittedReadThrough,
    CommittedReadThrough_V1,
    DirtyAdmissionError,
    DirtyScope,
    OversizedRangeError,
    OversizedRangeMode,
    ReadThroughResult,
    is_admitable_length,
    plan_bounded_segments,
)

# test file: .../tests/kernel_vfs/arc/test_cached_storage.py
PACKAGE_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = PACKAGE_ROOT / "ipfs_kit_py" / "kernel_vfs" / "cached_storage.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


class RecordingSource:
    """Committed source that records every fetch extent."""

    def __init__(self, payload: bytes | None = None) -> None:
        self.payload = payload if payload is not None else b""
        self.fetches: list[tuple[int, int]] = []
        self.lock = Lock()
        self.fail_next = False
        self.corrupt_length = False

    def seed(self, payload: bytes) -> None:
        self.payload = payload

    def fetch_range(self, binding: RangeBinding) -> bytes:
        with self.lock:
            self.fetches.append((binding.offset, binding.length))
            if self.fail_next:
                self.fail_next = False
                raise RuntimeError("source unavailable")
            if self.corrupt_length:
                return b"x"  # wrong length on purpose
            end = binding.offset + binding.length
            if end > len(self.payload):
                # Pad with zeros past EOF so length contract holds.
                chunk = self.payload[binding.offset :]
                return chunk + bytes(binding.length - len(chunk))
            return self.payload[binding.offset : end]


def _storage(
    source: RecordingSource | None = None,
    **kwargs,
) -> CachedStorage:
    defaults = dict(
        authorize=lambda _b: True,
        consistent=lambda _b: True,
        capacity_bytes=256 * 1024,
    )
    defaults.update(kwargs)
    if source is not None:
        defaults["source"] = source
    return CachedStorage(**defaults)


# ---------------------------------------------------------------------------
# Artifact / schema / inertness
# ---------------------------------------------------------------------------


def test_declared_module_exists() -> None:
    assert MODULE_PATH.is_file()
    assert MODULE_PATH.stat().st_size > 0


def test_schema_versions_and_aliases() -> None:
    assert TASK_ID == "KVFS-401"
    assert CONTRACT_VERSION == 1
    assert SCHEMA_VERSION.startswith("1.")
    assert CACHED_STORAGE_SCHEMA == CachedStorage_V1
    assert COMMITTED_READ_THROUGH_SCHEMA == CommittedReadThrough_V1
    assert BOUNDED_RANGE_ADMISSION_SCHEMA == BoundedRangeAdmission_V1
    assert CachedStorage_V1.endswith("@1")
    assert ADMISSION_METRICS_SCHEMA.endswith("@1")
    assert DEFAULT_SEGMENT_BYTES == 65_536
    assert DEFAULT_CAPACITY_BYTES == 4 * 1024 * 1024
    assert CommittedReadThrough is CachedStorage
    assert BoundedRangeAdmission is CachedStorage


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


def test_exports_are_importable() -> None:
    assert cs_mod.CachedStorage is CachedStorage
    assert cs_mod.plan_bounded_segments is plan_bounded_segments
    assert cs_mod.AdmissionDisposition is AdmissionDisposition


# ---------------------------------------------------------------------------
# Segmentation helpers
# ---------------------------------------------------------------------------


def test_plan_bounded_segments_covers_exact_request_without_overfetch() -> None:
    segments = plan_bounded_segments(100, 250, max_segment_bytes=100)
    assert [(s.offset, s.length) for s in segments] == [
        (100, 100),
        (200, 100),
        (300, 50),
    ]
    # No padding before start; exclusive end is exactly offset+length.
    assert segments[0].offset == 100
    assert segments[-1].end == 350


def test_plan_bounded_segments_single_when_within_ceiling() -> None:
    segments = plan_bounded_segments(0, 64, max_segment_bytes=MAX_RANGE_LENGTH)
    assert len(segments) == 1
    assert segments[0].offset == 0
    assert segments[0].length == 64


def test_is_admitable_length() -> None:
    assert is_admitable_length(1)
    assert is_admitable_length(MAX_RANGE_LENGTH)
    assert not is_admitable_length(0)
    assert not is_admitable_length(MAX_RANGE_LENGTH + 1)


# ---------------------------------------------------------------------------
# Cache hits revalidate exact bindings
# ---------------------------------------------------------------------------


def test_cache_hit_revalidates_exact_binding() -> None:
    src = RecordingSource(b"abcdefgh")
    store = _storage(src)
    binding = _binding(offset=0, length=8)

    first = store.read(binding)
    assert first.disposition is AdmissionDisposition.FILLED
    assert first.data == b"abcdefgh"
    assert first.admitted is True
    assert len(src.fetches) == 1

    second = store.read(binding)
    assert second.disposition is AdmissionDisposition.HIT
    assert second.from_cache is True
    assert second.data == b"abcdefgh"
    # No additional source fetch on exact hit.
    assert len(src.fetches) == 1

    # Different generation is a different binding — miss + independent fill.
    skewed = binding.with_generation("g2")
    third = store.read(skewed)
    assert third.disposition is AdmissionDisposition.FILLED
    assert len(src.fetches) == 2
    assert store.get(binding) == b"abcdefgh"
    assert store.get(skewed) == b"abcdefgh"


def test_exact_binding_lookup_rejects_overlap_alias() -> None:
    store = _storage()
    requested = _binding(offset=0, length=8)
    overlap = _binding(offset=4, length=8)
    decision = store.lookup(requested, [overlap])
    assert decision.disposition is RangeLookupDisposition.MISS
    assert decision.policy is RangeMatchPolicy.EXACT_ONLY


def test_get_requires_authorization_and_consistency_predicates() -> None:
    src = RecordingSource(b"payload!")
    store = CachedStorage(
        source=src,
        capacity_bytes=4096,
        require_predicates=True,
    )
    binding = _binding(length=8)
    # put_committed also requires gates when require_predicates is set.
    assert (
        store.put_committed(
            binding, b"payload!", authorize=lambda _: True, consistent=lambda _: True
        )
        is True
    )
    assert store.get(binding) is None  # missing predicates → fail-closed
    assert (
        store.get(binding, authorize=lambda _: True, consistent=lambda _: True)
        == b"payload!"
    )
    assert store.get(binding, authorize=lambda _: False, consistent=lambda _: True) is None
    assert store.get(binding, authorize=lambda _: True, consistent=lambda _: False) is None
    metrics = store.metrics()
    assert metrics.authorization_rejections >= 2
    assert metrics.consistency_rejections >= 1


# ---------------------------------------------------------------------------
# Misses fetch only requested bounded ranges
# ---------------------------------------------------------------------------


def test_miss_fetches_only_requested_bounded_range() -> None:
    payload = bytes(range(256)) * 4  # 1024 bytes
    src = RecordingSource(payload)
    store = _storage(src)
    binding = _binding(offset=100, length=32)

    result = store.read(binding)
    assert result.ok
    assert result.data == payload[100:132]
    assert src.fetches == [(100, 32)]
    # Cache holds only that exact range key.
    assert store.contains(binding)
    assert not store.contains(binding.with_extent(offset=0, length=32))


def test_callable_source_is_accepted() -> None:
    calls: list[tuple[int, int]] = []

    def filler(binding: RangeBinding) -> bytes:
        calls.append((binding.offset, binding.length))
        return b"Z" * binding.length

    store = _storage(source=filler)
    binding = _binding(offset=10, length=4)
    result = store.read(binding)
    assert result.data == b"ZZZZ"
    assert calls == [(10, 4)]


# ---------------------------------------------------------------------------
# Dirty staged bytes never enter shared ARC
# ---------------------------------------------------------------------------


def test_dirty_staged_bytes_never_enter_shared_arc() -> None:
    src = RecordingSource(b"committed")
    store = _storage(src)
    binding = _binding(length=9)

    # Commit a clean entry first.
    filled = store.read(binding)
    assert filled.disposition is AdmissionDisposition.FILLED
    assert store.contains(binding)

    # Mark dirty (e.g. open handle with staged writes).
    scope = store.mark_dirty(binding=binding)
    assert isinstance(scope, DirtyScope)
    assert store.is_dirty(binding)
    # Prior committed entry is evicted so dirty state cannot mix with ARC.
    assert not store.contains(binding)

    overlay = b"DIRTY!!!!"  # 9 bytes, matches binding/source length
    assert len(overlay) == 9
    dirty_read = store.read(binding, dirty=True, dirty_overlay=overlay)
    assert dirty_read.disposition is AdmissionDisposition.DIRTY_BYPASS
    assert dirty_read.data == overlay
    assert dirty_read.admitted is False
    # Overlay must not be present under the binding key.
    assert store.get(binding) is None
    assert not store.contains(binding)

    with pytest.raises(DirtyAdmissionError):
        store.put_committed(binding, overlay)

    # After clear_dirty, committed read-through may admit again.
    assert store.clear_dirty(binding=binding) is True
    assert not store.is_dirty(binding)
    again = store.read(binding)
    assert again.disposition is AdmissionDisposition.FILLED
    assert again.data == b"committed"
    assert store.contains(binding)
    assert store.get(binding) == b"committed"


def test_dirty_scope_blocks_admission_for_versioned_content() -> None:
    src = RecordingSource(b"01234567")
    store = _storage(src)
    binding = _binding(length=8)
    store.mark_dirty(
        namespace=binding.namespace,
        content_id=binding.content_id,
        version=binding.version,
    )
    result = store.read(binding)
    assert result.disposition is AdmissionDisposition.DIRTY_BYPASS
    assert result.admitted is False
    assert not store.contains(binding)
    # Unrelated content still admits.
    other = _binding(content_id="inode:99", length=8)
    other_result = store.read(other)
    assert other_result.disposition is AdmissionDisposition.FILLED
    assert store.contains(other)


# ---------------------------------------------------------------------------
# Policy / authorization-sensitive scopes cannot alias
# ---------------------------------------------------------------------------


def test_policy_sensitive_scopes_cannot_alias() -> None:
    src = RecordingSource(b"secret!!")
    store = _storage(src)
    public = _binding(policy="public", length=8)
    restricted = _binding(policy="restricted", length=8)

    assert public.cache_key != restricted.cache_key

    r_public = store.read(public)
    assert r_public.data == b"secret!!"
    assert store.contains(public)
    assert not store.contains(restricted)

    # Restricted policy does not hit the public entry.
    r_restricted = store.read(restricted)
    assert r_restricted.disposition is AdmissionDisposition.FILLED
    assert len(src.fetches) == 2
    assert store.get(public) == b"secret!!"
    assert store.get(restricted) == b"secret!!"

    # Authorization gate can refuse one policy without affecting the other.
    denied = store.read(
        public,
        authorize=lambda b: b.policy != "public",
        consistent=lambda _: True,
    )
    assert denied.disposition is AdmissionDisposition.REJECTED
    assert store.get(restricted) == b"secret!!"


def test_namespace_and_serializer_do_not_alias() -> None:
    src = RecordingSource(b"abcdefgh")
    store = _storage(src)
    a = _binding(namespace="tenant-a", length=8)
    b = _binding(namespace="tenant-b", length=8)
    c = _binding(namespace="tenant-a", serializer="cbor@1", length=8)
    store.read(a)
    assert store.contains(a)
    assert not store.contains(b)
    assert not store.contains(c)
    keys = {a.cache_key, b.cache_key, c.cache_key}
    assert len(keys) == 3


# ---------------------------------------------------------------------------
# Oversized ranges bypass or segment predictably
# ---------------------------------------------------------------------------


def test_oversized_range_segments_predictably() -> None:
    segment = 64
    total = segment * 3 + 10  # 202
    payload = bytes((i % 256) for i in range(total + 50))
    src = RecordingSource(payload)
    store = _storage(
        src,
        segment_bytes=segment,
        max_range_length=segment,
        oversized_mode=OversizedRangeMode.SEGMENT,
    )
    # Request larger than max_range_length so segmentation engages.
    result = store.read_range(
        content_id="inode:7",
        version="v1",
        generation="g1",
        offset=0,
        length=total,
        policy="public",
    )
    assert result.disposition is AdmissionDisposition.SEGMENTED
    assert result.segments == 4  # 64+64+64+10
    assert result.data == payload[:total]
    # Each fetch is exactly a planned segment — no over-fetch.
    assert src.fetches == [
        (0, 64),
        (64, 64),
        (128, 64),
        (192, 10),
    ]
    # Individual segments are admitted under exact bindings.
    first_seg = RangeBinding.create(
        namespace="default",
        content_id="inode:7",
        version="v1",
        generation="g1",
        offset=0,
        length=64,
        policy="public",
    )
    assert store.contains(first_seg)
    # Second read is served from cache (no new fetches).
    fetches_before = len(src.fetches)
    again = store.read_range(
        content_id="inode:7",
        version="v1",
        generation="g1",
        offset=0,
        length=total,
        policy="public",
    )
    assert again.disposition is AdmissionDisposition.SEGMENTED
    assert again.data == payload[:total]
    assert len(src.fetches) == fetches_before


def test_oversized_range_bypass_never_admits() -> None:
    segment = 32
    total = segment * 2 + 5
    payload = b"A" * total
    src = RecordingSource(payload)
    store = _storage(
        src,
        max_range_length=segment,
        segment_bytes=segment,
        oversized_mode=OversizedRangeMode.BYPASS,
    )
    result = store.read_range(
        content_id="inode:8",
        version="v1",
        offset=0,
        length=total,
    )
    assert result.disposition is AdmissionDisposition.BYPASS
    assert result.admitted is False
    assert result.data == payload
    # Bypass still only fetches the requested window, chunked for the source.
    assert src.fetches == [(0, 32), (32, 32), (64, 5)]
    # Nothing admitted under segment bindings.
    for off, length in src.fetches:
        seg = RangeBinding.create(
            namespace="default",
            content_id="inode:8",
            version="v1",
            offset=off,
            length=length,
        )
        assert not store.contains(seg)


def test_hard_ceiling_rejects_extreme_reads() -> None:
    store = _storage(max_read_bytes=1024)
    with pytest.raises(OversizedRangeError):
        store.read_range(
            content_id="inode:1",
            version="v1",
            offset=0,
            length=2048,
        )


# ---------------------------------------------------------------------------
# Errors and corrupt entries become safe misses
# ---------------------------------------------------------------------------


def test_source_error_becomes_safe_miss() -> None:
    src = RecordingSource(b"abcdefgh")
    src.fail_next = True
    store = _storage(src)
    binding = _binding(length=8)
    result = store.read(binding)
    assert result.disposition is AdmissionDisposition.SAFE_MISS
    assert result.data == b""
    assert not store.contains(binding)
    assert store.metrics().safe_misses >= 1
    assert store.metrics().source_errors >= 1

    # Subsequent success still works (no poisoned entry).
    src.fail_next = False
    ok = store.read(binding)
    assert ok.disposition is AdmissionDisposition.FILLED
    assert ok.data == b"abcdefgh"


def test_corrupt_entry_becomes_safe_miss_and_is_evicted() -> None:
    src = RecordingSource(b"abcdefgh")
    cache = AdaptiveReplacementCache(ARCConfig(capacity_bytes=4096))
    store = CachedStorage(
        cache=cache,
        source=src,
        authorize=lambda _: True,
        consistent=lambda _: True,
    )
    binding = _binding(length=8)
    assert store.read(binding).disposition is AdmissionDisposition.FILLED

    # Corrupt the live ARC value under the binding key (simulate bit-rot /
    # bookkeeping drift) by replacing with wrong-length bytes via core put.
    # Direct core put bypasses CachedStorage length checks.
    assert cache.put(binding.cache_key, b"short") is True

    # get() must not return corrupt data.
    assert store.get(binding) is None
    assert store.metrics().corrupt_entries >= 1
    assert not store.contains(binding)

    # read() recovers via safe miss → refill.
    recovered = store.read(binding)
    assert recovered.disposition is AdmissionDisposition.FILLED
    assert recovered.data == b"abcdefgh"
    assert store.get(binding) == b"abcdefgh"


def test_filler_length_mismatch_is_safe_miss() -> None:
    src = RecordingSource(b"abcdefgh")
    src.corrupt_length = True
    store = _storage(src)
    binding = _binding(length=8)
    result = store.read(binding)
    assert result.disposition is AdmissionDisposition.SAFE_MISS
    assert result.data == b""
    assert not store.contains(binding)


def test_missing_source_is_safe_miss() -> None:
    store = CachedStorage(
        authorize=lambda _: True,
        consistent=lambda _: True,
        capacity_bytes=4096,
    )
    result = store.read(_binding(length=4))
    assert result.disposition is AdmissionDisposition.SAFE_MISS
    assert result.reason == "no_source"


# ---------------------------------------------------------------------------
# Metrics / invariants / put path
# ---------------------------------------------------------------------------


def test_metrics_and_invariants_after_mixed_workload() -> None:
    src = RecordingSource(bytes(range(128)))
    store = _storage(src, segment_bytes=32, max_range_length=32)
    b1 = _binding(offset=0, length=16)
    store.read(b1)
    store.read(b1)  # hit
    store.read_range(
        namespace="ns-a",
        content_id="inode:42",
        version="v1",
        generation="g1",
        offset=0,
        length=40,  # oversized → segment
        policy="public",
    )
    metrics = store.metrics()
    assert isinstance(metrics, AdmissionMetrics)
    assert metrics.hits >= 1
    assert metrics.fills >= 1
    assert metrics.bytes_served > 0
    store.assert_invariants()
    record = metrics.to_dict()
    assert "hits" in record
    assert "safe_misses" in record


def test_read_through_result_record() -> None:
    src = RecordingSource(b"xyzzyxxx")
    store = _storage(src)
    result = store.read(_binding(length=8))
    assert isinstance(result, ReadThroughResult)
    record = result.to_dict()
    assert record["disposition"] == "filled"
    assert record["data_size"] == 8
    assert record["admitted"] is True


def test_put_committed_rejects_length_mismatch() -> None:
    store = _storage()
    binding = _binding(length=4)
    with pytest.raises(RangeExtentError):
        store.put_committed(binding, b"toolong")


def test_delete_and_contains() -> None:
    src = RecordingSource(b"12345678")
    store = _storage(src)
    binding = _binding(length=8)
    store.read(binding)
    assert store.contains(binding)
    assert store.delete(binding) is True
    assert not store.contains(binding)
    assert store.get(binding) is None


def test_segment_ceiling_guard() -> None:
    # Force more segments than the hard ceiling allows.
    huge = MAX_SEGMENTS_PER_READ * 2 + 1
    with pytest.raises(OversizedRangeError):
        plan_bounded_segments(0, huge, max_segment_bytes=1)


def test_dirty_scope_keying() -> None:
    scope = DirtyScope(namespace="n", content_id="c", version="v")
    binding = _binding(namespace="n", content_id="c", version="v", length=1)
    other = _binding(namespace="n", content_id="c", version="other", length=1)
    assert scope.matches(binding)
    assert not scope.matches(other)
    broad = DirtyScope(namespace="n", content_id="c", version=None)
    assert broad.matches(binding)
    assert broad.matches(other)
