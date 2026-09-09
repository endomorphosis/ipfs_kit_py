# PCPR-092 Kit security and correctness audit-package binding

These files bind the Kit-owned hermetic current root to the
Accelerate-owned security and correctness audit package. Kit does not
remint the pack CID, does not store the package as live durable bytes,
and does not decide semantic soundness.

- `cpython312/reference.security-and-correctness-audit-package.binding.json`
  binds the Kit current root to the Accelerate audit package. Exact
  commit and tree are bound by the PCPR-092 receipt
  `current_tree_binding`.
- Durable reconstruction of the current root is from disk, not memory.
  Audit-package replay is identity-preserving. Execution and package
  emission are owned by Accelerate. Status is external_audit_ready,
  never externally_audited. Closed release remains PCPR-093/094.
- Missing a live Quack-fenced session emits operator-blocking task
  `pcpr-092-operator-live-audit-package`.

Sealed validation PATH is exactly `/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin`.
