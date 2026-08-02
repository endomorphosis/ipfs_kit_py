"""ipfs_kit_py MCP++ server.

Backwards-compatible MCP JSON-RPC (initialize, tools/list, tools/call) plus the
hierarchical meta-tools. Transports: stdio (default), HTTP via Hypercorn+Trio,
and optional libp2p P2P. Runtime is anyio (trio backend), so all surfaces share
one async core.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict

import anyio

from . import mcplusplus
from .hierarchical_tool_manager import HierarchicalToolManager
from .mcplusplus.event_dag import EventDAGStore

PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "ipfs_kit_py-mcpplusplus", "version": "0.1.0"}


def _profile_g_rest_binding(http_method: str, path: str):
    """Resolve normative Profile G REST paths without changing wire semantics."""
    static = {
        ("GET", "/mcp/risk/profile"): "mcp++/risk/profile",
        ("POST", "/mcp/goals"): "mcp++/goals/create", ("GET", "/mcp/goals"): "mcp++/goals/list",
        ("POST", "/mcp/tasks"): "mcp++/tasks/create", ("GET", "/mcp/tasks"): "mcp++/tasks/list",
        ("GET", "/mcp/tasks/ready"): "mcp++/tasks/ready",
        ("POST", "/mcp/risk/assess"): "mcp++/risk/assess", ("GET", "/mcp/risk/evidence"): "mcp++/risk/evidence",
        ("GET", "/mcp/risk/history"): "mcp++/risk/history", ("POST", "/mcp/neighborhood/query"): "mcp++/neighborhood/query",
        ("POST", "/mcp/neighborhood/attest"): "mcp++/neighborhood/attest", ("GET", "/mcp/schedule/frontier"): "mcp++/schedule/frontier",
        ("POST", "/mcp/schedule/proposals"): "mcp++/schedule/propose", ("POST", "/mcp/schedule/claims"): "mcp++/schedule/claim",
        ("POST", "/mcp/schedule/resolutions"): "mcp++/schedule/resolve", ("POST", "/mcp/schedule/reconcile"): "mcp++/schedule/reconcile",
    }
    method = static.get((http_method, path))
    if method:
        return method, {}
    patterns = (
        ("GET", r"/mcp/goals/([^/]+)$", "mcp++/goals/get", "goal_cid"),
        ("POST", r"/mcp/goals/([^/]+)/(decompose|select)$", "goals", "goal_cid"),
        ("GET", r"/mcp/tasks/([^/]+)$", "mcp++/tasks/get", "task_cid"),
        ("GET", r"/mcp/schedule/status/([^/]+)$", "mcp++/schedule/status", "task_cid"),
        ("POST", r"/mcp/schedule/claims/([^/]+)/(renew|release)$", "schedule", "claim_cid"),
    )
    for verb, pattern, rpc, key in patterns:
        match = re.fullmatch(pattern, path) if verb == http_method else None
        if match:
            method = f"mcp++/{rpc}/{match.group(2)}" if rpc in {"goals", "schedule"} else rpc
            return method, {key: match.group(1)}
    return None


def _agent_supervisor_rest_binding(http_method: str, path: str):
    """Resolve the kit-owned Agent Supervisor immutable-receipt route."""
    if http_method in {"GET", "POST"} and path == "/mcp/agent-supervisor/receipts":
        return "agent_supervisor.receipts.read", {}
    match = re.fullmatch(r"/mcp/agent-supervisor/receipts/([^/]+)", path)
    if http_method == "GET" and match:
        from urllib.parse import unquote
        return "agent_supervisor.receipts.read", {"receipt_ids": [unquote(match.group(1))]}
    return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class MCPServer:
    def __init__(self, receipt_resolver: Any = None) -> None:
        self.tm = HierarchicalToolManager()
        # Do not let the default EventDAGStore location leak mutable state
        # between server instances.  Deployments that need durable provenance
        # opt in with a directory managed by their runtime environment.
        configured_dag_directory = os.environ.get("MCPPLUSPLUS_EVENT_DAG_DIR")
        self._dag_directory: tempfile.TemporaryDirectory[str] | None = None
        if configured_dag_directory:
            self._dag = EventDAGStore(storage_dir=configured_dag_directory)
        else:
            self._dag_directory = tempfile.TemporaryDirectory(prefix="ipfs-kit-mcpp-dag-")
            self._dag = EventDAGStore(storage_dir=self._dag_directory.name)
        from .agent_supervisor_receipts import AgentSupervisorReceiptResolver
        self._agent_supervisor_receipts = receipt_resolver or AgentSupervisorReceiptResolver()

    async def handle(self, msg: Dict[str, Any]):
        method = msg.get("method")
        params = msg.get("params") or {}
        is_notification = "id" not in msg
        # JSON-RPC notifications (no id) — e.g. the MCP `notifications/initialized`
        # handshake ack — are processed for side effects but MUST NOT be replied to.
        if is_notification:
            try:
                await self._route(method, params, notification=True)
            except Exception:
                pass
            return None
        mid = msg.get("id")
        try:
            result = await self._route(method, params)
            return {"jsonrpc": "2.0", "id": mid, "result": result}
        except Exception as e:
            from .mcplusplus.profile_g_transport import ERROR_NUMBERS
            wire_code = ERROR_NUMBERS.get(getattr(e, "code", ""), -32000)
            error = {"code": wire_code, "message": str(e)}
            if getattr(e, "code", None):
                error["data"] = e.data()
            return {"jsonrpc": "2.0", "id": mid, "error": error}

    async def _route(self, method: str, params: Dict[str, Any], notification: bool = False) -> Any:
        if notification or (method or "").startswith("notifications/"):
            # Known MCP lifecycle notifications (initialized, cancelled, …) are
            # accepted as no-ops; unknown ones are ignored rather than erroring.
            return None
        if method == "initialize":
            requested = params.get("capabilities", {}).get("experimental", {})
            experimental = {"mcp++": mcplusplus.get_capabilities()}
            if requested.get("mcp++/event-dag") is True:
                experimental["mcp++/event-dag"] = True
            if requested.get("mcp++/risk-scheduling") is True:
                from .mcplusplus.profile_g_transport import get_dispatcher
                experimental["mcp++/risk-scheduling"] = get_dispatcher().metadata
            return {
                "protocolVersion": PROTOCOL_VERSION,
                "serverInfo": SERVER_INFO,
                "capabilities": {
                    "tools": {},
                    "experimental": experimental,
                    # Profile D is implemented by the built-in deterministic
                    # evaluator, so advertise it independently of optional
                    # accelerator or HTTP dependencies.
                    "mcpPlusPlusProfiles": [
                        "mcp++/event-dag",
                        "mcp++/deontic-policy",
                        "mcp++/risk-scheduling",
                    ],
                },
                "profile_metadata": {
                    "mcp++/event-dag": self._dag.profile_metadata(),
                    "agent_supervisor.receipts.read": {
                        "owner": "ipfs_kit_py", "access": "read",
                        "transports": ["mcp", "mcp++", "libp2p"],
                    },
                },
            }
        if method == "tools/list":
            from .agent_supervisor_receipts import descriptor
            return {"tools": [*self.tm.all_tool_schemas(), descriptor()]}
        if method == "mcp++/interfaces":
            return {"interfaces": self._interface_descriptors()}
        if method == "agent_supervisor.receipts.read":
            return self._agent_supervisor_receipts.read(params)
        if method == "mcp++/dag/frontier":
            frontier = self._dag.frontier()
            return {**frontier, "count": self._dag.history(limit=1)["count"]}
        if method in ("mcp++/ucan/validate", "mcp++/ucan/delegate"):
            from .mcplusplus import delegation
            return delegation.validate_raw_delegation_chain(
                raw_chain=params.get("chain") or params.get("delegations") or [],
                resource=params.get("resource", "*"),
                ability=params.get("ability", "*"),
                actor=params.get("actor", ""),
            )
        if method == "mcp++/policy/evaluate":
            from .mcplusplus import delegation
            return delegation.evaluate_policy(
                tool=params.get("tool", ""),
                deny=params.get("deny", []),
                risk=float(params.get("risk", 0.0)),
                threshold=float(params.get("threshold", 0.7)),
            )
        if method.startswith(("mcp++/goals/", "mcp++/tasks/", "mcp++/risk/", "mcp++/neighborhood/", "mcp++/schedule/")):
            from .mcplusplus.profile_g_transport import get_dispatcher
            return get_dispatcher().dispatch(method, params)
        if method == "tools/call":
            name = params.get("name", "")
            args = params.get("arguments") or {}
            if name == "agent_supervisor.receipts.read":
                receipt_params = dict(args) if isinstance(args, dict) else args
                if isinstance(receipt_params, dict) and params.get("correlation_id") is not None:
                    receipt_params.setdefault("correlation_id", params["correlation_id"])
                return self._agent_supervisor_receipts.read(receipt_params)
            envelope = params.get("_mcppp_envelope")
            if envelope is not None:
                err = mcplusplus.validate_packet(envelope)
                if err:
                    raise ValueError(f"mcp++ envelope invalid: {err}")
            self._repair_minimal_ipfs_backend()
            category, _, tool = name.rpartition("/") if "/" in name else self._resolve(name)
            result = await self.tm.dispatch(category, tool, args)
            if params.get("profile_b") or envelope is not None:
                from .mcplusplus import artifacts
                recent_events = self._dag.history(limit=1)["events"]
                parents = [recent_events[0]["event_cid"]] if recent_events else []
                meta = artifacts.envelope_from_payloads(
                    interface_cid=self._interface_cid(),
                    input_payload={"tool": name, "arguments": args},
                    tool=name,
                    output_payload=result if isinstance(result, dict) else {"value": result},
                    correlation_id=str(params.get("correlation_id", "")),
                    parents=parents,
                )
                node = {"event_cid": meta["event_cid"], "timestamp": _now_iso(), **meta["event"]}
                self._dag.append(node)
                if isinstance(result, dict):
                    result = {**result, "_mcppp": meta}
                else:
                    result = {"value": result, "_mcppp": meta}
            return result
        if method == "ping":
            return {}
        raise ValueError(f"unknown method: {method}")

    @staticmethod
    def _repair_minimal_ipfs_backend() -> None:
        """Bridge the minimal client's unpin spelling without changing full backends.

        The bundled minimal client exposes ``ipfs_pin_rm`` while the legacy
        tool wrapper calls ``pin_rm`` on a nested IPFS backend.  This adapter
        is deliberately narrow: a backend that already provides ``pin_rm``
        remains untouched.
        """
        from . import core_operations

        kit = core_operations.get_kit()
        backend = getattr(kit, "ipfs", None)
        minimal_unpin = getattr(backend, "ipfs_pin_rm", None)
        if callable(getattr(backend, "pin_rm", None)) or not callable(minimal_unpin):
            return

        def ipfs_pin_rm(cid: str, recursive: bool = True, **kwargs: Any) -> Any:
            return minimal_unpin(cid)

        setattr(kit, "ipfs_pin_rm", ipfs_pin_rm)

    def _resolve(self, tool: str):
        for cat, tools in self.tm._groups.items():
            if tool in tools:
                return cat, "/", tool
        return "", "/", tool

    def _interface_cid(self) -> str:
        """Kubo CIDv1 over the canonical interface descriptor set (Profile A)."""
        from .mcplusplus import artifacts
        return artifacts.compute_artifact_cid({"interfaces": self._interface_descriptors()})

    def _interface_descriptors(self):
        """Profile A: canonical interface descriptors derived from the registry."""
        out = []
        for s in self.tm.all_tool_schemas():
            out.append({
                "namespace": f"ipfs_kit/{s['category']}",
                "name": s["name"],
                "input_schema": s.get("inputSchema", {}),
                "output_schema": {"type": "object"},
                "errors": ["IPFSError", "ToolNotFound"],
                "semantic_tags": s.get("tags", []),
                "compatibility": {"mcp": True, "mcp++": True},
            })
        from .agent_supervisor_receipts import descriptor
        out.append(descriptor())
        return out


async def serve_stdio() -> None:
    server = MCPServer()
    stdin = anyio.wrap_file(sys.stdin)
    async for line in stdin:
        line = line.strip()
        if not line:
            continue
        resp = await server.handle(json.loads(line))
        if resp is None:  # notification — no reply
            continue
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()


def create_http_app(server: MCPServer | None = None):
    """Build the shared ASGI application, allowing transport contract tests to inject storage."""
    server = server or MCPServer()

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
        path = scope.get("path", "")
        binding = (_agent_supervisor_rest_binding(scope.get("method", "GET"), path)
                   or _profile_g_rest_binding(scope.get("method", "GET"), path))
        if binding is not None:
            from urllib.parse import parse_qsl
            method, path_params = binding
            params = dict(parse_qsl(scope.get("query_string", b"").decode()))
            decoded = None
            if body:
                decoded = json.loads(body)
                if not isinstance(decoded, dict):
                    decoded = {}
            is_jsonrpc = bool(decoded and decoded.get("jsonrpc") == "2.0")
            if is_jsonrpc:
                nested = decoded.get("params")
                if isinstance(nested, dict):
                    params.update(nested)
            elif decoded:
                params.update(decoded)
            params.update(path_params)
            rpc_message = {"jsonrpc": "2.0", "method": method, "params": params}
            if not is_jsonrpc or "id" in decoded:
                rpc_message["id"] = decoded.get("id") if is_jsonrpc else 1
            resp = await server.handle(rpc_message)
            if not is_jsonrpc:
                resp = resp.get("result", resp.get("error")) if isinstance(resp, dict) else resp
        else:
            resp = await server.handle(json.loads(body or b"{}"))
        if resp is None:  # JSON-RPC notification — HTTP 202, no body
            await send({"type": "http.response.start", "status": 202, "headers": []})
            await send({"type": "http.response.body", "body": b""})
            return
        data = json.dumps(resp).encode()
        await send({"type": "http.response.start", "status": 200,
                    "headers": [(b"content-type", b"application/json")]})
        await send({"type": "http.response.body", "body": data})

    return app


async def serve_http(host: str = "127.0.0.1", port: int = 8004) -> None:
    from hypercorn.config import Config
    from hypercorn.trio import serve  # trio worker

    cfg = Config()
    cfg.bind = [f"{host}:{port}"]
    await serve(create_http_app(), cfg)


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
