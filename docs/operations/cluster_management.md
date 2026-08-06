# Cluster management (operations)

| Field | Value |
|---|---|
| Document class | Operator runbook (current-operations) |
| Status | active |
| Last verified | 2026-08-04 |
| Owner / task | KDOC-036 |
| Goal id | KDOC-G042 |
| Authority | **No production control-plane default.** See [ADR-0008](../architecture/decisions/0008-cluster-control-plane-authority.md) (**Proposed**) and [CLUSTER_COORDINATION.md](../architecture/CLUSTER_COORDINATION.md) (KDOC-015). Unresolved map decision **U-08**. |
| Companion ops | [cluster_state.md](cluster_state.md), [cluster_monitoring.md](cluster_monitoring.md) |

This runbook documents **how to operate** multi-node coordination surfaces that already exist in the tree. It **does not** name a single production multi-node control plane. Packaging and high-level product language that mention “cluster management” are **not** authority for deployment defaults while ADR-0008 remains Proposed.

**Acceptance rule for every procedure below:** each command/API is tagged with its **implementation family** and **prerequisites**. Unresolved authority is labeled **candidate / experimental / wrapper** and is **never** converted into a production recommendation.

---

## 1. Control-plane families (read first)

Multi-node coordination is three concurrent families. Operators must pick a path for a **specific job** (pinset, in-process roles/tasks, agent claims)—not “the cluster.”

| Family | What it coordinates | Primary modules | Consistency style (observed) | Production status |
|---|---|---|---|---|
| **A. Bespoke kit cluster** | Roles, membership/leadership, tasks, optional Arrow snapshot, CRDT gossip, content-replication helpers | `ipfs_kit_py/cluster/*`, `cluster_coordinator.py`, `cluster_management.py`, `cluster_state*.py`, `cluster_state_sync.py`, `cluster_dynamic_roles.py`, `cluster_authentication.py`, `cluster_monitoring.py`, `enhanced_daemon_manager_with_cluster.py`, `p2p_workflow_coordinator.py`, `merkle_clock.py` | In-process leadership + heartbeats; CRDT/LWW; Merkle clock for P2P workflows | **Candidate.** Dual roots; package façade currently non-constructible (see §3). |
| **B. Kubo IPFS Cluster wrappers** | External pinset / peer / service lifecycle | `ipfs_cluster_api.py`, `ipfs_cluster_ctl.py`, `ipfs_cluster_service.py`, `ipfs_cluster_daemon_manager.py`, `ipfs_cluster_follow*.py` | Upstream IPFS Cluster (often CRDT when configured) | **Wrapper path.** Requires external binaries; not kit role consensus. |
| **C. MCP++ coordination store** | Agent task claims, leases, fencing, daemon-health CIDs | `mcp_server/mcplusplus/coordination_storage.py` (`DurableCoordinationStore`) | Immutable CID blocks authoritative; rebuildable SQLite indexes | **Domain-scoped candidate.** Strong local recovery tests; **not** master/worker pinset membership. |

**Adjacent (not a fourth control plane):**

| Surface | Use when | Do not use for |
|---|---|---|
| `services/state_service.py` (`StateService`) | Local CLI/MCP file state under `~/.ipfs_kit` | Multi-node consensus |
| MCP `cluster_tools.cluster_status` | Thin status call that delegates to kit `get_cluster_status` | Selecting family A/B/C |
| `fs_journal_replication.py` | Filesystem journal metadata replication (data plane) | Membership authority |
| `multi_region_cluster.py` | Geographic health / routing helper | Full CAP / membership consensus |

Architecture depth, mismatch evidence, and consistency planes: [CLUSTER_COORDINATION.md](../architecture/CLUSTER_COORDINATION.md). Decision options (A/B/C/multi-track) without a winner: [ADR-0008](../architecture/decisions/0008-cluster-control-plane-authority.md).

### 1.1 Operator decision tree (job → family, not production default)

| Job | Prefer | Status label required in runbooks |
|---|---|---|
| Multi-node **pinset** coordination with upstream IPFS Cluster | **Family B** wrappers + external binaries | wrapper / external-process |
| In-process **master/worker/leecher** roles, task queues, leader helpers that tests exercise | **Family A** documented **subsets** (e.g. daemon-enhanced types) | candidate / experimental |
| MCP++ **agent claims, leases, fencing** | **Family C** `DurableCoordinationStore` | domain-scoped candidate |
| Local CLI/MCP status buckets | `StateService` | local-only |

Do **not** present any row as “the production default multi-node plane.” That requires ADR-0008 acceptance.

---

## 2. Prerequisites by family

### 2.1 Family A — bespoke kit cluster

| Prerequisite | Why |
|---|---|
| Python package importable as `ipfs_kit_py` | All A modules live under the kit package |
| Optional: `pyarrow` (extra often named `arrow`) | Arrow cluster state path |
| Optional: libp2p stack when using top-level manager peer bridge | Direct peer messaging / join topics |
| Optional: `psutil` | Resource inventory for role/setup helpers |
| Clear choice of **which A root** you are calling | Package `cluster/` vs top-level `cluster_*` are **not** interchangeable (see §3) |
| Expectation of **process-local** membership unless a transport is proven | Package membership heartbeat **send** is stubbed in `distributed_coordination.py` |

**Not a prerequisite for production authority:** packaging keyword `cluster` or README narrative.

### 2.2 Family B — Kubo IPFS Cluster wrappers

| Prerequisite | Why |
|---|---|
| External binaries: `ipfs-cluster-service`, `ipfs-cluster-ctl`, optionally follow | Wrappers shell/HTTP to those tools |
| Compatible Kubo/IPFS node lifecycle | Cluster peers attach to IPFS |
| Network reachability for cluster API ports | HTTP/ctl operations |
| Operator-owned upstream config (consensus mode, secret, peers) | Kit does not reimplement cluster consensus |

### 2.3 Family C — MCP++ coordination store

| Prerequisite | Why |
|---|---|
| MCP++ profile/runtime that constructs `DurableCoordinationStore` | Store is MCP++-scoped |
| Writable coordination dir (`MCPPLUSPLUS_COORDINATION_DIR` or default under kit share path) | Blocks + indexes on disk |
| Understanding that claims/leases ≠ pinset membership | Wrong mental model causes mis-ops |

---

## 3. Family A dual roots (critical mismatch)

Two different classes share the name `ClusterManager` / `ClusterCoordinator`. Shared method names do **not** imply shared semantics.

| Symbol | Package path (Family A-package) | Top-level path (Family A-toplevel) |
|---|---|---|
| `ClusterManager` | `ipfs_kit_py.cluster.cluster_manager.ClusterManager` | `ipfs_kit_py.cluster_management.ClusterManager` |
| `ClusterCoordinator` | `ipfs_kit_py.cluster.distributed_coordination.ClusterCoordinator` | `ipfs_kit_py.cluster_coordinator.ClusterCoordinator` |
| `NodeRole` | `cluster.role_manager.NodeRole` (7 values, `from_string`) | `cluster_coordinator.NodeRole` (3 values, `from_str`); third copy in daemon-enhanced module |

### 3.1 Package façade construction status

`ipfs_kit.ipfs_kit` with `enable_cluster_management=True` imports **package** `cluster.cluster_manager.ClusterManager` and calls it from `_setup_cluster_management`. At the last architecture baseline, constructing package `ClusterManager` fails because call sites pass unsupported kwargs to `MetricsCollector` and `MembershipManager` (`role`, `membership_timeout` vs `node_timeout`, etc.). See [CLUSTER_COORDINATION.md §8](../architecture/CLUSTER_COORDINATION.md).

**Operational implication:**

- Treat package README “unified ClusterManager” examples as **aspirational / stale** until §8 is repaired and covered by default-discovery construction tests.
- Prefer **documented subsets with focused tests** (e.g. `tests/test_cluster_services.py` for daemon-enhanced leader/replication helpers) for experimental Family A work.
- Treat top-level `cluster_management.ClusterManager` as a **parallel stack**, not a drop-in replacement for the package manager or for Family B.

### 3.2 Method surface divergence (illustrative)

| Concern | Package manager (examples) | Top-level manager (examples) |
|---|---|---|
| Tasks | `submit_task`, proposal APIs | `create_task`, `cancel_task`, `get_tasks` |
| Status | `get_cluster_status`, `get_metrics` | `get_cluster_status`, `get_nodes`, `get_content` |
| Lifecycle | `start` / `stop` | `start` / `stop` |
| Config | `propose_configuration_change` (package) | `propose_config_change` (top-level) |

Kit façade methods such as `submit_cluster_task` call `cluster_manager.submit_task(...)`. That only matches the **package** manager surface. If a different manager instance is wired, the call fails—another reason not to invent a production default.

---

## 4. Roles (Family A)

### 4.1 Classic roles (shared product intent)

| Role | Intended duties | Notes |
|---|---|---|
| **Master** | Orchestration, leadership, task distribution, optional indexing/replication initiation | Highest leadership priority in daemon-enhanced election helpers |
| **Worker** | Execute tasks, pin/process content, may receive replication | Leadership-eligible in some helpers |
| **Leecher** | Consume content with minimal contribution | Not leadership-eligible in daemon-enhanced election |

### 4.2 Extended roles (package `role_manager` only)

`gateway`, `observer`, `modular`, `local` exist on package `NodeRole`. Do not assume the top-level three-value enum accepts them.

### 4.3 Dynamic roles bridge

`cluster_dynamic_roles.ClusterDynamicRoles` can upgrade/downgrade roles from resource thresholds. Upgrade paths may call kit hooks such as `create_cluster_service(..., consensus="crdt")`, which **bridge into Family B** (external Kubo Cluster service), not pure in-process Family A CRDT (`StateCRDT` in `cluster_state_sync.py`). Document both; never merge them into one procedure.

### 4.4 Authentication boundary

`cluster_authentication.ClusterAuthManager` provides TLS/UCAN-oriented scaffolding. Treat as **not production-hardened multi-tenant auth** without module review and an accepted control-plane ADR. Transport trust boundaries remain architecture networking docs.

---

## 5. Operational API catalog (family-tagged)

Every row lists **family**, **prerequisites**, and **status**. Status values: `candidate`, `experimental`, `wrapper`, `domain-scoped`, `local-only`, `broken-until-repair`.

### 5.1 Kit façade (`ipfs_kit.ipfs_kit`)

| API / flag | Family | Prerequisites | Status | Notes |
|---|---|---|---|---|
| `enable_cluster_management=True` (ctor / metadata) | A-package (import path) | Package cluster imports succeed; node `role`; peer id sources | **broken-until-repair** for package construct | `_setup_cluster_management` builds package `ClusterManager` |
| `get_cluster_status()` | A (whatever manager is attached) | `cluster_manager` non-null and running | candidate | MCP `cluster_status` tool also thin-wraps this |
| `submit_cluster_task(task_type, payload, …)` | A-package method shape | Manager with `submit_task` | candidate / mismatch-prone | Payload must be `dict` |
| `get_task_status(task_id)` | A | Manager with `get_task_status` | candidate | Requires non-empty `task_id` |
| `stop_cluster_manager` (internal method dispatch) | A | Running manager | candidate | Calls `cluster_manager.stop()` |
| MCP tool `cluster_tools.cluster_status` | Adjacent → A façade | MCP server + kit with manager | candidate | Does **not** choose family B/C |

### 5.2 Top-level manager (`cluster_management.ClusterManager`)

| API | Family | Prerequisites | Status |
|---|---|---|---|
| `ClusterManager(node_id, role, peer_id, config=…, enable_libp2p=…)` | A-toplevel | Valid role string; optional Arrow (`pyarrow`); optional libp2p | candidate / experimental |
| `start()` / `stop()` | A-toplevel | Constructed manager | candidate |
| `create_task` / `cancel_task` / `get_task_status` / `get_tasks` | A-toplevel | `start()` success | candidate |
| `get_nodes` / `get_cluster_status` / `get_content` | A-toplevel | Running coordinator | candidate |
| `get_state_interface_info` / `access_state_from_external_process` | A-toplevel + Arrow | Arrow state initialized; see state runbook for Plasma **disabled** | candidate / partial |
| `propose_config_change` | A-toplevel | Master-oriented config path | candidate |
| `register_task_handler` | A-toplevel | Worker handlers registered | candidate |

### 5.3 Package coordinator / daemon-enhanced (tested subsets)

| API / type | Family | Prerequisites | Status | Evidence |
|---|---|---|---|---|
| `LeaderElection` (daemon-enhanced) | A-daemon | Role priority map | candidate | `tests/test_cluster_services.py` |
| `ReplicationManager.replicate_content` | A-daemon | Master initiates; master/worker receive; optional kit pin/get | candidate | same |
| Package `ClusterCoordinator.submit_task` | A-package | Constructible coordinator (not via broken manager façade) | experimental | Unit surfaces only |
| Package `ClusterManager(...)` full composition | A-package | **Blocked** by MetricsCollector/MembershipManager kwargs | **broken-until-repair** | CLUSTER_COORDINATION §8 |

### 5.4 Family B wrappers

| API / module | Family | Prerequisites | Status |
|---|---|---|---|
| `ipfs_cluster_service` / daemon manager start-stop-status | B | Binaries + config paths | wrapper |
| `ipfs_cluster_ctl` pin/peer operations | B | Running cluster service | wrapper |
| `ipfs_cluster_api` HTTP clients | B | Reachable cluster API | wrapper |
| `ipfs_cluster_follow*` | B | Follow binary + bootstrap | wrapper |

Use upstream IPFS Cluster docs for pinset semantics. Kit wrappers manage process/HTTP edges only.

### 5.5 Family C store

| API | Family | Prerequisites | Status |
|---|---|---|---|
| `DurableCoordinationStore` put/get/lease/recover | C | Coordination directory; MCP++ runtime | domain-scoped |
| Operator guide | C | — | [docs/coordination-storage.md](../coordination-storage.md) |

---

## 6. Role-aware setup procedures (scoped, non-production)

These are **lab / experimental** procedures for confirmed module paths. They are **not** production deployment standards.

### 6.1 Family A — top-level manager (parallel stack)

**Prerequisites:** importable top-level modules; optional `pyarrow`; optional libp2p.

```python
# Family: A-toplevel | Status: candidate/experimental | Not a production default
from ipfs_kit_py.cluster_management import ClusterManager

manager = ClusterManager(
    node_id="node-master-1",
    role="master",  # master | worker | leecher
    peer_id="12D3KooW...",  # real peer id when available
    config={
        "cluster_id": "lab-cluster",
        "state_path": "~/.ipfs/cluster_state",  # Arrow path when pyarrow present
    },
    enable_libp2p=False,  # set True only when libp2p peer stack is available
)
start = manager.start()
assert start.get("success"), start
status = manager.get_cluster_status()
```

Worker nodes use `role="worker"` and rely on discovery/join messaging when libp2p is enabled. Without a real multi-host transport, membership remains process-local.

### 6.2 Family A — kit flag (package import path)

```python
# Family: A-package via ipfs_kit | Status: broken-until-repair for full construct
# Do not use as production enablement until package ClusterManager constructs cleanly.
from ipfs_kit_py.ipfs_kit import ipfs_kit

kit = ipfs_kit(
    metadata={
        "role": "master",
        "cluster_id": "lab-cluster",
        "enable_cluster_management": True,
    }
)
# Inspect kit.cluster_manager; expect setup failure logs if package façade still mismatched.
```

If setup fails with `TypeError` on `MetricsCollector`/`MembershipManager`, you have hit the documented mismatch—not a host misconfiguration. Track repair under ADR-0008 Option A follow-ups.

### 6.3 Family A — daemon-enhanced content replication demo path

```text
EnhancedDaemonManager
  ├─ LeaderElection.elect_leader()
  ├─ ReplicationManager.replicate_content(cid, peers)
  └─ IndexingService (master-oriented)
```

**Prerequisites:** imports from `ipfs_kit_py.cluster.enhanced_daemon_manager_with_cluster`; optional kit instance for pin/get. **Status:** candidate (unit-tested helpers). See `cluster/practical_cluster_setup.py` for demo orchestration only.

### 6.4 Family B — external pinset path

```text
1. Install/configure Kubo + ipfs-cluster-service (upstream docs)
2. Use kit daemon managers / ctl wrappers for start/status/stop and pin ops
3. Do not assume kit NodeRole enums replace cluster peer roles
```

**Status:** wrapper. Pinset consensus authority is **upstream**, not Family A Arrow/CRDT.

### 6.5 Family C — agent coordination path

Use `DurableCoordinationStore` and [coordination-storage.md](../coordination-storage.md). **Status:** domain-scoped candidate. Do not schedule kit worker tasks or pinsets through this store.

---

## 7. Task flow (Family A)

```text
Operator / API
    │
    ├─► package ClusterCoordinator.submit_task / update_task_status
    │       (in-memory queue + assignments; optional proposals)
    │
    ├─► top-level ClusterCoordinator.create_task / cancel_task
    │       (queue-based scheduler threads when start() called)
    │
    └─► P2PWorkflowCoordinator (+ MerkleClock)
            workflow tags → priority queue → peer ownership
            state under ~/.ipfs_kit/p2p_workflows (default)
```

Merkle/P2P workflow plane is **orthogonal** to Arrow cluster state and to Kubo pinset consensus. Evidence: `tests/test_p2p_workflow.py`.

---

## 8. Partition, degradation, and recovery (compose carefully)

There is **no** repository-wide orchestrator that sequences Family A + B + C recovery.

### 8.1 Observed behaviors (Family A)

| Scenario | Observed behavior | Operational gap |
|---|---|---|
| Member heartbeat timeout | Mark departed; membership callback | Package heartbeat **send** is stubbed—multi-host detection needs a real transport bridge |
| Leader unhealthy | Daemon-enhanced path re-elects by priority | Top-level coordinator may diverge until restart/sync |
| Concurrent CRDT map updates | Vector clock marks concurrent; default **LWW** | Concurrent intent may be dropped |
| Package manager construct | TypeError on mismatched kwargs | Façade unusable until repair |

### 8.2 Recovery order (per plane)

```text
Family A process restart
  1. Reconstruct role/coordinator from config (no single shared bootstrap)
  2. If Arrow persistence enabled: load state_path tables (see cluster_state.md)
  3. If ClusterStateSync used: re-init CRDT; rejoin gossip only if kit provides it
  4. Re-run leader election if master-capable

Family B
  1. Restart ipfs-cluster-service / follow via daemon managers
  2. Rely on upstream cluster state recovery

Family C
  1. Open DurableCoordinationStore (rebuild indexes from blocks if needed)
  2. recover(rebuild=...) when indexes empty but blocks present
  3. get() may repair missing local block from backend after CID verify
```

### 8.3 Degradation guidance (not production SLOs)

- Prefer **read-only inspection** (status, state helpers, metrics) when authority is unclear.
- Do not automate cross-family “fail over A to B” without an accepted ADR multi-track policy.
- Automated recovery actions in monitoring (GC, pin reallocation) are **local heuristics**—see [cluster_monitoring.md](cluster_monitoring.md).

---

## 9. Scoped validation (confirmed paths only)

Prefer **default pytest discovery**. Network-heavy workflow files may require services; do not claim CI green without those gates.

| Concern | Focused tests | Family |
|---|---|---|
| Daemon-enhanced roles, leader election, replication, indexing | `tests/test_cluster_services.py` | A-daemon |
| Merkle clock / P2P workflow | `tests/test_p2p_workflow.py` | A-workflow |
| MCP++ coordination store | `tests/test_coordination_storage.py` | C |
| Kubo cluster daemon/API/follow units | `tests/unit/test_cluster_startup.py`, `test_cluster_api.py`, `test_cluster_follow_enhanced.py` | B |
| Health monitor adjacency | `tests/unit/test_health_monitor_cluster.py` | A/B adjacency |

**Gaps (do not over-claim):**

- No default-discovery test was observed that constructs package `cluster.ClusterManager` end-to-end against live multi-host heartbeats.
- Package vs top-level API parity is not enforced by tests.
- Real multi-host partition healing for Family A is under-specified relative to comments.

### 9.1 Offline structural checks

```bash
# This runbook present
test -s docs/operations/cluster_management.md

# Families still distinct (structural)
rg -n "class (ClusterManager|ClusterCoordinator|MembershipManager|ArrowClusterState|StateCRDT|ReplicationManager|DurableCoordinationStore)" \
  ipfs_kit_py/cluster/cluster_manager.py \
  ipfs_kit_py/cluster_management.py \
  ipfs_kit_py/cluster/distributed_coordination.py \
  ipfs_kit_py/cluster_coordinator.py \
  ipfs_kit_py/cluster_state.py \
  ipfs_kit_py/cluster_state_sync.py \
  ipfs_kit_py/cluster/enhanced_daemon_manager_with_cluster.py \
  ipfs_kit_py/mcp_server/mcplusplus/coordination_storage.py

# Package façade mismatch still present until repaired
rg -n "role=self.initial_role|membership_timeout=" ipfs_kit_py/cluster/cluster_manager.py

# ADR still Proposed (no invented production default)
rg -q "Status: Proposed" docs/architecture/decisions/0008-cluster-control-plane-authority.md
```

---

## 10. What this runbook deliberately does not recommend

| Forbidden claim | Why |
|---|---|
| “Use package `ClusterManager` as the production default” | Non-constructible façade; ADR-0008 Proposed |
| “Enable `enable_cluster_management=True` for production HA” | Wires broken/aspirational package path; no accepted authority |
| “Arrow state is the multi-node source of truth” | One of several state candidates; Plasma IPC disabled |
| “Family C replaces Kubo Cluster pinsets” | Different domain (claims/leases) |
| “Family B and Family A roles are the same subsystem” | Different processes and enums |
| Single cluster-wide linearizability | Consistency is **per-plane** best-effort / LWW / external |

---

## 11. Related documents

| Document | Relationship |
|---|---|
| [CLUSTER_COORDINATION.md](../architecture/CLUSTER_COORDINATION.md) | Canonical architecture: families, mismatches, consistency |
| [ADR-0008](../architecture/decisions/0008-cluster-control-plane-authority.md) | Proposed authority decision (no winner) |
| [SOURCE_OF_TRUTH_MAP.md](../architecture/SOURCE_OF_TRUTH_MAP.md) §4 | Evidence map; U-08 |
| [cluster_state.md](cluster_state.md) | State planes and inspection |
| [cluster_monitoring.md](cluster_monitoring.md) | Health, metrics, recovery actions |
| [coordination-storage.md](../coordination-storage.md) | Family C durability model |
| [CLUSTER_DEPLOYMENT_GUIDE.md](../guides/CLUSTER_DEPLOYMENT_GUIDE.md) | Deployment narrative—verify samples against §3 before trusting |
| `ipfs_kit_py/cluster/README.md` | Package feature narrative; may lag constructible APIs |

---

## 12. Change triggers

Re-verify this runbook when:

- ADR-0008 is Accepted or options change
- Package `ClusterManager` construction is repaired (or permanently namespaced)
- Dual `NodeRole` / coordinator modules are unified
- Heartbeat transport is wired or explicitly local-only
- New default-discovery integration tests cover start/stop multi-node paths
- Family B binary matrix or Family C schema changes
