#!/usr/bin/env python3
"""
Quick MCP Server Validation Test
"""

import anyio
import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

async def test_mcp_server():
    """Quick test of MCP server tools"""
    try:
        from mcp.ipfs_kit.mcp.enhanced_mcp_server_with_daemon_mgmt import EnhancedMCPServerWithDaemonMgmt
        
        print("Initializing MCP Server...")
        server = EnhancedMCPServerWithDaemonMgmt()
        
        # Test tool registration
        result = await server.handle_tools_list({})
        tools = result.get("tools", [])
        print(f"✓ Total tools registered: {len(tools)}")
        
        # Categorize tools
        categories = {}
        for tool in tools:
            name = tool["name"]
            if name.startswith("ipfs_"):
                if any(x in name for x in ["dht_", "name_", "pubsub_"]):
                    cat = "IPFS Advanced"
                elif "files_" in name:
                    cat = "IPFS MFS"
                else:
                    cat = "IPFS Core"
            elif name.startswith("vfs_"):
                cat = "VFS"
            else:
                cat = "System"
            
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(name)
        
        print("\nTool Breakdown:")
        total = 0
        for cat, tool_list in categories.items():
            print(f"  {cat}: {len(tool_list)} tools")
            total += len(tool_list)
        
        print(f"\nTotal: {total} tools")
        
        # Test sample execution
        print("\nTesting sample tools:")
        
        test_tools = [
            ("ipfs_id", {}),
            ("ipfs_add", {"content": "Test content"}),
            ("vfs_list_mounts", {}),
            ("system_health", {})
        ]
        
        successful = 0
        for tool_name, args in test_tools:
            try:
                result = await server.execute_tool(tool_name, args)
                if result.get("success", False):
                    print(f"  ✓ {tool_name}: OK")
                    successful += 1
                else:
                    print(f"  ✗ {tool_name}: {result.get('error', 'Failed')}")
            except Exception as e:
                print(f"  ✗ {tool_name}: Exception - {e}")
        
        print(f"\nTest Results: {successful}/{len(test_tools)} tools executed successfully")
        
        # Cleanup
        server.cleanup()
        
        return successful == len(test_tools)
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = anyio.run(test_mcp_server)
    if success:
        print("\n🎉 MCP Server validation successful!")
        sys.exit(0)
    else:
        print("\n❌ MCP Server validation failed!")
        sys.exit(1)
