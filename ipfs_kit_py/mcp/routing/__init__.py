"""
Optimized Data Routing Integration Module

This module provides integration for the optimized data routing system:
- Initializes the data router
- Registers API endpoints
- Sets up metrics collection
- Provides utilities for interacting with the routing system

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).
"""

import os
import logging
import asyncio
from typing import Optional, Dict, Any

from fastapi import FastAPI

from ipfs_kit_py.mcp.routing.data_router import DataRouter, create_data_router
from ipfs_kit_py.mcp.routing.router import create_routing_router

# Configure logging
logger = logging.getLogger(__name__)


class RoutingService:
    """
    Service for managing the optimized data routing system.
    
    This class integrates the data router with the MCP server and
    provides utilities for interacting with the routing system.
    """
    
    def __init__(
        self, 
        app: FastAPI, 
        backend_manager=None, 
        config_path: Optional[str] = None,
        auto_metrics: bool = True
    ):
        """
        Initialize the routing service.
        
        Args:
            app: FastAPI application
            backend_manager: Storage backend manager
            config_path: Path to configuration file
            auto_metrics: Whether to automatically collect metrics
        """
        # Create data router
        self.data_router = create_data_router(backend_manager, config_path)
        
        # Register API endpoints
        create_routing_router(app, backend_manager, self.data_router)
        
        # Store configuration
        self.backend_manager = backend_manager
        self.auto_metrics = auto_metrics
        self.metrics_interval = 3600  # 1 hour
        
        # Start metrics collection if auto_metrics is enabled
        self.metrics_task = None
        if auto_metrics:
            self.start_metrics_collection()
        
        logger.info("Routing service initialized")
    
    def start_metrics_collection(self, interval: int = 3600) -> None:
        """
        Start automatic collection of backend metrics.
        
        Args:
            interval: Collection interval in seconds
        """
        self.metrics_interval = interval
        
        # Start collection task
        if not self.metrics_task:
            self.metrics_task = asyncio.create_task(self._metrics_collection_loop())
            logger.info(f"Started automatic metrics collection (interval: {interval}s)")
    
    def stop_metrics_collection(self) -> None:
        """Stop automatic collection of backend metrics."""
        if self.metrics_task:
            self.metrics_task.cancel()
            self.metrics_task = None
            logger.info("Stopped automatic metrics collection")
    
    async def _metrics_collection_loop(self) -> None:
        """Background task to collect backend metrics periodically."""
        while True:
            try:
                # Collect metrics
                await self.data_router.collect_backend_metrics()
                logger.debug("Collected backend metrics")
            except Exception as e:
                logger.error(f"Error collecting backend metrics: {e}")
            
            # Sleep until next collection
            await asyncio.sleep(self.metrics_interval)
    
    async def route_content(
        self,
        content: bytes,
        metadata: Optional[Dict[str, Any]] = None,
        strategy: Optional[str] = None,
        priority: Optional[str] = None,
        client_location: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Route content to the optimal backend.
        
        Args:
            content: Content to store
            metadata: Optional metadata about the content
            strategy: Optional routing strategy to use
            priority: Optional routing priority
            client_location: Optional client location (lat/lon)
            
        Returns:
            Dict with routing result
        """
        return await self.data_router.route_content(
            content, metadata, strategy, priority, client_location
        )
    
    def analyze_content(
        self,
        content: bytes,
        metadata: Optional[Dict[str, Any]] = None,
        client_location: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Analyze how content would be routed.
        
        Args:
            content: Content to analyze
            metadata: Optional metadata about the content
            client_location: Optional client location (lat/lon)
            
        Returns:
            Dict with routing analysis
        """
        return self.data_router.get_routing_analysis(
            content, metadata, client_location
        )
    
    def select_backend(
        self,
        content: bytes,
        metadata: Optional[Dict[str, Any]] = None,
        available_backends: Optional[list] = None,
        strategy: Optional[str] = None,
        priority: Optional[str] = None,
        client_location: Optional[Dict[str, float]] = None
    ) -> str:
        """
        Select the optimal backend for content.
        
        Args:
            content: Content to store
            metadata: Optional metadata about the content
            available_backends: Optional list of available backends
            strategy: Optional routing strategy
            priority: Optional routing priority
            client_location: Optional client location (lat/lon)
            
        Returns:
            Name of the selected backend
        """
        return self.data_router.select_backend(
            content, metadata, available_backends, strategy, priority, client_location
        )


def setup_optimized_routing(
    app: FastAPI, 
    backend_manager=None,
    config_path: Optional[str] = None,
    auto_metrics: bool = True
) -> RoutingService:
    """
    Set up the optimized data routing system.
    
    Args:
        app: FastAPI application
        backend_manager: Storage backend manager
        config_path: Path to configuration file
        auto_metrics: Whether to automatically collect metrics
        
    Returns:
        Routing service instance
    """
    # Create routing service
    routing_service = RoutingService(
        app=app,
        backend_manager=backend_manager,
        config_path=config_path,
        auto_metrics=auto_metrics
    )
    
    # Set up shutdown handler
    @app.on_event("shutdown")
    async def shutdown_routing():
        routing_service.stop_metrics_collection()
    
    logger.info("Optimized data routing system set up")
    return routing_service