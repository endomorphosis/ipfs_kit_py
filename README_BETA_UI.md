# Beta Tool Runner UI

This repository includes a schema-driven Tool Runner UI behind a feature flag. It provides dynamic forms (selects, defaults, validation), confirmation prompts, a live region for results, and improved accessibility.

## Enable the beta UI

- In the browser: append `?ui=beta` to the dashboard URL, or run in dev and toggle via `localStorage.setItem('toolRunner.beta', 'true')`.

## Playwright tests (opt-in)

- The beta UI tests are opt-in to keep the default suite stable.
- Enable them by setting `BETA_UI=1` in the environment.

Example:

```bash
BETA_UI=1 npm run e2e
```

## Notes

- The legacy Tool Runner remains available and is the default.
- The beta runner includes ARIA labels/roles, a live region, first-field focus, Ctrl/Cmd+Enter to run, and validation with `aria-invalid`.

## Finalized Beta Tool Runner UI (2025)

- **Schema-driven forms**: Dynamic forms for MCP tools, validation, ARIA, keyboard shortcuts
- **Activation**: Enable via `?ui=beta` in the dashboard URL or `localStorage.setItem('toolRunner.beta', 'true')`
- **Accessibility**: ARIA labels/roles, live region, first-field focus, Ctrl/Cmd+Enter to run, validation with `aria-invalid`
- **Testing**: Opt-in Playwright E2E tests (`BETA_UI=1 npm run e2e`)
- **Fallback**: Legacy Tool Runner remains available as default
- **Documentation**: See `MCP_DASHBOARD_UI_PLAN.md` and main README for full dashboard details
