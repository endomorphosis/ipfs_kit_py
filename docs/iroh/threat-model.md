# Iroh backend threat model

- Security review: IROH-024
- Applies to: release bundle `iroh-1.0.2-ipfs-kit.1`, protocol 1
- Review date: 2026-07-13
- Related: [deployment security](security.md),
  [credential rotation](credential-rotation.md),
  [filesystem contract](filesystem-contract.md), and
  [recovery](recovery.md)

This model covers the managed Iroh sidecar, its local RPC boundary, immutable
blob and mutable manifest handling, operator surfaces, installation, and
credential references. It uses asset/boundary analysis followed by STRIDE-style
abuse cases. An accepted read ticket or write capability is bearer authority;
an authenticated peer is not therefore trusted to provide safe content.

## Security objectives

1. Only an authorized local caller can read, control, or destructively operate
   an enabled instance, and those permissions remain distinct.
2. Content is returned only after its BLAKE3 hash and exact size validate;
   namespace state advances only through an authenticated, immediately linked
   compare-and-swap revision.
3. Untrusted names, manifests, tickets, peers, archives, and RPC frames cannot
   escape their data model or consume unbounded host resources.
4. Node identities, namespace write capabilities, and read tickets never enter
   persisted configuration, receipts, logs, metrics, traces, or process args.
5. Only the exact pinned and attested dependency bundle runs, and recovery
   cannot silently roll state or authority backward.

Availability against a provider-wide Iroh or relay outage is an operational
objective, not a confidentiality guarantee. IPFS Kit does not claim to hide
the timing, volume, public node identifiers, or peer relationship metadata
inherently visible to direct peers, relays, DNS, or the host network.

## Assets and trust boundaries

| Boundary | Untrusted input | Protected assets | Enforcement point |
| --- | --- | --- | --- |
| MCP/HTTP/CLI to governance | actor, operation, paths, provider, ticket, confirmation | local control plane, data, audit integrity | operation allowlist, schema validation, independent read/control/destructive permissions |
| Python process to sidecar | RPC frames and sidecar responses | process memory, instance state, request integrity | owner-only local IPC, 16 MiB framing, typed protocol/version checks, timeout/cancellation |
| Sidecar to Iroh peers/relays | peer messages, blobs, tickets, manifests, timing | content integrity, namespace head, topology metadata | Iroh transport authentication plus IPFS Kit hash, manifest, ACL, and CAS validation |
| Virtual filesystem to host | user-controlled logical paths and export destinations | host filesystem and tenant separation | canonical path contract, no symlink traversal, atomic exclusive export |
| Installer to artifact source | archive bytes, metadata, archive member names | executable integrity and host filesystem | pinned URL/size/SHA-256, repository-bound attestation, safe exact-member bounded extraction |
| State and credential provider | local account, backup operator, stolen references | node identity, capabilities, manifests, user data | separate provider records, owner-only state, no secret persistence, audited provider access |
| Backup/restore to live service | old or modified state and credential export | continuity and revision freshness | signed inventory, digest verification, isolated restore, unique newest verified manifest chain |

The local service account, credential provider, kernel, approved build runner,
and attestation authority are trusted but independently constrained. General
MCP callers, API clients, remote peers, relay operators, artifact hosting,
backup storage, manifests before validation, and support-bundle recipients are
not trusted.

## Threat analysis and controls

| ID | Threat and abuse case | Impact | Prevent/detect/recover controls | Residual risk and decision |
| --- | --- | --- | --- | --- |
| T1 | A malicious, oversized, whitespace-bearing, or wrong-namespace ticket is imported; a caller tries to reflect it through an error | capability misuse, memory exhaustion, disclosure | 1 MiB byte limit, control permission, outer encoding validation, expected content hash/namespace verification by sidecar, typed generic errors, ticket never returned or audited | A copied valid bearer ticket works until its authority is revoked/replaced. Accepted; minimize distribution and rotate on loss. |
| T2 | An authenticated malicious peer sends corrupt blobs, excessive chunks, false metadata, or repeatedly stalls | integrity failure, bandwidth/connection exhaustion | exact BLAKE3 and size verification, bounded chunks/RPC frames/timeouts, connection and transfer ceilings, cancellation, staging quota, OS limits | A permitted peer can consume its allowed quota and reveal transfer metadata. Rate-limit externally and isolate tenants. |
| T3 | A manifest contains unknown fields, duplicate/aliased paths, invalid ACLs, forged writer data, too many entries, a disconnected parent, or conflicting newest heads | namespace forgery, confused deputy, memory/disk exhaustion | closed schema, canonical serialization, path/metadata/entry bounds, ACL validation, parent hash and revision link, writer verification in sidecar, head CAS, unique verified-chain recovery | A legitimately authorized writer can publish destructive changes. Retain versioned backups and separate write authority. |
| T4 | Traversal, absolute, encoded separator, Unicode alias, control character, Windows separator, or overlong path reaches host I/O | arbitrary read/write, tenant escape | canonical NFC absolute logical paths, forbidden separators/traversal/control bytes, segment/path limits, safe URL parsing, host destinations handled separately | Filesystem normalization differences outside managed exports remain an operator risk; use supported local filesystems. |
| T5 | A symlink, hard link, FIFO, device, bind mount, or race redirects state, staging, logs, or export | arbitrary overwrite/read, secret leakage | state component `lstat`, recursive permission audit, no archive links/special entries, exclusive temporary export and atomic replacement, owner-only root | Bind mounts are not always distinguishable portably. Pin/mount the state root through the service manager and audit host mounts. |
| T6 | A traversal archive, link, duplicate executable, declared-size overrun, or decompression bomb is installed | code execution, filesystem overwrite, disk/CPU exhaustion | pinned compressed size/digest, maximum 1,024 members, exactly one regular executable, safe member names, 512 MiB output cap, 200:1 expansion cap, exact-size copy, temporary extraction and atomic rename | Parsing a malicious compressed stream still uses bounded CPU. Installation occurs only in a constrained deployment job. |
| T7 | Node identity, write capability, ticket, or provider lookup identifier is stolen from config, args, logs, diagnostics, backup, debugger, or broad file permissions | impersonation, unauthorized data access/mutation | opaque references only, recursive inline-secret rejection, owner-only state, local IPC, allowlisted diagnostics, recursive redaction, release/support-bundle log scan, separate credential records, core-dump restrictions | Runtime memory and the credential provider contain usable authority. Harden the host/provider and use the emergency rotation procedure. |
| T8 | A captured mutation/RPC is replayed or two writers reuse an expected head | duplicate or stale mutation | unique operation IDs for audit, immutable content operations, immediately linked manifest revision and atomic expected-head CAS, idempotent sync checkpoints | A replay of an inherently idempotent read/import can still consume quota; resource controls apply. |
| T9 | An attacker restores an old but valid manifest, binary, config, credential version, or backup | rollback of ACL/data/security fixes | exact bundle/version handshake, binary receipt digest, signed backup inventory, parent-linked monotonic revisions, recovery selects the unique newest valid chain, canary/rollback evidence | A complete compromise that deletes every newer recovery point can hide freshness. Keep credential and immutable backup controls outside the service account. |
| T10 | Tickets, frames, paths, manifests, logs, connections, transfers, staging, storage, archive members, or retries exhaust resources | denial of service, disk corruption | explicit limits at every parser/transfer boundary, product maximums, timeouts/cancellation, bounded security scans, dry-run GC, quotas, OS/service-manager limits and alerts | Limits trade capacity for containment and do not guarantee availability during volumetric network attacks. |
| T11 | Local RPC is exposed over TCP/proxy/forwarding, or read callers obtain destructive operations | total instance compromise | configuration accepts only the assigned Unix socket/named pipe, owner-only runtime directory, transport-neutral allowlist, independent permissions, explicit destructive confirmation, safe audit record | Root/administrator can access local IPC and process memory; host administration is a trusted boundary. |
| T12 | Relay/DNS/discovery operators or metrics consumers learn addresses, peer graph, namespace use, timing, or volume | privacy and traffic analysis | credential-free approved relay URLs, optional discovery disablement, no peer/address lists in health receipts, bounded metric labels, protected logs, documented egress matrix | Relays necessarily observe connection metadata. For higher privacy, disable relay/discovery or use approved network controls; anonymity is not promised. |
| T13 | A dependency is substituted, typosquatted, silently upgraded, built with different features, vulnerably pinned, or redistributed without notices | code execution, legal exposure | exact versions/checksums/commits/tags/features/MSRV, Cargo lock policy, HTTPS crates.io sources, exact sidecar digest, GitHub repository-bound attestation, fail-closed startup handshake, SPDX/notice gate | Offline pin audit does not discover newly published advisories. CI/release must run current RustSec/OSV and license tooling before publishing. |

## Security invariants

- Iroh state directories are no broader than `0700`; regular files and local
  sockets are no broader than `0600`. No state-tree symlink is acceptable.
- The sidecar RPC endpoint is local IPC only. A healthy endpoint found over TCP
  is a security failure, not a supported deployment mode.
- `cid` and `iroh_hash` remain separate domains. An Iroh hash is never accepted
  as or labeled an IPFS CID.
- Unknown versions, capabilities, config fields, manifest fields, dependency
  pins, licenses, provenance, and ambiguous recovery heads fail closed.
- Security receipts identify findings and opaque locations only. They never
  contain match text, credential references, user paths, peers, relay URLs, or
  raw exceptions.
- OS limits are a second boundary. Raising an application limit above
  `RESOURCE_LIMIT_MAXIMUMS` requires a reviewed code change and conformance run,
  not an unvalidated configuration override.

## Verification and security vectors

The versioned vector catalog is
[`iroh-security-vectors.json`](../../ipfs_kit_py/resources/iroh-security-vectors.json)
and its closed
[`schema`](../../ipfs_kit_py/resources/iroh-security-vectors.schema.json).
It contains synthetic inputs only—never production credentials or user data.
`tests/test_iroh_security.py` executes the permission, redaction, resource,
archive, dependency, license, and document coverage gates offline. Existing
manifest, installer, MCP/API, filesystem, and recovery suites execute the
deeper controls referenced by each vector.

Release sign-off also requires a current advisory scan of the locked Rust and
Python dependency graphs, a license/notice report, secret scanning of build
logs and artifacts, artifact attestation verification, and multi-node hostile
input tests. A new advisory is triaged even when the pinned manifest itself is
unchanged; critical/high exploitable findings block publication unless the
security owner records a time-bounded exception and compensating control.

## Operational validation and response

Before enablement, run the offline security audit against the created state
tree, pinned release record, and every proposed log/support artifact. A failing
receipt blocks deployment. Preserve only the redacted receipt; protect the
source logs separately. Test an unauthorized read, control operation,
destructive operation without confirmation, TCP RPC connection, direct peer
path, relay fallback, and denied relay/discovery path.

On suspected compromise, isolate network and application routing, preserve
evidence without collecting secret values, classify the exposed authority,
and follow [credential rotation](credential-rotation.md). Restore on a clean
host from a verified recovery point, select the unique newest valid manifest
chain, verify every live blob, and rerun all denied/permitted paths before
rejoining production.

## Review triggers and ownership

The Iroh backend security owner approves this model and credential rotation;
the release owner approves dependency/advisory/license evidence; the service
owner owns capacity and network policy. Review is mandatory for any Iroh or
sidecar version, protocol/ticket/storage format, new RPC method, permission,
credential provider, relay/discovery mode, archive format, resource maximum,
manifest schema, export behavior, or recovery policy—and after every relevant
incident or newly exploitable dependency advisory.
