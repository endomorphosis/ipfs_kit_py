#!/usr/bin/env python3
"""Simple validation script to check lotus_kit availability."""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

# Redirect all output to a file
import io
import contextlib

output_buffer = io.StringIO()

with contextlib.redirect_stdout(output_buffer), contextlib.redirect_stderr(output_buffer):
    try:
        # Test 1: Direct import of lotus_kit
        from ipfs_kit_py.lotus_kit import lotus_kit
        print("✓ Direct lotus_kit import successful")
        
        # Test 2: Import HAS_LOTUS from ipfs_kit module
        from ipfs_kit_py.ipfs_kit import HAS_LOTUS
        print(f"✓ HAS_LOTUS from ipfs_kit.py: {HAS_LOTUS}")
        
        # Test 3: Create ipfs_kit instance
        import ipfs_kit_py
        kit = ipfs_kit_py.ipfs_kit()
        print("✓ ipfs_kit instance created")
        
        # Test 4: Check if lotus_kit is available
        has_lotus_kit = hasattr(kit, 'lotus_kit')
        print(f"Has lotus_kit: {has_lotus_kit}")
        
        if has_lotus_kit:
            print("✓ SUCCESS: lotus_kit is available")
        else:
            print("✗ FAILED: lotus_kit is not available")
            print(f"Role: {kit.role}")
            
            # Check module-level HAS_LOTUS
            import ipfs_kit_py.ipfs_kit
            has_lotus_module = getattr(ipfs_kit_py.ipfs_kit, 'HAS_LOTUS', 'NOT_FOUND')
            print(f"Module HAS_LOTUS: {has_lotus_module}")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        print(traceback.format_exc())

# Write output to file
with open('validation_output.txt', 'w') as f:
    f.write(output_buffer.getvalue())

print("Validation complete, check validation_output.txt")
