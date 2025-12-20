"""Shim module for tests and legacy scripts.

The implementation lives in `scripts/development/modern_mcp_feature_bridge.py`.
This file allows `import modern_mcp_feature_bridge` to work when running pytest
from the repository root.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any


def _load() -> ModuleType:
    repo_root = Path(__file__).resolve().parent
    target = repo_root / "scripts" / "development" / "modern_mcp_feature_bridge.py"
    if not target.exists():
        raise ModuleNotFoundError(f"Expected {target} to exist")

    spec = importlib.util.spec_from_file_location("_ipfs_kit_modern_mcp_feature_bridge", target)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module from {target}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


_m: ModuleType = _load()

ModernMCPFeatureBridge: Any = getattr(_m, "ModernMCPFeatureBridge")

__all__ = ["ModernMCPFeatureBridge"]
