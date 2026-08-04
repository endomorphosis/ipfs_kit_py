"""Thread-safe ARC cache implementation (KITA-023).

The ARC transition rules deliberately live in :mod:`reference`.  This class
serializes access to that deterministic state machine instead of maintaining a
second, almost-identical set of ordered dictionaries.  Consequently every
completed method call has one linearization point: acquisition of ``_lock``.
That is especially important for byte accounting and ghost-list adaptation,
where splitting a transition over several locks would make a cache history
impossible to replay.
"""

from __future__ import annotations

from collections.abc import Sequence
from copy import deepcopy
from threading import RLock
from typing import Any, ClassVar, Final

from ipfs_kit_py.cache.arc.contracts import (
    ADAPTIVE_REPLACEMENT_CACHE_SCHEMA,
    ARCConfig,
    ARCMetrics,
    ARCOperation,
    ARCOutcome,
    ARCSnapshot,
    AdaptiveReplacementCache_V1,
)
from ipfs_kit_py.cache.arc.reference import ARCReferenceModel


CACHE_CONTRACT_VERSION: Final[int] = 1
CACHE_SCHEMA: Final[str] = ADAPTIVE_REPLACEMENT_CACHE_SCHEMA
AdaptiveReplacementCache_V1_ThreadSafe: Final[str] = CACHE_SCHEMA


class AdaptiveReplacementCache:
    """A linearizable, byte-aware Adaptive Replacement Cache.

    The wrapped reference model owns all ARC state.  No mutable cache state is
    exposed, and every read that observes state is protected too: a snapshot,
    metrics record, or trace therefore describes a real completed cache state.
    ``RLock`` makes compound calls such as :meth:`run_trace` safe without
    needing a separate, error-prone internal locking convention.
    """

    SCHEMA: ClassVar[str] = CACHE_SCHEMA
    CONTRACT_VERSION: ClassVar[int] = CACHE_CONTRACT_VERSION
    INTERFACE: ClassVar[str] = AdaptiveReplacementCache_V1

    def __init__(self, config: ARCConfig | None = None, **kwargs: Any) -> None:
        self._lock = RLock()
        self._model = ARCReferenceModel(config, **kwargs)

    @property
    def config(self) -> ARCConfig:
        with self._lock:
            return self._model.config

    @property
    def capacity_bytes(self) -> int:
        with self._lock:
            return self._model.capacity_bytes

    @property
    def current_size(self) -> int:
        with self._lock:
            return self._model.current_size

    @property
    def p(self) -> int:
        with self._lock:
            return self._model.p

    @property
    def t1_size(self) -> int:
        with self._lock:
            return self._model.t1_size

    @property
    def t2_size(self) -> int:
        with self._lock:
            return self._model.t2_size

    @property
    def trace(self) -> tuple[dict[str, Any], ...]:
        """Return an immutable trace container with private record copies.

        ``ARCReferenceModel.trace`` intentionally returns its record mappings
        for lightweight oracle use.  Returning copies here prevents an outside
        thread from mutating an observed trace while another thread reads it.
        """

        with self._lock:
            return tuple(deepcopy(record) for record in self._model.trace)

    def contains(self, key: str) -> bool:
        with self._lock:
            return self._model.contains(key)

    def locate(self, key: str) -> str | None:
        with self._lock:
            return self._model.locate(key)

    def snapshot(self) -> ARCSnapshot:
        with self._lock:
            return self._model.snapshot()

    def metrics(self) -> ARCMetrics:
        with self._lock:
            return self._model.metrics()

    def assert_invariants(self) -> None:
        with self._lock:
            self._model.assert_invariants()

    def get(self, key: str) -> bytes | None:
        # KITA-044: admit under the process-wide hot-path bound before the
        # linearization lock so overload fails closed without unbounded queues.
        from ipfs_kit_py.core.performance import HotPathGate

        with HotPathGate(payload_bytes=0, fairness_class="arc-get"):
            with self._lock:
                return self._model.get(key)

    def put(self, key: str, value: bytes) -> bool:
        from ipfs_kit_py.core.performance import HotPathGate

        payload = len(value) if isinstance(value, (bytes, bytearray)) else 0
        with HotPathGate(payload_bytes=payload, fairness_class="arc-put"):
            with self._lock:
                return self._model.put(key, value)

    def delete(self, key: str) -> bool:
        with self._lock:
            return self._model.delete(key)

    def clear(self) -> None:
        with self._lock:
            self._model.clear()

    def apply(self, operation: ARCOperation) -> ARCOutcome:
        """Atomically apply one closed ARC operation."""

        with self._lock:
            return self._model.apply(operation)

    def run_trace(self, operations: Sequence[ARCOperation]) -> list[ARCOutcome]:
        """Atomically apply a bounded trace in its supplied order."""

        with self._lock:
            return self._model.run_trace(operations)


# Descriptive aliases are intentionally the same implementation, not wrappers:
# all of them retain the same single lock and linearization guarantees.
ThreadSafeAdaptiveReplacementCache = AdaptiveReplacementCache
ConcurrentAdaptiveReplacementCache = AdaptiveReplacementCache
ARCConcurrentCache = AdaptiveReplacementCache


__all__ = [
    "CACHE_CONTRACT_VERSION",
    "CACHE_SCHEMA",
    "AdaptiveReplacementCache_V1_ThreadSafe",
    "AdaptiveReplacementCache",
    "ThreadSafeAdaptiveReplacementCache",
    "ConcurrentAdaptiveReplacementCache",
    "ARCConcurrentCache",
]
