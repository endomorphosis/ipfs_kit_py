#!/usr/bin/env python
"""
Test script to validate MCP server fixes.

This script tests that our fixes to the IPFS controller routes
have been applied successfully and that the endpoints work as expected.
"""

import os
import json
import sys
import time
import requests
import tempfile
import argparse
from typing import Dict, Any, List

# Parse command line arguments
parser = argparse.ArgumentParser(description='Test MCP server fixes')
parser.add_argument('--port', type=int, default=8001, help='Port where MCP server is running')

# Only parse args when running the script directly, not when imported by pytest
if __name__ == "__main__":
    args = parser.parse_args()
else:
    # When run under pytest, use default values
    args = parser.parse_args([])

# Configuration
MCP_SERVER_URL = f"http://localhost:{args.port}"
MCP_API_PREFIX = "/api/v0/mcp"

# Test variables
TEST_CONTENT = "Hello, IPFS! This is a test from the MCP server fix verification script."

def make_request(method, endpoint, **kwargs):
    """Make HTTP request with unified error handling."""
    url = f"{MCP_SERVER_URL}{endpoint}"

    try:
        print(f"Request: {method.upper()} {url}")
        response = getattr(requests, method.lower())(url, **kwargs)

        # Log status
        print(f"Response status: {response.status_code}")

        # Try to parse JSON if present
        if response.content:
            try:
                content = response.json()
                print(f"Response: {json.dumps(content, indent=2)}")
            except ValueError:
                if len(response.content) > 200:
                    print(f"Response text: {response.content[:200]}... (truncated)")
                else:
                    print(f"Response text: {response.content}")

        # Raise for HTTP errors
        response.raise_for_status()

        # Return JSON if possible, otherwise raw response
        return response.json() if response.content and response.headers.get('content-type', '').startswith('application/json') else response
    except requests.exceptions.RequestException as e:
        print(f"Error making {method} request to {endpoint}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            try:
                print(f"Response body: {e.response.json()}")
            except ValueError:
                print(f"Response text: {e.response.text}")
        return {"success": False, "error": str(e)}

def test_json_add():
    """Test adding content using JSON payload."""
    print("\n=== Testing JSON Add Endpoint ===")

    response = make_request(
        "POST",
        f"{MCP_API_PREFIX}/ipfs/add",
        json={"content": TEST_CONTENT, "filename": "test.txt"}
    )

    if isinstance(response, dict) and response.get("success", False):
        print(f"✅ JSON Add test passed. CID: {response.get('cid', 'N/A')}")
        return response.get("cid")
    else:
        print("❌ JSON Add test failed")
        return None

def test_form_add():
    """Test adding content using form data."""
    print("\n=== Testing Form Add Endpoint ===")

    # Send form data with content
    data = {
        "content": f"{TEST_CONTENT} via form data",
        "filename": "test_form.txt"
    }

    response = make_request(
        "POST",
        f"{MCP_API_PREFIX}/ipfs/add",
        data=data
    )

    if isinstance(response, dict) and response.get("success", False):
        print(f"✅ Form Add test passed. CID: {response.get('cid', 'N/A')}")
        return response.get("cid")
    else:
        print("❌ Form Add test failed")
        return None

def test_file_upload():
    """Test uploading a file using multipart form."""
    print("\n=== Testing File Upload Endpoint ===")

    # Create a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as temp_file:
        file_content = f"{TEST_CONTENT} from file upload at {time.time()}"
        temp_file.write(file_content.encode())
        temp_file_path = temp_file.name

    try:
        # Upload the file
        with open(temp_file_path, "rb") as f:
            files = {"file": ("test_upload.txt", f, "text/plain")}

            response = requests.post(
                f"{MCP_SERVER_URL}{MCP_API_PREFIX}/ipfs/add",
                files=files
            )

            # Print response info
            print(f"Response status: {response.status_code}")
            content = response.json() if response.content else {}
            print(f"Response: {json.dumps(content, indent=2)}")

            if response.status_code == 200 and content.get("success", False):
                print(f"✅ File Upload test passed. CID: {content.get('cid', 'N/A')}")
                return content.get("cid")
            else:
                print("❌ File Upload test failed")
                return None
    finally:
        # Clean up
        os.unlink(temp_file_path)

def test_get_content(cid):
    """Test retrieving content by CID."""
    print(f"\n=== Testing Get Content Endpoint (CID: {cid}) ===")

    if not cid:
        print("❌ No CID provided, skipping test")
        return False

    # Test /ipfs/cat/{cid} endpoint
    response = requests.get(f"{MCP_SERVER_URL}{MCP_API_PREFIX}/ipfs/cat/{cid}")

    print(f"Response status: {response.status_code}")
    if len(response.content) > 100:
        print(f"Response content: {response.content[:100]}... (truncated)")
    else:
        print(f"Response content: {response.content}")

    if response.status_code == 200 and response.content:
        print("✅ Cat Content test passed")
        success_cat = True
    else:
        print("❌ Cat Content test failed")
        success_cat = False

    # Test /ipfs/get/{cid} endpoint (alias)
    response = requests.get(f"{MCP_SERVER_URL}{MCP_API_PREFIX}/ipfs/get/{cid}")

    print(f"Response status: {response.status_code}")
    if len(response.content) > 100:
        print(f"Response content: {response.content[:100]}... (truncated)")
    else:
        print(f"Response content: {response.content}")

    if response.status_code == 200 and response.content:
        print("✅ Get Content test passed")
        success_get = True
    else:
        print("❌ Get Content test failed")
        success_get = False

    return success_cat and success_get

def test_pin_operations(cid):
    """Test pin, list pins, and unpin operations."""
    print(f"\n=== Testing Pin Operations (CID: {cid}) ===")

    if not cid:
        print("❌ No CID provided, skipping test")
        return False

    # Test /ipfs/pin endpoint
    print("\nTesting Pin operation...")
    pin_response = make_request(
        "POST",
        f"{MCP_API_PREFIX}/ipfs/pin",
        json={"cid": cid}
    )

    if isinstance(pin_response, dict) and pin_response.get("success", False):
        print("✅ Pin test passed")
        pin_success = True
    else:
        print("❌ Pin test failed")
        pin_success = False

    # Test /ipfs/pins endpoint (listing pins)
    print("\nTesting List Pins operation...")
    list_response = make_request(
        "GET",
        f"{MCP_API_PREFIX}/ipfs/pins"
    )

    if isinstance(list_response, dict) and list_response.get("success", False):
        print("✅ List Pins test passed")
        pins = list_response.get("pins", [])
        if pins:
            print(f"Found {len(pins)} pinned items")
        else:
            print("No pins found (but API call succeeded)")
        list_success = True
    else:
        print("❌ List Pins test failed")
        list_success = False

    # Test /ipfs/unpin endpoint
    print("\nTesting Unpin operation...")
    unpin_response = make_request(
        "POST",
        f"{MCP_API_PREFIX}/ipfs/unpin",
        json={"cid": cid}
    )

    if isinstance(unpin_response, dict) and unpin_response.get("success", False):
        print("✅ Unpin test passed")
        unpin_success = True
    else:
        print("❌ Unpin test failed")
        unpin_success = False

    return pin_success and list_success and unpin_success

def run_all_tests():
    """Run all tests and compile results."""
    print("Starting MCP Server Fix Verification Tests")
    results = {
        "success": True,
        "tests": {},
        "timestamp": time.time()
    }

    # Test 1: Health Check
    print("\n=== Testing Health Endpoint ===")
    health_response = make_request("GET", f"{MCP_API_PREFIX}/health")
    health_success = isinstance(health_response, dict) and health_response.get("success", False)
    results["tests"]["health"] = health_success

    if not health_success:
        print("❌ Health check failed. Server may not be running.")
        results["success"] = False
        return results
    else:
        print("✅ Health check passed")

    # Test 2: JSON Add
    cid_json = test_json_add()
    results["tests"]["json_add"] = bool(cid_json)

    # Test 3: Form Add
    cid_form = test_form_add()
    results["tests"]["form_add"] = bool(cid_form)

    # Test 4: File Upload
    cid_file = test_file_upload()
    results["tests"]["file_upload"] = bool(cid_file)

    # Use the first available CID for subsequent tests
    test_cid = cid_json or cid_form or cid_file

    # Test 5: Get Content
    get_success = test_get_content(test_cid)
    results["tests"]["get_content"] = get_success

    # Test 6: Pin Operations
    pin_success = test_pin_operations(test_cid)
    results["tests"]["pin_operations"] = pin_success

    # Calculate overall success
    results["success"] = all(results["tests"].values())

    # Print summary
    print("\n=== Test Summary ===")
    for test_name, success in results["tests"].items():
        mark = "✅" if success else "❌"
        print(f"{mark} {test_name}")

    print(f"\nOverall success: {'✅ Yes' if results['success'] else '❌ No'}")
    print(f"Tests passed: {sum(1 for s in results['tests'].values() if s)} / {len(results['tests'])}")

    # Save results to file
    with open("mcp_fix_verification_results.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\nDetailed results saved to: mcp_fix_verification_results.json")
    return results

if __name__ == "__main__":
    run_all_tests()
