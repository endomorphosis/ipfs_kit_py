"""Optional proof-reuse bootstrap for direct pytest node selection.

Normal pytest startup discovers the shared plugin through the ``pytest11``
entry point declared in ``pyproject.toml``.  Disabling entry-point autoload is
common for focused tests, so this root bootstrap supplies the same plugin in
that case.  Missing optional proof-reuse packages leave pytest unchanged;
errors raised from inside an available plugin remain visible.
"""

from __future__ import annotations

import importlib
import os

_PROOF_REUSE_PLUGIN = "ipfs_accelerate_py.testing.proof_reuse.plugin"


def _optional_proof_reuse_plugin() -> tuple[str, ...]:
    try:
        importlib.import_module(_PROOF_REUSE_PLUGIN)
    except ModuleNotFoundError as exc:
        missing = exc.name or ""
        if missing and (
            missing == _PROOF_REUSE_PLUGIN
            or _PROOF_REUSE_PLUGIN.startswith(f"{missing}.")
        ):
            return ()
        raise
    return (_PROOF_REUSE_PLUGIN,)


# Avoid registering the same module under both its entry-point name and module
# name.  With autoload disabled, pytest processes this tuple early enough for
# the plugin's command-line and ini options to remain available.
pytest_plugins = (
    _optional_proof_reuse_plugin()
    if os.environ.get("PYTEST_DISABLE_PLUGIN_AUTOLOAD")
    else ()
)
