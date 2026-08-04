"""ARC cache contracts — keys, lists, budgets, and closed operation vocabulary (KITA-022).

This module is an inert, closed, versioned contract surface for the Adaptive
Replacement Cache core.  It defines finite, fail-closed records for:

* cache keys (``CacheKey@1``) that reject empty, oversized, control, and
  non-finite identifiers;
* capacity and entry budgets (bytes and counts);
* the four ARC lists T1 / T2 / B1 / B2 with pairwise-disjoint membership;
* adaptive target ``p`` bounds (``0 ≤ p ≤ capacity_bytes``);
* ghost entries that retain **keys only** (never live values);
* operation kinds, outcomes, and metric counters; and
* invariant predicates that every implementation and the reference model
  must satisfy after every admitted transition.

No storage backends, threads, or network I/O are imported here.  The legacy
``arc_cache`` module remains an observation until later migration tasks.

Interfaces (plan aliases): ``AdaptiveReplacementCache@1``, ``CacheKey@1``,
``ARCReferenceModel@1`` (reference lives in ``reference.py``).
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar, Final, Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# Schema / version / bounds
# ---------------------------------------------------------------------------

CONTRACT_VERSION: Final[int] = 1
SCHEMA_MAJOR: Final[int] = 1
SCHEMA_MINOR: Final[int] = 0
SCHEMA_PATCH: Final[int] = 0
SCHEMA_VERSION: Final[str] = f"{SCHEMA_MAJOR}.{SCHEMA_MINOR}.{SCHEMA_PATCH}"

ARC_CONTRACTS_NAMESPACE: Final[str] = "ipfs_kit_py/cache/arc/contracts"

CACHE_KEY_SCHEMA: Final[str] = f"{ARC_CONTRACTS_NAMESPACE}/cache-key@{SCHEMA_MAJOR}"
ARC_CONFIG_SCHEMA: Final[str] = f"{ARC_CONTRACTS_NAMESPACE}/config@{SCHEMA_MAJOR}"
ARC_OPERATION_SCHEMA: Final[str] = f"{ARC_CONTRACTS_NAMESPACE}/operation@{SCHEMA_MAJOR}"
ARC_OUTCOME_SCHEMA: Final[str] = f"{ARC_CONTRACTS_NAMESPACE}/outcome@{SCHEMA_MAJOR}"
ARC_SNAPSHOT_SCHEMA: Final[str] = f"{ARC_CONTRACTS_NAMESPACE}/snapshot@{SCHEMA_MAJOR}"
ARC_METRICS_SCHEMA: Final[str] = f"{ARC_CONTRACTS_NAMESPACE}/metrics@{SCHEMA_MAJOR}"
ADAPTIVE_REPLACEMENT_CACHE_SCHEMA: Final[str] = (
    f"{ARC_CONTRACTS_NAMESPACE}/adaptive-replacement-cache@{SCHEMA_MAJOR}"
)
ARC_REFERENCE_MODEL_SCHEMA: Final[str] = (
    f"{ARC_CONTRACTS_NAMESPACE}/reference-model@{SCHEMA_MAJOR}"
)

# Public interface aliases (plan: AdaptiveReplacementCache@1, CacheKey@1, …).
CacheKey_V1: Final[str] = CACHE_KEY_SCHEMA
AdaptiveReplacementCache_V1: Final[str] = ADAPTIVE_REPLACEMENT_CACHE_SCHEMA
ARCReferenceModel_V1: Final[str] = ARC_REFERENCE_MODEL_SCHEMA

MAX_SAFE_INTEGER: Final[int] = (1 << 53) - 1
MAX_KEY_BYTES: Final[int] = 512
MAX_CAPACITY_BYTES: Final[int] = 1 << 40  # 1 TiB absolute contract ceiling
MAX_ENTRY_BYTES: Final[int] = MAX_CAPACITY_BYTES
MAX_LIVE_ENTRIES: Final[int] = 1_048_576
MAX_GHOST_ENTRIES: Final[int] = 1_048_576
MAX_TRACE_OPS: Final[int] = 4_096
MAX_TEXT_BYTES: Final[int] = 4_096

# Default budgets for a small hermetic reference instance.
DEFAULT_CAPACITY_BYTES: Final[int] = 4_096
DEFAULT_MAX_LIVE_ENTRIES: Final[int] = 256
DEFAULT_MAX_GHOST_ENTRIES: Final[int] = 256
DEFAULT_INITIAL_P: Final[int] = 0

_KEY_RE: Final[re.Pattern[str]] = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._:/#@+\-]{0,511}$"
)
_CONTROL_OR_DEL: Final[re.Pattern[str]] = re.compile(r"[\x00-\x1f\x7f]")


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ARCContractError(ValueError):
    """Base class for ARC contract schema / invariant failures."""


class ARCKeyError(ARCContractError):
    """A cache key is empty, malformed, oversized, or non-finite."""


class ARCSizeError(ARCContractError):
    """An entry size, capacity, or budget is invalid or unbounded."""


class ARCCapacityError(ARCContractError):
    """A capacity or adaptive-target bound was violated."""


class ARCInvariantError(ARCContractError):
    """A declared ARC invariant does not hold on the observed state."""


class ARCValueError(ARCContractError):
    """A cache value is not admitted (wrong type, unbounded, oversized)."""


class ARCOperationError(ARCContractError):
    """An operation record is malformed or out of vocabulary."""


# ---------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------


class ARCList(str, Enum):
    """The four ARC lists.

    * ``T1`` — recent live items (recency).
    * ``T2`` — frequent live items (frequency).
    * ``B1`` — ghost history of T1 (keys only).
    * ``B2`` — ghost history of T2 (keys only).
    """

    T1 = "T1"
    T2 = "T2"
    B1 = "B1"
    B2 = "B2"


LIVE_LISTS: Final[frozenset[ARCList]] = frozenset({ARCList.T1, ARCList.T2})
GHOST_LISTS: Final[frozenset[ARCList]] = frozenset({ARCList.B1, ARCList.B2})


class ARCOperationKind(str, Enum):
    """Closed operation vocabulary for the ARC core and property traces."""

    GET = "get"
    PUT = "put"
    DELETE = "delete"
    CONTAINS = "contains"
    CLEAR = "clear"
    # Explicit capacity probe used by property strategies (no mutation).
    SNAPSHOT = "snapshot"


class ARCHitKind(str, Enum):
    """Where a lookup resolved (or missed)."""

    MISS = "miss"
    T1 = "hit_t1"
    T2 = "hit_t2"
    B1 = "ghost_b1"
    B2 = "ghost_b2"
    REJECTED = "rejected"


class ARCOutcomeKind(str, Enum):
    """Coarse outcome of an admitted or rejected operation."""

    SUCCESS = "success"
    MISS = "miss"
    REJECTED = "rejected"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _reject_non_finite_number(value: Any, *, name: str) -> None:
    if isinstance(value, bool):
        raise ARCSizeError(f"{name} must be an integer, not bool")
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ARCSizeError(f"{name} must be finite, got {value!r}")
        raise ARCSizeError(f"{name} must be an integer, got float {value!r}")
    if isinstance(value, complex):
        raise ARCSizeError(f"{name} must be an integer, got complex")


def require_bounded_int(
    value: Any,
    *,
    name: str,
    minimum: int = 0,
    maximum: int = MAX_SAFE_INTEGER,
) -> int:
    """Admit a finite integer in ``[minimum, maximum]`` (fail-closed)."""

    _reject_non_finite_number(value, name=name)
    if not isinstance(value, int):
        raise ARCSizeError(f"{name} must be an int, got {type(value).__name__}")
    if value < minimum or value > maximum:
        raise ARCSizeError(
            f"{name}={value} out of bounds [{minimum}, {maximum}]"
        )
    return value


def validate_cache_key(key: Any) -> str:
    """Validate and return a canonical ``CacheKey@1`` string.

    Rejects ``None``, non-str, empty, oversized, control characters,
    whitespace-only, and keys that fail the closed identifier pattern.
    """

    if key is None:
        raise ARCKeyError("cache key must not be None")
    if not isinstance(key, str):
        raise ARCKeyError(f"cache key must be str, got {type(key).__name__}")
    if not key:
        raise ARCKeyError("cache key must be non-empty")
    if len(key.encode("utf-8", errors="strict")) > MAX_KEY_BYTES:
        raise ARCKeyError(f"cache key exceeds {MAX_KEY_BYTES} bytes")
    if _CONTROL_OR_DEL.search(key):
        raise ARCKeyError("cache key must not contain control characters")
    if key.strip() != key or " " in key or "\t" in key:
        raise ARCKeyError("cache key must not contain surrounding or internal whitespace")
    if not _KEY_RE.fullmatch(key):
        raise ARCKeyError(f"cache key failed identifier pattern: {key!r}")
    return key


def validate_value(value: Any, *, capacity_bytes: int) -> bytes:
    """Admit a finite ``bytes`` value whose size fits the cache capacity.

    Unbounded containers (iterators, files, generators) and non-bytes types
    are rejected.  Oversized values reject rather than partially admit.
    """

    if value is None:
        raise ARCValueError("cache value must not be None")
    if not isinstance(value, (bytes, bytearray, memoryview)):
        raise ARCValueError(
            f"cache value must be bytes-like, got {type(value).__name__}"
        )
    data = bytes(value)
    size = len(data)
    if size > MAX_ENTRY_BYTES:
        raise ARCValueError(f"value size {size} exceeds MAX_ENTRY_BYTES")
    if size > capacity_bytes:
        raise ARCValueError(
            f"value size {size} exceeds capacity_bytes {capacity_bytes}"
        )
    return data


def validate_capacity_bytes(capacity_bytes: Any) -> int:
    """Capacity must be a positive finite integer within the contract ceiling."""

    return require_bounded_int(
        capacity_bytes,
        name="capacity_bytes",
        minimum=1,
        maximum=MAX_CAPACITY_BYTES,
    )


def validate_entry_budget(value: Any, *, name: str, maximum: int) -> int:
    return require_bounded_int(value, name=name, minimum=1, maximum=maximum)


# ---------------------------------------------------------------------------
# Config / key / live entry / ghost entry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CacheKey:
    """Content-stable cache key (``CacheKey@1``)."""

    SCHEMA: ClassVar[str] = CACHE_KEY_SCHEMA

    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", validate_cache_key(self.value))

    def __str__(self) -> str:
        return self.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "value": self.value,
        }


@dataclass(frozen=True)
class ARCConfig:
    """Closed configuration for an ARC instance.

    Invariants enforced at construction:

    * ``capacity_bytes ≥ 1`` and ≤ ``MAX_CAPACITY_BYTES``;
    * live and ghost entry budgets ≥ 1 and ≤ contract maxima;
    * ``0 ≤ initial_p ≤ capacity_bytes``.
    """

    SCHEMA: ClassVar[str] = ARC_CONFIG_SCHEMA

    capacity_bytes: int = DEFAULT_CAPACITY_BYTES
    max_live_entries: int = DEFAULT_MAX_LIVE_ENTRIES
    max_ghost_entries: int = DEFAULT_MAX_GHOST_ENTRIES
    initial_p: int = DEFAULT_INITIAL_P

    def __post_init__(self) -> None:
        cap = validate_capacity_bytes(self.capacity_bytes)
        live = validate_entry_budget(
            self.max_live_entries, name="max_live_entries", maximum=MAX_LIVE_ENTRIES
        )
        ghost = validate_entry_budget(
            self.max_ghost_entries,
            name="max_ghost_entries",
            maximum=MAX_GHOST_ENTRIES,
        )
        p = require_bounded_int(
            self.initial_p,
            name="initial_p",
            minimum=0,
            maximum=cap,
        )
        object.__setattr__(self, "capacity_bytes", cap)
        object.__setattr__(self, "max_live_entries", live)
        object.__setattr__(self, "max_ghost_entries", ghost)
        object.__setattr__(self, "initial_p", p)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "capacity_bytes": self.capacity_bytes,
            "max_live_entries": self.max_live_entries,
            "max_ghost_entries": self.max_ghost_entries,
            "initial_p": self.initial_p,
        }


@dataclass(frozen=True)
class LiveEntry:
    """A live T1/T2 entry: key, admitted size, and retained value bytes."""

    key: str
    size: int
    value: bytes

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", validate_cache_key(self.key))
        size = require_bounded_int(self.size, name="size", minimum=0, maximum=MAX_ENTRY_BYTES)
        if not isinstance(self.value, (bytes, bytearray, memoryview)):
            raise ARCValueError("LiveEntry.value must be bytes-like")
        data = bytes(self.value)
        if len(data) != size:
            raise ARCSizeError(
                f"LiveEntry size {size} disagrees with value length {len(data)}"
            )
        object.__setattr__(self, "size", size)
        object.__setattr__(self, "value", data)


@dataclass(frozen=True)
class GhostEntry:
    """A B1/B2 ghost entry: key only (no value payload).

    ``last_size`` is historical metadata used for adaptation accounting; it
    must never be treated as a live value and never contributes to
    ``current_size``.
    """

    key: str
    last_size: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", validate_cache_key(self.key))
        object.__setattr__(
            self,
            "last_size",
            require_bounded_int(
                self.last_size, name="last_size", minimum=0, maximum=MAX_ENTRY_BYTES
            ),
        )
        # Ghost entries intentionally have no value attribute.


# ---------------------------------------------------------------------------
# Operations / outcomes / metrics / snapshot
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ARCOperation:
    """One closed ARC operation for traces and property strategies."""

    SCHEMA: ClassVar[str] = ARC_OPERATION_SCHEMA

    kind: ARCOperationKind
    key: str | None = None
    value: bytes | None = None
    size: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ARCOperationKind):
            try:
                object.__setattr__(self, "kind", ARCOperationKind(self.kind))
            except (TypeError, ValueError) as exc:
                raise ARCOperationError(f"unknown operation kind: {self.kind!r}") from exc
        if self.key is not None:
            object.__setattr__(self, "key", validate_cache_key(self.key))
        if self.value is not None:
            if not isinstance(self.value, (bytes, bytearray, memoryview)):
                raise ARCValueError("operation value must be bytes-like or None")
            object.__setattr__(self, "value", bytes(self.value))
        if self.size is not None:
            object.__setattr__(
                self,
                "size",
                require_bounded_int(
                    self.size, name="size", minimum=0, maximum=MAX_ENTRY_BYTES
                ),
            )
        self._check_shape()

    def _check_shape(self) -> None:
        kind = self.kind
        if kind in (ARCOperationKind.GET, ARCOperationKind.DELETE, ARCOperationKind.CONTAINS):
            if self.key is None:
                raise ARCOperationError(f"{kind.value} requires a key")
        elif kind is ARCOperationKind.PUT:
            if self.key is None:
                raise ARCOperationError("put requires a key")
            if self.value is None and self.size is None:
                raise ARCOperationError("put requires value or size")
        elif kind in (ARCOperationKind.CLEAR, ARCOperationKind.SNAPSHOT):
            if self.key is not None or self.value is not None:
                raise ARCOperationError(f"{kind.value} takes no key/value")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema": self.SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "kind": self.kind.value,
        }
        if self.key is not None:
            payload["key"] = self.key
        if self.value is not None:
            payload["size"] = len(self.value)
            # Values are not embedded in public operation records (bounded refs only).
            payload["value_digest"] = _sha256_hex(self.value)
        elif self.size is not None:
            payload["size"] = self.size
        return payload


def _sha256_hex(data: bytes) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class ARCMetrics:
    """Exact counters for hits, ghost hits, admissions, evictions, rejections."""

    SCHEMA: ClassVar[str] = ARC_METRICS_SCHEMA

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

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "operations": self.operations,
            "hits_t1": self.hits_t1,
            "hits_t2": self.hits_t2,
            "misses": self.misses,
            "ghost_hits_b1": self.ghost_hits_b1,
            "ghost_hits_b2": self.ghost_hits_b2,
            "puts": self.puts,
            "updates": self.updates,
            "deletes": self.deletes,
            "rejections": self.rejections,
            "evictions_t1": self.evictions_t1,
            "evictions_t2": self.evictions_t2,
            "promotions_t1_to_t2": self.promotions_t1_to_t2,
            "promotions_b1_to_t2": self.promotions_b1_to_t2,
            "promotions_b2_to_t2": self.promotions_b2_to_t2,
            "p_adjustments": self.p_adjustments,
            "ghost_prunes": self.ghost_prunes,
            "bytes_admitted": self.bytes_admitted,
            "bytes_evicted": self.bytes_evicted,
            "bytes_updated_delta": self.bytes_updated_delta,
        }


@dataclass(frozen=True)
class ARCSnapshot:
    """Public, value-free projection of ARC list membership and budgets.

    Ghost lists expose keys only.  Live lists expose keys and sizes (not
    payloads) so accounting can be audited without leaking bodies.
    """

    SCHEMA: ClassVar[str] = ARC_SNAPSHOT_SCHEMA

    capacity_bytes: int
    current_size: int
    t1_size: int
    t2_size: int
    p: int
    t1_keys: tuple[str, ...]
    t2_keys: tuple[str, ...]
    b1_keys: tuple[str, ...]
    b2_keys: tuple[str, ...]
    t1_sizes: tuple[int, ...]
    t2_sizes: tuple[int, ...]
    live_entries: int
    ghost_entries: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "capacity_bytes": self.capacity_bytes,
            "current_size": self.current_size,
            "t1_size": self.t1_size,
            "t2_size": self.t2_size,
            "p": self.p,
            "t1_keys": list(self.t1_keys),
            "t2_keys": list(self.t2_keys),
            "b1_keys": list(self.b1_keys),
            "b2_keys": list(self.b2_keys),
            "t1_sizes": list(self.t1_sizes),
            "t2_sizes": list(self.t2_sizes),
            "live_entries": self.live_entries,
            "ghost_entries": self.ghost_entries,
        }


@dataclass(frozen=True)
class ARCOutcome:
    """Result of applying one operation against an ARC core."""

    SCHEMA: ClassVar[str] = ARC_OUTCOME_SCHEMA

    kind: ARCOutcomeKind
    hit: ARCHitKind
    key: str | None = None
    found: bool = False
    admitted: bool = False
    value_size: int | None = None
    evicted_keys: tuple[str, ...] = ()
    p_before: int = 0
    p_after: int = 0
    current_size: int = 0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "kind": self.kind.value,
            "hit": self.hit.value,
            "key": self.key,
            "found": self.found,
            "admitted": self.admitted,
            "value_size": self.value_size,
            "evicted_keys": list(self.evicted_keys),
            "p_before": self.p_before,
            "p_after": self.p_after,
            "current_size": self.current_size,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Invariant predicates
# ---------------------------------------------------------------------------


def lists_pairwise_disjoint(
    t1: Iterable[str],
    t2: Iterable[str],
    b1: Iterable[str],
    b2: Iterable[str],
) -> bool:
    """Return True iff the four ARC lists share no keys."""

    s1, s2, s3, s4 = set(t1), set(t2), set(b1), set(b2)
    return (
        s1.isdisjoint(s2)
        and s1.isdisjoint(s3)
        and s1.isdisjoint(s4)
        and s2.isdisjoint(s3)
        and s2.isdisjoint(s4)
        and s3.isdisjoint(s4)
    )


def ghost_lists_have_no_values(ghost_entries: Iterable[Any]) -> bool:
    """Ghost entries must not carry a live value payload attribute."""

    for entry in ghost_entries:
        if entry is None:
            return False
        if isinstance(entry, GhostEntry):
            if hasattr(entry, "value") and getattr(entry, "value") is not None:
                return False
            continue
        if isinstance(entry, Mapping):
            if "value" in entry and entry["value"] is not None:
                return False
            continue
        # Bare keys are fine.
        if isinstance(entry, str):
            continue
        if hasattr(entry, "value") and getattr(entry, "value") is not None:
            return False
    return True


def adaptive_target_bounded(p: int, capacity_bytes: int) -> bool:
    """``0 ≤ p ≤ capacity_bytes``."""

    try:
        p_i = int(p)
        c_i = int(capacity_bytes)
    except (TypeError, ValueError):
        return False
    return 0 <= p_i <= c_i and c_i >= 1


def current_size_matches_live(
    current_size: int,
    t1_size: int,
    t2_size: int,
    capacity_bytes: int,
) -> bool:
    """``current_size == t1_size + t2_size`` and never exceeds capacity."""

    try:
        return (
            int(current_size) == int(t1_size) + int(t2_size)
            and 0 <= int(current_size) <= int(capacity_bytes)
            and int(t1_size) >= 0
            and int(t2_size) >= 0
        )
    except (TypeError, ValueError):
        return False


def assert_arc_invariants(
    *,
    capacity_bytes: int,
    current_size: int,
    t1_size: int,
    t2_size: int,
    p: int,
    t1_keys: Sequence[str],
    t2_keys: Sequence[str],
    b1_keys: Sequence[str],
    b2_keys: Sequence[str],
    t1_sizes: Sequence[int] | None = None,
    t2_sizes: Sequence[int] | None = None,
    ghost_payloads: Iterable[Any] = (),
    max_live_entries: int | None = None,
    max_ghost_entries: int | None = None,
) -> None:
    """Raise :class:`ARCInvariantError` if any declared invariant fails."""

    if not current_size_matches_live(current_size, t1_size, t2_size, capacity_bytes):
        raise ARCInvariantError(
            f"current_size invariant failed: current_size={current_size}, "
            f"t1_size={t1_size}, t2_size={t2_size}, capacity={capacity_bytes}"
        )
    if not adaptive_target_bounded(p, capacity_bytes):
        raise ARCInvariantError(
            f"adaptive target p={p} not bounded by capacity={capacity_bytes}"
        )
    if not lists_pairwise_disjoint(t1_keys, t2_keys, b1_keys, b2_keys):
        raise ARCInvariantError("ARC lists are not pairwise disjoint")
    if t1_sizes is not None:
        if len(t1_sizes) != len(t1_keys):
            raise ARCInvariantError("t1_sizes length disagrees with t1_keys")
        if sum(t1_sizes) != t1_size:
            raise ARCInvariantError(
                f"t1_size {t1_size} != sum(t1_sizes) {sum(t1_sizes)}"
            )
    if t2_sizes is not None:
        if len(t2_sizes) != len(t2_keys):
            raise ARCInvariantError("t2_sizes length disagrees with t2_keys")
        if sum(t2_sizes) != t2_size:
            raise ARCInvariantError(
                f"t2_size {t2_size} != sum(t2_sizes) {sum(t2_sizes)}"
            )
    if not ghost_lists_have_no_values(ghost_payloads):
        raise ARCInvariantError("ghost list retained a live value payload")
    live_count = len(t1_keys) + len(t2_keys)
    ghost_count = len(b1_keys) + len(b2_keys)
    if max_live_entries is not None and live_count > max_live_entries:
        raise ARCInvariantError(
            f"live entry count {live_count} exceeds max_live_entries {max_live_entries}"
        )
    if max_ghost_entries is not None and ghost_count > max_ghost_entries:
        raise ARCInvariantError(
            f"ghost entry count {ghost_count} exceeds max_ghost_entries {max_ghost_entries}"
        )


# ---------------------------------------------------------------------------
# Protocol surface (AdaptiveReplacementCache@1)
# ---------------------------------------------------------------------------


@runtime_checkable
class AdaptiveReplacementCache(Protocol):
    """Protocol for ``AdaptiveReplacementCache@1`` implementors."""

    @property
    def capacity_bytes(self) -> int: ...

    @property
    def current_size(self) -> int: ...

    @property
    def p(self) -> int: ...

    def get(self, key: str) -> bytes | None: ...

    def put(self, key: str, value: bytes) -> bool: ...

    def delete(self, key: str) -> bool: ...

    def contains(self, key: str) -> bool: ...

    def clear(self) -> None: ...

    def snapshot(self) -> ARCSnapshot: ...

    def metrics(self) -> ARCMetrics: ...

    def assert_invariants(self) -> None: ...


__all__ = [
    "CONTRACT_VERSION",
    "SCHEMA_VERSION",
    "SCHEMA_MAJOR",
    "CacheKey_V1",
    "AdaptiveReplacementCache_V1",
    "ARCReferenceModel_V1",
    "CACHE_KEY_SCHEMA",
    "ARC_CONFIG_SCHEMA",
    "ARC_OPERATION_SCHEMA",
    "ARC_OUTCOME_SCHEMA",
    "ARC_SNAPSHOT_SCHEMA",
    "ARC_METRICS_SCHEMA",
    "ADAPTIVE_REPLACEMENT_CACHE_SCHEMA",
    "ARC_REFERENCE_MODEL_SCHEMA",
    "MAX_SAFE_INTEGER",
    "MAX_KEY_BYTES",
    "MAX_CAPACITY_BYTES",
    "MAX_ENTRY_BYTES",
    "MAX_LIVE_ENTRIES",
    "MAX_GHOST_ENTRIES",
    "MAX_TRACE_OPS",
    "DEFAULT_CAPACITY_BYTES",
    "DEFAULT_MAX_LIVE_ENTRIES",
    "DEFAULT_MAX_GHOST_ENTRIES",
    "DEFAULT_INITIAL_P",
    "ARCContractError",
    "ARCKeyError",
    "ARCSizeError",
    "ARCCapacityError",
    "ARCInvariantError",
    "ARCValueError",
    "ARCOperationError",
    "ARCList",
    "LIVE_LISTS",
    "GHOST_LISTS",
    "ARCOperationKind",
    "ARCHitKind",
    "ARCOutcomeKind",
    "require_bounded_int",
    "validate_cache_key",
    "validate_value",
    "validate_capacity_bytes",
    "validate_entry_budget",
    "CacheKey",
    "ARCConfig",
    "LiveEntry",
    "GhostEntry",
    "ARCOperation",
    "ARCMetrics",
    "ARCSnapshot",
    "ARCOutcome",
    "lists_pairwise_disjoint",
    "ghost_lists_have_no_values",
    "adaptive_target_bounded",
    "current_size_matches_live",
    "assert_arc_invariants",
    "AdaptiveReplacementCache",
]
