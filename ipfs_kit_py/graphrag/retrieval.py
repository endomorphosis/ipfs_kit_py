"""Deterministic, advisory-only hybrid retrieval for GraphRAG projections.

This module ranks already indexed candidates.  It intentionally does not
resolve entity meaning, validate evidence, read policy, or grant access.  A
consumer must perform semantic and authorization checks against the
authoritative content and policy layers after receiving these advisory results.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from .vector_index import (
    ExactFallbackLimitError,
    VectorIndex,
    VectorIndexError,
    VectorIndexIdentity,
    VectorSearchResult,
    _freeze_metadata,
    _identifier,
    _matches_filters,
)


MAX_TEXT_QUERY_CHARS = 4_096
DEFAULT_MAX_RESULTS = 1_000
DEFAULT_EXACT_FALLBACK_CANDIDATES = 512


class HybridRetrievalError(ValueError):
    """A bounded HybridRetriever@1 operation could not be performed."""


def _weight(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HybridRetrievalError(f"{name} must be a finite non-negative number")
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise HybridRetrievalError(f"{name} must be a finite non-negative number")
    return value


def _bounded(value: Any, name: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise HybridRetrievalError(f"{name} must be an integer in range")
    return value


@dataclass(frozen=True)
class HybridWeights:
    """Finite, non-negative weights normalized at the boundary."""

    vector: float = 0.5
    lexical: float = 0.5

    def __post_init__(self) -> None:
        vector = _weight(self.vector, "vector weight")
        lexical = _weight(self.lexical, "lexical weight")
        total = vector + lexical
        if total == 0:
            raise HybridRetrievalError("at least one hybrid weight must be positive")
        object.__setattr__(self, "vector", vector / total)
        object.__setattr__(self, "lexical", lexical / total)


@dataclass(frozen=True)
class LexicalSearchResult:
    document_id: str
    score: float
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "document_id", _identifier(self.document_id, "document_id"))
        if isinstance(self.score, bool) or not isinstance(self.score, (int, float)) or not math.isfinite(self.score):
            raise HybridRetrievalError("lexical score must be finite")
        object.__setattr__(self, "score", float(self.score))
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))


@dataclass(frozen=True)
class HybridSearchResult:
    document_id: str
    score: float
    vector_score: float | None
    lexical_score: float | None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    authoritative: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "document_id", _identifier(self.document_id, "document_id"))
        for name in ("score", "vector_score", "lexical_score"):
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)):
                raise HybridRetrievalError(f"{name} must be finite when present")
            if value is not None:
                object.__setattr__(self, name, float(value))
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))
        if self.authoritative is not False:
            raise HybridRetrievalError("retrieval results are always advisory, never authoritative")


@dataclass(frozen=True)
class HybridSearchResponse:
    results: tuple[HybridSearchResult, ...]
    weights: HybridWeights
    exact_fallback_used: bool
    exact_fallback_reason: str
    exact_fallback_limit: int
    authoritative: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.weights, HybridWeights):
            raise HybridRetrievalError("weights must be HybridWeights")
        object.__setattr__(self, "results", tuple(self.results))
        if any(not isinstance(result, HybridSearchResult) for result in self.results):
            raise HybridRetrievalError("results must be HybridSearchResult values")
        object.__setattr__(self, "exact_fallback_reason", str(self.exact_fallback_reason))
        object.__setattr__(self, "exact_fallback_limit", _bounded(self.exact_fallback_limit, "exact_fallback_limit", DEFAULT_MAX_RESULTS))
        if self.authoritative is not False:
            raise HybridRetrievalError("retrieval responses are always advisory, never authoritative")


def _normalized_scores(values: Mapping[str, float]) -> dict[str, float]:
    """Normalize one source deterministically without changing source ranks."""

    if not values:
        return {}
    lower, upper = min(values.values()), max(values.values())
    if lower == upper:
        return {key: 1.0 for key in values}
    return {key: (score - lower) / (upper - lower) for key, score in values.items()}


def _document_id(result: VectorSearchResult) -> str:
    value = result.metadata.get("document_id", result.record_id)
    return _identifier(value, "document_id") if isinstance(value, str) else result.record_id


def _metadata_key(value: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
    """Give duplicate lexical candidates a stable tie-break without ordering data."""

    return tuple((key, repr(value[key])) for key in sorted(value))


class HybridRetriever:
    """Merge vector and lexical candidates with deterministic, bounded ranking.

    ``lexical_search`` is a candidate provider with signature
    ``(text_query, limit, filters) -> Sequence[LexicalSearchResult | Mapping]``.
    Its output is validated and filters are re-applied locally; provider order
    cannot become a tie-breaker.
    """

    def __init__(
        self, vector_index: VectorIndex, lexical_search: Callable[[str, int, Mapping[str, Any] | None], Sequence[Any]] | None = None,
        *, max_results: int = DEFAULT_MAX_RESULTS, max_exact_fallback_candidates: int = DEFAULT_EXACT_FALLBACK_CANDIDATES,
        default_weights: HybridWeights | None = None,
    ) -> None:
        if not isinstance(vector_index, VectorIndex):
            raise HybridRetrievalError("vector_index must implement VectorIndex@1")
        if lexical_search is not None and not callable(lexical_search):
            raise HybridRetrievalError("lexical_search must be callable")
        self.vector_index = vector_index
        self.lexical_search = lexical_search
        self.max_results = _bounded(max_results, "max_results", DEFAULT_MAX_RESULTS)
        self.max_exact_fallback_candidates = _bounded(
            max_exact_fallback_candidates, "max_exact_fallback_candidates", DEFAULT_MAX_RESULTS
        )
        self.default_weights = default_weights if default_weights is not None else HybridWeights()
        if not isinstance(self.default_weights, HybridWeights):
            raise HybridRetrievalError("default_weights must be HybridWeights")

    def _weights(self, vector: float | None, lexical: float | None) -> HybridWeights:
        if vector is None and lexical is None:
            return self.default_weights
        return HybridWeights(
            self.default_weights.vector if vector is None else vector,
            self.default_weights.lexical if lexical is None else lexical,
        )

    @staticmethod
    def _coerce_lexical(value: Any) -> LexicalSearchResult:
        if isinstance(value, LexicalSearchResult):
            return value
        if isinstance(value, Mapping):
            try:
                return LexicalSearchResult(value["document_id"], value["score"], value.get("metadata", {}))
            except KeyError as exc:
                raise HybridRetrievalError("lexical mapping requires document_id and score") from exc
        if isinstance(value, tuple) and len(value) in (2, 3):
            return LexicalSearchResult(value[0], value[1], {} if len(value) == 2 else value[2])
        raise HybridRetrievalError("lexical result has an unsupported shape")

    def _lexical_results(
        self, text_query: str, k: int, filters: Mapping[str, Any] | None,
    ) -> tuple[LexicalSearchResult, ...]:
        if not text_query or self.lexical_search is None:
            return ()
        provided = self.lexical_search(text_query, k, filters)
        if isinstance(provided, (str, bytes)) or not isinstance(provided, Sequence):
            raise HybridRetrievalError("lexical_search must return a sequence")
        values = [self._coerce_lexical(item) for item in provided[:k]]
        # One score per document, selected deterministically irrespective of provider order.
        best: dict[str, LexicalSearchResult] = {}
        for value in values:
            if not _matches_filters(value.metadata, filters):
                continue
            current = best.get(value.document_id)
            if current is None or value.score > current.score or (
                value.score == current.score and _metadata_key(value.metadata) < _metadata_key(current.metadata)
            ):
                best[value.document_id] = value
        return tuple(best[key] for key in sorted(best))

    def search(
        self, query_vector: Sequence[float], text_query: str = "", k: int = 10, *,
        filters: Mapping[str, Any] | None = None, identity: VectorIndexIdentity | None = None,
        vector_weight: float | None = None, lexical_weight: float | None = None,
        allow_exact_fallback: bool = False,
    ) -> HybridSearchResponse:
        k = _bounded(k, "k", min(self.max_results, self.vector_index.max_query_k))
        if not isinstance(text_query, str) or len(text_query) > MAX_TEXT_QUERY_CHARS:
            raise HybridRetrievalError("text_query must be a bounded string")
        if filters is not None:
            filters = _freeze_metadata(filters)
        weights = self._weights(vector_weight, lexical_weight)
        vector_results = self.vector_index.search(query_vector, k, filters=filters, identity=identity)
        fallback_used = False
        fallback_reason = "not_requested"
        if allow_exact_fallback and len(vector_results) < k:
            exact_search = getattr(self.vector_index, "exact_search", None)
            if not callable(exact_search):
                fallback_reason = "unavailable"
            elif self.vector_index.count > self.max_exact_fallback_candidates:
                fallback_reason = "candidate_limit_exceeded"
            else:
                try:
                    vector_results = exact_search(
                        query_vector, k, filters=filters, identity=identity,
                        max_candidates=self.max_exact_fallback_candidates,
                    )
                    fallback_used = True
                    fallback_reason = "used"
                except ExactFallbackLimitError:
                    fallback_reason = "candidate_limit_exceeded"
                except VectorIndexError as exc:
                    raise HybridRetrievalError("exact fallback rejected the bounded query") from exc
        lexical_results = self._lexical_results(text_query, k, filters)

        vectors: dict[str, VectorSearchResult] = {}
        for value in vector_results:
            document_id = _document_id(value)
            current = vectors.get(document_id)
            if current is None or value.score > current.score or (value.score == current.score and value.record_id < current.record_id):
                vectors[document_id] = value
        lexical = {value.document_id: value for value in lexical_results}
        vector_normalized = _normalized_scores({key: value.score for key, value in vectors.items()})
        lexical_normalized = _normalized_scores({key: value.score for key, value in lexical.items()})
        output: list[HybridSearchResult] = []
        for document_id in sorted(set(vectors) | set(lexical)):
            vector_value = vectors.get(document_id)
            lexical_value = lexical.get(document_id)
            score = (
                weights.vector * vector_normalized.get(document_id, 0.0)
                + weights.lexical * lexical_normalized.get(document_id, 0.0)
            )
            metadata = vector_value.metadata if vector_value is not None else lexical_value.metadata
            output.append(HybridSearchResult(
                document_id, score,
                None if vector_value is None else vector_value.score,
                None if lexical_value is None else lexical_value.score,
                metadata,
            ))
        output.sort(key=lambda value: (-value.score, value.document_id))
        return HybridSearchResponse(
            tuple(output[:k]), weights, fallback_used, fallback_reason,
            self.max_exact_fallback_candidates,
        )

    retrieve = search
