# Pin Management Tools API Documentation

## Overview

The Pin Management Tools provide enhanced pin management capabilities for the IPFS Kit MCP server. These tools are designed to work with the Pin Management Dashboard and provide comprehensive pin listing, metadata retrieval, bulk operations, and export functionality.

## Tools

### list_pins

List all pinned content with enhanced metadata.

**Parameters:**
- `type` (string, optional): Type of pins to list. Options: "all", "direct", "indirect", "recursive". Default: "all"
- `include_metadata` (boolean, optional): Include additional metadata for each pin. Default: true

**Returns:**
```json
{
  "success": true,
  "pins": [
    {
      "cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
      "type": "recursive",
      "created": "2025-10-03T06:00:00.000Z",
      "size": "1.5 MB",
      "metadata": {
        "backend": "ipfs",
        "tags": [],
        "replication_count": 1,
        "name": "",
        "description": "",
        "size_bytes": 1572864,
        "num_links": 5
      }
    }
  ],
  "total_count": 1
}
```

**Example Usage:**
```javascript
const result = await mcpClient.callTool('list_pins', {
  type: 'recursive',
  include_metadata: true
});
```

---

### get_pin_stats

Get statistics about pinned content.

**Parameters:** None

**Returns:**
```json
{
  "success": true,
  "stats": {
    "total_pins": 25,
    "by_type": {
      "recursive": 20,
      "direct": 5,
      "indirect": 0
    },
    "by_backend": {
      "ipfs": 25
    }
  }
}
```

**Example Usage:**
```javascript
const result = await mcpClient.callTool('get_pin_stats', {});
```

---

### get_pin_metadata

Get detailed metadata for a specific pin.

**Parameters:**
- `cid` (string, required): Content identifier to get metadata for

**Returns:**
```json
{
  "success": true,
  "metadata": {
    "cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
    "type": "recursive",
    "created": "2025-10-03T06:00:00.000Z",
    "size": "1.5 MB",
    "status": "pinned",
    "metadata": {
      "backend": "ipfs",
      "tags": [],
      "replication_count": 1,
      "name": "",
      "description": "",
      "size_bytes": 1572864,
      "num_links": 5,
      "block_size": 262144,
      "data_size": 1310720
    }
  }
}
```

**Example Usage:**
```javascript
const result = await mcpClient.callTool('get_pin_metadata', {
  cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG'
});
```

---

### unpin_content

Unpin content from IPFS (remove pin).

**Parameters:**
- `cid` (string, required): Content identifier to unpin
- `recursive` (boolean, optional): Recursively unpin the object. Default: true

**Returns:**
```json
{
  "success": true,
  "pins": ["QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"]
}
```

**Example Usage:**
```javascript
const result = await mcpClient.callTool('unpin_content', {
  cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG',
  recursive: true
});
```

---

### bulk_unpin

Unpin multiple CIDs in bulk.

**Parameters:**
- `cids` (array of strings, required): List of CIDs to unpin
- `recursive` (boolean, optional): Recursively unpin the objects. Default: true

**Returns:**
```json
{
  "success": true,
  "total": 3,
  "success_count": 2,
  "error_count": 1,
  "errors": [
    {
      "cid": "QmBadCid123",
      "error": "Pin not found"
    }
  ]
}
```

**Example Usage:**
```javascript
const result = await mcpClient.callTool('bulk_unpin', {
  cids: [
    'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG',
    'QmRHdRzHVK4j9YMqmJ3tVXNvcvkNBKYLQg8WBtqfkbDvML'
  ],
  recursive: true
});
```

---

### export_pins

Export pins to JSON or CSV format.

**Parameters:**
- `format` (string, required): Export format. Options: "json", "csv"
- `filter_type` (string, optional): Filter by pin type before export

**Returns:**
```json
{
  "success": true,
  "data": "[{\"cid\":\"Qm...\",\"type\":\"recursive\",...}]",
  "count": 25
}
```

**Example Usage:**
```javascript
// Export as JSON
const jsonResult = await mcpClient.callTool('export_pins', {
  format: 'json',
  filter_type: 'recursive'
});

// Export as CSV
const csvResult = await mcpClient.callTool('export_pins', {
  format: 'csv'
});
```

---

## Integration with MCP Server

All pin management tools are registered with the MCP server and accessible via the JSON-RPC endpoint:

```bash
POST http://localhost:8004/mcp/tools/call
Content-Type: application/json

{
  "jsonrpc": "2.0",
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

## Dashboard Integration

The Pin Management Dashboard (`/pins`) uses these tools via the MCP SDK to provide:

1. **Pin Listing**: Displays all pins with metadata using `list_pins`
2. **Statistics**: Shows pin statistics using `get_pin_stats`
3. **Pin Details**: Shows detailed metadata using `get_pin_metadata`
4. **Unpin Operations**: Removes single pins using `unpin_content`
5. **Bulk Operations**: Removes multiple pins using `bulk_unpin`
6. **Export**: Exports pin data using `export_pins`

## Error Handling

All tools follow a consistent error handling pattern:

**Success Response:**
```json
{
  "success": true,
  "...": "tool-specific data"
}
```

**Error Response:**
```json
{
  "success": false,
  "error": "Error message describing what went wrong"
}
```

## Dependencies

The pin management tools depend on:
- IPFS daemon running (for real pin operations)
- Core IPFS tools (ipfs_pin_ls, ipfs_pin_rm, etc.)
- MCP server infrastructure

## Fallback Behavior

When the IPFS daemon is not available or errors occur:
- `list_pins` returns simulated pin data for testing
- Other tools return appropriate error messages
- The dashboard can still be accessed to view the UI structure

## Future Enhancements

Planned improvements for pin management tools:
- Support for IPFS Cluster pins
- Pin tagging and organization
- Scheduled pin operations
- Pin replication across backends
- Advanced filtering and search
