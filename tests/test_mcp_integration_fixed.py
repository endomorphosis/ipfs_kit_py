#!/usr/bin/env python3
"""
Test the daemon management fix in the MCP server.
"""

import sys
import os
import pytest

# Add the project root to Python path
from pathlib import Path


repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

pytestmark = pytest.mark.anyio

try:
    from ipfs_kit_py.mcp.servers.unified_mcp_server import create_mcp_server
    
    print("Testing IPFS Kit Integration with corrected daemon management...")
    
    # Create integration instance
    integration = IPFSKitIntegration()
    
    print("✅ Integration initialized successfully")
    
    # Test a simple operation
    import anyio
    
    async def test_operation():
        try:
            result = await integration.execute_ipfs_operation("ipfs_id")
            print(f"✅ IPFS ID operation result: {result.get('success', False)}")
            return True
        except Exception as e:
            print(f"❌ IPFS operation failed: {e}")
            return False
    
    # Run the test
    success = anyio.run(test_operation)
    print(f"\nOverall test result: {'✅ Success' if success else '❌ Failed'}")
    
except Exception as e:
    print(f"❌ Test failed with error: {e}")
    import traceback
    traceback.print_exc()
