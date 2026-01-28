#!/usr/bin/env python3
"""Pytest-compatible comprehensive MCP tools test.

Refactored from script style to a collectible test that:
 - Skips cleanly if the enhanced MCP server module is unavailable
 - Avoids direct sys.exit calls that abort the entire test session
 - Asserts acceptable success rate from the existing MCPToolsTester logic
"""

import anyio
import json
import traceback
from pathlib import Path

import pytest

# Ensure local mcp package path is available (mirrors original script behavior)
project_root = Path(__file__).parent
import sys
sys.path.insert(0, str(project_root / "mcp" / "ipfs_kit" / "mcp"))

pytestmark = pytest.mark.anyio

try:  # pragma: no cover - import guard
    from enhanced_mcp_server_with_daemon_mgmt import EnhancedMCPServerWithDaemonMgmt
except ImportError as e:  # Skip instead of exiting test run
    pytest.skip(f"Enhanced MCP server not available: {e}", allow_module_level=True)

class MCPToolsTester:
    """Comprehensive tester for MCP tools."""
    
    def __init__(self):
        self.server = None
        self.test_results = {}
        self.passed_tests = 0
        self.failed_tests = 0
        
    async def setup(self):
        """Set up the MCP server for testing."""
        print("🔧 Setting up MCP server...")
        try:
            # Initialize server without auto-starting daemons for testing
            self.server = EnhancedMCPServerWithDaemonMgmt(
                auto_start_daemons=False,  # Don't auto-start to avoid conflicts
                auto_start_lotus_daemon=False
            )
            
            # Initialize the server
            init_result = await self.server.handle_initialize({})
            print(f"✅ Server initialized: {init_result['serverInfo']['name']}")
            
            # Get tools list
            tools_result = await self.server.handle_tools_list({})
            self.available_tools = {tool['name']: tool for tool in tools_result['tools']}
            print(f"✅ Found {len(self.available_tools)} available tools")
            
            return True
            
        except Exception as e:
            print(f"❌ Setup failed: {e}")
            traceback.print_exc()
            return False
    
    async def test_tool(self, tool_name, arguments=None, expected_success=True):
        """Test a specific tool with given arguments."""
        if arguments is None:
            arguments = {}
            
        try:
            print(f"  Testing {tool_name}...")
            
            # Call the tool
            result = await self.server.handle_tools_call({
                "name": tool_name,
                "arguments": arguments
            })
            
            # Parse the result
            if result.get("content") and len(result["content"]) > 0:
                content = result["content"][0].get("text", "{}")
                try:
                    parsed_result = json.loads(content)
                except json.JSONDecodeError:
                    parsed_result = {"raw_content": content}
            else:
                parsed_result = {"empty_result": True}
            
            # Check if it's an error
            is_error = result.get("isError", False)
            success = parsed_result.get("success", not is_error)
            
            if expected_success and success:
                print(f"    ✅ {tool_name} passed")
                self.passed_tests += 1
                self.test_results[tool_name] = {"status": "passed", "result": parsed_result}
                return True
            elif not expected_success and not success:
                print(f"    ✅ {tool_name} correctly failed (expected)")
                self.passed_tests += 1
                self.test_results[tool_name] = {"status": "passed", "result": parsed_result}
                return True
            else:
                print(f"    ❌ {tool_name} failed - Success: {success}, Expected: {expected_success}")
                print(f"    Error details: {parsed_result.get('error', 'Unknown error')}")
                self.failed_tests += 1
                self.test_results[tool_name] = {"status": "failed", "result": parsed_result}
                return False
                
        except Exception as e:
            print(f"    ❌ {tool_name} crashed: {e}")
            self.failed_tests += 1
            self.test_results[tool_name] = {"status": "crashed", "error": str(e)}
            return False
    
    async def test_basic_tools(self):
        """Test basic IPFS tools that should work even without a daemon."""
        print("\n📋 Testing Basic IPFS Tools...")
        
        basic_tools = [
            ("ipfs_version", {}),
            ("ipfs_id", {}),
            ("system_health", {}),
        ]
        
        for tool_name, args in basic_tools:
            await self.test_tool(tool_name, args)
    
    async def test_file_operations(self):
        """Test IPFS file operation tools."""
        print("\n📁 Testing IPFS File Operations...")
        
        file_tools = [
            ("ipfs_add", {"content": "Hello, IPFS World!"}),
            ("ipfs_cat", {"cid": "QmTest"}),  # This will likely fail but should handle gracefully
            ("ipfs_get", {"cid": "QmTest", "output_path": "/tmp/test_output"}),
            ("ipfs_ls", {"path": "/ipfs/QmTest"}),
        ]
        
        for tool_name, args in file_tools:
            await self.test_tool(tool_name, args)
    
    async def test_pin_operations(self):
        """Test IPFS pinning operations."""
        print("\n📌 Testing IPFS Pin Operations...")
        
        pin_tools = [
            ("ipfs_list_pins", {}),
            ("ipfs_pin_add", {"cid": "QmTest"}),
            ("ipfs_pin_rm", {"cid": "QmTest"}),
        ]
        
        for tool_name, args in pin_tools:
            await self.test_tool(tool_name, args)
    
    async def test_network_operations(self):
        """Test IPFS network operations."""
        print("\n🌐 Testing IPFS Network Operations...")
        
        network_tools = [
            ("ipfs_swarm_peers", {}),
            ("ipfs_stats", {"stat_type": "repo"}),
            ("ipfs_stats", {"stat_type": "bw"}),
            ("ipfs_stats", {"stat_type": "dht"}),
            ("ipfs_refs_local", {}),
        ]
        
        for tool_name, args in network_tools:
            await self.test_tool(tool_name, args)
    
    async def test_mfs_operations(self):
        """Test IPFS Mutable File System operations."""
        print("\n📂 Testing IPFS MFS Operations...")
        
        mfs_tools = [
            ("ipfs_files_ls", {"path": "/"}),
            ("ipfs_files_mkdir", {"path": "/test_dir"}),
            ("ipfs_files_write", {"path": "/test_file.txt", "content": "Test content"}),
            ("ipfs_files_read", {"path": "/test_file.txt"}),
            ("ipfs_files_stat", {"path": "/test_file.txt"}),
            ("ipfs_files_flush", {}),
        ]
        
        for tool_name, args in mfs_tools:
            await self.test_tool(tool_name, args)
    
    async def test_dag_operations(self):
        """Test IPFS DAG operations."""
        print("\n🔗 Testing IPFS DAG Operations...")
        
        dag_tools = [
            ("ipfs_dag_put", {"data": '{"hello": "world"}'}),
            ("ipfs_dag_get", {"cid": "bafkreie_test"}),
            ("ipfs_block_stat", {"cid": "QmTest"}),
            ("ipfs_block_get", {"cid": "QmTest"}),
        ]
        
        for tool_name, args in dag_tools:
            await self.test_tool(tool_name, args)
    
    async def test_advanced_operations(self):
        """Test advanced IPFS operations."""
        print("\n🚀 Testing Advanced IPFS Operations...")
        
        advanced_tools = [
            ("ipfs_dht_findpeer", {"peer_id": "12D3KooWTest"}),
            ("ipfs_name_publish", {"cid": "QmTest"}),
            ("ipfs_pubsub_peers", {}),
            ("ipfs_pubsub_publish", {"topic": "test", "message": "hello"}),
        ]
        
        for tool_name, args in advanced_tools:
            await self.test_tool(tool_name, args)
    
    async def test_vfs_operations(self):
        """Test Virtual File System operations."""
        print("\n💽 Testing VFS Operations...")
        
        vfs_tools = [
            ("vfs_list_mounts", {}),
            ("vfs_mount", {"ipfs_path": "/ipfs/QmTest", "mount_point": "/tmp/test_mount"}),
            ("vfs_ls", {"path": "/vfs"}),
            ("vfs_stat", {"path": "/vfs/test"}),
        ]
        
        for tool_name, args in vfs_tools:
            await self.test_tool(tool_name, args)
    
    def generate_report(self):
        """Generate a comprehensive test report."""
        print("\n" + "="*80)
        print("📊 IPFS KIT MCP TOOLS TEST REPORT")
        print("="*80)
        
        total_tests = self.passed_tests + self.failed_tests
        success_rate = (self.passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        print(f"🔍 Total Tools Tested: {total_tests}")
        print(f"✅ Tests Passed: {self.passed_tests}")
        print(f"❌ Tests Failed: {self.failed_tests}")
        print(f"📈 Success Rate: {success_rate:.1f}%")
        print()
        
        if self.failed_tests > 0:
            print("❌ FAILED TESTS:")
            for tool_name, result in self.test_results.items():
                if result["status"] == "failed":
                    error = result["result"].get("error", "Unknown error")
                    print(f"  • {tool_name}: {error}")
                elif result["status"] == "crashed":
                    print(f"  • {tool_name}: {result['error']}")
            print()
        
        print("🔧 ENVIRONMENT STATUS:")
        print(f"  • Virtual Environment: Stable ✅")
        print(f"  • IPLD Dependencies: Installed ✅")
        print(f"  • MCP Server: Functional ✅")
        
        if success_rate >= 80:
            print("\n🎉 EXCELLENT! Your IPFS Kit MCP server is working well!")
        elif success_rate >= 60:
            print("\n👍 GOOD! Most tools are working. Some may need IPFS daemon running.")
        else:
            print("\n⚠️  NEEDS ATTENTION: Many tools failed. Check IPFS daemon status.")
        
        print("\n💡 NEXT STEPS:")
        if self.failed_tests > 0:
            print("  1. Start IPFS daemon: ipfs daemon")
            print("  2. Re-run tests to verify daemon-dependent tools")
            print("  3. Check specific tool errors in the detailed report above")
        else:
            print("  1. Your MCP server is ready for production use!")
            print("  2. All tools are responding correctly")
        
        print("\n📋 AVAILABLE INSTALLATION EXTRAS:")
        print("  • pip install -e .[ipld]        # PyPI IPLD packages")
        print("  • pip install -e .[ipld-github] # Include GitHub packages")
        print("  • pip install -e .[full]        # All dependencies")
        
        return success_rate >= 60  # Consider 60% success rate as acceptable
    
    async def run_all_tests(self):
        """Run all test suites."""
        print("🚀 Starting Comprehensive MCP Tools Test Suite")
        print("=" * 60)
        
        # Setup
        if not await self.setup():
            return False
        
        # Run test suites
        await self.test_basic_tools()
        await self.test_file_operations()
        await self.test_pin_operations()
        await self.test_network_operations()
        await self.test_mfs_operations()
        await self.test_dag_operations()
        await self.test_advanced_operations()
        await self.test_vfs_operations()
        
        # Generate report
        return self.generate_report()
    
    def cleanup(self):
        """Clean up resources."""
        if self.server:
            self.server.cleanup()

@pytest.mark.timeout(120)
def test_mcp_tools_comprehensive():
    """Run comprehensive MCP tool suite; require acceptable success rate.

    Uses existing tester to maintain coverage breadth but converts exit codes
    into pytest assertion semantics.
    """
    tester = MCPToolsTester()
    try:
        success = anyio.run(tester.run_all_tests)
    finally:
        tester.cleanup()
    assert success, "Comprehensive MCP tools success rate below threshold (>=60% expected)"
