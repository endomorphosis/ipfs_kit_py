"""Tool group registry.

``TOOL_GROUPS`` maps category -> {tool_name: callable}. This single registry is
consumed by the hierarchical tool manager (MCP), the CLI, and the JS SDK
generator, so no surface maintains its own copy.
"""
from __future__ import annotations

from typing import Awaitable, Callable, Dict

from . import cluster_tools, dag_tools, ipfs_tools, pin_tools

TOOL_GROUPS: Dict[str, Dict[str, Callable[..., Awaitable]]] = {
    "ipfs_tools": {"ipfs_add": ipfs_tools.ipfs_add, "ipfs_cat": ipfs_tools.ipfs_cat},
    "pin_tools": {"pin_add": pin_tools.pin_add, "pin_ls": pin_tools.pin_ls},
    "dag_tools": {"dag_get": dag_tools.dag_get, "dag_put": dag_tools.dag_put},
    "cluster_tools": {"cluster_status": cluster_tools.cluster_status},
}

__all__ = ["TOOL_GROUPS"]
