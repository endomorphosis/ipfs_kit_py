"""Contracts for the governed Iroh MCP and storage API surfaces."""

from __future__ import annotations

import json
from typing import Any

import fastapi
import httpx
import pytest

from ipfs_kit_py.iroh.governance import IrohOperationController, MemoryAuditSink
from ipfs_kit_py.mcp.servers.iroh_mcp_tools import IROH_MCP_TOOLS, handle_iroh_tool
from ipfs_kit_py.mcp.servers.unified_mcp_server import UnifiedMCPServer
from ipfs_kit_py.openapi_schema import get_openapi_schema
from ipfs_kit_py.storage_backends_api import storage_router


class Service:
    def __init__(self, _config: Any, calls: list[str]) -> None:
        self.calls = calls

    async def status(self) -> dict[str, Any]:
        self.calls.append("status")
        return {"running": False, "ready": False, "status": "stopped"}

    async def start(self) -> bool:
        self.calls.append("start")
        return True

    async def stop(self) -> bool:
        self.calls.append("stop")
        return True

    async def restart(self) -> bool:
        self.calls.append("restart")
        return True


def controller(calls: list[str]) -> IrohOperationController:
    return IrohOperationController(
        service_factory=lambda config: Service(config, calls),
        audit_sink=MemoryAuditSink(),
    )


def test_mcp_schemas_are_allowlisted_and_permission_separated() -> None:
    by_name = {tool["name"]: tool for tool in IROH_MCP_TOOLS}
    assert by_name["iroh_service_status"]["x-ipfs-kit-permission"] == "iroh.read"
    assert by_name["iroh_service_start"]["x-ipfs-kit-permission"] == "iroh.control"
    stop = by_name["iroh_service_stop"]
    assert stop["x-ipfs-kit-permission"] == "iroh.destructive"
    assert stop["annotations"]["destructiveHint"] is True
    assert stop["inputSchema"]["properties"]["confirm"]["const"] is True
    assert stop["inputSchema"]["additionalProperties"] is False


@pytest.mark.asyncio
async def test_unified_server_registers_and_dispatches_governed_tools(tmp_path) -> None:
    calls: list[str] = []
    server = UnifiedMCPServer(
        data_dir=str(tmp_path),
        auto_start_daemons=False,
        register_all_tools=True,
        iroh_permissions={"iroh.read"},
        iroh_controller=controller(calls),
    )
    listed = await server.handle_tools_list()
    names = {tool["name"] for tool in listed["tools"]}
    assert {"iroh_diagnostics", "iroh_service_status", "iroh_service_stop"} <= names

    response = await server.handle_tools_call(
        {"name": "iroh_service_status", "arguments": {"operation_id": "status-1"}}
    )
    payload = json.loads(response["content"][0]["text"])
    assert response["isError"] is False
    assert payload["operation_id"] == "status-1"
    assert payload["progress"][-1]["state"] == "completed"
    assert payload["audit"]["outcome"] == "success"
    assert calls == ["status"]


@pytest.mark.asyncio
async def test_control_permission_does_not_imply_read_or_destructive() -> None:
    calls: list[str] = []
    boundary = controller(calls)
    started = await handle_iroh_tool(
        "iroh_service_start", {}, permissions={"iroh.control"}, controller=boundary
    )
    denied = await handle_iroh_tool(
        "iroh_service_stop", {"confirm": True}, permissions={"iroh.control"}, controller=boundary
    )
    assert started["success"] is True
    assert denied["error"]["code"] == "permission_denied"
    assert calls == ["start"]


@pytest.mark.asyncio
async def test_destructive_confirmation_is_checked_before_side_effects() -> None:
    calls: list[str] = []
    boundary = controller(calls)
    refused = await handle_iroh_tool(
        "iroh_service_stop", {}, permissions={"iroh.destructive"}, controller=boundary
    )
    assert refused["success"] is False
    assert refused["error"]["code"] == "confirmation_required"
    assert refused["error"]["status"] == 409
    assert calls == []

    accepted = await handle_iroh_tool(
        "iroh_service_stop",
        {"confirm": True, "operation_id": "stop-1"},
        permissions={"iroh.destructive"},
        controller=boundary,
    )
    assert accepted["success"] is True
    assert accepted["operation_id"] == "stop-1"
    assert calls == ["stop"]


@pytest.mark.asyncio
async def test_malformed_ticket_is_typed_and_never_reflected() -> None:
    secret = " malformed ticket secret "
    result = await handle_iroh_tool(
        "iroh_ticket_import",
        {"ticket": secret, "expected_hash": "a" * 64},
        permissions={"iroh.control"},
        controller=controller([]),
    )
    rendered = json.dumps(result)
    assert result["success"] is False
    assert result["error"]["code"] == "invalid_ticket"
    assert secret not in rendered
    assert "ticket" not in result["audit"]


@pytest.mark.asyncio
async def test_storage_api_uses_server_assigned_permissions_and_status_codes() -> None:
    calls: list[str] = []
    app = fastapi.FastAPI()
    app.include_router(storage_router)
    app.state.iroh_operation_controller = controller(calls)
    app.state.iroh_permissions = {"iroh.read"}
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        listed = await client.get("/api/v0/storage/iroh/operations")
        assert listed.status_code == 200
        assert any(item["name"] == "ticket.import" for item in listed.json()["operations"])

        status = await client.post(
            "/api/v0/storage/iroh/operations/service.status",
            json={"operation_id": "api-status"},
        )
        assert status.status_code == 200
        assert status.json()["operation_id"] == "api-status"

        # A client cannot grant itself a permission through a header or body.
        denied = await client.post(
            "/api/v0/storage/iroh/operations/service.stop",
            headers={"X-Iroh-Permissions": "iroh.destructive"},
            json={"confirm": True, "permissions": ["iroh.destructive"]},
        )
        assert denied.status_code in {400, 403}
        assert calls == ["status"]


def test_maintained_openapi_describes_governance_and_typed_envelopes() -> None:
    schema = get_openapi_schema()
    execute = schema["paths"]["/api/v0/storage/iroh/operations/{operation}"]["post"]
    assert execute["operationId"] == "executeIrohOperation"
    assert set(execute["responses"]) >= {"200", "400", "403", "409", "422", "503"}
    assert schema["components"]["schemas"]["IrohPermission"]["enum"] == [
        "iroh.read",
        "iroh.control",
        "iroh.destructive",
    ]
    assert "IrohAuditRecord" in schema["components"]["schemas"]
    assert "IrohTypedError" in schema["components"]["schemas"]
