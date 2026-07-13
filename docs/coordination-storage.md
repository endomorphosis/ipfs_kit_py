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
