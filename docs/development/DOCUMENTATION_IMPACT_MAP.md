# Documentation change-impact map

| Field | Value |
|---|---|
| Document class | **Canonical** (agent / maintainer routing map) |
| Status | active |
| Last verified | 2026-08-04 |
| Owner / task | KDOC-051 / KDOC-G070 |
| Track | agent-docs |
| Authority class | Canonical maintenance map (not a runtime contract or ADR) |
| Evidence | [`docs/audits/PUBLIC_SURFACE_MATRIX.md`](../audits/PUBLIC_SURFACE_MATRIX.md), [`docs/architecture/SOURCE_OF_TRUTH_MAP.md`](../architecture/SOURCE_OF_TRUTH_MAP.md), architecture guides KDOC-010..019, [`docs/guides/DOCUMENTATION_GUIDE.md`](../guides/DOCUMENTATION_GUIDE.md) §11 |
| Scope | Map code, packaging, schema, CLI, tool, state, and workflow changes to the **minimum** documentation set that must be reviewed or updated |
| Non-goals | Replace architecture guides; reclassify the full ~440-file corpus; invent maintainer decisions for open `C-*` / `U-*` conflicts; edit protected plan/board/objectives files |

This map answers: *if I change X in source or packaging, which docs are in the blast radius, what checks prove claims, and which trees I must not hand-edit?*

Use it **instead of** scanning the entire `docs/` tree. Open only the owners listed for the change class that fired.

---

## 1. How to use this map

### 1.1 Five-minute agent workflow

1. **Classify the change** using §3 (primary trigger table) or §4 (special high-risk triggers).
2. **Open only the documentation owners** listed for that trigger (architecture + user/reference + ADR + generated as applicable).
3. **Set status** of affected Canonical docs to **needs-verification** when behavioral claims may be stale (see DOCUMENTATION_GUIDE §11).
4. **Run focused checks** from §5 for that class—prefer default pytest discovery paths.
5. **Do not** edit Generated trees by hand, Historical archives as present-tense guidance, or protected program-control files (§6).

### 1.2 Authority of linked maps

| Map | Use for |
|---|---|
| This file | **Blast radius** — which docs to touch after a code/packaging change |
| [`SOURCE_OF_TRUTH_MAP.md`](../architecture/SOURCE_OF_TRUTH_MAP.md) | Candidate code authority, focused tests, unresolved `U-*` |
| [`PUBLIC_SURFACE_MATRIX.md`](../audits/PUBLIC_SURFACE_MATRIX.md) | Public surfaces S01–S21, conflict IDs `C-*`, per-surface doc owners |
| [`DOCUMENTATION_GUIDE.md`](../guides/DOCUMENTATION_GUIDE.md) | Claim evidence ranking, change-trigger policy, review checklists |
| [`AGENT_SYSTEM_MAP.md`](../architecture/AGENT_SYSTEM_MAP.md) | Task → subsystem routing and high-risk import traps (when present; KDOC-050) |

### 1.3 Doc class shorthand used below

| Tag | Meaning | Edit rule |
|---|---|---|
| **Arch** | Canonical architecture guide under `docs/architecture/` | Update when design/ownership claims change |
| **User** | Installation, quick start, API/CLI/MCP journeys under `docs/` | Update when operator-facing steps or command surfaces change |
| **Ref** | Reference tables (`docs/api/`, `docs/reference/`, contracts) | Update when public surface lists change |
| **ADR** | Decision under `docs/architecture/decisions/` | Update status/links when ADR accepted, superseded, or rejected |
| **Gen** | Generated under `docs/api_generated/` (and related SDK artifacts) | **Regenerate only** — never hand-edit body content |
| **Ops** | Operations, deployment, Iroh runbooks | Update when lifecycle, ports, state roots, or install policy change |
| **Audit** | Evidence under `docs/audits/` | Refresh when surface inventory or conflicts change (program tasks) |
| **Hist** | `docs/ARCHIVE/`, `docs/implementation/`, status reports | Do not rewrite as current; supersede with Canonical pointers |

---

## 2. Surface ownership index (source domain → docs)

Use this as a **routing index**. Details and focused tests live in SOURCE_OF_TRUTH_MAP and PUBLIC_SURFACE_MATRIX.

| Source domain (code / packaging) | Primary architecture owner | Primary user / reference | Related ADR(s) | Avoid treating as equal authority |
|---|---|---|---|---|
| Package version, scripts, extras, Python floor (`pyproject.toml`, `setup.py`) | [`RUNTIME_AND_ENTRYPOINTS.md`](../architecture/RUNTIME_AND_ENTRYPOINTS.md), [`SYSTEM_OVERVIEW.md`](../architecture/SYSTEM_OVERVIEW.md) | `docs/installation_guide.md`, `docs/QUICK_REFERENCE.md`, README | ADR-0009 (docs toolchain) | Root `package.json`, non-packaged `src/__init__.py` |
| Root exports / lazy façade (`ipfs_kit_py/__init__.py`) | [`COMPATIBILITY_LAYERS.md`](../architecture/COMPATIBILITY_LAYERS.md), RUNTIME | Python API guides (`docs/api/high_level_api.md`, planned KDOC-031) | — | Backup `*.fixed` / `*_updated.py` siblings |
| High-level API dual path (`high_level_api/` vs `high_level_api.py`) | COMPATIBILITY_LAYERS, RUNTIME | `docs/api/high_level_api.md`, `docs/api/api_reference.md` | — | Inactive HLA siblings |
| CLI (`cli.py`, `unified_cli_dispatcher.py`, `*_cli.py`) | RUNTIME, [`CLI_MCP_ARCHITECTURE_AUDIT.md`](../architecture/CLI_MCP_ARCHITECTURE_AUDIT.md) (historical audit) | `docs/api/cli_reference.md` (KDOC-032) | — | `cli_old.py`, `cli.py.broken`, unmounted unified families |
| MCP++ registry / server (`mcp_server/`, `TOOL_GROUPS`, JS manifest) | [`MCP_CONTROL_PLANE.md`](../architecture/MCP_CONTROL_PLANE.md) | Planned MCP reference (KDOC-033); `mcp_server/README.md` | ADR-0003 | `ipfs_kit_py/mcp/`, root `mcp/`, `servers/` |
| Backend plugins / named config (`backend_registry.py`, `backend_manager.py`, `backends/`) | [`STORAGE_BACKEND_SYSTEM.md`](../architecture/STORAGE_BACKEND_SYSTEM.md) | Backend/config reference (KDOC-034), `docs/reference/storage_backends.md` | ADR-0002 | Unregistered experimental adapters |
| VFS / buckets / WAL / journal / content path | [`CONTENT_METADATA_VFS.md`](../architecture/CONTENT_METADATA_VFS.md) | `docs/VFS_CONTRACT_SPEC.md`, VFS/bucket docs (KDOC-035), `docs/reference/write_ahead_log.md` | ADR-0005 | Archived WAL removal reports as current design |
| Cluster roles / coordination | [`CLUSTER_COORDINATION.md`](../architecture/CLUSTER_COORDINATION.md) | Cluster ops (KDOC-036), `docs/guides/CLUSTER_DEPLOYMENT_GUIDE.md` | ADR-0008 | Competing Kubo Cluster wrappers without status labels |
| Network / Iroh / libp2p / P2P | [`NETWORK_TRANSPORTS.md`](../architecture/NETWORK_TRANSPORTS.md) | `docs/iroh/*` (KDOC-037 entry), integration guides | ADR-0006 | Non-packaged fsspec protocols as “declared” without packaging |
| Async / AnyIO / optional extras | [`ASYNC_AND_OPTIONAL_DEPENDENCIES.md`](../architecture/ASYNC_AND_OPTIONAL_DEPENDENCIES.md) | `docs/development/async_architecture.md`, install extras lists | ADR-0001, ADR-0004 | Dual `*_anyio.py` as fully unified API |
| Config / state roots / credentials / trust | [`CONFIGURATION_STATE_AND_TRUST.md`](../architecture/CONFIGURATION_STATE_AND_TRUST.md) | Credential guides, install binary policy | ADR-0007 | Docs that invent default secret storage without source |
| fsspec protocols | STORAGE + NETWORK + RUNTIME | Integration / Iroh fsspec docs | ADR-0006 | Runtime-registered protocols not in `pyproject.toml` |
| Generated API inventory / module structure | — (generated contract KDOC-046 / KDOC-G060) | `docs/api_generated/*` only via generator | ADR-0009 | Hand edits to `docs/api_generated/` |
| Documentation workflow / generators | ADR-0009, planned validation docs | `docs/workflows/documentation-maintenance.md` | ADR-0009 | Claiming Sphinx/MkDocs site works without verified config |

### 2.1 Public surface ID → owner (from PUBLIC_SURFACE_MATRIX)

| Surfaces | Documentation owner |
|---|---|
| S01–S02, S16 (packaging, setup, installers) | Installation + QUICK_REFERENCE; RUNTIME for process facts |
| S03–S08, S14–S15, S21 (package root, HLA, CLI, HTTP, daemons, clients) | RUNTIME_AND_ENTRYPOINTS + COMPATIBILITY_LAYERS as needed |
| S09–S11 (MCP++ server, tools CLI, FastMCP/SDK) | MCP_CONTROL_PLANE |
| S12–S13, S17 (backends, fsspec, Iroh storage) | STORAGE_BACKEND_SYSTEM + `docs/iroh/*` |
| S18 (cluster / network) | CLUSTER_COORDINATION + NETWORK_TRANSPORTS |
| S20 (config / state / credentials) | CONFIGURATION_STATE_AND_TRUST |
| Dual-path / historical (S04/S05/S11/S19/S21) | COMPATIBILITY_LAYERS + SOURCE_OF_TRUTH_MAP |

---

## 3. Change trigger matrix

**Change trigger** = a code, packaging, schema, or workflow edit that forces documentation review. When a trigger fires, mark listed Canonical docs **needs-verification** (or open a follow-up) and update owners before treating claims as current.

Each row: **what changed** → **docs in blast radius** → **focused checks** → **typical severity**.

Severity:

| Level | Meaning |
|---|---|
| **P0** | Public surface / version / tool count / install path — release and agent routing risk |
| **P1** | Architecture ownership or operator procedure |
| **P2** | Cross-links, glossary, secondary guides |

### 3.1 Packaging, version, and exports (P0)

| Change trigger | Architecture / evidence | User / reference / generated | Focused checks | Conflicts |
|---|---|---|---|---|
| **Package version** field in `pyproject.toml` or `setup.py` | SYSTEM_OVERVIEW, RUNTIME, SOURCE_OF_TRUTH_MAP baseline notes | README badge, installation_guide, QUICK_REFERENCE, release checklists | Align packaging version statements; re-check `__version__` drift (**C-VER**) | C-VER, U-01 |
| **`__version__` in `ipfs_kit_py/__init__.py`** | COMPATIBILITY_LAYERS, RUNTIME | Any doc asserting a single product version | Do not silently “fix” by editing only docs—record drift until closed | C-VER |
| **`[project.scripts]`** add/remove/rename | RUNTIME § entry profiles, SYSTEM_OVERVIEW | installation_guide, QUICK_REFERENCE, CLI reference, MCP start docs | `rg` scripts table vs docs; no invented names (e.g. `ipfs-kit-install` — **C-INSTALL-DOC**) | C-INSTALL-DOC |
| **`[project.entry-points."fsspec.specs"]`** | RUNTIME, STORAGE, NETWORK | Iroh fsspec docs, integration guides | Declared vs runtime-registered protocol set (**C-FSSPEC** / U-17) | C-FSSPEC |
| **`requires-python` or core dependencies** | ASYNC_AND_OPTIONAL_DEPENDENCIES, RUNTIME | installation_guide, CI docs | Python floor claims (**C-PY-FLOOR** vs `pytest.ini`) | C-PY-FLOOR |
| **Optional extras** add/remove/rename | ASYNC, STORAGE, NETWORK as applicable | installation_guide extras tables, Gen `dependencies.md` | Regenerate generated dependency inventory | — |
| **Root `__all__` / lazy export set** | COMPATIBILITY_LAYERS § root exports | Python API docs, examples, Gen AGENT_GUIDE | **C-EXPORT**: docs must not invent symbols not importable | C-EXPORT |
| **`setup.py` install-side effects** (binary auto-install) | CONFIGURATION_STATE_AND_TRUST, RUNTIME | installation_guide, auto_update_install | Policy: docs validation uses `IPFS_KIT_AUTO_INSTALL_BINARIES=0` | C-SETUP-SCRIPTS |

### 3.2 CLI and command surface (P0–P1)

| Change trigger | Architecture / evidence | User / reference | Focused checks | Conflicts |
|---|---|---|---|---|
| **FastCLI parser** families or flags (`cli.py`) | RUNTIME CLI profile | `docs/api/cli_reference.md`, QUICK_REFERENCE | Offline parser dump / CLI tests; deprecation report schema tests | C-CLI |
| **UnifiedCLIDispatcher** mount set (`unified_cli_dispatcher.py`) | RUNTIME, CLI_MCP audit (hist) | CLI reference — note what is *not* mounted (e.g. audit) | Tests under `tests/test_cli_*.py`, `tests/unit/test_minimal_cli.py` | C-CLI |
| **Standalone `*_cli.py` productization** | RUNTIME decision guide | Only document if packaging or FastCLI exposes it | Prefer console scripts over import paths | — |
| **Deprecation / policy CLI reports** | RUNTIME, MCP control plane (policy) | CLI reference deprecations | `tests/test_cli_deprecations_*.py` | — |

### 3.3 MCP / tool registry / tool-manifest (P0)

| Change trigger | Architecture / evidence | User / reference / generated | Focused checks | Conflicts |
|---|---|---|---|---|
| **`TOOL_GROUPS` membership or group layout** | MCP_CONTROL_PLANE § tool tables | MCP reference (KDOC-033), `mcp_server/README.md` | Live count vs docs; update JS manifest together | C-MCP-TOOLS, U-18 |
| **JS/TS `tools-manifest.json`** (or generator) | MCP_CONTROL_PLANE | SDK docs, interop notes | Manifest count vs registry; e2e assert `len(names)` | C-MCP-TOOLS |
| **FastMCP registration / hard-coded tool counts in tests** | MCP_CONTROL_PLANE | Test reports only if claimed as product counts | `tests_e2e_interop.py` and MCP unit/integration tests | C-MCP-TOOLS |
| **Packaged entry** `ipfs-kit-mcp` / `ipfs-kit-mcp-tools` | RUNTIME, MCP_CONTROL_PLANE | Installation + MCP start guides | Entry targets in pyproject vs prose | C-MCP-TREES |
| **Receipt / agent-supervisor fail-closed semantics** | MCP_CONTROL_PLANE | Ops / agent supervisor docs | `tests/test_agent_supervisor_receipts.py` | — |
| **Transport defaults** (stdio/HTTP/P2P, ports) | MCP_CONTROL_PLANE | Ops, deployment | Conformance tests | — |
| **Legacy MCP trees** touched (`mcp/`, root `mcp/`, `servers/`) | COMPATIBILITY_LAYERS, MCP_CONTROL_PLANE | Must **not** be documented as packaging default without U-11 / ADR-0003 | Label historical vs canonical | C-MCP-TREES, U-11 |

### 3.4 Storage backends, schema, and adapters (P1)

| Change trigger | Architecture / evidence | User / reference | Focused checks | Conflicts |
|---|---|---|---|---|
| **`BackendTypeRegistry` / `BackendPlugin` protocol** | STORAGE_BACKEND_SYSTEM | Backend reference (KDOC-034) | `tests/test_backend_*.py`, `tests/unit/test_configured_backends.py` | — |
| **`LEGACY_TYPES` or schema_version rules** | STORAGE, COMPATIBILITY | Migration notes, Iroh schema docs | Iroh backend manager tests | — |
| **Named backend document layout / atomic write / redaction** | STORAGE, CONFIGURATION_STATE_AND_TRUST | Secure credentials guide | Redaction / secretref tests | U-13 |
| **Adapter factory authority** (manager vs `backends.get_backend_adapter`) | STORAGE | Storage feature docs | Do not invent single factory if unresolved | U-* multi-adapter |
| **Iroh backend schema / migration** | STORAGE + `docs/iroh/*` | Iroh release-notes / compatibility | `tests/test_iroh_*.py` | — |

### 3.5 Content, VFS, buckets, WAL, journal (P1)

| Change trigger | Architecture / evidence | User / reference | Focused checks |
|---|---|---|---|
| **VFS / bucket contracts or path layout** | CONTENT_METADATA_VFS | `docs/VFS_CONTRACT_SPEC.md`, KDOC-035 outputs | `tests/test_vfs_*.py`, `tests/test_bucket_*.py` |
| **WAL / filesystem journal durability rules** | CONTENT_METADATA_VFS | `docs/reference/write_ahead_log.md`, journal guides | Journal unit tests under `tests/unit/` |
| **CID / pin / metadata index behavior** | CONTENT_METADATA_VFS | Pin management feature docs, metadata reference | Pin/metadata tests |
| **Cache / prefetch / tiering claims** | CONTENT + STORAGE | Prefetch / tiered cache reference | Prefer tests over status reports |

### 3.6 Cluster, network, Iroh operations (P1)

| Change trigger | Architecture / evidence | User / reference / ops | Focused checks | Conflicts |
|---|---|---|---|---|
| **Cluster role or consistency model** | CLUSTER_COORDINATION | Cluster ops (KDOC-036), deployment guides | Cluster tests (default discovery first) | U-08 |
| **Default content transport** (Kubo / Iroh / dual) | NETWORK_TRANSPORTS, SYSTEM_OVERVIEW | Iroh entry + interoperability | Iroh + IPFS client tests | U-09 |
| **libp2p / P2P workflow policy** | NETWORK, MCP (P2P tools) | P2P workflow guides | libp2p integration tests if offline-safe | U-10 |
| **Iroh install lifecycle / service config** | NETWORK + CONFIG | `docs/iroh/*` runbooks, install guides | Iroh install/packaging tests | — |
| **fsspec Iroh protocols** | RUNTIME + NETWORK | Iroh filesystem contract | Packaging entry points vs runtime | C-FSSPEC |

### 3.7 Async, optional dependencies, compatibility (P1)

| Change trigger | Architecture / evidence | User / reference | Focused checks | Conflicts |
|---|---|---|---|---|
| **AnyIO boundary or `*_anyio.py` duals** | ASYNC_AND_OPTIONAL_DEPENDENCIES, COMPATIBILITY | async_architecture.md | Import and async unit tests | U-14 |
| **JIT / optional feature gate** (`require_feature`, extras) | ASYNC, RUNTIME | Installation extras, API degradation notes | Feature-gate tests | — |
| **HLA package vs legacy module split** | COMPATIBILITY_LAYERS | high_level_api.md | Import path tests | C-HLA, U-03 |
| **IPFS client family change** (`ipfs.py` / `ipfs_client` / `ipfs/ipfs_py`) | COMPATIBILITY, RUNTIME, MCP (core ops path) | API docs that name a client class | Do not collapse three clients without ADR | C-IPFS-CLIENT, U-12 |
| **Promotion/retirement of historical trees** (`archive/`, backups, `*.fixed`) | COMPATIBILITY_LAYERS | Supersession banners on Hist docs only | Classification only unless authorized code change | — |
| **Compatibility helper** (`compat.py`) behavior | COMPATIBILITY | Migration notes | Focused unit tests if present | — |

### 3.8 Configuration, state, credentials, process lifecycle (P1)

| Change trigger | Architecture / evidence | User / ops | Focused checks | Conflicts |
|---|---|---|---|---|
| **Config precedence or state roots** | CONFIGURATION_STATE_AND_TRUST | Config guides, encrypted config feature docs | Config unit tests | U-13 |
| **Credential storage / secretref allow-list** | CONFIG | `docs/guides/SECURE_CREDENTIALS_GUIDE.md` | Redaction tests | — |
| **Binary install env flags** | CONFIG, RUNTIME | installation_guide, INSTALLER_DOCUMENTATION | `tests/test_auto_install_binaries.py` | — |
| **Daemon manager / service lifecycle** | RUNTIME, CONFIG | `docs/operations/*`, systemd guides | Prefer default-discovery daemon tests | U-16 |
| **Trust boundary / multi-tenant claims** | CONFIG, SYSTEM_OVERVIEW | Security runbooks under `docs/iroh/security.md` etc. | No secrets in examples | — |

### 3.9 Generated documentation and workflow (P1)

| Change trigger | Architecture / evidence | Generated / workflow | Focused checks | Conflicts |
|---|---|---|---|---|
| **Generator schema or module coverage** | Planned generated-doc contract (KDOC-046 / KDOC-G060) | All of `docs/api_generated/` | Re-run generator; compare drift | U-15 |
| **`.github/workflows/*` doc automation** | ADR-0009 | `docs/workflows/documentation-maintenance.md` | Workflow must match real commands | U-15 |
| **Example or symbol inventory inputs** | — | `examples_index.md`, AGENT_GUIDE | Offline example checks when available | — |
| **Navigation exclusivity / site toolchain** | ADR-0009, program nav tasks | DOCUMENTATION_INDEX, docs/README (later exclusive tasks) | Do not claim live Sphinx/MkDocs without config evidence | U-15 |

### 3.10 ADR, tests, and evidence anchors (P1–P2)

| Change trigger | Docs impact | Action |
|---|---|---|
| **ADR accepted / superseded / rejected** | Linked Arch guides + ADR index | Update status language; never leave “Proposed” after acceptance |
| **Test that was sole rank-1 evidence removed or moved to archived tree** | Any Canonical claim citing it | Re-evidence, downgrade, or mark Unknown |
| **`pytest.ini` norecursedirs / discovery change** | SOURCE_OF_TRUTH_MAP, testing_guide, this map’s “focused checks” | Prefer remaining default-discovery tests |
| **Glossary term meaning change** | [`GLOSSARY.md`](../architecture/GLOSSARY.md) + all Arch guides using the term | Update glossary first, then guides |

### 3.11 Migration and compatibility-facing releases (P0–P1)

| Change trigger | Docs blast radius | Notes |
|---|---|---|
| **Breaking CLI rename** | CLI reference, QUICK_REFERENCE, migration notes under `docs/migration/` | Provide old→new table; mark deprecations |
| **Breaking MCP tool rename/removal** | MCP_CONTROL_PLANE, tool-manifest, SDK, agent guides | Update registry + manifest + counts in lockstep |
| **Backend type removal or schema bump** | STORAGE, migration docs, Iroh compatibility.md | Record migration path; update LEGACY_TYPES narrative |
| **Python version floor bump** | installation_guide, CI docs, README | Explicit breaking-change callout |
| **Default state root relocation** | CONFIG, ops runbooks, cluster guides | Operators follow old paths without docs |

---

## 4. High-risk special triggers (explicit acceptance coverage)

These four classes are called out because they create **cross-tree** documentation failures and are easy to miss when scanning hundreds of files.

### 4.1 Version changes

| Signal | Minimum doc set | Do not forget |
|---|---|---|
| `pyproject.toml` `version` | README, installation_guide, QUICK_REFERENCE, SYSTEM_OVERVIEW packaging baseline, release checklists | `__init__.__version__` may still diverge (**C-VER**) — document drift or fix code under separate authority |
| Release tag / changelog | `docs/iroh/release-notes.md` (Iroh), project release docs, pypi_release | Historical PHASE* coverage reports are **not** version authority |

**Change trigger (version):** any packaging version edit requires re-verification of every present-tense version claim and the C-VER conflict statement.

### 4.2 Export surface changes

| Signal | Minimum doc set | Do not forget |
|---|---|---|
| `__all__` membership | COMPATIBILITY_LAYERS, Python API docs, examples | Lazy symbols may work but are not “public export” unless documented carefully |
| New top-level import path | RUNTIME, COMPATIBILITY | Prefer packaging + tests as rank-1 evidence |
| Removal of lazy proxy | API guides, Gen AGENT_GUIDE (after regen) | Search examples for removed names |

**Change trigger (export):** export set changes force API + compatibility guide review and example inventory regeneration.

### 4.3 Tool-manifest and MCP registry changes

| Signal | Minimum doc set | Do not forget |
|---|---|---|
| `TOOL_GROUPS` edit | MCP_CONTROL_PLANE tables, MCP user reference, `mcp_server/README.md` | JS `tools-manifest.json`, FastMCP tests hard-coding counts |
| Manifest-only edit | MCP_CONTROL_PLANE drift section | Registry remains source of truth until U-18 closed |
| New tool group | MCP_CONTROL_PLANE, Gen SDK path, agent guides | Receipt / policy hooks if high-risk tools |

**Change trigger (tool-manifest):** registry or manifest edits require count parity narrative and regeneration of dependent SDK artifacts; never hand-sync prose counts without re-measurement.

Measurement pattern (offline, from SOURCE_OF_TRUTH_MAP):

```bash
rg -n 'TOOL_GROUPS' ipfs_kit_py/mcp_server/tools/__init__.py
# Compare to ipfs_kit_py/mcp_server/js_sdk/tools-manifest.json tool names
```

### 4.4 Compatibility and dual-path changes

| Signal | Minimum doc set | Do not forget |
|---|---|---|
| HLA dual path change | COMPATIBILITY_LAYERS, RUNTIME, high_level_api.md | Do not delete conflict ID **C-HLA** until ADR/code resolves U-03 |
| MCP tree promotion/demotion | COMPATIBILITY, MCP_CONTROL_PLANE, ADR-0003 | Packaging scripts define default, not file size |
| Client family merge/split | COMPATIBILITY, RUNTIME, STORAGE/MCP as consumers | Three `ipfs_py` definitions — label families |
| Historical file moved to archive | COMPATIBILITY classification, supersession banners | Do not update Hist prose to present tense |

**Change trigger (compatibility):** dual-path or shim edits require COMPATIBILITY_LAYERS + consumer guides; unresolved authorities stay labeled **Unresolved**.

---

## 5. Focused validation by change class

Prefer **offline**, default pytest discovery (`tests/`, `tests/unit/`). Do not require live daemons for documentation gates. Set `IPFS_KIT_AUTO_INSTALL_BINARIES=0` for doc validation environments.

| Change class | Representative commands / tests |
|---|---|
| Packaging / version | `rg -n 'version|project.scripts|fsspec.specs' pyproject.toml setup.py ipfs_kit_py/__init__.py` |
| Import / exports | `tests/test_ipfs_kit_import.py`, `tests/test_import_paths_validation.py` |
| CLI | `tests/test_cli_import_verification.py`, `tests/test_cli_integration.py`, `tests/unit/test_minimal_cli.py` |
| MCP++ | `tests/test_mcp_jsonrpc_conformance.py`, `tests/test_mcp_server_integration.py`, `tests/test_mcp_initialization.py`, `tests/test_agent_supervisor_receipts.py` |
| Backends | `tests/test_backend_enhancements.py`, `tests/test_enhanced_backend_manager.py`, `tests/unit/test_configured_backends.py` |
| VFS / content | `tests/test_vfs_*.py`, `tests/test_bucket_*.py`, `tests/unit/test_filesystem_journal_comprehensive.py` |
| Iroh | `tests/test_iroh_*.py` (subset offline) |
| Install policy | `tests/test_auto_install_binaries.py`, `tests/test_installers.py` |
| Architecture support | `tests/test_architecture_support.py` |
| Doc file presence (this map) | See §8 validation |

After doc edits: update **Last verified** / tree baseline on touched Canonical guides when claims were re-checked.

---

## 6. Paths agents must not treat as free edit targets

| Path pattern | Reason |
|---|---|
| `docs/documentation_plan.md` | Operator-protected program control |
| `docs/architecture/ipfs_kit_documentation.objectives.md` | Operator-protected objectives heap |
| `docs/architecture/ipfs_kit_documentation.todo.md` | Operator-protected task board |
| `docs/api_generated/**` body files | **Generated** — regenerate via workflow/generator only |
| `docs/ARCHIVE/**`, most of `docs/implementation/**`, `docs/status_reports/**`, `docs/fixes/**` | **Historical** — supersede, do not rewrite as current product truth |
| External / vendored trees under `docs/*/` SDKs and gitlinks | **External** — ownership and revision explicit |
| Production source unless task allows | Documentation tasks default docs-only |

When a change only needs Historical disposition: add Canonical supersession pointers; do not modernize archived prose.

---

## 7. Blast-radius recipes (common PR shapes)

### 7.1 “I changed one MCP tool”

1. `TOOL_GROUPS` + tool module → MCP_CONTROL_PLANE  
2. JS manifest + any hard-coded counts → regenerate / update tests  
3. MCP user reference + `mcp_server/README.md`  
4. Skip full architecture set unless transport or packaging entry also changed  

### 7.2 “I bumped the package version”

1. `pyproject.toml` / setup alignment notes  
2. README + installation_guide + QUICK_REFERENCE  
3. SYSTEM_OVERVIEW / RUNTIME packaging baseline lines  
4. Explicit **C-VER** check against `__init__.__version__`  

### 7.3 “I added a CLI subcommand”

1. Confirm FastCLI mount (not only UnifiedCLIDispatcher definition)  
2. CLI reference + QUICK_REFERENCE  
3. RUNTIME CLI profile if process ownership changes  
4. Focused CLI tests  

### 7.4 “I changed backend config schema”

1. STORAGE_BACKEND_SYSTEM change-trigger section  
2. Backend/config user reference + credential redaction docs if secrets fields moved  
3. Iroh schema docs if Iroh plugin affected  
4. Backend unit tests  

### 7.5 “I moved state directory defaults”

1. CONFIGURATION_STATE_AND_TRUST  
2. Ops / systemd / deployment guides that hardcode paths  
3. Cluster and install docs  
4. Secure credentials guide if credential paths moved  

### 7.6 “I only touched tests”

1. If tests were sole evidence for a Canonical claim → re-verify that claim’s evidence list  
2. Update SOURCE_OF_TRUTH_MAP only when evidence maps are in scope for the task  
3. No broad doc rewrite required for pure coverage expansion  

---

## 8. Related documents and maintenance of this map

| Document | Relationship |
|---|---|
| [`DOCUMENTATION_GUIDE.md`](../guides/DOCUMENTATION_GUIDE.md) §11 | Normative **change trigger** policy and needs-verification states |
| [`SOURCE_OF_TRUTH_MAP.md`](../architecture/SOURCE_OF_TRUTH_MAP.md) | Code authority + tests this map routes into |
| [`PUBLIC_SURFACE_MATRIX.md`](../audits/PUBLIC_SURFACE_MATRIX.md) | Surface catalog and conflict IDs |
| [`documentation-maintenance.md`](../workflows/documentation-maintenance.md) | Generated-doc automation schedule |
| Architecture guides KDOC-010..019 | Per-subsystem **Change triggers** sections (detail) |
| ADRs `docs/architecture/decisions/` | Decision status that rewrites architecture language |

### 8.1 Change triggers for this map

Re-verify **this** impact map when:

- A new public packaging entry, console script, or major surface is added  
- Architecture guide ownership (KDOC-010..019) is reassigned or renamed  
- Generated-doc contract or navigation exclusivity (U-15) is resolved  
- Conflict IDs `C-*` are closed or new P0 conflicts appear  
- Default pytest discovery paths change  

**Last verified:** 2026-08-04 against the architecture guide set and Wave 0 surface/source maps present in-tree.

### 8.2 Validation (task gate)

```bash
test -s docs/development/DOCUMENTATION_IMPACT_MAP.md \
  && rg -q "Change trigger" docs/development/DOCUMENTATION_IMPACT_MAP.md
```

### 8.3 Acceptance checklist (KDOC-051)

| Criterion | Met |
|---|---|
| Maintainers/agents can identify blast radius without scanning ~440 files | Yes (§1–§3 routing + §7 recipes) |
| Maps source/package/workflow/schema/CLI/tool/state changes to doc owners | Yes (§2–§3) |
| Includes version / export / tool-manifest / compatibility triggers | Yes (§4 and §3.1–§3.3, §3.7) |
| Lists focused checks and avoids free-edit of Generated/Historical/protected paths | Yes (§5–§6) |
| Validation greps `Change trigger` | Yes (this file) |

*End of DOCUMENTATION_IMPACT_MAP.md — KDOC-051 agent-docs artifact.*
