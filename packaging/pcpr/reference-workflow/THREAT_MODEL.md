# PCPR-090 Kit threat-model binding

These files bind the Kit-owned hermetic current root to the
Accelerate-owned threat model. Kit does not remint the pack CID, does
not store the model as live durable bytes, and does not decide semantic
soundness.

- `cpython312/reference.threat-model.binding.json` binds the Kit current
  root to the Accelerate threat model. Exact commit and tree are bound
  by the PCPR-090 receipt `current_tree_binding`.
- Durable reconstruction of the current root is from disk, not memory.
  Threat-model replay is identity-preserving. Execution and model
  emission are owned by Accelerate. Trusted-computing-base inventory
  remains PCPR-091.
- Missing a live Quack-fenced session emits operator-blocking task
  `pcpr-090-operator-live-threat-model`.

Sealed validation PATH is exactly `/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin`.
