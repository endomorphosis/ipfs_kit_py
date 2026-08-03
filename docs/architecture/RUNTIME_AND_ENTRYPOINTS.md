# Runtime composition and entry points

| Field | Value |
|---|---|
| Task | KDOC-011 — Document runtime composition and entry points |
| Goal | KDOC-G021 |
| Track | arch-runtime |
| Authority class | Canonical architecture guide (runtime composition; not an accepted ADR for disputed authorities) |
| Baseline | Repository inspection 2026-08-03; packaging `pyproject.toml` `0.3.0`; evidence from KDOC-002 / KDOC-004 |
| Scope | Supported packaging entry points, major Python import paths, process/event-loop ownership, initialization, state/config, degradation, shutdown, and source/test anchors |
| Non-goals | Resolve disputed MCP/API authority; rewrite source; promote historical servers; classify every inactive artifact (see `COMPATIBILITY_LAYERS.md`) |

**Related evidence**

- [`docs/audits/PUBLIC_SURFACE_MATRIX.md`](../audits/PUBLIC_SURFACE_MATRIX.md) — surface catalog and conflict IDs (`C-*`)
- [`docs/architecture/SOURCE_OF_TRUTH_MAP.md`](./SOURCE_OF_TRUTH_MAP.md) — candidate authorities and tests
- [`docs/architecture/GLOSSARY.md`](./GLOSSARY.md) — shared vocabulary
- Planned siblings: `SYSTEM_OVERVIEW.md`, `COMPATIBILITY_LAYERS.md`, `MCP_CONTROL_PLANE.md`, `ASYNC_AND_OPTIONAL_DEPENDENCIES.md`

This guide answers: *which process owns the event loop, how does it start and stop, what state it needs, and what still works when optional pieces are missing?*

---

## 1. How to read each entry-point profile

Every supported entry below uses the same fields required by KDOC-011 acceptance:

| Field | Meaning |
|---|---|
| **Identity** | Console script, packaging entry point, or primary Python import path |
| **Status** | `canonical`, `compatibility`, `optional`, `experimental`, `historical`, `stub`, or `unresolved` (same vocabulary as the public surface matrix) |
| **Process / event-loop ownership** | Who creates the OS process and which async runtime (if any) owns the loop |
| **Initialization** | Ordered startup steps before the entry is ready for work |
| **State / config dependencies** | Env vars, dirs, ports, binaries, and config documents |
| **Optional degradation** | Fail-soft vs fail-closed behavior when extras, binaries, or services are absent |
| **Shutdown** | How the entry exits cleanly (signals, stop commands, object teardown) |
| **Source / tests** | Implementation paths and focused tests under default pytest discovery |

**Status vocabulary is not an ADR.** Where packaging and in-tree trees disagree (especially MCP), this guide names the **packaged** path as the default product entry and marks competing trees as compatibility/historical or unresolved.

---

## 2. Runtime composition overview

```text
                         ┌─────────────────────────────────────┐
                         │  Packaging (pyproject.toml 0.3.0)   │
                         │  [project.scripts] + fsspec.specs   │
                         └─────────────────┬───────────────────┘
                                           │
     ┌──────────────┬──────────────────────┼──────────────────────┬──────────────┐
     ▼              ▼                      ▼                      ▼              ▼
 ipfs-kit     ipfs-kit-mcp          ipfs-kit-mcp-tools      ipfs-kit-iroh*    fsspec
 FastCLI      MCP++ server          Hierarchical tools      Iroh CLIs         iroh / iroh+blob
 anyio        anyio+trio            anyio+trio              sync / asyncio    caller process
     │              │                      │                      │              │
     └──────┬───────┴──────────┬───────────┴──────────┬───────────┘              │
            ▼                  ▼                      ▼                          ▼
     ┌────────────┐    ┌──────────────┐      ┌────────────────┐         ┌──────────────┐
     │ Domain ops │    │ TOOL_GROUPS  │      │ Iroh service / │         │ IrohFileSystem│
     │ bucket/vfs │    │ Hierarchical │      │ binary / state │         │ (fsspec API)  │
     │ wal/pin/…  │    │ ToolManager  │      └────────────────┘         └──────────────┘
     └─────┬──────┘    └──────┬───────┘
           │                  │
           ▼                  ▼
     ┌────────────────────────────────────────────┐
     │ Shared library core (import-time lazy)     │
     │ __init__.py JIT, ipfs_kit, high_level_api, │
     │ backends, WAL, VFS, daemon managers        │
     └────────────────────────────────────────────┘
```

**Composition rules**

1. **Packaging is the product map.** Only scripts and fsspec protocols declared in `pyproject.toml` are guaranteed installable entry points. Sibling `*_cli.py` modules may work when imported but are not all console-scripted.
2. **One MCP tool registry.** `TOOL_GROUPS` in `ipfs_kit_py/mcp_server/tools/__init__.py` feeds `HierarchicalToolManager`, JSON-RPC (`ipfs-kit-mcp`), tools CLI (`ipfs-kit-mcp-tools`), FastMCP registrar, and the JS SDK generator.
3. **CLI is composite.** Console `ipfs-kit` owns process lifecycle for operator commands; domain families are selectively mounted from `UnifiedCLIDispatcher`.
4. **Import is lazy.** `import ipfs_kit_py` aims to stay light; heavy kits, HLA, and optional integrations load on first use via JIT / proxies.
5. **External daemons are opt-in.** Kubo/Lotus/Iroh binaries are not installed at import time by default (`IPFS_KIT_AUTO_INSTALL_BINARIES` defaults off).

### 2.1 Process models at a glance

| Model | Typical entries | Event loop |
|---|---|---|
| **Short-lived CLI process** | `ipfs-kit <cmd>`, `ipfs-kit-mcp-tools`, Iroh install/ops/manifest CLIs | anyio (default backend) or `asyncio.run` for the command duration; process exits when the command returns |
| **Long-lived MCP++ server** | `ipfs-kit-mcp` | `anyio.run(..., backend="trio")` owns the process for stdio, HTTP (Hypercorn trio worker), or P2P |
| **Background child process** | `ipfs-kit mcp start` (non-foreground) | Parent CLI spawns another `python -m ipfs_kit_py.cli mcp start --foreground` with PID under `~/.ipfs_kit` |
| **In-process library** | `import ipfs_kit_py`, `IPFSSimpleAPI`, `ipfs_kit`, fsspec | No new process; caller owns any event loop. Library may create daemons as *child* processes when asked |
| **External service processes** | Kubo (`ipfs daemon`), Lotus, managed Iroh binary | Separate OS processes; kit managers start/stop/status them |

### 2.2 Declared packaging surface (canonical map)

**Console scripts** (`[project.scripts]`):

| Script | Target | Role |
|---|---|---|
| `ipfs-kit` | `ipfs_kit_py.cli:sync_main` | Operator CLI (FastCLI) |
| `ipfs-kit-mcp` | `ipfs_kit_py.mcp_server.server:main` | MCP++ JSON-RPC server |
| `ipfs-kit-mcp-tools` | `ipfs_kit_py.mcp_server.cli:main` | One-shot tool CLI over same registry |
| `ipfs-kit-iroh` | `ipfs_kit_py.iroh_install_cli:main` | Managed Iroh binary install lifecycle |
| `ipfs-kit-iroh-ops` | `ipfs_kit_py.iroh.cli:main` | Iroh service operations CLI |
| `ipfs-kit-iroh-diagnostics` | `ipfs_kit_py.iroh.diagnostics_cli:main` | Iroh health / observability dump |
| `ipfs-kit-iroh-manifest` | `ipfs_kit_py.iroh.manifest_cli:main` | Manifest migrate / recover |
| `ipfs-kit-iroh-interop` | `ipfs_kit_py.iroh.multinode:main` | Opt-in multi-node interop harness |

**fsspec entry points** (`[project.entry-points."fsspec.specs"]`):

| Protocol | Target |
|---|---|
| `iroh` | `ipfs_kit_py.iroh_fsspec:IrohFileSystem` |
| `iroh+blob` | `ipfs_kit_py.iroh_fsspec:IrohFileSystem` |

There is **no** packaging console script named `ipfs-kit-install` (**C-INSTALL-DOC**). Use module installers or `ipfs-kit-iroh` for Iroh binaries.

### 2.3 Shared environment and state roots

| Concern | Default / key env | Notes |
|---|---|---|
| Kit state root | `~/.ipfs_kit` | Backend YAML, MCP PID/logs, `StateService`, CLI `--data-dir` |
| Binary directory | `IPFS_KIT_BIN_DIR` (else package-managed / platform default) | Kubo and Iroh install managers |
| Auto-install binaries | `IPFS_KIT_AUTO_INSTALL_BINARIES` (default **off** / falsy) | Setup/import must not download unless opted in |
| Kubo auto-upgrade | `IPFS_KIT_AUTO_UPGRADE_KUBO` (default on when install path runs) | See `kubo_runtime.py` |
| Fast init (tests / CLI) | `IPFS_KIT_FAST_INIT` | Set by CLI under pytest for MCP start |
| Dashboard server file | `IPFS_KIT_SERVER_FILE` / `--server-path` | Only for `ipfs-kit mcp start` dashboard path |
| Kubo repo | `~/.ipfs` (Kubo default; not kit state root) | Distinct from `~/.ipfs_kit` |
| MCP++ HTTP bind | `127.0.0.1:8004` | `ipfs-kit-mcp --transport http` and CLI MCP defaults |
| Kit daemon API | `0.0.0.0:9999` | `ipfs-kit daemon start` (legacy `IPFSKitDaemon`) |

---

## 3. Python package import and library façade

### 3.1 Package root — `import ipfs_kit_py`

| Field | Detail |
|---|---|
| **Identity** | `import ipfs_kit_py` / `from ipfs_kit_py import …` |
| **Status** | **canonical** package root; version string **unresolved** vs packaging (**C-VER**: `__version__ = "0.2.0"` in `__init__.py` vs packaging `0.3.0`) |
| **Process / event-loop ownership** | None. Runs in the caller process. Import path is synchronous. |
| **Initialization** | Loads JIT core (`jit_manager`, `require_feature`, `optional_feature`), wires lazy proxies for kits/installers/HLA/WAL helpers. Does **not** download binaries by default (`_DOWNLOAD_BINARIES_AUTOMATICALLY = False`). |
| **State / config dependencies** | Optional env for installers if later triggered. No mandatory on-disk state for a bare import. |
| **Optional degradation** | Missing optional extras leave lazy getters / feature gates fail-soft until first use. Root `__all__` is P2P/JIT-centric and does **not** list popular lazy symbols such as `IPFSSimpleAPI` or `ipfs_kit` (**C-EXPORT**). |
| **Shutdown** | N/A at import level. Callers dispose of constructed objects and stop any daemons they started. |
| **Source / tests** | `ipfs_kit_py/__init__.py`, `ipfs_kit_py/core/`, `jit_imports.py`, `deps_resolver.py`. Tests: `tests/test_ipfs_kit_import.py`, `tests/test_import_paths_validation.py`, `tests/test_cli_import_verification.py`, `tests/test_architecture_support.py`. |

### 3.2 Primary kit orchestrator — `ipfs_kit`

| Field | Detail |
|---|---|
| **Identity** | `from ipfs_kit_py.ipfs_kit import ipfs_kit` or lazy `get_ipfs_kit()` / package proxy |
| **Status** | **canonical** library orchestrator for multi-role IPFS + optional cluster/storage features |
| **Process / event-loop ownership** | Library object in the caller process. May spawn or attach to **external** Kubo/cluster daemons when `auto_start_daemons` / `initialize(start_daemons=…)` is enabled. Does not own a long-lived asyncio loop by itself. |
| **Initialization** | Constructor accepts `resources`, `metadata` (role, feature flags), and feature toggles (`enable_libp2p`, `enable_cluster_management`, `enable_metadata_index`, `auto_start_daemons`). Factory `ipfs_kit.create(role=…, auto_start_daemons=…)` optionally runs `initialize()` and requires daemon health when auto-start is true. Underlying client: `ipfs_py` from `ipfs_kit_py/ipfs.py` (**C-IPFS-CLIENT** names parallel clients that must not be treated as equal defaults). |
| **State / config dependencies** | Role in metadata; Kubo API/repo; optional cluster binaries; cache and metadata indexes; env binary policy (`IPFS_KIT_*`). MCP core ops intentionally use `ipfs_kit.create(auto_start_daemons=False)` (or a stub kit) to avoid surprise daemon launches. |
| **Optional degradation** | Features gated by role and availability of cluster/libp2p/storage kits. Missing binaries surface as failed daemon status rather than always raising at construct time when auto-start is off. |
| **Shutdown** | `stop_daemons()`, `stop_background_state_updates()`, and related teardown methods. Callers should stop background tasks before process exit. |
| **Source / tests** | `ipfs_kit_py/ipfs_kit.py`, `ipfs_kit_py/ipfs.py`, `kubo_runtime.py`, daemon managers. Tests: daemon unit suite (`tests/unit/test_daemon_*.py`), `tests/test_daemon_*.py`, kit integration tests. |

### 3.3 High-level API — `IPFSSimpleAPI` (dual path **C-HLA**)

| Field | Detail |
|---|---|
| **Identity** | `from ipfs_kit_py.high_level_api import IPFSSimpleAPI` (package). Legacy implementation file: `ipfs_kit_py/high_level_api.py` loaded under `sys.modules` name `ipfs_kit_py._high_level_api_impl` so it does not clobber the package. |
| **Status** | **canonical import name** is the package; runtime body is the legacy module when load succeeds; otherwise a **stub** with `available = False` (**C-HLA** / **U-03** unresolved long-term shape). |
| **Process / event-loop ownership** | Caller process. Package import avoids heavy dependency pull; first instantiation may load the large legacy module and optional stacks (FastAPI, WebRTC helpers, etc.). Dual `*_anyio` helpers exist for some subfeatures. |
| **Initialization** | `IPFSSimpleAPI.__new__` → `_try_load_ipfs_simple_api()` → if load fails, stub `__init__` sets `available = False` and methods return structured failure dicts. Optional libp2p integration initializes only when deps exist. |
| **State / config dependencies** | Depends on loaded impl: often kit config, optional API extras, local services. Stub path needs none. |
| **Optional degradation** | Explicit stub when legacy load fails (e.g. missing `fastapi` and auto-ensure fails). Method calls on stub return `{success: False, warning: …}` rather than raising ImportError at call sites. |
| **Shutdown** | Implementation-specific; stub has no resources. Full impl may hold clients/daemons—callers should use documented close/stop patterns on the live object. |
| **Source / tests** | `ipfs_kit_py/high_level_api/__init__.py`, `ipfs_kit_py/high_level_api.py`. Tests: high-level API integration and import verification suites under `tests/`. |

---

## 4. Operator CLI — `ipfs-kit` (FastCLI)

| Field | Detail |
|---|---|
| **Identity** | Console: `ipfs-kit …`; module: `python -m ipfs_kit_py.cli …`; packaging target `ipfs_kit_py.cli:sync_main` |
| **Status** | **canonical** operator CLI. Composition with `UnifiedCLIDispatcher` is partial (**C-CLI**). |
| **Process / event-loop ownership** | `sync_main()` configures Windows event-loop policy when needed, then `anyio.run(main)`. Async `main()` constructs `FastCLI` and `await cli.run()`. **The CLI process owns the anyio loop for the lifetime of one command** (except when it deliberately spawns a background child—see MCP start). Default anyio backend (not forced to trio). |
| **Initialization** | 1) Parse argv. 2) Fast path for lightweight `mcp` actions skips auto-heal import. 3) Otherwise load auto-heal config/error capture. 4) For most commands (not MCP start/stop/status/deprecations), attempt `initialize_backend_config(log_status=False)` and ignore failures. 5) Route: unified families → `UnifiedCLIDispatcher.dispatch`; else FastCLI handlers. |
| **State / config dependencies** | `~/.ipfs_kit` (data-dir, PID files, backend configs); auto-heal config file when used; service binaries for `services`; optional GitHub token/repo for autoheal. |
| **Optional degradation** | Unified command mount fails soft at parser build (`ImportError` logged). Missing unified dispatcher at run time exits with code 2. Auto-heal issue creation failures are logged; original CLI exception still propagates. Backend config init failures are ignored so MCP readiness checks stay fast. |
| **Shutdown** | Process exit when command completes. Background MCP child: `ipfs-kit mcp stop` sends SIGTERM/SIGINT using PID file. Services: manager `stop_daemon` / Lotus `daemon_stop`. No global atexit registry for all subcommands. |
| **Source / tests** | `ipfs_kit_py/cli.py` (`FastCLI`, `main`, `sync_main`), `unified_cli_dispatcher.py`. Tests: `tests/test_cli_import_verification.py`, `tests/test_cli_integration.py`, `tests/test_cli_access_methods.py`, `tests/test_cli_deprecations_*.py`, `tests/unit/test_minimal_cli.py`, `tests/unit/test_cli_integration_phase8_10_comprehensive.py`. |

### 4.1 Built-in FastCLI command families

| Command | Ownership notes | Init / state | Shutdown |
|---|---|---|---|
| `mcp start\|stop\|status\|deprecations` | **Not** the packaged MCP++ server. Resolves a **dashboard** script (`--server-path`, `IPFS_KIT_SERVER_FILE`, or packaged `mcp/dashboard/*` candidates) and runs it in-foreground or as a detached child re-entering this CLI. PID: `~/.ipfs_kit/mcp_<port>.pid`. Port default **8004**. | Data dir created; pytest forces fast-init and often foreground. Deprecations can operate without a live server for report generation. | `mcp stop` signals PID; unlinks PID file. Foreground: Ctrl-C / process death ends dashboard. |
| `daemon start` | Starts **legacy** `IPFSKitDaemon` from `ipfs_kit_py.mcp.ipfs_kit.daemon` (coupling packaged CLI to historical tree—**C-MCP-TREES** / unresolved daemon path). Host default `0.0.0.0`, port **9999**, config `/tmp/ipfs_kit_config`. | Import daemon class; `await daemon.start()` on the CLI anyio loop. | Process-bound; stop path is the daemon process lifecycle (not a separate FastCLI stop subcommand in the same parser tree). |
| `services start\|stop\|restart\|status` | Child **Kubo** via `EnhancedDaemonManager`; **Lotus** via `lotus_daemon`. Choices: `ipfs`, `lotus`, `all`. | Needs binaries on PATH or managed bin dir. | Explicit stop/restart handlers; force flag for Lotus. |
| `autoheal …` | Configures error capture → GitHub issues. | Config file via `AutoHealConfig`. | Config-only; no long-running worker in this CLI. |
| `bucket`, `vfs`, `wal`, `pin`, `backend`, `journal`, `state` | Mounted from `UnifiedCLIDispatcher`; each command runs domain handlers then exits. | Domain modules + backend init (unless skipped). | Domain-specific resource cleanup inside handlers. |

**Not mounted into FastCLI (library-only until wired):** unified `audit` tree; unified alternate `daemon` tree (**C-CLI**).

### 4.2 Unified CLI dispatcher (library composition layer)

| Field | Detail |
|---|---|
| **Identity** | `ipfs_kit_py.unified_cli_dispatcher.UnifiedCLIDispatcher` |
| **Status** | **canonical design** for domain subcommands; **partial** as sole CLI (product entry remains FastCLI) |
| **Process / event-loop ownership** | Invoked under the parent FastCLI anyio task when mounted; `unified_cli_dispatcher.main()` exists for direct module use but is not a packaging script. |
| **Initialization / degradation** | Per-domain imports; missing domain modules fail that command family. FastCLI catches import errors when mounting. |
| **Shutdown** | Returns control to FastCLI; no independent daemon. |
| **Source / tests** | `ipfs_kit_py/unified_cli_dispatcher.py`. Exercised indirectly by CLI integration and domain tests. |

### 4.3 Satellite CLIs (not packaging scripts)

Modules such as `backend_cli.py`, `bucket_vfs_cli.py`, `daemon_cli.py`, `wal_cli.py`, `audit_cli.py`, and `cli/*` may be importable or runnable as modules. Treat them as **compatibility / experimental / historical** unless a console script points at them. Prefer `ipfs-kit` + Iroh/MCP packaging scripts for operator workflows.

---

## 5. MCP++ control plane

### 5.1 Packaged server — `ipfs-kit-mcp`

| Field | Detail |
|---|---|
| **Identity** | Console: `ipfs-kit-mcp [--transport stdio\|http\|p2p] [--host] [--port]`; `ipfs_kit_py.mcp_server.server:main` |
| **Status** | **canonical** packaged MCP++ / JSON-RPC control plane for new agent integrations. Sole production runtime vs legacy trees remains **unresolved** at ADR level (**C-MCP-TREES** / U-11)—do not treat `ipfs_kit_py.mcp/`, root `mcp/`, or `servers/` as equal defaults. |
| **Process / event-loop ownership** | **Process-owned trio loop:** `main()` → `anyio.run(serve_*, backend="trio")`. Stdio: line-oriented JSON-RPC on stdin/stdout. HTTP: Hypercorn trio worker + ASGI app from `create_http_app()`. P2P: `p2p_transport.serve_p2p` with `MCPServer.handle`. All transports share one `MCPServer` async core. |
| **Initialization** | Construct `MCPServer` → `HierarchicalToolManager` + in-memory `EventDAGStore` + `AgentSupervisorReceiptResolver`. MCP `initialize` advertises protocol `2025-06-18`, server info `ipfs_kit_py-mcpplusplus`, tools capability, and experimental MCP++ profiles (`mcp++/event-dag`, `mcp++/risk-scheduling`). Tools resolve from `TOOL_GROUPS` (12 groups / **29** tools at baseline; JS manifest may lag—**C-MCP-TOOLS**). |
| **State / config dependencies** | Default HTTP bind `127.0.0.1:8004`. Tool backends often need live IPFS/Iroh. Receipts/coordination stores depend on MCP++ profile modules. No separate PID file for `ipfs-kit-mcp` itself (process is the server). |
| **Optional degradation** | Unknown notifications ignored. MCP++ envelope/UCAN/policy paths fail per request when invalid. HTTP Profile G REST bindings map onto the same JSON-RPC router. P2P requires libp2p stack. Missing tool backends return tool-level errors, not necessarily process crash. |
| **Shutdown** | Process signal / stdin EOF (stdio). Hypercorn lifespan `shutdown` for HTTP. No multi-worker orchestration in `main()`. |
| **Source / tests** | `ipfs_kit_py/mcp_server/server.py`, `hierarchical_tool_manager.py`, `tools/__init__.py`, `mcplusplus/`, `agent_supervisor_receipts.py`, `p2p_transport.py`. Tests: `tests/test_mcp_jsonrpc_conformance.py`, `tests/test_mcp_server_integration.py`, `tests/test_mcp_initialization.py`, `tests/test_agent_supervisor_receipts.py`, `ipfs_kit_py/mcp_server/tests_e2e_interop.py` (stdio/HTTP/FastMCP/JS). |

**CLI form**

```bash
ipfs-kit-mcp                          # stdio (default) — agent host pipes JSON-RPC
ipfs-kit-mcp --transport http --port 8004
ipfs-kit-mcp --transport p2p
```

### 5.2 Tools CLI — `ipfs-kit-mcp-tools`

| Field | Detail |
|---|---|
| **Identity** | `ipfs-kit-mcp-tools <category> <tool> [--key val …]`; `ipfs_kit_py.mcp_server.cli:main` |
| **Status** | **canonical** one-shot CLI over the **same** registry as the server |
| **Process / event-loop ownership** | Short-lived process. `anyio.run(tm.dispatch, …, backend="trio")` for a single tool call. |
| **Initialization** | Build `HierarchicalToolManager`, parse category/tool/flags (JSON-decode values when possible). |
| **State / config dependencies** | Same backend needs as the invoked tool (IPFS node, etc.). |
| **Optional degradation** | Help/list without tool execution. Non-success tool status → exit code 1. |
| **Shutdown** | Process exit after printing JSON result. |
| **Source / tests** | `ipfs_kit_py/mcp_server/cli.py`. Tests: MCP tools suites (`tests/test_mcp_tools_*.py`, `tests/test_comprehensive_tools.py`, `tests/test_tools_call_payload_parsing.py`). |

### 5.3 FastMCP registrar and JS/TS SDK (library / generated)

| Field | Detail |
|---|---|
| **Identity** | `from ipfs_kit_py.mcp_server.fastmcp_app import register_fastmcp, build_app`; JS SDK under `mcp_server/js_sdk/` (generated manifest) |
| **Status** | FastMCP = **compatibility** over the same registry; JS/TS = **generated** companion (**C-MCP-TOOLS** drift possible) |
| **Process / event-loop ownership** | Host FastMCP / Node process owns the loop. Registrar only attaches handlers. |
| **Initialization** | `register_fastmcp(app)` iterates `tm.all_tool_schemas()` and `app.add_tool(...)`. |
| **Optional degradation** | Requires `mcp` Python package for `build_app`. Manifest lag does not change Python registry authority. |
| **Shutdown** | Host application responsibility. |
| **Source / tests** | `mcp_server/fastmcp_app.py`, `js_sdk/`. Tests in `tests_e2e_interop.py` (`test_fastmcp_registrar_*`, SDK mirror tests). |

### 5.4 CLI dashboard path vs packaged MCP++ (do not conflate)

| Path | Entry | What it runs |
|---|---|---|
| Packaged MCP++ | `ipfs-kit-mcp` | `MCPServer` JSON-RPC + MCP++ profiles |
| Operator dashboard CLI | `ipfs-kit mcp start` | Discovers/loads a **dashboard** Python file (often under `ipfs_kit_py/mcp/dashboard/`) — **legacy/compatibility** stack |
| Unpackaged servers | `servers/*.py`, root shims | Historical / experimental; not packaging scripts |

For agent JSON-RPC and MCP++ profiles, prefer **`ipfs-kit-mcp`**. For dashboard UI workflows still on the legacy tree, use `ipfs-kit mcp …` knowing authority is unresolved.

---

## 6. Iroh entry points

### 6.1 Binary lifecycle — `ipfs-kit-iroh`

| Field | Detail |
|---|---|
| **Identity** | `ipfs-kit-iroh {install\|inspect\|update\|rollback}`; `ipfs_kit_py.iroh_install_cli:main` |
| **Status** | **canonical** managed Iroh sidecar install |
| **Process / event-loop ownership** | Synchronous CLI process; no asyncio loop. Mutating commands may download and replace binaries on disk. |
| **Initialization** | Parse args → `IrohInstallManager(bin_dir=…)` → command method. |
| **State / config dependencies** | `--bin-dir` / `IPFS_KIT_BIN_DIR`; version pins; digest verification; lock files for concurrent updates. |
| **Optional degradation** | `--dry-run` and `--check` without mutation. Errors → stderr + exit 1 (`IrohInstallError`). |
| **Shutdown** | Process exit after JSON result print. |
| **Source / tests** | `ipfs_kit_py/iroh_install_cli.py`. Tests: `tests/test_install_iroh.py`, packaging/Iroh readiness tests, `tests/test_iroh_*.py` install-related cases. |

### 6.2 Service operations — `ipfs-kit-iroh-ops`

| Field | Detail |
|---|---|
| **Identity** | `ipfs-kit-iroh-ops …`; `ipfs_kit_py.iroh.cli:main` |
| **Status** | **canonical** Iroh ops CLI |
| **Process / event-loop ownership** | Process owns `asyncio.run(execute(...))` for the command. Sync bridge helpers exist for mixed call sites. Client closed via `_close_client` paths after work. |
| **Initialization** | `CLIContext` + parser (including legacy argv normalization) → async `execute`. |
| **State / config dependencies** | Iroh service config / instance / state root (see `iroh/config.py`, service configuration docs under `docs/iroh/`). |
| **Optional degradation** | Structured JSON envelopes for partial failure (`ok: false`, exit codes for failed/interrupted). KeyboardInterrupt → clean JSON error. Sensitive errors sanitized in some paths. |
| **Shutdown** | Async client close; process exit with success/failed/interrupted codes. |
| **Source / tests** | `ipfs_kit_py/iroh/cli.py`. Tests: broad `tests/test_iroh_*.py` CLI coverage. |

### 6.3 Diagnostics — `ipfs-kit-iroh-diagnostics`

| Field | Detail |
|---|---|
| **Identity** | `ipfs-kit-iroh-diagnostics`; `ipfs_kit_py.iroh.diagnostics_cli:main` |
| **Status** | **canonical** observability dump |
| **Process / event-loop ownership** | `asyncio.run(run(...))` for diagnostics/prometheus generation. |
| **Initialization** | Load `IrohServiceConfig` (file or default instance/state-root). |
| **State / config dependencies** | Instance, state root, optional config path; may persist health receipt unless `--no-persist`. |
| **Optional degradation** | Configuration errors exit 2 without echoing secrets; general failures exit 1 with generic message (no ticket/path leak). |
| **Shutdown** | Process exit after writing JSON or Prometheus text to stdout. |
| **Source / tests** | `ipfs_kit_py/iroh/diagnostics_cli.py`. Tests: Iroh observability/diagnostics tests under `tests/test_iroh_*.py`. |

### 6.4 Manifest — `ipfs-kit-iroh-manifest`

| Field | Detail |
|---|---|
| **Identity** | `ipfs-kit-iroh-manifest {migrate\|recover}`; `ipfs_kit_py.iroh.manifest_cli:main` |
| **Status** | **canonical** for schema migrate / namespace recover helpers |
| **Process / event-loop ownership** | Sync migrate; recover uses `asyncio.run(recover_namespace(...))` when an authenticated client factory is supplied. |
| **Initialization / degradation** | Recover without client factory errors as configuration. Exceptions do not echo secret-bearing paths. |
| **Shutdown** | Process exit after JSON receipt/path output. |
| **Source / tests** | `ipfs_kit_py/iroh/manifest_cli.py`. Tests: Iroh manifest/recovery-related tests. |

### 6.5 Multi-node interop — `ipfs-kit-iroh-interop`

| Field | Detail |
|---|---|
| **Identity** | `ipfs-kit-iroh-interop`; `ipfs_kit_py.iroh.multinode:main` |
| **Status** | **optional / experimental** harness (opt-in env), not a production service |
| **Process / event-loop ownership** | `asyncio.run(run_from_environment())` or evidence validation only. May orchestrate multiple real Iroh nodes when enabled. |
| **Initialization** | Env-gated config (`OPT_IN_ENV` / driver env in module); or `--check-evidence` for offline validation. |
| **Optional degradation** | Configuration/driver errors → exit 2; failed scenarios → exit 1 with JSON evidence. |
| **Shutdown** | Harness tears down planned resources; process exits. |
| **Source / tests** | `ipfs_kit_py/iroh/multinode.py`. Tests: multinode/interop Iroh tests (often env-gated). |

---

## 7. Filesystem / fsspec protocols

### 7.1 Packaged Iroh fsspec — `iroh` / `iroh+blob`

| Field | Detail |
|---|---|
| **Identity** | `fsspec` open URLs `iroh://…`, `iroh+blob://…` via packaging entry points → `IrohFileSystem` |
| **Status** | **canonical packaging** for fsspec protocols |
| **Process / event-loop ownership** | Runs **in the caller process**. Sync fsspec API bridges to async Iroh client methods; does not start a global server loop. Import of `iroh_fsspec` is intended to be free of mandatory service side effects. |
| **Initialization** | fsspec loads `IrohFileSystem` from entry point metadata; constructor binds storage options / namespace configuration. |
| **State / config dependencies** | Iroh service/binary, manifests, credentials per Iroh security docs. Extra: `fsspec` (+ often `requests-unixsocket`). |
| **Optional degradation** | Without Iroh service, operations fail at call time. Without `fsspec` extra, packaging entry may still be declared but import fails for consumers. |
| **Shutdown** | Close open file handles (`close` on file-like objects); dispose filesystem instance. No process-level daemon from the entry point itself. |
| **Source / tests** | `ipfs_kit_py/iroh_fsspec.py`, `iroh_vfs.py`. Tests: `tests/test_iroh_fsspec_*.py`, `tests/test_iroh_fsspec_registration.py`, `tests/test_iroh_fsspec_async.py`. |

### 7.2 Non-packaged IPFS / multi-protocol fsspec (**C-FSSPEC**)

| Path | Status | Notes |
|---|---|---|
| `ipfs_kit_py/ipfs_fsspec.py` | In-tree; **not** in `[project.entry-points."fsspec.specs"]` | Classic IPFS filesystem modules |
| `ipfs_kit_py/enhanced_fsspec.py` | Import-time `fsspec.register_implementation` for `ipfs`, `filecoin`, `storacha`, `synapse` | Runtime registration can clobber; not packaging-declared |
| Vendored fsspec under `ipfs_kit_py/_vendor/fsspec` | Fallback for constrained environments | Not a product protocol brand |

Authority between classic and enhanced IPFS fsspec remains **unresolved**. Prefer documented Iroh packaging protocols for guaranteed discovery via fsspec entry points.

---

## 8. Daemons, installers, and external services

### 8.1 Service control composition

| Entry | Manager / module | Owns process? |
|---|---|---|
| `ipfs-kit services …` | `EnhancedDaemonManager` (IPFS), `lotus_daemon` (Lotus) | Starts/stops **external** daemon processes |
| `ipfs-kit daemon start` | Legacy `IPFSKitDaemon` | Long-lived API server on CLI loop |
| Library `ipfs_kit` | Role-aware daemon start via kit + managers | Optional child daemons |
| Kubo resolution | `kubo_runtime.py`, `install_ipfs.py` | Binary location + opt-in install |
| Parallel managers | `intelligent_daemon_manager.py`, `enhanced_daemon_manager.py`, cluster variants | **Unresolved** single “the” manager (**SOURCE_OF_TRUTH_MAP** §5/§9) |

### 8.2 Installer modules (library + root shims)

| Field | Detail |
|---|---|
| **Identity** | `ipfs_kit_py.install_ipfs` / `install_lotus` / `install_lassie` / `install_storacha` / Iroh install CLI; root `install_ipfs.py`, `install_lotus.py` wrappers |
| **Status** | **canonical** package modules; root scripts are thin shims |
| **Process / event-loop ownership** | Sync installers in caller process; may download artifacts when invoked. |
| **Initialization / policy** | `IPFS_KIT_AUTO_INSTALL_BINARIES` must be truthy for automatic paths; documentation validation sets it to `0`. |
| **Optional degradation** | Fail-soft warnings in setup hooks when auto-install disabled or network fails. |
| **Shutdown** | N/A after files written. |
| **Source / tests** | `install_*.py`, `setup.py` hooks, `tests/test_installers.py`, `tests/test_auto_install_binaries.py`, `tests/test_install_with_version_check.py`. |

---

## 9. Cross-cutting lifecycle matrix

| Entry point | Loop owner | Long-lived? | Default fail mode when optional missing |
|---|---|---|---|
| `import ipfs_kit_py` | Caller | No | Lazy stubs / deferred import errors |
| `ipfs_kit` / HLA | Caller (+ child daemons) | Object lifetime | Feature-off or structured failure |
| `ipfs-kit` CLI | anyio in CLI process | Per command (except background MCP child) | Exit codes; skip optional mounts |
| `ipfs-kit-mcp` | anyio **trio** in server process | Yes | Tool/request errors; process stays up |
| `ipfs-kit-mcp-tools` | anyio **trio** per call | No | Exit 1 on tool failure |
| FastMCP / JS SDK | Host process | Host-defined | Import/registry drift |
| `ipfs-kit-iroh` | Sync process | No | Exit 1 + error JSON/text |
| `ipfs-kit-iroh-ops` | asyncio per command | No | Structured `ok: false` envelopes |
| `ipfs-kit-iroh-diagnostics` | asyncio | No | Generic exit 1/2 |
| `ipfs-kit-iroh-manifest` | sync / asyncio | No | Exit 1 sanitized |
| `ipfs-kit-iroh-interop` | asyncio | Harness duration | Exit 1/2 + evidence |
| fsspec `iroh*` | Caller | Handle lifetime | Call-time I/O errors |

### 9.1 Async backend summary

| Surface | Backend |
|---|---|
| MCP++ server & tools CLI | **trio** via `anyio.run(..., backend="trio")` |
| Operator `ipfs-kit` | anyio **default** (typically asyncio unless configured) |
| Iroh ops / diagnostics / interop | **asyncio.run** |
| Library dual modules | `foo.py` + `foo_anyio.py` pattern widespread; not every path is AnyIO-complete (see planned `ASYNC_AND_OPTIONAL_DEPENDENCIES.md`) |

---

## 10. Decision guide (pick an entry point)

| Goal | Prefer | Avoid / caution |
|---|---|---|
| Embed kit in Python app | `ipfs_kit` / `IPFSSimpleAPI` with explicit daemon policy | Surprise `auto_start_daemons=True` in libraries |
| Operator CLI for buckets, VFS, WAL, pins, backends | `ipfs-kit <family> …` | Assuming unified `audit` is wired |
| MCP agent host (JSON-RPC / MCP++) | **`ipfs-kit-mcp`** (stdio default) | Assuming `ipfs-kit mcp start` is the same server |
| One-shot MCP tool from shell | `ipfs-kit-mcp-tools <category> <tool>` | Hand-maintained parallel tool lists |
| FastMCP host process | `register_fastmcp` / `build_app` | Second tool registry |
| Manage Iroh binary | `ipfs-kit-iroh` | Nonexistent `ipfs-kit-install` script |
| Iroh day-2 ops / health | `ipfs-kit-iroh-ops`, `ipfs-kit-iroh-diagnostics` | Ad-hoc binary flags without kit config |
| fsspec open for Iroh | `iroh://` / `iroh+blob://` | Assuming packaging also declares `ipfs://` |
| Start Kubo/Lotus for local dev | `ipfs-kit services start` | Enabling auto-install env in CI without intent |
| Dashboard UI (legacy tree) | `ipfs-kit mcp start` with explicit `--server-path` | Documenting it as MCP++ authority |

---

## 11. Unresolved owner decisions (do not invent closures)

These remain open; architecture prose must keep them explicit:

1. **C-VER / U-01** — Public version string: packaging `0.3.0` vs `__init__.__version__` `0.2.0`.
2. **C-CLI / U-02** — Whether `UnifiedCLIDispatcher` becomes the sole composition layer (including audit/daemon) under FastCLI.
3. **C-HLA / U-03** — Long-term high-level API: package stub, legacy file, or true package split.
4. **C-MCP-TREES / U-11** — Sole production MCP runtime: packaged `mcp_server` vs large legacy `mcp/` / root servers (proposed ADR territory).
5. **C-MCP-TOOLS** — Published tool count contract (29 registry vs 28 JS manifest vs stale README counts).
6. **C-FSSPEC** — Supported non-Iroh fsspec brands and registration model.
7. **Daemon manager authority** — Which manager is “the” Kubo lifecycle owner for new work.
8. **CLI daemon path** — Keep legacy `IPFSKitDaemon` import, move to MCP++ HTTP, or EnhancedDaemonManager-only.

---

## 12. Validation and evidence commands

```bash
# Packaging entry points
rg -n 'version|project.scripts|fsspec.specs' pyproject.toml

# MCP++ entry and registry
rg -n 'ipfs-kit-mcp|TOOL_GROUPS|HierarchicalToolManager|register_fastmcp' \
  pyproject.toml ipfs_kit_py/mcp_server/

# CLI composition
rg -n 'def sync_main|class FastCLI|_add_unified_commands|anyio.run' ipfs_kit_py/cli.py

# Import / version drift
rg -n '__version__' ipfs_kit_py/__init__.py pyproject.toml
```

**Doc acceptance for this guide (KDOC-011):**

```bash
test -s docs/architecture/RUNTIME_AND_ENTRYPOINTS.md && \
  rg -q "ipfs-kit-mcp" docs/architecture/RUNTIME_AND_ENTRYPOINTS.md
```

---

## 13. Document history

| Date | Note |
|---|---|
| 2026-08-03 | Initial KDOC-011 guide from packaging scripts, `cli.py`, `mcp_server/server.py`, Iroh CLIs, fsspec entry points, and Wave 0 evidence maps |
