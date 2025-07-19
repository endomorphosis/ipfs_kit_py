"""
Data Collector Module

Collects data from various sources including:
- IPFS Kit Observability API (combining MCP server metrics/status and IPFS metrics)
- System telemetry
- Virtual filesystem statistics
"""

import asyncio
import time
import logging
import aiohttp
import psutil
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .config import DashboardConfig

logger = logging.getLogger(__name__)


@dataclass
class DataPoint:
    """A single data point with timestamp and value."""
    timestamp: float
    value: Any
    tags: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp,
            "value": self.value,
            "tags": self.tags
        }


@dataclass
class MetricSeries:
    """A series of metric data points."""
    name: str
    data_points: List[DataPoint] = field(default_factory=list)
    unit: str = ""
    description: str = ""
    
    def add_point(self, value: Any, tags: Optional[Dict[str, str]] = None) -> None:
        """Add a data point."""
        self.data_points.append(DataPoint(
            timestamp=time.time(),
            value=value,
            tags=tags or {}
        ))
    
    def get_latest(self) -> Optional[DataPoint]:
        """Get the latest data point."""
        return self.data_points[-1] if self.data_points else None
    
    def get_range(self, start_time: float, end_time: float) -> List[DataPoint]:
        """Get data points within a time range."""
        return [
            point for point in self.data_points
            if start_time <= point.timestamp <= end_time
        ]
    
    def cleanup_old_data(self, max_age_hours: int) -> None:
        """Remove data points older than max_age_hours."""
        cutoff_time = time.time() - (max_age_hours * 3600)
        self.data_points = [
            point for point in self.data_points
            if point.timestamp >= cutoff_time
        ]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "data_points": [point.to_dict() for point in self.data_points],
            "unit": self.unit,
            "description": self.description
        }


class DataCollector:
    """
    Collects data from various sources for the dashboard.
    
    This class is responsible for gathering metrics and telemetry data
    from MCP servers, IPFS Kit instances, and system resources.
    """
    
    def __init__(self, config: DashboardConfig):
        """Initialize the data collector."""
        self.config = config
        self.metrics: Dict[str, MetricSeries] = {}
        self.is_running = False
        self.collection_task = None
        
        # HTTP session for collecting remote data
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Collection intervals
        self.observability_collection_interval = 15  # seconds
        self.system_collection_interval = 5  # seconds
        self.vfs_collection_interval = 5  # seconds
        
        # Error tracking
        self.error_count = 0
        self.last_error_time = 0
        
        # VFS Analytics integration
        try:
            from .vfs_analytics import vfs_monitor
            self.vfs_monitor = vfs_monitor
            self.has_vfs_analytics = True
            logger.info("VFS analytics integrated successfully")
        except ImportError as e:
            logger.warning(f"VFS analytics not available: {e}")
            self.vfs_monitor = None
            self.has_vfs_analytics = False
        
    async def start(self) -> None:
        """Start the data collection process."""
        if self.is_running:
            logger.warning("Data collector is already running")
            return
        
        logger.info("Starting data collector")
        self.is_running = True
        
        # Create HTTP session
        timeout = aiohttp.ClientTimeout(total=30)
        self.session = aiohttp.ClientSession(timeout=timeout)
        
        # Start VFS monitoring if available
        if self.has_vfs_analytics and self.vfs_monitor:
            try:
                await self.vfs_monitor.start_monitoring()
                logger.info("VFS analytics monitoring started")
            except Exception as e:
                logger.error(f"Failed to start VFS monitoring: {e}")
        
        # Start collection task
        self.collection_task = asyncio.create_task(self._collection_loop())
        
    async def stop(self) -> None:
        """Stop the data collection process."""
        if not self.is_running:
            return
        
        logger.info("Stopping data collector")
        self.is_running = False
        
        # Stop VFS monitoring
        if self.has_vfs_analytics and self.vfs_monitor:
            try:
                await self.vfs_monitor.stop_monitoring()
                logger.info("VFS analytics monitoring stopped")
            except Exception as e:
                logger.error(f"Failed to stop VFS monitoring: {e}")
        
        # Cancel collection task
        if self.collection_task:
            self.collection_task.cancel()
            try:
                await self.collection_task
            except asyncio.CancelledError:
                pass
        
        # Close HTTP session
        if self.session:
            await self.session.close()
            self.session = None
        
    async def _collection_loop(self) -> None:
        """Main collection loop."""
        last_observability_collection = 0
        last_system_collection = 0
        last_vfs_collection = 0
        
        try:
            while self.is_running:
                current_time = time.time()
                
                # Collect data from IPFS Kit Observability API
                if self.config.ipfs_kit_enabled and current_time - last_observability_collection >= self.observability_collection_interval:
                    try:
                        await self._collect_observability_data()
                        last_observability_collection = current_time
                    except Exception as e:
                        logger.error(f"Error collecting IPFS Kit observability data: {e}")
                        self._track_error()
                
                # Collect system data
                if current_time - last_system_collection >= self.system_collection_interval:
                    try:
                        await self._collect_system_data()
                        last_system_collection = current_time
                    except Exception as e:
                        logger.error(f"Error collecting system data: {e}")
                        self._track_error()
                
                # Collect VFS analytics data
                if self.has_vfs_analytics and self.vfs_monitor and current_time - last_vfs_collection >= self.vfs_collection_interval:
                    try:
                        await self._collect_vfs_analytics_data()
                        last_vfs_collection = current_time
                    except Exception as e:
                        logger.error(f"Error collecting VFS analytics data: {e}")
                        self._track_error()
                
                # Cleanup old data
                await self._cleanup_old_data()
                
                # Sleep for a short interval
                await asyncio.sleep(1)
                
        except asyncio.CancelledError:
            logger.info("Data collection cancelled")
        except Exception as e:
            logger.exception(f"Fatal error in data collection loop: {e}")
    
    def _track_error(self) -> None:
        """Track collection errors."""
        self.error_count += 1
        self.last_error_time = time.time()
        
        # Add error metric
        self._add_metric("collector_errors_total", self.error_count)
    
    async def _collect_observability_data(self) -> None:
        """Collect data from IPFS Kit Observability API."""
        if not self.session:
            return
        
        base_url = self.config.get_mcp_server_url() # Assuming MCP server URL is the base for observability API
        
        # Collect health data
        try:
            health_url = f"{base_url}/api/v0/observability/health"
            async with self.session.get(health_url) as response:
                if response.status == 200:
                    health_data = await response.json()
                    self._process_observability_health_data(health_data)
                else:
                    logger.warning(f"Observability health endpoint returned {response.status}")
                    self._add_metric("observability_health_status", 0, {"status": "unhealthy"})
        except Exception as e:
            logger.debug(f"Failed to collect observability health data: {e}")
            self._add_metric("observability_health_status", 0, {"status": "error"})
        
        # Collect metrics data
        try:
            metrics_url = f"{base_url}/api/v0/observability/metrics"
            async with self.session.get(metrics_url) as response:
                if response.status == 200:
                    metrics_data = await response.json()
                    self._process_observability_metrics_data(metrics_data)
                else:
                    logger.warning(f"Observability metrics endpoint returned {response.status}")
        except Exception as e:
            logger.debug(f"Failed to collect observability metrics data: {e}")
            
    def _process_observability_health_data(self, health_data: Dict[str, Any]) -> None:
        """Process observability health data."""
        status = health_data.get("status", "unknown")
        health_value = 1 if status == "healthy" else 0
        self._add_metric("observability_overall_health_status", health_value, {"status": status})
        
        components = health_data.get("components", {})
        for component, component_data in components.items():
            component_status = component_data.get("status", "unknown")
            component_value = 1 if component_status == "healthy" else 0
            self._add_metric(
                f"observability_component_health_status",
                component_value,
                {"component": component, "status": component_status}
            )
        
        uptime = health_data.get("uptime", 0)
        self._add_metric("observability_uptime_seconds", uptime)
        
        timestamp = health_data.get("timestamp", time.time())
        self._add_metric("observability_last_check", timestamp)

    def _process_observability_metrics_data(self, metrics_data: Dict[str, Any]) -> None:
        """Process observability metrics data."""
        # Example: Process performance metrics
        performance_metrics = metrics_data.get("performance_metrics", {})
        for category, metrics in performance_metrics.items():
            for metric_name, value in metrics.items():
                self._add_metric(f"observability_perf_{category}_{metric_name}", value)

        # Example: Process resource metrics
        resource_metrics = metrics_data.get("resource_metrics", {})
        for resource_type, metrics in resource_metrics.items():
            for metric_name, value in metrics.items():
                self._add_metric(f"observability_resource_{resource_type}_{metric_name}", value)
        
        # Example: Process VFS specific metrics if they are part of the observability API
        vfs_metrics = metrics_data.get("vfs_metrics", {})
        if vfs_metrics:
            for metric_name, value in vfs_metrics.items():
                self._add_metric(f"observability_vfs_{metric_name}", value)
    
    async def _collect_system_data(self) -> None:
        """Collect system resource data."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=None)
            self._add_metric("system_cpu_usage_percent", cpu_percent)
            
            # Memory usage
            memory = psutil.virtual_memory()
            self._add_metric("system_memory_usage_percent", memory.percent)
            self._add_metric("system_memory_used_bytes", memory.used)
            self._add_metric("system_memory_available_bytes", memory.available)
            self._add_metric("system_memory_total_bytes", memory.total)
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            self._add_metric("system_disk_usage_percent", disk_percent)
            self._add_metric("system_disk_used_bytes", disk.used)
            self._add_metric("system_disk_free_bytes", disk.free)
            self._add_metric("system_disk_total_bytes", disk.total)
            
            # Network I/O
            network = psutil.net_io_counters()
            self._add_metric("system_network_bytes_sent", network.bytes_sent)
            self._add_metric("system_network_bytes_recv", network.bytes_recv)
            
            # Process information
            process_count = len(psutil.pids())
            self._add_metric("system_processes_total", process_count)
            
            # Load average (Unix only)
            try:
                load_avg = psutil.getloadavg()
                self._add_metric("system_load_average_1m", load_avg[0])
                self._add_metric("system_load_average_5m", load_avg[1])
                self._add_metric("system_load_average_15m", load_avg[2])
            except AttributeError:
                # getloadavg not available on Windows
                pass
            
        except Exception as e:
            logger.error(f"Failed to collect system data: {e}")
    
    async def _collect_vfs_analytics_data(self) -> None:
        """Collect VFS analytics data."""
        if not self.vfs_monitor:
            return
        
        try:
            # Get comprehensive analytics
            analytics = self.vfs_monitor.get_analytics_summary()
            
            # Process overall health score
            overall_health = analytics.get('overall_health', {})
            health_score = overall_health.get('score', 0)
            health_status = overall_health.get('status', 'unknown')
            
            self._add_metric("vfs_health_score", health_score)
            self._add_metric("vfs_health_status", 1 if health_status == 'healthy' else 0, 
                           {"status": health_status})
            
            # Process realtime metrics
            realtime = analytics.get('realtime_metrics', {})
            if realtime:
                self._add_metric("vfs_operations_per_second", realtime.get('operations_per_second', 0))
                self._add_metric("vfs_bytes_per_second", realtime.get('bytes_per_second', 0))
                self._add_metric("vfs_error_rate", realtime.get('error_rate', 0))
                self._add_metric("vfs_total_operations", realtime.get('total_operations', 0))
                self._add_metric("vfs_total_bytes", realtime.get('total_bytes', 0))
                self._add_metric("vfs_total_errors", realtime.get('total_errors', 0))
            
            # Process bandwidth analysis
            bandwidth = analytics.get('bandwidth_analysis', {})
            if bandwidth and 'interfaces' in bandwidth:
                self._add_metric("vfs_total_bandwidth_in_bps", bandwidth.get('total_average_in_bps', 0))
                self._add_metric("vfs_total_bandwidth_out_bps", bandwidth.get('total_average_out_bps', 0))
                
                for interface, stats in bandwidth['interfaces'].items():
                    self._add_metric("vfs_interface_bandwidth_in_bps", 
                                   stats.get('average_in_bps', 0), {"interface": interface})
                    self._add_metric("vfs_interface_bandwidth_out_bps", 
                                   stats.get('average_out_bps', 0), {"interface": interface})
                    self._add_metric("vfs_interface_peak_in_bps", 
                                   stats.get('peak_in_bps', 0), {"interface": interface})
                    self._add_metric("vfs_interface_peak_out_bps", 
                                   stats.get('peak_out_bps', 0), {"interface": interface})
            
            # Process operation analysis
            operations = analytics.get('operation_analysis', {})
            if operations and 'operations_by_type' in operations:
                self._add_metric("vfs_total_analyzed_operations", operations.get('total_operations', 0))
                
                for op_key, op_stats in operations['operations_by_type'].items():
                    operation, backend = op_key.split(':') if ':' in op_key else (op_key, 'unknown')
                    tags = {"operation": operation, "backend": backend}
                    
                    self._add_metric("vfs_operation_count", op_stats.get('total_operations', 0), tags)
                    self._add_metric("vfs_operation_success_rate", op_stats.get('success_rate', 0), tags)
                    self._add_metric("vfs_operation_error_rate", op_stats.get('error_rate', 0), tags)
                    self._add_metric("vfs_operation_avg_duration_ms", op_stats.get('average_duration_ms', 0), tags)
                    self._add_metric("vfs_operation_avg_size_bytes", op_stats.get('average_size_bytes', 0), tags)
                    self._add_metric("vfs_operation_ops_per_minute", op_stats.get('operations_per_minute', 0), tags)
            
            # Process replication health
            replication = analytics.get('replication_health', {})
            if replication and 'current_status' in replication:
                status = replication['current_status']
                self._add_metric("vfs_replication_total_replicas", status.get('total_replicas', 0))
                self._add_metric("vfs_replication_healthy_replicas", status.get('healthy_replicas', 0))
                self._add_metric("vfs_replication_unhealthy_replicas", status.get('unhealthy_replicas', 0))
                self._add_metric("vfs_replication_health_percentage", status.get('health_percentage', 0))
                self._add_metric("vfs_replication_sync_lag_seconds", status.get('sync_lag_seconds', 0))
                self._add_metric("vfs_replication_pending_operations", status.get('pending_operations', 0))
                self._add_metric("vfs_replication_failed_operations", status.get('failed_operations', 0))
            
            # Process cache analysis
            cache = analytics.get('cache_analysis', {})
            if cache and 'current_metrics' in cache:
                metrics = cache['current_metrics']
                self._add_metric("vfs_cache_hit_rate", metrics.get('hit_rate', 0))
                self._add_metric("vfs_cache_miss_rate", metrics.get('miss_rate', 0))
                self._add_metric("vfs_cache_eviction_rate", metrics.get('eviction_rate', 0))
                self._add_metric("vfs_cache_size_bytes", metrics.get('size_bytes', 0))
                self._add_metric("vfs_cache_max_size_bytes", metrics.get('max_size_bytes', 0))
                self._add_metric("vfs_cache_utilization", metrics.get('utilization', 0))
                self._add_metric("vfs_cache_avg_lookup_time_ms", metrics.get('avg_lookup_time_ms', 0))
            
            # Process backend health
            backend_health = analytics.get('backend_health', {})
            if backend_health and 'backends' in backend_health::
                summary = backend_health.get('summary', {})
                self._add_metric("vfs_backend_total_count", summary.get('total_backends', 0))
                self._add_metric("vfs_backend_healthy_count", summary.get('healthy_backends', 0))
                self._add_metric("vfs_backend_unhealthy_count", summary.get('unhealthy_backends', 0))
                self._add_metric("vfs_backend_health_percentage", summary.get('health_percentage', 0))
                
                for backend_name, backend_status in backend_health['backends'].items():
                    tags = {"backend": backend_name}
                    self._add_metric("vfs_backend_healthy", 1 if backend_status.get('healthy', False) else 0, tags)
                    self._add_metric("vfs_backend_last_check_age_seconds", 
                                   backend_status.get('last_check_age_seconds', 0), tags)
                    self._add_metric("vfs_backend_is_stale", 1 if backend_status.get('is_stale', False) else 0, tags)
                    
                    if backend_status.get('average_latency_ms') is not None:
                        self._add_metric("vfs_backend_avg_latency_ms", 
                                       backend_status['average_latency_ms'], tags)
                    if backend_status.get('p95_latency_ms') is not None:
                        self._add_metric("vfs_backend_p95_latency_ms", 
                                       backend_status['p95_latency_ms'], tags)
            
            # Process alerts
            alerts = analytics.get('alerts', [])
            self._add_metric("vfs_active_alerts_total", len(alerts))
            
            # Count alerts by severity
            alert_counts = {'critical': 0, 'warning': 0, 'info': 0}
            for alert in alerts:
                severity = alert.get('severity', 'info')
                if severity in alert_counts:
                    alert_counts[severity] += 1
            
            for severity, count in alert_counts.items():
                self._add_metric("vfs_alerts_by_severity", count, {"severity": severity})
                
        except Exception as e:
            logger.error(f"Failed to collect VFS analytics data: {e}")
    
    def _add_metric(self, name: str, value: Any, tags: Optional[Dict[str, str]] = None) -> None:
        """Add a metric data point."""
        if name not in self.metrics:
            self.metrics[name] = MetricSeries(name=name)
        
        self.metrics[name].add_point(value, tags)
        
        # Limit the number of data points to prevent memory issues
        max_points = self.config.max_data_points
        if len(self.metrics[name].data_points) > max_points:
            # Remove oldest points
            self.metrics[name].data_points = self.metrics[name].data_points[-max_points:]
    
    async def _cleanup_old_data(self) -> None:
        """Clean up old data points."""
        for metric in self.metrics.values():
            metric.cleanup_old_data(self.config.data_retention_hours)
    
    def get_metrics(self) -> Dict[str, MetricSeries]:
        """Get all collected metrics."""
        return self.metrics.copy()
    
    def get_metric(self, name: str) -> Optional[MetricSeries]:
        """Get a specific metric by name."""
        return self.metrics.get(name)
    
    def get_latest_values(self) -> Dict[str, Any]:
        """Get the latest values for all metrics."""
        latest = {}
        for name, metric in self.metrics.items():
            latest_point = metric.get_latest()
            if latest_point:
                latest[name] = {
                    "value": latest_point.value,
                    "timestamp": latest_point.timestamp,
                    "tags": latest_point.tags
                }
        return latest
    
    def get_metric_summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics."""
        return {
            "total_metrics": len(self.metrics),
            "total_data_points": sum(len(metric.data_points) for metric in self.metrics.values()),
            "collection_errors": self.error_count,
            "last_error_time": self.last_error_time,
            "is_running": self.is_running,
            "metrics_list": list(self.metrics.keys())
        }
    
    async def get_vfs_deep_insights(self) -> Dict[str, Any]:
        """Get comprehensive VFS insights and analysis."""
        if not self.has_vfs_analytics:
            return {
                'available': False,
                'error': 'VFS analytics not available'
            }
        
        if not self.vfs_monitor: # Added check for vfs_monitor
            return {
                'available': False,
                'error': 'VFS monitor not initialized'
            }

        try:
            # Get comprehensive analytics from VFS monitor
            analytics = self.vfs_monitor.get_analytics_summary()
            
            # Get additional detailed analyses
            bandwidth_analysis = self.vfs_monitor.performance_monitor.get_bandwidth_analysis(60)
            operation_analysis = self.vfs_monitor.performance_monitor.get_operation_analysis(60)
            realtime_metrics = self.vfs_monitor.performance_monitor.get_realtime_metrics()
            replication_health = self.vfs_monitor.performance_monitor.get_replication_health()
            cache_analysis = self.vfs_monitor.performance_monitor.get_cache_analysis()
            backend_health = self.vfs_monitor.performance_monitor.get_backend_health_status()
            
            # Generate performance insights
            insights = self._generate_vfs_performance_insights(analytics)
            recommendations = self._generate_vfs_optimization_recommendations(analytics)
            
            # Get historical trends from collected metrics
            trends = self._analyze_vfs_trends()
            
            return {
                'available': True,
                'timestamp': time.time(),
                'comprehensive_report': analytics,
                'detailed_analyses': {
                    'bandwidth': bandwidth_analysis,
                    'operations': operation_analysis,
                    'realtime': realtime_metrics,
                    'replication': replication_health,
                    'cache': cache_analysis,
                    'backends': backend_health
                },
                'insights': insights,
                'recommendations': recommendations,
                'trends': trends,
                'health_summary': self._generate_vfs_health_summary(analytics)
            }
            
        except Exception as e:
            logger.error(f"Error getting VFS deep insights: {e}")
            return {
                'available': False,
                'error': str(e)
            }
    
    def _generate_vfs_performance_insights(self, analytics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate performance insights from VFS analytics."""
        insights = []
        
        try:
            # Analyze error patterns
            realtime = analytics.get('realtime_metrics', {})
            error_rate = realtime.get('error_rate', 0)
            ops_per_sec = realtime.get('operations_per_second', 0)
            
            if error_rate > 0.05:  # 5% error rate
                insights.append({
                    'type': 'performance_issue',
                    'severity': 'high' if error_rate > 0.2 else 'medium',
                    'category': 'error_rate',
                    'title': 'High VFS Error Rate',
                    'description': f'VFS operations are failing at {error_rate:.1%} rate',
                    'impact': 'Degraded user experience and potential data access issues',
                    'metrics': {'error_rate': error_rate, 'ops_per_second': ops_per_sec}
                })
            
            # Analyze throughput patterns
            if ops_per_sec > 100:
                insights.append({
                    'type': 'performance_pattern',
                    'severity': 'info',
                    'category': 'high_throughput',
                    'title': 'High VFS Throughput',
                    'description': f'VFS is processing {ops_per_sec:.1f} operations per second',
                    'impact': 'System is under heavy load - monitor for bottlenecks',
                    'metrics': {'operations_per_second': ops_per_sec}
                })
            elif ops_per_sec < 0.1 and self.is_running:
                insights.append({
                    'type': 'performance_issue',
                    'severity': 'medium',
                    'category': 'low_activity',
                    'title': 'Low VFS Activity',
                    'description': f'VFS activity is very low ({ops_per_sec:.1f} ops/sec)',
                    'impact': 'May indicate connectivity issues or system underutilization',
                    'metrics': {'operations_per_second': ops_per_sec}
                })
            
            # Analyze bandwidth patterns
            bandwidth = analytics.get('bandwidth_analysis', {})
            if bandwidth and 'total_average_bps' in bandwidth:
                total_bps = bandwidth['total_average_bps']
                if total_bps > 50 * 1024 * 1024:  # 50MB/s
                    insights.append({
                        'type': 'resource_usage',
                        'severity': 'medium',
                        'category': 'high_bandwidth',
                        'title': 'High Bandwidth Usage',
                        'description': f'VFS bandwidth usage: {total_bps / (1024*1024):.1f} MB/s',
                        'impact': 'High network utilization - may affect other services',
                        'metrics': {'bandwidth_mbps': total_bps / (1024*1024)}
                    })
            
            # Analyze cache performance
            cache = analytics.get('cache_analysis', {})
            if cache and 'current_metrics' in cache:
                hit_rate = cache['current_metrics'].get('hit_rate', 0)
                utilization = cache['current_metrics'].get('utilization', 0)
                
                if hit_rate < 0.7:  # 70% hit rate
                    insights.append({
                        'type': 'performance_issue',
                        'severity': 'medium',
                        'category': 'cache_efficiency',
                        'title': 'Low Cache Hit Rate',
                        'description': f'VFS cache hit rate is {hit_rate:.1%}',
                        'impact': 'Increased latency and backend load',
                        'metrics': {'cache_hit_rate': hit_rate, 'cache_utilization': utilization}
                    })
                
                if utilization > 0.9:  # 90% cache utilization
                    insights.append({
                        'type': 'resource_constraint',
                        'severity': 'warning',
                        'category': 'cache_pressure',
                        'title': 'High Cache Memory Pressure',
                        'description': f'VFS cache utilization is {utilization:.1%}',
                        'impact': 'Cache evictions may increase, reducing efficiency',
                        'metrics': {'cache_utilization': utilization}
                    })
            
            # Analyze replication health
            replication = analytics.get('replication_health', {})
            if replication and 'current_status' in replication:
                health_pct = replication['current_status'].get('health_percentage', 100)
                sync_lag = replication['current_status'].get('sync_lag_seconds', 0)
                
                if health_pct < 80:  # 80% healthy replicas
                    insights.append({
                        'type': 'availability_issue',
                        'severity': 'high' if health_pct < 50 else 'medium',
                        'category': 'replication_health',
                        'title': 'Replication Health Issues',
                        'description': f'Only {health_pct:.1f}% of replicas are healthy',
                        'impact': 'Reduced data redundancy and potential data loss risk',
                        'metrics': {'replication_health_percentage': health_pct}
                    })
                
                if sync_lag > 300:  # 5 minutes
                    insights.append({
                        'type': 'performance_issue',
                        'severity': 'medium',
                        'category': 'sync_lag',
                        'title': 'High Replication Sync Lag',
                        'description': f'Replication sync lag is {sync_lag:.1f} seconds',
                        'impact': 'Data consistency issues and delayed propagation',
                        'metrics': {'sync_lag_seconds': sync_lag}
                    })
            
            # Analyze backend health
            backend_health = analytics.get('backend_health', {})
            if backend_health and 'backends' in backend_health::
                summary = backend_health.get('summary', {})
                self._add_metric("vfs_backend_total_count", summary.get('total_backends', 0))
                self._add_metric("vfs_backend_healthy_count", summary.get('healthy_backends', 0))
                self._add_metric("vfs_backend_unhealthy_count", summary.get('unhealthy_backends', 0))
                self._add_metric("vfs_backend_health_percentage", summary.get('health_percentage', 0))
                
                for backend_name, backend_status in backend_health['backends'].items():
                    tags = {"backend": backend_name}
                    self._add_metric("vfs_backend_healthy", 1 if backend_status.get('healthy', False) else 0, tags)
                    self._add_metric("vfs_backend_last_check_age_seconds", 
                                   backend_status.get('last_check_age_seconds', 0), tags)
                    self._add_metric("vfs_backend_is_stale", 1 if backend_status.get('is_stale', False) else 0, tags)
                    
                    if backend_status.get('average_latency_ms') is not None:
                        self._add_metric("vfs_backend_avg_latency_ms", 
                                       backend_status['average_latency_ms'], tags)
                    if backend_status.get('p95_latency_ms') is not None:
                        self._add_metric("vfs_backend_p95_latency_ms", 
                                       backend_status['p95_latency_ms'], tags)
            
            # Process alerts
            alerts = analytics.get('alerts', [])
            self._add_metric("vfs_active_alerts_total", len(alerts))
            
            # Count alerts by severity
            alert_counts = {'critical': 0, 'warning': 0, 'info': 0}
            for alert in alerts:
                severity = alert.get('severity', 'info')
                if severity in alert_counts:
                    alert_counts[severity] += 1
            
            for severity, count in alert_counts.items():
                self._add_metric("vfs_alerts_by_severity", count, {"severity": severity})
                
        except Exception as e:
            logger.error(f"Failed to collect VFS analytics data: {e}")
    
    def _add_metric(self, name: str, value: Any, tags: Optional[Dict[str, str]] = None) -> None:
        """Add a metric data point."""
        if name not in self.metrics:
            self.metrics[name] = MetricSeries(name=name)
        
        self.metrics[name].add_point(value, tags)
        
        # Limit the number of data points to prevent memory issues
        max_points = self.config.max_data_points
        if len(self.metrics[name].data_points) > max_points:
            # Remove oldest points
            self.metrics[name].data_points = self.metrics[name].data_points[-max_points:]
    
    async def _cleanup_old_data(self) -> None:
        """Clean up old data points."""
        for metric in self.metrics.values():
            metric.cleanup_old_data(self.config.data_retention_hours)
    
    def get_metrics(self) -> Dict[str, MetricSeries]:
        """Get all collected metrics."""
        return self.metrics.copy()
    
    def get_metric(self, name: str) -> Optional[MetricSeries]:
        """Get a specific metric by name."""
        return self.metrics.get(name)
    
    def get_latest_values(self) -> Dict[str, Any]:
        """Get the latest values for all metrics."""
        latest = {}
        for name, metric in self.metrics.items():
            latest_point = metric.get_latest()
            if latest_point:
                latest[name] = {
                    "value": latest_point.value,
                    "timestamp": latest_point.timestamp,
                    "tags": latest_point.tags
                }
        return latest
    
    def get_metric_summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics."""
        return {
            "total_metrics": len(self.metrics),
            "total_data_points": sum(len(metric.data_points) for metric in self.metrics.values()),
            "collection_errors": self.error_count,
            "last_error_time": self.last_error_time,
            "is_running": self.is_running,
            "metrics_list": list(self.metrics.keys())
        }
    
    async def get_vfs_deep_insights(self) -> Dict[str, Any]:
        """Get comprehensive VFS insights and analysis."""
        if not self.has_vfs_analytics:
            return {
                'available': False,
                'error': 'VFS analytics not available'
            }
        
        if not self.vfs_monitor: # Added check for vfs_monitor
            return {
                'available': False,
                'error': 'VFS monitor not initialized'
            }

        try:
            # Get comprehensive analytics from VFS monitor
            analytics = self.vfs_monitor.get_analytics_summary()
            
            # Get additional detailed analyses
            bandwidth_analysis = self.vfs_monitor.performance_monitor.get_bandwidth_analysis(60)
            operation_analysis = self.vfs_monitor.performance_monitor.get_operation_analysis(60)
            realtime_metrics = self.vfs_monitor.performance_monitor.get_realtime_metrics()
            replication_health = self.vfs_monitor.performance_monitor.get_replication_health()
            cache_analysis = self.vfs_monitor.performance_monitor.get_cache_analysis()
            backend_health = self.vfs_monitor.performance_monitor.get_backend_health_status()
            
            # Generate performance insights
            insights = self._generate_vfs_performance_insights(analytics)
            recommendations = self._generate_vfs_optimization_recommendations(analytics)
            
            # Get historical trends from collected metrics
            trends = self._analyze_vfs_trends()
            
            return {
                'available': True,
                'timestamp': time.time(),
                'comprehensive_report': analytics,
                'detailed_analyses': {
                    'bandwidth': bandwidth_analysis,
                    'operations': operation_analysis,
                    'realtime': realtime_metrics,
                    'replication': replication_health,
                    'cache': cache_analysis,
                    'backends': backend_health
                },
                'insights': insights,
                'recommendations': recommendations,
                'trends': trends,
                'health_summary': self._generate_vfs_health_summary(analytics)
            }
            
        except Exception as e:
            logger.error(f"Error getting VFS deep insights: {e}")
            return {
                'available': False,
                'error': str(e)
            }
    
    def _generate_vfs_performance_insights(self, analytics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate performance insights from VFS analytics."""
        insights = []
        
        try:
            # Analyze error patterns
            realtime = analytics.get('realtime_metrics', {})
            error_rate = realtime.get('error_rate', 0)
            ops_per_sec = realtime.get('operations_per_second', 0)
            
            if error_rate > 0.05:  # 5% error rate
                insights.append({
                    'type': 'performance_issue',
                    'severity': 'high' if error_rate > 0.2 else 'medium',
                    'category': 'error_rate',
                    'title': 'High VFS Error Rate',
                    'description': f'VFS operations are failing at {error_rate:.1%} rate',
                    'impact': 'Degraded user experience and potential data access issues',
                    'metrics': {'error_rate': error_rate, 'ops_per_second': ops_per_sec}
                })
            
            # Analyze throughput patterns
            if ops_per_sec > 100:
                insights.append({
                    'type': 'performance_pattern',
                    'severity': 'info',
                    'category': 'high_throughput',
                    'title': 'High VFS Throughput',
                    'description': f'VFS is processing {ops_per_sec:.1f} operations per second',
                    'impact': 'System is under heavy load - monitor for bottlenecks',
                    'metrics': {'operations_per_second': ops_per_sec}
                })
            elif ops_per_sec < 0.1 and self.is_running:
                insights.append({
                    'type': 'performance_issue',
                    'severity': 'medium',
                    'category': 'low_activity',
                    'title': 'Low VFS Activity',
                    'description': f'VFS activity is very low ({ops_per_sec:.1f} ops/sec)',
                    'impact': 'May indicate connectivity issues or system underutilization',
                    'metrics': {'operations_per_second': ops_per_sec}
                })
            
            # Analyze bandwidth patterns
            bandwidth = analytics.get('bandwidth_analysis', {})
            if bandwidth and 'total_average_bps' in bandwidth:
                total_bps = bandwidth['total_average_bps']
                if total_bps > 50 * 1024 * 1024:  # 50MB/s
                    insights.append({
                        'type': 'resource_usage',
                        'severity': 'medium',
                        'category': 'high_bandwidth',
                        'title': 'High Bandwidth Usage',
                        'description': f'VFS bandwidth usage: {total_bps / (1024*1024):.1f} MB/s',
                        'impact': 'High network utilization - may affect other services',
                        'metrics': {'bandwidth_mbps': total_bps / (1024*1024)}
                    })
            
            # Analyze cache performance
            cache = analytics.get('cache_analysis', {})
            if cache and 'current_metrics' in cache:
                hit_rate = cache['current_metrics'].get('hit_rate', 0)
                utilization = cache['current_metrics'].get('utilization', 0)
                
                if hit_rate < 0.7:  # 70% hit rate
                    insights.append({
                        'type': 'performance_issue',
                        'severity': 'medium',
                        'category': 'cache_efficiency',
                        'title': 'Low Cache Hit Rate',
                        'description': f'VFS cache hit rate is {hit_rate:.1%}',
                        'impact': 'Increased latency and backend load',
                        'metrics': {'cache_hit_rate': hit_rate, 'cache_utilization': utilization}
                    })
                
                if utilization > 0.9:  # 90% cache utilization
                    insights.append({
                        'type': 'resource_constraint',
                        'severity': 'warning',
                        'category': 'cache_pressure',
                        'title': 'High Cache Memory Pressure',
                        'description': f'VFS cache utilization is {utilization:.1%}',
                        'impact': 'Cache evictions may increase, reducing efficiency',
                        'metrics': {'cache_analysis': utilization}
                    })
            
            # Analyze replication health
            replication = analytics.get('replication_health', {})
            if replication and 'current_status' in replication:
                health_pct = replication['current_status'].get('health_percentage', 100)
                sync_lag = replication['current_status'].get('sync_lag_seconds', 0)
                
                if health_pct < 80:  # 80% healthy replicas
                    insights.append({
                        'type': 'availability_issue',
                        'severity': 'high' if health_pct < 50 else 'medium',
                        'category': 'replication_health',
                        'title': 'Replication Health Issues',
                        'description': f'Only {health_pct:.1f}% of replicas are healthy',
                        'impact': 'Reduced data redundancy and potential data loss risk',
                        'metrics': {'replication_health_percentage': health_pct}
                    })
                
                if sync_lag > 300:  # 5 minutes
                    insights.append({
                        'type': 'performance_issue',
                        'severity': 'medium',
                        'category': 'sync_lag',
                        'title': 'High Replication Sync Lag',
                        'description': f'Replication sync lag is {sync_lag:.1f} seconds',
                        'impact': 'Data consistency issues and delayed propagation',
                        'metrics': {'sync_lag_seconds': sync_lag}
                    })
            
            # Analyze backend health
            backend_health = analytics.get('backend_health', {})
            if backend_health and 'backends' in backend_health::
                summary = backend_health.get('summary', {})
                self._add_metric("vfs_backend_total_count", summary.get('total_backends', 0))
                self._add_metric("vfs_backend_healthy_count", summary.get('healthy_backends', 0))
                self._add_metric("vfs_backend_unhealthy_count", summary.get('unhealthy_backends', 0))
                self._add_metric("vfs_backend_health_percentage", summary.get('health_percentage', 0))
                
                for backend_name, backend_status in backend_health['backends'].items():
                    tags = {"backend": backend_name}
                    self._add_metric("vfs_backend_healthy", 1 if backend_status.get('healthy', False) else 0, tags)
                    self._add_metric("vfs_backend_last_check_age_seconds", 
                                   backend_status.get('last_check_age_seconds', 0), tags)
                    self._add_metric("vfs_backend_is_stale", 1 if backend_status.get('is_stale', False) else 0, tags)
                    
                    if backend_status.get('average_latency_ms') is not None:
                        self._add_metric("vfs_backend_avg_latency_ms", 
                                       backend_status['average_latency_ms'], tags)
                    if backend_status.get('p95_latency_ms') is not None:
                        self._add_metric("vfs_backend_p95_latency_ms", 
                                       backend_status['p95_latency_ms'], tags)
            
            # Process alerts
            alerts = analytics.get('alerts', [])
            self._add_metric("vfs_active_alerts_total", len(alerts))
            
            # Count alerts by severity
            alert_counts = {'critical': 0, 'warning': 0, 'info': 0}
            for alert in alerts:
                severity = alert.get('severity', 'info')
                if severity in alert_counts:
                    alert_counts[severity] += 1
            
            for severity, count in alert_counts.items():
                self._add_metric("vfs_alerts_by_severity", count, {"severity": severity})
                
        except Exception as e:
            logger.error(f"Failed to collect VFS analytics data: {e}")
    
    def _add_metric(self, name: str, value: Any, tags: Optional[Dict[str, str]] = None) -> None:
        """Add a metric data point."""
        if name not in self.metrics:
            self.metrics[name] = MetricSeries(name=name)
        
        self.metrics[name].add_point(value, tags)
        
        # Limit the number of data points to prevent memory issues
        max_points = self.config.max_data_points
        if len(self.metrics[name].data_points) > max_points:
            # Remove oldest points
            self.metrics[name].data_points = self.metrics[name].data_points[-max_points:]
    
    async def _cleanup_old_data(self) -> None:
        """Clean up old data points."""
        for metric in self.metrics.values():
            metric.cleanup_old_data(self.config.data_retention_hours)
    
    def get_metrics(self) -> Dict[str, MetricSeries]:
        """Get all collected metrics."""
        return self.metrics.copy()
    
    def get_metric(self, name: str) -> Optional[MetricSeries]:
        """Get a specific metric by name."""
        return self.metrics.get(name)
    
    def get_latest_values(self) -> Dict[str, Any]:
        """Get the latest values for all metrics."""
        latest = {}
        for name, metric in self.metrics.items():
            latest_point = metric.get_latest()
            if latest_point:
                latest[name] = {
                    "value": latest_point.value,
                    "timestamp": latest_point.timestamp,
                    "tags": latest_point.tags
                }
        return latest
    
    def get_metric_summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics."""
        return {
            "total_metrics": len(self.metrics),
            "total_data_points": sum(len(metric.data_points) for metric in self.metrics.values()),
            "collection_errors": self.error_count,
            "last_error_time": self.last_error_time,
            "is_running": self.is_running,
            "metrics_list": list(self.metrics.keys())
        }
    
    async def get_vfs_deep_insights(self) -> Dict[str, Any]:
        """Get comprehensive VFS insights and analysis."""
        if not self.has_vfs_analytics:
            return {
                'available': False,
                'error': 'VFS analytics not available'
            }
        
        if not self.vfs_monitor: # Added check for vfs_monitor
            return {
                'available': False,
                'error': 'VFS monitor not initialized'
            }

        try:
            # Get comprehensive analytics from VFS monitor
            analytics = self.vfs_monitor.get_analytics_summary()
            
            # Get additional detailed analyses
            bandwidth_analysis = self.vfs_monitor.performance_monitor.get_bandwidth_analysis(60)
            operation_analysis = self.vfs_monitor.performance_monitor.get_operation_analysis(60)
            realtime_metrics = self.vfs_monitor.performance_monitor.get_realtime_metrics()
            replication_health = self.vfs_monitor.performance_monitor.get_replication_health()
            cache_analysis = self.vfs_monitor.performance_monitor.get_cache_analysis()
            backend_health = self.vfs_monitor.performance_monitor.get_backend_health_status()
            
            # Generate performance insights
            insights = self._generate_vfs_performance_insights(analytics)
            recommendations = self._generate_vfs_optimization_recommendations(analytics)
            
            # Get historical trends from collected metrics
            trends = self._analyze_vfs_trends()
            
            return {
                'available': True,
                'timestamp': time.time(),
                'comprehensive_report': analytics,
                'detailed_analyses': {
                    'bandwidth': bandwidth_analysis,
                    'operations': operation_analysis,
                    'realtime': realtime_metrics,
                    'replication': replication_health,
                    'cache': cache_analysis,
                    'backends': backend_health
                },
                'insights': insights,
                'recommendations': recommendations,
                'trends': trends,
                'health_summary': self._generate_vfs_health_summary(analytics)
            }
            
        except Exception as e:
            logger.error(f"Error getting VFS deep insights: {e}")
            return {
                'available': False,
                'error': str(e)
            }
    
    def _generate_vfs_performance_insights(self, analytics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate performance insights from VFS analytics."""
        insights = []
        
        try:
            # Analyze error patterns
            realtime = analytics.get('realtime_metrics', {})
            error_rate = realtime.get('error_rate', 0)
            ops_per_sec = realtime.get('operations_per_second', 0)
            
            if error_rate > 0.05:  # 5% error rate
                insights.append({
                    'type': 'performance_issue',
                    'severity': 'high' if error_rate > 0.2 else 'medium',
                    'category': 'error_rate',
                    'title': 'High VFS Error Rate',
                    'description': f'VFS operations are failing at {error_rate:.1%} rate',
                    'impact': 'Degraded user experience and potential data access issues',
                    'metrics': {'error_rate': error_rate, 'ops_per_second': ops_per_sec}
                })
            
            # Analyze throughput patterns
            if ops_per_sec > 100:
                insights.append({
                    'type': 'performance_pattern',
                    'severity': 'info',
                    'category': 'high_throughput',
                    'title': 'High VFS Throughput',
                    'description': f'VFS is processing {ops_per_sec:.1f} operations per second',
                    'impact': 'System is under heavy load - monitor for bottlenecks',
                    'metrics': {'operations_per_second': ops_per_sec}
                })
            elif ops_per_sec < 0.1 and self.is_running:
                insights.append({
                    'type': 'performance_issue',
                    'severity': 'medium',
                    'category': 'low_activity',
                    'title': 'Low VFS Activity',
                    'description': f'VFS activity is very low ({ops_per_sec:.1f} ops/sec)',
                    'impact': 'May indicate connectivity issues or system underutilization',
                    'metrics': {'operations_per_second': ops_per_sec}
                })
            
            # Analyze bandwidth patterns
            bandwidth = analytics.get('bandwidth_analysis', {})
            if bandwidth and 'total_average_bps' in bandwidth:
                total_bps = bandwidth['total_average_bps']
                if total_bps > 50 * 1024 * 1024:  # 50MB/s
                    insights.append({
                        'type': 'resource_usage',
                        'severity': 'medium',
                        'category': 'high_bandwidth',
                        'title': 'High Bandwidth Usage',
                        'description': f'VFS bandwidth usage: {total_bps / (1024*1024):.1f} MB/s',
                        'impact': 'High network utilization - may affect other services',
                        'metrics': {'bandwidth_mbps': total_bps / (1024*1024)}
                    })
            
            # Analyze cache performance
            cache = analytics.get('cache_analysis', {})
            if cache and 'current_metrics' in cache:
                hit_rate = cache['current_metrics'].get('hit_rate', 0)
                utilization = cache['current_metrics'].get('utilization', 0)
                
                if hit_rate < 0.7:  # 70% hit rate
                    insights.append({
                        'type': 'performance_issue',
                        'severity': 'medium',
                        'category': 'cache_efficiency',
                        'title': 'Low Cache Hit Rate',
                        'description': f'VFS cache hit rate is {hit_rate:.1%}',
                        'impact': 'Increased latency and backend load',
                        'metrics': {'cache_hit_rate': hit_rate, 'cache_utilization': utilization}
                    })
                
                if utilization > 0.9:  # 90% cache utilization
                    insights.append({
                        'type': 'resource_constraint',
                        'severity': 'warning',
                        'category': 'cache_pressure',
                        'title': 'High Cache Memory Pressure',
                        'description': f'VFS cache utilization is {utilization:.1%}',
                        'impact': 'Cache evictions may increase, reducing efficiency',
                        'metrics': {'cache_analysis': utilization}
                    })
            
            # Analyze replication health
            replication = analytics.get('replication_health', {})
            if replication and 'current_status' in replication:
                health_pct = replication['current_status'].get('health_percentage', 100)
                sync_lag = replication['current_status'].get('sync_lag_seconds', 0)
                
                if health_pct < 80:  # 80% healthy replicas
                    insights.append({
                        'type': 'availability_issue',
                        'severity': 'high' if health_pct < 50 else 'medium',
                        'category': 'replication_health',
                        'title': 'Replication Health Issues',
                        'description': f'Only {health_pct:.1f}% of replicas are healthy',
                        'impact': 'Reduced data redundancy and potential data loss risk',
                        'metrics': {'replication_health_percentage': health_pct}
                    })
                
                if sync_lag > 300:  # 5 minutes
                    insights.append({
                        'type': 'performance_issue',
                        'severity': 'medium',
                        'category': 'sync_lag',
                        'title': 'High Replication Sync Lag',
                        'description': f'Replication sync lag is {sync_lag:.1f} seconds',
                        'impact': 'Data consistency issues and delayed propagation',
                        'metrics': {'sync_lag_seconds': sync_lag}
                    })
            
            # Analyze backend health
            backend_health = analytics.get('backend_health', {})
            if backend_health and 'backends' in backend_health::
                summary = backend_health.get('summary', {})
                self._add_metric("vfs_backend_total_count", summary.get('total_backends', 0))
                self._add_metric("vfs_backend_healthy_count", summary.get('healthy_backends', 0))
                self._add_metric("vfs_backend_unhealthy_count", summary.get('unhealthy_backends', 0))
                self._add_metric("vfs_backend_health_percentage", summary.get('health_percentage', 0))
                
                for backend_name, backend_status in backend_health['backends'].items():
                    tags = {"backend": backend_name}
                    self._add_metric("vfs_backend_healthy", 1 if backend_status.get('healthy', False) else 0, tags)
                    self._add_metric("vfs_backend_last_check_age_seconds", 
                                   backend_status.get('last_check_age_seconds', 0), tags)
                    self._add_metric("vfs_backend_is_stale", 1 if backend_status.get('is_stale', False) else 0, tags)
                    
                    if backend_status.get('average_latency_ms') is not None:
                        self._add_metric("vfs_backend_avg_latency_ms", 
                                       backend_status['average_latency_ms'], tags)
                    if backend_status.get('p95_latency_ms') is not None:
                        self._add_metric("vfs_backend_p95_latency_ms", 
                                       backend_status['p95_latency_ms'], tags)
            
            # Process alerts
            alerts = analytics.get('alerts', [])
            self._add_metric("vfs_active_alerts_total", len(alerts))
            
            # Count alerts by severity
            alert_counts = {'critical': 0, 'warning': 0, 'info': 0}
            for alert in alerts:
                severity = alert.get('severity', 'info')
                if severity in alert_counts:
                    alert_counts[severity] += 1
            
            for severity, count in alert_counts.items():
                self._add_metric("vfs_alerts_by_severity", count, {"severity": severity})
                
        except Exception as e:
            logger.error(f"Failed to collect VFS analytics data: {e}")
    
    def _add_metric(self, name: str, value: Any, tags: Optional[Dict[str, str]] = None) -> None:
        """Add a metric data point."""
        if name not in self.metrics:
            self.metrics[name] = MetricSeries(name=name)
        
        self.metrics[name].add_point(value, tags)
        
        # Limit the number of data points to prevent memory issues
        max_points = self.config.max_data_points
        if len(self.metrics[name].data_points) > max_points:
            # Remove oldest points
            self.metrics[name].data_points = self.metrics[name].data_points[-max_points:]
    
    async def _cleanup_old_data(self) -> None:
        """Clean up old data points."""
        for metric in self.metrics.values():
            metric.cleanup_old_data(self.config.data_retention_hours)
    
    def get_metrics(self) -> Dict[str, MetricSeries]:
        """Get all collected metrics."""
        return self.metrics.copy()
    
    def get_metric(self, name: str) -> Optional[MetricSeries]:
        """Get a specific metric by name."""
        return self.metrics.get(name)
    
    def get_latest_values(self) -> Dict[str, Any]:
        """Get the latest values for all metrics."""
        latest = {}
        for name, metric in self.metrics.items():
            latest_point = metric.get_latest()
            if latest_point:
                latest[name] = {
                    "value": latest_point.value,
                    "timestamp": latest_point.timestamp,
                    "tags": latest_point.tags
                }
        return latest
    
    def get_metric_summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics."""
        return {
            "total_metrics": len(self.metrics),
            "total_data_points": sum(len(metric.data_points) for metric in self.metrics.values()),
            "collection_errors": self.error_count,
            "last_error_time": self.last_error_time,
            "is_running": self.is_running,
            "metrics_list": list(self.metrics.keys())
        }
    
    async def get_vfs_deep_insights(self) -> Dict[str, Any]:
        """Get comprehensive VFS insights and analysis."""
        if not self.has_vfs_analytics:
            return {
                'available': False,
                'error': 'VFS analytics not available'
            }
        
        if not self.vfs_monitor: # Added check for vfs_monitor
            return {
                'available': False,
                'error': 'VFS monitor not initialized'
            }

        try:
            # Get comprehensive analytics from VFS monitor
            analytics = self.vfs_monitor.get_analytics_summary()
            
            # Get additional detailed analyses
            bandwidth_analysis = self.vfs_monitor.performance_monitor.get_bandwidth_analysis(60)
            operation_analysis = self.vfs_monitor.performance_monitor.get_operation_analysis(60)
            realtime_metrics = self.vfs_monitor.performance_monitor.get_realtime_metrics()
            replication_health = self.vfs_monitor.performance_monitor.get_replication_health()
            cache_analysis = self.vfs_monitor.performance_monitor.get_cache_analysis()
            backend_health = self.vfs_monitor.performance_monitor.get_backend_health_status()
            
            # Generate performance insights
            insights = self._generate_vfs_performance_insights(analytics)
            recommendations = self._generate_vfs_optimization_recommendations(analytics)
            
            # Get historical trends from collected metrics
            trends = self._analyze_vfs_trends()
            
            return {
                'available': True,
                'timestamp': time.time(),
                'comprehensive_report': analytics,
                'detailed_analyses': {
                    'bandwidth': bandwidth_analysis,
                    'operations': operation_analysis,
                    'realtime': realtime_metrics,
                    'replication': replication_health,
                    'cache': cache_analysis,
                    'backends': backend_health
                },
                'insights': insights,
                'recommendations': recommendations,
                'trends': trends,
                'health_summary': self._generate_vfs_health_summary(analytics)
            }
            
        except Exception as e:
            logger.error(f"Error getting VFS deep insights: {e}")
            return {
                'available': False,
                'error': str(e)
            }
    
    def _generate_vfs_performance_insights(self, analytics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate performance insights from VFS analytics."""
        insights = []
        
        try:
            # Analyze error patterns
            realtime = analytics.get('realtime_metrics', {})
            error_rate = realtime.get('error_rate', 0)
            ops_per_sec = realtime.get('operations_per_second', 0)
            
            if error_rate > 0.05:  # 5% error rate
                insights.append({
                    'type': 'performance_issue',
                    'severity': 'high' if error_rate > 0.2 else 'medium',
                    'category': 'error_rate',
                    'title': 'High VFS Error Rate',
                    'description': f'VFS operations are failing at {error_rate:.1%} rate',
                    'impact': 'Degraded user experience and potential data access issues',
                    'metrics': {'error_rate': error_rate, 'ops_per_second': ops_per_sec}
                })
            
            # Analyze throughput patterns
            if ops_per_sec > 100:
                insights.append({
                    'type': 'performance_pattern',
                    'severity': 'info',
                    'category': 'high_throughput',
                    'title': 'High VFS Throughput',
                    'description': f'VFS is processing {ops_per_sec:.1f} operations per second',
                    'impact': 'System is under heavy load - monitor for bottlenecks',
                    'metrics': {'operations_per_second': ops_per_sec}
                })
            elif ops_per_sec < 0.1 and self.is_running:
                insights.append({
                    'type': 'performance_issue',
                    'severity': 'medium',
                    'category': 'low_activity',
                    'title': 'Low VFS Activity',
                    'description': f'VFS activity is very low ({ops_per_sec:.1f} ops/sec)',
                    'impact': 'May indicate connectivity issues or system underutilization',
                    'metrics': {'operations_per_second': ops_per_sec}
                })
            
            # Analyze bandwidth patterns
            bandwidth = analytics.get('bandwidth_analysis', {})
            if bandwidth and 'total_average_bps' in bandwidth:
                total_bps = bandwidth['total_average_bps']
                if total_bps > 50 * 1024 * 1024:  # 50MB/s
                    insights.append({
                        'type': 'resource_usage',
                        'severity': 'medium',
                        'category': 'high_bandwidth',
                        'title': 'High Bandwidth Usage',
                        'description': f'VFS bandwidth usage: {total_bps / (1024*1024):.1f} MB/s',
                        'impact': 'High network utilization - may affect other services',
                        'metrics': {'bandwidth_mbps': total_bps / (1024*1024)}
                    })
            
            # Analyze cache performance
            cache = analytics.get('cache_analysis', {})
            if cache and 'current_metrics' in cache:
                hit_rate = cache['current_metrics'].get('hit_rate', 0)
                utilization = cache['current_metrics'].get('utilization', 0)
                
                if hit_rate < 0.7:  # 70% hit rate
                    insights.append({
                        'type': 'performance_issue',
                        'severity': 'medium',
                        'category': 'cache_efficiency',
                        'title': 'Low Cache Hit Rate',
                        'description': f'VFS cache hit rate is {hit_rate:.1%}',
                        'impact': 'Increased latency and backend load',
                        'metrics': {'cache_hit_rate': hit_rate, 'cache_utilization': utilization}
                    })
                
                if utilization > 0.9:  # 90% cache utilization
                    insights.append({
                        'type': 'resource_constraint',
                        'severity': 'warning',
                        'category': 'cache_pressure',
                        'title': 'High Cache Memory Pressure',
                        'description': f'VFS cache utilization is {utilization:.1%}',
                        'impact': 'Cache evictions may increase, reducing efficiency',
                        'metrics': {'cache_analysis': utilization}
                    })
            
            # Analyze replication health
            replication = analytics.get('replication_health', {})
            if replication and 'current_status' in replication:
                health_pct = replication['current_status'].get('health_percentage', 100)
                sync_lag = replication['current_status'].get('sync_lag_seconds', 0)
                
                if health_pct < 80:  # 80% healthy replicas
                    insights.append({
                        'type': 'availability_issue',
                        'severity': 'high' if health_pct < 50 else 'medium',
                        'category': 'replication_health',
                        'title': 'Replication Health Issues',
                        'description': f'Only {health_pct:.1f}% of replicas are healthy',
                        'impact': 'Reduced data redundancy and potential data loss risk',
                        'metrics': {'replication_health_percentage': health_pct}
                    })
                
                if sync_lag > 300:  # 5 minutes
                    insights.append({
                        'type': 'performance_issue',
                        'severity': 'medium',
                        'category': 'sync_lag',
                        'title': 'High Replication Sync Lag',
                        'description': f'Replication sync lag is {sync_lag:.1f} seconds',
                        'impact': 'Data consistency issues and delayed propagation',
                        'metrics': {'sync_lag_seconds': sync_lag}
                    })
            
            # Analyze backend health
            backend_health = analytics.get('backend_health', {})
            if backend_health and 'backends' in backend_health::
                summary = backend_health.get('summary', {})
                self._add_metric("vfs_backend_total_count", summary.get('total_backends', 0))
                self._add_metric("vfs_backend_healthy_count", summary.get('healthy_backends', 0))
                self._add_metric("vfs_backend_unhealthy_count", summary.get('unhealthy_backends', 0))
                self._add_metric("vfs_backend_health_percentage", summary.get('health_percentage', 0))
                
                for backend_name, backend_status in backend_health['backends'].items():
                    tags = {"backend": backend_name}
                    self._add_metric("vfs_backend_healthy", 1 if backend_status.get('healthy', False) else 0, tags)
                    self._add_metric("vfs_backend_last_check_age_seconds", 
                                   backend_status.get('last_check_age_seconds', 0), tags)
                    self._add_metric("vfs_backend_is_stale", 1 if backend_status.get('is_stale', False) else 0, tags)
                    
                    if backend_status.get('average_latency_ms') is not None:
                        self._add_metric("vfs_backend_avg_latency_ms", 
                                       backend_status['average_latency_ms'], tags)
                    if backend_status.get('p95_latency_ms') is not None:
                        self._add_metric("vfs_backend_p95_latency_ms", 
                                       backend_status['p95_latency_ms'], tags)
            
            # Process alerts
            alerts = analytics.get('alerts', [])
            self._add_metric("vfs_active_alerts_total", len(alerts))
            
            # Count alerts by severity
            alert_counts = {'critical': 0, 'warning': 0, 'info': 0}
            for alert in alerts:
                severity = alert.get('severity', 'info')
                if severity in alert_counts:
                    alert_counts[severity] += 1
            
            for severity, count in alert_counts.items():
                self._add_metric("vfs_alerts_by_severity", count, {"severity": severity})
                
        except Exception as e:
            logger.error(f"Failed to collect VFS analytics data: {e}")
    
    def _add_metric(self, name: str, value: Any, tags: Optional[Dict[str, str]] = None) -> None:
        """Add a metric data point."""
        if name not in self.metrics:
            self.metrics[name] = MetricSeries(name=name)
        
        self.metrics[name].add_point(value, tags)
        
        # Limit the number of data points to prevent memory issues
        max_points = self.config.max_data_points
        if len(self.metrics[name].data_points) > max_points:
            # Remove oldest points
            self.metrics[name].data_points = self.metrics[name].data_points[-max_points:]
    
    async def _cleanup_old_data(self) -> None:
        """Clean up old data points."""
        for metric in self.metrics.values():
            metric.cleanup_old_data(self.config.data_retention_hours)
    
    def get_metrics(self) -> Dict[str, MetricSeries]:
        """Get all collected metrics."""
        return self.metrics.copy()
    
    def get_metric(self, name: str) -> Optional[MetricSeries]:
        """Get a specific metric by name."""
        return self.metrics.get(name)
    
    def get_latest_values(self) -> Dict[str, Any]:
        """Get the latest values for all metrics."""
        latest = {}
        for name, metric in self.metrics.items():
            latest_point = metric.get_latest()
            if latest_point:
                latest[name] = {
                    "value": latest_point.value,
                    "timestamp": latest_point.timestamp,
                    "tags": latest_point.tags
                }
        return latest
    
    def get_metric_summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics."""
        return {
            "total_metrics": len(self.metrics),
            "total_data_points": sum(len(metric.data_points) for metric in self.metrics.values()),
            "collection_errors": self.error_count,
            "last_error_time": self.last_error_time,
            "is_running": self.is_running,
            "metrics_list": list(self.metrics.keys())
        }
    
    async def get_vfs_deep_insights(self) -> Dict[str, Any]:
        """Get comprehensive VFS insights and analysis."""
        if not self.has_vfs_analytics:
            return {
                'available': False,
                'error': 'VFS analytics not available'
            }
        
        if not self.vfs_monitor: # Added check for vfs_monitor
            return {
                'available': False,
                'error': 'VFS monitor not initialized'
            }

        try:
            # Get comprehensive analytics from VFS monitor
            analytics = self.vfs_monitor.get_analytics_summary()
            
            # Get additional detailed analyses
            bandwidth_analysis = self.vfs_monitor.performance_monitor.get_bandwidth_analysis(60)
            operation_analysis = self.vfs_monitor.performance_monitor.get_operation_analysis(60)
            realtime_metrics = self.vfs_monitor.performance_monitor.get_realtime_metrics()
            replication_health = self.vfs_monitor.performance_monitor.get_replication_health()
            cache_analysis = self.vfs_monitor.performance_monitor.get_cache_analysis()
            backend_health = self.vfs_monitor.performance_monitor.get_backend_health_status()
            
            # Generate performance insights
            insights = self._generate_vfs_performance_insights(analytics)
            recommendations = self._generate_vfs_optimization_recommendations(analytics)
            
            # Get historical trends from collected metrics
            trends = self._analyze_vfs_trends()
            
            return {
                'available': True,
                'timestamp': time.time(),
                'comprehensive_report': analytics,
                'detailed_analyses': {
                    'bandwidth': bandwidth_analysis,
                    'operations': operation_analysis,
                    'realtime': realtime_metrics,
                    'replication': replication_health,
                    'cache': cache_analysis,
                    'backends': backend_health
                },
                'insights': insights,
                'recommendations': recommendations,
                'trends': trends,
                'health_summary': self._generate_vfs_health_summary(analytics)
            }
            
        except Exception as e:
            logger.error(f"Error getting VFS deep insights: {e}")
            return {
                'available': False,
                'error': str(e)
            }
    
    def _generate_vfs_performance_insights(self, analytics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate performance insights from VFS analytics."""
        insights = []
        
        try:
            # Analyze error patterns
            realtime = analytics.get('realtime_metrics', {})
            error_rate = realtime.get('error_rate', 0)
            ops_per_sec = realtime.get('operations_per_second', 0)
            
            if error_rate > 0.05:  # 5% error rate
                insights.append({
                    'type': 'performance_issue',
                    'severity': 'high' if error_rate > 0.2 else 'medium',
                    'category': 'error_rate',
                    'title': 'High VFS Error Rate',
                    'description': f'VFS operations are failing at {error_rate:.1%} rate',
                    'impact': 'Degraded user experience and potential data access issues',
                    'metrics': {'error_rate': error_rate, 'ops_per_second': ops_per_sec}
                })
            
            # Analyze throughput patterns
            if ops_per_sec > 100:
                insights.append({
                    'type': 'performance_pattern',
                    'severity': 'info',
                    'category': 'high_throughput',
                    'title': 'High VFS Throughput',
                    'description': f'VFS is processing {ops_per_sec:.1f} operations per second',
                    'impact': 'System is under heavy load - monitor for bottlenecks',
                    'metrics': {'operations_per_second': ops_per_sec}
                })
            elif ops_per_sec < 0.1 and self.is_running:
                insights.append({
                    'type': 'performance_issue',
                    'severity': 'medium',
                    'category': 'low_activity',
                    'title': 'Low VFS Activity',
                    'description': f'VFS activity is very low ({ops_per_sec:.1f} ops/sec)',
                    'impact': 'May indicate connectivity issues or system underutilization',
                    'metrics': {'operations_per_second': ops_per_sec}
                })
            
            # Analyze bandwidth patterns
            bandwidth = analytics.get('bandwidth_analysis', {})
            if bandwidth and 'total_average_bps' in bandwidth:
                total_bps = bandwidth['total_average_bps']
                if total_bps > 50 * 1024 * 1024:  # 50MB/s
                    insights.append({
                        'type': 'resource_usage',
                        'severity': 'medium',
                        'category': 'high_bandwidth',
                        'title': 'High Bandwidth Usage',
                        'description': f'VFS bandwidth usage: {total_bps / (1024*1024):.1f} MB/s',
                        'impact': 'High network utilization - may affect other services',
                        'metrics': {'bandwidth_mbps': total_bps / (1024*1024)}
                    })
            
            # Analyze cache performance
            cache = analytics.get('cache_analysis', {})
            if cache and 'current_metrics' in cache:
                hit_rate = cache['current_metrics'].get('hit_rate', 0)
                utilization = cache['current_metrics'].get('utilization', 0)
                
                if hit_rate < 0.7:  # 70% hit rate
                    insights.append({
                        'type': 'performance_issue',
                        'severity': 'medium',
                        'category': 'cache_efficiency',
                        'title': 'Low Cache Hit Rate',
                        'description': f'VFS cache hit rate is {hit_rate:.1%}',
                        'impact': 'Increased latency and backend load',
                        'metrics': {'cache_hit_rate': hit_rate, 'cache_utilization': utilization}
                    })
                
                if utilization > 0.9:  # 90% cache utilization
                    insights.append({
                        'type': 'resource_constraint',
                        'severity': 'warning',
                        'category': 'cache_pressure',
                        'title': 'High Cache Memory Pressure',
                        'description': f'VFS cache utilization is {utilization:.1%}',
                        'impact': 'Cache evictions may increase, reducing efficiency',
                        'metrics': {'cache_analysis': utilization}
                    })
            
            # Analyze replication health
            replication = analytics.get('replication_health', {})
            if replication and 'current_status' in replication:
                health_pct = replication['current_status'].get('health_percentage', 100)
                sync_lag = replication['current_status'].get('sync_lag_seconds', 0)
                
                if health_pct < 80:  # 80% healthy replicas
                    insights.append({
                        'type': 'availability_issue',
                        'severity': 'high' if health_pct < 50 else 'medium',
                        'category': 'replication_health',
                        'title': 'Replication Health Issues',
                        'description': f'Only {health_pct:.1f}% of replicas are healthy',
                        'impact': 'Reduced data redundancy and potential data loss risk',
                        'metrics': {'replication_health_percentage': health_pct}
                    })
                
                if sync_lag > 300:  # 5 minutes
                    insights.append({
                        'type': 'performance_issue',
                        'severity': 'medium',
                        'category': 'sync_lag',
                        'title': 'High Replication Sync Lag',
                        'description': f'Replication sync lag is {sync_lag:.1f} seconds',
                        'impact': 'Data consistency issues and delayed propagation',
                        'metrics': {'sync_lag_seconds': sync_lag}
                    })
            
            # Analyze backend health
            backend_health = analytics.get('backend_health', {})
            if backend_health and 'backends' in backend_health::
                summary = backend_health.get('summary', {})
                self._add_metric("vfs_backend_total_count", summary.get('total_backends', 0))
                self._add_metric("vfs_backend_healthy_count", summary.get('healthy_backends', 0))
                self._add_metric("vfs_backend_unhealthy_count", summary.get('unhealthy_backends', 0))
                self._add_metric("vfs_backend_health_percentage", summary.get('health_percentage', 0))
                
                for backend_name, backend_status in backend_health['backends'].items():
                    tags = {"backend": backend_name}
                    self._add_metric("vfs_backend_healthy", 1 if backend_status.get('healthy', False) else 0, tags)
                    self._add_metric("vfs_backend_last_check_age_seconds", 
                                   backend_status.get('last_check_age_seconds', 0), tags)
                    self._add_metric("vfs_backend_is_stale", 1 if backend_status.get('is_stale', False) else 0, tags)
                    
                    if backend_status.get('average_latency_ms') is not None:
                        self._add_metric("vfs_backend_avg_latency_ms", 
                                       backend_status['average_latency_ms'], tags)
                    if backend_status.get('p95_latency_ms') is not None:
                        self._add_metric("vfs_backend_p95_latency_ms", 
                                       backend_status['p95_latency_ms'], tags)
            
            # Process alerts
            alerts = analytics.get('alerts', [])
            self._add_metric("vfs_active_alerts_total", len(alerts))
            
            # Count alerts by severity
            alert_counts = {'critical': 0, 'warning': 0, 'info': 0}
            for alert in alerts:
                severity = alert.get('severity', 'info')
                if severity in alert_counts:
                    alert_counts[severity] += 1
            
            for severity, count in alert_counts.items():
                self._add_metric("vfs_alerts_by_severity", count, {"severity": severity})
                
        except Exception as e:
            logger.error(f"Failed to collect VFS analytics data: {e}")
    
    def _add_metric(self, name: str, value: Any, tags: Optional[Dict[str, str]] = None) -> None:
        """Add a metric data point."""
        if name not in self.metrics:
            self.metrics[name] = MetricSeries(name=name)
        
        self.metrics[name].add_point(value, tags)
        
        # Limit the number of data points to prevent memory issues
        max_points = self.config.max_data_points
        if len(self.metrics[name].data_points) > max_points:
            # Remove oldest points
            self.metrics[name].data_points = self.metrics[name].data_points[-max_points:]
    
    async def _cleanup_old_data(self) -> None:
        """Clean up old data points."""
        for metric in self.metrics.values():
            metric.cleanup_old_data(self.config.data_retention_hours)
    
    def get_metrics(self) -> Dict[str, MetricSeries]:
        """Get all collected metrics."""
        return self.metrics.copy()
    
    def get_metric(self, name: str) -> Optional[MetricSeries]:
        """Get a specific metric by name."""
        return self.metrics.get(name)
    
    def get_latest_values(self) -> Dict[str, Any]:
        """Get the latest values for all metrics."""
        latest = {}
        for name, metric in self.metrics.items():
            latest_point = metric.get_latest()
            if latest_point:
                latest[name] = {
                    "value": latest_point.value,
                    "timestamp": latest_point.timestamp,
                    "tags": latest_point.tags
                }
        return latest
    
    def get_metric_summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics."""
        return {
            "total_metrics": len(self.metrics),
            "total_data_points": sum(len(metric.data_points) for metric in self.metrics.values()),
            "collection_errors": self.error_count,
            "last_error_time": self.last_error_time,
            "is_running": self.is_running,
            "metrics_list": list(self.metrics.keys())
        }
    
    async def get_vfs_deep_insights(self) -> Dict[str, Any]:
        """Get comprehensive VFS insights and analysis."""
        if not self.has_vfs_analytics:
            return {
                'available': False,
                'error': 'VFS analytics not available'
            }
        
        if not self.vfs_monitor: # Added check for vfs_monitor
            return {
                'available': False,
                'error': 'VFS monitor not initialized'
            }

        try:
            # Get comprehensive analytics from VFS monitor
            analytics = self.vfs_monitor.get_analytics_summary()
            
            # Get additional detailed analyses
            bandwidth_analysis = self.vfs_monitor.performance_monitor.get_bandwidth_analysis(60)
            operation_analysis = self.vfs_monitor.performance_monitor.get_operation_analysis(60)
            realtime_metrics = self.vfs_monitor.performance_monitor.get_realtime_metrics()
            replication_health = self.vfs_monitor.performance_monitor.get_replication_health()
            cache_analysis = self.vfs_monitor.performance_monitor.get_cache_analysis()
            backend_health = self.vfs_monitor.performance_monitor.get_backend_health_status()
            
            # Generate performance insights
            insights = self._generate_vfs_performance_insights(analytics)
            recommendations = self._generate_vfs_optimization_recommendations(analytics)
            
            # Get historical trends from collected metrics
            trends = self._analyze_vfs_trends()
            
            return {
                'available': True,
                'timestamp': time.time(),
                'comprehensive_report': analytics,
                'detailed_analyses': {
                    'bandwidth': bandwidth_analysis,
                    'operations': operation_analysis,
                    'realtime': realtime_metrics,
                    'replication': replication_health,
                    'cache': cache_analysis,
                    'backends': backend_health
                },
                'insights': insights,
                'recommendations': recommendations,
                'trends': trends,
                'health_summary': self._generate_vfs_health_summary(analytics)
            }
            
        except Exception as e:
            logger.error(f"Error getting VFS deep insights: {e}")
            return {
                'available': False,
                'error': str(e)
            }
    
    def _generate_vfs_performance_insights(self, analytics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate performance insights from VFS analytics."""
        insights = []
        
        try:
            # Analyze error patterns
            realtime = analytics.get('realtime_metrics', {})
            error_rate = realtime.get('error_rate', 0)
            ops_per_sec = realtime.get('operations_per_second', 0)
            
            if error_rate > 0.05:  # 5% error rate
                insights.append({
                    'type': 'performance_issue',
                    'severity': 'high' if error_rate > 0.2 else 'medium',
                    'category': 'error_rate',
                    'title': 'High VFS Error Rate',
                    'description': f'VFS operations are failing at {error_rate:.1%} rate',
                    'impact': 'Degraded user experience and potential data access issues',
                    'metrics': {'error_rate': error_rate, 'ops_per_second': ops_per_sec}
                })
            
            # Analyze throughput patterns
            if ops_per_sec > 100:
                insights.append({
                    'type': 'performance_pattern',
                    'severity': 'info',
                    'category': 'high_throughput',
                    'title': 'High VFS Throughput',
                    'description': f'VFS is processing {ops_per_sec:.1f} operations per second',
                    'impact': 'System is under heavy load - monitor for bottlenecks',
                    'metrics': {'operations_per_second': ops_per_sec}
                })
            elif ops_per_sec < 0.1 and self.is_running:
                insights.append({
                    'type': 'performance_issue',
                    'severity': 'medium',
                    'category': 'low_activity',
                    'title': 'Low VFS Activity',
                    'description': f'VFS activity is very low ({ops_per_sec:.1f} ops/sec)',
                    'impact': 'May indicate connectivity issues or system underutilization',
                    'metrics': {'operations_per_second': ops_per_sec}
                })
            
            # Analyze bandwidth patterns
            bandwidth = analytics.get('bandwidth_analysis', {})
            if bandwidth and 'total_average_bps' in bandwidth:
                total_bps = bandwidth['total_average_bps']
                if total_bps > 50 * 1024 * 1024:  # 50MB/s
                    insights.append({
                        'type': 'resource_usage',
                        'severity': 'medium',
                        'category': 'high_bandwidth',
                        'title': 'High Bandwidth Usage',
                        'description': f'VFS bandwidth usage: {total_bps / (1024*1024):.1f} MB/s',
                        'impact': 'High network utilization - may affect other services',
                        'metrics': {'bandwidth_mbps': total_bps / (1024*1024)}
                    })
            
            # Analyze cache performance
            cache = analytics.get('cache_analysis', {})
            if cache and 'current_metrics' in cache:
                hit_rate = cache['current_metrics'].get('hit_rate', 0)
                utilization = cache['current_metrics'].get('utilization', 0)
                
                if hit_rate < 0.7:  # 70% hit rate
                    insights.append({
                        'type': 'performance_issue',
                        'severity': 'medium',
                        'category': 'cache_efficiency',
                        'title': 'Low Cache Hit Rate',
                        'description': f'VFS cache hit rate is {hit_rate:.1%}',
                        'impact': 'Increased latency and backend load',
                        'metrics': {'cache_hit_rate': hit_rate, 'cache_utilization': utilization}
                    })
                
                if utilization > 0.9:  # 90% cache utilization
                    insights.append({
                        'type': 'resource_constraint',
                        'severity': 'warning',
                        'category': 'cache_pressure',
                        'title': 'High Cache Memory Pressure',
                        'description': f'VFS cache utilization is {utilization:.1%}',
                        'impact': 'Cache evictions may increase, reducing efficiency',
                        'metrics': {'cache_analysis': utilization}
                    })
            
            # Analyze replication health
            replication = analytics.get('replication_health', {})
            if replication and 'current_status' in replication:
                health_pct = replication['current_status'].get('health_percentage', 100)
                sync_lag = replication['current_status'].get('sync_lag_seconds', 0)
                
                if health_pct < 80:  # 80% healthy replicas
                    insights.append({
                        'type': 'availability_issue',
                        'severity': 'high' if health_pct < 50 else 'medium',
                        'category': 'replication_health',
                        'title': 'Replication Health Issues',
                        'description': f'Only {health_pct:.1f}% of replicas are healthy',
                        'impact': 'Reduced data redundancy and potential data loss risk',
                        'metrics': {'replication_health_percentage': health_pct}
                    })
                
                if sync_lag > 300:  # 5 minutes
                    insights.append({
                        'type': 'performance_issue',
                        'severity': 'medium',
                        'category': 'sync_lag',
                        'title': 'High Replication Sync Lag',
                        'description': f'Replication sync lag is {sync_lag:.1f} seconds',
                        'impact': 'Data consistency issues and delayed propagation',
                        'metrics': {'sync_lag_seconds': sync_lag}
                    })
            
            # Analyze backend health
            backend_health = analytics.get('backend_health', {})
            if backend_health and 'backends' in backend_health::
                summary = backend_health.get('summary', {})
                self._add_metric("vfs_backend_total_count", summary.get('total_backends', 0))
                self._add_metric("vfs_backend_healthy_count", summary.get('healthy_backends', 0))
                self._add_metric("vfs_backend_unhealthy_count", summary.get('unhealthy_backends', 0))
                self._add_metric("vfs_backend_health_percentage", summary.get('health_percentage', 0))
                
                for backend_name, backend_status in backend_health['backends'].items():
                    tags = {"backend": backend_name}
                    self._add_metric("vfs_backend_healthy", 1 if backend_status.get('healthy', False) else 0, tags)
                    self._add_metric("vfs_backend_last_check_age_seconds", 
                                   backend_status.get('last_check_age_seconds', 0), tags)
                    self._add_metric("vfs_backend_is_stale", 1 if backend_status.get('is_stale', False) else 0, tags)
                    
                    if backend_status.get('average_latency_ms') is not None:
                        self._add_metric("vfs_backend_avg_latency_ms", 
                                       backend_status['average_latency_ms'], tags)
                    if backend_status.get('p95_latency_ms') is not None:
                        self._add_metric("vfs_backend_p95_latency_ms", 
                                       backend_status['p95_latency_ms'], tags)
            
            # Process alerts
            alerts = analytics.get('alerts', [])
            self._add_metric("vfs_active_alerts_total", len(alerts))
            
            # Count alerts by severity
            alert_counts = {'critical': 0, 'warning': 0, 'info': 0}
            for alert in alerts:
                severity = alert.get('severity', 'info')
                if severity in alert_counts:
                    alert_counts[severity] += 1
            
            for severity, count in alert_counts.items():
                self._add_metric("vfs_alerts_by_severity", count, {"severity": severity})
                
        except Exception as e:
            logger.error(f"Failed to collect VFS analytics data: {e}")
    
    def _add_metric(self, name: str, value: Any, tags: Optional[Dict[str, str]] = None) -> None:
        """Add a metric data point."""
        if name not in self.metrics:
            self.metrics[name] = MetricSeries(name=name)
        
        self.metrics[name].add_point(value, tags)
        
        # Limit the number of data points to prevent memory issues
        max_points = self.config.max_data_points
        if len(self.metrics[name].data_points) > max_points:
            # Remove oldest points
            self.metrics[name].data_points = self.metrics[name].data_points[-max_points:]
    
    async def _cleanup_old_data(self) -> None:
        """Clean up old data points."""
        for metric in self.metrics.values():
            metric.cleanup_old_data(self.config.data_retention_hours)
    
    def get_metrics(self) -> Dict[str, MetricSeries]:
        """Get all collected metrics."""
        return self.metrics.copy()
    
    def get_metric(self, name: str) -> Optional[MetricSeries]:
        """Get a specific metric by name."""
        return self.metrics.get(name)
    
    def get_latest_values(self) -> Dict[str, Any]:
        """Get the latest values for all metrics."""
        latest = {}
        for name, metric in self.metrics.items():
            latest_point = metric.get_latest()
            if latest_point:
                latest[name] = {
                    "value": latest_point.value,
                    "timestamp": latest_point.timestamp,
                    "tags": latest_point.tags
                }
        return latest
    
    def get_metric_summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics."""
        return {
            "total_metrics": len(self.metrics),
            "total_data_points": sum(len(metric.data_points) for metric in self.metrics.values()),
            "collection_errors": self.error_count,
            "last_error_time": self.last_error_time,
            "is_running": self.is_running,
            "metrics_list": list(self.metrics.keys())
        }
    
    async def get_vfs_deep_insights(self) -> Dict[str, Any]:
        """Get comprehensive VFS insights and analysis."""
        if not self.has_vfs_analytics:
            return {
                'available': False,
                'error': 'VFS analytics not available'
            }
        
        if not self.vfs_monitor: # Added check for vfs_monitor
            return {
                'available': False,
                'error': 'VFS monitor not initialized'
            }

        try:
            # Get comprehensive analytics from VFS monitor
            analytics = self.vfs_monitor.get_analytics_summary()
            
            # Get additional detailed analyses
            bandwidth_analysis = self.vfs_monitor.performance_monitor.get_bandwidth_analysis(60)
            operation_analysis = self.vfs_monitor.performance_monitor.get_operation_analysis(60)
            realtime_metrics = self.vfs_monitor.performance_monitor.get_realtime_metrics()
            replication_health = self.vfs_monitor.performance_monitor.get_replication_health()
            cache_analysis = self.vfs_monitor.performance_monitor.get_cache_analysis()
            backend_health = self.vfs_monitor.performance_monitor.get_backend_health_status()
            
            # Generate performance insights
            insights = self._generate_vfs_performance_insights(analytics)
            recommendations = self._generate_vfs_optimization_recommendations(analytics)
            
            # Get historical trends from collected metrics
            trends = self._analyze_vfs_trends()
            
            return {
                'available': True,
                'timestamp': time.time(),
                'comprehensive_report': analytics,
                'detailed_analyses': {
                    'bandwidth': bandwidth_analysis,
                    'operations': operation_analysis,
                    'realtime': realtime_metrics,
                    'replication': replication_health,
                    'cache': cache_analysis,
                    'backends': backend_health
                },
                'insights': insights,
                'recommendations': recommendations,
                'trends': trends,
                'health_summary': self._generate_vfs_health_summary(analytics)
            }
            
        except Exception as e:
            logger.error(f"Error getting VFS deep insights: {e}")
            return {
                'available': False,
                'error': str(e)
            }
    
    def _generate_vfs_performance_insights(self, analytics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate performance insights from VFS analytics."""
        insights = []
        
        try:
            # Analyze error patterns
            realtime = analytics.get('realtime_metrics', {})
            error_rate = realtime.get('error_rate', 0)
            ops_per_sec = realtime.get('operations_per_second', 0)
            
            if error_rate > 0.05:  # 5% error rate
                insights.append({
                    'type': 'performance_issue',
                    'severity': 'high' if error_rate > 0.2 else 'medium',
                    'category': 'error_rate',
                    'title': 'High VFS Error Rate',
                    'description': f'VFS operations are failing at {error_rate:.1%} rate',
                    'impact': 'Degraded user experience and potential data access issues',
                    'metrics': {'error_rate': error_rate, 'ops_per_second': ops_per_sec}
                })
            
            # Analyze throughput patterns
            if ops_per_sec > 100:
                insights.append({
                    'type': 'performance_pattern',
                    'severity': 'info',
                    'category': 'high_throughput',
                    'title': 'High VFS Throughput',
                    'description': f'VFS is processing {ops_per_sec:.1f} operations per second',
                    'impact': 'System is under heavy load - monitor for bottlenecks',
                    'metrics': {'operations_per_second': ops_per_sec}
                })
            elif ops_per_sec < 0.1 and self.is_running:
                insights.append({
                    'type': 'performance_issue',
                    'severity': 'medium',
                    'category': 'low_activity',
                    'title': 'Low VFS Activity',
                    'description': f'VFS activity is very low ({ops_per_sec:.1f} ops/sec)',
                    'impact': 'May indicate connectivity issues or system underutilization',
                    'metrics': {'operations_per_second': ops_per_sec}
                })
            
            # Analyze bandwidth patterns
            bandwidth = analytics.get('bandwidth_analysis', {})
            if bandwidth and 'total_average_bps' in bandwidth:
                total_bps = bandwidth['total_average_bps']
                if total_bps > 50 * 1024 * 1024:  # 50MB/s
                    insights.append({
                        'type': 'resource_usage',
                        'severity': 'medium',
                        'category': 'high_bandwidth',
                        'title': 'High Bandwidth Usage',
                        'description': f'VFS bandwidth usage: {total_bps / (1024*1024):.1f} MB/s',
                        'impact': 'High network utilization - may affect other services',
                        'metrics': {'bandwidth_mbps': total_bps / (1024*1024)}
                    })
            
            # Analyze cache performance
            cache = analytics.get('cache_analysis', {})
            if cache and 'current_metrics' in cache:
                hit_rate = cache['current_metrics'].get('hit_rate', 0)
                utilization = cache['current_metrics'].get('utilization', 0)
                
                if hit_rate < 0.7:  # 70% hit rate
                    insights.append({
                        'type': 'performance_issue',
                        'severity': 'medium',
                        'category': 'cache_efficiency',
                        'title': 'Low Cache Hit Rate',
                        'description': f'VFS cache hit rate is {hit_rate:.1%}',
                        'impact': 'Increased latency and backend load',
                        'metrics': {'cache_hit_rate': hit_rate, 'cache_utilization': utilization}
                    })
                
                if utilization > 0.9:  # 90% cache utilization
                    insights.append({
                        'type': 'resource_constraint',
                        'severity': 'warning',
                        'category': 'cache_pressure',
                        'title': 'High Cache Memory Pressure',
                        'description': f'VFS cache utilization is {utilization:.1%}',
                        'impact': 'Cache evictions may increase, reducing efficiency',
                        'metrics': {'cache_analysis': utilization}
                    })
            
            # Analyze replication health
            replication = analytics.get('replication_health', {})
            if replication and 'current_status' in replication:
                health_pct = replication['current_status'].get('health_percentage', 100)
                sync_lag = replication['current_status'].get('sync_lag_seconds', 0)
                
                if health_pct < 80:  # 80% healthy replicas
                    insights.append({
                        'type': 'availability_issue',
                        'severity': 'high' if health_pct < 50 else 'medium',
                        'category': 'replication_health',
                        'title': 'Replication Health Issues',
                        'description': f'Only {health_pct:.1f}% of replicas are healthy',
                        'impact': 'Reduced data redundancy and potential data loss risk',
                        'metrics': {'replication_health_percentage': health_pct}
                    })
                
                if sync_lag > 300:  # 5 minutes
                    insights.append({
                        'type': 'performance_issue',
                        'severity': 'medium',
                        'category': 'sync_lag',
                        'title': 'High Replication Sync Lag',
                        'description': f'Replication sync lag is {sync_lag:.1f} seconds',
                        'impact': 'Data consistency issues and delayed propagation',
                        'metrics': {'sync_lag_seconds': sync_lag}
                    })
            
            # Analyze backend health
            backend_health = analytics.get('backend_health', {})
            if backend_health and 'backends' in backend_health::
                summary = backend_health.get('summary', {})
                self._add_metric("vfs_backend_total_count", summary.get('total_backends', 0))
                self._add_metric("vfs_backend_healthy_count", summary.get('healthy_backends', 0))
                self._add_metric("vfs_backend_unhealthy_count", summary.get('unhealthy_backends', 0))
                self._add_metric("vfs_backend_health_percentage", summary.get('health_percentage', 0))
                
                for backend_name, backend_status in backend_health['backends'].items():
                    tags = {"backend": backend_name}
                    self._add_metric("vfs_backend_healthy", 1 if backend_status.get('healthy', False) else 0, tags)
                    self._add_metric("vfs_backend_last_check_age_seconds", 
                                   backend_status.get('last_check_age_seconds', 0), tags)
                    self._add_metric("vfs_backend_is_stale", 1 if backend_status.get('is_stale', False) else 0, tags)
                    
                    if backend_status.get('average_latency_ms') is not None:
                        self._add_metric("vfs_backend_avg_latency_ms", 
                                       backend_status['average_latency_ms'], tags)
                    if backend_status.get('p95_latency_ms') is not None:
                        self._add_metric("vfs_backend_p95_latency_ms", 
                                       backend_status['p95_latency_ms'], tags)
            
            # Process alerts
            alerts = analytics.get('alerts', [])
            self._add_metric("vfs_active_alerts_total", len(alerts))
            
            # Count alerts by severity
            alert_counts = {'critical': 0, 'warning': 0, 'info': 0}
            for alert in alerts:
                severity = alert.get('severity', 'info')
                if severity in alert_counts:
                    alert_counts[severity] += 1
            
            for severity, count in alert_counts.items():
                self._add_metric("vfs_alerts_by_severity", count, {"severity": severity})
                
        except Exception as e:
            logger.error(f"Failed to collect VFS analytics data: {e}")
    
    def _add_metric(self, name: str, value: Any, tags: Optional[Dict[str, str]] = None) -> None:
        """Add a metric data point."""
        if name not in self.metrics:
            self.metrics[name] = MetricSeries(name=name)
        
        self.metrics[name].add_point(value, tags)
        
        # Limit the number of data points to prevent memory issues
        max_points = self.config.max_data_points
        if len(self.metrics[name].data_points) > max_points:
            # Remove oldest points
            self.metrics[name].data_points = self.metrics[name].data_points[-max_points:]
    
    async def _cleanup_old_data(self) -> None:
        """Clean up old data points."""
        for metric in self.metrics.values():
            metric.cleanup_old_data(self.config.data_retention_hours)
    
    def get_metrics(self) -> Dict[str, MetricSeries]:
        """Get all collected metrics."""
        return self.metrics.copy()
    
    def get_metric(self, name: str) -> Optional[MetricSeries]:
        """Get a specific metric by name."""
        return self.metrics.get(name)
    
    def get_latest_values(self) -> Dict[str, Any]:
        """Get the latest values for all metrics."""
        latest = {}
        for name, metric in self.metrics.items():
            latest_point = metric.get_latest()
            if latest_point:
                latest[name] = {
                    "value": latest_point.value,
                    "timestamp": latest_point.timestamp,
                    "tags": latest_point.tags
                }
        return latest
    
    def get_metric_summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics."""
        return {
            "total_metrics": len(self.metrics),
            "total_data_points": sum(len(metric.data_points) for metric in self.metrics.values()),
            "collection_errors": self.error_count,
            "last_error_time": self.last_error_time,
            "is_running": self.is_running,
            "metrics_list": list(self.metrics.keys())
        }
    
    async def get_vfs_deep_insights(self) -> Dict[str, Any]:
        """Get comprehensive VFS insights and analysis."""
        if not self.has_vfs_analytics:
            return {
                'available': False,
                'error': 'VFS analytics not available'
            }
        
        if not self.vfs_monitor: # Added check for vfs_monitor
            return {
                'available': False,
                'error': 'VFS monitor not initialized'
            }

        try:
            # Get comprehensive analytics from VFS monitor
            analytics = self.vfs_monitor.get_analytics_summary()
            
            # Get additional detailed analyses
            bandwidth_analysis = self.vfs_monitor.performance_monitor.get_bandwidth_analysis(60)
            operation_analysis = self.vfs_monitor.performance_monitor.get_operation_analysis(60)
            realtime_metrics = self.vfs_monitor.performance_monitor.get_realtime_metrics()
            replication_health = self.vfs_monitor.performance_monitor.get_replication_health()
            cache_analysis = self.vfs_monitor.performance_monitor.get_cache_analysis()
            backend_health = self.vfs_monitor.performance_monitor.get_backend_health_status()
            
            # Generate performance insights
            insights = self._generate_vfs_performance_insights(analytics)
            recommendations = self._generate_vfs_optimization_recommendations(analytics)
            
            # Get historical trends from collected metrics
            trends = self._analyze_vfs_trends()
            
            return {
                'available': True,
                'timestamp': time.time(),
                'comprehensive_report': analytics,
                'detailed_analyses': {
                    'bandwidth': bandwidth_analysis,
                    'operations': operation_analysis,
                    'realtime': realtime_metrics,
                    'replication': replication_health,
                    'cache': cache_analysis,
                    'backends': backend_health
                },
                'insights': insights,
                'recommendations': recommendations,
                'trends': trends,
                'health_summary': self._generate_vfs_health_summary(analytics)
            }
            
        except Exception as e:
            logger.error(f"Error getting VFS deep insights: {e}")
            return {
                'available': False,
                'error': str(e)
            }
    
    def _generate_vfs_performance_insights(self, analytics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate performance insights from VFS analytics."""
        insights = []
        
        try:
            # Analyze error patterns
            realtime = analytics.get('realtime_metrics', {})
            error_rate = realtime.get('error_rate', 0)
            ops_per_sec = realtime.get('operations_per_second', 0)
            
            if error_rate > 0.05:  # 5% error rate
                insights.append({
                    'type': 'performance_issue',
                    'severity': 'high' if error_rate > 0.2 else 'medium',
                    'category': 'error_rate',
                    'title': 'High VFS Error Rate',
                    'description': f'VFS operations are failing at {error_rate:.1%} rate',
                    'impact': 'Degraded user experience and potential data access issues',
                    'metrics': {'error_rate': error_rate, 'ops_per_second': ops_per_sec}
                })
            
            # Analyze throughput patterns
            if ops_per_sec > 100:
                insights.append({
                    'type': 'performance_pattern',
                    'severity': 'info',
                    'category': 'high_throughput',
                    'title': 'High VFS Throughput',
                    'description': f'VFS is processing {ops_per_sec:.1f} operations per second',
                    'impact': 'System is under heavy load - monitor for bottlenecks',
                    'metrics': {'operations_per_second': ops_per_sec}
                })
            elif ops_per_sec < 0.1 and self.is_running:
                insights.append({
                    'type': 'performance_issue',
                    'severity': 'medium',
                    'category': 'low_activity',
                    'title': 'Low VFS Activity',
                    'description': f'VFS activity is very low ({ops_per_sec:.1f} ops/sec)',
                    'impact': 'May indicate connectivity issues or system underutilization',
                    'metrics': {'operations_per_second': ops_per_sec}
                })
            
            # Analyze bandwidth patterns
            bandwidth = analytics.get('bandwidth_analysis', {})
            if bandwidth and 'total_average_bps' in bandwidth:
                total_bps = bandwidth['total_average_bps']
                if total_bps > 50 * 1024 * 1024:  # 50MB/s
                    insights.append({
                        'type': 'resource_usage',
                        'severity': 'medium',
                        'category': 'high_bandwidth',
                        'title': 'High Bandwidth Usage',
                        'description': f'VFS bandwidth usage: {total_bps / (1024*1024):.1f} MB/s',
                        'impact': 'High network utilization - may affect other services',
                        'metrics': {'bandwidth_mbps': total_bps / (1024*1024)}
                    })
            
            # Analyze cache performance
            cache = analytics.get('cache_analysis', {})
            if cache and 'current_metrics' in cache:
                hit_rate = cache['current_metrics'].get('hit_rate', 0)
                utilization = cache['current_metrics'].get('utilization', 0)
                
                if hit_rate < 0.7:  # 70% hit rate
                    insights.append({
                        'type': 'performance_issue',
                        'severity': 'medium',
                        'category': 'cache_efficiency',
                        'title': 'Low Cache Hit Rate',
                        'description': f'VFS cache hit rate is {hit_rate:.1%}',
                        'impact': 'Increased latency and backend load',
                        'metrics': {'cache_hit_rate': hit_rate, 'cache_utilization': utilization}
                    })
                
                if utilization > 0.9:  # 90% cache utilization
                    insights.append({
                        'type': 'resource_constraint',
                        'severity': 'warning',
                        'category': 'cache_pressure',
                        'title': 'High Cache Memory Pressure',
                        'description': f'VFS cache utilization is {utilization:.1%}',
                        'impact': 'Cache evictions may increase, reducing efficiency',
                        'metrics': {'cache_analysis': utilization}
                    })
            
            # Analyze replication health
            replication = analytics.get('replication_health', {})
            if replication and 'current_status' in replication:
                health_pct = replication['current_status'].get('health_percentage', 100)
                sync_lag = replication['current_status'].get('sync_lag_seconds', 0)
                
                if health_pct < 80:  # 80% healthy replicas
                    insights.append({
                        'type': 'availability_issue',
                        'severity': 'high' if health_pct < 50 else 'medium',
                        'category': 'replication_health',
                        'title': 'Replication Health Issues',
                        'description': f'Only {health_pct:.1f}% of replicas are healthy',
                        'impact': 'Reduced data redundancy and potential data loss risk',
                        'metrics': {'replication_health_percentage': health_pct}
                    })
                
                if sync_lag > 300:  # 5 minutes
                    insights.append({
                        'type': 'performance_issue',
                        'severity': 'medium',
                        'category': 'sync_lag',
                        'title': 'High Replication Sync Lag',
                        'description': f'Replication sync lag is {sync_lag:.1f} seconds',
                        'impact': 'Data consistency issues and delayed propagation',
                        'metrics': {'sync_lag_seconds': sync_lag}
                    })
            
            # Analyze backend health
            backend_health = analytics.get('backend_health', {})
            if backend_health and 'backends' in backend_health::
                summary = backend_health.get('summary', {})
                self._add_metric("vfs_backend_total_count", summary.get('total_backends', 0))
                self._add_metric("vfs_backend_healthy_count", summary.get('healthy_backends', 0))
                self._add_metric("vfs_backend_unhealthy_count", summary.get('unhealthy_backends', 0))
                self._add_metric("vfs_backend_health_percentage", summary.get('health_percentage', 0))
                
                for backend_name, backend_status in backend_health['backends'].items():
                    tags = {"backend": backend_name}
                    self._add_metric("vfs_backend_healthy", 1 if backend_status.get('healthy', False) else 0, tags)
                    self._add_metric("vfs_backend_last_check_age_seconds", 
                                   backend_status.get('last_check_age_seconds', 0), tags)
                    self._add_metric("vfs_backend_is_stale", 1 if backend_status.get('is_stale', False) else 0, tags)
                    
                    if backend_status.get('average_latency_ms') is not None:
                        self._add_metric("vfs_backend_avg_latency_ms", 
                                       backend_status['average_latency_ms'], tags)
                    if backend_status.get('p95_latency_ms') is not None:
                        self._add_metric("vfs_backend_p95_latency_ms", 
                                       backend_status['p95_latency_ms'], tags)
            
            # Process alerts
            alerts = analytics.get('alerts', [])
            self._add_metric("vfs_active_alerts_total", len(alerts))
            
            # Count alerts by severity
            alert_counts = {'critical': 0, 'warning': 0, 'info': 0}
            for alert in alerts:
                severity = alert.get('severity', 'info')
                if severity in alert_counts:
                    alert_counts[severity] += 1
            
            for severity, count in alert_counts.items():
                self._add_metric("vfs_alerts_by_severity", count, {"severity": severity})
                
        except Exception as e:
            logger.error(f"Failed to collect VFS analytics data: {e}")
    
    def _add_metric(self, name: str, value: Any, tags: Optional[Dict[str, str]] = None) -> None:
        """Add a metric data point."""
        if name not in self.metrics:
            self.metrics[name] = MetricSeries(name=name)
        
        self.metrics[name].add_point(value, tags)
        
        # Limit the number of data points to prevent memory issues
        max_points = self.config.max_data_points
        if len(self.metrics[name].data_points) > max_points:
            # Remove oldest points
            self.metrics[name].data_points = self.metrics[name].data_points[-max_points:]
    
    async def _cleanup_old_data(self) -> None:
        """Clean up old data points."""
        for metric in self.metrics.values():
            metric.cleanup_old_data(self.config.data_retention_hours)
    
    def get_metrics(self) -> Dict[str, MetricSeries]:
        """Get all collected metrics."""
        return self.metrics.copy()
    
    def get_metric(self, name: str) -> Optional[MetricSeries]:
        """Get a specific metric by name."""
        return self.metrics.get(name)
    
    def get_latest_values(self) -> Dict[str, Any]:
        """Get the latest values for all metrics."""
        latest = {}
        for name, metric in self.metrics.items():
            latest_point = metric.get_latest()
            if latest_point:
                latest[name] = {
                    "value": latest_point.value,
                    "timestamp": latest_point.timestamp,
                    "tags": latest_point.tags
                }
        return latest
    
    def get_metric_summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics."""
        return {
            "total_metrics": len(self.metrics),
            "total_data_points": sum(len(metric.data_points) for metric in self.metrics.values()),
            "collection_errors": self.error_count,
            "last_error_time": self.last_error_time,
            "is_running": self.is_running,
            "metrics_list": list(self.metrics.keys())
        }
    
    async def get_vfs_deep_insights(self) -> Dict[str, Any]:
        """Get comprehensive VFS insights and analysis."""
        if not self.has_vfs_analytics:
            return {
                'available': False,
                'error': 'VFS analytics not available'
            }
        
        if not self.vfs_monitor: # Added check for vfs_monitor
            return {
                'available': False,
                'error': 'VFS monitor not initialized'
            }

        try:
            # Get comprehensive analytics from VFS monitor
            analytics = self.vfs_monitor.get_analytics_summary()
            
            # Get additional detailed analyses
            bandwidth_analysis = self.vfs_monitor.performance_monitor.get_bandwidth_analysis(60)
            operation_analysis = self.vfs_monitor.performance_monitor.get_operation_analysis(60)
            realtime_metrics = self.vfs_monitor.performance_monitor.get_realtime_metrics()
            replication_health = self.vfs_monitor.performance_monitor.get_replication_health()
            cache_analysis = self.vfs_monitor.performance_monitor.get_cache_analysis()
            backend_health = self.vfs_monitor.performance_monitor.get_backend_health_status()
            
            # Generate performance insights
            insights = self._generate_vfs_performance_insights(analytics)
            recommendations = self._generate_vfs_optimization_recommendations(analytics)
            
            # Get historical trends from collected metrics
            trends = self._analyze_vfs_trends()
            
            return {
                'available': True,
                'timestamp': time.time(),
                'comprehensive_report': analytics,
                'detailed_analyses': {
                    'bandwidth': bandwidth_analysis,
                    'operations': operation_analysis,
                    'realtime': realtime_metrics,
                    'replication': replication_health,
                    'cache': cache_analysis,
                    'backends': backend_health
                },
                'insights': insights,
                'recommendations': recommendations,
                'trends': trends,
                'health_summary': self._generate_vfs_health_summary(analytics)
            }
            
        except Exception as e:
            logger.error(f"Error getting VFS deep insights: {e}")
            return {
                'available': False,
                'error': str(e)
            }
    
    def _generate_vfs_performance_insights(self, analytics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate performance insights from VFS analytics."""
        insights = []
        
        try:
            # Analyze error patterns
            realtime = analytics.get('realtime_metrics', {})
            error_rate = realtime.get('error_rate', 0)
            ops_per_sec = realtime.get('operations_per_second', 0)
            
            if error_rate > 0.05:  # 5% error rate
                insights.append({
                    'type': 'performance_issue',
                    'severity': 'high' if error_rate > 0.2 else 'medium',
                    'category': 'error_rate',
                    'title': 'High VFS Error Rate',
                    'description': f'VFS operations are failing at {error_rate:.1%} rate',
                    'impact': 'Degraded user experience and potential data access issues',
                    'metrics': {'error_rate': error_rate, 'ops_per_second': ops_per_sec}
                })
            
            # Analyze throughput patterns
            if ops_per_sec > 100:
                insights.append({
                    'type': 'performance_pattern',
                    'severity': 'info',
                    'category': 'high_throughput',
                    'title': 'High VFS Throughput',
                    'description': f'VFS is processing {ops_per_sec:.1f} operations per second',
                    'impact': 'System is under heavy load - monitor for bottlenecks',
                    'metrics': {'operations_per_second': ops_per_sec}
                })
            elif ops_per_sec < 0.1 and self.is_running:
                insights.append({
                    'type': 'performance_issue',
                    'severity': 'medium',
                    'category': 'low_activity',
                    'title': 'Low VFS Activity',
                    'description': f'VFS activity is very low ({ops_per_sec:.1f} ops/sec)',
                    'impact': 'May indicate connectivity issues or system underutilization',
                    'metrics': {'operations_per_second': ops_per_sec}
                })
            
            # Analyze bandwidth patterns
            bandwidth = analytics.get('bandwidth_analysis', {})
            if bandwidth and 'total_average_bps' in bandwidth:
                total_bps = bandwidth['total_average_bps']
                if total_bps > 50 * 1024 * 1024:  # 50MB/s
                    insights.append({
                        'type': 'resource_usage',
                        'severity': 'medium',
                        'category': 'high_bandwidth',
                        'title': 'High Bandwidth Usage',
                        'description': f'VFS bandwidth usage: {total_bps / (1024*1024):.1f} MB/s',
                        'impact': 'High network utilization - may affect other services',
                        'metrics': {'bandwidth_mbps': total_bps / (1024*1024)}
                    })
            
            # Analyze cache performance
            cache = analytics.get('cache_analysis', {})
            if cache and 'current_metrics' in cache:
                hit_rate = cache['current_metrics'].get('hit_rate', 0)
                utilization = cache['current_metrics'].get('utilization', 0)
                
                if hit_rate < 0.7:  # 70% hit rate
                    insights.append({
                        'type': 'performance_issue',
                        'severity': 'medium',
                        'category': 'cache_efficiency',
                        'title': 'Low Cache Hit Rate',
                        'description': f'VFS cache hit rate is {hit_rate:.1%}',
                        'impact': 'Increased latency and backend load',
                        'metrics': {'cache_hit_rate': hit_rate, 'cache_utilization': utilization}
                    })
                
                if utilization > 0.9:  # 90% cache utilization
                    insights.append({
                        'type': 'resource_constraint',
                        'severity': 'warning',
                        'category': 'cache_pressure',
                        'title': 'High Cache Memory Pressure',
                        'description': f'VFS cache utilization is {utilization:.1%}',
                        'impact': 'Cache evictions may increase, reducing efficiency',
                        'metrics': {'cache_analysis': utilization}
                    })
            
            # Analyze replication health
            replication = analytics.get('replication_health', {})
            if replication and 'current_status' in replication:
                health_pct = replication['current_status'].get('health_percentage', 100)
                sync_lag = replication['current_status'].get('sync_lag_seconds', 0)
                
                if health_pct < 80:  # 80% healthy replicas
                    insights.append({
                        'type': 'availability_issue',
                        'severity': 'high' if health_pct < 50 else 'medium',
                        'category': 'replication_health',
                        'title': 'Replication Health Issues',
                        'description': f'Only {health_pct:.1f}% of replicas are healthy',
                        'impact': 'Reduced data redundancy and potential data loss risk',
                        'metrics': {'replication_health_percentage': health_pct}
                    })
                
                if sync_lag > 300:  # 5 minutes
                    insights.append({
                        'type': 'performance_issue',
                        'severity': 'medium',
                        'category': 'sync_lag',
                        'title': 'High Replication Sync Lag',
                        'description': f'Replication sync lag is {sync_lag:.1f} seconds',
                        'impact': 'Data consistency issues and delayed propagation',
                        'metrics': {'sync_lag_seconds': sync_lag}
                    })
            
            # Analyze backend health
            backend_health = analytics.get('backend_health', {})
            if backend_health and 'backends' in backend_health::
                summary = backend_health.get('summary', {})
                self._add_metric("vfs_backend_total_count", summary.get('total_backends', 0))
                self._add_metric("vfs_backend_healthy_count", summary.get('healthy_backends', 0))
                self._add_metric("vfs_backend_unhealthy_count", summary.get('unhealthy_backends', 0))
                self._add_metric("vfs_backend_health_percentage", summary.get('health_percentage', 0))
                
                for backend_name, backend_status in backend_health['backends'].items():
                    tags = {"backend": backend_name}
                    self._add_metric("vfs_backend_healthy", 1 if backend_status.get('healthy', False) else 0, tags)
                    self._add_metric("vfs_backend_last_check_age_seconds", 
                                   backend_status.get('last_check_age_seconds', 0), tags)
                    self._add_metric("vfs_backend_is_stale", 1 if backend_status.get('is_stale', False) else 0, tags)
                    
                    if backend_status.get('average_latency_ms') is not None:
                        self._add_metric("vfs_backend_avg_latency_ms", 
                                       backend_status['average_latency_ms'], tags)
                    if backend_status.get('p95_latency_ms') is not None:
                        self._add_metric("vfs_backend_p95_latency_ms", 
                                       backend_status['p95_latency_ms'], tags)
            
            # Process alerts
            alerts = analytics.get('alerts', [])
            self._add_metric("vfs_active_alerts_total", len(alerts))
            
            # Count alerts by severity
            alert_counts = {'critical': 0, 'warning': 0, 'info': 0}
            for alert in alerts:
                severity = alert.get('severity', 'info')
                if severity in alert_counts:
                    alert_counts[severity] += 1
            
            for severity, count in alert_counts.items():
                self._add_metric("vfs_alerts_by_severity", count, {"severity": severity})
                
        except Exception as e:
            logger.error(f"Failed to collect VFS analytics data: {e}")
    
    def _add_metric(self, name: str, value: Any, tags: Optional[Dict[str, str]] = None) -> None:
        """Add a metric data point."""
        if name not in self.metrics:
            self.metrics[name] = MetricSeries(name=name)
        
        self.metrics[name].add_point(value, tags)
        
        # Limit the number of data points to prevent memory issues
        max_points = self.config.max_data_points
        if len(self.metrics[name].data_points) > max_points:
            # Remove oldest points
            self.metrics[name].data_points = self.metrics[name].data_points[-max_points:]
    
    async def _cleanup_old_data(self) -> None:
        """Clean up old data points."""
        for metric in self.metrics.values():
            metric.cleanup_old_data(self.config.data_retention_hours)
    
    def get_metrics(self) -> Dict[str, MetricSeries]:
        """Get all collected metrics."""
        return self.metrics.copy()
    
    def get_metric(self, name: str) -> Optional[MetricSeries]:
        """Get a specific metric by name."""
        return self.metrics.get(name)
    
    def get_latest_values(self) -> Dict[str, Any]:
        """Get the latest values for all metrics."""
        latest = {}
        for name, metric in self.metrics.items():
            latest_point = metric.get_latest()
            if latest_point:
                latest[name] = {
                    "value": latest_point.value,
                    "timestamp": latest_point.timestamp,
                    "tags": latest_point.tags
                }
        return latest
    
    def get_metric_summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics."""
        return {
            "total_metrics": len(self.metrics),
            "total_data_points": sum(len(metric.data_points) for metric in self.metrics.values()),
            "collection_errors": self.error_count,
            "last_error_time": self.last_error_time,
            "is_running": self.is_running,
            "metrics_list": list(self.metrics.keys())
        }
    
    async def get_vfs_deep_insights(self) -> Dict[str, Any]:
        """Get comprehensive VFS insights and analysis."""
        if not self.has_vfs_analytics:
            return {
                'available': False,
                'error': 'VFS analytics not available'
            }
        
        if not self.vfs_monitor: # Added check for vfs_monitor
            return {
                'available': False,
                'error': 'VFS monitor not initialized'
            }

        try:
            # Get comprehensive analytics from VFS monitor
            analytics = self.vfs_monitor.get_analytics_summary()
            
            # Get additional detailed analyses
            bandwidth_analysis = self.vfs_monitor.performance_monitor.get_bandwidth_analysis(60)
            operation_analysis = self.vfs_monitor.performance_monitor.get_operation_analysis(60)
            realtime_metrics = self.vfs_monitor.performance_monitor.get_realtime_metrics()
            replication_health = self.vfs_monitor.performance_monitor.get_replication_health()
            cache_analysis = self.vfs_monitor.performance_monitor.get_cache_analysis()
            backend_health = self.vfs_monitor.performance_monitor.get_backend_health_status()
            
            # Generate performance insights
            insights = self._generate_vfs_performance_insights(analytics)
            recommendations = self._generate_vfs_optimization_recommendations(analytics)
            
            # Get historical trends from collected metrics
            trends = self._analyze_vfs_trends()
            
            return {
                'available': True,
                'timestamp': time.time(),
                'comprehensive_report': analytics,
                'detailed_analyses': {
                    'bandwidth': bandwidth_analysis,
                    'operations': operation_analysis,
                    'realtime': realtime_metrics,
                    'replication': replication_health,
                    'cache': cache_analysis,
                    'backends': backend_health
                },
                'insights': insights,
                'recommendations': recommendations,
                'trends': trends,
                'health_summary': self._generate_vfs_health_summary(analytics)
            }
            
        except Exception as e:
            logger.error(f"Error getting VFS deep insights: {e}")
            return {
                'available': False,
                'error': str(e)
            }
    
    def _generate_vfs_performance_insights(self, analytics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate performance insights from VFS analytics."""
        insights = []
        
        try:
            # Analyze error patterns
            realtime = analytics.get('realtime_metrics', {})
            error_rate = realtime.get('error_rate', 0)
            ops_per_sec = realtime.get('operations_per_second', 0)
            
            if error_rate > 0.05:  # 5% error rate
                insights.append({
                    'type': 'performance_issue',
                    'severity': 'high' if error_rate > 0.2 else 'medium',
                    'category': 'error_rate',
                    'title': 'High VFS Error Rate',
                    'description': f'VFS operations are failing at {error_rate:.1%} rate',
                    'impact': 'Degraded user experience and potential data access issues',
                    'metrics': {'error_rate': error_rate, 'ops_per_second': ops_per_sec}
                })
            
            # Analyze throughput patterns
            if ops_per_sec > 100:
                insights.append({
                    'type': 'performance_pattern',
                    'severity': 'info',
                    'category': 'high_throughput',
                    'title': 'High VFS Throughput',
                    'description': f'VFS is processing {ops_per_sec:.1f} operations per second',
                    'impact': 'System is under heavy load - monitor for bottlenecks',
                    'metrics': {'operations_per_second': ops_per_sec}
                })
            elif ops_per_sec < 0.1 and self.is_running:
                insights.append({
                    'type': 'performance_issue',
                    'severity': 'medium',
                    'category': 'low_activity',
                    'title': 'Low VFS Activity',
                    'description': f'VFS activity is very low ({ops_per_sec:.1f} ops/sec)',
                    'impact': 'May indicate connectivity issues or system underutilization',
                    'metrics': {'operations_per_second': ops_per_sec}
                })
            
            # Analyze bandwidth patterns
            bandwidth = analytics.get('bandwidth_analysis', {})
            if bandwidth and 'total_average_bps' in bandwidth:
                total_bps = bandwidth['total_average_bps']
                if total_bps > 50 * 1024 * 1024:  # 50MB/s
                    insights.append({
                        'type': 'resource_usage',
                        'severity': 'medium',
                        'category': 'high_bandwidth',
                        'title': 'High Bandwidth Usage',
                        'description': f'VFS bandwidth usage: {total_bps / (1024*1024):.1f} MB/s',
                        'impact': 'High network utilization - may affect other services',
                        'metrics': {'bandwidth_mbps': total_bps / (1024*1024)}
                    })
            
            # Analyze cache performance
            cache = analytics.get('cache_analysis', {})
            if cache and 'current_metrics' in cache:
                hit_rate = cache['current_metrics'].get('hit_rate', 0)
                utilization = cache['current_metrics'].get('utilization', 0)
                
                if hit_rate < 0.7:  # 70% hit rate
                    insights.append({
                        'type': 'performance_issue',
                        'severity': 'medium',
                        'category': 'cache_efficiency',
                        'title': 'Low Cache Hit Rate',
                        'description': f'VFS cache hit rate is {hit_rate:.1%}',
                        'impact': 'Increased latency and backend load',
                        'metrics': {'cache_hit_rate': hit_rate, 'cache_utilization': utilization}
                    })
                
                if utilization > 0.9:  # 90% cache utilization
                    insights.append({
                        'type': 'resource_constraint',
                        'severity': 'warning',
                        'category': 'cache_pressure',
                        'title': 'High Cache Memory Pressure',
                        'description': f'VFS cache utilization is {utilization:.1%}',
                        'impact': 'Cache evictions may increase, reducing efficiency',
                        'metrics': {'cache_analysis': utilization}
                    })
            
            # Analyze replication health
            replication = analytics.get('replication_health', {})
            if replication and 'current_status' in replication:
                health_pct = replication['current_status'].get('health_percentage', 100)
                sync_lag = replication['current_status'].get('sync_lag_seconds', 0)
                
                if health_pct < 80:  # 80% healthy replicas
                    insights.append({
                        'type': 'availability_issue',
                        'severity': 'high' if health_pct < 50 else 'medium',
                        'category': 'replication_health',
                        'title': 'Replication Health Issues',
                        'description': f'Only {health_pct:.1f}% of replicas are healthy',
                        'impact': 'Reduced data redundancy and potential data loss risk',
                        'metrics': {'replication_health_percentage': health_pct}
                    })
                
                if sync_lag > 300:  # 5 minutes
                    insights.append({
                        'type': 'performance_issue',
                        'severity': 'medium',
                        'category': 'sync_lag',
                        'title': 'High Replication Sync Lag',
                        'description': f'Replication sync lag is {sync_lag:.1f} seconds',
                        'impact': 'Data consistency issues and delayed propagation',
                        'metrics': {'sync_lag_seconds': sync_lag}
                    })
            
            # Analyze backend health
            backend_health = analytics.get('backend_health', {})
            if backend_health and 'backends' in backend_health::
                summary = backend_health.get('summary', {})
                self._add_metric("vfs_backend_total_count", summary.get('total_backends', 0))
                self._add_metric("vfs_backend_healthy_count", summary.get('healthy_backends', 0))
                self._add_metric("vfs_backend_unhealthy_count", summary.get('unhealthy_backends', 0))
                self._add_metric("vfs_backend_health_percentage", summary.get('health_percentage', 0))
                
                for backend_name, backend_status in backend_health['backends'].items():
                    tags = {"backend": backend_name}
                    self._add_metric("vfs_backend_healthy", 1 if backend_status.get('healthy', False) else 0, tags)
                    self._add_metric("vfs_backend_last_check_age_seconds", 
                                   backend_status.get('last_check_age_seconds', 0), tags)
                    self._add_metric("vfs_backend_is_stale", 1 if backend_status.get('is_stale', False) else 0, tags)
                    
                    if backend_status.get('average_latency_ms') is not None:
                        self._add_metric("vfs_backend_avg_latency_ms", 
                                       backend_status['average_latency_ms'], tags)
                    if backend_status.get('p95_latency_ms') is not None:
                        self._add_metric("vfs_backend_p95_latency_ms", 
                                       backend_status['p95_latency_ms'], tags)
            
            # Process alerts
            alerts = analytics.get('alerts', [])
            self._add_metric("vfs_active_alerts_total", len(alerts))
            
            # Count alerts by severity
            alert_counts = {'critical': 0, 'warning': 0, 'info': 0}
            for alert in alerts:
                severity = alert.get('severity', 'info')
                if severity in alert_counts:
                    alert_counts[severity] += 1
            
            for severity, count in alert_counts.items():
                self._add_metric("vfs_alerts_by_severity", count, {"severity": severity})
                
        except Exception as e:
            logger.error(f"Failed to collect VFS analytics data: {e}")
    
    def _add_metric(self, name: str, value: Any, tags: Optional[Dict[str, str]] = None) -> None:
        """Add a metric data point."""
        if name not in self.metrics:
            self.metrics[name] = MetricSeries(name=name)
        
        self.metrics[name].add_point(value, tags)
        
        # Limit the number of data points to prevent memory issues
        max_points = self.config.max_data_points
        if len(self.metrics[name].data_points) > max_points:
            # Remove oldest points
            self.metrics[name].data_points = self.metrics[name].data_points[-max_points:]
    
    async def _cleanup_old_data(self) -> None:
        """Clean up old data points."""
        for metric in self.metrics.values():
            metric.cleanup_old_data(self.config.data_retention_hours)
    
    def get_metrics(self) -> Dict[str, MetricSeries]:
        """Get all collected metrics."""
        return self.metrics.copy()
    
    def get_metric(self, name: str) -> Optional[MetricSeries]:
        """Get a specific metric by name."""
        return self.metrics.get(name)
    
    def get_latest_values(self) -> Dict[str, Any]:
        """Get the latest values for all metrics."""
        latest = {}
        for name, metric in self.metrics.items():
            latest_point = metric.get_latest()
            if latest_point:
                latest[name] = {
                    "value": latest_point.value,
                    "timestamp": latest_point.timestamp,
                    "tags": latest_point.tags
                }
        return latest
    
    def get_metric_summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics."""
        return {
            "total_metrics": len(self.metrics),
            "total_data_points": sum(len(metric.data_points) for metric in self.metrics.values()),
            "collection_errors": self.error_count,
            "last_error_time": self.last_error_time,
            "is_running": self.is_running,
            "metrics_list": list(self.metrics.keys())
        }
    
    async def get_vfs_deep_insights(self) -> Dict[str, Any]:
        """Get comprehensive VFS insights and analysis."""
        if not self.has_vfs_analytics:
            return {
                'available': False,
                'error': 'VFS analytics not available'
            }
        
        if not self.vfs_monitor: # Added check for vfs_monitor
            return {
                'available': False,
                'error': 'VFS monitor not initialized'
            }

        try:
            # Get comprehensive analytics from VFS monitor
            analytics = self.vfs_monitor.get_analytics_summary()
            
            # Get additional detailed analyses
            bandwidth_analysis = self.vfs_monitor.performance_monitor.get_bandwidth_analysis(60)
            operation_analysis = self.vfs_monitor.performance_monitor.get_operation_analysis(60)
            realtime_metrics = self.vfs_monitor.performance_monitor.get_realtime_metrics()
            replication_health = self.vfs_monitor.performance_monitor.get_replication_health()
            cache_analysis = self.vfs_monitor.performance_monitor.get_cache_analysis()
            backend_health = self.vfs_monitor.performance_monitor.get_backend_health_status()
            
            # Generate performance insights
            insights = self._generate_vfs_performance_insights(analytics)
            recommendations = self._generate_vfs_optimization_recommendations(analytics)
            
            # Get historical trends from collected metrics
            trends = self._analyze_vfs_trends()
            
            return {
                'available': True,
                'timestamp': time.time(),
                'comprehensive_report': analytics,
                'detailed_analyses': {
                    'bandwidth': bandwidth_analysis,
                    'operations': operation_analysis,
                    'realtime': realtime_metrics,
                    'replication': replication_health,
                    'cache': cache_analysis,
                    'backends': backend_health
                },
                'insights': insights,
                'recommendations': recommendations,
                'trends': trends,
                'health_summary': self._generate_vfs_health_summary(analytics)
            }
            
        except Exception as e:
            logger.error(f"Error getting VFS deep insights: {e}")
            return {
                'available': False,
                'error': str(e)
            }
    
    def _generate_vfs_performance_insights(self, analytics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate performance insights from VFS analytics."""
        insights = []
        
        try:
            # Analyze error patterns
            realtime = analytics.get('realtime_metrics', {})
            error_rate = realtime.get('error_rate', 0)
            ops_per_sec = realtime.get('operations_per_second', 0)
            
            if error_rate > 0.05:  # 5% error rate
                insights.append({
                    'type': 'performance_issue',
                    'severity': 'high' if error_rate > 0.2 else 'medium',
                    'category': 'error_rate',
                    'title': 'High VFS Error Rate',
                    'description': f'VFS operations are failing at {error_rate:.1%} rate',
                    'impact': 'Degraded user experience and potential data access issues',
                    'metrics': {'error_rate': error_rate, 'ops_per_second': ops_per_sec}
                })
            
            # Analyze throughput patterns
            if ops_per_sec > 100:
                insights.append({
                    'type': 'performance_pattern',
                    'severity': 'info',
                    'category': 'high_throughput',
                    'title': 'High VFS Throughput',
                    'description': f'VFS is processing {ops_per_sec:.1f} operations per second',
                    'impact': 'System is under heavy load - monitor for bottlenecks',
                    'metrics': {'operations_per_second': ops_per_sec}
                })
            elif ops_per_sec < 0.1 and self.is_running:
                insights.append({
                    'type': 'performance_issue',
                    'severity': 'medium',
                    'category': 'low_activity',
                    'title': 'Low VFS Activity',
                    'description': f'VFS activity is very low ({ops_per_sec:.1f} ops/sec)',
                    'impact': 'May indicate connectivity issues or system underutilization',
                    'metrics': {'operations_per_second': ops_per_sec}
                })
            
            # Analyze bandwidth patterns
            bandwidth = analytics.get('bandwidth_analysis', {})
            if bandwidth and 'total_average_bps' in bandwidth:
                total_bps = bandwidth['total_average_bps']
                if total_bps > 50 * 1024 * 1024:  # 50MB/s
                    insights.append({
                        'type': 'resource_usage',
                        'severity': 'medium',
                        'category': 'high_bandwidth',
                        'title': 'High Bandwidth Usage',
                        'description': f'VFS bandwidth usage: {total_bps / (1024*1024):.1f} MB/s',
                        'impact': 'High network utilization - may affect other services',
                        'metrics': {'bandwidth_mbps': total_bps / (1024*1024)}
                    })
            
            # Analyze cache performance
            cache = analytics.get('cache_analysis', {})
            if cache and 'current_metrics' in cache:
                hit_rate = cache['current_metrics'].get('hit_rate', 0)
                utilization = cache['current_metrics'].get('utilization', 0)
                
                if hit_rate < 0.7:  # 70% hit rate
                    insights.append({
                        'type': 'performance_issue',
                        'severity': 'medium',
                        'category': 'cache_efficiency',
                        'title': 'Low Cache Hit Rate',
                        'description': f'VFS cache hit rate is {hit_rate:.1%}',
                        'impact': 'Increased latency and backend load',
                        'metrics': {'cache_hit_rate': hit_rate, 'cache_utilization': utilization}
                    })
                
                if utilization > 0.9:  # 90% cache utilization
                    insights.append({
                        'type': 'resource_constraint',
                        'severity': 'warning',
                        'category': 'cache_pressure',
                        'title': 'High Cache Memory Pressure',
                        'description': f'VFS cache utilization is {utilization:.1%}',
                        'impact': 'Cache evictions may increase, reducing efficiency',
                        'metrics': {'cache_analysis': utilization}
                    })
            
            # Analyze replication health
            replication = analytics.get('replication_health', {})
            if replication and 'current_status' in replication:
                health_pct = replication['current_status'].get('health_percentage', 100)
                sync_lag = replication['current_status'].get('sync_lag_seconds', 0)
                
                if health_pct < 80:  # 80% healthy replicas
                    insights.append({
                        'type': 'availability_issue',
                        'severity': 'high' if health_pct < 50 else 'medium',
                        'category': 'replication_health',
                        'title': 'Replication Health Issues',
                        'description': f'Only {health_pct:.1f}% of replicas are healthy',
                        'impact': 'Reduced data redundancy and potential data loss risk',
                        'metrics': {'replication_health_percentage': health_pct}
                    })
                
                if sync_lag > 300:  # 5 minutes
                    insights.append({
                        'type': 'performance_issue',
                        'severity': 'medium',
                        'category': 'sync_lag',
                        'title': 'High Replication Sync Lag',
                        'description': f'Replication sync lag is {sync_lag:.1f} seconds',
                        'impact': 'Data consistency issues and delayed propagation',
                        'metrics': {'sync_lag_seconds': sync_lag}
                    })
            
            # Analyze backend health
            backend_health = analytics.get('backend_health', {})
            if backend_health and 'backends' in backend_health::
                summary = backend_health.get('summary', {})
                self._add_metric("vfs_backend_total_count", summary.get('total_backends', 0))
                self._add_metric("vfs_backend_healthy_count", summary.get('healthy_backends', 0))
                self._add_metric("vfs_backend_unhealthy_count", summary.get('unhealthy_backends', 0))
                self._add_metric("vfs_backend_health_percentage", summary.get('health_percentage', 0))
                
                for backend_name, backend_status in backend_health['backends'].items():
                    tags = {"backend": backend_name}
                    self._add_metric("vfs_backend_healthy", 1 if backend_status.get('healthy', False) else 0, tags)
                    self._add_metric("vfs_backend_last_check_age_seconds", 
                                   backend_status.get('last_check_age_seconds', 0), tags)
                    self._add_metric("vfs_backend_is_stale", 1 if backend_status.get('is_stale', False) else 0, tags)
                    
                    if backend_status.get('average_latency_ms') is not None:
                        self._add_metric("vfs_backend_avg_latency_ms", 
                                       backend_status['average_latency_ms'], tags)
                    if backend_status.get('p95_latency_ms') is not None:
                        self._add_metric("vfs_backend_p95_latency_ms", 
                                       backend_status['p95_latency_ms'], tags)
            
            # Process alerts
            alerts = analytics.get('alerts', [])
            self._add_metric("vfs_active_alerts_total", len(alerts))
            
            # Count alerts by severity
            alert_counts = {'critical': 0, 'warning': 0, 'info': 0}
            for alert in alerts:
                severity = alert.get('severity', 'info')
                if severity in alert_counts:
                    alert_counts[severity] += 1
            
            for severity, count in alert_counts.items():
                self._add_metric("vfs_alerts_by_severity", count, {"severity": severity})
                
        except Exception as e:
            logger.error(f"Failed to collect VFS analytics data: {e}")
    
    def _add_metric(self, name: str, value: Any, tags: Optional[Dict[str, str]] = None) -> None:
        """Add a metric data point."""
        if name not in self.metrics:
            self.metrics[name] = MetricSeries(name=name)
        
        self.metrics[name].add_point(value, tags)
        
        # Limit the number of data points to prevent memory issues
        max_points = self.config.max_data_points
        if len(self.metrics[name].data_points) > max_points:
            # Remove oldest points
            self.metrics[name].data_points = self.metrics[name].data_points[-max_points:]
    
    async def _cleanup_old_data(self) -> None:
        """Clean up old data points."""
        for metric in self.metrics.values():
            metric.cleanup_old_data(self.config.data_retention_hours)
    
    def get_metrics(self) -> Dict[str, MetricSeries]:
        """Get all collected metrics."""
        return self.metrics.copy()
    
    def get_metric(self, name: str) -> Optional[MetricSeries]:
        """Get a specific metric by name."""
        return self.metrics.get(name)
    
    def get_latest_values(self) -> Dict[str, Any]:
        """Get the latest values for all metrics."""
        latest = {}
        for name, metric in self.metrics.items():
            latest_point = metric.get_latest()
            if latest_point:
                latest[name] = {
                    "value": latest_point.value,
                    "timestamp": latest_point.timestamp,
                    "tags": latest_point.tags
                }
        return latest
    
    def get_metric_summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics."""
        return {
            "total_metrics": len(self.metrics),
            "total_data_points": sum(len(metric.data_points) for metric in self.metrics.values()),
            "collection_errors": self.error_count,
            "last_error_time": self.last_error_time,
            "is_running": self.is_running,
            "metrics_list": list(self.metrics.keys())
        }
    
    async def get_vfs_deep_insights(self) -> Dict[str, Any]:
        """Get comprehensive VFS insights and analysis."""
        if not self.has_vfs_analytics:
            return {
                'available': False,
                'error': 'VFS analytics not available'
            }
        
        if not self.vfs_monitor: # Added check for vfs_monitor
            return {
                'available': False,
                'error': 'VFS monitor not initialized'
            }

        try:
            # Get comprehensive analytics from VFS monitor
            analytics = self.vfs_monitor.get_analytics_summary()
            
            # Get additional detailed analyses
            bandwidth_analysis = self.vfs_monitor.performance_monitor.get_bandwidth_analysis(60)
            operation_analysis = self.vfs_monitor.performance_monitor.get_operation_analysis(60)
            realtime_metrics = self.vfs_monitor.performance_monitor.get_realtime_metrics()
            replication_health = self.vfs_monitor.performance_monitor.get_replication_health()
            cache_analysis = self.vfs_monitor.performance_monitor.get_cache_analysis()
            backend_health = self.vfs_monitor.performance_monitor.get_backend_health_status()
            
            # Generate performance insights
            insights = self._generate_vfs_performance_insights(analytics)
            recommendations = self._generate_vfs_optimization_recommendations(analytics)
            
            # Get historical trends from collected metrics
            trends = self._analyze_vfs_trends()
            
            return {
                'available': True,
                'timestamp': time.time(),
                'comprehensive_report': analytics,
                'detailed_analyses': {
                    'bandwidth': bandwidth_analysis,
                    'operations': operation_analysis,
                    'realtime': realtime_metrics,
                    'replication': replication_health,
                    'cache': cache_analysis,
                    'backends': backend_health
                },
                'insights': insights,
                'recommendations': recommendations,
                'trends': trends,
                'health_summary': self._generate_vfs_health_summary(analytics)
            }
            
        except Exception as e:
            logger.error(f"Error getting VFS deep insights: {e}")
            return {
                'available': False,
                'error': str(e)
            }
    
    def _generate_vfs_performance_insights(self, analytics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate performance insights from VFS analytics."""
        insights = []
        
        try:
            # Analyze error patterns
            realtime = analytics.get('realtime_metrics', {})
            error_rate = realtime.get('error_rate', 0)
            ops_per_sec = realtime.get('operations_per_second', 0)
            
            if error_rate > 0.05:  # 5% error rate
                insights.append({
                    'type': 'performance_issue',
                    'severity': 'high' if error_rate > 0.2 else 'medium',
                    'category': 'error_rate',
                    'title': 'High VFS Error Rate',
                    'description': f'VFS operations are failing at {error_rate:.1%} rate',
                    'impact': 'Degraded user experience and potential data access issues',
                    'metrics': {'error_rate': error_rate, 'ops_per_second': ops_per_sec}
                })
            
            # Analyze throughput patterns
            if ops_per_sec > 100:
                insights.append({
                    'type': 'performance_pattern',
                    'severity': 'info',
                    'category': 'high_throughput',
                    'title': 'High VFS Throughput',
                    'description': f'VFS is processing {ops_per_sec:.1f} operations per second',
                    'impact': 'System is under heavy load - monitor for bottlenecks',
                    'metrics': {'operations_per_second': ops_per_sec}
                })
            elif ops_per_sec < 0.1 and self.is_running:
                insights.append({
                    'type': 'performance_issue',
                    'severity': 'medium',
                    'category': 'low_activity',
                    'title': 'Low VFS Activity',
                    'description': f'VFS activity is very low ({ops_per_sec:.1f} ops/sec)',
                    'impact': 'May indicate connectivity issues or system underutilization',
                    'metrics': {'operations_per_second': ops_per_sec}
                })
            
            # Analyze bandwidth patterns
            bandwidth = analytics.get('bandwidth_analysis', {})
            if bandwidth and 'total_average_bps' in bandwidth:
                total_bps = bandwidth['total_average_bps']
                if total_bps > 50 * 1024 * 1024:  # 50MB/s
                    insights.append({
                        'type': 'resource_usage',
                        'severity': 'medium',
                        'category': 'high_bandwidth',
                        'title': 'High Bandwidth Usage',
                        'description': f'VFS bandwidth usage: {total_bps / (1024*1024):.1f} MB/s',
                        'impact': 'High network utilization - may affect other services',
                        'metrics': {'bandwidth_mbps': total_bps / (1024*1024)}
                    })
            
            # Analyze cache performance
            cache = analytics.get('cache_analysis', {})
            if cache and 'current_metrics' in cache:
                hit_rate = cache['current_metrics'].get('hit_rate', 0)
                utilization = cache['current_metrics'].get('utilization', 0)
                
                if hit_rate < 0.7:  # 70% hit rate
                    insights.append({
                        'type': 'performance_issue',
                        'severity': 'medium',
                        'category': 'cache_efficiency',
                        'title': 'Low Cache Hit Rate',
                        'description': f'VFS cache hit rate is {hit_rate:.1%}',
                        'impact': 'Increased latency and backend load',
                        'metrics': {'cache_hit_rate': hit_rate, 'cache_utilization': utilization}
                    })
                
                if utilization > 0.9:  # 90% cache utilization
                    insights.append({
                        'type': 'resource_constraint',
                        'severity': 'warning',
                        'category': 'cache_pressure',
                        'title': 'High Cache Memory Pressure',
                        'description': f'VFS cache utilization is {utilization:.1%}',
                        'impact': 'Cache evictions may increase, reducing efficiency',
                        'metrics': {'cache_analysis': utilization}
                    })
            
            # Analyze replication health
            replication = analytics.get('replication_health', {})
            if replication and 'current_status' in replication:
                health_pct = replication['current_status'].get('health_percentage', 100)
                sync_lag = replication['current_status'].get('sync_lag_seconds', 0)
                
                if health_pct < 80:  # 80% healthy replicas
                    insights.append({
                        'type': 'availability_issue',
                        'severity': 'high' if health_pct < 50 else 'medium',
                        'category': 'replication_health',
                        'title': 'Replication Health Issues',
                        'description': f'Only {health_pct:.1f}% of replicas are healthy',
                        'impact': 'Reduced data redundancy and potential data loss risk',
                        'metrics': {'replication_health_percentage': health_pct}
                    })
                
                if sync_lag > 300:  # 5 minutes
                    insights.append({
                        'type': 'performance_issue',
                        'severity': 'medium',
                        'category': 'sync_lag',
                        'title': 'High Replication Sync Lag',
                        'description': f'Replication sync lag is {sync_lag:.1f} seconds',
                        'impact': 'Data consistency issues and delayed propagation',
                        'metrics': {'sync_lag_seconds': sync_lag}
                    })
            
            # Analyze backend health
            backend_health = analytics.get('backend_health', {})
            if backend_health and 'backends' in backend_health::
                summary = backend_health.get('summary', {})
                self._add_metric("vfs_backend_total_count", summary.get('total_backends', 0))
                self._add_metric("vfs_backend_healthy_count", summary.get('healthy_backends', 0))
                self._add_metric("vfs_backend_unhealthy_count", summary.get('unhealthy_backends', 0))
                self._add_metric("vfs_backend_health_percentage", summary.get('health_percentage', 0))
                
                for backend_name, backend_status in backend_health['backends'].items():
                    tags = {"backend": backend_name}
                    self._add_metric("vfs_backend_healthy", 1 if backend_status.get('healthy', False) else 0, tags)
                    self._add_metric("vfs_backend_last_check_age_seconds", 
                                   backend_status.get('last_check_age_seconds', 0), tags)
                    self._add_metric("vfs_backend_is_stale", 1 if backend_status.get('is_stale', False) else 0, tags)
                    
                    if backend_status.get('average_latency_ms') is not None:
                        self._add_metric("vfs_backend_avg_latency_ms", 
                                       backend_status['average_latency_ms'], tags)
                    if backend_status.get('p95_latency_ms') is not None:
                        self._add_metric("vfs_backend_p95_latency_ms", 
                                       backend_status['p95_latency_ms'], tags)
            
            # Process alerts
            alerts = analytics.get('alerts', [])
            self._add_metric("vfs_active_alerts_total", len(alerts))
            
            # Count alerts by severity
            alert_counts = {'critical': 0, 'warning': 0, 'info': 0}
            for alert in alerts:
                severity = alert.get('severity', 'info')
                if severity in alert_counts:
                    alert_counts[severity] += 1
            
            for severity, count in alert_counts.items():
                self._add_metric("vfs_alerts_by_severity", count, {"severity": severity})
                
        except Exception as e:
            logger.error(f"Failed to collect VFS analytics data: {e}")
    
    def _add_metric(self, name: str, value: Any, tags: Optional[Dict[str, str]] = None) -> None:
        """Add a metric data point."""
        if name not in self.metrics:
            self.metrics[name] = MetricSeries(name=name)
        
        self.metrics[name].add_point(value, tags)
        
        # Limit the number of data points to prevent memory issues
        max_points = self.config.max_data_points
        if len(self.metrics[name].data_points) > max_points:
            # Remove oldest points
            self.metrics[name].data_points = self.metrics[name].data_points[-max_points:]
    
    async def _cleanup_old_data(self) -> None:
        """Clean up old data points."""
        for metric in self.metrics.values():
            metric.cleanup_old_data(self.config.data_retention_hours)
    
    def get_metrics(self) -> Dict[str, MetricSeries]:
        """Get all collected metrics."""
        return self.metrics.copy()
    
    def get_metric(self, name: str) -> Optional[MetricSeries]:
        """Get a specific metric by name."""
        return self.metrics.get(name)
    
    def get_latest_values(self) -> Dict[str, Any]:
        """Get the latest values for all metrics."""
        latest = {}
        for name, metric in self.metrics.items():
            latest_point = metric.get_latest()
            if latest_point:
                latest[name] = {
                    "value": latest_point.value,
                    "timestamp": latest_point.timestamp,
                    "tags": latest_point.tags
                }
        return latest
    
    def get_metric_summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics."""
        return {
            "total_metrics": len(self.metrics),
            "total_data_points": sum(len(metric.data_points) for metric in self.metrics.values()),
            "collection_errors": self.error_count,
            "last_error_time": self.last_error_time,
            "is_running": self.is_running,
            "metrics_list": list(self.metrics.keys())
        }
    
    async def get_vfs_deep_insights(self) -> Dict[str, Any]:
        """Get comprehensive VFS insights and analysis."""
        if not self.has_vfs_analytics:
            return {
                'available': False,
                'error': 'VFS analytics not available'
            }
        
        if not self.vfs_monitor: # Added check for vfs_monitor
            return {
                'available': False,
                'error': 'VFS monitor not initialized'
            }

        try:
            # Get comprehensive analytics from VFS monitor
            analytics = self.vfs_monitor.get_analytics_summary()
            
            # Get additional detailed analyses
            bandwidth_analysis = self.vfs_monitor.performance_monitor.get_bandwidth_analysis(60)
            operation_analysis = self.vfs_monitor.performance_monitor.get_operation_analysis(60)
            realtime_metrics = self.vfs_monitor.performance_monitor.get_realtime_metrics()
            replication_health = self.vfs_monitor.performance_monitor.get_replication_health()
            cache_analysis = self.vfs_monitor.performance_monitor.get_cache_analysis()
            backend_health = self.vfs_monitor.performance_monitor.get_backend_health_status()
            
            # Generate performance insights
            insights = self._generate_vfs_performance_insights(analytics)
            recommendations = self._generate_vfs_optimization_recommendations(analytics)
            
            # Get historical trends from collected metrics
            trends = self._analyze_vfs_trends()
            
            return {
                'available': True,
                'timestamp': time.time(),
                'comprehensive_report': analytics,
                'detailed_analyses': {
                    'bandwidth': bandwidth_analysis,
                    'operations': operation_analysis,
                    'realtime': realtime_metrics,
                    'replication': replication_health,
                    'cache': cache_analysis,
                    'backends': backend_health
                },
                'insights': insights,
                'recommendations': recommendations,
                'trends': trends,
                'health_summary': self._generate_vfs_health_summary(analytics)
            }
            
        except Exception as e:
            logger.error(f"Error getting VFS deep insights: {e}")
            return {
                'available': False,
                'error': str(e)
            }
    
    def _generate_vfs_performance_insights(self, analytics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate performance insights from VFS analytics."""
        insights = []
        
        try:
            # Analyze error patterns
            realtime = analytics.get('realtime_metrics', {})
            error_rate = realtime.get('error_rate', 0)
            ops_per_sec = realtime.get('operations_per_second', 0)
            
            if error_rate > 0.05:  # 5% error rate
                insights.append({
                    'type': 'performance_issue',
                    'severity': 'high' if error_rate > 0.2 else 'medium',
                    'category': 'error_rate',
                    'title': 'High VFS Error Rate',
                    'description': f'VFS operations are failing at {error_rate:.1%} rate',
                    'impact': 'Degraded user experience and potential data access issues',
                    'metrics': {'error_rate': error_rate, 'ops_per_second': ops_per_sec}
                })
            
            # Analyze throughput patterns
            if ops_per_sec > 100:
                insights.append({
                    'type': 'performance_pattern',
                    'severity': 'info',
                    'category': 'high_throughput',
                    'title': 'High VFS Throughput',
                    'description': f'VFS is processing {ops_per_sec:.1f} operations per second',
                    'impact': 'System is under heavy load - monitor for bottlenecks',
                    'metrics': {'operations_per_second': ops_per_sec}
                })
            elif ops_per_sec < 0.1 and self.is_running:
                insights.append({
                    'type': 'performance_issue',
                    'severity': 'medium',
                    'category': 'low_activity',
                    'title': 'Low VFS Activity',
                    'description': f'VFS activity is very low ({ops_per_sec:.1f} ops/sec)',
                    'impact': 'May indicate connectivity issues or system underutilization',
                    'metrics': {'operations_per_second': ops_per_sec}
                })
            
            # Analyze bandwidth patterns
            bandwidth = analytics.get('bandwidth_analysis', {})
            if bandwidth and 'total_average_bps' in bandwidth:
                total_bps = bandwidth['total_average_bps']
                if total_bps > 50 * 1024 * 1024:  # 50MB/s
                    insights.append({
                        'type': 'resource_usage',
                        'severity': 'medium',
                        'category': 'high_bandwidth',
                        'title': 'High Bandwidth Usage',
                        'description': f'VFS bandwidth usage: {total_bps / (1024*1024):.1f} MB/s',
                        'impact': 'High network utilization - may affect other services',
                        'metrics': {'bandwidth_mbps': total_bps / (1024*1024)}
                    })
            
            # Analyze cache performance
            cache = analytics.get('cache_analysis', {})
            if cache and 'current_metrics' in cache:
                hit_rate = cache['current_metrics'].get('hit_rate', 0)
                utilization = cache['current_metrics'].get('utilization', 0)
                
                if hit_rate < 0.7:  # 70% hit rate
                    insights.append({
                        'type': 'performance_issue',
                        'severity': 'medium',
                        'category': 'cache_efficiency',
                        'title': 'Low Cache Hit Rate',
                        'description': f'VFS cache hit rate is {hit_rate:.1%}',
                        'impact': 'Increased latency and backend load',
                        'metrics': {'cache_hit_rate': hit_rate, 'cache_utilization': utilization}
                    })
                
                if utilization > 0.9:  # 90% cache utilization
                    insights.append({
                        'type': 'resource_constraint',
                        'severity': 'warning',
                        'category': 'cache_pressure',
                        'title': 'High Cache Memory Pressure',
                        'description': f'VFS cache utilization is {utilization:.1%}',
                        'impact': 'Cache evictions may increase, reducing efficiency',
                        'metrics': {'cache_analysis': utilization}
                    })
            
            # Analyze replication health
            replication = analytics.get('replication_health', {})
            if replication and 'current_status' in replication:
                health_pct = replication['current_status'].get('health_percentage', 100)
                sync_lag = replication['current_status'].get('sync_lag_seconds', 0)
                
                if health_pct < 80:  # 80% healthy replicas
                    insights.append({
                        'type': 'availability_issue',
                        'severity': 'high' if health_pct < 50 else 'medium',
                        'category': 'replication_health',
                        'title': 'Replication Health Issues',
                        'description': f'Only {health_pct:.1f}% of replicas are healthy',
                        'impact': 'Reduced data redundancy and potential data loss risk',
                        'metrics': {'replication_health_percentage': health_pct}
                    })
                
                if sync_lag > 300:  # 5 minutes
                    insights.append({
                        'type': 'performance_issue',
                        'severity': 'medium',
                        'category': 'sync_lag',
                        'title': 'High Replication Sync Lag',
                        'description': f'Replication sync lag is {sync_lag:.1f} seconds',
                        'impact': 'Data consistency issues and delayed propagation',
                        'metrics': {'sync_lag_seconds': sync_lag}
                    })
            
            # Analyze backend health
            backend_health = analytics.get('backend_health', {})
            if backend_health and 'backends' in backend_health::
                summary = backend_health.get('summary', {})
                self._add_metric("vfs_backend_total_count", summary.get('total_backends', 0))
                self._add_metric("vfs_backend_healthy_count", summary.get('healthy_backends', 0))
                self._add_metric("vfs_backend_unhealthy_count", summary.get('unhealthy_backends', 0))
                self._add_metric("vfs_backend_health_percentage", summary.get('health_percentage', 0))
                
                for backend_name, backend_status in backend_health['backends'].items():
                    tags = {"backend": backend_name}
                    self._add_metric("vfs_backend_healthy", 1 if backend_status.get('healthy', False) else 0, tags)
                    self._add_metric("vfs_backend_last_check_age_seconds", 
                                   backend_status.get('last_check_age_seconds', 0), tags)
                    self._add_metric("vfs_backend_is_stale", 1 if backend_status.get('is_stale', False) else 0, tags)
                    
                    if backend_status.get('average_latency_ms') is not None:
                        self._add_metric("vfs_backend_avg_latency_ms", 
                                       backend_status['average_latency_ms'], tags)
                    if backend_status.get('p95_latency_ms') is not None:
                        self._add_metric("vfs_backend_p95_latency_ms", 
                                       backend_status['p95_latency_ms'], tags)
            
            # Process alerts
            alerts = analytics.get('alerts', [])
            self._add_metric("vfs_active_alerts_total", len(alerts))
            
            # Count alerts by severity
            alert_counts = {'critical': 0, 'warning': 0, 'info': 0}
            for alert in alerts:
                severity = alert.get('severity', 'info')
                if severity in alert_counts:
                    alert_counts[severity] += 1
            
            for severity, count in alert_counts.items():
                self._add_metric("vfs_alerts_by_severity", count, {"severity": severity})
                
        except Exception as e:
            logger.error(f"Failed to collect VFS analytics data: {e}")
    
    def _add_metric(self, name: str, value: Any, tags: Optional[Dict[str, str]] = None) -> None:
        """Add a metric data point."""
        if name not in self.metrics:
            self.metrics[name] = MetricSeries(name=name)
        
        self.metrics[name].add_point(value, tags)
        
        # Limit the number of data points to prevent memory issues
        max_points = self.config.max_data_points
        if len(self.metrics[name].data_points) > max_points:
            # Remove oldest points
            self.metrics[name].data_points = self.metrics[name].data_points[-max_points:]
    
    async def _cleanup_old_data(self) -> None:
        """Clean up old data points."""
        for metric in self.metrics.values():
            metric.cleanup_old_data(self.config.data_retention_hours)
    
    def get_metrics(self) -> Dict[str, MetricSeries]:
        """Get all collected metrics."""
        return self.metrics.copy()
    
    def get_metric(self, name: str) -> Optional[MetricSeries]:
        """Get a specific metric by name."""
        return self.metrics.get(name)
    
    def get_latest_values(self) -> Dict[str, Any]:
        """Get the latest values for all metrics."""
        latest = {}
        for name, metric in self.metrics.items():
            latest_point = metric.get_latest()
            if latest_point:
                latest[name] = {
                    "value": latest_point.value,
                    "timestamp": latest_point.timestamp,
                    "tags": latest_point.tags
                }
        return latest
    
    def get_metric_summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics."""
        return {
            "total_metrics": len(self.metrics),
            "total_data_points": sum(len(metric.data_points) for metric in self.metrics.values()),
            "collection_errors": self.error_count,
            "last_error_time": self.last_error_time,
            "is_running": self.is_running,
            "metrics_list": list(self.metrics.keys())
        }
    
    async def get_vfs_deep_insights(self) -> Dict[str, Any]:
        """Get comprehensive VFS insights and analysis."""
        if not self.has_vfs_analytics:
            return {
                'available': False,
                'error': 'VFS analytics not available'
            }
        
        if not self.vfs_monitor: # Added check for vfs_monitor
            return {
                'available': False,
                'error': 'VFS monitor not initialized'
            }

        try:
            # Get comprehensive analytics from VFS monitor
            analytics = self.vfs_monitor.get_analytics_summary()
            
            # Get additional detailed analyses
            bandwidth_analysis = self.vfs_monitor.performance_monitor.get_bandwidth_analysis(60)
            operation_analysis = self.vfs_monitor.performance_monitor.get_operation_analysis(60)
            realtime_metrics = self.vfs_monitor.performance_monitor.get_realtime_metrics()
            replication_health = self.vfs_monitor.performance_monitor.get_replication_health()
            cache_analysis = self.vfs_monitor.performance_monitor.get_cache_analysis()
            backend_health = self.vfs_monitor.performance_monitor.get_backend_health_status()
            
            # Generate performance insights
            insights = self._generate_vfs_performance_insights(analytics)
            recommendations = self._generate_vfs_optimization_recommendations(analytics)
            
            # Get historical trends from collected metrics
            trends = self._analyze_vfs_trends()
            
            return {
                'available': True,
                'timestamp': time.time(),
                'comprehensive_report': analytics,
                'detailed_analyses': {
                    'bandwidth': bandwidth_analysis,
                    'operations': operation_analysis,
                    'realtime': realtime_metrics,
                    'replication': replication_health,
                    'cache': cache_analysis,
                    'backends': backend_health
                },
                'insights': insights,
                'recommendations': recommendations,
                'trends': trends,
                'health_summary': self._generate_vfs_health_summary(analytics)
            }
            
        except Exception as e:
            logger.error(f"Error getting VFS deep insights: {e}")
            return {
                'available': False,
                'error': str(e)
            }
    
    def _generate_vfs_performance_insights(self, analytics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate performance insights from VFS analytics."""
        insights = []
        
        try:
            # Analyze error patterns
            realtime = analytics.get('realtime_metrics', {})
            error_rate = realtime.get('error_rate', 0)
            ops_per_sec = realtime.get('operations_per_second', 0)
            
            if error_rate > 0.05:  # 5% error rate
                insights.append({
                    'type': 'performance_issue',
                    'severity': 'high' if error_rate > 0.2 else 'medium',
                    'category': 'error_rate',
                    'title': 'High VFS Error Rate',
                    'description': f'VFS operations are failing at {error_rate:.1%} rate',
                    'impact': 'Degraded user experience and potential data access issues',
                    'metrics': {'error_rate': error_rate, 'ops_per_second': ops_per_sec}
                })
            
            # Analyze throughput patterns
            if ops_per_sec > 100:
                insights.append({
                    'type': 'performance_pattern',
                    'severity': 'info',
                    'category': 'high_throughput',
                    'title': 'High VFS Throughput',
                    'description': f'VFS is processing {ops_per_sec:.1f} operations per second',
                    'impact': 'System is under heavy load - monitor for bottlenecks',
                    'metrics': {'operations_per_second': ops_per_sec}
                })
            elif ops_per_sec < 0.1 and self.is_running:
                insights.append({
                    'type': 'performance_issue',
                    'severity': 'medium',
                    'category': 'low_activity',
                    'title': 'Low VFS Activity',
                    'description': f'VFS activity is very low ({ops_per_sec:.1f} ops/sec)',
                    'impact': 'May indicate connectivity issues or system underutilization',
                    'metrics': {'operations_per_second': ops_per_sec}
                })
            
            # Analyze bandwidth patterns
            bandwidth = analytics.get('bandwidth_analysis', {})
            if bandwidth and 'total_average_bps' in bandwidth:
                total_bps = bandwidth['total_average_bps']
                if total_bps > 50 * 1024 * 1024:  # 50MB/s
                    insights.append({
                        'type': 'resource_usage',
                        'severity': 'medium',
                        'category': 'high_bandwidth',
                        'title': 'High Bandwidth Usage',
                        'description': f'VFS bandwidth usage: {total_bps / (1024*1024):.1f} MB/s',
                        'impact': 'High network utilization - may affect other services',
                        'metrics': {'bandwidth_mbps': total_bps / (1024*1024)}
                    })
            
            # Analyze cache performance
            cache = analytics.get('cache_analysis', {})
            if cache and 'current_metrics' in cache:
                hit_rate = cache['current_metrics'].get('hit_rate', 0)
                utilization = cache['current_metrics'].get('utilization', 0)
                
                if hit_rate < 0.7:  # 70% hit rate
                    insights.append({
                        'type': 'performance_issue',
                        'severity': 'medium',
                        'category': 'cache_efficiency',
                        'title': 'Low Cache Hit Rate',
                        'description': f'VFS cache hit rate is {hit_rate:.1%}',
                        'impact': 'Increased latency and backend load',
                        'metrics': {'cache_hit_rate': hit_rate, 'cache_utilization': utilization}
                    })
                
                if utilization > 0.9:  # 90% cache utilization
                    insights.append({
                        'type': 'resource_constraint',
                        'severity': 'warning',
                        'category': 'cache_pressure',
                        'title': 'High Cache Memory Pressure',
                        'description': f'VFS cache utilization is {utilization:.1%}',
                        'impact': 'Cache evictions may increase, reducing efficiency',
                        'metrics': {'cache_analysis': utilization}
                    })
            
            # Analyze replication health
            replication = analytics.get('replication_health', {})
            if replication and 'current_status' in replication:
                health_pct = replication['current_status'].get('health_percentage', 100)
                sync_lag = replication['current_status'].get('sync_lag_seconds', 0)
                
                if health_pct < 80:  # 80% healthy replicas
                    insights.append({
                        'type': 'availability_issue',
                        'severity': 'high' if health_pct < 50 else 'medium',
                        'category': 'replication_health',
                        'title': 'Replication Health Issues',
                        'description': f'Only {health_pct:.1f}% of replicas are healthy',
                        'impact': 'Reduced data redundancy and potential data loss risk',
                        'metrics': {'replication_health_percentage': health_pct}
                    })
                
                if sync_lag > 300:  # 5 minutes
                    insights.append({
                        'type': 'performance_issue',
                        'severity': 'medium',
                        'category': 'sync_lag',
                        'title': 'High Replication Sync Lag',
                        'description': f'Replication sync lag is {sync_lag:.1f} seconds',
                        'impact': 'Data consistency issues and delayed propagation',
                        'metrics': {'sync_lag_seconds': sync_lag}
                    })
            
            # Analyze backend health
            backend_health = analytics.get('backend_health', {})
            if backend_health and 'backends' in backend_health::
                summary = backend_health.get('summary', {})
                self._add_metric("vfs_backend_total_count", summary.get('total_backends', 0))
                self._add_metric("vfs_backend_healthy_count", summary.get('healthy_backends', 0))
                self._add_metric("vfs_backend_unhealthy_count", summary.get('unhealthy_backends', 0))
                self._add_metric("vfs_backend_health_percentage", summary.get('health_percentage', 0))
                
                for backend_name, backend_status in backend_health['backends'].items():
                    tags = {"backend": backend_name}
                    self._add_metric("vfs_backend_healthy", 1 if backend_status.get('healthy', False) else 0, tags)
                    self._add_metric("vfs_backend_last_check_age_seconds", 
                                   backend_status.get('last_check_age_seconds', 0), tags)
                    self._add_metric("vfs_backend_is_stale", 1 if backend_status.get('is_stale', False) else 0, tags)
                    
                    if backend_status.get('average_latency_ms') is not None:
                        self._add_metric("vfs_backend_avg_latency_ms", 
                                       backend_status['average_latency_ms'], tags)
                    if backend_status.get('p95_latency_ms') is not None:
                        self._add_metric("vfs_backend_p95_latency_ms", 
                                       backend_status['p95_latency_ms'], tags)
            
            # Process alerts
            alerts = analytics.get('alerts', [])
            self._add_metric("vfs_active_alerts_total", len(alerts))
            
            # Count alerts by severity
            alert_counts = {'critical': 0, 'warning': 0, 'info': 0}
            for alert in alerts:
                severity = alert.get('severity', 'info')
                if severity in alert_counts:
                    alert_counts[severity] += 1
            
            for severity, count in alert_counts.items():
                self._add_metric("vfs_alerts_by_severity", count, {"severity": severity})
                
        except Exception as e:
            logger.error(f"Failed to collect VFS analytics data: {e}")
    
    def _add_metric(self, name: str, value: Any, tags: Optional[Dict[str, str]] = None) -> None:
        """Add a metric data point."""
        if name not in self.metrics:
            self.metrics[name] = MetricSeries(name=name)
        
        self.metrics[name].add_point(value, tags)
        
        # Limit the number of data points to prevent memory issues
        max_points = self.config.max_data_points
        if len(self.metrics[name].data_points) > max_points:
            # Remove oldest points
            self.metrics[name].data_points = self.metrics[name].data_points[-max_points:]
    
    async def _cleanup_old_data(self) -> None:
        """Clean up old data points."""
        for metric in self.metrics.values():
            metric.cleanup_old_data(self.config.data_retention_hours)
    
    def get_metrics(self) -> Dict[str, MetricSeries]:
        """Get all collected metrics."""
        return self.metrics.copy()
    
    def get_metric(self, name: str) -> Optional[MetricSeries]:
        """Get a specific metric by name."""
        return self.metrics.get(name)
    
    def get_latest_values(self) -> Dict[str, Any]:
        """Get the latest values for all metrics."""
        latest = {}
        for name, metric in self.metrics.items():
            latest_point = metric.get_latest()
            if latest_point:
                latest[name] = {
                    "value": latest_point.value,
                    "timestamp": latest_point.timestamp,
                    "tags": latest_point.tags
                }
        return latest
    
    def get_metric_summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics."""
        return {
            "total_metrics": len(self.metrics),
            "total_data_points": sum(len(metric.data_points) for metric in self.metrics.values()),
            "collection_errors": self.error_count,
            "last_error_time": self.last_error_time,
            "is_running": self.is_running,
            "metrics_list": list(self.metrics.keys())
        }
    
    async def get_vfs_deep_insights(self) -> Dict[str, Any]:
        """Get comprehensive VFS insights and analysis."""
        if not self.has_vfs_analytics:
            return {
                'available': False,
                'error': 'VFS analytics not available'
            }
        
        if not self.vfs_monitor: # Added check for vfs_monitor
            return {
                'available': False,
                'error': 'VFS monitor not initialized'
            }

        try:
            # Get comprehensive analytics from VFS monitor
            analytics = self.vfs_monitor.get_analytics_summary()
            
            # Get additional detailed analyses
            bandwidth_analysis = self.vfs_monitor.performance_monitor.get_bandwidth_analysis(60)
            operation_analysis = self.vfs_monitor.performance_monitor.get_operation_analysis(60)
            realtime_metrics = self.vfs_monitor.performance_monitor.get_realtime_metrics()
            replication_health = self.vfs_monitor.performance_monitor.get_replication_health()
            cache_analysis = self.vfs_monitor.performance_monitor.get_cache_analysis()
            backend_health = self.vfs_monitor.performance_monitor.get_backend_health_status()
            
            # Generate performance insights
            insights = self._generate_vfs_performance_insights(analytics)
            recommendations = self._generate_vfs_optimization_recommendations(analytics)
            
            # Get historical trends from collected metrics
            trends = self._analyze_vfs_trends()
            
            return {
                'available': True,
                'timestamp': time.time(),
                'comprehensive_report': analytics,
                'detailed_analyses': {
                    'bandwidth': bandwidth_analysis,
                    'operations': operation_analysis,
                    'realtime': realtime_metrics,
                    'replication': replication_health,
                    'cache': cache_analysis,
                    'backends': backend_health
                },
                'insights': insights,
                'recommendations': recommendations,
                'trends': trends,
                'health_summary': self._generate_vfs_health_summary(analytics)
            }
            
        except Exception as e:
            logger.error(f"Error getting VFS deep insights: {e}")
            return {
                'available': False,
                'error': str(e)
            }
    
    def _generate_vfs_performance_insights(self, analytics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate performance insights from VFS analytics."""
        insights = []
        
        try:
            # Analyze error patterns
            realtime = analytics.get('realtime_metrics', {})
            error_rate = realtime.get('error_rate', 0)
            ops_per_sec = realtime.get('operations_per_second', 0)
            
            if error_rate > 0.05:  # 5% error rate
                insights.append({
                    'type': 'performance_issue',
                    'severity': 'high' if error_rate > 0.2 else 'medium',
                    'category': 'error_rate',
                    'title': 'High VFS Error Rate',
                    'description': f'VFS operations are failing at {error_rate:.1%} rate',
                    'impact': 'Degraded user experience and potential data access issues',
                    'metrics': {'error_rate': error_rate, 'ops_per_second': ops_per_sec}
                })
            
            # Analyze throughput patterns
            if ops_per_sec > 100:
                insights.append({
                    'type': 'performance_pattern',
                    'severity': 'info',
                    'category': 'high_throughput',
                    'title': 'High VFS Throughput',
                    'description': f'VFS is processing {ops_per_sec:.1f} operations per second',
                    'impact': 'System is under heavy load - monitor for bottlenecks',
                    'metrics': {'operations_per_second': ops_per_sec}
                })
            elif ops_per_sec < 0.1 and self.is_running:
                insights.append({
                    'type': 'performance_issue',
                    'severity': 'medium',
                    'category': 'low_activity',
                    'title': 'Low VFS Activity',
                    'description': f'VFS activity is very low ({ops_per_sec:.1f} ops/sec)',
                    'impact': 'May indicate connectivity issues or system underutilization',
                    'metrics': {'operations_per_second': ops_per_sec}
                })
            
            # Analyze bandwidth patterns
            bandwidth = analytics.get('bandwidth_analysis', {})
            if bandwidth and 'total_average_bps' in bandwidth:
                total_bps = bandwidth['total_average_bps']
                if total_bps > 50 * 1024 * 1024:  # 50MB/s
                    insights.append({
                        'type': 'resource_usage',
                        'severity': 'medium',
                        'category': 'high_bandwidth',
                        'title': 'High Bandwidth Usage',
                        'description': f'VFS bandwidth usage: {total_bps / (1024*1024):.1f} MB/s',
                        'impact': 'High network utilization - may affect other services',
                        'metrics': {'bandwidth_mbps': total_bps / (1024*1024)}
                    })
            
            # Analyze cache performance
            cache = analytics.get('cache_analysis', {})
            if cache and 'current_metrics' in cache:
                hit_rate = cache['current_metrics'].get('hit_rate', 0)
                utilization = cache['current_metrics'].get('utilization', 0)
                
                if hit_rate < 0.7:  # 70% hit rate
                    insights.append({
                        'type': 'performance_issue',
                        'severity': 'medium',
                        'category': 'cache_efficiency',
                        'title': 'Low Cache Hit Rate',
                        'description': f'VFS cache hit rate is {hit_rate:.1%}',
                        'impact': 'Increased latency and backend load',
                        'metrics': {'cache_hit_rate': hit_rate, 'cache_utilization': utilization}
                    })
                
                if utilization > 0.9:  # 90% cache utilization
                    insights.append({
                        'type': 'resource_constraint',
                        'severity': 'warning',
                        'category': 'cache_pressure',
                        'title': 'High Cache Memory Pressure',
                        'description': f'VFS cache utilization is {utilization:.1%}',
                        'impact': 'Cache evictions may increase, reducing efficiency',
                        'metrics': {'cache_analysis': utilization}
                    })
            
            # Analyze replication health
            replication = analytics.get('replication_health', {})
            if replication and 'current_status' in replication:
                health_pct = replication['current_status'].get('health_percentage', 100)
                sync_lag = replication['current_status'].get('sync_lag_seconds', 0)
                
                if health_pct < 80:  # 80% healthy replicas
                    insights.append({
                        'type': 'availability_issue',
                        'severity': 'high' if health_pct < 50 else 'medium',
                        'category': 'replication_health',
                        'title': 'Replication Health Issues',
                        'description': f'Only {health_pct:.1f}% of replicas are healthy',
                        'impact': 'Reduced data redundancy and potential data loss risk',
                        'metrics': {'replication_health_percentage': health_pct}
                    })
                
                if sync_lag > 300:  # 5 minutes
                    insights.append({
                        'type': 'performance_issue',
                        'severity': 'medium',
                        'category': 'sync_lag',
                        'title': 'High Replication Sync Lag',
                        'description': f'Replication sync lag is {sync_lag:.1f} seconds',
                        'impact': 'Data consistency issues and delayed propagation',
                        'metrics': {'sync_lag_seconds': sync_lag}
                    })
            
            # Analyze backend health
            backend_health = analytics.get('backend_health', {})
            if backend_health and 'backends' in backend_health::
                summary = backend_health.get('summary', {})
                self._add_metric("vfs_backend_total_count", summary.get('total_backends', 0))
                self._add_metric("vfs_backend_healthy_count", summary.get('healthy_backends', 0))
                self._add_metric("vfs_backend_unhealthy_count", summary.get('unhealthy_backends', 0))
                self._add_metric("vfs_backend_health_percentage", summary.get('health_percentage', 0))
                
                for backend_name, backend_status in backend_health['backends'].items():
                    tags = {"backend": backend_name}
                    self._add_metric("vfs_backend_healthy", 1 if backend_status.get('healthy', False) else 0, tags)
                    self._add_metric("vfs_backend_last_check_age_seconds", 
                                   backend_status.get('last_check_age_seconds', 0), tags)
                    self._add_metric("vfs_backend_is_stale", 1 if backend_status.get('is_stale', False) else 0, tags)
                    
                    if backend_status.get('average_latency_ms') is not None:
                        self._add_metric("vfs_backend_avg_latency_ms", 
                                       backend_status['average_latency_ms'], tags)
                    if backend_status.get('p95_latency_ms') is not None:
                        self._add_metric("vfs_backend_p95_latency_ms", 
                                       backend_status['p95_latency_ms'], tags)
            
            # Process alerts
            alerts = analytics.get('alerts', [])
            self._add_metric("vfs_active_alerts_total", len(alerts))
            
            # Count alerts by severity
            alert_counts = {'critical': 0, 'warning': 0, 'info': 0}
            for alert in alerts:
                severity = alert.get('severity', 'info')
                if severity in alert_counts:
                    alert_counts[severity] += 1
            
            for severity, count in alert_counts.items():
                self._add_metric("vfs_alerts_by_severity", count, {"severity": severity})
                
        except Exception as e:
            logger.error(f"Failed to collect VFS analytics data: {e}")
    
    def _add_metric(self, name: str, value: Any, tags: Optional[Dict[str, str]] = None) -> None:
        """Add a metric data point."""
        if name not in self.metrics:
            self.metrics[name] = MetricSeries(name=name)
        
        self.metrics[name].add_point(value, tags)
        
        # Limit the number of data points to prevent memory issues
        max_points = self.config.max_data_points
        if len(self.metrics[name].data_points) > max_points:
            # Remove oldest points
            self.metrics[name].data_points = self.metrics[name].data_points[-max_points:]
    
    async def _cleanup_old_data(self) -> None:
        """Clean up old data points."""
        for metric in self.metrics.values():
            metric.cleanup_old_data(self.config.data_retention_hours)
    
    def get_metrics(self) -> Dict[str, MetricSeries]:
        """Get all collected metrics."""
        return self.metrics.copy()
    
    def get_metric(self, name: str) -> Optional[MetricSeries]:
        """Get a specific metric by name."""
        return self.metrics.get(name)
    
    def get_latest_values(self) -> Dict[str, Any]:
        """Get the latest values for all metrics."""
        latest = {}
        for name, metric in self.metrics.items():
            latest_point = metric.get_latest()
            if latest_point:
                latest[name] = {
                    "value": latest_point.value,
                    "timestamp": latest_point.timestamp,
                    "tags": latest_point.tags
                }
        return latest
    
    def get_metric_summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics."""
        return {
            "total_metrics": len(self.metrics),
            "total_data_points": sum(len(metric.data_points) for metric in self.metrics.values()),
            "collection_errors": self.error_count,
            "last_error_time": self.last_error_time,
            "is_running": self.is_running,
            "metrics_list": list(self.metrics.keys())
        }
    
    async def get_vfs_deep_insights(self) -> Dict[str, Any]:
        """Get comprehensive VFS insights and analysis."""
        if not self.has_vfs_analytics:
            return {
                'available': False,
                'error': 'VFS analytics not available'
            }
        
        if not self.vfs_monitor: # Added check for vfs_monitor
            return {
                'available': False,
                'error': 'VFS monitor not initialized'
            }

        try:
            # Get comprehensive analytics from VFS monitor
            analytics = self.vfs_monitor.get_analytics_summary()
            
            # Get additional detailed analyses
            bandwidth_analysis = self.vfs_monitor.performance_monitor.get_bandwidth_analysis(60)
            operation_analysis = self.vfs_monitor.performance_monitor.get_operation_analysis(60)
            realtime_metrics = self.vfs_monitor.performance_monitor.get_realtime_metrics()
            replication_health = self.vfs_monitor.performance_monitor.get_replication_health()
            cache_analysis = self.vfs_monitor.performance_monitor.get_cache_analysis()
            backend_health = self.vfs_monitor.performance_monitor.get_backend_health_status()
            
            # Generate performance insights
            insights = self._generate_vfs_performance_insights(analytics)
            recommendations = self._generate_vfs_optimization_recommendations(analytics)
            
            # Get historical trends from collected metrics
            trends = self._analyze_vfs_trends()
            
            return {
                'available': True,
                'timestamp': time.time(),
                'comprehensive_report': analytics,
                'detailed_analyses': {
                    'bandwidth': bandwidth_analysis,
                    'operations': operation_analysis,
                    'realtime': realtime_metrics,
                    'replication': replication_health,
                    'cache': cache_analysis,
                    'backends': backend_health
                },
                'insights': insights,
                'recommendations': recommendations,
                'trends': trends,
                'health_summary': self._generate_vfs_health_summary(analytics)
            }
            
        except Exception as e:
            logger.error(f"Error getting VFS deep insights: {e}")
            return {
                'available': False,
                'error': str(e)
            }
    
    def _generate_vfs_performance_insights(self, analytics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate performance insights from VFS analytics."""
        insights = []
        
        try:
            # Analyze error patterns
            realtime = analytics.get('realtime_metrics', {})
            error_rate = realtime.get('error_rate', 0)
            ops_per_sec = realtime.get('operations_per_second', 0)
            
            if error_rate > 0.05:  # 5% error rate
                insights.append({
                    'type': 'performance_issue',
                    'severity': 'high' if error_rate > 0.2 else 'medium',
                    'category': 'error_rate',
                    'title': 'High VFS Error Rate',
                    'description': f'VFS operations are failing at {error_rate:.1%} rate',
                    'impact': 'Degraded user experience and potential data access issues',
                    'metrics': {'error_rate': error_rate, 'ops_per_second': ops_per_sec}
                })
            
            # Analyze throughput patterns
            if ops_per_sec > 100:
                insights.append({
                    'type': 'performance_pattern',
                    'severity': 'info',
                    'category': 'high_throughput',
                    'title': 'High VFS Throughput',
                    'description': f'VFS is processing {ops_per_sec:.1f} operations per second',
                    'impact': 'System is under heavy load - monitor for bottlenecks',
                    'metrics': {'operations_per_second': ops_per_sec}
                })
            elif ops_per_sec < 0.1 and self.is_running:
                insights.append({
                    'type': 'performance_issue',
                    'severity': 'medium',
                    'category': 'low_activity',
                    'title': 'Low VFS Activity',
                    'description': f'VFS activity is very low ({ops_per_sec:.1f} ops/sec)',
                    'impact': 'May indicate connectivity issues or system underutilization',
                    'metrics': {'operations_per_second': ops_per_sec}
                })
            
            # Analyze bandwidth patterns
            bandwidth = analytics.get('bandwidth_analysis', {})
            if bandwidth and 'total_average_bps' in bandwidth:
                total_bps = bandwidth['total_average_bps']
                if total_bps > 50 * 1024 * 1024:  # 50MB/s
                    insights.append({
                        'type': 'resource_usage',
                        'severity': 'medium',
                        'category': 'high_bandwidth',
                        'title': 'High Bandwidth Usage',
                        'description': f'VFS bandwidth usage: {total_bps / (1024*1024):.1f} MB/s',
                        'impact': 'High network utilization - may affect other services',
                        'metrics': {'bandwidth_mbps': total_bps / (1024*1024)}
                    })
            
            # Analyze cache performance
            cache = analytics.get('cache_analysis', {})
            if cache and 'current_metrics' in cache:
                hit_rate = cache['current_metrics'].get('hit_rate', 0)
                utilization = cache['current_metrics'].get('utilization', 0)
                
                if hit_rate < 0.7:  # 70% hit rate
                    insights.append({
                        'type': 'performance_issue',
                        'severity': 'medium',
                        'category': 'cache_efficiency',
                        'title': 'Low Cache Hit Rate',
                        'description': f'VFS cache hit rate is {hit_rate:.1%}',
                        'impact': 'Increased latency and backend load',
                        'metrics': {'cache_hit_rate': hit_rate, 'cache_utilization': utilization}
                    })
                
                if utilization > 0.9:  # 90% cache utilization
                    insights.append({
                        'type': 'resource_constraint',
                        'severity': 'warning',
                        'category': 'cache_pressure',
                        'title': 'High Cache Memory Pressure',
                        'description': f'VFS cache utilization is {utilization:.1%}',
                        'impact': 'Cache evictions may increase, reducing efficiency',
                        'metrics': {'cache_analysis': utilization}
                    })
            
            # Analyze replication health
            replication = analytics.get('replication_health', {})
            if replication and 'current_status' in replication:
                health_pct = replication['current_status'].get('health_percentage', 100)
                sync_lag = replication['current_status'].get('sync_lag_seconds', 0)
                
                if health_pct < 80:  # 80% healthy replicas
                    insights.append({
                        'type': 'availability_issue',
                        'severity': 'high' if health_pct < 50 else 'medium',
                        'category': 'replication_health',
                        'title': 'Replication Health Issues',
                        'description': f'Only {health_pct:.1f}% of replicas are healthy',
                        'impact': 'Reduced data redundancy and potential data loss risk',
                        'metrics': {'replication_health_percentage': health_pct}
                    })
                
                if sync_lag > 300:  # 5 minutes
                    insights.append({
                        'type': 'performance_issue',
                        'severity': 'medium',
                        'category': 'sync_lag',
                        'title': 'High Replication Sync Lag',
                        'description': f'Replication sync lag is {sync_lag:.1f} seconds',
                        'impact': 'Data consistency issues and delayed propagation',
                        'metrics': {'sync_lag_seconds': sync_lag}
                    })
            
            # Analyze backend health
            backend_health = analytics.get('backend_health', {})
            if backend_health and 'backends' in backend_health::
                summary = backend_health.get('summary', {})
                self._add_metric("vfs_backend_total_count", summary.get('total_backends', 0))
                self._add_metric("vfs_backend_healthy_count", summary.get('healthy_backends', 0))
                self._add_metric("vfs_backend_unhealthy_count", summary.get('unhealthy_backends', 0))
                self._add_metric("vfs_backend_health_percentage", summary.get('health_percentage', 0))
                
                for backend_name, backend_status in backend_health['backends'].items():
                    tags = {"backend": backend_name}
                    self._add_metric("vfs_backend_healthy", 1 if backend_status.get('healthy', False) else 0, tags)
                    self._add_metric("vfs_backend_last_check_age_seconds", 
                                   backend_status.get('last_check_age_seconds', 0), tags)
                    self._add_metric("vfs_backend_is_stale", 1 if backend_status.get('is_stale', False) else 0, tags)
                    
                    if backend_status.get('average_latency_ms') is not None:
                        self._add_metric("vfs_backend_avg_latency_ms", 
                                       backend_status['average_latency_ms'], tags)
                    if backend_status.get('p95_latency_ms') is not None:
                        self._add_metric("vfs_backend_p95_latency_ms", 
                                       backend_status['p95_latency_ms'], tags)
            
            # Process alerts
            alerts = analytics.get('alerts', [])
            self._add_metric("vfs_active_alerts_total", len(alerts))
            
            # Count alerts by severity
            alert_counts = {'critical': 0, 'warning': 0, 'info': 0}
            for alert in alerts:
                severity = alert.get('severity', 'info')
                if severity in alert_counts:
                    alert_counts[severity] += 1
            
            for severity, count in alert_counts.items():
                self._add_metric("vfs_alerts_by_severity", count, {"severity": severity})
                
        except Exception as e:
            logger.error(f"Failed to collect VFS analytics data: {e}")
    
    def _add_metric(self, name: str, value: Any, tags: Optional[Dict[str, str]] = None) -> None:
        """Add a metric data point."""
        if name not in self.metrics:
            self.metrics[name] = MetricSeries(name=name)
        
        self.metrics[name].add_point(value, tags)
        
        # Limit the number of data points to prevent memory issues
        max_points = self.config.max_data_points
        if len(self.metrics[name].data_points) > max_points:
            # Remove oldest points
            self.metrics[name].data_points = self.metrics[name].data_points[-max_points:]
    
    async def _cleanup_old_data(self) -> None:
        """Clean up old data points."""
        for metric in self.metrics.values():
            metric.cleanup_old_data(self.config.data_retention_hours)
    
    def get_metrics(self) -> Dict[str, MetricSeries]:
        """Get all collected metrics."""
        return self.metrics.copy()
    
    def get_metric(self, name: str) -> Optional[MetricSeries]:
        """Get a specific metric by name."""
        return self.metrics.get(name)
    
    def get_latest_values(self) -> Dict[str, Any]:
        """Get the latest values for all metrics."""
        latest = {}
        for name, metric in self.metrics.items():
            latest_point = metric.get_latest()
            if latest_point:
                latest[name] = {
                    "value": latest_point.value,
                    "timestamp": latest_point.timestamp,
                    "tags": latest_point.tags
                }
        return latest
    
    def get_metric_summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics."""
        return {
            "total_metrics": len(self.metrics),
            "total_data_points": sum(len(metric.data_points) for metric in self.metrics.values()),
            "collection_errors": self.error_count,
            "last_error_time": self.last_error_time,
            "is_running": self.is_running,
            "metrics_list": list(self.metrics.keys())
        }
    
    async def get_vfs_deep_insights(self) -> Dict[str, Any]:
        """Get comprehensive VFS insights and analysis."""
        if not self.has_vfs_analytics:
            return {
                'available': False,
                'error': 'VFS analytics not available'
            }
        
        if not self.vfs_monitor: # Added check for vfs_monitor
            return {
                'available': False,
                'error': 'VFS monitor not initialized'
            }

        try:
            # Get comprehensive analytics from VFS monitor
            analytics = self.vfs_monitor.get_analytics_summary()
            
            # Get additional detailed analyses
            bandwidth_analysis = self.vfs_monitor.performance_monitor.get_bandwidth_analysis(60)
            operation_analysis = self.vfs_monitor.performance_monitor.get_operation_analysis(60)
            realtime_metrics = self.vfs_monitor.performance_monitor.get_realtime_metrics()
            replication_health = self.vfs_monitor.performance_monitor.get_replication_health()
            cache_analysis = self.vfs_monitor.performance_monitor.get_cache_analysis()
            backend_health = self.vfs_monitor.performance_monitor.get_backend_health_status()
            
            # Generate performance insights
            insights = self._generate_vfs_performance_insights(analytics)
            recommendations = self._generate_vfs_optimization_recommendations(analytics)
            
            # Get historical trends from collected metrics
            trends = self._analyze_vfs_trends()
            
            return {
                'available': True,
                'timestamp': time.time(),
                'comprehensive_report': analytics,
                'detailed_analyses': {
                    'bandwidth': bandwidth_analysis,
                    'operations': operation_analysis,
                    'realtime': realtime_metrics,
                    'replication': replication_health,
                    'cache': cache_analysis,
                    'backends': backend_health
                },
                'insights': insights,
                'recommendations': recommendations,
                'trends': trends,
                'health_summary': self._generate_vfs_health_summary(analytics)
            }
            
        except Exception as e:
            logger.error(f"Error getting VFS deep insights: {e}")
            return {
                'available': False,
                'error': str(e)
            }
    
    def _generate_vfs_performance_insights(self, analytics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate performance insights from VFS analytics."""
        insights = []
        
        try:
            # Analyze error patterns
            realtime = analytics.get('realtime_metrics', {})
            error_rate = realtime.get('error_rate', 0)
            ops_per_sec = realtime.get('operations_per_second', 0)
            
            if error_rate > 0.05:  # 5% error rate
                insights.append({
                    'type': 'performance_issue',
                    'severity': 'high' if error_rate > 0.2 else 'medium',
                    'category': 'error_rate',
                    'title': 'High VFS Error Rate',
                    'description': f'VFS operations are failing at {error_rate:.1%} rate',
                    'impact': 'Degraded user experience and potential data access issues',
                    'metrics': {'error_rate': error_rate, 'ops_per_second': ops_per_sec}
                })
            
            # Analyze throughput patterns
            if ops_per_sec > 100:
                insights.append({
                    'type': 'performance_pattern',
                    'severity': 'info',
                    'category': 'high_throughput',
                    'title': 'High VFS Throughput',
                    'description': f'VFS is processing {ops_per_sec:.1f} operations per second',
                    'impact': 'System is under heavy load - monitor for bottlenecks',
                    'metrics': {'operations_per_second': ops_per_sec}
                })
            elif ops_per_sec < 0.1 and self.is_running:
                insights.append({
                    'type': 'performance_issue',
                    'severity': 'medium',
                    'category': 'low_activity',
                    'title': 'Low VFS Activity',
                    'description': f'VFS activity is very low ({ops_per_sec:.1f} ops/sec)',
                    'impact': 'May indicate connectivity issues or system underutilization',
                    'metrics': {'operations_per_second': ops_per_sec}
                })
            
            # Analyze bandwidth patterns
            bandwidth = analytics.get('bandwidth_analysis', {})
            if bandwidth and 'total_average_bps' in bandwidth:
                total_bps = bandwidth['total_average_bps']
                if total_bps > 50 * 1024 * 1024:  # 50MB/s
                    insights.append({
                        'type': 'resource_usage',
                        'severity': 'medium',
                        'category': 'high_bandwidth',
                        'title': 'High Bandwidth Usage',
                        'description': f'VFS bandwidth usage: {total_bps / (1024*1024):.1f} MB/s',
                        'impact': 'High network utilization - may affect other services',
                        'metrics': {'bandwidth_mbps': total_bps / (1024*1024)}
                    })
            
            # Analyze cache performance
            cache = analytics.get('cache_analysis', {})
            if cache and 'current_metrics' in cache:
                hit_rate = cache['current_metrics'].get('hit_rate', 0)
                utilization = cache['current_metrics'].get('utilization', 0)
                
                if hit_rate < 0.7:  # 70% hit rate
                    insights.append({
                        'type': 'performance_issue',
                        'severity': 'medium',
                        'category': 'cache_efficiency',
                        'title': 'Low Cache Hit Rate',
                        'description': f'VFS cache hit rate is {hit_rate:.1%}',
                        'impact': 'Increased latency and backend load',
                        'metrics': {'cache_hit_rate': hit_rate, 'cache_utilization': utilization}
                    })
                
                if utilization > 0.9:  # 90% cache utilization
                    insights.append({
                        'type': 'resource_constraint',
                        'severity': 'warning',
                        'category': 'cache_pressure',
                        'title': 'High Cache Memory Pressure',
                        'description': f'VFS cache utilization is {utilization:.1%}',
                        'impact': 'Cache evictions may increase, reducing efficiency',
                        'metrics': {'cache_analysis': utilization}
                    })
            
            # Analyze replication health
            replication = analytics.get('replication_health', {})
            if replication and 'current_status' in replication:
                health_pct = replication['current_status'].get('health_percentage', 100)
                sync_lag = replication['current_status'].get('sync_lag_seconds', 0)
                
                if health_pct < 80:  # 80% healthy replicas
                    insights.append({
                        'type': 'availability_issue',
                        'severity': 'high' if health_pct < 50 else 'medium',
                        'category': 'replication_health',
                        'title': 'Replication Health Issues',
                        'description': f'Only {health_pct:.1f}% of replicas are healthy',
                        'impact': 'Reduced data redundancy and potential data loss risk',
                        'metrics': {'replication_health_percentage': health_pct}
                    })
                
                if sync_lag > 300:  # 5 minutes
                    insights.append({
                        'type': 'performance_issue',
                        'severity': 'medium',
                        'category': 'sync_lag',
                        'title': 'High Replication Sync Lag',
                        'description': f'Replication sync lag is {sync_lag:.1f} seconds',
                        'impact': 'Data consistency issues and delayed propagation',
                        'metrics': {'sync_lag_seconds': sync_lag}
                    })
            
            # Analyze backend health
            backend_health = analytics.get('backend_health', {})
            if backend_health and 'backends' in backend_health::
                summary = backend_health.get('summary', {})
                self._add_metric("vfs_backend_total_count", summary.get('total_backends', 0))
                self._add_metric("vfs_backend_healthy_count", summary.get('healthy_backends', 0))
                self._add_metric("vfs_backend_unhealthy_count", summary.get('unhealthy_backends', 0))
                self._add_metric("vfs_backend_health_percentage", summary.get('health_percentage', 0))
                
                for backend_name, backend_status in backend_health['backends'].items():
                    tags = {"backend": backend_name}
                    self._add_metric("vfs_backend_healthy", 1 if backend_status.get('healthy', False) else 0, tags)
                    self._add_metric("vfs_backend_last_check_age_seconds", 
                                   backend_status.get('last_check_age_seconds', 0), tags)
                    self._add_metric("vfs_backend_is_stale", 1 if backend_status.get('is_stale', False) else 0, tags)
                    
                    if backend_status.get('average_latency_ms') is not None:
                        self._add_metric("vfs_backend_avg_latency_ms", 
                                       backend_status['average_latency_ms'], tags)
                    if backend_status.get('p95_latency_ms') is not None:
                        self._add_metric("vfs_backend_p95_latency_ms", 
                                       backend_status['p95_latency_ms'], tags)
            
            # Process alerts
            alerts = analytics.get('alerts', [])
            self._add_metric("vfs_active_alerts_total", len(alerts))
            
            # Count alerts by severity
            alert_counts = {'critical': 0, 'warning': 0, 'info': 0}
            for alert in alerts:
                severity = alert.get('severity', 'info')
                if severity in alert_counts:
                    alert_counts[severity] += 1
            
            for severity, count in alert_counts.items():
                self._add_metric("vfs_alerts_by_severity", count, {"severity": severity})
                
        except Exception as e:
            logger.error(f"Failed to collect VFS analytics data: {e}")
    
    def _add_metric(self, name: str, value: Any, tags: Optional[Dict[str, str]] = None) -> None:
        """Add a metric data point."""
        if name not in self.metrics:
            self.metrics[name] = MetricSeries(name=name)
        
        self.metrics[name].add_point(value, tags)
        
        # Limit the number of data points to prevent memory issues
        max_points = self.config.max_data_points
        if len(self.metrics[name].data_points) > max_points:
            # Remove oldest points
            self.metrics[name].data_points = self.metrics[name].data_points[-max_points:]
    
    async def _cleanup_old_data(self) -> None:
        """Clean up old data points."""
        for metric in self.metrics.values():
            metric.cleanup_old_data(self.config.data_retention_hours)
    
    def get_metrics(self) -> Dict[str, MetricSeries]:
        """Get all collected metrics."""
        return self.metrics.copy()
    
    def get_metric(self, name: str) -> Optional[MetricSeries]:
        """Get a specific metric by name."""
        return self.metrics.get(name)
    
    def get_latest_values(self) -> Dict[str, Any]:
        """Get the latest values for all metrics."""
        latest = {}
        for name, metric in self.metrics.items():
            latest_point = metric.get_latest()
            if latest_point:
                latest[name] = {
                    "value": latest_point.value,
                    "timestamp": latest_point.timestamp,
                    "tags": latest_point.tags
                }
        return latest
    
    def get_metric_summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics."""
        return {
            "total_metrics": len(self.metrics),
            "total_data_points": sum(len(metric.data_points) for metric in self.metrics.values()),
            "collection_errors": self.error_count,
            "last_error_time": self.last_error_time,
            "is_running": self.is_running,
            "metrics_list": list(self.metrics.keys())
        }
    
    async def get_vfs_deep_insights(self) -> Dict[str, Any]:
        """Get comprehensive VFS insights and analysis."""
        if not self.has_vfs_analytics:
            return {
                'available': False,
                'error': 'VFS analytics not available'
            }
        
        if not self.vfs_monitor: # Added check for vfs_monitor
            return {
                'available': False,
                'error': 'VFS monitor not initialized'
            }

        try:
            # Get comprehensive analytics from VFS monitor
            analytics = self.vfs_monitor.get_analytics_summary()
            
            # Get additional detailed analyses
            bandwidth_analysis = self.vfs_monitor.performance_monitor.get_bandwidth_analysis(60)
            operation_analysis = self.vfs_monitor.performance_monitor.get_operation_analysis(60)
            realtime_metrics = self.vfs_monitor.performance_monitor.get_realtime_metrics()
            replication_health = self.vfs_monitor.performance_monitor.get_replication_health()
            cache_analysis = self.vfs_monitor.performance_monitor.get_cache_analysis()
            backend_health = self.vfs_monitor.performance_monitor.get_backend_health_status()
            
            # Generate performance insights
            insights = self._generate_vfs_performance_insights(analytics)
            recommendations = self._generate_vfs_optimization_recommendations(analytics)
            
            # Get historical trends from collected metrics
            trends = self._analyze_vfs_trends()
            
            return {
                'available': True,
                'timestamp': time.time(),
                'comprehensive_report': analytics,
                'detailed_analyses': {
                    'bandwidth': bandwidth_analysis,
                    'operations': operation_analysis,
                    'realtime': realtime_metrics,
                    'replication': replication_health,
                    'cache': cache_analysis,
                    'backends': backend_health
                },
                'insights': insights,
                'recommendations': recommendations,
                'trends': trends,
                'health_summary': self._generate_vfs_health_summary(analytics)
            }
            
        except Exception as e:
            logger.error(f"Error getting VFS deep insights: {e}")
            return {
                'available': False,
                'error': str(e)
            }
    
    def _generate_vfs_performance_insights(self, analytics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate performance insights from VFS analytics."""
        insights = []
        
        try:
            # Analyze error patterns
            realtime = analytics.get('realtime_metrics', {})
            error_rate = realtime.get('error_rate', 0)
            ops_per_sec = realtime.get('operations_per_second', 0)
            
            if error_rate > 0.05:  # 5% error rate
                insights.append({
                    'type': 'performance_issue',
                    'severity': 'high' if error_rate > 0.2 else 'medium',
                    'category': 'error_rate',
                    'title': 'High VFS Error Rate',
                    'description': f'VFS operations are failing at {error_rate:.1%} rate',
                    'impact': 'Degraded user experience and potential data access issues',
                    'metrics': {'error_rate': error_rate, 'ops_per_second': ops_per_sec}
                })
            
            # Analyze throughput patterns
            if ops_per_sec > 100:
                insights.append({
                    'type': 'performance_pattern',
                    'severity': 'info',
                    'category': 'high_throughput',
                    'title': 'High VFS Throughput',
                    'description': f'VFS is processing {ops_per_sec:.1f} operations per second',
                    'impact': 'System is under heavy load - monitor for bottlenecks',
                    'metrics': {'operations_per_second': ops_per_sec}
                })
            elif ops_per_sec < 0.1 and self.is_running:
                insights.append({
                    'type': 'performance_issue',
                    'severity': 'medium',
                    'category': 'low_activity',
                    'title': 'Low VFS Activity',
                    'description': f'VFS activity is very low ({ops_per_sec:.1f} ops/sec)',
                    'impact': 'May indicate connectivity issues or system underutilization',
                    'metrics': {'operations_per_second': ops_per_sec}
                })
            
            # Analyze bandwidth patterns
            bandwidth = analytics.get('bandwidth_analysis', {})
            if bandwidth and 'total_average_bps' in bandwidth:
                total_bps = bandwidth['total_average_bps']
                if total_bps > 50 * 1024 * 1024:  # 50MB/s
                    insights.append({
                        'type': 'resource_usage',
                        'severity': 'medium',
                        'category': 'high_bandwidth',
                        'title': 'High Bandwidth Usage',
                        'description': f'VFS bandwidth usage: {total_bps / (1024*1024):.1f} MB/s',
                        'impact': 'High network utilization - may affect other services',
                        'metrics': {'bandwidth_mbps': total_bps / (1024*1024)}
                    })
            
            # Analyze cache performance
            cache = analytics.get('cache_analysis', {})
            if cache and 'current_metrics' in cache:
                hit_rate = cache['current_metrics'].get('hit_rate', 0)
                utilization = cache['current_metrics'].get('utilization', 0)
                
                if hit_rate < 0.7:  # 70% hit rate
                    insights.append({
                        'type': 'performance_issue',
                        'severity': 'medium',
                        'category': 'cache_efficiency',
                        'title': 'Low Cache Hit Rate',
                        'description': f'VFS cache hit rate is {hit_rate:.1%}',
                        'impact': 'Increased latency and backend load',
                        'metrics': {'cache_hit_rate': hit_rate, 'cache_utilization': utilization}
                    })
                
                if utilization > 0.9:  # 90% cache utilization
                    insights.append({
                        'type': 'resource_constraint',
                        'severity': 'warning',
                        'category': 'cache_pressure',
                        'title': 'High Cache Memory Pressure',
                        'description': f'VFS cache utilization is {utilization:.1%}',
                        'impact': 'Cache evictions may increase, reducing efficiency',
                        'metrics': {'cache_analysis': utilization}
                    })
            
            # Analyze replication health
            replication = analytics.get('replication_health', {})
            if replication and 'current_status' in replication:
                health_pct = replication['current_status'].get('health_percentage', 100)
                sync_lag = replication['current_status'].get('sync_lag_seconds', 0)
                
                if health_pct < 80:  # 80% healthy replicas
                    insights.append({
                        'type': 'availability_issue',
                        'severity': 'high' if health_pct < 50 else 'medium',
                        'category': 'replication_health',
                        'title': 'Replication Health Issues',
                        'description': f'Only {health_pct:.1f}% of replicas are healthy',
                        'impact': 'Reduced data redundancy and potential data loss risk',
                        'metrics': {'replication_health_percentage': health_pct}
                    })
                
                if sync_lag > 300:  # 5 minutes
                    insights.append({
                        'type': 'performance_issue',
                        'severity': 'medium',
                        'category': 'sync_lag',
                        'title': 'High Replication Sync Lag',
                        'description': f'Replication sync lag is {sync_lag:.1f} seconds',
                        'impact': 'Data consistency issues and delayed propagation',
                        'metrics': {'sync_lag_seconds': sync_lag}
                    })
            
            # Analyze backend health
            backend_health = analytics.get('backend_health', {})
            if backend_health and 'backends' in backend_health::
                summary = backend_health.get('summary', {})
                self._add_metric("vfs_backend_total_count", summary.get('total_backends', 0))
                self._add_metric("vfs_backend_healthy_count", summary.get('healthy_backends', 0))
                self._add_metric("vfs_backend_unhealthy_count", summary.get('unhealthy_backends', 0))
                self._add_metric("vfs_backend_health_percentage", summary.get('health_percentage', 0))
                
                for backend_name, backend_status in backend_health['backends'].items():
                    tags = {"backend": backend_name}
                    self._add_metric("vfs_backend_healthy", 1 if backend_status.get('healthy', False) else 0, tags)
                    self._add_metric("vfs_backend_last_check_age_seconds", 
                                   backend_status.get('last_check_age_seconds', 0), tags)
                    self._add_metric("vfs_backend_is_stale", 1 if backend_status.get('is_stale', False) else 0, tags)
                    
                    if backend_status.get('average_latency_ms') is not None:
                        self._add_metric("vfs_backend_avg_latency_ms", 
                                       backend_status['average_latency_ms'], tags)
                    if backend_status.get('p95_latency_ms') is not None:
                        self._add_metric("vfs_backend_p95_latency_ms", 
                                       backend_status['p95_latency_ms'], tags)
            
            # Process alerts
            alerts = analytics.get('alerts', [])
            self._add_metric("vfs_active_alerts_total", len(alerts))
            
            # Count alerts by severity
            alert_counts = {'critical': 0, 'warning': 0, 'info': 0}
            for alert in alerts:
                severity = alert.get('severity', 'info')
                if severity in alert_counts:
                    alert_counts[severity] += 1
            
            for severity, count in alert_counts.items():
                self._add_metric("vfs_alerts_by_severity", count, {"severity": severity})
                
        except Exception as e:
            logger.error(f"Failed to collect VFS analytics data: {e}")
    
    def _add_metric(self, name: str, value: Any, tags: Optional[Dict[str, str]] = None) -> None:
        """Add a metric data point."""
        if name not in self.metrics:
            self.metrics[name] = MetricSeries(name=name)
        
        self.metrics[name].add_point(value, tags)
        
        # Limit the number of data points to prevent memory issues
        max_points = self.config.max_data_points
        if len(self.metrics[name].data_points) > max_points:
            # Remove oldest points
            self.metrics[name].data_points = self.metrics[name].data_points[-max_points:]
    
    async def _cleanup_old_data(self) -> None:
        """Clean up old data points."""
        for metric in self.metrics.values():
            metric.cleanup_old_data(self.config.data_retention_hours)
    
    def get_metrics(self) -> Dict[str, MetricSeries]:
        """Get all collected metrics."""
        return self.metrics.copy()
    
    def get_metric(self, name: str) -> Optional[MetricSeries]:
        """Get a specific metric by name."""
        return self.metrics.get(name)
    
    def get_latest_values(self) -> Dict[str, Any]:
        """Get the latest values for all metrics."""
        latest = {}
        for name, metric in self.metrics.items():
            latest_point = metric.get_latest()
            if latest_point:
                latest[name] = {
                    "value": latest_point.value,
                    "timestamp": latest_point.timestamp,
                    "tags": latest_point.tags
                }
        return latest
    
    def get_metric_summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics."""
        return {
            "total_metrics": len(self.metrics),
            "total_data_points": sum(len(metric.data_points) for metric in self.metrics.values()),
            "collection_errors": self.error_count,
            "last_error_time": self.last_error_time,
            "is_running": self.is_running,
            "metrics_list": list(self.metrics.keys())
        }
    
    async def get_vfs_deep_insights(self) -> Dict[str, Any]:
        """Get comprehensive VFS insights and analysis."""
        if not self.has_vfs_analytics:
            return {
                'available': False,
                'error': 'VFS analytics not available'
            }
        
        if not self.vfs_monitor: # Added check for vfs_monitor
            return {
                'available': False,
                'error': 'VFS monitor not initialized'
            }

        try:
            # Get comprehensive analytics from VFS monitor
            analytics = self.vfs_monitor.get_analytics_summary()
            
            # Get additional detailed analyses
            bandwidth_analysis = self.vfs_monitor.performance_monitor.get_bandwidth_analysis(60)
            operation_analysis = self.vfs_monitor.performance_monitor.get_operation_analysis(60)
            realtime_metrics = self.vfs_monitor.performance_monitor.get_realtime_metrics()
            replication_health = self.vfs_monitor.performance_monitor.get_replication_health()
            cache_analysis = self.vfs_monitor.performance_monitor.get_cache_analysis()
            backend_health = self.vfs_monitor.performance_monitor.get_backend_health_status()
            
            # Generate performance insights
            insights = self._generate_vfs_performance_insights(analytics)
            recommendations = self._generate_vfs_optimization_recommendations(analytics)
            
            # Get historical trends from collected metrics
            trends = self._analyze_vfs_trends()
            
            return {
                'available': True,
                'timestamp': time.time(),
                'comprehensive_report': analytics,
                'detailed_analyses': {
                    'bandwidth': bandwidth_analysis,
                    'operations': operation_analysis,
                    'realtime': realtime_metrics,
                    'replication': replication_health,
                    'cache': cache_analysis,
                    'backends': backend_health
                },
                'insights': insights,
                'recommendations': recommendations,
                'trends': trends,
                'health_summary': self._generate_vfs_health_summary(analytics)
            }
            
        except Exception as e:
            logger.error(f"Error getting VFS deep insights: {e}")
            return {
                'available': False,
                'error': str(e)
            }
    
    def _generate_vfs_performance_insights(self, analytics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate performance insights from VFS analytics."""
        insights = []
        
        try:
            # Analyze error patterns
            realtime = analytics.get('realtime_metrics', {})
            error_rate = realtime.get('error_rate', 0)
            ops_per_sec = realtime.get('operations_per_second', 0)
            
            if error_rate > 0.05:  # 5% error rate
                insights.append({
                    'type': 'performance_issue',
                    'severity': 'high' if error_rate > 0.2 else 'medium',
                    'category': 'error_rate',
                    'title': 'High VFS Error Rate',
                    'description': f'VFS operations are failing at {error_rate:.1%} rate',
                    'impact': 'Degraded user experience and potential data access issues',
                    'metrics': {'error_rate': error_rate, 'ops_per_second': ops_per_sec}
                })
            
            # Analyze throughput patterns
            if ops_per_sec > 100:
                insights.append({
                    'type': 'performance_pattern',
                    'severity': 'info',
                    'category': 'high_throughput',
                    'title': 'High VFS Throughput',
                    'description': f'VFS is processing {ops_per_sec:.1f} operations per second',
                    'impact': 'System is under heavy load - monitor for bottlenecks',
                    'metrics': {'operations_per_second': ops_per_sec}
                })
            elif ops_per_sec < 0.1 and self.is_running:
                insights.append({
                    'type': 'performance_issue',
                    'severity': 'medium',
                    'category': 'low_activity',
                    'title': 'Low VFS Activity',
                    'description': f'VFS activity is very low ({ops_per_sec:.1f} ops/sec)',
                    'impact': 'May indicate connectivity issues or system underutilization',
                    'metrics': {'operations_per_second': ops_per_sec}
                })
            
            # Analyze bandwidth patterns
            bandwidth = analytics.get('bandwidth', {}) # Changed from bandwidth_analysis to bandwidth
            if bandwidth and 'total_average_bps' in bandwidth:
                total_bps = bandwidth['total_average_bps']
                if total_bps > 50 * 1024 * 1024:  # 50MB/s
                    insights.append({
                        'type': 'resource_usage',
                        'severity': 'medium',
                        'category': 'high_bandwidth',
                        'title': 'High Bandwidth Usage',
                        'description': f'VFS bandwidth usage: {total_bps / (1024*1024):.1f} MB/s',
                        'impact': 'High network utilization - may affect other services',
                        'metrics': {'bandwidth_mbps': total_bps / (1024*1024)}
                    })
            
            # Analyze cache performance
            cache = analytics.get('cache_analysis', {})
            if cache and 'current_metrics' in cache:
                hit_rate = cache['current_metrics'].get('hit_rate', 0)
                utilization = cache['current_metrics'].get('utilization', 0)
                
                if hit_rate < 0.7:  # 70% hit rate
                    insights.append({
                        'type': 'performance_issue',
                        'severity': 'medium',
                        'category': 'cache_efficiency',
                        'title': 'Low Cache Hit Rate',
                        'description': f'VFS cache hit rate is {hit_rate:.1%}',
                        'impact': 'Increased latency and backend load',
                        'metrics': {'cache_hit_rate': hit_rate, 'cache_utilization': utilization}
                    })
                
                if utilization > 0.9:  # 90% cache utilization
                    insights.append({
                        'type': 'resource_constraint',
                        'severity': 'warning',
                        'category': 'cache_pressure',
                        'title': 'High Cache Memory Pressure',
                        'description': f'VFS cache utilization is {utilization:.1%}',
                        'impact': 'Cache evictions may increase, reducing efficiency',
                        'metrics': {'cache_utilization': utilization}
                    })
            
            # Analyze replication health
            replication = analytics.get('replication_health', {})
            if replication and 'current_status' in replication:
                health_pct = replication['current_status'].get('health_percentage', 100)
                sync_lag = replication['current_status'].get('sync_lag_seconds', 0)
                
                if health_pct < 80:  # 80% healthy replicas
                    insights.append({
                        'type': 'availability_issue',
                        'severity': 'high' if health_pct < 50 else 'medium',
                        'category': 'replication_health',
                        'title': 'Replication Health Issues',
                        'description': f'Only {health_pct:.1f}% of replicas are healthy',
                        'impact': 'Reduced data redundancy and potential data loss risk',
                        'metrics': {'replication_health_percentage': health_pct}
                    })
                
                if sync_lag > 300:  # 5 minutes
                    insights.append({
                        'type': 'performance_issue',
                        'severity': 'medium',
                        'category': 'sync_lag',
                        'title': 'High Replication Sync Lag',
                        'description': f'Replication sync lag is {sync_lag:.1f} seconds',
                        'impact': 'Data consistency issues and delayed propagation',
                        'metrics': {'sync_lag_seconds': sync_lag}
                    })
            
            # Analyze backend health
            backend_health = analytics.get('backend_health', {})
            if backend_health and 'backends' in backend_health:
