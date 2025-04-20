"""
Enhanced Routing Manager with Performance Optimizations

This module provides an enhanced version of the routing manager that incorporates
performance optimizations for improved efficiency, lower latency, and reduced
resource consumption.
"""

import os
import time
import logging
import asyncio
import tracemalloc
from typing import Dict, Any, List, Optional, Union, Tuple, Set, Callable

from .routing_manager import (
    RoutingManager, RoutingManagerSettings, get_routing_manager
)
from .performance_optimization import (
    RoutingDecisionCache, ContentSignatureCalculator, BatchProcessor,
    ConnectionPool, performance_metrics, measure_routing_performance,
    initialize_performance_optimizations, shutdown_performance_optimizations
)

# Configure logging
logger = logging.getLogger(__name__)


class EnhancedRoutingManager(RoutingManager):
    """
    Enhanced routing manager with performance optimizations.
    
    This class extends the base RoutingManager with various performance optimizations:
    - Decision caching for similar content
    - Efficient content signature calculation
    - Batch processing for metrics and learning updates
    - Connection pooling for backend access
    - Memory optimization through efficient data structures
    """
    
    def __init__(self, settings: Optional[RoutingManagerSettings] = None):
        """
        Initialize the enhanced routing manager.
        
        Args:
            settings: Optional settings for the routing manager
        """
        # Initialize base class
        super().__init__(settings)
        
        # Initialize optimization components
        self.decision_cache = RoutingDecisionCache(
            max_size=self.settings.cache_size if hasattr(self.settings, "cache_size") else 1000,
            ttl_seconds=self.settings.cache_ttl if hasattr(self.settings, "cache_ttl") else 3600
        )
        
        self.signature_calculator = ContentSignatureCalculator()
        
        # Create batch processor for outcome recording
        self.outcome_batch_processor = BatchProcessor(
            max_batch_size=50,
            max_wait_time=0.2,
            processor_func=self._process_outcome_batch
        )
        
        # Initialize connection pool
        self.connection_pool = ConnectionPool(
            max_connections=10,
            connection_ttl=300,
            connection_factory=self._create_backend_connection
        )
        
        # Performance monitoring
        self.enable_performance_monitoring = getattr(self.settings, "enable_performance_monitoring", True)
        self.memory_tracking = getattr(self.settings, "memory_tracking", False)
        
        # Background tasks
        self._perf_monitor_task = None
        
        # If memory tracking is enabled, start tracemalloc
        if self.memory_tracking:
            tracemalloc.start()
        
        logger.info("Enhanced routing manager initialized with performance optimizations")
    
    async def initialize(self) -> None:
        """Initialize the routing manager and optimization components."""
        # Initialize base class
        await super().initialize()
        
        # Initialize performance optimizations
        await initialize_performance_optimizations()
        
        # Start batch processor
        await self.outcome_batch_processor.start()
        
        # Start connection pool
        await self.connection_pool.start()
        
        # Start performance monitoring if enabled
        if self.enable_performance_monitoring:
            self._perf_monitor_task = asyncio.create_task(self._performance_monitoring_loop())
        
        logger.info("Enhanced routing manager initialization complete")
    
    async def _create_backend_connection(self, backend_id: str) -> Any:
        """
        Create a connection to a backend.
        
        Args:
            backend_id: Backend ID
            
        Returns:
            Backend connection object
        """
        # This is a placeholder for actual backend connection creation
        # In a real implementation, this would create a connection to the backend
        
        # Simulate connection creation with a delay
        await asyncio.sleep(0.05)
        
        # Return a simple object representing the connection
        return {
            "backend_id": backend_id,
            "connected_at": time.time(),
            "connection_id": f"{backend_id}_{int(time.time() * 1000)}"
        }
    
    async def _performance_monitoring_loop(self) -> None:
        """Background loop for performance monitoring."""
        try:
            while True:
                try:
                    # Sleep for a while
                    await asyncio.sleep(60)  # Update every minute
                    
                    # Update memory usage if tracking is enabled
                    if self.memory_tracking:
                        current, peak = tracemalloc.get_traced_memory()
                        performance_metrics.memory_usage_bytes = current
                        
                        logger.debug(f"Current memory usage: {current / 1024 / 1024:.2f} MB")
                        logger.debug(f"Peak memory usage: {peak / 1024 / 1024:.2f} MB")
                    
                    # Log current performance metrics
                    metrics = performance_metrics.to_dict()
                    
                    logger.info(
                        f"Routing performance: "
                        f"requests={metrics['requests']}, "
                        f"avg_time={metrics['avg_request_time_ms']:.2f}ms, "
                        f"cache_hit_ratio={metrics['cache_hit_ratio']:.2f}"
                    )
                    
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.error(f"Error in performance monitoring loop: {e}")
        except asyncio.CancelledError:
            logger.info("Performance monitoring task cancelled")
    
    @measure_routing_performance
    async def select_backend(
        self,
        content: Union[bytes, str, Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
        available_backends: Optional[List[str]] = None,
        strategy: Optional[Union[str]] = None,
        priority: Optional[Union[str]] = None,
        client_location: Optional[Dict[str, float]] = None
    ) -> str:
        """
        Select the best backend for content storage or retrieval.
        
        This optimized version includes caching, signature calculation, and
        performance monitoring.
        
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
            
            # Calculate signature
            signature = await self.signature_calculator.calculate_signature(content_bytes)
            
            # Analyze content
            content_info = self.legacy_router.analyze_content(content_bytes)
            
            # Add signature
            content_info["content_signature"] = signature
        
        # Merge additional metadata if provided
        if metadata:
            content_info.update(metadata)
        
        # Add client location if provided
        if client_location:
            content_info["client_location"] = client_location
        
        # Check cache
        cache_key = f"{strategy}:{priority}:{','.join(available_backends or [])}"
        cached_decision = await self.decision_cache.get({**content_info, "cache_key": cache_key})
        
        if cached_decision:
            logger.debug(f"Using cached routing decision for content")
            return cached_decision["backend_id"]
        
        # Use defaults if not provided
        if available_backends is None:
            available_backends = self.settings.backends
        
        # Call base implementation
        backend_id = await super().select_backend(
            content=actual_content,
            metadata=content_info,
            available_backends=available_backends,
            strategy=strategy,
            priority=priority,
            client_location=client_location
        )
        
        # Cache the decision
        await self.decision_cache.put(
            {**content_info, "cache_key": cache_key},
            {"backend_id": backend_id}
        )
        
        return backend_id
    
    async def record_routing_outcome(
        self,
        backend_id: str,
        content_info: Dict[str, Any],
        success: bool
    ) -> None:
        """
        Record the outcome of a routing decision to improve future decisions.
        
        This optimized version uses batch processing for efficiency.
        
        Args:
            backend_id: Backend that was used
            content_info: Content information
            success: Whether the operation was successful
        """
        # Add to batch for processing
        await self.outcome_batch_processor.add_item({
            "backend_id": backend_id,
            "content_info": content_info,
            "success": success,
            "timestamp": time.time()
        })
    
    async def _process_outcome_batch(self, batch: List[Dict[str, Any]]) -> None:
        """
        Process a batch of routing outcomes.
        
        Args:
            batch: List of outcome dictionaries
        """
        if not batch:
            return
        
        logger.debug(f"Processing batch of {len(batch)} routing outcomes")
        
        # Group by backend for efficiency
        backend_outcomes = {}
        
        for outcome in batch:
            backend_id = outcome["backend_id"]
            if backend_id not in backend_outcomes:
                backend_outcomes[backend_id] = []
            backend_outcomes[backend_id].append(outcome)
        
        # Process each backend's outcomes
        for backend_id, outcomes in backend_outcomes.items():
            # Update metrics in legacy router
            success_count = sum(1 for o in outcomes if o["success"])
            failure_count = len(outcomes) - success_count
            
            # Update backend stats
            if success_count > 0:
                self.legacy_router.update_backend_stats(
                    backend_id=backend_id,
                    operation="batch_success",
                    success=True,
                    size_bytes=sum(o["content_info"].get("size_bytes", 0) for o in outcomes if o["success"])
                )
            
            if failure_count > 0:
                self.legacy_router.update_backend_stats(
                    backend_id=backend_id,
                    operation="batch_failure",
                    success=False,
                    size_bytes=sum(o["content_info"].get("size_bytes", 0) for o in outcomes if not o["success"])
                )
            
            # Process individual outcomes with the adaptive optimizer
            for outcome in outcomes:
                try:
                    # Create dummy result for the optimizer
                    from .adaptive_optimizer import RouteOptimizationResult
                    result = RouteOptimizationResult(backend_id)
                    
                    # Extract content info
                    content_info = outcome["content_info"]
                    
                    # Set content analysis
                    result.content_analysis = {
                        "category": content_info.get("content_category", "unknown"),
                        "size_bytes": content_info.get("size_bytes", 0)
                    }
                    
                    # Record outcome
                    self.adaptive_optimizer.record_outcome(result, outcome["success"])
                except Exception as e:
                    logger.error(f"Error recording outcome with adaptive optimizer: {e}")
    
    async def get_backend_connection(self, backend_id: str) -> Any:
        """
        Get a connection to a backend from the connection pool.
        
        Args:
            backend_id: Backend ID
            
        Returns:
            Backend connection object
        """
        return await self.connection_pool.get_connection(backend_id)
    
    async def release_backend_connection(self, backend_id: str, connection: Any) -> None:
        """
        Release a backend connection back to the pool.
        
        Args:
            backend_id: Backend ID
            connection: Connection object
        """
        await self.connection_pool.release_connection(backend_id, connection)
    
    async def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get current performance metrics.
        
        Returns:
            Dictionary with performance metrics
        """
        return performance_metrics.to_dict()
    
    async def invalidate_cache(self, backend_id: Optional[str] = None) -> int:
        """
        Invalidate the routing decision cache.
        
        Args:
            backend_id: Optional backend ID to invalidate entries for
            
        Returns:
            Number of cache entries invalidated
        """
        return await self.decision_cache.invalidate(backend_id)
    
    async def get_routing_insights(self) -> Dict[str, Any]:
        """
        Get insights from the routing system.
        
        This enhanced version adds performance metrics to the insights.
        
        Returns:
            Dictionary with routing insights
        """
        # Get base insights
        insights = await super().get_routing_insights()
        
        # Add performance metrics
        insights["performance_metrics"] = performance_metrics.to_dict()
        
        # Add cache stats
        insights["cache_stats"] = {
            "decision_cache_size": len(self.decision_cache._cache),
            "signature_cache_size": len(self.signature_calculator._cache),
        }
        
        return insights
    
    async def close(self) -> None:
        """Close the enhanced routing manager and cleanup resources."""
        # Stop batch processor
        await self.outcome_batch_processor.stop()
        
        # Stop connection pool
        await self.connection_pool.stop()
        
        # Stop performance monitoring
        if self._perf_monitor_task:
            self._perf_monitor_task.cancel()
            try:
                await self._perf_monitor_task
            except asyncio.CancelledError:
                pass
        
        # Shutdown performance optimizations
        await shutdown_performance_optimizations()
        
        # Stop memory tracking if enabled
        if self.memory_tracking:
            tracemalloc.stop()
        
        logger.info("Enhanced routing manager closed")


# Singleton instance
_enhanced_routing_manager = None


def get_enhanced_routing_manager() -> EnhancedRoutingManager:
    """
    Get the singleton enhanced routing manager instance.
    
    Returns:
        EnhancedRoutingManager instance
    """
    global _enhanced_routing_manager
    if _enhanced_routing_manager is None:
        _enhanced_routing_manager = EnhancedRoutingManager()
    return _enhanced_routing_manager


async def initialize_enhanced_routing_manager(
    settings: Optional[RoutingManagerSettings] = None
) -> EnhancedRoutingManager:
    """
    Initialize the enhanced routing manager.
    
    Args:
        settings: Optional settings for the routing manager
        
    Returns:
        Initialized EnhancedRoutingManager instance
    """
    global _enhanced_routing_manager
    
    if _enhanced_routing_manager is None:
        # Create settings with defaults for enhanced routing
        if settings is None:
            settings = RoutingManagerSettings(
                enabled=True,
                default_strategy="hybrid",
                default_priority="balanced",
                backends=["ipfs", "filecoin", "s3", "storacha", "huggingface"],
                learning_enabled=True,
                # Enhanced settings
                cache_size=1000,
                cache_ttl=3600,
                enable_performance_monitoring=True,
                memory_tracking=False
            )
        
        _enhanced_routing_manager = EnhancedRoutingManager(settings)
    
    # Initialize the manager
    await _enhanced_routing_manager.initialize()
    
    return _enhanced_routing_manager


async def select_backend_optimized(
    content: Union[bytes, str, Dict[str, Any]],
    metadata: Optional[Dict[str, Any]] = None,
    available_backends: Optional[List[str]] = None,
    strategy: Optional[str] = None,
    priority: Optional[str] = None,
    client_location: Optional[Dict[str, float]] = None
) -> str:
    """
    Optimized function to select the best backend for content.
    
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
    # Get enhanced routing manager
    manager = get_enhanced_routing_manager()
    
    # Select backend
    return await manager.select_backend(
        content=content,
        metadata=metadata,
        available_backends=available_backends,
        strategy=strategy,
        priority=priority,
        client_location=client_location
    )