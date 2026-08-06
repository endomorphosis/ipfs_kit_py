# Archive category: status reports and fix notes

| Field | Value |
|---|---|
| **Document class** | Historical (category index) |
| **Authority class** | Historical — **not current** guidance |
| **Status** | active (curated intake index) |
| **Owner / task** | KDOC-045 (BATCH-HIST-STATUS + BATCH-HIST-FIX) |
| **Goal id** | KDOC-G050 |
| **Track** | information-architecture |
| **Last verified** | 2026-08-04 |
| **Register families** | **H5** — `docs/status_reports/`; **H6** — `docs/fixes/`; merges **H11** material already under `ARCHIVE/status-reports/` and `ARCHIVE/fixes/` |
| **Duplicate sets** | **DS-20 / DS-21** (status + fixes bulk); **DS-06** (MCP refactoring dual); related DS-07 status echoes |
| **Evidence** | [`docs/audits/HISTORICAL_DOCUMENT_REGISTER.md`](../../audits/HISTORICAL_DOCUMENT_REGISTER.md) §4.3–4.4, §4.9; [`docs/audits/DUPLICATE_AND_REDIRECT_PLAN.md`](../../audits/DUPLICATE_AND_REDIRECT_PLAN.md) §4.19; [`docs/ARCHIVE/README.md`](../README.md) |
| **Scope** | Point-in-time status / refactoring / integration summaries and one-off fix write-ups |
| **Non-goals** | Archiving maintained ops runbooks, architecture guides, CI validation guides, or feature how-tos; exclusive navigation rewrites (KDOC-060) |

> **Stop — historical material only.**  
> This category indexes **status reports** and **fix notes**: campaign summaries, refactoring “complete” narratives, and one-off bug/fix write-ups.  
> They are **provenance**, not live architecture, MCP status, dashboard configuration policy, or operator runbooks.  
> Prefer packaging, focused tests, CHANGELOG/issues, and the **current replacements** in [§4](#4-where-to-go-instead-current-replacements).

**Parent boundary:** [docs/ARCHIVE/README.md](../README.md) — reading rules, authority rank, and agent checklist apply to every path in this family.

---

## 1. Purpose of this category

`docs/ARCHIVE/status-and-fixes/` is the **curated merge destination** for register-approved status and fix history:

| Intake stream | Register | Disposition |
|---|---|---|
| `docs/status_reports/**` | H5 | **Archive** → this category |
| `docs/fixes/**` | H6 | **Archive** → this category (pair with existing ARCHIVE fixes) |
| `docs/ARCHIVE/status-reports/**` | H11 (already quarantined) | **Retain-historical**; indexed here for one reading path |
| `docs/ARCHIVE/fixes/**` | H11 (already quarantined) | **Retain-historical**; indexed here for one reading path |

| This category does | This category does **not** |
|---|---|
| Unify status + fix **report** history under one ARCHIVE reading path | Publish current “implementation status” |
| Preserve **original campaign context** and source paths | Replace MCP control-plane or packaging authority |
| Point readers at **current replacements** (or explicit “none — track in issues”) | Absorb CI **runbooks** (H12 retain split) or testing **health matrix** (H9 retain split) |
| Document merge/survivor notes for dual status reports (DS-06) | Treat ARCHIVE MCP status as primary product status (F-017) |

**Acceptance intent (KDOC-045):** no maintained current guide is archived here; inbound canonical links are not knowingly broken; moved/curated reports carry original context **plus** current replacement links.

---

## 2. Intake status and physical layout

### 2.1 Family dispositions (register)

#### H5 — Status reports

| Field | Value |
|---|---|
| **Source path** | `docs/status_reports/` |
| **Scale** | **18** markdown |
| **Date / baseline** | Refactoring / integration campaign era; headers often undated |
| **Current authority** | **Historical (provenance only)** |
| **Move risk** | **Medium** |
| **Batch owner** | **BATCH-HIST-STATUS** |
| **Disposition** | **Archive** → `docs/ARCHIVE/status-and-fixes/` |
| **Replacement gate (DS-20)** | **Open** after KDOC-042 boundary README (present) |

#### H6 — Fixes

| Field | Value |
|---|---|
| **Source path** | `docs/fixes/` |
| **Scale** | **14** markdown |
| **Date / baseline** | One-off fix campaigns (undated / campaign-era) |
| **Current authority** | **Historical** |
| **Move risk** | **Medium** (some may be linked from older indexes) |
| **Batch owner** | **BATCH-HIST-FIX** |
| **Disposition** | **Archive** (pair with existing `ARCHIVE/fixes/`) |
| **Replacement gate (DS-21)** | **Open** after KDOC-042 |

### 2.2 Where the report bodies live today

| Location | Role |
|---|---|
| **`docs/status_reports/**`** | Status report bodies at original paths (path-stable until Stub Redirect / optional co-locate). Read as Historical. |
| **`docs/fixes/**`** | Fix write-up bodies at original paths. Read as Historical. |
| **[`docs/ARCHIVE/status-reports/`](../status-reports/)** | Already-quarantined status narratives (MCP development status **2025-07-10**, modular server, pin project, mission complete). |
| **[`docs/ARCHIVE/fixes/`](../fixes/)** | Already-quarantined fix analyses (daemon manager attribute, pin index, Arrow IPC). |
| **This directory (`docs/ARCHIVE/status-and-fixes/`)** | **Category index** (this README): single curated map of original context + replacements + merge notes. Future co-located intake lands here when owners `git mv` without breaking referrers. |

**Hard rule:** Do **not** archive maintained CI runbooks (`docs/ci-cd/CI_CD_VALIDATION_GUIDE.md`, runner how-tos), testing process retainers (`TEST_HEALTH_MATRIX.md`), Wave 0 audits, or feature **guides**. Only report-like status/fix families (and their already-archived siblings) are in scope.

### 2.3 Merge layout (owners)

When physically consolidating:

| Source | Suggested ARCHIVE placement | Redirect |
|---|---|---|
| `docs/status_reports/*.md` | `docs/ARCHIVE/status-and-fixes/status/` **or** retain under existing `ARCHIVE/status-reports/` with this index as parent | Directory-level guidance (this README); sparse Stub only for index-linked paths |
| `docs/fixes/*.md` | `docs/ARCHIVE/status-and-fixes/fixes/` **or** existing `ARCHIVE/fixes/` | Same |
| Already under `ARCHIVE/status-reports/` / `ARCHIVE/fixes/` | **Leave in place** (low move risk); link from this index | None required |

Prefer `git mv`, Historical banners, and provenance rows — do not rewrite fix narratives into present-tense runbooks.

### 2.4 Phase order (redirect plan)

Per duplicate/redirect plan **Phase P2.1**: archive `status_reports` + `fixes` after KDOC-042 (done). Implementation COMPLETE bulk is a **separate** category ([`../implementation/README.md`](../implementation/README.md)) with higher move risk (P3.1).

---

## 3. Source inventory (original context)

### 3.1 H5 — `docs/status_reports/` (18)

All members are **Historical**. Original context is the campaign title / topic; dates are often absent in headers.

| Original path | Original context (episode) | Prefer instead (current) |
|---|---|---|
| `docs/status_reports/MCP_REFACTORING_SUMMARY.md` | MCP package restructure from root `mcp/` + `mcp_handlers/` into `ipfs_kit_py/mcp/` | [`MCP_CONTROL_PLANE.md`](../../architecture/MCP_CONTROL_PLANE.md) + packaging `ipfs-kit-mcp` |
| `docs/status_reports/MCP_SERVER_REFACTORING_SUMMARY.md` | MCP server refactoring dual (DS-06) — merge-then-archive with peer above; **neither** is current architecture | Same as above; optional single ARCHIVE merge note |
| `docs/status_reports/REFACTORING_COMPLETE_SUMMARY.md` | Broad refactoring “complete” narrative | [`SYSTEM_OVERVIEW.md`](../../architecture/SYSTEM_OVERVIEW.md), [`COMPATIBILITY_LAYERS.md`](../../architecture/COMPATIBILITY_LAYERS.md) |
| `docs/status_reports/CORE_REFACTORING_SUMMARY.md` | Core package refactoring episode | Runtime + compatibility architecture guides |
| `docs/status_reports/CLUSTER_CRON_REFACTORING_SUMMARY.md` | Cluster cron refactoring episode | [`CLUSTER_COORDINATION.md`](../../architecture/CLUSTER_COORDINATION.md), [`docs/operations/cluster_management.md`](../../operations/cluster_management.md) |
| `docs/status_reports/COMPLETE_INTEGRATION_SUMMARY.md` | Integration completion narrative | Integration hub under `docs/integration/` (owner refresh); architecture maps |
| `docs/status_reports/INTEGRATION_SUMMARY.md` | Shorter integration summary | Same as complete integration — Historical only |
| `docs/status_reports/PRIORITY_0_COMPLETION_SUMMARY.md` | Priority-0 completion campaign | Program plan + live audits; not a verification receipt |
| `docs/status_reports/PRIORITY_1_COMPLETE_SUMMARY.md` | Priority-1 completion campaign | Same |
| `docs/status_reports/ROOT_FOLDER_REFACTORING_SUMMARY.md` | Root folder refactoring episode | Source layout + [`RUNTIME_AND_ENTRYPOINTS.md`](../../architecture/RUNTIME_AND_ENTRYPOINTS.md) |
| `docs/status_reports/DEV_FOLDER_REORGANIZATION_SUMMARY.md` | Dev folder reorganization episode | Development process docs under `docs/development/` |
| `docs/status_reports/DOCUMENTATION_SUMMARY.md` | Documentation summary snapshot | [`docs/guides/DOCUMENTATION_GUIDE.md`](../../guides/DOCUMENTATION_GUIDE.md); Wave 0 `docs/audits/*` |
| `docs/status_reports/BACKEND_REVIEW_QUICK_REFERENCE.md` | Backend review quick reference (campaign) | [`STORAGE_BACKEND_SYSTEM.md`](../../architecture/STORAGE_BACKEND_SYSTEM.md), [`docs/reference/storage_backends.md`](../../reference/storage_backends.md) |
| `docs/status_reports/README_BACKEND_REVIEW.md` | Backend review README wrapper | Same storage architecture / reference |
| `docs/status_reports/GITHUB_CLI_CACHING.md` | GitHub CLI caching notes | Ops/CI truth: workflows + verified runbooks under `docs/ci-cd/` (retain split) |
| `docs/status_reports/GITHUB_CLI_CACHING_IMPLEMENTATION_SUMMARY.md` | Implementation summary for CLI caching | Same — Historical episode only |
| `docs/status_reports/GITHUB_CLI_CACHING_LIBP2P.md` | libp2p-related CLI caching notes | [`NETWORK_TRANSPORTS.md`](../../architecture/NETWORK_TRANSPORTS.md) + integration docs |
| `docs/status_reports/GITHUB_CLI_CACHING_LIBP2P_IMPLEMENTATION.md` | libp2p caching implementation write-up | Same |

**DS-06 note:** `MCP_REFACTORING_SUMMARY.md` and `MCP_SERVER_REFACTORING_SUMMARY.md` are dual historical narratives. Survivor for provenance may be either merged note under this category; **canonical runtime authority is never either file** — use packaging + MCP control plane.

### 3.2 H6 — `docs/fixes/` (14)

Fix notes are **not** product policy. Prefer CHANGELOG, issues, and verified guides when a subsystem still needs operator docs.

| Original path | Original context (episode) | Prefer instead (current) |
|---|---|---|
| `docs/fixes/BACKEND_INTEGRATION_FIX.md` | Service configuration / backend module integration fix (dashboard config transform) | Backend install paths in source; [`STORAGE_BACKEND_SYSTEM.md`](../../architecture/STORAGE_BACKEND_SYSTEM.md); MCP dashboard only via control-plane + packaging |
| `docs/fixes/BACKEND_MODAL_FIX_SUMMARY.md` | Backend modal UI fix summary | Feature/dashboard docs if maintained; else issues/CHANGELOG |
| `docs/fixes/CONFIG_FORM_FIELDS_FIX.md`, `docs/fixes/CONFIG_FORM_FIX_SUMMARY.md`, `docs/fixes/CONFIGURATION_FIX_DOCUMENTATION.md`, `docs/fixes/CONFIGURATION_FIX_README.md`, `docs/fixes/DASHBOARD_CONFIG_FIX.md` | Dashboard / config form fix cluster | [`CONFIGURATION_STATE_AND_TRUST.md`](../../architecture/CONFIGURATION_STATE_AND_TRUST.md); do not treat form fix notes as security policy |
| `docs/fixes/MCP_DASHBOARD_FIX_SUMMARY.md` | MCP dashboard fix summary | Packaging + [`MCP_CONTROL_PLANE.md`](../../architecture/MCP_CONTROL_PLANE.md) |
| `docs/fixes/PEER_MANAGER_FIX_SUMMARY.md` | Peer manager fix summary | [`NETWORK_TRANSPORTS.md`](../../architecture/NETWORK_TRANSPORTS.md), cluster ops |
| `docs/fixes/AUTOFIX_WORKFLOW_FIX_SUMMARY.md` | Autofix workflow fix summary | `.github/workflows/*` + CI validation guide (runbook retainers) |
| `docs/fixes/GO_BUILD_TOOLS_FIX.md` | Go build tools fix note | Development / containerization docs as applicable; not live build policy from undated fix alone |
| `docs/fixes/LOTUS_DEPS_DOCKER_FIX.md` | Lotus deps Docker fix | Deployment/container docs after verify |
| `docs/fixes/SYNTAX_ERROR_FIX_STATUS.md` | Syntax error fix status snapshot | Source tree / CI green as live signal |
| `docs/fixes/TEST_COLLECTION_FIX.md` | Test collection fix note | [`docs/development/testing_guide.md`](../../development/testing_guide.md), `pytest.ini` |

### 3.3 Already quarantined under ARCHIVE (indexed for one path)

#### Status reports (`docs/ARCHIVE/status-reports/`)

| Path | Original context | Prefer instead |
|---|---|---|
| [`../status-reports/MCP_DEVELOPMENT_STATUS.md`](../status-reports/MCP_DEVELOPMENT_STATUS.md) | Dated **2025-07-10**; older nav once treated as primary MCP status | Packaging + [`MCP_CONTROL_PLANE.md`](../../architecture/MCP_CONTROL_PLANE.md) |
| [`../status-reports/MODULAR_SERVER_STATUS.md`](../status-reports/MODULAR_SERVER_STATUS.md) | Modular server point-in-time status | Runtime entrypoints + MCP control plane |
| [`../status-reports/PIN_PROJECT_SUMMARY.md`](../status-reports/PIN_PROJECT_SUMMARY.md) | Pin project summary narrative | [`docs/features/pin-management/`](../../features/pin-management/) |
| [`../status-reports/MISSION_ACCOMPLISHED.md`](../status-reports/MISSION_ACCOMPLISHED.md) | Mission-complete campaign rhetoric | Never as acceptance evidence |

#### Fixes (`docs/ARCHIVE/fixes/`)

| Path | Original context | Prefer instead |
|---|---|---|
| [`../fixes/DAEMON_MANAGER_ATTRIBUTE_FIX.md`](../fixes/DAEMON_MANAGER_ATTRIBUTE_FIX.md) | Daemon manager attribute fix analysis | [`RUNTIME_AND_ENTRYPOINTS.md`](../../architecture/RUNTIME_AND_ENTRYPOINTS.md) + source |
| [`../fixes/PIN_INDEX_ISSUE_ANALYSIS.md`](../fixes/PIN_INDEX_ISSUE_ANALYSIS.md) | Pin index issue analysis | Pin-management feature guides + source |
| [`../fixes/APACHE_ARROW_IPC_INTEGRATION_FIX.md`](../fixes/APACHE_ARROW_IPC_INTEGRATION_FIX.md) | Arrow IPC integration fix | Storage / Arrow-related architecture and source |

---

## 4. Where to go instead (current replacements)

| Topic | Prefer (maintained / current) | Do **not** use status/fix reports as |
|---|---|---|
| **MCP / control plane** | Packaging `ipfs-kit-mcp` + [`MCP_CONTROL_PLANE.md`](../../architecture/MCP_CONTROL_PLANE.md) | “Primary” MCP development status or refactor summaries |
| **System architecture** | [`SYSTEM_OVERVIEW.md`](../../architecture/SYSTEM_OVERVIEW.md), [`RUNTIME_AND_ENTRYPOINTS.md`](../../architecture/RUNTIME_AND_ENTRYPOINTS.md), [`SOURCE_OF_TRUTH_MAP.md`](../../architecture/SOURCE_OF_TRUTH_MAP.md) | Refactoring COMPLETE banners |
| **Storage backends** | [`STORAGE_BACKEND_SYSTEM.md`](../../architecture/STORAGE_BACKEND_SYSTEM.md), [`docs/reference/storage_backends.md`](../../reference/storage_backends.md) | Backend review quick references as inventory truth |
| **Cluster / network** | [`CLUSTER_COORDINATION.md`](../../architecture/CLUSTER_COORDINATION.md), [`NETWORK_TRANSPORTS.md`](../../architecture/NETWORK_TRANSPORTS.md), `docs/operations/` | Cluster cron / peer fix notes as topology policy |
| **Configuration / trust** | [`CONFIGURATION_STATE_AND_TRUST.md`](../../architecture/CONFIGURATION_STATE_AND_TRUST.md) | Config form fix clusters as security policy |
| **Pins** | [`docs/features/pin-management/`](../../features/pin-management/) | Pin project ARCHIVE summaries as user guides |
| **Testing** | [`testing_guide.md`](../../development/testing_guide.md), CI, `pytest.ini` | Test collection fix status as suite health |
| **CI / runners** | Verified `docs/ci-cd/*` **runbooks** + `.github/workflows/*` | Workflow fix summaries as the only runner docs (reports archive; runbooks retain — H12 split) |
| **Product defects** | CHANGELOG, issue tracker, focused regression tests | Fix markdown as permanent operator procedure |
| **Documentation program** | Protected plan + [`docs/audits/*`](../../audits/) | Documentation/priority completion summaries as live verification |

---

## 5. What must never enter this category as “current”

| Keep out / do not reclassify as archive bulk | Why |
|---|---|
| CI **runbooks** (`CI_CD_VALIDATION_GUIDE.md`, `RUNNER_*`, setup/start guides) | H12 **Split** — retain after verify; only **report** subset archives |
| Testing **process** retainers (`TEST_HEALTH_MATRIX.md`, architecture compatibility reviews feeding testing guide) | H9 **Split** |
| Wave 0 audits and register/plan files under `docs/audits/` | Program evidence |
| Protected program files | Program-control |
| Maintained feature guides and architecture KDOC-010..019 outputs | Canonical / candidate-canonical |
| Generated API and external snapshots | KDOC-043/044/046 |
| Root competing indexes | Navigation — KDOC-060 |

---

## 6. Link and move safety

| Constraint | Application here |
|---|---|
| **No maintained guide archived** | Only H5/H6 report bulk + already-quarantined status/fix siblings; CI runbooks and feature guides stay put |
| **No knowingly broken inbound canonical links** | Source trees `docs/status_reports/**` and `docs/fixes/**` remain until Stub/Nav-unlink; already-ARCHIVEd files stay at current ARCHIVE paths |
| **Original context + replacements** | §3 tables list every member with episode context and replacement (or issues/CHANGELOG) |
| **Medium move risk** | Safer batch than implementation COMPLETE bulk; still use directory-level guidance and sparse stubs for index-linked paths (~8 referrers for `status_reports/`) |
| **F-017** | Never deep-link ARCHIVE/status as “implementation status” from current pages |

---

## 7. Agent and human checklist

Before citing anything in this family:

- [ ] Am I seeking **what was attempted/fixed in a past campaign**, not how to operate today?
- [ ] For MCP/runtime claims, have I checked **packaging** and [`MCP_CONTROL_PLANE.md`](../../architecture/MCP_CONTROL_PLANE.md)?
- [ ] For defects, am I using **issues/CHANGELOG/tests** rather than fix markdown alone?
- [ ] Am I avoiding ARCHIVE/status language that still says “primary” or “current”?
- [ ] Am I about to archive a **CI runbook** or **feature guide**? If yes — **stop** (wrong family / split retain).

---

## 8. Related program artifacts

| Artifact | Role |
|---|---|
| [docs/ARCHIVE/README.md](../README.md) | Archive boundary and reading rules |
| [docs/ARCHIVE/implementation/README.md](../implementation/README.md) | Parallel curated intake for implementation COMPLETE bulk (H1) |
| [docs/ARCHIVE/status-reports/](../status-reports/) | Already-quarantined status files |
| [docs/ARCHIVE/fixes/](../fixes/) | Already-quarantined fix analyses |
| [docs/audits/HISTORICAL_DOCUMENT_REGISTER.md](../../audits/HISTORICAL_DOCUMENT_REGISTER.md) | H5/H6/H11 dispositions |
| [docs/audits/DUPLICATE_AND_REDIRECT_PLAN.md](../../audits/DUPLICATE_AND_REDIRECT_PLAN.md) | DS-06, DS-20/21, Phase P2.1 |
| [docs/guides/DOCUMENTATION_GUIDE.md](../../guides/DOCUMENTATION_GUIDE.md) | Authority classes |
| KDOC-060 (planned) | Drop status/fix historical targets from exclusive navigation |

---

**Bottom line:** Status reports and fix notes are **historical provenance**. This category index curates H5, H6, and already-quarantined ARCHIVE siblings with original context and current replacement links. For MCP, architecture, storage, cluster, testing, and CI of the tree you are on, use [§4](#4-where-to-go-instead-current-replacements) — not completion or fix banners.
