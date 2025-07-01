#!/usr/bin/env python3
"""
Test VSCode MCP Integration

This script tests all the endpoints needed for VSCode MCP integration:
1. /api/v0/initialize - MCP initialization endpoint
2. /api/v0/sse - Server-Sent Events endpoint (basic check only)
3. /jsonrpc - JSON-RPC endpoint for Language Server Protocol
4. /api/v0/jsonrpc - API-prefixed JSON-RPC endpoint

It verifies these critical endpoints are working properly, ensuring
that VSCode will be able to communicate with the MCP server.
"""

import json
import sys
import time
import requests
import argparse
from urllib.parse import urljoin

# ANSI colors for terminal output
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[0;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'  # No Color

def print_success(message):
    """Print success message in green."""
    print(f"{GREEN}✓ {message}{NC}")

def print_error(message):
    """Print error message in red."""
    print(f"{RED}✗ {message}{NC}")

def print_info(message):
    """Print info message in blue."""
    print(f"{BLUE}ℹ {message}{NC}")

def print_warning(message):
    """Print warning message in yellow."""
    print(f"{YELLOW}⚠ {message}{NC}")

def print_section(title):
    """Print section title."""
    print(f"\n{YELLOW}=== {title} ==={NC}")

class VSCodeMCPTester:
    """Test VSCode MCP integration endpoints."""

    def __init__(self, base_url="http://localhost:9994", api_prefix="/api/v0", timeout=5):
        """Initialize the tester with server settings."""
        self.base_url = base_url.rstrip('/')
        self.api_prefix = api_prefix
        self.timeout = timeout
        self.errors = []
        self.warnings = []

    def full_url(self, path):
        """Get full URL for a path."""
        # Handle paths with and without API prefix
        if path.startswith('/api/'):
            return f"{self.base_url}{path}"
        return f"{self.base_url}{self.api_prefix}{path}"

    def test_server_health(self):
        """Test basic server health endpoint (root only)."""
        print_section("Testing Server Health")

        try:
            # Test root endpoint
            response = requests.get(f"{self.base_url}/", timeout=self.timeout)
            if response.status_code == 200:
                print_success("Server root endpoint is accessible")
                return True
            else:
                print_error(f"Server root endpoint returned status code {response.status_code}")
                self.errors.append("Server root endpoint not accessible")
                return False

        except requests.exceptions.RequestException as e:
            print_error(f"Error connecting to server: {e}")
            self.errors.append(f"Server connection error: {e}")
            return False

    def test_initialize_endpoint(self):
        """Test the initialization endpoint needed by VSCode."""
        print_section("Testing Initialize Endpoint")

        initialize_url = self.full_url("/initialize")
        try:
            response = requests.post(initialize_url, timeout=self.timeout)
            if response.status_code == 200:
                init_data = response.json()
                print_success(f"Initialize endpoint responded successfully")

                # Verify the response structure
                if "capabilities" in init_data:
                    print_success("Response includes capabilities")
                    if "tools" in init_data["capabilities"]:
                        tools = init_data["capabilities"]["tools"]
                        print_info(f"Available tools: {', '.join(tools)}")
                    if "resources" in init_data["capabilities"]:
                        resources = init_data["capabilities"]["resources"]
                        print_info(f"Available resources: {', '.join(resources)}")
                else:
                    print_warning("Response missing capabilities section")
                    self.warnings.append("Initialize endpoint missing capabilities")

                return True
            else:
                print_error(f"Initialize endpoint returned status code {response.status_code}")
                self.errors.append("Initialize endpoint error")
                return False

        except requests.exceptions.RequestException as e:
            print_error(f"Error connecting to initialize endpoint: {e}")
            self.errors.append(f"Initialize endpoint error: {e}")
            return False

    def test_jsonrpc_endpoint(self):
        """Test the JSON-RPC endpoint needed by VSCode."""
        print_section("Testing JSON-RPC Endpoints")

        # Test both the root jsonrpc and api-prefixed jsonrpc endpoints
        endpoints = [
            "/jsonrpc",  # Root JSON-RPC
            "/api/v0/jsonrpc"  # API-prefixed JSON-RPC
        ]

        all_success = True

        for endpoint in endpoints:
            jsonrpc_url = f"{self.base_url}{endpoint}"
            print_info(f"Testing endpoint: {jsonrpc_url}")

            # Create an initialize request
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "processId": 123,
                    "rootUri": None,
                    "capabilities": {}
                }
            }

            try:
                response = requests.post(
                    jsonrpc_url,
                    json=init_request,
                    headers={"Content-Type": "application/json"},
                    timeout=self.timeout
                )

                if response.status_code == 200:
                    try:
                        result = response.json()
                        if "result" in result and "capabilities" in result["result"]:
                            print_success(f"JSON-RPC endpoint {endpoint} responded with capabilities")
                        else:
                            print_warning(f"JSON-RPC endpoint {endpoint} response missing expected structure")
                            print_info(f"Response: {json.dumps(result, indent=2)}")
                            self.warnings.append(f"JSON-RPC {endpoint} unexpected response structure")
                            all_success = False
                    except json.JSONDecodeError:
                        print_error(f"JSON-RPC endpoint {endpoint} returned invalid JSON")
                        print_info(f"Raw response: {response.text[:100]}...")
                        self.errors.append(f"JSON-RPC {endpoint} invalid JSON")
                        all_success = False
                else:
                    print_error(f"JSON-RPC endpoint {endpoint} returned status code {response.status_code}")
                    self.errors.append(f"JSON-RPC {endpoint} error status {response.status_code}")
                    all_success = False

            except requests.exceptions.RequestException as e:
                print_error(f"Error connecting to JSON-RPC endpoint {endpoint}: {e}")
                self.errors.append(f"JSON-RPC {endpoint} connection error: {e}")
                all_success = False

        return all_success

    def test_sse_endpoint(self):
        """Test the SSE endpoint (simple connectivity test)."""
        print_section("Testing SSE Endpoint")

        sse_url = self.full_url("/sse")
        print_info(f"Testing SSE endpoint: {sse_url}")

        try:
            # We can only test for a response, not stream the events
            # since we're using basic requests library
            response = requests.get(sse_url, stream=True, timeout=1)

            if response.status_code == 200:
                # Check the content type
                content_type = response.headers.get('Content-Type', '')
                if 'text/event-stream' in content_type:
                    print_success("SSE endpoint is available with correct content type")

                    # Try to get at least one event
                    try:
                        for line in response.iter_lines(decode_unicode=True, delimiter="\n\n"):
                            if line:
                                print_success("Received SSE data")
                                break
                    except Exception:
                        # We might time out, which is OK
                        pass

                    return True
                else:
                    print_warning(f"SSE endpoint has incorrect content type: {content_type}")
                    self.warnings.append("SSE wrong content type")
                    return False
            else:
                print_error(f"SSE endpoint returned status code {response.status_code}")
                self.errors.append("SSE endpoint error")
                return False

        except requests.exceptions.RequestException as e:
            print_error(f"Error connecting to SSE endpoint: {e}")
            self.errors.append(f"SSE endpoint error: {e}")
            return False

    def test_ipfs_endpoints(self):
        """Test the IPFS endpoints that VSCode would use."""
        print_section("Testing IPFS Endpoints")

        # Test the add endpoint
        add_url = self.full_url("/ipfs/add")
        test_content = "This is a test content from VS Code integration test"
        files = {
            'file': ('test.txt', test_content.encode('utf-8'), 'text/plain')
        }

        try:
            response = requests.post(add_url, files=files, timeout=self.timeout)
            if response.status_code == 200:
                add_data = response.json()
                cid = add_data.get("cid") or add_data.get("Hash")
                if cid:
                    print_success(f"Successfully added content with CID: {cid}")

                    # Now test the cat endpoint
                    cat_url = self.full_url(f"/ipfs/cat/{cid}")
                    cat_response = requests.get(cat_url, timeout=self.timeout)
                    if cat_response.status_code == 200 and cat_response.text == test_content:
                        print_success("Successfully retrieved content")
                        return True
                    else:
                        print_error(f"Error retrieving content: Status {cat_response.status_code}")
                        self.errors.append("IPFS cat endpoint error")
                        return False
                else:
                    print_error("Missing CID in add response")
                    self.errors.append("IPFS add endpoint missing CID")
                    return False
            else:
                print_error(f"IPFS add endpoint returned status code {response.status_code}")
                self.errors.append("IPFS add endpoint error")
                return False
        except requests.exceptions.RequestException as e:
            print_error(f"Error testing IPFS endpoints: {e}")
            self.errors.append(f"IPFS endpoints error: {e}")
            return False

    def run_all_tests(self):
        """Run all tests and return True if all critical tests pass."""
        print_section("VS Code MCP Integration Test")
        print_info(f"Testing server at {self.base_url}{self.api_prefix}")
        print_info(f"Timeout: {self.timeout} seconds")

        # Clear previous results
        self.errors = []
        self.warnings = []

        # Run tests - server health is critical
        if not self.test_server_health():
            print_error("Server health check failed - skipping remaining tests")
            return False

        # Run other tests
        initialize_ok = self.test_initialize_endpoint()
        jsonrpc_ok = self.test_jsonrpc_endpoint()
        sse_ok = self.test_sse_endpoint()
        ipfs_ok = self.test_ipfs_endpoints()

        # Print summary
        print_section("Test Summary")

        # Check if critical endpoints for VSCode integration are working
        critical_ok = initialize_ok and jsonrpc_ok

        if critical_ok:
            print_success("Critical VSCode integration endpoints are working!")

            if sse_ok and ipfs_ok:
                print_success("All tests passed successfully!")
            else:
                print_warning("Some non-critical tests had issues:")
                if not sse_ok:
                    print_warning("- SSE endpoint test had warnings")
                if not ipfs_ok:
                    print_warning("- IPFS endpoints test had warnings")

            return True
        else:
            print_error("Some critical tests failed:")
            if not initialize_ok:
                print_error("- Initialize endpoint test failed")
            if not jsonrpc_ok:
                print_error("- JSON-RPC endpoint test failed")

            print_warning("VSCode integration may not work correctly.")
            return False

def main():
    """Run the script with command-line arguments."""
    parser = argparse.ArgumentParser(description="Test VSCode MCP integration.")
    parser.add_argument("--host", default="localhost", help="Host name or IP")
    parser.add_argument("--port", type=int, default=9994, help="Server port")
    parser.add_argument("--api-prefix", default="/api/v0", help="API prefix")
    parser.add_argument("--timeout", type=int, default=5, help="Request timeout in seconds")
    args = parser.parse_args()

    base_url = f"http://{args.host}:{args.port}"
    tester = VSCodeMCPTester(base_url=base_url, api_prefix=args.api_prefix, timeout=args.timeout)

    success = tester.run_all_tests()
    if success:
        print_success("\nVSCode MCP integration is working!")
        return 0
    else:
        print_error("\nVSCode MCP integration tests failed.")
        print_info("Check the test results above for details on which specific endpoints failed.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
