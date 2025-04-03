"""
Prometheus metrics exporter for IPFS Kit.

This module provides a Prometheus metrics exporter for IPFS Kit that exposes
various performance metrics from the PerformanceMetrics class in a format
that can be scraped by Prometheus.

The exporter integrates with the existing performance_metrics module and
exposes metrics via a dedicated HTTP endpoint that follows the Prometheus
exposition format.
"""

import logging
import time
from typing import Dict, List, Optional, Set

from .performance_metrics import PerformanceMetrics

# Try to import Prometheus client
try:
    import prometheus_client
    from prometheus_client import Counter, Gauge, Histogram, Summary
    from prometheus_client.core import CollectorRegistry
    
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    # Create dummy classes for type checking
    class Counter:
        def inc(self, value=1):
            pass
        
    class Gauge:
        def set(self, value):
            pass
        
    class Histogram:
        def observe(self, value):
            pass
            
    class Summary:
        def observe(self, value):
            pass
            
    class CollectorRegistry:
        def __init__(self):
            pass


logger = logging.getLogger(__name__)


class PrometheusExporter:
    """
    Exports IPFS Kit metrics in Prometheus format.
    
    This class creates and updates Prometheus metrics based on the PerformanceMetrics
    class data, exposing them in a format that can be scraped by Prometheus.
    """
    
    def __init__(
        self,
        metrics: PerformanceMetrics,
        prefix: str = "ipfs",
        registry: Optional[CollectorRegistry] = None,
        labels: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize the Prometheus exporter.
        
        Args:
            metrics: PerformanceMetrics instance to export
            prefix: Prefix for metric names
            registry: Optional Prometheus registry to use
            labels: Common labels to apply to all metrics
        """
        self.metrics = metrics
        self.prefix = prefix
        self.labels = labels or {}
        
        # Check if Prometheus client is available
        if not PROMETHEUS_AVAILABLE:
            logger.warning(
                "Prometheus client not available. Install with 'pip install prometheus-client'"
            )
            self.enabled = False
            return
            
        self.enabled = True
        self.registry = registry or CollectorRegistry()
        
        # Create metrics
        self._create_metrics()
        
        # Set of operation names we've seen (for dynamic metrics)
        self.known_operations = set()
        
        # Track last update time
        self.last_update = 0
        
    def _create_metrics(self):
        """Create Prometheus metrics."""
        # Cache metrics
        self.cache_hits = Counter(
            f"{self.prefix}_cache_hits_total",
            "Total number of cache hits",
            list(self.labels.keys()),
            registry=self.registry,
        )
        
        self.cache_misses = Counter(
            f"{self.prefix}_cache_misses_total",
            "Total number of cache misses",
            list(self.labels.keys()),
            registry=self.registry,
        )
        
        self.cache_hit_ratio = Gauge(
            f"{self.prefix}_cache_hit_ratio",
            "Ratio of cache hits to total accesses",
            list(self.labels.keys()),
            registry=self.registry,
        )
        
        # Tier-specific cache metrics are created dynamically
        self.tier_hits = {}
        self.tier_misses = {}
        
        # Operation metrics
        self.operation_count = Counter(
            f"{self.prefix}_operations_total",
            "Count of IPFS operations by type",
            ["operation"] + list(self.labels.keys()),
            registry=self.registry,
        )
        
        self.operation_latency = Histogram(
            f"{self.prefix}_operation_latency_seconds",
            "Latency of IPFS operations",
            ["operation"] + list(self.labels.keys()),
            buckets=(
                0.005, 0.01, 0.025, 0.05, 0.075, 
                0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0, 30.0, 60.0, 120.0
            ),
            registry=self.registry,
        )
        
        # Bandwidth metrics
        self.bandwidth_inbound = Counter(
            f"{self.prefix}_bandwidth_inbound_bytes_total",
            "Total inbound bandwidth used",
            list(self.labels.keys()),
            registry=self.registry,
        )
        
        self.bandwidth_outbound = Counter(
            f"{self.prefix}_bandwidth_outbound_bytes_total",
            "Total outbound bandwidth used",
            list(self.labels.keys()),
            registry=self.registry,
        )
        
        # Error metrics
        self.errors_total = Counter(
            f"{self.prefix}_errors_total",
            "Total number of errors",
            list(self.labels.keys()),
            registry=self.registry,
        )
        
        self.error_count_by_type = Counter(
            f"{self.prefix}_errors_by_type_total",
            "Count of errors by type",
            ["error_type"] + list(self.labels.keys()),
            registry=self.registry,
        )
        
        # System metrics
        self.cpu_usage = Gauge(
            f"{self.prefix}_cpu_usage_percent",
            "CPU usage percentage",
            list(self.labels.keys()),
            registry=self.registry,
        )
        
        self.memory_usage = Gauge(
            f"{self.prefix}_memory_usage_percent",
            "Memory usage percentage",
            list(self.labels.keys()),
            registry=self.registry,
        )
        
        self.memory_available = Gauge(
            f"{self.prefix}_memory_available_bytes",
            "Available memory in bytes",
            list(self.labels.keys()),
            registry=self.registry,
        )
        
        self.disk_usage = Gauge(
            f"{self.prefix}_disk_usage_percent",
            "Disk usage percentage",
            list(self.labels.keys()),
            registry=self.registry,
        )
        
        self.disk_free = Gauge(
            f"{self.prefix}_disk_free_bytes",
            "Free disk space in bytes",
            list(self.labels.keys()),
            registry=self.registry,
        )
        
        # Throughput metrics
        self.operations_per_second = Gauge(
            f"{self.prefix}_operations_per_second",
            "Operations per second",
            list(self.labels.keys()),
            registry=self.registry,
        )
        
        self.bytes_per_second = Gauge(
            f"{self.prefix}_bytes_per_second",
            "Bytes per second (total)",
            list(self.labels.keys()),
            registry=self.registry,
        )
        
    def _ensure_tier_metrics(self, tier: str):
        """Ensure metrics exist for a specific cache tier."""
        if tier not in self.tier_hits:
            self.tier_hits[tier] = Counter(
                f"{self.prefix}_cache_tier_hits_total",
                "Total number of cache hits by tier",
                ["tier"] + list(self.labels.keys()),
                registry=self.registry,
            )
            
        if tier not in self.tier_misses:
            self.tier_misses[tier] = Counter(
                f"{self.prefix}_cache_tier_misses_total",
                "Total number of cache misses by tier",
                ["tier"] + list(self.labels.keys()),
                registry=self.registry,
            )
            
    def update(self):
        """Update Prometheus metrics from the performance metrics."""
        if not self.enabled:
            logger.debug("Prometheus exporter not enabled")
            return
            
        # Update timestamp
        self.last_update = time.time()
        
        try:
            # Update cache metrics
            cache_hits = self.metrics.cache["hits"]
            cache_misses = self.metrics.cache["misses"]
            total_accesses = cache_hits + cache_misses
            
            # Update with difference since last update to avoid double counting
            hit_diff = cache_hits - getattr(self, "_last_cache_hits", 0)
            miss_diff = cache_misses - getattr(self, "_last_cache_misses", 0)
            
            if hit_diff > 0:
                self.cache_hits.inc(hit_diff, labels=self.labels)
            if miss_diff > 0:
                self.cache_misses.inc(miss_diff, labels=self.labels)
                
            # Store current values for next calculation
            self._last_cache_hits = cache_hits
            self._last_cache_misses = cache_misses
            
            # Update cache hit ratio
            if total_accesses > 0:
                self.cache_hit_ratio.set(cache_hits / total_accesses, labels=self.labels)
            
            # Update tier-specific cache metrics
            for tier, stats in self.metrics.cache["tiers"].items():
                self._ensure_tier_metrics(tier)
                
                tier_hits = stats["hits"]
                tier_misses = stats["misses"]
                
                # Calculate differences since last update
                last_tier_hits = getattr(self, f"_last_tier_hits_{tier}", 0)
                last_tier_misses = getattr(self, f"_last_tier_misses_{tier}", 0)
                
                tier_hit_diff = tier_hits - last_tier_hits
                tier_miss_diff = tier_misses - last_tier_misses
                
                # Update metrics
                if tier_hit_diff > 0:
                    self.tier_hits[tier].inc(tier_hit_diff, labels={"tier": tier, **self.labels})
                if tier_miss_diff > 0:
                    self.tier_misses[tier].inc(tier_miss_diff, labels={"tier": tier, **self.labels})
                    
                # Store current values
                setattr(self, f"_last_tier_hits_{tier}", tier_hits)
                setattr(self, f"_last_tier_misses_{tier}", tier_misses)
            
            # Update operation metrics
            for op, count in self.metrics.operations.items():
                last_count = getattr(self, f"_last_op_count_{op}", 0)
                count_diff = count - last_count
                
                if count_diff > 0:
                    self.operation_count.inc(count_diff, labels={"operation": op, **self.labels})
                    
                setattr(self, f"_last_op_count_{op}", count)
                
                # Track this operation for latency metrics
                self.known_operations.add(op)
            
            # Update operation latency metrics
            # For each known operation, get the latest metrics
            for op in self.known_operations:
                if op in self.metrics.latency and self.metrics.latency[op]:
                    latency_values = list(self.metrics.latency[op])
                    last_latency_count = getattr(self, f"_last_latency_count_{op}", 0)
                    
                    # Only process new latency values
                    if len(latency_values) > last_latency_count:
                        new_values = latency_values[last_latency_count:]
                        for val in new_values:
                            self.operation_latency.observe(val, labels={"operation": op, **self.labels})
                            
                        setattr(self, f"_last_latency_count_{op}", len(latency_values))
            
            # Update bandwidth metrics
            inbound_total = sum(item["size"] for item in self.metrics.bandwidth["inbound"])
            outbound_total = sum(item["size"] for item in self.metrics.bandwidth["outbound"])
            
            last_inbound = getattr(self, "_last_inbound_total", 0)
            last_outbound = getattr(self, "_last_outbound_total", 0)
            
            inbound_diff = inbound_total - last_inbound
            outbound_diff = outbound_total - last_outbound
            
            if inbound_diff > 0:
                self.bandwidth_inbound.inc(inbound_diff, labels=self.labels)
            if outbound_diff > 0:
                self.bandwidth_outbound.inc(outbound_diff, labels=self.labels)
                
            self._last_inbound_total = inbound_total
            self._last_outbound_total = outbound_total
            
            # Update error metrics
            error_count = self.metrics.errors["count"]
            last_error_count = getattr(self, "_last_error_count", 0)
            error_diff = error_count - last_error_count
            
            if error_diff > 0:
                self.errors_total.inc(error_diff, labels=self.labels)
                
            self._last_error_count = error_count
            
            # Update error type metrics
            for error_type, count in self.metrics.errors["by_type"].items():
                last_type_count = getattr(self, f"_last_error_type_{error_type}", 0)
                type_diff = count - last_type_count
                
                if type_diff > 0:
                    self.error_count_by_type.inc(
                        type_diff, labels={"error_type": error_type, **self.labels}
                    )
                    
                setattr(self, f"_last_error_type_{error_type}", count)
            
            # Update system metrics if available
            if self.metrics.track_system_resources and self.metrics.system_metrics["cpu"]:
                # Get latest metrics
                latest_cpu = list(self.metrics.system_metrics["cpu"])[-1]
                latest_memory = list(self.metrics.system_metrics["memory"])[-1]
                latest_disk = list(self.metrics.system_metrics["disk"])[-1]
                
                # Update gauges
                self.cpu_usage.set(latest_cpu["percent"], labels=self.labels)
                self.memory_usage.set(latest_memory["percent"], labels=self.labels)
                self.memory_available.set(latest_memory["available"], labels=self.labels)
                self.disk_usage.set(latest_disk["percent"], labels=self.labels)
                self.disk_free.set(latest_disk["free"], labels=self.labels)
            
            # Update throughput metrics
            throughput = self.metrics.get_current_throughput()
            self.operations_per_second.set(throughput["operations_per_second"], labels=self.labels)
            self.bytes_per_second.set(throughput["bytes_per_second"], labels=self.labels)
            
        except Exception as e:
            logger.error(f"Error updating Prometheus metrics: {e}", exc_info=True)
    
    def collect(self):
        """
        Update metrics and return all metrics for Prometheus scraping.
        
        This method is called by the Prometheus client when scraping metrics.
        It updates the metrics and returns all collectors from the registry.
        """
        if not self.enabled:
            return []
            
        # Update metrics
        self.update()
        
        # Return all collectors from the registry
        return self.registry.collect()
        
    def generate_latest(self):
        """
        Generate Prometheus metrics output in text format.
        
        Returns:
            Metrics in Prometheus text format
        """
        if not self.enabled:
            return b""
            
        # Update metrics first
        self.update()
        
        # Generate metrics in Prometheus format
        return prometheus_client.generate_latest(self.registry)
        
    def start_server(self, port=9100, addr=""):
        """
        Start a metrics server for Prometheus scraping.
        
        Args:
            port: Port to listen on
            addr: Address to bind to
        """
        if not self.enabled:
            logger.error("Cannot start Prometheus metrics server: client not available")
            return False
            
        try:
            prometheus_client.start_http_server(port, addr, self.registry)
            logger.info(f"Started Prometheus metrics server on {addr or '0.0.0.0'}:{port}")
            return True
        except Exception as e:
            logger.error(f"Failed to start Prometheus metrics server: {e}", exc_info=True)
            return False


def add_prometheus_metrics_endpoint(app, metrics_instance: PerformanceMetrics, path="/metrics"):
    """
    Add a Prometheus metrics endpoint to a FastAPI application.
    
    Args:
        app: FastAPI application instance
        metrics_instance: PerformanceMetrics instance
        path: Endpoint path for metrics
        
    Returns:
        True if successful, False otherwise
    """
    if not PROMETHEUS_AVAILABLE:
        logger.warning("Prometheus client not available, skipping metrics endpoint")
        return False
        
    try:
        from fastapi import Request
        from fastapi.responses import Response
        
        # Create exporter
        exporter = PrometheusExporter(metrics_instance, prefix="ipfs_kit")
        
        # Add endpoint
        @app.get(path)
        async def metrics(request: Request):
            return Response(
                content=exporter.generate_latest(),
                media_type="text/plain",
            )
            
        logger.info(f"Added Prometheus metrics endpoint at {path}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to add Prometheus metrics endpoint: {e}", exc_info=True)
        return False