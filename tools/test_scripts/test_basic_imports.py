#!/usr/bin/env python3

"""
Very simple test script to verify basic imports.
"""

import sys
import os

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
print(f"Project root: {project_root}")
sys.path.insert(0, project_root)

# Now try to import the ipfs_kit_py module
try:
    import ipfs_kit_py
    print(f"Successfully imported ipfs_kit_py from {ipfs_kit_py.__file__}")
    
    # Check high_level_api
    try:
        from ipfs_kit_py import high_level_api
        print(f"Successfully imported high_level_api from {high_level_api.__file__}")
        
        # Try to import IPFSSimpleAPI
        try:
            from ipfs_kit_py.high_level_api import IPFSSimpleAPI
            print("Successfully imported IPFSSimpleAPI!")
        except ImportError as e:
            print(f"Failed to import IPFSSimpleAPI: {e}")
    except ImportError as e:
        print(f"Failed to import high_level_api: {e}")
        
except ImportError as e:
    print(f"Failed to import ipfs_kit_py: {e}")

print("Basic import check complete")