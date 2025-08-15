# Dashboard UI Components Spec (MCP)

Purpose: Concrete, reusable components to implement the new dashboard to match the legacy UI screenshot. Each component lists props, data sources, events, accessibility, and sample markup.

## 1) Layout

### Sidebar
- Props: `items: Array<{id,label,icon,href}>`, `activeId`, `status: {mcp:"running|stopped", ipfs:"running|stopped", backends:number, cpu:number, ram:number}`
- Data: `MCP.status()`, `MCP.Services.status('ipfs')`, `MCP.Backends.list()`
- Events: `onSelect(id)`
- A11y: `nav[aria-label="Primary"]`, items as `button` with `aria-current="page"` for active
- Notes: include quick stats mini-bars

### Header
- Props: `title`, `subtitle`, `port`, `time`, `realtime:boolean`
- Data: `MCP.status().port`, `new Date()` ticker
- Events: `onToggleRealtime(boolean)`, `onRefresh()`
- A11y: `header role="banner"`, toggle is a `button` with `aria-pressed`

## 2) Primitives

### StatusPill
- Props: `status:'running'|'stopped'|'warn'`, `label`
- A11y: `role="status"` with `aria-live="polite"`

### KPI Card
- Props: `icon`, `title`, `value`, `caption`, `accent:'purple'|'green'|'orange'|'red'`
- A11y: `article` with `aria-labelledby`
- Sample:
```html
<article class="card kpi kpi--purple" aria-labelledby="kpi-services">
  <div class="kpi__icon" aria-hidden="true"></div>
  <div>
    <h3 id="kpi-services">Services</h3>
    <p class="kpi__value">15</p>
    <p class="kpi__caption">Active Services</p>
  </div>
</article>
```

### MetricBar
- Props: `label`, `value:number (0-100)`, `detail?:string`
- A11y: `role="progressbar"` with `aria-valuenow` `aria-valuemin="0"` `aria-valuemax="100"`

### NetworkPanel (shell)
- Props: `loading:boolean`, `points:Array<{ts,rx_bps,tx_bps}>`
- Data: `GET /api/metrics/network`
- A11y: `figure` with `figcaption` "Network Activity"
- Behavior: show spinner until `points.length>0`; render sparkline later

## 3) Overview Page

### Top Row Cards
- Server: `status.initialized ? 'Running' : 'Stopped'`, caption `Port ${port}`
- Services: `value = (await MCP.Services.list()).services.length`
- Backends: `value = (await MCP.Backends.list()).result.items.length`
- Buckets: `value = (await MCP.Buckets.list()).result.items.length`

### System Performance
- Data: `GET /api/system/health`
- Bars: CPU `health.cpu.percent`, Memory `health.mem.percent` + detail `used/total`, Disk `health.disk.percent` + detail

### Network Activity
- Data: `/api/metrics/network` (points deque already in server)
- Refresh: live via SSE/WS (toggle) or onRefresh()

## 4) Services Panel
- List: `MCP.Services.list()` -> `[{name,status}]`
- Controls: `MCP.Services.control(name, action)`; guard in CI or when not supported
- A11y: table with headers; buttons have labels `Start ${name}`

## 5) Backends Panel
- List: `MCP.Backends.list()` -> show name,type; controls Create/Get/Update/Delete/Test using SDK
- Create: `MCP.Backends.create(name, {type,...})`
- A11y: form with labels and validation

## 6) Buckets Panel
- List: `MCP.Buckets.list()`; Create/Delete via SDK; link to Files view preselecting bucket

## 7) Files Panel (VFS)
- Minimal: path input, List/Read/Write buttons; use `MCP.Files.*`
- Modes: text/hex for write

## 8) Real-time Updates
- SSE: `/api/logs/stream` used as heartbeat (or add `/api/metrics/stream` if needed)
- WS: `/ws` baseline; server already emits one `system_update`
- Toggle logic:
  - On: subscribe and periodically refresh cards/metrics
  - Off: cancel timers/subscriptions

## 9) State & Caching
- Cache `tools_list` and recent metrics in `localStorage` with TTL
- Prefer SDK (`window.MCP`) over raw fetches

## 10) Styling Tokens (CSS variables)
```css
:root {
  --bg-gradient: linear-gradient(180deg,#2e3a59,#6b4bcf);
  --card-bg: #ffffff;
  --text: #1f2937;
  --muted: #6b7280;
  --kpi-purple: #7b61ff;
  --kpi-green: #10b981;
  --kpi-orange: #f59e0b;
  --kpi-red: #ef4444;
}
```

## 11) Accessibility
- Keyboard: tab order, visible focus, Escape closes dialogs
- ARIA: live regions for results and status changes; progressbars for metrics
- Color contrast meets WCAG AA

## 12) Testing Hooks (data-testid)
- `data-testid="kpi-services"`, `kpi-backends`, `kpi-buckets`, `metric-cpu`, `metric-mem`, `metric-disk`, `network-panel`, `realtime-toggle`, `refresh-button`

## 13) Minimal Wiring Order
1. Sidebar + Header + KPI cards with static data
2. Wire MCP.status and counts to cards
3. Add System Performance bars wired to `/api/system/health`
4. Add Network panel wired to `/api/metrics/network`
5. Add Services/Backends/Buckets panels incrementally
6. Add real-time toggle + refresh cohesion
7. Polish a11y and responsive
