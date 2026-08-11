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
- Each implementation task owns only its declared outputs. KSR-104 is the sole
  repair task allowed to edit MCP++ package exports or final user docs.
- KSR-105 is a post-audit seal and owns only its two declared production
  modules and four focused test modules. It may not edit exports or user docs.
- Validation runs in the candidate worktree and again after merge.
- `tests/test_agent_supervisor_receipts.py` is read-only integration evidence,
  not a completion gate while its baseline `_agent_supervisor_rest_binding`
  import is absent. Workers report that external failure and do not repair it.

## Parallel waves

```text
Wave 0  KSR-000                     reviewed control plane (complete)
Wave 1  KSR-001                     closed contracts (complete)
Wave 2  KSR-002                     verified root CAS (complete)
Wave 3  KSR-003 | KSR-004           crash/recovery | provider adapter (complete)
Wave 4  KSR-005                     facade, acceptance, documentation (complete)
Wave 5  KSR-100                     canonical transport-CID validation (complete)
Wave 6  KSR-101                     verified live root and predecessor chain (complete)
Wave 7  KSR-102                     recovery/publication linearization (complete)
Wave 8  KSR-103                     closed API and semantic dag-json parity (complete)
Wave 9  KSR-104                     repaired acceptance and performance closeout (complete)
Wave 10 KSR-105                     terminal post-audit integrity seal
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

- Status: completed
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

- Status: completed
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

- Status: completed
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

- Status: completed
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

- Status: completed
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

## KSR-100 Reject non-canonical transport-CID aliases

- Status: completed
- Completion: auto
- Is schedulable: true
- Review only: false
- Priority: P0
- Track: cid-integrity
- Depends on: KSR-005
- Goal id: KSR-G050
- Outputs: ipfs_kit_py/mcp_server/mcplusplus/coordination_storage.py, ipfs_kit_py/mcp_server/mcplusplus/state_root_contracts.py, tests/test_semantic_state_root_contracts.py, tests/test_semantic_state_root_cas.py
- Validation: IPFS_KIT_AUTO_INSTALL_DEPS=0 IPFS_KIT_AUTO_INSTALL_BINARIES=0 python -m pytest -q tests/test_coordination_storage.py tests/test_semantic_state_root_contracts.py tests/test_semantic_state_root_cas.py
- Board namespace: durable-state-roots-v1
- Bundle: ksr/repair-integrity
- Parallel lane: ksr-canonical-cid
- Resource class: cpu-small
- Token class: medium
- Estimated tokens: 16000
- Implementation timeout seconds: 5400
- Provider role: codex-implement
- Context budget tokens: 32000
- LLM context budget bytes: 262144
- Plan context: docs/architecture/DURABLE_STATE_ROOTS_PLAN.md sections 4, 5, and 13.1
- Predicted files: ipfs_kit_py/mcp_server/mcplusplus/coordination_storage.py, ipfs_kit_py/mcp_server/mcplusplus/state_root_contracts.py, tests/test_semantic_state_root_contracts.py, tests/test_semantic_state_root_cas.py
- Predicted symbols: existing coordination CID decoder, root-contract CID validation, canonical base32 and minimal-varint checks
- Interfaces: CoordinationTransportCID@canonical-2, DurableStateRoots@1
- Allow concurrent with:
- Conflict policy: Harden and reuse the existing coordination transport-CID decoder. Do not create a new canonicalizer, CID profile, semantic identity helper, block store, database, or datasets import; do not change valid CID vectors.
- Preconditions: Base KSR board is complete at `83793a9b7adedfc4ef534ac5fdc98a509cb225a6`; audit repros prove that an overlong `0x81 0x00` version varint and alternate trailing base32 pad bits are accepted by `StateRootSnapshot`.
- Effects: Enforces one exact lowercase unpadded base32 representation, minimal CID varints, CIDv1, raw or dag-json codec, sha2-256 multihash, and a 32-byte digest at every root-contract and coordination-storage CID boundary.
- Acceptance: Canonical datasets-profile source and structured vectors remain byte-for-byte unchanged; non-minimal version/codec/multihash/length varints, non-zero pad-bit aliases, uppercase, malformed, wrong-codec, wrong-hash, and wrong-length CIDs fail closed; root contracts and store operations agree on every positive and negative vector.

## KSR-101 Verify live roots and the full indexed predecessor chain

- Status: completed
- Completion: auto
- Is schedulable: true
- Review only: false
- Priority: P0
- Track: live-integrity
- Depends on: KSR-100
- Goal id: KSR-G050
- Outputs: ipfs_kit_py/mcp_server/mcplusplus/coordination_storage.py, tests/test_semantic_state_root_cas.py, tests/test_semantic_state_root_recovery.py
- Validation: IPFS_KIT_AUTO_INSTALL_DEPS=0 IPFS_KIT_AUTO_INSTALL_BINARIES=0 python -m pytest -q tests/test_coordination_storage.py tests/test_semantic_state_root_contracts.py tests/test_semantic_state_root_cas.py tests/test_semantic_state_root_recovery.py
- Board namespace: durable-state-roots-v1
- Bundle: ksr/repair-integrity
- Parallel lane: ksr-live-chain
- Resource class: cpu-medium
- Token class: large
- Estimated tokens: 22000
- Implementation timeout seconds: 7200
- Provider role: codex-implement
- Context budget tokens: 40000
- LLM context budget bytes: 327680
- Plan context: docs/architecture/DURABLE_STATE_ROOTS_PLAN.md sections 6, 7, and 13.2
- Predicted files: ipfs_kit_py/mcp_server/mcplusplus/coordination_storage.py, tests/test_semantic_state_root_cas.py, tests/test_semantic_state_root_recovery.py
- Predicted symbols: verified current-root read, root-transition chain verifier, current_state_root, compare_and_swap_state_root
- Interfaces: DurableCoordinationStore@verified-root-2, StateRootTransition@1
- Allow concurrent with:
- Conflict policy: Verify through the existing immutable-block and SQLite index authorities. Do not trust a row without its blocks, delete corrupt evidence, add a shadow chain cache, change transition schema, or weaken current CAS concurrency.
- Preconditions: KSR-100 canonical CID validation is green; the audit reproduces a corrupt revision-one root that is still returned and can be advanced to revision two.
- Effects: Recomputes each referenced root and transition CID; requires dag-json transition codec and the exact closed field set; validates namespace, operation, revision, expected predecessor, successor, and current-row linkage before a live root is returned or CAS is allowed to advance it.
- Acceptance: Missing/corrupt current blocks, corrupt or raw-codec transition blocks, swapped transition CIDs, tampered SQLite root/revision values, broken predecessors, forks, or field/link mismatches raise `ArtifactIntegrityError`; the method publishes no transition and changes no current row; valid restart and two-process one-winner behavior remains green.

## KSR-102 Linearize recovery with root publication

- Status: completed
- Completion: auto
- Is schedulable: true
- Review only: false
- Priority: P0
- Track: recovery-concurrency
- Depends on: KSR-101
- Goal id: KSR-G060
- Outputs: ipfs_kit_py/mcp_server/mcplusplus/coordination_storage.py, tests/test_semantic_state_root_recovery.py
- Validation: IPFS_KIT_AUTO_INSTALL_DEPS=0 IPFS_KIT_AUTO_INSTALL_BINARIES=0 python -m pytest -q tests/test_coordination_storage.py tests/test_semantic_state_root_cas.py tests/test_semantic_state_root_recovery.py
- Board namespace: durable-state-roots-v1
- Bundle: ksr/repair-recovery
- Parallel lane: ksr-recovery-fence
- Resource class: cpu-medium
- Token class: large
- Estimated tokens: 22000
- Implementation timeout seconds: 7200
- Provider role: codex-implement
- Context budget tokens: 40000
- LLM context budget bytes: 327680
- Plan context: docs/architecture/DURABLE_STATE_ROOTS_PLAN.md sections 6, 7, and 13.3
- Predicted files: ipfs_kit_py/mcp_server/mcplusplus/coordination_storage.py, tests/test_semantic_state_root_recovery.py
- Predicted symbols: recover, root reconstruction writer fence, immutable snapshot boundary, recovery/CAS interleaving seam
- Interfaces: StateRootRecovery@linearizable-2, StateRootCAS@1
- Allow concurrent with:
- Conflict policy: Use the existing SQLite WAL/FULL transaction and `BEGIN IMMEDIATE`, or a tested equivalent generation/rescan protocol. Do not add a lock service, pointer file, second WAL/database, timestamp winner, or deletion of immutable evidence.
- Preconditions: KSR-101 live-chain verification is green; the audit deterministically captures a revision-one block snapshot, commits revision two on another connection, and shows stale recovery replacing the live indexes with revision one while the revision-two block remains.
- Effects: Establishes the recovery block snapshot while fenced against transition publication and holds that ordering through root-index commit; preserves orphan-transition adoption, prior-or-unique-successor interruption behavior, and ambiguous-fork rejection.
- Acceptance: Every orchestrated scan-before-CAS, scan-during-CAS, and commit-before-rebuild interleaving preserves the highest valid committed revision; recovery never decreases a live revision or drops a committed transition row; multi-process writers retain one winner; database loss, all crash boundaries, and corrupt/forked recovery fail closed.

## KSR-103 Align closed contracts, late replay, and semantic dag-json boundaries

- Status: completed
- Completion: auto
- Is schedulable: true
- Review only: false
- Priority: P0
- Track: contract-parity
- Depends on: KSR-101, KSR-102
- Goal id: KSR-G070
- Outputs: ipfs_kit_py/mcp_server/mcplusplus/coordination_storage.py, ipfs_kit_py/mcp_server/mcplusplus/state_root_contracts.py, ipfs_kit_py/mcp_server/mcplusplus/state_root_adapter.py, tests/test_semantic_state_root_contracts.py, tests/test_semantic_state_root_cas.py, tests/test_semantic_state_root_adapter.py, tests/test_semantic_state_root_acceptance.py
- Validation: IPFS_KIT_AUTO_INSTALL_DEPS=0 IPFS_KIT_AUTO_INSTALL_BINARIES=0 python -m pytest -q tests/test_coordination_storage.py tests/test_semantic_state_root_contracts.py tests/test_semantic_state_root_cas.py tests/test_semantic_state_root_recovery.py tests/test_semantic_state_root_adapter.py tests/test_semantic_state_root_acceptance.py
- Board namespace: durable-state-roots-v1
- Bundle: ksr/repair-acceptance
- Parallel lane: ksr-contract-parity
- Resource class: cpu-medium
- Token class: large
- Estimated tokens: 22000
- Implementation timeout seconds: 7200
- Provider role: codex-implement
- Context budget tokens: 40000
- LLM context budget bytes: 327680
- Plan context: docs/architecture/DURABLE_STATE_ROOTS_PLAN.md sections 4, 5, 8, and 13.4
- Predicted files: ipfs_kit_py/mcp_server/mcplusplus/coordination_storage.py, ipfs_kit_py/mcp_server/mcplusplus/state_root_contracts.py, ipfs_kit_py/mcp_server/mcplusplus/state_root_adapter.py, tests/test_semantic_state_root_contracts.py, tests/test_semantic_state_root_cas.py, tests/test_semantic_state_root_adapter.py, tests/test_semantic_state_root_acceptance.py
- Predicted symbols: DurableStateRoots, DurableStateRootAdapter, StateRootSnapshot, StateRootCASResult, current_root, compare_and_swap_root, put_verified, get_verified
- Interfaces: DurableStateRoots@2, StateRootCASResult@2, SemanticStateArtifactStore@1
- Allow concurrent with:
- Conflict policy: Keep generic raw-block support inside `DurableCoordinationStore`, but expose no raw CID as a semantic structured root. Do not import datasets/accelerate, mint or translate semantic identity, discover providers, introduce mocks, or create a second public result schema.
- Preconditions: KSR-100 canonical CIDs, KSR-101 verified live chains, and KSR-102 linearizable reconstruction are green.
- Effects: Makes the protocol-facing facade return only closed typed values; centralizes input validation; rejects inconsistent revision-zero/non-zero expectations; makes an exact same-operation request unchanged even after later revisions; conflicts on operation-ID reuse with different values; requires canonical dag-json CIDs for semantic adapter put/get/root operations.
- Acceptance: Unknown fields/statuses and inconsistent expectations fail before I/O; exact late replay returns typed `UNCHANGED` without incrementing or changing the current root; changed request reuse returns typed `CONFLICT`; raw-codec roots are rejected by the semantic adapter but remain usable by the generic store; exact caller expected CIDs and available/unavailable/failed/corrupt/not-requested provider facts are preserved.

## KSR-104 Close repaired acceptance and performance evidence

- Status: completed
- Completion: auto
- Is schedulable: true
- Review only: false
- Priority: P0
- Track: repair-closeout
- Depends on: KSR-103
- Goal id: KSR-G070
- Outputs: ipfs_kit_py/mcp_server/mcplusplus/coordination_storage.py, ipfs_kit_py/mcp_server/mcplusplus/__init__.py, tests/test_semantic_state_root_acceptance.py, tests/test_semantic_state_root_import_safety.py, tests/test_semantic_state_root_performance.py, docs/durable_state_roots.md
- Validation: IPFS_KIT_AUTO_INSTALL_DEPS=0 IPFS_KIT_AUTO_INSTALL_BINARIES=0 python -m pytest -q tests/test_coordination_storage.py tests/test_semantic_state_root_contracts.py tests/test_semantic_state_root_cas.py tests/test_semantic_state_root_recovery.py tests/test_semantic_state_root_adapter.py tests/test_semantic_state_root_acceptance.py tests/test_semantic_state_root_import_safety.py tests/test_semantic_state_root_performance.py
- Board namespace: durable-state-roots-v1
- Bundle: ksr/repair-acceptance
- Parallel lane: ksr-repair-closeout
- Resource class: cpu-medium
- Token class: large
- Estimated tokens: 22000
- Implementation timeout seconds: 7200
- Provider role: codex-implement
- Context budget tokens: 40000
- LLM context budget bytes: 327680
- Plan context: docs/architecture/DURABLE_STATE_ROOTS_PLAN.md sections 9, 10, 12, 13.1 through 13.5
- Predicted files: ipfs_kit_py/mcp_server/mcplusplus/coordination_storage.py, ipfs_kit_py/mcp_server/mcplusplus/__init__.py, tests/test_semantic_state_root_acceptance.py, tests/test_semantic_state_root_import_safety.py, tests/test_semantic_state_root_performance.py, docs/durable_state_roots.md
- Predicted symbols: public DurableStateRoots exports, repaired audit matrix, deterministic reopen/rebuild counters
- Interfaces: DurableStateRoots@2, DurableStateRootsAcceptance@2, StateRootReopenCost@1
- Allow concurrent with:
- Conflict policy: Add only acceptance, deterministic performance evidence, thin exports, and accurate integration docs. Do not use wall-clock-only gates, hide the known receipt-test collection failure, add a daemon/network dependency, or broaden the feature into a service, CLI, second store, or semantic analyzer.
- Preconditions: KSR-100 through KSR-103 pass independently; base implementation commit and all four audit reproducers remain recorded.
- Effects: Converts every audit reproducer into a regression test; pins a datasets-compatible structured CID vector without importing datasets; proves corruption/recovery/process concurrency/provider/import behavior end to end; avoids unconditional healthy root-index rebuild writes and records structural scan/rebuild counts.
- Acceptance: The complete focused suite and coordination regression pass; all canonical-alias, live-corruption, stale-recovery, late-replay, and raw-root negative cases pass; healthy reopen performs verification but zero root-index rebuild mutations when indexes match; orphan evidence still triggers reconstruction; exact state roots survive restart; two writers cannot overwrite silently; imports remain inert; provider states remain truthful; docs report tested behavior and the known external receipt-test blocker.

## KSR-105 Seal semantic preconditions and reconstruction evidence

- Status: pending
- Completion: auto
- Is schedulable: true
- Review only: false
- Priority: P0
- Track: audit-closure
- Depends on: KSR-104
- Goal id: KSR-G080
- Outputs: ipfs_kit_py/mcp_server/mcplusplus/coordination_storage.py, ipfs_kit_py/mcp_server/mcplusplus/state_root_adapter.py, tests/test_semantic_state_root_contracts.py, tests/test_semantic_state_root_adapter.py, tests/test_semantic_state_root_recovery.py, tests/test_semantic_state_root_acceptance.py
- Validation: IPFS_KIT_AUTO_INSTALL_DEPS=0 IPFS_KIT_AUTO_INSTALL_BINARIES=0 python -m pytest -q tests/test_coordination_storage.py tests/test_semantic_state_root_contracts.py tests/test_semantic_state_root_cas.py tests/test_semantic_state_root_recovery.py tests/test_semantic_state_root_adapter.py tests/test_semantic_state_root_acceptance.py tests/test_semantic_state_root_import_safety.py tests/test_semantic_state_root_performance.py
- Board namespace: durable-state-roots-v1
- Bundle: ksr/post-audit-seal
- Parallel lane: ksr-terminal-audit-seal
- Resource class: cpu-medium
- Token class: large
- Estimated tokens: 18000
- Implementation timeout seconds: 7200
- Provider role: codex-implement
- Context budget tokens: 36000
- LLM context budget bytes: 294912
- Plan context: docs/architecture/DURABLE_STATE_ROOTS_PLAN.md sections 4, 5, 7, 8, and 13.6
- Predicted files: ipfs_kit_py/mcp_server/mcplusplus/coordination_storage.py, ipfs_kit_py/mcp_server/mcplusplus/state_root_adapter.py, tests/test_semantic_state_root_contracts.py, tests/test_semantic_state_root_adapter.py, tests/test_semantic_state_root_recovery.py, tests/test_semantic_state_root_acceptance.py
- Predicted symbols: validate_semantic_dag_json_cid, DurableStateRootAdapter.compare_and_swap_root, DurableStateRootAdapter.recover_roots, DurableCoordinationStore._reconstructed_root_chain, DurableCoordinationStore.recover, root_recovery_metrics
- Interfaces: DurableStateRoots@post-audit-3, StateRootRecovery@codec-closed-3, CoordinationTransportCID@canonical-3, StateRootRebuildMetrics@2
- Allow concurrent with:
- Conflict policy: Preserve generic raw blocks and raw roots inside `DurableCoordinationStore`, but reject raw semantic inputs before adapter I/O and raw transition evidence before reconstruction writes. Reuse the existing CID decoder, closed recovery report, chain verifier, and counters. Do not add a new validator, canonicalizer, result schema, block store, database, WAL, service, provider, datasets import, or accelerator import.
- Preconditions: Clean terminal branch head `b9e7e5be98517056087a1f24c5a8a70484d54334`; KSR-100 through KSR-104 are completed; the independent audit reproduces post-commit adapter failure for a raw expected root, untyped raw-root recovery rejection, raw-transition index reconstruction, the missing same-value `a9 82 00` codec-alias vector, and unpinned delete-plus-insert metric semantics.
- Effects: Validates a non-null semantic expected root as dag-json before calling store CAS; returns a closed corrupt `StateRootRecoveryReport` with no reconstructed roots when semantic recovery encounters a raw root; requires each root-transition block CID itself to use dag-json before any rebuild/index mutation; tests the canonical `a9 02` to non-minimal same-value `a9 82 00` codec encoding at contract and store boundaries; counts successful root-index rebuild mutations as rows deleted plus rows inserted.
- Acceptance: A raw expected root raises before store CAS and leaves the complete block set, transition rows, and current-root row byte-for-byte unchanged; raw reconstructed roots return a typed corrupt recovery report with no roots; raw-codec transition blocks raise `ArtifactIntegrityError` before rebuild changes artifacts, transitions, or current roots; a true `a9 82 00` dag-json codec alias is rejected while every canonical vector is preserved; a successful explicit two-transition/one-namespace rebuild records exactly six root-index mutations (two transition deletes, one root delete, two transition inserts, one root insert), healthy reopen records zero, and rollback/failure never claims committed mutations; the complete focused matrix remains green and generic raw coordination storage still works.
