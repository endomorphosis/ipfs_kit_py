"""Optional proof-reuse bootstrap for direct pytest node selection.

Installed distributions discover the shared plugin through the ``pytest11``
entry point declared in ``pyproject.toml``.  A source checkout has no entry
point until it is installed, so this root bootstrap supplies the same plugin
when autoload is disabled or the matching installed entry point is absent.
Missing optional proof-reuse packages leave pytest unchanged; errors raised
from inside an available plugin remain visible.
"""

from __future__ import annotations

from importlib import metadata as importlib_metadata
from importlib.machinery import PathFinder
import os

_PROOF_REUSE_PLUGIN = "ipfs_accelerate_py.testing.proof_reuse.plugin"


def _module_available_without_import(module_name: str) -> bool:
    """Resolve a dotted module spec without executing parent packages."""

    search_path = None
    parts = module_name.split(".")
    for index, part in enumerate(parts):
        try:
            # Searching each path segment by basename avoids PathFinder's
            # normal requirement that a qualified parent already be imported.
            spec = PathFinder.find_spec(part, search_path)
        except Exception:
            return False
        if spec is None:
            return False
        search_path = spec.submodule_search_locations
        if index < len(parts) - 1 and search_path is None:
            return False
    return True


def _optional_proof_reuse_plugin() -> tuple[str, ...]:
    if not _module_available_without_import(_PROOF_REUSE_PLUGIN):
        return ()
    return (_PROOF_REUSE_PLUGIN,)


def _installed_proof_reuse_entry_point() -> bool:
    """Return whether pytest autoload can discover the shared plugin."""

    try:
        entry_points = importlib_metadata.entry_points()
        if hasattr(entry_points, "select"):
            candidates = entry_points.select(group="pytest11")
        else:  # pragma: no cover - compatibility with older importlib.metadata
            candidates = entry_points.get("pytest11", ())
    except Exception:
        return False
    return any(
        getattr(entry_point, "value", None) == _PROOF_REUSE_PLUGIN
        for entry_point in candidates
    )


def pytest_load_initial_conftests(early_config, parser, args):  # noqa: ARG001
    """Register the optional proof-reuse plugin when discovery needs a hand."""

    if os.environ.get("PYTEST_DISABLE_PLUGIN_AUTOLOAD") not in {"1", "true", "yes"}:
        if _installed_proof_reuse_entry_point():
            return
    plugins = _optional_proof_reuse_plugin()
    if not plugins:
        return
    early_config.pluginmanager.import_plugin(plugins[0])
