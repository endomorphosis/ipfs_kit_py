# WAL Telemetry Distributed Tracing

This document explains how to use the distributed tracing capabilities of the WAL telemetry system.

## Overview

Distributed tracing provides a way to track operations across multiple services and components in a distributed system. It helps identify performance bottlenecks, understand system behavior, and troubleshoot issues by providing a view of the complete request flow.

The WAL telemetry distributed tracing system provides:

1. **OpenTelemetry Integration**: Standards-compliant tracing using the OpenTelemetry protocol
2. **Context Propagation**: Pass trace context between components for end-to-end visibility
3. **Automatic Instrumentation**: Hook into WAL operations for automatic tracing
4. **Multiple Backends**: Export traces to Jaeger, Zipkin, OTLP collector, or console
5. **Correlation with Metrics**: Link traces to telemetry metrics for comprehensive monitoring
6. **Minimal Dependencies**: Fallback to basic tracing when OpenTelemetry is not available

## Getting Started

### Installation

The tracing module is part of the `ipfs_kit_py` package. Make sure you have the package installed:

```bash
pip install ipfs_kit_py
```

For full functionality, you should also install OpenTelemetry:

```bash
pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp
```

For specific backends, install the appropriate exporters:

```bash
# For Jaeger
pip install opentelemetry-exporter-jaeger

# For Zipkin
pip install opentelemetry-exporter-zipkin
```

### Basic Usage

Here's a simple example of using distributed tracing with the WAL telemetry system:

```python
from ipfs_kit_py.storage_wal import StorageWriteAheadLog, BackendHealthMonitor
from ipfs_kit_py.wal_telemetry import WALTelemetry
from ipfs_kit_py.wal_telemetry_tracing import WALTracing, TracingExporterType

# Create WAL components
health_monitor = BackendHealthMonitor(check_interval=5, history_size=10)
wal = StorageWriteAheadLog(base_path="~/.ipfs_kit/wal", health_monitor=health_monitor)

# Create telemetry
telemetry = WALTelemetry(
    wal=wal,
    metrics_path="~/.ipfs_kit/telemetry",
    sampling_interval=10,
    enable_detailed_timing=True,
    operation_hooks=True
)

# Create tracer with console exporter
tracer = WALTracing(
    service_name="my-service",
    telemetry=telemetry,
    exporter_type=TracingExporterType.CONSOLE,
    auto_instrument=True
)

# Now operations will be automatically traced
operation = wal.add_operation(
    operation_type="add", 
    backend="ipfs",
    parameters={"path": "/tmp/example.txt"}
)

# Cleanup when done
tracer.close()
telemetry.close()
wal.close()
health_monitor.close()
```

## Key Components

### WALTracing

The main class for distributed tracing is `WALTracing`. It provides the following functionality:

- Initialize tracing with various configurations
- Start and manage spans
- Propagate trace context between services
- Export traces to various backends
- Correlate traces with telemetry metrics

#### Constructor Parameters

```python
WALTracing(
    service_name: str = "ipfs-kit-wal",
    telemetry: Optional[WALTelemetry] = None,
    exporter_type: Union[str, TracingExporterType] = TracingExporterType.CONSOLE,
    exporter_endpoint: Optional[str] = None,
    resource_attributes: Optional[Dict[str, str]] = None,
    sampling_ratio: float = 1.0,
    auto_instrument: bool = True
)
```

- `service_name`: Name of the service for identification in traces
- `telemetry`: Optional WALTelemetry instance for metric correlation
- `exporter_type`: Type of tracing exporter (console, jaeger, zipkin, otlp)
- `exporter_endpoint`: Endpoint URL for the tracing backend
- `resource_attributes`: Additional resource attributes for traces
- `sampling_ratio`: Sampling ratio for traces (0.0-1.0)
- `auto_instrument`: Whether to automatically instrument WAL operations

### Tracing Spans

Spans represent a unit of work in a trace. You can create and manage spans in several ways:

#### Manual Span Creation

```python
# Create a span directly
with tracer.start_span(
    name="my-operation",
    attributes={"operation.type": "add", "backend": "ipfs"}
) as span:
    # Do some work
    span.set_attribute("custom.attribute", "value")
    
    # Record an event
    span.add_event(
        name="processing.step",
        attributes={"step": "validation"}
    )
```

#### Context Manager for WAL Operations

```python
# Create a span specifically for WAL operations
with tracer.create_span_context(
    operation_type="add",
    backend="ipfs",
    operation_id="op-123",
    attributes={"custom.attribute": "value"}
) as span:
    # Do some work with WAL
    result = do_something()
    
    # If there's an error, the span will automatically record it
    # and set the status to ERROR when exiting the context
```

#### Function Decorator

```python
# Trace a function automatically
@tracer.trace_function(
    name="my-function",
    operation_type="processing",
    backend="memory",
    attributes={"custom": "value"}
)
def process_data(data):
    # Function will be automatically traced
    return transformed_data
```

### Context Propagation

To trace operations across service boundaries, you need to propagate the trace context:

#### HTTP Server Integration

For FastAPI applications:

```python
from ipfs_kit_py.wal_telemetry_tracing import add_tracing_middleware

app = FastAPI()
add_tracing_middleware(app, tracer, "my-api-service")

@app.get("/api/data")
async def get_data(request: Request):
    # Extract trace context from request headers
    trace_context = tracer.extract_context(dict(request.headers))
    
    # Create span with extracted context
    with tracer.start_span(
        name="get-data",
        context=trace_context,
        attributes={"endpoint": "/api/data"}
    ) as span:
        # Process request
        result = process_data()
        return {"data": result, "trace_id": tracer.get_trace_id()}
```

#### HTTP Client Integration

For making requests to other services:

```python
async def call_service(url):
    # Create headers with trace context
    headers = {}
    tracer.inject_context(None, headers)  # Inject current context
    
    # Make HTTP request with trace context
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            return await response.json()
```

For a more complete approach with aiohttp:

```python
from ipfs_kit_py.wal_telemetry_tracing import trace_aiohttp_request

async def call_service(url):
    async with aiohttp.ClientSession() as session:
        # Get trace context and create span
        carrier, span = trace_aiohttp_request(tracer, "GET", url)
        
        try:
            # Make request with trace context
            async with session.get(url, headers=carrier) as response:
                data = await response.json()
                
                # Record response info
                span.set_attribute("http.status_code", response.status)
                
                # Set status based on response
                if response.status >= 400:
                    span.set_status(StatusCode.ERROR)
                    
                return data
        finally:
            # End span
            span.end()
```

## Exporters

The tracing system supports multiple exporters for sending traces to different backends:

### Console Exporter

Prints traces to the console. Useful for development and debugging:

```python
tracer = WALTracing(
    service_name="my-service",
    exporter_type=TracingExporterType.CONSOLE
)
```

### Jaeger Exporter

Sends traces to a Jaeger backend for visualization and analysis:

```python
tracer = WALTracing(
    service_name="my-service",
    exporter_type=TracingExporterType.JAEGER,
    exporter_endpoint="http://localhost:14268/api/traces"
)
```

### Zipkin Exporter

Sends traces to a Zipkin backend:

```python
tracer = WALTracing(
    service_name="my-service",
    exporter_type=TracingExporterType.ZIPKIN,
    exporter_endpoint="http://localhost:9411/api/v2/spans"
)
```

### OTLP Exporter

Sends traces to an OpenTelemetry collector:

```python
tracer = WALTracing(
    service_name="my-service",
    exporter_type=TracingExporterType.OTLP,
    exporter_endpoint="http://localhost:4317"
)
```

## Automatic Instrumentation

When you create a `WALTracing` instance with `auto_instrument=True` and provide a `WALTelemetry` instance, the tracer will automatically hook into WAL operations to create traces. This includes:

1. Tracing `add_operation` calls to track when operations are created
2. Tracing `update_operation_status` calls to track status changes
3. Recording operation timing information
4. Tracking backend health status changes

## APIs and Helper Functions

The tracing module provides several helper functions and utilities:

### FastAPI Integration

```python
from ipfs_kit_py.wal_telemetry_tracing import add_tracing_middleware

# Add tracing middleware to FastAPI app
add_tracing_middleware(app, tracer, service_name="my-api")
```

### HTTP Client Tracing

```python
from ipfs_kit_py.wal_telemetry_tracing import trace_aiohttp_request

# Trace an aiohttp request
carrier, span = trace_aiohttp_request(tracer, "GET", "http://example.com/api")
```

### Correlation IDs

To correlate traces with logs and metrics:

```python
# Get correlation ID based on current trace
correlation_id = tracer.correlation_id()

# Use in logs
logger.info(f"Processing operation [correlation_id={correlation_id}]")
```

### Adding Events

```python
# Add an event to the current span
tracer.add_event(
    name="operation.milestone",
    attributes={"milestone": "validation", "duration_ms": 45}
)
```

## Advanced Usage

### Custom Span Attributes

You can add custom attributes to spans to provide more context:

```python
with tracer.start_span("process-data") as span:
    span.set_attribute("data.size", len(data))
    span.set_attribute("data.format", "json")
    span.set_attribute("processing.mode", "batch")
```

### Recording Exceptions

Spans automatically record exceptions in context managers, but you can also record them manually:

```python
try:
    process_data()
except Exception as e:
    span.record_exception(e)
    span.set_status(StatusCode.ERROR, str(e))
    raise
```

### Resource Attributes

Resource attributes apply to all spans from a tracer and provide context about the environment:

```python
tracer = WALTracing(
    service_name="my-service",
    resource_attributes={
        "service.version": "1.2.3",
        "deployment.environment": "production",
        "host.name": "worker-pod-123",
        "cloud.provider": "aws",
        "cloud.region": "us-west-2"
    }
)
```

## Complete Example

Here's a more complete example showing how to use the tracing system in a distributed environment:

```python
import asyncio
import aiohttp
from fastapi import FastAPI, Request
from ipfs_kit_py.storage_wal import StorageWriteAheadLog, BackendHealthMonitor
from ipfs_kit_py.wal_telemetry import WALTelemetry
from ipfs_kit_py.wal_telemetry_tracing import (
    WALTracing, 
    TracingExporterType,
    add_tracing_middleware,
    trace_aiohttp_request
)

# Create WAL and telemetry
health_monitor = BackendHealthMonitor(check_interval=5, history_size=10)
wal = StorageWriteAheadLog(base_path="~/.ipfs_kit/wal", health_monitor=health_monitor)
telemetry = WALTelemetry(
    wal=wal,
    metrics_path="~/.ipfs_kit/telemetry",
    sampling_interval=10,
    enable_detailed_timing=True,
    operation_hooks=True
)

# Create tracer with Jaeger exporter
tracer = WALTracing(
    service_name="api-service",
    telemetry=telemetry,
    exporter_type=TracingExporterType.JAEGER,
    exporter_endpoint="http://jaeger:14268/api/traces",
    resource_attributes={
        "service.version": "1.0.0",
        "deployment.environment": "production"
    },
    auto_instrument=True
)

# Create FastAPI app with tracing middleware
app = FastAPI()
add_tracing_middleware(app, tracer, "api-service")

# Define API endpoints
@app.post("/api/operation")
async def add_operation(request: Request, operation_type: str, backend: str):
    # Extract trace context from request headers
    trace_context = tracer.extract_context(dict(request.headers))
    
    # Create span for this request
    with tracer.start_span(
        name="api.add_operation",
        context=trace_context,
        attributes={
            "operation.type": operation_type,
            "backend": backend
        }
    ) as span:
        # Add operation to WAL (will be automatically traced)
        result = wal.add_operation(
            operation_type=operation_type,
            backend=backend
        )
        
        # Schedule background processing
        if result.get("success"):
            asyncio.create_task(process_operation(
                result["operation_id"], 
                operation_type, 
                backend,
                tracer.generate_trace_context()  # Pass trace context to background task
            ))
            
        return {
            "success": result.get("success", False),
            "operation_id": result.get("operation_id"),
            "trace_id": tracer.get_trace_id()
        }

async def process_operation(operation_id, operation_type, backend, trace_context):
    # Extract trace context for continuation
    context = tracer.extract_context(trace_context)
    
    # Create span for processing with extracted context
    with tracer.start_span(
        name="process.operation",
        context=context,
        attributes={
            "operation.id": operation_id,
            "operation.type": operation_type,
            "backend": backend
        }
    ) as span:
        # Update operation status
        wal.update_operation_status(operation_id, "processing")
        
        # Call worker service
        worker_url = "http://worker:8080/api/process"
        
        # Create headers with trace context
        headers = {}
        tracer.inject_context(context, headers)
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    worker_url,
                    json={
                        "operation_id": operation_id,
                        "operation_type": operation_type,
                        "backend": backend
                    },
                    headers=headers
                ) as response:
                    data = await response.json()
                    
                    # Record result
                    if data.get("success"):
                        span.set_attribute("worker.response.success", True)
                        wal.update_operation_status(
                            operation_id, 
                            "completed",
                            updates={"result": data.get("message")}
                        )
                    else:
                        span.set_attribute("worker.response.success", False)
                        span.set_attribute("worker.response.error", data.get("error"))
                        span.set_status(StatusCode.ERROR)
                        wal.update_operation_status(
                            operation_id, 
                            "failed",
                            updates={
                                "error": data.get("error"),
                                "error_type": "worker_error"
                            }
                        )
            except Exception as e:
                # Record exception
                span.record_exception(e)
                span.set_status(StatusCode.ERROR)
                
                # Update operation status
                wal.update_operation_status(
                    operation_id,
                    "failed",
                    updates={
                        "error": str(e),
                        "error_type": type(e).__name__
                    }
                )
```

## Using the Example Simulation

The package includes a comprehensive example simulation that demonstrates the distributed tracing capabilities in a multi-service environment. You can find it in `examples/wal_telemetry_tracing_example.py`.

To run the simulation:

```bash
# Run with console exporter (default)
python examples/wal_telemetry_tracing_example.py

# Run with Jaeger exporter
python examples/wal_telemetry_tracing_example.py --exporter jaeger

# Run with custom duration and worker count
python examples/wal_telemetry_tracing_example.py --exporter jaeger --duration 120 --workers 5

# Run with custom ports
python examples/wal_telemetry_tracing_example.py --master-port 9000 --worker-port 9100
```

The simulation creates:
- A master service that coordinates operations
- Multiple worker services that process delegated tasks
- Simulated backend health status changes
- Realistic operation flows with error scenarios

This provides a real-world example of how to use the distributed tracing capabilities in a complex system.

## Best Practices

1. **Use Descriptive Span Names**: Name spans according to what they represent, not how they're implemented.

2. **Add Relevant Attributes**: Include attributes that will help with debugging and analysis, but avoid excessive detail.

3. **Use Context Propagation**: Always propagate trace context between services to maintain end-to-end visibility.

4. **Record Exceptions**: Make sure to record exceptions and set error status to make troubleshooting easier.

5. **Add Events for Milestones**: Use events to mark important milestones within a span.

6. **Use Resource Attributes**: Add service version, environment, and other context to help with filtering.

7. **Sample Appropriately**: Use a lower sampling ratio in high-traffic production environments.

8. **Close Resources**: Always close the tracer when shutting down to ensure all spans are exported.

## Troubleshooting

### Common Issues

1. **Missing Context Propagation**: If traces are not connected across services, ensure trace context is being properly propagated in HTTP headers.

2. **No Traces in Backend**: Check that the exporter endpoint is correct and the backend is running.

3. **Unclosed Spans**: If spans appear incomplete, ensure they are always closed, even in error cases.

4. **Missing Attributes**: If expected attributes are missing, verify they're being set on the correct span.

### Enabling Debug Logging

To see more details about tracing operations, enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("ipfs_kit_py.wal_telemetry_tracing").setLevel(logging.DEBUG)
```

### Verifying Trace Context

To verify trace context is being properly propagated:

```python
# Print trace context headers
trace_context = {}
tracer.inject_context(None, trace_context)
print(f"Trace context: {trace_context}")

# Verify trace ID is accessible
trace_id = tracer.get_trace_id()
print(f"Trace ID: {trace_id}")
```

## Conclusion

The WAL telemetry distributed tracing system provides a powerful way to monitor and analyze operations across a distributed system. By using OpenTelemetry standards and supporting multiple backend exporters, it offers flexibility and compatibility with the broader monitoring ecosystem.

By combining distributed tracing with the existing WAL telemetry metrics, you can gain comprehensive visibility into your system's performance and behavior, making it easier to identify and resolve issues.