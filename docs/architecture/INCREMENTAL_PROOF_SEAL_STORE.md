# Incremental Proof Seal Store

Kit is the storage authority for IncrementalProofSealer artifacts. It carries
bytes, CIDs, and opaque canonical records. It does not decide whether a proof
is valid, whether a unit may be reused, or whether an external prover succeeded.

Evidence subsets: `ips/kit-public-adapter@1`, `ips/kit-migration@1`.

## Public adapter

The `ipfs_kit_py.proof_seal_store` package exports:

- closed contracts (`ArtifactKind`, `ProofSealStore`, pointer/WAL records);
- lazy implementation adapters (local store, optional IPFS transport, cache
  index, forest, current-seal CAS, WAL, recovery).

Cold import is hermetic: no daemon, no network, no `~/.ipfs`, no default
user-state root, and no datasets import.

Construction of every durable surface requires an explicit store root.

## What kit stores

Closed public kinds: `proof_object`, `proof_receipt`, `verification_key`,
`proof_manifest`, `merkle_node`, `checkpoint_seal`, `delta_seal`,
`tombstone`, `invalidation_record`.

Public APIs reject proving keys and witness material. Cache candidates always
require fresh verification. The current-seal pointer is a separate
repository/branch CAS role and cannot collapse into a candidate.

## Recovery and durability

WAL phases follow the seven-phase seal transition. Recovery is deterministic
and idempotent. Ambiguous prover outcomes never become success. A stale parent
after pre-CAS persistence rejects publication. A committed pointer is not lost
because a later writer crashed.

## Legacy certificate transport

`proof_certificate_store` remains an integrity transport for exact-byte
blobs. `stage_legacy_certificate_blob` can persist those bytes under a
rehashed CID. Staging is not admission. Accelerate must cryptographically
verify a staged blob before it may enter the candidate index. Kit never
upgrades a staged blob into a current seal.

## Nonclaims

This document does **not** claim:

- that kit proves repository correctness or test execution;
- that kit decides reuse, invalidation, or evidence class;
- that a cache hit is an accepted proof;
- that process output, logs, or a present CID constitute a proof;
- that optional IPFS transport is required for unit tests or ordinary import;
- that proving-key or witness bytes are stored or surfaced on public paths.

Datasets remains the semantic authority. Accelerate remains the execution,
admission, and reuse authority.
