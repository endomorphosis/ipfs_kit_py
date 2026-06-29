"""Tool group registry.

``TOOL_GROUPS`` maps category -> {tool_name: callable}. This single registry is
consumed by the hierarchical tool manager (MCP), the CLI, and the JS SDK
generator, so no surface maintains its own copy.
"""
from __future__ import annotations

from typing import Awaitable, Callable, Dict

from . import (
    car_tools,
    cluster_tools,
    dag_tools,
    ipfs_tools,
    mfs_tools,
    name_tools,
    pin_tools,
    swarm_tools,
)

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
}

__all__ = ["TOOL_GROUPS"]
