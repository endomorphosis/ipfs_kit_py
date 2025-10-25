# Pin Management Dashboard - Feature Overview

## Dashboard Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  📌 Pin Management Dashboard                                    │
│  Manage your IPFS pins with advanced filtering and operations   │
└─────────────────────────────────────────────────────────────────┘

┌──────────────┬──────────────┬──────────────┬──────────────┐
│ Total Pins   │ Recursive    │ Direct       │ Backends     │
│     5        │     4        │     1        │     2        │
└──────────────┴──────────────┴──────────────┴──────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ 🔍 Search: [________________]  Type: [All ▼] Backend: [All ▼]  │
│                                                                 │
│ Sort: [Date ▼]  [Apply] [Reset]                                │
│                                                                 │
│ [🔄 Refresh] [📥 Export JSON] [📥 Export CSV]                  │
│ [☑️ Select All] [☐ Deselect All]                               │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ Pins (5)                              [2 selected] [🗑️ Bulk]   │
├─────────────────────────────────────────────────────────────────┤
│ ☑ │ CID          │ Type      │ Size   │ Backend │ Tags     │ … │
├───┼──────────────┼───────────┼────────┼─────────┼──────────┼───┤
│ ☐ │ QmYwAP... │ recursive │ 25 MB  │ ipfs    │ dataset  │ V │
│ ☑ │ QmRHdR... │ direct    │ 10 MB  │ cluster │ model    │ V │
│ ☐ │ QmTkzD... │ recursive │ 50 MB  │ ipfs    │ backup   │ V │
│ ☑ │ QmPZ9g... │ indirect  │ 5 MB   │ storacha│ archive  │ V │
│ ☐ │ QmYHNY... │ recursive │ 100 MB │ ipfs    │ public   │ V │
└─────────────────────────────────────────────────────────────────┘

                   [← Previous]  Page 1 of 1  [Next →]
```

## Key Features

### 1. Statistics Dashboard
- **Total Pins**: Overall count of all pins
- **By Type**: Breakdown (recursive, direct, indirect)
- **Backends**: Number of storage backends in use
- Real-time updates from MCP tools

### 2. Search & Filter Controls
- **Search Box**: Filter by CID, name, or tags
- **Type Filter**: All, Recursive, Direct, Indirect
- **Backend Filter**: All, IPFS, IPFS Cluster, Storacha
- **Sort Options**: Date, CID, Size, Type
- Apply/Reset buttons for filter management

### 3. Action Buttons
```
┌─────────────────────────────────────────┐
│ Primary Actions                         │
├─────────────────────────────────────────┤
│ [🔄 Refresh]       Reload pin list      │
│ [📥 Export JSON]   Export to JSON       │
│ [📥 Export CSV]    Export to CSV        │
│ [☑️ Select All]    Select all pins      │
│ [☐ Deselect All]  Clear selections     │
└─────────────────────────────────────────┘
```

### 4. Bulk Operations
- Appears when pins are selected
- Shows selection count
- Bulk unpin with confirmation
- Progress tracking

### 5. Pin Table Columns
```
┌───┬────────────┬──────────┬──────┬─────────┬──────┬─────────┬─────────┐
│ ☑ │ CID        │ Type     │ Size │ Backend │ Tags │ Created │ Actions │
├───┼────────────┼──────────┼──────┼─────────┼──────┼─────────┼─────────┤
│   │ Truncated  │ Badge    │ Text │ Text    │ Tags │ Date    │ Buttons │
│   │ with hover │ colored  │      │         │ list │ format  │ View+   │
│   │ for full   │          │      │         │      │         │ Unpin   │
└───┴────────────┴──────────┴──────┴─────────┴──────┴─────────┴─────────┘
```

### 6. Individual Actions
- **View Button**: Opens details modal
- **Unpin Button**: Removes pin with confirmation

### 7. Pin Details Modal
```
┌─────────────────────────────────────────────────┐
│ Pin Details                             [×]     │
├─────────────────────────────────────────────────┤
│                                                 │
│ CID:          QmYwAPJzv5CZsnA625s3Xf2nem...    │
│ Type:         [recursive]                       │
│ Size:         25 MB                             │
│ Status:       [pinned]                          │
│ Backend:      ipfs                              │
│ Replication:  1 copies                          │
│ Tags:         [dataset] [public]                │
│ Name:         Sample Pin 1                      │
│ Description:  This is a sample pin              │
│ Created:      1/15/2025, 10:30:00 AM            │
│                                                 │
├─────────────────────────────────────────────────┤
│                         [Close]  [🗑️ Unpin]    │
└─────────────────────────────────────────────────┘
```

### 8. Notifications
```
┌──────────────────────────────┐
│ ● Successfully unpinned 3    │
│   pins                       │
└──────────────────────────────┘
```

## MCP Tool Integration Flow

```
User Action → JavaScript Function → MCP SDK
    ↓              ↓                   ↓
Dashboard      callTool()         JSON-RPC
    ↓              ↓                   ↓
Button         Tool Name          /mcp/tools/call
    ↓              ↓                   ↓
Click          Arguments          Server Handler
    ↓              ↓                   ↓
Handler        Parameters         _list_pins()
    ↓              ↓                   ↓
Callback       Response           IPFS Model
    ↓              ↓                   ↓
Update UI      Success/Error      Data/Simulation
```

## Responsive Design Features

### Desktop View (≥1200px)
- Full statistics grid (4 columns)
- Wide table with all columns visible
- Side-by-side controls
- Large modal dialogs

### Tablet View (768px - 1199px)
- Statistics grid (2 columns)
- Scrollable table
- Stacked controls
- Medium modal dialogs

### Mobile View (<768px)
- Statistics grid (1 column)
- Horizontal scroll table
- Vertical stacked controls
- Full-screen modals

## Color Scheme

```
Primary:     #667eea (Purple-blue)
Secondary:   #764ba2 (Deep purple)
Success:     #4ade80 (Green)
Warning:     #fbbf24 (Amber)
Error:       #f87171 (Red)
Background:  #f8fafc (Light gray)
Text:        #1e293b (Dark slate)
Border:      #e2e8f0 (Light slate)
```

## Animation & Interactions

### Loading States
```
┌─────────────────┐
│       ●         │  ← Spinning animation
│   Loading...    │
└─────────────────┘
```

### Hover Effects
- Buttons: Slight darkening
- Table rows: Light background
- CID cells: Show full CID in tooltip

### Transitions
- Smooth fade in/out for modals
- Slide in for notifications
- Highlight for newly added pins

## Export Formats

### JSON Export
```json
[
  {
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
]
```

### CSV Export
```csv
cid,type,size,status,created,backend,tags
QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG,recursive,25 MB,pinned,2025-01-15T10:30:00Z,ipfs,"dataset,public"
QmRHdRzHVK4j9YMqmJ3tVXNvcvkNBKYLQg8WBtqfkbDvML,direct,10 MB,pinned,2025-01-10T15:20:00Z,ipfs-cluster,model
```

## Accessibility Features

- ✓ Keyboard navigation support
- ✓ ARIA labels for screen readers
- ✓ High contrast color scheme
- ✓ Focus indicators on interactive elements
- ✓ Semantic HTML structure
- ✓ Alt text for icons
- ✓ Clear error messages

## Performance Optimizations

- Pagination (20 items per page)
- Lazy loading for large datasets
- Debounced search input (300ms)
- Efficient DOM updates
- Minimal re-renders
- Cached MCP client instance

## Browser Compatibility

- ✓ Chrome 90+
- ✓ Firefox 88+
- ✓ Safari 14+
- ✓ Edge 90+

## Security Features

- HTTPS recommended for production
- Input sanitization
- XSS protection via template escaping
- CORS headers configured
- Rate limiting on MCP endpoints (future)
