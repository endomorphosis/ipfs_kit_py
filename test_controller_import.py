import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    # Print each module level to debug import issues
    print("Importing ipfs_kit_py...")
    import ipfs_kit_py
    print("Importing ipfs_kit_py.mcp...")
    import ipfs_kit_py.mcp
    print("Importing ipfs_kit_py.mcp.controllers...")
    import ipfs_kit_py.mcp.controllers
    print("Importing mcp_discovery_controller_anyio...")
    from ipfs_kit_py.mcp.controllers.mcp_discovery_controller_anyio import MCPDiscoveryControllerAnyIO
    
    print("\n*** Successfully imported MCPDiscoveryControllerAnyIO! ***")
    
    # Check that the key methods exist
    print("\nVerifying methods:")
    methods = [
        "get_local_server_info_async",
        "update_local_server_async",
        "announce_server_async"
    ]
    
    for method in methods:
        if hasattr(MCPDiscoveryControllerAnyIO, method):
            print(f"  ✓ Method {method} exists")
        else:
            print(f"  ✗ Method {method} does NOT exist")
    
    sys.exit(0)
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
    sys.exit(1)