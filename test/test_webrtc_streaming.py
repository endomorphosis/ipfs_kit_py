import unittest
import asyncio
import json
import os
import tempfile
from unittest.mock import patch, MagicMock, AsyncMock
import pytest

try:
    from ipfs_kit_py.webrtc_streaming import HAVE_WEBRTC, IPFSMediaStreamTrack, WebRTCStreamingManager
    _can_test_webrtc = HAVE_WEBRTC
except ImportError:
    _can_test_webrtc = False

# Check if notification system is available
try:
    from ipfs_kit_py.websocket_notifications import NotificationType, emit_event
    _can_test_notifications = True
except ImportError:
    _can_test_notifications = False

from ipfs_kit_py.high_level_api import IPFSSimpleAPI


@pytest.mark.skipif(not _can_test_webrtc, reason="WebRTC dependencies not available")
class TestWebRTCStreaming(unittest.TestCase):
    """Test WebRTC streaming functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.api = IPFSSimpleAPI()
        self.test_content = b"Test video content" * 100000  # ~1.6MB of fake video data
        self.test_cid = "QmTestWebRTCCID123"
    
    @patch('ipfs_kit_py.webrtc_streaming.IPFSMediaStreamTrack')
    def test_webrtc_streaming_manager_create_offer(self, mock_track):
        """Test creation of WebRTC offer."""
        # Mock track instance
        mock_track_instance = MagicMock()
        mock_track.return_value = mock_track_instance
        
        # Set up test manager
        manager = WebRTCStreamingManager(self.api)
        
        # Define test coroutine for async testing
        async def test_coroutine():
            # Test creating an offer
            pc = MagicMock()
            pc.createOffer = AsyncMock(return_value=MagicMock(sdp="test_sdp", type="offer"))
            pc.setLocalDescription = AsyncMock()
            pc.localDescription = MagicMock(sdp="test_sdp", type="offer")
            pc.addTrack = MagicMock()
            
            # Mock RTCPeerConnection
            with patch('ipfs_kit_py.webrtc_streaming.RTCPeerConnection', return_value=pc):
                offer = await manager.create_offer(self.test_cid, kind="video", frame_rate=30)
                
                # Check results
                self.assertIn("pc_id", offer)
                self.assertEqual(offer["sdp"], "test_sdp")
                self.assertEqual(offer["type"], "offer")
                
                # Verify method calls
                pc.createOffer.assert_called_once()
                pc.setLocalDescription.assert_called_once()
                pc.addTrack.assert_called_once()
                
                # Verify track creation
                mock_track.assert_called_once_with(
                    ipfs_api=self.api,
                    cid=self.test_cid,
                    kind="video",
                    frame_rate=30
                )
        
        # Run the test coroutine
        asyncio.run(test_coroutine())
    
    @patch('av.open')
    @patch('ipfs_kit_py.webrtc_streaming.os.makedirs')
    def test_ipfs_media_stream_track(self, mock_makedirs, mock_av_open):
        """Test IPFSMediaStreamTrack class."""
        # Define test coroutine for async testing
        async def test_coroutine():
            # Mock API
            mock_api = MagicMock()
            mock_api.cat.return_value = self.test_content
            
            # Set up test container
            mock_container = MagicMock()
            mock_stream = MagicMock()
            mock_container.streams.video = [mock_stream]
            mock_decoder = [MagicMock()]  # List of frames
            mock_container.decode.return_value = mock_decoder
            mock_av_open.return_value = mock_container
            
            # Create track
            track = IPFSMediaStreamTrack(
                ipfs_api=mock_api,
                cid=self.test_cid,
                kind="video"
            )
            
            # Wait a bit for async loading
            await asyncio.sleep(0.1)
            
            # Test receiving frames
            frame = await track.recv()
            self.assertIsNotNone(frame)
            
            # Verify method calls
            mock_api.cat.assert_called_once_with(self.test_cid)
            mock_av_open.assert_called_once()
            
            # Clean up
            track.stop()
        
        # Run the test coroutine
        asyncio.run(test_coroutine())
    
    @patch('ipfs_kit_py.webrtc_streaming.handle_webrtc_signaling')
    async def test_handle_webrtc_streaming(self, mock_handler):
        """Test handle_webrtc_streaming method."""
        # Mock WebSocket
        mock_websocket = AsyncMock()
        
        # Test the method
        await self.api.handle_webrtc_streaming(mock_websocket)
        
        # Verify handler was called
        mock_handler.assert_called_once_with(mock_websocket, self.api)


@pytest.mark.asyncio
@pytest.mark.skipif(not _can_test_webrtc, reason="WebRTC dependencies not available")
class TestAsyncWebRTCStreaming:
    """Test asynchronous WebRTC streaming functionality."""
    
    @pytest.fixture
    async def setup(self):
        """Set up test environment."""
        api = IPFSSimpleAPI()
        test_content = b"Test video content" * 100000  # ~1.6MB of fake video data
        test_cid = "QmTestWebRTCCID123"
        
        # Create temporary directory for test files
        test_dir = tempfile.mkdtemp()
        
        # Mock components
        with patch('ipfs_kit_py.webrtc_streaming.RTCPeerConnection') as mock_pc_class:
            # Set up mock peer connection
            mock_pc = AsyncMock()
            mock_pc.createOffer = AsyncMock(return_value=MagicMock(sdp="test_sdp", type="offer"))
            mock_pc.setLocalDescription = AsyncMock()
            mock_pc.addIceCandidate = AsyncMock()
            mock_pc.close = AsyncMock()
            mock_pc.localDescription = MagicMock(sdp="test_sdp", type="offer")
            mock_pc.connectionState = "new"
            mock_pc_class.return_value = mock_pc
            
            yield api, test_content, test_cid, test_dir, mock_pc
        
        # Clean up
        import shutil
        shutil.rmtree(test_dir)
    
    @patch('ipfs_kit_py.webrtc_streaming.IPFSMediaStreamTrack')
    async def test_webrtc_signaling_flow(self, mock_track, setup):
        """Test the complete WebRTC signaling flow."""
        api, test_content, test_cid, test_dir, mock_pc = setup
        
        # Mock WebSocket
        mock_websocket = AsyncMock()
        
        # Mock message queue for WebSocket
        message_queue = asyncio.Queue()
        
        # Add initial request
        await message_queue.put({
            "type": "offer_request",
            "cid": test_cid,
            "kind": "video",
            "frameRate": 30
        })
        
        # Add ICE candidate message
        await message_queue.put({
            "type": "candidate",
            "pc_id": "test_pc_id",
            "candidate": "a=candidate:1 1 UDP 2013266431 192.168.1.100 50000 typ host",
            "sdpMid": "0",
            "sdpMLineIndex": 0
        })
        
        # Add answer message
        await message_queue.put({
            "type": "answer",
            "pc_id": "test_pc_id",
            "sdp": "test_answer_sdp",
            "sdpType": "answer"
        })
        
        # Add close message
        await message_queue.put({
            "type": "close",
            "pc_id": "test_pc_id"
        })
        
        # Define receive_json side effect
        async def receive_json_side_effect():
            if not message_queue.empty():
                return await message_queue.get()
            raise asyncio.CancelledError()
        
        mock_websocket.receive_json.side_effect = receive_json_side_effect
        
        # Mock track
        mock_track_instance = MagicMock()
        mock_track.return_value = mock_track_instance
        
        # Set up WebRTC manager
        with patch('ipfs_kit_py.webrtc_streaming.WebRTCStreamingManager') as mock_manager_class:
            # Create mock manager
            mock_manager = AsyncMock()
            mock_manager.create_offer = AsyncMock(return_value={
                "pc_id": "test_pc_id",
                "sdp": "test_sdp",
                "type": "offer"
            })
            mock_manager.handle_answer = AsyncMock(return_value=True)
            mock_manager.handle_candidate = AsyncMock(return_value=True)
            mock_manager.close_peer_connection = AsyncMock(return_value=True)
            mock_manager_class.return_value = mock_manager
            
            # Test the signaling handler
            from ipfs_kit_py.webrtc_streaming import handle_webrtc_signaling
            
            try:
                await handle_webrtc_signaling(mock_websocket, api)
            except asyncio.CancelledError:
                # Expected when the queue is empty
                pass
            
            # Verify manager method calls
            mock_manager_class.assert_called_once_with(api)
            mock_manager.create_offer.assert_called_once()
            mock_manager.handle_answer.assert_called_once()
            mock_manager.handle_candidate.assert_called_once()
            mock_manager.close_peer_connection.assert_called_once()
            
            # Verify WebSocket communications
            mock_websocket.send_json.assert_called()
            
            # Get the first call to send_json (should be the offer)
            first_call_args = mock_websocket.send_json.call_args_list[0][0][0]
            self.assertEqual(first_call_args["type"], "offer")
            self.assertEqual(first_call_args["pc_id"], "test_pc_id")


@pytest.mark.asyncio
@pytest.mark.skipif(not _can_test_webrtc, reason="WebRTC dependencies not available")
class TestWebRTCMetrics:
    """Test WebRTC metrics collection functionality."""
    
    @pytest.fixture
    async def setup(self):
        """Set up test environment."""
        api = IPFSSimpleAPI()
        test_cid = "QmTestWebRTCCID123"
        
        # Create mock manager
        with patch('ipfs_kit_py.webrtc_streaming.RTCPeerConnection'):
            manager = WebRTCStreamingManager(api, config=None)
            
            # Add fake connections to the manager
            manager.peer_connections = {
                "pc_id_1": MagicMock(connectionState="connected"),
                "pc_id_2": MagicMock(connectionState="connected")
            }
            
            # Add fake stats to the manager
            manager.connection_stats = {
                "pc_id_1": {
                    "created_at": time.time() - 60,  # 1 minute ago
                    "state": "connected",
                    "cid": test_cid,
                    "kind": "video",
                    "rtt": 100,
                    "packet_loss": 0.5,
                    "bandwidth_estimate": 2000000,
                    "jitter": 25,
                    "frames_sent": 1000,
                    "last_frames_sent": 900,
                    "bitrate": 1000000
                },
                "pc_id_2": {
                    "created_at": time.time() - 120,  # 2 minutes ago
                    "state": "connected",
                    "cid": test_cid,
                    "kind": "video",
                    "rtt": 150,
                    "packet_loss": 1.0,
                    "bandwidth_estimate": 1500000,
                    "jitter": 30,
                    "frames_sent": 2000,
                    "last_frames_sent": 1800,
                    "bitrate": 800000
                }
            }
            
            yield manager, test_cid
    
    async def test_update_global_metrics(self, setup):
        """Test updating global metrics from connection stats."""
        manager, test_cid = setup
        
        # Update global metrics
        await manager._update_global_metrics()
        
        # Get global metrics
        metrics = manager.get_global_metrics()
        
        # Verify metrics values
        assert metrics["active_connections"] == 2
        assert metrics["rtt_avg"] == 125.0  # Average of 100 and 150
        assert metrics["packet_loss_avg"] == 0.75  # Average of 0.5 and 1.0
        assert metrics["bandwidth_avg"] == 1750000.0  # Average of 2000000 and 1500000
        assert metrics["jitter_avg"] == 27.5  # Average of 25 and 30
        assert metrics["current_bitrate_total"] == 1800000  # Sum of 1000000 and 800000
        assert metrics["total_frames_sent"] == 300  # Sum of (1000-900) and (2000-1800)
    
    async def test_cleanup_ended_connections(self, setup):
        """Test cleanup of ended connections."""
        manager, test_cid = setup
        
        # Change state of first connection to failed
        manager.peer_connections["pc_id_1"].connectionState = "failed"
        
        # Mock close_peer_connection method
        manager.close_peer_connection = AsyncMock()
        
        # Call cleanup method
        await manager._cleanup_ended_connections()
        
        # Verify close_peer_connection was called for the failed connection
        manager.close_peer_connection.assert_called_once_with("pc_id_1")
        
        # Verify connection was added to ended_connections
        assert "pc_id_1" in manager.ended_connections
    
    async def test_metrics_collection_task(self, setup):
        """Test the metrics collection task."""
        manager, test_cid = setup
        
        # Mock methods used by collect_metrics
        manager._update_global_metrics = AsyncMock()
        manager._cleanup_ended_connections = AsyncMock()
        
        # Create a future that completes after 0.2 seconds to cancel the task
        async def cancel_after_delay(task):
            await asyncio.sleep(0.2)
            task.cancel()
        
        # Start the collection task
        try:
            task = asyncio.create_task(manager._collect_metrics())
            await cancel_after_delay(task)
            await task
        except asyncio.CancelledError:
            # Expected when the task is cancelled
            pass
        
        # Verify methods were called at least once
        manager._update_global_metrics.assert_called()
        manager._cleanup_ended_connections.assert_called()
    
    async def test_close_all_connections_cancels_metrics(self, setup):
        """Test that closing all connections cancels the metrics task."""
        manager, test_cid = setup
        
        # Create a mock metrics task
        mock_task = AsyncMock()
        manager.metrics_task = mock_task
        
        # Mock close_peer_connection to prevent actual closing
        manager.close_peer_connection = AsyncMock()
        
        # Call close_all_connections
        await manager.close_all_connections()
        
        # Verify the metrics task was cancelled
        mock_task.cancel.assert_called_once()
        
        # Verify close_peer_connection was called for all connections
        assert manager.close_peer_connection.call_count == 2

@pytest.mark.asyncio
@pytest.mark.skipif(not (_can_test_webrtc and _can_test_notifications), 
                   reason="WebRTC or Notification dependencies not available")
class TestWebRTCNotifications:
    """Test WebRTC integration with the notification system."""
    
    @pytest.fixture
    async def setup(self):
        """Set up test environment."""
        api = IPFSSimpleAPI()
        test_cid = "QmTestWebRTCCID123"
        
        # Create mock emit_event function
        mock_emit_event = AsyncMock()
        
        yield api, test_cid, mock_emit_event
    
    @patch('ipfs_kit_py.webrtc_streaming.emit_event')
    async def test_webrtc_connection_notifications(self, mock_emit_event, setup):
        """Test that WebRTC connections emit the appropriate notifications."""
        api, test_cid, _ = setup
        
        # Set up manager
        manager = WebRTCStreamingManager(api)
        
        # Mock RTCPeerConnection
        mock_pc = AsyncMock()
        mock_pc.createOffer = AsyncMock(return_value=MagicMock(sdp="test_sdp", type="offer"))
        mock_pc.setLocalDescription = AsyncMock()
        mock_pc.addTrack = MagicMock()
        mock_pc.localDescription = MagicMock(sdp="test_sdp", type="offer")
        mock_pc.connectionState = "new"
        
        with patch('ipfs_kit_py.webrtc_streaming.RTCPeerConnection', return_value=mock_pc), \
             patch('ipfs_kit_py.webrtc_streaming.IPFSMediaStreamTrack') as mock_track, \
             patch('ipfs_kit_py.webrtc_streaming.HAVE_NOTIFICATIONS', return_value=True):
                
            # Test creating an offer (should emit connection created notification)
            offer = await manager.create_offer(test_cid, kind="video", frame_rate=30)
            
            # Verify notification was emitted for connection creation
            mock_emit_event.assert_called_with(
                NotificationType.WEBRTC_CONNECTION_CREATED,
                {
                    "pc_id": offer["pc_id"],
                    "cid": test_cid,
                    "kind": "video",
                    "frame_rate": 30
                },
                source="webrtc_manager"
            )
            
            # Reset mock for next test
            mock_emit_event.reset_mock()
            
            # Simulate connection state change to connected
            pc_id = offer["pc_id"]
            old_state = manager.connection_stats[pc_id]["state"]
            mock_pc.connectionState = "connected"
            
            # Manually call the connection state change handler
            for connection_state_handler in mock_pc._events.get("connectionstatechange", []):
                await connection_state_handler()
            
            # Verify connection established notification was emitted
            mock_emit_event.assert_called_with(
                NotificationType.WEBRTC_CONNECTION_ESTABLISHED,
                {
                    "pc_id": pc_id,
                    "cid": test_cid,
                    "kind": "video",
                    "connection_time": pytest.approx(0, abs=1)  # Approximate time check
                },
                source="webrtc_manager"
            )
            
            # Reset mock for next test
            mock_emit_event.reset_mock()
            
            # Add a mock track for stream started notification
            mock_track_instance = MagicMock()
            mock_track_instance.cid = test_cid
            mock_track_instance.kind = "video"
            mock_track.return_value = mock_track_instance
            
            # Test adding a content track (should emit stream started notification)
            await manager.add_content_track(pc_id, test_cid, kind="video")
            
            # Verify stream started notification was emitted
            mock_emit_event.assert_called_with(
                NotificationType.WEBRTC_STREAM_STARTED,
                {
                    "pc_id": pc_id,
                    "cid": test_cid,
                    "kind": "video",
                    "frame_rate": 30
                },
                source="webrtc_manager"
            )
            
            # Reset mock for next test
            mock_emit_event.reset_mock()
            
            # Simulate connection closing (should emit stream ended and connection closed notifications)
            manager.tracks[pc_id] = mock_track_instance
            await manager.close_peer_connection(pc_id)
            
            # Verify notifications were emitted in the correct order (stream ended first, then connection closed)
            assert mock_emit_event.call_count == 2, "Expected 2 notification events"
            
            # First call should be for stream ended
            first_call = mock_emit_event.call_args_list[0]
            assert first_call[0][0] == NotificationType.WEBRTC_STREAM_ENDED
            
            # Second call should be for connection closed
            second_call = mock_emit_event.call_args_list[1]
            assert second_call[0][0] == NotificationType.WEBRTC_CONNECTION_CLOSED
    
    @patch('ipfs_kit_py.webrtc_streaming.emit_event')
    async def test_set_quality_control(self, mock_emit_event, setup):
        """Test that WebRTC quality control works properly."""
        api, test_cid, _ = setup
        
        # Mock WebSocket
        mock_websocket = AsyncMock()
        
        # Create a message queue with a quality control message
        message_queue = asyncio.Queue()
        await message_queue.put({
            "type": "set_quality",
            "pc_id": "test_pc_id",
            "quality": "high"
        })
        
        # Add a termination message to end the test
        await message_queue.put(Exception("End of test"))
        
        # Define receive_json side effect
        async def receive_json_side_effect():
            if not message_queue.empty():
                msg = await message_queue.get()
                if isinstance(msg, Exception):
                    raise msg
                return msg
            raise asyncio.CancelledError()
        
        mock_websocket.receive_json.side_effect = receive_json_side_effect
        
        # Mock track with bitrate controller
        mock_track = MagicMock()
        mock_track._bitrate_controller = MagicMock()
        mock_track._bitrate_controller.set_quality.return_value = {
            "width": 1280, 
            "height": 720, 
            "bitrate": 2_500_000, 
            "frame_rate": 30
        }
        
        # Mock manager
        mock_manager = MagicMock()
        mock_manager.tracks = {"test_pc_id": mock_track}
        mock_manager.connection_stats = {"test_pc_id": {}}
        
        # Import signaling handler
        from ipfs_kit_py.webrtc_streaming import handle_webrtc_signaling
        
        # Test quality control
        with patch('ipfs_kit_py.webrtc_streaming.WebRTCStreamingManager', return_value=mock_manager), \
             patch('ipfs_kit_py.webrtc_streaming.HAVE_NOTIFICATIONS', True):
            try:
                await handle_webrtc_signaling(mock_websocket, api)
            except Exception as e:
                if str(e) != "End of test":
                    raise
            
            # Verify quality was set
            mock_track._bitrate_controller.set_quality.assert_called_once_with("high")
            
            # Verify notification was sent if available
            if _can_test_notifications:
                mock_emit_event.assert_called_with(
                    NotificationType.WEBRTC_QUALITY_CHANGED,
                    {
                        "pc_id": "test_pc_id",
                        "quality_level": "high",
                        "settings": mock_track._bitrate_controller.set_quality.return_value,
                        "track_index": 0,
                        "client_initiated": True
                    },
                    source="webrtc_signaling"
                )
            
            # Verify response was sent
            mock_websocket.send_json.assert_called_with({
                "type": "quality_result",
                "pc_id": "test_pc_id",
                "quality": "high",
                "success": True
            })
    
    async def test_signaling_notifications(self, mock_emit_event, setup):
        """Test that WebRTC signaling emits the appropriate notifications."""
        api, test_cid, _ = setup
        
        # Mock WebSocket
        mock_websocket = AsyncMock()
        
        # Set up mock manager
        mock_manager = AsyncMock()
        mock_manager.create_offer = AsyncMock(return_value={
            "pc_id": "test_pc_id",
            "sdp": "test_sdp",
            "type": "offer"
        })
        
        # Define a test exception for error handling testing
        test_exception = Exception("Test signaling error")
        
        with patch('ipfs_kit_py.webrtc_streaming.WebRTCStreamingManager', return_value=mock_manager), \
             patch('ipfs_kit_py.webrtc_streaming.HAVE_NOTIFICATIONS', return_value=True):
             
            # Import the signaling handler
            from ipfs_kit_py.webrtc_streaming import handle_webrtc_signaling
            
            # Test connection notification
            # First message does accept, then throws exception to exit handler
            mock_websocket.receive_json = AsyncMock(side_effect=[test_exception])
            
            try:
                await handle_webrtc_signaling(mock_websocket, api)
            except Exception:
                pass
            
            # Verify system info notification was emitted for new connection
            mock_emit_event.assert_called_with(
                NotificationType.SYSTEM_INFO,
                {
                    "message": "New WebRTC signaling connection established",
                    "client_id": mock_emit_event.call_args[0][1]["client_id"]
                },
                source="webrtc_signaling"
            )
            
            # Reset mock for next test
            mock_emit_event.reset_mock()
            
            # Test error notification
            mock_websocket.receive_json = AsyncMock(side_effect=json.JSONDecodeError("Invalid JSON", "{", 0))
            try:
                await handle_webrtc_signaling(mock_websocket, api)
            except Exception:
                pass
            
            # Verify error notification was emitted
            assert any(
                call[0][0] == NotificationType.WEBRTC_ERROR
                for call in mock_emit_event.call_args_list
            ), "Expected WEBRTC_ERROR notification"


if __name__ == "__main__":
    unittest.main()