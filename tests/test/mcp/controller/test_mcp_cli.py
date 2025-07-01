#!/usr/bin/env python3
"""
Test script for MCP server CLI controller integration.
"""

import logging
import sys
from ipfs_kit_py.mcp.server_bridge import MCPServer  # Refactored import

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Disable noisy logs from some components
logging.getLogger('ipfs_kit_py.huggingface_kit').setLevel(logging.WARNING)
logging.getLogger('ipfs_kit_py.storage_wal').setLevel(logging.WARNING)
logging.getLogger('ipfs_kit_py.wal_telemetry').setLevel(logging.WARNING)
logging.getLogger('ipfs_kit_py.wal_api').setLevel(logging.WARNING)

def test_mcp_cli_integration():
    """Test MCP server with CLI controller integration."""
    
    print("Creating MCP server instance...")
    server = MCPServer(
        debug_mode=True,
        log_level="INFO",
        isolation_mode=True  # Use isolated mode to avoid affecting the system
    )
    
    print("\nVerifying CLI controller is registered...")
    if "cli" not in server.controllers:
        print("ERROR: CLI controller not found in server.controllers")
        return False
    
    print(f"CLI controller is registered: {type(server.controllers['cli']).__name__}")
    
    print("\nAvailable CLI routes:")
    route_count = 0
    for route in server.router.routes:
        if "/cli/" in str(route.path):
            print(f"  - {route.path} [{route.methods}]")
            route_count += 1
    
    print(f"\nFound {route_count} CLI routes")
    
    print("\nMCP CLI integration test completed successfully!")
    return True

if __name__ == "__main__":
    success = test_mcp_cli_integration()
    sys.exit(0 if success else 1)