"""
Adaptive Optimizer for MCP Routing

This module provides an adaptive optimization system that combines multiple
routing factors to make intelligent routing decisions for content across
different storage backends.

Key features:
1. Multi-factor optimization based on content, network, geography, and cost
2. Adaptive weights that learn from past routing outcomes
3. Content-aware backend selection
4. Performance and cost analytics
5. Comprehensive routing insights
"""

import os
import json
import logging
import time
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Tuple, Set, Union
from datetime import datetime
import threading
import random
import math
import copy
import statistics

# Try to import numpy for better statistical functions
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    logging.warning("NumPy not available. Using basic statistics functions.")

# Local imports
from .optimized_router import ( # type: ignore
    ContentType, RoutingStrategy, BackendMetrics,
    ConnectivityAnalyzer, ContentAnalyzer, RouterMetricsCollector
)
from .bandwidth_aware_router import NetworkAnalyzer, NetworkQualityLevel, NetworkMetricType # type: ignore
from .data_router import ContentCategory, RoutingPriority # type: ignore
from .geographic_router import GeographicRouter # type: ignore
from .cost_router import CostRouter # type: ignore

# Configure logger
logger = logging.getLogger(__name__)


class OptimizationFactor(str, Enum):
    """Factors that influence routing optimization decisions."""
    CONTENT_TYPE = "content_type"        # Content type suitability
    FILE_SIZE = "file_size"              # File size appropriateness
    NETWORK_LATENCY = "network_latency"  # Network latency optimization
    NETWORK_BANDWIDTH = "network_bandwidth"  # Network bandwidth optimization
    NETWORK_RELIABILITY = "network_reliability"  # Network reliability
    STORAGE_COST = "storage_cost"        # Storage cost optimization
    RETRIEVAL_COST = "retrieval_cost"    # Retrieval cost optimization
    GEOGRAPHIC_PROXIMITY = "geographic_proximity"  # Geographic proximity
    BACKEND_LOAD = "backend_load"        # Current backend load
    BACKEND_AVAILABILITY = "backend_availability"  # Backend availability
    HISTORICAL_PERFORMANCE = "historical_performance"  # Historical performance
    COMPLIANCE = "compliance"            # Compliance requirements


@dataclass
class OptimizationWeights:
    """Weights for different optimization factors."""
    weights: Dict[OptimizationFactor, float] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize default weights if not provided."""
        default_weights = {
            OptimizationFactor.CONTENT_TYPE: 0.15,
            OptimizationFactor.FILE_SIZE: 0.10,
            OptimizationFactor.NETWORK_LATENCY: 0.15,
            OptimizationFactor.NETWORK_BANDWIDTH: 0.10,
            OptimizationFactor.NETWORK_RELIABILITY: 0.15,
            OptimizationFactor.STORAGE_COST: 0.05,
            OptimizationFactor.RETRIEVAL_COST: 0.05,
            OptimizationFactor.GEOGRAPHIC_PROXIMITY: 0.10,
            OptimizationFactor.BACKEND_LOAD: 0.05,
            OptimizationFactor.BACKEND_AVAILABILITY: 0.05,
            OptimizationFactor.HISTORICAL_PERFORMANCE: 0.05,
            OptimizationFactor.COMPLIANCE: 0.00,  # Disabled by default
        }
        
        # Use provided weights or defaults
        for factor in OptimizationFactor:
            if factor not in self.weights:
                self.weights[factor] = default_weights.get(factor, 0.0)
    
    def adjust_for_priority(self, priority: RoutingPriority) -> None:
        """
        Adjust weights based on routing priority.
        
        Args:
            priority: Routing priority
        """
        # Save a copy of the current weights
        original_weights = copy.deepcopy(self.weights)
        
        # Adjust weights based on priority
        if priority == RoutingPriority.PERFORMANCE:
            # Increase performance-related weights
            self.weights[OptimizationFactor.NETWORK_LATENCY] *= 2.0
            self.weights[OptimizationFactor.NETWORK_BANDWIDTH] *= 2.0
            self.weights[OptimizationFactor.NETWORK_RELIABILITY] *= 1.5
            self.weights[OptimizationFactor.BACKEND_AVAILABILITY] *= 1.5
            
            # Decrease cost-related weights
            self.weights[OptimizationFactor.STORAGE_COST] *= 0.5
            self.weights[OptimizationFactor.RETRIEVAL_COST] *= 0.5
            
        elif priority == RoutingPriority.COST:
            # Increase cost-related weights
            self.weights[OptimizationFactor.STORAGE_COST] *= 3.0
            self.weights[OptimizationFactor.RETRIEVAL_COST] *= 3.0
            
            # Decrease performance-related weights
            self.weights[OptimizationFactor.NETWORK_BANDWIDTH] *= 0.7
            self.weights[OptimizationFactor.NETWORK_LATENCY] *= 0.7
            
        elif priority == RoutingPriority.RELIABILITY:
            # Increase reliability-related weights
            self.weights[OptimizationFactor.NETWORK_RELIABILITY] *= 3.0
            self.weights[OptimizationFactor.BACKEND_AVAILABILITY] *= 3.0
            self.weights[OptimizationFactor.HISTORICAL_PERFORMANCE] *= 2.0
            
        elif priority == RoutingPriority.GEOGRAPHIC:
            # Increase geographic-related weights
            self.weights[OptimizationFactor.GEOGRAPHIC_PROXIMITY] *= 4.0
            
        # Normalize weights to sum to 1.0
        self._normalize_weights()
        
        logger.debug(f"Adjusted weights for priority {priority}:")
        for factor, weight in self.weights.items():
            original = original_weights.get(factor, 0.0)
            logger.debug(f"  - {factor}: {original:.3f} -> {weight:.3f}")
    
    def _normalize_weights(self) -> None:
        """Normalize weights to sum to 1.0."""
        total = sum(self.weights.values())
        if total > 0:
            for factor in self.weights:
                self.weights[factor] /= total
    
    def update_weight(self, factor: OptimizationFactor, delta: float) -> None:
        """
        Update a weight by adding delta to the current value.
        
        Args:
            factor: Optimization factor
            delta: Change in weight (positive or negative)
        """
        self.weights[factor] = max(0.0, self.weights[factor] + delta)
        self._normalize_weights()
    
    def to_dict(self) -> Dict[str, float]:
        """Convert weights to a dictionary with string keys."""
        return {factor.value: weight for factor, weight in self.weights.items()}


@dataclass
class RouteOptimizationResult:
    """Result of a route optimization decision."""
    backend_id: str
    overall_score: float = 0.0
    factor_scores: Dict[OptimizationFactor, float] = field(default_factory=dict)
    content_analysis: Dict[str, Any] = field(default_factory=dict)
    network_analysis: Dict[str, Any] = field(default_factory=dict)
    geographic_analysis: Dict[str, Any] = field(default_factory=dict)
    cost_analysis: Dict[str, Any] = field(default_factory=dict)
    alternatives: List[Tuple[str, float]] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "backend_id": self.backend_id,
            "overall_score": self.overall_score,
            "factor_scores": {k.value: v for k, v in self.factor_scores.items()},
            "content_analysis": self.content_analysis,
            "network_analysis": self.network_analysis,
            "geographic_analysis": self.geographic_analysis,
            "cost_analysis": self.cost_analysis,
            "alternatives": self.alternatives,
            "timestamp": self.timestamp
        }
        return result


class LearningSystem:
    """Learning system that adjusts optimization weights based on outcomes."""
    
    def __init__(self, weights: OptimizationWeights, learning_rate: float = 0.01):
        """
        Initialize the learning system.
        
        Args:
            weights: Initial optimization weights
            learning_rate: Learning rate for weight adjustments
        """
        self.weights = weights
        self.learning_rate = learning_rate
        self.outcome_history: List[Tuple[RouteOptimizationResult, bool]] = []
        self.history_limit = 100
        self.lock = threading.RLock()
        self.enabled = True
    
    def record_outcome(self, result: RouteOptimizationResult, success: bool) -> None:
        """
        Record the outcome of a routing decision.
        
        Args:
            result: Routing optimization result
            success: Whether the routing decision was successful
        """
        if not self.enabled:
            return
        
        with self.lock:
            # Add to history
            self.outcome_history.append((result, success))
            
            # Trim history if needed
            if len(self.outcome_history) > self.history_limit:
                self.outcome_history = self.outcome_history[-self.history_limit:]
            
            # Learn from the outcome
            self._learn_from_outcome(result, success)
    
    def _learn_from_outcome(self, result: RouteOptimizationResult, success: bool) -> None:
        """
        Learn from a routing outcome by adjusting weights.
        
        Args:
            result: Routing optimization result
            success: Whether the routing decision was successful
        """
        # Skip learning if there are insufficient factor scores
        if not result.factor_scores:
            return
        
        # Get the most influential factors (highest scores)
        factor_scores = list(result.factor_scores.items())
        factor_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Determine adjustment direction based on success
        direction = 1.0 if success else -1.0
        
        # Adjust the weights of the top factors
        num_factors_to_adjust = min(3, len(factor_scores))
        for i in range(num_factors_to_adjust):
            factor, score = factor_scores[i]
            
            # Calculate adjustment (higher scores get larger adjustments)
            adjustment = direction * self.learning_rate * score
            
            # Update the weight
            self.weights.update_weight(factor, adjustment)
            
            logger.debug(f"Adjusted weight for {factor}: {adjustment:+.4f}")
    
    def get_factor_performance(self) -> Dict[OptimizationFactor, float]:
        """
        Calculate the performance of each factor based on history.
        
        Returns:
            Dictionary mapping factors to their success rates
        """
        with self.lock:
            if not self.outcome_history:
                return {}
            
            # Initialize counters
            success_count: Dict[OptimizationFactor, int] = {f: 0 for f in OptimizationFactor}
            total_count: Dict[OptimizationFactor, int] = {f: 0 for f in OptimizationFactor}
            
            # Process history
            for result, success in self.outcome_history:
                for factor, score in result.factor_scores.items():
                    # Only count factors that had a significant influence (score > 0.1)
                    if score > 0.1:
                        total_count[factor] += 1
                        if success:
                            success_count[factor] += 1
            
            # Calculate success rates
            success_rates = {}
            for factor in OptimizationFactor:
                if total_count[factor] > 0:
                    success_rates[factor] = success_count[factor] / total_count[factor]
            
            return success_rates


class AdaptiveOptimizer:
    """
    Adaptive optimizer that combines multiple routing factors to make
    intelligent routing decisions for content across different storage backends.
    """
    
    def __init__(self):
        """Initialize the adaptive optimizer."""
        self.config: Dict[str, Any] = {} # Explicitly initialize config
        # Initialize components
        self.weights = OptimizationWeights()
        self.learning_system = LearningSystem(self.weights)

        # Component analyzers
        self.network_analyzer = NetworkAnalyzer()
        self.content_analyzer = ContentAnalyzer()
        self.metrics_collector = RouterMetricsCollector()
        self.geographic_router = GeographicRouter() # Initialize GeographicRouter
        self.cost_router = CostRouter()

        # Load backend regions from config into GeographicRouter
        # Assuming config is passed during initialization or set later
        # This part might need adjustment based on how config is loaded in the main server
        # For now, assume self.config exists and contains the routing section
        if hasattr(self, 'config') and 'routing' in self.config and 'geographic' in self.config['routing']:
            geo_config = self.config['routing']['geographic']
            if 'backend_regions' in geo_config:
                for backend_id, region_id in geo_config['backend_regions'].items():
                    self.geographic_router.set_backend_region(backend_id, region_id)
                    logger.info(f"Loaded backend region mapping: {backend_id} -> {region_id}")

        # Backend performance data
        self.backend_performance: Dict[str, Dict[str, Any]] = {}
        
        # Client location cache
        self.client_location: Optional[Dict[str, float]] = None
        
        # Thread safety
        self.lock = threading.RLock()
        
        # Configuration
        self.learning_enabled = True
        
        logger.info("Initialized adaptive optimizer for intelligent routing.")
    
    def optimize_route(
        self,
        content: bytes,
        metadata: Optional[Dict[str, Any]] = None,
        available_backends: Optional[List[str]] = None,
        priority: Optional[RoutingPriority] = None,
        client_location: Optional[Dict[str, float]] = None
    ) -> RouteOptimizationResult:
        """
        Optimize the route for content based on multiple factors.
        
        Args:
            content: Content to route
            metadata: Content metadata
            available_backends: Available backends (if None, all known backends are used)
            priority: Routing priority (if None, balanced is used)
            client_location: Client geographic location (if None, server location is used)
            
        Returns:
            RouteOptimizationResult object
        """
        # Default metadata
        if metadata is None:
            metadata = {}
        
        # Get the list of available backends
        if available_backends is None or not available_backends:
            available_backends = list(self.backend_performance.keys())
        
        # If no backends are available, return an error
        if not available_backends:
            logger.error("No backends available for routing")
            return RouteOptimizationResult("none")
        
        # If only one backend is available, return it immediately
        if len(available_backends) == 1:
            return RouteOptimizationResult(available_backends[0])
        
        # Adjust weights based on priority
        weights = copy.deepcopy(self.weights)
        if priority is not None:
            weights.adjust_for_priority(priority)
        
        # Store client location if provided
        if client_location is not None:
            self.client_location = client_location
        
        # Analyze content
        content_analysis = self._analyze_content(content, metadata)
        
        # Score each backend
        backend_scores: Dict[str, Dict[OptimizationFactor, float]] = {}
        overall_scores: Dict[str, float] = {}
        
        for backend_id in available_backends:
            # Calculate factor scores for this backend
            factor_scores = self._calculate_factor_scores(
                backend_id, content_analysis, metadata
            )
            
            # Calculate weighted score
            weighted_score = sum(
                factor_scores.get(factor, 0.0) * weight
                for factor, weight in weights.weights.items()
            )
            
            # Store scores
            backend_scores[backend_id] = factor_scores
            overall_scores[backend_id] = weighted_score
        
        # Choose the best backend
        if not overall_scores:
            # Fallback to the first backend if we couldn't score any
            selected_backend = available_backends[0]
        else:
            selected_backend = max(overall_scores.items(), key=lambda x: x[1])[0]
        
        # Create result
        result = RouteOptimizationResult(selected_backend)
        result.overall_score = overall_scores.get(selected_backend, 0.0)
        result.factor_scores = backend_scores.get(selected_backend, {})
        result.content_analysis = content_analysis
        
        # Add network analysis
        result.network_analysis = self._get_network_analysis(selected_backend)
        
        # Add geographic analysis if available
        result.geographic_analysis = self._get_geographic_analysis(selected_backend)
        
        # Add cost analysis
        result.cost_analysis = self._get_cost_analysis(selected_backend, content_analysis)
        
        # Add alternatives
        alternatives = [
            (backend_id, score) for backend_id, score in overall_scores.items()
            if backend_id != selected_backend
        ]
        result.alternatives = sorted(alternatives, key=lambda x: x[1], reverse=True)
        
        return result
    
    def record_outcome(self, result: RouteOptimizationResult, success: bool) -> None:
        """
        Record the outcome of a routing decision to improve future decisions.
        
        Args:
            result: Result of a routing optimization
            success: Whether the routing was successful
        """
        if self.learning_enabled:
            self.learning_system.record_outcome(result, success)
    
    def collect_all_metrics(self, backend_ids: List[str]) -> None:
        """
        Collect metrics for all specified backends.
        
        Args:
            backend_ids: List of backend identifiers
        """
        for backend_id in backend_ids:
            # Get baseline backend performance
            self._collect_backend_metrics(backend_id)
            
            # Collect network metrics
            self._collect_network_metrics(backend_id)
    
    def _collect_backend_metrics(self, backend_id: str) -> None:
        """
        Collect metrics for a backend.
        
        Args:
            backend_id: Backend identifier
        """
        # This would typically retrieve metrics from the backend
        # For now, we'll use synthetic data
        with self.lock:
            if backend_id not in self.backend_performance:
                self.backend_performance[backend_id] = {
                    "availability": random.uniform(0.95, 0.999),
                    "load": random.uniform(0.1, 0.8),
                    "storage_cost_per_gb": random.uniform(0.001, 0.1),
                    "retrieval_cost_per_gb": random.uniform(0.0, 0.05),
                    "historical_success_rate": random.uniform(0.9, 0.99),
                    "last_updated": datetime.utcnow().isoformat()
                }
    
    def _collect_network_metrics(self, backend_id: str) -> None:
        """
        Collect network metrics for a backend.
        
        Args:
            backend_id: Backend identifier
        """
        # Use the network analyzer to collect metrics
        self.network_analyzer.collect_metrics_for_backend(backend_id)
    
    def _analyze_content(self, content: bytes, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze content to determine optimal routing.
        
        Args:
            content: Content bytes
            metadata: Content metadata
            
        Returns:
            Dictionary with content analysis results
        """
        result = {}
        
        # Determine size
        if content:
            size_bytes = len(content)
        else:
            size_bytes = metadata.get("size_bytes", 0)
        
        result["size_bytes"] = size_bytes
        
        # Content type from metadata if available
        if "content_type" in metadata:
            result["content_type"] = metadata["content_type"]
        elif "mime_type" in metadata:
            result["mime_type"] = metadata["mime_type"]
        
        # File extension from metadata if available
        if "filename" in metadata:
            filename = metadata["filename"]
            _, ext = os.path.splitext(filename)
            if ext:
                result["extension"] = ext.lower()
        
        # Determine content category
        try:
            if "category" in metadata:
                # Use provided category if available
                result["category"] = metadata["category"]
            else:
                # Otherwise determine based on size
                if size_bytes < 1_000_000:  # 1 MB
                    result["category"] = ContentCategory.SMALL_FILE.value
                elif size_bytes < 100_000_000:  # 100 MB
                    result["category"] = ContentCategory.MEDIUM_FILE.value
                elif size_bytes < 1_000_000_000:  # 1 GB
                    result["category"] = ContentCategory.LARGE_FILE.value
                else:
                    result["category"] = ContentCategory.LARGE_FILE.value
        except Exception as e:
            logger.warning(f"Error determining content category: {e}")
            result["category"] = ContentCategory.OTHER.value
        
        return result
    
    def _calculate_factor_scores(
        self,
        backend_id: str,
        content_analysis: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> Dict[OptimizationFactor, float]:
        """
        Calculate scores for each optimization factor.
        
        Args:
            backend_id: Backend identifier
            content_analysis: Content analysis results
            metadata: Content metadata
            
        Returns:
            Dictionary mapping factors to scores (0.0-1.0)
        """
        factor_scores = {}
        
        # Content type suitability score
        factor_scores[OptimizationFactor.CONTENT_TYPE] = self._calculate_content_type_score(
            backend_id, content_analysis
        )
        
        # File size appropriateness score
        factor_scores[OptimizationFactor.FILE_SIZE] = self._calculate_file_size_score(
            backend_id, content_analysis
        )
        
        # Network performance scores
        latency_score, bandwidth_score, reliability_score = self._calculate_network_scores(backend_id)
        factor_scores[OptimizationFactor.NETWORK_LATENCY] = latency_score
        factor_scores[OptimizationFactor.NETWORK_BANDWIDTH] = bandwidth_score
        factor_scores[OptimizationFactor.NETWORK_RELIABILITY] = reliability_score
        
        # Cost scores
        storage_cost_score, retrieval_cost_score = self._calculate_cost_scores(
            backend_id, content_analysis
        )
        factor_scores[OptimizationFactor.STORAGE_COST] = storage_cost_score
        factor_scores[OptimizationFactor.RETRIEVAL_COST] = retrieval_cost_score
        
        # Geographic proximity score
        factor_scores[OptimizationFactor.GEOGRAPHIC_PROXIMITY] = self._calculate_geographic_score(
            backend_id
        )
        
        # Backend availability and load scores
        availability_score, load_score = self._calculate_backend_health_scores(backend_id)
        factor_scores[OptimizationFactor.BACKEND_AVAILABILITY] = availability_score
        factor_scores[OptimizationFactor.BACKEND_LOAD] = load_score
        
        # Historical performance score
        factor_scores[OptimizationFactor.HISTORICAL_PERFORMANCE] = self._calculate_historical_score(
            backend_id, content_analysis
        )
        
        # Compliance score (if needed)
        if metadata.get("compliance_requirements"):
            factor_scores[OptimizationFactor.COMPLIANCE] = self._calculate_compliance_score(
                backend_id, metadata.get("compliance_requirements", [])
            )
        else:
            factor_scores[OptimizationFactor.COMPLIANCE] = 0.5  # Neutral score
        
        return factor_scores
    
    def _calculate_content_type_score(
        self,
        backend_id: str,
        content_analysis: Dict[str, Any]
    ) -> float:
        """
        Calculate content type suitability score.
        
        Args:
            backend_id: Backend identifier
            content_analysis: Content analysis results
            
        Returns:
            Score from 0.0 to 1.0
        """
        category = content_analysis.get("category", ContentCategory.OTHER.value)
        
        # Backend-specific content type preferences
        # This would typically come from configuration or learning
        # For now, use some reasonable defaults
        content_preferences = {
            "ipfs": {
                ContentCategory.SMALL_FILE.value: 0.9,
                ContentCategory.MEDIUM_FILE.value: 0.7,
                ContentCategory.LARGE_FILE.value: 0.4,
                ContentCategory.DOCUMENT.value: 0.8,
                ContentCategory.MEDIA.value: 0.6,
                ContentCategory.OTHER.value: 0.5
            },
            "filecoin": {
                ContentCategory.SMALL_FILE.value: 0.3,
                ContentCategory.MEDIUM_FILE.value: 0.6,
                ContentCategory.LARGE_FILE.value: 0.9,
                ContentCategory.DOCUMENT.value: 0.6,
                ContentCategory.MEDIA.value: 0.8,
                ContentCategory.OTHER.value: 0.5
            },
            "s3": {
                ContentCategory.SMALL_FILE.value: 0.7,
                ContentCategory.MEDIUM_FILE.value: 0.8,
                ContentCategory.LARGE_FILE.value: 0.8,
                ContentCategory.DOCUMENT.value: 0.7,
                ContentCategory.MEDIA.value: 0.8,
                ContentCategory.OTHER.value: 0.7
            },
            "storacha": {
                ContentCategory.SMALL_FILE.value: 0.8,
                ContentCategory.MEDIUM_FILE.value: 0.7,
                ContentCategory.LARGE_FILE.value: 0.5,
                ContentCategory.DOCUMENT.value: 0.7,
                ContentCategory.MEDIA.value: 0.6,
                ContentCategory.OTHER.value: 0.6
            },
            "huggingface": {
                ContentCategory.SMALL_FILE.value: 0.8,
                ContentCategory.MEDIUM_FILE.value: 0.7,
                ContentCategory.LARGE_FILE.value: 0.4,
                ContentCategory.DOCUMENT.value: 0.7,
                ContentCategory.MEDIA.value: 0.5,
                ContentCategory.OTHER.value: 0.6
            },
            "lassie": {
                ContentCategory.SMALL_FILE.value: 0.8,
                ContentCategory.MEDIUM_FILE.value: 0.7,
                ContentCategory.LARGE_FILE.value: 0.6,
                ContentCategory.DOCUMENT.value: 0.7,
                ContentCategory.MEDIA.value: 0.7,
                ContentCategory.OTHER.value: 0.6
            }
        }
        
        # Get preferences for this backend
        backend_preferences = content_preferences.get(backend_id, {})
        
        # Return the score for this category, or a default score
        return backend_preferences.get(category, 0.5)
    
    def _calculate_file_size_score(
        self,
        backend_id: str,
        content_analysis: Dict[str, Any]
    ) -> float:
        """
        Calculate file size appropriateness score.
        
        Args:
            backend_id: Backend identifier
            content_analysis: Content analysis results
            
        Returns:
            Score from 0.0 to 1.0
        """
        size_bytes = content_analysis.get("size_bytes", 0)
        
        # Backend-specific size thresholds
        # This would typically come from configuration or learning
        size_thresholds = {
            "ipfs": {
                "ideal_min": 0,
                "ideal_max": 10_000_000,  # 10 MB
                "acceptable_min": 0,
                "acceptable_max": 100_000_000  # 100 MB
            },
            "filecoin": {
                "ideal_min": 10_000_000,  # 10 MB
                "ideal_max": 10_000_000_000,  # 10 GB
                "acceptable_min": 1_000_000,  # 1 MB
                "acceptable_max": 100_000_000_000  # 100 GB
            },
            "s3": {
                "ideal_min": 0,
                "ideal_max": 1_000_000_000,  # 1 GB
                "acceptable_min": 0,
                "acceptable_max": 5_000_000_000  # 5 GB
            },
            "storacha": {
                "ideal_min": 0,
                "ideal_max": 100_000_000,  # 100 MB
                "acceptable_min": 0,
                "acceptable_max": 1_000_000_000  # 1 GB
            },
            "huggingface": {
                "ideal_min": 0,
                "ideal_max": 50_000_000,  # 50 MB
                "acceptable_min": 0,
                "acceptable_max": 500_000_000  # 500 MB
            },
            "lassie": {
                "ideal_min": 0,
                "ideal_max": 100_000_000,  # 100 MB
                "acceptable_min": 0,
                "acceptable_max": 1_000_000_000  # 1 GB
            }
        }
        
        # Get thresholds for this backend
        thresholds = size_thresholds.get(backend_id, {
            "ideal_min": 0,
            "ideal_max": 1_000_000_000,  # 1 GB
            "acceptable_min": 0,
            "acceptable_max": 10_000_000_000  # 10 GB
        })
        
        # Calculate score based on how well the size fits within the thresholds
        if size_bytes < thresholds["acceptable_min"] or size_bytes > thresholds["acceptable_max"]:
            return 0.0  # Outside acceptable range
        elif size_bytes >= thresholds["ideal_min"] and size_bytes <= thresholds["ideal_max"]:
            return 1.0  # Within ideal range
        elif size_bytes < thresholds["ideal_min"]:
            # Between acceptable_min and ideal_min
            return (size_bytes - thresholds["acceptable_min"]) / (thresholds["ideal_min"] - thresholds["acceptable_min"])
        else:
            # Between ideal_max and acceptable_max
            return (thresholds["acceptable_max"] - size_bytes) / (thresholds["acceptable_max"] - thresholds["ideal_max"])
    
    def _calculate_network_scores(self, backend_id: str) -> Tuple[float, float, float]:
        """
        Calculate network performance scores.
        
        Args:
            backend_id: Backend identifier
            
        Returns:
            Tuple of (latency_score, bandwidth_score, reliability_score)
        """
        # Default scores
        latency_score = 0.5
        bandwidth_score = 0.5
        reliability_score = 0.5
        
        # Get network quality from analyzer
        if hasattr(self.network_analyzer, "get_network_quality"):
            try:
                latency_quality = self.network_analyzer.get_network_quality(
                    backend_id, NetworkMetricType.LATENCY
                )
                bandwidth_quality = self.network_analyzer.get_network_quality(
                    backend_id, NetworkMetricType.BANDWIDTH
                )
                error_rate_quality = self.network_analyzer.get_network_quality(
                    backend_id, NetworkMetricType.ERROR_RATE
                )
                
                # Convert quality levels to scores
                quality_to_score = {
                    NetworkQualityLevel.EXCELLENT: 1.0,
                    NetworkQualityLevel.GOOD: 0.8,
                    NetworkQualityLevel.FAIR: 0.6,
                    NetworkQualityLevel.POOR: 0.3,
                    NetworkQualityLevel.BAD: 0.1,
                    NetworkQualityLevel.UNKNOWN: 0.5
                }
                
                latency_score = quality_to_score.get(latency_quality, 0.5)
                bandwidth_score = quality_to_score.get(bandwidth_quality, 0.5)
                reliability_score = quality_to_score.get(error_rate_quality, 0.5)
                
                # Invert latency score (lower latency is better)
                latency_score = 1.0 - ((1.0 - latency_score) * 0.8)
                
            except Exception as e:
                logger.warning(f"Error getting network quality: {e}")
        
        return latency_score, bandwidth_score, reliability_score
    
    def _calculate_cost_scores(
        self,
        backend_id: str,
        content_analysis: Dict[str, Any]
    ) -> Tuple[float, float]:
        """
        Calculate cost-related scores.
        
        Args:
            backend_id: Backend identifier
            content_analysis: Content analysis results
            
        Returns:
            Tuple of (storage_cost_score, retrieval_cost_score)
        """
        # Get costs from backend performance data
        storage_cost = self.backend_performance.get(
            backend_id, {}).get("storage_cost_per_gb", 0.01)
        retrieval_cost = self.backend_performance.get(
            backend_id, {}).get("retrieval_cost_per_gb", 0.005)
        
        # Cost ranges for normalization
        max_storage_cost = 0.1  # $0.10 per GB is considered expensive
        max_retrieval_cost = 0.05  # $0.05 per GB is considered expensive
        
        # Calculate scores (lower cost = higher score)
        storage_cost_score = 1.0 - min(storage_cost / max_storage_cost, 1.0)
        retrieval_cost_score = 1.0 - min(retrieval_cost / max_retrieval_cost, 1.0)
        
        return storage_cost_score, retrieval_cost_score
    
    def _calculate_geographic_score(self, backend_id: str) -> float:
        """
        Calculate geographic proximity score.
        
        Args:
            backend_id: Backend identifier
            
        Returns:
            Score from 0.0 to 1.0
        """
        # Default score if client or backend location is unknown
        score = 0.5

        # Use the GeographicRouter instance
        client_loc = self.geographic_router.client_location # Use the router's client location
        backend_loc = self.geographic_router.get_backend_location(backend_id)

        if client_loc and backend_loc:
            # Handle global backends - assign a reasonably good score
            if backend_loc.lat == 0.0 and backend_loc.lon == 0.0:
                 # Check if the backend is explicitly marked global in config
                 region_id = self.geographic_router.get_backend_region(backend_id)
                 if region_id and region_id.startswith("global"):
                     return 0.8 # Good score for global networks

            try:
                distance_km = self.geographic_router.get_distance(client_loc, backend_loc)

                # Normalize distance (e.g., 0-20000 km) to a score (1.0 -> 0.0)
                # Closer distance results in a higher score.
                max_relevant_distance = 20000.0 # Assume distances beyond this are equally "far"
                normalized_distance = min(distance_km / max_relevant_distance, 1.0)
                score = 1.0 - normalized_distance

            except Exception as e:
                logger.warning(f"Error calculating geographic distance for {backend_id}: {e}")
                score = 0.5 # Fallback score on error
        elif not client_loc:
             logger.debug(f"Client location unknown, using neutral geographic score for {backend_id}.")
             score = 0.5
        else: # Backend location unknown
             logger.debug(f"Backend location unknown for {backend_id}, using neutral geographic score.")
             score = 0.5

        return score
    
    def _calculate_backend_health_scores(self, backend_id: str) -> Tuple[float, float]:
        """
        Calculate backend health scores (availability and load).
        
        Args:
            backend_id: Backend identifier
            
        Returns:
            Tuple of (availability_score, load_score)
        """
        # Get data from backend performance
        availability = self.backend_performance.get(
            backend_id, {}).get("availability", 0.99)
        load = self.backend_performance.get(
            backend_id, {}).get("load", 0.5)
        
        # Calculate scores
        availability_score = min(1.0, availability)
        
        # Load score is inverse of load (lower load is better)
        load_score = 1.0 - min(1.0, load)
        
        return availability_score, load_score
    
    def _calculate_historical_score(
        self,
        backend_id: str,
        content_analysis: Dict[str, Any]
    ) -> float:
        """
        Calculate historical performance score.
        
        Args:
            backend_id: Backend identifier
            content_analysis: Content analysis results
            
        Returns:
            Score from 0.0 to 1.0
        """
        # Get historical success rate
        success_rate = self.backend_performance.get(
            backend_id, {}).get("historical_success_rate", 0.9)
        
        # Return success rate as the score
        return success_rate
    
    def _calculate_compliance_score(
        self,
        backend_id: str,
        compliance_requirements: List[str]
    ) -> float:
        """
        Calculate compliance score.
        
        Args:
            backend_id: Backend identifier
            compliance_requirements: List of compliance requirements
            
        Returns:
            Score from 0.0 to 1.0
        """
        # This would typically check if the backend supports the required compliance types
        # For now, use some reasonable defaults
        compliance_support = {
            "ipfs": ["public"],
            "filecoin": ["public", "proprietary"],
            "s3": ["public", "proprietary", "personal_data", "hipaa", "pci_dss", "sox"],
            "storacha": ["public", "proprietary"],
            "huggingface": ["public", "proprietary"],
            "lassie": ["public"]
        }
        
        # Get supported compliance types for this backend
        supported = compliance_support.get(backend_id, ["public"])
        
        # Calculate percentage of requirements that are supported
        if not compliance_requirements:
            return 1.0
        
        num_supported = sum(1 for req in compliance_requirements if req in supported)
        return num_supported / len(compliance_requirements)
    
    def _get_network_analysis(self, backend_id: str) -> Dict[str, Any]:
        """
        Get network analysis for a backend.
        
        Args:
            backend_id: Backend identifier
            
        Returns:
            Dictionary with network analysis
        """
        result = {}
        
        try:
            # Get metrics from network analyzer
            metrics = self.network_analyzer.get_metrics_for_backend(backend_id)
            
            # Get quality assessments
            latency_quality = self.network_analyzer.get_network_quality(
                backend_id, NetworkMetricType.LATENCY
            )
            bandwidth_quality = self.network_analyzer.get_network_quality(
                backend_id, NetworkMetricType.BANDWIDTH
            )
            error_rate_quality = self.network_analyzer.get_network_quality(
                backend_id, NetworkMetricType.ERROR_RATE
            )
            
            # Add to result
            result = {
                "metrics": metrics,
                "quality": {
                    "latency": latency_quality.value if latency_quality else "unknown",
                    "bandwidth": bandwidth_quality.value if bandwidth_quality else "unknown",
                    "error_rate": error_rate_quality.value if error_rate_quality else "unknown"
                }
            }
        except Exception as e:
            logger.warning(f"Error getting network analysis: {e}")
            result = {"error": str(e)}
        
        return result
    
    def _get_geographic_analysis(self, backend_id: str) -> Dict[str, Any]:
        """
        Get geographic analysis for a backend.
        
        Args:
            backend_id: Backend identifier
            
        Returns:
            Dictionary with geographic analysis
        """
        result = {}
        
        try:
            # This would typically get geographic information from a service
            # For now, use some reasonable defaults
            backend_regions = {
                "ipfs": "global",
                "filecoin": "global",
                "s3": "us-east-1",
                "storacha": "global",
                "huggingface": "eu-west-1",
                "lassie": "global"
            }
            
            result = {
                "backend_region": backend_regions.get(backend_id, "unknown"),
                "client_location": self.client_location,
                "distance_score": self._calculate_geographic_score(backend_id)
            }
        except Exception as e:
            logger.warning(f"Error getting geographic analysis: {e}")
            result = {"error": str(e)}
        
        return result
    
    def _get_cost_analysis(
        self, 
        backend_id: str,
        content_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Get cost analysis for a backend.
        
        Args:
            backend_id: Backend identifier
            content_analysis: Content analysis results
            
        Returns:
            Dictionary with cost analysis
        """
        result = {}
        
        try:
            # Get costs from backend performance data
            storage_cost_per_gb = self.backend_performance.get(
                backend_id, {}).get("storage_cost_per_gb", 0.01)
            retrieval_cost_per_gb = self.backend_performance.get(
                backend_id, {}).get("retrieval_cost_per_gb", 0.005)
            
            # Calculate estimated costs for this content
            size_gb = content_analysis.get("size_bytes", 0) / 1_000_000_000
            estimated_storage_cost = size_gb * storage_cost_per_gb
            estimated_retrieval_cost = size_gb * retrieval_cost_per_gb
            
            result = {
                "storage_cost_per_gb": storage_cost_per_gb,
                "retrieval_cost_per_gb": retrieval_cost_per_gb,
                "content_size_gb": size_gb,
                "estimated_storage_cost": estimated_storage_cost,
                "estimated_retrieval_cost": estimated_retrieval_cost,
                "estimated_total_cost": estimated_storage_cost + estimated_retrieval_cost
            }
        except Exception as e:
            logger.warning(f"Error getting cost analysis: {e}")
            result = {"error": str(e)}
        
        return result
    
    def generate_insights(self) -> Dict[str, Any]:
        """
        Generate insights about routing decisions and backend performance.
        
        Returns:
            Dictionary with routing insights
        """
        insights = {}
        
        try:
            # Get optimization weights
            insights["optimization_weights"] = self.weights.to_dict()
            
            # Get factor performance from learning system
            if self.learning_enabled:
                factor_performance = self.learning_system.get_factor_performance()
                insights["factor_performance"] = {
                    k.value: v for k, v in factor_performance.items()
                }
            
            # Get backend performance ranking
            insights["performance_ranking"] = [
                {"backend_id": backend_id, "score": score}
                for backend_id, score in self.metrics_collector.get_backend_performance_ranking()
            ]
            
            # Get backend cost ranking
            insights["cost_ranking"] = [
                {"backend_id": backend_id, "score": score}
                for backend_id, score in self.metrics_collector.get_backend_cost_ranking()
            ]
            
            # Get network quality ranking
            network_quality = {}
            for backend_id in self.backend_performance:
                try:
                    latency_quality = self.network_analyzer.get_network_quality(
                        backend_id, NetworkMetricType.LATENCY
                    )
                    bandwidth_quality = self.network_analyzer.get_network_quality(
                        backend_id, NetworkMetricType.BANDWIDTH
                    )
                    error_rate_quality = self.network_analyzer.get_network_quality(
                        backend_id, NetworkMetricType.ERROR_RATE
                    )
                    
                    # Convert quality levels to scores
                    quality_to_score = {
                        NetworkQualityLevel.EXCELLENT: 1.0,
                        NetworkQualityLevel.GOOD: 0.8,
                        NetworkQualityLevel.FAIR: 0.6,
                        NetworkQualityLevel.POOR: 0.3,
                        NetworkQualityLevel.BAD: 0.1,
                        NetworkQualityLevel.UNKNOWN: 0.5
                    }
                    
                    latency_score = quality_to_score.get(latency_quality, 0.5)
                    bandwidth_score = quality_to_score.get(bandwidth_quality, 0.5)
                    reliability_score = quality_to_score.get(error_rate_quality, 0.5)
                    
                    # Calculate overall score
                    overall_score = (latency_score * 0.4 + bandwidth_score * 0.4 + reliability_score * 0.2)
                    
                    # Determine quality level from score
                    quality_level = "unknown"
                    if overall_score >= 0.9:
                        quality_level = "excellent"
                    elif overall_score >= 0.7:
                        quality_level = "good"
                    elif overall_score >= 0.5:
                        quality_level = "fair"
                    elif overall_score >= 0.3:
                        quality_level = "poor"
                    else:
                        quality_level = "bad"
                    
                    network_quality[backend_id] = {
                        "score": overall_score,
                        "quality_level": quality_level,
                        "latency": latency_quality.value if latency_quality else "unknown",
                        "bandwidth": bandwidth_quality.value if bandwidth_quality else "unknown",
                        "reliability": error_rate_quality.value if error_rate_quality else "unknown"
                    }
                except Exception as e:
                    logger.warning(f"Error getting network quality for {backend_id}: {e}")
                    network_quality[backend_id] = {
                        "score": 0.5,
                        "quality_level": "unknown",
                        "error": str(e)
                    }
            
            insights["network_quality_ranking"] = network_quality
            
            # Get optimal backends by content type
            optimal_backends = {}
            for category in ContentCategory:
                category_value = category.value
                
                # Simulate optimization for this content type
                best_backend = None
                best_score = -1.0
                
                for backend_id in self.backend_performance:
                    content_score = self._calculate_content_type_score(
                        backend_id, {"category": category_value}
                    )
                    
                    # Use a simple formula to determine the best backend
                    score = content_score
                    
                    if score > best_score:
                        best_score = score
                        best_backend = backend_id
                
                optimal_backends[category_value] = [best_backend] if best_backend else []
            
            insights["optimal_backends_by_content"] = optimal_backends
            
            # Get load distribution
            load_distribution = {}
            total_load = 0.0
            
            for backend_id, data in self.backend_performance.items():
                load = data.get("load", 0.5)
                load_distribution[backend_id] = load
                total_load += load
            
            # Normalize load distribution
            if total_load > 0:
                for backend_id in load_distribution:
                    load_distribution[backend_id] /= total_load
            
            insights["load_distribution"] = load_distribution
            
        except Exception as e:
            logger.error(f"Error generating insights: {e}")
            insights["error"] = str(e)
        
        return insights


# Factory function to create an optimizer
def create_adaptive_optimizer() -> AdaptiveOptimizer:
    """Create an adaptive optimizer instance."""
    return AdaptiveOptimizer()
