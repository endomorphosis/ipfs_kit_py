# PCPR-095 Kit residual-gap-report binding

These files bind the Kit-owned hermetic current root to the
Accelerate-owned residual-gap report receipt. Kit does not remint the pack
CID, does not store the residual-gap report as live durable bytes, and does not
decide semantic soundness.

- `cpython312/reference.residual-gap-report.binding.json` binds the
  Kit current root to the Accelerate residual-gap report. Exact commit and tree
  are bound by the PCPR-095 receipt `current_tree_binding`.
- Durable reconstruction of the current root is from disk, not memory.
  Gate-run replay is identity-preserving. Execution and gate emission
  are owned by Accelerate. Next bounded-pilot recommendation remains PCPR-096.
- Missing a live Quack-fenced session emits operator-blocking task
  `pcpr-095-operator-live-residual-gap-report`.

Sealed validation PATH is exactly `/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin`.
