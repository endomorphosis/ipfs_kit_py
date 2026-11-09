#!/usr/bin/env python3
# ipfs_kit_py/mcp/routing/algorithms/geographic.py

"""
Geographic Routing Strategy.

This module provides a routing strategy that selects the optimal backend based
on geographic location to minimize latency and comply with data residency requirements.
"""

import logging
from typing import Dict, List, Optional, Tuple, Set

from ..router import (
    Backend, ContentType, OperationType,
    RouteMetrics, RoutingContext, RoutingDecision, RoutingStrategy
)
from ..metrics import GeographicOptimizer

logger = logging.getLogger(__name__)

# Common geographic regions
DEFAULT_REGIONS = {
    'us-east': {'name': 'US East', 'location': 'Virginia', 'coordinates': (37.7749, -122.4194)},
    'us-west': {'name': 'US West', 'location': 'Oregon', 'coordinates': (45.5051, -122.6750)},
    'eu-west': {'name': 'EU West', 'location': 'Ireland', 'coordinates': (53.3498, -6.2603)},
    'eu-central': {'name': 'EU Central', 'location': 'Frankfurt', 'coordinates': (50.1109, 8.6821)},
    'ap-northeast': {'name': 'Asia Pacific Northeast', 'location': 'Tokyo', 'coordinates': (35.6762, 139.6503)},
    'ap-southeast': {'name': 'Asia Pacific Southeast', 'location': 'Singapore', 'coordinates': (1.3521, 103.8198)},
    'sa-east': {'name': 'South America East', 'location': 'São Paulo', 'coordinates': (-23.5505, -46.6333)}
}

# Default backend regions
DEFAULT_BACKEND_REGIONS = {
    'IPFS': ['us-east', 'eu-west', 'ap-northeast'],
    'FILECOIN': ['us-east', 'eu-central', 'ap-southeast'],
    'S3': ['us-east', 'us-west', 'eu-west', 'eu-central', 'ap-northeast', 'ap-southeast', 'sa-east'],
    'STORACHA': ['us-east', 'eu-west'],
    'HUGGINGFACE': ['us-east', 'eu-west'],
    'LASSIE': ['us-east', 'eu-central']
}

# Data residency requirements
DEFAULT_RESIDENCY_REQUIREMENTS = {
    'EU': {
        'allowed_regions': ['eu-west', 'eu-central'],
        'blocked_regions': []
    },
    'US': {
        'allowed_regions': ['us-east', 'us-west'],
        'blocked_regions': []
    },
    'APAC': {
        'allowed_regions': ['ap-northeast', 'ap-southeast'],
        'blocked_regions': []
    }
}


class GeographicRouter(RoutingStrategy):
    """
    Routing strategy that selects backends based on geographic considerations.
    
    This strategy considers:
    - User's geographic region
    - Data residency requirements
    - Backend availability in different regions
    - Geographic distance
    """
    
    def __init__(self, geo_optimizer: Optional[GeographicOptimizer] = None,
                regions: Optional[Dict] = None,
                backend_regions: Optional[Dict] = None,
                residency_requirements: Optional[Dict] = None):
        """
        Initialize the geographic router.
        
        Args:
            geo_optimizer: Optional geographic optimizer
            regions: Optional geographic regions definition
            backend_regions: Optional backend regions mapping
            residency_requirements: Optional data residency requirements
        """
        self.geo_optimizer = geo_optimizer
        self.regions = regions or DEFAULT_REGIONS
        self.backend_regions = backend_regions or DEFAULT_BACKEND_REGIONS
        self.residency_requirements = residency_requirements or DEFAULT_RESIDENCY_REQUIREMENTS
    
    def select_backend(self, context: RoutingContext,
                     available_backends: List[Backend],
                     metrics: Dict[Backend, RouteMetrics]) -> RoutingDecision:
        """
        Select a backend based on geographic considerations.
        
        Args:
            context: Routing context
            available_backends: List of available backends
            metrics: Metrics for each backend
            
        Returns:
            RoutingDecision: The routing decision
        """
        if not available_backends:
            raise ValueError("No backends available for geographic routing")
        
        # Get user's region from context
        user_region = context.region
        
        # If region is not specified, try to determine it from geo optimizer
        if user_region is None and self.geo_optimizer:
            user_ip = context.get_metadata('client_ip')
            if user_ip:
                user_region = self.geo_optimizer.get_region_for_ip(user_ip)
        
        # If still no region, use a default (us-east)
        if user_region is None:
            user_region = 'us-east'
        
        # Check for data residency requirements
        residency_zone = context.get_metadata('residency_zone')
        allowed_regions = set()
        blocked_regions = set()
        
        if residency_zone and residency_zone in self.residency_requirements:
            req = self.residency_requirements[residency_zone]
            allowed_regions = set(req.get('allowed_regions', []))
            blocked_regions = set(req.get('blocked_regions', []))
        
        # Filter backends based on data residency if required
        eligible_backends = []
        for backend in available_backends:
            if self._is_backend_eligible(backend, allowed_regions, blocked_regions):
                eligible_backends.append(backend)
        
        # If no eligible backends after filtering, use all available backends
        # (this could be changed to raise an error depending on compliance requirements)
        if not eligible_backends:
            eligible_backends = available_backends
            logger.warning(
                f"No backends meet residency requirements for zone {residency_zone}. "
                f"Falling back to all available backends."
            )
        
        # Calculate proximity scores for eligible backends
        backend_scores = {}
        for backend in eligible_backends:
            backend_score = self._calculate_proximity_score(backend, user_region)
            backend_scores[backend] = backend_score
        
        # Rank backends by proximity score (higher is better)
        ranked_backends = sorted(backend_scores.items(), key=lambda x: x[1], reverse=True)
        
        # Select the best backend
        selected_backend, score = ranked_backends[0] if ranked_backends else (eligible_backends[0], 0.0)
        
        # Create metrics for the decision
        decision_metrics = RouteMetrics(region=user_region)
        
        # Add backend-specific metrics if available
        if selected_backend in metrics:
            backend_metrics = metrics[selected_backend]
            decision_metrics = backend_metrics
            decision_metrics.region = user_region
        
        # Create the routing decision
        alternatives = [(b, s) for b, s in ranked_backends if b != selected_backend]
        reason = f"Selected {selected_backend} based on geographic proximity to region {user_region}"
        
        if residency_zone:
            reason += f" with residency requirements for {residency_zone}"
        
        return RoutingDecision(
            backend=selected_backend,
            score=score,
            reason=reason,
            metrics=decision_metrics,
            alternatives=alternatives,
            context=context
        )
    
    def _is_backend_eligible(self, backend: Backend, 
                          allowed_regions: Set[str],
                          blocked_regions: Set[str]) -> bool:
        """
        Check if a backend is eligible based on data residency requirements.
        
        Args:
            backend: Backend to check
            allowed_regions: Set of allowed regions (empty means any region is allowed)
            blocked_regions: Set of blocked regions
            
        Returns:
            bool: True if the backend is eligible, False otherwise
        """
        # Get regions where this backend is available
        backend_regions = set(self.backend_regions.get(backend, []))
        
        # If no specific allowed regions, any region not in blocked list is allowed
        if not allowed_regions:
            # Check if any backend region is not in blocked regions
            return any(region not in blocked_regions for region in backend_regions)
        
        # Check if any backend region is in allowed regions
        return any(region in allowed_regions for region in backend_regions)
    
    def _calculate_proximity_score(self, backend: Backend, user_region: str) -> float:
        """
        Calculate a proximity score for a backend relative to a user region.
        
        Args:
            backend: Backend to score
            user_region: User's region
            
        Returns:
            float: Proximity score (higher is better/closer)
        """
        # Get regions where this backend is available
        backend_regions = self.backend_regions.get(backend, [])
        
        # If the backend is available in the user's region, give it the highest score
        if user_region in backend_regions:
            return 1.0
        
        # If geo optimizer is available, use it to calculate distances
        if self.geo_optimizer and user_region in self.regions:
            user_coords = self.regions[user_region].get('coordinates')
            if user_coords:
                # Calculate minimum distance to any backend region
                min_distance = float('inf')
                for region in backend_regions:
                    if region in self.regions:
                        region_coords = self.regions[region].get('coordinates')
                        if region_coords:
                            distance = self.geo_optimizer.calculate_distance(
                                user_coords, region_coords
                            )
                            min_distance = min(min_distance, distance)
                
                # Convert distance to score (closer is better)
                if min_distance != float('inf'):
                    # Scale distance to a score between 0 and 1
                    # Max distance on Earth is about 20,000 km
                    max_distance = 20000  # km
                    score = 1.0 - (min_distance / max_distance)
                    return max(0.0, score)
        
        # Fallback: Score based on number of regions
        # More regions generally means better global coverage
        num_regions = len(backend_regions)
        return min(0.5, num_regions / 10.0)  # Scale to max 0.5 for fallback method