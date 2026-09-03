# PCPR-071 Kit recovery-and-idempotency binding

These files bind the Kit-owned hermetic current root to the
Accelerate-owned recovery and idempotency demonstration. Kit does not
remint the pack CID, does not store recovery as live durable bytes, and
does not decide semantic soundness.

- `cpython312/reference.recovery-and-idempotency.binding.json` binds the
  Kit current root to the Accelerate recovery. Exact commit and tree are
  bound by the PCPR-071 receipt `current_tree_binding`.
- Durable reconstruction of the current root is from disk, not memory.
  Recovery replay is identity-preserving. Execution and recovery are
  owned by Accelerate. The final receipt chain remains PCPR-072.
- Missing a live Quack-fenced session emits operator-blocking task
  `pcpr-071-operator-live-recovery-and-idempotency`.

Sealed validation PATH is exactly `/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin`.
