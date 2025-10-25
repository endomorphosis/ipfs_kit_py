# Pin Management Dashboard - Quick Start Guide

## Getting Started

### 1. Start the MCP Server

```bash
cd /path/to/ipfs_kit_py
python3 -m ipfs_kit_py.mcp.enhanced_unified_mcp_server --host 127.0.0.1 --port 8765
```

Or if you have the CLI installed:
```bash
ipfs-kit mcp start
```

### 2. Access the Dashboard

Open your browser and navigate to:
- **Comprehensive Pin Management**: http://localhost:8765/pins
- **Main Dashboard (with Pins tab)**: http://localhost:8765/

## Quick Actions

### View All Pins
1. Open http://localhost:8765/pins
2. Pins are automatically loaded via MCP tools
3. Statistics are shown at the top

### Search for Pins
1. Use the search box to find pins by CID, name, or tags
2. Results update as you type (300ms debounce)

### Filter Pins
1. Select pin type from dropdown (All, Recursive, Direct, Indirect)
2. Select backend from dropdown (All, IPFS, IPFS Cluster, Storacha)
3. Choose sort order (Date, CID, Size, Type)
4. Click "Apply Filters"

### Unpin Single Item
1. Locate the pin in the table
2. Click the "Unpin" button in the Actions column
3. Confirm the action in the dialog

### Unpin Multiple Items
1. Check the boxes next to pins you want to remove
2. The bulk actions bar appears showing selection count
3. Click "🗑️ Bulk Unpin"
4. Confirm the action
5. Progress is shown for each pin

### Export Pins
1. Click "📥 Export JSON" or "📥 Export CSV"
2. File downloads automatically
3. Filename includes timestamp: `pins_export_[timestamp].[format]`

### View Pin Details
1. Click "View" button for any pin
2. Modal opens with complete metadata
3. Can unpin directly from modal

## Keyboard Shortcuts

- `Ctrl/Cmd + R`: Refresh pins
- `Escape`: Close modal
- `Tab`: Navigate between form elements

## Understanding Pin Types

- **Recursive**: Pin includes all referenced content (most common)
- **Direct**: Only the immediate content is pinned
- **Indirect**: Content is pinned because it's referenced by a recursive pin

## Understanding Backends

- **IPFS**: Local IPFS node
- **IPFS Cluster**: Distributed IPFS cluster
- **Storacha**: Cloud pinning service

## Statistics Explained

### Total Pins
Total number of pins across all backends

### Recursive/Direct Count
Breakdown by pin type

### Storage Backends
Number of different backends currently storing pins

## MCP Tool Reference

All dashboard operations use these MCP tools:

| Tool | Purpose | Usage |
|------|---------|-------|
| `list_pins` | Get all pins | Automatic on load |
| `pin_content` | Pin new CID | Future feature |
| `unpin_content` | Remove pin | Via Unpin button |
| `bulk_unpin` | Remove multiple | Via Bulk Unpin |
| `get_pin_metadata` | View details | Via View button |
| `export_pins` | Download data | Via Export buttons |
| `get_pin_stats` | Get statistics | Automatic on load |

## Troubleshooting

### "No pins found"
- Check if IPFS is running
- Verify MCP server is connected to IPFS
- Dashboard will show simulated pins if IPFS unavailable

### "Failed to load pins"
- Open browser console (F12)
- Check for JavaScript errors
- Verify MCP server is running: http://localhost:8765/api/health

### Export not working
- Check browser console
- Ensure popup blockers allow downloads
- Verify MCP tools are responding

### Bulk operations slow
- Normal for large selections
- Each pin is unpinned individually
- Progress shown in results

## Best Practices

1. **Regular Exports**: Export pin list periodically for backup
2. **Tag Your Pins**: Use meaningful tags in metadata
3. **Filter Before Bulk Operations**: Use filters to select specific groups
4. **Monitor Statistics**: Track backend distribution and pin types
5. **Verify Before Unpinning**: Always check pin details before removing

## API Integration Examples

### JavaScript
```javascript
// Initialize client
const mcpClient = new MCPClient({ debug: true });

// List pins
const pins = await mcpClient.callTool('list_pins', {});

// Unpin content
await mcpClient.callTool('unpin_content', { cid: 'QmXXX' });

// Export to JSON
const data = await mcpClient.callTool('export_pins', { format: 'json' });
```

### cURL
```bash
# List pins
curl -X POST http://localhost:8765/mcp/tools/call \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"list_pins","arguments":{}},"id":1}'

# Get statistics
curl -X POST http://localhost:8765/mcp/tools/call \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"get_pin_stats","arguments":{}},"id":2}'
```

## Advanced Features (Coming Soon)

Phase 2-5 will add:
- [ ] Pin content directly from dashboard
- [ ] Edit pin metadata (tags, descriptions)
- [ ] Pin verification and health checks
- [ ] Advanced date range filtering
- [ ] Pin migration between backends
- [ ] Replication management
- [ ] Pin grouping and organization
- [ ] Analytics and usage reports

## Support

For issues or feature requests:
1. Check the comprehensive documentation in `docs/PIN_MANAGEMENT_GUIDE.md`
2. Review feature details in `docs/PIN_DASHBOARD_FEATURES.md`
3. Open an issue on GitHub

## Version

Current implementation: **Phase 1 Complete**
- ✅ MCP tool integration
- ✅ Basic CRUD operations
- ✅ Filtering and sorting
- ✅ Bulk operations
- ✅ Export functionality
- ✅ Statistics dashboard

Last updated: 2025-01-03
