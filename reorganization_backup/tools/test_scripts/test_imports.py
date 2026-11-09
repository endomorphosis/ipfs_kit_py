#!/usr/bin/env python3
"""
Simple import test to identify hanging imports.
"""

import sys
import os

print("Starting import test...")

try:
    print("1. Adding current directory to path...")
    sys.path.insert(0, os.getcwd())
    print("   ✅ Path added")

    print("2. Testing basic Python imports...")
    import asyncio
    import logging

    print("   ✅ Basic imports successful")

    print("3. Testing fixed_ipfs_model import...")
    from fixed_ipfs_model import IPFSModel

    print("   ✅ IPFSModel imported successfully")

    print("4. Testing unified_ipfs_tools import...")
    import unified_ipfs_tools

    print("   ✅ unified_ipfs_tools imported successfully")

    print("5. Testing fixed_direct_ipfs_tools import...")
    import fixed_direct_ipfs_tools

    print("   ✅ fixed_direct_ipfs_tools imported successfully")

    print("\n🎉 All imports successful!")

except Exception as e:
    print(f"❌ Import failed: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)
