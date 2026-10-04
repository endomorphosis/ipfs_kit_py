#!/usr/bin/env python3
# ipfs_kit_py/mcp/routing/algorithms/cost_based.py

"""
Cost-Based Routing Strategy.

This module provides a routing strategy that selects the optimal backend based
on cost metrics such as storage cost, retrieval cost, and operation cost.
"""

import logging
from typing import Dict, List, Optional, Tuple

from ..router import (
    Backend, ContentType, OperationType,
    RouteMetrics, RoutingContext, RoutingDecision, RoutingStrategy
)
from ..metrics import CostCalculator

logger = logging.getLogger(__name__)

# Default cost weights for different operations
DEFAULT_COST_WEIGHTS = {
    OperationType.READ: {
        'retrieval_cost': 0.8,
        'operation_cost': 0.2,
        'storage_cost': 0.0
    },
    OperationType.WRITE: {
        'storage_cost': 0.7,
        'operation_cost': 0.3,
        'retrieval_cost': 0.0
    },
    OperationType.DELETE: {
        'operation_cost': 1.0,
        'storage_cost': 0.0,
        'retrieval_cost': 0.0
    },
    OperationType.LIST: {
        'operation_cost': 1.0,
        'storage_cost': 0.0,
        'retrieval_cost': 0.0
    },
    OperationType.STAT: {
        'operation_cost': 1.0,
        'storage_cost': 0.0,
        'retrieval_cost': 0.0
    },
    OperationType.ARCHIVE: {
        'storage_cost': 0.8,
        'operation_cost': 0.2,
        'retrieval_cost': 0.0
    },
    OperationType.BACKUP: {
        'storage_cost': 0.8,
        'operation_cost': 0.2,
        'retrieval_cost': 0.0
    },
    OperationType.RESTORE: {
        'retrieval_cost': 0.8,
        'operation_cost': 0.2,
        'storage_cost': 0.0
    }
}


class CostBasedRouter(RoutingStrategy):
    """
    Routing strategy that selects backends based on cost considerations.
    
    This strategy considers:
    - Storage cost (per GB per month)
    - Retrieval cost (per GB)
    - Operation cost (per operation)
    - Operation type (read, write, etc.)
    - Content size
    """
    
    def __init__(self, cost_calculator: Optional[CostCalculator] = None,
                cost_weights: Optional[Dict] = None):
        """
        Initialize the cost-based router.
        
        Args:
            cost_calculator: Optional cost calculator
            cost_weights: Optional cost weights for different operations
        """
        self.cost_calculator = cost_calculator
        self.cost_weights = cost_weights or DEFAULT_COST_WEIGHTS
    
    def select_backend(self, context: RoutingContext,
                     available_backends: List[Backend],
                     metrics: Dict[Backend, RouteMetrics]) -> RoutingDecision:
        """
        Select a backend based on cost considerations.
        
        Args:
            context: Routing context
            available_backends: List of available backends
            metrics: Metrics for each backend
            
        Returns:
            RoutingDecision: The routing decision
        """
        if not available_backends:
            raise ValueError("No backends available for cost-based routing")
        
        # Determine operation type
        operation = context.operation
        
        # Get cost weights for this operation
        weights = self.cost_weights.get(operation, self.cost_weights[OperationType.READ])
        
        # Calculate weighted costs for each backend
        backend_costs = {}
        for backend in available_backends:
            if backend in metrics:
                backend_metrics = metrics[backend]
                weighted_cost = self._calculate_weighted_cost(backend_metrics, weights, context)
                backend_costs[backend] = weighted_cost
            else:
                # If no metrics are available, assign a high cost
                backend_costs[backend] = float('inf')
        
        # Rank backends by cost (lower is better)
        ranked_backends = sorted(backend_costs.items(), key=lambda x: x[1])
        
        # Convert costs to scores (invert costs, higher is better)
        if len(ranked_backends) > 0:
            # Find the maximum finite cost
            max_cost = max([cost for _, cost in ranked_backends if cost != float('inf')] or [1.0])
            
            # Create scores: 1.0 for lowest cost, 0.0 for highest cost
            scored_backends = []
            for backend, cost in ranked_backends:
                if cost == float('inf'):
                    scored_backends.append((backend, 0.0))
                else:
                    # Normalize and invert: 1.0 - (cost / max_cost)
                    # This gives 1.0 for cost=0 and 0.0 for cost=max_cost
                    score = 1.0 - (cost / max_cost) if max_cost > 0 else 1.0
                    scored_backends.append((backend, score))
        else:
            scored_backends = [(backend, 0.0) for backend in available_backends]
        
        # Select the best backend (highest score / lowest cost)
        selected_backend, score = scored_backends[0] if scored_backends else (available_backends[0], 0.0)
        
        # Create metrics for the decision
        decision_metrics = RouteMetrics()
        
        # Add backend-specific metrics if available
        if selected_backend in metrics:
            decision_metrics = metrics[selected_backend]
        
        # Create the routing decision
        alternatives = [(b, s) for b, s in scored_backends if b != selected_backend]
        reason = f"Selected {selected_backend} based on cost optimization for {operation.value} operation"
        
        return RoutingDecision(
            backend=selected_backend,
            score=score,
            reason=reason,
            metrics=decision_metrics,
            alternatives=alternatives,
            context=context
        )
    
    def _calculate_weighted_cost(self, metrics: RouteMetrics, 
                              weights: Dict[str, float],
                              context: RoutingContext) -> float:
        """
        Calculate the weighted cost for a backend.
        
        Args:
            metrics: Metrics for the backend
            weights: Cost weights for the operation
            context: Routing context
            
        Returns:
            float: Weighted cost
        """
        storage_cost = metrics.storage_cost or 0.0
        retrieval_cost = metrics.retrieval_cost or 0.0
        operation_cost = metrics.operation_cost or 0.0
        
        # Scale costs by content size if available
        content_size_gb = context.content_size_bytes / (1024 * 1024 * 1024) if context.content_size_bytes else 1.0
        
        # Apply size scaling to storage and retrieval costs
        storage_cost_total = storage_cost * content_size_gb
        retrieval_cost_total = retrieval_cost * content_size_gb
        
        # Calculate weighted cost
        weighted_cost = (
            weights.get('storage_cost', 0.0) * storage_cost_total +
            weights.get('retrieval_cost', 0.0) * retrieval_cost_total +
            weights.get('operation_cost', 0.0) * operation_cost
        )
        
        return weighted_cost