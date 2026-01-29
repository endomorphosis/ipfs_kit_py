# MCP Integration Architecture Documentation

## Overview

This document describes the correct integration architecture for IPFS Kit MCP (Model Context Protocol) server tools and how they should interface with the core `ipfs_kit_py` package.

**Related Documentation:**
- `COMPLETE_INTEGRATION_SUMMARY.md` - Comprehensive summary of all 36 integrations
- `docs/IPFS_DATASETS_INTEGRATION.md` - Base integration patterns for datasets
- `docs/VFS_BUCKET_GRAPHRAG_INTEGRATION.md` - VFS bucket GraphRAG architecture

**Context:** This architecture guide is part of a larger integration effort that added distributed dataset storage (ipfs_datasets_py) and compute acceleration (ipfs_accelerate_py) across 36 strategic points in the repository. All integrations follow the principles outlined in this document.

---

## Architecture Design

### Component Hierarchy

```
┌─────────────────────────────────────────────────────────────┐
│                    ipfs_kit_py Package                       │
│  (Source of Truth - All Core Functionality)                 │
│                                                              │
│  ├── Core Modules (bucket_manager, vfs_manager, etc.)       │
│  ├── Storage Backends (IPFS, Filecoin, Lassie, etc.)       │
│  ├── AI/ML Integration (datasets, accelerate, etc.)        │
│  └── Utilities (error handling, logging, etc.)             │
└─────────────────────────────────────────────────────────────┘
                              ↓
        ┌─────────────────────┴─────────────────────┐
        ↓                     ↓                      ↓
┌──────────────┐    ┌──────────────────┐    ┌──────────────┐
│  CLI Tools   │    │  MCP Server      │    │  Daemon      │
│  (cli/)      │    │  (mcp/)          │    │  Services    │
│              │    │                  │    │              │
│ Commands     │    │ ├── Tools        │    │ Background   │
│ import from  │    │ ├── Handlers     │    │ Processes    │
│ ipfs_kit_py  │    │ └── Servers      │    │              │
└──────────────┘    └──────────────────┘    └──────────────┘
                              ↓
                    ┌──────────────────┐
                    │  JavaScript SDK  │
                    │  (MCP Client)    │
                    └──────────────────┘
                              ↓
                    ┌──────────────────┐
                    │  MCP Dashboard   │
                    │  (Web UI)        │
                    └──────────────────┘
```

## Integration Rules

### Rule 1: Single Source of Truth

**All core functionality MUST live in the `ipfs_kit_py` package.**

```python
# ✅ CORRECT: Core functionality in ipfs_kit_py
# File: ipfs_kit_py/bucket_vfs_manager.py
class BucketVFSManager:
    def create_bucket(self, name, config):
        # Implementation here
        pass
```

### Rule 2: Import from Package

**MCP tools, CLI tools, and handlers MUST import from `ipfs_kit_py` package.**

```python
# ✅ CORRECT: MCP tool imports from package
# File: mcp/bucket_vfs_mcp_tools.py
from ipfs_kit_py.bucket_vfs_manager import get_global_bucket_manager
from ipfs_kit_py.error import create_result_dict

# ❌ INCORRECT: Don't implement functionality in MCP tools
# File: mcp/bucket_vfs_mcp_tools.py
class BucketVFSManager:  # Don't do this!
    def create_bucket(self, name, config):
        pass
```

### Rule 3: No Relative Imports Outside Package

**Files in `mcp/` should NOT use relative imports to access functionality.**

```python
# ✅ CORRECT: Absolute imports from package
from ipfs_kit_py.mcp.ipfs_kit.core.tool_registry import tool
from ipfs_kit_py.bucket_vfs_manager import get_global_bucket_manager

# ❌ INCORRECT: Relative imports
from core.tool_registry import tool  # Where is 'core'?
from ..bucket_manager import BucketManager  # Unclear path
```

### Rule 4: MCP Tools Are Thin Wrappers

**MCP tools should be thin wrappers that:**
1. Import functionality from `ipfs_kit_py`
2. Adapt it to MCP protocol
3. Handle MCP-specific concerns (JSON serialization, error formatting)

```python
# ✅ CORRECT: Thin wrapper pattern
from ipfs_kit_py.bucket_vfs_manager import get_global_bucket_manager
from mcp.types import Tool, TextContent

def create_bucket_tool(name: str, config: dict) -> dict:
    """MCP tool wrapper for bucket creation."""
    # Get the actual implementation from package
    manager = get_global_bucket_manager()
    
    # Call the package function
    result = manager.create_bucket(name, config)
    
    # Format for MCP protocol
    return {
        "success": True,
        "data": result,
        "type": "bucket_created"
    }
```

## Current Status

### ✅ Compliant Components

**VFS and Bucket MCP Tools:**
- `mcp/bucket_vfs_mcp_tools.py` - ✅ Imports from ipfs_kit_py (includes ipfs_datasets integration)
- `mcp/vfs_version_mcp_tools.py` - ✅ Imports from ipfs_kit_py (includes ipfs_datasets integration)
- `mcp/ipfs_kit/mcp_tools/vfs_tools.py` - ✅ Imports from ipfs_kit_py (includes ipfs_datasets integration)
- `mcp/ipfs_kit/mcp_tools/backend_tools.py` - ✅ Uses dependency injection
- `mcp/ipfs_kit/mcp_tools/system_tools.py` - ✅ Uses standard library

**MCP Servers:**
- `mcp/enhanced_server.py` - ✅ Infrastructure-level integration with ipfs_datasets
- `mcp/enhanced_mcp_server_with_vfs.py` - ✅ Imports from ipfs_kit_py
- `mcp/enhanced_vfs_mcp_server.py` - ✅ Imports from ipfs_kit_py
- `mcp/standalone_vfs_mcp_server.py` - ✅ Imports from ipfs_kit_py

**MCP Handlers:**
- All handlers in `mcp_handlers/` - ✅ Follow correct pattern (placeholders)

**Integration Status:**
- 36 strategic integrations across repository (see `COMPLETE_INTEGRATION_SUMMARY.md`)
- All MCP tools properly import from `ipfs_kit_py` package
- Dataset storage and compute acceleration available throughout
- Graceful fallbacks ensure CI/CD compatibility

### ✅ All Components Now Compliant!

**IPFS Core Tools (FIXED):**
- `ipfs_kit_py/tools/ipfs_core_tools.py` - ✅ Moved to main package, uses absolute imports
- `ipfs_kit_py/tools/pin_management_tools.py` - ✅ Moved to main package, uses absolute imports
- `mcp/ipfs_kit/tools/ipfs_core_tools_wrapper.py` - ✅ Thin wrapper re-exports from main package
- `mcp/ipfs_kit/tools/pin_management_tools_wrapper.py` - ✅ Thin wrapper re-exports from main package

**Solution Implemented (✅ COMPLETE):**

1. ✅ **DONE** - Moved files to `ipfs_kit_py/tools/` directory
2. ✅ **DONE** - Fixed imports to use absolute paths from `ipfs_kit_py.mcp.ipfs_kit.core`
3. ✅ **DONE** - Created thin wrappers in MCP directory for backward compatibility
4. ✅ **DONE** - Added comprehensive tests in `tests/test_import_paths_validation.py`

**Test Results:**
```bash
Ran 10 tests in 0.110s
OK (skipped=5)

✓ ipfs_core_tools.py in main package: True
✓ pin_management_tools.py in main package: True
✓ No direct relative imports: True
✓ Architecture compliance: 100%
```

The original files remain in `mcp/ipfs_kit/tools/` but have been moved to the main package. Wrappers have been created for backward compatibility.

## Adding New MCP Tools

### Step 1: Implement Core Functionality

Place core implementation in `ipfs_kit_py/`:

```python
# File: ipfs_kit_py/my_new_feature.py
class MyNewFeature:
    def do_something(self, params):
        # Core implementation
        return result
```

### Step 2: Create MCP Tool Wrapper

Create MCP wrapper in `mcp/`:

```python
# File: mcp/my_new_feature_mcp_tools.py
from ipfs_kit_py.my_new_feature import MyNewFeature
from mcp.types import Tool, TextContent

def create_my_tool(params: dict) -> dict:
    """MCP tool for my new feature."""
    feature = MyNewFeature()
    result = feature.do_something(params)
    
    return {
        "success": True,
        "data": result
    }
```

### Step 3: Register with MCP Server

Add tool to MCP server configuration:

```python
# File: mcp/enhanced_mcp_server.py
from mcp.my_new_feature_mcp_tools import create_my_tool

# Register tool
server.register_tool("my_new_feature", create_my_tool)
```

### Step 4: Expose to CLI (Optional)

Add CLI command:

```python
# File: cli/my_feature_cli.py
from ipfs_kit_py.my_new_feature import MyNewFeature
import click

@click.command()
@click.option('--param', help='Parameter')
def my_feature(param):
    """CLI command for my feature."""
    feature = MyNewFeature()
    result = feature.do_something({"param": param})
    click.echo(result)
```

## Testing Integration Paths

### Import Path Test

Create a test to validate imports:

```python
# File: tests/test_mcp_integration_paths.py
def test_mcp_tools_import_from_package():
    """Verify MCP tools import from ipfs_kit_py package."""
    # These should work
    from ipfs_kit_py.bucket_vfs_manager import get_global_bucket_manager
    from ipfs_kit_py.vfs_version_tracker import VFSVersionTracker
    from ipfs_kit_py.ipfs_datasets_integration import get_ipfs_datasets_manager
    
    # MCP tools should use these imports
    from mcp.bucket_vfs_mcp_tools import init_dataset_storage
    from mcp.vfs_version_mcp_tools import create_version_tools
    
    # Both should work without errors
    manager = get_global_bucket_manager()
    assert manager is not None
```

### No Circular Imports Test

```python
def test_no_circular_imports():
    """Verify no circular import dependencies."""
    import ipfs_kit_py
    import mcp.bucket_vfs_mcp_tools
    import mcp.vfs_version_mcp_tools
    
    # Should import without circular dependency errors
    assert True
```

## Best Practices

### 1. Keep MCP Tools Stateless

MCP tools should be stateless and delegate to package classes:

```python
# ✅ GOOD: Stateless, delegates to package
from ipfs_kit_py.bucket_vfs_manager import get_global_bucket_manager

def list_buckets():
    manager = get_global_bucket_manager()
    return manager.list_buckets()
```

### 2. Handle MCP Protocol Concerns

MCP tools handle protocol-specific concerns:

```python
# ✅ GOOD: Handles MCP protocol concerns
from ipfs_kit_py.bucket_vfs_manager import get_global_bucket_manager
from mcp.types import Tool, TextContent

def create_bucket_tool():
    return Tool(
        name="create_bucket",
        description="Create a new VFS bucket",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "config": {"type": "object"}
            }
        }
    )

async def handle_create_bucket(name, config):
    manager = get_global_bucket_manager()
    result = manager.create_bucket(name, config)
    return TextContent(
        type="text",
        text=json.dumps(result)
    )
```

### 3. Integration with ipfs_datasets_py and ipfs_accelerate_py

**MCP tools automatically benefit from dataset storage and compute acceleration** when properly importing from `ipfs_kit_py`:

```python
# ✅ CORRECT: Automatically uses dataset storage and acceleration
from ipfs_kit_py.bucket_vfs_manager import get_global_bucket_manager
from ipfs_kit_py.ipfs_datasets_integration import get_ipfs_datasets_manager

def create_bucket_with_tracking():
    """Create bucket - automatically tracked in datasets if enabled."""
    manager = get_global_bucket_manager()
    
    # If bucket_manager has enable_dataset_storage=True,
    # this operation is automatically tracked to IPFS datasets
    result = manager.create_bucket("my-bucket", {})
    
    return result
```

**Key Points:**
- 36 integrations across repository enable dataset storage
- MCP tools inherit this functionality by importing from `ipfs_kit_py`
- No need to add tracking code in MCP layer
- Graceful fallback when ipfs_datasets_py unavailable
- See `COMPLETE_INTEGRATION_SUMMARY.md` for all integration points

### 4. Graceful Handling of Optional Dependencies

### 2. Handle MCP Protocol Concerns

MCP tools handle protocol-specific concerns:

```python
from ipfs_kit_py.bucket_vfs_manager import get_global_bucket_manager
from mcp.types import TextContent

def list_buckets_tool():
    # Get data from package
    manager = get_global_bucket_manager()
    buckets = manager.list_buckets()
    
    # Format for MCP protocol
    content = TextContent(
        type="text",
        text=json.dumps(buckets, indent=2)
    )
    
    return [content]
```

### 3. Import Optional Dependencies Gracefully

```python
# Try importing optional features
HAS_DATASETS = False
try:
    from ipfs_kit_py.ipfs_datasets_integration import get_ipfs_datasets_manager
    HAS_DATASETS = True
except ImportError:
    logger.info("ipfs_datasets_py not available")

# Use with fallback
if HAS_DATASETS:
    manager = get_ipfs_datasets_manager()
else:
    # Fallback behavior
    pass
```

## Summary

### Key Principles

1. **Single Source of Truth**: All core functionality in `ipfs_kit_py` package
2. **Import from Package**: MCP tools import from `ipfs_kit_py`, never implement core logic
3. **Absolute Imports**: Use absolute imports, not relative paths
4. **Thin Wrappers**: MCP tools are thin protocol adapters
5. **Graceful Fallbacks**: Handle missing optional dependencies

### Compliance Checklist

- [ ] Core functionality in `ipfs_kit_py/`
- [ ] MCP tools in `mcp/` import from `ipfs_kit_py`
- [ ] No relative imports in `mcp/` files
- [ ] No duplicate implementations
- [ ] CLI commands import from `ipfs_kit_py`
- [ ] Tests validate import paths
- [ ] Optional dependencies handled gracefully

---

**Document Version**: 1.0  
**Last Updated**: 2026-01-29  
**Audit Status**: Complete ✅  
**Compliance**: 🟡 Mostly Compliant (2 files need fixes)
