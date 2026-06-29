"""Stats tool group (Kubo `ipfs stats` parity)."""
from __future__ import annotations

import uuid
from typing import Any, Dict

from ..core_operations import _call
from ..tool_metadata import tool_metadata


@tool_metadata(summary="Report node bandwidth statistics", tags=["stats", "read"])
async def stats_bw() -> Dict[str, Any]:
    out = await _call("ipfs_stats_bw")
    out["request_id"] = str(uuid.uuid4())
    return out


@tool_metadata(summary="Report local repo statistics", tags=["stats", "read"])
async def stats_repo() -> Dict[str, Any]:
    out = await _call("ipfs_stats_repo")
    out["request_id"] = str(uuid.uuid4())
    return out


__all__ = ["stats_bw", "stats_repo"]
