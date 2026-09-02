# PCPR-054 declared-release-profile SBOMs

These files are declared SPDX-2.3 SBOMs of the Kit *release* profile.
They list the root package and the PCPR-053 declared PEP 508 direct
requires. They are not a live Syft/CycloneDX/Trivy scan, not a hashed
transitive graph, not a signed SLSA attestation, and not a closed
PCPR release.

- `cpython312/release.sbom.json` is the canonical declared SBOM.
- Hash, license-concluded, and transitive identities stay typed
  unavailable. Hashes are never invented. `filesAnalyzed` is false.
- Named extras `libp2p` and `ipld-github` may carry source-checkout
  Git pins and are not this SBOM.

Sealed validation PATH is exactly `/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin`.
