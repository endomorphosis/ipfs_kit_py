# Iroh filesystem capability and conformance matrices

- Decision: IROH-003
- Status: frozen, version 1
- Effective: 2026-07-13
- Compatibility bundle: `iroh-1.0.2-ipfs-kit.1`
- Depends on: [IROH-002](filesystem-contract.md)

This document is the normative capability contract for the version-1
`IrohFileSystem`. It classifies the fsspec and VFS surface without presenting
Iroh blobs as a POSIX filesystem. The URL, manifest, permission, consistency,
and error rules in the [filesystem contract](filesystem-contract.md) remain
authoritative. The keywords **MUST**, **MUST NOT**, **SHOULD**, and **MAY** are
requirements.

## Classification vocabulary

Every operation has exactly one of these classifications:

| Classification | Meaning |
| --- | --- |
| `native` | The sidecar exposes the required Iroh primitive directly. The Python layer still validates inputs, permissions, deadlines, results, and redaction. |
| `emulated` | IPFS Kit implements filesystem semantics over verified immutable blobs and a versioned directory manifest. Emulation is persistent and peer-visible after manifest synchronization; it is never process-local bookkeeping. |
| `unsupported` | Version 1 cannot provide the promised semantics. The call fails deterministically with `IROH_UNSUPPORTED_OPERATION`; it does not silently no-op, approximate the behavior, or fall back to another backend. |

A classification describes how the capability is implemented, not its quality
or availability. `emulated` operations are required, supported operations.
They have the same sync/async, permission, integrity, and stable-error contract
as `native` operations.

## Required operation capability matrix

The operation name in the first column is the canonical conformance key. Each
required operation occurs exactly once in this matrix.

| Operation | Classification | Iroh primitive or emulation | Version-1 semantics |
| --- | --- | --- | --- |
| `ls` | `emulated` | Read one verified manifest snapshot and select immediate children. | Supports `detail=True` and `detail=False`. Results are sorted by normalized UTF-8 path bytes. A file target is returned as a one-item result; a missing path is not an empty directory. Tombstones are never returned. |
| `info` | `emulated` | Resolve one live manifest entry; immutable blob metadata uses `blobs.stat`. | Returns the common fields defined below. Root, file, and directory entries are supported. The result belongs to one verified snapshot. |
| `open` | `emulated` | Dispatch a reader to verified blob access or a writer to private staging, blob ingest, and manifest CAS. | Read, whole-file write, and exclusive-create modes are supported as specified below. A successful write is visible only after close/commit succeeds. |
| `ranged read` | `native` | Sidecar `blobs.read_range`, with `blobs.stat` when an end-relative offset requires size. | `cat_file(start, end)` and seekable read handles return the half-open byte interval `[start, end)`. Every completed range is content-verified before it is accepted into cache or an output destination. |
| `write` | `emulated` | Stage privately, ingest an immutable BLAKE3 blob, build a new manifest, then compare-and-swap its head. | Creates or wholly replaces one file. It never performs an in-place blob mutation. The manifest CAS is the commit point; a failed commit exposes no partial file revision. |
| `mkdir` | `emulated` | Add directory entries and publish one manifest revision. | Supports one directory and parent creation. Existing entries, missing parents, traversal through a file, permissions, and root behavior follow the rules below. |
| `rm` | `emulated` | Replace live entries with tombstones and publish one manifest revision. | Supports file removal and atomic recursive subtree removal. Non-recursive removal of a non-empty directory fails. Blob release/GC occurs only after the tombstone revision commits. |
| `cp` | `emulated` | Reuse blob hashes and clone manifest metadata when possible; fetch and ingest only where a destination namespace lacks the blob. | File and recursive directory copy are supported. A same-namespace copy commits once. A cross-namespace copy commits only the destination and is not an atomic multi-namespace operation. |
| `mv` | `emulated` | Rename manifest paths while retaining immutable blob hashes. | Same-namespace file or recursive directory moves commit in one revision. Cross-namespace moves are explicit copy-then-delete and are not atomic across namespaces. |
| `find` | `emulated` | Filter and walk a single verified manifest snapshot. | Supports `maxdepth`, `withdirs`, and `detail`; results are deterministic and omit tombstones. It performs no per-entry network listing. |
| `glob` | `emulated` | Match fsspec glob syntax against normalized live paths in one verified manifest snapshot. | Supports segment wildcards, character classes, and recursive `**`. Matching is case-sensitive and never follows links because links are unsupported. |
| `exists` | `emulated` | Resolve a live entry in one verified manifest snapshot, or stat an immutable blob. | Returns `False` only for `IROH_NOT_FOUND`; every other error is propagated unchanged. A tombstone is absent. |
| `sync` | `native` | Sidecar `sync.start`, `sync.progress`, `sync.cancel`, and `sync.status` over Iroh Docs/gossip. | Explicit sync and configured synchronized-read barriers are supported. Completion selects and verifies a head; it never resolves a conflicting head with last-writer-wins and never falls back to a local-only read. |

### Common metadata shape

`info`, detailed `ls`, detailed `find`, and detailed `glob` MUST return mutually
consistent fsspec metadata for the same snapshot. Each result contains:

| Field | Contract |
| --- | --- |
| `name` | Canonical `iroh://` or `iroh+blob://` URL with credentials and ticket references excluded. |
| `type` | Exactly `file` or `directory`. |
| `size` | Exact non-negative byte size for a file; `0` for a directory. |
| `mtime` | Entry UTC RFC 3339 timestamp for namespace paths; absent for a raw blob unless the local store has a safe, stable ingest timestamp. |
| `mode` | The validated manifest mode for namespace paths; absent for raw blobs. |
| `blob_hash` | Lowercase 64-hex BLAKE3 hash for a file; absent for a directory. This is never named or converted to an IPFS CID. |
| `revision` | Namespace manifest generation used by the operation; absent for a raw blob. |
| `metadata` | A copy of the bounded, secret-free scalar entry metadata; absent for raw blobs. |

Additional private sidecar fields, local cache paths, provider identities,
tickets, credential references, and capability material MUST NOT be returned.
The non-detailed forms return canonical names only.

## Open, read, and write conformance

| Surface | Classification | Required behavior | Stable failure |
| --- | --- | --- | --- |
| `open(path, "rb")` / `open(path, "r")` | `emulated` | Pins a verified manifest snapshot and opens the referenced immutable blob. Text mode is an fsspec text wrapper over the binary stream. | Missing file: `IROH_NOT_FOUND`; directory: `IROH_IS_DIRECTORY`; denied read: `IROH_PERMISSION_DENIED`. |
| `cat_file(path, start=None, end=None)` | `native` | Uses a blob range request and returns the half-open interval `[start, end)`. `None` means the corresponding boundary; negative offsets are resolved relative to the verified size and boundaries are clamped to `[0, size]`. An end not greater than start returns empty bytes. | Missing file: `IROH_NOT_FOUND`; directory: `IROH_IS_DIRECTORY`; corrupt data or wrong size: `IROH_INTEGRITY_ERROR`. |
| reader `seek` and `read` | `native` | Supports `SEEK_SET`, `SEEK_CUR`, and `SEEK_END`; reads only the requested ranges and does not download skipped prefixes merely to seek. | Invalid Python argument types fail at the Python boundary; transfer failures retain their stable Iroh code. |
| `open(path, "wb")` / `open(path, "w")` | `emulated` | Creates or wholly replaces a file through private staging. The expected head is captured before commit. | Directory: `IROH_IS_DIRECTORY`; denied replacement: `IROH_PERMISSION_DENIED`; losing CAS: `IROH_CONFLICT`. |
| `open(path, "xb")` / `open(path, "x")` | `emulated` | Creates a file only when no live entry exists in the commit snapshot. | Existing live file or directory: `IROH_ALREADY_EXISTS`; losing CAS: `IROH_CONFLICT`. |
| writer `flush` | `emulated` | Flushes staging bytes only. It MUST NOT publish a partially written manifest revision. | Staging failure: `IROH_IO_ERROR`. |
| writer `close` / context exit | `emulated` | Ingests and verifies the blob, performs manifest CAS, and returns only after commit is known. Repeated close after success is harmless. | Ingest mismatch: `IROH_INTEGRITY_ERROR`; CAS loss: `IROH_CONFLICT`; indeterminate commit: `IROH_IO_ERROR`. |
| append (`"a"`, `"ab"`) | `unsupported` | No append emulation is provided, even by downloading and replacing the object implicitly. | `IROH_UNSUPPORTED_OPERATION`. |
| update (`"+"`), in-place overwrite, or truncate of an existing file | `unsupported` | Random mutation and shared file-position semantics cannot be represented by immutable blobs. An explicit whole-file `"w"` replacement remains supported. | `IROH_UNSUPPORTED_OPERATION`. |

Opening a writer is not a successful mutation. Exceptions from `close` MUST be
observable by the caller, and a context manager MUST surface them from
`__exit__`. Cancellation before commit removes private staging state. Once the
sidecar confirms CAS success, cancellation cannot report the write as
uncommitted. Timeout or cancellation with an unknown CAS result is
`IROH_IO_ERROR` with a safe operation identifier and requires head
reconciliation before retry.

## Namespace operation conformance

All manifest-reading portions of one row use one verified snapshot. Each
same-namespace mutation in a row publishes exactly one new manifest revision
or none.

| Operation and case | Required result | Stable failure |
| --- | --- | --- |
| `ls` on a directory | Immediate live children, sorted by normalized UTF-8 path bytes. | Missing target: `IROH_NOT_FOUND`; file in a traversed component: `IROH_NOT_DIRECTORY`. |
| `info` on root, directory, or file | One metadata mapping with the common shape above. | Missing target: `IROH_NOT_FOUND`. |
| `mkdir(path, create_parents=False)` | Create exactly one empty directory when its parent is live. | Existing entry: `IROH_ALREADY_EXISTS`; missing parent: `IROH_NOT_FOUND`; file parent: `IROH_NOT_DIRECTORY`. |
| `mkdir(path, create_parents=True)` / `makedirs` | Create all missing ancestors and the leaf in one revision. `exist_ok=True` accepts an existing directory, not a file. | Existing file: `IROH_ALREADY_EXISTS`; denied ancestor mutation: `IROH_PERMISSION_DENIED`. |
| `mkdir` on namespace root | With `exist_ok=True`, no-op without a revision; otherwise the root already exists. | Without `exist_ok`: `IROH_ALREADY_EXISTS`. |
| `rm` on a file or empty directory | Commit a tombstone, then release its live blob reference when applicable. | Missing target: `IROH_NOT_FOUND`; root: `IROH_PERMISSION_DENIED`. |
| non-recursive `rm` on a non-empty directory | Make no change. | `IROH_NOT_EMPTY`. |
| recursive `rm` on a directory | Tombstone the complete live subtree atomically in deterministic deepest-first planning order. | Any validation or CAS failure leaves the original subtree live. |
| `cp` file within a namespace | Add a destination entry that references the same immutable blob. | Missing source: `IROH_NOT_FOUND`; directory without recursive mode: `IROH_IS_DIRECTORY`; destination collision without overwrite: `IROH_ALREADY_EXISTS`. |
| recursive `cp` directory within a namespace | Materialize the destination subtree in one revision, preserving modes, mtimes, and safe metadata. | Destination below source: `IROH_INVALID_PATH`; CAS loss: `IROH_CONFLICT`. |
| `mv` within a namespace | Rewrite the source path and every descendant path, if any, in one revision. No content bytes are copied. | Root move: `IROH_PERMISSION_DENIED`; destination below source: `IROH_INVALID_PATH`; collision: `IROH_ALREADY_EXISTS`. |
| cross-namespace `cp` | Verify source content and commit the destination namespace. Source remains unchanged. | Destination failure uses its stable cause; no source deletion occurs. |
| cross-namespace `mv` | Perform cross-namespace copy, then delete source only after destination commit. This is not atomic across namespaces. | Atomic mode: `IROH_UNSUPPORTED_OPERATION`; delete failure leaves the committed destination and reports the delete error. |
| `find` | Return all matching live descendants from one snapshot, respecting `maxdepth` and `withdirs`. | Missing base: `IROH_NOT_FOUND`; invalid depth: Python argument validation. |
| `glob` | Return deterministic, de-duplicated live matches from one snapshot. A valid pattern with no matches returns an empty result. | Malformed URL/path: `IROH_INVALID_URL` or `IROH_INVALID_PATH`; outage and denied traversal propagate. |
| `exists` | Return `True` for a live root, directory, file, or verified immutable blob and `False` only when lookup raises `IROH_NOT_FOUND`. | Permission, integrity, schema, version, service, timeout, and configuration errors MUST propagate, never become `False`. |

Overwrite is opt-in for `cp` and `mv`. It replaces a file with a file but MUST
NOT implicitly replace a directory, merge two directory trees, or change the
type of an existing entry. Recursive requests are preflighted completely
before CAS, including ancestry, collision, mode, ACL, and path-length checks.

`iroh+blob://` has no directory namespace: `info`, `exists`, whole/ranged read,
and read-only `open` are supported; directory operations and every mutation
fail with `IROH_UNSUPPORTED_OPERATION`. `iroh+ticket://` resolves a read-only
namespace snapshot: read and discovery operations are supported, while every
mutation fails with `IROH_PERMISSION_DENIED`. A backend configured
`read-only` has the same mutation failure.

## Synchronization conformance

| Case | Required behavior | Stable failure |
| --- | --- | --- |
| explicit `sync()` | Start or join the namespace sync, report bounded progress, wait for the requested barrier, validate candidate manifests and ancestry, and select a verified head. | Peer/protocol/barrier failure: `IROH_SYNC_FAILED`; deadline: `IROH_TIMEOUT`; caller cancellation: `IROH_CANCELLED`. |
| `read_consistency="local"` | Read the latest verified local head without starting a network barrier. Missing required local content is not disguised as absence. | Unavailable required content: `IROH_SERVICE_UNAVAILABLE`; known absent entry: `IROH_NOT_FOUND`. |
| `read_consistency="synchronized"` | Complete the configured barrier before choosing the operation's manifest snapshot. | Sync failure is propagated and MUST NOT fall back to the prior local head. |
| `sync.on_open=true` | Opening a namespace establishes the same barrier once before exposing the filesystem. It does not apply to immutable blob URLs. | Same as explicit `sync()`. |
| divergent valid heads | Retain both candidates for diagnosis and fail the barrier; never choose by wall clock, arrival order, or last-writer-wins. | `IROH_CONFLICT` when a caller must resolve manifest divergence. |
| sync disabled by configuration | Local consistency remains available; a requested synchronized barrier is invalid configuration. | `IROH_CONFIG_INVALID`. |

Successful synchronization means that the selected manifest head and its
revision chain are verified. It does not mean that every referenced file blob
has been eagerly downloaded. A later blob fetch remains integrity checked and
may independently fail.

## Unsupported capability matrix

These public calls or mode requests are deliberately unsupported in version 1.
They MUST fail before side effects with a public Iroh error whose `code` is
`IROH_UNSUPPORTED_OPERATION` and whose normal Python surface is
`NotImplementedError`.

| Capability / representative call | Classification | Reason |
| --- | --- | --- |
| symbolic and hard links (`symlink`, `link`, `readlink`) | `unsupported` | Manifests have only file and directory entry kinds. |
| ownership and mode mutation (`chmod`, `chown`, POSIX ACL changes) | `unsupported` | Version 1 modes are selected at creation and ACL identities are manifest-versioned. |
| timestamp and extended metadata mutation (`touch` of an existing entry, `utime`, xattrs) | `unsupported` | No standalone metadata-mutation contract exists. Creating a new empty file through the write path is supported. |
| filesystem watches and notifications | `unsupported` | Eventually consistent document events are not promised as complete filesystem-watch semantics. |
| file locks and leases exposed as POSIX locks | `unsupported` | A manifest CAS is conflict detection, not a file lock. |
| memory mapping, file descriptors, or local host-path exposure | `unsupported` | Remote immutable content has no stable host inode or descriptor identity. |
| sparse files, reflinks, device nodes, sockets, and FIFOs | `unsupported` | These POSIX object types and allocation semantics are absent from the manifest. |
| append, random write, update mode, and truncate-existing | `unsupported` | Blobs are immutable; callers must explicitly replace a whole file. |
| atomic mutation spanning namespaces or backend instances | `unsupported` | No shared CAS domain exists. Non-atomic cross-namespace copy and move behavior is explicit. |
| implicit IPFS CID/Iroh hash conversion or backend fallback | `unsupported` | Native BLAKE3 identifiers and IPFS CIDs are distinct trust domains. |

An implementation MUST NOT inherit an `AbstractFileSystem` default that turns
one of these calls into a lossy copy/read/write sequence. The Iroh filesystem
must override or gate such defaults so the stable failure is preserved.

## Stable typed failure matrix

Argument parsing occurs before credential resolution, service access, blob
transfer, or manifest mutation. Once an operation reaches the Iroh boundary,
all failures expose a stable `code`, operation name, safe message, and redacted
structured context as required by IROH-002.

| Condition | Required code | Normal Python surface | Applies to |
| --- | --- | --- | --- |
| malformed scheme/authority or forbidden query/fragment | `IROH_INVALID_URL` | `ValueError` | every operation |
| invalid normalized path or recursive destination beneath source | `IROH_INVALID_PATH` | `ValueError` | every path operation |
| malformed/mismatched namespace or blob hash | `IROH_INVALID_NAMESPACE` / `IROH_INVALID_HASH` | `ValueError` | namespace/blob resolution |
| unsupported manifest/config version | `IROH_UNSUPPORTED_SCHEMA` | typed Iroh error | every manifest-backed operation |
| invalid backend or impossible sync configuration | `IROH_CONFIG_INVALID` | `ValueError` | open, sync, every configured operation |
| missing or unusable credential | `IROH_CREDENTIAL_REQUIRED` / `IROH_CREDENTIAL_INVALID` | typed Iroh error | ticket reads and protected namespaces |
| ACL, mode, read-only mount, or capability denial | `IROH_PERMISSION_DENIED` | `PermissionError` | discovery, read, and mutation |
| no live entry in the selected verified snapshot | `IROH_NOT_FOUND` | `FileNotFoundError` | lookup and source operations |
| exclusive create or non-overwrite collision | `IROH_ALREADY_EXISTS` | `FileExistsError` | write, mkdir, cp, mv |
| file encountered where directory required | `IROH_NOT_DIRECTORY` | `NotADirectoryError` | traversal and directory operations |
| directory encountered where file required | `IROH_IS_DIRECTORY` | `IsADirectoryError` | open/read/write and non-recursive copy |
| non-recursive removal of non-empty directory | `IROH_NOT_EMPTY` | `OSError` | rm/rmdir |
| stale expected head, revision overflow, or divergent heads | `IROH_CONFLICT` | typed Iroh error | every manifest mutation and sync reconciliation |
| sidecar unhealthy or required content unavailable | `IROH_SERVICE_UNAVAILABLE` | typed Iroh error | every sidecar operation |
| incompatible sidecar or RPC version | `IROH_VERSION_MISMATCH` | typed Iroh error | negotiation before every storage operation |
| operation deadline expires | `IROH_TIMEOUT` | typed Iroh error | transfer, mutation, and sync |
| cooperative caller cancellation | `IROH_CANCELLED` | async cancellation surface | transfer, mutation, and sync before known commit |
| hash, size, signature, or manifest-link mismatch | `IROH_INTEGRITY_ERROR` | typed Iroh error | stat, read, ingest, snapshot, sync |
| local staging/IPC failure or indeterminate commit | `IROH_IO_ERROR` | `OSError` | open/write/close and RPC transport |
| deliberately unavailable semantic | `IROH_UNSUPPORTED_OPERATION` | `NotImplementedError` | unsupported matrix above |
| peer synchronization or barrier failure | `IROH_SYNC_FAILED` | typed Iroh error | explicit sync and synchronized reads |

No discovery operation may broadly catch `OSError`, an Iroh base exception, or
an RPC error and return an empty result. In particular, only `exists` translates
`IROH_NOT_FOUND`, and it translates it to `False`. `ls`, `find`, and `glob`
return empty results only for a valid, readable snapshot whose query genuinely
has no results.

## Synchronous and asynchronous conformance

The asynchronous implementation is canonical. Every operation in the required
matrix MUST have an awaitable implementation, and every potentially blocking
RPC, transfer, disk, sync, and commit step MUST yield rather than block the
event-loop thread. Synchronous fsspec methods are bounded adapters over the same
implementation.

For identical inputs and snapshot state, sync and async surfaces MUST have:

- the same classification, return shape, ordering, range boundaries, and
  overwrite behavior;
- the same manifest commit point and atomicity boundary;
- the same stable error `code`, safe context, and redaction;
- the same configured deadline, without detached work continuing after return;
- prompt cancellation cleanup before commit and reconciliation after an
  indeterminate result.

Sync adapters MUST NOT call `asyncio.run` in an already-running event loop.
They must direct such misuse to the async API with a stable, safe Python error,
without starting the requested operation.

## Conformance requirements

An implementation conforms to this matrix only when offline unit tests and
sidecar-backed integration tests cover all of the following:

1. Every required operation's success path on root, file, directory, missing
   path, and wrong entry type where those cases apply.
2. Detailed and non-detailed discovery results, deterministic ordering, one
   manifest snapshot per call, and omission of tombstones and secrets.
3. Whole and ranged reads at empty, first-byte, middle, EOF, clamped, and
   end-relative boundaries, including integrity failure before acceptance.
4. Whole-file create, exclusive create, replacement, close-time commit,
   conflict, cancellation, timeout, and abandoned-staging cleanup.
5. Atomic same-namespace mkdir, recursive remove, copy, and move, plus the
   documented non-atomic cross-namespace boundaries.
6. Local and synchronized reads, progress, cancellation, peer failure,
   divergent heads, and the no-fallback rule.
7. Every unsupported capability above returning
   `IROH_UNSUPPORTED_OPERATION` before side effects.
8. Sync and async parity for values, snapshots, cancellation, deadlines, and
   all stable failure codes.
9. Fail-closed behavior for unavailable or version-skewed sidecars, malformed
   manifests, invalid credentials, permission denial, and corrupt blobs.
10. Redaction of raw tickets, credential-reference identifiers, capabilities,
    node keys, local secret-store data, RPC payloads, and peer-sensitive values
    from exceptions, logs, metrics, tracing, and VFS lineage.

Run the offline document suite from the `external/ipfs_kit` repository:

```bash
python -m pytest -q tests/test_iroh_capability_matrix.py
```

The suite verifies the exact required-operation set and classifications, the
unsupported surface, sync/async parity, deterministic snapshot semantics, and
the stable typed-failure rules.
