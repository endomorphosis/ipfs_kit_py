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
import pytest
from typing import Dict, Any, List

# Configuration
DEFAULT_PORT = 8001


# Create a fixture for server configuration
@pytest.fixture
def server_config(request):
    """Return server configuration with port."""
    # Check if running under pytest with custom port
    port = getattr(request.config, "getoption", lambda x: None)("--port") or DEFAULT_PORT
    return {
        "url": f"http://localhost:{port}",
        "api_prefix": "/api/v0/mcp"
    }


# Test content
TEST_CONTENT = "Hello, IPFS! This is a test from the MCP server fix verification script."


def make_request(server_config, method, endpoint, **kwargs):
    """Make HTTP request with unified error handling."""
    url = f"{server_config['url']}{endpoint}"

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


class TestMCPFixes:
    """Test class for MCP server fixes."""

    @pytest.mark.skip(reason="Requires running MCP server")
    def test_json_add(self, server_config):
        """Test adding content using JSON payload."""
        print("\n=== Testing JSON Add Endpoint ===")

        response = make_request(
            server_config,
            "POST",
            f"{server_config['api_prefix']}/ipfs/add",
            json={"content": TEST_CONTENT, "filename": "test.txt"}
        )

        assert isinstance(response, dict)
        assert response.get("success", False)
        cid = response.get("cid")
        assert cid is not None
        print(f"✅ JSON Add test passed. CID: {cid}")
        return cid

    @pytest.mark.skip(reason="Requires running MCP server")
    def test_form_add(self, server_config):
        """Test adding content using form data."""
        print("\n=== Testing Form Add Endpoint ===")

        # Send form data with content
        data = {
            "content": f"{TEST_CONTENT} via form data",
            "filename": "test_form.txt"
        }

        response = make_request(
            server_config,
            "POST",
            f"{server_config['api_prefix']}/ipfs/add",
            data=data
        )

        assert isinstance(response, dict)
        assert response.get("success", False)
        cid = response.get("cid")
        assert cid is not None
        print(f"✅ Form Add test passed. CID: {cid}")
        return cid

    @pytest.mark.skip(reason="Requires running MCP server")
    def test_file_upload(self, server_config):
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
                    f"{server_config['url']}{server_config['api_prefix']}/ipfs/add",
                    files=files
                )

                # Print response info
                print(f"Response status: {response.status_code}")
                content = response.json() if response.content else {}
                print(f"Response: {json.dumps(content, indent=2)}")

                assert response.status_code == 200
                assert content.get("success", False)
                cid = content.get("cid")
                assert cid is not None
                print(f"✅ File Upload test passed. CID: {cid}")
                return cid
        finally:
            # Clean up
            os.unlink(temp_file_path)

    @pytest.mark.skip(reason="Requires running MCP server")
    def test_get_content(self, server_config):
        """Test retrieving content by CID."""
        # First add some content to get a CID
        cid = self.test_json_add(server_config)
        print(f"\n=== Testing Get Content Endpoint (CID: {cid}) ===")

        # Test /ipfs/cat/{cid} endpoint
        response = requests.get(f"{server_config['url']}{server_config['api_prefix']}/ipfs/cat/{cid}")

        print(f"Response status: {response.status_code}")
        if len(response.content) > 100:
            print(f"Response content: {response.content[:100]}... (truncated)")
        else:
            print(f"Response content: {response.content}")

        assert response.status_code == 200
        assert response.content
        print("✅ Cat Content test passed")

        # Test /ipfs/get/{cid} endpoint (alias)
        response = requests.get(f"{server_config['url']}{server_config['api_prefix']}/ipfs/get/{cid}")

        print(f"Response status: {response.status_code}")
        if len(response.content) > 100:
            print(f"Response content: {response.content[:100]}... (truncated)")
        else:
            print(f"Response content: {response.content}")

        assert response.status_code == 200
        assert response.content
        print("✅ Get Content test passed")

    @pytest.mark.skip(reason="Requires running MCP server")
    def test_pin_operations(self, server_config):
        """Test pin, list pins, and unpin operations."""
        # First add some content to get a CID
        cid = self.test_json_add(server_config)
        print(f"\n=== Testing Pin Operations (CID: {cid}) ===")

        # Test /ipfs/pin endpoint
        print("\nTesting Pin operation...")
        pin_response = make_request(
            server_config,
            "POST",
            f"{server_config['api_prefix']}/ipfs/pin",
            json={"cid": cid}
        )

        assert isinstance(pin_response, dict)
        assert pin_response.get("success", False)
        print("✅ Pin test passed")

        # Test /ipfs/pins endpoint (listing pins)
        print("\nTesting List Pins operation...")
        list_response = make_request(
            server_config,
            "GET",
            f"{server_config['api_prefix']}/ipfs/pins"
        )

        assert isinstance(list_response, dict)
        assert list_response.get("success", False)
        pins = list_response.get("pins", [])
        if pins:
            print(f"Found {len(pins)} pinned items")
        else:
            print("No pins found (but API call succeeded)")
        print("✅ List Pins test passed")

        # Test /ipfs/unpin endpoint
        print("\nTesting Unpin operation...")
        unpin_response = make_request(
            server_config,
            "POST",
            f"{server_config['api_prefix']}/ipfs/unpin",
            json={"cid": cid}
        )

        assert isinstance(unpin_response, dict)
        assert unpin_response.get("success", False)
        print("✅ Unpin test passed")

    @pytest.mark.skip(reason="Requires running MCP server")
    def test_health(self, server_config):
        """Test health endpoint."""
        print("\n=== Testing Health Endpoint ===")
        health_response = make_request(server_config, "GET", f"{server_config['api_prefix']}/health")

        assert isinstance(health_response, dict)
        assert health_response.get("success", False)
        print("✅ Health check passed")


# Add pytest command line option for port
def pytest_addoption(parser):
    parser.addoption("--port", action="store", default=DEFAULT_PORT, help="Port where MCP server is running")


# For direct execution of the script (not through pytest)
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Test MCP server fixes')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT, help='Port where MCP server is running')
    # Only parse args when running the script directly, not when imported by pytest
    if __name__ == "__main__":
        args = parser.parse_args()
    else:
        # When run under pytest, use default values
        args = parser.parse_args([])

    server_config = {
        "url": f"http://localhost:{args.port}",
        "api_prefix": "/api/v0/mcp"
    }

    # Create an instance of our test class
    tester = TestMCPFixes()

    # Run the tests manually
    print("Starting MCP Server Fix Verification Tests")
    results = {
        "success": True,
        "tests": {},
        "timestamp": time.time()
    }

    try:
        tester.test_health(server_config)
        results["tests"]["health"] = True
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        results["tests"]["health"] = False
        results["success"] = False

    if results["tests"].get("health", False):
        # Continue with other tests only if health check passes
        try:
            cid_json = tester.test_json_add(server_config)
            results["tests"]["json_add"] = True
        except Exception as e:
            print(f"❌ JSON Add test failed: {e}")
            results["tests"]["json_add"] = False
            results["success"] = False

        try:
            tester.test_form_add(server_config)
            results["tests"]["form_add"] = True
        except Exception as e:
            print(f"❌ Form Add test failed: {e}")
            results["tests"]["form_add"] = False
            results["success"] = False

        try:
            tester.test_file_upload(server_config)
            results["tests"]["file_upload"] = True
        except Exception as e:
            print(f"❌ File Upload test failed: {e}")
            results["tests"]["file_upload"] = False
            results["success"] = False

        try:
            tester.test_get_content(server_config)
            results["tests"]["get_content"] = True
        except Exception as e:
            print(f"❌ Get Content test failed: {e}")
            results["tests"]["get_content"] = False
            results["success"] = False

        try:
            tester.test_pin_operations(server_config)
            results["tests"]["pin_operations"] = True
        except Exception as e:
            print(f"❌ Pin Operations test failed: {e}")
            results["tests"]["pin_operations"] = False
            results["success"] = False

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
