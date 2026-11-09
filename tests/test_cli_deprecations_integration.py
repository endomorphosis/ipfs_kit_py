import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import urllib.request

# This integration test exercises the packaged CLI entry point end-to-end.
# It intentionally uses subprocess to mimic real user invocation rather than importing internals.

def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_cli_deprecations_lists_overview(tmp_path: Path):
    port = _free_port()
    env = os.environ.copy()
    # Start server in background (not foreground) so the deprecations command can run while it's up
    # We rely on CLI background mode launching another foreground child; this test just needs health to become ready.
    proc = subprocess.Popen([
        sys.executable, "-m", "ipfs_kit_py.cli", "mcp", "start", "--port", str(port)
    ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    # Wait for readiness via /api/system/deprecations or /healthz fallback
    deadline = time.time() + 20
    ready = False
    dep_url = f"http://127.0.0.1:{port}/api/system/deprecations"
    while time.time() < deadline and not ready:
        try:
            with urllib.request.urlopen(dep_url, timeout=1.5) as r:
                if r.status == 200:
                    ready = True
                    break
        except Exception:
            pass
        time.sleep(0.4)

    assert ready, "Server did not become ready in time"

    # Run CLI deprecations command (JSON output for easy parsing)
    result = subprocess.run([
        sys.executable, "-m", "ipfs_kit_py.cli", "mcp", "deprecations", "--port", str(port), "--json"
    ], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, f"CLI exited {result.returncode}: {result.stderr or result.stdout}"

    # Parse JSON
    try:
        data = json.loads(result.stdout)
    except Exception as e:  # pragma: no cover - diagnostic path
        raise AssertionError(f"Invalid JSON output: {e}\nRAW:\n{result.stdout}") from e
    assert isinstance(data, list), "Expected a list of deprecation entries"
    overview = next((d for d in data if d.get("endpoint") == "/api/system/overview"), None)
    assert overview is not None, "Expected overview endpoint in deprecations list"
    assert overview.get("remove_in") == "3.2.0"
    mig = overview.get("migration") or {}
    assert mig.get("health") == "/api/system/health"
    assert mig.get("status") == "/api/mcp/status"
    assert mig.get("metrics") == "/api/metrics/system"

    # Stop server via CLI
    stop_res = subprocess.run([
        sys.executable, "-m", "ipfs_kit_py.cli", "mcp", "stop", "--port", str(port)
    ], capture_output=True, text=True, timeout=15)
    # Non-zero exit is not fatal if server already exited, but we log it for diagnosis
    if stop_res.returncode != 0:  # pragma: no cover
        print("Stop command stderr:", stop_res.stderr)

    # Ensure background starter process is terminated (best-effort)
    if proc.poll() is None:  # pragma: no cover - depends on timing
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
