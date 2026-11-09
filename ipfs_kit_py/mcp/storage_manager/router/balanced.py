"""
Advanced Balanced Router for Optimized Data Routing

This module implements a sophisticated content router that combines
multiple routing strategies to make intelligent decisions about which
backend to use for different types of content and operations.
"""

import math
import logging
import threading
from typing import Dict, List, Any, Optional, Union, Tuple

from ..storage_types import StorageBackendType
from . import ContentRouter, RoutingStrategy
from .content_analyzer import get_instance as get_content_analyzer
from .cost_optimizer import get_instance as get_cost_optimizer
from .performance_tracker import get_instance as get_performance_tracker

# Configure logger
logger = logging.getLogger(__name__)


class BalancedRouter(ContentRouter):
    """
    Advanced balanced router that combines multiple routing strategies.
    
    This router makes intelligent decisions by combining insights from:
    1. Content type analysis
    2. Performance metrics
    3. Cost optimization
    4. Geographic routing
    5. Reliability metrics
    """
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        available_backends: Optional[List[StorageBackendType]] = None,
    ):
        """
        Initialize the balanced router.
        
        Args:
            config: Router configuration
            available_backends: List of available backend types
        """
        super().__init__(config, available_backends)
        
        # Initialize components
        self.content_analyzer = get_content_analyzer(self.config.get("content", {}))
        self.cost_optimizer = get_cost_optimizer(self.config.get("cost", {}))
        self.performance_tracker = get_performance_tracker()
        
        # Weight configuration for balanced strategy
        self.balance_weights = self.config.get("balance_weights", {
            "content": 0.25,  # Weight for content type score
            "performance": 0.20,  # Weight for performance score
            "cost": 0.15,  # Weight for cost score
            "reliability": 0.20,  # Weight for reliability score
            "preference": 0.20,  # Weight for backend preference
        })
        
        logger.info("Initialized balanced router with advanced strategies")
    
    def select_backend(
        self,
        request_data: Dict[str, Any],
    ) -> Tuple[Optional[StorageBackendType], Optional[str]]:
        """
        Select the best backend for a request using advanced strategies.
        
        Args:
            request_data: Dictionary with request data
            
        Returns:
            Tuple of (selected backend type, reason)
        """
        # Extract request data
        strategy = request_data.get("strategy", self.default_strategy)
        
        # If strategy is specified as string, convert to enum
        if strategy and isinstance(strategy, str):
            try:
                strategy = RoutingStrategy(strategy)
            except ValueError:
                # Invalid strategy, use default
                strategy = self.default_strategy
        
        # First check for explicit backend preference, content ID patterns, and cache
        base_result = super().select_backend(request_data)
        
        # If a decision was made in the base router, return it
        if base_result[0] is not None:
            return base_result
        
        # Use the appropriate strategy
        if strategy == RoutingStrategy.SIMPLE:
            return self._simple_strategy(request_data)
        elif strategy == RoutingStrategy.PERFORMANCE:
            return self._performance_strategy(request_data)
        elif strategy == RoutingStrategy.COST:
            return self._cost_strategy(request_data)
        elif strategy == RoutingStrategy.RELIABILITY:
            return self._reliability_strategy(request_data)
        elif strategy == RoutingStrategy.GEOGRAPHIC:
            return self._geographic_strategy(request_data)
        elif strategy == RoutingStrategy.CUSTOM:
            return self._custom_strategy(request_data)
        else:
            # Default to balanced strategy
            return self._balanced_strategy(request_data)
    
    def _performance_strategy(self, request_data: Dict[str, Any]) -> Tuple[Optional[StorageBackendType], str]:
        """
        Performance-based routing strategy.
        
        Args:
            request_data: Request data
            
        Returns:
            Tuple of (selected backend, reason)
        """
        operation = request_data.get("operation", "store")
        
        # Calculate performance scores for each backend
        scores = {}
        for backend in self.available_backends:
            # Get operation-specific performance score if available
            score = self.performance_tracker.get_operation_performance_score(backend, operation)
            scores[backend] = score
        
        # No scores available
        if not scores:
            return None, "no_scores"
        
        # Select backend with highest score
        best_backend = max(scores.items(), key=lambda x: x[1])
        return best_backend[0], f"performance_score:{best_backend[1]:.2f}"
    
    def _cost_strategy(self, request_data: Dict[str, Any]) -> Tuple[Optional[StorageBackendType], str]:
        """
        Cost-based routing strategy.
        
        Args:
            request_data: Request data
            
        Returns:
            Tuple of (selected backend, reason)
        """
        operation = request_data.get("operation", "store")
        size = request_data.get("size", 1024 * 1024)  # Default to 1MB if size not provided
        
        # Calculate cost scores for each backend
        scores = {}
        for backend in self.available_backends:
            score = self.cost_optimizer.get_cost_score(backend, size, operation)
            scores[backend] = score
        
        # No scores available
        if not scores:
            return None, "no_scores"
        
        # Select backend with highest score (lowest cost)
        best_backend = max(scores.items(), key=lambda x: x[1])
        return best_backend[0], f"cost_score:{best_backend[1]:.2f}"
    
    def _reliability_strategy(self, request_data: Dict[str, Any]) -> Tuple[Optional[StorageBackendType], str]:
        """
        Reliability-based routing strategy.
        
        Args:
            request_data: Request data
            
        Returns:
            Tuple of (selected backend, reason)
        """
        # Get most reliable backend
        reliability_scores = {}
        for backend in self.available_backends:
            backend_name = backend.value
            
            # Get error rate from performance tracker
            error_rate = self.performance_tracker.weighted_error_rate.get(backend_name, 0)
            
            # Convert to reliability score (1.0 - error_rate)
            reliability_scores[backend] = 1.0 - error_rate
        
        # No scores available, use default reliability preferences
        if not reliability_scores or all(score == 0 for score in reliability_scores.values()):
            # Use default reliability preferences
            default_reliability = {
                StorageBackendType.IPFS: 0.9,
                StorageBackendType.S3: 0.95,
                StorageBackendType.STORACHA: 0.85,
                StorageBackendType.FILECOIN: 0.8,
                StorageBackendType.HUGGINGFACE: 0.9,
                StorageBackendType.LASSIE: 0.85,
            }
            
            # Filter to available backends
            for backend in self.available_backends:
                if backend in default_reliability:
                    reliability_scores[backend] = default_reliability[backend]
        
        # Still no scores
        if not reliability_scores:
            return None, "no_scores"
        
        # Select backend with highest reliability score
        best_backend = max(reliability_scores.items(), key=lambda x: x[1])
        return best_backend[0], f"reliability_score:{best_backend[1]:.2f}"
    
    def _geographic_strategy(self, request_data: Dict[str, Any]) -> Tuple[Optional[StorageBackendType], str]:
        """
        Geographic routing strategy.
        
        Since we haven't implemented the geographic router component fully,
        this method falls back to a simplified approach based on backend preferences.
        
        Args:
            request_data: Request data
            
        Returns:
            Tuple of (selected backend, reason)
        """
        # Simplified geographic routing based on backend preferences
        # In a real implementation, this would use client IP, region mapping, etc.
        
        # For now, just use a simplified regional preference
        region_preferences = {
            "us": [StorageBackendType.S3, StorageBackendType.IPFS],
            "eu": [StorageBackendType.STORACHA, StorageBackendType.IPFS],
            "asia": [StorageBackendType.HUGGINGFACE, StorageBackendType.FILECOIN],
            "default": [StorageBackendType.IPFS, StorageBackendType.S3]
        }
        
        # Get region from request data or use default
        region = request_data.get("region", "default")
        
        # Get preferences for this region
        preferences = region_preferences.get(region, region_preferences["default"])
        
        # Find first available preferred backend
        for backend in preferences:
            if backend in self.available_backends:
                return backend, f"geo_preference:{region}"
        
        # No preferred backend available
        return None, "no_regional_preference"
    
    def _custom_strategy(self, request_data: Dict[str, Any]) -> Tuple[Optional[StorageBackendType], str]:
        """
        Custom routing strategy using pluggable functions.
        
        Args:
            request_data: Request data
            
        Returns:
            Tuple of (selected backend, reason)
        """
        # Get custom routing function from options
        options = request_data.get("options", {})
        custom_func = options.get("custom_router")
        
        # If function available, use it
        if callable(custom_func):
            try:
                result = custom_func(request_data, self.available_backends)
                
                # Check if result is proper tuple
                if isinstance(result, tuple) and len(result) == 2:
                    backend_name, reason = result
                    
                    # Convert to enum if string
                    if isinstance(backend_name, str):
                        try:
                            backend = StorageBackendType.from_string(backend_name)
                            if backend in self.available_backends:
                                return backend, f"custom:{reason}"
                        except ValueError:
                            pass
                    
                    # If backend is already enum
                    if isinstance(backend_name, StorageBackendType) and backend_name in self.available_backends:
                        return backend_name, f"custom:{reason}"
            except Exception as e:
                logger.warning(f"Error in custom routing function: {e}")
        
        # Fall back to balanced strategy
        return self._balanced_strategy(request_data)
    
    def _balanced_strategy(self, request_data: Dict[str, Any]) -> Tuple[Optional[StorageBackendType], str]:
        """
        Balanced routing strategy combining multiple factors.
        
        Args:
            request_data: Request data
            
        Returns:
            Tuple of (selected backend, reason)
        """
        content_type = request_data.get("content_type")
        filename = request_data.get("filename")
        size = request_data.get("size", 1024 * 1024)  # Default to 1MB if size not provided
        operation = request_data.get("operation", "store")
        
        # Get scores from different strategies
        scores = {backend: 0.0 for backend in self.available_backends}
        score_components = {backend: {} for backend in self.available_backends}
        
        # Calculate scores for each backend
        for backend in self.available_backends:
            # Content type score
            content_score = self.content_analyzer.get_content_type_score(backend, content_type, filename)
            score_components[backend]["content"] = content_score
            
            # Performance score
            perf_score = self.performance_tracker.get_operation_performance_score(backend, operation)
            score_components[backend]["performance"] = perf_score
            
            # Cost score
            cost_score = self.cost_optimizer.get_cost_score(backend, size, operation)
            score_components[backend]["cost"] = cost_score
            
            # Reliability score (inverse of error rate)
            error_rate = self.performance_tracker.weighted_error_rate.get(backend.value, 0)
            reliability_score = 1.0 - error_rate
            score_components[backend]["reliability"] = reliability_score
            
            # Custom preference factor
            preference_factor = self.backend_preferences.get(backend.value, 1.0)
            score_components[backend]["preference"] = preference_factor
            
            # Calculate weighted score using balance weights
            scores[backend] = (
                self.balance_weights.get("content", 0.25) * content_score +
                self.balance_weights.get("performance", 0.20) * perf_score +
                self.balance_weights.get("cost", 0.15) * cost_score +
                self.balance_weights.get("reliability", 0.20) * reliability_score +
                self.balance_weights.get("preference", 0.20) * preference_factor
            )
        
        # No scores available
        if not scores:
            return None, "no_scores"
        
        # Select backend with highest score
        best_backend = max(scores.items(), key=lambda x: x[1])
        backend, score = best_backend
        
        # Get score breakdown
        components = score_components[backend]
        reason_parts = [f"{k}:{v:.2f}" for k, v in components.items()]
        
        return backend, f"balanced_score:{score:.2f}_{','.join(reason_parts)}"
    
    def record_operation_result(
        self,
        backend: StorageBackendType,
        operation: str,
        latency: float,
        size: Optional[int] = None,
        success: bool = True,
    ):
        """
        Record the result of an operation for metrics collection.
        
        Args:
            backend: Backend used
            operation: Operation type (store, retrieve, etc.)
            latency: Operation latency in seconds
            size: Size of data in bytes
            success: Whether operation was successful
        """
        # Record in performance tracker
        self.performance_tracker.record_operation(
            backend_type=backend,
            operation_type=operation,
            latency=latency,
            size=size,
            success=success,
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get routing statistics.
        
        Returns:
            Dictionary of routing statistics
        """
        basic_stats = super().get_statistics()
        
        return {
            **basic_stats,
            "performance_stats": self.performance_tracker.get_statistics(),
            "content_analyzer": {
                "categories": list(self.content_analyzer.default_category_scores.keys()),
            },
            "cost_models": {
                backend: {
                    "storage_cost_per_gb_month": model.get("storage_cost_per_gb_month", 0),
                    "retrieval_cost_per_gb": model.get("retrieval_cost_per_gb", 0),
                }
                for backend, model in self.cost_optimizer.get_all_cost_models().items()
            },
            "balance_weights": self.balance_weights,
        }


# Singleton instance
_balanced_instance = None

def get_balanced_instance(
    config: Optional[Dict[str, Any]] = None,
    available_backends: Optional[List[StorageBackendType]] = None,
) -> BalancedRouter:
    """
    Get or create the singleton balanced router instance.
    
    Args:
        config: Router configuration
        available_backends: List of available backend types
        
    Returns:
        BalancedRouter instance
    """
    global _balanced_instance
    if _balanced_instance is None:
        _balanced_instance = BalancedRouter(config, available_backends)
    elif available_backends:
        _balanced_instance.update_available_backends(available_backends)
    return _balanced_instance