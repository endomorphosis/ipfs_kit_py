#!/usr/bin/env python3
"""
Test what gets imported when we import the core
"""

import sys

print("Modules before import:")
ipfs_modules = [name for name in sys.modules.keys() if 'ipfs_kit_py' in name]
print(f"  IPFS modules: {len(ipfs_modules)}")

# Import just the core
from ipfs_kit_py.core import jit_manager

print("\nModules after core import:")
ipfs_modules = [name for name in sys.modules.keys() if 'ipfs_kit_py' in name]
print(f"  IPFS modules: {len(ipfs_modules)}")
for module in sorted(ipfs_modules):
    print(f"    {module}")
