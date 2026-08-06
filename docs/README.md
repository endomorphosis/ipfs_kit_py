# IPFS Kit documentation — complete repository map

| Field | Value |
|---|---|
| **Document class** | Canonical (navigation map) |
| **Authority class** | **Complete repository map** for `docs/` — **not** the concise landing |
| **Status** | active |
| **Owner / task** | KDOC-060 |
| **Goal id** | KDOC-G080 / KDOC-G050 |
| **Last verified** | 2026-08-04 |
| **Scope** | Full maintained map of current, generated, historical, external, and proposed surfaces |
| **Non-goals** | Acting as a second “start here”; inventing status from COMPLETE reports |

> **Where to start.**  
> First-time readers: open **[`docs/index.md`](index.md)** (sole concise landing).  
> This file is the **full map**. Topic catalog: [`DOCUMENTATION_INDEX.md`](DOCUMENTATION_INDEX.md).  
> Architecture reading order: [`architecture/README.md`](architecture/README.md).

---

## 1. Authority model

### 1.1 Navigation surfaces (exclusive roles)

| Surface | Role | Competes as landing? |
|---|---|---|
| [`index.md`](index.md) | Concise start-here | **Yes — only this one** |
| **This file (`README.md`)** | Complete repository map | No |
| [`DOCUMENTATION_INDEX.md`](DOCUMENTATION_INDEX.md) | Structured catalog / lookup | No |
| [`architecture/README.md`](architecture/README.md) | Architecture & ADR reading order | No |
| [`QUICK_REFERENCE.md`](QUICK_REFERENCE.md) | Cheatsheet | No |

### 1.2 Material class labels

| Label | Meaning | Recommend as current how-to? |
|---|---|---|
| **Current** | Maintained authored guidance | Yes |
| **Generated** | Tool-produced inventory | Reference only |
| **Historical** | Provenance / campaign records | No |
| **External** | Upstream gitlinks / vendored trees | Only as upstream contract |
| **Proposed** | Not yet accepted or not yet in behavior | No |

Contract: [`guides/DOCUMENTATION_GUIDE.md`](guides/DOCUMENTATION_GUIDE.md).

### 1.3 Claim ranking (short)

When documents disagree, prefer: executable code & tests → packaging/`pyproject.toml` → public contracts → accepted ADRs → **Current** guides → history/ARCHIVE last.

---

## 2. Paths by role

### 2.1 New user

| Step | Document | Class |
|---|---|---|
| 1 | [installation_guide.md](installation_guide.md) | Current |
| 2 | [QUICK_REFERENCE.md](QUICK_REFERENCE.md) | Current |
| 3 | [api/high_level_api.md](api/high_level_api.md) or [api/cli_reference.md](api/cli_reference.md) | Current |
| 4 | [guides/VALIDATION_QUICK_START.md](guides/VALIDATION_QUICK_START.md) | Current |
| Optional | [INSTALLER_DOCUMENTATION.md](INSTALLER_DOCUMENTATION.md) | Current |

### 2.2 Application developer

| Area | Document | Class |
|---|---|---|
| API surface | [api/api_reference.md](api/api_reference.md), [api/high_level_api.md](api/high_level_api.md), [api/core_concepts.md](api/core_concepts.md) | Current |
| CLI | [api/cli_reference.md](api/cli_reference.md), [guides/CLI_POLICY_USAGE_GUIDE.md](guides/CLI_POLICY_USAGE_GUIDE.md) | Current |
| MCP | [api/mcp_reference.md](api/mcp_reference.md), [architecture/MCP_CONTROL_PLANE.md](architecture/MCP_CONTROL_PLANE.md) | Current |
| Storage | [reference/storage_backends.md](reference/storage_backends.md), [architecture/STORAGE_BACKEND_SYSTEM.md](architecture/STORAGE_BACKEND_SYSTEM.md) | Current |
| VFS / content | [VFS_CONTRACT_SPEC.md](VFS_CONTRACT_SPEC.md), [filesystem_journal.md](filesystem_journal.md), [architecture/CONTENT_METADATA_VFS.md](architecture/CONTENT_METADATA_VFS.md) | Current |
| Caching / WAL | [reference/tiered_cache.md](reference/tiered_cache.md), [reference/write_ahead_log.md](reference/write_ahead_log.md) | Current |
| Streaming | [reference/streaming_guide.md](reference/streaming_guide.md) | Current |
| Credentials | [credential_management.md](credential_management.md), [guides/SECURE_CREDENTIALS_GUIDE.md](guides/SECURE_CREDENTIALS_GUIDE.md) | Current |
| Integrations | [integration/INTEGRATION_OVERVIEW.md](integration/INTEGRATION_OVERVIEW.md), [integration/INTEGRATION_QUICK_START.md](integration/INTEGRATION_QUICK_START.md) | Current |
| Features (examples) | [features/pin-management/PIN_MANAGEMENT_GUIDE.md](features/pin-management/PIN_MANAGEMENT_GUIDE.md), [features/auto-healing/AUTO_HEALING.md](features/auto-healing/AUTO_HEALING.md) | Current (feature guides; verify against packaging) |
| Generated symbols | [api_generated/module_structure.md](api_generated/module_structure.md), [api_generated/examples_index.md](api_generated/examples_index.md) | **Generated** |

### 2.3 Operator / SRE

| Area | Document | Class |
|---|---|---|
| Cluster ops | [operations/cluster_management.md](operations/cluster_management.md), [operations/cluster_state.md](operations/cluster_state.md), [operations/cluster_monitoring.md](operations/cluster_monitoring.md) | Current |
| Auth / roles | [operations/cluster_authentication.md](operations/cluster_authentication.md), [operations/cluster_dynamic_roles.md](operations/cluster_dynamic_roles.md) | Current |
| Observability | [operations/observability.md](operations/observability.md), [operations/performance_metrics.md](operations/performance_metrics.md) | Current |
| Deploy | [guides/CLUSTER_DEPLOYMENT_GUIDE.md](guides/CLUSTER_DEPLOYMENT_GUIDE.md), [deployment/docker/DOCKER_QUICK_START.md](deployment/docker/DOCKER_QUICK_START.md), [containerization.md](containerization.md) | Current |
| Architecture (ops view) | [architecture/CLUSTER_COORDINATION.md](architecture/CLUSTER_COORDINATION.md), [architecture/CONFIGURATION_STATE_AND_TRUST.md](architecture/CONFIGURATION_STATE_AND_TRUST.md) | Current |
| Runtime selection | [architecture/RUNTIME_AND_ENTRYPOINTS.md](architecture/RUNTIME_AND_ENTRYPOINTS.md) | Current |

### 2.4 Implementation / review agent

| Area | Document | Class |
|---|---|---|
| System map | [architecture/AGENT_SYSTEM_MAP.md](architecture/AGENT_SYSTEM_MAP.md) | Current |
| Change impact | [development/DOCUMENTATION_IMPACT_MAP.md](development/DOCUMENTATION_IMPACT_MAP.md) | Current |
| Diagnostics | [guides/DEBUGGING_BY_SUBSYSTEM.md](guides/DEBUGGING_BY_SUBSYSTEM.md) | Current |
| Entry points | [architecture/RUNTIME_AND_ENTRYPOINTS.md](architecture/RUNTIME_AND_ENTRYPOINTS.md), [api_generated/AGENT_GUIDE.md](api_generated/AGENT_GUIDE.md) | Current / **Generated** |
| Open authorities | [architecture/SOURCE_OF_TRUTH_MAP.md](architecture/SOURCE_OF_TRUTH_MAP.md), [audits/PUBLIC_SURFACE_MATRIX.md](audits/PUBLIC_SURFACE_MATRIX.md) | Current (evidence) |
| ADRs | [architecture/decisions/README.md](architecture/decisions/README.md) | Current records (**Proposed** decisions stay labeled) |

### 2.5 Documentation maintainer

| Area | Document | Class |
|---|---|---|
| Lifecycle / claims | [guides/DOCUMENTATION_GUIDE.md](guides/DOCUMENTATION_GUIDE.md) | Current |
| Validation | [development/DOCUMENTATION_VALIDATION.md](development/DOCUMENTATION_VALIDATION.md) | Current |
| Maintenance cadence | [workflows/documentation-maintenance.md](workflows/documentation-maintenance.md) | Current |
| Generated contract | [audits/GENERATED_DOCUMENTATION_CONTRACT.md](audits/GENERATED_DOCUMENTATION_CONTRACT.md) | Current (contract) |
| Inventory / freshness | [audits/DOCUMENTATION_INVENTORY.md](audits/DOCUMENTATION_INVENTORY.md), [audits/FRESHNESS_AND_CHANGE_AUDIT.md](audits/FRESHNESS_AND_CHANGE_AUDIT.md) | Current (audits) |
| History / duplicates | [audits/HISTORICAL_DOCUMENT_REGISTER.md](audits/HISTORICAL_DOCUMENT_REGISTER.md), [audits/DUPLICATE_AND_REDIRECT_PLAN.md](audits/DUPLICATE_AND_REDIRECT_PLAN.md) | Current (registers) |
| Archive boundary | [ARCHIVE/README.md](ARCHIVE/README.md) | **Historical** boundary page |
| External boundary | [reference/EXTERNAL_DOCUMENTATION_SOURCES.md](reference/EXTERNAL_DOCUMENTATION_SOURCES.md) | **External** ownership |

---

## 3. Paths by task

| Task | Primary | Supporting | Class notes |
|---|---|---|---|
| Install package | [installation_guide.md](installation_guide.md) | [INSTALLER_DOCUMENTATION.md](INSTALLER_DOCUMENTATION.md), [pypi_release.md](pypi_release.md) | Current |
| Day-one operations | [QUICK_REFERENCE.md](QUICK_REFERENCE.md) | [guides/VALIDATION_QUICK_START.md](guides/VALIDATION_QUICK_START.md) | Current |
| Use Python API | [api/high_level_api.md](api/high_level_api.md) | [api/api_reference.md](api/api_reference.md), [api/core_concepts.md](api/core_concepts.md) | Current |
| Use CLI | [api/cli_reference.md](api/cli_reference.md) | [guides/CLI_POLICY_USAGE_GUIDE.md](guides/CLI_POLICY_USAGE_GUIDE.md) | Current |
| MCP tools / server | [api/mcp_reference.md](api/mcp_reference.md) | [architecture/MCP_CONTROL_PLANE.md](architecture/MCP_CONTROL_PLANE.md), ADR [0003](architecture/decisions/0003-mcp-runtime-authority.md) | Current; ADR may be **Proposed** |
| Multi-backend storage | [reference/storage_backends.md](reference/storage_backends.md) | [architecture/STORAGE_BACKEND_SYSTEM.md](architecture/STORAGE_BACKEND_SYSTEM.md), ADR [0002](architecture/decisions/0002-backend-plugin-registry.md) | Current |
| VFS / buckets / journal | [VFS_CONTRACT_SPEC.md](VFS_CONTRACT_SPEC.md) | [filesystem_journal.md](filesystem_journal.md), [architecture/CONTENT_METADATA_VFS.md](architecture/CONTENT_METADATA_VFS.md) | Current |
| Cluster membership / pins | [operations/cluster_management.md](operations/cluster_management.md) | [architecture/CLUSTER_COORDINATION.md](architecture/CLUSTER_COORDINATION.md), ADR [0008](architecture/decisions/0008-cluster-control-plane-authority.md) | Current |
| Network / Iroh / libp2p | [iroh/README.md](iroh/README.md) | [architecture/NETWORK_TRANSPORTS.md](architecture/NETWORK_TRANSPORTS.md), ADR [0006](architecture/decisions/0006-multi-protocol-storage-and-networking.md) | Current |
| Async / optional deps | [architecture/ASYNC_AND_OPTIONAL_DEPENDENCIES.md](architecture/ASYNC_AND_OPTIONAL_DEPENDENCIES.md) | ADR [0001](architecture/decisions/0001-imports-and-optional-dependencies.md), [0004](architecture/decisions/0004-anyio-and-sync-boundaries.md) | Current |
| Config / secrets / state | [architecture/CONFIGURATION_STATE_AND_TRUST.md](architecture/CONFIGURATION_STATE_AND_TRUST.md) | [credential_management.md](credential_management.md), ADR [0007](architecture/decisions/0007-configuration-state-and-secret-references.md) | Current |
| Test | [development/testing_guide.md](development/testing_guide.md) | [testing/TEST_HEALTH_MATRIX.md](testing/TEST_HEALTH_MATRIX.md) | Current |
| Deploy containers | [deployment/docker/DOCKER_QUICK_START.md](deployment/docker/DOCKER_QUICK_START.md) | [containerization.md](containerization.md) | Current |
| Integrate external systems | [integration/INTEGRATION_OVERVIEW.md](integration/INTEGRATION_OVERVIEW.md) | [integration/INTEGRATION_QUICK_START.md](integration/INTEGRATION_QUICK_START.md) | Current |
| Understand design “why” | [architecture/decisions/README.md](architecture/decisions/README.md) | Subsystem architecture guides | Current / **Proposed** per ADR |
| Find a symbol / example | [api_generated/module_structure.md](api_generated/module_structure.md) | [api_generated/examples_index.md](api_generated/examples_index.md) | **Generated** |
| Archaeology / provenance | [ARCHIVE/README.md](ARCHIVE/README.md) | [audits/HISTORICAL_DOCUMENT_REGISTER.md](audits/HISTORICAL_DOCUMENT_REGISTER.md) | **Historical** |

---

## 4. Paths by system

Canonical architecture hub and full reading order: **[`architecture/README.md`](architecture/README.md)**.

| System concern | Architecture guide | Operator / API companions |
|---|---|---|
| End-to-end context | [SYSTEM_OVERVIEW.md](architecture/SYSTEM_OVERVIEW.md) | [index.md](index.md) |
| Processes & entry points | [RUNTIME_AND_ENTRYPOINTS.md](architecture/RUNTIME_AND_ENTRYPOINTS.md) | packaging scripts in `pyproject.toml` |
| Shims / legacy trees | [COMPATIBILITY_LAYERS.md](architecture/COMPATIBILITY_LAYERS.md) | — |
| Backend plugins & adapters | [STORAGE_BACKEND_SYSTEM.md](architecture/STORAGE_BACKEND_SYSTEM.md) | [reference/storage_backends.md](reference/storage_backends.md) |
| Content, metadata, VFS, WAL | [CONTENT_METADATA_VFS.md](architecture/CONTENT_METADATA_VFS.md) | [VFS_CONTRACT_SPEC.md](VFS_CONTRACT_SPEC.md) |
| Cluster coordination | [CLUSTER_COORDINATION.md](architecture/CLUSTER_COORDINATION.md) | [operations/cluster_management.md](operations/cluster_management.md) |
| Network transports | [NETWORK_TRANSPORTS.md](architecture/NETWORK_TRANSPORTS.md) | [iroh/README.md](iroh/README.md) |
| MCP control plane | [MCP_CONTROL_PLANE.md](architecture/MCP_CONTROL_PLANE.md) | [api/mcp_reference.md](api/mcp_reference.md) |
| Async & optional deps | [ASYNC_AND_OPTIONAL_DEPENDENCIES.md](architecture/ASYNC_AND_OPTIONAL_DEPENDENCIES.md) | [development/async_architecture.md](development/async_architecture.md) |
| Config, state, trust | [CONFIGURATION_STATE_AND_TRUST.md](architecture/CONFIGURATION_STATE_AND_TRUST.md) | [credential_management.md](credential_management.md) |
| Shared vocabulary | [GLOSSARY.md](architecture/GLOSSARY.md) | — |
| Evidence & conflicts | [SOURCE_OF_TRUTH_MAP.md](architecture/SOURCE_OF_TRUTH_MAP.md) | [audits/PUBLIC_SURFACE_MATRIX.md](audits/PUBLIC_SURFACE_MATRIX.md) |
| Agent orientation | [AGENT_SYSTEM_MAP.md](architecture/AGENT_SYSTEM_MAP.md) | [api_generated/AGENT_GUIDE.md](api_generated/AGENT_GUIDE.md) (**Generated**) |

---

## 5. Directory map (what lives where)

| Path | Role | Default class |
|---|---|---|
| `docs/index.md` | Concise landing | Current (nav) |
| `docs/README.md` | This map | Current (nav) |
| `docs/DOCUMENTATION_INDEX.md` | Topic catalog | Current (nav catalog) |
| `docs/architecture/` | Architecture guides, glossary, agent map, SoT | Current |
| `docs/architecture/decisions/` | ADRs | Current records; decisions may be **Proposed** |
| `docs/api/` | Authored API / CLI / MCP references | Current |
| `docs/api_generated/` | Generator-owned inventories | **Generated** |
| `docs/guides/` | How-to and governance standards | Current |
| `docs/operations/` | Operator runbooks | Current |
| `docs/reference/` | Feature references + external ownership record | Current / **External** (ownership doc) |
| `docs/integration/` | Integration hub | Current |
| `docs/development/` | Testing, validation, impact maps | Current |
| `docs/deployment/`, `docs/ci-cd/` | Deploy and CI notes | Mixed — prefer Current runbooks; many CI summaries are **Historical** |
| `docs/features/` | Feature-specific guides | Mixed — prefer guides without COMPLETE status banners |
| `docs/iroh/` | Iroh integration | Current |
| `docs/testing/` | Test health / matrices | Mixed — process docs Current; coverage campaigns **Historical** |
| `docs/migration/` | Migration episode notes | **Historical** (unless re-verified) |
| `docs/implementation/`, `docs/fixes/`, `docs/status_reports/`, `docs/test_reports/`, `docs/project/` | Episode reports and completion narratives | **Historical** unless a specific file is re-homed |
| `docs/ARCHIVE/` | Explicit non-current quarantine | **Historical** |
| `docs/ipfs-docs/`, `docs/*-sdk/`, `docs/libp2p-*`, `docs/lassie/`, `docs/storacha_specs/`, `docs/py-ipld-*`, … | External gitlinks or embedded snapshots | **External** — see [EXTERNAL_DOCUMENTATION_SOURCES.md](reference/EXTERNAL_DOCUMENTATION_SOURCES.md) |
| `docs/workflows/` | Maintainer workflows | Current |
| `docs/audits/` | Program inventories and contracts | Current (audit class) |
| Root-level `*COMPLETE*`, coverage roadmaps, phase reports under `docs/` | Campaign dumps | **Historical** — do not promote |

Program-control (operator-protected, not product how-to): `documentation_plan.md`, `architecture/ipfs_kit_documentation.objectives.md`, `architecture/ipfs_kit_documentation.todo.md`.

---

## 6. Generated material

| Entry | Class | Notes |
|---|---|---|
| [api_generated/README.md](api_generated/README.md) | **Generated** | Index; do not hand-edit bodies |
| [api_generated/module_structure.md](api_generated/module_structure.md) | **Generated** | Module/signature inventory |
| [api_generated/dependencies.md](api_generated/dependencies.md) | **Generated** | From packaging |
| [api_generated/examples_index.md](api_generated/examples_index.md) | **Generated** | Example file index |
| [api_generated/AGENT_GUIDE.md](api_generated/AGENT_GUIDE.md) | **Generated** | Compact agent entry points |
| [api_generated/doc_status.md](api_generated/doc_status.md) | **Generated** | Measured counts |
| [audits/GENERATED_DOCUMENTATION_CONTRACT.md](audits/GENERATED_DOCUMENTATION_CONTRACT.md) | Current (contract) | How generation is defined |

Authored conceptual API notes remain under `docs/api/` (**Current**). Prefer packaging + tests when generated and authored disagree.

---

## 7. Historical material

| Entry | Class | Notes |
|---|---|---|
| [ARCHIVE/README.md](ARCHIVE/README.md) | **Historical** boundary | **Start here for archive rules** — never as product how-to |
| [ARCHIVE/implementation/](ARCHIVE/implementation/) | **Historical** | Intake for implementation reports |
| [ARCHIVE/status-and-fixes/](ARCHIVE/status-and-fixes/) | **Historical** | Status/fix quarantine |
| [audits/HISTORICAL_DOCUMENT_REGISTER.md](audits/HISTORICAL_DOCUMENT_REGISTER.md) | Current register | Classification of historical families |
| [audits/DUPLICATE_AND_REDIRECT_PLAN.md](audits/DUPLICATE_AND_REDIRECT_PLAN.md) | Current plan | Duplicate dispositions |
| `docs/implementation/**`, root `*COMPLETE*`, coverage campaigns | **Historical** | Discoverable; **not** start-here targets |
| [migration/MCP_SERVER_MIGRATION_GUIDE.md](migration/MCP_SERVER_MIGRATION_GUIDE.md) | **Historical** | Migration provenance — not live runtime authority |

---

## 8. External material

Ownership and empty-checkout expectations: **[reference/EXTERNAL_DOCUMENTATION_SOURCES.md](reference/EXTERNAL_DOCUMENTATION_SOURCES.md)** (**External** boundary record).

Examples of external / embedded paths (not authored kit guidance):

- Documentation gitlinks under `docs/` (may be empty without intentional submodule init)
- Embedded snapshots such as `docs/py-ipld-*`
- Vendored SDK or upstream doc trees (`docs/*-sdk/`, `docs/ipfs-docs/`, etc.)

**Rule:** external trees do not override kit packaging, tests, ADRs, or Current guides. Documentation tasks must not fetch gitlinks solely to fill empty directories.

---

## 9. Proposed material

| Kind | Where labeled | Rule |
|---|---|---|
| ADR decisions not yet accepted | [architecture/decisions/](architecture/decisions/README.md) status field | Do not describe as shipped policy |
| Open owner decisions `U-*` | [SOURCE_OF_TRUTH_MAP.md](architecture/SOURCE_OF_TRUTH_MAP.md) | Evidence gaps, not resolved truth |
| Roadmaps / future features | e.g. [ROADMAP_FEATURES.md](ROADMAP_FEATURES.md) | Treat as **Proposed** / planning unless re-verified Current |

---

## 10. Repository root (outside `docs/`)

| Path | Use |
|---|---|
| Repository `README.md` | Project overview and contribution entry (not a substitute for this map) |
| `pyproject.toml` | Packaging, scripts, extras — highest narrative authority for entry points |
| `examples/` | Runnable samples (indexed under **Generated** examples list) |
| `tests/` | Rank-1 behavior evidence |
| `CHANGELOG.md` | Release history |

---

## 11. Maintenance

- Only **KDOC-060** (or a later exclusive navigation owner) rewrites these four navigation files.  
- Content tasks update their declared outputs and may **not** reintroduce competing landings or promote ARCHIVE/COMPLETE paths as Current.  
- After large doc moves, re-verify local links from this map and [`index.md`](index.md).  
- Final link audit: planned under KDOC-061 (`docs/audits/FINAL_NAVIGATION_AND_LINK_AUDIT.md`).
