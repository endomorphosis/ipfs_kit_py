# Durable state roots

`DurableStateRootAdapter` is a narrow, typed facade over an injected
`DurableCoordinationStore`. It publishes a revisioned current root per
namespace using compare-and-swap and immutable transition records.

`ipfs_datasets_py` owns semantic identity. Callers calculate the semantic CID
and pass it as `expected_cid`; this package verifies that CID without
canonicalizing, translating, or minting a replacement identity.

`DurableCoordinationStore` owns storage: immutable local blocks, CID
verification, SQLite-WAL visibility indexes, root transitions, and recovery.
The adapter owns neither a block directory nor a database.

```python
from ipfs_kit_py.mcp_server.mcplusplus import DurableStateRootAdapter
from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import DurableCoordinationStore

with DurableCoordinationStore(".state-roots") as store:
    roots = DurableStateRootAdapter(store)
    artifact = roots.put_verified(payload, expected_cid=datasets_cid, replicate=False)
    published = roots.compare_and_swap_root(
        "semantic/my-workspace",
        expected_revision=0,
        expected_root_cid=None,
        new_root_cid=artifact.cid,
        operation_id="publish-001",
    )
```

An update either returns `updated`, an idempotent `unchanged`, or a typed
`conflict`; it never overwrites a stale root. Local persistence is hermetic and
needs no daemon. Replication is optional and injected through the store's
existing backend: `available`, `unavailable`, `failed`, `corrupt`, and
`not_requested` remain distinct outcomes. A requested but absent provider is
not simulated.

Imports and construction are inert: no provider discovery, installation,
network service, or daemon startup occurs. Recovery verifies immutable blocks
and transitions; corrupt or ambiguous chains fail closed.

## Verified reopen behavior

Each reopen verifies local immutable blocks and checks the root-transition
chain against SQLite. When those indexes already match, this is read-only: the
root-index rebuild-mutation counter remains zero. Immutable transition evidence
that is absent from SQLite (for example, after an interruption) instead causes
reconstruction, so a valid durable successor is not ignored. The focused suite
also covers canonical-CID aliases, live corruption, stale recovery, late exact
replay, raw-root rejection at the semantic facade, restart persistence,
concurrent CAS writers, inert imports, and truthful optional-provider states.

The related external `tests/test_agent_supervisor_receipts.py` remains outside
this feature's validation gate: it currently fails at collection because the
unrelated `ipfs_kit_py.mcp_server.server` surface does not export
`_agent_supervisor_rest_binding`. No receipt behavior is claimed as validated
until that owning transport surface is repaired.
