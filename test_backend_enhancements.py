"""
Test file for the enhanced backend configuration and monitoring system.
"""

import pytest
import os
import json
import tempfile
from pathlib import Path

# Import our new modules
from ipfs_kit_py.metadata_manager import MetadataManager, get_metadata_manager
from ipfs_kit_py.mcp_metadata_wrapper import MetadataFirstMCP, get_metadata_first_mcp


def test_metadata_manager_initialization():
    """Test that MetadataManager initializes correctly."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        manager = MetadataManager(temp_path)
        
        # Check directories are created
        assert manager.base_dir.exists()
        assert manager.config_dir.exists()
        assert manager.backends_dir.exists()
        assert manager.metadata_dir.exists()
        assert manager.cache_dir.exists()
        assert manager.logs_dir.exists()
        
        # Check default config is created
        config_file = manager.config_dir / "main.json"
        assert config_file.exists()


def test_backend_configuration_management():
    """Test backend configuration CRUD operations."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        manager = MetadataManager(temp_path)
        
        # Test setting backend config
        backend_config = {
            "type": "s3",
            "enabled": True,
            "endpoint": "https://s3.amazonaws.com",
            "bucket": "test-bucket"
        }
        
        success = manager.set_backend_config("test-s3", backend_config)
        assert success
        
        # Test getting backend config
        retrieved_config = manager.get_backend_config("test-s3")
        assert retrieved_config is not None
        assert retrieved_config["config"]["type"] == "s3"
        assert retrieved_config["config"]["bucket"] == "test-bucket"
        
        # Test listing backends
        backends = manager.list_backends()
        assert "test-s3" in backends
        
        # Test removing backend config
        success = manager.remove_backend_config("test-s3")
        assert success
        
        # Verify removal
        retrieved_config = manager.get_backend_config("test-s3")
        assert retrieved_config is None


def test_metadata_operations():
    """Test metadata storage and retrieval."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        manager = MetadataManager(temp_path)
        
        # Test setting metadata
        test_data = {"test": "value", "number": 42}
        success = manager.set_metadata("test_key", test_data)
        assert success
        
        # Test getting metadata
        retrieved = manager.get_metadata("test_key")
        assert retrieved == test_data
        
        # Test non-existent key
        not_found = manager.get_metadata("non_existent")
        assert not_found is None


def test_global_settings():
    """Test global settings management."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        manager = MetadataManager(temp_path)
        
        # Test setting and getting global settings
        success = manager.set_global_setting("test_setting", "test_value")
        assert success
        
        value = manager.get_global_setting("test_setting")
        assert value == "test_value"
        
        # Test default value
        default_value = manager.get_global_setting("non_existent", "default")
        assert default_value == "default"


def test_mcp_metadata_wrapper():
    """Test the MCP metadata wrapper functionality."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create a metadata manager with custom path
        manager = MetadataManager(temp_path)
        
        # Create MCP wrapper
        mcp_wrapper = MetadataFirstMCP()
        mcp_wrapper.metadata_manager = manager  # Use our test manager
        
        # Test backend config operations
        test_config = {
            "type": "test",
            "enabled": True,
            "setting": "value"
        }
        
        success = mcp_wrapper.set_backend_config_metadata_first("test_backend", test_config)
        assert success
        
        retrieved = mcp_wrapper.get_backend_config_metadata_first("test_backend")
        assert retrieved is not None
        assert retrieved["config"]["type"] == "test"


def test_metadata_first_decorator():
    """Test the metadata-first decorator functionality."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        manager = MetadataManager(temp_path)
        
        mcp_wrapper = MetadataFirstMCP()
        mcp_wrapper.metadata_manager = manager
        
        # Test function that would be decorated
        call_count = 0
        
        @mcp_wrapper.metadata_first('test_function')
        def test_function(arg1, arg2="default"):
            nonlocal call_count
            call_count += 1
            return {"arg1": arg1, "arg2": arg2, "call_count": call_count}
        
        # First call should execute the function
        result1 = test_function("value1", arg2="value2")
        assert result1["call_count"] == 1
        
        # Verify metadata was stored
        stored = manager.get_metadata("test_function")
        assert stored is not None
        

def test_directory_structure_creation():
    """Test that the ~/.ipfs_kit directory structure is created properly."""
    # This test uses the actual home directory path but in a temp dir for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a fake home directory
        fake_home = Path(temp_dir) / "home"
        fake_home.mkdir()
        
        # Use a custom base path that mimics ~/.ipfs_kit
        ipfs_kit_dir = fake_home / ".ipfs_kit"
        
        manager = MetadataManager(ipfs_kit_dir)
        
        # Verify all expected directories exist
        expected_dirs = [
            "config",
            "metadata", 
            "backends",
            "cache",
            "logs"
        ]
        
        for dirname in expected_dirs:
            dir_path = ipfs_kit_dir / dirname
            assert dir_path.exists(), f"Directory {dirname} was not created"
            assert dir_path.is_dir(), f"{dirname} is not a directory"


if __name__ == "__main__":
    # Run tests directly
    test_metadata_manager_initialization()
    test_backend_configuration_management()
    test_metadata_operations()
    test_global_settings()
    test_mcp_metadata_wrapper()
    test_metadata_first_decorator()
    test_directory_structure_creation()
    
    print("All tests passed!")