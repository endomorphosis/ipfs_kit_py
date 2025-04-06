# WAL Telemetry High-Level API Integration

This document explains how to use the WAL telemetry integration with the IPFS Kit high-level API, providing a comprehensive solution for monitoring, metrics collection, and distributed tracing.

## Overview

The WAL telemetry API integration provides:

1. **Unified Interface**: Simple high-level API methods for telemetry, metrics, and tracing
2. **Prometheus Integration**: Export metrics in Prometheus format for monitoring tools
3. **Distributed Tracing**: End-to-end tracing for operations across components
4. **FastAPI Integration**: Easy metrics endpoint and trace middleware for FastAPI
5. **Comprehensive Metrics**: Latency, throughput, success rates, and error tracking

## Installation

The WAL telemetry API integration is included with IPFS Kit. For full functionality, install the optional dependencies:

```bash
# Core functionality
pip install ipfs_kit_py

# For Prometheus monitoring
pip install prometheus_client

# For distributed tracing
pip install opentelemetry-api opentelemetry-sdk
pip install opentelemetry-exporter-otlp  # Optional: OTLP exporter
pip install opentelemetry-exporter-jaeger  # Optional: Jaeger exporter
pip install opentelemetry-exporter-zipkin  # Optional: Zipkin exporter

# For API server
pip install fastapi uvicorn
```

## Basic Usage

### Initializing the WAL Telemetry System

```python
from ipfs_kit_py.high_level_api import IPFSSimpleAPI
from ipfs_kit_py.wal_telemetry_api import extend_high_level_api

# Create high-level API instance
api = IPFSSimpleAPI(role="master")

# Extend with WAL telemetry capabilities
api = extend_high_level_api(api)

# Initialize WAL telemetry
result = api.wal_telemetry(
    enabled=True,
    aggregation_interval=60,  # Aggregate metrics every 60 seconds
    max_history_entries=100   # Keep 100 historical entries
)
print(f"Telemetry initialization: {result['success']}")
```

### Adding Prometheus Integration

```python
# Initialize Prometheus integration
prometheus_result = api.wal_prometheus(
    enabled=True,
    prefix="wal",           # Prefix for metric names
    start_server=False      # Don't start a standalone server
)
print(f"Prometheus initialization: {prometheus_result['success']}")

# If you want a standalone metrics server:
prometheus_result = api.wal_prometheus(
    enabled=True,
    port=9090,            # Port for the metrics server
    start_server=True     # Start a standalone server
)
print(f"Prometheus server running at: {prometheus_result['server']['url']}")
```

### Setting Up Distributed Tracing

```python
from ipfs_kit_py.wal_telemetry_tracing import TracingExporterType

# Initialize tracing
tracing_result = api.wal_tracing(
    enabled=True,
    service_name="my-ipfs-service",
    exporter_type=TracingExporterType.CONSOLE,  # Options: CONSOLE, OTLP, JAEGER, ZIPKIN
    sampling_ratio=1.0,                         # Sample all traces
    auto_instrument=True                        # Automatically instrument operations
)
print(f"Tracing initialization: {tracing_result['success']}")

# With Jaeger exporter
tracing_result = api.wal_tracing(
    enabled=True,
    service_name="my-ipfs-service",
    exporter_type=TracingExporterType.JAEGER,
    exporter_endpoint="http://localhost:14268/api/traces",
    resource_attributes={
        "deployment.environment": "production",
        "service.version": "1.0.0"
    }
)
```

### Creating and Managing Traces

```python
# Create a span for an operation
span_result = api.wal_create_span(
    operation_type="add",
    backend="ipfs",
    attributes={
        "file_size": 1024,
        "path": "/tmp/example.txt"
    }
)

# Get the span context
if span_result["success"]:
    context = span_result["span_context"]
    
    # Use the span context to create child spans...
    
    # Update the span with results
    api._wal_telemetry_extension.tracer.update_span(
        context, 
        success=True,
        attributes={
            "duration_ms": 150,
            "cid": "QmExample..."
        }
    )
    
    # End the span
    api._wal_telemetry_extension.tracer.end_span(context)
```

### Accessing Telemetry Metrics

```python
# Get all metrics
metrics = api.wal_get_metrics()

# Get metrics with filtering
metrics = api.wal_get_metrics(
    include_history=True,        # Include historical metrics
    operation_type="add",        # Filter by operation type
    backend_type="ipfs",         # Filter by backend type
    start_time=time.time()-3600, # Last hour
    end_time=time.time()
)

# Display metrics
if metrics["success"]:
    print("Real-time metrics:")
    for category, metrics_data in metrics["real_time_metrics"].items():
        print(f"  {category}:")
        for key, value in metrics_data.items():
            print(f"    {key}: {value}")
```

## FastAPI Integration

### Adding a Metrics Endpoint

```python
from fastapi import FastAPI

# Create FastAPI app
app = FastAPI()

# Add metrics endpoint
api.wal_add_metrics_endpoint(
    app=app,
    endpoint="/metrics"  # Prometheus scrape endpoint
)
```

### Adding Tracing Middleware

```python
from fastapi import FastAPI, Request

# Create FastAPI app
app = FastAPI()

# Add tracing middleware
@app.middleware("http")
async def tracing_middleware(request: Request, call_next):
    # Extract context from request headers if available
    carrier = dict(request.headers)
    context_result = api.wal_extract_tracing_context(carrier)
    
    if context_result["success"]:
        parent_context = context_result["context"]
    else:
        parent_context = None
        
    # Create span for this request
    span_result = api.wal_create_span(
        operation_type="http_request",
        backend="api",
        parent_context=parent_context,
        attributes={
            "http.method": request.method,
            "http.url": str(request.url),
            "http.path": request.url.path
        }
    )
    
    # Process the request
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    
    # Update span with response information
    if span_result["success"]:
        context = span_result["span_context"]
        
        api._wal_telemetry_extension.tracer.update_span(
            context,
            success=response.status_code < 400,
            attributes={
                "http.status_code": response.status_code,
                "http.duration_ms": duration * 1000
            }
        )
        
        # End span
        api._wal_telemetry_extension.tracer.end_span(context)
        
    return response
```

## Distributed Tracing Across Services

### Context Propagation

```python
# Service A: Create a span and inject context into headers
span_result = api.wal_create_span(
    operation_type="process_file",
    backend="api"
)

# Inject context into headers for HTTP request
headers = {}
if span_result["success"]:
    context = span_result["span_context"]
    inject_result = api.wal_inject_tracing_context(headers, context)
    
# Make HTTP request to Service B with propagated context
response = requests.get("http://service-b/endpoint", headers=headers)

# Complete the span
if span_result["success"]:
    api._wal_telemetry_extension.tracer.end_span(span_result["span_context"])

# Service B: Extract context from request headers
@app.middleware("http")
async def tracing_middleware(request: Request, call_next):
    # Extract the propagated context
    carrier = dict(request.headers)
    context_result = api.wal_extract_tracing_context(carrier)
    
    if context_result["success"]:
        parent_context = context_result["context"]
    else:
        parent_context = None
        
    # Create a child span with the parent context
    span_result = api.wal_create_span(
        operation_type="handle_request",
        backend="service-b",
        parent_context=parent_context
    )
    
    # Process the request
    response = await call_next(request)
    
    # End the span
    if span_result["success"]:
        api._wal_telemetry_extension.tracer.end_span(span_result["span_context"])
        
    return response
```

## Complete Example

See the complete example in `examples/wal_telemetry_api_example.py`.

The example demonstrates:
1. Initializing the high-level API with WAL telemetry
2. Setting up Prometheus metrics and distributed tracing
3. Creating a FastAPI server with metrics endpoint and tracing middleware
4. Simulating operations to generate telemetry data
5. Accessing and displaying metrics

### Running the Example

```bash
# Run in non-server mode (just simulate operations and show metrics)
python examples/wal_telemetry_api_example.py

# Run in server mode (start a FastAPI server with endpoints)
python examples/wal_telemetry_api_example.py --server

# Specify number of operations and delay
python examples/wal_telemetry_api_example.py --operations 50 --delay 0.1
```

## API Reference

### WAL Telemetry Initialization

```python
api.wal_telemetry(
    enabled=True,                  # Whether telemetry is enabled
    aggregation_interval=60,       # Interval for metric aggregation (seconds)
    max_history_entries=100,       # Maximum historical entries to keep
    log_level="INFO"               # Logging level
)
```

### Prometheus Integration

```python
api.wal_prometheus(
    enabled=True,                  # Whether Prometheus integration is enabled
    port=8000,                     # Port for standalone metrics server
    endpoint="/metrics",           # Path for metrics endpoint
    prefix="wal",                  # Prefix for metric names
    start_server=False,            # Whether to start a standalone server
    registry_name=None             # Custom name for the Prometheus registry
)
```

### Distributed Tracing

```python
api.wal_tracing(
    enabled=True,                  # Whether tracing is enabled
    service_name="ipfs-kit-wal",   # Name of the service
    exporter_type="console",       # Exporter type: "console", "otlp", "jaeger", "zipkin"
    exporter_endpoint=None,        # Endpoint for the exporter
    resource_attributes=None,      # Additional attributes for the tracing resource
    sampling_ratio=1.0,            # Fraction of traces to sample (0.0-1.0)
    auto_instrument=True           # Whether to automatically instrument operations
)
```

### Metrics Retrieval

```python
api.wal_get_metrics(
    include_history=False,        # Whether to include historical metrics
    operation_type=None,          # Filter by operation type
    backend_type=None,            # Filter by backend type
    start_time=None,              # Start time for historical metrics
    end_time=None                 # End time for historical metrics
)
```

### FastAPI Integration

```python
api.wal_add_metrics_endpoint(
    app,                          # FastAPI application
    endpoint="/metrics"           # Path for the metrics endpoint
)
```

### Trace Management

```python
api.wal_create_span(
    operation_type,               # Type of operation being traced
    operation_id=None,            # Unique identifier for the operation
    backend="api",                # Backend system processing the operation
    parent_context=None,          # Parent context for distributed tracing
    attributes=None               # Additional span attributes
)

api.wal_get_tracing_context()     # Get current tracing context

api.wal_inject_tracing_context(
    carrier,                      # Dictionary to inject context into
    context=None                  # Context to inject (uses current if None)
)

api.wal_extract_tracing_context(
    carrier                       # Dictionary containing tracing context
)
```

## Best Practices

1. **Initialize Early**: Set up WAL telemetry at application startup to capture all operations
2. **Use Descriptive Names**: Choose clear operation types and backend names for better metrics
3. **Add Useful Attributes**: Include attributes like file sizes, CIDs, and operation parameters
4. **Context Propagation**: Always propagate trace context between services for end-to-end visibility
5. **Monitor Error Rates**: Set up alerts on error rates to detect issues early
6. **Adjust Sampling**: Use lower sampling rates in high-volume production environments
7. **Correlate with Logs**: Include trace IDs in logs for better debugging
8. **Dashboard Integration**: Set up Grafana dashboards with Prometheus metrics for visibility
9. **Regular Analysis**: Review metrics and traces regularly to identify optimization opportunities

## Troubleshooting

### Common Issues

1. **Missing Metrics**: Ensure telemetry is enabled and operations are running with the correct operation types
2. **Tracing Not Working**: Check that the tracing exporter is correctly configured and endpoint is accessible
3. **Context Propagation Issues**: Verify that headers are correctly injected and extracted
4. **High Memory Usage**: Adjust history settings to keep fewer historical entries
5. **Missing Dependencies**: Install optional dependencies for full functionality

### Debugging

Enable detailed logging to diagnose issues:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("ipfs_kit_py.wal_telemetry_api").setLevel(logging.DEBUG)
logging.getLogger("ipfs_kit_py.wal_telemetry_tracing").setLevel(logging.DEBUG)
```

## Performance Considerations

1. **Sampling**: Use sampling for high-volume production environments
2. **Metric Aggregation**: Adjust aggregation interval based on load
3. **Context Size**: Keep trace context small to minimize overhead
4. **Dependency Impact**: Consider the impact of exporters on system resources
5. **Standalone Servers**: For high-volume systems, use standalone metrics servers

## Further Reading

- [WAL Telemetry Documentation](wal_telemetry.md)
- [WAL Telemetry Prometheus Integration](wal_telemetry_prometheus.md) 
- [WAL Telemetry Distributed Tracing](wal_telemetry_tracing.md)
- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)
- [Prometheus Documentation](https://prometheus.io/docs/)