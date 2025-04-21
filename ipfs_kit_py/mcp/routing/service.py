"""
Optimized Data Routing service for MCP server.

This module implements the Optimized Data Routing functionality
as specified in the MCP roadmap for Phase 1: Core Functionality Enhancements (Q3 2025).
"""

import logging
import time
import asyncio
import json
import random
import math
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class BackendMetadata(BaseModel):
    """Backend metadata for routing decisions."""
    id: str = Field(..., description="Backend identifier")
    type: str = Field(..., description="Backend type")
    available: bool = Field(True, description="Whether the backend is available")
    capacity: int = Field(0, description="Storage capacity in bytes")
    used: int = Field(0, description="Used storage in bytes")
    reliability: float = Field(1.0, description="Reliability score (0-1)")
    performance: float = Field(1.0, description="Performance score (0-1)")
    cost_per_gb: float = Field(0.0, description="Cost per GB stored")
    geographic_region: Optional[str] = Field(None, description="Geographic region")
    latency: float = Field(0.0, description="Average latency in seconds")
    bandwidth: float = Field(float("inf"), description="Available bandwidth in bytes/s")
    max_file_size: Optional[int] = Field(None, description="Maximum file size in bytes")
    supports_metadata: bool = Field(False, description="Whether backend supports metadata")
    tier: str = Field("standard", description="Storage tier (hot, warm, cold)")
    labels: Dict[str, str] = Field(default_factory=dict, description="Custom labels")
    stats: Dict[str, Any] = Field(default_factory=dict, description="Statistics and metrics")
    last_updated: float = Field(default_factory=time.time, description="Last update timestamp")


class RoutingPolicy(BaseModel):
    """Routing policy definition."""
    id: str = Field(..., description="Policy identifier")
    name: str = Field(..., description="Policy name")
    description: Optional[str] = Field(None, description="Policy description")
    criteria: Dict[str, Any] = Field(..., description="Routing criteria")
    filter_backends: Optional[List[str]] = Field(None, description="Backends to include/exclude")
    weight_factors: Dict[str, float] = Field(
        default_factory=dict, description="Weighting factors for criteria"
    )
    content_patterns: Optional[Dict[str, Any]] = Field(
        None, description="Content patterns for routing"
    )
    active: bool = Field(True, description="Whether the policy is active")
    priority: int = Field(10, description="Policy priority (1-100)")
    fallback_backend: Optional[str] = Field(None, description="Fallback backend if policy fails")


class ContentRequest(BaseModel):
    """Content request metadata for routing decisions."""
    content_size: int = Field(..., description="Content size in bytes")
    content_type: Optional[str] = Field(None, description="Content type")
    content_id: Optional[str] = Field(None, description="Content identifier")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    priority: int = Field(0, description="Request priority (0-100)")
    geographic_region: Optional[str] = Field(None, description="Geographic region of request")
    client_ip: Optional[str] = Field(None, description="Client IP address")
    operation: str = Field("store", description="Operation type: store, retrieve, etc.")
    redundancy: int = Field(1, description="Number of copies to store")
    labels: Dict[str, str] = Field(default_factory=dict, description="Content labels")


class RoutingResult(BaseModel):
    """Result of routing decision."""
    backend_id: str = Field(..., description="Selected backend identifier")
    score: float = Field(..., description="Routing score")
    policy_id: Optional[str] = Field(None, description="ID of policy that made the decision")
    reasons: List[str] = Field(default_factory=list, description="Reasons for selection")
    alternatives: List[Dict[str, Any]] = Field(
        default_factory=list, description="Alternative backends"
    )
    estimated_latency: Optional[float] = Field(None, description="Estimated latency in seconds")
    estimated_cost: Optional[float] = Field(None, description="Estimated cost")
    content_hash: Optional[str] = Field(None, description="Content hash for verification")


class GeoLocation(BaseModel):
    """Geographic location information."""
    latitude: float = Field(..., description="Latitude")
    longitude: float = Field(..., description="Longitude")
    country: str = Field(..., description="Country code")
    region: str = Field(..., description="Region/state")
    city: Optional[str] = Field(None, description="City")
    timezone: Optional[str] = Field(None, description="Timezone")


class RouteStatistics(BaseModel):
    """Statistics for routing decisions."""
    total_requests: int = Field(0, description="Total routing requests")
    successful_routes: int = Field(0, description="Successful routing decisions")
    failed_routes: int = Field(0, description="Failed routing decisions")
    backend_usage: Dict[str, int] = Field(
        default_factory=dict, description="Usage count per backend"
    )
    policy_usage: Dict[str, int] = Field(default_factory=dict, description="Usage count per policy")
    avg_decision_time: float = Field(0.0, description="Average decision time in seconds")
    content_size_histogram: Dict[str, int] = Field(
        default_factory=dict, description="Content size histogram"
    )


class DataRoutingService:
    """
    Service for intelligent data routing across storage backends.

    This service implements the Optimized Data Routing requirements
    from the MCP roadmap, including content-aware backend selection,
    cost-based routing algorithms, and geographic optimization.
    """
    def __init__(self, backend_registry = None, metrics_service = None, geo_db_path = None):
        """
        Initialize the data routing service.

        Args:
            backend_registry: Registry of storage backends
            metrics_service: Metrics service for monitoring
            geo_db_path: Path to MaxMind GeoIP database (optional)
        """
        self.backend_registry = backend_registry
        self.metrics_service = metrics_service
        self.geo_db_path = geo_db_path

        # Backends metadata
        self.backends: Dict[str, BackendMetadata] = {}

        # Routing policies
        self.policies: Dict[str, RoutingPolicy] = {}

        # IP to location cache
        self.ip_location_cache: Dict[str, GeoLocation] = {}

        # Backend statistics
        self.backend_stats: Dict[str, Dict[str, Any]] = {}

        # Routing statistics
        self.stats = RouteStatistics()

        # Persistent storage for policies
        self.policies_file = "/tmp/ipfs_kit/mcp/routing/policies.json"

        # GeoIP provider (will be loaded if geo_db_path is provided)
        self.geo_provider = None

        # Cached geographic distances
        self.geo_distance_cache: Dict[str, Dict[str, float]] = {}

        # Default weighting factors
        self.default_weights = {
            "cost": 1.0,
            "performance": 1.0,
            "reliability": 1.0,
            "capacity": 0.7,
            "geographic": 0.5,
        }

        # Background tasks
        self.update_task = None

    async def start(self):
        """Start the data routing service."""
        logger.info("Starting data routing service")

        # Create data directories
        import os

        os.makedirs(os.path.dirname(self.policies_file), exist_ok=True)

        # Initialize GeoIP provider if a database path was provided
        if self.geo_db_path:
            try:
                import geoip2.database

                self.geo_provider = geoip2.database.Reader(self.geo_db_path)
                logger.info(f"Initialized GeoIP provider with database: {self.geo_db_path}")
            except Exception as e:
                logger.warning(f"Failed to initialize GeoIP provider: {e}")

        # Load routing policies
        await self.load_policies()

        # Create default policies if none exist
        if not self.policies:
            await self.create_default_policies()

        # Initialize backends metadata
        await self.update_backends_metadata()

        # Start backend metadata update task
        self.update_task = asyncio.create_task(self._update_backends_loop())

        logger.info("Data routing service started")

    async def stop(self):
        """Stop the data routing service."""
        logger.info("Stopping data routing service")

        # Cancel update task
        if self.update_task:
            self.update_task.cancel()
            try:
                await self.update_task
            except asyncio.CancelledError:
                pass

        # Save routing policies
        await self.save_policies()

        # Close GeoIP provider if open
        if self.geo_provider:
            self.geo_provider.close()

        logger.info("Data routing service stopped")

    async def load_policies(self):
        """Load routing policies from storage."""
        try:
            import os

            if os.path.exists(self.policies_file):
                import aiofiles

                async with aiofiles.open(self.policies_file, "r") as f:
                    content = await f.read()
                    policies_data = json.loads(content)

                    for policy_data in policies_data:
                        policy = RoutingPolicy(**policy_data)
                        self.policies[policy.id] = policy

                    logger.info(f"Loaded {len(self.policies)} routing policies")
            else:
                logger.info("No routing policies file found, will create defaults")
        except Exception as e:
            logger.error(f"Error loading routing policies: {e}")

    async def save_policies(self):
        """Save routing policies to storage."""
        try:
            policies_data = [policy.dict() for policy in self.policies.values()]

            import aiofiles

            async with aiofiles.open(self.policies_file, "w") as f:
                await f.write(json.dumps(policies_data, indent=2))

            logger.info(f"Saved {len(policies_data)} routing policies")
        except Exception as e:
            logger.error(f"Error saving routing policies: {e}")

    async def create_default_policies(self):
        """Create default routing policies."""
        try:
            # Cost-optimized policy
            cost_policy = RoutingPolicy(
                id="cost_optimized",
                name="Cost Optimized",
                description="Routes to the most cost-effective backend",
                criteria={"type": "cost", "min_reliability": 0.9},
                weight_factors={"cost": 3.0, "performance": 0.5, "reliability": 1.0},
                priority=50,
            )
            self.policies[cost_policy.id] = cost_policy

            # Performance-optimized policy
            perf_policy = RoutingPolicy(
                id="performance_optimized",
                name="Performance Optimized",
                description="Routes to the highest performance backend",
                criteria={"type": "performance", "min_reliability": 0.95},
                weight_factors={"cost": 0.5, "performance": 3.0, "reliability": 1.0},
                priority=40,
            )
            self.policies[perf_policy.id] = perf_policy

            # Geography-optimized policy
            geo_policy = RoutingPolicy(
                id="geographic_optimized",
                name="Geographic Optimized",
                description="Routes to the geographically closest backend",
                criteria={"type": "geographic", "min_reliability": 0.9},
                weight_factors={
                    "cost": 0.7,
                    "performance": 1.0,
                    "reliability": 1.0,
                    "geographic": 3.0,
                },
                priority=30,
            )
            self.policies[geo_policy.id] = geo_policy

            # Balanced policy
            balanced_policy = RoutingPolicy(
                id="balanced",
                name="Balanced",
                description="Balances cost, performance, and reliability",
                criteria={"type": "balanced", "min_reliability": 0.95},
                weight_factors={
                    "cost": 1.0,
                    "performance": 1.0,
                    "reliability": 1.0,
                    "geographic": 0.5,
                },
                priority=60,
            )
            self.policies[balanced_policy.id] = balanced_policy

            # Large file policy
            large_file_policy = RoutingPolicy(
                id="large_file",
                name="Large File Storage",
                description="Optimized for large files",
                criteria={
                    "type": "content",
                    "min_size": 100 * 1024 * 1024,  # 100MB
                    "min_reliability": 0.98,
                },
                weight_factors={
                    "cost": 1.5,
                    "performance": 1.0,
                    "reliability": 2.0,
                    "capacity": 2.0,
                },
                priority=20,
            )
            self.policies[large_file_policy.id] = large_file_policy

            # Archive policy
            archive_policy = RoutingPolicy(
                id="archive",
                name="Archive Storage",
                description="Long-term, reliable storage",
                criteria={
                    "type": "archive",
                    "preferred_tier": "cold",
                    "min_reliability": 0.99,
                },
                weight_factors={"cost": 2.0, "performance": 0.3, "reliability": 3.0},
                priority=10,
            )
            self.policies[archive_policy.id] = archive_policy

            await self.save_policies()
            logger.info("Created default routing policies")
        except Exception as e:
            logger.error(f"Error creating default policies: {e}")

    async def _update_backends_loop(self):
        """Continuously update backend metadata."""
        while True:
            try:
                await self.update_backends_metadata()
            except Exception as e:
                logger.error(f"Error updating backend metadata: {e}")

            # Sleep for 60 seconds before next update
            await asyncio.sleep(60)

    async def update_backends_metadata(self):
        """Update metadata for all backends."""
        if not self.backend_registry:
            logger.warning("Backend registry not available, using empty metadata")
            return

        try:
            # Get all available backends
            backend_ids = self.backend_registry.get_available_backends()

            for backend_id in backend_ids:
                try:
                    # Get backend module
                    backend_module = self.backend_registry.get_backend(backend_id)
                    if not backend_module:
                        continue

                    # Get backend metadata
                    backend_type = getattr(backend_module, "backend_type", "unknown")

                    # Check if we already have metadata for this backend
                    if backend_id in self.backends:
                        metadata = self.backends[backend_id]
                    else:
                        # Create new metadata
                        metadata = BackendMetadata(
                            id=backend_id,
                            type=backend_type,
                            available=True,
                            capacity=0,
                            used=0,
                            reliability=1.0,
                            performance=1.0,
                            cost_per_gb=0.0,
                            last_updated=time.time(),
                        )

                    # Update standard metadata
                    metadata.available = True
                    metadata.last_updated = time.time()

                    # Update specific backend properties
                    if hasattr(backend_module, "get_info"):
                        try:
                            info = await backend_module.get_info()
                            if info:
                                # Update capacity and used space
                                if "capacity" in info:
                                    metadata.capacity = info["capacity"]
                                if "used" in info:
                                    metadata.used = info["used"]

                                # Update other properties
                                if "reliability" in info:
                                    metadata.reliability = info["reliability"]
                                if "performance" in info:
                                    metadata.performance = info["performance"]
                                if "cost_per_gb" in info:
                                    metadata.cost_per_gb = info["cost_per_gb"]
                                if "geographic_region" in info:
                                    metadata.geographic_region = info["geographic_region"]
                                if "tier" in info:
                                    metadata.tier = info["tier"]
                                if "supports_metadata" in info:
                                    metadata.supports_metadata = info["supports_metadata"]
                                if "max_file_size" in info:
                                    metadata.max_file_size = info["max_file_size"]
                        except Exception as e:
                            logger.warning(f"Error getting info for backend {backend_id}: {e}")

                    # Update from backend statistics if available
                    if backend_id in self.backend_stats:
                        stats = self.backend_stats[backend_id]
                        metadata.stats = stats

                        # Update performance metrics from stats
                        if "avg_latency" in stats:
                            metadata.latency = stats["avg_latency"]
                        if "throughput" in stats:
                            metadata.bandwidth = stats["throughput"]

                    # Apply backend-specific defaults
                    if backend_type == "ipfs":
                        metadata.tier = "hot"
                        if not metadata.cost_per_gb:
                            metadata.cost_per_gb = 0.01
                    elif backend_type == "s3":
                        metadata.tier = "warm"
                        if not metadata.cost_per_gb:
                            metadata.cost_per_gb = 0.023
                    elif backend_type == "filecoin":
                        metadata.tier = "cold"
                        if not metadata.cost_per_gb:
                            metadata.cost_per_gb = 0.005

                    # Store updated metadata
                    self.backends[backend_id] = metadata
                except Exception as e:
                    logger.error(f"Error updating metadata for backend {backend_id}: {e}")

            # Remove metadata for backends that are no longer available
            for backend_id in list(self.backends.keys()):
                if backend_id not in backend_ids:
                    del self.backends[backend_id]
        except Exception as e:
            logger.error(f"Error updating backends metadata: {e}")

    async def update_backend_statistics(self, backend_id: str, stats: Dict[str, Any]):
        """
        Update statistics for a specific backend.

        Args:
            backend_id: Backend identifier
            stats: Statistics dictionary
        """
        self.backend_stats[backend_id] = stats

    async def route_content(
        self, request: ContentRequest, policy_id: Optional[str] = None
    ) -> RoutingResult:
        """
        Route a content request to the optimal backend.

        Args:
            request: Content request metadata
            policy_id: Optional specific policy to use

        Returns:
            Routing result with selected backend
        """
        start_time = time.time()

        try:
            self.stats.total_requests += 1

            # Get available backends
            available_backends = []
            for backend_id, metadata in self.backends.items():
                if metadata.available:
                    available_backends.append(backend_id)

            if not available_backends:
                self.stats.failed_routes += 1
                raise ValueError("No available backends for routing")

            # If policy_id is specified, use that policy
            if policy_id:
                policy = self.policies.get(policy_id)
                if not policy:
                    raise ValueError(f"Policy {policy_id} not found")

                # Apply the policy
                result = await self._apply_policy(policy, request, available_backends)
                if result:
                    # Update statistics
                    self.stats.successful_routes += 1
                    self.stats.backend_usage[result.backend_id] = (
                        self.stats.backend_usage.get(result.backend_id, 0) + 1
                    )
                    self.stats.policy_usage[policy.id] = (
                        self.stats.policy_usage.get(policy.id, 0) + 1
                    )

                    # Update content size histogram
                    size_bin = self._get_size_bin(request.content_size)
                    self.stats.content_size_histogram[size_bin] = (
                        self.stats.content_size_histogram.get(size_bin, 0) + 1
                    )

                    # Update metrics
                    self._update_metrics(request, result, time.time() - start_time)

                    return result
            else:
                # Try policies in priority order
                sorted_policies = sorted(
                    self.policies.values(), key=lambda p: p.priority, reverse=True
                )

                for policy in sorted_policies:
                    if not policy.active:
                        continue

                    result = await self._apply_policy(policy, request, available_backends)
                    if result:
                        # Update statistics
                        self.stats.successful_routes += 1
                        self.stats.backend_usage[result.backend_id] = (
                            self.stats.backend_usage.get(result.backend_id, 0) + 1
                        )
                        self.stats.policy_usage[policy.id] = (
                            self.stats.policy_usage.get(policy.id, 0) + 1
                        )

                        # Update content size histogram
                        size_bin = self._get_size_bin(request.content_size)
                        self.stats.content_size_histogram[size_bin] = (
                            self.stats.content_size_histogram.get(size_bin, 0) + 1
                        )

                        # Update metrics
                        self._update_metrics(request, result, time.time() - start_time)

                        return result

            # No policy matched, use fallback strategy (round-robin)
            backend_id = random.choice(available_backends)

            result = RoutingResult(
                backend_id=backend_id,
                score=0.5,
                reasons=["Fallback routing (no matching policy)"],
            )

            # Update statistics
            self.stats.successful_routes += 1
            self.stats.backend_usage[result.backend_id] = (
                self.stats.backend_usage.get(result.backend_id, 0) + 1
            )

            # Update content size histogram
            size_bin = self._get_size_bin(request.content_size)
            self.stats.content_size_histogram[size_bin] = (
                self.stats.content_size_histogram.get(size_bin, 0) + 1
            )

            # Update metrics
            self._update_metrics(request, result, time.time() - start_time)

            return result

        except Exception as e:
            self.stats.failed_routes += 1
            logger.error(f"Error routing content: {e}")
            raise
        finally:
            # Update average decision time
            decision_time = time.time() - start_time
            self.stats.avg_decision_time = (
                self.stats.avg_decision_time * (self.stats.total_requests - 1) + decision_time
            ) / self.stats.total_requests

    def _get_size_bin(self, size: int) -> str:
        """
        Get the appropriate size bin for a content size.

        Args:
            size: Content size in bytes

        Returns:
            Size bin label
        """
        if size < 1024:
            return "<1KB"
        elif size < 1024 * 1024:
            return "1KB-1MB"
        elif size < 10 * 1024 * 1024:
            return "1MB-10MB"
        elif size < 100 * 1024 * 1024:
            return "10MB-100MB"
        elif size < 1024 * 1024 * 1024:
            return "100MB-1GB"
        elif size < 10 * 1024 * 1024 * 1024:
            return "1GB-10GB"
        else:
            return ">10GB"

    def _update_metrics(self, request: ContentRequest, result: RoutingResult, duration: float):
        """
        Update metrics for a routing decision.

        Args:
            request: Content request
            result: Routing result
            duration: Decision duration in seconds
        """
        if self.metrics_service:
            try:

                # Record routing operation
                self.metrics_service.record_api_operation(
                    "route_content", "routing", time.time() - duration, "success"
                )
            except Exception as e:
                logger.error(f"Error updating metrics: {e}")

    async def _apply_policy(
    self,
    policy: RoutingPolicy
        request: ContentRequest
        available_backends: List[str]
    ) -> Optional[RoutingResult]:
        """
        Apply a routing policy to a content request.

        Args:
            policy: Routing policy
            request: Content request
            available_backends: List of available backends

        Returns:
            Routing result or None if policy doesn't apply
        """
        # Initialize list of potential backends
        potential_backends = []

        # Apply backend filters if specified
        filtered_backends = available_backends
        if policy.filter_backends:
            filtered_backends = [b for b in available_backends if b in policy.filter_backends]
            if not filtered_backends:
                return None

        # Check content patterns if specified
        if policy.content_patterns:
            # Check content type pattern
            if "content_type" in policy.content_patterns:
                pattern = policy.content_patterns["content_type"]
                if request.content_type and isinstance(pattern, str):
                    import re

                    if not re.match(pattern, request.content_type):
                        return None

            # Check content size range
            if "size_range" in policy.content_patterns:
                size_range = policy.content_patterns["size_range"]
                if "min" in size_range and request.content_size < size_range["min"]:
                    return None
                if "max" in size_range and request.content_size > size_range["max"]:
                    return None

            # Check content labels
            if "labels" in policy.content_patterns:
                required_labels = policy.content_patterns["labels"]
                for key, value in required_labels.items():
                    if key not in request.labels or request.labels[key] != value:
                        return None

        # Evaluate each backend against the criteria
        for backend_id in filtered_backends:
            metadata = self.backends.get(backend_id)
            if not metadata:
                continue

            # Check basic requirements
            if (
                policy.criteria.get("min_reliability")
                and metadata.reliability < policy.criteria["min_reliability"]
            ):
                continue

            if (
                request.content_size > 0
                and metadata.max_file_size
                and request.content_size > metadata.max_file_size
            ):
                continue

            if (
                policy.criteria.get("preferred_tier")
                and metadata.tier != policy.criteria["preferred_tier"]
            ):
                continue

            # Calculate score for this backend
            score = await self._calculate_backend_score(metadata, request, policy)

            # Add to potential backends
            potential_backends.append((backend_id, score))

        if not potential_backends:
            # Try fallback if specified
            if policy.fallback_backend and policy.fallback_backend in available_backends:
                metadata = self.backends.get(policy.fallback_backend)
                if metadata:
                    score = 0.5  # Default fallback score
                    potential_backends.append((policy.fallback_backend, score))

            if not potential_backends:
                return None

        # Sort backends by score, highest first
        potential_backends.sort(key=lambda x: x[1], reverse=True)

        # Select the highest scoring backend
        selected_backend_id, score = potential_backends[0]

        # Get selection reasons
        reasons = self._get_selection_reasons(self.backends[selected_backend_id], request, policy)

        # Create alternatives list
        alternatives = []
        for backend_id, alt_score in potential_backends[1:4]:  # Top 3 alternatives
            alternatives.append({"backend_id": backend_id, "score": alt_score})

        # Estimate latency if possible
        estimated_latency = self._estimate_latency(self.backends[selected_backend_id], request)

        # Estimate cost if possible
        estimated_cost = self._estimate_cost(self.backends[selected_backend_id], request)

        # Create routing result
        result = RoutingResult(
            backend_id=selected_backend_id,
            score=score,
            policy_id=policy.id,
            reasons=reasons,
            alternatives=alternatives,
            estimated_latency=estimated_latency,
            estimated_cost=estimated_cost,
        )

        return result

    async def _calculate_backend_score(
        self, metadata: BackendMetadata, request: ContentRequest, policy: RoutingPolicy
    ) -> float:
        """
        Calculate a score for a backend based on the routing policy.

        Args:
            metadata: Backend metadata
            request: Content request
            policy: Routing policy

        Returns:
            Score between 0 and 1
        """
        weights = policy.weight_factors or self.default_weights

        # Initialize score components
        components = {}

        # Cost score (lower is better)
        cost_factor = await self._calculate_cost_factor(metadata, request)
        components["cost"] = (1.0 - cost_factor) * weights.get("cost", 1.0)

        # Performance score (higher is better)
        perf_factor = await self._calculate_performance_factor(metadata, request)
        components["performance"] = perf_factor * weights.get("performance", 1.0)

        # Reliability score (higher is better)
        reliability_factor = metadata.reliability
        components["reliability"] = reliability_factor * weights.get("reliability", 1.0)

        # Capacity score (higher is better)
        if metadata.capacity > 0:
            capacity_factor = 1.0 - (metadata.used / metadata.capacity)
        else:
            capacity_factor = 0.5  # Default if capacity unknown
        components["capacity"] = capacity_factor * weights.get("capacity", 0.7)

        # Geographic score (higher is better)
        geo_factor = await self._calculate_geographic_factor(metadata, request)
        components["geographic"] = geo_factor * weights.get("geographic", 0.5)

        # Combine components
        total_weight = sum(weights.values())
        if total_weight > 0:
            score = sum(components.values()) / total_weight
        else:
            score = 0.5

        # Apply policy-specific adjustments
        if policy.criteria.get("type") == "cost" and metadata.cost_per_gb > 0:
            # Extra weight to cost factor for cost-optimized routing
            score = score * 0.7 + (1.0 - cost_factor) * 0.3
        elif policy.criteria.get("type") == "performance":
            # Extra weight to performance factor for performance-optimized routing
            score = score * 0.7 + perf_factor * 0.3
        elif policy.criteria.get("type") == "geographic":
            # Extra weight to geographic factor for geography-optimized routing
            score = score * 0.7 + geo_factor * 0.3
        elif policy.criteria.get("type") == "archive":
            # For archive, give extra weight to reliability
            score = score * 0.7 + reliability_factor * 0.3

        return min(1.0, max(0.0, score))

    async def _calculate_cost_factor(
        self, metadata: BackendMetadata, request: ContentRequest
    ) -> float:
        """
        Calculate a cost factor for a backend.

        Args:
            metadata: Backend metadata
            request: Content request

        Returns:
            Cost factor between 0 and 1 (lower is cheaper)
        """
        # If cost_per_gb is 0, assume it's free
        if metadata.cost_per_gb <= 0:
            return 0.0

        # Calculate raw cost for this request
        size_gb = request.content_size / (1024 * 1024 * 1024)
        raw_cost = metadata.cost_per_gb * size_gb

        # Normalize to a factor between 0 and 1
        # Using a logarithmic scale to handle wide range of costs
        if raw_cost <= 0:
            return 0.0

        # Using a logarithmic model where $0.001 -> 0.2, $0.01 -> 0.5, $0.1 -> 0.8
        log_factor = 0.2 + 0.3 * math.log10(raw_cost * 1000)
        return min(1.0, max(0.0, log_factor))

    async def _calculate_performance_factor(
        self, metadata: BackendMetadata, request: ContentRequest
    ) -> float:
        """
        Calculate a performance factor for a backend.

        Args:
            metadata: Backend metadata
            request: Content request

        Returns:
            Performance factor between 0 and 1 (higher is better)
        """
        # Start with the base performance rating
        perf_factor = metadata.performance

        # Adjust based on latency (lower is better)
        if metadata.latency > 0:
            latency_factor = math.exp(-metadata.latency)  # e^-x maps (0,inf) to (1,0)
            perf_factor = perf_factor * 0.7 + latency_factor * 0.3

        # Adjust based on tier
        if metadata.tier == "hot":
            perf_factor *= 1.2
        elif metadata.tier == "cold":
            perf_factor *= 0.8

        # Normalize to range [0,1]
        return min(1.0, max(0.0, perf_factor))

    async def _calculate_geographic_factor(
        self, metadata: BackendMetadata, request: ContentRequest
    ) -> float:
        """
        Calculate a geographic factor for a backend.

        Args:
            metadata: Backend metadata
            request: Content request

        Returns:
            Geographic factor between 0 and 1 (higher is better)
        """
        # If no geographic information is available, return neutral factor
        if not metadata.geographic_region or not request.geographic_region:
            return 0.5

        # If regions match exactly, that's optimal
        if metadata.geographic_region == request.geographic_region:
            return 1.0

        # Calculate distance factor if we have more detailed location info
        if self.geo_provider and request.client_ip:
            # Check cache first
            cache_key = f"{request.client_ip}:{metadata.geographic_region}"
            if cache_key in self.geo_distance_cache:
                distance_factor = self.geo_distance_cache[cache_key]
                return distance_factor

            # Get client location
            client_location = await self._get_location_from_ip(request.client_ip)
            if client_location:
                # Get backend location centroid
                backend_location = self._get_location_for_region(metadata.geographic_region)
                if backend_location:
                    # Calculate distance
                    distance = self._calculate_geo_distance(
                        client_location.latitude,
                        client_location.longitude,
                        backend_location.latitude,
                        backend_location.longitude,
                    )

                    # Convert to a factor between 0 and 1
                    # Using an exponential decay: e^(-d/5000), where d is in km
                    # This gives ~0.82 at 1000km, ~0.67 at 2000km, ~0.37 at 5000km
                    distance_factor = math.exp(-distance / 5000)

                    # Cache the result
                    self.geo_distance_cache[cache_key] = distance_factor

                    return distance_factor

        # Fallback: simple region comparison
        # Compare first parts of region codes (assuming format like "us-east", "eu-west")
        backend_region_parts = metadata.geographic_region.split("-")
        request_region_parts = request.geographic_region.split("-")

        if backend_region_parts and request_region_parts:
            if backend_region_parts[0] == request_region_parts[0]:
                # Same main region
                return (
                    0.9
                    if len(backend_region_parts) > 1
                    and len(request_region_parts) > 1
                    and backend_region_parts[1] != request_region_parts[1]
                    else 1.0
                )
            else:
                # Different main regions
                return 0.6

        # Default moderate factor
        return 0.5

    async def _get_location_from_ip(self, ip_address: str) -> Optional[GeoLocation]:
        """
        Get geographic location from an IP address.

        Args:
            ip_address: IP address

        Returns:
            GeoLocation or None if not found
        """
        # Check cache first
        if ip_address in self.ip_location_cache:
            return self.ip_location_cache[ip_address]

        if not self.geo_provider:
            return None

        try:
            # Look up IP in GeoIP database
            response = self.geo_provider.city(ip_address)

            location = GeoLocation(
                latitude=response.location.latitude,
                longitude=response.location.longitude,
                country=response.country.iso_code,
                region=(
                    response.subdivisions.most_specific.iso_code
                    if response.subdivisions
                    else "unknown"
                ),
                city=response.city.name,
                timezone=response.location.time_zone,
            )

            # Cache the result
            self.ip_location_cache[ip_address] = location

            return location
        except Exception as e:
            logger.warning(f"Error getting location for IP {ip_address}: {e}")
            return None

    def _get_location_for_region(self, region_code: str) -> Optional[GeoLocation]:
        """
        Get a geographic location for a region code.

        Args:
            region_code: Region code (e.g., "us-east", "eu-west")

        Returns:
            GeoLocation or None if not recognized
        """
        # Simple mapping of region codes to centroids
        region_map = {
            "us-east": GeoLocation(latitude=38.5, longitude=-77.5, country="US", region="VA"),
            "us-west": GeoLocation(latitude=37.7, longitude=-122.4, country="US", region="CA"),
            "eu-west": GeoLocation(latitude=51.5, longitude=-0.1, country="GB", region="LDN"),
            "eu-central": GeoLocation(latitude=50.1, longitude=8.6, country="DE", region="HE"),
            "ap-east": GeoLocation(latitude=22.3, longitude=114.1, country="HK", region="HK"),
            "ap-southeast": GeoLocation(latitude=1.3, longitude=103.8, country="SG", region="SG"),
            "ap-northeast": GeoLocation(latitude=35.7, longitude=139.7, country="JP", region="TK"),
            "sa-east": GeoLocation(latitude=-23.5, longitude=-46.6, country="BR", region="SP"),
        }

        # Check for exact match
        if region_code in region_map:
            return region_map[region_code]

        # Check for prefix match
        for code, location in region_map.items():
            if region_code.startswith(code.split("-")[0]):
                return location

        return None

    def _calculate_geo_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate distance between two geographic points using Haversine formula.

        Args:
            lat1: Latitude of point 1 in degrees
            lon1: Longitude of point 1 in degrees
            lat2: Latitude of point 2 in degrees
            lon2: Longitude of point 2 in degrees

        Returns:
            Distance in kilometers
        """
        # Convert to radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)

        # Haversine formula
        dlon = lon2_rad - lon1_rad
        dlat = lat2_rad - lat1_rad
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        radius = 6371  # Earth radius in kilometers

        return radius * c

    def _get_selection_reasons(
        self, metadata: BackendMetadata, request: ContentRequest, policy: RoutingPolicy
    ) -> List[str]:
        """
        Get human-readable reasons for backend selection.

        Args:
            metadata: Selected backend metadata
            request: Content request
            policy: Applied policy

        Returns:
            List of reason strings
        """
        reasons = []

        # Add policy-based reason
        reasons.append(f"Selected by '{policy.name}' policy")

        # Add specific reasons based on policy type
        if policy.criteria.get("type") == "cost":
            cost_per_gb = metadata.cost_per_gb
            reasons.append(f"Cost optimized: ${cost_per_gb:.4f}/GB")
        elif policy.criteria.get("type") == "performance":
            reasons.append(f"Performance optimized: {metadata.performance:.2f} performance score")
        elif policy.criteria.get("type") == "geographic":
            if metadata.geographic_region:
                reasons.append(f"Geographically optimized: {metadata.geographic_region} region")
        elif policy.criteria.get("type") == "archive":
            reasons.append(f"Optimized for archival: {metadata.reliability:.2f} reliability score")
        elif policy.criteria.get("type") == "content":
            reasons.append(f"Content-aware selection: {self._format_size(request.content_size)}")

        # Add capacity reason
        if metadata.capacity > 0:
            used_percent = (metadata.used / metadata.capacity) * 100
            reasons.append(
                f"Capacity: {used_percent:.1f}% used of {self._format_size(metadata.capacity)}"
            )

        return reasons

    def _format_size(self, size_bytes: int) -> str:
        """
        Format a byte size into a human-readable string.

        Args:
            size_bytes: Size in bytes

        Returns:
            Formatted size string
        """
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        elif size_bytes < 1024 * 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024 * 1024):.1f} TB"

    def _estimate_latency(
        self, metadata: BackendMetadata, request: ContentRequest
    ) -> Optional[float]:
        """
        Estimate latency for a content operation.

        Args:
            metadata: Backend metadata
            request: Content request

        Returns:
            Estimated latency in seconds or None if cannot estimate
        """
        # If we have historical latency, use that as a base
        if metadata.latency > 0:
            base_latency = metadata.latency
        else:
            # Estimate based on tier
            if metadata.tier == "hot":
                base_latency = 0.05  # 50ms
            elif metadata.tier == "warm":
                base_latency = 0.2  # 200ms
            elif metadata.tier == "cold":
                base_latency = 1.0  # 1s
            else:
                base_latency = 0.1  # 100ms

        # Adjust for content size
        size_factor = 1.0
        if request.content_size > 1024 * 1024:  # More than 1MB
            # Increase latency for large content based on estimated transfer time
            if metadata.bandwidth > 0 and metadata.bandwidth != float("inf"):
                transfer_time = request.content_size / metadata.bandwidth
                size_factor = 1.0 + transfer_time
            else:
                # Rough estimate if bandwidth unknown
                size_mb = request.content_size / (1024 * 1024)
                size_factor = 1.0 + (0.1 * math.log10(size_mb + 1))

        # Adjust for operation type
        op_factor = 1.0
        if request.operation == "store":
            op_factor = 1.2  # Store operations typically take longer
        elif request.operation == "retrieve":
            op_factor = 1.0
        elif request.operation == "delete":
            op_factor = 0.5  # Delete operations are typically faster

        return base_latency * size_factor * op_factor

    def _estimate_cost(self, metadata: BackendMetadata, request: ContentRequest) -> Optional[float]:
        """
        Estimate cost for a content operation.

        Args:
            metadata: Backend metadata
            request: Content request

        Returns:
            Estimated cost in USD or None if cannot estimate
        """
        if metadata.cost_per_gb <= 0:
            return 0.0

        # Calculate size in GB
        size_gb = request.content_size / (1024 * 1024 * 1024)

        # Base storage cost
        storage_cost = metadata.cost_per_gb * size_gb

        # Adjust based on operation
        op_factor = 1.0
        if request.operation == "store":
            op_factor = 1.0
        elif request.operation == "retrieve":
            # Some backends charge for retrieval
            if metadata.tier == "cold":
                op_factor = 0.2  # Retrieval charge for cold storage
            else:
                op_factor = 0.02  # Minimal retrieval charge for hot/warm
        elif request.operation == "delete":
            # Some backends charge minimal fees for delete
            op_factor = 0.01

        # Adjust for redundancy
        redundancy_factor = request.redundancy if request.redundancy > 0 else 1

        return storage_cost * op_factor * redundancy_factor

    async def get_routing_stats(self) -> Dict[str, Any]:
        """
        Get routing statistics.

        Returns:
            Dictionary of routing statistics
        """
        return self.stats.dict()

    async def create_policy(self, policy: RoutingPolicy) -> RoutingPolicy:
        """
        Create a new routing policy.

        Args:
            policy: Routing policy to create

        Returns:
            Created policy
        """
        if policy.id in self.policies:
            raise ValueError(f"Policy with ID {policy.id} already exists")

        self.policies[policy.id] = policy
        await self.save_policies()

        return policy

    async def update_policy(self, policy_id: str, policy: RoutingPolicy) -> RoutingPolicy:
        """
        Update an existing routing policy.

        Args:
            policy_id: ID of policy to update
            policy: Updated policy

        Returns:
            Updated policy
        """
        if policy_id not in self.policies:
            raise ValueError(f"Policy with ID {policy_id} not found")

        # Check if ID has changed
        if policy_id != policy.id:
            del self.policies[policy_id]

        self.policies[policy.id] = policy
        await self.save_policies()

        return policy

    async def delete_policy(self, policy_id: str) -> bool:
        """
        Delete a routing policy.

        Args:
            policy_id: ID of policy to delete

        Returns:
            True if policy was deleted
        """
        if policy_id not in self.policies:
            return False

        del self.policies[policy_id]
        await self.save_policies()

        return True

    async def get_policy(self, policy_id: str) -> Optional[RoutingPolicy]:
        """
        Get a routing policy by ID.

        Args:
            policy_id: Policy ID

        Returns:
            Policy or None if not found
        """
        return self.policies.get(policy_id)

    async def list_policies(self) -> List[RoutingPolicy]:
        """
        Get a list of all routing policies.

        Returns:
            List of routing policies
        """
        return list(self.policies.values())

    async def get_backend_metadata(self, backend_id: str) -> Optional[BackendMetadata]:
        """
        Get metadata for a specific backend.

        Args:
            backend_id: Backend ID

        Returns:
            Backend metadata or None if not found
        """
        return self.backends.get(backend_id)

    async def list_backend_metadata(self) -> List[BackendMetadata]:
        """
        Get metadata for all backends.

        Returns:
            List of backend metadata
        """
        return list(self.backends.values())
