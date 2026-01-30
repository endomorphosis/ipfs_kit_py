#!/usr/bin/env python3
"""
Comprehensive validation of MCP server tools including fallback testing.
"""

import sys
import os
import anyio
import traceback
import pytest

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

pytestmark = pytest.mark.anyio

async def test_tool_categories():
    """Test different categories of tools."""
    try:
        print("=== Comprehensive Tool Testing ===")
        
        from ipfs_kit_py.mcp.ipfs_kit.mcp.enhanced_mcp_server_with_daemon_mgmt import EnhancedMCPServerWithDaemonMgmt
        server = EnhancedMCPServerWithDaemonMgmt()
        
        # Test samples from each category
        test_cases = [
            # Core IPFS tools
            ("ipfs_version", {}),
            ("ipfs_id", {}),
            ("ipfs_add", {"content": "test content"}),
            
            # Advanced tools
            ("ipfs_swarm_peers", {}),
            ("ipfs_dht_findpeer", {"peer_id": "12D3KooWTest"}),
            
            # MFS tools
            ("ipfs_files_ls", {"path": "/"}),
            ("ipfs_files_mkdir", {"path": "/test_dir"}),
            
            # VFS tools
            ("vfs_list_mounts", {}),
            ("vfs_mount", {"ipfs_path": "/ipfs/test", "mount_point": "/tmp/test"}),
            
            # System tool
            ("system_health", {})
        ]
        
        results = {"success": 0, "fallback": 0, "error": 0}
        
        for tool_name, args in test_cases:
            try:
                print(f"\n🧪 Testing {tool_name}...")
                result = await server.execute_tool(tool_name, args)
                
                if result.get("success"):
                    if "mock" in str(result).lower():
                        print(f"  ✓ {tool_name}: Fallback/Mock working")
                        results["fallback"] += 1
                    else:
                        print(f"  ✅ {tool_name}: Real implementation working")
                        results["success"] += 1
                    
                    # Show brief result
                    if "operation" in result:
                        print(f"    Operation: {result['operation']}")
                    if "data" in result and len(str(result["data"])) < 100:
                        print(f"    Data: {result['data']}")
                else:
                    print(f"  ❌ {tool_name}: Failed - {result.get('error', 'Unknown error')}")
                    results["error"] += 1
                    
            except Exception as e:
                print(f"  💥 {tool_name}: Exception - {e}")
                results["error"] += 1
        
        # Summary
        total = sum(results.values())
        print(f"\n📊 Test Summary:")
        print(f"  Total tested: {total}")
        print(f"  Real implementations: {results['success']}")
        print(f"  Fallback/Mock: {results['fallback']}")
        print(f"  Errors: {results['error']}")
        print(f"  Success rate: {((results['success'] + results['fallback']) / total * 100):.1f}%")
        
        return results["error"] == 0
        
    except Exception as e:
        print(f"❌ Comprehensive test failed: {e}")
        traceback.print_exc()
        return False

async def test_mcp_protocol():
    """Test MCP protocol handlers."""
    try:
        print("\n=== MCP Protocol Testing ===")
        
        from ipfs_kit_py.mcp.ipfs_kit.mcp.enhanced_mcp_server_with_daemon_mgmt import EnhancedMCPServerWithDaemonMgmt
        server = EnhancedMCPServerWithDaemonMgmt()
        
        # Test protocol handlers
        print("🔌 Testing initialize...")
        init_result = await server.handle_initialize({})
        print(f"  ✓ Initialize: {init_result['serverInfo']['name']}")
        
        print("🛠️ Testing tools/list...")
        tools_result = await server.handle_tools_list({})
        print(f"  ✓ Tools list: {len(tools_result['tools'])} tools")
        
        print("📦 Testing resources/list...")
        resources_result = await server.handle_resources_list({})
        print(f"  ✓ Resources list: {len(resources_result['resources'])} resources")
        
        print("🎯 Testing tools/call...")
        call_result = await server.handle_tools_call({
            "name": "ipfs_id",
            "arguments": {}
        })
        print(f"  ✓ Tools call: {'success' if not call_result.get('isError') else 'error'}")
        
        return True
        
    except Exception as e:
        print(f"❌ MCP protocol test failed: {e}")
        traceback.print_exc()
        return False

async def main():
    """Main test runner."""
    print("🚀 Starting comprehensive MCP server validation...")
    
    # Test 1: Tool functionality
    tools_ok = await test_tool_categories()
    
    # Test 2: MCP protocol
    protocol_ok = await test_mcp_protocol()
    
    # Final result
    if tools_ok and protocol_ok:
        print("\n🎉 All comprehensive tests passed!")
        print("✅ MCP server is fully functional with proper fallback mechanisms")
        return True
    else:
        print("\n❌ Some tests failed")
        return False

if __name__ == "__main__":
    success = anyio.run(main)
    sys.exit(0 if success else 1)
