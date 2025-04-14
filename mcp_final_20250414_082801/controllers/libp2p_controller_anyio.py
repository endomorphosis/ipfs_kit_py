import logging
import warnings
import sniffio
import os
import anyio

#!/usr/bin/env python3
"""
libp2p controller for MCP integration with AnyIO support.

This controller provides HTTP endpoints for direct peer-to-peer communication
using libp2p, without requiring the full IPFS daemon. It exposes functionalities
for peer discovery, content routing, and direct content exchange, using AnyIO
for backend-agnostic async operations.
"""

# AnyIO import


# Try to import FastAPI dependencies
try:
    from fastapi import APIRouter, HTTPException, Body, Query, Path, status, Response
    from pydantic import BaseModel, Field
except ImportError:
    # For testing without FastAPI
    class APIRouter:
        def add_api_route(self, *args, **kwargs):
            pass

    class HTTPException(Exception):
        pass

    class Response:
        pass

    class BaseModel:
        pass

    def Body(*args, **kwargs):
        return None

    def Query(*args, **kwargs):
        return None

    def Path(*args, **kwargs):
        return None

    class Field:
        def __init__(self, *args, **kwargs):
            pass

    class status:
        HTTP_404_NOT_FOUND = 404
        HTTP_500_INTERNAL_SERVER_ERROR = 500
        HTTP_503_SERVICE_UNAVAILABLE = 503


# Try to import the dependency checker
try:
    from install_libp2p import ensure_mcp_libp2p_integration, HAS_LIBP2P

    HAS_INSTALL_LIBP2P = True
except ImportError:
    HAS_INSTALL_LIBP2P = False
    # Fallback to standard import if install_libp2p module is not available
    try:
        from ipfs_kit_py.libp2p import HAS_LIBP2P
    except ImportError:
        HAS_LIBP2P = False

# Import our controller
try:
    from ipfs_kit_py.mcp.controllers.libp2p_controller import (
        LibP2PController,
        HealthResponse,
        PeerDiscoveryRequest,
        PeerDiscoveryResponse,
        PeerConnectionRequest,
        ContentRequest,
        ContentDataRequest,
        ContentProvidersResponse,
        DHTFindPeerRequest,
        DHTProvideRequest,
        DHTFindProvidersRequest,
        PubSubPublishRequest,
        PubSubSubscribeRequest,
        PubSubUnsubscribeRequest,
        MessageHandlerRequest,
        StartStopResponse)
except ImportError:

    class LibP2PController:
        pass

    class HealthResponse(BaseModel):
        pass

    class PeerDiscoveryRequest(BaseModel):
        pass

    class PeerDiscoveryResponse(BaseModel):
        pass

    class PeerConnectionRequest(BaseModel):
        pass

    class ContentRequest(BaseModel):
        pass

    class ContentDataRequest(BaseModel):
        pass

    class ContentProvidersResponse(BaseModel):
        pass

    class DHTFindPeerRequest(BaseModel):
        pass

    class DHTProvideRequest(BaseModel):
        pass

    class DHTFindProvidersRequest(BaseModel):
        pass

    class PubSubPublishRequest(BaseModel):
        pass

    class PubSubSubscribeRequest(BaseModel):
        pass

    class PubSubUnsubscribeRequest(BaseModel):
        pass

    class MessageHandlerRequest(BaseModel):
        pass

    class StartStopResponse(BaseModel):
        pass


# Configure logger
logger = logging.getLogger(__name__)


class LibP2PControllerAnyIO(LibP2PController):
    """
    Controller for libp2p peer-to-peer operations with AnyIO support.

    This controller provides HTTP endpoints for direct peer-to-peer communication
    using libp2p, without requiring the full IPFS daemon. It exposes functionalities
    for peer discovery, content routing, and direct content exchange, using AnyIO
    for backend-agnostic async operations.
    """
    def __init___v2(self, libp2p_model):
        """
        Initialize the libp2p controller with AnyIO support.

        Args:
            libp2p_model: The libp2p model instance to use
        """
        # Check for LibP2P dependencies before initializing
        libp2p_available = False

        # Try to use the dependency management system if available
        if HAS_INSTALL_LIBP2P:
            try:
                # Check if auto-installation is enabled via environment variable
                auto_install = os.environ.get("IPFS_KIT_AUTO_INSTALL_DEPS", "0") == "1"

                if auto_install:
                    logger.info("Auto-installing LibP2P dependencies for MCP integration...")
                    libp2p_available = ensure_mcp_libp2p_integration()
                    if libp2p_available:
                        logger.info(
                            "LibP2P dependencies successfully installed for MCP integration"
                        )
                    else:
                        logger.warning("Failed to install LibP2P dependencies for MCP integration")
                else:
                    # Just check if dependencies are available without installing
                    libp2p_available = HAS_LIBP2P
                    if not libp2p_available:
                        logger.warning(
                            "LibP2P dependencies not available and auto-installation is disabled"
                        )
                        logger.warning(
                            "Set IPFS_KIT_AUTO_INSTALL_DEPS=1 to enable auto-installation"
                        )
            except Exception as e:
                logger.error(f"Error checking LibP2P dependencies: {e}")
                libp2p_available = False
        else:
            # Fall back to basic check if dependency management is not available
            libp2p_available = HAS_LIBP2P
            if not libp2p_available:
                logger.warning(
                    "LibP2P dependencies not available and install_libp2p module not found"
                )

        # Store dependency status for health check
        self.libp2p_dependencies_available = libp2p_available

        # Add shutdown-related attributes
        self.is_shutting_down = False
        self.event_loop_thread = None
        self.cleanup_task = None
        self.host = None
        self.peer = None
        self.swarm = None

        # Initialize the parent class
        super().__init__(libp2p_model)
        logger.info(
            f"LibP2P controller with AnyIO initialized (dependencies available: {libp2p_available})"
        )

    async def shutdown(self):
        """
        Shutdown the controller and clean up resources.

        This method ensures all LibP2P-related resources are properly cleaned up
        when the MCP server is shutting down. It handles:
        1. Stopping the LibP2P peer/host
        2. Cleaning up connections and swarm resources
        3. Closing any open streams
        4. Handling event loop threads for proper cleanup
        5. Cancelling any ongoing tasks
        """
        logger.info("Shutting down LibP2P Controller...")

        # Set a flag to indicate shutdown in progress
        self.is_shutting_down = True

        # Stop libp2p peer if running
        if hasattr(self, "peer") and self.peer is not None:
            try:
                logger.info("Stopping LibP2P peer...")

                # Try to close any open streams or connections first
                if hasattr(self.peer, "swarm") and self.peer.swarm is not None:
                    try:
                        logger.info("Closing LibP2P swarm connections...")

                        # Try to access connections if available
                        if hasattr(self.peer.swarm, "connections") and isinstance(
                            self.peer.swarm.connections, dict
                        ):
                            connections = list(self.peer.swarm.connections.items())
                            logger.info(f"Closing {len(connections)} LibP2P connections")

                            # Close each connection
                            for peer_id, conn_list in connections:
                                try:
                                    logger.info(f"Closing connections to peer {peer_id}")
                                    for conn in conn_list:
                                        # Try multiple methods for closing
                                        for method_name in [
                                            "close",
                                            "disconnect",
                                            "stop",
                                        ]:
                                            if hasattr(conn, method_name) and callable(
                                                getattr(conn, method_name)
                                            ):
                                                try:
                                                    await anyio.to_thread.run_sync(
                                                        getattr(conn, method_name)
                                                    )
                                                    break
                                                except Exception as close_err:
                                                    logger.error(
                                                        f"Error calling {method_name} on connection: {close_err}"
                                                    )
                                except Exception as conn_err:
                                    logger.error(
                                        f"Error closing connections to peer {peer_id}: {conn_err}"
                                    )

                            # Clear the connections dictionary
                            self.peer.swarm.connections.clear()
                    except Exception as swarm_err:
                        logger.error(f"Error cleaning up LibP2P swarm: {swarm_err}")

                # Stop the peer using model method
                if self.libp2p_model and hasattr(self.libp2p_model, "stop"):
                    try:
                        logger.info("Calling model.stop() to shutdown LibP2P peer")
                        await anyio.to_thread.run_sync(self.libp2p_model.stop)
                        logger.info("LibP2P peer stopped via model")
                    except Exception as model_err:
                        logger.error(f"Error stopping LibP2P peer via model: {model_err}")

                        # Try direct method on peer if model method fails
                        if hasattr(self.peer, "stop") and callable(self.peer.stop):
                            try:
                                logger.info("Calling direct peer.stop() method")
                                await anyio.to_thread.run_sync(self.peer.stop)
                                logger.info("LibP2P peer stopped via direct method")
                            except Exception as direct_err:
                                logger.error(
                                    f"Error stopping LibP2P peer via direct method: {direct_err}"
                                )

                # Clear references
                self.peer = None
                self.host = None
                self.swarm = None
                logger.info("Cleared LibP2P peer references")
            except Exception as e:
                logger.error(f"Error stopping LibP2P peer: {e}")

        # Clean up event loop thread if it exists
        if hasattr(self, "event_loop_thread") and self.event_loop_thread is not None:
            try:
                logger.info("Cleaning up LibP2P event loop thread...")

                # Try to access event_loop attribute if it exists
                if (
                    hasattr(self.event_loop_thread, "event_loop")
                    and self.event_loop_thread.event_loop
                ):
                    try:
                        # Set shutdown flag if it exists
                        if hasattr(self.event_loop_thread.event_loop, "should_exit"):
                            self.event_loop_thread.event_loop.should_exit = True
                            logger.info("Set should_exit flag on LibP2P event loop")

                        # Try to call stop on the event loop if it exists
                        if hasattr(self.event_loop_thread.event_loop, "stop") and callable(
                            self.event_loop_thread.event_loop.stop
                        ):
                            self.event_loop_thread.event_loop.stop()
                            logger.info("Called stop() on LibP2P event loop")
                    except Exception as e:
                        logger.error(f"Error stopping LibP2P event loop: {e}")

                # Try to join thread with timeout if it's a Thread object
                if hasattr(self.event_loop_thread, "join") and callable(
                    self.event_loop_thread.join
                ):
                    self.event_loop_thread.join(timeout=1.0)
                    logger.info("Successfully joined LibP2P event_loop_thread")

                # Set to None to help with garbage collection
                self.event_loop_thread = None
                logger.info("Cleared LibP2P event_loop_thread reference")
            except Exception as e:
                logger.error(f"Error cleaning up LibP2P event loop thread: {e}")

        # Clean up cleanup_task if it exists
        if hasattr(self, "cleanup_task") and self.cleanup_task is not None:
            try:
                logger.info("Cancelling LibP2P cleanup task...")

                # Handle different types of task objects
                if hasattr(self.cleanup_task, "cancel"):
                    # It's a standard task
                    self.cleanup_task.cancel()
                    logger.info("Cancelled LibP2P cleanup task")
                elif hasattr(self.cleanup_task, "cancel_scope"):
                    # It's a task with cancel scope
                    self.cleanup_task.cancel_scope.cancel()
                    logger.info("Cancelled LibP2P cleanup task scope")

                # Set to None to help with garbage collection
                self.cleanup_task = None
                logger.info("Cleared LibP2P cleanup_task reference")
            except Exception as e:
                logger.error(f"Error cancelling LibP2P cleanup task: {e}")

        logger.info("LibP2P Controller shutdown complete")

    @staticmethod
    def get_backend():
        """Get the current async backend being used."""
        try:
            return sniffio.current_async_library()
        except sniffio.AsyncLibraryNotFoundError:
            return None

    def _warn_if_async_context(self, method_name):
        """Warn if called from async context without using async version."""
        backend = self.get_backend()
        if backend is not None:
            warnings.warn(
                f"Synchronous method {method_name} called from async context. "
                f"Use {method_name}_async instead for better performance.",
                stacklevel=3,
            )

    # Override synchronous methods to add warnings
    def health_check(self):
        """Check libp2p health with warning in async context."""
        self._warn_if_async_context("health_check")
        return super().health_check()

    def discover_peers(self, request):
        """Discover peers with warning in async context."""
        self._warn_if_async_context("discover_peers")
        return super().discover_peers(request)

    def get_peers(self, method="all", limit=10):
        """Get peers with warning in async context."""
        self._warn_if_async_context("get_peers")
        return super().get_peers(method, limit)

    def connect_peer(self, request):
        """Connect to peer with warning in async context."""
        self._warn_if_async_context("connect_peer")
        return super().connect_peer(request)

    def find_providers(self, cid, timeout=30):
        """Find providers with warning in async context."""
        self._warn_if_async_context("find_providers")
        return super().find_providers(cid, timeout)

    def retrieve_content_info(self, cid, timeout=60):
        """Retrieve content info with warning in async context."""
        self._warn_if_async_context("retrieve_content_info")
        return super().retrieve_content_info(cid, timeout)

    def retrieve_content(self, cid, timeout=60):
        """Retrieve content with warning in async context."""
        self._warn_if_async_context("retrieve_content")
        return super().retrieve_content(cid, timeout)

    def announce_content(self, request):
        """Announce content with warning in async context."""
        self._warn_if_async_context("announce_content")
        return super().announce_content(request)

    def get_connected_peers(self):
        """Get connected peers with warning in async context."""
        self._warn_if_async_context("get_connected_peers")
        return super().get_connected_peers()

    def get_peer_info(self, peer_id):
        """Get peer info with warning in async context."""
        self._warn_if_async_context("get_peer_info")
        return super().get_peer_info(peer_id)

    def get_stats(self):
        """Get stats with warning in async context."""
        self._warn_if_async_context("get_stats")
        return super().get_stats()

    def reset(self):
        """Reset with warning in async context."""
        self._warn_if_async_context("reset")
        return super().reset()

    def start_peer(self):
        """Start peer with warning in async context."""
        self._warn_if_async_context("start_peer")
        return super().start_peer()

    def stop_peer(self):
        """Stop peer with warning in async context."""
        self._warn_if_async_context("stop_peer")
        return super().stop_peer()

    def dht_find_peer(self, request):
        """Find peer in DHT with warning in async context."""
        self._warn_if_async_context("dht_find_peer")
        return super().dht_find_peer(request)

    def dht_provide(self, request):
        """Provide in DHT with warning in async context."""
        self._warn_if_async_context("dht_provide")
        return super().dht_provide(request)

    def dht_find_providers(self, request):
        """Find providers in DHT with warning in async context."""
        self._warn_if_async_context("dht_find_providers")
        return super().dht_find_providers(request)

    def pubsub_publish(self, request):
        """Publish to pubsub with warning in async context."""
        self._warn_if_async_context("pubsub_publish")
        return super().pubsub_publish(request)

    def pubsub_subscribe(self, request):
        """Subscribe to pubsub with warning in async context."""
        self._warn_if_async_context("pubsub_subscribe")
        return super().pubsub_subscribe(request)

    def pubsub_unsubscribe(self, request):
        """Unsubscribe from pubsub with warning in async context."""
        self._warn_if_async_context("pubsub_unsubscribe")
        return super().pubsub_unsubscribe(request)

    def pubsub_get_topics(self):
        """Get pubsub topics with warning in async context."""
        self._warn_if_async_context("pubsub_get_topics")
        return super().pubsub_get_topics()

    def pubsub_get_peers(self, topic=None):
        """Get pubsub peers with warning in async context."""
        self._warn_if_async_context("pubsub_get_peers")
        return super().pubsub_get_peers(topic)

    def register_message_handler(self, request):
        """Register message handler with warning in async context."""
        self._warn_if_async_context("register_message_handler")
        return super().register_message_handler(request)

    def unregister_message_handler(self, request):
        """Unregister message handler with warning in async context."""
        self._warn_if_async_context("unregister_message_handler")
        return super().unregister_message_handler(request)

    def list_message_handlers(self):
        """List message handlers with warning in async context."""
        self._warn_if_async_context("list_message_handlers")
        return super().list_message_handlers()

    # Async implementation of methods
    async def health_check_async(self):
        """
        Check if libp2p is available and healthy asynchronously.

        Returns:
            dict: Health status information
        """
        # Check if libp2p model is initialized
        if not self.libp2p_model:
            return {
                "success": False
                "libp2p_available": False
                "peer_initialized": False
                "error": "libp2p model not initialized",
                "error_type": "initialization_error",
            }

        # Get detailed dependency status
        dependency_status = {
            "libp2p_available": hasattr(self, "libp2p_dependencies_available")
            and self.libp2p_dependencies_available,
            "install_libp2p_available": HAS_INSTALL_LIBP2P
            "auto_install_enabled": os.environ.get("IPFS_KIT_AUTO_INSTALL_DEPS", "0") == "1",
        }

        # If dependencies are missing but installation is possible, include that info
        if (
            not dependency_status["libp2p_available"]
            and dependency_status["install_libp2p_available"]
        ):
            dependency_status["installation_hint"] = (
                "Set IPFS_KIT_AUTO_INSTALL_DEPS=1 to enable auto-installation"
            )

        try:
            # Get health from model using anyio
            result = await anyio.to_thread.run_sync(self.libp2p_model.get_health)

            # Add our enhanced dependency status to the result
            result["dependencies"] = dependency_status

            # If not successful due to missing dependencies, enhance the error message
            if not result.get("success") and not result.get("peer_initialized"):
                # Check if it's specifically a dependency issue
                if not dependency_status["libp2p_available"]:
                    result["error_type"] = "dependency_error"

                    # Provide more helpful error message
                    if (
                        dependency_status["install_libp2p_available"]
                        and not dependency_status["auto_install_enabled"]
                    ):
                        result["error"] = (
                            "LibP2P dependencies not available. Set IPFS_KIT_AUTO_INSTALL_DEPS=1 to enable auto-installation."
                        )
                    else:
                        result["error"] = "LibP2P dependencies not available."

                # Still raise HTTP exception for API consistency
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=result.get("error", "libp2p service unavailable"),
                )

            return result

        except Exception as e:
            # If we can't even check health, create a basic status response
            if isinstance(e, HTTPException):
                # Re-raise HTTP exceptions
                raise

            # For other errors, return a detailed error response
            logger.error(f"Error checking libp2p health: {e}")
            return {
                "success": False
                "libp2p_available": dependency_status["libp2p_available"],
                "peer_initialized": False
                "error": f"Error checking libp2p health: {str(e)}",
                "error_type": "health_check_error",
                "dependencies": dependency_status
            }

    async def discover_peers_async(self, request: PeerDiscoveryRequest):
        """
        Discover peers using various discovery mechanisms asynchronously.

        Args:
            request: Peer discovery request parameters

        Returns:
            dict: Discovered peers information
        """
        # Check if libp2p is available
        is_available = await anyio.to_thread.run_sync(self.libp2p_model.is_available)
        if not is_available:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p is not available",
            )

        # Call model method using anyio
        result = await anyio.to_thread.run_sync(
            self.libp2p_model.discover_peers,
            discovery_method=request.discovery_method,
            limit=request.limit,
        )

        # If not successful, raise HTTP exception
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to discover peers"),
            )

        return result

    async def get_peers_async(
        self
        method: str = Query("all", description="Discovery method (dht, mdns, bootstrap, all)"),
        limit: int = Query(10, description="Maximum number of peers to discover", ge=1, le=100),
    ):
        """
        Get list of discovered peers asynchronously.

        Args:
            method: Discovery method to use
            limit: Maximum number of peers to return

        Returns:
            dict: Discovered peers information
        """
        # Check if libp2p is available
        is_available = await anyio.to_thread.run_sync(self.libp2p_model.is_available)
        if not is_available:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p is not available",
            )

        # Call model method using anyio
        result = await anyio.to_thread.run_sync(
            self.libp2p_model.discover_peers, discovery_method=method, limit=limit
        )

        # If not successful, raise HTTP exception
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to discover peers"),
            )

        return result

    async def connect_peer_async(self, request: PeerConnectionRequest):
        """
        Connect to a specific peer asynchronously.

        Args:
            request: Peer connection request parameters

        Returns:
            dict: Connection status
        """
        # Check if libp2p is available
        is_available = await anyio.to_thread.run_sync(self.libp2p_model.is_available)
        if not is_available:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p is not available",
            )

        # Call model method using anyio
        result = await anyio.to_thread.run_sync(
            self.libp2p_model.connect_peer, peer_addr=request.peer_addr
        )

        # If not successful, raise HTTP exception
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to connect to peer"),
            )

        return result

    async def find_providers_async(
        self
        cid: str = Path(..., description="Content ID to find providers for"),
        timeout: int = Query(30, description="Timeout in seconds", ge=1, le=300),
    ):
        """
        Find providers for a specific CID asynchronously.

        Args:
            cid: Content ID to find providers for
            timeout: Timeout in seconds

        Returns:
            dict: Content providers information
        """
        # Check if libp2p is available
        is_available = await anyio.to_thread.run_sync(self.libp2p_model.is_available)
        if not is_available:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p is not available",
            )

        # Call model method using anyio
        result = await anyio.to_thread.run_sync(
            self.libp2p_model.find_content, cid=cid, timeout=timeout
        )

        # If not successful but it's just that no providers were found,
        # return empty result instead of error
        if not result.get("success") and result.get("error_type") == "provider_lookup_error":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to find content providers"),
            )

        return result

    async def retrieve_content_info_async(
        self
        cid: str = Path(..., description="Content ID to retrieve info for"),
        timeout: int = Query(60, description="Timeout in seconds", ge=1, le=300),
    ):
        """
        Check if content is available and get metadata asynchronously.

        Args:
            cid: Content ID to retrieve info for
            timeout: Timeout in seconds

        Returns:
            dict: Content metadata
        """
        # Check if libp2p is available
        is_available = await anyio.to_thread.run_sync(self.libp2p_model.is_available)
        if not is_available:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p is not available",
            )

        # Call model method using anyio
        result = await anyio.to_thread.run_sync(
            self.libp2p_model.retrieve_content, cid=cid, timeout=timeout
        )

        # If not successful and content not found, return 404
        if not result.get("success") and result.get("error_type") == "content_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result.get("error", f"Content not found: {cid}"),
            )

        # If other error, return 500
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to retrieve content info"),
            )

        return result

    async def retrieve_content_async(
        self
        cid: str = Path(..., description="Content ID to retrieve"),
        timeout: int = Query(60, description="Timeout in seconds", ge=1, le=300),
    ):
        """
        Retrieve content data by CID asynchronously.

        Args:
            cid: Content ID to retrieve
            timeout: Timeout in seconds

        Returns:
            bytes: Content data or error response
        """
        # Check if libp2p is available
        is_available = await anyio.to_thread.run_sync(self.libp2p_model.is_available)
        if not is_available:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p is not available",
            )

        # Call model method using anyio
        result = await anyio.to_thread.run_sync(
            self.libp2p_model.get_content, cid=cid, timeout=timeout
        )

        # If not successful and content not found, return 404
        if not result.get("success") and result.get("error_type") == "content_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result.get("error", f"Content not found: {cid}"),
            )

        # If other error, return 500
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to retrieve content"),
            )

        # Return content data directly
        content_data = result.get("data")

        # Try to detect content type
        content_type = "application/octet-stream"
        if content_data and len(content_data) > 2:
            # The content type detection is the same as in the original method
            # Check for common magic bytes
            if content_data.startswith(b"\xff\xd8\xff"):
                content_type = "image/jpeg"
            elif content_data.startswith(b"\x89PNG\r\n\x1a\n"):
                content_type = "image/png"
            elif content_data.startswith(b"GIF87a") or content_data.startswith(b"GIF89a"):
                content_type = "image/gif"
            elif content_data.startswith(b"%PDF"):
                content_type = "application/pdf"
            elif content_data.startswith(b"PK\x03\x04"):
                content_type = "application/zip"
            # Text detection
            elif all(c < 128 and c >= 32 or c in (9, 10, 13) for c in content_data[:100]):
                try:
                    # Check if it's JSON
                    if (content_data.startswith(b"{") and content_data.rstrip().endswith(b"}")) or (
                        content_data.startswith(b"[") and content_data.rstrip().endswith(b"]")
                    ):
                        content_type = "application/json"
                    else:
                        content_type = "text/plain"
                except Exception:
                    content_type = "text/plain"

        return Response(
            content=content_data,
            media_type=content_type,
            headers={
                "Content-Disposition": f"attachment; filename={cid}",
                "X-Content-CID": cid
                "X-Content-Size": str(len(content_data)) if content_data else "0",
            },
        )

    async def announce_content_async(self, request: ContentDataRequest):
        """
        Announce content availability to the network asynchronously.

        Args:
            request: Content announcement request parameters

        Returns:
            dict: Announcement status
        """
        # Check if libp2p is available
        is_available = await anyio.to_thread.run_sync(self.libp2p_model.is_available)
        if not is_available:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p is not available",
            )

        # Call model method using anyio
        result = await anyio.to_thread.run_sync(
            self.libp2p_model.announce_content, cid=request.cid, data=request.data
        )

        # If not successful, raise HTTP exception
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to announce content"),
            )

        return result

    async def get_connected_peers_async(self):
        """
        Get information about currently connected peers asynchronously.

        Returns:
            dict: Connected peers information
        """
        # Check if libp2p is available
        is_available = await anyio.to_thread.run_sync(self.libp2p_model.is_available)
        if not is_available:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p is not available",
            )

        # Call model method using anyio
        result = await anyio.to_thread.run_sync(self.libp2p_model.get_connected_peers)

        # If not successful, raise HTTP exception
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to get connected peers"),
            )

        return result

    async def get_peer_info_async(
        self, peer_id: str = Path(..., description="Peer ID to get info for")
    ):
        """
        Get detailed information about a specific peer asynchronously.

        Args:
            peer_id: Peer ID to get info for

        Returns:
            dict: Peer information
        """
        # Check if libp2p is available
        is_available = await anyio.to_thread.run_sync(self.libp2p_model.is_available)
        if not is_available:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p is not available",
            )

        # Call model method using anyio
        result = await anyio.to_thread.run_sync(self.libp2p_model.get_peer_info, peer_id=peer_id)

        # If not successful and peer not found, return 404
        if not result.get("success") and result.get("error_type") == "peer_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result.get("error", f"Peer not found: {peer_id}"),
            )

        # If other error, return 500
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to get peer info"),
            )

        return result

    async def get_stats_async(self):
        """
        Get operation statistics asynchronously.

        Returns:
            dict: Operation statistics
        """
        # Check if libp2p model is initialized
        if not self.libp2p_model:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p model not initialized",
            )

        # Get stats from model using anyio
        return await anyio.to_thread.run_sync(self.libp2p_model.get_stats)

    async def reset_async(self):
        """
        Reset the libp2p peer, clearing caches and statistics asynchronously.

        Returns:
            dict: Reset status
        """
        # Check if libp2p model is initialized
        if not self.libp2p_model:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p model not initialized",
            )

        # Call model method using anyio
        result = await anyio.to_thread.run_sync(self.libp2p_model.reset)

        # If not successful, raise HTTP exception
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to reset libp2p peer"),
            )

        return result

    async def start_peer_async(self):
        """
        Start the libp2p peer if it's not already running asynchronously.

        Returns:
            dict: Start status
        """
        # Check if libp2p model is initialized
        if not self.libp2p_model:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p model not initialized",
            )

        # Call model method using anyio
        result = await anyio.to_thread.run_sync(self.libp2p_model.start)

        # If not successful, raise HTTP exception
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to start libp2p peer"),
            )

        return result

    async def stop_peer_async(self):
        """
        Stop the libp2p peer if it's running asynchronously.

        Returns:
            dict: Stop status
        """
        # Check if libp2p model is initialized
        if not self.libp2p_model:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p model not initialized",
            )

        # Call model method using anyio
        result = await anyio.to_thread.run_sync(self.libp2p_model.stop)

        # If not successful, raise HTTP exception
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to stop libp2p peer"),
            )

        return result

    async def dht_find_peer_async(self, request: DHTFindPeerRequest):
        """
        Find a peer's addresses using the DHT asynchronously.

        Args:
            request: DHT find peer request parameters

        Returns:
            dict: Peer addresses information
        """
        # Check if libp2p is available
        is_available = await anyio.to_thread.run_sync(self.libp2p_model.is_available)
        if not is_available:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p is not available",
            )

        # Call model method using anyio
        result = await anyio.to_thread.run_sync(
            self.libp2p_model.dht_find_peer,
            peer_id=request.peer_id,
            timeout=request.timeout,
        )

        # If not successful, raise HTTP exception
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to find peer in DHT"),
            )

        return result

    async def dht_provide_async(self, request: DHTProvideRequest):
        """
        Announce to the DHT that we are providing a CID asynchronously.

        Args:
            request: DHT provide request parameters

        Returns:
            dict: Provide status
        """
        # Check if libp2p is available
        is_available = await anyio.to_thread.run_sync(self.libp2p_model.is_available)
        if not is_available:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p is not available",
            )

        # Call model method using anyio
        result = await anyio.to_thread.run_sync(self.libp2p_model.dht_provide, cid=request.cid)

        # If not successful, raise HTTP exception
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to provide content in DHT"),
            )

        return result

    async def dht_find_providers_async(self, request: DHTFindProvidersRequest):
        """
        Find providers for a CID using the DHT asynchronously.

        Args:
            request: DHT find providers request parameters

        Returns:
            dict: Provider information
        """
        # Check if libp2p is available
        is_available = await anyio.to_thread.run_sync(self.libp2p_model.is_available)
        if not is_available:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p is not available",
            )

        # Call model method using anyio
        result = await anyio.to_thread.run_sync(
            self.libp2p_model.dht_find_providers,
            cid=request.cid,
            timeout=request.timeout,
            limit=request.limit,
        )

        # If not successful, raise HTTP exception
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to find providers in DHT"),
            )

        return result

    async def pubsub_publish_async(self, request: PubSubPublishRequest):
        """
        Publish a message to a PubSub topic asynchronously.

        Args:
            request: PubSub publish request parameters

        Returns:
            dict: Publish status
        """
        # Check if libp2p is available
        is_available = await anyio.to_thread.run_sync(self.libp2p_model.is_available)
        if not is_available:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p is not available",
            )

        # Call model method using anyio
        result = await anyio.to_thread.run_sync(
            self.libp2p_model.pubsub_publish,
            topic=request.topic,
            message=request.message,
        )

        # If not successful, raise HTTP exception
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to publish message"),
            )

        return result

    async def pubsub_subscribe_async(self, request: PubSubSubscribeRequest):
        """
        Subscribe to a PubSub topic asynchronously.

        Args:
            request: PubSub subscribe request parameters

        Returns:
            dict: Subscription status
        """
        # Check if libp2p is available
        is_available = await anyio.to_thread.run_sync(self.libp2p_model.is_available)
        if not is_available:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p is not available",
            )

        # Call model method using anyio
        result = await anyio.to_thread.run_sync(
            self.libp2p_model.pubsub_subscribe,
            topic=request.topic,
            handler_id=request.handler_id,
        )

        # If not successful, raise HTTP exception
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to subscribe to topic"),
            )

        return result

    async def pubsub_unsubscribe_async(self, request: PubSubUnsubscribeRequest):
        """
        Unsubscribe from a PubSub topic asynchronously.

        Args:
            request: PubSub unsubscribe request parameters

        Returns:
            dict: Unsubscription status
        """
        # Check if libp2p is available
        is_available = await anyio.to_thread.run_sync(self.libp2p_model.is_available)
        if not is_available:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p is not available",
            )

        # Call model method using anyio
        result = await anyio.to_thread.run_sync(
            self.libp2p_model.pubsub_unsubscribe,
            topic=request.topic,
            handler_id=request.handler_id,
        )

        # If not successful, raise HTTP exception
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to unsubscribe from topic"),
            )

        return result

    async def pubsub_get_topics_async(self):
        """
        Get list of subscribed PubSub topics asynchronously.

        Returns:
            dict: Topic list
        """
        # Check if libp2p is available
        is_available = await anyio.to_thread.run_sync(self.libp2p_model.is_available)
        if not is_available:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p is not available",
            )

        # Call model method using anyio
        result = await anyio.to_thread.run_sync(self.libp2p_model.pubsub_get_topics)

        # If not successful, raise HTTP exception
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to get topics"),
            )

        return result

    async def pubsub_get_peers_async(
        self, topic: str = Query(None, description="Optional topic to filter peers by")
    ):
        """
        Get list of peers in the PubSub mesh asynchronously.

        Args:
            topic: Optional topic to filter peers by

        Returns:
            dict: Peer list
        """
        # Check if libp2p is available
        is_available = await anyio.to_thread.run_sync(self.libp2p_model.is_available)
        if not is_available:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p is not available",
            )

        # Call model method using anyio
        result = await anyio.to_thread.run_sync(self.libp2p_model.pubsub_get_peers, topic=topic)

        # If not successful, raise HTTP exception
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to get pubsub peers"),
            )

        return result

    async def register_message_handler_async(self, request: MessageHandlerRequest):
        """
        Register a new protocol message handler asynchronously.

        Args:
            request: Message handler registration request parameters

        Returns:
            dict: Registration status
        """
        # Check if libp2p is available
        is_available = await anyio.to_thread.run_sync(self.libp2p_model.is_available)
        if not is_available:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p is not available",
            )

        # Call model method using anyio
        result = await anyio.to_thread.run_sync(
            self.libp2p_model.register_message_handler,
            handler_id=request.handler_id,
            protocol_id=request.protocol_id,
            description=request.description,
        )

        # If not successful, raise HTTP exception
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to register message handler"),
            )

        return result

    async def unregister_message_handler_async(self, request: MessageHandlerRequest):
        """
        Unregister a protocol message handler asynchronously.

        Args:
            request: Message handler unregistration request parameters

        Returns:
            dict: Unregistration status
        """
        # Check if libp2p is available
        is_available = await anyio.to_thread.run_sync(self.libp2p_model.is_available)
        if not is_available:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p is not available",
            )

        # Call model method using anyio
        result = await anyio.to_thread.run_sync(
            self.libp2p_model.unregister_message_handler,
            handler_id=request.handler_id,
            protocol_id=request.protocol_id,
        )

        # If not successful, raise HTTP exception
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to unregister message handler"),
            )

        return result

    async def list_message_handlers_async(self):
        """
        List all registered protocol message handlers asynchronously.

        Returns:
            dict: Handler list
        """
        # Check if libp2p is available
        is_available = await anyio.to_thread.run_sync(self.libp2p_model.is_available)
        if not is_available:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p is not available",
            )

        # Call model method using anyio
        result = await anyio.to_thread.run_sync(self.libp2p_model.list_message_handlers)

        # If not successful, raise HTTP exception
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to list message handlers"),
            )

        return result

    def register_routes(self, router: APIRouter):
        """
        Register routes with the API router. Overrides base method to use async versions.

        Args:
            router: FastAPI router to register routes with
        """
        # Health check endpoint
        if "/libp2p/health" not in self.initialized_endpoints:
            router.add_api_route(
                "/libp2p/health",
                self.health_check_async,
                methods=["GET"],
                response_model=HealthResponse,
                summary="Check libp2p health",
                description="Check if libp2p is available and get peer health information",
                tags=["libp2p"],
            )
            self.initialized_endpoints.add("/libp2p/health")

        # Peer discovery endpoint
        if "/libp2p/discover" not in self.initialized_endpoints:
            router.add_api_route(
                "/libp2p/discover",
                self.discover_peers_async,
                methods=["POST"],
                response_model=PeerDiscoveryResponse,
                summary="Discover peers",
                description="Discover peers using various discovery mechanisms",
                tags=["libp2p"],
            )
            self.initialized_endpoints.add("/libp2p/discover")

        # Simple peer discovery with GET
        if "/libp2p/peers" not in self.initialized_endpoints:
            router.add_api_route(
                "/libp2p/peers",
                self.get_peers_async,
                methods=["GET"],
                response_model=PeerDiscoveryResponse,
                summary="List peers",
                description="Get list of discovered peers",
                tags=["libp2p"],
            )
            self.initialized_endpoints.add("/libp2p/peers")

        # Connect to peer endpoint
        if "/libp2p/connect" not in self.initialized_endpoints:
            router.add_api_route(
                "/libp2p/connect",
                self.connect_peer_async,
                methods=["POST"],
                summary="Connect to peer",
                description="Connect to a specific peer using multiaddr",
                tags=["libp2p"],
            )
            self.initialized_endpoints.add("/libp2p/connect")

        # Find content providers endpoint
        if "/libp2p/providers/{cid}" not in self.initialized_endpoints:
            router.add_api_route(
                "/libp2p/providers/{cid}",
                self.find_providers_async,
                methods=["GET"],
                response_model=ContentProvidersResponse,
                summary="Find content providers",
                description="Find providers for a specific CID",
                tags=["libp2p"],
            )
            self.initialized_endpoints.add("/libp2p/providers/{cid}")

        # Retrieve content metadata endpoint
        if "/libp2p/content/info/{cid}" not in self.initialized_endpoints:
            router.add_api_route(
                "/libp2p/content/info/{cid}",
                self.retrieve_content_info_async,
                methods=["GET"],
                summary="Get content info",
                description="Check if content is available and get metadata",
                tags=["libp2p"],
            )
            self.initialized_endpoints.add("/libp2p/content/info/{cid}")

        # Retrieve content data endpoint
        if "/libp2p/content/{cid}" not in self.initialized_endpoints:
            router.add_api_route(
                "/libp2p/content/{cid}",
                self.retrieve_content_async,
                methods=["GET"],
                summary="Get content",
                description="Retrieve content data by CID",
                tags=["libp2p"],
                response_class=Response,
            )
            self.initialized_endpoints.add("/libp2p/content/{cid}")

        # Announce content endpoint
        if "/libp2p/announce" not in self.initialized_endpoints:
            router.add_api_route(
                "/libp2p/announce",
                self.announce_content_async,
                methods=["POST"],
                summary="Announce content",
                description="Announce content availability to the network",
                tags=["libp2p"],
            )
            self.initialized_endpoints.add("/libp2p/announce")

        # Get connected peers endpoint
        if "/libp2p/connected" not in self.initialized_endpoints:
            router.add_api_route(
                "/libp2p/connected",
                self.get_connected_peers_async,
                methods=["GET"],
                summary="Get connected peers",
                description="Get information about currently connected peers",
                tags=["libp2p"],
            )
            self.initialized_endpoints.add("/libp2p/connected")

        # Get peer info endpoint
        if "/libp2p/peer/{peer_id}" not in self.initialized_endpoints:
            router.add_api_route(
                "/libp2p/peer/{peer_id}",
                self.get_peer_info_async,
                methods=["GET"],
                summary="Get peer info",
                description="Get detailed information about a specific peer",
                tags=["libp2p"],
            )
            self.initialized_endpoints.add("/libp2p/peer/{peer_id}")

        # Get stats endpoint
        if "/libp2p/stats" not in self.initialized_endpoints:
            router.add_api_route(
                "/libp2p/stats",
                self.get_stats_async,
                methods=["GET"],
                summary="Get stats",
                description="Get operation statistics",
                tags=["libp2p"],
            )
            self.initialized_endpoints.add("/libp2p/stats")

        # Reset endpoint
        if "/libp2p/reset" not in self.initialized_endpoints:
            router.add_api_route(
                "/libp2p/reset",
                self.reset_async,
                methods=["POST"],
                summary="Reset",
                description="Reset the libp2p peer, clearing caches and statistics",
                tags=["libp2p"],
            )
            self.initialized_endpoints.add("/libp2p/reset")

        # Add lifecycle management endpoints
        if "/libp2p/start" not in self.initialized_endpoints:
            router.add_api_route(
                "/libp2p/start",
                self.start_peer_async,
                methods=["POST"],
                response_model=StartStopResponse,
                summary="Start peer",
                description="Start the libp2p peer if it's not already running",
                tags=["libp2p"],
            )
            self.initialized_endpoints.add("/libp2p/start")

        if "/libp2p/stop" not in self.initialized_endpoints:
            router.add_api_route(
                "/libp2p/stop",
                self.stop_peer_async,
                methods=["POST"],
                response_model=StartStopResponse,
                summary="Stop peer",
                description="Stop the libp2p peer if it's running",
                tags=["libp2p"],
            )
            self.initialized_endpoints.add("/libp2p/stop")

        # Add DHT operation endpoints
        if "/libp2p/dht/find_peer" not in self.initialized_endpoints:
            router.add_api_route(
                "/libp2p/dht/find_peer",
                self.dht_find_peer_async,
                methods=["POST"],
                summary="Find peer in DHT",
                description="Find a peer's addresses using the DHT",
                tags=["libp2p-dht"],
            )
            self.initialized_endpoints.add("/libp2p/dht/find_peer")

        if "/libp2p/dht/provide" not in self.initialized_endpoints:
            router.add_api_route(
                "/libp2p/dht/provide",
                self.dht_provide_async,
                methods=["POST"],
                summary="Provide content in DHT",
                description="Announce to the DHT that we are providing a CID",
                tags=["libp2p-dht"],
            )
            self.initialized_endpoints.add("/libp2p/dht/provide")

        if "/libp2p/dht/find_providers" not in self.initialized_endpoints:
            router.add_api_route(
                "/libp2p/dht/find_providers",
                self.dht_find_providers_async,
                methods=["POST"],
                summary="Find providers in DHT",
                description="Find providers for a CID using the DHT",
                tags=["libp2p-dht"],
            )
            self.initialized_endpoints.add("/libp2p/dht/find_providers")

        # Add PubSub operation endpoints
        if "/libp2p/pubsub/publish" not in self.initialized_endpoints:
            router.add_api_route(
                "/libp2p/pubsub/publish",
                self.pubsub_publish_async,
                methods=["POST"],
                summary="Publish message",
                description="Publish a message to a PubSub topic",
                tags=["libp2p-pubsub"],
            )
            self.initialized_endpoints.add("/libp2p/pubsub/publish")

        if "/libp2p/pubsub/subscribe" not in self.initialized_endpoints:
            router.add_api_route(
                "/libp2p/pubsub/subscribe",
                self.pubsub_subscribe_async,
                methods=["POST"],
                summary="Subscribe to topic",
                description="Subscribe to a PubSub topic",
                tags=["libp2p-pubsub"],
            )
            self.initialized_endpoints.add("/libp2p/pubsub/subscribe")

        if "/libp2p/pubsub/unsubscribe" not in self.initialized_endpoints:
            router.add_api_route(
                "/libp2p/pubsub/unsubscribe",
                self.pubsub_unsubscribe_async,
                methods=["POST"],
                summary="Unsubscribe from topic",
                description="Unsubscribe from a PubSub topic",
                tags=["libp2p-pubsub"],
            )
            self.initialized_endpoints.add("/libp2p/pubsub/unsubscribe")

        if "/libp2p/pubsub/topics" not in self.initialized_endpoints:
            router.add_api_route(
                "/libp2p/pubsub/topics",
                self.pubsub_get_topics_async,
                methods=["GET"],
                summary="Get topics",
                description="Get list of subscribed PubSub topics",
                tags=["libp2p-pubsub"],
            )
            self.initialized_endpoints.add("/libp2p/pubsub/topics")

        if "/libp2p/pubsub/peers" not in self.initialized_endpoints:
            router.add_api_route(
                "/libp2p/pubsub/peers",
                self.pubsub_get_peers_async,
                methods=["GET"],
                summary="Get pubsub peers",
                description="Get list of peers in the PubSub mesh",
                tags=["libp2p-pubsub"],
            )
            self.initialized_endpoints.add("/libp2p/pubsub/peers")

        # Add message handler management endpoints
        if "/libp2p/handlers/register" not in self.initialized_endpoints:
            router.add_api_route(
                "/libp2p/handlers/register",
                self.register_message_handler_async,
                methods=["POST"],
                summary="Register handler",
                description="Register a new protocol message handler",
                tags=["libp2p-handlers"],
            )
            self.initialized_endpoints.add("/libp2p/handlers/register")

        if "/libp2p/handlers/unregister" not in self.initialized_endpoints:
            router.add_api_route(
                "/libp2p/handlers/unregister",
                self.unregister_message_handler_async,
                methods=["POST"],
                summary="Unregister handler",
                description="Unregister a protocol message handler",
                tags=["libp2p-handlers"],
            )
            self.initialized_endpoints.add("/libp2p/handlers/unregister")

        if "/libp2p/handlers/list" not in self.initialized_endpoints:
            router.add_api_route(
                "/libp2p/handlers/list",
                self.list_message_handlers_async,
                methods=["GET"],
                summary="List handlers",
                description="List all registered protocol message handlers",
                tags=["libp2p-handlers"],
            )
            self.initialized_endpoints.add("/libp2p/handlers/list")

        logger.info(
            f"Registered libp2p controller routes with AnyIO support: {len(self.initialized_endpoints)} endpoints"
        )
