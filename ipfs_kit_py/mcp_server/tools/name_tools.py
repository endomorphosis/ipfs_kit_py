"""IPNS naming tool group (publish / resolve)."""
from __future__ import annotations

import uuid
from typing import Any, Dict

from ..core_operations import _call
from ..tool_metadata import tool_metadata


@tool_metadata(summary="Publish a path to IPNS", tags=["name", "write"])
async def name_publish(path: str) -> Dict[str, Any]:
    out = await _call("name_publish", path=path)
    out["request_id"] = str(uuid.uuid4())
    return out


@tool_metadata(summary="Resolve an IPNS name to a path", tags=["name", "read"])
async def name_resolve() -> Dict[str, Any]:
    out = await _call("name_resolve")
    out["request_id"] = str(uuid.uuid4())
    return out


__all__ = ["name_publish", "name_resolve"]
