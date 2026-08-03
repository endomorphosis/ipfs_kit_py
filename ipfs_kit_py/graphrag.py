"""Canonical GraphRAG package surface and multi-interface adapters (KITA-017).

This module is the public package entry for GraphRAG.  It:

1. elevates the durable engine under ``ipfs_kit_py/graphrag/`` into a real
   package (via ``__path__``) so ``from ipfs_kit_py.graphrag.service import …``
   resolves the canonical modules;
2. re-exports those modules without reimplementing engine behaviour; and
3. provides one shared request/result/error envelope used by the package,
   CLI, and MCP projections so normalized payloads are byte-equivalent after
   transport-only fields are stripped.

Historic ``GraphRAGSearchEngine`` is retained only as a thin adapter that
delegates to :class:`GraphRAGService` / vector / hybrid retrieval.  Import or
initialization failure never returns a success or no-op result.

No pickle, no executable cache load, and no optional ML import at module load.
"""

from __future__ import annotations

import json
import math
import secrets
import sys
from collections.abc import Mapping, Sequence
from importlib import import_module
from pathlib import Path
from typing import Any, Final

# ---------------------------------------------------------------------------
# Package elevation: the sibling ``graphrag/`` directory holds the engine.
# ---------------------------------------------------------------------------

_ENGINE_ROOT: Final[Path] = Path(__file__).resolve().parent / "graphrag"
if not _ENGINE_ROOT.is_dir():
    raise ImportError(
        f"canonical GraphRAG engine directory is missing: {_ENGINE_ROOT}"
    )

# Make this module a package so submodule imports resolve to the engine tree.
__path__ = [str(_ENGINE_ROOT)]  # type: ignore[name-defined]

_ENGINE_MODULES: Final[tuple[str, ...]] = (
    "contracts",
    "storage",
    "projections",
    "service",
    "vector_index",
    "retrieval",
)

try:
    _loaded = {
        name: import_module(f"{__name__}.{name}") for name in _ENGINE_MODULES
    }
except Exception as exc:  # fail-closed: never leave a half-loaded facade
    raise ImportError(
        "canonical GraphRAG engine modules failed to import; "
        "wrappers must not degrade to success/no-op"
    ) from exc

contracts = _loaded["contracts"]
storage = _loaded["storage"]
projections = _loaded["projections"]
service = _loaded["service"]
vector_index = _loaded["vector_index"]
retrieval = _loaded["retrieval"]

# Public re-exports (engine is the authority; this file is an adapter only).
GraphRAGContractError = contracts.GraphRAGContractError
GraphRAGSchemaError = contracts.GraphRAGSchemaError
GraphRAGIdentityMismatchError = contracts.GraphRAGIdentityMismatchError
GraphRAGModelMismatchError = contracts.GraphRAGModelMismatchError
GraphRAGDimensionMismatchError = contracts.GraphRAGDimensionMismatchError
GraphRAGIndexMismatchError = contracts.GraphRAGIndexMismatchError
GraphRAGMetric = contracts.GraphRAGMetric
GraphRAGContentState = contracts.GraphRAGContentState
GraphRAGHistoryOperation = contracts.GraphRAGHistoryOperation
GraphRAGCapabilityState = contracts.GraphRAGCapabilityState
GraphRAGProvenance = contracts.GraphRAGProvenance
GraphRAGContent = contracts.GraphRAGContent
GraphRAGRelation = contracts.GraphRAGRelation
GraphRAGEmbedding = contracts.GraphRAGEmbedding
GraphRAGIndexManifest = contracts.GraphRAGIndexManifest
GraphRAGHistoryEntry = contracts.GraphRAGHistoryEntry
GraphRAGQuery = contracts.GraphRAGQuery
GraphRAGResultMatch = contracts.GraphRAGResultMatch
GraphRAGQueryResult = contracts.GraphRAGQueryResult
GraphRAGGeneration = contracts.GraphRAGGeneration
canonical_json_bytes = contracts.canonical_json_bytes
content_identity = contracts.content_identity
validate_index_compatibility = contracts.validate_index_compatibility

SafeGraphRAGStorage = storage.SafeGraphRAGStorage
GraphRAGStorageError = storage.GraphRAGStorageError
GraphRAGStorageSecurityError = storage.GraphRAGStorageSecurityError
GraphRAGStorageFormatError = storage.GraphRAGStorageFormatError

GraphProjection = projections.GraphProjection
IndexGeneration = projections.IndexGeneration

GraphRAGService = service.GraphRAGService
GraphRAGServiceError = service.GraphRAGServiceError
GraphRAGLedgerError = service.GraphRAGLedgerError
GraphRAGVersionError = service.GraphRAGVersionError
GraphRAGProjectionError = service.GraphRAGProjectionError

VectorIndex = vector_index.VectorIndex
ExactVectorIndex = vector_index.ExactVectorIndex
ANNVectorIndex = vector_index.ANNVectorIndex
VectorIndexIdentity = vector_index.VectorIndexIdentity
VectorRecord = vector_index.VectorRecord
VectorSearchResult = vector_index.VectorSearchResult
VectorIndexError = vector_index.VectorIndexError
VectorIdentityMismatchError = vector_index.VectorIdentityMismatchError

HybridRetriever = retrieval.HybridRetriever
HybridWeights = retrieval.HybridWeights
HybridSearchResult = retrieval.HybridSearchResult
HybridSearchResponse = retrieval.HybridSearchResponse
LexicalSearchResult = retrieval.LexicalSearchResult
HybridRetrievalError = retrieval.HybridRetrievalError

# ---------------------------------------------------------------------------
# Shared multi-interface envelope (package / CLI / MCP)
# ---------------------------------------------------------------------------

CONTRACT_VERSION: Final[int] = 1
GRAPHRAG_INTERFACE_NAMESPACE: Final[str] = "ipfs_kit_py/graphrag/interface"
GRAPHRAG_REQUEST_SCHEMA: Final[str] = f"{GRAPHRAG_INTERFACE_NAMESPACE}/request@1"
GRAPHRAG_RESULT_SCHEMA: Final[str] = f"{GRAPHRAG_INTERFACE_NAMESPACE}/result@1"
GRAPHRAG_ERROR_SCHEMA: Final[str] = f"{GRAPHRAG_INTERFACE_NAMESPACE}/error@1"
GRAPHRAG_CONFORMANCE_SCHEMA: Final[str] = (
    "ipfs_kit_py/runtime-readiness/graphrag-conformance@1"
)

TRANSPORTS: Final[tuple[str, ...]] = ("package", "cli", "mcp")
TRANSPORT_ONLY_KEYS: Final[frozenset[str]] = frozenset(
    {
        "request_id",
        "related_request_id",
        "transport",
        "timing",
        "elapsed_ms",
        "duration_ms",
        "started_at_ms",
        "finished_at_ms",
        "timestamp",
        "wall_time_ms",
        "framing",
        "jsonrpc",
        "id",
        "http_status",
        "protocol_id",
        "stream_id",
    }
)

# Operation identifiers shared by every interface.
OP_OPEN: Final[str] = "graphrag.open"
OP_APPLY: Final[str] = "graphrag.apply"
OP_DELETE: Final[str] = "graphrag.delete"
OP_REHYDRATE: Final[str] = "graphrag.rehydrate"
OP_REBUILD: Final[str] = "graphrag.rebuild"
OP_VERSION_HISTORY: Final[str] = "graphrag.version_history"
OP_CURRENT: Final[str] = "graphrag.current_content"
OP_VECTOR_SEARCH: Final[str] = "graphrag.vector_search"
OP_HYBRID_SEARCH: Final[str] = "graphrag.hybrid_search"
OP_PROJECTION: Final[str] = "graphrag.projection"

GRAPHRAG_OPERATIONS: Final[tuple[str, ...]] = (
    OP_OPEN,
    OP_APPLY,
    OP_DELETE,
    OP_REHYDRATE,
    OP_REBUILD,
    OP_VERSION_HISTORY,
    OP_CURRENT,
    OP_VECTOR_SEARCH,
    OP_HYBRID_SEARCH,
    OP_PROJECTION,
)

# Per-operation request field contracts (closed; unknown keys rejected).
_REQUEST_FIELDS: Final[Mapping[str, frozenset[str]]] = {
    OP_OPEN: frozenset({"root", "manifest"}),
    OP_APPLY: frozenset({"root", "manifest", "content", "relations", "embeddings"}),
    OP_DELETE: frozenset({"root", "manifest", "content"}),
    OP_REHYDRATE: frozenset({"root", "manifest"}),
    OP_REBUILD: frozenset({"root", "manifest"}),
    OP_VERSION_HISTORY: frozenset({"root", "manifest", "document_id"}),
    OP_CURRENT: frozenset({"root", "manifest", "document_id"}),
    OP_VECTOR_SEARCH: frozenset(
        {"query_vector", "k", "filters", "identity", "records", "backend"}
    ),
    OP_HYBRID_SEARCH: frozenset(
        {
            "query_vector",
            "text_query",
            "k",
            "filters",
            "identity",
            "records",
            "lexical_results",
            "vector_weight",
            "lexical_weight",
            "allow_exact_fallback",
            "backend",
        }
    ),
    OP_PROJECTION: frozenset({"root", "manifest"}),
}


class GraphRAGInterfaceError(ValueError):
    """A package/CLI/MCP GraphRAG request could not be admitted."""


class GraphRAGImportError(GraphRAGInterfaceError, ImportError):
    """A required GraphRAG surface could not be imported (fail-closed)."""


def _canonical(value: Any) -> Any:
    """Deterministic JSON projection used for byte-equivalent comparison."""

    return json.loads(canonical_json_bytes(value).decode("utf-8"))


def strip_transport_fields(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Drop transport-only keys so package/CLI/MCP results can match exactly."""

    if not isinstance(payload, Mapping):
        raise GraphRAGInterfaceError("payload must be an object")

    def walk(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {
                key: walk(item)
                for key, item in value.items()
                if key not in TRANSPORT_ONLY_KEYS
            }
        if isinstance(value, list):
            return [walk(item) for item in value]
        return value

    return walk(dict(payload))


def semantic_payload(payload: Mapping[str, Any]) -> bytes:
    """Return canonical JSON bytes of the transport-stripped payload."""

    return canonical_json_bytes(strip_transport_fields(payload))


def _error_record(
    code: str,
    message: str,
    *,
    operation: str,
    category: str = "request",
) -> dict[str, Any]:
    return {
        "schema": GRAPHRAG_ERROR_SCHEMA,
        "contract_version": CONTRACT_VERSION,
        "code": code,
        "category": category,
        "message": message,
        "operation": operation,
        "retryable": False,
    }


def _success_envelope(
    operation: str,
    result: Mapping[str, Any],
    *,
    transport: str,
    request_id: str,
    content_cid: str | None = None,
    generation_id: str | None = None,
) -> dict[str, Any]:
    if transport not in TRANSPORTS:
        raise GraphRAGInterfaceError(f"unknown transport: {transport}")
    envelope: dict[str, Any] = {
        "schema": GRAPHRAG_RESULT_SCHEMA,
        "contract_version": CONTRACT_VERSION,
        "success": True,
        "operation": operation,
        "request_schema": GRAPHRAG_REQUEST_SCHEMA,
        "result_schema": GRAPHRAG_RESULT_SCHEMA,
        "error_schema": GRAPHRAG_ERROR_SCHEMA,
        "result": _canonical(result),
        "error": None,
        "content_cid": content_cid,
        "generation_id": generation_id,
        "transport": transport,
        "request_id": request_id,
    }
    return envelope


def _failure_envelope(
    operation: str,
    error: Mapping[str, Any],
    *,
    transport: str,
    request_id: str,
) -> dict[str, Any]:
    if transport not in TRANSPORTS:
        raise GraphRAGInterfaceError(f"unknown transport: {transport}")
    return {
        "schema": GRAPHRAG_RESULT_SCHEMA,
        "contract_version": CONTRACT_VERSION,
        "success": False,
        "operation": operation,
        "request_schema": GRAPHRAG_REQUEST_SCHEMA,
        "result_schema": GRAPHRAG_RESULT_SCHEMA,
        "error_schema": GRAPHRAG_ERROR_SCHEMA,
        "result": None,
        "error": _canonical(error),
        "content_cid": None,
        "generation_id": None,
        "transport": transport,
        "request_id": request_id,
    }


def request_schema_for(operation: str) -> dict[str, Any]:
    """Return the closed JSON-schema-like descriptor for one operation."""

    if operation not in _REQUEST_FIELDS:
        raise GraphRAGInterfaceError(f"unknown GraphRAG operation: {operation}")
    fields = sorted(_REQUEST_FIELDS[operation])
    return {
        "schema": GRAPHRAG_REQUEST_SCHEMA,
        "contract_version": CONTRACT_VERSION,
        "operation": operation,
        "required": ["operation"],
        "properties": {
            "operation": {"const": operation},
            **{field: {"type": "any"} for field in fields},
        },
        "additionalProperties": False,
        "fields": fields,
    }


def all_request_schemas() -> dict[str, dict[str, Any]]:
    return {operation: request_schema_for(operation) for operation in GRAPHRAG_OPERATIONS}


def _require_mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise GraphRAGInterfaceError(f"{name} must be an object")
    return value


def _admit_request(operation: str, request: Mapping[str, Any]) -> Mapping[str, Any]:
    if operation not in _REQUEST_FIELDS:
        raise GraphRAGInterfaceError(f"unknown GraphRAG operation: {operation}")
    body = _require_mapping(request, "request")
    if body.get("operation", operation) != operation:
        raise GraphRAGInterfaceError("request.operation does not match dispatch operation")
    allowed = _REQUEST_FIELDS[operation] | {"operation", "request_id", "context"}
    unknown = set(body) - allowed
    if unknown:
        raise GraphRAGInterfaceError(
            f"request contains unknown fields: {', '.join(sorted(unknown))}"
        )
    return body


def _manifest_from(value: Any) -> Any:
    if isinstance(value, GraphRAGIndexManifest):
        return value
    return GraphRAGIndexManifest.from_dict(_require_mapping(value, "manifest"))


def _content_from(value: Any) -> Any:
    if isinstance(value, GraphRAGContent):
        return value
    return GraphRAGContent.from_dict(_require_mapping(value, "content"))


def _relations_from(value: Any) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        out = []
        for item in value:
            if isinstance(item, GraphRAGRelation):
                out.append(item)
            else:
                out.append(GraphRAGRelation.from_dict(_require_mapping(item, "relation")))
        return tuple(out)
    raise GraphRAGInterfaceError("relations must be a sequence")


def _embeddings_from(value: Any) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        out = []
        for item in value:
            if isinstance(item, GraphRAGEmbedding):
                out.append(item)
            else:
                out.append(GraphRAGEmbedding.from_dict(_require_mapping(item, "embedding")))
        return tuple(out)
    raise GraphRAGInterfaceError("embeddings must be a sequence")


def _open_service(root: Any, manifest: Any) -> Any:
    if not isinstance(root, str) or not root:
        raise GraphRAGInterfaceError("root must be a non-empty path string")
    return GraphRAGService.open(root, _manifest_from(manifest))


def _generation_summary(generation: Any) -> dict[str, Any]:
    gen = generation.generation if hasattr(generation, "generation") else generation
    manifest = gen.manifest if hasattr(gen, "manifest") else generation.manifest
    projection = getattr(generation, "projection", None)
    nodes = () if projection is None else tuple(item.document_id for item in projection.nodes)
    edges = () if projection is None else tuple(item.relation_id for item in projection.edges)
    return {
        "generation_id": manifest.generation_id,
        "generation_cid": gen.content_id if hasattr(gen, "content_id") else content_identity(gen.to_record()),
        "manifest_cid": manifest.content_id,
        "source_event_id": getattr(generation, "source_event_id", ""),
        "projection_identity": None if projection is None else projection.identity,
        "nodes": list(nodes),
        "edges": list(edges),
        "content_count": len(gen.contents) if hasattr(gen, "contents") else len(nodes),
        "relation_count": len(gen.relations) if hasattr(gen, "relations") else len(edges),
        "embedding_count": len(gen.embeddings) if hasattr(gen, "embeddings") else 0,
    }


def _vector_identity_from(value: Any) -> Any:
    if value is None:
        raise GraphRAGInterfaceError("identity is required for vector/hybrid search")
    if isinstance(value, VectorIndexIdentity):
        return value
    body = _require_mapping(value, "identity")
    return VectorIndexIdentity(
        body["index_id"],
        body["model_id"],
        body["tokenizer_id"],
        int(body["dimension"]),
        body.get("metric", "cosine"),
        body.get("source_id", ""),
        body.get("source_version", ""),
    )


def _records_from(value: Any, identity: Any) -> tuple[Any, ...]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise GraphRAGInterfaceError("records must be a sequence")
    out = []
    for item in value:
        if isinstance(item, VectorRecord):
            out.append(item)
            continue
        body = _require_mapping(item, "record")
        vector = body["vector"]
        if not isinstance(vector, Sequence) or isinstance(vector, (str, bytes)):
            raise GraphRAGInterfaceError("record.vector must be a numeric sequence")
        out.append(
            VectorRecord(
                body["record_id"],
                tuple(float(x) for x in vector),
                body.get("metadata") or {},
                identity,
            )
        )
    return tuple(out)


def _build_vector_index(body: Mapping[str, Any], identity: Any) -> Any:
    backend = body.get("backend", "exact")
    if backend not in ("exact", "ann"):
        raise GraphRAGInterfaceError("backend must be 'exact' or 'ann'")
    records = _records_from(body.get("records"), identity)
    if backend == "ann":
        index = ANNVectorIndex(identity)
    else:
        index = ExactVectorIndex(identity)
    if records:
        index.rebuild(records, identity=identity)
    return index


def _vector_results_to_records(results: Sequence[Any]) -> list[dict[str, Any]]:
    return [
        {
            "record_id": item.record_id,
            "score": float(item.score),
            "metadata": dict(item.metadata),
        }
        for item in results
    ]


def _hybrid_results_to_records(response: Any) -> dict[str, Any]:
    return {
        "results": [
            {
                "document_id": item.document_id,
                "score": float(item.score),
                "vector_score": None if item.vector_score is None else float(item.vector_score),
                "lexical_score": None if item.lexical_score is None else float(item.lexical_score),
                "metadata": dict(item.metadata),
                "authoritative": False,
            }
            for item in response.results
        ],
        "weights": {
            "vector": float(response.weights.vector),
            "lexical": float(response.weights.lexical),
        },
        "exact_fallback_used": bool(response.exact_fallback_used),
        "exact_fallback_reason": str(response.exact_fallback_reason),
        "exact_fallback_limit": int(response.exact_fallback_limit),
        "authoritative": False,
    }


def _execute(operation: str, body: Mapping[str, Any]) -> tuple[dict[str, Any], str | None, str | None]:
    """Run one admitted operation against the canonical engine.

    Returns ``(result, content_cid, generation_id)``.
    """

    if operation in (OP_OPEN, OP_REHYDRATE, OP_REBUILD, OP_PROJECTION):
        svc = _open_service(body["root"], body["manifest"])
        if operation == OP_REBUILD:
            generation = svc.rebuild()
        elif operation == OP_REHYDRATE:
            generation = svc.rehydrate()
        else:
            generation = svc.index_generation
            if generation is None:
                generation = svc.rehydrate()
        summary = _generation_summary(generation)
        return summary, summary["generation_cid"], summary["generation_id"]

    if operation == OP_APPLY:
        svc = _open_service(body["root"], body["manifest"])
        content = _content_from(body["content"])
        generation = svc.apply(
            content,
            relations=_relations_from(body.get("relations")),
            embeddings=_embeddings_from(body.get("embeddings")),
        )
        summary = _generation_summary(generation)
        summary["document_id"] = content.document_id
        summary["version_id"] = content.version_id
        summary["content_cid"] = content.content_id
        return summary, content.content_id, summary["generation_id"]

    if operation == OP_DELETE:
        svc = _open_service(body["root"], body["manifest"])
        content = _content_from(body["content"])
        generation = svc.delete_content(content)
        summary = _generation_summary(generation)
        summary["document_id"] = content.document_id
        summary["version_id"] = content.version_id
        summary["content_cid"] = content.content_id
        return summary, content.content_id, summary["generation_id"]

    if operation == OP_VERSION_HISTORY:
        svc = _open_service(body["root"], body["manifest"])
        document_id = body.get("document_id")
        if not isinstance(document_id, str) or not document_id:
            raise GraphRAGInterfaceError("document_id is required")
        history = svc.version_history(document_id)
        records = [item.to_record() for item in history]
        return {
            "document_id": document_id,
            "versions": records,
            "content_cids": [item.content_id for item in history],
        }, records[-1]["content_id"] if records else None, None

    if operation == OP_CURRENT:
        svc = _open_service(body["root"], body["manifest"])
        document_id = body.get("document_id")
        if not isinstance(document_id, str) or not document_id:
            raise GraphRAGInterfaceError("document_id is required")
        current = svc.current_content(document_id)
        if current is None:
            return {"document_id": document_id, "content": None}, None, None
        return {
            "document_id": document_id,
            "content": current.to_record(),
        }, current.content_id, None

    if operation == OP_VECTOR_SEARCH:
        identity = _vector_identity_from(body.get("identity"))
        index = _build_vector_index(body, identity)
        query = body.get("query_vector")
        if not isinstance(query, Sequence) or isinstance(query, (str, bytes)):
            raise GraphRAGInterfaceError("query_vector must be a numeric sequence")
        k = int(body.get("k", 10))
        filters = body.get("filters")
        results = index.search(
            tuple(float(x) for x in query),
            k,
            filters=filters,
            identity=identity,
        )
        payload = {
            "matches": _vector_results_to_records(results),
            "k": k,
            "backend": body.get("backend", "exact"),
            "identity": {
                "index_id": identity.index_id,
                "model_id": identity.model_id,
                "tokenizer_id": identity.tokenizer_id,
                "dimension": identity.dimension,
                "metric": identity.metric,
            },
            "authoritative": False,
        }
        return payload, None, None

    if operation == OP_HYBRID_SEARCH:
        identity = _vector_identity_from(body.get("identity"))
        index = _build_vector_index(body, identity)
        query = body.get("query_vector")
        if not isinstance(query, Sequence) or isinstance(query, (str, bytes)):
            raise GraphRAGInterfaceError("query_vector must be a numeric sequence")
        text_query = body.get("text_query", "")
        if not isinstance(text_query, str):
            raise GraphRAGInterfaceError("text_query must be a string")
        k = int(body.get("k", 10))
        filters = body.get("filters")
        lexical_payload = body.get("lexical_results") or ()
        if not isinstance(lexical_payload, Sequence) or isinstance(lexical_payload, (str, bytes)):
            raise GraphRAGInterfaceError("lexical_results must be a sequence")

        def lexical_search(_text: str, limit: int, _filters: Mapping[str, Any] | None):
            values = []
            for item in lexical_payload[:limit]:
                if isinstance(item, LexicalSearchResult):
                    values.append(item)
                else:
                    mapping = _require_mapping(item, "lexical result")
                    values.append(
                        LexicalSearchResult(
                            mapping["document_id"],
                            float(mapping["score"]),
                            mapping.get("metadata") or {},
                        )
                    )
            return values

        retriever = HybridRetriever(index, lexical_search=lexical_search)
        response = retriever.search(
            tuple(float(x) for x in query),
            text_query=text_query,
            k=k,
            filters=filters,
            identity=identity,
            vector_weight=body.get("vector_weight"),
            lexical_weight=body.get("lexical_weight"),
            allow_exact_fallback=bool(body.get("allow_exact_fallback", False)),
        )
        payload = _hybrid_results_to_records(response)
        payload["k"] = k
        payload["backend"] = body.get("backend", "exact")
        return payload, None, None

    raise GraphRAGInterfaceError(f"operation not implemented: {operation}")


def dispatch(
    operation: str,
    request: Mapping[str, Any] | None = None,
    *,
    transport: str = "package",
    request_id: str | None = None,
) -> dict[str, Any]:
    """Dispatch a GraphRAG operation through the shared interface envelope.

    Every transport (package, CLI, MCP) must call this function so request
    admission, engine execution, and result/error/CID normalization are shared.
    """

    if transport not in TRANSPORTS:
        raise GraphRAGInterfaceError(f"unknown transport: {transport}")
    rid = request_id or f"graphrag-{secrets.token_hex(8)}"
    try:
        body = _admit_request(operation, request or {})
        result, content_cid, generation_id = _execute(operation, body)
        return _success_envelope(
            operation,
            result,
            transport=transport,
            request_id=rid,
            content_cid=content_cid,
            generation_id=generation_id,
        )
    except (
        GraphRAGInterfaceError,
        GraphRAGContractError,
        GraphRAGServiceError,
        GraphRAGStorageError,
        VectorIndexError,
        HybridRetrievalError,
        TypeError,
        ValueError,
        KeyError,
        OSError,
    ) as exc:
        # Fail closed: never translate semantic failure into success.
        code = type(exc).__name__
        category = "request"
        if isinstance(exc, (GraphRAGStorageSecurityError, GraphRAGStorageFormatError)):
            category = "poisoning"
        elif isinstance(exc, (GraphRAGLedgerError, GraphRAGProjectionError)):
            category = "ledger"
        elif isinstance(exc, (VectorIdentityMismatchError, GraphRAGIndexMismatchError, GraphRAGModelMismatchError, GraphRAGDimensionMismatchError)):
            category = "identity"
        elif isinstance(exc, GraphRAGVersionError):
            category = "version"
        return _failure_envelope(
            operation,
            _error_record(code, str(exc) or code, operation=operation, category=category),
            transport=transport,
            request_id=rid,
        )


def package_call(operation: str, request: Mapping[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
    """Package (Python) transport projection."""

    return dispatch(operation, request, transport="package", **kwargs)


def cli_call(operation: str, request: Mapping[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
    """CLI transport projection (JSON-line friendly, not a stub)."""

    return dispatch(operation, request, transport="cli", **kwargs)


def mcp_call(operation: str, request: Mapping[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
    """MCP transport projection used by MCP and MCP++ tool adapters."""

    return dispatch(operation, request, transport="mcp", **kwargs)


# Explicit CLI vector/hybrid paths (acceptance: not stubs).
def cli_vector_search(request: Mapping[str, Any], **kwargs: Any) -> dict[str, Any]:
    return cli_call(OP_VECTOR_SEARCH, request, **kwargs)


def cli_hybrid_search(request: Mapping[str, Any], **kwargs: Any) -> dict[str, Any]:
    return cli_call(OP_HYBRID_SEARCH, request, **kwargs)


def package_vector_search(request: Mapping[str, Any], **kwargs: Any) -> dict[str, Any]:
    return package_call(OP_VECTOR_SEARCH, request, **kwargs)


def package_hybrid_search(request: Mapping[str, Any], **kwargs: Any) -> dict[str, Any]:
    return package_call(OP_HYBRID_SEARCH, request, **kwargs)


def mcp_vector_search(request: Mapping[str, Any], **kwargs: Any) -> dict[str, Any]:
    return mcp_call(OP_VECTOR_SEARCH, request, **kwargs)


def mcp_hybrid_search(request: Mapping[str, Any], **kwargs: Any) -> dict[str, Any]:
    return mcp_call(OP_HYBRID_SEARCH, request, **kwargs)


def assert_interface_parity(
    *envelopes: Mapping[str, Any],
) -> bytes:
    """Assert that envelopes are byte-equivalent after transport stripping.

    Returns the shared semantic payload bytes.  Raises on any mismatch.
    """

    if len(envelopes) < 2:
        raise GraphRAGInterfaceError("parity requires at least two envelopes")
    payloads = [semantic_payload(env) for env in envelopes]
    first = payloads[0]
    for index, payload in enumerate(payloads[1:], start=1):
        if payload != first:
            raise GraphRAGInterfaceError(
                f"interface parity mismatch between envelope 0 and {index}"
            )
    return first


# ---------------------------------------------------------------------------
# Thin legacy adapter: GraphRAGSearchEngine delegates to the canonical engine.
# ---------------------------------------------------------------------------


class GraphRAGSearchEngine:
    """Thin adapter over :class:`GraphRAGService` and hybrid retrieval.

    The historic SQLite / pickle / optional-ML engine is retired.  This class
    keeps a familiar name for callers while every durable mutation and query
    goes through the shared :func:`dispatch` path.  Construction never
    swallows import failure into a successful no-op engine.
    """

    def __init__(
        self,
        workspace_dir: str | None = None,
        enable_caching: bool = True,
        *,
        db_path: str | None = None,
        cache_file: str | None = None,
        manifest: Any | None = None,
        root: str | None = None,
    ) -> None:
        # Fail closed on the retired unsafe persistence path.
        if cache_file is not None:
            raise GraphRAGInterfaceError(
                "pickle embedding cache is retired; use GraphRAGService durable records"
            )
        if db_path is not None and root is None:
            # Treat explicit db_path as a workspace root for the durable service.
            root = str(Path(db_path).expanduser().absolute().parent)

        if GraphRAGService is None or HybridRetriever is None:
            raise GraphRAGImportError("canonical GraphRAG engine is not available")

        self.enable_caching = bool(enable_caching)
        self.workspace_dir = workspace_dir or root
        if self.workspace_dir is None:
            import tempfile

            self._tmp = tempfile.TemporaryDirectory(prefix="ipfs_kit_graphrag_")
            self.workspace_dir = self._tmp.name
        else:
            self._tmp = None

        self.manifest = manifest or GraphRAGIndexManifest(
            "adapter-generation",
            "index-adapter",
            "model-adapter",
            "tokenizer-adapter",
            3,
            GraphRAGMetric.COSINE,
            "source-adapter",
            "source-version-adapter",
        )
        self._service = GraphRAGService(self.workspace_dir, self.manifest)
        # Vector index is rebuilt from admitted embeddings on demand.
        self._identity = VectorIndexIdentity.from_manifest(self.manifest)
        self._vector_index: Any = ExactVectorIndex(self._identity)
        self.stats = {"total_indexed": 0, "cache_hits": 0, "cache_misses": 0}
        # Compatibility attributes expected by some historic callers.
        self.db_path = str(Path(self.workspace_dir) / "records")
        self.conn = None
        self.embeddings_model = None
        self.knowledge_graph = None
        self.rdf_graph = None
        self.nlp_model = None
        self.embedding_cache: dict[str, Any] = {}

    def _manifest_request(self) -> dict[str, Any]:
        return {
            "root": self.workspace_dir,
            "manifest": self.manifest.to_record(),
        }

    async def index_content(
        self,
        cid: str,
        path: str = "",
        content: str = "",
        **kwargs: Any,
    ) -> dict[str, Any]:
        document_id = kwargs.get("document_id") or cid
        version_id = kwargs.get("version_id") or f"{document_id}-v{self.stats['total_indexed'] + 1}"
        provenance = GraphRAGProvenance(
            self.manifest.source_id,
            self.manifest.source_version,
            kwargs.get("source_cid") or cid or document_id,
        )
        record = GraphRAGContent(document_id, version_id, content or path or cid, provenance)
        envelope = package_call(
            OP_APPLY,
            {
                **self._manifest_request(),
                "content": record.to_record(),
            },
        )
        if not envelope["success"]:
            return {"success": False, "error": envelope["error"], "cid": cid}
        self.stats["total_indexed"] += 1
        return {
            "success": True,
            "cid": cid,
            "document_id": document_id,
            "version_id": version_id,
            "content_cid": envelope.get("content_cid"),
            "generation_id": envelope.get("generation_id"),
        }

    async def search(self, query: str, search_type: str = "hybrid", **kwargs: Any) -> Any:
        if search_type == "vector":
            return await self.vector_search(query, **kwargs)
        if search_type in ("hybrid", "text", "graph", "sparql"):
            return await self.hybrid_search(query, **kwargs)
        envelope = _failure_envelope(
            OP_HYBRID_SEARCH,
            _error_record("UnsupportedSearchType", f"unsupported search_type: {search_type}", operation=OP_HYBRID_SEARCH),
            transport="package",
            request_id=f"graphrag-{secrets.token_hex(4)}",
        )
        return {"success": False, "error": envelope["error"]}

    async def vector_search(self, query: str, limit: int = 10, **kwargs: Any) -> dict[str, Any]:
        query_vector = kwargs.get("query_vector")
        if query_vector is None:
            # Deterministic pseudo-embedding from text without optional ML deps.
            query_vector = _text_to_vector(query, self._identity.dimension)
        records = kwargs.get("records") or ()
        envelope = package_vector_search(
            {
                "query_vector": list(query_vector),
                "k": limit,
                "identity": {
                    "index_id": self._identity.index_id,
                    "model_id": self._identity.model_id,
                    "tokenizer_id": self._identity.tokenizer_id,
                    "dimension": self._identity.dimension,
                    "metric": self._identity.metric,
                    "source_id": self._identity.source_id,
                    "source_version": self._identity.source_version,
                },
                "records": records,
                "filters": kwargs.get("filters"),
                "backend": kwargs.get("backend", "exact"),
            }
        )
        if not envelope["success"]:
            return {"success": False, "error": envelope["error"], "results": []}
        return {
            "success": True,
            "results": envelope["result"]["matches"],
            "content_cid": envelope.get("content_cid"),
        }

    async def hybrid_search(self, query: str, **kwargs: Any) -> dict[str, Any]:
        query_vector = kwargs.get("query_vector")
        if query_vector is None:
            query_vector = _text_to_vector(query, self._identity.dimension)
        envelope = package_hybrid_search(
            {
                "query_vector": list(query_vector),
                "text_query": query,
                "k": int(kwargs.get("limit", kwargs.get("k", 10))),
                "identity": {
                    "index_id": self._identity.index_id,
                    "model_id": self._identity.model_id,
                    "tokenizer_id": self._identity.tokenizer_id,
                    "dimension": self._identity.dimension,
                    "metric": self._identity.metric,
                    "source_id": self._identity.source_id,
                    "source_version": self._identity.source_version,
                },
                "records": kwargs.get("records") or (),
                "lexical_results": kwargs.get("lexical_results") or (),
                "filters": kwargs.get("filters"),
                "vector_weight": kwargs.get("vector_weight"),
                "lexical_weight": kwargs.get("lexical_weight"),
                "allow_exact_fallback": kwargs.get("allow_exact_fallback", False),
                "backend": kwargs.get("backend", "exact"),
            }
        )
        if not envelope["success"]:
            return {"success": False, "error": envelope["error"], "results": []}
        return {
            "success": True,
            "results": envelope["result"]["results"],
            "weights": envelope["result"]["weights"],
            "exact_fallback_used": envelope["result"]["exact_fallback_used"],
        }

    async def text_search(self, query: str, limit: int = 10) -> dict[str, Any]:
        return await self.hybrid_search(query, limit=limit, vector_weight=0.0, lexical_weight=1.0)

    async def graph_search(self, query: str, max_depth: int = 2, **kwargs: Any) -> dict[str, Any]:
        # Graph traversal is a ranking projection only; reuse hybrid path.
        return await self.hybrid_search(query, **kwargs)

    async def sparql_search(self, query: str, **kwargs: Any) -> dict[str, Any]:
        return {
            "success": False,
            "error": {
                "schema": GRAPHRAG_ERROR_SCHEMA,
                "code": "SPARQLRetired",
                "message": "SPARQL path retired; use GraphRAGService durable queries",
                "operation": "graphrag.sparql_search",
            },
            "results": [],
        }

    def cleanup(self) -> None:
        if self._tmp is not None:
            self._tmp.cleanup()
            self._tmp = None

    def get_statistics(self) -> dict[str, Any]:
        return dict(self.stats)

    get_stats = get_statistics


def _text_to_vector(text: str, dimension: int) -> tuple[float, ...]:
    """Bounded deterministic text embedding used when no ML model is present.

    This is not a semantic model; it exists so CLI/package/MCP vector paths
    remain non-stub without importing optional ML stacks at module load.
    """

    if not isinstance(text, str):
        raise GraphRAGInterfaceError("query text must be a string")
    if not isinstance(dimension, int) or dimension < 1:
        raise GraphRAGInterfaceError("dimension must be a positive integer")
    values = [0.0] * dimension
    if not text:
        values[0] = 1.0
        return tuple(values)
    data = text.encode("utf-8")
    for index, byte in enumerate(data):
        values[index % dimension] += (byte + 1) / 256.0
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return tuple(v / norm for v in values)


# Versioned public aliases for the interface registry.
GraphRAGService_V1 = GraphRAGService
MCPGraphRAGTools_V1 = "ipfs_kit_py/graphrag/mcp-tools@1"
GraphRAGConformanceReceipt_V1 = GRAPHRAG_CONFORMANCE_SCHEMA

__all__ = [
    # Engine re-exports
    "GraphRAGService",
    "GraphRAGIndexManifest",
    "GraphRAGContent",
    "GraphRAGRelation",
    "GraphRAGEmbedding",
    "GraphRAGProvenance",
    "GraphRAGMetric",
    "GraphRAGContentState",
    "GraphProjection",
    "IndexGeneration",
    "ExactVectorIndex",
    "ANNVectorIndex",
    "VectorIndexIdentity",
    "VectorRecord",
    "HybridRetriever",
    "HybridWeights",
    "canonical_json_bytes",
    "content_identity",
    # Interface
    "dispatch",
    "package_call",
    "cli_call",
    "mcp_call",
    "cli_vector_search",
    "cli_hybrid_search",
    "package_vector_search",
    "package_hybrid_search",
    "mcp_vector_search",
    "mcp_hybrid_search",
    "request_schema_for",
    "all_request_schemas",
    "strip_transport_fields",
    "semantic_payload",
    "assert_interface_parity",
    "GraphRAGSearchEngine",
    "GraphRAGInterfaceError",
    "GraphRAGImportError",
    "GRAPHRAG_REQUEST_SCHEMA",
    "GRAPHRAG_RESULT_SCHEMA",
    "GRAPHRAG_ERROR_SCHEMA",
    "GRAPHRAG_OPERATIONS",
    "TRANSPORTS",
    "TRANSPORT_ONLY_KEYS",
]
