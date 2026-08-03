"""Tool group registry.

``TOOL_GROUPS`` maps category -> {tool_name: callable}. This single registry is
consumed by the hierarchical tool manager (MCP), the CLI, and the JS SDK
generator, so no surface maintains its own copy.
"""
from __future__ import annotations

import re
from typing import Any, Awaitable, Callable, Dict
from urllib.parse import unquote

from . import (
    bitswap_tools,
    block_tools,
    car_tools,
    cluster_tools,
    dag_tools,
    ipfs_tools,
    mfs_tools,
    name_tools,
    pin_tools,
    stats_tools,
    swarm_tools,
)


async def iroh_diagnostics(
    instance: str = "default",
    format: str = "health",
    persist: bool = True,
) -> Dict[str, Any]:
    """Return a redacted Iroh health receipt or bounded-label metrics.

    Iroh diagnostics live in the optional managed-Iroh integration, which
    pulls in the application's HTTP stack.  Keep that import at execution
    time so constructing the core MCP server remains usable from a minimal
    wheel without FastAPI installed.
    """
    from .iroh_tools import iroh_diagnostics as managed_iroh_diagnostics

    return await managed_iroh_diagnostics(instance=instance, format=format, persist=persist)

# This is the sole category-to-tool registry.  MCP, CLI, FastMCP, and SDK
# generation consume this object through HierarchicalToolManager.
TOOL_GROUPS: Dict[str, Dict[str, Callable[..., Awaitable]]] = {
    "ipfs_tools": {"ipfs_add": ipfs_tools.ipfs_add, "ipfs_cat": ipfs_tools.ipfs_cat,
                   "ipfs_ls": ipfs_tools.ipfs_ls},
    "pin_tools": {"pin_add": pin_tools.pin_add, "pin_ls": pin_tools.pin_ls,
                  "pin_rm": pin_tools.pin_rm, "get_pinset": pin_tools.get_pinset},
    "dag_tools": {"dag_get": dag_tools.dag_get, "dag_put": dag_tools.dag_put},
    "mfs_tools": {"files_ls": mfs_tools.files_ls, "files_mkdir": mfs_tools.files_mkdir,
                  "files_stat": mfs_tools.files_stat, "files_write": mfs_tools.files_write,
                  "files_read": mfs_tools.files_read, "files_rm": mfs_tools.files_rm},
    "swarm_tools": {"node_id": swarm_tools.node_id, "swarm_peers": swarm_tools.swarm_peers},
    "name_tools": {"name_publish": name_tools.name_publish, "name_resolve": name_tools.name_resolve},
    "car_tools": {"create_car": car_tools.create_car},
    "cluster_tools": {"cluster_status": cluster_tools.cluster_status},
    "block_tools": {"block_put": block_tools.block_put, "block_get": block_tools.block_get,
                    "block_stat": block_tools.block_stat},
    "bitswap_tools": {"bitswap_stat": bitswap_tools.bitswap_stat,
                      "bitswap_wantlist": bitswap_tools.bitswap_wantlist},
    "stats_tools": {"stats_bw": stats_tools.stats_bw, "stats_repo": stats_tools.stats_repo},
    "iroh_tools": {"iroh_diagnostics": iroh_diagnostics},
}


# MCP protocol, REST, and tool dispatch all use this module as their source of
# truth.  Keeping the route names next to the tool registry prevents one
# transport from silently gaining a method that another transport cannot
# resolve.
MCP_PROTOCOL_ROUTES: Dict[str, str] = {
    "initialize": "initialize",
    "tools/list": "tools_list",
    "tools/call": "tools_call",
    "mcp++/interfaces": "interfaces",
    "agent_supervisor.receipts.read": "agent_supervisor_receipts",
    "mcp++/dag/frontier": "dag_frontier",
    "mcp++/ucan/validate": "ucan",
    "mcp++/ucan/delegate": "ucan",
    "mcp++/policy/evaluate": "policy",
    "ping": "ping",
}

MCP_PROTOCOL_ROUTE_PREFIXES: tuple[tuple[str, str], ...] = (
    ("notifications/", "notification"),
    ("mcp++/goals/", "profile_g"),
    ("mcp++/tasks/", "profile_g"),
    ("mcp++/risk/", "profile_g"),
    ("mcp++/neighborhood/", "profile_g"),
    ("mcp++/schedule/", "profile_g"),
)

# Static HTTP bindings are intentionally expressed in terms of the same MCP
# method names above.  The ASGI transport then has no private route table.
MCP_REST_ROUTES: Dict[tuple[str, str], str] = {
    ("GET", "/mcp/risk/profile"): "mcp++/risk/profile",
    ("POST", "/mcp/goals"): "mcp++/goals/create",
    ("GET", "/mcp/goals"): "mcp++/goals/list",
    ("POST", "/mcp/tasks"): "mcp++/tasks/create",
    ("GET", "/mcp/tasks"): "mcp++/tasks/list",
    ("GET", "/mcp/tasks/ready"): "mcp++/tasks/ready",
    ("POST", "/mcp/risk/assess"): "mcp++/risk/assess",
    ("GET", "/mcp/risk/evidence"): "mcp++/risk/evidence",
    ("GET", "/mcp/risk/history"): "mcp++/risk/history",
    ("POST", "/mcp/neighborhood/query"): "mcp++/neighborhood/query",
    ("POST", "/mcp/neighborhood/attest"): "mcp++/neighborhood/attest",
    ("GET", "/mcp/schedule/frontier"): "mcp++/schedule/frontier",
    ("POST", "/mcp/schedule/proposals"): "mcp++/schedule/propose",
    ("POST", "/mcp/schedule/claims"): "mcp++/schedule/claim",
    ("POST", "/mcp/schedule/resolutions"): "mcp++/schedule/resolve",
    ("POST", "/mcp/schedule/reconcile"): "mcp++/schedule/reconcile",
    ("GET", "/mcp/agent-supervisor/receipts"): "agent_supervisor.receipts.read",
    ("POST", "/mcp/agent-supervisor/receipts"): "agent_supervisor.receipts.read",
}

# (HTTP verb, path pattern, MCP method template, parameter-name, list-value)
# ``action`` is a named capture used only by the method template.
MCP_REST_ROUTE_PATTERNS: tuple[tuple[str, str, str, str, bool], ...] = (
    ("GET", r"/mcp/goals/(?P<goal_cid>[^/]+)$", "mcp++/goals/get", "goal_cid", False),
    ("POST", r"/mcp/goals/(?P<goal_cid>[^/]+)/(?P<action>decompose|select)$",
     "mcp++/goals/{action}", "goal_cid", False),
    ("GET", r"/mcp/tasks/(?P<task_cid>[^/]+)$", "mcp++/tasks/get", "task_cid", False),
    ("GET", r"/mcp/schedule/status/(?P<task_cid>[^/]+)$", "mcp++/schedule/status", "task_cid", False),
    ("POST", r"/mcp/schedule/claims/(?P<claim_cid>[^/]+)/(?P<action>renew|release)$",
     "mcp++/schedule/{action}", "claim_cid", False),
    ("GET", r"/mcp/agent-supervisor/receipts/(?P<receipt_ids>[^/]+)$",
     "agent_supervisor.receipts.read", "receipt_ids", True),
)

# Canonical MCP++ profile names are advertised only when their capability flag
# is available.  In particular, the built-in deontic policy is Profile D, not
# an HTTP- or accelerator-only feature.
MCP_PROFILE_REGISTRY: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("mcp++/interface-descriptors", ("A_interface_descriptors",)),
    ("mcp++/cid-envelopes", ("B_cid_envelopes",)),
    ("mcp++/ucan", ("C_ucan_unsigned",)),
    ("mcp++/deontic-policy", ("D_policy",)),
    ("mcp++/event-dag", ("E_dag_events",)),
    ("mcp++/p2p-transport", ("E_p2p_transport",)),
    ("mcp++/risk-scheduling", ("G_risk_scheduling",)),
)


def resolve_tool_route(name: str) -> tuple[str, str] | None:
    """Return a registered ``(category, tool)`` pair for an MCP tool name."""
    if not isinstance(name, str) or not name:
        return None
    category, separator, tool = name.partition("/")
    if separator:
        return (category, tool) if tool and tool in TOOL_GROUPS.get(category, {}) else None
    matches = [category for category, tools in TOOL_GROUPS.items() if name in tools]
    return (matches[0], name) if len(matches) == 1 else None


def resolve_mcp_route(method: str) -> str | None:
    """Resolve an RPC method through the shared protocol route registry."""
    route = MCP_PROTOCOL_ROUTES.get(method)
    if route is not None:
        return route
    for prefix, route in MCP_PROTOCOL_ROUTE_PREFIXES:
        if method.startswith(prefix):
            return route
    return None


def resolve_rest_route(http_method: str, path: str) -> tuple[str, Dict[str, Any]] | None:
    """Resolve an HTTP endpoint to its registry-backed RPC method and params."""
    method = MCP_REST_ROUTES.get((http_method.upper(), path))
    if method is not None:
        return method, {}
    for verb, pattern, method_template, parameter, list_value in MCP_REST_ROUTE_PATTERNS:
        if verb != http_method.upper():
            continue
        match = re.fullmatch(pattern, path)
        if match is None:
            continue
        method = method_template.format(**match.groupdict())
        value = unquote(match.group(parameter))
        return method, {parameter: [value] if list_value else value}
    return None


def supported_mcpp_profiles(capabilities: Dict[str, Any]) -> list[str]:
    """Return canonical profile identifiers supported by this runtime."""
    profiles = capabilities.get("profiles", {}) if isinstance(capabilities, dict) else {}
    if not isinstance(profiles, dict):
        return []
    return [
        name for name, requirements in MCP_PROFILE_REGISTRY
        if all(profiles.get(requirement) is True for requirement in requirements)
    ]


__all__ = [
    "TOOL_GROUPS",
    "MCP_PROTOCOL_ROUTES",
    "MCP_PROTOCOL_ROUTE_PREFIXES",
    "MCP_REST_ROUTES",
    "MCP_REST_ROUTE_PATTERNS",
    "MCP_PROFILE_REGISTRY",
    "resolve_tool_route",
    "resolve_mcp_route",
    "resolve_rest_route",
    "supported_mcpp_profiles",
]
