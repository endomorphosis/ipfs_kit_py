# PCPR-070 Kit state-owner-restart binding

These files bind the Kit-owned hermetic current root to the
Accelerate-owned authoritative state-owner restart. Kit does not remint
the pack CID, does not store the restart as live durable bytes, and does
not decide semantic soundness.

- `cpython312/reference.state-owner-restart.binding.json` binds the Kit
  current root to the Accelerate restart. Exact commit and tree are
  bound by the PCPR-070 receipt `current_tree_binding`.
- Durable reconstruction of the current root is from disk, not memory.
  Execution and owner restart are owned by Accelerate. Recovery remains
  PCPR-071.
- Missing a live Quack-fenced session emits operator-blocking task
  `pcpr-070-operator-live-authoritative-state-owner-restart`.

Sealed validation PATH is exactly `/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin`.
