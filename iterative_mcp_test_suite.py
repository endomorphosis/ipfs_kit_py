#!/usr/bin/env python3
"""
Comprehensive Iterative Test Suite for Modern Hybrid MCP Dashboard

This test suite validates the integration of:
1. Light initialization
2. Bucket-based virtual filesystem
3. ~/.ipfs_kit/ state management
4. JSON RPC MCP protocol
5. Refactored modular architecture
6. All original MCP functionality

Tests are designed to be run iteratively to ensure each feature works correctly.
"""

import asyncio
import json
import requests
import sys
import time
from pathlib import Path
from typing import Dict, Any, List

# Test configuration
TEST_HOST = "127.0.0.1"
TEST_PORT = 8899
BASE_URL = f"http://{TEST_HOST}:{TEST_PORT}"

class ModernMCPTester:
    """Comprehensive test suite for modern hybrid MCP dashboard."""
    
    def __init__(self):
        self.base_url = BASE_URL
        self.test_results = []
        self.data_dir = Path("~/.ipfs_kit").expanduser()
    
    def log_test(self, test_name: str, passed: bool, details: str = ""):
        """Log test result."""
        status = "✅ PASS" if passed else "❌ FAIL"
        result = {
            "test": test_name,
            "passed": passed,
            "details": details,
            "timestamp": time.time()
        }
        self.test_results.append(result)
        print(f"{status}: {test_name}")
        if details:
            print(f"    Details: {details}")
    
    def test_server_connectivity(self) -> bool:
        """Test 1: Basic server connectivity."""
        try:
            response = requests.get(f"{self.base_url}/", timeout=5)
            if response.status_code == 200 and "Modern Hybrid MCP Dashboard" in response.text:
                self.log_test("Server Connectivity", True, f"Server responding on port {TEST_PORT}")
                return True
            else:
                self.log_test("Server Connectivity", False, f"Unexpected response: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Server Connectivity", False, f"Connection failed: {e}")
            return False
    
    def test_mcp_protocol_init(self) -> bool:
        """Test 2: MCP protocol initialization."""
        try:
            payload = {
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}}
                }
            }
            response = requests.post(f"{self.base_url}/mcp/initialize", 
                                   json=payload, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if "protocolVersion" in data and "capabilities" in data:
                    self.log_test("MCP Protocol Init", True, "MCP handshake successful")
                    return True
            
            self.log_test("MCP Protocol Init", False, f"Invalid response: {response.text}")
            return False
        except Exception as e:
            self.log_test("MCP Protocol Init", False, f"Error: {e}")
            return False
    
    def test_mcp_tools_discovery(self) -> bool:
        """Test 3: MCP tools discovery and registration."""
        try:
            payload = {"method": "tools/list", "params": {}}
            response = requests.post(f"{self.base_url}/mcp/tools/list", 
                                   json=payload, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                tools = data.get("tools", [])
                
                expected_tools = [
                    "list_files", "read_file", "write_file",  # Original tools
                    "daemon_status", "list_backends", "list_buckets", "system_metrics",  # Restored tools
                    "bucket_create", "bucket_delete"  # Modern bucket tools
                ]
                
                found_tools = [tool["name"] for tool in tools]
                missing_tools = [tool for tool in expected_tools if tool not in found_tools]
                
                if not missing_tools:
                    self.log_test("MCP Tools Discovery", True, f"Found all {len(tools)} expected tools")
                    return True
                else:
                    self.log_test("MCP Tools Discovery", False, f"Missing tools: {missing_tools}")
                    return False
            
            self.log_test("MCP Tools Discovery", False, f"Request failed: {response.status_code}")
            return False
        except Exception as e:
            self.log_test("MCP Tools Discovery", False, f"Error: {e}")
            return False
    
    def test_filesystem_state_management(self) -> bool:
        """Test 4: ~/.ipfs_kit/ filesystem state management."""
        try:
            # Test that we can read from the actual filesystem state
            if not self.data_dir.exists():
                self.log_test("Filesystem State Management", False, "~/.ipfs_kit/ directory not found")
                return False
            
            # Check key directories exist
            required_dirs = ["buckets", "backends", "services"]
            missing_dirs = []
            
            for dir_name in required_dirs:
                dir_path = self.data_dir / dir_name
                if not dir_path.exists():
                    missing_dirs.append(dir_name)
            
            if missing_dirs:
                self.log_test("Filesystem State Management", False, f"Missing directories: {missing_dirs}")
                return False
            
            self.log_test("Filesystem State Management", True, "All required state directories present")
            return True
            
        except Exception as e:
            self.log_test("Filesystem State Management", False, f"Error: {e}")
            return False
    
    def test_bucket_vfs_operations(self) -> bool:
        """Test 5: Bucket-based virtual filesystem operations."""
        try:
            # Test list_buckets tool
            payload = {"method": "list_buckets", "params": {}}
            response = requests.post(f"{self.base_url}/mcp/tools/call", 
                                   json=payload, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                result = data.get("result", [])
                
                if isinstance(result, list) and len(result) > 0:
                    # Check if we have both parquet and directory buckets
                    bucket_types = set(bucket.get("type") for bucket in result)
                    
                    if "parquet" in bucket_types or "directory" in bucket_types:
                        self.log_test("Bucket VFS Operations", True, 
                                    f"Found {len(result)} buckets with types: {bucket_types}")
                        return True
                    else:
                        self.log_test("Bucket VFS Operations", False, "No valid bucket types found")
                        return False
                else:
                    self.log_test("Bucket VFS Operations", False, "No buckets found")
                    return False
            
            self.log_test("Bucket VFS Operations", False, f"Request failed: {response.status_code}")
            return False
        except Exception as e:
            self.log_test("Bucket VFS Operations", False, f"Error: {e}")
            return False
    
    def test_backend_management(self) -> bool:
        """Test 6: Backend management through filesystem state."""
        try:
            # Test list_backends tool
            payload = {"method": "list_backends", "params": {}}
            response = requests.post(f"{self.base_url}/mcp/tools/call", 
                                   json=payload, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                result = data.get("result", [])
                
                if isinstance(result, list) and len(result) > 0:
                    # Verify backend structure
                    for backend in result:
                        if not all(key in backend for key in ["name", "type", "status", "path"]):
                            self.log_test("Backend Management", False, "Invalid backend structure")
                            return False
                    
                    self.log_test("Backend Management", True, 
                                f"Found {len(result)} configured backends")
                    return True
                else:
                    self.log_test("Backend Management", False, "No backends found")
                    return False
            
            self.log_test("Backend Management", False, f"Request failed: {response.status_code}")
            return False
        except Exception as e:
            self.log_test("Backend Management", False, f"Error: {e}")
            return False
    
    def test_daemon_status_monitoring(self) -> bool:
        """Test 7: Daemon status monitoring from state files."""
        try:
            # Test daemon_status tool
            payload = {"method": "daemon_status", "params": {}}
            response = requests.post(f"{self.base_url}/mcp/tools/call", 
                                   json=payload, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                result = data.get("result", {})
                
                required_fields = ["ipfs", "mcp_server", "services", "timestamp"]
                if all(field in result for field in required_fields):
                    self.log_test("Daemon Status Monitoring", True, 
                                f"Status: IPFS={result['ipfs']}, MCP={result['mcp_server']}")
                    return True
                else:
                    self.log_test("Daemon Status Monitoring", False, "Missing status fields")
                    return False
            
            self.log_test("Daemon Status Monitoring", False, f"Request failed: {response.status_code}")
            return False
        except Exception as e:
            self.log_test("Daemon Status Monitoring", False, f"Error: {e}")
            return False
    
    def test_rest_api_endpoints(self) -> bool:
        """Test 8: REST API endpoints for dashboard integration."""
        try:
            endpoints = [
                ("/api/system/overview", "System Overview"),
                ("/api/backends", "Backends API"),
                ("/api/buckets", "Buckets API"), 
                ("/api/services", "Services API"),
                ("/api/metrics", "Metrics API")
            ]
            
            failed_endpoints = []
            
            for endpoint, name in endpoints:
                try:
                    response = requests.get(f"{self.base_url}{endpoint}", timeout=5)
                    if response.status_code != 200:
                        failed_endpoints.append(f"{name} ({response.status_code})")
                except Exception as e:
                    failed_endpoints.append(f"{name} (error: {e})")
            
            if not failed_endpoints:
                self.log_test("REST API Endpoints", True, f"All {len(endpoints)} endpoints working")
                return True
            else:
                self.log_test("REST API Endpoints", False, f"Failed: {failed_endpoints}")
                return False
                
        except Exception as e:
            self.log_test("REST API Endpoints", False, f"Error: {e}")
            return False
    
    def test_system_metrics(self) -> bool:
        """Test 9: System metrics with light dependencies."""
        try:
            # Test system_metrics tool
            payload = {"method": "system_metrics", "params": {}}
            response = requests.post(f"{self.base_url}/mcp/tools/call", 
                                   json=payload, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                result = data.get("result", {})
                
                required_fields = ["cpu", "memory", "disk", "timestamp"]
                if all(field in result for field in required_fields):
                    cpu_percent = result["cpu"].get("percent", 0)
                    memory_percent = result["memory"].get("percent", 0)
                    
                    self.log_test("System Metrics", True, 
                                f"CPU: {cpu_percent}%, Memory: {memory_percent}%")
                    return True
                else:
                    self.log_test("System Metrics", False, "Missing metrics fields")
                    return False
            
            self.log_test("System Metrics", False, f"Request failed: {response.status_code}")
            return False
        except Exception as e:
            self.log_test("System Metrics", False, f"Error: {e}")
            return False
    
    def test_file_operations_with_buckets(self) -> bool:
        """Test 10: File operations with bucket support."""
        try:
            test_bucket = "test-iterative-operations"
            test_content = "Test content for iterative validation"
            test_file = "test_file.txt"
            
            # Test write_file with bucket
            payload = {
                "method": "write_file",
                "params": {
                    "path": test_file,
                    "content": test_content,
                    "bucket": test_bucket
                }
            }
            response = requests.post(f"{self.base_url}/mcp/tools/call", 
                                   json=payload, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("error") is None:
                    # Test read_file with bucket
                    read_payload = {
                        "method": "read_file",
                        "params": {
                            "path": test_file,
                            "bucket": test_bucket
                        }
                    }
                    read_response = requests.post(f"{self.base_url}/mcp/tools/call", 
                                                json=read_payload, timeout=5)
                    
                    if read_response.status_code == 200:
                        read_data = read_response.json()
                        read_result = read_data.get("result", "")
                        
                        if read_result == test_content:
                            self.log_test("File Operations with Buckets", True, 
                                        f"Successfully wrote and read from bucket '{test_bucket}'")
                            return True
                        else:
                            self.log_test("File Operations with Buckets", False, 
                                        "Content mismatch between write and read")
                            return False
                    
            self.log_test("File Operations with Buckets", False, "File operation failed")
            return False
        except Exception as e:
            self.log_test("File Operations with Buckets", False, f"Error: {e}")
            return False
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all iterative tests."""
        print("🚀 Starting Comprehensive Iterative Test Suite")
        print("=" * 60)
        
        tests = [
            self.test_server_connectivity,
            self.test_mcp_protocol_init,
            self.test_mcp_tools_discovery,
            self.test_filesystem_state_management,
            self.test_bucket_vfs_operations,
            self.test_backend_management,
            self.test_daemon_status_monitoring,
            self.test_rest_api_endpoints,
            self.test_system_metrics,
            self.test_file_operations_with_buckets
        ]
        
        passed_tests = 0
        total_tests = len(tests)
        
        for test_func in tests:
            try:
                if test_func():
                    passed_tests += 1
            except Exception as e:
                print(f"❌ FATAL ERROR in {test_func.__name__}: {e}")
        
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        success_rate = (passed_tests / total_tests) * 100
        status = "✅ SUCCESS" if passed_tests == total_tests else "⚠️  PARTIAL SUCCESS" if passed_tests > 0 else "❌ FAILURE"
        
        print(f"Status: {status}")
        print(f"Passed: {passed_tests}/{total_tests} ({success_rate:.1f}%)")
        
        if passed_tests == total_tests:
            print("\n🎉 ALL ITERATIVE TESTS PASSED!")
            print("✅ Modern hybrid MCP dashboard is fully functional")
            print("✅ Light initialization working")
            print("✅ Bucket VFS operations working")
            print("✅ ~/.ipfs_kit/ state management working")
            print("✅ JSON RPC MCP protocol working")
            print("✅ All original functionality restored")
        else:
            print(f"\n⚠️  {total_tests - passed_tests} tests failed")
            print("🔧 Review test details above for issues to address")
        
        return {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "success_rate": success_rate,
            "all_passed": passed_tests == total_tests,
            "detailed_results": self.test_results
        }

def main():
    """Main entry point for iterative testing."""
    print("🧪 Modern Hybrid MCP Dashboard - Iterative Test Suite")
    print(f"🎯 Target: {BASE_URL}")
    print()
    
    tester = ModernMCPTester()
    results = tester.run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if results["all_passed"] else 1)

if __name__ == "__main__":
    main()
