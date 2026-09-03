# PCPR-057 Kit branch and release gates binding

These files bind Kit to the Accelerate-owned declared branch-protection
policy and release gate for proof-carrying-platform-0.1.0. They do not
remint those identities, do not import sibling packages, and do not
apply GitHub settings.

This binding is not live GitHub branch protection, not live tag
protection, not a freeze, and not a closed PCPR release. Named extras
`libp2p` and `ipld-github` may carry source-checkout Git pins and are
not this gate. Missing repository-admin permission is an explicit
operator-blocking task. The governance gate is not complete.

- `cpython312/release.binding.json` pins branch-policy CID
  `baguqeeram3uegwfx6c4i76eyj5nuzlgsqw6yl5vb5c6drkuyacn5l77ksnna` and
  release-gate CID
  `baguqeerajahrusqwd33fqbuw46zgqcsw4xsuswdqq6td7c3nyddeeg5qofca`.
  Exact commit and tree are bound by the PCPR-057 receipt
  `current_tree_binding`. `origin/main` is not the release identity.

Sealed validation PATH is exactly `/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin`.
