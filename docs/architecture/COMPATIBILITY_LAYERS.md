# Compatibility layers and code-path classification

| Field | Value |
|---|---|
| Task | KDOC-012 — Classify canonical, compatibility, experimental, and historical code paths |
| Goal | KDOC-G021 |
| Track | arch-runtime |
| Authority class | Canonical architecture guide (classification map; **not** an accepted ADR for disputed authorities) |
| Baseline | Repository inspection 2026-08-03; packaging `pyproject.toml` `0.3.0`; Wave 0 evidence from KDOC-002 / KDOC-004 / KDOC-011 |
| Scope | Allowlist-oriented status for root exports, high-level APIs, IPFS client families, MCP stacks, cluster families, AnyIO dual modules, and tracked inactive artifacts |
| Non-goals | Delete, rename, or promote code; invent maintainer decisions that close open ADRs; rewrite source or tests |

**Related evidence**

- [`docs/audits/PUBLIC_SURFACE_MATRIX.md`](../audits/PUBLIC_SURFACE_MATRIX.md) — surface catalog and conflict IDs (`C-*`)
- [`docs/architecture/SOURCE_OF_TRUTH_MAP.md`](./SOURCE_OF_TRUTH_MAP.md) — candidate authorities and unresolved IDs (`U-*`)
- [`docs/architecture/RUNTIME_AND_ENTRYPOINTS.md`](./RUNTIME_AND_ENTRYPOINTS.md) — process ownership and packaged entries
- [`docs/architecture/MCP_CONTROL_PLANE.md`](./MCP_CONTROL_PLANE.md) — MCP++ vs legacy trees
- [`docs/architecture/GLOSSARY.md`](./GLOSSARY.md) — **compatibility layer** definition

This guide answers: *which path is the design center for new work, which paths are shims or archives, and which authorities remain open for owner decision?*

---

## 1. How to read this map

### 1.1 Status vocabulary

Same vocabulary as the public surface matrix and runtime guide. Status is **not** an ADR.

| Status | Meaning for agents and docs |
|---|---|
| **canonical** | Preferred current path for the capability; packaging or proven library default |
| **compatibility** | Supported shim or alternate path; may run and be tested; not the design center for new work |
| **optional** | Requires extras, binaries, or external services |
| **experimental** | Present and exercised in-tree; not declared as the product default |
| **historical** | Legacy tree retained for tests/imports; not packaging default; do not document as current start path |
| **stub / partial** | Public name exists; implementation incomplete, deferred, or degraded |
| **inactive** | Backup, draft, broken, or non-import peer; never treat as runtime peer |
| **unresolved** | Competing authorities; maintainer decision still required (see **Unresolved authority** table) |

### 1.2 Evidence rank (source policy)

Claims are ordered: (1) packaging / console scripts, (2) executable import graph used by packaged entries, (3) focused tests under default pytest discovery, (4) public source contracts, (5) Git history, (6) current docs.

### 1.3 Classification record shape

Every family section uses:

| Field | Meaning |
|---|---|
| **Path / identity** | Module, package, script, or artifact |
| **Status** | Vocabulary from §1.1 |
| **Role** | What the path is for |
| **Evidence** | Packaging, importers, tests, or measured facts |
| **Do not** | Common footguns for agents and authors |

### 1.4 Allowlist orientation

For **new work**, prefer:

1. Packaging targets in `pyproject.toml` `[project.scripts]` and `fsspec.specs`
2. Library paths imported by those targets or by `ipfs_kit` / lazy package proxies
3. Default-discovery tests under `tests/` and `tests/unit/`

Treat everything else as **compatibility**, **historical**, **experimental**, **inactive**, or **unresolved** until an ADR accepts a different default.

---

## 2. Root exports and package façade

### 2.1 Package identity

| Path / identity | Status | Role | Evidence | Do not |
|---|---|---|---|---|
| `ipfs_kit_py` package (`ipfs_kit_py/__init__.py`) | **canonical** package root | Installable library root; JIT/lazy façade | `[tool.setuptools.packages.find]` includes `ipfs_kit_py*`; import tests | Treat root `src/` as the distributed package (`src/__init__.py` is outside packaging; `__version__ = "3.0.0"`) |
| Packaging version `0.3.0` (`pyproject.toml` / `setup.py`) | **canonical** for release metadata | Published package version | PEP 621 `version = "0.3.0"` | Assume `__init__.__version__` matches without checking |
| `ipfs_kit_py.__version__ = "0.2.0"` | **compatibility** string / **unresolved** vs packaging | In-module version attribute | `ipfs_kit_py/__init__.py`; conflict **C-VER** / **U-01** | Publish release notes from this string alone |
| Root `package.json` `0.1.0` | **historical** / harness-only | Playwright e2e harness | Not Python packaging | Cite as kit version |
| Non-packaged `src/__init__.py` `3.0.0` | **inactive** for product distribution | Out-of-package tree | Not in setuptools package find | Import as `ipfs_kit_py` |

### 2.2 Declared `__all__` vs popular lazy symbols (**C-EXPORT**)

| Symbol class | Status | Evidence | Do not |
|---|---|---|---|
| `__all__` (21 names: P2P workflow core, JIT helpers, backend status helpers, optional accelerate/datasets getters) | **canonical** *declared* export list | `ipfs_kit_py/__init__.py` `__all__` | Treat `__all__` as the full set of supported APIs |
| Lazy proxies / getters (`IPFSSimpleAPI`, `get_ipfs_kit`, `get_ipfs_py`, installers, filesystem helpers) | **canonical** *runtime* library paths when feature loads; **not** listed in `__all__` | Lazy loaders and `@optional_feature` in `__init__.py`; docs/examples emphasize these | Assume `from ipfs_kit_py import IPFSSimpleAPI` appears in `__all__` |
| JIT / optional feature core (`jit_manager`, `require_feature`, `optional_feature`) | **canonical** | Core package init; listed in `__all__` | Force import-time binary install (default `IPFS_KIT_AUTO_INSTALL_BINARIES` off) |

**Unresolved authority (root exports):** Whether the public Python surface should expand `__all__` to include lazy HLA/kit/fsspec symbols, keep a P2P-centric `__all__`, or publish a separate “stable API” module remains open (**C-EXPORT**). Packaging version authority (**C-VER** / **U-01**) is separate and also open.

### 2.3 Root repository shims (outside package body)

| Path | Status | Role | Evidence |
|---|---|---|---|
| Root `install_ipfs.py`, `install_lotus.py` | **compatibility** thin wrappers | Redirect to package install modules | Small root files; package modules own implementation |
| Root `enhanced_mcp_server_with_daemon_mgmt.py`, `consolidated_mcp_dashboard.py` | **historical** / **compatibility** | Unpackaged alternate MCP/dashboard entries | Not in `[project.scripts]` |
| Root `daemon_config_manager.py` | **compatibility** sibling | Mirrors package daemon config helpers | Prefer `ipfs_kit_py/daemon_config_manager.py` for library use |
| `archive/`, `backup/` | **historical** | Archived patches, servers, reorg dumps | Never import as product path |
| `servers/*.py` | **historical** / **experimental** | Unpackaged MCP server variants | See §5 |

---

## 3. High-level API family (**C-HLA** / **U-03**)

| Path / identity | Status | Role | Evidence | Do not |
|---|---|---|---|---|
| Import name `ipfs_kit_py.high_level_api` → package dir `high_level_api/` | **canonical import name** | What `importlib` resolves for the package path | `find_spec(...).origin` → `high_level_api/__init__.py` | Assume the sibling `high_level_api.py` file is the import target |
| Package `IPFSSimpleAPI` (stub/proxy that lazy-loads legacy impl) | **canonical import shape**; runtime body **compatibility** when legacy loads | Public constructor name; may degrade to stub | `high_level_api/__init__.py` loads legacy under a *non-clobbering* module name; stub sets `available = False` | Treat stub-only mode as full API success without checking `available` |
| Sibling module file `ipfs_kit_py/high_level_api.py` (~554 KB) | **compatibility** implementation body | Large legacy `IPFSSimpleAPI` implementation loaded under alternate `sys.modules` name | Loaded by package `_try_load_ipfs_simple_api`; not the package origin | Edit this file and assume it is `ipfs_kit_py.high_level_api` in `sys.modules` |
| Package helpers `high_level_api/libp2p_integration*.py`, `webrtc_benchmark_helpers*.py` | **optional** / dual AnyIO | Feature helpers beside the façade | Present next to package `__init__.py` | Require libp2p at import of the package (import is deferred) |
| `high_level_api.py.fixed`, `.new`, `high_level_api_fixed.py`, `high_level_api_improved.py`, `high_level_api_updated.py`, `fixed_high_level_api.py` | **inactive** | Drafts, backups, incomplete peers | Not import targets; not loaded by package init | Glob-discover and treat as peer APIs |

**Lazy package wiring:** `ipfs_kit_py.__init__` exposes `IPFSSimpleAPI` via `_IPFSSimpleAPIProxy` and `get_high_level_api()` behind `@optional_feature('high_level_api')`.

**Focused tests:** import/path suites (`tests/test_ipfs_kit_import.py`, `tests/test_import_paths_validation.py`, `tests/test_architecture_support.py`); HLA behavior often exercised indirectly via kit/MCP tests.

**Unresolved authority (high-level API):** Is the long-term supported surface (a) the package stub as intentional public API, (b) the legacy file as sole runtime body behind the package, or (c) a true package-split migration that deletes or archives the sibling file? (**C-HLA** / **U-03**). Classification does **not** choose among these.

---

## 4. Three IPFS client families (**C-IPFS-CLIENT** / **U-12**)

Three distinct classes named `ipfs_py` exist in-tree. Only one is the orchestrator default.

| Family | Path | Status | Role | Evidence | Do not |
|---|---|---|---|---|---|
| **A — Kit orchestrator client** | `ipfs_kit_py/ipfs.py` (`class ipfs_py`, ~2k LOC) | **canonical** for library kit façade | Primary client used by `ipfs_kit` | `ipfs_kit.py`: `from .ipfs import ipfs_py`; daemon manager integration | Assume every `ipfs_py` import resolves here |
| **B — MCP roadmap simplified client** | `ipfs_kit_py/ipfs_client.py` (`class ipfs_py`, ~400 LOC) | **compatibility** / **experimental** | Simplified client described for MCP roadmap gaps | Module docstring: “simplified implementation… MCP roadmap”; separate class definition | Use as drop-in for family A without API parity proof |
| **C — Nested package reference client** | `ipfs_kit_py/ipfs/ipfs_py.py` (`class ipfs_py`, ~260 LOC) | **compatibility** / **historical** | Nested package client under `ipfs/` | Third `class ipfs_py` definition | Import as `ipfs_kit_py.ipfs` and expect family A |

### 4.1 Adjacent (not the three `ipfs_py` classes)

| Path | Status | Role |
|---|---|---|
| `ipfs_kit_py/ipfs_kit.py` | **canonical** multi-role orchestrator | Composes family A client |
| `ipfs_kit_py/kubo_runtime.py`, `install_ipfs.py`, `ipfs_daemon_manager.py` | **canonical** binary/lifecycle helpers | Opt-in install; managed Kubo |
| `ipfs_kit_py/ipfs_kit_daemon_client.py` | **compatibility** | Daemon client variant |
| `tools/ipfs_core_tools.IPFSClient` | **experimental** / tools-tree | HTTP `/api/v0` oriented helper outside package product surface |
| Direct `ipfshttpclient` use in some Iroh paths | **optional** integration detail | Not a third kit `ipfs_py` |

**Focused tests:** `tests/unit/test_daemon_*.py`, `tests/test_daemon_*.py`, `tests/unit/test_ipfs_health.py`; broader IPFS suites under `tests/` (filter integration as needed).

**Unresolved authority (IPFS clients):** Which implementation is the sole supported `ipfs_py` for library *and* MCP tools long term, and what happens to B/C (**U-12**). Managed vs system Kubo default when both exist on `PATH` is also open.

---

## 5. MCP stacks (**C-MCP-TREES**, **C-MCP-TOOLS** / **U-11**, **U-18**)

### 5.1 Stack ranking

| Stack | Paths | Status | Role | Evidence |
|---|---|---|---|---|
| **MCP++ (packaged)** | `ipfs_kit_py/mcp_server/` (`server.py`, `cli.py`, `tools/`, `hierarchical_tool_manager.py`, `fastmcp_app.py`, `mcplusplus/`, `js_sdk/`) | **canonical** *packaged* control plane | Product console scripts and single `TOOL_GROUPS` registry | `ipfs-kit-mcp` → `mcp_server.server:main`; `ipfs-kit-mcp-tools` → `mcp_server.cli:main`; **34** `.py` modules |
| **Legacy in-package MCP** | `ipfs_kit_py/mcp/` (controllers, dashboard, servers, auth, storage_manager, …) | **compatibility** / **historical** | Prior-generation control plane still importable and heavily tested | **~619** `.py`; migration guide still cites `mcp.servers.unified_mcp_server` as “canonical runtime” — **competing claim** vs packaging |
| **Root `mcp/` shims** | `mcp/*_mcp_tools.py`, root enhanced/standalone servers under `mcp/` | **compatibility** | Bridge modules for older layouts | **~24** `.py`; not packaging script targets |
| **Unpackaged `servers/`** | `servers/final_mcp_server_enhanced.py`, `enhanced_mcp_server_with_*.py`, `streamlined_mcp_server.py`, `containerized_mcp_server.py` | **historical** / **experimental** | Standalone launchers retained for tests and old docs | **6** `.py`; not in `[project.scripts]` |
| **Package MCP name collisions** | `ipfs_kit_py/mcp.py` | **stub** / **historical** | Minimal anyio peer/server toy class `MCP` | Must not be confused with `mcp_server` or `mcp/` |
| **Adjacent MCP-named modules** | `mcp_client.py`, `mcp_extensions.py`, `mcp_search.py`, `direct_mcp_server.py`, `enhanced_mcp_server*.py`, `consolidated_mcp_dashboard.py` | **compatibility** / **historical** | Clients, extensions, alternate servers/dashboards | Not console-script targets |
| **CLI coupling to legacy** | FastCLI / `ipfs-kit daemon` paths that import `ipfs_kit_py.mcp…` daemon | **compatibility** coupling | Packaged CLI still reaches into legacy tree for some daemon paths | Documented in runtime guide; does not re-rank packaging |

### 5.2 Tool registry (single write-path intent)

| Surface | Status | Evidence | Drift |
|---|---|---|---|
| `TOOL_GROUPS` in `mcp_server/tools/__init__.py` | **canonical** registry for MCP++ | Shared by hierarchical manager, tools CLI, JSON-RPC server, FastMCP registrar, JS SDK generator | Measured **29** tools / **12** groups (includes `iroh_diagnostics`) |
| `js_sdk/tools-manifest.json` | **generated companion** | Must be regenerated from registry | **28** tools — missing `iroh_diagnostics` (**C-MCP-TOOLS**) |
| `mcp_server/README.md` tool counts | **stale documentation** | Still frames **21** / **7** in places | Do not cite as measured truth |
| FastMCP e2e hard-assert `len(names) == 28` | **stale test contract** | `tests_e2e_interop.py` | Will fail against live **29** until updated |

### 5.3 How to choose an MCP path (without closing ADRs)

| Intent | Prefer | Avoid as default |
|---|---|---|
| New agent / MCP++ integration | `ipfs-kit-mcp`, `ipfs-kit-mcp-tools`, `mcp_server.tools` | Root `servers/*`, `final_mcp_server_enhanced.py` |
| Understanding packaging truth | `pyproject.toml` scripts | Docstrings citing root enhanced servers on port 9998 |
| Reading legacy tests / dashboards | `ipfs_kit_py/mcp/` with explicit “legacy” label | Calling legacy “canonical” without ADR acceptance |
| Production sole-runtime policy | **Unresolved** — Proposed ADR-0003 | Treating this guide as ADR acceptance |

**Focused tests:** `ipfs_kit_py/mcp_server/tests_e2e_interop.py`, `tests/test_mcp_jsonrpc_conformance.py`, `tests/test_mcp_*.py`, `tests/test_agent_supervisor_receipts.py`. Many `tests/test_mcp_*` and integration suites still target legacy enhanced/dashboard servers — filter carefully.

**Unresolved authority (MCP stacks):** Is `ipfs_kit_py.mcp_server` the sole supported server for new deployments, with `ipfs_kit_py.mcp`, root `mcp/`, and `servers/` strictly compatibility (**C-MCP-TREES** / **U-11**)? Published tool count / JS manifest parity (**C-MCP-TOOLS** / **U-18**) is also open. This document classifies packaging as the *current product entry* and leaves production-authority acceptance to ADR-0003.

---

## 6. Cluster families (**U-08**)

Three coordination families coexist and must not be conflated.

| Family | Paths | Status | Role | Evidence |
|---|---|---|---|---|
| **A — Bespoke kit cluster** | `ipfs_kit_py/cluster/` (`role_manager.py`, `cluster_manager.py`, `distributed_coordination.py`, `monitoring.py`, …); top-level `cluster_*.py` (`cluster_state`, `cluster_coordinator`, `cluster_management`, `cluster_dynamic_roles`, `cluster_authentication`, `cluster_monitoring`, `cluster_state_sync`, `cluster_state_helpers`, `cluster_state_anyio`) | **canonical candidate** for in-kit multi-node roles; organization **unresolved** | Kit-native roles, state, monitoring | Package + parallel top-level modules; tests `tests/test_cluster_services.py`, `tests/unit/test_cluster_*.py` |
| **B — Kubo IPFS Cluster wrappers** | `ipfs_cluster_api.py`, `ipfs_cluster_ctl.py`, `ipfs_cluster_service.py`, `ipfs_cluster_daemon_manager.py`, `ipfs_cluster_follow*.py`, unit files `ipfs-cluster*.service` | **compatibility** / **optional** external-service integration | Operate official `ipfs-cluster` binaries | Distinct from bespoke `cluster/` package; requires external cluster stack |
| **C — MCP++ durable coordination** | `mcp_server/mcplusplus/coordination_storage.py`, `event_dag.py`, `delegation.py`; receipts via agent-supervisor paths | **canonical** *within MCP++* for coordination artifacts | Content-addressed coordination / receipts — not Kubo Cluster | `docs/coordination-storage.md`; MCP++ guide |
| Supporting primitives | `merkle_clock.py`, `p2p_workflow_coordinator.py`, `services/state_service.py` | **canonical** helpers / **shared** | Causal clocks, P2P tasks, CLI/MCP state parity | Cross-linked from cluster and runtime maps |
| Multi-region helper | `multi_region_cluster.py` | **experimental** / optional | Extended topology helper | Not packaging default |
| Doc/script drift | Root `start_3_node_cluster.py` (missing); real script `tools/start_3_node_cluster.py` | Root path **historical** (stale claims); tools path **compatibility** launcher | Deployment examples | Freshness audit F-001 |

**Do not:** Document “the cluster” as a single API surface. Separate (1) kit role/state, (2) Kubo Cluster CLI/service wrappers, (3) MCP++ coordination store.

**Unresolved authority (cluster):** Production multi-node default among A/B/C, relationship of `cluster_state` vs `StateService` vs `DurableCoordinationStore`, and constructor/API mismatches across modules (**U-08**). Ownership for the deep guide is `CLUSTER_COORDINATION.md` / ADR-0008; this file only ranks families.

---

## 7. AnyIO variants and async dual modules (**U-14**)

### 7.1 Runtime policy (not universal migration)

| Concern | Status | Evidence |
|---|---|---|
| MCP++ server process uses anyio with **trio** backend | **canonical** for packaged MCP++ | `mcp_server/server.py`; Hypercorn trio worker for HTTP |
| Operator CLI (`ipfs-kit`) anyio/sync composition | **canonical** for CLI | `cli.py` / FastCLI |
| Library callers | **caller-owned** loop | No new process; deliberate sync and asyncio sites remain |
| Docs claiming “complete AnyIO migration” | **historical** campaign reports | `docs/ANYIO_MIGRATION.md`, `docs/COMPLETE_ANYIO_MIGRATION_SUMMARY.md` — not proof of universal conversion |
| Bulk refactor tool | **historical** | `tools/asyncio_to_anyio_bulk_refactor.py` |

### 7.2 Dual-module pattern (`foo.py` + `foo_anyio.py`)

Widespread **compatibility** pairing: sync (or asyncio-native) module plus AnyIO variant. Neither side is automatically deleted. Prefer the variant that matches the caller’s runtime; do not claim every path is AnyIO-complete.

**Package-root `*_anyio.py` modules (measured inventory):**

| AnyIO module | Typical sync / peer | Status label |
|---|---|---|
| `api_anyio.py` | `api.py` | dual / compatibility pair |
| `arc_cache_anyio.py` | `arc_cache.py` | dual |
| `arrow_metadata_index_anyio.py` | `arrow_metadata_index.py` | dual |
| `cluster_state_anyio.py` | `cluster_state.py` | dual |
| `disk_cache_anyio.py` | `disk_cache.py` | dual |
| `peer_websocket_anyio.py` | peer websocket sync peer | dual |
| `wal_api_anyio.py`, `wal_cli_integration_anyio.py`, `wal_telemetry_*_anyio.py`, `wal_visualization_anyio.py`, `wal_websocket_anyio.py` | matching `wal_*` modules | dual (WAL telemetry family heavy) |
| `websocket_notifications_anyio.py` | websocket notifications peer | dual |

**Nested duals / helpers:**

| Path | Status |
|---|---|
| `cache/async_operations_anyio.py` | dual under cache package |
| `high_level_api/libp2p_integration_anyio.py`, `webrtc_benchmark_helpers_anyio.py` | dual helpers |
| `libp2p/anyio_compat.py` | **compatibility** bridge inside libp2p |
| `mcp/server_anyio.py` | **compatibility** within legacy MCP tree (not MCP++) |

**Focused tests:** `tests/test_anyio_migration.py`, `tests/test_iroh_fsspec_async.py`; pytest `anyio_mode = auto`.

**Unresolved authority (AnyIO):** End-state is deliberate dual stack vs ongoing migration; default async backend for library callers outside MCP++; stub vs fail-closed when extras are missing (**U-14**). Detailed matrix ownership: planned `ASYNC_AND_OPTIONAL_DEPENDENCIES.md` / ADR-0001 / ADR-0004. This guide forbids claiming universal AnyIO completion.

---

## 8. Tracked inactive artifacts

**Policy:** Files matching backup/draft/broken patterns are **inactive**. They are not runtime peers, not packaging entries, and not sources for generated API docs. Agents must not “fix forward” by importing them as the primary module.

### 8.1 Pattern catalog

| Pattern | Status | Examples in tree |
|---|---|---|
| `*.broken` | **inactive** | `cli.py.broken` |
| `*.fixed` / `*.new` | **inactive** | `high_level_api.py.fixed`, `high_level_api.py.new`, `ipfs.py.new` |
| `*_fixed.py`, `*_improved.py`, `*_updated.py`, `fixed_*.py` | **inactive** | `high_level_api_fixed.py`, `high_level_api_improved.py`, `high_level_api_updated.py`, `enhanced_bucket_index_fixed.py`, `fixed_high_level_api.py`, `fixed_get_filesystem.py` |
| `*_old.py` | **inactive** / **historical** | `cli_old.py` |
| `*.corrupted_backup` | **inactive** | `backend_manager.py.corrupted_backup` |
| `*.deprecated_backup`, `*_deprecated_backup/`, `GRPC_DEPRECATION_NOTICE.md` | **historical** | `routing/grpc_*.deprecated_backup`, `routing/grpc_deprecated_backup/` |
| `*.original` | **inactive** | `ai_ml_integration.py.original` |
| Explicit archive trees | **historical** | `archive/`, `backup/`, `docs/ARCHIVE/` |
| `tests/archived_stale_tests/` | **historical** | Excluded from default pytest discovery (`norecursedirs`) |
| Empty external doc gitlinks | **external** / N/A | `docs/ipfs_cluster/`, `docs/ipfs-docs/`, … — not kit runtime |

### 8.2 HLA inactive cluster (explicit list)

All of the following are **inactive** relative to the package import path `ipfs_kit_py.high_level_api`:

- `ipfs_kit_py/high_level_api.py.fixed`
- `ipfs_kit_py/high_level_api.py.new`
- `ipfs_kit_py/high_level_api_fixed.py`
- `ipfs_kit_py/high_level_api_improved.py`
- `ipfs_kit_py/high_level_api_updated.py`
- `ipfs_kit_py/fixed_high_level_api.py`

(The large live body `high_level_api.py` is **compatibility** implementation, not inactive — see §3.)

### 8.3 CLI inactive peers

| Path | Status |
|---|---|
| `cli.py` (`sync_main` / FastCLI) | **canonical** packaged CLI |
| `unified_cli_dispatcher.py` | **canonical design** / **partial** composition under FastCLI (**C-CLI**) |
| `cli_old.py`, `cli.py.broken`, `cli_commands.py` | **inactive** / superseded |

### 8.4 Retention

**Unresolved authority (inactive artifacts):** Whether `*.fixed` / backup siblings remain in the main package tree or must move under `archive/`, and deprecation timelines for legacy MCP and simplified bucket stacks (**SOURCE_OF_TRUTH_MAP** §11). Classification only; no moves in this task.

---

## 9. Cross-cutting compatibility helpers

| Path | Status | Role |
|---|---|---|
| `ipfs_kit_py/compat.py` | **compatibility** helpers | Shared transition utilities |
| Lazy `__getattr__` / proxy patterns on package root | **canonical** mechanism | Avoid import-time heavy deps and binary downloads |
| `enhanced_fsspec.py` runtime registration of `ipfs` / `filecoin` / … | **compatibility** / **experimental** vs packaging | Only `iroh` / `iroh+blob` are packaging fsspec entry points (**C-FSSPEC** / **U-17**) |
| `ipfs_fsspec.py` | **compatibility** / optional library | IPFS fsspec modules not declared in packaging |
| `iroh_fsspec.py` (`IrohFileSystem`) | **canonical** packaged fsspec | `pyproject.toml` `fsspec.specs` |
| Top-level `ipfs_backend.py` vs `backends/ipfs_backend.py` | **unresolved** dual adapters | **U-04** — do not pick silently |
| Multiple daemon managers (`enhanced_daemon_manager`, `intelligent_daemon_manager`, cluster-enhanced) | **unresolved** parallel lifecycle controllers | **U-16** |

---

## 10. Unresolved authority register

Items below are **explicit owner decisions**. Agents and docs must not invent closures. Surface conflicts (`C-*`) and map IDs (`U-*`) cross-link Wave 0 evidence.

| ID | Topic | Families affected | Related ADR / guide | Status |
|---|---|---|---|---|
| **U-01** / **C-VER** | Package version `0.2.0` vs packaging `0.3.0` | Root exports | Release docs | **Unresolved authority** |
| **U-02** / **C-CLI** | FastCLI vs unified dispatcher long-term composition | CLI | Runtime guide | **Unresolved authority** |
| **U-03** / **C-HLA** | HLA package stub vs legacy module body | High-level API | Python API docs | **Unresolved authority** |
| **U-04** | Live adapter factory; dual `ipfs_backend` | Storage | Storage guide | **Unresolved authority** |
| **U-08** | Bespoke cluster vs Kubo Cluster vs MCP++ coordination | Cluster families | ADR-0008, cluster guide | **Unresolved authority** |
| **U-11** / **C-MCP-TREES** | Production MCP runtime among `mcp_server`, `mcp/`, root `mcp/`, `servers/` | MCP stacks | ADR-0003, MCP control plane | **Unresolved authority** |
| **U-12** / **C-IPFS-CLIENT** | Sole supported `ipfs_py` among three class definitions | IPFS clients | Runtime, MCP, storage | **Unresolved authority** |
| **U-14** | AnyIO end-state and missing-extra policy | AnyIO variants | ADR-0001/0004, async guide | **Unresolved authority** |
| **U-16** | Daemon manager authority among enhanced/intelligent/cluster/legacy | Runtime / ops | Runtime guide | **Unresolved authority** |
| **U-17** / **C-FSSPEC** | Supported fsspec protocols beyond packaged Iroh | fsspec | Storage / integration | **Unresolved authority** |
| **U-18** / **C-MCP-TOOLS** | Published tool count vs registry vs JS manifest | MCP tools | MCP guide, SDK | **Unresolved authority** |
| **C-EXPORT** | Whether `__all__` should list lazy HLA/kit symbols | Root exports | API docs | **Unresolved authority** |
| Inactive retention | Keep backup siblings in-package vs force `archive/` | Tracked inactive | Maintenance policy | **Unresolved authority** |

---

## 11. Navigation cheat sheet (allowlist)

| Need | Start here | Status |
|---|---|---|
| Installable library | `import ipfs_kit_py` | canonical package |
| Operator CLI | `ipfs-kit` → `cli:sync_main` | canonical packaging |
| MCP server / tools CLI | `ipfs-kit-mcp`, `ipfs-kit-mcp-tools` | canonical packaging (MCP++) |
| Kit orchestrator | `ipfs_kit` / `get_ipfs_kit()` | canonical |
| IPFS client for kit | `ipfs_kit_py.ipfs.ipfs_py` (via `from .ipfs import ipfs_py`) | canonical family A |
| High-level API import | `ipfs_kit_py.high_level_api` package | canonical import name; body may be compatibility load |
| Packaged fsspec | `iroh` / `iroh+blob` → `IrohFileSystem` | canonical packaging |
| Backend type registry | `backend_registry.py` / `backend_manager.py` | canonical config plugins |
| Legacy MCP controllers/dashboards | `ipfs_kit_py/mcp/` | compatibility / historical |
| Alternate MCP process files | `servers/`, root enhanced servers | historical / experimental |
| Draft/backup modules | `*.fixed`, `*_improved.py`, … | inactive |
| Archive dumps | `archive/`, `backup/` | historical |

---

## 12. Evidence refresh commands

```bash
# Packaging entries and version drift
rg -n 'version|project.scripts|fsspec.specs' pyproject.toml setup.py ipfs_kit_py/__init__.py

# Three ipfs_py families
rg -n 'class ipfs_py' ipfs_kit_py/ipfs.py ipfs_kit_py/ipfs_client.py ipfs_kit_py/ipfs/ipfs_py.py
rg -n 'from \.ipfs import ipfs_py' ipfs_kit_py/ipfs_kit.py

# MCP trees vs packaging
rg -n 'ipfs-kit-mcp|mcp_server.server' pyproject.toml
find ipfs_kit_py/mcp_server ipfs_kit_py/mcp mcp servers -name '*.py' 2>/dev/null | wc -l

# HLA dual path
python3 - <<'PY'
import importlib.util
print(importlib.util.find_spec("ipfs_kit_py.high_level_api").origin)
PY

# Inactive patterns
find ipfs_kit_py -maxdepth 3 \( -name '*.broken' -o -name '*.fixed' -o -name '*.new' \
  -o -name '*_fixed.py' -o -name '*_improved.py' -o -name '*_updated.py' \
  -o -name '*_old.py' -o -name '*.corrupted_backup' -o -name '*deprecated*' -o -name 'fixed_*.py' \)

# AnyIO duals at package root
ls ipfs_kit_py/*_anyio.py
```

---

## 13. Change triggers

Revisit this classification when any of the following change:

- `[project.scripts]`, fsspec entry points, or package version fields
- Resolution of ADR-0003 (MCP), ADR-0008 (cluster), ADR-0001/0004 (AnyIO)
- Removal or package-split of `high_level_api.py` vs `high_level_api/`
- Deletion or archival of any of the three `ipfs_py` definitions
- Collapse of dual `*_anyio.py` modules into a single async policy
- Forced move of `*.fixed` / backup siblings into `archive/`
- Changes to `TOOL_GROUPS` count or JS SDK generation

**Last verified:** 2026-08-03 (KDOC-012): packaging scripts/version; `__all__` vs lazy exports; HLA package origin + legacy file + inactive siblings; three `class ipfs_py` definitions with kit import of family A; MCP++ 34 vs legacy mcp ~619 vs root mcp ~24 vs servers 6; cluster package + Kubo wrappers + MCP++ coordination; 17 package-root `*_anyio.py` modules; inactive pattern inventory under `ipfs_kit_py/`.

---

## 14. Acceptance checklist (KDOC-012)

| Criterion | Met |
|---|---|
| Root exports have status/evidence or unresolved owner decision | Yes (§2, **C-EXPORT** / **C-VER**) |
| High-level APIs classified | Yes (§3, **C-HLA** / **U-03**) |
| Three IPFS client families classified | Yes (§4, **C-IPFS-CLIENT** / **U-12**) |
| MCP stacks classified | Yes (§5, **C-MCP-TREES** / **U-11**) |
| Cluster families classified | Yes (§6, **U-08**) |
| AnyIO variants classified | Yes (§7, **U-14**) |
| Tracked inactive artifacts classified | Yes (§8) |
| Explicit **Unresolved authority** language for open decisions | Yes (§10 and per-section notes) |
| Classification only (no code delete/rename/promote) | Yes |
| Validation greps `Unresolved authority` | Yes (this file) |

*End of COMPATIBILITY_LAYERS.md — KDOC-012 architecture artifact.*
