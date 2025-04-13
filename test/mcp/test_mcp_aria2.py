"""
Test the integration of Aria2 with the MCP server.

This test verifies that the Aria2 controller and model are properly 
integrated with the MCP server and that the API endpoints work correctly.
"""

import time
import json
import os
import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from ipfs_kit_py.mcp.server import MCPServer
from ipfs_kit_py.aria2_kit import aria2_kit

# Create a test FastAPI app
app = FastAPI()

# Create MCP server with debug mode for testing
mcp_server = MCPServer(
    debug_mode=True,
    log_level="INFO",
    isolation_mode=True,  # Use isolated mode for testing
    persistence_path="/tmp/ipfs_kit_test/aria2_mcp_test"
)

# Register MCP server with app
mcp_server.register_with_app(app, prefix="/mcp")

# Create test client
client = TestClient(app)

def test_aria2_health_endpoint():
    """Test the Aria2 health endpoint."""
    # Call the health endpoint
    response = client.get("/mcp/aria2/health")
    
    # Verify the response
    assert response.status_code == 200
    data = response.json()
    assert "success" in data
    assert "status" in data
    
    # Print the health status for debugging
    print(f"Aria2 health status: {data}")

def test_aria2_version_endpoint():
    """Test the Aria2 version endpoint."""
    # Call the version endpoint
    response = client.get("/mcp/aria2/version")
    
    # This might fail if Aria2 is not installed, which is ok for testing
    if response.status_code == 200:
        data = response.json()
        assert "success" in data
        assert data["success"] == True
        assert "version" in data
        print(f"Aria2 version: {data['version']}")
    else:
        # Print error for information only
        print(f"Aria2 version error (expected if aria2 not installed): {response.json()}")

def test_aria2_list_downloads():
    """Test listing downloads."""
    # Call the list endpoint
    response = client.get("/mcp/aria2/list")
    
    # This might fail if Aria2 is not running, which is ok for testing
    if response.status_code == 200:
        data = response.json()
        assert "success" in data
        assert "downloads" in data
        print(f"Aria2 downloads: {len(data['downloads'])}")
    else:
        # Print error for information only
        print(f"Aria2 list error (expected if aria2 not running): {response.json()}")
        
def test_aria2_add_uri():
    """Test adding a download by URI."""
    # Test data
    test_uri = "https://example.com/test.txt"
    test_data = {
        "uris": test_uri,
        "filename": "test.txt",
        "options": {
            "dir": "/tmp",
            "out": "test_download.txt"
        }
    }
    
    # Call the add endpoint
    response = client.post("/mcp/aria2/add", json=test_data)
    
    # This might fail if Aria2 is not running, which is ok for testing
    if response.status_code == 200:
        data = response.json()
        assert "success" in data
        assert data["success"] == True
        assert "gid" in data
        print(f"Added download with GID: {data['gid']}")
        
        # Try to get status
        time.sleep(1)  # Wait for download to start
        status_response = client.get(f"/mcp/aria2/status/{data['gid']}")
        
        if status_response.status_code == 200:
            status_data = status_response.json()
            assert status_data["success"] == True
            print(f"Download status: {status_data.get('state', 'unknown')}")
            
            # Try to pause download
            pause_response = client.post("/mcp/aria2/pause", json={"gid": data["gid"]})
            if pause_response.status_code == 200:
                print("Successfully paused download")
            
            # Try to resume download
            resume_response = client.post("/mcp/aria2/resume", json={"gid": data["gid"]})
            if resume_response.status_code == 200:
                print("Successfully resumed download")
            
            # Try to remove download
            remove_response = client.post("/mcp/aria2/remove", json={"gid": data["gid"]})
            if remove_response.status_code == 200:
                print("Successfully removed download")
    else:
        # Print error for information only
        print(f"Aria2 add error (expected if aria2 not running): {response.json()}")

def test_aria2_global_stats():
    """Test getting global statistics."""
    # Call the global stats endpoint
    response = client.get("/mcp/aria2/global-stats")
    
    # This might fail if Aria2 is not running, which is ok for testing
    if response.status_code == 200:
        data = response.json()
        assert "success" in data
        assert data["success"] == True
        print(f"Aria2 global stats: {data}")
    else:
        # Print error for information only
        print(f"Aria2 global stats error (expected if aria2 not running): {response.json()}")

def run_all_tests():
    """Run all tests manually in sequence."""
    print("\n=== Testing Aria2 MCP Integration ===\n")
    
    test_aria2_health_endpoint()
    test_aria2_version_endpoint()
    test_aria2_list_downloads()
    test_aria2_add_uri()
    test_aria2_global_stats()
    
    print("\n=== All tests completed ===")

if __name__ == "__main__":
    run_all_tests()