# IPFS Kit Optimized Data Routing

This module provides intelligent data routing capabilities for IPFS Kit, allowing efficient content placement, retrieval, and management across multiple storage backends.

## Overview

The routing system uses adaptive algorithms to select the most appropriate storage backend for each piece of content, optimizing for factors like:

- **Content Type Compatibility**: Matching content types to specialized backends
- **Performance**: Selecting backends with low latency and high throughput
- **Cost Efficiency**: Minimizing storage and retrieval costs
- **Geographic Proximity**: Reducing network latency by using nearby backends
- **Load Balancing**: Distributing load across available backends

## Architecture

The routing system consists of several components:

1. **Routing Manager**: Central coordinator that provides a simple interface to the routing system
2. **Optimized Router**: Core routing logic for content-aware backend selection
3. **Adaptive Optimizer**: Advanced routing optimization with learning capabilities
4. **Routing Dashboard**: Visual interface for monitoring and configuration

## Usage

### Basic Usage

```python
from ipfs_kit_py.routing import RoutingManager, RoutingManagerSettings

# Initialize routing manager
settings = RoutingManagerSettings(
    enabled=True,
    backends=["ipfs", "filecoin", "s3"],
    default_strategy="hybrid",
    default_priority="balanced"
)

routing_manager = await RoutingManager.create(settings)

# Select the best backend for content
backend_id = await routing_manager.select_backend(
    content=content_data,
    metadata={
        "content_type": "application/pdf",
        "filename": "document.pdf"
    }
)

# Record the outcome for learning
await routing_manager.record_routing_outcome(
    backend_id=backend_id,
    content_info={
        "content_type": "application/pdf",
        "size_bytes": len(content_data)
    },
    success=True
)
```

### Dashboard

The routing system includes a visual dashboard for monitoring and configuration. You can run it using the provided CLI:

```bash
# Run the dashboard
python -m ipfs_kit_py.bin.routing_dashboard

# Or with options
python -m ipfs_kit_py.bin.routing_dashboard --host 0.0.0.0 --port 8050 --theme darkly
```

Or programmatically:

```python
from ipfs_kit_py.routing.dashboard import run_dashboard

# Run the dashboard with custom settings
run_dashboard({
    "host": "127.0.0.1",
    "port": 8050,
    "theme": "darkly",
    "debug": True
})
```

### Integration with MCP Server

The routing system is designed to be used independently or integrated with the MCP server. The MCP server uses the routing system through a compatibility layer that imports functionality from the core ipfs_kit_py module.

This separation of concerns allows:
- Core routing logic to be maintained in one place
- Different interaction methods (Apache Arrow IPC vs MCP protocol)
- Standalone usage outside of the MCP server

## Configuration

The routing system is configurable through the `RoutingManagerSettings` class:

```python
settings = RoutingManagerSettings(
    # Basic settings
    enabled=True,
    backends=["ipfs", "filecoin", "s3"],
    default_strategy="hybrid",
    default_priority="balanced",
    
    # Advanced settings
    collect_metrics_on_startup=True,
    auto_start_background_tasks=True,
    learning_enabled=True,
    telemetry_interval=300,
    metrics_retention_days=7,
    
    # Optimization weights
    optimization_weights={
        "network_quality": 0.25,
        "content_match": 0.2,
        "cost_efficiency": 0.2,
        "geographic_proximity": 0.15,
        "load_balancing": 0.05,
        "reliability": 0.1,
        "historical_success": 0.05
    },
    
    # Geographic location
    geo_location={
        "region": "us-east",
        "coordinates": {
            "lat": 40.7128,
            "lon": -74.0060
        }
    }
)
```

## Advanced Features

### Routing Strategies

The system supports different routing strategies:

- **adaptive**: Uses machine learning to optimize routing based on multiple factors
- **content_type**: Routes based on content characteristics (type, size)
- **cost**: Optimizes for minimum storage and retrieval cost
- **performance**: Prioritizes backends with low latency and high throughput
- **geographic**: Routes to geographically proximate backends
- **reliability**: Prioritizes the most reliable backends
- **hybrid**: Combines multiple factors using weighted scoring (default)

### Routing Priorities

You can also specify a routing priority to emphasize certain aspects:

- **balanced**: Equal consideration of all factors (default)
- **performance**: Emphasis on speed and responsiveness
- **cost**: Emphasis on cost efficiency
- **reliability**: Emphasis on backend reliability and availability
- **geographic**: Emphasis on geographic proximity

## Contributing

Contributions to the routing system are welcome. Areas for improvement include:

- Additional routing algorithms
- Enhanced metrics collection
- Improved visualization in the dashboard
- Better documentation and examples
- Performance optimizations