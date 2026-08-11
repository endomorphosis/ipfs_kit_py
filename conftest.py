"""Source-tree fallback for the kit-owned proof-reuse pytest bridge.

Installed distributions discover the bridge through pytest11 metadata.  A
checkout does not have that metadata, so source tests opt in only when the
bridge module is importable.  This is deliberately module-level pytest plugin
declaration; early-conftest hooks can run before pytest's normal plugin policy.
"""

from __future__ import annotations

import importlib.util
import os
from importlib import metadata


_BRIDGE = "ipfs_kit_py.pytest_proof_reuse"


def _bridge_is_importable() -> bool:
    try:
        return importlib.util.find_spec(_BRIDGE) is not None
    except (ImportError, AttributeError, ValueError):
        return False


def _installed_bridge_exists() -> bool:
    """Avoid loading the same bridge through both pytest11 and source fallback."""
    try:
        entries = metadata.entry_points()
        selected = entries.select(group="pytest11") if hasattr(entries, "select") else entries.get("pytest11", ())
        return any(entry.name == "ipfs-kit-proof-reuse" and entry.value == _BRIDGE for entry in selected)
    except Exception:
        return False


_AUTOLOAD_DISABLED = bool(os.environ.get("PYTEST_DISABLE_PLUGIN_AUTOLOAD"))

# When entry-point autoload is disabled, installed metadata is not evidence that
# pytest will load the bridge.  Keep the source fallback deterministic in that
# mode while avoiding duplicate registration during ordinary installed runs.
pytest_plugins = (
    (_BRIDGE,)
    if _bridge_is_importable()
    and (_AUTOLOAD_DISABLED or not _installed_bridge_exists())
    else ()
)
