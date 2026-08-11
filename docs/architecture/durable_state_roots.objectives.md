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
`-- KSR-G040  Optional-provider projection, facade, and acceptance
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
- Evidence: ksr/authority@1, ksr/contracts@1, ksr/root-cas@1, ksr/recovery@1, ksr/provider@1, ksr/acceptance@1
- Evidence criteria: The final root API composes `DurableCoordinationStore`, uses datasets-supplied semantic CIDs unchanged, and passes hermetic corruption, interruption, and concurrent-writer tests.
- Acceptance criteria: ksr/authority@1; ksr/contracts@1; ksr/root-cas@1; ksr/recovery@1; ksr/provider@1; ksr/acceptance@1
- Outputs: ipfs_kit_py/mcp_server/mcplusplus/state_root_contracts.py, ipfs_kit_py/mcp_server/mcplusplus/state_root_adapter.py, ipfs_kit_py/mcp_server/mcplusplus/coordination_storage.py, docs/durable_state_roots.md
- Validation: IPFS_KIT_AUTO_INSTALL_DEPS=0 IPFS_KIT_AUTO_INSTALL_BINARIES=0 python -m pytest -q tests/test_coordination_storage.py tests/test_semantic_state_root_contracts.py tests/test_semantic_state_root_cas.py tests/test_semantic_state_root_recovery.py tests/test_semantic_state_root_adapter.py tests/test_semantic_state_root_acceptance.py tests/test_semantic_state_root_import_safety.py
- Acceptance: Expected semantic CIDs verify without translation; current roots update atomically by CID and revision; restart/replay is deterministic; corruption and ambiguous forks fail closed; two writers cannot silently overwrite; optional provider absence is typed; no daemon, network, install, or mock is required.
- Gap task: KSR-000 through KSR-005
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
