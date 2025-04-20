"""
Optimized Data Routing Manager for MCP

This module serves as the main entry point for the optimized data routing system,
integrating all components and providing a clean interface for the MCP server.

It implements the "Optimized Data Routing" component from the MCP roadmap:
- Content-aware backend selection
- Cost-based routing algorithms
- Geographic optimization
- Bandwidth and latency analysis

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).
"""

import os
import json
import time
import logging
import asyncio
import threading
from enum import Enum
from typing import Dict, List, Any, Optional, Union, Tuple, Set
from datetime import datetime
from pydantic import BaseModel, Field
from fastapi import FastAPI, APIRouter, Request, Response, Body, Depends

# Import routing components
from .routing.optimized_router import (
    OptimizedDataRouter, RoutingStrategy, ContentCategory, get_instance as get_router
)
from .routing.adaptive_optimizer import (
    AdaptiveOptimizer, create_adaptive_optimizer,
    OptimizationFactor, RoutingPriority
)
from .routing.router_api import router as routing_api_router
from .routing.data_router import ContentAnalyzer

# Configure logging
logger = logging.getLogger(__name__)


class RoutingManagerSettings(BaseModel):
    """Settings for the Routing Manager."""
    
    enabled: bool = Field(True, description="Whether routing optimization is enabled")
    default_strategy: str = Field("hybrid", description="Default routing strategy")
    default_priority: str = Field("balanced", description="Default routing priority")
    collect_metrics_on_startup: bool = Field(True, description="Whether to collect metrics on startup")
    auto_start_background_tasks: bool = Field(True, description="Whether to auto-start background tasks")
    learning_enabled: bool = Field(True, description="Whether learning is enabled")
    backends: List[str] = Field(default=[], description="Available backends")
    telemetry_interval: int = Field(300, description="Telemetry collection interval in seconds")
    metrics_retention_days: int = Field(7, description="Number of days to retain metrics")
    optimization_weights: Optional[Dict[str, float]] = Field(None, description="Custom optimization weights")
    geo_location: Optional[Dict[str, float]] = Field(None, description="Server geographic location")
    config_path: Optional[str] = Field(None, description="Path to routing configuration file")


class MetricsCollector:
    """Collects and aggregates metrics for routing optimization."""
    
    def __init__(self):
        """Initialize metrics collector."""
        self.backend_metrics: Dict[str, Dict[str, Any]] = {}
        self.network_metrics: Dict[str, Dict[str, Any]] = {}
        self.last_collection_time: Dict[str, float] = {}
        self.lock = threading.RLock()
    
    def update_backend_metrics(self, backend_id: str, metrics: Dict[str, Any]) -> None:
        """
        Update backend metrics.
        
        Args:
            backend_id: Backend ID
            metrics: Metrics dictionary
        """
        with self.lock:
            if backend_id not in self.backend_metrics:
                self.backend_metrics[backend_id] = {}
            
            # Update metrics
            self.backend_metrics[backend_id].update(metrics)
            self.last_collection_time[backend_id] = time.time()
    
    def update_network_metrics(self, backend_id: str, metrics: Dict[str, Any]) -> None:
        """
        Update network metrics.
        
        Args:
            backend_id: Backend ID
            metrics: Network metrics dictionary
        """
        with self.lock:
            if backend_id not in self.network_metrics:
                self.network_metrics[backend_id] = {}
            
            # Update metrics
            self.network_metrics[backend_id].update(metrics)
            self.last_collection_time[backend_id] = time.time()
    
    def get_backend_metrics(self, backend_id: str) -> Dict[str, Any]:
        """
        Get backend metrics.
        
        Args:
            backend_id: Backend ID
            
        Returns:
            Backend metrics dictionary
        """
        with self.lock:
            return self.backend_metrics.get(backend_id, {})
    
    def get_network_metrics(self, backend_id: str) -> Dict[str, Any]:
        """
        Get network metrics.
        
        Args:
            backend_id: Backend ID
            
        Returns:
            Network metrics dictionary
        """
        with self.lock:
            return self.network_metrics.get(backend_id, {})
    
    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all metrics.
        
        Returns:
            Dictionary mapping backend IDs to metrics
        """
        with self.lock:
            result = {}
            for backend_id in set(list(self.backend_metrics.keys()) + list(self.network_metrics.keys())):
                result[backend_id] = {
                    "backend": self.backend_metrics.get(backend_id, {}),
                    "network": self.network_metrics.get(backend_id, {}),
                    "last_updated": self.last_collection_time.get(backend_id, 0)
                }
            return result


class RoutingManager:
    """
    Central manager for the optimized data routing system.
    
    This class integrates all routing components and provides a clean interface
    for the MCP server to use the optimized data routing system.
    """
    
    def __init__(self, settings: Optional[RoutingManagerSettings] = None):
        """
        Initialize the routing manager.
        
        Args:
            settings: Optional settings for the routing manager
        """
        self.settings = settings or RoutingManagerSettings()
        
        # Initialize components
        self.legacy_router = get_router()
        self.adaptive_optimizer = create_adaptive_optimizer()
        self.metrics_collector = MetricsCollector()
        self.content_analyzer = ContentAnalyzer()
        
        # Enable learning if configured
        self.adaptive_optimizer.learning_enabled = self.settings.learning_enabled
        
        # Set default strategy
        try:
            self.default_strategy = RoutingStrategy(self.settings.default_strategy)
        except ValueError:
            logger.warning(f"Invalid default strategy: {self.settings.default_strategy}, using HYBRID")
            self.default_strategy = RoutingStrategy.HYBRID
        
        # Set default priority
        try:
            self.default_priority = RoutingPriority(self.settings.default_priority)
        except ValueError:
            logger.warning(f"Invalid default priority: {self.settings.default_priority}, using BALANCED")
            self.default_priority = RoutingPriority.BALANCED
        
        # Register backends
        for backend_id in self.settings.backends:
            self.register_backend(backend_id)
        
        # Set custom weights if provided
        if self.settings.optimization_weights:
            self._set_optimization_weights(self.settings.optimization_weights)
        
        # Set geographic location if provided
        if self.settings.geo_location:
            self._set_geographic_location(self.settings.geo_location)
        
        # Background tasks
        self._background_tasks = []
        self._shutdown_event = asyncio.Event()
        
        # Start background tasks if configured
        if self.settings.auto_start_background_tasks:
            self.start_background_tasks()
        
        # Load configuration if provided
        if self.settings.config_path:
            self.load_configuration(self.settings.config_path)
        
        logger.info("Routing Manager initialized")
    
    async def initialize(self) -> None:
        """Initialize the routing manager and collect initial metrics."""
        if self.settings.collect_metrics_on_startup:
            logger.info("Collecting initial metrics...")
            await self.collect_metrics(self.settings.backends)
    
    def register_backend(self, backend_id: str) -> None:
        """
        Register a backend with the routing system.
        
        Args:
            backend_id: Backend ID to register
        """
        # Register with legacy router
        self.legacy_router.register_backend(backend_id)
        
        # Initialize empty metrics
        self.metrics_collector.update_backend_metrics(backend_id, {
            "status": "registered",
            "registered_at": time.time()
        })
        
        logger.info(f"Registered backend: {backend_id}")
    
    def unregister_backend(self, backend_id: str) -> None:
        """
        Unregister a backend from the routing system.
        
        Args:
            backend_id: Backend ID to unregister
        """
        # Unregister from legacy router
        self.legacy_router.unregister_backend(backend_id)
        
        logger.info(f"Unregistered backend: {backend_id}")
    
    async def select_backend(
        self,
        content: Union[bytes, str, Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
        available_backends: Optional[List[str]] = None,
        strategy: Optional[Union[RoutingStrategy, str]] = None,
        priority: Optional[Union[RoutingPriority, str]] = None,
        client_location: Optional[Dict[str, float]] = None
    ) -> str:
        """
        Select the best backend for content storage or retrieval.
        
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
        if not self.settings.enabled:
            # If routing optimization is disabled, use simple strategy
            return self._select_backend_simple(available_backends)
        
        # Use defaults if not provided
        if available_backends is None:
            available_backends = self.settings.backends
        
        # Convert strategy if provided as string
        if strategy is not None and isinstance(strategy, str):
            try:
                strategy = RoutingStrategy(strategy)
            except ValueError:
                strategy = self.default_strategy
        elif strategy is None:
            strategy = self.default_strategy
        
        # Convert priority if provided as string
        if priority is not None and isinstance(priority, str):
            try:
                priority = RoutingPriority(priority)
            except ValueError:
                priority = self.default_priority
        elif priority is None:
            priority = self.default_priority
        
        # Process content based on type
        content_info = {}
        actual_content = None
        
        if isinstance(content, dict):
            # Content is provided as metadata
            content_info = content
            # Create dummy content for analysis if size is provided
            if "size_bytes" in content_info:
                actual_content = b"0" * min(1024, content_info["size_bytes"])
            else:
                actual_content = b"0" * 1024  # Default dummy content
        elif isinstance(content, (bytes, str)):
            # Content is provided as actual data
            actual_content = content
            # Analyze content to get metadata
            content_bytes = content if isinstance(content, bytes) else content.encode("utf-8")
            content_info = self.legacy_router.analyze_content(content_bytes)
        
        # Merge additional metadata if provided
        if metadata:
            content_info.update(metadata)
        
        # Add client location if provided
        if client_location:
            content_info["client_location"] = client_location
        
        try:
            # Try using adaptive optimizer for advanced routing
            result = self.adaptive_optimizer.optimize_route(
                content=actual_content,
                metadata=content_info,
                available_backends=available_backends,
                priority=priority,
                client_location=client_location
            )
            
            # Log the decision
            logger.debug(
                f"Selected backend '{result.backend_id}' for content "
                f"(category: {result.content_analysis.get('category', 'unknown')}, "
                f"size: {result.content_analysis.get('size_bytes', 0)} bytes)"
            )
            
            return result.backend_id
            
        except Exception as e:
            # Fall back to legacy router if adaptive optimizer fails
            logger.warning(f"Adaptive optimizer failed: {str(e)}, falling back to legacy router")
            return self.legacy_router.get_backend_for_content(content_info, strategy)
    
    def _select_backend_simple(self, available_backends: Optional[List[str]] = None) -> str:
        """
        Simple backend selection when optimization is disabled.
        
        Args:
            available_backends: List of available backends
            
        Returns:
            ID of the selected backend
        """
        backends = available_backends or self.settings.backends
        if not backends:
            return "ipfs"  # Default fallback
        
        # Use round-robin strategy
        return self.legacy_router.get_backend_for_content(
            content_info={},
            strategy=RoutingStrategy.ROUND_ROBIN
        )
    
    async def record_routing_outcome(
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
        if not self.settings.enabled or not self.settings.learning_enabled:
            return
        
        try:
            # Extract category
            category_str = content_info.get("category", "other")
            try:
                category = ContentCategory(category_str)
            except ValueError:
                category = ContentCategory.OTHER
            
            # Extract size
            size_bytes = content_info.get("size_bytes", 0)
            
            # Record with legacy router
            self.legacy_router.update_backend_stats(
                backend_id=backend_id,
                operation="store" if "operation" not in content_info else content_info["operation"],
                success=success,
                size_bytes=size_bytes,
                content_type=content_info.get("content_type")
            )
            
            # Record with adaptive optimizer
            try:
                # Create dummy result for the optimizer
                from .routing.adaptive_optimizer import RouteOptimizationResult
                result = RouteOptimizationResult(backend_id)
                result.content_analysis = {
                    "category": category.value,
                    "size_bytes": size_bytes
                }
                
                # Record outcome
                self.adaptive_optimizer.record_outcome(result, success)
            except Exception as e:
                logger.warning(f"Error recording outcome with adaptive optimizer: {str(e)}")
            
        except Exception as e:
            logger.error(f"Error recording routing outcome: {str(e)}")
    
    async def collect_metrics(self, backend_ids: Optional[List[str]] = None) -> None:
        """
        Collect metrics for routing optimization.
        
        Args:
            backend_ids: Optional list of backend IDs to collect metrics for
        """
        if backend_ids is None:
            backend_ids = self.settings.backends
        
        try:
            # Collect metrics with adaptive optimizer
            self.adaptive_optimizer.collect_all_metrics(backend_ids)
            
            # Collect and update additional metrics
            for backend_id in backend_ids:
                # Get network metrics
                network_metrics = self.adaptive_optimizer.network_analyzer.get_metrics(backend_id)
                
                # Update metrics collector
                self.metrics_collector.update_network_metrics(
                    backend_id=backend_id,
                    metrics={
                        "latency_ms": network_metrics.get_average_latency(),
                        "bandwidth_mbps": network_metrics.get_average_bandwidth(),
                        "error_rate": network_metrics.get_average_error_rate(),
                        "quality_level": network_metrics.get_overall_quality().value,
                        "performance_score": network_metrics.get_performance_score()
                    }
                )
                
                # Update backend stats in legacy router
                self.legacy_router.update_backend_availability(
                    backend_id=backend_id,
                    available=network_metrics.get_performance_score() > 0.3  # Minimum threshold
                )
            
            logger.debug(f"Collected metrics for {len(backend_ids)} backends")
            
        except Exception as e:
            logger.error(f"Error collecting metrics: {str(e)}")
    
    def _set_optimization_weights(self, weights: Dict[str, float]) -> None:
        """
        Set custom optimization weights.
        
        Args:
            weights: Dictionary mapping optimization factors to weights
        """
        try:
            # Convert string keys to OptimizationFactor enum
            enum_weights = {}
            for key, value in weights.items():
                try:
                    factor = OptimizationFactor(key)
                    enum_weights[factor] = value
                except ValueError:
                    logger.warning(f"Invalid optimization factor: {key}")
            
            # Set weights in adaptive optimizer
            for factor, weight in enum_weights.items():
                self.adaptive_optimizer.weights.weights[factor] = weight
            
            # Normalize weights
            self.adaptive_optimizer.weights._normalize_weights()
            
            logger.info(f"Set custom optimization weights: {weights}")
            
        except Exception as e:
            logger.error(f"Error setting optimization weights: {str(e)}")
    
    def _set_geographic_location(self, location: Dict[str, float]) -> None:
        """
        Set geographic location for the server.
        
        Args:
            location: Dictionary with 'lat' and 'lon' keys
        """
        try:
            if "lat" in location and "lon" in location:
                # Set in geographic router
                self.adaptive_optimizer.geographic_router.set_server_location(
                    location["lat"],
                    location["lon"]
                )
                
                logger.info(f"Set geographic location: {location}")
            
        except Exception as e:
            logger.error(f"Error setting geographic location: {str(e)}")
    
    async def get_routing_insights(self) -> Dict[str, Any]:
        """
        Get insights from the routing system.
        
        Returns:
            Dictionary with routing insights
        """
        try:
            # Get insights from adaptive optimizer
            insights = self.adaptive_optimizer.generate_insights()
            
            # Add insights from legacy router
            legacy_insights = {
                "backend_stats": self.legacy_router.get_backend_stats(),
                "route_mappings": self.legacy_router.get_route_mappings()
            }
            
            # Merge insights
            merged_insights = {
                **insights,
                "legacy": legacy_insights,
                "metrics": self.metrics_collector.get_all_metrics()
            }
            
            return merged_insights
            
        except Exception as e:
            logger.error(f"Error generating routing insights: {str(e)}")
            return {"error": str(e)}
    
    def register_with_app(self, app: FastAPI) -> None:
        """
        Register routing API endpoints with a FastAPI app.
        
        Args:
            app: FastAPI application
        """
        # Include the routing API router
        app.include_router(routing_api_router)
        
        logger.info("Registered routing API endpoints")
    
    def start_background_tasks(self) -> None:
        """Start background tasks for the routing manager."""
        # Start metrics collection task
        metrics_task = asyncio.create_task(
            self._metrics_collection_task(
                interval_seconds=self.settings.telemetry_interval
            )
        )
        self._background_tasks.append(metrics_task)
        
        logger.info("Started routing manager background tasks")
    
    async def stop_background_tasks(self) -> None:
        """Stop background tasks for the routing manager."""
        # Signal shutdown
        self._shutdown_event.set()
        
        # Wait for tasks to complete
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
            self._background_tasks.clear()
        
        logger.info("Stopped routing manager background tasks")
    
    async def _metrics_collection_task(self, interval_seconds: int = 300) -> None:
        """
        Background task for collecting metrics periodically.
        
        Args:
            interval_seconds: Interval in seconds
        """
        try:
            while not self._shutdown_event.is_set():
                # Collect metrics
                await self.collect_metrics()
                
                # Wait for next collection
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=interval_seconds
                    )
                except asyncio.TimeoutError:
                    # Normal timeout, continue with next collection
                    pass
        except asyncio.CancelledError:
            logger.info("Metrics collection task cancelled")
        except Exception as e:
            logger.error(f"Error in metrics collection task: {str(e)}")
    
    def save_configuration(self, config_path: str) -> bool:
        """
        Save current routing configuration.
        
        Args:
            config_path: Path to save configuration to
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Export legacy router configuration
            legacy_config = self.legacy_router.export_routing_config()
            
            # Add adaptive optimizer configuration
            adaptive_config = self.adaptive_optimizer.to_dict()
            
            # Create combined configuration
            config = {
                "legacy_router": legacy_config,
                "adaptive_optimizer": adaptive_config,
                "settings": self.settings.dict(),
                "saved_at": datetime.now().isoformat()
            }
            
            # Save to file
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, "w") as f:
                json.dump(config, f, indent=2)
            
            logger.info(f"Saved routing configuration to {config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving routing configuration: {str(e)}")
            return False
    
    def load_configuration(self, config_path: str) -> bool:
        """
        Load routing configuration from file.
        
        Args:
            config_path: Path to load configuration from
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not os.path.exists(config_path):
                logger.warning(f"Configuration file not found: {config_path}")
                return False
            
            # Load from file
            with open(config_path, "r") as f:
                config = json.load(f)
            
            # Apply legacy router configuration
            if "legacy_router" in config:
                self.legacy_router.import_routing_config(config["legacy_router"])
            
            # Apply settings if present
            if "settings" in config:
                # Only apply certain settings to avoid overriding runtime settings
                safe_settings = ["default_strategy", "default_priority", "optimization_weights"]
                for key in safe_settings:
                    if key in config["settings"]:
                        setattr(self.settings, key, config["settings"][key])
            
            logger.info(f"Loaded routing configuration from {config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading routing configuration: {str(e)}")
            return False


# Singleton instance
_routing_manager = None


def get_routing_manager() -> RoutingManager:
    """
    Get the singleton routing manager instance.
    
    Returns:
        RoutingManager instance
    """
    global _routing_manager
    if _routing_manager is None:
        _routing_manager = RoutingManager()
    return _routing_manager


async def initialize_routing_manager(settings: Optional[RoutingManagerSettings] = None) -> RoutingManager:
    """
    Initialize the routing manager.
    
    Args:
        settings: Optional settings for the routing manager
        
    Returns:
        Initialized RoutingManager instance
    """
    global _routing_manager
    
    if _routing_manager is None:
        _routing_manager = RoutingManager(settings)
    
    # Initialize the manager
    await _routing_manager.initialize()
    
    return _routing_manager


def register_routing_manager(app: FastAPI) -> None:
    """
    Register the routing manager with a FastAPI app.
    
    This registers the routing API endpoints and any middleware needed.
    
    Args:
        app: FastAPI application
    """
    routing_manager = get_routing_manager()
    routing_manager.register_with_app(app)


async def select_optimal_backend(
    content: Union[bytes, str, Dict[str, Any]],
    metadata: Optional[Dict[str, Any]] = None,
    available_backends: Optional[List[str]] = None,
    strategy: Optional[str] = None,
    priority: Optional[str] = None,
    client_location: Optional[Dict[str, float]] = None
) -> str:
    """
    Convenience function to select the optimal backend for content.
    
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
    routing_manager = get_routing_manager()
    return await routing_manager.select_backend(
        content=content,
        metadata=metadata,
        available_backends=available_backends,
        strategy=strategy,
        priority=priority,
        client_location=client_location
    )