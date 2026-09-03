# PCPR-067 Kit safe-reuse binding

These files bind the Kit-owned hermetic current root to the
Accelerate-owned eligible-reuse admission. Kit does not remint the pack
CID, does not store reuse as live durable bytes, and does not decide
semantic soundness.

- `cpython312/reference.safe-reuse.binding.json` binds the Kit current
  root to the Accelerate reuse admission. Exact commit and tree are
  bound by the PCPR-067 receipt `current_tree_binding`.
- Execution is owned by Accelerate. A relevant interface change remains
  PCPR-068.
- Missing a live Quack-fenced session emits operator-blocking task
  `pcpr-067-operator-live-safe-reuse`.

Sealed validation PATH is exactly `/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin`.
