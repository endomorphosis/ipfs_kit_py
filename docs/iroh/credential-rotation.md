# Iroh credential rotation procedure

- Runbook: IROH-024
- Applies to: release bundle `iroh-1.0.2-ipfs-kit.1`, protocol 1
- Related: [threat model](threat-model.md), [deployment security](security.md),
  [operations](operations.md), and [recovery](recovery.md)

This is the production procedure for routine and emergency rotation of Iroh
node identities, namespace write capabilities, and read tickets. These are
different authorities: rotating one does not rotate the others. Never paste a
raw value into a command, config file, ticket, chat, log, receipt, or evidence
record. Record provider audit IDs and public node/namespace IDs only.

## Roles, evidence, and prerequisites

The change owner coordinates the cutover; a credential custodian generates,
disables, and destroys provider records; a service operator controls the
instance; a verifier independently checks identity, authorization, data, and
network paths. Emergency rotation may combine people only under the incident
policy, and the exception is recorded afterward.

Before any routine rotation:

1. Open a change/rotation ID and inventory affected instances, public node IDs,
   namespaces, recipient aliases, backends, peers, relay rules, and backups.
   Do not inventory secret values or raw reference identifiers.
2. Confirm an encrypted immutable recovery point, verify its signed inventory
   and digests, and complete an isolated restore test. Confirm the old provider
   version is retained but disabled from general use for the approved rollback
   window.
3. Capture a redacted baseline: service readiness, exact installed-binary
   digest/version, current unique manifest head, live blob verification sample,
   direct and relay connectivity, sync/GC idle state, and denied authorization
   checks.
4. Freeze unrelated configuration changes. Quiesce namespace mutations and
   transfers for authority/identity cutovers; drain or cancel with receipts.
5. Prepare monitoring for old credential-version access, old public node or
   namespace use, authorization failures, manifest conflicts, transfer errors,
   relay changes, and readiness. Credential provider logs remain restricted.

Provider record names and aliases are sensitive metadata. Configuration stores
only `credential://iroh/<opaque-name>` (or the approved named-backend
`secretref:` form), never the resolved material. Prefer immutable provider
versions and an atomic alias/reference update over overwriting a value in
place. The service account gets read access to the new record only when the
canary begins.

## Routine node identity rotation

Changing the node private identity changes its public node ID. Blob hashes do
not change, but peer addresses, tickets, firewall inventories, and monitoring
may refer to the old node.

1. Generate a new identity inside the approved KMS/credential provider with
   export disabled where possible. Record its provider audit ID and independently
   derive/verify the expected new public node ID without exposing the key.
2. Back up the old identity using the provider-native encrypted export under
   dual control. Create a new opaque credential reference or version; grant the
   service account temporary read access to old and new records.
3. Stop the managed instance and verify it is `stopped`, not `foreign`. Never
   start a second node with the same old or new identity and copied live state.
4. Atomically change only `identity.node_identity_ref` to the new record using
   owner-only configuration. Run configuration and offline security validation,
   then start the instance.
5. Verify the exact expected new public node ID, local RPC ownership, readiness,
   manifest reads, an authorized write/CAS, blob ingest/read/export hash, and
   direct plus relay paths. Verify unauthorized read/control/destructive calls
   are still denied and destructive confirmation is still required.
6. Update authenticated peer address books, approved public inventories,
   firewall/relay monitoring, and replacement tickets that embed the old node
   address. Do not mutate ticket material in place; issue and verify it.
7. End the write freeze after the canary remains healthy for the change window.
   Monitor both public IDs and both provider versions through the rollback
   window.
8. Disable old-identity reads, restart once to prove the service no longer
   resolves it, then revoke/delete the old record and destroy temporary exports
   according to retention and dual-control policy. Attach redacted validation,
   provider audit IDs, config digest, public IDs, and timestamps to the change.

Rollback is allowed only before old-identity revocation. Stop the instance,
restore the prior reference and a state snapshot compatible with that identity,
start exactly one instance, verify the old public ID and manifest head, and
revert peer routing. A failed rollback or a possibly copied identity becomes an
emergency rotation; do not extend the old authority's life merely to recover
connectivity.

## Namespace write-capability rotation

First determine whether the upstream authority can revoke the compromised or
retiring writer while preserving the namespace. If it can, create a new
least-privilege writer, verify it, atomically move writers, revoke the old
writer, and validate rejection. If it cannot, replacement requires a new
namespace; deleting a provider record does not revoke a copied capability.

For a replacement namespace:

1. Freeze mutations and pin the current unique verified head. Export the
   canonical manifest, ACL intent, and live blobs; verify every BLAKE3 hash,
   exact size, parent link, and the export receipt.
2. Create the replacement namespace and write authority in the provider.
   Rebuild the ACL with least privilege. Import verified blobs and publish a
   new genesis/successor chain according to the migration contract—never forge
   an old namespace ID, revision, writer, or parent hash.
3. Canary read and write through a backend explicitly configured with the new
   namespace ID and new opaque capability reference. Confirm the old capability
   cannot authorize the new namespace.
4. Issue distinct replacement read tickets per recipient. Distribute them over
   authenticated channels, require recipients to verify the expected namespace
   out of band, and collect only non-secret acknowledgement/audit IDs.
5. Atomically cut applications, MCP/API policy, sync mappings, replication,
   backup inventory, and monitoring to the new namespace. Run hash/data-count
   reconciliation and an authorized CAS from every writer role.
6. Revoke/disable the old authority when supported; otherwise deny old routing
   and keep the namespace read-only only for the approved rollback window.
   Alert on any old-namespace mutation or old provider-record access.
7. After validation and the rollback window, remove controlled old tickets and
   writer records, expire old routing, apply retention to the old data, and
   record the new public namespace ID plus redacted evidence.

Rollback before revocation routes clients back to the frozen old namespace and
requires reconciliation of any canary writes; never merge by wall clock or
last arrival. After revocation or an exposure, roll forward to a corrected new
namespace instead.

## Read-ticket rotation and recipient offboarding

1. Confirm recipient identity, expected namespace, role, and expiry/review
   period. Generate the least-authority replacement ticket and store it directly
   as a new provider version/record.
2. Configure only its opaque reference, import through the governed control
   operation, and verify it resolves to the explicitly expected namespace and
   content. Test that it cannot mutate.
3. Deliver through an authenticated secret channel. Never send it in a URL,
   command argument, ordinary email/chat, audit record, or support bundle.
4. When upstream revocation exists: verify the new ticket, revoke the old one,
   monitor rejection, then delete controlled copies. Without revocation:
   deleting records only offboards controlled clients; a possibly copied ticket
   requires namespace-authority replacement.
5. Update the non-secret authority inventory with recipient alias, role,
   namespace ID, issue/review dates, and provider audit ID. Scan cutover logs for
   leakage and retain only the redacted security receipt.

## Emergency compromise rotation

Do not wait for the routine window when a raw credential may have been read,
logged, backed up improperly, exposed through local RPC, or used by an unknown
actor.

1. Start the incident record and preserve restricted provider/audit/service
   evidence without copying the suspected value. Isolate application routing,
   direct transport, discovery, and relay egress; stop the affected instance on
   a clean control path.
2. Classify every potentially exposed authority. Exposure of a node identity
   triggers node rotation; write-capability exposure triggers supported
   revocation or namespace replacement; copied read-ticket exposure triggers
   revocation or namespace replacement. Rotate related authority when scope
   cannot be bounded.
3. From a clean host and credential session, generate replacement records and
   invalidate old authority as early as the chosen recovery path permits. Do
   not retain a known-compromised secret for rollback.
4. Restore only verified data and the unique newest verified manifest chain
   from an immutable recovery point. Install only the pinned, attested binary;
   audit permissions, resources, dependencies/licenses, and all logs.
5. Reissue minimum credentials, reconnect one canary, verify permitted and
   denied paths, then stage the remaining rollout. Increase monitoring for old
   node/namespace/provider use through the incident review period.
6. Complete notification, credential destruction, root-cause remediation, and
   threat-model/vector updates. A successful service start is not incident
   closure; independent data, authority, and negative-path checks are required.

## Acceptance record

A rotation is complete only when the record contains the change/incident ID,
credential class, public old/new node or namespace IDs where applicable,
provider audit IDs, operator/verifier identities, start/cutover/revocation
timestamps, configuration and binary digests, recovery-point ID, validation
receipt digests, direct/relay results, authorized and denied operation results,
manifest reconciliation result, monitoring window, and destruction evidence.
No record may contain a credential value, raw credential reference, ticket,
user path, peer address list, or unredacted log excerpt.
