"""Modern MCP Feature Bridge.

This module historically acted as a shim that loaded a development script from
`scripts/development/modern_mcp_feature_bridge.py`.

For testability and "zero-touch" installs, we also provide a built-in fallback
implementation when that development script is absent.
"""

from __future__ import annotations

import importlib.util
import time
from pathlib import Path
from types import ModuleType
from typing import Any


def _load() -> ModuleType:
    repo_root = Path(__file__).resolve().parent
    target = repo_root / "scripts" / "development" / "modern_mcp_feature_bridge.py"
    if not target.exists():
        raise ModuleNotFoundError(str(target))

    spec = importlib.util.spec_from_file_location("_ipfs_kit_modern_mcp_feature_bridge", target)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module from {target}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


class _FallbackModernMCPFeatureBridge:
    def __init__(self, *args, **kwargs):
        self.start_time = time.time()
        self.initialized = False

    async def initialize_async(self) -> None:
        self.initialized = True

    def get_system_status(self) -> dict:
        uptime = max(0.0, time.time() - self.start_time)
        return {
            "success": True,
            "data": {
                "timestamp": time.time(),
                "uptime": uptime,
                "directories": [],
            },
        }

    def get_system_health(self) -> dict:
        return {
            "success": True,
            "data": {
                "overall_health": "ok",
                "checks": {},
                "timestamp": time.time(),
            },
        }

    def get_buckets(self) -> dict:
        return {"success": True, "data": []}

    def get_backends(self) -> dict:
        return {"success": True, "data": []}

    def get_mcp_status(self) -> dict:
        return {"success": True, "data": {"available": True}}

    def get_available_comprehensive_features(self) -> dict:
        return {
            "success": True,
            "data": {
                "categories": {
                    "system": ["status", "health"],
                    "storage": ["buckets", "backends"],
                    "mcp": ["tools", "status"],
                }
            },
        }


try:
    _m: ModuleType = _load()
    ModernMCPFeatureBridge: Any = getattr(_m, "ModernMCPFeatureBridge")
except Exception:
    ModernMCPFeatureBridge = _FallbackModernMCPFeatureBridge

__all__ = ["ModernMCPFeatureBridge"]
