# Agent-oriented canonical system map

| Field | Value |
|---|---|
| Document class | **Canonical** (agent routing map) |
| Status | active |
| Last verified | 2026-08-04 |
| Owner / task | KDOC-050 / KDOC-G070 |
| Track | agent-docs |
| Authority class | Compact task-routing map (not a runtime contract or ADR) |
| Evidence | Architecture guides KDOC-010..019, [`SOURCE_OF_TRUTH_MAP.md`](./SOURCE_OF_TRUTH_MAP.md), [`COMPATIBILITY_LAYERS.md`](./COMPATIBILITY_LAYERS.md), [`PUBLIC_SURFACE_MATRIX.md`](../audits/PUBLIC_SURFACE_MATRIX.md), ADRs under `decisions/` |
| Scope | Help an implementation or review agent choose **where to read, edit, and test** for a scoped task |
| Non-goals | Replace subsystem guides; close open `C-*` / `U-*` conflicts; rewrite source or tests; edit protected program-control files |

This map answers: *for this task, which subsystem owns the change, which code and docs are canonical, which tests prove it, which ADRs constrain it, and which trees I must not treat as the design center?*

**Sibling agent maps**

| Map | Use for |
|---|---|
| **This file** | Task → subsystem routing, allow/deny paths, import traps, process/state boundaries |
| [`DOCUMENTATION_IMPACT_MAP.md`](../development/DOCUMENTATION_IMPACT_MAP.md) | After a code change: which docs are in the blast radius |
| [`DEBUGGING_BY_SUBSYSTEM.md`](../guides/DEBUGGING_BY_SUBSYSTEM.md) | Runtime diagnosis by subsystem (when present) |
| [`SOURCE_OF_TRUTH_MAP.md`](./SOURCE_OF_TRUTH_MAP.md) | Candidate code authority, focused tests, open `U-*` |
| [`COMPATIBILITY_LAYERS.md`](./COMPATIBILITY_LAYERS.md) | Status labels and inactive-pattern catalog |

**Conflict policy for this document:** Own a compact routing map; **link** to canonical guides instead of copying them.

---

## 1. Five-minute agent workflow

1. **Classify the task** with §3 (task → subsystem). Open only that subsystem’s architecture guide and the linked SOURCE_OF_TRUTH section.
2. **Confirm the entry surface** with §4 (allowlist). Prefer packaging scripts and library paths used by those scripts.
3. **Reject wrong trees** with §2 and §5. **Do not** edit, import as primary, or document as current start paths: `archive/`, `backup/`, `*.fixed`, `*_old.py`, `docs/api_generated/` (hand-edit), or legacy MCP trees for new work.
4. **Respect process and state boundaries** with §6 (who owns the event loop; `~/.ipfs_kit` vs `~/.ipfs`).
5. **Run focused tests** from §7 under default pytest discovery (`tests/`, `tests/unit/` only — see §7.1).
6. **Check ADRs and open conflicts** with §8 before inventing an authority closure.
7. **If docs must change**, use [`DOCUMENTATION_IMPACT_MAP.md`](../development/DOCUMENTATION_IMPACT_MAP.md) — not a full `docs/` scan.

```text
  Task description
        │
        ▼
  §3 task → subsystem ──► architecture guide + SOURCE_OF_TRUTH §N
        │
        ▼
  §4 allowlist entry ──► edit candidate code under that tree only
        │
        ▼
  §2 / §5 deny list ──► skip legacy / fixed / backup / generated
        │
        ▼
  §7 focused tests ──► default discovery only unless task requires integration
        │
        ▼
  §8 ADR + open U-* ──► do not invent maintainer decisions
```

---

## 2. Path classes (read / edit / never-default)

Use these labels when scoping a change. Status vocabulary matches [`COMPATIBILITY_LAYERS.md`](./COMPATIBILITY_LAYERS.md) §1.1.

| Class | Meaning for agents | Typical paths | Edit rule |
|---|---|---|---|
| **Canonical** | Design center for new work | `pyproject.toml` scripts; `ipfs_kit_py/cli.py`; `ipfs_kit_py/mcp_server/`; `backend_registry.py` / `backend_manager.py`; `backends/`; bucket/VFS/WAL modules used by packaged CLI; `iroh/`; architecture guides under `docs/architecture/` | Prefer as first edit target |
| **Compatibility** | Supported shim or alternate; may be tested | Legacy HLA body `high_level_api.py`; dual `*_anyio.py`; `ipfs_kit_py/mcp/` when fixing packaged coupling | Edit only when the task explicitly targets the shim or a packaged path still imports it |
| **Historical** | Retained for history/tests; not product default | `archive/`, `backup/`, `servers/`, root enhanced MCP servers, `docs/ARCHIVE/`, `docs/implementation/` status dumps | **Do not** treat as equal authority or current start path |
| **Inactive** | Backup/draft/broken peer; never a runtime peer | `*.fixed`, `*.broken`, `*.new`, `*_fixed.py`, `*_improved.py`, `*_updated.py`, `fixed_*.py`, `*_old.py`, `*.corrupted_backup`, `*.deprecated_backup` | **Do not** import, “fix forward” from, or promote to primary module |
| **Generated** | Produced by tooling | `docs/api_generated/*`, MCP JS SDK `tools-manifest.json` (regenerate from registry) | **Do not** hand-edit body content; regenerate from source |
| **Read-only evidence** | Program inventories and audits | `docs/audits/*`, `SOURCE_OF_TRUTH_MAP.md` baselines | Update only under documentation-program tasks |
| **Protected** | Operator-locked program control | `docs/documentation_plan.md`, `docs/architecture/ipfs_kit_documentation.objectives.md`, `docs/architecture/ipfs_kit_documentation.todo.md` | **Do not** create, modify, rename, delete, or regenerate |

### 2.1 Hard deny list (unless the task explicitly requires the surface)

**Do not** use these as the primary read/edit/test surface for ordinary feature or fix work:

| Surface | Why |
|---|---|
| `archive/**`, `backup/**` | Historical dumps and reorg backups |
| `servers/**`, root `enhanced_mcp_server_*.py`, `final_mcp_server_enhanced.py` | Unpackaged alternate MCP servers |
| `ipfs_kit_py/mcp/**` for **new** control-plane features | Legacy MCP stack; packaged MCP++ is `mcp_server/` (**C-MCP-TREES** / **U-11**) |
| Root `mcp/**` shims for new tools | Bridge to older layouts; write tools into `mcp_server/tools/` + `TOOL_GROUPS` |
| `ipfs_kit_py/mcp.py` | Stub peer toy; not MCP++ |
| `*.fixed`, `*.broken`, `*.new`, `*_fixed.py`, `*_improved.py`, `*_updated.py`, `fixed_*.py`, `*_old.py` | Inactive peers |
| `*.corrupted_backup`, `*deprecated_backup*`, `routing/grpc_deprecated_backup/` | Explicit backups / deprecations |
| `docs/api_generated/**` (hand edits) | Generated inventory |
| `docs/ARCHIVE/**`, most of `docs/status_reports/**`, `docs/implementation/**` as present-tense design | Historical or report-like |
| `tests/integration/**`, `tests/archived_stale_tests/**` as default proof | Excluded from default pytest discovery (`pytest.ini` `norecursedirs`) |
| `src/` as the distributed package | Outside setuptools package find; not `ipfs_kit_py` |
| Root `package.json` version | Playwright harness only — not Python package version |

### 2.2 Prefer allowlist (first choices)

| Need | Start here |
|---|---|
| Installable library | `import ipfs_kit_py` → `ipfs_kit_py/__init__.py` |
| Operator CLI | `ipfs-kit` → `ipfs_kit_py.cli:sync_main` |
| MCP server | `ipfs-kit-mcp` → `ipfs_kit_py.mcp_server.server:main` |
| MCP tools one-shot | `ipfs-kit-mcp-tools` → `mcp_server.cli:main` |
| Tool registry | `ipfs_kit_py/mcp_server/tools/__init__.py` (`TOOL_GROUPS`) |
| Kit orchestrator | `ipfs_kit_py/ipfs_kit.py` |
| IPFS client (kit path) | `ipfs_kit_py.ipfs` / family used by kit (**C-IPFS-CLIENT** open for siblings) |
| High-level API import name | `ipfs_kit_py.high_level_api` **package** (not the sibling `.py` file as import origin) |
| Backend **types** / named config | `backend_registry.py`, `backend_manager.py` |
| Live storage adapters | `ipfs_kit_py/backends/` |
| Packaged fsspec | `iroh` / `iroh+blob` → `iroh_fsspec.py` |
| Iroh ops | `ipfs_kit_py/iroh/`, `ipfs-kit-iroh*` scripts |
| Kit state root | `~/.ipfs_kit` (not `~/.ipfs`) |
| Packaging truth | `pyproject.toml` (`0.3.0`, scripts, extras, fsspec.specs) |

---

## 3. Task → subsystem routing

Map the **intent** of a scoped task to one primary subsystem. Open that row’s architecture guide first; use SOURCE_OF_TRUTH section for candidate paths and tests. Secondary guides are for cross-cutting only.

| Task / change class (examples) | Primary subsystem | Architecture guide | SOURCE_OF_TRUTH | Code allowlist (start) | Avoid unless required |
|---|---|---|---|---|---|
| Console scripts, process model, CLI composition, import/JIT, installers | Runtime / entry points | [`RUNTIME_AND_ENTRYPOINTS.md`](./RUNTIME_AND_ENTRYPOINTS.md), [`SYSTEM_OVERVIEW.md`](./SYSTEM_OVERVIEW.md) | §1 | `pyproject.toml`, `cli.py`, `unified_cli_dispatcher.py`, `__init__.py`, `kubo_runtime.py` | `cli_old.py`, `cli.py.broken`, root install wrappers as authority |
| Shim classification, dual paths, inactive siblings, version string drift | Compatibility | [`COMPATIBILITY_LAYERS.md`](./COMPATIBILITY_LAYERS.md) | §1, §11 | Labels in COMPATIBILITY; package root | Promoting `*.fixed` / archive trees |
| Backend YAML, plugin types, live adapters, routing algorithms | Storage backends | [`STORAGE_BACKEND_SYSTEM.md`](./STORAGE_BACKEND_SYSTEM.md) | §2 | `backend_registry.py`, `backend_manager.py`, `backends/` | `backend_manager.py.corrupted_backup`, unregistered experiments |
| Buckets, VFS, pins, WAL, journal, metadata index, CAR | Content / durability | [`CONTENT_METADATA_VFS.md`](./CONTENT_METADATA_VFS.md) | §3 | `bucket_vfs_*`, `vfs_*`, `storage_wal.py`, `filesystem_journal.py`, pin modules | `simple_*bucket*`, `*_fixed` index peers as defaults |
| Bespoke cluster roles, CRDT/state, P2P workflow coordinator | Cluster (bespoke) | [`CLUSTER_COORDINATION.md`](./CLUSTER_COORDINATION.md) | §4 | `cluster/`, `cluster_state*.py`, `p2p_workflow_coordinator.py` | Conflating with Kubo Cluster wrappers |
| Kubo IPFS Cluster CLI/service wrappers | Cluster (Kubo family) | [`CLUSTER_COORDINATION.md`](./CLUSTER_COORDINATION.md) | §4 | `ipfs_cluster_*.py` | Treating as same API as bespoke `cluster/` |
| Iroh service/blob/fsspec, libp2p, P2P transport, content routing HTTP | Network transports | [`NETWORK_TRANSPORTS.md`](./NETWORK_TRANSPORTS.md); normative `docs/iroh/*` | §5 | `iroh/`, `libp2p/`, `routing/` (non-deprecated), `p2p_transport.py` | `routing/*deprecated*`, libp2p mocks as production |
| MCP tools, JSON-RPC server, FastMCP, agent receipts, JS SDK tools | MCP control plane | [`MCP_CONTROL_PLANE.md`](./MCP_CONTROL_PLANE.md) | §6 | `mcp_server/**`, `TOOL_GROUPS` | `ipfs_kit_py/mcp/`, root `mcp/`, `servers/`, `mcp.py` stub |
| AnyIO dual modules, optional extras, lazy imports, degradation | Async / optional deps | [`ASYNC_AND_OPTIONAL_DEPENDENCIES.md`](./ASYNC_AND_OPTIONAL_DEPENDENCIES.md) | §8 | `core/`, `jit_imports.py`, `deps_resolver.py`, dual modules **as labeled** | Claiming universal AnyIO migration complete (**U-14**) |
| Config files, `~/.ipfs_kit`, credentials, secrets, trust, daemon config | Config / trust | [`CONFIGURATION_STATE_AND_TRUST.md`](./CONFIGURATION_STATE_AND_TRUST.md) | §7 | `config*.py`, `credential_manager.py`, `backend_manager` redaction, `iroh/security.py` | Inventing secret defaults; logging credentials |
| System context, planes, actors, reading order | System overview | [`SYSTEM_OVERVIEW.md`](./SYSTEM_OVERVIEW.md) | §1, §9, §11 | Overview + linked guides | Resolving ADRs in the overview |
| Vocabulary / term meaning | Glossary | [`GLOSSARY.md`](./GLOSSARY.md) | — | Glossary terms | Redefining status words |
| Documentation blast radius after a code change | Docs impact | [`DOCUMENTATION_IMPACT_MAP.md`](../development/DOCUMENTATION_IMPACT_MAP.md) | — | Owners listed per trigger | Scanning all ~440 docs |
| Decision / authority choice | ADRs | [`decisions/README.md`](./decisions/README.md) + numbered ADR | Open `U-*` in map | Matching ADR only | Inventing Accepted status |

### 3.1 Plane routing (data vs control)

| Work is about… | Plane | Prefer |
|---|---|---|
| Content bytes, CIDs, pins, VFS paths, WAL/journal, adapters | **Storage data plane** | Library / CLI domain verbs / `backends/` / Kubo or Iroh |
| Tools, JSON-RPC, tool schemas, receipts, coordination store | **Control plane** | Packaged MCP++ (`mcp_server`) |
| Both (agent tool that mutates content) | Control **invokes** data | Register tool in `TOOL_GROUPS`; implement data path in data-plane modules |

**Do not** implement a second content store inside the control plane, or document legacy MCP dashboards as the packaged agent entry.

---

## 4. Canonical entry surfaces (packaging allowlist)

Only these are **guaranteed installable** product entries from `pyproject.toml`. Detail and lifecycle: [`RUNTIME_AND_ENTRYPOINTS.md`](./RUNTIME_AND_ENTRYPOINTS.md).

| Script / entry | Target | Role | Status |
|---|---|---|---|
| `ipfs-kit` | `ipfs_kit_py.cli:sync_main` | Operator CLI (FastCLI + selective unified mounts) | canonical |
| `ipfs-kit-mcp` | `ipfs_kit_py.mcp_server.server:main` | Long-lived MCP++ server (stdio / HTTP / P2P) | canonical |
| `ipfs-kit-mcp-tools` | `ipfs_kit_py.mcp_server.cli:main` | One-shot tools over same `TOOL_GROUPS` | canonical |
| `ipfs-kit-iroh*` family | `iroh_install_cli` / iroh ops modules | Managed Iroh binary lifecycle | canonical / optional binary |
| fsspec `iroh`, `iroh+blob` | `IrohFileSystem` | Packaged fsspec protocols | canonical |
| Library | `import ipfs_kit_py` | In-process; caller owns process/loop | canonical package |

**Composition rules agents must keep**

1. **Packaging is the product map** for scripts and fsspec protocols.
2. **One MCP tool write path:** `TOOL_GROUPS` → HierarchicalToolManager / tools CLI / FastMCP / JS generator (**C-MCP-TOOLS** tracks count drift; do not invent a second registry).
3. **CLI is composite:** FastCLI selectively mounts unified dispatcher families; not every dispatcher family is packaged as equal.
4. **Import is lazy:** do not force heavy deps or binary download at import (`IPFS_KIT_AUTO_INSTALL_BINARIES` default off).
5. **External daemons are opt-in** child or external processes, not the library process itself.

---

## 5. High-risk import and edit traps

These are the most common agent mistakes. Each row: trap → correct default → conflict ID when known.

| Trap | Do not | Do instead | Conflict |
|---|---|---|---|
| MCP from first `mcp` hit | Edit `ipfs_kit_py/mcp/` or root `mcp/` or `servers/` as the product server | `ipfs_kit_py/mcp_server/` + `ipfs-kit-mcp` | **C-MCP-TREES** / **U-11** |
| MCP stub module | `import ipfs_kit_py.mcp` as the server | `mcp_server.server` | — |
| HLA file vs package | Edit `high_level_api.py` and assume it is `sys.modules['ipfs_kit_py.high_level_api']` | Package dir `high_level_api/`; legacy file is compatibility body | **C-HLA** / **U-03** |
| HLA backups | Glob `*high_level_api*` and treat peers as APIs | Ignore inactive `*.fixed` / `*_improved.py` cluster | inactive policy |
| Version string | Cite `__init__.__version__` (`0.2.0`) as release version alone | Prefer packaging `0.3.0`; record drift | **C-VER** / **U-01** |
| fsspec protocols | Claim `ipfs://` is packaging-declared | Only `iroh` / `iroh+blob` in `fsspec.specs` | **C-FSSPEC** / **U-17** |
| IPFS client class | Pick a random `class ipfs_py` | Follow kit import (`from .ipfs import ipfs_py`) until ADR | **C-IPFS-CLIENT** / **U-12** |
| Dual backends | Edit top-level `ipfs_backend.py` without checking `backends/` | Prefer `backends/` adapters + registry path; flag dual if both touched | **U-04** |
| Cluster “the” API | Merge bespoke cluster + Kubo Cluster + MCP++ store | Name the family explicitly | **U-08** |
| CLI dead peers | Restore `cli_old.py` / `cli.py.broken` | `cli.py` + selective unified mounts | **C-CLI** / **U-02** |
| Install path docs | Document `ipfs-kit-install` or root `final_mcp_server_enhanced.py` as packaged | Packaging script names only | **C-INSTALL-DOC** |
| Generated docs | Hand-edit `docs/api_generated/` | Regenerate from contract/generator | ADR-0009 |
| Protected board files | “Complete” todo/objectives/plan as side effect | Leave protected paths alone | operator policy |
| Integration tests as default gate | Rely on `tests/integration/` for offline CI green | Prefer `tests/` + `tests/unit/` discovery | pytest `norecursedirs` |
| Auto binary install | Assume import installs Kubo | Opt-in `IPFS_KIT_AUTO_INSTALL_BINARIES` | setup policy |
| State roots | Write kit state into `~/.ipfs` | Kit: `~/.ipfs_kit`; Kubo repo separate | trust guide |
| Export surface | Assume `__all__` lists all supported APIs | Lazy proxies exist outside `__all__` | **C-EXPORT** |
| Tool count | Cite MCP README “21 tools” or JS “28” without measuring | Measure `TOOL_GROUPS` (baseline 12 groups / 29 tools); note drift | **C-MCP-TOOLS** / **U-18** |
| Daemon start path | Assume `ipfs-kit daemon` is MCP++ | Packaged CLI may still reach legacy `mcp/` daemon | **U-16** |

### 5.1 Inactive filename patterns (skip on discovery)

If a search returns these, **do not** promote them without an explicit task:

```text
*.broken  *.fixed  *.new  *.original  *.corrupted_backup
*_fixed.py  *_improved.py  *_updated.py  *_old.py  fixed_*.py
*deprecated_backup*  archive/  backup/  docs/ARCHIVE/
```

Full catalog: [`COMPATIBILITY_LAYERS.md`](./COMPATIBILITY_LAYERS.md) §8.

---

## 6. Process, event-loop, and state boundaries

### 6.1 Who owns the process and loop

| Model | Entries | Ownership |
|---|---|---|
| Short-lived CLI | `ipfs-kit`, `ipfs-kit-mcp-tools`, most Iroh CLIs | Process owns anyio/asyncio for the command; exits on return |
| Long-lived MCP++ | `ipfs-kit-mcp` | Process owns `anyio` **trio** backend for stdio/HTTP/P2P |
| In-process library | `import ipfs_kit_py`, fsspec, HLA | **Caller** owns process and event loop |
| Background child | e.g. non-foreground `ipfs-kit mcp start` | Parent spawns child; PID/logs under kit state root |
| External daemon | Kubo, Iroh service, Lotus, optional IPFS Cluster | Separate OS processes; kit managers start/stop/status only |

**Do not** assume a single global event loop or that library import starts daemons.

### 6.2 State roots and trust edges

| Root / artifact | Role | Notes |
|---|---|---|
| `~/.ipfs_kit` | Kit state: backend YAML, MCP PID/logs, buckets, StateService, coordination | Default kit state root |
| `~/.ipfs` | Kubo repo (when used) | **Not** the kit state root |
| Backend documents | Named backend configs | Sensitive keys redacted via registry helpers |
| Credentials / secrets | Credential and secrets managers | Prefer references/encryption over plaintext examples |
| MCP++ receipts / coordination store | Fail-closed agent evidence | Control-plane artifacts, not content bytes |
| Env `IPFS_KIT_AUTO_INSTALL_BINARIES` | Binary install gate | Default off for validation/docs |
| Env `IPFS_KIT_BIN_DIR` | Binary location override | See runtime / trust guides |

Detail: [`CONFIGURATION_STATE_AND_TRUST.md`](./CONFIGURATION_STATE_AND_TRUST.md), [`SYSTEM_OVERVIEW.md`](./SYSTEM_OVERVIEW.md) §8.

### 6.3 Planes (reminder)

```text
Actors (CLI / import / agent host)
        │
        ▼
Control plane: FastCLI · MCP++ · TOOL_GROUPS · receipts
        │ invokes
        ▼
Data plane: adapters · VFS/buckets · pins · WAL/journal · cache
        │ I/O
        ▼
External: Kubo · Iroh · Lotus · S3/remote · Cluster
```

---

## 7. Focused tests by subsystem

**Policy:** Prefer tests under default pytest discovery. From `pytest.ini`: `testpaths = tests` and `norecursedirs = tests/integration tests/archived_stale_tests`.

**Do not** treat `tests/integration/` or `tests/archived_stale_tests/` as the offline proof gate unless the task explicitly requires them (network/service assumptions).

### 7.1 Discovery rules for agents

| Location | Default discovery | Use when |
|---|---|---|
| `tests/*.py`, `tests/unit/**` | Yes | Primary proof for scoped changes |
| `tests/integration/**` | No (`norecursedirs`) | Explicit integration / service tasks only |
| `tests/archived_stale_tests/**` | No | Never for new work |
| In-package e2e (e.g. mcp_server interop) | Path-specific | MCP conformance when cited by guides |

### 7.2 Subsystem → test anchors (non-exhaustive)

Full lists live in [`SOURCE_OF_TRUTH_MAP.md`](./SOURCE_OF_TRUTH_MAP.md). Use these as **entry** suites:

| Subsystem | Focused tests (start here) |
|---|---|
| Import / package / CLI | `tests/test_ipfs_kit_import.py`, `tests/test_import_paths_validation.py`, `tests/test_cli_import_verification.py`, `tests/test_cli_access_methods.py`, `tests/test_cli_integration.py`, `tests/unit/test_minimal_cli.py`, `tests/test_auto_install_binaries.py` |
| Storage backends | `tests/test_backend_enhancements.py`, `tests/test_backends_services_tools.py`, `tests/test_enhanced_backend_manager.py`, `tests/test_storage_backend_policies.py`, `tests/unit/test_backend_adapter_comprehensive.py`, `tests/unit/test_configured_backends.py` |
| VFS / buckets / pins | `tests/test_vfs_*.py`, `tests/test_bucket_*.py`, `tests/test_unified_bucket_api.py`, `tests/test_mcp_vfs_*.py`, `tests/unit/test_vfs_version_tracking.py`, `tests/test_enhanced_pin_metadata.py` |
| WAL / journal | `tests/unit/test_filesystem_journal_comprehensive.py`, `tests/unit/test_enhanced_wal_durability.py` (integration WAL under `tests/integration/` only if required) |
| Iroh / fsspec | `tests/test_iroh_*.py`, `tests/test_iroh_filesystem_contract.py`, `tests/test_iroh_fsspec_*.py` |
| Cluster / P2P workflow | `tests/test_cluster_services.py`, `tests/test_p2p_workflow.py`, `tests/test_coordination_storage.py`, `tests/unit/test_cluster_*.py` |
| MCP++ / tools / receipts | `tests/test_mcp_jsonrpc_conformance.py`, `tests/test_mcp_server_integration.py`, `tests/test_mcp_tools_*.py`, `tests/test_agent_supervisor_receipts.py`, `tests/test_comprehensive_tools.py` |
| Config / credentials / daemon config | `tests/test_secure_config.py`, `tests/test_config_apis.py`, `tests/test_daemon_config*.py`, `tests/test_iroh_config.py`, `tests/test_iroh_security.py` |
| libp2p (thinner) | `tests/test_simple_libp2p.py`, `tests/unit/test_enhanced_libp2p.py` |

### 7.3 Suggested commands

```bash
# Scoped unit/default discovery examples (adjust path to task)
python -m pytest tests/test_import_paths_validation.py tests/test_ipfs_kit_import.py -q
python -m pytest tests/unit/test_minimal_cli.py -q
python -m pytest tests/test_mcp_jsonrpc_conformance.py tests/test_agent_supervisor_receipts.py -q

# Confirm you are not depending on excluded trees for offline green
rg -n 'norecursedirs' pytest.ini
```

---

## 8. ADR and open-authority index

ADRs live under [`docs/architecture/decisions/`](./decisions/). Process: [`decisions/README.md`](./decisions/README.md).

| ADR | Topic | Open agents when… |
|---|---|---|
| [ADR-0001](./decisions/0001-imports-and-optional-dependencies.md) | Imports and optional dependencies | Changing lazy import / extras policy |
| [ADR-0002](./decisions/0002-backend-plugin-registry.md) | Backend plugin registry | Adding backend types or validation side effects |
| [ADR-0003](./decisions/0003-mcp-runtime-authority.md) | MCP runtime authority | Choosing among MCP trees or new server entry |
| [ADR-0004](./decisions/0004-anyio-and-sync-boundaries.md) | AnyIO / sync boundaries | Unifying dual modules or async policy |
| [ADR-0005](./decisions/0005-content-metadata-and-durability.md) | Content, metadata, durability | WAL/journal/VFS authority claims |
| [ADR-0006](./decisions/0006-multi-protocol-storage-and-networking.md) | Multi-protocol storage/network | fsspec brands, multi-transport defaults |
| [ADR-0007](./decisions/0007-configuration-state-and-secret-references.md) | Config, state, secrets | State roots, credential reference design |
| [ADR-0008](./decisions/0008-cluster-control-plane-authority.md) | Cluster control-plane authority | Multi-node default stack choice |
| [ADR-0009](./decisions/0009-documentation-site-toolchain.md) | Documentation toolchain | Generators, site config, generated docs |

**Do not** mark a Proposed ADR as Accepted or close a `U-*` / `C-*` conflict without maintainer confirmation. Unresolved register (summary): [`COMPATIBILITY_LAYERS.md`](./COMPATIBILITY_LAYERS.md) §10 and [`SOURCE_OF_TRUTH_MAP.md`](./SOURCE_OF_TRUTH_MAP.md).

| ID | Topic | Agent rule |
|---|---|---|
| **U-01** / **C-VER** | Version `0.2.0` vs packaging `0.3.0` | Document both; do not silently “fix” one side in code without task scope |
| **U-02** / **C-CLI** | FastCLI vs unified dispatcher | Prefer packaged FastCLI mounts; do not invent full dual CLI equality |
| **U-03** / **C-HLA** | HLA package vs legacy body | Import package name; treat large `.py` as compatibility body |
| **U-04** | Dual IPFS backends / adapter factory | Prefer `backends/`; flag dual paths |
| **U-08** | Cluster family authority | Name family; do not merge APIs |
| **U-11** / **C-MCP-TREES** | MCP++ vs legacy trees | New work → `mcp_server` |
| **U-12** / **C-IPFS-CLIENT** | Multiple `ipfs_py` | Follow kit import path |
| **U-14** | AnyIO end-state | Dual modules remain; no universal migration claim |
| **U-16** | Daemon manager authority | Do not pick enhanced/intelligent/legacy as sole without ADR |
| **U-17** / **C-FSSPEC** | fsspec beyond Iroh packaging | Packaging-declared only unless task says otherwise |
| **U-18** / **C-MCP-TOOLS** | Tool count drift | Measure registry; regenerate manifest |

---

## 9. Common false assumptions

| False assumption | Reality |
|---|---|
| “The first path matching the feature name is the product path.” | Many parallel trees exist; packaging + status labels decide. |
| “`mcp/` is the MCP server.” | Packaged server is `mcp_server/`; `mcp/` is legacy/compatibility. |
| “Editing any `high_level_api*` file updates the public import.” | Import origin is the package directory; backups are inactive. |
| “All CLI dispatcher families are mounted.” | FastCLI mounts a selective subset (**C-CLI**). |
| “fsspec `ipfs` is a declared packaging entry.” | Only `iroh` / `iroh+blob` are declared. |
| “Default pytest runs everything under `tests/`.” | `integration` and `archived_stale_tests` are excluded. |
| “Import installs IPFS binaries.” | Auto-install is opt-in and default off. |
| “`~/.ipfs` is kit state.” | Kit state is `~/.ipfs_kit`; Kubo uses `~/.ipfs`. |
| “Docs under `docs/implementation/` or status reports are current design.” | Prefer Canonical architecture guides; treat reports as historical unless refreshed. |
| “I can hand-edit generated API docs.” | Regenerate; **do not** hand-edit `docs/api_generated/`. |
| “Closing a conflict in prose is enough.” | Open `U-*` need ADR/maintainer confirmation. |
| “Root `package.json` or `src/__init__.py` versions are the kit version.” | Python packaging version is in `pyproject.toml`. |
| “JS tools-manifest count is the registry truth.” | Python `TOOL_GROUPS` is the write-path candidate; manifest may lag. |
| “Bespoke cluster and Kubo Cluster are one subsystem.” | Distinct families (**U-08**). |
| “Control plane stores content.” | Tools invoke data plane; receipts ≠ bytes. |

---

## 10. Architecture reading order (when onboarding a new area)

1. This map (§3 row for the task)  
2. [`SYSTEM_OVERVIEW.md`](./SYSTEM_OVERVIEW.md) — context and planes  
3. Subsystem architecture guide from §3  
4. [`SOURCE_OF_TRUTH_MAP.md`](./SOURCE_OF_TRUTH_MAP.md) matching section — paths + tests  
5. [`COMPATIBILITY_LAYERS.md`](./COMPATIBILITY_LAYERS.md) — if multiple trees appear  
6. Related ADR from §8  
7. [`DOCUMENTATION_IMPACT_MAP.md`](../development/DOCUMENTATION_IMPACT_MAP.md) — if docs change  
8. User/reference docs only after architecture ownership is clear  

**Vocabulary:** [`GLOSSARY.md`](./GLOSSARY.md). **Public surface IDs:** [`PUBLIC_SURFACE_MATRIX.md`](../audits/PUBLIC_SURFACE_MATRIX.md).

---

## 11. Evidence refresh (optional, offline)

```bash
# Packaging entries and version drift
rg -n 'version|project.scripts|fsspec.specs' pyproject.toml setup.py ipfs_kit_py/__init__.py

# MCP++ registry vs JS manifest drift
rg -n 'TOOL_GROUPS|register_fastmcp' ipfs_kit_py/mcp_server/

# Inactive / backup patterns under the package
find ipfs_kit_py -type f \( \
  -name '*.broken' -o -name '*.fixed' -o -name '*.new' \
  -o -name '*_fixed.py' -o -name '*_improved.py' -o -name '*_updated.py' \
  -o -name '*_old.py' -o -name '*.corrupted_backup' -o -name '*deprecated*' \
  -o -name 'fixed_*.py' \) 2>/dev/null | head

# Pytest exclusion policy
rg -n 'norecursedirs|testpaths' pytest.ini
```

---

## 12. Acceptance checklist (KDOC-050)

| Check | Met when |
|---|---|
| Agent can route a scoped task | §3 maps intent → guide + code allowlist + avoid column |
| Canonical vs non-default surfaces are explicit | §2 path classes; §4 packaging allowlist |
| Legacy / fixed / backup / generated are blocked by default | §2.1 deny list; §5 traps; inactive patterns |
| Process and state boundaries are visible | §6 |
| Focused tests are discoverable | §7 with default-discovery policy |
| ADRs and open conflicts are linked | §8 |
| False assumptions are listed | §9 |
| Document stays a map, not a copy of guides | Links to SYSTEM_OVERVIEW, RUNTIME, COMPATIBILITY, subsystem guides, impact map |

**Last verified:** 2026-08-04 (KDOC-050): packaging scripts and fsspec allowlist; MCP++ vs legacy trees; HLA package vs inactive siblings; pytest `norecursedirs`; kit vs Kubo state roots; ADR index 0001–0009; cross-links to KDOC-010..019 guides and KDOC-051 impact map.
