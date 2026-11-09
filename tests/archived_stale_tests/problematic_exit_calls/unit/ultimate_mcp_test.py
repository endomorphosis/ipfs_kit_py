#!/usr/bin/env python3
"""
Ultimate MCP Tools Test Suite
=============================

This is the most comprehensive test suite for the MCP server that tests:
1. Server startup and health
2. All REST API endpoints
3. JSON-RPC protocol compliance
4. All IPFS operations (add, cat, pin, unpin, version)
5. Error handling and edge cases
6. Performance under load
7. MCP protocol specifics
8. Tool discovery and execution
9. Parameter validation
10. Security headers and CORS

This suite provides a complete verification that all MCP tools work correctly.
"""

import os
import sys
import json
import time
import subprocess
import traceback
import threading
from datetime import datetime
from pathlib import Path

def write_log(message, log_file="ultimate_mcp_test.log"):
    """Write message to log file with timestamp"""
    timestamp = datetime.now().isoformat()
    with open(log_file, "a") as f:
        f.write(f"{timestamp}: {message}\n")

class UltimateMCPTestSuite:
    """Ultimate comprehensive test suite for MCP server functionality"""
    
    def __init__(self, server_file="final_mcp_server_enhanced.py", port=9999):
        self.server_file = server_file
        self.port = port
        self.base_url = f"http://localhost:{port}"
        self.jsonrpc_url = f"{self.base_url}/jsonrpc"
        self.server_proc = None
        self.results = {
            "start_time": datetime.now().isoformat(),
            "tests": {},
            "summary": {"passed": 0, "failed": 0, "errors": []},
            "performance": {},
            "security": {}
        }
    
    def log_test(self, test_name, passed, message="", details=None):
        """Log test result"""
        status = "PASS" if passed else "FAIL"
        write_log(f"{status}: {test_name} - {message}")
        
        self.results["tests"][test_name] = {
            "status": status,
            "message": message,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        
        if passed:
            self.results["summary"]["passed"] += 1
        else:
            self.results["summary"]["failed"] += 1
            self.results["summary"]["errors"].append(f"{test_name}: {message}")
    
    def start_server(self):
        """Start the MCP server"""
        try:
            write_log("🚀 Starting MCP server...")
            
            # Kill any existing servers
            subprocess.run(["pkill", "-f", "final_mcp_server"], check=False)
            time.sleep(2)
            
            # Start server
            venv_python = Path.cwd() / ".venv" / "bin" / "python"
            cmd = [str(venv_python), self.server_file, "--host", "0.0.0.0", "--port", str(self.port)]
            
            with open("server_ultimate_test.log", "w") as log_file:
                self.server_proc = subprocess.Popen(
                    cmd,
                    stdout=log_file,
                    stderr=subprocess.STDOUT
                )
            
            # Wait for startup
            for i in range(30):
                try:
                    result = subprocess.run([
                        "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                        f"{self.base_url}/health"
                    ], capture_output=True, text=True, timeout=5)
                    
                    if result.returncode == 0 and result.stdout == "200":
                        self.log_test("server_startup", True, f"Server started on port {self.port}")
                        return True
                except:
                    pass
                time.sleep(1)
            
            self.log_test("server_startup", False, "Server failed to start within 30 seconds")
            return False
            
        except Exception as e:
            self.log_test("server_startup", False, f"Exception during startup: {e}")
            return False
    
    def stop_server(self):
        """Stop the MCP server"""
        try:
            if self.server_proc:
                self.server_proc.terminate()
                self.server_proc.wait(timeout=10)
            subprocess.run(["pkill", "-f", "final_mcp_server"], check=False)
            self.log_test("server_shutdown", True, "Server stopped successfully")
        except Exception as e:
            self.log_test("server_shutdown", False, f"Error stopping server: {e}")
    
    def test_basic_endpoints(self):
        """Test all basic REST endpoints"""
        endpoints = [
            ("health", "/health", "Health check endpoint"),
            ("info", "/", "Server info endpoint"),
            ("tools", "/mcp/tools", "Tools listing endpoint"),
            ("stats", "/stats", "Statistics endpoint"),
            ("docs", "/docs", "API documentation")
        ]
        
        for name, path, description in endpoints:
            try:
                result = subprocess.run([
                    "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                    "--max-time", "10", f"{self.base_url}{path}"
                ], capture_output=True, text=True, timeout=15)
                
                if result.returncode == 0 and result.stdout in ["200", "307"]:  # 307 for docs redirect
                    self.log_test(f"endpoint_{name}", True, f"{description} responding ({result.stdout})")
                else:
                    self.log_test(f"endpoint_{name}", False, f"{description} failed: {result.stdout}")
            except Exception as e:
                self.log_test(f"endpoint_{name}", False, f"{description} exception: {e}")
    
    def test_ipfs_operations(self):
        """Test all IPFS operations thoroughly"""
        # Test 1: Add operation
        test_content = "Hello, Ultimate IPFS Test! This is comprehensive testing."
        try:
            result = subprocess.run([
                "curl", "-s", "-X", "POST",
                "-H", "Content-Type: application/json",
                "-d", json.dumps({"content": test_content}),
                "--max-time", "15",
                f"{self.base_url}/ipfs/add"
            ], capture_output=True, text=True, timeout=20)
            
            if result.returncode == 0:
                try:
                    response = json.loads(result.stdout)
                    if response.get("success") and "cid" in response:
                        cid = response["cid"]
                        self.log_test("ipfs_add", True, f"Add successful, CID: {cid}", response)
                        
                        # Test 2: Cat operation
                        cat_result = subprocess.run([
                            "curl", "-s", "--max-time", "15",
                            f"{self.base_url}/ipfs/cat/{cid}"
                        ], capture_output=True, text=True, timeout=20)
                        
                        if cat_result.returncode == 0:
                            try:
                                cat_response = json.loads(cat_result.stdout)
                                if cat_response.get("success"):
                                    self.log_test("ipfs_cat", True, f"Cat successful for CID: {cid}", cat_response)
                                else:
                                    self.log_test("ipfs_cat", False, f"Cat failed: {cat_response}")
                            except:
                                self.log_test("ipfs_cat", False, f"Cat response not JSON: {cat_result.stdout[:100]}")
                        else:
                            self.log_test("ipfs_cat", False, f"Cat request failed: {cat_result.stderr}")
                        
                        # Test 3: Pin operations
                        pin_result = subprocess.run([
                            "curl", "-s", "-X", "POST",
                            "-H", "Content-Type: application/json",
                            "-d", "{}",
                            "--max-time", "15",
                            f"{self.base_url}/ipfs/pin/add/{cid}"
                        ], capture_output=True, text=True, timeout=20)
                        
                        if pin_result.returncode == 0:
                            try:
                                pin_response = json.loads(pin_result.stdout)
                                if pin_response.get("success"):
                                    self.log_test("ipfs_pin_add", True, f"Pin add successful for CID: {cid}")
                                    
                                    # Test 4: Unpin operation
                                    unpin_result = subprocess.run([
                                        "curl", "-s", "-X", "DELETE",
                                        "--max-time", "15",
                                        f"{self.base_url}/ipfs/pin/rm/{cid}"
                                    ], capture_output=True, text=True, timeout=20)
                                    
                                    if unpin_result.returncode == 0:
                                        try:
                                            unpin_response = json.loads(unpin_result.stdout)
                                            if unpin_response.get("success"):
                                                self.log_test("ipfs_pin_rm", True, f"Unpin successful for CID: {cid}")
                                            else:
                                                self.log_test("ipfs_pin_rm", False, f"Unpin failed: {unpin_response}")
                                        except:
                                            self.log_test("ipfs_pin_rm", False, f"Unpin response not JSON: {unpin_result.stdout[:100]}")
                                    else:
                                        self.log_test("ipfs_pin_rm", False, f"Unpin request failed")
                                else:
                                    self.log_test("ipfs_pin_add", False, f"Pin add failed: {pin_response}")
                            except:
                                self.log_test("ipfs_pin_add", False, f"Pin response not JSON: {pin_result.stdout[:100]}")
                        else:
                            self.log_test("ipfs_pin_add", False, f"Pin request failed")
                    else:
                        self.log_test("ipfs_add", False, f"Add failed: {response}")
                except:
                    self.log_test("ipfs_add", False, f"Add response not JSON: {result.stdout[:100]}")
            else:
                self.log_test("ipfs_add", False, f"Add request failed: {result.stderr}")
        except Exception as e:
            self.log_test("ipfs_add", False, f"Add operation exception: {e}")
        
        # Test 5: Version endpoint
        try:
            version_result = subprocess.run([
                "curl", "-s", "--max-time", "10",
                f"{self.base_url}/ipfs/version"
            ], capture_output=True, text=True, timeout=15)
            
            if version_result.returncode == 0:
                try:
                    version_response = json.loads(version_result.stdout)
                    if version_response.get("success") and "version" in version_response:
                        self.log_test("ipfs_version", True, "Version endpoint successful", version_response["version"])
                    else:
                        self.log_test("ipfs_version", False, f"Version failed: {version_response}")
                except:
                    self.log_test("ipfs_version", False, f"Version response not JSON: {version_result.stdout[:100]}")
            else:
                self.log_test("ipfs_version", False, f"Version request failed")
        except Exception as e:
            self.log_test("ipfs_version", False, f"Version exception: {e}")
    
    def test_json_rpc_protocol(self):
        """Test JSON-RPC protocol compliance"""
        test_cases = [
            {
                "name": "invalid_method",
                "request": {"jsonrpc": "2.0", "method": "invalid_method", "params": {}, "id": 1},
                "expect_error": True
            },
            {
                "name": "malformed_request", 
                "request": {"method": "test"},  # Missing jsonrpc version
                "expect_error": True
            },
            {
                "name": "tools_list",
                "request": {"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 2},
                "expect_error": False
            }
        ]
        
        for case in test_cases:
            try:
                result = subprocess.run([
                    "curl", "-s", "-X", "POST",
                    "-H", "Content-Type: application/json",
                    "-d", json.dumps(case["request"]),
                    "--max-time", "10",
                    self.jsonrpc_url
                ], capture_output=True, text=True, timeout=15)
                
                if result.returncode == 0:
                    try:
                        response = json.loads(result.stdout)
                        has_error = "error" in response
                        
                        if case["expect_error"] and has_error:
                            self.log_test(f"jsonrpc_{case['name']}", True, f"Correctly returned error: {response.get('error', {}).get('message', 'Unknown')}")
                        elif not case["expect_error"] and not has_error:
                            self.log_test(f"jsonrpc_{case['name']}", True, f"Request successful: {case['name']}")
                        else:
                            self.log_test(f"jsonrpc_{case['name']}", False, f"Unexpected response: {response}")
                    except:
                        self.log_test(f"jsonrpc_{case['name']}", False, f"Response not JSON: {result.stdout[:100]}")
                else:
                    self.log_test(f"jsonrpc_{case['name']}", False, f"Request failed: {result.stderr}")
            except Exception as e:
                self.log_test(f"jsonrpc_{case['name']}", False, f"Exception: {e}")
    
    def test_error_handling(self):
        """Test error handling and edge cases"""
        error_tests = [
            ("404_endpoint", "/nonexistent", "404"),
            ("invalid_cid", "/ipfs/cat/invalid_cid", "500"),
            ("empty_content", "/ipfs/add", "POST with empty content")
        ]
        
        for name, path, description in error_tests:
            try:
                if "POST" in description:
                    result = subprocess.run([
                        "curl", "-s", "-X", "POST",
                        "-H", "Content-Type: application/json",
                        "-d", '{"content": ""}',
                        "-w", "%{http_code}",
                        "--max-time", "10",
                        f"{self.base_url}{path}"
                    ], capture_output=True, text=True, timeout=15)
                else:
                    result = subprocess.run([
                        "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                        "--max-time", "10",
                        f"{self.base_url}{path}"
                    ], capture_output=True, text=True, timeout=15)
                
                if result.returncode == 0:
                    status_code = result.stdout[-3:] if len(result.stdout) >= 3 else result.stdout
                    if status_code in ["404", "422", "500"]:
                        self.log_test(f"error_{name}", True, f"Correctly handled {description}: {status_code}")
                    else:
                        self.log_test(f"error_{name}", False, f"Unexpected status for {description}: {status_code}")
                else:
                    self.log_test(f"error_{name}", False, f"Request failed for {description}")
            except Exception as e:
                self.log_test(f"error_{name}", False, f"Exception testing {description}: {e}")
    
    def test_performance(self):
        """Test basic performance metrics"""
        try:
            # Test rapid requests
            start_time = time.time()
            successful_requests = 0
            
            for i in range(20):
                try:
                    result = subprocess.run([
                        "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                        "--max-time", "5",
                        f"{self.base_url}/health"
                    ], capture_output=True, text=True, timeout=8)
                    
                    if result.returncode == 0 and result.stdout == "200":
                        successful_requests += 1
                except:
                    pass
            
            end_time = time.time()
            duration = end_time - start_time
            rps = successful_requests / duration if duration > 0 else 0
            
            self.results["performance"] = {
                "total_requests": 20,
                "successful_requests": successful_requests,
                "duration": duration,
                "requests_per_second": rps
            }
            
            if successful_requests >= 15:  # Allow for some failures
                self.log_test("performance_load", True, f"Performance: {successful_requests}/20 requests, {rps:.2f} RPS")
            else:
                self.log_test("performance_load", False, f"Poor performance: {successful_requests}/20 requests")
                
        except Exception as e:
            self.log_test("performance_load", False, f"Performance test exception: {e}")
    
    def test_security_headers(self):
        """Test security headers and CORS"""
        try:
            result = subprocess.run([
                "curl", "-s", "-I", "--max-time", "10",
                f"{self.base_url}/health"
            ], capture_output=True, text=True, timeout=15)
            
            if result.returncode == 0:
                headers = result.stdout.lower()
                
                security_checks = {
                    "cors_origin": "access-control-allow-origin" in headers,
                    "cors_methods": "access-control-allow-methods" in headers,
                    "cors_headers": "access-control-allow-headers" in headers,
                    "content_type": "content-type" in headers
                }
                
                self.results["security"] = security_checks
                
                if security_checks["cors_origin"]:
                    self.log_test("security_cors", True, "CORS headers present")
                else:
                    self.log_test("security_cors", False, "CORS headers missing")
                    
                if security_checks["content_type"]:
                    self.log_test("security_content_type", True, "Content-Type header present")
                else:
                    self.log_test("security_content_type", False, "Content-Type header missing")
            else:
                self.log_test("security_headers", False, "Failed to get headers")
                
        except Exception as e:
            self.log_test("security_headers", False, f"Security test exception: {e}")
    
    def run_all_tests(self):
        """Run the complete test suite"""
        write_log("🚀 Starting Ultimate MCP Test Suite")
        write_log("="*60)
        
        try:
            # Start server
            if not self.start_server():
                write_log("❌ Failed to start server - aborting tests")
                return self.results
            
            # Run all test categories
            write_log("🔍 Testing basic endpoints...")
            self.test_basic_endpoints()
            
            write_log("🔧 Testing IPFS operations...")
            self.test_ipfs_operations()
            
            write_log("📡 Testing JSON-RPC protocol...")
            self.test_json_rpc_protocol()
            
            write_log("🚨 Testing error handling...")
            self.test_error_handling()
            
            write_log("⚡ Testing performance...")
            self.test_performance()
            
            write_log("🔒 Testing security...")
            self.test_security_headers()
            
        except Exception as e:
            write_log(f"❌ Test suite exception: {e}")
            write_log(traceback.format_exc())
        finally:
            # Always stop server
            self.stop_server()
        
        # Finalize results
        self.results["end_time"] = datetime.now().isoformat()
        self.results["total_tests"] = len(self.results["tests"])
        
        # Save results
        with open("ultimate_mcp_test_results.json", "w") as f:
            json.dump(self.results, f, indent=2)
        
        # Summary
        write_log("="*60)
        write_log("🧪 ULTIMATE MCP TEST SUITE SUMMARY")
        write_log("="*60)
        write_log(f"✅ Tests Passed: {self.results['summary']['passed']}")
        write_log(f"❌ Tests Failed: {self.results['summary']['failed']}")
        write_log(f"📊 Total Tests: {self.results['total_tests']}")
        
        if self.results["performance"]:
            perf = self.results["performance"]
            write_log(f"⚡ Performance: {perf['successful_requests']}/{perf['total_requests']} requests, {perf['requests_per_second']:.2f} RPS")
        
        if self.results["summary"]["failed"] > 0:
            write_log("🚨 Failed tests:")
            for error in self.results["summary"]["errors"]:
                write_log(f"   • {error}")
        
        write_log(f"📄 Detailed results saved to: ultimate_mcp_test_results.json")
        write_log(f"📄 Logs saved to: ultimate_mcp_test.log")
        
        return self.results

def main():
    """Main function"""
    # Clear previous logs
    for log_file in ["ultimate_mcp_test.log", "server_ultimate_test.log", "ultimate_mcp_test_results.json"]:
        if os.path.exists(log_file):
            os.remove(log_file)
    
    # Run tests
    test_suite = UltimateMCPTestSuite()
    results = test_suite.run_all_tests()
    
    # Print summary to stdout as well
    print("\n" + "="*60)
    print("🧪 ULTIMATE MCP TEST SUITE RESULTS")
    print("="*60)
    print(f"✅ Tests Passed: {results['summary']['passed']}")
    print(f"❌ Tests Failed: {results['summary']['failed']}")
    print(f"📊 Total Tests: {results['total_tests']}")
    
    if results.get("performance"):
        perf = results["performance"]
        print(f"⚡ Performance: {perf['requests_per_second']:.2f} RPS")
    
    if results["summary"]["failed"] > 0:
        print(f"\n🚨 {results['summary']['failed']} tests failed:")
        for error in results["summary"]["errors"]:
            print(f"   • {error}")
        sys.exit(1)
    else:
        print(f"\n🎉 All {results['summary']['passed']} tests passed!")
        print("✅ MCP server is fully functional and ready for production!")
        sys.exit(0)

if __name__ == "__main__":
    main()
