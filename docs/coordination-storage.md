# Durable MCP++ Coordination Storage

`DurableCoordinationStore` is the `ipfs_kit_py` persistence seam for MCP++
Profile G artifacts. It stores canonical DAG-JSON bytes under their CIDv1
`dag-json`/`sha2-256` address and maintains rebuildable SQLite indexes for task
claims, accepted leases, fencing tokens, and expiring daemon-health records.

## Durability model

The immutable block tree under `blocks/` is authoritative. A `put()` returns
only after the local block has been flushed and its index transaction has
committed. When an IPFS or Helia backend is configured, the same canonical
bytes are replicated before the call returns. Backend CID mismatches fail
closed.

The optional backend accepts three integration styles:

- `store_block(cid, bytes, codec)` and `load_block(cid)` for a Helia sidecar or
  application bridge;
- `put` and `get` for simple Helia-compatible adapters;
- Kubo block/DAG client methods such as `block.put`, `block.get`, and `dag.put`.

```python
from ipfs_kit_py.mcp_server.mcplusplus import DurableCoordinationStore

store = DurableCoordinationStore("/var/lib/ipfs-kit/coordination", backend=helia_bridge)
result = store.put_profile_g("TaskClaim", claim, expected_cid=claim_cid)
lease = store.active_lease(claim["task_cid"])
artifact = store.get(result["cid"])
```

## Recovery

Startup verifies every local block against its CID. If the SQLite index is
missing, it is rebuilt automatically by replaying canonical artifacts in
creation order and then applying coordination archive tombstones. A malformed
or CID-mismatched block stops recovery rather than silently omitting history.
An unreadable SQLite file is preserved with a `corrupt-*` suffix and replaced
from the immutable blocks.

If a local block is missing but the configured backend still has it, `get()`
verifies the returned CID and repairs the local block tree.

## Retention and Profile F compaction

Retention applies only to derived index rows. `compact_indexes()` writes one
CID-addressed `mcp++/coordination-index-archive@1` artifact containing the
eligible rows and their artifact CIDs before pruning those rows. Claim,
resolution, health, receipt, archive, and all other artifact blocks use
permanent retention and remain retrievable by CID.

Profile F Event DAG compaction may therefore replace a live traversal with an
archive boundary without affecting any coordination artifact referenced by
that event. The Event DAG archive and coordination index archive serve
different purposes: the former proves event inclusion, while the latter
preserves rebuildable query-index history.

## Existing native DuckDB owner adapter

`ipfs_kit_py.mcp_server.mcplusplus.duckdb_coordination_storage.DuckDBCoordinationStore`
provides immutable kit block persistence and state-root CAS within an existing
DuckDB + Quack owner's database. The launcher supplies its already-open native
connection, shared reentrant transaction lock, exact owner identity, and one
fixed namespace. The adapter does not open or close a connection, start a
server, use a filesystem block store, or offer a replication fallback. It
rejects an in-memory catalog because it cannot issue durable receipts there.

Construct the adapter after native readiness and outside a caller transaction:

```python
store = DuckDBCoordinationStore(
    owner_connection,
    transaction_lock=owner_transaction_lock,
    owner_identity=ready_owner_identity,
    namespace="source-forest/spar/profile1",
)
block = store.put(manifest, codec="dag-json", replicate=False)
before = store.current_state_root(store.namespace)
receipt = store.compare_and_swap_state_root(
    store.namespace,
    expected_revision=before["revision"],
    expected_root_cid=before["root_cid"],
    new_root_cid=block["cid"],
    operation_id="source-publication-1",
)
```

Each access verifies the latest native generation, schema revision, fence,
database UUID, process birth, and the exact READY server/store binding. A stale
adapter fails closed; the replacement native owner must construct a new adapter.
The fixed namespace is also bound to the database UUID and store ID. Content and
operations in another namespace are inaccessible even when their CIDs are known.

The existing kit canonical CID encoding and closed state-root transition schema
are reused. `put` verifies an optional `expected_cid`; `get`, `get_bytes`, and
`has` verify stored bytes, canonical encoding, and metadata on every read. Root
reads verify the complete transition chain, including the immutable contents of
earlier roots. Missing or corrupted history fails closed without rebuilding,
resetting, or creating replacement authority.

A successful CAS commits the transition block, operation record, and current root
pointer together under the native transaction lock. The existing result shapes
are retained: `updated`, `unchanged` / `idempotent_replay`, and `conflict` /
`stale_expectation` or `operation_id_reused`. Replaying an earlier successful
operation returns the current verified root without rolling it back. Revisions
prevent an old expectation from succeeding after an A → B → A root sequence.

Reads acquire the shared reentrant lock but never begin, commit, or roll back a
transaction, allowing a native status snapshot to read root and block evidence in
its own transaction. Writes own a transaction and roll it back on exceptions,
including interruption. Persistence durability is supplied by the admitted native
DuckDB database and WAL. Root CAS receipts prove kit persistence only; they do
not grant task completion or datasets semantic acceptance.

`tests/test_duckdb_coordination_storage.py` exercises real persistent DuckDB
connections with raw and native-style mapping rows, competing CAS calls,
transaction rollback, owner fences, namespace isolation, corruption, and abrupt
process exit before and after commit followed by a new native generation.
