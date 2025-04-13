"""
MCP Server Blue/Green Metrics Collector

This module provides metrics collection functionality for the MCP Server
blue/green deployment, with support for Prometheus integration.
"""

import time
import logging
import threading
from enum import Enum
from typing import Dict, Any, Optional, List, Union, Callable

try:
    import prometheus_client
    from prometheus_client import Counter, Gauge, Histogram, Summary
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logging.warning("Prometheus client not available. Install with: pip install prometheus-client")

# Configure logging
logger = logging.getLogger(__name__)

class ServerType(Enum):
    """Type of server being measured."""
    BLUE = "blue"
    GREEN = "green"

class MetricsCollector:
    """
    Metrics collector for the MCP Server blue/green deployment.
    
    Collects and exposes metrics about server performance, including:
    - Request counts (total, successes, failures)
    - Response times
    - Health status
    - Memory usage
    - Custom metrics
    
    Can export metrics to Prometheus if the prometheus_client library is available.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the metrics collector with the given configuration.
        
        Args:
            config: Dictionary containing configuration options
        """
        self.config = config or {}
        self.metrics = {
            ServerType.BLUE: self._init_server_metrics(),
            ServerType.GREEN: self._init_server_metrics()
        }
        
        # Overall metrics for the proxy
        self.overall_metrics = {
            "start_time": time.time(),
            "total_requests": 0,
            "blue_green_comparison_metrics": {
                "total_comparisons": 0,
                "identical_responses": 0,
                "different_responses": 0,
                "response_time_diffs": []
            }
        }
        
        # Set up Prometheus if available and enabled
        self.prometheus_enabled = (
            PROMETHEUS_AVAILABLE and 
            self.config.get("prometheus", {}).get("enabled", False)
        )
        
        if self.prometheus_enabled:
            self._setup_prometheus()
        
        logger.info("Metrics collector initialized")
    
    def _init_server_metrics(self) -> Dict[str, Any]:
        """Initialize metrics dictionary for a server type."""
        return {
            "requests": {
                "total": 0,
                "successes": 0,
                "failures": 0,
                "by_endpoint": {}  # Will be populated as requests come in
            },
            "response_times": [],
            "recent_response_times": [],  # Last 100 requests
            "health_checks": {
                "total": 0,
                "healthy": 0,
                "unhealthy": 0,
                "last_status": None,
                "last_check_time": None
            },
            "errors": {
                "total": 0,
                "by_type": {}  # Will be populated as errors occur
            },
            "custom_metrics": {}  # For any additional metrics
        }
    
    def _setup_prometheus(self) -> None:
        """Set up Prometheus metrics if enabled."""
        if not self.prometheus_enabled:
            return
        
        # Server-specific metrics
        self.prom_request_counter = Counter(
            'mcp_server_requests_total', 
            'Total number of requests processed',
            ['server', 'status']
        )
        
        self.prom_response_time = Histogram(
            'mcp_server_response_time_seconds',
            'Response time in seconds',
            ['server'],
            buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
        )
        
        self.prom_health_gauge = Gauge(
            'mcp_server_health',
            'Health status (1=healthy, 0=unhealthy)',
            ['server']
        )
        
        # Comparison metrics
        self.prom_comparison_counter = Counter(
            'mcp_blue_green_comparisons_total',
            'Total number of blue/green response comparisons',
            ['result']  # 'identical' or 'different'
        )
        
        self.prom_response_diff = Histogram(
            'mcp_blue_green_response_time_diff_seconds',
            'Difference in response time between blue and green servers',
            buckets=(-1.0, -0.5, -0.1, -0.05, -0.01, 0.01, 0.05, 0.1, 0.5, 1.0)
        )
        
        # Start prometheus HTTP server if port is specified
        prom_port = self.config.get("prometheus", {}).get("port", 9100)
        prometheus_client.start_http_server(prom_port)
        logger.info(f"Prometheus metrics server started on port {prom_port}")
    
    def record_request(
        self, 
        server_type: ServerType, 
        success: bool, 
        response_time: float,
        endpoint: str = "default"
    ) -> None:
        """
        Record metrics for a request.
        
        Args:
            server_type: Type of server that processed the request
            success: Whether the request was successful
            response_time: Time taken to process the request in seconds
            endpoint: Endpoint or request type that was accessed
        """
        metrics = self.metrics[server_type]
        
        # Update request counts
        metrics["requests"]["total"] += 1
        if success:
            metrics["requests"]["successes"] += 1
        else:
            metrics["requests"]["failures"] += 1
        
        # Update endpoint-specific metrics
        if endpoint not in metrics["requests"]["by_endpoint"]:
            metrics["requests"]["by_endpoint"][endpoint] = {
                "total": 0, 
                "successes": 0, 
                "failures": 0
            }
        
        metrics["requests"]["by_endpoint"][endpoint]["total"] += 1
        if success:
            metrics["requests"]["by_endpoint"][endpoint]["successes"] += 1
        else:
            metrics["requests"]["by_endpoint"][endpoint]["failures"] += 1
        
        # Update response times
        metrics["response_times"].append(response_time)
        metrics["recent_response_times"].append(response_time)
        if len(metrics["recent_response_times"]) > 100:
            metrics["recent_response_times"].pop(0)  # Keep only last 100
        
        # Update overall count
        self.overall_metrics["total_requests"] += 1
        
        # Update Prometheus metrics if enabled
        if self.prometheus_enabled:
            status = "success" if success else "failure"
            self.prom_request_counter.labels(
                server=server_type.value, 
                status=status
            ).inc()
            
            self.prom_response_time.labels(
                server=server_type.value
            ).observe(response_time)
    
    def record_health_check(self, server_type: ServerType, healthy: bool) -> None:
        """
        Record metrics for a health check.
        
        Args:
            server_type: Type of server that was checked
            healthy: Whether the server was healthy
        """
        metrics = self.metrics[server_type]["health_checks"]
        
        metrics["total"] += 1
        if healthy:
            metrics["healthy"] += 1
        else:
            metrics["unhealthy"] += 1
        
        metrics["last_status"] = healthy
        metrics["last_check_time"] = time.time()
        
        # Update Prometheus metrics if enabled
        if self.prometheus_enabled:
            self.prom_health_gauge.labels(
                server=server_type.value
            ).set(1 if healthy else 0)
    
    def record_error(
        self, 
        server_type: ServerType, 
        error_type: str, 
        error_msg: str = None
    ) -> None:
        """
        Record metrics for an error.
        
        Args:
            server_type: Type of server that experienced the error
            error_type: Type or category of error
            error_msg: Error message (optional)
        """
        metrics = self.metrics[server_type]["errors"]
        
        metrics["total"] += 1
        
        if error_type not in metrics["by_type"]:
            metrics["by_type"][error_type] = {
                "count": 0,
                "recent": []  # Will store recent error messages
            }
        
        metrics["by_type"][error_type]["count"] += 1
        
        if error_msg:
            metrics["by_type"][error_type]["recent"].append({
                "time": time.time(),
                "message": error_msg
            })
            # Keep only last 10 error messages
            if len(metrics["by_type"][error_type]["recent"]) > 10:
                metrics["by_type"][error_type]["recent"].pop(0)
    
    def record_comparison(self, identical: bool, response_time_diff: float) -> None:
        """
        Record metrics for a comparison between blue and green responses.
        
        Args:
            identical: Whether the responses were identical
            response_time_diff: Difference in response time (green - blue) in seconds
        """
        metrics = self.overall_metrics["blue_green_comparison_metrics"]
        
        metrics["total_comparisons"] += 1
        if identical:
            metrics["identical_responses"] += 1
        else:
            metrics["different_responses"] += 1
        
        metrics["response_time_diffs"].append(response_time_diff)
        if len(metrics["response_time_diffs"]) > 100:
            metrics["response_time_diffs"].pop(0)  # Keep only last 100
        
        # Update Prometheus metrics if enabled
        if self.prometheus_enabled:
            result = "identical" if identical else "different"
            self.prom_comparison_counter.labels(result=result).inc()
            self.prom_response_diff.observe(response_time_diff)
    
    def record_custom_metric(
        self, 
        server_type: ServerType, 
        metric_name: str, 
        value: Any
    ) -> None:
        """
        Record a custom metric.
        
        Args:
            server_type: Type of server the metric is for
            metric_name: Name of the custom metric
            value: Value to record
        """
        metrics = self.metrics[server_type]["custom_metrics"]
        
        if metric_name not in metrics:
            metrics[metric_name] = []
        
        metrics[metric_name].append({
            "time": time.time(),
            "value": value
        })
        
        # Keep only last 100 values
        if len(metrics[metric_name]) > 100:
            metrics[metric_name].pop(0)
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get a summary of current metrics.
        
        Returns:
            Dict containing a summary of all metrics
        """
        blue_metrics = self.metrics[ServerType.BLUE]
        green_metrics = self.metrics[ServerType.GREEN]
        comparison_metrics = self.overall_metrics["blue_green_comparison_metrics"]
        
        # Calculate blue metrics
        blue_requests = max(1, blue_metrics["requests"]["total"])
        blue_success_rate = (blue_metrics["requests"]["successes"] / blue_requests) * 100
        blue_recent_times = blue_metrics["recent_response_times"]
        blue_avg_time = sum(blue_recent_times) / max(1, len(blue_recent_times))
        
        # Calculate green metrics
        green_requests = max(1, green_metrics["requests"]["total"])
        green_success_rate = (green_metrics["requests"]["successes"] / green_requests) * 100
        green_recent_times = green_metrics["recent_response_times"]
        green_avg_time = sum(green_recent_times) / max(1, len(green_recent_times))
        
        # Calculate comparison metrics
        total_comparisons = max(1, comparison_metrics["total_comparisons"])
        identical_rate = (comparison_metrics["identical_responses"] / total_comparisons) * 100
        
        # Create summary
        return {
            "overall": {
                "uptime": time.time() - self.overall_metrics["start_time"],
                "total_requests": self.overall_metrics["total_requests"]
            },
            "blue": {
                "requests": blue_metrics["requests"]["total"],
                "success_rate": blue_success_rate,
                "avg_response_time": blue_avg_time,
                "health": {
                    "status": blue_metrics["health_checks"]["last_status"],
                    "healthy_rate": (blue_metrics["health_checks"]["healthy"] / 
                                      max(1, blue_metrics["health_checks"]["total"])) * 100
                },
                "errors": blue_metrics["errors"]["total"]
            },
            "green": {
                "requests": green_metrics["requests"]["total"],
                "success_rate": green_success_rate,
                "avg_response_time": green_avg_time,
                "health": {
                    "status": green_metrics["health_checks"]["last_status"],
                    "healthy_rate": (green_metrics["health_checks"]["healthy"] / 
                                      max(1, green_metrics["health_checks"]["total"])) * 100
                },
                "errors": green_metrics["errors"]["total"]
            },
            "comparison": {
                "total_comparisons": comparison_metrics["total_comparisons"],
                "identical_response_rate": identical_rate,
                "avg_response_time_diff": sum(comparison_metrics["response_time_diffs"]) / 
                                          max(1, len(comparison_metrics["response_time_diffs"]))
            }
        }
    
    def get_detailed_metrics(self) -> Dict[str, Any]:
        """
        Get detailed metrics for all servers.
        
        Returns:
            Dict containing all collected metrics
        """
        return {
            "overall": self.overall_metrics,
            "blue": self.metrics[ServerType.BLUE],
            "green": self.metrics[ServerType.GREEN]
        }
    
    def reset_metrics(self) -> None:
        """Reset all metrics."""
        self.metrics = {
            ServerType.BLUE: self._init_server_metrics(),
            ServerType.GREEN: self._init_server_metrics()
        }
        
        self.overall_metrics = {
            "start_time": time.time(),
            "total_requests": 0,
            "blue_green_comparison_metrics": {
                "total_comparisons": 0,
                "identical_responses": 0,
                "different_responses": 0,
                "response_time_diffs": []
            }
        }
        
        logger.info("Metrics have been reset")