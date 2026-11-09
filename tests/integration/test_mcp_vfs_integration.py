#!/usr/bin/env python3
"""
IPFS Kit Python - VFS integration test for MCP
Tests the integration between MCP, IPFS, and the Virtual File System.

This test verifies that:
1. The MCP server has VFS tools exposed
2. The VFS tools can interact with the IPFS system
3. End-to-end workflows between IPFS and VFS function correctly
"""

import json
import os
import pytest
import requests
import time
import uuid

# Get MCP server URL from environment or use default
MCP_BASE_URL = os.environ.get("MCP_BASE_URL", "http://localhost:9996")
JSONRPC_ENDPOINT = f"{MCP_BASE_URL}/jsonrpc"

# Test constants
TEST_CONTENT = "This is test content for VFS-IPFS integration testing."
TEST_DIR = f"/vfs-test-{uuid.uuid4().hex[:8]}"
TEST_FILE = f"{TEST_DIR}/test-file.txt"


def call_jsonrpc(method, params=None):
    """Call the JSON-RPC API with the given method and parameters."""
    if params is None:
        params = {}
    
    headers = {"Content-Type": "application/json"}
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1
    }
    
    response = requests.post(JSONRPC_ENDPOINT, headers=headers, json=payload)
    response.raise_for_status()
    result = response.json()
    
    if "error" in result:
        raise Exception(f"JSON-RPC error: {result['error']}")
    
    return result.get("result")


def test_mcp_server_health():
    """Test the MCP server health endpoint."""
    response = requests.get(f"{MCP_BASE_URL}/health")
    assert response.status_code == 200, "MCP server health check failed"


def test_ipfs_version():
    """Test that the IPFS version tool is available."""
    result = call_jsonrpc("ipfs_version")
    assert result, "IPFS version should return a value"
    assert "Version" in result, "IPFS version should contain Version field"


def test_vfs_tools_availability():
    """Test that essential VFS tools are available."""
    # Get the list of available methods
    response = requests.post(
        JSONRPC_ENDPOINT,
        headers={"Content-Type": "application/json"},
        json={"jsonrpc": "2.0", "method": "rpc.discover", "id": 1}
    )
    result = response.json()
    
    methods = []
    if "result" in result and "methods" in result["result"]:
        methods = list(result["result"]["methods"].keys())
    
    # Check for VFS tools
    vfs_tools = [
        "vfs_mount", "vfs_mkdir", "vfs_write", 
        "vfs_read", "vfs_ls", "vfs_rm", "vfs_exists"
    ]
    
    for tool in vfs_tools:
        assert tool in methods, f"VFS tool {tool} should be available"


def test_ipfs_add():
    """Test adding content to IPFS."""
    result = call_jsonrpc("ipfs_add", {"content": TEST_CONTENT})
    assert result, "IPFS add should return a result"
    assert "Hash" in result, "IPFS add should return a Hash (CID)"
    return result["Hash"]


def test_ipfs_cat(cid):
    """Test retrieving content from IPFS."""
    content = call_jsonrpc("ipfs_cat", {"cid": cid})
    assert content == TEST_CONTENT, "Retrieved content should match the original"


def test_vfs_mkdir():
    """Test creating a directory in VFS."""
    result = call_jsonrpc("vfs_mkdir", {"path": TEST_DIR})
    assert result is not None, "VFS mkdir should return a result"


def test_vfs_write(content):
    """Test writing content to a file in VFS."""
    result = call_jsonrpc("vfs_write", {"path": TEST_FILE, "content": content})
    assert result is not None, "VFS write should return a result"


def test_vfs_read():
    """Test reading content from a file in VFS."""
    content = call_jsonrpc("vfs_read", {"path": TEST_FILE})
    assert content, "VFS read should return content"
    return content


def test_vfs_ls():
    """Test listing the contents of a VFS directory."""
    result = call_jsonrpc("vfs_ls", {"path": TEST_DIR})
    assert result, "VFS ls should return a result"
    assert len(result) > 0, "VFS directory should not be empty"
    
    # Find our test file in the listing
    found = False
    for item in result:
        if item.get("name") == TEST_FILE.split("/")[-1]:
            found = True
            break
    
    assert found, f"Test file {TEST_FILE} should be in the directory listing"


def test_vfs_exists():
    """Test the VFS exists tool."""
    result = call_jsonrpc("vfs_exists", {"path": TEST_FILE})
    assert result is True, "Test file should exist in VFS"
    
    result = call_jsonrpc("vfs_exists", {"path": f"{TEST_FILE}_nonexistent"})
    assert result is False, "Nonexistent file should not exist in VFS"


def test_vfs_rm():
    """Test removing a file from VFS."""
    # First verify the file exists
    result = call_jsonrpc("vfs_exists", {"path": TEST_FILE})
    assert result is True, "Test file should exist before removal"
    
    # Remove the file
    result = call_jsonrpc("vfs_rm", {"path": TEST_FILE})
    assert result is not None, "VFS rm should return a result"
    
    # Verify the file no longer exists
    result = call_jsonrpc("vfs_exists", {"path": TEST_FILE})
    assert result is False, "Test file should not exist after removal"


@pytest.mark.dependency()
def test_e2e_ipfs_to_vfs_integration():
    """Test end-to-end integration from IPFS to VFS."""
    # Step 1: Add content to IPFS
    cid = test_ipfs_add()
    assert cid, "Should have received a valid CID"
    
    # Step 2: Create VFS directory
    test_vfs_mkdir()
    
    # Step 3: Write the CID to a file in VFS
    test_vfs_write(cid)
    
    # Step 4: Read the CID back from VFS
    read_cid = test_vfs_read()
    assert read_cid == cid, "CID read from VFS should match the original"
    
    # Step 5: Use the CID from VFS to retrieve content from IPFS
    test_ipfs_cat(read_cid)
    
    # Step 6: List the directory to verify the file exists
    test_vfs_ls()
    
    # Step 7: Clean up by removing the file
    test_vfs_rm()


if __name__ == "__main__":
    # Run the tests manually when executed directly
    print("Testing MCP server health...")
    test_mcp_server_health()
    
    print("Testing IPFS version...")
    test_ipfs_version()
    
    print("Testing VFS tools availability...")
    test_vfs_tools_availability()
    
    print("Testing end-to-end integration...")
    test_e2e_ipfs_to_vfs_integration()
    
    print("All tests passed!")
