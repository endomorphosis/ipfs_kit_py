# Iroh upstream compatibility decision

- Decision: IROH-001
- Status: accepted for implementation; binary distribution gated
- Audited: 2026-07-12
- Release bundle: `iroh-1.0.2-ipfs-kit.1`
- Sidecar protocol: 1
- Machine record: [`../../ipfs_kit_py/resources/iroh-releases.json`](../../ipfs_kit_py/resources/iroh-releases.json)

## Decision

IPFS Kit will build its managed Iroh sidecar against one exact, audited bundle:
`iroh` 1.0.2, `iroh-blobs` 0.103.0, `iroh-docs` 0.101.0, and
`iroh-gossip` 0.101.0. Cargo's compatible-version resolution is not an
authorization to change any member of this bundle. The lockfile, crate archive
checksums, features, tags, commits, minimum Rust version, and sidecar protocol
must all agree with the machine record.

The supported runtime is an IPFS Kit-owned binary named
`ipfs-kit-iroh-sidecar`, not an upstream general-purpose CLI. Upstream Iroh is
a protocol-library ecosystem. Its published `iroh-relay` and
`iroh-dns-server` binaries provide relay and discovery infrastructure; neither
provides the local blob, document, and filesystem-manifest service required by
this backend.

The sidecar is currently **source-pinned**, not published. All selected target
platforms are therefore `installable: false`. Installers and runtime discovery
must fail closed until per-platform URLs, sizes, SHA-256 digests, attestations,
and captured version fixtures are added in a new audited revision. A contract
fixture does not assert that an artifact exists.

## Normative artifacts

The JSON record is the source consumed by installers and runtime compatibility
checks. The schemas reject unknown fields and encode the supported component
set, target matrix, artifact promotion gate, and exact version-output shape.

| Artifact | Purpose |
| --- | --- |
| `ipfs_kit_py/resources/iroh-releases.json` | Selected releases, checksums, interfaces, targets, formats, licenses, and upgrade policy |
| `ipfs_kit_py/resources/iroh-releases.schema.json` | Draft 2020-12 schema for the compatibility record |
| `ipfs_kit_py/resources/iroh-version-fixture.schema.json` | Draft 2020-12 schema for recorded `--version` results |
| `tests/fixtures/iroh/version/*.json` | One version contract fixture for every selected target |

If this document and the JSON disagree, treat the configuration as invalid and
stop. Correct both in one reviewed compatibility change; do not silently choose
one.

## Selected upstream components

| Crate | Version | Effective feature set | Rust | Archive SHA-256 | Tag commit |
| --- | --- | --- | --- | --- | --- |
| `iroh` | 1.0.2 | `fast-apple-datapath`, `metrics`, `portmapper`, `tls-ring` | 1.91 | `5fca9b4b462c343ff88fc0af4096c186f939b602a0bc08723536ef2c31c93971` | `c3ccf502c3881444811fbb3a3a0eeaf850594dba` |
| `iroh-blobs` | 0.103.0 | `fs-store`, `hide-proto-docs`, `rpc` plus `metrics` | 1.91 | `5be50b0e2d0a9ba65cee4e0dfb708b3704e02ad12bd4c14c6307e94245943126` | `e82cbdcbdac9a78033174aad55e3199b2cf4c0dc` |
| `iroh-docs` | 0.101.0 | `fs-store`, `metrics`, `redb-v2-migration`, `rpc` | 1.91 | `8fd1bd5e39d0321a3c4a2bcef9650476c076e2df41a0e84577eca23d6de6c8ab` | `091e8cac47bbc49cdb84b0bfed227cc163b61dfe` |
| `iroh-gossip` | 0.101.0 | `metrics`, `net` | 1.91 | `4e1dc4b05f73e7a1b9e83b531eb63c3fd671b0af3aeb13b59c546dd7ca747515` | `2ce78afe09d89d41d123f28eac19bdc831609cc8` |

The `metrics` feature is explicitly selected for `iroh-blobs`, although it is
not part of that crate's defaults. Features listed in the JSON are the required
effective feature set, not a suggestion to enable every available feature.

Audit evidence is available from the authoritative
[crates.io version API](https://crates.io/api/v1/crates/iroh/1.0.2) and the
upstream tagged repositories for
[`iroh`](https://github.com/n0-computer/iroh/tree/v1.0.2),
[`iroh-blobs`](https://github.com/n0-computer/iroh-blobs/tree/v0.103.0),
[`iroh-docs`](https://github.com/n0-computer/iroh-docs/tree/v0.101.0), and
[`iroh-gossip`](https://github.com/n0-computer/iroh-gossip/tree/v0.101.0).
During this audit, each `.crate` download was hashed independently and matched
the checksum published by crates.io.

## Binary and interface contract

The selected binary identity is:

```text
ipfs-kit-iroh-sidecar 0.1.0 (protocol 1; iroh 1.0.2; iroh-blobs 0.103.0; iroh-docs 0.101.0; iroh-gossip 0.101.0)
```

`ipfs-kit-iroh-sidecar --version` must exit 0, write exactly that line plus a
single LF to stdout, and write nothing to stderr. Version parsing must be exact;
extra prose, a different protocol, omitted component versions, malformed UTF-8,
or a nonzero exit is incompatible.

The CLI is diagnostic-only. It must not become the per-operation filesystem
transport. The production boundary is a versioned local IPC RPC service with
these capability groups and required methods:

- `system`: `version`, `capabilities`, `health`, `shutdown`
- `blobs`: `ingest`, `stat`, `read_range`, `protect`, `release`
- `manifests`: `open`, `create`, `read`, `compare_and_swap`, `history`
- `sync`: `start`, `progress`, `cancel`, `status`

IROH-002 and IROH-006 will freeze request, response, error, framing, transport,
timeout, cancellation, and redaction details. This decision reserves the method
surface and establishes that protocol version 1 must be negotiated before any
storage operation.

## Supported target matrix

“Supported” here means selected as a release target. It does not mean a binary
is presently available. Each target has a golden contract fixture so builds can
verify their output before promotion.

| Platform ID | Rust target | Archive | Executable | Fixture | Installable now |
| --- | --- | --- | --- | --- | --- |
| `linux_x86_64_gnu` | `x86_64-unknown-linux-gnu` | `tar.gz` | `ipfs-kit-iroh-sidecar` | contract golden | no |
| `linux_x86_64_musl` | `x86_64-unknown-linux-musl` | `tar.gz` | `ipfs-kit-iroh-sidecar` | contract golden | no |
| `linux_aarch64_gnu` | `aarch64-unknown-linux-gnu` | `tar.gz` | `ipfs-kit-iroh-sidecar` | contract golden | no |
| `linux_aarch64_musl` | `aarch64-unknown-linux-musl` | `tar.gz` | `ipfs-kit-iroh-sidecar` | contract golden | no |
| `macos_x86_64` | `x86_64-apple-darwin` | `tar.gz` | `ipfs-kit-iroh-sidecar` | contract golden | no |
| `macos_aarch64` | `aarch64-apple-darwin` | `tar.gz` | `ipfs-kit-iroh-sidecar` | contract golden | no |
| `windows_x86_64` | `x86_64-pc-windows-msvc` | `zip` | `ipfs-kit-iroh-sidecar.exe` | contract golden | no |

Linux aarch64 is the spelling used by the manifest even where a host reports
`arm64`. Linux libc detection must distinguish GNU from musl. macOS targets have
no libc selector. Windows arm64 and all 32-bit targets are unsupported by this
bundle and must be rejected rather than mapped to a nearby target.

### Artifact promotion gate

Promotion from `source-pinned` to `published` is a single atomic record change:

1. Build all seven targets from the pinned lockfile and source checksums.
2. Publish immutable archives named by the manifest template.
3. Add each archive's exact HTTPS URL, byte size, and lowercase SHA-256 digest.
4. Produce GitHub artifact attestations for the repository and verify each with
   the command recorded under `verification.sidecar_artifacts.attestation`.
5. Run the extracted executable on its native target and replace that target's
   `contract-golden` fixture with an `artifact-capture` containing UTC capture
   time and the same archive SHA-256.
6. Set the sidecar status to `published` and all seven targets to
   `installable: true`; validate the complete record before release.

The schema deliberately prevents a partial promotion: source-pinned or
withdrawn releases cannot advertise installable targets, while published
releases require artifact metadata for every target. Detached upstream
signatures are not available for this IPFS Kit-owned binary. SHA-256 protects
identity; the required repository-bound artifact attestation supplies
provenance. An installer must verify both before extraction.

## Data-format decisions

- Blob identifiers are lowercase hexadecimal encodings of 32-byte BLAKE3-256
  digests. They remain native Iroh hashes and must never be labeled as IPFS CIDs.
- `iroh-docs` provides signed, eventually consistent key/value entries whose
  values can reference `iroh-blobs` content.
- A filesystem is an IPFS Kit versioned directory manifest layered over those
  primitives. Iroh blobs are immutable content, not POSIX files.
- Upstream persistent-store, Bao, redb, and irpc encodings are sidecar-private.
  They are not Python API formats and cannot be exposed as a compatibility
  promise. IROH-002 will define the portable manifest format.
- Tickets, private keys, write capabilities, and other credential encodings are
  opaque. Only credential references may cross persisted backend configuration.

## Supply-chain and license policy

Crate archives must be downloaded over HTTPS from the exact crates.io URLs in
the record and verified with SHA-256 before use. crates.io does not publish a
detached signature for these four archives, so the machine record explicitly
sets their signature source to `null`; a checksum is not misrepresented as a
signature. Builds must use a committed lockfile, reject checksum or version
drift, run the project's dependency audit, and avoid build-time network access
after the verified inputs are staged.

All selected upstream crates are dual-licensed under MIT or Apache-2.0. The
spelling in crate metadata differs (`MIT OR Apache-2.0` versus
`MIT/Apache-2.0`), but the redistribution decision is the SPDX expression
`MIT OR Apache-2.0`. Every sidecar archive must ship the upstream
`LICENSE-MIT` and `LICENSE-APACHE` texts together with applicable IPFS Kit
license and notice material. Dependency license and vulnerability audits remain
release gates; this record does not waive transitive obligations.

## Breaking-version boundaries

- `iroh` before 1.0 is outside the stable endpoint, key, relay, and transport
  line selected here.
- `iroh-blobs` before 0.103 is from the pre-Iroh-1.0 integration line; its RPC
  and store APIs are not compatible by assumption.
- `iroh-docs` before 0.101 uses older Iroh dependencies and different redb
  migration behavior. Never test migration on the only copy of live data.
- Any component version outside the exact four-member bundle is incompatible,
  including apparently compatible patch or minor releases.
- Any sidecar RPC protocol other than 1 is incompatible. Refuse it before
  issuing blob, manifest, or synchronization operations.

These are hard startup/build boundaries. There is no best-effort mode and no
fallback to IPFS, local files, a different Iroh binary, or a different crate
version.

## Upgrade and rollback procedure

Every upgrade, including a patch-only change, gets a new bundle ID and repeats
the compatibility audit:

1. Review all four changelogs and identify API, wire, ticket, hash, discovery,
   and persistent-store changes.
2. Pin versions, crate checksums, tags, commits, Rust minimum version, features,
   licenses, and `Cargo.lock`.
3. Build reproducibly for every selected target and complete dependency,
   license, and provenance audits.
4. Run RPC contract, two-node transfer, ranged read, manifest conflict,
   restart, corruption, timeout, cancellation, and secret-redaction suites.
5. Run migration tests on a disposable copy of production-format data and test
   both mixed-version peers and interrupted migration.
6. Publish immutable draft archives, add exact digests and sizes, attest them,
   and capture native `--version` results for every target.
7. Canary the new bundle while retaining the previous binary and a
   pre-migration data snapshot.

Rollback is an atomic restoration of the retained binary. If an upgrade changed
storage, restore the pre-migration snapshot as well. Never open migrated live
data with an older binary unless the upgrade audit explicitly proved downgrade
safety. Failed canaries and withdrawn artifacts must update the machine record
to fail closed before broad rollout.

## Validation

Run the offline compatibility suite from the `external/ipfs_kit` repository:

```bash
python -m pytest -q tests/test_iroh_compatibility_record.py
```

The suite validates both schemas, the release record, the one-to-one target and
fixture mapping, the exact version line, cross-field component consistency, and
the fail-closed artifact promotion rules. Network access is not required.
