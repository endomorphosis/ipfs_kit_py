"""Committed read-through and bounded range admission (KVFS-401).

This module owns the *read path / admission* surface that connects generation-
bound range keys (KVFS-400) to a shared ARC for kernel-shaped reads:

* **Cache hits revalidate exact bindings** — a live ARC value is returned only
  when the stored :class:`~ipfs_kit_py.cache.arc.range_bindings.RangeBinding`
  equals the request (namespace, content/inode, version, generation,
  serializer, policy, offset, length) *and* authorization / consistency gates
  approve;
* **Misses fetch only requested bounded ranges** — the committed source is
  invoked with the exact ``(offset, length)`` of each admitable segment, never
  a whole-object load invented by this layer;
* **Dirty staged bytes never enter shared ARC** — scopes marked dirty (or
  reads that carry a dirty overlay) bypass admission; only committed filler
  results may be put;
* **Policy / authorization-sensitive scopes cannot alias** — ``policy`` is part
  of every cache key, and authorize predicates are fail-closed;
* **Oversized ranges bypass or segment predictably** — lengths above the
  admitable ceiling either bypass the shared ARC or are split into consecutive
  bounded segments under a closed policy;
* **Errors and corrupt entries become safe misses** — filler failures, length
  mismatches, and corrupt live values never surface as hits and never poison
  ARC with bad payloads.

Mutation invalidation / generation advance belongs to KVFS-404.  This module
does not import fusepy, open host mounts, or perform network I/O.

Interfaces (plan aliases): ``CachedStorage@1``, ``CommittedReadThrough@1``,
``BoundedRangeAdmission@1``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from threading import RLock
from typing import Any, ClassVar, Final, Protocol, runtime_checkable

from ipfs_kit_py.cache.arc.cache import AdaptiveReplacementCache
from ipfs_kit_py.cache.arc.concurrency import (
    CacheFillCancelled,
    CacheFillError,
    CacheFillRejected,
    CacheFillResult,
    FillStatus,
)
from ipfs_kit_py.cache.arc.contracts import (
    ARCConfig,
    AdaptiveReplacementCache as AdaptiveReplacementCacheProtocol,
    MAX_SAFE_INTEGER,
    require_bounded_int,
)
from ipfs_kit_py.cache.arc.range_bindings import (
    DEFAULT_GENERATION,
    DEFAULT_NAMESPACE,
    DEFAULT_POLICY,
    DEFAULT_SERIALIZER,
    MAX_INFLIGHT_FLIGHTS,
    MAX_RANGE_LENGTH,
    GenerationAwareRangeSingleFlight,
    RangeBinding,
    RangeExtentError,
    RangeIdentityError,
    RangeLookupDisposition,
    RangeMatchPolicy,
    RangePolicyDecision,
    resolve_range_lookup,
    validate_offset,
    validate_range_extent,
)

# ---------------------------------------------------------------------------
# Schema / version / bounds
# ---------------------------------------------------------------------------

TASK_ID: Final[str] = "KVFS-401"
CONTRACT_VERSION: Final[int] = 1
SCHEMA_MAJOR: Final[int] = 1
SCHEMA_MINOR: Final[int] = 0
SCHEMA_PATCH: Final[int] = 0
SCHEMA_VERSION: Final[str] = f"{SCHEMA_MAJOR}.{SCHEMA_MINOR}.{SCHEMA_PATCH}"

CACHED_STORAGE_NAMESPACE: Final[str] = "ipfs_kit_py/kernel_vfs/cached_storage"

CACHED_STORAGE_SCHEMA: Final[str] = (
    f"{CACHED_STORAGE_NAMESPACE}/cached-storage@{SCHEMA_MAJOR}"
)
COMMITTED_READ_THROUGH_SCHEMA: Final[str] = (
    f"{CACHED_STORAGE_NAMESPACE}/committed-read-through@{SCHEMA_MAJOR}"
)
BOUNDED_RANGE_ADMISSION_SCHEMA: Final[str] = (
    f"{CACHED_STORAGE_NAMESPACE}/bounded-range-admission@{SCHEMA_MAJOR}"
)
READ_THROUGH_RESULT_SCHEMA: Final[str] = (
    f"{CACHED_STORAGE_NAMESPACE}/read-through-result@{SCHEMA_MAJOR}"
)
ADMISSION_METRICS_SCHEMA: Final[str] = (
    f"{CACHED_STORAGE_NAMESPACE}/admission-metrics@{SCHEMA_MAJOR}"
)

# Public interface aliases.
CachedStorage_V1: Final[str] = CACHED_STORAGE_SCHEMA
CommittedReadThrough_V1: Final[str] = COMMITTED_READ_THROUGH_SCHEMA
BoundedRangeAdmission_V1: Final[str] = BOUNDED_RANGE_ADMISSION_SCHEMA

# Align segment size with ranged-storage default chunk so FUSE-sized reads
# share a single capacity story with the storage boundary.
DEFAULT_SEGMENT_BYTES: Final[int] = 65_536  # 64 KiB
DEFAULT_CAPACITY_BYTES: Final[int] = 4 * 1024 * 1024  # 4 MiB hermetic default
DEFAULT_MAX_READ_BYTES: Final[int] = 64 * 1024 * 1024  # 64 MiB single-call ceiling
MAX_DIRTY_SCOPES: Final[int] = 65_536
MAX_SEGMENTS_PER_READ: Final[int] = 4_096


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class CachedStorageError(Exception):
    """Base class for committed read-through failures."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "CACHED_STORAGE_ERROR",
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.detail = dict(detail or {})


class AdmissionRejected(CachedStorageError):
    """Authorization, consistency, or dirty-scope gate refused the read."""

    def __init__(
        self,
        message: str = "admission rejected",
        *,
        code: str = "ADMISSION_REJECTED",
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, detail=detail)


class DirtyAdmissionError(AdmissionRejected):
    """An attempt was made to admit dirty staged bytes into shared ARC."""

    def __init__(
        self,
        message: str = "dirty staged bytes cannot enter shared ARC",
        **kwargs: Any,
    ) -> None:
        super().__init__(message, code="DIRTY_ADMISSION", **kwargs)


class SourceFetchError(CachedStorageError):
    """The committed source failed; treated as a safe miss at the API edge."""

    def __init__(
        self,
        message: str = "committed source fetch failed",
        *,
        cause: BaseException | None = None,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code="SOURCE_FETCH_FAILED", detail=detail)
        self.cause = cause


class CorruptCacheEntryError(CachedStorageError):
    """A live ARC payload failed integrity revalidation."""

    def __init__(
        self,
        message: str = "corrupt cache entry",
        *,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code="CORRUPT_CACHE_ENTRY", detail=detail)


class OversizedRangeError(CachedStorageError):
    """A read length exceeds the hard single-call ceiling."""

    def __init__(
        self,
        message: str = "read range exceeds hard ceiling",
        *,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code="OVERSIZED_RANGE", detail=detail)


# ---------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------


class AdmissionDisposition(str, Enum):
    """Closed outcome of one committed read-through attempt."""

    HIT = "hit"
    FILLED = "filled"
    BYPASS = "bypass"
    SEGMENTED = "segmented"
    DIRTY_BYPASS = "dirty_bypass"
    SAFE_MISS = "safe_miss"
    REJECTED = "rejected"
    FAILED = "failed"


class OversizedRangeMode(str, Enum):
    """How lengths above the admitable ARC ceiling are handled.

    * ``BYPASS`` — fetch the full requested range from the committed source
      once and never put the result into shared ARC.
    * ``SEGMENT`` — split the request into consecutive bounded segments, each
      admitted (or hit) under its own exact :class:`RangeBinding`, then
      concatenate.  Segments never over-fetch past the requested end.
    """

    BYPASS = "bypass"
    SEGMENT = "segment"


# ---------------------------------------------------------------------------
# Metrics / result records
# ---------------------------------------------------------------------------


@dataclass
class AdmissionMetrics:
    """Bounded counters for committed read-through diagnostics."""

    SCHEMA: ClassVar[str] = ADMISSION_METRICS_SCHEMA

    hits: int = 0
    misses: int = 0
    fills: int = 0
    bypasses: int = 0
    segmented_reads: int = 0
    dirty_bypasses: int = 0
    safe_misses: int = 0
    authorization_rejections: int = 0
    consistency_rejections: int = 0
    dirty_admission_rejections: int = 0
    corrupt_entries: int = 0
    source_fetches: int = 0
    source_errors: int = 0
    bytes_served: int = 0
    bytes_admitted: int = 0
    bytes_fetched: int = 0

    def snapshot(self) -> "AdmissionMetrics":
        return AdmissionMetrics(
            hits=self.hits,
            misses=self.misses,
            fills=self.fills,
            bypasses=self.bypasses,
            segmented_reads=self.segmented_reads,
            dirty_bypasses=self.dirty_bypasses,
            safe_misses=self.safe_misses,
            authorization_rejections=self.authorization_rejections,
            consistency_rejections=self.consistency_rejections,
            dirty_admission_rejections=self.dirty_admission_rejections,
            corrupt_entries=self.corrupt_entries,
            source_fetches=self.source_fetches,
            source_errors=self.source_errors,
            bytes_served=self.bytes_served,
            bytes_admitted=self.bytes_admitted,
            bytes_fetched=self.bytes_fetched,
        )

    def to_dict(self) -> dict[str, int]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "fills": self.fills,
            "bypasses": self.bypasses,
            "segmented_reads": self.segmented_reads,
            "dirty_bypasses": self.dirty_bypasses,
            "safe_misses": self.safe_misses,
            "authorization_rejections": self.authorization_rejections,
            "consistency_rejections": self.consistency_rejections,
            "dirty_admission_rejections": self.dirty_admission_rejections,
            "corrupt_entries": self.corrupt_entries,
            "source_fetches": self.source_fetches,
            "source_errors": self.source_errors,
            "bytes_served": self.bytes_served,
            "bytes_admitted": self.bytes_admitted,
            "bytes_fetched": self.bytes_fetched,
        }


@dataclass(frozen=True)
class ReadThroughResult:
    """Immutable outcome of one :meth:`CachedStorage.read` call."""

    SCHEMA: ClassVar[str] = READ_THROUGH_RESULT_SCHEMA

    data: bytes
    disposition: AdmissionDisposition
    offset: int
    length: int
    admitted: bool = False
    source_fetches: int = 0
    segments: int = 0
    binding: RangeBinding | None = None
    reason: str = ""
    from_cache: bool = False

    @property
    def ok(self) -> bool:
        return self.disposition in {
            AdmissionDisposition.HIT,
            AdmissionDisposition.FILLED,
            AdmissionDisposition.BYPASS,
            AdmissionDisposition.SEGMENTED,
            AdmissionDisposition.DIRTY_BYPASS,
        }

    @property
    def is_hit(self) -> bool:
        return self.disposition is AdmissionDisposition.HIT

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "disposition": self.disposition.value,
            "offset": self.offset,
            "length": self.length,
            "data_size": len(self.data),
            "admitted": self.admitted,
            "source_fetches": self.source_fetches,
            "segments": self.segments,
            "from_cache": self.from_cache,
            "reason": self.reason,
            "binding": None if self.binding is None else self.binding.to_dict(),
        }


@dataclass(frozen=True)
class RangeSegment:
    """One consecutive admitable sub-range of a (possibly oversized) read."""

    offset: int
    length: int

    def __post_init__(self) -> None:
        off, length_i = validate_range_extent(self.offset, self.length)
        object.__setattr__(self, "offset", off)
        object.__setattr__(self, "length", length_i)

    @property
    def end(self) -> int:
        return self.offset + self.length

    def to_dict(self) -> dict[str, int]:
        return {"offset": self.offset, "length": self.length}


# ---------------------------------------------------------------------------
# Source protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class CommittedRangeSource(Protocol):
    """Protocol for a committed (non-dirty) byte-range source."""

    def fetch_range(self, binding: RangeBinding) -> bytes:
        """Return exactly ``binding.length`` committed bytes at ``binding.offset``."""
        ...


# Type alias for callables used as committed fillers.
CommittedFiller = Callable[[RangeBinding], bytes]


# ---------------------------------------------------------------------------
# Segmentation helpers
# ---------------------------------------------------------------------------


def plan_bounded_segments(
    offset: int,
    length: int,
    *,
    max_segment_bytes: int = MAX_RANGE_LENGTH,
) -> list[RangeSegment]:
    """Split ``[offset, offset+length)`` into consecutive admitable segments.

    Segments cover *exactly* the requested interval — no padding before the
    start offset and no over-fetch past the exclusive end.  Each segment length
    is in ``[1, max_segment_bytes]``.
    """

    off = validate_offset(offset)
    length_i = require_bounded_int(
        length, name="length", minimum=1, maximum=MAX_SAFE_INTEGER
    )
    max_seg = require_bounded_int(
        max_segment_bytes,
        name="max_segment_bytes",
        minimum=1,
        maximum=MAX_RANGE_LENGTH,
    )
    end = off + length_i
    if end > MAX_SAFE_INTEGER:
        raise RangeExtentError(
            f"range end offset+length={end} exceeds MAX_SAFE_INTEGER"
        )
    estimated = (length_i + max_seg - 1) // max_seg
    if estimated > MAX_SEGMENTS_PER_READ:
        raise OversizedRangeError(
            f"read would require {estimated} segments; ceiling is "
            f"{MAX_SEGMENTS_PER_READ}",
            detail={"length": length_i, "max_segment_bytes": max_seg},
        )
    segments: list[RangeSegment] = []
    pos = off
    while pos < end:
        chunk = min(max_seg, end - pos)
        segments.append(RangeSegment(offset=pos, length=chunk))
        pos += chunk
    return segments


def is_admitable_length(length: int, *, maximum: int = MAX_RANGE_LENGTH) -> bool:
    """True when ``length`` may form a single ARC range binding."""

    try:
        require_bounded_int(length, name="length", minimum=1, maximum=maximum)
    except ValueError:
        return False
    return True


# ---------------------------------------------------------------------------
# Dirty scope identity
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DirtyScope:
    """Identity of a content scope whose staged bytes must not enter ARC.

    Dirty tracking is coarser than a single range: any uncommitted write for
    ``(namespace, content_id)`` (optionally pinned to a version) blocks
    admission for that scope until cleared after commit.
    """

    namespace: str
    content_id: str
    version: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.namespace, str) or not self.namespace:
            raise RangeIdentityError("namespace must be a non-empty str")
        if not isinstance(self.content_id, str) or not self.content_id:
            raise RangeIdentityError("content_id must be a non-empty str")
        if self.version is not None and (
            not isinstance(self.version, str) or not self.version
        ):
            raise RangeIdentityError("version must be a non-empty str or None")

    def matches(self, binding: RangeBinding) -> bool:
        if binding.namespace != self.namespace:
            return False
        if binding.content_id != self.content_id:
            return False
        if self.version is not None and binding.version != self.version:
            return False
        return True

    def key(self) -> tuple[str, str, str | None]:
        return (self.namespace, self.content_id, self.version)


def _scope_from_binding(binding: RangeBinding) -> DirtyScope:
    return DirtyScope(
        namespace=binding.namespace,
        content_id=binding.content_id,
        version=binding.version,
    )


# ---------------------------------------------------------------------------
# CachedStorage
# ---------------------------------------------------------------------------


class CachedStorage:
    """Committed read-through facade over generation-bound range ARC.

    The shared ARC receives only committed, authorize-approved, integrity-
    validated range payloads under exact :class:`RangeBinding` keys.  Dirty
    staged bytes, oversized bypass results, and failed/corrupt observations
    never enter the cache.
    """

    SCHEMA: ClassVar[str] = CACHED_STORAGE_SCHEMA
    CONTRACT_VERSION: ClassVar[int] = CONTRACT_VERSION
    INTERFACE: ClassVar[str] = CachedStorage_V1

    def __init__(
        self,
        cache: AdaptiveReplacementCacheProtocol | None = None,
        *,
        source: CommittedRangeSource | CommittedFiller | None = None,
        config: ARCConfig | None = None,
        capacity_bytes: int = DEFAULT_CAPACITY_BYTES,
        max_range_length: int = MAX_RANGE_LENGTH,
        segment_bytes: int = DEFAULT_SEGMENT_BYTES,
        max_read_bytes: int = DEFAULT_MAX_READ_BYTES,
        oversized_mode: OversizedRangeMode | str = OversizedRangeMode.SEGMENT,
        max_inflight: int = MAX_INFLIGHT_FLIGHTS,
        authorize: Callable[[RangeBinding], bool] | None = None,
        consistent: Callable[[RangeBinding], bool] | None = None,
        require_predicates: bool = True,
    ) -> None:
        if cache is not None and config is not None:
            raise TypeError("pass either cache or config, not both")
        if cache is None:
            if config is None:
                config = ARCConfig(capacity_bytes=capacity_bytes)
            cache = AdaptiveReplacementCache(config)
        if not isinstance(cache, AdaptiveReplacementCacheProtocol):
            raise TypeError("cache must be an AdaptiveReplacementCache")

        max_range_length = require_bounded_int(
            max_range_length,
            name="max_range_length",
            minimum=1,
            maximum=MAX_RANGE_LENGTH,
        )
        segment_bytes = require_bounded_int(
            segment_bytes,
            name="segment_bytes",
            minimum=1,
            maximum=max_range_length,
        )
        max_read_bytes = require_bounded_int(
            max_read_bytes,
            name="max_read_bytes",
            minimum=1,
            maximum=MAX_SAFE_INTEGER,
        )
        if not isinstance(oversized_mode, OversizedRangeMode):
            try:
                oversized_mode = OversizedRangeMode(oversized_mode)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"unknown oversized_mode: {oversized_mode!r}"
                ) from exc

        self._lock = RLock()
        self._cache = cache
        self._coordinator = GenerationAwareRangeSingleFlight(
            cache, max_inflight=max_inflight
        )
        self._source = source
        self._max_range_length = max_range_length
        self._segment_bytes = segment_bytes
        self._max_read_bytes = max_read_bytes
        self._oversized_mode = oversized_mode
        self._authorize = authorize
        self._consistent = consistent
        self._require_predicates = bool(require_predicates)
        # Side map: cache_key -> exact binding admitted under that key.
        self._bindings: dict[str, RangeBinding] = {}
        # Dirty scopes: block ARC admission until cleared after commit.
        self._dirty: dict[tuple[str, str, str | None], DirtyScope] = {}
        self._metrics = AdmissionMetrics()

    # --- properties --------------------------------------------------------

    @property
    def cache(self) -> AdaptiveReplacementCacheProtocol:
        return self._cache

    @property
    def coordinator(self) -> GenerationAwareRangeSingleFlight:
        return self._coordinator

    @property
    def max_range_length(self) -> int:
        return self._max_range_length

    @property
    def segment_bytes(self) -> int:
        return self._segment_bytes

    @property
    def max_read_bytes(self) -> int:
        return self._max_read_bytes

    @property
    def oversized_mode(self) -> OversizedRangeMode:
        return self._oversized_mode

    @property
    def dirty_scope_count(self) -> int:
        with self._lock:
            return len(self._dirty)

    def metrics(self) -> AdmissionMetrics:
        with self._lock:
            return self._metrics.snapshot()

    # --- dirty scope management --------------------------------------------

    def mark_dirty(
        self,
        *,
        namespace: str = DEFAULT_NAMESPACE,
        content_id: str | None = None,
        inode: str | int | None = None,
        version: str | None = None,
        binding: RangeBinding | None = None,
    ) -> DirtyScope:
        """Mark a content scope dirty so staged bytes cannot enter shared ARC."""

        scope = self._resolve_dirty_scope(
            namespace=namespace,
            content_id=content_id,
            inode=inode,
            version=version,
            binding=binding,
        )
        with self._lock:
            if (
                scope.key() not in self._dirty
                and len(self._dirty) >= MAX_DIRTY_SCOPES
            ):
                raise CachedStorageError(
                    f"dirty scope map is bounded at {MAX_DIRTY_SCOPES}",
                    code="DIRTY_SCOPE_LIMIT",
                )
            self._dirty[scope.key()] = scope
            # Evict any live committed entries for this scope so a later hit
            # cannot serve pre-dirty committed bytes mixed with staged state.
            self._evict_scope_locked(scope)
        return scope

    def clear_dirty(
        self,
        *,
        namespace: str = DEFAULT_NAMESPACE,
        content_id: str | None = None,
        inode: str | int | None = None,
        version: str | None = None,
        binding: RangeBinding | None = None,
    ) -> bool:
        """Clear dirty marking after a successful commit (or abort discard)."""

        scope = self._resolve_dirty_scope(
            namespace=namespace,
            content_id=content_id,
            inode=inode,
            version=version,
            binding=binding,
        )
        with self._lock:
            return self._dirty.pop(scope.key(), None) is not None

    def is_dirty(
        self,
        binding: RangeBinding | None = None,
        *,
        namespace: str = DEFAULT_NAMESPACE,
        content_id: str | None = None,
        inode: str | int | None = None,
        version: str | None = None,
    ) -> bool:
        if binding is not None:
            with self._lock:
                return self._is_dirty_locked(binding)
        scope = self._resolve_dirty_scope(
            namespace=namespace,
            content_id=content_id,
            inode=inode,
            version=version,
            binding=None,
        )
        with self._lock:
            return scope.key() in self._dirty

    # --- direct get / put (exact binding) ----------------------------------

    def get(
        self,
        binding: RangeBinding | Mapping[str, Any],
        *,
        authorize: Callable[[RangeBinding], bool] | None = None,
        consistent: Callable[[RangeBinding], bool] | None = None,
    ) -> bytes | None:
        """Return a revalidated exact-binding hit, or ``None`` as a safe miss.

        Never fetches from the committed source.  Corrupt / stale / unauthorized
        entries are removed and counted as safe misses.
        """

        identity = self._coerce_binding(binding)
        auth = self._resolve_authorize(authorize)
        cons = self._resolve_consistent(consistent)

        with self._lock:
            if self._is_dirty_locked(identity):
                self._metrics.dirty_bypasses += 1
                return None
            if not self._gates_pass_locked(identity, auth, cons, count=True):
                return None
            return self._revalidated_get_locked(identity)

    def put_committed(
        self,
        binding: RangeBinding | Mapping[str, Any],
        value: bytes,
        *,
        authorize: Callable[[RangeBinding], bool] | None = None,
        consistent: Callable[[RangeBinding], bool] | None = None,
    ) -> bool:
        """Admit committed bytes under an exact binding.

        Rejects dirty scopes, length mismatches, and failed gates.  Never
        admits dirty staged overlays.
        """

        identity = self._coerce_binding(binding)
        if not isinstance(value, (bytes, bytearray, memoryview)):
            raise TypeError("value must be bytes-like")
        data = bytes(value)
        if len(data) != identity.length:
            raise RangeExtentError(
                f"value length {len(data)} disagrees with binding length "
                f"{identity.length}"
            )
        auth = self._resolve_authorize(authorize)
        cons = self._resolve_consistent(consistent)

        with self._lock:
            if self._is_dirty_locked(identity):
                self._metrics.dirty_admission_rejections += 1
                raise DirtyAdmissionError(
                    detail={"cache_key": identity.cache_key}
                )
            if not self._gates_pass_locked(identity, auth, cons, count=True):
                return False
            admitted = self._cache.put(identity.cache_key, data)
            if admitted:
                self._bindings[identity.cache_key] = identity
                self._metrics.bytes_admitted += len(data)
                self._prune_bindings_locked()
            return admitted

    def contains(self, binding: RangeBinding | Mapping[str, Any]) -> bool:
        identity = self._coerce_binding(binding)
        with self._lock:
            stored = self._bindings.get(identity.cache_key)
            return (
                stored == identity
                and self._cache.contains(identity.cache_key)
                and not self._is_dirty_locked(identity)
            )

    def delete(self, binding: RangeBinding | Mapping[str, Any]) -> bool:
        identity = self._coerce_binding(binding)
        with self._lock:
            return self._remove_key_locked(identity.cache_key)

    def lookup(
        self,
        requested: RangeBinding,
        candidates: Sequence[RangeBinding],
    ) -> RangePolicyDecision:
        """Expose exact-range policy without touching ARC (no aliasing)."""

        return resolve_range_lookup(
            requested, candidates, policy=RangeMatchPolicy.EXACT_ONLY
        )

    # --- read-through ------------------------------------------------------

    def read(
        self,
        binding: RangeBinding | Mapping[str, Any] | None = None,
        *,
        namespace: str = DEFAULT_NAMESPACE,
        content_id: str | None = None,
        inode: str | int | None = None,
        version: str | None = None,
        generation: str = DEFAULT_GENERATION,
        serializer: str = DEFAULT_SERIALIZER,
        policy: str = DEFAULT_POLICY,
        offset: int = 0,
        length: int | None = None,
        source: CommittedRangeSource | CommittedFiller | None = None,
        authorize: Callable[[RangeBinding], bool] | None = None,
        consistent: Callable[[RangeBinding], bool] | None = None,
        dirty: bool = False,
        dirty_overlay: bytes | None = None,
    ) -> ReadThroughResult:
        """Committed read-through for a (possibly oversized) byte range.

        Parameters
        ----------
        binding:
            Exact range binding when the request is already within the
            admitable ceiling.  Mutually exclusive with free identity fields.
        dirty / dirty_overlay:
            When either is set, the result is assembled without ARC admission.
            ``dirty_overlay`` (if provided) is returned as the read data for
            the requested extent and is never put into shared ARC.
        """

        identity_fields = self._resolve_identity(
            binding=binding,
            namespace=namespace,
            content_id=content_id,
            inode=inode,
            version=version,
            generation=generation,
            serializer=serializer,
            policy=policy,
            offset=offset,
            length=length,
        )
        off = identity_fields["offset"]
        length_i = identity_fields["length"]
        if length_i > self._max_read_bytes:
            raise OversizedRangeError(
                f"read length {length_i} exceeds max_read_bytes "
                f"{self._max_read_bytes}",
                detail={
                    "length": length_i,
                    "max_read_bytes": self._max_read_bytes,
                },
            )

        auth = self._resolve_authorize(authorize)
        cons = self._resolve_consistent(consistent)
        filler = source if source is not None else self._source

        # Dirty overlay path: never touch shared ARC for admission.
        if dirty or dirty_overlay is not None:
            return self._read_dirty(
                identity_fields=identity_fields,
                dirty_overlay=dirty_overlay,
                filler=filler,
                auth=auth,
                cons=cons,
            )

        # Single admitable binding path.
        if length_i <= self._max_range_length:
            single = RangeBinding(
                namespace=identity_fields["namespace"],
                content_id=identity_fields["content_id"],
                version=identity_fields["version"],
                generation=identity_fields["generation"],
                serializer=identity_fields["serializer"],
                offset=off,
                length=length_i,
                policy=identity_fields["policy"],
            )
            return self._read_single(
                single, filler=filler, auth=auth, cons=cons
            )

        # Oversized: bypass or segment.
        if self._oversized_mode is OversizedRangeMode.BYPASS:
            return self._read_bypass(
                identity_fields=identity_fields,
                filler=filler,
                auth=auth,
                cons=cons,
            )
        return self._read_segmented(
            identity_fields=identity_fields,
            filler=filler,
            auth=auth,
            cons=cons,
        )

    def read_range(
        self,
        *,
        offset: int,
        length: int,
        namespace: str = DEFAULT_NAMESPACE,
        content_id: str | None = None,
        inode: str | int | None = None,
        version: str,
        generation: str = DEFAULT_GENERATION,
        serializer: str = DEFAULT_SERIALIZER,
        policy: str = DEFAULT_POLICY,
        source: CommittedRangeSource | CommittedFiller | None = None,
        authorize: Callable[[RangeBinding], bool] | None = None,
        consistent: Callable[[RangeBinding], bool] | None = None,
        dirty: bool = False,
        dirty_overlay: bytes | None = None,
    ) -> ReadThroughResult:
        """Keyword-friendly alias for :meth:`read`."""

        return self.read(
            namespace=namespace,
            content_id=content_id,
            inode=inode,
            version=version,
            generation=generation,
            serializer=serializer,
            policy=policy,
            offset=offset,
            length=length,
            source=source,
            authorize=authorize,
            consistent=consistent,
            dirty=dirty,
            dirty_overlay=dirty_overlay,
        )

    # --- internal: dirty read ----------------------------------------------

    def _read_dirty(
        self,
        *,
        identity_fields: dict[str, Any],
        dirty_overlay: bytes | None,
        filler: CommittedRangeSource | CommittedFiller | None,
        auth: Callable[[RangeBinding], bool] | None,
        cons: Callable[[RangeBinding], bool] | None,
    ) -> ReadThroughResult:
        off = identity_fields["offset"]
        length_i = identity_fields["length"]
        # Build a probe binding for gates when length is admitable; otherwise
        # use a 1-byte probe at offset for authorize/consistent only.
        probe_length = min(length_i, self._max_range_length)
        probe = RangeBinding(
            namespace=identity_fields["namespace"],
            content_id=identity_fields["content_id"],
            version=identity_fields["version"],
            generation=identity_fields["generation"],
            serializer=identity_fields["serializer"],
            offset=off,
            length=probe_length,
            policy=identity_fields["policy"],
        )
        with self._lock:
            if not self._gates_pass_locked(probe, auth, cons, count=True):
                self._metrics.safe_misses += 1
                return ReadThroughResult(
                    data=b"",
                    disposition=AdmissionDisposition.REJECTED,
                    offset=off,
                    length=length_i,
                    reason="authorization_or_consistency",
                )
            # Ensure scope is recorded dirty so concurrent put_committed fails.
            scope = DirtyScope(
                namespace=probe.namespace,
                content_id=probe.content_id,
                version=probe.version,
            )
            self._dirty[scope.key()] = scope
            self._evict_scope_locked(scope)
            self._metrics.dirty_bypasses += 1

        if dirty_overlay is not None:
            if not isinstance(dirty_overlay, (bytes, bytearray, memoryview)):
                raise TypeError("dirty_overlay must be bytes-like")
            data = bytes(dirty_overlay)
            if len(data) != length_i:
                raise RangeExtentError(
                    f"dirty_overlay length {len(data)} disagrees with "
                    f"requested length {length_i}"
                )
            # Explicitly refuse to admit overlay bytes.
            with self._lock:
                self._metrics.bytes_served += len(data)
            return ReadThroughResult(
                data=data,
                disposition=AdmissionDisposition.DIRTY_BYPASS,
                offset=off,
                length=length_i,
                admitted=False,
                source_fetches=0,
                reason="dirty_overlay",
            )

        # No overlay: fetch committed base without admission (still dirty scope).
        data, fetches = self._fetch_unbounded(
            identity_fields, filler=filler, admit=False
        )
        with self._lock:
            self._metrics.bytes_served += len(data)
            self._metrics.source_fetches += fetches
            self._metrics.bytes_fetched += len(data)
        return ReadThroughResult(
            data=data,
            disposition=AdmissionDisposition.DIRTY_BYPASS,
            offset=off,
            length=length_i,
            admitted=False,
            source_fetches=fetches,
            reason="dirty_scope",
        )

    # --- internal: single binding ------------------------------------------

    def _read_single(
        self,
        binding: RangeBinding,
        *,
        filler: CommittedRangeSource | CommittedFiller | None,
        auth: Callable[[RangeBinding], bool] | None,
        cons: Callable[[RangeBinding], bool] | None,
    ) -> ReadThroughResult:
        with self._lock:
            dirty = self._is_dirty_locked(binding)
            if not self._gates_pass_locked(binding, auth, cons, count=True):
                self._metrics.safe_misses += 1
                return ReadThroughResult(
                    data=b"",
                    disposition=AdmissionDisposition.REJECTED,
                    offset=binding.offset,
                    length=binding.length,
                    binding=binding,
                    reason="authorization_or_consistency",
                )
            if not dirty:
                cached = self._revalidated_get_locked(binding)
                if cached is not None:
                    self._metrics.hits += 1
                    self._metrics.bytes_served += len(cached)
                    return ReadThroughResult(
                        data=cached,
                        disposition=AdmissionDisposition.HIT,
                        offset=binding.offset,
                        length=binding.length,
                        binding=binding,
                        admitted=False,
                        from_cache=True,
                    )
                self._metrics.misses += 1

        if dirty:
            if filler is None:
                with self._lock:
                    self._metrics.dirty_bypasses += 1
                    self._metrics.safe_misses += 1
                return ReadThroughResult(
                    data=b"",
                    disposition=AdmissionDisposition.DIRTY_BYPASS,
                    offset=binding.offset,
                    length=binding.length,
                    binding=binding,
                    admitted=False,
                    reason="dirty_scope_no_source",
                )
            try:
                data, fetches = self._fetch_binding(
                    binding, filler, admit=False
                )
            except SourceFetchError:
                with self._lock:
                    self._metrics.dirty_bypasses += 1
                    self._metrics.source_errors += 1
                    self._metrics.safe_misses += 1
                return ReadThroughResult(
                    data=b"",
                    disposition=AdmissionDisposition.SAFE_MISS,
                    offset=binding.offset,
                    length=binding.length,
                    binding=binding,
                    reason="dirty_source_error",
                )
            with self._lock:
                self._metrics.dirty_bypasses += 1
                self._metrics.bytes_served += len(data)
                self._metrics.source_fetches += fetches
                self._metrics.bytes_fetched += len(data)
            return ReadThroughResult(
                data=data,
                disposition=AdmissionDisposition.DIRTY_BYPASS,
                offset=binding.offset,
                length=binding.length,
                binding=binding,
                admitted=False,
                source_fetches=fetches,
                reason="dirty_scope",
            )

        if filler is None:
            with self._lock:
                self._metrics.safe_misses += 1
            return ReadThroughResult(
                data=b"",
                disposition=AdmissionDisposition.SAFE_MISS,
                offset=binding.offset,
                length=binding.length,
                binding=binding,
                reason="no_source",
            )

        try:
            result = self._coordinator.get_or_fill_result(
                binding, lambda: self._call_filler(filler, binding)
            )
        except Exception as exc:  # noqa: BLE001 — safe-miss boundary
            with self._lock:
                self._metrics.source_errors += 1
                self._metrics.safe_misses += 1
            return ReadThroughResult(
                data=b"",
                disposition=AdmissionDisposition.SAFE_MISS,
                offset=binding.offset,
                length=binding.length,
                binding=binding,
                reason=f"fill_error:{type(exc).__name__}",
            )

        return self._finalize_fill_result(binding, result)

    def _finalize_fill_result(
        self, binding: RangeBinding, result: CacheFillResult
    ) -> ReadThroughResult:
        if result.status is FillStatus.HIT:
            data = result.value or b""
            # Revalidate: coordinator hit skips our side-map; enforce now.
            with self._lock:
                if not self._value_ok_locked(binding, data):
                    self._remove_key_locked(binding.cache_key)
                    self._metrics.corrupt_entries += 1
                    self._metrics.safe_misses += 1
                    return ReadThroughResult(
                        data=b"",
                        disposition=AdmissionDisposition.SAFE_MISS,
                        offset=binding.offset,
                        length=binding.length,
                        binding=binding,
                        reason="corrupt_hit",
                    )
                # Record binding if missing (hit from pre-seeded ARC).
                self._bindings[binding.cache_key] = binding
                self._metrics.hits += 1
                self._metrics.bytes_served += len(data)
            return ReadThroughResult(
                data=data,
                disposition=AdmissionDisposition.HIT,
                offset=binding.offset,
                length=binding.length,
                binding=binding,
                from_cache=True,
            )

        if result.status is FillStatus.FILLED:
            data = result.value or b""
            with self._lock:
                # Race: scope became dirty during fill — drop admission.
                if self._is_dirty_locked(binding):
                    self._remove_key_locked(binding.cache_key)
                    self._metrics.dirty_admission_rejections += 1
                    self._metrics.dirty_bypasses += 1
                    self._metrics.bytes_served += len(data)
                    return ReadThroughResult(
                        data=data,
                        disposition=AdmissionDisposition.DIRTY_BYPASS,
                        offset=binding.offset,
                        length=binding.length,
                        binding=binding,
                        admitted=False,
                        source_fetches=1,
                        reason="dirty_during_fill",
                    )
                if not self._value_ok_locked(binding, data):
                    self._remove_key_locked(binding.cache_key)
                    self._metrics.corrupt_entries += 1
                    self._metrics.safe_misses += 1
                    return ReadThroughResult(
                        data=b"",
                        disposition=AdmissionDisposition.SAFE_MISS,
                        offset=binding.offset,
                        length=binding.length,
                        binding=binding,
                        reason="corrupt_fill",
                    )
                self._bindings[binding.cache_key] = binding
                self._metrics.fills += 1
                self._metrics.source_fetches += 1
                self._metrics.bytes_fetched += len(data)
                self._metrics.bytes_admitted += len(data)
                self._metrics.bytes_served += len(data)
                self._prune_bindings_locked()
            return ReadThroughResult(
                data=data,
                disposition=AdmissionDisposition.FILLED,
                offset=binding.offset,
                length=binding.length,
                binding=binding,
                admitted=True,
                source_fetches=1,
            )

        # FAILED / REJECTED / CANCELLED → safe miss (no poison).
        with self._lock:
            self._remove_key_locked(binding.cache_key)
            if result.status is FillStatus.FAILED:
                self._metrics.source_errors += 1
            self._metrics.safe_misses += 1
        return ReadThroughResult(
            data=b"",
            disposition=AdmissionDisposition.SAFE_MISS,
            offset=binding.offset,
            length=binding.length,
            binding=binding,
            reason=result.status.value,
        )

    # --- internal: bypass / segment ----------------------------------------

    def _read_bypass(
        self,
        *,
        identity_fields: dict[str, Any],
        filler: CommittedRangeSource | CommittedFiller | None,
        auth: Callable[[RangeBinding], bool] | None,
        cons: Callable[[RangeBinding], bool] | None,
    ) -> ReadThroughResult:
        off = identity_fields["offset"]
        length_i = identity_fields["length"]
        probe = RangeBinding(
            namespace=identity_fields["namespace"],
            content_id=identity_fields["content_id"],
            version=identity_fields["version"],
            generation=identity_fields["generation"],
            serializer=identity_fields["serializer"],
            offset=off,
            length=min(length_i, self._max_range_length),
            policy=identity_fields["policy"],
        )
        with self._lock:
            if not self._gates_pass_locked(probe, auth, cons, count=True):
                self._metrics.safe_misses += 1
                return ReadThroughResult(
                    data=b"",
                    disposition=AdmissionDisposition.REJECTED,
                    offset=off,
                    length=length_i,
                    reason="authorization_or_consistency",
                )
            if self._is_dirty_locked(probe):
                self._metrics.dirty_bypasses += 1
                dirty = True
            else:
                dirty = False
                self._metrics.bypasses += 1
                self._metrics.misses += 1

        try:
            data, fetches = self._fetch_unbounded(
                identity_fields, filler=filler, admit=False
            )
        except SourceFetchError:
            with self._lock:
                self._metrics.source_errors += 1
                self._metrics.safe_misses += 1
            return ReadThroughResult(
                data=b"",
                disposition=AdmissionDisposition.SAFE_MISS,
                offset=off,
                length=length_i,
                reason="source_error",
            )

        with self._lock:
            self._metrics.source_fetches += fetches
            self._metrics.bytes_fetched += len(data)
            self._metrics.bytes_served += len(data)
        return ReadThroughResult(
            data=data,
            disposition=(
                AdmissionDisposition.DIRTY_BYPASS
                if dirty
                else AdmissionDisposition.BYPASS
            ),
            offset=off,
            length=length_i,
            admitted=False,
            source_fetches=fetches,
            reason="oversized_bypass",
        )

    def _read_segmented(
        self,
        *,
        identity_fields: dict[str, Any],
        filler: CommittedRangeSource | CommittedFiller | None,
        auth: Callable[[RangeBinding], bool] | None,
        cons: Callable[[RangeBinding], bool] | None,
    ) -> ReadThroughResult:
        off = identity_fields["offset"]
        length_i = identity_fields["length"]
        segments = plan_bounded_segments(
            off, length_i, max_segment_bytes=self._segment_bytes
        )
        parts: list[bytes] = []
        total_fetches = 0
        any_admitted = False
        any_hit = False
        for segment in segments:
            binding = RangeBinding(
                namespace=identity_fields["namespace"],
                content_id=identity_fields["content_id"],
                version=identity_fields["version"],
                generation=identity_fields["generation"],
                serializer=identity_fields["serializer"],
                offset=segment.offset,
                length=segment.length,
                policy=identity_fields["policy"],
            )
            result = self._read_single(
                binding, filler=filler, auth=auth, cons=cons
            )
            if not result.ok:
                # Preserve authorization rejection; other failures collapse to a
                # safe miss so callers never observe partial segment data.
                disposition = (
                    result.disposition
                    if result.disposition is AdmissionDisposition.REJECTED
                    else AdmissionDisposition.SAFE_MISS
                )
                if disposition is AdmissionDisposition.SAFE_MISS:
                    with self._lock:
                        self._metrics.safe_misses += 1
                return ReadThroughResult(
                    data=b"",
                    disposition=disposition,
                    offset=off,
                    length=length_i,
                    source_fetches=total_fetches + result.source_fetches,
                    segments=len(segments),
                    reason=f"segment_{result.disposition.value}:{result.reason}",
                )
            parts.append(result.data)
            total_fetches += result.source_fetches
            any_admitted = any_admitted or result.admitted
            any_hit = any_hit or result.from_cache

        data = b"".join(parts)
        if len(data) != length_i:
            with self._lock:
                self._metrics.corrupt_entries += 1
                self._metrics.safe_misses += 1
            return ReadThroughResult(
                data=b"",
                disposition=AdmissionDisposition.SAFE_MISS,
                offset=off,
                length=length_i,
                source_fetches=total_fetches,
                segments=len(segments),
                reason="segment_length_mismatch",
            )
        with self._lock:
            self._metrics.segmented_reads += 1
            # bytes_served already counted per segment in _read_single; do not
            # double-count here.
        return ReadThroughResult(
            data=data,
            disposition=AdmissionDisposition.SEGMENTED,
            offset=off,
            length=length_i,
            admitted=any_admitted,
            source_fetches=total_fetches,
            segments=len(segments),
            from_cache=any_hit and total_fetches == 0,
            reason="oversized_segment",
        )

    # --- fetch helpers -----------------------------------------------------

    def _call_filler(
        self,
        filler: CommittedRangeSource | CommittedFiller,
        binding: RangeBinding,
    ) -> bytes:
        fetch_range = getattr(filler, "fetch_range", None)
        if callable(fetch_range):
            raw = fetch_range(binding)
        elif callable(filler):
            raw = filler(binding)  # type: ignore[operator]
        else:
            raise TypeError(
                "committed source must be callable or provide fetch_range"
            )
        if not isinstance(raw, (bytes, bytearray, memoryview)):
            raise TypeError("committed source must return bytes-like")
        data = bytes(raw)
        if len(data) != binding.length:
            raise RangeExtentError(
                f"source length {len(data)} disagrees with binding length "
                f"{binding.length}"
            )
        return data

    def _fetch_binding(
        self,
        binding: RangeBinding,
        filler: CommittedRangeSource | CommittedFiller | None,
        *,
        admit: bool,
    ) -> tuple[bytes, int]:
        if filler is None:
            raise SourceFetchError("no committed source configured")
        try:
            data = self._call_filler(filler, binding)
        except Exception as exc:  # noqa: BLE001
            raise SourceFetchError(cause=exc) from exc
        if admit:
            with self._lock:
                if not self._is_dirty_locked(binding):
                    if self._cache.put(binding.cache_key, data):
                        self._bindings[binding.cache_key] = binding
                        self._metrics.bytes_admitted += len(data)
                        self._prune_bindings_locked()
        return data, 1

    def _fetch_unbounded(
        self,
        identity_fields: dict[str, Any],
        *,
        filler: CommittedRangeSource | CommittedFiller | None,
        admit: bool,
    ) -> tuple[bytes, int]:
        """Fetch a possibly oversized range as consecutive admitable pieces.

        When ``admit`` is False (bypass / dirty), pieces are fetched but never
        put.  Pieces never extend past the requested end.
        """

        if filler is None:
            raise SourceFetchError("no committed source configured")
        off = identity_fields["offset"]
        length_i = identity_fields["length"]
        # For unbounded bypass, still only fetch the requested window, chunked
        # to the admitable ceiling so source APIs stay bounded.
        segments = plan_bounded_segments(
            off, length_i, max_segment_bytes=self._max_range_length
        )
        parts: list[bytes] = []
        fetches = 0
        for segment in segments:
            binding = RangeBinding(
                namespace=identity_fields["namespace"],
                content_id=identity_fields["content_id"],
                version=identity_fields["version"],
                generation=identity_fields["generation"],
                serializer=identity_fields["serializer"],
                offset=segment.offset,
                length=segment.length,
                policy=identity_fields["policy"],
            )
            data, n = self._fetch_binding(binding, filler, admit=admit)
            parts.append(data)
            fetches += n
        return b"".join(parts), fetches

    # --- revalidation / gates ----------------------------------------------

    def _revalidated_get_locked(self, binding: RangeBinding) -> bytes | None:
        """Return live bytes only when the exact binding revalidates.

        Caller must hold ``self._lock``.
        """

        key = binding.cache_key
        stored = self._bindings.get(key)
        if stored is not None and stored != binding:
            # Exact-binding mismatch under the same key is corrupt bookkeeping.
            self._remove_key_locked(key)
            self._metrics.corrupt_entries += 1
            self._metrics.safe_misses += 1
            return None
        value = self._cache.get(key)
        if value is None:
            self._bindings.pop(key, None)
            return None
        if not self._value_ok_locked(binding, value):
            self._remove_key_locked(key)
            self._metrics.corrupt_entries += 1
            self._metrics.safe_misses += 1
            return None
        if stored is None:
            self._bindings[key] = binding
        return value

    @staticmethod
    def _value_ok_locked(binding: RangeBinding, value: bytes) -> bool:
        if not isinstance(value, (bytes, bytearray, memoryview)):
            return False
        data = bytes(value)
        return len(data) == binding.length

    def _gates_pass_locked(
        self,
        binding: RangeBinding,
        authorize: Callable[[RangeBinding], bool] | None,
        consistent: Callable[[RangeBinding], bool] | None,
        *,
        count: bool,
    ) -> bool:
        if self._require_predicates:
            if authorize is None:
                if count:
                    self._metrics.authorization_rejections += 1
                return False
            if consistent is None:
                if count:
                    self._metrics.consistency_rejections += 1
                return False
        if authorize is not None and not self._approved(authorize, binding):
            if count:
                self._metrics.authorization_rejections += 1
            return False
        if consistent is not None and not self._approved(consistent, binding):
            if count:
                self._metrics.consistency_rejections += 1
            return False
        return True

    @staticmethod
    def _approved(
        predicate: Callable[[RangeBinding], bool], binding: RangeBinding
    ) -> bool:
        try:
            return bool(predicate(binding))
        except Exception:  # noqa: BLE001 — fail-closed
            return False

    def _resolve_authorize(
        self, override: Callable[[RangeBinding], bool] | None
    ) -> Callable[[RangeBinding], bool] | None:
        return override if override is not None else self._authorize

    def _resolve_consistent(
        self, override: Callable[[RangeBinding], bool] | None
    ) -> Callable[[RangeBinding], bool] | None:
        return override if override is not None else self._consistent

    # --- dirty / binding bookkeeping ---------------------------------------

    def _is_dirty_locked(self, binding: RangeBinding) -> bool:
        # Exact versioned scope.
        if (
            binding.namespace,
            binding.content_id,
            binding.version,
        ) in self._dirty:
            return True
        # Version-agnostic dirty mark.
        if (binding.namespace, binding.content_id, None) in self._dirty:
            return True
        return False

    def _evict_scope_locked(self, scope: DirtyScope) -> int:
        removed = 0
        for key, candidate in tuple(self._bindings.items()):
            if scope.matches(candidate):
                if self._remove_key_locked(key):
                    removed += 1
        return removed

    def _remove_key_locked(self, key: str) -> bool:
        removed = self._cache.delete(key)
        self._bindings.pop(key, None)
        return removed

    def _prune_bindings_locked(self) -> None:
        try:
            snap = self._cache.snapshot()
            live = set(snap.t1_keys) | set(snap.t2_keys)
        except Exception:  # noqa: BLE001
            return
        for key in tuple(self._bindings):
            if key not in live:
                self._bindings.pop(key, None)

    # --- identity resolution -----------------------------------------------

    @staticmethod
    def _coerce_binding(
        binding: RangeBinding | Mapping[str, Any],
    ) -> RangeBinding:
        if isinstance(binding, RangeBinding):
            return binding
        return RangeBinding.from_dict(binding)

    @staticmethod
    def _resolve_dirty_scope(
        *,
        namespace: str,
        content_id: str | None,
        inode: str | int | None,
        version: str | None,
        binding: RangeBinding | None,
    ) -> DirtyScope:
        if binding is not None:
            return DirtyScope(
                namespace=binding.namespace,
                content_id=binding.content_id,
                version=binding.version,
            )
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
        return DirtyScope(
            namespace=namespace, content_id=content_id, version=version
        )

    def _resolve_identity(
        self,
        *,
        binding: RangeBinding | Mapping[str, Any] | None,
        namespace: str,
        content_id: str | None,
        inode: str | int | None,
        version: str | None,
        generation: str,
        serializer: str,
        policy: str,
        offset: int,
        length: int | None,
    ) -> dict[str, Any]:
        if binding is not None:
            identity = self._coerce_binding(binding)
            if length is not None and length != identity.length:
                raise RangeExtentError(
                    "length disagrees with supplied binding.length"
                )
            if offset not in (0, identity.offset) and offset != identity.offset:
                raise RangeExtentError(
                    "offset disagrees with supplied binding.offset"
                )
            return {
                "namespace": identity.namespace,
                "content_id": identity.content_id,
                "version": identity.version,
                "generation": identity.generation,
                "serializer": identity.serializer,
                "policy": identity.policy,
                "offset": identity.offset,
                "length": identity.length,
            }
        if length is None:
            raise RangeExtentError("length is required without a binding")
        if content_id is not None and inode is not None:
            raise RangeIdentityError("pass content_id or inode, not both")
        if content_id is None and inode is None:
            raise RangeIdentityError("content_id or inode is required")
        if version is None:
            raise RangeIdentityError("version is required without a binding")
        if content_id is None:
            if isinstance(inode, bool) or not isinstance(inode, (str, int)):
                raise RangeIdentityError(
                    f"inode must be str or int, got {type(inode).__name__}"
                )
            content_id = str(inode)
        off = validate_offset(offset)
        length_i = require_bounded_int(
            length, name="length", minimum=1, maximum=MAX_SAFE_INTEGER
        )
        return {
            "namespace": namespace,
            "content_id": content_id,
            "version": version,
            "generation": generation,
            "serializer": serializer,
            "policy": policy,
            "offset": off,
            "length": length_i,
        }

    def assert_invariants(self) -> None:
        """Assert ARC core invariants plus local binding-map hygiene."""

        self._cache.assert_invariants()
        with self._lock:
            for key, binding in self._bindings.items():
                assert key == binding.cache_key
                if self._cache.contains(key):
                    value = self._cache.get(key)
                    if value is not None:
                        assert len(value) == binding.length


# Public aliases matching plan vocabulary.
CommittedReadThrough = CachedStorage
BoundedRangeAdmission = CachedStorage
CommittedCachedStorage = CachedStorage


__all__ = [
    "TASK_ID",
    "CONTRACT_VERSION",
    "SCHEMA_VERSION",
    "SCHEMA_MAJOR",
    "CACHED_STORAGE_SCHEMA",
    "COMMITTED_READ_THROUGH_SCHEMA",
    "BOUNDED_RANGE_ADMISSION_SCHEMA",
    "READ_THROUGH_RESULT_SCHEMA",
    "ADMISSION_METRICS_SCHEMA",
    "CachedStorage_V1",
    "CommittedReadThrough_V1",
    "BoundedRangeAdmission_V1",
    "DEFAULT_SEGMENT_BYTES",
    "DEFAULT_CAPACITY_BYTES",
    "DEFAULT_MAX_READ_BYTES",
    "MAX_DIRTY_SCOPES",
    "MAX_SEGMENTS_PER_READ",
    "MAX_RANGE_LENGTH",
    "CachedStorageError",
    "AdmissionRejected",
    "DirtyAdmissionError",
    "SourceFetchError",
    "CorruptCacheEntryError",
    "OversizedRangeError",
    "AdmissionDisposition",
    "OversizedRangeMode",
    "AdmissionMetrics",
    "ReadThroughResult",
    "RangeSegment",
    "CommittedRangeSource",
    "CommittedFiller",
    "plan_bounded_segments",
    "is_admitable_length",
    "DirtyScope",
    "CachedStorage",
    "CommittedReadThrough",
    "BoundedRangeAdmission",
    "CommittedCachedStorage",
    # Re-exports for call-site convenience.
    "RangeBinding",
    "FillStatus",
    "CacheFillResult",
    "CacheFillError",
    "CacheFillCancelled",
    "CacheFillRejected",
    "RangeLookupDisposition",
    "RangeMatchPolicy",
]
