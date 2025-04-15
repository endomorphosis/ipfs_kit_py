"""
Bandwidth and Latency Analysis Module for Optimized Data Routing

This module analyzes and tracks bandwidth and latency metrics for storage backends:
- Real-time bandwidth measurement for backend selection
- Latency tracking and prediction
- Connection quality monitoring
- Adaptive routing based on network conditions
- Performance history and trends analysis

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).
"""

import logging
import asyncio
import time
import statistics
import heapq
import json
import math
from enum import Enum
from typing import Dict, List, Any, Optional, Union, Tuple, Deque, Set
from datetime import datetime, timedelta
from collections import deque, defaultdict
import threading
import random

# Configure logging
logger = logging.getLogger(__name__)


class NetworkMetricType(Enum):
    """Types of network metrics tracked."""
    LATENCY = "latency"                # Round-trip time in milliseconds
    DOWNLOAD_BANDWIDTH = "download"    # Download bandwidth in bytes/second
    UPLOAD_BANDWIDTH = "upload"        # Upload bandwidth in bytes/second
    ERROR_RATE = "error_rate"          # Error rate as percentage (0-100)
    JITTER = "jitter"                  # Variability in latency
    PACKET_LOSS = "packet_loss"        # Packet loss percentage (0-100)
    CONNECTION_STABILITY = "stability" # Stability score (0-1)


class NetworkQualityLevel(Enum):
    """Network quality classification."""
    EXCELLENT = "excellent"  # Exceptional performance
    GOOD = "good"            # Good performance
    FAIR = "fair"            # Acceptable performance
    POOR = "poor"            # Problematic performance
    CRITICAL = "critical"    # Highly problematic performance
    UNKNOWN = "unknown"      # Unknown quality level


class MetricSample:
    """A single sample of a network metric."""
    
    def __init__(
        self,
        metric_type: NetworkMetricType,
        value: float,
        timestamp: Optional[datetime] = None,
        backend_id: str = "",
        region: str = "",
        client_id: str = "",
        request_size_bytes: int = 0,
        request_type: str = "",
        sample_duration_ms: float = 0.0
    ):
        """
        Initialize a metric sample.
        
        Args:
            metric_type: Type of network metric
            value: Measured value
            timestamp: Timestamp of measurement
            backend_id: Backend identifier
            region: Backend region
            client_id: Client identifier
            request_size_bytes: Size of request in bytes
            request_type: Type of request
            sample_duration_ms: Duration of sampling period in milliseconds
        """
        self.metric_type = metric_type
        self.value = value
        self.timestamp = timestamp or datetime.now()
        self.backend_id = backend_id
        self.region = region
        self.client_id = client_id
        self.request_size_bytes = request_size_bytes
        self.request_type = request_type
        self.sample_duration_ms = sample_duration_ms
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "metric_type": self.metric_type.value,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "backend_id": self.backend_id,
            "region": self.region,
            "client_id": self.client_id,
            "request_size_bytes": self.request_size_bytes,
            "request_type": self.request_type,
            "sample_duration_ms": self.sample_duration_ms
        }


class MetricTimeSeries:
    """Time series of network metric samples."""
    
    def __init__(
        self,
        metric_type: NetworkMetricType,
        max_samples: int = 100,
        backend_id: str = "",
        region: str = ""
    ):
        """
        Initialize a metric time series.
        
        Args:
            metric_type: Type of network metric
            max_samples: Maximum number of samples to keep
            backend_id: Backend identifier
            region: Backend region
        """
        self.metric_type = metric_type
        self.max_samples = max_samples
        self.backend_id = backend_id
        self.region = region
        self.samples: Deque[MetricSample] = deque(maxlen=max_samples)
        
        # Statistics cache
        self._stats_cache: Dict[str, Any] = {}
        self._stats_cache_timestamp: Optional[datetime] = None
        self._stats_cache_samples_count: int = 0
    
    def add_sample(self, sample: MetricSample) -> None:
        """
        Add a sample to the time series.
        
        Args:
            sample: Metric sample
        """
        self.samples.append(sample)
        
        # Invalidate statistics cache
        self._stats_cache = {}
        self._stats_cache_timestamp = None
        self._stats_cache_samples_count = 0
    
    def get_samples(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[MetricSample]:
        """
        Get samples within a time range.
        
        Args:
            start_time: Start time (inclusive)
            end_time: End time (inclusive)
            
        Returns:
            List of samples
        """
        if start_time is None and end_time is None:
            return list(self.samples)
            
        filtered_samples = []
        
        for sample in self.samples:
            if start_time and sample.timestamp < start_time:
                continue
                
            if end_time and sample.timestamp > end_time:
                continue
                
            filtered_samples.append(sample)
            
        return filtered_samples
    
    def get_statistics(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Calculate statistics for the time series.
        
        Args:
            start_time: Start time (inclusive)
            end_time: End time (inclusive)
            use_cache: Whether to use cached statistics
            
        Returns:
            Dictionary of statistics
        """
        # Check if we can use cached statistics
        if (use_cache and 
            start_time is None and 
            end_time is None and 
            self._stats_cache and 
            self._stats_cache_timestamp and 
            self._stats_cache_samples_count == len(self.samples)):
            # Cache is valid
            return self._stats_cache
        
        # Get samples
        samples = self.get_samples(start_time, end_time)
        
        if not samples:
            return {
                "count": 0,
                "min": None,
                "max": None,
                "mean": None,
                "median": None,
                "std_dev": None,
                "percentile_90": None,
                "percentile_95": None,
                "percentile_99": None,
                "latest": None,
                "trend": None
            }
        
        # Extract values
        values = [sample.value for sample in samples]
        
        # Calculate statistics
        stats = {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "mean": statistics.mean(values) if values else None,
            "median": statistics.median(values) if values else None,
            "std_dev": statistics.stdev(values) if len(values) > 1 else 0.0,
            "latest": samples[-1].value if samples else None,
        }
        
        # Add percentiles
        if len(values) >= 10:
            stats["percentile_90"] = percentile(values, 90)
            stats["percentile_95"] = percentile(values, 95)
            stats["percentile_99"] = percentile(values, 99)
        else:
            stats["percentile_90"] = stats["max"]
            stats["percentile_95"] = stats["max"]
            stats["percentile_99"] = stats["max"]
        
        # Calculate trend
        if len(samples) >= 2:
            oldest_timestamp = samples[0].timestamp
            newest_timestamp = samples[-1].timestamp
            time_diff = (newest_timestamp - oldest_timestamp).total_seconds()
            
            if time_diff > 0:
                oldest_values = [s.value for s in samples[:max(1, len(samples)//5)]]
                newest_values = [s.value for s in samples[-(len(samples)//5):]]
                
                old_avg = statistics.mean(oldest_values)
                new_avg = statistics.mean(newest_values)
                
                if old_avg != 0:
                    stats["trend"] = (new_avg - old_avg) / old_avg
                else:
                    stats["trend"] = 0.0
            else:
                stats["trend"] = 0.0
        else:
            stats["trend"] = 0.0
        
        # Cache statistics if using full time range
        if start_time is None and end_time is None:
            self._stats_cache = stats
            self._stats_cache_timestamp = datetime.now()
            self._stats_cache_samples_count = len(self.samples)
        
        return stats
    
    def get_quality_level(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> NetworkQualityLevel:
        """
        Determine the quality level based on the metric.
        
        Args:
            start_time: Start time (inclusive)
            end_time: End time (inclusive)
            
        Returns:
            NetworkQualityLevel
        """
        stats = self.get_statistics(start_time, end_time)
        
        if stats["count"] == 0:
            return NetworkQualityLevel.UNKNOWN
        
        # Quality thresholds based on metric type
        if self.metric_type == NetworkMetricType.LATENCY:
            # Latency in milliseconds (lower is better)
            if stats["mean"] < 50:
                return NetworkQualityLevel.EXCELLENT
            elif stats["mean"] < 100:
                return NetworkQualityLevel.GOOD
            elif stats["mean"] < 200:
                return NetworkQualityLevel.FAIR
            elif stats["mean"] < 500:
                return NetworkQualityLevel.POOR
            else:
                return NetworkQualityLevel.CRITICAL
                
        elif self.metric_type == NetworkMetricType.DOWNLOAD_BANDWIDTH:
            # Bandwidth in bytes/second (higher is better)
            # 10 MB/s = excellent, 1 MB/s = good, 100 KB/s = fair, 10 KB/s = poor
            if stats["mean"] > 10 * 1024 * 1024:
                return NetworkQualityLevel.EXCELLENT
            elif stats["mean"] > 1 * 1024 * 1024:
                return NetworkQualityLevel.GOOD
            elif stats["mean"] > 100 * 1024:
                return NetworkQualityLevel.FAIR
            elif stats["mean"] > 10 * 1024:
                return NetworkQualityLevel.POOR
            else:
                return NetworkQualityLevel.CRITICAL
                
        elif self.metric_type == NetworkMetricType.UPLOAD_BANDWIDTH:
            # Bandwidth in bytes/second (higher is better)
            # Typically upload is slower, so lower thresholds
            if stats["mean"] > 5 * 1024 * 1024:
                return NetworkQualityLevel.EXCELLENT
            elif stats["mean"] > 500 * 1024:
                return NetworkQualityLevel.GOOD
            elif stats["mean"] > 50 * 1024:
                return NetworkQualityLevel.FAIR
            elif stats["mean"] > 5 * 1024:
                return NetworkQualityLevel.POOR
            else:
                return NetworkQualityLevel.CRITICAL
                
        elif self.metric_type == NetworkMetricType.ERROR_RATE:
            # Error rate as percentage (lower is better)
            if stats["mean"] < 0.1:
                return NetworkQualityLevel.EXCELLENT
            elif stats["mean"] < 1.0:
                return NetworkQualityLevel.GOOD
            elif stats["mean"] < 5.0:
                return NetworkQualityLevel.FAIR
            elif stats["mean"] < 10.0:
                return NetworkQualityLevel.POOR
            else:
                return NetworkQualityLevel.CRITICAL
                
        elif self.metric_type == NetworkMetricType.JITTER:
            # Jitter in milliseconds (lower is better)
            if stats["mean"] < 5:
                return NetworkQualityLevel.EXCELLENT
            elif stats["mean"] < 20:
                return NetworkQualityLevel.GOOD
            elif stats["mean"] < 50:
                return NetworkQualityLevel.FAIR
            elif stats["mean"] < 100:
                return NetworkQualityLevel.POOR
            else:
                return NetworkQualityLevel.CRITICAL
                
        elif self.metric_type == NetworkMetricType.PACKET_LOSS:
            # Packet loss percentage (lower is better)
            if stats["mean"] < 0.1:
                return NetworkQualityLevel.EXCELLENT
            elif stats["mean"] < 1.0:
                return NetworkQualityLevel.GOOD
            elif stats["mean"] < 3.0:
                return NetworkQualityLevel.FAIR
            elif stats["mean"] < 10.0:
                return NetworkQualityLevel.POOR
            else:
                return NetworkQualityLevel.CRITICAL
                
        elif self.metric_type == NetworkMetricType.CONNECTION_STABILITY:
            # Stability score (higher is better)
            if stats["mean"] > 0.95:
                return NetworkQualityLevel.EXCELLENT
            elif stats["mean"] > 0.9:
                return NetworkQualityLevel.GOOD
            elif stats["mean"] > 0.8:
                return NetworkQualityLevel.FAIR
            elif stats["mean"] > 0.6:
                return NetworkQualityLevel.POOR
            else:
                return NetworkQualityLevel.CRITICAL
        
        return NetworkQualityLevel.UNKNOWN
    
    def predict_future_value(self, prediction_time: datetime) -> Optional[float]:
        """
        Predict the future value at a specific time.
        
        Args:
            prediction_time: Time to predict for
            
        Returns:
            Predicted value or None if prediction is not possible
        """
        samples = list(self.samples)
        
        if len(samples) < 5:
            # Not enough samples for prediction
            return None
        
        # Extract timestamps and values
        times = [(s.timestamp - samples[0].timestamp).total_seconds() for s in samples]
        values = [s.value for s in samples]
        
        # Simple linear regression
        n = len(times)
        sum_x = sum(times)
        sum_y = sum(values)
        sum_xy = sum(x * y for x, y in zip(times, values))
        sum_xx = sum(x * x for x in times)
        
        # Calculate slope and intercept
        if n * sum_xx - sum_x * sum_x == 0:
            # No trend
            return statistics.mean(values)
        
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_xx - sum_x * sum_x)
        intercept = (sum_y - slope * sum_x) / n
        
        # Predict value at prediction_time
        prediction_seconds = (prediction_time - samples[0].timestamp).total_seconds()
        predicted_value = intercept + slope * prediction_seconds
        
        return predicted_value
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "metric_type": self.metric_type.value,
            "backend_id": self.backend_id,
            "region": self.region,
            "samples_count": len(self.samples),
            "statistics": self.get_statistics(),
            "quality_level": self.get_quality_level().value
        }


class BackendNetworkMetrics:
    """Network metrics for a specific backend."""
    
    def __init__(self, backend_id: str, region: str = ""):
        """
        Initialize backend network metrics.
        
        Args:
            backend_id: Backend identifier
            region: Backend region
        """
        self.backend_id = backend_id
        self.region = region
        self.metrics: Dict[NetworkMetricType, MetricTimeSeries] = {}
        
        # Initialize metrics
        for metric_type in NetworkMetricType:
            self.metrics[metric_type] = MetricTimeSeries(
                metric_type=metric_type,
                backend_id=backend_id,
                region=region
            )
    
    def add_sample(self, sample: MetricSample) -> None:
        """
        Add a sample to the appropriate metric.
        
        Args:
            sample: Metric sample
        """
        metric_type = sample.metric_type
        
        if metric_type not in self.metrics:
            self.metrics[metric_type] = MetricTimeSeries(
                metric_type=metric_type,
                backend_id=self.backend_id,
                region=self.region
            )
        
        self.metrics[metric_type].add_sample(sample)
    
    def get_metric(self, metric_type: NetworkMetricType) -> MetricTimeSeries:
        """
        Get the time series for a specific metric.
        
        Args:
            metric_type: Type of network metric
            
        Returns:
            MetricTimeSeries
        """
        if metric_type not in self.metrics:
            self.metrics[metric_type] = MetricTimeSeries(
                metric_type=metric_type,
                backend_id=self.backend_id,
                region=self.region
            )
        
        return self.metrics[metric_type]
    
    def get_overall_quality(self) -> NetworkQualityLevel:
        """
        Calculate the overall quality level for the backend.
        
        Returns:
            NetworkQualityLevel
        """
        # Get quality levels for important metrics
        quality_levels = []
        
        for metric_type in [
            NetworkMetricType.LATENCY,
            NetworkMetricType.DOWNLOAD_BANDWIDTH,
            NetworkMetricType.ERROR_RATE,
            NetworkMetricType.CONNECTION_STABILITY
        ]:
            if metric_type in self.metrics:
                metric = self.metrics[metric_type]
                if len(metric.samples) > 0:
                    quality_levels.append(metric.get_quality_level())
        
        if not quality_levels:
            return NetworkQualityLevel.UNKNOWN
        
        # Count occurrences of each quality level
        level_counts = {}
        for level in quality_levels:
            level_counts[level] = level_counts.get(level, 0) + 1
        
        # If any metric is CRITICAL, the overall quality is POOR at best
        if NetworkQualityLevel.CRITICAL in level_counts:
            critical_count = level_counts[NetworkQualityLevel.CRITICAL]
            if critical_count >= len(quality_levels) / 2:
                return NetworkQualityLevel.CRITICAL
            else:
                return NetworkQualityLevel.POOR
        
        # If any metric is POOR, the overall quality is FAIR at best
        if NetworkQualityLevel.POOR in level_counts:
            poor_count = level_counts[NetworkQualityLevel.POOR]
            if poor_count >= len(quality_levels) / 2:
                return NetworkQualityLevel.POOR
            else:
                return NetworkQualityLevel.FAIR
        
        # If all metrics are EXCELLENT, the overall quality is EXCELLENT
        if len(level_counts) == 1 and NetworkQualityLevel.EXCELLENT in level_counts:
            return NetworkQualityLevel.EXCELLENT
        
        # If all metrics are GOOD or EXCELLENT, the overall quality is GOOD
        good_and_excellent = level_counts.get(NetworkQualityLevel.GOOD, 0) + level_counts.get(NetworkQualityLevel.EXCELLENT, 0)
        if good_and_excellent == len(quality_levels):
            if level_counts.get(NetworkQualityLevel.EXCELLENT, 0) > level_counts.get(NetworkQualityLevel.GOOD, 0):
                return NetworkQualityLevel.EXCELLENT
            else:
                return NetworkQualityLevel.GOOD
        
        # Default to FAIR
        return NetworkQualityLevel.FAIR
    
    def get_performance_score(self) -> float:
        """
        Calculate a performance score (0.0-1.0).
        
        Returns:
            Performance score
        """
        # Get quality level
        quality = self.get_overall_quality()
        
        # Map quality level to score
        if quality == NetworkQualityLevel.EXCELLENT:
            base_score = 0.9
        elif quality == NetworkQualityLevel.GOOD:
            base_score = 0.75
        elif quality == NetworkQualityLevel.FAIR:
            base_score = 0.5
        elif quality == NetworkQualityLevel.POOR:
            base_score = 0.25
        elif quality == NetworkQualityLevel.CRITICAL:
            base_score = 0.1
        else:  # UNKNOWN
            return 0.5  # Default to average
        
        # Adjust score based on specific metrics
        adjustments = 0.0
        
        # Latency adjustment
        if NetworkMetricType.LATENCY in self.metrics:
            latency_metric = self.metrics[NetworkMetricType.LATENCY]
            if latency_metric.samples:
                latency_stats = latency_metric.get_statistics()
                # Lower latency is better
                if latency_stats["mean"] < 20:
                    adjustments += 0.05
                elif latency_stats["mean"] > 300:
                    adjustments -= 0.05
        
        # Bandwidth adjustment
        if NetworkMetricType.DOWNLOAD_BANDWIDTH in self.metrics:
            bandwidth_metric = self.metrics[NetworkMetricType.DOWNLOAD_BANDWIDTH]
            if bandwidth_metric.samples:
                bandwidth_stats = bandwidth_metric.get_statistics()
                # Higher bandwidth is better
                if bandwidth_stats["mean"] > 20 * 1024 * 1024:  # > 20 MB/s
                    adjustments += 0.05
                elif bandwidth_stats["mean"] < 50 * 1024:  # < 50 KB/s
                    adjustments -= 0.05
        
        # Error rate adjustment
        if NetworkMetricType.ERROR_RATE in self.metrics:
            error_metric = self.metrics[NetworkMetricType.ERROR_RATE]
            if error_metric.samples:
                error_stats = error_metric.get_statistics()
                # Lower error rate is better
                if error_stats["mean"] < 0.1:
                    adjustments += 0.05
                elif error_stats["mean"] > 5.0:
                    adjustments -= 0.1
        
        # Apply adjustments and clamp to range [0.0, 1.0]
        score = max(0.0, min(1.0, base_score + adjustments))
        
        return score
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "backend_id": self.backend_id,
            "region": self.region,
            "metrics": {
                metric_type.value: metric.to_dict()
                for metric_type, metric in self.metrics.items()
                if len(metric.samples) > 0
            },
            "overall_quality": self.get_overall_quality().value,
            "performance_score": self.get_performance_score()
        }


class NetworkAnalyzer:
    """
    Analyzes network metrics for storage backends.
    
    This class tracks and analyzes bandwidth, latency, and other network metrics
    for different storage backends, allowing for network-aware routing decisions.
    """
    
    def __init__(self):
        """Initialize the network analyzer."""
        self.backend_metrics: Dict[str, Dict[str, BackendNetworkMetrics]] = defaultdict(dict)
        self.lock = threading.RLock()
        
        # Measurement calibration
        self.measurement_overhead_ms = 5.0  # Default overhead
        
        # Synthetic data generation for testing
        self.synthetic_data_enabled = False
        self.synthetic_data_thread = None
        self.synthetic_data_stop_event = threading.Event()
    
    def get_metrics(self, backend_id: str, region: str = "") -> BackendNetworkMetrics:
        """
        Get network metrics for a specific backend and region.
        
        Args:
            backend_id: Backend identifier
            region: Backend region
            
        Returns:
            BackendNetworkMetrics
        """
        with self.lock:
            if backend_id not in self.backend_metrics or region not in self.backend_metrics[backend_id]:
                self.backend_metrics[backend_id][region] = BackendNetworkMetrics(
                    backend_id=backend_id,
                    region=region
                )
            
            return self.backend_metrics[backend_id][region]
    
    def add_sample(self, sample: MetricSample) -> None:
        """
        Add a metric sample.
        
        Args:
            sample: Metric sample
        """
        with self.lock:
            metrics = self.get_metrics(sample.backend_id, sample.region)
            metrics.add_sample(sample)
    
    def measure_latency(
        self,
        backend_id: str,
        endpoint_url: str,
        region: str = "",
        num_pings: int = 3,
        timeout_seconds: float = 5.0
    ) -> Optional[float]:
        """
        Measure round-trip latency to a backend endpoint.
        
        Args:
            backend_id: Backend identifier
            endpoint_url: Backend endpoint URL
            region: Backend region
            num_pings: Number of pings to perform
            timeout_seconds: Timeout in seconds
            
        Returns:
            Average latency in milliseconds or None if measurement failed
        """
        # In a real implementation, this would make HTTP requests to measure latency
        # Here we'll simulate it for demo purposes
        try:
            latencies = []
            
            for _ in range(num_pings):
                start_time = time.time()
                
                # Simulate HTTP request by sleeping
                # In a real implementation, this would be an actual HTTP request
                time.sleep(random.uniform(0.05, 0.3))  # 50-300ms simulated latency
                
                end_time = time.time()
                latency_ms = (end_time - start_time) * 1000.0  # Convert to milliseconds
                
                # Subtract measurement overhead
                latency_ms = max(0.0, latency_ms - self.measurement_overhead_ms)
                
                latencies.append(latency_ms)
            
            # Calculate average latency
            average_latency = statistics.mean(latencies)
            
            # Create and add sample
            sample = MetricSample(
                metric_type=NetworkMetricType.LATENCY,
                value=average_latency,
                backend_id=backend_id,
                region=region,
                sample_duration_ms=sum(latencies)
            )
            
            self.add_sample(sample)
            
            return average_latency
            
        except Exception as e:
            logger.warning(f"Failed to measure latency for {backend_id}: {str(e)}")
            return None
    
    def measure_bandwidth(
        self,
        backend_id: str,
        endpoint_url: str,
        direction: str = "download",
        region: str = "",
        test_size_bytes: int = 1024 * 1024,  # 1 MB
        timeout_seconds: float = 30.0
    ) -> Optional[float]:
        """
        Measure bandwidth to a backend endpoint.
        
        Args:
            backend_id: Backend identifier
            endpoint_url: Backend endpoint URL
            direction: "download" or "upload"
            region: Backend region
            test_size_bytes: Size of test data in bytes
            timeout_seconds: Timeout in seconds
            
        Returns:
            Bandwidth in bytes/second or None if measurement failed
        """
        # In a real implementation, this would transfer data to measure bandwidth
        # Here we'll simulate it for demo purposes
        try:
            start_time = time.time()
            
            # Simulate data transfer by sleeping
            # In a real implementation, this would be an actual data transfer
            # Simulate different speeds for different backends and random variations
            transfer_duration = 0.0
            
            if backend_id == "ipfs":
                # IPFS tends to be slower
                bytes_per_second = random.uniform(500 * 1024, 2 * 1024 * 1024)  # 500 KB/s - 2 MB/s
            elif backend_id == "s3":
                # S3 tends to be faster
                bytes_per_second = random.uniform(2 * 1024 * 1024, 10 * 1024 * 1024)  # 2 MB/s - 10 MB/s
            else:
                # Default midrange speed
                bytes_per_second = random.uniform(1 * 1024 * 1024, 5 * 1024 * 1024)  # 1 MB/s - 5 MB/s
                
            # Calculate how long the transfer would take
            transfer_duration = test_size_bytes / bytes_per_second
            
            # Sleep to simulate the transfer
            time.sleep(min(transfer_duration, timeout_seconds))
            
            end_time = time.time()
            
            # Calculate actual bandwidth
            elapsed_seconds = end_time - start_time
            
            if elapsed_seconds <= 0:
                return None
                
            bandwidth = test_size_bytes / elapsed_seconds  # bytes/second
            
            # Create and add sample
            metric_type = (
                NetworkMetricType.DOWNLOAD_BANDWIDTH
                if direction == "download"
                else NetworkMetricType.UPLOAD_BANDWIDTH
            )
            
            sample = MetricSample(
                metric_type=metric_type,
                value=bandwidth,
                backend_id=backend_id,
                region=region,
                request_size_bytes=test_size_bytes,
                sample_duration_ms=elapsed_seconds * 1000.0
            )
            
            self.add_sample(sample)
            
            return bandwidth
            
        except Exception as e:
            logger.warning(f"Failed to measure {direction} bandwidth for {backend_id}: {str(e)}")
            return None
    
    def measure_error_rate(
        self,
        backend_id: str,
        endpoint_url: str,
        region: str = "",
        num_requests: int = 10,
        timeout_seconds: float = 10.0
    ) -> Optional[float]:
        """
        Measure error rate for requests to a backend endpoint.
        
        Args:
            backend_id: Backend identifier
            endpoint_url: Backend endpoint URL
            region: Backend region
            num_requests: Number of requests to perform
            timeout_seconds: Timeout in seconds
            
        Returns:
            Error rate as percentage (0-100) or None if measurement failed
        """
        # In a real implementation, this would make HTTP requests to measure error rate
        # Here we'll simulate it for demo purposes
        try:
            errors = 0
            
            for _ in range(num_requests):
                # Simulate request failure probability based on backend
                if backend_id == "ipfs":
                    # IPFS might have higher error rates
                    failure_probability = 0.1  # 10% failure rate
                elif backend_id == "s3":
                    # S3 would have lower error rates
                    failure_probability = 0.01  # 1% failure rate
                else:
                    # Default moderate error rate
                    failure_probability = 0.05  # 5% failure rate
                
                # Simulate request
                if random.random() < failure_probability:
                    errors += 1
            
            # Calculate error rate
            error_rate = (errors / num_requests) * 100.0  # Convert to percentage
            
            # Create and add sample
            sample = MetricSample(
                metric_type=NetworkMetricType.ERROR_RATE,
                value=error_rate,
                backend_id=backend_id,
                region=region,
                request_type="test",
                sample_duration_ms=0.0
            )
            
            self.add_sample(sample)
            
            return error_rate
            
        except Exception as e:
            logger.warning(f"Failed to measure error rate for {backend_id}: {str(e)}")
            return None
    
    def rank_backends_by_network_quality(
        self,
        backend_ids: List[str],
        region: str = "",
        metric_weights: Optional[Dict[NetworkMetricType, float]] = None
    ) -> List[Tuple[str, float, NetworkQualityLevel]]:
        """
        Rank backends by network quality.
        
        Args:
            backend_ids: List of backend identifiers
            region: Backend region
            metric_weights: Optional weights for different metrics
            
        Returns:
            List of (backend_id, score, quality_level) tuples sorted by score
        """
        # Default weights if not provided
        if metric_weights is None:
            metric_weights = {
                NetworkMetricType.LATENCY: 0.3,
                NetworkMetricType.DOWNLOAD_BANDWIDTH: 0.3,
                NetworkMetricType.UPLOAD_BANDWIDTH: 0.1,
                NetworkMetricType.ERROR_RATE: 0.2,
                NetworkMetricType.CONNECTION_STABILITY: 0.1
            }
        
        rankings = []
        
        for backend_id in backend_ids:
            try:
                # Get metrics for backend
                metrics = self.get_metrics(backend_id, region)
                
                # Get overall quality level
                quality_level = metrics.get_overall_quality()
                
                # Get performance score
                score = metrics.get_performance_score()
                
                # Add to rankings
                rankings.append((backend_id, score, quality_level))
                
            except Exception as e:
                logger.warning(f"Failed to rank backend {backend_id}: {str(e)}")
                # Add with unknown quality and low score
                rankings.append((backend_id, 0.1, NetworkQualityLevel.UNKNOWN))
        
        # Sort by score (higher is better)
        return sorted(rankings, key=lambda x: x[1], reverse=True)
    
    def select_backend_by_network_quality(
        self,
        backend_ids: List[str],
        min_quality_level: NetworkQualityLevel = NetworkQualityLevel.FAIR,
        region: str = ""
    ) -> Optional[str]:
        """
        Select a backend based on network quality.
        
        Args:
            backend_ids: List of backend identifiers
            min_quality_level: Minimum acceptable quality level
            region: Backend region
            
        Returns:
            Selected backend identifier or None if no suitable backend found
        """
        # Rank backends by network quality
        rankings = self.rank_backends_by_network_quality(backend_ids, region)
        
        # Filter by minimum quality level
        quality_rankings = []
        
        for backend_id, score, quality_level in rankings:
            # Map quality levels to numeric values for comparison
            quality_values = {
                NetworkQualityLevel.EXCELLENT: 5,
                NetworkQualityLevel.GOOD: 4,
                NetworkQualityLevel.FAIR: 3,
                NetworkQualityLevel.POOR: 2,
                NetworkQualityLevel.CRITICAL: 1,
                NetworkQualityLevel.UNKNOWN: 0
            }
            
            min_value = quality_values.get(min_quality_level, 0)
            backend_value = quality_values.get(quality_level, 0)
            
            if backend_value >= min_value:
                quality_rankings.append((backend_id, score, quality_level))
        
        # Return highest ranking backend that meets quality requirement
        if quality_rankings:
            return quality_rankings[0][0]
        
        # If no backends meet the quality requirement, return the highest ranking backend
        if rankings:
            return rankings[0][0]
        
        return None
    
    def predict_network_conditions(
        self,
        backend_id: str,
        future_time: datetime,
        region: str = ""
    ) -> Dict[str, Any]:
        """
        Predict future network conditions for a backend.
        
        Args:
            backend_id: Backend identifier
            future_time: Future time to predict for
            region: Backend region
            
        Returns:
            Dictionary with predictions
        """
        metrics = self.get_metrics(backend_id, region)
        
        predictions = {}
        
        # Predict values for important metrics
        for metric_type in [
            NetworkMetricType.LATENCY,
            NetworkMetricType.DOWNLOAD_BANDWIDTH,
            NetworkMetricType.UPLOAD_BANDWIDTH,
            NetworkMetricType.ERROR_RATE
        ]:
            metric = metrics.get_metric(metric_type)
            predicted_value = metric.predict_future_value(future_time)
            
            if predicted_value is not None:
                predictions[metric_type.value] = predicted_value
        
        # Add metadata
        predictions["prediction_time"] = future_time.isoformat()
        predictions["backend_id"] = backend_id
        predictions["region"] = region
        
        return predictions
    
    def get_network_quality_history(
        self,
        backend_id: str,
        start_time: datetime,
        end_time: datetime,
        region: str = "",
        resolution_minutes: int = 60
    ) -> Dict[str, Any]:
        """
        Get historical network quality data.
        
        Args:
            backend_id: Backend identifier
            start_time: Start time
            end_time: End time
            region: Backend region
            resolution_minutes: Time resolution in minutes
            
        Returns:
            Dictionary with historical data
        """
        metrics = self.get_metrics(backend_id, region)
        
        # Calculate time windows
        time_windows = []
        current_time = start_time
        window_duration = timedelta(minutes=resolution_minutes)
        
        while current_time < end_time:
            window_end = min(current_time + window_duration, end_time)
            time_windows.append((current_time, window_end))
            current_time = window_end
        
        # Get data for each window
        history = []
        
        for window_start, window_end in time_windows:
            window_data = {
                "start_time": window_start.isoformat(),
                "end_time": window_end.isoformat(),
                "metrics": {}
            }
            
            # Get statistics for each metric type
            for metric_type in NetworkMetricType:
                metric = metrics.get_metric(metric_type)
                stats = metric.get_statistics(window_start, window_end)
                
                if stats["count"] > 0:
                    window_data["metrics"][metric_type.value] = stats
            
            # Get overall quality for window
            quality_level = metrics.get_overall_quality()
            window_data["quality_level"] = quality_level.value
            
            history.append(window_data)
        
        return {
            "backend_id": backend_id,
            "region": region,
            "history": history
        }
    
    def clear_metrics(
        self,
        backend_id: Optional[str] = None,
        region: Optional[str] = None,
        older_than: Optional[datetime] = None
    ) -> None:
        """
        Clear metrics.
        
        Args:
            backend_id: Backend identifier (clear all if None)
            region: Backend region (clear all regions if None)
            older_than: Clear metrics older than this time (clear all if None)
        """
        with self.lock:
            if backend_id is None:
                # Clear all backends
                if older_than is None:
                    self.backend_metrics.clear()
                else:
                    # Only clear old metrics
                    pass  # Not implemented for this demo
            else:
                # Clear specific backend
                if backend_id in self.backend_metrics:
                    if region is None:
                        # Clear all regions for backend
                        if older_than is None:
                            self.backend_metrics[backend_id].clear()
                        else:
                            # Only clear old metrics
                            pass  # Not implemented for this demo
                    else:
                        # Clear specific region for backend
                        if region in self.backend_metrics[backend_id]:
                            if older_than is None:
                                del self.backend_metrics[backend_id][region]
                            else:
                                # Only clear old metrics
                                pass  # Not implemented for this demo
    
    def get_all_backends_metrics(self) -> Dict[str, Any]:
        """
        Get metrics for all backends.
        
        Returns:
            Dictionary with metrics for all backends
        """
        result = {}
        
        with self.lock:
            for backend_id, regions in self.backend_metrics.items():
                backend_data = {}
                
                for region, metrics in regions.items():
                    backend_data[region] = metrics.to_dict()
                
                result[backend_id] = backend_data
        
        return result
    
    def enable_synthetic_data(
        self,
        backend_ids: List[str] = None,
        update_interval_seconds: float = 30.0
    ) -> None:
        """
        Enable synthetic data generation for testing.
        
        Args:
            backend_ids: List of backend identifiers
            update_interval_seconds: Update interval in seconds
        """
        if backend_ids is None:
            backend_ids = ["ipfs", "filecoin", "s3", "storacha", "huggingface", "lassie"]
        
        self.synthetic_data_enabled = True
        self.synthetic_data_stop_event.clear()
        
        if self.synthetic_data_thread is None or not self.synthetic_data_thread.is_alive():
            self.synthetic_data_thread = threading.Thread(
                target=self._generate_synthetic_data,
                args=(backend_ids, update_interval_seconds),
                daemon=True
            )
            self.synthetic_data_thread.start()
    
    def disable_synthetic_data(self) -> None:
        """Disable synthetic data generation."""
        self.synthetic_data_enabled = False
        self.synthetic_data_stop_event.set()
        
        if self.synthetic_data_thread and self.synthetic_data_thread.is_alive():
            self.synthetic_data_thread.join(timeout=1.0)
            self.synthetic_data_thread = None
    
    def _generate_synthetic_data(
        self,
        backend_ids: List[str],
        update_interval_seconds: float
    ) -> None:
        """
        Generate synthetic data for testing.
        
        Args:
            backend_ids: List of backend identifiers
            update_interval_seconds: Update interval in seconds
        """
        regions = ["us-east", "us-west", "eu-central", "ap-southeast"]
        
        while not self.synthetic_data_stop_event.is_set():
            for backend_id in backend_ids:
                for region in regions:
                    # Generate latency sample
                    if backend_id == "ipfs":
                        latency = random.uniform(80, 200)  # Higher latency
                    elif backend_id == "s3":
                        latency = random.uniform(20, 80)   # Lower latency
                    else:
                        latency = random.uniform(50, 150)  # Moderate latency
                    
                    latency_sample = MetricSample(
                        metric_type=NetworkMetricType.LATENCY,
                        value=latency,
                        backend_id=backend_id,
                        region=region
                    )
                    
                    # Generate download bandwidth sample
                    if backend_id == "ipfs":
                        bandwidth = random.uniform(500 * 1024, 2 * 1024 * 1024)  # 500 KB/s - 2 MB/s
                    elif backend_id == "s3":
                        bandwidth = random.uniform(2 * 1024 * 1024, 10 * 1024 * 1024)  # 2 MB/s - 10 MB/s
                    else:
                        bandwidth = random.uniform(1 * 1024 * 1024, 5 * 1024 * 1024)  # 1 MB/s - 5 MB/s
                    
                    bandwidth_sample = MetricSample(
                        metric_type=NetworkMetricType.DOWNLOAD_BANDWIDTH,
                        value=bandwidth,
                        backend_id=backend_id,
                        region=region
                    )
                    
                    # Generate error rate sample
                    if backend_id == "ipfs":
                        error_rate = random.uniform(1.0, 5.0)  # Higher error rate
                    elif backend_id == "s3":
                        error_rate = random.uniform(0.1, 1.0)  # Lower error rate
                    else:
                        error_rate = random.uniform(0.5, 3.0)  # Moderate error rate
                    
                    error_sample = MetricSample(
                        metric_type=NetworkMetricType.ERROR_RATE,
                        value=error_rate,
                        backend_id=backend_id,
                        region=region
                    )
                    
                    # Add samples
                    self.add_sample(latency_sample)
                    self.add_sample(bandwidth_sample)
                    self.add_sample(error_sample)
            
            # Wait for next update
            if self.synthetic_data_stop_event.wait(update_interval_seconds):
                # Stop event was set
                break


# Helper function for calculating percentiles
def percentile(data: List[float], percentile: float) -> float:
    """
    Calculate percentile of a list of values.
    
    Args:
        data: List of values
        percentile: Percentile (0-100)
        
    Returns:
        Percentile value
    """
    size = len(data)
    if size == 0:
        return 0.0
        
    sorted_data = sorted(data)
    
    if percentile <= 0:
        return sorted_data[0]
    if percentile >= 100:
        return sorted_data[-1]
    
    # Calculate rank (0-based)
    rank = (percentile / 100.0) * (size - 1)
    
    # Get integer part and fractional part
    rank_int = int(rank)
    rank_frac = rank - rank_int
    
    # Interpolate between values
    if rank_int + 1 < size:
        return sorted_data[rank_int] * (1 - rank_frac) + sorted_data[rank_int + 1] * rank_frac
    else:
        return sorted_data[rank_int]


# Factory function to create a network analyzer
def create_network_analyzer() -> NetworkAnalyzer:
    """
    Create a network analyzer.
    
    Returns:
        NetworkAnalyzer instance
    """
    return NetworkAnalyzer()