"""
MCP Monitoring Module for system metrics and performance tracking.

This module provides comprehensive monitoring capabilities for the MCP server, including:
1. Performance metrics collection and analysis
2. Backend status monitoring
3. Usage statistics tracking
4. Health checks and alerting
5. Prometheus metrics exposure
"""

import os
import time
import json
import logging
import threading
import queue
import uuid
import platform
import socket
import psutil
from enum import Enum
from typing import Dict, Any, List, Optional, Callable, Union, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field

# Configure logger
logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics collected."""
    COUNTER = "counter"  # Monotonically increasing value
    GAUGE = "gauge"      # Value that can go up and down
    HISTOGRAM = "histogram"  # Distribution of values
    SUMMARY = "summary"  # Similar to histogram but with quantiles


class MetricUnit(Enum):
    """Units for metrics."""
    BYTES = "bytes"
    SECONDS = "seconds"
    OPERATIONS = "operations"
    PERCENTAGE = "percentage"
    COUNT = "count"
    MILLISECONDS = "milliseconds"
    REQUESTS = "requests"


class MetricTag(Enum):
    """Tags for categorizing metrics."""
    STORAGE = "storage"
    BACKEND = "backend"
    NETWORK = "network"
    SYSTEM = "system"
    API = "api"
    USER = "user"
    SEARCH = "search"
    MIGRATION = "migration"
    STREAMING = "streaming"


@dataclass
class Metric:
    """Definition of a metric."""
    name: str
    type: MetricType
    description: str
    unit: MetricUnit
    tags: List[MetricTag] = field(default_factory=list)
    labels: List[str] = field(default_factory=list)
    

@dataclass
class MetricSample:
    """Individual metric sample."""
    metric: Metric
    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    label_values: Dict[str, str] = field(default_factory=dict)
    

@dataclass
class MetricSeries:
    """Time series of metric samples."""
    metric: Metric
    samples: List[MetricSample] = field(default_factory=list)
    max_samples: int = 1000  # Maximum samples to keep in memory
    
    def add_sample(self, value: float, label_values: Optional[Dict[str, str]] = None) -> None:
        """
        Add a sample to the series.
        
        Args:
            value: Sample value
            label_values: Optional label values
        """
        sample = MetricSample(
            metric=self.metric,
            value=value,
            label_values=label_values or {}
        )
        
        self.samples.append(sample)
        
        # Trim if needed
        if len(self.samples) > self.max_samples:
            self.samples = self.samples[-self.max_samples:]
    
    def get_latest(self) -> Optional[MetricSample]:
        """
        Get the latest sample.
        
        Returns:
            Latest sample or None if no samples
        """
        if not self.samples:
            return None
        
        return self.samples[-1]
    
    def get_average(self, window_seconds: Optional[float] = None) -> Optional[float]:
        """
        Get average value over time window.
        
        Args:
            window_seconds: Optional time window in seconds (all samples if None)
            
        Returns:
            Average value or None if no samples
        """
        if not self.samples:
            return None
        
        if window_seconds is None:
            # Average all samples
            return sum(sample.value for sample in self.samples) / len(self.samples)
        
        # Get samples within time window
        now = datetime.now()
        cutoff = now - timedelta(seconds=window_seconds)
        
        window_samples = [
            sample for sample in self.samples
            if sample.timestamp >= cutoff
        ]
        
        if not window_samples:
            return None
        
        return sum(sample.value for sample in window_samples) / len(window_samples)
    
    def get_min_max(self, window_seconds: Optional[float] = None) -> Tuple[Optional[float], Optional[float]]:
        """
        Get minimum and maximum values over time window.
        
        Args:
            window_seconds: Optional time window in seconds (all samples if None)
            
        Returns:
            Tuple of (min, max) or (None, None) if no samples
        """
        if not self.samples:
            return None, None
        
        if window_seconds is None:
            # Min/max all samples
            values = [sample.value for sample in self.samples]
            return min(values), max(values)
        
        # Get samples within time window
        now = datetime.now()
        cutoff = now - timedelta(seconds=window_seconds)
        
        window_samples = [
            sample for sample in self.samples
            if sample.timestamp >= cutoff
        ]
        
        if not window_samples:
            return None, None
        
        values = [sample.value for sample in window_samples]
        return min(values), max(values)


class MetricsRegistry:
    """Registry for collecting and retrieving metrics."""
    
    def __init__(self):
        """Initialize the metrics registry."""
        self.metrics: Dict[str, Metric] = {}
        self.series: Dict[str, Dict[str, MetricSeries]] = {}
        self.counters: Dict[str, Dict[str, float]] = {}
        self.lock = threading.RLock()
        
        # Initialize standard metrics
        self._init_standard_metrics()
    
    def _init_standard_metrics(self) -> None:
        """Initialize standard system and MCP metrics."""
        # System metrics
        self.register_metric(
            name="system_cpu_usage",
            metric_type=MetricType.GAUGE,
            description="CPU usage percentage",
            unit=MetricUnit.PERCENTAGE,
            tags=[MetricTag.SYSTEM],
            labels=["cpu"]
        )
        
        self.register_metric(
            name="system_memory_usage",
            metric_type=MetricType.GAUGE,
            description="Memory usage",
            unit=MetricUnit.BYTES,
            tags=[MetricTag.SYSTEM]
        )
        
        self.register_metric(
            name="system_disk_usage",
            metric_type=MetricType.GAUGE,
            description="Disk usage",
            unit=MetricUnit.BYTES,
            tags=[MetricTag.SYSTEM],
            labels=["path"]
        )
        
        # Network metrics
        self.register_metric(
            name="network_bytes_sent",
            metric_type=MetricType.COUNTER,
            description="Network bytes sent",
            unit=MetricUnit.BYTES,
            tags=[MetricTag.NETWORK],
            labels=["interface"]
        )
        
        self.register_metric(
            name="network_bytes_received",
            metric_type=MetricType.COUNTER,
            description="Network bytes received",
            unit=MetricUnit.BYTES,
            tags=[MetricTag.NETWORK],
            labels=["interface"]
        )
        
        # API metrics
        self.register_metric(
            name="api_requests_total",
            metric_type=MetricType.COUNTER,
            description="Total API requests",
            unit=MetricUnit.REQUESTS,
            tags=[MetricTag.API],
            labels=["endpoint", "method", "status"]
        )
        
        self.register_metric(
            name="api_request_duration",
            metric_type=MetricType.HISTOGRAM,
            description="API request duration",
            unit=MetricUnit.MILLISECONDS,
            tags=[MetricTag.API],
            labels=["endpoint", "method"]
        )
        
        # Backend metrics
        self.register_metric(
            name="backend_operations_total",
            metric_type=MetricType.COUNTER,
            description="Total backend operations",
            unit=MetricUnit.OPERATIONS,
            tags=[MetricTag.BACKEND, MetricTag.STORAGE],
            labels=["backend", "operation", "status"]
        )
        
        self.register_metric(
            name="backend_operation_duration",
            metric_type=MetricType.HISTOGRAM,
            description="Backend operation duration",
            unit=MetricUnit.MILLISECONDS,
            tags=[MetricTag.BACKEND, MetricTag.STORAGE],
            labels=["backend", "operation"]
        )
        
        self.register_metric(
            name="backend_stored_bytes",
            metric_type=MetricType.GAUGE,
            description="Bytes stored in backend",
            unit=MetricUnit.BYTES,
            tags=[MetricTag.BACKEND, MetricTag.STORAGE],
            labels=["backend"]
        )
        
        # Migration metrics
        self.register_metric(
            name="migration_operations_total",
            metric_type=MetricType.COUNTER,
            description="Total migration operations",
            unit=MetricUnit.OPERATIONS,
            tags=[MetricTag.MIGRATION],
            labels=["source_backend", "target_backend", "status"]
        )
        
        self.register_metric(
            name="migration_bytes_transferred",
            metric_type=MetricType.COUNTER,
            description="Bytes transferred in migrations",
            unit=MetricUnit.BYTES,
            tags=[MetricTag.MIGRATION],
            labels=["source_backend", "target_backend"]
        )
        
        # Streaming metrics
        self.register_metric(
            name="streaming_operations_total",
            metric_type=MetricType.COUNTER,
            description="Total streaming operations",
            unit=MetricUnit.OPERATIONS,
            tags=[MetricTag.STREAMING],
            labels=["direction", "status"]
        )
        
        self.register_metric(
            name="streaming_bytes_transferred",
            metric_type=MetricType.COUNTER,
            description="Bytes transferred in streaming operations",
            unit=MetricUnit.BYTES,
            tags=[MetricTag.STREAMING],
            labels=["direction"]
        )
        
        # Search metrics
        self.register_metric(
            name="search_operations_total",
            metric_type=MetricType.COUNTER,
            description="Total search operations",
            unit=MetricUnit.OPERATIONS,
            tags=[MetricTag.SEARCH],
            labels=["index_type", "status"]
        )
        
        self.register_metric(
            name="search_operation_duration",
            metric_type=MetricType.HISTOGRAM,
            description="Search operation duration",
            unit=MetricUnit.MILLISECONDS,
            tags=[MetricTag.SEARCH],
            labels=["index_type"]
        )
    
    def register_metric(self, name: str, metric_type: MetricType, description: str,
                       unit: MetricUnit, tags: List[MetricTag] = None,
                       labels: List[str] = None) -> Metric:
        """
        Register a new metric.
        
        Args:
            name: Metric name
            metric_type: Type of metric
            description: Description of the metric
            unit: Unit of measurement
            tags: List of tags for categorization
            labels: List of label names for this metric
            
        Returns:
            Registered metric
        """
        with self.lock:
            if name in self.metrics:
                return self.metrics[name]
            
            metric = Metric(
                name=name,
                type=metric_type,
                description=description,
                unit=unit,
                tags=tags or [],
                labels=labels or []
            )
            
            self.metrics[name] = metric
            
            # Initialize series and counters
            self.series[name] = {}
            
            if metric_type == MetricType.COUNTER:
                self.counters[name] = {}
            
            return metric
    
    def _get_series_key(self, label_values: Dict[str, str]) -> str:
        """
        Get the series key for label values.
        
        Args:
            label_values: Label values
            
        Returns:
            Series key
        """
        if not label_values:
            return "_default_"
        
        # Sort by key for consistency
        return "_".join(f"{k}:{v}" for k, v in sorted(label_values.items()))
    
    def record_metric(self, name: str, value: float, 
                     label_values: Optional[Dict[str, str]] = None) -> None:
        """
        Record a metric value.
        
        Args:
            name: Metric name
            value: Metric value
            label_values: Optional label values
        """
        with self.lock:
            if name not in self.metrics:
                logger.warning(f"Metric {name} not registered")
                return
            
            metric = self.metrics[name]
            label_values = label_values or {}
            
            # Validate labels
            for label in label_values:
                if label not in metric.labels:
                    logger.warning(f"Label {label} not defined for metric {name}")
                    return
            
            # Get series key
            series_key = self._get_series_key(label_values)
            
            # Handle counter type specially
            if metric.type == MetricType.COUNTER:
                counter_key = series_key
                
                if counter_key not in self.counters[name]:
                    self.counters[name][counter_key] = 0
                
                # For counters, value is the increment
                self.counters[name][counter_key] += value
                
                # Update current value for recording
                value = self.counters[name][counter_key]
            
            # Get or create series
            if series_key not in self.series[name]:
                self.series[name][series_key] = MetricSeries(metric=metric)
            
            # Add sample
            self.series[name][series_key].add_sample(value, label_values)
    
    def increment_counter(self, name: str, 
                         increment: float = 1.0,
                         label_values: Optional[Dict[str, str]] = None) -> None:
        """
        Increment a counter metric.
        
        Args:
            name: Metric name
            increment: Value to increment by
            label_values: Optional label values
        """
        with self.lock:
            if name not in self.metrics:
                logger.warning(f"Metric {name} not registered")
                return
            
            metric = self.metrics[name]
            
            if metric.type != MetricType.COUNTER:
                logger.warning(f"Metric {name} is not a counter")
                return
            
            # Record metric with the increment value
            self.record_metric(name, increment, label_values)
    
    def set_gauge(self, name: str, value: float,
                 label_values: Optional[Dict[str, str]] = None) -> None:
        """
        Set a gauge metric value.
        
        Args:
            name: Metric name
            value: New gauge value
            label_values: Optional label values
        """
        with self.lock:
            if name not in self.metrics:
                logger.warning(f"Metric {name} not registered")
                return
            
            metric = self.metrics[name]
            
            if metric.type != MetricType.GAUGE:
                logger.warning(f"Metric {name} is not a gauge")
                return
            
            # Record the gauge value
            self.record_metric(name, value, label_values)
    
    def observe_histogram(self, name: str, value: float,
                         label_values: Optional[Dict[str, str]] = None) -> None:
        """
        Record a histogram observation.
        
        Args:
            name: Metric name
            value: Observed value
            label_values: Optional label values
        """
        with self.lock:
            if name not in self.metrics:
                logger.warning(f"Metric {name} not registered")
                return
            
            metric = self.metrics[name]
            
            if metric.type != MetricType.HISTOGRAM and metric.type != MetricType.SUMMARY:
                logger.warning(f"Metric {name} is not a histogram or summary")
                return
            
            # Record the observation
            self.record_metric(name, value, label_values)
    
    def get_metric_value(self, name: str, 
                        label_values: Optional[Dict[str, str]] = None) -> Optional[float]:
        """
        Get the latest value of a metric.
        
        Args:
            name: Metric name
            label_values: Optional label values
            
        Returns:
            Latest metric value or None if not found
        """
        with self.lock:
            if name not in self.metrics:
                logger.warning(f"Metric {name} not registered")
                return None
            
            # Get series key
            series_key = self._get_series_key(label_values or {})
            
            # Check if series exists
            if series_key not in self.series[name]:
                return None
            
            # Get latest sample
            latest = self.series[name][series_key].get_latest()
            
            if latest is None:
                return None
            
            return latest.value
    
    def get_metrics(self, tag: Optional[MetricTag] = None) -> Dict[str, Dict[str, Any]]:
        """
        Get all metrics, optionally filtered by tag.
        
        Args:
            tag: Optional tag to filter by
            
        Returns:
            Dictionary of metrics
        """
        result = {}
        
        with self.lock:
            for name, metric in self.metrics.items():
                # Filter by tag if specified
                if tag and tag not in metric.tags:
                    continue
                
                # Get all series for this metric
                metric_series = {}
                
                for series_key, series in self.series[name].items():
                    latest = series.get_latest()
                    
                    if latest:
                        # Create entry with latest value and labels
                        series_entry = {
                            "value": latest.value,
                            "timestamp": latest.timestamp.isoformat(),
                            "labels": latest.label_values
                        }
                        
                        metric_series[series_key] = series_entry
                
                # Add metric information
                result[name] = {
                    "description": metric.description,
                    "type": metric.type.value,
                    "unit": metric.unit.value,
                    "tags": [tag.value for tag in metric.tags],
                    "series": metric_series
                }
        
        return result
    
    def get_prometheus_metrics(self) -> str:
        """
        Get metrics in Prometheus exposition format.
        
        Returns:
            Prometheus metrics text
        """
        lines = []
        
        with self.lock:
            for name, metric in sorted(self.metrics.items()):
                # Add metric help comment
                prometheus_name = name.replace('.', '_')
                lines.append(f"# HELP {prometheus_name} {metric.description}")
                
                # Add metric type comment
                prom_type = "gauge"
                if metric.type == MetricType.COUNTER:
                    prom_type = "counter"
                elif metric.type == MetricType.HISTOGRAM:
                    prom_type = "histogram"
                elif metric.type == MetricType.SUMMARY:
                    prom_type = "summary"
                
                lines.append(f"# TYPE {prometheus_name} {prom_type}")
                
                # Add samples for each series
                for series_key, series in self.series[name].items():
                    latest = series.get_latest()
                    
                    if latest:
                        # Format labels
                        label_str = ""
                        if latest.label_values:
                            label_fragments = []
                            for k, v in sorted(latest.label_values.items()):
                                # Escape backslash, double quote and newline in label values
                                v = v.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
                                label_fragments.append(f'{k}="{v}"')
                            
                            label_str = "{" + ",".join(label_fragments) + "}"
                        
                        # Add sample line
                        lines.append(f"{prometheus_name}{label_str} {latest.value}")
        
        return "\n".join(lines) + "\n"


class SystemMonitor:
    """Monitor for system metrics."""
    
    def __init__(self, metrics_registry: MetricsRegistry):
        """
        Initialize the system monitor.
        
        Args:
            metrics_registry: Metrics registry to record to
        """
        self.metrics = metrics_registry
        self.running = False
        self.monitor_thread = None
        self.interval = 10  # seconds
    
    def start(self, interval: int = 10) -> None:
        """
        Start monitoring system metrics.
        
        Args:
            interval: Collection interval in seconds
        """
        if self.running:
            return
        
        self.interval = interval
        self.running = True
        
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True
        )
        self.monitor_thread.start()
    
    def stop(self) -> None:
        """Stop monitoring system metrics."""
        self.running = False
        
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5.0)
    
    def _monitor_loop(self) -> None:
        """Background thread to collect system metrics."""
        while self.running:
            try:
                # Collect CPU metrics
                cpu_percent = psutil.cpu_percent(interval=None, percpu=True)
                for i, percent in enumerate(cpu_percent):
                    self.metrics.set_gauge(
                        "system_cpu_usage",
                        percent,
                        label_values={"cpu": str(i)}
                    )
                
                # Collect overall CPU usage
                self.metrics.set_gauge(
                    "system_cpu_usage",
                    psutil.cpu_percent(interval=None),
                    label_values={"cpu": "total"}
                )
                
                # Collect memory metrics
                memory = psutil.virtual_memory()
                self.metrics.set_gauge("system_memory_usage", memory.used)
                
                # Collect disk metrics
                for path in ["/", "/home"]:
                    try:
                        disk = psutil.disk_usage(path)
                        self.metrics.set_gauge(
                            "system_disk_usage",
                            disk.used,
                            label_values={"path": path}
                        )
                    except Exception as e:
                        logger.warning(f"Error collecting disk metrics for {path}: {e}")
                
                # Collect network metrics
                net_io = psutil.net_io_counters(pernic=True)
                for interface, counts in net_io.items():
                    self.metrics.set_gauge(
                        "network_bytes_sent",
                        counts.bytes_sent,
                        label_values={"interface": interface}
                    )
                    
                    self.metrics.set_gauge(
                        "network_bytes_received",
                        counts.bytes_recv,
                        label_values={"interface": interface}
                    )
                
            except Exception as e:
                logger.error(f"Error collecting system metrics: {e}")
            
            # Sleep until next collection interval
            time.sleep(self.interval)


class BackendMonitor:
    """Monitor for backend metrics."""
    
    def __init__(self, metrics_registry: MetricsRegistry, backend_registry: Dict[str, Any]):
        """
        Initialize the backend monitor.
        
        Args:
            metrics_registry: Metrics registry to record to
            backend_registry: Dictionary mapping backend names to instances
        """
        self.metrics = metrics_registry
        self.backend_registry = backend_registry
        self.running = False
        self.monitor_thread = None
        self.interval = 30  # seconds
    
    def start(self, interval: int = 30) -> None:
        """
        Start monitoring backend metrics.
        
        Args:
            interval: Collection interval in seconds
        """
        if self.running:
            return
        
        self.interval = interval
        self.running = True
        
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True
        )
        self.monitor_thread.start()
    
    def stop(self) -> None:
        """Stop monitoring backend metrics."""
        self.running = False
        
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5.0)
    
    def _monitor_loop(self) -> None:
        """Background thread to collect backend metrics."""
        while self.running:
            try:
                # Check each backend
                for backend_name, backend in self.backend_registry.items():
                    try:
                        # Try to get status if available
                        if hasattr(backend, 'get_status'):
                            start_time = time.time()
                            status = backend.get_status()
                            elapsed_ms = (time.time() - start_time) * 1000
                            
                            # Record status check duration
                            self.metrics.observe_histogram(
                                "backend_operation_duration",
                                elapsed_ms,
                                label_values={
                                    "backend": backend_name,
                                    "operation": "get_status"
                                }
                            )
                            
                            # Record operation count
                            self.metrics.increment_counter(
                                "backend_operations_total",
                                label_values={
                                    "backend": backend_name,
                                    "operation": "get_status",
                                    "status": "success" if status.get("success", False) else "failure"
                                }
                            )
                            
                            # Extract storage size if available
                            if status.get("success", False):
                                stored_bytes = self._extract_stored_bytes(status)
                                if stored_bytes is not None:
                                    self.metrics.set_gauge(
                                        "backend_stored_bytes",
                                        stored_bytes,
                                        label_values={"backend": backend_name}
                                    )
                    
                    except Exception as e:
                        logger.warning(f"Error monitoring backend {backend_name}: {e}")
                        
                        # Record failure
                        self.metrics.increment_counter(
                            "backend_operations_total",
                            label_values={
                                "backend": backend_name,
                                "operation": "get_status",
                                "status": "error"
                            }
                        )
            
            except Exception as e:
                logger.error(f"Error in backend monitoring: {e}")
            
            # Sleep until next collection interval
            time.sleep(self.interval)
    
    def _extract_stored_bytes(self, status: Dict[str, Any]) -> Optional[float]:
        """
        Extract stored bytes from backend status.
        
        Args:
            status: Backend status dictionary
            
        Returns:
            Stored bytes or None if not available
        """
        # Try different possible locations in the status
        if "stored_bytes" in status:
            return float(status["stored_bytes"])
        
        if "storage" in status and "used_bytes" in status["storage"]:
            return float(status["storage"]["used_bytes"])
        
        if "status" in status:
            if "stored_bytes" in status["status"]:
                return float(status["status"]["stored_bytes"])
            
            if "storage" in status["status"] and "used_bytes" in status["status"]["storage"]:
                return float(status["status"]["storage"]["used_bytes"])
            
            if "storage" in status["status"] and "size" in status["status"]["storage"]:
                return float(status["status"]["storage"]["size"])
        
        if "details" in status and "size" in status["details"]:
            return float(status["details"]["size"])
        
        # Not found
        return None
    
    def record_operation(self, backend_name: str, operation: str, 
                        duration_ms: float, success: bool = True,
                        bytes_processed: Optional[float] = None) -> None:
        """
        Record a backend operation.
        
        Args:
            backend_name: Name of the backend
            operation: Operation name
            duration_ms: Duration in milliseconds
            success: Whether the operation was successful
            bytes_processed: Optional bytes processed
        """
        # Record operation duration
        self.metrics.observe_histogram(
            "backend_operation_duration",
            duration_ms,
            label_values={
                "backend": backend_name,
                "operation": operation
            }
        )
        
        # Record operation count
        self.metrics.increment_counter(
            "backend_operations_total",
            label_values={
                "backend": backend_name,
                "operation": operation,
                "status": "success" if success else "failure"
            }
        )


class APIMonitor:
    """Monitor for API metrics."""
    
    def __init__(self, metrics_registry: MetricsRegistry):
        """
        Initialize the API monitor.
        
        Args:
            metrics_registry: Metrics registry to record to
        """
        self.metrics = metrics_registry
    
    def record_request(self, endpoint: str, method: str, 
                      duration_ms: float, status: int) -> None:
        """
        Record an API request.
        
        Args:
            endpoint: API endpoint
            method: HTTP method
            duration_ms: Request duration in milliseconds
            status: HTTP status code
        """
        # Determine status category
        status_category = f"{status // 100}xx"
        
        # Record request count
        self.metrics.increment_counter(
            "api_requests_total",
            label_values={
                "endpoint": endpoint,
                "method": method,
                "status": status_category
            }
        )
        
        # Record request duration
        self.metrics.observe_histogram(
            "api_request_duration",
            duration_ms,
            label_values={
                "endpoint": endpoint,
                "method": method
            }
        )


class MigrationMonitor:
    """Monitor for migration metrics."""
    
    def __init__(self, metrics_registry: MetricsRegistry):
        """
        Initialize the migration monitor.
        
        Args:
            metrics_registry: Metrics registry to record to
        """
        self.metrics = metrics_registry
    
    def record_migration(self, source_backend: str, target_backend: str,
                        status: str, bytes_transferred: Optional[float] = None) -> None:
        """
        Record a migration operation.
        
        Args:
            source_backend: Source backend name
            target_backend: Target backend name
            status: Migration status
            bytes_transferred: Optional bytes transferred
        """
        # Record migration count
        self.metrics.increment_counter(
            "migration_operations_total",
            label_values={
                "source_backend": source_backend,
                "target_backend": target_backend,
                "status": status
            }
        )
        
        # Record bytes transferred if available
        if bytes_transferred is not None and bytes_transferred > 0:
            self.metrics.increment_counter(
                "migration_bytes_transferred",
                increment=bytes_transferred,
                label_values={
                    "source_backend": source_backend,
                    "target_backend": target_backend
                }
            )


class StreamingMonitor:
    """Monitor for streaming metrics."""
    
    def __init__(self, metrics_registry: MetricsRegistry):
        """
        Initialize the streaming monitor.
        
        Args:
            metrics_registry: Metrics registry to record to
        """
        self.metrics = metrics_registry
    
    def record_streaming(self, direction: str, status: str,
                       bytes_transferred: Optional[float] = None) -> None:
        """
        Record a streaming operation.
        
        Args:
            direction: Streaming direction (upload/download)
            status: Operation status
            bytes_transferred: Optional bytes transferred
        """
        # Record streaming count
        self.metrics.increment_counter(
            "streaming_operations_total",
            label_values={
                "direction": direction,
                "status": status
            }
        )
        
        # Record bytes transferred if available
        if bytes_transferred is not None and bytes_transferred > 0:
            self.metrics.increment_counter(
                "streaming_bytes_transferred",
                increment=bytes_transferred,
                label_values={"direction": direction}
            )


class SearchMonitor:
    """Monitor for search metrics."""
    
    def __init__(self, metrics_registry: MetricsRegistry):
        """
        Initialize the search monitor.
        
        Args:
            metrics_registry: Metrics registry to record to
        """
        self.metrics = metrics_registry
    
    def record_search(self, index_type: str, duration_ms: float,
                    status: str = "success") -> None:
        """
        Record a search operation.
        
        Args:
            index_type: Type of search index
            duration_ms: Operation duration in milliseconds
            status: Operation status
        """
        # Record search count
        self.metrics.increment_counter(
            "search_operations_total",
            label_values={
                "index_type": index_type,
                "status": status
            }
        )
        
        # Record search duration
        self.metrics.observe_histogram(
            "search_operation_duration",
            duration_ms,
            label_values={"index_type": index_type}
        )


class MonitoringManager:
    """Manager for all monitoring components."""
    
    def __init__(self, backend_registry: Optional[Dict[str, Any]] = None):
        """
        Initialize the monitoring manager.
        
        Args:
            backend_registry: Optional dictionary mapping backend names to instances
        """
        self.backend_registry = backend_registry or {}
        
        # Create metrics registry
        self.metrics = MetricsRegistry()
        
        # Create component monitors
        self.system_monitor = SystemMonitor(self.metrics)
        self.backend_monitor = BackendMonitor(self.metrics, self.backend_registry)
        self.api_monitor = APIMonitor(self.metrics)
        self.migration_monitor = MigrationMonitor(self.metrics)
        self.streaming_monitor = StreamingMonitor(self.metrics)
        self.search_monitor = SearchMonitor(self.metrics)
    
    def start(self) -> None:
        """Start all monitoring components."""
        self.system_monitor.start()
        self.backend_monitor.start()
    
    def stop(self) -> None:
        """Stop all monitoring components."""
        self.system_monitor.stop()
        self.backend_monitor.stop()
    
    def get_metrics(self, format: str = "json") -> Union[Dict[str, Any], str]:
        """
        Get collected metrics.
        
        Args:
            format: Output format ("json" or "prometheus")
            
        Returns:
            Metrics in requested format
        """
        if format == "prometheus":
            return self.metrics.get_prometheus_metrics()
        else:
            return self.metrics.get_metrics()
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """
        Get system metrics.
        
        Returns:
            Dictionary of system metrics
        """
        return self.metrics.get_metrics(tag=MetricTag.SYSTEM)
    
    def get_backend_metrics(self) -> Dict[str, Any]:
        """
        Get backend metrics.
        
        Returns:
            Dictionary of backend metrics
        """
        return self.metrics.get_metrics(tag=MetricTag.BACKEND)
    
    def record_api_request(self, endpoint: str, method: str,
                          duration_ms: float, status: int) -> None:
        """
        Record an API request.
        
        Args:
            endpoint: API endpoint
            method: HTTP method
            duration_ms: Request duration in milliseconds
            status: HTTP status code
        """
        self.api_monitor.record_request(endpoint, method, duration_ms, status)
    
    def record_backend_operation(self, backend_name: str, operation: str,
                               duration_ms: float, success: bool = True,
                               bytes_processed: Optional[float] = None) -> None:
        """
        Record a backend operation.
        
        Args:
            backend_name: Name of the backend
            operation: Operation name
            duration_ms: Duration in milliseconds
            success: Whether the operation was successful
            bytes_processed: Optional bytes processed
        """
        self.backend_monitor.record_operation(
            backend_name, operation, duration_ms, success, bytes_processed
        )
    
    def record_migration(self, source_backend: str, target_backend: str,
                       status: str, bytes_transferred: Optional[float] = None) -> None:
        """
        Record a migration operation.
        
        Args:
            source_backend: Source backend name
            target_backend: Target backend name
            status: Migration status
            bytes_transferred: Optional bytes transferred
        """
        self.migration_monitor.record_migration(
            source_backend, target_backend, status, bytes_transferred
        )
    
    def record_streaming(self, direction: str, status: str,
                       bytes_transferred: Optional[float] = None) -> None:
        """
        Record a streaming operation.
        
        Args:
            direction: Streaming direction (upload/download)
            status: Operation status
            bytes_transferred: Optional bytes transferred
        """
        self.streaming_monitor.record_streaming(
            direction, status, bytes_transferred
        )
    
    def record_search(self, index_type: str, duration_ms: float,
                    status: str = "success") -> None:
        """
        Record a search operation.
        
        Args:
            index_type: Type of search index
            duration_ms: Operation duration in milliseconds
            status: Operation status
        """
        self.search_monitor.record_search(index_type, duration_ms, status)
    
    def get_system_info(self) -> Dict[str, Any]:
        """
        Get system information.
        
        Returns:
            Dictionary with system information
        """
        info = {
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "cpu_count": psutil.cpu_count(),
            "memory_total": psutil.virtual_memory().total,
            "disk_total": {path: psutil.disk_usage(path).total for path in ["/", "/home"]},
            "uptime": int(time.time() - psutil.boot_time())
        }
        
        # Add network interfaces
        interfaces = {}
        for name, stats in psutil.net_if_stats().items():
            interfaces[name] = {
                "up": stats.isup,
                "speed": stats.speed,
                "mtu": stats.mtu
            }
        
        info["network_interfaces"] = interfaces
        
        return info