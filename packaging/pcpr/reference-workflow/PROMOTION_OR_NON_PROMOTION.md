# PCPR-094 Kit promotion-or-non-promotion binding

These files bind the Kit-owned hermetic current root to the
Accelerate-owned promotion or non-promotion receipt. Kit does not remint the pack
CID, does not store the promotion decision as live durable bytes, and does not
decide semantic soundness.

- `cpython312/reference.promotion-or-non-promotion.binding.json` binds the
  Kit current root to the Accelerate promotion decision. Exact commit and tree
  are bound by the PCPR-094 receipt `current_tree_binding`.
- Durable reconstruction of the current root is from disk, not memory.
  Gate-run replay is identity-preserving. Execution and gate emission
  are owned by Accelerate. Closed release remains PCPR-094.
- Missing a live Quack-fenced session emits operator-blocking task
  `pcpr-094-operator-live-promotion`.

Sealed validation PATH is exactly `/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin`.
