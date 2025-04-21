"""
MCP Discovery Controller for the MCP server.

This controller exposes MCP server discovery API endpoints allowing servers to discover
each other, share capabilities, and collaborate on handling requests.
"""

import logging
import time
import uuid
import asyncio
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from ipfs_kit_py.mcp.models.mcp_discovery_model import MCPDiscoveryModel

# Configure logger
logger = logging.getLogger(__name__)


# Define Pydantic models for requests and responses
class MCPDiscoveryResponse(BaseModel):
    """
import sys
import os
# Add the parent directory to sys.path to allow importing mcp_error_handling
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
import mcp_error_handling

Base response model for MCP discovery operations."""
    success: bool = Field(..., description="Whether the operation was successful")
    operation_id: Optional[str] = Field(None, description="Unique identifier for this operation")
    timestamp: float = Field(..., description="Operation timestamp")


class ServerInfoResponse(MCPDiscoveryResponse):
    """Response model for server info."""
    server_info: Dict[str, Any] = Field(..., description="Server information")
    is_local: bool = Field(..., description="Whether this is the local server")


class ServerListResponse(MCPDiscoveryResponse):
    """Response model for server list."""
    servers: List[Dict[str, Any]] = Field(default=[], description="List of servers")
    server_count: int = Field(0, description="Number of servers")


class AnnounceRequest(BaseModel):
    """Request model for announcing a server."""
    additional_metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional metadata to include"
    )


class RegisterServerRequest(BaseModel):
    """Request model for registering a server."""
    server_info: Dict[str, Any] = Field(..., description="Server information")


class UpdateServerRequest(BaseModel):
    """Request model for updating server properties."""
    role: Optional[str] = Field(None, description="Server role")
    features: Optional[List[str]] = Field(None, description="Server features")
    api_endpoint: Optional[str] = Field(None, description="HTTP API endpoint")
    websocket_endpoint: Optional[str] = Field(None, description="WebSocket endpoint")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class DiscoverServersRequest(BaseModel):
    """Request model for discovering servers."""
    methods: Optional[List[str]] = Field(None, description="Discovery methods to use")
    compatible_only: bool = Field(True, description="Only return compatible servers")
    feature_requirements: Optional[List[str]] = Field(None, description="Required features")


class DispatchTaskRequest(BaseModel):
    """Request model for dispatching tasks."""
    task_type: str = Field(..., description="Type of task to dispatch")
    task_data: Any = Field(..., description="Data for the task")
    required_features: Optional[List[str]] = Field(
        None, description="Required features for the task"
    )
    preferred_server_id: Optional[str] = Field(None, description="Preferred server ID")


class MCPDiscoveryController:
    """
    Controller for MCP server discovery.

    Exposes HTTP API endpoints for MCP server discovery and collaboration.
    """
    def __init__(self, discovery_model: MCPDiscoveryModel):
        """
        Initialize the MCP discovery controller.

        Args:
            discovery_model: MCP Discovery model
        """
        self.discovery_model = discovery_model
        self.is_shutting_down = False  # Flag to track shutdown state
        logger.info("MCP Discovery Controller initialized")

    def register_routes(self, router: APIRouter):
        """
        Register routes with a FastAPI router.

        Args:
            router: FastAPI router to register routes with
        """
        # Get local server info
        router.add_api_route(
            "/discovery/server",
            self.get_local_server_info,
            methods=["GET"],
            response_model=ServerInfoResponse,
            summary="Get local server info",
            description="Get information about this MCP server",
        )

        # Update local server info
        router.add_api_route(
            "/discovery/server",
            self.update_local_server,
            methods=["PUT"],
            response_model=ServerInfoResponse,
            summary="Update local server info",
            description="Update information about this MCP server",
        )

        # Announce server
        router.add_api_route(
            "/discovery/announce",
            self.announce_server,
            methods=["POST"],
            response_model=MCPDiscoveryResponse,
            summary="Announce server",
            description="Announce this server to the network",
        )

        # Discover servers
        router.add_api_route(
            "/discovery/servers",
            self.discover_servers,
            methods=["POST"],
            response_model=ServerListResponse,
            summary="Discover servers",
            description="Discover MCP servers in the network",
        )

        # Get known servers
        router.add_api_route(
            "/discovery/servers",
            self.get_known_servers,
            methods=["GET"],
            response_model=ServerListResponse,
            summary="Get known servers",
            description="Get list of known MCP servers",
        )

        # Get compatible servers
        router.add_api_route(
            "/discovery/servers/compatible",
            self.get_compatible_servers,
            methods=["GET"],
            response_model=ServerListResponse,
            summary="Get compatible servers",
            description="Get list of MCP servers with compatible feature sets",
        )

        # Get server by ID
        router.add_api_route(
            "/discovery/servers/{server_id}",
            self.get_server_by_id,
            methods=["GET"],
            response_model=ServerInfoResponse,
            summary="Get server by ID",
            description="Get information about a specific MCP server",
        )

        # Register a server manually
        router.add_api_route(
            "/discovery/servers/register",
            self.register_server,
            methods=["POST"],
            response_model=MCPDiscoveryResponse,
            summary="Register server",
            description="Manually register an MCP server",
        )

        # Remove a server
        router.add_api_route(
            "/discovery/servers/{server_id}",
            self.remove_server,
            methods=["DELETE"],
            response_model=MCPDiscoveryResponse,
            summary="Remove server",
            description="Remove an MCP server from known servers",
        )

        # Clean stale servers
        router.add_api_route(
            "/discovery/servers/clean",
            self.clean_stale_servers,
            methods=["POST"],
            response_model=MCPDiscoveryResponse,
            summary="Clean stale servers",
            description="Remove servers that haven't been seen for a while",
        )

        # Check server health
        router.add_api_route(
            "/discovery/servers/{server_id}/health",
            self.check_server_health,
            methods=["GET"],
            response_model=MCPDiscoveryResponse,
            summary="Check server health",
            description="Check health status of a specific MCP server",
        )

        # Dispatch task
        router.add_api_route(
            "/discovery/tasks/dispatch",
            self.dispatch_task,
            methods=["POST"],
            response_model=MCPDiscoveryResponse,
            summary="Dispatch task",
            description="Dispatch a task to a compatible server",
        )

        # Get statistics
        router.add_api_route(
            "/discovery/stats",
            self.get_stats,
            methods=["GET"],
            response_model=MCPDiscoveryResponse,
            summary="Get statistics",
            description="Get statistics about server discovery",
        )

        # Reset
        router.add_api_route(
            "/discovery/reset",
            self.reset,
            methods=["POST"],
            response_model=MCPDiscoveryResponse,
            summary="Reset discovery model",
            description="Reset the discovery model, clearing all state",
        )

        # Add WebSocket endpoint for server-to-server communication
        # This would require a WebSocket endpoint implementation here
        # For now, we'll just note that we would add it

        logger.info("MCP Discovery Controller routes registered")

    async def get_local_server_info(self) -> Dict[str, Any]:
        """
        Get information about the local server.

        Returns:
            Dict with local server information
        """
        # Get server info
        server_info = self.discovery_model.get_server_info(self.discovery_model.server_id)

        # Convert to response format
        return {
            "success": server_info["success"],
            "operation_id": str(uuid.uuid4()),
            "timestamp": time.time(),
            "server_info": server_info["server_info"],
            "is_local": True,
        }

    async def update_local_server(self, request: UpdateServerRequest) -> Dict[str, Any]:
        """
        Update information about the local server.

        Args:
            request: Update request with new server properties

        Returns:
            Dict with updated server information
        """
        # Prepare updates
        updates = {}

        if request.role:
            updates["role"] = request.role

        if request.features:
            updates["features"] = request.features

        if request.api_endpoint:
            updates["api_endpoint"] = request.api_endpoint

        if request.websocket_endpoint:
            updates["websocket_endpoint"] = request.websocket_endpoint

        if request.metadata:
            updates["metadata"] = request.metadata

        # Update server info
        self.discovery_model.update_server_info(**updates)

        # Get updated server info
        server_info = self.discovery_model.get_server_info(self.discovery_model.server_id)

        # Convert to response format
        return {
            "success": server_info["success"],
            "operation_id": str(uuid.uuid4()),
            "timestamp": time.time(),
            "server_info": server_info["server_info"],
            "is_local": True,
        }

    async def announce_server(self, request: Optional["AnnounceRequest"] = None) -> Dict[str, Any]:
        """
        Announce this server to the network.

        Args:
            request: Optional announcement request with additional metadata

        Returns:
            Dict with announcement status
        """
        # Update metadata if provided
        if request and request.additional_metadata:
            self.discovery_model.update_server_info(metadata=request.additional_metadata)

        # Announce server
        announcement_result = self.discovery_model.announce_server()

        # Convert to response format
        return {
            "success": announcement_result["success"],
            "operation_id": str(uuid.uuid4()),
            "timestamp": time.time(),
            "announcement_channels": announcement_result.get("announcement_channels", []),
        }

    async def discover_servers(self, request: DiscoverServersRequest) -> Dict[str, Any]:
        """
        Discover MCP servers in the network.

        Args:
            request: Discovery request with options

        Returns:
            Dict with discovered servers
        """
        # Discover servers
        discovery_result = self.discovery_model.discover_servers(
            methods=request.methods,
            compatible_only=request.compatible_only,
            feature_requirements=request.feature_requirements,
        )

        # Convert to response format
        return {
            "success": discovery_result["success"],
            "operation_id": str(uuid.uuid4()),
            "timestamp": time.time(),
            "servers": discovery_result.get("servers", []),
            "server_count": discovery_result.get("server_count", 0),
            "new_servers": discovery_result.get("new_servers", 0),
        }

    async def get_known_servers(
        self, filter_role: Optional[str] = None, filter_features: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get list of known MCP servers.

        Args:
            filter_role: Filter by server role
            filter_features: Filter by required features (comma-separated)

        Returns:
            Dict with known servers
        """
        # Parse features filter
        feature_requirements = None
        if filter_features:
            feature_requirements = filter_features.split(",")

        # Add this as a wrapper around the model's discover_servers method
        # but using only the "manual" method to return already known servers
        discovery_result = self.discovery_model.discover_servers(
            methods=["manual"],
            compatible_only=False,  # Don't filter by compatibility
            feature_requirements=feature_requirements,
        )

        # Filter by role if specified
        if filter_role and discovery_result.get("success", False):
            filtered_servers = []
            for server in discovery_result.get("servers", []):
                if server.get("role") == filter_role:
                    filtered_servers.append(server)

            discovery_result["servers"] = filtered_servers
            discovery_result["server_count"] = len(filtered_servers)

        # Convert to response format
        return {
            "success": discovery_result["success"],
            "operation_id": str(uuid.uuid4()),
            "timestamp": time.time(),
            "servers": discovery_result.get("servers", []),
            "server_count": discovery_result.get("server_count", 0),
        }

    async def get_compatible_servers(
        self, feature_requirements: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get list of MCP servers with compatible feature sets.

        Args:
            feature_requirements: Required features (comma-separated)

        Returns:
            Dict with compatible servers
        """
        # Parse features filter
        feature_list = None
        if feature_requirements:
            feature_list = feature_requirements.split(",")

        # Get compatible servers
        compatible_result = self.discovery_model.get_compatible_servers(
            feature_requirements=feature_list
        )

        # Convert to response format
        return {
            "success": compatible_result["success"],
            "operation_id": str(uuid.uuid4()),
            "timestamp": time.time(),
            "servers": compatible_result.get("servers", []),
            "server_count": compatible_result.get("server_count", 0),
        }

    async def get_server_by_id(self, server_id: str) -> Dict[str, Any]:
        """
        Get information about a specific MCP server.

        Args:
            server_id: ID of the server to get info for

        Returns:
            Dict with server information
        """
        # Get server info
        server_info = self.discovery_model.get_server_info(server_id)

        # If server not found, raise 404
        if not server_info["success"]:
            mcp_error_handling.raise_http_exception(
        code="CONTENT_NOT_FOUND",
        message_override=f"Server not found: {server_id}",
        endpoint="/api/v0/mcp_discovery",
        doc_category="api"
    )

        # Convert to response format
        return {
            "success": True,
            "operation_id": str(uuid.uuid4()),
            "timestamp": time.time(),
            "server_info": server_info["server_info"],
            "is_local": server_info.get("is_local", False),
        }

    async def register_server(self, request: RegisterServerRequest) -> Dict[str, Any]:
        """
        Manually register an MCP server.

        Args:
            request: Registration request with server info

        Returns:
            Dict with registration status
        """
        # Register server
        register_result = self.discovery_model.register_server(request.server_info)

        # Convert to response format
        return {
            "success": register_result["success"],
            "operation_id": str(uuid.uuid4()),
            "timestamp": time.time(),
            "server_id": register_result.get("server_id"),
            "is_new": register_result.get("is_new", False),
        }

    async def remove_server(self, server_id: str) -> Dict[str, Any]:
        """
        Remove an MCP server from known servers.

        Args:
            server_id: ID of the server to remove

        Returns:
            Dict with removal status
        """
        # Remove server
        remove_result = self.discovery_model.remove_server(server_id)

        # If server not found, raise 404
        if (
            not remove_result["success"]
            and remove_result.get("error") == f"Server not found: {server_id}"
        ):
            mcp_error_handling.raise_http_exception(
        code="CONTENT_NOT_FOUND",
        message_override=f"Server not found: {server_id}",
        endpoint="/api/v0/mcp_discovery",
        doc_category="api"
    )

        # Convert to response format
        return {
            "success": remove_result["success"],
            "operation_id": str(uuid.uuid4()),
            "timestamp": time.time(),
            "server_id": server_id,
        }

    async def clean_stale_servers(self, max_age_seconds: int = 3600) -> Dict[str, Any]:
        """
        Remove servers that haven't been seen for a while.

        Args:
            max_age_seconds: Maximum age in seconds before a server is considered stale

        Returns:
            Dict with cleanup status
        """
        # Clean stale servers
        clean_result = self.discovery_model.clean_stale_servers(max_age_seconds=max_age_seconds)

        # Convert to response format
        return {
            "success": clean_result["success"],
            "operation_id": str(uuid.uuid4()),
            "timestamp": time.time(),
            "removed_servers": clean_result.get("removed_servers", []),
            "removed_count": clean_result.get("removed_count", 0),
        }

    async def check_server_health(self, server_id: str) -> Dict[str, Any]:
        """
        Check health status of a specific MCP server.

        Args:
            server_id: ID of the server to check

        Returns:
            Dict with health status
        """
        # Check server health
        health_result = self.discovery_model.check_server_health(server_id)

        # If server not found, raise 404
        if not health_result["success"] and health_result.get("error", "").startswith(
            "Server not found"
        ):
            mcp_error_handling.raise_http_exception(
        code="CONTENT_NOT_FOUND",
        message_override=f"Server not found: {server_id}",
        endpoint="/api/v0/mcp_discovery",
        doc_category="api"
    )

        # Convert to response format
        return {
            "success": health_result["success"],
            "operation_id": str(uuid.uuid4()),
            "timestamp": time.time(),
            "server_id": server_id,
            "healthy": health_result.get("healthy", False),
            "health_source": health_result.get("health_source"),
        }

    async def dispatch_task(self, request: DispatchTaskRequest) -> Dict[str, Any]:
        """
        Dispatch a task to a compatible server.

        Args:
            request: Task dispatch request

        Returns:
            Dict with dispatch status and results
        """
        # Dispatch task
        dispatch_result = self.discovery_model.dispatch_task(
            task_type=request.task_type,
            task_data=request.task_data,
            required_features=request.required_features,
            preferred_server_id=request.preferred_server_id,
        )

        # Convert to response format
        return {
            "success": dispatch_result["success"],
            "operation_id": str(uuid.uuid4()),
            "timestamp": time.time(),
            "task_type": request.task_type,
            "server_id": dispatch_result.get("server_id"),
            "processed_locally": dispatch_result.get("processed_locally", False),
            "task_result": dispatch_result.get("task_result"),
        }

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about server discovery.

        Returns:
            Dict with statistics
        """
        # Get stats
        stats_result = self.discovery_model.get_stats()

        # Convert to response format
        return {
            "success": stats_result["success"],
            "operation_id": str(uuid.uuid4()),
            "timestamp": time.time(),
            "stats": stats_result.get("stats", {}),
        }

    async def reset(self) -> Dict[str, Any]:
        """
        Reset the discovery model, clearing all state.

        Returns:
            Dict with reset status
        """
        # Reset model
        reset_result = self.discovery_model.reset()

        # Convert to response format
        return {
            "success": reset_result["success"],
            "operation_id": str(uuid.uuid4()),
            "timestamp": time.time(),
        }

    async def shutdown(self):
        """
        Safely shut down the MCP Discovery Controller.

        This method ensures proper cleanup of discovery-related resources.
        """
        logger.info("MCP Discovery Controller shutdown initiated")

        # Signal that we're shutting down to prevent new operations
        self.is_shutting_down = True

        # Track any errors during shutdown
        errors = []

        # Clean up discovery model resources
        try:
            # Check for various shutdown methods
            if hasattr(self.discovery_model, "shutdown"):
                await self.discovery_model.shutdown()
            elif hasattr(self.discovery_model, "close"):
                await self.discovery_model.close()
            elif hasattr(self.discovery_model, "async_shutdown"):
                await self.discovery_model.async_shutdown()
            elif hasattr(self.discovery_model, "cancel_all_tasks"):
                await self.discovery_model.cancel_all_tasks()

            # For sync methods, we need to handle differently
            elif hasattr(self.discovery_model, "sync_shutdown"):
                # Use anyio to run in a thread if available
                try:
                    import anyio
                    import sniffio

                    sniffio.current_async_library()
                    await anyio.to_thread.run_sync(self.discovery_model.sync_shutdown)
                except (ImportError, ModuleNotFoundError):
                    # Fallback to running directly (might block)
                    try:
                        self.discovery_model.sync_shutdown()
                    except Exception as e:
                        logger.error(f"Error during model sync_shutdown direct call: {e}")
                        errors.append(str(e))
                except Exception as e:
                    logger.error(f"Error during model sync_shutdown via anyio: {e}")
                    errors.append(str(e))

            # Additional model-specific cleanup
            if hasattr(self.discovery_model, "reset"):
                # Reset the model to clear state
                try:
                    self.discovery_model.reset()
                except Exception as e:
                    logger.error(f"Error resetting discovery model: {e}")
                    errors.append(str(e))

        except Exception as e:
            logger.error(f"Error shutting down discovery model: {e}")
            errors.append(str(e))

        # Report shutdown completion
        if errors:
            logger.warning(f"MCP Discovery Controller shutdown completed with {len(errors)} errors")
        else:
            logger.info("MCP Discovery Controller shutdown completed successfully")

    def sync_shutdown(self):
        """
        Synchronous version of shutdown.

        This can be called in contexts where async is not available.
        """
        logger.info("MCP Discovery Controller sync_shutdown initiated")

        # Set shutdown flag
        self.is_shutting_down = True

        # Track any errors during shutdown
        errors = []

        # Clean up discovery model resources
        try:
            # Check for sync shutdown methods first
            if hasattr(self.discovery_model, "sync_shutdown"):
                self.discovery_model.sync_shutdown()
            elif hasattr(self.discovery_model, "close"):
                # Try direct call for sync methods
                if not asyncio.iscoroutinefunction(self.discovery_model.close):
                    self.discovery_model.close()
            elif hasattr(self.discovery_model, "shutdown"):
                # Try direct call for sync methods
                if not asyncio.iscoroutinefunction(self.discovery_model.shutdown):
                    self.discovery_model.shutdown()

            # For async methods in a sync context, we have limited options
            # The best we can do is log that we can't properly close
            elif hasattr(self.discovery_model, "shutdown") or hasattr(
                self.discovery_model, "async_shutdown"
            ):
                logger.warning("Cannot properly call async shutdown methods in sync context")

            # Additional model-specific cleanup
            if hasattr(self.discovery_model, "reset"):
                # Reset the model to clear state
                try:
                    self.discovery_model.reset()
                except Exception as e:
                    logger.error(f"Error resetting discovery model: {e}")
                    errors.append(str(e))

        except Exception as e:
            logger.error(f"Error during sync shutdown of discovery model: {e}")
            errors.append(str(e))

        # Report shutdown completion
        if errors:
            logger.warning(
                f"MCP Discovery Controller sync_shutdown completed with {len(errors)} errors"
            )
        else:
            logger.info("MCP Discovery Controller sync_shutdown completed successfully")
