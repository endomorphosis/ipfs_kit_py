"""CAR (content-addressed archive) tool group."""
from __future__ import annotations

import uuid
from typing import Any, Dict, List

from ..core_operations import _call
from ..tool_metadata import tool_metadata


@tool_metadata(summary="Create a CAR archive from roots", tags=["car", "write"])
async def create_car(roots: List[str]) -> Dict[str, Any]:
    out = await _call("create_car", roots=roots, blocks=None)
    out["request_id"] = str(uuid.uuid4())
    return out


__all__ = ["create_car"]
