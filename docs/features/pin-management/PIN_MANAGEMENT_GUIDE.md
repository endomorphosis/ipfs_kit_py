# Pin Management Dashboard - Implementation Guide

## Overview

The Pin Management Dashboard provides comprehensive tools for managing IPFS pins through the MCP (Model Context Protocol) server. This implementation connects the dashboard UI to backend MCP tools for real-time pin management.

## Architecture

```
┌─────────────────────────────────────────────┐
│  Pin Management Dashboard (HTML/JS)         │
│  - UI Controls & Filters                    │
│  - Table Display                            │
│  - Bulk Operations                          │
└──────────────┬──────────────────────────────┘
               │ Uses MCP SDK
               ▼
┌─────────────────────────────────────────────┐
│  MCP SDK (JavaScript)                       │
│  - JSON-RPC Client                          │
│  - Tool Invocation                          │
└──────────────┬──────────────────────────────┘
               │ HTTP/JSON-RPC
               ▼
┌─────────────────────────────────────────────┐
│  Enhanced Unified MCP Server (Python)       │
│  - Route: /mcp/tools/call                   │
│  - Route: /api/call_mcp_tool               │
│  - Route: /pins (Dashboard)                │
└──────────────┬──────────────────────────────┘
               │ Calls MCP Tools
               ▼
┌─────────────────────────────────────────────┐
│  Pin Management MCP Tools                   │
│  - list_pins                                │
│  - pin_content                              │
│  - unpin_content                            │
│  - bulk_unpin                               │
│  - get_pin_metadata                         │
│  - export_pins                              │
│  - get_pin_stats                            │
└──────────────┬──────────────────────────────┘
               │ Integrates with
               ▼
┌─────────────────────────────────────────────┐
│  IPFS Model / Simulation Layer              │
│  - Real IPFS integration (when available)   │
│  - Simulated pins (for testing)             │
└─────────────────────────────────────────────┘
```

## MCP Tools Implemented

### 1. `list_pins`
Lists all pinned content with metadata and filtering options.

**Parameters:**
- `type` (string, optional): Filter by pin type ("all", "recursive", "direct", "indirect")
- `cid` (string, optional): Filter by specific CID

**Returns:**
```json
{
  "success": true,
  "pins": [
    {
      "cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
      "type": "recursive",
      "size": "25 MB",
      "status": "pinned",
      "created": "2025-01-15T10:30:00Z",
      "metadata": {
        "backend": "ipfs",
        "replication_count": 1,
        "tags": ["dataset", "public"],
        "name": "Sample Pin 1",
        "description": "This is a sample pin"
      }
    }
  ],
  "total": 5,
  "filter": {
    "type": "all",
    "cid": null
  }
}
```

### 2. `pin_content`
Pins new content to IPFS.

**Parameters:**
- `cid` (string, required): Content identifier to pin
- `recursive` (boolean, optional): Pin recursively (default: true)

**Returns:**
```json
{
  "success": true,
  "cid": "QmTestCID123456789",
  "pinned": true,
  "recursive": true,
  "message": "Successfully pinned QmTestCID123456789"
}
```

### 3. `unpin_content`
Unpins content from IPFS.

**Parameters:**
- `cid` (string, required): Content identifier to unpin
- `recursive` (boolean, optional): Unpin recursively (default: true)

**Returns:**
```json
{
  "success": true,
  "cid": "QmTestCID123456789",
  "unpinned": true,
  "message": "Successfully unpinned QmTestCID123456789"
}
```

### 4. `bulk_unpin`
Unpins multiple CIDs in a single operation.

**Parameters:**
- `cids` (array of strings, required): List of CIDs to unpin

**Returns:**
```json
{
  "success": true,
  "total": 3,
  "success_count": 3,
  "error_count": 0,
  "results": [
    {
      "cid": "QmBulk1",
      "success": true,
      "error": null
    }
  ]
}
```

### 5. `get_pin_metadata`
Gets detailed metadata for a specific pin.

**Parameters:**
- `cid` (string, required): Content identifier

**Returns:**
```json
{
  "success": true,
  "cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
  "metadata": {
    "cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
    "type": "recursive",
    "size": "25 MB",
    "status": "pinned",
    "created": "2025-01-15T10:30:00Z",
    "metadata": {
      "backend": "ipfs",
      "replication_count": 1,
      "tags": ["dataset", "public"]
    }
  }
}
```

### 6. `export_pins`
Exports pins in various formats.

**Parameters:**
- `format` (string, optional): Export format ("json" or "csv", default: "json")
- `filter_type` (string, optional): Filter by pin type before export

**Returns (JSON format):**
```json
{
  "success": true,
  "format": "json",
  "data": "[{\"cid\":\"Qm...\",\"type\":\"recursive\",...}]",
  "count": 5
}
```

**Returns (CSV format):**
```json
{
  "success": true,
  "format": "csv",
  "data": "cid,type,size,status,created,backend,tags\nQm...,recursive,25 MB,pinned,...",
  "count": 5
}
```

### 7. `get_pin_stats`
Gets comprehensive statistics about all pins.

**Returns:**
```json
{
  "success": true,
  "stats": {
    "total_pins": 5,
    "by_type": {
      "recursive": 4,
      "direct": 1
    },
    "by_backend": {
      "ipfs": 3,
      "ipfs-cluster": 2
    },
    "by_status": {
      "pinned": 5
    },
    "tags": {
      "dataset": 3,
      "model": 1,
      "backup": 2
    }
  }
}
```

## Dashboard Features

### Comprehensive Pin Management Dashboard (`/pins`)

A full-featured standalone dashboard with:

1. **Statistics Overview**
   - Total pins count
   - Breakdown by type (recursive, direct)
   - Number of storage backends in use

2. **Search & Filtering**
   - Search by CID, name, or tags
   - Filter by pin type
   - Filter by backend
   - Sort by date, CID, size, or type

3. **Bulk Operations**
   - Select individual pins
   - Select all / Deselect all
   - Bulk unpin selected pins
   - Track operation progress

4. **Export Functionality**
   - Export to JSON format
   - Export to CSV format
   - Filtered exports based on current filters

5. **Pin Details Modal**
   - View complete metadata
   - See replication status
   - View tags and descriptions
   - Unpin from modal

6. **Real-time Updates**
   - Refresh button to reload pins
   - Automatic loading via MCP SDK
   - Error handling with fallback

### Unified Comprehensive Dashboard Integration

The main dashboard at `/` includes a Pins tab with:

- Pin listing table
- Individual pin actions (View, Unpin)
- MCP SDK integration with fallback to direct API
- Real-time data loading

## Usage Examples

### JavaScript (Dashboard)

```javascript
// Initialize MCP client
const mcpClient = new MCPClient({ debug: true });

// List all pins
const result = await mcpClient.callTool('list_pins', {});
console.log('Total pins:', result.total);

// Filter by type
const recursivePins = await mcpClient.callTool('list_pins', { 
  type: 'recursive' 
});

// Pin new content
const pinResult = await mcpClient.callTool('pin_content', { 
  cid: 'QmNewContent123',
  recursive: true
});

// Unpin content
const unpinResult = await mcpClient.callTool('unpin_content', { 
  cid: 'QmOldContent456'
});

// Bulk unpin
const bulkResult = await mcpClient.callTool('bulk_unpin', { 
  cids: ['Qm1', 'Qm2', 'Qm3']
});

// Get statistics
const stats = await mcpClient.callTool('get_pin_stats', {});
console.log('Stats:', stats.stats);

// Export to CSV
const exportResult = await mcpClient.callTool('export_pins', { 
  format: 'csv' 
});
// Create download link
const blob = new Blob([exportResult.data], { type: 'text/csv' });
const url = URL.createObjectURL(blob);
```

### Python (MCP Server)

```python
# In MCP server or tools
from ipfs_kit_py.mcp.enhanced_unified_mcp_server import EnhancedUnifiedMCPServer

server = EnhancedUnifiedMCPServer()

# List pins
result = await server._list_pins(pin_type="all")

# Pin content
result = await server._pin_content("QmTestCID", recursive=True)

# Get stats
stats = await server._get_pin_stats()
```

### REST API (Direct HTTP)

```bash
# List pins via MCP JSON-RPC
curl -X POST http://localhost:8765/mcp/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "list_pins",
      "arguments": {}
    },
    "id": 1
  }'

# Pin content
curl -X POST http://localhost:8765/mcp/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "pin_content",
      "arguments": {
        "cid": "QmTestCID123",
        "recursive": true
      }
    },
    "id": 2
  }'

# Export pins
curl -X POST http://localhost:8765/mcp/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "export_pins",
      "arguments": {
        "format": "csv"
      }
    },
    "id": 3
  }'
```

## Data Flow

### Pin Listing Flow
1. User opens `/pins` dashboard
2. JavaScript `loadPins()` function executes
3. MCP SDK calls `list_pins` tool via `/mcp/tools/call`
4. Server's `handle_mcp_request()` routes to `_list_pins()`
5. `_list_pins()` attempts to connect to IPFS model
6. If unavailable, returns simulated pin data
7. Results sent back to dashboard
8. Dashboard updates table with pin data

### Pin Operation Flow (Unpin Example)
1. User clicks "Unpin" button
2. Confirmation dialog appears
3. JavaScript `unpinContent()` executes
4. MCP SDK calls `unpin_content` tool
5. Server routes to `_unpin_content()`
6. IPFS model removes pin (or simulates)
7. Success/error response returned
8. Dashboard shows notification
9. Pin list automatically refreshes

## Configuration

### Server Configuration
The MCP server automatically:
- Mounts static files from multiple possible locations
- Serves templates from `mcp/templates/`
- Exposes pin management endpoints
- Handles JSON-RPC and direct API calls

### Template Locations
Templates are loaded from:
- `ipfs_kit_py/mcp/dashboard_templates/` (source)
- `mcp/templates/` (runtime)

### Static Files
MCP SDK and other static assets loaded from:
- `mcp/dashboard/static/`
- `ipfs_kit_py/mcp/dashboard/static/`
- `static/`

## Testing

### Manual Testing
1. Start MCP server: `python3 mcp/enhanced_unified_mcp_server.py`
2. Open browser to `http://localhost:8765/pins`
3. Verify pins are listed
4. Test filtering and sorting
5. Test bulk operations
6. Test export functionality

### Simulated Data
When IPFS is not available, the server automatically generates simulated pins for testing:
- 5 sample pins with realistic CIDs
- Random types, sizes, and backends
- Sample tags and metadata
- Realistic creation dates

## Troubleshooting

### Issue: No pins displayed
**Solution:** 
- Check browser console for MCP SDK errors
- Verify MCP server is running
- Check `/api/health` endpoint responds
- Review server logs for errors

### Issue: MCP SDK not found
**Solution:**
- Verify static files are mounted correctly
- Check `/static/mcp-sdk.js` is accessible
- Review server startup logs for static mount errors

### Issue: Bulk operations fail
**Solution:**
- Check browser console for specific errors
- Verify CIDs are valid
- Check MCP tool responses in Network tab
- Review server error logs

## Future Enhancements

Planned improvements (Phases 2-5):
- Enhanced metadata editing
- Pin verification and health checks
- Replication management across backends
- Advanced filtering (date ranges, size ranges)
- Pin grouping and organization
- Batch import from files
- Pin migration tools
- Analytics and usage reports

## Files Modified

1. **mcp/enhanced_unified_mcp_server.py**
   - Added 7 pin management MCP tools
   - Added `/pins` route for standalone dashboard
   - Added `/mcp/tools/call` JSON-RPC endpoint
   - Added static files mounting
   - Enhanced `_list_pins()` with IPFS integration

2. **ipfs_kit_py/mcp/dashboard_templates/unified_comprehensive_dashboard.html**
   - Added MCP SDK script inclusion
   - Updated `loadPins()` to use MCP tools
   - Added `unpinContent()` using MCP SDK
   - Added `viewPin()` for metadata display
   - Added fallback to direct API

3. **ipfs_kit_py/mcp/dashboard_templates/comprehensive_pin_management.html** (NEW)
   - Full-featured standalone pin management UI
   - Complete statistics dashboard
   - Advanced filtering and sorting
   - Bulk operations support
   - Export functionality
   - Pin details modal
   - Responsive design

## Summary

This implementation provides a complete, production-ready pin management solution that:
- ✅ Connects UI to backend MCP tools
- ✅ Supports real IPFS integration with graceful fallback
- ✅ Provides comprehensive pin operations (list, pin, unpin, bulk, export, stats)
- ✅ Includes full-featured standalone dashboard
- ✅ Follows MCP JSON-RPC protocol standards
- ✅ Handles errors gracefully
- ✅ Supports multiple export formats
- ✅ Provides detailed metadata and statistics
