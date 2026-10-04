#!/usr/bin/env python3
"""
Test suite for Filecoin Pin backend integration with ipfs_kit_py.

Tests CLI, MCP controller, backend manager integration, and basic functionality.
"""

import pytest
import os
import sys
from pathlib import Path

# Add parent directory to path
import anyio
sys.path.insert(0, str(Path(__file__).parent.parent / "ipfs_kit_py"))


pytestmark = pytest.mark.anyio
class TestFilecoinPinIntegration:
    """Test Filecoin Pin integration with ipfs_kit_py."""
    
    def test_backend_import(self):
        """Test that Filecoin Pin backend can be imported."""
        from ipfs_kit_py.mcp.storage_manager.backends import FilecoinPinBackend
        assert FilecoinPinBackend is not None
    
    def test_backend_initialization_without_api_key(self):
        """Test backend initialization in mock mode (no API key)."""
        from ipfs_kit_py.mcp.storage_manager.backends import FilecoinPinBackend
        
        resources = {"api_key": None}
        metadata = {"default_replication": 3}
        
        backend = FilecoinPinBackend(resources, metadata)
        
        assert backend.get_name() == "filecoin_pin"
        assert backend.mock_mode
    
    def test_backend_initialization_with_api_key(self):
        """Test backend initialization with API key."""
        from ipfs_kit_py.mcp.storage_manager.backends import FilecoinPinBackend
        
        resources = {"api_key": "test_key_12345"}
        metadata = {"default_replication": 3}
        
        backend = FilecoinPinBackend(resources, metadata)
        
        assert backend.get_name() == "filecoin_pin"
        assert backend.mock_mode == False
        assert backend.api_key == "test_key_12345"
    
    def test_mock_add_content(self):
        """Test adding content in mock mode."""
        from ipfs_kit_py.mcp.storage_manager.backends import FilecoinPinBackend
        
        resources = {"api_key": None}
        metadata = {"default_replication": 3}
        backend = FilecoinPinBackend(resources, metadata)
        
        # Add content
        content = b"Test content for Filecoin Pin"
        pin_metadata = {
            "name": "test-pin",
            "description": "Test pin",
            "tags": ["test"]
        }
        
        result = backend.add_content(content, pin_metadata)
        
        assert result["success"]
        assert "cid" in result
        assert result["status"] == "pinned"
        assert result["backend"] == "filecoin_pin"
        assert result["mock"]
    
    def test_mock_get_content(self):
        """Test retrieving content in mock mode."""
        from ipfs_kit_py.mcp.storage_manager.backends import FilecoinPinBackend
        
        resources = {"api_key": None}
        metadata = {}
        backend = FilecoinPinBackend(resources, metadata)
        
        # Get content
        cid = "bafybeibtest123"
        result = backend.get_content(cid)
        
        assert result["success"]
        assert "data" in result
        assert result["cid"] == cid
        assert result["backend"] == "filecoin_pin"
        assert result["mock"]
    
    def test_mock_list_pins(self):
        """Test listing pins in mock mode."""
        from ipfs_kit_py.mcp.storage_manager.backends import FilecoinPinBackend
        
        resources = {"api_key": None}
        metadata = {}
        backend = FilecoinPinBackend(resources, metadata)
        
        # List pins
        result = backend.list_pins(limit=10)
        
        assert result["success"]
        assert "pins" in result
        assert "count" in result
        assert result["backend"] == "filecoin_pin"
        assert result["mock"]
    
    def test_mock_get_metadata(self):
        """Test getting pin metadata in mock mode."""
        from ipfs_kit_py.mcp.storage_manager.backends import FilecoinPinBackend
        
        resources = {"api_key": None}
        metadata = {}
        backend = FilecoinPinBackend(resources, metadata)
        
        # Get metadata
        cid = "bafybeibtest123"
        result = backend.get_metadata(cid)
        
        assert result["success"]
        assert result["cid"] == cid
        assert result["status"] == "pinned"
        assert "deals" in result
        assert len(result["deals"]) > 0
        assert result["backend"] == "filecoin_pin"
        assert result["mock"]
    
    def test_mock_remove_content(self):
        """Test removing content in mock mode."""
        from ipfs_kit_py.mcp.storage_manager.backends import FilecoinPinBackend
        
        resources = {"api_key": None}
        metadata = {}
        backend = FilecoinPinBackend(resources, metadata)
        
        # Remove content
        cid = "bafybeibtest123"
        result = backend.remove_content(cid)
        
        assert result["success"]
        assert result["cid"] == cid
        assert result["backend"] == "filecoin_pin"
        assert result["mock"]
    
    def test_controller_import(self):
        """Test that Filecoin Pin controller can be imported."""
        from ipfs_kit_py.mcp.controllers.filecoin_pin_controller import FilecoinPinController
        assert FilecoinPinController is not None
    
    def test_controller_initialization(self):
        """Test controller initialization."""
        from ipfs_kit_py.mcp.controllers.filecoin_pin_controller import FilecoinPinController
        
        controller = FilecoinPinController()
        assert controller is not None
    
    @pytest.mark.anyio
    async def test_controller_pin_add(self):
        """Test controller pin_add method."""
        from ipfs_kit_py.mcp.controllers.filecoin_pin_controller import (
            FilecoinPinController,
            FilecoinPinAddRequest
        )
        
        controller = FilecoinPinController()
        
        # Create request (using mock mode)
        request = FilecoinPinAddRequest(
            content="test content",
            name="test-pin",
            description="Test pin via controller"
        )
        
        result = await controller.pin_add(request)
        
        assert result["success"]
        assert "cid" in result
        assert result["backend"] == "filecoin_pin"
    
    @pytest.mark.anyio
    async def test_controller_pin_list(self):
        """Test controller pin_list method."""
        from ipfs_kit_py.mcp.controllers.filecoin_pin_controller import (
            FilecoinPinController,
            FilecoinPinListRequest
        )
        
        controller = FilecoinPinController()
        
        # Create request
        request = FilecoinPinListRequest(limit=10)
        
        result = await controller.pin_list(request)
        
        assert result["success"]
        assert "pins" in result
        assert result["backend"] == "filecoin_pin"
    
    @pytest.mark.anyio
    async def test_controller_pin_status(self):
        """Test controller pin_status method."""
        from ipfs_kit_py.mcp.controllers.filecoin_pin_controller import (
            FilecoinPinController,
            FilecoinPinStatusRequest
        )
        
        controller = FilecoinPinController()
        
        # Create request
        request = FilecoinPinStatusRequest(cid="bafybeibtest123")
        
        result = await controller.pin_status(request)
        
        assert result["success"]
        assert result["cid"] == "bafybeibtest123"
        assert result["backend"] == "filecoin_pin"
    
    @pytest.mark.anyio
    async def test_controller_pin_remove(self):
        """Test controller pin_remove method."""
        from ipfs_kit_py.mcp.controllers.filecoin_pin_controller import (
            FilecoinPinController,
            FilecoinPinRemoveRequest
        )
        
        controller = FilecoinPinController()
        
        # Create request
        request = FilecoinPinRemoveRequest(cid="bafybeibtest123")
        
        result = await controller.pin_remove(request)
        
        assert result["success"]
        assert result["cid"] == "bafybeibtest123"
        assert result["backend"] == "filecoin_pin"
    
    def test_backend_manager_initialization(self):
        """Test that backend manager can initialize Filecoin Pin backend."""
        from ipfs_kit_py.mcp.storage_manager.backend_manager import BackendManager
        
        manager = BackendManager()
        
        # Initialize backends (will add filecoin_pin if available)
        import anyio
        anyio.run(manager.initialize_default_backends)
        
        # Check if filecoin_pin backend was added
        backends = manager.list_backends()
        assert "filecoin_pin" in backends
    
    def test_storage_types_enum(self):
        """Test that FILECOIN_PIN is in StorageBackendType enum."""
        from ipfs_kit_py.mcp.storage_manager.storage_types import StorageBackendType
        
        assert hasattr(StorageBackendType, 'FILECOIN_PIN')
        assert StorageBackendType.FILECOIN_PIN == "filecoin_pin"
    
    def test_cli_import(self):
        """Test that CLI module can be imported."""
        import ipfs_kit_py.filecoin_pin_cli as cli_module
        assert cli_module is not None
    
    def test_cli_parser_setup(self):
        """Test CLI parser setup."""
        import argparse
        from ipfs_kit_py.filecoin_pin_cli import setup_filecoin_pin_parser
        
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        
        filecoin_parser = setup_filecoin_pin_parser(subparsers)
        assert filecoin_parser is not None


class TestFilecoinPinRealAPI:
    """Test Filecoin Pin with real API (requires API key)."""
    
    @pytest.mark.integration
    def test_real_api_initialization(self):
        """Test backend initialization with real API key."""
        from ipfs_kit_py.mcp.storage_manager.backends import FilecoinPinBackend
        
        api_key = os.getenv('FILECOIN_PIN_API_KEY', '')
        resources = {"api_key": api_key}
        metadata = {"default_replication": 3}
        
        backend = FilecoinPinBackend(resources, metadata)
        
        assert backend.get_name() == "filecoin_pin"
        if api_key:
            assert backend.mock_mode is False
        else:
            assert backend.mock_mode is True
    
    @pytest.mark.integration
    def test_real_api_list_pins(self):
        """Test listing pins with real API."""
        from ipfs_kit_py.mcp.storage_manager.backends import FilecoinPinBackend
        
        api_key = os.getenv('FILECOIN_PIN_API_KEY', '')
        resources = {"api_key": api_key}
        metadata = {}
        
        backend = FilecoinPinBackend(resources, metadata)
        result = backend.list_pins(limit=10)
        
        # Note: This may fail if API is not yet available
        # Just checking the structure of the response
        assert "success" in result
        assert "backend" in result
        assert result["backend"] == "filecoin_pin"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-k", "not integration"])
