#!/usr/bin/env python3
"""
Simple test to isolate the vfs_list_mounts issue.
"""

import anyio
import sys
import os
from pathlib import Path
import pytest

# Add the project root to the Python path
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

pytestmark = pytest.mark.anyio

async def test_vfs_list_mounts():
    """Test vfs_list_mounts specifically."""
    try:
        from ipfs_kit_py.mcp.ipfs_kit.mcp.enhanced_mcp_server_with_daemon_mgmt import IPFSKitIntegration
        
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
    result = anyio.run(test_vfs_list_mounts)
