#!/usr/bin/env python3
"""
Advanced MCP Server Test Script

This script tests more advanced features of the MCP server:
1. CLI Controller - Test adding and retrieving content via CLI
2. WebRTC Controller - Test more advanced WebRTC operations
3. High-Level API integration - Test how MCP integrates with the high-level API
4. IPFS Core Operations - Test the IPFS operations with proper POST body
"""

import requests
import json
import time
import os
import tempfile
import sys
from typing import Dict, Any, Optional

class MCPAdvancedTester:
    """Advanced test class for MCP server features."""
    
    def __init__(self, base_url="http://localhost:9999"):
        """Initialize the tester with the base URL of the MCP server."""
        self.base_url = base_url
        self.test_results = {}
        self.temp_files = []
        
    def cleanup(self):
        """Clean up temporary files."""
        for path in self.temp_files:
            if os.path.exists(path):
                try:
                    os.remove(path)
                    print(f"Removed temporary file: {path}")
                except Exception as e:
                    print(f"Error removing {path}: {e}")
    
    def run_test(self, endpoint, method="GET", data=None, files=None, 
                headers=None, test_name=None, expected_status=200):
        """Run a test on a specific endpoint."""
        if test_name is None:
            test_name = f"{method} {endpoint}"
            
        url = f"{self.base_url}{endpoint}"
        print(f"\n[TEST] {test_name}")
        print(f"Request: {method} {url}")
        
        if data:
            if isinstance(data, dict) and not any(isinstance(v, (bytes, bytearray)) for v in data.values()):
                try:
                    print(f"Data: {json.dumps(data)}")
                except:
                    print(f"Data: [Complex data structure]")
            else:
                print(f"Data: [Binary or complex data]")
                
        start_time = time.time()
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers)
            elif method.upper() == "POST":
                if files:
                    response = requests.post(url, files=files, headers=headers)
                elif headers and headers.get("Content-Type") == "application/json":
                    response = requests.post(url, json=data, headers=headers)
                else:
                    response = requests.post(url, data=data, headers=headers)
            elif method.upper() == "PUT":
                if headers and headers.get("Content-Type") == "application/json":
                    response = requests.put(url, json=data, headers=headers)
                else:
                    response = requests.put(url, data=data, headers=headers)
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
            except:
                print(f"Response: {response.text[:500]}")
                
            # Store test result
            success = response.status_code == expected_status
            self.test_results[test_name] = {
                "status": response.status_code,
                "elapsed": elapsed,
                "success": success,
                "expected_status": expected_status
            }
            
            return response
            
        except Exception as e:
            print(f"Error: {str(e)}")
            self.test_results[test_name] = {
                "status": None,
                "elapsed": time.time() - start_time,
                "success": False,
                "error": str(e),
                "expected_status": expected_status
            }
            return None
    
    def test_cli_add_content(self):
        """Test adding content via CLI controller."""
        print("\n=== Testing CLI Add Content ===")
        
        # Create a temporary file with test content
        content = "Test content for CLI add operation - " + str(time.time())
        fd, temp_path = tempfile.mkstemp(prefix="mcp_test_", suffix=".txt")
        os.close(fd)
        
        with open(temp_path, "w") as f:
            f.write(content)
        
        self.temp_files.append(temp_path)
        
        # Read the file content
        with open(temp_path, "rb") as f:
            file_content = f.read()
        
        # Create CLI add command with the required content field
        command_data = {
            "command": "add",
            "args": [temp_path],
            "params": {"wrap-with-directory": False, "pin": True},
            "format": "json",
            "content": content  # Add the required content field
        }
        
        headers = {"Content-Type": "application/json"}
        response = self.run_test("/api/v0/mcp/cli/add", "POST", 
                               data=command_data, headers=headers, 
                               test_name="CLI Add Content")
        
        if response and response.status_code == 200:
            result = response.json()
            if result.get("success") and result.get("result"):
                cid = None
                if isinstance(result["result"], dict) and "Hash" in result["result"]:
                    cid = result["result"]["Hash"]
                elif isinstance(result["result"], str):
                    # Try to parse JSON string result
                    try:
                        result_obj = json.loads(result["result"])
                        if isinstance(result_obj, dict) and "Hash" in result_obj:
                            cid = result_obj["Hash"]
                    except:
                        pass
                
                if cid:
                    print(f"Successfully added content with CID: {cid}")
                    # Test retrieving the content
                    self.test_cli_cat_content(cid)
                    return cid
                else:
                    print("Add operation succeeded but CID not found in response")
            else:
                print(f"Add operation failed: {result.get('error', 'Unknown error')}")
        else:
            print("Add operation failed: No valid response")
        
        return None
    
    def test_cli_cat_content(self, cid):
        """Test retrieving content via CLI controller."""
        print(f"\n=== Testing CLI Cat Content for CID: {cid} ===")
        
        # Create CLI cat command
        command_data = {
            "command": "cat",
            "args": [cid],
            "params": {},
            "format": "text"
        }
        
        headers = {"Content-Type": "application/json"}
        response = self.run_test("/api/v0/mcp/cli/cat", "POST", 
                               data=command_data, headers=headers, 
                               test_name=f"CLI Cat Content: {cid}")
        
        if response and response.status_code == 200:
            result = response.json()
            if result.get("success") and result.get("result"):
                print(f"Successfully retrieved content")
                return True
            else:
                print(f"Cat operation failed: {result.get('error', 'Unknown error')}")
        else:
            print("Cat operation failed: No valid response")
        
        return False
    
    def test_webrtc_operations(self):
        """Test advanced WebRTC operations."""
        print("\n=== Testing Advanced WebRTC Operations ===")
        
        # 1. First check if WebRTC is available
        response = self.run_test("/api/v0/mcp/webrtc/check", "GET", 
                               test_name="WebRTC Check Dependencies")
        
        if not response or response.status_code != 200:
            print("WebRTC dependency check failed, skipping further tests")
            return False
        
        result = response.json()
        if not result.get("success") or not result.get("webrtc_available"):
            print("WebRTC is not available, skipping further tests")
            return False
        
        # 2. Create a test file to stream
        content = "Test content for WebRTC streaming - " + str(time.time())
        fd, temp_path = tempfile.mkstemp(prefix="mcp_webrtc_", suffix=".txt")
        os.close(fd)
        
        with open(temp_path, "w") as f:
            f.write(content)
        
        self.temp_files.append(temp_path)
        
        # 3. Add the file to IPFS
        files = {"file": ("test.txt", open(temp_path, "rb"))}
        add_response = self.run_test("/api/v0/mcp/ipfs/add", "POST", 
                                   files=files, test_name="Add File for WebRTC")
        
        if not add_response or add_response.status_code != 200:
            print("Failed to add file for WebRTC streaming, skipping further tests")
            return False
        
        add_result = add_response.json()
        cid = add_result.get("cid")
        
        if not cid:
            print("Failed to get CID from add response, skipping further tests")
            return False
        
        # 4. Start a WebRTC stream
        stream_data = {
            "cid": cid,
            "address": "127.0.0.1",
            "port": 8090,  # Different port to avoid conflicts
            "quality": "medium"
        }
        
        headers = {"Content-Type": "application/json"}
        stream_response = self.run_test("/api/v0/mcp/webrtc/stream", "POST", 
                                      data=stream_data, headers=headers, 
                                      test_name=f"WebRTC Stream: {cid}")
        
        if not stream_response or stream_response.status_code != 200:
            print("Failed to start WebRTC stream, skipping further tests")
            return False
        
        stream_result = stream_response.json()
        server_id = stream_result.get("server_id")
        
        if not server_id:
            print("Failed to get server ID from stream response, skipping further tests")
            return False
        
        # 5. List WebRTC connections
        conn_response = self.run_test("/api/v0/mcp/webrtc/connections", "GET", 
                                    test_name="WebRTC List Connections")
        
        # 6. Stop the WebRTC stream
        stop_response = self.run_test(f"/api/v0/mcp/webrtc/stream/stop/{server_id}", 
                                   "POST", test_name=f"WebRTC Stop Stream: {server_id}")
        
        if not stop_response or stop_response.status_code != 200:
            print(f"Failed to stop WebRTC stream: {server_id}")
        
        return True
    
    def test_ipfs_pin_operations(self):
        """Test IPFS pin operations with proper POST body."""
        print("\n=== Testing IPFS Pin Operations ===")
        
        # 1. Create a test file to pin
        content = "Test content for IPFS pin operations - " + str(time.time())
        fd, temp_path = tempfile.mkstemp(prefix="mcp_pin_", suffix=".txt")
        os.close(fd)
        
        with open(temp_path, "w") as f:
            f.write(content)
        
        self.temp_files.append(temp_path)
        
        # 2. Add the file to IPFS
        files = {"file": ("test.txt", open(temp_path, "rb"))}
        add_response = self.run_test("/api/v0/mcp/ipfs/add", "POST", 
                                   files=files, test_name="Add File for Pin Test")
        
        if not add_response or add_response.status_code != 200:
            print("Failed to add file for pin test, skipping further tests")
            return False
        
        add_result = add_response.json()
        cid = add_result.get("cid")
        
        if not cid:
            print("Failed to get CID from add response, skipping further tests")
            return False
        
        # 3. Test pin add with proper POST body
        pin_data = {"cid": cid}
        headers = {"Content-Type": "application/json"}
        
        pin_response = self.run_test("/api/v0/mcp/ipfs/pin/add", "POST", 
                                   data=pin_data, headers=headers, 
                                   test_name=f"IPFS Pin Add: {cid}")
        
        if not pin_response or pin_response.status_code != 200:
            print(f"Failed to pin content: {cid}")
        
        # 4. Test pin list
        ls_response = self.run_test("/api/v0/mcp/ipfs/pin/ls", "GET", 
                                  test_name="IPFS Pin List")
        
        # 5. Test pin remove with proper POST body
        unpin_data = {"cid": cid}
        unpin_response = self.run_test("/api/v0/mcp/ipfs/pin/rm", "POST", 
                                     data=unpin_data, headers=headers, 
                                     test_name=f"IPFS Pin Remove: {cid}")
        
        if not unpin_response or unpin_response.status_code != 200:
            print(f"Failed to unpin content: {cid}")
        
        return True
    
    def test_get_debug_endpoints(self):
        """Test debug endpoints with alternate paths."""
        print("\n=== Testing Debug Endpoints ===")
        
        # Test alternate paths for debug endpoints
        self.run_test("/api/v0/mcp/debug", "GET", test_name="Debug Root")
        self.run_test("/api/v0/mcp/operations", "GET", test_name="Operations Log")
        self.run_test("/api/v0/mcp/daemon/status", "GET", test_name="Daemon Status")
        
        return True
        
    def test_fs_journal_controller(self):
        """Test Filesystem Journal controller endpoints."""
        print("\n=== Testing Filesystem Journal Controller ===")
        
        # 1. First try to get status (will likely fail if not enabled)
        status_response = self.run_test(
            "/api/v0/mcp/fs-journal/status", 
            "GET",
            test_name="FS Journal Status",
            expected_status=400  # Expect 400 since it's probably not enabled yet
        )
        
        # 2. Enable journaling
        enable_data = {
            "journal_path": "/tmp/mcp_test_journal",
            "checkpoint_interval": 10,
            "wal_enabled": True
        }
        headers = {"Content-Type": "application/json"}
        enable_response = self.run_test(
            "/api/v0/mcp/fs-journal/enable",
            "POST",
            data=enable_data,
            headers=headers,
            test_name="Enable FS Journal"
        )
        
        # If enabling failed (likely due to unsupported feature), skip remaining tests
        if not enable_response or enable_response.status_code != 200:
            print("Filesystem Journal not supported or failed to enable, skipping further tests")
            return False
        
        # 3. Create a directory
        mkdir_data = {
            "path": "/test_dir",
            "parents": True
        }
        mkdir_response = self.run_test(
            "/api/v0/mcp/fs-journal/mkdir",
            "POST",
            data=mkdir_data,
            headers=headers,
            test_name="FS Journal Mkdir"
        )
        
        # 4. Write a file
        write_data = {
            "path": "/test_dir/test_file.txt",
            "content": "This is a test file created by the MCP test suite."
        }
        write_response = self.run_test(
            "/api/v0/mcp/fs-journal/write",
            "POST",
            data=write_data,
            headers=headers,
            test_name="FS Journal Write"
        )
        
        # 5. List directory
        ls_response = self.run_test(
            "/api/v0/mcp/fs-journal/ls?path=/test_dir",
            "GET",
            test_name="FS Journal List Directory"
        )
        
        # 6. Read file
        read_response = self.run_test(
            "/api/v0/mcp/fs-journal/read?path=/test_dir/test_file.txt",
            "GET",
            test_name="FS Journal Read"
        )
        
        # 7. Create a checkpoint
        checkpoint_response = self.run_test(
            "/api/v0/mcp/fs-journal/checkpoint",
            "POST",
            headers=headers,
            test_name="FS Journal Create Checkpoint"
        )
        
        # 8. List transactions
        transactions_response = self.run_test(
            "/api/v0/mcp/fs-journal/transactions",
            "GET",
            test_name="FS Journal List Transactions"
        )
        
        # 9. Export filesystem
        export_data = {
            "path": "/test_dir"
        }
        export_response = self.run_test(
            "/api/v0/mcp/fs-journal/export",
            "POST",
            data=export_data,
            headers=headers,
            test_name="FS Journal Export"
        )
        
        return True
    
    def test_cli_add_content_multipart(self):
        """Test adding content via CLI controller using multipart form data."""
        print("\n=== Testing CLI Add Content (Multipart) ===")
        
        # Create a temporary file with test content
        content = "Test content for CLI add operation (multipart) - " + str(time.time())
        fd, temp_path = tempfile.mkstemp(prefix="mcp_multipart_", suffix=".txt")
        os.close(fd)
        
        with open(temp_path, "w") as f:
            f.write(content)
        
        self.temp_files.append(temp_path)
        
        # Create multipart form data
        files = {
            "file": ("test.txt", open(temp_path, "rb")),
            "command": (None, "add"),
            "format": (None, "json")
        }
        
        response = self.run_test("/api/v0/mcp/cli/add", "POST", 
                              files=files,
                              test_name="CLI Add Content (Multipart)")
        
        if response and response.status_code == 200:
            result = response.json()
            if result.get("success") and result.get("result"):
                cid = None
                if isinstance(result["result"], dict) and "Hash" in result["result"]:
                    cid = result["result"]["Hash"]
                elif isinstance(result["result"], str):
                    # Try to parse JSON string result
                    try:
                        result_obj = json.loads(result["result"])
                        if isinstance(result_obj, dict) and "Hash" in result_obj:
                            cid = result_obj["Hash"]
                    except:
                        pass
                
                if cid:
                    print(f"Successfully added content with CID: {cid}")
                    # Test retrieving the content
                    self.test_cli_cat_content(cid)
                    return cid
                else:
                    print("Add operation succeeded but CID not found in response")
            else:
                print(f"Add operation failed: {result.get('error', 'Unknown error')}")
        else:
            print("Add operation failed: No valid response")
        
        return None
            
    def run_all_advanced_tests(self):
        """Run all advanced tests."""
        try:
            print("\n=== Running Advanced MCP Server Tests ===")
            
            # Test CLI operations
            self.test_cli_add_content()
            self.test_cli_add_content_multipart()
            
            # Test WebRTC operations
            self.test_webrtc_operations()
            
            # Test IPFS pin operations
            self.test_ipfs_pin_operations()
            
            # Test debug endpoints
            self.test_get_debug_endpoints()
            
            # Test Filesystem Journal controller
            self.test_fs_journal_controller()
            
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
            print(f"Success rate: {successful/len(self.test_results):.1%}")
            
        finally:
            # Clean up temporary files
            self.cleanup()

if __name__ == "__main__":
    # Get base URL from command line if provided
    base_url = "http://localhost:9999" if len(sys.argv) < 2 else sys.argv[1]
    
    tester = MCPAdvancedTester(base_url)
    tester.run_all_advanced_tests()