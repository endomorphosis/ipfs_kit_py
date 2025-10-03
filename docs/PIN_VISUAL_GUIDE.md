# Pin Management Dashboard - Visual Overview

## Main Dashboard Screenshot (Mockup)

```
╔═════════════════════════════════════════════════════════════════════════════╗
║  📌 Pin Management Dashboard                                                ║
║  Manage your IPFS pins with advanced filtering, bulk operations, and export ║
╚═════════════════════════════════════════════════════════════════════════════╝

┌──────────────┬──────────────┬──────────────┬──────────────┐
│ Total Pins   │ Recursive    │ Direct       │ Backends     │
│     5        │     4        │     1        │     2        │
└──────────────┴──────────────┴──────────────┴──────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ 🔍 [Search by CID, name, or tags...]           Type: [All Types ▼]         │
│                                              Backend: [All Backends ▼]      │
│ Sort: [Date (newest) ▼]  [Apply Filters] [Reset]                          │
│                                                                             │
│ [🔄 Refresh] [📥 Export JSON] [📥 Export CSV]                              │
│ [☑️ Select All] [☐ Deselect All]                                            │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ Pins (5)                                     2 selected  [🗑️ Bulk Unpin]    │
├─────────────────────────────────────────────────────────────────────────────┤
│ ☑│ CID                         │Type      │Size  │Backend  │Tags      │Act │
├──┼─────────────────────────────┼──────────┼──────┼─────────┼──────────┼────┤
│ □│ QmYwAPJzv5CZsnA625s3Xf...   │recursive │25 MB │ipfs     │dataset   │V U │
│ ☑│ QmRHdRzHVK4j9YMqmJ3tVX...   │direct    │10 MB │cluster  │model     │V U │
│ □│ QmTkzDwWqPbnAh5YiV5VwcT...  │recursive │50 MB │ipfs     │backup    │V U │
│ ☑│ QmPZ9gcCEpqKTo6aq61g2nX...  │indirect  │5 MB  │storacha │archive   │V U │
│ □│ QmYHNYAaYK5hm3ZhZFx5W9H...  │recursive │100MB │ipfs     │public    │V U │
└─────────────────────────────────────────────────────────────────────────────┘

                        [← Previous]  Page 1 of 1  [Next →]
```

Legend:
- V = View Details
- U = Unpin

## Pin Details Modal (Mockup)

```
                    ┌─────────────────────────────────┐
                    │ Pin Details                  [×]│
                    ├─────────────────────────────────┤
                    │                                 │
                    │ CID:                            │
                    │ QmYwAPJzv5CZsnA625s3Xf2nemtY... │
                    │                                 │
                    │ Type:         [recursive]       │
                    │ Size:         25 MB             │
                    │ Status:       [pinned]          │
                    │                                 │
                    │ Backend:      ipfs              │
                    │ Replication:  1 copies          │
                    │                                 │
                    │ Tags:         [dataset][public] │
                    │                                 │
                    │ Name:         Sample Pin 1      │
                    │ Description:  This is a sample  │
                    │               pin for testing   │
                    │                                 │
                    │ Created:      Jan 15, 10:30 AM  │
                    │                                 │
                    ├─────────────────────────────────┤
                    │          [Close]  [🗑️ Unpin]   │
                    └─────────────────────────────────┘
```

## Bulk Unpin Confirmation (Mockup)

```
                    ┌─────────────────────────────────┐
                    │ Confirm Bulk Unpin           [×]│
                    ├─────────────────────────────────┤
                    │                                 │
                    │ Are you sure you want to unpin  │
                    │ 2 selected pins?                │
                    │                                 │
                    │ This action cannot be undone.   │
                    │                                 │
                    │ Pins to be unpinned:            │
                    │ • QmRHdRzHVK4j9YMqmJ3tVX...     │
                    │ • QmPZ9gcCEpqKTo6aq61g2nX...     │
                    │                                 │
                    ├─────────────────────────────────┤
                    │       [Cancel]  [🗑️ Unpin All] │
                    └─────────────────────────────────┘
```

## Export Download (Mockup)

```
                    ┌─────────────────────────────────┐
                    │ Export Pins                  [×]│
                    ├─────────────────────────────────┤
                    │                                 │
                    │ Format:  ● JSON  ○ CSV          │
                    │                                 │
                    │ Include:                        │
                    │ ☑ Metadata                      │
                    │ ☑ Tags                          │
                    │ ☑ Creation dates                │
                    │                                 │
                    │ Filter by type:                 │
                    │ [All Types ▼]                   │
                    │                                 │
                    │ Preview:                        │
                    │ 5 pins will be exported         │
                    │ Estimated file size: 2.5 KB     │
                    │                                 │
                    ├─────────────────────────────────┤
                    │        [Cancel]  [📥 Download]  │
                    └─────────────────────────────────┘
```

## Success Notification (Mockup)

```
┌──────────────────────────────────────┐
│ ✓ Successfully exported 5 pins to    │
│   pins_export_1704264000.json        │
└──────────────────────────────────────┘
```

## Loading State (Mockup)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│                                    ⟳                                         │
│                              Loading pins...                                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Mobile View (Mockup)

```
┌────────────────────────────────┐
│ ☰  Pin Management              │
├────────────────────────────────┤
│                                │
│ ┌────────┬────────┬──────────┐ │
│ │Total: 5│Recur: 4│Direct: 1│ │
│ └────────┴────────┴──────────┘ │
│                                │
│ 🔍 [Search...]                 │
│                                │
│ Type: [All ▼]                  │
│ Backend: [All ▼]               │
│ Sort: [Date ▼]                 │
│                                │
│ [Apply] [Reset]                │
│                                │
│ [🔄] [📥 JSON] [📥 CSV]        │
│ [☑ All] [☐ None]              │
│                                │
│ ┌──────────────────────────┐   │
│ │ □ QmYwAPJzv5CZsn...      │   │
│ │ Type: recursive          │   │
│ │ Size: 25 MB              │   │
│ │ [View] [Unpin]           │   │
│ └──────────────────────────┘   │
│                                │
│ ┌──────────────────────────┐   │
│ │ ☑ QmRHdRzHVK4j9YMq...     │   │
│ │ Type: direct             │   │
│ │ Size: 10 MB              │   │
│ │ [View] [Unpin]           │   │
│ └──────────────────────────┘   │
│                                │
│ [1 selected] [🗑️ Bulk Unpin]  │
│                                │
│        Page 1 of 1             │
└────────────────────────────────┘
```

## Color Palette

```
Primary (Purple-blue):  ████ #667eea
Secondary (Deep purple):████ #764ba2
Success (Green):        ████ #4ade80
Warning (Amber):        ████ #fbbf24
Error (Red):            ████ #f87171
Background (Light):     ████ #f8fafc
Text (Dark):            ████ #1e293b
Border (Light slate):   ████ #e2e8f0
```

## Interactive Elements

### Buttons
```
Primary:    [Button Text]     ← Purple gradient
Secondary:  [Button Text]     ← Gray
Success:    [✓ Button Text]   ← Green
Danger:     [🗑️ Button Text]   ← Red
Outline:    [Button Text]     ← White with border
```

### Badges
```
Type badges:     [recursive] [direct] [indirect]
Status badges:   [pinned] [pending] [error]
```

### Tags
```
Small pills:     dataset  model  backup  archive  public
```

## Responsive Breakpoints

```
Mobile:    < 768px  (Stacked layout)
Tablet:    768-1199px  (2-column grid)
Desktop:   ≥ 1200px  (Full layout)
```

## Accessibility Features

- ✓ Keyboard navigation (Tab, Enter, Escape)
- ✓ ARIA labels for screen readers
- ✓ High contrast ratios (WCAG AA)
- ✓ Focus indicators
- ✓ Semantic HTML
- ✓ Error announcements

## Animation Timing

```
Modal fade:      200ms ease-in-out
Notification:    300ms slide-in
Hover effects:   150ms ease
Loading spinner: 1s linear infinite
```

## Data Flow Animation

```
User Click
    ↓ 0ms
Button Press Effect
    ↓ 50ms
Loading Indicator
    ↓ 100-500ms
MCP SDK Call
    ↓ Network latency
Server Processing
    ↓ 10-100ms
Response Received
    ↓ 50ms
UI Update
    ↓ 100ms
Success Notification
    ↓ 3000ms
Auto-dismiss
```

## Key User Flows

### Flow 1: View Pins
```
1. User lands on /pins
2. Loading indicator shows
3. MCP SDK calls list_pins
4. Pins populate table
5. Statistics update
```

### Flow 2: Search & Filter
```
1. User types in search
2. 300ms debounce
3. Filter function runs
4. Table updates
5. Count updates
```

### Flow 3: Bulk Unpin
```
1. User selects checkboxes
2. Bulk bar appears
3. User clicks Bulk Unpin
4. Confirmation modal
5. User confirms
6. Progress shown
7. Success notification
8. List refreshes
```

### Flow 4: Export
```
1. User clicks Export JSON
2. MCP SDK calls export_pins
3. Data formatted
4. Download starts
5. Success notification
```

---

This visual overview shows all major UI components and user interactions in the Pin Management Dashboard.
