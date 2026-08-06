# MCP++ and the multi-interface control plane

| Field | Value |
|---|---|
| **Document class** | Canonical (architecture guide) |
| **Status** | active |
| **Last verified** | 2026-08-03 |
| **Tree baseline** | `294271ade01e4e4c03a8b1693159fff8c99f3c34` |
| **Owner / task** | KDOC-017 / KDOC-G024 |
| **Evidence** | `pyproject.toml` `[project.scripts]`; `ipfs_kit_py/mcp_server/` (server, tools, hierarchical manager, FastMCP, CLI, JS SDK, mcplusplus, receipts); `ipfs_kit_py/mcp/`; root `mcp/`; `servers/`; focused tests listed in §11; Wave 0 maps [`SOURCE_OF_TRUTH_MAP.md`](./SOURCE_OF_TRUTH_MAP.md) §6, [`PUBLIC_SURFACE_MATRIX.md`](../audits/PUBLIC_SURFACE_MATRIX.md) S09–S11 |
| **Related ADR (Proposed)** | [`decisions/0003-mcp-runtime-authority.md`](./decisions/0003-mcp-runtime-authority.md) — **MCP runtime authority and single registry** (index: [`decisions/README.md`](./decisions/README.md) §8.1 ADR-0003). Body may be pending authorship; decision status remains **Proposed** until maintainer confirmation. |
| **Glossary** | [`GLOSSARY.md`](./GLOSSARY.md) — MCP++, tool registry, tool surface, fail-closed receipts |

---

## 1. Scope and explicit non-goals

### 1.1 Scope

This guide describes the **control plane** for agent- and operator-facing tool
invocation over the Model Context Protocol (MCP) and MCP++ extensions:

- The packaged **MCP++** runtime under `ipfs_kit_py/mcp_server/`
- The **single write-path tool registry** (`TOOL_GROUPS`) and hierarchical
  dispatch path
- **Multiple surfaces** that must share that registry: native JSON-RPC MCP
  server, tools CLI, Python callables, FastMCP registrar, and generated JS/TS SDK
- MCP++ **profiles** (interface descriptors, CID envelopes, UCAN/policy hooks,
  event DAG, risk scheduling), **durable coordination storage**, and
  **fail-closed** agent-supervisor receipt reads
- Transports: **stdio** (default), **HTTP** (Hypercorn + Trio), optional
  **libp2p P2P**
- Explicit labeling of **compatibility / historical** MCP trees that still
  exist beside packaging

### 1.2 Non-goals

| Out of scope | Owner / note |
|---|---|
| Choosing sole **production MCP runtime authority** among `mcp_server`, `ipfs_kit_py.mcp`, root `mcp/`, and `servers/` | **Proposed** [ADR-0003](./decisions/0003-mcp-runtime-authority.md); do not treat packaging or this guide as acceptance of that ADR |
| Cluster control-plane family (bespoke vs Kubo Cluster vs MCP++ coordination) | [ADR-0008](./decisions/0008-cluster-control-plane-authority.md) / cluster architecture guide |
| User-facing MCP reference API catalog | Planned `docs/api/mcp_reference.md` (KDOC-033) |
| Regenerating JS SDK / dashboard descriptor packs | Generator + KDOC generated-doc rules; this guide only records measured drift |
| Editing production registries, shims, or servers | Docs-only task; conflict policy forbids deciding legacy authority in code |
| Storage data plane (backends, pins, VFS content path) | Backend / content / VFS architecture guides |

### 1.3 How to read authority language

| Phrase in this guide | Meaning |
|---|---|
| **Packaged current stack** | What `pyproject.toml` console scripts launch today (`ipfs-kit-mcp`, `ipfs-kit-mcp-tools`) |
| **Compatibility / historical stack** | Importable trees retained for tests, migration, or older dashboards — **not** packaging defaults |
| **Implemented invariant** | Code + packaging behavior that holds regardless of the open authority ADR |
| **Proposed** | Linked ADR or index row; **not** maintainer-accepted production policy |

---

## 2. Supported / canonical surfaces and compatibility status

### 2.1 Packaged current stack (MCP++)

| Surface | Entry path | Status | Notes |
|---|---|---|---|
| MCP++ JSON-RPC server | Console `ipfs-kit-mcp` → `ipfs_kit_py.mcp_server.server:main` | **Packaged current** | `PROTOCOL_VERSION = "2025-06-18"`; `SERVER_INFO.name = "ipfs_kit_py-mcpplusplus"` |
| Tools CLI | Console `ipfs-kit-mcp-tools` → `ipfs_kit_py.mcp_server.cli:main` | **Packaged current** | Same `HierarchicalToolManager` / `TOOL_GROUPS` as the server |
| Tool callables (Python) | `from ipfs_kit_py.mcp_server.tools…` / package re-export of `TOOL_GROUPS` | **Packaged current** | Thin async wrappers over `core_operations` |
| FastMCP registrar | `ipfs_kit_py.mcp_server.fastmcp_app.register_fastmcp` / `build_app` | **Compatibility surface over the same registry** | Requires optional `mcp` package; not a second tool list |
| JS/TS SDK + manifest | `python -m ipfs_kit_py.mcp_server.js_sdk.generate`; committed `js_sdk/tools-manifest.json` | **Generated companion** | Must be regenerated from `TOOL_GROUPS`; currently drifted (see §2.3) |
| MCP++ coordination / profiles | `ipfs_kit_py/mcp_server/mcplusplus/` | **Packaged current (graceful)** | Extras may degrade; base MCP tools still run |
| Agent supervisor receipts | `agent_supervisor.receipts.read` via JSON-RPC, `tools/call`, or HTTP `/mcp/agent-supervisor/receipts` | **Packaged current** | Fail-closed; no fixture success path |

**Operator launch (offline-default stdio):**

```bash
# Packaged MCP++ server (stdio is default)
ipfs-kit-mcp --transport stdio
# HTTP Profile G / REST-capable ASGI (Hypercorn + trio)
ipfs-kit-mcp --transport http --host 127.0.0.1 --port 8004
# Optional P2P (requires libp2p extra)
ipfs-kit-mcp --transport p2p

# Same registry via CLI
ipfs-kit-mcp-tools list
ipfs-kit-mcp-tools pin_tools pin_ls
```

### 2.2 Compatibility / historical stack

These paths remain **importable** and covered by many tests. They are **not**
the `pyproject.toml` console-script targets for MCP++. Production authority
among them and `mcp_server` is **unresolved** ([ADR-0003](./decisions/0003-mcp-runtime-authority.md)).

| Path | Role | Status label |
|---|---|---|
| `ipfs_kit_py/mcp/` | Large prior-generation stack: controllers, dashboard, auth, HA, storage_manager, many `servers/*` | **Compatibility / historical** (**C-MCP-TREES**) |
| `ipfs_kit_py/mcp/servers/unified_mcp_server.py` | “Unified” server still advertised by [`docs/MCP_SERVER_MIGRATION_GUIDE.md`](../MCP_SERVER_MIGRATION_GUIDE.md) as canonical import | **Competing claim** vs packaging → MCP++; do not silently merge narratives |
| Other `ipfs_kit_py/mcp/servers/*` | Enhanced/VFS/standalone/etc. | **Deprecated within the legacy tree** when `IPFS_KIT_MCP_MODE=production` unless `IPFS_KIT_ALLOW_LEGACY_MCP=1` |
| Root `mcp/*_mcp_tools.py` and alternate root servers | Shims / bridges to older layouts | **Compatibility shims** |
| Root `servers/*.py` | Unpackaged alternate servers (e.g. `final_mcp_server_enhanced.py`) | **Historical / experimental** |
| `ipfs_kit_py/mcp.py` | Minimal anyio peer/server stub class `MCP` | **Not** MCP++; do not confuse with `mcp_server` |
| `consolidated_mcp_dashboard.py` (package or root) | Alternate dashboard entries outside packaging scripts | **Unresolved lifecycle** |
| FastCLI `ipfs-kit daemon` / legacy daemon import | Packaged CLI still reaches into **legacy** `mcp/` for daemon classes in places | **Coupling** packaged entry → historical tree (**C-MCP-TREES** follow-on) |

### 2.3 Measured tool counts (replace prose counts)

**Do not hard-code marketing numbers.** Counts below were measured from the
tree baseline listed in the header. Re-run the evidence commands when the
registry or manifest changes.

| Artifact | Measured count (2026-08-03 / baseline above) | Source |
|---|---|---|
| `TOOL_GROUPS` categories | **12** | `ipfs_kit_py/mcp_server/tools/__init__.py` |
| `TOOL_GROUPS` tools | **29** | same (includes `iroh_diagnostics`) |
| Committed JS `tools-manifest.json` tools | **28** | `ipfs_kit_py/mcp_server/js_sdk/tools-manifest.json` |
| Registry-only (not in JS manifest) | **1** — `iroh_diagnostics` | set difference |
| FastMCP e2e hard-assert | still expects **28** in `tests_e2e_interop.py` | **C-MCP-TOOLS** drift |
| `mcp_server/README.md` prose | still claims **21** tools / **7** tools in places | stale; **ignore for contracts** |

#### `TOOL_GROUPS` inventory (measured)

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

**Additional non-registry tool advertised by the native server:**
`agent_supervisor.receipts.read` is appended in `tools/list` via
`agent_supervisor_receipts.descriptor()` and is **not** a `TOOL_GROUPS` entry.
It is a kit-owned control-plane method over durable coordination storage.

#### Reproducible measurement

```bash
# Offline; no binary install
export IPFS_KIT_AUTO_INSTALL_BINARIES=0

python3 - <<'PY'
import re, json
from pathlib import Path
text = Path("ipfs_kit_py/mcp_server/tools/__init__.py").read_text()
body = re.search(r"TOOL_GROUPS.*?=\s*\{(.*?)\n\}", text, re.S).group(1)
groups = re.findall(r'"([a-z_]+)":\s*\{', body)
tools = re.findall(r'"([a-z_]+)":\s*[a-z_]+\.', body)
mf = {t["name"] for t in json.loads(
    Path("ipfs_kit_py/mcp_server/js_sdk/tools-manifest.json").read_text()
)["tools"]}
print(f"{len(groups)} groups / {len(tools)} registry tools; "
      f"{len(mf)} JS manifest; reg-only: {sorted(set(tools) - mf)}")
PY
```

Conflict ID **C-MCP-TOOLS** (Wave 0): published contract must track the
registry (**29**) or an explicit, regenerated manifest — not README prose.

---

## 3. Component ownership and source-of-truth paths

### 3.1 Ownership map (MCP++ tree)

| Concern | Path | Owns |
|---|---|---|
| Packaging entry | `pyproject.toml` `[project.scripts]` | `ipfs-kit-mcp`, `ipfs-kit-mcp-tools` |
| Server / transports | `ipfs_kit_py/mcp_server/server.py` | JSON-RPC route table, stdio/HTTP/P2P `main` |
| Single tool registry | `ipfs_kit_py/mcp_server/tools/__init__.py` → `TOOL_GROUPS` | Category → tool name → callable |
| Per-category tool modules | `ipfs_kit_py/mcp_server/tools/*_tools.py` | Thin async wrappers |
| Business logic over kit | `ipfs_kit_py/mcp_server/core_operations.py` | Shared `ipfs_kit` calls + **deterministic stub kit** when daemon/import fails |
| Hierarchical manager | `ipfs_kit_py/mcp_server/hierarchical_tool_manager.py` | Discovery APIs, schema build, dispatch, per-category circuit breakers, `request_id` |
| Tool metadata / JSON Schema | `ipfs_kit_py/mcp_server/tool_metadata.py` | `@tool_metadata`, `build_input_schema` from signatures |
| FastMCP bridge | `ipfs_kit_py/mcp_server/fastmcp_app.py` | Registers **all** registry tools onto a FastMCP app |
| Tools CLI | `ipfs_kit_py/mcp_server/cli.py` | CLI argv → `tm.dispatch` under trio |
| JS/TS generator | `ipfs_kit_py/mcp_server/js_sdk/generate.py` | Emits SDK + `tools-manifest.json` from registry |
| MCP++ profiles / packet | `ipfs_kit_py/mcp_server/mcplusplus/` | Capabilities, envelopes, delegation, event DAG, Profile G/H, coordination store |
| Fail-closed receipts | `ipfs_kit_py/mcp_server/agent_supervisor_receipts.py` | `AgentSupervisorReceiptResolver` |
| Optional P2P transport | `ipfs_kit_py/mcp_server/p2p_transport.py` | Protocol `/mcp+p2p/1.0.0`; graceful without libp2p |
| Exceptions | `ipfs_kit_py/mcp_server/exceptions.py` | Category/tool not found, execution errors |

### 3.2 Distinct registries (do not conflate)

| Registry | Location | Role |
|---|---|---|
| MCP++ hierarchical registry | `mcp_server/tools.TOOL_GROUPS` + `HierarchicalToolManager` | Production MCP++ tool write path |
| Core package `ToolRegistry` | `ipfs_kit_py/core/tool_registry.py` | JIT/core tooling — **not** the MCP++ control-plane registry |
| Legacy MCP tool modules | `ipfs_kit_py/mcp/servers/*_mcp_tools.py`, root `mcp/*_mcp_tools.py` | Compatibility surfaces; **not** `TOOL_GROUPS` |

**Implemented invariant (one registry, multiple surfaces for MCP++):**
native server, CLI, FastMCP registrar, Python imports, and JS generator are
designed to consume **`TOOL_GROUPS` only** for kit IPFS-family tools. Confirming
that no second write-path registry remains for production tools is part of
open work under ADR-0003 / **C-MCP-TOOLS**, not something this guide invents.

### 3.3 Evidence pointers (Wave 0)

- Authority map: [`SOURCE_OF_TRUTH_MAP.md`](./SOURCE_OF_TRUTH_MAP.md) §6  
- Surface matrix: [`PUBLIC_SURFACE_MATRIX.md`](../audits/PUBLIC_SURFACE_MATRIX.md) S09–S11, conflicts **C-MCP-TOOLS**, **C-MCP-TREES**  
- Pre-MCP++ audits (historical narrative): [`MCP_INTEGRATION_ARCHITECTURE.md`](./MCP_INTEGRATION_ARCHITECTURE.md), [`CLI_MCP_ARCHITECTURE_AUDIT.md`](./CLI_MCP_ARCHITECTURE_AUDIT.md), [`MCP_CONTROLLER_CONSOLIDATION.md`](./MCP_CONTROLLER_CONSOLIDATION.md)

---

## 4. Data flow and control flow

### 4.1 One registry, multiple surfaces

```text
                    ┌──────────────────────────────────────┐
                    │  TOOL_GROUPS                         │
                    │  tools/__init__.py (12 × 29 tools)   │
                    └──────────────────┬───────────────────┘
                                       │
                    ┌──────────────────▼───────────────────┐
                    │  HierarchicalToolManager             │
                    │  list_categories / list_tools /      │
                    │  get_schema / dispatch               │
                    │  + CircuitBreaker per category       │
                    │  + request_id tracing                │
                    └─┬────────────┬───────────┬───────────┘
                      │            │           │
           ┌──────────▼──┐  ┌──────▼────┐  ┌───▼────────────┐
           │ MCPServer   │  │ CLI       │  │ FastMCP        │
           │ JSON-RPC    │  │ mcp_server│  │ register_      │
           │ tools/list  │  │ /cli.py   │  │ fastmcp        │
           │ tools/call  │  └───────────┘  └────────────────┘
           └──────┬──────┘
                  │  also: receipts, mcp++/*, Profile G REST
     ┌────────────┼────────────────┐
     ▼            ▼                ▼
  stdio        HTTP ASGI         P2P (opt)
  (default)    Hypercorn+trio    libp2p

  core_operations._call  →  ipfs_kit (or _StubKit)
  JS SDK generator       →  tools-manifest.json + *.js/*.ts
```

### 4.2 Schema and dispatch flow

1. **Registration:** tool modules define async functions; optional
   `@tool_metadata` attaches summary/tags/deprecation.
2. **Schema:** `build_input_schema(fn)` derives JSON Schema from the signature;
   `get_schema` / `all_tool_schemas` expose name, description, `inputSchema`.
3. **Discovery:**
   - Stock MCP: `tools/list` returns all registry schemas **plus** the receipt
     descriptor.
   - Manager/CLI: `list_categories` → `list_tools` → `get_schema` (hierarchical
     meta-API; avoids flooding discovery UIs when used intentionally).
4. **Invocation:**
   - `tools/call` with tool `name` (flat name resolved via category scan, or
     `category/tool` form) → `HierarchicalToolManager.dispatch`.
   - CLI: `ipfs-kit-mcp-tools <category> <tool> [--k v …]` → same `dispatch`.
5. **Dispatch mechanics:**
   - Allocate UUID **`request_id`**
   - Check **per-category circuit breaker** (open → structured error without
     calling the tool)
   - Filter params to signature parameters
   - Await coroutine (or call sync function)
   - On success: `on_success`, ensure `request_id` on result
   - On failure: `on_failure`, return `{status: error, request_id, …}`

### 4.3 MCP++ envelope and coordination path

When `tools/call` includes `_mcppp_envelope` or `profile_b`, the server may:

1. Validate the envelope via `mcplusplus.validate_packet` (no-op if validator
   extras absent).
2. Dispatch the tool as usual.
3. Build intent/decision/receipt-style artifacts (`mcplusplus.artifacts`) and
   append an event node to the in-process **event DAG** (`EventDAGStore`).
4. Attach `_mcppp` metadata onto the result dict.

Profile G risk-scheduling methods (`mcp++/goals/*`, `mcp++/tasks/*`,
`mcp++/risk/*`, `mcp++/neighborhood/*`, `mcp++/schedule/*`) route through
`mcplusplus.profile_g_transport.ProfileGDispatcher`. HTTP maps normative REST
paths under `/mcp/…` into those RPC methods without changing wire semantics.

### 4.4 Receipt read path (fail-closed)

```text
client  →  agent_supervisor.receipts.read  (JSON-RPC | tools/call | REST)
        →  AgentSupervisorReceiptResolver.read
        →  DurableCoordinationStore (immutable dag-json blocks + SQLite index)
        →  verified artifact only; missing/unverified → denied / unavailable
```

There is **no** fixture or synthetic-success fallback in the resolver module
docstring or implementation path.

---

## 5. Invariants and consistency / ordering guarantees

| ID | Invariant | Evidence |
|---|---|---|
| I-REG | MCP++ kit tools for the packaged surfaces are declared only in `TOOL_GROUPS` | `tools/__init__.py` module docstring; FastMCP/CLI/server consumers |
| I-SURF | FastMCP and CLI do not maintain parallel tool name lists | `fastmcp_app.register_fastmcp` iterates `tm.all_tool_schemas()`; CLI uses `HierarchicalToolManager` |
| I-REQ | Every dispatch returns or tags a `request_id` | `hierarchical_tool_manager.dispatch` |
| I-CB | Category circuit breaker fails closed when open (no tool execution) | same |
| I-RCPT | Receipt reads are fail-closed; integrity/missing ⇒ error, not fake success | `agent_supervisor_receipts.py`, `DurableCoordinationStore` |
| I-STORE | Immutable block bytes (dag-json) are authoritative; SQLite is rebuildable acceleration | `coordination_storage.py` module + `recover(rebuild=…)` |
| I-ASYNC | Packaged server/CLI run under **anyio with trio backend** | `server.main`, `cli.main` |
| I-PROTO | Stock MCP clients use `initialize` / `tools/list` / `tools/call` / notifications | `MCPServer._route` |
| I-AUTH-OPEN | Sole production runtime among competing trees is **not** closed by this guide | ADR-0003 **Proposed** |

**Ordering:** event DAG appends for Profile B envelopes are local to the
server process’s `EventDAGStore` instance unless durable store APIs are used
explicitly. Multi-node consistency for coordination artifacts is an open
operator concern (receipt store deployment defaults — map §6 unresolved #3).

---

## 6. Process, async, and lifecycle boundaries

| Boundary | Behavior |
|---|---|
| Async runtime | **anyio**, backend **`trio`** for stdio, HTTP, P2P, and tools CLI |
| HTTP server | **Hypercorn** trio worker (`serve_http`); default bind `127.0.0.1:8004` |
| Kit orchestration | `core_operations` wraps synchronous `ipfs_kit` via worker-thread offload so trio remains cooperative |
| Process model | One OS process per `ipfs-kit-mcp` invocation; no multi-worker claim in-tree for the ASGI app |
| Daemon coupling | MCP++ does **not** auto-start Kubo; `core_operations.get_kit` uses `auto_start_daemons=False`. Live IPFS still needed for non-stub results |
| Lifecycle notifications | JSON-RPC notifications (no `id`, e.g. `notifications/initialized`) are accepted without reply (HTTP 202) |
| Optional extras | libp2p, accelerate `mcplusplus_module`, envelope validator — imported under try/except; base server remains plain MCP |

Detailed AnyIO/asyncio policy is owned by `ASYNC_AND_OPTIONAL_DEPENDENCIES.md`
(KDOC-018); this guide only records the MCP++ trio choice.

---

## 7. Trust boundaries and sensitive-data handling

| Boundary | Handling |
|---|---|
| Local default bind | HTTP defaults to loopback (`127.0.0.1`) — not a multi-tenant auth stack by itself |
| UCAN / delegation | `mcp++/ucan/validate`, `mcp++/ucan/delegate`, `mcp++/policy/evaluate` provide chain validation and deny/risk evaluation hooks; full signed UCAN depends on extras (`HAVE_MCPLUSPLUS`) |
| Receipt envelope | Resolver validates owner/capability/method/access fields; unknown payload keys denied |
| Coordination dir | Default `~/.local/share/ipfs_kit_py/mcppp_coordination` or `MCPPLUSPLUS_COORDINATION_DIR` — treat as local trust domain |
| Secrets | Tools must not log credentials; backend redaction is owned by config/backend guides — MCP tools are thin wrappers |
| Profile H payments | `mcplusplus/profile_h*.py` paid-kit path is a specialized trust surface; not the default tool path |

**Do not** paste live tokens, private keys, or host-specific secret paths into
examples. Use placeholders.

---

## 8. Expected failures, degraded modes, and observability

### 8.1 Degraded modes

| Condition | Observable behavior |
|---|---|
| No live IPFS / kit import failure | `core_operations._StubKit` returns deterministic stub CIDs/results so surfaces stay testable offline |
| Missing libp2p | P2P transport unavailable; `get_capabilities()` reports `E_p2p_transport: false` |
| Missing envelope validator | `validate_packet` no-ops (returns `None`); base MCP still works |
| Missing accelerate mcplusplus module | Signed UCAN / some profile flags degrade; local profiles A/B/D/E/G still present in code |
| Category circuit open | `dispatch` returns `status: error` with circuit message + `request_id` |
| Unknown JSON-RPC method | Error response (HTTP JSON-RPC error envelope) |
| Receipt missing / integrity fail | `unavailable` / denied style responses — **never** synthetic success |
| Corrupt SQLite index | Blocks preserved; corrupt DB renamed; index recreated / `recover` rebuild from blocks |

### 8.2 Observability

- Structured logs on dispatch success/error include `request_id`, category,
  tool, and elapsed ms (`hierarchical_tool_manager` logger).
- Circuit breaker state is per category in-process (not exported as metrics
  API in the baseline tree).
- Coordination store exposes artifact index tables for claims/leases/health —
  operator-facing metrics productization is not claimed here.

---

## 9. Extension points and safe modification guidance

### 9.1 Add a kit tool (intended path)

1. Implement core behavior on the kit / backend (not only in MCP wrappers).
2. Add an async function in the appropriate
   `ipfs_kit_py/mcp_server/tools/<group>_tools.py` (or new module).
3. Optionally decorate with `@tool_metadata(...)`.
4. Register exactly once in `TOOL_GROUPS` under the correct category.
5. Regenerate JS SDK / manifest (`python -m ipfs_kit_py.mcp_server.js_sdk.generate`
   or project `make mcp-sdk` if present).
6. Update focused tests; **never** hard-code stale tool totals in docs without
   re-measurement.
7. Do **not** fork a second registry for FastMCP, CLI, or dashboard.

### 9.2 Safe vs unsafe changes

| Safe | Unsafe without ADR / multi-surface update |
|---|---|
| New tool in `TOOL_GROUPS` + regenerate SDK | Editing only JS manifest or only FastMCP list |
| Schema changes via function signatures | Inventing a parallel tool name in legacy `mcp/` as the production path |
| Documenting measured drift | Claiming ADR-0003 is Accepted |
| Thin wrappers over `core_operations` | Implementing heavy business logic only in legacy controllers |

### 9.3 How a developer invokes a tool without divergent schemas

| Interface | Invocation |
|---|---|
| Python | `await HierarchicalToolManager().dispatch("pin_tools", "pin_ls", {})` or import the tool function |
| CLI | `ipfs-kit-mcp-tools pin_tools pin_ls` |
| MCP client | `initialize` → `tools/list` → `tools/call` with `name: "pin_ls"` (or `pin_tools/pin_ls`) |
| FastMCP | `register_fastmcp(app)` then use standard FastMCP tool calling |
| JS | Generated SDK methods (after regenerate to include new tools) |

---

## 10. Design rationale, trade-offs, and rejected alternatives

Rationale labels follow [`DOCUMENTATION_GUIDE.md`](../guides/DOCUMENTATION_GUIDE.md) §5.

| Topic | Rationale | Confidence |
|---|---|---|
| Hierarchical categories + meta discovery APIs | Avoid flooding clients with dozens of top-level tools; mirrors `ipfs_datasets_py` manager pattern (module docstring) | **Inferred** from code comments + structure; product UX policy not separately ADR’d |
| Single `TOOL_GROUPS` registry shared by surfaces | Prevent schema/name drift across CLI/MCP/SDK | **Accepted** as *implemented design intent* in registry docstring; **Published contract count** still drifted (**C-MCP-TOOLS**) |
| Trio backend for server + CLI | One async core across transports | **Accepted** as implemented (`anyio.run(..., backend="trio")`) |
| Graceful MCP++ extras | Run as plain MCP without accelerate/libp2p | **Accepted** as implemented (`mcplusplus/__init__.py`) |
| Fail-closed receipts | Supervisory audit must not invent success | **Accepted** as implemented invariant |
| Immutable blocks + rebuildable SQLite | Content-addressed durability; local index may be discarded | **Accepted** as implemented in `DurableCoordinationStore` |
| Competing MCP trees retained | Migration, tests, dashboards | **Unknown** final disposition — **Proposed** ADR-0003 |
| Migration guide “unified_mcp_server only” | Documents legacy-tree deprecation guards | **Inferred** historical policy; **conflicts** with packaging → `mcp_server` (**C-MCP-TREES**) |

### 10.1 Rejected / non-default alternatives (as currently coded)

| Alternative | Status in tree |
|---|---|
| Maintain separate tool lists per surface | Rejected by MCP++ design; FastMCP re-reads registry |
| Synthetic receipt success for missing CIDs | Rejected (fail-closed) |
| Auto-start IPFS daemons from MCP++ kit getter | Rejected (`auto_start_daemons=False`) |
| Treat root `servers/` as packaging entry | Not declared in `[project.scripts]` |

### 10.2 Open owner decisions (must stay open)

Linked from [`decisions/README.md`](./decisions/README.md) §8.2 and
[`SOURCE_OF_TRUTH_MAP.md`](./SOURCE_OF_TRUTH_MAP.md) §6:

1. **Production MCP runtime authority** — `mcp_server` vs `mcp` / root `mcp/` /
   `servers/` / migration-guide unified server (**ADR-0003**, **Proposed**).
2. **Tool registry singularity & published count** — 29 registry vs 28 JS vs
   stale README 21/7 (**C-MCP-TOOLS**).
3. **Receipt / coordination store deployment defaults** and multi-node read
   consistency.
4. **Legacy dashboard lifecycle** (maintain, archive, re-bind to MCP++).
5. **CLI daemon path** — continue legacy `mcp/` daemon import, MCP++ HTTP
   Profile G, or `EnhancedDaemonManager` only.

---

## 11. Tests and fixtures that verify the behavior

Prefer default pytest discovery (`tests/`, unit trees; integration/archived
often excluded by `pytest.ini`).

| Area | Paths |
|---|---|
| MCP++ multi-surface e2e | `ipfs_kit_py/mcp_server/tests_e2e_interop.py` (stdio/HTTP/JS/FastMCP/handshake; **note hard-assert 28 vs registry 29**) |
| JSON-RPC conformance | `tests/test_mcp_jsonrpc_conformance.py` |
| Server init / start | `tests/test_mcp_initialization.py`, `tests/test_mcp_start_verification.py`, `tests/test_mcp_server_integration.py` |
| Tools / payload | `tests/test_mcp_tools_*.py`, `tests/test_comprehensive_tools.py`, `tests/test_tools_call_payload_parsing.py`, `tests/test_tool_status.py` |
| Receipts | `tests/test_agent_supervisor_receipts.py` |
| Iroh MCP | `tests/test_iroh_mcp_api.py` |
| UI smoke (often legacy dashboard) | `tests/test_mcp_ui_smoke.py` — filter carefully |
| Legacy / comprehensive MCP | many `tests/test_mcp_*.py`, `tests/unit/test_unified_mcp_server_comprehensive.py` — may target **compatibility** trees (**C-MCP-TREES**) |
| CI workflows (supplementary) | `.github/workflows/mcp-server-ci.yml`, `final-mcp-server.yml`, `enhanced-mcp-server.yml` |

Offline validation policy for documentation: `IPFS_KIT_AUTO_INSTALL_BINARIES=0`.

---

## 12. Change triggers and last-verified baseline

### 12.1 Re-verify this guide when

| Change | Action |
|---|---|
| Edit `TOOL_GROUPS` or tool modules | Re-run measurement commands; update §2.3 tables; regenerate JS manifest |
| Change packaging scripts for MCP | Update §2.1 entry paths |
| Accept/reject ADR-0003 | Update §1.3 / §10 language; never leave “Proposed” if Accepted |
| Alter receipt fail-closed semantics | Update §4.4 / §5 / §8 |
| Change transports (stdio/HTTP/P2P) or default port | Update §6 |
| Resolve JS/FastMCP count drift | Clear **C-MCP-TOOLS** notes when registry, manifest, and tests agree |

### 12.2 Baseline

| Field | Value |
|---|---|
| Last verified | 2026-08-03 |
| Tree | `294271ade01e4e4c03a8b1693159fff8c99f3c34` |
| Measurement | 12 groups / 29 `TOOL_GROUPS` tools; 28 JS manifest tools; registry-only `iroh_diagnostics` |

### 12.3 Related documents

| Document | Relationship |
|---|---|
| [ADR-0003 MCP runtime authority](./decisions/0003-mcp-runtime-authority.md) | **Proposed** authority decision (required link for this task) |
| [ADR index](./decisions/README.md) | Process + ADR-0003 row |
| [SOURCE_OF_TRUTH_MAP.md](./SOURCE_OF_TRUTH_MAP.md) §6 | Evidence map for MCP control plane |
| [PUBLIC_SURFACE_MATRIX.md](../audits/PUBLIC_SURFACE_MATRIX.md) | S09–S11 surfaces + conflict IDs |
| [GLOSSARY.md](./GLOSSARY.md) | MCP++ vocabulary |
| [MCP_SERVER_MIGRATION_GUIDE.md](../MCP_SERVER_MIGRATION_GUIDE.md) | Legacy-tree migration narrative (may conflict with packaging; do not treat as ADR acceptance) |
| `ipfs_kit_py/mcp_server/README.md` | In-tree developer notes; tool counts may be stale |
| Planned `docs/api/mcp_reference.md` | User/API reference (KDOC-033) |

---

## Appendix A — Stock JSON-RPC methods (MCP++)

| Method | Role |
|---|---|
| `initialize` | Protocol version, server info, experimental MCP++ capabilities / profile metadata |
| `tools/list` | All `TOOL_GROUPS` schemas + receipt descriptor |
| `tools/call` | Dispatch registry tool or receipt read; optional `_mcppp_envelope` |
| `ping` | Liveness |
| `mcp++/interfaces` | Profile A interface descriptors from registry |
| `mcp++/dag/frontier` | Event DAG frontier |
| `mcp++/ucan/validate`, `mcp++/ucan/delegate` | Delegation chain hooks |
| `mcp++/policy/evaluate` | Deny-list / risk threshold policy |
| `mcp++/goals/*`, `mcp++/tasks/*`, `mcp++/risk/*`, `mcp++/neighborhood/*`, `mcp++/schedule/*` | Profile G dispatcher |
| `agent_supervisor.receipts.read` | Fail-closed receipt resolution |
| `notifications/*` | Lifecycle notifications (no response) |

## Appendix B — Conflict index (MCP-related)

| ID | Summary |
|---|---|
| **C-MCP-TOOLS** | Registry **29** vs JS manifest **28** vs FastMCP e2e assert **28** vs README **21/7** |
| **C-MCP-TREES** | Packaging → `mcp_server` vs large `mcp/` / root `mcp/` / `servers/` / migration-guide unified server |
| **U-11** | Production MCP runtime authority (ADR-0003) |
| **U-08** | Cluster control plane vs MCP++ coordination (ADR-0008; not decided here) |
