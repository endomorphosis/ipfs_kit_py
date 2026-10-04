#!/usr/bin/env python3

"""
Test script to verify that the MCPDiscoveryControllerAnyIO can be imported successfully.
This test uses pytest's assertion framework instead of sys.exit().
"""

import pytest
import traceback
import sys

def test_mcp_discovery_controller_anyio_import():
    """Test if MCPDiscoveryControllerAnyIO can be imported correctly."""
    try:
        # Just check if the module can be imported
        from ipfs_kit_py.mcp.controllers.mcp_discovery_controller_anyio import MCPDiscoveryControllerAnyIO
        
        print("Successfully imported MCPDiscoveryControllerAnyIO!")
        print("Import check passed!")
        # The test passes if we reach this point
        assert True
    except ImportError as e:
        print(f"Import Error: {e}")
        traceback.print_exc()
        pytest.fail(f"Failed to import MCPDiscoveryControllerAnyIO: {e}")
    except Exception as e:
        print(f"Unexpected Error: {e}")
        traceback.print_exc()
        pytest.fail(f"Unexpected error during import: {e}")

if __name__ == "__main__":
    # This allows the file to be run directly, outside of pytest
    try:
        from ipfs_kit_py.mcp.controllers.mcp_discovery_controller_anyio import MCPDiscoveryControllerAnyIO
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