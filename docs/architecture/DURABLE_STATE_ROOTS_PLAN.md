# Durable semantic-state roots through the MCP++ coordination store

## 1. Outcome and scope

This plan adds one narrow, generic state-root capability to `ipfs_kit_py` for
the Python semantic-state coding harness. It does **not** add another content
store. The implementation composes the existing
`ipfs_kit_py.mcp_server.mcplusplus.coordination_storage.DurableCoordinationStore`
for immutable blocks, local durability, optional IPFS/Helia replication,
corruption detection, SQLite-WAL indexing, and index reconstruction.

The capability must provide:

- verified storage and retrieval of caller-identified structured artifacts;
- a namespaced, revisioned current-root reference;
- compare-and-swap root publication;
- atomic local visibility;
- deterministic restart/replay and index reconstruction;
- fail-closed corruption handling;
- safe recovery at injected interruption boundaries;
- typed optional-provider availability; and
- hermetic operation without an IPFS daemon.

The feature is storage infrastructure only. It does not scan repositories,
understand symbols, compile capsules, select tests, execute models, or decide
whether a semantic state is valid.

## 2. Reviewed revisions and inspected authorities

The implementation board was prepared against these exact revisions:

| Repository or authority | Revision | Role |
| --- | --- | --- |
| `ipfs_kit_py` implementation baseline | `5a7a2df8181cfdc33bc19be09989df7ff83f2d4e` | Branch base for this program |
| Earlier `ipfs_kit_py` review | `69091bf8f11a3ef1fb0e04e11a6d8a4c87f3fa78` | Prior reconnaissance reference; confirmed ancestor of the baseline |
| Mcp-Plus-Plus | `dc3164653a48d059ae9812078359daeafb451c07` | Generic MCP-IDL, CID-artifact, receipt, and event-DAG wire authority |

Relevant implementation and tests inspected before planning:

- `ipfs_kit_py/mcp_server/mcplusplus/coordination_storage.py`
  - `DurableCoordinationStore`
  - `BlockBackend`
  - `IPFSHeliaBlockBackend`
  - `cid_for_bytes` and expected-CID verification
  - immutable fsynced block publication
  - SQLite `journal_mode=WAL` and `synchronous=FULL`
  - rebuildable artifact, claim, lease, health, and archive indexes
  - corruption-preserving database replacement and immutable-block recovery
- `tests/test_coordination_storage.py`
  - MCP++ conformance-vector CIDs
  - restart/index rebuild
  - backend read repair
  - fencing, retention, and corruption behavior
- `tests/test_agent_supervisor_receipts.py`
  - current accelerator receipt use of the durable coordination store
- `ipfs_kit_py/core/wal/`
  - reviewed as a separate canonical WAL contract family, but not selected for
    this small extension because `DurableCoordinationStore` already owns the
    relevant SQLite-WAL transaction and immutable-block recovery boundary.

No semantic-state-specific schema was found in the reviewed MCP++ revision.
MCP++ remains the generic transport/envelope authority. The semantic payload
schema and semantic CID profile remain owned by `ipfs_datasets_py`.

Baseline validation at `5a7a2df8` found `tests/test_coordination_storage.py`
green (`7 passed`). `tests/test_agent_supervisor_receipts.py` currently fails
during collection because `ipfs_kit_py.mcp_server.server` does not export the
test's `_agent_supervisor_rest_binding` import. That transport-surface drift
predates this branch and is read-only evidence, not authority to repair an
unrelated MCP route in this program. It must be reported separately and rerun
if its owning surface is repaired; it is not a KSR completion gate.

## 3. Existing authority and the narrow extension

### 3.1 What already exists

`DurableCoordinationStore` already has the storage behavior this feature must
reuse:

1. Structured mappings are serialized deterministically.
2. A real CIDv1 is calculated for the resulting bytes.
3. An optional `expected_cid` is compared before publication.
4. Immutable blocks are written through a same-directory temporary file,
   `fsync`, atomic no-replace link, and parent-directory `fsync`.
5. The SQLite acceleration index uses WAL mode and full synchronous commits.
6. Reads recompute the CID and reject corrupt local or backend bytes.
7. Missing/corrupt derived SQLite state can be rebuilt from immutable blocks.
8. `IPFSHeliaBlockBackend` projects injected Kubo/Helia capabilities without
   requiring one particular provider.

Creating `ipfs_kit_py/durable_state`, a second CAS directory, or a parallel
block database would split content authority and is prohibited by this plan.

### 3.2 What is missing

The existing store does not yet expose:

- a closed state-root contract;
- a namespaced current-root index;
- root generation/revision values;
- expected-root compare-and-swap;
- immutable root-transition records;
- root-chain reconstruction after SQLite loss;
- typed replication-unavailable results; or
- crash injection and concurrency assurance for root transitions.

The program adds only those pieces.

## 4. Content-identity boundary

`ipfs_datasets_py.logic.software_contracts.content` remains the sole semantic
CID authority. A kit adapter must not derive a new semantic identity, translate
one CID profile into another, or accept a digest-shaped pseudo-CID.

For semantic artifacts the caller supplies:

- the closed structured payload; and
- its authoritative `expected_cid`, calculated by datasets.

The kit path then uses `DurableCoordinationStore.put(...,
expected_cid=expected_cid, codec="dag-json")` as an independent integrity
check. Returning the same CID is verification, not a competing declaration of
semantic identity. Reads return exact verified bytes or structured content so
the datasets adapter can run its domain-specific decode-and-recompute check.

Root-transition records are generic kit/MCP++ coordination artifacts and may
use the existing coordination-store CID profile. They reference, but never
replace or reinterpret, the datasets semantic-state CID.

## 5. Proposed public contracts

The implementation should add inert closed contracts under
`ipfs_kit_py/mcp_server/mcplusplus/state_root_contracts.py` and a thin adapter
under `state_root_adapter.py`.

```python
class RootUpdateStatus(str, Enum):
    UPDATED = "updated"
    UNCHANGED = "unchanged"
    CONFLICT = "conflict"
    UNAVAILABLE = "unavailable"
    CORRUPT = "corrupt"

@dataclass(frozen=True, slots=True)
class StateRootSnapshot:
    namespace: str
    root_cid: str | None
    revision: int
    transition_cid: str | None

@dataclass(frozen=True, slots=True)
class StateRootCASResult:
    status: RootUpdateStatus
    before: StateRootSnapshot
    after: StateRootSnapshot
    transition_cid: str | None
    reason_code: str
    local_durable: bool
    replicated: bool

@dataclass(frozen=True, slots=True)
class StateRootRecoveryReport:
    verified_blocks: int
    reconstructed_roots: tuple[StateRootSnapshot, ...]
    ignored_idempotent_transitions: tuple[str, ...]
    errors: tuple[Mapping[str, str], ...]

class DurableStateRoots(Protocol):
    def put_verified(
        self,
        payload: Mapping[str, Any],
        *,
        expected_cid: str,
        replicate: bool = True,
    ) -> ArtifactWriteResult: ...

    def get_verified(self, cid: str) -> Mapping[str, Any]: ...
    def current_root(self, namespace: str) -> StateRootSnapshot: ...
    def compare_and_swap_root(
        self,
        namespace: str,
        *,
        expected_revision: int,
        expected_root_cid: str | None,
        new_root_cid: str,
        operation_id: str,
    ) -> StateRootCASResult: ...
    def recover_roots(self) -> StateRootRecoveryReport: ...
```

Exact names may change to fit nearby conventions, but the behavior and closed
typed outcomes must remain equivalent. Namespace and operation identifiers are
bounded, normalized strings. A root begins at revision zero with no CID.

The comparison includes both expected CID and expected revision. This prevents
silent lost updates and ABA-style reuse of an old CID. If the current root
already equals `new_root_cid` for the same `operation_id`, replay returns
`unchanged` without incrementing the revision. A different successor from a
stale expectation returns `conflict`; it is never silently overwritten.

## 6. Root-transition storage and atomic visibility

Add one generic immutable schema, versioned independently from semantic state:

```text
mcp++/coordination/state-root-transition@1
```

A transition contains at least:

- namespace;
- operation ID/idempotency key;
- expected prior CID and revision;
- successor CID and revision;
- creation/observation value supplied once and retained for replay; and
- schema/version marker.

Extend the existing coordination SQLite schema with rebuildable root and
transition indexes. The immutable transition block and semantic-state block
remain authoritative; SQLite remains an acceleration/visibility structure.

One successful update follows this ordering:

1. Validate namespace, operation ID, expected values, and successor CID shape.
2. Verify that the successor block is present and its bytes match the CID.
3. Enter `BEGIN IMMEDIATE` on the existing SQLite-WAL connection, serializing
   writers across processes.
4. Read and compare the current CID and revision inside that transaction.
5. Reject a stale expectation before publishing a transition block.
6. Durably publish the immutable transition through the existing block path.
7. Index the transition and update the current-root row in the same SQLite
   transaction.
8. Commit under `synchronous=FULL` before returning `updated`.
9. Report optional backend replication separately and truthfully.

No current root becomes visible before its referenced semantic block verifies.
No method may update a root by overwriting a JSON pointer outside this
transaction boundary.

## 7. Recovery and corruption policy

Recovery scans and verifies immutable blocks through the existing store. It
reconstructs root chains by namespace and revision, requiring:

- revision zero or the prior reconstructed revision as the base;
- exact agreement between a transition's expected prior root and the
  reconstructed root;
- a successor revision exactly one greater than its predecessor;
- a present, verified successor artifact block; and
- operation-ID idempotency.

Duplicate byte-identical/idempotent transitions are benign. Competing valid
successors for the same namespace/revision are ambiguous and must fail closed;
recovery must not select a lexical or timestamp winner. A corrupt transition,
tampered semantic block, invalid CID, broken root chain, or corrupt remote
repair is reported and cannot become current.

Crash injection must cover, at minimum:

- before the SQL transaction;
- after expectation verification;
- after transition-block fsync;
- after transition indexing;
- before SQLite commit; and
- immediately after SQLite commit.

After restart, the visible result is either the verified prior root or the one
unique verified successor. It is never a torn mixture. Replaying the same
operation is idempotent.

## 8. Optional provider behavior

The hermetic local coordination store is sufficient for development and tests.
An IPFS daemon is never required. Optional persistence uses the existing
`IPFSHeliaBlockBackend` with an injected capability; the adapter must not
discover, install, start, or simulate a provider.

Provider outcomes are typed:

- `available`: requested replication completed and returned matching content;
- `unavailable`: no requested capability exists;
- `failed`: a capability existed but failed;
- `corrupt`: returned content or CID did not verify; or
- `not_requested`: local-only operation.

Local durability and replication are separate facts. If local publication
succeeds and optional replication fails, the result must say exactly that. A
caller that declares remote replication mandatory may reject admission, but
the adapter cannot relabel a partial outcome as fully replicated and cannot
substitute a mock.

## 9. Files and ownership

The intended implementation footprint is deliberately small:

```text
ipfs_kit_py/mcp_server/mcplusplus/
  coordination_storage.py       # existing block/index authority; root extension
  state_root_contracts.py        # inert closed result/protocol contracts
  state_root_adapter.py          # narrow composition adapter
  __init__.py                    # final lazy/thin exports only

tests/
  test_semantic_state_root_contracts.py
  test_semantic_state_root_cas.py
  test_semantic_state_root_recovery.py
  test_semantic_state_root_adapter.py
  test_semantic_state_root_acceptance.py
  test_semantic_state_root_import_safety.py

docs/durable_state_roots.md
```

The term `semantic` appears in fixture/test intent because this is the first
consumer. Production storage contracts remain generic and payload-opaque.

## 10. Required assurance

Focused tests must prove:

- the datasets-computed expected CID is preserved exactly;
- a mismatched expected CID is rejected before visibility;
- identical payloads and transitions replay deterministically;
- a root never references a missing or corrupt block;
- unrelated namespaces do not conflict;
- a stale CID or revision loses CAS;
- two concurrent writers cannot both publish distinct successors;
- identical concurrent successors are benign and do not advance twice;
- SQLite loss rebuilds roots from immutable verified transitions;
- every interruption boundary recovers to prior or unique successor;
- ambiguous transition forks fail closed;
- local and remote corruption are detected;
- an unavailable provider is typed and never simulated;
- local operation requires no daemon or network; and
- ordinary imports do not install packages, start processes/threads, create
  directories, access the network, or mutate the environment.

The existing coordination-storage tests remain a regression gate. The known
receipt-transport collection failure above remains separately visible and must
not be hidden or repaired incidentally by a root-storage worker.

## 11. Supervisor execution

The executable task board is
`docs/architecture/durable_state_roots.todo.md`; the objective heap is
`docs/architecture/durable_state_roots.objectives.md`. All three control
documents are protected operator inputs and must be passed as protected paths
to the supervisor.

```text
Wave 0  KSR-000                     reviewed control plane (complete)
Wave 1  KSR-001                     contracts (complete)
Wave 2  KSR-002                     root transition and CAS (complete)
Wave 3  KSR-003 | KSR-004           recovery matrix | provider adapter (complete)
Wave 4  KSR-005                     facade, acceptance, docs, regressions (complete)
Wave 5  KSR-100                     canonical transport-CID validation
Wave 6  KSR-101                     verified live root and predecessor chain
Wave 7  KSR-102                     recovery/publication linearization
Wave 8  KSR-103                     closed API and semantic dag-json parity
Wave 9  KSR-104                     repaired acceptance and performance closeout
```

Use direct clean worktrees, external runtime/state directories, four
non-strict lanes so idle workers can borrow ready work, merge claims, and the
explicit `codex-implement` provider role. Disable package/binary auto-install
for all validation. The supervisor must not infer completion from unavailable
providers or from documentation-only changes.

## 12. Non-goals

This program does not implement:

- a second immutable CAS or block directory;
- semantic canonicalization or semantic CID generation;
- repository scanning, capsules, invalidation, context packing, or tests;
- model or prover invocation;
- an MCP server or network service;
- automatic daemon/provider installation;
- provider mocks in a production path;
- a dashboard or user interface;
- ZK proofs; or
- refactors of unrelated storage, VFS, bucket, cluster, or WAL families.

## 13. Post-implementation audit and repair program

The base implementation board completed at exact commit
`83793a9b7adedfc4ef534ac5fdc98a509cb225a6`. Its declared focused matrix passed
(`49 passed`), but an independent read-only audit found four behaviors outside
that matrix. The release is not accepted until KSR-100 through KSR-104 close
them.

### 13.1 Canonical CID aliases

`state_root_contracts._validate_cid` decodes CID bytes but does not prove that
the input string is their one canonical encoding. It therefore accepts:

- non-minimal varints, such as replacing CID version byte `0x01` with
  `0x81 0x00`; and
- lowercase base32 strings with alternate non-zero trailing pad bits.

Both aliases are rejected by a conforming multiformats decoder but were
accepted as distinct root-identity strings by `StateRootSnapshot`. Repair must
harden the existing kit transport-CID decoding authority and reuse it from the
root contracts. It must not add a semantic CID calculator or import datasets.

### 13.2 Unverified live roots and predecessor evidence

At the reviewed commit, `current_state_root` trusts the SQLite row without
re-reading the referenced root and transition blocks. CAS verifies the proposed
successor but not the live predecessor. The audit demonstrated:

1. publish revision one;
2. replace the current root block with corrupt bytes;
3. observe that `current_root` still reports revision one; and
4. publish revision two successfully over the corrupt predecessor.

The live read and CAS comparison must verify the root block, transition block,
transition CID and codec, closed transition fields, namespace, revision, and
predecessor/successor linkage. A corrupt or inconsistent chain cannot be
reported as current and cannot be advanced.

### 13.3 Recovery/publication race

`recover(rebuild=True)` currently scans immutable blocks before it acquires the
SQLite writer transaction. In the audited interleaving, recovery captured a
revision-one block snapshot, another connection committed revision two, and
the stale recovery transaction then deleted the new indexes and rebuilt
revision one. Both live connections reported revision one even though the
revision-two transition block remained durable.

Reconstruction must establish its block snapshot while fenced against CAS
transition publication, using the existing SQLite `BEGIN IMMEDIATE` authority
or a proven equivalent rescan/generation protocol. Recovery must never reduce
a committed revision or omit a transition committed before its rebuild
transaction.

### 13.4 Closed API, replay, and semantic codec parity

The storage primitive currently returns open dictionaries while the public
protocol promises closed values, and it duplicates validation rules from the
contract module. The semantic adapter also needs an explicit structured-codec
boundary: raw blocks remain valid coordination-store content, but may not be
published through the semantic structured-artifact adapter.

The repaired public semantics are:

- the protocol-facing facade returns only the KSR-001 closed result types;
- invalid revision-zero/non-zero expectations fail before storage mutation;
- an exact replay of the same namespace, operation ID, expected values, and
  successor is `unchanged` even after a later revision is current;
- reuse of an operation ID with different request values is `conflict`;
- semantic adapter put/get/root operations accept canonical `dag-json` CIDs
  only and preserve the caller's exact expected CID; and
- provider availability remains independent of local durability and never
  falls back to a mock.

### 13.5 Repair assurance and performance

KSR-104 reruns every focused and coordination regression and adds the audit
reproductions as durable tests. It also records the healthy-reopen behavior:
the implementation may verify immutable evidence on startup, but must not
unconditionally delete and rebuild correct root indexes merely because a
transition exists. Tests should use deterministic scan/rebuild counters rather
than a fragile wall-clock threshold. The known, pre-existing
`_agent_supervisor_rest_binding` receipt-test collection failure remains
reported and outside this storage repair.
