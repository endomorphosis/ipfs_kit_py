# Public surface matrix (KDOC-002)

| Field | Value |
|---|---|
| Task | KDOC-002 — Map public interfaces, entry points, and exposed capabilities |
| Goal | KDOC-G012 |
| Track | evidence-surfaces |
| Baseline tree | worktree evidence inspected 2026-08-03 |
| Authority class | Generated audit / evidence (not a product guide) |
| Edit policy | Read packaging, source, and focused tests; write only this matrix |
| Validation | `test -s docs/audits/PUBLIC_SURFACE_MATRIX.md && rg -q "pyproject.toml" docs/audits/PUBLIC_SURFACE_MATRIX.md` |

## Purpose

Map every supported **public** packaging entry, Python export, CLI command family,
MCP/JSON-RPC/FastMCP/SDK surface, filesystem protocol, backend plugin registry,
and daemon/service entry to:

1. **Entry path** — how a user or agent reaches the surface
2. **Implementation authority / status** — canonical, compatibility, optional,
   historical, stub, or unresolved
3. **Optional requirements** — extras, binaries, env flags, services
4. **Focused tests** — paths that prove or exercise the surface
5. **Known drift** — version, export, tool-count, or doc/code conflicts
6. **Documentation owner** — planned or current doc that should own claims

This matrix records conflicts **explicitly**. It does not invent maintainer
decisions that reconcile competing implementations.

## Evidence bases (authority order)

| Rank | Evidence | Paths |
|---|---|---|
| 1 | Packaging metadata | `pyproject.toml` (canonical), `setup.py` (legacy install hook) |
| 2 | Executable entry points | `[project.scripts]`, `[project.entry-points."fsspec.specs"]` |
| 3 | Runtime contracts | `ipfs_kit_py/__init__.py`, `cli.py`, `mcp_server/`, `backend_registry.py`, fsspec modules |
| 4 | Focused tests | `tests/`, `ipfs_kit_py/mcp_server/tests_e2e_interop.py` |
| 5 | Existing audits / docs | `docs/architecture/CLI_MCP_ARCHITECTURE_AUDIT.md`, `README.md`, install guides |

## Explicit cross-surface conflicts

These are first-class findings. Later guides must not paper them over.

| Conflict ID | Topic | Competing claims | Evidence |
|---|---|---|---|
| **C-VER** | Package version | `pyproject.toml` / `setup.py` / README badge = **0.3.0**; `ipfs_kit_py/__init__.py` `__version__` = **0.2.0** | `pyproject.toml:7`, `setup.py:173`, `ipfs_kit_py/__init__.py:83`, `README.md` badge |
| **C-EXPORT** | Root exports vs docs | `__all__` emphasizes P2P workflow + JIT helpers; common docs/examples emphasize `IPFSSimpleAPI`, `ipfs_kit`, installers, fsspec | `__init__.py` `__all__` vs README / `docs/installation_guide.md` |
| **C-MCP-TOOLS** | MCP tool count | Runtime `TOOL_GROUPS` = **29** tools (12 groups, includes `iroh_diagnostics`); committed JS manifest = **28** (missing `iroh_diagnostics`); FastMCP e2e docstring asserts **28**; `mcp_server/README.md` claims **21** tools and omits newer groups; same README “Tests” section says **7** tools | `tools/__init__.py`, `js_sdk/tools-manifest.json`, `tests_e2e_interop.py:238-248`, `mcp_server/README.md` |
| **C-MCP-TREES** | Competing MCP servers | Canonical packaging points at `ipfs_kit_py.mcp_server`; large parallel trees under `ipfs_kit_py/mcp/`, root `mcp/`, `servers/`, and root shims remain importable | `pyproject.toml` scripts vs package layouts |
| **C-HLA** | High-level API dual path | Package `high_level_api/` (stub/proxy) vs module `high_level_api.py` (~550 KB legacy impl) loaded under alternate module name | `high_level_api/__init__.py`, `high_level_api.py` |
| **C-FSSPEC** | IPFS fsspec implementation | `ipfs_fsspec.IPFSFileSystem` / `IPFSFSSpecFileSystem` vs `enhanced_fsspec` multi-protocol registration; only Iroh protocols are declared in packaging entry points | `pyproject.toml` fsspec.specs; `ipfs_fsspec.py`; `enhanced_fsspec.py` |
| **C-CLI** | CLI dispatcher composition | Console script `ipfs-kit` → `cli:sync_main` (`FastCLI`); separate `unified_cli_dispatcher.py` defines additional subcommands (audit, richer daemon) not fully wired into `FastCLI` | `cli.py`, `unified_cli_dispatcher.py` |
| **C-INSTALL-DOC** | Installer CLI name | Docs mention `ipfs-kit-install`; packaging has no such console script | `docs/installation_guide.md` vs `pyproject.toml` `[project.scripts]` |
| **C-SETUP-SCRIPTS** | setuptools legacy path | `setup.py` loads deps/extras from `pyproject.toml` but does **not** redeclare console scripts or fsspec entry points; PEP 517 builds use `pyproject.toml` | `setup.py` |

---

## Surface catalog

Each subsection is one public surface. Status vocabulary:

| Status | Meaning |
|---|---|
| **canonical** | Preferred current entry for the capability |
| **compatibility** | Supported shim or alternate path; not the design center |
| **optional** | Requires extras, binaries, or network services |
| **experimental** | Present and tested in-tree; not declared as default product path |
| **historical** | Legacy tree retained for tests/imports; not packaging default |
| **stub / partial** | Public name exists but implementation is incomplete or deferred |
| **unresolved** | Competing authorities; maintainer decision still required |

Documentation owners use **planned** architecture/user docs from the KDOC program
when the maintained product doc does not yet exist.

---

### S01 — Packaging metadata (`pyproject.toml`)

| Field | Value |
|---|---|
| **Entry path** | `pyproject.toml` `[project]`; build via `setuptools.build_meta` |
| **Authority / status** | **canonical** for name, version **0.3.0**, Python `>=3.12`, dependencies, optional extras, console scripts, fsspec entry points |
| **Optional requirements** | None to read metadata. Install needs network for many deps; `libp2p` / `ipld-github` / `ipfs_accelerate` extras pull heavy or VCS packages |
| **Focused tests** | `tests/test_iroh_packaging.py`; packaging assertions in Iroh release/readiness tests; install-path tests that import package metadata |
| **Known drift** | **C-VER**, **C-SETUP-SCRIPTS**. Optional-extra set is large (`iroh`, `fsspec`, `api`, `libp2p`, `ai_ml`, `full`, …); docs often understate Python 3.12 floor |
| **Documentation owner** | Planned: `docs/installation_guide.md`, `docs/QUICK_REFERENCE.md` (KDOC-030); packaging facts also feed `docs/architecture/RUNTIME_AND_ENTRYPOINTS.md` (KDOC-011) |

**Declared console scripts** (`[project.scripts]`):

| Script | Target |
|---|---|
| `ipfs-kit` | `ipfs_kit_py.cli:sync_main` |
| `ipfs-kit-mcp` | `ipfs_kit_py.mcp_server.server:main` |
| `ipfs-kit-mcp-tools` | `ipfs_kit_py.mcp_server.cli:main` |
| `ipfs-kit-iroh` | `ipfs_kit_py.iroh_install_cli:main` |
| `ipfs-kit-iroh-ops` | `ipfs_kit_py.iroh.cli:main` |
| `ipfs-kit-iroh-diagnostics` | `ipfs_kit_py.iroh.diagnostics_cli:main` |
| `ipfs-kit-iroh-manifest` | `ipfs_kit_py.iroh.manifest_cli:main` |
| `ipfs-kit-iroh-interop` | `ipfs_kit_py.iroh.multinode:main` |

**Declared fsspec entry points** (`[project.entry-points."fsspec.specs"]`):

| Protocol | Target |
|---|---|
| `iroh` | `ipfs_kit_py.iroh_fsspec:IrohFileSystem` |
| `iroh+blob` | `ipfs_kit_py.iroh_fsspec:IrohFileSystem` |

**Not declared in packaging** (code-side only): backend plugin group name
`ipfs_kit.backends` (see S12); IPFS/filecoin/storacha/synapse fsspec protocols
registered at import time in modules (see S11).

---

### S02 — Legacy `setup.py` install hook

| Field | Value |
|---|---|
| **Entry path** | `python setup.py install` / `pip install` with legacy setuptools path; `setup()` in `setup.py` |
| **Authority / status** | **compatibility** for metadata alignment; **optional** side effects for binary install |
| **Optional requirements** | `IPFS_KIT_AUTO_INSTALL_BINARIES` truthy to attempt Kubo/Lotus/Iroh binary install during install/develop; `IPFS_KIT_BIN_DIR`; `IPFS_KIT_SKIP_LOTUS_CHECK` |
| **Focused tests** | Installer and binary detection tests (`tests/comprehensive_installer_test.py`, `tests/test_lotus_daemon_auto_install.py`, `tests/test_install_iroh.py`) — not pure packaging unit tests |
| **Known drift** | Does not re-export console scripts/entry points; auto-install is fail-soft with stderr warnings. Program policy sets `IPFS_KIT_AUTO_INSTALL_BINARIES=0` for documentation checks |
| **Documentation owner** | `docs/installation_guide.md` (must state opt-in binaries); planned RUNTIME_AND_ENTRYPOINTS |

---

### S03 — Python package root (`ipfs_kit_py`)

| Field | Value |
|---|---|
| **Entry path** | `import ipfs_kit_py` / `from ipfs_kit_py import …` |
| **Authority / status** | **canonical** package root with **lazy / JIT** loading; `__version__` currently **unresolved** vs packaging (**C-VER**) |
| **Optional requirements** | Core import aims to stay light; many symbols load optional modules on access. Binary auto-download on import is disabled by default (`_DOWNLOAD_BINARIES_AUTOMATICALLY = False`) |
| **Focused tests** | `tests/test_cli_import_verification.py`; high-level API integration tests; any smoke that `import ipfs_kit_py` succeeds |
| **Known drift** | **C-VER**, **C-EXPORT**. Module docstring still shows historical MCP start via `final_mcp_server_enhanced.py` (root `servers/` tree), not `ipfs-kit-mcp`. `__all__` is P2P/JIT-centric and omits many popular lazy symbols (`IPFSSimpleAPI`, `ipfs_kit`, `IPFSFileSystem`, installers) |
| **Documentation owner** | Planned: getting-started Python API docs (KDOC-G041 / KDOC-031+); `docs/architecture/COMPATIBILITY_LAYERS.md` for lazy/compat rules |

**`__all__` (explicit):** `MerkleClock`, `FibonacciHeap`, `WorkflowPriorityQueue`,
`P2PWorkflowCoordinator`, `WorkflowStatus`, `WorkflowTask`, `hamming_distance`,
`select_task_owner`, `create_task_hash`, `P2PWorkflowTools`, `jit_manager`,
`require_feature`, `optional_feature`, `initialize_backend_config`,
`get_backend_statuses`, `get_ipfs_datasets`, `get_ipfs_accelerate`,
`get_ipfs_transformers`, `ipfs_datasets_py`, `ipfs_accelerate_py`,
`ipfs_transformers_py`.

**Additional public-ish bindings** (lazy proxies / helpers, not all in `__all__`):
`IPFSSimpleAPI`, `ipfs_kit`, installers (`install_ipfs`, …), availability flags,
`IPFSFileSystem` loader, API app loader, WAL helpers — reachability depends on
JIT and optional deps.

---

### S04 — High-level Python API (`IPFSSimpleAPI`)

| Field | Value |
|---|---|
| **Entry path** | `from ipfs_kit_py import IPFSSimpleAPI` (proxy) or `from ipfs_kit_py.high_level_api import IPFSSimpleAPI` |
| **Authority / status** | **unresolved** dual path (**C-HLA**): package directory stub/proxy vs legacy `high_level_api.py` implementation loaded under a non-clobbering module name |
| **Optional requirements** | Feature flag / JIT `high_level_api`; many methods need daemons, `libp2p`, AI/ML, WebRTC extras depending on call |
| **Focused tests** | `tests/integration/test_high_level_api.py`, `test_high_level_api_libp2p_anyio.py`, `test_high_level_api_ai_ml.py`, `test_high_level_api_metadata_replication.py` |
| **Known drift** | Stub path returns `available=False` warnings if legacy load fails; SDK generation methods live on the large legacy module; docs rarely describe the dual-module layout |
| **Documentation owner** | Planned Python API user doc (KDOC-G041); architecture: RUNTIME_AND_ENTRYPOINTS + COMPATIBILITY_LAYERS |

---

### S05 — Core orchestrator class (`ipfs_kit`)

| Field | Value |
|---|---|
| **Entry path** | `from ipfs_kit_py import ipfs_kit` (lazy proxy) / `ipfs_kit_py.ipfs_kit` submodule class |
| **Authority / status** | **canonical** low-level orchestrator for many MCP `core_operations` call paths; historically also the primary kit class |
| **Optional requirements** | IPFS/Kubo binary and config for full operations; related cluster/lotus components optional |
| **Focused tests** | Broad integration suite under `tests/integration/` and `tests/comprehensive_ipfs_test.py`; MCP core_operations path covered by `mcp_server` e2e |
| **Known drift** | Attribute vs submodule naming historically fragile (comments in `__init__.py` about package attribute clobber); parallel “kit” modules exist in accelerate/datasets integrations |
| **Documentation owner** | Planned SYSTEM_OVERVIEW + RUNTIME_AND_ENTRYPOINTS; not a standalone user guide target |

---

### S06 — Unified CLI (`ipfs-kit` / `FastCLI`)

| Field | Value |
|---|---|
| **Entry path** | Console: `ipfs-kit …`; module: `python -m ipfs_kit_py.cli …`; entry `ipfs_kit_py.cli:sync_main` → async `main()` |
| **Authority / status** | **canonical** CLI entry. Implementation class: `FastCLI` in `cli.py`. Unified feature commands partially delegated to `UnifiedCLIDispatcher` |
| **Optional requirements** | MCP start/stop needs server modules and ports; services need IPFS/Lotus binaries; autoheal needs GitHub config |
| **Focused tests** | `tests/test_cli_import_verification.py`, `tests/test_cli_integration.py`, `tests/test_cli_access_methods.py`, `tests/test_cli_deprecations_*.py`, `tests/integration/test_cli_interface.py`, `tests/integration/test_wal_cli_integration_anyio.py` |
| **Known drift** | **C-CLI**. Top-level subcommands observed from parser: `mcp`, `daemon`, `services`, `autoheal`, `bucket`, `vfs`, `wal`, `pin`, `backend`, `journal`, `state`. `UnifiedCLIDispatcher` also defines `audit` and alternate `daemon` wiring not fully mirrored. `cli.py.broken` / `cli_old.py` are non-entry historical artifacts |
| **Documentation owner** | Planned CLI user guide + RUNTIME_AND_ENTRYPOINTS; operational deprecations narrative in MCP control-plane docs |

**Built-in `mcp` actions:** `start` (default port 8004), `stop`, `status`, `deprecations` (JSON report schema `REPORT_SCHEMA_VERSION = "1.0.0"`).

**Built-in `services`:** start/stop/restart/status for `ipfs` / `lotus` / `all`.

**Built-in `daemon`:** `start` (default host `0.0.0.0`, port `9999`).

**Built-in `autoheal`:** enable/disable/status/config.

---

### S07 — Unified CLI dispatcher module (library)

| Field | Value |
|---|---|
| **Entry path** | `ipfs_kit_py.unified_cli_dispatcher.UnifiedCLIDispatcher` (import); intended composition into `ipfs-kit` |
| **Authority / status** | **canonical design** for domain subcommands (bucket/vfs/wal/pin/backend/journal/state/audit/daemon); **partial** as sole CLI — primary console entry is still `FastCLI` |
| **Optional requirements** | Domain modules for each handler (bucket VFS, WAL, pin, backend manager, journal, …) |
| **Focused tests** | Indirect via CLI integration and domain CLI tests; architecture intent in `docs/architecture/CLI_MCP_ARCHITECTURE_AUDIT.md` (may be stale vs current wiring) |
| **Known drift** | **C-CLI**; architecture audit document may predate current `FastCLI` composition |
| **Documentation owner** | RUNTIME_AND_ENTRYPOINTS; CLI_MCP_ARCHITECTURE_AUDIT (historical audit, refresh via later KDOC tasks) |

---

### S08 — Standalone / satellite CLIs (not all console-scripted)

| Field | Value |
|---|---|
| **Entry path** | Direct module execution or import of `*_cli.py` / `cli/*` modules (examples: `backend_cli.py`, `bucket_vfs_cli.py`, `daemon_cli.py`, `wal_cli.py`, `fs_journal_cli.py`, `cli/bucket_cli.py`, `cli/enhanced_pin_cli.py`, `cli/p2p_workflow_cli.py`, `cli/enhanced_multiprocessing_cli.py`, `audit_cli.py`, `webrtc_cli.py`, …) |
| **Authority / status** | Mix of **compatibility** (being absorbed into unified CLI), **experimental**, and **historical**. Only Iroh + MCP + main `ipfs-kit` are packaging console scripts |
| **Optional requirements** | Domain-specific (click for some; WebRTC extras; intelligent daemon manager; etc.) |
| **Focused tests** | Domain tests (WAL CLI anyio integration, pin CLIs, daemon CLI tests, P2P workflow) |
| **Known drift** | `CLI_MCP_ARCHITECTURE_AUDIT.md` lists many as non-integrated; some MCP shims under root `mcp/` exist that the audit still marks missing — **audit freshness is itself drift** |
| **Documentation owner** | RUNTIME_AND_ENTRYPOINTS (classify integrated vs standalone); do not present every `*_cli.py` as an equal product entry |

---

### S09 — MCP++ server (`ipfs_kit_py.mcp_server`)

| Field | Value |
|---|---|
| **Entry path** | Console: `ipfs-kit-mcp [--transport stdio\|http\|p2p] [--host] [--port]`; module: `ipfs_kit_py.mcp_server.server:main`. Tools CLI: `ipfs-kit-mcp-tools`. Python: import tool callables from `mcp_server.tools.*` |
| **Authority / status** | **canonical** MCP control plane for packaging and MCP++ profiles. One registry: `TOOL_GROUPS` in `mcp_server/tools/__init__.py`, consumed by hierarchical manager, CLI, JSON-RPC, FastMCP registrar, JS SDK generator |
| **Optional requirements** | HTTP transport: Hypercorn + anyio trio backend; P2P: libp2p; MCP++ envelope/UCAN/policy features degrade when `mcplusplus` extras absent; tool backends need live IPFS/Iroh depending on tool |
| **Focused tests** | **`ipfs_kit_py/mcp_server/tests_e2e_interop.py`** (stdio/HTTP/JS SDK/FastMCP/handshake); `tests/test_mcp_jsonrpc_conformance.py`; many `tests/test_mcp_*.py` and `tests/integration/test_mcp_*.py` (broader, often hit legacy trees — filter carefully) |
| **Known drift** | **C-MCP-TOOLS**, **C-MCP-TREES**. Live registry count **29**; manifest **28** (`iroh_diagnostics` missing); README counts **21** / **7** stale. FastMCP test docstring still says 28 while `register_fastmcp` currently returns 29 names |
| **Documentation owner** | Planned `docs/architecture/MCP_CONTROL_PLANE.md` (KDOC-016); user MCP journey under KDOC-G040 |

**`TOOL_GROUPS` (runtime authority, 12 groups / 29 tools):**

| Group | Tools |
|---|---|
| `ipfs_tools` | `ipfs_add`, `ipfs_cat`, `ipfs_ls` |
| `pin_tools` | `pin_add`, `pin_ls`, `pin_rm`, `get_pinset` |
| `dag_tools` | `dag_get`, `dag_put` |
| `mfs_tools` | `files_ls`, `files_mkdir`, `files_stat`, `files_write`, `files_read`, `files_rm` |
| `swarm_tools` | `node_id`, `swarm_peers` |
| `name_tools` | `name_publish`, `name_resolve` |
| `car_tools` | `create_car` |
| `cluster_tools` | `cluster_status` |
| `block_tools` | `block_put`, `block_get`, `block_stat` |
| `bitswap_tools` | `bitswap_stat`, `bitswap_wantlist` |
| `stats_tools` | `stats_bw`, `stats_repo` |
| `iroh_tools` | `iroh_diagnostics` |

**Transports:** stdio (default), HTTP (default bind `127.0.0.1:8004`), P2P (libp2p Profile E).

---

### S10 — FastMCP registrar and JS/TS SDK

| Field | Value |
|---|---|
| **Entry path** | Python: `from ipfs_kit_py.mcp_server.fastmcp_app import register_fastmcp, create_fastmcp_app` (requires `mcp` package). JS/TS: `python -m ipfs_kit_py.mcp_server.js_sdk.generate` → generated SDK + `tools-manifest.json`; `make mcp-sdk` in project docs |
| **Authority / status** | FastMCP = **compatibility** surface over the same registry. JS/TS SDK = **generated** companion; manifest is **derived** and currently **drifted** |
| **Optional requirements** | `mcp` Python package for FastMCP; Node ecosystem for dashboard descriptor pack / Playwright e2e |
| **Focused tests** | `test_fastmcp_registrar_covers_full_registry`, `test_js_sdk_mirrors_python_tools`, `test_ts_sdk_typed_tool_names` in `tests_e2e_interop.py` |
| **Known drift** | **C-MCP-TOOLS** (manifest vs registry; hard-coded 28 in test docstring). Dashboard swissknife path referenced by tests may be out-of-tree |
| **Documentation owner** | MCP_CONTROL_PLANE; generated-doc contract (KDOC-046 / KDOC-G060) owns refresh rules for SDK artifacts |

---

### S11 — Legacy / parallel MCP servers and shims

| Field | Value |
|---|---|
| **Entry path** | `ipfs_kit_py.mcp.*` servers and controllers; root package `mcp/`; `servers/*.py` (e.g. `final_mcp_server_enhanced.py`); root shims `enhanced_mcp_server_with_daemon_mgmt.py`, `consolidated_mcp_dashboard.py`; CLI `ipfs-kit mcp start` may still target dashboard-oriented servers depending on `--server-path` |
| **Authority / status** | **historical / compatibility** for many paths; **unresolved** which dashboard server is operational default when not using `ipfs-kit-mcp` |
| **Optional requirements** | FastAPI/uvicorn (`api` extra), dashboard static assets, daemon managers, various MCP tool shims |
| **Focused tests** | Large set: `tests/test_mcp_*.py`, `tests/comprehensive_mcp_test*.py`, `tests/integration/test_mcp_*.py`, Playwright MCP UI specs — many target legacy enhanced/dashboard servers rather than MCP++ `mcp_server` |
| **Known drift** | **C-MCP-TREES**. `__init__.py` docstring still advertises `final_mcp_server_enhanced.py`. Architecture audit incomplete relative to files now present under `mcp/*_mcp_tools.py` |
| **Documentation owner** | MCP_CONTROL_PLANE must label legacy vs canonical; COMPATIBILITY_LAYERS; ARCHIVE disposition via KDOC-041+ |

---

### S12 — Backend type registry and storage backends

| Field | Value |
|---|---|
| **Entry path** | `ipfs_kit_py.backend_registry.BackendTypeRegistry` / helpers; backend manager modules; CLI `ipfs-kit backend …`; package `ipfs_kit_py.backends/*` adapters |
| **Authority / status** | **canonical** for **side-effect-free type plugins** (validate/migrate/capabilities/health/schema). Live storage adapters under `backends/` and older manager modules are a separate runtime layer — relationship **partially documented** |
| **Optional requirements** | Entry-point discovery group name `ipfs_kit.backends` (not declared in `pyproject.toml`; built-ins registered in code). Iroh plugin always registered from `iroh.backend`. Cloud backends need credentials/extras (`s3`, `huggingface`, …) |
| **Focused tests** | `tests/test_backend_enhancements.py`, `tests/test_backends_services_tools.py`, `tests/test_iroh_backend_manager.py`, `tests/integration/test_ipfs_backend_implementation.py`, `tests/integration/test_storage_backends_real.py`, `tests/integration/backends/` |
| **Known drift** | No `[project.entry-points."ipfs_kit.backends"]` in packaging despite registry support. Legacy type list is long; not every type has a first-class adapter implementation. Parallel `enhanced_backend_manager` / `backend_manager` names coexist |
| **Documentation owner** | Planned `docs/architecture/STORAGE_BACKEND_SYSTEM.md` (KDOC-012) |

**Built-in type names (22 with `load_entry_points=False`):**  
`cluster`, `digitalocean`, `estuary`, `filecoin`, `filecoin_pin`, `filesystem`,
`ftp`, `gdrive`, `github`, `huggingface`, `ipfs`, `ipfs_cluster`, `iroh`,
`lassie`, `local`, `local_fs`, `local_storage`, `minio`, `parquet`, `s3`,
`sshfs`, `storacha`.

---

### S13 — Filesystem / fsspec protocols

| Field | Value |
|---|---|
| **Entry path** | Packaging: `iroh://`, `iroh+blob://` via entry points. Runtime registration: `ipfs_fsspec`, `enhanced_fsspec` (`ipfs`, `filecoin`, `storacha`, `synapse`, …), `parquet_vfs_integration` (`parquet-ipfs`), `iroh_fsspec` in-process register helpers |
| **Authority / status** | **canonical packaging** only for Iroh protocols. IPFS fsspec path is **unresolved** between classic and enhanced modules (**C-FSSPEC**). Vendored `ipfs_kit_py/_vendor/fsspec` exists for environments without the extra |
| **Optional requirements** | Extra `fsspec` (and often `requests-unixsocket`); Iroh binary/service for Iroh FS; Synapse/Filecoin extras as applicable |
| **Focused tests** | `tests/test_iroh_fsspec_*.py`, `tests/test_iroh_fsspec_registration.py`, `tests/test_synapse_fsspec.py`, `tests/integration/test_fsspec*.py`, `tests/integration/test_ipfs_fsspec_*.py` |
| **Known drift** | **C-FSSPEC**. Import of `iroh_fsspec` is documented as service-side-effect free; enhanced multi-protocol registration is import-time and clobbers. Docs often show only `ipfs://` without packaging entry-point caveats |
| **Documentation owner** | STORAGE_BACKEND_SYSTEM + Iroh docs under `docs/iroh/`; user storage/VFS guides (KDOC-G040) |

---

### S14 — REST / FastAPI HTTP API

| Field | Value |
|---|---|
| **Entry path** | `ipfs_kit_py.api:app` (and related routers); optional launch via `python -m` / uvicorn when API extra installed; lazy loader from package root |
| **Authority / status** | **optional** public HTTP surface (`api` extra: FastAPI, uvicorn, multipart, jinja2). Parallel `api_anyio.py` is **compatibility / alternate** async style — authority between sync FastAPI module and AnyIO variant is **unresolved** for new work |
| **Optional requirements** | `pip install 'ipfs_kit_py[api]'` (or `full`); daemon/backends for non-dummy routes |
| **Focused tests** | API and MCP HTTP tests under `tests/integration/`; observability/storage router imports guarded in `__init__.py` |
| **Known drift** | Dummy app when FastAPI missing; versioned `/api/v0` plus multiple feature routers (fs-journal, metadata, …). Not listed in `[project.scripts]` |
| **Documentation owner** | Planned API user/reference docs; RUNTIME_AND_ENTRYPOINTS for how HTTP relates to CLI/MCP |

---

### S15 — Daemon and service process control

| Field | Value |
|---|---|
| **Entry path** | `ipfs-kit services …`, `ipfs-kit daemon start`; modules `ipfs_daemon_manager.py`, `lotus_daemon.py`, `intelligent_daemon_manager.py`, `enhanced_daemon_manager.py`, cluster daemon managers; client `ipfs_kit_daemon_client.py`; standalone `daemon_cli.py` |
| **Authority / status** | **canonical** product intent: manage external Kubo/Lotus (and related) processes without surprising auto-install. Multiple manager classes = **unresolved** single authority for “the” daemon manager |
| **Optional requirements** | Platform binaries; OpenCL packages for Lotus (setup warns on Linux); ports/config dirs; `IPFS_KIT_AUTO_INSTALL_BINARIES` only when opting into installers |
| **Focused tests** | `tests/test_daemon_*.py`, `tests/test_intelligent_daemon*.py`, `tests/test_enhanced_daemon_*.py`, `tests/integration/test_daemon_status_fix.py`, `tests/integration/test_mcp_daemon_management.py`, `tests/integration/test_cluster_daemon_status.py` |
| **Known drift** | Default daemon API port **9999** vs MCP **8004** vs historical **9998** in package docstring. Intelligent vs enhanced vs IPFS-specific managers coexist |
| **Documentation owner** | RUNTIME_AND_ENTRYPOINTS; operations lifecycle docs; installation guide for binary prerequisites |

---

### S16 — Binary / dependency installers

| Field | Value |
|---|---|
| **Entry path** | Python: `ipfs_kit_py.install_ipfs`, `install_lotus`, `install_lassie`, `install_storacha`, `install_iroh`, `install_synapse_sdk`; console: `ipfs-kit-iroh` for Iroh; root shims `install_ipfs.py`, `install_lotus.py` |
| **Authority / status** | **optional**, **opt-in**. Ordinary imports must not download binaries (stated in package docstring and setup gate) |
| **Optional requirements** | Network; write access to `IPFS_KIT_BIN_DIR` or `~/.local/share/ipfs_kit_py/bin`; platform support varies |
| **Focused tests** | `tests/test_install_iroh.py`, `tests/test_iroh_install_cli.py`, `tests/comprehensive_installer_test.py`, `tests/final_binary_detection_validation.py`, Lotus auto-install tests |
| **Known drift** | **C-INSTALL-DOC** (`ipfs-kit-install` absent). Installer availability flags exported from package root |
| **Documentation owner** | `docs/installation_guide.md`, `docs/guides/auto_update_install.md` (verify claims); Iroh install runbooks |

---

### S17 — Iroh console and ops surface

| Field | Value |
|---|---|
| **Entry path** | `ipfs-kit-iroh`, `ipfs-kit-iroh-ops`, `ipfs-kit-iroh-diagnostics`, `ipfs-kit-iroh-manifest`, `ipfs-kit-iroh-interop`; Python package `ipfs_kit_py.iroh.*`; fsspec S13; MCP tool `iroh_diagnostics` |
| **Authority / status** | **canonical** for Iroh-specific product surface; **optional** extra `iroh` (blake3, duckdb) plus binary |
| **Optional requirements** | `iroh` extra; managed Iroh binary via install CLI; multi-node/interop tests may need multiple processes |
| **Focused tests** | Extensive `tests/test_iroh_*.py` (CLI, fsspec, packaging, security, multinode, observability, performance, …) |
| **Known drift** | MCP tool present in registry but missing from JS manifest (**C-MCP-TOOLS**). Iroh docs tree under `docs/iroh/` is more mature than many other subsystem docs |
| **Documentation owner** | `docs/iroh/*` (retained normative contracts); STORAGE_BACKEND_SYSTEM cross-links; MCP_CONTROL_PLANE for tool exposure |

---

### S18 — Cluster, libp2p, and P2P workflow surfaces

| Field | Value |
|---|---|
| **Entry path** | Python modules `cluster_*`, `ipfs_kit_py.cluster`, `ipfs_kit_py.libp2p`; MCP `cluster_status`; CLI `cli/p2p_workflow_cli.py`; root exports for workflow coordinator/tools |
| **Authority / status** | **optional** / multi-implementation. libp2p extra tracks upstream git main (moving target). P2P workflow is prominently exported in `__all__` but is not a console script |
| **Optional requirements** | `libp2p` extra and native deps; cluster service binaries for full cluster; network |
| **Focused tests** | Cluster and libp2p integration tests; MCP libp2p integration tests; P2P workflow unit/integration where present |
| **Known drift** | Cluster role/state modules are numerous (`cluster_management`, `cluster_coordinator`, `cluster_state*`, dynamic roles). Authority for “the” cluster API is **unresolved** pending SOURCE_OF_TRUTH_MAP (KDOC-004) |
| **Documentation owner** | Planned CLUSTER_COORDINATION + NETWORK_TRANSPORTS architecture guides |

---

### S19 — Root compatibility shims and embedded projects

| Field | Value |
|---|---|
| **Entry path** | Repo-root modules: `install_ipfs.py`, `install_lotus.py`, `consolidated_mcp_dashboard.py`, `enhanced_mcp_server_with_daemon_mgmt.py`, `daemon_config_manager.py`, `migrate_secrets.py`; package find includes `external*`; submodules `ipfs_accelerate_py`, datasets/transformers accessors |
| **Authority / status** | **compatibility** shims for tests and legacy imports; integrations **optional** via extras `ipfs_accelerate`, `ipfs_datasets`, `transformers` |
| **Optional requirements** | Heavy ML stacks for accelerate; datasets stack; not required for core kit |
| **Focused tests** | Import shims often exercised by tests that `import consolidated_mcp_dashboard` etc.; integration tests for datasets/accelerate when available |
| **Known drift** | Root MCP docstring paths; `package.json` version **0.1.0** is Playwright e2e harness only (not Python package version) |
| **Documentation owner** | COMPATIBILITY_LAYERS; integration docs (KDOC-G040); external/embedded boundary (KDOC-043/044) |

---

### S20 — Configuration, credentials, and state locations

| Field | Value |
|---|---|
| **Entry path** | Defaults such as `~/.ipfs_kit` (CLI data-dir), `/tmp/ipfs_kit_config` (daemon config-dir default in CLI), backend config documents, credential manager modules, autoheal config files |
| **Authority / status** | **canonical concern** for operators; exact schema authority split across modules — **unresolved** single config bible |
| **Optional requirements** | Filesystem permissions; secret stores; never embed real credentials in docs |
| **Focused tests** | `tests/integration/test_mcp_credential_management.py`, daemon config tests, autoheal config tests, backend config validation in registry tests |
| **Known drift** | Multiple default directories and env vars (`IPFS_KIT_*`); docs disagree on bin dirs (`~/.ipfs-kit/bin` vs `~/.local/share/ipfs_kit_py/bin`) |
| **Documentation owner** | Planned CONFIGURATION_STATE_AND_TRUST architecture guide; secure credentials guide under `docs/guides/` |

---

## Surface → documentation owner map (summary)

| Surface IDs | Documentation owner (current or planned) | Downstream KDOC |
|---|---|---|
| S01–S02, S16 | `docs/installation_guide.md`, `docs/QUICK_REFERENCE.md` | KDOC-030 |
| S03–S05, S06–S08, S14–S15 | `docs/architecture/RUNTIME_AND_ENTRYPOINTS.md` | KDOC-011 |
| S09–S11, S10 | `docs/architecture/MCP_CONTROL_PLANE.md` | KDOC-016 |
| S12–S13, S17 (storage) | `docs/architecture/STORAGE_BACKEND_SYSTEM.md`, `docs/iroh/*` | KDOC-012 |
| S18 | CLUSTER_COORDINATION, NETWORK_TRANSPORTS | KDOC-014/015 |
| S04/S05/S11/S19 dual paths | COMPATIBILITY_LAYERS + SOURCE_OF_TRUTH_MAP | KDOC-004, KDOC-019 |
| S20 | CONFIGURATION_STATE_AND_TRUST | KDOC-018 |
| All | Getting-started accuracy (versions/exports/commands) | KDOC-G041 |

---

## Optional requirements matrix (packaging extras)

From `pyproject.toml` `[project.optional-dependencies]` (names only; install with
`pip install 'ipfs_kit_py[<extra>]'`):

| Extra | Primary surfaces unlocked |
|---|---|
| `iroh` | S17, Iroh backend plugin, diagnostics tool data path |
| `fsspec` | S13 non-vendored fsspec |
| `api` | S14 FastAPI |
| `libp2p` | S18 networking, MCP p2p transport |
| `arrow` / `ipld` / `ipld-github` / `car_files` / `enhanced_ipfs` | content/CAR/IPLD paths |
| `ai_ml` / `transformers` / `huggingface` | AI/ML high-level features |
| `webrtc` / `graphql` / `s3` / `saturn` / `ipni` / `filecoin_pin` | specialized integrations |
| `ipfs_datasets` / `ipfs_accelerate` | S19 integrations |
| `performance` / `dev` | benchmarks and developer tooling |
| `full` | broad dependency union (still not every VCS extra) |

Core runtime already pulls `anyio`, `trio`, `hypercorn`, `requests`, `httpx`,
`aiohttp`, cryptography stack, etc. — MCP HTTP can run without the `api` extra,
but FastAPI REST cannot.

---

## Focused test index (by surface family)

| Family | Representative paths |
|---|---|
| Packaging / version-sensitive | `tests/test_iroh_packaging.py`, import verification |
| CLI | `tests/test_cli_*.py`, `tests/integration/test_cli_interface.py` |
| MCP++ registry | `ipfs_kit_py/mcp_server/tests_e2e_interop.py` |
| MCP legacy/dashboard | `tests/test_mcp_*.py`, `tests/integration/test_mcp_*.py`, Playwright under `tests/e2e/` |
| fsspec / Iroh FS | `tests/test_iroh_fsspec_*.py`, `tests/integration/test_fsspec*.py` |
| Backends | `tests/test_backend*.py`, `tests/integration/test_*backend*` |
| High-level API | `tests/integration/test_high_level_api*.py` |
| Daemons | `tests/test_daemon*.py`, `tests/test_intelligent_daemon*.py` |
| Installers | `tests/test_install_iroh.py`, `tests/comprehensive_installer_test.py` |

Tests alone do not establish authority when they target historical servers; pair
with packaging entry points (S01) and `TOOL_GROUPS` (S09).

---

## Reproduction commands (offline-friendly)

```bash
# Packaging scripts and version
rg -n '^version|\[project.scripts\]|fsspec.specs' pyproject.toml
rg -n '__version__' ipfs_kit_py/__init__.py

# MCP tool registry vs manifest (expects 29 vs 28 today)
python - <<'PY'
from ipfs_kit_py.mcp_server.tools import TOOL_GROUPS
import json
from pathlib import Path
reg = {n for g in TOOL_GROUPS.values() for n in g}
mf = {t["name"] for t in json.loads(Path("ipfs_kit_py/mcp_server/js_sdk/tools-manifest.json").read_text())["tools"]}
print(len(reg), len(mf), sorted(reg - mf))
PY

# Backend built-ins
python - <<'PY'
from ipfs_kit_py.backend_registry import BackendTypeRegistry
print(sorted(BackendTypeRegistry(load_entry_points=False)._plugins))
PY

# CLI top-level commands
python - <<'PY'
from ipfs_kit_py.cli import FastCLI
for a in FastCLI().parser._subparsers._group_actions:
    if getattr(a, "choices", None):
        print(sorted(a.choices))
PY
```

Do not set `IPFS_KIT_AUTO_INSTALL_BINARIES=1` for documentation validation.

---

## Out of scope for this matrix

- Resolving maintainer choices among competing implementations (KDOC-004 SOURCE_OF_TRUTH_MAP, ADRs).
- Full generated API inventory (KDOC-046 / `docs/api_generated/`).
- Documentation corpus inventory (KDOC-001) or freshness audit (KDOC-003).
- Editing protected plan files or non-`docs/audits/PUBLIC_SURFACE_MATRIX.md` paths.

---

## Acceptance checklist (KDOC-002)

| Criterion | Met |
|---|---|
| Surfaces list entry path | Yes (S01–S20) |
| Implementation authority/status | Yes (status vocabulary + per surface) |
| Optional requirements | Yes (per surface + extras table) |
| Focused tests | Yes (per surface + index) |
| Known drift | Yes (global C-* table + per surface) |
| Documentation owner | Yes (per surface + summary map) |
| Version / export / tool-count conflicts explicit | Yes (**C-VER**, **C-EXPORT**, **C-MCP-TOOLS**, …) |
| Validation command greps `pyproject.toml` | Yes (this file) |

---

*End of PUBLIC_SURFACE_MATRIX.md — KDOC-002 evidence artifact.*
