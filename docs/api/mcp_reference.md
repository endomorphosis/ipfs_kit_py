# MCP / MCP++ Reference

User-facing reference for the **packaged** Model Context Protocol (MCP) and
**MCP++** control plane shipped with `ipfs_kit_py`. This document describes
what operators and agents can launch, discover, and call on the **current
tree**. Architecture detail lives in
[`docs/architecture/MCP_CONTROL_PLANE.md`](../architecture/MCP_CONTROL_PLANE.md).

| Field | Value |
|---|---|
| **Document class** | Current user / API reference |
| **Status** | active |
| **Last verified** | 2026-08-04 |
| **Tree baseline** | `bee2495a0c1e0e6711cadaecfa5b3787b4eeef4f` |
| **Owner / task** | KDOC-033 |
| **Registry source of truth** | `ipfs_kit_py/mcp_server/tools/__init__.py` → `TOOL_GROUPS` |
| **Related ADR (Proposed)** | [`decisions/0003-mcp-runtime-authority.md`](../architecture/decisions/0003-mcp-runtime-authority.md) — **not accepted** by this reference |

**Authority language (read first):**

| Phrase | Meaning here |
|---|---|
| **Packaged current** | What `pyproject.toml` console scripts launch today |
| **Implemented** | Code and packaging behavior that holds regardless of open ADRs |
| **Compatibility / historical** | Importable trees retained for tests, migration, or older dashboards — **not** packaging defaults |
| **Proposed** | Linked ADR or open conflict; **not** maintainer-accepted sole production policy |

This reference does **not** declare [ADR-0003](../architecture/decisions/0003-mcp-runtime-authority.md)
Accepted. Packaging preference for `mcp_server` is **implemented packaging**,
not a closed production-authority decision among competing MCP trees
(**C-MCP-TREES** / **U-11**).

---

## 1. Scope and non-goals

### 1.1 Scope

- Packaged entry points: `ipfs-kit-mcp`, `ipfs-kit-mcp-tools`
- Transports: stdio (default), HTTP, optional libp2p P2P
- Stock MCP JSON-RPC: `initialize`, `tools/list`, `tools/call`, notifications
- Hierarchical discovery, JSON Schema derivation, and dispatch
- **Measured** tool groups from `TOOL_GROUPS` (with re-measurement commands)
- FastMCP bridge, Python callables, and generated JS/TS SDK surfaces
- MCP++ experimental profiles, envelopes, receipts (high level)
- Error, degraded, security, and conformance guidance

### 1.2 Non-goals

| Out of scope | See instead |
|---|---|
| Choosing sole production MCP runtime among `mcp_server`, `ipfs_kit_py.mcp`, root `mcp/`, `servers/` | **Proposed** ADR-0003; stay status-honest |
| Full architecture rationale / component ownership maps | [MCP_CONTROL_PLANE.md](../architecture/MCP_CONTROL_PLANE.md) |
| Operator CLI `ipfs-kit mcp …` (dashboard start/stop) | [cli_reference.md](cli_reference.md) — distinct stack |
| Regenerating JS SDK as part of this doc | `python -m ipfs_kit_py.mcp_server.js_sdk.generate` / project `make mcp-sdk` if present |
| Live secrets, host-specific paths, or multi-tenant auth productization | Placeholders only; config/trust guides |

---

## 2. Packaged entry points

| Console script | Module target | Role |
|---|---|---|
| `ipfs-kit-mcp` | `ipfs_kit_py.mcp_server.server:main` | MCP++ JSON-RPC server (stdio / HTTP / P2P) |
| `ipfs-kit-mcp-tools` | `ipfs_kit_py.mcp_server.cli:main` | One-shot tools CLI over the **same** registry |

```bash
# After install (console scripts) or from a checkout with PYTHONPATH
ipfs-kit-mcp --help
ipfs-kit-mcp-tools --help

# Module form (when scripts are not on PATH)
python -m ipfs_kit_py.mcp_server.server --help
python -m ipfs_kit_py.mcp_server.cli --help
```

**Server identity (from code):**

| Constant | Value |
|---|---|
| `PROTOCOL_VERSION` | `2025-06-18` |
| `SERVER_INFO.name` | `ipfs_kit_py-mcpplusplus` |
| `SERVER_INFO.version` | `0.1.0` (server module constant; not necessarily the package version) |

**Async runtime:** all packaged MCP++ server and tools-CLI paths run under
**anyio with the `trio` backend**.

---

## 3. Transports

```bash
# Default — line-delimited JSON-RPC on stdio (agent / IDE hosts)
ipfs-kit-mcp
# equivalent:
ipfs-kit-mcp --transport stdio

# HTTP ASGI (Hypercorn + trio); default bind is loopback
ipfs-kit-mcp --transport http --host 127.0.0.1 --port 8004

# Optional P2P stream transport (requires libp2p extra / importable peer stack)
ipfs-kit-mcp --transport p2p
```

| Flag | Values | Default | Notes |
|---|---|---|---|
| `--transport` | `stdio`, `http`, `p2p` | `stdio` | Mutually chosen at process start |
| `--host` | address | `127.0.0.1` | HTTP only; loopback by default |
| `--port` | int | `8004` | HTTP only |

| Transport | Behavior |
|---|---|
| **stdio** | One JSON-RPC object per line; notifications (no `id`) produce **no** reply |
| **HTTP** | JSON-RPC body to the ASGI app; also REST bindings for Profile G paths under `/mcp/…` and agent-supervisor receipts under `/mcp/agent-supervisor/receipts` |
| **P2P** | Protocol id `/mcp+p2p/1.0.0` via `p2p_transport.py`; unavailable when libp2p is missing |

**Daemon coupling:** MCP++ does **not** auto-start Kubo. `core_operations.get_kit`
uses `auto_start_daemons=False`. Live IPFS (or another backend the tool needs)
is still required for non-stub content results.

---

## 4. Surfaces that share one registry

```text
TOOL_GROUPS  (tools/__init__.py)
      │
      ▼
HierarchicalToolManager  (schema, list, dispatch, circuit breakers)
      │
      ├─ MCPServer JSON-RPC   (ipfs-kit-mcp)
      ├─ Tools CLI            (ipfs-kit-mcp-tools)
      ├─ Python callables     (import tool functions or dispatch)
      ├─ FastMCP registrar    (optional mcp package)
      └─ JS/TS generator      (tools-manifest.json + SDK)
```

| Surface | How to use | Status |
|---|---|---|
| Native MCP++ server | `ipfs-kit-mcp` → `initialize` / `tools/list` / `tools/call` | **Packaged current** |
| Tools CLI | `ipfs-kit-mcp-tools <category> <tool> [--k v …]` | **Packaged current** |
| Python | `from ipfs_kit_py.mcp_server.tools…` or `HierarchicalToolManager().dispatch` | **Packaged current** |
| FastMCP | `register_fastmcp(app)` / `build_app()` | **Compatibility bridge over the same registry** (requires `mcp` package) |
| JS/TS SDK | Generated from registry; committed `js_sdk/tools-manifest.json` | **Generated companion** (may lag registry — see §6) |

**Do not** treat legacy trees as this registry:

| Path | Label |
|---|---|
| `ipfs_kit_py/mcp/` (controllers, dashboards, many servers) | **Compatibility / historical** |
| Root `mcp/*_mcp_tools.py`, root `servers/*.py` | **Compatibility / historical or experimental** |
| `ipfs-kit mcp start` (FastCLI) | **Dashboard control path** — not `ipfs-kit-mcp` |
| `ipfs_kit_py/mcp.py` class `MCP` | Minimal stub; **not** MCP++ |

Production authority among competing trees remains **Proposed** under ADR-0003.
For new agent integrations prefer the **packaged** MCP++ scripts above, and
label any legacy import as compatibility until maintainers accept an authority
decision.

---

## 5. Discovery, schema, and dispatch

### 5.1 Stock MCP methods

| Method | Purpose |
|---|---|
| `initialize` | Handshake; returns `protocolVersion`, `serverInfo`, capabilities (including experimental MCP++ flags when requested) |
| `tools/list` | All registry tool schemas **plus** `agent_supervisor.receipts.read` |
| `tools/call` | Invoke a tool by `name` with `arguments` object |
| `notifications/*` | Accepted as no-ops when sent as JSON-RPC notifications (no `id`); no reply on stdio; HTTP **202** |

### 5.2 Hierarchical manager APIs

Used by the CLI and available to Python callers:

| API | Behavior |
|---|---|
| `list_categories()` | `[{name, tool_count}, …]` |
| `list_tools(category)` | Tool names in that group |
| `get_schema(category, tool)` | `name`, `description`, `inputSchema`, tags, deprecated |
| `all_tool_schemas()` | Flat list with `category` on each schema |
| `dispatch(category, tool, params)` | Execute with `request_id` and per-category circuit breaker |

Schemas are **derived from function signatures** (`build_input_schema`); optional
`@tool_metadata` supplies summary/tags/deprecation.

### 5.3 Naming and `tools/call`

Clients may pass:

| `name` form | Resolution |
|---|---|
| Flat tool name, e.g. `pin_ls` | Category scanned in `TOOL_GROUPS` order |
| Hierarchical, e.g. `pin_tools/pin_ls` | Explicit category + tool |
| `agent_supervisor.receipts.read` | Fail-closed receipt resolver (not in `TOOL_GROUPS`) |

Example JSON-RPC (illustrative):

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "ipfs_add",
    "arguments": {"file_path": "/tmp/example.txt", "recursive": false}
  }
}
```

Optional MCP++ envelope on `tools/call`:

- `_mcppp_envelope` — validated when present (`mcplusplus.validate_packet`;
  no-op validator when extras absent)
- `profile_b` — may attach `_mcppp` metadata and append an in-process event DAG node

### 5.4 Tools CLI

```bash
# List categories
ipfs-kit-mcp-tools
# or
ipfs-kit-mcp-tools --help

# List category → tools
ipfs-kit-mcp-tools list

# Dispatch (same path as MCP tools/call)
ipfs-kit-mcp-tools pin_tools pin_ls
ipfs-kit-mcp-tools ipfs_tools ipfs_add --file_path /tmp/example.txt
ipfs-kit-mcp-tools iroh_tools iroh_diagnostics --format health
```

CLI conventions:

- Args: `<category> <tool> [--key value …]`
- Values are parsed with `json.loads` when valid JSON; otherwise strings
- Prints a JSON result; exit **0** when `status == "success"`, else **1**
- Missing category/tool usage → exit **2**

### 5.5 Python dispatch

```python
import anyio
from ipfs_kit_py.mcp_server.hierarchical_tool_manager import HierarchicalToolManager

async def main():
    tm = HierarchicalToolManager()
    print(tm.list_categories())
    print(tm.list_tools("pin_tools"))
    print(tm.get_schema("ipfs_tools", "ipfs_add"))
    result = await tm.dispatch("pin_tools", "pin_ls", {})
    print(result)

anyio.run(main, backend="trio")
```

Or import a tool callable directly:

```python
from ipfs_kit_py.mcp_server.tools.ipfs_tools import ipfs_add
# async: await ipfs_add(file_path="…")
```

### 5.6 FastMCP bridge

```python
from ipfs_kit_py.mcp_server.fastmcp_app import register_fastmcp, build_app

# Option A: attach to an existing FastMCP app
from mcp.server import FastMCP
app = FastMCP("ipfs_kit_py-mcpplusplus")
register_fastmcp(app)  # returns list of registered tool names

# Option B: construct fully registered app (requires mcp package)
app = build_app()
```

FastMCP re-reads `HierarchicalToolManager.all_tool_schemas()` — it does **not**
maintain a second tool list.

### 5.7 JS / TS SDK

```bash
python -m ipfs_kit_py.mcp_server.js_sdk.generate
# or project make target when present:
# make mcp-sdk
```

Artifacts under `ipfs_kit_py/mcp_server/js_sdk/`:

- `tools-manifest.json` — generated companion of the registry
- `ipfs-kit-mcp-sdk.js` / `.ts`, `mcpp-client.js`

**Always regenerate after registry changes.** Do not edit the manifest by hand
as a parallel registry.

---

## 6. Measured tool inventory (do not invent counts)

**Policy:** never hard-code marketing or README tool totals without generation
or measurement evidence. Counts below were measured on the tree baseline in the
header. Re-run the commands in §6.3 after any registry or manifest change.

| Artifact | Measured count (2026-08-04 / baseline above) | Source |
|---|---:|---|
| `TOOL_GROUPS` categories | **12** | `tools/__init__.py` via import |
| `TOOL_GROUPS` tools | **29** | same (includes `iroh_diagnostics`) |
| Committed JS `tools-manifest.json` tools | **28** | `js_sdk/tools-manifest.json` |
| Registry-only (not in JS manifest) | **1** — `iroh_diagnostics` | set difference |
| Non-registry tool on `tools/list` | **+1** — `agent_supervisor.receipts.read` | `agent_supervisor_receipts.descriptor()` |

**Drift note (C-MCP-TOOLS):** published contracts must track the registry
(**29**) or an explicit, regenerated manifest — not stale package README prose
that still claims **21** tools / **7** tools in places. FastMCP e2e hard-asserts
may still expect older counts until updated.

### 6.1 Groups and tools (measured)

| Group | Count | Tools |
|---|---:|---|
| `ipfs_tools` | 3 | `ipfs_add`, `ipfs_cat`, `ipfs_ls` |
| `pin_tools` | 4 | `pin_add`, `pin_ls`, `pin_rm`, `get_pinset` |
| `dag_tools` | 2 | `dag_get`, `dag_put` |
| `mfs_tools` | 6 | `files_ls`, `files_mkdir`, `files_stat`, `files_write`, `files_read`, `files_rm` |
| `swarm_tools` | 2 | `node_id`, `swarm_peers` |
| `name_tools` | 2 | `name_publish`, `name_resolve` |
| `car_tools` | 1 | `create_car` |
| `cluster_tools` | 1 | `cluster_status` |
| `block_tools` | 3 | `block_put`, `block_get`, `block_stat` |
| `bitswap_tools` | 2 | `bitswap_stat`, `bitswap_wantlist` |
| `stats_tools` | 2 | `stats_bw`, `stats_repo` |
| `iroh_tools` | 1 | `iroh_diagnostics` |
| **Total** | **29** | |

### 6.2 Parameters (from live schemas)

Schemas are auto-derived; this table is a **measured snapshot** for operator
convenience. Prefer `get_schema` / `tools/list` for the live contract.

| Tool | Required | Other properties (defaults) |
|---|---|---|
| `ipfs_add` | `file_path` | `recursive` (false) |
| `ipfs_cat` | `cid` | |
| `ipfs_ls` | `path` | |
| `pin_add` | `cid` | `recursive` |
| `pin_ls` | — | |
| `pin_rm` | `cid` | `recursive` |
| `get_pinset` | — | |
| `dag_get` | `cid` | |
| `dag_put` | `data` | |
| `files_ls` | — | `path`, `long` |
| `files_mkdir` | `path` | `parents` |
| `files_stat` | `path` | |
| `files_write` | `path`, `content` | |
| `files_read` | `path` | |
| `files_rm` | `path` | |
| `node_id` | — | |
| `swarm_peers` | — | |
| `name_publish` | `path` | |
| `name_resolve` | — | |
| `create_car` | `roots` | |
| `cluster_status` | — | |
| `block_put` | `data` | |
| `block_get` | `cid` | |
| `block_stat` | `cid` | |
| `bitswap_stat` | — | |
| `bitswap_wantlist` | — | `peer` |
| `stats_bw` | — | |
| `stats_repo` | — | |
| `iroh_diagnostics` | — | `instance` (default), `format` (health), `persist` (true) |

### 6.3 Reproducible measurement (offline)

```bash
export IPFS_KIT_AUTO_INSTALL_BINARIES=0

python3 - <<'PY'
import json
from pathlib import Path
from ipfs_kit_py.mcp_server.tools import TOOL_GROUPS

groups = list(TOOL_GROUPS)
tools = [t for g in TOOL_GROUPS.values() for t in g]
mf = {
    t["name"]
    for t in json.loads(
        Path("ipfs_kit_py/mcp_server/js_sdk/tools-manifest.json").read_text()
    )["tools"]
}
print(f"{len(groups)} groups / {len(tools)} registry tools; "
      f"{len(mf)} JS manifest; reg-only: {sorted(set(tools) - mf)}")
for name, mapping in TOOL_GROUPS.items():
    print(f"  {name}: {len(mapping)} -> {list(mapping)}")
PY
```

CLI cross-check (no daemon required for listing):

```bash
ipfs-kit-mcp-tools list
```

---

## 7. MCP++ extensions (high level)

Stock MCP clients work without MCP++ extras. Experimental capabilities are
advertised on `initialize` under `capabilities.experimental` when requested.

| Area | Methods / hooks | Notes |
|---|---|---|
| Interface descriptors | `mcp++/interfaces` | Profile A descriptors from registry schemas |
| UCAN / policy | `mcp++/ucan/validate`, `mcp++/ucan/delegate`, `mcp++/policy/evaluate` | Degrade when signed-UCAN extras absent |
| Event DAG | `mcp++/dag/frontier`; Profile B envelopes on `tools/call` | In-process DAG unless durable store APIs used |
| Risk scheduling (Profile G) | `mcp++/goals/*`, `mcp++/tasks/*`, `mcp++/risk/*`, `mcp++/neighborhood/*`, `mcp++/schedule/*` | Also REST under `/mcp/…` on HTTP transport |
| Agent supervisor receipts | `agent_supervisor.receipts.read` | Fail-closed; JSON-RPC, `tools/call`, or REST |

**Coordination storage default directory** (local trust domain):

- `~/.local/share/ipfs_kit_py/mcppp_coordination`
- Override: `MCPPLUSPLUS_COORDINATION_DIR`

See also [Durable MCP++ Coordination Storage](../coordination-storage.md) and
the control-plane guide for envelope and Profile G/H detail.

---

## 8. Agent supervisor receipts (fail-closed)

| Property | Value |
|---|---|
| Method / tool name | `agent_supervisor.receipts.read` |
| Owner | `ipfs_kit_py` |
| Access | read |
| In `TOOL_GROUPS`? | **No** — appended to `tools/list` and interface descriptors |
| Synthetic success | **Never** — missing/unverified artifacts are denied / unavailable |

**Payload fields (allowed):** `receipt_ids`, `limit`, `cursor`, `status`,
`target_id` (plus envelope metadata such as `correlation_id` where applicable).

**HTTP (when using HTTP transport):**

| Verb | Path |
|---|---|
| GET / POST | `/mcp/agent-supervisor/receipts` |
| GET | `/mcp/agent-supervisor/receipts/{receipt_id}` |

Do not document fixture fallbacks; the resolver has none.

---

## 9. Errors, degraded modes, and results

### 9.1 Dispatch result shape

Successful and failed tool executions typically return a dict including:

| Field | Meaning |
|---|---|
| `status` | e.g. `success` or `error` (normalized by core operations / dispatch) |
| `request_id` | UUID allocated per `dispatch` (also on circuit-open errors) |
| `error` | Present on failure |
| `category` / `tool` | Present on many dispatch failures |

Circuit open (per category, after repeated failures):

```json
{"status": "error", "error": "circuit '<category>' open", "request_id": "…"}
```

JSON-RPC layer: failures become `{"jsonrpc":"2.0","id":…,"error":{…}}` with
optional structured `data` when the exception exposes MCP++ error codes.

### 9.2 Degraded modes

| Condition | Observable behavior |
|---|---|
| No live IPFS / kit import failure | `core_operations._StubKit` returns deterministic stub CIDs/results so surfaces stay testable offline — **not** production data |
| Missing libp2p | P2P transport unavailable |
| Missing envelope validator | `validate_packet` no-ops; base MCP tools still run |
| Missing optional MCP++ signed-UCAN extras | Local profiles remain; full signed UCAN features degrade |
| Category circuit open | No tool execution; structured error + `request_id` |
| Unknown JSON-RPC method | Error response |
| Receipt missing / integrity fail | Denied / unavailable — **never** synthetic success |
| Corrupt SQLite coordination index | Immutable blocks preserved; index rebuild path exists |

### 9.3 Observability

- Structured logs on dispatch include `request_id`, category, tool, elapsed ms
- Circuit breakers are **in-process per category** (not a published metrics API)
- Prefer correlating agent work with `request_id` and, when used, MCP++
  `correlation_id` on envelopes/receipts

---

## 10. Security and trust boundaries

| Boundary | Guidance |
|---|---|
| HTTP default bind | Loopback (`127.0.0.1`) — **not** a multi-tenant auth stack by itself |
| Network exposure | Binding non-loopback HTTP or enabling P2P is an operator trust decision |
| UCAN / policy hooks | Optional; do not assume deny-by-default for all tools without configuration |
| Receipts | Fail-closed read of content-addressed artifacts only |
| Coordination dir | Local filesystem trust domain; protect `MCPPLUSPLUS_COORDINATION_DIR` |
| Secrets | Never put live tokens, private keys, or host secret paths in examples or tickets |
| Tool wrappers | Thin async wrappers — backend credential redaction is owned by config/backend docs |

---

## 11. Compatibility guidance (without accepting ADR-0003)

Use this table when choosing an integration path. Status labels are
**descriptive**, not a production mandate.

| You want… | Prefer | Avoid treating as packaged MCP++ |
|---|---|---|
| Agent JSON-RPC / MCP tools | `ipfs-kit-mcp` + `TOOL_GROUPS` | Root `servers/*`, archive MCP trees |
| One-shot operator tool call | `ipfs-kit-mcp-tools` | Ad-hoc scripts that re-list tools by hand |
| Dashboard start/stop via FastCLI | `ipfs-kit mcp …` (documented in CLI ref) | Confusing this with `ipfs-kit-mcp` |
| Legacy controller / enhanced servers | Explicit **compatibility** import + tests | Calling them “canonical MCP++” |
| Migration guide “unified_mcp_server” | Treat as **competing claim** vs packaging | Silently equating it with `mcp_server` |

**Open (must stay open until maintainers confirm ADR-0003):**

1. Sole **production MCP runtime authority** among `mcp_server`, `ipfs_kit_py.mcp`,
   root `mcp/`, and `servers/` (**Proposed** ADR-0003, **C-MCP-TREES**).
2. **Published tool-count contract** alignment: registry 29 vs JS 28 vs stale
   README prose (**C-MCP-TOOLS**).
3. Multi-node defaults for receipt / coordination store deployment.

What **is** implemented today (not the same as ADR acceptance):

- Packaged scripts point at `ipfs_kit_py.mcp_server`
- Kit IPFS-family tools for those surfaces are declared once in `TOOL_GROUPS`
- FastMCP, CLI, native server, and JS generator are designed to consume that
  registry rather than parallel lists

---

## 12. Conformance and verification

### 12.1 Offline checks (no daemon)

```bash
export IPFS_KIT_AUTO_INSTALL_BINARIES=0

# Entry points resolve
ipfs-kit-mcp --help
ipfs-kit-mcp-tools list

# Registry measurement (§6.3)
python3 -c "from ipfs_kit_py.mcp_server.tools import TOOL_GROUPS; \
print(len(TOOL_GROUPS), sum(len(g) for g in TOOL_GROUPS.values()))"

# Focused interop (when running the package test suite)
# pytest ipfs_kit_py/mcp_server/tests_e2e_interop.py
# pytest tests/test_mcp_jsonrpc_conformance.py
```

### 12.2 With a live IPFS API

Start or point configuration at a reachable Kubo (or compatible) API, then
exercise content tools (for example `ipfs_add` / `pin_ls`) via CLI or MCP.
Stub results without a daemon are **not** proof of production readiness.

### 12.3 After adding a tool

1. Implement kit/core behavior (not only an MCP wrapper).
2. Add async function under `ipfs_kit_py/mcp_server/tools/`.
3. Register **once** in `TOOL_GROUPS`.
4. Regenerate JS SDK / manifest.
5. Update focused tests; re-measure counts for any docs that quote totals.
6. Do **not** invent a second registry for FastMCP, CLI, or dashboards.

---

## 13. Related documents

| Document | Role |
|---|---|
| [MCP_CONTROL_PLANE.md](../architecture/MCP_CONTROL_PLANE.md) | Canonical architecture guide |
| [ADR-0003 (Proposed)](../architecture/decisions/0003-mcp-runtime-authority.md) | Open runtime authority decision |
| [RUNTIME_AND_ENTRYPOINTS.md](../architecture/RUNTIME_AND_ENTRYPOINTS.md) | Process and entry map |
| [COMPATIBILITY_LAYERS.md](../architecture/COMPATIBILITY_LAYERS.md) | Compatibility stack patterns |
| [cli_reference.md](cli_reference.md) | `ipfs-kit` parser including `mcp` dashboard commands |
| [installation_guide.md](../installation_guide.md) | Install and first-success |
| [QUICK_REFERENCE.md](../QUICK_REFERENCE.md) | Short operator cheatsheet |
| [coordination-storage.md](../coordination-storage.md) | Durable MCP++ coordination store |
| [PUBLIC_SURFACE_MATRIX.md](../audits/PUBLIC_SURFACE_MATRIX.md) | Wave 0 surface S09–S11 evidence |
| Package `ipfs_kit_py/mcp_server/README.md` | In-tree overview (may lag measured counts) |

---

## 14. Document maintenance

| When this changes… | Update |
|---|---|
| `TOOL_GROUPS` membership | Re-run §6.3; refresh §6 tables; regenerate JS manifest |
| Server CLI flags / transports | §3 |
| Receipt or Profile G routes | §7–§8 |
| ADR-0003 status | Only after maintainer confirmation — never upgrade to Accepted in this file alone |
| Packaging entry points | §2 and install/quick-reference cross-links |

**Last measurement evidence for tool counts:** import of `TOOL_GROUPS` and read
of `js_sdk/tools-manifest.json` on 2026-08-04 against tree baseline
`bee2495a0c1e0e6711cadaecfa5b3787b4eeef4f` (12 groups / 29 tools; JS manifest 28;
registry-only `iroh_diagnostics`).
