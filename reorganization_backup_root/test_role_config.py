#!/usr/bin/env python3
"""Quick test of the MCP server role configuration."""

import sys
import os

# Add the current directory to the Python path
current_dir = os.getcwd()
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from mcp.ipfs_kit.modular_enhanced_mcp_server import ModularEnhancedMCPServer
    
    print("Testing MCP server role configuration...")
    
    # Test master role
    print("\n=== Testing Master Role ===")
    server = ModularEnhancedMCPServer(host="127.0.0.1", port=8765, role="master", debug=True)
    print(f"Server state: {server.server_state}")
    print(f"Role: {server.role}")
    print(f"Debug: {server.debug}")
    
    # Test worker role  
    print("\n=== Testing Worker Role ===")
    server2 = ModularEnhancedMCPServer(host="127.0.0.1", port=8766, role="worker", debug=False)
    print(f"Server state: {server2.server_state}")
    print(f"Role: {server2.role}")
    print(f"Debug: {server2.debug}")
    
    print("\n✅ Role configuration test completed successfully!")
    
except Exception as e:
    print(f"❌ Error during role configuration test: {e}")
    import traceback
    traceback.print_exc()
