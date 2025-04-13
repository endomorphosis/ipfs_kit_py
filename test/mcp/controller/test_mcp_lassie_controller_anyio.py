"""
Tests for the LassieControllerAnyIO class.

These tests verify the functionality of the AnyIO version of the Lassie controller,
focusing on proper async/sync delegation and HTTP endpoint behavior.
"""

import pytest
import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import tempfile
import os
import shutil
import json
import time
import anyio

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.testclient import TestClient

# Import Pydantic models from the controller
from ipfs_kit_py.mcp_server.controllers.storage.lassie_controller import (
    FetchCIDRequest, RetrieveContentRequest, ExtractCARRequest,
    IPFSLassieRequest, LassieIPFSRequest, OperationResponse
)


class MockLassieModelAnyIO:
    """Mock of the Lassie model for testing the AnyIO controller."""
    
    def __init__(self):
        """Initialize with predefined return values for each method."""
        self.fetch_cid_return = {
            "success": True,
            "operation_id": "fetch-12345",
            "timestamp": time.time(),
            "cid": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            "path": "/path/in/cid",
            "size_bytes": 1024,
            "block_count": 5,
            "output_file": "/tmp/output.bin"
        }
        
        self.retrieve_content_return = {
            "success": True,
            "operation_id": "retrieve-12345",
            "timestamp": time.time(),
            "cid": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            "destination": "/tmp/destination",
            "extracted": True,
            "size_bytes": 2048
        }
        
        self.extract_car_return = {
            "success": True,
            "operation_id": "extract-12345",
            "timestamp": time.time(),
            "car_path": "/tmp/file.car",
            "output_dir": "/tmp/output",
            "extracted_files": ["file1.txt", "file2.jpg"],
            "root_cid": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            "size_bytes": 4096
        }
        
        self.ipfs_to_lassie_return = {
            "success": True,
            "operation_id": "ipfs2lassie-12345",
            "timestamp": time.time(),
            "ipfs_cid": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            "destination": "/tmp/from_ipfs",
            "extracted": True,
            "size_bytes": 3072
        }
        
        self.lassie_to_ipfs_return = {
            "success": True,
            "operation_id": "lassie2ipfs-12345",
            "timestamp": time.time(),
            "original_cid": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            "ipfs_cid": "bafkreihwsnuregceqh263vgdathcprnbvatyat6h6mu7ipjhhodcdbyhb4",
            "size_bytes": 2560,
            "pinned": True
        }
        
        self.check_connection_return = {
            "success": True,
            "version": "0.6.0",
            "duration_ms": 50.5
        }
        
        self.get_stats_return = {
            "total_retrievals": 100,
            "successful_retrievals": 95,
            "failed_retrievals": 5,
            "avg_retrieval_time_ms": 250.5,
            "total_bytes_retrieved": 10485760
        }
        
        # Define error returns for testing error handling
        self.error_return = {
            "success": False,
            "operation_id": "error-12345",
            "timestamp": time.time(),
            "error": "Failed to retrieve content",
            "error_type": "RetrievalError"
        }
    
    def fetch_cid(self, **kwargs):
        """Synchronous fetch_cid method."""
        return self.fetch_cid_return
    
    async def fetch_cid_async(self, **kwargs):
        """Asynchronous fetch_cid method."""
        return self.fetch_cid_return
    
    def retrieve_content(self, **kwargs):
        """Synchronous retrieve_content method."""
        return self.retrieve_content_return
    
    async def retrieve_content_async(self, **kwargs):
        """Asynchronous retrieve_content method."""
        return self.retrieve_content_return
    
    def extract_car(self, **kwargs):
        """Synchronous extract_car method."""
        return self.extract_car_return
    
    async def extract_car_async(self, **kwargs):
        """Asynchronous extract_car method."""
        return self.extract_car_return
    
    def ipfs_to_lassie(self, **kwargs):
        """Synchronous ipfs_to_lassie method."""
        return self.ipfs_to_lassie_return
    
    async def ipfs_to_lassie_async(self, **kwargs):
        """Asynchronous ipfs_to_lassie method."""
        return self.ipfs_to_lassie_return
    
    def lassie_to_ipfs(self, **kwargs):
        """Synchronous lassie_to_ipfs method."""
        return self.lassie_to_ipfs_return
    
    async def lassie_to_ipfs_async(self, **kwargs):
        """Asynchronous lassie_to_ipfs method."""
        return self.lassie_to_ipfs_return
    
    def check_connection(self):
        """Synchronous check_connection method."""
        return self.check_connection_return
    
    async def check_connection_async(self):
        """Asynchronous check_connection method."""
        return self.check_connection_return
    
    def get_stats(self):
        """Synchronous get_stats method."""
        return self.get_stats_return
    
    async def get_stats_async(self):
        """Asynchronous get_stats method."""
        return self.get_stats_return


class TestLassieControllerAnyIOInitialization(unittest.TestCase):
    """Test initialization and route registration for LassieControllerAnyIO."""
    
    def setUp(self):
        """Set up for each test."""
        self.mock_lassie_model = MockLassieModelAnyIO()
        
        # Import the controller
        from ipfs_kit_py.mcp_server.controllers.storage.lassie_controller_anyio import LassieControllerAnyIO
        
        # Create the controller
        self.controller = LassieControllerAnyIO(self.mock_lassie_model)
        
        # Create API router
        self.router = APIRouter()
    
    def test_initialization(self):
        """Test controller initialization."""
        self.assertEqual(self.controller.lassie_model, self.mock_lassie_model)
    
    def test_register_routes(self):
        """Test route registration."""
        # Register routes
        self.controller.register_routes(self.router)
        
        # Get registered paths
        route_paths = [route.path for route in self.router.routes]
        
        # Check that all expected paths are registered
        self.assertIn("/lassie/fetch", route_paths)
        self.assertIn("/lassie/retrieve", route_paths)
        self.assertIn("/lassie/extract", route_paths)
        self.assertIn("/lassie/from_ipfs", route_paths)
        self.assertIn("/lassie/to_ipfs", route_paths)
        self.assertIn("/storage/lassie/status", route_paths)
        
        # Check methods
        route_methods = {route.path: [method for method in route.methods] for route in self.router.routes}
        self.assertIn("POST", route_methods.get("/lassie/fetch", []))
        self.assertIn("POST", route_methods.get("/lassie/retrieve", []))
        self.assertIn("POST", route_methods.get("/lassie/extract", []))
        self.assertIn("POST", route_methods.get("/lassie/from_ipfs", []))
        self.assertIn("POST", route_methods.get("/lassie/to_ipfs", []))
        self.assertIn("GET", route_methods.get("/storage/lassie/status", []))


class TestLassieControllerAnyIO:
    """Test LassieControllerAnyIO with async methods."""
    
    @pytest.fixture
    def controller(self):
        """Create a LassieControllerAnyIO instance for testing."""
        from ipfs_kit_py.mcp_server.controllers.storage.lassie_controller_anyio import LassieControllerAnyIO
        
        # Create mock model
        mock_model = MockLassieModelAnyIO()
        
        # Create controller
        controller = LassieControllerAnyIO(mock_model)
        
        return controller
    
    @pytest.fixture
    def mock_lassie_model(self):
        """Create a mock Lassie model."""
        return MockLassieModelAnyIO()
    
    @pytest.mark.anyio
    async def test_handle_fetch_cid_request_async_impl(self, controller, mock_lassie_model):
        """Test handle_fetch_cid_request with async implementation."""
        # Create request
        request = FetchCIDRequest(
            cid="bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            path="/path/in/cid",
            block_limit=100,
            protocols=["bitswap", "graphsync"],
            providers=["/ip4/1.2.3.4/tcp/4001/p2p/QmPeer1"],
            dag_scope="all",
            output_file="/tmp/output.bin",
            filename="test.bin"
        )
        
        # Test with async implementation available
        with patch.object(mock_lassie_model, 'fetch_cid_async', new_callable=AsyncMock) as mock_async:
            mock_async.return_value = mock_lassie_model.fetch_cid_return
            controller.lassie_model = mock_lassie_model
            
            # Call the method
            result = await controller.handle_fetch_cid_request(request)
            
            # Verify async method was called with correct parameters
            mock_async.assert_awaited_once_with(
                cid="bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
                path="/path/in/cid",
                block_limit=100,
                protocols=["bitswap", "graphsync"],
                providers=["/ip4/1.2.3.4/tcp/4001/p2p/QmPeer1"],
                dag_scope="all",
                output_file="/tmp/output.bin",
                filename="test.bin"
            )
            
            # Verify result
            assert result["success"] is True
            assert result["cid"] == "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
            assert result["output_file"] == "/tmp/output.bin"
    
    @pytest.mark.anyio
    async def test_handle_fetch_cid_request_sync_fallback(self, controller, mock_lassie_model):
        """Test handle_fetch_cid_request with fallback to sync implementation."""
        # Create request
        request = FetchCIDRequest(
            cid="bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            path="/path/in/cid",
            block_limit=100,
            protocols=["bitswap", "graphsync"],
            providers=["/ip4/1.2.3.4/tcp/4001/p2p/QmPeer1"],
            dag_scope="all",
            output_file="/tmp/output.bin",
            filename="test.bin"
        )
        
        # Remove async implementation to test fallback
        mock_model = mock_lassie_model
        if hasattr(mock_model, 'fetch_cid_async'):
            delattr(mock_model, 'fetch_cid_async')
        
        controller.lassie_model = mock_model
        
        # Test with sync fallback
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = mock_model.fetch_cid_return
            
            # Call the method
            result = await controller.handle_fetch_cid_request(request)
            
            # Verify to_thread.run_sync was called
            mock_run_sync.assert_awaited_once()
            
            # Verify result
            assert result["success"] is True
            assert result["cid"] == "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
            assert result["output_file"] == "/tmp/output.bin"
    
    @pytest.mark.anyio
    async def test_handle_retrieve_content_request_async_impl(self, controller, mock_lassie_model):
        """Test handle_retrieve_content_request with async implementation."""
        # Create request
        request = RetrieveContentRequest(
            cid="bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            destination="/tmp/destination",
            extract=True,
            verbose=False
        )
        
        # Test with async implementation available
        with patch.object(mock_lassie_model, 'retrieve_content_async', new_callable=AsyncMock) as mock_async:
            mock_async.return_value = mock_lassie_model.retrieve_content_return
            controller.lassie_model = mock_lassie_model
            
            # Call the method
            result = await controller.handle_retrieve_content_request(request)
            
            # Verify async method was called with correct parameters
            mock_async.assert_awaited_once_with(
                cid="bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
                destination="/tmp/destination",
                extract=True,
                verbose=False
            )
            
            # Verify result
            assert result["success"] is True
            assert result["cid"] == "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
            assert result["destination"] == "/tmp/destination"
            assert result["extracted"] is True
    
    @pytest.mark.anyio
    async def test_handle_retrieve_content_request_sync_fallback(self, controller, mock_lassie_model):
        """Test handle_retrieve_content_request with fallback to sync implementation."""
        # Create request
        request = RetrieveContentRequest(
            cid="bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            destination="/tmp/destination",
            extract=True,
            verbose=False
        )
        
        # Remove async implementation to test fallback
        mock_model = mock_lassie_model
        if hasattr(mock_model, 'retrieve_content_async'):
            delattr(mock_model, 'retrieve_content_async')
        
        controller.lassie_model = mock_model
        
        # Test with sync fallback
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = mock_model.retrieve_content_return
            
            # Call the method
            result = await controller.handle_retrieve_content_request(request)
            
            # Verify to_thread.run_sync was called
            mock_run_sync.assert_awaited_once()
            
            # Verify result
            assert result["success"] is True
            assert result["cid"] == "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
            assert result["destination"] == "/tmp/destination"
            assert result["extracted"] is True
    
    @pytest.mark.anyio
    async def test_handle_extract_car_request_async_impl(self, controller, mock_lassie_model):
        """Test handle_extract_car_request with async implementation."""
        # Create request
        request = ExtractCARRequest(
            car_path="/tmp/file.car",
            output_dir="/tmp/output",
            cid="bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
        )
        
        # Test with async implementation available
        with patch.object(mock_lassie_model, 'extract_car_async', new_callable=AsyncMock) as mock_async:
            mock_async.return_value = mock_lassie_model.extract_car_return
            controller.lassie_model = mock_lassie_model
            
            # Call the method
            result = await controller.handle_extract_car_request(request)
            
            # Verify async method was called with correct parameters
            mock_async.assert_awaited_once_with(
                car_path="/tmp/file.car",
                output_dir="/tmp/output",
                cid="bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
            )
            
            # Verify result
            assert result["success"] is True
            assert result["car_path"] == "/tmp/file.car"
            assert result["output_dir"] == "/tmp/output"
            assert result["root_cid"] == "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
    
    @pytest.mark.anyio
    async def test_handle_extract_car_request_sync_fallback(self, controller, mock_lassie_model):
        """Test handle_extract_car_request with fallback to sync implementation."""
        # Create request
        request = ExtractCARRequest(
            car_path="/tmp/file.car",
            output_dir="/tmp/output",
            cid="bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
        )
        
        # Remove async implementation to test fallback
        mock_model = mock_lassie_model
        if hasattr(mock_model, 'extract_car_async'):
            delattr(mock_model, 'extract_car_async')
        
        controller.lassie_model = mock_model
        
        # Test with sync fallback
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = mock_model.extract_car_return
            
            # Call the method
            result = await controller.handle_extract_car_request(request)
            
            # Verify to_thread.run_sync was called
            mock_run_sync.assert_awaited_once()
            
            # Verify result
            assert result["success"] is True
            assert result["car_path"] == "/tmp/file.car"
            assert result["output_dir"] == "/tmp/output"
            assert result["root_cid"] == "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
    
    @pytest.mark.anyio
    async def test_handle_ipfs_to_lassie_request_async_impl(self, controller, mock_lassie_model):
        """Test handle_ipfs_to_lassie_request with async implementation."""
        # Create request
        request = IPFSLassieRequest(
            cid="bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            destination="/tmp/from_ipfs",
            extract=True
        )
        
        # Test with async implementation available
        with patch.object(mock_lassie_model, 'ipfs_to_lassie_async', new_callable=AsyncMock) as mock_async:
            mock_async.return_value = mock_lassie_model.ipfs_to_lassie_return
            controller.lassie_model = mock_lassie_model
            
            # Call the method
            result = await controller.handle_ipfs_to_lassie_request(request)
            
            # Verify async method was called with correct parameters
            mock_async.assert_awaited_once_with(
                cid="bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
                destination="/tmp/from_ipfs",
                extract=True
            )
            
            # Verify result
            assert result["success"] is True
            assert result["ipfs_cid"] == "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
            assert result["destination"] == "/tmp/from_ipfs"
            assert result["extracted"] is True
    
    @pytest.mark.anyio
    async def test_handle_ipfs_to_lassie_request_sync_fallback(self, controller, mock_lassie_model):
        """Test handle_ipfs_to_lassie_request with fallback to sync implementation."""
        # Create request
        request = IPFSLassieRequest(
            cid="bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            destination="/tmp/from_ipfs",
            extract=True
        )
        
        # Remove async implementation to test fallback
        mock_model = mock_lassie_model
        if hasattr(mock_model, 'ipfs_to_lassie_async'):
            delattr(mock_model, 'ipfs_to_lassie_async')
        
        controller.lassie_model = mock_model
        
        # Test with sync fallback
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = mock_model.ipfs_to_lassie_return
            
            # Call the method
            result = await controller.handle_ipfs_to_lassie_request(request)
            
            # Verify to_thread.run_sync was called
            mock_run_sync.assert_awaited_once()
            
            # Verify result
            assert result["success"] is True
            assert result["ipfs_cid"] == "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
            assert result["destination"] == "/tmp/from_ipfs"
            assert result["extracted"] is True
    
    @pytest.mark.anyio
    async def test_handle_lassie_to_ipfs_request_async_impl(self, controller, mock_lassie_model):
        """Test handle_lassie_to_ipfs_request with async implementation."""
        # Create request
        request = LassieIPFSRequest(
            cid="bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            pin=True,
            verbose=False
        )
        
        # Test with async implementation available
        with patch.object(mock_lassie_model, 'lassie_to_ipfs_async', new_callable=AsyncMock) as mock_async:
            mock_async.return_value = mock_lassie_model.lassie_to_ipfs_return
            controller.lassie_model = mock_lassie_model
            
            # Call the method
            result = await controller.handle_lassie_to_ipfs_request(request)
            
            # Verify async method was called with correct parameters
            mock_async.assert_awaited_once_with(
                cid="bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
                pin=True,
                verbose=False
            )
            
            # Verify result
            assert result["success"] is True
            assert result["original_cid"] == "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
            assert result["ipfs_cid"] == "bafkreihwsnuregceqh263vgdathcprnbvatyat6h6mu7ipjhhodcdbyhb4"
            assert result["pinned"] is True
    
    @pytest.mark.anyio
    async def test_handle_lassie_to_ipfs_request_sync_fallback(self, controller, mock_lassie_model):
        """Test handle_lassie_to_ipfs_request with fallback to sync implementation."""
        # Create request
        request = LassieIPFSRequest(
            cid="bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            pin=True,
            verbose=False
        )
        
        # Remove async implementation to test fallback
        mock_model = mock_lassie_model
        if hasattr(mock_model, 'lassie_to_ipfs_async'):
            delattr(mock_model, 'lassie_to_ipfs_async')
        
        controller.lassie_model = mock_model
        
        # Test with sync fallback
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = mock_model.lassie_to_ipfs_return
            
            # Call the method
            result = await controller.handle_lassie_to_ipfs_request(request)
            
            # Verify to_thread.run_sync was called
            mock_run_sync.assert_awaited_once()
            
            # Verify result
            assert result["success"] is True
            assert result["original_cid"] == "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
            assert result["ipfs_cid"] == "bafkreihwsnuregceqh263vgdathcprnbvatyat6h6mu7ipjhhodcdbyhb4"
            assert result["pinned"] is True
    
    @pytest.mark.anyio
    async def test_handle_status_request_async_impl(self, controller, mock_lassie_model):
        """Test handle_status_request with async implementation."""
        # Test with async implementation available
        with patch.object(mock_lassie_model, 'check_connection_async', new_callable=AsyncMock) as mock_check_async, \
             patch.object(mock_lassie_model, 'get_stats_async', new_callable=AsyncMock) as mock_stats_async:
            
            mock_check_async.return_value = mock_lassie_model.check_connection_return
            mock_stats_async.return_value = mock_lassie_model.get_stats_return
            controller.lassie_model = mock_lassie_model
            
            # Call the method
            result = await controller.handle_status_request()
            
            # Verify async methods were called
            mock_check_async.assert_awaited_once()
            mock_stats_async.assert_awaited_once()
            
            # Verify result
            assert result["success"] is True
            assert result["is_available"] is True
            assert result["lassie_version"] == "0.6.0"
            assert "stats" in result
            assert result["stats"]["total_retrievals"] == 100
            assert result["stats"]["successful_retrievals"] == 95
    
    @pytest.mark.anyio
    async def test_handle_status_request_sync_fallback(self, controller, mock_lassie_model):
        """Test handle_status_request with fallback to sync implementation."""
        # Remove async implementation to test fallback
        mock_model = mock_lassie_model
        if hasattr(mock_model, 'check_connection_async'):
            delattr(mock_model, 'check_connection_async')
        if hasattr(mock_model, 'get_stats_async'):
            delattr(mock_model, 'get_stats_async')
        
        controller.lassie_model = mock_model
        
        # Test with sync fallback
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.side_effect = [
                mock_model.check_connection_return,
                mock_model.get_stats_return
            ]
            
            # Call the method
            result = await controller.handle_status_request()
            
            # Verify to_thread.run_sync was called twice
            assert mock_run_sync.await_count == 2
            
            # Verify result
            assert result["success"] is True
            assert result["is_available"] is True
            assert result["lassie_version"] == "0.6.0"
            assert "stats" in result
    
    @pytest.mark.anyio
    async def test_error_handling_http_exception(self, controller, mock_lassie_model):
        """Test error handling with HTTP exception."""
        # Create request
        request = FetchCIDRequest(
            cid="bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            path="/path/in/cid"
        )
        
        # Configure model to return error
        mock_model = mock_lassie_model
        mock_model.fetch_cid_async = AsyncMock(return_value=mock_model.error_return)
        controller.lassie_model = mock_model
        
        # Call the method and check for HTTPException
        with pytest.raises(HTTPException) as excinfo:
            await controller.handle_fetch_cid_request(request)
        
        # Verify exception
        assert excinfo.value.status_code == 500
        assert "error" in excinfo.value.detail
        assert excinfo.value.detail["error"] == "Failed to retrieve content"
        assert excinfo.value.detail["error_type"] == "RetrievalError"


# We'll skip HTTP endpoint tests since they would essentially just call the async methods we already tested
# @pytest.mark.skip(reason="HTTP endpoint tests require a running server") - removed by fix_all_tests.py
class TestLassieControllerAnyIOHTTPEndpoints:
    """Tests for HTTP endpoints of the LassieControllerAnyIO."""
    
    @pytest.fixture
    def app(self):
        """Create FastAPI app with controller routes."""
        from ipfs_kit_py.mcp_server.controllers.storage.lassie_controller_anyio import LassieControllerAnyIO
        
        # Create app and router
        app = FastAPI()
        router = APIRouter()
        
        # Create mock model
        model = MockLassieModelAnyIO()
        
        # Create controller and register routes
        controller = LassieControllerAnyIO(model)
        controller.register_routes(router)
        
        # Include router in app
        app.include_router(router)
        
        return app
    
    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)
    
    def test_fetch_endpoint(self, client):
        """Test the fetch endpoint."""
        # Create request data
        request_data = {
            "cid": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            "path": "/path/in/cid",
            "output_file": "/tmp/output.bin"
        }
        
        # Send request
        response = client.post("/lassie/fetch", json=request_data)
        
        # Check response
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["cid"] == "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"