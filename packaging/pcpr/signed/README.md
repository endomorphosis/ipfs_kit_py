# PCPR-055 declared signed tags and artifacts

These files are the Kit *release* signed-tag policy and artifact
checksum manifest. They are not a live GPG/SSH git tag, not a cosign
signature, not a published wheel or sdist, and not a closed PCPR
release.

- `cpython312/release.tag-policy.json` is the canonical declared tag
  policy. The intended annotated tag name is `ipfs_kit_py-v0.3.0`.
  Exact commit and tree are bound by the PCPR-055 receipt
  `current_tree_binding` because nested admission rewrites HEAD.
  `origin/main` is not the release identity.
- `cpython312/release.checksums.json` and `cpython312/SHA256SUMS` checksum
  the committed PCPR-053 lock and PCPR-054 SBOM/provenance files. Wheel,
  sdist, container, and signature identities stay typed unavailable.
  Hashes and signatures are never invented.
- Named extras `libp2p` and `ipld-github` may carry source-checkout Git
  pins and are not this signed release.

Sealed validation PATH is exactly `/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin`.
