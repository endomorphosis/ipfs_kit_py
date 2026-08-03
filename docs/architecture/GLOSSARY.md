# Shared architecture glossary

- Status: evidence baseline (Wave 0)
- Task: KDOC-006
- Goal: KDOC-G013
- Authority class: Canonical (shared vocabulary; not a runtime contract)
- Baseline: repository inspection 2026-08-03
- Scope: implementation-linked definitions for architecture guides and ADRs
- Non-goals: invent maintainer decisions; redefine disputed APIs; replace
  subsystem guides; resolve authority conflicts

This glossary is the shared vocabulary packet for later architecture tasks
(KDOC-010..019 and related ADRs). Terms are linked to current source paths and
tests where they exist. Claims follow the program source policy: executable
behavior and focused tests outrank packaging metadata, public source contracts,
Git history, and existing prose.

**How to use**

| Field | Meaning |
|---|---|
| Definition | Normative meaning for new architecture prose |
| Distinguish from | Commonly conflated neighbors |
| Implementation | Candidate authority paths (not an accepted ADR) |
| Status | `stable`, `working`, or `unresolved` for vocabulary conflicts |
| Related | Cross-links inside this glossary |

When a term has competing implementations, prefer the candidate authority and
mark the conflict **unresolved**. Do not present parallel modules as equally
authoritative without qualification.

Evidence anchors used throughout:

```bash
# Backend config plugins vs live adapters
rg -n 'BACKEND_ENTRY_POINT_GROUP|class BackendAdapter|class BackendManager' \
  ipfs_kit_py/backend_registry.py ipfs_kit_py/backends/base_adapter.py \
  ipfs_kit_py/backend_manager.py

# Content address / CID usage in durability and receipts
rg -n 'content.address|Content Identifier|cid' \
  ipfs_kit_py/mcp_server/agent_supervisor_receipts.py \
  docs/api/core_concepts.md

# WAL vs filesystem journal
rg -n 'class StorageWriteAheadLog|class FilesystemJournal' \
  ipfs_kit_py/storage_wal.py ipfs_kit_py/filesystem_journal.py

# MCP++ single tool registry and fail-closed receipts
rg -n 'HierarchicalToolManager|TOOL_GROUPS|AgentSupervisorReceiptResolver' \
  ipfs_kit_py/mcp_server/
```

---

## Adapter

| | |
|---|---|
| **Definition** | A live runtime object that implements storage (or protocol) operations against a concrete backend instance. Adapters hold connections, health state, and isomorphic method surfaces (add/get/list/health). |
| **Distinguish from** | **Backend** (named configuration document / type plugin); **registry** (type catalog, not an open connection). |
| **Implementation** | `ipfs_kit_py/backends/base_adapter.py` (`BackendAdapter` ABC); concrete adapters in `ipfs_kit_py/backends/` (`ipfs_backend.py`, `iroh_backend.py`, `filesystem_backend.py`, `s3_backend.py`, `real_api_storage_backends.py`). Parallel top-level `ipfs_kit_py/ipfs_backend.py` exists as a compatibility/historical path. |
| **Status** | Working. **Unresolved:** which factory path constructs adapters from validated YAML (direct `backends/*` callers, routing layer, or a single manager API)—see [SOURCE_OF_TRUTH_MAP](./SOURCE_OF_TRUTH_MAP.md) §2. |
| **Related** | [Backend](#backend), [Registry](#registry), [Compatibility layer](#compatibility-layer) |

---

## Authoritative state

| | |
|---|---|
| **Definition** | State that is the recovery source of truth for a concern: if it is lost or corrupted, the system cannot reconstruct that concern without external input. Examples include content-addressed block bytes that have no other replica, durable coordination artifacts whose integrity is verified on read, and namespace heads that the owning store treats as primary. |
| **Distinguish from** | **Rebuildable state** (derivable caches/indexes); **receipt** (verified artifact about work, not necessarily the data plane itself); **index** (often secondary). |
| **Implementation** | Context-dependent. Content bytes under pins/backends; Iroh namespace-head authority described in `ipfs_kit_py/iroh/manifest.py` (sidecar is namespace-head authority; portable JSON contract is local); MCP++ durable coordination via `ipfs_kit_py/mcp_server/mcplusplus/coordination_storage.py` and fail-closed receipt loads in `agent_supervisor_receipts.py`. |
| **Status** | Working concept; **unresolved per subsystem** which store is authoritative for cluster state (`cluster_state.py` vs `services/state_service.py` vs `DurableCoordinationStore`) and whether Arrow metadata is authoritative or rebuildable—see map §3–§4. |
| **Related** | [Rebuildable state](#rebuildable-state), [Receipt](#receipt), [Manifest](#manifest), [Content address / content addressing](#content-address--content-addressing) |

---

## Backend

| | |
|---|---|
| **Definition** | A named, validated storage configuration document plus a registered *type* plugin that describes how to interpret that document. Backend configuration is side-effect-free: discovery and validation must not start daemons, resolve live credentials into connections, or open storage sessions. |
| **Distinguish from** | **Adapter** (live runtime instance); **service** / **daemon** (process lifecycle); **bucket** (logical namespace over content, not a backend type). |
| **Implementation** | Type registry: `ipfs_kit_py/backend_registry.py` (`BACKEND_ENTRY_POINT_GROUP = "ipfs_kit.backends"`, redaction, migration hooks). Named documents: `ipfs_kit_py/backend_manager.py` (atomic YAML under `~/.ipfs_kit/backends/`). Schemas/policies: `backend_schemas.py`, `backend_policies.py`, `backend_config.py`. Examples: `config/enhanced_backend_examples.yaml`, `config/iroh-backend.example.yaml`. |
| **Status** | Stable distinction in code comments and registry module docstring. |
| **Related** | [Adapter](#adapter), [Registry](#registry), [Service](#service) |

---

## Bucket

| | |
|---|---|
| **Definition** | A logical S3-like content namespace that groups paths, metadata, and often a mapped storage backend. Buckets are operator-facing units for list/put/get/version workflows and are distinct from raw CID blocks. |
| **Distinguish from** | **VFS** (path/mount abstraction that may sit on buckets); **backend** (where bytes live); **manifest** (directory revision document, especially Iroh). |
| **Implementation** | Candidate managers: `bucket_vfs_manager.py`, `bucket_vfs_api.py`, `bucket_manager.py`, `unified_bucket_interface.py`, `unified_bucket_cli.py`, `vfs_bucket_manager.py`. CLI composition via `unified_cli_dispatcher.py` bucket subcommands. Tests: `tests/test_bucket_*.py`, `tests/test_unified_bucket_api.py`, `tests/test_bucket_backend_mapping.py`. |
| **Status** | Working. **Unresolved:** production-default manager among `bucket_vfs_manager`, `unified_bucket_interface`, and simplified variants (`simple_bucket_manager.py`, `simplified_bucket_manager.py`). |
| **Related** | [VFS](#vfs-virtual-filesystem), [Backend](#backend), [Index](#index) |

---

## CAR (Content Addressable aRchive)

| | |
|---|---|
| **Definition** | A portable archive format that packages content-addressed blocks (and roots) for import/export and offline transfer. In this tree, CAR tooling is part of durability and MCP tool surfaces, not a separate storage backend type. |
| **Distinguish from** | **WAL** (operation log); **CID** (identifier); **pin** (local retention intent). |
| **Implementation** | `ipfs_kit_py/car_wal_manager.py`; MCP tools `ipfs_kit_py/mcp_server/tools/car_tools.py`. Tests: `tests/test_car_and_files_tools.py`, `tests/test_car_import_to_bucket.py`, `tests/test_phase3_car_files.py`. |
| **Status** | Working. |
| **Related** | [Content address / content addressing](#content-address--content-addressing), [WAL](#wal-write-ahead-log), [CID](#cid-content-identifier) |

---

## CID (Content Identifier)

| | |
|---|---|
| **Definition** | A self-describing, multiformat hash-based identifier for content-addressed data. The same bytes under the same codec/hash parameters yield the same CID; any content change yields a different CID. CIDv0 (`Qm…`) and CIDv1 (`bafy…`) both appear in kit workflows. |
| **Distinguish from** | **Content address / content addressing** (the *method*); **receipt ID** (may be a CID of an artifact, but names a coordination record); **path** in VFS/bucket (location in a namespace, may resolve to a CID). |
| **Implementation** | Used across pins (`pins.py`, `pin_manager.py`), VFS contracts (`docs/VFS_CONTRACT_SPEC.md` lineage fields), Iroh blob/manifest paths, and receipt resolution (`agent_supervisor_receipts.py` accepts receipt IDs or CIDs). Conceptual prose: `docs/api/core_concepts.md`. |
| **Status** | Stable IPFS/IPLD concept; kit-specific wrappers vary by subsystem. |
| **Related** | [Content address / content addressing](#content-address--content-addressing), [Pin](#pin), [Receipt](#receipt) |

---

## Compatibility layer

| | |
|---|---|
| **Definition** | Code, packaging entry, or documentation path retained for transition, shims, legacy imports, or historical behavior that is **not** the preferred authority for new work. Compatibility layers may still run and be tested; they must be labeled so architecture prose does not treat them as equal defaults. |
| **Distinguish from** | **Candidate authority** (primary path for a concern); **historical/archive** material that is not on the runtime path; **optional dependency** (feature may be absent without being “legacy”). |
| **Implementation** | Examples from the source map: `ipfs_kit_py/mcp/` and root `mcp/` shims vs packaged `mcp_server`; `compat.py`; high-level API `*.fixed` / `*_improved.py` backups; top-level vs `backends/` IPFS adapter duals; deprecated routing gRPC backups under `routing/`. Classification ownership: future `docs/architecture/COMPATIBILITY_LAYERS.md` (KDOC-012 family). |
| **Status** | Working policy term. **Unresolved:** production MCP runtime authority (`mcp_server` vs `mcp` / root servers) remains proposed-ADR territory, not accepted here. |
| **Related** | [Tool surface](#tool-surface), [Registry](#registry), [Adapter](#adapter) |

---

## Content address / content addressing

| | |
|---|---|
| **Definition** | Identifying and retrieving data by a cryptographic digest of its bytes (and codec/multihash parameters), rather than by mutable location (host/path/URL alone). Content addressing enables immutability of identity, integrity verification, deduplication, and location-independent retrieval across peers and backends. |
| **Distinguish from** | **CID** (the concrete identifier encoding); **location addressing** (classic URL/path identity); **authoritative state** (which store owns recovery—not the addressing scheme itself). |
| **Implementation** | Foundation concept across IPFS/Iroh/pin/VFS paths. Introductory prose: `docs/api/core_concepts.md` (“Content Addressing: The Foundation”). Receipts load content-addressed artifacts via `DurableCoordinationStore`. Iroh manifests use content hashes (`blake3` / manifest hash links in `iroh/manifest.py`). |
| **Status** | Stable. Required shared vocabulary for architecture and durability prose. |
| **Related** | [CID](#cid-content-identifier), [CAR](#car-content-addressable-archive), [Authoritative state](#authoritative-state), [Receipt](#receipt) |

---

## Daemon

| | |
|---|---|
| **Definition** | A long-running OS process that owns a network or storage service endpoint (for example Kubo `ipfs daemon`, IPFS Cluster service processes, or managed Iroh sidecars). Daemon managers start, stop, configure, and health-check those processes; they are not the storage adapter API itself. |
| **Distinguish from** | **Service** (broader managed capability, may be in-process); **adapter** (client-side API to storage); **MCP server** (control-plane process—may be daemon-like but is not a content daemon). |
| **Implementation** | Kubo lifecycle: `ipfs_kit_py/kubo_runtime.py`, `ipfs_daemon_manager.py`. Cluster wrappers: `ipfs_cluster_daemon_manager.py`, `ipfs_cluster_service.py`. Parallel managers: `intelligent_daemon_manager.py`, `enhanced_daemon_manager.py`, `cluster/enhanced_daemon_manager_with_cluster.py`. Config: `daemon_config_manager.py`, `daemon_cli.py`. Opt-in binary install gated by `IPFS_KIT_AUTO_INSTALL_BINARIES`. |
| **Status** | Working. **Unresolved:** which daemon manager is authority among enhanced/intelligent/cluster-enhanced variants. |
| **Related** | [Service](#service), [Node role](#node-role), [Backend](#backend) |

---

## Index

| | |
|---|---|
| **Definition** | A secondary structure optimized for query, listing, or metadata lookup over content, pins, or buckets. Indexes accelerate access; whether they are rebuildable or authoritative is a per-subsystem decision and must not be assumed. |
| **Distinguish from** | **Authoritative state** (recovery source); **manifest** (versioned directory document); **registry** (plugin/tool catalog, not content metadata). |
| **Implementation** | Arrow metadata: `arrow_metadata_index.py`, `arrow_metadata_index_anyio.py`, `metadata_manager.py`, `metadata_sync_handler.py`. Pin metadata: `pin_metadata_index.py`. Bucket index variants: `enhanced_bucket_index.py` / `enhanced_bucket_index_fixed.py` (parallel). Tests: `tests/test_enhanced_pin_metadata.py`, `tests/test_datasets_metadata_index_contract.py`. |
| **Status** | Working. **Unresolved:** whether Arrow metadata is authoritative, secondary, or rebuildable-from-pins/content. |
| **Related** | [Authoritative state](#authoritative-state), [Rebuildable state](#rebuildable-state), [Bucket](#bucket), [Pin](#pin) |

---

## Journal (filesystem journal)

| | |
|---|---|
| **Definition** | A transaction log of **filesystem metadata and structure** operations (create, delete, rename, write metadata, mount/unmount CID, checkpoints) used for VFS consistency and crash recovery. It works *alongside* the WAL but focuses on the virtual filesystem tree rather than backend storage operation queues. |
| **Distinguish from** | **WAL** (storage operation durability/queue across backends); **manifest** (Iroh directory revision); **index** (query structure). |
| **Implementation** | `ipfs_kit_py/filesystem_journal.py` (`FilesystemJournal`, `JournalOperationType`, `JournalEntryStatus`); integration `fs_journal_integration.py`, `fs_journal_backends.py`, `fs_journal_replication.py`. Operator prose: `docs/filesystem_journal.md`. |
| **Status** | Working distinction in module docstring. **Unresolved:** whether WAL + journal is required for all mutating VFS ops or some backends are exempt. |
| **Related** | [WAL](#wal-write-ahead-log), [VFS](#vfs-virtual-filesystem), [Authoritative state](#authoritative-state) |

---

## Manifest

| | |
|---|---|
| **Definition** | A versioned, structured directory (or namespace) document that lists entries, modes, and cryptographic links to prior revisions. In the Iroh path, the portable JSON manifest contract is validated and hashed in-process while the managed sidecar may own the durable namespace head. |
| **Distinguish from** | **Index** (query acceleration); **bucket** (operator namespace); **receipt** (work/audit artifact); **CID** (identifier of bytes or a linked object). |
| **Implementation** | `ipfs_kit_py/iroh/manifest.py` (`MANIFEST_SCHEMA_VERSION`, `IrohManifestStore` contract, `ParentRevision`, RFC 8785 canonicalization, BLAKE3 hashing, optimistic CAS). Tests: `tests/test_iroh_manifest.py`. Filesystem contracts: `docs/iroh/filesystem-contract.md`. |
| **Status** | Working for Iroh. Other “manifest” usages in older docs should be checked against this definition before reuse. |
| **Related** | [Authoritative state](#authoritative-state), [Content address / content addressing](#content-address--content-addressing), [VFS](#vfs-virtual-filesystem) |

---

## Node role

| | |
|---|---|
| **Definition** | A capability profile assigned to a kit node in the **bespoke** cluster model, controlling coordination duties, resource expectations, and often IPFS config overrides. Classic roles are master, worker, and leecher; the enum also includes modular, local, gateway, and observer. |
| **Distinguish from** | **Daemon** (process); **service** (managed capability); **Kubo IPFS Cluster peer roles** (separate wrapper family under `ipfs_cluster_*`); MCP tool categories (control-plane, not cluster membership). |
| **Implementation** | `ipfs_kit_py/cluster/role_manager.py` (`NodeRole` enum, `role_capabilities`). Coordination: `cluster_coordinator.py`, `cluster/cluster_manager.py`, `cluster_dynamic_roles.py`. Distinct Kubo Cluster wrappers: `ipfs_cluster_api.py`, `ipfs_cluster_ctl.py`, `ipfs_cluster_service.py`. Default high-level init often assumes leecher—see `docs/api/core_concepts.md`. |
| **Status** | Working for bespoke roles. **Unresolved:** production multi-node control-plane authority among bespoke cluster, Kubo Cluster wrappers, and MCP++ coordination store. |
| **Related** | [Service](#service), [Daemon](#daemon), [Authoritative state](#authoritative-state) |

---

## Pin

| | |
|---|---|
| **Definition** | An explicit retention intent that keeps content-addressed data (by CID) from being garbage-collected by a local or remote store. Pins are metadata about retention, not the content bytes themselves. |
| **Distinguish from** | **CID** (identity of content); **index** (query structure over pins/metadata); **receipt** (coordination artifact). |
| **Implementation** | `pins.py`, `pin_manager.py`, `simple_pin_manager.py`, `pin_metadata_index.py`, `pin_wal.py`, `cli/enhanced_pin_cli.py`. MCP tool groups include pin tools under `mcp_server/tools/`. Tests: `tests/test_enhanced_pin_metadata.py`. |
| **Status** | Working. Empty `enhanced_pin_index.py` is a stub—do not treat as authority. |
| **Related** | [CID](#cid-content-identifier), [Index](#index), [WAL](#wal-write-ahead-log) |

---

## Rebuildable state

| | |
|---|---|
| **Definition** | State that can be reconstructed from authoritative sources (content bytes, pins, journals, remote backends) after loss—for example caches, derived indexes, and some metadata projections. Losing rebuildable state degrades performance or features but is not, by itself, permanent data loss if authority remains. |
| **Distinguish from** | **Authoritative state** (cannot be reconstructed without external input); **compatibility layer** (code path classification, not state durability). |
| **Implementation** | Tiered/intelligent caches: `tiered_cache_manager.py`, `cache/`, `cache_manager.py`. Many index paths are *candidates* for rebuildable classification pending owner decision. Architecture gap called out in [SOURCE_OF_TRUTH_MAP](./SOURCE_OF_TRUTH_MAP.md) §3. |
| **Status** | Working concept; per-store classification still incomplete. |
| **Related** | [Authoritative state](#authoritative-state), [Index](#index), [Journal](#journal-filesystem-journal) |

---

## Receipt

| | |
|---|---|
| **Definition** | An immutable, content-addressed coordination or audit artifact recording that supervised work occurred (or failed), loaded only when its bytes can be verified. In MCP++, agent supervisor receipt reads are **fail-closed**: no fixture or synthetic-success fallback. |
| **Distinguish from** | **WAL entry** / **journal entry** (local durability of storage/FS ops); **CID** (may identify the receipt blob); **tool surface** (how the read is exposed). |
| **Implementation** | `ipfs_kit_py/mcp_server/agent_supervisor_receipts.py` (`AgentSupervisorReceiptResolver`, `METHOD = "agent_supervisor.receipts.read"`, capability `supervisor.receipts.read`). Storage: `mcp_server/mcplusplus/coordination_storage.py` (`DurableCoordinationStore`). Tests: `tests/test_agent_supervisor_receipts.py`. |
| **Status** | Working for fail-closed resolver semantics. **Unresolved:** operator defaults for where `DurableCoordinationStore` persists artifacts and multi-node read consistency. |
| **Related** | [Content address / content addressing](#content-address--content-addressing), [Authoritative state](#authoritative-state), [Tool surface](#tool-surface) |

---

## Registry

| | |
|---|---|
| **Definition** | A catalog that maps names/types to plugins, tools, or constructors **without** necessarily creating live instances. Registries are configuration and discovery authority; they are not open connections or running daemons. |
| **Distinguish from** | **Adapter** / live service instance; **index** (content metadata); **tool surface** (how tools are exposed over a protocol). |
| **Implementation** | Backend type registry: `backend_registry.py` (side-effect-free by design). MCP++ tools: `mcp_server/hierarchical_tool_manager.py` + `mcp_server/tools/` (`TOOL_GROUPS`) + `tool_metadata.py`; FastMCP binds the same registry in `fastmcp_app.py`. Core package: `ipfs_kit_py/core/tool_registry.py` (`ToolRegistry`)—distinct from MCP++ hierarchical manager; do not conflate. |
| **Status** | Working. **Unresolved:** confirm no second write-path tool registry remains outside `TOOL_GROUPS` / `HierarchicalToolManager` for production tools. |
| **Related** | [Backend](#backend), [Tool surface](#tool-surface), [Compatibility layer](#compatibility-layer) |

---

## Service

| | |
|---|---|
| **Definition** | A managed capability unit with lifecycle (start/stop/health) that may run in-process or delegate to an external daemon. Services are orchestration and dependency objects used by CLI, MCP, and kit composition—not the same as a storage **backend document** or a **node role**. |
| **Distinguish from** | **Daemon** (OS process endpoint); **adapter** (storage client API); **tool surface** (invocation protocol). |
| **Implementation** | `ipfs_kit_py/service_manager.py`, `ipfs_kit_py/core/service_manager.py` (`ServiceManager`). Domain services include `services/state_service.py` and Iroh service modules under `ipfs_kit_py/iroh/service.py`. Packaging scripts expose long-running control planes such as `ipfs-kit-mcp` → `mcp_server.server:main`. |
| **Status** | Working. Multiple `ServiceManager` implementations exist (package root vs `core/` vs legacy MCP copies)—call sites must name the path. |
| **Related** | [Daemon](#daemon), [Node role](#node-role), [Tool surface](#tool-surface) |

---

## Tool surface

| | |
|---|---|
| **Definition** | A protocol or API façade through which registered tools are listed, described, and invoked (MCP JSON-RPC, FastMCP, CLI tool commands, JS/TS SDK, optional P2P transport). Multiple surfaces should share **one** write-path tool registry for production MCP++. |
| **Distinguish from** | **Registry** (catalog/manager); **compatibility layer** (legacy MCP controllers/servers); **receipt** (artifact returned or stored by some tools). |
| **Implementation** | Packaged MCP++: `mcp_server/server.py`, hierarchical meta-tools in `hierarchical_tool_manager.py`, FastMCP in `fastmcp_app.py`, tools CLI `mcp_server/cli.py` (`ipfs-kit-mcp-tools`), JS SDK `mcp_server/js_sdk/`, P2P `p2p_transport.py`. Legacy: `ipfs_kit_py/mcp/`, root `mcp/*_mcp_tools.py` shims. Packaging: `pyproject.toml` scripts `ipfs-kit-mcp`, `ipfs-kit-mcp-tools`. |
| **Status** | Working packaging entry for MCP++. **Unresolved:** sole production runtime authority vs legacy `mcp/` stack (proposed ADR slot `0003-mcp-runtime-authority.md`). |
| **Related** | [Registry](#registry), [Receipt](#receipt), [Compatibility layer](#compatibility-layer) |

---

## VFS (Virtual filesystem)

| | |
|---|---|
| **Definition** | A path-oriented filesystem abstraction over content-addressed and multi-backend storage, supporting mount points, path resolution, list/read/write semantics, and integration with fsspec-style APIs. VFS is the data-plane path model; it is not the control-plane tool registry. |
| **Distinguish from** | **Bucket** (namespace unit often mounted under VFS); **adapter** (backend I/O); **journal** (metadata durability for VFS ops); **fsspec protocol brand** (packaging registration of a concrete filesystem class). |
| **Implementation** | Managers: `vfs_manager.py`, `bucket_vfs_manager.py`, `vfs_bucket_manager.py`, `vfs_version_tracker.py`. IPFS fsspec: `ipfs_fsspec.py` (`VFSCore`). Iroh: `iroh_fsspec.py`, `iroh_vfs.py`; packaging entry `fsspec.specs` → `IrohFileSystem` in `pyproject.toml`. Contract prose: `docs/VFS_CONTRACT_SPEC.md` (note: still cites legacy unified MCP server paths—freshness risk), `docs/iroh/filesystem-contract.md`. Tests: `tests/test_vfs_*.py`, `tests/test_mcp_vfs_*.py`, `tests/test_iroh_filesystem_contract.py`. |
| **Status** | Working. **Unresolved:** single supported manager API for new features; fsspec protocol brand support matrix (IPFS vs Iroh packaging). |
| **Related** | [Bucket](#bucket), [Journal](#journal-filesystem-journal), [Adapter](#adapter), [Manifest](#manifest) |

---

## WAL (Write-ahead log)

| | |
|---|---|
| **Definition** | A durable log of **storage operations** (add, get, pin, upload, etc.) queued and persisted so work can retry when backends are unavailable. The WAL records intended storage actions and their status; it is not the VFS structure journal. |
| **Distinguish from** | **Journal** (filesystem metadata/structure); **CAR** (block archive packaging); **receipt** (verified coordination artifact). |
| **Implementation** | Primary: `storage_wal.py` (`StorageWriteAheadLog`, `OperationType`, `OperationStatus`, `BackendType`). Related: `wal.py`, `enhanced_wal_durability.py`, `car_wal_manager.py`, `pin_wal.py`, `wal_integration.py`. Dual async telemetry modules `*_anyio.py` exist for some WAL-adjacent paths. |
| **Status** | Working. **Unresolved:** MCP++ tool parity for WAL historically incomplete; root `mcp/wal_mcp_tools.py` is a shim—verify against MCP++ `TOOL_GROUPS` in control-plane work. |
| **Related** | [Journal](#journal-filesystem-journal), [Backend](#backend), [CAR](#car-content-addressable-archive) |

---

## Commonly conflated pairs (quick reference)

Use this table when drafting architecture prose. Prefer the left column wording when both appear.

| Say… | Not as the same as… | Why they differ |
|---|---|---|
| Backend (config/type) | Adapter (live I/O) | Config plugins must not open connections; adapters do. |
| WAL | Filesystem journal | Storage operation queue vs VFS metadata transactions. |
| Authoritative state | Rebuildable state / cache / index | Recovery source vs reconstructible projection. |
| Registry | Running service / daemon | Catalog vs lifecycle process. |
| Tool surface | Tool registry | Protocol façade vs single catalog of tools. |
| MCP++ (`mcp_server`) | Legacy MCP (`mcp/`, root shims) | Packaged control plane vs compatibility stack—authority unresolved. |
| Bespoke node role | Kubo IPFS Cluster peer | Different module families and APIs. |
| Bucket | Backend | Namespace vs storage configuration. |
| CID | VFS path | Content identity vs mount-relative location. |
| Receipt | WAL/journal entry | Fail-closed verified artifact vs local durability log. |
| Manifest (Iroh) | Arrow / bucket index | Versioned directory document vs query index. |
| Service | Daemon | Managed capability (possibly in-process) vs OS process endpoint. |
| Content addressing | Location addressing | Identity by digest vs identity by host/path. |
| Compatibility layer | Candidate authority | Transition path vs preferred implementation for new work. |

---

## Unresolved vocabulary

These terms appear in source or docs but lack a single accepted definition or owner. Architecture writers must flag them rather than invent a decision. Prefer linking a **proposed** ADR over asserting acceptance.

| Term / phrase | Why unresolved | Evidence / next owner |
|---|---|---|
| **Production MCP runtime** | Packaged `ipfs_kit_py.mcp_server` coexists with large `ipfs_kit_py/mcp/` and root MCP scripts | Map §6; proposed ADR `0003-mcp-runtime-authority.md` |
| **Public package version string** | Packaging `0.3.0` vs `__init__.__version__ = "0.2.0"` | Map §1; release owner |
| **CLI composition authority** | `unified_cli_dispatcher.py` vs `cli.py` FastCLI split | Map §1; KDOC-011 |
| **High-level API module identity** | Monolithic `high_level_api.py` vs package dir helpers and `*_fixed` backups | Map §1 |
| **Live adapter factory** | No single documented constructor from YAML → `BackendAdapter` | Map §2 |
| **IPFS adapter path** | Top-level `ipfs_backend.py` vs `backends/ipfs_backend.py` | Map §2 |
| **Bucket/VFS stack default** | Multiple managers and simplified variants | Map §3; KDOC-013 guide |
| **Durability layering mandate** | Whether WAL + journal apply to every mutating VFS backend | Map §3 |
| **Metadata index role** | Arrow index authoritative vs rebuildable | Map §3 |
| **Cluster control-plane authority** | Bespoke `cluster*` vs Kubo Cluster wrappers vs MCP++ coordination store | Map §4; ADR `0008-cluster-control-plane-authority.md` |
| **Authoritative cluster state store** | `cluster_state.py` vs `StateService` vs `DurableCoordinationStore` | Map §4 |
| **Default content transport** | Kubo vs Iroh vs dual-write for new deployments | Map §5 |
| **Daemon manager authority** | enhanced / intelligent / cluster-enhanced managers | Map §5 |
| **Tool registry singularity** | Confirm no second production write-path registry | Map §6 |
| **Receipt store deployment defaults** | Persistence location and multi-node consistency | Map §6 |
| **Canonical config composition** | `config_manager` vs backend YAML vs daemon/Iroh config precedence | Map §7 |
| **fsspec protocol brands** | IPFS fsspec vs Iroh-only packaging entry | Map §3 |
| **“Service” class name collisions** | Multiple `ServiceManager` / tool registry copies under `core/` and `mcp/` | `core/service_manager.py`, `service_manager.py`, `mcp/ipfs_kit/core/*` |
| **Status vocabulary in older docs** | Phrases like “production ready” in pre-program docs without evidence ranking | Program plan requires accepted / proposed / inferred / unknown rationale labels (KDOC-005) |

When a later task resolves one of these items, update this table (or mark the row resolved with ADR link) in the same change that accepts the decision—do not silently redefine terms in subsystem guides only.

---

## Authority and status labels (for all architecture docs)

These labels are part of the shared vocabulary even when not subsystem-specific.

| Label | Meaning |
|---|---|
| **Candidate authority** | Best current implementation path from static evidence; not an accepted ADR |
| **Compatibility / historical** | Parallel, shim, legacy, backup, or archived surface |
| **Accepted** | Maintainer-confirmed decision with evidence |
| **Proposed** | Written ADR or design still awaiting confirmation |
| **Inferred** | Reasonable reading of code/history; may be wrong |
| **Unknown / unresolved** | Conflict or gap; must remain visible |
| **Generated** | Produced by tooling; not hand-maintained prose |
| **External** | Upstream or submodule content; not rewritten as kit authority |

Document classes and review checklists live in `docs/guides/DOCUMENTATION_GUIDE.md` (KDOC-005). This glossary owns term definitions; it does not own navigation (KDOC-060) or generated API output (KDOC-046).

---

## Related artifacts

| Artifact | Role |
|---|---|
| [SOURCE_OF_TRUTH_MAP.md](./SOURCE_OF_TRUTH_MAP.md) | Subsystem authorities, tests, unresolved owner decisions |
| [ipfs_kit_documentation.objectives.md](./ipfs_kit_documentation.objectives.md) | Goal heap (protected operator input) |
| [ipfs_kit_documentation.todo.md](./ipfs_kit_documentation.todo.md) | Executable board (protected operator input) |
| [../documentation_plan.md](../documentation_plan.md) | Human program plan (protected operator input) |
| `docs/iroh/*.md` | Normative Iroh contracts (security, lifecycle, filesystem) |
| `docs/VFS_CONTRACT_SPEC.md` | VFS request/response contract (freshness risk on runtime path) |
| `docs/api/core_concepts.md` | Older conceptual intro to content addressing and roles |

---

## Maintenance

- **Change triggers:** new public subsystem name, renamed packaging entry, accepted ADR that reassigns authority, or discovery of a second write-path registry/manager.
- **Edit policy:** this file is the sole KDOC-006 output; do not embed full subsystem designs here—link guides instead.
- **Validation (offline):**

```bash
test -s docs/architecture/GLOSSARY.md && rg -q "content address" docs/architecture/GLOSSARY.md
```
