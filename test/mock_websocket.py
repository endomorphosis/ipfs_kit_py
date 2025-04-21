"""Mock FastAPI WebSocket Module

This module provides mock implementations of FastAPI WebSocket classes
for testing without requiring the actual FastAPI package.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Union, Callable

logger = logging.getLogger(__name__)


class WebSocket:
    """Mock WebSocket class for testing."""
    
    def __init__(self):
        self.client_state = "connected"
        self.application_state = "connected"
        self.received_data = []
        self.sent_data = []
        self.headers = {}
        self.query_params = {}
        self.path_params = {}
        self.cookies = {}
        self.closed = False
    
    async def accept(self) -> None:
        """Accept the WebSocket connection."""
        logger.info("WebSocket connection accepted")
        self.client_state = "connected"
        self.application_state = "connected"
    
    async def close(self, code: int = 1000, reason: Optional[str] = None) -> None:
        """Close the WebSocket connection."""
        logger.info(f"WebSocket connection closed (code: {code}, reason: {reason})")
        self.client_state = "disconnected"
        self.application_state = "disconnected"
        self.closed = True
    
    async def send_text(self, data: str) -> None:
        """Send text data over the WebSocket."""
        logger.info(f"Sending text over WebSocket: {data}")
        self.sent_data.append(("text", data))
    
    async def send_json(self, data: Any) -> None:
        """Send JSON data over the WebSocket."""
        logger.info(f"Sending JSON over WebSocket: {data}")
        self.sent_data.append(("json", data))
    
    async def send_bytes(self, data: bytes) -> None:
        """Send binary data over the WebSocket."""
        logger.info(f"Sending binary data over WebSocket: {len(data)} bytes")
        self.sent_data.append(("bytes", data))
    
    async def receive_text(self) -> str:
        """Receive text data from the WebSocket."""
        if self.received_data:
            data_type, data = self.received_data.pop(0)
            if data_type == "text":
                return data
        return "mock_text_data"
    
    async def receive_json(self) -> Any:
        """Receive JSON data from the WebSocket."""
        if self.received_data:
            data_type, data = self.received_data.pop(0)
            if data_type == "json":
                return data
        return {"message": "mock_json_data"}
    
    async def receive_bytes(self) -> bytes:
        """Receive binary data from the WebSocket."""
        if self.received_data:
            data_type, data = self.received_data.pop(0)
            if data_type == "bytes":
                return data
        return b"mock_binary_data"
    
    def mock_receive(self, data_type: str, data: Any) -> None:
        """Mock receiving data from the client."""
        self.received_data.append((data_type, data))


class WebSocketDisconnect(Exception):
    """Exception raised when a WebSocket is disconnected."""
    
    def __init__(self, code: int = 1000, reason: Optional[str] = None):
        self.code = code
        self.reason = reason
        super().__init__(f"WebSocket disconnected with code {code}: {reason}")


# Add the mock classes to the FastAPI modules
import sys
try:
    import unittest.mock as mock
    
    # Create a mock FastAPI module
    mock_fastapi = mock.MagicMock()
    mock_fastapi.WebSocket = WebSocket
    mock_fastapi.WebSocketDisconnect = WebSocketDisconnect
    
    # Add FastAPI to sys.modules if it doesn't exist
    if 'fastapi' not in sys.modules:
        sys.modules['fastapi'] = mock_fastapi
        logger.info("Added mock FastAPI module to sys.modules")
    
except ImportError:
    logger.warning("unittest.mock not available, skipping FastAPI mock setup")