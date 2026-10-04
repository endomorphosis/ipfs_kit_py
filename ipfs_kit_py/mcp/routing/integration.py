#!/usr/bin/env python3
# ipfs_kit_py/mcp/routing/integration.py

"""
MCP Server Integration for Optimized Data Routing.

This module provides the integration between the MCP server and the
optimized data routing system, allowing intelligent backend selection
for storage operations.
"""

import logging
import time
from typing import Dict, List, Optional, Any, Tuple, Union

from ..router import (
    Backend, ContentType, OperationType, RouteMetrics, 
    RoutingContext, RoutingDecision, DataRouter
)
from . import initialize_router, get_router

logger = logging.getLogger(__name__)


class MCPRoutingIntegration:
    """
    Integrates the optimized routing system with the MCP server.
    
    This class provides methods for initializing the routing system and
    using it to make backend selection decisions for storage operations.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the routing integration.
        
        Args:
            config: Optional configuration for the routing system
        """
        self.config = config or {}
        self.router = initialize_router(self.config)
        
        # Cache for performance data
        self.performance_data = {}
        
        logger.info("Initialized MCP routing integration")
    
    def register_backend(self, backend: Backend, info: Dict[str, Any] = None) -> None:
        """
        Register a storage backend with the router.
        
        Args:
            backend: Backend identifier
            info: Additional backend information
        """
        self.router.register_backend(backend, info)
        logger.info(f"Registered backend with router: {backend}")
    
    def unregister_backend(self, backend: Backend) -> None:
        """
        Unregister a storage backend from the router.
        
        Args:
            backend: Backend identifier
        """
        self.router.unregister_backend(backend)
        logger.info(f"Unregistered backend from router: {backend}")
    
    def record_operation_performance(self, backend: Backend, operation_type: str, 
                                  start_time: float, bytes_sent: int = 0, 
                                  bytes_received: int = 0, success: bool = True,
                                  error: Optional[str] = None) -> None:
        """
        Record performance metrics for an operation.
        
        Args:
            backend: The storage backend
            operation_type: Type of operation
            start_time: Start time of the operation
            bytes_sent: Number of bytes sent
            bytes_received: Number of bytes received
            success: Whether the operation was successful
            error: Error message if the operation failed
        """
        # Get the performance metrics collector
        perf_metrics = self.router.metrics_collectors.get('performance')
        if not perf_metrics:
            logger.warning("No performance metrics collector registered")
            return
        
        # Record the metrics
        metrics = perf_metrics.record_operation_performance(
            backend=backend,
            start_time=start_time,
            bytes_sent=bytes_sent,
            bytes_received=bytes_received,
            operation_type=operation_type,
            success=success,
            error=error
        )
        
        # Store in local cache
        self.performance_data[backend] = metrics
        
        logger.debug(
            f"Recorded performance for {backend} ({operation_type}): "
            f"{metrics.get('throughput_mbps', 0):.2f} Mbps, "
            f"{metrics.get('latency_ms', 0):.2f} ms, "
            f"success: {success}"
        )
    
    def select_backend(self, operation_type: str, content_type: Optional[str] = None,
                     content_size: Optional[int] = None, user_id: Optional[str] = None,
                     region: Optional[str] = None, strategy: Optional[str] = None,
                     metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Select the optimal backend for an operation.
        
        Args:
            operation_type: Type of operation (read, write, etc.)
            content_type: Type of content (image, video, etc.)
            content_size: Size of content in bytes
            user_id: User ID
            region: Geographic region
            strategy: Routing strategy to use
            metadata: Additional metadata for the routing decision
            
        Returns:
            Dict[str, Any]: Dictionary with selected backend and decision details
        """
        try:
            # Convert string types to enums
            op_type = OperationType(operation_type.lower()) if operation_type else OperationType.READ
            
            # Convert content type if provided
            content_enum = None
            if content_type:
                try:
                    content_enum = ContentType(content_type.lower())
                except ValueError:
                    logger.warning(f"Unknown content type: {content_type}")
            
            # Create routing context
            context = RoutingContext(
                operation=op_type,
                content_type=content_enum,
                content_size_bytes=content_size,
                user_id=user_id,
                region=region,
                metadata=metadata or {}
            )
            
            # Get routing decision
            decision = self.router.select_backend(context, strategy)
            
            # Format the result for the MCP server
            result = {
                'backend': decision.backend,
                'score': decision.score,
                'reason': decision.reason,
                'alternatives': [
                    {'backend': b, 'score': s} for b, s in decision.alternatives
                ],
                'metrics': {
                    k: v for k, v in decision.metrics.as_dict().items()
                    if k != 'custom_metrics'
                }
            }
            
            # Add custom metrics if available
            if hasattr(decision.metrics, 'custom_metrics'):
                for k, v in decision.metrics.custom_metrics.items():
                    if isinstance(v, dict):
                        result['metrics'][k] = v
            
            return result
            
        except Exception as e:
            logger.error(f"Error selecting backend: {e}", exc_info=True)
            
            # Return a default result with an error
            return {
                'backend': self._get_default_backend(),
                'score': 0.0,
                'reason': f"Error selecting backend: {str(e)}",
                'error': str(e),
                'alternatives': [],
                'metrics': {}
            }
    
    def _get_default_backend(self) -> str:
        """
        Get a default backend when the router fails.
        
        Returns:
            str: Default backend name
        """
        # Use the first available backend or a configured default
        default_backend = self.config.get('default_backend', 'IPFS')
        
        if self.router.available_backends:
            return list(self.router.available_backends)[0]
        
        return default_backend
    
    def get_backend_metrics(self, backend: Backend) -> Dict[str, Any]:
        """
        Get all metrics for a backend.
        
        Args:
            backend: Backend identifier
            
        Returns:
            Dict[str, Any]: Dictionary of metrics
        """
        metrics = {}
        
        # Collect metrics from each collector
        for name, collector in self.router.metrics_collectors.items():
            try:
                collector_metrics = collector.collect_metrics(backend)
                metrics[name] = collector_metrics
            except Exception as e:
                logger.warning(f"Error collecting {name} metrics for {backend}: {e}")
        
        return metrics
    
    def get_routing_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get the routing decision history.
        
        Args:
            limit: Maximum number of decisions to return
            
        Returns:
            List[Dict[str, Any]]: List of routing decisions
        """
        history = self.router.get_routing_history(limit)
        
        # Convert to dictionaries
        return [
            {
                'backend': decision.backend,
                'score': decision.score,
                'reason': decision.reason,
                'timestamp': getattr(decision.context, 'timestamp', None),
                'operation': getattr(decision.context, 'operation', None).value 
                    if hasattr(decision.context, 'operation') else None,
                'content_type': getattr(decision.context, 'content_type', None).value 
                    if hasattr(decision.context, 'content_type') and decision.context.content_type else None,
                'content_size': getattr(decision.context, 'content_size_bytes', None),
                'user_id': getattr(decision.context, 'user_id', None),
                'region': getattr(decision.context, 'region', None)
            }
            for decision in history
        ]


# Create a global instance for convenience
_mcp_routing: Optional[MCPRoutingIntegration] = None


def initialize_mcp_routing(config: Optional[Dict[str, Any]] = None) -> MCPRoutingIntegration:
    """
    Initialize the MCP routing integration.
    
    Args:
        config: Optional configuration for the routing system
        
    Returns:
        MCPRoutingIntegration: The initialized integration instance
    """
    global _mcp_routing
    _mcp_routing = MCPRoutingIntegration(config)
    return _mcp_routing


def get_mcp_routing() -> MCPRoutingIntegration:
    """
    Get the global MCP routing integration instance.
    
    Returns:
        MCPRoutingIntegration: The integration instance
        
    Raises:
        RuntimeError: If the integration has not been initialized
    """
    if _mcp_routing is None:
        raise RuntimeError("MCP routing integration has not been initialized. Call initialize_mcp_routing() first.")
    return _mcp_routing


def select_backend(operation_type: str, content_type: Optional[str] = None,
                 content_size: Optional[int] = None, user_id: Optional[str] = None,
                 region: Optional[str] = None, strategy: Optional[str] = None,
                 metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Select the optimal backend for an operation.
    
    This is a convenience function that uses the global MCP routing integration.
    
    Args:
        operation_type: Type of operation (read, write, etc.)
        content_type: Type of content (image, video, etc.)
        content_size: Size of content in bytes
        user_id: User ID
        region: Geographic region
        strategy: Routing strategy to use
        metadata: Additional metadata for the routing decision
        
    Returns:
        Dict[str, Any]: Dictionary with selected backend and decision details
    """
    return get_mcp_routing().select_backend(
        operation_type=operation_type,
        content_type=content_type,
        content_size=content_size,
        user_id=user_id,
        region=region,
        strategy=strategy,
        metadata=metadata
    )


# Example usage
def example_usage():
    """Example usage of the MCP routing integration."""
    # Initialize the routing integration
    routing = initialize_mcp_routing({
        'default_backend': 'IPFS',
        'strategy_weights': {
            'content': 0.3,
            'cost': 0.3,
            'geo': 0.2,
            'performance': 0.2
        }
    })
    
    # Register available backends
    routing.register_backend('IPFS', {'type': 'ipfs', 'version': '0.14.0'})
    routing.register_backend('S3', {'type': 's3', 'bucket': 'data-bucket'})
    routing.register_backend('FILECOIN', {'type': 'filecoin', 'network': 'mainnet'})
    
    # Example 1: Select backend for storing a large video file
    result = routing.select_backend(
        operation_type='write',
        content_type='video',
        content_size=500 * 1024 * 1024,  # 500 MB
        region='us-east'
    )
    print(f"Selected backend for large video: {result['backend']}")
    print(f"Reason: {result['reason']}")
    
    # Example 2: Select backend for reading a document
    result = routing.select_backend(
        operation_type='read',
        content_type='document',
        content_size=2 * 1024 * 1024,  # 2 MB
        region='eu-west'
    )
    print(f"Selected backend for document: {result['backend']}")
    print(f"Reason: {result['reason']}")
    
    # Example 3: Record performance metrics for a backend
    start_time = time.time()
    # Simulate some operation
    time.sleep(0.1)
    routing.record_operation_performance(
        backend='IPFS',
        operation_type='read',
        start_time=start_time,
        bytes_received=10 * 1024 * 1024,  # 10 MB
        success=True
    )
    
    # Example 4: Select backend with specific strategy
    result = routing.select_backend(
        operation_type='read',
        content_size=100 * 1024 * 1024,  # 100 MB
        strategy='performance'
    )
    print(f"Selected backend using performance strategy: {result['backend']}")
    print(f"Reason: {result['reason']}")


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Run the example
    example_usage()