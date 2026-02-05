#!/usr/bin/env python3
import sys
from pathlib import Path


repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from ipfs_kit_py.mcp.servers.unified_mcp_server import create_mcp_server, IPFSKitIntegration
import anyio
import pytest

pytestmark = pytest.mark.anyio

async def test_mock_format():
    integration = IPFSKitIntegration(auto_start_daemons=False, auto_start_lotus_daemon=False)
    
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
    anyio.run(test_mock_format)
