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
import shutil
from contextlib import suppress
from pathlib import Path
import subprocess
import time
import pytest
import aiohttp
import json
import socket

collect_ignore = ["unit/test_graphrag_features.py"]


_IPFS_DAEMON_PROC: subprocess.Popen | None = None


def _ensure_project_ipfs_path() -> Path:
    """Force a project-local IPFS_PATH so tests never touch ~/.ipfs."""
    repo_root = Path(__file__).resolve().parents[1]
    ipfs_repo = Path(os.environ.get("IPFS_PATH", "") or (repo_root / ".cache" / "ipfs-repo"))
    # If env var was relative, anchor it in repo_root for stability.
    if not ipfs_repo.is_absolute():
        ipfs_repo = (repo_root / ipfs_repo).resolve()
    ipfs_repo.mkdir(parents=True, exist_ok=True)
    os.environ["IPFS_PATH"] = str(ipfs_repo)
    return ipfs_repo


def _ensure_ipfs_repo_initialized(ipfs_repo: Path) -> None:
    if (ipfs_repo / "config").exists():
        return
    if not shutil.which("ipfs"):
        return
    env = os.environ.copy()
    env["IPFS_PATH"] = str(ipfs_repo)
    subprocess.run(["ipfs", "init"], env=env, check=True, capture_output=True, text=True)


def _pick_free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _configure_ipfs_repo_ports(ipfs_repo: Path, *, force: bool = False) -> None:
    """Avoid port collisions with any already-running daemon.

    Kubo defaults to binding API on 127.0.0.1:5001 and Gateway on 8080.
    In shared environments that may already be taken.
    """
    config_path = ipfs_repo / "config"
    if not config_path.exists():
        return

    try:
        cfg = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return

    addresses = cfg.get("Addresses") or {}
    api_addr = addresses.get("API")
    gw_addr = addresses.get("Gateway")

    # Rewrite if using default ports, or if forced (e.g. after a bind failure).
    changed = False
    if isinstance(api_addr, str) and (force or api_addr.endswith("/tcp/5001")):
        addresses["API"] = f"/ip4/127.0.0.1/tcp/{_pick_free_local_port()}"
        changed = True
    if isinstance(gw_addr, str) and (force or gw_addr.endswith("/tcp/8080")):
        addresses["Gateway"] = f"/ip4/127.0.0.1/tcp/{_pick_free_local_port()}"
        changed = True

    if not changed:
        return

    cfg["Addresses"] = addresses
    config_path.write_text(json.dumps(cfg, indent=2, sort_keys=True), encoding="utf-8")

    # Remove any stale api file so the daemon rewrites it.
    api_file = ipfs_repo / "api"
    if api_file.exists():
        with suppress(Exception):
            api_file.unlink()


def _ensure_ipfs_daemon_running(ipfs_repo: Path) -> None:
    global _IPFS_DAEMON_PROC

    if not shutil.which("ipfs"):
        return

    env = os.environ.copy()
    env["IPFS_PATH"] = str(ipfs_repo)

    # If we started a daemon earlier and it died, clear it.
    if _IPFS_DAEMON_PROC is not None and _IPFS_DAEMON_PROC.poll() is not None:
        _IPFS_DAEMON_PROC = None

    # Fast-path: already running (use a daemon-only command).
    try:
        res = subprocess.run(
            ["ipfs", "swarm", "peers"],
            env=env,
            capture_output=True,
            text=True,
            timeout=2,
        )
        if res.returncode == 0:
            return
    except Exception:
        pass

    def _start_and_wait() -> tuple[bool, str, Path]:
        cache_dir = (Path(__file__).resolve().parents[1] / ".cache")
        cache_dir.mkdir(parents=True, exist_ok=True)
        log_path = cache_dir / "ipfs-daemon.log"
        log_f = open(log_path, "ab", buffering=0)

        proc = subprocess.Popen(
            ["ipfs", "daemon"],
            env=env,
            stdout=log_f,
            stderr=log_f,
            start_new_session=True,
        )

        deadline = time.time() + 30
        last_err = ""
        while time.time() < deadline:
            # If daemon exited early, bail quickly.
            if proc.poll() is not None:
                last_err = f"daemon exited with code {proc.returncode}"
                return False, last_err, log_path
            try:
                res = subprocess.run(
                    ["ipfs", "swarm", "peers"],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                if res.returncode == 0:
                    _IPFS_DAEMON_PROC = proc
                    return True, "", log_path
                last_err = (res.stderr or res.stdout or "").strip()
            except Exception as e:
                last_err = str(e)
            time.sleep(0.25)

        return False, last_err, log_path

    ok, last_err, log_path = _start_and_wait()
    if ok:
        return

    # Retry once with forced port reconfiguration (handles bind conflicts).
    with suppress(Exception):
        if _IPFS_DAEMON_PROC is not None:
            _IPFS_DAEMON_PROC.terminate()
    _IPFS_DAEMON_PROC = None

    _configure_ipfs_repo_ports(ipfs_repo, force=True)
    ok, last_err, log_path = _start_and_wait()
    if ok:
        return

    raise RuntimeError(
        f"IPFS daemon did not become ready in time. Last error: {last_err}. Log: {log_path}"
    )


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


def _force_local_mcp() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    mcp_pkg = repo_root / "mcp"
    if not mcp_pkg.exists():
        return
    # Remove any third-party mcp module to avoid shadowing.
    sys.modules.pop("mcp", None)
    init_file = mcp_pkg / "__init__.py"
    if not init_file.exists():
        return
    spec = importlib.util.spec_from_file_location("mcp", str(init_file))
    if spec is None or spec.loader is None:
        return
    module = importlib.util.module_from_spec(spec)
    module.__path__ = [str(mcp_pkg)]
    sys.modules["mcp"] = module
    spec.loader.exec_module(module)  # type: ignore[attr-defined]

    # If the package isn't importable (e.g., running tests without editable
    # install), prefer adding repo_root (not the package dir).
    # Use find_spec to avoid importing ipfs_kit_py during collection.
    if importlib.util.find_spec("ipfs_kit_py") is None:
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))


_sanitize_sys_path()
_prepend_zero_touch_bin()
_force_local_mcp()

if os.environ.get("IPFS_KIT_TEST_IGNORE_SIGINT", "1") == "1":
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def pytest_collectstart(collector):  # noqa: ANN001
    # Re-sanitize during collection because some test modules mutate sys.path
    # at import time.
    _sanitize_sys_path()
    _force_local_mcp()


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
    _force_local_mcp()


def pytest_sessionstart(session):  # noqa: ANN001
    _sanitize_sys_path()
    _force_local_mcp()
    # Warm up dataset-related shims to reduce ImportError-based skips.
    for mod_name in (
        "filesystem_journal",
        "fs_journal_monitor",
        "fs_journal_replication",
    ):
        with suppress(Exception):
            __import__(mod_name)

    # Integration tests expect a working `ipfs` CLI and daemon. Make this
    # best-effort and fully project-local (never ~/.ipfs).
    try:
        ipfs_repo = _ensure_project_ipfs_path()
        _ensure_ipfs_repo_initialized(ipfs_repo)
        _configure_ipfs_repo_ports(ipfs_repo)
        _ensure_ipfs_daemon_running(ipfs_repo)
    except Exception as e:
        # Don't hard-fail the whole suite; tests that require IPFS will fail
        # with clearer messages, and others can still run.
        logger = __import__("logging").getLogger(__name__)
        logger.warning(f"IPFS test bootstrap failed: {e}")


def pytest_sessionfinish(session, exitstatus):  # noqa: ANN001
    global _IPFS_DAEMON_PROC
    proc = _IPFS_DAEMON_PROC
    if proc is None:
        return
    _IPFS_DAEMON_PROC = None
    try:
        proc.terminate()
        proc.wait(timeout=10)
    except Exception:
        with suppress(Exception):
            proc.kill()


@pytest.fixture(autouse=True)
def _ensure_ipfs_daemon_for_mcp_verification(request):  # noqa: ANN001
    """Some tests assume an IPFS daemon is online.

    A few integration tests (notably `tests/test_mcp_tools_verification.py`) use
    the `ipfs` CLI directly and will fail if a previous test stopped the daemon.
    Ensure the daemon is up for those tests only.
    """
    path = str(getattr(request, "fspath", "") or getattr(request, "path", ""))
    if not path.endswith("test_mcp_tools_verification.py"):
        yield
        return

    try:
        ipfs_repo = _ensure_project_ipfs_path()
        _ensure_ipfs_repo_initialized(ipfs_repo)
        _configure_ipfs_repo_ports(ipfs_repo)
        _ensure_ipfs_daemon_running(ipfs_repo)
    except Exception as e:
        pytest.skip(f"IPFS daemon not available for MCP verification tests: {e}")
    yield


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

    return create_mcp_server()


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
