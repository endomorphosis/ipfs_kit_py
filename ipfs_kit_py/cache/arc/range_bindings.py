"""Generation-bound range/chunk ARC keys and generation-aware single-flight (KVFS-400).

This module owns the *range binding* surface that large FUSE reads need on top
of the byte-aware ARC core:

* :class:`RangeBinding` keys bind namespace, inode/content/version, generation,
  serializer, offset, and length into a single deterministic ARC cache key;
* :class:`RangeMatchPolicy` makes exact-range and overlapping behaviour
  explicit and deterministic (default: exact match only);
* :class:`GenerationAwareRangeSingleFlight` single-flights concurrent misses
  only when the full binding — including generation — is equal; a generation
  advance elects an independent filler and cannot share a prior flight; and
* cancellation and error fan-out stay bounded by the in-flight map cardinality
  and the per-key waiter set (never process-wide broadcast).

ARC byte accounting and ghost-list invariants remain the responsibility of the
injected :class:`~ipfs_kit_py.cache.arc.contracts.AdaptiveReplacementCache`
implementation; this module only composes validated keys and fill coordination.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar, Final

from ipfs_kit_py.cache.arc.concurrency import (
    CacheFillCancelled,
    CacheFillError,
    CacheFillRejected,
    CacheFillResult,
    FillStatus,
    SingleFlightARC,
)
from ipfs_kit_py.cache.arc.contracts import (
    MAX_ENTRY_BYTES,
    MAX_SAFE_INTEGER,
    AdaptiveReplacementCache as AdaptiveReplacementCacheProtocol,
    require_bounded_int,
    validate_cache_key,
)

# ---------------------------------------------------------------------------
# Schema / version / bounds
# ---------------------------------------------------------------------------

CONTRACT_VERSION: Final[int] = 1
SCHEMA_MAJOR: Final[int] = 1
SCHEMA_MINOR: Final[int] = 0
SCHEMA_PATCH: Final[int] = 0
SCHEMA_VERSION: Final[str] = f"{SCHEMA_MAJOR}.{SCHEMA_MINOR}.{SCHEMA_PATCH}"

RANGE_BINDINGS_NAMESPACE: Final[str] = "ipfs_kit_py/cache/arc/range_bindings"
RANGE_BINDING_SCHEMA: Final[str] = f"{RANGE_BINDINGS_NAMESPACE}/range-binding@{SCHEMA_MAJOR}"
RANGE_SINGLE_FLIGHT_SCHEMA: Final[str] = (
    f"{RANGE_BINDINGS_NAMESPACE}/generation-aware-single-flight@{SCHEMA_MAJOR}"
)
RangeBinding_V1: Final[str] = RANGE_BINDING_SCHEMA
GenerationAwareRangeSingleFlight_V1: Final[str] = RANGE_SINGLE_FLIGHT_SCHEMA

DEFAULT_NAMESPACE: Final[str] = "default"
DEFAULT_SERIALIZER: Final[str] = "bytes@1"
DEFAULT_POLICY: Final[str] = "default"
DEFAULT_GENERATION: Final[str] = "0"

# Align with ranged storage single-range bound (16 MiB) so FUSE-sized chunks
# are admitable without inventing a second capacity story.
MAX_RANGE_LENGTH: Final[int] = 16 * 1024 * 1024
MAX_IDENTITY_BYTES: Final[int] = 512
MAX_INFLIGHT_FLIGHTS: Final[int] = 256

_BINDING_TEXT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "namespace",
        "content_id",
        "version",
        "generation",
        "serializer",
        "policy",
    }
)
_BINDING_DICT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "namespace",
        "content_id",
        "version",
        "generation",
        "serializer",
        "policy",
        "offset",
        "length",
    }
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class RangeBindingError(ValueError):
    """Base class for range-binding schema / policy failures."""


class RangeIdentityError(RangeBindingError):
    """A textual identity field is empty, oversized, or non-finite."""


class RangeExtentError(RangeBindingError):
    """Offset/length is invalid, unbounded, or exceeds the contract ceiling."""


class RangePolicyError(RangeBindingError):
    """A range match / overlap policy decision cannot be formed."""


# ---------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------


class RangeRelation(str, Enum):
    """Deterministic geometric relation between two range extents.

    Relations other than :attr:`EXACT` never share a cache key or a
    single-flight under the default :class:`RangeMatchPolicy.EXACT_ONLY`
    policy.  They exist so callers (invalidation, diagnostics) can classify
    overlaps without inventing ad-hoc integer comparisons.
    """

    EXACT = "exact"
    CONTAINS = "contains"  # ``self`` fully covers ``other``
    CONTAINED = "contained"  # ``other`` fully covers ``self``
    OVERLAPS = "overlaps"  # partial non-empty intersection
    DISJOINT = "disjoint"
    IDENTITY_MISMATCH = "identity_mismatch"


class RangeMatchPolicy(str, Enum):
    """How a lookup or fill joins against stored / in-flight ranges.

    * ``EXACT_ONLY`` — only identical ``(offset, length)`` under equal identity
      and generation may hit or single-flight.  Overlapping ranges are distinct
      keys and run independent fillers.  This is the production default and the
      only policy that is safe without a covering-slice proof.
    """

    EXACT_ONLY = "exact_only"


class RangeLookupDisposition(str, Enum):
    """Closed outcome of applying a :class:`RangeMatchPolicy` to candidates."""

    EXACT_HIT = "exact_hit"
    MISS = "miss"
    REJECTED = "rejected"


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _bounded_identity_text(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise RangeIdentityError(f"{name} must be str, got {type(value).__name__}")
    if not value:
        raise RangeIdentityError(f"{name} must be non-empty")
    encoded = value.encode("utf-8", errors="strict")
    if len(encoded) > MAX_IDENTITY_BYTES:
        raise RangeIdentityError(f"{name} exceeds {MAX_IDENTITY_BYTES} bytes")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise RangeIdentityError(f"{name} must not contain control characters")
    if value.strip() != value or " " in value or "\t" in value:
        raise RangeIdentityError(
            f"{name} must not contain surrounding or internal whitespace"
        )
    return value


def validate_offset(value: Any) -> int:
    """Admit a finite non-negative byte offset within the safe-integer ceiling."""

    try:
        return require_bounded_int(
            value, name="offset", minimum=0, maximum=MAX_SAFE_INTEGER
        )
    except ValueError as exc:
        raise RangeExtentError(str(exc)) from exc


def validate_length(value: Any, *, maximum: int = MAX_RANGE_LENGTH) -> int:
    """Admit a positive finite length within the range contract ceiling.

    Zero-length ranges are rejected: an empty fill is not a coherent cache
    entry and would alias every empty read under the same identity.
    """

    try:
        return require_bounded_int(value, name="length", minimum=1, maximum=maximum)
    except ValueError as exc:
        raise RangeExtentError(str(exc)) from exc


def validate_range_extent(
    offset: Any, length: Any, *, maximum_length: int = MAX_RANGE_LENGTH
) -> tuple[int, int]:
    """Validate ``(offset, length)`` and reject arithmetic overflow of the end."""

    off = validate_offset(offset)
    length_i = validate_length(length, maximum=maximum_length)
    # End is exclusive; require it stays within the safe integer domain so
    # overlap arithmetic never wraps.
    end = off + length_i
    if end > MAX_SAFE_INTEGER:
        raise RangeExtentError(
            f"range end offset+length={end} exceeds MAX_SAFE_INTEGER"
        )
    if length_i > MAX_ENTRY_BYTES:
        raise RangeExtentError(
            f"length {length_i} exceeds MAX_ENTRY_BYTES {MAX_ENTRY_BYTES}"
        )
    return off, length_i


# ---------------------------------------------------------------------------
# RangeBinding
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RangeBinding:
    """Immutable generation-bound range/chunk identity (``RangeBinding@1``).

    Every dimension participates in :attr:`cache_key`.  A changed namespace,
    inode/content id, version, generation, serializer, policy, offset, or
    length is therefore a different ARC key and cannot return a stale payload.
    """

    SCHEMA: ClassVar[str] = RANGE_BINDING_SCHEMA

    namespace: str
    content_id: str
    version: str
    generation: str
    serializer: str
    offset: int
    length: int
    policy: str = DEFAULT_POLICY

    def __post_init__(self) -> None:
        for field in _BINDING_TEXT_FIELDS:
            object.__setattr__(
                self, field, _bounded_identity_text(getattr(self, field), field)
            )
        off, length_i = validate_range_extent(self.offset, self.length)
        object.__setattr__(self, "offset", off)
        object.__setattr__(self, "length", length_i)

    # --- aliases -----------------------------------------------------------

    @property
    def inode(self) -> str:
        """Alias: content identity may be a stable inode number string."""

        return self.content_id

    @property
    def content(self) -> str:
        """Alias used by callers that name the content identity ``content``."""

        return self.content_id

    @property
    def end(self) -> int:
        """Exclusive end offset (``offset + length``)."""

        return self.offset + self.length

    # --- construction ------------------------------------------------------

    @classmethod
    def create(
        cls,
        *,
        namespace: str = DEFAULT_NAMESPACE,
        content_id: str | None = None,
        inode: str | int | None = None,
        version: str,
        generation: str = DEFAULT_GENERATION,
        serializer: str = DEFAULT_SERIALIZER,
        offset: int,
        length: int,
        policy: str = DEFAULT_POLICY,
    ) -> "RangeBinding":
        """Build a binding from either ``content_id`` or ``inode`` (not both)."""

        if content_id is not None and inode is not None:
            raise RangeIdentityError("pass content_id or inode, not both")
        if content_id is None and inode is None:
            raise RangeIdentityError("content_id or inode is required")
        if content_id is None:
            if isinstance(inode, bool) or not isinstance(inode, (str, int)):
                raise RangeIdentityError(
                    f"inode must be str or int, got {type(inode).__name__}"
                )
            content_id = str(inode)
        return cls(
            namespace=namespace,
            content_id=content_id,
            version=version,
            generation=generation,
            serializer=serializer,
            offset=offset,
            length=length,
            policy=policy,
        )

    @classmethod
    def from_dict(cls, value: Any) -> "RangeBinding":
        if not isinstance(value, Mapping):
            raise RangeIdentityError("range binding must be a mapping")
        keys = set(value)
        if keys != _BINDING_DICT_FIELDS:
            raise RangeIdentityError(
                "range binding has unknown or missing identity fields"
            )
        return cls(
            namespace=value["namespace"],
            content_id=value["content_id"],
            version=value["version"],
            generation=value["generation"],
            serializer=value["serializer"],
            offset=value["offset"],
            length=value["length"],
            policy=value["policy"],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "namespace": self.namespace,
            "content_id": self.content_id,
            "version": self.version,
            "generation": self.generation,
            "serializer": self.serializer,
            "policy": self.policy,
            "offset": self.offset,
            "length": self.length,
        }

    def identity_scope(self) -> tuple[str, str, str, str, str]:
        """Return the non-range identity axes used for generation isolation.

        ``(namespace, content_id, version, serializer, policy)`` — generation
        is intentionally excluded so a generation advance can be applied to the
        whole scope while still binding generation into each cache key.
        """

        return (
            self.namespace,
            self.content_id,
            self.version,
            self.serializer,
            self.policy,
        )

    def with_generation(self, generation: str) -> "RangeBinding":
        """Return a copy of this binding under a new generation."""

        return RangeBinding(
            namespace=self.namespace,
            content_id=self.content_id,
            version=self.version,
            generation=generation,
            serializer=self.serializer,
            offset=self.offset,
            length=self.length,
            policy=self.policy,
        )

    def with_extent(self, *, offset: int, length: int) -> "RangeBinding":
        """Return a copy of this binding with a different byte extent."""

        return RangeBinding(
            namespace=self.namespace,
            content_id=self.content_id,
            version=self.version,
            generation=self.generation,
            serializer=self.serializer,
            offset=offset,
            length=length,
            policy=self.policy,
        )

    def same_identity(self, other: "RangeBinding") -> bool:
        """True when non-range identity axes match (generation may differ)."""

        if not isinstance(other, RangeBinding):
            return False
        return self.identity_scope() == other.identity_scope()

    def same_generation_identity(self, other: "RangeBinding") -> bool:
        """True when identity axes and generation match (range may differ)."""

        return self.same_identity(other) and self.generation == other.generation

    @property
    def cache_key(self) -> str:
        """Deterministic ARC key binding every identity and range dimension.

        The key is a hex digest under the closed ``arc-range:`` prefix so it
        always satisfies :func:`validate_cache_key` regardless of field values
        that would otherwise introduce disallowed characters.
        """

        canonical = json.dumps(
            {
                "schema": self.SCHEMA,
                "contract_version": CONTRACT_VERSION,
                **self.to_dict(),
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        digest = hashlib.sha256(canonical.encode("ascii")).hexdigest()
        key = f"arc-range:{digest}"
        return validate_cache_key(key)

    @property
    def flight_key(self) -> str:
        """Single-flight map key — identical to :attr:`cache_key`.

        Generation is part of the key, so concurrent misses single-flight only
        under equal generation (and equal range/identity).  A generation
        advance is a different flight by construction.
        """

        return self.cache_key


# ---------------------------------------------------------------------------
# Overlap / exact-range policy
# ---------------------------------------------------------------------------


def range_end(offset: int, length: int) -> int:
    """Exclusive end for a validated extent."""

    off, length_i = validate_range_extent(offset, length)
    return off + length_i


def ranges_overlap(a_offset: int, a_length: int, b_offset: int, b_length: int) -> bool:
    """Return True iff the half-open intervals ``[off, off+len)`` intersect."""

    a_off, a_len = validate_range_extent(a_offset, a_length)
    b_off, b_len = validate_range_extent(b_offset, b_length)
    return a_off < (b_off + b_len) and b_off < (a_off + a_len)


def classify_range_relation(left: RangeBinding, right: RangeBinding) -> RangeRelation:
    """Classify the geometric relation of two bindings deterministically.

    Identity mismatch (including generation) short-circuits before geometry so
    stale-generation ranges never appear as overlapping hits.
    """

    if not isinstance(left, RangeBinding) or not isinstance(right, RangeBinding):
        raise RangePolicyError("classify_range_relation requires RangeBinding values")
    if not left.same_generation_identity(right):
        return RangeRelation.IDENTITY_MISMATCH
    if left.offset == right.offset and left.length == right.length:
        return RangeRelation.EXACT
    left_end = left.end
    right_end = right.end
    if left.offset <= right.offset and left_end >= right_end:
        # Equal extents already returned EXACT; remaining cases are proper
        # containment.
        if left.offset < right.offset or left_end > right_end:
            return RangeRelation.CONTAINS
        return RangeRelation.EXACT
    if right.offset <= left.offset and right_end >= left_end:
        if right.offset < left.offset or right_end > left_end:
            return RangeRelation.CONTAINED
        return RangeRelation.EXACT
    if left.offset < right_end and right.offset < left_end:
        return RangeRelation.OVERLAPS
    return RangeRelation.DISJOINT


@dataclass(frozen=True)
class RangePolicyDecision:
    """Closed decision produced by :func:`resolve_range_lookup`."""

    disposition: RangeLookupDisposition
    policy: RangeMatchPolicy
    relation: RangeRelation | None = None
    matched: RangeBinding | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "disposition": self.disposition.value,
            "policy": self.policy.value,
            "relation": None if self.relation is None else self.relation.value,
            "matched": None if self.matched is None else self.matched.to_dict(),
        }


def resolve_range_lookup(
    requested: RangeBinding,
    candidates: Iterable[RangeBinding],
    *,
    policy: RangeMatchPolicy = RangeMatchPolicy.EXACT_ONLY,
) -> RangePolicyDecision:
    """Apply a deterministic match policy against candidate bindings.

    Under :attr:`RangeMatchPolicy.EXACT_ONLY` the first candidate whose full
    binding equals ``requested`` (including generation and extent) is an exact
    hit.  Overlapping or covering candidates never promote to a hit: they are
    classified and ignored so partial-range aliasing cannot return wrong bytes.
    Candidate order is irrelevant for correctness because only exact equality
    admits; the first exact match is returned for stable diagnostics.
    """

    if not isinstance(requested, RangeBinding):
        raise RangePolicyError("requested must be a RangeBinding")
    if not isinstance(policy, RangeMatchPolicy):
        try:
            policy = RangeMatchPolicy(policy)
        except (TypeError, ValueError) as exc:
            raise RangePolicyError(f"unknown range match policy: {policy!r}") from exc
    if policy is not RangeMatchPolicy.EXACT_ONLY:
        raise RangePolicyError(f"unsupported range match policy: {policy!r}")

    first_non_exact: RangeRelation | None = None
    for candidate in candidates:
        if not isinstance(candidate, RangeBinding):
            raise RangePolicyError("candidates must be RangeBinding values")
        relation = classify_range_relation(requested, candidate)
        if relation is RangeRelation.EXACT:
            return RangePolicyDecision(
                disposition=RangeLookupDisposition.EXACT_HIT,
                policy=policy,
                relation=relation,
                matched=candidate,
            )
        if first_non_exact is None and relation is not RangeRelation.IDENTITY_MISMATCH:
            first_non_exact = relation
    return RangePolicyDecision(
        disposition=RangeLookupDisposition.MISS,
        policy=policy,
        relation=first_non_exact,
        matched=None,
    )


def single_flight_compatible(left: RangeBinding, right: RangeBinding) -> bool:
    """True iff two misses may join the same single-flight.

    Requires equal generation, identity, serializer, policy, and exact range.
    Overlapping ranges and generation skew never share a flight.
    """

    return classify_range_relation(left, right) is RangeRelation.EXACT


# ---------------------------------------------------------------------------
# Generation-aware single-flight
# ---------------------------------------------------------------------------


class GenerationAwareRangeSingleFlight:
    """Coordinate range fills so only equal-generation exact keys single-flight.

    This is a thin, generation-aware facade over :class:`SingleFlightARC`.  The
    flight map key is :attr:`RangeBinding.flight_key`, which already embeds
    generation; therefore:

    * concurrent misses for the same binding elect one filler;
    * a different generation is a different key and starts an independent fill;
    * cancellation / failure wakes only waiters of that exact flight (bounded
      fan-out); and
    * admitted values flow through the injected ARC so byte and ghost
      invariants remain those of the core implementation.
    """

    SCHEMA: ClassVar[str] = RANGE_SINGLE_FLIGHT_SCHEMA
    CONTRACT_VERSION: ClassVar[int] = CONTRACT_VERSION
    DEFAULT_POLICY: ClassVar[RangeMatchPolicy] = RangeMatchPolicy.EXACT_ONLY

    def __init__(
        self,
        cache: AdaptiveReplacementCacheProtocol,
        *,
        policy: RangeMatchPolicy = RangeMatchPolicy.EXACT_ONLY,
        max_inflight: int = MAX_INFLIGHT_FLIGHTS,
    ) -> None:
        if not isinstance(cache, AdaptiveReplacementCacheProtocol):
            raise TypeError("cache must be an AdaptiveReplacementCache")
        if not isinstance(policy, RangeMatchPolicy):
            try:
                policy = RangeMatchPolicy(policy)
            except (TypeError, ValueError) as exc:
                raise RangePolicyError(f"unknown range match policy: {policy!r}") from exc
        if policy is not RangeMatchPolicy.EXACT_ONLY:
            raise RangePolicyError(f"unsupported range match policy: {policy!r}")
        max_inflight = require_bounded_int(
            max_inflight, name="max_inflight", minimum=1, maximum=MAX_SAFE_INTEGER
        )
        self._cache = cache
        self._policy = policy
        self._coordinator = SingleFlightARC(cache)
        # Mirror the coordinator bound so tests and diagnostics see the same
        # ceiling; SingleFlightARC enforces its own map cardinality.
        self._coordinator._max_inflight = max_inflight
        self._max_inflight = max_inflight

    @property
    def cache(self) -> AdaptiveReplacementCacheProtocol:
        return self._cache

    @property
    def policy(self) -> RangeMatchPolicy:
        return self._policy

    @property
    def max_inflight(self) -> int:
        return self._max_inflight

    @property
    def inflight_count(self) -> int:
        return self._coordinator.inflight_count

    @property
    def waiting_count(self) -> int:
        return self._coordinator.waiting_count

    def get(self, binding: RangeBinding) -> bytes | None:
        """Return a live ARC value for the exact binding, or ``None`` on miss."""

        binding = self._coerce_binding(binding)
        return self._cache.get(binding.cache_key)

    def put(self, binding: RangeBinding, value: bytes) -> bool:
        """Admit ``value`` under the exact binding key.

        The value length must equal ``binding.length`` so a range key cannot
        alias a differently sized payload.
        """

        binding = self._coerce_binding(binding)
        if not isinstance(value, (bytes, bytearray, memoryview)):
            raise TypeError("value must be bytes-like")
        data = bytes(value)
        if len(data) != binding.length:
            raise RangeExtentError(
                f"value length {len(data)} disagrees with binding length {binding.length}"
            )
        return self._cache.put(binding.cache_key, data)

    def contains(self, binding: RangeBinding) -> bool:
        binding = self._coerce_binding(binding)
        return self._cache.contains(binding.cache_key)

    def delete(self, binding: RangeBinding) -> bool:
        binding = self._coerce_binding(binding)
        return self._cache.delete(binding.cache_key)

    def get_or_fill_result(
        self,
        binding: RangeBinding,
        filler: Callable[[], bytes],
    ) -> CacheFillResult:
        """Return a typed fill result, single-flighting equal-generation misses."""

        binding = self._coerce_binding(binding)
        if not callable(filler):
            raise TypeError("filler must be callable")

        def _checked_filler() -> bytes:
            raw = filler()
            if not isinstance(raw, (bytes, bytearray, memoryview)):
                raise TypeError("filler must return bytes-like")
            data = bytes(raw)
            if len(data) != binding.length:
                raise RangeExtentError(
                    f"filler length {len(data)} disagrees with binding length "
                    f"{binding.length}"
                )
            return data

        result = self._coordinator.get_or_fill_result(binding.flight_key, _checked_filler)
        # Re-bind the public key field to the validated range key string so
        # callers comparing against RangeBinding.cache_key stay consistent.
        if result.key != binding.cache_key:
            return CacheFillResult(
                key=binding.cache_key,
                status=result.status,
                value=result.value,
                error=result.error,
            )
        return result

    def get_or_fill(self, binding: RangeBinding, filler: Callable[[], bytes]) -> bytes:
        """Return filled or cached bytes, raising a typed error on failure."""

        return self.get_or_fill_result(binding, filler).unwrap()

    def cancel(self, binding: RangeBinding) -> bool:
        """Cancel the in-flight fill for this exact binding (bounded fan-out)."""

        binding = self._coerce_binding(binding)
        return self._coordinator.cancel(binding.flight_key)

    def lookup(
        self,
        requested: RangeBinding,
        candidates: Sequence[RangeBinding],
    ) -> RangePolicyDecision:
        """Expose the deterministic exact/overlap policy without touching ARC."""

        requested = self._coerce_binding(requested)
        return resolve_range_lookup(requested, candidates, policy=self._policy)

    @staticmethod
    def _coerce_binding(binding: RangeBinding | Mapping[str, Any]) -> RangeBinding:
        if isinstance(binding, RangeBinding):
            return binding
        return RangeBinding.from_dict(binding)


# Public aliases matching plan vocabulary.
RangeCacheKey = RangeBinding
ChunkBinding = RangeBinding
GenerationBoundRangeKey = RangeBinding
RangeSingleFlight = GenerationAwareRangeSingleFlight
ARCRangeCoordinator = GenerationAwareRangeSingleFlight


__all__ = [
    "CONTRACT_VERSION",
    "SCHEMA_VERSION",
    "SCHEMA_MAJOR",
    "RANGE_BINDING_SCHEMA",
    "RANGE_SINGLE_FLIGHT_SCHEMA",
    "RangeBinding_V1",
    "GenerationAwareRangeSingleFlight_V1",
    "DEFAULT_NAMESPACE",
    "DEFAULT_SERIALIZER",
    "DEFAULT_POLICY",
    "DEFAULT_GENERATION",
    "MAX_RANGE_LENGTH",
    "MAX_IDENTITY_BYTES",
    "MAX_INFLIGHT_FLIGHTS",
    "RangeBindingError",
    "RangeIdentityError",
    "RangeExtentError",
    "RangePolicyError",
    "RangeRelation",
    "RangeMatchPolicy",
    "RangeLookupDisposition",
    "validate_offset",
    "validate_length",
    "validate_range_extent",
    "RangeBinding",
    "RangeCacheKey",
    "ChunkBinding",
    "GenerationBoundRangeKey",
    "range_end",
    "ranges_overlap",
    "classify_range_relation",
    "RangePolicyDecision",
    "resolve_range_lookup",
    "single_flight_compatible",
    "GenerationAwareRangeSingleFlight",
    "RangeSingleFlight",
    "ARCRangeCoordinator",
    # Re-exported fill types for test/call-site convenience.
    "FillStatus",
    "CacheFillResult",
    "CacheFillError",
    "CacheFillCancelled",
    "CacheFillRejected",
]
