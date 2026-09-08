# PCPR-083 Kit authority-bypass binding

These files bind the Kit-owned hermetic current root to the
Accelerate-owned authority-bypass proof. Kit does not remint the pack
CID, does not store the proof as live durable bytes, and does not
decide semantic soundness.

- `cpython312/reference.authority-bypass.binding.json` binds the Kit
  current root to the Accelerate authority-bypass proof. Exact commit
  and tree are bound by the PCPR-083 receipt `current_tree_binding`.
- Durable reconstruction of the current root is from disk, not memory.
  Bypass replay is identity-preserving. Execution and client emission
  are owned by Accelerate. Threat-model preparation remains PCPR-090.
- Missing a live Quack-fenced session emits operator-blocking task
  `pcpr-083-operator-live-external-client-authority-bypass`.

Sealed validation PATH is exactly `/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin`.
