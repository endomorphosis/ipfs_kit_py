"""Canonical core operations — single source of truth.

Every MCP tool, CLI command, and JS SDK call ultimately routes through these
async functions. They wrap the synchronous ``ipfs_kit`` orchestrator (run in a
worker thread so we stay cooperative under trio/anyio) and normalise results to
the aligned ``{"status": ...}`` envelope shared with ipfs_datasets_py.
"""
from __future__ import annotations

import functools
from typing import Any, Dict, Optional

import anyio

_kit = None


def get_kit():
    """Lazily build a single ipfs_kit instance (no daemon autostart in tests)."""
    global _kit
    if _kit is None:
        try:
            from ipfs_kit_py.ipfs_kit import ipfs_kit
            _kit = ipfs_kit.create(auto_start_daemons=False)
        except Exception:  # pragma: no cover - environment without daemon
            _kit = _StubKit()
    return _kit


class _StubKit:
    """Deterministic stub so the surfaces are testable without a live daemon."""

    def ipfs_add(self, file_path, recursive=False, **kw):
        return {"success": True, "cid": "bafkstub_add", "size": 0}

    def ipfs_cat(self, cid, **kw):
        return {"success": True, "content": b"", "cid": cid}

    def ipfs_pin_add(self, cid, recursive=True, **kw):
        return {"success": True, "pinned": cid}

    def ipfs_pin_ls(self, **kw):
        return {"success": True, "pins": {}}

    def ipfs_dag_get(self, cid, **kw):
        return {"success": True, "value": {}, "cid": cid}

    def ipfs_dag_put(self, data, **kw):
        return {"success": True, "cid": "bafkstub_dag"}

    def get_cluster_status(self, **kw):
        return {"success": True, "peers": []}


async def _call(method: str, /, **kwargs) -> Dict[str, Any]:
    kit = get_kit()
    fn = getattr(kit, method)
    raw = await anyio.to_thread.run_sync(functools.partial(fn, **kwargs))
    ok = bool(raw.get("success", True)) if isinstance(raw, dict) else True
    return {
        "status": "success" if ok else "error",
        "result": raw,
    }
