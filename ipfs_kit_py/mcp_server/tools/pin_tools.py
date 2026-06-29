"""Pin management tool group (add / list)."""
from __future__ import annotations

import uuid
from typing import Any, Dict

from ..core_operations import _call
from ..tool_metadata import tool_metadata


@tool_metadata(summary="Pin a CID to the local node", tags=["pin", "write"])
async def pin_add(cid: str, recursive: bool = True) -> Dict[str, Any]:
    out = await _call("ipfs_pin_add", cid=cid, recursive=recursive)
    out["request_id"] = str(uuid.uuid4())
    return out


@tool_metadata(summary="List pinned CIDs", tags=["pin", "read"])
async def pin_ls() -> Dict[str, Any]:
    out = await _call("ipfs_pin_ls")
    out["request_id"] = str(uuid.uuid4())
    return out


__all__ = ["pin_add", "pin_ls"]
