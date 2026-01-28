#!/usr/bin/env python3
"""
Comprehensive test to check which MCP tools are working with real IPFS data vs mocks.
"""

import anyio
import json
import sys
import subprocess
import time
import pytest

# List of tools to test (excluding those that require specific parameters)
tools_to_test = [
    ("ipfs_version", {}),
    ("ipfs_id", {}),
    ("ipfs_pin_ls", {}),
    ("ipfs_swarm_peers", {}),
    ("ipfs_stats", {"stat_type": "repo"}),
    ("ipfs_refs_local", {}),
    ("ipfs_files_ls", {"path": "/"}),
    ("vfs_mount", {"ipfs_path": "/ipfs/test", "mount_point": "/tmp/test"}),
    ("vfs_list_mounts", {}),
    ("vfs_read", {"path": "/vfs/test"}),
    ("system_health", {}),
]

pytestmark = pytest.mark.anyio

async def test_tool_via_mcp():
    """Test tools directly via MCP."""
    from mcp.ipfs_kit.mcp.enhanced_mcp_server_with_daemon_mgmt import IPFSKitIntegration
    
    integration = IPFSKitIntegration()
    
    results = {}
    
    for tool_name, args in tools_to_test:
        try:
            print(f"Testing {tool_name}...")
            result = await integration.execute_ipfs_operation(tool_name, **args)
            
            # Check if it's real or mock data
            is_mock = result.get("is_mock", False)
            success = result.get("success", True)
            
            status = "REAL" if (success and not is_mock) else "MOCK/ERROR"
            if is_mock:
                status += f" (Reason: {result.get('error_reason', 'Unknown')})"
            
            results[tool_name] = {
                "status": status,
                "success": success,
                "is_mock": is_mock,
                "result": result
            }
            
            print(f"  {tool_name}: {status}")
            
        except Exception as e:
            results[tool_name] = {
                "status": f"ERROR: {e}",
                "success": False,
                "is_mock": False,
                "result": None
            }
            print(f"  {tool_name}: ERROR - {e}")
    
    return results

if __name__ == "__main__":
    results = anyio.run(test_tool_via_mcp)
    
    print("\n" + "="*50)
    print("SUMMARY:")
    print("="*50)
    
    real_tools = []
    mock_tools = []
    error_tools = []
    
    for tool_name, result in results.items():
        if "ERROR" in result["status"]:
            error_tools.append(tool_name)
        elif "MOCK" in result["status"]:
            mock_tools.append(tool_name)
        else:
            real_tools.append(tool_name)
    
    print(f"✅ REAL DATA ({len(real_tools)}): {', '.join(real_tools)}")
    print(f"⚠️  MOCK DATA ({len(mock_tools)}): {', '.join(mock_tools)}")
    print(f"❌ ERRORS ({len(error_tools)}): {', '.join(error_tools)}")
    
    print(f"\nTotal tools tested: {len(tools_to_test)}")
    print(f"Success rate: {len(real_tools)}/{len(tools_to_test)} ({len(real_tools)*100//len(tools_to_test)}%)")
