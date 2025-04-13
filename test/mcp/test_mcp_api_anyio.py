#!/usr/bin/env python3
"""
Test script for the MCP server AnyIO implementation.
"""

import os
import sys
import time
import json
import logging
import requests
import argparse
import traceback
from requests.exceptions import ConnectionError, Timeout

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MCPAPITester:
    """Comprehensive MCP API tester for AnyIO implementation."""
    
    def __init__(self, base_url="http://localhost:9992"):
        """Initialize the API tester with a base URL."""
        self.base_url = base_url
        self.session = requests.Session()
        # Track results for reporting
        self.results = {
            "passed": [],
            "failed": [],
            "skipped": []
        }
        
    def test_endpoint(self, method, path, data=None, expected_status=200, description=None):
        """Test a single endpoint and record the result."""
        start_time = time.time()
        url = f"{self.base_url}{path}"
        method = method.lower()  # Normalize method
        result = {
            "method": method.upper(),
            "url": url,
            "path": path,
            "start_time": start_time,
            "description": description or f"{method.upper()} {path}"
        }
        
        try:
            if method == "get":
                response = self.session.get(url, timeout=5)
            elif method == "post":
                response = self.session.post(url, json=data, timeout=5)
            elif method == "put":
                response = self.session.put(url, json=data, timeout=5)
            elif method == "delete":
                response = self.session.delete(url, timeout=5)
            else:
                result["status"] = "skipped"
                result["reason"] = f"Unsupported method: {method}"
                self.results["skipped"].append(result)
                return result
                
            # Process response
            status_code = response.status_code
            result["status_code"] = status_code
            result["duration"] = time.time() - start_time
            
            try:
                result["response"] = response.json()
            except:
                result["response"] = response.text
                
            # Check if status code matches expected
            if status_code == expected_status:
                result["status"] = "passed"
                self.results["passed"].append(result)
            else:
                result["status"] = "failed"
                result["reason"] = f"Expected status {expected_status}, got {status_code}"
                self.results["failed"].append(result)
                
        except (ConnectionError, Timeout) as e:
            result["status"] = "failed"
            result["reason"] = f"Connection error: {str(e)}"
            result["duration"] = time.time() - start_time
            result["traceback"] = traceback.format_exc()
            self.results["failed"].append(result)
            
        except Exception as e:
            result["status"] = "failed"
            result["reason"] = f"Unexpected error: {str(e)}"
            result["duration"] = time.time() - start_time
            result["traceback"] = traceback.format_exc()
            self.results["failed"].append(result)
            
        return result
        
    def print_result(self, result):
        """Print a single test result in a readable format."""
        status = result["status"].upper()
        if status == "PASSED":
            status_str = f"\033[92m{status}\033[0m"  # Green
        elif status == "FAILED":
            status_str = f"\033[91m{status}\033[0m"  # Red
        else:
            status_str = f"\033[93m{status}\033[0m"  # Yellow
            
        print(f"{status_str} - {result['method']} {result['path']}")
        if "duration" in result:
            print(f"  Duration: {result['duration']:.3f}s")
        if "status_code" in result:
            print(f"  Status code: {result['status_code']}")
        if "reason" in result and result["status"] != "passed":
            print(f"  Reason: {result['reason']}")
        if "traceback" in result:
            print(f"  Traceback: {result['traceback']}")
        if "response" in result:
            # Format response based on type
            if isinstance(result["response"], dict):
                # For JSON responses, pretty-print with indentation
                response_str = json.dumps(result["response"], indent=2)
                if len(response_str) > 500:
                    response_str = response_str[:500] + "...(truncated)"
                print(f"  Response: {response_str}")
            elif isinstance(result["response"], str):
                # For string responses, truncate if too long
                response_str = result["response"]
                if len(response_str) > 500:
                    response_str = response_str[:500] + "...(truncated)"
                print(f"  Response: {response_str}")
                
        print()  # Add empty line between results
        
    def print_summary(self):
        """Print a summary of all test results."""
        total = len(self.results["passed"]) + len(self.results["failed"]) + len(self.results["skipped"])
        
        # Calculate pass rate
        pass_rate = len(self.results["passed"]) / total * 100 if total > 0 else 0
        
        # Print header
        print("\n" + "=" * 70)
        print(f"API TEST SUMMARY - {self.base_url}")
        print("=" * 70)
        
        # Print statistics
        print(f"Total endpoints tested: {total}")
        print(f"Passed: {len(self.results['passed'])} ({pass_rate:.1f}%)")
        print(f"Failed: {len(self.results['failed'])}")
        print(f"Skipped: {len(self.results['skipped'])}")
        
        if len(self.results["failed"]) > 0:
            print("\nFailed endpoints:")
            for result in self.results["failed"]:
                print(f"  - {result['method']} {result['path']} ({result.get('reason', 'No reason provided')})")
                
        print("=" * 70)
        
    def run_tests(self, print_results=True):
        """Run a comprehensive battery of tests."""
        # Test basic connectivity first
        try:
            print("Testing basic connectivity to server...")
            response = self.session.get(self.base_url, timeout=5)
            print(f"Server is reachable! Status code: {response.status_code}")
            print(f"Response: {response.text[:100]}...\n")
        except Exception as e:
            print(f"ERROR: Could not connect to server at {self.base_url}")
            print(f"Error details: {str(e)}")
            traceback.print_exc()
            return self.results

        # Define and run tests in groups
        self.test_core_endpoints()
        self.test_ipfs_endpoints()
        self.test_ipfs_cat_endpoint()  # Special test for IPFS cat endpoint
        self.test_daemon_endpoints()
        self.test_webrtc_endpoints()
        
        # Print summary
        if print_results:
            self.print_summary()
            
        return self.results
        
    def test_core_endpoints(self):
        """Test core MCP endpoints."""
        # Test health endpoint
        result = self.test_endpoint("get", "/api/v0/health", description="Health check endpoint")
        if print_immediately:
            self.print_result(result)
            
        # Test debug endpoint (if in debug mode)
        result = self.test_endpoint("get", "/api/v0/debug", description="Debug state endpoint")
        if print_immediately:
            self.print_result(result)
            
        # Test operations endpoint (if in debug mode)
        result = self.test_endpoint("get", "/api/v0/operations", description="Operations log endpoint")
        if print_immediately:
            self.print_result(result)
            
    def test_daemon_endpoints(self):
        """Test daemon management endpoints."""
        # Test daemon status endpoint
        result = self.test_endpoint("get", "/api/v0/daemon/status", description="Daemon status endpoint")
        if print_immediately:
            self.print_result(result)
            
    def test_ipfs_endpoints(self):
        """Test IPFS-related endpoints."""
        # Test IPFS version endpoint
        result = self.test_endpoint("get", "/api/v0/ipfs/version", description="IPFS version endpoint")
        if print_immediately:
            self.print_result(result)
            
        # Test IPFS ID endpoint
        result = self.test_endpoint("get", "/api/v0/ipfs/id", description="IPFS ID endpoint")
        if print_immediately:
            self.print_result(result)
            
        # Test pin operations (list pins)
        result = self.test_endpoint("get", "/api/v0/ipfs/pin/ls", description="List IPFS pins")
        if print_immediately:
            self.print_result(result)
            
    def test_ipfs_cat_endpoint(self):
        """Test IPFS cat endpoint with different methods."""
        # Known CID for a small file - the IPFS logo (or use any CID known to work)
        # CID for the IPFS logo: QmTkzDwWqPbnAh5YiV5VwcTLnGdwSNsNTn2aDxdXBFca7D
        test_cid = "QmTkzDwWqPbnAh5YiV5VwcTLnGdwSNsNTn2aDxdXBFca7D"
        
        # Method 1: GET with path parameter
        result = self.test_endpoint(
            "get", 
            f"/api/v0/ipfs/cat/{test_cid}", 
            description="IPFS cat with path parameter"
        )
        if print_immediately:
            self.print_result(result)
            
        # Method 2: GET with query parameter
        result = self.test_endpoint(
            "get", 
            f"/api/v0/ipfs/cat?arg={test_cid}", 
            description="IPFS cat with query parameter"
        )
        if print_immediately:
            self.print_result(result)
            
    def test_webrtc_endpoints(self):
        """Test WebRTC-related endpoints."""
        # Test WebRTC Check endpoint
        result = self.test_endpoint("get", "/api/v0/webrtc/check", description="WebRTC availability check")
        if print_immediately:
            self.print_result(result)
            
        # Test WebRTC Status endpoint (list active connections)
        result = self.test_endpoint("get", "/api/v0/webrtc/status", description="WebRTC connection status")
        if print_immediately:
            self.print_result(result)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test the MCP server AnyIO implementation")
    parser.add_argument("--url", default="http://localhost:9992", help="Base URL of the MCP server")
    parser.add_argument("--quiet", action="store_true", help="Only print summary, not individual results")
    args = parser.parse_args()
    
    print_immediately = not args.quiet
    
    print(f"Testing MCP server at {args.url}")
    print(f"Detailed output: {'disabled' if args.quiet else 'enabled'}")
    print("-" * 50)
    
    tester = MCPAPITester(base_url=args.url)
    results = tester.run_tests(print_results=True)
    
    # Exit with appropriate code based on test results
    if len(results["failed"]) > 0:
        sys.exit(1)
    else:
        sys.exit(0)