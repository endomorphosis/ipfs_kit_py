import os
from pathlib import Path
from fastapi.testclient import TestClient
from ipfs_kit_py.consolidated_mcp_dashboard import ConsolidatedMCPDashboard


def test_mcp_client_serves_static_sdk(tmp_path):
    # Ensure static/mcp-sdk.js exists alongside the server file
    server_dir = Path(__file__).resolve().parents[2]
    static_sdk = server_dir / 'static' / 'mcp-sdk.js'
    assert static_sdk.exists(), f"Expected SDK at {static_sdk}"

    dash = ConsolidatedMCPDashboard({
        'data_dir': str(tmp_path),
        'host': '127.0.0.1',
        'port': 0,
        'debug': False,
    })
    client = TestClient(dash.app)

    r = client.get('/mcp-client.js')
    assert r.status_code == 200
    # Header denotes source
    assert r.headers.get('X-MCP-SDK-Source') == 'static'
    body = r.text
    assert 'MCP SDK (Browser/Node UMD)' in body
    # Shim should be appended
    assert 'MCP.listTools' in body or 'listTools' in body


def test_root_renders_beta_ui(tmp_path):
    dash = ConsolidatedMCPDashboard({
        'data_dir': str(tmp_path),
        'host': '127.0.0.1',
        'port': 0,
        'debug': False,
    })
    client = TestClient(dash.app)

    r = client.get('/')
    assert r.status_code == 200
    assert 'IPFS Kit MCP Dashboard' in r.text
    # Fallback toolrunner should be hidden inline
    assert 'toolrunner-fallback' in r.text
