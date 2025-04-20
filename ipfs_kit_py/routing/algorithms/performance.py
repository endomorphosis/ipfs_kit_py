#!/usr/bin/env python3
# ipfs_kit_py/mcp/routing/algorithms/performance.py

"""
Performance-Based Routing Strategy.

This module provides a routing strategy that selects the optimal backend based
on performance metrics such as latency, throughput, and availability.
"""

import logging
from typing import Dict, List, Optional, Tuple

from ..router import (
    Backend, ContentType, OperationType,
    RouteMetrics, RoutingContext, RoutingDecision, RoutingStrategy
)
from ..metrics import PerformanceMetrics

logger = logging.getLogger(__name__)

# Default performance weights for different operations
DEFAULT_PERFORMANCE_WEIGHTS = {
    OperationType.READ: {
        'latency_ms': 0.4,
        'throughput_mbps': 0.4,
        'success_rate': 0.1,
        'availability': 0.1
    },
    OperationType.WRITE: {
        'throughput_mbps': 0.5,
        'latency_ms': 0.2,
        'success_rate': 0.2,
        'availability': 0.1
    },
    OperationType.DELETE: {
        'latency_ms': 0.6,
        'success_rate': 0.3,
        'availability': 0.1,
        'throughput_mbps': 0.0
    },
    OperationType.LIST: {
        'latency_ms': 0.7,
        'success_rate': 0.2,
        'availability': 0.1,
        'throughput_mbps': 0.0
    },
    OperationType.STAT: {
        'latency_ms': 0.8,
        'success_rate': 0.1,
        'availability': 0.1,
        'throughput_mbps': 0.0
    },
    OperationType.ARCHIVE: {
        'throughput_mbps': 0.5,
        'success_rate': 0.3,
        'availability': 0.1,
        'latency_ms': 0.1
    },
    OperationType.BACKUP: {
        'throughput_mbps': 0.5,
        'success_rate': 0.3,
        'availability': 0.1,
        'latency_ms': 0.1
    },
    OperationType.RESTORE: {
        'throughput_mbps': 0.4,
        'latency_ms': 0.3,
        'success_rate': 0.2,
        'availability': 0.1
    }
}


class PerformanceRouter(RoutingStrategy):
    """
    Routing strategy that selects backends based on performance metrics.
    
    This strategy considers:
    - Latency (response time)
    - Throughput (bandwidth)
    - Success rate (reliability)
    - Availability (uptime)
    - Current load and queue depth
    """
    
    def __init__(self, performance_metrics: Optional[PerformanceMetrics] = None,
                performance_weights: Optional[Dict] = None):
        """
        Initialize the performance-based router.
        
        Args:
            performance_metrics: Optional performance metrics collector
            performance_weights: Optional performance weights for different operations
        """
        self.performance_metrics = performance_metrics
        self.performance_weights = performance_weights or DEFAULT_PERFORMANCE_WEIGHTS
    
    def select_backend(self, context: RoutingContext,
                     available_backends: List[Backend],
                     metrics: Dict[Backend, RouteMetrics]) -> RoutingDecision:
        """
        Select a backend based on performance metrics.
        
        Args:
            context: Routing context
            available_backends: List of available backends
            metrics: Metrics for each backend
            
        Returns:
            RoutingDecision: The routing decision
        """
        if not available_backends:
            raise ValueError("No backends available for performance-based routing")
        
        # Determine operation type
        operation = context.operation
        
        # Get performance weights for this operation
        weights = self.performance_weights.get(operation, self.performance_weights[OperationType.READ])
        
        # Calculate performance scores for each backend
        backend_scores = {}
        for backend in available_backends:
            if backend in metrics:
                backend_metrics = metrics[backend]
                performance_score = self._calculate_performance_score(backend_metrics, weights)
                backend_scores[backend] = performance_score
            else:
                # If no metrics are available, assign a neutral score
                backend_scores[backend] = 0.5
        
        # Rank backends by performance score (higher is better)
        ranked_backends = sorted(backend_scores.items(), key=lambda x: x[1], reverse=True)
        
        # Select the best backend (highest score)
        selected_backend, score = ranked_backends[0] if ranked_backends else (available_backends[0], 0.0)
        
        # Create metrics for the decision
        decision_metrics = RouteMetrics()
        
        # Add backend-specific metrics if available
        if selected_backend in metrics:
            decision_metrics = metrics[selected_backend]
        
        # Create the routing decision
        alternatives = [(b, s) for b, s in ranked_backends if b != selected_backend]
        reason = f"Selected {selected_backend} based on performance optimization for {operation.value} operation"
        
        return RoutingDecision(
            backend=selected_backend,
            score=score,
            reason=reason,
            metrics=decision_metrics,
            alternatives=alternatives,
            context=context
        )
    
    def _calculate_performance_score(self, metrics: RouteMetrics, 
                                  weights: Dict[str, float]) -> float:
        """
        Calculate a performance score for a backend.
        
        Args:
            metrics: Metrics for the backend
            weights: Performance weights for the operation
            
        Returns:
            float: Performance score (higher is better)
        """
        # Extract metrics (with defaults)
        latency_ms = metrics.latency_ms if metrics.latency_ms is not None else 100.0
        throughput_mbps = metrics.throughput_mbps if metrics.throughput_mbps is not None else 10.0
        success_rate = metrics.success_rate if metrics.success_rate is not None else 0.99
        availability = metrics.availability if metrics.availability is not None else 0.99
        current_load = metrics.current_load if metrics.current_load is not None else 0.5
        queue_depth = metrics.queue_depth if metrics.queue_depth is not None else 10
        
        # Normalize metrics to 0-1 range (1 is better)
        # For latency: lower is better, so invert the score
        latency_score = 1.0 - min(1.0, latency_ms / 1000.0)
        
        # For throughput: higher is better, cap at 1000 Mbps
        throughput_score = min(1.0, throughput_mbps / 1000.0)
        
        # Success rate and availability are already in 0-1 range
        
        # For load and queue: lower is better, so invert the score
        load_score = 1.0 - current_load
        queue_score = 1.0 - min(1.0, queue_depth / 100.0)
        
        # Apply weights to get composite score
        score = (
            weights.get('latency_ms', 0.0) * latency_score +
            weights.get('throughput_mbps', 0.0) * throughput_score +
            weights.get('success_rate', 0.0) * success_rate +
            weights.get('availability', 0.0) * availability
        )
        
        # Apply load and queue penalties (not weighted by operation type)
        # These factors are universally important regardless of operation
        load_penalty = 0.1 * (1.0 - load_score)
        queue_penalty = 0.1 * (1.0 - queue_score)
        
        # Final score with penalties applied
        final_score = score * (1.0 - load_penalty - queue_penalty)
        
        return max(0.0, min(1.0, final_score))  # Ensure score is in 0-1 range