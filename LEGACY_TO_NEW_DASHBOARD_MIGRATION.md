# Legacy → New MCP Dashboard Migration Guide

This guide maps the legacy MCP Dashboard UI/flows to the new consolidated dashboard’s components, SDK calls, and endpoints. Use it to implement features with parity and to verify behavior.

## 1) Overview
- Legacy: Sidebar + header + top KPI cards + performance + network.
- New: `Sidebar`, `Header`, `KPI Card`, `MetricBar`, `NetworkPanel` (see `DASHBOARD_UI_COMPONENTS_SPEC.md`).

## 2) Feature Mapping

| Legacy Area | New Component(s) | Data Source / SDK | REST/JSON-RPC | Notes |
|---|---|---|---|---|
| MCP Server card | KPI Card (Server) | `MCP.status()` | `GET /api/mcp/status` | Show Running/Stopped + port. |
| Services card | KPI Card (Services) | `MCP.Services.list()` | `GET /api/services` | Count active services. |
| Backends card | KPI Card (Backends) | `MCP.Backends.list()` | `GET /api/state/backends` | Count items. |
| Buckets card | KPI Card (Buckets) | `MCP.Buckets.list()` | `POST /mcp/tools/call {name:'list_buckets'}` | Show total buckets. |
| System Performance | MetricBar (CPU/Mem/Disk) | `fetch('/api/system/health')` | `GET /api/system/health` | Percent + humanized values. |
| Network Activity | NetworkPanel | `fetch('/api/metrics/network')` | `GET /api/metrics/network` | Spinner → sparkline. |
| Sidebar status | Sidebar quick stats | `MCP.status()`, Services/IPFS, Backends | multiple | Mini-bars for CPU/RAM. |

## 3) Panels

- Services
  - List: `await MCP.Services.list()` → table (name, status)
  - Control: `await MCP.Services.control(name, action)` (guard in CI)
- Backends
  - List: `await MCP.Backends.list()`
  - CRUD: `create/get/update/delete/test` via SDK
- Buckets
  - List + CRUD via `MCP.Buckets.*`
- Files/VFS
  - `MCP.Files.list/read/write/mkdir/rm/mv/copy/stat/tree`
- Logs
  - `MCP.Logs.get(limit)`, `MCP.Logs.clear()`; SSE at `/api/logs/stream`

## 4) Real-time Updates
- Use SSE `/api/logs/stream` as a heartbeat, or wire WS `/ws` (receives `system_update`).
- Toggle behavior:
  - On: subscribe & refresh cards/metrics at interval
  - Off: unsubscribe & use manual refresh

## 5) Accessibility
- Cards as `article` with `aria-labelledby`
- Bars as `role=progressbar` with proper `aria-valuenow`
- Live regions for async status/results

## 6) Testing
- Playwright selectors (examples):
  - KPI: `[data-testid="kpi-services"]`
  - Metrics: `#metric-cpu`, `#metric-mem`, `#metric-disk`
  - Network: `[data-testid="network-panel"]`
  - Controls: `[data-testid="realtime-toggle"]`, `[data-testid="refresh-button"]`

## 7) Sample SDK Calls
```js
const st = await MCP.status();
const services = await MCP.Services.list();
const backs = await MCP.Backends.list();
const buckets = await MCP.Buckets.list();
const health = await fetch('/api/system/health').then(r=>r.json());
const net = await fetch('/api/metrics/network').then(r=>r.json());
```

## 8) Acceptance Criteria
- Visual parity (sidebar, header, cards, colors, layout) with the legacy screenshot.
- Functional parity (counts, metrics, network, quick stats, real-time toggle, refresh).
- A11y and responsive checks pass (WCAG AA).
- E2E tests green (skip IPFS-dependent steps when unavailable).
