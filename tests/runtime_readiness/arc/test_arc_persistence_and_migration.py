"""Regression coverage for the ARC integration/migration boundary (KITA-024)."""

from __future__ import annotations

import asyncio
import json

from ipfs_kit_py.arc_cache import ARCache, CacheBinding, GenerationBoundARC
from ipfs_kit_py.arc_cache_anyio import ARCacheAnyIO
from ipfs_kit_py.cache.arc.contracts import ARCConfig
from ipfs_kit_py.cache.arc.metrics import ARCIntegrationMetricsCollector


def _binding(
    *,
    content_id: str = "cid-a",
    version: str = "v1",
    policy: str = "public",
    generation: str = "g1",
) -> CacheBinding:
    return CacheBinding(
        content_id=content_id,
        version=version,
        namespace="tenant-a",
        policy=policy,
        serializer="bytes@1",
        generation=generation,
    )


def _guarded_get(cache: GenerationBoundARC, binding: CacheBinding) -> bytes | None:
    return cache.get(binding, authorize=lambda _: True, consistent=lambda _: True)


def test_persistence_is_data_only_atomic_and_restores_exact_bindings(tmp_path):
    source = GenerationBoundARC(ARCConfig(capacity_bytes=4096))
    first = _binding()
    second = _binding(content_id="cid-b", version="v2", policy="restricted")
    assert source.put(first, b"first")
    assert source.put(second, b"second")

    location = tmp_path / "arc-state.json"
    assert source.persist(location)
    raw = location.read_bytes()
    envelope = json.loads(raw)
    assert envelope["schema"].endswith("@1")
    assert envelope["version"] == 1
    assert b"pickle" not in raw.lower()
    assert not list(tmp_path.glob(".arc-state.json.*.tmp"))

    restored = GenerationBoundARC(ARCConfig(capacity_bytes=4096))
    assert restored.restore(location)
    assert _guarded_get(restored, first) == b"first"
    assert _guarded_get(restored, second) == b"second"


def test_corrupt_schema_mismatched_and_stale_persistence_miss_without_mutation(tmp_path):
    source = GenerationBoundARC(ARCConfig(capacity_bytes=4096))
    persisted = _binding()
    assert source.put(persisted, b"persisted")
    location = tmp_path / "arc-state.json"
    assert source.persist(location)

    target = GenerationBoundARC(ARCConfig(capacity_bytes=4096))
    resident = _binding(content_id="resident")
    assert target.put(resident, b"resident")
    location.write_bytes(b"{not json")
    assert not target.restore(location)
    assert _guarded_get(target, resident) == b"resident"
    assert target.metrics().persistence_corrupt == 1

    assert source.persist(location)
    envelope = json.loads(location.read_text())
    envelope["version"] = 999
    location.write_text(json.dumps(envelope))
    assert not target.restore(location)
    assert _guarded_get(target, resident) == b"resident"
    assert target.metrics().persistence_schema_rejections == 1

    assert source.persist(location)
    assert target.advance_generation("cid-a", "g2", namespace="tenant-a") == 0
    assert not target.restore(location)
    assert _guarded_get(target, resident) == b"resident"
    assert target.metrics().persistence_stale_rejections == 1


def test_binding_dimensions_invalidate_only_exact_dependents_and_reads_are_guarded():
    cache = GenerationBoundARC(ARCConfig(capacity_bytes=4096))
    old = _binding(version="v1", policy="public")
    changed_version = _binding(version="v2", policy="public")
    changed_policy = _binding(version="v1", policy="restricted")
    assert cache.put(old, b"old")
    assert cache.put(changed_version, b"version")
    assert cache.put(changed_policy, b"policy")

    # A hit can never become an authorization/freshness bypass.
    assert cache.get(old) is None
    assert cache.get(old, authorize=lambda _: True) is None
    assert cache.get(old, consistent=lambda _: True) is None
    assert _guarded_get(cache, old) == b"old"

    assert cache.invalidate(content_id="cid-a", version="v1", policy="public") == 1
    assert _guarded_get(cache, old) is None
    assert _guarded_get(cache, changed_version) == b"version"
    assert _guarded_get(cache, changed_policy) == b"policy"
    assert cache.metrics().stale_rejections >= 1
    assert cache.metrics().authorization_rejections == 2
    assert cache.metrics().consistency_rejections == 1


def test_generation_change_invalidates_that_content_scope_only():
    cache = GenerationBoundARC(ARCConfig(capacity_bytes=4096))
    stale = _binding(generation="g1")
    unrelated = _binding(content_id="other", generation="g1")
    assert cache.put(stale, b"stale")
    assert cache.put(unrelated, b"other")
    assert cache.advance_generation("cid-a", "g2", namespace="tenant-a") == 1
    assert _guarded_get(cache, stale) is None
    assert _guarded_get(cache, unrelated) == b"other"


def test_new_generation_write_invalidates_previous_generation_only_after_admission():
    cache = GenerationBoundARC(ARCConfig(capacity_bytes=4096))
    old = _binding(generation="g1")
    replacement = _binding(generation="g2")
    assert cache.put(old, b"old")
    assert cache.put(replacement, b"new")
    assert _guarded_get(cache, old) is None
    assert _guarded_get(cache, replacement) == b"new"

    # A rejected successor cannot advance the scope or invalidate the live key.
    rejected = _binding(generation="g3")
    assert not cache.put(rejected, b"x" * 4097)
    assert _guarded_get(cache, replacement) == b"new"


def test_metrics_capture_pre_access_recency_and_legacy_views_delegate():
    collector = ARCIntegrationMetricsCollector()
    first = collector.record_access("key", now=10.0)
    second = collector.record_access("key", now=12.5)
    assert first.age is None
    assert second.previous_access == 10.0
    assert second.age == 2.5

    cache = ARCache(maxsize=4096)
    assert cache.put("key", b"value")
    assert cache.get("key") == b"value"
    assert "key" in cache.T2
    del cache.T2["key"]
    assert not cache.contains("key")
    integration = cache.get_stats()["integration"]
    for state in ("live_hits", "ghost_hits", "stale_rejections", "admission_rejections", "evictions", "fills_started"):
        assert state in integration


def test_anyio_surface_delegates_to_one_legacy_adapter():
    legacy = ARCache(maxsize=4096)
    anyio_cache = ARCacheAnyIO(cache=legacy)

    async def exercise() -> None:
        assert await anyio_cache.async_put("key", b"value")
        assert await anyio_cache.async_get("key") == b"value"
        assert await anyio_cache.async_delete("key")

    asyncio.run(exercise())
    assert anyio_cache.cache is legacy
    assert not legacy.contains("key")


def test_legacy_capacity_alias_constructs_the_same_core_adapter():
    cache = ARCache(capacity=4096, disk_cache_dir="ignored", enable_disk_cache=True)
    assert cache.maxsize == 4096
