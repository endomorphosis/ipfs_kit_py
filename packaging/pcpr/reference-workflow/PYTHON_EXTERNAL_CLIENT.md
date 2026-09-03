# PCPR-080 Kit Python-external-client binding

These files bind the Kit-owned hermetic current root to the
Accelerate-owned Python external-client demonstration. Kit does not
remint the pack CID, does not store the client as live durable bytes,
and does not decide semantic soundness.

- `cpython312/reference.python-external-client.binding.json` binds the
  Kit current root to the Accelerate Python client. Exact commit and
  tree are bound by the PCPR-080 receipt `current_tree_binding`.
- Durable reconstruction of the current root is from disk, not memory.
  Client replay is identity-preserving. Execution and client emission
  are owned by Accelerate. Generic MCP-client demonstration remains
  PCPR-081.
- Missing a live Quack-fenced session emits operator-blocking task
  `pcpr-080-operator-live-python-external-client`.

Sealed validation PATH is exactly `/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin`.
