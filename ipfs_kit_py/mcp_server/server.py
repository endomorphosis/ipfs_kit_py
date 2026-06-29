"""ipfs_kit_py MCP++ server.

Backwards-compatible MCP JSON-RPC (initialize, tools/list, tools/call) plus the
hierarchical meta-tools. Transports: stdio (default), HTTP via Hypercorn+Trio,
and optional libp2p P2P. Runtime is anyio (trio backend), so all surfaces share
one async core.
"""
from __future__ import annotations

import json
import sys
from typing import Any, Dict

import anyio

from . import mcplusplus
from .hierarchical_tool_manager import HierarchicalToolManager

PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "ipfs_kit_py-mcpplusplus", "version": "0.1.0"}


class MCPServer:
    def __init__(self) -> None:
        self.tm = HierarchicalToolManager()

    async def handle(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        mid = msg.get("id")
        method = msg.get("method")
        params = msg.get("params") or {}
        try:
            result = await self._route(method, params)
            return {"jsonrpc": "2.0", "id": mid, "result": result}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32000, "message": str(e)}}

    async def _route(self, method: str, params: Dict[str, Any]) -> Any:
        if method == "initialize":
            return {
                "protocolVersion": PROTOCOL_VERSION,
                "serverInfo": SERVER_INFO,
                "capabilities": {"tools": {}, "experimental": {"mcp++": mcplusplus.get_capabilities()}},
            }
        if method == "tools/list":
            return {"tools": self.tm.all_tool_schemas()}
        if method == "tools/call":
            name = params.get("name", "")
            args = params.get("arguments") or {}
            envelope = params.get("_mcppp_envelope")
            if envelope is not None:
                err = mcplusplus.validate_packet(envelope)
                if err:
                    raise ValueError(f"mcp++ envelope invalid: {err}")
            category, _, tool = name.rpartition("/") if "/" in name else self._resolve(name)
            return await self.tm.dispatch(category, tool, args)
        if method == "ping":
            return {}
        raise ValueError(f"unknown method: {method}")

    def _resolve(self, tool: str):
        for cat, tools in self.tm._groups.items():
            if tool in tools:
                return cat, "/", tool
        return "", "/", tool


async def serve_stdio() -> None:
    server = MCPServer()
    stdin = anyio.wrap_file(sys.stdin)
    async for line in stdin:
        line = line.strip()
        if not line:
            continue
        resp = await server.handle(json.loads(line))
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()


async def serve_http(host: str = "127.0.0.1", port: int = 8004) -> None:
    from hypercorn.config import Config
    from hypercorn.trio import serve  # trio worker

    server = MCPServer()

    async def app(scope, receive, send):
        if scope["type"] == "lifespan":
            while True:
                ev = await receive()
                if ev["type"] == "lifespan.startup":
                    await send({"type": "lifespan.startup.complete"})
                elif ev["type"] == "lifespan.shutdown":
                    await send({"type": "lifespan.shutdown.complete"})
                    return
        if scope["type"] != "http":
            return
        body = b""
        while True:
            ev = await receive()
            body += ev.get("body", b"")
            if not ev.get("more_body"):
                break
        resp = await server.handle(json.loads(body or b"{}"))
        data = json.dumps(resp).encode()
        await send({"type": "http.response.start", "status": 200,
                    "headers": [(b"content-type", b"application/json")]})
        await send({"type": "http.response.body", "body": data})

    cfg = Config()
    cfg.bind = [f"{host}:{port}"]
    await serve(app, cfg)


async def serve_p2p() -> None:
    from .p2p_transport import serve_p2p as _serve
    server = MCPServer()
    await _serve(server.handle)


def main(argv=None) -> None:
    import argparse
    p = argparse.ArgumentParser("ipfs-kit-mcp")
    p.add_argument("--transport", choices=["stdio", "http", "p2p"], default="stdio")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8004)
    a = p.parse_args(argv)
    if a.transport == "http":
        anyio.run(serve_http, a.host, a.port, backend="trio")
    elif a.transport == "p2p":
        anyio.run(serve_p2p, backend="trio")
    else:
        anyio.run(serve_stdio, backend="trio")


if __name__ == "__main__":
    main()
