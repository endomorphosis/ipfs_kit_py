"""MCP operation exposing redacted Iroh health and bounded metrics."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ipfs_kit_py.iroh.config import IrohServiceConfig, validate_instance_name
from ipfs_kit_py.iroh.observability import IrohObservability

IROH_DIAGNOSTICS_TOOL = {
    "name": "iroh_diagnostics",
    "description": "Get a redacted health receipt or bounded-label metrics for an Iroh instance",
    "inputSchema": {
        "type": "object",
        "properties": {
            "instance": {
                "type": "string",
                "pattern": "^[a-z0-9][a-z0-9_-]{0,63}$",
                "default": "default",
            },
            "format": {
                "type": "string",
                "enum": ["health", "metrics", "prometheus"],
                "default": "health",
            },
            "persist": {"type": "boolean", "default": True},
        },
        "additionalProperties": False,
    },
}
IROH_MCP_TOOLS = [IROH_DIAGNOSTICS_TOOL]
tools = IROH_MCP_TOOLS


async def handle_iroh_diagnostics(
    arguments: Mapping[str, Any] | None = None,
    *,
    observability_factory: Any = IrohObservability,
    state_root: str | None = None,
) -> dict[str, Any]:
    """Execute diagnostics without reflecting input or exception data."""

    if arguments is not None and not isinstance(arguments, Mapping):
        return {
            "success": False,
            "code": "invalid_arguments",
            "error": "arguments must be an object",
        }
    args = dict(arguments or {})
    if set(args) - {"instance", "format", "persist"}:
        return {"success": False, "code": "invalid_arguments", "error": "unsupported argument"}
    try:
        instance = validate_instance_name(args.get("instance", "default"))
    except Exception:
        return {"success": False, "code": "invalid_instance", "error": "invalid Iroh instance"}

    output_format = args.get("format", "health")
    if output_format not in {"health", "metrics", "prometheus"}:
        return {"success": False, "code": "invalid_format", "error": "invalid diagnostic format"}
    persist = args.get("persist", True)
    if not isinstance(persist, bool):
        return {"success": False, "code": "invalid_arguments", "error": "persist must be boolean"}

    try:
        observer = observability_factory(
            IrohServiceConfig.default(instance, state_root=state_root, enabled=True)
        )
        if output_format == "metrics":
            result = await observer.metrics(persist=persist)
        elif output_format == "prometheus":
            result = await observer.prometheus(persist=persist)
        else:
            result = await observer.diagnostics(persist=persist)
    except Exception:
        return {
            "success": False,
            "code": "diagnostics_unavailable",
            "error": "Iroh diagnostics unavailable",
        }
    return {"success": True, "format": output_format, "diagnostics": result}


async def iroh_diagnostics(arguments: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return await handle_iroh_diagnostics(arguments)


get_iroh_diagnostics = handle_iroh_diagnostics

__all__ = [
    "IROH_DIAGNOSTICS_TOOL",
    "IROH_MCP_TOOLS",
    "get_iroh_diagnostics",
    "handle_iroh_diagnostics",
    "iroh_diagnostics",
    "tools",
]
