"""IPFS cluster tool group (status)."""
from __future__ import annotations

import uuid
from typing import Any, Dict

from ..core_operations import _call
from ..tool_metadata import tool_metadata


@tool_metadata(summary="Get IPFS cluster status", tags=["cluster", "read"])
async def cluster_status() -> Dict[str, Any]:
    out = await _call("get_cluster_status")
    out["request_id"] = str(uuid.uuid4())
    return out


__all__ = ["cluster_status"]
