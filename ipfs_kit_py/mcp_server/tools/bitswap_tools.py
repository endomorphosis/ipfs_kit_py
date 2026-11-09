"""Bitswap tool group (Kubo `ipfs bitswap` parity)."""
from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from ..core_operations import _call
from ..tool_metadata import tool_metadata


@tool_metadata(summary="Show bitswap exchange statistics", tags=["bitswap", "read"])
async def bitswap_stat() -> Dict[str, Any]:
    out = await _call("ipfs_bitswap_stat")
    out["request_id"] = str(uuid.uuid4())
    return out


@tool_metadata(summary="Show blocks currently on the wantlist", tags=["bitswap", "read"])
async def bitswap_wantlist(peer: Optional[str] = None) -> Dict[str, Any]:
    out = await _call("ipfs_bitswap_wantlist", peer=peer)
    out["request_id"] = str(uuid.uuid4())
    return out


__all__ = ["bitswap_stat", "bitswap_wantlist"]
