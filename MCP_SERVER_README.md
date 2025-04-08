# MCP Server

## Overview

The MCP (Model-Controller-Persistence) server is a structured approach for IPFS operations in the ipfs_kit_py project. It provides a clean separation of concerns through three main components:

1. **Models**: Handle business logic for IPFS operations
2. **Controllers**: Handle HTTP requests and API endpoints
3. **Persistence**: Manage caching and data storage

## Architecture

### Components

#### Models (`/ipfs_kit_py/mcp/models/`)
- **IPFSModel**: Encapsulates IPFS operations with standardized responses
- Provides simulation capabilities for development and testing
- Implements consistent error handling and response formats

#### Controllers (`/ipfs_kit_py/mcp/controllers/`)
- **IPFSController**: Maps HTTP routes to model methods
- Handles request validation and response formatting
- Manages HTTP status codes and headers

#### Persistence (`/ipfs_kit_py/mcp/persistence/`)
- **MCPCacheManager**: Implements multi-tier caching (memory and disk)
- Provides thread-safe access to cached content
- Implements intelligent eviction policies

### Main Server Class

The `MCPServer` class coordinates these components and provides a complete FastAPI application:

```python
from ipfs_kit_py.mcp import MCPServer

# Create the server
server = MCPServer(
    debug_mode=True,       # Enable detailed logging and debugging
    isolation_mode=True,   # Use isolated IPFS repository
    persistence_path="/path/to/cache"  # Custom cache location
)

# Use with FastAPI
from fastapi import FastAPI
app = FastAPI()
server.register_with_app(app, prefix="/api/v0/mcp")

# Start the server
import uvicorn
uvicorn.run(app, host="0.0.0.0", port=8000)
```

## Key Features

1. **Clean Separation of Concerns**:
   - Models focus on business logic
   - Controllers handle HTTP specifics
   - Persistence manages caching

2. **Flexible Configuration**:
   - Debug mode for detailed logs
   - Isolation mode for testing
   - Customizable cache configuration

3. **Multi-tier Caching**:
   - Memory cache for fastest access
   - Disk cache for larger datasets
   - Configurable cache sizes and eviction policies

4. **Simulation Mode**:
   - Provides realistic responses when IPFS is unavailable
   - Useful for development and testing

5. **Comprehensive API**:
   - Complete IPFS operations (add, get, pin, etc.)
   - Statistical endpoints for monitoring
   - Health check and debugging endpoints

## Usage Examples

### Basic Server

```python
from ipfs_kit_py.mcp import MCPServer
from fastapi import FastAPI

# Create server and app
server = MCPServer()
app = FastAPI()
server.register_with_app(app)

# Add content
@app.get("/add-example")
async def add_example():
    result = await server.ipfs_model.add_content("Hello, IPFS!")
    return result
```

### Using the CLI

```bash
# Start the server
python -m ipfs_kit_py.mcp.server --port 8000 --debug

# Use with curl
curl -X POST http://localhost:8000/api/v0/mcp/ipfs/add \
  -H "Content-Type: application/json" \
  -d '{"content": "Hello, IPFS!"}'
```

### Custom Cache Configuration

```python
from ipfs_kit_py.mcp import MCPServer

# Configure custom cache settings
server = MCPServer(
    cache_config={
        "memory_limit": 500 * 1024 * 1024,  # 500MB
        "disk_limit": 5 * 1024 * 1024 * 1024,  # 5GB
        "disk_path": "/mnt/fast_storage/ipfs_cache"
    }
)
```

## Testing

The MCP server has a comprehensive test suite with 82 passing tests covering all key components:

- Models and simulation capabilities
- Controller endpoints and HTTP behavior
- Cache operations and thread safety
- Middleware and error handling

See [TEST_README.md](TEST_README.md) and [MCP_TEST_IMPROVEMENTS.md](MCP_TEST_IMPROVEMENTS.md) for detailed information about the test suite and recent improvements.

## Future Development

1. **Enhanced Caching Algorithms**:
   - Implement predictive prefetching
   - Add content-aware caching policies

2. **Multi-node Synchronization**:
   - Synchronize cache state between nodes
   - Implement distributed cache invalidation

3. **Metrics Collection**:
   - Add detailed performance metrics
   - Expose Prometheus-compatible metrics endpoint

4. **Authorization System**:
   - Add role-based access control
   - Implement token-based authentication