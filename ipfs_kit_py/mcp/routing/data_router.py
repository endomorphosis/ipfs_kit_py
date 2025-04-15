"""
Optimized Data Routing Module

This module implements intelligent routing of data between storage backends:
- Content-aware backend selection based on data characteristics
- Cost-based routing algorithms to optimize for price vs performance
- Geographic routing for edge-optimized content delivery
- Bandwidth and latency analysis for network-aware decisions

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).
"""

import os
import json
import time
import logging
import asyncio
import random
from enum import Enum
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)


class RoutingStrategy(Enum):
    """Strategies for routing data between backends."""
    CONTENT_TYPE = "content_type"  # Route based on content type
    COST = "cost"                  # Route based on cost optimization
    LATENCY = "latency"            # Route based on latency optimization
    GEOGRAPHIC = "geographic"      # Route based on geographic proximity
    RELIABILITY = "reliability"    # Route based on backend reliability
    BALANCED = "balanced"          # Balanced approach considering multiple factors
    CUSTOM = "custom"              # Custom routing rules


class RoutingPriority(Enum):
    """Priority levels for routing decisions."""
    COST = "cost"                  # Prioritize cost savings
    PERFORMANCE = "performance"    # Prioritize performance
    RELIABILITY = "reliability"    # Prioritize reliability
    GEOGRAPHIC = "geographic"      # Prioritize geographic proximity


class ContentCategory(Enum):
    """Categories for different types of content."""
    SMALL_FILE = "small_file"          # Small files (< 1MB)
    MEDIUM_FILE = "medium_file"        # Medium files (1MB - 100MB)
    LARGE_FILE = "large_file"          # Large files (> 100MB)
    MEDIA = "media"                    # Media files (images, video, audio)
    DOCUMENT = "document"              # Documents (text, pdf, etc.)
    STRUCTURED_DATA = "structured_data"  # Structured data (JSON, XML, etc.)
    BINARY = "binary"                  # Binary data
    ENCRYPTED = "encrypted"            # Encrypted content
    OTHER = "other"                    # Other content


@dataclass
class BackendMetrics:
    """Performance and cost metrics for a storage backend."""
    # Performance metrics
    avg_latency_ms: float = 0.0
    success_rate: float = 1.0
    throughput_mbps: float = 0.0
    
    # Cost metrics
    storage_cost_per_gb: float = 0.0
    retrieval_cost_per_gb: float = 0.0
    bandwidth_cost_per_gb: float = 0.0
    
    # Usage metrics
    total_stored_bytes: float = 0.0
    total_retrieved_bytes: float = 0.0
    
    # Geographic metrics
    region: str = "unknown"
    multi_region: bool = False
    
    # Reliability metrics
    uptime_percentage: float = 99.9
    last_downtime: Optional[datetime] = None
    
    # Last update timestamp
    last_updated: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to a dictionary."""
        result = {
            "avg_latency_ms": self.avg_latency_ms,
            "success_rate": self.success_rate,
            "throughput_mbps": self.throughput_mbps,
            "storage_cost_per_gb": self.storage_cost_per_gb,
            "retrieval_cost_per_gb": self.retrieval_cost_per_gb,
            "bandwidth_cost_per_gb": self.bandwidth_cost_per_gb,
            "total_stored_bytes": self.total_stored_bytes,
            "total_retrieved_bytes": self.total_retrieved_bytes,
            "region": self.region,
            "multi_region": self.multi_region,
            "uptime_percentage": self.uptime_percentage,
            "last_updated": self.last_updated.isoformat()
        }
        
        if self.last_downtime:
            result["last_downtime"] = self.last_downtime.isoformat()
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BackendMetrics':
        """Create metrics from a dictionary."""
        # Handle datetime conversions
        last_updated = datetime.fromisoformat(data["last_updated"]) if "last_updated" in data else datetime.now()
        last_downtime = datetime.fromisoformat(data["last_downtime"]) if "last_downtime" in data else None
        
        return cls(
            avg_latency_ms=data.get("avg_latency_ms", 0.0),
            success_rate=data.get("success_rate", 1.0),
            throughput_mbps=data.get("throughput_mbps", 0.0),
            storage_cost_per_gb=data.get("storage_cost_per_gb", 0.0),
            retrieval_cost_per_gb=data.get("retrieval_cost_per_gb", 0.0),
            bandwidth_cost_per_gb=data.get("bandwidth_cost_per_gb", 0.0),
            total_stored_bytes=data.get("total_stored_bytes", 0.0),
            total_retrieved_bytes=data.get("total_retrieved_bytes", 0.0),
            region=data.get("region", "unknown"),
            multi_region=data.get("multi_region", False),
            uptime_percentage=data.get("uptime_percentage", 99.9),
            last_downtime=last_downtime,
            last_updated=last_updated
        )


@dataclass
class RoutingRule:
    """Rule for routing content to specific backends."""
    id: str
    name: str
    content_categories: List[ContentCategory]
    content_patterns: List[str] = field(default_factory=list)
    min_size_bytes: Optional[int] = None
    max_size_bytes: Optional[int] = None
    preferred_backends: List[str] = field(default_factory=list)
    excluded_backends: List[str] = field(default_factory=list)
    priority: RoutingPriority = RoutingPriority.BALANCED
    strategy: RoutingStrategy = RoutingStrategy.BALANCED
    custom_factors: Dict[str, float] = field(default_factory=dict)
    active: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert rule to a dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "content_categories": [cat.value for cat in self.content_categories],
            "content_patterns": self.content_patterns,
            "min_size_bytes": self.min_size_bytes,
            "max_size_bytes": self.max_size_bytes,
            "preferred_backends": self.preferred_backends,
            "excluded_backends": self.excluded_backends,
            "priority": self.priority.value,
            "strategy": self.strategy.value,
            "custom_factors": self.custom_factors,
            "active": self.active
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RoutingRule':
        """Create rule from a dictionary."""
        # Convert content categories from strings to enum values
        content_categories = []
        for cat in data.get("content_categories", []):
            try:
                content_categories.append(ContentCategory(cat))
            except ValueError:
                # Skip invalid categories
                pass
        
        # Convert priority and strategy from strings to enum values
        try:
            priority = RoutingPriority(data.get("priority", RoutingPriority.BALANCED.value))
        except ValueError:
            priority = RoutingPriority.BALANCED
        
        try:
            strategy = RoutingStrategy(data.get("strategy", RoutingStrategy.BALANCED.value))
        except ValueError:
            strategy = RoutingStrategy.BALANCED
        
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            content_categories=content_categories,
            content_patterns=data.get("content_patterns", []),
            min_size_bytes=data.get("min_size_bytes"),
            max_size_bytes=data.get("max_size_bytes"),
            preferred_backends=data.get("preferred_backends", []),
            excluded_backends=data.get("excluded_backends", []),
            priority=priority,
            strategy=strategy,
            custom_factors=data.get("custom_factors", {}),
            active=data.get("active", True)
        )


class ContentAnalyzer:
    """Analyzes content to determine its characteristics."""
    
    def __init__(self):
        """Initialize the content analyzer."""
        # MIME type to category mappings
        self.mime_category_map = {
            # Images
            "image/": ContentCategory.MEDIA,
            # Audio
            "audio/": ContentCategory.MEDIA,
            # Video
            "video/": ContentCategory.MEDIA,
            # Documents
            "text/": ContentCategory.DOCUMENT,
            "application/pdf": ContentCategory.DOCUMENT,
            "application/msword": ContentCategory.DOCUMENT,
            "application/vnd.openxmlformats-officedocument": ContentCategory.DOCUMENT,
            # Structured data
            "application/json": ContentCategory.STRUCTURED_DATA,
            "application/xml": ContentCategory.STRUCTURED_DATA,
            "application/yaml": ContentCategory.STRUCTURED_DATA,
            # Binary
            "application/octet-stream": ContentCategory.BINARY,
            "application/x-binary": ContentCategory.BINARY,
            # Encrypted (based on naming rather than MIME type)
            ".enc": ContentCategory.ENCRYPTED,
            ".pgp": ContentCategory.ENCRYPTED,
        }
    
    def analyze(self, content: Union[bytes, str], metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Analyze content to determine its characteristics.
        
        Args:
            content: Content to analyze (bytes or string)
            metadata: Optional metadata about the content
            
        Returns:
            Dict with content characteristics
        """
        # Initialize result
        result = {
            "size_bytes": 0,
            "category": ContentCategory.OTHER.value,
            "media_type": "application/octet-stream",
            "patterns_matched": []
        }
        
        # Determine size
        if isinstance(content, bytes):
            result["size_bytes"] = len(content)
        elif isinstance(content, str):
            result["size_bytes"] = len(content.encode('utf-8'))
        
        # Determine size category
        if result["size_bytes"] < 1024 * 1024:  # 1MB
            result["size_category"] = ContentCategory.SMALL_FILE.value
        elif result["size_bytes"] < 100 * 1024 * 1024:  # 100MB
            result["size_category"] = ContentCategory.MEDIUM_FILE.value
        else:
            result["size_category"] = ContentCategory.LARGE_FILE.value
        
        # Extract media type from metadata if available
        if metadata:
            if "content_type" in metadata:
                result["media_type"] = metadata["content_type"]
            elif "mime_type" in metadata:
                result["media_type"] = metadata["mime_type"]
            elif "filename" in metadata and "." in metadata["filename"]:
                # Try to guess from filename extension
                ext = metadata["filename"].split(".")[-1].lower()
                if ext in ["jpg", "jpeg", "png", "gif", "bmp", "tiff", "webp"]:
                    result["media_type"] = f"image/{ext}"
                elif ext in ["mp3", "wav", "ogg", "flac", "m4a"]:
                    result["media_type"] = f"audio/{ext}"
                elif ext in ["mp4", "avi", "mkv", "mov", "webm"]:
                    result["media_type"] = f"video/{ext}"
                elif ext in ["pdf"]:
                    result["media_type"] = "application/pdf"
                elif ext in ["doc", "docx"]:
                    result["media_type"] = "application/msword"
                elif ext in ["xls", "xlsx"]:
                    result["media_type"] = "application/vnd.ms-excel"
                elif ext in ["ppt", "pptx"]:
                    result["media_type"] = "application/vnd.ms-powerpoint"
                elif ext in ["json"]:
                    result["media_type"] = "application/json"
                elif ext in ["xml"]:
                    result["media_type"] = "application/xml"
                elif ext in ["yaml", "yml"]:
                    result["media_type"] = "application/yaml"
                elif ext in ["txt", "md", "rst"]:
                    result["media_type"] = "text/plain"
                elif ext in ["html", "htm"]:
                    result["media_type"] = "text/html"
                elif ext in ["css"]:
                    result["media_type"] = "text/css"
                elif ext in ["js"]:
                    result["media_type"] = "application/javascript"
                elif ext in ["enc", "pgp", "gpg"]:
                    result["media_type"] = "application/octet-stream"
                    result["category"] = ContentCategory.ENCRYPTED.value
        
        # Determine content category based on media type
        if result["category"] == ContentCategory.OTHER.value:  # Only if not already set
            for mime_prefix, category in self.mime_category_map.items():
                if result["media_type"].startswith(mime_prefix):
                    result["category"] = category.value
                    break
        
        # Additional pattern matching (for encrypted content, etc.)
        if isinstance(content, bytes) and content.startswith(b'-----BEGIN PGP'):
            result["category"] = ContentCategory.ENCRYPTED.value
            result["patterns_matched"].append("pgp_header")
        
        return result


class GeographicRouter:
    """Routes content based on geographic location."""
    
    def __init__(self):
        """Initialize the geographic router."""
        # Available regions
        self.regions = {
            "us-east": {"lat": 37.926868, "lon": -78.024902},
            "us-west": {"lat": 37.343577, "lon": -121.894684},
            "eu-central": {"lat": 50.110851, "lon": 8.682947},
            "eu-west": {"lat": 53.344189, "lon": -6.267664},
            "ap-southeast": {"lat": 1.352083, "lon": 103.819839},
            "ap-northeast": {"lat": 35.689487, "lon": 139.691711},
            "sa-east": {"lat": -23.550093, "lon": -46.633888},
        }
        
        # Client location (to be set by application)
        self.client_location = None
    
    def set_client_location(self, lat: float, lon: float) -> None:
        """
        Set the client's geographic location.
        
        Args:
            lat: Latitude
            lon: Longitude
        """
        self.client_location = {"lat": lat, "lon": lon}
    
    def get_nearest_region(self) -> Optional[str]:
        """
        Get the nearest region to the client.
        
        Returns:
            Region code or None if client location not set
        """
        if not self.client_location:
            return None
        
        # Find closest region
        min_distance = float("inf")
        nearest_region = None
        
        for region, coords in self.regions.items():
            # Calculate simple distance (not taking into account Earth's curvature)
            distance = ((self.client_location["lat"] - coords["lat"]) ** 2 +
                       (self.client_location["lon"] - coords["lon"]) ** 2) ** 0.5
            
            if distance < min_distance:
                min_distance = distance
                nearest_region = region
        
        return nearest_region
    
    def rank_backends_by_location(self, backend_regions: Dict[str, str]) -> List[str]:
        """
        Rank backends by proximity to client.
        
        Args:
            backend_regions: Dict mapping backend names to region codes
            
        Returns:
            List of backend names sorted by proximity
        """
        if not self.client_location:
            # No client location, return backends in original order
            return list(backend_regions.keys())
        
        # Calculate distances for each backend
        distances = {}
        for backend, region in backend_regions.items():
            if region not in self.regions:
                # Unknown region, use a large distance
                distances[backend] = float("inf")
                continue
            
            # Calculate distance to region
            coords = self.regions[region]
            distance = ((self.client_location["lat"] - coords["lat"]) ** 2 +
                       (self.client_location["lon"] - coords["lon"]) ** 2) ** 0.5
            
            distances[backend] = distance
        
        # Sort backends by distance
        return sorted(distances.keys(), key=lambda b: distances[b])


class CostOptimizer:
    """Optimizes content routing based on cost."""
    
    def __init__(self):
        """Initialize the cost optimizer."""
        pass
    
    def calculate_storage_cost(self, size_bytes: int, backend_metrics: BackendMetrics) -> float:
        """
        Calculate storage cost for a given size and backend.
        
        Args:
            size_bytes: Size in bytes
            backend_metrics: Backend metrics
            
        Returns:
            Estimated cost in USD
        """
        # Convert bytes to gigabytes
        size_gb = size_bytes / (1024 * 1024 * 1024)
        
        # Calculate cost
        return size_gb * backend_metrics.storage_cost_per_gb
    
    def calculate_retrieval_cost(self, size_bytes: int, backend_metrics: BackendMetrics) -> float:
        """
        Calculate retrieval cost for a given size and backend.
        
        Args:
            size_bytes: Size in bytes
            backend_metrics: Backend metrics
            
        Returns:
            Estimated cost in USD
        """
        # Convert bytes to gigabytes
        size_gb = size_bytes / (1024 * 1024 * 1024)
        
        # Calculate cost
        return size_gb * backend_metrics.retrieval_cost_per_gb
    
    def rank_backends_by_cost(
        self, 
        size_bytes: int, 
        backend_metrics: Dict[str, BackendMetrics],
        cost_type: str = "storage"
    ) -> List[str]:
        """
        Rank backends by cost for a given size.
        
        Args:
            size_bytes: Size in bytes
            backend_metrics: Dict mapping backend names to metrics
            cost_type: Type of cost to optimize for ("storage", "retrieval", or "both")
            
        Returns:
            List of backend names sorted by cost
        """
        costs = {}
        
        for backend, metrics in backend_metrics.items():
            # Calculate costs
            storage_cost = self.calculate_storage_cost(size_bytes, metrics)
            retrieval_cost = self.calculate_retrieval_cost(size_bytes, metrics)
            
            # Determine overall cost based on type
            if cost_type == "storage":
                costs[backend] = storage_cost
            elif cost_type == "retrieval":
                costs[backend] = retrieval_cost
            else:  # "both"
                costs[backend] = storage_cost + retrieval_cost
        
        # Sort backends by cost
        return sorted(costs.keys(), key=lambda b: costs[b])


class PerformanceOptimizer:
    """Optimizes content routing based on performance."""
    
    def __init__(self):
        """Initialize the performance optimizer."""
        pass
    
    def calculate_performance_score(
        self, 
        backend_metrics: BackendMetrics,
        latency_weight: float = 0.5,
        throughput_weight: float = 0.3,
        reliability_weight: float = 0.2
    ) -> float:
        """
        Calculate a performance score for a backend.
        
        Args:
            backend_metrics: Backend metrics
            latency_weight: Weight of latency in the score
            throughput_weight: Weight of throughput in the score
            reliability_weight: Weight of reliability in the score
            
        Returns:
            Performance score (higher is better)
        """
        # Normalize latency (lower is better, so invert)
        latency_score = 1.0 - min(1.0, backend_metrics.avg_latency_ms / 1000.0)
        
        # Normalize throughput (higher is better)
        throughput_score = min(1.0, backend_metrics.throughput_mbps / 100.0)
        
        # Reliability score (success rate)
        reliability_score = backend_metrics.success_rate
        
        # Calculate weighted score
        return (
            latency_score * latency_weight +
            throughput_score * throughput_weight +
            reliability_score * reliability_weight
        )
    
    def rank_backends_by_performance(
        self,
        backend_metrics: Dict[str, BackendMetrics],
        latency_weight: float = 0.5,
        throughput_weight: float = 0.3,
        reliability_weight: float = 0.2
    ) -> List[str]:
        """
        Rank backends by performance.
        
        Args:
            backend_metrics: Dict mapping backend names to metrics
            latency_weight: Weight of latency in the score
            throughput_weight: Weight of throughput in the score
            reliability_weight: Weight of reliability in the score
            
        Returns:
            List of backend names sorted by performance (best first)
        """
        scores = {}
        
        for backend, metrics in backend_metrics.items():
            scores[backend] = self.calculate_performance_score(
                metrics, latency_weight, throughput_weight, reliability_weight
            )
        
        # Sort backends by score (higher is better)
        return sorted(scores.keys(), key=lambda b: scores[b], reverse=True)


class DataRouter:
    """
    Main data routing system that selects optimal storage backends.
    
    This class implements the Optimized Data Routing feature from the MCP roadmap,
    providing content-aware backend selection and cost-based routing.
    """
    
    def __init__(self, backend_manager=None, config_path: Optional[str] = None):
        """
        Initialize the data router.
        
        Args:
            backend_manager: Storage backend manager
            config_path: Path to configuration file
        """
        self.backend_manager = backend_manager
        self.config_path = config_path or os.path.join(
            os.path.expanduser("~"), ".ipfs_kit", "routing_config.json"
        )
        
        # Initialize components
        self.content_analyzer = ContentAnalyzer()
        self.geographic_router = GeographicRouter()
        self.cost_optimizer = CostOptimizer()
        self.performance_optimizer = PerformanceOptimizer()
        
        # Initialize metrics and rules
        self.backend_metrics: Dict[str, BackendMetrics] = {}
        self.routing_rules: Dict[str, RoutingRule] = {}
        
        # Load configuration
        self._load_config()
        
        logger.info("Data Router initialized")
    
    def _load_config(self) -> None:
        """Load routing configuration from file."""
        if not os.path.exists(self.config_path):
            logger.info(f"Routing configuration file not found: {self.config_path}")
            self._init_default_config()
            return
        
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            # Load backend metrics
            self.backend_metrics = {}
            for backend_name, metrics_data in config.get("backend_metrics", {}).items():
                self.backend_metrics[backend_name] = BackendMetrics.from_dict(metrics_data)
            
            # Load routing rules
            self.routing_rules = {}
            for rule_data in config.get("routing_rules", []):
                rule = RoutingRule.from_dict(rule_data)
                self.routing_rules[rule.id] = rule
            
            logger.info(f"Loaded {len(self.backend_metrics)} backend metrics and {len(self.routing_rules)} routing rules")
        
        except Exception as e:
            logger.error(f"Error loading routing configuration: {e}")
            self._init_default_config()
    
    def _init_default_config(self) -> None:
        """Initialize default routing configuration."""
        # Initialize with empty metrics
        self.backend_metrics = {}
        
        # Create default routing rules
        self.routing_rules = {}
        
        # Add default rules
        
        # Rule for small files
        small_files_rule = RoutingRule(
            id="small_files",
            name="Small Files Routing",
            content_categories=[ContentCategory.SMALL_FILE],
            max_size_bytes=1024 * 1024,  # 1MB
            preferred_backends=["ipfs"],
            strategy=RoutingStrategy.PERFORMANCE,
            priority=RoutingPriority.PERFORMANCE
        )
        self.routing_rules[small_files_rule.id] = small_files_rule
        
        # Rule for media files
        media_rule = RoutingRule(
            id="media_files",
            name="Media Files Routing",
            content_categories=[ContentCategory.MEDIA],
            preferred_backends=["storacha", "s3"],
            strategy=RoutingStrategy.BALANCED,
            priority=RoutingPriority.PERFORMANCE
        )
        self.routing_rules[media_rule.id] = media_rule
        
        # Rule for large files
        large_files_rule = RoutingRule(
            id="large_files",
            name="Large Files Routing",
            content_categories=[ContentCategory.LARGE_FILE],
            min_size_bytes=100 * 1024 * 1024,  # 100MB
            preferred_backends=["filecoin"],
            strategy=RoutingStrategy.COST,
            priority=RoutingPriority.COST
        )
        self.routing_rules[large_files_rule.id] = large_files_rule
        
        # Rule for documents
        document_rule = RoutingRule(
            id="documents",
            name="Document Routing",
            content_categories=[ContentCategory.DOCUMENT],
            preferred_backends=["ipfs", "s3"],
            strategy=RoutingStrategy.BALANCED,
            priority=RoutingPriority.BALANCED
        )
        self.routing_rules[document_rule.id] = document_rule
        
        # Rule for encrypted content
        encrypted_rule = RoutingRule(
            id="encrypted",
            name="Encrypted Content Routing",
            content_categories=[ContentCategory.ENCRYPTED],
            preferred_backends=["ipfs", "filecoin"],
            strategy=RoutingStrategy.RELIABILITY,
            priority=RoutingPriority.RELIABILITY
        )
        self.routing_rules[encrypted_rule.id] = encrypted_rule
        
        # Save default configuration
        self._save_config()
    
    def _save_config(self) -> None:
        """Save routing configuration to file."""
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            
            config = {
                "backend_metrics": {name: metrics.to_dict() for name, metrics in self.backend_metrics.items()},
                "routing_rules": [rule.to_dict() for rule in self.routing_rules.values()]
            }
            
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            logger.info(f"Saved routing configuration to {self.config_path}")
        
        except Exception as e:
            logger.error(f"Error saving routing configuration: {e}")
    
    def update_backend_metrics(self, backend_name: str, metrics: BackendMetrics) -> None:
        """
        Update metrics for a storage backend.
        
        Args:
            backend_name: Name of the backend
            metrics: Updated metrics
        """
        self.backend_metrics[backend_name] = metrics
        self._save_config()
    
    def add_routing_rule(self, rule: RoutingRule) -> str:
        """
        Add a new routing rule.
        
        Args:
            rule: Routing rule to add
            
        Returns:
            Rule ID
        """
        self.routing_rules[rule.id] = rule
        self._save_config()
        return rule.id
    
    def update_routing_rule(self, rule_id: str, rule: RoutingRule) -> bool:
        """
        Update an existing routing rule.
        
        Args:
            rule_id: ID of the rule to update
            rule: Updated rule
            
        Returns:
            True if successful
        """
        if rule_id not in self.routing_rules:
            return False
        
        # Keep the same ID
        rule.id = rule_id
        self.routing_rules[rule_id] = rule
        self._save_config()
        return True
    
    def delete_routing_rule(self, rule_id: str) -> bool:
        """
        Delete a routing rule.
        
        Args:
            rule_id: ID of the rule to delete
            
        Returns:
            True if successful
        """
        if rule_id not in self.routing_rules:
            return False
        
        del self.routing_rules[rule_id]
        self._save_config()
        return True
    
    def get_routing_rule(self, rule_id: str) -> Optional[RoutingRule]:
        """
        Get a routing rule by ID.
        
        Args:
            rule_id: Rule ID
            
        Returns:
            Routing rule or None if not found
        """
        return self.routing_rules.get(rule_id)
    
    def list_routing_rules(self) -> List[RoutingRule]:
        """
        List all routing rules.
        
        Returns:
            List of routing rules
        """
        return list(self.routing_rules.values())
    
    def get_backend_metrics(self, backend_name: str) -> Optional[BackendMetrics]:
        """
        Get metrics for a storage backend.
        
        Args:
            backend_name: Name of the backend
            
        Returns:
            Backend metrics or None if not found
        """
        return self.backend_metrics.get(backend_name)
    
    def get_all_backend_metrics(self) -> Dict[str, BackendMetrics]:
        """
        Get metrics for all storage backends.
        
        Returns:
            Dict mapping backend names to metrics
        """
        return self.backend_metrics.copy()
    
    async def collect_backend_metrics(self) -> None:
        """
        Collect metrics for all available storage backends.
        
        This method updates backend_metrics with the latest performance data.
        """
        if not self.backend_manager:
            logger.warning("Cannot collect backend metrics: backend manager not available")
            return
        
        try:
            # Get available backends
            backends = self.backend_manager.list_backends()
            
            for backend_name in backends:
                # Get backend instance
                backend = self.backend_manager.get_backend(backend_name)
                if not backend:
                    continue
                
                # Get existing metrics or create new
                metrics = self.backend_metrics.get(backend_name, BackendMetrics())
                
                # Update metrics based on backend type
                if backend_name == "ipfs":
                    # Update IPFS metrics
                    metrics.storage_cost_per_gb = 0.0  # IPFS is free for storage
                    metrics.retrieval_cost_per_gb = 0.0  # IPFS is free for retrieval
                    
                    # Get stats if available
                    if hasattr(backend, "get_performance_metrics"):
                        perf_metrics = await backend.get_performance_metrics()
                        if perf_metrics:
                            # Update metrics from performance data
                            metrics.avg_latency_ms = perf_metrics.get("avg_latency_ms", metrics.avg_latency_ms)
                            metrics.success_rate = perf_metrics.get("success_rate", metrics.success_rate)
                            metrics.throughput_mbps = perf_metrics.get("throughput_mbps", metrics.throughput_mbps)
                    
                    # Get repo stats if available
                    try:
                        repo_stats = await backend.ipfs.ipfs_stats_repo()
                        if repo_stats and repo_stats.get("success", False):
                            metrics.total_stored_bytes = float(repo_stats.get("RepoSize", 0))
                    except:
                        pass
                
                elif backend_name == "filecoin":
                    # Update Filecoin metrics
                    metrics.storage_cost_per_gb = 0.00002  # $0.00002 per GB per month
                    metrics.retrieval_cost_per_gb = 0.0001  # $0.0001 per GB
                    metrics.region = "global"  # Filecoin is global
                    metrics.multi_region = True
                
                elif backend_name == "s3":
                    # Update S3 metrics
                    metrics.storage_cost_per_gb = 0.023  # $0.023 per GB per month (standard)
                    metrics.retrieval_cost_per_gb = 0.0  # $0.0 per GB (data transfer in is free)
                    metrics.bandwidth_cost_per_gb = 0.09  # $0.09 per GB (data transfer out)
                    metrics.region = "us-east-1"  # Default region
                
                elif backend_name == "storacha":
                    # Update Storacha metrics
                    metrics.storage_cost_per_gb = 0.015  # $0.015 per GB per month
                    metrics.retrieval_cost_per_gb = 0.0  # Assuming retrieval is free
                    metrics.region = "global"
                    metrics.multi_region = True
                
                # Update the timestamp
                metrics.last_updated = datetime.now()
                
                # Save updated metrics
                self.backend_metrics[backend_name] = metrics
            
            # Save updated metrics
            self._save_config()
            
        except Exception as e:
            logger.error(f"Error collecting backend metrics: {e}")
    
    def select_backend(
        self, 
        content: Union[bytes, str],
        metadata: Optional[Dict[str, Any]] = None,
        available_backends: Optional[List[str]] = None,
        strategy: Optional[RoutingStrategy] = None,
        priority: Optional[RoutingPriority] = None,
        client_location: Optional[Dict[str, float]] = None
    ) -> str:
        """
        Select the optimal backend for storing content.
        
        Args:
            content: Content to store
            metadata: Optional metadata about the content
            available_backends: Optional list of available backends
            strategy: Optional routing strategy to use
            priority: Optional routing priority
            client_location: Optional client location (lat/lon)
            
        Returns:
            Name of the selected backend
        """
        # Set client location if provided
        if client_location:
            self.geographic_router.set_client_location(
                client_location.get("lat", 0.0),
                client_location.get("lon", 0.0)
            )
        
        # Get available backends
        if available_backends is None:
            if self.backend_manager:
                available_backends = self.backend_manager.list_backends()
            else:
                # Default to common backends
                available_backends = ["ipfs", "filecoin", "s3", "storacha"]
        
        # If no backends available, return default
        if not available_backends:
            return "ipfs"  # Default to IPFS
        elif len(available_backends) == 1:
            return available_backends[0]  # Only one backend available
        
        # Analyze content
        content_analysis = self.content_analyzer.analyze(content, metadata)
        content_category = ContentCategory(content_analysis["category"])
        content_size = content_analysis["size_bytes"]
        
        # Find matching routing rules
        matching_rules = []
        for rule in self.routing_rules.values():
            if not rule.active:
                continue
            
            # Check content category
            if content_category in rule.content_categories:
                # Check size constraints
                if rule.min_size_bytes is not None and content_size < rule.min_size_bytes:
                    continue
                if rule.max_size_bytes is not None and content_size > rule.max_size_bytes:
                    continue
                
                # Check content patterns
                if rule.content_patterns:
                    pattern_matched = False
                    for pattern in rule.content_patterns:
                        if pattern in content_analysis["patterns_matched"]:
                            pattern_matched = True
                            break
                    if not pattern_matched:
                        continue
                
                # Rule matches
                matching_rules.append(rule)
        
        # If no rules match, use fallback logic
        if not matching_rules:
            # Use provided strategy or default to balanced
            routing_strategy = strategy or RoutingStrategy.BALANCED
            routing_priority = priority or RoutingPriority.BALANCED
        else:
            # Sort rules by priority (most specific first)
            # Assuming rules with more constraints are more specific
            matching_rules.sort(key=lambda r: (
                1 if r.min_size_bytes is not None else 0 +
                1 if r.max_size_bytes is not None else 0 +
                len(r.content_patterns) +
                len(r.preferred_backends)
            ), reverse=True)
            
            # Use the highest priority rule
            top_rule = matching_rules[0]
            routing_strategy = top_rule.strategy
            routing_priority = top_rule.priority
            
            # Filter available backends based on rule
            if top_rule.preferred_backends:
                preferred_available = [b for b in top_rule.preferred_backends if b in available_backends]
                if preferred_available:
                    available_backends = preferred_available
            
            # Remove excluded backends
            if top_rule.excluded_backends:
                available_backends = [b for b in available_backends if b not in top_rule.excluded_backends]
        
        # If we've filtered out all backends, use the original list
        if not available_backends:
            if self.backend_manager:
                available_backends = self.backend_manager.list_backends()
            else:
                available_backends = ["ipfs", "filecoin", "s3", "storacha"]
        
        # Apply routing strategy
        if routing_strategy == RoutingStrategy.CONTENT_TYPE:
            # Simple content type based routing
            if content_category == ContentCategory.SMALL_FILE:
                preferred = ["ipfs", "s3"]
            elif content_category == ContentCategory.LARGE_FILE:
                preferred = ["filecoin", "s3"]
            elif content_category == ContentCategory.MEDIA:
                preferred = ["storacha", "s3", "ipfs"]
            elif content_category == ContentCategory.DOCUMENT:
                preferred = ["ipfs", "s3"]
            elif content_category == ContentCategory.STRUCTURED_DATA:
                preferred = ["ipfs", "s3"]
            elif content_category == ContentCategory.ENCRYPTED:
                preferred = ["filecoin", "ipfs"]
            else:
                preferred = ["ipfs"]
            
            # Select first available preferred backend
            for backend in preferred:
                if backend in available_backends:
                    return backend
        
        elif routing_strategy == RoutingStrategy.COST:
            # Cost-based routing
            backend_metrics = {
                name: self.backend_metrics.get(name, BackendMetrics())
                for name in available_backends
            }
            
            ranked_backends = self.cost_optimizer.rank_backends_by_cost(
                content_size,
                backend_metrics,
                "storage" if routing_priority == RoutingPriority.COST else "both"
            )
            
            # Return the cheapest available backend
            if ranked_backends:
                return ranked_backends[0]
        
        elif routing_strategy == RoutingStrategy.LATENCY:
            # Latency-based routing
            backend_metrics = {
                name: self.backend_metrics.get(name, BackendMetrics())
                for name in available_backends
            }
            
            ranked_backends = self.performance_optimizer.rank_backends_by_performance(
                backend_metrics,
                latency_weight=0.8,
                throughput_weight=0.1,
                reliability_weight=0.1
            )
            
            # Return the fastest available backend
            if ranked_backends:
                return ranked_backends[0]
        
        elif routing_strategy == RoutingStrategy.GEOGRAPHIC:
            # Geographic routing
            backend_regions = {
                name: self.backend_metrics.get(name, BackendMetrics()).region
                for name in available_backends
            }
            
            ranked_backends = self.geographic_router.rank_backends_by_location(backend_regions)
            
            # Return the nearest available backend
            if ranked_backends:
                return ranked_backends[0]
        
        elif routing_strategy == RoutingStrategy.RELIABILITY:
            # Reliability-based routing
            backend_metrics = {
                name: self.backend_metrics.get(name, BackendMetrics())
                for name in available_backends
            }
            
            ranked_backends = self.performance_optimizer.rank_backends_by_performance(
                backend_metrics,
                latency_weight=0.1,
                throughput_weight=0.2,
                reliability_weight=0.7
            )
            
            # Return the most reliable available backend
            if ranked_backends:
                return ranked_backends[0]
        
        elif routing_strategy == RoutingStrategy.BALANCED or routing_strategy == RoutingStrategy.CUSTOM:
            # Balanced approach using multiple factors
            backend_metrics = {
                name: self.backend_metrics.get(name, BackendMetrics())
                for name in available_backends
            }
            
            # Calculate scores for each backend
            scores = {}
            
            for backend, metrics in backend_metrics.items():
                # Performance score
                perf_score = self.performance_optimizer.calculate_performance_score(metrics)
                
                # Cost score (lower is better, so invert)
                cost_per_gb = metrics.storage_cost_per_gb + metrics.retrieval_cost_per_gb / 10
                max_cost = 0.1  # $0.1 per GB is the max we consider
                cost_score = 1.0 - min(1.0, cost_per_gb / max_cost)
                
                # Geographic score
                if self.geographic_router.client_location:
                    geo_backends = {backend: metrics.region}
                    geo_rank = self.geographic_router.rank_backends_by_location(geo_backends)
                    geo_score = 1.0 if geo_rank and geo_rank[0] == backend else 0.5
                else:
                    geo_score = 0.5  # Neutral if no client location
                
                # Calculate weighted score based on priority
                if routing_priority == RoutingPriority.PERFORMANCE:
                    scores[backend] = perf_score * 0.6 + cost_score * 0.2 + geo_score * 0.2
                elif routing_priority == RoutingPriority.COST:
                    scores[backend] = perf_score * 0.2 + cost_score * 0.6 + geo_score * 0.2
                elif routing_priority == RoutingPriority.GEOGRAPHIC:
                    scores[backend] = perf_score * 0.2 + cost_score * 0.2 + geo_score * 0.6
                else:  # BALANCED
                    scores[backend] = perf_score * 0.4 + cost_score * 0.4 + geo_score * 0.2
            
            # Get backend with highest score
            if scores:
                return max(scores.items(), key=lambda x: x[1])[0]
        
        # Default fallback to first available backend
        return available_backends[0]
    
    async def route_content(
        self,
        content: Union[bytes, str],
        metadata: Optional[Dict[str, Any]] = None,
        strategy: Optional[RoutingStrategy] = None,
        priority: Optional[RoutingPriority] = None,
        client_location: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Route content to the optimal backend.
        
        Args:
            content: Content to store
            metadata: Optional metadata about the content
            strategy: Optional routing strategy to use
            priority: Optional routing priority
            client_location: Optional client location (lat/lon)
            
        Returns:
            Dict with routing result
        """
        if not self.backend_manager:
            return {
                "success": False,
                "error": "Backend manager not available",
                "error_type": "RouterError"
            }
        
        try:
            # Select backend
            backend_name = self.select_backend(
                content, metadata, None, strategy, priority, client_location
            )
            
            # Get backend
            backend = self.backend_manager.get_backend(backend_name)
            if not backend:
                return {
                    "success": False,
                    "error": f"Selected backend '{backend_name}' not available",
                    "error_type": "RouterError"
                }
            
            # Store content
            result = await backend.add_content(content, metadata)
            
            # Add routing information to result
            result["router_info"] = {
                "selected_backend": backend_name,
                "routing_strategy": strategy.value if strategy else "auto",
                "routing_priority": priority.value if priority else "auto",
                "content_analysis": self.content_analyzer.analyze(content, metadata)
            }
            
            return result
        
        except Exception as e:
            logger.error(f"Error routing content: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "RouterError"
            }
    
    def get_routing_analysis(
        self,
        content: Union[bytes, str],
        metadata: Optional[Dict[str, Any]] = None,
        client_location: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Get an analysis of how content would be routed.
        
        Args:
            content: Content to analyze
            metadata: Optional metadata about the content
            client_location: Optional client location (lat/lon)
            
        Returns:
            Dict with routing analysis
        """
        try:
            # Set client location if provided
            if client_location:
                self.geographic_router.set_client_location(
                    client_location.get("lat", 0.0),
                    client_location.get("lon", 0.0)
                )
            
            # Get available backends
            if self.backend_manager:
                available_backends = self.backend_manager.list_backends()
            else:
                # Default to common backends
                available_backends = ["ipfs", "filecoin", "s3", "storacha"]
            
            # Analyze content
            content_analysis = self.content_analyzer.analyze(content, metadata)
            
            # Get backend metrics
            backend_metrics = {
                name: self.backend_metrics.get(name, BackendMetrics())
                for name in available_backends
            }
            
            # Calculate routing options for different strategies
            routing_options = {}
            for strategy in RoutingStrategy:
                for priority in RoutingPriority:
                    try:
                        backend = self.select_backend(
                            content, 
                            metadata, 
                            available_backends, 
                            strategy, 
                            priority, 
                            client_location
                        )
                        key = f"{strategy.value}_{priority.value}"
                        routing_options[key] = backend
                    except:
                        pass
            
            # Calculate costs for each backend
            content_size = content_analysis["size_bytes"]
            costs = {}
            for backend, metrics in backend_metrics.items():
                storage_cost = self.cost_optimizer.calculate_storage_cost(content_size, metrics)
                retrieval_cost = self.cost_optimizer.calculate_retrieval_cost(content_size, metrics)
                costs[backend] = {
                    "storage_cost": storage_cost,
                    "retrieval_cost": retrieval_cost,
                    "total_cost": storage_cost + retrieval_cost
                }
            
            # Find applicable routing rules
            content_category = ContentCategory(content_analysis["category"])
            matching_rule_ids = []
            for rule in self.routing_rules.values():
                if not rule.active:
                    continue
                
                if content_category in rule.content_categories:
                    # Check size constraints
                    if rule.min_size_bytes is not None and content_size < rule.min_size_bytes:
                        continue
                    if rule.max_size_bytes is not None and content_size > rule.max_size_bytes:
                        continue
                    
                    matching_rule_ids.append(rule.id)
            
            # Return analysis
            return {
                "success": True,
                "content_analysis": content_analysis,
                "available_backends": available_backends,
                "routing_options": routing_options,
                "costs": costs,
                "matching_rules": matching_rule_ids,
                "optimal_backend": self.select_backend(
                    content, metadata, available_backends, None, None, client_location
                ),
                "client_location": self.geographic_router.client_location
            }
        
        except Exception as e:
            logger.error(f"Error analyzing routing: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "RouterError"
            }


# Helper function to validate a routing rule
def validate_routing_rule(rule_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate a routing rule configuration.
    
    Args:
        rule_data: Rule data to validate
        
    Returns:
        Tuple of (valid, error_message)
    """
    # Check required fields
    required_fields = ["id", "name", "content_categories"]
    for field in required_fields:
        if field not in rule_data:
            return False, f"Missing required field: {field}"
    
    # Check ID format
    if not isinstance(rule_data["id"], str) or not rule_data["id"]:
        return False, "ID must be a non-empty string"
    
    # Check content categories
    if not isinstance(rule_data["content_categories"], list) or not rule_data["content_categories"]:
        return False, "content_categories must be a non-empty list"
    
    # Check if content categories are valid
    for category in rule_data["content_categories"]:
        try:
            ContentCategory(category)
        except ValueError:
            return False, f"Invalid content category: {category}"
    
    # Check optional fields
    if "min_size_bytes" in rule_data and rule_data["min_size_bytes"] is not None:
        if not isinstance(rule_data["min_size_bytes"], int) or rule_data["min_size_bytes"] < 0:
            return False, "min_size_bytes must be a non-negative integer"
    
    if "max_size_bytes" in rule_data and rule_data["max_size_bytes"] is not None:
        if not isinstance(rule_data["max_size_bytes"], int) or rule_data["max_size_bytes"] < 0:
            return False, "max_size_bytes must be a non-negative integer"
    
    # Check size constraints
    if "min_size_bytes" in rule_data and "max_size_bytes" in rule_data:
        if rule_data["min_size_bytes"] is not None and rule_data["max_size_bytes"] is not None:
            if rule_data["min_size_bytes"] > rule_data["max_size_bytes"]:
                return False, "min_size_bytes cannot be greater than max_size_bytes"
    
    # Check strategy
    if "strategy" in rule_data:
        try:
            RoutingStrategy(rule_data["strategy"])
        except ValueError:
            return False, f"Invalid routing strategy: {rule_data['strategy']}"
    
    # Check priority
    if "priority" in rule_data:
        try:
            RoutingPriority(rule_data["priority"])
        except ValueError:
            return False, f"Invalid routing priority: {rule_data['priority']}"
    
    # All checks passed
    return True, None


# Factory function to create a data router instance
def create_data_router(backend_manager=None, config_path: Optional[str] = None) -> DataRouter:
    """
    Create a data router instance.
    
    Args:
        backend_manager: Storage backend manager
        config_path: Path to configuration file
        
    Returns:
        Data router instance
    """
    return DataRouter(backend_manager, config_path)