#!/usr/bin/env python3

"""
Simple test script to verify that the MCPDiscoveryControllerAnyIO can be imported successfully.
"""

import sys
import traceback

# Don't import other modules to avoid dependency issues
try:
    # Just check if the module can be imported
    from ipfs_kit_py.mcp_server.controllers.mcp_discovery_controller_anyio import MCPDiscoveryControllerAnyIO
    
    print("Successfully imported MCPDiscoveryControllerAnyIO!")
    print("Import check passed!")
    sys.exit(0)
except ImportError as e:
    print(f"Import Error: {e}")
    traceback.print_exc()
    sys.exit(1)
except Exception as e:
    print(f"Unexpected Error: {e}")
    traceback.print_exc()
    sys.exit(2)