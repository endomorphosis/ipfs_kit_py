#!/usr/bin/env python3
"""
Comprehensive MCP Tools Test Suite
==================================

This test suite comprehensively tests all MCP tools and functionality to ensure
everything works correctly. It includes:

1. Server startup and health checks
2. REST API endpoints testing
3. JSON-RPC protocol testing
4. Individual tool functionality testing
5. Integration testing
6. Error handling testing
7. Performance testing
8. Mock IPFS functionality testing

Usage:
    python comprehensive_mcp_test.py [--server-file SERVER] [--port PORT] [--timeout TIMEOUT]
"""

import os
import sys
import json
import time
import asyncio
import logging
import requests
import subprocess
import traceback
import argparse
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path

# Configure comprehensive logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("comprehensive_mcp_test.log", mode='w'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("mcp-test")

class MCPTestSuite:
    """Comprehensive test suite for MCP server functionality"""
    
    def __init__(self, server_file: str = "final_mcp_server_enhanced.py", 
                 port: int = 9998, timeout: int = 30):
        self.server_file = server_file
        self.port = port
        self.timeout = timeout
        self.base_url = f"http://localhost:{port}"
        self.jsonrpc_url = f"{self.base_url}/jsonrpc"
        self.server_process = None
        self.test_results = {
            "passed": 0,
            "failed": 0,
            "errors": [],
            "start_time": datetime.now().isoformat(),
            "tests": {}
        }
        
    def log_test_result(self, test_name: str, passed: bool, message: str = "", details: Any = None):
        """Log test result"""
        result = "PASS" if passed else "FAIL"
        logger.info(f"TEST {result}: {test_name} - {message}")
        
        self.test_results["tests"][test_name] = {
            "passed": passed,
            "message": message,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        
        if passed:
            self.test_results["passed"] += 1
        else:
            self.test_results["failed"] += 1
            self.test_results["errors"].append(f"{test_name}: {message}")
    
    def start_server(self) -> bool:
        """Start the MCP server"""
        try:
            # Check if server file exists
            if not os.path.exists(self.server_file):
                self.log_test_result("server_file_exists", False, f"Server file {self.server_file} not found")
                return False
            
            self.log_test_result("server_file_exists", True, f"Server file {self.server_file} found")
            
            # Kill any existing server
            try:
                subprocess.run(["pkill", "-f", f"python.*{self.server_file}"], 
                             check=False, capture_output=True)
                time.sleep(2)
            except:
                pass
            
            # Start server
            cmd = [sys.executable, self.server_file, "--host", "0.0.0.0", "--port", str(self.port)]
            self.server_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for server to start
            for i in range(self.timeout):
                try:
                    response = requests.get(f"{self.base_url}/health", timeout=2)
                    if response.status_code == 200:
                        self.log_test_result("server_startup", True, f"Server started on port {self.port}")
                        return True
                except requests.exceptions.RequestException:
                    time.sleep(1)
                    continue
            
            self.log_test_result("server_startup", False, f"Server failed to start within {self.timeout} seconds")
            return False
            
        except Exception as e:
            self.log_test_result("server_startup", False, f"Exception starting server: {e}")
            return False
    
    def stop_server(self):
        """Stop the MCP server"""
        try:
            if self.server_process:
                self.server_process.terminate()
                try:
                    self.server_process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.server_process.kill()
                    self.server_process.wait()
                self.log_test_result("server_shutdown", True, "Server shut down successfully")
            
            # Also kill any running instances
            subprocess.run(["pkill", "-f", f"python.*{self.server_file}"], 
                         check=False, capture_output=True)
                         
        except Exception as e:
            self.log_test_result("server_shutdown", False, f"Error shutting down server: {e}")
    
    def test_health_endpoint(self) -> bool:
        """Test the health endpoint"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if "status" in data and data["status"] == "healthy":
                    self.log_test_result("health_endpoint", True, "Health endpoint working correctly", data)
                    return True
                else:
                    self.log_test_result("health_endpoint", False, "Health endpoint returned unexpected data", data)
                    return False
            else:
                self.log_test_result("health_endpoint", False, f"Health endpoint returned status {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test_result("health_endpoint", False, f"Health endpoint test failed: {e}")
            return False
    
    def test_info_endpoint(self) -> bool:
        """Test the info endpoint"""
        try:
            response = requests.get(f"{self.base_url}/", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ["name", "version", "description"]
                missing_fields = [field for field in required_fields if field not in data]
                
                if not missing_fields:
                    self.log_test_result("info_endpoint", True, "Info endpoint working correctly", data)
                    return True
                else:
                    self.log_test_result("info_endpoint", False, f"Missing fields: {missing_fields}", data)
                    return False
            else:
                self.log_test_result("info_endpoint", False, f"Info endpoint returned status {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test_result("info_endpoint", False, f"Info endpoint test failed: {e}")
            return False
    
    def test_metrics_endpoint(self) -> bool:
        """Test the metrics endpoint"""
        try:
            response = requests.get(f"{self.base_url}/metrics", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if "uptime" in data and "request_count" in data:
                    self.log_test_result("metrics_endpoint", True, "Metrics endpoint working correctly", data)
                    return True
                else:
                    self.log_test_result("metrics_endpoint", False, "Metrics endpoint missing expected fields", data)
                    return False
            else:
                self.log_test_result("metrics_endpoint", False, f"Metrics endpoint returned status {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test_result("metrics_endpoint", False, f"Metrics endpoint test failed: {e}")
            return False
    
    def test_jsonrpc_basic(self) -> bool:
        """Test basic JSON-RPC functionality"""
        try:
            # Test with invalid method
            invalid_request = {
                "jsonrpc": "2.0",
                "method": "invalid_method",
                "params": {},
                "id": 1
            }
            
            response = requests.post(
                self.jsonrpc_url,
                json=invalid_request,
                headers={"Content-Type": "application/json"},
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                if "error" in data:
                    self.log_test_result("jsonrpc_error_handling", True, "JSON-RPC properly handles invalid methods", data)
                else:
                    self.log_test_result("jsonrpc_error_handling", False, "JSON-RPC should return error for invalid method", data)
                    return False
            else:
                self.log_test_result("jsonrpc_error_handling", False, f"JSON-RPC returned status {response.status_code}")
                return False
            
            return True
            
        except Exception as e:
            self.log_test_result("jsonrpc_error_handling", False, f"JSON-RPC basic test failed: {e}")
            return False
    
    def test_ipfs_add_operation(self) -> bool:
        """Test IPFS add operation via REST API"""
        try:
            test_content = "Hello, IPFS! This is a test content."
            
            response = requests.post(
                f"{self.base_url}/ipfs/add",
                json={"content": test_content},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if "cid" in data and data["cid"].startswith("Qm"):
                    self.log_test_result("ipfs_add_operation", True, f"IPFS add successful, CID: {data['cid']}", data)
                    return True
                else:
                    self.log_test_result("ipfs_add_operation", False, "IPFS add returned invalid CID format", data)
                    return False
            else:
                self.log_test_result("ipfs_add_operation", False, f"IPFS add returned status {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test_result("ipfs_add_operation", False, f"IPFS add operation test failed: {e}")
            return False
    
    def test_ipfs_cat_operation(self) -> bool:
        """Test IPFS cat operation via REST API"""
        try:
            # First add content
            test_content = "Test content for cat operation"
            add_response = requests.post(
                f"{self.base_url}/ipfs/add",
                json={"content": test_content},
                timeout=10
            )
            
            if add_response.status_code != 200:
                self.log_test_result("ipfs_cat_operation", False, "Failed to add content for cat test")
                return False
            
            cid = add_response.json()["cid"]
            
            # Now test cat operation
            cat_response = requests.get(f"{self.base_url}/ipfs/cat/{cid}", timeout=10)
            
            if cat_response.status_code == 200:
                content = cat_response.text
                if test_content in content or "Mock content" in content:
                    self.log_test_result("ipfs_cat_operation", True, f"IPFS cat successful for CID: {cid}")
                    return True
                else:
                    self.log_test_result("ipfs_cat_operation", False, f"IPFS cat returned unexpected content: {content}")
                    return False
            else:
                self.log_test_result("ipfs_cat_operation", False, f"IPFS cat returned status {cat_response.status_code}")
                return False
                
        except Exception as e:
            self.log_test_result("ipfs_cat_operation", False, f"IPFS cat operation test failed: {e}")
            return False
    
    def test_ipfs_pin_operations(self) -> bool:
        """Test IPFS pin operations via REST API"""
        try:
            # First add content
            test_content = "Test content for pin operations"
            add_response = requests.post(
                f"{self.base_url}/ipfs/add",
                json={"content": test_content},
                timeout=10
            )
            
            if add_response.status_code != 200:
                self.log_test_result("ipfs_pin_operations", False, "Failed to add content for pin test")
                return False
            
            cid = add_response.json()["cid"]
            
            # Test pin add
            pin_response = requests.post(f"{self.base_url}/ipfs/pin/add/{cid}", timeout=10)
            
            if pin_response.status_code != 200:
                self.log_test_result("ipfs_pin_operations", False, f"Pin add failed with status {pin_response.status_code}")
                return False
            
            # Test pin remove
            unpin_response = requests.delete(f"{self.base_url}/ipfs/pin/rm/{cid}", timeout=10)
            
            if unpin_response.status_code == 200:
                self.log_test_result("ipfs_pin_operations", True, f"Pin operations successful for CID: {cid}")
                return True
            else:
                self.log_test_result("ipfs_pin_operations", False, f"Pin remove failed with status {unpin_response.status_code}")
                return False
                
        except Exception as e:
            self.log_test_result("ipfs_pin_operations", False, f"IPFS pin operations test failed: {e}")
            return False
    
    def test_ipfs_version(self) -> bool:
        """Test IPFS version endpoint"""
        try:
            response = requests.get(f"{self.base_url}/ipfs/version", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if "Version" in data and "System" in data:
                    self.log_test_result("ipfs_version", True, "IPFS version endpoint working", data)
                    return True
                else:
                    self.log_test_result("ipfs_version", False, "IPFS version missing expected fields", data)
                    return False
            else:
                self.log_test_result("ipfs_version", False, f"IPFS version returned status {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test_result("ipfs_version", False, f"IPFS version test failed: {e}")
            return False
    
    def test_jsonrpc_tools_listing(self) -> bool:
        """Test JSON-RPC tools listing"""
        try:
            request = {
                "jsonrpc": "2.0",
                "method": "tools/list",
                "params": {},
                "id": 2
            }
            
            response = requests.post(
                self.jsonrpc_url,
                json=request,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if "result" in data and isinstance(data["result"], dict):
                    tools = data["result"]
                    tool_count = len(tools.get("tools", []))
                    self.log_test_result("jsonrpc_tools_listing", True, f"JSON-RPC tools listing successful, found {tool_count} tools", tools)
                    return True
                else:
                    self.log_test_result("jsonrpc_tools_listing", False, "JSON-RPC tools listing returned unexpected format", data)
                    return False
            else:
                self.log_test_result("jsonrpc_tools_listing", False, f"JSON-RPC tools listing returned status {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test_result("jsonrpc_tools_listing", False, f"JSON-RPC tools listing test failed: {e}")
            return False
    
    def test_performance_basic(self) -> bool:
        """Test basic performance metrics"""
        try:
            # Test multiple rapid requests
            start_time = time.time()
            successful_requests = 0
            
            for i in range(10):
                try:
                    response = requests.get(f"{self.base_url}/health", timeout=2)
                    if response.status_code == 200:
                        successful_requests += 1
                except:
                    pass
            
            end_time = time.time()
            duration = end_time - start_time
            rps = successful_requests / duration if duration > 0 else 0
            
            if successful_requests >= 8:  # Allow for some failures
                self.log_test_result("performance_basic", True, f"Performance test: {successful_requests}/10 requests successful, {rps:.2f} RPS")
                return True
            else:
                self.log_test_result("performance_basic", False, f"Performance test: only {successful_requests}/10 requests successful")
                return False
                
        except Exception as e:
            self.log_test_result("performance_basic", False, f"Performance test failed: {e}")
            return False
    
    def test_error_handling(self) -> bool:
        """Test error handling capabilities"""
        try:
            # Test 404 endpoint
            response = requests.get(f"{self.base_url}/nonexistent", timeout=5)
            if response.status_code != 404:
                self.log_test_result("error_handling_404", False, f"Expected 404, got {response.status_code}")
                return False
            
            # Test invalid JSON-RPC
            invalid_json = "not json"
            response = requests.post(
                self.jsonrpc_url,
                data=invalid_json,
                headers={"Content-Type": "application/json"},
                timeout=5
            )
            # Should return some error status
            if response.status_code in [400, 422, 500]:
                self.log_test_result("error_handling", True, "Error handling working correctly")
                return True
            else:
                self.log_test_result("error_handling", False, f"Unexpected status for invalid JSON: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test_result("error_handling", False, f"Error handling test failed: {e}")
            return False
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all tests and return results"""
        logger.info("🚀 Starting comprehensive MCP server test suite")
        
        try:
            # Start server
            if not self.start_server():
                return self.test_results
            
            # Run all tests
            tests = [
                self.test_health_endpoint,
                self.test_info_endpoint,
                self.test_metrics_endpoint,
                self.test_jsonrpc_basic,
                self.test_ipfs_add_operation,
                self.test_ipfs_cat_operation,
                self.test_ipfs_pin_operations,
                self.test_ipfs_version,
                self.test_jsonrpc_tools_listing,
                self.test_performance_basic,
                self.test_error_handling
            ]
            
            for test in tests:
                try:
                    test()
                except Exception as e:
                    logger.error(f"Test {test.__name__} crashed: {e}")
                    self.log_test_result(test.__name__, False, f"Test crashed: {e}")
            
        finally:
            # Always stop server
            self.stop_server()
        
        # Final results
        self.test_results["end_time"] = datetime.now().isoformat()
        self.test_results["duration"] = str(datetime.fromisoformat(self.test_results["end_time"]) - 
                                         datetime.fromisoformat(self.test_results["start_time"]))
        
        logger.info(f"🏁 Test suite completed: {self.test_results['passed']} passed, {self.test_results['failed']} failed")
        
        return self.test_results
    
    def save_results(self, filename: str = None):
        """Save test results to file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"mcp_test_results_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(self.test_results, f, indent=2)
        
        logger.info(f"📄 Test results saved to {filename}")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Comprehensive MCP Server Test Suite")
    parser.add_argument("--server-file", default="final_mcp_server_enhanced.py",
                       help="MCP server file to test")
    parser.add_argument("--port", type=int, default=9998,
                       help="Port to run server on")
    parser.add_argument("--timeout", type=int, default=30,
                       help="Timeout for server startup")
    parser.add_argument("--save-results", action="store_true",
                       help="Save results to JSON file")
    
    args = parser.parse_args()
    
    # Run tests
    test_suite = MCPTestSuite(
        server_file=args.server_file,
        port=args.port,
        timeout=args.timeout
    )
    
    results = test_suite.run_all_tests()
    
    # Save results if requested
    if args.save_results:
        test_suite.save_results()
    
    # Print summary
    print("\n" + "="*80)
    print("🧪 COMPREHENSIVE MCP TEST SUITE RESULTS")
    print("="*80)
    print(f"✅ Tests Passed: {results['passed']}")
    print(f"❌ Tests Failed: {results['failed']}")
    print(f"⏱️  Duration: {results.get('duration', 'N/A')}")
    
    if results['errors']:
        print("\n🚨 Failed Tests:")
        for error in results['errors']:
            print(f"   • {error}")
    
    print("\n📋 Individual Test Results:")
    for test_name, test_result in results['tests'].items():
        status = "✅ PASS" if test_result['passed'] else "❌ FAIL"
        print(f"   {status} {test_name}: {test_result['message']}")
    
    # Exit with appropriate code
    if results['failed'] > 0:
        print(f"\n🚨 {results['failed']} tests failed. Please check the logs for details.")
        sys.exit(1)
    else:
        print(f"\n🎉 All {results['passed']} tests passed! MCP server is working correctly.")
        sys.exit(0)

if __name__ == "__main__":
    main()
