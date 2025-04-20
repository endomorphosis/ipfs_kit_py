"""
Simple Routing Implementation for MCP Server

This is a simplified version of the Optimized Router that is fully functional.
It implements the core routing functionality with a focus on simplicity and reliability.

Key features:
1. Content-aware backend selection based on file type and size
2. Cost-based and performance-based routing strategies
3. Support for routing policies with backend preferences
4. Metrics collection for routing decisions

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements.
"""

import os
import json
import time
import logging
import threading
import random
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

# Configure logger
logger = logging.getLogger(__name__)


class ContentType(str, Enum):
    """Enum for content types with different routing strategies."""
    SMALL_FILE = "small_file"            # < 1 MB
    MEDIUM_FILE = "medium_file"          # 1 MB - 100 MB
    LARGE_FILE = "large_file"            # 100 MB - 1 GB
    VERY_LARGE_FILE = "very_large_file"  # > 1 GB
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    TEXT = "text"
    STRUCTURED_DATA = "structured_data"  # JSON, CSV, etc.
    BINARY = "binary"
    DIRECTORY = "directory"
    COLLECTION = "collection"            # Multiple related files
    ENCRYPTED = "encrypted"
    UNKNOWN = "unknown"


class RoutingStrategy(str, Enum):
    """Enum for data routing strategies."""
    COST_OPTIMIZED = "cost_optimized"
    PERFORMANCE_OPTIMIZED = "performance_optimized"
    REDUNDANCY_OPTIMIZED = "redundancy_optimized"
    BALANCED = "balanced"


@dataclass
class BackendMetrics:
    """Performance and cost metrics for a storage backend."""
    # Basic information
    backend_id: str
    backend_type: str
    
    # Performance metrics
    avg_read_latency_ms: float = 0.0
    avg_write_latency_ms: float = 0.0
    avg_throughput_mbps: float = 0.0
    success_rate: float = 1.0  # 1.0 = 100%
    
    # Cost metrics
    storage_cost_per_gb_month: float = 0.0
    read_cost_per_gb: float = 0.0
    write_cost_per_gb: float = 0.0
    
    # Availability metrics
    availability_percentage: float = 99.9
    
    # Last update time
    last_updated: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def update_metrics(self, metrics: Dict[str, Any]) -> None:
        """Update metrics with new values."""
        for key, value in metrics.items():
            if hasattr(self, key):
                setattr(self, key, value)
        
        self.last_updated = datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class RoutingPolicy:
    """Policy configuration for data routing decisions."""
    # Basic information
    id: str
    name: str
    description: Optional[str] = None
    enabled: bool = True
    
    # Primary routing strategy
    strategy: RoutingStrategy = RoutingStrategy.BALANCED
    
    # Content type specific routing
    content_type_routing: Dict[ContentType, RoutingStrategy] = field(default_factory=dict)
    
    # Performance thresholds
    min_throughput_mbps: Optional[float] = None
    max_latency_ms: Optional[float] = None
    
    # Redundancy settings
    replication_factor: int = 1  # Number of copies across backends
    
    # Backend preferences
    preferred_backends: List[str] = field(default_factory=list)
    excluded_backends: List[str] = field(default_factory=list)
    
    # Creation and update timestamps
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    def update(self, policy_data: Dict[str, Any]) -> None:
        """Update policy with new values."""
        for key, value in policy_data.items():
            if hasattr(self, key):
                setattr(self, key, value)
        
        self.updated_at = datetime.utcnow().isoformat()


@dataclass
class RoutingDecision:
    """Result of a routing decision for content placement or retrieval."""
    # Decision details
    content_id: str
    content_type: ContentType
    operation_type: str  # "store", "retrieve", "replicate", "migrate"
    
    # Selected backends and rationale
    primary_backend_id: str
    backup_backend_ids: List[str] = field(default_factory=list)
    
    # Factors influencing the decision
    strategy_used: RoutingStrategy = RoutingStrategy.BALANCED
    decision_factors: Dict[str, float] = field(default_factory=dict)  # Factor name -> weight
    
    # Decision metadata
    policy_id: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class ContentAnalyzer:
    """Analyzes content to determine optimal routing."""
    
    def __init__(self):
        """Initialize the content analyzer."""
        self._mime_type_mapping: Dict[str, ContentType] = {
            # Images
            'image/jpeg': ContentType.IMAGE,
            'image/png': ContentType.IMAGE,
            'image/gif': ContentType.IMAGE,
            'image/webp': ContentType.IMAGE,
            'image/svg+xml': ContentType.IMAGE,
            
            # Videos
            'video/mp4': ContentType.VIDEO,
            'video/webm': ContentType.VIDEO,
            'video/ogg': ContentType.VIDEO,
            'video/quicktime': ContentType.VIDEO,
            
            # Audio
            'audio/mpeg': ContentType.AUDIO,
            'audio/ogg': ContentType.AUDIO,
            'audio/wav': ContentType.AUDIO,
            'audio/webm': ContentType.AUDIO,
            
            # Text
            'text/plain': ContentType.TEXT,
            'text/html': ContentType.TEXT,
            'text/css': ContentType.TEXT,
            'text/javascript': ContentType.TEXT,
            'application/javascript': ContentType.TEXT,
            
            # Structured data
            'application/json': ContentType.STRUCTURED_DATA,
            'application/xml': ContentType.STRUCTURED_DATA,
            'text/csv': ContentType.STRUCTURED_DATA,
            'application/vnd.ms-excel': ContentType.STRUCTURED_DATA,
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ContentType.STRUCTURED_DATA,
            
            # Binary
            'application/octet-stream': ContentType.BINARY,
            'application/pdf': ContentType.BINARY,
            'application/zip': ContentType.BINARY,
            'application/x-tar': ContentType.BINARY,
            'application/x-gzip': ContentType.BINARY,
        }
    
    def analyze_content(self, content_metadata: Dict[str, Any]) -> ContentType:
        """
        Analyze content metadata to determine its type.
        
        Args:
            content_metadata: Metadata about the content
            
        Returns:
            ContentType enum value
        """
        # If we have a mime_type, use it
        mime_type = content_metadata.get('mime_type')
        if mime_type and mime_type in self._mime_type_mapping:
            return self._mime_type_mapping[mime_type]
        
        # Check if it's a directory
        if content_metadata.get('is_directory', False):
            return ContentType.DIRECTORY
        
        # Check if it's a collection
        if content_metadata.get('is_collection', False):
            return ContentType.COLLECTION
        
        # Check if it's encrypted
        if content_metadata.get('is_encrypted', False):
            return ContentType.ENCRYPTED
        
        # Determine by size
        size_bytes = content_metadata.get('size_bytes', 0)
        if size_bytes < 1_000_000:  # 1 MB
            return ContentType.SMALL_FILE
        elif size_bytes < 100_000_000:  # 100 MB
            return ContentType.MEDIUM_FILE
        elif size_bytes < 1_000_000_000:  # 1 GB
            return ContentType.LARGE_FILE
        else:
            return ContentType.VERY_LARGE_FILE


class RouterMetricsCollector:
    """Collects and analyzes metrics for routing decisions."""
    
    def __init__(self):
        """Initialize the metrics collector."""
        self._backend_metrics: Dict[str, BackendMetrics] = {}
        self._decision_history: List[RoutingDecision] = []
        self._history_limit = 1000  # Maximum number of decisions to keep
        self._lock = threading.RLock()
    
    def update_backend_metrics(self, backend_id: str, metrics: Dict[str, Any]) -> None:
        """
        Update metrics for a storage backend.
        
        Args:
            backend_id: Backend identifier
            metrics: Dictionary of metrics to update
        """
        with self._lock:
            if backend_id not in self._backend_metrics:
                backend_type = metrics.get('backend_type', 'unknown')
                self._backend_metrics[backend_id] = BackendMetrics(
                    backend_id=backend_id, 
                    backend_type=backend_type
                )
            
            self._backend_metrics[backend_id].update_metrics(metrics)
    
    def get_backend_metrics(self, backend_id: str) -> Optional[BackendMetrics]:
        """
        Get metrics for a storage backend.
        
        Args:
            backend_id: Backend identifier
            
        Returns:
            BackendMetrics object or None if not found
        """
        with self._lock:
            return self._backend_metrics.get(backend_id)
    
    def get_all_backend_metrics(self) -> Dict[str, BackendMetrics]:
        """
        Get metrics for all storage backends.
        
        Returns:
            Dictionary of backend_id -> BackendMetrics
        """
        with self._lock:
            return self._backend_metrics.copy()
    
    def record_decision(self, decision: RoutingDecision) -> None:
        """
        Record a routing decision.
        
        Args:
            decision: RoutingDecision object
        """
        with self._lock:
            self._decision_history.append(decision)
            
            # Trim history if it exceeds the limit
            if len(self._decision_history) > self._history_limit:
                self._decision_history = self._decision_history[-self._history_limit:]
    
    def get_decision_history(self, limit: Optional[int] = None) -> List[RoutingDecision]:
        """
        Get the history of routing decisions.
        
        Args:
            limit: Maximum number of decisions to return (most recent first)
            
        Returns:
            List of RoutingDecision objects
        """
        with self._lock:
            if limit is None:
                return self._decision_history.copy()
            return self._decision_history[-limit:].copy()
    
    def get_backend_performance_ranking(self) -> List[Tuple[str, float]]:
        """
        Get a ranking of backends by performance.
        
        Returns:
            List of (backend_id, score) tuples, sorted by score (descending)
        """
        with self._lock:
            scores = []
            
            for backend_id, metrics in self._backend_metrics.items():
                # Performance score is inverse to latency (lower is better for latency)
                # and proportional to throughput (higher is better)
                # We also consider success rate and availability
                if metrics.avg_read_latency_ms > 0:
                    latency_score = 1000 / metrics.avg_read_latency_ms
                else:
                    latency_score = 10  # Default if no latency data
                
                throughput_score = metrics.avg_throughput_mbps
                
                # Combine factors with weights
                score = (latency_score * 0.4 + 
                        throughput_score * 0.3 + 
                        metrics.success_rate * 20 + 
                        metrics.availability_percentage * 0.1)
                
                scores.append((backend_id, score))
            
            # Sort by score (descending)
            return sorted(scores, key=lambda x: x[1], reverse=True)
    
    def get_backend_cost_ranking(self) -> List[Tuple[str, float]]:
        """
        Get a ranking of backends by cost (lower is better).
        
        Returns:
            List of (backend_id, score) tuples, sorted by score (ascending)
        """
        with self._lock:
            scores = []
            
            for backend_id, metrics in self._backend_metrics.items():
                # Cost score is a weighted combination of storage and operation costs
                storage_cost = metrics.storage_cost_per_gb_month
                read_cost = metrics.read_cost_per_gb
                write_cost = metrics.write_cost_per_gb
                
                # If any cost is zero, set a small default to avoid division by zero
                storage_cost = max(storage_cost, 0.001)
                read_cost = max(read_cost, 0.0001)
                write_cost = max(write_cost, 0.0001)
                
                # Higher score = higher cost = worse
                score = (storage_cost * 0.6 + 
                        read_cost * 0.2 + 
                        write_cost * 0.2)
                
                scores.append((backend_id, score))
            
            # Sort by score (ascending - lower cost is better)
            return sorted(scores, key=lambda x: x[1])


class SimpleRouter:
    """
    Simple router for optimizing data placement and retrieval across backends.
    Implements routing strategies based on content type, cost, and performance.
    """
    
    def __init__(self):
        """Initialize the optimized router."""
        self._policies: Dict[str, RoutingPolicy] = {}
        self._default_policy = RoutingPolicy(
            id="default",
            name="Default Balanced Policy",
            strategy=RoutingStrategy.BALANCED
        )
        
        # Helper components
        self._content_analyzer = ContentAnalyzer()
        self._metrics_collector = RouterMetricsCollector()
        
        # Cache of backend endpoints
        self._backend_endpoints: Dict[str, str] = {}
        
        # Lock for thread safety
        self._lock = threading.RLock()
        
        logger.info("Initialized simple router.")
    
    def add_policy(self, policy: RoutingPolicy) -> None:
        """
        Add or update a routing policy.
        
        Args:
            policy: RoutingPolicy object
        """
        with self._lock:
            self._policies[policy.id] = policy
    
    def remove_policy(self, policy_id: str) -> bool:
        """
        Remove a routing policy.
        
        Args:
            policy_id: Policy identifier
            
        Returns:
            True if the policy was removed, False if it wasn't found
        """
        with self._lock:
            if policy_id in self._policies:
                del self._policies[policy_id]
                return True
            return False
    
    def get_policy(self, policy_id: str) -> Optional[RoutingPolicy]:
        """
        Get a routing policy.
        
        Args:
            policy_id: Policy identifier
            
        Returns:
            RoutingPolicy object or None if not found
        """
        with self._lock:
            return self._policies.get(policy_id)
    
    def list_policies(self) -> List[RoutingPolicy]:
        """
        List all routing policies.
        
        Returns:
            List of RoutingPolicy objects
        """
        with self._lock:
            return list(self._policies.values())
    
    def set_default_policy(self, policy_id: str) -> bool:
        """
        Set the default policy.
        
        Args:
            policy_id: Policy identifier
            
        Returns:
            True if successful, False if the policy wasn't found
        """
        with self._lock:
            if policy_id in self._policies:
                self._default_policy = self._policies[policy_id]
                return True
            return False
    
    def register_backend(self, backend_id: str, endpoint: str, 
                        metrics: Optional[Dict[str, Any]] = None) -> None:
        """
        Register a storage backend with the router.
        
        Args:
            backend_id: Backend identifier
            endpoint: Backend endpoint URL
            metrics: Initial metrics for the backend (optional)
        """
        with self._lock:
            self._backend_endpoints[backend_id] = endpoint
            
            if metrics:
                self._metrics_collector.update_backend_metrics(backend_id, metrics)
    
    def update_backend_metrics(self, backend_id: str, metrics: Dict[str, Any]) -> None:
        """
        Update metrics for a storage backend.
        
        Args:
            backend_id: Backend identifier
            metrics: Dictionary of metrics to update
        """
        self._metrics_collector.update_backend_metrics(backend_id, metrics)
    
    def get_route_for_content(self, content_id: str, content_metadata: Dict[str, Any],
                            operation: str, policy_id: Optional[str] = None) -> RoutingDecision:
        """
        Get the optimal route for content placement or retrieval.
        
        Args:
            content_id: Content identifier
            content_metadata: Metadata about the content
            operation: Operation type ("store", "retrieve", "replicate", "migrate")
            policy_id: Optional policy identifier to use (default: use default policy)
            
        Returns:
            RoutingDecision object with the routing decision
        """
        with self._lock:
            # Get the policy to use
            policy = self._default_policy
            if policy_id and policy_id in self._policies:
                policy = self._policies[policy_id]
            
            # Determine content type
            content_type = self._content_analyzer.analyze_content(content_metadata)
            
            # Get the routing strategy for this content type
            strategy = policy.strategy
            if content_type in policy.content_type_routing:
                strategy = policy.content_type_routing[content_type]
            
            # Get backend metrics
            all_backend_metrics = self._metrics_collector.get_all_backend_metrics()
            
            # Filter out excluded backends
            available_backends = {
                backend_id: metrics for backend_id, metrics in all_backend_metrics.items()
                if backend_id not in policy.excluded_backends
            }
            
            # If no backends are available, return an error
            if not available_backends:
                logger.error(f"No available backends for content {content_id} with strategy {strategy}")
                raise ValueError(f"No available backends for content {content_id}")
            
            # Select backends based on the routing strategy
            selected_backend_id = None
            backup_backend_ids = []
            decision_factors = {}
            
            # Preferred backends get a boost
            preferred_backends = {
                backend_id: metrics for backend_id, metrics in available_backends.items()
                if backend_id in policy.preferred_backends
            }
            
            # Choose routing strategy
            if strategy == RoutingStrategy.COST_OPTIMIZED:
                selected_backend_id, backup_backend_ids, decision_factors = self._get_cost_optimized_route(
                    available_backends, preferred_backends, content_type, operation, policy
                )
            elif strategy == RoutingStrategy.PERFORMANCE_OPTIMIZED:
                selected_backend_id, backup_backend_ids, decision_factors = self._get_performance_optimized_route(
                    available_backends, preferred_backends, content_type, operation, policy
                )
            elif strategy == RoutingStrategy.REDUNDANCY_OPTIMIZED:
                selected_backend_id, backup_backend_ids, decision_factors = self._get_redundancy_optimized_route(
                    available_backends, preferred_backends, content_type, operation, policy
                )
            else:  # Default to balanced
                selected_backend_id, backup_backend_ids, decision_factors = self._get_balanced_route(
                    available_backends, preferred_backends, content_type, operation, policy
                )
            
            # Create the routing decision
            decision = RoutingDecision(
                content_id=content_id,
                content_type=content_type,
                operation_type=operation,
                primary_backend_id=selected_backend_id,
                backup_backend_ids=backup_backend_ids,
                strategy_used=strategy,
                decision_factors=decision_factors,
                policy_id=policy.id
            )
            
            # Record the decision
            self._metrics_collector.record_decision(decision)
            
            return decision
    
    def _get_cost_optimized_route(self, available_backends: Dict[str, BackendMetrics],
                                preferred_backends: Dict[str, BackendMetrics],
                                content_type: ContentType, operation: str,
                                policy: RoutingPolicy) -> Tuple[str, List[str], Dict[str, float]]:
        """
        Get the cost-optimized route for content.
        
        Args:
            available_backends: Dictionary of available backends (backend_id -> metrics)
            preferred_backends: Dictionary of preferred backends (backend_id -> metrics)
            content_type: Type of content
            operation: Operation type ("store", "retrieve", "replicate", "migrate")
            policy: Routing policy to use
            
        Returns:
            Tuple of (primary_backend_id, backup_backend_ids, decision_factors)
        """
        decision_factors = {}
        
        # Get cost rankings
        rankings = self._metrics_collector.get_backend_cost_ranking()
        
        # Filter to only include available backends
        rankings = [(backend_id, score) for backend_id, score in rankings if backend_id in available_backends]
        
        if not rankings:
            # No available backends with cost data, return a random one
            backend_ids = list(available_backends.keys())
            if not backend_ids:
                raise ValueError("No available backends")
            
            selected_backend_id = random.choice(backend_ids)
            decision_factors["random_selection"] = 1.0
            return selected_backend_id, [], decision_factors
        
        # Calculate weighted scores considering various factors
        weighted_scores = []
        
        for backend_id, base_score in rankings:
            metrics = available_backends[backend_id]
            
            # Start with base cost score (inverse, since lower cost is better)
            # Higher cost_weight means lower cost (better)
            cost_weight = 1.0 / max(base_score, 0.001)  # Avoid division by zero
            
            # Adjust factor based on operation type
            if operation == "store":
                # Consider storage cost and write cost
                operation_cost = metrics.storage_cost_per_gb_month * 0.7 + metrics.write_cost_per_gb * 0.3
                operation_weight = 1.0 / max(operation_cost, 0.001)
            elif operation == "retrieve":
                # Consider read cost
                operation_cost = metrics.read_cost_per_gb
                operation_weight = 1.0 / max(operation_cost, 0.001)
            else:
                # Replicate or migrate - balance of read/write costs
                operation_cost = (metrics.read_cost_per_gb * 0.3 + metrics.write_cost_per_gb * 0.7)
                operation_weight = 1.0 / max(operation_cost, 0.001)
            
            # Preferred backend bonus
            preferred_bonus = 1.5 if backend_id in preferred_backends else 1.0
            
            # Combine factors
            total_score = cost_weight * 0.6 + operation_weight * 0.4
            total_score *= preferred_bonus
            
            weighted_scores.append((backend_id, total_score))
            
            # Record decision factors
            decision_factors[f"cost_weight_{backend_id}"] = cost_weight
            decision_factors[f"operation_weight_{backend_id}"] = operation_weight
            decision_factors[f"preferred_bonus_{backend_id}"] = preferred_bonus
            decision_factors[f"total_score_{backend_id}"] = total_score
        
        # Sort by total score (descending)
        weighted_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Get primary and backup backends
        selected_backend_id = weighted_scores[0][0]
        
        # Get backup backends if replication is needed
        backup_backend_ids = []
        if policy.replication_factor > 1 and len(weighted_scores) > 1:
            # Get the next N highest-scoring backends
            backup_count = min(policy.replication_factor - 1, len(weighted_scores) - 1)
            backup_backend_ids = [backend_id for backend_id, _ in weighted_scores[1:backup_count+1]]
        
        return selected_backend_id, backup_backend_ids, decision_factors
    
    def _get_performance_optimized_route(self, available_backends: Dict[str, BackendMetrics],
                                        preferred_backends: Dict[str, BackendMetrics],
                                        content_type: ContentType, operation: str,
                                        policy: RoutingPolicy) -> Tuple[str, List[str], Dict[str, float]]:
        """
        Get the performance-optimized route for content.
        
        Args:
            available_backends: Dictionary of available backends (backend_id -> metrics)
            preferred_backends: Dictionary of preferred backends (backend_id -> metrics)
            content_type: Type of content
            operation: Operation type ("store", "retrieve", "replicate", "migrate")
            policy: Routing policy to use
            
        Returns:
            Tuple of (primary_backend_id, backup_backend_ids, decision_factors)
        """
        decision_factors = {}
        
        # Get performance rankings
        rankings = self._metrics_collector.get_backend_performance_ranking()
        
        # Filter to only include available backends
        rankings = [(backend_id, score) for backend_id, score in rankings if backend_id in available_backends]
        
        if not rankings:
            # No available backends with performance data, return a random one
            backend_ids = list(available_backends.keys())
            if not backend_ids:
                raise ValueError("No available backends")
            
            selected_backend_id = random.choice(backend_ids)
            decision_factors["random_selection"] = 1.0
            return selected_backend_id, [], decision_factors
        
        # Calculate weighted scores considering various factors
        weighted_scores = []
        
        for backend_id, base_score in rankings:
            metrics = available_backends[backend_id]
            
            # Start with base performance score
            performance_weight = base_score
            
            # Adjust factor based on operation type
            if operation == "store":
                # For storing, write latency is more important
                if metrics.avg_write_latency_ms > 0:
                    latency_factor = 1000 / metrics.avg_write_latency_ms
                else:
                    latency_factor = 10
                
                operation_weight = latency_factor
            else:
                # For retrieving/replicating/migrating, read latency is more important
                if metrics.avg_read_latency_ms > 0:
                    latency_factor = 1000 / metrics.avg_read_latency_ms
                else:
                    latency_factor = 10
                
                operation_weight = latency_factor
            
            # Apply throughput factor - higher is better
            throughput_factor = metrics.avg_throughput_mbps / 10.0  # Normalize
            
            # Preferred backend bonus
            preferred_bonus = 1.5 if backend_id in preferred_backends else 1.0
            
            # Check policy thresholds
            threshold_factor = 1.0
            
            if policy.min_throughput_mbps is not None and metrics.avg_throughput_mbps < policy.min_throughput_mbps:
                threshold_factor *= 0.5  # Penalize backends that don't meet minimum throughput
            
            if policy.max_latency_ms is not None:
                if operation == "store" and metrics.avg_write_latency_ms > policy.max_latency_ms:
                    threshold_factor *= 0.5  # Penalize backends that exceed maximum latency
                elif metrics.avg_read_latency_ms > policy.max_latency_ms:
                    threshold_factor *= 0.5
            
            # Combine factors
            total_score = (performance_weight * 0.4 + 
                          operation_weight * 0.4 + 
                          throughput_factor * 0.2)
            
            total_score *= preferred_bonus * threshold_factor
            
            weighted_scores.append((backend_id, total_score))
            
            # Record decision factors
            decision_factors[f"performance_weight_{backend_id}"] = performance_weight
            decision_factors[f"operation_weight_{backend_id}"] = operation_weight
            decision_factors[f"throughput_factor_{backend_id}"] = throughput_factor
            decision_factors[f"preferred_bonus_{backend_id}"] = preferred_bonus
            decision_factors[f"threshold_factor_{backend_id}"] = threshold_factor
            decision_factors[f"total_score_{backend_id}"] = total_score
        
        # Sort by total score (descending)
        weighted_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Get primary and backup backends
        selected_backend_id = weighted_scores[0][0]
        
        # Get backup backends if replication is needed
        backup_backend_ids = []
        if policy.replication_factor > 1 and len(weighted_scores) > 1:
            # Get the next N highest-scoring backends
            backup_count = min(policy.replication_factor - 1, len(weighted_scores) - 1)
            backup_backend_ids = [backend_id for backend_id, _ in weighted_scores[1:backup_count+1]]
        
        return selected_backend_id, backup_backend_ids, decision_factors
    
    def _get_redundancy_optimized_route(self, available_backends: Dict[str, BackendMetrics],
                                      preferred_backends: Dict[str, BackendMetrics],
                                      content_type: ContentType, operation: str,
                                      policy: RoutingPolicy) -> Tuple[str, List[str], Dict[str, float]]:
        """
        Get the redundancy-optimized route for content to maximize durability.
        
        Args:
            available_backends: Dictionary of available backends (backend_id -> metrics)
            preferred_backends: Dictionary of preferred backends (backend_id -> metrics)
            content_type: Type of content
            operation: Operation type ("store", "retrieve", "replicate", "migrate")
            policy: Routing policy to use
            
        Returns:
            Tuple of (primary_backend_id, backup_backend_ids, decision_factors)
        """
        decision_factors = {}
        
        # For redundancy optimization, availability and reliability are key
        weighted_scores = []
        
        for backend_id, metrics in available_backends.items():
            # Consider availability and success rate
            availability_factor = metrics.availability_percentage / 100.0
            success_factor = metrics.success_rate
            
            # Use different backend types for better redundancy
            backend_type_counts = {}
            for other_id, other_metrics in available_backends.items():
                if other_id != backend_id:
                    backend_type = other_metrics.backend_type
                    backend_type_counts[backend_type] = backend_type_counts.get(backend_type, 0) + 1
            
            # If we already have many backends of this type, lower the diversity factor
            diversity_factor = 1.0
            if metrics.backend_type in backend_type_counts:
                count = backend_type_counts[metrics.backend_type]
                diversity_factor = 1.0 / (count + 1)
            
            # Preferred backend bonus
            preferred_bonus = 1.5 if backend_id in preferred_backends else 1.0
            
            # Combine factors
            total_score = (availability_factor * 0.4 + 
                         success_factor * 0.4 + 
                         diversity_factor * 0.2)
            
            total_score *= preferred_bonus
            
            weighted_scores.append((backend_id, total_score))
            
            # Record decision factors
            decision_factors[f"availability_factor_{backend_id}"] = availability_factor
            decision_factors[f"success_factor_{backend_id}"] = success_factor
            decision_factors[f"diversity_factor_{backend_id}"] = diversity_factor
            decision_factors[f"preferred_bonus_{backend_id}"] = preferred_bonus
            decision_factors[f"total_score_{backend_id}"] = total_score
        
        # Sort by total score (descending)
        weighted_scores.sort(key=lambda x: x[1], reverse=True)
        
        if not weighted_scores:
            raise ValueError("No available backends")
        
        # For redundancy optimization, we always want multiple backends if possible
        if len(weighted_scores) >= policy.replication_factor:
            # Take the top N backends
            selected_backends = weighted_scores[:policy.replication_factor]
            selected_backend_id = selected_backends[0][0]
            backup_backend_ids = [backend_id for backend_id, _ in selected_backends[1:]]
        else:
            # Not enough backends for desired replication
            selected_backend_id = weighted_scores[0][0]
            backup_backend_ids = [backend_id for backend_id, _ in weighted_scores[1:]]
        
        return selected_backend_id, backup_backend_ids, decision_factors
    
    def _get_balanced_route(self, available_backends: Dict[str, BackendMetrics],
                          preferred_backends: Dict[str, BackendMetrics],
                          content_type: ContentType, operation: str,
                          policy: RoutingPolicy) -> Tuple[str, List[str], Dict[str, float]]:
        """
        Get a balanced route considering multiple factors.
        
        Args:
            available_backends: Dictionary of available backends (backend_id -> metrics)
            preferred_backends: Dictionary of preferred backends (backend_id -> metrics)
            content_type: Type of content
            operation: Operation type ("store", "retrieve", "replicate", "migrate")
            policy: Routing policy to use
            
        Returns:
            Tuple of (primary_backend_id, backup_backend_ids, decision_factors)
        """
        decision_factors = {}
        
        # Get cost and performance rankings
        cost_rankings = dict(self._metrics_collector.get_backend_cost_ranking())
        performance_rankings = dict(self._metrics_collector.get_backend_performance_ranking())
        
        weighted_scores = []
        
        for backend_id, metrics in available_backends.items():
            # Get base scores (if available)
            cost_score = cost_rankings.get(backend_id, 1.0)
            performance_score = performance_rankings.get(backend_id, 1.0)
            
            # Consider multiple factors with equal weights
            availability_factor = metrics.availability_percentage / 100.0
            success_factor = metrics.success_rate
            
            # Normalize cost score (lower is better, so invert)
            cost_factor = 1.0 / max(cost_score, 0.001)
            
            # Preferred backend bonus
            preferred_bonus = 1.5 if backend_id in preferred_backends else 1.0
            
            # Combine all factors equally
            total_score = (performance_score * 0.25 + 
                         cost_factor * 0.25 + 
                         availability_factor * 0.25 + 
                         success_factor * 0.25)
            
            total_score *= preferred_bonus
            
            weighted_scores.append((backend_id, total_score))
            
            # Record decision factors
            decision_factors[f"performance_score_{backend_id}"] = performance_score
            decision_factors[f"cost_factor_{backend_id}"] = cost_factor
            decision_factors[f"availability_factor_{backend_id}"] = availability_factor
            decision_factors[f"success_factor_{backend_id}"] = success_factor
            decision_factors[f"preferred_bonus_{backend_id}"] = preferred_bonus
            decision_factors[f"total_score_{backend_id}"] = total_score
        
        # Sort by total score (descending)
        weighted_scores.sort(key=lambda x: x[1], reverse=True)
        
        if not weighted_scores:
            raise ValueError("No available backends")
        
        # Get primary and backup backends
        selected_backend_id = weighted_scores[0][0]
        
        # Get backup backends if replication is needed
        backup_backend_ids = []
        if policy.replication_factor > 1 and len(weighted_scores) > 1:
            # Get the next N highest-scoring backends
            backup_count = min(policy.replication_factor - 1, len(weighted_scores) - 1)
            backup_backend_ids = [backend_id for backend_id, _ in weighted_scores[1:backup_count+1]]
        
        return selected_backend_id, backup_backend_ids, decision_factors
