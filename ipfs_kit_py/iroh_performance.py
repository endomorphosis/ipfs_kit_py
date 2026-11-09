"""Reproducible performance receipts for the Iroh fsspec adapter.

The checked-in baseline is intentionally a deterministic, in-memory floor.
It catches algorithmic regressions and unbounded resource use without making
claims about a particular peer network.  Operators can feed samples from a
real sidecar into :func:`evaluate_sample` using the same field names.
"""

from __future__ import annotations

import json
import math
import statistics
import time
from dataclasses import asdict, dataclass
from importlib.resources import files
from typing import Any, Mapping


BASELINE_RESOURCE = "iroh-performance-baseline.json"


@dataclass(frozen=True, slots=True)
class IrohPerformanceSample:
    """Portable metrics emitted by :func:`benchmark_async_filesystem`."""

    metadata_p95_ms: float
    warm_range_p95_ms: float
    sequential_read_mib_s: float
    parallel_read_mib_s: float
    retained_cache_bytes: int
    largest_transport_read_bytes: int | None = None
    peak_active_operations: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_iroh_performance_baseline() -> dict[str, Any]:
    """Load and minimally validate the packaged regression baseline."""

    resource = files("ipfs_kit_py.resources").joinpath(BASELINE_RESOURCE)
    value = json.loads(resource.read_text(encoding="utf-8"))
    if value.get("schema_version") != 1:
        raise ValueError("unsupported Iroh performance baseline schema")
    if not isinstance(value.get("workload"), Mapping) or not isinstance(
        value.get("budgets"), Mapping
    ):
        raise ValueError("invalid Iroh performance baseline")
    return value


def _p95(values: list[float]) -> float:
    if not values:
        raise ValueError("at least one timing sample is required")
    if len(values) == 1:
        return values[0]
    # Inclusive quantiles are stable for the small, fixed benchmark sample.
    return statistics.quantiles(values, n=20, method="inclusive")[18]


async def benchmark_async_filesystem(
    filesystem: Any,
    path: str,
    *,
    payload_bytes: int | None = None,
    range_bytes: int | None = None,
    iterations: int | None = None,
    parallelism: int | None = None,
) -> IrohPerformanceSample:
    """Measure the standard metadata, range, and transfer workloads.

    The supplied object follows fsspec's async convention (``_info`` and
    ``_cat_file``).  Timing uses ``perf_counter`` and returns data rather than
    printing, making the runner usable from pytest, CI, or an operator CLI.
    """

    baseline = load_iroh_performance_baseline()
    workload = baseline["workload"]
    payload_bytes = int(payload_bytes or workload["payload_bytes"])
    range_bytes = int(range_bytes or workload["range_bytes"])
    iterations = int(iterations or workload["iterations"])
    parallelism = int(parallelism or workload["parallelism"])
    if min(payload_bytes, range_bytes, iterations, parallelism) <= 0:
        raise ValueError("benchmark workload values must be positive")

    metadata_times: list[float] = []
    for _ in range(iterations):
        started = time.perf_counter()
        await filesystem._info(path)
        metadata_times.append((time.perf_counter() - started) * 1000.0)

    # Prime the immutable range cache before measuring its steady state.
    await filesystem._cat_file(path, start=0, end=range_bytes)
    range_times: list[float] = []
    for _ in range(iterations):
        started = time.perf_counter()
        await filesystem._cat_file(path, start=0, end=range_bytes)
        range_times.append((time.perf_counter() - started) * 1000.0)

    started = time.perf_counter()
    value = await filesystem._cat_file(path, start=0, end=payload_bytes)
    elapsed = max(time.perf_counter() - started, 1e-12)
    sequential = len(value) / (1024.0 * 1024.0) / elapsed

    requests = [
        (
            index * range_bytes % payload_bytes,
            min(index * range_bytes % payload_bytes + range_bytes, payload_bytes),
        )
        for index in range(parallelism)
    ]
    started = time.perf_counter()
    if hasattr(filesystem, "_cat_ranges"):
        values = await filesystem._cat_ranges(
            [path] * parallelism,
            [item[0] for item in requests],
            [item[1] for item in requests],
        )
    else:  # pragma: no cover - compatibility for third-party adapters
        import anyio

        values = [None] * parallelism

        async def read(index: int, start: int, end: int) -> None:
            values[index] = await filesystem._cat_file(path, start=start, end=end)

        async with anyio.create_task_group() as group:
            for index, (start, end) in enumerate(requests):
                group.start_soon(read, index, start, end)
    elapsed = max(time.perf_counter() - started, 1e-12)
    transferred = sum(len(value) for value in values if isinstance(value, bytes))
    parallel = transferred / (1024.0 * 1024.0) / elapsed

    cache = filesystem.cache_info() if hasattr(filesystem, "cache_info") else {}
    return IrohPerformanceSample(
        metadata_p95_ms=_p95(metadata_times),
        warm_range_p95_ms=_p95(range_times),
        sequential_read_mib_s=sequential,
        parallel_read_mib_s=parallel,
        retained_cache_bytes=int(cache.get("bytes", 0)),
    )


def evaluate_sample(
    sample: IrohPerformanceSample | Mapping[str, Any],
    baseline: Mapping[str, Any] | None = None,
) -> list[str]:
    """Return stable budget violation labels; an empty list is a pass."""

    baseline = baseline or load_iroh_performance_baseline()
    budgets = baseline["budgets"]
    values = sample.as_dict() if isinstance(sample, IrohPerformanceSample) else dict(sample)
    checks = (
        ("metadata_p95_ms", "metadata_p95_ms", "max"),
        ("warm_range_p95_ms", "warm_range_p95_ms", "max"),
        ("sequential_read_mib_s", "sequential_read_min_mib_s", "min"),
        ("parallel_read_mib_s", "parallel_read_min_mib_s", "min"),
        ("retained_cache_bytes", "retained_cache_max_bytes", "max"),
        ("largest_transport_read_bytes", "transport_read_max_bytes", "max"),
        ("peak_active_operations", "active_operations_max", "max"),
    )
    violations: list[str] = []
    for field, budget_field, direction in checks:
        actual = values.get(field)
        if actual is None:
            continue
        if isinstance(actual, bool) or not isinstance(actual, (int, float)) or not math.isfinite(actual):
            violations.append(f"{field}:invalid")
            continue
        budget = budgets[budget_field]
        if (direction == "max" and actual > budget) or (
            direction == "min" and actual < budget
        ):
            violations.append(field)
    return violations


__all__ = [
    "BASELINE_RESOURCE",
    "IrohPerformanceSample",
    "load_iroh_performance_baseline",
    "benchmark_async_filesystem",
    "evaluate_sample",
]
