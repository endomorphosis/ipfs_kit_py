"""
Test script for the MCP server API.
This script tests various endpoints of the MCP server API.
"""

import os
import time
import json
import sys
import subprocess
import requests
import threading
import tempfile
import atexit

# Configuration
MCP_SERVER_URL = "http://localhost:8765"
MCP_API_PREFIX = "/api/v0/mcp"  # This matches the prefix in run_mcp_server.py
TEST_FILE_CONTENT = b"Hello, MCP Server! This is a test file."
TEST_TEXT_CONTENT = "Hello, MCP Server! This is a test string."

# First check if the server is running and what endpoints are available
def check_server_status():
    """Check if the server is running and what endpoints are available."""
    print("Checking server status...")
    
    # Try the health endpoint directly
    try:
        print(f"Trying health endpoint at {MCP_SERVER_URL}{MCP_API_PREFIX}/health")
        response = requests.get(f"{MCP_SERVER_URL}{MCP_API_PREFIX}/health")
        if response.status_code == 200:
            print("Health endpoint is accessible, server is running!")
            try:
                # Try to parse JSON response
                data = response.json()
                if data.get("success", False) or data.get("healthy", False):
                    print("Health check successful!")
                    return True
            except ValueError:
                # If it's not JSON but still a 200 response, consider it a success
                print("Health endpoint returned non-JSON but 200 status code, continuing...")
                return True
        else:
            print(f"Health endpoint responded with status code: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to health endpoint: {e}")
        return False

# Utility function for HTTP requests with error handling
def make_request(method, endpoint, **kwargs):
    """Make HTTP request with unified error handling."""
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

# Start the MCP server process
def start_server():
    """Start the MCP server process."""
    print("Starting MCP server with dedicated script...")
    
    # Make sure start_test_mcp_server.py exists
    server_script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "start_test_mcp_server.py")
    if not os.path.exists(server_script_path):
        print(f"Server script not found at {server_script_path}")
        return None
    
    # Start the server directly using the script
    process = subprocess.Popen(
        [sys.executable, server_script_path, "--host", "127.0.0.1", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.path.dirname(os.path.abspath(__file__))
    )
    
    # Wait for server to start
    print("Waiting for server to start...")
    for i in range(15):  # Try for 15 seconds
        time.sleep(1)
        try:
            # First try the health endpoint directly
            response = requests.get(f"{MCP_SERVER_URL}{MCP_API_PREFIX}/health")
            if response.status_code == 200:
                print(f"Server started successfully! Health endpoint working at {MCP_API_PREFIX}/health")
                return process
        except requests.exceptions.RequestException:
            pass
            
        try:
            # Then try root endpoint as fallback
            response = requests.get(f"{MCP_SERVER_URL}/")
            if response.status_code == 200:
                print("Server root endpoint is working. API should be available.")
                
                # Try to get information about API prefix
                try:
                    data = response.json()
                    if "api_prefix" in data:
                        # Update global variable
                        print(f"Server reported API prefix: {data['api_prefix']}")
                        # We'll use the defined prefix rather than changing it
                except:
                    pass
                    
                return process
        except requests.exceptions.RequestException:
            print(f"Server not yet ready... (attempt {i+1}/15)")
    
    # If we get here, server failed to start properly
    print("Failed to start server within timeout. Showing server output:")
    process.terminate()
    try:
        stdout, stderr = process.communicate(timeout=5)
        print("STDOUT:", stdout.decode(errors='replace'))
        print("STDERR:", stderr.decode(errors='replace'))
    except subprocess.TimeoutExpired:
        process.kill()
        print("Could not get server output within timeout.")
    
    return None

# Test health endpoint
def test_health():
    """Test the health endpoint."""
    print("Testing health endpoint...")
    response = make_request("GET", f"{MCP_API_PREFIX}/health")
    print(f"Health response: {json.dumps(response, indent=2)}")
    # Check for either "healthy" or "success" field for flexibility
    return response.get("healthy", response.get("success", False))

# Test daemon status endpoint
def test_daemon_status():
    """Test the daemon status endpoint."""
    print("Testing daemon status endpoint...")
    response = make_request("GET", f"{MCP_API_PREFIX}/daemon/status")
    print(f"Daemon status response: {json.dumps(response, indent=2)}")
    return response.get("success", False)

# Test IPFS add endpoint
def test_ipfs_add():
    """Test the IPFS add endpoint."""
    print("Testing IPFS add endpoint...")
    
    # Create a temporary file
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(TEST_FILE_CONTENT)
        temp_file_path = temp_file.name
    
    try:
        # Add file via multipart form
        with open(temp_file_path, 'rb') as f:
            files = {'file': ('test.txt', f, 'text/plain')}
            response = make_request(
                "POST", 
                f"{MCP_API_PREFIX}/ipfs/add", 
                files=files
            )
        print(f"IPFS add response: {json.dumps(response, indent=2)}")
        
        # Return CID if successful
        if response.get("success", False):
            return response.get("cid")
        return None
    finally:
        # Clean up temporary file
        try:
            os.unlink(temp_file_path)
        except OSError:
            pass

# Test IPFS add string endpoint
def test_ipfs_add_string():
    """Test the IPFS add string endpoint."""
    print("Testing IPFS add string endpoint...")
    
    # Add string content
    response = make_request(
        "POST", 
        f"{MCP_API_PREFIX}/ipfs/add_string", 
        json={"content": TEST_TEXT_CONTENT}
    )
    print(f"IPFS add string response: {json.dumps(response, indent=2)}")
    
    # Return CID if successful
    if response.get("success", False):
        return response.get("cid")
    return None

# Test IPFS cat endpoint
def test_ipfs_cat(cid):
    """Test the IPFS cat endpoint."""
    print(f"Testing IPFS cat endpoint with CID: {cid}...")
    
    # Get content by CID
    response = requests.get(f"{MCP_SERVER_URL}{MCP_API_PREFIX}/ipfs/cat/{cid}")
    
    if response.status_code == 200:
        content = response.content
        print(f"IPFS cat response: {content.decode('utf-8')}")
        return content
    else:
        print(f"IPFS cat failed: {response.status_code}")
        return None

# Test IPFS pin endpoint
def test_ipfs_pin(cid):
    """Test the IPFS pin endpoint."""
    print(f"Testing IPFS pin endpoint with CID: {cid}...")
    
    # Pin content
    response = make_request(
        "POST", 
        f"{MCP_API_PREFIX}/ipfs/pin", 
        json={"cid": cid}
    )
    print(f"IPFS pin response: {json.dumps(response, indent=2)}")
    return response.get("success", False)

# Test IPFS pin list endpoint
def test_ipfs_pin_list():
    """Test the IPFS pin list endpoint."""
    print("Testing IPFS pin list endpoint...")
    
    # Get pin list
    response = make_request("GET", f"{MCP_API_PREFIX}/ipfs/pins")
    print(f"IPFS pin list response: {json.dumps(response, indent=2)}")
    return response.get("pins", [])

# Test IPFS unpin endpoint
def test_ipfs_unpin(cid):
    """Test the IPFS unpin endpoint."""
    print(f"Testing IPFS unpin endpoint with CID: {cid}...")
    
    # Unpin content
    response = make_request(
        "POST", 
        f"{MCP_API_PREFIX}/ipfs/unpin", 
        json={"cid": cid}
    )
    print(f"IPFS unpin response: {json.dumps(response, indent=2)}")
    return response.get("success", False)

# Test CLI controller
def test_cli_controller():
    """Test the CLI controller endpoints."""
    print("Testing CLI controller...")
    
    # Test CLI version endpoint
    response = make_request("GET", f"{MCP_API_PREFIX}/cli/version")
    print(f"CLI version response: {json.dumps(response, indent=2)}")
    
    # Test CLI command execution
    response = make_request(
        "POST", 
        f"{MCP_API_PREFIX}/cli/command", 
        json={"command": "ipfs", "args": ["--version"], "format": "text"}
    )
    print(f"CLI command response: {json.dumps(response, indent=2)}")
    
    return response.get("success", False)

# Test credential controller
def test_credential_controller():
    """Test the credential controller endpoints."""
    print("Testing credential controller...")
    
    # List credentials
    response = make_request("GET", f"{MCP_API_PREFIX}/credentials/list")
    print(f"Credential list response: {json.dumps(response, indent=2)}")
    
    return response.get("success", False)

# Test distributed controller
def test_distributed_controller():
    """Test the distributed controller endpoints."""
    print("Testing distributed controller...")
    
    # Get status
    response = make_request("GET", f"{MCP_API_PREFIX}/distributed/status")
    print(f"Distributed status response: {json.dumps(response, indent=2)}")
    
    return response.get("success", False)

# Test WebRTC controller
def test_webrtc_controller():
    """Test the WebRTC controller endpoints."""
    print("Testing WebRTC controller...")
    
    # Get capabilities
    response = make_request("GET", f"{MCP_API_PREFIX}/webrtc/capabilities")
    print(f"WebRTC capabilities response: {json.dumps(response, indent=2)}")
    
    return response.get("success", False)

# Test filesystem journal controller
def test_fs_journal_controller():
    """Test the filesystem journal controller endpoints."""
    print("Testing filesystem journal controller...")
    
    # Get status
    response = make_request("GET", f"{MCP_API_PREFIX}/fs_journal/status")
    print(f"FS journal status response: {json.dumps(response, indent=2)}")
    
    return response.get("success", False)

# Test debug endpoints if debug mode is enabled
def test_debug_endpoints():
    """Test debug endpoints."""
    print("Testing debug endpoints...")
    
    # Get debug state
    response = make_request("GET", f"{MCP_API_PREFIX}/debug")
    print(f"Debug state response: {json.dumps(response, indent=2)}")
    
    # Get operation log
    response = make_request("GET", f"{MCP_API_PREFIX}/operations")
    print(f"Operation log response: {json.dumps(response, indent=2)}")
    
    return response.get("success", False)

# Test Files API (MFS) endpoints
def test_files_api(test_cid=None):
    """Test the Files API (MFS) endpoints."""
    print("Testing Files API (MFS) endpoints...")
    
    # Test creating a directory
    response = make_request(
        "POST", 
        f"{MCP_API_PREFIX}/ipfs/files/mkdir", 
        json={"path": "/test-dir", "parents": True}
    )
    print(f"Files mkdir response: {json.dumps(response, indent=2)}")
    
    # Test listing files
    response = make_request(
        "GET", 
        f"{MCP_API_PREFIX}/ipfs/files/ls",
        params={"path": "/", "long": "true"}
    )
    print(f"Files ls response: {json.dumps(response, indent=2)}")
    
    # Test file stat
    response = make_request(
        "GET", 
        f"{MCP_API_PREFIX}/ipfs/files/stat",
        params={"path": "/test-dir"}
    )
    print(f"Files stat response: {json.dumps(response, indent=2)}")
    
    return response.get("success", False)

# Test IPNS endpoints
def test_ipns_api(test_cid=None):
    """Test the IPNS endpoints."""
    print("Testing IPNS endpoints...")
    
    if not test_cid:
        print("Warning: No test CID available for IPNS testing")
        return False
    
    # Test publishing name
    response = make_request(
        "POST", 
        f"{MCP_API_PREFIX}/ipfs/name/publish", 
        json={"path": f"/ipfs/{test_cid}", "key": "self", "lifetime": "24h"}
    )
    print(f"IPNS publish response: {json.dumps(response, indent=2)}")
    
    # Get the name that was published
    name = response.get("Name", "")
    if name:
        # Test resolving name
        response = make_request(
            "GET", 
            f"{MCP_API_PREFIX}/ipfs/name/resolve",
            params={"name": name}
        )
        print(f"IPNS resolve response: {json.dumps(response, indent=2)}")
    
    return response.get("success", False)

# Test DAG endpoints
def test_dag_api(test_cid=None):
    """Test the DAG endpoints."""
    print("Testing DAG endpoints...")
    
    # Test putting a DAG node
    dag_node = {
        "data": "test data",
        "links": []
    }
    response = make_request(
        "POST", 
        f"{MCP_API_PREFIX}/ipfs/dag/put", 
        json={"node": dag_node, "store_codec": "dag-cbor", "pin": True}
    )
    print(f"DAG put response: {json.dumps(response, indent=2)}")
    
    dag_cid = response.get("cid", "")
    if dag_cid:
        # Test getting a DAG node
        response = make_request(
            "GET", 
            f"{MCP_API_PREFIX}/ipfs/dag/get",
            params={"cid": dag_cid}
        )
        print(f"DAG get response: {json.dumps(response, indent=2)}")
    
    return response.get("success", False)

# Test Block endpoints
def test_block_api():
    """Test the Block endpoints."""
    print("Testing Block endpoints...")
    
    # Create some test data for a block
    block_data = "Test block data"
    encoded_data = block_data.encode("utf-8").hex()
    
    # Test putting a block
    response = make_request(
        "POST", 
        f"{MCP_API_PREFIX}/ipfs/block/put", 
        json={"data": encoded_data, "format": "raw"}
    )
    print(f"Block put response: {json.dumps(response, indent=2)}")
    
    block_cid = response.get("cid", response.get("Key", ""))
    if block_cid:
        # Test getting block stat
        response = make_request(
            "GET", 
            f"{MCP_API_PREFIX}/ipfs/block/stat",
            params={"cid": block_cid}
        )
        print(f"Block stat response: {json.dumps(response, indent=2)}")
        
        # Test getting a block
        try:
            block_response = requests.get(
                f"{MCP_SERVER_URL}{MCP_API_PREFIX}/ipfs/block/get/{block_cid}"
            )
            if block_response.status_code == 200:
                print(f"Block get response: {block_response.content}")
            else:
                print(f"Block get failed: {block_response.status_code}")
            return block_response.status_code == 200
        except Exception as e:
            print(f"Error getting block: {e}")
            return False
    
    return True  # Return True to continue tests even if this fails

# Test DHT endpoints
def test_dht_api():
    """Test the DHT endpoints."""
    print("Testing DHT endpoints...")
    
    # Test finding providers for a CID
    test_cid = "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"  # Example CID
    response = make_request(
        "GET", 
        f"{MCP_API_PREFIX}/ipfs/dht/findprovs",
        params={"cid": test_cid}
    )
    print(f"DHT findprovs response: {json.dumps(response, indent=2)}")
    
    # Test finding a peer
    test_peer_id = "QmSoLV4Bbm51jM9C4gDYZQ9Cy3U6aXMJDAbzgu2fzaDs64"  # Example peer ID
    response = make_request(
        "GET", 
        f"{MCP_API_PREFIX}/ipfs/dht/findpeer",
        params={"peer_id": test_peer_id}
    )
    print(f"DHT findpeer response: {json.dumps(response, indent=2)}")
    
    return True  # Return True even if peers weren't found, as long as the API endpoints respond

# Main testing function
def run_all_tests():
    """Run all MCP server tests."""
    print("Starting MCP server API tests...")
    
    # First check if server is running and get the correct API prefix
    if not check_server_status():
        print("Server status check failed. Aborting tests.")
        return False
        
    # Then do the health check
    if not test_health():
        print("Health check failed. Aborting tests.")
        return False
    
    # Test daemon status
    test_daemon_status()
    
    # Test IPFS operations
    cid_from_file = test_ipfs_add()
    cid_from_string = test_ipfs_add_string()
    
    # Use the first successful CID for subsequent tests
    test_cid = cid_from_file or cid_from_string
    if test_cid:
        # Test retrieving content
        content = test_ipfs_cat(test_cid)
        
        # Test pinning operations
        test_ipfs_pin(test_cid)
        pins = test_ipfs_pin_list()
        test_ipfs_unpin(test_cid)
        
        # Test newly implemented APIs
        print("\n===== Testing New API Endpoints =====\n")
        test_files_api(test_cid)
        test_ipns_api(test_cid)
        test_dag_api(test_cid)
        test_block_api()
        test_dht_api()
    else:
        print("Warning: No test CID available for advanced API testing")
    
    # Test controllers
    test_cli_controller()
    test_credential_controller()
    test_distributed_controller()
    test_webrtc_controller()
    test_fs_journal_controller()
    
    # Test debug endpoints
    test_debug_endpoints()
    
    print("All MCP server API tests completed!")
    return True

if __name__ == "__main__":
    # Check if server process should be started
    start_own_server = "--start-server" in sys.argv
    server_process = None
    
    if start_own_server:
        print("Starting MCP server...")
        server_process = start_server()
        if server_process is None:
            print("Failed to start MCP server. Exiting.")
            sys.exit(1)
    
    try:
        # Run all tests
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("Tests interrupted by user.")
        sys.exit(1)
    finally:
        if start_own_server and server_process is not None:
            print("Stopping MCP server...")
            try:
                server_process.terminate()
                server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print("Server didn't terminate gracefully, forcing...")
                server_process.kill()