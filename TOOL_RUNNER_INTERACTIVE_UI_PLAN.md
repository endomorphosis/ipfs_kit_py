# Interactive Tool Runner UI: Implementation & Testing Plan


## 1. Goals & Requirements
- Replace or supplement the legacy tool runner (simple select + run) with a dynamic, schema-driven form UI for MCP tools.
- Allow users to pass arguments for any tool, with type-safe validation and helpful defaults.
- Support dynamic selects (backends, buckets, pins, etc) and enums from live MCP state.
- Show confirmation prompts for destructive actions (delete, rm, etc).
- Provide clear feedback: loading, errors, results, and success/failure.
- Maintain accessibility (keyboard, screen reader) and responsive layout.
- Keep legacy UI as fallback until new UI is fully validated.


## 2. Implementation Steps
### 2.1. Schema-driven Form Engine
- Parse each tool's `inputSchema` (JSON Schema-lite) to auto-generate form fields.
- Support types: string, number, boolean, object, array, enums, dynamic selects (via `ui.enumFrom`).
- Render appropriate widgets: text, textarea, select, checkbox, etc.
- Prefill defaults and required fields; show titles, descriptions, and placeholders.
- For fields with `ui.enumFrom`, fetch options from MCP (Backends, Buckets, Pins, etc).
- Show confirmation dialog if schema includes `confirm.message`.

### 2.2. Argument Validation & Submission
- Validate required fields and types before submission.
- Show inline errors for invalid/missing input.
- On submit, call MCP via SDK (`MCP.callTool`) and display result (success/error, timing).
- Disable submit button while loading; show spinner or progress.

### 2.3. Feedback & Accessibility
- Show clear error messages and result output (JSON pretty-print).
- Ensure all controls are keyboard-accessible and labeled.
- Use ARIA roles and attributes for form fields and dialogs.
- Responsive layout for desktop/tablet/mobile.

### 2.4. Integration & Fallback
- Integrate with MCP SDK for tool list, state, and calls.
- Keep legacy tool runner as fallback (simple select + JSON args textarea).
- Allow opt-in via URL flag (`?ui=beta`) or localStorage for beta UI.


## 3. Testing Plan
### 3.1. End-to-End (E2E)
- Use Playwright to test:
  - Tool runner loads and renders forms for all tools.
  - Dynamic selects populate from live MCP state (backends, buckets, pins).
  - Required fields and validation errors are shown.
  - Confirmation prompts appear for destructive actions.
  - Tool calls succeed/fail as expected; results are displayed.
  - Accessibility: tab order, ARIA, screen reader labels.
  - Responsive layout: desktop/mobile.
- Opt-in beta E2E tests (skipped by default, enable with env var).

### 3.2. Regression & Legacy
- Ensure legacy tool runner remains functional and unchanged until migration is complete.
- Run full E2E suite after each change; keep tests green.

### 3.3. Accessibility
- Use Playwright and manual checks for keyboard navigation, ARIA, and screen reader compatibility.


## 4. Milestones & Deliverables
- **Milestone 1:** Schema-driven form engine (fields, validation, dynamic selects).
- **Milestone 2:** Confirmation dialogs and error/result feedback.
- **Milestone 3:** Accessibility and responsive polish.
- **Milestone 4:** E2E and accessibility test coverage; opt-in beta flag.
- **Milestone 5:** Documentation and migration plan for legacy UI.


## 5. Summary
- The new Tool Runner UI will allow users to interact with MCP tools in a type-safe, user-friendly way, with dynamic forms, validation, and feedback.
- All changes will be gated behind a beta flag until fully tested; legacy UI remains as fallback.
- Comprehensive E2E and accessibility tests will ensure reliability and usability.
- Migration to the new UI will be documented and gradual, with user feedback.

## Server Work (low-risk)
- Optionally enrich _tools_list with fields described above for a subset of tools.
- Add alias /mcp/tools/describe → same as /mcp/tools/list to allow future divergence.
- No change to /mcp/tools/call behavior.

## SDK Enhancements
- MCP.schema.normalize(toolsList) → converts legacy maps into schema-lite.
- MCP.schema.validate(name, args) → return { ok, errors[] }.
- MCP.schema.coerce(name, rawArgs) → coerce strings to number/boolean; parse JSON fields.
- MCP.options.fetch(provider) → resolve dynamic select options with simple cache + refresh.

## SPA Implementation
- Feature flag: ?ui=beta or localStorage toolRunner.beta=true.
- Components:
  - ToolPicker (search, group, favorites) [data-testid=tool-search, tool-card-<name>, tool-favorite-<name>]
  - ToolForm (auto-generated inputs, inline validation) [tool-form-field-<name>]
  - RawJsonEditor [tool-form-json]
  - RunnerBar (Run, Cancel, Confirm) [tool-run, tool-cancel, tool-confirm]
  - ResultPanel (request/response, copy) [tool-request-json, tool-result-json]
  - HistoryPanel (list, re-run, clear) [tool-history-item-<i>]
  - Presets (save/select/delete) [tool-preset-save, tool-preset-select]
- Validation UX:
  - Required marks, inline messages; disable Run when invalid.
  - Confirm modal for danger tools; type name to confirm optional (phase 2).

## Testing Plan

Playwright E2E (add to existing suite):
- Happy paths
  - Files: write→read (text), mkdir→tree, rm dir (confirm), mv, copy recursive.
  - Buckets: create via backend dropdown→list→update patch→delete (confirm).
  - Pins: create with CID pattern→list→export→import (merge; added count).
  - IPFS: version call renders results; tests skip if IPFS not present.
  - Raw JSON: switch to JSON, edit args, run successfully.
  - Presets: save preset, reload page, preset persists and re-runs.
  - Search/favorites: search narrows tools, favorite persists.
- Validation and errors
  - Required fields block run, error tooltips visible.
  - Coercion: enter "123" for number, "true" for boolean, accepted.
  - Invalid JSON in raw mode shows error and disables run.
  - Server error (force 400) renders clearly in result panel with code/message.
- Accessibility
  - Axe basic checks (no critical violations) on Tool Runner panel.

Unit tests (small, JS):
- Schema normalize from legacy to schema-lite.
- Coercion/validation edge cases.
- Options provider cache + refresh.

## Milestones
- M1 (Files + Buckets):
  - SDK normalization + basic form renderer (text/number/checkbox/select/textarea).
  - Enrich server metadata for files_* and buckets.*
  - E2E for files + buckets paths.
- M2 (Pins + Raw JSON + Confirm + Presets/History):
  - Add CID widget, confirm flow, raw JSON editor, localStorage presets.
  - E2E for pins and raw mode.
- M3 (Options Providers + Accessibility + Polish):
  - Dynamic selects (backends, buckets, pins) via providers.
  - Search/favorites, keyboard navigation, axe checks.
- M4 (Docs + Stabilization):
  - Document schema-lite, SDK helpers, and usage in README.
  - Remove old button-only runner after a deprecation window.

## Risks & Mitigations
- Schema mismatch: normalize legacy schema on client; keep server minimal.
- Breaking tests: implement behind flag; update E2E incrementally.
- IPFS not installed: keep tests conditional (already in place).

## Acceptance Criteria
- Any tool can be run via forms or raw JSON with validated arguments.
- Dangerous ops require confirmation.
- Responses are readable and copyable; history and presets persist.
- All existing and new Playwright tests pass locally and in CI.
- No change to JSON-RPC call contract.

## Rollout
- Default off behind ?ui=beta for one iteration.
- After green tests and review, promote to default and keep button runner as a fallback for one release.

## Task Breakdown
- UI-001: Add schema normalization + type coercion helpers to SDK.
- UI-002: Add ToolPicker + ToolForm components (beta flag) in SPA.
- UI-003: Implement RawJsonEditor + validation wiring.
- UI-004: ResultPanel, copy buttons, and error rendering.
- UI-005: Presets + History with localStorage.
- UI-006: Confirm dialog for danger tools; wire tools (files_rm, delete_*).
- UI-007: Dynamic options providers (backends/buckets/pins).
- UI-008: Accessibility pass and keyboard navigation.
- UI-009: Enrich _tools_list with metadata for Files/Buckets/Pins.
- UI-010: Playwright tests for Files/Buckets.
- UI-011: Playwright tests for Pins/IPFS + Raw JSON + Presets.
- UI-012: Docs + README updates.
