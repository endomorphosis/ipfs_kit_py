# PCPR-061 Kit semantic ContextPack binding

These files bind Kit to the Datasets-owned DatasetsContextPack@1
identity. Kit does not remint that identity, does not import sibling
packages, and does not store ContextPack bytes in this task.

Durable storage and current-root CAS remain PCPR-062. This binding is
not a live Supervisor submission, not live materialization, not a
freeze, and not a closed PCPR release. Missing a live Quack-fenced
session is an explicit operator-blocking task.

Exact commit and tree are bound by the PCPR-061 receipt
`current_tree_binding`. `origin/main` is not the release identity.

Sealed validation PATH is exactly `/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin`.
