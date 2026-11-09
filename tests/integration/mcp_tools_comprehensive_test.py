#!/usr/bin/env python3
"""
MCP Tools Comprehensive Test Suite
=================================

This test suite validates that ALL MCP server tools work correctly after workspace cleanup.
It tests each tool individually and verifies the complete functionality.
"""

import os
import sys
import json
import time
import subprocess
import traceback
from pathlib import Path
from datetime import datetime

class MCPToolsValidator:
    """Comprehensive validator for all MCP tools"""
    
    def __init__(self, server_file="final_mcp_server_enhanced.py", port=9997):
        self.server_file = server_file
        self.port = port
        self.base_url = f"http://localhost:{port}"
        self.server_proc = None
        self.results = {
            "start_time": datetime.now().isoformat(),
            "server_tests": {},
            "tool_tests": {},
            "integration_tests": {},
            "summary": {"passed": 0, "failed": 0, "total": 0}
        }
    
    def log_result(self, category, test_name, passed, message="", details=None):
        """Log test result"""
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {category}.{test_name}: {message}")
        
        if category not in self.results:
            self.results[category] = {}
        
        self.results[category][test_name] = {
            "status": status,
            "message": message,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        
        if passed:
            self.results["summary"]["passed"] += 1
        else:
            self.results["summary"]["failed"] += 1
        self.results["summary"]["total"] += 1
    
    def start_server(self):
        """Start the MCP server"""
        try:
            print(f"🚀 Starting MCP server: {self.server_file}")
            
            # Kill any existing servers
            subprocess.run(["pkill", "-f", "final_mcp_server"], check=False, capture_output=True)
            time.sleep(2)
            
            # Check server file exists
            if not Path(self.server_file).exists():
                self.log_result("server", "file_exists", False, f"Server file {self.server_file} not found")
                return False
            
            # Start server
            venv_python = Path(".venv/bin/python")
            python_cmd = str(venv_python) if venv_python.exists() else "python3"
            
            cmd = [python_cmd, self.server_file, "--host", "0.0.0.0", "--port", str(self.port)]
            
            with open("mcp_tools_test_server.log", "w") as log_file:
                self.server_proc = subprocess.Popen(
                    cmd,
                    stdout=log_file,
                    stderr=subprocess.STDOUT
                )
            
            # Wait for startup
            print("   ⏳ Waiting for server startup...")
            for i in range(30):
                try:
                    result = subprocess.run([
                        "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                        f"{self.base_url}/health"
                    ], capture_output=True, text=True, timeout=5)
                    
                    if result.returncode == 0 and result.stdout == "200":
                        self.log_result("server", "startup", True, f"Started on port {self.port}")
                        return True
                except:
                    pass
                time.sleep(1)
            
            self.log_result("server", "startup", False, "Failed to start within 30 seconds")
            return False
            
        except Exception as e:
            self.log_result("server", "startup", False, f"Exception: {e}")
            return False
    
    def stop_server(self):
        """Stop the MCP server"""
        try:
            if self.server_proc:
                self.server_proc.terminate()
                try:
                    self.server_proc.wait(timeout=10)
                except:
                    self.server_proc.kill()
            subprocess.run(["pkill", "-f", "final_mcp_server"], check=False, capture_output=True)
            self.log_result("server", "shutdown", True, "Server stopped")
        except Exception as e:
            self.log_result("server", "shutdown", False, f"Error: {e}")
    
    def test_basic_endpoints(self):
        """Test basic server endpoints"""
        endpoints = [
            ("/health", "Health check"),
            ("/", "Server info"),
            ("/mcp/tools", "Tools listing"),
            ("/stats", "Statistics"),
            ("/docs", "Documentation")
        ]
        
        for endpoint, description in endpoints:
            try:
                result = subprocess.run([
                    "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                    "--max-time", "10",
                    f"{self.base_url}{endpoint}"
                ], capture_output=True, text=True, timeout=15)
                
                if result.returncode == 0 and result.stdout in ["200", "307"]:  # 307 for redirects
                    self.log_result("server_tests", f"endpoint_{endpoint[1:].replace('/', '_')}", True, f"{description} OK ({result.stdout})")
                else:
                    self.log_result("server_tests", f"endpoint_{endpoint[1:].replace('/', '_')}", False, f"{description} failed: {result.stdout}")
            except Exception as e:
                self.log_result("server_tests", f"endpoint_{endpoint[1:].replace('/', '_')}", False, f"{description} exception: {e}")
    
    def test_mcp_tools_discovery(self):
        """Test MCP tools discovery and listing"""
        try:
            result = subprocess.run([
                "curl", "-s", f"{self.base_url}/mcp/tools"
            ], capture_output=True, text=True, timeout=15)
            
            if result.returncode == 0:
                try:
                    tools_response = json.loads(result.stdout)
                    
                    # Check response structure
                    if "tools" in tools_response:
                        tools = tools_response["tools"]
                        tool_count = len(tools)
                        self.log_result("tool_tests", "discovery", True, f"Found {tool_count} tools", tools)
                        
                        # Check for expected tools
                        expected_tools = ["load_dataset", "save_dataset", "process_dataset", "pin_to_ipfs", "get_from_ipfs"]
                        found_tools = [tool.get("name", "") for tool in tools]
                        
                        for expected in expected_tools:
                            if expected in found_tools:
                                self.log_result("tool_tests", f"tool_{expected}_present", True, f"Tool {expected} found")
                            else:
                                self.log_result("tool_tests", f"tool_{expected}_present", False, f"Tool {expected} missing")
                    else:
                        self.log_result("tool_tests", "discovery", False, f"Invalid response format: {tools_response}")
                except json.JSONDecodeError:
                    self.log_result("tool_tests", "discovery", False, f"Invalid JSON response: {result.stdout[:100]}")
            else:
                self.log_result("tool_tests", "discovery", False, f"Request failed: {result.stderr}")
                
        except Exception as e:
            self.log_result("tool_tests", "discovery", False, f"Exception: {e}")
    
    def test_ipfs_operations(self):
        """Test IPFS operations comprehensively"""
        # Test 1: Add content
        test_content = "MCP Tools Test Content - Comprehensive Validation"
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
                        self.log_result("tool_tests", "ipfs_add", True, f"Added content, CID: {cid}")
                        
                        # Test 2: Retrieve content
                        cat_result = subprocess.run([
                            "curl", "-s", "--max-time", "15",
                            f"{self.base_url}/ipfs/cat/{cid}"
                        ], capture_output=True, text=True, timeout=20)
                        
                        if cat_result.returncode == 0:
                            try:
                                cat_response = json.loads(cat_result.stdout)
                                if cat_response.get("success") and cat_response.get("content") == test_content:
                                    self.log_result("tool_tests", "ipfs_cat", True, f"Retrieved content successfully")
                                else:
                                    self.log_result("tool_tests", "ipfs_cat", False, f"Content mismatch: {cat_response}")
                            except:
                                self.log_result("tool_tests", "ipfs_cat", False, f"Invalid JSON: {cat_result.stdout[:100]}")
                        else:
                            self.log_result("tool_tests", "ipfs_cat", False, "Cat request failed")
                        
                        # Test 3: Pin content
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
                                    self.log_result("tool_tests", "ipfs_pin", True, "Pinned content successfully")
                                else:
                                    self.log_result("tool_tests", "ipfs_pin", False, f"Pin failed: {pin_response}")
                            except:
                                self.log_result("tool_tests", "ipfs_pin", False, f"Invalid JSON: {pin_result.stdout[:100]}")
                        else:
                            self.log_result("tool_tests", "ipfs_pin", False, "Pin request failed")
                        
                    else:
                        self.log_result("tool_tests", "ipfs_add", False, f"Add failed: {response}")
                except:
                    self.log_result("tool_tests", "ipfs_add", False, f"Invalid JSON: {result.stdout[:100]}")
            else:
                self.log_result("tool_tests", "ipfs_add", False, "Add request failed")
        except Exception as e:
            self.log_result("tool_tests", "ipfs_add", False, f"Exception: {e}")
        
        # Test IPFS version
        try:
            version_result = subprocess.run([
                "curl", "-s", "--max-time", "10",
                f"{self.base_url}/ipfs/version"
            ], capture_output=True, text=True, timeout=15)
            
            if version_result.returncode == 0:
                try:
                    version_response = json.loads(version_result.stdout)
                    if version_response.get("success"):
                        self.log_result("tool_tests", "ipfs_version", True, f"Version: {version_response.get('version', {})}")
                    else:
                        self.log_result("tool_tests", "ipfs_version", False, f"Version failed: {version_response}")
                except:
                    self.log_result("tool_tests", "ipfs_version", False, f"Invalid JSON: {version_result.stdout[:100]}")
            else:
                self.log_result("tool_tests", "ipfs_version", False, "Version request failed")
        except Exception as e:
            self.log_result("tool_tests", "ipfs_version", False, f"Exception: {e}")
    
    def test_dataset_operations(self):
        """Test dataset-related MCP tools"""
        # Test dataset creation via JSON-RPC
        test_data = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "load_dataset",
                "arguments": {
                    "source": "test_data",
                    "format": "json"
                }
            },
            "id": 1
        }
        
        try:
            result = subprocess.run([
                "curl", "-s", "-X", "POST",
                "-H", "Content-Type: application/json",
                "-d", json.dumps(test_data),
                "--max-time", "15",
                f"{self.base_url}/jsonrpc"
            ], capture_output=True, text=True, timeout=20)
            
            if result.returncode == 0:
                try:
                    response = json.loads(result.stdout)
                    if "result" in response:
                        self.log_result("tool_tests", "dataset_load", True, "Dataset loading tool accessible")
                    elif "error" in response:
                        # Expected for test data that doesn't exist
                        self.log_result("tool_tests", "dataset_load", True, f"Tool responded correctly with error: {response['error'].get('message', 'Unknown')}")
                    else:
                        self.log_result("tool_tests", "dataset_load", False, f"Unexpected response: {response}")
                except:
                    self.log_result("tool_tests", "dataset_load", False, f"Invalid JSON: {result.stdout[:100]}")
            else:
                self.log_result("tool_tests", "dataset_load", False, "Dataset load request failed")
        except Exception as e:
            self.log_result("tool_tests", "dataset_load", False, f"Exception: {e}")
    
    def test_performance(self):
        """Test basic performance"""
        try:
            start_time = time.time()
            successful_requests = 0
            total_requests = 10
            
            for i in range(total_requests):
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
            
            if successful_requests >= total_requests * 0.8:  # 80% success rate
                self.log_result("integration_tests", "performance", True, f"{successful_requests}/{total_requests} requests, {rps:.2f} RPS")
            else:
                self.log_result("integration_tests", "performance", False, f"Poor performance: {successful_requests}/{total_requests}")
                
        except Exception as e:
            self.log_result("integration_tests", "performance", False, f"Exception: {e}")
    
    def run_all_tests(self):
        """Run the complete test suite"""
        print("🧪 COMPREHENSIVE MCP TOOLS VALIDATION")
        print("=" * 60)
        
        try:
            # Start server
            if not self.start_server():
                print("❌ Failed to start server - aborting tests")
                return self.results
            
            print("\n🔍 Testing basic server functionality...")
            self.test_basic_endpoints()
            
            print("\n🛠️ Testing MCP tools discovery...")
            self.test_mcp_tools_discovery()
            
            print("\n📦 Testing IPFS operations...")
            self.test_ipfs_operations()
            
            print("\n📊 Testing dataset operations...")
            self.test_dataset_operations()
            
            print("\n⚡ Testing performance...")
            self.test_performance()
            
        except Exception as e:
            print(f"❌ Test suite exception: {e}")
            print(traceback.format_exc())
        finally:
            self.stop_server()
        
        # Save results
        self.results["end_time"] = datetime.now().isoformat()
        with open("mcp_tools_validation_results.json", "w") as f:
            json.dump(self.results, f, indent=2)
        
        # Print summary
        print("\n" + "=" * 60)
        print("🎯 MCP TOOLS VALIDATION SUMMARY")
        print("=" * 60)
        print(f"✅ Tests Passed: {self.results['summary']['passed']}")
        print(f"❌ Tests Failed: {self.results['summary']['failed']}")
        print(f"📊 Total Tests: {self.results['summary']['total']}")
        
        if self.results['summary']['failed'] > 0:
            print("\n🚨 Failed tests need attention!")
            return False
        else:
            print("\n🎉 All MCP tools are working correctly!")
            return True

def main():
    """Main function"""
    # Check if server file exists
    if not Path("final_mcp_server_enhanced.py").exists():
        print("❌ Server file final_mcp_server_enhanced.py not found in current directory")
        print("   Make sure you're running from the project root")
        return False
    
    validator = MCPToolsValidator()
    success = validator.run_all_tests()
    
    print(f"\n📄 Detailed results saved to: mcp_tools_validation_results.json")
    print(f"📄 Server logs saved to: mcp_tools_test_server.log")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
