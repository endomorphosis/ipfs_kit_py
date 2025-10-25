# Pin Management Dashboard User Guide

## Introduction

The Pin Management Dashboard provides a comprehensive web interface for managing your IPFS pins. It allows you to view, filter, sort, export, and perform bulk operations on your pinned content.

## Accessing the Dashboard

1. Start the IPFS Kit MCP server:
   ```bash
   ipfs-kit mcp start
   ```

2. Open your browser and navigate to:
   ```
   http://localhost:8004/pins
   ```

## Dashboard Features

### Overview Statistics

At the top of the dashboard, you'll see key statistics:
- **Total Pins**: Total number of pinned items
- **Recursive**: Number of recursive pins
- **Direct**: Number of direct pins
- **Storage Backends**: Number of storage backends in use

### Search and Filter

The dashboard provides powerful search and filtering capabilities:

**Search Box**
- Search by CID, name, or tags
- Real-time filtering as you type
- Case-insensitive search

**Filter Dropdowns**
- **All Types**: Filter by pin type (recursive, direct, indirect)
- **All Backends**: Filter by storage backend (ipfs, ipfs-cluster, storacha)
- **Sort By**: Sort pins by date, CID, size, or type

Click **Apply Filters** to apply your selections, or **Reset** to clear all filters.

### Pin List

The main table shows all pins matching your filters:

| Column | Description |
|--------|-------------|
| Checkbox | Select pins for bulk operations |
| CID | Content Identifier (clickable to view details) |
| Type | Pin type (recursive, direct, indirect) |
| Size | Content size in human-readable format |
| Backend | Storage backend where the pin is stored |
| Tags | Custom tags associated with the pin |
| Created | Date when the pin was created |
| Actions | Quick actions (View, Unpin) |

### Operations

#### Viewing Pin Details

1. Click the **View** button next to any pin
2. A modal will open showing detailed metadata:
   - CID and pin type
   - Size and status
   - Backend and replication count
   - Tags, name, and description
   - Technical details (block size, data size, number of links)

#### Unpinning a Single Pin

1. Click the **Unpin** button next to the pin you want to remove
2. Confirm the action in the dialog
3. The pin will be removed from IPFS

#### Bulk Operations

Select multiple pins for bulk operations:

1. **Select Pins**: Click the checkboxes next to pins you want to manage
2. **Select All**: Click the "☑️ Select All" button to select all visible pins
3. **Deselect All**: Click the "☐ Deselect All" button to clear selections
4. **Bulk Unpin**: Click the "🗑️ Bulk Unpin" button to remove all selected pins

The bulk actions bar will appear at the top of the pin list showing how many pins are selected.

#### Exporting Pins

Export your pin list to a file:

1. **JSON Export**: Click "📥 Export JSON" to download pins as JSON
2. **CSV Export**: Click "📥 Export CSV" to download pins as CSV

The export includes:
- CID
- Pin type
- Size
- Status
- Created date
- Backend
- Tags

### Refresh Data

Click the **🔄 Refresh** button to reload the pin list and statistics from the IPFS daemon.

### Pagination

When you have many pins:
- Navigate between pages using **Previous** and **Next** buttons
- Current page and total pages are shown in the center
- Default: 20 pins per page

## Use Cases

### Finding Specific Content

1. Use the search box to find pins by CID or tags
2. Filter by type to see only recursive or direct pins
3. Sort by date to find recently pinned content

### Cleaning Up Unused Pins

1. Sort by date to see oldest pins
2. Filter by backend to focus on specific storage
3. Select multiple old pins
4. Use bulk unpin to remove them

### Exporting Pin Inventory

1. Apply filters to get the pins you want
2. Click "Export JSON" or "Export CSV"
3. Use the exported data for backups or analysis

### Managing Large Pin Sets

1. Use filters to narrow down pins by type or backend
2. Use "Select All" to select all filtered pins
3. Perform bulk operations on the selection

## Tips and Best Practices

### Performance
- The dashboard shows 20 pins per page by default for optimal performance
- Use filters to reduce the number of displayed pins
- Refresh data periodically to see latest changes

### Safety
- Always verify pin selections before bulk unpinning
- Use the View button to check pin details before removing
- Export pins before performing bulk deletions for backup

### Organization
- Use consistent naming in the search function
- Filter by backend to manage pins on specific storage systems
- Export regularly to maintain an inventory

## Troubleshooting

### Dashboard Not Loading
- Ensure the MCP server is running (`ipfs-kit mcp start`)
- Check that port 8004 is not blocked by firewall
- Try accessing via `http://127.0.0.1:8004/pins` instead

### No Pins Showing
- Verify IPFS daemon is running (`ipfs daemon`)
- Check browser console for errors (F12)
- Click Refresh to reload pin data

### Bulk Operations Not Working
- Ensure pins are selected (checkboxes checked)
- Check IPFS daemon is running
- Look for error notifications in the top-right corner

### Export Not Downloading
- Check browser download settings
- Ensure pop-ups are not blocked
- Try a different browser

## Technical Details

The Pin Management Dashboard uses:
- **MCP SDK**: JavaScript SDK for calling MCP server tools
- **JSON-RPC**: Protocol for tool communication
- **IPFS API**: Direct integration with IPFS daemon
- **Real-time Updates**: Immediate feedback on operations

All operations are performed through the MCP server's pin management tools:
- `list_pins` - Fetches pin data
- `get_pin_stats` - Retrieves statistics
- `get_pin_metadata` - Gets detailed pin information
- `unpin_content` - Removes single pins
- `bulk_unpin` - Removes multiple pins
- `export_pins` - Exports pin data

## Getting Help

For more information:
- API Documentation: See `PIN_MANAGEMENT_API.md`
- MCP Server README: See `/mcp/README.md`
- GitHub Issues: Report problems or request features

## Future Features

Planned enhancements for the Pin Management Dashboard:
- Pin tagging and organization
- Scheduled pin operations
- Pin health monitoring
- Cross-backend pin replication
- Advanced search with regex support
- Pin activity timeline
