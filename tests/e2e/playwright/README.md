MCP Dashboard Playwright tests

What this covers
- Tool Runner keyboard shortcuts: Enter runs from search/select/form; Ctrl+Enter runs from JSON args.
- Tools list cache: UI stores mcp_tools_cache with a TTL in localStorage.
- SSE logs controls: filter text, level select, and max-lines truncation; Clear button behavior.

Prereqs
- Server running and reachable (default http://127.0.0.1:8004). Start via ipfs-kit mcp start --port 8004 --foreground.
- Node 18+ with Playwright dependencies. Node modules are vendored in this folder.

Run
```bash
cd tests/e2e/playwright
npm run test
# Override base URL if needed
BASE_URL=http://127.0.0.1:8105 npm run test
```
