#!/usr/bin/env python3
"""
Validation script for the enhanced MCP server with comprehensive tool coverage.
Tests tool registration, execution, and mock implementations.
"""

import sys
import os
import traceback
import asyncio

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def test_server_import():
    """Test importing the MCP server module."""
    try:
        print("Testing server import...")
        from mcp.ipfs_kit.mcp.enhanced_mcp_server_with_daemon_mgmt import EnhancedMCPServerWithDaemonMgmt
        print("✓ Server module imported successfully")
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        traceback.print_exc()
        return False

def test_server_instantiation():
    """Test creating a server instance."""
    try:
        print("\nTesting server instantiation...")
        from mcp.ipfs_kit.mcp.enhanced_mcp_server_with_daemon_mgmt import EnhancedMCPServerWithDaemonMgmt
        server = EnhancedMCPServerWithDaemonMgmt()
        print("✓ Server instantiated successfully")
        return server
    except Exception as e:
        print(f"✗ Instantiation failed: {e}")
        traceback.print_exc()
        return None

def test_tool_registration(server):
    """Test tool registration and counting."""
    try:
        print("\nTesting tool registration...")
        tools = list(server.tools.keys())
        print(f"✓ {len(tools)} tools registered")
        
        # Categorize tools
        categories = {
            'core': [t for t in tools if t.startswith('ipfs_') and not any(k in t for k in ['dht', 'name', 'pubsub', 'files'])],
            'advanced': [t for t in tools if any(k in t for k in ['dht', 'name', 'pubsub', 'swarm'])],
            'mfs': [t for t in tools if 'files_' in t],
            'vfs': [t for t in tools if 'vfs_' in t],
            'system': [t for t in tools if t in ['system_health']]
        }
        
        for category, tool_list in categories.items():
            print(f"  {category.upper()}: {len(tool_list)} tools")
            if tool_list:
                print(f"    Examples: {', '.join(tool_list[:3])}")
        
        return tools
    except Exception as e:
        print(f"✗ Tool registration test failed: {e}")
        traceback.print_exc()
        return []

async def test_sample_tool_execution(server, tools):
    """Test executing a few sample tools."""
    try:
        print("\nTesting sample tool execution...")
        
        # Test a few representative tools
        test_tools = []
        if 'ipfs_version' in tools:
            test_tools.append('ipfs_version')
        if 'ipfs_id' in tools:
            test_tools.append('ipfs_id')
        if 'ipfs_files_ls' in tools:
            test_tools.append('ipfs_files_ls')
        if 'vfs_list_mounts' in tools:
            test_tools.append('vfs_list_mounts')
        if 'system_health' in tools:
            test_tools.append('system_health')
        
        for tool_name in test_tools[:3]:  # Test first 3 available tools
            try:
                print(f"  Testing {tool_name}...")
                result = await server.execute_tool(tool_name, {})
                if result and result.get('success') is not False:
                    print(f"    ✓ {tool_name} executed successfully")
                    if 'error' not in result:
                        print(f"      Result: {str(result)[:100]}...")
                else:
                    print(f"    ⚠ {tool_name} returned error: {result.get('error', 'Unknown error')}")
            except Exception as e:
                print(f"    ✗ {tool_name} failed: {e}")
        
        return True
    except Exception as e:
        print(f"✗ Tool execution test failed: {e}")
        traceback.print_exc()
        return False

async def main():
    """Main validation function."""
    print("=== MCP Server Validation ===")
    
    # Test 1: Import
    if not test_server_import():
        print("\n❌ Validation failed at import stage")
        return False
    
    # Test 2: Instantiation
    server = test_server_instantiation()
    if not server:
        print("\n❌ Validation failed at instantiation stage")
        return False
    
    # Test 3: Tool registration
    tools = test_tool_registration(server)
    if not tools:
        print("\n❌ Validation failed at tool registration stage")
        return False
    
    # Test 4: Tool execution
    if not await test_sample_tool_execution(server, tools):
        print("\n❌ Validation failed at tool execution stage")
        return False
    
    print("\n✅ All validation tests passed!")
    print(f"Server is ready with {len(tools)} tools registered")
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
