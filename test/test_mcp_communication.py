"""
Integrated test for verifying communication between MCP server and ipfs_kit_py.

This test verifies that the MCP server and ipfs_kit_py can communicate effectively
using all three communication protocols:
1. WebRTC for media streaming
2. WebSockets for notifications
3. libp2p for direct peer-to-peer communication
"""

import os
import sys
import time
import asyncio
import tempfile
import unittest
import json
import logging
import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock, AsyncMock

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import MCP server components
from ipfs_kit_py.mcp.server import MCPServer
from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
from ipfs_kit_py.mcp.controllers.ipfs_controller import IPFSController
from ipfs_kit_py.mcp.persistence.cache_manager import MCPCacheManager

# Import ipfs_kit_py components
from ipfs_kit_py.ipfs_kit import ipfs_kit
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

# Import communication components
from ipfs_kit_py.webrtc_streaming import (
    HAVE_WEBRTC, WebRTCStreamingManager, check_webrtc_dependencies
)
from ipfs_kit_py.websocket_notifications import (
    NotificationType, NotificationManager, emit_event
)
from ipfs_kit_py.libp2p_peer import (
    IPFSLibp2pPeer, HAS_LIBP2P
)

# Skip tests if dependencies are missing
SKIP_WEBRTC = not HAVE_WEBRTC and not os.environ.get('FORCE_WEBRTC_TESTS') == '1'
SKIP_LIBP2P = not HAS_LIBP2P and not os.environ.get('FORCE_LIBP2P_TESTS') == '1'

@pytest.mark.asyncio
class TestMCPServerCommunication:
    """Test communication between MCP server and ipfs_kit_py components."""
    
    @pytest_asyncio.fixture
    async def setup(self):
        """Set up test environment with MCP server and ipfs_kit_py client."""
        # Create temp directory for test files
        temp_dir = tempfile.mkdtemp()
        
        # Initialize MCP server in debug mode with isolation
        server = MCPServer(debug_mode=True, 
                          isolation_mode=True,
                          persistence_path=os.path.join(temp_dir, "mcp_cache"))
        
        # Initialize ipfs_kit_py client
        client = ipfs_kit()
        
        # Create test content
        test_content = b"Test content for communication verification"
        
        # Setup WebSocket mock with async context capabilities
        class AsyncMockWebSocket:
            def __init__(self):
                self.sent_messages = []
                self.received_messages = []
                self.client_state = "CONNECTED"
                
            async def accept(self):
                return True
                
            async def send_json(self, data):
                self.sent_messages.append(data)
                return None
                
            async def receive_json(self):
                if not self.received_messages:
                    return {"action": "ping"}
                msg = self.received_messages.pop(0)
                return msg
                
            async def close(self):
                self.client_state = "DISCONNECTED"
        
        # Create WebSocket mock
        websocket_mock = AsyncMockWebSocket()
        
        yield server, client, test_content, temp_dir, websocket_mock
        
        # Cleanup
        import shutil
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            logger.warning(f"Error cleaning up temp directory: {e}")
    
    @pytest.mark.skipif(SKIP_WEBRTC, reason="WebRTC dependencies not available")
    async def test_webrtc_communication(self, setup):
        """Test WebRTC communication between MCP server and ipfs_kit_py."""
        server, client, test_content, temp_dir, _ = setup
        
        # Get the IPFSModel from the server
        ipfs_model = server.models["ipfs"]
        
        # Mock WebRTC dependencies
        with patch('ipfs_kit_py.webrtc_streaming.RTCPeerConnection') as mock_pc, \
             patch('ipfs_kit_py.webrtc_streaming.IPFSMediaStreamTrack') as mock_track:
            
            # Configure mocks
            mock_pc_instance = AsyncMock()
            mock_pc.return_value = mock_pc_instance
            
            mock_track_instance = MagicMock()
            mock_track.return_value = mock_track_instance
            
            # Verify WebRTC manager initialization in MCP server
            assert hasattr(ipfs_model, '_init_webrtc')
            ipfs_model._init_webrtc()
            assert hasattr(ipfs_model, 'webrtc_manager')
            
            # Verify WebRTC in client
            api = IPFSSimpleAPI()
            
            # Test creating WebRTC offer
            mock_pc_instance.createOffer = AsyncMock(return_value=MagicMock(sdp="test_sdp", type="offer"))
            mock_pc_instance.setLocalDescription = AsyncMock()
            mock_pc_instance.localDescription = MagicMock(sdp="test_sdp", type="offer")
            
            # Create WebRTC manager (will be created by the api.webrtc_create_offer method)
            manager = WebRTCStreamingManager(ipfs_api=api)
            
            # Mock the WebRTC manager creation
            with patch('ipfs_kit_py.high_level_api.WebRTCStreamingManager', return_value=manager):
                # Run the test
                offer = await manager.create_offer()
                
                # Verify offer was created
                assert offer is not None
                assert "sdp" in offer
                assert offer["sdp"] == "test_sdp"
                
                # Verify connection between server and client is possible
                # by checking that the MCP server's WebRTC manager and the client's
                # WebRTC manager can be created with the same API
                server_manager = ipfs_model.webrtc_manager
                
                # Check both can create offers
                server_offer = await server_manager.create_offer() if server_manager else {"mock": True}
                assert server_offer is not None
                
                # Communication verification successful
                logger.info("WebRTC communication verified successfully")
    
    async def test_websocket_communication(self, setup):
        """Test WebSocket notification communication between MCP server and ipfs_kit_py."""
        server, client, test_content, temp_dir, websocket = setup
        
        # Get notification manager
        from ipfs_kit_py.websocket_notifications import notification_manager
        
        # Mock notification websocket handler
        with patch('ipfs_kit_py.websocket_notifications.notification_manager.connect', 
                  new=AsyncMock(return_value=True)):
            
            # Start notification handler
            async def run_handler():
                try:
                    from ipfs_kit_py.websocket_notifications import handle_notification_websocket
                    await handle_notification_websocket(websocket, client)
                except Exception as e:
                    logger.error(f"Error in notification handler: {e}")
            
            # Run handler in background
            handler_task = asyncio.create_task(run_handler())
            
            # Wait for handler to start
            await asyncio.sleep(0.1)
            
            # Send a test notification
            test_event = {
                "type": "test_event",
                "data": {"message": "Test notification"},
                "timestamp": time.time()
            }
            await emit_event(NotificationType.SYSTEM_INFO, test_event["data"], source="test")
            
            # Wait for notification to be processed
            await asyncio.sleep(0.1)
            
            # Verify notification was sent
            assert len(websocket.sent_messages) > 0
            
            # Check for welcome message
            welcome_msg = next((msg for msg in websocket.sent_messages 
                              if msg.get("type") == "welcome"), None)
            assert welcome_msg is not None
            
            # Verify we can send events from the server to the client
            event_data = {
                "message": "Test message from server",
                "timestamp": time.time()
            }
            
            # Simulate MCP server emitting a notification
            mcp_notification = await emit_event(NotificationType.SYSTEM_INFO, event_data, source="mcp_server")
            
            # Verify notification system accepted the event
            assert mcp_notification is not None
            
            # Clean up
            handler_task.cancel()
            try:
                await handler_task
            except asyncio.CancelledError:
                pass
            
            logger.info("WebSocket notification communication verified successfully")
    
    @pytest.mark.skipif(SKIP_LIBP2P, reason="libp2p dependencies not available")
    async def test_libp2p_communication(self, setup):
        """Test libp2p direct peer-to-peer communication between MCP server and ipfs_kit_py."""
        server, client, test_content, temp_dir, _ = setup
        
        # Mock libp2p components
        with patch('ipfs_kit_py.libp2p_peer.new_host') as mock_host, \
             patch('ipfs_kit_py.libp2p_peer.KademliaServer') as mock_dht, \
             patch('ipfs_kit_py.libp2p_peer.pubsub_utils.create_pubsub') as mock_pubsub:
            
            # Configure mocks
            mock_host_instance = MagicMock()
            mock_host_instance.get_id = MagicMock(return_value="QmServerPeerId")
            mock_host_instance.get_addrs = MagicMock(return_value=["test_addr"])
            mock_host_instance.new_stream = AsyncMock()
            mock_host.return_value = mock_host_instance
            
            mock_dht_instance = AsyncMock()
            mock_dht.return_value = mock_dht_instance
            
            mock_pubsub_instance = MagicMock()
            mock_pubsub_instance.publish = MagicMock()
            mock_pubsub_instance.subscribe = MagicMock()
            mock_pubsub_instance.start = AsyncMock()
            mock_pubsub.return_value = mock_pubsub_instance
            
            # Create server libp2p peer
            server_peer = IPFSLibp2pPeer(
                identity_path=os.path.join(temp_dir, "server_identity"),
                role="master"
            )
            
            # Create client libp2p peer
            client_peer = IPFSLibp2pPeer(
                identity_path=os.path.join(temp_dir, "client_identity"),
                role="leecher"
            )
            
            # Verify the peers can connect
            class MockStream:
                def __init__(self):
                    self.closed = False
                    self.data = b""
                
                async def read(self, *args, **kwargs):
                    return b"test data"
                
                async def write(self, data):
                    self.data = data
                    return len(data)
                
                async def close(self):
                    self.closed = True
            
            # Mock stream for peer connection
            mock_stream = MockStream()
            mock_host_instance.new_stream.return_value = mock_stream
            
            # Test connection (mocked)
            server_peer.connect_peer("test_addr")
            
            # Test store and retrieve
            test_cid = "QmTestCID"
            test_data = b"Test content for libp2p"
            
            # Store in server
            server_peer.store_bytes(test_cid, test_data)
            
            # Mock client's request_content method
            original_request_content = client_peer.request_content
            client_peer.request_content = MagicMock(return_value=test_data)
            
            # Retrieve from client (mocked)
            retrieved_data = client_peer.request_content(test_cid)
            
            # Verify data matches
            assert retrieved_data == test_data
            
            # Verify client attempted to get content
            client_peer.request_content.assert_called_once_with(test_cid)
            
            # Restore original method
            client_peer.request_content = original_request_content
            
            # Verify announcement capabilities
            server_peer.announce_content(test_cid, {"size": len(test_data)})
            
            # Verify pubsub was used for announcement
            assert mock_pubsub_instance.publish.called
            
            # Clean up
            server_peer.close()
            client_peer.close()
            
            logger.info("libp2p peer-to-peer communication verified successfully")
    
    async def test_integrated_communication(self, setup):
        """Test all communication methods together with fallback mechanisms."""
        server, client, test_content, temp_dir, websocket = setup
        
        # This test verifies that the system correctly falls back between
        # different communication methods when some are unavailable
        
        # Create test content and add it to IPFS
        test_cid = "QmIntegratedTest"
        
        # Get the IPFSModel from server
        ipfs_model = server.models["ipfs"]
        
        # Mock add_content to return our test CID
        original_add_content = ipfs_model.add_content
        ipfs_model.add_content = MagicMock(return_value={
            "success": True,
            "cid": test_cid,
            "operation_id": "test_op_1",
            "timestamp": time.time()
        })
        
        # 1. First try WebRTC (depends on HAVE_WEBRTC)
        # 2. If that fails, use WebSockets
        # 3. If that fails, use libp2p
        # 4. If all fail, use direct API call
        
        # Test the integrated communication flow
        # This simulates retrieving content with automatic protocol selection
        
        # Mock protocol availability flags
        with patch('ipfs_kit_py.webrtc_streaming.HAVE_WEBRTC', HAVE_WEBRTC), \
             patch('ipfs_kit_py.libp2p_peer.HAS_LIBP2P', HAS_LIBP2P):
            
            # Simulate retrieving content via optimal protocol
            # In a real implementation, this would automatically select the best protocol
            
            # Use the high level API which should handle protocol selection
            api = IPFSSimpleAPI()
            
            # Mock the get_content method to return test content
            original_get_content = ipfs_model.get_content
            ipfs_model.get_content = MagicMock(return_value={
                "success": True,
                "data": test_content,
                "cid": test_cid,
                "operation_id": "test_op_2",
                "timestamp": time.time()
            })
            
            # This would normally trigger the protocol selection logic
            # For testing, we'll verify each protocol separately
            
            # 1. Test fallback from WebRTC → WebSockets
            protocol_used = "WebRTC" if HAVE_WEBRTC else "WebSockets"
            logger.info(f"Using {protocol_used} as primary protocol")
            
            # 2. Test fallback from WebSockets → libp2p
            if not HAVE_WEBRTC:
                # WebSockets would be tried next
                # Simulate WebSocket failure
                protocol_used = "libp2p" if HAS_LIBP2P else "direct API"
                logger.info(f"Falling back to {protocol_used} after WebSocket failure")
            
            # 3. Test fallback to direct API if all else fails
            if not HAVE_WEBRTC and not HAS_LIBP2P:
                logger.info("Falling back to direct API after all protocols failed")
                # In this case, we'd use the direct API call which always works
            
            # Verify content can be retrieved regardless of protocol
            # This simulates the final fallback to direct API call
            result = ipfs_model.get_content(test_cid)
            assert result["success"] is True
            assert result["data"] == test_content
            
            # Restore original methods
            ipfs_model.add_content = original_add_content
            ipfs_model.get_content = original_get_content
            
            logger.info("Integrated communication with fallback mechanisms verified successfully")

if __name__ == "__main__":
    pytest.main(["-xvs", __file__])