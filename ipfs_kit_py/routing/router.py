#!/usr/bin/env python3
# ipfs_kit_py/mcp/routing/router.py

"""
Core Router Implementation for Optimized Data Routing.

This module provides the main DataRouter class and supporting classes for
making intelligent routing decisions for data across different storage backends.
"""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Set, Callable, Union, TypeVar

logger = logging.getLogger(__name__)

# Type definitions
Backend = str  # Type alias for backend identifiers
Content = TypeVar('Content')  # Type variable for content data
MetricsCollector = TypeVar('MetricsCollector')  # Type variable for metrics collectors


class BackendType(Enum):
    """Types of storage backends."""
    IPFS = "IPFS"
    FILECOIN = "FILECOIN"
    S3 = "S3" 
    STORACHA = "STORACHA"
    HUGGINGFACE = "HUGGINGFACE"
    LASSIE = "LASSIE"
    LOCAL = "LOCAL"
    CUSTOM = "CUSTOM"


class ContentType(Enum):
    """Types of content for routing decisions."""
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    DATASET = "dataset"
    MODEL = "model"
    ARCHIVE = "archive"
    BINARY = "binary"
    UNKNOWN = "unknown"
    

class OperationType(Enum):
    """Types of operations for routing decisions."""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    LIST = "list"
    STAT = "stat"
    ARCHIVE = "archive"
    BACKUP = "backup"
    RESTORE = "restore"


@dataclass
class RouteMetrics:
    """Metrics used for routing decisions."""
    # Performance metrics
    latency_ms: Optional[float] = None  # Average latency in milliseconds
    throughput_mbps: Optional[float] = None  # Throughput in megabits per second
    success_rate: Optional[float] = None  # Success rate (0.0-1.0)
    availability: Optional[float] = None  # Availability (0.0-1.0)
    
    # Cost metrics
    storage_cost: Optional[float] = None  # Cost per GB per month
    retrieval_cost: Optional[float] = None  # Cost per GB retrieved
    operation_cost: Optional[float] = None  # Cost per operation
    
    # Geographic metrics
    region: Optional[str] = None  # Geographic region
    distance_km: Optional[float] = None  # Distance in kilometers
    
    # Load metrics
    current_load: Optional[float] = None  # Current load (0.0-1.0)
    queue_depth: Optional[int] = None  # Number of pending operations
    
    # Content metrics
    content_size_bytes: Optional[int] = None  # Size in bytes
    content_type: Optional[ContentType] = None  # Type of content
    
    # Custom metrics
    custom_metrics: Dict[str, Any] = field(default_factory=dict)  # Custom metrics
    
    def get_metric(self, name: str, default: Any = None) -> Any:
        """
        Get a metric by name.
        
        Args:
            name: Name of the metric
            default: Default value if metric does not exist
            
        Returns:
            Any: The metric value or default
        """
        if hasattr(self, name):
            return getattr(self, name)
        return self.custom_metrics.get(name, default)
    
    def set_metric(self, name: str, value: Any) -> None:
        """
        Set a metric by name.
        
        Args:
            name: Name of the metric
            value: Value to set
        """
        if hasattr(self, name):
            setattr(self, name, value)
        else:
            self.custom_metrics[name] = value
    
    def as_dict(self) -> Dict[str, Any]:
        """
        Convert metrics to a dictionary.
        
        Returns:
            Dict[str, Any]: Dictionary of metrics
        """
        result = {}
        for key, value in self.__dict__.items():
            if key != 'custom_metrics' and value is not None:
                result[key] = value
        
        # Add custom metrics
        result.update(self.custom_metrics)
        
        return result


@dataclass
class RoutingContext:
    """Context for routing decisions."""
    operation: OperationType  # Type of operation being performed
    content_type: Optional[ContentType] = None  # Type of content
    content_size_bytes: Optional[int] = None  # Size of content in bytes
    user_id: Optional[str] = None  # ID of the user performing the operation
    region: Optional[str] = None  # Geographic region of the user
    timestamp: float = field(default_factory=time.time)  # Timestamp of the request
    priority: int = 0  # Priority of the request (higher is more important)
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional metadata
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """
        Get metadata by key.
        
        Args:
            key: Metadata key
            default: Default value if key does not exist
            
        Returns:
            Any: The metadata value or default
        """
        return self.metadata.get(key, default)
    
    def set_metadata(self, key: str, value: Any) -> None:
        """
        Set metadata by key.
        
        Args:
            key: Metadata key
            value: Value to set
        """
        self.metadata[key] = value


@dataclass
class RoutingDecision:
    """Result of a routing decision."""
    backend: Backend  # Selected backend
    score: float  # Score of the decision (higher is better)
    reason: str  # Reason for the decision
    metrics: RouteMetrics  # Metrics used for the decision
    alternatives: List[Tuple[Backend, float]] = field(default_factory=list)  # Alternative backends with scores
    context: Optional[RoutingContext] = None  # Context used for the decision
    
    @property
    def has_alternatives(self) -> bool:
        """Check if there are alternative backends."""
        return len(self.alternatives) > 0
    
    def get_best_alternative(self) -> Optional[Tuple[Backend, float]]:
        """
        Get the best alternative backend.
        
        Returns:
            Optional[Tuple[Backend, float]]: Best alternative or None
        """
        if not self.alternatives:
            return None
        return max(self.alternatives, key=lambda x: x[1])


class RoutingStrategy(ABC):
    """Abstract base class for routing strategies."""
    
    @abstractmethod
    def select_backend(self, context: RoutingContext, 
                     available_backends: List[Backend],
                     metrics: Dict[Backend, RouteMetrics]) -> RoutingDecision:
        """
        Select a backend based on the strategy.
        
        Args:
            context: Routing context
            available_backends: List of available backends
            metrics: Metrics for each backend
            
        Returns:
            RoutingDecision: The routing decision
        """
        pass


class DataRouter:
    """
    Main router class for making intelligent routing decisions.
    
    This class uses various strategies and metrics to determine the optimal
    backend for different types of data and operations.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the data router.
        
        Args:
            config: Router configuration
        """
        self.config = config or {}
        self.strategies: Dict[str, RoutingStrategy] = {}
        self.metrics_collectors: Dict[str, MetricsCollector] = {}
        self.primary_strategy: Optional[RoutingStrategy] = None
        self.available_backends: Set[Backend] = set()
        self.backend_info: Dict[Backend, Dict[str, Any]] = {}
        self.routing_history: List[RoutingDecision] = []
        self.max_history_size = self.config.get('max_history_size', 1000)
    
    def register_backend(self, backend: Backend, info: Dict[str, Any] = None) -> None:
        """
        Register a storage backend with the router.
        
        Args:
            backend: Backend identifier
            info: Additional backend information
        """
        self.available_backends.add(backend)
        self.backend_info[backend] = info or {}
        logger.info(f"Registered backend: {backend}")
    
    def unregister_backend(self, backend: Backend) -> None:
        """
        Unregister a storage backend from the router.
        
        Args:
            backend: Backend identifier
        """
        if backend in self.available_backends:
            self.available_backends.remove(backend)
            if backend in self.backend_info:
                del self.backend_info[backend]
            logger.info(f"Unregistered backend: {backend}")
    
    def add_strategy(self, name: str, strategy: RoutingStrategy) -> None:
        """
        Add a routing strategy.
        
        Args:
            name: Strategy name
            strategy: Strategy instance
        """
        self.strategies[name] = strategy
        logger.info(f"Added routing strategy: {name}")
    
    def remove_strategy(self, name: str) -> None:
        """
        Remove a routing strategy.
        
        Args:
            name: Strategy name
        """
        if name in self.strategies:
            del self.strategies[name]
            logger.info(f"Removed routing strategy: {name}")
    
    def set_primary_strategy(self, strategy: RoutingStrategy) -> None:
        """
        Set the primary routing strategy.
        
        Args:
            strategy: Strategy instance
        """
        self.primary_strategy = strategy
        logger.info(f"Set primary routing strategy: {strategy.__class__.__name__}")
    
    def register_metrics_collector(self, name: str, collector: MetricsCollector) -> None:
        """
        Register a metrics collector.
        
        Args:
            name: Collector name
            collector: Collector instance
        """
        self.metrics_collectors[name] = collector
        logger.info(f"Registered metrics collector: {name}")
    
    def unregister_metrics_collector(self, name: str) -> None:
        """
        Unregister a metrics collector.
        
        Args:
            name: Collector name
        """
        if name in self.metrics_collectors:
            del self.metrics_collectors[name]
            logger.info(f"Unregistered metrics collector: {name}")
    
    def collect_metrics(self, backends: Optional[List[Backend]] = None) -> Dict[Backend, RouteMetrics]:
        """
        Collect metrics for available backends.
        
        Args:
            backends: List of backends to collect metrics for, or None for all
            
        Returns:
            Dict[Backend, RouteMetrics]: Metrics for each backend
        """
        if backends is None:
            backends = list(self.available_backends)
        
        metrics: Dict[Backend, RouteMetrics] = {}
        
        for backend in backends:
            # Skip backends that are not registered
            if backend not in self.available_backends:
                continue
            
            # Create metrics object for this backend
            backend_metrics = RouteMetrics()
            
            # Collect metrics from each collector
            for name, collector in self.metrics_collectors.items():
                try:
                    if hasattr(collector, 'collect_metrics'):
                        collector_metrics = collector.collect_metrics(backend)
                        for metric_name, value in collector_metrics.items():
                            backend_metrics.set_metric(metric_name, value)
                except Exception as e:
                    logger.warning(f"Error collecting metrics for {backend} from {name}: {e}")
            
            metrics[backend] = backend_metrics
        
        return metrics
    
    def select_backend(self, context: RoutingContext, 
                     strategy_name: Optional[str] = None) -> RoutingDecision:
        """
        Select a backend for the given context.
        
        Args:
            context: Routing context
            strategy_name: Name of strategy to use, or None for primary
            
        Returns:
            RoutingDecision: The routing decision
            
        Raises:
            ValueError: If no backends are available or no strategy is set
        """
        if not self.available_backends:
            raise ValueError("No backends available for routing")
        
        # Choose strategy
        strategy = None
        if strategy_name is not None:
            if strategy_name in self.strategies:
                strategy = self.strategies[strategy_name]
            else:
                logger.warning(f"Strategy {strategy_name} not found, using primary")
        
        if strategy is None:
            strategy = self.primary_strategy
        
        if strategy is None:
            raise ValueError("No routing strategy available")
        
        # Collect metrics
        metrics = self.collect_metrics()
        
        # Make decision
        decision = strategy.select_backend(
            context=context,
            available_backends=list(self.available_backends),
            metrics=metrics
        )
        
        # Record decision in history
        self._record_decision(decision)
        
        return decision
    
    def _record_decision(self, decision: RoutingDecision) -> None:
        """
        Record a routing decision in history.
        
        Args:
            decision: The routing decision
        """
        self.routing_history.append(decision)
        
        # Trim history if it gets too large
        if len(self.routing_history) > self.max_history_size:
            self.routing_history = self.routing_history[-self.max_history_size:]
    
    def get_backend_info(self, backend: Backend) -> Dict[str, Any]:
        """
        Get information about a backend.
        
        Args:
            backend: Backend identifier
            
        Returns:
            Dict[str, Any]: Backend information
            
        Raises:
            KeyError: If backend is not registered
        """
        if backend not in self.backend_info:
            raise KeyError(f"Backend {backend} not registered")
        return self.backend_info[backend]
    
    def get_routing_history(self, limit: Optional[int] = None) -> List[RoutingDecision]:
        """
        Get routing decision history.
        
        Args:
            limit: Maximum number of decisions to return, or None for all
            
        Returns:
            List[RoutingDecision]: List of routing decisions
        """
        if limit is None or limit >= len(self.routing_history):
            return list(self.routing_history)
        return self.routing_history[-limit:]