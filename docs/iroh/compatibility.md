# Iroh upstream compatibility decision

Decision: IROH-001  
Status: accepted  
Audit date: 2026-07-12  
Machine-readable authority: [`ipfs_kit_py/resources/iroh-releases.json`](../../ipfs_kit_py/resources/iroh-releases.json)

## Decision

IPFS Kit supports one exact Iroh source bundle:

| Component | Version | Purpose | Enabled direct features |
| --- | --- | --- | --- |
| `iroh` | 1.0.2 | authenticated QUIC endpoints, discovery, and relay transport | `fast-apple-datapath`, `metrics`, `portmapper`, `tls-ring` |
| `iroh-blobs` | 0.103.0 | BLAKE3 blob storage, transfer, ranged reads, and tags | `fs-store`, `hide-proto-docs`, `metrics`, `rpc` |
| `iroh-docs` | 0.101.0 | signed, eventually consistent manifest replication | `fs-store`, `metrics`, `redb-v2-migration`, `rpc` |
| `iroh-gossip` | 0.101.0 | live synchronization required by `iroh-docs` | `metrics`, `net` |

All four crate manifests declare Rust 1.91 as their minimum supported Rust
version. Their exact crates.io SHA-256 checksums,
repository tags, and commits are pinned in the machine-readable record. Cargo
default features are enabled, and each crate's selected direct feature set is
recorded above and in the machine-readable record. The dependency-unified
feature graph remains lockfile/build evidence rather than part of this record.
Cargo must build the bundle from a
checked-in lockfile with `--locked`; a compatible semver range is not an
acceptable production pin. Any feature-policy change creates a different
bundle even when crate versions remain unchanged.

This combination is selected because `iroh-docs` 0.101.0 explicitly updates
its dependency set to Iroh 1.0, `iroh-blobs` 0.103, and `iroh-gossip` 0.101.
Iroh 1.0.2 is the current 1.0 patch release at the audit date and includes the
1.0.1 compatibility fix plus transport receive fixes. This is a bundle
decision, not four independent version decisions.

## Why there is an IPFS Kit sidecar

Iroh 1.x is a protocol-library ecosystem. The official Iroh 1.0.2 release
publishes `iroh-relay` and `iroh-dns-server` executables, but no general-purpose
`iroh` blobs/docs daemon or filesystem CLI. Neither server provides the local
blob store and document APIs required by this backend. Installing one under the
name `iroh` would be both incorrect and unsafe.

The production runtime is therefore a project-owned binary named
`ipfs-kit-iroh-sidecar`, initially version 0.1.0, compiled from the exact bundle
above. It exposes protocol version 1 over local IPC. Its RPC is the operation
path; its CLI surface selected by this decision is limited to the
side-effect-free `--version` diagnostic.
Subprocess CLI calls must never be the per-file read/write path.

The selected RPC capability groups are:

- `system.version`, `system.capabilities`, `system.health`, and graceful
  shutdown;
- blob ingest, stat, ranged read/export, reference protection, and delete;
- manifest namespace open/create, read, compare-and-swap publication, and
  history inspection; and
- peer synchronization start, progress, cancellation, and status.

The exact selected method identifiers are recorded under
`sidecar.rpc.required_methods` in the machine-readable authority. Later
contract work may define their request and response bodies, but it may not
silently rename, omit, or add a required operation: doing so requires a new
protocol version and compatibility decision. Likewise, health or bootstrap CLI
subcommands are not assumed to exist merely because they are useful diagnostic
concepts; adding one requires a schema and record update.

IROH-002 and IROH-006 own the exact request, response, error, framing, and
redaction contracts for these selected method identifiers. No unstable
upstream Rust type or `irpc` message crosses
the Python/sidecar boundary. Unknown RPC protocol versions, missing
capabilities, malformed responses, or version mismatches fail before a storage
operation is attempted.

The required diagnostic command is:

```text
$ ipfs-kit-iroh-sidecar --version
ipfs-kit-iroh-sidecar 0.1.0 (protocol 1; iroh 1.0.2; iroh-blobs 0.103.0; iroh-docs 0.101.0; iroh-gossip 0.101.0)
```

The command writes exactly one UTF-8 line to stdout, nothing to stderr, and
returns zero. Golden records for every platform are under
`tests/fixtures/iroh/version/`. They are contract fixtures while the
distribution state is `source-pinned`; IROH-004 must replace/confirm each with
a capture from its release artifact before changing that state to `published`.

## Platforms and distribution gate

The build matrix is:

| OS | Architectures / ABI | Archive |
| --- | --- | --- |
| Linux | x86_64 and aarch64, GNU libc | `.tar.gz` |
| Linux | x86_64 and aarch64, musl | `.tar.gz` |
| macOS | x86_64 and Apple silicon | `.tar.gz` |
| Windows | x86_64 MSVC | `.zip` |

These are supported build targets, not currently installable binary artifacts.
Every platform deliberately has `installable: false` in the release record.
The installer must reject the bundle until IROH-004 publishes an artifact for
the detected target and atomically adds its HTTPS URL, nonzero byte size, and
SHA-256 digest to the record. The JSON Schema makes those three fields
mandatory when `installable` becomes true and forbids them when false. There is
no source-build fallback during ordinary Python import or backend use.

Archive names follow
`ipfs-kit-iroh-sidecar-v{version}-{rust_target}.{archive_format}`. Archives may
contain only the one appropriately named executable plus release metadata and
license notices. Platform detection must distinguish GNU libc from musl and
must reject 32-bit, unknown libc, and unlisted targets.

## Supply-chain verification

Source checksums in the record come from each explicitly recorded crates.io
version-API endpoint and identify the exact `.crate` archives. Repository tags
and commits provide review
provenance but do not replace those checksums. The selected crates are all
dual-licensed under MIT or Apache-2.0; the upstream spelling differs between
crate manifests (`MIT OR Apache-2.0` and `MIT/Apache-2.0`) but the licensing
choice is the same. Redistributed binaries must include both upstream license
notices and the IPFS Kit license/notice material.

At this audit date, the selected crates have no detached signature set, and the
official Iroh release assets expose SHA-256 digests but no detached signatures.
Consequently, project sidecar publication must provide both:

1. the GitHub release asset SHA-256 digest pinned in this record; and
2. a GitHub artifact attestation tied to the repository workflow and source
   commit.

The machine record identifies crates.io as the source-archive checksum
authority and the `endomorphosis/ipfs_kit_py` GitHub repository as the sidecar
artifact and attestation authority. It also records the non-shell verification
argument vector (`gh attestation verify ... --repo endomorphosis/ipfs_kit_py`)
that IROH-004 must implement or invoke without interpolation. These authorities
are part of the compatibility contract; an artifact from another repository is
not equivalent even when its bytes have the expected digest.

IROH-004 must verify both before extraction. Verification failure, absent
attestation support, a digest absent from this file, an archive-path escape,
or an unexpected archive member is fatal. A tag, TLS download, or checksum
fetched from the same mutable response as an unpinned artifact is insufficient
on its own.

Upstream audit sources:

- [Iroh 1.0.2 release and assets](https://github.com/n0-computer/iroh/releases/tag/v1.0.2)
- [Iroh 1.0.2 crate](https://crates.io/crates/iroh/1.0.2)
- [iroh-blobs 0.103.0 source](https://github.com/n0-computer/iroh-blobs/tree/v0.103.0)
- [iroh-docs 0.101.0 source](https://github.com/n0-computer/iroh-docs/tree/v0.101.0)
- [iroh-gossip 0.101.0 source](https://github.com/n0-computer/iroh-gossip/tree/v0.101.0)

## Data-format boundaries

Iroh blob identifiers are native 32-byte BLAKE3 hashes and remain distinct
from IPFS CIDs. Blob bytes are immutable. The Iroh blob store's file layout,
Bao encoding, tags, and `irpc` wire types are private sidecar implementation
details and must not be persisted in Python backend configuration.

An Iroh document is a namespace containing signed entries keyed by application
bytes. Entries identify an author, key, timestamp, content length, and BLAKE3
content hash; blob content is stored and transferred separately. IPFS Kit will
store its versioned directory-manifest format as document values only after
IROH-002 freezes that format. Raw upstream entries are not a POSIX directory,
and document convergence is not an atomic filesystem transaction.

Namespace secrets, author keys, write capabilities, node keys, and tickets are
credentials. Their upstream binary/text encodings are opaque to IPFS Kit and
must be handled through secret references. They may not appear in backend YAML,
RPC logs, process arguments, metrics, fixtures, exceptions, or lineage. Ticket
parsing is disabled until IROH-002 specifies an accepted grammar and redaction
rules.

## Breaking boundaries

The following boundaries require a new compatibility bundle:

- Iroh releases before 1.0 use pre-stability endpoint, key, relay, and
  transport APIs.
- `iroh-blobs` before 0.103 is not the Iroh 1.0 dependency line. Its store and
  RPC APIs are not assumed compatible.
- `iroh-docs` before 0.101 uses older dependency and redb migration lines.
  Versions 0.99 and 0.100 explicitly contain breaking dependency/wire changes.
- Any newer minor release of blobs, docs, or gossip may change a Rust API,
  storage format, or protocol. The 0.x components are never floated.
- Any sidecar RPC protocol other than 1 is incompatible even if all upstream
  crate versions happen to match.

Patch upgrades are not automatic. A security fix can justify expedited review,
but it cannot bypass the upgrade procedure.

## Upgrade and rollback procedure

1. Open an upgrade change containing a proposed new bundle ID. Read every
   component changelog from the current pin to the candidate and record API,
   wire, ticket, hash, and persistent-store changes.
2. Obtain crates.io checksums, tags, commits, Rust MSRV, licenses, and dependency
   features independently. Update the lockfile and run the Rust supply-chain
   audit. Never edit a checksum to make a failed download pass.
3. Build each target in an isolated reproducible workflow. Run sidecar unit,
   RPC contract, two-node transfer, manifest conflict, restart, corruption,
   cancellation, and redaction tests.
4. Copy a production-format data directory. Test old-sidecar read, new-sidecar
   migration/read/write, restart, and peer sync against both old and new peers.
   A migration must be one-way only after an explicit backup and receipt.
5. Publish immutable draft artifacts, generate GitHub attestations, independently
   verify them and their SHA-256 values, and capture `--version` on every target.
   Update the platform fixtures and only then set those entries installable.
6. Roll out as a canary without deleting the retained prior binary or backup.
   Confirm capability negotiation, health, data integrity, and transfer metrics
   before promotion.
7. Roll back by stopping the sidecar and atomically restoring the prior binary.
   Restore the pre-migration data-directory snapshot if the new release changed
   persistent data. Never start an older binary on a migrated live directory
   unless the migration test proved it safe.

Changing the supported bundle requires updating this document, the JSON record,
schema-valid platform artifacts, every version fixture, and the named
conformance tests in the same change.

## Validation

From `external/ipfs_kit`:

```bash
python -m pytest -q tests/test_iroh_compatibility_record.py
```

This validates the release file with JSON Schema Draft 2020-12, verifies exact
source pins, ensures platform IDs/targets are unique, and requires a matching
`--version` record for every supported target. The schema itself is shipped as
`ipfs_kit_py/resources/iroh-releases.schema.json` alongside the release record.
Each version record is independently validated by the shipped
`ipfs_kit_py/resources/iroh-version-fixture.schema.json`. An
`artifact-capture` fixture is invalid unless it records both its capture time
and artifact digest; the current `contract-golden` fixtures intentionally omit
both until IROH-004 publishes the first sidecar artifacts.
