# IPFS Kit documentation

| Field | Value |
|---|---|
| **Document class** | Canonical (navigation landing) |
| **Authority class** | **Sole concise start-here** for `docs/` |
| **Status** | active |
| **Owner / task** | KDOC-060 |
| **Goal id** | KDOC-G080 / KDOC-G050 |
| **Last verified** | 2026-08-04 |
| **Scope** | First-stop navigation only; not a full inventory |
| **Non-goals** | Exhaustive file lists; historical campaign catalogs; generated API dumps |

> **Navigation authority (exclusive).**  
> This page is the **only** concise “start here” landing for documentation.  
> - Full repository map → [`docs/README.md`](README.md)  
> - Structured catalog → [`docs/DOCUMENTATION_INDEX.md`](DOCUMENTATION_INDEX.md)  
> - Architecture & ADR reading order → [`docs/architecture/README.md`](architecture/README.md)  
> Those three files **do not** compete as alternate landings; each has one role.

---

## Material classes (read this first)

Every linked path below is labeled. Prefer **Current** over everything else for how-to and production claims.

| Label | Meaning | May use as how-to? |
|---|---|---|
| **Current** | Maintained guidance verified against the tree | Yes |
| **Generated** | Deterministic inventory from code/packaging | Reference only |
| **Historical** | Dated reports, COMPLETE summaries, ARCHIVE | No |
| **External** | Gitlinks / vendored upstream (may be empty) | Upstream contract only |
| **Proposed** | Intent not yet shipped or owner-accepted | No (label as proposal) |

Lifecycle rules: [`docs/guides/DOCUMENTATION_GUIDE.md`](guides/DOCUMENTATION_GUIDE.md) (**Current**).

---

## Start here (Current)

| If you need… | Open |
|---|---|
| Install and verify | [`installation_guide.md`](installation_guide.md) → [`QUICK_REFERENCE.md`](QUICK_REFERENCE.md) |
| Python / high-level API | [`api/high_level_api.md`](api/high_level_api.md) → [`api/api_reference.md`](api/api_reference.md) |
| CLI | [`api/cli_reference.md`](api/cli_reference.md) |
| MCP / control plane | [`api/mcp_reference.md`](api/mcp_reference.md) · architecture [`architecture/MCP_CONTROL_PLANE.md`](architecture/MCP_CONTROL_PLANE.md) |
| System context | [`architecture/SYSTEM_OVERVIEW.md`](architecture/SYSTEM_OVERVIEW.md) · [architecture hub](architecture/README.md) |
| Storage backends | [`reference/storage_backends.md`](reference/storage_backends.md) · [`architecture/STORAGE_BACKEND_SYSTEM.md`](architecture/STORAGE_BACKEND_SYSTEM.md) |
| VFS / content plane | [`VFS_CONTRACT_SPEC.md`](VFS_CONTRACT_SPEC.md) · [`architecture/CONTENT_METADATA_VFS.md`](architecture/CONTENT_METADATA_VFS.md) |
| Cluster / ops | [`operations/cluster_management.md`](operations/cluster_management.md) · [`guides/CLUSTER_DEPLOYMENT_GUIDE.md`](guides/CLUSTER_DEPLOYMENT_GUIDE.md) |
| Testing | [`development/testing_guide.md`](development/testing_guide.md) |
| Agent orientation | [`architecture/AGENT_SYSTEM_MAP.md`](architecture/AGENT_SYSTEM_MAP.md) · [**Generated**] [`api_generated/AGENT_GUIDE.md`](api_generated/AGENT_GUIDE.md) |

Packaging and console scripts in `pyproject.toml` outrank any narrative claim about “the” runtime entry point.

---

## Paths by role

### New user / integrator

1. [Installation](installation_guide.md) (**Current**)  
2. [Quick reference](QUICK_REFERENCE.md) (**Current**)  
3. [High-level API](api/high_level_api.md) or [CLI reference](api/cli_reference.md) (**Current**)  
4. Optional: [Integration quick start](integration/INTEGRATION_QUICK_START.md) (**Current**)

### Application developer

1. [API reference](api/api_reference.md) · [High-level API](api/high_level_api.md) (**Current**)  
2. [Storage backends](reference/storage_backends.md) · [VFS contract](VFS_CONTRACT_SPEC.md) (**Current**)  
3. [System overview](architecture/SYSTEM_OVERVIEW.md) → subsystem guides ([architecture hub](architecture/README.md)) (**Current**)  
4. [ADRs](architecture/decisions/README.md) when authority is disputed (**Current** records; some decisions remain **Proposed**)

### Operator / SRE

1. [Cluster management](operations/cluster_management.md) · [Cluster state](operations/cluster_state.md) · [Monitoring](operations/cluster_monitoring.md) (**Current**)  
2. [Cluster deployment guide](guides/CLUSTER_DEPLOYMENT_GUIDE.md) · [Docker quick start](deployment/docker/DOCKER_QUICK_START.md) (**Current**)  
3. [Credentials](credential_management.md) · [Secure credentials guide](guides/SECURE_CREDENTIALS_GUIDE.md) (**Current**)  
4. [Configuration, state, and trust](architecture/CONFIGURATION_STATE_AND_TRUST.md) (**Current**)

### Implementation / review agent

1. [Agent system map](architecture/AGENT_SYSTEM_MAP.md) (**Current**)  
2. [Documentation impact map](development/DOCUMENTATION_IMPACT_MAP.md) (**Current**)  
3. [Debugging by subsystem](guides/DEBUGGING_BY_SUBSYSTEM.md) (**Current**)  
4. [**Generated**] [Agent guide](api_generated/AGENT_GUIDE.md) · [Module inventory](api_generated/module_structure.md)  
5. [Source-of-truth map](architecture/SOURCE_OF_TRUTH_MAP.md) for open authorities (**Current** evidence)

### Documentation maintainer

1. [Documentation guide](guides/DOCUMENTATION_GUIDE.md) (**Current** contract)  
2. [Documentation validation](development/DOCUMENTATION_VALIDATION.md) · [Maintenance workflow](workflows/documentation-maintenance.md) (**Current**)  
3. Full map: [`README.md`](README.md) · Catalog: [`DOCUMENTATION_INDEX.md`](DOCUMENTATION_INDEX.md)

---

## Paths by task

| Task | Primary (**Current**) | Related |
|---|---|---|
| Install / installers | [installation_guide.md](installation_guide.md) | [INSTALLER_DOCUMENTATION.md](INSTALLER_DOCUMENTATION.md) |
| Call the Python API | [api/high_level_api.md](api/high_level_api.md) | [api/api_reference.md](api/api_reference.md) |
| Use the CLI | [api/cli_reference.md](api/cli_reference.md) | [guides/CLI_POLICY_USAGE_GUIDE.md](guides/CLI_POLICY_USAGE_GUIDE.md) |
| Run or extend MCP | [api/mcp_reference.md](api/mcp_reference.md) | [architecture/MCP_CONTROL_PLANE.md](architecture/MCP_CONTROL_PLANE.md) |
| Configure backends | [reference/storage_backends.md](reference/storage_backends.md) | [architecture/STORAGE_BACKEND_SYSTEM.md](architecture/STORAGE_BACKEND_SYSTEM.md) |
| VFS / journal / content | [VFS_CONTRACT_SPEC.md](VFS_CONTRACT_SPEC.md) | [filesystem_journal.md](filesystem_journal.md), [architecture/CONTENT_METADATA_VFS.md](architecture/CONTENT_METADATA_VFS.md) |
| Cluster deploy / ops | [operations/cluster_management.md](operations/cluster_management.md) | [architecture/CLUSTER_COORDINATION.md](architecture/CLUSTER_COORDINATION.md) |
| Iroh / network | [iroh/README.md](iroh/README.md) | [architecture/NETWORK_TRANSPORTS.md](architecture/NETWORK_TRANSPORTS.md) |
| Test | [development/testing_guide.md](development/testing_guide.md) | [testing/TEST_HEALTH_MATRIX.md](testing/TEST_HEALTH_MATRIX.md) |
| Integrate other systems | [integration/INTEGRATION_OVERVIEW.md](integration/INTEGRATION_OVERVIEW.md) | [integration/INTEGRATION_QUICK_START.md](integration/INTEGRATION_QUICK_START.md) |
| Understand a decision | [architecture/decisions/README.md](architecture/decisions/README.md) | [architecture/SOURCE_OF_TRUTH_MAP.md](architecture/SOURCE_OF_TRUTH_MAP.md) |

---

## Paths by system (architecture)

Recommended order is owned by the architecture hub: [`architecture/README.md`](architecture/README.md).

| Plane / concern | Guide (**Current**) |
|---|---|
| System context | [SYSTEM_OVERVIEW.md](architecture/SYSTEM_OVERVIEW.md) |
| Runtime & entry points | [RUNTIME_AND_ENTRYPOINTS.md](architecture/RUNTIME_AND_ENTRYPOINTS.md) |
| Compatibility layers | [COMPATIBILITY_LAYERS.md](architecture/COMPATIBILITY_LAYERS.md) |
| Storage backends | [STORAGE_BACKEND_SYSTEM.md](architecture/STORAGE_BACKEND_SYSTEM.md) |
| Content / metadata / VFS | [CONTENT_METADATA_VFS.md](architecture/CONTENT_METADATA_VFS.md) |
| Cluster coordination | [CLUSTER_COORDINATION.md](architecture/CLUSTER_COORDINATION.md) |
| Network transports | [NETWORK_TRANSPORTS.md](architecture/NETWORK_TRANSPORTS.md) |
| MCP control plane | [MCP_CONTROL_PLANE.md](architecture/MCP_CONTROL_PLANE.md) |
| Async & optional deps | [ASYNC_AND_OPTIONAL_DEPENDENCIES.md](architecture/ASYNC_AND_OPTIONAL_DEPENDENCIES.md) |
| Config, state, trust | [CONFIGURATION_STATE_AND_TRUST.md](architecture/CONFIGURATION_STATE_AND_TRUST.md) |
| Glossary | [GLOSSARY.md](architecture/GLOSSARY.md) |
| Evidence / open decisions | [SOURCE_OF_TRUTH_MAP.md](architecture/SOURCE_OF_TRUTH_MAP.md) |

---

## Non-current material (do not start here)

| Class | Boundary | Entry |
|---|---|---|
| **Historical** | Campaign reports, COMPLETE summaries, old status | [`ARCHIVE/README.md`](ARCHIVE/README.md) — **not** current guidance |
| **Generated** | AST/packaging inventories | [`api_generated/README.md`](api_generated/README.md) · contract [`audits/GENERATED_DOCUMENTATION_CONTRACT.md`](audits/GENERATED_DOCUMENTATION_CONTRACT.md) |
| **External** | Gitlinks & embedded upstream snapshots | [`reference/EXTERNAL_DOCUMENTATION_SOURCES.md`](reference/EXTERNAL_DOCUMENTATION_SOURCES.md) |
| **Proposed** | Unaccepted ADRs / program targets | Flagged inside [ADRs](architecture/decisions/README.md) and open `U-*` items in [SOURCE_OF_TRUTH_MAP](architecture/SOURCE_OF_TRUTH_MAP.md) |

**Do not** treat `docs/implementation/*COMPLETE*`, root coverage roadmaps, or `docs/ARCHIVE/**` as production status or install authority.

---

## Navigation roles (no competing authority)

| File | Role | Authority |
|---|---|---|
| **`docs/index.md`** (this page) | Concise landing | **Start-here** only |
| [`docs/README.md`](README.md) | Complete repository map | Map, not landing |
| [`docs/DOCUMENTATION_INDEX.md`](DOCUMENTATION_INDEX.md) | Structured topic catalog | Catalog; defers to landing + map |
| [`docs/architecture/README.md`](architecture/README.md) | Architecture + ADR reading order | Architecture hub only |
| [`docs/QUICK_REFERENCE.md`](QUICK_REFERENCE.md) | Command/API cheatsheet | Cheatsheet; not a second index |

Program-control inputs (operators only; not navigation targets for product how-to): `docs/documentation_plan.md`, objectives, and task board under `docs/architecture/`.

---

## Support

- Issues: use the repository issue tracker with reproduction steps.  
- Validation policy for doc work: set `IPFS_KIT_AUTO_INSTALL_BINARIES=0` when running offline checks (see [DOCUMENTATION_VALIDATION.md](development/DOCUMENTATION_VALIDATION.md)).
