# PCPR-096 Kit next-bounded-pilot binding

These files bind the Kit-owned hermetic current root to the
Accelerate-owned next-bounded-pilot recommendation. Kit does not remint the
pack CID, does not store the recommendation as live durable bytes, and does
not decide semantic soundness.

- `cpython312/reference.next-bounded-pilot.binding.json` binds the
  Kit current root to the Accelerate next-bounded-pilot recommendation.
  Exact commit and tree are bound by the PCPR-096 receipt `current_tree_binding`.
- Durable reconstruction of the current root is from disk, not memory.
  Recommendation replay is identity-preserving. Execution and recommendation
  emission are owned by Accelerate. The recommended pilot is synthetic, not
  created, and does not expand PCPR.
- Missing a live Quack-fenced session emits operator-blocking task
  `pcpr-096-operator-live-next-bounded-pilot`.

Sealed validation PATH is exactly `/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin`.
