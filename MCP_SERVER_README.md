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
   - Advanced operations (DAG, Block, IPNS, DHT)
   - Statistical endpoints for monitoring
   - Health check and debugging endpoints

6. **FSSpec Integration**:
   - Filesystem interface for IPFS content
   - Streamlined data access with FSSpec compatibility
   - Efficient file operations with range support

7. **Streaming Capabilities**:
   - Media streaming with chunked access
   - Range requests for partial content
   - Bidirectional streaming for uploads

8. **Filesystem Journaling**:
   - Transaction safety for filesystem operations
   - Automatic recovery from failures
   - Checkpointing for data integrity

9. **WAL Telemetry**:
   - AI-powered analysis of operation logs
   - Visualization of performance metrics
   - Anomaly detection and recommendations

10. **Configuration Management**:
    - Save and load configurations
    - Format conversion and validation
    - Secret management with optional inclusion

11. **Distributed Architecture**:
    - Cluster-wide cache coordination
    - Peer discovery with multiple methods
    - Cross-node state synchronization
    - Distributed task processing

12. **WebRTC Streaming**:
    - Media streaming over WebRTC
    - Dynamic quality adjustment
    - Performance benchmarking
    - Connection monitoring

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

# Get content by CID (uses ParquetCIDCache for metadata)
curl -X GET http://localhost:8000/api/v0/mcp/ipfs/cat/QmContent123

# Pin content (updates ParquetCIDCache metadata)
curl -X POST http://localhost:8000/api/v0/mcp/ipfs/pin \
  -H "Content-Type: application/json" \
  -d '{"cid": "QmContent123"}'

# Find peers using DHT
curl -X POST http://localhost:8000/api/v0/mcp/ipfs/dht/findpeer \
  -H "Content-Type: application/json" \
  -d '{"peer_id": "QmPeerID"}'

# Find content providers using DHT
curl -X POST http://localhost:8000/api/v0/mcp/ipfs/dht/findprovs \
  -H "Content-Type: application/json" \
  -d '{"cid": "QmContentID", "num_providers": 5}'

# Store data as a DAG node
curl -X POST http://localhost:8000/api/v0/mcp/ipfs/dag/put \
  -H "Content-Type: application/json" \
  -d '{"obj": {"name": "example", "data": [1, 2, 3]}}'
```

### Custom Cache Configuration

```python
from ipfs_kit_py.mcp import MCPServer

# Configure custom cache settings with ParquetCIDCache
server = MCPServer(
    cache_config={
        "memory_limit": 500 * 1024 * 1024,  # 500MB
        "disk_limit": 5 * 1024 * 1024 * 1024,  # 5GB
        "disk_path": "/mnt/fast_storage/ipfs_cache",
        "enable_parquet_cache": True,  # Enable ParquetCIDCache for metadata
        "parquet_cache_path": "/mnt/fast_storage/parquet_cache",
        "parquet_max_partition_rows": 100000,
        "parquet_auto_sync": True,
        "parquet_sync_interval": 300  # Seconds
    }
)
```

### Using FSSpec Filesystem

```python
# Get a filesystem interface from the MCP server
curl -X GET "http://localhost:8000/api/v0/mcp/cli/fs/get-filesystem?enable_metrics=true&use_gateway_fallback=true"

# Open a file by CID with range requests
curl -X GET "http://localhost:8000/api/v0/mcp/cli/fs/open/QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx?start_byte=0&end_byte=1024"
```

### Streaming Media

```python
# Stream media content with chunked access
curl -X GET "http://localhost:8000/api/v0/mcp/cli/stream/media/QmVideoContentCID?chunk_size=2097152"
```

### Filesystem Journaling

```python
# Enable filesystem journaling
curl -X POST "http://localhost:8000/api/v0/mcp/cli/fs/enable-journaling" \
  -H "Content-Type: application/json" \
  -d '{"journal_base_path": "~/.ipfs_kit/journal", "auto_recovery": true}'
  
# Get journal status
curl -X GET "http://localhost:8000/api/v0/mcp/cli/fs/journal-status"
```

### WAL Telemetry Analysis

```python
# Analyze WAL telemetry data with AI
curl -X POST "http://localhost:8000/api/v0/mcp/cli/wal/telemetry/ai-analyze" \
  -H "Content-Type: application/json" \
  -d '{"time_range": "24h", "operation_types": ["add", "pin"], "analysis_type": "comprehensive"}'
  
# Generate telemetry visualizations
curl -X POST "http://localhost:8000/api/v0/mcp/cli/wal/telemetry/visualize" \
  -H "Content-Type: application/json" \
  -d '{"visualization_type": "performance_over_time", "time_range": "7d", "output_format": "json"}'
```

### Configuration Management

```python
# Save configuration to file
curl -X POST "http://localhost:8000/api/v0/mcp/cli/config/save" \
  -H "Content-Type: application/json" \
  -d '{"config_path": "~/.ipfs_kit/config.yaml", "format": "yaml", "include_secrets": false}'
  
# Get current configuration
curl -X GET "http://localhost:8000/api/v0/mcp/cli/config?include_secrets=false&format=json"
```

## Testing

The MCP server has a comprehensive test suite with 82 passing tests covering all key components:

- Models and simulation capabilities
- Controller endpoints and HTTP behavior
- Cache operations and thread safety
- Middleware and error handling

See [TEST_README.md](TEST_README.md) and [MCP_TEST_IMPROVEMENTS.md](MCP_TEST_IMPROVEMENTS.md) for detailed information about the test suite and recent improvements.

## Parquet CID Cache Integration

The MCP server now includes comprehensive integration with ParquetCIDCache for efficient metadata management:

1. **Advanced Metadata Storage and Retrieval**:
   - Schema-optimized Arrow-based metadata storage via ParquetCIDCache
   - Efficient columnar format for fast queries and filtering
   - Sophisticated heat scoring for content prioritization
   - Persistent tracking of content access patterns
   - Comprehensive error handling with simulation mode

2. **Integration with Core Operations**:
   - `get_content`: Checks ParquetCIDCache for metadata before retrieval
   - `add_content`: Stores metadata with intelligent heat scoring
   - `pin_content`: Updates pin status in ParquetCIDCache

3. **Schema Optimization**:
   - Workload-based schema evolution and optimization
   - Automatic detection of query patterns
   - Dynamic column pruning for unused fields
   - Specialized indexes for frequently queried columns

4. **Performance Benefits**:
   - Reduced query latency through optimized schemas
   - Improved storage efficiency with column pruning
   - Fast metadata lookups with specialized indexes
   - Heat-based cache promotion for frequently accessed content

## Distributed Features

The MCP server now includes comprehensive distributed capabilities through the Distributed Controller:

1. **Cluster-Wide Caching Coordination**:
   - Synchronized cache across all cluster nodes
   - Automatic invalidation propagation
   - Intelligent cache placement strategies
   - Configurable time-to-live and propagation policies

2. **Peer Discovery and Configuration**:
   - Multiple discovery methods (mDNS, DHT, direct, bootstrap)
   - Automatic peer configuration
   - Role-based peer filtering
   - Performance metrics for peer connections

3. **Cross-Node State Synchronization**:
   - Real-time state updates via WebSockets
   - Path-based state queries and updates
   - Differential state synchronization
   - Conflict resolution with vector clocks

4. **Distributed Task Processing**:
   - Task submission and routing to appropriate nodes
   - Progress tracking and result aggregation
   - Priority-based scheduling
   - Fault tolerance with automatic task reassignment

### Using Distributed Features

```bash
# Discover peers using multiple methods
curl -X POST "http://localhost:8000/api/v0/mcp/distributed/peers/discover" \
  -H "Content-Type: application/json" \
  -d '{"discovery_methods": ["mdns", "dht"], "max_peers": 20, "timeout_seconds": 30}'

# Register a node with the cluster
curl -X POST "http://localhost:8000/api/v0/mcp/distributed/nodes/register" \
  -H "Content-Type: application/json" \
  -d '{"role": "worker", "capabilities": ["storage", "compute"], "resources": {"cpu_cores": 8, "memory_gb": 16}}'

# Perform a cluster-wide cache operation
curl -X POST "http://localhost:8000/api/v0/mcp/distributed/cache" \
  -H "Content-Type: application/json" \
  -d '{"operation": "put", "key": "shared_config", "value": {"max_connections": 100}, "propagate": true}'

# Submit a distributed task
curl -X POST "http://localhost:8000/api/v0/mcp/distributed/tasks/submit" \
  -H "Content-Type: application/json" \
  -d '{"task_type": "process_dataset", "parameters": {"cid": "QmDataset123", "algorithm": "feature_extraction"}, "priority": 8}'

# Get real-time cluster events using WebSockets
# Using a WebSocket client to connect to:
# ws://localhost:8000/api/v0/mcp/distributed/events
```

## WebRTC Streaming Support

The MCP server includes comprehensive WebRTC streaming capabilities through the WebRTC Controller:

1. **Media Streaming**:
   - Stream IPFS media content over WebRTC
   - Dynamic quality adjustment based on network conditions
   - ICE server configuration for NAT traversal
   - Connection statistics and monitoring

2. **Performance Benchmarking**:
   - Comprehensive streaming benchmarks
   - Latency and bandwidth measurements
   - Quality metrics tracking
   - Detailed performance reports

### Using WebRTC Features

```bash
# Check WebRTC dependencies
curl -X GET "http://localhost:8000/api/v0/mcp/webrtc/check"

# Stream content over WebRTC
curl -X POST "http://localhost:8000/api/v0/mcp/webrtc/stream" \
  -H "Content-Type: application/json" \
  -d '{"cid": "QmVideoContentCID", "quality": "high", "benchmark": true}'

# List active WebRTC connections
curl -X GET "http://localhost:8000/api/v0/mcp/webrtc/connections"

# Get statistics for a connection
curl -X GET "http://localhost:8000/api/v0/mcp/webrtc/connections/conn-123/stats"

# Run a WebRTC benchmark
curl -X POST "http://localhost:8000/api/v0/mcp/webrtc/benchmark" \
  -H "Content-Type: application/json" \
  -d '{"cid": "QmVideoContentCID", "duration": 120, "format": "html"}'
```

## Advanced ParquetCIDCache Usage

```python
from ipfs_kit_py.mcp import MCPServer
from ipfs_kit_py.cache.schema_column_optimization import SchemaOptimizer, WorkloadType

# Create server with ParquetCIDCache
server = MCPServer(
    cache_config={
        "enable_parquet_cache": True,
        "parquet_cache_path": "~/.ipfs_kit/cid_cache"
    }
)

# Access the ParquetCIDCache through the IPFS model
parquet_cache = server.models["ipfs"].ipfs_kit.parquet_cache

# Create a schema optimizer
optimizer = SchemaOptimizer()

# Optimize the schema based on workload type
optimizer.optimize_schema(parquet_cache.schema, WorkloadType.READ_HEAVY)

# Query CIDs with specific metadata
hot_cids = parquet_cache.query(
    filters={"heat_score": {"$gt": 0.7}},
    limit=10
)

# Get statistics about the cache
stats = parquet_cache.stats()
print(f"Total CIDs: {stats['record_count']}")
print(f"Total size: {stats['total_size_bytes'] / (1024*1024):.2f} MB")
```

## Future Development

1. **Security Enhancements**:
   - Add role-based access control
   - Implement token-based authentication
   - Add comprehensive API rate limiting

2. **Advanced Analytics Dashboard**:
   - Create unified visual dashboard for all metrics
   - Add predictive system health monitoring
   - Integrate with Grafana and Prometheus

3. **Integration Ecosystem**:
   - Add integration with popular data science frameworks
   - Create plugins for development environments
   - Build cross-language client libraries

4. **Enterprise Features**:
   - Add multi-tenant support
   - Implement advanced access control
   - Add enterprise audit logging
   - Create deployment automation tools