# Release Checklist: Submodule Scope Hygiene

Use this checklist before publishing or merging release branches for submodule-scoped VFS integration work.

## Scope Hygiene

- [ ] Verify no unrelated dirty files are present in worktree.
- [ ] Verify changed paths are limited to intended submodule scope.
- [ ] Verify docs/spec updates are included for contract changes.

## Runtime Policy

- [ ] Confirm production runtime path references unified MCP server only.
- [ ] Confirm legacy server production guard is active.

## Test Evidence

Attach command output snapshots for:
- [ ] `pytest external/ipfs_kit/tests/test_vfs_contract_hardening.py -q`
- [ ] `pytest external/ipfs_kit/tests/test_datasets_metadata_index_contract.py -q`
- [ ] `pytest external/ipfs_kit/tests/test_mcp_vfs_adapter_contract.py -q`
- [ ] `pytest external/ipfs_kit/tests/test_vfs_jsonrpc.py external/ipfs_kit/tests/test_vfs_mcp_tools.py -q`

## Metadata and Sync Contracts

- [ ] Verify metadata envelope includes schema version and lineage fields.
- [ ] Verify sync durability behavior across restart is covered by tests.
- [ ] Verify conflict policy behavior (`overwrite|skip|strict`) is covered.

## Sign-off

- [ ] Reviewer sign-off for contract compatibility
- [ ] Reviewer sign-off for CI lane green state
