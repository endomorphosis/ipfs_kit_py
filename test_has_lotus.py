#!/usr/bin/env python3
"""Quick test to verify HAS_LOTUS is now available."""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

print("Testing HAS_LOTUS availability...")

try:
    import ipfs_kit_py.ipfs_kit
    has_lotus = getattr(ipfs_kit_py.ipfs_kit, 'HAS_LOTUS', 'NOT_FOUND')
    print(f"HAS_LOTUS: {has_lotus}")
    
    if has_lotus == 'NOT_FOUND':
        print("HAS_LOTUS is still not available")
        sys.exit(1)
    
    print("Creating ipfs_kit instance...")
    kit = ipfs_kit_py.ipfs_kit.ipfs_kit()
    
    print(f"Has lotus_kit: {hasattr(kit, 'lotus_kit')}")
    
    if hasattr(kit, 'lotus_kit'):
        print("✓ SUCCESS: lotus_kit is available")
        sys.exit(0)
    else:
        print("✗ FAILED: lotus_kit is not available")
        lotus_attrs = [attr for attr in dir(kit) if 'lotus' in attr.lower()]
        print(f"Lotus-related attributes: {lotus_attrs}")
        sys.exit(1)
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
