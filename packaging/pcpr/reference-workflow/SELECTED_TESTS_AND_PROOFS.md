# PCPR-065 Kit selected-tests-and-proofs binding

These files bind the Kit-owned hermetic current root to the
Accelerate-owned selected-tests-and-proofs run. Kit does not remint the
pack CID, does not store the run as live durable bytes, and does not
decide semantic soundness.

- `cpython312/reference.selected-tests-and-proofs.binding.json` binds
  the Kit current root to the Accelerate run. Exact commit and tree are
  bound by the PCPR-065 receipt `current_tree_binding`.
- Execution is owned by Accelerate. Unrelated-state-change reuse remains
  PCPR-066.
- Missing a live Quack-fenced session emits operator-blocking task
  `pcpr-065-operator-live-selected-tests-and-proofs`.

Sealed validation PATH is exactly `/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin`.
