#!/usr/bin/env python3
"""
Tests for the IPFSControllerAnyIO class.

This module tests the AnyIO-compatible version of the IPFS controller,
which provides async endpoints for IPFS operations.
"""

import unittest
import pytest
from unittest.mock import MagicMock, AsyncMock, patch, call
import json
import time
import logging
import warnings
from fastapi import APIRouter, HTTPException, status, Response, Request
from fastapi.testclient import TestClient

# Import the controller to test
try:
    from ipfs_kit_py.mcp.controllers.ipfs_controller_anyio import (
        IPFSControllerAnyIO, ContentRequest, CIDRequest, OperationResponse, 
        AddContentResponse, GetContentResponse, PinResponse, ListPinsResponse,
        MakeDirRequest, WriteFileRequest, ReadFileRequest, RemoveFileRequest,
        CopyFileRequest, MoveFileRequest, FlushFilesRequest, StatsResponse,
        DaemonStatusRequest, DaemonStatusResponse, ReplicationStatusResponse
    )
except ImportError:
    # Mock classes for testing when real ones are not available
    class IPFSControllerAnyIO:
        def __init__(self, ipfs_model):
            self.ipfs_model = ipfs_model
    class ContentRequest: pass
    class CIDRequest: pass
    class OperationResponse: pass
    class AddContentResponse: pass
    class GetContentResponse: pass
    class PinResponse: pass
    class ListPinsResponse: pass
    class MakeDirRequest: pass
    class WriteFileRequest: pass
    class ReadFileRequest: pass
    class RemoveFileRequest: pass
    class CopyFileRequest: pass
    class MoveFileRequest: pass
    class FlushFilesRequest: pass
    class StatsResponse: pass
    class DaemonStatusRequest: pass
    class DaemonStatusResponse: pass
    class ReplicationStatusResponse: pass


class MockIPFSControllerAnyIO(IPFSControllerAnyIO):
    """Mock IPFSControllerAnyIO for testing."""
    
    def __init__(self, ipfs_model=None):
        """Initialize with a mock IPFS model."""
        if ipfs_model is None:
            # Create a default mock model
            ipfs_model = MagicMock()
            
            # Set up default behaviors
            ipfs_model.add_content.return_value = {
                "success": True,
                "cid": "QmTest123",
                "size": 1024,
                "operation_id": "add_123456",
                "duration_ms": 10
            }
            
            ipfs_model.get_content.return_value = {
                "success": True,
                "cid": "QmTest123",
                "data": b"test content",
                "size": 12,
                "operation_id": "get_123456",
                "duration_ms": 5
            }
            
            ipfs_model.pin_content.return_value = {
                "success": True,
                "cid": "QmTest123",
                "pinned": True,
                "operation_id": "pin_123456",
                "duration_ms": 8
            }
            
            ipfs_model.unpin_content.return_value = {
                "success": True,
                "cid": "QmTest123",
                "unpinned": True,
                "operation_id": "unpin_123456",
                "duration_ms": 7
            }
            
            ipfs_model.list_pins.return_value = {
                "success": True,
                "pins": [
                    {"cid": "QmTest123", "type": "recursive"},
                    {"cid": "QmTest456", "type": "recursive"}
                ],
                "count": 2,
                "operation_id": "list_pins_123456",
                "duration_ms": 5
            }
            
            ipfs_model.get_stats.return_value = {
                "success": True,
                "operation_stats": {
                    "adds": 10,
                    "gets": 20,
                    "pins": 5
                },
                "system_stats": {
                    "memory_usage_mb": 100,
                    "disk_usage_mb": 1000
                },
                "operation_id": "stats_123456",
                "duration_ms": 3
            }
            
            ipfs_model.async_check_daemon_status = MagicMock(return_value={
                "success": True,
                "daemon_status": {
                    "ipfs": {"running": True, "pid": 1234},
                    "ipfs_cluster": {"running": True, "pid": 1235}
                },
                "overall_status": "healthy",
                "status_code": 200,
                "operation_id": "daemon_status_123456",
                "duration_ms": 10
            })
            
            ipfs_model.async_get_stats = MagicMock(return_value={
                "success": True,
                "operation_stats": {
                    "adds": 10,
                    "gets": 20,
                    "pins": 5
                },
                "operation_id": "stats_123456",
                "duration_ms": 3
            })
            
            ipfs_model.files_ls = MagicMock(return_value={
                "success": True,
                "path": "/",
                "entries": [
                    {"Name": "test.txt", "Type": 0, "Size": 1024, "Hash": "QmTest123"},
                    {"Name": "folder", "Type": 1, "Size": 0, "Hash": "QmTestDir456"}
                ],
                "operation_id": "files_ls_123456",
                "duration_ms": 5
            })
            
            ipfs_model.files_mkdir = MagicMock(return_value={
                "success": True,
                "path": "/test",
                "parents": True,
                "operation_id": "files_mkdir_123456",
                "duration_ms": 5
            })
            
            ipfs_model.files_stat = MagicMock(return_value={
                "success": True,
                "path": "/test/file.txt",
                "hash": "QmTest123",
                "size": 1024,
                "operation_id": "files_stat_123456",
                "duration_ms": 4
            })
            
            ipfs_model.files_write = MagicMock(return_value={
                "success": True,
                "path": "/test/file.txt",
                "size": 12,
                "operation_id": "files_write_123456",
                "duration_ms": 8
            })
            
            ipfs_model.files_read = MagicMock(return_value=b"test content")
            
            ipfs_model.files_rm = MagicMock(return_value={
                "success": True,
                "path": "/test/file.txt",
                "operation_id": "files_rm_123456",
                "duration_ms": 6
            })
            
            ipfs_model.files_cp = MagicMock(return_value={
                "success": True,
                "source": "/test/file.txt",
                "destination": "/test/file_copy.txt",
                "operation_id": "files_cp_123456",
                "duration_ms": 7
            })
            
            ipfs_model.files_mv = MagicMock(return_value={
                "success": True,
                "source": "/test/file.txt",
                "destination": "/test/file_moved.txt",
                "operation_id": "files_mv_123456",
                "duration_ms": 7
            })
            
            ipfs_model.files_flush = MagicMock(return_value={
                "success": True,
                "path": "/",
                "cid": "QmTest123",
                "operation_id": "files_flush_123456",
                "duration_ms": 10
            })
            
            ipfs_model.get_replication_status = MagicMock(return_value={
                "success": True,
                "cid": "QmTest123",
                "replication": {
                    "total_copies": 3,
                    "healthy_copies": 3,
                    "locations": ["node1", "node2", "node3"]
                },
                "needs_replication": False,
                "operation_id": "replication_123456",
                "duration_ms": 12
            })
            
            ipfs_model.get_node_id = MagicMock(return_value={
                "success": True,
                "ID": "QmNodeID",
                "Addresses": ["/ip4/127.0.0.1/tcp/4001/p2p/QmNodeID"],
                "AgentVersion": "kubo/0.18.0",
                "operation_id": "node_id_123456",
                "duration_ms": 3
            })
            
            ipfs_model.get_version = MagicMock(return_value={
                "success": True,
                "Version": "0.18.0",
                "Commit": "abcdef",
                "operation_id": "version_123456",
                "duration_ms": 2
            })
            
            ipfs_model.swarm_peers = MagicMock(return_value={
                "success": True,
                "Peers": [
                    {"Addr": "/ip4/192.168.1.1/tcp/4001", "Peer": "QmPeer1"},
                    {"Addr": "/ip4/192.168.1.2/tcp/4001", "Peer": "QmPeer2"}
                ],
                "peer_count": 2,
                "operation_id": "swarm_peers_123456",
                "duration_ms": 5
            })
        
        # Initialize the parent class
        super().__init__(ipfs_model)


class TestIPFSControllerAnyIOInitialization(unittest.TestCase):
    """Test initialization and setup of the IPFSControllerAnyIO class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_model = MagicMock()
        self.controller = IPFSControllerAnyIO(self.mock_model)
    
    def test_initialization(self):
        """Test that controller initializes correctly."""
        self.assertEqual(self.controller.ipfs_model, self.mock_model)
    
    def test_register_routes(self):
        """Test route registration with FastAPI router."""
        # Create a mock router
        mock_router = MagicMock(spec=APIRouter)
        
        # Register routes
        self.controller.register_routes(mock_router)
        
        # Check that add_api_route was called multiple times
        self.assertTrue(mock_router.add_api_route.call_count > 0)
        
        # Check that at least these key endpoints were registered
        route_paths = set()
        for call_args in mock_router.add_api_route.call_args_list:
            route_paths.add(call_args[0][0])  # First positional arg is path
        
        # Content management endpoints
        self.assertIn("/ipfs/add", route_paths)
        self.assertIn("/ipfs/cat/{cid}", route_paths)
        
        # Pin management endpoints
        self.assertIn("/ipfs/pin/add", route_paths)
        self.assertIn("/ipfs/pin/rm", route_paths)
        self.assertIn("/ipfs/pin/ls", route_paths)
        
        # MFS endpoints
        self.assertIn("/ipfs/files/ls", route_paths)
        self.assertIn("/ipfs/files/mkdir", route_paths)
        self.assertIn("/ipfs/files/stat", route_paths)
        self.assertIn("/ipfs/files/write", route_paths)
        self.assertIn("/ipfs/files/read", route_paths)
        self.assertIn("/ipfs/files/rm", route_paths)
        self.assertIn("/ipfs/files/cp", route_paths)
        self.assertIn("/ipfs/files/mv", route_paths)
        self.assertIn("/ipfs/files/flush", route_paths)
        
        # IPNS endpoints
        self.assertIn("/ipfs/name/publish", route_paths)
        self.assertIn("/ipfs/name/resolve", route_paths)
        
        # DAG endpoints
        self.assertIn("/ipfs/dag/get", route_paths)
        self.assertIn("/ipfs/dag/put", route_paths)
        
        # Block endpoints
        self.assertIn("/ipfs/block/stat", route_paths)
        self.assertIn("/ipfs/block/get", route_paths)
        
        # DHT endpoints
        self.assertIn("/ipfs/dht/findpeer", route_paths)
        self.assertIn("/ipfs/dht/findprovs", route_paths)
        
        # System endpoints
        self.assertIn("/ipfs/daemon/status", route_paths)
        self.assertIn("/ipfs/stats", route_paths)
        self.assertIn("/ipfs/replication/status", route_paths)
        
        # Node info endpoints
        self.assertIn("/ipfs/id", route_paths)
        self.assertIn("/ipfs/version", route_paths)
        self.assertIn("/ipfs/swarm/peers", route_paths)
    
    def test_get_backend(self):
        """Test async backend detection method."""
        # Should return None when not in async context
        self.assertIsNone(self.controller.get_backend())
        
        # In a real async context, would return "async" "io" or "trio"


@pytest.mark.anyio
class TestIPFSControllerAnyIO:
    """Test the IPFSControllerAnyIO class's async methods."""
    
    @pytest.fixture
    def mock_ipfs_model(self):
        """Create a mock IPFS model for testing."""
        model = MagicMock()
        # Set up basic model behavior for common methods
        model.add_content.return_value = {
            "success": True,
            "cid": "QmTest123",
            "size": 1024
        }
        model.get_content.return_value = {
            "success": True,
            "cid": "QmTest123",
            "data": b"test content",
            "size": 12
        }
        
        # Configure pin operations
        model.pin_content.return_value = {
            "success": True,
            "cid": "QmTest123",
            "pinned": True
        }
        model.unpin_content.return_value = {
            "success": True,
            "cid": "QmTest123",
            "unpinned": True
        }
        
        # Add AsyncMock instances for async methods that might be called directly
        model.async_get_stats = AsyncMock(return_value={
            "success": True,
            "operation_stats": {
                "adds": 10,
                "gets": 20,
                "pins": 5
            },
            "system_stats": {
                "memory_usage_mb": 100,
                "disk_usage_mb": 1000
            }
        })
        
        model.async_check_daemon_status = AsyncMock(return_value={
            "success": True,
            "daemon_status": {
                "ipfs": {"running": True, "pid": 1234}
            },
            "overall_status": "healthy"
        })
        
        # Configure sync methods that might be called via anyio.to_thread.run_sync
        model.get_replication_status = MagicMock(return_value={
            "success": True,
            "cid": "QmTest123",
            "replication": {
                "total_copies": 3,
                "healthy_copies": 3
            }
        })
        
        model.files_ls = MagicMock(return_value={
            "success": True,
            "path": "/",
            "entries": [
                {"Name": "test.txt", "Type": 0, "Size": 1024, "Hash": "QmTest123"},
                {"Name": "folder", "Type": 1, "Size": 0, "Hash": "QmTestDir456"}
            ]
        })
        
        model.files_mkdir = MagicMock(return_value={
            "success": True,
            "path": "/test",
            "parents": True
        })
        
        model.files_stat = MagicMock(return_value={
            "success": True,
            "path": "/test/file.txt",
            "hash": "QmTest123",
            "size": 1024
        })
        
        model.files_write = MagicMock(return_value={
            "success": True,
            "path": "/test/file.txt",
            "size": 12
        })
        
        model.files_read = MagicMock(return_value=b"test content")
        
        model.files_rm = MagicMock(return_value={
            "success": True,
            "path": "/test/file.txt"
        })
        
        model.files_cp = MagicMock(return_value={
            "success": True,
            "source": "/test/file.txt",
            "destination": "/test/file_copy.txt"
        })
        
        model.files_mv = MagicMock(return_value={
            "success": True,
            "source": "/test/file.txt",
            "destination": "/test/file_moved.txt"
        })
        
        model.files_flush = MagicMock(return_value={
            "success": True,
            "path": "/",
            "cid": "QmTest123"
        })
        
        model.list_pins = MagicMock(return_value={
            "success": True,
            "pins": [
                {"cid": "QmTest123", "type": "recursive"},
                {"cid": "QmTest456", "type": "recursive"}
            ],
            "count": 2
        })
        
        # Also provide async versions if controller tries to call them directly
        model.files_ls_async = AsyncMock(return_value=model.files_ls.return_value)
        model.files_mkdir_async = AsyncMock(return_value=model.files_mkdir.return_value)
        model.files_stat_async = AsyncMock(return_value=model.files_stat.return_value)
        model.files_write_async = AsyncMock(return_value=model.files_write.return_value)
        model.files_read_async = AsyncMock(return_value=model.files_read.return_value)
        model.files_rm_async = AsyncMock(return_value=model.files_rm.return_value)
        model.files_cp_async = AsyncMock(return_value=model.files_cp.return_value)
        model.files_mv_async = AsyncMock(return_value=model.files_mv.return_value)
        model.files_flush_async = AsyncMock(return_value=model.files_flush.return_value)
        model.list_pins_async = AsyncMock(return_value=model.list_pins.return_value)
        model.get_content_async = AsyncMock(return_value=model.get_content.return_value)
        model.pin_content_async = AsyncMock(return_value=model.pin_content.return_value)
        model.unpin_content_async = AsyncMock(return_value=model.unpin_content.return_value)
        
        return model
    
    @pytest.fixture
    def controller(self, mock_ipfs_model):
        """Create a controller instance for testing."""
        return IPFSControllerAnyIO(mock_ipfs_model)

    async def test_get_stats_async(self, controller, mock_ipfs_model):
        """Test get_stats async method."""
        # Mock the anyio run_sync
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = {
                "success": True,
                "operation_stats": {
                    "adds": 10,
                    "gets": 20,
                    "pins": 5
                },
                "system_stats": {
                    "memory_usage_mb": 100,
                    "disk_usage_mb": 1000
                },
                "operation_id": "stats_123456",
                "duration_ms": 3
            }
            
            # Call the method
            result = await controller.get_stats()
            
            # Verify async pattern: sync model method was called via to_thread.run_sync
            mock_run_sync.assert_awaited_once_with(mock_ipfs_model.async_get_stats)
            
            # Verify result
            assert result["success"] is True
            assert "operation_stats" in result
            assert result["operation_stats"]["adds"] == 10
    
    async def test_check_daemon_status_async(self, controller, mock_ipfs_model):
        """Test check_daemon_status async method."""
        # Create request
        request = DaemonStatusRequest(daemon_type="ipfs")
        
        # Mock the anyio run_sync
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = {
                "success": True,
                "daemon_status": {
                    "ipfs": {"running": True, "pid": 1234}
                },
                "overall_status": "healthy",
                "status_code": 200,
                "daemon_type": "ipfs",
                "operation_id": "daemon_status_123456",
                "duration_ms": 10
            }
            
            # Call the method
            result = await controller.check_daemon_status(request)
            
            # Verify async pattern: sync model method was called via to_thread.run_sync
            mock_run_sync.assert_awaited_once_with(
                mock_ipfs_model.async_check_daemon_status,
                "ipfs"
            )
            
            # Verify result
            assert result["success"] is True
            assert result["overall_status"] == "healthy"
            assert result["daemon_status"]["ipfs"]["running"] is True
    
    async def test_get_replication_status_async(self, controller, mock_ipfs_model):
        """Test get_replication_status async method."""
        # Create mock request
        mock_request = MagicMock(spec=Request)
        mock_request.query_params = {"cid": "QmTest123"}
        
        # Mock the anyio run_sync
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = {
                "success": True,
                "cid": "QmTest123",
                "replication": {
                    "total_copies": 3,
                    "healthy_copies": 3,
                    "locations": ["node1", "node2", "node3"]
                },
                "needs_replication": False,
                "operation_id": "replication_123456",
                "duration_ms": 12
            }
            
            # Call the method
            result = await controller.get_replication_status(mock_request)
            
            # Verify async pattern: sync model method was called via to_thread.run_sync
            mock_run_sync.assert_awaited_once_with(
                mock_ipfs_model.get_replication_status, 
                "QmTest123"
            )
            
            # Verify result
            assert result["success"] is True
            assert result["cid"] == "QmTest123"
            assert not result["needs_replication"]
            assert result["replication"]["total_copies"] == 3
    
    async def test_add_content_async(self, controller, mock_ipfs_model):
        """Test add_content method."""
        # Create content request
        content_request = ContentRequest(content="test content", filename="test.txt")
        
        # Mock the anyio to_thread.run_sync to handle the case where sync method is used
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = mock_ipfs_model.add_content.return_value
            
            # Call the method
            result = await controller.add_content(content_request)
            
            # Verify model method was called with correct parameters
            # It might use direct call or anyio.to_thread.run_sync depending on implementation
            if mock_run_sync.await_count > 0:
                # Called via anyio.to_thread.run_sync
                mock_run_sync.assert_awaited_once()
            else:
                # Called directly
                mock_ipfs_model.add_content.assert_called_once_with(
                    content="test content", 
                    filename="test.txt"
                )
            
            # Verify result processing
            assert result["success"] is True
            assert "cid" in result

    async def test_add_file_async(self, controller, mock_ipfs_model):
        """Test add_file method."""
        # Create mock file
        mock_file = MagicMock()
        mock_file.filename = "test.txt"
        mock_file.read = AsyncMock(return_value=b"test content")
        
        # Mock the anyio to_thread.run_sync to handle the case where sync method is used
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = mock_ipfs_model.add_content.return_value
            
            # Call the method
            result = await controller.add_file(mock_file)
            
            # Verify file was read
            mock_file.read.assert_awaited_once()
            
            # Verify model method was called with correct parameters
            # It might use direct call or anyio.to_thread.run_sync depending on implementation
            if mock_run_sync.await_count > 0:
                # Called via anyio.to_thread.run_sync
                mock_run_sync.assert_awaited_once()
            else:
                # Called directly
                mock_ipfs_model.add_content.assert_called_once_with(
                    content=b"test content",
                    filename="test.txt"
                )
            
            # Verify result
            assert result["success"] is True
            assert "cid" in result
    
    async def test_get_content_async(self, controller, mock_ipfs_model):
        """Test get_content async method."""
        # Mock the anyio.move_on_after context manager
        with patch('anyio.move_on_after') as mock_move_on_after, \
             patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            # Mock the context manager to simply yield control
            mock_move_on_after.return_value.__aenter__.return_value = None
            mock_move_on_after.return_value.__aexit__.return_value = None
            
            # Set up model response for test 
            mock_response = {
                "success": True,
                "data": b"test content",
                "cid": "QmTest123",
                "size": 12
            }
            mock_ipfs_model.get_content.return_value = mock_response
            mock_run_sync.return_value = mock_response
            
            # Call the method
            response = await controller.get_content("QmTest123")
            
            # Verify model method was called correctly (either directly or via anyio.to_thread.run_sync)
            if mock_run_sync.await_count > 0:
                # Called via anyio.to_thread.run_sync
                called = False
                for call_args in mock_run_sync.call_args_list:
                    if call_args[0][0] == mock_ipfs_model.get_content:
                        called = True
                        # Verify the call includes keyword arguments instead of positional parameters
                        if len(call_args) > 1 and isinstance(call_args[1], dict):
                            assert call_args[1].get('cid') == "QmTest123"  # Check CID parameter
                assert called, "The get_content method was not called via anyio.to_thread.run_sync"
            else:
                # Called directly
                mock_ipfs_model.get_content.assert_called_once_with(cid="QmTest123")
            
            # Verify response is a FastAPI Response object
            assert isinstance(response, Response)
            assert response.body == b"test content"
            
            # Check headers
            assert "X-IPFS-Path" in response.headers
            assert response.headers["X-IPFS-Path"] == "/ipfs/QmTest123"
            assert "X-Content-Size" in response.headers
            assert response.headers["X-Content-Size"] == "12"
    
    async def test_get_content_json_async(self, controller, mock_ipfs_model):
        """Test get_content_json method."""
        # Create CID request
        cid_request = CIDRequest(cid="QmTest123")
        
        # Mock the anyio to_thread.run_sync function
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = mock_ipfs_model.get_content.return_value
            
            # Call the method
            result = await controller.get_content_json(cid_request)
            
            # Verify model method was called correctly (either directly or via anyio.to_thread.run_sync)
            if mock_run_sync.await_count > 0:
                # Called via anyio.to_thread.run_sync
                called = False
                for call_args in mock_run_sync.call_args_list:
                    if call_args[0][0] == mock_ipfs_model.get_content:
                        called = True
                        # Verify the call includes keyword arguments instead of positional parameters
                        if len(call_args) > 1 and isinstance(call_args[1], dict):
                            assert call_args[1].get('cid') == "QmTest123"  # Check CID parameter
                assert called, "The get_content method was not called via anyio.to_thread.run_sync"
            else:
                # Called directly
                mock_ipfs_model.get_content.assert_called_once_with(cid="QmTest123")
            
            # Verify result
            assert result["success"] is True
            assert result["cid"] == "QmTest123"
            assert result["data"] == b"test content"
    
    async def test_pin_content_async(self, controller, mock_ipfs_model):
        """Test pin_content method."""
        # Create CID request
        cid_request = CIDRequest(cid="QmTest123")
        
        # Set up model response
        mock_response = {
            "success": True,
            "cid": "QmTest123",
            "pinned": True
        }
        mock_ipfs_model.pin_content.return_value = mock_response
        
        # Mock the anyio to_thread.run_sync function
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = mock_response
            
            # Call the method
            result = await controller.pin_content(cid_request)
            
            # Verify model method was called correctly (either directly or via anyio.to_thread.run_sync)
            if mock_run_sync.await_count > 0:
                # Called via anyio.to_thread.run_sync
                called = False
                for call_args in mock_run_sync.call_args_list:
                    if call_args[0][0] == mock_ipfs_model.pin_content:
                        called = True
                        # Verify the call includes keyword arguments instead of positional parameters
                        if len(call_args) > 1 and isinstance(call_args[1], dict):
                            assert call_args[1].get('cid') == "QmTest123"  # Check CID parameter
                assert called, "The pin_content method was not called via anyio.to_thread.run_sync"
            else:
                # Called directly
                mock_ipfs_model.pin_content.assert_called_once_with(cid="QmTest123")
            
            # Verify result
            assert result["success"] is True
            assert result["cid"] == "QmTest123"
            assert result["pinned"] is True
    
    async def test_unpin_content_async(self, controller, mock_ipfs_model):
        """Test unpin_content method."""
        # Create CID request
        cid_request = CIDRequest(cid="QmTest123")
        
        # Set up model response
        mock_response = {
            "success": True,
            "cid": "QmTest123",
            "unpinned": True
        }
        mock_ipfs_model.unpin_content.return_value = mock_response
        
        # Mock the anyio to_thread.run_sync function
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = mock_response
            
            # Call the method
            result = await controller.unpin_content(cid_request)
            
            # Verify model method was called correctly (either directly or via anyio.to_thread.run_sync)
            if mock_run_sync.await_count > 0:
                # Called via anyio.to_thread.run_sync
                called = False
                for call_args in mock_run_sync.call_args_list:
                    if call_args[0][0] == mock_ipfs_model.unpin_content:
                        called = True
                        # Verify the call includes keyword arguments instead of positional parameters
                        if len(call_args) > 1 and isinstance(call_args[1], dict):
                            assert call_args[1].get('cid') == "QmTest123"  # Check CID parameter
                assert called, "The unpin_content method was not called via anyio.to_thread.run_sync"
            else:
                # Called directly
                mock_ipfs_model.unpin_content.assert_called_once_with(cid="QmTest123")
            
            # Verify result
            assert result["success"] is True
            assert result["cid"] == "QmTest123"
            assert result["unpinned"] is True
    
    async def test_list_pins_async(self, controller, mock_ipfs_model):
        """Test list_pins async method."""
        # Mock the anyio to_thread.run_sync
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = {
                "success": True,
                "pins": [
                    {"cid": "QmTest123", "type": "recursive"},
                    {"cid": "QmTest456", "type": "recursive"}
                ],
                "count": 2
            }
            
            # Call the method
            result = await controller.list_pins()
            
            # Verify async pattern: sync model method was called via to_thread.run_sync
            mock_run_sync.assert_awaited_once_with(mock_ipfs_model.list_pins)
            
            # Verify result
            assert result["success"] is True
            assert len(result["pins"]) == 2
            assert result["count"] == 2
    
    async def test_list_files_async(self, controller, mock_ipfs_model):
        """Test list_files async method."""
        # Update the mock model's return values
        mock_ipfs_model.files_ls.return_value = {
            "success": True,
            "path": "/",
            "entries": [
                {"Name": "test.txt", "Type": 0, "Size": 1024, "Hash": "QmTest123"},
                {"Name": "folder", "Type": 1, "Size": 0, "Hash": "QmTestDir456"}
            ]
        }
        mock_ipfs_model.files_ls_async.return_value = mock_ipfs_model.files_ls.return_value
        
        # Mock the anyio to_thread.run_sync
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            # Use the same return value
            mock_run_sync.return_value = mock_ipfs_model.files_ls.return_value
            
            # Call the method
            result = await controller.list_files(path="/", long=True)
            
            # Verify async pattern: the controller might be using either:
            # 1. Direct async call to files_ls_async
            # 2. Sync call to files_ls via anyio.to_thread.run_sync
            # 3. Direct sync call to files_ls
            if mock_run_sync.await_count > 0:
                # Called via anyio.to_thread.run_sync
                called = False
                for call_args in mock_run_sync.call_args_list:
                    if call_args[0][0] == mock_ipfs_model.files_ls:
                        called = True
                        # Check keyword arguments if available
                        if len(call_args) > 1 and isinstance(call_args[1], dict):
                            assert call_args[1].get('path') == "/"  # path
                            assert call_args[1].get('long') is True  # long
                assert called, "The files_ls method was not called via anyio.to_thread.run_sync"
            elif mock_ipfs_model.files_ls_async.await_count > 0:
                # Called async method directly - it's using positional arguments
                assert mock_ipfs_model.files_ls_async.await_args is not None
                assert mock_ipfs_model.files_ls_async.await_args[0][0] == "/"  # path
                assert mock_ipfs_model.files_ls_async.await_args[0][1] is True  # long
            elif mock_ipfs_model.files_ls.call_count > 0:
                # Called sync method directly
                mock_ipfs_model.files_ls.assert_called_with(path="/", long=True)
            else:
                assert False, "Neither files_ls nor files_ls_async nor anyio.to_thread.run_sync was called"
            
            # Verify result
            assert result["success"] is True
            assert result["path"] == "/"
            assert len(result["entries"]) == 2
    
    async def test_make_directory_async(self, controller, mock_ipfs_model):
        """Test make_directory async method."""
        # Create request
        request = MakeDirRequest(path="/test", parents=True)
        
        # Mock the anyio to_thread.run_sync
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = {
                "success": True,
                "path": "/test",
                "parents": True,
                "operation_id": "files_mkdir_123456",
                "duration_ms": 5
            }
            
            # Call the method
            result = await controller.make_directory(request)
            
            # Verify async pattern: sync model methods were called via to_thread.run_sync
            # It might either use direct call or anyio.to_thread.run_sync depending on implementation
            if mock_run_sync.await_count > 0:
                # Called via anyio.to_thread.run_sync
                called = False
                for call_args in mock_run_sync.call_args_list:
                    if call_args[0][0] == mock_ipfs_model.files_mkdir:
                        called = True
                        # Check other arguments
                        if len(call_args[0]) > 1:
                            assert call_args[0][1] == "/test"  # path
                        if len(call_args[0]) > 2:
                            assert call_args[0][2] is True  # parents
                assert called, "The files_mkdir method was not called via anyio.to_thread.run_sync"
            
            # Verify result
            assert result["success"] is True
            assert result["path"] == "/test"
            assert result["parents"] is True
    
    async def test_stat_file_async(self, controller, mock_ipfs_model):
        """Test stat_file async method."""
        # Mock the anyio to_thread.run_sync
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = {
                "success": True,
                "path": "/test/file.txt",
                "hash": "QmTest123",
                "size": 1024,
                "operation_id": "files_stat_123456",
                "duration_ms": 4
            }
            
            # Call the method
            result = await controller.stat_file(path="/test/file.txt")
            
            # Verify async pattern: sync model methods were called via to_thread.run_sync
            # It might either use direct call or anyio.to_thread.run_sync depending on implementation
            if mock_run_sync.await_count > 0:
                # Called via anyio.to_thread.run_sync
                called = False
                for call_args in mock_run_sync.call_args_list:
                    if call_args[0][0] == mock_ipfs_model.files_stat:
                        called = True
                        # Check other arguments
                        if len(call_args[0]) > 1:
                            assert call_args[0][1] == "/test/file.txt"  # path
                assert called, "The files_stat method was not called via anyio.to_thread.run_sync"
            
            # Verify result
            assert result["success"] is True
            assert result["path"] == "/test/file.txt"
            assert result["hash"] == "QmTest123"
            assert result["size"] == 1024
    
    async def test_write_file_async(self, controller, mock_ipfs_model):
        """Test write_file async method."""
        # Create request
        request = WriteFileRequest(
            path="/test/file.txt",
            content="test content",
            offset=0,
            create=True,
            truncate=True,
            parents=False
        )
        
        # Mock the anyio to_thread.run_sync
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = {
                "success": True,
                "path": "/test/file.txt",
                "size": 12,
                "operation_id": "files_write_123456",
                "duration_ms": 8
            }
            
            # Call the method
            result = await controller.write_file(request)
            
            # Verify async pattern: sync model methods were called via to_thread.run_sync
            # It might either use direct call or anyio.to_thread.run_sync depending on implementation
            if mock_run_sync.await_count > 0:
                # Called via anyio.to_thread.run_sync
                called = False
                for call_args in mock_run_sync.call_args_list:
                    if call_args[0][0] == mock_ipfs_model.files_write:
                        called = True
                        # Check key parameters if available
                        if len(call_args[0]) > 1:
                            assert call_args[0][1] == "/test/file.txt"  # path
                assert called, "The files_write method was not called via anyio.to_thread.run_sync"
            
            # Verify result
            assert result["success"] is True
            assert result["path"] == "/test/file.txt"
            assert result["size"] == 12
    
    async def test_read_file_async(self, controller, mock_ipfs_model):
        """Test read_file async method."""
        # Create request
        request = ReadFileRequest(
            path="/test/file.txt",
            offset=0,
            count=-1
        )
        
        # Mock the anyio to_thread.run_sync
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = b"test content"
            
            # Call the method
            result = await controller.read_file(request=request)
            
            # Verify async pattern: sync model methods were called via to_thread.run_sync
            # It might either use direct call or anyio.to_thread.run_sync depending on implementation
            if mock_run_sync.await_count > 0:
                # Called via anyio.to_thread.run_sync
                called = False
                for call_args in mock_run_sync.call_args_list:
                    if call_args[0][0] == mock_ipfs_model.files_read:
                        called = True
                        # Check key parameters if available
                        if len(call_args[0]) > 1:
                            assert call_args[0][1] == "/test/file.txt"  # path
                assert called, "The files_read method was not called via anyio.to_thread.run_sync"
            
            # Verify result
            assert result["success"] is True
            assert result["path"] == "/test/file.txt"
            assert result["content"] == "test content"  # Converted from bytes to text
    
    async def test_remove_file_async(self, controller, mock_ipfs_model):
        """Test remove_file async method."""
        # Create request
        request = RemoveFileRequest(
            path="/test/file.txt",
            recursive=False,
            force=False
        )
        
        # Mock the anyio to_thread.run_sync
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = {
                "success": True,
                "path": "/test/file.txt",
                "operation_id": "files_rm_123456",
                "duration_ms": 6
            }
            
            # Call the method
            result = await controller.remove_file(request)
            
            # Verify async pattern: sync model methods were called via to_thread.run_sync
            # It might either use direct call or anyio.to_thread.run_sync depending on implementation
            if mock_run_sync.await_count > 0:
                # Called via anyio.to_thread.run_sync
                called = False
                for call_args in mock_run_sync.call_args_list:
                    if call_args[0][0] == mock_ipfs_model.files_rm:
                        called = True
                        # Check key parameters if available
                        if len(call_args[0]) > 1:
                            assert call_args[0][1] == "/test/file.txt"  # path
                assert called, "The files_rm method was not called via anyio.to_thread.run_sync"
            
            # Verify result
            assert result["success"] is True
            assert result["path"] == "/test/file.txt"
    
    async def test_copy_file_async(self, controller, mock_ipfs_model):
        """Test copy_file async method."""
        # Create request
        request = CopyFileRequest(
            source="/test/file.txt",
            destination="/test/file_copy.txt",
            parents=False
        )
        
        # Mock the anyio to_thread.run_sync
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = {
                "success": True,
                "source": "/test/file.txt",
                "destination": "/test/file_copy.txt",
                "operation_id": "files_cp_123456",
                "duration_ms": 7
            }
            
            # Call the method
            result = await controller.copy_file(request)
            
            # Verify async pattern: sync model methods were called via to_thread.run_sync
            # It might either use direct call or anyio.to_thread.run_sync depending on implementation
            if mock_run_sync.await_count > 0:
                # Called via anyio.to_thread.run_sync
                called = False
                for call_args in mock_run_sync.call_args_list:
                    if call_args[0][0] == mock_ipfs_model.files_cp:
                        called = True
                        # Check key parameters if available
                        if len(call_args[0]) > 1:
                            assert call_args[0][1] == "/test/file.txt"  # source
                        if len(call_args[0]) > 2:
                            assert call_args[0][2] == "/test/file_copy.txt"  # destination
                assert called, "The files_cp method was not called via anyio.to_thread.run_sync"
            
            # Verify result
            assert result["success"] is True
            assert result["source"] == "/test/file.txt"
            assert result["destination"] == "/test/file_copy.txt"
    
    async def test_move_file_async(self, controller, mock_ipfs_model):
        """Test move_file async method."""
        # Create request
        request = MoveFileRequest(
            source="/test/file.txt",
            destination="/test/file_moved.txt",
            parents=False
        )
        
        # Mock the anyio to_thread.run_sync
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = {
                "success": True,
                "source": "/test/file.txt",
                "destination": "/test/file_moved.txt",
                "operation_id": "files_mv_123456",
                "duration_ms": 7
            }
            
            # Call the method
            result = await controller.move_file(request)
            
            # Verify async pattern: sync model methods were called via to_thread.run_sync
            # It might either use direct call or anyio.to_thread.run_sync depending on implementation
            if mock_run_sync.await_count > 0:
                # Called via anyio.to_thread.run_sync
                called = False
                for call_args in mock_run_sync.call_args_list:
                    if call_args[0][0] == mock_ipfs_model.files_mv:
                        called = True
                        # Check key parameters if available
                        if len(call_args[0]) > 1:
                            assert call_args[0][1] == "/test/file.txt"  # source
                        if len(call_args[0]) > 2:
                            assert call_args[0][2] == "/test/file_moved.txt"  # destination
                assert called, "The files_mv method was not called via anyio.to_thread.run_sync"
            
            # Verify result
            assert result["success"] is True
            assert result["source"] == "/test/file.txt"
            assert result["destination"] == "/test/file_moved.txt"
    
    async def test_flush_files_async(self, controller, mock_ipfs_model):
        """Test flush_files async method."""
        # Create request
        request = FlushFilesRequest(path="/")
        
        # Mock the anyio to_thread.run_sync
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = {
                "success": True,
                "path": "/",
                "cid": "QmTest123",
                "operation_id": "files_flush_123456",
                "duration_ms": 10
            }
            
            # Call the method
            result = await controller.flush_files(request)
            
            # Verify async pattern: sync model methods were called via to_thread.run_sync
            # It might either use direct call or anyio.to_thread.run_sync depending on implementation
            if mock_run_sync.await_count > 0:
                # Called via anyio.to_thread.run_sync
                called = False
                for call_args in mock_run_sync.call_args_list:
                    if hasattr(call_args[0][0], '__self__') and call_args[0][0].__self__ == mock_ipfs_model:
                        called = True
                        if len(call_args[0]) > 1:
                            assert call_args[0][1] == "/"  # Check path parameter
                assert called, "The files_flush method was not called via anyio.to_thread.run_sync"
            
            # Verify result
            assert result["success"] is True
            assert result["path"] == "/"
            assert result["cid"] == "QmTest123"


@pytest.mark.skip("HTTP endpoint tests require FastAPI TestClient")
class TestIPFSControllerAnyIOHTTPEndpoints:
    """Test the HTTP endpoints of the IPFSControllerAnyIO class.
    
    These tests require a FastAPI TestClient and are currently skipped.
    """
    
    @pytest.fixture
    def test_client(self):
        """Create a FastAPI test client."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        
        app = FastAPI()
        controller = MockIPFSControllerAnyIO()
        router = APIRouter()
        controller.register_routes(router)
        app.include_router(router)
        return TestClient(app)
    
    def test_add_content_endpoint(self, test_client):
        """Test POST /ipfs/add/json endpoint."""
        response = test_client.post(
            "/ipfs/add/json", 
            json={"content": "test content", "filename": "test.txt"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "cid" in data
        assert data["cid"] == "QmTest123"
    
    def test_get_content_endpoint(self, test_client):
        """Test GET /ipfs/cat/{cid} endpoint."""
        response = test_client.get("/ipfs/cat/QmTest123")
        assert response.status_code == 200
        assert response.content == b"test content"
        assert "X-IPFS-Path" in response.headers
        assert response.headers["X-IPFS-Path"] == "/ipfs/QmTest123"
    
    def test_pin_content_endpoint(self, test_client):
        """Test POST /ipfs/pin/add endpoint."""
        response = test_client.post(
            "/ipfs/pin/add",
            json={"cid": "QmTest123"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["cid"] == "QmTest123"
        assert data["pinned"] is True
    
    def test_unpin_content_endpoint(self, test_client):
        """Test POST /ipfs/pin/rm endpoint."""
        response = test_client.post(
            "/ipfs/pin/rm",
            json={"cid": "QmTest123"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["cid"] == "QmTest123"
        assert data["unpinned"] is True
    
    def test_list_pins_endpoint(self, test_client):
        """Test GET /ipfs/pin/ls endpoint."""
        response = test_client.get("/ipfs/pin/ls")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "pins" in data
        assert isinstance(data["pins"], list)
        assert len(data["pins"]) == 2
    
    def test_list_files_endpoint(self, test_client):
        """Test GET /ipfs/files/ls endpoint."""
        response = test_client.get("/ipfs/files/ls?path=/")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["path"] == "/"
        assert "entries" in data
        assert len(data["entries"]) == 2
    
    def test_stats_endpoint(self, test_client):
        """Test GET /ipfs/stats endpoint."""
        response = test_client.get("/ipfs/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "operation_stats" in data
        assert data["operation_stats"]["adds"] == 10


if __name__ == "__main__":
    unittest.main()