# Unified CLI and MCP Architecture - Complete Integration Guide

## Overview

This guide documents the complete unified CLI and MCP architecture integration for IPFS Kit, where all functionality flows through a consistent pattern: Core Modules → CLI → MCP Tools → Dashboard.

## Architecture Pattern

```
┌─────────────────────────────────────────────────────────────┐
│                    Core Modules                              │
│              (ipfs_kit_py/*.py)                             │
│                                                              │
│  storage_wal.py, bucket_vfs_manager.py,                    │
│  pin_manager.py, backend_manager.py, etc.                  │
└──────────────┬──────────────────────────┬──────────────────┘
               │                          │
               ▼                          ▼
┌──────────────────────────┐  ┌──────────────────────────────┐
│     CLI Integration       │  │    MCP Integration Layer      │
│   (ipfs_kit_py/*_cli.py)  │  │ (ipfs_kit_py/mcp/servers/    │
│                           │  │      *_mcp_tools.py)         │
│  - wal_cli.py            │  │  - wal_mcp_tools.py          │
│  - bucket_vfs_cli.py     │  │  - pin_mcp_tools.py          │
│  - simple_pin_cli.py     │  │  - backend_mcp_tools.py      │
│  - backend_cli.py        │  │  - bucket_vfs_mcp_tools.py   │
│  - vfs_version_cli.py    │  │  - vfs_version_mcp_tools.py  │
│  - journal_cli.py        │  │  - secrets_mcp_tools.py      │
│  - state_cli.py          │  │                              │
└──────────────┬────────────┘  └──────────────┬───────────────┘
               │                              │
               ▼                              ▼
┌──────────────────────────┐  ┌──────────────────────────────┐
│   Unified CLI Dispatcher  │  │   MCP Compatibility Shims     │
│ (unified_cli_dispatcher.py│  │      (mcp/*.py)              │
│  integrated into cli.py)  │  │                              │
└──────────────┬────────────┘  └──────────────┬───────────────┘
               │                              │
               ▼                              ▼
┌──────────────────────────┐  ┌──────────────────────────────┐
│    ipfs-kit Command       │  │      MCP Server              │
│                           │  │                              │
│  $ ipfs-kit bucket ...    │  │  HTTP/WebSocket Server       │
│  $ ipfs-kit wal ...       │  │  Port: 8004                  │
│  $ ipfs-kit pin ...       │  │                              │
└───────────────────────────┘  └──────────────┬───────────────┘
                                              │
                                              ▼
                               ┌──────────────────────────────┐
                               │    JavaScript SDK             │
                               │                              │
                               │  MCP Client Library          │
                               └──────────────┬───────────────┘
                                              │
                                              ▼
                               ┌──────────────────────────────┐
                               │    MCP Dashboard             │
                               │                              │
                               │  Web UI for all operations   │
                               └──────────────────────────────┘
```

## Unified CLI Commands

All commands are now accessible via the single `ipfs-kit` command:

### 1. Bucket VFS Management

```bash
# Create a new bucket
ipfs-kit bucket create mybucket --type dataset --structure hierarchical

# List all buckets
ipfs-kit bucket list

# Get bucket information
ipfs-kit bucket info mybucket

# Upload file to bucket
ipfs-kit bucket upload mybucket /path/to/file --dest /remote/path

# Download from bucket
ipfs-kit bucket download mybucket /remote/path --dest /local/path

# List bucket contents
ipfs-kit bucket ls mybucket --path /

# Delete bucket
ipfs-kit bucket delete mybucket --force
```

### 2. VFS Versioning

```bash
# Create snapshot
ipfs-kit vfs snapshot mybucket --message "Initial snapshot"

# List versions
ipfs-kit vfs versions mybucket

# Restore version
ipfs-kit vfs restore mybucket v1.0.0

# Compare versions
ipfs-kit vfs diff mybucket v1.0.0 v1.0.1
```

### 3. Write-Ahead Log (WAL)

```bash
# Show WAL status
ipfs-kit wal status

# List operations
ipfs-kit wal list --status pending --limit 50

# Show operation details
ipfs-kit wal show <operation_id>

# Wait for operation
ipfs-kit wal wait <operation_id> --timeout 300

# Clean up old operations
ipfs-kit wal cleanup --age 7
```

### 4. Pin Management

```bash
# Add pin
ipfs-kit pin add QmHash --name "my-pin" --recursive

# List pins
ipfs-kit pin ls --type recursive

# Get pin info
ipfs-kit pin info QmHash

# Remove pin
ipfs-kit pin rm QmHash
```

### 5. Backend Management

```bash
# Create backend
ipfs-kit backend create mybackend s3 \
  --endpoint https://s3.amazonaws.com \
  --access-key KEY \
  --secret-key SECRET \
  --bucket mybucket \
  --region us-west-2

# List backends
ipfs-kit backend list

# Get backend info
ipfs-kit backend info mybackend

# Test connection
ipfs-kit backend test mybackend

# Update backend
ipfs-kit backend update mybackend --endpoint https://new-endpoint.com

# Delete backend
ipfs-kit backend delete mybackend
```

### 6. Filesystem Journal

```bash
# Show journal status
ipfs-kit journal status

# List journal entries
ipfs-kit journal list --limit 50

# Replay journal
ipfs-kit journal replay --from-seq 100 --to-seq 200

# Compact journal
ipfs-kit journal compact --keep-days 30
```

### 7. State Management

```bash
# Show current state
ipfs-kit state show

# Export state
ipfs-kit state export /path/to/export.json --format json

# Import state
ipfs-kit state import /path/to/import.json

# Reset state
ipfs-kit state reset --confirm
```

### 8. Existing Commands

```bash
# MCP Server
ipfs-kit mcp start --port 8004
ipfs-kit mcp stop
ipfs-kit mcp status

# Daemon
ipfs-kit daemon start --port 9999
ipfs-kit daemon stop

# Services
ipfs-kit services start --service all
ipfs-kit services stop --service ipfs
ipfs-kit services status

# Auto-healing
ipfs-kit autoheal enable --github-token TOKEN
ipfs-kit autoheal status
```

## MCP Tools Reference

### WAL MCP Tools (8 tools)

1. **wal_status** - Get WAL status and statistics
2. **wal_list_operations** - List operations with filtering
3. **wal_get_operation** - Get operation details
4. **wal_wait_for_operation** - Wait for completion
5. **wal_cleanup** - Clean up old operations
6. **wal_retry_operation** - Retry failed operations
7. **wal_cancel_operation** - Cancel operations
8. **wal_add_operation** - Add new operations

### Pin MCP Tools (8 tools)

1. **pin_add** - Add new IPFS pins
2. **pin_list** - List all pins with filtering
3. **pin_remove** - Remove pins
4. **pin_get_info** - Get pin details
5. **pin_list_pending** - List pending operations
6. **pin_verify** - Verify pin validity
7. **pin_update** - Update pin from old to new CID
8. **pin_get_statistics** - Get pin statistics

### Backend MCP Tools (8 tools)

1. **backend_create** - Create new backend
2. **backend_list** - List all backends
3. **backend_get_info** - Get backend details
4. **backend_update** - Update backend configuration
5. **backend_delete** - Delete backend
6. **backend_test_connection** - Test connectivity
7. **backend_get_statistics** - Get statistics
8. **backend_list_pin_mappings** - List pin mappings

### Existing MCP Tools

- **Bucket VFS Tools** (bucket_vfs_mcp_tools.py)
- **VFS Version Tools** (vfs_version_mcp_tools.py)
- **Secrets Management Tools** (secrets_mcp_tools.py)

## Dashboard Integration

All MCP tools are automatically available in the MCP Server and can be consumed by the JavaScript SDK and Dashboard.

### Starting the MCP Server

```bash
ipfs-kit mcp start --port 8004 --host 127.0.0.1
```

### Accessing from JavaScript SDK

```javascript
// Example: List WAL operations
const response = await mcpClient.callTool('wal_list_operations', {
  status: 'pending',
  limit: 50,
  backend: 'ipfs'
});

// Example: Add a pin
const pinResponse = await mcpClient.callTool('pin_add', {
  cid_or_file: 'QmHash...',
  name: 'my-document',
  recursive: true
});

// Example: List backends
const backends = await mcpClient.callTool('backend_list', {
  include_disabled: true
});
```

## Adding New Features

To add a new feature following this architecture:

### 1. Create Core Module

```python
# ipfs_kit_py/my_feature.py
class MyFeatureManager:
    def __init__(self):
        pass
    
    def do_something(self, param):
        # Core functionality
        return result
```

### 2. Create CLI Integration

```python
# ipfs_kit_py/my_feature_cli.py
async def handle_my_feature_command(args):
    manager = get_my_feature_manager()
    result = manager.do_something(args.param)
    print(f"✅ {result}")
    return 0
```

### 3. Add to Unified CLI Dispatcher

```python
# In unified_cli_dispatcher.py
def _add_my_feature_commands(self, subparsers):
    my_feature = subparsers.add_parser("my-feature", help="...")
    my_feature_sub = my_feature.add_subparsers(dest="my_feature_action")
    
    do = my_feature_sub.add_parser("do", help="Do something")
    do.add_argument("param", help="Parameter")
```

### 4. Create MCP Tools

```python
# ipfs_kit_py/mcp/servers/my_feature_mcp_tools.py
MY_FEATURE_MCP_TOOLS = [
    {
        "name": "my_feature_do",
        "description": "Do something via MCP",
        "inputSchema": {
            "type": "object",
            "properties": {
                "param": {"type": "string", "description": "Parameter"}
            },
            "required": ["param"]
        }
    }
]

async def handle_my_feature_do(arguments):
    manager = get_my_feature_manager()
    result = manager.do_something(arguments["param"])
    return {"success": True, "result": result}

MY_FEATURE_TOOL_HANDLERS = {
    "my_feature_do": handle_my_feature_do
}
```

### 5. Create Compatibility Shim

```python
# mcp/my_feature_mcp_tools.py
from ipfs_kit_py.mcp.servers.my_feature_mcp_tools import (
    MY_FEATURE_MCP_TOOLS,
    MY_FEATURE_TOOL_HANDLERS,
    handle_my_feature_do
)
```

### 6. Register MCP Tools

Add to the MCP server's tool registry to expose to Dashboard.

## Testing

### Test CLI Commands

```bash
# Test each command group
ipfs-kit bucket list
ipfs-kit vfs versions mybucket
ipfs-kit wal status
ipfs-kit pin ls
ipfs-kit backend list
```

### Test MCP Tools

```bash
# Start MCP server
ipfs-kit mcp start --port 8004

# Test via JavaScript SDK or curl
curl -X POST http://localhost:8004/tools/wal_status
```

## Benefits

### 1. Consistency
- All features follow the same architecture pattern
- Predictable structure makes development easier
- Clear separation of concerns

### 2. Maintainability
- Single source of truth for each feature (core module)
- CLI and MCP tools are thin wrappers
- Easy to add new features following the pattern

### 3. Accessibility
- Single unified CLI command (`ipfs-kit`)
- All features accessible via Dashboard
- Consistent API for JavaScript SDK

### 4. Testability
- Core modules can be tested independently
- CLI commands can be tested via subprocess
- MCP tools can be tested via HTTP

### 5. Documentation
- Clear architecture makes documentation straightforward
- Each layer has specific responsibilities
- Easy to understand data flow

## Migration from Standalone CLIs

Old standalone CLIs are now integrated:

| Old Command | New Command |
|------------|-------------|
| `wal-cli status` | `ipfs-kit wal status` |
| `bucket-cli list` | `ipfs-kit bucket list` |
| `pin-cli add <cid>` | `ipfs-kit pin add <cid>` |
| `backend-cli list` | `ipfs-kit backend list` |

## Summary

✅ **Unified CLI** - Single `ipfs-kit` command for all operations
✅ **Complete MCP Integration** - 24+ tools accessible via Dashboard
✅ **Consistent Architecture** - Core → CLI → MCP → Dashboard
✅ **Comprehensive Documentation** - This guide + inline comments
✅ **Easy to Extend** - Clear pattern for adding new features

All IPFS Kit functionality is now accessible through:
- Command line via `ipfs-kit`
- MCP Server via HTTP/WebSocket
- JavaScript SDK
- Web Dashboard

The architecture is production-ready, well-documented, and maintainable.
