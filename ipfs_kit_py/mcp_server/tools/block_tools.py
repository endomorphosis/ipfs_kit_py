"""Raw block tool group (Kubo `ipfs block` parity)."""
from __future__ import annotations

import uuid
from typing import Any, Dict

from ..core_operations import _call
from ..tool_metadata import tool_metadata


@tool_metadata(summary="Store a raw block and return its CID", tags=["block", "write"])
async def block_put(data: str) -> Dict[str, Any]:
    out = await _call("ipfs_block_put", data=data)
    out["request_id"] = str(uuid.uuid4())
    return out


@tool_metadata(summary="Fetch a raw block by CID", tags=["block", "read"])
async def block_get(cid: str) -> Dict[str, Any]:
    out = await _call("ipfs_block_get", cid=cid)
    out["request_id"] = str(uuid.uuid4())
    return out


@tool_metadata(summary="Report size of a raw block", tags=["block", "read"])
async def block_stat(cid: str) -> Dict[str, Any]:
    out = await _call("ipfs_block_stat", cid=cid)
    out["request_id"] = str(uuid.uuid4())
    return out


__all__ = ["block_put", "block_get", "block_stat"]
