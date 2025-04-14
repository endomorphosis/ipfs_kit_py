#!/usr/bin/env python3
"""
MCP Streaming functionality test script.

This script demonstrates how to use the real-time streaming capabilities of the MCP server,
including WebSocket connections for events and real-time notifications, and WebRTC for
peer-to-peer communication.
"""

import os
import sys
import time
import json
import uuid
import asyncio
import argparse
import logging
import websockets
import requests
from typing import Dict, Any, List, Optional, Callable

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Parse arguments
parser = argparse.ArgumentParser(description='Test MCP Streaming functionality')
parser.add_argument('--host', type=str, default='localhost', help='MCP Server host')
parser.add_argument('--port', type=int, default=9997, help='MCP Server port')
parser.add_argument('--api-prefix', type=str, default='/api/v0', help='API prefix')
parser.add_argument('--test', type=str, choices=['websocket', 'webrtc', 'all'], default='all', 
                    help='Which test to run (websocket, webrtc, or all)')
args = parser.parse_args()

# Constants
HOST = args.host
PORT = args.port
API_PREFIX = args.api_prefix
BASE_URL = f"http://{HOST}:{PORT}{API_PREFIX}"
WS_URL = f"ws://{HOST}:{PORT}/ws"
WEBRTC_URL = f"ws://{HOST}:{PORT}/webrtc/signal"

# Example event handlers for WebSocket messages
async def handle_websocket_message(message: Dict[str, Any]) -> None:
    """Handle a WebSocket message."""
    if "type" in message:
        message_type = message["type"]
        
        if message_type == "welcome":
            logger.info(f"Connected to WebSocket server with connection ID: {message.get('connection_id')}")
        
        elif message_type == "subscribed":
            logger.info(f"Subscribed to channel: {message.get('channel')}")
        
        elif message_type == "unsubscribed":
            logger.info(f"Unsubscribed from channel: {message.get('channel')}")
        
        elif message_type == "unsubscribed_all":
            logger.info(f"Unsubscribed from all channels: {message.get('channels')}")
        
        elif message_type == "pong":
            logger.debug("Received pong response")
        
        elif message_type == "error":
            logger.error(f"Received error: {message.get('error')}")
        
        elif message_type == "echo":
            logger.info(f"Received echo: {message.get('data')}")
        
        else:
            logger.info(f"Received message: {message}")
    else:
        logger.info(f"Received message without type: {message}")

# WebRTC peer class
class WebRTCPeer:
    """
    WebRTC peer for testing signaling.
    
    This is a simplified version without actual WebRTC connections.
    It only simulates the signaling process.
    """
    
    def __init__(self, room_id: str, peer_id: Optional[str] = None):
        """
        Initialize the WebRTC peer.
        
        Args:
            room_id: The room ID to join
            peer_id: Optional peer ID (generated if not provided)
        """
        self.room_id = room_id
        self.peer_id = peer_id or str(uuid.uuid4())
        self.connection = None
        self.other_peers = []
        self.is_connected = False
        
        # Message handlers
        self.handlers: Dict[str, Callable] = {
            "welcome": self._handle_welcome,
            "peer_joined": self._handle_peer_joined,
            "peer_left": self._handle_peer_left,
            "offer": self._handle_offer,
            "answer": self._handle_answer,
            "candidate": self._handle_candidate,
            "room_message": self._handle_room_message,
            "peer_message": self._handle_peer_message
        }
    
    async def connect(self) -> None:
        """Connect to the WebRTC signaling server."""
        try:
            url = f"{WEBRTC_URL}/{self.room_id}/{self.peer_id}"
            self.connection = await websockets.connect(url)
            self.is_connected = True
            logger.info(f"WebRTC peer {self.peer_id} connected to room {self.room_id}")
            
            # Start message handling
            asyncio.create_task(self._handle_messages())
            
            # Send periodic pings to keep the connection alive
            asyncio.create_task(self._ping_periodically())
        except Exception as e:
            logger.error(f"Error connecting to WebRTC signaling server: {e}")
            self.is_connected = False
    
    async def disconnect(self) -> None:
        """Disconnect from the WebRTC signaling server."""
        if self.connection:
            await self.connection.close()
            self.is_connected = False
            logger.info(f"WebRTC peer {self.peer_id} disconnected from room {self.room_id}")
    
    async def _handle_messages(self) -> None:
        """Handle incoming WebRTC signaling messages."""
        try:
            while self.is_connected and self.connection:
                message = await self.connection.recv()
                data = json.loads(message)
                
                if "type" in data:
                    message_type = data["type"]
                    if message_type in self.handlers:
                        await self.handlers[message_type](data)
                    else:
                        logger.info(f"Received unknown message type: {message_type}")
                        logger.debug(f"Message content: {data}")
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"WebRTC connection closed for peer {self.peer_id}")
            self.is_connected = False
        except Exception as e:
            logger.error(f"Error handling WebRTC messages: {e}")
            self.is_connected = False
    
    async def _ping_periodically(self) -> None:
        """Send periodic pings to keep the connection alive."""
        try:
            while self.is_connected and self.connection:
                await asyncio.sleep(30)
                if self.is_connected and self.connection:
                    await self.connection.send(json.dumps({"type": "ping"}))
        except Exception as e:
            logger.error(f"Error sending ping: {e}")
    
    async def send_offer_to_all(self) -> None:
        """Send a simulated offer to all other peers in the room."""
        if not self.is_connected or not self.connection:
            logger.error("Cannot send offer: not connected")
            return
        
        for peer in self.other_peers:
            # Send a simulated offer
            offer = {
                "type": "offer",
                "target": peer["peer_id"],
                "sdp": "simulated_sdp_offer_for_testing"
            }
            
            await self.connection.send(json.dumps(offer))
            logger.info(f"Sent offer to peer {peer['peer_id']}")
    
    async def send_room_message(self, data: Dict[str, Any]) -> None:
        """Send a message to all peers in the room."""
        if not self.is_connected or not self.connection:
            logger.error("Cannot send room message: not connected")
            return
        
        message = {
            "type": "room_message",
            "data": data
        }
        
        await self.connection.send(json.dumps(message))
        logger.info(f"Sent room message: {data}")
    
    async def _handle_welcome(self, data: Dict[str, Any]) -> None:
        """Handle welcome message from the signaling server."""
        # Store other peers
        self.other_peers = data.get("peers", [])
        logger.info(f"Joined room {self.room_id} with {len(self.other_peers)} other peers")
        
        if self.other_peers:
            peer_ids = [p["peer_id"] for p in self.other_peers]
            logger.info(f"Other peers in room: {', '.join(peer_ids)}")
    
    async def _handle_peer_joined(self, data: Dict[str, Any]) -> None:
        """Handle peer joined message."""
        peer_id = data.get("peer_id")
        
        # Skip if it's our own join notification
        if peer_id == self.peer_id:
            return
        
        # Add to other peers
        peer_info = {"peer_id": peer_id, "metadata": data.get("metadata", {})}
        self.other_peers.append(peer_info)
        
        logger.info(f"Peer {peer_id} joined the room")
    
    async def _handle_peer_left(self, data: Dict[str, Any]) -> None:
        """Handle peer left message."""
        peer_id = data.get("peer_id")
        
        # Remove from other peers
        self.other_peers = [p for p in self.other_peers if p["peer_id"] != peer_id]
        
        logger.info(f"Peer {peer_id} left the room")
    
    async def _handle_offer(self, data: Dict[str, Any]) -> None:
        """Handle WebRTC offer."""
        from_peer = data.get("from")
        sdp = data.get("sdp")
        
        logger.info(f"Received offer from peer {from_peer}")
        
        # In a real implementation, we would set the remote description
        # and create an answer. For this test, we'll just send a simulated answer.
        
        if self.is_connected and self.connection:
            answer = {
                "type": "answer",
                "target": from_peer,
                "sdp": "simulated_sdp_answer_for_testing"
            }
            
            await self.connection.send(json.dumps(answer))
            logger.info(f"Sent answer to peer {from_peer}")
    
    async def _handle_answer(self, data: Dict[str, Any]) -> None:
        """Handle WebRTC answer."""
        from_peer = data.get("from")
        sdp = data.get("sdp")
        
        logger.info(f"Received answer from peer {from_peer}")
        
        # In a real implementation, we would set the remote description
    
    async def _handle_candidate(self, data: Dict[str, Any]) -> None:
        """Handle ICE candidate."""
        from_peer = data.get("from")
        candidate = data.get("candidate")
        
        logger.info(f"Received ICE candidate from peer {from_peer}")
        
        # In a real implementation, we would add the ICE candidate
    
    async def _handle_room_message(self, data: Dict[str, Any]) -> None:
        """Handle room message."""
        from_peer = data.get("from")
        message_data = data.get("data", {})
        
        logger.info(f"Received room message from peer {from_peer}: {message_data}")
    
    async def _handle_peer_message(self, data: Dict[str, Any]) -> None:
        """Handle direct peer message."""
        from_peer = data.get("from")
        message_data = data.get("data", {})
        
        logger.info(f"Received direct message from peer {from_peer}: {message_data}")

# Test WebSocket functionality
async def test_websocket() -> None:
    """Test WebSocket functionality."""
    logger.info("Testing WebSocket functionality...")
    
    # Check if WebSocket is available
    try:
        response = requests.get(f"{BASE_URL}/realtime/status")
        if response.status_code != 200:
            logger.error(f"WebSocket status check failed with status code: {response.status_code}")
            return
        
        data = response.json()
        if not data.get("success", False):
            logger.error(f"WebSocket status check failed: {data.get('error', 'Unknown error')}")
            return
        
        logger.info(f"WebSocket status: {data.get('status')}")
        logger.info(f"WebSocket stats: {data.get('stats')}")
    except Exception as e:
        logger.error(f"Error checking WebSocket status: {e}")
        return
    
    # Connect to WebSocket
    try:
        logger.info(f"Connecting to WebSocket at {WS_URL}...")
        async with websockets.connect(WS_URL) as websocket:
            logger.info("WebSocket connected")
            
            # Handle incoming messages
            async def message_handler():
                while True:
                    try:
                        message = await websocket.recv()
                        data = json.loads(message)
                        await handle_websocket_message(data)
                    except websockets.exceptions.ConnectionClosed:
                        logger.info("WebSocket connection closed")
                        break
                    except Exception as e:
                        logger.error(f"Error handling WebSocket message: {e}")
                        break
            
            # Start message handler
            task = asyncio.create_task(message_handler())
            
            # Subscribe to channels
            await websocket.send(json.dumps({
                "command": "subscribe",
                "channel": "ipfs:all"
            }))
            
            await asyncio.sleep(1)
            
            # Subscribe to storage channel
            await websocket.send(json.dumps({
                "command": "subscribe",
                "channel": "storage:all"
            }))
            
            await asyncio.sleep(1)
            
            # Echo test
            await websocket.send(json.dumps({
                "command": "echo",
                "data": {"hello": "world", "time": time.time()}
            }))
            
            await asyncio.sleep(1)
            
            # Ping test
            await websocket.send(json.dumps({
                "command": "ping"
            }))
            
            await asyncio.sleep(1)
            
            # Unsubscribe from a channel
            await websocket.send(json.dumps({
                "command": "unsubscribe",
                "channel": "ipfs:all"
            }))
            
            await asyncio.sleep(1)
            
            # Unsubscribe from all channels
            await websocket.send(json.dumps({
                "command": "unsubscribe_all"
            }))
            
            await asyncio.sleep(1)
            
            # Cancel the message handler
            task.cancel()
            
            logger.info("WebSocket test completed successfully")
    
    except Exception as e:
        logger.error(f"Error in WebSocket test: {e}")

# Test WebRTC functionality
async def test_webrtc() -> None:
    """Test WebRTC signaling functionality."""
    logger.info("Testing WebRTC functionality...")
    
    # Check if WebRTC is available
    try:
        response = requests.get(f"{BASE_URL}/webrtc/status")
        if response.status_code != 200:
            logger.error(f"WebRTC status check failed with status code: {response.status_code}")
            return
        
        data = response.json()
        if not data.get("success", False):
            logger.error(f"WebRTC status check failed: {data.get('error', 'Unknown error')}")
            return
        
        logger.info(f"WebRTC status: {data.get('status')}")
        logger.info(f"WebRTC stats: {data.get('stats')}")
    except Exception as e:
        logger.error(f"Error checking WebRTC status: {e}")
        return
    
    # Create a test room
    try:
        response = requests.post(
            f"{BASE_URL}/webrtc/rooms",
            json={"name": "Test Room", "description": "Room for testing WebRTC"}
        )
        
        if response.status_code != 200:
            logger.error(f"Failed to create WebRTC room: {response.status_code}")
            return
        
        data = response.json()
        room_id = data.get("room_id")
        
        if not room_id:
            logger.error("Failed to get room ID from response")
            return
        
        logger.info(f"Created WebRTC room with ID: {room_id}")
    except Exception as e:
        logger.error(f"Error creating WebRTC room: {e}")
        return
    
    # Create and connect peers
    try:
        # Create first peer
        peer1 = WebRTCPeer(room_id, f"peer1_{uuid.uuid4()}")
        await peer1.connect()
        
        await asyncio.sleep(1)
        
        # Create second peer
        peer2 = WebRTCPeer(room_id, f"peer2_{uuid.uuid4()}")
        await peer2.connect()
        
        await asyncio.sleep(2)
        
        # Check room status
        response = requests.get(f"{BASE_URL}/webrtc/rooms/{room_id}")
        if response.status_code == 200:
            room_data = response.json()
            logger.info(f"Room status: {room_data}")
        
        # Peer 1 sends a message to the room
        await peer1.send_room_message({
            "text": "Hello from peer 1!",
            "timestamp": time.time()
        })
        
        await asyncio.sleep(2)
        
        # Peer 1 sends an offer to all other peers
        await peer1.send_offer_to_all()
        
        await asyncio.sleep(3)
        
        # Check if peers received the messages
        logger.info(f"Peer 1 other peers: {peer1.other_peers}")
        logger.info(f"Peer 2 other peers: {peer2.other_peers}")
        
        # Disconnect peers
        await peer1.disconnect()
        await peer2.disconnect()
        
        logger.info("WebRTC test completed successfully")
    
    except Exception as e:
        logger.error(f"Error in WebRTC test: {e}")

# Test stream upload and download
async def test_streaming() -> None:
    """Test stream upload and download functionality."""
    logger.info("Testing streaming functionality...")
    
    # Create a test file
    test_file_path = "test_stream_file.txt"
    test_file_content = "This is a test file for streaming.\n" * 1000  # ~30KB file
    
    try:
        with open(test_file_path, "w") as f:
            f.write(test_file_content)
        
        logger.info(f"Created test file: {test_file_path}")
        
        # Upload the file using the streaming endpoint
        with open(test_file_path, "rb") as f:
            files = {'file': (test_file_path, f)}
            response = requests.post(f"{BASE_URL}/stream/add", files=files)
            
            if response.status_code != 200:
                logger.error(f"Failed to upload file: {response.status_code}")
                return
            
            data = response.json()
            cid = data.get("cid")
            
            if not cid:
                logger.error("Failed to get CID from response")
                return
            
            logger.info(f"Uploaded file with CID: {cid}")
            logger.info(f"Upload stats: {data}")
        
        # Download the file using the streaming endpoint
        response = requests.get(f"{BASE_URL}/stream/cat/{cid}", stream=True)
        
        if response.status_code != 200:
            logger.error(f"Failed to download file: {response.status_code}")
            return
        
        # Save to a new file
        download_path = "test_stream_download.txt"
        with open(download_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        logger.info(f"Downloaded file to: {download_path}")
        
        # Verify the content
        with open(download_path, "r") as f:
            content = f.read()
            if content == test_file_content:
                logger.info("Download verification successful: content matches")
            else:
                logger.error("Download verification failed: content does not match")
        
        # Clean up
        os.remove(test_file_path)
        os.remove(download_path)
        
        logger.info("Streaming test completed successfully")
    
    except Exception as e:
        logger.error(f"Error in streaming test: {e}")
        # Clean up
        if os.path.exists(test_file_path):
            os.remove(test_file_path)
        if os.path.exists("test_stream_download.txt"):
            os.remove("test_stream_download.txt")

async def main() -> None:
    """Run the MCP streaming functionality tests."""
    logger.info("Starting MCP streaming functionality tests")
    
    # Check MCP server
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code != 200:
            logger.error(f"MCP server health check failed with status code: {response.status_code}")
            return
        
        data = response.json()
        if not data.get("success", False):
            logger.error(f"MCP server health check failed: {data.get('error', 'Unknown error')}")
            return
        
        logger.info(f"MCP server status: {data.get('status')}")
    except Exception as e:
        logger.error(f"Error connecting to MCP server: {e}")
        return
    
    # Run tests based on command line arguments
    if args.test in ['websocket', 'all']:
        await test_websocket()
    
    if args.test in ['webrtc', 'all']:
        await test_webrtc()
    
    if args.test == 'all':
        await test_streaming()
    
    logger.info("All tests completed")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Tests interrupted by user")
    except Exception as e:
        logger.error(f"Error running tests: {e}")