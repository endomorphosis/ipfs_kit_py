"""Swarm / node identity tool group."""
from __future__ import annotations

import uuid
from typing import Any, Dict

from ..core_operations import _call
from ..tool_metadata import tool_metadata


@tool_metadata(summary="Get local node identity", tags=["swarm", "read"])
async def node_id() -> Dict[str, Any]:
    out = await _call("ipfs_id")
    out["request_id"] = str(uuid.uuid4())
    return out


@tool_metadata(summary="List connected swarm peers", tags=["swarm", "read"])
async def swarm_peers() -> Dict[str, Any]:
    out = await _call("ipfs_swarm_peers")
    out["request_id"] = str(uuid.uuid4())
    return out


__all__ = ["node_id", "swarm_peers"]
