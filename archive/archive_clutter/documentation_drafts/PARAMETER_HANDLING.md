# Enhanced Parameter Handling in MCP Tools

This document explains the enhanced parameter handling approach implemented for IPFS and multi-backend tools in the Model Context Protocol (MCP) server.

## Problem Statement

Tools registered with the MCP server were experiencing parameter naming inconsistencies between client calls and tool implementations, causing tools to fail when clients used parameter names that differed from those expected by the tool implementations.

Common examples:
- Clients sending `content` when implementations expected `data`
- Clients sending `path` when implementations expected `file_path`
- Clients sending `hash` when implementations expected `cid`

## Solution Approach

We've implemented a multi-layered approach to parameter handling:

1. **Enhanced Parameter Adapter** - A general-purpose adapter that maps parameter names between client calls and tool implementations
2. **Direct Tool Handlers** - Specialized handlers for problematic tools that directly extract parameters using multiple possible names
3. **Common Parameter Mappings** - A centralized mapping of equivalent parameter names across all tools
4. **ToolContext Wrapper** - A wrapper that provides consistent access to parameters regardless of how they're passed

## Architecture

### Enhanced Parameter Adapter

The `enhanced_parameter_adapter.py` module provides:

- A `ToolContext` class that wraps the original context and provides consistent access to parameters
- An `adapt_parameters` decorator that automatically maps parameters using configurable mappings
- Utility functions for creating tool wrappers and generic handlers

### Direct Tool Handlers

Direct handlers are implemented in:
- `ipfs_tool_adapters.py` - Handlers for IPFS tools
- `enhanced/multi_backend_tool_adapters.py` - Handlers for multi-backend filesystem tools

These handlers:
1. Extract parameters using multiple possible names with fallbacks
2. Validate required parameters
3. Call the actual implementation with the correct parameter names
4. Provide consistent error handling

### Common Parameter Mappings

The common parameter mappings are defined in `enhanced_parameter_adapter.py` and include:

```python
COMMON_PARAM_MAPPINGS = {
    'content': ['content', 'data', 'text', 'value'],
    'cid': ['cid', 'hash', 'content_id', 'ipfs_hash'],
    'path': ['path', 'file_path', 'filepath', 'mfs_path', 'vfs_path', 'fs_path'],
    ...
}
```

These mappings are used by both the enhanced parameter adapter and the direct tool handlers.

## Tool Registration Process

When registering tools with the MCP server, the following process is used:

1. Try to get a direct handler for the tool from `ipfs_tool_adapters.py` or `multi_backend_tool_adapters.py`
2. If a direct handler exists, register it with the MCP server
3. If no direct handler exists, create a tool wrapper using the enhanced parameter adapter
4. Register the wrapped handler with the MCP server

## Using the Enhanced Parameter Handling

### Starting the Enhanced MCP Server

```bash
# Start the server
./enhanced_mcp_launcher.py --action start

# Check server status
./enhanced_mcp_launcher.py --action status

# Restart the server
./enhanced_mcp_launcher.py --action restart

# Stop the server
./enhanced_mcp_launcher.py --action stop
```

### Testing Parameter Handling

Run the test scripts to verify parameter handling:

```bash
# Test IPFS parameter handling
python test_ipfs_mcp_tools.py

# Test multi-backend parameter handling
python test_multi_backend_params.py
```

## Implementation Examples

### Direct Handler Example

```python
async def handle_ipfs_add(ctx):
    """Custom handler for ipfs_add with direct parameter mapping"""
    wrapped_ctx = ToolContext(ctx)
    arguments = wrapped_ctx.arguments
    
    # Extract parameters with fallbacks
    content = arguments.get('content', arguments.get('data', arguments.get('text')))
    filename = arguments.get('filename', arguments.get('name'))
    pin = arguments.get('pin', True)
    
    if not content:
        return {
            "success": False,
            "error": "Missing required parameter: content"
        }
    
    # Call the implementation function with correct parameters
    result = await add_content(content, filename, pin)
    return result
```

### Using the Parameter Adapter Decorator

```python
@adapt_parameters(mappings={
    'filename': ['name', 'file_name'],
    'pin': ['should_pin', 'keep']
})
async def ipfs_add_content(content, filename=None, pin=True):
    """Add content to IPFS"""
    # Implementation that uses the correctly mapped parameters
    ...
```

## Advantages of This Approach

1. **Compatibility** - Tools work with various parameter naming conventions
2. **Maintainability** - Common parameter mappings are centralized
3. **Flexibility** - Direct handlers for problematic tools, adapter for others
4. **Transparency** - Debugging information shows parameter mapping
5. **Robustness** - Consistent error handling and parameter validation

## Future Improvements

1. **Automatic Parameter Analysis** - Analyze tool usage patterns to automatically identify parameter mappings
2. **Schema Validation** - Add schema validation for parameters
3. **Client-Side Adapter** - Create a client-side adapter for consistent parameter naming
4. **Interactive Documentation** - Generate documentation that shows all accepted parameter names for each tool
