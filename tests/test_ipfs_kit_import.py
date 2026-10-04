#!/usr/bin/env python3
"""Test just the ipfs_kit import"""

import os
import sys
import traceback

# Add current directory to Python path
sys.path.insert(0, os.getcwd())

print("🧪 Testing ipfs_kit import...")

try:
    print("📦 Importing ipfs_kit class...")
    from ipfs_kit_py.ipfs_kit import ipfs_kit
    print("✅ ipfs_kit imported successfully")
    
    print("📦 Creating instance...")
    metadata = {"role": "master"}
    kit = ipfs_kit(metadata=metadata)
    print(f"✅ ipfs_kit created with role: {kit.role}")
    
    print("🎉 Test passed!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    print("\n🔍 Full traceback:")
    traceback.print_exc()
