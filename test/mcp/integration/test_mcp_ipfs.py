"""
Test script specifically for the MCP server IPFS controller.
This script focuses on testing the IPFS-related endpoints.
"""

import os
import time
import json
import sys
import requests
import tempfile
import random
import string

# Configuration
MCP_SERVER_URL = "http://localhost:8000"
MCP_API_PREFIX = "/api/v0/mcp"
TEST_CONTENT = "Hello, IPFS! This is a test from the MCP server test script."

def random_string(length=10):
    """Generate a random string for testing."""
    return ''.join(random.choice(string.ascii_letters) for _ in range(length))

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

def test_ipfs_endpoints():
    """Test all IPFS controller endpoints."""
    results = {
        "success": True,
        "endpoints": {},
        "errors": []
    }

    # Test health endpoint first
    print("Testing server health...")
    health = make_request("GET", f"{MCP_API_PREFIX}/health")
    if not health.get("success", False):
        print("Server health check failed. Cannot proceed with IPFS tests.")
        results["success"] = False
        results["errors"].append("Server health check failed")
        return results

    # List available endpoints
    print("Getting available IPFS endpoints...")
    endpoints = []
    try:
        # Try to get the server root to see available endpoints
        root_response = requests.get(MCP_SERVER_URL)
        if root_response.status_code == 200:
            root_data = root_response.json()
            if "endpoints" in root_data:
                endpoints = root_data["endpoints"]
                print(f"Available endpoints: {json.dumps(endpoints, indent=2)}")
    except Exception as e:
        print(f"Error getting server endpoints: {e}")

    # Test 1: Add string content
    print("\nTesting add content as string...")
    # Try different endpoint paths since we're not sure which one is correct
    for path in ["/ipfs/add-string", "/ipfs/add_string", "/ipfs/addString"]:
        full_path = f"{MCP_API_PREFIX}{path}"
        print(f"Trying endpoint: {full_path}")

        response = make_request(
            "POST",
            full_path,
            json={"content": TEST_CONTENT}
        )

        results["endpoints"][path] = {
            "success": response.get("success", False),
            "status_code": getattr(response, "status_code", None),
            "response": response
        }

        if response.get("success", False):
            print(f"Success with {path}! CID: {response.get('cid', 'unknown')}")
            test_cid = response.get("cid")
            break
    else:
        print("Could not add string content through any endpoint")
        test_cid = None

    # Test 2: Add file content
    print("\nTesting add file content...")
    # Create a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as temp_file:
        file_content = f"Test file content: {random_string(20)}"
        temp_file.write(file_content.encode())
        temp_file_path = temp_file.name

    try:
        # Try different variations of the add endpoint
        for path in ["/ipfs/add", "/ipfs/upload"]:
            full_path = f"{MCP_API_PREFIX}{path}"
            print(f"Trying endpoint: {full_path}")

            # Try with form data
            with open(temp_file_path, 'rb') as f:
                files = {'file': ('test.txt', f, 'text/plain')}
                response = requests.post(
                    f"{MCP_SERVER_URL}{full_path}",
                    files=files
                )

            success = response.status_code == 200
            results["endpoints"][path] = {
                "success": success,
                "status_code": response.status_code,
                "response": response.json() if success else None
            }

            if success:
                print(f"Success with {path}! Response: {response.json()}")
                if test_cid is None and "cid" in response.json():
                    test_cid = response.json()["cid"]
                break
        else:
            print("Failed to upload file through any endpoint")

        # Try with JSON payload
        print("\nTrying add with JSON payload...")
        for path in ["/ipfs/add", "/ipfs/add-json"]:
            full_path = f"{MCP_API_PREFIX}{path}"
            print(f"Trying endpoint: {full_path}")

            json_payload = {
                "content": file_content,
                "filename": "test.txt"
            }

            response = make_request(
                "POST",
                full_path,
                json=json_payload
            )

            results["endpoints"][f"{path} (JSON)"] = {
                "success": response.get("success", False),
                "response": response
            }

            if response.get("success", False):
                print(f"Success with {path} (JSON)! Response: {response}")
                if test_cid is None and "cid" in response:
                    test_cid = response["cid"]
                break
        else:
            print("Failed to add content with JSON payload through any endpoint")
    finally:
        # Clean up
        os.unlink(temp_file_path)

    # Test 3: If we have a CID, test getting the content
    if test_cid:
        print(f"\nTesting get content with CID: {test_cid}")

        # Try different variations of the get/cat endpoint
        for path in [f"/ipfs/cat/{test_cid}", f"/ipfs/get/{test_cid}"]:
            full_path = f"{MCP_API_PREFIX}{path}"
            print(f"Trying endpoint: {full_path}")

            try:
                response = requests.get(f"{MCP_SERVER_URL}{full_path}")

                success = response.status_code == 200
                results["endpoints"][path] = {
                    "success": success,
                    "status_code": response.status_code,
                    "content_length": len(response.content) if success else 0
                }

                if success:
                    print(f"Success with {path}! Content: {response.content.decode()[:50]}...")
                    break
            except Exception as e:
                print(f"Error with {path}: {e}")
                results["endpoints"][path] = {
                    "success": False,
                    "error": str(e)
                }
        else:
            print("Failed to get content through any endpoint")

        # Test pin operations
        print("\nTesting pin operations...")
        for path in ["/ipfs/pin", "/ipfs/pins/add"]:
            full_path = f"{MCP_API_PREFIX}{path}"
            print(f"Trying pin endpoint: {full_path}")

            response = make_request(
                "POST",
                full_path,
                json={"cid": test_cid}
            )

            results["endpoints"][path] = {
                "success": response.get("success", False),
                "response": response
            }

            if response.get("success", False):
                print(f"Successfully pinned CID with {path}")
                break
        else:
            print("Failed to pin content through any endpoint")

        # Test list pins
        print("\nTesting list pins...")
        for path in ["/ipfs/pins", "/ipfs/pin/ls"]:
            full_path = f"{MCP_API_PREFIX}{path}"
            print(f"Trying list pins endpoint: {full_path}")

            response = make_request("GET", full_path)

            results["endpoints"][path] = {
                "success": response.get("success", False),
                "response": response
            }

            if response.get("success", False):
                print(f"Successfully listed pins with {path}: {response.get('pins', [])}")
                break
        else:
            print("Failed to list pins through any endpoint")

        # Test unpin
        print("\nTesting unpin operations...")
        for path in ["/ipfs/unpin", "/ipfs/pins/remove"]:
            full_path = f"{MCP_API_PREFIX}{path}"
            print(f"Trying unpin endpoint: {full_path}")

            response = make_request(
                "POST",
                full_path,
                json={"cid": test_cid}
            )

            results["endpoints"][path] = {
                "success": response.get("success", False),
                "response": response
            }

            if response.get("success", False):
                print(f"Successfully unpinned CID with {path}")
                break
        else:
            print("Failed to unpin content through any endpoint")
    else:
        print("\nNo CID available for content retrieval and pin tests")
        results["errors"].append("No CID available for further tests")

    # Return comprehensive results
    return results

if __name__ == "__main__":
    print("Starting IPFS controller tests...")
    results = test_ipfs_endpoints()

    # Save results to file
    with open("mcp_ipfs_test_results.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\nTest Summary:")
    print(f"Overall success: {results['success']}")
    print(f"Endpoints tested: {len(results['endpoints'])}")
    successful = sum(1 for e in results["endpoints"].values() if e.get("success", False))
    print(f"Successful endpoints: {successful}")
    print(f"Failed endpoints: {len(results['endpoints']) - successful}")

    if results["errors"]:
        print("\nErrors:")
        for error in results["errors"]:
            print(f"- {error}")

    print("\nDetailed results saved to: mcp_ipfs_test_results.json")
