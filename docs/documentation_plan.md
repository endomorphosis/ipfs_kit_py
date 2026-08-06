# IPFS Kit documentation and architecture program

- Status: active
- Program namespace: `ipfs-kit-documentation-architecture-v2`
- Task prefix: `KDOC-`
- Goal prefix: `KDOC-G`
- Baseline: repository commit `f6a574375febbcf9a46fcd24bbc7bc5cfb551de5`
- Plan last verified: 2026-08-03

This is the canonical human-readable plan for refreshing the `ipfs_kit_py`
documentation. It supersedes the February 2026 claim in the previous version
of this file that all documentation work was complete.

Companion control documents:

- [Goal and subgoal heap](architecture/ipfs_kit_documentation.objectives.md)
- [Executable supervisor task board](architecture/ipfs_kit_documentation.todo.md)

The plan is intentionally documentation-only. Workers may inspect source,
tests, packaging metadata, Git history, and runtime help, but program outputs
belong under `docs/`. A discovered code defect is recorded as a documentation
gap or follow-up; it is not silently fixed by a documentation task.

## 1. Why this program exists

The documentation needs another pass for two independent reasons.

First, the implementation and packaging surface have changed. The current
tree includes, among other things, the consolidated CLI dispatcher, the
`mcp_server` MCP++ surface, a side-effect-free backend type registry, Iroh
backend and service support, lazy compatibility loading, and updated archival
boundaries. Existing authored and generated material does not consistently
describe those changes.

Second, the repository needs a durable explanation of its bespoke system.
Developers and agents need more than method lists: they need component
boundaries, data and control flows, invariants, failure behavior, extension
points, and the reasons behind choices such as lazy optional imports, one MCP
tool registry across several interfaces, content-addressed state, rebuildable
indexes, AnyIO boundaries, and coexistence of multiple storage/network
backends.

### 1.1 Evidence from the current tree

The planning audit found:

- `docs/` contains about 440 files, including 396 Markdown files and 34 Python
  files. Much of the Python content is embedded third-party project material,
  not authored product documentation.
- `docs/README.md`, `docs/index.md`, and `docs/DOCUMENTATION_INDEX.md` are
  competing navigation surfaces with roughly 1,400 lines between them.
- Most files in `implementation/`, `status_reports/`, and `fixes/` are dated
  completion reports but remain mixed into current navigation.
- Existing architecture documents predate major MCP++, Iroh, unified CLI, and
  backend-registry work.
- `docs/api_generated/module_structure.md` identifies an October 2025
  generation date and covers far fewer modules than the present package.
- Some guidance names missing scripts or obsolete APIs. For example,
  `docs/index.md` points at a nonexistent root `start_3_node_cluster.py`, and
  `docs/development/async_architecture.md` recommends APIs that AnyIO does not
  provide.
- The source tree itself contains compatibility layers and parallel-looking
  implementations. Documentation must identify the canonical path and label
  compatibility, experimental, deprecated, and historical surfaces rather
  than presenting every module as equally authoritative.

Previous documentation-supervisor work in July 2026 improved reachability of
many files. This program does not repeat that link-only campaign. It verifies
claims against the current tree, establishes the canonical architecture, and
then integrates navigation.

## 2. Program outcome

At completion, a developer or agent should be able to answer all of the
following without reverse-engineering the whole repository:

1. What is `ipfs_kit_py`, which entry points are supported, and which modules
   are compatibility shims or historical implementations?
2. How do Python, CLI, daemon/service, MCP/JSON-RPC, and filesystem surfaces
   reach shared capabilities?
3. How do content, metadata, pins, buckets, VFS state, journals, WAL/CAR data,
   caches, and remote backends relate?
4. How do Kubo/IPFS, Iroh, libp2p, cluster roles, routing, replication, and
   coordination coexist, and where are consistency boundaries?
5. How are optional dependencies, sync/async compatibility, process
   lifecycle, retries, health, and graceful degradation handled?
6. Where are credentials and mutable state stored, what crosses a trust
   boundary, and what must never be logged or embedded in docs?
7. Why were the major architectural choices made, what trade-offs were
   accepted, and which alternatives were rejected or remain open?
8. What code and tests prove each claim, and what change should trigger a
   documentation review?

## 3. Documentation contract

### 3.1 Authority classes

Every maintained document must make its authority clear.

| Class | Meaning | Update rule |
|---|---|---|
| Canonical | Current conceptual, task, operational, or reference guidance | Must cite current source/tests and carry a verification date or baseline |
| Generated | Deterministic output from code or packaging metadata | Never hand-maintained except generator templates; drift must be detectable |
| Historical | A dated implementation report, migration record, result, or superseded design | Retained for provenance, excluded from current recommendations |
| External | Vendored or gitlinked upstream material | Ownership and revision are explicit; excluded from authored-doc coverage |
| Proposed | A design or ADR not yet reflected in current behavior | Must not be written as an implemented capability |

### 3.2 Source policy

Claims are ordered by authority:

1. executable behavior and focused tests;
2. packaging and entry-point metadata;
3. public source contracts, schemas, and docstrings;
4. Git history and accepted decision records;
5. current documentation;
6. inference.

An inferred rationale must be labeled **inferred**. An unknown rationale is
recorded as **unknown / maintainer confirmation needed**. Agents must not turn
a plausible explanation into historical fact.

### 3.3 Required architecture-guide sections

Every canonical architecture guide contains:

- scope and explicit non-goals;
- supported/canonical surfaces and compatibility status;
- component ownership and source-of-truth paths;
- data flow and control flow, with a small diagram where useful;
- invariants and consistency or ordering guarantees;
- process, async, and lifecycle boundaries;
- trust boundaries and sensitive-data handling;
- expected failures, degraded modes, and observability;
- extension points and safe modification guidance;
- design rationale, trade-offs, and rejected alternatives with confidence;
- tests or fixtures that verify the behavior;
- change triggers and last-verified baseline.

### 3.4 Writing rules for agents

- Inspect implementation and focused tests before editing a claim.
- Prefer stable concepts over exhaustive inventories in authored guides.
- Put exhaustive signatures and module listings in generated/reference
  material.
- Do not import optional modules merely to inventory them when AST/static
  inspection is sufficient.
- Set `IPFS_KIT_AUTO_INSTALL_BINARIES=0` for documentation validation.
- Do not initialize or fetch external documentation gitlinks.
- Use runnable, offline examples by default. Mark daemon, credential, network,
  or platform prerequisites explicitly.
- Never put real credentials, host-specific paths, or live tokens in examples.
- Do not describe a stub, fallback, archived file, or optional adapter as a
  production default without evidence.

## 4. Target information architecture

The program evolves the existing tree incrementally; it does not perform a
single disruptive mass move.

```text
docs/
├── index.md                         # concise canonical landing page
├── README.md                        # repository-oriented documentation map
├── getting-started/                 # verified install and first-success paths
├── architecture/
│   ├── README.md                    # architecture map and reading order
│   ├── SYSTEM_OVERVIEW.md
│   ├── RUNTIME_AND_ENTRYPOINTS.md
│   ├── STORAGE_BACKEND_SYSTEM.md
│   ├── CONTENT_METADATA_VFS.md
│   ├── CLUSTER_COORDINATION.md
│   ├── MCP_CONTROL_PLANE.md
│   ├── ASYNC_AND_OPTIONAL_DEPENDENCIES.md
│   ├── CONFIGURATION_STATE_AND_TRUST.md
│   ├── NETWORK_TRANSPORTS.md
│   ├── COMPATIBILITY_LAYERS.md
│   └── decisions/
├── guides/                          # task-oriented developer/user guidance
├── operations/                      # deployment, lifecycle, recovery, telemetry
├── reference/                       # exact configuration and capability facts
├── integration/                     # boundaries with datasets and other systems
├── development/                     # contributing, testing, change-impact guidance
├── iroh/                            # retained normative Iroh contracts/runbooks
├── api_generated/                   # generator-owned API inventory
├── audits/                          # dated evidence, inventories, final scorecard
└── ARCHIVE/                         # explicitly non-current historical material
```

The three embedded `py-ipld-*` project snapshots and external documentation
gitlinks receive an ownership/boundary record. They are not counted as
authored `ipfs_kit_py` documentation.

## 5. Goal hierarchy

The durable goal descriptions and acceptance gates live in the
[objective heap](architecture/ipfs_kit_documentation.objectives.md). In
summary:

- **KDOC-G000 — trustworthy, current, rationale-rich documentation**
  - **KDOC-G010 — evidence-backed baseline and governance**
    - corpus/freshness inventory;
    - public-surface and source-of-truth maps;
    - documentation lifecycle and claim standard.
  - **KDOC-G020 — bespoke architecture guide set**
    - system context and runtime composition;
    - storage/content/VFS data plane;
    - cluster and network coordination;
    - MCP/CLI/API control surfaces;
    - async, optional dependency, configuration, state, and trust boundaries.
  - **KDOC-G030 — architectural decision record set**
    - ADR template and index;
    - evidence-backed choices, trade-offs, rejected alternatives, and unknowns.
  - **KDOC-G040 — refreshed developer and operator journeys**
    - installation, quick start, Python API, CLI, MCP, configuration,
      storage, VFS, cluster, Iroh, integrations, testing, and contribution.
  - **KDOC-G050 — coherent information architecture and history boundary**
    - one canonical navigation path;
    - explicit historical/generated/external classification;
    - controlled duplicate reconciliation.
  - **KDOC-G060 — repeatable freshness and quality controls**
    - generated-doc contract, validation runbook, ownership, and scorecard.
  - **KDOC-G070 — agent-oriented system understanding**
    - compact system map, change-impact map, and subsystem debugging guide.
  - **KDOC-G080 — program integration and acceptance**
    - current-tree verification, navigation, and evidence-backed closeout.

## 6. Execution waves and dependencies

```text
Wave 0: evidence and governance (KDOC-001..006, parallel)
    │
    ├── Wave 1A: architecture guides (KDOC-010..019, parallel by subsystem)
    │       └── Wave 2A: ADRs (KDOC-020..027, parallel by decision)
    │
    ├── Wave 1B: current user/reference docs (KDOC-030..039, parallel)
    │
    └── Wave 1C: history/external/generated boundaries (KDOC-041..046)
            │
            ├── Wave 2B: agent maps and maintenance controls (KDOC-050..053)
            │
            └── Wave 3: navigation, final audit, scorecard (KDOC-060..063)
```

Dependencies are evidence dependencies, not blanket serialization. For
example, the storage architecture task waits for the source-of-truth map but
does not wait for the MCP guide. Tasks that modify shared navigation are held
until subsystem authorship is complete.

## 7. Parallel lanes and file ownership

| Lane/bundle | Exclusive outputs | May run with |
|---|---|---|
| `kdoc/evidence-corpus` | `docs/audits/DOCUMENTATION_INVENTORY.md`, freshness/history registers | all other Wave 0 evidence tasks |
| `kdoc/evidence-surfaces` | public surface and architecture evidence maps | evidence/governance lanes |
| `kdoc/governance` | lifecycle, style, claim, diagram, and provenance standards | evidence lanes |
| `kdoc/arch-runtime` | system overview, entry points, compatibility layers | storage, cluster, MCP, trust lanes |
| `kdoc/arch-storage` | backend and content/VFS architecture | runtime, cluster, MCP, trust lanes |
| `kdoc/arch-distributed` | cluster and network architecture | runtime, storage, MCP, trust lanes |
| `kdoc/arch-control` | MCP/control-plane architecture | runtime, storage, cluster, trust lanes |
| `kdoc/arch-trust` | async/dependencies and configuration/state/trust guides | other architecture lanes |
| `kdoc/adrs` | one ADR per task; ADR index is separately owned | other decision files after the template exists |
| `kdoc/current-*` | explicitly named current guides/references | other current-doc bundles with disjoint files |
| `kdoc/history` | historical classification and later curated source directories | only after inventories; never concurrent with navigation |
| `kdoc/navigation` | `docs/index.md`, `docs/README.md`, `docs/DOCUMENTATION_INDEX.md`, architecture index | final integration only |
| `kdoc/quality` | validation contract and final reports | final waves |

No task may edit another bundle's declared `Outputs:`. Shared navigation files
are owned only by the integration tasks. The plan, objective heap, and task
board are protected operator inputs and are never implementation-task outputs.

## 8. Definition of done

### 8.1 Per-document gate

A maintained document is complete only when:

- every material current-state claim has a source/test reference;
- examples match the current public entry point and identify prerequisites;
- canonical, compatibility, optional, experimental, and historical status is
  explicit;
- links are repository-relative and resolve in the checked-out tree;
- unsupported or ambiguous behavior is labeled rather than guessed;
- no sensitive data or machine-specific state is embedded;
- its task's offline validation command passes.

### 8.2 Program gate

The root goal closes only when:

- all leaf tasks are complete on the merge target, not merely marked complete
  in lane-local state;
- the architecture set covers every supported entry point and major stateful
  subsystem;
- the ADR index links every delivered decision and records confidence/status;
- refreshed user/reference docs agree with `pyproject.toml`, CLI help, public
  source contracts, and focused tests;
- one canonical index distinguishes current, generated, historical, and
  external content;
- documentation generation and validation have a reproducible contract;
- the final audit records zero broken canonical links, zero unclassified
  maintained documents, and no known high-severity stale claims;
- any unresolved uncertainty has an owner and follow-up instead of an invented
  answer.

## 9. Supervisor operation

Use the established `ipfs_datasets_py` agent-supervisor stack provided by
`ipfs_accelerate_py`; the older local `ipfs_datasets_py.optimizers.todo_daemon`
implementation lacks the cross-lane reservation and strict-sharding controls
required for safe parallel execution.

Run from the `ipfs_kit_py` repository root on branch
`documentation-supervisor/kit-architecture-refresh-20260803`.

### 9.1 Safety and liveness choices

- Four strict shards use the trailing task number modulo four. Wave 0 has at
  least one ready task in every residue class.
- Each shard has an isolated state directory and worktree root.
- All shards share one merge-queue directory and one merge target branch.
- Plan/objective/board files are protected against worker mutation.
- Objective and codebase refill scans are not enabled; the reviewed board is
  the sole source of work.
- `IPFS_KIT_AUTO_INSTALL_BINARIES=0` prevents documentation inspection from
  downloading executables.
- Retry limits convert repeated implementation/validation failures into
  visible diagnostics instead of infinite churn.
- A startup grace period and log-stall threshold prevent slow imports or a
  live implementation from being mistaken for deadlock.

### 9.2 Launch template

The active launch uses the following shape, repeated for shards `0..3`:

```bash
export PYTHONPATH=/path/to/ipfs_accelerate:/path/to/ipfs_datasets
export IPFS_KIT_AUTO_INSTALL_BINARIES=0

python -m ipfs_accelerate_py.agent_supervisor.todo_daemon.implementation_supervisor \
  --todo-path docs/architecture/ipfs_kit_documentation.todo.md \
  --task-prefix '## KDOC-' \
  --state-dir /path/to/state/lane-N \
  --state-prefix kdoc_lane_N \
  --worktree-root /path/to/worktrees/lane-N \
  --merge-queue-dir /path/to/merge-queue \
  --merge-target-branch documentation-supervisor/kit-architecture-refresh-20260803 \
  --task-shard-count 4 \
  --task-shard-index N \
  --strict-task-sharding \
  --implementation-protected-path docs/documentation_plan.md \
  --implementation-protected-path docs/architecture/ipfs_kit_documentation.objectives.md \
  --implementation-protected-path docs/architecture/ipfs_kit_documentation.todo.md \
  --implement
```

Supervisor state is intentionally outside this submodule because its
`data/` directory is not ignored. The active runtime path is
`/home/barberb/.local/state/ipfs_accelerate_py/ipfs-kit-documentation-v2/`.

### 9.3 Health checks

For each lane, inspect:

- `kdoc_lane_N_supervisor.pid` and `kdoc_lane_N_managed_daemon.pid`;
- `kdoc_lane_N_supervisor_status.json` for a recent heartbeat;
- `kdoc_lane_N_task_state.json` for ready/waiting/active counts;
- `kdoc_lane_N_supervisor_events.jsonl` for selection, implementation,
  validation, merge, retry, and recycle events;
- the active implementation log for recent output.

A waiting task is not blocked when its declared dependency is incomplete. A
lane is operationally blocked only when it has an unresolved protected-path or
merge incident, exhausted retries without a repair path, repeated provider
failure past backoff, a stale heartbeat with no live child, or a dependency
reference that cannot ever be satisfied. The operator should repair that
specific condition and preserve the evidence rather than editing status by
hand.

## 10. Risks and controls

| Risk | Control |
|---|---|
| Agents repeat stale documentation claims | Current source/test citations and freshness audit are prerequisites |
| Agents invent architectural rationale | ADR confidence labels and explicit unknown/confirmation state |
| Parallel authors overwrite indexes | Late exclusive navigation lane |
| Mass archival breaks links | Inventory and redirect plan precede any move; one history owner |
| Generated and authored docs diverge | Generator-owned directory and drift contract |
| Optional imports trigger side effects | Static inspection first and binary auto-install disabled |
| Multiple supervisors choose the same task | Strict numeric sharding plus shared task/resource claims |
| Simultaneous merges conflict | Disjoint outputs plus shared merge queue |
| A model loops on a bad task | Bounded implementation, validation, and merge retry budgets |
| Documentation describes aspirations as reality | Status vocabulary and source hierarchy enforced in every task |

## 11. Deliberate non-goals

- Refactoring production code to make the architecture cleaner.
- Proving every historical completion report correct.
- Fetching or rewriting upstream IPFS/libp2p/Filecoin documentation.
- Treating generated API listings as a substitute for conceptual guides.
- Publishing or changing repository-hosting configuration outside `docs/` in
  this program. Workflow changes discovered here become separately authorized
  follow-ups.
- Promoting an inferred design rationale to an accepted ADR without evidence.

## 12. Handoff

Humans should review architecture and ADR content for intent, not just prose.
Agents should begin with the executable board, preserve its dependency and
file-ownership contracts, and use the objective heap when a task needs broader
context. If implementation evidence conflicts with this plan, record the
conflict in the assigned audit/guide and refine the plan through operator
review; do not weaken evidence requirements to make the task appear complete.
