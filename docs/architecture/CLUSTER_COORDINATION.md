# Cluster roles, coordination, consistency, and replication

| Field | Value |
|---|---|
| Document class | **Canonical** architecture guide (not an accepted ADR) |
| Status | active |
| Last verified | 2026-08-03 |
| Tree baseline | `6fc55f0918a0f45e04b37727b45c1a1f5aaf9322` |
| Owner / task | KDOC-015 |
| Goal id | KDOC-G023 |
| Track | arch-distributed |
| Evidence map | [`SOURCE_OF_TRUTH_MAP.md`](SOURCE_OF_TRUTH_MAP.md) §4 |
| Related ADRs | Planned: `docs/architecture/decisions/0008-cluster-control-plane-authority.md` (**KDOC-028**, not yet authored) |
| Change triggers | See [§13 Change triggers](#13-change-triggers-and-last-verified-baseline) |

This guide documents **bespoke kit cluster roles and coordination**, **Arrow / CRDT / Merkle-clock state paths**, **content and metadata replication edges**, **health and partition behavior**, and the **distinct Kubo IPFS Cluster wrapper family**. It does **not** select a single production multi-node control plane. Packaging keywords mention cluster management, but competing implementations, constructor/API mismatches, and thin cross-stack tests leave authority **unresolved** (**U-08**). The proposed authority decision belongs to **KDOC-028 / ADR 0008**.

Vocabulary: see [`GLOSSARY.md`](GLOSSARY.md) for *cluster role*, *daemon*, *service*, and control-plane terms.

---

## 1. Scope and explicit non-goals

### 1.1 Scope

| In scope | Why |
|---|---|
| Competing control-plane **families** (bespoke `cluster/` + `cluster_*`, Kubo `ipfs_cluster_*`, MCP++ coordination store) | Prevent conflating unrelated stacks |
| Roles and capabilities (master / worker / leecher and extended enums) | Operator and API surface |
| Membership, leader election, task distribution | Coordination lifecycle |
| Arrow cluster state snapshots and helpers | Shared state candidate |
| Vector-clock / CRDT-like state sync | Consistency path |
| Merkle clock and P2P workflow task ownership | Causal / task plane |
| Content replication managers and FS journal metadata replication | Replication edges |
| Health, heartbeats, partition, recovery, multi-region hooks | Failure modes |
| Focused tests under default pytest discovery | Rank-1 evidence |
| Observed constructor/API mismatches | Decision/follow-up for KDOC-028 |

### 1.2 Non-goals

| Out of scope | Owner / pointer |
|---|---|
| Choosing the production default multi-node control plane | **KDOC-028** → ADR 0008 |
| Kubo / Iroh / libp2p transport security and lifecycle detail | KDOC-016 → `NETWORK_TRANSPORTS.md` |
| MCP tool registry layout as a whole | KDOC-017 → `MCP_CONTROL_PLANE.md` |
| Content bytes, VFS path authority, WAL/journal durability layering | KDOC-014 → `CONTENT_METADATA_VFS.md` |
| Backend configuration plugins vs live adapters | KDOC-013 → `STORAGE_BACKEND_SYSTEM.md` |
| Exhaustive method inventories | Generated/reference docs; this guide teaches structure and mismatches |
| Editing protected program-control files | Operator policy |

---

## 2. Three control-plane families (no canonical selection)

Status labels follow [`SOURCE_OF_TRUTH_MAP.md`](SOURCE_OF_TRUTH_MAP.md). **Candidate** means “looks primary from static inspection of a family,” not “accepted production default.”

```text
                    Multi-node coordination in this repository
                    (authority among families is UNRESOLVED — U-08)
         ┌────────────────────────────┬────────────────────────────┐
         │                            │                            │
         ▼                            ▼                            ▼
 ┌───────────────────┐    ┌──────────────────────┐    ┌──────────────────────┐
 │ A. Bespoke kit    │    │ B. Kubo IPFS Cluster │    │ C. MCP++ durable     │
 │ cluster stack     │    │ external process     │    │ coordination store   │
 │                   │    │ wrappers             │    │ (Profile G)          │
 │ cluster/ package  │    │ ipfs_cluster_*       │    │ DurableCoordination  │
 │ + top-level       │    │ api/ctl/service/     │    │ Store + Event DAG    │
 │ cluster_* modules │    │ daemon/follow        │    │                      │
 └─────────┬─────────┘    └──────────┬───────────┘    └──────────┬───────────┘
           │                         │                           │
           ▼                         ▼                           ▼
   Roles, membership,         pinset / peer / service     claims, leases,
   Arrow state, CRDT,         binary lifecycle via        fencing tokens,
   daemon-enhanced            Kubo cluster tools          daemon health CIDs
   replication helpers
```

| Family | Primary modules | What it coordinates | Consistency style (observed) | Packaging / entry |
|---|---|---|---|---|
| **A. Bespoke kit cluster** | `ipfs_kit_py/cluster/*`, `cluster_coordinator.py`, `cluster_management.py`, `cluster_state*.py`, `cluster_state_sync.py`, `cluster_dynamic_roles.py`, `cluster_authentication.py`, `cluster_monitoring.py`, `enhanced_daemon_manager_with_cluster.py`, `p2p_workflow_coordinator.py`, `merkle_clock.py` | Node roles, membership, leader election, tasks, optional Arrow snapshot, CRDT gossip, content replication helpers | In-process leadership + heartbeats; CRDT/LWW vector clocks; Merkle clock for P2P workflows | Library import; package README examples; **no** dedicated console script solely for bespoke cluster |
| **B. Kubo IPFS Cluster wrappers** | `ipfs_cluster_api.py`, `ipfs_cluster_ctl.py`, `ipfs_cluster_service.py`, `ipfs_cluster_daemon_manager.py`, `ipfs_cluster_follow.py`, `ipfs_cluster_follow_daemon_manager.py` | External `ipfs-cluster-service` / `ipfs-cluster-ctl` / follow binaries and HTTP APIs | Whatever Kubo Cluster implements (CRDT consensus often configured by callers; not reimplemented here) | Resource/metadata constructors wrapping binaries; systemd unit templates present |
| **C. MCP++ coordination store** | `mcp_server/mcplusplus/coordination_storage.py` (`DurableCoordinationStore`), related Event DAG / delegation | Agent task claims, leases, fencing, expiring daemon health as CID-addressed artifacts | Immutable blocks authoritative; rebuildable SQLite indexes; fail-closed on CID mismatch | Used by MCP++ profiles; default dir `~/.local/share/ipfs_kit_py/mcppp_coordination` or `MCPPLUSPLUS_COORDINATION_DIR` |

**Adjacent (not a fourth control plane, but easy to conflate)**

| Surface | Role relative to cluster |
|---|---|
| `services/state_service.py` (`StateService`) | Lightweight **local** JSON/file state for CLI/MCP parity (`~/.ipfs_kit` buckets/pins/status). Not a multi-node cluster consensus store. |
| MCP `cluster_tools.cluster_status` | Thin tool that calls `get_cluster_status`; does not choose family A/B/C. |
| `fs_journal_replication.py` | Metadata replication for filesystem journal plane (data-plane adjacency; owned in depth by KDOC-014). |
| `multi_region_cluster.py` | Geographic region health / routing helper; not a full membership consensus implementation. |

### 2.1 Why this guide refuses a canonical default

Evidence against selecting one family as “the” production control plane without an ADR:

1. **Parallel import roots.** Family A is split between `ipfs_kit_py.cluster` (lazy package) and top-level `cluster_*` modules with **duplicate type names** and **incompatible constructors** (see [§8](#8-observed-api-and-constructor-mismatches-decisionfollow-up)).
2. **Family A package manager does not construct today.** Instantiating `ipfs_kit_py.cluster.cluster_manager.ClusterManager` raises `TypeError` against current `MetricsCollector` / `MembershipManager` signatures (verified at last-verified baseline).
3. **Family B is process-wrapper oriented.** It assumes external Kubo Cluster binaries; tests focus on daemon/follow/API unit paths, not a unified kit role model.
4. **Family C is MCP++ agent coordination.** Strong recovery tests (`tests/test_coordination_storage.py`) prove durable claim/lease storage, not kit master/worker task scheduling.
5. **Map and glossary already mark U-08 unresolved.** Selecting a default here would invent an ADR outcome.

**Follow-up:** KDOC-028 must present options, migration consequences, and required tests **without** this guide pre-picking a winner.

---

## 3. Roles and capabilities (Family A)

### 3.1 Role enumerations (do not assume one enum)

| Source | Roles | Converter |
|---|---|---|
| `cluster/role_manager.py` `NodeRole` | `master`, `worker`, `leecher`, `modular`, `local`, `gateway`, `observer` | `from_string` |
| `cluster_coordinator.py` `NodeRole` | `master`, `worker`, `leecher` only | `from_str` |
| `cluster/enhanced_daemon_manager_with_cluster.py` `NodeRole` | `master`, `worker`, `leecher` | priority via `get_priority` (master=0, worker=1, leecher=999) |

**Mismatch note:** Callers that assume a single `NodeRole` type or a single converter method (`from_string` vs `from_str`) will break across modules. This is part of the [API mismatch record](#8-observed-api-and-constructor-mismatches-decisionfollow-up).

### 3.2 Classic role semantics (shared intent)

| Role | Intended duties | Typical eligibility |
|---|---|---|
| **Master** | Orchestration, membership/leadership, task distribution, optional indexing/replication initiation | Highest leadership priority in daemon-enhanced path |
| **Worker** | Task execution, content processing/pinning, may receive replication | Leadership-eligible in some election helpers |
| **Leecher** | Consume content with minimal contribution | Not leadership-eligible in daemon-enhanced election |

Extended roles in `role_manager.NodeRole`:

| Role | Intent (from package README / capabilities map) |
|---|---|
| **Gateway** | HTTP gateway serving; not cluster management |
| **Observer** | Health/metrics only; minimal storage/processing |
| **Modular** | Full-featured development/testing profile |
| **Local** | Local-only; networking disabled |

### 3.3 Capabilities map (`role_capabilities`)

`ipfs_kit_py/cluster/role_manager.py` defines `role_capabilities` per role with:

- **Resource floors** (`min_memory_mb`, `min_storage_gb`, bandwidth, uptime, preferred cores)
- **Capability flags** (e.g. `cluster_management`, `dht_server`, `content_routing`, `task_distribution`, `metadata_indexing`, `persistent_storage`, `high_replication`)
- **IPFS config overrides** (routing type, datastore GC, swarm connmgr)

`RoleManager` supports auto-detect, role switching, and configuration callbacks. Dynamic switching also lives in top-level `ClusterDynamicRoles` (resource thresholds, upgrade/downgrade cooldowns). Dynamic role upgrade paths may call kit hooks such as `create_cluster_service(..., consensus="crdt")`—that path **bridges toward Family B** (Kubo Cluster service) rather than pure in-process Family A.

### 3.4 Authentication boundary (thin docs relative to code size)

`cluster_authentication.py` (`ClusterAuthManager`) provides TLS/UCAN-oriented peer auth scaffolding (`node_id`, `role`, `security_dir`, `cluster_id`, `security_config`). Trust-boundary documentation is thin relative to module size; operators must not assume production-hardened multi-tenant auth without reviewing this module and tests. Detailed threat modeling for transports remains KDOC-016 / security docs.

---

## 4. Membership, leadership, and task flow

### 4.1 Membership

**Package path:** `MembershipManager` in `cluster/distributed_coordination.py`

| Concern | Behavior |
|---|---|
| Inputs | `cluster_id`, `node_id`, `heartbeat_interval` (default 30s), `node_timeout` (default 90s), optional membership callback |
| State | `members`, `active_members`, `departed_members`, last heartbeat timestamps |
| Heartbeat | Background thread; `_send_heartbeat` is currently a **stub** (logs only; real pubsub not wired in this module) |
| Timeout | Active members without recent heartbeats → departure callback |

**Top-level path:** `ClusterCoordinator` embeds its own node registry (`NodeInfo` / `NodeStatus`), heartbeat interval (default 15s), and node timeout (default 60s) **without** requiring package `MembershipManager`.

These are parallel membership models, not a single shared service.

### 4.2 Leader election

| Implementation | Algorithm (observed) | Notes |
|---|---|---|
| `cluster/distributed_coordination.ClusterCoordinator` | Vote collection among active members; finalize and announce leader; leadership callback | Tied to membership manager when provided |
| `cluster_coordinator.ClusterCoordinator` | Master-oriented task scheduling; `is_master` / `current_leader` fields | Task queues and pubsub topic names |
| `enhanced_daemon_manager_with_cluster.LeaderElection` | Deterministic sort by role priority then node id; heartbeat health check; re-elect if unhealthy | Covered by `tests/test_cluster_services.py` |

No single election protocol is enforced across Family A modules.

### 4.3 Task distribution and P2P workflows

```text
Operator / API
    │
    ├─► package ClusterCoordinator.submit_task / update_task_status
    │       (in-memory queue + assignments; consensus proposals optional)
    │
    ├─► top-level ClusterCoordinator.create_task / cancel_task
    │       (Queue-based scheduler threads when start() called)
    │
    └─► P2PWorkflowCoordinator (+ MerkleClock)
            parse workflow tags → priority queue → peer ownership via select_task_owner
            state under ~/.ipfs_kit/p2p_workflows (default)
```

`merkle_clock.py` provides append-only hashed events with logical clocks and helpers (`select_task_owner`, Hamming distance) used by P2P workflow coordination. This plane is **orthogonal** to Arrow cluster state and to Kubo Cluster pinset consensus.

MCP tool surface for cluster is minimal: `cluster_tools.cluster_status` → `get_cluster_status` only.

---

## 5. State stores and Consistency models

This section records **what the code implements**, not a chosen global Consistency SLA.

### 5.1 Consistency summary (by plane)

| Plane | Mechanism | Conflict policy (default observed) | Authoritative? |
|---|---|---|---|
| Package membership/leader | Heartbeats + election votes in process memory | Last successful election; leader death restarts election | **Local process view only** (heartbeat send is stubbed) |
| Top-level coordinator registry | In-memory `nodes` / `tasks` dicts + optional sync thread | Master assigns work; worker reports results | Process-local unless bridged elsewhere |
| Arrow cluster state | PyArrow table schema; optional disk persistence under state path | Single-writer intent around `RLock`; Plasma IPC **disabled** | Candidate shared snapshot; **not** proven multi-writer safe across hosts |
| CRDT state sync | `VectorClock` + `StateCRDT` + `ClusterStateSync` | Default algorithm **`lww`** (last-write-wins); concurrent updates detected via clocks | In-memory CRDT with optional gossip setup on kit instance |
| Merkle clock / P2P workflow | Hash-linked events + logical clock | Ownership selection helpers; file-backed workflow state | Per-peer local clock + data dir; not global linearizability |
| MCP++ coordination store | CID-addressed immutable artifacts + SQLite indexes | Fencing tokens / lease expiry for claims | **Blocks authoritative**; indexes rebuildable (strong local recovery tests) |
| Kubo Cluster wrappers | External service consensus | Typically CRDT in upstream cluster (configured by service init) | External process authority when binaries run |
| FS journal metadata replication | `MetadataReplicationManager` | Default **`lww`** (see KDOC-014) | Journal plane, not cluster membership |

**Do not claim cluster-wide linearizability.** Across Family A, Consistency is best described as **per-plane best-effort coordination** with LWW for concurrent state maps and leader-based task assignment—not a single ACID multi-node store.

### 5.2 Arrow cluster state (snapshots)

`ArrowClusterState` (`cluster_state.py`) implements `ClusterStateInterface`:

| Aspect | Detail |
|---|---|
| Schema | `create_cluster_state_schema()` — `cluster_id`, `master_id`, `updated_at`, nested `nodes`, `tasks`, `content` (with providers/replication/pinned_at) |
| Constructor | `cluster_id`, `node_id`, `state_path` (default `~/.ipfs_cluster_state`), `memory_size` (1GB default for legacy Plasma), `enable_persistence` |
| Plasma / shared memory | **Disabled** due to pyarrow Plasma removal/deprecation; code logs that shared-memory functionality is disabled |
| Persistence | Load/save via Arrow/Parquet paths when enabled |
| Async twin | `cluster_state_anyio.ArrowClusterStateAnyIO` |
| External query helpers | `cluster_state_helpers.py` (get nodes/tasks/content, pandas export, topology helpers) |

`cluster_management.ClusterManager` optionally constructs `ArrowClusterState` when pyarrow imports succeed and registers the master node into state. Plasma-oriented access APIs remain in older code paths and must be treated as **legacy / non-functional** until reimplemented.

### 5.3 Vector clocks and CRDT-like paths

`cluster_state_sync.py`:

| Type | Responsibility |
|---|---|
| `VectorClock` | create / increment / merge / compare → before, after, concurrent, equal |
| `StateCRDT` | State dict + update log + sequence numbers; `consensus_algorithm` default `"lww"`; `detect_conflicts` + `resolve_conflict_lww` |
| `ClusterStateSync` | Kit-bound manager; initializes CRDT with `"lww"`; optional auto-sync thread and gossip topic setup from kit metadata |

`ClusterDynamicRoles` may request Kubo Cluster service init with `consensus="crdt"`—that is **upstream cluster CRDT**, not the in-process `StateCRDT` class. Document both; do not merge them into one mental model.

### 5.4 State store identity (unresolved)

| Candidate “cluster state” | Reality |
|---|---|
| `ArrowClusterState` | Columnar snapshot + helpers; Plasma path dead |
| `StateCRDT` / `ClusterStateSync` | Gossip/LWW map; separate from Arrow schema |
| `StateService` | Local CLI/MCP file state; not multi-node |
| `DurableCoordinationStore` | MCP++ Profile G claims/leases; different schema and purpose |

**Unresolved (U-08 / map §4):** which store is authoritative for “cluster state” in multi-node kit deployments. This guide lists candidates only.

---

## 6. Replication

### 6.1 Content replication (daemon-enhanced Family A)

`cluster/enhanced_daemon_manager_with_cluster.ReplicationManager`:

| Rule | Behavior |
|---|---|
| Initiate | **Master only** (`can_initiate_replication`) |
| Receive | Master or worker (`can_receive_replication`) |
| API | `async replicate_content(cid, target_peers, priority=1)` with retry bookkeeping |
| Coupling | Optional `ipfs_kit_instance` for actual pin/get operations |

Covered by unit tests in `tests/test_cluster_services.py` (`TestReplicationManager`). Practical demo orchestration lives in `cluster/practical_cluster_setup.py`.

### 6.2 Pinset replication via Kubo Cluster (Family B)

Wrappers expose service/ctl/follow and HTTP API clients. Operators running real `ipfs-cluster-service` get pinset replication and peer membership from **upstream** IPFS Cluster, not from `ReplicationManager`. Dynamic role transitions that call `create_cluster_service` / `create_cluster_ctl` are bridge points into this family.

### 6.3 Metadata / journal replication (data-plane adjacency)

`fs_journal_replication.MetadataReplicationManager` (detail in KDOC-014):

- Configurable levels (single, quorum, progressive, etc.)
- Default conflict resolution **LWW**
- Auto recovery hooks and checkpoint replication
- Base path default `~/.ipfs_kit/fs_replication`

Treat this as **filesystem metadata durability scaling**, not as a substitute for membership consensus.

### 6.4 MCP++ artifact replication

`DurableCoordinationStore` can mirror blocks to an optional Helia/IPFS backend before return; local immutable blocks remain authority. Index compaction archives derived rows without deleting artifact blocks. See `docs/coordination-storage.md`.

---

## 7. Health, partition, and recovery behavior

### 7.1 Health monitoring (Family A)

| Component | Role |
|---|---|
| `cluster/monitoring.MetricsCollector` | Time-series metrics; optional `metrics_dir`; retention days |
| `cluster/monitoring.ClusterMonitor` | Periodic checks; alert callback; membership-change hooks from package manager |
| `cluster_monitoring.ClusterMonitoring` / `ClusterDashboard` | Kit-instance-bound monitoring and dashboard helpers |
| Leader heartbeat checks | `LeaderElection.check_leader_health` / `trigger_election_if_needed` |
| MCP++ `daemon_health` index | Expiring health artifacts by peer DID |

### 7.2 Partition behavior (observed / inferred)

| Scenario | Observed behavior | Gap |
|---|---|---|
| Member heartbeat timeout | Mark departed; membership callback | Package heartbeat **send** is stubbed—real multi-host detection needs a transport bridge |
| Leader unhealthy | Daemon-enhanced path re-elects by priority | Top-level coordinator may diverge until restarted/synced |
| Concurrent CRDT updates | Vector clock marks concurrent; LWW resolves | No multi-phase commit; last writer wins may drop concurrent intent |
| Arrow state multi-process | Plasma disabled; disk persistence only | No zero-copy IPC across processes as originally designed |
| MCP++ corrupt SQLite | Preserve `corrupt-*` file; rebuild indexes from blocks | Strong local recovery; not a cluster membership partition solver |
| Multi-region endpoints | `multi_region_cluster.RegionStatus` healthy/degraded/unavailable | Routing helper; not full CAP analysis |

### 7.3 Recovery order (per plane—compose carefully)

```text
Family A process restart
  1. Reconstruct RoleManager / coordinator from config (no single shared bootstrap)
  2. If Arrow persistence enabled: load state_path tables
  3. If ClusterStateSync used: re-init CRDT; rejoin gossip if kit provides it
  4. Re-run leader election if acting as master-capable node

Family B
  1. Restart ipfs-cluster-service / follow via daemon managers
  2. Rely on upstream cluster state recovery

Family C
  1. DurableCoordinationStore.__init__ → open DB or rebuild from blocks/
  2. recover(rebuild=...) when index empty but blocks present
  3. get() may repair missing local block from backend after CID verify
```

There is **no** repository-wide recovery orchestrator that sequences A+B+C.

---

## 8. Observed API and constructor mismatches (decision/follow-up)

These mismatches are **rank-1 evidence** for KDOC-028 and for not selecting Family A package APIs as production defaults without repair.

### 8.1 Duplicate types with incompatible constructors

| Symbol | Location A | Location B | Incompatibility |
|---|---|---|---|
| `ClusterManager` | `cluster/cluster_manager.py` | `cluster_management.py` | Same ctor *parameter names* but **different dependencies and public methods**. Package wires RoleManager + MembershipManager + package ClusterCoordinator; top-level wires top-level ClusterCoordinator + Arrow state + libp2p. Shared public methods: only a subset (`start`, `stop`, `get_cluster_status`, …). |
| `ClusterCoordinator` | `cluster/distributed_coordination.py` | `cluster_coordinator.py` | Package: `(cluster_id, node_id, is_master, …)`. Top-level: `(node_id, role, peer_id, config, …)`. Different public method sets (`submit_task` vs `create_task`, etc.). |
| `NodeRole` | `role_manager` (7 values, `from_string`) | `cluster_coordinator` (3 values, `from_str`) | Enum members and converter names differ. Third copy in `enhanced_daemon_manager_with_cluster`. |
| `MembershipManager` | Defined in `distributed_coordination.py` | **Call site** in `cluster/cluster_manager.py` | Call passes unsupported kwargs (below). |

### 8.2 Confirmed constructor call-site failures (package `ClusterManager`)

Verified at last-verified baseline by importing and constructing:

```text
ClusterManager(node_id=..., role="master")
  → MetricsCollector.__init__() got an unexpected keyword argument 'role'
```

Call site in `cluster/cluster_manager.py` vs definitions:

| Callee | Call site kwargs | Actual `__init__` parameters | Result |
|---|---|---|---|
| `MetricsCollector` | `node_id`, **`role`**, `collection_interval` | `node_id`, `metrics_dir`, `collection_interval`, `retention_days` | **TypeError** on `role` |
| `MembershipManager` | `cluster_id`, `node_id`, **`role`**, **`peer_id`**, `heartbeat_interval`, **`membership_timeout`**, callback | `cluster_id`, `node_id`, `heartbeat_interval`, **`node_timeout`**, callback | **TypeError** on `role` (and would fail on `peer_id` / `membership_timeout` vs `node_timeout`) |

Standalone check:

```text
MembershipManager(..., role=..., peer_id=..., membership_timeout=...)
  → TypeError: unexpected keyword argument 'role'
```

**Implication:** The packaged “unified” `cluster.ClusterManager` composition path is **not constructible** against its sibling modules as committed. Treat README examples that import package managers as **aspirational / stale** until repaired. Prefer citing concrete working subsets (e.g. tests that import `enhanced_daemon_manager_with_cluster` types) when writing operator procedures.

### 8.3 Method surface divergence (illustrative)

| Class | Package-only public methods (examples) | Top-level-only public methods (examples) |
|---|---|---|
| `ClusterManager` | `submit_task`, `propose_configuration_change`, `get_node_roles`, `get_metrics` | `create_task`, `cancel_task`, `get_nodes`, `get_tasks`, `get_content`, `access_state_from_external_process`, … |
| `ClusterCoordinator` | `submit_task`, `join_cluster`, `initiate_election`, `propose_change`, `vote_on_proposal`, … | `start`, `stop`, `create_task`, `cancel_task`, `get_nodes`, `get_cluster_status`, … |

Shared names do not imply shared semantics.

### 8.4 Plasma / Arrow documentation drift

- Code and comments still describe Plasma shared memory and C Data Interface access patterns.
- Runtime disables Plasma and warns on init.
- Top-level manager still references plasma socket fields in some status paths.

### 8.5 Decision / follow-up (owned by KDOC-028)

| Item | Required follow-up |
|---|---|
| Control-plane authority | ADR 0008: choose or explicitly multi-track Family A / B / C with operator decision tree |
| Family A API unification | Align constructors (role/peer_id/timeout names), unify `NodeRole`, pick one `ClusterManager` / `ClusterCoordinator` or namespace them permanently |
| Package manager green path | Fix MetricsCollector/MembershipManager call sites; add construction + start/stop integration tests under default discovery |
| State identity | Decide Arrow vs CRDT vs MCP++ store vs StateService roles; document single “authoritative cluster state” or explicitly layered authorities |
| Heartbeat transport | Wire or delete stub `_send_heartbeat`; document required libp2p/pubsub dependency |
| Auth | Threat model for `ClusterAuthManager` relative to chosen plane |

This guide **records** mismatches; it does **not** implement fixes (out of edit scope for KDOC-015).

---

## 9. Component map and source-of-truth paths

### 9.1 Family A — package `ipfs_kit_py/cluster/`

| Module | Responsibility |
|---|---|
| `__init__.py` | Lazy exports (`ClusterManager`, `ClusterCoordinator`, `MembershipManager`, `RoleManager`, daemon-enhanced types, …) to avoid import cycles |
| `role_manager.py` | Extended roles, capabilities, resource detection, role switching |
| `distributed_coordination.py` | Membership + package coordinator (election, tasks, proposals) |
| `cluster_manager.py` | Intended composition façade (**currently non-constructible**—§8) |
| `monitoring.py` | MetricsCollector + ClusterMonitor |
| `enhanced_daemon_manager_with_cluster.py` | LeaderElection, ReplicationManager, IndexingService, EnhancedDaemonManager |
| `practical_cluster_setup.py` | Demo multi-node orchestration script |
| `utils.py` | Shared helpers (e.g. GPU info) |

### 9.2 Family A — top-level modules

| Module | Responsibility |
|---|---|
| `cluster_coordinator.py` | Alternate coordinator + 3-role enum + task/node registries |
| `cluster_management.py` | Alternate ClusterManager + Arrow + libp2p bridge |
| `cluster_state.py` / `_anyio` / `_helpers` | Arrow state + query helpers |
| `cluster_state_sync.py` | VectorClock, StateCRDT, ClusterStateSync |
| `cluster_dynamic_roles.py` | Resource-driven role transitions; may start Kubo Cluster service |
| `cluster_authentication.py` | TLS/UCAN auth manager |
| `cluster_monitoring.py` | Kit-bound monitoring/dashboard |
| `merkle_clock.py` / `p2p_workflow_coordinator.py` | Causal workflow coordination |
| `multi_region_cluster.py` | Multi-region health/routing helper |

### 9.3 Family B — Kubo wrappers

| Module | Responsibility |
|---|---|
| `ipfs_cluster_api.py` | HTTP clients for cluster and follow APIs; CTL wrappers |
| `ipfs_cluster_ctl.py` | `ipfs_cluster_ctl` resource/metadata wrapper |
| `ipfs_cluster_service.py` | Service lifecycle wrapper |
| `ipfs_cluster_daemon_manager.py` | Config + async start/stop/status/restart helpers |
| `ipfs_cluster_follow*.py` | Follow-mode service management |

### 9.4 Family C — MCP++ coordination

| Module | Responsibility |
|---|---|
| `mcp_server/mcplusplus/coordination_storage.py` | `DurableCoordinationStore` |
| `docs/coordination-storage.md` | Operator-facing durability model |
| `tests/test_coordination_storage.py` | Recovery, fencing, retention |

---

## 10. Design rationale, trade-offs, and rejected alternatives

**Accepted (local to modules, not global product policy):** Role-based specialization (master/worker/leecher) is a recurring product concept across package README, deployment guide, and daemon-enhanced managers.

**Accepted:** LWW + vector clocks are used where concurrent map updates are expected (`StateCRDT`, journal metadata replication), trading strong Consistency for availability of merges.

**Accepted:** MCP++ separates immutable CID blocks from rebuildable indexes (fail-closed integrity).

**Inferred:** Parallel Family A trees (`cluster/` package vs top-level `cluster_*`) grew as incremental features rather than a single modular redesign—hence duplicate names and mismatched constructors.

**Inferred:** Plasma was abandoned due to upstream Arrow removal; disk Arrow tables remain as a partial replacement without multi-process IPC.

**Proposed (not accepted):** ADR 0008 selects production control-plane authority and migration policy. Status: **not authored** as of this baseline.

**Unknown / maintainer confirmation needed:** Whether any production deployment standardizes on package README examples despite non-constructible `ClusterManager`; which daemon manager (enhanced / intelligent / cluster-enhanced) is lifecycle authority (map U-09 adjacent / daemon manager unresolved).

**Rejected for this guide:** Declaring “use `ipfs_kit_py.cluster.ClusterManager` as the canonical API” without fixing §8—would violate acceptance criteria and mislead operators.

**Rejected for this guide:** Treating Kubo Cluster wrappers and bespoke roles as the same subsystem.

---

## 11. Unresolved owner decisions

Carried from [`SOURCE_OF_TRUTH_MAP.md`](SOURCE_OF_TRUTH_MAP.md); this guide must not invent outcomes.

| ID | Topic | Impact on this guide |
|---|---|---|
| **U-08** | Bespoke cluster vs Kubo Cluster wrappers vs MCP++ coordination authority | All “defaults” stay candidate-only; ADR 0008 owns the decision |
| **State store identity** (map §4) | Arrow vs CRDT vs StateService vs DurableCoordinationStore | Consistency claims are per-plane only |
| **API/constructor mismatches** (§8) | Unify or permanently namespace duplicate types | Package manager unusable until fixed |
| **Daemon manager authority** | enhanced / intelligent / cluster-enhanced | Lifecycle composition for multi-node deploys unclear |
| **Auth trust boundary** | `ClusterAuthManager` production posture | Security claims limited |

---

## 12. Tests and fixtures that verify the behavior

Prefer **default pytest discovery**. Workflow `.github/workflows/cluster-tests.yml` may assume network/services—mark carefully when claiming CI green.

### 12.1 Test map (rank-1 evidence)

| Concern | Focused tests |
|---|---|
| Daemon-enhanced roles, leader election, replication, indexing | `tests/test_cluster_services.py` |
| Merkle clock, task ownership, P2P workflow coordinator | `tests/test_p2p_workflow.py` |
| MCP++ DurableCoordinationStore recovery / fencing / retention | `tests/test_coordination_storage.py` |
| Kubo cluster daemon manager startup | `tests/unit/test_cluster_startup.py` |
| Cluster follow enhanced | `tests/unit/test_cluster_follow_enhanced.py` |
| Cluster HTTP API unit | `tests/unit/test_cluster_api.py` |
| Cluster backends / health monitor adjacency | `tests/unit/test_cluster_backends.py`, `tests/unit/test_health_monitor_cluster.py` |
| VFS/metadata replication edge | `tests/test_vfs_replication.py` (data-plane; see KDOC-014) |

### 12.2 Gaps (do not over-claim)

- No default-discovery test was observed that constructs package `cluster.ClusterManager` successfully end-to-end against live membership heartbeats.
- Package vs top-level API parity is **not** enforced by tests (mismatch persists).
- Real multi-host partition/healing for Family A is under-specified relative to code comments.

### 12.3 Offline validation for this document

```bash
test -s docs/architecture/CLUSTER_COORDINATION.md \
  && rg -q "Consistency" docs/architecture/CLUSTER_COORDINATION.md
```

Broader claim re-check (optional):

```bash
# Competing families still present
rg -n "class (ClusterManager|ClusterCoordinator|MembershipManager|ArrowClusterState|StateCRDT|ReplicationManager|DurableCoordinationStore)" \
  ipfs_kit_py/cluster/cluster_manager.py \
  ipfs_kit_py/cluster_management.py \
  ipfs_kit_py/cluster/distributed_coordination.py \
  ipfs_kit_py/cluster_coordinator.py \
  ipfs_kit_py/cluster_state.py \
  ipfs_kit_py/cluster_state_sync.py \
  ipfs_kit_py/cluster/enhanced_daemon_manager_with_cluster.py \
  ipfs_kit_py/mcp_server/mcplusplus/coordination_storage.py

# Confirmed mismatch still present (call site kwargs)
rg -n "role=self.initial_role|membership_timeout=" ipfs_kit_py/cluster/cluster_manager.py
rg -n "def __init__" -A6 ipfs_kit_py/cluster/distributed_coordination.py | head -40
rg -n "def __init__" -A6 ipfs_kit_py/cluster/monitoring.py | head -20
```

---

## 13. Change triggers and last-verified baseline

Re-verify this guide when any of the following change:

| Trigger | Sections to re-check |
|---|---|
| Constructor alignment of `ClusterManager` / `MembershipManager` / `MetricsCollector` | §4, §8, §11 |
| Unification or deletion of duplicate `NodeRole` / coordinator modules | §3, §8 |
| Plasma re-enablement or Arrow state redesign | §5.2, §7 |
| CRDT algorithm defaults or gossip transport wiring | §5.1, §5.3 |
| Kubo Cluster wrapper public APIs or daemon manager authority | §2, §6.2, §9.3 |
| MCP++ coordination schema / recovery | §2 Family C, §5.1, §7.3 |
| Acceptance of ADR 0008 | Rewrite §2 and §11 as Accepted; remove “do not select” framing only if ADR says so |
| New focused tests covering package manager construction | §12 |
| Heartbeat/pubsub real transport implementation | §4.1, §7.2 |

| Baseline field | Value |
|---|---|
| Last verified | 2026-08-03 |
| Tree baseline | `6fc55f0918a0f45e04b37727b45c1a1f5aaf9322` |
| Evidence sources | Static inspection of modules in §9; runtime TypeError on package `ClusterManager` / `MembershipManager`; default-discovery tests in §12; `SOURCE_OF_TRUTH_MAP.md` §4; glossary cluster-role entry |

---

## 14. Operator orientation cheat sheet

### 14.1 “I need multi-node pin coordination with upstream IPFS Cluster”

Prefer **Family B** wrappers and external binaries; do not assume bespoke roles replace pinset consensus.

### 14.2 “I need kit master/worker task distribution in-process”

Use **documented Family A subsets that tests actually exercise** (e.g. daemon-enhanced leader/replication types). Do **not** assume package `ClusterManager()` works until §8 is fixed. Treat top-level `cluster_management.ClusterManager` as a parallel stack, not a drop-in.

### 14.3 “I need MCP++ agent claim/lease durability”

Use **Family C** `DurableCoordinationStore` and `docs/coordination-storage.md`. This is not a replacement for Kubo Cluster pinsets or kit role managers.

### 14.4 “I need Consistency guarantees”

Read [§5.1](#51-consistency-summary-by-plane). Ask which plane must be consistent. There is no single cluster-wide Consistency mode switch.

---

## 15. Related documents

| Document | Relationship |
|---|---|
| [`SOURCE_OF_TRUTH_MAP.md`](SOURCE_OF_TRUTH_MAP.md) §4 | Evidence map this guide expands |
| [`GLOSSARY.md`](GLOSSARY.md) | Cluster role and control-plane vocabulary |
| [`CONTENT_METADATA_VFS.md`](CONTENT_METADATA_VFS.md) | Journal/metadata replication and LWW adjacency |
| [`RUNTIME_AND_ENTRYPOINTS.md`](RUNTIME_AND_ENTRYPOINTS.md) | Process entry points (MCP++, CLI) |
| [`docs/coordination-storage.md`](../coordination-storage.md) | MCP++ DurableCoordinationStore durability model |
| [`docs/guides/CLUSTER_DEPLOYMENT_GUIDE.md`](../guides/CLUSTER_DEPLOYMENT_GUIDE.md) | Deployment narrative (roles/docker); verify against §8 before trusting code samples |
| [`docs/features/P2P_WORKFLOW_GUIDE.md`](../features/P2P_WORKFLOW_GUIDE.md) | P2P workflow operator guide |
| `ipfs_kit_py/cluster/README.md` | Package feature narrative; may lag constructible APIs |
| Planned ADR 0008 | **KDOC-028** cluster control-plane authority decision |
| Planned `NETWORK_TRANSPORTS.md` | KDOC-016 transport boundaries |

---

## 16. End-to-end flow sketches (non-normative composition)

### 16.1 Intended package composition (currently broken at construct)

```text
RoleManager → MembershipManager → ClusterCoordinator → ClusterMonitor
                     │
                     └── ClusterManager.start() would start components
```

Blocked by §8.2 until call sites match signatures.

### 16.2 Top-level management + Arrow (parallel stack)

```text
ClusterManager (cluster_management)
  ├─ ClusterCoordinator (top-level; role/peer_id/config)
  ├─ ArrowClusterState (optional; pyarrow)
  └─ IPFSLibp2pPeer bridge (optional)
```

### 16.3 Daemon-enhanced content replication demo path

```text
EnhancedDaemonManager
  ├─ LeaderElection.elect_leader()
  ├─ ReplicationManager.replicate_content(cid, peers)
  └─ IndexingService (master-oriented)
```

### 16.4 MCP++ claim lifecycle (Family C)

```text
put Profile G TaskClaim artifact (CID)
  → index claims
  → accept lease with fencing_token
  → expire/resolve
  → on crash: rebuild indexes from blocks/
```
