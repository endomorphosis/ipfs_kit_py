# PCPR-091 Kit trusted-computing-base binding

These files bind the Kit-owned hermetic current root to the
Accelerate-owned trusted-computing-base inventory. Kit does not remint
the pack CID, does not store the inventory as live durable bytes, and
does not decide semantic soundness.

- `cpython312/reference.trusted-computing-base.binding.json` binds the
  Kit current root to the Accelerate TCB inventory. Exact commit and
  tree are bound by the PCPR-091 receipt `current_tree_binding`.
- Durable reconstruction of the current root is from disk, not memory.
  TCB-inventory replay is identity-preserving. Execution and inventory
  emission are owned by Accelerate. Audit package remains PCPR-092.
- Missing a live Quack-fenced session emits operator-blocking task
  `pcpr-091-operator-live-tcb-inventory`.

Sealed validation PATH is exactly `/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin`.
