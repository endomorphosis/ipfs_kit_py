"""Shim module for tests and legacy scripts.

The implementation lives in `scripts/development/modernized_comprehensive_dashboard.py`.
This file allows `import modernized_comprehensive_dashboard` to work when running
pytest from the repository root.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any


def _load() -> ModuleType:
    repo_root = Path(__file__).resolve().parent
    candidates = [
        repo_root / "scripts" / "development" / "modernized_comprehensive_dashboard.py",
        repo_root / "scripts" / "development" / "modernized_comprehensive_dashboard_complete.py",
    ]

    last_error: Exception | None = None
    for target in (p for p in candidates if p.exists()):
        try:
            spec = importlib.util.spec_from_file_location(
                f"_ipfs_kit_modernized_comprehensive_dashboard_{target.stem}", target
            )
            if spec is None or spec.loader is None:
                raise ImportError(f"Unable to load module from {target}")

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # type: ignore[attr-defined]

            # Only accept modules that define the expected API.
            if hasattr(module, "ModernizedComprehensiveDashboard") and hasattr(module, "MemoryLogHandler"):
                return module
        except Exception as e:
            last_error = e

    if last_error is not None:
        raise last_error

    raise ModuleNotFoundError(
        "Expected a modernized dashboard implementation to exist and define the required symbols. "
        + ", ".join(str(p) for p in candidates)
    )


_m: ModuleType = _load()

# The dev stub may exist but be empty; the complete module contains the real symbols.
ModernizedComprehensiveDashboard: Any = getattr(
    _m, "ModernizedComprehensiveDashboard", getattr(_m, "ModernizedDashboard", None)
)
if ModernizedComprehensiveDashboard is None:
    raise AttributeError(
        "ModernizedComprehensiveDashboard not found in loaded module. "
        "Ensure scripts/development/modernized_comprehensive_dashboard_complete.py defines it."
    )

MemoryLogHandler: Any = getattr(_m, "MemoryLogHandler", None)
if MemoryLogHandler is None:
    raise AttributeError(
        "MemoryLogHandler not found in loaded module. "
        "Ensure scripts/development/modernized_comprehensive_dashboard_complete.py defines it."
    )

# Optional feature flags exposed by the implementation (tests expect these names)
IPFS_AVAILABLE: bool = bool(getattr(_m, "IPFS_AVAILABLE", False))
BUCKET_MANAGER_AVAILABLE: bool = bool(getattr(_m, "BUCKET_MANAGER_AVAILABLE", False))
PSUTIL_AVAILABLE: bool = bool(getattr(_m, "PSUTIL_AVAILABLE", False))
YAML_AVAILABLE: bool = bool(getattr(_m, "YAML_AVAILABLE", False))

__all__ = [
    "ModernizedComprehensiveDashboard",
    "MemoryLogHandler",
    "IPFS_AVAILABLE",
    "BUCKET_MANAGER_AVAILABLE",
    "PSUTIL_AVAILABLE",
    "YAML_AVAILABLE",
]
