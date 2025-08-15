#!/usr/bin/env python
"""
Test script for the MCP WebSocket implementation.

This script tests the WebSocket functionality for the MCP server, including:
1. Real-time event notifications
2. Channel-based subscription system
3. Connection management with automatic recovery
4. Secure message broadcasting
"""

import logging
import sys
import os
import json
import time
import asyncio
import uuid
from typing import Dict, Any, List, Optional, Union
import websockets
import aiohttp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("websocket_test")

# Add parent directory to path if needed
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


class WebSocketClient:
    """Simple WebSocket client for testing."""
    
    def __init__(self, url: str):
        """Initialize the WebSocket client."""
        self.url = url
        self.connection = None
        self.connected = False
        self.messages = []
        self.connection_id = None
    
    async def connect(self) -> bool:
        """Connect to the WebSocket server."""
        try:
            self.connection = await websockets.connect(self.url)
            self.connected = True
            
            # Get welcome message
            welcome = await self.receive()
            if welcome and welcome.get("type") == "welcome":
                self.connection_id = welcome.get("connection_id")
                logger.info(f"Connected to WebSocket server with ID: {self.connection_id}")
                return True
            else:
                logger.error("Did not receive welcome message")
                await self.disconnect()
                return False
        
        except Exception as e:
            logger.error(f"Error connecting to WebSocket server: {e}")
            self.connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from the WebSocket server."""
        if self.connection:
            await self.connection.close()
        self.connected = False
        logger.info("Disconnected from WebSocket server")
    
    async def send(self, message: Dict[str, Any]) -> bool:
        """Send a message to the WebSocket server."""
        if not self.connected:
            logger.error("Not connected to WebSocket server")
            return False
        
        try:
            await self.connection.send(json.dumps(message))
            return True
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            self.connected = False
            return False
    
    async def receive(self) -> Optional[Dict[str, Any]]:
        """Receive a message from the WebSocket server."""
        if not self.connected:
            logger.error("Not connected to WebSocket server")
            return None
        
        try:
            message = await self.connection.recv()
            parsed = json.loads(message)
            self.messages.append(parsed)
            return parsed
        except Exception as e:
            logger.error(f"Error receiving message: {e}")
            self.connected = False
            return None
    
    async def subscribe(self, channel: str) -> bool:
        """Subscribe to a channel."""
        result = await self.send({
            "command": "subscribe",
            "channel": channel
        })
        
        if result:
            # Wait for subscription confirmation
            message = await self.receive()
            return message and message.get("type") == "subscribed" and message.get("channel") == channel
        
        return False
    
    async def unsubscribe(self, channel: str) -> bool:
        """Unsubscribe from a channel."""
        result = await self.send({
            "command": "unsubscribe",
            "channel": channel
        })
        
        if result:
            # Wait for unsubscription confirmation
            message = await self.receive()
            return message and message.get("type") == "unsubscribed" and message.get("channel") == channel
        
        return False
    
    async def unsubscribe_all(self) -> bool:
        """Unsubscribe from all channels."""
        result = await self.send({
            "command": "unsubscribe_all"
        })
        
        if result:
            # Wait for unsubscription confirmation
            message = await self.receive()
            return message and message.get("type") == "unsubscribed_all"
        
        return False
    
    async def ping(self) -> bool:
        """Ping the WebSocket server."""
        result = await self.send({
            "command": "ping"
        })
        
        if result:
            # Wait for pong
            message = await self.receive()
            return message and message.get("type") == "pong"
        
        return False
    
    async def echo(self, data: Any) -> bool:
        """Send an echo request to the WebSocket server."""
        result = await self.send({
            "command": "echo",
            "data": data
        })
        
        if result:
            # Wait for echo response
            message = await self.receive()
            return message and message.get("type") == "echo" and message.get("data") == data
        
        return False
    
    def get_messages(self) -> List[Dict[str, Any]]:
        """Get all received messages."""
        return self.messages


class RESTClient:
    """Simple REST client for testing the WebSocket API."""
    
    def __init__(self, base_url: str, admin_key: str = "test_admin_key"):
        """Initialize the REST client."""
        self.base_url = base_url
        self.admin_key = admin_key
    
    async def get_status(self) -> Dict[str, Any]:
        """Get WebSocket service status."""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base_url}/status") as response:
                return await response.json()
    
    async def broadcast_message(self, channel: str, message: Dict[str, Any]) -> Dict[str, Any]:
        """Broadcast a message to a channel."""
        headers = {"admin-key": self.admin_key}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/broadcast",
                json=message,
                params={"channel": channel},
                headers=headers
            ) as response:
                return await response.json()
    
    async def trigger_ipfs_event(
        self, event_type: str, cid: Optional[str] = None, details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Trigger an IPFS event."""
        headers = {"admin-key": self.admin_key}
        params = {"event_type": event_type}
        
        if cid:
            params["cid"] = cid
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/ipfs/event",
                json=details,
                params=params,
                headers=headers
            ) as response:
                return await response.json()
    
    async def trigger_storage_event(
        self, backend: str, operation: str, cid: Optional[str] = None, details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Trigger a storage event."""
        headers = {"admin-key": self.admin_key}
        params = {"backend": backend, "operation": operation}
        
        if cid:
            params["cid"] = cid
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/storage/event",
                json=details,
                params=params,
                headers=headers
            ) as response:
                return await response.json()


async def run_websocket_test(
    websocket_url: str = "ws://localhost:8000/ws",
    rest_url: str = "http://localhost:8000/api/v0/realtime"
):
    """Run comprehensive tests on the WebSocket implementation."""
    logger.info("Starting MCP WebSocket test...")
    
    try:
        # Import the websocket module to check it exists
        try:
            from ipfs_kit_py.mcp_websocket import ConnectionManager, WebSocketService
            logger.info("Successfully imported websocket module")
        except ImportError:
            logger.info("Could not import websocket module directly - testing externally")
        
        # Create WebSocket client
        ws_client = WebSocketClient(websocket_url)
        
        # Test 1: Connect to WebSocket server
        logger.info("Test 1: Connect to WebSocket server")
        connected = await ws_client.connect()
        
        if connected:
            logger.info("✅ WebSocket connection successful")
            logger.info(f"Connection ID: {ws_client.connection_id}")
        else:
            logger.error("❌ WebSocket connection failed")
            return False
        
        # Test 2: Basic echo functionality
        logger.info("Test 2: Basic echo functionality")
        echo_data = {
            "test": "data",
            "timestamp": time.time(),
            "random": str(uuid.uuid4())
        }
        
        echo_result = await ws_client.echo(echo_data)
        
        if echo_result:
            logger.info("✅ Echo test successful")
        else:
            logger.error("❌ Echo test failed")
            await ws_client.disconnect()
            return False
        
        # Test 3: Ping-pong
        logger.info("Test 3: Ping-pong")
        ping_result = await ws_client.ping()
        
        if ping_result:
            logger.info("✅ Ping-pong test successful")
        else:
            logger.error("❌ Ping-pong test failed")
            await ws_client.disconnect()
            return False
        
        # Test 4: Channel subscription
        logger.info("Test 4: Channel subscription")
        test_channel = f"test:{uuid.uuid4()}"
        subscribe_result = await ws_client.subscribe(test_channel)
        
        if subscribe_result:
            logger.info(f"✅ Subscription to {test_channel} successful")
        else:
            logger.error(f"❌ Subscription to {test_channel} failed")
            await ws_client.disconnect()
            return False
        
        # Test 5: Create REST client for broadcasting
        logger.info("Test 5: Create REST client for broadcasting")
        rest_client = RESTClient(rest_url)
        
        # Get WebSocket service status
        status = await rest_client.get_status()
        logger.info(f"WebSocket service status: {json.dumps(status, indent=2)}")
        
        if status.get("success", False):
            logger.info("✅ WebSocket service status check successful")
        else:
            logger.error("❌ WebSocket service status check failed")
            await ws_client.disconnect()
            return False
        
        # Test 6: Broadcast message to channel
        logger.info("Test 6: Broadcast message to channel")
        broadcast_message = {
            "type": "test_message",
            "content": f"Test message at {time.time()}",
            "id": str(uuid.uuid4())
        }
        
        broadcast_result = await rest_client.broadcast_message(test_channel, broadcast_message)
        logger.info(f"Broadcast result: {json.dumps(broadcast_result, indent=2)}")
        
        if broadcast_result.get("success", False):
            logger.info("✅ Message broadcast API call successful")
            
            # Wait for the message
            logger.info("Waiting for broadcast message...")
            received_message = None
            try:
                # Set a timeout for receiving the message
                received_message = await asyncio.wait_for(ws_client.receive(), timeout=2.0)
            except asyncio.TimeoutError:
                logger.error("❌ Timeout waiting for broadcast message")
                await ws_client.disconnect()
                return False
            
            if received_message:
                logger.info(f"Received message: {json.dumps(received_message, indent=2)}")
                if received_message.get("type") == broadcast_message.get("type") and \
                   received_message.get("content") == broadcast_message.get("content") and \
                   received_message.get("id") == broadcast_message.get("id"):
                    logger.info("✅ Received correct broadcast message")
                else:
                    logger.error("❌ Received message does not match broadcast message")
                    await ws_client.disconnect()
                    return False
            else:
                logger.error("❌ Did not receive broadcast message")
                await ws_client.disconnect()
                return False
        else:
            logger.error("❌ Message broadcast API call failed")
            await ws_client.disconnect()
            return False
        
        # Test 7: IPFS event broadcasting
        logger.info("Test 7: IPFS event broadcasting")
        
        # Subscribe to IPFS event channel
        ipfs_channel = "ipfs:add"
        subscribe_result = await ws_client.subscribe(ipfs_channel)
        
        if subscribe_result:
            logger.info(f"✅ Subscription to {ipfs_channel} successful")
            
            # Trigger IPFS event
            test_cid = f"bafytest{uuid.uuid4().hex[:16]}"
            ipfs_event_result = await rest_client.trigger_ipfs_event(
                event_type="add",
                cid=test_cid,
                details={"size": 1024, "name": "test.txt"}
            )
            
            logger.info(f"IPFS event result: {json.dumps(ipfs_event_result, indent=2)}")
            
            if ipfs_event_result.get("success", False):
                logger.info("✅ IPFS event API call successful")
                
                # Wait for the event
                logger.info("Waiting for IPFS event...")
                received_event = None
                try:
                    received_event = await asyncio.wait_for(ws_client.receive(), timeout=2.0)
                except asyncio.TimeoutError:
                    logger.error("❌ Timeout waiting for IPFS event")
                    await ws_client.disconnect()
                    return False
                
                if received_event:
                    logger.info(f"Received IPFS event: {json.dumps(received_event, indent=2)}")
                    if received_event.get("event_type") == "add" and \
                       received_event.get("cid") == test_cid:
                        logger.info("✅ Received correct IPFS event")
                    else:
                        logger.error("❌ Received event does not match IPFS event")
                        await ws_client.disconnect()
                        return False
                else:
                    logger.error("❌ Did not receive IPFS event")
                    await ws_client.disconnect()
                    return False
            else:
                logger.error("❌ IPFS event API call failed")
                await ws_client.disconnect()
                return False
        else:
            logger.error(f"❌ Subscription to {ipfs_channel} failed")
            await ws_client.disconnect()
            return False
        
        # Test 8: Storage event broadcasting
        logger.info("Test 8: Storage event broadcasting")
        
        # Subscribe to storage event channel
        storage_channel = "storage:s3"
        subscribe_result = await ws_client.subscribe(storage_channel)
        
        if subscribe_result:
            logger.info(f"✅ Subscription to {storage_channel} successful")
            
            # Trigger storage event
            test_cid = f"bafytest{uuid.uuid4().hex[:16]}"
            storage_event_result = await rest_client.trigger_storage_event(
                backend="s3",
                operation="store",
                cid=test_cid,
                details={"size": 2048, "bucket": "test-bucket", "key": "test-key.txt"}
            )
            
            logger.info(f"Storage event result: {json.dumps(storage_event_result, indent=2)}")
            
            if storage_event_result.get("success", False):
                logger.info("✅ Storage event API call successful")
                
                # Wait for the event
                logger.info("Waiting for storage event...")
                received_event = None
                try:
                    received_event = await asyncio.wait_for(ws_client.receive(), timeout=2.0)
                except asyncio.TimeoutError:
                    logger.error("❌ Timeout waiting for storage event")
                    await ws_client.disconnect()
                    return False
                
                if received_event:
                    logger.info(f"Received storage event: {json.dumps(received_event, indent=2)}")
                    if received_event.get("backend") == "s3" and \
                       received_event.get("operation") == "store" and \
                       received_event.get("cid") == test_cid:
                        logger.info("✅ Received correct storage event")
                    else:
                        logger.error("❌ Received event does not match storage event")
                        await ws_client.disconnect()
                        return False
                else:
                    logger.error("❌ Did not receive storage event")
                    await ws_client.disconnect()
                    return False
            else:
                logger.error("❌ Storage event API call failed")
                await ws_client.disconnect()
                return False
        else:
            logger.error(f"❌ Subscription to {storage_channel} failed")
            await ws_client.disconnect()
            return False
        
        # Test 9: Unsubscribe from specific channel
        logger.info("Test 9: Unsubscribe from specific channel")
        unsubscribe_result = await ws_client.unsubscribe(test_channel)
        
        if unsubscribe_result:
            logger.info(f"✅ Unsubscribe from {test_channel} successful")
            
            # Try to broadcast to this channel
            broadcast_message = {
                "type": "test_message_after_unsub",
                "content": f"This message should not be received at {time.time()}",
                "id": str(uuid.uuid4())
            }
            
            await rest_client.broadcast_message(test_channel, broadcast_message)
            
            # Wait a moment to see if we receive a message
            try:
                # Use a very short timeout since we shouldn't receive anything
                received_message = await asyncio.wait_for(ws_client.receive(), timeout=1.0)
                
                # If we received a message, make sure it's not from the unsubscribed channel
                if received_message.get("type") == broadcast_message.get("type"):
                    logger.error("❌ Received message from unsubscribed channel")
                    await ws_client.disconnect()
                    return False
                else:
                    logger.info("Received message from another channel (which is fine)")
            except asyncio.TimeoutError:
                logger.info("✅ Did not receive message from unsubscribed channel (expected)")
        else:
            logger.error(f"❌ Unsubscribe from {test_channel} failed")
            await ws_client.disconnect()
            return False
        
        # Test 10: Unsubscribe from all channels
        logger.info("Test 10: Unsubscribe from all channels")
        unsubscribe_all_result = await ws_client.unsubscribe_all()
        
        if unsubscribe_all_result:
            logger.info("✅ Unsubscribe from all channels successful")
            
            # Try to broadcast to IPFS channel
            await rest_client.trigger_ipfs_event(
                event_type="add",
                cid=f"bafytest{uuid.uuid4().hex[:16]}",
                details={"size": 1024, "name": "test_after_unsub_all.txt"}
            )
            
            # Wait a moment to see if we receive a message
            try:
                # Use a very short timeout since we shouldn't receive anything
                received_message = await asyncio.wait_for(ws_client.receive(), timeout=1.0)
                logger.error("❌ Received message after unsubscribing from all channels")
                await ws_client.disconnect()
                return False
            except asyncio.TimeoutError:
                logger.info("✅ Did not receive message after unsubscribing from all channels (expected)")
        else:
            logger.error("❌ Unsubscribe from all channels failed")
            await ws_client.disconnect()
            return False
        
        # Test 11: Disconnect and reconnect
        logger.info("Test 11: Disconnect and reconnect")
        await ws_client.disconnect()
        logger.info("Disconnected from WebSocket server")
        
        # Wait a moment
        await asyncio.sleep(1)
        
        # Reconnect
        reconnected = await ws_client.connect()
        
        if reconnected:
            logger.info("✅ WebSocket reconnection successful")
            logger.info(f"New connection ID: {ws_client.connection_id}")
        else:
            logger.error("❌ WebSocket reconnection failed")
            return False
        
        # Final disconnect
        await ws_client.disconnect()
        
        logger.info("All WebSocket tests completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Error testing WebSocket functionality: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


if __name__ == "__main__":
    # Parse command line arguments for WebSocket and REST URLs
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--ws-url", default="ws://localhost:8000/ws", help="WebSocket server URL")
    parser.add_argument("--rest-url", default="http://localhost:8000/api/v0/realtime", help="REST API URL")
    # Only parse args when running the script directly, not when imported by pytest
    if __name__ == "__main__":
        args = parser.parse_args()
    else:
        # When run under pytest, use default values
        args = parser.parse_args([])
    
    # Run the test asynchronously
    if sys.platform == "win32":
        # Windows requires this for asyncio.run()
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    result = asyncio.run(run_websocket_test(args.ws_url, args.rest_url))
    
    if result:
        logger.info("✅ MCP WebSocket test passed!")
        sys.exit(0)
    else:
        logger.error("❌ MCP WebSocket test failed")
        sys.exit(1)