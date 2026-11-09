"""Spec-conformant MCP / MCP++ JSON-RPC dispatch + hypercorn transport.

This is a small, self-contained, framework-light helper that gives any
FastAPI/Starlette application a single, standards-compliant MCP endpoint
(``POST /mcp``) implementing the base MCP handshake (``initialize``,
``notifications/initialized``, ``ping``, ``tools/list``, ``tools/call``)
so that *stock* MCP clients can connect.  It deliberately does **not**
replace existing REST routes — it is purely additive, satisfying the
MCP++ transport spec non-goal of "replacing existing MCP client<->server
transports".

It also exposes :func:`serve_hypercorn`, an anyio/trio-aware ASGI runner
that prefers Hypercorn (which supports both the asyncio and trio backends)
and falls back to uvicorn when Hypercorn is unavailable.  This is what lets
MCP++ servers honour the trio/anyio + hypercorn + libp2p stack while keeping
backwards compatibility with the base MCP protocol.

NOTE: This module is intentionally dependency-light and vendored verbatim
into ``ipfs_kit_py``, ``ipfs_datasets_py`` and ``ipfs_accelerate_py`` so the
three servers share one implementation instead of maintaining three.  Keep
the copies byte-identical; the canonical source lives in ``ipfs_kit_py``.
"""
from __future__ import annotations

import json
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union

# Base MCP protocol version advertised in the ``initialize`` handshake.
MCP_PROTOCOL_VERSION = "2024-11-05"

# JSON-RPC 2.0 error codes.
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

ToolsListFn = Callable[[], Union[List[Dict[str, Any]], Awaitable[List[Dict[str, Any]]]]]
ToolsCallFn = Callable[[str, Dict[str, Any]], Awaitable[Any]]


class MCPToolError(Exception):
    """Raised by a tools/call implementation to surface a JSON-RPC error."""

    def __init__(self, message: str, code: int = INTERNAL_ERROR, data: Any = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


async def _maybe_await(value: Any) -> Any:
    if hasattr(value, "__await__"):
        return await value
    return value


def _to_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, default=str)
    except Exception:
        return str(value)


class MCPJSONRPCHandler:
    """Dispatch base-MCP JSON-RPC envelopes to tool callables.

    Parameters
    ----------
    server_name / server_version:
        Reported via the ``initialize`` ``serverInfo`` block.
    list_tools:
        Returns the MCP tool catalog as a list of
        ``{"name", "description", "inputSchema"}`` dicts (sync or async).
    call_tool:
        ``async (name, arguments) -> result``.  Raise :class:`MCPToolError`
        for tool-level errors.  The returned value is wrapped into the MCP
        ``tools/call`` content shape.
    experimental_capabilities:
        Optional dict advertised under ``capabilities.experimental`` so
        MCP++ profile negotiation can be surfaced to clients.
    """

    def __init__(
        self,
        *,
        server_name: str,
        list_tools: ToolsListFn,
        call_tool: ToolsCallFn,
        server_version: str = "1.0.0",
        experimental_capabilities: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.server_name = server_name
        self.server_version = server_version
        self._list_tools = list_tools
        self._call_tool = call_tool
        self._experimental = experimental_capabilities or {}

    # -- public API ---------------------------------------------------------
    async def handle(self, payload: Any) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:
        """Handle a parsed JSON-RPC payload (single object or batch list).

        Returns the response object/list, or ``None`` when the request was a
        notification (or batch of only notifications) and no response is due.
        """
        if isinstance(payload, list):
            if not payload:
                return self._error(None, INVALID_REQUEST, "Empty batch")
            responses: List[Dict[str, Any]] = []
            for item in payload:
                resp = await self._dispatch_one(item)
                if resp is not None:
                    responses.append(resp)
            return responses or None
        return await self._dispatch_one(payload)

    # -- internals ----------------------------------------------------------
    async def _dispatch_one(self, msg: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(msg, dict):
            return self._error(None, INVALID_REQUEST, "Invalid Request")
        req_id = msg.get("id")
        method = msg.get("method")
        params = msg.get("params") or {}
        is_notification = "id" not in msg
        if not isinstance(method, str):
            return None if is_notification else self._error(req_id, INVALID_REQUEST, "Missing method")

        try:
            if method == "initialize":
                result = self._initialize_result()
            elif method in ("notifications/initialized", "initialized", "notifications/cancelled"):
                return None  # notifications -> no response
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                tools = await _maybe_await(self._list_tools())
                result = {"tools": list(tools or [])}
            elif method == "tools/call":
                result = await self._tools_call(params)
            else:
                if is_notification:
                    return None
                return self._error(req_id, METHOD_NOT_FOUND, f"Method not found: {method}")
        except MCPToolError as exc:
            if is_notification:
                return None
            return self._error(req_id, exc.code, exc.message, exc.data)
        except Exception as exc:  # pragma: no cover - defensive
            if is_notification:
                return None
            return self._error(req_id, INTERNAL_ERROR, str(exc))

        if is_notification:
            return None
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    def _initialize_result(self) -> Dict[str, Any]:
        return {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {
                "tools": {"listChanged": True},
                "experimental": self._experimental,
            },
            "serverInfo": {"name": self.server_name, "version": self.server_version},
        }

    async def _tools_call(self, params: Any) -> Dict[str, Any]:
        if not isinstance(params, dict):
            raise MCPToolError("Invalid params", INVALID_PARAMS)
        name = params.get("name")
        if not name or not isinstance(name, str):
            raise MCPToolError("Missing tool name", INVALID_PARAMS)
        arguments = params.get("arguments") or {}
        if not isinstance(arguments, dict):
            raise MCPToolError("'arguments' must be an object", INVALID_PARAMS)
        raw = await self._call_tool(name, arguments)
        return {
            "content": [{"type": "text", "text": _to_text(raw)}],
            "structuredContent": raw if isinstance(raw, (dict, list)) else None,
            "isError": False,
        }

    @staticmethod
    def _error(req_id: Any, code: int, message: str, data: Any = None) -> Dict[str, Any]:
        err: Dict[str, Any] = {"code": code, "message": message}
        if data is not None:
            err["data"] = data
        return {"jsonrpc": "2.0", "id": req_id, "error": err}


def register_mcp_jsonrpc(app: Any, handler: MCPJSONRPCHandler, paths=("/mcp",)) -> None:
    """Register the conformant JSON-RPC endpoint on a FastAPI/Starlette app.

    ``paths`` may include multiple mount points (e.g. ``("/mcp", "/")``) so
    legacy clients that POST JSON-RPC to the bare root keep working.
    """
    from starlette.requests import Request  # local import keeps this module import-light
    from starlette.responses import JSONResponse, Response

    async def _endpoint(request: Request) -> Response:
        try:
            body = await request.body()
            payload = json.loads(body) if body else None
        except Exception:
            return JSONResponse(
                MCPJSONRPCHandler._error(None, PARSE_ERROR, "Parse error"), status_code=200
            )
        if payload is None:
            return JSONResponse(
                MCPJSONRPCHandler._error(None, INVALID_REQUEST, "Empty request"), status_code=200
            )
        response = await handler.handle(payload)
        if response is None:
            # Notification(s) only: 202 Accepted with no body per MCP transport.
            return Response(status_code=202)
        return JSONResponse(response, status_code=200)

    for path in paths:
        app.add_route(path, _endpoint, methods=["POST"])


async def serve_hypercorn(
    app: Any,
    host: str,
    port: int,
    *,
    log_level: str = "info",
    shutdown_trigger: Optional[Callable[[], Awaitable[None]]] = None,
) -> None:
    """Serve an ASGI app, preferring Hypercorn (asyncio/trio aware).

    Detects the running async library via sniffio and selects the matching
    Hypercorn worker (trio vs asyncio).  Falls back to uvicorn if Hypercorn
    is not installed so the server still boots in minimal environments.
    """
    try:
        from hypercorn.config import Config
    except Exception:  # pragma: no cover - fallback path
        import uvicorn

        config = uvicorn.Config(app, host=host, port=port, log_level=log_level, lifespan="off")
        await uvicorn.Server(config).serve()
        return

    config = Config()
    config.bind = [f"{host}:{port}"]
    config.loglevel = log_level
    config.accesslog = "-" if log_level == "debug" else None

    backend = "asyncio"
    try:
        import sniffio

        backend = sniffio.current_async_library()
    except Exception:
        backend = "asyncio"

    if backend == "trio":
        from hypercorn.trio import serve as _serve
    else:
        from hypercorn.asyncio import serve as _serve

    kwargs: Dict[str, Any] = {}
    if shutdown_trigger is not None:
        kwargs["shutdown_trigger"] = shutdown_trigger
    await _serve(app, config, **kwargs)
