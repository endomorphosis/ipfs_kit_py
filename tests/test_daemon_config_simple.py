"""Deterministic smoke tests for daemon configuration components.

These tests intentionally avoid starting external daemons or invoking binaries.
They validate that the current public APIs import and behave consistently.
"""

from __future__ import annotations

import json
from pathlib import Path


def _write_minimal_ipfs_config(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    config_file = path / "config"
    config_file.write_text(
        json.dumps(
            {
                "Identity": {"PeerID": "QmTestPeer", "PrivKey": ""},
                "Addresses": {
                    "API": "/ip4/127.0.0.1/tcp/0",
                    "Gateway": "/ip4/127.0.0.1/tcp/0",
                    "Swarm": ["/ip4/127.0.0.1/tcp/0"],
                },
                "Discovery": {"MDNS": {"Enabled": False}},
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_daemon_config_manager_smoke(tmp_path, monkeypatch):
    from ipfs_kit_py.daemon_config_manager import DaemonConfigManager

    ipfs_path = tmp_path / "ipfs"
    lotus_path = tmp_path / "lotus"
    lotus_path.mkdir(parents=True, exist_ok=True)
    _write_minimal_ipfs_config(ipfs_path)

    monkeypatch.setenv("IPFS_PATH", str(ipfs_path))
    monkeypatch.setenv("LOTUS_PATH", str(lotus_path))

    manager = DaemonConfigManager()

    ipfs_status = manager.check_daemon_configuration("ipfs")
    assert ipfs_status["configured"] is True
    assert ipfs_status["valid_config"] is True

    overall = manager.check_and_configure_all_daemons()
    assert overall["success"] is True
    assert overall["all_configured"] is True


def test_enhanced_mcp_server_module_smoke():
    from fastapi import FastAPI

    from ipfs_kit_py.mcp.enhanced_mcp_server_with_config import InMemoryClusterState, create_app

    app = create_app(InMemoryClusterState(node_id="test-node", role="primary"))
    assert isinstance(app, FastAPI)
    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/health" in paths


def test_installer_ensure_daemon_configured_smoke(tmp_path):
    from ipfs_kit_py.install_ipfs import install_ipfs
    from ipfs_kit_py.install_lotus import install_lotus

    assert hasattr(install_ipfs, "ensure_daemon_configured")
    assert hasattr(install_lotus, "ensure_daemon_configured")

    ipfs_repo = tmp_path / "ipfs"
    ipfs_repo.mkdir(parents=True, exist_ok=True)
    (ipfs_repo / "config").write_text("{}", encoding="utf-8")

    ipfs_installer = install_ipfs(metadata={"ipfs_path": str(ipfs_repo), "bin_dir": str(tmp_path / "bin")})
    assert ipfs_installer.ensure_daemon_configured() is True
