# Iroh filesystem and backend contract

- Decision: IROH-002
- Status: frozen, version 1
- Effective: 2026-07-12
- Compatibility bundle: `iroh-1.0.2-ipfs-kit.1`
- Depends on: [IROH-001](compatibility.md)

This document is the normative version-1 boundary between IPFS Kit callers,
the future `IrohFileSystem`, persisted manifests, backend configuration, and
the managed sidecar. The keywords **MUST**, **MUST NOT**, **SHOULD**, and
**MAY** are requirements. Later implementation work may add machinery, but it
must not silently change these meanings.

## Normative artifacts

| Artifact | Contract |
| --- | --- |
| [`iroh-manifest.schema.json`](../../ipfs_kit_py/resources/iroh-manifest.schema.json) | Draft 2020-12 schema for an immutable namespace revision |
| [`iroh-backend-config.schema.json`](../../ipfs_kit_py/resources/iroh-backend-config.schema.json) | Draft 2020-12 schema for secret-free persisted backend configuration |
| [`manifest-v1.json`](../../tests/fixtures/iroh/filesystem/manifest-v1.json) | Golden revision containing a root, directory, file, and tombstone |
| [`backend-config-v1.json`](../../tests/fixtures/iroh/filesystem/backend-config-v1.json) | Golden read-write backend using credential references |
| [`contract-v1.json`](../../tests/fixtures/iroh/filesystem/contract-v1.json) | Golden URL, normalization, and stable error vocabulary |

JSON Schema validation is necessary but not sufficient. Requirements called
out as semantic checks below (NFC, unique paths, ancestry, revision linkage,
ACL identity membership, and secret handling) MUST also be enforced before a
manifest or configuration is accepted. Unknown properties and unknown schema
versions are errors; consumers MUST NOT guess, downgrade, or ignore them.

## Identifier and URL grammar

Version 1 recognizes exactly three schemes. The following ABNF uses the core
rules from RFC 5234; literals are case-sensitive where explicitly stated.

```abnf
namespace-url = "iroh://" namespace-id "/" [ encoded-path ]
blob-url      = "iroh+blob://" blob-hash
ticket-url    = "iroh+ticket://" ticket-ref "/" [ encoded-path ]

namespace-id = 64lowerhex
blob-hash    = 64lowerhex
ticket-ref   = lowalnum *62(lowalnum / "-")
64lowerhex   = 64( DIGIT / %x61-66 )
lowalnum     = DIGIT / %x61-7A
```

`namespace-id` is the lowercase hexadecimal encoding of the 32-byte namespace
public identifier. It is public identity, not a write capability. `blob-hash`
is the lowercase hexadecimal encoding of the 32-byte BLAKE3-256 digest used by
`iroh-blobs`. Neither value is an IPFS CID, and callers MUST NOT relabel or
multibase-convert it implicitly. Uppercase, prefixes such as `0x`, padding,
short or long values, and non-hexadecimal characters are invalid.

An `iroh://` URL addresses a path in the current accepted head of a mutable
namespace. The slash following the authority is mandatory; the root is the URL
ending in that slash. An `iroh+blob://` URL addresses the entire immutable blob
and has no slash, path, query, fragment, user information, or port. Ranged reads
use method arguments, never URL query parameters.

An `iroh+ticket://` URL is read-only. `ticket-ref` is a non-secret lookup name,
not an encoded Iroh ticket. It resolves through the configured credential
facility to a `read_ticket_ref`; the returned secret is passed to the sidecar
over protected local RPC only. Raw tickets are forbidden in URLs, process
arguments, configuration, exceptions, logs, metrics, tracing, and VFS lineage.
Ticket references are never returned in a canonical URL. A ticket URL MUST fail
with `IROH_CREDENTIAL_REQUIRED` when no exact reference can be resolved and
`IROH_CREDENTIAL_INVALID` when the resolved ticket is malformed, expired, or
does not identify the requested namespace. There is no network lookup by
ticket-reference name.

All schemes reject query strings and fragments. Authorities reject percent
escapes, Unicode, user information, ports, IPv6 brackets, and empty values.
Scheme matching follows URI convention and may be case-insensitive, but every
canonical URL emitted by IPFS Kit uses the lowercase spelling above.

## Path normalization

Manifest paths are normalized Unicode strings relative to the namespace root.
The root is the empty string. A non-root path is `/`-joined segments with no
leading or trailing slash. Producers and consumers MUST apply these rules in
this order:

1. Parse the URL without treating `+` as space. Reject malformed percent
   escapes. Decode each path segment exactly once as strict UTF-8.
2. Reject percent-encoded `/` (`%2f`, any case), backslash (`%5c`), NUL, C0
   controls, and DEL before decoding. A decoded slash or backslash is invalid;
   it never creates another segment.
3. Normalize decoded text to Unicode NFC. Inputs that are not already NFC are
   rejected rather than silently redirected to a different path.
4. Reject empty interior segments, `.` and `..`, a leading or trailing slash
   in manifest form, backslash, NUL, C0 controls, DEL, and surrogate code
   points. There is no home expansion, environment expansion, drive-letter
   handling, or separator collapse.
5. Reject a segment whose UTF-8 encoding exceeds 255 bytes or a complete
   normalized path whose UTF-8 encoding exceeds 4096 bytes.

Paths are case-sensitive and byte-stable after NFC. A URL producer MUST
percent-encode every byte outside the URI unreserved set and MUST use uppercase
hexadecimal in escapes. A consumer may accept either case in percent escapes.
The filesystem does not infer directory intent from a trailing slash; only the
root URL may end in `/`.

## Manifest version 1

A namespace head points to an immutable UTF-8 JSON manifest that validates
against `iroh-manifest.schema.json`. New manifests MUST use JSON Canonicalization
Scheme (RFC 8785) before ingest. The Iroh blob hash of those exact canonical
bytes is the head token used by compare-and-swap. Readers may parse
non-canonical bytes only after verifying their blob hash, but the next writer
MUST publish canonical bytes.

The top-level fields have these meanings:

| Field | Meaning |
| --- | --- |
| `schema_version` | Integer `1`; every other value fails with `IROH_UNSUPPORTED_SCHEMA` |
| `namespace_id` | Namespace public identifier from the URL and sidecar |
| `revision` | Non-negative signed-64-bit generation; initial manifest is `0` |
| `parent_revision` | `null` at revision 0; otherwise the exact prior generation and its manifest blob hash |
| `created_at` | UTC RFC 3339 timestamp with a `Z` suffix, supplied once at commit |
| `writer_id` | Public identity that signed/published this revision |
| `permissions` | Manifest ACL that can only attenuate underlying Iroh capabilities |
| `entries` | Complete materialized directory state, including retained tombstones |

For every revision greater than zero, `parent_revision.revision` MUST equal
`revision - 1`, and `parent_revision.manifest_hash` MUST be the verified current
head observed by the writer. The namespace, revision, parent, and canonical
manifest hash form the compare-and-swap precondition. Revision overflow is a
hard `IROH_CONFLICT`; it never wraps. A writer identity MUST equal the owner or
occur in `permissions.writers`, and the owner MUST occur in the writers list.
Identity arrays contain no duplicates.

Entries MUST be sorted by the UTF-8 bytes of `path`, with the root first. Paths
MUST be unique. There is exactly one live root-directory entry. Every live
non-root entry has a live directory parent, and no file may be an ancestor.
Tombstones do not satisfy ancestry. Implementations MUST reject rather than
repair a malformed tree.

Each entry contains `path`, `kind` (`file` or `directory`), `tombstone`, `mode`,
UTC `mtime`, and bounded scalar `metadata`. A live file additionally contains
its lowercase BLAKE3 `blob_hash` and exact byte `size`. A live directory never
contains blob fields. A tombstone records its former kind and requires
`deleted_at`, but MUST NOT contain a blob hash or size; the prior revision is
the audit source for deleted content. Tombstones remain until an explicit,
policy-controlled compaction establishes that retained revisions and peers no
longer need them.

Metadata keys are lowercase and may not name secret-bearing concepts. Values
are scalar JSON values; nested structures and binary encodings are not allowed.
Credentials, tickets, private keys, capability material, peer-sensitive
connection data, and user file content MUST NOT be copied into metadata.
Content type and user metadata are descriptive only and cannot override a
reserved field.

### Modes and permissions

Version 1 accepts only this mode subset (shown in octal):

| Kind | Modes | Meaning |
| --- | --- | --- |
| file | `0400`, `0444`, `0600`, `0644` | readable; owner-write bit controls replacement/removal |
| directory | `0500`, `0555`, `0700`, `0755` | read lists; execute traverses; owner-write controls child mutations |

Group and other bits are collapsed into the manifest's public/shared read
decision; group identity is not modeled. Setuid, setgid, sticky, and executable
file bits are invalid. `chmod` is unsupported in version 1: modes are selected
when an entry is created and may change only as part of a future explicitly
versioned metadata operation.

Underlying Iroh possession is necessary but not sufficient. A read requires a
valid local/read ticket capability and either `public_read`, owner identity, or
membership in `readers`/`writers`. A mutation additionally requires the write
capability, writer membership, applicable owner-write directory/file mode, and
a successful manifest CAS. The ACL never grants rights absent from the Iroh
capability. A sidecar unable to authenticate the caller MUST fail closed.

## Backend configuration version 1

Persisted YAML or JSON for a named backend MUST decode to a JSON-compatible
object that validates against `iroh-backend-config.schema.json` before it is
used or written. The contract is independent of the serialization container;
YAML tags, aliases that produce cycles, non-string keys, and non-JSON scalar
types are invalid.

The backend `type` is exactly `iroh`. `namespace.id` is always explicit so an
unexpected ticket cannot redirect a mount. `namespace.access` is `read-only`
or `read-write`; read-write configuration requires `write_capability_ref`.
`service.rpc_endpoint` accepts local Unix sockets and Windows named pipes only.
TCP, HTTP, wildcard binds, relative Unix paths, shell commands, and subprocess
argument arrays are not backend configuration.

Every sensitive value is represented by a reference with this grammar:

```text
secretref:<provider>:<identifier>
```

The allowed providers are `secure-config`, `enhanced-secrets`,
`credential-manager`, and `environment`. The identifier names a record or
environment variable; it is not the value. `node_key_ref` identifies the node
private key, `write_capability_ref` the namespace write capability, and
`read_ticket_ref` an optional read ticket. Resolvers MUST retrieve the secret
only at the last responsible moment, never write the resolved value back, and
redact both value and reference identifier from externally visible diagnostics.
Missing providers and records fail closed.

Property names such as `ticket`, `token`, `secret`, `private_key`, `node_key`,
`write_capability`, command-line arguments, and arbitrary extension mappings
are not accepted. Schema validation therefore rejects common inline-secret
forms. Implementations MUST additionally apply recursive secret scanning before
persistence; schema-valid text that is known to be secret material is still a
policy violation.

Timeout values are finite seconds greater than zero and at most one hour.
`connect_seconds` covers local RPC connection and version negotiation;
`operation_seconds` is the default deadline for one storage request; and
`shutdown_seconds` covers graceful service shutdown. Deadlines do not include
unbounded implicit retries.

`sync.conflict_policy` is fixed to `fail`. `read_consistency` is either `local`
or `synchronized`. Synchronized reads require sync to be enabled and wait for
the requested synchronization barrier before choosing a snapshot; failure or
timeout does not fall back to local. `on_open` controls whether opening a
namespace starts that barrier. It does not apply to immutable blob URLs.

## Consistency and mutation model

Blob reads have strong content integrity: all returned bytes are verified
against the requested BLAKE3 hash, including completed ranged-transfer state.
A mismatch produces `IROH_INTEGRITY_ERROR` and no bytes are committed to a
destination or cache as valid.

Namespace reads operate on one verified manifest snapshot per high-level
operation. A listing or stream never splices entries from two heads. Local
read-after-write is guaranteed after a successful CAS. Replication between
peers is eventually consistent unless the caller requests the synchronized
barrier. Offline local reads may succeed only from a fully verified local
manifest and blobs; missing content remains `IROH_SERVICE_UNAVAILABLE` or
`IROH_NOT_FOUND` according to whether its absence is known.

Writes stage bytes in a private local file, ingest and verify the immutable
blob, construct a new full manifest, and compare-and-swap the namespace head.
The successful head change is the commit point. A failed CAS returns
`IROH_CONFLICT`; it never applies last-writer-wins, silently rebases, or
overwrites the winning manifest. A caller may explicitly reread, reapply its
operation, and retry. Retrying the identical request against the same observed
head is idempotent. Abandoned blobs are unreferenced and remain subject to the
separate lease/retention/GC policy.

Copy and rename modify manifest entries and reuse immutable blob hashes. Delete
publishes tombstones and releases live references only after commit. Recursive
operations and explicit fsspec transactions publish one manifest revision or
none. Cross-namespace moves are copy-plus-delete and are not atomic across
namespaces. There is no fallback to IPFS, local-file storage, another backend,
or an older schema when any Iroh step fails.

## Synchronous and asynchronous behavior

The asynchronous implementation is canonical. Every potentially blocking RPC,
disk, transfer, sync, and service operation has an awaitable path and must not
block the event-loop thread. Synchronous fsspec methods are bounded adapters
that run the same operation and return the same value or typed failure. They
MUST NOT call `asyncio.run` from an already-running event loop, create detached
background work, or return before a manifest commit completes.

Cancellation is cooperative and prompt at stream/RPC boundaries. Before the
commit point it cleans private staging state and returns `IROH_CANCELLED`; after
the sidecar reports a successful CAS, cancellation cannot report the mutation
as uncommitted. If the commit result is unknown, the adapter returns a typed I/O
failure with the operation identifier and requires head reconciliation before
retry. Timeout follows the same reconciliation rule. Sync and async APIs expose
identical error codes, redacted context, snapshot, overwrite, and range
semantics.

## Stable error contract

Public Iroh failures carry a stable `code`, safe message, operation name, and
redacted structured context. Upstream exception text, tickets, capabilities,
node keys, raw RPC payloads, and local secret-store identifiers are never
included. Codes are versioned API; implementations may add safe detail but may
not substitute an untyped exception.

| Code | Meaning / normal Python surface |
| --- | --- |
| `IROH_INVALID_URL` | Unsupported or structurally invalid URL / `ValueError` |
| `IROH_INVALID_PATH` | Path normalization or limit violation / `ValueError` |
| `IROH_INVALID_NAMESPACE` | Malformed or mismatched namespace ID / `ValueError` |
| `IROH_INVALID_HASH` | Malformed immutable BLAKE3 hash / `ValueError` |
| `IROH_UNSUPPORTED_SCHEMA` | Manifest/config version is not exactly supported |
| `IROH_CONFIG_INVALID` | Schema or semantic configuration failure / `ValueError` |
| `IROH_CREDENTIAL_REQUIRED` | Required secret reference cannot be resolved |
| `IROH_CREDENTIAL_INVALID` | Resolved capability/ticket/key is unusable |
| `IROH_PERMISSION_DENIED` | Capability, ACL, or mode denies access / `PermissionError` |
| `IROH_NOT_FOUND` | Verified snapshot contains no live entry / `FileNotFoundError` |
| `IROH_ALREADY_EXISTS` | Exclusive create or destination collision / `FileExistsError` |
| `IROH_NOT_DIRECTORY` | A traversed component is a file / `NotADirectoryError` |
| `IROH_IS_DIRECTORY` | A file-only operation targets a directory / `IsADirectoryError` |
| `IROH_NOT_EMPTY` | Non-recursive removal targets a non-empty directory / `OSError` |
| `IROH_CONFLICT` | Namespace head CAS or revision precondition failed |
| `IROH_SERVICE_UNAVAILABLE` | Sidecar absent, unhealthy, or required content unavailable |
| `IROH_VERSION_MISMATCH` | Sidecar/RPC compatibility bundle is not selected by IROH-001 |
| `IROH_TIMEOUT` | Deadline expired; commit state is included safely |
| `IROH_CANCELLED` | Caller cancellation completed / async cancellation surface |
| `IROH_INTEGRITY_ERROR` | Hash, signature, manifest link, or size verification failed |
| `IROH_IO_ERROR` | Local staging, IPC, or indeterminate commit I/O failure / `OSError` |
| `IROH_UNSUPPORTED_OPERATION` | Deliberately unsupported filesystem/POSIX feature / `NotImplementedError` |
| `IROH_SYNC_FAILED` | Explicit synchronization or barrier failed without fallback |

Lookup methods such as `exists` may translate only `IROH_NOT_FOUND` to `False`.
They MUST propagate permission, service, integrity, version, schema, timeout,
and configuration failures. This prevents an outage from masquerading as an
empty filesystem.

## Unsupported POSIX and filesystem features

Version 1 is a versioned object filesystem, not a POSIX mount. These features
fail deterministically with `IROH_UNSUPPORTED_OPERATION`:

- symbolic links, hard links, device nodes, sockets, and FIFOs;
- uid/gid ownership, groups, POSIX ACLs, setuid/setgid/sticky bits, and `chown`;
- `chmod`, `utime`, xattrs, filesystem watches, advisory/mandatory locks,
  memory mapping, sparse files, and reflink/ioctl operations;
- executable files, open-file descriptor inheritance, and host-path exposure;
- in-place random writes, append shared by concurrent writers, and truncate of
  an existing object (a whole-file replacement is required);
- atomic operations spanning namespaces or backend instances;
- transparent resolution of IPFS CIDs as Iroh hashes or vice versa.

Implementations MUST NOT emulate unsupported security or locking semantics in
process-local memory. A later version may add a feature only with a schema and
capability-contract revision.

## Evolution and validation

The only supported manifest and backend configuration `schema_version` is the
integer `1`. A missing, string-valued, negative, zero, or future version fails
before storage/service access. Migrations produce a new validated document or
manifest revision atomically; consumers never mutate an old object in place.
Unknown fields are rejected so a newer producer cannot be partially
interpreted by an older consumer.

Run the offline contract suite from the `external/ipfs_kit` repository:

```bash
python -m pytest -q tests/test_iroh_filesystem_contract.py
```

It validates both schemas and golden fixtures, semantic invariants, exact URL
and error vocabulary, rejection of malformed hashes and paths, rejection of
inline secret material, and fail-closed unsupported schema versions.
