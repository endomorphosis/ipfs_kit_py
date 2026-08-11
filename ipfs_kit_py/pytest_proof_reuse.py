"""Safe pytest bridge for the optional proof-reuse accelerator.

Importing this module performs no accelerator import, environment probing, or
runtime setup.  Pytest calls the hooks below only while it is configuring a
test run, at which point the optional accelerator plugin can be registered.
"""

from __future__ import annotations

import importlib
import importlib.util
from types import ModuleType
from typing import Any


ACCELERATOR_PLUGIN = "ipfs_accelerate_py.testing.proof_reuse.plugin"
PLUGIN_NAME = "ipfs-proof-reuse"
_OPTIONAL_ACCELERATOR_MODULE_CHAIN = frozenset(
    {
        "ipfs_accelerate_py",
        "ipfs_accelerate_py.testing",
        "ipfs_accelerate_py.testing.proof_reuse",
        ACCELERATOR_PLUGIN,
    }
)


def _accelerator_is_absent_namespace() -> bool:
    """Return whether the accelerator root is absent or namespace-only.

    An uninitialised nested gitlink is visible to Python as a PEP 420 namespace
    package.  After a failed child import its spec can have a ``NamespaceLoader``
    rather than a null loader, so namespace classification must use the stable
    origin/search-location properties instead of the loader implementation.
    """

    try:
        spec = importlib.util.find_spec("ipfs_accelerate_py")
    except (AttributeError, ImportError, ValueError):
        # If classification itself fails, retain the original import error.
        return False
    if spec is None:
        return True
    return spec.origin is None and spec.submodule_search_locations is not None


def _accelerator_plugin_is_undiscoverable() -> bool:
    """Return true only when the complete optional target has no import spec.

    The name carried by ``ModuleNotFoundError`` is not enough: a discovered
    plugin is free to import another accelerator module, or even raise a
    chain-named error itself.  Looking up the complete target lets namespace
    absence remain optional without laundering a found plugin's failure.
    """
    try:
        return importlib.util.find_spec(ACCELERATOR_PLUGIN) is None
    except ModuleNotFoundError as exc:
        # ``find_spec`` imports dotted parents on some Python versions.  A
        # missing namespace parent still means the complete target cannot be
        # discovered; any other missing name is an actionable parent failure.
        return (exc.name or "") in _OPTIONAL_ACCELERATOR_MODULE_CHAIN
    except (AttributeError, ImportError, ValueError):
        return False


def _optional_accelerator_plugin() -> ModuleType | None:
    """Return the accelerator plugin, suppressing only proven absence.

    Missing children beneath a regular accelerator package and missing
    dependencies imported by a found plugin are actionable installation errors.
    They intentionally remain visible to pytest.
    """
    try:
        return importlib.import_module(ACCELERATOR_PLUGIN)
    except ModuleNotFoundError as exc:
        if (
            (exc.name or "") in _OPTIONAL_ACCELERATOR_MODULE_CHAIN
            and _accelerator_is_absent_namespace()
            and _accelerator_plugin_is_undiscoverable()
        ):
            return None
        raise


def _register_accelerator(pluginmanager: Any) -> None:
    if pluginmanager.hasplugin(PLUGIN_NAME):
        return
    # The accelerator may also be installed as its own pytest11 entry point.
    # Register at most one implementation in that case.
    if pluginmanager.hasplugin(ACCELERATOR_PLUGIN):
        return
    plugin = _optional_accelerator_plugin()
    if plugin is not None:
        is_registered = getattr(pluginmanager, "is_registered", None)
        if is_registered is not None and is_registered(plugin):
            return
        pluginmanager.register(plugin, PLUGIN_NAME)


def pytest_addoption(parser: Any, pluginmanager: Any) -> None:
    """Register early enough for any optional plugin command-line options."""
    _register_accelerator(pluginmanager)


def pytest_configure(config: Any) -> None:
    """Cover pytest configurations that do not call ``pytest_addoption``."""
    _register_accelerator(config.pluginmanager)
