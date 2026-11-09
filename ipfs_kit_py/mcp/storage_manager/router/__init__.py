"""
Optimized Data Routing for MCP Storage Manager

This module implements intelligent content-aware routing algorithms
for selecting the optimal storage backend for different types of content
and operations.

As specified in the MCP roadmap for Phase 1: Core Functionality Enhancements (Q3 2025).
"""

import logging
import time
import hashlib
import json
import re
import threading
from enum import Enum
from typing import Dict, List, Any, Optional, Union, BinaryIO, Tuple

from ..storage_types import StorageBackendType, ContentReference

# Configure logger
logger = logging.getLogger(__name__)


class RoutingStrategy(str, Enum):
    """Available routing strategies for backend selection."""
    
    SIMPLE = "simple"               # Basic routing based on file type and size
    PERFORMANCE = "performance"     # Route based on performance metrics
    COST = "cost"                   # Route to minimize storage costs
    RELIABILITY = "reliability"     # Route to maximize reliability
    GEOGRAPHIC = "geographic"       # Route based on geographic proximity
    BALANCED = "balanced"           # Balance between cost, performance, reliability
    ML_OPTIMIZED = "ml_optimized"   # Use machine learning to optimize routing
    CUSTOM = "custom"               # Use custom routing function


class RouterMetrics:
    """Collector for routing performance metrics."""
    
    def __init__(self):
        """Initialize the router metrics collector."""
        self.decision_times = {}  # Backend type -> list of decision times
        self.decision_counts = {}  # Backend type -> count
        self.strategy_usage = {}  # Strategy -> count
        self.cache_hits = 0
        self.cache_misses = 0
        self.total_requests = 0
        self.total_decision_time = 0
        self.lock = threading.RLock()
    
    def record_decision(self, backend_type: StorageBackendType, decision_time: float, strategy: RoutingStrategy):
        """
        Record a routing decision.
        
        Args:
            backend_type: Selected backend type
            decision_time: Time taken to make decision (seconds)
            strategy: Routing strategy used
        """
        with self.lock:
            backend_name = backend_type.value
            
            # Record decision time
            if backend_name not in self.decision_times:
                self.decision_times[backend_name] = []
            self.decision_times[backend_name].append(decision_time)
            
            # Record decision count
            self.decision_counts[backend_name] = self.decision_counts.get(backend_name, 0) + 1
            
            # Record strategy usage
            self.strategy_usage[strategy] = self.strategy_usage.get(strategy, 0) + 1
            
            # Update totals
            self.total_requests += 1
            self.total_decision_time += decision_time
    
    def record_cache_hit(self):
        """Record a routing cache hit."""
        with self.lock:
            self.cache_hits += 1
            self.total_requests += 1
    
    def record_cache_miss(self):
        """Record a routing cache miss."""
        with self.lock:
            self.cache_misses += 1
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get current routing statistics.
        
        Returns:
            Dictionary of routing statistics
        """
        with self.lock:
            # Calculate average decision times
            avg_times = {}
            for backend, times in self.decision_times.items():
                if times:
                    avg_times[backend] = sum(times) / len(times)
            
            # Calculate cache hit rate
            cache_hit_rate = 0
            if self.total_requests > 0:
                cache_hit_rate = self.cache_hits / self.total_requests
            
            # Calculate average decision time
            avg_decision_time = 0
            decision_count = sum(self.decision_counts.values())
            if decision_count > 0:
                avg_decision_time = self.total_decision_time / decision_count
            
            return {
                "total_requests": self.total_requests,
                "decision_counts": self.decision_counts,
                "average_decision_times": avg_times,
                "average_decision_time": avg_decision_time,
                "cache_hits": self.cache_hits,
                "cache_misses": self.cache_misses,
                "cache_hit_rate": cache_hit_rate,
                "strategy_usage": self.strategy_usage,
            }
    
    def reset(self):
        """Reset all metrics."""
        with self.lock:
            self.decision_times = {}
            self.decision_counts = {}
            self.strategy_usage = {}
            self.cache_hits = 0
            self.cache_misses = 0
            self.total_requests = 0
            self.total_decision_time = 0


class ContentRouter:
    """
    Base content router for optimized backend selection.
    
    This class implements basic routing logic and serves as a foundation
    for more advanced routing strategies.
    """
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        available_backends: Optional[List[StorageBackendType]] = None,
    ):
        """
        Initialize the content router.
        
        Args:
            config: Router configuration
            available_backends: List of available backend types
        """
        self.config = config or {}
        self.available_backends = available_backends or []
        
        # Default strategy
        self.default_strategy = RoutingStrategy(self.config.get("default_strategy", "balanced"))
        
        # Strategy weights
        self.strategy_weights = self.config.get("strategy_weights", {
            RoutingStrategy.SIMPLE.value: 0.1,
            RoutingStrategy.PERFORMANCE.value: 0.3,
            RoutingStrategy.COST.value: 0.2,
            RoutingStrategy.RELIABILITY.value: 0.2,
            RoutingStrategy.GEOGRAPHIC.value: 0.1,
            RoutingStrategy.BALANCED.value: 0.1,
        })
        
        # Backend override mapping (content ID pattern -> backend)
        self.backend_overrides = self.config.get("backend_overrides", {})
        
        # Backend preference factors
        self.backend_preferences = self.config.get("backend_preferences", {})
        
        # Decision cache
        self.decision_cache = {}
        self.cache_ttl = self.config.get("cache_ttl", 300)  # seconds
        
        # Metrics
        self.metrics = RouterMetrics()
        
        # Lock for thread safety
        self.lock = threading.RLock()
        
        # Initialize decision metrics
        self.decision_metrics = {backend.value: {"count": 0} for backend in self.available_backends}
    
    def update_available_backends(self, backends: List[StorageBackendType]):
        """
        Update the list of available backends.
        
        Args:
            backends: List of available backend types
        """
        with self.lock:
            self.available_backends = backends
            
            # Update decision metrics
            for backend in backends:
                if backend.value not in self.decision_metrics:
                    self.decision_metrics[backend.value] = {"count": 0}
    
    def select_backend(
        self,
        request_data: Dict[str, Any],
    ) -> Tuple[Optional[StorageBackendType], Optional[str]]:
        """
        Select the best backend for a request.
        
        Args:
            request_data: Dictionary with request data:
                - data: The data to be stored (optional)
                - content_type: MIME type of the content (optional)
                - size: Size of the content in bytes (optional)
                - preference: Preferred backend (optional)
                - filename: Filename (optional)
                - content_id: Content ID (optional)
                - operation: Operation type (store, retrieve, etc.)
                - client_ip: Client IP address (optional)
                - strategy: Routing strategy (optional)
                - options: Additional options (optional)
            
        Returns:
            Tuple of (selected backend type, reason)
        """
        # Extract request data
        data = request_data.get("data")
        content_type = request_data.get("content_type")
        size = request_data.get("size")
        preference = request_data.get("preference")
        filename = request_data.get("filename")
        content_id = request_data.get("content_id")
        operation = request_data.get("operation", "store")
        client_ip = request_data.get("client_ip")
        strategy = request_data.get("strategy", self.default_strategy)
        options = request_data.get("options", {})
        
        # Record start time for metrics
        start_time = time.time()
        
        # If preference is specified as string, convert to enum
        if preference and isinstance(preference, str):
            try:
                preference = StorageBackendType.from_string(preference)
            except ValueError:
                # Invalid backend name, ignore preference
                preference = None
        
        # If strategy is specified as string, convert to enum
        if strategy and isinstance(strategy, str):
            try:
                strategy = RoutingStrategy(strategy)
            except ValueError:
                # Invalid strategy, use default
                strategy = self.default_strategy
        
        # Check backend overrides for content ID
        if content_id:
            for pattern, backend_name in self.backend_overrides.items():
                if re.match(pattern, content_id):
                    try:
                        override_backend = StorageBackendType.from_string(backend_name)
                        if override_backend in self.available_backends:
                            # Record decision time
                            decision_time = time.time() - start_time
                            self.metrics.record_decision(override_backend, decision_time, strategy)
                            
                            # Record decision in metrics
                            with self.lock:
                                if override_backend.value in self.decision_metrics:
                                    self.decision_metrics[override_backend.value]["count"] += 1
                            
                            return override_backend, f"content_id_pattern:{pattern}"
                    except ValueError:
                        pass
        
        # Check if request matches a cached decision
        cache_key = self._generate_cache_key(request_data)
        cached_result = self._check_cache(cache_key)
        if cached_result:
            backend, reason = cached_result
            self.metrics.record_cache_hit()
            
            # Record decision in metrics
            with self.lock:
                if backend.value in self.decision_metrics:
                    self.decision_metrics[backend.value]["count"] += 1
            
            return backend, f"cached:{reason}"
        
        # Record cache miss
        self.metrics.record_cache_miss()
        
        # If preference is specified and available, use it
        if preference and preference in self.available_backends:
            # Record decision time
            decision_time = time.time() - start_time
            self.metrics.record_decision(preference, decision_time, strategy)
            
            # Record decision in metrics
            with self.lock:
                if preference.value in self.decision_metrics:
                    self.decision_metrics[preference.value]["count"] += 1
            
            # Cache decision
            self._cache_decision(cache_key, (preference, "user_preference"))
            
            return preference, "user_preference"
        
        # Select backend based on content type and size - simple strategy
        selected_backend, reason = self._simple_strategy(request_data)
        
        # If no backend was selected, use the first available
        if not selected_backend and self.available_backends:
            selected_backend = self.available_backends[0]
            reason = "first_available"
        elif not selected_backend:
            reason = "no_backends_available"
        
        # Record decision time
        decision_time = time.time() - start_time
        if selected_backend:
            self.metrics.record_decision(selected_backend, decision_time, strategy)
            
            # Record decision in metrics
            with self.lock:
                if selected_backend.value in self.decision_metrics:
                    self.decision_metrics[selected_backend.value]["count"] += 1
        
        # Cache decision
        if selected_backend:
            self._cache_decision(cache_key, (selected_backend, reason))
        
        return selected_backend, reason
    
    def _generate_cache_key(self, request_data: Dict[str, Any]) -> str:
        """
        Generate a cache key for a request.
        
        Args:
            request_data: Request data
            
        Returns:
            Cache key string
        """
        # Extract data for key
        content_type = request_data.get("content_type", "")
        size = request_data.get("size", 0)
        filename = request_data.get("filename", "")
        content_id = request_data.get("content_id", "")
        operation = request_data.get("operation", "store")
        
        # For content-based decisions, use a hash of metadata
        key_parts = [
            f"op:{operation}",
            f"type:{content_type}" if content_type else "",
            f"size:{size}" if size else "",
            f"file:{filename}" if filename else "",
            f"id:{content_id}" if content_id else "",
        ]
        
        # Filter out empty parts
        key_parts = [part for part in key_parts if part]
        
        # Create key
        return "_".join(key_parts)
    
    def _check_cache(self, cache_key: str) -> Optional[Tuple[StorageBackendType, str]]:
        """
        Check if a decision is cached.
        
        Args:
            cache_key: Cache key
            
        Returns:
            Cached decision or None
        """
        with self.lock:
            if cache_key not in self.decision_cache:
                return None
            
            backend, reason, timestamp = self.decision_cache[cache_key]
            
            # Check if cache entry is expired
            if time.time() - timestamp > self.cache_ttl:
                del self.decision_cache[cache_key]
                return None
            
            # Check if backend is still available
            if backend not in self.available_backends:
                del self.decision_cache[cache_key]
                return None
            
            return backend, reason
    
    def _cache_decision(self, cache_key: str, decision: Tuple[StorageBackendType, str]):
        """
        Cache a decision.
        
        Args:
            cache_key: Cache key
            decision: Decision tuple (backend, reason)
        """
        with self.lock:
            backend, reason = decision
            self.decision_cache[cache_key] = (backend, reason, time.time())
    
    def _simple_strategy(self, request_data: Dict[str, Any]) -> Tuple[Optional[StorageBackendType], str]:
        """
        Simple routing strategy based on content type and size.
        
        Args:
            request_data: Request data
            
        Returns:
            Tuple of (selected backend, reason)
        """
        content_type = request_data.get("content_type")
        size = request_data.get("size")
        
        # Simple content type routing rules
        if content_type:
            # Handle media files
            if content_type.startswith("image/"):
                # Images are good for IPFS
                if StorageBackendType.IPFS in self.available_backends:
                    return StorageBackendType.IPFS, "image_content"
            
            elif content_type.startswith("video/"):
                # Videos might be better for S3 or Filecoin
                if StorageBackendType.S3 in self.available_backends:
                    return StorageBackendType.S3, "video_content"
                elif StorageBackendType.FILECOIN in self.available_backends:
                    return StorageBackendType.FILECOIN, "video_content"
            
            elif content_type.startswith("audio/"):
                # Audio files can go to IPFS
                if StorageBackendType.IPFS in self.available_backends:
                    return StorageBackendType.IPFS, "audio_content"
            
            # Handle models and datasets
            elif "model" in content_type:
                # ML models go to HuggingFace
                if StorageBackendType.HUGGINGFACE in self.available_backends:
                    return StorageBackendType.HUGGINGFACE, "model_content"
            
            elif content_type in ["application/json", "text/csv"]:
                # Datasets can go to HuggingFace or IPFS
                if StorageBackendType.HUGGINGFACE in self.available_backends:
                    return StorageBackendType.HUGGINGFACE, "dataset_content"
                elif StorageBackendType.IPFS in self.available_backends:
                    return StorageBackendType.IPFS, "dataset_content"
        
        # Simple size-based routing
        if size is not None:
            # Very small files (< 100KB)
            if size < 100 * 1024:
                if StorageBackendType.IPFS in self.available_backends:
                    return StorageBackendType.IPFS, "small_file"
            
            # Medium files (100KB - 10MB)
            elif size < 10 * 1024 * 1024:
                if StorageBackendType.IPFS in self.available_backends:
                    return StorageBackendType.IPFS, "medium_file"
                elif StorageBackendType.S3 in self.available_backends:
                    return StorageBackendType.S3, "medium_file"
            
            # Large files (10MB - 1GB)
            elif size < 1024 * 1024 * 1024:
                if StorageBackendType.S3 in self.available_backends:
                    return StorageBackendType.S3, "large_file"
                elif StorageBackendType.FILECOIN in self.available_backends:
                    return StorageBackendType.FILECOIN, "large_file"
            
            # Very large files (> 1GB)
            else:
                if StorageBackendType.FILECOIN in self.available_backends:
                    return StorageBackendType.FILECOIN, "very_large_file"
                elif StorageBackendType.S3 in self.available_backends:
                    return StorageBackendType.S3, "very_large_file"
        
        # Default to IPFS if available
        if StorageBackendType.IPFS in self.available_backends:
            return StorageBackendType.IPFS, "default_ipfs"
        
        # No specific recommendation
        return None, "no_preference"
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get routing statistics.
        
        Returns:
            Dictionary of routing statistics
        """
        return {
            "router_metrics": self.metrics.get_statistics(),
            "decision_metrics": self.decision_metrics,
            "cache_size": len(self.decision_cache),
            "available_backends": [backend.value for backend in self.available_backends],
        }
    
    def clear_cache(self):
        """Clear the decision cache."""
        with self.lock:
            self.decision_cache.clear()


# Singleton instance
_instance = None

def get_instance(
    config: Optional[Dict[str, Any]] = None,
    available_backends: Optional[List[StorageBackendType]] = None,
) -> ContentRouter:
    """
    Get or create the singleton content router instance.
    
    Args:
        config: Router configuration
        available_backends: List of available backend types
        
    Returns:
        ContentRouter instance
    """
    global _instance
    if _instance is None:
        _instance = ContentRouter(config, available_backends)
    elif available_backends:
        _instance.update_available_backends(available_backends)
    return _instance