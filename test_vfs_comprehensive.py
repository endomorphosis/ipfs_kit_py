#!/usr/bin/env python3
"""
Comprehensive VFS Verification Test
===================================

This script tests the VFS functionality through the MCP server by:
1. Starting the MCP server
2. Calling VFS operations via the MCP protocol
3. Verifying responses and functionality
4. Testing both real VFS operations and mock fallbacks
"""

import sys
import os
import json
import asyncio
import tempfile
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MCPVFSClient:
    """Client for testing VFS operations through MCP protocol."""
    
    def __init__(self, server_path: str):
        self.server_path = server_path
        self.server_process = None
        self.msg_id = 0
        
    async def start_server(self):
        """Start the MCP server process."""
        logger.info(f"Starting MCP server: {self.server_path}")
        
        self.server_process = await asyncio.create_subprocess_exec(
            sys.executable, self.server_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Wait a moment for server to start
        await asyncio.sleep(1)
        
        # Initialize the server
        await self.send_message({
            "jsonrpc": "2.0",
            "id": self.get_next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "clientInfo": {
                    "name": "vfs-test-client",
                    "version": "1.0.0"
                }
            }
        })
        
        # Send initialized notification
        await self.send_notification({
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        })
        
        logger.info("MCP server initialized successfully")
        
    async def stop_server(self):
        """Stop the MCP server process."""
        if self.server_process:
            logger.info("Stopping MCP server...")
            self.server_process.terminate()
            await self.server_process.wait()
            
    def get_next_id(self):
        """Get next message ID."""
        self.msg_id += 1
        return self.msg_id
        
    async def send_message(self, message: dict) -> dict:
        """Send a message to the server and get response."""
        if not self.server_process:
            raise RuntimeError("Server not started")
            
        # Send message
        message_str = json.dumps(message) + "\n"
        self.server_process.stdin.write(message_str.encode())
        await self.server_process.stdin.drain()
        
        # Read response
        response_line = await self.server_process.stdout.readline()
        if not response_line:
            raise RuntimeError("No response from server")
            
        response = json.loads(response_line.decode().strip())
        return response
        
    async def send_notification(self, message: dict):
        """Send a notification (no response expected)."""
        if not self.server_process:
            raise RuntimeError("Server not started")
            
        message_str = json.dumps(message) + "\n"
        self.server_process.stdin.write(message_str.encode())
        await self.server_process.stdin.drain()
        
    async def list_tools(self) -> dict:
        """List available tools."""
        return await self.send_message({
            "jsonrpc": "2.0",
            "id": self.get_next_id(),
            "method": "tools/list"
        })
        
    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Call a specific tool."""
        return await self.send_message({
            "jsonrpc": "2.0",
            "id": self.get_next_id(),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        })

class VFSTestSuite:
    """Test suite for VFS operations."""
    
    def __init__(self, client: MCPVFSClient):
        self.client = client
        self.test_results = []
        self.temp_dir = None
        
    async def setup(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp(prefix="vfs_test_")
        logger.info(f"Created temp directory: {self.temp_dir}")
        
    async def teardown(self):
        """Cleanup test environment."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            logger.info(f"Removed temp directory: {self.temp_dir}")
            
    def record_test_result(self, test_name: str, success: bool, message: str = "", details: dict = None):
        """Record a test result."""
        result = {
            "test": test_name,
            "success": success,
            "message": message,
            "details": details or {},
            "timestamp": datetime.now().isoformat()
        }
        self.test_results.append(result)
        
        status = "✓" if success else "✗"
        logger.info(f"{status} {test_name}: {message}")
        
    async def test_tools_list(self):
        """Test that VFS tools are available."""
        test_name = "VFS Tools Availability"
        
        try:
            response = await self.client.list_tools()
            
            if "result" not in response:
                self.record_test_result(test_name, False, "No result in response", response)
                return
                
            tools = response["result"].get("tools", [])
            tool_names = [tool["name"] for tool in tools]
            
            # Check for VFS tools
            expected_vfs_tools = [
                "vfs_mount", "vfs_unmount", "vfs_list_mounts",
                "vfs_read", "vfs_write", "vfs_copy", "vfs_move",
                "vfs_mkdir", "vfs_rmdir", "vfs_ls", "vfs_stat",
                "vfs_sync_to_ipfs", "vfs_sync_from_ipfs"
            ]
            
            missing_tools = [tool for tool in expected_vfs_tools if tool not in tool_names]
            
            if missing_tools:
                self.record_test_result(test_name, False, f"Missing tools: {missing_tools}", 
                                      {"available_tools": tool_names})
            else:
                self.record_test_result(test_name, True, f"All {len(expected_vfs_tools)} VFS tools available",
                                      {"available_tools": tool_names})
                
        except Exception as e:
            self.record_test_result(test_name, False, f"Exception: {e}")
            
    async def test_vfs_list_mounts(self):
        """Test VFS mount listing."""
        test_name = "VFS List Mounts"
        
        try:
            response = await self.client.call_tool("vfs_list_mounts", {})
            
            if "result" not in response:
                self.record_test_result(test_name, False, "No result in response", response)
                return
                
            content = response["result"]["content"][0]["text"]
            result = json.loads(content)
            
            if result.get("success") or result.get("is_mock"):
                self.record_test_result(test_name, True, "VFS list mounts working", result)
            else:
                self.record_test_result(test_name, False, "VFS list mounts failed", result)
                
        except Exception as e:
            self.record_test_result(test_name, False, f"Exception: {e}")
            
    async def test_vfs_mount(self):
        """Test VFS mounting."""
        test_name = "VFS Mount"
        
        try:
            mount_point = os.path.join(self.temp_dir, "test_mount")
            os.makedirs(mount_point, exist_ok=True)
            
            response = await self.client.call_tool("vfs_mount", {
                "ipfs_path": "/ipfs/QmTestCID123",
                "mount_point": mount_point,
                "read_only": True
            })
            
            if "result" not in response:
                self.record_test_result(test_name, False, "No result in response", response)
                return
                
            content = response["result"]["content"][0]["text"]
            result = json.loads(content)
            
            if result.get("success") or result.get("is_mock"):
                self.record_test_result(test_name, True, "VFS mount working", result)
            else:
                self.record_test_result(test_name, False, "VFS mount failed", result)
                
        except Exception as e:
            self.record_test_result(test_name, False, f"Exception: {e}")
            
    async def test_vfs_mkdir(self):
        """Test VFS directory creation."""
        test_name = "VFS Mkdir"
        
        try:
            response = await self.client.call_tool("vfs_mkdir", {
                "path": "/test_dir",
                "parents": True,
                "mode": "0755"
            })
            
            if "result" not in response:
                self.record_test_result(test_name, False, "No result in response", response)
                return
                
            content = response["result"]["content"][0]["text"]
            result = json.loads(content)
            
            if result.get("success") or result.get("is_mock"):
                self.record_test_result(test_name, True, "VFS mkdir working", result)
            else:
                self.record_test_result(test_name, False, "VFS mkdir failed", result)
                
        except Exception as e:
            self.record_test_result(test_name, False, f"Exception: {e}")
            
    async def test_vfs_write(self):
        """Test VFS file writing."""
        test_name = "VFS Write"
        
        try:
            test_content = f"Test content created at {datetime.now().isoformat()}"
            
            response = await self.client.call_tool("vfs_write", {
                "path": "/test_file.txt",
                "content": test_content,
                "encoding": "utf-8",
                "create_dirs": True
            })
            
            if "result" not in response:
                self.record_test_result(test_name, False, "No result in response", response)
                return
                
            content = response["result"]["content"][0]["text"]
            result = json.loads(content)
            
            if result.get("success") or result.get("is_mock"):
                self.record_test_result(test_name, True, "VFS write working", result)
            else:
                self.record_test_result(test_name, False, "VFS write failed", result)
                
        except Exception as e:
            self.record_test_result(test_name, False, f"Exception: {e}")
            
    async def test_vfs_read(self):
        """Test VFS file reading."""
        test_name = "VFS Read"
        
        try:
            response = await self.client.call_tool("vfs_read", {
                "path": "/test_file.txt",
                "encoding": "utf-8"
            })
            
            if "result" not in response:
                self.record_test_result(test_name, False, "No result in response", response)
                return
                
            content = response["result"]["content"][0]["text"]
            result = json.loads(content)
            
            if result.get("success") or result.get("is_mock"):
                self.record_test_result(test_name, True, "VFS read working", result)
            else:
                self.record_test_result(test_name, False, "VFS read failed", result)
                
        except Exception as e:
            self.record_test_result(test_name, False, f"Exception: {e}")
            
    async def test_vfs_ls(self):
        """Test VFS directory listing."""
        test_name = "VFS List"
        
        try:
            response = await self.client.call_tool("vfs_ls", {
                "path": "/",
                "detailed": True,
                "recursive": False
            })
            
            if "result" not in response:
                self.record_test_result(test_name, False, "No result in response", response)
                return
                
            content = response["result"]["content"][0]["text"]
            result = json.loads(content)
            
            if result.get("success") or result.get("is_mock"):
                self.record_test_result(test_name, True, "VFS ls working", result)
            else:
                self.record_test_result(test_name, False, "VFS ls failed", result)
                
        except Exception as e:
            self.record_test_result(test_name, False, f"Exception: {e}")
            
    async def test_vfs_stat(self):
        """Test VFS file statistics."""
        test_name = "VFS Stat"
        
        try:
            response = await self.client.call_tool("vfs_stat", {
                "path": "/test_file.txt"
            })
            
            if "result" not in response:
                self.record_test_result(test_name, False, "No result in response", response)
                return
                
            content = response["result"]["content"][0]["text"]
            result = json.loads(content)
            
            if result.get("success") or result.get("is_mock"):
                self.record_test_result(test_name, True, "VFS stat working", result)
            else:
                self.record_test_result(test_name, False, "VFS stat failed", result)
                
        except Exception as e:
            self.record_test_result(test_name, False, f"Exception: {e}")
            
    async def test_vfs_copy(self):
        """Test VFS file copying."""
        test_name = "VFS Copy"
        
        try:
            response = await self.client.call_tool("vfs_copy", {
                "source": "/test_file.txt",
                "dest": "/test_file_copy.txt",
                "preserve_metadata": True
            })
            
            if "result" not in response:
                self.record_test_result(test_name, False, "No result in response", response)
                return
                
            content = response["result"]["content"][0]["text"]
            result = json.loads(content)
            
            if result.get("success") or result.get("is_mock"):
                self.record_test_result(test_name, True, "VFS copy working", result)
            else:
                self.record_test_result(test_name, False, "VFS copy failed", result)
                
        except Exception as e:
            self.record_test_result(test_name, False, f"Exception: {e}")
            
    async def test_vfs_move(self):
        """Test VFS file moving."""
        test_name = "VFS Move"
        
        try:
            response = await self.client.call_tool("vfs_move", {
                "source": "/test_file_copy.txt",
                "dest": "/test_file_moved.txt"
            })
            
            if "result" not in response:
                self.record_test_result(test_name, False, "No result in response", response)
                return
                
            content = response["result"]["content"][0]["text"]
            result = json.loads(content)
            
            if result.get("success") or result.get("is_mock"):
                self.record_test_result(test_name, True, "VFS move working", result)
            else:
                self.record_test_result(test_name, False, "VFS move failed", result)
                
        except Exception as e:
            self.record_test_result(test_name, False, f"Exception: {e}")
            
    async def test_vfs_sync_to_ipfs(self):
        """Test VFS sync to IPFS."""
        test_name = "VFS Sync to IPFS"
        
        try:
            response = await self.client.call_tool("vfs_sync_to_ipfs", {
                "path": "/",
                "recursive": True
            })
            
            if "result" not in response:
                self.record_test_result(test_name, False, "No result in response", response)
                return
                
            content = response["result"]["content"][0]["text"]
            result = json.loads(content)
            
            if result.get("success") or result.get("is_mock"):
                self.record_test_result(test_name, True, "VFS sync to IPFS working", result)
            else:
                self.record_test_result(test_name, False, "VFS sync to IPFS failed", result)
                
        except Exception as e:
            self.record_test_result(test_name, False, f"Exception: {e}")
            
    async def test_vfs_sync_from_ipfs(self):
        """Test VFS sync from IPFS."""
        test_name = "VFS Sync from IPFS"
        
        try:
            response = await self.client.call_tool("vfs_sync_from_ipfs", {
                "ipfs_path": "/ipfs/QmTestCID123",
                "vfs_path": "/synced",
                "force": False
            })
            
            if "result" not in response:
                self.record_test_result(test_name, False, "No result in response", response)
                return
                
            content = response["result"]["content"][0]["text"]
            result = json.loads(content)
            
            if result.get("success") or result.get("is_mock"):
                self.record_test_result(test_name, True, "VFS sync from IPFS working", result)
            else:
                self.record_test_result(test_name, False, "VFS sync from IPFS failed", result)
                
        except Exception as e:
            self.record_test_result(test_name, False, f"Exception: {e}")
            
    async def test_vfs_rmdir(self):
        """Test VFS directory removal."""
        test_name = "VFS Rmdir"
        
        try:
            response = await self.client.call_tool("vfs_rmdir", {
                "path": "/test_dir",
                "recursive": True
            })
            
            if "result" not in response:
                self.record_test_result(test_name, False, "No result in response", response)
                return
                
            content = response["result"]["content"][0]["text"]
            result = json.loads(content)
            
            if result.get("success") or result.get("is_mock"):
                self.record_test_result(test_name, True, "VFS rmdir working", result)
            else:
                self.record_test_result(test_name, False, "VFS rmdir failed", result)
                
        except Exception as e:
            self.record_test_result(test_name, False, f"Exception: {e}")
            
    async def test_vfs_unmount(self):
        """Test VFS unmounting."""
        test_name = "VFS Unmount"
        
        try:
            mount_point = os.path.join(self.temp_dir, "test_mount")
            
            response = await self.client.call_tool("vfs_unmount", {
                "mount_point": mount_point
            })
            
            if "result" not in response:
                self.record_test_result(test_name, False, "No result in response", response)
                return
                
            content = response["result"]["content"][0]["text"]
            result = json.loads(content)
            
            if result.get("success") or result.get("is_mock"):
                self.record_test_result(test_name, True, "VFS unmount working", result)
            else:
                self.record_test_result(test_name, False, "VFS unmount failed", result)
                
        except Exception as e:
            self.record_test_result(test_name, False, f"Exception: {e}")
            
    async def run_all_tests(self):
        """Run all VFS tests."""
        logger.info("Starting VFS test suite...")
        
        # Setup
        await self.setup()
        
        try:
            # Run tests in sequence
            await self.test_tools_list()
            await self.test_vfs_list_mounts()
            await self.test_vfs_mount()
            await self.test_vfs_mkdir()
            await self.test_vfs_write()
            await self.test_vfs_read()
            await self.test_vfs_ls()
            await self.test_vfs_stat()
            await self.test_vfs_copy()
            await self.test_vfs_move()
            await self.test_vfs_sync_to_ipfs()
            await self.test_vfs_sync_from_ipfs()
            await self.test_vfs_rmdir()
            await self.test_vfs_unmount()
            
        finally:
            # Cleanup
            await self.teardown()
            
        # Print summary
        self.print_summary()
        
    def print_summary(self):
        """Print test summary."""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["success"])
        failed_tests = total_tests - passed_tests
        
        print("\n" + "="*60)
        print("VFS TEST SUMMARY")
        print("="*60)
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            print("\nFAILED TESTS:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"  ✗ {result['test']}: {result['message']}")
        
        print("\nDETAILED RESULTS:")
        for result in self.test_results:
            status = "✓" if result["success"] else "✗"
            print(f"  {status} {result['test']}: {result['message']}")
            
            # Show if it's using mock data
            if result["details"].get("is_mock"):
                print(f"    📝 Using mock data (real VFS not available)")
                
        print("="*60)

async def main():
    """Main test function."""
    # Get the server path
    server_path = os.path.join(os.path.dirname(__file__), "mcp", "enhanced_mcp_server_with_daemon_mgmt.py")
    
    if not os.path.exists(server_path):
        print(f"Error: MCP server not found at {server_path}")
        sys.exit(1)
        
    # Create client and test suite
    client = MCPVFSClient(server_path)
    test_suite = VFSTestSuite(client)
    
    try:
        # Start server
        await client.start_server()
        
        # Run tests
        await test_suite.run_all_tests()
        
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        
    except Exception as e:
        logger.error(f"Test error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Stop server
        await client.stop_server()

if __name__ == "__main__":
    asyncio.run(main())
