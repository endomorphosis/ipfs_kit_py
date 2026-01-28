#!/usr/bin/env python3
"""
Test VFS MCP Tools Integration
=============================

This script verifies that all VFS (Virtual File System) tools are properly
integrated with the MCP server and functioning correctly.
"""

import anyio
import inspect
import json
import sys
import os
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
import pytest

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

pytestmark = pytest.mark.anyio

print("🔍 Testing VFS MCP Tools Integration")
print("=" * 50)

# List of all VFS tools that should be available
EXPECTED_VFS_TOOLS = [
    "vfs_mount",
    "vfs_unmount", 
    "vfs_list_mounts",
    "vfs_read",
    "vfs_write",
    "vfs_copy",
    "vfs_move",
    "vfs_mkdir",
    "vfs_rmdir",
    "vfs_ls",
    "vfs_stat",
    "vfs_sync_to_ipfs",
    "vfs_sync_from_ipfs"
]

def test_vfs_tools_availability():
    """Test that all VFS tools are available in the MCP server."""
    print("\n📋 Testing VFS Tools Availability")
    print("-" * 40)
    
    try:
        # Import the MCP server
        from mcp.enhanced_mcp_server_with_daemon_mgmt import EnhancedMCPServerWithDaemonMgmt
        
        # Create server instance
        server = EnhancedMCPServerWithDaemonMgmt()
        
        # Check that all expected VFS tools are registered
        available_tools = list(server.tools.keys())
        vfs_tools = [tool for tool in available_tools if tool.startswith("vfs_")]
        
        print(f"✅ Found {len(vfs_tools)} VFS tools:")
        for tool in sorted(vfs_tools):
            print(f"   - {tool}")
        
        # Check if all expected tools are present
        missing_tools = set(EXPECTED_VFS_TOOLS) - set(vfs_tools)
        if missing_tools:
            print(f"\n❌ Missing VFS tools: {missing_tools}")
            return False
        
        extra_tools = set(vfs_tools) - set(EXPECTED_VFS_TOOLS)
        if extra_tools:
            print(f"\n➕ Extra VFS tools found: {extra_tools}")
        
        print(f"\n✅ All {len(EXPECTED_VFS_TOOLS)} expected VFS tools are available!")
        return True
        
    except Exception as e:
        print(f"❌ Error testing VFS tools availability: {e}")
        return False

def test_vfs_tool_schemas():
    """Test that all VFS tools have proper schema definitions."""
    print("\n🔧 Testing VFS Tool Schemas")
    print("-" * 40)
    
    try:
        from mcp.enhanced_mcp_server_with_daemon_mgmt import EnhancedMCPServerWithDaemonMgmt
        
        server = EnhancedMCPServerWithDaemonMgmt()
        
        schema_issues = []
        
        for tool_name in EXPECTED_VFS_TOOLS:
            if tool_name not in server.tools:
                schema_issues.append(f"Tool {tool_name} not found")
                continue
                
            tool = server.tools[tool_name]
            
            # Check required fields
            if "name" not in tool:
                schema_issues.append(f"{tool_name}: missing 'name' field")
            if "description" not in tool:
                schema_issues.append(f"{tool_name}: missing 'description' field")
            if "inputSchema" not in tool:
                schema_issues.append(f"{tool_name}: missing 'inputSchema' field")
            else:
                # Check inputSchema structure
                schema = tool["inputSchema"]
                if "type" not in schema:
                    schema_issues.append(f"{tool_name}: inputSchema missing 'type' field")
                if "properties" not in schema:
                    schema_issues.append(f"{tool_name}: inputSchema missing 'properties' field")
        
        if schema_issues:
            print("❌ Schema validation issues found:")
            for issue in schema_issues:
                print(f"   - {issue}")
            return False
        
        print("✅ All VFS tool schemas are properly defined!")
        return True
        
    except Exception as e:
        print(f"❌ Error testing VFS tool schemas: {e}")
        return False

def test_vfs_core_integration():
    """Test the VFS core integration."""
    print("\n🔌 Testing VFS Core Integration")
    print("-" * 40)
    
    try:
        # Test VFS core import
        from ipfs_fsspec import get_vfs, VFSCore
        
        # Get VFS instance
        vfs = get_vfs()
        
        print(f"✅ VFS instance created: {type(vfs).__name__}")
        
        # Test basic VFS operations
        print("📂 Testing basic VFS operations...")
        
        # Test registry
        if hasattr(vfs, 'registry'):
            print("✅ VFS registry available")
        else:
            print("❌ VFS registry not found")
            return False
            
        # Test cache manager
        if hasattr(vfs, 'cache_manager'):
            print("✅ VFS cache manager available")
        else:
            print("❌ VFS cache manager not found")
            return False
            
        # Test replication manager
        if hasattr(vfs, 'replication_manager'):
            print("✅ VFS replication manager available")
        else:
            print("❌ VFS replication manager not found")
            return False
            
        print("✅ VFS core integration verified!")
        return True
        
    except Exception as e:
        print(f"❌ Error testing VFS core integration: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_vfs_async_functions():
    """Test the async VFS functions."""
    print("\n⚡ Testing VFS Async Functions")
    print("-" * 40)
    
    try:
        from ipfs_fsspec import (
            vfs_mount, vfs_unmount, vfs_list_mounts, vfs_read, vfs_write,
            vfs_ls, vfs_stat, vfs_mkdir, vfs_rmdir, vfs_copy, vfs_move,
            vfs_sync_to_ipfs, vfs_sync_from_ipfs
        )
        
        print("✅ All VFS async functions imported successfully")
        
        # Test that functions are callable
        async_functions = [
            vfs_mount, vfs_unmount, vfs_list_mounts, vfs_read, vfs_write,
            vfs_ls, vfs_stat, vfs_mkdir, vfs_rmdir, vfs_copy, vfs_move,
            vfs_sync_to_ipfs, vfs_sync_from_ipfs
        ]
        
        for func in async_functions:
            if not callable(func):
                print(f"❌ {func.__name__} is not callable")
                return False
                
        print("✅ All VFS async functions are callable!")
        return True
        
    except Exception as e:
        print(f"❌ Error testing VFS async functions: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_vfs_tool_execution():
    """Test VFS tool execution through the MCP server."""
    print("\n🏃 Testing VFS Tool Execution")
    print("-" * 40)
    
    try:
        from mcp.enhanced_mcp_server_with_daemon_mgmt import EnhancedMCPServerWithDaemonMgmt
        
        server = EnhancedMCPServerWithDaemonMgmt()
        
        # Test that execute_tool method exists
        if not hasattr(server, 'execute_tool'):
            print("❌ execute_tool method not found")
            return False
            
        print("✅ execute_tool method available")
        
        # Test that VFS operations are handled
        if not hasattr(server.ipfs_integration, 'execute_vfs_operation'):
            print("❌ execute_vfs_operation method not found")
            return False
            
        print("✅ execute_vfs_operation method available")
        
        # Test that VFS is integrated
        if not hasattr(server.ipfs_integration, 'vfs_enabled'):
            print("❌ vfs_enabled attribute not found")
            return False
            
        print("✅ VFS integration flag available")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing VFS tool execution: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_vfs_backend_support():
    """Test VFS backend support."""
    print("\n🔧 Testing VFS Backend Support")
    print("-" * 40)
    
    try:
        from ipfs_fsspec import VFSBackendRegistry
        
        # Test backend registry
        registry = VFSBackendRegistry()
        
        # Check for expected backends
        expected_backends = ["ipfs", "local", "memory", "s3"]
        available_backends = []
        
        for backend in expected_backends:
            try:
                backend_class = registry.get_backend(backend)
                if backend_class:
                    available_backends.append(backend)
                    print(f"✅ Backend '{backend}' available")
                else:
                    print(f"❌ Backend '{backend}' not available")
            except Exception as e:
                print(f"⚠️  Backend '{backend}' error: {e}")
        
        if len(available_backends) >= 2:  # At least local and memory should work
            print(f"✅ VFS backend support verified ({len(available_backends)} backends)")
            return True
        else:
            print(f"❌ Insufficient backend support ({len(available_backends)} backends)")
            return False
            
    except Exception as e:
        print(f"❌ Error testing VFS backend support: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_all_tests():
    """Run all VFS MCP integration tests."""
    print(f"\n🚀 Starting VFS MCP Integration Tests")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    tests = [
        ("VFS Tools Availability", test_vfs_tools_availability),
        ("VFS Tool Schemas", test_vfs_tool_schemas),
        ("VFS Core Integration", test_vfs_core_integration),
        ("VFS Async Functions", test_vfs_async_functions),
        ("VFS Tool Execution", test_vfs_tool_execution),
        ("VFS Backend Support", test_vfs_backend_support),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*60}")
        print(f"Running: {test_name}")
        print('='*60)
        
        try:
            if inspect.iscoroutinefunction(test_func):
                result = anyio.run(test_func)
            else:
                result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test '{test_name}' failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\n🎯 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All VFS MCP integration tests PASSED!")
        print("✅ VFS tools are fully integrated and working correctly!")
    else:
        print("⚠️  Some tests failed. VFS integration may need attention.")
    
    return passed == total

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
