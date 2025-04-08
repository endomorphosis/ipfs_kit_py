# MCP Server Architecture and Implementation

## Overview

The MCP (Model-Controller-Persistence) server is a structured approach to IPFS operations in the ipfs_kit_py project. It separates concerns into three main components:

1. **Models**: Handle business logic for IPFS operations (adding content, retrieving content, pinning, etc.)
2. **Controllers**: Handle HTTP requests and API endpoints using FastAPI
3. **Persistence**: Manage caching and data storage for improved performance

This architecture provides several benefits:
- Clean separation of concerns
- Improved testability
- Centralized caching for better performance
- Modular design for future extensions

## Core Components

### MCP Server (`server.py`)

The main server class coordinates models, controllers, and persistence components:

```python
class MCPServer:
    def __init__(self, 
                debug_mode: bool = False, 
                log_level: str = "INFO",
                persistence_path: str = None,
                isolation_mode: bool = False):
        # Initialize components
        self.cache_manager = MCPCacheManager(...)
        self.ipfs_kit = ipfs_kit(...)
        
        self.models = {
            "ipfs": IPFSModel(self.ipfs_kit, self.cache_manager)
        }
        self.controllers = {
            "ipfs": IPFSController(self.models["ipfs"])
        }
        self.persistence = self.cache_manager
```

Key features:
- **Debug Mode**: Enhanced logging and operation tracking
- **Isolation Mode**: Run with isolated IPFS repository for testing
- **FastAPI Integration**: Creates a router for HTTP endpoints
- **Operation Logging**: Debug middleware tracks request flow

### IPFS Model (`models/ipfs_model.py`)

Implements the business logic for IPFS operations:

```python
class IPFSModel:
    def __init__(self, ipfs_kit_instance=None, cache_manager=None):
        self.ipfs_kit = ipfs_kit_instance
        self.cache_manager = cache_manager
        self.operation_stats = {...}
    
    def add_content(self, content: Union[str, bytes], filename: Optional[str] = None):
        # Implementation of content addition with metrics tracking
        
    def get_content(self, cid: str):
        # Implementation with cache integration
        
    def pin_content(self, cid: str):
        # Pin implementation
```

Key features:
- **Metrics Tracking**: Records operation counts, byte transfers, etc.
- **Cache Integration**: Uses cache_manager for performance
- **Failure Handling**: Standardized error responses
- **Simulation Mode**: Can operate with simulated responses for testing

### IPFS Controller (`controllers/ipfs_controller.py`)

Handles HTTP requests for IPFS operations:

```python
class IPFSController:
    def __init__(self, ipfs_model):
        self.ipfs_model = ipfs_model
    
    def register_routes(self, router: APIRouter):
        # Register FastAPI routes
        router.add_api_route("/ipfs/add", self.add_content, methods=["POST"])
        router.add_api_route("/ipfs/cat/{cid}", self.get_content, methods=["GET"])
        # More routes...
    
    async def add_content(self, content_request: ContentRequest):
        # Handle HTTP request and delegate to model
```

Key features:
- **FastAPI Integration**: Uses Pydantic models for request/response validation
- **HTTP Error Handling**: Converts model errors to HTTP errors
- **Endpoint Documentation**: Provides API documentation for FastAPI

### Cache Manager (`persistence/cache_manager.py`)

Implements a tiered caching system (memory and disk):

```python
class MCPCacheManager:
    def __init__(self, 
                base_path: str = None, 
                memory_limit: int = 100 * 1024 * 1024,  # 100 MB
                disk_limit: int = 1024 * 1024 * 1024):  # 1 GB
        self.memory_cache = {}
        self.disk_cache_path = os.path.join(self.base_path, "disk_cache")
        self.metadata = {}
    
    def put(self, key: str, value: Any, metadata: Dict[str, Any] = None):
        # Store in memory and/or disk based on size
    
    def get(self, key: str) -> Optional[Any]:
        # Retrieve from memory or disk with promotion
```

Key features:
- **Tiered Caching**: Memory (fast) and disk (larger capacity) layers
- **Intelligent Eviction**: Based on recency, frequency, and size
- **Background Cleanup**: Automatic eviction when limits are reached
- **Persistence**: Survives restarts with metadata

## Testing Approaches

Multiple testing approaches were implemented:

### 1. MCP Emulator (`examples/mcp_emulator.py`)
- Standalone implementation that doesn't require external dependencies
- Mimics the core functionality of the real MCP server
- Useful for demonstrating the architecture and functionality
- Executes a full example workflow with all IPFS operations

### 2. Simple Test (`examples/mcp_simple_test.py`)
- Tests the MCP server's core functionality without requiring networking
- Uses the real MCP implementation but disables isolation mode
- Handles async operations properly
- Verifies core operations (add, get, pin, unpin, list)

### 3. Async Test (`examples/mcp_async_test.py`)
- Tests the MCP server with FastAPI integration without HTTP server
- Demonstrates how the server's endpoints are registered and called
- Tests direct interaction with route handlers

### 4. Full Server Example (`examples/mcp_server_example.py`)
- Complete implementation with FastAPI server
- Showcases all available endpoints and features
- Uses custom port (9999) to avoid conflicts
- Can be run with various flags for debugging and isolation

## Implementation Highlights

### Graceful Degradation

The system can operate in different modes:

- **Full Mode**: With working IPFS daemon
- **Simulation Mode**: Auto-creates simulated responses for testing
- **Isolation Mode**: Separate IPFS path for testing

### Caching Design

The caching system uses a sophisticated scoring algorithm:

```python
def _calculate_score(self, key: str) -> float:
    # Calculate priority score based on:
    recency = max(0, 1.0 - (time_since_access / (24 * 60 * 60)))
    frequency = min(1.0, access_count / 10.0)
    size_factor = max(0.1, 1.0 - (size / (10 * 1024 * 1024)))
    
    # Combined score
    score = (recency * 0.4 + frequency * 0.4 + size_factor * 0.2)
    return score
```

This ensures optimal use of limited cache resources.

### Debug Infrastructure

Comprehensive debugging capabilities:

- Operation logging for request/response tracking
- Detailed metrics for all operations
- Cache statistics and hit rates
- Debug HTTP endpoints for introspection

## Usage Example

```python
from fastapi import FastAPI
from ipfs_kit_py.mcp.server import MCPServer

# Create FastAPI app
app = FastAPI(title="IPFS MCP Server")

# Create MCP server with debug mode
mcp_server = MCPServer(
    debug_mode=True,
    persistence_path="/path/to/cache"
)

# Register MCP server with FastAPI app
mcp_server.register_with_app(app, prefix="/mcp")

# Now the app has MCP endpoints
# GET /mcp/health
# POST /mcp/ipfs/add
# GET /mcp/ipfs/cat/{cid}
# etc.
```

## Key Findings

1. The MCP architecture provides a clean separation of concerns and facilitates testing
2. The server can run in debug mode, providing detailed information for troubleshooting
3. Isolation mode allows for testing without affecting the host system
4. Caching improves performance and provides useful metrics
5. The emulator demonstrates the architecture without requiring IPFS installation
6. The implementation gracefully handles IPFS daemon failures with simulated responses
7. The tiered caching system optimizes resource usage and improves performance

## Future Enhancements

Potential future improvements:

1. **Additional Models**: Support for Storacha, S3, and other providers
2. **Distributed Caching**: Share cache between nodes in a cluster
3. **Webhooks**: Event notifications for operations
4. **Rate Limiting**: Protect against abuse
5. **Authentication**: Secure API access
6. **Metrics Export**: Prometheus-compatible metrics endpoint
7. **Improve Documentation**: Add more detailed API reference documentation
8. **Comprehensive Integration Tests**: Add more tests for edge cases