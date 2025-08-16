#!/usr/bin/env python3
"""
Direct MCP Tools Test for ipfs-kit-enhanced
==========================================

This script tests all tools in the enhanced MCP server directly
by communicating with the server via stdio.
"""

import json
import subprocess
import asyncio
import sys
import os
import tempfile
from datetime import datetime

class DirectMCPTester:
    """Direct test harness for the enhanced MCP server."""
    
    def __init__(self, server_path):
        self.server_path = server_path
        self.process = None
        self.request_id = 1
        
    async def start_server(self):
        """Start the MCP server process."""
        print(f"Starting Enhanced MCP server: {self.server_path}")
        self.process = await asyncio.create_subprocess_exec(
            "python3", self.server_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        print("✓ Enhanced MCP server started")
        
    async def stop_server(self):
        """Stop the MCP server process."""
        if self.process:
            self.process.terminate()
            await self.process.wait()
            print("✓ Enhanced MCP server stopped")
    
    async def send_request(self, method, params=None):
        """Send a request to the MCP server."""
        if not self.process:
            raise Exception("Server not started")
            
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params or {}
        }
        
        self.request_id += 1
        
        # Send request
        request_json = json.dumps(request) + "\n"
        self.process.stdin.write(request_json.encode())
        await self.process.stdin.drain()
        
        # Read response
        response_line = await self.process.stdout.readline()
        if not response_line:
            raise Exception("No response from server")
            
        response = json.loads(response_line.decode().strip())
        return response
    
    async def test_initialize(self):
        """Test server initialization."""
        print("\n=== Testing Initialize ===")
        
        response = await self.send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0.0"}
        })
        
        if "error" in response:
            print(f"✗ Initialize failed: {response['error']}")
            return False
            
        result = response.get("result", {})
        print(f"✓ Protocol version: {result.get('protocolVersion')}")
        print(f"✓ Server name: {result.get('serverInfo', {}).get('name')}")
        print(f"✓ Server version: {result.get('serverInfo', {}).get('version')}")
        
        return True
    
    async def test_tools_list(self):
        """Test listing available tools."""
        print("\n=== Testing Tools List ===")
        
        response = await self.send_request("tools/list")
        
        if "error" in response:
            print(f"✗ Tools list failed: {response['error']}")
            return False
            
        tools = response.get("result", {}).get("tools", [])
        print(f"✓ Found {len(tools)} tools:")
        
        tool_names = []
        for tool in tools:
            print(f"  - {tool['name']}: {tool['description']}")
            tool_names.append(tool['name'])
            
        return tool_names
    
    async def test_tool(self, tool_name, arguments, description=""):
        """Test a specific tool."""
        print(f"\n=== Testing {tool_name} {description} ===")
        
        try:
            response = await self.send_request("tools/call", {
                "name": tool_name,
                "arguments": arguments
            })
            
            if "error" in response:
                print(f"✗ {tool_name} failed: {response['error']}")
                return False
                
            content = response.get("result", {}).get("content", [])
            if content:
                result = json.loads(content[0]["text"])
                if result.get("success"):
                    print(f"✓ {tool_name} succeeded")
                    # Print key information from the result
                    for key, value in result.items():
                        if key not in ["success", "timestamp"] and value is not None:
                            if isinstance(value, (dict, list)):
                                print(f"  {key}: {type(value).__name__} with {len(value)} items")
                            else:
                                print(f"  {key}: {str(value)[:100]}...")
                    return result
                else:
                    print(f"✗ {tool_name} failed: {result.get('error', 'Unknown error')}")
                    return False
            else:
                print(f"✗ {tool_name} returned no content")
                return False
                
        except Exception as e:
            print(f"✗ {tool_name} exception: {e}")
            return False
    
    async def run_comprehensive_test(self):
        """Run comprehensive tests for all tools."""
        print("=" * 80)
        print("Enhanced IPFS Kit MCP Server - Comprehensive Tool Test")
        print("=" * 80)
        print(f"Testing server: {self.server_path}")
        print(f"Test started: {datetime.now().isoformat()}")
        
        results = {}
        
        try:
            await self.start_server()
            
            # Basic protocol tests
            results['initialize'] = await self.test_initialize()
            tool_names = await self.test_tools_list()
            results['tools_list'] = bool(tool_names)
            
            # Test all IPFS tools
            print(f"\n{'='*80}")
            print("TESTING CORE IPFS OPERATIONS")
            print(f"{'='*80}")
            
            # Test ipfs_add with content
            add_result = await self.test_tool("ipfs_add", {
                "content": "Hello, Enhanced IPFS! This is test content for Phase 1."
            }, "(with content)")
            results['ipfs_add_content'] = bool(add_result)
            test_cid = add_result.get('cid') if add_result else None
            
            # Test ipfs_add with file
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
                f.write("This is a test file for Enhanced IPFS MCP server.\nPhase 1 implementation test.")
                temp_file = f.name
            
            try:
                file_add_result = await self.test_tool("ipfs_add", {
                    "file_path": temp_file
                }, "(with file)")
                results['ipfs_add_file'] = bool(file_add_result)
                file_cid = file_add_result.get('cid') if file_add_result else None
            finally:
                os.unlink(temp_file)
            
            # Test ipfs_cat/get
            if test_cid:
                results['ipfs_cat'] = bool(await self.test_tool("ipfs_cat", {"cid": test_cid}))
                results['ipfs_get'] = bool(await self.test_tool("ipfs_get", {"cid": test_cid}))
            else:
                results['ipfs_cat'] = bool(await self.test_tool("ipfs_cat", {"cid": "bafkreie1234"}))
                results['ipfs_get'] = bool(await self.test_tool("ipfs_get", {"cid": "bafkreie1234"}))
            
            # Test ipfs_pin
            pin_cid = test_cid or "bafkreie1234567890abcdef1234567890abcdef12345678"
            results['ipfs_pin'] = bool(await self.test_tool("ipfs_pin", {
                "cid": pin_cid,
                "recursive": True
            }))
            
            # Test ipfs_ls
            results['ipfs_ls'] = bool(await self.test_tool("ipfs_ls", {
                "cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",  # IPFS docs directory
                "headers": True
            }))
            
            # Test ipfs_stat  
            results['ipfs_stat'] = bool(await self.test_tool("ipfs_stat", {
                "cid": pin_cid
            }))
            
            # Test ipfs_version
            results['ipfs_version'] = bool(await self.test_tool("ipfs_version", {
                "all": True
            }))
            
            # Test ipfs_id
            results['ipfs_id'] = bool(await self.test_tool("ipfs_id", {}))
            
            # Test ipfs_list_pins
            results['ipfs_list_pins'] = bool(await self.test_tool("ipfs_list_pins", {
                "type": "all",
                "quiet": False
            }))
            
            # Test ipfs_unpin
            results['ipfs_unpin'] = bool(await self.test_tool("ipfs_unpin", {
                "cid": pin_cid,
                "recursive": True
            }))
            
            # Test ipfs_block_get
            results['ipfs_block_get'] = bool(await self.test_tool("ipfs_block_get", {
                "cid": pin_cid
            }))
            
            # Test ipfs_block_stat
            results['ipfs_block_stat'] = bool(await self.test_tool("ipfs_block_stat", {
                "cid": pin_cid
            }))
            
            # Test ipfs_dag_get
            results['ipfs_dag_get'] = bool(await self.test_tool("ipfs_dag_get", {
                "cid": pin_cid,
                "output_codec": "dag-json"
            }))
            
            # Test ipfs_object_stat
            results['ipfs_object_stat'] = bool(await self.test_tool("ipfs_object_stat", {
                "cid": pin_cid
            }))
            
            # Test system tools
            print(f"\n{'='*80}")
            print("TESTING SYSTEM MONITORING TOOLS")
            print(f"{'='*80}")
            
            results['filesystem_health'] = bool(await self.test_tool("filesystem_health", {
                "path": "/"
            }))
            
            results['system_health'] = bool(await self.test_tool("system_health", {}))
            
            results['ipfs_cluster_status'] = bool(await self.test_tool("ipfs_cluster_status", {}))
            
        except Exception as e:
            print(f"\n✗ Test execution failed: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            await self.stop_server()
        
        # Print comprehensive summary
        print(f"\n{'='*80}")
        print("COMPREHENSIVE TEST SUMMARY")
        print(f"{'='*80}")
        
        passed = sum(1 for result in results.values() if result)
        total = len(results)
        
        # Group results by category
        protocol_tests = {k: v for k, v in results.items() if k in ['initialize', 'tools_list']}
        ipfs_tests = {k: v for k, v in results.items() if k.startswith('ipfs_')}
        system_tests = {k: v for k, v in results.items() if k in ['filesystem_health', 'system_health', 'ipfs_cluster_status']}
        
        print("Protocol Tests:")
        for test_name, result in protocol_tests.items():
            status = "✓ PASS" if result else "✗ FAIL"
            print(f"  {test_name:20} {status}")
        
        print("\nIPFS Core Operations:")
        for test_name, result in ipfs_tests.items():
            status = "✓ PASS" if result else "✗ FAIL"
            print(f"  {test_name:20} {status}")
        
        print("\nSystem Monitoring Tools:")
        for test_name, result in system_tests.items():
            status = "✓ PASS" if result else "✗ FAIL"
            print(f"  {test_name:20} {status}")
        
        print(f"\n{'-'*80}")
        print(f"Overall: {passed}/{total} tests passed ({(passed/total)*100:.1f}%)")
        
        if passed == total:
            print("🎉 All tests passed! Enhanced MCP server is fully functional!")
            return True
        else:
            print(f"❌ {total-passed} tests failed. See details above.")
            return False


async def main():
    """Main test function."""
    server_path = "enhanced_mcp_server_phase1.py"
    
    if not os.path.exists(server_path):
        print(f"Error: Enhanced server file not found: {server_path}")
        sys.exit(1)
    
    tester = DirectMCPTester(server_path)
    success = await tester.run_comprehensive_test()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
