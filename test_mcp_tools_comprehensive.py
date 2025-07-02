usr/bin/env python3
"""
Comprehensive MCP Server Tools Test
==================================

This script tests all the MCP server tools by communicating directly
with the server using the MCP protocol over stdio.
"""

import json
import subprocess
import asyncio
import sys
import os
import tempfile
from datetime import datetime

class MCPTester:
    """Test harness for MCP server tools."""
    
    def __init__(self, server_path):
        self.server_path = server_path
        self.process = None
        self.request_id = 1
        
    async def start_server(self):
        """Start the MCP server process."""
        print(f"Starting MCP server: {self.server_path}")
        self.process = await asyncio.create_subprocess_exec(
            "python3", self.server_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        print("✓ MCP server started")
        
    async def stop_server(self):
        """Stop the MCP server process."""
        if self.process:
            self.process.terminate()
            await self.process.wait()
            print("✓ MCP server stopped")
    
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
        
        for tool in tools:
            print(f"  - {tool['name']}: {tool['description']}")
            
        return len(tools) > 0
    
    async def test_ipfs_add(self):
        """Test IPFS add tool."""
        print("\n=== Testing IPFS Add ===")
        
        # Test with content
        response = await self.send_request("tools/call", {
            "name": "ipfs_add",
            "arguments": {
                "content": "Hello, IPFS! This is a test message."
            }
        })
        
        if "error" in response:
            print(f"✗ IPFS add failed: {response['error']}")
            return False
            
        content = response.get("result", {}).get("content", [])
        if content:
            result = json.loads(content[0]["text"])
            if result.get("success"):
                print(f"✓ Content added with CID: {result.get('cid')}")
                print(f"✓ Size: {result.get('size')} bytes")
                return result.get('cid')
            else:
                print(f"✗ IPFS add failed: {result.get('error')}")
                
        return False
    
    async def test_ipfs_add_file(self):
        """Test IPFS add with file."""
        print("\n=== Testing IPFS Add File ===")
        
        # Create a temporary test file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("This is a test file for IPFS.\nIt contains multiple lines.\nAnd some test data.")
            temp_file = f.name
        
        try:
            response = await self.send_request("tools/call", {
                "name": "ipfs_add",
                "arguments": {
                    "file_path": temp_file
                }
            })
            
            if "error" in response:
                print(f"✗ IPFS add file failed: {response['error']}")
                return False
                
            content = response.get("result", {}).get("content", [])
            if content:
                result = json.loads(content[0]["text"])
                if result.get("success"):
                    print(f"✓ File added with CID: {result.get('cid')}")
                    print(f"✓ Size: {result.get('size')} bytes")
                    print(f"✓ Source: {result.get('source')}")
                    return result.get('cid')
                else:
                    print(f"✗ IPFS add file failed: {result.get('error')}")
                    
        finally:
            os.unlink(temp_file)
            
        return False
    
    async def test_ipfs_get(self, cid):
        """Test IPFS get tool."""
        print("\n=== Testing IPFS Get ===")
        
        if not cid:
            print("✗ No CID provided for get test")
            return False
            
        response = await self.send_request("tools/call", {
            "name": "ipfs_get",
            "arguments": {
                "cid": cid
            }
        })
        
        if "error" in response:
            print(f"✗ IPFS get failed: {response['error']}")
            return False
            
        content = response.get("result", {}).get("content", [])
        if content:
            result = json.loads(content[0]["text"])
            if result.get("success"):
                print(f"✓ Content retrieved for CID: {result.get('cid')}")
                print(f"✓ Size: {result.get('size')} bytes")
                print(f"✓ Content preview: {result.get('content', '')[:50]}...")
                return True
            else:
                print(f"✗ IPFS get failed: {result.get('error')}")
                
        return False
    
    async def test_ipfs_pin(self, cid):
        """Test IPFS pin tool."""
        print("\n=== Testing IPFS Pin ===")
        
        if not cid:
            print("✗ No CID provided for pin test")
            return False
            
        response = await self.send_request("tools/call", {
            "name": "ipfs_pin",
            "arguments": {
                "cid": cid,
                "recursive": True
            }
        })
        
        if "error" in response:
            print(f"✗ IPFS pin failed: {response['error']}")
            return False
            
        content = response.get("result", {}).get("content", [])
        if content:
            result = json.loads(content[0]["text"])
            if result.get("success"):
                print(f"✓ Content pinned for CID: {result.get('cid')}")
                print(f"✓ Recursive: {result.get('recursive')}")
                print(f"✓ Pinned: {result.get('pinned')}")
                return True
            else:
                print(f"✗ IPFS pin failed: {result.get('error')}")
                
        return False
    
    async def test_filesystem_health(self):
        """Test filesystem health tool."""
        print("\n=== Testing Filesystem Health ===")
        
        response = await self.send_request("tools/call", {
            "name": "filesystem_health",
            "arguments": {
                "path": "/"
            }
        })
        
        if "error" in response:
            print(f"✗ Filesystem health failed: {response['error']}")
            return False
            
        content = response.get("result", {}).get("content", [])
        if content:
            result = json.loads(content[0]["text"])
            if result.get("success"):
                print(f"✓ Path: {result.get('path')}")
                print(f"✓ Health status: {result.get('health_status')}")
                if 'used_percent' in result:
                    print(f"✓ Used: {result.get('used_percent')}%")
                    print(f"✓ Free: {result.get('free_bytes', 0) / (1024**3):.2f} GB")
                return True
            else:
                print(f"✗ Filesystem health failed: {result.get('error')}")
                
        return False
    
    async def test_system_health(self):
        """Test system health tool."""
        print("\n=== Testing System Health ===")
        
        response = await self.send_request("tools/call", {
            "name": "system_health",
            "arguments": {}
        })
        
        if "error" in response:
            print(f"✗ System health failed: {response['error']}")
            return False
            
        content = response.get("result", {}).get("content", [])
        if content:
            result = json.loads(content[0]["text"])
            if result.get("success"):
                print(f"✓ Server version: {result.get('server_version')}")
                if 'cpu_percent' in result:
                    print(f"✓ CPU usage: {result.get('cpu_percent')}%")
                    print(f"✓ Memory usage: {result.get('memory_percent')}%")
                if 'disk_usage' in result:
                    print(f"✓ Disk usage data available for {len(result['disk_usage'])} paths")
                return True
            else:
                print(f"✗ System health failed: {result.get('error')}")
                
        return False
    
    async def test_ipfs_cluster_status(self):
        """Test IPFS cluster status tool."""
        print("\n=== Testing IPFS Cluster Status ===")
        
        response = await self.send_request("tools/call", {
            "name": "ipfs_cluster_status",
            "arguments": {}
        })
        
        if "error" in response:
            print(f"✗ IPFS cluster status failed: {response['error']}")
            return False
            
        content = response.get("result", {}).get("content", [])
        if content:
            result = json.loads(content[0]["text"])
            if result.get("success"):
                print(f"✓ Cluster ID: {result.get('cluster_id')}")
                print(f"✓ Version: {result.get('version')}")
                peers = result.get('peers', [])
                print(f"✓ Peers: {len(peers)}")
                for peer in peers:
                    print(f"  - {peer.get('id')}: {peer.get('status')}")
                return True
            else:
                print(f"✗ IPFS cluster status failed: {result.get('error')}")
                
        return False
    
    async def run_all_tests(self):
        """Run all tests."""
        print("=" * 60)
        print("MCP Server Tools Comprehensive Test")
        print("=" * 60)
        print(f"Testing server: {self.server_path}")
        print(f"Test started: {datetime.now().isoformat()}")
        
        results = {}
        test_cid = None
        
        try:
            await self.start_server()
            
            # Basic protocol tests
            results['initialize'] = await self.test_initialize()
            results['tools_list'] = await self.test_tools_list()
            
            # IPFS tools tests
            test_cid = await self.test_ipfs_add()
            results['ipfs_add'] = bool(test_cid)
            
            file_cid = await self.test_ipfs_add_file()
            results['ipfs_add_file'] = bool(file_cid)
            
            # Use the CID from content add for subsequent tests
            if test_cid:
                results['ipfs_get'] = await self.test_ipfs_get(test_cid)
                results['ipfs_pin'] = await self.test_ipfs_pin(test_cid)
            else:
                results['ipfs_get'] = False
                results['ipfs_pin'] = False
            
            # System monitoring tools
            results['filesystem_health'] = await self.test_filesystem_health()
            results['system_health'] = await self.test_system_health()
            results['ipfs_cluster_status'] = await self.test_ipfs_cluster_status()
            
        except Exception as e:
            print(f"\n✗ Test execution failed: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            await self.stop_server()
        
        # Print summary
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for result in results.values() if result)
        total = len(results)
        
        for test_name, result in results.items():
            status = "✓ PASS" if result else "✗ FAIL"
            print(f"{test_name:20} {status}")
        
        print("-" * 60)
        print(f"Total: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All tests passed!")
            return True
        else:
            print("❌ Some tests failed!")
            return False


async def main():
    """Main test function."""
    server_path = "mcp_stdio_server.py"
    
    if not os.path.exists(server_path):
        print(f"Error: Server file not found: {server_path}")
        sys.exit(1)
    
    tester = MCPTester(server_path)
    success = await tester.run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
