# PCPR-081 Kit generic-MCP-client binding

These files bind the Kit-owned hermetic current root to the
Accelerate-owned generic MCP-client demonstration. Kit does not
remint the pack CID, does not store the client as live durable bytes,
and does not decide semantic soundness.

- `cpython312/reference.generic-mcp-client.binding.json` binds the
  Kit current root to the Accelerate generic MCP client. Exact commit
  and tree are bound by the PCPR-081 receipt `current_tree_binding`.
- Durable reconstruction of the current root is from disk, not memory.
  Client replay is identity-preserving. Execution and client emission
  are owned by Accelerate. Cross-client identity parity remains
  PCPR-082.
- Missing a live Quack-fenced session emits operator-blocking task
  `pcpr-081-operator-live-generic-mcp-client`.

Sealed validation PATH is exactly `/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin`.
