# PCPR-066 Kit unrelated-state-change binding

These files bind the Kit-owned hermetic current root to the
Accelerate-owned unrelated documentation change. Kit does not remint the
pack CID, does not store the change as live durable bytes, and does not
decide semantic soundness.

- `cpython312/reference.unrelated-state-change.binding.json` binds the
  Kit current root to the Accelerate change. Exact commit and tree are
  bound by the PCPR-066 receipt `current_tree_binding`.
- Execution is owned by Accelerate. Eligible reuse remains PCPR-067.
- Missing a live Quack-fenced session emits operator-blocking task
  `pcpr-066-operator-live-unrelated-state-change`.

Sealed validation PATH is exactly `/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin`.
