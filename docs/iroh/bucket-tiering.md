# Iroh virtual buckets and tiered storage

`IrohBucketTieringManager` binds a virtual bucket to validated named backends.
Iroh backends may be used as a `primary`, `replica`, `cache`, or `archive`.
Bindings refer to backend names only; credentials and tickets remain in the
named-backend credential resolver and never enter a bucket policy or receipt.

## Policy contract

Bucket and tier policies are versioned at schema version 1. Their packaged JSON
Schemas are:

- `ipfs_kit_py/resources/iroh-bucket-policy.schema.json`
- `ipfs_kit_py/resources/iroh-tier-policy.schema.json`

A bucket has exactly one enabled primary. A named backend can appear only once
in a bucket, and the replication factor cannot exceed the number of enabled
primary and replica bindings. Placement checks backend writability, health,
reported capacity, per-binding reserves, per-binding quotas, and the bucket's
logical-byte quota before recording a change.

```python
from ipfs_kit_py.backend_manager import BackendManager

backends = BackendManager("/var/lib/ipfs-kit")
tiering = backends.get_bucket_tiering_manager()
tiering.create_bucket(
    "media",
    primary="iroh_primary",
    replicas=["iroh_replica"],
    cache="local_cache",
    archive="iroh_archive",
    quota_bytes=100 * 1024**3,
)
```

Logical quota usage counts each BLAKE3-addressed object once, regardless of the
number of replicas. Re-submitting the same hash and size produces `noop`
actions, does not consume quota again, and does not invoke the placement
handler. A repeated hash with a different size is an integrity failure.

Legacy single-backend policies can be normalized with
`migrate_bucket_policy()`. Applying a migrated policy through `update_policy()`
reconciles new and obsolete bindings and emits a `policy_migration` receipt.

## Reconciliation and audit

Policies, unique content, placements, and receipts are transactionally stored
in an owner-only DuckDB database. `reconcile()` compares desired content and
role bindings with durable placement state. It can plan changes with
`dry_run=True`; `prune=True` additionally removes content that is absent from
an authoritative supplied inventory.

Every run emits a canonical, BLAKE3-digested `ReconciliationReceipt`. Receipts
record policy identity, logical usage before and after, quota, deduplication,
and each place/remove/noop/reject action without paths, payloads, tickets, or
credentials. They can be written atomically with owner-only permissions and
verified with `verify_reconciliation_receipt()`. The receipt schema is packaged
as `ipfs_kit_py/resources/iroh-bucket-reconciliation-receipt.schema.json`.

Quota or capacity rejection is atomic. `place_content()` raises
`IrohConflictError` by default and includes the durable `receipt_id` in safe
exception metadata; pass `raise_on_rejection=False` to consume the rejected
receipt directly.
