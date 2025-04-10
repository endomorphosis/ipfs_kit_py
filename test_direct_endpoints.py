"""
Test script to directly test the newly implemented MCP API endpoints.
This script will test each endpoint individually without going through the test framework.
"""

import os
import time
import json
import sys
import requests
import tempfile
import subprocess

# Configuration
MCP_SERVER_URL = "http://localhost:8000"
MCP_API_BASE = "/api/v0"  # Try without the /mcp part
TEST_FILE_CONTENT = b"Hello, MCP Server! This is a test file."
TEST_TEXT_CONTENT = "Hello, MCP Server! This is a test string."

# Utility function for making requests
def make_request(method, endpoint, **kwargs):
    """Make an HTTP request with error handling."""
    url = f"{MCP_SERVER_URL}{endpoint}"
    
    try:
        response = getattr(requests, method.lower())(url, **kwargs)
        response.raise_for_status()
        return response.json() if response.content else {}
    except requests.exceptions.RequestException as e:
        print(f"Error making {method} request to {endpoint}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            try:
                print(f"Response body: {e.response.json()}")
            except ValueError:
                print(f"Response text: {e.response.text}")
        return {"success": False, "error": str(e)}

# Start MCP server
def start_server():
    """Start the MCP server subprocess."""
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "run_mcp_server:app", "--host", "127.0.0.1", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.path.dirname(os.path.abspath(__file__))
    )
    
    # Wait for server to start
    print("Waiting for server to start...")
    time.sleep(5)
    
    return process

# Test endpoints directly
def test_endpoints():
    """Test each of the newly implemented endpoints directly."""
    
    # Access global API base and allow modification
    global MCP_API_BASE
    
    # First see what endpoints are actually available
    paths_to_try = [
        "/",
        MCP_API_BASE,
        f"{MCP_API_BASE}/ipfs",
        f"{MCP_API_BASE}/mcp",
        f"{MCP_API_BASE}/mcp/ipfs",
        f"{MCP_API_BASE}/mcp/health"
    ]
    
    print("Checking available endpoints...")
    for path in paths_to_try:
        try:
            response = requests.get(f"{MCP_SERVER_URL}{path}")
            print(f"Path {path}: Status {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Path {path}: Error {e}")
    
    # Try to add a file to get a CID for further tests
    print("\nTesting IPFS add operation...")
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(TEST_FILE_CONTENT)
        temp_file_path = temp_file.name
    
    try:
        # Try multiple possible endpoints for add
        possible_endpoints = [
            f"{MCP_API_BASE}/ipfs/add",
            f"{MCP_API_BASE}/mcp/ipfs/add"
        ]
        
        cid = None
        for endpoint in possible_endpoints:
            print(f"Trying to add file with endpoint: {endpoint}")
            with open(temp_file_path, 'rb') as f:
                files = {'file': ('test.txt', f, 'text/plain')}
                response = requests.post(f"{MCP_SERVER_URL}{endpoint}", files=files)
                print(f"Status: {response.status_code}")
                if response.status_code == 200:
                    try:
                        result = response.json()
                        if "cid" in result or "Hash" in result:
                            cid = result.get("cid", result.get("Hash"))
                            print(f"Successfully added file with CID: {cid}")
                            MCP_API_BASE = endpoint.rsplit('/ipfs/add', 1)[0]
                            print(f"Using API base: {MCP_API_BASE}")
                            break
                    except Exception as e:
                        print(f"Error parsing response: {e}")
    
        if not cid:
            print("Failed to add file and get CID. Cannot proceed with other tests.")
            return False
            
        # Now test the newly implemented endpoints
        
        # Test Files API (MFS)
        print("\nTesting Files API (MFS) endpoints...")
        
        print("Creating directory...")
        response = make_request(
            "POST", 
            f"{MCP_API_BASE}/ipfs/files/mkdir", 
            json={"path": "/test-dir", "parents": True}
        )
        print(f"Files mkdir response: {json.dumps(response, indent=2)}")
        
        print("Listing files...")
        response = make_request(
            "GET", 
            f"{MCP_API_BASE}/ipfs/files/ls",
            params={"path": "/", "long": "true"}
        )
        print(f"Files ls response: {json.dumps(response, indent=2)}")
        
        # Test DAG API
        print("\nTesting DAG API...")
        dag_node = {
            "data": "test data",
            "links": []
        }
        response = make_request(
            "POST", 
            f"{MCP_API_BASE}/ipfs/dag/put", 
            json={"node": dag_node, "store_codec": "dag-cbor", "pin": True}
        )
        print(f"DAG put response: {json.dumps(response, indent=2)}")
        
        # Test Block API
        print("\nTesting Block API...")
        block_data = "Test block data"
        encoded_data = block_data.encode("utf-8").hex()
        
        response = make_request(
            "POST", 
            f"{MCP_API_BASE}/ipfs/block/put", 
            json={"data": encoded_data, "format": "raw"}
        )
        print(f"Block put response: {json.dumps(response, indent=2)}")
        
        # Test DHT API
        print("\nTesting DHT API...")
        response = make_request(
            "GET", 
            f"{MCP_API_BASE}/ipfs/dht/findprovs",
            params={"cid": cid}
        )
        print(f"DHT findprovs response: {json.dumps(response, indent=2)}")
        
        return True
        
    finally:
        # Clean up temp file
        try:
            os.unlink(temp_file_path)
        except OSError:
            pass

# Main function
if __name__ == "__main__":
    # Start the server
    print("Starting MCP server...")
    server_process = start_server()
    
    try:
        # Test endpoints
        test_endpoints()
    finally:
        # Stop the server
        print("Stopping MCP server...")
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print("Server didn't terminate gracefully, forcing...")
            server_process.kill()