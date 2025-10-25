# MCP Server

This directory contains the production MCP server for IPFS Kit.

## Production Server

- `enhanced_unified_mcp_server.py` - The main production MCP server with full backend observability and dashboard.
- `enhanced_mcp_server_with_daemon_mgmt.py` - Enhanced daemon management and real IPFS integration.

## Features

- Real IPFS operations using direct commands
- Automatic daemon management and startup
- Graceful fallback handling for protobuf compatibility issues
- Comprehensive error handling and logging
- Full MCP protocol compliance
- Pin Management Dashboard with bulk operations
- Backend health monitoring and metrics

## Usage

The server is configured in VS Code and Cline through their respective configuration files:
- VS Code: `.vscode/settings.json`
- Cline: `.config/Code - Insiders/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`

Start the server using the CLI:
```bash
ipfs-kit mcp start
```

Access the dashboard at: `http://localhost:8004/pins`

## Available Tools

### Core IPFS Operations
- `ipfs_add` - Add content to IPFS
- `ipfs_cat` - Retrieve content from IPFS
- `ipfs_pin_add` - Pin content to prevent garbage collection
- `ipfs_pin_rm` - Remove pin from content
- `ipfs_pin_ls` - List pins by type
- `ipfs_pin_update` - Update a pin to a new CID
- `ipfs_version` - Get IPFS daemon version
- `ipfs_id` - Get IPFS node identity

### Pin Management Tools (for Dashboard)
- `list_pins` - List all pins with enhanced metadata
- `get_pin_stats` - Get statistics about pins (total, by type, by backend)
- `get_pin_metadata` - Get detailed metadata for a specific pin
- `unpin_content` - Unpin content (wrapper for ipfs_pin_rm)
- `bulk_unpin` - Bulk unpin multiple CIDs
- `export_pins` - Export pins to JSON or CSV format

### System Tools
- `system_health` - Get system health status
- `get_backend_status` - Get backend health information
- `list_backends` - List all storage backends

## Pin Management Dashboard

The Pin Management Dashboard (`/pins`) provides a comprehensive UI for managing IPFS pins:

### Features
- **View Pins**: Browse all pinned content with metadata
- **Search & Filter**: Search by CID, name, or tags; filter by type and backend
- **Sort**: Sort pins by date, CID, size, or type
- **Bulk Operations**: Select multiple pins and unpin in bulk
- **Export**: Export pin lists to JSON or CSV formats
- **Statistics**: View pin statistics by type and backend
- **Metadata**: View detailed metadata for each pin

### API Endpoints

All pin management tools are accessible via the MCP JSON-RPC endpoint:

```bash
POST /mcp/tools/call
{
  "method": "tools/call",
  "params": {
    "name": "list_pins",
    "arguments": {
      "type": "all",
      "include_metadata": true
    }
  },
  "id": 1
}
```

See the tools documentation for parameter details.
