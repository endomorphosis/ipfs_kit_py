"""ipfs_kit_py MCP++ server.

Backwards-compatible MCP JSON-RPC (initialize, tools/list, tools/call) plus the
hierarchical meta-tools. Transports: stdio (default), HTTP via Hypercorn+Trio,
and optional libp2p P2P. Runtime is anyio (trio backend), so all surfaces share
one async core.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict

import anyio

from . import mcplusplus
from .authorization import AuthorizationDenied, AuthorizationGate, _digest
from .hierarchical_tool_manager import HierarchicalToolManager
from .mcplusplus.event_dag import EventDAGStore
from .mcplusplus.revocation import RevocationLedger
from .mcplusplus.ucan import UCANVerifier
from ..mcp.profile_d_policy import get_profile_d_policy_provider
from .tools import (
    resolve_mcp_route,
    resolve_rest_route,
    resolve_tool_route,
    supported_mcpp_profiles,
)

PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "ipfs_kit_py-mcpplusplus", "version": "0.1.0"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class MCPServer:
    def __init__(
        self,
        receipt_resolver: Any = None,
        *,
        event_dag: EventDAGStore | None = None,
        policy_provider: Any | None = None,
        ucan_ledger: Any | None = None,
        ucan_verifier: Any | None = None,
        envelope_validator: Any | None = None,
        validator_available: bool | None = None,
        authorization_gate: AuthorizationGate | None = None,
    ) -> None:
        """Create a server with optional injected receipt and provenance stores.

        ``event_dag`` is deliberately explicit so embedders and transport
        tests can share a durable event history without relying on process
        environment state.  When omitted, the durable EventDAGStore default
        is used; deployments may override its location with
        ``MCPPLUSPLUS_EVENT_DAG_DIR``.
        """
        self.tm = HierarchicalToolManager()
        configured_dag_directory = os.environ.get("MCPPLUSPLUS_EVENT_DAG_DIR")
        if event_dag is not None:
            self._dag = event_dag
        elif configured_dag_directory:
            self._dag = EventDAGStore(storage_dir=configured_dag_directory)
        else:
            self._dag = EventDAGStore()
        self.policy_provider = (
            policy_provider
            if policy_provider is not None
            else get_profile_d_policy_provider()
        )
        self.ucan_ledger = (
            ucan_ledger
            if ucan_ledger is not None
            else RevocationLedger(self._dag.root / "ucan-revocation-ledger.json")
        )
        self.ucan_verifier = (
            ucan_verifier
            if ucan_verifier is not None
            else UCANVerifier(ledger=self.ucan_ledger)
        )
        if validator_available is None:
            validator_available = bool(mcplusplus.HAVE_VALIDATOR)
        if envelope_validator is None and validator_available:
            envelope_validator = mcplusplus.validate_packet
        self.authorization_gate = (
            authorization_gate
            if authorization_gate is not None
            else AuthorizationGate(
                policy_provider=self.policy_provider,
                ucan_verifier=self.ucan_verifier,
                ledger=self.ucan_ledger,
                audit_store=self._dag,
                envelope_validator=envelope_validator,
                validator_available=validator_available,
            )
        )
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
        route = resolve_mcp_route(method or "")
        if notification or route == "notification":
            # Known MCP lifecycle notifications (initialized, cancelled, …) are
            # accepted as no-ops; unknown ones are ignored rather than erroring.
            return None
        if route == "initialize":
            requested = params.get("capabilities", {}).get("experimental", {})
            capability_map = dict(mcplusplus.get_capabilities())
            profile_capabilities = dict(capability_map.get("profiles", {}))
            profile_capabilities["D_policy"] = bool(
                getattr(self.policy_provider, "available", False)
            )
            capability_map["profiles"] = profile_capabilities
            profiles = supported_mcpp_profiles(capability_map)
            experimental = {"mcp++": capability_map}
            if requested.get("mcp++/event-dag") is True and "mcp++/event-dag" in profiles:
                experimental["mcp++/event-dag"] = True
            if requested.get("mcp++/risk-scheduling") is True and "mcp++/risk-scheduling" in profiles:
                from .mcplusplus.profile_g_transport import get_dispatcher
                experimental["mcp++/risk-scheduling"] = get_dispatcher().metadata
            profile_metadata = {
                "agent_supervisor.receipts.read": {
                    "owner": "ipfs_kit_py", "access": "read",
                    "transports": ["mcp", "mcp++", "libp2p"],
                },
            }
            provider_metadata = getattr(self.policy_provider, "metadata", None)
            if callable(provider_metadata):
                profile_metadata["mcp++/deontic-policy"] = dict(provider_metadata())
            else:
                profile_metadata["mcp++/deontic-policy"] = {
                    "provider": type(self.policy_provider).__name__,
                    "available": bool(getattr(self.policy_provider, "available", False)),
                    "fail_closed": True,
                }
            if "mcp++/event-dag" in profiles:
                profile_metadata["mcp++/event-dag"] = self._dag.profile_metadata()
            return {
                "protocolVersion": PROTOCOL_VERSION,
                "serverInfo": SERVER_INFO,
                "capabilities": {
                    "tools": {},
                    "experimental": experimental,
                    "mcpPlusPlusProfiles": profiles,
                },
                "profile_metadata": profile_metadata,
            }
        if route == "tools_list":
            from .agent_supervisor_receipts import descriptor
            return {"tools": [*self.tm.all_tool_schemas(), descriptor()]}
        if route == "interfaces":
            return {"interfaces": self._interface_descriptors()}
        if route == "agent_supervisor_receipts":
            return self._agent_supervisor_receipts.read(params)
        if route == "dag_frontier":
            frontier = self._dag.frontier()
            return {**frontier, "count": self._dag.history(limit=1)["count"]}
        if route == "ucan":
            if self.ucan_ledger is None or not bool(getattr(self.ucan_ledger, "available", False)):
                return {"allowed": False, "valid": False, "reason": "ledger_unavailable"}
            if self.ucan_verifier is None or not callable(getattr(self.ucan_verifier, "verify", None)):
                return {"allowed": False, "valid": False, "reason": "ucan_verifier_unavailable"}
            try:
                verified = self.ucan_verifier.verify(
                    params.get("chain") or params.get("delegations") or params.get("ucans") or params.get("token"),
                    expected_resource=params.get("resource"),
                    expected_ability=params.get("ability"),
                    expected_audience=params.get("actor"),
                    request_bounds=params.get("request_bounds") or {},
                )
            except Exception:
                return {"allowed": False, "valid": False, "reason": "ucan_verification_unavailable"}
            receipt = getattr(verified, "to_receipt", None)
            if callable(receipt):
                return receipt()
            return {
                "allowed": bool(getattr(verified, "allowed", False)),
                "valid": bool(getattr(verified, "allowed", False)),
                "reason": str(getattr(verified, "reason", "denied")),
            }
        if route == "policy":
            if not bool(getattr(self.policy_provider, "available", False)):
                raise AuthorizationDenied("policy_provider_unavailable")
            try:
                return dict(self.policy_provider.evaluate(
                    actor=params.get("actor", "anonymous"),
                    action=params.get("action") or params.get("tool") or "",
                    resource=params.get("resource"),
                    policy=params.get("policy"),
                    policy_text=params.get("policy_text"),
                    evaluated_at=params.get("evaluated_at"),
                    intent_cid=params.get("intent_cid"),
                    request_zkp_certificate=bool(params.get("request_zkp_certificate", True)),
                ))
            except AuthorizationDenied:
                raise
            except Exception as exc:
                raise AuthorizationDenied("policy_provider_unavailable") from exc
        if route == "profile_g":
            from .mcplusplus.profile_g_transport import get_dispatcher
            return get_dispatcher().dispatch(method, params)
        if route == "tools_call":
            name = params.get("name", "")
            args = params.get("arguments") or {}
            if not isinstance(name, str) or not name:
                raise ValueError("tools/call requires a non-empty tool name")
            if not isinstance(args, dict):
                raise ValueError("tools/call arguments must be an object")
            decision = self.authorization_gate.authorize(
                tool=name,
                arguments=args,
                envelope=params.get("_mcppp_envelope"),
            )
            try:
                if name == "agent_supervisor.receipts.read":
                    receipt_params = dict(args)
                    if params.get("correlation_id") is not None:
                        receipt_params.setdefault("correlation_id", params["correlation_id"])
                    result = self._agent_supervisor_receipts.read(receipt_params)
                else:
                    self._repair_minimal_ipfs_backend()
                    tool_route = resolve_tool_route(name)
                    if tool_route is None:
                        raise ValueError(f"unknown tool: {name}")
                    category, tool = tool_route
                    result = await self.tm.dispatch(category, tool, args)
                if params.get("profile_b"):
                    from .mcplusplus import artifacts
                    recent_events = self._dag.history(limit=1)["events"]
                    parents = [recent_events[0]["event_cid"]] if recent_events else []
                    meta = artifacts.envelope_from_payloads(
                        interface_cid=self._interface_cid(),
                        input_payload={
                            "tool": name,
                            "envelope_digest": decision.envelope_digest,
                            "arguments_digest": _digest(args),
                        },
                        tool=name,
                        output_payload={"result_digest": _digest(result)},
                        correlation_id=decision.request_id,
                        parents=parents,
                    )
                    node = {"event_cid": meta["event_cid"], "timestamp": _now_iso(), **meta["event"]}
                    self._dag.append(node)
                    if isinstance(result, dict):
                        result = {**result, "_mcppp": meta}
                    else:
                        result = {"value": result, "_mcppp": meta}
                if isinstance(result, dict):
                    result = {**result, "_authorization": decision.public()}
                else:
                    result = {"value": result, "_authorization": decision.public()}
                self.authorization_gate.record_effect(decision, result)
                return result
            except Exception as exc:
                self.authorization_gate.record_effect(
                    decision,
                    {"outcome": "error", "error_type": type(exc).__name__},
                )
                raise
        if route == "ping":
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
        binding = resolve_rest_route(scope.get("method", "GET"), path)
        # Profile D is deliberately served by the same provider-backed MCP
        # route as JSON-RPC.  Keep this small transport alias here until the
        # registry can expose the canonical policy route directly.
        if binding is None and scope.get("method", "GET") == "POST" and path == "/mcp/policy/evaluate":
            binding = ("mcp++/policy/evaluate", {})
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
