#!/usr/bin/env python3
"""
Direct test of the MCP server mock operations
"""
import sys
import os
# Add the parent directory to the path to allow imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Direct import of the IPFSKitIntegration class
from mcp.ipfs_kit.mcp.enhanced_mcp_server_with_daemon_mgmt import IPFSKitIntegration
import anyio

async def test_mock_operations():
    """Test the mock operations directly"""
    integration = IPFSKitIntegration()
    
    print("Testing VFS Mount operation...")
    result = await integration._mock_operation("vfs_mount", 
                                              error_reason="Testing new error format",
                                              ipfs_path="/ipfs/test",
                                              mount_point="/tmp/test")
    
    print("VFS Mount Mock Result:")
    print(result)
    print()
    
    print("Testing DAG Get operation...")
    result = await integration._mock_operation("ipfs_dag_get", 
                                              error_reason="Testing new error format",
                                              cid="QmInvalidCIDThatDoesNotExist12345")
    
    print("DAG Get Mock Result:")
    print(result)
    print()
    
    print("Testing complete execute_ipfs_operation...")
    result = await integration.execute_ipfs_operation("vfs_mount", 
                                                     ipfs_path="/ipfs/test",
                                                     mount_point="/tmp/test")
    
    print("Execute IPFS Operation Result:")
    print(result)

if __name__ == "__main__":
    anyio.run(test_mock_operations)
