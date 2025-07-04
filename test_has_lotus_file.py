#!/usr/bin/env python3
"""Test script that writes output to a file."""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

with open('test_output.txt', 'w') as f:
    try:
        f.write("Testing HAS_LOTUS availability...\n")
        
        import ipfs_kit_py.ipfs_kit
        has_lotus = getattr(ipfs_kit_py.ipfs_kit, 'HAS_LOTUS', 'NOT_FOUND')
        f.write(f"HAS_LOTUS: {has_lotus}\n")
        
        if has_lotus == 'NOT_FOUND':
            f.write("HAS_LOTUS is still not available\n")
            sys.exit(1)
        
        f.write("Creating ipfs_kit instance...\n")
        kit = ipfs_kit_py.ipfs_kit.ipfs_kit()
        
        f.write(f"Has lotus_kit: {hasattr(kit, 'lotus_kit')}\n")
        
        if hasattr(kit, 'lotus_kit'):
            f.write("✓ SUCCESS: lotus_kit is available\n")
        else:
            f.write("✗ FAILED: lotus_kit is not available\n")
            lotus_attrs = [attr for attr in dir(kit) if 'lotus' in attr.lower()]
            f.write(f"Lotus-related attributes: {lotus_attrs}\n")
            
    except Exception as e:
        f.write(f"Error: {e}\n")
        import traceback
        f.write(traceback.format_exc())
        
print("Test completed, check test_output.txt for results")
