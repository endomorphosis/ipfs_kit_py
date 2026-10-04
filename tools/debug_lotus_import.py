#!/usr/bin/env python3
"""Debug script to test lotus_kit import and initialization."""

import sys
import os
import traceback

print("=== Debug lotus_kit import ===")
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")
print(f"Python path: {sys.path[:3]}")

print("\n1. Testing direct lotus_kit import:")
try:
    from ipfs_kit_py.lotus_kit import lotus_kit
    print("✓ lotus_kit import successful")
    print(f"  lotus_kit class: {lotus_kit}")
except Exception as e:
    print(f"✗ lotus_kit import failed: {e}")
    traceback.print_exc()

print("\n2. Testing ipfs_kit_py module import:")
try:
    import ipfs_kit_py
    print("✓ ipfs_kit_py module import successful")
    print(f"  HAS_LOTUS: {getattr(ipfs_kit_py, 'HAS_LOTUS', 'NOT_FOUND')}")
    print(f"  Has lotus_kit: {hasattr(ipfs_kit_py, 'lotus_kit')}")
except Exception as e:
    print(f"✗ ipfs_kit_py module import failed: {e}")
    traceback.print_exc()

print("\n3. Testing ipfs_kit class instantiation:")
try:
    from ipfs_kit_py import ipfs_kit
    print("✓ ipfs_kit class import successful")
    
    # Create instance
    kit = ipfs_kit(metadata={"role": "leecher"})
    print("✓ ipfs_kit instance created")
    print(f"  Has lotus_kit attribute: {hasattr(kit, 'lotus_kit')}")
    
    if hasattr(kit, 'lotus_kit'):
        print(f"  lotus_kit value: {kit.lotus_kit}")
    else:
        print("  lotus_kit attribute not found")
        print(f"  Available attributes: {[attr for attr in dir(kit) if not attr.startswith('_')]}")
        
except Exception as e:
    print(f"✗ ipfs_kit instantiation failed: {e}")
    traceback.print_exc()

print("\n4. Testing HAS_LOTUS flag from ipfs_kit.py:")
try:
    from ipfs_kit_py.ipfs_kit import HAS_LOTUS
    print(f"✓ HAS_LOTUS import successful: {HAS_LOTUS}")
except Exception as e:
    print(f"✗ HAS_LOTUS import failed: {e}")
    traceback.print_exc()

print("\n=== Debug complete ===")
