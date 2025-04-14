"""
WebSocket server implementation for MCP server.

This module provides a concrete server implementation for the WebSocket
notifications system, addressing the WebSocket Integration requirements
in the MCP roadmap, particularly the 'Connection management with automatic recovery' component.
"""

import asyncio
import logging
import json
import time
from typing import Dict, Any, Optional, List, Set
import threading
import websockets
from websockets.server import WebSocketServerProtocol
from websockets.exceptions import ConnectionClosed

from .websocket_notifications import get_ws_manager, EventType

# Configure logger
logger = logging.getLogger(__name__)

class WebSocketServer:
    """
    WebSocket server for the MCP system.
    
    This class implements a standalone WebSocket server that handles
    connections, message routing, and automatic reconnection strategies.
    """
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8765, ping_interval: int = 30):
        """
        Initialize the WebSocket server.
        
        Args:
            host: Hostname to bind to
            port: Port to listen on
            ping_interval: Interval for sending pings to clients (seconds)
        """
        self.host = host
        self.port = port
        self.ping_interval = ping_interval
        self.server = None
        self.running = False
        self.connections: Dict[str, WebSocketServerProtocol] = {}
        self.ws_manager = get_ws_manager()
        self.lock = threading.RLock()
        self.start_timestamp = None
    
    async def start(self):
        """Start the WebSocket server."""
        if self.running:
            logger.warning("WebSocket server is already running")
            return
        
        logger.info(f"Starting WebSocket server on {self.host}:{self.port}")
        
        try:
            # Initialize the WebSocket manager
            self.ws_manager.start()
            
            # Start the WebSocket server
            self.server = await websockets.serve(
                self.handle_connection,
                self.host,
                self.port
            )
            
            self.running = True
            self.start_timestamp = time.time()
            
            # Start the ping task
            asyncio.create_task(self.ping_clients())
            
            logger.info(f"WebSocket server started successfully on {self.host}:{self.port}")
            
            # Notify about server start
            self.ws_manager.notify("system", {
                "type": EventType.SYSTEM,
                "action": "server_started",
                "host": self.host,
                "port": self.port,
                "timestamp": time.time()
            })
            
        except Exception as e:
            logger.error(f"Failed to start WebSocket server: {e}")
            raise
    
    async def stop(self):
        """Stop the WebSocket server."""
        if not self.running:
            logger.warning("WebSocket server is not running")
            return
        
        logger.info("Stopping WebSocket server")
        
        try:
            # Close all connections
            close_tasks = []
            for conn_id, connection in list(self.connections.items()):
                close_tasks.append(self.close_connection(conn_id, 1001, "Server shutting down"))
            
            if close_tasks:
                await asyncio.gather(*close_tasks, return_exceptions=True)
            
            # Stop the WebSocket server
            self.server.close()
            await self.server.wait_closed()
            
            # Stop the WebSocket manager
            self.ws_manager.stop()
            
            self.running = False
            logger.info("WebSocket server stopped successfully")
            
        except Exception as e:
            logger.error(f"Error stopping WebSocket server: {e}")
            raise
    
    async def handle_connection(self, websocket: WebSocketServerProtocol, path: str):
        """
        Handle a new WebSocket connection.
        
        Args:
            websocket: WebSocket connection
            path: Connection path
        """
        # Register the connection with the WebSocket manager
        conn_id = self.ws_manager.register_connection(websocket)
        
        # Store the connection
        with self.lock:
            self.connections[conn_id] = websocket
        
        logger.info(f"New WebSocket connection: {conn_id} from {websocket.remote_address} (path: {path})")
        
        try:
            # Send a welcome message
            await websocket.send(json.dumps({
                "type": "system",
                "action": "welcome",
                "connection_id": conn_id,
                "timestamp": time.time(),
                "server_version": "1.0.0",
                "server_uptime": time.time() - (self.start_timestamp or time.time())
            }))
            
            # Main message loop
            async for message in websocket:
                try:
                    # Handle the message
                    await self.ws_manager.handle_message(conn_id, message)
                except Exception as e:
                    logger.error(f"Error handling message from {conn_id}: {e}")
                    # Send error notification to client
                    await websocket.send(json.dumps({
                        "type": "error",
                        "error": str(e),
                        "timestamp": time.time()
                    }))
        
        except ConnectionClosed as e:
            logger.info(f"WebSocket connection closed: {conn_id} - {e.code} {e.reason}")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            # Unregister the connection
            self.ws_manager.unregister_connection(conn_id)
            
            # Remove the connection from our store
            with self.lock:
                if conn_id in self.connections:
                    del self.connections[conn_id]
            
            logger.info(f"WebSocket connection closed: {conn_id}")
    
    async def close_connection(self, conn_id: str, code: int = 1000, reason: str = ""):
        """
        Close a specific WebSocket connection.
        
        Args:
            conn_id: Connection ID to close
            code: WebSocket close code
            reason: Close reason
        """
        with self.lock:
            if conn_id in self.connections:
                websocket = self.connections[conn_id]
                try:
                    await websocket.close(code, reason)
                    logger.info(f"Closed WebSocket connection: {conn_id} - {code} {reason}")
                except Exception as e:
                    logger.error(f"Error closing WebSocket connection {conn_id}: {e}")
                finally:
                    # Remove the connection from our store
                    if conn_id in self.connections:
                        del self.connections[conn_id]
    
    async def ping_clients(self):
        """Periodically ping clients to keep connections alive."""
        while self.running:
            try:
                # Send ping to all connections
                ping_count = 0
                with self.lock:
                    for conn_id, websocket in list(self.connections.items()):
                        try:
                            pong_waiter = await websocket.ping()
                            ping_count += 1
                            # Start a task to handle the pong response
                            asyncio.create_task(self.handle_pong(conn_id, pong_waiter))
                        except Exception as e:
                            logger.error(f"Error pinging client {conn_id}: {e}")
                
                if ping_count > 0:
                    logger.debug(f"Sent ping to {ping_count} clients")
            
            except Exception as e:
                logger.error(f"Error in ping task: {e}")
            
            # Wait for the next ping interval
            await asyncio.sleep(self.ping_interval)
    
    async def handle_pong(self, conn_id: str, pong_waiter: asyncio.Future):
        """
        Handle a pong response from a client.
        
        Args:
            conn_id: Connection ID
            pong_waiter: Future for the pong response
        """
        try:
            # Wait for the pong with a timeout
            await asyncio.wait_for(pong_waiter, timeout=self.ping_interval / 2)
            
            # Update the last ping time
            if conn_id in self.connections:
                self.ws_manager.connections[conn_id]["last_ping"] = time.time()
            
        except asyncio.TimeoutError:
            logger.warning(f"Client {conn_id} did not respond to ping, checking connection...")
            # Check if the connection is still open
            if conn_id in self.connections:
                try:
                    # Try to send a small message
                    await self.connections[conn_id].send(json.dumps({
                        "type": "ping",
                        "timestamp": time.time()
                    }))
                except Exception:
                    logger.warning(f"Client {conn_id} appears to be disconnected, closing connection")
                    # Close the connection
                    await self.close_connection(conn_id, 1001, "Ping timeout")
        except Exception as e:
            logger.error(f"Error handling pong from {conn_id}: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get server statistics.
        
        Returns:
            Dict with server statistics
        """
        return {
            "server": {
                "host": self.host,
                "port": self.port,
                "running": self.running,
                "uptime": time.time() - (self.start_timestamp or time.time()) if self.running else 0,
                "connections": len(self.connections)
            },
            "websocket_manager": self.ws_manager.get_stats()
        }

# Global server instance
_ws_server = None

def get_ws_server() -> WebSocketServer:
    """
    Get the global WebSocket server instance.
    
    Returns:
        WebSocket server instance
    """
    global _ws_server
    if _ws_server is None:
        _ws_server = WebSocketServer()
    return _ws_server

async def start_ws_server():
    """Start the global WebSocket server."""
    server = get_ws_server()
    await server.start()

async def stop_ws_server():
    """Stop the global WebSocket server."""
    server = get_ws_server()
    await server.stop()
