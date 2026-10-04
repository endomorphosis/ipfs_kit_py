"""
Mock implementation for FastAPI WebSocket.

This module provides mock implementations for FastAPI WebSocket
and related components to allow tests to run without the actual dependency.
"""

import logging
import json
from typing import Dict, Any, Optional, List, Union, Callable, Awaitable

logger = logging.getLogger(__name__)

class WebSocket:
    """Mock WebSocket implementation for testing."""
    
    def __init__(self):
        self.accepted = False
        self.closed = False
        self.sent_messages = []
        self.received_messages = []
        self.client_state = "CONNECTING"
        self.headers = {}
        self.query_params = {}
        self.path_params = {}
        self.cookies = {}
        
    async def accept(self):
        """Accept the WebSocket connection."""
        self.accepted = True
        self.client_state = "CONNECTED"
        logger.info("WebSocket connection accepted")
        return True
        
    async def close(self, code: int = 1000):
        """Close the WebSocket connection."""
        self.closed = True
        self.client_state = "DISCONNECTED"
        logger.info(f"WebSocket connection closed with code {code}")
        return True
        
    async def send_text(self, data: str):
        """Send text data to the client."""
        self.sent_messages.append({"type": "text", "data": data})
        logger.info(f"Sent text message: {data}")
        return True
        
    async def send_json(self, data: Dict[str, Any]):
        """Send JSON data to the client."""
        text_data = json.dumps(data)
        self.sent_messages.append({"type": "json", "data": data})
        logger.info(f"Sent JSON message: {data}")
        return True
        
    async def send_bytes(self, data: bytes):
        """Send binary data to the client."""
        self.sent_messages.append({"type": "bytes", "data": data})
        logger.info(f"Sent binary message: {len(data)} bytes")
        return True
        
    async def receive_text(self):
        """Receive text data from the client."""
        if not self.received_messages:
            return ""
        msg = self.received_messages.pop(0)
        if isinstance(msg, str):
            return msg
        elif isinstance(msg, dict):
            return json.dumps(msg)
        elif isinstance(msg, bytes):
            return msg.decode("utf-8")
        return str(msg)
        
    async def receive_json(self):
        """Receive JSON data from the client."""
        if not self.received_messages:
            return {}
        msg = self.received_messages.pop(0)
        if isinstance(msg, str):
            return json.loads(msg)
        elif isinstance(msg, dict):
            return msg
        elif isinstance(msg, bytes):
            return json.loads(msg.decode("utf-8"))
        return {}
        
    async def receive_bytes(self):
        """Receive binary data from the client."""
        if not self.received_messages:
            return b""
        msg = self.received_messages.pop(0)
        if isinstance(msg, str):
            return msg.encode("utf-8")
        elif isinstance(msg, dict):
            return json.dumps(msg).encode("utf-8")
        elif isinstance(msg, bytes):
            return msg
        return str(msg).encode("utf-8")

class WebSocketDisconnect(Exception):
    """Exception raised when WebSocket connection is closed."""
    
    def __init__(self, code: int = 1000):
        self.code = code
        super().__init__(f"WebSocket disconnected with code {code}")

# Patch the fastapi module to use our mock WebSocket
import sys
from types import ModuleType

# Create mock fastapi module
fastapi_module = ModuleType("fastapi")
fastapi_module.WebSocket = WebSocket
fastapi_module.WebSocketDisconnect = WebSocketDisconnect

# Add to sys.modules to allow importing
sys.modules["fastapi"] = fastapi_module