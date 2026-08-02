"""Bounded, deterministic vector indexes for GraphRAG projections.

The index is deliberately a projection: vectors make documents easier to
*find*, but they never establish document truth, semantic meaning, or an
authorization decision.  Callers must obtain those from the authoritative
GraphRAG records and policy layer after retrieval.

No ML or native ANN dependency is imported here.  ``ANNVectorIndex`` accepts a
small backend protocol so deployments can provide one explicitly, while the
default backend is an exact, deterministic compatibility backend.  The exact
index is also the reference implementation used for recall measurements and
bounded fallback.
"""

from __future__ import annotations

import math
import time
from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Protocol, runtime_checkable


MAX_VECTOR_DIMENSION = 1_048_576
DEFAULT_MAX_RECORDS = 100_000
DEFAULT_MAX_QUERY_K = 1_000
DEFAULT_P95_FLOOR_SECONDS = 0.000_001


class VectorIndexError(ValueError):
    """Base error for closed vector-index operations."""


class VectorIdentityMismatchError(VectorIndexError):
    """A record or query does not belong to this pinned index."""


class VectorValidationError(VectorIndexError):
    """A vector, filter, or index bound is malformed."""


class ExactFallbackLimitError(VectorIndexError):
    """An exact scan would exceed the caller's explicit candidate budget."""


def _identifier(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.encode("utf-8")) > 512:
        raise VectorValidationError(f"{name} must be a non-empty bounded string")
    return value.strip()


def _metric(value: Any) -> str:
    value = getattr(value, "value", value)
    if not isinstance(value, str):
        raise VectorValidationError("metric must be cosine, dot_product, or euclidean")
    value = value.lower().strip()
    if value not in {"cosine", "dot_product", "euclidean"}:
        raise VectorValidationError("metric must be cosine, dot_product, or euclidean")
    return value


def _bounded_positive(value: Any, name: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise VectorValidationError(f"{name} must be an integer in range")
    return value


def _finite_vector(value: Any, dimension: int | None = None) -> tuple[float, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise VectorValidationError("vector must be a finite numeric sequence")
    if not value or len(value) > MAX_VECTOR_DIMENSION:
        raise VectorValidationError("vector dimension is outside the supported range")
    result: list[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise VectorValidationError("vector values must be finite numbers")
        item = float(item)
        if not math.isfinite(item):
            raise VectorValidationError("vector values must be finite numbers")
        result.append(item)
    if dimension is not None and len(result) != dimension:
        raise VectorIdentityMismatchError("vector dimension differs from index identity")
    return tuple(result)


def _freeze_value(value: Any) -> Any:
    """Make metadata inert, finite, and stable for deterministic filtering."""

    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise VectorValidationError("metadata cannot contain non-finite floats")
        return value
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise VectorValidationError("metadata keys must be strings")
        return MappingProxyType({key: _freeze_value(value[key]) for key in sorted(value)})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze_value(item) for item in value)
    raise VectorValidationError("metadata must be inert JSON-like data")


def _freeze_metadata(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if value is None:
        return MappingProxyType({})
    if not isinstance(value, Mapping):
        raise VectorValidationError("metadata must be a mapping")
    frozen = _freeze_value(value)
    assert isinstance(frozen, Mapping)
    return frozen


def _matches_filters(metadata: Mapping[str, Any], filters: Mapping[str, Any] | None) -> bool:
    if filters is None:
        return True
    frozen = _freeze_metadata(filters)
    return all(metadata.get(key, object()) == value for key, value in frozen.items())


@dataclass(frozen=True)
class VectorIndexIdentity:
    """All identity fields that must agree before vectors may be compared."""

    index_id: str
    model_id: str
    tokenizer_id: str
    dimension: int
    metric: str
    source_id: str = "unspecified-source"
    source_version: str = "unspecified-version"
    schema_version: str = "vector-index@1"

    def __post_init__(self) -> None:
        for name in ("index_id", "model_id", "tokenizer_id", "source_id", "source_version", "schema_version"):
            object.__setattr__(self, name, _identifier(getattr(self, name), name))
        object.__setattr__(self, "dimension", _bounded_positive(self.dimension, "dimension", MAX_VECTOR_DIMENSION))
        object.__setattr__(self, "metric", _metric(self.metric))

    @classmethod
    def from_manifest(cls, manifest: Any) -> "VectorIndexIdentity":
        """Create an identity from a closed ``GraphRAGIndexManifest``-like value."""

        try:
            return cls(
                index_id=manifest.index_id,
                model_id=manifest.model_id,
                tokenizer_id=manifest.tokenizer_id,
                dimension=manifest.dimension,
                metric=manifest.metric,
                source_id=manifest.source_id,
                source_version=manifest.source_version,
            )
        except AttributeError as exc:
            raise VectorValidationError("manifest does not expose GraphRAG index identity fields") from exc

    def assert_matches(self, other: "VectorIndexIdentity") -> None:
        if not isinstance(other, VectorIndexIdentity) or self != other:
            raise VectorIdentityMismatchError("index/model/tokenizer/dimension/metric/source identity differs")


@dataclass(frozen=True)
class VectorRecord:
    """A single projection record.  ``identity`` is checked on insertion."""

    record_id: str
    vector: Sequence[float]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    identity: VectorIndexIdentity | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "record_id", _identifier(self.record_id, "record_id"))
        object.__setattr__(self, "vector", _finite_vector(self.vector))
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))
        if self.identity is not None and not isinstance(self.identity, VectorIndexIdentity):
            raise VectorValidationError("record identity must be VectorIndexIdentity")


@dataclass(frozen=True)
class VectorSearchResult:
    record_id: str
    score: float
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "record_id", _identifier(self.record_id, "record_id"))
        if isinstance(self.score, bool) or not isinstance(self.score, (int, float)) or not math.isfinite(self.score):
            raise VectorValidationError("search score must be finite")
        object.__setattr__(self, "score", float(self.score))
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))


@dataclass(frozen=True)
class VectorIndexSnapshot:
    identity: VectorIndexIdentity
    records: tuple[VectorRecord, ...]


@dataclass(frozen=True)
class ANNRecallBenchmark:
    """A reproducible recall result, including an explicit p95 timing floor."""

    recall_at_k: float
    query_p95_seconds: float
    p95_floor_seconds: float
    query_count: int
    k: int

    def __post_init__(self) -> None:
        for name in ("recall_at_k", "query_p95_seconds", "p95_floor_seconds"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise VectorValidationError(f"{name} must be finite and non-negative")
            object.__setattr__(self, name, float(value))
        if self.recall_at_k > 1:
            raise VectorValidationError("recall_at_k cannot exceed one")
        if self.query_p95_seconds < self.p95_floor_seconds:
            raise VectorValidationError("query p95 must retain its declared floor")
        object.__setattr__(self, "query_count", _bounded_positive(self.query_count, "query_count", DEFAULT_MAX_RECORDS))
        object.__setattr__(self, "k", _bounded_positive(self.k, "k", DEFAULT_MAX_QUERY_K))


@runtime_checkable
class ANNBackend(Protocol):
    """Minimal, deployment-supplied ANN backend protocol.

    The backend returns candidate record ids only.  The wrapper validates every
    id, reapplies filters, and recomputes scores, so backend ordering or scores
    cannot influence deterministic public results.
    """

    def rebuild(self, records: Sequence[VectorRecord], identity: VectorIndexIdentity) -> None: ...

    def search(
        self, query: Sequence[float], limit: int, filters: Mapping[str, Any] | None = None
    ) -> Sequence[str | VectorSearchResult]: ...


class VectorIndex(ABC):
    """Versioned VectorIndex@1 interface."""

    identity: VectorIndexIdentity

    @abstractmethod
    def add(self, record: VectorRecord, *, identity: VectorIndexIdentity | None = None) -> None: ...

    @abstractmethod
    def update(self, record: VectorRecord, *, identity: VectorIndexIdentity | None = None) -> None: ...

    @abstractmethod
    def delete(self, record_id: str, *, identity: VectorIndexIdentity | None = None) -> None: ...

    @abstractmethod
    def rebuild(self, records: Iterable[VectorRecord], *, identity: VectorIndexIdentity | None = None) -> None: ...

    @abstractmethod
    def search(
        self, query: Sequence[float], k: int = 10, *, filters: Mapping[str, Any] | None = None,
        identity: VectorIndexIdentity | None = None,
    ) -> tuple[VectorSearchResult, ...]: ...


class ExactVectorIndex(VectorIndex):
    """Deterministic exact baseline with atomic add/update/delete/rebuild."""

    def __init__(
        self, identity: VectorIndexIdentity, *, max_records: int = DEFAULT_MAX_RECORDS,
        max_query_k: int = DEFAULT_MAX_QUERY_K,
    ) -> None:
        if not isinstance(identity, VectorIndexIdentity):
            raise VectorValidationError("identity must be VectorIndexIdentity")
        self.identity = identity
        self.max_records = _bounded_positive(max_records, "max_records", DEFAULT_MAX_RECORDS)
        self.max_query_k = _bounded_positive(max_query_k, "max_query_k", DEFAULT_MAX_QUERY_K)
        self._records: dict[str, VectorRecord] = {}

    @property
    def count(self) -> int:
        return len(self._records)

    def snapshot(self) -> VectorIndexSnapshot:
        return VectorIndexSnapshot(self.identity, tuple(self._records[key] for key in sorted(self._records)))

    def _assert_identity(self, identity: VectorIndexIdentity | None) -> None:
        if identity is not None:
            self.identity.assert_matches(identity)

    def _validate_record(self, record: VectorRecord, identity: VectorIndexIdentity | None) -> VectorRecord:
        if not isinstance(record, VectorRecord):
            raise VectorValidationError("record must be VectorRecord")
        self._assert_identity(identity)
        if record.identity is not None:
            self.identity.assert_matches(record.identity)
        _finite_vector(record.vector, self.identity.dimension)
        return record

    def _publish(self, records: dict[str, VectorRecord]) -> None:
        """Hook for ANN subclasses; publishing happens only after validation."""

        self._records = records

    def add(self, record: VectorRecord, *, identity: VectorIndexIdentity | None = None) -> None:
        record = self._validate_record(record, identity)
        if record.record_id in self._records:
            raise VectorIndexError("record already exists; use update")
        if len(self._records) >= self.max_records:
            raise VectorIndexError("index record bound exceeded")
        staged = dict(self._records)
        staged[record.record_id] = record
        self._publish(staged)

    def update(self, record: VectorRecord, *, identity: VectorIndexIdentity | None = None) -> None:
        record = self._validate_record(record, identity)
        if record.record_id not in self._records:
            raise VectorIndexError("cannot update a missing record")
        staged = dict(self._records)
        staged[record.record_id] = record
        self._publish(staged)

    def upsert(self, record: VectorRecord, *, identity: VectorIndexIdentity | None = None) -> None:
        if record.record_id in self._records:
            self.update(record, identity=identity)
        else:
            self.add(record, identity=identity)

    def delete(self, record_id: str, *, identity: VectorIndexIdentity | None = None) -> None:
        self._assert_identity(identity)
        record_id = _identifier(record_id, "record_id")
        if record_id not in self._records:
            raise VectorIndexError("cannot delete a missing record")
        staged = dict(self._records)
        del staged[record_id]
        self._publish(staged)

    def rebuild(self, records: Iterable[VectorRecord], *, identity: VectorIndexIdentity | None = None) -> None:
        self._assert_identity(identity)
        if isinstance(records, (str, bytes)) or not isinstance(records, Iterable):
            raise VectorValidationError("records must be an iterable of VectorRecord")
        staged: dict[str, VectorRecord] = {}
        for record in records:
            record = self._validate_record(record, identity)
            if record.record_id in staged:
                raise VectorIndexError("rebuild records must have unique ids")
            if len(staged) >= self.max_records:
                raise VectorIndexError("index record bound exceeded")
            staged[record.record_id] = record
        self._publish(staged)

    def _validate_query(
        self, query: Sequence[float], k: int, filters: Mapping[str, Any] | None,
        identity: VectorIndexIdentity | None,
    ) -> tuple[tuple[float, ...], int, Mapping[str, Any] | None]:
        self._assert_identity(identity)
        query = _finite_vector(query, self.identity.dimension)
        k = _bounded_positive(k, "k", self.max_query_k)
        if filters is not None:
            filters = _freeze_metadata(filters)
        return query, k, filters

    def _score(self, query: Sequence[float], vector: Sequence[float]) -> float:
        if self.identity.metric == "dot_product":
            return math.fsum(left * right for left, right in zip(query, vector))
        if self.identity.metric == "euclidean":
            return -math.sqrt(math.fsum((left - right) ** 2 for left, right in zip(query, vector)))
        numerator = math.fsum(left * right for left, right in zip(query, vector))
        query_norm = math.sqrt(math.fsum(item * item for item in query))
        vector_norm = math.sqrt(math.fsum(item * item for item in vector))
        return 0.0 if query_norm == 0.0 or vector_norm == 0.0 else numerator / (query_norm * vector_norm)

    def _exact_results(
        self, query: Sequence[float], k: int, filters: Mapping[str, Any] | None,
        candidates: Iterable[str] | None = None,
    ) -> tuple[VectorSearchResult, ...]:
        ids = sorted(self._records) if candidates is None else sorted(set(candidates))
        results = [
            VectorSearchResult(record_id, self._score(query, self._records[record_id].vector), self._records[record_id].metadata)
            for record_id in ids
            if record_id in self._records and _matches_filters(self._records[record_id].metadata, filters)
        ]
        return tuple(sorted(results, key=lambda value: (-value.score, value.record_id))[:k])

    def exact_search(
        self, query: Sequence[float], k: int = 10, *, filters: Mapping[str, Any] | None = None,
        identity: VectorIndexIdentity | None = None, max_candidates: int | None = None,
    ) -> tuple[VectorSearchResult, ...]:
        query, k, filters = self._validate_query(query, k, filters, identity)
        candidate_count = sum(_matches_filters(record.metadata, filters) for record in self._records.values())
        if max_candidates is not None:
            max_candidates = _bounded_positive(max_candidates, "max_candidates", self.max_records)
            if candidate_count > max_candidates:
                raise ExactFallbackLimitError(
                    f"exact candidate count {candidate_count} exceeds explicit limit {max_candidates}"
                )
        return self._exact_results(query, k, filters)

    def search(
        self, query: Sequence[float], k: int = 10, *, filters: Mapping[str, Any] | None = None,
        identity: VectorIndexIdentity | None = None,
    ) -> tuple[VectorSearchResult, ...]:
        return self.exact_search(query, k, filters=filters, identity=identity)

    query = search


class _ExactANNBackend:
    """Portable default backend that preserves the ANN boundary without a dependency."""

    def __init__(self) -> None:
        self._records: dict[str, VectorRecord] = {}
        self._identity: VectorIndexIdentity | None = None

    def rebuild(self, records: Sequence[VectorRecord], identity: VectorIndexIdentity) -> None:
        self._records = {record.record_id: record for record in records}
        self._identity = identity

    def search(
        self, query: Sequence[float], limit: int, filters: Mapping[str, Any] | None = None
    ) -> Sequence[str]:
        if self._identity is None:
            return ()
        # Candidate ordering is intentionally not trusted by ANNVectorIndex.
        baseline = ExactVectorIndex(self._identity, max_records=max(1, len(self._records)))
        baseline.rebuild(self._records.values())
        return tuple(result.record_id for result in baseline.search(query, limit, filters=filters))


class ANNVectorIndex(ExactVectorIndex):
    """ANN projection with an injected backend and deterministic re-scoring.

    ``candidate_multiplier`` and ``max_ann_candidates`` bound backend work.
    Backends never receive authority to add records or decide a final order.
    """

    def __init__(
        self, identity: VectorIndexIdentity, *, backend: ANNBackend | None = None,
        candidate_multiplier: int = 4, max_ann_candidates: int = DEFAULT_MAX_QUERY_K,
        max_records: int = DEFAULT_MAX_RECORDS, max_query_k: int = DEFAULT_MAX_QUERY_K,
    ) -> None:
        super().__init__(identity, max_records=max_records, max_query_k=max_query_k)
        self.candidate_multiplier = _bounded_positive(candidate_multiplier, "candidate_multiplier", DEFAULT_MAX_QUERY_K)
        self.max_ann_candidates = _bounded_positive(max_ann_candidates, "max_ann_candidates", self.max_records)
        if backend is not None and not isinstance(backend, ANNBackend):
            raise VectorValidationError("backend must implement ANNBackend@1")
        self.backend: ANNBackend = backend if backend is not None else _ExactANNBackend()
        self.backend.rebuild((), self.identity)

    def _publish(self, records: dict[str, VectorRecord]) -> None:
        ordered = tuple(records[key] for key in sorted(records))
        # Build backend first; a backend failure leaves the prior projection intact.
        self.backend.rebuild(ordered, self.identity)
        self._records = records

    def search(
        self, query: Sequence[float], k: int = 10, *, filters: Mapping[str, Any] | None = None,
        identity: VectorIndexIdentity | None = None,
    ) -> tuple[VectorSearchResult, ...]:
        query, k, filters = self._validate_query(query, k, filters, identity)
        limit = min(self.max_ann_candidates, max(k, k * self.candidate_multiplier))
        raw = self.backend.search(query, limit, filters)
        if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
            raise VectorIndexError("ANN backend returned a non-sequence candidate response")
        ids: list[str] = []
        for candidate in raw[:limit]:
            record_id = candidate.record_id if isinstance(candidate, VectorSearchResult) else candidate
            if not isinstance(record_id, str):
                raise VectorIndexError("ANN backend returned a non-string candidate id")
            if record_id in self._records:
                ids.append(record_id)
        return self._exact_results(query, k, filters, ids)


# A descriptive alias for callers that prefer the task's terminology.
PluggableANNIndex = ANNVectorIndex


def benchmark_ann_recall(
    ann_index: VectorIndex, exact_index: ExactVectorIndex, queries: Iterable[Sequence[float]], *, k: int = 10,
    filters: Mapping[str, Any] | None = None, p95_floor_seconds: float = DEFAULT_P95_FLOOR_SECONDS,
) -> ANNRecallBenchmark:
    """Compare an ANN projection against a pinned exact baseline.

    The result records a non-zero timing floor so very fast clocks do not
    silently report a misleading zero p95.  This is measurement metadata, not
    an availability SLO.
    """

    if not isinstance(ann_index, VectorIndex) or not isinstance(exact_index, ExactVectorIndex):
        raise VectorValidationError("benchmark requires VectorIndex and ExactVectorIndex")
    ann_index.identity.assert_matches(exact_index.identity)
    k = _bounded_positive(k, "k", min(ann_index.max_query_k, exact_index.max_query_k))
    if isinstance(p95_floor_seconds, bool) or not isinstance(p95_floor_seconds, (int, float)) or not math.isfinite(p95_floor_seconds) or p95_floor_seconds < 0:
        raise VectorValidationError("p95_floor_seconds must be finite and non-negative")
    query_values = tuple(queries)
    if not query_values or len(query_values) > DEFAULT_MAX_RECORDS:
        raise VectorValidationError("queries must be a non-empty bounded iterable")
    recalls: list[float] = []
    durations: list[float] = []
    for query in query_values:
        exact = exact_index.search(query, k, filters=filters, identity=ann_index.identity)
        started = time.perf_counter()
        approximate = ann_index.search(query, k, filters=filters, identity=exact_index.identity)
        durations.append(time.perf_counter() - started)
        expected = {result.record_id for result in exact}
        received = {result.record_id for result in approximate}
        recalls.append(1.0 if not expected else len(expected & received) / len(expected))
    durations.sort()
    p95 = durations[max(0, math.ceil(len(durations) * 0.95) - 1)]
    floor = float(p95_floor_seconds)
    return ANNRecallBenchmark(sum(recalls) / len(recalls), max(p95, floor), floor, len(query_values), k)
