# ipfs_kit_py/wal_telemetry_prometheus.py

"""
Prometheus integration for WAL telemetry.

This module provides Prometheus integration for the WAL telemetry system,
allowing WAL performance metrics to be exposed in Prometheus format
for monitoring with Prometheus, Grafana, and other observability tools.
"""

import time
import logging
import threading
from typing import Dict, List, Any, Optional, Union, Set

# Try to import the WAL telemetry module
try:
    from .wal_telemetry import (
        WALTelemetry,
        TelemetryMetricType,
        TelemetryAggregation
    )
    WAL_TELEMETRY_AVAILABLE = True
except ImportError:
    WAL_TELEMETRY_AVAILABLE = False
    
# Try to import Prometheus client
try:
    import prometheus_client
    from prometheus_client import (
        Counter, Gauge, Histogram, Summary, 
        CollectorRegistry, start_http_server
    )
    from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily
    
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
    
    class GaugeMetricFamily:
        def __init__(self, *args, **kwargs):
            pass
        def add_metric(self, *args, **kwargs):
            pass
            
    class CounterMetricFamily:
        def __init__(self, *args, **kwargs):
            pass
        def add_metric(self, *args, **kwargs):
            pass

# Configure logging
logger = logging.getLogger(__name__)

class WALTelemetryCollector:
    """
    Prometheus collector for WAL telemetry metrics.
    
    This collector integrates with the WAL telemetry system to expose
    performance metrics in a format that can be scraped by Prometheus.
    """
    
    def __init__(self, telemetry: Any, prefix: str = "wal"):
        """
        Initialize the WAL telemetry collector.
        
        Args:
            telemetry: WALTelemetry instance to collect metrics from
            prefix: Prefix for metric names (default: "wal")
        """
        if not WAL_TELEMETRY_AVAILABLE:
            raise ImportError("WAL telemetry module not available")
            
        self.telemetry = telemetry
        self.prefix = prefix
        self.last_update = 0
        self.update_interval = 5  # seconds
        self.known_operation_types = set()
        self.known_backends = set()
        
    def collect(self):
        """
        Collect WAL telemetry metrics for Prometheus.
        
        This method is called by Prometheus client during scraping.
        It returns a list of metrics in Prometheus format.
        """
        # Update metrics at most once per update_interval
        current_time = time.time()
        if current_time - self.last_update > self.update_interval:
            # Get real-time metrics
            self.rt_metrics = self.telemetry.get_real_time_metrics()
            self.last_update = current_time
            
            # Update operation types and backends for dimension tracking
            for key in self.rt_metrics.get("latency", {}):
                if ":" in key:
                    op_type, backend = key.split(":", 1)
                    self.known_operation_types.add(op_type)
                    self.known_backends.add(backend)
        
        # Define and yield metrics
        metrics = []
        
        # 1. Operation latency metrics
        for metric_name, stat_name in [
            ("latency_seconds", "mean"),
            ("latency_seconds_median", "median"),
            ("latency_seconds_max", "max"),
            ("latency_seconds_min", "min"),
            ("latency_seconds_p95", "percentile_95")
        ]:
            metric = GaugeMetricFamily(
                f"{self.prefix}_operation_{metric_name}",
                f"Operation {stat_name.replace('_', ' ')} latency in seconds",
                labels=["operation_type", "backend"]
            )
            
            for key, stats in self.rt_metrics.get("latency", {}).items():
                if ":" in key:
                    op_type, backend = key.split(":", 1)
                    metric.add_metric([op_type, backend], stats.get(stat_name, 0))
                    
            yield metric
        
        # 2. Success rate metrics
        success_rate = GaugeMetricFamily(
            f"{self.prefix}_operation_success_rate",
            "Operation success rate (0-1)",
            labels=["operation_type", "backend"]
        )
        
        for key, rate in self.rt_metrics.get("success_rate", {}).items():
            if ":" in key:
                op_type, backend = key.split(":", 1)
                success_rate.add_metric([op_type, backend], rate)
                
        yield success_rate
        
        # 3. Error rate metrics
        error_rate = GaugeMetricFamily(
            f"{self.prefix}_operation_error_rate",
            "Operation error rate (0-1)",
            labels=["operation_type", "backend"]
        )
        
        for key, rate in self.rt_metrics.get("error_rate", {}).items():
            if ":" in key:
                op_type, backend = key.split(":", 1)
                error_rate.add_metric([op_type, backend], rate)
                
        yield error_rate
        
        # 4. Throughput metrics
        throughput = GaugeMetricFamily(
            f"{self.prefix}_operations_per_minute",
            "Operation throughput (operations per minute)",
            labels=["operation_type", "backend"]
        )
        
        for key, rate in self.rt_metrics.get("throughput", {}).items():
            if ":" in key:
                op_type, backend = key.split(":", 1)
                throughput.add_metric([op_type, backend], rate)
                
        yield throughput
        
        # 5. Operation status counts
        status_counts = GaugeMetricFamily(
            f"{self.prefix}_operations_by_status",
            "Number of operations by status",
            labels=["operation_type", "backend", "status"]
        )
        
        for key, counts in self.rt_metrics.get("status_distribution", {}).items():
            if ":" in key:
                op_type, backend = key.split(":", 1)
                for status, count in counts.items():
                    status_counts.add_metric([op_type, backend, status], count)
                    
        yield status_counts
        
        # If we have access to the WAL instance via telemetry, get more metrics
        if hasattr(self.telemetry, "wal") and self.telemetry.wal:
            wal = self.telemetry.wal
            
            # 6. Queue metrics
            queue_size = GaugeMetricFamily(
                f"{self.prefix}_queue_size",
                "Number of operations in queue",
                labels=["status"]
            )
            
            try:
                stats = wal.get_statistics()
                for status, count in stats.items():
                    if status in ["pending", "processing", "total_operations"]:
                        queue_size.add_metric([status], count)
            except Exception as e:
                logger.warning(f"Error getting WAL statistics: {e}")
                
            yield queue_size
            
            # 7. Backend health metrics
            if hasattr(wal, "health_monitor") and wal.health_monitor:
                backend_health = GaugeMetricFamily(
                    f"{self.prefix}_backend_health",
                    "Backend health status (1=online, 0.5=degraded, 0=offline)",
                    labels=["backend"]
                )
                
                try:
                    statuses = wal.health_monitor.get_status()
                    for backend, status_info in statuses.items():
                        # Convert status to numeric value
                        status_value = 1.0 if status_info.get("status") == "online" else \
                                       0.5 if status_info.get("status") == "degraded" else 0.0
                        backend_health.add_metric([backend], status_value)
                except Exception as e:
                    logger.warning(f"Error getting backend health: {e}")
                    
                yield backend_health
                
                # 8. Backend response time
                backend_latency = GaugeMetricFamily(
                    f"{self.prefix}_backend_response_time_seconds",
                    "Backend response time in seconds",
                    labels=["backend"]
                )
                
                try:
                    for backend, status_info in statuses.items():
                        latency = status_info.get("last_response_time", 0)
                        backend_latency.add_metric([backend], latency)
                except Exception as e:
                    logger.warning(f"Error getting backend latency: {e}")
                    
                yield backend_latency

class WALTelemetryPrometheusExporter:
    """
    Prometheus exporter for WAL telemetry.
    
    This class provides a Prometheus exporter for WAL telemetry metrics,
    making them available for scraping by Prometheus monitoring systems.
    """
    
    def __init__(self, 
                 telemetry: Any, 
                 prefix: str = "wal",
                 registry: Optional[CollectorRegistry] = None):
        """
        Initialize the WAL telemetry Prometheus exporter.
        
        Args:
            telemetry: WALTelemetry instance to expose metrics from
            prefix: Prefix for metric names (default: "wal")
            registry: Custom Prometheus registry (default: create new)
        """
        if not WAL_TELEMETRY_AVAILABLE:
            raise ImportError("WAL telemetry module not available")
            
        if not PROMETHEUS_AVAILABLE:
            raise ImportError("Prometheus client not available")
            
        self.telemetry = telemetry
        self.prefix = prefix
        self.registry = registry or CollectorRegistry()
        
        # Create and register collector
        self.collector = WALTelemetryCollector(telemetry, prefix)
        self.registry.register(self.collector)
        
        # Create thread-safe lock for server management
        self._lock = threading.RLock()
        self._server = None
        self._server_port = None
        
    def start_server(self, port: int = 9100, addr: str = "") -> bool:
        """
        Start a metrics server for Prometheus scraping.
        
        Args:
            port: Port to listen on
            addr: Address to bind to
            
        Returns:
            True if server started successfully, False otherwise
        """
        with self._lock:
            if self._server is not None:
                logger.warning(f"Prometheus server already running on port {self._server_port}")
                return False
                
            try:
                # Check that port is available
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                result = sock.connect_ex((addr or "localhost", port))
                sock.close()
                
                if result == 0:
                    logger.error(f"Port {port} is already in use")
                    return False
                
                # Start HTTP server for metrics
                prometheus_client.start_http_server(port, addr, self.registry)
                self._server_port = port
                logger.info(f"Started Prometheus metrics server on {addr or '0.0.0.0'}:{port}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to start Prometheus metrics server: {e}")
                return False
                
    def stop_server(self) -> bool:
        """
        Stop the metrics server.
        
        Returns:
            True if server stopped successfully, False otherwise
        """
        with self._lock:
            if self._server is None:
                logger.warning("Prometheus server not running")
                return False
                
            try:
                # Unfortunately, prometheus_client doesn't provide a clean way to stop the server
                # We'll need to implement this manually if needed
                logger.warning("Stopping Prometheus server not implemented")
                return False
                
            except Exception as e:
                logger.error(f"Failed to stop Prometheus metrics server: {e}")
                return False
                
    def generate_latest(self) -> bytes:
        """
        Generate Prometheus metrics output in text format.
        
        Returns:
            Metrics in Prometheus text format
        """
        if not PROMETHEUS_AVAILABLE:
            return b""
            
        return prometheus_client.generate_latest(self.registry)

def add_wal_metrics_endpoint(app, telemetry, path: str = "/metrics/wal"):
    """
    Add a WAL telemetry metrics endpoint to a FastAPI application.
    
    Args:
        app: FastAPI application instance
        telemetry: WALTelemetry instance
        path: Endpoint path for metrics
        
    Returns:
        True if successful, False otherwise
    """
    if not WAL_TELEMETRY_AVAILABLE:
        logger.warning("WAL telemetry not available, skipping metrics endpoint")
        return False
        
    if not PROMETHEUS_AVAILABLE:
        logger.warning("Prometheus client not available, skipping metrics endpoint")
        return False
        
    try:
        from fastapi import Request
        from fastapi.responses import Response
        
        # Create exporter
        exporter = WALTelemetryPrometheusExporter(telemetry, prefix="wal")
        
        # Add endpoint
        @app.get(path)
        async def wal_metrics(request: Request):
            return Response(
                content=exporter.generate_latest(),
                media_type="text/plain"
            )
            
        logger.info(f"Added WAL metrics endpoint at {path}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to add WAL metrics endpoint: {e}")
        return False

# Example usage
if __name__ == "__main__":
    # Enable debug logging
    logging.basicConfig(level=logging.INFO)
    
    if not WAL_TELEMETRY_AVAILABLE:
        print("WAL telemetry module not available")
        exit(1)
        
    if not PROMETHEUS_AVAILABLE:
        print("Prometheus client not available. Install with 'pip install prometheus-client'")
        exit(1)
        
    # Create WAL and telemetry instances
    try:
        from ipfs_kit_py.wal_telemetry import WALTelemetry
        from ipfs_kit_py.storage_wal import (
            StorageWriteAheadLog, 
            BackendHealthMonitor
        )
        
        # Create WAL components
        health_monitor = BackendHealthMonitor(
            check_interval=5,
            history_size=10
        )
        
        wal = StorageWriteAheadLog(
            base_path="~/.ipfs_kit/wal",
            partition_size=100,
            health_monitor=health_monitor
        )
        
        # Create telemetry instance
        telemetry = WALTelemetry(
            wal=wal,
            metrics_path="~/.ipfs_kit/telemetry",
            sampling_interval=10,
            enable_detailed_timing=True,
            operation_hooks=True
        )
        
        # Create Prometheus exporter
        exporter = WALTelemetryPrometheusExporter(telemetry)
        
        # Start metrics server
        exporter.start_server(port=9101)
        
        print("Prometheus metrics server running on port 9101")
        print("Press Ctrl+C to exit")
        
        # Add some operations to generate telemetry data
        for i in range(5):
            result = wal.add_operation(
                operation_type="add",
                backend="ipfs",
                parameters={"path": f"/tmp/file{i}.txt"}
            )
            print(f"Added operation: {result['operation_id']}")
            
        # Keep running until interrupted
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Exiting...")
        finally:
            # Clean up
            telemetry.close()
            wal.close()
            health_monitor.close()
            
    except ImportError as e:
        print(f"Error importing required modules: {e}")
        exit(1)