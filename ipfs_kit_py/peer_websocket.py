"""
WebSocket-based peer discovery for IPFS Kit.

This module enables finding and connecting to IPFS peers using WebSockets.
It provides both server and client functionality:
1. Server: Advertises local peer information over WebSockets
2. Client: Discovers and connects to remote peers over WebSockets

This enables easier NAT traversal and peer discovery compared to traditional
IPFS peer discovery methods, especially in environments where direct connections
are difficult due to firewalls or NAT.
"""

import os
import json
import time
import uuid
import logging
import anyio
from typing import Dict, List, Any, Optional, Set, Callable
from enum import Enum

# WebSocket imports - wrapped in try/except for graceful fallback
try:
    import websockets
    from websockets.server import WebSocketServerProtocol
    from websockets.client import WebSocketClientProtocol
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False
    
# FastAPI imports for server integration
try:
    from fastapi import WebSocket, WebSocketDisconnect, FastAPI
    from starlette.websockets import WebSocketState
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

# Configure logging
logger = logging.getLogger(__name__)

# Message types
class MessageType(str, Enum):
    """Types of peer discovery messages."""
    PEER_INFO = "peer_info"
    PEER_REQUEST = "peer_request"
    PEER_LIST = "peer_list"
    PEER_CONNECT = "peer_connect"
    PEER_DISCONNECT = "peer_disconnect"
    HEARTBEAT = "heartbeat"
    ERROR = "error"

class PeerRole(str, Enum):
    """Peer roles in the network."""
    MASTER = "master"
    WORKER = "worker"
    LEECHER = "leecher"
    GATEWAY = "gateway"

class PeerInfo:
    """Information about a peer in the network."""
    
    def __init__(self, 
                peer_id: str, 
                multiaddrs: List[str],
                role: PeerRole = PeerRole.LEECHER,
                capabilities: List[str] = None,
                resources: Dict[str, Any] = None,
                metadata: Dict[str, Any] = None):
        """
        Initialize peer information.
        
        Args:
            peer_id: IPFS peer ID
            multiaddrs: List of multiaddresses for connecting to this peer
            role: Role of this peer in the network
            capabilities: List of capabilities this peer supports
            resources: Information about peer resources
            metadata: Additional peer metadata
        """
        self.peer_id = peer_id
        self.multiaddrs = multiaddrs
        self.role = role
        self.capabilities = capabilities or []
        self.resources = resources or {}
        self.metadata = metadata or {}
        self.last_seen = time.time()
        self.connection_success_rate = 1.0
        self.connection_attempts = 0
        self.successful_connections = 0
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert peer info to dictionary for serialization."""
        return {
            "peer_id": self.peer_id,
            "multiaddrs": self.multiaddrs,
            "role": self.role,
            "capabilities": self.capabilities,
            "resources": self.resources,
            "metadata": self.metadata,
            "last_seen": self.last_seen,
            "connection_success_rate": self.connection_success_rate
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PeerInfo':
        """Create a PeerInfo object from a dictionary."""
        peer_info = cls(
            peer_id=data["peer_id"],
            multiaddrs=data["multiaddrs"],
            role=data.get("role", PeerRole.LEECHER),
            capabilities=data.get("capabilities", []),
            resources=data.get("resources", {}),
            metadata=data.get("metadata", {})
        )
        
        # Set additional fields if available
        if "last_seen" in data:
            peer_info.last_seen = data["last_seen"]
            
        if "connection_success_rate" in data:
            peer_info.connection_success_rate = data["connection_success_rate"]
            
        return peer_info
        
    def update_from_dict(self, data: Dict[str, Any]):
        """Update peer info from a dictionary."""
        if "multiaddrs" in data:
            self.multiaddrs = data["multiaddrs"]
            
        if "role" in data:
            self.role = data["role"]
            
        if "capabilities" in data:
            self.capabilities = data["capabilities"]
            
        if "resources" in data:
            self.resources = data["resources"]
            
        if "metadata" in data:
            # Merge metadata rather than replace
            self.metadata.update(data["metadata"])
            
        # Always update last_seen
        self.last_seen = time.time()
        
    def record_connection_attempt(self, success: bool):
        """
        Record a connection attempt to this peer.
        
        Args:
            success: Whether the connection attempt was successful
        """
        self.connection_attempts += 1
        if success:
            self.successful_connections += 1
            
        # Update success rate
        self.connection_success_rate = self.successful_connections / self.connection_attempts

class PeerWebSocketServer:
    """
    WebSocket server for peer discovery.
    
    This server:
    1. Advertises local peer information to clients
    2. Receives information about other peers from clients
    3. Facilitates peer discovery by sharing peer lists
    """
    
    def __init__(self, 
                local_peer_info: PeerInfo,
                max_peers: int = 100,
                heartbeat_interval: int = 30,
                peer_ttl: int = 300):
        """
        Initialize the peer WebSocket server.
        
        Args:
            local_peer_info: Information about the local peer
            max_peers: Maximum number of peers to track
            heartbeat_interval: Heartbeat interval in seconds
            peer_ttl: Time-to-live for peer information in seconds
        """
        self.local_peer_info = local_peer_info
        self.max_peers = max_peers
        self.heartbeat_interval = heartbeat_interval
        self.peer_ttl = peer_ttl
        
        self.peers: Dict[str, PeerInfo] = {}
        self.connections: Dict[WebSocketServerProtocol, str] = {}
        self.server = None
        self.cleanup_task = None
        self.heartbeat_task = None
        self.running = False
        
    async def start(self, host: str = "0.0.0.0", port: int = 8765):
        """
        Start the WebSocket server.
        
        Args:
            host: Host address to bind to
            port: Port to listen on
        """
        if not WEBSOCKET_AVAILABLE:
            raise ImportError("WebSockets library not available")
            
        self.running = True
        
        # Start server
        self.server = await websockets.serve(self.handle_connection, host, port)
        logger.info(f"Peer WebSocket server started on {host}:{port}")
        
        # Start background tasks
        self.cleanup_task = anyio.create_task(self._cleanup_peers())
        self.heartbeat_task = anyio.create_task(self._send_heartbeats())
        
        # Add local peer to known peers
        self.peers[self.local_peer_info.peer_id] = self.local_peer_info
        
    async def stop(self):
        """Stop the WebSocket server."""
        self.running = False
        
        # Cancel background tasks
        if self.cleanup_task:
            try:
                self.cleanup_task.cancel()
                # Wait for cancellation to complete
                try:
                    await anyio.wait_for(self.cleanup_task, timeout=2.0)
                except (anyio.TimeoutError, anyio.CancelledError):
                    pass
            except Exception as e:
                logger.error(f"Error canceling cleanup task: {e}")
            
        if self.heartbeat_task:
            try:
                self.heartbeat_task.cancel()
                # Wait for cancellation to complete
                try:
                    await anyio.wait_for(self.heartbeat_task, timeout=2.0)
                except (anyio.TimeoutError, anyio.CancelledError):
                    pass
            except Exception as e:
                logger.error(f"Error canceling heartbeat task: {e}")
            
        # Close all active connections
        for websocket in list(self.connections.keys()):
            try:
                await websocket.close(code=1001, reason="Server shutting down")
            except Exception as e:
                logger.error(f"Error closing WebSocket connection: {e}")
                
        # Clear connections dictionary
        self.connections.clear()
            
        # Close server
        if self.server:
            try:
                self.server.close()
                await self.server.wait_closed()
            except Exception as e:
                logger.error(f"Error closing WebSocket server: {e}")
            
        logger.info("Peer WebSocket server stopped")
        
    async def handle_connection(self, websocket: WebSocketServerProtocol, path: str):
        """
        Handle a new WebSocket connection.
        
        Args:
            websocket: WebSocket connection
            path: Connection path
        """
        try:
            # Send local peer info
            await websocket.send(json.dumps({
                "type": MessageType.PEER_INFO,
                "peer": self.local_peer_info.to_dict(),
                "timestamp": time.time()
            }))
            
            # Process messages until disconnection
            while True:
                message = await websocket.recv()
                await self._process_message(websocket, message)
                
        except websockets.exceptions.ConnectionClosed:
            # Client disconnected
            if websocket in self.connections:
                peer_id = self.connections[websocket]
                del self.connections[websocket]
                logger.info(f"Client disconnected: {peer_id}")
                
        except Exception as e:
            logger.error(f"Error handling WebSocket connection: {e}")
            
    async def _process_message(self, websocket: WebSocketServerProtocol, message: str):
        """
        Process a message from a client.
        
        Args:
            websocket: WebSocket connection
            message: Message content
        """
        try:
            data = json.loads(message)
            message_type = data.get("type")
            
            if message_type == MessageType.PEER_INFO:
                # Update peer information
                peer_data = data.get("peer", {})
                peer_id = peer_data.get("peer_id")
                
                if not peer_id:
                    await self._send_error(websocket, "Missing peer_id in PEER_INFO message")
                    return
                    
                # Store connection if not already stored
                if websocket not in self.connections:
                    self.connections[websocket] = peer_id
                    
                # Update or create peer info
                if peer_id in self.peers:
                    self.peers[peer_id].update_from_dict(peer_data)
                else:
                    self.peers[peer_id] = PeerInfo.from_dict(peer_data)
                    
                logger.debug(f"Received peer info from {peer_id}")
                
            elif message_type == MessageType.PEER_REQUEST:
                # Client is requesting peer list
                await self._send_peer_list(websocket, data.get("filter", {}))
                
            elif message_type == MessageType.PEER_CONNECT:
                # Client is connecting to a peer
                target_id = data.get("target_id")
                if not target_id:
                    await self._send_error(websocket, "Missing target_id in PEER_CONNECT message")
                    return
                    
                if target_id not in self.peers:
                    await self._send_error(websocket, f"Unknown peer: {target_id}")
                    return
                    
                # Record connection attempt (no way to know if successful)
                logger.debug(f"Peer connection attempt from {self.connections.get(websocket, 'unknown')} to {target_id}")
                
            elif message_type == MessageType.HEARTBEAT:
                # Client heartbeat - just record activity
                if websocket in self.connections:
                    peer_id = self.connections[websocket]
                    if peer_id in self.peers:
                        self.peers[peer_id].last_seen = time.time()
                        
            else:
                await self._send_error(websocket, f"Unknown message type: {message_type}")
                
        except json.JSONDecodeError:
            await self._send_error(websocket, "Invalid JSON message")
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await self._send_error(websocket, f"Error processing message: {str(e)}")
            
    async def _send_peer_list(self, websocket: WebSocketServerProtocol, filters: Dict[str, Any] = None):
        """
        Send peer list to a client.
        
        Args:
            websocket: WebSocket connection
            filters: Optional filters for the peer list
        """
        filters = filters or {}
        
        # Filter peers
        filtered_peers = {}
        for peer_id, peer_info in self.peers.items():
            # Skip local peer if requested
            if filters.get("exclude_self", False) and peer_id == self.local_peer_info.peer_id:
                continue
                
            # Filter by role
            if "role" in filters and peer_info.role != filters["role"]:
                continue
                
            # Filter by capabilities
            required_capabilities = filters.get("capabilities", [])
            if required_capabilities and not all(cap in peer_info.capabilities for cap in required_capabilities):
                continue
                
            # Add to filtered peers
            filtered_peers[peer_id] = peer_info.to_dict()
            
        # Send peer list
        await websocket.send(json.dumps({
            "type": MessageType.PEER_LIST,
            "peers": filtered_peers,
            "timestamp": time.time()
        }))
        
    async def _send_error(self, websocket: WebSocketServerProtocol, error_message: str):
        """
        Send an error message to a client.
        
        Args:
            websocket: WebSocket connection
            error_message: Error message
        """
        await websocket.send(json.dumps({
            "type": MessageType.ERROR,
            "error": error_message,
            "timestamp": time.time()
        }))
        
    async def _cleanup_peers(self):
        """Periodic task to clean up stale peers."""
        try:
            while self.running:
                now = time.time()
                stale_peers = []
                
                # Find stale peers
                for peer_id, peer_info in self.peers.items():
                    if now - peer_info.last_seen > self.peer_ttl:
                        # Skip local peer
                        if peer_id != self.local_peer_info.peer_id:
                            stale_peers.append(peer_id)
                            
                # Remove stale peers
                for peer_id in stale_peers:
                    del self.peers[peer_id]
                    logger.debug(f"Removed stale peer: {peer_id}")
                    
                # Enforce maximum peer limit if exceeded
                if len(self.peers) > self.max_peers:
                    # Sort peers by last seen time (oldest first)
                    sorted_peers = sorted(
                        [(pid, p) for pid, p in self.peers.items() if pid != self.local_peer_info.peer_id],
                        key=lambda x: x[1].last_seen
                    )
                    
                    # Remove oldest peers until we're under the limit
                    peers_to_remove = sorted_peers[:len(self.peers) - self.max_peers]
                    for peer_id, _ in peers_to_remove:
                        del self.peers[peer_id]
                        logger.debug(f"Removed excess peer: {peer_id}")
                        
                # Wait for next cleanup
                await anyio.sleep(60)  # Check every minute
                
        except anyio.CancelledError:
            # Task cancelled - that's ok
            pass
            
        except Exception as e:
            logger.error(f"Error in peer cleanup task: {e}")
            
    async def _send_heartbeats(self):
        """Periodic task to send heartbeats to all connected clients."""
        try:
            while self.running:
                # Update local peer's last_seen time
                self.local_peer_info.last_seen = time.time()
                
                # Prepare heartbeat message
                heartbeat = json.dumps({
                    "type": MessageType.HEARTBEAT,
                    "timestamp": time.time()
                })
                
                # Send to all connections (use a copy of the list to prevent race conditions)
                # If a connection is removed during iteration, we won't encounter issues
                connections_snapshot = list(self.connections.keys())
                for websocket in connections_snapshot:
                    try:
                        # Check if the connection is still in the dictionary
                        # It might have been removed by another task
                        if websocket in self.connections:
                            await websocket.send(heartbeat)
                    except websockets.exceptions.ConnectionClosed:
                        # Connection closed, remove from dictionary if still there
                        if websocket in self.connections:
                            peer_id = self.connections[websocket]
                            del self.connections[websocket]
                            logger.debug(f"Removed closed connection to {peer_id} during heartbeat")
                    except Exception as e:
                        logger.debug(f"Error sending heartbeat: {e}")
                        # Don't remove connection here - it might be temporary error
                        
                # Wait for next heartbeat
                await anyio.sleep(self.heartbeat_interval)
                
        except anyio.CancelledError:
            # Task cancelled - that's ok
            pass
            
        except Exception as e:
            logger.error(f"Error in heartbeat task: {e}")

class PeerWebSocketClient:
    """
    WebSocket client for peer discovery.
    
    This client:
    1. Connects to peer discovery servers
    2. Advertises local peer information
    3. Discovers and connects to remote peers
    """
    
    def __init__(self, 
                local_peer_info: PeerInfo,
                on_peer_discovered: Callable[[PeerInfo], None] = None,
                auto_connect: bool = True,
                reconnect_interval: int = 30,
                max_reconnect_attempts: int = 5):
        """
        Initialize the peer WebSocket client.
        
        Args:
            local_peer_info: Information about the local peer
            on_peer_discovered: Callback function when a new peer is discovered
            auto_connect: Whether to automatically connect to discovered peers
            reconnect_interval: Reconnect interval in seconds
            max_reconnect_attempts: Maximum number of reconnect attempts
        """
        self.local_peer_info = local_peer_info
        self.on_peer_discovered = on_peer_discovered
        self.auto_connect = auto_connect
        self.reconnect_interval = reconnect_interval
        self.max_reconnect_attempts = max_reconnect_attempts
        
        self.peers: Dict[str, PeerInfo] = {}
        self.connections: Dict[str, WebSocketClientProtocol] = {}
        self.discovery_servers: Dict[str, Dict[str, Any]] = {}
        self.running = False
        self.tasks = set()
        
        # Add local peer to known peers
        self.peers[self.local_peer_info.peer_id] = self.local_peer_info
        
    async def start(self):
        """Start the peer discovery client."""
        if not WEBSOCKET_AVAILABLE:
            raise ImportError("WebSockets library not available")
            
        self.running = True
        logger.info("Peer WebSocket client started")
        
    async def stop(self):
        """Stop the peer discovery client."""
        if not self.running:
            logger.debug("Client already stopped, nothing to do")
            return
            
        self.running = False
        
        # Cancel all tasks with careful error handling
        for task in list(self.tasks):
            try:
                task.cancel()
                # Wait for cancellation to complete with timeout
                try:
                    await anyio.wait_for(anyio.gather(task, return_exceptions=True), timeout=2.0)
                except (anyio.TimeoutError, anyio.CancelledError):
                    pass
            except Exception as e:
                logger.error(f"Error cancelling task: {e}")
            
        self.tasks.clear()
        
        # Close all connections with proper error handling
        for server_url, conn in list(self.connections.items()):
            try:
                await conn.close(code=1001, reason="Client shutting down")
            except Exception as e:
                logger.debug(f"Error closing connection to {server_url}: {e}")
                
        # Clear all dictionaries
        self.connections.clear()
        self.discovery_servers.clear()
        
        # Keep peer information for potential restart
        # but mark local state as inactive
        if self.local_peer_info:
            self.local_peer_info.last_seen = time.time()
        
        logger.info("Peer WebSocket client stopped")
        
    async def connect_to_discovery_server(self, url: str) -> bool:
        """
        Connect to a peer discovery server.
        
        Args:
            url: WebSocket URL of the discovery server
            
        Returns:
            Success status
        """
        if not self.running:
            raise RuntimeError("Client not started")
            
        try:
            # Create new connection task
            task = anyio.create_task(self._maintain_server_connection(url))
            self.tasks.add(task)
            task.add_done_callback(self.tasks.discard)
            
            # Add to discovery servers
            self.discovery_servers[url] = {
                "url": url,
                "connected": True,
                "last_connected": time.time(),
                "reconnect_attempts": 0
            }
            
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to discovery server {url}: {e}")
            return False
            
    async def _maintain_server_connection(self, url: str):
        """
        Maintain connection to a discovery server.
        
        This task handles:
        - Initial connection
        - Heartbeats
        - Reconnection on failure
        - Message processing
        
        Args:
            url: WebSocket URL of the discovery server
        """
        reconnect_attempts = 0
        connection_successful = False
        
        while self.running and reconnect_attempts < self.max_reconnect_attempts:
            try:
                # Connect to server with timeout
                connection_task = websockets.connect(url)
                try:
                    websocket = await anyio.wait_for(connection_task, timeout=10.0)
                    self.connections[url] = websocket
                    connection_successful = True
                    
                    # Reset reconnect counter on successful connection
                    if reconnect_attempts > 0:
                        logger.info(f"Reconnected to {url} after {reconnect_attempts} attempts")
                        reconnect_attempts = 0
                        
                    # Update server status
                    self.discovery_servers[url]["connected"] = True
                    self.discovery_servers[url]["last_connected"] = time.time()
                    self.discovery_servers[url]["reconnect_attempts"] = reconnect_attempts
                    
                    logger.info(f"Connected to discovery server: {url}")
                    
                    # Send local peer info
                    try:
                        await anyio.wait_for(
                            websocket.send(json.dumps({
                                "type": MessageType.PEER_INFO,
                                "peer": self.local_peer_info.to_dict(),
                                "timestamp": time.time()
                            })), 
                            timeout=5.0
                        )
                    except anyio.TimeoutError:
                        logger.warning(f"Timeout sending peer info to {url}")
                        raise ConnectionError("Timeout sending initial peer info")
                    
                    # Request peer list
                    try:
                        await anyio.wait_for(
                            websocket.send(json.dumps({
                                "type": MessageType.PEER_REQUEST,
                                "filter": {"exclude_self": True},
                                "timestamp": time.time()
                            })),
                            timeout=5.0
                        )
                    except anyio.TimeoutError:
                        logger.warning(f"Timeout requesting peer list from {url}")
                        raise ConnectionError("Timeout requesting peer list")
                    
                    # Process messages
                    while self.running:
                        # Use try/except to properly handle timeouts and errors
                        try:
                            # Set up heartbeat
                            heartbeat_task = anyio.create_task(self._send_heartbeat(websocket))
                            
                            # Wait for message or heartbeat completion
                            message_task = anyio.create_task(websocket.recv())
                            done, pending = await anyio.wait(
                                [message_task, heartbeat_task],
                                return_when=anyio.FIRST_COMPLETED,
                                timeout=60.0
                            )
                            
                            # If timeout occurred, no tasks completed
                            if not done:
                                # Cancel pending tasks
                                for task in pending:
                                    task.cancel()
                                    
                                # Send a ping to check if connection is still alive
                                try:
                                    pong = await anyio.wait_for(websocket.ping(), timeout=5.0)
                                    if not pong:
                                        raise ConnectionError("No ping response")
                                except Exception:
                                    raise ConnectionError("Failed to ping server")
                                    
                                # Continue to next iteration
                                continue
                            
                            # Cancel pending tasks
                            for task in pending:
                                task.cancel()
                                
                            # Process completed tasks
                            for task in done:
                                if task is message_task:
                                    # Process message
                                    message = task.result()
                                    await self._process_message(message)
                                # If heartbeat completed, it's already done
                                
                        except anyio.TimeoutError:
                            # Check if connection is still valid with ping
                            try:
                                pong = await anyio.wait_for(websocket.ping(), timeout=5.0)
                                if not pong:
                                    raise ConnectionError("No ping response")
                            except Exception:
                                raise ConnectionError("Connection appears dead")
                
                except anyio.TimeoutError:
                    logger.warning(f"Timeout connecting to {url}")
                    raise ConnectionError("Connection timeout")
                    
            except websockets.exceptions.ConnectionClosed as e:
                logger.info(f"Connection closed to {url}: {e}")
                if url in self.connections:
                    del self.connections[url]
                    
                self.discovery_servers[url]["connected"] = False
                # Connection was established before but now closed
                connection_successful = False
                
            except Exception as e:
                logger.error(f"Error in server connection {url}: {e}")
                if url in self.connections:
                    del self.connections[url]
                    
                self.discovery_servers[url]["connected"] = False
                connection_successful = False
                
            # Only increment attempts if we never successfully connected
            # or if we previously connected but failed to reconnect
            if not connection_successful:
                reconnect_attempts += 1
                self.discovery_servers[url]["reconnect_attempts"] = reconnect_attempts
                
                if reconnect_attempts < self.max_reconnect_attempts:
                    # Wait before reconnecting (with exponential backoff)
                    backoff = min(60, self.reconnect_interval * (2 ** (reconnect_attempts - 1)))
                    logger.info(f"Reconnecting to {url} in {backoff}s (attempt {reconnect_attempts}/{self.max_reconnect_attempts})")
                    await anyio.sleep(backoff)
                else:
                    # Max reconnect attempts reached
                    logger.warning(f"Gave up reconnecting to {url} after {reconnect_attempts} attempts")
                    self.discovery_servers[url]["connected"] = False
            else:
                # If we had a successful connection but it failed, start over with reconnect attempts
                reconnect_attempts = 1
                self.discovery_servers[url]["reconnect_attempts"] = reconnect_attempts
                
                # Use a shorter delay for the first reconnect attempt after a successful connection
                logger.info(f"Reconnecting to {url} in {self.reconnect_interval}s (attempt 1/{self.max_reconnect_attempts})")
                await anyio.sleep(self.reconnect_interval)
        
    async def _send_heartbeat(self, websocket: WebSocketClientProtocol):
        """
        Send a heartbeat to a server.
        
        Args:
            websocket: WebSocket connection
        """
        try:
            # Wait before sending heartbeat
            await anyio.sleep(30)  # Send heartbeat every 30 seconds
            
            # Send heartbeat with timeout
            await anyio.wait_for(
                websocket.send(json.dumps({
                    "type": MessageType.HEARTBEAT,
                    "timestamp": time.time()
                })),
                timeout=5.0  # 5 second timeout for sending heartbeat
            )
            
            return True
        except anyio.TimeoutError:
            # Log timeout but don't raise - let caller handle this
            logger.warning("Timeout sending heartbeat")
            return False
        except websockets.exceptions.ConnectionClosed:
            # Connection is already closed, heartbeat can't be sent
            logger.debug("Connection closed, can't send heartbeat")
            return False
        except Exception as e:
            # Unexpected error
            logger.error(f"Error sending heartbeat: {e}")
            return False
        
    async def _process_message(self, message: str):
        """
        Process a message from a server.
        
        Args:
            message: Message content
        """
        try:
            data = json.loads(message)
            message_type = data.get("type")
            
            if message_type == MessageType.PEER_INFO:
                # Update peer information
                peer_data = data.get("peer", {})
                peer_id = peer_data.get("peer_id")
                
                if not peer_id or peer_id == self.local_peer_info.peer_id:
                    # Skip local peer
                    return
                    
                # Update or create peer info
                is_new = peer_id not in self.peers
                if peer_id in self.peers:
                    self.peers[peer_id].update_from_dict(peer_data)
                else:
                    self.peers[peer_id] = PeerInfo.from_dict(peer_data)
                    
                # Call discovery callback for new peers
                if is_new and self.on_peer_discovered:
                    self.on_peer_discovered(self.peers[peer_id])
                    
                logger.debug(f"Received peer info: {peer_id}")
                
                # Auto-connect if enabled
                if is_new and self.auto_connect:
                    # Implement actual peer connection via IPFS swarm connect
                    peer_info = self.peers[peer_id]
                    logger.debug(f"Auto-connecting to peer: {peer_id}")
                    
                    # Connect to multiaddresses if available
                    if peer_info.multiaddrs:
                        for addr in peer_info.multiaddrs:
                            try:
                                # Check if the multiaddr includes peer ID
                                if '/p2p/' in addr or '/ipfs/' in addr:
                                    # Already has peer ID included
                                    # Attempt connection in a new task to not block processing
                                    task = anyio.create_task(self._attempt_ipfs_connection(addr))
                                    self.tasks.add(task)
                                    task.add_done_callback(self.tasks.discard)
                                else:
                                    # Need to append peer ID
                                    full_addr = f"{addr}/p2p/{peer_id}"
                                    task = anyio.create_task(self._attempt_ipfs_connection(full_addr))
                                    self.tasks.add(task)
                                    task.add_done_callback(self.tasks.discard)
                            except Exception as e:
                                logger.error(f"Error starting connection task to {addr}: {e}")
                    else:
                        logger.warning(f"No multiaddresses available for peer {peer_id}")
                    
            elif message_type == MessageType.PEER_LIST:
                # Process received peer list
                peer_list = data.get("peers", {})
                
                for peer_id, peer_data in peer_list.items():
                    # Skip local peer
                    if peer_id == self.local_peer_info.peer_id:
                        continue
                        
                    # Update or create peer info
                    is_new = peer_id not in self.peers
                    if peer_id in self.peers:
                        self.peers[peer_id].update_from_dict(peer_data)
                    else:
                        self.peers[peer_id] = PeerInfo.from_dict(peer_data)
                        
                    # Call discovery callback for new peers
                    if is_new and self.on_peer_discovered:
                        self.on_peer_discovered(self.peers[peer_id])
                        
                    # Auto-connect if enabled
                    if is_new and self.auto_connect:
                        # Implement actual peer connection for peers from list
                        peer_info = self.peers[peer_id]
                        logger.debug(f"Auto-connecting to peer from list: {peer_id}")
                        
                        # Connect to multiaddresses if available
                        if peer_info.multiaddrs:
                            for addr in peer_info.multiaddrs:
                                try:
                                    # Check if the multiaddr includes peer ID
                                    if '/p2p/' in addr or '/ipfs/' in addr:
                                        # Already has peer ID included
                                        # Attempt connection in a new task to not block processing
                                        task = anyio.create_task(self._attempt_ipfs_connection(addr))
                                        self.tasks.add(task)
                                        task.add_done_callback(self.tasks.discard)
                                    else:
                                        # Need to append peer ID
                                        full_addr = f"{addr}/p2p/{peer_id}"
                                        task = anyio.create_task(self._attempt_ipfs_connection(full_addr))
                                        self.tasks.add(task)
                                        task.add_done_callback(self.tasks.discard)
                                except Exception as e:
                                    logger.error(f"Error starting connection task to {addr}: {e}")
                        else:
                            logger.warning(f"No multiaddresses available for peer {peer_id}")
                        
                logger.debug(f"Received peer list with {len(peer_list)} peers")
                
            elif message_type == MessageType.HEARTBEAT:
                # Server heartbeat - just ignore
                pass
                
            elif message_type == MessageType.ERROR:
                # Server error
                error = data.get("error", "Unknown error")
                logger.warning(f"Received error from server: {error}")
                
        except json.JSONDecodeError:
            logger.warning("Received invalid JSON message")
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def get_discovered_peers(self, 
                           filter_role: Optional[str] = None, 
                           filter_capabilities: Optional[List[str]] = None) -> List[PeerInfo]:
        """
        Get list of discovered peers with optional filtering.
        
        Args:
            filter_role: Filter by peer role
            filter_capabilities: Filter by required capabilities
            
        Returns:
            List of peer info objects
        """
        result = []
        
        for peer_id, peer_info in self.peers.items():
            # Skip local peer
            if peer_id == self.local_peer_info.peer_id:
                continue
                
            # Filter by role
            if filter_role and peer_info.role != filter_role:
                continue
                
            # Filter by capabilities
            if filter_capabilities and not all(cap in peer_info.capabilities for cap in filter_capabilities):
                continue
                
            result.append(peer_info)
            
        return result
        
    def get_peer_by_id(self, peer_id: str) -> Optional[PeerInfo]:
        """Get peer info by ID."""
        return self.peers.get(peer_id)
        
    async def _attempt_ipfs_connection(self, multiaddr: str) -> bool:
        """
        Attempt to connect to a peer via the IPFS swarm.
        
        Args:
            multiaddr: Multiaddress to connect to
            
        Returns:
            Success status
        """
        logger.debug(f"Attempting IPFS connection to {multiaddr}")
        
        try:
            # Check if we have access to an IPFS instance
            # This can be customized based on how IPFS access is provided to the client
            import subprocess
            import shutil
            
            # Check if ipfs command is available
            ipfs_path = shutil.which("ipfs")
            if ipfs_path:
                # Use subprocess for the connection
                cmd = [ipfs_path, "swarm", "connect", multiaddr]
                process = await anyio.create_subprocess_exec(
                    *cmd,
                    stdout=anyio.subprocess.PIPE,
                    stderr=anyio.subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
                success = process.returncode == 0
                
                if success:
                    output = stdout.decode().strip()
                    logger.info(f"Successfully connected to peer: {output}")
                    
                    # Extract peer ID from output or multiaddr
                    if '/p2p/' in multiaddr:
                        peer_id = multiaddr.split('/p2p/')[1].split('/')[0]
                    elif '/ipfs/' in multiaddr:
                        peer_id = multiaddr.split('/ipfs/')[1].split('/')[0]
                    else:
                        peer_id = "unknown"
                        
                    # Update peer info if available
                    if peer_id in self.peers:
                        self.peers[peer_id].record_connection_attempt(True)
                    
                    return True
                else:
                    error = stderr.decode().strip()
                    logger.warning(f"Failed to connect to peer: {error}")
                    
                    # Extract peer ID from multiaddr to update connection stats
                    if '/p2p/' in multiaddr:
                        peer_id = multiaddr.split('/p2p/')[1].split('/')[0]
                    elif '/ipfs/' in multiaddr:
                        peer_id = multiaddr.split('/ipfs/')[1].split('/')[0]
                    else:
                        peer_id = "unknown"
                        
                    # Update peer info if available
                    if peer_id in self.peers:
                        self.peers[peer_id].record_connection_attempt(False)
                        
                    return False
            else:
                logger.warning("IPFS command not found, can't connect to peer")
                return False
                
        except Exception as e:
            logger.error(f"Error attempting IPFS connection to {multiaddr}: {e}")
            return False

# Function to integrate with FastAPI
def register_peer_websocket(app: FastAPI, 
                           local_peer_info: PeerInfo,
                           path: str = "/api/v0/peer/ws"):
    """
    Register peer WebSocket endpoint with FastAPI.
    
    Args:
        app: FastAPI application
        local_peer_info: Local peer information
        path: WebSocket endpoint path
        
    Returns:
        Success status
    """
    if not FASTAPI_AVAILABLE:
        logger.warning("FastAPI not available. Peer WebSocket API not registered.")
        return False
        
    try:
        # Create server instance
        server = PeerWebSocketServer(local_peer_info)
        
        # Store in app state
        app.state.peer_websocket_server = server
        
        # Define WebSocket endpoint
        @app.websocket(path)
        async def peer_websocket(websocket: WebSocket):
            peer_id = None
            connection_added = False
            connection_start_time = time.time()
            
            try:
                # Accept connection with proper error handling and timeout
                try:
                    # Accept the connection
                    await anyio.wait_for(
                        websocket.accept(),
                        timeout=5.0
                    )
                except anyio.TimeoutError:
                    logger.error(f"Timeout accepting WebSocket connection")
                    return
                except Exception as e:
                    logger.error(f"Error accepting WebSocket connection: {e}")
                    return
                
                # Send local peer info with timeout
                try:
                    await anyio.wait_for(
                        websocket.send_json({
                            "type": MessageType.PEER_INFO,
                            "peer": local_peer_info.to_dict(),
                            "timestamp": time.time()
                        }),
                        timeout=5.0
                    )
                except anyio.TimeoutError:
                    logger.error(f"Timeout sending initial peer info")
                    await websocket.close(code=1011, reason="Timeout sending initial info")
                    return
                except Exception as e:
                    logger.error(f"Error sending initial peer info: {e}")
                    await websocket.close(code=1011, reason="Failed to send initial info")
                    return
                
                # Successfully established connection - log info
                client_info = f"{websocket.client.host}:{websocket.client.port}" if hasattr(websocket, 'client') else "unknown"
                logger.info(f"New WebSocket connection established from {client_info}")
                
                # Process messages with proper timeout handling
                connection_healthy = True
                last_activity_time = time.time()
                ping_interval = 30  # Send ping every 30 seconds of inactivity
                
                while connection_healthy:
                    try:
                        # Calculate time until next ping
                        time_since_activity = time.time() - last_activity_time
                        timeout = max(1.0, ping_interval - time_since_activity)
                        
                        # Use shorter timeout as we get closer to ping time
                        message = await anyio.wait_for(
                            websocket.receive_text(),
                            timeout=timeout
                        )
                        
                        # Update activity time
                        last_activity_time = time.time()
                        
                        # Track peer ID from connections dictionary
                        if websocket in server.connections:
                            peer_id = server.connections[websocket]
                            connection_added = True
                        
                        # Process message
                        await server._process_message(websocket, message)
                        
                    except anyio.TimeoutError:
                        # No message received within timeout - check connection health
                        time_since_activity = time.time() - last_activity_time
                        
                        # If it's been too long since any activity, send a ping
                        if time_since_activity >= ping_interval:
                            try:
                                # First check if still connected
                                if (hasattr(websocket, 'client_state') and 
                                    websocket.client_state == WebSocketState.DISCONNECTED):
                                    logger.debug("WebSocket connection already disconnected")
                                    connection_healthy = False
                                    break
                                
                                # Send heartbeat/ping
                                ping_start = time.time()
                                await anyio.wait_for(
                                    websocket.send_json({
                                        "type": MessageType.HEARTBEAT,
                                        "timestamp": time.time()
                                    }),
                                    timeout=5.0
                                )
                                
                                # Update activity time after successful ping
                                last_activity_time = time.time()
                                logger.debug(f"Sent heartbeat ping, took {(time.time()-ping_start)*1000:.1f}ms")
                                
                            except Exception as e:
                                # Any error during ping means connection is unhealthy
                                logger.debug(f"Connection appears dead during heartbeat: {e}")
                                connection_healthy = False
                                break
                    
                    except WebSocketDisconnect:
                        logger.debug(f"WebSocket receive loop disconnected normally")
                        connection_healthy = False
                        break
                        
                    except Exception as e:
                        logger.error(f"Error processing WebSocket message: {e}")
                        # Only break on serious errors
                        if "connection" in str(e).lower() or "closed" in str(e).lower():
                            connection_healthy = False
                            break
                
            except WebSocketDisconnect:
                logger.debug(f"WebSocket disconnected normally")
                
            except Exception as e:
                logger.error(f"Error in peer WebSocket: {e}")
                
            finally:
                # Calculate connection duration
                connection_duration = time.time() - connection_start_time
                
                # Always clean up the connection
                if websocket in server.connections:
                    peer_id = server.connections[websocket]
                    del server.connections[websocket]
                    logger.info(f"Client disconnected: {peer_id}, connection duration: {connection_duration:.1f}s")
                else:
                    logger.info(f"Client disconnected (unknown peer), connection duration: {connection_duration:.1f}s")
                
                # Ensure socket is closed
                try:
                    if hasattr(websocket, 'client_state') and websocket.client_state != WebSocketState.DISCONNECTED:
                        await anyio.wait_for(
                            websocket.close(code=1000, reason="Connection complete"),
                            timeout=2.0
                        )
                except Exception as e:
                    logger.debug(f"Error closing WebSocket: {e}")
                
        # Add startup event to start server
        @app.on_event("startup")
        async def start_peer_websocket_server():
            logger.info("Starting peer WebSocket server...")
            server.running = True
            server.cleanup_task = anyio.create_task(server._cleanup_peers())
            server.heartbeat_task = anyio.create_task(server._send_heartbeats())
            logger.info("Peer WebSocket server started")
            
        # Add shutdown event to stop server
        @app.on_event("shutdown")
        async def stop_peer_websocket_server():
            logger.info("Stopping peer WebSocket server...")
            server.running = False
            
            # Cancel background tasks
            if server.cleanup_task:
                try:
                    server.cleanup_task.cancel()
                    # Wait for cancellation to complete
                    try:
                        await anyio.wait_for(server.cleanup_task, timeout=2.0)
                    except (anyio.TimeoutError, anyio.CancelledError):
                        pass
                except Exception as e:
                    logger.error(f"Error canceling cleanup task: {e}")
                
            if server.heartbeat_task:
                try:
                    server.heartbeat_task.cancel()
                    # Wait for cancellation to complete
                    try:
                        await anyio.wait_for(server.heartbeat_task, timeout=2.0)
                    except (anyio.TimeoutError, anyio.CancelledError):
                        pass
                except Exception as e:
                    logger.error(f"Error canceling heartbeat task: {e}")
                
            # Close all connections
            for websocket in list(server.connections.keys()):
                try:
                    await websocket.close(code=1001, reason="Server shutting down")
                except Exception as e:
                    logger.error(f"Error closing WebSocket connection: {e}")
            
            # Clear connections and peers
            server.connections.clear()
            
            logger.info("Peer WebSocket server stopped")
            
        logger.info(f"Peer WebSocket endpoint registered at {path}")
        return True
        
    except Exception as e:
        logger.error(f"Error registering peer WebSocket: {e}")
        return False

# Integration with IPFS Kit
def create_peer_info_from_ipfs_kit(ipfs_kit_instance, role: str = None, capabilities: List[str] = None) -> PeerInfo:
    """
    Create a PeerInfo object from an IPFS Kit instance.
    
    Args:
        ipfs_kit_instance: IPFS Kit instance
        role: Override default role
        capabilities: Override default capabilities
        
    Returns:
        PeerInfo object
    """
    try:
        # Get peer ID
        id_info = ipfs_kit_instance.ipfs_id()
        if not id_info.get("success", False):
            raise ValueError(f"Failed to get IPFS ID: {id_info.get('error', 'Unknown error')}")
            
        peer_id = id_info.get("ID", "")
        if not peer_id:
            raise ValueError("Empty IPFS peer ID")
            
        # Get addresses
        multiaddrs = id_info.get("Addresses", [])
        
        # Determine role
        if role is None:
            # Try to get role from ipfs_kit
            if hasattr(ipfs_kit_instance, "role"):
                role = ipfs_kit_instance.role
            else:
                # Default to leecher
                role = PeerRole.LEECHER
                
        # Determine capabilities
        if capabilities is None:
            capabilities = []
            
            # Check for common capabilities
            if hasattr(ipfs_kit_instance, "check_daemon_status"):
                daemon_status = ipfs_kit_instance.check_daemon_status("ipfs")
                if daemon_status.get("running", False):
                    capabilities.append("ipfs")
                    
                cluster_status = ipfs_kit_instance.check_daemon_status("ipfs_cluster_service")
                if cluster_status.get("running", False):
                    capabilities.append("ipfs_cluster")
                    
            # Add tiered cache capability if available
            if hasattr(ipfs_kit_instance, "get_tiered_cache_status"):
                cache_status = ipfs_kit_instance.get_tiered_cache_status()
                if cache_status.get("enabled", False):
                    capabilities.append("tiered_cache")
                    
            # Add WAL capability if available
            if hasattr(ipfs_kit_instance, "check_wal_status"):
                wal_status = ipfs_kit_instance.check_wal_status()
                if wal_status.get("enabled", False):
                    capabilities.append("wal")
                    
        # Create PeerInfo object
        return PeerInfo(
            peer_id=peer_id,
            multiaddrs=multiaddrs,
            role=role,
            capabilities=capabilities,
            resources={},  # Could add system resource info here
            metadata={}    # Could add version info here
        )
        
    except Exception as e:
        logger.error(f"Error creating peer info from IPFS Kit: {e}")
        # Return minimal peer info
        return PeerInfo(
            peer_id="unknown",
            multiaddrs=[],
            role=role or PeerRole.LEECHER,
            capabilities=capabilities or []
        )

# Example client code
WEBSOCKET_CLIENT_EXAMPLE = """
// Example client-side JavaScript for WebSocket peer discovery

class PeerDiscoveryClient {
  constructor(url = "ws://localhost:8000/api/v0/peer/ws") {
    this.url = url;
    this.socket = null;
    this.connected = false;
    this.peers = new Map();
    this.onPeerDiscovered = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
  }

  connect() {
    return new Promise((resolve, reject) => {
      try {
        this.socket = new WebSocket(this.url);

        this.socket.onopen = () => {
          console.log("WebSocket connected");
          this.connected = true;
          this.reconnectAttempts = 0;

          // Request peer list
          this.requestPeers();
          resolve();
        };

        this.socket.onmessage = (event) => {
          const message = JSON.parse(event.data);
          this.handleMessage(message);
        };

        this.socket.onerror = (error) => {
          console.error("WebSocket error:", error);
          reject(error);
        };

        this.socket.onclose = (event) => {
          console.log(`WebSocket closed: ${event.code} - ${event.reason}`);
          this.connected = false;
          
          // Try to reconnect
          if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = Math.pow(2, this.reconnectAttempts) * 1000; // Exponential backoff
            console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
            
            setTimeout(() => {
              this.connect().catch(err => console.error("Reconnect failed:", err));
            }, delay);
          }
        };
      } catch (error) {
        reject(error);
      }
    });
  }

  handleMessage(message) {
    const { type } = message;

    switch (type) {
      case "peer_info":
        this.handlePeerInfo(message.peer);
        break;
      case "peer_list":
        this.handlePeerList(message.peers);
        break;
      case "error":
        console.error(`Server error: ${message.error}`);
        break;
      case "heartbeat":
        // Send heartbeat response
        this.sendHeartbeat();
        break;
      default:
        console.warn(`Unknown message type: ${type}`);
    }
  }

  handlePeerInfo(peer) {
    const { peer_id } = peer;
    if (!peer_id) return;

    // Add or update peer
    const isNew = !this.peers.has(peer_id);
    this.peers.set(peer_id, peer);

    // Notify about new peer
    if (isNew && this.onPeerDiscovered) {
      this.onPeerDiscovered(peer);
    }
  }

  handlePeerList(peers) {
    // Process all peers in the list
    for (const [peer_id, peer] of Object.entries(peers)) {
      this.handlePeerInfo(peer);
    }
  }

  requestPeers(filters = {}) {
    if (!this.connected) return;

    this.socket.send(JSON.stringify({
      type: "peer_request",
      filter: filters,
      timestamp: Date.now() / 1000
    }));
  }

  sendHeartbeat() {
    if (!this.connected) return;

    this.socket.send(JSON.stringify({
      type: "heartbeat",
      timestamp: Date.now() / 1000
    }));
  }

  sendPeerInfo(peerInfo) {
    if (!this.connected) return;

    this.socket.send(JSON.stringify({
      type: "peer_info",
      peer: peerInfo,
      timestamp: Date.now() / 1000
    }));
  }

  disconnect() {
    if (this.socket) {
      this.socket.close();
      this.connected = false;
    }
  }

  // Get all discovered peers
  getAllPeers() {
    return Array.from(this.peers.values());
  }

  // Get peers with specific role
  getPeersByRole(role) {
    return this.getAllPeers().filter(peer => peer.role === role);
  }

  // Get peers with specific capabilities
  getPeersByCapabilities(capabilities) {
    return this.getAllPeers().filter(peer => {
      return capabilities.every(cap => peer.capabilities.includes(cap));
    });
  }
}

// Usage example:
// const client = new PeerDiscoveryClient();
// client.onPeerDiscovered = (peer) => {
//   console.log(`Discovered new peer: ${peer.peer_id}`);
// };
// client.connect().then(() => {
//   console.log("Connected to peer discovery server");
// });
"""

if __name__ == "__main__":
    print("IPFS Kit WebSocket peer discovery module")