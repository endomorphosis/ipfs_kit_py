"""Pytest configuration for this repository.

Some tests in this repo historically mutated `sys.path` to run without an
installed package. A dangerous pattern is inserting the *package directory*
(e.g. `<repo>/ipfs_kit_py`) onto `sys.path`, which can accidentally expose
internal subpackages (like `ipfs_kit_py/libp2p/`) as top-level imports
(`import libp2p`), shadowing real third-party dependencies.

This conftest keeps imports stable by removing unsafe entries while still
allowing tests to import `ipfs_kit_py` in editable/installed environments.
"""

from __future__ import annotations

import importlib.util
import inspect
import os
import signal
import sys
from contextlib import suppress
from pathlib import Path
import pytest
import aiohttp


def _prepend_zero_touch_bin() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    candidate_bins = [repo_root / "bin", repo_root / "ipfs_kit_py" / "bin"]
    existing = [str(path) for path in candidate_bins if path.is_dir()]
    if not existing:
        return
    current = os.environ.get("PATH", "")
    parts = [p for p in current.split(os.pathsep) if p]
    for path in reversed(existing):
        if path not in parts:
            parts.insert(0, path)
    os.environ["PATH"] = os.pathsep.join(parts)


def _sanitize_sys_path() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    local_pkg_dir = (repo_root / "ipfs_kit_py").resolve()

    # Remove any direct insertion of the *package directory*.
    # It is safe to have repo_root on sys.path; it is NOT safe to have
    # local_pkg_dir (because it can shadow external deps via sibling folders).
    sanitized: list[str] = []
    for entry in sys.path:
        if not entry:
            sanitized.append(entry)
            continue
        try:
            resolved = Path(entry).resolve()
        except Exception:
            sanitized.append(entry)
            continue

        if resolved == local_pkg_dir:
            continue
        sanitized.append(entry)

    sys.path[:] = sanitized

    # Ensure repo_root is on sys.path so local top-level packages (like `mcp`)
    # are importable even when ipfs_kit_py is installed from site-packages.
    if (repo_root / "mcp").exists():
        # Always prefer repo_root so local top-level packages (like `mcp`) win.
        if str(repo_root) in sys.path:
            with suppress(ValueError):
                sys.path.remove(str(repo_root))
        sys.path.insert(0, str(repo_root))

    # Ensure local `mcp` wins over any third-party package named `mcp`.
    mod = sys.modules.get("mcp")
    if mod is not None:
        mod_path = getattr(mod, "__file__", "") or ""
        if str(repo_root) not in mod_path:
            sys.modules.pop("mcp", None)

    # If the package isn't importable (e.g., running tests without editable
    # install), prefer adding repo_root (not the package dir).
    # Use find_spec to avoid importing ipfs_kit_py during collection.
    if importlib.util.find_spec("ipfs_kit_py") is None:
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))


_sanitize_sys_path()
_prepend_zero_touch_bin()

if os.environ.get("IPFS_KIT_TEST_IGNORE_SIGINT", "1") == "1":
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def pytest_collectstart(collector):  # noqa: ANN001
    # Re-sanitize during collection because some test modules mutate sys.path
    # at import time.
    _sanitize_sys_path()


def pytest_collection_modifyitems(config, items):  # noqa: ANN001
    for item in items:
        func = getattr(item, "function", None) or getattr(item, "obj", None)
        if func is None or not inspect.iscoroutinefunction(func):
            continue
        if item.get_closest_marker("anyio"):
            continue
        if item.get_closest_marker("asyncio"):
            continue
        if item.get_closest_marker("trio"):
            continue
        item.add_marker(pytest.mark.anyio)


def pytest_itemcollected(item):  # noqa: ANN001
    func = getattr(item, "obj", None)
    if func is None or not inspect.iscoroutinefunction(func):
        return
    if item.get_closest_marker("anyio"):
        return
    if item.get_closest_marker("asyncio"):
        return
    if item.get_closest_marker("trio"):
        return
    item.add_marker(pytest.mark.anyio)


def pytest_runtest_setup(item):  # noqa: ANN001
    # Final guard before each test executes.
    _sanitize_sys_path()


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem):  # noqa: ANN001
    func = getattr(pyfuncitem, "obj", None)
    if func is None or not inspect.iscoroutinefunction(func):
        return None

    if (
        pyfuncitem.get_closest_marker("anyio")
        or pyfuncitem.get_closest_marker("asyncio")
        or pyfuncitem.get_closest_marker("trio")
    ):
        return None

    testargs = {
        arg: pyfuncitem.funcargs[arg]
        for arg in pyfuncitem._fixtureinfo.argnames
        if arg in pyfuncitem.funcargs
    }

    instance = getattr(pyfuncitem, "_instance", None)
    sig = inspect.signature(func)
    params = list(sig.parameters)

    import anyio

    if instance is not None and params and params[0] == "self":
        anyio.run(func, instance, **testargs)
    else:
        anyio.run(func, **testargs)

    return True


@pytest.fixture(scope="session")
def server():
    """Provide a shared MCP server instance for validation tests."""
    from ipfs_kit_py.mcp.ipfs_kit.mcp.enhanced_mcp_server_with_daemon_mgmt import (
        EnhancedMCPServerWithDaemonMgmt,
    )

    return EnhancedMCPServerWithDaemonMgmt()


@pytest.fixture(scope="session")
def anyio_backend():
    """Force anyio to use asyncio backend for tests."""
    return "asyncio"


@pytest.fixture(scope="session")
def tools(server):
    """Provide the tool list from the shared MCP server."""
    return list(getattr(server, "tools", {}).keys())


@pytest.fixture
async def session():
    """Provide an aiohttp client session for async MCP tests."""
    async with aiohttp.ClientSession() as client:
        yield client
