"""Integration telemetry for the ARC migration layer.

The ARC core exposes algorithm counters.  This module deliberately keeps the
integration counters separate: an authorization denial is not an ARC miss and
a persistence decode failure is not an eviction.  The collector is small,
thread-safe, and never retains cache values.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from threading import RLock
from time import monotonic
from typing import Final


METRICS_SCHEMA: Final[str] = "ipfs_kit_py/cache/arc/integration-metrics@1"


@dataclass(frozen=True)
class AccessTiming:
    """Timing captured before an access changes its recency state."""

    previous_access: float | None
    accessed_at: float
    age: float | None


@dataclass(frozen=True)
class ARCIntegrationMetrics:
    """Immutable, value-free snapshot of migration-layer events."""

    live_hits: int = 0
    ghost_hits: int = 0
    stale_rejections: int = 0
    authorization_rejections: int = 0
    consistency_rejections: int = 0
    admission_rejections: int = 0
    evictions: int = 0
    fills_started: int = 0
    fills_succeeded: int = 0
    fills_failed: int = 0
    fills_cancelled: int = 0
    persistence_writes: int = 0
    persistence_loads: int = 0
    persistence_corrupt: int = 0
    persistence_schema_rejections: int = 0
    persistence_stale_rejections: int = 0

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


class ARCIntegrationMetricsCollector:
    """Linearizable counters and pre-access recency timestamps.

    ``record_access`` reads the old timestamp before replacing it.  This is
    important: a score based on a timestamp written during the same lookup is
    always zero and cannot describe recency.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._counts = {name: 0 for name in ARCIntegrationMetrics.__dataclass_fields__}
        self._accesses: dict[str, float] = {}

    def increment(self, name: str, count: int = 1) -> None:
        if name not in self._counts:
            raise ValueError(f"unknown ARC integration metric: {name}")
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ValueError("metric count must be a non-negative integer")
        with self._lock:
            self._counts[name] += count

    def record_access(self, key: str, *, now: float | None = None) -> AccessTiming:
        observed = monotonic() if now is None else now
        if not isinstance(observed, (int, float)) or isinstance(observed, bool):
            raise ValueError("access time must be numeric")
        observed = float(observed)
        with self._lock:
            previous = self._accesses.get(key)
            # Capture the age from the *previous* observation, then update.
            age = None if previous is None else max(0.0, observed - previous)
            self._accesses[key] = observed
            return AccessTiming(previous, observed, age)

    def forget(self, key: str) -> None:
        with self._lock:
            self._accesses.pop(key, None)

    def snapshot(self) -> ARCIntegrationMetrics:
        with self._lock:
            return ARCIntegrationMetrics(**self._counts)


# Short aliases make the public surface discoverable without introducing a
# second metrics implementation.
Metrics = ARCIntegrationMetrics
MetricsCollector = ARCIntegrationMetricsCollector

__all__ = [
    "METRICS_SCHEMA",
    "AccessTiming",
    "ARCIntegrationMetrics",
    "ARCIntegrationMetricsCollector",
    "Metrics",
    "MetricsCollector",
]
