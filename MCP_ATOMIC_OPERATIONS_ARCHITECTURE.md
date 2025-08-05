# MCP Server Atomic Operations Architecture

## Overview

The MCP server has been refactored to follow a proper separation of concerns architecture where:

- **MCP Server**: Performs atomic operations on `~/.ipfs_kit/` files
- **Daemon**: Manages state through orchestrated operations (started separately with `ipfs-kit daemon`)
- **CLI**: Controls both MCP server and daemon independently

## Architecture Changes

### 1. MCP Server (Atomic Operations Only)

**Location**: `ipfs_kit_py/mcp_server/`

**Key Components**:
- `models/mcp_config_manager.py` - Manages MCP configuration from `~/.ipfs_kit/` files
- `services/mcp_daemon_service.py` - Lightweight interface to read daemon status and queue commands
- `controllers/` - 5 controllers mirroring CLI command structure
- `server.py` - Main MCP server with CLI-aligned tools

**Responsibilities**:
- Read/write configuration files in `~/.ipfs_kit/`
- Perform atomic file operations
- Read metadata from parquet files
- Queue commands for daemon to process
- Provide MCP protocol interface to CLI functionality

**Does NOT**:
- Start or manage the daemon process
- Perform orchestrated operations
- Maintain persistent state
- Handle replication or synchronization

### 2. Daemon Service Interface

**File**: `ipfs_kit_py/mcp_server/services/mcp_daemon_service.py`

**Key Features**:
- Reads daemon status from `~/.ipfs_kit/daemon_status.json`
- Writes command files to `~/.ipfs_kit/commands/` for daemon to process
- No daemon lifecycle management
- Atomic command queuing operations

**Example Operations**:
```python
# Queue a pin sync command for daemon to process
await daemon_service.force_sync_pins("my-backend")

# Queue metadata backup command
await daemon_service.force_backup_metadata()

# Read current daemon status from files
status = await daemon_service.get_daemon_status()
```

### 3. MCP Configuration Manager

**File**: `ipfs_kit_py/mcp_server/models/mcp_config_manager.py`

**Features**:
- Reads from `~/.ipfs_kit/config.json` and `~/.ipfs_kit/mcp_config.json`
- Supports dot notation for nested config keys
- Merges configurations with MCP-specific taking precedence
- Validates configuration settings

**Example Usage**:
```python
config_manager = get_mcp_config_manager("~/.ipfs_kit")
mcp_config = config_manager.get_mcp_config()
config_manager.set_config("mcp.port", 8001)
```

## CLI Integration

### MCP Commands

The CLI now provides comprehensive MCP server control:

```bash
# Start refactored MCP server (default)
ipfs-kit mcp start --port 8001 --debug

# Start legacy enhanced server
ipfs-kit mcp start --enhanced --port 8001

# Start legacy standard server  
ipfs-kit mcp start --standard --port 8001

# Check MCP server status
ipfs-kit mcp status

# Stop MCP server
ipfs-kit mcp stop

# Restart MCP server
ipfs-kit mcp restart
```

### Daemon Commands (Separate)

The daemon is managed independently:

```bash
# Start daemon
ipfs-kit daemon start --role local

# Check daemon status
ipfs-kit daemon status

# Stop daemon
ipfs-kit daemon stop
```

## Separation of Concerns

### MCP Server Responsibilities
- ✅ Atomic file operations on `~/.ipfs_kit/`
- ✅ Configuration management
- ✅ Metadata reading from parquet files
- ✅ Command queuing for daemon
- ✅ MCP protocol interface

### Daemon Responsibilities  
- ✅ Backend health monitoring
- ✅ Pin synchronization across backends
- ✅ Metadata index maintenance
- ✅ Replication management
- ✅ Cache and eviction policies
- ✅ Processing command queue

### CLI Responsibilities
- ✅ Starting/stopping MCP server
- ✅ Starting/stopping daemon
- ✅ Direct file operations
- ✅ User interface and commands

## Benefits

1. **Clear Separation**: Each component has well-defined responsibilities
2. **Independent Operation**: MCP server works without daemon, daemon works without MCP server
3. **Atomic Operations**: MCP server focuses on individual file operations
4. **Orchestrated Operations**: Daemon handles complex multi-step processes
5. **Configuration Isolation**: MCP has its own config management
6. **Testing**: Components can be tested independently
7. **Maintenance**: Easier to maintain and debug each component

## Usage Examples

### Starting Both Services

```bash
# Terminal 1: Start daemon for orchestration
ipfs-kit daemon start --role local --port 9999

# Terminal 2: Start MCP server for API access
ipfs-kit mcp start --port 8001 --debug
```

### MCP Client Usage

```python
# MCP client can now perform atomic operations
# while daemon handles orchestration in background

# Get backend list (atomic read)
backends = await mcp_client.call_tool("backend_list", {})

# Queue pin sync (atomic command write)
result = await mcp_client.call_tool("force_sync_pins", {"backend_name": "s3"})

# Read daemon status (atomic read)
status = await mcp_client.call_tool("daemon_status", {})
```

## File Structure

```
~/.ipfs_kit/
├── config.json              # Main configuration
├── mcp_config.json          # MCP-specific configuration
├── daemon_status.json       # Daemon status (written by daemon)
├── daemon.pid               # Daemon process ID
├── daemon.log               # Daemon logs
├── commands/                # Command queue directory
│   ├── sync_pins_20250731_133204.json
│   └── backup_metadata_20250731_133205.json
├── backend_index.parquet    # Backend metadata
├── pin_mappings.parquet     # Pin metadata
└── buckets/                 # Bucket data
```

## Testing

Run the atomic operations test:

```bash
python test_mcp_atomic_operations.py
```

This validates:
- ✅ MCP server components work independently
- ✅ Configuration manager handles `~/.ipfs_kit/` files
- ✅ Daemon service provides atomic interface
- ✅ Command queuing works correctly
- ✅ CLI integration functions properly
- ✅ Proper separation of concerns maintained
