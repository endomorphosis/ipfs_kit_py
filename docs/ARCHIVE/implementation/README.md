# Archive category: implementation reports

| Field | Value |
|---|---|
| **Document class** | Historical (category index) |
| **Authority class** | Historical — **not current** guidance |
| **Status** | active (curated intake index) |
| **Owner / task** | KDOC-045 (BATCH-HIST-IMPL) |
| **Goal id** | KDOC-G050 |
| **Track** | information-architecture |
| **Last verified** | 2026-08-04 |
| **Register family** | **H1** — `docs/implementation/` |
| **Duplicate set** | **DS-12** — Implementation COMPLETE bulk vs architecture |
| **Evidence** | [`docs/audits/HISTORICAL_DOCUMENT_REGISTER.md`](../../audits/HISTORICAL_DOCUMENT_REGISTER.md) §4.1; [`docs/audits/DUPLICATE_AND_REDIRECT_PLAN.md`](../../audits/DUPLICATE_AND_REDIRECT_PLAN.md) §4.12; [`docs/ARCHIVE/README.md`](../README.md) |
| **Scope** | Report-like implementation completion / summary bulk (register H1) and related episode summaries already under ARCHIVE |
| **Non-goals** | Archiving maintained architecture, API, ops, feature, or testing **guides**; navigation rewrites (KDOC-060); generated trees |

> **Stop — historical material only.**  
> This category indexes **campaign implementation reports** (`*COMPLETE*`, `*SUMMARY*`, phase narratives).  
> They are **provenance**, not live API, architecture, MCP runtime, CLI, or operations truth.  
> Present-tense language inside source reports (“production ready,” “validation complete”) is **historical rhetoric**.  
> Prefer packaging metadata, focused tests, and the **current replacements** in [§4](#4-where-to-go-instead-current-replacements).

**Parent boundary:** [docs/ARCHIVE/README.md](../README.md) — reading rules, authority rank, and agent checklist apply to every path in this family.

---

## 1. Purpose of this category

`docs/ARCHIVE/implementation/` is the **curated historical home** for the large implementation-campaign bulk that the reviewed register classifies as **Archive** (H1 / BATCH-HIST-IMPL).

| This category does | This category does **not** |
|---|---|
| Quarantine completion / summary **reports** as discoverable history | Hold current subsystem design authority |
| Preserve **original campaign context** (source path, date, episode topic) | Replace architecture or feature guides |
| Point every topic cluster at a **current replacement** | Claim coverage %, “all systems operational,” or packaging entry points |
| Coordinate with already-quarantined implementation-summaries | Accept maintained process docs from `docs/development/`, `docs/api/`, `docs/architecture/` Wave 0 guides |

**Acceptance intent (KDOC-045):** no maintained current guide is archived here; inbound canonical paths are not broken by this index; every registered report carries original context **plus** current replacement links.

---

## 2. Intake status and physical layout

### 2.1 Disposition (register)

| Field | Value |
|---|---|
| **Source path** | `docs/implementation/` |
| **Scale (baseline)** | ~75 files / **73 markdown** (inventory / register H1) |
| **Date / baseline** | Implementation-campaign era through mid-2025–2026; sample `EXECUTIVE_SUMMARY.md` dated **2025-10-22**; `FINAL_IMPLEMENTATION_SUMMARY.md` dated **2025-12-19**; July 2026 DOC-KIT links elevated discoverability without re-authoring as architecture |
| **Current authority** | **Historical (provenance only)** |
| **Move risk** | **High** (dense COMPLETE/SUMMARY linkage; DS-12 inbound impact) |
| **Disposition** | **Archive** under this category; interim **Drop-from-navigation** until exclusive nav (KDOC-060) |
| **Replacement gate (DS-12)** | Topic replacements exist under architecture / features / ops / reference (KDOC-010..019, 030..039). Bulk filesystem `mv` remains **redirect-sensitive** because of High move risk |

### 2.2 Where the report bodies live today

| Location | Role |
|---|---|
| **`docs/implementation/**`** (source family) | Report bodies remain path-stable at original locations so **inbound links do not 404** until Stub Redirect owners rewrite referrers (redirect plan §5–6). Treat every file there with the **same Historical rules** as ARCHIVE. |
| **This directory (`docs/ARCHIVE/implementation/`)** | **Category index** (this README): original context + replacement map + intake rules. Destination for future co-located intake when stubs/nav-unlink land. |
| **[`docs/ARCHIVE/implementation-summaries/`](../implementation-summaries/)** | Sibling quarantine for feature episode summaries already moved (e.g. auto-healing). Not a second current guide tree. |
| **[`docs/ARCHIVE/summaries/`](../summaries/)** | Related CLI/dashboard/daemon summaries already quarantined. |

**Hard rule:** This task does **not** archive packaging docs, Wave 0 audits, protected program files, generated API trees, or maintained feature/architecture guides. Only register-approved **report-like** implementation bulk is in scope.

### 2.3 Future physical intake (when redirects allow)

When Stub Redirect or Nav-unlink is applied for High-risk referrers (DS-12; ~12 markdown paths mention `implementation/`):

1. Prefer `git mv` into this directory (or a dated subfolder) to preserve history.
2. Leave a short **Historical redirect stub** at the old path (redirect plan §5.1).
3. Keep or update the provenance row in [§3](#3-source-inventory-original-context) (source path, date, replacement).
4. Add the standard Historical banner (ARCHIVE README §2.3).
5. Do **not** rewrite archived prose into present tense.

Until then, **this index is the curated destination narrative**; source paths remain the discoverable file bodies.

---

## 3. Source inventory (original context)

All paths below are **Historical**. Scale and membership track register H1; listings are exhaustive for the source tree as of this task verification.

### 3.1 Directory-level provenance

| Field | Value |
|---|---|
| **Original root** | `docs/implementation/` |
| **Original README** | `docs/implementation/README.md` — stub “Implementation documentation” (not a current map) |
| **Pattern classes** | `*_COMPLETE.md`, `*_IMPLEMENTATION_COMPLETE.md`, `*_SUMMARY.md`, `FINAL_*`, `EXECUTIVE_*`, phase narratives under `phases/` |
| **Non-markdown dumps** | `BATCH7_VERIFICATION.txt`, `COMPLETION_SUMMARY.txt` — provenance only |
| **Batch owner** | **BATCH-HIST-IMPL** (KDOC-045 primary; KDOC-041 for duplicate resolution) |

### 3.2 Topic clusters → original members → replacements

Use the **replacement** column for present-tense work. Source paths are relative to `docs/implementation/` unless noted.

#### A. Executive / roll-up narratives

| Original path | Original context | Prefer instead (current) |
|---|---|---|
| `EXECUTIVE_SUMMARY.md` | **2025-10-22** — CI/CD + MCP dashboard validation “all systems operational” campaign | Packaging scripts + [`MCP_CONTROL_PLANE.md`](../../architecture/MCP_CONTROL_PLANE.md); CI truth under `.github/workflows/` + [`docs/development/testing_guide.md`](../../development/testing_guide.md) |
| `FINAL_IMPLEMENTATION_SUMMARY.md` | **2025-12-19** — multi-week “completed in hours” roll-up | [`SYSTEM_OVERVIEW.md`](../../architecture/SYSTEM_OVERVIEW.md), [`SOURCE_OF_TRUTH_MAP.md`](../../architecture/SOURCE_OF_TRUTH_MAP.md) |
| `FINAL_IMPLEMENTATION_NOTES.md`, `IMPLEMENTATION_COMPLETE_SUMMARY.md`, `REAL_IMPLEMENTATION_COMPLETE.md`, `COMPREHENSIVE_REAL_IMPLEMENTATIONS_COMPLETE.md`, `COMPREHENSIVE_IMPROVEMENTS_COMPLETE.md`, `SUMMARY_OF_CHANGES.md`, `PHASE2_IMPLEMENTATION_SUMMARY.md`, `DIAGNOSTIC_SUMMARY.md`, `SERVICE_UPDATE_SUMMARY.md` | Episode roll-ups and “real implementation” banners | Architecture + subsystem guides; never as live completion receipts |
| `FILE_REORGANIZATION_SUMMARY.md`, `REORGANIZATION_SUCCESS_REPORT.md` | Tree reorganization campaigns | [`docs/guides/DOCUMENTATION_GUIDE.md`](../../guides/DOCUMENTATION_GUIDE.md); program plan (protected) |

#### B. VFS, buckets, and content metadata

| Original path | Original context | Prefer instead (current) |
|---|---|---|
| `BUCKET_VFS_INTERFACES_COMPLETE.md`, `INDIVIDUAL_BUCKET_VFS_COMPLETE.md`, `ENHANCED_VFS_DOWNLOAD_COMPLETE.md`, `ENHANCED_VFS_PACKAGE_REFACTORING_COMPLETE.md`, `FTP_SSHFS_VFS_BACKENDS_COMPLETE.md`, `GIT_VFS_TRANSLATION_AND_SSHFS_IMPLEMENTATION.md`, `SSHFS_GIT_VFS_IMPLEMENTATION_COMPLETE.md`, `IPFS_VFS_INDEX_SYSTEM_COMPLETE.md`, `VFS_DASHBOARD_INTEGRATION_COMPLETE.md`, `VFS_VERSION_TRACKING_COMPLETE.md`, `FILE_MANAGER_INTEGRATION_COMPLETE.md` | VFS / bucket / backend completion episodes | [`CONTENT_METADATA_VFS.md`](../../architecture/CONTENT_METADATA_VFS.md), [`docs/features/vfs/`](../../features/vfs/), [`STORAGE_BACKEND_SYSTEM.md`](../../architecture/STORAGE_BACKEND_SYSTEM.md) |
| `PARQUET_BUCKET_INDEX_COMPLETE.md`, `PARQUET_IPLD_IMPLEMENTATION_SUMMARY.md`, `ENHANCED_PARQUET_METADATA_COMPLETE.md`, `DUCKDB_PARQUET_CONVERSION_COMPLETE.md`, `COMPREHENSIVE_COLUMNAR_IPLD_IMPLEMENTATION_COMPLETE.md` | Columnar / Parquet / IPLD campaign reports | Storage architecture + [`docs/reference/storage_backends.md`](../../reference/storage_backends.md), [`docs/reference/metadata_index.md`](../../reference/metadata_index.md) |

#### C. Pins, Filecoin, replication, WAL

| Original path | Original context | Prefer instead (current) |
|---|---|---|
| `ENHANCED_PIN_INTEGRATION_COMPLETE.md`, `PIN_GET_CAT_IMPLEMENTATION_COMPLETE.md`, `PIN_METADATA_INDEX_COMPLETE_FIX.md` | Pin API / index episodes | [`docs/features/pin-management/`](../../features/pin-management/), packaging entry points |
| `FILECOIN_PIN_IMPLEMENTATION_SUMMARY.md`, `FILECOIN_PIN_FINAL_SUMMARY.md`, `FILECOIN_IPFS_BACKEND_IMPLEMENTATION_PLAN.md` | Filecoin pin plan + summaries | [`FILECOIN_PIN_USER_GUIDE.md`](../../features/pin-management/FILECOIN_PIN_USER_GUIDE.md), [`FILECOIN_PIN_CONFIGURATION.md`](../../features/pin-management/FILECOIN_PIN_CONFIGURATION.md) |
| `REPLICATION_MANAGEMENT_COMPLETE.md`, `THREE_TIER_POLICY_IMPLEMENTATION_COMPLETE.md` | Replication / policy episodes | Cluster + storage ops: [`CLUSTER_COORDINATION.md`](../../architecture/CLUSTER_COORDINATION.md), [`docs/operations/cluster_management.md`](../../operations/cluster_management.md) |
| `WAL_FS_JOURNAL_REMOVAL_COMPLETE.md` | WAL / FS journal removal narrative (**not** CLI truth — freshness F-class) | [`docs/reference/write_ahead_log.md`](../../reference/write_ahead_log.md), [`docs/reference/wal_telemetry_api.md`](../../reference/wal_telemetry_api.md) |

#### D. Cluster, daemon, roles, multiprocessing

| Original path | Original context | Prefer instead (current) |
|---|---|---|
| `CLUSTER_CONFIG_IMPLEMENTATION_COMPLETE.md`, `CLUSTER_FOLLOW_ENHANCEMENT_COMPLETE.md` | Cluster config / follow episodes | [`CLUSTER_COORDINATION.md`](../../architecture/CLUSTER_COORDINATION.md), `docs/operations/cluster_*.md` |
| `DAEMON_ARCHITECTURE_REFACTORING_COMPLETE.md`, `DAEMON_FILESYSTEM_FIXES_COMPLETE.md`, `DAEMON_STATE_MANAGEMENT_VERIFICATION_COMPLETE.md` | Daemon refactor / state episodes | [`RUNTIME_AND_ENTRYPOINTS.md`](../../architecture/RUNTIME_AND_ENTRYPOINTS.md), [`COMPATIBILITY_LAYERS.md`](../../architecture/COMPATIBILITY_LAYERS.md) |
| `ROLE_BASED_COMPONENT_DISABLING_IMPLEMENTATION.md`, `MULTI_PROCESSING_IMPLEMENTATION_COMPLETE.md`, `MULTIPROCESSING_IMPLEMENTATION_SUMMARY.md`, `RESOURCE_TRACKING_IMPLEMENTATION_COMPLETE.md` | Roles / MP / resource tracking | [`docs/operations/resource_management.md`](../../operations/resource_management.md), configuration trust guide |

#### E. MCP, dashboard, logging, monitoring

| Original path | Original context | Prefer instead (current) |
|---|---|---|
| `MCP_SYSTEMD_IMPLEMENTATION_SUMMARY.md`, `MODULAR_IMPLEMENTATION_SUMMARY.md`, `TOOL_COVERAGE_ENHANCEMENT_COMPLETE.md`, `TEMPLATE_INTEGRATION_VERIFICATION.md` | MCP packaging / modular / tool coverage episodes | Packaging `ipfs-kit-mcp` + [`MCP_CONTROL_PLANE.md`](../../architecture/MCP_CONTROL_PLANE.md); never ARCHIVE status as “primary MCP” |
| `DASHBOARD_IMPLEMENTATION_SUMMARY.md`, `COMPREHENSIVE_DASHBOARD_ENHANCEMENT_COMPLETE.md`, `LOG_STYLING_IMPLEMENTATION_SUMMARY.md`, `LOG_AGGREGATION_IMPLEMENTATION_COMPLETE.md`, `COMPREHENSIVE_LOGGING_IMPLEMENTATION.md`, `MONITORING_IMPLEMENTATION_SUMMARY.md` | Dashboard / log / monitoring campaigns | [`docs/features/MONITORING_GUIDE.md`](../../features/MONITORING_GUIDE.md), [`docs/operations/observability.md`](../../operations/observability.md), [`docs/features/dashboard/`](../../features/dashboard/) |

#### F. Network, libp2p, P2P, connectivity

| Original path | Original context | Prefer instead (current) |
|---|---|---|
| `LIBP2P_INTEGRATION_COMPLETE.md`, `UNIVERSAL_CONNECTIVITY_SUMMARY.md`, `P2P_WORKFLOW_IMPLEMENTATION_SUMMARY.md`, `UNIFIED_INTEGRATION_COMPLETE.md` | Connectivity / P2P integration episodes | [`NETWORK_TRANSPORTS.md`](../../architecture/NETWORK_TRANSPORTS.md), [`docs/features/P2P_WORKFLOW_GUIDE.md`](../../features/P2P_WORKFLOW_GUIDE.md), integration hub under `docs/integration/` (refresh-owned, not this archive) |

#### G. Config, Arrow, error fixes, tests, blueprints

| Original path | Original context | Prefer instead (current) |
|---|---|---|
| `ENCRYPTED_CONFIG_SUMMARY.md` | Encrypted config episode | [`CONFIGURATION_STATE_AND_TRUST.md`](../../architecture/CONFIGURATION_STATE_AND_TRUST.md), [`docs/features/ENCRYPTED_CONFIG_GUIDE.md`](../../features/ENCRYPTED_CONFIG_GUIDE.md) |
| `ARROW_IPC_ZERO_COPY_IMPLEMENTATION.md` | Arrow IPC implementation note | Architecture storage / ops; related fix history under [`docs/ARCHIVE/fixes/`](../fixes/) |
| `CIRCULAR_IMPORT_FIXES_COMPLETE.md`, `COMPREHENSIVE_ERROR_FIXES_COMPLETE.md` | Import / error fix campaigns | Source tree + CHANGELOG / issues; not operator runbooks |
| `TEST_SUITE_SUMMARY.md` | Test suite campaign summary | [`docs/development/testing_guide.md`](../../development/testing_guide.md), `pytest.ini`, CI workflows |
| `phases/COMPREHENSIVE_REFACTORING_PHASE1_SUMMARY.md`, `phases/COMPREHENSIVE_REFACTORING_PHASE2_SUMMARY.md`, `phases/PHASE1_IMPLEMENTATION_COMPLETE.md`, `phases/PHASES_8_9_IMPLEMENTATION_COMPLETE.md`, `phases/PHASE_8_12_FEATURES.md`, `phases/MEDIUM_TERM_IMPLEMENTATION_BLUEPRINT.md` | Phased refactor / feature blueprint narratives | [`SYSTEM_OVERVIEW.md`](../../architecture/SYSTEM_OVERVIEW.md); treat blueprints as **Proposed/Historical**, not roadmap authority |

### 3.3 Related material already under ARCHIVE (not re-homed here)

| Path | Context | Prefer instead |
|---|---|---|
| [`../implementation-summaries/AUTO_HEALING_IMPLEMENTATION_SUMMARY.md`](../implementation-summaries/AUTO_HEALING_IMPLEMENTATION_SUMMARY.md) | Auto-healing episode summary (DS-05 multi-home set) | [`docs/features/auto-healing/AUTO_HEALING.md`](../../features/auto-healing/AUTO_HEALING.md) |
| [`../summaries/*`](../summaries/) | CLI / dashboard / daemon summaries | [`docs/api/cli_reference.md`](../../api/cli_reference.md), architecture runtime guides |

Feature-tree report wrappers (`docs/features/**/*SUMMARY*`, `*COMPLETE*`) remain **Split** under BATCH-HIST-FEAT (H13) — archive **reports only**, never the maintained feature guides beside them.

---

## 4. Where to go instead (current replacements)

| Topic | Prefer (maintained / current) | Do **not** use implementation reports as |
|---|---|---|
| **System architecture** | [`SYSTEM_OVERVIEW.md`](../../architecture/SYSTEM_OVERVIEW.md), [`RUNTIME_AND_ENTRYPOINTS.md`](../../architecture/RUNTIME_AND_ENTRYPOINTS.md), [`COMPATIBILITY_LAYERS.md`](../../architecture/COMPATIBILITY_LAYERS.md), [`SOURCE_OF_TRUTH_MAP.md`](../../architecture/SOURCE_OF_TRUTH_MAP.md) | Subsystem design authority |
| **MCP / control plane** | Packaging `ipfs-kit-mcp` + [`MCP_CONTROL_PLANE.md`](../../architecture/MCP_CONTROL_PLANE.md) | Production “status” or alternate server paths |
| **Storage / VFS** | [`STORAGE_BACKEND_SYSTEM.md`](../../architecture/STORAGE_BACKEND_SYSTEM.md), [`CONTENT_METADATA_VFS.md`](../../architecture/CONTENT_METADATA_VFS.md), [`docs/features/vfs/`](../../features/vfs/), [`docs/reference/storage_backends.md`](../../reference/storage_backends.md) | Backend inventory from COMPLETE banners |
| **Cluster / network** | [`CLUSTER_COORDINATION.md`](../../architecture/CLUSTER_COORDINATION.md), [`NETWORK_TRANSPORTS.md`](../../architecture/NETWORK_TRANSPORTS.md), `docs/operations/` | Historical multi-node “done” tables |
| **Config / trust** | [`CONFIGURATION_STATE_AND_TRUST.md`](../../architecture/CONFIGURATION_STATE_AND_TRUST.md) | Ad-hoc campaign config notes |
| **Async / optional deps** | [`ASYNC_AND_OPTIONAL_DEPENDENCIES.md`](../../architecture/ASYNC_AND_OPTIONAL_DEPENDENCIES.md), [`async_architecture.md`](../../development/async_architecture.md) | AnyIO “100% complete” claims in reports |
| **Python / CLI / install** | [`high_level_api.md`](../../api/high_level_api.md), [`cli_reference.md`](../../api/cli_reference.md), [`installation_guide.md`](../../installation_guide.md) | Implementation CLI digressions |
| **Testing process** | [`testing_guide.md`](../../development/testing_guide.md), CI, `pytest.ini` | Test suite summaries as coverage proof |
| **Pins / Filecoin** | [`docs/features/pin-management/`](../../features/pin-management/) | Filecoin pin FINAL/SUMMARY as operator policy |
| **WAL / telemetry** | [`docs/reference/write_ahead_log.md`](../../reference/write_ahead_log.md), `wal_telemetry_*.md` | `WAL_FS_JOURNAL_REMOVAL_COMPLETE.md` as CLI truth |
| **Auto-healing** | [`docs/features/auto-healing/AUTO_HEALING.md`](../../features/auto-healing/AUTO_HEALING.md) | Implementation-summary duplicates |
| **Documentation program** | Protected plan + [`docs/audits/*`](../../audits/) | Project COMPLETE checklists as verification |

---

## 5. What must never enter this category as “current”

| Keep out / do not reclassify as archive bulk | Why |
|---|---|
| Wave 0 maps & program evidence (`SOURCE_OF_TRUTH_MAP`, `GLOSSARY`, `docs/audits/*`) | Program evidence — not campaign dumps |
| Protected files (`documentation_plan.md`, objectives, todo board) | Program-control |
| Generated API (`docs/api_generated/`) | KDOC-043/046 |
| Maintained feature guides under `docs/features/**` (non-report children) | Split retain (H13) |
| Architecture guides produced by KDOC-010..019 | Canonical replacements |
| External / embedded project snapshots | KDOC-044 |
| Competing root indexes (`index.md`, `README.md`, `DOCUMENTATION_INDEX.md`) | Navigation surfaces — KDOC-060, never historical bulk |

---

## 6. Link and move safety

| Constraint | Application here |
|---|---|
| **No maintained guide archived** | Only H1 report-like bulk and already-quarantined summaries; guides stay in architecture/features/ops |
| **No knowingly broken inbound canonical links** | Report bodies stay at `docs/implementation/**` until Stub Redirect / Nav-unlink owners act; this index does not delete or rename them |
| **Original context + replacements** | §3 tables carry source path, campaign context/dates, and replacement links |
| **High move risk** | Bulk `mv` deferred relative to status/fixes (redirect plan P3.1); Drop-from-navigation is the interim disposition |
| **Nav-unlink** | Exclusive navigation (KDOC-060) must not promote `docs/implementation/*COMPLETE*` as start-here |

**Inbound-impact note (DS-12):** approximately a dozen markdown referrers mention `implementation/` path patterns. Critical index files may still list historical COMPLETE paths — those are navigation defects for KDOC-060, not reasons to treat reports as current.

---

## 7. Agent and human checklist

Before citing anything in this family:

- [ ] Am I looking for **history/provenance**, not how the system works today?
- [ ] Have I checked packaging, source, tests, or a **Canonical** architecture/feature guide?
- [ ] Am I ignoring “complete / production ready / all systems operational” banners as live evidence?
- [ ] If I must link a report, is the link labeled **Historical** / **not current**?
- [ ] Am I about to archive a **maintained guide**? If yes — **stop** (out of scope / wrong disposition).

---

## 8. Related program artifacts

| Artifact | Role |
|---|---|
| [docs/ARCHIVE/README.md](../README.md) | Archive boundary and reading rules |
| [docs/ARCHIVE/status-and-fixes/README.md](../status-and-fixes/README.md) | Parallel curated intake for status + fix reports (H5/H6) |
| [docs/audits/HISTORICAL_DOCUMENT_REGISTER.md](../../audits/HISTORICAL_DOCUMENT_REGISTER.md) | H1 disposition, move risk, batch owner |
| [docs/audits/DUPLICATE_AND_REDIRECT_PLAN.md](../../audits/DUPLICATE_AND_REDIRECT_PLAN.md) | DS-12 gate, redirect patterns, phase P3.1 |
| [docs/guides/DOCUMENTATION_GUIDE.md](../../guides/DOCUMENTATION_GUIDE.md) | Authority classes; Historical may not recommend as current |
| KDOC-060 (planned) | Drop historical implementation targets from exclusive navigation |

---

**Bottom line:** Implementation COMPLETE/SUMMARY bulk is **historical provenance**. This category index curates it under ARCHIVE with original context and current replacement links. For architecture, API, MCP, storage, cluster, and testing of the tree you are on, use [§4](#4-where-to-go-instead-current-replacements) — not `docs/implementation/*` banners.
