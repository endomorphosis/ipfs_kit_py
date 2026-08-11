# Durable semantic-state roots objective heap

Machine-ingestible goal hierarchy for `ipfs_accelerate_py.agent_supervisor`.
The executable projection is
`docs/architecture/durable_state_roots.todo.md` with task prefix `## KSR-`.
The reviewed human design is
`docs/architecture/DURABLE_STATE_ROOTS_PLAN.md`.

## Goal tree

```text
KSR-G000  Durable content-addressed state-root release
|-- KSR-G010  Frozen identity boundary and closed root contracts
|-- KSR-G020  Atomic revisioned root transitions in DurableCoordinationStore
|-- KSR-G030  Deterministic interruption recovery and concurrency safety
|-- KSR-G040  Optional-provider projection, facade, and acceptance
|-- KSR-G050  Canonical CID and verified live-root evidence
|-- KSR-G060  Linearizable recovery and publication
`-- KSR-G070  Closed semantic adapter and repaired release assurance
```

## KSR-G000 Durable content-addressed state-root release

- Status: active
- Parent:
- Depends on:
- Fib priority: 1
- Priority: P0
- Track: semantic-state-roots
- Bundle: ksr/root
- Goal: Extend the existing MCP++ durable coordination store with generic, revisioned, compare-and-swap state roots that preserve caller-owned semantic CIDs and recover safely without a daemon.
- Evidence: ksr/authority@1, ksr/contracts@2, ksr/root-cas@2, ksr/recovery@2, ksr/provider@1, ksr/acceptance@2
- Evidence criteria: The final root API composes `DurableCoordinationStore`, uses datasets-supplied semantic CIDs unchanged, rejects non-canonical CID aliases, verifies live root chains, linearizes reconstruction with publication, and passes hermetic corruption, interruption, and concurrent-writer tests.
- Acceptance criteria: ksr/authority@1; ksr/contracts@2; ksr/root-cas@2; ksr/recovery@2; ksr/provider@1; ksr/acceptance@2
- Outputs: ipfs_kit_py/mcp_server/mcplusplus/state_root_contracts.py, ipfs_kit_py/mcp_server/mcplusplus/state_root_adapter.py, ipfs_kit_py/mcp_server/mcplusplus/coordination_storage.py, docs/durable_state_roots.md
- Validation: IPFS_KIT_AUTO_INSTALL_DEPS=0 IPFS_KIT_AUTO_INSTALL_BINARIES=0 python -m pytest -q tests/test_coordination_storage.py tests/test_semantic_state_root_contracts.py tests/test_semantic_state_root_cas.py tests/test_semantic_state_root_recovery.py tests/test_semantic_state_root_adapter.py tests/test_semantic_state_root_acceptance.py tests/test_semantic_state_root_import_safety.py tests/test_semantic_state_root_performance.py
- Acceptance: Expected semantic CIDs verify without translation; canonical aliases fail closed; current and predecessor evidence verifies before reads or updates; recovery cannot roll a concurrent commit backward; restart/replay is deterministic; corruption and ambiguous forks fail closed; optional provider absence is typed; no daemon, network, install, or mock is required.
- Gap task: KSR-000 through KSR-005, KSR-100 through KSR-104
- Refinement: Add only root contracts, indexes, transitions, recovery, and a thin adapter around the existing coordination store; never create another block store or semantic identity authority.

## KSR-G010 Frozen identity boundary and closed root contracts

- Status: active
- Parent: KSR-G000
- Depends on:
- Fib priority: 2
- Priority: P0
- Track: contracts
- Bundle: ksr/contracts
- Goal: Freeze the reviewed store/MCP++/datasets authority boundary and define closed typed state-root, CAS, recovery, and provider-availability records.
- Evidence: ksr/authority@1, ksr/contracts@1
- Evidence criteria: Reviews name exact revisions and existing storage behavior; contracts accept caller-supplied CIDs without minting or translating semantic identities.
- Acceptance criteria: ksr/authority@1; ksr/contracts@1
- Outputs: docs/architecture/DURABLE_STATE_ROOTS_PLAN.md, docs/architecture/durable_state_roots.objectives.md, docs/architecture/durable_state_roots.todo.md, ipfs_kit_py/mcp_server/mcplusplus/state_root_contracts.py
- Validation: IPFS_KIT_AUTO_INSTALL_DEPS=0 IPFS_KIT_AUTO_INSTALL_BINARIES=0 python -m pytest -q tests/test_semantic_state_root_contracts.py
- Acceptance: Contracts are immutable, bounded, versioned, round-trip deterministically, distinguish updated/unchanged/conflict/unavailable/corrupt outcomes, and keep datasets as semantic CID authority.
- Gap task: KSR-000, KSR-001
- Refinement: Contract code is inert and imports no datasets, accelerator, backend client, daemon, or installer.

## KSR-G020 Atomic revisioned root transitions in DurableCoordinationStore

- Status: active
- Parent: KSR-G000
- Depends on: KSR-G010
- Fib priority: 3
- Priority: P0
- Track: persistence
- Bundle: ksr/persistence
- Goal: Store verified semantic artifacts and publish namespaced current roots through revisioned expected-old compare-and-swap in the existing coordination store and SQLite-WAL transaction boundary.
- Evidence: ksr/verified-artifact@1, ksr/root-transition@1, ksr/root-cas@1
- Evidence criteria: Immutable blocks remain authoritative; SQLite root rows and transition indexes are rebuildable; root visibility follows referenced-block verification and transactional comparison.
- Acceptance criteria: ksr/verified-artifact@1; ksr/root-transition@1; ksr/root-cas@1
- Outputs: ipfs_kit_py/mcp_server/mcplusplus/coordination_storage.py, tests/test_semantic_state_root_cas.py
- Validation: IPFS_KIT_AUTO_INSTALL_DEPS=0 IPFS_KIT_AUTO_INSTALL_BINARIES=0 python -m pytest -q tests/test_coordination_storage.py tests/test_semantic_state_root_cas.py
- Acceptance: Missing/mismatched successor blocks never become current; CID plus revision prevents ABA and lost updates; identical operation replay is benign; stale distinct successors return a typed conflict; no second CAS/block implementation is created.
- Gap task: KSR-002
- Refinement: Extend the current database migration/recovery path and immutable publication primitives rather than wrapping them with an unrelated pointer store.

## KSR-G030 Deterministic interruption recovery and concurrency safety

- Status: active
- Parent: KSR-G000
- Depends on: KSR-G020
- Fib priority: 5
- Priority: P0
- Track: recovery
- Bundle: ksr/recovery
- Goal: Rebuild state roots from verified immutable transitions and prove prior-or-unique-successor recovery under crashes, database loss, corruption, and concurrent processes.
- Evidence: ksr/crash-matrix@1, ksr/rebuild@1, ksr/concurrency@1, ksr/corruption@1
- Evidence criteria: Every protocol boundary is fault-injected; recovery refuses missing/corrupt referenced blocks and ambiguous same-revision forks.
- Acceptance criteria: ksr/crash-matrix@1; ksr/rebuild@1; ksr/concurrency@1; ksr/corruption@1
- Outputs: ipfs_kit_py/mcp_server/mcplusplus/coordination_storage.py, tests/test_semantic_state_root_recovery.py
- Validation: IPFS_KIT_AUTO_INSTALL_DEPS=0 IPFS_KIT_AUTO_INSTALL_BINARIES=0 python -m pytest -q tests/test_coordination_storage.py tests/test_semantic_state_root_cas.py tests/test_semantic_state_root_recovery.py
- Acceptance: Interrupted updates recover to the verified prior root or one unique successor; replay is idempotent; two distinct successors never both win; corrupt blocks, invalid chains, and ambiguous forks fail closed with bounded evidence.
- Gap task: KSR-003
- Refinement: SQLite is rebuildable acceleration; recovery trusts only verified immutable blocks and valid transition chains.

## KSR-G040 Optional-provider projection, facade, and acceptance

- Status: active
- Parent: KSR-G000
- Depends on: KSR-G020, KSR-G030
- Fib priority: 8
- Priority: P0
- Track: integration
- Bundle: ksr/integration
- Goal: Publish a thin root adapter over `DurableCoordinationStore`, expose truthful optional IPFS/Helia outcomes, and close hermetic acceptance and import-safety gates.
- Evidence: ksr/provider@1, ksr/facade@1, ksr/acceptance@1, ksr/import-safety@1
- Evidence criteria: The adapter owns no bytes, block directory, database, canonicalizer, provider discovery, or fallback mock; existing coordination/receipt regressions stay green.
- Acceptance criteria: ksr/provider@1; ksr/facade@1; ksr/acceptance@1; ksr/import-safety@1
- Outputs: ipfs_kit_py/mcp_server/mcplusplus/state_root_adapter.py, ipfs_kit_py/mcp_server/mcplusplus/__init__.py, tests/test_semantic_state_root_adapter.py, tests/test_semantic_state_root_acceptance.py, tests/test_semantic_state_root_import_safety.py, docs/durable_state_roots.md
- Validation: IPFS_KIT_AUTO_INSTALL_DEPS=0 IPFS_KIT_AUTO_INSTALL_BINARIES=0 python -m pytest -q tests/test_coordination_storage.py tests/test_semantic_state_root_contracts.py tests/test_semantic_state_root_cas.py tests/test_semantic_state_root_recovery.py tests/test_semantic_state_root_adapter.py tests/test_semantic_state_root_acceptance.py tests/test_semantic_state_root_import_safety.py
- Acceptance: Local hermetic persistence is complete without IPFS; requested provider absence/failure/corruption is typed; no simulated provider is reported as durable replication; public imports are side-effect free and the complete focused matrix passes.
- Gap task: KSR-004, KSR-005
- Refinement: Use injected `IPFSHeliaBlockBackend` capabilities and thin exports; do not add an MCP server, network service, CLI, or unrelated storage refactor.

## KSR-G050 Canonical CID and verified live-root evidence

- Status: active
- Parent: KSR-G000
- Depends on: KSR-G040
- Fib priority: 13
- Priority: P0
- Track: integrity
- Bundle: ksr/repair-integrity
- Goal: Reject every non-canonical transport-CID alias and require current-root reads and CAS to verify the complete indexed root/transition chain before returning or advancing it.
- Evidence: ksr/canonical-cid@1, ksr/live-chain@1, ksr/corruption@2
- Evidence criteria: Minimal-varint and canonical-base32 negative vectors fail at every root boundary; block and SQLite tampering cannot be reported as current or used as a CAS predecessor.
- Acceptance criteria: ksr/canonical-cid@1; ksr/live-chain@1; ksr/corruption@2
- Outputs: ipfs_kit_py/mcp_server/mcplusplus/coordination_storage.py, ipfs_kit_py/mcp_server/mcplusplus/state_root_contracts.py, tests/test_semantic_state_root_contracts.py, tests/test_semantic_state_root_cas.py, tests/test_semantic_state_root_recovery.py
- Validation: IPFS_KIT_AUTO_INSTALL_DEPS=0 IPFS_KIT_AUTO_INSTALL_BINARIES=0 python -m pytest -q tests/test_coordination_storage.py tests/test_semantic_state_root_contracts.py tests/test_semantic_state_root_cas.py tests/test_semantic_state_root_recovery.py
- Acceptance: Only canonical CIDv1/base32/raw-or-dag-json/sha2-256 values cross the kit root boundary; current root and predecessor transition evidence is recomputed and linked end to end; corruption produces `ArtifactIntegrityError` without mutation.
- Gap task: KSR-100, KSR-101
- Refinement: Harden and reuse the existing coordination CID decoder; do not add another canonicalizer, block store, semantic identity function, or datasets import.

## KSR-G060 Linearizable recovery and publication

- Status: active
- Parent: KSR-G000
- Depends on: KSR-G050
- Fib priority: 21
- Priority: P0
- Track: concurrency
- Bundle: ksr/repair-recovery
- Goal: Make immutable-block reconstruction linearizable with root publication so a stale recovery snapshot can never reduce or omit a concurrently committed root revision.
- Evidence: ksr/recovery-fence@1, ksr/rebuild-interleaving@1, ksr/process-concurrency@2
- Evidence criteria: Deterministically orchestrated scan/CAS interleavings preserve the newest committed transition; orphan transitions and ambiguous forks retain prior fail-closed behavior.
- Acceptance criteria: ksr/recovery-fence@1; ksr/rebuild-interleaving@1; ksr/process-concurrency@2
- Outputs: ipfs_kit_py/mcp_server/mcplusplus/coordination_storage.py, tests/test_semantic_state_root_recovery.py
- Validation: IPFS_KIT_AUTO_INSTALL_DEPS=0 IPFS_KIT_AUTO_INSTALL_BINARIES=0 python -m pytest -q tests/test_coordination_storage.py tests/test_semantic_state_root_cas.py tests/test_semantic_state_root_recovery.py
- Acceptance: Recovery establishes its authoritative scan under the existing writer fence or a proven equivalent protocol; a committed revision is never rolled back; one-winner CAS and interruption recovery remain deterministic across processes.
- Gap task: KSR-102
- Refinement: Reuse SQLite WAL/FULL and `BEGIN IMMEDIATE`; do not add a lock service, pointer file, second WAL, or lexical/timestamp winner rule.

## KSR-G070 Closed semantic adapter and repaired release assurance

- Status: active
- Parent: KSR-G000
- Depends on: KSR-G050, KSR-G060
- Fib priority: 34
- Priority: P0
- Track: acceptance
- Bundle: ksr/repair-acceptance
- Goal: Align storage and facade behavior with the closed root contracts, enforce the semantic adapter's dag-json boundary, define stable late replay, and close the repaired acceptance/performance matrix.
- Evidence: ksr/contracts@2, ksr/semantic-codec@1, ksr/replay@2, ksr/acceptance@2, ksr/reopen-cost@1
- Evidence criteria: Protocol-facing results are closed typed values; exact operation replay remains unchanged after later revisions; semantic roots reject raw CIDs; audit repros and import/provider gates pass; healthy reopen avoids needless root-index rebuild writes.
- Acceptance criteria: ksr/contracts@2; ksr/semantic-codec@1; ksr/replay@2; ksr/acceptance@2; ksr/reopen-cost@1
- Outputs: ipfs_kit_py/mcp_server/mcplusplus/coordination_storage.py, ipfs_kit_py/mcp_server/mcplusplus/state_root_contracts.py, ipfs_kit_py/mcp_server/mcplusplus/state_root_adapter.py, ipfs_kit_py/mcp_server/mcplusplus/__init__.py, tests/test_semantic_state_root_adapter.py, tests/test_semantic_state_root_acceptance.py, tests/test_semantic_state_root_import_safety.py, tests/test_semantic_state_root_performance.py, docs/durable_state_roots.md
- Validation: IPFS_KIT_AUTO_INSTALL_DEPS=0 IPFS_KIT_AUTO_INSTALL_BINARIES=0 python -m pytest -q tests/test_coordination_storage.py tests/test_semantic_state_root_contracts.py tests/test_semantic_state_root_cas.py tests/test_semantic_state_root_recovery.py tests/test_semantic_state_root_adapter.py tests/test_semantic_state_root_acceptance.py tests/test_semantic_state_root_import_safety.py tests/test_semantic_state_root_performance.py
- Acceptance: The exact public protocol is closed and typed; semantic adapter operations require canonical dag-json CIDs supplied by the caller; late exact replay is unchanged and operation-ID reuse conflicts; all audit repros and focused regressions pass with truthful provider status and inert imports; performance evidence is deterministic and documented.
- Gap task: KSR-103, KSR-104
- Refinement: Keep raw support inside the generic coordination store, keep datasets as semantic identity authority, and use structural counters rather than fragile wall-clock performance thresholds.
