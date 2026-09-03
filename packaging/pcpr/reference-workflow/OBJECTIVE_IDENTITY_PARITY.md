# PCPR-082 Kit objective-identity-parity binding

These files bind the Kit-owned hermetic current root to the
Accelerate-owned objective-identity-parity demonstration. Kit does not
remint the pack CID, does not store the client as live durable bytes,
and does not decide semantic soundness.

- `cpython312/reference.objective-identity-parity.binding.json` binds the
  Kit current root to the Accelerate objective identity parity. Exact commit
  and tree are bound by the PCPR-082 receipt `current_tree_binding`.
- Durable reconstruction of the current root is from disk, not memory.
  Client replay is identity-preserving. Execution and client emission
  are owned by Accelerate. Cross-client identity parity remains
  PCPR-082.
- Missing a live Quack-fenced session emits operator-blocking task
  `pcpr-082-operator-live-cross-client-objective-identity-parity`.

Sealed validation PATH is exactly `/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin`.
