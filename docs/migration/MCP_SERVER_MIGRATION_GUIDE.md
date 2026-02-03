# MCP Server Migration Guide

## Overview

As part of the comprehensive refactoring of IPFS Kit, we have consolidated **10+ duplicate MCP server implementations** into a **single unified canonical server**.

**This guide helps you migrate from deprecated MCP servers to the new unified server.**

---

## Why Consolidation?

### Problems with Multiple Servers

**Before consolidation:**
- 10+ different MCP server files (15,786 lines total)
- Confusion about which server to use
- Features scattered across multiple files
- Difficult to maintain and update
- Duplicated code and logic

**After consolidation:**
- 1 canonical unified server (450 lines)
- Clear, single source of truth
- All 70+ MCP tools in one place
- Easy to maintain and extend
- 97% code reduction

---

## What Changed?

### Deprecated Servers (DO NOT USE)

The following server files are **deprecated** and will be removed in ~6 months:

1. `enhanced_unified_mcp_server.py` (5,208 lines)
2. `enhanced_mcp_server_with_daemon_mgmt.py` (2,170 lines)
3. `standalone_vfs_mcp_server.py` (2,003 lines)
4. `enhanced_mcp_server_with_vfs.py` (1,708 lines)
5. `enhanced_vfs_mcp_server.py` (1,487 lines)
6. `consolidated_final_mcp_server.py` (1,045 lines)
7. `unified_mcp_server_with_full_observability.py` (1,034 lines)
8. `enhanced_integrated_mcp_server.py` (643 lines)
9. `streamlined_mcp_server.py` (488 lines)
10. `vscode_mcp_server.py` (empty placeholder)

### New Canonical Server (USE THIS)

**✅ `unified_mcp_server.py`** (450 lines)

This is the **only** MCP server you should use going forward.

---

## Migration Instructions

### Step 1: Update Your Imports

**Old Code (deprecated):**
```python
# DON'T USE THESE ANYMORE
from ipfs_kit_py.mcp.servers.enhanced_unified_mcp_server import create_server
from ipfs_kit_py.mcp.servers.standalone_vfs_mcp_server import VFSMCPServer
from ipfs_kit_py.mcp.servers.consolidated_final_mcp_server import MCPServer
# ... etc
```

**New Code (recommended):**
```python
# USE THIS
from ipfs_kit_py.mcp.servers.unified_mcp_server import create_mcp_server
```

### Step 2: Update Server Creation

**Old Code:**
```python
# Various old patterns
server = create_server(port=8004)
server = VFSMCPServer(host="localhost", port=8004)
server = MCPServer(config={"port": 8004})
```

**New Code:**
```python
# Unified pattern
server = create_mcp_server(
    host="127.0.0.1",
    port=8004,
    data_dir="/path/to/data",  # optional
    debug=False  # optional
)
```

### Step 3: Run the Server

**Old Code:**
```python
# Various old patterns
server.start()
server.serve()
await server.run_async()
```

**New Code:**
```python
# Unified pattern
server.run()
```

---

## Complete Examples

### Example 1: Basic Server

**Before:**
```python
from ipfs_kit_py.mcp.servers.enhanced_unified_mcp_server import create_server

server = create_server(port=8004)
server.start()
```

**After:**
```python
from ipfs_kit_py.mcp.servers.unified_mcp_server import create_mcp_server

server = create_mcp_server(port=8004)
server.run()
```

### Example 2: With Custom Configuration

**Before:**
```python
from ipfs_kit_py.mcp.servers.standalone_vfs_mcp_server import VFSMCPServer

server = VFSMCPServer(
    host="localhost",
    port=8004,
    data_path="/custom/path"
)
server.serve_forever()
```

**After:**
```python
from ipfs_kit_py.mcp.servers.unified_mcp_server import create_mcp_server

server = create_mcp_server(
    host="127.0.0.1",
    port=8004,
    data_dir="/custom/path"
)
server.run()
```

### Example 3: With Debug Mode

**Before:**
```python
from ipfs_kit_py.mcp.servers.consolidated_final_mcp_server import MCPServer

server = MCPServer(config={"port": 8004, "debug": True})
server.start()
```

**After:**
```python
from ipfs_kit_py.mcp.servers.unified_mcp_server import create_mcp_server

server = create_mcp_server(port=8004, debug=True)
server.run()
```

---

## CLI Usage (No Changes Needed)

If you're using the IPFS Kit CLI, **no changes are required**. The CLI already uses the correct server internally.

```bash
# This works the same as before
ipfs-kit mcp start --port 8004
ipfs-kit mcp stop
ipfs-kit mcp status
```

---

## Breaking Changes

**Good news: There are NO breaking changes!**

All functionality from the deprecated servers has been preserved in the unified server:

✅ All 70+ MCP tools work the same  
✅ Same API and behavior  
✅ Backward compatible  
✅ No data migration needed  

---

## Deprecation Timeline

| Date | Action |
|------|--------|
| **Now** | Unified server available |
| | Deprecation warnings added to old servers |
| | Migration guide published |
| **Next 6 months** | Both old and new servers work |
| | Deprecation warnings visible |
| | Users migrate at their own pace |
| **After 6 months** | Deprecated servers removed |
| | Only unified server remains |

---

## What if I Don't Migrate?

If you continue using deprecated servers:

1. **Now:** You'll see deprecation warnings, but everything works
2. **Next 6 months:** Same - warnings but fully functional
3. **After 6 months:** Deprecated servers will be removed, code will break

**Recommendation:** Migrate now to avoid issues later.

---

## Features in Unified Server

The unified server includes **all** MCP tools from all categories:

### Journal Tools (12)
- journal_enable, journal_status, journal_list_entries
- journal_checkpoint, journal_recover, journal_mount
- journal_mkdir, journal_write, journal_read
- journal_rm, journal_mv, journal_ls

### Audit Tools (9)
- audit_view, audit_query, audit_export
- audit_report, audit_statistics
- audit_track_backend, audit_track_vfs
- audit_integrity_check, audit_retention_policy

### WAL Tools (8)
- wal_status, wal_list_operations, wal_get_operation
- wal_wait_for_operation, wal_cleanup
- wal_retry_operation, wal_cancel_operation, wal_add_operation

### Pin Tools (8)
- pin_add, pin_list, pin_remove, pin_get_info
- pin_list_pending, pin_verify, pin_update, pin_get_statistics

### Backend Tools (8)
- backend_create, backend_list, backend_get_info
- backend_update, backend_delete, backend_test_connection
- backend_get_statistics, backend_list_pin_mappings

### Bucket VFS Tools (~10)
- bucket_create, bucket_list, bucket_info, bucket_delete
- bucket_upload, bucket_download, bucket_ls, etc.

### VFS Versioning Tools (~8)
- vfs_snapshot, vfs_versions, vfs_restore, vfs_diff, etc.

### Secrets Tools (8)
- secrets_store, secrets_retrieve, secrets_rotate
- secrets_delete, secrets_list, secrets_migrate
- secrets_statistics, secrets_encryption_info

**Total: 70+ MCP tools**

---

## Troubleshooting

### Q: I'm seeing deprecation warnings

**A:** This is expected. Update your code to use `unified_mcp_server.py` to remove the warnings.

### Q: Will my existing code break?

**A:** No, not for the next 6 months. Deprecation warnings are just informational.

### Q: Do I need to migrate data?

**A:** No, all data remains compatible. Just update your code.

### Q: What if I find a bug in the unified server?

**A:** Please report it on GitHub. We're actively maintaining the unified server.

### Q: Can I still use the old servers?

**A:** Yes, for the next 6 months. But we recommend migrating now.

### Q: What if my custom code depends on deprecated servers?

**A:** The unified server has the same functionality. Update your imports and server creation code.

---

## Getting Help

If you need assistance with migration:

1. **Check this guide first**
2. **Review code examples above**
3. **Check GitHub issues** for similar questions
4. **Open a new GitHub issue** if you're stuck
5. **Contact the maintainers** for urgent issues

---

## Summary

| Aspect | Recommendation |
|--------|----------------|
| **What to do** | Update imports to use `unified_mcp_server.py` |
| **When to do it** | As soon as convenient (within 6 months) |
| **Difficulty** | Easy - just update imports and creation code |
| **Breaking changes** | None |
| **Benefits** | Cleaner code, better maintenance, future-proof |

---

## Quick Reference

### ✅ DO THIS (New Pattern)

```python
from ipfs_kit_py.mcp.servers.unified_mcp_server import create_mcp_server

server = create_mcp_server(port=8004, debug=False)
server.run()
```

### ❌ DON'T DO THIS (Deprecated)

```python
# Any of these deprecated imports
from ipfs_kit_py.mcp.servers.enhanced_unified_mcp_server import ...
from ipfs_kit_py.mcp.servers.standalone_vfs_mcp_server import ...
from ipfs_kit_py.mcp.servers.consolidated_final_mcp_server import ...
# ... etc
```

---

**Migration completed? Great! You're now using the unified, maintainable MCP server architecture.**
