# Documentation index (structured catalog)

| Field | Value |
|---|---|
| **Document class** | Canonical (navigation catalog) |
| **Authority class** | **Structured catalog only** — not a landing page |
| **Status** | active |
| **Owner / task** | KDOC-060 |
| **Goal id** | KDOC-G080 / KDOC-G050 |
| **Last verified** | 2026-08-04 |
| **Scope** | Lookup tables by topic and material class |
| **Non-goals** | Start-here authority; exhaustive listing of every historical file |

> **Redirect / role notice.**  
> **Start here:** [`docs/index.md`](index.md)  
> **Full map:** [`docs/README.md`](README.md)  
> **Architecture order:** [`docs/architecture/README.md`](architecture/README.md)  
> This file is a **catalog**. It deliberately does **not** compete as a second home page. Prefer Current targets; Historical and Generated sections are labeled and are not how-to authority.

---

## Authority and labels

| Label | May recommend as current guidance? |
|---|---|
| **Current** | Yes |
| **Generated** | No (inventory/reference only) |
| **Historical** | No |
| **External** | Only as upstream ownership/contract |
| **Proposed** | No |

Lifecycle: [`guides/DOCUMENTATION_GUIDE.md`](guides/DOCUMENTATION_GUIDE.md).

---

## A. Navigation surfaces

| File | Role | Class |
|---|---|---|
| [index.md](index.md) | Sole concise landing | Current (nav) |
| [README.md](README.md) | Complete repository map | Current (nav) |
| **DOCUMENTATION_INDEX.md** (this file) | Topic catalog | Current (nav catalog) |
| [architecture/README.md](architecture/README.md) | Architecture / ADR hub | Current (nav) |
| [QUICK_REFERENCE.md](QUICK_REFERENCE.md) | Cheatsheet | Current |

---

## B. Getting started (Current)

| Document | Description |
|---|---|
| [installation_guide.md](installation_guide.md) | Install, prerequisites, verification |
| [QUICK_REFERENCE.md](QUICK_REFERENCE.md) | Common operations and commands |
| [INSTALLER_DOCUMENTATION.md](INSTALLER_DOCUMENTATION.md) | Optional dependency / installer entry points |
| [guides/VALIDATION_QUICK_START.md](guides/VALIDATION_QUICK_START.md) | Sanity-check a setup |
| [api/high_level_api.md](api/high_level_api.md) | Simplified Python API |
| [api/cli_reference.md](api/cli_reference.md) | CLI command reference |
| [integration/INTEGRATION_QUICK_START.md](integration/INTEGRATION_QUICK_START.md) | Integration bootstrap |

---

## C. API and interfaces (Current)

| Document | Description |
|---|---|
| [api/api_reference.md](api/api_reference.md) | Authored API reference |
| [api/high_level_api.md](api/high_level_api.md) | High-level wrappers and patterns |
| [api/cli_reference.md](api/cli_reference.md) | CLI surface |
| [api/mcp_reference.md](api/mcp_reference.md) | MCP tools and server surface |
| [api/core_concepts.md](api/core_concepts.md) | Core concepts companion |

**Generated** companion inventories (not conceptual authority): [api_generated/README.md](api_generated/README.md).

---

## D. Architecture and decisions (Current)

| Document | Description |
|---|---|
| [architecture/README.md](architecture/README.md) | Reading order hub |
| [architecture/SYSTEM_OVERVIEW.md](architecture/SYSTEM_OVERVIEW.md) | System context |
| [architecture/RUNTIME_AND_ENTRYPOINTS.md](architecture/RUNTIME_AND_ENTRYPOINTS.md) | Processes and entry points |
| [architecture/COMPATIBILITY_LAYERS.md](architecture/COMPATIBILITY_LAYERS.md) | Shims and legacy layers |
| [architecture/STORAGE_BACKEND_SYSTEM.md](architecture/STORAGE_BACKEND_SYSTEM.md) | Backend architecture |
| [architecture/CONTENT_METADATA_VFS.md](architecture/CONTENT_METADATA_VFS.md) | Content / metadata / VFS plane |
| [architecture/CLUSTER_COORDINATION.md](architecture/CLUSTER_COORDINATION.md) | Cluster architecture |
| [architecture/NETWORK_TRANSPORTS.md](architecture/NETWORK_TRANSPORTS.md) | Network transports |
| [architecture/MCP_CONTROL_PLANE.md](architecture/MCP_CONTROL_PLANE.md) | MCP control plane |
| [architecture/ASYNC_AND_OPTIONAL_DEPENDENCIES.md](architecture/ASYNC_AND_OPTIONAL_DEPENDENCIES.md) | Async and optional deps |
| [architecture/CONFIGURATION_STATE_AND_TRUST.md](architecture/CONFIGURATION_STATE_AND_TRUST.md) | Config, state, trust |
| [architecture/GLOSSARY.md](architecture/GLOSSARY.md) | Shared vocabulary |
| [architecture/SOURCE_OF_TRUTH_MAP.md](architecture/SOURCE_OF_TRUTH_MAP.md) | Evidence and open authorities |
| [architecture/AGENT_SYSTEM_MAP.md](architecture/AGENT_SYSTEM_MAP.md) | Agent-oriented system map |
| [architecture/decisions/README.md](architecture/decisions/README.md) | ADR index and process |

Legacy architecture narratives under `docs/architecture/*AUDIT*` or older titles (e.g. `REFACTORED_ARCHITECTURE_README.md`) are **not** the primary path; use the hub above.

---

## E. Storage, VFS, and data plane (Current)

| Document | Description |
|---|---|
| [reference/storage_backends.md](reference/storage_backends.md) | Multi-backend usage |
| [VFS_CONTRACT_SPEC.md](VFS_CONTRACT_SPEC.md) | VFS request/response/sync contracts |
| [filesystem_journal.md](filesystem_journal.md) | Filesystem journal |
| [reference/tiered_cache.md](reference/tiered_cache.md) | Tiered cache |
| [reference/write_ahead_log.md](reference/write_ahead_log.md) | Write-ahead log |
| [reference/metadata_index.md](reference/metadata_index.md) | Metadata index notes |
| [architecture/CONTENT_METADATA_VFS.md](architecture/CONTENT_METADATA_VFS.md) | Architecture for content/VFS |
| [architecture/STORAGE_BACKEND_SYSTEM.md](architecture/STORAGE_BACKEND_SYSTEM.md) | Backend system architecture |

---

## F. Operations and deployment (Current)

| Document | Description |
|---|---|
| [operations/cluster_management.md](operations/cluster_management.md) | Cluster management |
| [operations/cluster_state.md](operations/cluster_state.md) | Cluster state |
| [operations/cluster_monitoring.md](operations/cluster_monitoring.md) | Monitoring |
| [operations/cluster_authentication.md](operations/cluster_authentication.md) | Cluster authentication |
| [operations/cluster_dynamic_roles.md](operations/cluster_dynamic_roles.md) | Dynamic roles |
| [operations/observability.md](operations/observability.md) | Observability |
| [operations/performance_metrics.md](operations/performance_metrics.md) | Performance metrics |
| [operations/resource_management.md](operations/resource_management.md) | Resource management |
| [guides/CLUSTER_DEPLOYMENT_GUIDE.md](guides/CLUSTER_DEPLOYMENT_GUIDE.md) | Cluster deployment |
| [deployment/docker/DOCKER_QUICK_START.md](deployment/docker/DOCKER_QUICK_START.md) | Docker quick start |
| [containerization.md](containerization.md) | Containerization overview |
| [credential_management.md](credential_management.md) | Credentials |
| [guides/SECURE_CREDENTIALS_GUIDE.md](guides/SECURE_CREDENTIALS_GUIDE.md) | Secure credentials practices |

Additional files under `docs/deployment/` and `docs/ci-cd/` may be **Historical** completion reports — do not treat every path there as Current runbook.

---

## G. Integrations and network (Current)

| Document | Description |
|---|---|
| [integration/INTEGRATION_OVERVIEW.md](integration/INTEGRATION_OVERVIEW.md) | Integration overview |
| [integration/INTEGRATION_QUICK_START.md](integration/INTEGRATION_QUICK_START.md) | Quick start |
| [iroh/README.md](iroh/README.md) | Iroh integration |
| [architecture/NETWORK_TRANSPORTS.md](architecture/NETWORK_TRANSPORTS.md) | Network architecture |
| [reference/streaming_guide.md](reference/streaming_guide.md) | Streaming guide |

---

## H. Features (Current-preferring)

| Document | Description | Class note |
|---|---|---|
| [features/pin-management/PIN_MANAGEMENT_GUIDE.md](features/pin-management/PIN_MANAGEMENT_GUIDE.md) | Pin management | Current guide |
| [features/pin-management/PIN_QUICK_START.md](features/pin-management/PIN_QUICK_START.md) | Pin quick start | Current guide |
| [features/auto-healing/AUTO_HEALING.md](features/auto-healing/AUTO_HEALING.md) | Auto-healing overview | Current guide |
| [features/auto-healing/AUTO_HEALING_QUICKSTART.md](features/auto-healing/AUTO_HEALING_QUICKSTART.md) | Auto-healing quick start | Current guide |

Feature trees also contain implementation summaries; prefer guides without COMPLETE/production-ready campaign banners. Those summaries are **Historical**.

---

## I. Development, testing, and contribution (Current)

| Document | Description |
|---|---|
| [development/testing_guide.md](development/testing_guide.md) | Testing guide |
| [testing/TEST_HEALTH_MATRIX.md](testing/TEST_HEALTH_MATRIX.md) | Test health matrix |
| [development/async_architecture.md](development/async_architecture.md) | Async architecture notes |
| [development/DOCUMENTATION_IMPACT_MAP.md](development/DOCUMENTATION_IMPACT_MAP.md) | Doc impact by change area |
| [development/DOCUMENTATION_VALIDATION.md](development/DOCUMENTATION_VALIDATION.md) | Validation runbook |
| [workflows/documentation-maintenance.md](workflows/documentation-maintenance.md) | Maintenance workflow |
| [guides/DOCUMENTATION_GUIDE.md](guides/DOCUMENTATION_GUIDE.md) | Lifecycle and claim standard |
| [guides/DEBUGGING_BY_SUBSYSTEM.md](guides/DEBUGGING_BY_SUBSYSTEM.md) | Subsystem debugging |
| [guides/CLI_POLICY_USAGE_GUIDE.md](guides/CLI_POLICY_USAGE_GUIDE.md) | CLI policy usage |
| [pypi_release.md](pypi_release.md) | PyPI release notes |

Root and `docs/testing/` **coverage campaign** files (`100_PERCENT_*`, `TEST_COVERAGE_*`, phase coverage reports) are **Historical** — live coverage comes from CI/pytest, not markdown banners.

---

## J. Program evidence and audits (Current audit class)

| Document | Description |
|---|---|
| [audits/DOCUMENTATION_INVENTORY.md](audits/DOCUMENTATION_INVENTORY.md) | Corpus inventory |
| [audits/PUBLIC_SURFACE_MATRIX.md](audits/PUBLIC_SURFACE_MATRIX.md) | Public surface matrix |
| [audits/FRESHNESS_AND_CHANGE_AUDIT.md](audits/FRESHNESS_AND_CHANGE_AUDIT.md) | Freshness audit |
| [audits/HISTORICAL_DOCUMENT_REGISTER.md](audits/HISTORICAL_DOCUMENT_REGISTER.md) | Historical register |
| [audits/DUPLICATE_AND_REDIRECT_PLAN.md](audits/DUPLICATE_AND_REDIRECT_PLAN.md) | Duplicate / redirect plan |
| [audits/GENERATED_DOCUMENTATION_CONTRACT.md](audits/GENERATED_DOCUMENTATION_CONTRACT.md) | Generated-doc contract |

---

## K. Generated material

| Document | Description | Class |
|---|---|---|
| [api_generated/README.md](api_generated/README.md) | Generated tree index | **Generated** |
| [api_generated/module_structure.md](api_generated/module_structure.md) | Module inventory | **Generated** |
| [api_generated/dependencies.md](api_generated/dependencies.md) | Dependency / script inventory | **Generated** |
| [api_generated/examples_index.md](api_generated/examples_index.md) | Examples index | **Generated** |
| [api_generated/AGENT_GUIDE.md](api_generated/AGENT_GUIDE.md) | Agent compact guide | **Generated** |
| [api_generated/doc_status.md](api_generated/doc_status.md) | Generator status snapshot | **Generated** |

Do not hand-edit generated bodies; regenerate per the contract.

---

## L. Historical material

| Document / tree | Description | Class |
|---|---|---|
| [ARCHIVE/README.md](ARCHIVE/README.md) | Archive boundary and reading rules | **Historical** |
| [ARCHIVE/implementation/](ARCHIVE/implementation/) | Archived implementation reports | **Historical** |
| [ARCHIVE/status-and-fixes/](ARCHIVE/status-and-fixes/) | Archived status/fix material | **Historical** |
| [ARCHIVE/status-reports/](ARCHIVE/status-reports/) | Archived status reports (e.g. old MCP status) | **Historical** |
| [migration/MCP_SERVER_MIGRATION_GUIDE.md](migration/MCP_SERVER_MIGRATION_GUIDE.md) | MCP migration episode | **Historical** |
| `docs/implementation/**` | Implementation COMPLETE/summary narratives | **Historical** |
| `docs/fixes/**`, `docs/status_reports/**`, `docs/test_reports/**` | Fix/status/test dumps | **Historical** |
| Root `*COMPLETE*`, coverage roadmaps, phase reports under `docs/` | Campaign dumps | **Historical** |

**Catalog rule:** Historical paths are listed only for discovery. They are **never** start-here or production-status authority.

---

## M. External material

| Document | Description | Class |
|---|---|---|
| [reference/EXTERNAL_DOCUMENTATION_SOURCES.md](reference/EXTERNAL_DOCUMENTATION_SOURCES.md) | Ownership of gitlinks and embedded projects | **External** boundary record |

External trees themselves (gitlinks may be empty; embedded `docs/py-ipld-*`, SDK doc trees, etc.) are **External** content — see the ownership record. Not counted as authored kit documentation coverage.

---

## N. Proposed material

| Source | How to treat |
|---|---|
| ADR files with status **Proposed** under [architecture/decisions/](architecture/decisions/README.md) | Not production policy |
| Open `U-*` / `C-*` items in [SOURCE_OF_TRUTH_MAP.md](architecture/SOURCE_OF_TRUTH_MAP.md) | Unresolved; do not invent resolution |
| Planning docs such as [ROADMAP_FEATURES.md](ROADMAP_FEATURES.md) | **Proposed** / planning unless re-verified |

---

## O. Finding paths quickly

### By role

| Role | Jump to |
|---|---|
| New user | §B · [index.md](index.md) |
| Developer | §C, §E · [README.md §2.2](README.md#22-application-developer) |
| Operator | §F · [README.md §2.3](README.md#23-operator--sre) |
| Agent | [architecture/AGENT_SYSTEM_MAP.md](architecture/AGENT_SYSTEM_MAP.md) · §K |
| Doc maintainer | §I, §J · [guides/DOCUMENTATION_GUIDE.md](guides/DOCUMENTATION_GUIDE.md) |

### By task

Use the task table in [README.md §3](README.md#3-paths-by-task) or the short table in [index.md](index.md).

### By system

Use [architecture/README.md](architecture/README.md).

---

## P. Contributing to documentation

1. Classify the document (**Current** / **Generated** / **Historical** / **External** / **Proposed**).  
2. Place it under the appropriate directory (§5 of [README.md](README.md)).  
3. Do **not** edit protected program-control files (`documentation_plan.md`, objectives, todo board).  
4. Do **not** rewrite navigation surfaces except via exclusive navigation ownership (this task family).  
5. Update the **owning** content document; navigation owners refresh the catalog when Current targets change.  
6. Follow [guides/DOCUMENTATION_GUIDE.md](guides/DOCUMENTATION_GUIDE.md) for evidence and headers.

---

**Catalog status:** Structured for exclusive navigation (KDOC-060). Exhaustive enumeration of every historical file is intentionally deferred to [HISTORICAL_DOCUMENT_REGISTER.md](audits/HISTORICAL_DOCUMENT_REGISTER.md) and directory listings.
