"""
Observability module for the MCP Optimized Data Routing system.

This module provides metrics, logging, and tracing capabilities to monitor 
the performance and behavior of the routing optimization system.
"""

import os
import time
import json
import logging
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Union
from enum import Enum
import threading
from collections import defaultdict, deque

# Configure logging
logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics collected by the observability system."""
    
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


class RoutingMetrics:
    """Collects and exposes metrics for the routing system."""
    
    def __init__(self):
        """Initialize the metrics collector."""
        self._metrics = defaultdict(lambda: {
            "type": None,
            "value": 0,
            "samples": deque(maxlen=100),
            "timestamp": time.time(),
            "labels": {}
        })
        self._lock = threading.Lock()
    
    def counter(self, name: str, increment: float = 1.0, labels: Optional[Dict[str, str]] = None):
        """
        Increment a counter metric.
        
        Args:
            name: Metric name
            increment: Value to increment by
            labels: Optional labels for the metric
        """
        with self._lock:
            if name not in self._metrics or self._metrics[name]["type"] is None:
                self._metrics[name]["type"] = MetricType.COUNTER.value
            
            if self._metrics[name]["type"] != MetricType.COUNTER.value:
                logger.warning(f"Metric {name} is not a counter")
                return
            
            self._metrics[name]["value"] += increment
            self._metrics[name]["timestamp"] = time.time()
            
            if labels:
                self._metrics[name]["labels"].update(labels)
    
    def gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """
        Set a gauge metric.
        
        Args:
            name: Metric name
            value: Current value
            labels: Optional labels for the metric
        """
        with self._lock:
            if name not in self._metrics or self._metrics[name]["type"] is None:
                self._metrics[name]["type"] = MetricType.GAUGE.value
            
            if self._metrics[name]["type"] != MetricType.GAUGE.value:
                logger.warning(f"Metric {name} is not a gauge")
                return
            
            self._metrics[name]["value"] = value
            self._metrics[name]["timestamp"] = time.time()
            
            if labels:
                self._metrics[name]["labels"].update(labels)
    
    def observe(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """
        Add a sample to a histogram metric.
        
        Args:
            name: Metric name
            value: Observed value
            labels: Optional labels for the metric
        """
        with self._lock:
            if name not in self._metrics or self._metrics[name]["type"] is None:
                self._metrics[name]["type"] = MetricType.HISTOGRAM.value
            
            if self._metrics[name]["type"] != MetricType.HISTOGRAM.value:
                logger.warning(f"Metric {name} is not a histogram")
                return
            
            self._metrics[name]["samples"].append(value)
            self._metrics[name]["timestamp"] = time.time()
            
            if labels:
                self._metrics[name]["labels"].update(labels)
    
    def start_timer(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        """
        Start a timer metric.
        
        Args:
            name: Metric name
            labels: Optional labels for the metric
            
        Returns:
            Start time
        """
        start_time = time.time()
        
        with self._lock:
            if name not in self._metrics or self._metrics[name]["type"] is None:
                self._metrics[name]["type"] = MetricType.TIMER.value
            
            if self._metrics[name]["type"] != MetricType.TIMER.value:
                logger.warning(f"Metric {name} is not a timer")
                return start_time
            
            if labels:
                self._metrics[name]["labels"].update(labels)
        
        return start_time
    
    def stop_timer(self, name: str, start_time: float):
        """
        Stop a timer metric and record the duration.
        
        Args:
            name: Metric name
            start_time: Start time returned by start_timer
        """
        duration = time.time() - start_time
        
        with self._lock:
            if name not in self._metrics or self._metrics[name]["type"] != MetricType.TIMER.value:
                logger.warning(f"Metric {name} is not a timer")
                return
            
            self._metrics[name]["samples"].append(duration)
            self._metrics[name]["timestamp"] = time.time()
    
    def get_metrics(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all collected metrics.
        
        Returns:
            Dict of metrics
        """
        result = {}
        
        with self._lock:
            for name, data in self._metrics.items():
                result[name] = {
                    "type": data["type"],
                    "labels": dict(data["labels"]),
                    "timestamp": data["timestamp"]
                }
                
                if data["type"] == MetricType.COUNTER.value:
                    result[name]["value"] = data["value"]
                
                elif data["type"] == MetricType.GAUGE.value:
                    result[name]["value"] = data["value"]
                
                elif data["type"] == MetricType.HISTOGRAM.value:
                    samples = list(data["samples"])
                    if samples:
                        result[name].update({
                            "count": len(samples),
                            "sum": sum(samples),
                            "min": min(samples),
                            "max": max(samples),
                            "mean": statistics.mean(samples) if samples else 0,
                            "median": statistics.median(samples) if samples else 0,
                            "p95": self._percentile(samples, 95),
                            "p99": self._percentile(samples, 99)
                        })
                    else:
                        result[name].update({
                            "count": 0,
                            "sum": 0,
                            "min": 0,
                            "max": 0,
                            "mean": 0,
                            "median": 0,
                            "p95": 0,
                            "p99": 0
                        })
                
                elif data["type"] == MetricType.TIMER.value:
                    samples = list(data["samples"])
                    if samples:
                        result[name].update({
                            "count": len(samples),
                            "sum": sum(samples),
                            "min": min(samples),
                            "max": max(samples),
                            "mean": statistics.mean(samples),
                            "median": statistics.median(samples),
                            "p95": self._percentile(samples, 95),
                            "p99": self._percentile(samples, 99)
                        })
                    else:
                        result[name].update({
                            "count": 0,
                            "sum": 0,
                            "min": 0,
                            "max": 0,
                            "mean": 0,
                            "median": 0,
                            "p95": 0,
                            "p99": 0
                        })
        
        return result
    
    def _percentile(self, data: List[float], percentile: float) -> float:
        """
        Calculate percentile of a list of values.
        
        Args:
            data: List of values
            percentile: Percentile to calculate (0-100)
            
        Returns:
            Percentile value
        """
        if not data:
            return 0.0
            
        # Sort data
        sorted_data = sorted(data)
        n = len(sorted_data)
        
        # Calculate index
        idx = (n - 1) * percentile / 100
        idx_floor = int(idx)
        idx_ceil = min(idx_floor + 1, n - 1)
        
        # Interpolate
        if idx_floor == idx_ceil:
            return sorted_data[idx_floor]
        else:
            return sorted_data[idx_floor] + (sorted_data[idx_ceil] - sorted_data[idx_floor]) * (idx - idx_floor)


class RoutingTracer:
    """
    Traces routing decisions for debugging and analysis.
    
    This class captures detailed information about routing decisions,
    including all factors considered and their weights.
    """
    
    def __init__(
        self, 
        max_traces: int = 1000, 
        detailed: bool = False,
        trace_to_log: bool = False
    ):
        """
        Initialize the tracer.
        
        Args:
            max_traces: Maximum number of traces to keep in memory
            detailed: Whether to capture detailed information
            trace_to_log: Whether to log traces as they are captured
        """
        self.traces = deque(maxlen=max_traces)
        self.detailed = detailed
        self.trace_to_log = trace_to_log
        self._lock = threading.Lock()
    
    def trace_routing_decision(
        self,
        content_id: str,
        content_category: str,
        content_size_bytes: int,
        selected_backend: str,
        available_backends: List[str],
        overall_score: float,
        factor_scores: Dict[str, float],
        weights: Dict[str, float],
        client_info: Optional[Dict[str, Any]] = None,
        execution_time_ms: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        Trace a routing decision.
        
        Args:
            content_id: Content identifier
            content_category: Content category
            content_size_bytes: Content size in bytes
            selected_backend: Selected backend
            available_backends: Available backends
            overall_score: Overall score
            factor_scores: Factor scores
            weights: Factor weights
            client_info: Optional client information
            execution_time_ms: Optional execution time
            context: Optional additional context
        """
        timestamp = datetime.utcnow().isoformat()
        
        trace = {
            "timestamp": timestamp,
            "content_id": content_id,
            "content_category": content_category,
            "content_size_bytes": content_size_bytes,
            "selected_backend": selected_backend,
            "available_backends": available_backends,
            "overall_score": overall_score,
            "factor_scores": factor_scores,
            "weights": weights
        }
        
        if client_info is not None:
            trace["client_info"] = client_info
        
        if execution_time_ms is not None:
            trace["execution_time_ms"] = execution_time_ms
        
        if context is not None and self.detailed:
            trace["context"] = context
        
        with self._lock:
            self.traces.append(trace)
        
        if self.trace_to_log:
            logger.info(f"Routing trace: {json.dumps(trace)}")
    
    def get_traces(
        self, 
        limit: Optional[int] = None,
        content_category: Optional[str] = None,
        backend_id: Optional[str] = None,
        since: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get captured traces.
        
        Args:
            limit: Maximum number of traces to return
            content_category: Filter by content category
            backend_id: Filter by backend ID
            since: Filter by timestamp
            
        Returns:
            List of traces
        """
        with self._lock:
            # Start with all traces
            filtered_traces = list(self.traces)
        
        # Apply filters
        if content_category is not None:
            filtered_traces = [
                t for t in filtered_traces
                if t.get("content_category") == content_category
            ]
        
        if backend_id is not None:
            filtered_traces = [
                t for t in filtered_traces
                if t.get("selected_backend") == backend_id
            ]
        
        if since is not None:
            since_str = since.isoformat()
            filtered_traces = [
                t for t in filtered_traces
                if t.get("timestamp", "") >= since_str
            ]
        
        # Apply limit
        if limit is not None:
            filtered_traces = filtered_traces[-limit:]
        
        return filtered_traces


class RoutingObservability:
    """
    Main observability class for the routing system.
    
    This class combines metrics and tracing to provide comprehensive
    observability for the routing system.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the observability system.
        
        Args:
            config: Optional configuration
        """
        self.config = config or {}
        self.metrics = RoutingMetrics()
        
        # Create tracer
        trace_config = self.config.get("tracing", {})
        self.tracer = RoutingTracer(
            max_traces=trace_config.get("max_traces", 1000),
            detailed=trace_config.get("detailed", False),
            trace_to_log=trace_config.get("trace_to_log", False)
        )
        
        # Track backend selection
        self.backend_selection_counter = defaultdict(int)
        self._lock = threading.Lock()
    
    def record_routing_decision(
        self,
        content_id: str,
        content_category: str,
        content_size_bytes: int,
        selected_backend: str,
        available_backends: List[str],
        overall_score: float,
        factor_scores: Dict[str, float],
        weights: Dict[str, float],
        client_info: Optional[Dict[str, Any]] = None,
        execution_time_ms: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        Record a routing decision.
        
        This updates both metrics and traces.
        
        Args:
            content_id: Content identifier
            content_category: Content category
            content_size_bytes: Content size in bytes
            selected_backend: Selected backend
            available_backends: Available backends
            overall_score: Overall score
            factor_scores: Factor scores
            weights: Factor weights
            client_info: Optional client information
            execution_time_ms: Optional execution time
            context: Optional additional context
        """
        # Update backend selection counter
        with self._lock:
            self.backend_selection_counter[selected_backend] += 1
        
        # Update metrics
        self.metrics.counter(
            "routing.decisions.total",
            labels={"category": content_category}
        )
        
        self.metrics.counter(
            f"routing.backend.{selected_backend}.selections",
            labels={"category": content_category}
        )
        
        self.metrics.observe(
            "routing.decision.score",
            overall_score,
            labels={"backend": selected_backend, "category": content_category}
        )
        
        self.metrics.gauge(
            f"routing.backend.{selected_backend}.load",
            self.backend_selection_counter[selected_backend],
            labels={"category": content_category}
        )
        
        if execution_time_ms is not None:
            self.metrics.observe(
                "routing.decision.execution_time_ms",
                execution_time_ms,
                labels={"backend": selected_backend, "category": content_category}
            )
        
        # Trace decision
        self.tracer.trace_routing_decision(
            content_id=content_id,
            content_category=content_category,
            content_size_bytes=content_size_bytes,
            selected_backend=selected_backend,
            available_backends=available_backends,
            overall_score=overall_score,
            factor_scores=factor_scores,
            weights=weights,
            client_info=client_info,
            execution_time_ms=execution_time_ms,
            context=context
        )
    
    def record_routing_outcome(
        self,
        content_id: str,
        backend_id: str,
        content_category: str,
        success: bool,
        error_details: Optional[str] = None
    ):
        """
        Record the outcome of a routing decision.
        
        Args:
            content_id: Content identifier
            backend_id: Backend identifier
            content_category: Content category
            success: Whether the routing was successful
            error_details: Optional error details
        """
        # Update metrics
        outcome = "success" if success else "failure"
        
        self.metrics.counter(
            f"routing.outcome.{outcome}",
            labels={
                "backend": backend_id,
                "category": content_category
            }
        )
        
        # Calculate success rate
        total_success = self.metrics.get_metrics().get(
            "routing.outcome.success", {}
        ).get("value", 0)
        
        total_failure = self.metrics.get_metrics().get(
            "routing.outcome.failure", {}
        ).get("value", 0)
        
        total = total_success + total_failure
        success_rate = total_success / total if total > 0 else 0
        
        self.metrics.gauge(
            "routing.outcome.success_rate",
            success_rate,
            labels={"backend": backend_id, "category": content_category}
        )
        
        # Log error details if provided
        if not success and error_details:
            logger.warning(
                f"Routing failure for content {content_id} on backend {backend_id}: {error_details}"
            )
    
    def get_metrics(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all collected metrics.
        
        Returns:
            Dict of metrics
        """
        return self.metrics.get_metrics()
    
    def get_traces(
        self, 
        limit: Optional[int] = None,
        content_category: Optional[str] = None,
        backend_id: Optional[str] = None,
        since: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get captured traces.
        
        Args:
            limit: Maximum number of traces to return
            content_category: Filter by content category
            backend_id: Filter by backend ID
            since: Filter by timestamp
            
        Returns:
            List of traces
        """
        return self.tracer.get_traces(
            limit=limit,
            content_category=content_category,
            backend_id=backend_id,
            since=since
        )
    
    def get_backend_load_distribution(self) -> Dict[str, float]:
        """
        Get the load distribution across backends.
        
        Returns:
            Dict mapping backend IDs to their share of the load
        """
        with self._lock:
            counters = dict(self.backend_selection_counter)
        
        total = sum(counters.values())
        if total == 0:
            return {}
        
        return {
            backend_id: count / total
            for backend_id, count in counters.items()
        }
    
    def reset_metrics(self):
        """Reset all metrics."""
        self.metrics = RoutingMetrics()
        
        with self._lock:
            self.backend_selection_counter.clear()


# Global instance for easy access
routing_observability = RoutingObservability()