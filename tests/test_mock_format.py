#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/barberb/ipfs_kit_py')

from mcp.ipfs_kit.mcp.enhanced_mcp_server_with_daemon_mgmt import IPFSKitIntegration
import asyncio

async def test_mock_format():
    integration = IPFSKitIntegration()
    
    # Test a VFS operation that should return a mock
    result = await integration.execute_ipfs_operation("vfs_mount", 
                                                     ipfs_path="/ipfs/test",
                                                     mount_point="/tmp/test")
    
    print("VFS Mount result:")
    print(result)
    
    # Test DAG operation with invalid CID
    result = await integration.execute_ipfs_operation("ipfs_dag_get", 
                                                     cid="QmInvalidCIDThatDoesNotExist12345")
    
    print("\nDAG Get result:")
    print(result)

if __name__ == "__main__":
    asyncio.run(test_mock_format())
