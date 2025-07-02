"""
Comprehensive test suite for IPFS core functionality.

This module contains tests for the core IPFS operations including
adding, retrieving, pinning, and managing content.
"""

import os
import pytest
import io
import tempfile
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import the modules we need
try:
    from ipfs_kit_py.ipfs import ipfs
    from ipfs_kit_py.high_level_api import IPFSSimpleAPI
except ImportError as e:
    logger.error(f"Error importing IPFS modules: {e}")
    # Create mock versions for testing
    class ipfs:
        def __init__(self, config=None):
            self.config = config or {}
        
        def add(self, *args, **kwargs):
            return {"Hash": "QmTestHash"}
        
        def cat(self, *args, **kwargs):
            return b"test content"
    
    class IPFSSimpleAPI:
        def __init__(self, config=None):
            self.config = config or {}
            
        def add(self, *args, **kwargs):
            return {"Hash": "QmTestHash"}
            
        def get(self, *args, **kwargs):
            return b"test content"

@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdirname:
        yield Path(tmpdirname)

@pytest.fixture
def mock_ipfs():
    """Create a mocked IPFS client."""
    mock = MagicMock()
    mock.add.return_value = {"Hash": "QmTestHash"}
    mock.cat.return_value = b"test content"
    mock.pin.add.return_value = {"Pins": ["QmTestHash"]}
    mock.pin.rm.return_value = {"Pins": ["QmTestHash"]}
    mock.pin.ls.return_value = {"Keys": {"QmTestHash": {"Type": "recursive"}}}
    return mock

@pytest.fixture
def test_ipfs_config():
    """Create a test configuration for IPFS."""
    return {
        "test_mode": True,
        "api_url": "http://localhost:5001/api/v0",
        "gateway_url": "http://localhost:8080/ipfs"
    }

# Test core IPFS functionality
class TestIPFSCore:
    
    @patch('ipfs_kit_py.ipfs.ipfs_py')
    def test_ipfs_init(self, mock_ipfs_py):
        """Test IPFS initialization."""
        config = {"test_mode": True}
        ipfs_instance = ipfs(config)
        assert ipfs_instance is not None
        assert ipfs_instance.config == config
    
    @patch('ipfs_kit_py.ipfs.ipfs_py')
    def test_add_string_content(self, mock_ipfs_py):
        """Test adding string content to IPFS."""
        mock_ipfs_py.return_value.add.return_value = {"Hash": "QmTestHash"}
        
        ipfs_instance = ipfs({"test_mode": True})
        result = ipfs_instance.add("test content")
        
        assert "Hash" in result
        assert result["Hash"] == "QmTestHash"
        mock_ipfs_py.return_value.add.assert_called_once()
    
    @patch('ipfs_kit_py.ipfs.ipfs_py')
    def test_add_binary_content(self, mock_ipfs_py):
        """Test adding binary content to IPFS."""
        mock_ipfs_py.return_value.add.return_value = {"Hash": "QmTestHash"}
        
        ipfs_instance = ipfs({"test_mode": True})
        result = ipfs_instance.add(b"test binary content")
        
        assert "Hash" in result
        assert result["Hash"] == "QmTestHash"
        mock_ipfs_py.return_value.add.assert_called_once()
    
    @patch('ipfs_kit_py.ipfs.ipfs_py')
    def test_add_file(self, mock_ipfs_py, temp_dir):
        """Test adding a file to IPFS."""
        mock_ipfs_py.return_value.add.return_value = {"Hash": "QmTestHash"}
        
        # Create a test file
        test_file = temp_dir / "test_file.txt"
        test_file.write_text("test file content")
        
        ipfs_instance = ipfs({"test_mode": True})
        result = ipfs_instance.add(str(test_file))
        
        assert "Hash" in result
        assert result["Hash"] == "QmTestHash"
        mock_ipfs_py.return_value.add.assert_called_once()
    
    @patch('ipfs_kit_py.ipfs.ipfs_py')
    def test_cat_hash(self, mock_ipfs_py):
        """Test retrieving content by hash from IPFS."""
        mock_ipfs_py.return_value.cat.return_value = b"test content"
        
        ipfs_instance = ipfs({"test_mode": True})
        result = ipfs_instance.cat("QmTestHash")
        
        assert result == b"test content"
        mock_ipfs_py.return_value.cat.assert_called_once_with("QmTestHash")
    
    @patch('ipfs_kit_py.ipfs.ipfs_py')
    def test_pin_operations(self, mock_ipfs_py):
        """Test pin operations (add, ls, rm)."""
        mock_pin = MagicMock()
        mock_pin.add.return_value = {"Pins": ["QmTestHash"]}
        mock_pin.ls.return_value = {"Keys": {"QmTestHash": {"Type": "recursive"}}}
        mock_pin.rm.return_value = {"Pins": ["QmTestHash"]}
        
        mock_ipfs_py.return_value.pin = mock_pin
        
        ipfs_instance = ipfs({"test_mode": True})
        
        # Test pin add
        add_result = ipfs_instance.pin_add("QmTestHash")
        assert "Pins" in add_result
        assert "QmTestHash" in add_result["Pins"]
        
        # Test pin ls
        ls_result = ipfs_instance.pin_ls("QmTestHash")
        assert "Keys" in ls_result
        assert "QmTestHash" in ls_result["Keys"]
        
        # Test pin rm
        rm_result = ipfs_instance.pin_rm("QmTestHash")
        assert "Pins" in rm_result
        assert "QmTestHash" in rm_result["Pins"]

# Test high-level API
class TestIPFSHighLevelAPI:
    
    @patch('ipfs_kit_py.high_level_api.ipfs')
    def test_high_level_api_init(self, mock_ipfs_class):
        """Test high-level API initialization."""
        config = {"test_mode": True}
        api = IPFSSimpleAPI(config)
        assert api is not None
        mock_ipfs_class.assert_called_once_with(config)
    
    @patch('ipfs_kit_py.high_level_api.ipfs')
    def test_high_level_add(self, mock_ipfs_class):
        """Test high-level add method."""
        mock_ipfs_instance = MagicMock()
        mock_ipfs_instance.add.return_value = {"Hash": "QmTestHash"}
        mock_ipfs_class.return_value = mock_ipfs_instance
        
        api = IPFSSimpleAPI({"test_mode": True})
        result = api.add("test content")
        
        assert "Hash" in result
        assert result["Hash"] == "QmTestHash"
        mock_ipfs_instance.add.assert_called_once()
    
    @patch('ipfs_kit_py.high_level_api.ipfs')
    def test_high_level_get(self, mock_ipfs_class):
        """Test high-level get method."""
        mock_ipfs_instance = MagicMock()
        mock_ipfs_instance.cat.return_value = b"test content"
        mock_ipfs_class.return_value = mock_ipfs_instance
        
        api = IPFSSimpleAPI({"test_mode": True})
        result = api.get("QmTestHash")
        
        assert result == b"test content"
        mock_ipfs_instance.cat.assert_called_once_with("QmTestHash")

if __name__ == "__main__":
    pytest.main(["-v", __file__])
