"""Compatibility package for legacy `mcp.controllers.*` imports.

The canonical implementation is under `ipfs_kit_py.mcp.controllers`.
This package aliases that module tree so older imports keep working.
"""

from __future__ import annotations

import importlib
import pkgutil
import sys
from types import ModuleType

_REAL_PREFIX = "ipfs_kit_py.mcp.controllers"
_ALIAS_PREFIX = __name__  # "mcp.controllers"


def _alias_module(alias_name: str, real_name: str) -> ModuleType | None:
    try:
        module = importlib.import_module(real_name)
    except Exception:
        return None

    sys.modules[alias_name] = module
    return module


# Import the real package (ensures it exists).
_real_pkg = importlib.import_module(_REAL_PREFIX)

# Alias all submodules/subpackages so `import mcp.controllers.foo` resolves.
for module_info in pkgutil.walk_packages(_real_pkg.__path__, prefix=_REAL_PREFIX + "."):
    real_name = module_info.name
    alias_name = _ALIAS_PREFIX + real_name[len(_REAL_PREFIX) :]
    module = _alias_module(alias_name, real_name)
    if module is None:
        continue

    # Expose first-level children as attributes of `mcp.controllers` so
    # `from mcp.controllers import fs_journal_controller` works.
    suffix = real_name[len(_REAL_PREFIX) + 1 :]
    if suffix and "." not in suffix:
        globals()[suffix] = module


def __getattr__(name: str) -> ModuleType:
    # Lazy access for modules that weren't pre-imported (or failed to import).
    real_name = f"{_REAL_PREFIX}.{name}"
    alias_name = f"{_ALIAS_PREFIX}.{name}"
    module = _alias_module(alias_name, real_name)
    if module is None:
        raise AttributeError(name)
    globals()[name] = module
    return module


__all__ = [
    name
    for name, value in globals().items()
    if not name.startswith("_") and isinstance(value, ModuleType)
]
