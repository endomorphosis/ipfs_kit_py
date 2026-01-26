#!/usr/bin/env python3
"""
Minimal smoke test: start ConsolidatedMCPDashboard on a test port, probe status and tools, then
call server_shutdown and ensure the process exits.
"""
import anyio
import json
import os
import socket
import sys
import threading
import time
from pathlib import Path

import urllib.request

sys.path.insert(0, str(Path(__file__).parent))

from ipfs_kit_py.mcp.dashboard.consolidated_mcp_dashboard import ConsolidatedMCPDashboard  # type: ignore


def port_open(host: str, port: int, timeout: float = 0.2) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def http_get_json(url: str, timeout: float = 2.0):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        raw = r.read().decode('utf-8', 'ignore')
        try:
            return json.loads(raw)
        except Exception:
            return raw


def http_post_json(url: str, body: dict, timeout: float = 3.0):
    data = json.dumps(body).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode('utf-8', 'ignore')
        return json.loads(raw)


def run_server_in_thread(app: ConsolidatedMCPDashboard):
    def _runner():
        anyio.run(app.run)

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    return t


def main():
    host = os.environ.get('MCP_HOST', '127.0.0.1')
    port = int(os.environ.get('MCP_PORT', '8109'))
    data_dir = os.environ.get('MCP_DATA_DIR') or str(Path.home() / '.ipfs_kit')
    app = ConsolidatedMCPDashboard({'host': host, 'port': port, 'data_dir': data_dir, 'debug': False})

    t = run_server_in_thread(app)

    # wait until port open
    deadline = time.time() + 10
    while time.time() < deadline and not port_open(host, port):
        time.sleep(0.1)

    assert port_open(host, port), 'server did not open port in time'

    status = http_get_json(f'http://{host}:{port}/api/mcp/status')
    assert status.get('initialized') is True
    assert int(status.get('total_tools', 0)) >= 20

    # call a tool through JSON-RPC
    js = http_post_json(f'http://{host}:{port}/mcp/tools/call', { 'name': 'get_system_status', 'args': {} })
    assert js.get('jsonrpc') == '2.0'
    assert 'result' in js

    # shutdown
    http_post_json(f'http://{host}:{port}/mcp/tools/call', { 'name': 'server_shutdown', 'args': {} })

    # wait for thread to stop
    deadline = time.time() + 5
    while time.time() < deadline and t.is_alive():
        time.sleep(0.1)
    # The thread should stop after shutdown
    assert not t.is_alive(), 'server thread still alive after shutdown'
    return 0


if __name__ == '__main__':
    try:
        code = main()
    except AssertionError as e:
        print(f'ASSERT: {e}')
        code = 2
    except Exception as e:
        print(f'ERR: {e}')
        code = 1
    sys.exit(code)
