"""
MCP server integration for optimized routing

This file provides integration between the MCP server and the optimized data routing system.
"""

import os
import logging
from typing import Dict, Any, List, Optional

from .routing.adaptive_optimizer import (
    AdaptiveOptimizer, create_adaptive_optimizer, RouteOptimizationResult,
    OptimizationFactor
)
from .routing.data_router import ContentCategory, RoutingPriority, RoutingStrategy
from .routing.bandwidth_aware_router import NetworkQualityLevel, NetworkMetricType

# Configure logging
logger = logging.getLogger(__name__)


class RoutingManager:
    """
    Manager class that integrates the adaptive routing optimizer with the MCP server.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the routing manager.
        
        Args:
            config: Optional configuration dict
        """
        self.config = config or {}
        
        # Create optimizer
        self.optimizer = create_adaptive_optimizer()
        
        # Get available backends from config or use defaults
        self.available_backends = self.config.get("available_backends", [
            "ipfs", "filecoin", "s3", "storacha", "huggingface", "lassie"
        ])
        
        # Routing strategy
        strategy_name = self.config.get("routing_strategy", "adaptive")
        try:
            self.routing_strategy = RoutingStrategy(strategy_name)
        except ValueError:
            self.routing_strategy = RoutingStrategy.ADAPTIVE
        
        # Default priority
        priority_name = self.config.get("default_priority", "balanced")
        try:
            self.default_priority = RoutingPriority(priority_name)
        except ValueError:
            self.default_priority = RoutingPriority.BALANCED
        
        # Enable learning
        self.enable_learning = self.config.get("enable_learning", True)
        self.optimizer.learning_enabled = self.enable_learning
        
        # Start collection of metrics if configured
        if self.config.get("collect_metrics_on_startup", True):
            self._collect_initial_metrics()
    
    def _collect_initial_metrics(self):
        """Collect initial metrics for available backends."""
        try:
            logger.info("Collecting initial metrics for available backends...")
            self.optimizer.collect_all_metrics(self.available_backends)
        except Exception as e:
            logger.warning(f"Error collecting initial metrics: {str(e)}")
    
    def select_backend(
        self,
        content: bytes,
        metadata: Optional[Dict[str, Any]] = None,
        priority: Optional[RoutingPriority] = None,
        client_location: Optional[Dict[str, float]] = None
    ) -> str:
        """
        Select the optimal backend for content.
        
        Args:
            content: Content to route
            metadata: Optional metadata
            priority: Optional routing priority
            client_location: Optional client location (lat/lon)
            
        Returns:
            Selected backend ID
        """
        # Use default priority if not specified
        if priority is None:
            priority = self.default_priority
        
        # Check if routing strategy is not adaptive
        if self.routing_strategy != RoutingStrategy.ADAPTIVE:
            # Use strategy-specific routing
            if self.routing_strategy == RoutingStrategy.ROUND_ROBIN:
                return self._round_robin_selection()
            elif self.routing_strategy == RoutingStrategy.RANDOM:
                return self._random_selection()
            elif self.routing_strategy == RoutingStrategy.FIXED:
                return self._fixed_selection()
        
        # Use adaptive optimizer for routing
        try:
            result = self.optimizer.optimize_route(
                content=content,
                metadata=metadata,
                available_backends=self.available_backends,
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
            logger.error(f"Error in adaptive routing: {str(e)}")
            # Fall back to simpler strategy
            return self._fallback_selection()
    
    def record_routing_outcome(
        self,
        backend_id: str,
        content_category: str,
        content_size_bytes: int,
        success: bool
    ):
        """
        Record the outcome of a routing decision to improve future decisions.
        
        Args:
            backend_id: Backend identifier
            content_category: Content category
            content_size_bytes: Content size in bytes
            success: Whether the routing was successful
        """
        if not self.enable_learning:
            return
        
        try:
            # Convert category
            try:
                category = ContentCategory(content_category)
            except ValueError:
                category = ContentCategory.OTHER
            
            # Create dummy result for recording
            result = RouteOptimizationResult(backend_id)
            result.content_analysis = {
                "category": category.value,
                "size_bytes": content_size_bytes
            }
            
            # Record outcome
            self.optimizer.record_outcome(result, success)
            
        except Exception as e:
            logger.error(f"Error recording routing outcome: {str(e)}")
    
    def get_routing_insights(self) -> Dict[str, Any]:
        """
        Get insights from the routing system.
        
        Returns:
            Dict with routing insights
        """
        try:
            return self.optimizer.generate_insights()
        except Exception as e:
            logger.error(f"Error generating routing insights: {str(e)}")
            return {}
    
    def _round_robin_selection(self) -> str:
        """Simple round-robin backend selection."""
        # This would be implemented with a counter in a real system
        import random
        return random.choice(self.available_backends)
    
    def _random_selection(self) -> str:
        """Random backend selection."""
        import random
        return random.choice(self.available_backends)
    
    def _fixed_selection(self) -> str:
        """Fixed backend selection."""
        # Use the first available backend or a configured default
        default_backend = self.config.get("default_backend", "ipfs")
        if default_backend in self.available_backends:
            return default_backend
        return self.available_backends[0] if self.available_backends else "ipfs"
    
    def _fallback_selection(self) -> str:
        """Fallback selection when adaptive routing fails."""
        return self._fixed_selection()


# Factory function to create a routing manager
def create_routing_manager(config: Optional[Dict[str, Any]] = None) -> RoutingManager:
    """
    Create a routing manager.
    
    Args:
        config: Optional configuration
        
    Returns:
        RoutingManager instance
    """
    return RoutingManager(config)