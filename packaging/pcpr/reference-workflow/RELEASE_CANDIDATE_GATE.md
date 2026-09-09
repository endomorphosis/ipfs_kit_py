# PCPR-093 Kit release-candidate-gate binding

These files bind the Kit-owned hermetic current root to the
Accelerate-owned release-candidate gate. Kit does not remint the pack
CID, does not store the gate run as live durable bytes, and does not
decide semantic soundness.

- `cpython312/reference.release-candidate-gate.binding.json` binds the
  Kit current root to the Accelerate gate run. Exact commit and tree
  are bound by the PCPR-093 receipt `current_tree_binding`.
- Durable reconstruction of the current root is from disk, not memory.
  Gate-run replay is identity-preserving. Execution and gate emission
  are owned by Accelerate. Closed release remains PCPR-094.
- Missing a live Quack-fenced session emits operator-blocking task
  `pcpr-093-operator-live-release-candidate-gate`.

Sealed validation PATH is exactly `/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin`.
