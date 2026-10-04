"""
MCP Server integration for the Unified Storage Manager.

This module integrates the Unified Storage Manager into the MCP server,
providing server endpoints for multi-backend storage operations.
"""

import logging
import json
import os
from typing import Dict, List, Any, Optional

# Configure logger
logger = logging.getLogger(__name__)


class StorageManagerIntegration:
    """
    Integration class that connects the Unified Storage Manager to the MCP server.

    This class serves as the bridge between the MCP server framework and the
    Unified Storage Manager components.
    """
    def __init__(self, server_instance = None, config_path = None):
        """
        Initialize storage manager integration.

        Args:
            server_instance: MCP server instance
            config_path: Path to configuration file
        """
        self.server = server_instance
        self.config = self._load_config(config_path)
        self.resources = {}
        self.metadata = {}
        self.storage_manager = None
        self.notification_manager = None
        self.notification_service = None
        self.websocket_notifier = None
        self.performance_optimizer = None

        # Initialize components
        self._init_components()

        logger.info("Storage Manager Integration initialized")

    def _load_config(self, config_path = None) -> Dict[str, Any]:
        """
        Load configuration from file.

        Args:
            config_path: Path to configuration file

        Returns:
            Configuration dictionary
        """
        config = {
            "storage_registry_path": os.path.join("data", "storage_registry.json"),
            "enable_notifications": True,
            "enable_performance_optimization": True,
            "max_notification_history": 1000,
            "backends": {
                "ipfs": {"enabled": True},
                "s3": {"enabled": True, "default_bucket": "mcp-storage"},
                "storacha": {"enabled": True},
                "filecoin": {
                    "enabled": True,
                    "default_miner": None,
                    "replication_count": 1,
                    "verify_deals": True,
                },
            },
        }

        # Load from file if provided
        if config_path:
            try:
                with open(config_path, "r") as f:
                    loaded_config = json.load(f)

                    # Merge loaded config into default config
                    for key, value in loaded_config.items():
                        if key == "backends" and isinstance(value, dict):
                            # Merge backend configs
                            for backend, backend_config in value.items():
                                if backend in config["backends"]:
                                    config["backends"][backend].update(backend_config)
                                else:
                                    config["backends"][backend] = backend_config
                        else:
                            config[key] = value

                logger.info(f"Loaded configuration from {config_path}")
            except Exception as e:
                logger.error(f"Failed to load configuration from {config_path}: {e}")

        return config

    def _init_components(self):
        """Initialize storage manager components."""
        # Import required components
        try:
            from ipfs_kit_py.mcp.storage_manager import UnifiedStorageManager
            from ipfs_kit_py.mcp.storage_manager.performance import PerformanceOptimizer
            from ipfs_kit_py.mcp.storage_manager.notifications import (
                NotificationManager,
                StorageNotificationService,
                WebSocketStorageNotifier)
            from ipfs_kit_py.mcp.storage_manager.api import UnifiedStorageAPI

            # Initialize performance optimizer if enabled
            if self.config.get("enable_performance_optimization", True):
                self.performance_optimizer = PerformanceOptimizer()
                logger.info("Performance optimizer initialized")

                # Add optimizer to metadata
                self.metadata["performance_optimizer"] = self.performance_optimizer

            # Initialize notification system if enabled
            if self.config.get("enable_notifications", True):
                max_history = self.config.get("max_notification_history", 1000)
                self.notification_manager = NotificationManager(max_history=max_history)
                self.notification_service = StorageNotificationService(self.notification_manager)
                self.websocket_notifier = WebSocketStorageNotifier(self.notification_manager)
                logger.info("Notification system initialized")

                # Add notification service to metadata
                self.metadata["notification_service"] = self.notification_service

            # Initialize storage manager
            self.metadata["storage_registry_path"] = self.config.get("storage_registry_path")
            self.metadata["backends"] = self.config.get("backends", {})

            self.storage_manager = UnifiedStorageManager(
                resources=self.resources, metadata=self.metadata
            )
            logger.info("Unified Storage Manager initialized")

            # Initialize API handler
            self.api_handler = UnifiedStorageAPI(self.storage_manager)
            logger.info("Storage API handler initialized")

            # Register routes with server if available
            if self.server:
                self._register_routes()
                logger.info("Storage routes registered with server")

        except Exception as e:
            logger.error(f"Failed to initialize storage manager components: {e}")
            raise

    def _register_routes(self):
        """Register routes with MCP server."""
        # Check if server has a route registration method
        if not hasattr(self.server, "register_handler") or not callable(
            self.server.register_handler
        ):
            logger.warning(
                "Server does not have register_handler method, skipping route registration"
            )
            return

        # Register REST API routes
        self.server.register_handler("GET", "/api/v0/storage(.*)", self._handle_rest_api)
        self.server.register_handler("POST", "/api/v0/storage(.*)", self._handle_rest_api)
        self.server.register_handler("PUT", "/api/v0/storage(.*)", self._handle_rest_api)
        self.server.register_handler("DELETE", "/api/v0/storage(.*)", self._handle_rest_api)

        # Register WebSocket route if notifications are enabled
        if self.websocket_notifier:
            self.server.register_websocket_handler("/ws/storage", self._handle_websocket)

    async def _handle_rest_api(self, request):
        """
        Handle REST API requests.

        Args:
            request: HTTP request object

        Returns:
            HTTP response
        """
        try:
            # Extract request details
            method = request.method
            path = request.path.replace("/api/v0", "")
            params = dict(request.query_params)

            # Handle file uploads (multipart form data)
            if request.headers.get("content-type", "").startswith("multipart/form-data"):
                form = await request.form()

                # Extract file data
                file_field = next((field for field in form if hasattr(form[field], "read")), None)
                if file_field:
                    file_obj = form[file_field]
                    data = await file_obj.read()

                    # Add file metadata to params
                    params["file_name"] = getattr(file_obj, "filename", "")
                    params["content_type"] = getattr(file_obj, "content_type", "")
                else:
                    # No file found
                    data = None

                # Extract other form values as params
                for field in form:
                    if not hasattr(form[field], "read"):
                        params[field] = form[field]
            else:
                # Regular request body
                data = await request.body() if method in ["POST", "PUT"] else None

            # Handle API request
            result = self.api_handler.handle_request(method, path, params, data)

            # Extract status code
            status_code = result.pop("status_code", 200)

            # Convert to JSON response
            return self.server.create_response(status_code, result)

        except Exception as e:
            logger.exception(f"Error handling storage API request: {e}")
            return self.server.create_response(
                500, {"success": False, "error": f"Internal server error: {str(e)}"}
            )

    async def _handle_websocket(self, websocket):
        """
        Handle WebSocket connections.

        Args:
            websocket: WebSocket connection object
        """
        client_id = None

        try:
            # Accept connection
            client_id = await self.websocket_notifier.on_connect(websocket)

            # Handle messages
            async for message in websocket.iter_json():
                await self.websocket_notifier.on_message(websocket, client_id, message)

        except Exception as e:
            logger.error(f"Error in WebSocket connection: {e}")
        finally:
            # Handle disconnection
            if client_id:
                await self.websocket_notifier.on_disconnect(client_id)

    def shutdown(self):
        """Cleanup resources and shutdown components."""
        # Clean up storage manager
        if self.storage_manager:
            self.storage_manager.cleanup()

        logger.info("Storage Manager Integration shutdown complete")


class MCPStorageService:
    """
    Service-oriented wrapper for the Unified Storage Manager.

    This class provides a simplified interface for other MCP services to interact
    with the storage system without dealing with the full API.
    """
    def __init___v2(self, storage_manager):
        """
        Initialize MCP storage service.

        Args:
            storage_manager: Unified Storage Manager instance
        """
        self.storage_manager = storage_manager

    def store_content(
    self,
    data: bytes
        preferred_backend: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        synchronous: bool = True,
    ) -> str:
        """
        Store content in the storage system.

        Args:
            data: Content data
            preferred_backend: Preferred backend (optional)
            metadata: Additional metadata
            synchronous: Whether to wait for operation to complete

        Returns:
            Content ID
        """
        result = self.storage_manager.store(
            data=data, backend_preference=preferred_backend, metadata=metadata or {}
        )

        if not result.get("success", False):
            raise ValueError(f"Failed to store content: {result.get('error')}")

        return result["content_id"]

    def retrieve_content(self, content_id: str, preferred_backend: Optional[str] = None) -> bytes:
        """
        Retrieve content from the storage system.

        Args:
            content_id: Content ID
            preferred_backend: Preferred backend (optional)

        Returns:
            Content data
        """
        result = self.storage_manager.retrieve(
            content_id=content_id, backend_preference=preferred_backend
        )

        if not result.get("success", False):
            raise ValueError(f"Failed to retrieve content: {result.get('error')}")

        return result["data"]

    def delete_content(self, content_id: str, backend: Optional[str] = None) -> bool:
        """
        Delete content from the storage system.

        Args:
            content_id: Content ID
            backend: Backend to delete from (all if None)

        Returns:
            True if successful
        """
        result = self.storage_manager.delete(content_id=content_id, backend=backend)

        return result.get("success", False)

    def get_content_info(self, content_id: str) -> Dict[str, Any]:
        """
        Get information about content.

        Args:
            content_id: Content ID

        Returns:
            Content information
        """
        result = self.storage_manager.get_content_info(content_id)

        if not result.get("success", False):
            raise ValueError(f"Failed to get content info: {result.get('error')}")

        return result["content_reference"]

    def replicate_content(self, content_id: str, target_backend: str) -> bool:
        """
        Replicate content to another backend.

        Args:
            content_id: Content ID
            target_backend: Target backend

        Returns:
            True if successful
        """
        result = self.storage_manager.replicate(
            content_id=content_id, target_backend=target_backend
        )

        return result.get("success", False)

    def update_metadata(self, content_id: str, metadata: Dict[str, Any]) -> bool:
        """
        Update content metadata.

        Args:
            content_id: Content ID
            metadata: New metadata to set or update

        Returns:
            True if successful
        """
        result = self.storage_manager.update_metadata(content_id=content_id, metadata=metadata)

        return result.get("success", False)

    def list_available_backends(self) -> List[Dict[str, Any]]:
        """
        Get list of available backends.

        Returns:
            List of backend information
        """
        return self.storage_manager.get_backends()

    def get_storage_statistics(self) -> Dict[str, Any]:
        """
        Get storage statistics.

        Returns:
            Storage statistics
        """
        return self.storage_manager.get_statistics()
