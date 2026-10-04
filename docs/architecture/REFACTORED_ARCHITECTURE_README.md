# IPFS-Kit Refactored Architecture

## Overview

The IPFS-Kit has been refactored into a daemon-based architecture that separates management operations from client operations. This provides better scalability, separation of concerns, and performance.

## Architecture Components

### 🔧 IPFS-Kit Daemon (`ipfs_kit_daemon.py`)
- **Purpose**: Central management process for all backend operations
- **Responsibilities**:
  - Filesystem backend health monitoring and management
  - Starting/stopping IPFS backends
  - Log collection and rotation
  - Replication management and coordination
  - Pin index updates and maintenance
  - Background monitoring loops
- **API**: HTTP REST API on port 8887 (configurable)
- **Persistence**: Maintains state across restarts

### 📡 Daemon Client Library (`ipfs_kit_daemon_client.py`)
- **Purpose**: Communication layer between clients and daemon
- **Features**:
  - Async HTTP client for daemon communication
  - Route reader for direct parquet index access
  - Mixin classes for easy integration
  - Error handling and fallback mechanisms
- **Usage**: Imported by MCP servers and CLI tools

### 🌐 Refactored MCP Server (`refactored_mcp_server.py`)
- **Purpose**: Lightweight interface for MCP tools and dashboard
- **Features**:
  - Delegates management operations to daemon
  - Direct IPFS-Kit library usage for retrieval
  - Enhanced VFS endpoints with daemon integration
  - Dashboard integration with real-time data
- **API**: HTTP REST API on port 8888 (configurable)

### 💻 CLI Tool (`ipfs_kit_cli.py`)
- **Purpose**: Command-line interface with daemon integration
- **Features**:
  - Daemon management commands
  - Direct IPFS operations for performance
  - Route inspection and statistics
  - Pin management with optimal routing
- **Usage**: `python ipfs_kit_cli.py <command> [args]`

## Key Benefits

### 🚀 Performance
- **Fast Routing**: Direct parquet index access for routing decisions
- **No Daemon Dependency**: Retrieval operations don't require daemon communication
- **Parallel Operations**: Management and retrieval can run independently

### 🔧 Scalability
- **Separate Lifecycles**: Components can be restarted independently
- **Resource Isolation**: Daemon handles resource-intensive background tasks
- **Multiple Clients**: Many MCP servers/CLI tools can use same daemon

### 📊 Monitoring
- **Centralized Health**: Single daemon monitors all backends
- **Real-time Status**: Dashboard gets live data from daemon
- **Background Processing**: Continuous health checks and maintenance

## Usage Guide

### Starting the System

1. **Start the Daemon** (required for management operations):
   ```bash
   python ipfs_kit_daemon.py
   ```

2. **Start MCP Server** (for dashboard and API access):
   ```bash
   python refactored_mcp_server.py
   ```

3. **Use CLI Tool** (for command-line operations):
   ```bash
   python ipfs_kit_cli.py daemon status
   python ipfs_kit_cli.py pin add <hash>
   python ipfs_kit_cli.py route stats
   ```

### API Endpoints

#### Daemon API (Port 8887)
- `GET /health` - Daemon health check
- `GET /status` - Daemon status and uptime
- `GET /backends/health` - Backend health status
- `POST /backends/start/<name>` - Start a backend
- `POST /backends/stop/<name>` - Stop a backend
- `GET /replication/status` - Replication status
- `POST /replication/sync` - Trigger replication sync

#### MCP Server API (Port 8888)
- `GET /api/health` - Server health (includes daemon status)
- `GET /api/vfs/*` - VFS operations with daemon integration
- `GET /api/dashboard/*` - Dashboard endpoints with real-time data
- `POST /api/pins/*` - Pin management with optimal routing

### CLI Commands

```bash
# Daemon management
python ipfs_kit_cli.py daemon status
python ipfs_kit_cli.py daemon start
python ipfs_kit_cli.py daemon stop

# Backend operations
python ipfs_kit_cli.py backend list
python ipfs_kit_cli.py backend health
python ipfs_kit_cli.py backend start <name>
python ipfs_kit_cli.py backend stop <name>

# Pin operations
python ipfs_kit_cli.py pin add <hash>
python ipfs_kit_cli.py pin remove <hash>
python ipfs_kit_cli.py pin list

# Routing and statistics
python ipfs_kit_cli.py route stats
python ipfs_kit_cli.py route suggest
python ipfs_kit_cli.py route inspect <hash>

# IPFS operations (direct library access)
python ipfs_kit_cli.py ipfs get <hash>
python ipfs_kit_cli.py ipfs add <file>
python ipfs_kit_cli.py ipfs id
```

## Configuration

### Daemon Configuration
```python
# In ipfs_kit_daemon.py or config file
DAEMON_CONFIG = {
    "host": "127.0.0.1",
    "port": 8887,
    "log_level": "INFO",
    "health_check_interval": 30,
    "replication_sync_interval": 300,
    "max_log_size": "100MB",
    "data_dir": "/tmp/ipfs_kit_daemon"
}
```

### MCP Server Configuration
```python
# In refactored_mcp_server.py or config file
SERVER_CONFIG = {
    "host": "127.0.0.1", 
    "port": 8888,
    "daemon_url": "http://127.0.0.1:8887",
    "enable_dashboard": True,
    "ipfs_kit_config": {
        "auto_start_daemons": False  # Daemon manages this
    }
}
```

## Development Workflow

### For Management Operations
1. Use daemon client to communicate with daemon
2. Handle daemon unavailability gracefully
3. Provide fallback to direct IPFS-Kit usage when possible

### For Retrieval Operations  
1. Use IPFS-Kit libraries directly for best performance
2. Read parquet indexes for routing decisions
3. No daemon dependency required

### For New Features
1. **Management features**: Add to daemon and expose via API
2. **Retrieval features**: Implement in IPFS-Kit libraries
3. **Interface features**: Add to MCP server or CLI tool

## Monitoring and Debugging

### Health Checks
- Daemon: `curl http://localhost:8887/health`
- MCP Server: `curl http://localhost:8888/api/health`
- CLI: `python ipfs_kit_cli.py daemon status`

### Logs
- Daemon logs: Check daemon process output or configured log file
- MCP Server logs: Check server process output
- IPFS Backend logs: Managed by daemon, accessible via API

### Demo Script
Run the architecture demo to verify everything is working:
```bash
python demo_refactored_architecture.py
```

## Migration from Old Architecture

The refactored architecture maintains compatibility while providing new capabilities:

1. **Existing MCP endpoints**: Still work, but now use daemon for management
2. **IPFS operations**: Now use direct library access for better performance  
3. **Dashboard**: Enhanced with real-time daemon data
4. **CLI**: New daemon-aware commands while maintaining IPFS operations

## Troubleshooting

### Common Issues

1. **Daemon not starting**: Check port availability (8887)
2. **MCP server can't connect to daemon**: Verify daemon is running and accessible
3. **CLI operations fail**: Ensure IPFS-Kit libraries are available
4. **Routing issues**: Check parquet index files are accessible

### Recovery Procedures

1. **Restart daemon**: `python ipfs_kit_cli.py daemon restart`
2. **Reset daemon state**: Stop daemon, clear data directory, restart
3. **Fallback mode**: MCP server can operate without daemon for retrieval operations

## Next Steps

1. **Testing**: Run comprehensive tests with `python demo_refactored_architecture.py`
2. **Configuration**: Customize daemon and server configurations for your environment
3. **Integration**: Update existing scripts to use new CLI commands
4. **Monitoring**: Set up health check monitoring for production use

The refactored architecture provides a solid foundation for scaling IPFS-Kit operations while maintaining high performance and reliability.
