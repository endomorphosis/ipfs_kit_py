"""ARC reference model — pure deterministic state machine (KITA-022).

``ARCReferenceModel@1`` is an independent oracle for Adaptive Replacement
Cache behaviour under entry and byte budgets.  It enforces:

* ``current_size == T1_size + T2_size`` and ``current_size ≤ capacity``;
* T1 / T2 / B1 / B2 pairwise disjoint;
* ghost lists retain keys (and optional last_size) only — never values;
* adaptive target ``p`` bounded in ``[0, capacity_bytes]``;
* exact update / growth / ghost-hit byte accounting;
* deterministic LRU eviction (OrderedDict insertion order); and
* rejection of invalid keys, sizes, capacities, and unbounded values.

Property strategies emit **reproducible minimal traces** from an integer
seed so differential and invariant tests are hermetic.

The reference model does **not** import the legacy ``arc_cache`` module.
"""

from __future__ import annotations

import random
from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, ClassVar, Final

from ipfs_kit_py.cache.arc.contracts import (
    ARC_REFERENCE_MODEL_SCHEMA,
    ARCConfig,
    ARCHitKind,
    ARCInvariantError,
    ARCKeyError,
    ARCMetrics,
    ARCOperation,
    ARCOperationError,
    ARCOperationKind,
    ARCOutcome,
    ARCOutcomeKind,
    ARCSnapshot,
    ARCValueError,
    AdaptiveReplacementCache_V1,
    DEFAULT_CAPACITY_BYTES,
    GhostEntry,
    LiveEntry,
    MAX_TRACE_OPS,
    assert_arc_invariants,
    validate_cache_key,
    validate_value,
)

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

REFERENCE_MODEL_CONTRACT_VERSION: Final[int] = 1
REFERENCE_MODEL_SCHEMA: Final[str] = ARC_REFERENCE_MODEL_SCHEMA
ARCReferenceModel_V1: Final[str] = REFERENCE_MODEL_SCHEMA


# ---------------------------------------------------------------------------
# Mutable metrics (internal)
# ---------------------------------------------------------------------------


@dataclass
class _Metrics:
    operations: int = 0
    hits_t1: int = 0
    hits_t2: int = 0
    misses: int = 0
    ghost_hits_b1: int = 0
    ghost_hits_b2: int = 0
    puts: int = 0
    updates: int = 0
    deletes: int = 0
    rejections: int = 0
    evictions_t1: int = 0
    evictions_t2: int = 0
    promotions_t1_to_t2: int = 0
    promotions_b1_to_t2: int = 0
    promotions_b2_to_t2: int = 0
    p_adjustments: int = 0
    ghost_prunes: int = 0
    bytes_admitted: int = 0
    bytes_evicted: int = 0
    bytes_updated_delta: int = 0

    def freeze(self) -> ARCMetrics:
        return ARCMetrics(
            operations=self.operations,
            hits_t1=self.hits_t1,
            hits_t2=self.hits_t2,
            misses=self.misses,
            ghost_hits_b1=self.ghost_hits_b1,
            ghost_hits_b2=self.ghost_hits_b2,
            puts=self.puts,
            updates=self.updates,
            deletes=self.deletes,
            rejections=self.rejections,
            evictions_t1=self.evictions_t1,
            evictions_t2=self.evictions_t2,
            promotions_t1_to_t2=self.promotions_t1_to_t2,
            promotions_b1_to_t2=self.promotions_b1_to_t2,
            promotions_b2_to_t2=self.promotions_b2_to_t2,
            p_adjustments=self.p_adjustments,
            ghost_prunes=self.ghost_prunes,
            bytes_admitted=self.bytes_admitted,
            bytes_evicted=self.bytes_evicted,
            bytes_updated_delta=self.bytes_updated_delta,
        )


# ---------------------------------------------------------------------------
# Reference model
# ---------------------------------------------------------------------------


class ARCReferenceModel:
    """Pure deterministic ARC state machine (``ARCReferenceModel@1``).

    Algorithm (byte-aware generalization of Megiddo & Modha ARC):

    * **T1** — recency live list (LRU → MRU via :class:`OrderedDict`).
    * **T2** — frequency live list.
    * **B1** / **B2** — ghost histories (keys + last_size only).
    * **p** — target size in bytes for T1, always ``0 ≤ p ≤ capacity``.
    * On B1 ghost hit: increase ``p`` by ``size * max(1, |B2| // max(|B1|, 1))``.
    * On B2 ghost hit: decrease ``p`` by ``size * max(1, |B1| // max(|B2|, 1))``.
    * Eviction prefers T1 when ``T1_size > p`` (or T2 empty); otherwise T2.
    * Ghost lists are pruned to ``max_ghost_entries`` (combined) deterministically.

    Every public mutator ends with :meth:`assert_invariants`.
    """

    SCHEMA: ClassVar[str] = REFERENCE_MODEL_SCHEMA
    CONTRACT_VERSION: ClassVar[int] = REFERENCE_MODEL_CONTRACT_VERSION
    INTERFACE: ClassVar[str] = AdaptiveReplacementCache_V1

    def __init__(self, config: ARCConfig | None = None, **kwargs: Any) -> None:
        if config is None:
            if kwargs:
                config = ARCConfig(**kwargs)
            else:
                config = ARCConfig(capacity_bytes=DEFAULT_CAPACITY_BYTES)
        elif kwargs:
            raise TypeError("pass either config or keyword budgets, not both")
        self._config = config
        # OrderedDict: first = LRU, last = MRU.
        self._t1: OrderedDict[str, LiveEntry] = OrderedDict()
        self._t2: OrderedDict[str, LiveEntry] = OrderedDict()
        self._b1: OrderedDict[str, GhostEntry] = OrderedDict()
        self._b2: OrderedDict[str, GhostEntry] = OrderedDict()
        self._t1_size: int = 0
        self._t2_size: int = 0
        self._p: int = config.initial_p
        self._metrics = _Metrics()
        self._trace: list[dict[str, Any]] = []
        self.assert_invariants()

    # -- properties ---------------------------------------------------------

    @property
    def config(self) -> ARCConfig:
        return self._config

    @property
    def capacity_bytes(self) -> int:
        return self._config.capacity_bytes

    @property
    def current_size(self) -> int:
        return self._t1_size + self._t2_size

    @property
    def p(self) -> int:
        return self._p

    @property
    def t1_size(self) -> int:
        return self._t1_size

    @property
    def t2_size(self) -> int:
        return self._t2_size

    @property
    def trace(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._trace)

    # -- inspection ---------------------------------------------------------

    def contains(self, key: str) -> bool:
        key = validate_cache_key(key)
        return key in self._t1 or key in self._t2

    def locate(self, key: str) -> str | None:
        """Return list name for key, or None if unknown."""

        key = validate_cache_key(key)
        if key in self._t1:
            return "T1"
        if key in self._t2:
            return "T2"
        if key in self._b1:
            return "B1"
        if key in self._b2:
            return "B2"
        return None

    def snapshot(self) -> ARCSnapshot:
        return ARCSnapshot(
            capacity_bytes=self.capacity_bytes,
            current_size=self.current_size,
            t1_size=self._t1_size,
            t2_size=self._t2_size,
            p=self._p,
            t1_keys=tuple(self._t1.keys()),
            t2_keys=tuple(self._t2.keys()),
            b1_keys=tuple(self._b1.keys()),
            b2_keys=tuple(self._b2.keys()),
            t1_sizes=tuple(e.size for e in self._t1.values()),
            t2_sizes=tuple(e.size for e in self._t2.values()),
            live_entries=len(self._t1) + len(self._t2),
            ghost_entries=len(self._b1) + len(self._b2),
        )

    def metrics(self) -> ARCMetrics:
        return self._metrics.freeze()

    def assert_invariants(self) -> None:
        """Fail closed if any reference-model invariant is violated."""

        ghost_payloads: list[Any] = list(self._b1.values()) + list(self._b2.values())
        # Also assert OrderedDict values never smuggle a ``value`` field.
        for ghost in ghost_payloads:
            if isinstance(ghost, GhostEntry) and hasattr(type(ghost), "value"):
                # dataclass may not define value; only reject real payloads.
                pass
            if getattr(ghost, "value", None) is not None:
                raise ARCInvariantError("ghost entry retained a value payload")
        assert_arc_invariants(
            capacity_bytes=self.capacity_bytes,
            current_size=self.current_size,
            t1_size=self._t1_size,
            t2_size=self._t2_size,
            p=self._p,
            t1_keys=tuple(self._t1.keys()),
            t2_keys=tuple(self._t2.keys()),
            b1_keys=tuple(self._b1.keys()),
            b2_keys=tuple(self._b2.keys()),
            t1_sizes=tuple(e.size for e in self._t1.values()),
            t2_sizes=tuple(e.size for e in self._t2.values()),
            ghost_payloads=ghost_payloads,
            max_live_entries=self._config.max_live_entries,
            max_ghost_entries=self._config.max_ghost_entries,
        )
        # Ghost entries must be GhostEntry instances (no LiveEntry leakage).
        for entry in ghost_payloads:
            if not isinstance(entry, GhostEntry):
                raise ARCInvariantError(
                    f"ghost list contains non-GhostEntry: {type(entry).__name__}"
                )
            if isinstance(entry, LiveEntry):
                raise ARCInvariantError("ghost list contains LiveEntry")

    # -- core operations ----------------------------------------------------

    def get(self, key: str) -> bytes | None:
        """Lookup with T1→T2 promotion on recency hit; T2 re-MRU on frequency hit."""

        key = validate_cache_key(key)
        self._metrics.operations += 1
        p_before = self._p

        if key in self._t1:
            entry = self._t1.pop(key)
            self._t1_size -= entry.size
            self._t2[key] = entry
            self._t2.move_to_end(key)
            self._t2_size += entry.size
            self._metrics.hits_t1 += 1
            self._metrics.promotions_t1_to_t2 += 1
            outcome = ARCOutcome(
                kind=ARCOutcomeKind.SUCCESS,
                hit=ARCHitKind.T1,
                key=key,
                found=True,
                admitted=True,
                value_size=entry.size,
                p_before=p_before,
                p_after=self._p,
                current_size=self.current_size,
            )
            self._record(ARCOperationKind.GET, outcome)
            self.assert_invariants()
            return entry.value

        if key in self._t2:
            entry = self._t2[key]
            self._t2.move_to_end(key)
            self._metrics.hits_t2 += 1
            outcome = ARCOutcome(
                kind=ARCOutcomeKind.SUCCESS,
                hit=ARCHitKind.T2,
                key=key,
                found=True,
                admitted=True,
                value_size=entry.size,
                p_before=p_before,
                p_after=self._p,
                current_size=self.current_size,
            )
            self._record(ARCOperationKind.GET, outcome)
            self.assert_invariants()
            return entry.value

        self._metrics.misses += 1
        outcome = ARCOutcome(
            kind=ARCOutcomeKind.MISS,
            hit=ARCHitKind.MISS,
            key=key,
            found=False,
            admitted=False,
            p_before=p_before,
            p_after=self._p,
            current_size=self.current_size,
        )
        self._record(ARCOperationKind.GET, outcome)
        self.assert_invariants()
        return None

    def put(self, key: str, value: bytes) -> bool:
        """Admit or update ``key`` with exact byte accounting and eviction."""

        try:
            key = validate_cache_key(key)
            data = validate_value(value, capacity_bytes=self.capacity_bytes)
        except (ARCKeyError, ARCValueError) as exc:
            self._metrics.operations += 1
            self._metrics.rejections += 1
            outcome = ARCOutcome(
                kind=ARCOutcomeKind.REJECTED,
                hit=ARCHitKind.REJECTED,
                key=str(key) if isinstance(key, str) else None,
                found=False,
                admitted=False,
                p_before=self._p,
                p_after=self._p,
                current_size=self.current_size,
                error=str(exc),
            )
            self._record(ARCOperationKind.PUT, outcome)
            self.assert_invariants()
            return False

        size = len(data)
        self._metrics.operations += 1
        p_before = self._p
        evicted: list[str] = []

        # Update in place (T1 or T2).
        if key in self._t1:
            old = self._t1[key]
            delta = size - old.size
            if self.current_size + delta > self.capacity_bytes:
                # Need room for growth; temporary remove, replace, reinsert.
                self._t1.pop(key)
                self._t1_size -= old.size
                evicted.extend(self._replace(size))
                if self.current_size + size > self.capacity_bytes:
                    # Cannot admit growth; restore old entry.
                    self._t1[key] = old
                    self._t1_size += old.size
                    self._metrics.rejections += 1
                    outcome = ARCOutcome(
                        kind=ARCOutcomeKind.REJECTED,
                        hit=ARCHitKind.T1,
                        key=key,
                        found=True,
                        admitted=False,
                        value_size=size,
                        evicted_keys=tuple(evicted),
                        p_before=p_before,
                        p_after=self._p,
                        current_size=self.current_size,
                        error="update exceeds capacity after eviction",
                    )
                    self._record(ARCOperationKind.PUT, outcome)
                    self.assert_invariants()
                    return False
                # Drop from ghosts if present (should not be).
                self._b1.pop(key, None)
                self._b2.pop(key, None)
                self._t1[key] = LiveEntry(key=key, size=size, value=data)
                self._t1.move_to_end(key)
                self._t1_size += size
            else:
                self._t1[key] = LiveEntry(key=key, size=size, value=data)
                self._t1.move_to_end(key)
                self._t1_size += delta
            self._metrics.updates += 1
            self._metrics.bytes_updated_delta += delta
            outcome = ARCOutcome(
                kind=ARCOutcomeKind.SUCCESS,
                hit=ARCHitKind.T1,
                key=key,
                found=True,
                admitted=True,
                value_size=size,
                evicted_keys=tuple(evicted),
                p_before=p_before,
                p_after=self._p,
                current_size=self.current_size,
            )
            self._record(ARCOperationKind.PUT, outcome)
            self.assert_invariants()
            return True

        if key in self._t2:
            old = self._t2[key]
            delta = size - old.size
            if self.current_size + delta > self.capacity_bytes:
                self._t2.pop(key)
                self._t2_size -= old.size
                evicted.extend(self._replace(size))
                if self.current_size + size > self.capacity_bytes:
                    self._t2[key] = old
                    self._t2_size += old.size
                    self._metrics.rejections += 1
                    outcome = ARCOutcome(
                        kind=ARCOutcomeKind.REJECTED,
                        hit=ARCHitKind.T2,
                        key=key,
                        found=True,
                        admitted=False,
                        value_size=size,
                        evicted_keys=tuple(evicted),
                        p_before=p_before,
                        p_after=self._p,
                        current_size=self.current_size,
                        error="update exceeds capacity after eviction",
                    )
                    self._record(ARCOperationKind.PUT, outcome)
                    self.assert_invariants()
                    return False
                self._b1.pop(key, None)
                self._b2.pop(key, None)
                self._t2[key] = LiveEntry(key=key, size=size, value=data)
                self._t2.move_to_end(key)
                self._t2_size += size
            else:
                self._t2[key] = LiveEntry(key=key, size=size, value=data)
                self._t2.move_to_end(key)
                self._t2_size += delta
            self._metrics.updates += 1
            self._metrics.bytes_updated_delta += delta
            outcome = ARCOutcome(
                kind=ARCOutcomeKind.SUCCESS,
                hit=ARCHitKind.T2,
                key=key,
                found=True,
                admitted=True,
                value_size=size,
                evicted_keys=tuple(evicted),
                p_before=p_before,
                p_after=self._p,
                current_size=self.current_size,
            )
            self._record(ARCOperationKind.PUT, outcome)
            self.assert_invariants()
            return True

        # Ghost hit B1 → adapt p up, admit into T2.
        if key in self._b1:
            self._adapt_on_b1_hit(size)
            self._b1.pop(key)
            self._metrics.ghost_hits_b1 += 1
            hit_kind = ARCHitKind.B1
            promotion = "b1_to_t2"
        elif key in self._b2:
            self._adapt_on_b2_hit(size)
            self._b2.pop(key)
            self._metrics.ghost_hits_b2 += 1
            hit_kind = ARCHitKind.B2
            promotion = "b2_to_t2"
        else:
            hit_kind = ARCHitKind.MISS
            promotion = "new_t1"

        # Entry-count budget for live set.
        if (
            len(self._t1) + len(self._t2) >= self._config.max_live_entries
            and hit_kind is ARCHitKind.MISS
        ):
            # Force one eviction path by requesting room for a synthetic unit.
            if self._t1 or self._t2:
                evicted.extend(self._evict_one(prefer_t1=self._t1_size > self._p))

        evicted.extend(self._replace(size))
        if self.current_size + size > self.capacity_bytes:
            self._metrics.rejections += 1
            outcome = ARCOutcome(
                kind=ARCOutcomeKind.REJECTED,
                hit=hit_kind,
                key=key,
                found=False,
                admitted=False,
                value_size=size,
                evicted_keys=tuple(evicted),
                p_before=p_before,
                p_after=self._p,
                current_size=self.current_size,
                error="cannot free enough capacity",
            )
            self._record(ARCOperationKind.PUT, outcome)
            self.assert_invariants()
            return False

        entry = LiveEntry(key=key, size=size, value=data)
        if promotion in ("b1_to_t2", "b2_to_t2"):
            self._t2[key] = entry
            self._t2.move_to_end(key)
            self._t2_size += size
            if promotion == "b1_to_t2":
                self._metrics.promotions_b1_to_t2 += 1
            else:
                self._metrics.promotions_b2_to_t2 += 1
        else:
            # Completely new → T1.
            self._t1[key] = entry
            self._t1.move_to_end(key)
            self._t1_size += size

        self._metrics.puts += 1
        self._metrics.bytes_admitted += size
        self._prune_ghosts()
        outcome = ARCOutcome(
            kind=ARCOutcomeKind.SUCCESS,
            hit=hit_kind,
            key=key,
            found=hit_kind is not ARCHitKind.MISS,
            admitted=True,
            value_size=size,
            evicted_keys=tuple(evicted),
            p_before=p_before,
            p_after=self._p,
            current_size=self.current_size,
        )
        self._record(ARCOperationKind.PUT, outcome)
        self.assert_invariants()
        return True

    def delete(self, key: str) -> bool:
        """Explicitly evict a live key into the appropriate ghost list."""

        key = validate_cache_key(key)
        self._metrics.operations += 1
        p_before = self._p

        if key in self._t1:
            entry = self._t1.pop(key)
            self._t1_size -= entry.size
            self._to_ghost(key, entry.size, to_b1=True)
            self._metrics.deletes += 1
            self._metrics.evictions_t1 += 1
            self._metrics.bytes_evicted += entry.size
            self._prune_ghosts()
            outcome = ARCOutcome(
                kind=ARCOutcomeKind.SUCCESS,
                hit=ARCHitKind.T1,
                key=key,
                found=True,
                admitted=False,
                value_size=entry.size,
                evicted_keys=(key,),
                p_before=p_before,
                p_after=self._p,
                current_size=self.current_size,
            )
            self._record(ARCOperationKind.DELETE, outcome)
            self.assert_invariants()
            return True

        if key in self._t2:
            entry = self._t2.pop(key)
            self._t2_size -= entry.size
            self._to_ghost(key, entry.size, to_b1=False)
            self._metrics.deletes += 1
            self._metrics.evictions_t2 += 1
            self._metrics.bytes_evicted += entry.size
            self._prune_ghosts()
            outcome = ARCOutcome(
                kind=ARCOutcomeKind.SUCCESS,
                hit=ARCHitKind.T2,
                key=key,
                found=True,
                admitted=False,
                value_size=entry.size,
                evicted_keys=(key,),
                p_before=p_before,
                p_after=self._p,
                current_size=self.current_size,
            )
            self._record(ARCOperationKind.DELETE, outcome)
            self.assert_invariants()
            return True

        outcome = ARCOutcome(
            kind=ARCOutcomeKind.MISS,
            hit=ARCHitKind.MISS,
            key=key,
            found=False,
            admitted=False,
            p_before=p_before,
            p_after=self._p,
            current_size=self.current_size,
        )
        self._record(ARCOperationKind.DELETE, outcome)
        self.assert_invariants()
        return False

    def clear(self) -> None:
        """Drop all live and ghost state; reset ``p`` to ``initial_p``."""

        self._metrics.operations += 1
        self._t1.clear()
        self._t2.clear()
        self._b1.clear()
        self._b2.clear()
        self._t1_size = 0
        self._t2_size = 0
        self._p = self._config.initial_p
        outcome = ARCOutcome(
            kind=ARCOutcomeKind.SUCCESS,
            hit=ARCHitKind.MISS,
            found=False,
            admitted=False,
            p_before=self._p,
            p_after=self._p,
            current_size=0,
        )
        self._record(ARCOperationKind.CLEAR, outcome)
        self.assert_invariants()

    def apply(self, operation: ARCOperation) -> ARCOutcome:
        """Apply one closed operation; return the outcome record."""

        if not isinstance(operation, ARCOperation):
            raise ARCOperationError("apply requires ARCOperation")
        kind = operation.kind
        if kind is ARCOperationKind.GET:
            assert operation.key is not None
            before = len(self._trace)
            self.get(operation.key)
            return self._outcome_from_trace(before)
        if kind is ARCOperationKind.PUT:
            assert operation.key is not None
            if operation.value is not None:
                value = operation.value
            elif operation.size is not None:
                value = b"\x00" * operation.size
            else:
                raise ARCOperationError("put requires value or size")
            before = len(self._trace)
            self.put(operation.key, value)
            return self._outcome_from_trace(before)
        if kind is ARCOperationKind.DELETE:
            assert operation.key is not None
            before = len(self._trace)
            self.delete(operation.key)
            return self._outcome_from_trace(before)
        if kind is ARCOperationKind.CONTAINS:
            assert operation.key is not None
            found = self.contains(operation.key)
            outcome = ARCOutcome(
                kind=ARCOutcomeKind.SUCCESS if found else ARCOutcomeKind.MISS,
                hit=ARCHitKind.T1 if found else ARCHitKind.MISS,
                key=operation.key,
                found=found,
                admitted=found,
                p_before=self._p,
                p_after=self._p,
                current_size=self.current_size,
            )
            self._metrics.operations += 1
            self._record(ARCOperationKind.CONTAINS, outcome)
            return outcome
        if kind is ARCOperationKind.CLEAR:
            before = len(self._trace)
            self.clear()
            return self._outcome_from_trace(before)
        if kind is ARCOperationKind.SNAPSHOT:
            snap = self.snapshot()
            outcome = ARCOutcome(
                kind=ARCOutcomeKind.SUCCESS,
                hit=ARCHitKind.MISS,
                found=False,
                admitted=False,
                p_before=self._p,
                p_after=self._p,
                current_size=snap.current_size,
            )
            self._record(ARCOperationKind.SNAPSHOT, outcome)
            return outcome
        raise ARCOperationError(f"unsupported operation: {kind}")

    def run_trace(self, operations: Sequence[ARCOperation]) -> list[ARCOutcome]:
        """Apply a sequence of operations; return outcomes in order."""

        if len(operations) > MAX_TRACE_OPS:
            raise ARCOperationError(
                f"trace length {len(operations)} exceeds MAX_TRACE_OPS={MAX_TRACE_OPS}"
            )
        return [self.apply(op) for op in operations]

    # -- adaptation / eviction (internal) -----------------------------------

    def _adapt_on_b1_hit(self, size: int) -> None:
        """Increase T1 target when a recently-evicted key returns."""

        ratio = max(1, len(self._b2) // max(len(self._b1), 1))
        delta = size * ratio
        old = self._p
        self._p = min(self.capacity_bytes, self._p + delta)
        if self._p != old:
            self._metrics.p_adjustments += 1

    def _adapt_on_b2_hit(self, size: int) -> None:
        """Decrease T1 target when a frequently-evicted key returns."""

        ratio = max(1, len(self._b1) // max(len(self._b2), 1))
        delta = size * ratio
        old = self._p
        self._p = max(0, self._p - delta)
        if self._p != old:
            self._metrics.p_adjustments += 1

    def _replace(self, required_size: int) -> list[str]:
        """Evict until ``current_size + required_size ≤ capacity``."""

        evicted: list[str] = []
        while self.current_size + required_size > self.capacity_bytes and (
            self._t1 or self._t2
        ):
            prefer_t1 = False
            if self._t1 and (self._t1_size > self._p or not self._t2):
                prefer_t1 = True
            elif self._t2:
                prefer_t1 = False
            elif self._t1:
                prefer_t1 = True
            else:
                break
            keys = self._evict_one(prefer_t1=prefer_t1)
            if not keys:
                break
            evicted.extend(keys)
        return evicted

    def _evict_one(self, *, prefer_t1: bool) -> list[str]:
        """Deterministically evict the LRU entry of the preferred list."""

        if prefer_t1 and self._t1:
            key, entry = self._t1.popitem(last=False)  # LRU
            self._t1_size -= entry.size
            self._to_ghost(key, entry.size, to_b1=True)
            self._metrics.evictions_t1 += 1
            self._metrics.bytes_evicted += entry.size
            self._prune_ghosts()
            return [key]
        if self._t2:
            key, entry = self._t2.popitem(last=False)
            self._t2_size -= entry.size
            self._to_ghost(key, entry.size, to_b1=False)
            self._metrics.evictions_t2 += 1
            self._metrics.bytes_evicted += entry.size
            self._prune_ghosts()
            return [key]
        if self._t1:
            key, entry = self._t1.popitem(last=False)
            self._t1_size -= entry.size
            self._to_ghost(key, entry.size, to_b1=True)
            self._metrics.evictions_t1 += 1
            self._metrics.bytes_evicted += entry.size
            self._prune_ghosts()
            return [key]
        return []

    def _to_ghost(self, key: str, size: int, *, to_b1: bool) -> None:
        """Move a live key into B1 or B2 without retaining the value."""

        # Ensure key is not on the other ghost list.
        self._b1.pop(key, None)
        self._b2.pop(key, None)
        ghost = GhostEntry(key=key, last_size=size)
        if to_b1:
            self._b1[key] = ghost
            self._b1.move_to_end(key)
        else:
            self._b2[key] = ghost
            self._b2.move_to_end(key)

    def _prune_ghosts(self) -> None:
        """Bound combined ghost occupancy; drop LRU ghosts deterministically."""

        limit = self._config.max_ghost_entries
        while len(self._b1) + len(self._b2) > limit:
            # Prefer pruning the longer list; ties break toward B1 then B2.
            if len(self._b1) >= len(self._b2) and self._b1:
                self._b1.popitem(last=False)
            elif self._b2:
                self._b2.popitem(last=False)
            elif self._b1:
                self._b1.popitem(last=False)
            else:
                break
            self._metrics.ghost_prunes += 1

    def _record(self, kind: ARCOperationKind, outcome: ARCOutcome) -> None:
        self._trace.append(
            {
                "op": kind.value,
                "outcome": outcome.to_dict(),
                "snapshot": self.snapshot().to_dict(),
            }
        )

    def _outcome_from_trace(self, before: int) -> ARCOutcome:
        if len(self._trace) <= before:
            raise ARCInvariantError("operation produced no trace record")
        raw = self._trace[-1]["outcome"]
        return ARCOutcome(
            kind=ARCOutcomeKind(raw["kind"]),
            hit=ARCHitKind(raw["hit"]),
            key=raw.get("key"),
            found=bool(raw.get("found")),
            admitted=bool(raw.get("admitted")),
            value_size=raw.get("value_size"),
            evicted_keys=tuple(raw.get("evicted_keys") or ()),
            p_before=int(raw.get("p_before") or 0),
            p_after=int(raw.get("p_after") or 0),
            current_size=int(raw.get("current_size") or 0),
            error=raw.get("error"),
        )


# ---------------------------------------------------------------------------
# Property strategy — reproducible minimal traces
# ---------------------------------------------------------------------------


# Small closed alphabet for minimal, reproducible keys.
_TRACE_KEYS: Final[tuple[str, ...]] = tuple(f"k{i}" for i in range(8))
_TRACE_SIZES: Final[tuple[int, ...]] = (1, 2, 4, 8, 16, 32, 64)


def minimal_trace_strategy(
    seed: int,
    *,
    max_ops: int = 12,
    capacity_bytes: int = 128,
    max_live_entries: int = 16,
    max_ghost_entries: int = 16,
) -> tuple[ARCConfig, list[ARCOperation]]:
    """Emit a reproducible minimal operation trace from an integer seed.

    The generator is deliberately small and deterministic:

    * fixed key alphabet ``k0..k7`` and size ladder;
    * ``random.Random(seed)`` only — no system entropy;
    * length in ``[1, max_ops]`` derived from the seed stream;
    * operation mix biased toward put/get so growth and ghost hits appear.

    Returns ``(config, operations)`` suitable for :meth:`ARCReferenceModel.run_trace`.
    """

    if max_ops < 1 or max_ops > MAX_TRACE_OPS:
        raise ARCOperationError(f"max_ops out of bounds: {max_ops}")
    rng = random.Random(int(seed))
    config = ARCConfig(
        capacity_bytes=capacity_bytes,
        max_live_entries=max_live_entries,
        max_ghost_entries=max_ghost_entries,
        initial_p=0,
    )
    n = 1 + rng.randrange(max_ops)
    ops: list[ARCOperation] = []
    for _ in range(n):
        roll = rng.randrange(100)
        key = _TRACE_KEYS[rng.randrange(len(_TRACE_KEYS))]
        size = _TRACE_SIZES[rng.randrange(len(_TRACE_SIZES))]
        if size > capacity_bytes:
            size = 1 + rng.randrange(max(1, capacity_bytes))
        if roll < 45:
            ops.append(
                ARCOperation(
                    kind=ARCOperationKind.PUT,
                    key=key,
                    value=bytes([rng.randrange(256) for _ in range(size)]),
                )
            )
        elif roll < 75:
            ops.append(ARCOperation(kind=ARCOperationKind.GET, key=key))
        elif roll < 90:
            ops.append(ARCOperation(kind=ARCOperationKind.DELETE, key=key))
        elif roll < 96:
            ops.append(ARCOperation(kind=ARCOperationKind.CONTAINS, key=key))
        else:
            ops.append(ARCOperation(kind=ARCOperationKind.SNAPSHOT))
    return config, ops


def run_seeded_trace(seed: int, **kwargs: Any) -> tuple[ARCReferenceModel, list[ARCOutcome]]:
    """Build a model, run a seeded minimal trace, and return ``(model, outcomes)``."""

    config, ops = minimal_trace_strategy(seed, **kwargs)
    model = ARCReferenceModel(config)
    outcomes = model.run_trace(ops)
    model.assert_invariants()
    return model, outcomes


def traces_match(
    left: Sequence[dict[str, Any]],
    right: Sequence[dict[str, Any]],
) -> bool:
    """Structural equality for differential comparison of public traces."""

    if len(left) != len(right):
        return False
    for a, b in zip(left, right):
        if a != b:
            return False
    return True


__all__ = [
    "REFERENCE_MODEL_CONTRACT_VERSION",
    "REFERENCE_MODEL_SCHEMA",
    "ARCReferenceModel_V1",
    "ARCReferenceModel",
    "minimal_trace_strategy",
    "run_seeded_trace",
    "traces_match",
]
