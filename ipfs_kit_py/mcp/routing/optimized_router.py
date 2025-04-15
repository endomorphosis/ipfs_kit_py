#!/usr/bin/env python3
"""
Optimized Data Routing Module

This module implements intelligent content routing for the MCP server:
- Content-aware backend selection
- Cost-based routing algorithms
- Geographic optimization
- Bandwidth and latency analysis

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements.
"""

import os
import time
import json
import logging
import threading
import math
import uuid
import mimetypes
import hashlib
from enum import Enum
from typing import Dict, List, Tuple, Set, Optional, Union, Any, Callable
from collections import defaultdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mcp_router")

class RoutingStrategy(Enum):
    """Available routing strategies for backend selection."""
    RANDOM = "random"               # Random selection (for testing)
    ROUND_ROBIN = "round_robin"     # Simple round-robin selection
    CONTENT_TYPE = "content_type"   # Based on content type
    COST = "cost"                   # Based on cost optimization
    PERFORMANCE = "performance"     # Based on current performance
    AVAILABILITY = "availability"   # Based on availability
    GEOGRAPHIC = "geographic"       # Based on geographic proximity
    HYBRID = "hybrid"               # Combination of multiple factors
    CUSTOM = "custom"               # Custom routing function

class ContentCategory(Enum):
    """Content categories for routing decisions."""
    GENERIC = "generic"             # Generic/unknown content
    DOCUMENT = "document"           # Documents (pdf, doc, etc.)
    IMAGE = "image"                 # Images
    VIDEO = "video"                 # Video files
    AUDIO = "audio"                 # Audio files
    CODE = "code"                   # Source code
    DATASET = "dataset"             # Datasets
    MODEL = "model"                 # ML models
    CONTAINER = "container"         # Container images
    ARCHIVE = "archive"             # Archives (zip, tar, etc.)
    ENCRYPTED = "encrypted"         # Encrypted content
    
    @classmethod
    def from_mime_type(cls, mime_type: str) -> 'ContentCategory':
        """
        Determine content category from MIME type.
        
        Args:
            mime_type: MIME type string
            
        Returns:
            Corresponding ContentCategory
        """
        if not mime_type:
            return cls.GENERIC
            
        mime_type = mime_type.lower()
        
        if mime_type.startswith("image/"):
            return cls.IMAGE
        elif mime_type.startswith("video/"):
            return cls.VIDEO
        elif mime_type.startswith("audio/"):
            return cls.AUDIO
        elif mime_type.startswith("text/"):
            if any(x in mime_type for x in ["javascript", "css", "html", "xml", "json"]):
                return cls.CODE
            return cls.DOCUMENT
        elif mime_type.startswith("application/"):
            if any(x in mime_type for x in ["pdf", "msword", "vnd.ms-", "vnd.openxmlformats", "rtf"]):
                return cls.DOCUMENT
            elif any(x in mime_type for x in ["zip", "tar", "gzip", "x-7z", "x-rar", "x-bzip"]):
                return cls.ARCHIVE
            elif any(x in mime_type for x in ["x-executable", "octet-stream", "x-binary"]):
                # Potential binaries or executables
                return cls.GENERIC
            elif any(x in mime_type for x in ["java", "python", "javascript", "json", "xml"]):
                return cls.CODE
            elif "octet-stream" in mime_type:
                return cls.GENERIC
            elif any(x in mime_type for x in ["docker", "container"]):
                return cls.CONTAINER
        
        # Default fallback
        return cls.GENERIC
    
    @classmethod
    def from_file_extension(cls, filename: str) -> 'ContentCategory':
        """
        Determine content category from file extension.
        
        Args:
            filename: Filename with extension
            
        Returns:
            Corresponding ContentCategory
        """
        if not filename:
            return cls.GENERIC
        
        # Extract extension
        _, ext = os.path.splitext(filename)
        if not ext:
            return cls.GENERIC
            
        ext = ext.lower().lstrip(".")
        
        # Images
        if ext in ["jpg", "jpeg", "png", "gif", "bmp", "tiff", "webp", "svg"]:
            return cls.IMAGE
        
        # Videos
        elif ext in ["mp4", "avi", "mov", "mkv", "webm", "flv", "wmv", "m4v"]:
            return cls.VIDEO
        
        # Audio
        elif ext in ["mp3", "wav", "ogg", "flac", "aac", "m4a", "wma"]:
            return cls.AUDIO
        
        # Documents
        elif ext in ["pdf", "doc", "docx", "txt", "rtf", "odt", "xls", "xlsx", "ppt", "pptx", "csv", "md", "html"]:
            return cls.DOCUMENT
        
        # Code
        elif ext in ["py", "js", "java", "c", "cpp", "cs", "go", "rs", "php", "rb", "ts", "html", "css", "xml", "json"]:
            return cls.CODE
        
        # Datasets
        elif ext in ["csv", "json", "xml", "parquet", "avro", "hdf5", "npy", "npz"]:
            return cls.DATASET
        
        # Models
        elif ext in ["pb", "pt", "pth", "h5", "onnx", "tflite", "pkl"]:
            return cls.MODEL
        
        # Containers
        elif ext in ["tar", "sif"]:
            return cls.CONTAINER
        
        # Archives
        elif ext in ["zip", "tar", "gz", "tgz", "bz2", "7z", "rar"]:
            return cls.ARCHIVE
        
        # Default fallback
        return cls.GENERIC

class BackendStats:
    """Statistics and metrics for a storage backend."""
    
    def __init__(self, backend_name: str):
        """
        Initialize backend statistics.
        
        Args:
            backend_name: Storage backend name
        """
        self.backend_name = backend_name
        self.reset()
    
    def reset(self):
        """Reset all statistics."""
        # Performance metrics
        self.total_operations = 0
        self.successful_operations = 0
        self.failed_operations = 0
        
        # Latency tracking
        self.latencies = []
        self.avg_latency = 0.0
        
        # Content metrics
        self.content_type_counts = defaultdict(int)
        self.total_bytes_stored = 0
        self.operation_counts = defaultdict(int)
        
        # Availability tracking
        self.last_availability_check = 0
        self.availability_status = True
        self.availability_history = []  # List of (timestamp, status) tuples
        
        # Cost metrics
        self.estimated_cost = 0.0
        self.last_updated = time.time()
    
    def update_latency(self, operation_latency: float):
        """
        Update latency metrics with a new measurement.
        
        Args:
            operation_latency: Latency in seconds for an operation
        """
        self.latencies.append(operation_latency)
        
        # Keep only last 100 latency measurements
        if len(self.latencies) > 100:
            self.latencies.pop(0)
        
        # Update average
        self.avg_latency = sum(self.latencies) / len(self.latencies) if self.latencies else 0
    
    def update_availability(self, status: bool):
        """
        Update availability status.
        
        Args:
            status: True if backend is available, False otherwise
        """
        now = time.time()
        self.last_availability_check = now
        self.availability_status = status
        self.availability_history.append((now, status))
        
        # Keep only last 24 hours of availability history
        cutoff = now - (24 * 60 * 60)
        self.availability_history = [
            (ts, status) for ts, status in self.availability_history
            if ts >= cutoff
        ]
    
    def record_operation(self, operation: str, success: bool, size_bytes: Optional[int] = None, 
                        content_type: Optional[str] = None, latency: Optional[float] = None):
        """
        Record an operation for this backend.
        
        Args:
            operation: Operation type (store, retrieve, etc.)
            success: Whether operation succeeded
            size_bytes: Size of data involved in operation
            content_type: Content type of the data
            latency: Operation latency in seconds
        """
        self.total_operations += 1
        if success:
            self.successful_operations += 1
        else:
            self.failed_operations += 1
        
        # Update operation counts
        key = f"{operation}_{success}"
        self.operation_counts[key] += 1
        
        # Update content metrics
        if content_type:
            self.content_type_counts[content_type] += 1
        
        # Update bytes stored
        if size_bytes and size_bytes > 0:
            self.total_bytes_stored += size_bytes
        
        # Update latency
        if latency is not None:
            self.update_latency(latency)
        
        self.last_updated = time.time()
    
    def get_availability_percentage(self, window_seconds: int = 86400) -> float:
        """
        Calculate availability percentage over a time window.
        
        Args:
            window_seconds: Time window in seconds (default: 24 hours)
            
        Returns:
            Availability percentage (0-100)
        """
        if not self.availability_history:
            return 100.0 if self.availability_status else 0.0
        
        # Filter history within the window
        now = time.time()
        cutoff = now - window_seconds
        relevant_history = [
            status for ts, status in self.availability_history
            if ts >= cutoff
        ]
        
        if not relevant_history:
            return 100.0 if self.availability_status else 0.0
        
        # Calculate percentage
        return (sum(1 for status in relevant_history if status) / len(relevant_history)) * 100.0
    
    def get_success_rate(self) -> float:
        """
        Calculate success rate for operations.
        
        Returns:
            Success rate percentage (0-100)
        """
        if self.total_operations == 0:
            return 100.0
        
        return (self.successful_operations / self.total_operations) * 100.0
    
    def get_health_score(self) -> float:
        """
        Calculate overall health score for this backend.
        
        Returns:
            Health score (0-1) where 1 is perfectly healthy
        """
        # Combine availability, success rate, and latency into a single score
        availability = self.get_availability_percentage() / 100.0
        success_rate = self.get_success_rate() / 100.0
        
        # Normalize latency (lower is better)
        # We'll consider >5s as the worst case
        latency_factor = max(0, min(1, 1 - (self.avg_latency / 5.0)))
        
        # Weight the factors
        return (0.4 * availability) + (0.4 * success_rate) + (0.2 * latency_factor)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert statistics to dictionary representation.
        
        Returns:
            Dictionary with all statistics
        """
        return {
            "backend_name": self.backend_name,
            "total_operations": self.total_operations,
            "successful_operations": self.successful_operations,
            "failed_operations": self.failed_operations,
            "avg_latency": self.avg_latency,
            "success_rate": self.get_success_rate(),
            "availability": self.get_availability_percentage(),
            "availability_status": self.availability_status,
            "health_score": self.get_health_score(),
            "total_bytes_stored": self.total_bytes_stored,
            "content_type_counts": dict(self.content_type_counts),
            "operation_counts": dict(self.operation_counts),
            "estimated_cost": self.estimated_cost,
            "last_updated": self.last_updated
        }

class RouteMapping:
    """Mapping between content and storage backends."""
    
    def __init__(self, content_category: Union[ContentCategory, str], 
                backend_mappings: Dict[str, float]):
        """
        Initialize a route mapping.
        
        Args:
            content_category: Content category or custom key
            backend_mappings: Mapping of backend names to weights
        """
        self.content_category = content_category.value if isinstance(content_category, ContentCategory) else content_category
        self.backend_mappings = backend_mappings
        self.last_updated = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary representation.
        
        Returns:
            Dictionary representation of the mapping
        """
        return {
            "content_category": self.content_category,
            "backend_mappings": self.backend_mappings,
            "last_updated": self.last_updated
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RouteMapping':
        """
        Create a RouteMapping from dictionary data.
        
        Args:
            data: Dictionary data
            
        Returns:
            RouteMapping instance
        """
        return cls(
            content_category=data["content_category"],
            backend_mappings=data["backend_mappings"]
        )

class OptimizedDataRouter:
    """
    Optimized data routing system for intelligent storage backend selection.
    
    Features:
    - Content-aware backend selection
    - Cost-based routing algorithms
    - Geographic optimization
    - Bandwidth and latency analysis
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the data router.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        
        # Default configuration
        self.default_strategy = RoutingStrategy(self.config.get("default_strategy", RoutingStrategy.HYBRID.value))
        self.update_interval = self.config.get("update_interval", 300)  # 5 minutes
        
        # Initialize storage
        self.backends = set()
        self.backend_stats = {}
        self.route_mappings = {}
        self.custom_routes = {}
        
        # Backend cost information
        self.backend_costs = self.config.get("backend_costs", {})
        
        # Metrics and monitoring
        self.routing_decisions = []
        self.last_backend_index = 0  # For round-robin
        
        # Cache for optimized lookups
        self._category_backend_cache = {}
        
        # Initialize empty state
        self._last_update = 0
        self._update_thread = None
        self._stop_updates = threading.Event()
        
        # Geographic mapping
        self.geo_regions = self.config.get("geo_regions", {})
        self.current_region = self.config.get("current_region", "default")
        
        # Default backend options
        for backend in self.config.get("backends", []):
            self.register_backend(backend)
        
        # Initialize default mappings
        self._init_default_mappings()
        
        logger.info("Optimized Data Router initialized with strategy: " + self.default_strategy.value)
        
        # Start background updates if configured
        if self.config.get("auto_start_updates", True):
            self.start_updates()
    
    def _init_default_mappings(self):
        """Initialize default content category to backend mappings."""
        default_backends = list(self.backends)
        if not default_backends:
            return
        
        # Create equal weight distribution
        weight = 1.0 / len(default_backends)
        default_mapping = {backend: weight for backend in default_backends}
        
        # Create a mapping for each content category
        for category in ContentCategory:
            if category.value not in self.route_mappings:
                self.route_mappings[category.value] = RouteMapping(
                    content_category=category,
                    backend_mappings=default_mapping.copy()
                )
    
    def register_backend(self, backend_name: str):
        """
        Register a storage backend with the router.
        
        Args:
            backend_name: Name of the storage backend
        """
        if backend_name in self.backends:
            logger.warning(f"Backend {backend_name} already registered with router")
            return
        
        self.backends.add(backend_name)
        self.backend_stats[backend_name] = BackendStats(backend_name)
        logger.info(f"Registered backend {backend_name} with router")
        
        # Update mappings to include the new backend
        self._update_mappings_for_new_backend(backend_name)
    
    def _update_mappings_for_new_backend(self, backend_name: str):
        """
        Update existing mappings to include a new backend.
        
        Args:
            backend_name: Name of the new backend
        """
        for category, mapping in self.route_mappings.items():
            # Add with a small initial weight
            mapping.backend_mappings[backend_name] = 0.1
            
            # Normalize weights to sum to 1
            total = sum(mapping.backend_mappings.values())
            for backend in mapping.backend_mappings:
                mapping.backend_mappings[backend] /= total
            
            mapping.last_updated = time.time()
    
    def unregister_backend(self, backend_name: str):
        """
        Unregister a storage backend from the router.
        
        Args:
            backend_name: Name of the storage backend
        """
        if backend_name not in self.backends:
            logger.warning(f"Backend {backend_name} not registered with router")
            return
        
        self.backends.remove(backend_name)
        if backend_name in self.backend_stats:
            del self.backend_stats[backend_name]
        
        # Remove from mappings and redistribute weights
        for category, mapping in self.route_mappings.items():
            if backend_name in mapping.backend_mappings:
                # Remove the backend and redistribute its weight
                weight = mapping.backend_mappings.pop(backend_name)
                
                # If no backends left, skip
                if not mapping.backend_mappings:
                    continue
                
                # Distribute the weight proportionally
                total = sum(mapping.backend_mappings.values())
                if total > 0:
                    for backend in mapping.backend_mappings:
                        mapping.backend_mappings[backend] += (weight * mapping.backend_mappings[backend] / total)
                
                mapping.last_updated = time.time()
        
        # Clear caches
        self._category_backend_cache.clear()
        
        logger.info(f"Unregistered backend {backend_name} from router")
    
    def update_backend_stats(self, backend_name: str, operation: str, success: bool, 
                           size_bytes: Optional[int] = None, content_type: Optional[str] = None, 
                           latency: Optional[float] = None):
        """
        Update statistics for a backend based on an operation.
        
        Args:
            backend_name: Name of the storage backend
            operation: Operation type (store, retrieve, etc.)
            success: Whether operation succeeded
            size_bytes: Size of data involved in operation
            content_type: Content type of the data
            latency: Operation latency in seconds
        """
        if backend_name not in self.backend_stats:
            self.register_backend(backend_name)
        
        self.backend_stats[backend_name].record_operation(
            operation=operation,
            success=success,
            size_bytes=size_bytes,
            content_type=content_type,
            latency=latency
        )
    
    def update_backend_availability(self, backend_name: str, available: bool):
        """
        Update availability status for a backend.
        
        Args:
            backend_name: Name of the storage backend
            available: Whether the backend is available
        """
        if backend_name not in self.backend_stats:
            self.register_backend(backend_name)
        
        self.backend_stats[backend_name].update_availability(available)
        
        # If availability changed, clear caches
        self._category_backend_cache.clear()
    
    def set_route_mapping(self, content_category: Union[ContentCategory, str], 
                        backend_mappings: Dict[str, float]):
        """
        Set a custom route mapping for a content category.
        
        Args:
            content_category: Content category or custom string key
            backend_mappings: Mapping of backend names to weights (should sum to 1)
        """
        category = content_category.value if isinstance(content_category, ContentCategory) else content_category
        
        # Validate backends
        unknown_backends = set(backend_mappings.keys()) - self.backends
        if unknown_backends:
            raise ValueError(f"Unknown backends in mapping: {unknown_backends}")
        
        # Normalize weights to sum to 1
        total = sum(backend_mappings.values())
        if abs(total - 1.0) > 0.001:  # Allow small floating-point difference
            normalized = {k: v / total for k, v in backend_mappings.items()}
        else:
            normalized = backend_mappings
        
        self.route_mappings[category] = RouteMapping(
            content_category=category,
            backend_mappings=normalized
        )
        
        # Clear cache for this category
        if category in self._category_backend_cache:
            del self._category_backend_cache[category]
        
        logger.info(f"Set custom route mapping for category {category}")
    
    def get_backend_for_content(self, content_info: Dict[str, Any], 
                               strategy: Optional[RoutingStrategy] = None) -> str:
        """
        Select the best backend for storing/retrieving content.
        
        Args:
            content_info: Dictionary with content information
                Required keys include one or more of:
                - content_type: MIME type
                - filename: Filename with extension
                - size_bytes: Content size in bytes
                - content_category: Explicit content category
                - region: Geographic region
            strategy: Routing strategy to use (defaults to configured default)
            
        Returns:
            Name of the selected backend
        """
        if not self.backends:
            raise ValueError("No backends registered with router")
        
        # Default to configured strategy if not specified
        strategy = strategy or self.default_strategy
        
        # Record decision data
        decision_data = {
            "timestamp": time.time(),
            "content_info": content_info.copy(),
            "strategy": strategy.value,
        }
        
        # Random strategy (for testing)
        if strategy == RoutingStrategy.RANDOM:
            import random
            selected = random.choice(list(self.backends))
            decision_data["selected_backend"] = selected
            decision_data["reason"] = "Random selection"
            self.routing_decisions.append(decision_data)
            return selected
        
        # Round-robin strategy
        if strategy == RoutingStrategy.ROUND_ROBIN:
            backends = list(self.backends)
            if not backends:
                raise ValueError("No backends available")
            
            # Increment and wrap
            self.last_backend_index = (self.last_backend_index + 1) % len(backends)
            selected = backends[self.last_backend_index]
            
            decision_data["selected_backend"] = selected
            decision_data["reason"] = "Round-robin selection"
            self.routing_decisions.append(decision_data)
            return selected
        
        # Determine content category
        content_category = self._determine_content_category(content_info)
        
        # Custom strategy
        if strategy == RoutingStrategy.CUSTOM and "routing_key" in content_info:
            routing_key = content_info["routing_key"]
            if routing_key in self.custom_routes:
                selected = self.custom_routes[routing_key]
                decision_data["selected_backend"] = selected
                decision_data["reason"] = f"Custom route for key {routing_key}"
                self.routing_decisions.append(decision_data)
                return selected
        
        # Get available backends (filter out unavailable ones)
        available_backends = [
            backend for backend in self.backends
            if backend in self.backend_stats and self.backend_stats[backend].availability_status
        ]
        
        if not available_backends:
            # If no backends are available, fall back to any backend
            logger.warning("No available backends found, using any registered backend")
            available_backends = list(self.backends)
        
        # Content type strategy
        if strategy == RoutingStrategy.CONTENT_TYPE:
            selected = self._select_backend_by_content_type(content_category, available_backends)
            decision_data["selected_backend"] = selected
            decision_data["reason"] = f"Content type selection for {content_category}"
            decision_data["content_category"] = content_category
            self.routing_decisions.append(decision_data)
            return selected
        
        # Cost strategy
        if strategy == RoutingStrategy.COST:
            size_bytes = content_info.get("size_bytes", 0)
            selected = self._select_backend_by_cost(content_category, size_bytes, available_backends)
            decision_data["selected_backend"] = selected
            decision_data["reason"] = f"Cost optimization for {content_category}"
            decision_data["content_category"] = content_category
            decision_data["size_bytes"] = size_bytes
            self.routing_decisions.append(decision_data)
            return selected
        
        # Performance strategy
        if strategy == RoutingStrategy.PERFORMANCE:
            selected = self._select_backend_by_performance(content_category, available_backends)
            decision_data["selected_backend"] = selected
            decision_data["reason"] = f"Performance optimization for {content_category}"
            decision_data["content_category"] = content_category
            self.routing_decisions.append(decision_data)
            return selected
        
        # Availability strategy
        if strategy == RoutingStrategy.AVAILABILITY:
            selected = self._select_backend_by_availability(content_category, available_backends)
            decision_data["selected_backend"] = selected
            decision_data["reason"] = f"Availability optimization for {content_category}"
            decision_data["content_category"] = content_category
            self.routing_decisions.append(decision_data)
            return selected
        
        # Geographic strategy
        if strategy == RoutingStrategy.GEOGRAPHIC:
            region = content_info.get("region", self.current_region)
            selected = self._select_backend_by_geography(region, content_category, available_backends)
            decision_data["selected_backend"] = selected
            decision_data["reason"] = f"Geographic optimization for region {region}"
            decision_data["region"] = region
            decision_data["content_category"] = content_category
            self.routing_decisions.append(decision_data)
            return selected
        
        # Hybrid strategy (default) - combines multiple factors
        if strategy == RoutingStrategy.HYBRID:
            size_bytes = content_info.get("size_bytes", 0)
            region = content_info.get("region", self.current_region)
            selected = self._select_backend_hybrid(
                content_category=content_category,
                size_bytes=size_bytes,
                region=region,
                available_backends=available_backends
            )
            decision_data["selected_backend"] = selected
            decision_data["reason"] = "Hybrid optimization"
            decision_data["content_category"] = content_category
            decision_data["size_bytes"] = size_bytes
            decision_data["region"] = region
            self.routing_decisions.append(decision_data)
            return selected
        
        # If we get here, no strategy matched; use first available backend
        selected = available_backends[0]
        decision_data["selected_backend"] = selected
        decision_data["reason"] = "Fallback selection (no matching strategy)"
        self.routing_decisions.append(decision_data)
        return selected
    
    def _determine_content_category(self, content_info: Dict[str, Any]) -> str:
        """
        Determine content category from content info.
        
        Args:
            content_info: Dictionary with content information
            
        Returns:
            Content category string
        """
        # Explicit category takes precedence
        if "content_category" in content_info:
            if isinstance(content_info["content_category"], ContentCategory):
                return content_info["content_category"].value
            return content_info["content_category"]
        
        # Determine from MIME type if available
        if "content_type" in content_info:
            category = ContentCategory.from_mime_type(content_info["content_type"])
            return category.value
        
        # Try to determine from filename
        if "filename" in content_info:
            category = ContentCategory.from_file_extension(content_info["filename"])
            return category.value
        
        # Default to generic
        return ContentCategory.GENERIC.value
    
    def _select_backend_by_content_type(self, content_category: str, available_backends: List[str]) -> str:
        """
        Select backend based on content type mapping.
        
        Args:
            content_category: Content category string
            available_backends: List of available backends
            
        Returns:
            Selected backend name
        """
        # Check cache first
        cache_key = f"content_{content_category}_{','.join(sorted(available_backends))}"
        if cache_key in self._category_backend_cache:
            return self._category_backend_cache[cache_key]
        
        # Get mapping for this category
        mapping = self.route_mappings.get(content_category)
        if not mapping:
            # If no specific mapping, use GENERIC
            mapping = self.route_mappings.get(ContentCategory.GENERIC.value)
            
            # If still no mapping, create default
            if not mapping:
                weight = 1.0 / len(available_backends)
                backend_mappings = {backend: weight for backend in available_backends}
                mapping = RouteMapping(ContentCategory.GENERIC, backend_mappings)
        
        # Filter to only available backends
        filtered_mappings = {
            backend: weight for backend, weight in mapping.backend_mappings.items()
            if backend in available_backends
        }
        
        if not filtered_mappings:
            # If no mappings are available, use any available backend
            selected = available_backends[0]
        else:
            # Use weighted random selection
            selected = self._weighted_random_selection(filtered_mappings)
        
        # Cache the result
        self._category_backend_cache[cache_key] = selected
        
        return selected
    
    def _select_backend_by_cost(self, content_category: str, size_bytes: int, available_backends: List[str]) -> str:
        """
        Select backend based on cost optimization.
        
        Args:
            content_category: Content category string
            size_bytes: Size of content in bytes
            available_backends: List of available backends
            
        Returns:
            Selected backend name
        """
        if not available_backends:
            raise ValueError("No available backends")
        
        # Calculate cost for storing this content on each backend
        costs = {}
        for backend in available_backends:
            # Get cost model for this backend
            cost_model = self.backend_costs.get(backend, {})
            
            # Calculate storage cost
            storage_cost = cost_model.get("storage_cost_per_gb", 0.0) * (size_bytes / (1024 * 1024 * 1024))
            
            # Add fixed costs
            fixed_cost = cost_model.get("fixed_cost_per_operation", 0.0)
            
            # Consider bandwidth costs if applicable
            bandwidth_cost = cost_model.get("bandwidth_cost_per_gb", 0.0) * (size_bytes / (1024 * 1024 * 1024))
            
            # Total cost
            costs[backend] = storage_cost + fixed_cost + bandwidth_cost
        
        # Select the cheapest backend
        if not costs:
            return available_backends[0]
            
        selected = min(costs, key=costs.get)
        return selected
    
    def _select_backend_by_performance(self, content_category: str, available_backends: List[str]) -> str:
        """
        Select backend based on performance metrics.
        
        Args:
            content_category: Content category string
            available_backends: List of available backends
            
        Returns:
            Selected backend name
        """
        if not available_backends:
            raise ValueError("No available backends")
        
        # Calculate performance score for each backend
        scores = {}
        for backend in available_backends:
            stats = self.backend_stats.get(backend)
            if not stats:
                scores[backend] = 0.5  # Default score for unknown backends
                continue
            
            # Consider average latency (lower is better)
            latency_score = max(0, min(1, 1 - (stats.avg_latency / 5.0)))
            
            # Consider success rate
            success_score = stats.get_success_rate() / 100.0
            
            # Combine into overall performance score
            scores[backend] = (0.7 * latency_score) + (0.3 * success_score)
        
        # Select the backend with the highest score
        if not scores:
            return available_backends[0]
            
        selected = max(scores, key=scores.get)
        return selected
    
    def _select_backend_by_availability(self, content_category: str, available_backends: List[str]) -> str:
        """
        Select backend based on availability metrics.
        
        Args:
            content_category: Content category string
            available_backends: List of available backends
            
        Returns:
            Selected backend name
        """
        if not available_backends:
            raise ValueError("No available backends")
        
        # Calculate availability score for each backend
        scores = {}
        for backend in available_backends:
            stats = self.backend_stats.get(backend)
            if not stats:
                scores[backend] = 0.5  # Default score for unknown backends
                continue
            
            # Get availability percentage
            availability = stats.get_availability_percentage() / 100.0
            
            # Consider success rate
            success_rate = stats.get_success_rate() / 100.0
            
            # Combine into overall availability score
            scores[backend] = (0.6 * availability) + (0.4 * success_rate)
        
        # Select the backend with the highest score
        if not scores:
            return available_backends[0]
            
        selected = max(scores, key=scores.get)
        return selected
    
    def _select_backend_by_geography(self, region: str, content_category: str, available_backends: List[str]) -> str:
        """
        Select backend based on geographic proximity.
        
        Args:
            region: Geographic region code
            content_category: Content category string
            available_backends: List of available backends
            
        Returns:
            Selected backend name
        """
        if not available_backends:
            raise ValueError("No available backends")
        
        # Check if we have region-to-backend mappings
        region_backends = self.geo_regions.get(region, {}).get("backends", [])
        region_backends = [b for b in region_backends if b in available_backends]
        
        # If we have backends for this region, select from them
        if region_backends:
            # Use content type strategy within the region-specific backends
            return self._select_backend_by_content_type(content_category, region_backends)
        
        # Otherwise, fall back to content type strategy with all available backends
        return self._select_backend_by_content_type(content_category, available_backends)
    
    def _select_backend_hybrid(self, content_category: str, size_bytes: int, 
                             region: str, available_backends: List[str]) -> str:
        """
        Select backend using a hybrid approach considering multiple factors.
        
        Args:
            content_category: Content category string
            size_bytes: Size of content in bytes
            region: Geographic region
            available_backends: List of available backends
            
        Returns:
            Selected backend name
        """
        if not available_backends:
            raise ValueError("No available backends")
        
        # Calculate a composite score for each backend
        scores = {}
        for backend in available_backends:
            # Get backend stats
            stats = self.backend_stats.get(backend)
            if not stats:
                scores[backend] = 0.5  # Default score for unknown backends
                continue
            
            # Content type fit (from route mappings)
            mapping = self.route_mappings.get(content_category)
            if not mapping:
                mapping = self.route_mappings.get(ContentCategory.GENERIC.value)
            
            content_score = mapping.backend_mappings.get(backend, 0.0) if mapping else 0.1
            
            # Cost factor
            cost_model = self.backend_costs.get(backend, {})
            storage_cost = cost_model.get("storage_cost_per_gb", 0.0) * (size_bytes / (1024 * 1024 * 1024))
            fixed_cost = cost_model.get("fixed_cost_per_operation", 0.0)
            bandwidth_cost = cost_model.get("bandwidth_cost_per_gb", 0.0) * (size_bytes / (1024 * 1024 * 1024))
            total_cost = storage_cost + fixed_cost + bandwidth_cost
            
            # Normalize cost (higher cost = lower score)
            # We'll use a sigmoid function to normalize costs
            cost_score = 1.0 / (1.0 + math.exp(total_cost - 0.01))
            
            # Performance factor
            latency_score = max(0, min(1, 1 - (stats.avg_latency / 5.0)))
            success_score = stats.get_success_rate() / 100.0
            performance_score = (0.7 * latency_score) + (0.3 * success_score)
            
            # Availability factor
            availability = stats.get_availability_percentage() / 100.0
            
            # Geographic factor
            region_backends = self.geo_regions.get(region, {}).get("backends", [])
            geo_score = 1.0 if backend in region_backends else 0.3
            
            # Combine all factors with weights
            scores[backend] = (
                (0.25 * content_score) +
                (0.2 * cost_score) +
                (0.25 * performance_score) +
                (0.15 * availability) +
                (0.15 * geo_score)
            )
        
        # Select the backend with the highest score
        if not scores:
            return available_backends[0]
            
        selected = max(scores, key=scores.get)
        return selected
    
    def _weighted_random_selection(self, weights: Dict[str, float]) -> str:
        """
        Perform weighted random selection from a dictionary of weights.
        
        Args:
            weights: Dictionary mapping items to their weights
            
        Returns:
            Selected item
        """
        if not weights:
            raise ValueError("Empty weights dictionary")
            
        import random
        
        # Calculate cumulative weights
        items = list(weights.keys())
        weights_list = [weights[item] for item in items]
        
        # Check if all weights are zero
        if all(w == 0 for w in weights_list):
            # If all weights are zero, use uniform distribution
            return random.choice(items)
        
        # Calculate cumulative weights
        cumulative = []
        total = 0
        for w in weights_list:
            total += w
            cumulative.append(total)
        
        # Select based on weights
        r = random.random() * total
        for i, c in enumerate(cumulative):
            if r <= c:
                return items[i]
        
        # Fallback (should never reach here)
        return items[-1]
    
    def set_custom_route(self, routing_key: str, backend_name: str):
        """
        Set a custom routing rule by key.
        
        Args:
            routing_key: Routing key for content
            backend_name: Backend to route to
        """
        if backend_name not in self.backends:
            raise ValueError(f"Unknown backend: {backend_name}")
        
        self.custom_routes[routing_key] = backend_name
        logger.info(f"Set custom route for key {routing_key} to backend {backend_name}")
    
    def suggest_backend_weights(self, evaluation_data: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, Dict[str, float]]]:
        """
        Suggest optimal backend weights based on performance and usage data.
        
        Args:
            evaluation_data: Optional external data to consider
            
        Returns:
            Dictionary with suggested weights for each content category
        """
        suggestions = {}
        
        # Calculate current performance metrics
        backend_performance = {}
        for backend in self.backends:
            stats = self.backend_stats.get(backend, BackendStats(backend))
            
            # Skip unavailable backends
            if not stats.availability_status:
                continue
                
            # Calculate a performance score
            health_score = stats.get_health_score()
            
            # Adjust based on content type specialization
            content_specialization = {}
            total_ops = sum(stats.content_type_counts.values())
            
            if total_ops > 0:
                for content_type, count in stats.content_type_counts.items():
                    # Convert MIME type to content category
                    category = ContentCategory.from_mime_type(content_type).value
                    
                    # Calculate specialization score based on proportion of this content type
                    if category not in content_specialization:
                        content_specialization[category] = 0
                    
                    content_specialization[category] += count / total_ops
            
            backend_performance[backend] = {
                "health_score": health_score,
                "content_specialization": content_specialization,
                "avg_latency": stats.avg_latency,
                "success_rate": stats.get_success_rate()
            }
        
        # Calculate suggested weights for each content category
        for category in ContentCategory:
            category_key = category.value
            
            # Skip if no backends available
            if not backend_performance:
                continue
                
            # Base weights on health score
            base_weights = {
                backend: data["health_score"]
                for backend, data in backend_performance.items()
            }
            
            # Adjust for content specialization
            for backend, data in backend_performance.items():
                specialization = data["content_specialization"].get(category_key, 0)
                # Boost weight based on specialization (0-50% boost)
                base_weights[backend] *= (1 + (specialization * 0.5))
            
            # Normalize weights to sum to 1
            total = sum(base_weights.values())
            if total > 0:
                normalized = {k: v / total for k, v in base_weights.items()}
            else:
                # If all weights are 0, use equal distribution
                equal_weight = 1.0 / len(backend_performance)
                normalized = {backend: equal_weight for backend in backend_performance}
            
            # Store suggestion
            if category_key not in suggestions:
                suggestions[category_key] = {}
            
            suggestions[category_key] = {
                "current": self.route_mappings.get(category_key, RouteMapping(category, {})).backend_mappings,
                "suggested": normalized,
                "metrics": {backend: backend_performance[backend] for backend in normalized}
            }
        
        return suggestions
    
    def analyze_content(self, content: Union[bytes, str], filename: Optional[str] = None,
                      content_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze content to determine its category and characteristics.
        
        Args:
            content: Content data as bytes or string
            filename: Optional filename with extension
            content_type: Optional content MIME type
            
        Returns:
            Dictionary with content analysis results
        """
        result = {
            "size_bytes": len(content) if isinstance(content, bytes) else len(content.encode('utf-8'))
        }
        
        # Determine content type if not provided
        if not content_type and filename:
            guessed_type = mimetypes.guess_type(filename)[0]
            if guessed_type:
                content_type = guessed_type
        
        if content_type:
            result["content_type"] = content_type
        
        if filename:
            result["filename"] = filename
        
        # Determine content category
        result["content_category"] = self._determine_content_category(result)
        
        # Generate content hash for identification
        content_bytes = content if isinstance(content, bytes) else content.encode('utf-8')
        content_hash = hashlib.sha256(content_bytes).hexdigest()
        result["content_hash"] = content_hash
        
        # Analyze first few bytes for magic numbers
        if isinstance(content, bytes) and len(content) > 16:
            # Convert first 16 bytes to hex for analysis
            magic_bytes = content[:16].hex()
            result["magic_bytes"] = magic_bytes
        
        return result
    
    def get_backend_stats(self, backend_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics for a specific backend or all backends.
        
        Args:
            backend_name: Optional backend name, if None returns all backends
            
        Returns:
            Dictionary with backend statistics
        """
        if backend_name:
            if backend_name not in self.backend_stats:
                return {"error": f"Backend {backend_name} not found"}
            
            return self.backend_stats[backend_name].to_dict()
        
        # Return stats for all backends
        return {
            backend: stats.to_dict()
            for backend, stats in self.backend_stats.items()
        }
    
    def get_route_mappings(self, content_category: Optional[Union[ContentCategory, str]] = None) -> Dict[str, Any]:
        """
        Get route mappings for a specific content category or all categories.
        
        Args:
            content_category: Optional content category, if None returns all mappings
            
        Returns:
            Dictionary with route mappings
        """
        if content_category:
            category = content_category.value if isinstance(content_category, ContentCategory) else content_category
            
            if category not in self.route_mappings:
                return {"error": f"No mapping found for category {category}"}
            
            return self.route_mappings[category].to_dict()
        
        # Return all mappings
        return {
            category: mapping.to_dict()
            for category, mapping in self.route_mappings.items()
        }
    
    def _update_routing_weights(self):
        """Update routing weights based on performance metrics."""
        # Get suggestions based on current performance data
        suggestions = self.suggest_backend_weights()
        
        # Update weights based on suggestions
        for category, suggestion_data in suggestions.items():
            suggested = suggestion_data.get("suggested", {})
            
            # Only update if we have a reasonable suggestion
            if suggested:
                # Apply gradual adjustment (30% toward suggested weights)
                current = self.route_mappings.get(category)
                if current:
                    new_weights = {}
                    for backend, suggested_weight in suggested.items():
                        current_weight = current.backend_mappings.get(backend, 0.0)
                        # Move 30% toward suggested weight
                        new_weights[backend] = current_weight + (0.3 * (suggested_weight - current_weight))
                    
                    # Add any missing backends with a small weight
                    for backend in self.backends:
                        if backend not in new_weights:
                            new_weights[backend] = 0.05
                    
                    # Normalize weights to sum to 1
                    total = sum(new_weights.values())
                    if total > 0:
                        normalized = {k: v / total for k, v in new_weights.items()}
                        
                        # Update mapping
                        self.route_mappings[category] = RouteMapping(
                            content_category=category,
                            backend_mappings=normalized
                        )
                        
                        # Clear cache for this category
                        cache_keys = [k for k in self._category_backend_cache if k.startswith(f"content_{category}_")]
                        for key in cache_keys:
                            if key in self._category_backend_cache:
                                del self._category_backend_cache[key]
    
    def start_updates(self):
        """Start background updates for routing weights."""
        if self._update_thread and self._update_thread.is_alive():
            logger.warning("Updates already running")
            return
        
        self._stop_updates.clear()
        self._update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self._update_thread.start()
        logger.info("Started routing weight updates")
    
    def stop_updates(self):
        """Stop background updates for routing weights."""
        self._stop_updates.set()
        if self._update_thread:
            self._update_thread.join(timeout=5)
            logger.info("Stopped routing weight updates")
    
    def _update_loop(self):
        """Background update loop for routing weights."""
        while not self._stop_updates.is_set():
            try:
                # Check if it's time to update
                now = time.time()
                if now - self._last_update >= self.update_interval:
                    self._update_routing_weights()
                    self._last_update = now
                    logger.debug("Updated routing weights")
            except Exception as e:
                logger.error(f"Error in routing update loop: {e}")
            
            # Sleep until next update
            self._stop_updates.wait(min(60, self.update_interval))
    
    def export_routing_config(self) -> Dict[str, Any]:
        """
        Export routing configuration as a serializable dictionary.
        
        Returns:
            Dictionary with complete routing configuration
        """
        # Export route mappings
        mappings = {
            category: mapping.to_dict()
            for category, mapping in self.route_mappings.items()
        }
        
        # Export custom routes
        custom_routes = dict(self.custom_routes)
        
        # Export backend costs
        costs = dict(self.backend_costs)
        
        # Export geo regions
        regions = dict(self.geo_regions)
        
        return {
            "route_mappings": mappings,
            "custom_routes": custom_routes,
            "backend_costs": costs,
            "geo_regions": regions,
            "default_strategy": self.default_strategy.value,
            "current_region": self.current_region,
            "update_interval": self.update_interval,
            "exported_at": time.time()
        }
    
    def import_routing_config(self, config: Dict[str, Any]) -> bool:
        """
        Import routing configuration from a dictionary.
        
        Args:
            config: Dictionary with routing configuration
            
        Returns:
            Boolean indicating success
        """
        try:
            # Import route mappings
            if "route_mappings" in config:
                for category, mapping_data in config["route_mappings"].items():
                    mapping = RouteMapping.from_dict(mapping_data)
                    self.route_mappings[category] = mapping
            
            # Import custom routes
            if "custom_routes" in config:
                for key, backend in config["custom_routes"].items():
                    self.custom_routes[key] = backend
            
            # Import backend costs
            if "backend_costs" in config:
                self.backend_costs = config["backend_costs"]
            
            # Import geo regions
            if "geo_regions" in config:
                self.geo_regions = config["geo_regions"]
            
            # Import strategy
            if "default_strategy" in config:
                try:
                    self.default_strategy = RoutingStrategy(config["default_strategy"])
                except ValueError:
                    logger.warning(f"Invalid routing strategy: {config['default_strategy']}")
            
            # Import current region
            if "current_region" in config:
                self.current_region = config["current_region"]
            
            # Import update interval
            if "update_interval" in config:
                self.update_interval = config["update_interval"]
            
            # Clear caches
            self._category_backend_cache.clear()
            
            logger.info("Successfully imported routing configuration")
            return True
            
        except Exception as e:
            logger.error(f"Error importing routing configuration: {e}")
            return False

# Singleton instance
_instance = None

def get_instance(config=None):
    """Get or create a singleton instance of the data router."""
    global _instance
    if _instance is None:
        _instance = OptimizedDataRouter(config)
    return _instance