"""Governed Iroh tools for the canonical unified MCP server."""

from __future__ import annotations

import copy
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from ipfs_kit_py.iroh.config import IrohServiceConfig, validate_instance_name
from ipfs_kit_py.iroh.governance import (
    IrohOperationController,
    IrohPermission,
    OPERATION_DEFINITIONS,
)
from ipfs_kit_py.iroh.observability import IrohObservability


TOOL_OPERATIONS = {
    "iroh_diagnostics": "diagnostics",
    "iroh_service_status": "service.status",
    "iroh_blob_stat": "blob.stat",
    "iroh_service_start": "service.start",
    "iroh_blob_fetch": "blob.fetch",
    "iroh_ticket_import": "ticket.import",
    "iroh_service_stop": "service.stop",
    "iroh_service_restart": "service.restart",
}


def _tool_schema(tool_name: str, operation: str) -> dict[str, Any]:
    definition = OPERATION_DEFINITIONS[operation]
    schema = copy.deepcopy(dict(definition.input_schema))
    if definition.destructive:
        schema["properties"]["confirm"] = {
            "type": "boolean",
            "const": True,
            "description": "Explicit confirmation of this destructive operation.",
        }
        schema.setdefault("required", []).append("confirm")
    return {
        "name": tool_name,
        "description": definition.description,
        "inputSchema": schema,
        "annotations": {
            "readOnlyHint": definition.permission == IrohPermission.READ,
            "destructiveHint": definition.destructive,
            "idempotentHint": operation in {"diagnostics", "service.status", "blob.stat"},
        },
        "x-ipfs-kit-permission": definition.permission.value,
        "x-ipfs-kit-operation": operation,
    }


IROH_MCP_TOOLS = [_tool_schema(name, operation) for name, operation in TOOL_OPERATIONS.items()]
IROH_DIAGNOSTICS_TOOL = IROH_MCP_TOOLS[0]
tools = IROH_MCP_TOOLS


async def _run_diagnostics(
    arguments: Mapping[str, Any] | None = None,
    *,
    observability_factory: Any = IrohObservability,
    state_root: str | None = None,
) -> dict[str, Any]:
    """Run the original redacted diagnostics implementation."""

    args = dict(arguments or {})
    instance = validate_instance_name(args.get("instance", "default"))
    output_format = args.get("format", "health")
    persist = args.get("persist", True)
    observer = observability_factory(
        IrohServiceConfig.default(instance, state_root=state_root, enabled=True)
    )
    if output_format == "metrics":
        result = await observer.metrics(persist=persist)
    elif output_format == "prometheus":
        result = await observer.prometheus(persist=persist)
    else:
        result = await observer.diagnostics(persist=persist)
    return {"success": True, "format": output_format, "diagnostics": result}


async def handle_iroh_diagnostics(
    arguments: Mapping[str, Any] | None = None,
    *,
    observability_factory: Any = IrohObservability,
    state_root: str | None = None,
) -> dict[str, Any]:
    """Compatibility handler retaining the diagnostic-only safe contract."""

    if arguments is not None and not isinstance(arguments, Mapping):
        return {"success": False, "code": "invalid_arguments", "error": "arguments must be an object"}
    args = dict(arguments or {})
    if set(args) - {"instance", "format", "persist"}:
        return {"success": False, "code": "invalid_arguments", "error": "unsupported argument"}
    try:
        validate_instance_name(args.get("instance", "default"))
    except Exception:
        return {"success": False, "code": "invalid_instance", "error": "invalid Iroh instance"}
    if args.get("format", "health") not in {"health", "metrics", "prometheus"}:
        return {"success": False, "code": "invalid_format", "error": "invalid diagnostic format"}
    if not isinstance(args.get("persist", True), bool):
        return {"success": False, "code": "invalid_arguments", "error": "persist must be boolean"}
    try:
        return await _run_diagnostics(
            args, observability_factory=observability_factory, state_root=state_root
        )
    except Exception:
        return {"success": False, "code": "diagnostics_unavailable", "error": "Iroh diagnostics unavailable"}


async def handle_iroh_tool(
    tool_name: str,
    arguments: Mapping[str, Any] | None = None,
    *,
    permissions: Iterable[str | IrohPermission] | str | IrohPermission | None = None,
    actor: str = "mcp",
    controller: IrohOperationController | None = None,
    state_root: str | Path | None = None,
) -> dict[str, Any]:
    """Dispatch one allowlisted tool through the shared governed boundary."""

    operation = TOOL_OPERATIONS.get(tool_name)
    if operation is None:
        # Do not reflect an attacker-controlled tool name.
        return await (controller or IrohOperationController(state_root=state_root)).execute(
            "unsupported", {}, permissions=permissions, actor=actor
        )
    if arguments is not None and not isinstance(arguments, Mapping):
        safe_arguments: Any = arguments
        confirm = False
    else:
        safe_arguments = dict(arguments or {})
        confirm = safe_arguments.pop("confirm", False)
    return await (controller or IrohOperationController(state_root=state_root)).execute(
        operation,
        safe_arguments,
        permissions=permissions,
        confirm=confirm,
        actor=actor,
    )


async def iroh_diagnostics(arguments: Mapping[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
    return await handle_iroh_tool("iroh_diagnostics", arguments, **kwargs)


async def handle_iroh_service_status(arguments: Mapping[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
    return await handle_iroh_tool("iroh_service_status", arguments, **kwargs)


async def handle_iroh_blob_stat(arguments: Mapping[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
    return await handle_iroh_tool("iroh_blob_stat", arguments, **kwargs)


async def handle_iroh_service_start(arguments: Mapping[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
    return await handle_iroh_tool("iroh_service_start", arguments, **kwargs)


async def handle_iroh_blob_fetch(arguments: Mapping[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
    return await handle_iroh_tool("iroh_blob_fetch", arguments, **kwargs)


async def handle_iroh_ticket_import(arguments: Mapping[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
    return await handle_iroh_tool("iroh_ticket_import", arguments, **kwargs)


async def handle_iroh_service_stop(arguments: Mapping[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
    return await handle_iroh_tool("iroh_service_stop", arguments, **kwargs)


async def handle_iroh_service_restart(arguments: Mapping[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
    return await handle_iroh_tool("iroh_service_restart", arguments, **kwargs)


get_iroh_diagnostics = handle_iroh_diagnostics

__all__ = [
    "IROH_DIAGNOSTICS_TOOL",
    "IROH_MCP_TOOLS",
    "TOOL_OPERATIONS",
    "get_iroh_diagnostics",
    "handle_iroh_blob_fetch",
    "handle_iroh_blob_stat",
    "handle_iroh_diagnostics",
    "handle_iroh_service_restart",
    "handle_iroh_service_start",
    "handle_iroh_service_status",
    "handle_iroh_service_stop",
    "handle_iroh_ticket_import",
    "handle_iroh_tool",
    "iroh_diagnostics",
    "tools",
]
