"""
Metrics Aggregator Module

Aggregates and processes metrics data from the data collector to provide
useful insights and analytics for the dashboard.
"""

import time
import statistics
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from collections import defaultdict, deque
from datetime import datetime, timedelta

from .config import DashboardConfig
from .data_collector import DataCollector, MetricSeries, DataPoint

logger = logging.getLogger(__name__)


@dataclass
class AggregatedMetric:
    """An aggregated metric with statistical summaries."""
    name: str
    current_value: float
    min_value: float
    max_value: float
    avg_value: float
    sum_value: float
    count: int
    trend: str  # "up", "down", "stable"
    change_rate: float  # rate of change per hour
    tags: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "current_value": self.current_value,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "avg_value": self.avg_value,
            "sum_value": self.sum_value,
            "count": self.count,
            "trend": self.trend,
            "change_rate": self.change_rate,
            "tags": self.tags
        }


@dataclass
class HealthStatus:
    """Health status information."""
    status: str  # "healthy", "warning", "critical"
    score: float  # 0-100
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status,
            "score": self.score,
            "issues": self.issues,
            "recommendations": self.recommendations
        }


@dataclass
class Alert:
    """Alert information."""
    id: str
    level: str  # "info", "warning", "critical"
    title: str
    message: str
    metric_name: str
    current_value: float
    threshold: float
    timestamp: float
    acknowledged: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "level": self.level,
            "title": self.title,
            "message": self.message,
            "metric_name": self.metric_name,
            "current_value": self.current_value,
            "threshold": self.threshold,
            "timestamp": self.timestamp,
            "acknowledged": self.acknowledged
        }


class MetricsAggregator:
    """
    Aggregates and analyzes metrics data to provide insights for the dashboard.
    
    This class processes raw metrics data from the DataCollector and provides:
    - Statistical summaries
    - Trend analysis
    - Health status assessment
    - Alert generation
    - Performance analytics
    """
    
    def __init__(self, config: DashboardConfig, data_collector: DataCollector):
        """Initialize the metrics aggregator."""
        self.config = config
        self.data_collector = data_collector
        
        # Aggregated metrics cache
        self.aggregated_metrics: Dict[str, AggregatedMetric] = {}
        
        # Health status
        self.health_status = HealthStatus(status="unknown", score=0)
        
        # Alerts
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        
        # Analysis window
        self.analysis_window_minutes = 30
        
        # Performance analytics
        self.performance_analytics: Dict[str, Any] = {}
        
        # Virtual filesystem analytics
        self.vfs_analytics: Dict[str, Any] = {}
    
    def update_aggregations(self) -> None:
        """Update all aggregated metrics and analytics."""
        try:
            logger.debug("Updating metric aggregations")
            
            # Get latest metrics from data collector
            metrics = self.data_collector.get_metrics()
            
            # Update aggregated metrics
            self._update_aggregated_metrics(metrics)
            
            # Update health status
            self._update_health_status()
            
            # Check for alerts
            self._check_alerts()
            
            # Update performance analytics
            self._update_performance_analytics(metrics)
            
            # Update VFS analytics
            self._update_vfs_analytics(metrics)
            
            logger.debug("Metric aggregations updated successfully")
            
        except Exception as e:
            logger.error(f"Failed to update aggregations: {e}")
    
    def _update_aggregated_metrics(self, metrics: Dict[str, MetricSeries]) -> None:
        """Update aggregated metrics with statistical summaries."""
        current_time = time.time()
        analysis_start_time = current_time - (self.analysis_window_minutes * 60)
        
        for metric_name, metric_series in metrics.items():
            try:
                # Get data points within analysis window
                recent_points = metric_series.get_range(analysis_start_time, current_time)
                
                if not recent_points:
                    continue
                
                # Extract values
                values = [point.value for point in recent_points if isinstance(point.value, (int, float))]
                
                if not values:
                    continue
                
                # Calculate statistics
                current_value = values[-1]
                min_value = min(values)
                max_value = max(values)
                avg_value = statistics.mean(values)
                sum_value = sum(values)
                count = len(values)
                
                # Calculate trend and change rate
                trend, change_rate = self._calculate_trend(values, len(recent_points))
                
                # Get tags from latest point
                tags = recent_points[-1].tags if recent_points else {}
                
                # Create aggregated metric
                self.aggregated_metrics[metric_name] = AggregatedMetric(
                    name=metric_name,
                    current_value=current_value,
                    min_value=min_value,
                    max_value=max_value,
                    avg_value=avg_value,
                    sum_value=sum_value,
                    count=count,
                    trend=trend,
                    change_rate=change_rate,
                    tags=tags
                )
                
            except Exception as e:
                logger.debug(f"Failed to aggregate metric {metric_name}: {e}")
    
    def _calculate_trend(self, values: List[float], point_count: int) -> Tuple[str, float]:
        """Calculate trend direction and change rate."""
        if len(values) < 2:
            return "stable", 0.0
        
        # Use linear regression to determine trend
        try:
            # Simple slope calculation
            x_values = list(range(len(values)))
            n = len(values)
            
            sum_x = sum(x_values)
            sum_y = sum(values)
            sum_xy = sum(x * y for x, y in zip(x_values, values))
            sum_x2 = sum(x * x for x in x_values)
            
            # Calculate slope
            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
            
            # Determine trend
            if abs(slope) < 0.01:  # Threshold for "stable"
                trend = "stable"
            elif slope > 0:
                trend = "up"
            else:
                trend = "down"
            
            # Calculate change rate per hour
            # Slope is change per data point, convert to change per hour
            points_per_hour = 3600 / (self.analysis_window_minutes * 60 / point_count)
            change_rate = slope * points_per_hour
            
            return trend, change_rate
            
        except (ZeroDivisionError, ValueError):
            return "stable", 0.0
    
    def _update_health_status(self) -> None:
        """Update overall health status based on metrics."""
        issues = []
        recommendations = []
        
        # Check CPU usage
        cpu_metric = self.aggregated_metrics.get("system_cpu_usage_percent")
        if cpu_metric:
            if cpu_metric.current_value > 90:
                issues.append("Very high CPU usage")
                recommendations.append("Check for CPU-intensive processes")
            elif cpu_metric.current_value > self.config.alert_thresholds.get("cpu_usage", 80):
                issues.append("High CPU usage")
        
        # Check memory usage
        memory_metric = self.aggregated_metrics.get("system_memory_usage_percent")
        if memory_metric:
            if memory_metric.current_value > 95:
                issues.append("Very high memory usage")
                recommendations.append("Free up memory or add more RAM")
            elif memory_metric.current_value > self.config.alert_thresholds.get("memory_usage", 90):
                issues.append("High memory usage")
        
        # Check disk usage
        disk_metric = self.aggregated_metrics.get("system_disk_usage_percent")
        if disk_metric:
            if disk_metric.current_value > 98:
                issues.append("Critical disk usage")
                recommendations.append("Free up disk space immediately")
            elif disk_metric.current_value > self.config.alert_thresholds.get("disk_usage", 95):
                issues.append("High disk usage")
                recommendations.append("Clean up old files or add more storage")
        
        # Check MCP server health
        mcp_health_metric = self.aggregated_metrics.get("mcp_server_health_status")
        if mcp_health_metric and mcp_health_metric.current_value < 1:
            issues.append("MCP server is not healthy")
            recommendations.append("Check MCP server logs and configuration")
        
        # Check error rates
        error_metrics = [
            name for name in self.aggregated_metrics.keys()
            if "error" in name.lower() or "failure" in name.lower()
        ]
        
        for error_metric_name in error_metrics:
            error_metric = self.aggregated_metrics[error_metric_name]
            if error_metric.trend == "up" and error_metric.current_value > 0:
                issues.append(f"Increasing error rate in {error_metric_name}")
                recommendations.append("Investigate error causes and implement fixes")
        
        # Calculate health score
        score = 100.0
        
        # Reduce score based on issues
        critical_issues = len([issue for issue in issues if "critical" in issue.lower() or "very high" in issue.lower()])
        warning_issues = len(issues) - critical_issues
        
        score -= critical_issues * 30  # -30 points per critical issue
        score -= warning_issues * 15   # -15 points per warning issue
        
        score = max(0, min(100, score))
        
        # Determine status
        if score >= 90:
            status = "healthy"
        elif score >= 70:
            status = "warning" 
        else:
            status = "critical"
        
        # Update health status
        self.health_status = HealthStatus(
            status=status,
            score=score,
            issues=issues,
            recommendations=recommendations
        )
    
    def _check_alerts(self) -> None:
        """Check for alert conditions and generate alerts."""
        current_time = time.time()
        
        # Check threshold-based alerts
        for metric_name, metric in self.aggregated_metrics.items():
            alert_id = f"threshold_{metric_name}"
            
            # CPU usage alert
            if metric_name == "system_cpu_usage_percent":
                threshold = self.config.alert_thresholds.get("cpu_usage", 80)
                if metric.current_value > threshold:
                    self._create_alert(
                        alert_id,
                        "warning" if metric.current_value < 95 else "critical",
                        "High CPU Usage",
                        f"CPU usage is {metric.current_value:.1f}% (threshold: {threshold}%)",
                        metric_name,
                        metric.current_value,
                        threshold,
                        current_time
                    )
                else:
                    self._clear_alert(alert_id)
            
            # Memory usage alert
            elif metric_name == "system_memory_usage_percent":
                threshold = self.config.alert_thresholds.get("memory_usage", 90)
                if metric.current_value > threshold:
                    self._create_alert(
                        alert_id,
                        "warning" if metric.current_value < 98 else "critical",
                        "High Memory Usage",
                        f"Memory usage is {metric.current_value:.1f}% (threshold: {threshold}%)",
                        metric_name,
                        metric.current_value,
                        threshold,
                        current_time
                    )
                else:
                    self._clear_alert(alert_id)
            
            # Disk usage alert
            elif metric_name == "system_disk_usage_percent":
                threshold = self.config.alert_thresholds.get("disk_usage", 95)
                if metric.current_value > threshold:
                    self._create_alert(
                        alert_id,
                        "critical",
                        "High Disk Usage",
                        f"Disk usage is {metric.current_value:.1f}% (threshold: {threshold}%)",
                        metric_name,
                        metric.current_value,
                        threshold,
                        current_time
                    )
                else:
                    self._clear_alert(alert_id)
            
            # Error rate alerts
            elif "error" in metric_name.lower() or "failure" in metric_name.lower():
                threshold = self.config.alert_thresholds.get("error_rate", 5.0)
                if metric.current_value > threshold and metric.trend == "up":
                    self._create_alert(
                        alert_id,
                        "warning",
                        "Increasing Error Rate",
                        f"Error rate for {metric_name} is {metric.current_value:.1f} and increasing",
                        metric_name,
                        metric.current_value,
                        threshold,
                        current_time
                    )
                else:
                    self._clear_alert(alert_id)
        
        # Check response time alerts
        response_time_metrics = [
            name for name in self.aggregated_metrics.keys()
            if "duration" in name.lower() or "latency" in name.lower() or "time" in name.lower()
        ]
        
        for metric_name in response_time_metrics:
            metric = self.aggregated_metrics[metric_name]
            alert_id = f"response_time_{metric_name}"
            threshold = self.config.alert_thresholds.get("response_time", 5000.0)  # 5 seconds
            
            # Convert to milliseconds if needed
            value_ms = metric.current_value * 1000 if metric.current_value < 10 else metric.current_value
            
            if value_ms > threshold:
                self._create_alert(
                    alert_id,
                    "warning",
                    "Slow Response Time",
                    f"Response time for {metric_name} is {value_ms:.1f}ms (threshold: {threshold}ms)",
                    metric_name,
                    value_ms,
                    threshold,
                    current_time
                )
            else:
                self._clear_alert(alert_id)
    
    def _create_alert(self, alert_id: str, level: str, title: str, message: str,
                     metric_name: str, current_value: float, threshold: float, timestamp: float) -> None:
        """Create or update an alert."""
        alert = Alert(
            id=alert_id,
            level=level,
            title=title,
            message=message,
            metric_name=metric_name,
            current_value=current_value,
            threshold=threshold,
            timestamp=timestamp
        )
        
        # Check if this is a new alert
        if alert_id not in self.active_alerts:
            logger.info(f"New alert: {title} - {message}")
            # Add to history
            self.alert_history.append(alert)
            
            # Limit history size
            if len(self.alert_history) > 100:
                self.alert_history = self.alert_history[-100:]
        
        # Update active alerts
        self.active_alerts[alert_id] = alert
    
    def _clear_alert(self, alert_id: str) -> None:
        """Clear an active alert."""
        if alert_id in self.active_alerts:
            logger.info(f"Cleared alert: {alert_id}")
            del self.active_alerts[alert_id]
    
    def _update_performance_analytics(self, metrics: Dict[str, MetricSeries]) -> None:
        """Update performance analytics."""
        analytics = {
            "mcp_server": {},
            "ipfs_kit": {},
            "system": {}
        }
        
        # MCP server analytics
        mcp_metrics = {name: metric for name, metric in self.aggregated_metrics.items() if name.startswith("mcp_")}
        
        # Total operations across all backends
        total_operations = sum(
            metric.current_value for name, metric in mcp_metrics.items()
            if "operations_total" in name
        )
        analytics["mcp_server"]["total_operations"] = total_operations
        
        # Average response time
        response_times = [
            metric.current_value for name, metric in mcp_metrics.items()
            if "duration_seconds" in name
        ]
        if response_times:
            analytics["mcp_server"]["avg_response_time"] = statistics.mean(response_times)
        
        # Success rate
        success_rates = [
            metric.current_value for name, metric in mcp_metrics.items()
            if "success_rate" in name
        ]
        if success_rates:
            analytics["mcp_server"]["avg_success_rate"] = statistics.mean(success_rates)
        
        # Backend performance
        backend_performance = {}
        for name, metric in mcp_metrics.items():
            if "backend" in metric.tags:
                backend = metric.tags["backend"]
                if backend not in backend_performance:
                    backend_performance[backend] = {}
                
                if "operations_total" in name:
                    backend_performance[backend]["operations"] = metric.current_value
                elif "duration_seconds" in name:
                    backend_performance[backend]["avg_response_time"] = metric.current_value
                elif "success_rate" in name:
                    backend_performance[backend]["success_rate"] = metric.current_value
        
        analytics["mcp_server"]["backend_performance"] = backend_performance
        
        # IPFS Kit analytics
        ipfs_metrics = {name: metric for name, metric in self.aggregated_metrics.items() if name.startswith("ipfs_")}
        
        # Cache performance
        cache_hit_ratio = ipfs_metrics.get("ipfs_cache_hit_ratio")
        if cache_hit_ratio:
            analytics["ipfs_kit"]["cache_hit_ratio"] = cache_hit_ratio.current_value
        
        # System analytics
        system_metrics = {name: metric for name, metric in self.aggregated_metrics.items() if name.startswith("system_")}
        
        for name, metric in system_metrics.items():
            if "cpu" in name:
                analytics["system"]["cpu_usage"] = metric.current_value
            elif "memory" in name and "percent" in name:
                analytics["system"]["memory_usage"] = metric.current_value
            elif "disk" in name and "percent" in name:
                analytics["system"]["disk_usage"] = metric.current_value
        
        self.performance_analytics = analytics
    
    def _update_vfs_analytics(self, metrics: Dict[str, MetricSeries]) -> None:
        """Update virtual filesystem analytics."""
        vfs_analytics = {
            "total_operations": 0,
            "read_operations": 0,
            "write_operations": 0,
            "list_operations": 0,
            "avg_response_time": 0,
            "error_rate": 0,
            "cache_effectiveness": 0
        }
        
        # Collect VFS-related metrics
        vfs_metrics = {
            name: metric for name, metric in self.aggregated_metrics.items()
            if "vfs" in name.lower() or "filesystem" in name.lower()
        }
        
        # Count operations by type
        for name, metric in vfs_metrics.items():
            if "operations_total" in name:
                operation_type = metric.tags.get("operation", "unknown")
                vfs_analytics["total_operations"] += metric.current_value
                
                if operation_type == "read":
                    vfs_analytics["read_operations"] += metric.current_value
                elif operation_type == "write":
                    vfs_analytics["write_operations"] += metric.current_value
                elif operation_type == "list":
                    vfs_analytics["list_operations"] += metric.current_value
        
        # Calculate ratios
        total_ops = vfs_analytics["total_operations"]
        if total_ops > 0:
            vfs_analytics["read_ratio"] = vfs_analytics["read_operations"] / total_ops
            vfs_analytics["write_ratio"] = vfs_analytics["write_operations"] / total_ops
            vfs_analytics["list_ratio"] = vfs_analytics["list_operations"] / total_ops
        
        # Cache effectiveness from IPFS metrics
        cache_hit_ratio = self.aggregated_metrics.get("ipfs_cache_hit_ratio")
        if cache_hit_ratio:
            vfs_analytics["cache_effectiveness"] = cache_hit_ratio.current_value
        
        self.vfs_analytics = vfs_analytics
    
    def get_dashboard_summary(self) -> Dict[str, Any]:
        """Get a summary for the dashboard."""
        return {
            "health_status": self.health_status.to_dict(),
            "active_alerts": [alert.to_dict() for alert in self.active_alerts.values()],
            "performance_analytics": self.performance_analytics,
            "vfs_analytics": self.vfs_analytics,
            "metrics_summary": {
                "total_metrics": len(self.aggregated_metrics),
                "metrics_with_issues": len([
                    m for m in self.aggregated_metrics.values()
                    if m.trend == "down" and "error" not in m.name.lower()
                ]),
                "trending_up": len([
                    m for m in self.aggregated_metrics.values() if m.trend == "up"
                ]),
                "trending_down": len([
                    m for m in self.aggregated_metrics.values() if m.trend == "down"
                ])
            }
        }
    
    def get_aggregated_metrics(self) -> Dict[str, AggregatedMetric]:
        """Get all aggregated metrics."""
        return self.aggregated_metrics.copy()
    
    def get_alerts(self) -> Tuple[List[Alert], List[Alert]]:
        """Get active alerts and alert history."""
        return list(self.active_alerts.values()), self.alert_history.copy()
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert."""
        if alert_id in self.active_alerts:
            self.active_alerts[alert_id].acknowledged = True
            logger.info(f"Alert acknowledged: {alert_id}")
            return True
        return False
    
    def get_health_status(self) -> HealthStatus:
        """Get current health status."""
        return self.health_status
    
    def get_performance_analytics(self) -> Dict[str, Any]:
        """Get performance analytics."""
        return self.performance_analytics.copy()
    
    def get_vfs_analytics(self) -> Dict[str, Any]:
        """Get virtual filesystem analytics."""
        return self.vfs_analytics.copy()
