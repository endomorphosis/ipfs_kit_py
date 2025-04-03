# Observability with Prometheus and Grafana

IPFS Kit includes comprehensive observability features using Prometheus and Grafana for monitoring, alerting, and visualization of system performance and operational metrics.

## Overview

The observability stack provides real-time insights into:

- **System Resources**: CPU, memory, and disk usage across all IPFS nodes
- **Cache Performance**: Hit ratios, sizes, and eviction metrics for all cache tiers
- **Operation Metrics**: Rate, latency, and error metrics for IPFS operations
- **Network Metrics**: Bandwidth usage, peer connections, and data transfer rates
- **Content Statistics**: Pin counts, total content size, and storage distribution

## Architecture

The observability implementation consists of three main components:

1. **Metrics Collection**: The `prometheus_exporter.py` module converts internal performance metrics to Prometheus format and exposes them via an HTTP endpoint.

2. **Prometheus Server**: Scrapes metrics from all IPFS nodes at configurable intervals and stores them in a time-series database.

3. **Grafana Dashboards**: Provides visualization of metrics with pre-configured dashboards for system and operations monitoring.

```mermaid
graph TD
    A[IPFS Kit] -->|Exposes Metrics| B[/metrics Endpoint]
    B -->|Scrapes| C[Prometheus Server]
    C -->|Visualizes| D[Grafana Dashboards]
    
    subgraph "IPFS Node"
        A
        B
    end
    
    subgraph "Observability Stack"
        C
        D
    end
```

## Metrics Collection

### Key Metric Types

IPFS Kit exposes the following metric types through the Prometheus exporter:

1. **Counters**: Monotonically increasing values for operations, errors, and data transfers
   - `ipfs_operations_total`: Count of operations by type (add, get, pin, etc.)
   - `ipfs_errors_total`: Count of errors by type
   - `ipfs_errors_by_type_total`: Count of errors by error type (connection, timeout, etc.)
   - `ipfs_cache_hits_total`: Total number of cache hits
   - `ipfs_cache_misses_total`: Total number of cache misses
   - `ipfs_cache_tier_hits_total`: Total number of cache hits by tier (memory, disk, etc.)
   - `ipfs_cache_tier_misses_total`: Total number of cache misses by tier
   - `ipfs_bandwidth_inbound_bytes_total`: Total bytes received
   - `ipfs_bandwidth_outbound_bytes_total`: Total bytes sent

2. **Gauges**: Current values for system resources and states
   - `ipfs_cpu_usage_percent`: Current CPU usage percentage
   - `ipfs_memory_usage_percent`: Current memory usage percentage  
   - `ipfs_memory_available_bytes`: Available memory in bytes
   - `ipfs_disk_usage_percent`: Current disk usage percentage
   - `ipfs_disk_free_bytes`: Free disk space in bytes
   - `ipfs_cache_hit_ratio`: Ratio of cache hits to total accesses
   - `ipfs_operations_per_second`: Current operations per second
   - `ipfs_bytes_per_second`: Current bytes per second (total throughput)

3. **Histograms**: Distribution of operation durations
   - `ipfs_operation_latency_seconds`: Latency of IPFS operations with buckets for different duration ranges
   - Includes percentile buckets from 5ms to 120s for comprehensive latency analysis
   - Segmented by operation type through labels

4. **Labels**: All metrics include contextual labels where appropriate
   - `operation`: Type of operation (add, get, cat, pin, etc.)
   - `tier`: Cache tier (memory, disk, etc.)
   - `error_type`: Type of error (connection, timeout, etc.)
   - Additional custom labels can be added when initializing the exporter

5. **Role-specific Metrics**: Metrics are tagged with the node role
   - Master nodes expose additional cluster and replication metrics
   - Worker nodes focus on processing and throughput metrics
   - Leecher nodes emphasize cache and network efficiency

### Complete Metrics Reference

Below is a comprehensive list of all metrics exposed by the IPFS Kit Prometheus exporter:

#### Cache Metrics
| Metric Name | Type | Description | Labels |
|-------------|------|-------------|--------|
| `ipfs_cache_hits_total` | Counter | Total number of cache hits | - |
| `ipfs_cache_misses_total` | Counter | Total number of cache misses | - |
| `ipfs_cache_hit_ratio` | Gauge | Ratio of cache hits to total accesses | - |
| `ipfs_cache_tier_hits_total` | Counter | Total number of cache hits by tier | `tier` |
| `ipfs_cache_tier_misses_total` | Counter | Total number of cache misses by tier | `tier` |

#### Operation Metrics
| Metric Name | Type | Description | Labels |
|-------------|------|-------------|--------|
| `ipfs_operations_total` | Counter | Count of IPFS operations by type | `operation` |
| `ipfs_operation_latency_seconds` | Histogram | Latency of IPFS operations | `operation` |
| `ipfs_operations_per_second` | Gauge | Operations per second | - |

#### Bandwidth Metrics
| Metric Name | Type | Description | Labels |
|-------------|------|-------------|--------|
| `ipfs_bandwidth_inbound_bytes_total` | Counter | Total inbound bandwidth used | - |
| `ipfs_bandwidth_outbound_bytes_total` | Counter | Total outbound bandwidth used | - |
| `ipfs_bytes_per_second` | Gauge | Bytes per second (total throughput) | - |

#### Error Metrics
| Metric Name | Type | Description | Labels |
|-------------|------|-------------|--------|
| `ipfs_errors_total` | Counter | Total number of errors | - |
| `ipfs_errors_by_type_total` | Counter | Count of errors by type | `error_type` |

#### System Metrics
| Metric Name | Type | Description | Labels |
|-------------|------|-------------|--------|
| `ipfs_cpu_usage_percent` | Gauge | CPU usage percentage | - |
| `ipfs_memory_usage_percent` | Gauge | Memory usage percentage | - |
| `ipfs_memory_available_bytes` | Gauge | Available memory in bytes | - |
| `ipfs_disk_usage_percent` | Gauge | Disk usage percentage | - |
| `ipfs_disk_free_bytes` | Gauge | Free disk space in bytes | - |

### Metrics Exporter

IPFS Kit includes a custom Prometheus metrics exporter in the `prometheus_exporter.py` module that converts internal performance metrics from the `PerformanceMetrics` class to Prometheus format. The exporter supports:

1. **Dynamic Metric Creation**: Creates appropriate Prometheus metrics based on the performance data collected
2. **Label Support**: Adds metadata labels to metrics for filtering and aggregation
3. **Integration with FastAPI**: Automatically adds a `/metrics` endpoint to the API server
4. **Automatic Updates**: Keeps metrics up-to-date as operations are performed
5. **Graceful Degradation**: Falls back to basic functionality if Prometheus client is unavailable

Metrics are exposed using the standard Prometheus text exposition format and can be scraped by any Prometheus-compatible monitoring system.

### Enabling Metrics

Metrics collection is optional and can be enabled in multiple ways:

1. **Configuration File**:
```yaml
observability:
  metrics_enabled: true
  prometheus_port: 9100
  metrics_path: /metrics
```

2. **Environment Variables**:
```bash
export IPFS_KIT_METRICS_ENABLED=true
export IPFS_KIT_METRICS_PATH=/metrics
export IPFS_KIT_METRICS_PORT=9100
```

3. **Programmatically**:
```python
from ipfs_kit_py.ipfs_kit import ipfs_kit

kit = ipfs_kit(metadata={
    "metrics_enabled": True,
    "metrics_path": "/metrics",
    "metrics_port": 9100
})
```

### Standalone Metrics Server

You can also run a standalone metrics server without using the API:

```python
from ipfs_kit_py.ipfs_kit import ipfs_kit
from ipfs_kit_py.prometheus_exporter import PrometheusExporter

# Initialize IPFS Kit
kit = ipfs_kit()

# Get performance metrics instance
metrics = kit.performance_metrics

# Create exporter with custom labels
exporter = PrometheusExporter(
    metrics, 
    prefix="ipfs", 
    labels={"node_type": "master", "environment": "production"}
)

# Start a metrics server
exporter.start_server(port=9100)
```

## Prometheus Configuration

The Prometheus configuration is stored in a Kubernetes ConfigMap and includes:

- **Scrape Configurations**: Rules for collecting metrics from master, worker, and leecher nodes
- **Relabeling Rules**: Adds metadata labels to metrics for better filtering
- **Kubernetes Service Discovery**: Automatically finds IPFS nodes based on their labels
- **Evaluation Rules**: Optional alerting and recording rules

Example scrape configuration:
```yaml
scrape_configs:
  # IPFS master node metrics
  - job_name: 'ipfs-master'
    kubernetes_sd_configs:
      - role: endpoints
        namespaces:
          names:
            - ipfs-kit
    relabel_configs:
      - source_labels: [__meta_kubernetes_service_label_app]
        regex: ipfs-master
        action: keep
      - source_labels: [__meta_kubernetes_endpoint_port_name]
        regex: metrics
        action: keep
      - source_labels: [__meta_kubernetes_pod_node_name]
        target_label: node
      - source_labels: [__meta_kubernetes_pod_name]
        target_label: pod
    metrics_path: /metrics

  # IPFS worker nodes metrics
  - job_name: 'ipfs-worker'
    kubernetes_sd_configs:
      - role: endpoints
        namespaces:
          names:
            - ipfs-kit
    relabel_configs:
      - source_labels: [__meta_kubernetes_service_label_app]
        regex: ipfs-worker
        action: keep
```

## Grafana Dashboards

IPFS Kit includes pre-configured Grafana dashboards:

### 1. System Dashboard

Provides a high-level overview of system performance metrics:

- **CPU, Memory, and Disk Usage**: Real-time and historical usage graphs
- **Network Bandwidth**: Inbound and outbound traffic rates
- **Cache Performance**: Hit ratios and sizes for memory and disk tiers
- **Per-Node Metrics**: Performance breakdown by node role (master, worker, leecher)

### 2. Operations Dashboard

Focuses on IPFS operation metrics for detailed analysis:

- **Operation Rates**: Breakdown of operations by type (add, get, pin, etc.)
- **Operation Latency**: Percentile-based latency metrics (p50, p90, p99)
- **Error Rates**: Overall and per-operation error rates
- **Cache Hit/Miss**: Detailed cache access patterns
- **Content Statistics**: Pin counts, total content size, and replication metrics

## Deployment

### Kubernetes Deployment

To deploy the observability stack in Kubernetes:

```bash
# Apply namespace
kubectl apply -f kubernetes/namespace.yaml

# Deploy Prometheus
kubectl apply -f kubernetes/prometheus-configmap.yaml
kubectl apply -f kubernetes/prometheus-deployment.yaml

# Deploy Grafana
kubectl apply -f kubernetes/grafana-dashboard-configmap.yaml
kubectl apply -f kubernetes/grafana-deployment.yaml

# Access Grafana (default password: ipfskitadmin)
kubectl port-forward -n ipfs-kit svc/grafana 3000:3000
```

### Docker Compose Deployment

For local development or single-node setups, you can use Docker Compose:

```yaml
# docker-compose.yml
version: '3.7'
services:
  prometheus:
    image: prom/prometheus:v2.30.3
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"
    networks:
      - ipfs-network

  grafana:
    image: grafana/grafana:7.5.7
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=ipfskitadmin
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning
    ports:
      - "3000:3000"
    networks:
      - ipfs-network
    depends_on:
      - prometheus

networks:
  ipfs-network:
    external: true
```

## Custom Metrics

### Adding Application-Specific Metrics

You can extend the metrics collection with custom metrics specific to your application by using the PrometheusExporter helper functions:

```python
from ipfs_kit_py import ipfs_kit
from ipfs_kit_py.prometheus_exporter import PrometheusExporter

# Initialize IPFS Kit
kit = ipfs_kit()
metrics = kit.performance_metrics

# Create a PrometheusExporter with your metrics
exporter = PrometheusExporter(
    metrics,
    prefix="ipfs_app",  # Custom prefix for your application
    labels={"app": "my_ipfs_app", "environment": "production"}
)

# Create custom metrics directly
content_size_gauge = exporter.registry.gauge(
    "content_size_bytes_total",
    "Total size of all content stored",
    labelnames=["content_type"]
)

request_counter = exporter.registry.counter(
    "client_requests_total",
    "Total number of client requests",
    labelnames=["endpoint", "method"]
)

processing_time = exporter.registry.histogram(
    "processing_time_seconds",
    "Time taken to process requests",
    labelnames=["operation_type"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0)
)

# Use the metrics in your application
def track_content_addition(content_type, size):
    content_size_gauge.labels(content_type=content_type).inc(size)

def track_request(endpoint, method):
    request_counter.labels(endpoint=endpoint, method=method).inc()

def track_processing(operation_type, duration):
    processing_time.labels(operation_type=operation_type).observe(duration)

# Example usage
track_content_addition("image", 1024 * 1024)  # 1MB image
track_request("/api/v0/add", "POST")
track_processing("image_resize", 2.3)  # 2.3 seconds to process
```

### Creating Metrics for Specific IPFS Use Cases

Here are examples of custom metrics for common IPFS use cases:

#### Content Type Tracking

```python
# Initialize metrics
content_by_type = exporter.registry.gauge(
    "content_by_type_bytes", 
    "Content size by type in bytes",
    labelnames=["content_type"]
)

content_count_by_type = exporter.registry.gauge(
    "content_count_by_type", 
    "Number of items by content type",
    labelnames=["content_type"]
)

# Update metrics when adding content
def on_content_add(cid, size, mime_type):
    # Map MIME type to general category
    content_type = mime_type.split('/')[0]  # e.g., 'image/jpeg' -> 'image'
    
    # Update metrics
    content_by_type.labels(content_type=content_type).inc(size)
    content_count_by_type.labels(content_type=content_type).inc()
    
    # Return CID to caller
    return cid
```

#### Peer Connection Monitoring

```python
# Initialize metrics
connected_peers = exporter.registry.gauge(
    "connected_peers",
    "Number of connected peers"
)

peer_connection_quality = exporter.registry.gauge(
    "peer_connection_quality",
    "Connection quality score with peers (0-100)",
    labelnames=["peer_id"]
)

peer_latency = exporter.registry.histogram(
    "peer_latency_seconds",
    "Latency between peers in seconds",
    labelnames=["peer_id"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0)
)

# Update metrics periodically
def update_peer_metrics():
    # Get current peer connections
    peers = kit.get_peers()
    
    # Update total count
    connected_peers.set(len(peers))
    
    # Update per-peer metrics
    for peer in peers:
        # Ping peer to get latency
        ping_result = kit.ping_peer(peer["id"])
        
        if ping_result["success"]:
            latency = ping_result["latency"]
            peer_latency.labels(peer_id=peer["id"]).observe(latency)
            
            # Calculate quality score based on latency and other factors
            quality_score = max(0, min(100, 100 - (latency * 50)))
            peer_connection_quality.labels(peer_id=peer["id"]).set(quality_score)
```

#### IPFS Service Health Metrics

```python
# Initialize metrics
service_health = exporter.registry.gauge(
    "service_health",
    "Overall health of IPFS service (0-100)"
)

service_up = exporter.registry.gauge(
    "service_up",
    "Whether the service is up (1) or down (0)",
    labelnames=["component"]
)

# Update metrics in health check function
def check_health():
    components = {
        "ipfs_daemon": kit.is_daemon_running(),
        "api_server": kit.is_api_available(),
        "gateway": kit.is_gateway_available(),
        "cluster": kit.is_cluster_available()
    }
    
    # Update individual component status
    for component, is_up in components.items():
        service_up.labels(component=component).set(1 if is_up else 0)
    
    # Calculate overall health score (percentage of components up)
    up_count = sum(1 for status in components.values() if status)
    health_score = (up_count / len(components)) * 100
    service_health.set(health_score)
    
    return health_score > 50  # Return True if health score above 50%
```

## Advanced Usage

### High-Cardinality Metrics

With IPFS Kit's distributed architecture, be careful with high-cardinality metrics as they can cause performance issues in Prometheus. Some strategies specifically for IPFS Kit:

- **CID-based metrics**: Instead of adding a label for each CID (which would create millions of time series), track counts by size ranges or content types
- **Peer-specific metrics**: Limit tracking to a small set of important peers or aggregate by network/region
- **Path metrics**: Track by directory depth or top-level directories instead of individual paths

Example for managing CID cardinality:

```python
# Instead of this (very high cardinality)
# content_size = exporter.registry.gauge(
#     "content_size_bytes", 
#     "Content size in bytes",
#     labelnames=["cid"]  # Potentially millions of values!
# )

# Do this instead (controlled cardinality)
content_size_by_range = exporter.registry.gauge(
    "content_size_bytes", 
    "Content size in bytes",
    labelnames=["size_range"]  # Limited set of values
)

# Size ranges
SIZE_RANGES = {
    "tiny": (0, 1024),                # 0-1KB
    "small": (1024, 1024*10),         # 1KB-10KB
    "medium": (1024*10, 1024*100),    # 10KB-100KB
    "large": (1024*100, 1024*1024),   # 100KB-1MB
    "huge": (1024*1024, float('inf')) # >1MB
}

def categorize_size(size_bytes):
    """Categorize a size into a range."""
    for range_name, (min_size, max_size) in SIZE_RANGES.items():
        if min_size <= size_bytes < max_size:
            return range_name
    return "unknown"

# Update metrics when adding content
def track_content_size(size_bytes):
    size_range = categorize_size(size_bytes)
    content_size_by_range.labels(size_range=size_range).inc(size_bytes)
```

### Aggregation Guidelines for IPFS Kit

For optimal performance, follow these aggregation guidelines specific to IPFS Kit:

1. **Tier-based Metrics**: Instead of individual cache metrics, use the built-in tier aggregation
   ```
   sum(rate(ipfs_cache_tier_hits_total{tier="memory"}[5m])) / 
   sum(rate(ipfs_cache_tier_hits_total{tier="memory"}[5m]) + rate(ipfs_cache_tier_misses_total{tier="memory"}[5m]))
   ```

2. **Operation Categories**: Group operations by category for higher-level insights
   ```
   # Recording rule example
   - record: ipfs_operations:by_category:rate5m
     expr: sum by (category) (
       label_replace(
         rate(ipfs_operations_total[5m]), 
         "category", 
         "content", 
         "operation", 
         "(add|cat|get)"
       )
     )
   ```

3. **Role-based Aggregation**: Aggregate metrics by node role for cluster-wide views
   ```
   # Average CPU usage by role
   avg by (role) (ipfs_cpu_usage_percent)
   ```

### Alerting Rules for IPFS Kit

Here are recommended alerting rules specific to IPFS Kit's architecture and common failure modes:

```yaml
groups:
- name: ipfs-kit-alerts
  rules:
  # System resource alerts
  - alert: IPFSHighMemoryUsage
    expr: ipfs_memory_usage_percent > 85
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High memory usage on {{$labels.instance}}"
      description: "IPFS node memory usage is {{ $value }}%, which is above the 85% threshold for 5 minutes"

  - alert: IPFSDiskSpaceLow
    expr: ipfs_disk_free_bytes / 1024 / 1024 / 1024 < 5
    for: 10m
    labels:
      severity: warning
    annotations:
      summary: "Low disk space on {{$labels.instance}}"
      description: "IPFS node has less than 5GB of free disk space"

  # Operational alerts
  - alert: IPFSHighErrorRate
    expr: sum(rate(ipfs_errors_total[5m])) / sum(rate(ipfs_operations_total[5m])) > 0.05
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High error rate on {{$labels.instance}}"
      description: "IPFS Kit error rate is {{ $value | humanizePercentage }} for the last 5 minutes"

  - alert: IPFSCacheHitRatioLow
    expr: ipfs_cache_hit_ratio < 0.5
    for: 15m
    labels:
      severity: warning
    annotations:
      summary: "Low cache hit ratio on {{$labels.instance}}"
      description: "Cache hit ratio is {{ $value | humanizePercentage }}, below 50% for the last 15 minutes"

  # Master-specific alerts
  - alert: IPFSMasterOffline
    expr: up{job="ipfs-master"} == 0
    for: 2m
    labels:
      severity: critical
    annotations:
      summary: "IPFS Master node offline"
      description: "IPFS master node {{$labels.instance}} is down for more than 2 minutes"

  # Worker-specific alerts
  - alert: IPFSWorkerHighLatency
    expr: histogram_quantile(0.95, sum(rate(ipfs_operation_latency_seconds_bucket{job="ipfs-worker"}[5m])) by (le, instance)) > 2
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High operation latency on worker {{$labels.instance}}"
      description: "95th percentile operation latency is above 2 seconds on worker {{$labels.instance}}"

  # Network-related alerts
  - alert: IPFSSlowBandwidth
    expr: rate(ipfs_bandwidth_inbound_bytes_total[5m]) + rate(ipfs_bandwidth_outbound_bytes_total[5m]) < 100 * 1024
    for: 10m
    labels:
      severity: warning
    annotations:
      summary: "Slow network throughput on {{$labels.instance}}"
      description: "Combined bandwidth is below 100KB/s for 10 minutes, indicating potential network issues"
```

### Recording Rules for IPFS Kit

To improve query performance and create derived metrics, add these recording rules to your Prometheus configuration:

```yaml
groups:
- name: ipfs-kit-recording-rules
  interval: 1m
  rules:
  # Operational metrics
  - record: ipfs:operations:rate1m
    expr: sum(rate(ipfs_operations_total[1m])) by (operation)
    
  - record: ipfs:operations:errors:ratio
    expr: sum(rate(ipfs_errors_total[5m])) / sum(rate(ipfs_operations_total[5m]))
  
  # Cache performance
  - record: ipfs:cache:hit_ratio:by_tier
    expr: sum by (tier) (rate(ipfs_cache_tier_hits_total[5m])) / sum by (tier) (rate(ipfs_cache_tier_hits_total[5m]) + rate(ipfs_cache_tier_misses_total[5m]))
  
  # Latency metrics
  - record: ipfs:latency:p95:by_operation
    expr: histogram_quantile(0.95, sum(rate(ipfs_operation_latency_seconds_bucket[5m])) by (le, operation))
  
  # System resources by role
  - record: ipfs:resources:by_role
    expr: avg by (role) (ipfs_cpu_usage_percent)
  
  # Node health score
  - record: ipfs:node:health_score
    expr: (1 - ipfs:operations:errors:ratio) * 0.4 + ipfs:cache:hit_ratio:total * 0.3 + (1 - min(ipfs_cpu_usage_percent / 100, 1)) * 0.15 + (1 - min(ipfs_memory_usage_percent / 100, 1)) * 0.15
```

These recording rules provide:
1. Pre-calculated rates for common queries
2. Derived metrics like health scores
3. Percentile calculations for latency
4. Role-based aggregation for cluster overview

## References

### External Documentation
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/naming/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Kubernetes Monitoring Best Practices](https://kubernetes.io/docs/tasks/debug-application-cluster/resource-usage-monitoring/)

### IPFS Kit References
- [Performance Metrics Module](/ipfs_kit_py/performance_metrics.py): Core metrics collection for IPFS Kit
- [Prometheus Exporter Module](/ipfs_kit_py/prometheus_exporter.py): Metrics conversion to Prometheus format
- [API Integration](/ipfs_kit_py/api.py): FastAPI integration for the Prometheus metrics endpoint

### Example Dashboards
- [System Dashboard](/kubernetes/grafana-dashboard-configmap.yaml): Pre-configured system metrics dashboard
- [Operations Dashboard](/kubernetes/grafana-dashboard-configmap.yaml): Pre-configured operations metrics dashboard

### Deployment Examples
- [Prometheus Deployment](/kubernetes/prometheus-deployment.yaml): Kubernetes deployment for Prometheus
- [Grafana Deployment](/kubernetes/grafana-deployment.yaml): Kubernetes deployment for Grafana