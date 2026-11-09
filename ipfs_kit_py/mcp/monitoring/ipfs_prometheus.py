"""
Prometheus Integration for IPFS Operations.

This module provides Prometheus metrics collection and export capabilities
for the advanced IPFS operations, enabling comprehensive monitoring and
performance analytics.
"""

import logging
import time
from typing import Any, Dict, List, Optional, Set, Union

from prometheus_client import Counter, Gauge, Histogram, Summary, start_http_server, Info

# Set up logging
logger = logging.getLogger("ipfs_prometheus")

# Define Prometheus metrics
class IPFSMetrics:
    """
    Prometheus metrics for IPFS operations.
    
    This class defines and manages Prometheus metrics for monitoring
    the performance and activity of IPFS operations.
    """
    
    def __init__(self):
        """Initialize the IPFS metrics."""
        # General IPFS operations metrics
        self.api_requests = Counter(
            'ipfs_api_requests_total',
            'Total number of IPFS API requests',
            ['method', 'endpoint']
        )
        
        self.api_errors = Counter(
            'ipfs_api_errors_total',
            'Total number of IPFS API request errors',
            ['method', 'endpoint', 'error_type']
        )
        
        self.api_latency = Histogram(
            'ipfs_api_request_duration_seconds',
            'IPFS API request latency in seconds',
            ['method', 'endpoint'],
            buckets=[0.01, 0.05, 0.1, 0.5, 1, 5, 10, 30]
        )
        
        # Connection pool metrics
        self.connection_pool_size = Gauge(
            'ipfs_connection_pool_size',
            'Current size of the IPFS connection pool'
        )
        
        self.connection_pool_active = Gauge(
            'ipfs_connection_pool_active',
            'Number of active connections in the IPFS connection pool'
        )
        
        self.connection_pool_idle = Gauge(
            'ipfs_connection_pool_idle',
            'Number of idle connections in the IPFS connection pool'
        )
        
        self.connection_pool_wait_time = Histogram(
            'ipfs_connection_pool_wait_seconds',
            'Time spent waiting for an available connection',
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1]
        )
        
        # DHT operation metrics
        self.dht_operations = Counter(
            'ipfs_dht_operations_total',
            'Total number of DHT operations',
            ['operation']
        )
        
        self.dht_operation_errors = Counter(
            'ipfs_dht_operation_errors_total',
            'Total number of DHT operation errors',
            ['operation', 'error_type']
        )
        
        self.dht_operation_latency = Histogram(
            'ipfs_dht_operation_duration_seconds',
            'DHT operation latency in seconds',
            ['operation'],
            buckets=[0.1, 0.5, 1, 5, 10, 30, 60]
        )
        
        self.dht_peers_found = Histogram(
            'ipfs_dht_peers_found',
            'Number of peers found in DHT operations',
            ['operation'],
            buckets=[0, 1, 2, 5, 10, 20, 50, 100]
        )
        
        # IPNS operation metrics
        self.ipns_operations = Counter(
            'ipfs_ipns_operations_total',
            'Total number of IPNS operations',
            ['operation']
        )
        
        self.ipns_operation_errors = Counter(
            'ipfs_ipns_operation_errors_total',
            'Total number of IPNS operation errors',
            ['operation', 'error_type']
        )
        
        self.ipns_operation_latency = Histogram(
            'ipfs_ipns_operation_duration_seconds',
            'IPNS operation latency in seconds',
            ['operation'],
            buckets=[0.1, 0.5, 1, 5, 10, 30, 60]
        )
        
        self.ipns_keys_count = Gauge(
            'ipfs_ipns_keys_count',
            'Number of IPNS keys available'
        )
        
        # DAG operation metrics
        self.dag_operations = Counter(
            'ipfs_dag_operations_total',
            'Total number of DAG operations',
            ['operation']
        )
        
        self.dag_operation_errors = Counter(
            'ipfs_dag_operation_errors_total',
            'Total number of DAG operation errors',
            ['operation', 'error_type']
        )
        
        self.dag_operation_latency = Histogram(
            'ipfs_dag_operation_duration_seconds',
            'DAG operation latency in seconds',
            ['operation'],
            buckets=[0.1, 0.5, 1, 5, 10, 30, 60]
        )
        
        self.dag_node_size = Histogram(
            'ipfs_dag_node_size_bytes',
            'Size of DAG nodes in bytes',
            buckets=[100, 1000, 10000, 100000, 1000000, 10000000]
        )
        
        # Content metrics
        self.content_add_size = Histogram(
            'ipfs_content_add_size_bytes',
            'Size of content added to IPFS in bytes',
            buckets=[1000, 10000, 100000, 1000000, 10000000, 100000000]
        )
        
        self.content_get_size = Histogram(
            'ipfs_content_get_size_bytes',
            'Size of content retrieved from IPFS in bytes',
            buckets=[1000, 10000, 100000, 1000000, 10000000, 100000000]
        )
        
        self.content_add_latency = Histogram(
            'ipfs_content_add_duration_seconds',
            'Time to add content to IPFS in seconds',
            buckets=[0.1, 0.5, 1, 5, 10, 30, 60, 300]
        )
        
        self.content_get_latency = Histogram(
            'ipfs_content_get_duration_seconds',
            'Time to retrieve content from IPFS in seconds',
            buckets=[0.1, 0.5, 1, 5, 10, 30, 60, 300]
        )
        
        self.pins_count = Gauge(
            'ipfs_pins_count',
            'Number of pinned items in IPFS'
        )
        
        # MCP Server integration metrics
        self.integration_usage = Counter(
            'ipfs_advanced_integration_usage_total',
            'Usage count of advanced IPFS integrations',
            ['operation', 'source']
        )
        
        # Node information
        self.node_info = Info(
            'ipfs_node',
            'Information about the IPFS node'
        )
    
    def update_node_info(self, node_id: str, version: str, addresses: List[str]):
        """
        Update IPFS node information.
        
        Args:
            node_id: IPFS node ID
            version: IPFS version
            addresses: List of node multiaddresses
        """
        self.node_info.info({
            'node_id': node_id,
            'version': version,
            'addresses': ','.join(addresses),
            'updated_at': str(int(time.time()))
        })
    
    def track_api_request(
        self, method: str, endpoint: str, duration: float, error: Optional[str] = None
    ):
        """
        Track an IPFS API request.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint called
            duration: Request duration in seconds
            error: Optional error type if request failed
        """
        self.api_requests.labels(method=method, endpoint=endpoint).inc()
        self.api_latency.labels(method=method, endpoint=endpoint).observe(duration)
        
        if error:
            self.api_errors.labels(method=method, endpoint=endpoint, error_type=error).inc()
    
    def track_connection_pool(self, total: int, active: int, idle: int, wait_time: Optional[float] = None):
        """
        Track connection pool metrics.
        
        Args:
            total: Total connections in pool
            active: Active connections in use
            idle: Idle connections
            wait_time: Optional time spent waiting for a connection
        """
        self.connection_pool_size.set(total)
        self.connection_pool_active.set(active)
        self.connection_pool_idle.set(idle)
        
        if wait_time is not None:
            self.connection_pool_wait_time.observe(wait_time)
    
    def track_dht_operation(
        self, operation: str, duration: float, success: bool, peers_found: Optional[int] = None, error: Optional[str] = None
    ):
        """
        Track a DHT operation.
        
        Args:
            operation: DHT operation name
            duration: Operation duration in seconds
            success: Whether operation was successful
            peers_found: Optional number of peers found
            error: Optional error type if operation failed
        """
        self.dht_operations.labels(operation=operation).inc()
        self.dht_operation_latency.labels(operation=operation).observe(duration)
        
        if not success and error:
            self.dht_operation_errors.labels(operation=operation, error_type=error).inc()
        
        if peers_found is not None:
            self.dht_peers_found.labels(operation=operation).observe(peers_found)
    
    def track_ipns_operation(
        self, operation: str, duration: float, success: bool, error: Optional[str] = None
    ):
        """
        Track an IPNS operation.
        
        Args:
            operation: IPNS operation name
            duration: Operation duration in seconds
            success: Whether operation was successful
            error: Optional error type if operation failed
        """
        self.ipns_operations.labels(operation=operation).inc()
        self.ipns_operation_latency.labels(operation=operation).observe(duration)
        
        if not success and error:
            self.ipns_operation_errors.labels(operation=operation, error_type=error).inc()
    
    def set_ipns_keys_count(self, count: int):
        """
        Set the count of IPNS keys.
        
        Args:
            count: Number of IPNS keys
        """
        self.ipns_keys_count.set(count)
    
    def track_dag_operation(
        self, operation: str, duration: float, success: bool, node_size: Optional[int] = None, error: Optional[str] = None
    ):
        """
        Track a DAG operation.
        
        Args:
            operation: DAG operation name
            duration: Operation duration in seconds
            success: Whether operation was successful
            node_size: Optional size of the DAG node in bytes
            error: Optional error type if operation failed
        """
        self.dag_operations.labels(operation=operation).inc()
        self.dag_operation_latency.labels(operation=operation).observe(duration)
        
        if not success and error:
            self.dag_operation_errors.labels(operation=operation, error_type=error).inc()
        
        if node_size is not None:
            self.dag_node_size.observe(node_size)
    
    def track_content_add(self, size: int, duration: float):
        """
        Track content addition to IPFS.
        
        Args:
            size: Content size in bytes
            duration: Operation duration in seconds
        """
        self.content_add_size.observe(size)
        self.content_add_latency.observe(duration)
    
    def track_content_get(self, size: int, duration: float):
        """
        Track content retrieval from IPFS.
        
        Args:
            size: Content size in bytes
            duration: Operation duration in seconds
        """
        self.content_get_size.observe(size)
        self.content_get_latency.observe(duration)
    
    def set_pins_count(self, count: int):
        """
        Set the count of pinned items.
        
        Args:
            count: Number of pinned items
        """
        self.pins_count.set(count)
    
    def track_integration_usage(self, operation: str, source: str):
        """
        Track usage of the advanced IPFS integration.
        
        Args:
            operation: Operation being used
            source: Source/component using the integration
        """
        self.integration_usage.labels(operation=operation, source=source).inc()

# Singleton instance
_metrics_instance = None

def get_metrics_instance() -> IPFSMetrics:
    """
    Get or create a singleton metrics instance.
    
    Returns:
        IPFSMetrics instance
    """
    global _metrics_instance
    
    if _metrics_instance is None:
        _metrics_instance = IPFSMetrics()
    
    return _metrics_instance

class PrometheusExporter:
    """
    Prometheus metrics exporter for IPFS operations.
    
    This class provides a metrics server that exposes the IPFS metrics
    in Prometheus format for scraping.
    """
    
    def __init__(self, host: str = "localhost", port: int = 9090):
        """
        Initialize the Prometheus exporter.
        
        Args:
            host: Host to bind the metrics server to
            port: Port to bind the metrics server to
        """
        self.host = host
        self.port = port
        self.server_started = False
        self.metrics = get_metrics_instance()
        
        logger.info(f"Prometheus exporter initialized (will listen on {host}:{port})")
    
    def start(self):
        """Start the Prometheus metrics server."""
        if not self.server_started:
            logger.info(f"Starting Prometheus metrics server on {self.host}:{self.port}")
            start_http_server(self.port, self.host)
            self.server_started = True
            logger.info(f"Prometheus metrics server started at http://{self.host}:{self.port}/metrics")
    
    def get_metrics(self) -> IPFSMetrics:
        """
        Get the metrics instance.
        
        Returns:
            IPFSMetrics instance
        """
        return self.metrics

# Singleton instance
_exporter_instance = None

def get_exporter_instance(host: str = "localhost", port: int = 9090) -> PrometheusExporter:
    """
    Get or create a singleton exporter instance.
    
    Args:
        host: Host to bind the metrics server to
        port: Port to bind the metrics server to
        
    Returns:
        PrometheusExporter instance
    """
    global _exporter_instance
    
    if _exporter_instance is None:
        _exporter_instance = PrometheusExporter(host, port)
    
    return _exporter_instance