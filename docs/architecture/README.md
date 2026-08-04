# Architecture documentation — reading order and ADR hub

| Field | Value |
|---|---|
| **Document class** | Canonical (architecture navigation) |
| **Authority class** | **Architecture and ADR reading order only** — not the global docs landing |
| **Status** | active |
| **Owner / task** | KDOC-060 |
| **Goal id** | KDOC-G080 / KDOC-G020 / KDOC-G030 |
| **Last verified** | 2026-08-04 |
| **Scope** | Order and index for architecture guides and decisions under `docs/architecture/` |
| **Non-goals** | Replacing [`docs/index.md`](../index.md); API how-to; historical campaign indexes |

> **Navigation role.**  
> Global start-here: [`docs/index.md`](../index.md)  
> Full docs map: [`docs/README.md`](../README.md)  
> Topic catalog: [`docs/DOCUMENTATION_INDEX.md`](../DOCUMENTATION_INDEX.md)  
> **This page** owns only the architecture guide sequence and ADR entry.

All architecture guides below are **Current** unless marked otherwise. ADR **decision status** may still be **Proposed** — that is independent of the file being a maintained record (see [decisions/README.md](decisions/README.md)).

---

## 1. Material classes in this tree

| Path / kind | Class | Notes |
|---|---|---|
| Subsystem guides (`SYSTEM_OVERVIEW.md`, …) | **Current** | Primary architecture path |
| [GLOSSARY.md](GLOSSARY.md), [SOURCE_OF_TRUTH_MAP.md](SOURCE_OF_TRUTH_MAP.md), [AGENT_SYSTEM_MAP.md](AGENT_SYSTEM_MAP.md) | **Current** | Vocabulary, evidence, agents |
| [decisions/](decisions/) ADRs | **Current** records | Decision status may be **Proposed** / Accepted / … |
| Older `*AUDIT*`, visual summaries, pre-KDOC architecture titles | **Historical** or superseded | Not the default path |
| Program objectives / todo under this directory | Program-control | Operator-protected; not product architecture how-to |

---

## 2. Recommended reading order (system path)

For a new contributor, reviewer, or agent learning the bespoke system:

| Step | Document | Owns |
|---|---|---|
| 1 | [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md) | Context, actors, data vs control plane, trust, deployment shapes |
| 2 | [GLOSSARY.md](GLOSSARY.md) | Shared terms (backend vs adapter, VFS, WAL, receipt, …) |
| 3 | [RUNTIME_AND_ENTRYPOINTS.md](RUNTIME_AND_ENTRYPOINTS.md) | Packaging scripts, process ownership, init/shutdown |
| 4 | [CONTENT_METADATA_VFS.md](CONTENT_METADATA_VFS.md) | Content bytes, CIDs, buckets/VFS, journal/WAL data plane |
| 5 | [STORAGE_BACKEND_SYSTEM.md](STORAGE_BACKEND_SYSTEM.md) | Backend plugins vs live adapters, multi-backend |
| 6 | [MCP_CONTROL_PLANE.md](MCP_CONTROL_PLANE.md) | MCP++ registry, tools, receipts, control surfaces |
| 7 | [CLUSTER_COORDINATION.md](CLUSTER_COORDINATION.md) | Bespoke cluster vs external cluster wrappers |
| 8 | [NETWORK_TRANSPORTS.md](NETWORK_TRANSPORTS.md) | Iroh, libp2p, routing, P2P-related transport |
| 9 | [ASYNC_AND_OPTIONAL_DEPENDENCIES.md](ASYNC_AND_OPTIONAL_DEPENDENCIES.md) | AnyIO/asyncio, extras, degradation |
| 10 | [CONFIGURATION_STATE_AND_TRUST.md](CONFIGURATION_STATE_AND_TRUST.md) | Config precedence, state roots, credentials, trust |
| 11 | [COMPATIBILITY_LAYERS.md](COMPATIBILITY_LAYERS.md) | Shims, backups, historical import trees |
| 12 | [decisions/README.md](decisions/README.md) | ADR process + numbered decisions |
| 13 | [SOURCE_OF_TRUTH_MAP.md](SOURCE_OF_TRUTH_MAP.md) | Evidence ranks, conflicts `C-*`, open `U-*` |
| 14 | [AGENT_SYSTEM_MAP.md](AGENT_SYSTEM_MAP.md) | Compact map for implementation/review agents |

**Companion (Generated, not architecture authority):** [`docs/api_generated/AGENT_GUIDE.md`](../api_generated/AGENT_GUIDE.md).

**Companion (ops / API, outside this directory):** see role/task tables in [`docs/index.md`](../index.md) and [`docs/README.md`](../README.md).

---

## 3. Paths by role (architecture slice)

### 3.1 Application developer

1. [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md)  
2. [RUNTIME_AND_ENTRYPOINTS.md](RUNTIME_AND_ENTRYPOINTS.md)  
3. Data plane: [CONTENT_METADATA_VFS.md](CONTENT_METADATA_VFS.md) → [STORAGE_BACKEND_SYSTEM.md](STORAGE_BACKEND_SYSTEM.md)  
4. Control plane: [MCP_CONTROL_PLANE.md](MCP_CONTROL_PLANE.md)  
5. Relevant ADRs under [decisions/](decisions/)

### 3.2 Operator / SRE

1. [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md) (§ deployment / failure domains)  
2. [CLUSTER_COORDINATION.md](CLUSTER_COORDINATION.md)  
3. [CONFIGURATION_STATE_AND_TRUST.md](CONFIGURATION_STATE_AND_TRUST.md)  
4. [RUNTIME_AND_ENTRYPOINTS.md](RUNTIME_AND_ENTRYPOINTS.md)  
5. Ops runbooks: [`docs/operations/`](../operations/) (**Current** companions)

### 3.3 Implementation / review agent

1. [AGENT_SYSTEM_MAP.md](AGENT_SYSTEM_MAP.md)  
2. [SOURCE_OF_TRUTH_MAP.md](SOURCE_OF_TRUTH_MAP.md) — open authorities before inventing “the” runtime  
3. [RUNTIME_AND_ENTRYPOINTS.md](RUNTIME_AND_ENTRYPOINTS.md)  
4. Subsystem guide matching the change  
5. [decisions/](decisions/) for disputed policy  
6. Impact: [`docs/development/DOCUMENTATION_IMPACT_MAP.md`](../development/DOCUMENTATION_IMPACT_MAP.md)  
7. Diagnostics: [`docs/guides/DEBUGGING_BY_SUBSYSTEM.md`](../guides/DEBUGGING_BY_SUBSYSTEM.md)

### 3.4 Architecture / ADR author

1. Claim standard: [`docs/guides/DOCUMENTATION_GUIDE.md`](../guides/DOCUMENTATION_GUIDE.md)  
2. [SOURCE_OF_TRUTH_MAP.md](SOURCE_OF_TRUTH_MAP.md)  
3. [decisions/README.md](decisions/README.md) + [decisions/0000-template.md](decisions/0000-template.md)  
4. Subsystem guide for the decision’s scope

---

## 4. Paths by task (architecture slice)

| Task | Architecture entry | Related ADR (if any) |
|---|---|---|
| Choose a process entry point | [RUNTIME_AND_ENTRYPOINTS.md](RUNTIME_AND_ENTRYPOINTS.md) | [0003-mcp-runtime-authority.md](decisions/0003-mcp-runtime-authority.md) |
| Understand optional imports / extras | [ASYNC_AND_OPTIONAL_DEPENDENCIES.md](ASYNC_AND_OPTIONAL_DEPENDENCIES.md) | [0001-imports-and-optional-dependencies.md](decisions/0001-imports-and-optional-dependencies.md) |
| Backend plugin vs adapter | [STORAGE_BACKEND_SYSTEM.md](STORAGE_BACKEND_SYSTEM.md) | [0002-backend-plugin-registry.md](decisions/0002-backend-plugin-registry.md) |
| VFS / durability / metadata | [CONTENT_METADATA_VFS.md](CONTENT_METADATA_VFS.md) | [0005-content-metadata-and-durability.md](decisions/0005-content-metadata-and-durability.md) |
| Multi-protocol networking | [NETWORK_TRANSPORTS.md](NETWORK_TRANSPORTS.md) | [0006-multi-protocol-storage-and-networking.md](decisions/0006-multi-protocol-storage-and-networking.md) |
| Cluster authority | [CLUSTER_COORDINATION.md](CLUSTER_COORDINATION.md) | [0008-cluster-control-plane-authority.md](decisions/0008-cluster-control-plane-authority.md) |
| Config / secrets / state roots | [CONFIGURATION_STATE_AND_TRUST.md](CONFIGURATION_STATE_AND_TRUST.md) | [0007-configuration-state-and-secret-references.md](decisions/0007-configuration-state-and-secret-references.md) |
| AnyIO / sync boundaries | [ASYNC_AND_OPTIONAL_DEPENDENCIES.md](ASYNC_AND_OPTIONAL_DEPENDENCIES.md) | [0004-anyio-and-sync-boundaries.md](decisions/0004-anyio-and-sync-boundaries.md) |
| Doc site / generation toolchain | [SOURCE_OF_TRUTH_MAP.md](SOURCE_OF_TRUTH_MAP.md) (U-15) | [0009-documentation-site-toolchain.md](decisions/0009-documentation-site-toolchain.md) |
| Compatibility / shims | [COMPATIBILITY_LAYERS.md](COMPATIBILITY_LAYERS.md) | — |

---

## 5. Guide index (Current)

| Guide | File |
|---|---|
| System overview | [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md) |
| Runtime and entry points | [RUNTIME_AND_ENTRYPOINTS.md](RUNTIME_AND_ENTRYPOINTS.md) |
| Compatibility layers | [COMPATIBILITY_LAYERS.md](COMPATIBILITY_LAYERS.md) |
| Storage backend system | [STORAGE_BACKEND_SYSTEM.md](STORAGE_BACKEND_SYSTEM.md) |
| Content, metadata, VFS | [CONTENT_METADATA_VFS.md](CONTENT_METADATA_VFS.md) |
| Cluster coordination | [CLUSTER_COORDINATION.md](CLUSTER_COORDINATION.md) |
| Network transports | [NETWORK_TRANSPORTS.md](NETWORK_TRANSPORTS.md) |
| MCP control plane | [MCP_CONTROL_PLANE.md](MCP_CONTROL_PLANE.md) |
| Async and optional dependencies | [ASYNC_AND_OPTIONAL_DEPENDENCIES.md](ASYNC_AND_OPTIONAL_DEPENDENCIES.md) |
| Configuration, state, and trust | [CONFIGURATION_STATE_AND_TRUST.md](CONFIGURATION_STATE_AND_TRUST.md) |
| Glossary | [GLOSSARY.md](GLOSSARY.md) |
| Source-of-truth / open decisions | [SOURCE_OF_TRUTH_MAP.md](SOURCE_OF_TRUTH_MAP.md) |
| Agent system map | [AGENT_SYSTEM_MAP.md](AGENT_SYSTEM_MAP.md) |

---

## 6. Architectural decision records

**Process and index:** [decisions/README.md](decisions/README.md) (**Current**).

| ADR | File | Topic |
|---|---|---|
| Template | [decisions/0000-template.md](decisions/0000-template.md) | Copy for new ADRs |
| ADR-0001 | [decisions/0001-imports-and-optional-dependencies.md](decisions/0001-imports-and-optional-dependencies.md) | Imports and optional dependencies |
| ADR-0002 | [decisions/0002-backend-plugin-registry.md](decisions/0002-backend-plugin-registry.md) | Backend plugin registry |
| ADR-0003 | [decisions/0003-mcp-runtime-authority.md](decisions/0003-mcp-runtime-authority.md) | MCP runtime authority |
| ADR-0004 | [decisions/0004-anyio-and-sync-boundaries.md](decisions/0004-anyio-and-sync-boundaries.md) | AnyIO and sync boundaries |
| ADR-0005 | [decisions/0005-content-metadata-and-durability.md](decisions/0005-content-metadata-and-durability.md) | Content, metadata, durability |
| ADR-0006 | [decisions/0006-multi-protocol-storage-and-networking.md](decisions/0006-multi-protocol-storage-and-networking.md) | Multi-protocol storage/networking |
| ADR-0007 | [decisions/0007-configuration-state-and-secret-references.md](decisions/0007-configuration-state-and-secret-references.md) | Config, state, secret references |
| ADR-0008 | [decisions/0008-cluster-control-plane-authority.md](decisions/0008-cluster-control-plane-authority.md) | Cluster control-plane authority |
| ADR-0009 | [decisions/0009-documentation-site-toolchain.md](decisions/0009-documentation-site-toolchain.md) | Documentation site toolchain |

Read each ADR’s **decision status** header. **Proposed** decisions must not be cited as settled production policy.

---

## 7. Evidence and external companions

| Resource | Class | Role |
|---|---|---|
| [SOURCE_OF_TRUTH_MAP.md](SOURCE_OF_TRUTH_MAP.md) | Current | Ranked sources, conflicts, unknowns |
| [`docs/audits/PUBLIC_SURFACE_MATRIX.md`](../audits/PUBLIC_SURFACE_MATRIX.md) | Current (audit) | Public surface inventory |
| [`docs/api_generated/`](../api_generated/) | **Generated** | Symbol/example inventories |
| [`docs/ARCHIVE/`](../ARCHIVE/) | **Historical** | Not architecture authority |
| [`docs/reference/EXTERNAL_DOCUMENTATION_SOURCES.md`](../reference/EXTERNAL_DOCUMENTATION_SOURCES.md) | **External** | Gitlink / embedded ownership |

---

## 8. What not to use as primary architecture path

| Avoid as “current architecture” | Why |
|---|---|
| `docs/implementation/*COMPLETE*` and root phase summaries | **Historical** campaign reports |
| `docs/ARCHIVE/**` | Explicit non-current quarantine |
| Pre-program audit-only titles without KDOC headers | May be stale or partial |
| **Generated** API trees as conceptual design | Inventory only |
| **External** SDK/doc gitlinks | Upstream; may be empty |

---

## 9. Related non-architecture entry points

| Need | Go to |
|---|---|
| Install / first use | [`docs/installation_guide.md`](../installation_guide.md) |
| API / CLI / MCP how-to | [`docs/api/`](../api/) |
| Operator runbooks | [`docs/operations/`](../operations/) |
| Global landing | [`docs/index.md`](../index.md) |

---

## 10. Maintenance

- Content of each subsystem guide is owned by its KDOC architecture task; **this README** is owned by exclusive navigation (KDOC-060).  
- When adding a guide, append it to §2–§5 and cross-link from [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md) reading order if it is part of the default path.  
- New ADRs: follow [decisions/README.md](decisions/README.md); do not invent numbers outside the registered set without maintainer approval.  
- Program-control files in this directory (`ipfs_kit_documentation.objectives.md`, `ipfs_kit_documentation.todo.md`) are **not** edited by navigation or content implementation tasks.
