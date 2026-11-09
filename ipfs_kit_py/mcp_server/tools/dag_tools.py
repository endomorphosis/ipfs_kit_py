"""DAG tool group (get / put)."""
from __future__ import annotations

import uuid
from typing import Any, Dict

from ..core_operations import _call
from ..tool_metadata import tool_metadata


@tool_metadata(summary="Get a DAG node by CID", tags=["dag", "read"], cache_ttl=300)
async def dag_get(cid: str) -> Dict[str, Any]:
    out = await _call("ipfs_dag_get", cid=cid)
    out["request_id"] = str(uuid.uuid4())
    return out


@tool_metadata(summary="Put a DAG node, returns CID", tags=["dag", "write"])
async def dag_put(data: dict) -> Dict[str, Any]:
    out = await _call("ipfs_dag_put", data=data)
    out["request_id"] = str(uuid.uuid4())
    return out


__all__ = ["dag_get", "dag_put"]
