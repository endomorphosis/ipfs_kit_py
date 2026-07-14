# Iroh filesystem backend release notes

## Disabled preview — 2026-07-13

This release includes the versioned Iroh filesystem, fsspec adapter, named
backend/VFS integration, installer and managed service lifecycle, manifest and
blob integrity, synchronization, garbage collection, observability, operator
commands, interoperability harness, and packaging gates.

Iroh is **disabled by default** with `iroh.enabled=false`. Existing IPFS Kit
imports and non-Iroh backends continue to work without installing an Iroh
sidecar. Enabling Iroh is currently experimental and requires an explicit
operator configuration change; it is not yet a supported production storage
backend.

### Compatibility

- Python 3.12 and 3.13 are covered by the release matrix.
- The frozen bundle is `iroh-1.0.2-ipfs-kit.1` with RPC protocol 1.
- Iroh BLAKE3 hashes remain distinct from IPFS CIDs.
- Unknown component bundles or RPC protocol versions fail closed.
- Base and built distributions do not bundle or implicitly install a sidecar.

### Operator impact

Before any opt-in, read the [readiness report](release-readiness.md), rehearse a
verified export and restore, retain a pre-migration snapshot, and assign a
storage on-call owner. Rollback begins by disabling Iroh and is
non-destructive: manifests, blobs, identity backups, and state are retained and
verified before traffic returns.

### Known limitations

- The selected sidecar remains source-pinned; installable attested platform
  artifacts are not published in the compatibility record.
- Checked-in real-node interoperability evidence has status `not_run`.
- Experimental and canary SLO observation windows have not been completed.
- These limitations block canary and supported promotion but do not block a
  release in which Iroh remains disabled.

### Promotion and support

Promotion proceeds manually through experimental, canary (maximum 5%), and
supported stages. It requires new test/benchmark/security receipts, real-node
and artifact provenance evidence, rollback proof, SLO history, and explicit
release-manager/storage-on-call sign-off. Report integrity, data loss,
credential exposure, or SLO incidents through the IPFS Kit issue tracker with
the `iroh` label and attach only redacted receipts.

