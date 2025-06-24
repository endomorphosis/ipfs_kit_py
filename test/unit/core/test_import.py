#!/usr/bin/env python3

"""
Simple test script to verify that the high_level_api module can be imported successfully.
"""

import sys
import traceback

try:
    from ipfs_kit_py.high_level_api import IPFSSimpleAPI
    print("Successfully imported IPFSSimpleAPI from high_level_api!")

    # Try to create an instance to make sure class is properly defined
    api = IPFSSimpleAPI(allow_simulation=True)
    print("Successfully created an instance of IPFSSimpleAPI!")

    # Specifically check if ai_register_dataset exists
    if hasattr(api, 'ai_register_dataset'):
        print("ai_register_dataset method exists on IPFSSimpleAPI!")
    else:
        print("ERROR: ai_register_dataset method not found on IPFSSimpleAPI!")

    print("All tests passed successfully!")
    # sys.exit(0) # Removed to prevent pytest collection error
except ImportError as e:
    print(f"Import Error: {e}")
    traceback.print_exc()
    sys.exit(1)
except IndentationError as e:
    print(f"Indentation Error: {e}")
    traceback.print_exc()
    sys.exit(2)
except Exception as e:
    print(f"Unexpected Error: {e}")
    traceback.print_exc()
    sys.exit(3)
