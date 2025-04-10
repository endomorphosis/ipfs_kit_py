#!/usr/bin/env python3
"""
Tests for the LibP2PControllerAnyIO class.

This module tests the AnyIO-compatible version of the LibP2P controller,
which provides async endpoints for libp2p operations.
"""

import unittest
import pytest
from unittest.mock import MagicMock, AsyncMock, patch, call
import json
import time
import logging
import warnings
from fastapi import APIRouter, HTTPException, status, Response

# Import the controller to test
try:
    from ipfs_kit_py.mcp.controllers.libp2p_controller_anyio import (
        LibP2PControllerAnyIO, HAS_LIBP2P, HealthResponse, PeerDiscoveryRequest,
        PeerConnectionRequest, ContentDataRequest, DHTFindPeerRequest,
        DHTProvideRequest, DHTFindProvidersRequest, PubSubPublishRequest,
        PubSubSubscribeRequest, PubSubUnsubscribeRequest, MessageHandlerRequest
    )
except ImportError:
    # Mock classes for testing when real ones are not available
    HAS_LIBP2P = False
    class LibP2PControllerAnyIO:
        def __init__(self, libp2p_model):
            self.libp2p_model = libp2p_model
            self.initialized_endpoints = set()
    class HealthResponse: pass
    class PeerDiscoveryRequest: pass
    class PeerConnectionRequest: pass
    class ContentDataRequest: pass
    class DHTFindPeerRequest: pass
    class DHTProvideRequest: pass
    class DHTFindProvidersRequest: pass
    class PubSubPublishRequest: pass
    class PubSubSubscribeRequest: pass
    class PubSubUnsubscribeRequest: pass
    class MessageHandlerRequest: pass


class MockLibP2PControllerAnyIO(LibP2PControllerAnyIO):
    """Mock LibP2PControllerAnyIO for testing."""
    
    def __init__(self, libp2p_model=None):
        """Initialize with a mock libp2p model."""
        if libp2p_model is None:
            # Create a default mock model
            libp2p_model = MagicMock()
            
            # Set up default behaviors
            libp2p_model.is_available.return_value = True
            libp2p_model.get_health.return_value = {
                "success": True,
                "libp2p_available": True,
                "peer_initialized": True,
                "peer_id": "test-peer-id",
                "addresses": ["/ip4/127.0.0.1/tcp/9999/p2p/test-peer-id"],
                "connected_peers": 5,
                "dht_peers": 10,
                "protocols": ["/ipfs/ping/1.0.0", "/ipfs/id/1.0.0"],
                "role": "worker"
            }
            
            # Set up model method return values
            libp2p_model.discover_peers.return_value = {
                "success": True,
                "peers": ["peer1", "peer2", "peer3"],
                "peer_count": 3
            }
            
            libp2p_model.connect_peer.return_value = {
                "success": True,
                "peer_id": "peer1",
                "connection_id": "conn-1234",
                "multiaddrs": ["/ip4/192.168.1.1/tcp/1234/p2p/peer1"]
            }
            
            libp2p_model.find_content.return_value = {
                "success": True,
                "providers": ["peer1", "peer2"],
                "provider_count": 2
            }
            
            libp2p_model.retrieve_content.return_value = {
                "success": True,
                "cid": "QmTest123",
                "size": 1024,
                "mime_type": "text/plain",
                "metadata": {"name": "test-file"}
            }
            
            libp2p_model.get_content.return_value = {
                "success": True,
                "cid": "QmTest123",
                "data": b"test content",
                "size": 12
            }
            
            libp2p_model.announce_content.return_value = {
                "success": True,
                "cid": "QmTest123",
                "announced_to": 5
            }
            
            libp2p_model.get_connected_peers.return_value = {
                "success": True,
                "peers": ["peer1", "peer2", "peer3"],
                "peer_count": 3
            }
            
            libp2p_model.get_peer_info.return_value = {
                "success": True,
                "peer_id": "peer1",
                "addresses": ["/ip4/192.168.1.1/tcp/1234/p2p/peer1"],
                "protocols": ["/ipfs/ping/1.0.0"],
                "connected": True,
                "connection_info": {"established": time.time() - 3600}
            }
            
            libp2p_model.get_stats.return_value = {
                "success": True,
                "operations": {
                    "discover_peers": 10,
                    "connect_peer": 5,
                    "find_content": 20
                },
                "uptime_seconds": 7200
            }
            
            libp2p_model.reset.return_value = {
                "success": True,
                "reset_timestamp": time.time()
            }
            
            libp2p_model.start.return_value = {
                "success": True,
                "action": "start",
                "status": "running"
            }
            
            libp2p_model.stop.return_value = {
                "success": True,
                "action": "stop",
                "status": "stopped"
            }
            
            libp2p_model.dht_find_peer.return_value = {
                "success": True,
                "peer_id": "peer1",
                "addresses": ["/ip4/192.168.1.1/tcp/1234/p2p/peer1"]
            }
            
            libp2p_model.dht_provide.return_value = {
                "success": True,
                "cid": "QmTest123",
                "announced_to": 10
            }
            
            libp2p_model.dht_find_providers.return_value = {
                "success": True,
                "cid": "QmTest123",
                "providers": ["peer1", "peer2"],
                "provider_count": 2
            }
            
            libp2p_model.pubsub_publish.return_value = {
                "success": True,
                "topic": "test-topic",
                "message_id": "msg-1234",
                "recipients": 5
            }
            
            libp2p_model.pubsub_subscribe.return_value = {
                "success": True,
                "topic": "test-topic",
                "subscription_id": "sub-1234",
                "handler_id": "handler-1"
            }
            
            libp2p_model.pubsub_unsubscribe.return_value = {
                "success": True,
                "topic": "test-topic",
                "subscription_id": "sub-1234",
                "handler_id": "handler-1"
            }
            
            libp2p_model.pubsub_get_topics.return_value = {
                "success": True,
                "topics": ["topic1", "topic2"],
                "topic_count": 2
            }
            
            libp2p_model.pubsub_get_peers.return_value = {
                "success": True,
                "peers": ["peer1", "peer2"],
                "peer_count": 2,
                "topic": "test-topic"
            }
            
            libp2p_model.register_message_handler.return_value = {
                "success": True,
                "handler_id": "handler-1",
                "protocol_id": "/test/protocol/1.0.0"
            }
            
            libp2p_model.unregister_message_handler.return_value = {
                "success": True,
                "handler_id": "handler-1",
                "protocol_id": "/test/protocol/1.0.0"
            }
            
            libp2p_model.list_message_handlers.return_value = {
                "success": True,
                "handlers": [
                    {
                        "handler_id": "handler-1",
                        "protocol_id": "/test/protocol/1.0.0",
                        "description": "Test handler"
                    }
                ],
                "handler_count": 1
            }
            
        # Initialize the parent class
        super().__init__(libp2p_model)


class TestLibP2PControllerAnyIOInitialization(unittest.TestCase):
    """Test initialization and setup of the LibP2PControllerAnyIO class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_model = MagicMock()
        self.controller = LibP2PControllerAnyIO(self.mock_model)
    
    def test_initialization(self):
        """Test that controller initializes correctly."""
        self.assertEqual(self.controller.libp2p_model, self.mock_model)
        self.assertIsInstance(self.controller.initialized_endpoints, set)
        self.assertEqual(len(self.controller.initialized_endpoints), 0)
    
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
        
        # Core endpoints
        self.assertIn("/libp2p/health", route_paths)
        self.assertIn("/libp2p/discover", route_paths)
        self.assertIn("/libp2p/peers", route_paths)
        self.assertIn("/libp2p/connect", route_paths)
        
        # DHT endpoints
        self.assertIn("/libp2p/dht/find_peer", route_paths)
        self.assertIn("/libp2p/dht/provide", route_paths)
        self.assertIn("/libp2p/dht/find_providers", route_paths)
        
        # PubSub endpoints
        self.assertIn("/libp2p/pubsub/publish", route_paths)
        self.assertIn("/libp2p/pubsub/subscribe", route_paths)
        self.assertIn("/libp2p/pubsub/unsubscribe", route_paths)
        self.assertIn("/libp2p/pubsub/topics", route_paths)
        self.assertIn("/libp2p/pubsub/peers", route_paths)
        
        # Handler endpoints
        self.assertIn("/libp2p/handlers/register", route_paths)
        self.assertIn("/libp2p/handlers/unregister", route_paths)
        self.assertIn("/libp2p/handlers/list", route_paths)
        
        # Verify that initialized_endpoints was updated
        self.assertTrue(len(self.controller.initialized_endpoints) > 0)
        self.assertEqual(len(self.controller.initialized_endpoints), len(route_paths))
    
    def test_register_routes_idempotent(self):
        """Test that registering routes multiple times is idempotent."""
        mock_router = MagicMock(spec=APIRouter)
        
        # Register routes twice
        self.controller.register_routes(mock_router)
        call_count = mock_router.add_api_route.call_count
        
        self.controller.register_routes(mock_router)
        new_call_count = mock_router.add_api_route.call_count
        
        # Second call should not register any new routes
        self.assertEqual(call_count, new_call_count)
    
    def test_backend_detection(self):
        """Test async backend detection method."""
        # Should return None when not in async context
        self.assertIsNone(self.controller.get_backend())
        
        # In a real async context, would return "asyncio" or "trio"


@pytest.mark.anyio
class TestLibP2PControllerAnyIO:
    """Test the LibP2PControllerAnyIO class's async methods."""
    
    @pytest.fixture
    def mock_libp2p_model(self):
        """Create a mock libp2p model for testing."""
        model = MagicMock()
        model.get_health.return_value = {
            "success": True,
            "libp2p_available": True,
            "peer_initialized": True,
            "peer_id": "test-peer-id"
        }
        model.is_available.return_value = True
        return model
    
    @pytest.fixture
    def controller(self, mock_libp2p_model):
        """Create a controller instance for testing."""
        return LibP2PControllerAnyIO(mock_libp2p_model)
    
    async def test_health_check_async(self, controller, mock_libp2p_model):
        """Test health_check_async method."""
        # Mock the anyio run_sync
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = {
                "success": True,
                "libp2p_available": True,
                "peer_initialized": True,
                "peer_id": "test-peer-id",
                "addresses": ["/ip4/127.0.0.1/tcp/4001/p2p/test-peer-id"]
            }
            
            # Call the method
            result = await controller.health_check_async()
            
            # Verify async pattern: sync model method was called via to_thread.run_sync
            mock_run_sync.assert_awaited_once_with(mock_libp2p_model.get_health)
            
            # Verify result
            assert result["success"] is True
            assert result["peer_id"] == "test-peer-id"
    
    async def test_health_check_async_error(self, controller, mock_libp2p_model):
        """Test health_check_async method with error response."""
        # Mock the anyio run_sync to return error
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = {
                "success": False,
                "libp2p_available": False,
                "peer_initialized": False,
                "error": "libp2p service unavailable",
                "error_type": "service_error"
            }
            
            # Call the method and expect exception
            with pytest.raises(HTTPException) as excinfo:
                await controller.health_check_async()
            
            # Verify exception details
            assert excinfo.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            assert "libp2p service unavailable" in excinfo.value.detail
    
    async def test_discover_peers_async(self, controller, mock_libp2p_model):
        """Test discover_peers_async method."""
        # Create request
        request = PeerDiscoveryRequest(
            discovery_method="all",
            limit=10
        )
        
        # Mock the anyio run_sync calls
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            # First call for is_available
            mock_run_sync.side_effect = [
                True,  # is_available
                {  # discover_peers
                    "success": True,
                    "peers": ["peer1", "peer2", "peer3"],
                    "peer_count": 3
                }
            ]
            
            # Call the method
            result = await controller.discover_peers_async(request)
            
            # Verify async pattern: sync model methods were called via to_thread.run_sync
            assert mock_run_sync.await_count == 2
            calls = [
                call(mock_libp2p_model.is_available),
                call(mock_libp2p_model.discover_peers, discovery_method="all", limit=10)
            ]
            mock_run_sync.assert_has_awaits(calls)
            
            # Verify result
            assert result["success"] is True
            assert len(result["peers"]) == 3
            assert "peer1" in result["peers"]
    
    async def test_get_peers_async(self, controller, mock_libp2p_model):
        """Test get_peers_async method."""
        # Mock the anyio run_sync calls
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            # First call for is_available
            mock_run_sync.side_effect = [
                True,  # is_available
                {  # discover_peers
                    "success": True,
                    "peers": ["peer1", "peer2", "peer3"],
                    "peer_count": 3
                }
            ]
            
            # Call the method with default parameters
            result = await controller.get_peers_async()
            
            # Verify async pattern: sync model methods were called via to_thread.run_sync
            assert mock_run_sync.await_count == 2
            calls = [
                call(mock_libp2p_model.is_available),
                call(mock_libp2p_model.discover_peers, discovery_method="all", limit=10)
            ]
            mock_run_sync.assert_has_awaits(calls)
            
            # Verify result
            assert result["success"] is True
            assert len(result["peers"]) == 3
            assert "peer1" in result["peers"]
    
    async def test_connect_peer_async(self, controller, mock_libp2p_model):
        """Test connect_peer_async method."""
        # Create request
        request = PeerConnectionRequest(
            peer_addr="/ip4/192.168.1.1/tcp/4001/p2p/QmPeerTest"
        )
        
        # Mock the anyio run_sync calls
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            # First call for is_available
            mock_run_sync.side_effect = [
                True,  # is_available
                {  # connect_peer
                    "success": True,
                    "peer_id": "QmPeerTest",
                    "connection_id": "conn-1234"
                }
            ]
            
            # Call the method
            result = await controller.connect_peer_async(request)
            
            # Verify async pattern: sync model methods were called via to_thread.run_sync
            assert mock_run_sync.await_count == 2
            calls = [
                call(mock_libp2p_model.is_available),
                call(mock_libp2p_model.connect_peer, peer_addr="/ip4/192.168.1.1/tcp/4001/p2p/QmPeerTest")
            ]
            mock_run_sync.assert_has_awaits(calls)
            
            # Verify result
            assert result["success"] is True
            assert result["connection_id"] == "conn-1234"
    
    async def test_find_providers_async(self, controller, mock_libp2p_model):
        """Test find_providers_async method."""
        # Mock the anyio run_sync calls
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            # First call for is_available
            mock_run_sync.side_effect = [
                True,  # is_available
                {  # find_content
                    "success": True,
                    "providers": ["peer1", "peer2"],
                    "provider_count": 2
                }
            ]
            
            # Call the method
            result = await controller.find_providers_async(cid="QmTest123", timeout=30)
            
            # Verify async pattern: sync model methods were called via to_thread.run_sync
            assert mock_run_sync.await_count == 2
            calls = [
                call(mock_libp2p_model.is_available),
                call(mock_libp2p_model.find_content, cid="QmTest123", timeout=30)
            ]
            mock_run_sync.assert_has_awaits(calls)
            
            # Verify result
            assert result["success"] is True
            assert len(result["providers"]) == 2
            assert "peer1" in result["providers"]
    
    async def test_retrieve_content_info_async(self, controller, mock_libp2p_model):
        """Test retrieve_content_info_async method."""
        # Mock the anyio run_sync calls
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            # First call for is_available
            mock_run_sync.side_effect = [
                True,  # is_available
                {  # retrieve_content
                    "success": True,
                    "cid": "QmTest123",
                    "size": 1024,
                    "metadata": {"name": "test-file"}
                }
            ]
            
            # Call the method
            result = await controller.retrieve_content_info_async(cid="QmTest123", timeout=60)
            
            # Verify async pattern: sync model methods were called via to_thread.run_sync
            assert mock_run_sync.await_count == 2
            calls = [
                call(mock_libp2p_model.is_available),
                call(mock_libp2p_model.retrieve_content, cid="QmTest123", timeout=60)
            ]
            mock_run_sync.assert_has_awaits(calls)
            
            # Verify result
            assert result["success"] is True
            assert result["cid"] == "QmTest123"
            assert result["size"] == 1024
    
    async def test_retrieve_content_async(self, controller, mock_libp2p_model):
        """Test retrieve_content_async method."""
        # Mock the anyio run_sync calls
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            # First call for is_available
            mock_run_sync.side_effect = [
                True,  # is_available
                {  # get_content
                    "success": True,
                    "cid": "QmTest123",
                    "data": b"test content",
                    "size": 12
                }
            ]
            
            # Call the method
            response = await controller.retrieve_content_async(cid="QmTest123", timeout=60)
            
            # Verify async pattern: sync model methods were called via to_thread.run_sync
            assert mock_run_sync.await_count == 2
            calls = [
                call(mock_libp2p_model.is_available),
                call(mock_libp2p_model.get_content, cid="QmTest123", timeout=60)
            ]
            mock_run_sync.assert_has_awaits(calls)
            
            # Verify response is a FastAPI Response with correct content
            assert isinstance(response, Response)
            assert response.body == b"test content"
            assert response.headers["X-Content-CID"] == "QmTest123"
            assert response.headers["X-Content-Size"] == "12"
    
    async def test_announce_content_async(self, controller, mock_libp2p_model):
        """Test announce_content_async method."""
        # Create request
        request = ContentDataRequest(
            cid="QmTest123",
            data=b"test content"
        )
        
        # Mock the anyio run_sync calls
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            # First call for is_available
            mock_run_sync.side_effect = [
                True,  # is_available
                {  # announce_content
                    "success": True,
                    "cid": "QmTest123",
                    "announced_to": 5
                }
            ]
            
            # Call the method
            result = await controller.announce_content_async(request)
            
            # Verify async pattern: sync model methods were called via to_thread.run_sync
            assert mock_run_sync.await_count == 2
            calls = [
                call(mock_libp2p_model.is_available),
                call(mock_libp2p_model.announce_content, cid="QmTest123", data=b"test content")
            ]
            mock_run_sync.assert_has_awaits(calls)
            
            # Verify result
            assert result["success"] is True
            assert result["cid"] == "QmTest123"
            assert result["announced_to"] == 5
    
    async def test_get_connected_peers_async(self, controller, mock_libp2p_model):
        """Test get_connected_peers_async method."""
        # Mock the anyio run_sync calls
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            # First call for is_available
            mock_run_sync.side_effect = [
                True,  # is_available
                {  # get_connected_peers
                    "success": True,
                    "peers": ["peer1", "peer2", "peer3"],
                    "peer_count": 3
                }
            ]
            
            # Call the method
            result = await controller.get_connected_peers_async()
            
            # Verify async pattern: sync model methods were called via to_thread.run_sync
            assert mock_run_sync.await_count == 2
            calls = [
                call(mock_libp2p_model.is_available),
                call(mock_libp2p_model.get_connected_peers)
            ]
            mock_run_sync.assert_has_awaits(calls)
            
            # Verify result
            assert result["success"] is True
            assert len(result["peers"]) == 3
            assert "peer1" in result["peers"]
    
    async def test_get_peer_info_async(self, controller, mock_libp2p_model):
        """Test get_peer_info_async method."""
        # Mock the anyio run_sync calls
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            # First call for is_available
            mock_run_sync.side_effect = [
                True,  # is_available
                {  # get_peer_info
                    "success": True,
                    "peer_id": "peer1",
                    "addresses": ["/ip4/192.168.1.1/tcp/4001/p2p/peer1"],
                    "protocols": ["/ipfs/ping/1.0.0"],
                    "connected": True
                }
            ]
            
            # Call the method
            result = await controller.get_peer_info_async(peer_id="peer1")
            
            # Verify async pattern: sync model methods were called via to_thread.run_sync
            assert mock_run_sync.await_count == 2
            calls = [
                call(mock_libp2p_model.is_available),
                call(mock_libp2p_model.get_peer_info, peer_id="peer1")
            ]
            mock_run_sync.assert_has_awaits(calls)
            
            # Verify result
            assert result["success"] is True
            assert result["peer_id"] == "peer1"
            assert result["connected"] is True
    
    async def test_get_stats_async(self, controller, mock_libp2p_model):
        """Test get_stats_async method."""
        # Mock the anyio run_sync calls
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = {
                "success": True,
                "operations": {
                    "discover_peers": 10,
                    "connect_peer": 5
                },
                "uptime_seconds": 7200
            }
            
            # Call the method
            result = await controller.get_stats_async()
            
            # Verify async pattern: sync model method was called via to_thread.run_sync
            mock_run_sync.assert_awaited_once_with(mock_libp2p_model.get_stats)
            
            # Verify result
            assert result["success"] is True
            assert "operations" in result
            assert result["uptime_seconds"] == 7200
    
    async def test_reset_async(self, controller, mock_libp2p_model):
        """Test reset_async method."""
        # Mock the anyio run_sync calls
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = {
                "success": True,
                "reset_timestamp": time.time()
            }
            
            # Call the method
            result = await controller.reset_async()
            
            # Verify async pattern: sync model method was called via to_thread.run_sync
            mock_run_sync.assert_awaited_once_with(mock_libp2p_model.reset)
            
            # Verify result
            assert result["success"] is True
            assert "reset_timestamp" in result
    
    async def test_start_peer_async(self, controller, mock_libp2p_model):
        """Test start_peer_async method."""
        # Mock the anyio run_sync calls
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = {
                "success": True,
                "action": "start",
                "status": "running"
            }
            
            # Call the method
            result = await controller.start_peer_async()
            
            # Verify async pattern: sync model method was called via to_thread.run_sync
            mock_run_sync.assert_awaited_once_with(mock_libp2p_model.start)
            
            # Verify result
            assert result["success"] is True
            assert result["action"] == "start"
            assert result["status"] == "running"
    
    async def test_stop_peer_async(self, controller, mock_libp2p_model):
        """Test stop_peer_async method."""
        # Mock the anyio run_sync calls
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = {
                "success": True,
                "action": "stop",
                "status": "stopped"
            }
            
            # Call the method
            result = await controller.stop_peer_async()
            
            # Verify async pattern: sync model method was called via to_thread.run_sync
            mock_run_sync.assert_awaited_once_with(mock_libp2p_model.stop)
            
            # Verify result
            assert result["success"] is True
            assert result["action"] == "stop"
            assert result["status"] == "stopped"
    
    async def test_dht_find_peer_async(self, controller, mock_libp2p_model):
        """Test dht_find_peer_async method."""
        # Create request
        request = DHTFindPeerRequest(
            peer_id="QmPeerTest",
            timeout=30
        )
        
        # Mock the anyio run_sync calls
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            # First call for is_available
            mock_run_sync.side_effect = [
                True,  # is_available
                {  # dht_find_peer
                    "success": True,
                    "peer_id": "QmPeerTest",
                    "addresses": ["/ip4/192.168.1.1/tcp/4001/p2p/QmPeerTest"]
                }
            ]
            
            # Call the method
            result = await controller.dht_find_peer_async(request)
            
            # Verify async pattern: sync model methods were called via to_thread.run_sync
            assert mock_run_sync.await_count == 2
            calls = [
                call(mock_libp2p_model.is_available),
                call(mock_libp2p_model.dht_find_peer, peer_id="QmPeerTest", timeout=30)
            ]
            mock_run_sync.assert_has_awaits(calls)
            
            # Verify result
            assert result["success"] is True
            assert result["peer_id"] == "QmPeerTest"
            assert len(result["addresses"]) == 1
    
    async def test_dht_provide_async(self, controller, mock_libp2p_model):
        """Test dht_provide_async method."""
        # Create request
        request = DHTProvideRequest(
            cid="QmTest123"
        )
        
        # Mock the anyio run_sync calls
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            # First call for is_available
            mock_run_sync.side_effect = [
                True,  # is_available
                {  # dht_provide
                    "success": True,
                    "cid": "QmTest123",
                    "announced_to": 10
                }
            ]
            
            # Call the method
            result = await controller.dht_provide_async(request)
            
            # Verify async pattern: sync model methods were called via to_thread.run_sync
            assert mock_run_sync.await_count == 2
            calls = [
                call(mock_libp2p_model.is_available),
                call(mock_libp2p_model.dht_provide, cid="QmTest123")
            ]
            mock_run_sync.assert_has_awaits(calls)
            
            # Verify result
            assert result["success"] is True
            assert result["cid"] == "QmTest123"
            assert result["announced_to"] == 10
    
    async def test_dht_find_providers_async(self, controller, mock_libp2p_model):
        """Test dht_find_providers_async method."""
        # Create request
        request = DHTFindProvidersRequest(
            cid="QmTest123",
            timeout=30,
            limit=20
        )
        
        # Mock the anyio run_sync calls
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            # First call for is_available
            mock_run_sync.side_effect = [
                True,  # is_available
                {  # dht_find_providers
                    "success": True,
                    "cid": "QmTest123",
                    "providers": ["peer1", "peer2"],
                    "provider_count": 2
                }
            ]
            
            # Call the method
            result = await controller.dht_find_providers_async(request)
            
            # Verify async pattern: sync model methods were called via to_thread.run_sync
            assert mock_run_sync.await_count == 2
            calls = [
                call(mock_libp2p_model.is_available),
                call(mock_libp2p_model.dht_find_providers, cid="QmTest123", timeout=30, limit=20)
            ]
            mock_run_sync.assert_has_awaits(calls)
            
            # Verify result
            assert result["success"] is True
            assert result["cid"] == "QmTest123"
            assert len(result["providers"]) == 2
    
    async def test_pubsub_publish_async(self, controller, mock_libp2p_model):
        """Test pubsub_publish_async method."""
        # Create request
        request = PubSubPublishRequest(
            topic="test-topic",
            message="Hello, world!"
        )
        
        # Mock the anyio run_sync calls
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            # First call for is_available
            mock_run_sync.side_effect = [
                True,  # is_available
                {  # pubsub_publish
                    "success": True,
                    "topic": "test-topic",
                    "message_id": "msg-1234",
                    "recipients": 5
                }
            ]
            
            # Call the method
            result = await controller.pubsub_publish_async(request)
            
            # Verify async pattern: sync model methods were called via to_thread.run_sync
            assert mock_run_sync.await_count == 2
            calls = [
                call(mock_libp2p_model.is_available),
                call(mock_libp2p_model.pubsub_publish, topic="test-topic", message="Hello, world!")
            ]
            mock_run_sync.assert_has_awaits(calls)
            
            # Verify result
            assert result["success"] is True
            assert result["topic"] == "test-topic"
            assert result["message_id"] == "msg-1234"
    
    async def test_pubsub_subscribe_async(self, controller, mock_libp2p_model):
        """Test pubsub_subscribe_async method."""
        # Create request
        request = PubSubSubscribeRequest(
            topic="test-topic",
            handler_id="handler-1"
        )
        
        # Mock the anyio run_sync calls
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            # First call for is_available
            mock_run_sync.side_effect = [
                True,  # is_available
                {  # pubsub_subscribe
                    "success": True,
                    "topic": "test-topic",
                    "subscription_id": "sub-1234",
                    "handler_id": "handler-1"
                }
            ]
            
            # Call the method
            result = await controller.pubsub_subscribe_async(request)
            
            # Verify async pattern: sync model methods were called via to_thread.run_sync
            assert mock_run_sync.await_count == 2
            calls = [
                call(mock_libp2p_model.is_available),
                call(mock_libp2p_model.pubsub_subscribe, topic="test-topic", handler_id="handler-1")
            ]
            mock_run_sync.assert_has_awaits(calls)
            
            # Verify result
            assert result["success"] is True
            assert result["topic"] == "test-topic"
            assert result["subscription_id"] == "sub-1234"
            assert result["handler_id"] == "handler-1"
    
    async def test_pubsub_unsubscribe_async(self, controller, mock_libp2p_model):
        """Test pubsub_unsubscribe_async method."""
        # Create request
        request = PubSubUnsubscribeRequest(
            topic="test-topic",
            handler_id="handler-1"
        )
        
        # Mock the anyio run_sync calls
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            # First call for is_available
            mock_run_sync.side_effect = [
                True,  # is_available
                {  # pubsub_unsubscribe
                    "success": True,
                    "topic": "test-topic",
                    "subscription_id": "sub-1234",
                    "handler_id": "handler-1"
                }
            ]
            
            # Call the method
            result = await controller.pubsub_unsubscribe_async(request)
            
            # Verify async pattern: sync model methods were called via to_thread.run_sync
            assert mock_run_sync.await_count == 2
            calls = [
                call(mock_libp2p_model.is_available),
                call(mock_libp2p_model.pubsub_unsubscribe, topic="test-topic", handler_id="handler-1")
            ]
            mock_run_sync.assert_has_awaits(calls)
            
            # Verify result
            assert result["success"] is True
            assert result["topic"] == "test-topic"
            assert result["handler_id"] == "handler-1"
    
    async def test_pubsub_get_topics_async(self, controller, mock_libp2p_model):
        """Test pubsub_get_topics_async method."""
        # Mock the anyio run_sync calls
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            # First call for is_available
            mock_run_sync.side_effect = [
                True,  # is_available
                {  # pubsub_get_topics
                    "success": True,
                    "topics": ["topic1", "topic2"],
                    "topic_count": 2
                }
            ]
            
            # Call the method
            result = await controller.pubsub_get_topics_async()
            
            # Verify async pattern: sync model methods were called via to_thread.run_sync
            assert mock_run_sync.await_count == 2
            calls = [
                call(mock_libp2p_model.is_available),
                call(mock_libp2p_model.pubsub_get_topics)
            ]
            mock_run_sync.assert_has_awaits(calls)
            
            # Verify result
            assert result["success"] is True
            assert len(result["topics"]) == 2
            assert "topic1" in result["topics"]
    
    async def test_pubsub_get_peers_async(self, controller, mock_libp2p_model):
        """Test pubsub_get_peers_async method."""
        # Mock the anyio run_sync calls
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            # First call for is_available
            mock_run_sync.side_effect = [
                True,  # is_available
                {  # pubsub_get_peers
                    "success": True,
                    "peers": ["peer1", "peer2"],
                    "peer_count": 2,
                    "topic": "test-topic"
                }
            ]
            
            # Call the method
            result = await controller.pubsub_get_peers_async(topic="test-topic")
            
            # Verify async pattern: sync model methods were called via to_thread.run_sync
            assert mock_run_sync.await_count == 2
            calls = [
                call(mock_libp2p_model.is_available),
                call(mock_libp2p_model.pubsub_get_peers, topic="test-topic")
            ]
            mock_run_sync.assert_has_awaits(calls)
            
            # Verify result
            assert result["success"] is True
            assert len(result["peers"]) == 2
            assert result["topic"] == "test-topic"
    
    async def test_register_message_handler_async(self, controller, mock_libp2p_model):
        """Test register_message_handler_async method."""
        # Create request
        request = MessageHandlerRequest(
            handler_id="handler-1",
            protocol_id="/test/protocol/1.0.0",
            description="Test handler"
        )
        
        # Mock the anyio run_sync calls
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            # First call for is_available
            mock_run_sync.side_effect = [
                True,  # is_available
                {  # register_message_handler
                    "success": True,
                    "handler_id": "handler-1",
                    "protocol_id": "/test/protocol/1.0.0"
                }
            ]
            
            # Call the method
            result = await controller.register_message_handler_async(request)
            
            # Verify async pattern: sync model methods were called via to_thread.run_sync
            assert mock_run_sync.await_count == 2
            calls = [
                call(mock_libp2p_model.is_available),
                call(
                    mock_libp2p_model.register_message_handler,
                    handler_id="handler-1",
                    protocol_id="/test/protocol/1.0.0",
                    description="Test handler"
                )
            ]
            mock_run_sync.assert_has_awaits(calls)
            
            # Verify result
            assert result["success"] is True
            assert result["handler_id"] == "handler-1"
            assert result["protocol_id"] == "/test/protocol/1.0.0"
    
    async def test_unregister_message_handler_async(self, controller, mock_libp2p_model):
        """Test unregister_message_handler_async method."""
        # Create request
        request = MessageHandlerRequest(
            handler_id="handler-1",
            protocol_id="/test/protocol/1.0.0"
        )
        
        # Mock the anyio run_sync calls
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            # First call for is_available
            mock_run_sync.side_effect = [
                True,  # is_available
                {  # unregister_message_handler
                    "success": True,
                    "handler_id": "handler-1",
                    "protocol_id": "/test/protocol/1.0.0"
                }
            ]
            
            # Call the method
            result = await controller.unregister_message_handler_async(request)
            
            # Verify async pattern: sync model methods were called via to_thread.run_sync
            assert mock_run_sync.await_count == 2
            calls = [
                call(mock_libp2p_model.is_available),
                call(
                    mock_libp2p_model.unregister_message_handler,
                    handler_id="handler-1",
                    protocol_id="/test/protocol/1.0.0"
                )
            ]
            mock_run_sync.assert_has_awaits(calls)
            
            # Verify result
            assert result["success"] is True
            assert result["handler_id"] == "handler-1"
            assert result["protocol_id"] == "/test/protocol/1.0.0"
    
    async def test_list_message_handlers_async(self, controller, mock_libp2p_model):
        """Test list_message_handlers_async method."""
        # Mock the anyio run_sync calls
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            # First call for is_available
            mock_run_sync.side_effect = [
                True,  # is_available
                {  # list_message_handlers
                    "success": True,
                    "handlers": [
                        {
                            "handler_id": "handler-1",
                            "protocol_id": "/test/protocol/1.0.0",
                            "description": "Test handler"
                        }
                    ],
                    "handler_count": 1
                }
            ]
            
            # Call the method
            result = await controller.list_message_handlers_async()
            
            # Verify async pattern: sync model methods were called via to_thread.run_sync
            assert mock_run_sync.await_count == 2
            calls = [
                call(mock_libp2p_model.is_available),
                call(mock_libp2p_model.list_message_handlers)
            ]
            mock_run_sync.assert_has_awaits(calls)
            
            # Verify result
            assert result["success"] is True
            assert len(result["handlers"]) == 1
            assert result["handler_count"] == 1


@pytest.mark.skip("HTTP endpoint tests require FastAPI TestClient")
class TestLibP2PControllerAnyIOHTTPEndpoints:
    """Test the HTTP endpoints of the LibP2PControllerAnyIO class.
    
    These tests require a FastAPI TestClient and are currently skipped.
    """
    
    @pytest.fixture
    def test_client(self):
        """Create a FastAPI test client."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        
        app = FastAPI()
        mock_model = MagicMock()
        controller = MockLibP2PControllerAnyIO(mock_model)
        controller.register_routes(app)
        return TestClient(app)
    
    def test_health_endpoint(self, test_client):
        """Test GET /libp2p/health endpoint."""
        response = test_client.get("/libp2p/health")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["libp2p_available"] is True
        assert data["peer_initialized"] is True
    
    def test_discover_peers_endpoint(self, test_client):
        """Test POST /libp2p/discover endpoint."""
        request_data = {
            "discovery_method": "all",
            "limit": 10
        }
        response = test_client.post("/libp2p/discover", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["peers"]) > 0
    
    def test_get_peers_endpoint(self, test_client):
        """Test GET /libp2p/peers endpoint."""
        response = test_client.get("/libp2p/peers")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["peers"]) > 0
    
    def test_connect_peer_endpoint(self, test_client):
        """Test POST /libp2p/connect endpoint."""
        request_data = {
            "peer_addr": "/ip4/192.168.1.1/tcp/4001/p2p/QmPeerTest"
        }
        response = test_client.post("/libp2p/connect", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["connection_id"] == "conn-1234"


if __name__ == "__main__":
    unittest.main()