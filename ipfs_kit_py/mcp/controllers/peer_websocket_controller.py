"""
Peer WebSocket Controller for the MCP server.

This controller handles WebSocket peer discovery, allowing peers to find each other
through WebSocket connections even in environments with NAT or firewalls.
"""

import logging
import time
import uuid
from typing import Dict, List, Any, Optional

# Import FastAPI components
from fastapi import APIRouter
from pydantic import BaseModel, Field

# Import peer WebSocket components (first try anyio version, then fall back to regular)
try:
    from ipfs_kit_py.peer_websocket_anyio import (
        PeerInfo,
        PeerWebSocketServer,
        PeerWebSocketClient,
        register_peer_websocket,
        create_peer_info_from_ipfs_kit,
        PeerRole,
        MessageType,
        WEBSOCKET_AVAILABLE)

    HAS_PEER_WEBSOCKET = True
except ImportError:
    try:
        from ipfs_kit_py.peer_websocket import (
            PeerInfo,
            PeerWebSocketServer,
            PeerWebSocketClient,
            # create_peer_info_from_ipfs_kit, # Removed F401
            # MessageType, # Removed F401
            # WEBSOCKET_AVAILABLE, # Removed F401
        )

        #         from ipfs_kit_py.peer_websocket import WEBSOCKET_AVAILABLE  # Import separately if needed
        # Unused import commented out

        HAS_PEER_WEBSOCKET = True
    except ImportError:
        HAS_PEER_WEBSOCKET = False

# Configure logger
logger = logging.getLogger(__name__)


# Define Pydantic models for requests and responses
class PeerWebSocketResponse(BaseModel):
    """Base response model for peer WebSocket operations."""
    success: bool = Field(..., description="Whether the operation was successful")
    operation_id: Optional[str] = Field(None, description="Unique identifier for this operation")
    timestamp: float = Field(..., description="Operation timestamp")


class StartServerRequest(BaseModel):
    """Request model for starting a peer WebSocket server."""
    host: str = Field("0.0.0.0", description="Host address to bind to")
    port: int = Field(8765, description="Port to listen on")
    max_peers: int = Field(100, description="Maximum number of peers to track")
    heartbeat_interval: int = Field(30, description="Heartbeat interval in seconds")
    peer_ttl: int = Field(300, description="Time-to-live for peer information in seconds")
    role: Optional[str] = Field(None, description="Override default peer role")
    capabilities: Optional[List[str]] = Field(
        None, description="Override default peer capabilities"
    )


class StartServerResponse(PeerWebSocketResponse):
    """Response model for starting a peer WebSocket server."""
    server_url: Optional[str] = Field(None, description="WebSocket URL of the server")
    peer_info: Optional[Dict[str, Any]] = Field(None, description="Local peer information")


class ConnectToServerRequest(BaseModel):
    """Request model for connecting to a peer WebSocket server."""
    server_url: str = Field(..., description="WebSocket URL of the peer discovery server")
    auto_connect: bool = Field(
        True, description="Whether to automatically connect to discovered peers"
    )
    reconnect_interval: int = Field(30, description="Reconnect interval in seconds")
    max_reconnect_attempts: int = Field(5, description="Maximum number of reconnect attempts")


class ConnectToServerResponse(PeerWebSocketResponse):
    """Response model for connecting to a peer WebSocket server."""
    connected: bool = Field(..., description="Whether connection was successful")
    server_url: str = Field(..., description="WebSocket URL of the server")


class DiscoveredPeersResponse(PeerWebSocketResponse):
    """Response model for listing discovered peers."""
    peers: List[Dict[str, Any]] = Field(default=[], description="List of discovered peers")
    count: int = Field(0, description="Number of discovered peers")


class PeerWebSocketController:
    """
    Controller for peer WebSocket discovery.

    Handles HTTP requests related to peer discovery via WebSockets.
    """
    def __init__(self, ipfs_model):
        """
        Initialize the peer WebSocket controller.

        Args:
            ipfs_model: IPFS model to use for operations
        """
        self.ipfs_model = ipfs_model
        self.peer_websocket_server = None
        self.peer_websocket_client = None
        self.local_peer_info = None

        logger.info("Peer WebSocket Controller initialized")

        # Check if WebSocket support is available
        if not HAS_PEER_WEBSOCKET:
            logger.warning(
                "WebSocket dependency not available. Peer WebSocket discovery will be disabled."
            )

    def register_routes(self, router: APIRouter):
        """
        Register routes with a FastAPI router.

        Args:
            router: FastAPI router to register routes with
        """
        # Check websocket support
        router.add_api_route(
            "/peer/websocket/check",
            self.check_websocket_support,
            methods=["GET"],
            response_model=PeerWebSocketResponse,
            summary="Check WebSocket support",
            description="Check if WebSocket support is available for peer discovery")

        # Start WebSocket server
        router.add_api_route(
            "/peer/websocket/server/start",
            self.start_server,
            methods=["POST"],
            response_model=StartServerResponse,
            summary="Start peer WebSocket server",
            description="Start a WebSocket server for peer discovery",
        )

        # Stop WebSocket server
        router.add_api_route(
            "/peer/websocket/server/stop",
            self.stop_server,
            methods=["POST"],
            response_model=PeerWebSocketResponse,
            summary="Stop peer WebSocket server",
            description="Stop the peer WebSocket server",
        )

        # Get server status
        router.add_api_route(
            "/peer/websocket/server/status",
            self.get_server_status,
            methods=["GET"],
            response_model=PeerWebSocketResponse,
            summary="Get server status",
            description="Get status of the peer WebSocket server",
        )

        # Connect to discovery server
        router.add_api_route(
            "/peer/websocket/client/connect",
            self.connect_to_server,
            methods=["POST"],
            response_model=ConnectToServerResponse,
            summary="Connect to peer discovery server",
            description="Connect to a WebSocket peer discovery server",
        )

        # Disconnect from server
        router.add_api_route(
            "/peer/websocket/client/disconnect",
            self.disconnect_from_server,
            methods=["POST"],
            response_model=PeerWebSocketResponse,
            summary="Disconnect from peer discovery server",
            description="Disconnect from the WebSocket peer discovery server",
        )

        # Get discovered peers
        router.add_api_route(
            "/peer/websocket/peers",
            self.get_discovered_peers,
            methods=["GET"],
            response_model=DiscoveredPeersResponse,
            summary="Get discovered peers",
            description="Get list of peers discovered via WebSocket",
        )

        # Get peer by ID
        router.add_api_route(
            "/peer/websocket/peers/{peer_id}",
            self.get_peer_by_id,
            methods=["GET"],
            response_model=PeerWebSocketResponse,
            summary="Get peer by ID",
            description="Get information about a specific peer",
        )

        # Register WebSocket route directly
        if HAS_PEER_WEBSOCKET:
            # Initialize local peer info if needed
            if self.local_peer_info is None:
                try:
                    # Create a PeerInfo object directly instead of calling create_peer_info_from_ipfs_kit
                    # This addresses the 'ipfs_py' object has no attribute 'id' error
                    peer_id = "mcp-server-" + str(uuid.uuid4())[:8]
                    self.local_peer_info = PeerInfo(
                        peer_id=peer_id,
                        multiaddrs=["/ip4/127.0.0.1/tcp/8000/p2p/" + peer_id],
                        role=PeerRole.MASTER,  # MCP server is always MASTER role
                        capabilities=["ipfs", "mcp"],
                    )
                except Exception as e:
                    logger.error(f"Error creating peer info: {e}")
                    self.local_peer_info = PeerInfo(
                        peer_id="unknown",
                        multiaddrs=[],
                        role=PeerRole.LEECHER,
                        capabilities=[],
                    )

            # Add WebSocket endpoint to router - will be handled by register_peer_websocket
            register_peer_websocket(router, self.local_peer_info, "/peer/websocket")
            logger.info("WebSocket peer discovery endpoint registered")

        logger.info("Peer WebSocket Controller routes registered")

    async def _shutdown(self):
        """Asynchronously shutdown the peer websocket components."""
        if self.peer_websocket_server:
            await self.peer_websocket_server.shutdown()
            self.peer_websocket_server = None
        if self.peer_websocket_client:
            await self.peer_websocket_client.shutdown()
            self.peer_websocket_client = None

    def shutdown_sync(self):
        """Synchronous wrapper to shutdown the peer websocket components."""
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            asyncio.create_task(self._shutdown())
        else:
            asyncio.run(self._shutdown())

    async def check_websocket_support(self) -> Dict[str, Any]:
        """
        Check if WebSocket support is available.

        Returns:
            Dictionary with WebSocket support status
        """
        return {
            "success": True,
            "operation_id": str(uuid.uuid4()),
            "timestamp": time.time(),
            "websocket_available": HAS_PEER_WEBSOCKET,
        }

    async def start_server(self, request: StartServerRequest) -> Dict[str, Any]:
        """
        Start a WebSocket server for peer discovery.

        Args:
            request: Server configuration options

        Returns:
            Dictionary with server status
        """
        if not HAS_PEER_WEBSOCKET:
            return {
                "success": False,
                "operation_id": str(uuid.uuid4()),
                "timestamp": time.time(),
                "error": "WebSocket support not available",
            }

        try:
            # Initialize local peer info
            if self.local_peer_info is None:
                try:
                    # Create a PeerInfo object directly instead of calling create_peer_info_from_ipfs_kit
                    # This addresses the 'ipfs_py' object has no attribute 'id' error
                    peer_id = "mcp-server-" + str(uuid.uuid4())[:8]
                    self.local_peer_info = PeerInfo(
                        peer_id=peer_id,
                        multiaddrs=["/ip4/127.0.0.1/tcp/8000/p2p/" + peer_id],
                        role=request.role or PeerRole.MASTER,  # MCP server is always MASTER role
                        capabilities=request.capabilities or ["ipfs", "mcp"],
                    )
                except Exception as e:
                    logger.error(f"Error creating peer info: {e}")
                    # Create with minimal information
                    self.local_peer_info = PeerInfo(
                        peer_id="unknown",
                        multiaddrs=[],
                        role=request.role or PeerRole.LEECHER,
                        capabilities=request.capabilities or [],
                    )

            # Create and start WebSocket server
            self.peer_websocket_server = PeerWebSocketServer(
                local_peer_info=self.local_peer_info,
                max_peers=request.max_peers,
                heartbeat_interval=request.heartbeat_interval,
                peer_ttl=request.peer_ttl,
            )

            # Start server properly with existing asyncio event loop
            await self.peer_websocket_server.start(host=request.host, port=request.port)

            server_url = f"ws://{request.host}:{request.port}"
            logger.info(f"WebSocket peer discovery server started at {server_url}")

            return {
                "success": True,
                "operation_id": str(uuid.uuid4()),
                "timestamp": time.time(),
                "server_url": server_url,
                "peer_info": self.local_peer_info.to_dict(),
            }

        except Exception as e:
            logger.error(f"Error starting WebSocket server: {e}")
            # Clean up any partially initialized server
            if hasattr(self, "peer_websocket_server") and self.peer_websocket_server is not None:
                try:
                    await self.peer_websocket_server.stop()
                    self.peer_websocket_server = None
                except Exception as cleanup_error:
                    logger.error(
                        f"Error cleaning up WebSocket server after failed start: {cleanup_error}"
                    )

            return {
                "success": False,
                "operation_id": str(uuid.uuid4()),
                "timestamp": time.time(),
                "error": str(e),
            }

    async def stop_server(self) -> Dict[str, Any]:
        """
        Stop the WebSocket server.

        Returns:
            Dictionary with operation status
        """
        if not self.peer_websocket_server:
            return {
                "success": False,
                "operation_id": str(uuid.uuid4()),
                "timestamp": time.time(),
                "error": "Server not running",
            }

        try:
            # Stop server properly with existing asyncio context
            await self.peer_websocket_server.stop()

            # Clear the server reference
            self.peer_websocket_server = None
            logger.info("WebSocket peer discovery server stopped")

            return {
                "success": True,
                "operation_id": str(uuid.uuid4()),
                "timestamp": time.time(),
                "message": "Server stopped successfully",
            }

        except Exception as e:
            logger.error(f"Error stopping WebSocket server: {e}")

            # Even on error, try to clear the server reference to prevent resource leaks
            try:
                self.peer_websocket_server = None
            except Exception:
                pass

            return {
                "success": False,
                "operation_id": str(uuid.uuid4()),
                "timestamp": time.time(),
                "error": str(e),
            }

    async def get_server_status(self) -> Dict[str, Any]:
        """
        Get status of the WebSocket server.

        Returns:
            Dictionary with server status
        """
        if not self.peer_websocket_server:
            return {
                "success": True,
                "operation_id": str(uuid.uuid4()),
                "timestamp": time.time(),
                "running": False,
                "peers_connected": 0,
            }

        peer_count = len(self.peer_websocket_server.connections)
        known_peers = len(self.peer_websocket_server.peers)

        return {
            "success": True,
            "operation_id": str(uuid.uuid4()),
            "timestamp": time.time(),
            "running": True,
            "peers_connected": peer_count,
            "known_peers": known_peers,
            "local_peer": self.local_peer_info.to_dict() if self.local_peer_info else None,
        }

    async def connect_to_server(self, request: ConnectToServerRequest) -> Dict[str, Any]:
        """
        Connect to a WebSocket peer discovery server.

        Args:
            request: Connection configuration options

        Returns:
            Dictionary with connection status
        """
        if not HAS_PEER_WEBSOCKET:
            return {
                "success": False,
                "operation_id": str(uuid.uuid4()),
                "timestamp": time.time(),
                "error": "WebSocket support not available",
            }

        try:
            # Initialize local peer info if needed
            if self.local_peer_info is None:
                try:
                    # Create a PeerInfo object directly instead of calling create_peer_info_from_ipfs_kit
                    # This addresses the 'ipfs_py' object has no attribute 'id' error
                    peer_id = "mcp-client-" + str(uuid.uuid4())[:8]
                    self.local_peer_info = PeerInfo(
                        peer_id=peer_id,
                        multiaddrs=["/ip4/127.0.0.1/tcp/8000/p2p/" + peer_id],
                        role=PeerRole.MASTER,  # MCP server is always MASTER role
                        capabilities=["ipfs", "mcp"],
                    )
                except Exception as e:
                    logger.error(f"Error creating peer info: {e}")
                    # Create with minimal information
                    self.local_peer_info = PeerInfo(
                        peer_id="unknown",
                        multiaddrs=[],
                        role=PeerRole.LEECHER,
                        capabilities=[],
                    )

            # Create callback to handle newly discovered peers
            def on_peer_discovered(peer_info):
                logger.info(f"New peer discovered: {peer_info.peer_id}")
                # Could add additional logic here like notifying a message queue

            # Create client
            if self.peer_websocket_client is None:
                self.peer_websocket_client = PeerWebSocketClient(
                    local_peer_info=self.local_peer_info,
                    on_peer_discovered=on_peer_discovered,
                    auto_connect=request.auto_connect,
                    reconnect_interval=request.reconnect_interval,
                    max_reconnect_attempts=request.max_reconnect_attempts,
                )

                # Start client using the current asyncio context
                await self.peer_websocket_client.start()

            # Connect to server
            connection_result = await self.peer_websocket_client.connect_to_discovery_server(
                request.server_url
            )

            return {
                "success": True,
                "operation_id": str(uuid.uuid4()),
                "timestamp": time.time(),
                "connected": connection_result,
                "server_url": request.server_url,
            }

        except Exception as e:
            logger.error(f"Error connecting to WebSocket server: {e}")

            # Clean up client if it failed to initialize properly
            if hasattr(self, "peer_websocket_client") and self.peer_websocket_client is not None:
                try:
                    await self.peer_websocket_client.stop()
                    self.peer_websocket_client = None
                except Exception as cleanup_error:
                    logger.error(
                        f"Error cleaning up WebSocket client after failed connect: {cleanup_error}"
                    )

            return {
                "success": False,
                "operation_id": str(uuid.uuid4()),
                "timestamp": time.time(),
                "error": str(e),
            }

    async def disconnect_from_server(self) -> Dict[str, Any]:
        """
        Disconnect from the WebSocket peer discovery server.

        Returns:
            Dictionary with operation status
        """
        if not self.peer_websocket_client:
            return {
                "success": False,
                "operation_id": str(uuid.uuid4()),
                "timestamp": time.time(),
                "error": "Client not running",
            }

        try:
            # Stop client using current asyncio context
            await self.peer_websocket_client.stop()

            # Clear the client reference
            self.peer_websocket_client = None
            logger.info("WebSocket peer discovery client stopped")

            return {
                "success": True,
                "operation_id": str(uuid.uuid4()),
                "timestamp": time.time(),
                "message": "Client stopped successfully",
            }

        except Exception as e:
            logger.error(f"Error stopping WebSocket client: {e}")

            # Even on error, try to clear the client reference to prevent resource leaks
            try:
                self.peer_websocket_client = None
            except Exception:
                pass

            return {
                "success": False,
                "operation_id": str(uuid.uuid4()),
                "timestamp": time.time(),
                "error": str(e),
            }

    async def get_discovered_peers(
        self,
        filter_role: Optional[str] = None,
        filter_capabilities: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get list of discovered peers.

        Args:
            filter_role: Filter by peer role
            filter_capabilities: Filter by required capabilities (comma-separated)

        Returns:
            Dictionary with discovered peers
        """
        if not self.peer_websocket_client:
            return {
                "success": True,
                "operation_id": str(uuid.uuid4()),
                "timestamp": time.time(),
                "peers": [],
                "count": 0,
            }

        # Parse capabilities filter
        capabilities_list = None
        if filter_capabilities:
            capabilities_list = filter_capabilities.split(",")

        # Get peers
        peers = self.peer_websocket_client.get_discovered_peers(
            filter_role=filter_role, filter_capabilities=capabilities_list
        )

        # Convert to dictionary representation
        peer_dicts = [peer.to_dict() for peer in peers]

        return {
            "success": True,
            "operation_id": str(uuid.uuid4()),
            "timestamp": time.time(),
            "peers": peer_dicts,
            "count": len(peer_dicts),
        }

    async def get_peer_by_id(self, peer_id: str) -> Dict[str, Any]:
        """
        Get information about a specific peer.

        Args:
            peer_id: Peer identifier

        Returns:
            Dictionary with peer information
        """
        if not self.peer_websocket_client:
            return {
                "success": False,
                "operation_id": str(uuid.uuid4()),
                "timestamp": time.time(),
                "error": "Client not running",
            }

        # Get peer
        peer = self.peer_websocket_client.get_peer_by_id(peer_id)
        if not peer:
            return {
                "success": False,
                "operation_id": str(uuid.uuid4()),
                "timestamp": time.time(),
                "error": f"Peer not found: {peer_id}",
            }

        return {
            "success": True,
            "operation_id": str(uuid.uuid4()),
            "timestamp": time.time(),
            "peer": peer.to_dict(),
        }

    async def shutdown(self):
        """
        Shutdown the controller and clean up resources.

        This method ensures all WebSocket-related resources are properly cleaned up
        when the MCP server is shutting down.
        """
        logger.info("Shutting down Peer WebSocket Controller...")

        # Stop server if running
        if hasattr(self, "peer_websocket_server") and self.peer_websocket_server is not None:
            try:
                logger.info("Stopping WebSocket peer discovery server...")
                await self.peer_websocket_server.stop()
                self.peer_websocket_server = None
                logger.info("WebSocket peer discovery server stopped")
            except Exception as e:
                logger.error(f"Error stopping WebSocket peer server: {e}")

        # Stop client if running
        if hasattr(self, "peer_websocket_client") and self.peer_websocket_client is not None:
            try:
                logger.info("Disconnecting WebSocket peer discovery client...")
                await self.peer_websocket_client.stop()
                self.peer_websocket_client = None
                logger.info("WebSocket peer discovery client stopped")
            except Exception as e:
                logger.error(f"Error stopping WebSocket peer client: {e}")

        logger.info("Peer WebSocket Controller shutdown complete")

    def sync_shutdown(self):
        """
        Synchronous version of shutdown for backward compatibility.

        This method provides a synchronous way to shut down the controller
        for contexts where async/await cannot be used directly.
        """
        logger.info("Running synchronous shutdown for Peer WebSocket Controller")
        try:
            # Try using anyio first (preferred method)
            try:
                import anyio

                anyio.run(self.shutdown)
                return
            except ImportError:
                logger.warning("anyio not available, falling back to asyncio")

            # Fallback to asyncio
            import asyncio

            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                # Create a new event loop if no event loop is set
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # Run the shutdown method
            try:
                loop.run_until_complete(self.shutdown())
            except RuntimeError as e:
                if "This event loop is already running" in str(e):
                    logger.warning("Cannot use run_until_complete in a running event loop")
                    # Cannot handle properly in this case - controller shutdown might be incomplete
                else:
                    raise
        except Exception as e:
            logger.error(f"Error in sync_shutdown for Peer WebSocket Controller: {e}")

        logger.info("Synchronous shutdown for Peer WebSocket Controller completed")