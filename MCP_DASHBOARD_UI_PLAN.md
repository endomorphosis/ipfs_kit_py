# MCP Dashboard UI: Implementation and Testing Plan

Date: 2025-08-10
Status: Proposed (ready to implement)
Owner: ipfs_kit_py

## 1) Overview

We will evolve the minimal MCP debug page into a user-friendly, SDK-first dashboard. The UI will render dynamic forms for MCP tools, add guided domain panels (Backends, Buckets, Pins, Files/VFS, Services, CARs, Logs), and rely exclusively on the JavaScript SDK exposed at /mcp-client.js.

The plan is incremental, with clear milestones, acceptance criteria, and a robust test strategy (unit, component, and Playwright E2E).

> Visual Parity Note (Aug 2025): We will align the new unified dashboard with the legacy (screenshot) look: gradient hero header, metric cards (MCP Server, Services, Backends, Buckets), System Performance panel (CPU / Memory / Disk bars), Network Activity card (sparkline / loading state), left sidebar with icons + active highlight, lower-left compact System Status + Quick Stats, real-time toggle, and Refresh Data button.

This document adds a focused “Visual Parity & Layout” phase (M0) ahead of schema-driven Tool Runner milestones to ensure early user recognition and continuity.

## 2) Goals and Non-Goals

- Goals
  - Discoverable, approachable UI that works out of the box on localhost.
  - Dynamic Tool Runner that renders forms from schemas and supports presets/history.
  - Domain panels for routine tasks with validations and helpful feedback.
  - SDK-only access: all UI calls go through window.MCP.
  - Strong test coverage with fast feedback and CI-ready E2E.
- Non-Goals (initially)
  - Multi-user auth/session management.
  - Complex role-based access control.
  - Production SSO or HTTPS termination.

## 3) Current State (reference)

- Backend: FastAPI server; JSON-RPC endpoints
  - POST /mcp/tools/list, POST /mcp/tools/call
  - REST mirrors for convenience; SSE logs /api/logs/stream; WS /ws; health /api/system/health; status /api/mcp/status.
- Storage: ~/.ipfs_kit with JSON files, VFS under vfs/, CARs under car_store/.
- SDK: /mcp-client.js exposes window.MCP
  - Core: listTools, callTool, status
  - Namespaces: Services, Backends, Buckets, Pins, Files, IPFS, CARs, State, Logs, Server
- Minimal page: /app.js lists tools and allows one-click calls with no args.

## 4) UX Architecture

- Single-page app (SPA) driven by window.MCP.
- Two main areas:
  1. Dynamic Tool Runner (generic; works for any tool)
  2. Domain panels (guided flows for common operations)
- Optional frameworks:
  - Option A (no build): Vanilla JS + small helpers; fastest to embed.
  - Option B (light build): Preact + Vite for componentization and testing. Recommended for maintainability.

### 4.1 Visual Parity & Layout Specification (derived from legacy UI)

Core regions:
- Sidebar (fixed width ~220px) with product logo/version, nav groups (Overview, Services, Backends, Buckets, Metrics, Configuration, MCP Server) and footer status panel.
- Header / Hero (full-width minus sidebar): gradient background, large title + subtitle, cluster/time meta row (port, clock), control buttons (Real-time Updates toggle pill, Refresh Data button).
- Metrics band (below hero): 4 summary Cards (MCP Server State, Active Services count, Storage Backends count, Total Buckets count). Responsive: collapse to 2x2 on narrow screens.
- Main content grid: Left column System Performance card (progress bars), right column Network Activity (sparkline or loading skeleton). Additional rows later (Recent Activity, Logs summary, Top Tools usage) – deferred.
- Sidebar footer System Status widget: shows MCP Server (Running/Stopped), IPFS Daemon (Running/Unavailable), Backends count, Quick Stats (mini CPU/RAM bars), color-coded with accessible contrast.

Design tokens (initial draft):
- Gradient hero: linear-gradient(135deg, #2d3b8d 0%, #6a3fb7 50%, #b445c1 100%) with subtle dot pattern overlay (SVG or CSS repeating-radial-gradient) – optional.
- Card surface: rgba(255,255,255,0.08) border: 1px solid rgba(255,255,255,0.15) backdrop-filter: blur(6px) (falls back to solid color if no backdrop support).
- Accent colors: Services (green #0aa870), Backends (magenta #d14ad1), Buckets (orange #e6602d), MCP Server (purple #6a3fb7).
- Semantic statuses: success #17c964, warning #f5a524, danger #f31260, info #0072f5, neutral #8896a7.
- Spacing scale: 4px base (4 / 8 / 12 / 16 / 24 / 32).
- Radius: 14px cards, 8px buttons, 4px pills.
- Typography: System font stack; weight 600 for card headline number; 700 for main hero title.

Accessibility targets:
- Sidebar active item contrast >= 4.5:1.
- Focus ring: 2px outline #ffffffaa offset 2px on keyboard navigation.
- Progress bars: show percentage text (visually or via aria-label) for SR users.

Performance: DOM skeleton load state within <150ms; metrics update patch ≤ 10KB JSON.

Real-time mode toggle behavior:
- When enabled: subscribe WebSocket; update cards + quick stats every broadcast; network sparkline animates.
- When disabled: freeze UI; dim Real-time badge; manual Refresh Data triggers one status + metrics fetch.

Skeleton states:
- Loading metrics: animated shimmer placeholders in bars & network card central spinner with “Loading network data…”.
- Fallback if psutil absent: show “Unavailable” badges and disable bars.

Error surfaces:
- If WebSocket disconnects: show non-blocking toast + attempt reconnect with backoff (5s, 10s, 30s) while real-time toggle stays ON but pulses.

Extensibility Hooks:
- Each card root data-card="services|backends|buckets|mcp" for future plugin injection.
- Event dispatch window.dispatchEvent(new CustomEvent('dashboard:metrics:update', {detail:snapshot})) after each apply.

## 5) Dynamic Tool Runner

- Render Arguments form from tool schema; call tool; show result.
- Features
  - Search/filter tools, group by category (see §8 metadata).
  - Form controls by type: string/number/boolean/enum; JSON editor for object/array.
  - Validation (required, type, enum) with inline errors.
  - Presets (save/load/delete) and per-tool history (replay).
  - Request/Response panel with timing and copyable cURL.
- Data contract
  - Inputs: MCP.listTools() result; selected tool name.
  - Output: Validated args object for MCP.callTool(name, args).
  - Errors: schema/validation/server errors surfaced with details.

## 6) Domain Panels

- Backends
  - List/get/create/update/delete/test via MCP.Backends.*.
  - Inline JSON editor for config; type required with hints.
- Buckets
  - List/create/delete/get/update; link to Files panel with bucket preselected.
- Pins
  - List/create/delete; import/export; dedupe feedback.
- Files / VFS
  - Tree browser of ~/.ipfs_kit/vfs; stat/read/write/mkdir/mv/copy/rm/touch; hex/text modes.
  - Breadcrumbs and context menu actions.
- Services
  - Status probes (e.g., IPFS bin and API port); safe controls with CI guard.
- CARs
  - List/import/export; highlight car_store path; IPFS-dependent actions guarded.
- Logs
  - Live SSE tail with filters; clear logs; copy.

## 7) UX/A11y/Perf

- Layout/navigation: header with status pill; left nav; content cards; dark/light.
- Toasters for success/error; non-blocking loading states.
- Keyboard navigation and ARIA labels; high contrast.
- Debounced searches; virtualized long lists; cached tools list.

## 8) Server-side Metadata Enhancements (optional but valuable)

- Augment tools with JSON Schema (backward compatible):
  - jsonSchema per tool: title, description, properties, required, default, enum, examples, minimum/maximum.
- Add category to each tool for UI grouping: Backends, Buckets, Pins, Files, IPFS, CARs, State, Logs, Services, Server.
- Optional UI presets tools
  - ui_presets_get / ui_presets_set to persist presets under ~/.ipfs_kit/ui/.

## 9) Milestones and Acceptance Criteria
- M0: Visual Parity & Layout Foundation
  - Deliver: Sidebar + hero gradient + summary cards + performance & network panels + status footer + real-time toggle & refresh button.
  - Data Bound: /api/mcp/status → counts (services_active → Services, backends, buckets), uptime (for MCP Server card tooltip), security.auth_enabled (lock icon state), counts.requests (subtle analytics tooltip). Realtime metrics via WebSocket (cpu, mem, disk, network rx/tx) bound to progress bars + sparkline.
  - Acceptance:
    - All regions render with placeholder skeletons then populate.
    - Tabbing cycles through interactive controls with visible focus.
    - Disabling real-time stops bar/sparkline updates (no new values for ≥5s) until re-enabled.
    - Refresh button re-fetches status & last metrics snapshot (assert diff timestamp).
    - Lighthouse accessibility ≥ 90 for overview page (excluding tool panels).

- M1: Dynamic Tool Runner
  - Deliver: Tool list + generated form + validation + call + result panel.
  - Extras: Presets and history.
  - Accept: Any tool can be run with args; errors visible; presets persist.
- M2: Domain Panels
  - Deliver: Backends, Files, Buckets, Pins minimum complete; Services/Logs basic; CARs conditional.
  - Accept: CRUD and actions work with clear feedback; Files panel can write/read file.
- M3: UX polish & A11y
  - Deliver: Responsive layout, keyboard support, toasts, improved JSON/X-viewers.
  - Accept: Keyboard-only flows usable; visual feedback consistent; basic perf targets met.
- M4: Metadata enrichment (optional)
  
### 9.1 Stretch Enhancements (Post-Parity)
- Per-endpoint request rate (EMA over last 1/5/15 minutes) – augment WebSocket payload.
- Historical mini-sparklines for CPU & Memory (reuse history arrays already tracked server-side).
- Quick Stats expand panel: shows top 5 tools invoked (needs server counting metrics).
- Dark/Light theme toggle with prefers-color-scheme baseline.

### 9.2 De-Scope Guidelines
If time constrained, ship M0 with static (non-sparkline) network panel placeholder and add live sparkline in M3.
  - Deliver: jsonSchema + category on server; form fidelity improved.
  - Accept: Forms render from jsonSchema; fallback still works.

## 10) Testing Strategy

- Unit tests (JS)
  - Schema → form control mapping; defaults applied; validation behavior.
  - Presets/history: save/load/delete; resilience to malformed JSON.
- Component tests (if Preact/Vite)
  - Tool Runner: select tool → form renders; submit → calls SDK with expected payload; error handling.
  - Panel tests: Backends and Files happy path + edge cases.
- Playwright E2E
  - Setup via tests/e2e/global-setup.js (starts server and seeds backends).
  - Scenarios:
    - Status visible; tools searchable.
    - files_write (text) followed by files_read returns expected content.
    - Backends create/list/get/update/delete idempotent.
    - Buckets create/list/delete.
    - Pins create/list/delete; export/import (dedupe) round-trip.
    - Services probe shows structure; control actions skipped in CI.
    - CARs list works; export/import skipped unless IPFS is available.
    - Logs SSE shows lines; clear resets.
- CI
  - Two tiers: quick sdk_smoke.spec.js, and full UI suite behind feature flag.
  - Artifacts: traces, screenshots, HTML report.

## 11) Risks and Mitigations

- IPFS not installed → IPFS/CARs features limited.
  - Mitigate: conditional tests (skip when unavailable); clear UI messaging.
- Schema gaps → limited form fidelity initially.
  - Mitigate: enrich server metadata over time; provide manual JSON args input.
- Large responses/logs → slow renders.
  - Mitigate: truncation with expand; virtualization; streaming for logs.

## 12) Rollout Plan

- Default to new Tools (beta) and basic domain panels while keeping current debug view accessible.
- Gather feedback; promote new UI as default once M2 stabilized.
- Maintain backward compatibility for SDK and tool names.

## 13) Developer Notes

- SDK only: do not use raw fetch in UI; always go through window.MCP.
- Keep /mcp-client.js stable; serve with Cache-Control: no-store to avoid stale bundles.
- Prefer small, composable components and clear error surfaces.

## 14) Finalized Dashboard UI (2025)

- **Modern SPA**: Sidebar navigation, dashboard cards, real-time updates
- **Tool Runner UI**: Legacy and beta (schema-driven) UIs
  - Beta UI: Enable via `?ui=beta` or `localStorage.setItem('toolRunner.beta', 'true')`
- **Schema-driven forms**: Dynamic forms for MCP tools, validation, ARIA, keyboard shortcuts
- **Panels**: Overview, Tools, Buckets, Pins, Backends, Services, Integrations, Files, CARs, Logs
- **MCP JS SDK**: `/mcp-client.js` exposes `window.MCP` with all tool namespaces
- **Accessibility**: ARIA roles, keyboard navigation, responsive design
- **Testing**: Playwright E2E, Python smoke/unit tests
- **Data locations**: All state file-backed under `~/.ipfs_kit`

---

## Quickstart

Start the dashboard server:

```bash
ipfs-kit mcp start --host 127.0.0.1 --port 8004
# or
python -m ipfs_kit_py.cli mcp start --host 127.0.0.1 --port 8004
```

Open the UI at [http://127.0.0.1:8004/](http://127.0.0.1:8004/)

---

## Tool Runner UI

- **Legacy UI**: Simple select + run
- **Beta UI**: Schema-driven forms, ARIA, validation, keyboard shortcuts
  - Enable via `?ui=beta` or `localStorage.setItem('toolRunner.beta', 'true')`

## MCP JS SDK

- Exposed at `/mcp-client.js` as `window.MCP`
- Namespaces: Services, Backends, Buckets, Pins, Files, IPFS, CARs, State, Logs, Server
- Methods: `listTools()`, `callTool(name, args)`, plus per-namespace helpers

## Panels

- Overview, Tools, Buckets, Pins, Backends, Services, Integrations, Files, CARs, Logs

## Data Locations

- All state is file-backed under `~/.ipfs_kit` for CLI parity

## Testing

- Playwright E2E tests (see `tests/e2e/`)
- Python smoke and unit tests

## Documentation

- See `CONSOLIDATED_MCP_DASHBOARD.md` for dashboard details
- See `README_BETA_UI.md` for beta Tool Runner UI details

---

## 15) Visual Parity Execution Checklist (Legacy Screenshot Alignment)

This section enumerates each visible element from the legacy dashboard screenshot and maps it to implementation tasks, data sources, and acceptance criteria. Use it as a punch‑list for M0.

### 15.1 Layout Regions
Region | Description | Implementation Tasks | Data Source | Acceptance Criteria
--- | --- | --- | --- | ---
Sidebar | Logo/version, nav items, footer status | Skeleton HTML; dynamic counts; active highlight; responsive collapse | `/api/mcp/status` | Accessible labels; counts update in realtime
Hero Header | Gradient banner, title/subtitle, meta row (port/time), real-time toggle, refresh button | Gradient CSS; live clock; buttons wired | Config + client clock + WS state | Toggle stops updates; refresh repaints data
Summary Cards (4) | MCP Server, Active Services, Backends, Buckets | Card component; number animation; uptime tooltip | `/api/mcp/status` | Numbers render <500ms; uptime increments
System Performance Card | CPU/Mem/Disk bars | Bind snapshot; smooth transitions; psutil fallback text | WebSocket snapshot | Bars reflect latest tick or show Unavailable
Network Activity Card | Loading spinner then sparkline | Skeleton state; circular buffer; sparkline render | WebSocket deltas | Sparkline shows last ≥30 points or fallback
Sidebar Footer Status | MCP Server, IPFS, Backends count, mini CPU/RAM bars | Subscribe to metrics; mini bar components | Status + snapshot | Values update; statuses colored
Real-time Toggle | Pill button with dot | Manage WS lifecycle; aria-pressed | Client state | WS closed when off; indicator color change
Refresh Data Button | Manual fetch action | Debounce; refetch status & snapshot; visual flash | `/api/mcp/status` | Disabled during fetch; timestamp changes

### 15.2 Data Mapping Matrix
UI Field | Status JSON Path | Notes
--- | --- | ---
Active Services | data.counts.services_active | Already computed
Storage Backends | data.counts.backends | Length of backends mapping
Total Buckets | data.counts.buckets | Length of buckets list
MCP Server State | derived from uptime>0 | Could add explicit state later
Requests (tooltip) | data.counts.requests | Optional display
Auth Enabled | data.security.auth_enabled | Lock icon state
CPU Usage | metrics.cpu | From WS snapshot
Memory Usage | metrics.mem | From WS snapshot
Disk Usage | metrics.disk | From WS snapshot
Network Sparkline | derived successive net deltas | Build client-side

### 15.3 Component Build Order
1. Static skeleton (sidebar, hero, cards, panels)
2. Status fetch + populate summary cards
3. WebSocket metrics integration (performance bars)
4. Real-time toggle logic
5. Network sparkline implementation
6. Sidebar footer quick stats binding
7. Accessibility pass (tab order, ARIA, focus ring)
8. Visual polish (animations, skeletons, hover)
9. Tooltips & uptime formatting
10. Request count tooltip integration

### 15.4 Styling Tokens (JS Example)
```js
export const TOKENS = {
  color: {
    gradientStart: '#2d3b8d',
    gradientMid: '#6a3fb7',
    gradientEnd: '#b445c1',
    surface: 'rgba(255,255,255,0.08)',
    border: 'rgba(255,255,255,0.15)',
    textPrimary: '#ffffff',
    textSecondary: '#c2c8d5',
    status: { success: '#17c964', warning: '#f5a524', danger: '#f31260', info: '#0072f5' },
    accents: { services: '#0aa870', backends: '#d14ad1', buckets: '#e6602d', server: '#6a3fb7' }
  },
  radius: { card: '14px', button: '8px', pill: '24px' },
  spacing: (n)=>`${4*n}px`,
};
```

### 15.5 Accessibility & Performance Targets
- Lighthouse Accessibility ≥ 90 (Overview page)
- LCP < 2.0s (local dev baseline)
- WebSocket payload < 1 KB per tick
- All interactive controls reachable via Tab in logical order

### 15.6 Stretch Items (Post M0)
- CPU & Memory mini-sparklines
- Per-endpoint request rate (1/5/15 min EMA)
- Theme toggle (dark/light with prefers-color-scheme)
- Top tools usage mini-table (server support needed)

### 15.7 Definition of Done (M0)
All items in 15.1 implemented; data mapping validated; accessibility & performance targets met; no console errors after 60s real-time session.

