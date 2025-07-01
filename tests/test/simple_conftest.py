"""
Simplified conftest.py for testing ipfs_kit_py.

This version reduces dependencies and complexity to allow tests to run.
"""

import os
import sys
import pytest
import logging
from unittest.mock import MagicMock
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add the project root to the Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Import our test patching module
try:
    import ipfs_test_patch
    logger.info("Successfully loaded test patching module")
except ImportError as e:
    logger.error(f"Error importing test patching module: {e}")
    
# Basic fixtures

@pytest.fixture(scope="session")
def temp_dir(tmp_path_factory):
    """Create a temporary directory for tests."""
    return tmp_path_factory.mktemp("test_data")

@pytest.fixture
def mock_ipfs_client():
    """Provide a mock IPFS client for tests."""
    client = MagicMock()
    client.add = MagicMock(return_value={"Hash": "QmTestHash"})
    client.cat = MagicMock(return_value=b"test content")
    client.id = MagicMock(return_value={"ID": "QmTestNodeId"})
    return client

@pytest.fixture
def mock_ipfs(monkeypatch):
    """Mock IPFS module for isolated testing."""
    mock = MagicMock()
    mock.return_value.add.return_value = {"success": True, "cid": "QmTestCid123"}
    mock.return_value.cat.return_value = {"success": True, "data": b"test data"}
    mock.return_value.pin_add.return_value = {"success": True, "cid": "QmTestCid123"}
    monkeypatch.setattr("ipfs_kit_py.ipfs.ipfs_py", mock)
    return mock