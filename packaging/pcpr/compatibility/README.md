# PCPR-056 Kit portfolio compatibility lock binding

These files bind Kit to the one declared proof-carrying-platform-0.1.0
portfolio compatibility lock owned by Accelerate. They do not remint
that lock, do not import sibling packages, and do not re-encode
identities.

This binding is not a live signed manifest, not a freeze, not a
published wheel or sdist, and not a closed PCPR release. Named extras
`libp2p` and `ipld-github` may carry source-checkout Git pins and are
not this lock.

- `cpython312/release.binding.json` pins lock CID
  `baguqeerawsekbbbt5ccctjt4tydzeahfkahsatb6q5x7k6cy4inrii5lhqmq`.
  Exact commit and tree are bound by the PCPR-056 receipt
  `current_tree_binding`. `origin/main` is not the release identity.

Sealed validation PATH is exactly `/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin`.
