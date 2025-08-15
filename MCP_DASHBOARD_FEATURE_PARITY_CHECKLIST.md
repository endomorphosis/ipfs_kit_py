# MCP Dashboard Feature Parity Checklist

Goal: Ensure the new consolidated MCP dashboard matches the legacy dashboard shown in the reference screenshot (visual + functional parity).

Legend: [ ] Todo · [~] In progress · [x] Done · [n/a] Not applicable

## 1) Global Shell
- [x] Sidebar navigation with sections and icons
  - Overview, Services, Backends, Buckets, Metrics, Configuration, MCP Server
- [x] Header with title + subtitle
  - "IPFS Kit Dashboard" + "Unified MCP Server & Control Interface"
- [x] Status bar in header
  - [x] Port indicator (e.g., Port 8004)
  - [x] Current time display (auto-updates)
  - [x] Real-time Updates toggle (green when on)
  - [x] Refresh Data button

Implementation hints:
- Use a small SPA (Vanilla/Preact/React). Source UI data from window.MCP.
- Provide dark/light friendly gradient backgrounds (CSS variables).

## 2) Overview Cards (Top Row)
- [x] MCP Server card
  - Shows "Running" + port; reflects `/api/mcp/status.initialized`
- [x] Services card
  - Shows count of active services (e.g., 15)
  - From `MCP.Services.list()` or `/api/services`
- [x] Backends card
  - Shows count of storage backends
  - From `MCP.Backends.list()`
- [x] Buckets card
  - Shows total buckets
  - From `MCP.Buckets.list()`

Acceptance:
- Counts update with Real-time toggle on (SSE/WS) or upon Refresh Data.
- Cards use consistent shadow, icon, and badge colors.

## 3) System Performance
- [x] CPU Usage bar + percentage
- [x] Memory Usage bar + percentage and absolute (e.g., 358.5 GB / 503.8 GB)
- [x] Disk Usage bar + percentage and absolute (e.g., 180.8 GB / 286.7 GB)

Source: `/api/system/health` and `/api/metrics/system`.

Acceptance:
- Values refresh on interval or via SSE.
- Bars animate smoothly without layout shift.

## 4) Network Activity
- [x] Network activity panel with loading state
- [x] Line chart or sparkline history from `/api/metrics/network` (aggregated deque)

Acceptance:
- Shows recent rx/tx bands; degrades gracefully to spinner if unavailable.

## 5) Sidebar System Status (Left Pane)
- [x] MCP Server status chip (Running/Stopped, green/red)
- [x] IPFS Daemon status chip (Running/Stopped)
- [x] Backends count quick stat
- [x] Quick stats mini-bars (CPU, RAM)

Source:
- MCP: `/api/mcp/status`
- IPFS: `MCP.Services.status('ipfs')` or tool `ipfs_version`
- Backends: `MCP.Backends.list()`

## 6) Panel Details
- Services
  - [x] List services with status + basic controls (guard in CI)
- Backends
  - [x] List + CRUD (create/get/update/delete/test)
- Buckets
  - [x] List + CRUD
- Metrics
  - [x] System and network metrics consolidated view
- Configuration
  - [x] Basic MCP settings (data dir, ports) with read-only or safe mutators
- MCP Server
  - [x] Status summary, SDK presence (`window.MCP`), and shutdown tool

## 7) UX, A11y, and Behavior
- [x] Keyboard navigation across all panels
- [x] ARIA roles/labels on cards and controls
- [x] Responsive layout (>= 1280px desktop target; degrade to tablet/mobile)
- [x] Real-time toggle controls SSE/WS subscription
- [x] Manual refresh button triggers re-fetch across widgets

## 8) SDK + Endpoints Mapping
- SDK: `/mcp-client.js` => `window.MCP`
  - Services, Backends, Buckets, Pins, Files, IPFS, CARs, State, Logs, Server
- REST/JSON-RPC mirrors:
  - Tools list/call: `POST /mcp/tools/list`, `POST /mcp/tools/call`
  - Health/Status: `/api/system/health`, `/api/mcp/status`
  - Logs/WS/SSE: `/api/logs/stream`, `/ws`
  - Network metrics: `/api/metrics/network`

## 9) Tests
- [x] Playwright: overview counts render and refresh
- [x] Playwright: performance bars show non-zero values
- [x] Playwright: network activity shows spinner then data
- [x] Playwright: sidebar status chips reflect status
- [x] Real-time toggle influences updates

## 10) Acceptance Criteria (Overall)
- Visual parity to legacy screenshot (cards, colors, layout, sidebar)
- Functional parity for listed panels and quick stats
- Reliable refresh behavior and optional real-time updates
- A11y and responsive checks pass
- Tests green in CI (skip/guard where environment-dependent)

Compliance/Migration notes:
- Active UI migrated off deprecated `/api/system/overview` to `/api/mcp/status`, `/api/system/health`, and `/api/metrics/*`.
- Deprecated endpoint retained for legacy tests and deprecation reporting; planned removal: 3.2.0.

---

Track progress by marking items as [x]. Commit updates alongside feature changes.
