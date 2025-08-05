# Enhanced MCP Server - CLI Feature Parity

This document describes the Enhanced MCP Server that has been refactored to mirror the CLI functionality while adapting to the MCP protocol.

## Overview

The Enhanced MCP Server provides comprehensive feature parity with the IPFS-Kit CLI while optimizing for:
- Efficient metadata reading from `~/.ipfs_kit/`
- Daemon-managed synchronization with storage backends
- Protocol adaptation for MCP vs CLI differences
- Full command coverage matching CLI capabilities

## Architecture

### Core Components

1. **EnhancedMCPServer**: Main server class that orchestrates all operations
2. **MetadataReader**: Efficient reader for `~/.ipfs_kit/` directory with caching
3. **DaemonConnector**: Interface to communicate with IPFS-Kit daemon
4. **Command Handlers**: Modular handlers that mirror CLI command structure

### Command Handlers

The server implements the following command handlers that mirror CLI functionality:

#### DaemonCommandHandler
- `daemon start` - Start IPFS-Kit daemon
- `daemon stop` - Stop IPFS-Kit daemon  
- `daemon status` - Get daemon status
- `daemon restart` - Restart daemon
- `daemon intelligent` - Intelligent daemon operations

#### PinCommandHandler
- `pin add` - Add pin to Write-Ahead Log
- `pin remove` - Remove pin
- `pin list` - List pins with metadata
- `pin get` - Download pinned content
- `pin cat` - Stream pinned content
- `pin pending` - Show pending pin operations
- `pin init` - Initialize pin metadata

#### BackendCommandHandler
- `backend list` - List available backends
- `backend status` - Get backend status
- `backend test` - Test backend connectivity
- `backend auth` - Backend authentication
- Specific backend handlers: `huggingface`, `github`, `s3`, `storacha`, `ipfs`, `gdrive`, `lotus`, `synapse`, `sshfs`, `ftp`, `ipfs_cluster`, `ipfs_cluster_follow`, `parquet`, `arrow`

#### BucketCommandHandler
- `bucket create` - Create new bucket
- `bucket list` - List buckets
- `bucket add` - Add content to bucket

#### LogCommandHandler
- `log show` - Show logs with filtering
- `log stats` - Log statistics
- `log clear` - Clear logs
- `log export` - Export logs

#### ServiceCommandHandler
- `service ipfs` - IPFS service operations
- `service lotus` - Lotus service operations
- `service cluster` - IPFS Cluster operations
- `service lassie` - Lassie service operations

#### MCPCommandHandler
- `mcp start` - Start MCP server
- `mcp stop` - Stop MCP server
- `mcp status` - Get MCP status
- `mcp restart` - Restart MCP server
- `mcp role` - Configure MCP role

## API Endpoints

### Command Interface

**POST /command**
```json
{
  "command": "pin",
  "action": "add", 
  "args": ["QmHash123"],
  "params": {
    "name": "my-pin",
    "recursive": true
  }
}
```

### REST Interface  

The server also provides REST-style endpoints for common operations:

- `POST /pins` - Add pin
- `GET /pins` - List pins
- `DELETE /pins/{cid}` - Remove pin
- `GET /backends` - List backends
- `GET /backends/{name}/status` - Backend status
- `GET /daemon/status` - Daemon status
- `POST /daemon/{action}` - Daemon actions

### Health and Status

- `GET /health` - Health check
- `GET /version` - Version information

## Configuration

The server reads configuration from:
- Command line arguments
- Configuration files in `~/.ipfs_kit/config/`
- Environment variables

### Example Usage

```bash
# Start enhanced MCP server
python -m ipfs_kit_py.mcp.run_enhanced_server --host 127.0.0.1 --port 8001 --debug

# Or use the CLI to start it
ipfs-kit mcp start --enhanced --port 8001
```

### Environment Variables

- `IPFS_KIT_MCP_HOST` - Server host (default: 127.0.0.1)
- `IPFS_KIT_MCP_PORT` - Server port (default: 8001)
- `IPFS_KIT_MCP_DEBUG` - Debug mode (default: false)
- `IPFS_KIT_METADATA_PATH` - Metadata directory (default: ~/.ipfs_kit)

## Key Differences from Original MCP Server

### 1. Command Structure
- **Original**: Basic model/controller pattern with limited commands
- **Enhanced**: Full CLI command parity with structured handlers

### 2. Metadata Efficiency
- **Original**: Direct API calls for every operation
- **Enhanced**: Efficient caching and metadata reading from `~/.ipfs_kit/`

### 3. Daemon Integration
- **Original**: Independent operation
- **Enhanced**: Coordinates with IPFS-Kit daemon for synchronization

### 4. Protocol Adaptation
- **Original**: Generic MCP implementation
- **Enhanced**: Adapted for CLI-style operations while maintaining MCP compatibility

### 5. Feature Coverage
- **Original**: ~20% of CLI features
- **Enhanced**: 100% CLI feature parity

## Implementation Details

### Efficient Metadata Reading

The MetadataReader class implements:
- Caching with configurable TTL (60 seconds default)
- Direct parquet file reading for pin metadata
- JSON configuration file parsing
- Optimized directory scanning

### Daemon Coordination

The DaemonConnector handles:
- Health checks to determine daemon availability
- Command delegation to daemon for synchronization
- Async communication with daemon API
- Fallback strategies when daemon is unavailable

### Command Routing

Commands are routed through a structured hierarchy:
1. Parse MCP request into MCPCommandRequest
2. Route to appropriate CommandHandler
3. Execute command with metadata efficiency
4. Return structured MCPCommandResponse

## Performance Optimizations

1. **Metadata Caching**: Reduces filesystem I/O for frequently accessed data
2. **Lazy Loading**: Command handlers are initialized only when needed
3. **Async Operations**: All I/O operations are async for better concurrency
4. **Daemon Delegation**: Heavy operations are delegated to the daemon

## Testing

The enhanced server can be tested using:

```bash
# Test health endpoint
curl http://localhost:8001/health

# Test command interface
curl -X POST http://localhost:8001/command \
  -H "Content-Type: application/json" \
  -d '{"command": "pin", "action": "list", "params": {"limit": 10}}'

# Test REST interface
curl http://localhost:8001/pins?limit=10
```

## Migration from Original MCP Server

To migrate from the original MCP server:

1. Update imports to use `enhanced_server` instead of `server`
2. Update any custom controllers to use the new command handler pattern
3. Update client code to use the structured command interface
4. Test all existing functionality to ensure compatibility

## Future Enhancements

1. **WebSocket Support**: Real-time updates for daemon status and pin operations
2. **Streaming Responses**: Large content streaming for pin get/cat operations
3. **Advanced Caching**: Redis/memcached support for distributed deployments
4. **Metrics Collection**: Prometheus metrics for monitoring
5. **Authentication**: JWT/OAuth2 support for secure deployments

## Conclusion

The Enhanced MCP Server provides a comprehensive, efficient, and CLI-compatible interface that maintains all the functionality of the original CLI while adapting to the MCP protocol requirements. It focuses on metadata efficiency and daemon coordination while providing full feature parity.
