"""
MCP Server Integration for Optimized Data Routing

This module provides a compatibility layer between the MCP server and the
core ipfs_kit_py routing module. It allows the MCP server to use the optimized
data routing functionality while maintaining separation of concerns.
"""

import os
import json
import logging
import asyncio
from typing import Dict, List, Any, Optional, Union, Callable
from pathlib import Path
from fastapi import FastAPI, Request

# Import from core ipfs_kit_py routing module instead of local implementation
from ipfs_kit_py.routing.routing_manager import (
    RoutingManager, RoutingManagerSettings, initialize_routing_manager,
    register_routing_manager, get_routing_manager, select_optimal_backend
)
from ipfs_kit_py.routing.optimized_router import RoutingStrategy, ContentCategory
from ipfs_kit_py.routing.data_router import RoutingPriority

# Configure logging
logger = logging.getLogger(__name__)


class RoutingIntegration:
    """
    Integration between MCP server and optimized data routing system.
    
    This class sets up and manages the routing system, providing an easy interface
    for the MCP server to use optimized data routing.
    """
    
    def __init__(
        self,
        app: FastAPI,
        config: Optional[Dict[str, Any]] = None,
        storage_backend_manager = None  # Type hint omitted for circular import avoidance
    ):
        """
        Initialize routing integration.
        
        Args:
            app: FastAPI application
            config: Optional configuration dictionary
            storage_backend_manager: Optional storage backend manager
        """
        self.app = app
        self.config = config or {}
        self.backend_manager = storage_backend_manager
        
        # Extract settings from config
        self.settings = self._create_settings()
        
        # Set up routing manager
        self.routing_manager = None
        
        # Register cleanup handler
        if hasattr(app, "router"):
            @app.on_event("shutdown")
            async def shutdown_routing():
                await self.shutdown()
        
        logger.info("Routing integration initialized")
    
    def _create_settings(self) -> RoutingManagerSettings:
        """
        Create routing manager settings from configuration.
        
        Returns:
            RoutingManagerSettings instance
        """
        # Initialize with defaults
        settings_dict = {
            "enabled": self.config.get("routing_enabled", True),
            "default_strategy": self.config.get("routing_strategy", "hybrid"),
            "default_priority": self.config.get("routing_priority", "balanced"),
            "collect_metrics_on_startup": self.config.get("collect_metrics_on_startup", True),
            "auto_start_background_tasks": self.config.get("auto_start_background_tasks", True),
            "learning_enabled": self.config.get("learning_enabled", True),
            "backends": [],
            "telemetry_interval": self.config.get("telemetry_interval", 300),
            "metrics_retention_days": self.config.get("metrics_retention_days", 7),
        }
        
        # Get config path
        config_dir = self.config.get("config_dir")
        if config_dir:
            settings_dict["config_path"] = os.path.join(config_dir, "routing_config.json")
        
        # Get geo location
        geo_location = self.config.get("geo_location")
        if geo_location:
            settings_dict["geo_location"] = geo_location
        
        # Get optimization weights
        optimization_weights = self.config.get("optimization_weights")
        if optimization_weights:
            settings_dict["optimization_weights"] = optimization_weights
        
        # Create settings
        return RoutingManagerSettings(**settings_dict)
    
    async def initialize(self) -> None:
        """Initialize the routing integration."""
        # Get available backends from backend manager
        if self.backend_manager:
            backends = await self.backend_manager.list_backends()
            self.settings.backends = backends
        
        # Initialize routing manager
        self.routing_manager = await initialize_routing_manager(self.settings)
        
        # Register API endpoints
        register_routing_manager(self.app)
        
        logger.info("Routing integration initialized with %d backends", len(self.settings.backends))
    
    async def select_backend(
        self,
        content: Union[bytes, str, Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
        available_backends: Optional[List[str]] = None,
        strategy: Optional[str] = None,
        priority: Optional[str] = None,
        client_location: Optional[Dict[str, float]] = None
    ) -> str:
        """
        Select the optimal backend for content storage or retrieval.
        
        This is the main entry point for routing decisions.
        
        Args:
            content: Content data, hash, or metadata
            metadata: Additional content metadata
            available_backends: List of available backends
            strategy: Routing strategy
            priority: Routing priority
            client_location: Client geographic location
            
        Returns:
            ID of the selected backend
        """
        return await select_optimal_backend(
            content=content,
            metadata=metadata,
            available_backends=available_backends,
            strategy=strategy,
            priority=priority,
            client_location=client_location
        )
    
    async def record_outcome(
        self,
        backend_id: str,
        content_info: Dict[str, Any],
        success: bool
    ) -> None:
        """
        Record the outcome of a routing decision to improve future decisions.
        
        Args:
            backend_id: Backend that was used
            content_info: Content information
            success: Whether the operation was successful
        """
        routing_manager = get_routing_manager()
        await routing_manager.record_routing_outcome(
            backend_id=backend_id,
            content_info=content_info,
            success=success
        )
    
    async def add_backend(self, backend_id: str) -> None:
        """
        Add a backend to the routing system.
        
        Args:
            backend_id: Backend ID to add
        """
        routing_manager = get_routing_manager()
        routing_manager.register_backend(backend_id)
        
        # Update settings
        if backend_id not in self.settings.backends:
            self.settings.backends.append(backend_id)
    
    async def remove_backend(self, backend_id: str) -> None:
        """
        Remove a backend from the routing system.
        
        Args:
            backend_id: Backend ID to remove
        """
        routing_manager = get_routing_manager()
        routing_manager.unregister_backend(backend_id)
        
        # Update settings
        if backend_id in self.settings.backends:
            self.settings.backends.remove(backend_id)
    
    async def get_insights(self) -> Dict[str, Any]:
        """
        Get insights from the routing system.
        
        Returns:
            Dictionary with routing insights
        """
        routing_manager = get_routing_manager()
        return await routing_manager.get_routing_insights()
    
    async def shutdown(self) -> None:
        """Shutdown the routing integration."""
        routing_manager = get_routing_manager()
        
        # Stop background tasks
        await routing_manager.stop_background_tasks()
        
        # Save configuration if path is set
        if self.settings.config_path:
            routing_manager.save_configuration(self.settings.config_path)
        
        logger.info("Routing integration shutdown")


# Convenience functions
async def setup_routing(
    app: FastAPI,
    config: Optional[Dict[str, Any]] = None,
    storage_backend_manager = None
) -> RoutingIntegration:
    """
    Set up routing integration with MCP server.
    
    Args:
        app: FastAPI application
        config: Optional configuration dictionary
        storage_backend_manager: Optional storage backend manager
        
    Returns:
        RoutingIntegration instance
    """
    # Create integration
    integration = RoutingIntegration(
        app=app,
        config=config,
        storage_backend_manager=storage_backend_manager
    )
    
    # Initialize
    await integration.initialize()
    
    return integration


def add_routing_middleware(app: FastAPI) -> None:
    """
    Add routing middleware to FastAPI application.
    
    This middleware sets up the routing context for each request.
    
    Args:
        app: FastAPI application
    """
    @app.middleware("http")
    async def routing_middleware(request: Request, call_next: Callable):
        # Extract client information for routing
        client_info = {}
        
        # Extract client IP
        client_ip = request.client.host if request.client else None
        if client_ip:
            client_info["ip"] = client_ip
        
        # Extract client location from headers if available
        if "X-Client-Latitude" in request.headers and "X-Client-Longitude" in request.headers:
            try:
                client_info["location"] = {
                    "lat": float(request.headers["X-Client-Latitude"]),
                    "lon": float(request.headers["X-Client-Longitude"])
                }
            except ValueError:
                pass
        
        # Add client info to request state
        request.state.client_info = client_info
        
        # Continue with request
        response = await call_next(request)
        return response
    
    logger.info("Added routing middleware")