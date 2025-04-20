#!/usr/bin/env python3
# ipfs_kit_py/mcp/routing/algorithms/composite.py

"""
Composite Routing Strategy.

This module provides a composite routing strategy that combines multiple
other strategies with configurable weights to make balanced routing decisions.
"""

import logging
from typing import Dict, List, Optional, Tuple, Any

from ..router import (
    Backend, ContentType, OperationType,
    RouteMetrics, RoutingContext, RoutingDecision, RoutingStrategy
)

logger = logging.getLogger(__name__)


class CompositeRouter(RoutingStrategy):
    """
    Combines multiple routing strategies with weighted scoring.
    
    This strategy allows for balanced decision-making by considering multiple
    factors simultaneously, such as content type, cost, geographic location,
    and performance metrics.
    """
    
    def __init__(self, strategies: Dict[str, Tuple[RoutingStrategy, float]]):
        """
        Initialize the composite router.
        
        Args:
            strategies: Dictionary mapping strategy names to (strategy, weight) tuples
                       The weights should sum to approximately 1.0
        """
        self.strategies = strategies
        
        # Normalize weights to ensure they sum to 1.0
        total_weight = sum(weight for _, weight in strategies.values())
        if total_weight > 0:
            self.strategies = {
                name: (strategy, weight / total_weight)
                for name, (strategy, weight) in strategies.items()
            }
        
        logger.info(f"Initialized composite router with {len(strategies)} strategies")
    
    def select_backend(self, context: RoutingContext,
                     available_backends: List[Backend],
                     metrics: Dict[Backend, RouteMetrics]) -> RoutingDecision:
        """
        Select a backend by combining multiple strategies.
        
        Args:
            context: Routing context
            available_backends: List of available backends
            metrics: Metrics for each backend
            
        Returns:
            RoutingDecision: The routing decision
        """
        if not available_backends:
            raise ValueError("No backends available for composite routing")
        
        # Dictionary to store cumulative scores for each backend
        cumulative_scores: Dict[Backend, float] = {backend: 0.0 for backend in available_backends}
        
        # Dictionary to store decisions from each strategy for the final reason
        strategy_decisions: Dict[str, RoutingDecision] = {}
        
        # Apply each strategy and accumulate scores
        for strategy_name, (strategy, weight) in self.strategies.items():
            try:
                # Get decision from this strategy
                decision = strategy.select_backend(context, available_backends, metrics)
                strategy_decisions[strategy_name] = decision
                
                # Add score for selected backend
                cumulative_scores[decision.backend] += decision.score * weight
                
                # Add scores for alternatives
                for alt_backend, alt_score in decision.alternatives:
                    if alt_backend in cumulative_scores:
                        cumulative_scores[alt_backend] += alt_score * weight
            
            except Exception as e:
                logger.warning(f"Strategy {strategy_name} failed: {e}")
                # Continue with other strategies
        
        # Rank backends by cumulative score
        ranked_backends = sorted(
            [(backend, score) for backend, score in cumulative_scores.items()],
            key=lambda x: x[1],
            reverse=True
        )
        
        # Select the backend with the highest cumulative score
        if not ranked_backends:
            # Fallback to first available backend if no scores
            selected_backend = available_backends[0]
            score = 0.0
            alternatives = []
        else:
            selected_backend, score = ranked_backends[0]
            alternatives = [(b, s) for b, s in ranked_backends[1:]]
        
        # Create detailed reason including individual strategy decisions
        reason_parts = [f"Selected {selected_backend} using composite strategy with weighted scores:"]
        
        for strategy_name, (strategy, weight) in self.strategies.items():
            if strategy_name in strategy_decisions:
                decision = strategy_decisions[strategy_name]
                reason_parts.append(
                    f"- {strategy_name} ({weight:.2f}): {decision.backend} "
                    f"(score: {decision.score:.2f})"
                )
        
        reason = "\n".join(reason_parts)
        
        # Create metrics for the decision
        decision_metrics = RouteMetrics()
        
        # Add backend-specific metrics if available
        if selected_backend in metrics:
            decision_metrics = metrics[selected_backend]
        
        # Add strategy contribution data to metrics
        strategy_contributions = {}
        for strategy_name, (_, weight) in self.strategies.items():
            if strategy_name in strategy_decisions:
                decision = strategy_decisions[strategy_name]
                backend_score = 0.0
                
                # Find score this strategy gave to the selected backend
                if decision.backend == selected_backend:
                    backend_score = decision.score
                else:
                    for alt_backend, alt_score in decision.alternatives:
                        if alt_backend == selected_backend:
                            backend_score = alt_score
                            break
                
                strategy_contributions[strategy_name] = {
                    'weight': weight,
                    'score': backend_score,
                    'contribution': backend_score * weight
                }
        
        decision_metrics.custom_metrics['strategy_contributions'] = strategy_contributions
        
        return RoutingDecision(
            backend=selected_backend,
            score=score,
            reason=reason,
            metrics=decision_metrics,
            alternatives=alternatives,
            context=context
        )
    
    def add_strategy(self, name: str, strategy: RoutingStrategy, weight: float) -> None:
        """
        Add a new strategy to the composite router.
        
        Args:
            name: Strategy name
            strategy: Strategy instance
            weight: Strategy weight
        """
        self.strategies[name] = (strategy, weight)
        
        # Renormalize weights
        total_weight = sum(w for _, w in self.strategies.values())
        if total_weight > 0:
            self.strategies = {
                n: (s, w / total_weight)
                for n, (s, w) in self.strategies.items()
            }
        
        logger.info(f"Added strategy {name} with weight {weight}")
    
    def remove_strategy(self, name: str) -> None:
        """
        Remove a strategy from the composite router.
        
        Args:
            name: Strategy name
        """
        if name in self.strategies:
            del self.strategies[name]
            
            # Renormalize weights
            total_weight = sum(w for _, w in self.strategies.values())
            if total_weight > 0:
                self.strategies = {
                    n: (s, w / total_weight)
                    for n, (s, w) in self.strategies.items()
                }
            
            logger.info(f"Removed strategy {name}")
    
    def adjust_weight(self, name: str, weight: float) -> None:
        """
        Adjust the weight of a strategy.
        
        Args:
            name: Strategy name
            weight: New weight
        """
        if name in self.strategies:
            strategy, _ = self.strategies[name]
            self.strategies[name] = (strategy, weight)
            
            # Renormalize weights
            total_weight = sum(w for _, w in self.strategies.values())
            if total_weight > 0:
                self.strategies = {
                    n: (s, w / total_weight)
                    for n, (s, w) in self.strategies.items()
                }
            
            logger.info(f"Adjusted weight for {name} to {weight}")
    
    def get_weights(self) -> Dict[str, float]:
        """
        Get the current weights for all strategies.
        
        Returns:
            Dict[str, float]: Dictionary mapping strategy names to weights
        """
        return {name: weight for name, (_, weight) in self.strategies.items()}