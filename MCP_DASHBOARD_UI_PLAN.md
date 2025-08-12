# MCP Dashboard UI: Implementation and Testing Plan

Date: 2025-08-10
Status: Proposed (ready to implement)
Owner: ipfs_kit_py

## 1) Overview

We will evolve the minimal MCP debug page into a user-friendly, SDK-first dashboard. The UI will render dynamic forms for MCP tools, add guided domain panels (Backends, Buckets, Pins, Files/VFS, Services, CARs, Logs), and rely exclusively on the JavaScript SDK exposed at /mcp-client.js.

The plan is incremental, with clear milestones, acceptance criteria, and a robust test strategy (unit, component, and Playwright E2E).

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
