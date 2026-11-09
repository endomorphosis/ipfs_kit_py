#!/usr/bin/env python3
"""
Enhanced Metrics & Monitoring Module

This module implements a comprehensive metrics collection, monitoring,
and reporting system for the MCP server, featuring:

- Prometheus integration
- Custom metrics tracking
- Runtime performance monitoring
- Backend-specific metrics
- Health check endpoints

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements.
"""

import os
import time
import json
import logging
import threading
import datetime
from enum import Enum
from typing import Dict, List, Optional, Union, Any, Callable, Set
from collections import defaultdict, deque

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mcp_metrics")

class MetricType(Enum):
    """Types of metrics supported by the monitoring system."""
    COUNTER = "counter"          # Monotonically increasing counter
    GAUGE = "gauge"              # Value that can go up and down
    HISTOGRAM = "histogram"      # Distribution of values
    SUMMARY = "summary"          # Similar to histogram but with quantiles
    TIMER = "timer"              # Special case for timing operations

class MetricLabel(Enum):
    """Common metric labels used across the system."""
    BACKEND = "backend"          # Storage backend name (ipfs, filecoin, etc.)
    OPERATION = "operation"      # Operation type (read, write, etc.)
    STATUS = "status"            # Operation status (success, failure)
    ENDPOINT = "endpoint"        # API endpoint
    METHOD = "method"            # HTTP method
    CONTENT_TYPE = "content_type" # Content type
    ERROR_TYPE = "error_type"    # Type of error

class MCPMetrics:
    """
    Enhanced metrics and monitoring system for the MCP server.
    
    Features:
    - Prometheus-compatible metrics collection
    - Custom dimensional metrics
    - Runtime performance monitoring
    - Health check infrastructure
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the metrics and monitoring system.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        
        # Default configuration
        self.collection_interval = self.config.get("collection_interval", 10)  # seconds
        self.retain_metrics = self.config.get("retain_metrics", True)
        self.metric_retention_days = self.config.get("metric_retention_days", 7)
        self.enable_prometheus = self.config.get("enable_prometheus", True)
        
        # Initialize metrics storage
        self.metrics = {}
        self.metrics_metadata = {}
        self.metrics_history = defaultdict(lambda: deque(maxlen=8640))  # 24 hours at 10s intervals
        
        # For time series metrics
        self.time_series = defaultdict(lambda: defaultdict(list))
        
        # Health status
        self.health_checks = {}
        self.health_status = {
            "status": "starting",
            "last_check": time.time(),
            "checks": {},
            "details": {}
        }
        
        # Internal state for rate calculation
        self._last_collection_time = time.time()
        self._last_operation_counts = {}
        
        # Collection thread
        self._stop_collection = threading.Event()
        self._collection_thread = None
        
        # Performance tracking
        self.start_times = {}
        
        # Initialize built-in metrics
        self._init_metrics()
        
        logger.info("MCP Metrics initialized")
        
        # Start collection if configured
        if self.config.get("auto_start_collection", True):
            self.start_collection()
    
    def _init_metrics(self):
        """Initialize built-in metrics."""
        # Server metrics
        self.register_metric(
            name="mcp_server_uptime",
            metric_type=MetricType.GAUGE,
            description="MCP server uptime in seconds",
            labels=[]
        )
        
        self.register_metric(
            name="mcp_server_memory_usage",
            metric_type=MetricType.GAUGE,
            description="MCP server memory usage in bytes",
            labels=[]
        )
        
        self.register_metric(
            name="mcp_server_cpu_usage",
            metric_type=MetricType.GAUGE,
            description="MCP server CPU usage percentage",
            labels=[]
        )
        
        # API metrics
        self.register_metric(
            name="mcp_api_requests_total",
            metric_type=MetricType.COUNTER,
            description="Total number of API requests",
            labels=[MetricLabel.ENDPOINT, MetricLabel.METHOD, MetricLabel.STATUS]
        )
        
        self.register_metric(
            name="mcp_api_request_duration_seconds",
            metric_type=MetricType.HISTOGRAM,
            description="API request duration in seconds",
            labels=[MetricLabel.ENDPOINT, MetricLabel.METHOD],
            buckets=[0.01, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
        )
        
        # Backend metrics
        self.register_metric(
            name="mcp_backend_operations_total",
            metric_type=MetricType.COUNTER,
            description="Total number of backend operations",
            labels=[MetricLabel.BACKEND, MetricLabel.OPERATION, MetricLabel.STATUS]
        )
        
        self.register_metric(
            name="mcp_backend_operation_duration_seconds",
            metric_type=MetricType.HISTOGRAM,
            description="Backend operation duration in seconds",
            labels=[MetricLabel.BACKEND, MetricLabel.OPERATION],
            buckets=[0.01, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
        )
        
        self.register_metric(
            name="mcp_backend_data_transferred_bytes",
            metric_type=MetricType.COUNTER,
            description="Total data transferred in bytes",
            labels=[MetricLabel.BACKEND, MetricLabel.OPERATION]
        )
        
        # Error metrics
        self.register_metric(
            name="mcp_errors_total",
            metric_type=MetricType.COUNTER,
            description="Total number of errors",
            labels=[MetricLabel.ERROR_TYPE]
        )
        
        # Health metrics
        self.register_metric(
            name="mcp_health_check_status",
            metric_type=MetricType.GAUGE,
            description="Health check status (1 = healthy, 0 = unhealthy)",
            labels=["check_name"]
        )
    
    def register_metric(self, name: str, metric_type: MetricType, description: str, 
                       labels: List[Union[str, MetricLabel]], buckets: Optional[List[float]] = None) -> None:
        """
        Register a new metric.
        
        Args:
            name: Metric name
            metric_type: Type of metric
            description: Description of what the metric measures
            labels: List of label keys for the metric
            buckets: Optional list of bucket boundaries for histograms
        """
        # Convert MetricLabel enums to strings
        str_labels = [label.value if isinstance(label, MetricLabel) else label for label in labels]
        
        if name in self.metrics:
            logger.warning(f"Metric {name} already registered")
            return
        
        # Initialize metric store based on type
        if metric_type == MetricType.COUNTER:
            self.metrics[name] = defaultdict(float)
        elif metric_type == MetricType.GAUGE:
            self.metrics[name] = defaultdict(float)
        elif metric_type == MetricType.HISTOGRAM:
            buckets = buckets or [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
            self.metrics[name] = {
                "buckets": sorted(buckets),
                "values": defaultdict(list),
                "counts": defaultdict(lambda: [0] * (len(buckets) + 1)),
                "sums": defaultdict(float)
            }
        elif metric_type == MetricType.SUMMARY:
            self.metrics[name] = {
                "values": defaultdict(list),
                "count": defaultdict(int),
                "sum": defaultdict(float)
            }
        elif metric_type == MetricType.TIMER:
            self.metrics[name] = {
                "values": defaultdict(list),
                "count": defaultdict(int),
                "sum": defaultdict(float)
            }
        
        # Store metadata
        self.metrics_metadata[name] = {
            "type": metric_type,
            "description": description,
            "labels": str_labels,
            "buckets": buckets
        }
        
        logger.debug(f"Registered metric {name} of type {metric_type.value}")
    
    def inc_counter(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        """
        Increment a counter metric.
        
        Args:
            name: Metric name
            value: Value to increment by
            labels: Dictionary of label key-values
        """
        if name not in self.metrics:
            logger.warning(f"Metric {name} not registered")
            return
        
        if self.metrics_metadata[name]["type"] != MetricType.COUNTER:
            logger.warning(f"Metric {name} is not a counter")
            return
        
        labels_key = self._get_labels_key(labels or {})
        self.metrics[name][labels_key] += value
        
        # Record timestamp and value for time series
        ts = time.time()
        self.time_series[name][labels_key].append((ts, self.metrics[name][labels_key]))
    
    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """
        Set a gauge metric value.
        
        Args:
            name: Metric name
            value: Value to set
            labels: Dictionary of label key-values
        """
        if name not in self.metrics:
            logger.warning(f"Metric {name} not registered")
            return
        
        if self.metrics_metadata[name]["type"] != MetricType.GAUGE:
            logger.warning(f"Metric {name} is not a gauge")
            return
        
        labels_key = self._get_labels_key(labels or {})
        prev_value = self.metrics[name][labels_key]
        self.metrics[name][labels_key] = value
        
        # Only record if value changed
        if value != prev_value:
            ts = time.time()
            self.time_series[name][labels_key].append((ts, value))
    
    def observe_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """
        Observe a value for a histogram metric.
        
        Args:
            name: Metric name
            value: Value to observe
            labels: Dictionary of label key-values
        """
        if name not in self.metrics:
            logger.warning(f"Metric {name} not registered")
            return
        
        if self.metrics_metadata[name]["type"] != MetricType.HISTOGRAM:
            logger.warning(f"Metric {name} is not a histogram")
            return
        
        labels_key = self._get_labels_key(labels or {})
        
        # Add to raw values list (for optional statistics)
        if self.retain_metrics:
            self.metrics[name]["values"][labels_key].append(value)
        
        # Update histogram buckets
        buckets = self.metrics[name]["buckets"]
        counts = self.metrics[name]["counts"][labels_key]
        
        # Update sum
        self.metrics[name]["sums"][labels_key] += value
        
        # Update bucket counts
        for i, bucket in enumerate(buckets):
            if value <= bucket:
                counts[i] += 1
        
        # +Inf bucket always incremented
        counts[-1] += 1
        
        # Record timestamp and value for time series
        ts = time.time()
        self.time_series[name][labels_key].append((ts, value))
    
    def observe_summary(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """
        Observe a value for a summary metric.
        
        Args:
            name: Metric name
            value: Value to observe
            labels: Dictionary of label key-values
        """
        if name not in self.metrics:
            logger.warning(f"Metric {name} not registered")
            return
        
        if self.metrics_metadata[name]["type"] != MetricType.SUMMARY:
            logger.warning(f"Metric {name} is not a summary")
            return
        
        labels_key = self._get_labels_key(labels or {})
        
        # Add to values list
        if self.retain_metrics:
            self.metrics[name]["values"][labels_key].append(value)
        
        # Update count and sum
        self.metrics[name]["count"][labels_key] += 1
        self.metrics[name]["sum"][labels_key] += value
        
        # Record timestamp and value for time series
        ts = time.time()
        self.time_series[name][labels_key].append((ts, value))
    
    def start_timer(self, name: str, labels: Optional[Dict[str, str]] = None) -> str:
        """
        Start a timer for measuring operation duration.
        
        Args:
            name: Metric name
            labels: Dictionary of label key-values
            
        Returns:
            Timer ID for stopping the timer
        """
        timer_id = f"{name}:{self._get_labels_key(labels or {})}:{time.time()}"
        self.start_times[timer_id] = time.time()
        return timer_id
    
    def stop_timer(self, timer_id: str) -> float:
        """
        Stop a timer and record the duration.
        
        Args:
            timer_id: Timer ID from start_timer
            
        Returns:
            Elapsed time in seconds
        """
        if timer_id not in self.start_times:
            logger.warning(f"Timer {timer_id} not found")
            return 0.0
        
        start_time = self.start_times.pop(timer_id)
        elapsed = time.time() - start_time
        
        # Extract metric name and labels from timer ID
        parts = timer_id.split(":")
        if len(parts) < 2:
            logger.warning(f"Invalid timer ID format: {timer_id}")
            return elapsed
        
        name = parts[0]
        labels_key = parts[1]
        
        # Support both direct histograms and special timer type
        if name in self.metrics:
            if self.metrics_metadata[name]["type"] == MetricType.HISTOGRAM:
                # Parse labels from key
                try:
                    labels_dict = json.loads(labels_key) if labels_key != "" else {}
                except:
                    labels_dict = {}
                
                self.observe_histogram(name, elapsed, labels_dict)
            elif self.metrics_metadata[name]["type"] == MetricType.TIMER:
                try:
                    labels_dict = json.loads(labels_key) if labels_key != "" else {}
                except:
                    labels_dict = {}
                
                # Record in the timer metric
                if self.retain_metrics:
                    self.metrics[name]["values"][labels_key].append(elapsed)
                
                self.metrics[name]["count"][labels_key] += 1
                self.metrics[name]["sum"][labels_key] += elapsed
                
                # Record timestamp and value for time series
                ts = time.time()
                self.time_series[name][labels_key].append((ts, elapsed))
        
        return elapsed
    
    def _get_labels_key(self, labels: Dict[str, str]) -> str:
        """
        Get a string key for labels dictionary.
        
        Args:
            labels: Dictionary of label key-values
            
        Returns:
            String key for the labels
        """
        if not labels:
            return ""
        
        # Sort for consistent ordering
        return json.dumps(labels, sort_keys=True)
    
    def _parse_labels_key(self, labels_key: str) -> Dict[str, str]:
        """
        Parse a labels key back into a dictionary.
        
        Args:
            labels_key: String key for labels
            
        Returns:
            Dictionary of label key-values
        """
        if not labels_key:
            return {}
        
        try:
            return json.loads(labels_key)
        except:
            return {}
    
    def get_metric(self, name: str) -> Dict[str, Any]:
        """
        Get a metric by name.
        
        Args:
            name: Metric name
            
        Returns:
            Dictionary with metric data and metadata
        """
        if name not in self.metrics:
            return {"error": f"Metric {name} not found"}
        
        return {
            "name": name,
            "type": self.metrics_metadata[name]["type"].value,
            "description": self.metrics_metadata[name]["description"],
            "labels": self.metrics_metadata[name]["labels"],
            "data": self._get_metric_data(name)
        }
    
    def _get_metric_data(self, name: str) -> Dict[str, Any]:
        """
        Get processed metric data for a specific metric.
        
        Args:
            name: Metric name
            
        Returns:
            Dictionary with processed metric data
        """
        metric_type = self.metrics_metadata[name]["type"]
        
        if metric_type == MetricType.COUNTER or metric_type == MetricType.GAUGE:
            return {labels_key: value for labels_key, value in self.metrics[name].items()}
        
        elif metric_type == MetricType.HISTOGRAM:
            result = {}
            for labels_key, counts in self.metrics[name]["counts"].items():
                buckets = self.metrics_metadata[name]["buckets"]
                
                bucket_data = []
                for i, bucket in enumerate(buckets):
                    bucket_data.append({
                        "le": bucket,
                        "count": counts[i]
                    })
                
                # Add +Inf bucket
                bucket_data.append({
                    "le": "+Inf",
                    "count": counts[-1]
                })
                
                # Add sum
                sum_value = self.metrics[name]["sums"][labels_key]
                
                # Calculate mean if we have values
                values = self.metrics[name]["values"].get(labels_key, [])
                mean = sum_value / len(values) if values else 0
                
                result[labels_key] = {
                    "buckets": bucket_data,
                    "count": counts[-1],
                    "sum": sum_value,
                    "mean": mean
                }
            
            return result
        
        elif metric_type == MetricType.SUMMARY or metric_type == MetricType.TIMER:
            result = {}
            for labels_key in self.metrics[name]["count"].keys():
                count = self.metrics[name]["count"][labels_key]
                sum_value = self.metrics[name]["sum"][labels_key]
                values = self.metrics[name]["values"].get(labels_key, [])
                
                # Calculate statistics
                mean = sum_value / count if count > 0 else 0
                
                # Calculate quantiles if we have values
                quantiles = {}
                if values:
                    sorted_values = sorted(values)
                    
                    for q in [0.5, 0.9, 0.95, 0.99]:
                        idx = int(q * len(sorted_values))
                        if idx >= len(sorted_values):
                            idx = len(sorted_values) - 1
                        quantiles[str(q)] = sorted_values[idx]
                
                result[labels_key] = {
                    "count": count,
                    "sum": sum_value,
                    "mean": mean,
                    "quantiles": quantiles
                }
            
            return result
        
        return {}
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """
        Get all metrics.
        
        Returns:
            Dictionary with all metric data
        """
        return {
            name: self.get_metric(name)
            for name in self.metrics
        }
    
    def get_prometheus_metrics(self) -> str:
        """
        Get metrics in Prometheus exposition format.
        
        Returns:
            String with Prometheus-formatted metrics
        """
        if not self.enable_prometheus:
            return "# Prometheus metrics disabled"
        
        lines = []
        
        for name, metadata in self.metrics_metadata.items():
            metric_type = metadata["type"]
            description = metadata["description"]
            
            # Add TYPE and HELP metadata
            prometheus_type = metric_type.value
            if metric_type == MetricType.TIMER:
                prometheus_type = "summary"  # Map custom timer type to Prometheus summary
            
            lines.append(f"# HELP {name} {description}")
            lines.append(f"# TYPE {name} {prometheus_type}")
            
            if metric_type == MetricType.COUNTER or metric_type == MetricType.GAUGE:
                for labels_key, value in self.metrics[name].items():
                    labels_str = self._labels_key_to_prometheus(labels_key)
                    lines.append(f"{name}{labels_str} {value}")
            
            elif metric_type == MetricType.HISTOGRAM:
                for labels_key, counts in self.metrics[name]["counts"].items():
                    base_labels = self._parse_labels_key(labels_key)
                    buckets = self.metrics_metadata[name]["buckets"]
                    
                    # Add bucket entries
                    for i, bucket in enumerate(buckets):
                        labels = base_labels.copy()
                        labels["le"] = str(bucket)
                        labels_str = self._dict_to_prometheus_labels(labels)
                        lines.append(f"{name}_bucket{labels_str} {counts[i]}")
                    
                    # Add +Inf bucket
                    labels = base_labels.copy()
                    labels["le"] = "+Inf"
                    labels_str = self._dict_to_prometheus_labels(labels)
                    lines.append(f"{name}_bucket{labels_str} {counts[-1]}")
                    
                    # Add sum
                    labels_str = self._labels_key_to_prometheus(labels_key)
                    sum_value = self.metrics[name]["sums"][labels_key]
                    lines.append(f"{name}_sum{labels_str} {sum_value}")
                    
                    # Add count
                    lines.append(f"{name}_count{labels_str} {counts[-1]}")
            
            elif metric_type == MetricType.SUMMARY or metric_type == MetricType.TIMER:
                for labels_key in self.metrics[name]["count"].keys():
                    base_labels = self._parse_labels_key(labels_key)
                    count = self.metrics[name]["count"][labels_key]
                    sum_value = self.metrics[name]["sum"][labels_key]
                    values = self.metrics[name]["values"].get(labels_key, [])
                    
                    # Add quantiles if we have values
                    if values:
                        sorted_values = sorted(values)
                        
                        for q in [0.5, 0.9, 0.95, 0.99]:
                            labels = base_labels.copy()
                            labels["quantile"] = str(q)
                            labels_str = self._dict_to_prometheus_labels(labels)
                            
                            idx = int(q * len(sorted_values))
                            if idx >= len(sorted_values):
                                idx = len(sorted_values) - 1
                            value = sorted_values[idx]
                            
                            lines.append(f"{name}{labels_str} {value}")
                    
                    # Add sum
                    labels_str = self._labels_key_to_prometheus(labels_key)
                    lines.append(f"{name}_sum{labels_str} {sum_value}")
                    
                    # Add count
                    lines.append(f"{name}_count{labels_str} {count}")
        
        return "\n".join(lines)
    
    def _labels_key_to_prometheus(self, labels_key: str) -> str:
        """
        Convert a labels key to Prometheus format.
        
        Args:
            labels_key: String key for labels
            
        Returns:
            Prometheus-formatted labels string
        """
        if not labels_key:
            return ""
        
        try:
            labels = json.loads(labels_key)
            return self._dict_to_prometheus_labels(labels)
        except:
            return ""
    
    def _dict_to_prometheus_labels(self, labels: Dict[str, str]) -> str:
        """
        Convert a labels dictionary to Prometheus format.
        
        Args:
            labels: Dictionary of label key-values
            
        Returns:
            Prometheus-formatted labels string
        """
        if not labels:
            return ""
        
        parts = [f'{k}="{v}"' for k, v in labels.items()]
        return "{" + ",".join(parts) + "}"
    
    def collect_system_metrics(self) -> None:
        """Collect system metrics like CPU, memory, and uptime."""
        try:
            import psutil
            import os
            
            # Uptime (get process start time)
            process = psutil.Process(os.getpid())
            uptime = time.time() - process.create_time()
            self.set_gauge("mcp_server_uptime", uptime)
            
            # Memory usage
            memory_info = process.memory_info()
            self.set_gauge("mcp_server_memory_usage", memory_info.rss)
            
            # CPU usage
            cpu_percent = process.cpu_percent(interval=None)
            self.set_gauge("mcp_server_cpu_usage", cpu_percent)
            
        except ImportError:
            logger.warning("psutil not installed, system metrics collection disabled")
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
    
    def start_collection(self) -> None:
        """Start background metrics collection thread."""
        if self._collection_thread and self._collection_thread.is_alive():
            logger.warning("Metrics collection already running")
            return
        
        self._stop_collection.clear()
        self._collection_thread = threading.Thread(target=self._collection_loop, daemon=True)
        self._collection_thread.start()
        logger.info("Started metrics collection thread")
    
    def stop_collection(self) -> None:
        """Stop background metrics collection thread."""
        self._stop_collection.set()
        if self._collection_thread:
            self._collection_thread.join(timeout=5)
            logger.info("Stopped metrics collection thread")
    
    def _collection_loop(self) -> None:
        """Background metrics collection loop."""
        while not self._stop_collection.is_set():
            try:
                # Collect system metrics
                self.collect_system_metrics()
                
                # Update health status
                self._update_health_status()
                
                # Prune old time series data
                self._prune_time_series()
                
                # Store periodic snapshots
                self._store_metrics_snapshot()
                
            except Exception as e:
                logger.error(f"Error in metrics collection loop: {e}")
            
            # Sleep until next collection interval
            self._stop_collection.wait(self.collection_interval)
    
    def _store_metrics_snapshot(self) -> None:
        """Store a snapshot of all metrics for historical tracking."""
        if not self.retain_metrics:
            return
        
        timestamp = time.time()
        for name in self.metrics:
            data = self._get_metric_data(name)
            self.metrics_history[name].append({
                "timestamp": timestamp,
                "data": data
            })
    
    def _prune_time_series(self) -> None:
        """Prune old time series data."""
        if not self.retain_metrics or self.metric_retention_days <= 0:
            return
        
        cutoff = time.time() - (self.metric_retention_days * 24 * 60 * 60)
        
        for name in list(self.time_series.keys()):
            for labels_key in list(self.time_series[name].keys()):
                # Filter out old points
                series = self.time_series[name][labels_key]
                self.time_series[name][labels_key] = [
                    (ts, value) for ts, value in series
                    if ts >= cutoff
                ]
    
    def register_health_check(self, name: str, check_func: Callable[[], Dict[str, Any]]) -> None:
        """
        Register a health check function.
        
        Args:
            name: Health check name
            check_func: Function that returns health status
        """
        self.health_checks[name] = check_func
        logger.info(f"Registered health check: {name}")
    
    def _update_health_status(self) -> None:
        """Update the overall health status by running all health checks."""
        current_time = time.time()
        all_checks_healthy = True
        checks = {}
        details = {}
        
        for name, check_func in self.health_checks.items():
            try:
                result = check_func()
                is_healthy = result.get("healthy", False)
                
                if not is_healthy:
                    all_checks_healthy = False
                
                checks[name] = is_healthy
                details[name] = result
                
                # Update health check metrics
                self.set_gauge("mcp_health_check_status", 
                              1.0 if is_healthy else 0.0, 
                              {"check_name": name})
                
            except Exception as e:
                logger.error(f"Error in health check {name}: {e}")
                all_checks_healthy = False
                checks[name] = False
                details[name] = {"healthy": False, "error": str(e)}
                
                # Update health check metrics
                self.set_gauge("mcp_health_check_status", 0.0, {"check_name": name})
        
        self.health_status = {
            "status": "healthy" if all_checks_healthy else "unhealthy",
            "last_check": current_time,
            "checks": checks,
            "details": details
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get the current health status.
        
        Returns:
            Dictionary with health status information
        """
        return self.health_status
    
    def track_api_request(self, endpoint: str, method: str, status_code: int, 
                         duration: float, content_type: Optional[str] = None) -> None:
        """
        Track an API request for metrics.
        
        Args:
            endpoint: API endpoint path
            method: HTTP method
            status_code: Response status code
            duration: Request duration in seconds
            content_type: Optional content type
        """
        # Categorize status
        status = "success" if 200 <= status_code < 400 else "error"
        
        # Track request count
        self.inc_counter(
            "mcp_api_requests_total", 
            1.0, 
            {
                MetricLabel.ENDPOINT.value: endpoint,
                MetricLabel.METHOD.value: method,
                MetricLabel.STATUS.value: status
            }
        )
        
        # Track request duration
        self.observe_histogram(
            "mcp_api_request_duration_seconds",
            duration,
            {
                MetricLabel.ENDPOINT.value: endpoint,
                MetricLabel.METHOD.value: method
            }
        )
        
        # Track errors if applicable
        if status == "error":
            error_type = f"http_{status_code}"
            self.inc_counter(
                "mcp_errors_total",
                1.0,
                {MetricLabel.ERROR_TYPE.value: error_type}
            )
    
    def track_backend_operation(self, backend: str, operation: str, success: bool,
                              duration: float, data_size: Optional[int] = None,
                              error_type: Optional[str] = None) -> None:
        """
        Track a backend storage operation for metrics.
        
        Args:
            backend: Storage backend name
            operation: Operation type (read, write, etc.)
            success: Whether the operation succeeded
            duration: Operation duration in seconds
            data_size: Optional size of data transferred in bytes
            error_type: Optional error type if operation failed
        """
        # Track operation count
        status = "success" if success else "error"
        self.inc_counter(
            "mcp_backend_operations_total", 
            1.0, 
            {
                MetricLabel.BACKEND.value: backend,
                MetricLabel.OPERATION.value: operation,
                MetricLabel.STATUS.value: status
            }
        )
        
        # Track operation duration
        self.observe_histogram(
            "mcp_backend_operation_duration_seconds",
            duration,
            {
                MetricLabel.BACKEND.value: backend,
                MetricLabel.OPERATION.value: operation
            }
        )
        
        # Track data size if provided
        if data_size is not None:
            self.inc_counter(
                "mcp_backend_data_transferred_bytes",
                float(data_size),
                {
                    MetricLabel.BACKEND.value: backend,
                    MetricLabel.OPERATION.value: operation
                }
            )
        
        # Track errors if applicable
        if not success and error_type:
            self.inc_counter(
                "mcp_errors_total",
                1.0,
                {MetricLabel.ERROR_TYPE.value: error_type}
            )

# Singleton instance
_instance = None

def get_instance(config=None):
    """Get or create a singleton instance of the metrics system."""
    global _instance
    if _instance is None:
        _instance = MCPMetrics(config)
    return _instance