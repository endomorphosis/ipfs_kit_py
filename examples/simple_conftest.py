"""
Simplified test configuration for pytest.
"""

import os
import sys
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add the project root to the Python path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

# Apply our mock modules for the lotus_kit import error
sys.path.insert(0, str(project_root / 'test'))

# Create our fix for LOTUS_KIT_AVAILABLE
from unittest.mock import MagicMock

class MockLotusKit:
    def __init__(self, *args, **kwargs):
        pass

    def check_connection(self):
        return {"success": True, "available": True}

    # Add other methods as needed...

# Create mock modules in sys.modules
lotus_module = type('module', (), {})()
lotus_module.LOTUS_KIT_AVAILABLE = True
lotus_module.lotus_kit = MockLotusKit
sys.modules['ipfs_kit_py.lotus_kit'] = lotus_module

# Basic test fixtures
import pytest

@pytest.fixture
def temp_dir(tmp_path_factory):
    """Create a temporary directory for tests."""
    return tmp_path_factory.mktemp("test_data")

@pytest.fixture
def mock_ipfs_client():
    """Provide a mock IPFS client for tests."""
    from unittest.mock import MagicMock

    client = MagicMock()
    client.add = MagicMock(return_value={"Hash": "QmTestHash"})
    client.cat = MagicMock(return_value=b"test content")
    client.id = MagicMock(return_value={"ID": "QmTestNodeId"})

    return client
