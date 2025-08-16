#!/usr/bin/env python3
"""
Test the daemon management fix in the MCP server.
"""

import sys
import os

# Add the project root to Python path
sys.path.insert(0, '/home/runner/work/ipfs_kit_py/ipfs_kit_py')

try:
    from mcp.enhanced_mcp_server_with_daemon_mgmt import IPFSKitIntegration
    
    print("Testing IPFS Kit Integration with corrected daemon management...")
    
    # Create integration instance
    integration = IPFSKitIntegration()
    
    print("✅ Integration initialized successfully")
    
    # Test a simple operation
    import asyncio
    
    async def test_operation():
        try:
            result = await integration.execute_ipfs_operation("ipfs_id")
            print(f"✅ IPFS ID operation result: {result.get('success', False)}")
            return True
        except Exception as e:
            print(f"❌ IPFS operation failed: {e}")
            return False
    
    # Run the test
    success = asyncio.run(test_operation())
    print(f"\nOverall test result: {'✅ Success' if success else '❌ Failed'}")
    
except Exception as e:
    print(f"❌ Test failed with error: {e}")
    import traceback
    traceback.print_exc()
