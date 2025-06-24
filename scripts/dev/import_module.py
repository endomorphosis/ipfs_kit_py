#!/usr/bin/env python3

"""
Script to try importing the high_level_api module.
"""

try:
    import sys
    sys.path.insert(0, '.')
    from ipfs_kit_py.high_level_api import IPFSSimpleAPI
    print("Successfully imported IPFSSimpleAPI!")
except Exception as e:
    print(f"Import error: {e}")
    import traceback
    traceback.print_exc()
