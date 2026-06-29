"""MFS (mutable file system) tool group."""
from __future__ import annotations

import uuid
from typing import Any, Dict

from ..core_operations import _call
from ..tool_metadata import tool_metadata


@tool_metadata(summary="List an MFS directory", tags=["mfs", "read"])
async def files_ls(path: str = "/", long: bool = False) -> Dict[str, Any]:
    out = await _call("files_ls", path=path, long=long)
    out["request_id"] = str(uuid.uuid4())
    return out


@tool_metadata(summary="Make an MFS directory", tags=["mfs", "write"])
async def files_mkdir(path: str, parents: bool = False) -> Dict[str, Any]:
    out = await _call("files_mkdir", path=path, parents=parents)
    out["request_id"] = str(uuid.uuid4())
    return out


@tool_metadata(summary="Stat an MFS path", tags=["mfs", "read"])
async def files_stat(path: str) -> Dict[str, Any]:
    out = await _call("files_stat", path=path)
    out["request_id"] = str(uuid.uuid4())
    return out


@tool_metadata(summary="Write content to an MFS path", tags=["mfs", "write"])
async def files_write(path: str, content: str) -> Dict[str, Any]:
    out = await _call("files_write", path=path, content=content)
    out["request_id"] = str(uuid.uuid4())
    return out


@tool_metadata(summary="Read content from an MFS path", tags=["mfs", "read"])
async def files_read(path: str) -> Dict[str, Any]:
    out = await _call("files_read", path=path)
    out["request_id"] = str(uuid.uuid4())
    return out


@tool_metadata(summary="Remove an MFS path", tags=["mfs", "write"])
async def files_rm(path: str) -> Dict[str, Any]:
    out = await _call("files_rm", path=path)
    out["request_id"] = str(uuid.uuid4())
    return out


__all__ = ["files_ls", "files_mkdir", "files_stat", "files_write", "files_read", "files_rm"]
