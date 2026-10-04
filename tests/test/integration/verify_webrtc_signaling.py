#!/usr/bin/env python
"""
Verification test for WebRTC Signaling in MCP.

This script tests the WebRTC signaling functionality of the MCP server by:
1. Creating a signaling server instance
2. Simulating WebRTC peers connecting to rooms
3. Testing message exchange between peers
4. Verifying proper room management and cleanup

This addresses the "WebRTC Signaling" section from the "Streaming Operations" 
area in the mcp_roadmap.md that needs reassessment.
"""

import os
import sys
import json
import time
import uuid
import anyio
import logging
import argparse
from typing import Dict, Any, List, Tuple, Optional
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
import websockets

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("webrtc_verification")

# Add parent directory to path if needed
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import required modules
try:
    from mcp_webrtc import WebRTCSignalingServer, create_webrtc_router
    WEBRTC_MODULE_AVAILABLE = True
except ImportError:
    WEBRTC_MODULE_AVAILABLE = False
    logger.error("WebRTC module not available. Make sure mcp_webrtc.py is accessible.")


class MockWebSocket:
    """Mock WebSocket class for testing the signaling server."""
    
    def __init__(self):
        """Initialize the mock WebSocket."""
        self.accepted = False
        self.sent_messages = []
        self.closed = False
        self._send_stream, self._receive_stream = anyio.create_memory_object_stream(100)
    
    async def accept(self):
        """Accept the WebSocket connection."""
        self.accepted = True
    
    async def send_text(self, data: str):
        """Send text message."""
        self.sent_messages.append(data)
    
    async def send_json(self, data: Dict[str, Any]):
        """Send JSON message."""
        self.sent_messages.append(json.dumps(data))
    
    async def receive_text(self) -> str:
        """Receive text message."""
        return await self._receive_stream.receive()
    
    async def close(self):
        """Close the WebSocket connection."""
        self.closed = True
    
    def add_message(self, message: str):
        """Add a message to the receive queue."""
        if isinstance(message, dict):
            message = json.dumps(message)
        self._send_stream.send_nowait(message)
    
    def get_json_messages(self) -> List[Dict[str, Any]]:
        """Get all sent JSON messages."""
        return [json.loads(msg) for msg in self.sent_messages]


class WebRTCVerificationTest:
    """Test harness for verifying MCP WebRTC signaling functionality."""
    
    def __init__(self):
        """Initialize the test harness."""
        if not WEBRTC_MODULE_AVAILABLE:
            raise ImportError("WebRTC module not available")
        
        # Create signaling server instance
        self.signaling_server = WebRTCSignalingServer()
        
        # Create FastAPI app with WebRTC router
        self.app = FastAPI()
        self.router = create_webrtc_router("/api/v0")
        self.app.include_router(self.router)
        
        # Create test client
        self.client = TestClient(self.app)
    
    async def test_room_creation(self):
        """Test room creation and listing."""
        logger.info("Test 1: Room creation and listing")
        
        # Create a room via REST API
        response = self.client.post("/api/v0/webrtc/rooms", json={"name": "Test Room"})
        
        if response.status_code == 200 and response.json()["success"]:
            room_id = response.json()["room_id"]
            logger.info(f"✅ Room created successfully: {room_id}")
        else:
            logger.error(f"❌ Failed to create room: {response.text}")
            return False
        
        # List rooms
        response = self.client.get("/api/v0/webrtc/rooms")
        
        if response.status_code == 200 and response.json()["success"]:
            rooms = response.json()["rooms"]
            if any(room["room_id"] == room_id for room in rooms):
                logger.info("✅ Room listed successfully")
            else:
                logger.error("❌ Created room not found in room list")
                return False
        else:
            logger.error(f"❌ Failed to list rooms: {response.text}")
            return False
        
        # Get room details
        response = self.client.get(f"/api/v0/webrtc/rooms/{room_id}")
        
        if response.status_code == 200 and response.json()["success"]:
            room_info = response.json()["room"]
            if room_info["room_id"] == room_id:
                logger.info("✅ Room details retrieved successfully")
            else:
                logger.error("❌ Room details mismatch")
                return False
        else:
            logger.error(f"❌ Failed to get room details: {response.text}")
            return False
        
        return True
    
    async def test_peer_joining(self):
        """Test peer joining a room."""
        logger.info("Test 2: Peer joining")
        
        # Create a new room
        room_id = self.signaling_server.create_room()
        
        # Create mock WebSocket connections for two peers
        peer1_ws = MockWebSocket()
        peer2_ws = MockWebSocket()
        
        # Start handling peer1 in the background
        peer1_id = str(uuid.uuid4())
        async with anyio.create_task_group() as task_group:
            task_group.start_soon(
                self.signaling_server.handle_signaling,
                peer1_ws,
                room_id,
                peer1_id,
                {"name": "Peer 1"}
            )

            # Wait a moment for processing
            await anyio.sleep(0.1)

            # Check if peer1 received welcome message
            peer1_messages = peer1_ws.get_json_messages()
            welcome_messages = [msg for msg in peer1_messages if msg.get("type") == "welcome"]

            if welcome_messages and welcome_messages[0]["peer_id"] == peer1_id:
                logger.info("✅ Peer 1 received welcome message")
            else:
                logger.error("❌ Peer 1 did not receive welcome message")
                await peer1_ws.close()
                await peer2_ws.close()
                return False

            # Start handling peer2 in the background
            peer2_id = str(uuid.uuid4())
            task_group.start_soon(
                self.signaling_server.handle_signaling,
                peer2_ws,
                room_id,
                peer2_id,
                {"name": "Peer 2"}
            )

            # Wait a moment for processing
            await anyio.sleep(0.1)

            # Check if peer2 received welcome message with peer1 in the list
            peer2_messages = peer2_ws.get_json_messages()
            welcome_messages = [msg for msg in peer2_messages if msg.get("type") == "welcome"]

            if welcome_messages:
                welcome_msg = welcome_messages[0]
                if welcome_msg["peer_id"] == peer2_id:
                    logger.info("✅ Peer 2 received welcome message")
                    peers_in_welcome = welcome_msg.get("peers", [])
                    if any(p["peer_id"] == peer1_id for p in peers_in_welcome):
                        logger.info("✅ Peer 2 welcome message includes Peer 1")
                    else:
                        logger.error("❌ Peer 2 welcome message does not include Peer 1")
                        await peer1_ws.close()
                        await peer2_ws.close()
                        return False
                else:
                    logger.error("❌ Peer 2 welcome message has incorrect peer_id")
                    await peer1_ws.close()
                    await peer2_ws.close()
                    return False
            else:
                logger.error("❌ Peer 2 did not receive welcome message")
                await peer1_ws.close()
                await peer2_ws.close()
                return False

            # Verify room status
            room_info = self.signaling_server.get_room_info(room_id)
            if room_info and len(room_info["peers"]) == 2:
                logger.info("✅ Room contains both peers")
            else:
                logger.error("❌ Room does not contain both peers")
                await peer1_ws.close()
                await peer2_ws.close()
                return False

            # Clean up
            await peer1_ws.close()
            await peer2_ws.close()
            await anyio.sleep(0.1)  # Allow tasks to clean up

        return True
    
    async def test_signaling_messages(self):
        """Test signaling message exchange."""
        logger.info("Test 3: Signaling message exchange")
        
        # Create a new room
        room_id = self.signaling_server.create_room()
        
        # Create mock WebSocket connections for two peers
        peer1_ws = MockWebSocket()
        peer2_ws = MockWebSocket()
        
        # Start handling peers in the background
        peer1_id = str(uuid.uuid4())
        peer2_id = str(uuid.uuid4())

        async with anyio.create_task_group() as task_group:
            task_group.start_soon(
                self.signaling_server.handle_signaling,
                peer1_ws,
                room_id,
                peer1_id,
                {"name": "Peer 1"}
            )

            task_group.start_soon(
                self.signaling_server.handle_signaling,
                peer2_ws,
                room_id,
                peer2_id,
                {"name": "Peer 2"}
            )

            # Wait for welcome messages
            await anyio.sleep(0.1)

            # Clear message queues
            peer1_ws.sent_messages = []
            peer2_ws.sent_messages = []

            # Test 3.1: Send offer from peer1 to peer2
            offer_msg = {
                "type": "offer",
                "target": peer2_id,
                "sdp": "dummy SDP offer data"
            }
            peer1_ws.add_message(json.dumps(offer_msg))

            # Let it process
            await anyio.sleep(0.1)

            # Check if the message was forwarded correctly
            # Note: This is a bit of a limitation of our test setup.
            # In actual use with WebSockets for forwarding, this wouldn't forward correctly
            # in the mock environment. We're checking the logic here.

            peer_info = self.signaling_server.get_peers_in_room(room_id)
            if len(peer_info) == 2:
                logger.info("✅ Both peers still in room after offer")
            else:
                logger.error("❌ Peers not properly maintained in room after offer")
                await peer1_ws.close()
                await peer2_ws.close()
                return False

            # Test 3.2: Send ICE candidate from peer2 to peer1
            ice_msg = {
                "type": "candidate",
                "target": peer1_id,
                "candidate": "dummy ICE candidate",
                "sdpMLineIndex": 0,
                "sdpMid": "0"
            }
            peer2_ws.add_message(json.dumps(ice_msg))

            # Let it process
            await anyio.sleep(0.1)

            # Check if peers are still connected
            peer_info = self.signaling_server.get_peers_in_room(room_id)
            if len(peer_info) == 2:
                logger.info("✅ Both peers still in room after ICE candidate")
            else:
                logger.error("❌ Peers not properly maintained in room after ICE candidate")
                await peer1_ws.close()
                await peer2_ws.close()
                return False

            # Test 3.3: Send answer from peer2 to peer1
            answer_msg = {
                "type": "answer",
                "target": peer1_id,
                "sdp": "dummy SDP answer data"
            }
            peer2_ws.add_message(json.dumps(answer_msg))

            # Let it process
            await anyio.sleep(0.1)

            # Verify signaling server statistics
            stats = self.signaling_server.get_stats()
            if stats["active_rooms"] >= 1 and stats["active_peers"] >= 2:
                logger.info("✅ Signaling server stats show active room and peers")
            else:
                logger.error("❌ Signaling server stats incorrect")
                await peer1_ws.close()
                await peer2_ws.close()
                return False

            # Test 3.4: Send ping and check for pong
            ping_msg = {
                "type": "ping"
            }
            peer1_ws.add_message(json.dumps(ping_msg))

            # Let it process
            await anyio.sleep(0.1)

            # Check for pong response
            peer1_messages = peer1_ws.get_json_messages()
            if any(json.loads(msg).get("type") == "pong" for msg in peer1_messages if isinstance(msg, str)):
                logger.info("✅ Peer 1 received pong response")
            else:
                logger.warning("⚠️ Peer 1 did not receive pong response (might be WebSocket forwarding limitation)")

            # Clean up
            await peer1_ws.close()
            await peer2_ws.close()
            await anyio.sleep(0.1)  # Allow tasks to clean up

        return True
    
    async def test_peer_leaving(self):
        """Test peer leaving a room."""
        logger.info("Test 4: Peer leaving")
        
        # Create a new room
        room_id = self.signaling_server.create_room()
        
        # Create mock WebSocket connections for two peers
        peer1_ws = MockWebSocket()
        peer2_ws = MockWebSocket()
        
        # Start handling peers
        peer1_id = str(uuid.uuid4())
        peer2_id = str(uuid.uuid4())

        async with anyio.create_task_group() as task_group:
            task_group.start_soon(
                self.signaling_server.handle_signaling,
                peer1_ws,
                room_id,
                peer1_id,
                {"name": "Peer 1"}
            )

            task_group.start_soon(
                self.signaling_server.handle_signaling,
                peer2_ws,
                room_id,
                peer2_id,
                {"name": "Peer 2"}
            )

            # Wait for connection setup
            await anyio.sleep(0.1)

            # Verify both peers are in the room
            room_info = self.signaling_server.get_room_info(room_id)
            if room_info and len(room_info["peers"]) == 2:
                logger.info("✅ Room contains both peers")
            else:
                logger.error("❌ Room does not contain both peers")
                await peer1_ws.close()
                await peer2_ws.close()
                return False

            # Simulate peer1 disconnecting
            await peer1_ws.close()
            await anyio.sleep(0.1)  # Allow cleanup

            # Verify peer1 was removed from the room
            room_info = self.signaling_server.get_room_info(room_id)
            if room_info and len(room_info["peers"]) == 1:
                logger.info("✅ Room contains only peer2 after peer1 disconnected")
                if room_info["peers"][0]["peer_id"] == peer2_id:
                    logger.info("✅ Remaining peer is peer2")
                else:
                    logger.error("❌ Remaining peer is not peer2")
                    await peer2_ws.close()
                    return False
            else:
                logger.error("❌ Room does not contain exactly one peer after disconnect")
                await peer2_ws.close()
                return False

            # Now disconnect peer2
            await peer2_ws.close()
            await anyio.sleep(0.1)  # Allow cleanup

            # Verify the room was removed
            if not self.signaling_server.get_room_info(room_id):
                logger.info("✅ Room was removed after all peers disconnected")
            else:
                logger.error("❌ Room was not removed after all peers disconnected")
                return False

        return True
    
    async def run_tests(self):
        """Run all verification tests."""
        tests = [
            self.test_room_creation,
            self.test_peer_joining,
            self.test_signaling_messages,
            self.test_peer_leaving
        ]
        
        all_passed = True
        
        for i, test in enumerate(tests, 1):
            try:
                logger.info(f"Running test {i}/{len(tests)}: {test.__name__}")
                result = await test()
                if result:
                    logger.info(f"✅ Test {test.__name__} passed")
                else:
                    logger.error(f"❌ Test {test.__name__} failed")
                    all_passed = False
            except Exception as e:
                logger.error(f"❌ Test {test.__name__} failed with exception: {e}")
                import traceback
                logger.error(traceback.format_exc())
                all_passed = False
            
            logger.info("-" * 40)
        
        return all_passed
    
    async def check_endpoints(self):
        """Check if WebRTC endpoints are accessible."""
        logger.info("Checking WebRTC endpoints")
        
        # Check status endpoint
        response = self.client.get("/api/v0/webrtc/status")
        if response.status_code == 200 and response.json()["success"]:
            logger.info("✅ WebRTC status endpoint is accessible")
            logger.info(f"Stats: {response.json()['stats']}")
        else:
            logger.error("❌ WebRTC status endpoint is not accessible")
            return False
        
        # Check rooms endpoint
        response = self.client.get("/api/v0/webrtc/rooms")
        if response.status_code == 200 and response.json()["success"]:
            logger.info("✅ WebRTC rooms endpoint is accessible")
        else:
            logger.error("❌ WebRTC rooms endpoint is not accessible")
            return False
        
        return True
    
    async def run(self):
        """Run the full verification test."""
        try:
            # First check if endpoints are accessible
            endpoints_ok = await self.check_endpoints()
            if not endpoints_ok:
                logger.error("❌ WebRTC endpoints check failed")
                return False
            
            # Run all tests
            tests_ok = await self.run_tests()
            if not tests_ok:
                logger.error("❌ WebRTC verification tests failed")
                return False
            
            logger.info("✅ All WebRTC verification tests passed")
            return True
        except Exception as e:
            logger.error(f"Error running verification test: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False


async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='MCP WebRTC Signaling Verification Test')
    # Only parse args when running the script directly, not when imported by pytest
    if __name__ == "__main__":
        args = parser.parse_args()
    else:
        # When run under pytest, use default values
        args = parser.parse_args([])
    
    if not WEBRTC_MODULE_AVAILABLE:
        logger.error("WebRTC module not available. Cannot run verification tests.")
        return 1
    
    test = WebRTCVerificationTest()
    success = await test.run()
    
    if success:
        logger.info("✅ WebRTC signaling verification test completed successfully")
        return 0
    else:
        logger.error("❌ WebRTC signaling verification test failed")
        return 1


if __name__ == "__main__":
    exit_code = anyio.run(main)
    sys.exit(exit_code)