#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

# Test import and count tools
print("Testing modular server tool count...")

try:
    from mcp.ipfs_kit.mcp_tools.tool_manager import MCPToolManager
    from mcp.ipfs_kit.backends.health_monitor import BackendHealthMonitor
    print("✓ MCP Tool Manager imported")
    
    # Create backend monitor
    backend_monitor = BackendHealthMonitor()
    print("✓ Backend monitor created")
    
    # Create tool manager
    tool_manager = MCPToolManager(backend_monitor)
    print(f"✓ Tool manager created")
    
    # Get tools
    tools = tool_manager.get_tools()
    print(f"✓ Tools retrieved: {len(tools)} tools")
    
    # List all tools
    print("\nAvailable tools:")
    for i, tool in enumerate(tools, 1):
        print(f"{i:2d}. {tool.name} - {tool.description}")
    
    print(f"\nTotal tools: {len(tools)}")
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\nTest completed successfully!")
