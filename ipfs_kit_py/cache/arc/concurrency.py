"""Single-flight fill coordination for :mod:`ipfs_kit_py.cache.arc`.

Only the elected leader runs a filler.  Followers wait on the same condition
and receive the leader's terminal result, including cancellation and failure.
The in-flight dictionary is always read, added, and removed while ``_lock`` is
held; filler code runs *outside* that lock so it can safely call cache APIs or
wait for external I/O without blocking unrelated completions.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
from threading import Condition, RLock
from typing import Callable, Final

from ipfs_kit_py.cache.arc.contracts import (
    AdaptiveReplacementCache as AdaptiveReplacementCacheProtocol,
    validate_cache_key,
)


SINGLE_FLIGHT_CONTRACT_VERSION: Final[int] = 1


class FillStatus(str, Enum):
    """Terminal states returned by :meth:`SingleFlightARC.get_or_fill_result`."""

    HIT = "hit"
    FILLED = "filled"
    REJECTED = "rejected"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CacheFillError(RuntimeError):
    """A single-flight fill did not produce an admitted cache value."""


class CacheFillRejected(CacheFillError):
    """The filler completed, but the ARC contract rejected its value."""


class CacheFillCancelled(CacheFillError):
    """The in-flight fill was cancelled before it could be admitted."""


@dataclass(frozen=True)
class CacheFillResult:
    """Typed terminal result shared by a fill leader and all of its waiters."""

    key: str
    status: FillStatus
    value: bytes | None = None
    error: BaseException | None = None

    @property
    def from_cache(self) -> bool:
        return self.status is FillStatus.HIT

    @property
    def admitted(self) -> bool:
        return self.status is FillStatus.FILLED

    @property
    def ok(self) -> bool:
        return self.status in (FillStatus.HIT, FillStatus.FILLED)

    def unwrap(self) -> bytes:
        """Return the value or raise a stable, typed fill exception."""

        if self.ok:
            assert self.value is not None
            return self.value
        if self.status is FillStatus.CANCELLED:
            if isinstance(self.error, CacheFillCancelled):
                raise self.error
            raise CacheFillCancelled(f"fill for {self.key!r} was cancelled")
        if self.status is FillStatus.REJECTED:
            if isinstance(self.error, CacheFillRejected):
                raise self.error
            raise CacheFillRejected(f"fill for {self.key!r} was rejected")
        detail = f"fill for {self.key!r} failed"
        if self.error is None:
            raise CacheFillError(detail)
        raise CacheFillError(detail) from self.error


@dataclass
class _Flight:
    """Private state, accessed only while its coordinator lock is held."""

    condition: Condition
    done: bool = False
    result: CacheFillResult | None = None
    waiters: int = 0


class SingleFlightARC:
    """Coordinate synchronous cache fills for one ARC protocol implementation.

    A key has at most one active filler.  Filling is deliberately synchronous:
    callers choose their own executor or event-loop boundary, while this class
    keeps shared state under a conventional lock and never dispatches a thread
    that could mutate a shared dictionary without that guard.
    """

    def __init__(self, cache: AdaptiveReplacementCacheProtocol) -> None:
        # Use the published runtime-checkable protocol rather than coupling
        # coordination to this module's concrete lock wrapper.  That keeps the
        # single-flight primitive usable with another conforming cache while
        # retaining the lock ordering guarantees below.
        if not isinstance(cache, AdaptiveReplacementCacheProtocol):
            raise TypeError("cache must be an AdaptiveReplacementCache")
        self._cache = cache
        self._lock = RLock()
        self._flights: dict[str, _Flight] = {}

    @property
    def cache(self) -> AdaptiveReplacementCacheProtocol:
        return self._cache

    @property
    def inflight_count(self) -> int:
        with self._lock:
            return len(self._flights)

    @property
    def waiting_count(self) -> int:
        """Return followers currently blocked on an elected filler.

        This is deliberately observational: it is useful for shutdown and
        diagnostics, but callers must not use it for correctness decisions.
        """

        with self._lock:
            return sum(flight.waiters for flight in self._flights.values())

    def get_or_fill_result(
        self, key: str, filler: Callable[[], bytes]
    ) -> CacheFillResult:
        """Return a typed result, running ``filler`` once for concurrent misses.

        The linearization point for joining or creating a flight is protected by
        ``_lock``.  A cancellation can win while a leader is in user code; in
        that case the leader never admits its subsequently produced bytes.
        """

        key = validate_cache_key(key)
        if not callable(filler):
            raise TypeError("filler must be callable")

        with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                return CacheFillResult(key=key, status=FillStatus.HIT, value=cached)

            flight = self._flights.get(key)
            if flight is None:
                flight = _Flight(condition=Condition(self._lock))
                self._flights[key] = flight
                leader = True
            else:
                leader = False

            if not leader:
                # A manually cancelled leader can still be unwinding user code.
                # Keep its terminal flight installed until that leader returns so
                # a new caller cannot start a second filler concurrently with it.
                if flight.done:
                    assert flight.result is not None
                    return flight.result
                flight.waiters += 1
                try:
                    while not flight.done:
                        flight.condition.wait()
                    assert flight.result is not None
                    return flight.result
                finally:
                    flight.waiters -= 1

        # User code must never run while the coordinator lock is held.
        try:
            value = filler()
        except asyncio.CancelledError as exc:
            result = CacheFillResult(
                key=key,
                status=FillStatus.CANCELLED,
                error=CacheFillCancelled(str(exc) or f"fill for {key!r} was cancelled"),
            )
        except BaseException as exc:
            result = CacheFillResult(key=key, status=FillStatus.FAILED, error=exc)
        else:
            with self._lock:
                # Cancellation may have completed the flight while user code ran.
                if flight.done:
                    return self._retire_locked(key, flight)
                try:
                    admitted = self._cache.put(key, value)
                except BaseException as exc:
                    result = CacheFillResult(key=key, status=FillStatus.FAILED, error=exc)
                else:
                    if admitted:
                        result = CacheFillResult(
                            key=key, status=FillStatus.FILLED, value=bytes(value)
                        )
                    else:
                        result = CacheFillResult(
                            key=key,
                            status=FillStatus.REJECTED,
                            error=CacheFillRejected(
                                f"ARC rejected fill value for {key!r}"
                            ),
                        )
                return self._finish_locked(key, flight, result)

        with self._lock:
            if flight.done:
                return self._retire_locked(key, flight)
            return self._finish_locked(key, flight, result)

    def get_or_fill(self, key: str, filler: Callable[[], bytes]) -> bytes:
        """Return a cache value, raising a typed error for a terminal failure."""

        return self.get_or_fill_result(key, filler).unwrap()

    def fill_result(self, key: str, filler: Callable[[], bytes]) -> CacheFillResult:
        """Alias for callers that name the operation as a fill."""

        return self.get_or_fill_result(key, filler)

    def cancel(self, key: str) -> bool:
        """Cancel an active fill and wake every waiter with a typed result."""

        key = validate_cache_key(key)
        with self._lock:
            flight = self._flights.get(key)
            if flight is None or flight.done:
                return False
            result = CacheFillResult(
                key=key,
                status=FillStatus.CANCELLED,
                error=CacheFillCancelled(f"fill for {key!r} was cancelled"),
            )
            # The elected filler may still be running outside our lock.  Keep
            # its terminal flight registered until it returns, preventing a
            # replacement leader from executing duplicate work in that window.
            self._finish_locked(key, flight, result, retain_until_leader_returns=True)
            return True

    def _finish_locked(
        self,
        key: str,
        flight: _Flight,
        result: CacheFillResult,
        *,
        retain_until_leader_returns: bool = False,
    ) -> CacheFillResult:
        """Publish once and notify waiters while holding the coordinator lock."""

        if flight.done:
            assert flight.result is not None
            return flight.result
        flight.result = result
        flight.done = True
        # Do not remove a later flight if future maintenance changes ordering.
        if not retain_until_leader_returns and self._flights.get(key) is flight:
            del self._flights[key]
        flight.condition.notify_all()
        return result

    def _retire_locked(self, key: str, flight: _Flight) -> CacheFillResult:
        """Retire a manually-cancelled flight after its leader leaves user code."""

        assert flight.done
        assert flight.result is not None
        if self._flights.get(key) is flight:
            del self._flights[key]
        return flight.result


SingleFlight = SingleFlightARC
SingleFlightCache = SingleFlightARC
ARCFillCoordinator = SingleFlightARC


__all__ = [
    "SINGLE_FLIGHT_CONTRACT_VERSION",
    "FillStatus",
    "CacheFillError",
    "CacheFillRejected",
    "CacheFillCancelled",
    "CacheFillResult",
    "SingleFlightARC",
    "SingleFlight",
    "SingleFlightCache",
    "ARCFillCoordinator",
]
