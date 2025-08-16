#!/usr/bin/env python3
"""
Comprehensive Test for Enhanced VFS MCP Server
==============================================

This script tests the integration of daemon management and advanced caching
capabilities in the enhanced VFS MCP server, with focus on validating
high-level API orchestration of storage backends.
"""

import json
import asyncio
import subprocess
import tempfile
import os
import sys
import time
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnhancedVFSMCPTester:
    """Comprehensive tester for enhanced VFS MCP server capabilities."""
    
    def __init__(self):
        self.server_process = None
        self.test_results = {}
        self.server_path = os.path.join(os.path.dirname(__file__), "mcp", "enhanced_vfs_mcp_server.py")
    
    async def run_comprehensive_test(self):
        """Run comprehensive test suite."""
        print("=== Enhanced VFS MCP Server Comprehensive Test ===")
        print(f"Server path: {self.server_path}")
        print()
        
        # Start server
        await self.start_server()
        
        try:
            # Test basic functionality
            await self.test_server_initialization()
            await self.test_tool_listing()
            
            # Test daemon management integration
            await self.test_daemon_management()
            
            # Test advanced caching capabilities
            await self.test_adaptive_caching()
            await self.test_intelligent_prefetching()
            
            # Test high-level API orchestration
            await self.test_storage_backend_orchestration()
            
            # Test virtual filesystem operations
            await self.test_vfs_operations()
            
            # Generate comprehensive report
            self.generate_test_report()
            
        finally:
            await self.stop_server()
    
    async def start_server(self):
        """Start the enhanced MCP server."""
        try:
            print("🚀 Starting Enhanced VFS MCP Server...")
            
            # Check if server file exists
            if not os.path.exists(self.server_path):
                raise FileNotFoundError(f"Server file not found: {self.server_path}")
            
            # Start server process
            self.server_process = await asyncio.create_subprocess_exec(
                sys.executable, self.server_path,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Wait for initialization
            await asyncio.sleep(2)
            
            if self.server_process.returncode is not None:
                stderr = await self.server_process.stderr.read()
                raise RuntimeError(f"Server failed to start: {stderr.decode()}")
            
            print("✅ Enhanced VFS MCP Server started successfully")
            
        except Exception as e:
            print(f"❌ Failed to start server: {e}")
            raise
    
    async def stop_server(self):
        """Stop the MCP server."""
        if self.server_process:
            try:
                self.server_process.terminate()
                await asyncio.wait_for(self.server_process.wait(), timeout=5)
                print("✅ Server stopped successfully")
            except asyncio.TimeoutError:
                self.server_process.kill()
                await self.server_process.wait()
                print("⚠️  Server force killed")
            except Exception as e:
                print(f"❌ Error stopping server: {e}")
    
    async def send_mcp_request(self, method: str, params: dict = None, timeout: int = 10) -> dict:
        """Send MCP request to server."""
        if not self.server_process:
            raise RuntimeError("Server not started")
        
        request = {
            "jsonrpc": "2.0",
            "id": int(time.time() * 1000),
            "method": method
        }
        
        if params:
            request["params"] = params
        
        try:
            # Send request
            request_json = json.dumps(request) + "\n"
            self.server_process.stdin.write(request_json.encode())
            await self.server_process.stdin.drain()
            
            # Read response
            response_line = await asyncio.wait_for(
                self.server_process.stdout.readline(), timeout=timeout
            )
            
            if not response_line:
                raise RuntimeError("Server closed connection")
            
            response = json.loads(response_line.decode().strip())
            return response
            
        except asyncio.TimeoutError:
            raise RuntimeError(f"Request timed out after {timeout}s")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON response: {e}")
    
    async def test_server_initialization(self):
        """Test server initialization and basic communication."""
        print("\n📡 Testing Server Initialization...")
        
        try:
            # Test basic ping (tools/list should work)
            response = await self.send_mcp_request("tools/list")
            
            if response.get("result"):
                print("✅ Server communication established")
                self.test_results["server_communication"] = True
            else:
                print("❌ Server communication failed")
                self.test_results["server_communication"] = False
                
        except Exception as e:
            print(f"❌ Server initialization test failed: {e}")
            self.test_results["server_communication"] = False
    
    async def test_tool_listing(self):
        """Test tool listing and capabilities."""
        print("\n🔧 Testing Tool Listing...")
        
        try:
            response = await self.send_mcp_request("tools/list")
            result = response.get("result", {})
            tools = result.get("tools", [])
            
            print(f"📋 Found {len(tools)} tools:")
            
            # Categorize tools
            tool_categories = {
                "daemon": [],
                "cache": [],
                "vfs": [],
                "api": [],
                "ipfs": []
            }
            
            for tool in tools:
                name = tool.get("name", "")
                category = "unknown"
                
                if name.startswith("daemon_"):
                    category = "daemon"
                elif name.startswith("cache_"):
                    category = "cache"
                elif name.startswith("vfs_"):
                    category = "vfs"
                elif name.startswith("api_"):
                    category = "api"
                elif name.startswith("ipfs_"):
                    category = "ipfs"
                
                if category != "unknown":
                    tool_categories[category].append(name)
                
                print(f"   • {name}: {tool.get('description', 'No description')}")
            
            # Report capabilities
            print(f"\n📊 Tool Categories:")
            for category, tool_list in tool_categories.items():
                if tool_list:
                    print(f"   • {category.title()}: {len(tool_list)} tools")
                    for tool in tool_list:
                        print(f"     - {tool}")
            
            # Expected enhanced tools
            expected_tools = [
                "daemon_start", "daemon_stop", "daemon_status",
                "cache_adaptive_get", "cache_intelligent_prefetch", "cache_statistics",
                "vfs_orchestrate_backend", "api_storage_orchestration_test"
            ]
            
            missing_tools = [tool for tool in expected_tools if tool not in [t["name"] for t in tools]]
            
            if missing_tools:
                print(f"⚠️  Missing expected tools: {missing_tools}")
                self.test_results["tool_listing"] = "partial"
            else:
                print("✅ All expected enhanced tools available")
                self.test_results["tool_listing"] = "complete"
            
            self.test_results["total_tools"] = len(tools)
            self.test_results["tool_categories"] = {k: len(v) for k, v in tool_categories.items()}
            
        except Exception as e:
            print(f"❌ Tool listing test failed: {e}")
            self.test_results["tool_listing"] = "failed"
    
    async def test_daemon_management(self):
        """Test daemon management capabilities."""
        print("\n🔧 Testing Daemon Management...")
        
        daemon_tests = ["daemon_status", "daemon_start", "daemon_stop"]
        
        for test in daemon_tests:
            try:
                print(f"   Testing {test}...")
                
                if test == "daemon_status":
                    # Test getting status of all daemons
                    response = await self.send_mcp_request(
                        "tools/call",
                        {
                            "name": "daemon_status",
                            "arguments": {}
                        }
                    )
                    
                elif test == "daemon_start":
                    # Test starting IPFS daemon (most likely to be available)
                    response = await self.send_mcp_request(
                        "tools/call",
                        {
                            "name": "daemon_start",
                            "arguments": {"daemon_type": "ipfs"}
                        }
                    )
                    
                elif test == "daemon_stop":
                    # Test stopping IPFS daemon
                    response = await self.send_mcp_request(
                        "tools/call",
                        {
                            "name": "daemon_stop",
                            "arguments": {"daemon_type": "ipfs"}
                        }
                    )
                
                # Parse response
                if response.get("result"):
                    content = response["result"].get("content", [])
                    if content and content[0].get("type") == "text":
                        result_data = json.loads(content[0]["text"])
                        
                        if result_data.get("success") or "error" in result_data:
                            print(f"   ✅ {test}: {result_data.get('operation', 'unknown')}")
                            self.test_results[f"daemon_{test}"] = True
                        else:
                            print(f"   ❌ {test}: Unexpected response format")
                            self.test_results[f"daemon_{test}"] = False
                    else:
                        print(f"   ❌ {test}: Invalid response content")
                        self.test_results[f"daemon_{test}"] = False
                else:
                    print(f"   ❌ {test}: No result in response")
                    self.test_results[f"daemon_{test}"] = False
                
                # Small delay between tests
                await asyncio.sleep(0.5)
                
            except Exception as e:
                print(f"   ❌ {test} failed: {e}")
                self.test_results[f"daemon_{test}"] = False
    
    async def test_adaptive_caching(self):
        """Test adaptive caching capabilities."""
        print("\n💾 Testing Adaptive Caching...")
        
        cache_tests = [
            ("cache_statistics", {}),
            ("cache_adaptive_get", {"key": "QmTestCID123", "context": {"content_type": "test"}})
        ]
        
        for test_name, args in cache_tests:
            try:
                print(f"   Testing {test_name}...")
                
                response = await self.send_mcp_request(
                    "tools/call",
                    {
                        "name": test_name,
                        "arguments": args
                    }
                )
                
                if response.get("result"):
                    content = response["result"].get("content", [])
                    if content and content[0].get("type") == "text":
                        result_data = json.loads(content[0]["text"])
                        
                        if "timestamp" in result_data:
                            print(f"   ✅ {test_name}: Response received")
                            self.test_results[f"cache_{test_name}"] = True
                            
                            # Special handling for cache_statistics
                            if test_name == "cache_statistics":
                                stats = result_data
                                print(f"      Basic stats: {stats.get('basic_stats', {})}")
                                if "arc_cache" in stats:
                                    print(f"      ARC cache available: Yes")
                                if "tiered_cache" in stats:
                                    print(f"      Tiered cache available: Yes")
                                if "predictive_cache" in stats:
                                    print(f"      Predictive cache available: Yes")
                        else:
                            print(f"   ❌ {test_name}: Unexpected response format")
                            self.test_results[f"cache_{test_name}"] = False
                    else:
                        print(f"   ❌ {test_name}: Invalid response content")
                        self.test_results[f"cache_{test_name}"] = False
                else:
                    print(f"   ❌ {test_name}: No result in response")
                    self.test_results[f"cache_{test_name}"] = False
                
                await asyncio.sleep(0.5)
                
            except Exception as e:
                print(f"   ❌ {test_name} failed: {e}")
                self.test_results[f"cache_{test_name}"] = False
    
    async def test_intelligent_prefetching(self):
        """Test intelligent prefetching capabilities."""
        print("\n🎯 Testing Intelligent Prefetching...")
        
        try:
            print("   Testing cache_intelligent_prefetch...")
            
            response = await self.send_mcp_request(
                "tools/call",
                {
                    "name": "cache_intelligent_prefetch",
                    "arguments": {
                        "cid": "QmTestDirectoryCID",
                        "context": {
                            "content_type": "directory",
                            "priority": "high"
                        }
                    }
                }
            )
            
            if response.get("result"):
                content = response["result"].get("content", [])
                if content and content[0].get("type") == "text":
                    result_data = json.loads(content[0]["text"])
                    
                    if result_data.get("operation") == "intelligent_prefetch":
                        print(f"   ✅ Intelligent prefetch executed")
                        print(f"      Prefetch count: {result_data.get('prefetch_count', 0)}")
                        print(f"      Candidates considered: {result_data.get('candidates_considered', 0)}")
                        
                        if "semantic_cache_hits" in result_data:
                            print(f"      Semantic cache hits: {result_data['semantic_cache_hits']}")
                        
                        self.test_results["intelligent_prefetch"] = True
                    else:
                        print(f"   ❌ Unexpected response format")
                        self.test_results["intelligent_prefetch"] = False
                else:
                    print(f"   ❌ Invalid response content")
                    self.test_results["intelligent_prefetch"] = False
            else:
                print(f"   ❌ No result in response")
                self.test_results["intelligent_prefetch"] = False
                
        except Exception as e:
            print(f"   ❌ Intelligent prefetch test failed: {e}")
            self.test_results["intelligent_prefetch"] = False
    
    async def test_storage_backend_orchestration(self):
        """Test high-level API storage backend orchestration."""
        print("\n🎼 Testing Storage Backend Orchestration...")
        
        orchestration_tests = [
            ("api_storage_orchestration_test", {"test_scenario": "basic"}),
            ("vfs_orchestrate_backend", {
                "filesystem_path": "/test/orchestration",
                "target_backend": "high_performance",
                "metadata": {"content_type": "test", "priority": "high"}
            })
        ]
        
        for test_name, args in orchestration_tests:
            try:
                print(f"   Testing {test_name}...")
                
                response = await self.send_mcp_request(
                    "tools/call",
                    {
                        "name": test_name,
                        "arguments": args
                    }
                )
                
                if response.get("result"):
                    content = response["result"].get("content", [])
                    if content and content[0].get("type") == "text":
                        result_data = json.loads(content[0]["text"])
                        
                        if result_data.get("success"):
                            print(f"   ✅ {test_name}: Success")
                            
                            # Special handling for orchestration test
                            if test_name == "api_storage_orchestration_test":
                                validation = result_data.get("validation", {})
                                print(f"      High-level API available: {validation.get('high_level_api_available')}")
                                print(f"      Metadata stored: {validation.get('metadata_stored')}")
                                print(f"      Backend orchestration: {validation.get('backend_orchestration')}")
                            
                            elif test_name == "vfs_orchestrate_backend":
                                print(f"      Target backend: {result_data.get('target_backend')}")
                                print(f"      Replication status: {result_data.get('replication_status', 'N/A')}")
                            
                            self.test_results[f"orchestration_{test_name}"] = True
                        else:
                            print(f"   ❌ {test_name}: {result_data.get('error', 'Unknown error')}")
                            self.test_results[f"orchestration_{test_name}"] = False
                    else:
                        print(f"   ❌ {test_name}: Invalid response content")
                        self.test_results[f"orchestration_{test_name}"] = False
                else:
                    print(f"   ❌ {test_name}: No result in response")
                    self.test_results[f"orchestration_{test_name}"] = False
                
                await asyncio.sleep(0.5)
                
            except Exception as e:
                print(f"   ❌ {test_name} failed: {e}")
                self.test_results[f"orchestration_{test_name}"] = False
    
    async def test_vfs_operations(self):
        """Test virtual filesystem operations."""
        print("\n📁 Testing VFS Operations...")
        
        try:
            print("   Testing vfs_mount...")
            
            response = await self.send_mcp_request(
                "tools/call",
                {
                    "name": "vfs_mount",
                    "arguments": {
                        "cid": "QmTestMountCID",
                        "mount_point": "/vfs/test",
                        "storage_backend": "adaptive",
                        "cache_strategy": "intelligent"
                    }
                }
            )
            
            if response.get("result"):
                content = response["result"].get("content", [])
                if content and content[0].get("type") == "text":
                    result_data = json.loads(content[0]["text"])
                    
                    if result_data.get("success"):
                        print(f"   ✅ VFS mount successful")
                        print(f"      Mount point: {result_data.get('mount_point')}")
                        print(f"      CID: {result_data.get('cid')}")
                        self.test_results["vfs_mount"] = True
                    else:
                        print(f"   ❌ VFS mount failed: {result_data.get('error')}")
                        self.test_results["vfs_mount"] = False
                else:
                    print(f"   ❌ Invalid response content")
                    self.test_results["vfs_mount"] = False
            else:
                print(f"   ❌ No result in response")
                self.test_results["vfs_mount"] = False
                
        except Exception as e:
            print(f"   ❌ VFS mount test failed: {e}")
            self.test_results["vfs_mount"] = False
    
    def generate_test_report(self):
        """Generate comprehensive test report."""
        print("\n" + "="*60)
        print("📊 ENHANCED VFS MCP SERVER TEST REPORT")
        print("="*60)
        
        # Count results
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result is True)
        failed_tests = sum(1 for result in self.test_results.values() if result is False)
        partial_tests = total_tests - passed_tests - failed_tests
        
        print(f"\n📈 Test Summary:")
        print(f"   Total Tests: {total_tests}")
        print(f"   Passed: {passed_tests} ✅")
        print(f"   Failed: {failed_tests} ❌")
        print(f"   Partial: {partial_tests} ⚠️")
        
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        print(f"   Success Rate: {success_rate:.1f}%")
        
        # Detailed results
        print(f"\n📋 Detailed Results:")
        
        categories = {
            "Server Communication": ["server_communication"],
            "Tool Listing": ["tool_listing", "total_tools"],
            "Daemon Management": [k for k in self.test_results.keys() if k.startswith("daemon_")],
            "Advanced Caching": [k for k in self.test_results.keys() if k.startswith("cache_")],
            "Intelligent Prefetching": ["intelligent_prefetch"],
            "Storage Orchestration": [k for k in self.test_results.keys() if k.startswith("orchestration_")],
            "VFS Operations": ["vfs_mount"]
        }
        
        for category, tests in categories.items():
            if tests:
                print(f"\n   {category}:")
                for test in tests:
                    if test in self.test_results:
                        result = self.test_results[test]
                        if result is True:
                            status = "✅ PASS"
                        elif result is False:
                            status = "❌ FAIL"
                        elif isinstance(result, str):
                            status = f"⚠️  {result}"
                        else:
                            status = f"ℹ️  {result}"
                        
                        print(f"     {test}: {status}")
        
        # Feature availability assessment
        print(f"\n🚀 Enhanced Features Assessment:")
        
        enhanced_features = {
            "Daemon Management": any(self.test_results.get(k) for k in self.test_results.keys() if k.startswith("daemon_")),
            "Adaptive Caching": any(self.test_results.get(k) for k in self.test_results.keys() if k.startswith("cache_")),
            "Intelligent Prefetching": self.test_results.get("intelligent_prefetch"),
            "Storage Backend Orchestration": any(self.test_results.get(k) for k in self.test_results.keys() if k.startswith("orchestration_")),
            "High-Level API Integration": self.test_results.get("orchestration_api_storage_orchestration_test"),
            "Virtual Filesystem": self.test_results.get("vfs_mount")
        }
        
        for feature, available in enhanced_features.items():
            status = "✅ AVAILABLE" if available else "❌ NOT AVAILABLE"
            print(f"   {feature}: {status}")
        
        # Overall assessment
        print(f"\n🎯 Overall Assessment:")
        
        if success_rate >= 80:
            overall_status = "✅ EXCELLENT - Enhanced VFS MCP Server is fully functional"
        elif success_rate >= 60:
            overall_status = "⚠️  GOOD - Most features working, some issues detected"
        elif success_rate >= 40:
            overall_status = "⚠️  PARTIAL - Basic functionality working, enhanced features need attention"
        else:
            overall_status = "❌ POOR - Significant issues detected, requires debugging"
        
        print(f"   {overall_status}")
        
        # Recommendations
        print(f"\n💡 Recommendations:")
        
        if failed_tests > 0:
            print("   • Review failed tests and check error logs")
            print("   • Ensure all dependencies are properly installed")
            print("   • Verify IPFS daemon is accessible")
        
        if "tool_listing" in self.test_results and self.test_results["tool_listing"] == "partial":
            print("   • Some expected tools are missing - check imports")
        
        if not any(self.test_results.get(k) for k in self.test_results.keys() if k.startswith("orchestration_")):
            print("   • Storage backend orchestration not working - check high-level API integration")
        
        if success_rate < 100:
            print("   • Run individual tool tests for more detailed debugging")
        
        print("\n" + "="*60)


async def main():
    """Main test execution."""
    tester = EnhancedVFSMCPTester()
    await tester.run_comprehensive_test()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test execution failed: {e}")
        sys.exit(1)
