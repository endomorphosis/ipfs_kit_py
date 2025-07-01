#!/usr/bin/env python3
"""Simple test to check IPFS Kit import"""

import sys
import traceback

print("Testing IPFS Kit import...")

try:
    from ipfs_kit_py import IPFSKit
    print("✅ Successfully imported IPFSKit")
    
    try:
        kit = IPFSKit()
        print("✅ Successfully created IPFSKit instance")
    except Exception as e:
        print(f"⚠️ Error creating IPFSKit instance: {e}")
        try:
            kit = IPFSKit(mock_mode=True)
            print("✅ Successfully created IPFSKit instance in mock mode")
        except Exception as e2:
            print(f"❌ Error creating IPFSKit instance even in mock mode: {e2}")
            traceback.print_exc()
            
except ImportError as e:
    print(f"❌ Failed to import IPFSKit: {e}")
    traceback.print_exc()
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    traceback.print_exc()

print("Test complete")
