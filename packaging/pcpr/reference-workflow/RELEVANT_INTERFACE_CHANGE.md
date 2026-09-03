# PCPR-068 Kit relevant-interface-change binding

These files bind the Kit-owned hermetic current root to the
Accelerate-owned relevant interface change. Kit does not remint the
pack CID, does not store the change as live durable bytes, and does not
decide semantic soundness.

- `cpython312/reference.relevant-interface-change.binding.json` binds the
  Kit current root to the Accelerate change. Exact commit and tree are
  bound by the PCPR-068 receipt `current_tree_binding`.
- Execution is owned by Accelerate. Stale rejection remains PCPR-069.
- Missing a live Quack-fenced session emits operator-blocking task
  `pcpr-068-operator-live-relevant-interface-change`.

Sealed validation PATH is exactly `/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin`.
