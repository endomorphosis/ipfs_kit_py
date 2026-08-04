"""Canonical GraphRAG MCP / MCP++ tools (KITA-017).

These tools project the shared package GraphRAG interface
(``ipfs_kit_py.graphrag.dispatch``) into MCP ``tools/list`` / ``tools/call``
descriptors.  Request schemas, result/error envelopes, and content CIDs match
the package and CLI projections byte-for-byte after transport-only fields are
stripped.

Import failure is fail-closed: this module will not register success/no-op
callables when the package engine cannot be imported.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Final, Mapping

try:
    from ipfs_kit_py import graphrag as _graphrag
except Exception as exc:  # pragma: no cover
    raise ImportError(
        "graphrag_tools cannot import the canonical package engine; "
        "MCP++ must not advertise success/no-op GraphRAG tools"
    ) from exc

try:
    from ..tool_metadata import tool_metadata
except Exception:  # optional decorator; tools remain usable without it
    def tool_metadata(**_kwargs):  # type: ignore[misc]
        def decorator(func):
            return func

        return decorator


MCPGraphRAGTools_V1: Final[str] = "ipfs_kit_py/graphrag/mcp-tools@1"
GRAPHRAG_TOOL_CATEGORY: Final[str] = "graphrag_tools"

# Public MCP tool names (category/name form used by hierarchical managers).
TOOL_OPEN: Final[str] = "graphrag_open"
TOOL_APPLY: Final[str] = "graphrag_apply"
TOOL_DELETE: Final[str] = "graphrag_delete"
TOOL_REHYDRATE: Final[str] = "graphrag_rehydrate"
TOOL_REBUILD: Final[str] = "graphrag_rebuild"
TOOL_VERSION_HISTORY: Final[str] = "graphrag_version_history"
TOOL_CURRENT: Final[str] = "graphrag_current_content"
TOOL_VECTOR_SEARCH: Final[str] = "graphrag_vector_search"
TOOL_HYBRID_SEARCH: Final[str] = "graphrag_hybrid_search"
TOOL_PROJECTION: Final[str] = "graphrag_projection"

_TOOL_TO_OPERATION: Final[Mapping[str, str]] = {
    TOOL_OPEN: _graphrag.OP_OPEN,
    TOOL_APPLY: _graphrag.OP_APPLY,
    TOOL_DELETE: _graphrag.OP_DELETE,
    TOOL_REHYDRATE: _graphrag.OP_REHYDRATE,
    TOOL_REBUILD: _graphrag.OP_REBUILD,
    TOOL_VERSION_HISTORY: _graphrag.OP_VERSION_HISTORY,
    TOOL_CURRENT: _graphrag.OP_CURRENT,
    TOOL_VECTOR_SEARCH: _graphrag.OP_VECTOR_SEARCH,
    TOOL_HYBRID_SEARCH: _graphrag.OP_HYBRID_SEARCH,
    TOOL_PROJECTION: _graphrag.OP_PROJECTION,
}


def _tool_descriptor(name: str, operation: str, summary: str) -> dict[str, Any]:
    request = _graphrag.request_schema_for(operation)
    return {
        "name": f"{GRAPHRAG_TOOL_CATEGORY}/{name}",
        "description": summary,
        "operation_id": operation,
        "version": 1,
        "request_schema": _graphrag.GRAPHRAG_REQUEST_SCHEMA,
        "result_schema": _graphrag.GRAPHRAG_RESULT_SCHEMA,
        "error_schema": _graphrag.GRAPHRAG_ERROR_SCHEMA,
        "capability": operation,
        "support_tier": "production",
        "access_requirement": "public",
        "inputSchema": {
            "type": "object",
            "required": ["request"],
            "properties": {
                "request": request,
                "context": {"type": "object", "default": {}},
            },
            "additionalProperties": False,
        },
        "response_schema": _graphrag.GRAPHRAG_RESULT_SCHEMA,
        "operation_request_fields": request["fields"],
    }


def list_tool_descriptors() -> list[dict[str, Any]]:
    """Return MCP tools/list descriptors for every GraphRAG operation."""

    summaries = {
        TOOL_OPEN: "Open/rehydrate a durable GraphRAG ledger and projection",
        TOOL_APPLY: "Append an immutable GraphRAG content transition",
        TOOL_DELETE: "Tombstone GraphRAG content (no resurrection)",
        TOOL_REHYDRATE: "Rebuild projection from durable records after restart",
        TOOL_REBUILD: "Clean rebuild of the GraphRAG projection",
        TOOL_VERSION_HISTORY: "List admitted versions for a document",
        TOOL_CURRENT: "Return the current content record for a document",
        TOOL_VECTOR_SEARCH: "Exact or ANN vector search (non-stub, advisory ranking)",
        TOOL_HYBRID_SEARCH: "Deterministic hybrid vector+lexical search (non-stub)",
        TOOL_PROJECTION: "Return current projection identity and membership",
    }
    return [
        _tool_descriptor(name, operation, summaries[name])
        for name, operation in _TOOL_TO_OPERATION.items()
    ]


def call_tool(name: str, arguments: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Synchronous MCP tools/call entrypoint."""

    if not isinstance(name, str) or not name:
        return _graphrag.mcp_call(
            _graphrag.OP_OPEN,
            {"root": "", "manifest": {}},
        )  # will fail closed via admission; kept for shape
    short = name.split("/")[-1]
    operation = _TOOL_TO_OPERATION.get(short) or _TOOL_TO_OPERATION.get(name)
    if operation is None:
        return {
            "schema": _graphrag.GRAPHRAG_RESULT_SCHEMA,
            "contract_version": _graphrag.CONTRACT_VERSION,
            "success": False,
            "operation": name,
            "request_schema": _graphrag.GRAPHRAG_REQUEST_SCHEMA,
            "result_schema": _graphrag.GRAPHRAG_RESULT_SCHEMA,
            "error_schema": _graphrag.GRAPHRAG_ERROR_SCHEMA,
            "result": None,
            "error": {
                "schema": _graphrag.GRAPHRAG_ERROR_SCHEMA,
                "contract_version": _graphrag.CONTRACT_VERSION,
                "code": "UnknownTool",
                "category": "request",
                "message": f"unknown GraphRAG tool: {name}",
                "operation": name,
                "retryable": False,
            },
            "content_cid": None,
            "generation_id": None,
            "transport": "mcp",
            "request_id": "unknown-tool",
        }
    body: dict[str, Any] = {}
    if arguments:
        if "request" in arguments and isinstance(arguments["request"], Mapping):
            body = dict(arguments["request"])
        else:
            body = dict(arguments)
    return _graphrag.mcp_call(operation, body)


async def call_tool_async(
    name: str, arguments: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    return call_tool(name, arguments)


def _make_async_tool(operation: str) -> Callable[..., Awaitable[dict[str, Any]]]:
    async def _tool(**kwargs: Any) -> dict[str, Any]:
        # Accept either flat kwargs or a nested request object.
        if "request" in kwargs and isinstance(kwargs["request"], Mapping):
            body = dict(kwargs["request"])
        else:
            body = {key: value for key, value in kwargs.items() if key != "context"}
        return _graphrag.mcp_call(operation, body)

    _tool.__name__ = operation.replace(".", "_")
    _tool.__doc__ = f"MCP tool for {operation}"
    return _tool


@tool_metadata(summary="Open/rehydrate durable GraphRAG ledger", tags=["graphrag", "read"])
async def graphrag_open(**kwargs: Any) -> dict[str, Any]:
    return await _make_async_tool(_graphrag.OP_OPEN)(**kwargs)


@tool_metadata(summary="Apply GraphRAG content transition", tags=["graphrag", "write"])
async def graphrag_apply(**kwargs: Any) -> dict[str, Any]:
    return await _make_async_tool(_graphrag.OP_APPLY)(**kwargs)


@tool_metadata(summary="Tombstone GraphRAG content", tags=["graphrag", "write"])
async def graphrag_delete(**kwargs: Any) -> dict[str, Any]:
    return await _make_async_tool(_graphrag.OP_DELETE)(**kwargs)


@tool_metadata(summary="Rehydrate GraphRAG projection", tags=["graphrag", "read"])
async def graphrag_rehydrate(**kwargs: Any) -> dict[str, Any]:
    return await _make_async_tool(_graphrag.OP_REHYDRATE)(**kwargs)


@tool_metadata(summary="Clean rebuild GraphRAG projection", tags=["graphrag", "write"])
async def graphrag_rebuild(**kwargs: Any) -> dict[str, Any]:
    return await _make_async_tool(_graphrag.OP_REBUILD)(**kwargs)


@tool_metadata(summary="GraphRAG version history", tags=["graphrag", "read"])
async def graphrag_version_history(**kwargs: Any) -> dict[str, Any]:
    return await _make_async_tool(_graphrag.OP_VERSION_HISTORY)(**kwargs)


@tool_metadata(summary="Current GraphRAG content", tags=["graphrag", "read"])
async def graphrag_current_content(**kwargs: Any) -> dict[str, Any]:
    return await _make_async_tool(_graphrag.OP_CURRENT)(**kwargs)


@tool_metadata(summary="GraphRAG vector search (non-stub)", tags=["graphrag", "search"])
async def graphrag_vector_search(**kwargs: Any) -> dict[str, Any]:
    return await _make_async_tool(_graphrag.OP_VECTOR_SEARCH)(**kwargs)


@tool_metadata(summary="GraphRAG hybrid search (non-stub)", tags=["graphrag", "search"])
async def graphrag_hybrid_search(**kwargs: Any) -> dict[str, Any]:
    return await _make_async_tool(_graphrag.OP_HYBRID_SEARCH)(**kwargs)


@tool_metadata(summary="GraphRAG projection identity", tags=["graphrag", "read"])
async def graphrag_projection(**kwargs: Any) -> dict[str, Any]:
    return await _make_async_tool(_graphrag.OP_PROJECTION)(**kwargs)


# Category -> tool name -> callable (same shape as mcp_server.tools.TOOL_GROUPS).
GRAPHRAG_TOOL_GROUP: dict[str, Callable[..., Awaitable[dict[str, Any]]]] = {
    TOOL_OPEN: graphrag_open,
    TOOL_APPLY: graphrag_apply,
    TOOL_DELETE: graphrag_delete,
    TOOL_REHYDRATE: graphrag_rehydrate,
    TOOL_REBUILD: graphrag_rebuild,
    TOOL_VERSION_HISTORY: graphrag_version_history,
    TOOL_CURRENT: graphrag_current_content,
    TOOL_VECTOR_SEARCH: graphrag_vector_search,
    TOOL_HYBRID_SEARCH: graphrag_hybrid_search,
    TOOL_PROJECTION: graphrag_projection,
}


class MCPGraphRAGTools:
    """MCP++-ready tool surface for GraphRAG.

    Registration into a broader ``TOOL_GROUPS`` map is explicit and fail-closed:
    a competing registration of the same category raises rather than winning
    silently.
    """

    schema: Final[str] = MCPGraphRAGTools_V1
    category: Final[str] = GRAPHRAG_TOOL_CATEGORY

    def __init__(self) -> None:
        # Binding proves the package engine is importable (import-time check).
        if _graphrag.GraphRAGService is None:
            raise ImportError("GraphRAGService unavailable; refusing MCP tool surface")
        self._tools = dict(GRAPHRAG_TOOL_GROUP)

    def list_tools(self) -> list[dict[str, Any]]:
        return list_tool_descriptors()

    def call(self, name: str, arguments: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return call_tool(name, arguments)

    async def call_async(
        self, name: str, arguments: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        return await call_tool_async(name, arguments)

    def register_into(self, tool_groups: dict[str, Any]) -> dict[str, Any]:
        """Insert GraphRAG tools into a TOOL_GROUPS-like mapping (fail-closed)."""

        if not isinstance(tool_groups, dict):
            raise TypeError("tool_groups must be a dict")
        if GRAPHRAG_TOOL_CATEGORY in tool_groups:
            existing = tool_groups[GRAPHRAG_TOOL_CATEGORY]
            if existing is not self._tools and existing != self._tools:
                raise ValueError(
                    f"competing registration for {GRAPHRAG_TOOL_CATEGORY}; "
                    "duplicate GraphRAG tool groups are rejected"
                )
        updated = dict(tool_groups)
        updated[GRAPHRAG_TOOL_CATEGORY] = dict(self._tools)
        return updated

    def hierarchical_names(self) -> tuple[str, ...]:
        return tuple(f"{GRAPHRAG_TOOL_CATEGORY}/{name}" for name in sorted(self._tools))


def register_graphrag_tools(tool_groups: dict[str, Any] | None = None) -> dict[str, Any]:
    """Register GraphRAG tools into an MCP++ tool group map."""

    return MCPGraphRAGTools().register_into(dict(tool_groups or {}))


def mcpp_includes_graphrag(tool_groups: Mapping[str, Any]) -> bool:
    """Return True when a tool group map includes the canonical GraphRAG tools."""

    group = tool_groups.get(GRAPHRAG_TOOL_CATEGORY)
    if not isinstance(group, Mapping):
        return False
    required = set(GRAPHRAG_TOOL_GROUP)
    return required.issubset(set(group))


__all__ = [
    "MCPGraphRAGTools",
    "MCPGraphRAGTools_V1",
    "GRAPHRAG_TOOL_GROUP",
    "GRAPHRAG_TOOL_CATEGORY",
    "list_tool_descriptors",
    "call_tool",
    "call_tool_async",
    "register_graphrag_tools",
    "mcpp_includes_graphrag",
    "graphrag_open",
    "graphrag_apply",
    "graphrag_delete",
    "graphrag_rehydrate",
    "graphrag_rebuild",
    "graphrag_version_history",
    "graphrag_current_content",
    "graphrag_vector_search",
    "graphrag_hybrid_search",
    "graphrag_projection",
]
