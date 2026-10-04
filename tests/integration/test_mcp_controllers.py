#!/usr/bin/env python3

import requests
import json
import time
import sys

class MCPTester:
    """Test class for MCP server endpoints."""
    
    def __init__(self, base_url="http://localhost:9999"):
        """Initialize the tester with the base URL of the MCP server."""
        self.base_url = base_url
        self.test_results = {}
        
    def run_test(self, endpoint, method="GET", data=None, headers=None, test_name=None):
        """Run a test on a specific endpoint."""
        if test_name is None:
            test_name = f"{method} {endpoint}"
            
        url = f"{self.base_url}{endpoint}"
        print(f"\n[TEST] {test_name}")
        print(f"Request: {method} {url}")
        
        if data:
            # Don't try to JSON serialize files or bytes
            if isinstance(data, dict) and any(
                isinstance(v, bytes) or hasattr(v, 'read') or 
                (isinstance(v, tuple) and len(v) >= 2 and hasattr(v[1], 'read'))
                for v in data.values()):
                print(f"Data: [File upload]")
            else:
                try:
                    print(f"Data: {json.dumps(data)}")
                except TypeError:
                    print(f"Data: {str(data)[:100]}")
            
        start_time = time.time()
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers)
            elif method.upper() == "POST":
                if isinstance(data, dict) and any(
                    hasattr(v, 'read') or 
                    (isinstance(v, tuple) and len(v) >= 2 and hasattr(v[1], 'read'))
                    for v in data.values()):
                    # Handle file upload
                    response = requests.post(url, files=data, headers=headers)
                elif headers and headers.get("Content-Type") == "application/json":
                    response = requests.post(url, json=data, headers=headers)
                else:
                    response = requests.post(url, data=data, headers=headers)
            elif method.upper() == "PUT":
                response = requests.put(url, json=data, headers=headers)
            elif method.upper() == "DELETE":
                response = requests.delete(url, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
                
            elapsed = time.time() - start_time
            print(f"Status: {response.status_code}")
            print(f"Time: {elapsed:.3f}s")
            
            try:
                response_data = response.json()
                print(f"Response: {json.dumps(response_data, indent=2)}")
            except ValueError:
                print(f"Response: {response.text[:500]}")
                
            # Store test result
            self.test_results[test_name] = {
                "status": response.status_code,
                "elapsed": elapsed,
                "success": 200 <= response.status_code < 300
            }
            
            return response
            
        except Exception as e:
            print(f"Error: {str(e)}")
            self.test_results[test_name] = {
                "status": None,
                "elapsed": time.time() - start_time,
                "success": False,
                "error": str(e)
            }
            return None
            
    def test_health_endpoint(self):
        """Test the health endpoint."""
        return self.run_test("/api/v0/mcp/health", "GET", test_name="Health Endpoint")
        
    def test_debug_endpoints(self):
        """Test debug endpoints."""
        self.run_test("/api/v0/mcp/debug/status", "GET", test_name="Debug Status")
        self.run_test("/api/v0/mcp/debug/config", "GET", test_name="Debug Config")
        
    def test_ipfs_endpoints(self):
        """Test IPFS controller endpoints."""
        # Test add endpoint
        test_file_path = "/tmp/test_ipfs_file.txt"
        with open(test_file_path, "w") as f:
            f.write("Test content for IPFS add")
            
        with open(test_file_path, "rb") as f:
            files = {"file": ("test.txt", f)}
            add_response = self.run_test("/api/v0/mcp/ipfs/add", "POST", data=files, test_name="IPFS Add")
        
        # Extract CID if available
        cid = None
        try:
            if add_response and add_response.status_code == 200:
                cid = add_response.json().get("cid")
        except:
            pass
            
        # Test cat endpoint if we have a CID
        if cid:
            self.run_test(f"/api/v0/mcp/ipfs/cat?cid={cid}", "GET", test_name="IPFS Cat")
            
        # Test pin endpoints
        if cid:
            self.run_test(f"/api/v0/mcp/ipfs/pin/add?cid={cid}", "POST", test_name="IPFS Pin Add")
            self.run_test("/api/v0/mcp/ipfs/pin/ls", "GET", test_name="IPFS Pin List")
            self.run_test(f"/api/v0/mcp/ipfs/pin/rm?cid={cid}", "POST", test_name="IPFS Pin Remove")
            
    def test_credential_endpoints(self):
        """Test credential controller endpoints."""
        # Test list endpoint based on actual implementation
        self.run_test("/api/v0/mcp/credentials", "GET", test_name="Credential List")
        
        # Test add S3 credentials endpoint
        s3_credential_data = {
            "name": "test-s3",
            "aws_access_key_id": "test-access-key",
            "aws_secret_access_key": "test-secret-key",
            "endpoint_url": "https://s3.example.com",
            "region": "us-west-1"
        }
        headers = {"Content-Type": "application/json"}
        self.run_test("/api/v0/mcp/credentials/s3", "POST", data=s3_credential_data, 
                     headers=headers, test_name="S3 Credential Add")
        
        # Test add Storacha credentials endpoint
        storacha_credential_data = {
            "name": "test-storacha",
            "api_token": "test-token",
            "space_did": "did:key:test"
        }
        self.run_test("/api/v0/mcp/credentials/storacha", "POST", data=storacha_credential_data, 
                     headers=headers, test_name="Storacha Credential Add")
        
        # Test remove credential endpoint
        self.run_test("/api/v0/mcp/credentials/s3/test-s3", 
                     "DELETE", test_name="Credential Remove")
        
    def test_webrtc_endpoints(self):
        """Test WebRTC controller endpoints."""
        # Test dependency check endpoint
        self.run_test("/api/v0/mcp/webrtc/check", "GET", test_name="WebRTC Check Dependencies")
        
        # Test stream endpoint with POST and proper body
        stream_data = {
            "cid": "QmTest",
            "address": "127.0.0.1",
            "port": 8080,
            "quality": "medium"
        }
        headers = {"Content-Type": "application/json"}
        self.run_test("/api/v0/mcp/webrtc/stream", "POST", data=stream_data, 
                     headers=headers, test_name="WebRTC Stream")
        
        # Test list connections endpoint
        self.run_test("/api/v0/mcp/webrtc/connections", "GET", test_name="WebRTC Connections List")
        
    def test_cli_endpoints(self):
        """Test CLI controller endpoints."""
        # Test version endpoint
        self.run_test("/api/v0/mcp/cli/version", "GET", test_name="CLI Version")
        
        # Test list pins endpoint
        self.run_test("/api/v0/mcp/cli/pins", "GET", test_name="CLI Pins List")
        
    def test_all(self):
        """Run all tests."""
        self.test_health_endpoint()
        self.test_debug_endpoints()
        self.test_ipfs_endpoints()
        self.test_credential_endpoints()
        self.test_webrtc_endpoints()
        self.test_cli_endpoints()
        
        # Print summary
        print("\n=== Test Summary ===")
        successful = 0
        failed = 0
        for name, result in self.test_results.items():
            status = "✅ PASS" if result["success"] else "❌ FAIL"
            print(f"{status} - {name}")
            if result["success"]:
                successful += 1
            else:
                failed += 1
                
        print(f"\nTotal tests: {len(self.test_results)}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        
if __name__ == "__main__":
    # Get base URL from command line if provided
    base_url = "http://localhost:9999"
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
        
    tester = MCPTester(base_url)
    tester.test_all()