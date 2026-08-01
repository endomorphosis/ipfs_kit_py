"""Compatibility and generation-bound adapters for the synchronized ARC core.

The ARC algorithm has one implementation: ``AdaptiveReplacementCache``.  The
legacy ``ARCache`` name and the generation-aware persistence surface below are
adapters over that implementation; neither owns a second set of ARC lists.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, MutableMapping
from dataclasses import dataclass
import hashlib
import json
from threading import RLock
from typing import Any, Final

from ipfs_kit_py.cache.arc.cache import AdaptiveReplacementCache
from ipfs_kit_py.cache.arc.contracts import ARCConfig
from ipfs_kit_py.cache.arc.metrics import (
    ARCIntegrationMetrics,
    ARCIntegrationMetricsCollector,
    AccessTiming,
)
# These utility classes historically happened to live in this module.  Keep
# their public import path without retaining a second implementation here.
from ipfs_kit_py.cache.probabilistic_data_structures import (
    BloomFilter,
    CountMinSketch,
    HyperLogLog,
    MinHash,
)


GENERATION_BINDING_SCHEMA: Final[str] = "ipfs_kit_py/cache/arc/generation-binding@1"
_BINDING_FIELDS: Final[frozenset[str]] = frozenset(
    {"content_id", "version", "namespace", "policy", "serializer", "generation"}
)


def _bounded_text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > 512:
        raise ValueError(f"{name} must be a non-empty string of at most 512 bytes")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError(f"{name} must not contain control characters")
    return value


@dataclass(frozen=True)
class CacheBinding:
    """Immutable identity for a cacheable representation.

    Every dimension is part of the hash supplied to the ARC core.  A changed
    content id, version, policy, serializer, namespace, or generation is
    therefore a different key and cannot accidentally return an old payload.
    """

    content_id: str
    version: str
    namespace: str = "default"
    policy: str = "default"
    serializer: str = "bytes@1"
    generation: str = "0"

    def __post_init__(self) -> None:
        for field in _BINDING_FIELDS:
            object.__setattr__(self, field, _bounded_text(getattr(self, field), field))

    @property
    def content(self) -> str:
        """Alias used by callers that call the content identity ``content``."""

        return self.content_id

    def to_dict(self) -> dict[str, str]:
        return {
            "content_id": self.content_id,
            "version": self.version,
            "namespace": self.namespace,
            "policy": self.policy,
            "serializer": self.serializer,
            "generation": self.generation,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "CacheBinding":
        if not isinstance(value, dict) or set(value) != _BINDING_FIELDS:
            raise ValueError("binding has an unknown or missing identity field")
        return cls(**value)

    @property
    def cache_key(self) -> str:
        canonical = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return "arc:" + hashlib.sha256(canonical.encode("ascii")).hexdigest()


GenerationBinding = CacheBinding
CacheIdentity = CacheBinding


class GenerationBoundARC:
    """A guarded ARC facade with exact generation invalidation and persistence.

    Values are returned only after both the authorization and consistency
    predicates approve the *exact* binding.  Callers must provide those
    predicates for a read; an omitted predicate is fail-closed.  This keeps a
    cache hit from becoming an authorization or freshness bypass.
    """

    def __init__(self, config: ARCConfig | None = None, *, cache: AdaptiveReplacementCache | None = None) -> None:
        if cache is not None and config is not None:
            raise TypeError("pass either config or cache, not both")
        self._lock = RLock()
        self._cache = cache if cache is not None else AdaptiveReplacementCache(config)
        self._bindings: dict[str, CacheBinding] = {}
        self._generations: dict[tuple[str, str], str] = {}
        self._metrics = ARCIntegrationMetricsCollector()

    @property
    def core(self) -> AdaptiveReplacementCache:
        return self._cache

    @property
    def metrics_collector(self) -> ARCIntegrationMetricsCollector:
        return self._metrics

    def metrics(self) -> ARCIntegrationMetrics:
        return self._metrics.snapshot()

    @staticmethod
    def _scope(binding: CacheBinding) -> tuple[str, str]:
        return binding.namespace, binding.content_id

    @staticmethod
    def _coerce_binding(binding: CacheBinding | dict[str, str]) -> CacheBinding:
        return binding if isinstance(binding, CacheBinding) else CacheBinding.from_dict(binding)

    def _remove_key_locked(self, key: str) -> bool:
        removed = self._cache.delete(key)
        self._bindings.pop(key, None)
        self._metrics.forget(key)
        return removed

    def _prune_bindings_locked(self) -> None:
        live = set(self._cache.snapshot().t1_keys) | set(self._cache.snapshot().t2_keys)
        for key in tuple(self._bindings):
            if key not in live:
                self._bindings.pop(key, None)
                self._metrics.forget(key)

    def put(self, binding: CacheBinding | dict[str, str], value: bytes) -> bool:
        identity = self._coerce_binding(binding)
        key = identity.cache_key
        with self._lock:
            scope = self._scope(identity)
            active_generation = self._generations.get(scope)
            previous_location = self._cache.locate(key)
            before = self._cache.metrics()
            admitted = self._cache.put(key, value)
            after = self._cache.metrics()
            if previous_location in {"B1", "B2"}:
                self._metrics.increment("ghost_hits")
            self._metrics.increment("evictions", (after.evictions_t1 + after.evictions_t2) - (before.evictions_t1 + before.evictions_t2))
            if not admitted:
                self._metrics.increment("admission_rejections")
                return False
            # A successful write for a new generation advances that content
            # scope just like an explicit generation notification.  Do this
            # only after admission, so a rejected oversized value cannot make
            # otherwise-valid live data disappear.
            if active_generation is not None and active_generation != identity.generation:
                for stale_key, candidate in tuple(self._bindings.items()):
                    if self._scope(candidate) == scope and candidate.generation != identity.generation:
                        self._remove_key_locked(stale_key)
            self._bindings[key] = identity
            self._generations[scope] = identity.generation
            self._prune_bindings_locked()
            return True

    def get(
        self,
        binding: CacheBinding | dict[str, str],
        *,
        authorize: Callable[[CacheBinding], bool] | None = None,
        consistent: Callable[[CacheBinding], bool] | None = None,
    ) -> bytes | None:
        """Return a value only after required authorization and consistency gates."""

        identity = self._coerce_binding(binding)
        key = identity.cache_key
        with self._lock:
            stored = self._bindings.get(key)
            active_generation = self._generations.get(self._scope(identity), identity.generation)
            if stored != identity or active_generation != identity.generation:
                if stored is not None:
                    self._remove_key_locked(key)
                self._metrics.increment("stale_rejections")
                return None
            if authorize is None or not self._approved(authorize, identity):
                self._metrics.increment("authorization_rejections")
                return None
            if consistent is None or not self._approved(consistent, identity):
                self._metrics.increment("consistency_rejections")
                return None
            location = self._cache.locate(key)
            value = self._cache.get(key)
            if value is None:
                self._bindings.pop(key, None)
                self._metrics.forget(key)
                return None
            if location in {"T1", "T2"}:
                self._metrics.increment("live_hits")
                self._metrics.record_access(key)
            return value

    @staticmethod
    def _approved(predicate: Callable[[CacheBinding], bool], binding: CacheBinding) -> bool:
        try:
            return bool(predicate(binding))
        except Exception:
            return False

    def contains(self, binding: CacheBinding | dict[str, str]) -> bool:
        identity = self._coerce_binding(binding)
        with self._lock:
            return self._bindings.get(identity.cache_key) == identity and self._cache.contains(identity.cache_key)

    def invalidate(self, binding: CacheBinding | dict[str, str] | None = None, **exact: str) -> int:
        """Delete only identities matching every supplied identity dimension."""

        if binding is not None and exact:
            raise TypeError("pass a binding or exact identity fields, not both")
        if binding is not None:
            identity = self._coerce_binding(binding)
            exact = identity.to_dict()
        if not exact or not set(exact).issubset(_BINDING_FIELDS):
            raise ValueError("invalidation requires one or more exact binding fields")
        if any(not isinstance(value, str) for value in exact.values()):
            raise ValueError("invalidation identity fields must be strings")
        with self._lock:
            keys = [key for key, candidate in self._bindings.items() if all(getattr(candidate, name) == value for name, value in exact.items())]
            for key in keys:
                self._remove_key_locked(key)
            return len(keys)

    def advance_generation(self, content_id: str, generation: str, *, namespace: str = "default") -> int:
        """Make prior generations of one namespace/content pair stale."""

        content_id = _bounded_text(content_id, "content_id")
        generation = _bounded_text(generation, "generation")
        namespace = _bounded_text(namespace, "namespace")
        with self._lock:
            scope = namespace, content_id
            self._generations[scope] = generation
            keys = [key for key, binding in self._bindings.items() if self._scope(binding) == scope and binding.generation != generation]
            for key in keys:
                self._remove_key_locked(key)
            return len(keys)

    invalidate_dependents = invalidate

    def record_fill(self, state: str) -> None:
        normalized = str(getattr(state, "value", state)).lower()
        names = {
            "started": "fills_started", "leader": "fills_started", "succeeded": "fills_succeeded",
            "success": "fills_succeeded", "failed": "fills_failed", "failure": "fills_failed",
            "cancelled": "fills_cancelled", "canceled": "fills_cancelled",
        }
        if normalized not in names:
            raise ValueError("unknown fill state")
        self._metrics.increment(names[normalized])

    def persist(self, path: str) -> bool:
        from ipfs_kit_py.cache.arc.persistence import save

        return save(self, path)

    def restore(self, path: str) -> bool:
        from ipfs_kit_py.cache.arc.persistence import load

        return load(self, path)

    def _persistence_export(self) -> list[dict[str, Any]]:
        """Value export under the core lock; only live records are serialized."""

        with self._lock, self._cache._lock:  # core lock protects its reference model
            model = self._cache._model
            entries: list[dict[str, Any]] = []
            for collection in (model._t1, model._t2):
                for key, entry in collection.items():
                    binding = self._bindings.get(key)
                    if binding is not None:
                        entries.append({"binding": binding.to_dict(), "value": bytes(entry.value)})
            return entries

    def _persistence_import(self, entries: list[dict[str, Any]]) -> bool:
        """Validate all input before atomically replacing this facade's live set."""

        try:
            candidate_rows: list[tuple[CacheBinding, bytes]] = []
            candidate_keys: set[str] = set()
            candidate_generations: dict[tuple[str, str], str] = {}
            for entry in entries:
                if not isinstance(entry, dict) or set(entry) != {"binding", "value"}:
                    return False
                identity = CacheBinding.from_dict(entry["binding"])
                value = entry["value"]
                if not isinstance(value, bytes) or identity.cache_key in candidate_keys:
                    return False
                scope = self._scope(identity)
                known_generation = candidate_generations.setdefault(scope, identity.generation)
                # A saved facade has exactly one active generation per scope.
                # Accepting two generations would recreate an incoherent state
                # after restart, so treat it as stale rather than choosing one.
                if known_generation != identity.generation:
                    return False
                candidate_keys.add(identity.cache_key)
                candidate_rows.append((identity, value))
        except (TypeError, ValueError):
            return False
        with self._lock:
            for identity, _ in candidate_rows:
                existing = self._generations.get(self._scope(identity))
                if existing is not None and existing != identity.generation:
                    return False
            replacement = AdaptiveReplacementCache(self._cache.config)
            replacement_bindings: dict[str, CacheBinding] = {}
            replacement_generations = dict(self._generations)
            try:
                for identity, value in candidate_rows:
                    if not replacement.put(identity.cache_key, value):
                        return False
                    replacement_bindings[identity.cache_key] = identity
                    replacement_generations.setdefault(self._scope(identity), identity.generation)
            except (TypeError, ValueError):
                return False
            restored = replacement.snapshot()
            live_keys = set(restored.t1_keys) | set(restored.t2_keys)
            # Never turn a valid file into a partial restart.  A differently
            # configured target may be smaller than the source, in which case
            # the whole persisted snapshot is simply a safe cache miss.
            if live_keys != set(replacement_bindings):
                return False
            self._cache = replacement
            self._bindings = replacement_bindings
            self._generations = replacement_generations
            return True


class _ARCListView(MutableMapping[str, bytes | bool]):
    """A compatibility view, never a second mutable ARC list."""

    def __init__(self, owner: "ARCache", list_name: str) -> None:
        self._owner = owner
        self._list_name = list_name

    def _snapshot(self) -> dict[str, bytes | bool]:
        with self._owner._cache._lock:
            model = self._owner._cache._model
            values = getattr(model, "_" + self._list_name.lower())
            if self._list_name in {"T1", "T2"}:
                return {key: entry.value for key, entry in values.items()}
            return {key: True for key in values}

    def __getitem__(self, key: str) -> bytes | bool:
        return self._snapshot()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._snapshot())

    def __len__(self) -> int:
        return len(self._snapshot())

    def __setitem__(self, key: str, value: bytes | bool) -> None:
        if self._list_name not in {"T1", "T2"} or not isinstance(value, (bytes, bytearray, memoryview)):
            raise TypeError("only live ARC compatibility views accept bytes values")
        self._owner.put(key, bytes(value))

    def __delitem__(self, key: str) -> None:
        if key not in self._snapshot():
            raise KeyError(key)
        self._owner.delete(key)


class ARCache:
    """Legacy API delegating to one synchronized ``AdaptiveReplacementCache``."""

    def __init__(
        self,
        maxsize: int = 100 * 1024 * 1024,
        config: dict[str, Any] | ARCConfig | None = None,
        **legacy_options: Any,
    ) -> None:
        """Create the legacy facade while accepting its historical options.

        ``capacity`` was used by a few callers before ``maxsize`` became the
        documented spelling.  It remains an input alias, but all ARC state is
        still owned by the synchronized core.  Non-ARC legacy options such as
        disk-cache settings are intentionally ignored here: this is the memory
        ARC adapter, not a second persistence/cache implementation.
        """

        if isinstance(config, ARCConfig):
            if legacy_options:
                # Accept unrelated historical options, but do not silently
                # reinterpret ARC settings supplied by an immutable config.
                legacy_options.pop("capacity", None)
            if maxsize != 100 * 1024 * 1024 and maxsize != config.capacity_bytes:
                raise ValueError("maxsize and ARCConfig.capacity_bytes disagree")
            core_config = config
        elif config is None or isinstance(config, dict):
            settings = dict(config or {})
            option_capacity = legacy_options.pop("capacity", None)
            configured_capacity = settings.pop("capacity_bytes", settings.pop("capacity", option_capacity))
            capacity = maxsize if configured_capacity is None else configured_capacity
            if capacity != maxsize and maxsize != 100 * 1024 * 1024:
                raise ValueError("maxsize and config.capacity_bytes disagree")
            core_config = ARCConfig(
                capacity_bytes=capacity,
                max_live_entries=settings.pop("max_live_entries", 256),
                max_ghost_entries=settings.pop("max_ghost_entries", settings.pop("ghost_list_size", 256)),
                initial_p=settings.pop("initial_p", 0),
            )
        else:
            raise TypeError("config must be a mapping, ARCConfig, or None")
        self._cache = AdaptiveReplacementCache(core_config)
        self._metrics = ARCIntegrationMetricsCollector()
        self._last_timing: dict[str, AccessTiming] = {}
        self.T1 = _ARCListView(self, "T1")
        self.T2 = _ARCListView(self, "T2")
        self.B1 = _ARCListView(self, "B1")
        self.B2 = _ARCListView(self, "B2")

    @property
    def maxsize(self) -> int:
        return self._cache.capacity_bytes

    @property
    def current_size(self) -> int:
        return self._cache.current_size

    @property
    def p(self) -> int:
        return self._cache.p

    @property
    def T1_size(self) -> int:
        return self._cache.t1_size

    @property
    def T2_size(self) -> int:
        return self._cache.t2_size

    @property
    def metrics_collector(self) -> ARCIntegrationMetricsCollector:
        return self._metrics

    def __len__(self) -> int:
        snapshot = self._cache.snapshot()
        return snapshot.live_entries

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and self.contains(key)

    def contains(self, key: str) -> bool:
        return self._cache.contains(key)

    def get(self, key: str, default: bytes | None = None) -> bytes | None:
        location = self._cache.locate(key)
        value = self._cache.get(key)
        if value is None:
            return default
        if location in {"T1", "T2"}:
            self._metrics.increment("live_hits")
            self._last_timing[key] = self._metrics.record_access(key)
        return value

    def put(self, key: str, value: bytes) -> bool:
        previous_location = self._cache.locate(key)
        before = self._cache.metrics()
        admitted = self._cache.put(key, value)
        after = self._cache.metrics()
        if previous_location in {"B1", "B2"}:
            self._metrics.increment("ghost_hits")
        evicted = (after.evictions_t1 + after.evictions_t2) - (before.evictions_t1 + before.evictions_t2)
        self._metrics.increment("evictions", evicted)
        if not admitted:
            self._metrics.increment("admission_rejections")
        return admitted

    set = put

    def delete(self, key: str) -> bool:
        deleted = self._cache.delete(key)
        if deleted:
            self._metrics.forget(key)
            self._last_timing.pop(key, None)
        return deleted

    evict = delete

    def clear(self) -> None:
        self._cache.clear()
        self._last_timing.clear()

    def get_heat_score(self, key: str) -> float:
        timing = self._last_timing.get(key)
        if timing is None or timing.age is None:
            return 1.0
        return 1.0 / (1.0 + timing.age)

    def get_stats(self) -> dict[str, Any]:
        snapshot = self._cache.snapshot()
        core = self._cache.metrics()
        return {
            "maxsize": self.maxsize,
            "current_size": snapshot.current_size,
            "item_count": snapshot.live_entries,
            "T1": {"count": len(snapshot.t1_keys), "size": snapshot.t1_size},
            "T2": {"count": len(snapshot.t2_keys), "size": snapshot.t2_size},
            "B1": {"count": len(snapshot.b1_keys), "size": 0},
            "B2": {"count": len(snapshot.b2_keys), "size": 0},
            "p": snapshot.p,
            "hits": {"t1": core.hits_t1, "t2": core.hits_t2},
            "misses": core.misses,
            "operations": core.operations,
            "evictions": core.evictions_t1 + core.evictions_t2,
            "promotions": core.promotions_t1_to_t2 + core.promotions_b1_to_t2 + core.promotions_b2_to_t2,
            "integration": self._metrics.snapshot().to_dict(),
        }

    def get_arc_metrics(self) -> dict[str, Any]:
        return self._cache.metrics().to_dict()


ARCCache = ARCache
LegacyARCache = ARCache
PersistentARC = GenerationBoundARC
GenerationBoundCache = GenerationBoundARC
PersistentARCache = GenerationBoundARC

__all__ = [
    "GENERATION_BINDING_SCHEMA", "CacheBinding", "GenerationBinding", "CacheIdentity",
    "GenerationBoundARC", "GenerationBoundCache", "PersistentARC", "PersistentARCache",
    "ARCache", "ARCCache", "LegacyARCache",
    "BloomFilter", "HyperLogLog", "CountMinSketch", "MinHash",
]
