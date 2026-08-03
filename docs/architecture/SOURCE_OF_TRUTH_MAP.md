# Architectural source-of-truth and test map

- Status: evidence baseline (Wave 0)
- Task: KDOC-004
- Goal: KDOC-G012
- Authority class: Canonical (evidence map; not a runtime contract)
- Baseline: repository inspection 2026-08-03
- Scope: map candidate implementation authorities, compatibility/historical paths, focused tests, current docs, gaps, and unresolved owner decisions for architecture guides
- Non-goals: resolve disputed authority; invent maintainer decisions; rewrite source or tests; refresh generated API docs

This map is the evidence packet later architecture tasks (KDOC-010..019 and related ADRs) consume. Claims are ordered by the program source policy: executable behavior and focused tests, packaging/entry-point metadata, public source contracts, Git history, then current documentation.

**Legend**

| Label | Meaning |
|---|---|
| Candidate authority | Paths that currently look primary for the subsystem; not an accepted ADR |
| Compatibility / historical | Parallel, shim, legacy, backup, or archived surfaces that must not be treated as equal defaults without qualification |
| Focused tests | Offline-friendly or highly targeted tests under `tests/` (pytest discovery; `tests/integration` and `tests/archived_stale_tests` are excluded by `pytest.ini`) |
| Current docs | Existing prose that discusses the subsystem (often stale; freshness is KDOC-003) |
| Gaps | Missing evidence, docs, or cross-surface wiring visible from static inspection |
| Unresolved | Owner decisions that must remain open until a proposed ADR or maintainer confirmation |

**Evidence commands (reproducible, offline)**

```bash
# Package version and public scripts
rg -n 'version|project.scripts|fsspec.specs' pyproject.toml setup.py ipfs_kit_py/__init__.py

# Backend config registry (side-effect-free plugin types)
rg -n 'BACKEND_ENTRY_POINT_GROUP|class BackendManager|class BackendTypeRegistry' \
  ipfs_kit_py/backend_registry.py ipfs_kit_py/backend_manager.py

# MCP++ packaging entry and single tool registry
rg -n 'ipfs-kit-mcp|TOOL_GROUPS|HierarchicalToolManager|register_fastmcp' \
  pyproject.toml ipfs_kit_py/mcp_server/

# Version mismatch (known)
rg -n '__version__|version\s*=' ipfs_kit_py/__init__.py pyproject.toml setup.py
```

---

## 1. Runtime, import, and package entry points

### Candidate authority

| Concern | Paths |
|---|---|
| Packaging / version (PEP 621) | `pyproject.toml` (`version = "0.3.0"`), `setup.py` (loads project metadata; version `0.3.0`) |
| Console scripts | `pyproject.toml` `[project.scripts]`: `ipfs-kit` → `ipfs_kit_py.cli:sync_main`; `ipfs-kit-mcp` → `ipfs_kit_py.mcp_server.server:main`; `ipfs-kit-mcp-tools` → `ipfs_kit_py.mcp_server.cli:main`; Iroh family → `iroh_install_cli` / `iroh.*` |
| fsspec registration | `pyproject.toml` `[project.entry-points."fsspec.specs"]` → `ipfs_kit_py.iroh_fsspec:IrohFileSystem` |
| Package root / lazy exports | `ipfs_kit_py/__init__.py` (JIT-backed installers, high-level API lazy paths, WAL helpers) |
| JIT / optional feature core | `ipfs_kit_py/core/__init__.py` (`jit_manager`, `ToolRegistry`, `ServiceManager`, `ErrorHandler`), `ipfs_kit_py/jit_imports.py`, `ipfs_kit_py/deps_resolver.py` |
| Primary kit façade | `ipfs_kit_py/ipfs_kit.py` |
| High-level Python API surface | `ipfs_kit_py/high_level_api.py` (large monolithic module); package dir `ipfs_kit_py/high_level_api/` (libp2p/WebRTC helpers) |
| Unified CLI composition | `ipfs_kit_py/unified_cli_dispatcher.py` (bucket/vfs/wal/pin/backend/journal/state/audit/daemon subcommands) |
| Packaged CLI entry | `ipfs_kit_py/cli.py` (`sync_main`; MCP dashboard-oriented FastCLI plus dispatcher integration points) |
| Kubo binary lifecycle (opt-in) | `ipfs_kit_py/kubo_runtime.py`, `ipfs_kit_py/install_ipfs.py`, `setup.py` auto-install gated by `IPFS_KIT_AUTO_INSTALL_BINARIES` |

### Compatibility / historical paths

| Path | Notes |
|---|---|
| `ipfs_kit_py/__init__.py` `__version__ = "0.2.0"` | Diverges from packaging `0.3.0` |
| `ipfs_kit_py/cli_old.py`, `cli.py.broken`, `cli_commands.py` | Superseded or broken CLI material |
| `ipfs_kit_py/high_level_api.py.fixed`, `.new`, `high_level_api_fixed.py`, `high_level_api_improved.py`, `high_level_api_updated.py` | Parallel drafts / backups of the high-level API |
| `ipfs_kit_py/compat.py` | Compatibility helpers |
| Root `install_ipfs.py` / `install_lotus.py` | Thin root wrappers; package modules under `ipfs_kit_py/` are the implementation |
| Docstring examples citing `final_mcp_server_enhanced.py` | Entry path not matching packaged `ipfs-kit-mcp` |
| `archive/`, `backup/` | Historical code and server variants; not runtime defaults |

### Focused tests

- `tests/test_ipfs_kit_import.py`
- `tests/test_import_paths_validation.py`
- `tests/test_cli_import_verification.py`
- `tests/test_cli_access_methods.py`
- `tests/test_cli_integration.py`
- `tests/test_cli_deprecations_*.py` (report schema / policy)
- `tests/test_auto_install_binaries.py`
- `tests/test_installers.py`
- `tests/test_architecture_support.py`

### Current docs

- Root `README.md`, `docs/README.md`, `docs/index.md`, `docs/DOCUMENTATION_INDEX.md` (competing navigation)
- `docs/installation_guide.md`, `docs/INSTALLER_DOCUMENTATION.md`
- `docs/architecture/ARCHITECTURE_MODULE_ORGANIZATION.md` (pre-MCP++ layering)
- `docs/architecture/CLI_MCP_ARCHITECTURE_AUDIT.md` (CLI/MCP compliance audit; pre-dates full MCP++ consolidation claims)
- `docs/guides/` partial CLI/policy notes

### Gaps

- No single maintained “supported entry points” matrix yet (owned by KDOC-002 / KDOC-011 architecture guides).
- `__init__.py` public `__all__` emphasizes P2P workflow symbols more than packaging scripts; export surface needs explicit classification.
- Unified dispatcher vs `cli.py` FastCLI responsibilities are split; which path is the operator default for non-MCP commands is not fully documented.
- Optional extras in `pyproject.toml` are rich; degradation matrices for missing extras are incomplete in authored docs.

### Unresolved owner decisions

1. **Version authority:** Is `0.3.0` (packaging) or `0.2.0` (`__init__.__version__`) the public package version string? Unresolved until release owner confirmation.
2. **CLI composition authority:** Is `unified_cli_dispatcher.py` the sole long-term composition layer under `ipfs-kit`, or does `cli.py` FastCLI remain the primary packaged surface with partial subcommand coverage?
3. **High-level API module identity:** Is the monolithic `high_level_api.py` the supported import path, with `high_level_api/` only for specialized helpers, or is a package-split migration intended?
4. **Binary install policy narrative:** Package code is opt-in via `IPFS_KIT_AUTO_INSTALL_BINARIES`, but older docs/docstrings still imply import-time installation. Unresolved documentation default wording until KDOC-035 / lifecycle guides.

---

## 2. Storage backend system (config plugins vs live adapters)

### Candidate authority

| Concern | Paths |
|---|---|
| Side-effect-free backend *type* registry | `ipfs_kit_py/backend_registry.py` (`BACKEND_ENTRY_POINT_GROUP = "ipfs_kit.backends"`, validation, redaction, migration hooks) |
| Named backend document manager | `ipfs_kit_py/backend_manager.py` (atomic YAML under `~/.ipfs_kit/backends/`, validation via registry plugins) |
| Backend schemas / policies | `ipfs_kit_py/backend_schemas.py`, `ipfs_kit_py/backend_policies.py`, `ipfs_kit_py/backend_config.py` |
| Live storage adapters | `ipfs_kit_py/backends/` (`base_adapter.py`, `ipfs_backend.py`, `iroh_backend.py`, `filesystem_backend.py`, `s3_backend.py`, `real_api_storage_backends.py`) |
| Tiered / intelligent cache | `ipfs_kit_py/tiered_cache_manager.py`, `ipfs_kit_py/cache/`, `ipfs_kit_py/cache_manager.py` |
| Content routing across backends | `ipfs_kit_py/routing/` (`router.py`, `routing_manager.py`, algorithms; gRPC paths partially deprecated) |
| Example configs | `config/enhanced_backend_examples.yaml`, `config/iroh-backend.example.yaml` |

### Compatibility / historical paths

| Path | Notes |
|---|---|
| `ipfs_kit_py/backend_manager.py.corrupted_backup` | Explicit backup; not authority |
| `ipfs_kit_py/ipfs_backend.py` (top-level) vs `backends/ipfs_backend.py` | Parallel IPFS backend modules |
| `ipfs_kit_py/routing/grpc*.deprecated_backup`, `grpc_deprecated_backup/`, `GRPC_DEPRECATION_NOTICE.md` | Deprecated gRPC routing stack |
| Legacy MCP storage managers under `ipfs_kit_py/mcp/storage*`, `mcp/storage_manager` | Control-plane era storage wiring; not the config registry |

### Focused tests

- `tests/test_backend_enhancements.py`
- `tests/test_backends_services_tools.py`
- `tests/test_enhanced_backend_manager.py`
- `tests/test_storage_backend_policies.py`
- `tests/test_iroh_backend_manager.py`
- `tests/test_bucket_backend_mapping.py`
- `tests/test_coordination_storage.py`

### Current docs

- `docs/architecture/BACKEND_ARCHITECTURE_VISUAL_SUMMARY.md`
- `docs/architecture/FILESYSTEM_BACKEND_ARCHITECTURE_REVIEW.md`
- `docs/iroh/named-backends.md`, `docs/iroh/capability-matrix.md`
- `docs/features/STORAGE_FEATURES_DOCUMENTATION_COMPLETE.md` (report-like)
- Future target guide: `docs/architecture/STORAGE_BACKEND_SYSTEM.md` (KDOC-012)

### Gaps

- Distinction between **configuration plugins** (registry/manager) and **live adapters** (`backends/`) is clear in code comments but not in a maintained architecture guide.
- Entry-point group `ipfs_kit.backends` discoverability vs in-tree registered types needs an inventory in generated or reference docs.
- Health probes on `BackendManager` are optional injection points; default probe set and failure semantics are under-documented.
- S3/remote adapter credential binding paths overlap configuration/security map (section 7).

### Unresolved owner decisions

1. **Live adapter factory authority:** Which module constructs runtime adapters from validated YAML—callers of `backends/*`, routing layer, or a single manager API?
2. **Top-level vs package `ipfs_backend`:** Which IPFS adapter is supported for new work?
3. **Routing transport:** Is HTTP (`routing/http_server.py`) the supported control path after gRPC deprecation, or is routing library-only?

---

## 3. Content, metadata, VFS, and durability

### Candidate authority

| Concern | Paths |
|---|---|
| Bucket VFS core | `ipfs_kit_py/bucket_vfs_manager.py`, `bucket_vfs_api.py`, `bucket_manager.py` |
| VFS managers / contracts | `ipfs_kit_py/vfs_manager.py`, `vfs_bucket_manager.py`, `vfs_version_tracker.py` |
| Unified bucket interface | `ipfs_kit_py/unified_bucket_interface.py`, `unified_bucket_cli.py` |
| IPFS fsspec | `ipfs_kit_py/ipfs_fsspec.py` |
| Iroh fsspec / VFS | `ipfs_kit_py/iroh_fsspec.py`, `iroh_vfs.py`, `iroh/filesystem` contracts via `docs/iroh/filesystem-contract.md` + `iroh/` service modules |
| Metadata index | `ipfs_kit_py/arrow_metadata_index.py` (+ `arrow_metadata_index_anyio.py`), `metadata_manager.py`, `metadata_sync_handler.py` |
| Pins | `ipfs_kit_py/pins.py`, `pin_metadata_index.py`, `pin_manager.py`, `simple_pin_manager.py`, `cli/enhanced_pin_cli.py` |
| Content manager | `ipfs_kit_py/content_manager.py` |
| WAL durability | `ipfs_kit_py/storage_wal.py`, `wal.py`, `enhanced_wal_durability.py`, `car_wal_manager.py`, `pin_wal.py`, `wal_integration.py` |
| Filesystem journal | `ipfs_kit_py/filesystem_journal.py`, `fs_journal_integration.py`, `fs_journal_backends.py`, `fs_journal_replication.py` |
| CAR tooling | `ipfs_kit_py/car_wal_manager.py`, MCP `mcp_server/tools/car_tools.py` |
| Normative VFS contract prose | `docs/VFS_CONTRACT_SPEC.md`, `docs/iroh/filesystem-contract.md` |

### Compatibility / historical paths

| Path | Notes |
|---|---|
| `simple_bucket_manager.py`, `simplified_bucket_manager.py`, `simple_bucket_cli.py`, `clean_bucket_cli.py` | Simplified / alternate bucket stacks |
| `enhanced_bucket_index.py` / `enhanced_bucket_index_fixed.py` | Parallel index implementations |
| `ipfs_fsspec.py.clean`, `.full` | Non-package backup variants |
| Multiple VFS CLI entry modules (`bucket_vfs_cli.py`, `vfs_version_cli.py`, `cli/bucket_cli.py`) | Not all wired into the packaged unified dispatcher |
| Empty `enhanced_pin_index.py` | Stub; JIT feature checks may reference enhanced pin index |
| WAL telemetry / websocket / visualization `*_anyio.py` pairs | Dual async stacks; see section 8 |

### Focused tests

- VFS / buckets: `tests/test_vfs_*.py`, `tests/test_bucket_*.py`, `tests/test_unified_bucket_api.py`, `tests/test_final_vfs_bucket_integration.py`, `tests/test_mcp_vfs_*.py`
- Iroh filesystem: `tests/test_iroh_filesystem_contract.py`, `tests/test_iroh_fsspec_*.py`, `tests/test_iroh_vfs_integration.py`, `tests/test_iroh_blob_store.py`, `tests/test_iroh_manifest.py`
- Metadata / pins: `tests/test_enhanced_pin_metadata.py`, `tests/test_datasets_metadata_index_contract.py`
- CAR: `tests/test_car_and_files_tools.py`, `tests/test_car_import_to_bucket.py`, `tests/test_phase3_car_files.py`
- Contract hardening: `tests/test_vfs_contract_hardening.py`, `tests/test_vfs_architecture.py`

### Current docs

- `docs/VFS_CONTRACT_SPEC.md`, `docs/filesystem_journal.md`, `docs/filesystem_spec/`
- `docs/features/vfs/`, `docs/features/BUCKET_SYSTEM_*.md`, `docs/features/pin-management/`
- `docs/iroh/filesystem-contract.md`, `bucket-tiering.md`, `recovery.md`, `operations.md`
- `docs/GRAPHRAG_AND_BUCKET_EXPORT.md`
- Future target: `docs/architecture/CONTENT_METADATA_VFS.md` (KDOC-013)

### Gaps

- Authoritative vs rebuildable state (content bytes vs Arrow indexes vs pin metadata vs journal) is not yet traced end-to-end in one guide.
- Recovery ordering across WAL, CAR, and filesystem journal is implementation-dense and under-summarized.
- Which bucket manager is the production default (`bucket_vfs_manager` vs `unified_bucket_interface` vs simplified variants) is ambiguous for newcomers.
- MCP tool coverage for WAL historically called out as missing in architecture audit; root `mcp/wal_mcp_tools.py` exists as shim—parity with MCP++ tool groups needs verification in KDOC-016.

### Unresolved owner decisions

1. **Bucket/VFS stack authority:** Single supported manager API for new features?
2. **Durability layering:** Is `storage_wal.py` + `filesystem_journal.py` the required path for all mutating VFS ops, or are some backends exempt?
3. **Metadata index role:** Is Arrow metadata authoritative, secondary, or rebuildable-from-pins/content?
4. **fsspec protocol brands:** IPFS fsspec registration vs Iroh-only packaging entry points—what is supported for `fsspec.open` users?

---

## 4. Cluster coordination and bespoke roles

### Candidate authority

| Concern | Paths |
|---|---|
| Cluster package (roles / manager) | `ipfs_kit_py/cluster/` (`role_manager.py`, `cluster_manager.py`, `distributed_coordination.py`, `monitoring.py`) |
| Cluster state | `ipfs_kit_py/cluster_state.py`, `cluster_state_sync.py`, `cluster_state_helpers.py`, `cluster_state_anyio.py` |
| Coordination / roles | `ipfs_kit_py/cluster_coordinator.py`, `cluster_management.py`, `cluster_dynamic_roles.py`, `cluster_authentication.py`, `cluster_monitoring.py` |
| Causal / task primitives | `ipfs_kit_py/merkle_clock.py`, `ipfs_kit_py/p2p_workflow_coordinator.py` |
| MCP++ durable coordination store | `ipfs_kit_py/mcp_server/mcplusplus/coordination_storage.py`, `event_dag.py`, `delegation.py` |
| State service (CLI/MCP parity) | `ipfs_kit_py/services/state_service.py` |
| Kubo IPFS Cluster *wrappers* (distinct family) | `ipfs_kit_py/ipfs_cluster_api.py`, `ipfs_cluster_ctl.py`, `ipfs_cluster_service.py`, `ipfs_cluster_daemon_manager.py`, `ipfs_cluster_follow*.py` |

### Compatibility / historical paths

| Path | Notes |
|---|---|
| Bespoke `cluster_*` top-level modules vs `cluster/` package | Parallel organization; import graph not single-rooted |
| `cluster_state` vs `cluster_state_anyio` | Sync/async twin |
| Root scripts / docs naming `start_3_node_cluster.py` | Cited in older docs; not present at repository root (stale claim) |
| `archive/` cluster and MCP server variants | Historical |

### Focused tests

- `tests/test_cluster_services.py`
- `tests/test_p2p_workflow.py`
- `tests/test_coordination_storage.py`
- `tests/test_vfs_replication.py` (replication edge with VFS)
- Workflow CI: `.github/workflows/cluster-tests.yml` (network/service assumptions—mark carefully)

### Current docs

- `docs/guides/CLUSTER_DEPLOYMENT_GUIDE.md`
- `docs/features/P2P_WORKFLOW_GUIDE.md`, `P2P_WORKFLOW_QUICK_REF.md`
- `docs/coordination-storage.md`
- Future targets: `docs/architecture/CLUSTER_COORDINATION.md` (KDOC-014)

### Gaps

- Bespoke cluster consistency model vs Kubo Cluster service wrappers are easy to conflate; no current guide separates them with constructor/API matrices.
- Role selection, task ownership (`p2p_workflow_coordinator`), and Merkle-clock ordering lack a single sequence diagram backed by tests.
- Authentication (`cluster_authentication.py`) trust boundary documentation is thin relative to code size.

### Unresolved owner decisions

1. **Cluster control-plane authority:** Bespoke `cluster_*` / `cluster/` stack vs Kubo `ipfs-cluster` wrappers vs MCP++ coordination store—which is production default for multi-node kit deployments?
2. **State store identity:** Relationship between `cluster_state.py`, `services/state_service.py`, and `DurableCoordinationStore` for “authoritative cluster state.”
3. **API/constructor mismatches** across cluster modules (flagged in objectives) remain to be enumerated with failing or missing tests rather than assumed.

---

## 5. Network transports (Iroh, libp2p, routing, P2P)

### Candidate authority

| Concern | Paths |
|---|---|
| Iroh service & protocol | `ipfs_kit_py/iroh/` (`service.py`, `client.py`, `backend.py`, `blob_store.py`, `manifest.py`, `protocol.py`, `security.py`, `multinode.py`, CLIs) |
| Iroh install / packaging hooks | `ipfs_kit_py/iroh_install_cli.py`, `install_iroh.py`, extras `iroh` in `pyproject.toml` |
| Iroh normative docs (retain) | `docs/iroh/*.md` (security, lifecycle, interoperability, threat-model, etc.) |
| libp2p integration | `ipfs_kit_py/libp2p/` (peer manager, gossipsub, kademlia, protocol adapters, `anyio_compat.py`) |
| P2P workflow | `ipfs_kit_py/p2p_workflow_coordinator.py`, `cli/p2p_workflow_cli.py` |
| MCP P2P transport | `ipfs_kit_py/mcp_server/p2p_transport.py` |
| Data routing | `ipfs_kit_py/routing/` (see section 2) |
| Kubo runtime / daemon | `ipfs_kit_py/kubo_runtime.py`, `ipfs_daemon_manager.py`, `ipfs.py` / clients (section 6 cross-link) |

### Compatibility / historical paths

| Path | Notes |
|---|---|
| `libp2p` optional extra tracking upstream `main` | Moving-target dependency; not a pinned contract |
| `libp2p_mocks.py` and test doubles | Non-production |
| Deprecated routing gRPC servers | Historical control path |
| Multiple daemon managers (`enhanced_daemon_manager.py`, `intelligent_daemon_manager.py`, cluster-enhanced variants) | Parallel lifecycle controllers |

### Focused tests

- Iroh suite: `tests/test_iroh_*.py` (backend, blob store, CLI gates, config, fsspec, install, MCP API, multinode, observability, packaging, performance, security, service, release readiness, …)
- libp2p: `tests/test_simple_libp2p.py` (coverage thinner than Iroh)
- P2P workflow: `tests/test_p2p_workflow.py`
- CI: `.github/workflows/iroh-ci.yml`

### Current docs

- Full `docs/iroh/` set (strongest normative external-facing transport docs in-tree)
- `docs/features/P2P_WORKFLOW_*.md`
- `ipfs_kit_py/libp2p/UNIVERSAL_CONNECTIVITY.md`, routing READMEs
- Future target: `docs/architecture/NETWORK_TRANSPORTS.md` (KDOC-015)

### Gaps

- Actual exposed P2P CLI/MCP surfaces vs aspirational workflow docs need a measured inventory.
- libp2p test depth and packaging pin policy are weak relative to Iroh’s contract suite.
- Cross-transport content path (Kubo bitswap vs Iroh blob vs libp2p) is not documented as a decision tree.

### Unresolved owner decisions

1. **Default content transport** for new deployments: Kubo, Iroh, or dual-write?
2. **libp2p dependency policy:** pin commit/tag vs track `main`; required vs optional for MCP P2P transport.
3. **Daemon manager authority** among enhanced/intelligent/cluster-enhanced managers for Kubo lifecycle.

---

## 6. MCP / control plane (MCP++, legacy MCP, multi-interface tools)

### Candidate authority

| Concern | Paths |
|---|---|
| Packaged MCP++ server | `ipfs_kit_py/mcp_server/server.py` (`PROTOCOL_VERSION`, anyio/trio, stdio/HTTP/P2P) |
| Hierarchical tool manager / single registry | `ipfs_kit_py/mcp_server/hierarchical_tool_manager.py`, `tools/` (`TOOL_GROUPS`: ipfs, iroh, pin, car, cluster, …), `tool_metadata.py` |
| FastMCP registrar (same registry) | `ipfs_kit_py/mcp_server/fastmcp_app.py` |
| MCP++ profiles / coordination | `ipfs_kit_py/mcp_server/mcplusplus/` |
| Fail-closed agent receipts | `ipfs_kit_py/mcp_server/agent_supervisor_receipts.py` |
| JS/TS SDK | `ipfs_kit_py/mcp_server/js_sdk/` |
| CLI for tools | `ipfs_kit_py/mcp_server/cli.py` (script `ipfs-kit-mcp-tools`) |
| Core operations helper | `ipfs_kit_py/mcp_server/core_operations.py` |

### Compatibility / historical paths

| Path | Notes |
|---|---|
| `ipfs_kit_py/mcp/` large legacy stack | Controllers, dashboard, servers, storage_manager, auth, HA, streaming—compatibility / prior generation |
| Root `mcp/` shims | `bucket_vfs_mcp_tools.py`, `secrets_mcp_tools.py`, `wal_mcp_tools.py`, etc.—bridge to older server layouts |
| Root `enhanced_mcp_server_with_daemon_mgmt.py`, `consolidated_mcp_dashboard.py` | Alternate entry scripts outside packaging scripts |
| `ipfs_kit_py/mcp/dashboard_old`, `templates_old` | Explicitly old |
| Architecture docs still centering `mcp/servers/*` shims | Pre-MCP++ narrative |

### Focused tests

- Conformance / server: `tests/test_mcp_jsonrpc_conformance.py`, `tests/test_mcp_server_integration.py`, `tests/test_mcp_initialization.py`, `tests/test_mcp_start_verification.py`
- Tools: `tests/test_mcp_tools_*.py`, `tests/test_comprehensive_tools.py`, `tests/test_tools_call_payload_parsing.py`, `tests/test_tool_status.py`
- VFS/MCP: `tests/test_mcp_vfs_*.py`, `tests/test_vfs_mcp_*.py`
- Receipts: `tests/test_agent_supervisor_receipts.py`
- Iroh MCP: `tests/test_iroh_mcp_api.py`
- UI smoke: `tests/test_mcp_ui_smoke.py`
- CI: `.github/workflows/mcp-server-ci.yml`, `final-mcp-server.yml`, `enhanced-mcp-server.yml`

### Current docs

- `docs/MCP_SERVER_MIGRATION_GUIDE.md`
- `docs/architecture/MCP_INTEGRATION_ARCHITECTURE.md`, `MCP_CONTROLLER_CONSOLIDATION.md`, `CLI_MCP_ARCHITECTURE_AUDIT.md`
- `docs/features/mcp/`
- Future target: `docs/architecture/MCP_CONTROL_PLANE.md` (KDOC-016); ADR draft slot `0003-mcp-runtime-authority.md`

### Gaps

- Tool counts and schema drift between hierarchical meta-tools and any remaining legacy controllers need measured generation (not hand inventories).
- Production-authority conflict between `mcp_server` (packaged) and still-present `mcp/` / root servers is the highest-severity control-plane documentation risk.
- Dashboard/JS SDK wiring relative to MCP++ HTTP Profile G paths is only partially described in server source.

### Unresolved owner decisions

1. **Production MCP runtime authority:** Is `ipfs_kit_py.mcp_server` the sole supported server for new deployments, with `ipfs_kit_py.mcp` and root `mcp/` strictly compatibility? (Objectives require a proposed ADR—do not treat as accepted here.)
2. **Tool registry singularity:** Confirm no second write-path registry remains for production tools outside `TOOL_GROUPS` / `HierarchicalToolManager`.
3. **Receipt store deployment defaults:** Where `DurableCoordinationStore` persists artifacts in operator installs, and multi-node read consistency expectations.
4. **Legacy dashboard lifecycle:** Maintain, archive, or re-bind to MCP++.

---

## 7. Configuration, local state, credentials, and trust

### Candidate authority

| Concern | Paths |
|---|---|
| Thin config module | `ipfs_kit_py/config.py`, `ipfs_kit_py/config_manager.py`, `ipfs_kit_py/config/` package |
| Backend documents (secrets redaction) | `backend_manager.py` + `backend_registry.redact_backend_config` / sensitive key regex |
| Credentials | `ipfs_kit_py/credential_manager.py`, `cli_secure_config.py` |
| Secrets | `ipfs_kit_py/enhanced_secrets_manager.py`, `aes_encryption.py` |
| Daemon configuration | `ipfs_kit_py/daemon_config_manager.py`, root `daemon_config_manager.py`, `ipfs_kit_py/daemon_cli.py` |
| Iroh security & service config | `ipfs_kit_py/iroh/security.py`, `iroh/config.py`, `docs/iroh/security.md`, `threat-model.md`, `credential-rotation.md`, `service-configuration.md` |
| Default state root | `~/.ipfs_kit` (backend manager, `StateService`); Kubo bin dir via `IPFS_KIT_BIN_DIR` / package-local `bin` in `kubo_runtime.py` |
| Example configs | `config/*.example.*`, `config/mcp_config.yml`, `config/iroh-*.example.*` |

### Compatibility / historical paths

| Path | Notes |
|---|---|
| Multiple config JSON/YAML trees under `config/` including test result dumps | Mixed operator examples and historical results |
| `migrate_secrets.py` (root) | One-off migration utility |
| Legacy MCP auth under `ipfs_kit_py/mcp/auth`, `mcp/security` | Prior control-plane security model |

### Focused tests

- `tests/test_secure_config.py`
- `tests/test_config_apis.py`, `tests/test_extended_config.py`
- `tests/test_daemon_config*.py`, `tests/test_enhanced_daemon_config.py`
- `tests/test_service_configuration.py`, `tests/test_service_config_form_fix.py`
- `tests/test_iroh_config.py`, `tests/test_iroh_security.py`
- `tests/test_dashboard_config_loading.py`

### Current docs

- `docs/credential_management.md`, `docs/guides/SECURE_CREDENTIALS_GUIDE.md`
- `docs/features/ENCRYPTED_CONFIG_GUIDE.md`
- `docs/iroh/security.md`, `threat-model.md`, `credential-rotation.md`
- `docs/guides/CONFIG_SAVE_FIX_REFERENCE.md` (fix-like)
- Future target: `docs/architecture/CONFIGURATION_STATE_AND_TRUST.md` (KDOC-018)

### Gaps

- Configuration precedence (env vs YAML vs defaults vs daemon managers) is fragmented across modules.
- State directory ownership (`~/.ipfs_kit` vs Kubo `~/.ipfs` vs Iroh service paths) needs a single operator map.
- Secret-bearing examples policy exists in the program plan but is not yet enforced by a doc guide (KDOC-005).

### Unresolved owner decisions

1. **Canonical config API:** `config_manager` vs backend YAML store vs daemon_config_manager vs Iroh config—composition rules for multi-service nodes.
2. **Credential storage backend** for production (encrypted file, OS keyring, env refs only).
3. **Trust boundary for MCP HTTP** exposure defaults (bind address, authn/z) relative to stdio-only agent use.

---

## 8. Async boundaries and optional dependencies

### Candidate authority

| Concern | Paths |
|---|---|
| anyio/trio runtime (MCP++) | `mcp_server/server.py` (anyio + trio backend, Hypercorn) |
| Dependency extras | `pyproject.toml` `[project.optional-dependencies]` (`iroh`, `fsspec`, `libp2p`, `arrow`, `api`, …) |
| JIT feature gates | `core` JIT manager, `jit_imports.py`, `deps_resolver.py` |
| Dual modules pattern | Widespread `foo.py` + `foo_anyio.py` (WAL telemetry, cluster state, arrow metadata, high_level_api helpers, etc.) |
| Install opt-in | `setup.py` / `kubo_runtime.py` / Iroh installers respecting `IPFS_KIT_AUTO_INSTALL_BINARIES=0` default |

### Compatibility / historical paths

| Path | Notes |
|---|---|
| `docs/ANYIO_MIGRATION.md`, `docs/COMPLETE_ANYIO_MIGRATION_SUMMARY.md` | Migration reports; not proof of universal AnyIO completion |
| `tools/asyncio_to_anyio_bulk_refactor.py` | Historical bulk refactor tool |
| asyncio-native modules still present | Expected; not every path is AnyIO |

### Focused tests

- `tests/test_anyio_migration.py`
- `tests/test_iroh_fsspec_async.py`
- Async-capable MCP/server tests as above
- pytest config: `anyio_mode = auto` in `pytest.ini`

### Current docs

- `docs/ANYIO_MIGRATION.md`, coverage/phase reports under `docs/`
- `docs/development/` (if present for async architecture; some guidance previously flagged stale)
- Future target: `docs/architecture/ASYNC_AND_OPTIONAL_DEPENDENCIES.md` (KDOC-017)

### Gaps

- No authoritative matrix of sync-only vs anyio vs trio-required entry points.
- Optional extra failure modes (import error vs degraded stub vs hard fail) differ by subsystem and are under-specified.

### Unresolved owner decisions

1. **AnyIO end-state:** Deliberate dual stack vs ongoing migration—objectives forbid claiming universal migration without evidence.
2. **Default async backend** for library callers (asyncio vs trio) outside MCP++.
3. **Stub vs fail-closed** policy when optional extras are missing (per feature).

---

## 9. IPFS client and Kubo integration family

### Candidate authority

| Concern | Paths |
|---|---|
| Primary client used by kit façade | `ipfs_kit_py/ipfs.py` (`class ipfs_py`; imported by `ipfs_kit.py`) |
| Package-local Kubo resolution | `ipfs_kit_py/kubo_runtime.py` |
| Daemon manager | `ipfs_kit_py/ipfs_daemon_manager.py` |
| Multiformats helpers | `ipfs_kit_py/ipfs_multiformats.py` |
| Installer | `ipfs_kit_py/install_ipfs.py` |

### Compatibility / historical paths

| Path | Notes |
|---|---|
| `ipfs_kit_py/ipfs_client.py` | Alternate `ipfs_py` “simplified MCP roadmap” client |
| `ipfs_kit_py/ipfs/ipfs_py.py` | Nested package client |
| `ipfs_kit_py/ipfs_kit_daemon_client.py` | Daemon client variant |
| Installers for Lotus/Lassie/Storacha | Adjacent binary families; optional |

### Focused tests

- `tests/test_daemon_*.py`, `tests/test_intelligent_daemon*.py`
- `tests/test_comprehensive_ipfs_test.py` (heavier)
- `tests/test_install_with_version_check.py`, `tests/test_updated_installer.py`
- Prefer unit/daemon_config tests for offline docs validation

### Current docs

- Installation and daemon guides; mixed freshness
- Architecture module organization still lists generic “core IPFS” without client disambiguation

### Gaps

- Three `ipfs_py` class definitions create import-path footguns for agents and new contributors.
- HTTP API surface coverage vs CLI subprocess coverage is not summarized.

### Unresolved owner decisions

1. **Canonical `ipfs_py` implementation** for library and MCP tools.
2. **Managed vs system Kubo** default when both exist on `PATH`.

---

## 10. Generated documentation and maintenance evidence

### Candidate authority

| Concern | Paths |
|---|---|
| Generator script | `tools/generate_api_docs.py` |
| Generated output tree | `docs/api_generated/` (`module_structure.md`, `AGENT_GUIDE.md`, `dependencies.md`, `doc_status.md`, …) |
| Doc workflows | `.github/workflows/docs.yml`, `pages.yml`, `auto-doc-maintenance.yml` |
| Packaging as generator input | `pyproject.toml`, package docstrings |

### Compatibility / historical paths

| Path | Notes |
|---|---|
| `docs/api_generated/module_structure.md` header date **2025-10-29** | Stale relative to 2026 tree; covers fewer modules than present package |
| Hand-maintained API notes under `docs/api/` | May drift from generated |
| Phase/coverage report Markdown at `docs/` root | Historical campaign artifacts |

### Focused tests

- No dedicated pytest suite asserts generated-doc freshness in the default offline set; validation is workflow/script based.
- Packaging-related: `tests/test_iroh_packaging.py`, import path tests indirectly protect public surfaces.

### Current docs

- `docs/api_generated/*` (generator-owned; do not hand-edit bodies)
- `docs/guides/DOCUMENTATION_GUIDE.md` target owned by KDOC-005 (lifecycle rules)
- Program plan sections on generated class

### Gaps

- Generated inventory is out of date; refresh is KDOC-046 ownership.
- No checked-in contract that CI fails on generator drift for architecture-critical modules.
- Competing navigation indexes still point at mixed generated/authored/historical material (KDOC-060).

### Unresolved owner decisions

1. **Generator toolchain and publish path** (Pages vs in-repo only)—ADR slot `0009-documentation-site-toolchain.md`.
2. **Whether `docs/api/` remains** alongside `api_generated/` or becomes a thin stub.

---

## 11. Compatibility layers and archival boundaries (cross-cutting)

### Candidate authority

| Concern | Paths |
|---|---|
| Explicit archive trees | `archive/`, `backup/`, `docs/ARCHIVE/` |
| Compatibility helpers | `ipfs_kit_py/compat.py`, lazy `__getattr__` patterns in package root |
| Root `mcp/` shim package | Compatibility bridge for older tool modules |
| Program classification rules | `docs/documentation_plan.md` authority classes (Canonical / Generated / Historical / External / Proposed) |

### Compatibility / historical paths

- `*.broken`, `*.corrupted_backup`, `*.deprecated_backup`, `*_fixed.py`, `*_improved.py`, `*_updated.py`, `*_old.py`
- Embedded third-party snapshots and gitlinked external docs (do not fetch; classify in KDOC-001/041+)
- `tests/archived_stale_tests/` (pytest norecursedirs)

### Focused tests

- `tests/test_cli_deprecations_*.py`
- `tests/test_iroh_compatibility_record.py`
- Import/CLI verification tests that encode “supported path” expectations

### Current docs

- Future target: `docs/architecture/COMPATIBILITY_LAYERS.md` (KDOC-019)
- Existing audits under `docs/architecture/*AUDIT*`

### Gaps

- No machine-readable allowlist of supported modules vs backup siblings.
- Agents frequently discover backup files via glob and treat them as peers—documentation must label them systematically.

### Unresolved owner decisions

1. **Retention policy** for `*.fixed` / backup siblings in the main package tree vs forced move to `archive/`.
2. **Deprecation timeline** for legacy MCP and simplified bucket stacks.

---

## Cross-reference: planned architecture guides → this map

| Future guide (KDOC) | Primary map sections |
|---|---|
| `SYSTEM_OVERVIEW.md` / `RUNTIME_AND_ENTRYPOINTS.md` | §1, §9, §11 |
| `STORAGE_BACKEND_SYSTEM.md` | §2 |
| `CONTENT_METADATA_VFS.md` | §3 |
| `CLUSTER_COORDINATION.md` | §4 |
| `NETWORK_TRANSPORTS.md` | §5 |
| `MCP_CONTROL_PLANE.md` | §6 |
| `ASYNC_AND_OPTIONAL_DEPENDENCIES.md` | §8 |
| `CONFIGURATION_STATE_AND_TRUST.md` | §7 |
| `COMPATIBILITY_LAYERS.md` | §11 |
| Generated refresh (KDOC-046) | §10 |

---

## Aggregate unresolved decisions (owner confirmation required)

These items are intentionally **not** resolved by this map. Downstream ADRs may propose outcomes; agents must not treat proposals as accepted.

| ID | Topic | Blocking for |
|---|---|---|
| U-01 | Package version string `0.2.0` vs `0.3.0` | Runtime overview, release docs |
| U-02 | Canonical CLI composition (`cli.py` vs `unified_cli_dispatcher.py`) | Runtime, operator guides |
| U-03 | High-level API module vs package split | Python API docs |
| U-04 | Backend live-adapter factory and dual `ipfs_backend` modules | Storage guide |
| U-05 | Bucket/VFS manager authority among parallel stacks | Content/VFS guide |
| U-06 | WAL/journal durability requirements per backend | Content/VFS, ADR 0005 |
| U-07 | Arrow metadata authoritative vs rebuildable | Content/VFS, ADR 0005 |
| U-08 | Bespoke cluster vs Kubo Cluster vs MCP++ coordination authority | Cluster guide, ADR 0008 |
| U-09 | Default content transport (Kubo / Iroh / dual) | Network guide, ADR 0006 |
| U-10 | libp2p pin/track policy and MCP P2P requirements | Network, MCP guides |
| U-11 | **MCP production runtime authority** (`mcp_server` vs `mcp` vs root servers) | MCP guide, ADR 0003 |
| U-12 | Canonical `ipfs_py` client implementation | Runtime, MCP, storage |
| U-13 | Config/state directory and credential storage composition | Trust guide, ADR 0007 |
| U-14 | AnyIO end-state and missing-extra degradation policy | Async guide, ADR 0001/0004 |
| U-15 | Generated-doc toolchain and navigation exclusivity | KDOC-046, KDOC-060, ADR 0009 |
| U-16 | Daemon manager authority (enhanced vs intelligent vs cluster-enhanced) | Runtime, operations |
| U-17 | fsspec supported protocol set beyond packaged Iroh entries | Storage, integration docs |

---

## Change triggers

Revisit this map when any of the following change:

- `[project.scripts]`, fsspec entry points, or package version fields
- `backend_registry.py` / `backend_manager.py` contracts
- `mcp_server` tool registry layout or packaged server entry
- Addition/removal of parallel client, bucket, cluster, or CLI modules
- Pytest discovery paths or large moves between `tests/` and archived trees
- Generator output under `docs/api_generated/` after KDOC-046 refresh

**Last verified:** 2026-08-03 (static inspection of packaging metadata, package layout, focused test names, workflows, and existing architecture/Iroh docs; no live network services; `IPFS_KIT_AUTO_INSTALL_BINARIES` unset/disabled for doc validation policy).
