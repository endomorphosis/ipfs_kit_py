#!/usr/bin/env python3
"""
Direct test script for the fixes to files_ls and files_stat methods.
This script directly tests the patched methods without going through HTTP.
"""

import sys
import os
import time
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load the patches
print("Applying patches...")
import patch_missing_methods

# Import ipfs_kit
from ipfs_kit_py.ipfs_kit import ipfs_kit

# Create an instance
print("Creating ipfs_kit instance...")
kit = ipfs_kit()

# Test files_ls with long parameter
print("\n--- Testing files_ls with long parameter ---")
try:
    result = kit.files_ls("/", long=True)
    print(json.dumps(result, indent=2))
    print("files_ls with long parameter: SUCCESS")
except Exception as e:
    print(f"Error: {str(e)}")
    print("files_ls with long parameter: FAILED")

# Test files_stat method
print("\n--- Testing files_stat method ---")
try:
    result = kit.files_stat("/")
    print(json.dumps(result, indent=2))
    print("files_stat method: SUCCESS")
except Exception as e:
    print(f"Error: {str(e)}")
    print("files_stat method: FAILED")

# Test all MCP-related methods to verify fixes
print("\n--- Testing all patched methods ---")

# DHT operations
try:
    result = kit.dht_findpeer("QmTest123")
    print("dht_findpeer: SUCCESS")
except Exception as e:
    print(f"dht_findpeer error: {str(e)}")

try:
    result = kit.dht_findprovs("QmTest123")
    print("dht_findprovs: SUCCESS")
except Exception as e:
    print(f"dht_findprovs error: {str(e)}")

# Files operations
try:
    result = kit.files_mkdir("/test_dir_" + str(int(time.time())))
    print("files_mkdir: SUCCESS")
except Exception as e:
    print(f"files_mkdir error: {str(e)}")

print("\nAll tests completed!")