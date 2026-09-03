# PCPR-072 Kit final-receipt-chain binding

These files bind the Kit-owned hermetic current root to the
Accelerate-owned final proof-carrying receipt chain. Kit does not
remint the pack CID, does not store the chain as live durable bytes, and
does not decide semantic soundness.

- `cpython312/reference.final-receipt-chain.binding.json` binds the
  Kit current root to the Accelerate chain. Exact commit and tree are
  bound by the PCPR-072 receipt `current_tree_binding`.
- Durable reconstruction of the current root is from disk, not memory.
  Chain replay is identity-preserving. Execution and chain emission are
  owned by Accelerate. External-client demonstration remains PCPR-080.
- Missing a live Quack-fenced session emits operator-blocking task
  `pcpr-072-operator-live-final-receipt-chain`.

Sealed validation PATH is exactly `/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin`.
