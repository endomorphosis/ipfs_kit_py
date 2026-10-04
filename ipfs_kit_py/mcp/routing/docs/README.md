# Optimized Data Routing System

## Overview

The Optimized Data Routing system provides intelligent routing of storage operations across different backends based on multiple criteria, such as content type, cost, geographic location, and performance metrics. It helps you make informed decisions about where to store and retrieve data to optimize for cost, performance, compliance, and other requirements.

## Key Features

- **Content-Aware Routing**: Routes data based on content type (images, videos, documents, etc.)
- **Cost Optimization**: Selects backends based on storage, retrieval, and operation costs
- **Geographic Intelligence**: Routes based on user location and data residency requirements
- **Performance-Based Routing**: Uses real-time metrics like latency and throughput to optimize performance
- **Composite Decision-Making**: Combines multiple factors with configurable weights for balanced decisions
- **Metrics Collection**: Tracks and analyzes performance and cost metrics over time
- **Extensible Architecture**: Easy to add new backends, metrics collectors, and routing strategies

## Architecture

The routing system consists of several components:

1. **Core Router**: Orchestrates backend selection using various strategies
2. **Routing Strategies**: Specialized algorithms for different routing criteria
3. **Metrics Collectors**: Gather data to inform routing decisions
4. **MCP Integration**: Connects the routing system with the MCP server

### Core Router Components

- `DataRouter`: Main router class that selects backends
- `RoutingContext`: Contains context for a routing decision
- `RoutingDecision`: Represents the outcome of a routing decision
- `RoutingStrategy`: Abstract base class for routing strategies

### Routing Strategies

- `ContentAwareRouter`: Routes based on content characteristics
- `CostBasedRouter`: Optimizes for cost efficiency
- `GeographicRouter`: Routes based on location and data residency
- `PerformanceRouter`: Optimizes for latency and throughput
- `CompositeRouter`: Combines multiple strategies with configurable weights

### Metrics Collectors

- `BandwidthMonitor`: Tracks throughput metrics
- `LatencyTracker`: Monitors response times
- `CostCalculator`: Analyzes storage and operation costs
- `GeographicOptimizer`: Handles geographic optimization
- `ContentTypeAnalyzer`: Analyzes content types
- `PerformanceMetrics`: Aggregates performance metrics

## Installation

The Optimized Data Routing system is included in the IPFS Kit Python package. No additional installation is required.

## Basic Usage

```python
from ipfs_kit_py.mcp.routing.integration import initialize_mcp_routing, select_backend

# Initialize the routing system
routing = initialize_mcp_routing()

# Register available backends
routing.register_backend('IPFS', {'type': 'ipfs'})
routing.register_backend('S3', {'type': 's3'})
routing.register_backend('FILECOIN', {'type': 'filecoin'})

# Select a backend for storing a file
result = routing.select_backend(
    operation_type='write',
    content_type='image',
    content_size=5 * 1024 * 1024,  # 5 MB
    region='us-east'
)

# Use the selected backend
selected_backend = result['backend']
print(f"Selected backend: {selected_backend}")
print(f"Reason: {result['reason']}")
```

## Configuration

You can customize the routing system by passing a configuration dictionary to `initialize_mcp_routing()`:

```python
config = {
    'default_backend': 'IPFS',
    'strategy_weights': {
        'content': 0.3,
        'cost': 0.3,
        'geo': 0.2,
        'performance': 0.2
    },
    'backend_costs': {
        'IPFS': {
            'storage_cost': 0.02,    # $ per GB per month
            'retrieval_cost': 0.01,  # $ per GB
            'operation_cost': 0.0001  # $ per operation
        },
        'S3': {
            'storage_cost': 0.023,
            'retrieval_cost': 0.09,
            'operation_cost': 0.0005
        }
    },
    'geographic_regions': {
        'us-east': {'name': 'US East', 'coordinates': (37.7749, -122.4194)},
        'eu-west': {'name': 'EU West', 'coordinates': (53.3498, -6.2603)}
    }
}

routing = initialize_mcp_routing(config)
```

### Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `default_backend` | Fallback backend when routing fails | `'IPFS'` |
| `strategy_weights` | Weights for different routing strategies | Equal weights |
| `backend_costs` | Storage and retrieval costs for backends | Default costs |
| `geographic_regions` | Definitions of geographic regions | Default regions |
| `max_history_size` | Maximum number of routing decisions to keep | `1000` |

## Advanced Features

### Selecting a Backend with a Specific Strategy

You can use a specific routing strategy instead of the composite strategy:

```python
# Use only cost-based routing
result = routing.select_backend(
    operation_type='write',
    content_size=1 * 1024 * 1024 * 1024,  # 1 GB
    strategy='cost_based'
)
```

Available strategies: `'content_aware'`, `'cost_based'`, `'geographic'`, `'performance'`

### Recording Performance Metrics

Record performance metrics to improve future routing decisions:

```python
# Record performance for a completed operation
start_time = time.time() - 0.1  # Operation took 100ms
routing.record_operation_performance(
    backend='IPFS',
    operation_type='read',
    start_time=start_time,
    bytes_received=10 * 1024 * 1024,  # 10 MB
    success=True
)
```

### Getting Backend Metrics

Retrieve collected metrics for a backend:

```python
# Get all metrics for a backend
metrics = routing.get_backend_metrics('IPFS')

# Access specific metric types
latency = metrics.get('latency', {}).get('latency_ms')
throughput = metrics.get('bandwidth', {}).get('throughput_mbps')
```

### Viewing Routing History

Review past routing decisions:

```python
# Get recent routing decisions
history = routing.get_routing_history(limit=10)

# Print decisions
for decision in history:
    print(f"Backend: {decision['backend']}, Operation: {decision['operation']}")
```

## Content Type Mapping

The system maps content types to these standard categories:

| Category | Description | Examples |
|----------|-------------|----------|
| `image` | Image files | JPEG, PNG, GIF |
| `video` | Video files | MP4, AVI, MKV |
| `audio` | Audio files | MP3, WAV, FLAC |
| `document` | Document files | PDF, DOCX, TXT |
| `dataset` | Data files | CSV, Parquet, HDF5 |
| `model` | ML model files | PyTorch, TensorFlow |
| `archive` | Archive files | ZIP, TAR, 7Z |
| `binary` | Other binary files | EXE, BIN |

## Operation Types

The system supports these operation types:

| Operation | Description |
|-----------|-------------|
| `read` | Read/download data |
| `write` | Write/upload data |
| `delete` | Delete data |
| `list` | List/enumerate data |
| `stat` | Get metadata about data |
| `archive` | Archive data for long-term storage |
| `backup` | Back up data |
| `restore` | Restore data from backup |

## Integration with MCP Server

The Optimized Data Routing system integrates with the MCP server through the `MCPRoutingIntegration` class. This integration provides:

1. Backend selection for storage operations
2. Performance metrics collection
3. Cost analysis and optimization
4. Geographic routing capabilities

### Example: Using in MCP Server

```python
from ipfs_kit_py.mcp.routing.integration import initialize_mcp_routing

# Initialize routing in server startup
def initialize_server():
    routing = initialize_mcp_routing()
    server.routing = routing
    
    # Register available backends
    for backend in server.get_available_backends():
        routing.register_backend(backend, server.get_backend_info(backend))

# Use routing in request handler
def handle_upload(request):
    # Select backend
    result = server.routing.select_backend(
        operation_type='write',
        content_type=request.content_type,
        content_size=len(request.data),
        region=request.headers.get('X-User-Region')
    )
    
    # Use selected backend
    backend = result['backend']
    
    # Track start time
    start_time = time.time()
    
    # Perform upload
    response = server.upload_to_backend(backend, request.data)
    
    # Record performance
    server.routing.record_operation_performance(
        backend=backend,
        operation_type='write',
        start_time=start_time,
        bytes_sent=len(request.data),
        success=response.success
    )
    
    return response
```

## Extending the System

### Adding a New Backend

```python
# Register a new backend
routing.register_backend('NEW_BACKEND', {
    'type': 'custom',
    'regions': ['us-east', 'eu-west'],
    'features': ['example-feature']
})
```

### Adding a Custom Routing Strategy

```python
from ipfs_kit_py.mcp.routing.router import RoutingStrategy, RoutingDecision

class CustomStrategy(RoutingStrategy):
    def select_backend(self, context, available_backends, metrics):
        # Custom logic to select a backend
        backend = available_backends[0]  # Example: select first available
        
        return RoutingDecision(
            backend=backend,
            score=1.0,
            reason="Selected by custom strategy",
            metrics=metrics.get(backend, RouteMetrics())
        )

# Add the strategy to the router
router.add_strategy("custom", CustomStrategy())
```

## Best Practices

1. **Register All Available Backends**: Make sure to register all available storage backends before making routing decisions.

2. **Use Appropriate Strategy Weights**: Adjust strategy weights based on your priorities (cost, performance, content type, location).

3. **Record Performance Metrics**: Regularly record performance metrics to improve future routing decisions.

4. **Monitor Backend Distribution**: Check the distribution of data across backends to ensure balanced usage.

5. **Consider Data Residency**: Use the geographic routing features to comply with data residency requirements.

6. **Periodically Review Decisions**: Use the routing history to review and fine-tune the routing system.

## Troubleshooting

### Common Issues

1. **No backends available for routing**
   
   Make sure you've registered backends using `register_backend()`.

2. **Strategy not found**
   
   Check that you're using a valid strategy name when specifying a strategy.

3. **Missing metrics for routing decisions**
   
   Ensure you're recording performance metrics regularly to inform routing decisions.

### Logging

The routing system uses Python's standard logging module. To enable detailed logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('ipfs_kit_py.mcp.routing')
logger.setLevel(logging.DEBUG)
```

## Performance Considerations

- The routing system is designed to be lightweight and make quick decisions
- Metrics collection is cached to minimize performance impact
- For high-volume applications, consider adjusting the cache TTL and history sizes

## Examples

Check the examples directory for complete usage examples:

- `basic_routing.py`: Simple examples of using the routing system
- `multimedia_storage_app.py`: Advanced example of a multimedia storage application

## API Reference

### MCPRoutingIntegration

Main class for integrating the routing system with the MCP server.

#### Methods

- `select_backend(operation_type, content_type=None, content_size=None, user_id=None, region=None, strategy=None, metadata=None)`: Select a backend for an operation
- `record_operation_performance(backend, operation_type, start_time, bytes_sent=0, bytes_received=0, success=True, error=None)`: Record performance metrics
- `get_backend_metrics(backend)`: Get metrics for a backend
- `get_routing_history(limit=None)`: Get routing decision history

### Global Functions

- `initialize_mcp_routing(config=None)`: Initialize the routing system
- `select_backend(operation_type, content_type=None, content_size=None, user_id=None, region=None, strategy=None, metadata=None)`: Global convenience function for backend selection