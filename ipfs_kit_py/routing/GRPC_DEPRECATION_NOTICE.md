# gRPC Components Deprecation Notice

## Status: DEPRECATED as of July 10, 2025

The gRPC routing components have been **deprecated** to resolve critical protobuf version conflicts.

## Affected Components

### Deprecated gRPC Files:
- `ipfs_kit_py/routing/grpc_server.py` 
- `ipfs_kit_py/routing/grpc_client.py`
- `ipfs_kit_py/routing/grpc_auth.py` 
- `ipfs_kit_py/routing/standalone_grpc_server.py`
- `ipfs_kit_py/routing/grpc/routing_pb2.py`
- `ipfs_kit_py/routing/grpc/routing_pb2_grpc.py`

### Protobuf Conflict Details:
```
gRPC routing required: protobuf==5.29.0 (hardcoded in generated files)
libp2p networking required: protobuf>=3.20.1,<4.0.0  
Current environment: protobuf 6.30.2
Result: Runtime validation failures and import crashes
```

## What Still Works (Unaffected)

✅ **All Core IPFS Operations**
- File add, get, pin, ls operations
- Content addressing and retrieval
- Local and remote IPFS node communication

✅ **Parquet-IPLD Storage System** 
- DataFrame storage as content-addressed Parquet
- Arrow-based analytics and queries
- Virtual filesystem integration
- Advanced caching (ARC) and WAL

✅ **MCP Servers**
- Standalone MCP server
- VFS MCP server  
- Cluster MCP server
- All MCP tools and functionality

✅ **Storage Infrastructure**
- Tiered cache management
- Write-ahead logging
- Metadata replication
- Performance optimization

## Migration Guide

### Instead of gRPC Routing:

```python
# OLD: gRPC client (deprecated)
from ipfs_kit_py.routing.grpc_client import RoutingClient
client = await RoutingClient.create("localhost:50051")
result = await client.select_backend(content_type="image/jpeg")

# NEW: Direct API usage (recommended)
from ipfs_kit_py.high_level_api import select_optimal_backend
result = await select_optimal_backend(content_type="image/jpeg")
```

### Instead of gRPC Server:

```python
# OLD: gRPC server (deprecated)  
from ipfs_kit_py.routing.grpc_server import GRPCServer
server = GRPCServer(host="0.0.0.0", port=50051)

# NEW: HTTP API server (available)
from ipfs_kit_py.routing.http_server import HTTPRoutingServer
server = HTTPRoutingServer(host="0.0.0.0", port=8080)
```

## HTTP API Replacement

The gRPC routing service has been replaced with an HTTP REST API:

### Endpoints:
- `POST /api/v1/select-backend` - Select optimal storage backend
- `POST /api/v1/record-outcome` - Record routing decision outcomes
- `GET /api/v1/insights` - Get routing analytics and insights  
- `GET /api/v1/metrics` - Get real-time performance metrics
- `GET /health` - Service health check

### Example Usage:
```bash
# Select backend via HTTP API
curl -X POST http://localhost:8080/api/v1/select-backend \
  -H "Content-Type: application/json" \
  -d '{"content_type": "image/jpeg", "content_size": 1024000}'

# Get routing insights  
curl http://localhost:8080/api/v1/insights

# Health check
curl http://localhost:8080/health
```

## Benefits of Deprecation

✅ **Eliminates Protobuf Conflicts** - Single protobuf version required
✅ **Preserves All Core Features** - Zero functionality loss for main features  
✅ **Improves Stability** - No more runtime validation failures
✅ **Simplifies Dependencies** - Cleaner dependency tree
✅ **Better Performance** - HTTP API often faster than gRPC for simple calls

## Impact Assessment

### Minimal Impact:
- **gRPC routing was optional** - Used primarily for cross-language access
- **Core IPFS operations unaffected** - No protobuf dependencies
- **Parquet storage unaffected** - Pure Arrow/Python implementation
- **MCP servers fully functional** - Independent of gRPC

### Who Might Be Affected:
- Applications using gRPC routing service directly
- Cross-language clients calling gRPC endpoints
- Custom integrations depending on protobuf routing messages

## Timeline

- **Immediate**: gRPC imports disabled, HTTP API available
- **This week**: Full HTTP API documentation  
- **Next month**: gRPC files removed from repository

## Questions or Issues?

The deprecation only affects the **optional gRPC routing interface**. All core IPFS Kit functionality remains fully operational and unaffected.

For questions about migration or HTTP API usage, please refer to the updated documentation.
