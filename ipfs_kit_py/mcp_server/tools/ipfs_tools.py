"""IPFS content tool group (add / cat)."""
from __future__ import annotations

import uuid
from typing import Any, Dict

from ..core_operations import _call
from ..tool_metadata import tool_metadata


@tool_metadata(summary="Add a file to IPFS and return its CID", tags=["ipfs", "write"])
async def ipfs_add(file_path: str, recursive: bool = False) -> Dict[str, Any]:
    out = await _call("ipfs_add", file_path=file_path, recursive=recursive)
    out["request_id"] = str(uuid.uuid4())
    return out


@tool_metadata(summary="Retrieve content from IPFS by CID", tags=["ipfs", "read"], cache_ttl=300)
async def ipfs_cat(cid: str) -> Dict[str, Any]:
    out = await _call("ipfs_cat", cid=cid)
    out["request_id"] = str(uuid.uuid4())
    return out


@tool_metadata(summary="List entries under an IPFS path", tags=["ipfs", "read"])
async def ipfs_ls(path: str) -> Dict[str, Any]:
    out = await _call("ipfs_ls_path", path=path)
    out["request_id"] = str(uuid.uuid4())
    return out


__all__ = ["ipfs_add", "ipfs_cat", "ipfs_ls"]
