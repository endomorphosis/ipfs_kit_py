# MCP (Model-Controller-Persistence) Server for IPFS Kit

## Overview

The MCP server provides a modular architecture for IPFS Kit that separates concerns into three distinct layers:

1. **Models**: Encapsulate business logic and domain operations
2. **Controllers**: Handle HTTP requests and route them to the appropriate models
3. **Persistence**: Manage data storage, caching, and state management

This architecture offers several benefits:
- **Improved testability**: Each component can be tested in isolation
- **Enhanced debugging**: Debug mode with operation tracking and state inspection
- **Cleaner code organization**: Clear separation of concerns
- **Easier maintenance**: Changes to one layer don't affect others
- **Better performance**: Sophisticated caching system

## Directory Structure

```
ipfs_kit_py/mcp/
├── __init__.py         # Package initialization
├── server.py           # Main server orchestration
├── README.md           # This documentation file
├── models/             # Business logic layer
│   ├── __init__.py     # Models package initialization
│   └── ipfs_model.py   # IPFS operations model
├── controllers/        # HTTP request handling layer
│   ├── __init__.py     # Controllers package initialization
│   └── ipfs_controller.py  # IPFS operations controller
└── persistence/        # Data storage layer
    ├── __init__.py     # Persistence package initialization
    └── cache_manager.py  # Cache management system
```

## Key Components

### MCPServer

The main server class that orchestrates all components. It initializes models, controllers, and persistence layers, and registers routes with a FastAPI application.

```python
from ipfs_kit_py.mcp import MCPServer

# Initialize the MCP server
mcp_server = MCPServer(
    debug_mode=True,
    isolation_mode=False,
    ipfs_api=ipfs_api_instance,
    cache_dir="/path/to/cache",
    memory_cache_size=100 * 1024 * 1024,  # 100MB
    disk_cache_size=1 * 1024 * 1024 * 1024,  # 1GB
)

# Register with a FastAPI app
mcp_server.register_with_app(app, prefix="/api/v0/mcp")
```

### IPFSModel

The model class encapsulating IPFS operations and business logic. It handles adding, retrieving, pinning, and unpinning content, as well as tracking operation statistics.

```python
# The model is accessible through the MCP server
ipfs_model = mcp_server.models["ipfs"]

# Example operation
result = ipfs_model.add_content(content_bytes)
```

### IPFSController

The controller class handling HTTP requests related to IPFS operations. It defines routes, validates requests, delegates to the model, and formats responses.

```python
# Controllers are automatically registered with the FastAPI app
# When you call mcp_server.register_with_app(app, prefix="/api/v0/mcp")

# Example of a controller-defined endpoint:
# POST /api/v0/mcp/ipfs/add
# GET /api/v0/mcp/ipfs/get/{cid}
# POST /api/v0/mcp/ipfs/pin/{cid}
# DELETE /api/v0/mcp/ipfs/unpin/{cid}
# GET /api/v0/mcp/ipfs/pins
```

### CacheManager

A sophisticated caching system for operation results. It provides memory and disk tiers with automatic promotion/demotion based on access patterns.

```python
# The cache manager is accessible through the MCP server
cache_manager = mcp_server.persistence

# Cache operations
cache_manager.put("key", value, metadata={"size": len(value)})
value = cache_manager.get("key")
cache_manager.delete("key")

# Get cache statistics
cache_info = cache_manager.get_cache_info()
```

## Debug Mode

When enabled, debug mode provides enhanced information for troubleshooting:

- Detailed operation tracking in an in-memory log
- Debug endpoints for state inspection
- Request/response logging middleware
- Performance metrics

Access debug endpoints:
- GET /api/v0/mcp/debug - Current server state
- GET /api/v0/mcp/health - Health check
- GET /api/v0/mcp/operations - Operations log

## Isolation Mode

Isolation mode allows testing without affecting the host system:

- Uses in-memory storage instead of making real IPFS API calls
- Simulates responses based on persistent cache
- Useful for testing and debugging without requiring an IPFS daemon

## Example Usage

See `/examples/mcp_server_example.py` for a complete example of integrating the MCP server with a FastAPI application.

Basic integration:

```python
from fastapi import FastAPI
from ipfs_kit_py.high_level_api import IPFSSimpleAPI
from ipfs_kit_py.mcp import MCPServer

# Create FastAPI app
app = FastAPI()

# Initialize IPFS API client
ipfs_api = IPFSSimpleAPI()

# Initialize MCP server
mcp_server = MCPServer(
    debug_mode=True,
    isolation_mode=False,
    ipfs_api=ipfs_api,
)

# Register MCP server with the FastAPI app
mcp_server.register_with_app(app, prefix="/api/v0/mcp")

# Run the app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
```

## Benefits for Debugging

The MCP architecture provides several benefits for debugging in a live environment:

1. **Operation Tracking**: All operations are tracked with timestamps and results
2. **State Inspection**: Debug endpoints allow inspecting the current state of the system
3. **Isolation Mode**: Test functionality without affecting the real IPFS system
4. **Detailed Logging**: Comprehensive logging of all operations and errors
5. **Performance Metrics**: Timing information for all operations
6. **Cache Statistics**: Detailed information about cache performance

## Future Enhancements

1. Additional model implementations for other IPFS Kit functionality:
   - Cluster operations
   - AI/ML integration
   - Write-ahead logging

2. Extended controller capabilities:
   - Authentication and authorization
   - Rate limiting
   - Quota management

3. Advanced persistence features:
   - Database integration
   - Distributed caching
   - Persistent operation logging