# Iroh deployment security

- Runbook: IROH-023
- Applies to: release bundle `iroh-1.0.2-ipfs-kit.1`, protocol 1
- Related: [filesystem contract](filesystem-contract.md),
  [service configuration](service-configuration.md),
  [operations](operations.md), [recovery](recovery.md), the
  [threat model](threat-model.md), and the
  [credential rotation procedure](credential-rotation.md)

This document is the deployment security baseline for the Iroh backend. The
product threat model is maintained in [threat-model.md](threat-model.md). An Iroh node processes data and
protocol messages from untrusted peers; a ticket or write capability is bearer
authority; the local RPC client can exercise whatever credentials the service
resolves. Build authorization around those facts.

## Trust boundaries and protected assets

Keep these asset classes distinct:

| Asset | Sensitivity | Required handling |
| --- | --- | --- |
| Node private identity | Secret; continuity-critical | Non-exportable KMS/credential store when possible; separately encrypted recovery copy |
| Namespace write capability | Secret; permits mutation | Dedicated record per namespace/role; never co-locate with read-only clients |
| Read ticket | Secret bearer read authority | Shortest practical distribution and review window; resolve only at use |
| Namespace ID, node ID, blob hash | Public identifier, but potentially metadata-sensitive | Safe only in approved audit context; it is not a credential |
| Manifests and sync mappings | Integrity-critical and content-metadata-sensitive | Private, authenticated backup; verify schema and hashes before trust |
| Blob data and exports | User data | Apply the source data classification and retention policy |
| Local RPC socket and service account | Control plane | Host-local, least privilege, no shared account, no remote proxy |

Possession of an underlying Iroh capability is necessary but does not bypass
the version-1 manifest ACL. Conversely, an ACL entry cannot grant authority
that the caller's capability lacks. Both layers must authorize a request.

## Credential rules

- Persist only opaque credential references. Service identity uses
  `credential://iroh/<identifier>`; named backends use the allowed
  `secretref:<provider>:<identifier>` form. A reference is not the secret.
- Resolve a value only at the service/application boundary immediately before
  protected local RPC. Never write the resolved value back to configuration,
  state, a recovery manifest, or a receipt.
- Do not pass raw keys, tickets, capabilities, or secret-reference identifiers
  in command arguments, URLs, environment diagnostics, exceptions, logs,
  metrics, traces, process titles, crash reports, or support bundles.
- Separate node identity, namespace write, and namespace read records. Grant
  the service account access only to records needed by that instance.
- Disable core dumps and debugger attachment for the service account where the
  platform permits it. Scrub inherited environment and use a minimal service
  manager environment.
- Audit credential reads, writes, export, and deletion in the provider. Audit
  records may name an approved public instance/namespace alias, not a raw
  ticket or secret value.

Configuration loading rejects common inline-secret field names recursively,
but that safeguard is not a secret scanner for arbitrary files. Review every
configuration and backup destination independently.

## Host and filesystem hardening

Run each trust domain under a dedicated unprivileged account. Keep the state
root on a local filesystem with owner enforcement, adequate free space, and
encryption at rest. The required modes are `0700` for directories and `0600`
for managed files. Do not weaken them for monitoring or backup; use a narrowly
authorized agent instead.

Each instance owns a unique `data/`, `staging/`, `run/`, `logs/`, and
`receipts/` tree. Reject symlinks and bind mounts that escape the approved
root. Do not share one instance directory through NFS, a container volume
mounted by multiple writers, snapshots restored while live, or two supervisors.

For systemd, retain `NoNewPrivileges=true` and `PrivateTmp=true` from the
example, use an explicit `User`/`Group`, and add site-tested restrictions such
as a read-only system image, a write allowlist for the state root, a restrictive
umask, capability bounding, syscall policy, and resource limits. Do not add a
restriction until canary transfer, DNS, relay, and graceful shutdown tests pass.

The executable and `.ipfs-kit-iroh-install.json` receipt are managed together.
Use `ipfs-kit-iroh inspect --check` at startup/deployment and alert on digest or
version drift. Never run a binary merely because it exists in `PATH`.

## Network hardening

The RPC endpoint must remain an owner-controlled Unix socket or local named
pipe. Never expose it over TCP, an ingress controller, SSH remote forwarding,
or a generic socket proxy. Local callers should have separate OS identities
and only the minimum control/read/write permissions at the application layer.

For Iroh transport and relay rules, follow the flow matrix in
[operations.md](operations.md#network-policy):

- bind fixed transport ports when the security group requires predictable
  rules; port `0` is dynamic and must be discovered after start;
- restrict inbound QUIC/UDP to expected networks where feasible;
- restrict relay egress to approved credential-free HTTPS origins and the
  site's DNS resolvers;
- disable local or DNS discovery when it is not required;
- treat relay connection times, node addresses, and peer relationships as
  metadata; do not put peer lists or remote addresses in general metrics;
- rate-limit at the perimeter without turning transient loss into unbounded
  application retries.

Test that the denied path is actually denied. A healthy local RPC response does
not prove that firewall, relay fallback, or peer authorization is correct.

## Safe namespace sharing

A namespace ID does not grant access. Raw tickets and capabilities do. Before
sharing, identify the recipient and expected namespace over an authenticated
out-of-band channel and grant read-only access unless mutation is necessary.

Store a received ticket under a new local credential record, then configure
only its non-secret lookup reference. `iroh+ticket://` contains that lookup
name, never encoded ticket bytes. Resolution must confirm that the ticket
identifies the namespace explicitly configured for the backend. Do not accept
a ticket that silently redirects a mount.

Maintain an authority inventory containing owner, namespace ID, role,
recipient, issue date, review date, and credential-record audit ID. The
inventory must not contain secret values. Review it after personnel, tenant,
or topology changes.

Deleting a ticket reference only removes the local copy. Because a disclosed
bearer ticket may have been copied, treat loss as an incident and rotate the
underlying authority when revocation is required.

## Key and capability rotation

Rotation is a controlled migration. Back up and test recovery first, pause
unrelated configuration changes, use a canary, and retain the old secret only
for a bounded rollback window in the credential provider.
The authoritative production and emergency steps, evidence requirements, and
rollback boundaries are in
[credential-rotation.md](credential-rotation.md); the summary below is kept for
deployment review.

### Rotate the node identity

Changing node identity changes the public node ID and can break peer addressing
or tickets that name the old node. It does not change content hashes, and it
must not be confused with rotating a namespace write capability.

1. Inventory namespaces, peers, tickets, relay policy, and services tied to the
   old node ID. Quiesce writes and transfers; create a consistent state backup
   plus a provider-native export of the old identity.
2. Generate a fresh identity in the approved provider. Do not copy its value
   into JSON. Prefer a new reference name so rollback remains unambiguous.
3. Stop the sidecar and atomically deploy configuration referencing the new
   record. Start it and confirm readiness and the expected new public node ID.
4. Verify namespace read/write capability separately. Re-establish peer
   discovery/addressing and issue replacement read tickets where the old node
   address was embedded. Test direct and relay paths.
5. Monitor through the rollback window. Then disable the old identity, verify
   no service reads it, revoke/delete it according to provider policy, and
   destroy temporary recovery copies under dual control.

If a step fails, stop the service before restoring both the prior reference and
compatible prior state. Never run two nodes concurrently with the same restored
private identity.

### Rotate namespace capabilities and tickets

Where the upstream capability model cannot revoke an already copied bearer
ticket in place, create a replacement namespace/authority boundary, copy the
latest verified manifest and live blobs, and cut clients over explicitly.
Do not claim that deleting a secret-store record revoked remote copies.

1. Freeze mutations and pin the current verified head. Inventory legitimate
   readers/writers without recording their secret material.
2. Create the replacement authority and least-privilege credentials. Copy
   content with hash verification and publish a valid new namespace head.
3. Issue new per-recipient read tickets/write references through the secure
   channel. Update backends atomically and verify expected namespace IDs.
4. Revoke or disable old authority where supported, remove all controlled old
   records, deny old routing, and monitor for use of the old namespace/node.
5. Retain the old data read-only only for the approved recovery period; then
   apply the data and credential destruction policy.

For a routine ticket refresh where upstream revocation is available, the same
order applies without a namespace copy: create, distribute, validate, revoke,
observe, then delete.

## Logging, diagnostics, and audit

Use `ipfs-kit-iroh-diagnostics` for the bounded health schema. It allowlists
fields and deliberately omits raw error strings, local paths, credentials,
tickets, private keys, and peer lists. Prometheus labels are limited to
`instance`, `path`, `result`, and `direction`; do not add namespace, peer,
ticket-reference, or user-path values as labels.

Protect service logs and health/crash/GC/sync receipts as user-data metadata.
Keep them owner-only, send them only to approved collectors, bound retention,
and scan releases and incident bundles for:

- credential URI and secret-reference identifiers;
- raw ticket/capability/key patterns;
- query strings, environment values, and command arguments;
- local user paths, peer addresses/lists, and content-derived filenames.

Audit destructive and control operations with an operation ID, authenticated
actor, public instance/namespace identifier where allowed, result code, and
receipt digest. Never audit the authority used to perform the operation.

## Resource and data-integrity controls

Set `max_connections`, `max_concurrent_transfers`, `max_open_files`,
`max_staging_bytes`, and `max_storage_bytes` to host capacity and tenant risk.
Use OS limits as a second boundary. Alert before disk exhaustion; do not respond
by bypassing manifest retention, leases, or GC dry-run review.

All imported/exported blobs must match their lowercase BLAKE3 hash and exact
size. Manifest bytes, namespace, revision, parent link, writer, ACL, and head
CAS must validate before use. Treat integrity failures, multiple newest valid
heads, unexpected version/schema, or a changed installed-binary digest as a
security event. Do not repair by choosing last arrival or wall-clock time.

Untrusted paths must pass the filesystem contract: no traversal, encoded
separator, control character, non-NFC alias, symlink emulation, or host-path
exposure. Archive extraction and export destinations need their own safe-path
policy; a valid Iroh path is not permission to overwrite an arbitrary host file.

## Backup security

Backups contain user content, topology metadata, manifests, and possibly
provider-native encrypted credentials. Encrypt in transit and at rest with a
key outside the backup set. Separate access to data backups from credential
exports, require dual control for identity recovery where possible, and record
restore access.

Never place raw credentials in the backup inventory or checksum manifest.
Verify backup digests and perform isolated restore tests without connecting a
duplicate node identity to production. Apply immutable/versioned retention so
an attacker with service-account access cannot rewrite every recovery point.
See [recovery.md](recovery.md#backup-procedure) for the complete backup set.

## Security incident procedure

1. Preserve logs, receipts, configuration, installed-binary receipt, and
   storage snapshots under incident controls. Do not collect secret values in
   the ticket or chat.
2. Isolate transport/relay egress and disable application routing. Keep the
   host powered and state read-only when forensics requires it. Stop through
   the owning supervisor; never signal an unproven `foreign` PID.
3. Classify exposure: node identity, namespace authority, read ticket, user
   data, binary/supply chain, local RPC, or manifest integrity.
4. Rotate the affected authority using the procedures above from a clean host.
   Assume copied bearer credentials remain usable until their authority is
   actually revoked or replaced.
5. Restore only verified manifests/blobs and a verified pinned binary. Rebuild
   GC references before collection. Test denied and permitted paths.
6. Increase monitoring through the review window, document affected public
   IDs and data scope, satisfy notification requirements, and destroy temporary
   secret copies.

## Release security checklist

- Verified pinned binary and receipt; no `PATH` ambiguity
- Dedicated account, owner-only state/config/socket, core dumps disabled
- Local RPC only; direct/relay/discovery firewall rules tested
- No inline or command-line secrets; provider audit enabled
- Least-authority tickets and separate read/write records inventoried
- Resource limits and disk alerts enabled
- Logs, metrics, traces, and support bundles pass redaction review
- Encrypted immutable recovery point and isolated restore test current
- Node identity and namespace capability rotation owners assigned
- GC requires reconciliation, dry run, leases, receipt, and reviewed retention
