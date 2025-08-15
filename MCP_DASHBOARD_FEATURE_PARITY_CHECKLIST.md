# MCP Dashboard Feature Parity Checklist

Goal: Ensure the new consolidated MCP dashboard matches the legacy dashboard shown in the reference screenshot (visual + functional parity).

Legend: [ ] Todo · [~] In progress · [x] Done · [n/a] Not applicable

## 1) Global Shell
- [ ] Sidebar navigation with sections and icons
  - Overview, Services, Backends, Buckets, Metrics, Configuration, MCP Server
- [ ] Header with title + subtitle
  - "IPFS Kit Dashboard" + "Unified MCP Server & Control Interface"
- [ ] Status bar in header
  - [ ] Port indicator (e.g., Port 8004)
  - [ ] Current time display (auto-updates)
  - [ ] Real-time Updates toggle (green when on)
  - [ ] Refresh Data button

Implementation hints:
- Use a small SPA (Vanilla/Preact/React). Source UI data from window.MCP.
- Provide dark/light friendly gradient backgrounds (CSS variables).

## 2) Overview Cards (Top Row)
- [ ] MCP Server card
  - Shows "Running" + port; reflects `/api/mcp/status.initialized`
- [ ] Services card
  - Shows count of active services (e.g., 15)
  - From `MCP.Services.list()` or `/api/services`
- [ ] Backends card
  - Shows count of storage backends
  - From `MCP.Backends.list()`
- [ ] Buckets card
  - Shows total buckets
  - From `MCP.Buckets.list()`

Acceptance:
- Counts update with Real-time toggle on (SSE/WS) or upon Refresh Data.
- Cards use consistent shadow, icon, and badge colors.

## 3) System Performance
- [ ] CPU Usage bar + percentage
- [ ] Memory Usage bar + percentage and absolute (e.g., 358.5 GB / 503.8 GB)
- [ ] Disk Usage bar + percentage and absolute (e.g., 180.8 GB / 286.7 GB)

Source: `/api/system/health` or metrics endpoint in server; augment if needed.

Acceptance:
- Values refresh on interval or via SSE.
- Bars animate smoothly without layout shift.

## 4) Network Activity
- [ ] Network activity panel with loading state
- [ ] Line chart or sparkline history from `/api/metrics/network` (aggregated deque)

Acceptance:
- Shows recent rx/tx bands; degrades gracefully to spinner if unavailable.

## 5) Sidebar System Status (Left Pane)
- [ ] MCP Server status chip (Running/Stopped, green/red)
- [ ] IPFS Daemon status chip (Running/Stopped)
- [ ] Backends count quick stat
- [ ] Quick stats mini-bars (CPU, RAM)

Source:
- MCP: `/api/mcp/status`
- IPFS: `MCP.Services.status('ipfs')` or tool `ipfs_version`
- Backends: `MCP.Backends.list()`

## 6) Panel Details
- Services
  - [ ] List services with status + basic controls (guard in CI)
- Backends
  - [ ] List + CRUD (create/get/update/delete/test)
- Buckets
  - [ ] List + CRUD
- Metrics
  - [ ] System and network metrics consolidated view
- Configuration
  - [ ] Basic MCP settings (data dir, ports) with read-only or safe mutators
- MCP Server
  - [ ] Status summary, SDK presence (`window.MCP`), and shutdown tool

## 7) UX, A11y, and Behavior
- [ ] Keyboard navigation across all panels
- [ ] ARIA roles/labels on cards and controls
- [ ] Responsive layout (>= 1280px desktop target; degrade to tablet/mobile)
- [ ] Real-time toggle controls SSE/WS subscription
- [ ] Manual refresh button triggers re-fetch across widgets

## 8) SDK + Endpoints Mapping
- SDK: `/mcp-client.js` => `window.MCP`
  - Services, Backends, Buckets, Pins, Files, IPFS, CARs, State, Logs, Server
- REST/JSON-RPC mirrors:
  - Tools list/call: `POST /mcp/tools/list`, `POST /mcp/tools/call`
  - Health/Status: `/api/system/health`, `/api/mcp/status`
  - Logs/WS/SSE: `/api/logs/stream`, `/ws`
  - Network metrics: `/api/metrics/network`

## 9) Tests
- [ ] Playwright: overview counts render and refresh
- [ ] Playwright: performance bars show non-zero values
- [ ] Playwright: network activity shows spinner then data
- [ ] Playwright: sidebar status chips reflect status
- [ ] Playwright: real-time toggle influences updates

## 10) Acceptance Criteria (Overall)
- Visual parity to legacy screenshot (cards, colors, layout, sidebar)
- Functional parity for listed panels and quick stats
- Reliable refresh behavior and optional real-time updates
- A11y and responsive checks pass
- Tests green in CI (skip/guard where environment-dependent)

---

Track progress by marking items as [x]. Commit updates alongside feature changes.
