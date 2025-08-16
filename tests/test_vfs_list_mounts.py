#!/usr/bin/env python3
"""
Simple test to isolate the vfs_list_mounts issue.
"""

import asyncio
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, '/home/runner/work/ipfs_kit_py/ipfs_kit_py')

async def test_vfs_list_mounts():
    """Test vfs_list_mounts specifically."""
    try:
        from mcp.ipfs_kit.mcp.enhanced_mcp_server_with_daemon_mgmt import IPFSKitIntegration
        
        integration = IPFSKitIntegration()
        
        print("Testing vfs_list_mounts...")
        result = await integration.execute_ipfs_operation("vfs_list_mounts")
        
        print(f"Result: {result}")
        print(f"Success: {result.get('success')}")
        print(f"Is Mock: {result.get('is_mock')}")
        print(f"Warning: {result.get('warning')}")
        print(f"Error Reason: {result.get('error_reason')}")
        
        return result
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    result = asyncio.run(test_vfs_list_mounts())
