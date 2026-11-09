"""
Optimized Data Routing Module for MCP Server

This module provides intelligent routing of data operations across different storage backends.
It implements content-aware backend selection, cost-based routing algorithms, geographic
optimization, and bandwidth/latency-based routing decisions.

Key features:
1. Content-aware backend selection based on file type, size, and access patterns
2. Cost-based routing algorithms to optimize for storage and retrieval costs
3. Geographic optimization to reduce latency and improve compliance
4. Bandwidth and latency analysis for adaptive routing decisions
5. Performance metrics collection and analysis

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements.
"""

import os
import json
import time
import logging
import threading
import hashlib
import random
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Union, Set, Tuple, Callable
from datetime import datetime, timedelta
from pathlib import Path

# Configure logger
logger = logging.getLogger(__name__)

# Try importing optional dependencies
try:
    import geopy.distance
    from geopy.geocoders import Nominatim
    HAS_GEOPY = True
except ImportError:
    HAS_GEOPY = False
    logger.warning("Geopy not available. Geographic optimization will be limited.")

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    logger.warning("Requests not available. Some connectivity checks will be limited.")


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
    LATENCY_OPTIMIZED = "latency_optimized"
    BANDWIDTH_OPTIMIZED = "bandwidth_optimized"
    LOCALITY_OPTIMIZED = "locality_optimized"
    COMPLIANCE_OPTIMIZED = "compliance_optimized"
    BALANCED = "balanced"
    CUSTOM = "custom"


class StorageClass(str, Enum):
    """Enum for storage classes with different cost and performance profiles."""
    HOT = "hot"                # Frequently accessed, fast retrieval, higher cost
    WARM = "warm"              # Occasionally accessed, moderate retrieval times and cost
    COLD = "cold"              # Rarely accessed, slower retrieval, lower cost
    ARCHIVE = "archive"        # Very rarely accessed, slowest retrieval, lowest cost
    COMPLIANCE = "compliance"  # Immutable storage with compliance features
    TEMPORARY = "temporary"    # Short-term storage with automatic expiration


class GeographicRegion(str, Enum):
    """Enum for geographic regions for content placement."""
    NORTH_AMERICA = "north_america"
    SOUTH_AMERICA = "south_america"
    EUROPE = "europe"
    ASIA_PACIFIC = "asia_pacific"
    AFRICA = "africa"
    MIDDLE_EAST = "middle_east"
    AUSTRALIA = "australia"
    GLOBAL = "global"  # Content replicated globally


class ComplianceType(str, Enum):
    """Enum for compliance types affecting routing decisions."""
    GDPR = "gdpr"              # European data protection
    HIPAA = "hipaa"            # US healthcare data
    PCI_DSS = "pci_dss"        # Payment card data
    SOX = "sox"                # Financial data
    CCPA = "ccpa"              # California privacy
    PERSONAL_DATA = "personal_data"  # Generic personal data
    PROPRIETARY = "proprietary"      # Business proprietary data
    PUBLIC = "public"                # Non-sensitive public data


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
    egress_cost_per_gb: float = 0.0
    
    # Availability metrics
    availability_percentage: float = 99.9
    uptime_last_24h: float = 100.0
    
    # Geographic information
    region: GeographicRegion = GeographicRegion.GLOBAL
    physical_location: Optional[str] = None  # City, country
    coordinates: Optional[Tuple[float, float]] = None  # Latitude, longitude
    
    # Compliance features
    supported_compliance: List[ComplianceType] = field(default_factory=list)
    
    # Current load and capacity
    current_load_percentage: float = 0.0
    available_capacity_gb: float = 0.0
    
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
    
    # Storage class preferences
    default_storage_class: StorageClass = StorageClass.HOT
    content_type_storage_class: Dict[ContentType, StorageClass] = field(default_factory=dict)
    
    # Geographic routing
    preferred_regions: List[GeographicRegion] = field(default_factory=list)
    geo_compliance_required: bool = False
    geo_routing_enabled: bool = True
    
    # Cost controls
    max_storage_cost_per_gb_month: Optional[float] = None
    max_egress_cost_per_gb: Optional[float] = None
    cost_optimization_enabled: bool = True
    
    # Performance thresholds
    min_throughput_mbps: Optional[float] = None
    max_latency_ms: Optional[float] = None
    performance_optimization_enabled: bool = True
    
    # Redundancy settings
    replication_factor: int = 1  # Number of copies across backends
    min_availability_percentage: float = 99.0
    
    # Backend preferences
    preferred_backends: List[str] = field(default_factory=list)
    excluded_backends: List[str] = field(default_factory=list)
    
    # Advanced settings
    custom_routing_function: Optional[str] = None
    metadata_based_routing_enabled: bool = False
    
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
    
    # Performance and cost projections
    estimated_latency_ms: Optional[float] = None
    estimated_cost: Optional[float] = None
    
    # Decision metadata
    policy_id: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class RouterGeolocation:
    """Helper class for geographic lookups and distance calculations."""
    
    def __init__(self):
        """Initialize the geolocation service."""
        self._geolocator = None
        self._cache: Dict[str, Tuple[float, float]] = {}
        
        # Try to initialize the geolocator if geopy is available
        if HAS_GEOPY:
            try:
                self._geolocator = Nominatim(user_agent="mcp-optimized-router")
                logger.info("Initialized geolocation service.")
            except Exception as e:
                logger.warning(f"Failed to initialize geolocation service: {e}")
        else:
            logger.warning("Geopy not available. Geographic optimization will be limited.")
    
    def get_coordinates(self, location: str) -> Optional[Tuple[float, float]]:
        """
        Get the coordinates (latitude, longitude) for a location.
        
        Args:
            location: Location string (e.g., "New York, USA")
            
        Returns:
            Tuple of (latitude, longitude) or None if not found
        """
        if not self._geolocator:
            return None
        
        # Check cache first
        if location in self._cache:
            return self._cache[location]
        
        try:
            geolocation = self._geolocator.geocode(location)
            if geolocation:
                coordinates = (geolocation.latitude, geolocation.longitude)
                self._cache[location] = coordinates
                return coordinates
            return None
        except Exception as e:
            logger.error(f"Error getting coordinates for {location}: {e}")
            return None
    
    def calculate_distance(self, coord1: Tuple[float, float], coord2: Tuple[float, float]) -> Optional[float]:
        """
        Calculate the distance between two coordinates in kilometers.
        
        Args:
            coord1: First coordinate (latitude, longitude)
            coord2: Second coordinate (latitude, longitude)
            
        Returns:
            Distance in kilometers or None if calculation fails
        """
        if not HAS_GEOPY:
            return None
        
        try:
            return geopy.distance.distance(coord1, coord2).kilometers
        except Exception as e:
            logger.error(f"Error calculating distance: {e}")
            return None
    
    def get_region_from_coordinates(self, coordinates: Tuple[float, float]) -> Optional[GeographicRegion]:
        """
        Simple approximation of geographic region from coordinates.
        
        Args:
            coordinates: Tuple of (latitude, longitude)
            
        Returns:
            GeographicRegion enum value or None if couldn't determine
        """
        lat, lon = coordinates
        
        # Very simple region determination - should be replaced with a proper geo library
        if 25 <= lat <= 65 and -130 <= lon <= -50:
            return GeographicRegion.NORTH_AMERICA
        elif -55 <= lat <= 15 and -80 <= lon <= -35:
            return GeographicRegion.SOUTH_AMERICA
        elif 35 <= lat <= 70 and -10 <= lon <= 40:
            return GeographicRegion.EUROPE
        elif -10 <= lat <= 55 and 60 <= lon <= 145:
            return GeographicRegion.ASIA_PACIFIC
        elif -35 <= lat <= 35 and -20 <= lon <= 55:
            return GeographicRegion.AFRICA
        elif 15 <= lat <= 40 and 35 <= lon <= 60:
            return GeographicRegion.MIDDLE_EAST
        elif -45 <= lat <= -10 and 110 <= lon <= 155:
            return GeographicRegion.AUSTRALIA
        
        return None


class ConnectivityAnalyzer:
    """Analyzes network connectivity to different backends to optimize routing."""
    
    def __init__(self):
        """Initialize the connectivity analyzer."""
        self._results: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._client_ip: Optional[str] = None
        self._client_location: Optional[Tuple[float, float]] = None
    
    def analyze_backend(self, backend_id: str, endpoint: str) -> Dict[str, Any]:
        """
        Analyze connectivity to a backend.
        
        Args:
            backend_id: Backend identifier
            endpoint: Backend endpoint URL
            
        Returns:
            Dictionary with connectivity metrics
        """
        if not HAS_REQUESTS:
            return {
                "backend_id": backend_id,
                "endpoint": endpoint,
                "status": "unknown",
                "latency_ms": 0.0,
                "timestamp": datetime.utcnow().isoformat()
            }
        
        with self._lock:
            try:
                # Perform a simple HEAD request to measure latency
                start_time = time.time()
                response = requests.head(endpoint, timeout=5)
                end_time = time.time()
                
                latency_ms = (end_time - start_time) * 1000
                
                result = {
                    "backend_id": backend_id,
                    "endpoint": endpoint,
                    "status": "available" if response.status_code < 400 else "error",
                    "status_code": response.status_code,
                    "latency_ms": latency_ms,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                # Cache the result
                self._results[backend_id] = result
                
                return result
            except Exception as e:
                logger.warning(f"Error analyzing backend {backend_id}: {e}")
                
                result = {
                    "backend_id": backend_id,
                    "endpoint": endpoint,
                    "status": "error",
                    "error": str(e),
                    "latency_ms": None,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                # Cache the result
                self._results[backend_id] = result
                
                return result
    
    def get_client_ip(self) -> Optional[str]:
        """
        Get the client's IP address.
        
        Returns:
            IP address as string or None if unavailable
        """
        if self._client_ip:
            return self._client_ip
        
        if not HAS_REQUESTS:
            return None
        
        try:
            response = requests.get('https://api.ipify.org', timeout=5)
            if response.status_code == 200:
                ip = response.text.strip()
                self._client_ip = ip
                return ip
        except Exception as e:
            logger.warning(f"Error getting client IP: {e}")
        
        return None
    
    def get_client_location(self) -> Optional[Tuple[float, float]]:
        """
        Get the client's geographic location.
        
        Returns:
            Tuple of (latitude, longitude) or None if unavailable
        """
        if self._client_location:
            return self._client_location
        
        if not HAS_REQUESTS:
            return None
        
        try:
            ip = self.get_client_ip()
            if not ip:
                return None
            
            response = requests.get(f'https://ipapi.co/{ip}/json/', timeout=5)
            if response.status_code == 200:
                data = response.json()
                if 'latitude' in data and 'longitude' in data:
                    location = (data['latitude'], data['longitude'])
                    self._client_location = location
                    return location
        except Exception as e:
            logger.warning(f"Error getting client location: {e}")
        
        return None


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
                egress_cost = metrics.egress_cost_per_gb
                
                # If any cost is zero, set a small default to avoid division by zero
                storage_cost = max(storage_cost, 0.001)
                read_cost = max(read_cost, 0.0001)
                write_cost = max(write_cost, 0.0001)
                egress_cost = max(egress_cost, 0.0001)
                
                # Higher score = higher cost = worse
                score = (storage_cost * 0.4 + 
                        read_cost * 0.2 + 
                        write_cost * 0.2 + 
                        egress_cost * 0.2)
                
                scores.append((backend_id, score))
            
            # Sort by score (ascending - lower cost is better)
            return sorted(scores, key=lambda x: x[1])


class OptimizedRouter:
    """
    Core router for optimizing data placement and retrieval across backends.
    Implements intelligent routing strategies based on content type, cost, 
    performance, geography, and other factors.
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
        self._geolocation = RouterGeolocation()
        self._connectivity = ConnectivityAnalyzer()
        self._content_analyzer = ContentAnalyzer()
        self._metrics_collector = RouterMetricsCollector()
        
        # Cache of backend endpoints
        self._backend_endpoints: Dict[str, str] = {}
        
        # Lock for thread safety
        self._lock = threading.RLock()
        
        logger.info("Initialized optimized router.")
    
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
    
    def analyze_backend_connectivity(self, backend_id: str) -> Dict[str, Any]:
        """
        Analyze connectivity to a backend.
        
        Args:
            backend_id: Backend identifier
            
        Returns:
            Dictionary with connectivity metrics
        """
        endpoint = self._backend_endpoints.get(backend_id)
        if not endpoint:
            return {
                "backend_id": backend_id,
                "status": "unknown",
                "error": "Backend not registered",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        return self._connectivity.analyze_backend(backend_id, endpoint)
    
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
            policy = self._default_
