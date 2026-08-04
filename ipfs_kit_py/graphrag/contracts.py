"""Closed, inert GraphRAG contracts.

This module deliberately contains data contracts only.  In particular it does
not discover providers, import ML libraries, or construct models.  The records
below are the sole on-disk interchange language used by :mod:`.storage`.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar, Final


CONTRACT_VERSION: Final[int] = 1
SCHEMA_MAJOR: Final[int] = 1
SCHEMA_VERSION: Final[str] = "1.0.0"
GRAPHRAG_CONTRACT_NAMESPACE: Final[str] = "ipfs_kit_py/graphrag"

GRAPHRAG_PROVENANCE_SCHEMA: Final[str] = f"{GRAPHRAG_CONTRACT_NAMESPACE}/provenance@{SCHEMA_MAJOR}"
GRAPHRAG_CONTENT_SCHEMA: Final[str] = f"{GRAPHRAG_CONTRACT_NAMESPACE}/content@{SCHEMA_MAJOR}"
GRAPHRAG_RELATION_SCHEMA: Final[str] = f"{GRAPHRAG_CONTRACT_NAMESPACE}/relation@{SCHEMA_MAJOR}"
GRAPHRAG_EMBEDDING_SCHEMA: Final[str] = f"{GRAPHRAG_CONTRACT_NAMESPACE}/embedding@{SCHEMA_MAJOR}"
GRAPHRAG_INDEX_MANIFEST_SCHEMA: Final[str] = f"{GRAPHRAG_CONTRACT_NAMESPACE}/index-manifest@{SCHEMA_MAJOR}"
GRAPHRAG_HISTORY_ENTRY_SCHEMA: Final[str] = f"{GRAPHRAG_CONTRACT_NAMESPACE}/history-entry@{SCHEMA_MAJOR}"
GRAPHRAG_QUERY_SCHEMA: Final[str] = f"{GRAPHRAG_CONTRACT_NAMESPACE}/query@{SCHEMA_MAJOR}"
GRAPHRAG_RESULT_MATCH_SCHEMA: Final[str] = f"{GRAPHRAG_CONTRACT_NAMESPACE}/result-match@{SCHEMA_MAJOR}"
GRAPHRAG_QUERY_RESULT_SCHEMA: Final[str] = f"{GRAPHRAG_CONTRACT_NAMESPACE}/query-result@{SCHEMA_MAJOR}"
GRAPHRAG_GENERATION_SCHEMA: Final[str] = f"{GRAPHRAG_CONTRACT_NAMESPACE}/generation@{SCHEMA_MAJOR}"

# Public schema aliases make version pinning explicit at call sites.
GraphRAGContent_V1: Final[str] = GRAPHRAG_CONTENT_SCHEMA
GraphRAGRelation_V1: Final[str] = GRAPHRAG_RELATION_SCHEMA
GraphRAGEmbedding_V1: Final[str] = GRAPHRAG_EMBEDDING_SCHEMA
GraphRAGIndexManifest_V1: Final[str] = GRAPHRAG_INDEX_MANIFEST_SCHEMA
GraphRAGHistoryEntry_V1: Final[str] = GRAPHRAG_HISTORY_ENTRY_SCHEMA
GraphRAGQuery_V1: Final[str] = GRAPHRAG_QUERY_SCHEMA
GraphRAGQueryResult_V1: Final[str] = GRAPHRAG_QUERY_RESULT_SCHEMA

MAX_IDENTIFIER_BYTES: Final[int] = 512
MAX_METADATA_BYTES: Final[int] = 16_384
MAX_RECORD_BYTES: Final[int] = 262_144
MAX_VECTOR_DIMENSION: Final[int] = 1_048_576
MAX_COLLECTION_ITEMS: Final[int] = 100_000
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#@+\-]{0,511}$")


class GraphRAGContractError(ValueError):
    """A record is outside the finite GraphRAG contract."""


class GraphRAGSchemaError(GraphRAGContractError):
    """A record used the wrong schema, version, or field set."""


class GraphRAGIdentityMismatchError(GraphRAGContractError):
    """A supplied content identity did not match canonical record bytes."""


class GraphRAGModelMismatchError(GraphRAGContractError):
    """A model or tokenizer identity does not match an index."""


class GraphRAGDimensionMismatchError(GraphRAGContractError):
    """An embedding/query dimension does not match an index."""


class GraphRAGIndexMismatchError(GraphRAGContractError):
    """An index, metric, source, or schema identity does not match."""


class GraphRAGMetric(str, Enum):
    COSINE = "cosine"
    DOT_PRODUCT = "dot_product"
    EUCLIDEAN = "euclidean"


class GraphRAGContentState(str, Enum):
    ACTIVE = "active"
    TOMBSTONED = "tombstoned"


class GraphRAGHistoryOperation(str, Enum):
    ADDED = "added"
    UPDATED = "updated"
    TOMBSTONED = "tombstoned"


class GraphRAGCapabilityState(str, Enum):
    """Declared capability state; it never imports or probes a provider."""

    UNCONFIGURED = "unconfigured"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


def _canonical(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        if isinstance(value, int) and (value > (1 << 53) - 1 or value < -((1 << 53) - 1)):
            raise GraphRAGContractError("integer is outside the safe JSON range")
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise GraphRAGContractError("non-finite floats are forbidden")
        return value
    if isinstance(value, Enum):
        return _canonical(value.value)
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise GraphRAGContractError("record keys must be strings")
        return {key: _canonical(value[key]) for key in sorted(value)}
    if isinstance(value, (tuple, list)):
        return [_canonical(item) for item in value]
    raise GraphRAGContractError(f"unsupported record value: {type(value).__name__}")


def canonical_json_bytes(value: Any) -> bytes:
    """Return deterministic, non-executable JSON bytes for contract data."""

    return json.dumps(
        _canonical(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def content_identity(value: Any) -> str:
    """Return a deterministic CIDv1-like identity for canonical JSON data."""

    digest = hashlib.sha256(canonical_json_bytes(value)).digest()
    raw = b"\x01\xa9\x02\x12\x20" + digest
    return "b" + base64.b32encode(raw).decode("ascii").rstrip("=").lower()


def _identifier(value: Any, field_name: str, *, optional: bool = False) -> str:
    if not isinstance(value, str):
        raise GraphRAGContractError(f"{field_name} must be a string")
    value = value.strip()
    if not value and optional:
        return ""
    if not value or len(value.encode("utf-8")) > MAX_IDENTIFIER_BYTES or not _IDENTIFIER.fullmatch(value):
        raise GraphRAGContractError(f"{field_name} must be a bounded identifier")
    return value


def _positive_int(value: Any, field_name: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > maximum:
        raise GraphRAGContractError(f"{field_name} must be an integer in range")
    return value


def _enum(value: Any, enum_type: type[Enum], field_name: str) -> Enum:
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        raise GraphRAGContractError(f"{field_name} is not a supported value") from exc


def _metadata(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise GraphRAGContractError("metadata must be an object")
    normalized = _canonical(value)
    if len(canonical_json_bytes(normalized)) > MAX_METADATA_BYTES:
        raise GraphRAGContractError("metadata exceeds its byte bound")
    return normalized


def _tuple(value: Any, field_name: str) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise GraphRAGContractError(f"{field_name} must be a sequence")
    if len(value) > MAX_COLLECTION_ITEMS:
        raise GraphRAGContractError(f"{field_name} exceeds its item bound")
    return tuple(value)


def _decode(payload: Mapping[str, Any], schema: str, fields: set[str], name: str) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise GraphRAGSchemaError(f"{name} must be an object")
    if payload.get("schema") != schema or payload.get("contract_version") != CONTRACT_VERSION:
        raise GraphRAGSchemaError(f"{name} schema/version is not supported")
    allowed = fields | {"schema", "contract_version", "content_id"}
    unknown = set(payload) - allowed
    missing = fields - set(payload)
    if unknown or missing:
        raise GraphRAGSchemaError(f"{name} has an invalid field set")
    return payload


def _verify_identity(payload: Mapping[str, Any], value: "GraphRAGContract") -> None:
    supplied = payload.get("content_id")
    if supplied is not None and supplied != value.content_id:
        raise GraphRAGIdentityMismatchError("record content_id is not canonical")


class GraphRAGContract:
    """Immutable, content-addressed base class for all GraphRAG records."""

    SCHEMA: ClassVar[str] = ""

    def _payload(self) -> dict[str, Any]:
        raise NotImplementedError

    @property
    def schema(self) -> str:
        return self.SCHEMA

    def to_dict(self) -> dict[str, Any]:
        return {"schema": self.SCHEMA, "contract_version": CONTRACT_VERSION, **_canonical(self._payload())}

    def to_record(self) -> dict[str, Any]:
        return {**self.to_dict(), "content_id": self.content_id}

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_dict())

    @property
    def content_id(self) -> str:
        return content_identity(self.to_dict())

    @property
    def cid(self) -> str:
        return self.content_id


@dataclass(frozen=True)
class GraphRAGProvenance(GraphRAGContract):
    SCHEMA: ClassVar[str] = GRAPHRAG_PROVENANCE_SCHEMA
    source_id: str
    source_version: str
    source_cid: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_id", _identifier(self.source_id, "source_id"))
        object.__setattr__(self, "source_version", _identifier(self.source_version, "source_version"))
        object.__setattr__(self, "source_cid", _identifier(self.source_cid, "source_cid"))

    def _payload(self) -> dict[str, Any]:
        return {"source_id": self.source_id, "source_version": self.source_version, "source_cid": self.source_cid}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "GraphRAGProvenance":
        raw = _decode(payload, cls.SCHEMA, {"source_id", "source_version", "source_cid"}, "provenance")
        value = cls(raw["source_id"], raw["source_version"], raw["source_cid"])
        _verify_identity(raw, value)
        return value


@dataclass(frozen=True)
class GraphRAGContent(GraphRAGContract):
    SCHEMA: ClassVar[str] = GRAPHRAG_CONTENT_SCHEMA
    document_id: str
    version_id: str
    payload_cid: str
    provenance: GraphRAGProvenance
    state: GraphRAGContentState = GraphRAGContentState.ACTIVE
    tombstone_of: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "document_id", _identifier(self.document_id, "document_id"))
        object.__setattr__(self, "version_id", _identifier(self.version_id, "version_id"))
        object.__setattr__(self, "payload_cid", _identifier(self.payload_cid, "payload_cid", optional=True))
        if not isinstance(self.provenance, GraphRAGProvenance):
            raise GraphRAGContractError("provenance must be GraphRAGProvenance")
        state = _enum(self.state, GraphRAGContentState, "state")
        object.__setattr__(self, "state", state)
        object.__setattr__(self, "tombstone_of", _identifier(self.tombstone_of, "tombstone_of", optional=True))
        object.__setattr__(self, "metadata", _metadata(self.metadata))
        if state is GraphRAGContentState.ACTIVE and not self.payload_cid:
            raise GraphRAGContractError("active content requires payload_cid")
        if state is GraphRAGContentState.TOMBSTONED and (self.payload_cid or not self.tombstone_of):
            raise GraphRAGContractError("tombstoned content requires tombstone_of and no payload_cid")

    def _payload(self) -> dict[str, Any]:
        return {"document_id": self.document_id, "version_id": self.version_id, "payload_cid": self.payload_cid,
                "provenance": self.provenance.to_record(), "state": self.state.value,
                "tombstone_of": self.tombstone_of, "metadata": dict(self.metadata)}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "GraphRAGContent":
        raw = _decode(payload, cls.SCHEMA, {"document_id", "version_id", "payload_cid", "provenance", "state", "tombstone_of", "metadata"}, "content")
        value = cls(raw["document_id"], raw["version_id"], raw["payload_cid"], GraphRAGProvenance.from_dict(raw["provenance"]), raw["state"], raw["tombstone_of"], raw["metadata"])
        _verify_identity(raw, value)
        return value


@dataclass(frozen=True)
class GraphRAGRelation(GraphRAGContract):
    SCHEMA: ClassVar[str] = GRAPHRAG_RELATION_SCHEMA
    relation_id: str
    source_document_id: str
    target_document_id: str
    relation_type: str
    version_id: str
    provenance: GraphRAGProvenance

    def __post_init__(self) -> None:
        for name in ("relation_id", "source_document_id", "target_document_id", "relation_type", "version_id"):
            object.__setattr__(self, name, _identifier(getattr(self, name), name))
        if self.source_document_id == self.target_document_id:
            raise GraphRAGContractError("relations must connect distinct documents")
        if not isinstance(self.provenance, GraphRAGProvenance):
            raise GraphRAGContractError("provenance must be GraphRAGProvenance")

    def _payload(self) -> dict[str, Any]:
        return {"relation_id": self.relation_id, "source_document_id": self.source_document_id,
                "target_document_id": self.target_document_id, "relation_type": self.relation_type,
                "version_id": self.version_id, "provenance": self.provenance.to_record()}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "GraphRAGRelation":
        raw = _decode(payload, cls.SCHEMA, {"relation_id", "source_document_id", "target_document_id", "relation_type", "version_id", "provenance"}, "relation")
        value = cls(raw["relation_id"], raw["source_document_id"], raw["target_document_id"], raw["relation_type"], raw["version_id"], GraphRAGProvenance.from_dict(raw["provenance"]))
        _verify_identity(raw, value)
        return value


@dataclass(frozen=True)
class GraphRAGEmbedding(GraphRAGContract):
    SCHEMA: ClassVar[str] = GRAPHRAG_EMBEDDING_SCHEMA
    embedding_id: str
    document_id: str
    model_id: str
    tokenizer_id: str
    dimension: int
    metric: GraphRAGMetric
    vector_digest: str
    index_id: str
    source_cid: str

    def __post_init__(self) -> None:
        for name in ("embedding_id", "document_id", "model_id", "tokenizer_id", "vector_digest", "index_id", "source_cid"):
            object.__setattr__(self, name, _identifier(getattr(self, name), name))
        object.__setattr__(self, "dimension", _positive_int(self.dimension, "dimension", MAX_VECTOR_DIMENSION))
        object.__setattr__(self, "metric", _enum(self.metric, GraphRAGMetric, "metric"))

    def _payload(self) -> dict[str, Any]:
        return {"embedding_id": self.embedding_id, "document_id": self.document_id, "model_id": self.model_id,
                "tokenizer_id": self.tokenizer_id, "dimension": self.dimension, "metric": self.metric.value,
                "vector_digest": self.vector_digest, "index_id": self.index_id, "source_cid": self.source_cid}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "GraphRAGEmbedding":
        fields = {"embedding_id", "document_id", "model_id", "tokenizer_id", "dimension", "metric", "vector_digest", "index_id", "source_cid"}
        raw = _decode(payload, cls.SCHEMA, fields, "embedding")
        value = cls(**{field: raw[field] for field in fields})
        _verify_identity(raw, value)
        return value


@dataclass(frozen=True)
class GraphRAGIndexManifest(GraphRAGContract):
    SCHEMA: ClassVar[str] = GRAPHRAG_INDEX_MANIFEST_SCHEMA
    generation_id: str
    index_id: str
    model_id: str
    tokenizer_id: str
    dimension: int
    metric: GraphRAGMetric
    source_id: str
    source_version: str
    schema_ids: Sequence[str] = field(default_factory=tuple)
    capability_state: GraphRAGCapabilityState = GraphRAGCapabilityState.UNCONFIGURED

    def __post_init__(self) -> None:
        for name in ("generation_id", "index_id", "model_id", "tokenizer_id", "source_id", "source_version"):
            object.__setattr__(self, name, _identifier(getattr(self, name), name))
        object.__setattr__(self, "dimension", _positive_int(self.dimension, "dimension", MAX_VECTOR_DIMENSION))
        object.__setattr__(self, "metric", _enum(self.metric, GraphRAGMetric, "metric"))
        schemas = tuple(_identifier(value, "schema_ids") for value in _tuple(self.schema_ids, "schema_ids"))
        if len(set(schemas)) != len(schemas):
            raise GraphRAGContractError("schema_ids must be unique")
        object.__setattr__(self, "schema_ids", schemas)
        object.__setattr__(self, "capability_state", _enum(self.capability_state, GraphRAGCapabilityState, "capability_state"))

    def _payload(self) -> dict[str, Any]:
        return {"generation_id": self.generation_id, "index_id": self.index_id, "model_id": self.model_id,
                "tokenizer_id": self.tokenizer_id, "dimension": self.dimension, "metric": self.metric.value,
                "source_id": self.source_id, "source_version": self.source_version,
                "schema_ids": list(self.schema_ids), "capability_state": self.capability_state.value}

    def assert_compatible(self, value: GraphRAGEmbedding | "GraphRAGIndexManifest" | "GraphRAGQuery") -> None:
        """Reject any model, dimension, metric, or index identity drift."""
        if not isinstance(value, (GraphRAGEmbedding, GraphRAGIndexManifest, GraphRAGQuery)):
            raise GraphRAGContractError("compatibility value has an unsupported contract type")
        if self.model_id != value.model_id or self.tokenizer_id != value.tokenizer_id:
            raise GraphRAGModelMismatchError("model/tokenizer identity differs from index manifest")
        if self.dimension != value.dimension:
            raise GraphRAGDimensionMismatchError("vector dimension differs from index manifest")
        if self.metric != value.metric or self.index_id != value.index_id:
            raise GraphRAGIndexMismatchError("metric or index identity differs from index manifest")
        if isinstance(value, GraphRAGIndexManifest) and (self.source_id != value.source_id or self.source_version != value.source_version):
            raise GraphRAGIndexMismatchError("source identity differs from index manifest")

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "GraphRAGIndexManifest":
        fields = {"generation_id", "index_id", "model_id", "tokenizer_id", "dimension", "metric", "source_id", "source_version", "schema_ids", "capability_state"}
        raw = _decode(payload, cls.SCHEMA, fields, "index manifest")
        value = cls(**{field: raw[field] for field in fields})
        _verify_identity(raw, value)
        return value


@dataclass(frozen=True)
class GraphRAGHistoryEntry(GraphRAGContract):
    SCHEMA: ClassVar[str] = GRAPHRAG_HISTORY_ENTRY_SCHEMA
    history_id: str
    document_id: str
    version_id: str
    previous_version_id: str
    operation: GraphRAGHistoryOperation
    content_cid: str

    def __post_init__(self) -> None:
        for name in ("history_id", "document_id", "version_id", "content_cid"):
            object.__setattr__(self, name, _identifier(getattr(self, name), name))
        object.__setattr__(self, "previous_version_id", _identifier(self.previous_version_id, "previous_version_id", optional=True))
        object.__setattr__(self, "operation", _enum(self.operation, GraphRAGHistoryOperation, "operation"))
        if self.operation is GraphRAGHistoryOperation.ADDED and self.previous_version_id:
            raise GraphRAGContractError("added history cannot name a previous version")
        if self.operation is not GraphRAGHistoryOperation.ADDED and not self.previous_version_id:
            raise GraphRAGContractError("update/tombstone history requires a previous version")

    def _payload(self) -> dict[str, Any]:
        return {"history_id": self.history_id, "document_id": self.document_id, "version_id": self.version_id,
                "previous_version_id": self.previous_version_id, "operation": self.operation.value, "content_cid": self.content_cid}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "GraphRAGHistoryEntry":
        fields = {"history_id", "document_id", "version_id", "previous_version_id", "operation", "content_cid"}
        raw = _decode(payload, cls.SCHEMA, fields, "history entry")
        value = cls(**{field: raw[field] for field in fields})
        _verify_identity(raw, value)
        return value


@dataclass(frozen=True)
class GraphRAGQuery(GraphRAGContract):
    SCHEMA: ClassVar[str] = GRAPHRAG_QUERY_SCHEMA
    query_id: str
    query_cid: str
    model_id: str
    tokenizer_id: str
    dimension: int
    metric: GraphRAGMetric
    index_id: str

    def __post_init__(self) -> None:
        for name in ("query_id", "query_cid", "model_id", "tokenizer_id", "index_id"):
            object.__setattr__(self, name, _identifier(getattr(self, name), name))
        object.__setattr__(self, "dimension", _positive_int(self.dimension, "dimension", MAX_VECTOR_DIMENSION))
        object.__setattr__(self, "metric", _enum(self.metric, GraphRAGMetric, "metric"))

    def _payload(self) -> dict[str, Any]:
        return {"query_id": self.query_id, "query_cid": self.query_cid, "model_id": self.model_id,
                "tokenizer_id": self.tokenizer_id, "dimension": self.dimension, "metric": self.metric.value, "index_id": self.index_id}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "GraphRAGQuery":
        fields = {"query_id", "query_cid", "model_id", "tokenizer_id", "dimension", "metric", "index_id"}
        raw = _decode(payload, cls.SCHEMA, fields, "query")
        value = cls(**{field: raw[field] for field in fields})
        _verify_identity(raw, value)
        return value


@dataclass(frozen=True)
class GraphRAGResultMatch(GraphRAGContract):
    SCHEMA: ClassVar[str] = GRAPHRAG_RESULT_MATCH_SCHEMA
    document_id: str
    content_cid: str
    score: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "document_id", _identifier(self.document_id, "document_id"))
        object.__setattr__(self, "content_cid", _identifier(self.content_cid, "content_cid"))
        if isinstance(self.score, bool) or not isinstance(self.score, (int, float)) or not math.isfinite(float(self.score)):
            raise GraphRAGContractError("score must be finite")
        object.__setattr__(self, "score", float(self.score))

    def _payload(self) -> dict[str, Any]:
        return {"document_id": self.document_id, "content_cid": self.content_cid, "score": self.score}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "GraphRAGResultMatch":
        raw = _decode(payload, cls.SCHEMA, {"document_id", "content_cid", "score"}, "result match")
        value = cls(raw["document_id"], raw["content_cid"], raw["score"])
        _verify_identity(raw, value)
        return value


@dataclass(frozen=True)
class GraphRAGQueryResult(GraphRAGContract):
    SCHEMA: ClassVar[str] = GRAPHRAG_QUERY_RESULT_SCHEMA
    query_id: str
    generation_id: str
    matches: Sequence[GraphRAGResultMatch] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "query_id", _identifier(self.query_id, "query_id"))
        object.__setattr__(self, "generation_id", _identifier(self.generation_id, "generation_id"))
        matches = _tuple(self.matches, "matches")
        if not all(isinstance(match, GraphRAGResultMatch) for match in matches):
            raise GraphRAGContractError("matches must contain GraphRAGResultMatch records")
        if len({match.document_id for match in matches}) != len(matches):
            raise GraphRAGContractError("query result matches must have unique document IDs")
        object.__setattr__(self, "matches", matches)

    def _payload(self) -> dict[str, Any]:
        return {"query_id": self.query_id, "generation_id": self.generation_id,
                "matches": [match.to_record() for match in self.matches]}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "GraphRAGQueryResult":
        raw = _decode(payload, cls.SCHEMA, {"query_id", "generation_id", "matches"}, "query result")
        value = cls(raw["query_id"], raw["generation_id"], tuple(GraphRAGResultMatch.from_dict(item) for item in _tuple(raw["matches"], "matches")))
        _verify_identity(raw, value)
        return value


@dataclass(frozen=True)
class GraphRAGGeneration(GraphRAGContract):
    """A complete immutable index generation suitable for safe persistence."""

    SCHEMA: ClassVar[str] = GRAPHRAG_GENERATION_SCHEMA
    manifest: GraphRAGIndexManifest
    contents: Sequence[GraphRAGContent] = field(default_factory=tuple)
    relations: Sequence[GraphRAGRelation] = field(default_factory=tuple)
    embeddings: Sequence[GraphRAGEmbedding] = field(default_factory=tuple)
    history: Sequence[GraphRAGHistoryEntry] = field(default_factory=tuple)
    results: Sequence[GraphRAGQueryResult] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.manifest, GraphRAGIndexManifest):
            raise GraphRAGContractError("manifest must be GraphRAGIndexManifest")
        expected = (("contents", GraphRAGContent, "document_id"), ("relations", GraphRAGRelation, "relation_id"),
                    ("embeddings", GraphRAGEmbedding, "embedding_id"), ("history", GraphRAGHistoryEntry, "history_id"),
                    ("results", GraphRAGQueryResult, "query_id"))
        for name, item_type, identity_field in expected:
            values = _tuple(getattr(self, name), name)
            if not all(isinstance(item, item_type) for item in values):
                raise GraphRAGContractError(f"{name} contains an invalid record type")
            if len({getattr(item, identity_field) for item in values}) != len(values):
                raise GraphRAGContractError(f"{name} must have unique {identity_field}s")
            object.__setattr__(self, name, values)
        contents_by_id = {content.document_id: content for content in self.contents}
        for content in self.contents:
            if (content.provenance.source_id != self.manifest.source_id or
                    content.provenance.source_version != self.manifest.source_version):
                raise GraphRAGIndexMismatchError("content provenance differs from index manifest")
        for relation in self.relations:
            if (relation.source_document_id not in contents_by_id or
                    relation.target_document_id not in contents_by_id):
                raise GraphRAGContractError("relations must reference content in the generation")
            if (relation.provenance.source_id != self.manifest.source_id or
                    relation.provenance.source_version != self.manifest.source_version):
                raise GraphRAGIndexMismatchError("relation provenance differs from index manifest")
        for embedding in self.embeddings:
            self.manifest.assert_compatible(embedding)
            content = contents_by_id.get(embedding.document_id)
            if content is None:
                raise GraphRAGContractError("embeddings must reference content in the generation")
            if embedding.source_cid != content.provenance.source_cid:
                raise GraphRAGIndexMismatchError("embedding source CID differs from its content provenance")
        for entry in self.history:
            if entry.document_id not in contents_by_id:
                raise GraphRAGContractError("history must reference content in the generation")
        for result in self.results:
            if result.generation_id != self.manifest.generation_id:
                raise GraphRAGIndexMismatchError("result generation identity differs from index manifest")
            for match in result.matches:
                content = contents_by_id.get(match.document_id)
                if content is None or match.content_cid != content.content_id:
                    raise GraphRAGContractError("result matches must reference canonical generation content")

    def _payload(self) -> dict[str, Any]:
        return {"manifest": self.manifest.to_record(), "contents": [item.to_record() for item in self.contents],
                "relations": [item.to_record() for item in self.relations], "embeddings": [item.to_record() for item in self.embeddings],
                "history": [item.to_record() for item in self.history], "results": [item.to_record() for item in self.results]}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "GraphRAGGeneration":
        fields = {"manifest", "contents", "relations", "embeddings", "history", "results"}
        raw = _decode(payload, cls.SCHEMA, fields, "generation")
        value = cls(
            GraphRAGIndexManifest.from_dict(raw["manifest"]),
            tuple(GraphRAGContent.from_dict(item) for item in _tuple(raw["contents"], "contents")),
            tuple(GraphRAGRelation.from_dict(item) for item in _tuple(raw["relations"], "relations")),
            tuple(GraphRAGEmbedding.from_dict(item) for item in _tuple(raw["embeddings"], "embeddings")),
            tuple(GraphRAGHistoryEntry.from_dict(item) for item in _tuple(raw["history"], "history")),
            tuple(GraphRAGQueryResult.from_dict(item) for item in _tuple(raw["results"], "results")),
        )
        _verify_identity(raw, value)
        if len(value.canonical_bytes()) > MAX_RECORD_BYTES:
            raise GraphRAGContractError("generation exceeds its record byte bound")
        return value


def validate_index_compatibility(manifest: GraphRAGIndexManifest, value: GraphRAGEmbedding | GraphRAGIndexManifest | GraphRAGQuery) -> None:
    """Public fail-closed compatibility check used by engines and storage."""

    if not isinstance(manifest, GraphRAGIndexManifest):
        raise GraphRAGContractError("manifest must be GraphRAGIndexManifest")
    manifest.assert_compatible(value)
