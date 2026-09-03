# PCPR-064 Kit bounded PatchPlan binding

These files bind the Kit-owned hermetic current root to the
Accelerate-owned bounded PatchPlan. Kit does not remint the pack CID,
does not apply the patch as live storage, and does not decide semantic
soundness.

- `cpython312/reference.bounded-patch.binding.json` binds the Kit
  current root to the Accelerate PatchPlan. Exact commit and tree are
  bound by the PCPR-064 receipt `current_tree_binding`.
- Execution is owned by Accelerate. Selected tests remain PCPR-065.
- Missing a live Quack-fenced session emits operator-blocking task
  `pcpr-064-operator-live-bounded-patch`.

Sealed validation PATH is exactly `/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin`.
