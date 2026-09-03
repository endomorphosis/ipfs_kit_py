# PCPR-069 Kit stale-rejection binding

These files bind the Kit-owned hermetic current root to the
Accelerate-owned stale rejection and PlanDelta. Kit does not remint the
pack CID, does not store the PlanDelta as live durable bytes, and does
not decide semantic soundness.

- `cpython312/reference.stale-rejection.binding.json` binds the Kit
  current root to the Accelerate stale rejection. Exact commit and tree
  are bound by the PCPR-069 receipt `current_tree_binding`.
- Execution is owned by Accelerate. Restart recovery remains PCPR-070.
- Missing a live Quack-fenced session emits operator-blocking task
  `pcpr-069-operator-live-stale-rejection-and-plan-delta`.

Sealed validation PATH is exactly `/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin`.
