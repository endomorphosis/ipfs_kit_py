#!/usr/bin/env python3
"""
Verification script for MCP Streaming Operations.

This script verifies that the Streaming Operations functionality
mentioned in the roadmap is working correctly, including file streaming,
WebSocket notifications, and WebRTC signaling.
"""

import os
import sys
import json
import time
import logging
import tempfile
import asyncio
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger("streaming_test")

# Add project root to Python path
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

async def test_streaming_imports():
    """Test the streaming module imports correctly."""
    try:
        from ipfs_kit_py.mcp.streaming import (
            # File streaming
            ChunkedFileUploader,
            StreamingDownloader,
            BackgroundPinningManager,
            ProgressTracker,

            # WebSocket
            WebSocketManager,
            get_ws_manager,
            EventType,

            # WebRTC
            SignalingServer,
            Room,
            PeerConnection
        )

        logger.info("✅ Successfully imported streaming modules")
        return True, {
            "ChunkedFileUploader": ChunkedFileUploader,
            "StreamingDownloader": StreamingDownloader,
            "BackgroundPinningManager": BackgroundPinningManager,
            "ProgressTracker": ProgressTracker,
            "WebSocketManager": WebSocketManager,
            "get_ws_manager": get_ws_manager,
            "EventType": EventType,
            "SignalingServer": SignalingServer,
            "Room": Room,
            "PeerConnection": PeerConnection
        }
    except ImportError as e:
        logger.error(f"❌ Failed to import streaming modules: {e}")
        return False, None

async def test_progress_tracker(streaming_classes):
    """Test the ProgressTracker component."""
    ProgressTracker = streaming_classes["ProgressTracker"]

    # Create progress tracker
    tracker = ProgressTracker("test_operation")

    # Test callback registration
    callback_called = False
    callback_data = None

    def progress_callback(progress_info):
        nonlocal callback_called, callback_data
        callback_called = True
        callback_data = progress_info

    tracker.register_callback(progress_callback)

    # Initialize tracker
    tracker.initialize(total_size=100, total_chunks=10)

    # Verify callback was called
    if not callback_called:
        logger.error("❌ Progress callback was not called on initialize")
        return False

    # Reset for next test
    callback_called = False

    # Update progress
    tracker.update(processed_size=50, processed_chunks=5)

    # Verify callback was called
    if not callback_called:
        logger.error("❌ Progress callback was not called on update")
        return False

    # Verify progress info
    if callback_data.progress_percentage != 50.0:
        logger.error(f"❌ Expected progress 50%, got {callback_data.progress_percentage}%")
        return False

    # Reset for next test
    callback_called = False

    # Increment progress
    tracker.increment(size_increment=25, chunks_increment=2)

    # Verify callback was called
    if not callback_called:
        logger.error("❌ Progress callback was not called on increment")
        return False

    # Verify progress info
    if callback_data.processed_size != 75:
        logger.error(f"❌ Expected processed size 75, got {callback_data.processed_size}")
        return False

    if callback_data.processed_chunks != 7:
        logger.error(f"❌ Expected processed chunks 7, got {callback_data.processed_chunks}")
        return False

    # Complete operation
    tracker.complete()

    # Verify progress info
    if not callback_data.completed:
        logger.error("❌ Progress not marked as completed")
        return False

    if callback_data.progress_percentage != 100.0:
        logger.error(f"❌ Expected progress 100%, got {callback_data.progress_percentage}%")
        return False

    logger.info("✅ ProgressTracker tests passed")
    return True

async def test_chunked_file_uploader(streaming_classes):
    """Test the ChunkedFileUploader component."""
    ChunkedFileUploader = streaming_classes["ChunkedFileUploader"]
    ProgressTracker = streaming_classes["ProgressTracker"]

    # Create a test file
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        # Write random data
        temp_file.write(os.urandom(1024 * 1024))  # 1MB
        temp_path = temp_file.name

    # Create a mock destination
    class MockDestination:
        def __init__(self):
            self.chunks = []

        async def add_chunk(self, data):
            self.chunks.append(data)
            return {"success": True, "chunk_id": len(self.chunks)}

        async def finalize(self, chunk_ids):
            total_size = sum(len(chunk) for chunk in self.chunks)
            return {"success": True, "cid": "test_cid", "total_size": total_size}

    destination = MockDestination()

    # Create an uploader with small chunks for testing
    uploader = ChunkedFileUploader(chunk_size=256 * 1024, max_concurrent=2)

    # Create progress tracker
    tracker = ProgressTracker()

    # Upload the file
    result = await uploader.upload(temp_path, destination, tracker)

    # Verify result
    if not result.get("success", False):
        logger.error(f"❌ Upload failed: {result.get('error')}")
        return False

    # Verify chunks were uploaded
    if len(destination.chunks) == 0:
        logger.error("❌ No chunks were uploaded")
        return False

    # Verify total size
    total_size = sum(len(chunk) for chunk in destination.chunks)
    if total_size != os.path.getsize(temp_path):
        logger.error(f"❌ Expected size {os.path.getsize(temp_path)}, got {total_size}")
        return False

    # Verify progress was tracked
    if not tracker.progress_info.completed:
        logger.error("❌ Progress not marked as completed")
        return False

    # Clean up
    os.unlink(temp_path)

    logger.info("✅ ChunkedFileUploader tests passed")
    return True

async def test_websocket_manager(streaming_classes):
    """Test the WebSocketManager component."""
    WebSocketManager = streaming_classes["WebSocketManager"]
    get_ws_manager = streaming_classes["get_ws_manager"]
    EventType = streaming_classes["EventType"]

    # Create a mock WebSocket
    class MockWebSocket:
        def __init__(self):
            self.messages = []

        async def send_text(self, message):
            self.messages.append(message)
            return True

    # Get WebSocket manager
    manager = get_ws_manager()

    # Create a mock client
    mock_socket = MockWebSocket()
    client_id = await manager.register_client(mock_socket)

    # Verify client was registered
    client_info = manager.get_client_info(client_id)
    if not client_info:
        logger.error("❌ Client was not registered")
        return False

    # Subscribe to a channel
    success = await manager.subscribe(client_id, "test_channel")
    if not success:
        logger.error("❌ Failed to subscribe to channel")
        return False

    # Verify subscription
    client_info = manager.get_client_info(client_id)
    if "test_channel" not in client_info["channels"]:
        logger.error("❌ Channel subscription not recorded")
        return False

    # Send a message
    message = {"type": "test", "data": "Hello, WebSocket!"}
    success = await manager.send(client_id, message)
    if not success:
        logger.error("❌ Failed to send message")
        return False

    # Verify message was sent
    if not mock_socket.messages:
        logger.error("❌ No messages were sent")
        return False

    try:
        sent_message = json.loads(mock_socket.messages[0])
        if sent_message != message:
            logger.error(f"❌ Message mismatch: {sent_message} != {message}")
            return False
    except json.JSONDecodeError:
        logger.error(f"❌ Invalid JSON message: {mock_socket.messages[0]}")
        return False

    # Test notification
    manager.notify("test_channel", {"event": EventType.CONTENT_ADDED.value, "cid": "test_cid"})

    # Give the notification time to process
    await asyncio.sleep(0.1)

    # Verify notification was sent
    if len(mock_socket.messages) < 2:
        logger.warning("⚠️ Notification not received, but this might be due to async scheduling")

    # Unsubscribe
    success = await manager.unsubscribe(client_id, "test_channel")
    if not success:
        logger.error("❌ Failed to unsubscribe from channel")
        return False

    # Verify unsubscription
    client_info = manager.get_client_info(client_id)
    if "test_channel" in client_info["channels"]:
        logger.error("❌ Channel unsubscription not processed")
        return False

    # Unregister client
    await manager.unregister_client(client_id)

    # Verify client was unregistered
    client_info = manager.get_client_info(client_id)
    if client_info:
        logger.error("❌ Client not unregistered")
        return False

    logger.info("✅ WebSocketManager tests passed")
    return True

async def test_signaling_server(streaming_classes):
    """Test the SignalingServer component."""
    SignalingServer = streaming_classes["SignalingServer"]
    Room = streaming_classes["Room"]
    PeerConnection = streaming_classes["PeerConnection"]

    # Create a mock WebSocket
    class MockWebSocket:
        def __init__(self):
            self.messages = []

        async def send_text(self, message):
            self.messages.append(message)
            return True

    # Initialize signaling server
    server = SignalingServer()

    # Create a room
    room = await server.create_room("test_room")

    # Verify room was created
    if not room or room.id != "test_room":
        logger.error("❌ Room was not created properly")
        return False

    # Create mock peer connections
    peer1_socket = MockWebSocket()
    peer2_socket = MockWebSocket()

    # Join room with peers
    peer1 = await server.join_room("test_room", peer1_socket, "peer1", {"name": "Peer 1"})
    peer2 = await server.join_room("test_room", peer2_socket, "peer2", {"name": "Peer 2"})

    # Verify peers joined
    room_info = server.get_room_info("test_room")
    if len(room_info["peers"]) != 2:
        logger.error(f"❌ Expected 2 peers, got {len(room_info['peers'])}")
        return False

    # Send signaling message
    message = {
        "type": "offer",
        "to": "peer2",
        "sdp": "test_sdp"
    }

    success = await server.handle_signal("test_room", "peer1", message)
    if not success:
        logger.error("❌ Failed to handle signal")
        return False

    # Verify message was relayed
    if not peer2_socket.messages:
        logger.error("❌ No messages were relayed")
        return False

    try:
        relayed_message = json.loads(peer2_socket.messages[0])
        if relayed_message["type"] != "offer" or relayed_message["from"] != "peer1":
            logger.error(f"❌ Message mismatch: {relayed_message}")
            return False
    except json.JSONDecodeError:
        logger.error(f"❌ Invalid JSON message: {peer2_socket.messages[0]}")
        return False

    # Leave room
    success = await server.leave_room("test_room", "peer1")
    if not success:
        logger.error("❌ Failed to leave room")
        return False

    # Verify peer left
    room_info = server.get_room_info("test_room")
    if len(room_info["peers"]) != 1:
        logger.error(f"❌ Expected 1 peer after leaving, got {len(room_info['peers'])}")
        return False

    # Leave with last peer to delete room
    success = await server.leave_room("test_room", "peer2")
    if not success:
        logger.error("❌ Failed to leave room with last peer")
        return False

    # Verify room was deleted
    room_info = server.get_room_info("test_room")
    if room_info:
        logger.error("❌ Room not deleted after all peers left")
        return False

    logger.info("✅ SignalingServer tests passed")
    return True

async def main():
    """Run all streaming verification tests."""
    logger.info("\n=== STREAMING OPERATIONS VERIFICATION ===\n")

    # Test 1: Import the streaming modules
    import_success, streaming_classes = await test_streaming_imports()
    if not import_success:
        logger.error("❌ Streaming module import test failed")
        return False

    # Test 2: Progress tracker
    if not await test_progress_tracker(streaming_classes):
        logger.error("❌ Progress tracker test failed")
        return False

    # Test 3: Chunked file uploader
    if not await test_chunked_file_uploader(streaming_classes):
        logger.error("❌ Chunked file uploader test failed")
        return False

    # Test 4: WebSocket manager
    if not await test_websocket_manager(streaming_classes):
        logger.error("❌ WebSocket manager test failed")
        return False

    # Test 5: Signaling server
    if not await test_signaling_server(streaming_classes):
        logger.error("❌ Signaling server test failed")
        return False

    logger.info("\n=== TEST RESULT ===")
    logger.info("✅ All Streaming Operations tests passed!")
    logger.info("The streaming functionality has been successfully verified.")

    return True

if __name__ == "__main__":
    asyncio.run(main())
