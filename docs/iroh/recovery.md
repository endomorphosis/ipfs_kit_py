# Iroh backup and disaster recovery

- Runbook: IROH-023
- Applies to: release bundle `iroh-1.0.2-ipfs-kit.1`, protocol 1
- Related: [operations](operations.md), [security](security.md),
  [manifest contract](filesystem-contract.md), and
  [service lifecycle](service-lifecycle.md)

Recovery has two independent goals: preserve the node/namespace authority and
preserve verifiable content. A copy of `data/` without the node identity may
lose network continuity; an identity without manifests and blobs does not
recover user data. Back up and test both, but keep credential exports protected
separately from data backups.

## Recovery objectives and ownership

For every named instance, define and test:

- recovery point objective (RPO) for namespace mutations, sync checkpoints,
  and credential changes;
- recovery time objective (RTO), including binary installation, credential
  approval, large-blob restore, peer discovery, and integrity verification;
- backup/restore owner, credential recovery approver, namespace owner, and
  incident escalation path;
- expected state root, service-account UID/GID, release bundle/protocol,
  public node ID, namespace IDs, and latest known manifest heads;
- retention, geographic copy, encryption key, immutability, and restore-test
  schedule.

An eventually consistent peer is not a backup guarantee. A relay is not a
backup. The retained `.previous` executable is only binary rollback.

## Backup set

| Item | Required | Restore purpose |
| --- | --- | --- |
| Complete `<state-root>/instances/<name>/data/` | Yes | Sidecar data, local blobs, namespace state/history |
| `.instance.json` and canonical `config.json` | Yes | Instance ownership and exact state configuration |
| Service and named-backend source configurations | Yes | Reconstruct bindings, ACL intent, timeouts, and policies; contains references only |
| Node identity credential | Yes for node continuity | Restore the same public node ID; export only through provider-native encrypted recovery |
| Namespace write capabilities and needed read tickets | Yes when this node is authority-dependent | Recover mutation/read authority; protect separately from data |
| Canonical manifest snapshots and recorded heads | Yes | Independently verify namespace, revision, parent chain, ACL, and content inventory |
| Live blob export or complete verified `data/` copy | Yes | Recover content; important namespaces should have both forms |
| GC reference-tracker DuckDB and GC receipts | If GC is enabled | Preserve references, leases/runs, and audit evidence; rebuild before GC if absent |
| IROH/IPFS sync `mappings.json`, `checkpoints/`, `receipts.jsonl` and optional CAR staging | If sync is used | Idempotent resume, hash-domain mapping, lineage, and reconciliation evidence |
| Install/update receipts and release manifest | Yes | Reinstall the exact verified binary; the binary itself may be reacquired |
| Health/crash receipts and bounded logs | Per audit policy | Diagnose pre-failure state; not needed to reconstruct content |
| `run/` socket, service lock, and PID receipt | No | Ephemeral ownership state; recreate after confirming no old process lives |
| `staging/` incomplete transfer files | Normally no | Incomplete data is not authoritative; preserve only for incident forensics |

Do not assume that arbitrary application sync state lives below the service
root. Record the `SyncStateStore` directory explicitly. Back up any configured
VFS sync state and backend-manager configuration as part of the application,
not just the sidecar.

## Backup procedure

Use a filesystem snapshot or backup agent that preserves owners, modes,
timestamps, and sparse/large files. The destination must be encrypted,
authenticated, access-controlled, and outside the service account's ability to
rewrite prior recovery points.

1. **Prepare.** Record diagnostics, installed version receipt, free space,
   public node ID, namespace IDs, and each current `(revision, manifest_hash)`.
   Confirm the previous backup is readable before starting a new one.
2. **Quiesce.** Stop new writes, namespace sharing, sync, imports/exports, and
   GC. Wait for in-flight operations to finish. For a crash-consistent full
   instance copy, stop the sidecar through its sole supervisor and verify it is
   no longer running. Never copy a live DuckDB file with ordinary file-copy
   semantics.
3. **Snapshot state.** Snapshot/copy the complete instance root except the
   recreated `run/` artifacts. Include `data/`, configuration, ownership
   marker, receipts, GC database, and separately located sync state. Preserve
   `0700` directories and `0600` files.
4. **Export authority separately.** Use the credential provider's approved
   backup/escrow operation for the node identity, write capabilities, and
   required tickets. Record credential record IDs and versions in a restricted
   inventory, never their resolved values in the data backup or checksum list.
5. **Make a logical content copy.** For critical namespaces, read a single
   verified `ManifestSnapshot`, save its canonical JSON, and export each live
   file's immutable `blob_hash` with `IrohBlobStore.export()`. Export uses an
   atomic destination and verifies exact length and BLAKE3 before publication.
   Preserve tombstones in the manifest, not as files.
6. **Seal evidence.** Produce a checksum/authentication manifest for every
   non-secret backup file plus instance, release bundle, protocol, public node
   ID, namespace heads, snapshot ID, start/end time, and quiescence result.
   Sign or MAC this inventory and store it separately. Do not put raw secrets
   or secret-reference identifiers in it.
7. **Resume safely.** Start the service, require `running` and `ready`, verify
   the expected node ID/head, then resume routing, synchronization, and GC.
8. **Verify.** On an isolated recovery host, verify the backup inventory,
   permissions, configuration parsing, manifest chain, and a representative
   sample of every blob-size class. Periodically perform a full restore.

If continuous writes cannot be stopped, use storage-level atomic snapshots and
record the application barrier/head tokens inside the same recovery record.
A sequence of ordinary copies taken while manifests, blobs, or DuckDB state are
changing is not a consistent backup.

## Restore procedure

Never restore over a running instance. Never connect two nodes using the same
private identity at the same time.

1. Isolate the recovery host from production Iroh transport and relay egress.
   Install the Python package and exact pinned sidecar with
   `ipfs-kit-iroh install ... --check`; verify its receipt and compatibility.
2. Verify the signed/MACed backup inventory and every file digest before use.
   Reject partial, unexpectedly new schema/version, public permissions,
   symlinks, or an unverified executable.
3. Recreate the dedicated account with the intended UID/GID. Restore the
   instance tree to its exact absolute state root with `0700` directories and
   `0600` files. Omit stale socket, lock, and PID files only after proving no
   old process exists.
4. Restore credentials through the provider under the expected references.
   Verify access without printing values. If the original identity cannot be
   restored, follow [Recovery without the original node identity](#recovery-without-the-original-node-identity).
5. Atomically restore service and backend configurations. Run `load_config()`
   and named-backend validation offline. Confirm local RPC path, namespace IDs,
   release bundle, protocol, ownership, network, relay, discovery, and resource
   limits before enabling them.
6. Keep external routing disabled. Start the sole supervisor, then verify
   liveness, readiness, public node ID, version, storage totals, and current
   namespace heads. Treat any unexpected head or identity as a failed restore.
7. Validate canonical manifests and parent links, then hash-check representative
   blobs or the full logical export. Reconcile sync mappings and the GC reference
   index. Do not run live GC until reconciliation reports no unexplained missing
   blobs or references.
8. Test a read-only canary, a new write/CAS in a designated recovery namespace,
   atomic export, direct connectivity, and relay fallback. Test the denied RPC
   and firewall paths too.
9. Re-enable peers and application routing gradually. Preserve the failed host
   and recovery receipts until incident/change review closes.

## Outage modes

| Symptom | Expected behavior | Operator action |
| --- | --- | --- |
| Process down | `running=false`, `ready=false`; no new RPC operations | Inspect crash receipt/log, disk and binary receipt; fix cause, then start through owning supervisor |
| Process live but RPC unready | `running=true`, `ready=false`; do not route requests | Check socket ownership, readiness/version negotiation, resource exhaustion; restart only through supervisor |
| Crash loop | Starts are persistently refused | Correct root cause; while stopped run `python -m ipfs_kit_py.iroh.service clear-crash-loop --config <path>`; then supervised start |
| Direct path unavailable, relay healthy | Peer operations may use approved relay | Verify relay health/metadata policy; do not expose RPC or broaden firewall indiscriminately |
| Relay unavailable, direct path healthy | Directly reachable peers continue; relay-only peers fail | Preserve local operations, repair approved egress/DNS/relay, avoid unbounded retries |
| Network partition/offline | Verified local manifest/blob reads may work; missing remote content and sync fail | Keep writes within conflict policy, record barrier failure, reconcile heads before retry after recovery |
| Disk full/staging limit | New ingest/export/write may fail without committing a head | Stop ingestion, add capacity, clean only abandoned staging after stop; use reviewed GC, never delete data files manually |
| Credential provider unavailable | Operations needing identity/ticket/capability fail closed | Restore provider, access policy, and exact record version; never substitute inline secrets |
| Namespace head corrupt/missing | Reads fail integrity/not-found; no fallback to another backend | Run authenticated manifest recovery dry-run, investigate, then apply only the newest unique verified chain |
| Blob corrupt/missing | Integrity/not-found failure; export destination remains uncommitted | Restore by hash from verified backup/peer, verify BLAKE3 and size, then repair inventory/references |
| Manifest CAS conflict | Losing mutation is not committed | Read the winning head, reapply intent deliberately, and retry with its exact token; never use last-writer-wins |
| Interrupted sync | Durable checkpoint identifies completed objects | Resume the identical request/checkpoint; verify receipt and mappings; do not relabel CID/Iroh hash |
| Interrupted GC | Durable run retains stable release operation IDs | Repair references if needed, then `resume(run_id)`; never convert a dry run into a live sweep |
| Binary upgrade failure | Service may be stopped/unready; state remains | Stop process, verified binary rollback, restore compatible config/data if changed, then full canary validation |
| Suspected key compromise | Peer/content availability may continue but authority is unsafe | Isolate, preserve evidence without secrets, rotate identity/capability from clean host per security runbook |

## Recover a corrupt namespace head

`IrohManifestStore.recover_head()` obtains history, reads candidates by exact
revision/hash, validates canonical manifest semantics, and follows parent hash
links. It selects only a unique newest fully verified linear chain. Corrupt,
unreadable, forked-at-the-newest-revision, or unsupported candidates do not win.

Use an already authenticated local `IrohRuntimeClient`; do not place credentials
in the script or arguments. Audit first:

```python
from ipfs_kit_py.iroh import IrohManifestStore

store = IrohManifestStore(authenticated_runtime_client)
receipt = await store.recover_head(namespace_id, dry_run=True)
print(receipt.to_dict())
```

Compare `previous_head`, `recovered_head`, `candidates_examined`, and
`valid_candidates` with backup evidence and incident scope. Applying recovery
changes the head through compare-and-swap, so pause writers and require change
approval:

```python
receipt = await store.recover_head(namespace_id, dry_run=False)
assert receipt.recovered_head == expected_recovered_head
```

If there is no verifiable chain or there are multiple valid newest heads, the
method fails closed. Restore the namespace from a verified logical backup into
a controlled authority boundary; do not choose by timestamp, arrival order, or
operator intuition.

To restore older *content* after an accidental deletion, read the chosen older
verified snapshot, ensure all referenced blobs are available, and publish its
desired live entries as a new successor revision to the current head. Do not
rewind the head to an arbitrary old hash: that breaks linear history and may
resurrect permissions or tombstones incorrectly.

## Recover missing or corrupt blobs

1. Pin the exact verified manifest snapshot that references the blob and record
   its expected lowercase BLAKE3 hash and size.
2. Obtain the blob from an authenticated backup or authorized peer by its hash.
   Treat provider/ticket input as secret and keep it only in protected RPC.
3. Ingest with `expected_hash`; reject any mismatch. A successful hash does not
   by itself authorize adding the blob to a different namespace.
4. Reread/export the full blob and verify exact hash/size. Reconcile the GC
   tracker and sync mapping, then retest the manifest path.

Never edit an immutable blob, rename a CID to an Iroh hash, or change a manifest
entry merely to match corrupt bytes.

## Recover GC state

The reference-tracker database is safety-critical for deletion but can be
rebuilt from verified manifest and blob inventories. If DuckDB is missing,
corrupt, or not crash-consistent:

1. Disable scheduled/live GC and preserve the database and receipts for
   investigation.
2. Enumerate every retained verified manifest revision and sidecar blob
   `(hash, size)` inventory. Include namespace heads needed by readers, backups,
   exports, or sync and restore their leases/policy protection.
3. Run `ReferenceTracker.repair(manifests, blobs)` with its default
   `dry_run=True`. Resolve every `missing_blobs` report and unexpected reference
   addition/removal.
4. Apply with `dry_run=False` only after the inventories and retention policy
   are approved. Back up the rebuilt database.
5. Run a GC dry run with the normal (default 24-hour or longer) retention, save
   and verify the receipt, then re-enable the schedule.

Do not infer that an unreferenced blob is disposable until retained revisions,
leases, exports, backups, and in-flight transfers have been reconciled.

## Recover synchronization

IROH/IPFS synchronization persists mappings, per-request checkpoints, and
append-only reconciliation receipts. Restore these together. Confirm that each
mapping keeps `cid` and `iroh_hash` separate and that the checkpoint request
matches direction, logical paths, source/destination, conflict policy, and
expected hashes.

Resume only the identical interrupted request. Per-object checkpoints make
replay idempotent; completed objects are verified rather than blindly copied.
If checkpoint validation fails, retain it as evidence and start a new explicit
operation. Reconcile deleted entries and partial failures from the receipt
before declaring success. Never silently fall back from Iroh to IPFS/local or
resolve a conflict by last arrival.

## Recovery without the original node identity

If the identity cannot be restored, the old public node ID cannot be recreated.
Do not copy another live node's private identity or connect a duplicate.

1. Preserve and verify data, manifests, namespace capabilities, and backup
   evidence. Create a new node identity in the approved provider.
2. Configure and start the restored data under the new reference while isolated.
   Confirm the new public node ID and verify content locally.
3. Use recovered namespace authority to restore access. Re-advertise the new
   node, update peer allowlists/discovery, and issue replacement tickets where
   the prior node addressing was embedded.
4. Validate readers/writers and direct/relay paths, then retire references to
   the lost identity. Treat unexplained loss as a credential incident.

Content hashes remain verifiable, but availability and peer addressing do not
automatically migrate to the new node.

## Disaster scenarios

### Total host loss

Provision a clean host, install the exact verified bundle, restore credentials
and the consistent instance snapshot, rebuild ephemeral runtime state, and
follow the full restore procedure. If only a logical export survives, create a
new isolated namespace/authority, ingest every file with expected hashes,
publish a validated manifest, and distribute new least-authority credentials.

### Region or relay loss

Promote a recovery copy only after ensuring the original identity is not live.
Use approved alternate relay/direct paths and DNS changes with bounded TTLs.
Verify node ID and namespace heads before routing clients. Reconcile changes
made during partition explicitly; do not merge by wall clock.

### Malicious or accidental deletion

Stop GC and mutation, preserve evidence, identify the last trusted verified
head, and restore missing blobs from immutable backup. Publish recovered content
as a new successor revision. Rotate authority if deletion involved credential
misuse. Retain affected manifests/tombstones for audit until policy allows
compaction.

### Failed upgrade

Binary rollback is described in [operations.md](operations.md#upgrade-and-rollback).
It swaps one retained executable and receipt only. If configuration or durable
formats changed, restore the pre-upgrade recovery point as a unit. Validate
identity, manifests, blobs, sync state, and GC references before reopening.

## Recovery test and acceptance

A recovery point is accepted only when an isolated drill demonstrates:

- inventory signature/MAC and every sampled/full digest verify;
- exact bundle/protocol, owner-only modes, no symlink/path escape, and offline
  configuration validation;
- expected node ID when identity restoration is required, without a duplicate
  production node;
- every namespace head has a unique verified parent chain and correct ACL;
- representative or full live blobs match BLAKE3 and exact size;
- a canary read, CAS write, atomic export, interrupted sync resume, and GC dry
  run produce valid receipts;
- direct and relay behavior matches policy and remote RPC remains denied;
- measured RPO and RTO satisfy the declared objectives;
- credentials and secret-reference identifiers do not appear in logs,
  checksum inventories, process arguments, or support artifacts.

Record the drill date, backup ID, public instance/node/namespace identifiers as
policy permits, test results, measured RPO/RTO, exceptions, owners, and next
test date. Destroy temporary restored credentials and data after the drill
using the approved storage and key-management procedure.
