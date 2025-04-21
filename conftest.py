"""
pytest configuration file.

This file contains global fixtures and configuration for pytest.
It automatically applies fixes for common test issues.
"""

import os
import sys
import pytest
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add the project root to the Python path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

# Make sure we do the imports safely
try:
    # Import our test fixes in a safe way that doesn't conflict with pytest's assertion rewriting
    test_fixes_path = project_root / 'test' / 'fix_all_tests.py'
    if test_fixes_path.exists():
        import importlib.util
        spec = importlib.util.spec_from_file_location("fix_all_tests", test_fixes_path)
        fix_all_tests = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fix_all_tests)
        
        # Apply all fixes
        fix_all_tests.apply_all_fixes()
        logger.info("Successfully applied all test fixes")
except ImportError as e:
    logger.error(f"Error importing test fixes: {e}")
except Exception as e:
    logger.error(f"Error applying test fixes: {e}")

# Global fixtures

@pytest.fixture(scope="session")
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

# Skip markers for missing dependencies
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "requires_fsspec: mark test as requiring fsspec")
    config.addinivalue_line("markers", "requires_fastapi: mark test as requiring fastapi")
    config.addinivalue_line("markers", "requires_libp2p: mark test as requiring libp2p")
    config.addinivalue_line("markers", "requires_webrtc: mark test as requiring webrtc dependencies")

def pytest_runtest_setup(item):
    """Skip tests if dependencies are missing."""
    markers = list(item.iter_markers())
    
    for marker in markers:
        if marker.name == "requires_fsspec":
            try:
                import fsspec
            except ImportError:
                pytest.skip("fsspec not installed")
                
        elif marker.name == "requires_fastapi":
            try:
                import fastapi
            except ImportError:
                pytest.skip("fastapi not installed")
                
        elif marker.name == "requires_libp2p":
            try:
                import libp2p
            except ImportError:
                pytest.skip("libp2p not installed")
                
        elif marker.name == "requires_webrtc":
            try:
                import aiortc
                import av
            except ImportError:
                pytest.skip("webrtc dependencies not installed")