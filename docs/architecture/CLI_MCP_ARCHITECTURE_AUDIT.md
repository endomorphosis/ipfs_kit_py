# CLI and MCP Tools Architecture Audit

## Executive Summary

This document provides a comprehensive audit of all CLI tools and MCP server tools in ipfs_kit_py, evaluating compliance with the proper architectural pattern:

```
Core Module (ipfs_kit_py/)
    ↓
CLI Integration (module_cli.py or cli.py subcommand)
    ↓                              ↓
ipfs-kit command              MCP Integration (ipfs_kit_py/mcp/servers/)
                                   ↓
                              Shim (mcp/)
                                   ↓
                              MCP Server → JS SDK → Dashboard
```

## Inventory of Components

### ✅ Compliant Components (Following Pattern)

#### 1. Secrets Management
- **Core Module**: `ipfs_kit_py/enhanced_secrets_manager.py`, `aes_encryption.py`
- **CLI**: None (functionality through MCP only)
- **MCP Tools**: `ipfs_kit_py/mcp/servers/secrets_mcp_tools.py`
- **MCP Shim**: `mcp/secrets_mcp_tools.py`
- **Status**: ✅ **COMPLIANT**
- **Notes**: Properly follows architecture pattern

#### 2. Bucket VFS
- **Core Module**: `ipfs_kit_py/bucket_vfs_manager.py`
- **CLI**: `ipfs_kit_py/bucket_vfs_cli.py` (standalone, needs integration)
- **MCP Tools**: `ipfs_kit_py/mcp/servers/bucket_vfs_mcp_tools.py`
- **MCP Shim**: `mcp/bucket_vfs_mcp_tools.py`
- **Status**: ⚠️ **PARTIAL** - CLI exists but not integrated into main `ipfs-kit` command
- **Action Needed**: Integrate CLI into main dispatcher

#### 3. VFS Versioning
- **Core Module**: `ipfs_kit_py/vfs_version_tracker.py`
- **CLI**: `ipfs_kit_py/vfs_version_cli.py` (standalone, needs integration)
- **MCP Tools**: `ipfs_kit_py/mcp/servers/vfs_version_mcp_tools.py`
- **MCP Shim**: `mcp/vfs_version_mcp_tools.py`
- **Status**: ⚠️ **PARTIAL** - CLI exists but not integrated
- **Action Needed**: Integrate CLI into main dispatcher

---

### ⚠️ Components Needing Attention

#### 4. WAL (Write-Ahead Log)
- **Core Module**: `ipfs_kit_py/storage_wal.py`, `enhanced_wal_durability.py`
- **CLI**: 
  - `ipfs_kit_py/wal_cli.py` (standalone)
  - `ipfs_kit_py/wal_cli_integration.py` (integration helper)
- **MCP Tools**: ❌ **MISSING**
- **MCP Shim**: ❌ **MISSING**
- **Status**: ❌ **NON-COMPLIANT** - Has CLI but no MCP tools
- **Action Needed**: 
  1. Create `ipfs_kit_py/mcp/servers/wal_mcp_tools.py`
  2. Create `mcp/wal_mcp_tools.py` shim
  3. Integrate CLI into main dispatcher

#### 5. Pin Management
- **Core Module**: `ipfs_kit_py/enhanced_pin_api.py`, `pin_manager.py`
- **CLI**: 
  - `ipfs_kit_py/simple_pin_cli.py` (standalone)
  - `ipfs_kit_py/cli/enhanced_pin_cli.py` (subdirectory)
- **MCP Tools**: ❌ **MISSING** (some pin tools may exist in other servers)
- **MCP Shim**: ❌ **MISSING**
- **Status**: ❌ **NON-COMPLIANT**
- **Action Needed**:
  1. Create `ipfs_kit_py/mcp/servers/pin_mcp_tools.py`
  2. Create `mcp/pin_mcp_tools.py` shim
  3. Integrate CLI into main dispatcher
  4. Consolidate pin CLI files

#### 6. Backend Management
- **Core Module**: `ipfs_kit_py/backend_manager.py`, `enhanced_backend_manager.py`
- **CLI**: `ipfs_kit_py/backend_cli.py` (standalone)
- **MCP Tools**: ❌ **MISSING** (backend tools exist in MCP ipfs_kit/mcp_tools/)
- **MCP Shim**: ❌ **MISSING**
- **Status**: ❌ **NON-COMPLIANT**
- **Action Needed**:
  1. Review existing backend tools in MCP
  2. Create proper `ipfs_kit_py/mcp/servers/backend_mcp_tools.py`
  3. Create `mcp/backend_mcp_tools.py` shim
  4. Integrate CLI into main dispatcher

#### 7. Daemon Management
- **Core Module**: `ipfs_kit_py/enhanced_daemon_manager.py`, daemon managers
- **CLI**: 
  - `ipfs_kit_py/daemon_cli.py` (standalone)
  - Partial in main `cli.py` (mcp start/stop uses daemon)
- **MCP Tools**: Partial (daemon management exists in MCP servers)
- **MCP Shim**: ❌ **MISSING**
- **Status**: ⚠️ **PARTIAL**
- **Action Needed**:
  1. Extract daemon tools to proper location
  2. Create `ipfs_kit_py/mcp/servers/daemon_mcp_tools.py`
  3. Create `mcp/daemon_mcp_tools.py` shim
  4. Integrate standalone daemon CLI

#### 8. Filesystem Journal
- **Core Module**: `ipfs_kit_py/filesystem_journal.py`, `fs_journal_*`
- **CLI**: `ipfs_kit_py/fs_journal_cli.py` (standalone)
- **MCP Tools**: ❌ **MISSING**
- **MCP Shim**: ❌ **MISSING**
- **Status**: ❌ **NON-COMPLIANT**
- **Action Needed**:
  1. Create `ipfs_kit_py/mcp/servers/fs_journal_mcp_tools.py`
  2. Create `mcp/fs_journal_mcp_tools.py` shim
  3. Integrate CLI into main dispatcher

#### 9. WebRTC
- **Core Module**: `ipfs_kit_py/webrtc_*.py` (multiple files)
- **CLI**: `ipfs_kit_py/webrtc_cli.py` (standalone)
- **MCP Tools**: ❌ **MISSING**
- **MCP Shim**: ❌ **MISSING**
- **Status**: ❌ **NON-COMPLIANT**
- **Action Needed**:
  1. Create `ipfs_kit_py/mcp/servers/webrtc_mcp_tools.py`
  2. Create `mcp/webrtc_mcp_tools.py` shim
  3. Integrate CLI into main dispatcher

#### 10. Filecoin Integration
- **Core Module**: `ipfs_kit_py/filecoin_storage.py`, `advanced_filecoin_client.py`
- **CLI**: `ipfs_kit_py/filecoin_pin_cli.py` (standalone)
- **MCP Tools**: ❌ **MISSING**
- **MCP Shim**: ❌ **MISSING**
- **Status**: ❌ **NON-COMPLIANT**
- **Action Needed**:
  1. Create `ipfs_kit_py/mcp/servers/filecoin_mcp_tools.py`
  2. Create `mcp/filecoin_mcp_tools.py` shim
  3. Integrate CLI into main dispatcher

#### 11. State Management
- **Core Module**: `ipfs_kit_py/cluster_state.py`, state management modules
- **CLI**: 
  - `ipfs_kit_py/state_cli.py` (standalone)
  - `ipfs_kit_py/state_cli_lightweight.py` (alternative)
- **MCP Tools**: ❌ **MISSING**
- **MCP Shim**: ❌ **MISSING**
- **Status**: ❌ **NON-COMPLIANT**
- **Action Needed**:
  1. Create `ipfs_kit_py/mcp/servers/state_mcp_tools.py`
  2. Create `mcp/state_mcp_tools.py` shim
  3. Integrate CLI into main dispatcher
  4. Consolidate state CLI files

#### 12. P2P Workflows
- **Core Module**: `ipfs_kit_py/p2p_workflow_coordinator.py`
- **CLI**: `ipfs_kit_py/cli/p2p_workflow_cli.py` (in subdirectory)
- **MCP Tools**: ❌ **MISSING**
- **MCP Shim**: ❌ **MISSING**
- **Status**: ❌ **NON-COMPLIANT**
- **Action Needed**:
  1. Create `ipfs_kit_py/mcp/servers/p2p_workflow_mcp_tools.py`
  2. Create `mcp/p2p_workflow_mcp_tools.py` shim
  3. Integrate CLI into main dispatcher

#### 13. WAL Telemetry
- **Core Module**: `ipfs_kit_py/wal_telemetry*.py` (multiple files)
- **CLI**: `ipfs_kit_py/wal_telemetry_cli.py` (standalone)
- **MCP Tools**: ❌ **MISSING**
- **MCP Shim**: ❌ **MISSING**
- **Status**: ❌ **NON-COMPLIANT**
- **Action Needed**:
  1. Create `ipfs_kit_py/mcp/servers/wal_telemetry_mcp_tools.py`
  2. Create `mcp/wal_telemetry_mcp_tools.py` shim
  3. Integrate CLI into main dispatcher

#### 14. Bucket Management (Simple/Unified)
- **Core Module**: `ipfs_kit_py/simple_bucket_manager.py`, `unified_bucket_interface.py`
- **CLI**: 
  - `ipfs_kit_py/simple_bucket_cli.py` (standalone)
  - `ipfs_kit_py/unified_bucket_cli.py` (standalone)
  - `ipfs_kit_py/clean_bucket_cli.py` (standalone)
  - `ipfs_kit_py/cli/bucket_cli.py` (subdirectory)
- **MCP Tools**: ✅ Covered by bucket_vfs_mcp_tools
- **MCP Shim**: ✅ Exists
- **Status**: ⚠️ **PARTIAL** - Multiple CLI files not integrated
- **Action Needed**:
  1. Consolidate bucket CLIs
  2. Integrate into main dispatcher

---

## Current CLI Entry Point

**Single Entry Point**: `ipfs-kit = "ipfs_kit_py.cli:sync_main"`

**Main CLI File**: `ipfs_kit_py/cli.py`

**Current Subcommands**:
```
ipfs-kit mcp start [options]
ipfs-kit mcp stop [options]
ipfs-kit mcp status [options]
ipfs-kit mcp deprecations [options]
```

**Missing Subcommands** (standalone CLIs not integrated):
- `ipfs-kit bucket` - Bucket VFS operations
- `ipfs-kit vfs` - VFS versioning
- `ipfs-kit wal` - Write-ahead log
- `ipfs-kit pin` - Pin management
- `ipfs-kit backend` - Backend management
- `ipfs-kit daemon` - Daemon operations
- `ipfs-kit journal` - Filesystem journal
- `ipfs-kit webrtc` - WebRTC operations
- `ipfs-kit filecoin` - Filecoin integration
- `ipfs-kit state` - State management
- `ipfs-kit p2p` - P2P workflows
- `ipfs-kit telemetry` - Telemetry operations

---

## Summary Statistics

### Overall Compliance

- **✅ Fully Compliant**: 1 component (7%)
- **⚠️ Partially Compliant**: 3 components (21%)
- **❌ Non-Compliant**: 10 components (72%)

### Missing Components

- **MCP Tools Missing**: 10 modules
- **MCP Shims Missing**: 10 modules
- **CLI Not Integrated**: 13+ standalone CLI files
- **Total CLI Files**: 25+ files

### Priority Recommendations

1. **High Priority** (Core functionality):
   - WAL management MCP tools
   - Pin management MCP tools
   - Backend management MCP tools
   - Integrate bucket CLI, vfs CLI, wal CLI

2. **Medium Priority** (Common operations):
   - Daemon management MCP tools
   - Filesystem journal MCP tools
   - State management MCP tools
   - Integrate pin CLI, daemon CLI, journal CLI

3. **Lower Priority** (Specialized features):
   - WebRTC MCP tools
   - Filecoin MCP tools
   - P2P workflow MCP tools
   - WAL telemetry MCP tools

---

## Recommended Implementation Order

### Phase 1: Core Infrastructure (Week 1)
1. Expand main CLI dispatcher to support subcommands
2. Create template for MCP tools + shims
3. Integrate bucket, vfs, and wal CLIs

### Phase 2: Essential Tools (Week 2)
4. Create WAL MCP tools + shim
5. Create Pin management MCP tools + shim
6. Create Backend management MCP tools + shim
7. Integrate corresponding CLIs

### Phase 3: Management Tools (Week 3)
8. Create Daemon management MCP tools + shim
9. Create Filesystem journal MCP tools + shim
10. Create State management MCP tools + shim
11. Integrate corresponding CLIs

### Phase 4: Specialized Features (Week 4)
12. Create WebRTC MCP tools + shim
13. Create Filecoin MCP tools + shim
14. Create P2P workflow MCP tools + shim
15. Create WAL telemetry MCP tools + shim
16. Integrate remaining CLIs

### Phase 5: Testing & Documentation (Week 5)
17. Comprehensive testing of all CLI commands
18. Comprehensive testing of all MCP tools
19. Update documentation
20. Create architecture diagrams

---

## Architecture Pattern Template

### For Each Feature Module:

```
Feature Name: <name>
├── Core Module: ipfs_kit_py/<name>.py
├── CLI Integration: ipfs_kit_py/<name>_cli.py
│   └── Integrated into: ipfs_kit_py/cli.py (ipfs-kit <name> subcommand)
├── MCP Tools: ipfs_kit_py/mcp/servers/<name>_mcp_tools.py
└── MCP Shim: mcp/<name>_mcp_tools.py
    └── Exposed to: MCP Server → JS SDK → Dashboard
```

### Required Files for New Feature:

1. **Core Module** (`ipfs_kit_py/<name>.py`)
   - Business logic
   - No external interface dependencies
   - Fully testable

2. **CLI Integration** (`ipfs_kit_py/<name>_cli.py`)
   - Imports from core module
   - CLI argument parsing
   - User-friendly interface
   - Entry function for main CLI dispatcher

3. **MCP Tools** (`ipfs_kit_py/mcp/servers/<name>_mcp_tools.py`)
   - Imports from core module
   - MCP Tool definitions
   - Async handlers
   - JSON response formatting

4. **MCP Shim** (`mcp/<name>_mcp_tools.py`)
   - Re-exports from ipfs_kit_py.mcp.servers
   - Backward compatibility
   - Test patching support

5. **Main CLI Integration** (add to `ipfs_kit_py/cli.py`)
   - Add subcommand parser
   - Import CLI module
   - Wire up commands

---

## Conclusion

The repository has a well-defined architecture pattern that is being followed for newer components (secrets, bucket VFS), but many legacy CLI tools and core modules lack proper MCP integration and CLI integration. A systematic effort is needed to bring all components into compliance with the target architecture.

**Total Effort Estimate**: 4-5 weeks for complete compliance
**High Priority Items**: 10-15 components
**Testing Required**: 25+ CLI commands, 40+ MCP tools
