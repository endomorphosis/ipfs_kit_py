#!/usr/bin/env python3
"""Opt-in integration tests for backend + daemon subsystems.

These tests are gated behind `IPFS_KIT_RUN_LONG_INTEGRATION=1` and are intended
to validate basic, stable behaviors of the current codebase (not historical
adapter/helper APIs).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pytest


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

pytestmark = pytest.mark.anyio


def _skip_long_integration() -> None:
    if os.environ.get("IPFS_KIT_RUN_LONG_INTEGRATION") != "1":
        pytest.skip("Set IPFS_KIT_RUN_LONG_INTEGRATION=1 to run corrected daemon system tests")


def test_backend_manager_crud(tmp_path: Path):
    _skip_long_integration()

    from ipfs_kit_py.backend_manager import BackendManager

    manager = BackendManager(ipfs_kit_path=str(tmp_path))

    created = manager.create_backend(
        "test_backend",
        "s3",
        bucket_name="test-bucket",
        region="us-east-1",
        enabled=True,
    )
    assert isinstance(created, dict)
    assert "error" not in created

    listed = manager.list_backends()
    assert isinstance(listed, dict)
    assert listed.get("total", 0) >= 1

    shown = manager.show_backend("test_backend")
    assert isinstance(shown, dict)
    assert shown.get("name") == "test_backend"
    assert shown.get("type") == "s3"

    updated = manager.update_backend("test_backend", enabled=False)
    assert isinstance(updated, dict)
    assert updated.get("backend", {}).get("enabled") is False

    removed = manager.remove_backend("test_backend")
    assert isinstance(removed, dict)
    assert removed.get("status") == "Backend removed"


def test_intelligent_daemon_manager_smoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _skip_long_integration()

    # Avoid touching the real user HOME; the daemon manager writes under ~/.ipfs_kit.
    monkeypatch.setenv("HOME", str(tmp_path))

    from ipfs_kit_py.intelligent_daemon_manager import IntelligentDaemonManager

    daemon = IntelligentDaemonManager()
    backend_index = daemon.get_backend_index()

    # `get_backend_index()` should always return a DataFrame (possibly empty).
    import pandas as pd

    assert isinstance(backend_index, pd.DataFrame)

