#!/usr/bin/env python3
"""
Verify MCP tools functionality.
This script tests key MCP endpoints to ensure they're working properly.
"""
import sys
import json
import requests
import time

BASE_URL = "http://localhost:9994"
API_URL = f"{BASE_URL}/api/v0"

def test_endpoint(url, method="GET", data=None, expected_status=200, description=""):
    """Test an endpoint and return if it's working."""
    print(f"Testing {description}: {url}")
    try:
        if method == "GET":
            response = requests.get(url, timeout=5)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=5)
        else:
            print(f"  ❌ Unsupported method: {method}")
            return False
        
        if response.status_code == expected_status:
            print(f"  ✅ Status code: {response.status_code}")
            try:
                result = response.json()
                print(f"  Response: {json.dumps(result)[:100]}...")
                return True
            except:
                print(f"  Response: {response.text[:100]}...")
                return True
        else:
            print(f"  ❌ Unexpected status code: {response.status_code}")
            print(f"  Response: {response.text[:100]}...")
            return False
    except Exception as e:
        print(f"  ❌ Error: {str(e)}")
        return False

def test_sse_endpoint(url):
    """Test SSE endpoint."""
    print(f"Testing SSE endpoint: {url}")
    try:
        response = requests.get(url, stream=True, timeout=5)
        
        if response.status_code != 200:
            print(f"  ❌ Unexpected status code: {response.status_code}")
            return False
        
        # Check headers for SSE content type
        content_type = response.headers.get('Content-Type', '')
        if 'text/event-stream' not in content_type:
            print(f"  ❌ Not an SSE stream. Content-Type: {content_type}")
            response.close()
            return False
        
        # Try to read the first event
        print("  Waiting for initial event...")
        line_count = 0
        found_connected = False
        found_data = False
        
        for line in response.iter_lines(decode_unicode=True):
            line_count += 1
            if line:
                print(f"  Received: {line}")
                if 'event: connected' in line:
                    found_connected = True
                elif line.startswith('data:'):
                    found_data = True
            
            if found_connected and found_data:
                print("  ✅ SSE endpoint working properly")
                break
                
            if line_count > 10:
                break
        
        response.close()
        return found_connected and found_data
    except Exception as e:
        print(f"  ❌ Error: {str(e)}")
        return False

def run_tests():
    """Run all MCP tools tests."""
    results = {}
    
    # Test root endpoint
    results["root"] = test_endpoint(BASE_URL, description="Root endpoint")
    
    # Test SSE endpoints
    results["sse_root"] = test_sse_endpoint(f"{BASE_URL}/sse")
    results["sse_api"] = test_sse_endpoint(f"{API_URL}/sse")
    
    # Test IPFS endpoints
    results["ipfs_version"] = test_endpoint(f"{API_URL}/ipfs/version", description="IPFS Version")
    
    # Test Storage endpoints
    results["storage_manager"] = test_endpoint(f"{API_URL}/storage_manager/list_backends", 
                                               description="Storage backends")
    
    # Print summary
    print("\n=== Summary ===")
    all_passed = True
    for name, result in results.items():
        status = "✅ Working" if result else "❌ Failed"
        print(f"{name}: {status}")
        if not result:
            all_passed = False
    
    if all_passed:
        print("\nAll MCP tools are working correctly! 🎉")
        return 0
    else:
        print("\nSome MCP tools are not working correctly.")
        return 1

if __name__ == "__main__":
    result = run_tests()
    # Also write the results to a file for easier inspection
    with open("mcp_tools_verification.log", "w") as f:
        f.write("MCP Tools Verification Log\n")
        f.write("==========================\n\n")
        f.write(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        for name, status in results.items():
            f.write(f"{name}: {'✅ Working' if status else '❌ Failed'}\n")
        f.write("\n")
        if all(results.values()):
            f.write("All MCP tools are working correctly! 🎉\n")
        else:
            f.write("Some MCP tools are not working correctly.\n")
    sys.exit(result)
