#!/usr/bin/env python3
"""
Memory-Optimized Metrics & Monitoring Module

This module implements a memory-efficient metrics collection, monitoring,
and reporting system for the MCP server, addressing the memory usage issue
highlighted in the MCP Status document.

Key optimizations:
- Circular buffer time series with configurable retention
- Reservoir sampling for histogram/summary metrics
- Efficient label storage mechanism
- Optional downsampling for high-frequency metrics
- Memory usage tracking and aggressive pruning
"""

import os
import time
import json
import logging
import threading
import datetime
import weakref
import random
import math
from enum import Enum
from typing import Dict, List, Optional, Union, Any, Callable, Set, Tuple, NamedTuple, Deque
from collections import defaultdict, deque, Counter

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

class LabelKey(NamedTuple):
    """Memory-efficient immutable label key"""
    key: Tuple[Tuple[str, str], ...]
    
    @staticmethod
    def from_dict(labels_dict: Dict[str, str]) -> 'LabelKey':
        """Create a LabelKey from a dictionary."""
        if not labels_dict:
            return LabelKey(())
        return LabelKey(tuple(sorted((k, v) for k, v in labels_dict.items())))
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to a dictionary."""
        return dict(self.key)
    
    def to_prometheus(self) -> str:
        """Convert to Prometheus label format."""
        if not self.key:
            return ""
        
        parts = [f'{k}="{v}"' for k, v in self.key]
        return "{" + ",".join(parts) + "}"

class CircularBuffer:
    """
    Memory-efficient circular buffer for time series data.
    Only stores a fixed number of points with timestamp-based eviction.
    """
    
    def __init__(self, max_points: int = 1000, max_age_seconds: Optional[int] = None):
        """
        Initialize circular buffer.
        
        Args:
            max_points: Maximum number of points to store
            max_age_seconds: Maximum age of points to keep (None for no limit)
        """
        self.max_points = max_points
        self.max_age_seconds = max_age_seconds
        self.buffer: Deque[Tuple[float, float]] = deque(maxlen=max_points)
    
    def add(self, timestamp: float, value: float) -> None:
        """Add a point to the buffer."""
        self.buffer.append((timestamp, value))
    
    def prune(self, current_time: Optional[float] = None) -> None:
        """Prune old points based on max_age."""
        if not self.max_age_seconds:
            return
            
        if current_time is None:
            current_time = time.time()
            
        cutoff = current_time - self.max_age_seconds
        
        # Only keep points newer than cutoff
        while self.buffer and self.buffer[0][0] < cutoff:
            self.buffer.popleft()
    
    def get_points(self, start_time: Optional[float] = None, end_time: Optional[float] = None) -> List[Tuple[float, float]]:
        """Get points within a time range."""
        if not self.buffer:
            return []
            
        if start_time is None and end_time is None:
            return list(self.buffer)
            
        result = []
        for ts, value in self.buffer:
            if start_time is not None and ts < start_time:
                continue
            if end_time is not None and ts > end_time:
                continue
            result.append((ts, value))
            
        return result
    
    def get_latest(self) -> Optional[Tuple[float, float]]:
        """Get the most recent point."""
        if not self.buffer:
            return None
        return self.buffer[-1]
    
    def clear(self) -> None:
        """Clear all points."""
        self.buffer.clear()
    
    def __len__(self) -> int:
        """Get the number of points."""
        return len(self.buffer)

class ReservoirSample:
    """
    Reservoir sampling implementation for maintaining a representative
    sample of values when dealing with large streams of data.
    """
    
    def __init__(self, reservoir_size: int = 1000):
        """
        Initialize reservoir sampler.
        
        Args:
            reservoir_size: Maximum number of samples to keep
        """
        self.reservoir_size = reservoir_size
        self.reservoir: List[float] = []
        self.count = 0
        self.sum = 0.0
        self.min = float('inf')
        self.max = float('-inf')
    
    def add(self, value: float) -> None:
        """
        Add a value to the reservoir.
        
        Uses Algorithm R for reservoir sampling to maintain a statistically
        representative sample even with very large streams.
        """
        self.count += 1
        self.sum += value
        
        # Update min/max
        if value < self.min:
            self.min = value
        if value > self.max:
            self.max = value
        
        # If we haven't filled the reservoir yet, just append
        if len(self.reservoir) < self.reservoir_size:
            self.reservoir.append(value)
            return
            
        # Randomly replace an element with decreasing probability
        j = random.randint(0, self.count - 1)
        if j < self.reservoir_size:
            self.reservoir[j] = value
    
    def clear(self) -> None:
        """Clear all samples."""
        self.reservoir.clear()
        self.count = 0
        self.sum = 0.0
        self.min = float('inf') 
        self.max = float('-inf')
    
    def get_samples(self) -> List[float]:
        """Get all samples in the reservoir."""
        return self.reservoir.copy()
    
    def get_sorted_samples(self) -> List[float]:
        """Get sorted samples for quantile calculation."""
        return sorted(self.reservoir)
    
    def get_quantile(self, q: float) -> Optional[float]:
        """
        Calculate quantile from the reservoir.
        
        Args:
            q: Quantile between 0 and 1
            
        Returns:
            Estimated quantile or None if no samples
        """
        if not self.reservoir:
            return None
            
        sorted_samples = self.get_sorted_samples()
        idx = int(q * len(sorted_samples))
        if idx >= len(sorted_samples):
            idx = len(sorted_samples) - 1
        return sorted_samples[idx]
    
    def get_mean(self) -> float:
        """Calculate mean of all observed values."""
        if self.count == 0:
            return 0.0
        return self.sum / self.count
    
    def get_statistics(self) -> Dict[str, float]:
        """Get basic statistics from the reservoir."""
        if self.count == 0:
            return {
                "count": 0,
                "sum": 0.0,
                "mean": 0.0,
                "min": 0.0,
                "max": 0.0
            }
            
        return {
            "count": self.count,
            "sum": self.sum,
            "mean": self.sum / self.count,
            "min": self.min,
            "max": self.max
        }
    
    def __len__(self) -> int:
        """Get the number of observed values (not just in reservoir)."""
        return self.count

class MCPMetricsOptimized:
    """
    Memory-optimized metrics and monitoring system for the MCP server.
    
    Features:
    - Efficient memory usage for high-volume metrics
    - Prometheus-compatible metrics collection
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
        self.time_series_points = self.config.get("time_series_points", 600)   # 1h at 10s intervals
        self.time_series_max_age = self.config.get("time_series_max_age", 3600)  # 1h
        self.reservoir_size = self.config.get("reservoir_size", 1000)  # Max samples for histograms
        self.enable_prometheus = self.config.get("enable_prometheus", True)
        self.retention_policy = self.config.get("retention_policy", "aggressive")  # Options: conservative, moderate, aggressive
        self.enable_memory_tracking = self.config.get("enable_memory_tracking", True)
        
        # Memory optimization settings based on retention policy
        if self.retention_policy == "conservative":
            # Keep more data in memory
            self.store_raw_samples = True
            self.snapshot_interval = 60  # Take snapshots every minute
            self.snapshot_retention = 60  # Keep 1 hour of snapshots
        elif self.retention_policy == "moderate":
            # Balance between memory usage and data retention
            self.store_raw_samples = True
            self.snapshot_interval = 300  # Take snapshots every 5 minutes
            self.snapshot_retention = 12  # Keep 1 hour of snapshots
        else:  # aggressive
            # Minimize memory usage
            self.store_raw_samples = False
            self.snapshot_interval = 600  # Take snapshots every 10 minutes
            self.snapshot_retention = 6  # Keep 1 hour of snapshots
        
        # Initialize metrics storage using memory-efficient structures
        self.counters = defaultdict(lambda: defaultdict(float))
        self.gauges = defaultdict(lambda: defaultdict(float))
        self.histograms = {}
        self.summaries = {}
        self.timers = {}
        
        # Time series data
        self.time_series = defaultdict(lambda: defaultdict(lambda: CircularBuffer(
            max_points=self.time_series_points,
            max_age_seconds=self.time_series_max_age
        )))
        
        # Metrics metadata
        self.metrics_metadata = {}
        
        # Limited snapshots for history
        self.metrics_snapshots = defaultdict(lambda: deque(maxlen=self.snapshot_retention))
        self.last_snapshot_time = 0
        
        # Health status
        self.health_checks = {}
        self.health_status = {
            "status": "starting",
            "last_check": time.time(),
            "checks": {},
            "details": {}
        }
        
        # Performance tracking
        self.start_times = {}
        
        # For memory usage tracking
        self.memory_usage_metrics = {
            "total_metrics": 0,
            "total_time_series_points": 0,
            "total_label_combinations": 0,
            "total_samples": 0,
            "last_check": 0
        }
        
        # Collection thread
        self._stop_collection = threading.Event()
        self._collection_thread = None
        
        # Initialize built-in metrics
        self._init_metrics()
        
        logger.info("MCP Metrics (Memory-Optimized) initialized")
        
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
        
        # Metrics system metrics (meta-metrics)
        self.register_metric(
            name="mcp_metrics_memory_usage",
            metric_type=MetricType.GAUGE,
            description="Memory used by metrics system",
            labels=["component"]
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
        
        if name in self.metrics_metadata:
            logger.warning(f"Metric {name} already registered")
            return
        
        # Initialize metric store based on type
        if metric_type == MetricType.HISTOGRAM:
            buckets = buckets or [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
            self.histograms[name] = {
                "buckets": sorted(buckets),
                "samples": defaultdict(lambda: ReservoirSample(self.reservoir_size)),
                "counts": defaultdict(lambda: [0] * (len(buckets) + 1)),
                "sums": defaultdict(float)
            }
        elif metric_type == MetricType.SUMMARY:
            self.summaries[name] = {
                "samples": defaultdict(lambda: ReservoirSample(self.reservoir_size)),
                "count": defaultdict(int),
                "sum": defaultdict(float)
            }
        elif metric_type == MetricType.TIMER:
            self.timers[name] = {
                "samples": defaultdict(lambda: ReservoirSample(self.reservoir_size)),
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
        if name not in self.metrics_metadata:
            logger.warning(f"Metric {name} not registered")
            return
        
        if self.metrics_metadata[name]["type"] != MetricType.COUNTER:
            logger.warning(f"Metric {name} is not a counter")
            return
        
        label_key = LabelKey.from_dict(labels or {})
        self.counters[name][label_key] += value
        
        # Record timestamp and value for time series
        ts = time.time()
        self.time_series[name][label_key].add(ts, self.counters[name][label_key])
    
    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """
        Set a gauge metric value.
        
        Args:
            name: Metric name
            value: Value to set
            labels: Dictionary of label key-values
        """
        if name not in self.metrics_metadata:
            logger.warning(f"Metric {name} not registered")
            return
        
        if self.metrics_metadata[name]["type"] != MetricType.GAUGE:
            logger.warning(f"Metric {name} is not a gauge")
            return
        
        label_key = LabelKey.from_dict(labels or {})
        prev_value = self.gauges[name][label_key]
        self.gauges[name][label_key] = value
        
        # Only record if value changed significantly (save memory)
        if abs(value - prev_value) > 0.001 or not self.time_series[name][label_key].buffer:
            ts = time.time()
            self.time_series[name][label_key].add(ts, value)
    
    def observe_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """
        Observe a value for a histogram metric.
        
        Args:
            name: Metric name
            value: Value to observe
            labels: Dictionary of label key-values
        """
        if name not in self.metrics_metadata:
            logger.warning(f"Metric {name} not registered")
            return
        
        if self.metrics_metadata[name]["type"] != MetricType.HISTOGRAM:
            logger.warning(f"Metric {name} is not a histogram")
            return
        
        label_key = LabelKey.from_dict(labels or {})
        
        # Add to reservoir sample
        self.histograms[name]["samples"][label_key].add(value)
        
        # Update histogram buckets
        buckets = self.histograms[name]["buckets"]
        counts = self.histograms[name]["counts"][label_key]
        
        # Update sum
        self.histograms[name]["sums"][label_key] += value
        
        # Update bucket counts
        for i, bucket in enumerate(buckets):
            if value <= bucket:
                counts[i] += 1
        
        # +Inf bucket always incremented
        counts[-1] += 1
        
        # Record timestamp and value for time series (downsampling to save memory)
        # Only record every Nth point for high-frequency metrics
        ts = time.time()
        should_record = True
        
        # Apply downsampling if the time series is getting large
        buffer = self.time_series[name][label_key]
        if len(buffer) > self.time_series_points / 2:
            # Check if we have recorded a point recently
            latest = buffer.get_latest()
            if latest and ts - latest[0] < 1.0:  # Less than 1 second since last point
                should_record = False
        
        if should_record:
            buffer.add(ts, value)
    
    def observe_summary(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """
        Observe a value for a summary metric.
        
        Args:
            name: Metric name
            value: Value to observe
            labels: Dictionary of label key-values
        """
        if name not in self.metrics_metadata:
            logger.warning(f"Metric {name} not registered")
            return
        
        if self.metrics_metadata[name]["type"] != MetricType.SUMMARY:
            logger.warning(f"Metric {name} is not a summary")
            return
        
        label_key = LabelKey.from_dict(labels or {})
        
        # Add to reservoir sample
        self.summaries[name]["samples"][label_key].add(value)
        
        # Update count and sum
        self.summaries[name]["count"][label_key] += 1
        self.summaries[name]["sum"][label_key] += value
        
        # Record timestamp and value for time series (with downsampling)
        ts = time.time()
        
        # Apply downsampling if the time series is getting large
        buffer = self.time_series[name][label_key]
        should_record = True
        
        if len(buffer) > self.time_series_points / 2:
            # Check if we have recorded a point recently
            latest = buffer.get_latest()
            if latest and ts - latest[0] < 1.0:  # Less than 1 second since last point
                should_record = False
        
        if should_record:
            buffer.add(ts, value)
    
    def start_timer(self, name: str, labels: Optional[Dict[str, str]] = None) -> str:
        """
        Start a timer for measuring operation duration.
        
        Args:
            name: Metric name
            labels: Dictionary of label key-values
            
        Returns:
            Timer ID for stopping the timer
        """
        label_key = LabelKey.from_dict(labels or {})
        timer_id = f"{name}:{hash(label_key)}:{time.time()}"
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
        
        # Extract metric name and label hash from timer ID
        parts = timer_id.split(":")
        if len(parts) < 2:
            logger.warning(f"Invalid timer ID format: {timer_id}")
            return elapsed
        
        name = parts[0]
        
        # Support both direct histograms and special timer type
        if name in self.metrics_metadata:
            if self.metrics_metadata[name]["type"] == MetricType.HISTOGRAM:
                # Reconstruct labels from the original timer call
                # For histograms, we'll just record it with empty labels if we can't reconstruct
                try:
                    # Try to find the original label key from hash
                    # This is a best-effort approach
                    label_hash = int(parts[1])
                    
                    # Find matching label key
                    for label_key in self.histograms[name]["samples"].keys():
                        if hash(label_key) == label_hash:
                            self.observe_histogram(name, elapsed, label_key.to_dict())
                            break
                    else:
                        # No match found, use empty labels
                        self.observe_histogram(name, elapsed, {})
                except:
                    # Fallback to empty labels
                    self.observe_histogram(name, elapsed, {})
                    
            elif self.metrics_metadata[name]["type"] == MetricType.TIMER:
                try:
                    # Try to find the original label key from hash
                    label_hash = int(parts[1])
                    
                    # Find matching label key
                    for label_key in self.timers[name]["samples"].keys():
                        if hash(label_key) == label_hash:
                            # Record in the timer metric
                            self.timers[name]["samples"][label_key].add(elapsed)
                            self.timers[name]["count"][label_key] += 1
                            self.timers[name]["sum"][label_key] += elapsed
                            
                            # Record in time series
                            ts = time.time()
                            self.time_series[name][label_key].add(ts, elapsed)
                            break
                    else:
                        # No match found, use empty labels
                        label_key = LabelKey.from_dict({})
                        self.timers[name]["samples"][label_key].add(elapsed)
                        self.timers[name]["count"][label_key] += 1
                        self.timers[name]["sum"][label_key] += elapsed
                        
                        # Record in time series
                        ts = time.time()
                        self.time_series[name][label_key].add(ts, elapsed)
                except:
                    # Fallback to empty labels
                    label_key = LabelKey.from_dict({})
                    self.timers[name]["samples"][label_key].add(elapsed)
                    self.timers[name]["count"][label_key] += 1
                    self.timers[name]["sum"][label_key] += elapsed
                    
                    # Record in time series
                    ts = time.time()
                    self.time_series[name][label_key].add(ts, elapsed)
        
        return elapsed
    
    def get_metric(self, name: str) -> Dict[str, Any]:
        """
        Get a metric by name.
        
        Args:
            name: Metric name
            
        Returns:
            Dictionary with metric data and metadata
        """
        if name not in self.metrics_metadata:
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
        
        if metric_type == MetricType.COUNTER:
            return {str(label_key.to_dict()): value 
                  for label_key, value in self.counters[name].items()}
        
        elif metric_type == MetricType.GAUGE:
            return {str(label_key.to_dict()): value 
                  for label_key, value in self.gauges[name].items()}
        
        elif metric_type == MetricType.HISTOGRAM:
            result = {}
            for label_key, counts in self.histograms[name]["counts"].items():
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
                sum_value = self.histograms[name]["sums"][label_key]
                
                # Get statistics from reservoir sample
                stats = self.histograms[name]["samples"][label_key].get_statistics()
                
                labels_dict = label_key.to_dict()
                result[str(labels_dict)] = {
                    "buckets": bucket_data,
                    "count": counts[-1],
                    "sum": sum_value,
                    "mean": stats["mean"],
                    "min": stats["min"],
                    "max": stats["max"]
                }
            
            return result
        
        elif metric_type == MetricType.SUMMARY or metric_type == MetricType.TIMER:
            result = {}
            metric_data = self.summaries[name] if metric_type == MetricType.SUMMARY else self.timers[name]
            
            for label_key in metric_data["count"].keys():
                stats = metric_data["samples"][label_key].get_statistics()
                
                # Calculate quantiles
                quantiles = {}
                sample = metric_data["samples"][label_key]
                for q in [0.5, 0.9, 0.95, 0.99]:
                    q_value = sample.get_quantile(q)
                    if q_value is not None:
                        quantiles[str(q)] = q_value
                
                labels_dict = label_key.to_dict()
                result[str(labels_dict)] = {
                    "count": stats["count"],
                    "sum": stats["sum"],
                    "mean": stats["mean"],
                    "min": stats["min"],
                    "max": stats["max"],
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
            for name in self.metrics_metadata
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
            
            if metric_type == MetricType.COUNTER:
                for label_key, value in self.counters[name].items():
                    labels_str = label_key.to_prometheus()
                    lines.append(f"{name}{labels_str} {value}")
            
            elif metric_type == MetricType.GAUGE:
                for label_key, value in self.gauges[name].items():
                    labels_str = label_key.to_prometheus()
                    lines.append(f"{name}{labels_str} {value}")
            
            elif metric_type == MetricType.HISTOGRAM:
                for label_key, counts in self.histograms[name]["counts"].items():
                    base_labels = label_key.to_dict()
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
                    labels_str = label_key.to_prometheus()
                    sum_value = self.histograms[name]["sums"][label_key]
                    lines.append(f"{name}_sum{labels_str} {sum_value}")
                    
                    # Add count
                    lines.append(f"{name}_count{labels_str} {counts[-1]}")
            
            elif metric_type == MetricType.SUMMARY or metric_type == MetricType.TIMER:
                metric_data = self.summaries[name] if metric_type == MetricType.SUMMARY else self.timers[name]
                
                for label_key in metric_data["count"].keys():
                    base_labels = label_key.to_dict()
                    stats = metric_data["samples"][label_key].get_statistics()
                    
                    # Add quantiles
                    for q in [0.5, 0.9, 0.95, 0.99]:
                        q_value = metric_data["samples"][label_key].get_quantile(q)
                        if q_value is not None:
                            labels = base_labels.copy()
                            labels["quantile"] = str(q)
                            labels_str = self._dict_to_prometheus_labels(labels)
                            lines.append(f"{name}{labels_str} {q_value}")
                    
                    # Add sum
                    labels_str = label_key.to_prometheus()
                    lines.append(f"{name}_sum{labels_str} {stats['sum']}")
                    
                    # Add count
                    lines.append(f"{name}_count{labels_str} {stats['count']}")
        
        return "\n".join(lines)
    
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
            
            # Track metrics system's own memory usage
            if self.enable_memory_tracking:
                self._collect_metrics_memory_usage()
                
        except ImportError:
            logger.warning("psutil not installed, system metrics collection disabled")
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
    
    def _collect_metrics_memory_usage(self) -> None:
        """Collect memory usage of the metrics system itself."""
        try:
            from pympler import asizeof
            
            # Count metrics
            total_metrics = len(self.metrics_metadata)
            
            # Count unique label combinations
            total_counter_labels = sum(len(v) for v in self.counters.values())
            total_gauge_labels = sum(len(v) for v in self.gauges.values())
            total_histogram_labels = sum(len(v["counts"]) for v in self.histograms.values())
            total_summary_labels = sum(len(v["count"]) for v in self.summaries.values())
            total_timer_labels = sum(len(v["count"]) for v in self.timers.values())
            
            total_labels = (total_counter_labels + total_gauge_labels + 
                           total_histogram_labels + total_summary_labels +
                           total_timer_labels)
            
            # Count time series points
            total_points = sum(
                sum(len(ts.buffer) for ts in series.values())
                for series in self.time_series.values()
            )
            
            # Count samples in reservoirs
            total_samples = 0
            for histogram in self.histograms.values():
                total_samples += sum(len(sample.reservoir) for sample in histogram["samples"].values())
            
            for summary in self.summaries.values():
                total_samples += sum(len(sample.reservoir) for sample in summary["samples"].values())
                
            for timer in self.timers.values():
                total_samples += sum(len(sample.reservoir) for sample in timer["samples"].values())
            
            # Update tracking metrics
            self.memory_usage_metrics = {
                "total_metrics": total_metrics,
                "total_time_series_points": total_points,
                "total_label_combinations": total_labels,
                "total_samples": total_samples,
                "last_check": time.time()
            }
            
            # Estimate memory usage of different components
            counters_size = asizeof.asizeof(self.counters)
            gauges_size = asizeof.asizeof(self.gauges)
            histograms_size = asizeof.asizeof(self.histograms)
            summaries_size = asizeof.asizeof(self.summaries)
            timers_size = asizeof.asizeof(self.timers)
            time_series_size = asizeof.asizeof(self.time_series)
            snapshots_size = asizeof.asizeof(self.metrics_snapshots)
            metadata_size = asizeof.asizeof(self.metrics_metadata)
            
            total_size = (counters_size + gauges_size + histograms_size + 
                         summaries_size + timers_size + time_series_size + 
                         snapshots_size + metadata_size)
            
            # Record metrics
            self.set_gauge("mcp_metrics_memory_usage", counters_size, {"component": "counters"})
            self.set_gauge("mcp_metrics_memory_usage", gauges_size, {"component": "gauges"})
            self.set_gauge("mcp_metrics_memory_usage", histograms_size, {"component": "histograms"})
            self.set_gauge("mcp_metrics_memory_usage", summaries_size, {"component": "summaries"})
            self.set_gauge("mcp_metrics_memory_usage", timers_size, {"component": "timers"})
            self.set_gauge("mcp_metrics_memory_usage", time_series_size, {"component": "time_series"})
            self.set_gauge("mcp_metrics_memory_usage", snapshots_size, {"component": "snapshots"})
            self.set_gauge("mcp_metrics_memory_usage", metadata_size, {"component": "metadata"})
            self.set_gauge("mcp_metrics_memory_usage", total_size, {"component": "total"})
            
            logger.debug(f"Metrics system memory usage: {total_size/1024/1024:.2f} MB, "
                       f"{total_metrics} metrics, {total_labels} label combinations, "
                       f"{total_points} time series points, {total_samples} samples")
            
        except ImportError:
            logger.debug("pympler not installed, detailed memory tracking disabled")
        except Exception as e:
            logger.error(f"Error tracking metrics memory usage: {e}")
    
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
                current_time = time.time()
                
                # Collect system metrics
                self.collect_system_metrics()
                
                # Update health status
                self._update_health_status()
                
                # Prune time series data to keep memory usage in check
                for name in self.time_series:
                    for label_key in list(self.time_series[name].keys()):
                        self.time_series[name][label_key].prune(current_time)
                
                # Take periodic snapshots
                if current_time - self.last_snapshot_time >= self.snapshot_interval:
                    self._store_metrics_snapshot()
                    self.last_snapshot_time = current_time
                
            except Exception as e:
                logger.error(f"Error in metrics collection loop: {e}")
            
            # Sleep until next collection interval
            self._stop_collection.wait(self.collection_interval)
    
    def _store_metrics_snapshot(self) -> None:
        """Store a snapshot of all metrics for historical tracking."""
        try:
            timestamp = time.time()
            snapshot = {
                "timestamp": timestamp,
                "counters": {},
                "gauges": {},
                "histograms": {},
                "summaries": {},
                "timers": {}
            }
            
            # Only store the current values, not the full history
            # Counters
            for name in self.counters:
                snapshot["counters"][name] = {
                    str(label_key.to_dict()): value 
                    for label_key, value in self.counters[name].items()
                }
            
            # Gauges
            for name in self.gauges:
                snapshot["gauges"][name] = {
                    str(label_key.to_dict()): value 
                    for label_key, value in self.gauges[name].items()
                }
            
            # For histograms, summaries, and timers, just store summary statistics
            for name, histogram in self.histograms.items():
                snapshot["histograms"][name] = {}
                for label_key, sample in histogram["samples"].items():
                    snapshot["histograms"][name][str(label_key.to_dict())] = sample.get_statistics()
            
            for name, summary in self.summaries.items():
                snapshot["summaries"][name] = {}
                for label_key, sample in summary["samples"].items():
                    snapshot["summaries"][name][str(label_key.to_dict())] = sample.get_statistics()
            
            for name, timer in self.timers.items():
                snapshot["timers"][name] = {}
                for label_key, sample in timer["samples"].items():
                    snapshot["timers"][name][str(label_key.to_dict())] = sample.get_statistics()
            
            # Store snapshot
            self.metrics_snapshots[timestamp] = snapshot
            
        except Exception as e:
            logger.error(f"Error storing metrics snapshot: {e}")
    
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
    
    def get_memory_usage_stats(self) -> Dict[str, Any]:
        """
        Get memory usage statistics for the metrics system.
        
        Returns:
            Dictionary with memory usage information
        """
        return self.memory_usage_metrics
    
    def flush_all_metrics(self) -> None:
        """
        Flush all metrics data to free memory.
        
        This is an aggressive action to reduce memory usage when needed.
        It keeps metadata and current values but clears historical data.
        """
        # Keep current counters and gauges but clear history
        self.time_series.clear()
        self.metrics_snapshots.clear()
        
        # For histograms, summaries, and timers, keep only the most recent values
        for name, histogram in self.histograms.items():
            # Keep counts but clear raw samples
            for sample in histogram["samples"].values():
                sample.clear()
        
        for name, summary in self.summaries.items():
            # Keep counts and sums but clear raw samples
            for sample in summary["samples"].values():
                sample.clear()
        
        for name, timer in self.timers.items():
            # Keep counts and sums but clear raw samples
            for sample in timer["samples"].values():
                sample.clear()
        
        logger.info("Flushed all metrics history to reduce memory usage")
    
    def sample_time_series(self, factor: int = 10) -> int:
        """
        Sample time series data to reduce memory usage.
        
        Args:
            factor: Keep only every Nth point
            
        Returns:
            Number of points removed
        """
        if factor <= 1:
            return 0
            
        total_removed = 0
        
        for metric_series in self.time_series.values():
            for buffer in metric_series.values():
                original_len = len(buffer)
                
                # Create a new buffer with only every Nth point
                if original_len > factor:
                    new_buffer = deque(maxlen=buffer.max_points)
                    for i, point in enumerate(buffer.buffer):
                        if i % factor == 0:
                            new_buffer.append(point)
                    
                    # Replace the buffer
                    buffer.buffer = new_buffer
                    total_removed += original_len - len(new_buffer)
        
        logger.info(f"Sampled time series data, removed {total_removed} points")
        return total_removed

# Singleton instance
_instance = None

def get_instance(config=None):
    """Get or create a singleton instance of the metrics system."""
    global _instance
    if _instance is None:
        _instance = MCPMetricsOptimized(config)
    return _instance