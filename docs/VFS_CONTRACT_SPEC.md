# VFS Contract Specification

Status: Canonical
Runtime: ipfs_kit_py.mcp.servers.unified_mcp_server
Schema Version: 2

## Scope

This document defines the required request/response contract for VFS operations exposed by:
- `VFSCore` in `ipfs_kit_py/ipfs_fsspec.py`
- `vfs_*` helper functions in `ipfs_kit_py/ipfs_fsspec.py`
- MCP tool dispatch via `ipfs_kit_py/mcp/servers/unified_mcp_server.py`

## Global Response Contract

All VFS operations MUST return a JSON object containing:
- `success` (bool)
- `operation` (string) when surfaced through MCP adapters or integration wrappers

When `success` is false, responses SHOULD include:
- `error` (string)
- `code` (string, stable machine-readable failure key)

For content mutation operations, integration metadata MUST include:
- `schema_version` ("2")
- `operation_id` (string, `op-...`)
- `operation` (string)
- `path` (string)
- `backend` (string when available)
- `mount_point` (string when available)
- `timestamp` (ISO 8601 UTC)

Lineage fields SHOULD be present when available:
- `cid`
- `source_cid`
- `source_operation_id`

## Operation Contracts

### `vfs_mount`
Success shape includes:
- `success`, `mount_point`, `backend`, `mounted`

Failure examples:
- `code=mount_not_found` or backend validation errors from core methods

### `vfs_unmount`
Success shape includes:
- `success`, `unmounted`, `mount_point`

### `vfs_list_mounts`
Success shape includes:
- `success`, `count`, `mounts`

### `vfs_resolve_path`
Success shape includes:
- `success`, `resolved`, `local_path`, `mount_point`, `backend`, `resolved_path`

Failure shape includes:
- `success=false`, `resolved=false`, `error`

### `vfs_read`
Success shape includes:
- `success`, `path`, `content`, `cached`

### `vfs_write`
Success shape includes:
- `success`, `path`
- `integration.dataset`
- `integration.accelerate`
- `integration.metadata`

### `vfs_copy`, `vfs_move`, `vfs_mkdir`, `vfs_rmdir`, `vfs_ls`, `vfs_stat`
Must return `success` and operation-specific keys (`entries`, `exists`, etc.)

### `vfs_sync_to_ipfs`
Success shape includes:
- `success`, `path`, `cid`, `entry_count`
- `changed` (bool, when applicable)
- `transport_mode` (string)
- `integration`

### `vfs_sync_from_ipfs`
Success shape includes:
- `success`, `path`, `cid`
- `restored_count` (int)
- `skipped_count` (int)
- `policy` (`overwrite|skip|strict`)
- `integration`

Failure examples:
- `code=missing_sync_state`
- `code=snapshot_not_found`
- `code=sync_conflict` (strict conflict policy)

## Sync Durability Contract

`VFSCore` MUST persist sync state across process restart using atomic writes and safe-load behavior:
- persisted state map by path
- persisted snapshots by cid
- corruption-safe load fallback to empty state

## Transport Contract

`sync_to_ipfs` transport strategy is controlled by `IPFS_KIT_SYNC_TRANSPORT`:
- `auto` (default): best-effort real transport through datasets manager, fallback deterministic
- `deterministic`: deterministic-only snapshot path

## Conflict Policy Contract

`sync_from_ipfs` policy controlled by `IPFS_KIT_SYNC_CONFLICT_POLICY`:
- `overwrite`: local conflicts overwritten
- `skip`: conflicting files skipped
- `strict`: conflict causes explicit failure (`code=sync_conflict`)

## Runtime Policy

Production runtime MUST use `unified_mcp_server`. Legacy MCP servers are deprecated and blocked in production mode unless `IPFS_KIT_ALLOW_LEGACY_MCP=1` is explicitly set.
