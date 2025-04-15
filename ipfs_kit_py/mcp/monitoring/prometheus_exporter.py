"""
Prometheus Exporter for MCP Server.

This module provides a Prometheus exporter for exposing MCP metrics to Prometheus.
"""

import logging
import time
from typing import Dict, List, Any, Optional, Callable, Set, Union
import threading
from contextlib import contextmanager

try:
    import prometheus_client
    from prometheus_client import (
        Counter, Gauge, Histogram, Summary, 
        REGISTRY, CONTENT_TYPE_LATEST,
        generate_latest, start_http_server
    )
    prometheus_available = True
except ImportError:
    prometheus_available = False
    # Create dummy classes for type checking when prometheus_client is not available
    class DummyMetric:
        def inc(self, amount=1): pass
        def dec(self, amount=1): pass
        def set(self, value): pass
        def observe(self, value): pass
    Counter = Gauge = Histogram = Summary = DummyMetric

from fastapi import FastAPI, Response, APIRouter

# Import metrics optimizer if available
try:
    from ipfs_kit_py.mcp.monitoring.metrics_optimizer import OptimizedMetricsRegistry, MetricsMemoryOptimizer
    metrics_optimizer_available = True
except ImportError:
    metrics_optimizer_available = False

# Configure logger
logger = logging.getLogger(__name__)

class PrometheusExporter:
    """
    Prometheus exporter for MCP metrics.
    
    This class provides functionality to export MCP metrics to Prometheus,
    including metrics for storage operations, backend performance, and API usage.
    
    Memory optimization has been implemented to address high memory usage
    when tracking many metrics.
    """
    
    def __init__(
        self,
        prefix: str = "mcp",
        enable_default_metrics: bool = True,
        auto_start_server: bool = False,
        port: int = 8000,
        path: str = "/metrics",
        max_metrics_per_type: int = 1000,
        retention_window_seconds: int = 3600,
        enable_memory_optimization: bool = True,
    ):
        """
        Initialize the Prometheus exporter.
        
        Args:
            prefix: Prefix for all metrics
            enable_default_metrics: Whether to enable default process metrics
            auto_start_server: Whether to start a standalone HTTP server
            port: Port for the standalone HTTP server
            path: Path for the metrics endpoint
            max_metrics_per_type: Maximum number of metrics per type (for memory optimization)
            retention_window_seconds: Time window to retain detailed metrics (for memory optimization)
            enable_memory_optimization: Whether to enable memory optimization
        """
        self.prefix = prefix
        self.path = path
        self.port = port
        self.auto_start_server = auto_start_server
        self.server = None
        
        # Memory optimization settings
        self.enable_memory_optimization = enable_memory_optimization
        self.max_metrics_per_type = max_metrics_per_type
        self.retention_window_seconds = retention_window_seconds
        
        # Initialize optimized metrics registry if memory optimization is enabled
        if self.enable_memory_optimization:
            self.optimized_registry = OptimizedMetricsRegistry(
                max_metrics_per_type=max_metrics_per_type,
                retention_window_seconds=retention_window_seconds,
            )
        else:
            self.optimized_registry = None
        
        # Initialize metrics collections
        self.counters = {}  # Dict[str, Counter]
        self.gauges = {}  # Dict[str, Gauge]
        self.histograms = {}  # Dict[str, Histogram]
        self.summaries = {}  # Dict[str, Summary]
        
        # Initialize default metrics if Prometheus is available
        if prometheus_available and enable_default_metrics:
            prometheus_client.start_http_server(port)
        
        # If auto_start_server is True, start the standalone HTTP server
        if prometheus_available and auto_start_server:
            self.server = start_http_server(port)
            logger.info(f"Started Prometheus HTTP server on port {port}")
            
        logger.info(f"Prometheus exporter initialized with prefix '{prefix}'")
        
        if self.enable_memory_optimization:
            logger.info(f"Memory optimization enabled with max {max_metrics_per_type} metrics per type")
    
    def create_counter(self, name: str, description: str, labels: Optional[List[str]] = None, category: str = "default") -> Counter:
        """
        Create a counter metric.
        
        Args:
            name: Metric name
            description: Metric description
            labels: List of label names
            category: Metric category for optimization
            
        Returns:
            Counter metric
        """
        if not prometheus_available:
            return Counter()
            
        full_name = f"{self.prefix}_{name}" if self.prefix else name
        
        if full_name in self.counters:
            return self.counters[full_name]
        
        counter = Counter(full_name, description, labels or [])
        self.counters[full_name] = counter
        
        # Register with optimizer if available
        if self.enable_memory_optimization and metrics_optimizer_available:
            self.optimized_registry.register_metric(counter, full_name, category)
            
        return counter
        
    def create_gauge(self, name: str, description: str, labels: Optional[List[str]] = None, category: str = "default") -> Gauge:
        """
        Create a gauge metric.
        
        Args:
            name: Metric name
            description: Metric description
            labels: List of label names
            category: Metric category for optimization
            
        Returns:
            Gauge metric
        """
        if not prometheus_available:
            return Gauge()
            
        full_name = f"{self.prefix}_{name}" if self.prefix else name
        
        if full_name in self.gauges:
            return self.gauges[full_name]
        
        gauge = Gauge(full_name, description, labels or [])
        self.gauges[full_name] = gauge
        
        # Register with optimizer if available
        if self.enable_memory_optimization and metrics_optimizer_available:
            self.optimized_registry.register_metric(gauge, full_name, category)
            
        return gauge
        
    def create_histogram(self, name: str, description: str, labels: Optional[List[str]] = None, 
                        buckets: Optional[List[float]] = None, category: str = "default") -> Histogram:
        """
        Create a histogram metric.
        
        Args:
            name: Metric name
            description: Metric description
            labels: List of label names
            buckets: List of bucket boundaries
            category: Metric category for optimization
            
        Returns:
            Histogram metric
        """
        if not prometheus_available:
            return Histogram()
            
        full_name = f"{self.prefix}_{name}" if self.prefix else name
        
        if full_name in self.histograms:
            return self.histograms[full_name]
        
        histogram = Histogram(full_name, description, labels or [], buckets=buckets)
        self.histograms[full_name] = histogram
        
        # Register with optimizer if available
        if self.enable_memory_optimization and metrics_optimizer_available:
            self.optimized_registry.register_metric(histogram, full_name, category)
            
        return histogram
        
    def update_counter(self, name: str, value: float = 1, labels: Optional[Dict[str, str]] = None) -> None:
        """
        Increment a counter metric.
        
        Args:
            name: Metric name
            value: Increment value
            labels: Label values
        """
        full_name = f"{self.prefix}_{name}" if self.prefix else name
        
        if full_name not in self.counters:
            logger.warning(f"Counter {full_name} not found")
            return
            
        counter = self.counters[full_name]
        
        # Check with optimizer if we should update
        if self.enable_memory_optimization and metrics_optimizer_available:
            if not self.optimized_registry.should_update_metric(full_name, value):
                return
        
        if labels:
            counter.labels(**labels).inc(value)
        else:
            counter.inc(value)
            
        # Track with optimizer
        if self.enable_memory_optimization and metrics_optimizer_available:
            self.optimized_registry.update_metric(full_name, value, "counter")
            
    def update_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """
        Update a gauge metric.
        
        Args:
            name: Metric name
            value: Current value
            labels: Label values
        """
        full_name = f"{self.prefix}_{name}" if self.prefix else name
        
        if full_name not in self.gauges:
            logger.warning(f"Gauge {full_name} not found")
            return
            
        gauge = self.gauges[full_name]
        
        # Check with optimizer if we should update
        if self.enable_memory_optimization and metrics_optimizer_available:
            if not self.optimized_registry.should_update_metric(full_name, value):
                return
        
        if labels:
            gauge.labels(**labels).set(value)
        else:
            gauge.set(value)
            
        # Track with optimizer
        if self.enable_memory_optimization and metrics_optimizer_available:
            self.optimized_registry.update_metric(full_name, value, "gauge")
            
    def observe_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """
        Observe a value for a histogram metric.
        
        Args:
            name: Metric name
            value: Observed value
            labels: Label values
        """
        full_name = f"{self.prefix}_{name}" if self.prefix else name
        
        if full_name not in self.histograms:
            logger.warning(f"Histogram {full_name} not found")
            return
            
        histogram = self.histograms[full_name]
        
        # Check with optimizer if we should update
        if self.enable_memory_optimization and metrics_optimizer_available:
            if not self.optimized_registry.should_update_metric(full_name, value):
                return
        
        if labels:
            histogram.labels(**labels).observe(value)
        else:
            histogram.observe(value)
            
        # Track with optimizer
        if self.enable_memory_optimization and metrics_optimizer_available:
            self.optimized_registry.update_metric(full_name, value, "histogram")
            
    def cleanup_metrics(self) -> None:
        """
        Clean up metrics that should no longer be tracked.
        Only has an effect if memory optimization is enabled.
        """
        if not self.enable_memory_optimization or not metrics_optimizer_available:
            return
            
        # Get metrics to retain
        retained_metrics = self.optimized_registry.get_retained_metrics()
        
        # Count metrics before cleanup
        total_before = len(self.counters) + len(self.gauges) + len(self.histograms) + len(self.summaries)
        
        # Remove metrics that are not in the retained set
        for metric_dict in [self.counters, self.gauges, self.histograms, self.summaries]:
            to_remove = []
            
            for full_name in metric_dict:
                if not full_name.startswith(f"{self.prefix}_"):
                    continue  # Skip metrics not created by this exporter
                    
                name = full_name[len(f"{self.prefix}_"):] if self.prefix else full_name
                
                if name not in retained_metrics:
                    to_remove.append(full_name)
            
            for full_name in to_remove:
                del metric_dict[full_name]
        
        # Count metrics after cleanup
        total_after = len(self.counters) + len(self.gauges) + len(self.histograms) + len(self.summaries)
        
        if total_before > total_after:
            logger.info(f"Cleaned up {total_before - total_after} metrics")
            
    def shutdown(self) -> None:
        """
        Shut down the exporter.
        """
        if self.enable_memory_optimization and metrics_optimizer_available:
            self.optimized_registry.shutdown()
            
        if self.server:
            self.server.shutdown()
            
        logger.info("Prometheus exporter shut down")
