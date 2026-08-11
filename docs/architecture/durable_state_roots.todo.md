# Durable semantic-state roots implementation board

Executable projection of
[`durable_state_roots.objectives.md`](./durable_state_roots.objectives.md) and
[`DURABLE_STATE_ROOTS_PLAN.md`](./DURABLE_STATE_ROOTS_PLAN.md).

This is the sole active board for namespace `durable-state-roots-v1` and uses
task prefix `## KSR-`.

## Execution policy

- `DURABLE_STATE_ROOTS_PLAN.md`, this board, and the objective heap are
  protected operator inputs. Workers may read but never rewrite them.
- All work composes
  `ipfs_kit_py.mcp_server.mcplusplus.coordination_storage.DurableCoordinationStore`.
  Creating another CAS, block directory, content database, or root JSON store
  is out of scope.
- `ipfs_datasets_py.logic.software_contracts.content` remains the semantic CID
  authority. Kit accepts the caller's mandatory expected CID and verifies it;
  it never translates or replaces semantic identity.
- SQLite root indexes are rebuildable acceleration. Existing immutable blocks
  and valid immutable root transitions are recovery authority.
- No task imports datasets or accelerate from kit production code. Contract
  fixtures and injected test doubles are sufficient for focused validation.
- Optional IPFS/Helia capabilities are injected. No task installs, discovers,
  starts, or silently mocks a provider.
- `IPFS_KIT_AUTO_INSTALL_DEPS=0` and
  `IPFS_KIT_AUTO_INSTALL_BINARIES=0` apply to every validation command.
- Each implementation task owns only its declared outputs. KSR-005 is the sole
  pending task allowed to edit MCP++ package exports or final user docs.
- Validation runs in the candidate worktree and again after merge.
- `tests/test_agent_supervisor_receipts.py` is read-only integration evidence,
  not a completion gate while its baseline `_agent_supervisor_rest_binding`
  import is absent. Workers report that external failure and do not repair it.

## Parallel waves

```text
Wave 0  KSR-000                     reviewed control plane (complete)
Wave 1  KSR-001                     closed contracts
Wave 2  KSR-002                     verified root CAS
Wave 3  KSR-003 | KSR-004           crash/recovery | provider adapter
Wave 4  KSR-005                     facade, acceptance, documentation
```

## KSR-000 Inspect and freeze durable-state authorities

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P0
- Track: authority
- Depends on:
- Goal id: KSR-G010
- Outputs: docs/architecture/DURABLE_STATE_ROOTS_PLAN.md, docs/architecture/durable_state_roots.objectives.md, docs/architecture/durable_state_roots.todo.md
- Validation: test -s docs/architecture/DURABLE_STATE_ROOTS_PLAN.md && test -s docs/architecture/durable_state_roots.objectives.md && test -s docs/architecture/durable_state_roots.todo.md && rg -q "5a7a2df8181cfdc33bc19be09989df7ff83f2d4e" docs/architecture/DURABLE_STATE_ROOTS_PLAN.md && rg -q "DurableCoordinationStore" docs/architecture/DURABLE_STATE_ROOTS_PLAN.md
- Board namespace: durable-state-roots-v1
- Bundle: ksr/authority
- Parallel lane: ksr-authority
- Resource class: io-static-analysis
- Token class: medium
- Estimated tokens: 12000
- Implementation timeout seconds: 3600
- Provider role: codex-implement
- Context budget tokens: 20000
- LLM context budget bytes: 163840
- Plan context: docs/architecture/DURABLE_STATE_ROOTS_PLAN.md sections 1 through 3
- Predicted files: docs/architecture/DURABLE_STATE_ROOTS_PLAN.md, docs/architecture/durable_state_roots.objectives.md, docs/architecture/durable_state_roots.todo.md
- Predicted symbols: DurableCoordinationStore, BlockBackend, IPFSHeliaBlockBackend, StateRootCAS authority boundary
- Interfaces: DurableCoordinationStore@reviewed, McpPlusPlusCIDArtifacts@dc316465, SoftwareContractCIDProfile@external-authority
- Allow concurrent with:
- Conflict policy: Inspection and control documents only. Do not implement production code, alter reviewed authorities, initialize external submodules, or treat an existing CID helper as permission to create a semantic identity authority.
- Preconditions: Clean worktree at `5a7a2df8181cfdc33bc19be09989df7ff83f2d4e`; earlier review `69091bf8f11a3ef1fb0e04e11a6d8a4c87f3fa78`; MCP++ review `dc3164653a48d059ae9812078359daeafb451c07`.
- Effects: Records exact revisions, inspected storage/recovery tests, sole-authority boundaries, missing root capabilities, proposed files, public contracts, atomic ordering, recovery rules, non-goals, and executable waves.
- Acceptance: All three protected documents are present and parser-compatible; they explicitly require composition of `DurableCoordinationStore`, preserve datasets semantic CIDs, and prohibit a second block store, daemon requirement, mock fallback, or unrelated refactor.

## KSR-001 Define closed state-root contracts

- Status: todo
- Completion: auto
- Is schedulable: true
- Review only: false
- Priority: P0
- Track: contracts
- Depends on: KSR-000
- Goal id: KSR-G010
- Outputs: ipfs_kit_py/mcp_server/mcplusplus/state_root_contracts.py, tests/test_semantic_state_root_contracts.py
- Validation: IPFS_KIT_AUTO_INSTALL_DEPS=0 IPFS_KIT_AUTO_INSTALL_BINARIES=0 python -m pytest -q tests/test_semantic_state_root_contracts.py
- Board namespace: durable-state-roots-v1
- Bundle: ksr/contracts
- Parallel lane: ksr-contracts
- Resource class: cpu-small
- Token class: medium
- Estimated tokens: 14000
- Implementation timeout seconds: 5400
- Provider role: codex-implement
- Context budget tokens: 28000
- LLM context budget bytes: 229376
- Plan context: docs/architecture/DURABLE_STATE_ROOTS_PLAN.md sections 4 and 5
- Predicted files: ipfs_kit_py/mcp_server/mcplusplus/state_root_contracts.py, tests/test_semantic_state_root_contracts.py
- Predicted symbols: RootUpdateStatus, ProviderStatus, StateRootSnapshot, StateRootCASResult, StateRootRecoveryReport, ArtifactWriteResult, DurableStateRoots
- Interfaces: DurableStateRoots@1, StateRootSnapshot@1, StateRootCASResult@1, StateRootRecoveryReport@1
- Allow concurrent with:
- Conflict policy: Add inert closed contracts only. Do not create storage directories/databases, calculate domain identity, import datasets/accelerate, contact providers, edit `coordination_storage.py`, or export the new API yet.
- Preconditions: KSR-000 authority and profile boundaries are frozen.
- Effects: Defines bounded immutable values for current roots, revisions, CAS outcomes, recovery evidence, local durability, replication status, typed conflicts, typed corruption, and typed unavailability.
- Acceptance: Every contract rejects unknown/invalid status, negative revisions, malformed namespaces/CIDs, inconsistent before/after revisions, and false durable/replicated claims; deterministic round trips preserve all fields; no constructor performs I/O or semantic CID generation.

## KSR-002 Add revisioned root CAS to DurableCoordinationStore

- Status: todo
- Completion: auto
- Is schedulable: true
- Review only: false
- Priority: P0
- Track: root-cas
- Depends on: KSR-001
- Goal id: KSR-G020
- Outputs: ipfs_kit_py/mcp_server/mcplusplus/coordination_storage.py, tests/test_semantic_state_root_cas.py
- Validation: IPFS_KIT_AUTO_INSTALL_DEPS=0 IPFS_KIT_AUTO_INSTALL_BINARIES=0 python -m pytest -q tests/test_coordination_storage.py tests/test_semantic_state_root_cas.py
- Board namespace: durable-state-roots-v1
- Bundle: ksr/persistence
- Parallel lane: ksr-root-cas
- Resource class: cpu-medium
- Token class: large
- Estimated tokens: 22000
- Implementation timeout seconds: 7200
- Provider role: codex-implement
- Context budget tokens: 40000
- LLM context budget bytes: 327680
- Plan context: docs/architecture/DURABLE_STATE_ROOTS_PLAN.md sections 3 through 6
- Predicted files: ipfs_kit_py/mcp_server/mcplusplus/coordination_storage.py, tests/test_semantic_state_root_cas.py
- Predicted symbols: STATE_ROOT_TRANSITION_SCHEMA, current_state_root, compare_and_swap_state_root, state_roots, root_transitions
- Interfaces: DurableCoordinationStore@root-cas-1, StateRootTransition@1, StateRootCAS@1
- Allow concurrent with:
- Conflict policy: Extend the existing immutable block and SQLite-WAL transaction authority. Do not create another block store, pointer file, SQLite database, canonicalizer, CID profile, or lock service. Preserve all existing coordination artifact behavior and migrations.
- Preconditions: Closed KSR-001 contracts exist; successor semantic artifacts arrive through `put` with a mandatory datasets-computed expected CID.
- Effects: Adds rebuildable root/transition indexes and namespaced CID-plus-revision CAS under `BEGIN IMMEDIATE`; verifies the successor block before visibility; publishes an immutable transition and current-root row atomically; supports idempotent same-operation replay and typed stale conflicts.
- Acceptance: A missing or corrupt successor never becomes current; revision starts at zero and increases exactly once per distinct accepted transition; stale CID or revision cannot overwrite; two threads/processes using one expectation yield one distinct winner; identical operation replay is unchanged; existing coordination tests pass.

## KSR-003 Prove interruption recovery, reconstruction, and corruption handling

- Status: todo
- Completion: auto
- Is schedulable: true
- Review only: false
- Priority: P0
- Track: recovery
- Depends on: KSR-002
- Goal id: KSR-G030
- Outputs: ipfs_kit_py/mcp_server/mcplusplus/coordination_storage.py, tests/test_semantic_state_root_recovery.py
- Validation: IPFS_KIT_AUTO_INSTALL_DEPS=0 IPFS_KIT_AUTO_INSTALL_BINARIES=0 python -m pytest -q tests/test_coordination_storage.py tests/test_semantic_state_root_cas.py tests/test_semantic_state_root_recovery.py
- Board namespace: durable-state-roots-v1
- Bundle: ksr/recovery
- Parallel lane: ksr-recovery
- Resource class: cpu-medium
- Token class: large
- Estimated tokens: 22000
- Implementation timeout seconds: 7200
- Provider role: codex-implement
- Context budget tokens: 40000
- LLM context budget bytes: 327680
- Plan context: docs/architecture/DURABLE_STATE_ROOTS_PLAN.md sections 6 and 7
- Predicted files: ipfs_kit_py/mcp_server/mcplusplus/coordination_storage.py, tests/test_semantic_state_root_recovery.py
- Predicted symbols: recover_state_roots, state_root_crash_injector, root transition chain validation, StateRootRecoveryReport
- Interfaces: StateRootRecovery@1, RootTransitionCrashMatrix@1
- Allow concurrent with: KSR-004
- Conflict policy: Build recovery into the existing immutable-block scan and index reconstruction. Do not accept lexical/timestamp winner selection, delete corrupt evidence, weaken CID verification, invent a second WAL, or edit the provider adapter owned by KSR-004.
- Preconditions: KSR-002 root transitions and CAS are green.
- Effects: Injects crashes before transaction, after comparison, after transition fsync, after indexing, before commit, and after commit; reconstructs valid chains after SQLite loss; detects corrupt/missing successors, invalid revisions, duplicate operations, and ambiguous forks.
- Acceptance: Every crash boundary recovers to the verified prior root or one unique successor; replay does not double-increment; database reconstruction reproduces current roots; ambiguity and corruption fail closed with bounded evidence; process-level concurrent distinct writers never silently overwrite.

## KSR-004 Add the thin provider-aware state-root adapter

- Status: todo
- Completion: auto
- Is schedulable: true
- Review only: false
- Priority: P0
- Track: adapter
- Depends on: KSR-002
- Goal id: KSR-G040
- Outputs: ipfs_kit_py/mcp_server/mcplusplus/state_root_adapter.py, tests/test_semantic_state_root_adapter.py
- Validation: IPFS_KIT_AUTO_INSTALL_DEPS=0 IPFS_KIT_AUTO_INSTALL_BINARIES=0 python -m pytest -q tests/test_coordination_storage.py tests/test_semantic_state_root_contracts.py tests/test_semantic_state_root_cas.py tests/test_semantic_state_root_adapter.py
- Board namespace: durable-state-roots-v1
- Bundle: ksr/integration
- Parallel lane: ksr-provider-adapter
- Resource class: cpu-small
- Token class: medium
- Estimated tokens: 16000
- Implementation timeout seconds: 5400
- Provider role: codex-implement
- Context budget tokens: 32000
- LLM context budget bytes: 262144
- Plan context: docs/architecture/DURABLE_STATE_ROOTS_PLAN.md sections 4, 5, and 8
- Predicted files: ipfs_kit_py/mcp_server/mcplusplus/state_root_adapter.py, tests/test_semantic_state_root_adapter.py
- Predicted symbols: DurableStateRootAdapter, put_verified, get_verified, current_root, compare_and_swap_root, recover_roots, ProviderStatus
- Interfaces: DurableStateRoots@1, StateRootProviderAvailability@1
- Allow concurrent with: KSR-003
- Conflict policy: The adapter owns no blocks, directory, database, canonicalizer, or provider discovery. Compose an injected `DurableCoordinationStore` and its existing `IPFSHeliaBlockBackend`; never import datasets/accelerate, start/install a daemon, silently disable requested replication, or use a mock in production.
- Preconditions: KSR-001 contracts and KSR-002 store operations exist.
- Effects: Requires caller-supplied expected CIDs for semantic artifacts; projects verified reads/root operations; distinguishes local durability from available/unavailable/failed/corrupt/not-requested replication; exposes explicit local-only behavior for hermetic use.
- Acceptance: The adapter preserves the exact expected CID; mismatches fail before root update; absent requested provider returns typed unavailable; provider mismatch returns corrupt; optional failure does not become a false replicated claim; local-only operation passes without network or daemon.

## KSR-005 Publish the facade and close the acceptance matrix

- Status: todo
- Completion: auto
- Is schedulable: true
- Review only: false
- Priority: P0
- Track: closeout
- Depends on: KSR-003, KSR-004
- Goal id: KSR-G040
- Outputs: ipfs_kit_py/mcp_server/mcplusplus/__init__.py, tests/test_semantic_state_root_acceptance.py, tests/test_semantic_state_root_import_safety.py, docs/durable_state_roots.md
- Validation: IPFS_KIT_AUTO_INSTALL_DEPS=0 IPFS_KIT_AUTO_INSTALL_BINARIES=0 python -m pytest -q tests/test_coordination_storage.py tests/test_semantic_state_root_contracts.py tests/test_semantic_state_root_cas.py tests/test_semantic_state_root_recovery.py tests/test_semantic_state_root_adapter.py tests/test_semantic_state_root_acceptance.py tests/test_semantic_state_root_import_safety.py
- Board namespace: durable-state-roots-v1
- Bundle: ksr/acceptance
- Parallel lane: ksr-closeout
- Resource class: cpu-medium
- Token class: large
- Estimated tokens: 22000
- Implementation timeout seconds: 7200
- Provider role: codex-implement
- Context budget tokens: 40000
- LLM context budget bytes: 327680
- Plan context: docs/architecture/DURABLE_STATE_ROOTS_PLAN.md sections 9 through 12
- Predicted files: ipfs_kit_py/mcp_server/mcplusplus/__init__.py, tests/test_semantic_state_root_acceptance.py, tests/test_semantic_state_root_import_safety.py, docs/durable_state_roots.md
- Predicted symbols: public DurableStateRoots exports, complete root persistence acceptance matrix
- Interfaces: DurableStateRoots@1, DurableStateRootsAcceptance@1
- Allow concurrent with:
- Conflict policy: Keep exports thin and side-effect free. Document only tested behavior. Do not add a CLI/server/UI, broaden MCP registration, repair unrelated imports/tests, hide regressions, initialize network providers, or weaken conflict/corruption assertions.
- Preconditions: KSR-003 recovery and KSR-004 adapter suites pass independently.
- Effects: Publishes the narrow contracts/adapter, tests datasets-style expected CID preservation, deterministic root identity, stale/failed CAS, interrupted transition recovery, concurrent writers, optional provider states, and import safety; documents integration for the accelerator harness.
- Acceptance: The complete focused suite and existing coordination/receipt regressions pass; two writers cannot silently overwrite; interrupted writes recover; corrupt blocks fail closed; unavailable providers stay typed; ordinary import performs no install/network/process/thread/filesystem/environment mutation; documentation states that datasets owns semantic identity and `DurableCoordinationStore` owns storage.
