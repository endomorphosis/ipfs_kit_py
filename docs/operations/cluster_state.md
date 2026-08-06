# Cluster state (operations)

| Field | Value |
|---|---|
| Document class | Operator runbook (current-operations) |
| Status | active |
| Last verified | 2026-08-04 |
| Owner / task | KDOC-036 |
| Goal id | KDOC-G042 |
| Authority | **No authoritative multi-node “cluster state” is selected.** See [ADR-0008](../architecture/decisions/0008-cluster-control-plane-authority.md) (**Proposed**), [CLUSTER_COORDINATION.md](../architecture/CLUSTER_COORDINATION.md) §5, and map **U-08**. |
| Companion ops | [cluster_management.md](cluster_management.md), [cluster_monitoring.md](cluster_monitoring.md) |

This runbook explains how to **inspect, persist, and recover** state surfaces that appear in the kit tree. It lists **candidates** and **per-plane** behavior. It does **not** declare a production multi-node source of truth.

**Acceptance rule:** every inspection/command path is tagged with **implementation family**, **state plane**, and **prerequisites**. Unresolved authority is never converted into a production recommendation.

---

## 1. State store identity (unresolved)

Several independent stores answer “what is the cluster state?” depending on who you ask. They are **not** interchangeable.

| Candidate store | Family / plane | What it holds | Authoritative? |
|---|---|---|---|
| `ArrowClusterState` (`cluster_state.py`) | A — Arrow snapshot | Columnar table: cluster metadata, nodes, tasks, content | **Candidate** shared snapshot; process-local writer intent; **not** proven multi-writer safe across hosts |
| `StateCRDT` / `ClusterStateSync` (`cluster_state_sync.py`) | A — CRDT map | Dict state + vector clocks + update log; default consensus **`lww`** | In-memory CRDT with optional gossip setup; **separate** from Arrow schema |
| Coordinator in-memory registries | A — process registry | Nodes/tasks dicts on package or top-level coordinator | Process-local unless bridged |
| Package membership/leader memory | A — membership | Members, heartbeats, votes | Local process view; package heartbeat **send** stubbed |
| `StateService` (`services/state_service.py`) | Adjacent — local CLI/MCP | JSON/file buckets under `~/.ipfs_kit` | **Local only**; not multi-node consensus |
| `DurableCoordinationStore` | C — MCP++ | CID-addressed claims/leases/health artifacts + SQLite indexes | **Blocks authoritative** for Profile G domain only |
| Kubo Cluster service state | B — external | Pinset / peer state in upstream processes | External authority when binaries run |
| Merkle clock / P2P workflow files | A — workflow | Causal events under `~/.ipfs_kit/p2p_workflows` (default) | Per-peer local clock + data dir |
| FS journal metadata replication | Data plane adjacency | Journal metadata durability (`fs_journal_replication`) | Journal plane, not membership |

**Do not claim cluster-wide linearizability.** Across Family A, consistency is best described as **per-plane best-effort coordination** with LWW for concurrent maps and leader-based task assignment—not a single ACID multi-node store.

Architecture reference: [CLUSTER_COORDINATION.md §5](../architecture/CLUSTER_COORDINATION.md).

---

## 2. Prerequisites by state plane

| Plane | Prerequisites | Notes |
|---|---|---|
| Arrow snapshot | `pyarrow` installed; writable `state_path` | Optional pandas for DataFrame helpers |
| Arrow async twin | `cluster_state_anyio` + anyio stack | Same schema intent |
| CRDT sync | Import `cluster_state_sync`; optional kit gossip/pubsub | Default algorithm `"lww"` |
| Top-level manager state bridge | Constructed `cluster_management.ClusterManager` with Arrow init success | Parallel stack to package façade |
| Package manager → Arrow | Package manager constructible | Currently **blocked** for package façade (see management runbook §3) |
| State helpers (disk query) | Path to persisted Arrow/Parquet state | Helpers read files; do not require live manager |
| Family C store | MCP++ coordination directory | See [coordination-storage.md](../coordination-storage.md) |
| Family B pinset state | Running `ipfs-cluster-service` + ctl/API | Upstream tooling |

---

## 3. Arrow cluster state (Family A — snapshot plane)

### 3.1 Module map

| Module | Role |
|---|---|
| `ipfs_kit_py/cluster_state.py` | `ClusterStateInterface`, `ArrowClusterState`, schema factory |
| `ipfs_kit_py/cluster_state_anyio.py` | Async twin |
| `ipfs_kit_py/cluster_state_helpers.py` | Offline/path-based query helpers |
| `cluster_management.ClusterManager._init_arrow_state` | Optional construction when `pyarrow` imports succeed |

Related narrative docs (deeper schema notes): [cluster_arrow_state.md](cluster_arrow_state.md), [cluster_state_helpers.md](cluster_state_helpers.md), [cluster_state_sync.md](cluster_state_sync.md). Prefer **this** runbook for family tags and authority limits.

### 3.2 Constructor and defaults

| Parameter | Default / behavior |
|---|---|
| `cluster_id` | Required string |
| `node_id` | Required; master identification for writer intent |
| `state_path` | Default `~/.ipfs_cluster_state` (expanded); top-level manager may use config `state_path` under IPFS path |
| `memory_size` | 1GB default — historical Plasma sizing; **Plasma disabled** |
| `enable_persistence` | `True` → load/save via Arrow/Parquet paths under `state_path` |

On init, code logs that **Plasma shared memory is disabled** due to pyarrow deprecation/removal. Treat Plasma sockets, object IDs, and “zero-copy C Data IPC across processes” in older comments/status fields as **legacy / non-functional** until reimplemented.

### 3.3 Schema (summary)

`create_cluster_state_schema()` defines a table with nested lists (conceptual fields):

| Area | Fields (intent) |
|---|---|
| Cluster metadata | `cluster_id`, `master_id`, `updated_at` |
| Nodes | id, role, status, peers, capabilities, resource gauges |
| Tasks | id, type, status, timestamps, assigned_to, resource needs, I/O CIDs |
| Content | cid, size, providers, pin flags, timestamps |

Exact field types live in `cluster_state.py`—do not invent columns in automation.

### 3.4 Core APIs (family-tagged)

| API | Family / plane | Prerequisites | Status |
|---|---|---|---|
| `ArrowClusterState(...)` | A — Arrow | `pyarrow`; writable path | candidate |
| `get_state()` | A — Arrow | Initialized instance | candidate |
| `add_node` / `update_node` / node queries | A — Arrow | Writer access; `RLock` | candidate |
| `add_task` / `update_task` / `assign_task` | A — Arrow | Writer access | candidate |
| Content update helpers | A — Arrow | Writer access | candidate |
| `get_c_data_interface()` | A — Arrow | Instance | **partial / legacy fields** (Plasma values may be empty/stale) |
| `access_via_c_data_interface(state_path)` (static) | A — Arrow helpers | Path with persisted state | candidate / disk-based |
| Top-level `get_state_interface_info()` | A-toplevel + Arrow | Manager with `state_manager` | candidate / partial |

### 3.5 Direct usage example (lab only)

```python
# Family: A — Arrow snapshot | Status: candidate | Not multi-host authority
from ipfs_kit_py.cluster_state import ArrowClusterState

state = ArrowClusterState(
    cluster_id="lab-cluster",
    node_id="master-1",
    state_path="/tmp/lab_cluster_state",
    enable_persistence=True,
)

# Mutations are local to this process's table (+ disk if persistence succeeds)
state.add_node(
    node_id="worker-1",
    peer_id="12D3KooW...",
    role="worker",
    address="",
    resources={"cpu_count": 4, "memory_total": 8 * 1024**3},
    capabilities=["gpu"],
)
table = state.get_state()  # pyarrow.Table
```

**Do not** treat a single master disk directory as HA shared state without an accepted replication/authority story.

---

## 4. Path-based inspection with helpers (Family A — offline query)

`cluster_state_helpers.py` reads **persisted** state from a path. Prefer helpers for operator inspection when no live manager is available.

| Helper | Purpose | Prerequisites | Status |
|---|---|---|---|
| `get_state_path_from_metadata(base_dir=None)` | Resolve path from kit metadata conventions | Optional base dir | candidate |
| `get_cluster_state(state_path)` | Load Arrow table | Path exists; pyarrow | candidate |
| `get_cluster_state_as_dict` / `get_cluster_metadata` | Dict views | Loaded state | candidate |
| `get_all_nodes` / `get_node_by_id` / `find_nodes_by_role` / `find_nodes_by_capability` / `find_nodes_with_gpu` | Node queries | Path | candidate |
| `get_all_tasks` / `get_task_by_id` / `find_tasks_by_status` / `find_tasks_by_type` / `find_tasks_by_node` | Task queries | Path | candidate |
| `find_tasks_by_resource_requirements` / `find_available_node_for_task` | Placement heuristics | Path + task ids | experimental heuristics |
| `get_all_content` / `find_content_by_cid` / `find_content_by_provider` / `find_orphaned_content` | Content queries | Path | candidate |
| `get_cluster_status_summary` / `get_network_topology` | Summaries | Path | candidate |
| `get_task_execution_metrics` / `estimate_time_to_completion` | Derived metrics | Path | experimental estimates |
| `get_cluster_state_as_pandas` | Split DataFrames | pandas + path | candidate |
| `export_state_to_json(state_path, output_path)` | Export snapshot | Writable output | candidate |
| `connect_to_state_store(state_path)` | Legacy shared-memory connect attempt | Path | **legacy / non-functional** for Plasma; inspect return carefully |

Example:

```python
# Family: A — Arrow helpers | Status: candidate | Offline inspection
from ipfs_kit_py.cluster_state_helpers import (
    get_cluster_status_summary,
    find_nodes_by_role,
    find_tasks_by_status,
    export_state_to_json,
)

state_path = "/path/to/cluster_state"  # directory used by ArrowClusterState
summary = get_cluster_status_summary(state_path)
workers = find_nodes_by_role(state_path, "worker")
pending = find_tasks_by_status(state_path, "pending")
export_state_to_json(state_path, "/tmp/cluster_state_export.json")
```

---

## 5. CRDT / vector-clock sync (Family A — map plane)

| Type | Responsibility | Default |
|---|---|---|
| `VectorClock` | create / increment / merge / compare → before, after, concurrent, equal | — |
| `StateCRDT` | State dict + update log + sequence numbers; `detect_conflicts` + `resolve_conflict_lww` | `consensus_algorithm="lww"` |
| `ClusterStateSync` | Kit-bound manager; optional auto-sync thread and gossip topic from kit metadata | Initializes CRDT with `"lww"` |

**Important distinctions:**

- In-process `StateCRDT` is **not** the same as Kubo Cluster `consensus="crdt"` used when dynamic roles start Family B services.
- CRDT maps are **not** automatically the same object as the Arrow table schema.
- Concurrent updates: vector clocks mark concurrency; LWW may drop concurrent intent.

Operator posture while ADR-0008 is Proposed: treat CRDT sync as **experimental coordination aid**, not production multi-master database semantics.

See also [cluster_state_sync.md](cluster_state_sync.md) for narrative detail; keep family tags from this runbook.

---

## 6. Family C — DurableCoordinationStore (domain-scoped)

| Aspect | Detail |
|---|---|
| Family | **C** |
| Purpose | Agent task claims, leases, fencing tokens, expiring daemon health as CID artifacts |
| Authority model | Immutable blocks authoritative; indexes rebuildable; fail-closed on CID mismatch |
| Default location | `MCPPLUSPLUS_COORDINATION_DIR` or kit share default under MCP++ |
| Recovery | Open store → rebuild indexes from `blocks/` when empty/corrupt → optional backend fetch after CID verify |
| Tests | `tests/test_coordination_storage.py` |
| Ops guide | [coordination-storage.md](../coordination-storage.md) |

**Do not** use Family C as:

- Kit master/worker membership registry
- Pinset consensus
- Arrow schema replacement for node/task tables

---

## 7. Family B — external cluster state

Pinset and peer membership for real multi-node pinning live in **upstream IPFS Cluster** when Family B binaries run. Kit modules wrap lifecycle and HTTP/ctl; they do not reimplement consensus.

| Operation class | Where to look |
|---|---|
| Service start/status/stop | `ipfs_cluster_daemon_manager`, `ipfs_cluster_service` |
| Pin / peer ctl | `ipfs_cluster_ctl`, `ipfs_cluster_api` |
| Follow mode | `ipfs_cluster_follow*` |

**Prerequisites:** binaries, secrets, bootstrap peers, network. **Status:** wrapper / external-process authority.

---

## 8. Local StateService (adjacent)

`StateService` stores lightweight local JSON/file state for CLI/MCP parity (buckets, pins, status under `~/.ipfs_kit`). 

| Use | Do not use |
|---|---|
| Single-host CLI/MCP continuity | Multi-node cluster consensus |
| Local operational bookmarks | Authoritative task assignment across hosts |

---

## 9. Consistency summary (by plane)

| Plane | Mechanism | Conflict policy (default observed) | Authoritative? |
|---|---|---|---|
| Package membership/leader | Heartbeats + election votes in memory | Last successful election | Local process view |
| Top-level coordinator registry | In-memory nodes/tasks + optional sync thread | Master assigns; workers report | Process-local unless bridged |
| Arrow cluster state | PyArrow table; optional disk | Single-writer intent around `RLock` | Candidate snapshot |
| CRDT state sync | Vector clocks + `StateCRDT` | **`lww`** | In-memory (+ optional gossip) |
| Merkle / P2P workflow | Hash-linked events + logical clock | Ownership helpers | Per-peer local |
| MCP++ coordination | CID blocks + indexes | Fencing / lease expiry | Blocks for Profile G |
| Kubo Cluster wrappers | External service | Upstream (often CRDT) | External when running |
| FS journal metadata | `MetadataReplicationManager` | Default LWW | Journal plane |

---

## 10. Persistence, backup, and recovery

### 10.1 Arrow disk path

When `enable_persistence=True`:

1. Ensure `state_path` is on durable storage for that **single** writer host.
2. Back up the directory as a point-in-time snapshot (table files / parquet).
3. On restore, instantiate `ArrowClusterState` with the same `cluster_id` / path and confirm `get_state()` row counts via helpers.
4. Reconcile live coordinator memory separately—disk Arrow load does **not** automatically repopulate all Family A in-memory registries.

### 10.2 CRDT plane

1. Re-init `ClusterStateSync` / `StateCRDT`.
2. Rejoin gossip only if kit metadata/transport provides it.
3. Expect LWW merge of concurrent updates—not full history preservation.

### 10.3 Family C

```text
DurableCoordinationStore.__init__
  → open DB or rebuild from blocks/
  → recover(rebuild=...) when index empty but blocks present
  → get() may repair missing local block from backend after CID verify
```

### 10.4 Family B

Restart service/follow via daemon managers; trust upstream recovery. Kit wrappers do not replace cluster state DB repair procedures from IPFS Cluster documentation.

### 10.5 Cross-plane note

There is **no** single “restore the cluster” button that sequences A+B+C. Compose recovery **per plane** after identifying which family was actually in use.

---

## 11. Python 3.12 / test compatibility notes

PyArrow `Schema` objects are immutable. Test helpers avoid patching schema equality incorrectly; `create_test_task_data` in `cluster_state.py` builds type-correct task dicts for tests. Operators running unit suites should prefer project fixtures rather than hand-rolled MagicMock schemas.

---

## 12. Scoped validation

| Concern | Evidence |
|---|---|
| Arrow / helpers unit coverage | `tests/unit/core/test_cluster_state.py`, `test_cluster_state_helpers.py` (when present under default discovery) |
| Distributed state sync experiments | Tests referencing `cluster_state_setup` / sync modules—check current discovery |
| Family C recovery | `tests/test_coordination_storage.py` |
| Architecture honesty | [CLUSTER_COORDINATION.md §5](../architecture/CLUSTER_COORDINATION.md), §12 gaps |

### 12.1 Offline checks

```bash
test -s docs/operations/cluster_state.md

# Distinct state candidates still present
rg -n "class (ArrowClusterState|StateCRDT|ClusterStateSync|DurableCoordinationStore)" \
  ipfs_kit_py/cluster_state.py \
  ipfs_kit_py/cluster_state_sync.py \
  ipfs_kit_py/mcp_server/mcplusplus/coordination_storage.py

# Plasma remains disabled (wording may vary; code path must not re-enable silently)
rg -n "Plasma shared memory functionality is disabled" ipfs_kit_py/cluster_state.py

# Authority still unresolved
rg -q "Status: Proposed" docs/architecture/decisions/0008-cluster-control-plane-authority.md
```

---

## 13. What this runbook deliberately does not recommend

| Forbidden claim | Why |
|---|---|
| “Arrow is the production cluster state” | Unresolved vs CRDT / MCP++ / Kubo / StateService |
| “Enable Plasma shared memory for multi-process IPC” | Disabled in code |
| “Helpers connect zero-copy across hosts” | Disk/path helpers; Plasma path dead |
| “CRDT LWW provides linearizable multi-master tasks” | LWW drops concurrent intent |
| “StateService is multi-node consensus” | Local CLI/MCP only |
| “DurableCoordinationStore stores pinsets” | Claims/leases domain only |

---

## 14. Related documents

| Document | Relationship |
|---|---|
| [cluster_management.md](cluster_management.md) | Roles, dual managers, enablement |
| [cluster_monitoring.md](cluster_monitoring.md) | Health metrics over nodes/tasks |
| [CLUSTER_COORDINATION.md](../architecture/CLUSTER_COORDINATION.md) | Canonical state/consistency architecture |
| [ADR-0008](../architecture/decisions/0008-cluster-control-plane-authority.md) | Proposed control-plane authority |
| [coordination-storage.md](../coordination-storage.md) | Family C durability |
| [cluster_arrow_state.md](cluster_arrow_state.md) | Arrow narrative detail |
| [cluster_state_helpers.md](cluster_state_helpers.md) | Helper API narrative |
| [cluster_state_sync.md](cluster_state_sync.md) | CRDT narrative |

---

## 15. Change triggers

Re-verify when:

- ADR-0008 accepts a state identity or multi-track layering
- Plasma is re-enabled or Arrow IPC is redesigned
- CRDT algorithm defaults or gossip transport change
- Helper signatures or schema fields change
- Family C block/index layout changes
- Package vs top-level manager unification lands
