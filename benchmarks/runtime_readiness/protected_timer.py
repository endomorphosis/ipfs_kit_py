"""Immutable wall-clock primitive for production-bound benchmark samples.

KITA-043 and KITA-044 deliberately do not own this file.  A benchmark adapter
supplies the operation label and callback; this function executes the callback
and returns its value together with independently measured monotonic elapsed
seconds.  Exceptions propagate and therefore cannot become successful timing
samples.
"""

from __future__ import annotations

import time
from typing import Any, Callable, TypeVar


T = TypeVar("T")
_PERF_COUNTER_NS = time.perf_counter_ns


def monotonic_sample_timer(
    operation: str, execute: Callable[[], T]
) -> tuple[T, float]:
    if not isinstance(operation, str) or not operation:
        raise ValueError("operation must be a non-empty string")
    if not callable(execute):
        raise TypeError("execute must be callable")
    started_ns = _PERF_COUNTER_NS()
    value = execute()
    elapsed_ns = max(1, _PERF_COUNTER_NS() - started_ns)
    return value, elapsed_ns / 1_000_000_000.0


__all__ = ["monotonic_sample_timer"]
