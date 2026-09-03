# PCPR-062 Kit ContextPack persist and current root

These files are Kit-owned *declared* ContextPack storage for the
PCPR-061 DatasetsContextPack@1 identity. Kit verifies exact canonical
bytes, stores them, and publishes a generation-bearing current root
through hermetic compare-and-swap.

- `cpython312/reference.context-pack.bytes.json` is the exact
  DatasetsContextPack@1 identity payload stored by Kit.
- `cpython312/reference.context-pack.root.json` is the storage and
  current-root receipt. Exact commit and tree are bound by the
  PCPR-062 receipt `current_tree_binding`. `origin/main` is not the
  release identity.
- Hermetic persist and CAS are not live IPFS, not live Quack, and not
  live supervisor admission.
- Deterministic execution remains PCPR-063.
- Missing a live durable backend or Quack-fenced session emits
  operator-blocking task `pcpr-062-operator-live-context-pack-root`.

Sealed validation PATH is exactly `/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin`.
