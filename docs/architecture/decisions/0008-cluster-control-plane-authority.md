# ADR-0008: Cluster control-plane authority

> **Document class:** Proposed  
> **Decision status:** Proposed  
> **Date:** 2026-08-03  
> **Last verified:** 2026-08-03  
> **Evidence baseline:** current tree as of 2026-08-03 (`ddf1c8608c93332e17b3f0243a46d7f50f88ab1b`); cluster guide baseline `6fc55f0918a0f45e04b37727b45c1a1f5aaf9322` (KDOC-015)  
> **Authors:** KDOC-028 (agent task)  
> **Confirmation owner:** maintainers of multi-node / cluster product surface (library + packaging + ops); documentation maintainers may not accept this ADR alone  
> **Supersedes:** none  
> **Superseded by:** none  
> **Related guides:** [`../CLUSTER_COORDINATION.md`](../CLUSTER_COORDINATION.md), [`../SOURCE_OF_TRUTH_MAP.md`](../SOURCE_OF_TRUTH_MAP.md) §4, [`../MCP_CONTROL_PLANE.md`](../MCP_CONTROL_PLANE.md), [`../SYSTEM_OVERVIEW.md`](../SYSTEM_OVERVIEW.md), [`../CONFIGURATION_STATE_AND_TRUST.md`](../CONFIGURATION_STATE_AND_TRUST.md)  
> **Related conflicts / U-IDs:** U-08; adjacent: state-store identity (map §4), daemon-manager lifecycle (map / U-09 adjacency), U-11 (MCP trees—orthogonal authority)

Process contract:
[`README.md`](./README.md) · Claim standard:
[`docs/guides/DOCUMENTATION_GUIDE.md`](../../guides/DOCUMENTATION_GUIDE.md)

---

## 1. Context

Multi-node coordination in this repository is implemented as **three concurrent control-plane families**, plus adjacent local state and replication helpers that are easy to conflate with them. Packaging keywords and high-level description mention “cluster management,” but no maintainer-accepted record names a **production default** multi-node control plane for kit deployments.

| Force | Effect |
|---|---|
| Parallel Family A trees (`ipfs_kit_py/cluster/` package vs top-level `cluster_*` modules) | Duplicate type names, incompatible constructors, diverging public APIs |
| Family B Kubo IPFS Cluster wrappers | Process-wrapper path to external binaries; different lifecycle and consensus model |
| Family C MCP++ `DurableCoordinationStore` | Strong local recovery tests for agent claims/leases—not kit master/worker membership |
| Operator and agent demand for “the” cluster API | Risk of guides or examples inventing a canonical default without evidence |
| Unresolved **U-08** in the source-of-truth map | Architecture guides must stay candidate-only until this ADR is accepted |

**In scope:**

- Which control-plane **family** (or explicit multi-track policy) is production authority for multi-node kit deployments
- Compatibility, migration, and testing consequences of each option
- How Family A internal dual roots (`cluster/` vs top-level `cluster_*`) relate if Family A is retained
- What “authoritative cluster state” means relative to Arrow / CRDT / MCP++ / `StateService` candidates (decision framing only; full durability SLAs may remain adjacent ADRs)
- Confirmation request and acceptance criteria for promotion from **Proposed** to **Accepted**

**Out of scope:**

- Implementing constructor fixes or deleting modules (code tasks after acceptance)
- Sole production **MCP runtime** among `mcp_server` / `mcp` / root trees (**ADR-0003** / **U-11**)
- Default **content transport** Kubo vs Iroh (**ADR-0006** / **U-09**)
- WAL / content-metadata durability layering (**ADR-0005**)
- Exhaustive method inventories (reference/generated docs)
- Declaring any family Accepted by virtue of this draft

**Non-goal of this draft:** Selecting a winner among families A, B, and C. Conflict policy for KDOC-028 and the ADR index require this record to **remain Proposed** and to present options without hiding ambiguity.

---

## 2. Current behavior (evidence, not aspiration)

Present-tense claims below describe the tree **as observed**. They do **not** assert a chosen production default.

### 2.1 Three control-plane families

```text
                    Multi-node coordination (authority UNRESOLVED — U-08)
         ┌────────────────────────────┬────────────────────────────┐
         ▼                            ▼                            ▼
 ┌───────────────────┐    ┌──────────────────────┐    ┌──────────────────────┐
 │ A. Bespoke kit    │    │ B. Kubo IPFS Cluster │    │ C. MCP++ durable     │
 │ cluster stack     │    │ external process     │    │ coordination store   │
 │ cluster/ +        │    │ wrappers             │    │ DurableCoordination  │
 │ cluster_* modules │    │ ipfs_cluster_*       │    │ Store + Event DAG    │
 └───────────────────┘    └──────────────────────┘    └──────────────────────┘
```

| Surface / path | Observed role | Evidence | Status label |
|---|---|---|---|
| `ipfs_kit_py/cluster/` (`role_manager`, `distributed_coordination`, `cluster_manager`, `monitoring`, `enhanced_daemon_manager_with_cluster`, …) | Bespoke roles, membership, election, metrics, daemon-enhanced replication helpers | Source + `tests/test_cluster_services.py` | **Candidate** Family A package root |
| Top-level `cluster_coordinator.py`, `cluster_management.py`, `cluster_state*.py`, `cluster_state_sync.py`, `cluster_dynamic_roles.py`, `cluster_authentication.py`, `cluster_monitoring.py`, `merkle_clock.py`, `p2p_workflow_coordinator.py` | Parallel Family A APIs (coordinators, Arrow state, CRDT sync, dynamic roles, auth, P2P workflows) | Source + `tests/test_p2p_workflow.py` | **Candidate** Family A top-level root |
| `ipfs_cluster_api.py`, `ipfs_cluster_ctl.py`, `ipfs_cluster_service.py`, `ipfs_cluster_daemon_manager.py`, `ipfs_cluster_follow*.py` | Wrappers for external `ipfs-cluster-*` binaries and HTTP APIs | Source + unit tests under `tests/unit/test_cluster_*.py` | **Candidate** Family B |
| `mcp_server/mcplusplus/coordination_storage.py` (`DurableCoordinationStore`) | CID-addressed claims, leases, fencing, daemon-health artifacts; rebuildable SQLite indexes | Source + `tests/test_coordination_storage.py`; `docs/coordination-storage.md` | **Candidate** Family C (agent coordination) |
| `services/state_service.py` (`StateService`) | Local JSON/file state for CLI/MCP parity | Source | **Adjacent** — not multi-node consensus |
| MCP `cluster_tools.cluster_status` | Thin tool → `get_cluster_status` | MCP tool registry / control-plane guide | **Adjacent** — does not select family |
| `fs_journal_replication.py` | Journal metadata replication (data-plane adjacency) | Source; KDOC-014 ownership | **Adjacent** |
| `multi_region_cluster.py` | Geographic health/routing helper | Source | **Adjacent** |
| Packaging `pyproject.toml` / `setup.py` description and keywords | Mentions “cluster management” / keyword `cluster` | Packaging metadata | Marketing signal only — **not** family selection |
| Console scripts | No dedicated console entry solely for bespoke Family A cluster management (MCP++ has `ipfs-kit-mcp`) | Packaging entry points | Family A is library-import oriented |

### 2.2 Family A internal split (rank-1 structural evidence)

| Symbol | Location A | Location B | Incompatibility (observed) |
|---|---|---|---|
| `ClusterManager` | `cluster/cluster_manager.py` | `cluster_management.py` | Same-ish parameter *names* but different dependencies and public methods; package path composes RoleManager + MembershipManager + package coordinator; top-level composes top-level coordinator + Arrow + libp2p bridge |
| `ClusterCoordinator` | `cluster/distributed_coordination.py` | `cluster_coordinator.py` | Different `__init__` shapes (`cluster_id, node_id, is_master, …` vs `node_id, role, peer_id, config, …`) and different public method sets (`submit_task` vs `create_task`, etc.) |
| `NodeRole` | `role_manager` (7 values, `from_string`) | `cluster_coordinator` (3 values, `from_str`); third copy in `enhanced_daemon_manager_with_cluster` | Enum members and converter names diverge |
| `MembershipManager` | Defined in `distributed_coordination.py` | Call site in `cluster/cluster_manager.py` | Call site passes unsupported kwargs |

**Confirmed non-constructible package façade (baseline from KDOC-015 / cluster guide §8):**

| Call | Failure mode |
|---|---|
| `ClusterManager(node_id=…, role="master")` (package) | `MetricsCollector.__init__` does not accept `role` → `TypeError` |
| Package call site → `MembershipManager(..., role=…, peer_id=…, membership_timeout=…)` | Actual signature is `(cluster_id, node_id, heartbeat_interval, node_timeout, membership_callback)` → `TypeError` on `role` (and related kwargs) |

Implication: the packaged “unified” `cluster.ClusterManager` composition path is **not constructible** against sibling modules as committed. README examples that treat it as the production façade are **aspirational / stale** until repaired.

Additional Family A facts:

- Package membership heartbeat **send** is stubbed (logs only) in `MembershipManager`—multi-host detection needs a real transport bridge.
- Arrow `ArrowClusterState` Plasma shared-memory path is **disabled** (upstream Arrow Plasma removal); disk/table persistence remains a candidate snapshot, not proven multi-writer across hosts.
- CRDT path (`StateCRDT` / `ClusterStateSync`) defaults to **LWW**; orthogonal to Kubo Cluster’s upstream CRDT when Family B binaries run.
- Dynamic role paths may call `create_cluster_service(..., consensus="crdt")`, **bridging into Family B** rather than pure in-process Family A.

### 2.3 Family B and C (summary)

| Family | Coordinates | Consistency / authority (observed) | Test strength (default discovery) |
|---|---|---|---|
| **B** | External pinset/peer/service lifecycle via Kubo Cluster tools | Upstream cluster consensus when binaries run; kit code wraps processes/HTTP | Unit-oriented (`test_cluster_startup`, `test_cluster_api`, follow/backends) |
| **C** | Agent task claims, leases, fencing tokens, expiring health CIDs | Immutable blocks authoritative; indexes rebuildable; fail-closed on CID mismatch | Strong recovery/fencing/retention (`test_coordination_storage.py`) |

### 2.4 Consistency claim boundary

Across Family A, consistency is best described as **per-plane best-effort coordination** (in-process leadership, LWW maps, optional Arrow snapshots)—**not** cluster-wide linearizability. Family C proves durable local coordination recovery, not master/worker task scheduling. Family B defers consensus to upstream. Guides must not merge these into one mental model.

Narrative: Competition is real and measurable; **no family is presently Accepted as production default.** Ambiguity is intentional in documentation until maintainers confirm.

---

## 3. Decision

**Status:** Proposed  

### 3.1 Decision statement

**No production control-plane family is selected by this ADR.**

Maintainers must choose one of the options in §3.2 (or an explicit multi-track policy under option D) before architecture guides, operator runbooks, or packaging claims may present a single “canonical” multi-node control plane. Until promotion rules in [`README.md`](./README.md) §3.1 are met, all families remain **candidates**.

Candidate decision framing for confirmation (not selected):

> For multi-node kit deployments, production control-plane authority shall be &lt;option id&gt;, with &lt;migration/compat policy&gt; for non-chosen families and a named authoritative state plane (or layered authorities).

### 3.2 Options (required — no winner selected)

| Option | Summary | Fit / risk |
|---|---|---|
| **A — Bespoke kit cluster as production default** | Treat Family A as the multi-node role/membership/task plane; repair package `ClusterManager` / unify or permanently namespace dual roots; document Arrow/CRDT layering | Aligns with master/worker/leecher product narrative and packaging “cluster” wording; **high repair cost** (constructor mismatches, stub heartbeats, dual APIs); risk of shipping aspirational façade |
| **B — Kubo IPFS Cluster wrappers as production default** | External `ipfs-cluster-*` is the multi-node pinset/membership authority; kit owns process lifecycle and HTTP/ctl wrappers; bespoke roles become optional helpers or deprecation candidates | Strong upstream consensus story when binaries available; kit becomes operator of **external** lifecycle; less native role/task model; binary and network dependencies |
| **C — MCP++ coordination store as production default** | `DurableCoordinationStore` is the multi-node coordination authority for kit-mediated agent/work claims | Strong tests and durability model; **does not** implement classic master/worker/pinset semantics; conflating with Family A roles would mislead operators |
| **D — Explicit multi-track (layered authorities)** | Publish an operator decision tree: e.g. pinset → B; agent claims/leases → C; optional in-process roles/tasks → A (experimental until repaired) | Honest about current tree; higher docs/ops complexity; still needs state-store identity and “what is production” wording per track |
| **Status quo** | Leave competing surfaces unlabeled as default; continue candidate-only language in guides | No false certainty; **ongoing operator and agent confusion**; packaging keywords continue to over-promise |

**Selected option (if any):** none yet — awaiting confirmation  

**Forbidden without acceptance:** Presenting package README’s `cluster.ClusterManager`, Kubo wrappers, or MCP++ coordination as “the” production multi-node default in architecture guides or release notes.

---

## 4. Rationale (confidence-labeled)

**Accepted:**  

- Competing multi-node surfaces exist in-tree and are documented as distinct families in [`CLUSTER_COORDINATION.md`](../CLUSTER_COORDINATION.md) (KDOC-015).  
- Package `ClusterManager` construction against current `MetricsCollector` / `MembershipManager` signatures fails with `TypeError` (rank-1 call-site vs definition mismatch).  
- MCP++ `DurableCoordinationStore` has focused recovery/fencing tests under default pytest discovery.  
- Packaging advertises cluster management without selecting an implementation family.  
- Source-of-truth map lists **U-08** as an unresolved owner decision binding guides and this ADR slot.

**Proposed:**  

- Maintainers should accept one of §3.2 options (including explicit multi-track) so operators and agents have a single authority story.  
- If Family A remains in any production track, constructors and dual-root APIs should be unified or permanently namespaced, with construction + start/stop tests under default discovery.  
- If multi-track is accepted, each track must name: primary modules, state identity, failure domain, and “do not use for X” boundaries.  
- Heartbeat transport for Family A should be either wired to a real pubsub/libp2p path or explicitly documented as process-local-only.

**Inferred:**  

- Parallel Family A trees grew as incremental features rather than a single modular redesign—hence duplicate names and mismatched constructors.  
- Plasma abandonment left Arrow disk tables as a partial replacement without multi-process IPC.  
- Dynamic-role bridges into Family B suggest historical intent to compose stacks, not to replace Kubo Cluster wholesale.  
- Packaging “cluster” language reflects product aspiration more than a verified single runtime.

**Unknown:**  

- Whether any production deployment standardizes on package README examples despite non-constructible `ClusterManager` — unknown / maintainer confirmation needed.  
- Which daemon manager (enhanced / intelligent / cluster-enhanced) is lifecycle authority when composing multi-node deploys — unknown / maintainer confirmation needed.  
- Whether “authoritative cluster state” should be Arrow snapshots, CRDT maps, MCP++ blocks, layered all three, or none of these for membership — unknown / maintainer confirmation needed.  
- Production posture of `ClusterAuthManager` (TLS/UCAN scaffolding) relative to the chosen plane — unknown / maintainer confirmation needed.  
- Whether Family B binaries are a hard dependency for “supported” multi-node deployments or optional — unknown / maintainer confirmation needed.

---

## 5. Evidence

| Rank | Claim | Citation |
|---|---|---|
| 1 | Package `ClusterManager` call site passes unsupported kwargs to `MetricsCollector` / `MembershipManager` | `ipfs_kit_py/cluster/cluster_manager.py` (e.g. `role=self.initial_role`, `membership_timeout=…`); defs in `cluster/monitoring.py`, `cluster/distributed_coordination.py` |
| 1 | Daemon-enhanced roles, leader election, replication helpers covered by unit tests | `tests/test_cluster_services.py` |
| 1 | Merkle clock / P2P workflow coordinator behavior tested | `tests/test_p2p_workflow.py` |
| 1 | MCP++ coordination store recovery, fencing, retention tested | `tests/test_coordination_storage.py` |
| 1 | Dual `ClusterManager` / `ClusterCoordinator` class definitions coexist | `cluster/cluster_manager.py`, `cluster_management.py`, `cluster/distributed_coordination.py`, `cluster_coordinator.py` |
| 1 | `ArrowClusterState`, `StateCRDT` exist as separate state candidates | `cluster_state.py`, `cluster_state_sync.py` |
| 1 | `DurableCoordinationStore` class exists under MCP++ | `mcp_server/mcplusplus/coordination_storage.py` |
| 1 | Kubo Cluster wrapper modules present | `ipfs_cluster_api.py`, `ipfs_cluster_ctl.py`, `ipfs_cluster_service.py`, `ipfs_cluster_daemon_manager.py`, `ipfs_cluster_follow*.py` |
| 1 | Family B unit tests under default discovery | `tests/unit/test_cluster_startup.py`, `test_cluster_api.py`, `test_cluster_follow_enhanced.py`, `test_cluster_backends.py`, `test_health_monitor_cluster.py` |
| 2 | Packaging describes “cluster management”; keyword `cluster` | `pyproject.toml`, `setup.py` |
| 2 | No dedicated console script solely for bespoke Family A cluster | Packaging entry-point tables (MCP++ scripts exist separately) |
| 3 | Cluster guide records families, mismatches, consistency planes | [`../CLUSTER_COORDINATION.md`](../CLUSTER_COORDINATION.md) §§2–8, §12 |
| 3 | Map §4 candidate paths and U-08 question | [`../SOURCE_OF_TRUTH_MAP.md`](../SOURCE_OF_TRUTH_MAP.md) §4 and aggregate U-table |
| 4 | ADR index pre-registers this slot as **Proposed (required)** with confirmation | [`README.md`](./README.md) §8.1 ADR-0008, §8.2 |
| 5 | Trust guide lists U-08 open | [`../CONFIGURATION_STATE_AND_TRUST.md`](../CONFIGURATION_STATE_AND_TRUST.md) §12 |
| 5 | System overview warns not to assume one control plane without ADR | [`../SYSTEM_OVERVIEW.md`](../SYSTEM_OVERVIEW.md) §10 |

**Evidence that is explicitly insufficient for Accepted status:**

- Documentation consensus that families should stay labeled “candidate”
- Packaging marketing language about cluster management
- Existence of strong tests for **one** family (e.g. Family C recovery) without a maintainer statement that that family is the multi-node production default
- Inference about historical growth of parallel trees
- Agent authorship of this Proposed ADR

**Test gaps (do not over-claim):**

- No default-discovery test observed that constructs package `cluster.ClusterManager` successfully end-to-end against live multi-host heartbeats
- Package vs top-level API parity is **not** enforced by tests
- Real multi-host partition/healing for Family A is under-specified relative to comments
- Workflow `.github/workflows/cluster-tests.yml` may assume network/services—mark carefully when claiming CI green

---

## 6. Consequences

### 6.1 Positive

- **If Accepted (any option):** Operators and agents get an explicit authority story; guides can use non-candidate language for the chosen track(s).  
- **If A accepted after repair:** Single role/membership/task narrative matching kit vocabulary (master/worker/leecher).  
- **If B accepted:** Clear dependency on upstream IPFS Cluster for pinset consensus; kit focus on wrappers and lifecycle.  
- **If C accepted for its domain:** Fail-closed durable agent coordination with tested recovery.  
- **If D accepted:** Avoids false unification; documents safe composition.  
- **While Proposed:** Prevents architecture guides from inventing a default; preserves U-08 visibility.

### 6.2 Negative / costs

- **While Proposed:** Continued ambiguity; risk of divergent operator runbooks and example code.  
- **Option A:** Significant engineering to fix constructors, unify types, wire heartbeats, add integration tests.  
- **Option B:** External binary/version matrix; weaker native kit role model unless bridged carefully.  
- **Option C alone as “the cluster”:** Semantic mismatch with pinset/role expectations; may still need A or B for content replication.  
- **Option D:** Ongoing multi-track docs and support burden.  
- **Status quo indefinitely:** Highest long-term confusion cost.

### 6.3 Migration and compatibility

| From → To | Migration notes |
|---|---|
| Status quo → A | Fix package façade first; freeze or rename top-level duplicates; provide shim period with deprecation warnings; update deployment guide examples |
| Status quo → B | Document required binaries; mark Family A APIs experimental or compatibility-only; align dynamic-role bridges as supported path into B |
| Status quo → C | Scope C to agent claims/leases; do not rename as general “cluster membership”; migrate MCP tools/docs to that boundary |
| Status quo → D | Publish decision tree and “authoritative for X” table; require family tags on every cluster example |
| Any → deprecating a family | Keep import paths temporarily; add tests that fail if accidental re-promotion; archive only after confirmation window |

Compatibility rule while this ADR is **Proposed:** label every multi-node example with its family (A/B/C) and status (candidate / experimental / wrapper).

### 6.4 Security and trust

- Family A `ClusterAuthManager` is scaffolding-scale relative to threat-model depth—do not claim multi-tenant production hardening without review.  
- Family B inherits trust boundaries of external cluster processes and their APIs (network exposure, peer auth).  
- Family C: immutable CID blocks + fencing tokens; indexes rebuildable—trust integrity of block store and peer DIDs.  
- Credentials: none in this ADR; use placeholders only if examples are required.  
- Adjacent: MCP HTTP non-loopback remains elevated risk (control-plane guides)—orthogonal to cluster family choice.

### 6.5 Testing and verification

**Tests that encode today’s behavior (must keep honest):**

- `tests/test_cluster_services.py` — Family A daemon-enhanced helpers  
- `tests/test_p2p_workflow.py` — Merkle/P2P workflow plane  
- `tests/test_coordination_storage.py` — Family C durability  
- `tests/unit/test_cluster_startup.py`, `test_cluster_api.py`, `test_cluster_follow_enhanced.py` — Family B wrappers  

**Tests that should be added before accepting Option A (or A track under D):**

1. Construction of intended `ClusterManager` / `ClusterCoordinator` without `TypeError`  
2. Start/stop smoke under default pytest discovery  
3. Membership heartbeat path either works over a real transport or is explicitly documented and tested as local-only  
4. Single `NodeRole` converter contract (or dual permanently namespaced types with contract tests)  
5. Negative tests that prevent reintroducing kwargs/signature drift between call sites and callees  

**Tests before accepting Option B as sole multi-node default:**

1. Documented binary presence gates and clear skip/xfail policy  
2. Lifecycle round-trip (service start/status/stop) in supported environments  
3. Explicit non-goals for Family A role APIs in the same suite docs  

**Tests before accepting Option C as sole multi-node default:**

1. Maintain recovery/fencing suite green  
2. Explicit tests that C is **not** a pinset membership API (boundary tests / docs assertions)  

**Offline re-check commands (documentation / structural):**

```bash
# ADR remains Proposed and non-empty
test -s docs/architecture/decisions/0008-cluster-control-plane-authority.md \
  && rg -q "Status: Proposed" docs/architecture/decisions/0008-cluster-control-plane-authority.md

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

# Confirmed package mismatch still present until repaired
rg -n "role=self.initial_role|membership_timeout=" ipfs_kit_py/cluster/cluster_manager.py
```

---

## 7. Alternatives considered

| Alternative | Why considered | Why rejected / deferred | Confidence |
|---|---|---|---|
| Declare package `cluster.ClusterManager` canonical now | Matches package layout and README aspiration | Non-constructible against sibling modules; would invent Accepted authority | **Accepted** as deferred (cannot accept without repair + confirmation) |
| Treat Kubo wrappers and bespoke roles as one subsystem | Shared “cluster” naming | Different processes, APIs, and consistency models | **Accepted** as rejected conflation (guide + this ADR) |
| Treat MCP++ coordination as kit master/worker plane | Strong tests | Different purpose (claims/leases vs role/task/pinset) | **Accepted** as rejected conflation without explicit multi-track policy |
| Agent-selected winner in this draft | Unblocks wording in guides | Violates KDOC-028 conflict policy, ADR process, and U-08 confirmation requirement | **Accepted** as rejected for this task |
| Status quo forever (no ADR body) | Avoid premature choice | Leaves U-08 without a decision vehicle; index requires this file | **Proposed** rejection of permanent silence—this ADR records options instead |
| Unknown / wait for more reverse engineering only | Incomplete state identity | Options and confirmation question are already answerable by maintainers | **Inferred** — more code reading does not replace owner confirmation |

At least one alternative (including “do nothing / keep status quo”) is required: **status quo** remains a valid temporary policy but is listed as an option with explicit confusion costs, not as silent default acceptance.

---

## 8. Unknowns and owner confirmation

| Field | Value |
|---|---|
| **Confirmation owner** | Maintainers responsible for multi-node / cluster product surface (core library + packaging + ops). Documentation maintainers may draft and update this record but **must not** flip status to Accepted without that confirmation (or unambiguous implemented invariant meeting README §3.1). |
| **Confirmation question** | For multi-node kit deployments, which control-plane policy is production authority: **A** (bespoke kit cluster, after stated repairs), **B** (Kubo IPFS Cluster wrappers), **C** (MCP++ coordination store for its domain only), or **D** (explicit multi-track with a published decision tree)—and what is the authoritative state store (or layered authorities) under that policy? |
| **What “Accepted” requires** | (1) Explicit maintainer selection of A/B/C/D (or a named refinement); (2) rank-1–4 evidence that the chosen track is implementable (for A: construction/integration tests green; for B: documented binary lifecycle; for C: domain boundary + recovery tests; for D: decision tree + per-track tests); (3) written migration/compat policy for non-chosen surfaces; (4) update of this ADR status and confirmation section—not guide-only prose. |
| **Blocking for** | Operator deployment defaults; any architecture guide language that names a single production multi-node control plane; packaging claims beyond “includes cluster-related modules”; KDOC follow-ons that implement deprecations or canonical APIs; cluster operations docs that would otherwise invent authority (e.g. tasks depending on KDOC-028). |
| **Related U-IDs / conflicts** | **U-08** (this decision); state-store identity (map §4); API/constructor mismatches (cluster guide §8); daemon manager authority (adjacent); **U-11** / ADR-0003 (MCP runtime—orthogonal); **U-09** / ADR-0006 (content transport—orthogonal). |

**Open unknowns:**

1. Production deployments’ actual preferred family (if any) — unknown / maintainer confirmation needed  
2. Whether Family A package README examples are intentionally aspirational or accidental bitrot — unknown / maintainer confirmation needed  
3. Authoritative state store identity among Arrow, CRDT, `StateService`, and `DurableCoordinationStore` — unknown / maintainer confirmation needed  
4. Daemon manager lifecycle authority when composing multi-node deploys — unknown / maintainer confirmation needed  
5. `ClusterAuthManager` production trust posture for the chosen plane — unknown / maintainer confirmation needed  
6. Whether multi-track (D) is preferred short-term even if a single default is long-term goal — unknown / maintainer confirmation needed  

---

## 9. Supersession and relationships

| Relation | ADR / doc |
|---|---|
| Supersedes | none |
| Superseded by | none |
| Related ADRs | ADR-0003 (MCP runtime authority—orthogonal control plane); ADR-0005 (content/metadata durability); ADR-0006 (multi-protocol networking); ADR-0007 (config/state/secrets) |
| Architecture guides | [`../CLUSTER_COORDINATION.md`](../CLUSTER_COORDINATION.md) (evidence home; must not pre-pick winner); [`../MCP_CONTROL_PLANE.md`](../MCP_CONTROL_PLANE.md); [`../SYSTEM_OVERVIEW.md`](../SYSTEM_OVERVIEW.md); [`../CONFIGURATION_STATE_AND_TRUST.md`](../CONFIGURATION_STATE_AND_TRUST.md); [`../NETWORK_TRANSPORTS.md`](../NETWORK_TRANSPORTS.md) (adjacent) |
| Source-of-truth map | [`../SOURCE_OF_TRUTH_MAP.md`](../SOURCE_OF_TRUTH_MAP.md) §4, U-08 |
| Deployment guide | `docs/guides/CLUSTER_DEPLOYMENT_GUIDE.md` (must stay status-honest until Accepted) |

---

## 10. Follow-up actions

| Action | Owner | Notes |
|---|---|---|
| Answer confirmation question (§8) | Cluster/product maintainers | Required to leave Proposed |
| Keep guides candidate-only until Accepted | Doc authors / KDOC program | Cite this ADR with **Proposed** language only |
| If Option A (or A track): fix MetricsCollector/MembershipManager call sites; unify or namespace dual types | Engineering | Unblocks constructibility; add default-discovery construction tests |
| If Option A: wire or document-away stub `_send_heartbeat` | Engineering | Multi-host membership honesty |
| If Option B: binary matrix + lifecycle tests policy | Engineering / ops | Avoid false CI green without services |
| If Option C sole or track: document domain boundary vs roles/pinset | Docs + MCP maintainers | Prevent semantic overload |
| If Option D: publish operator decision tree in cluster guide post-acceptance | Docs | Family tags on every example |
| Decide state-store identity (Arrow vs CRDT vs MCP++ vs local StateService) | Maintainers | May amend this ADR or a short follow-on note under same U-08 umbrella |
| Threat model for auth relative to chosen plane | Security-minded maintainer | `cluster_authentication.py` |
| Do **not** edit decisions README from this task | Agents | Index is framework-owned (KDOC-020) |
| Cluster operations docs depending on this ADR | Later KDOC tasks | Retain Proposed authority language until confirmation |

---

## 11. Review checklist (authors)

- [x] Filename is `0008-cluster-control-plane-authority.md` (not left as 0000)
- [x] Banner **Decision status** matches §3 **Status** (`Proposed`)
- [x] **Current behavior** is evidence-backed and separate from the proposal
- [x] No present-tense “the system’s production default is X” for Proposed-only intent
- [x] Every material *why* uses **Accepted / Proposed / Inferred / Unknown**
- [x] No Inferred or Unknown claim is written as Accepted history
- [x] Evidence table prefers ranks 1–4 for Accepted claims; docs rank 5 supporting only
- [x] Alternatives include status quo and explicit reject of agent-selected winner
- [x] Confirmation owner and question filled (status is Proposed)
- [x] No secrets, live tokens, or host-specific credential paths
- [x] `docs/architecture/decisions/README.md` was **not** edited by this task
- [x] Related architecture guide already points at this ADR slot; status-honest language retained (no family picked)

---

## Appendix A — Option decision tree (non-binding; for maintainers)

```text
Need multi-node coordination?
├─ Agent claims / leases / fencing for MCP++ profiles
│    └─ Family C is the natural fit (may coexist under Option D)
├─ External IPFS Cluster pinset / peer service already in ops
│    └─ Family B wrappers (Option B or D-track)
├─ In-process kit roles, tasks, local leadership without external cluster
│    └─ Family A — only after constructor/API repair (Option A or D-track)
└─ Unsure / multiple needs
     └─ Prefer Option D with explicit “authoritative for X” table over silent status quo
```

This appendix is **not** a selection. It is a framing aid for the confirmation owner.

---

## Appendix B — Status and confidence cheat sheet

**Decision status (header / §3):**  
`Proposed` · `Accepted` · `Rejected` · `Superseded` · `Deprecated` · `Unknown`

**Rationale confidence (§4 markers):**

```markdown
**Accepted:** …
**Proposed:** …
**Inferred:** …
**Unknown:** … unknown / maintainer confirmation needed
```

**Forbidden promotion paths without evidence + confirmation rules:**

- Inferred rationale → Accepted decision narrative  
- Proposed authority → Accepted default in guides  
- Documentation-only claim → Accepted production behavior  
- Strong tests for one family → Accepted production default for all multi-node use  

See [`README.md`](./README.md) §§3–4 for full promotion rules.
