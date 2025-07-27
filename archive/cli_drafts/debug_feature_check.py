#!/usr/bin/env python3
"""
Test what happens when we check features
"""

import sys
import time

print("Modules before core import:")
ipfs_modules = [name for name in sys.modules.keys() if 'ipfs_kit_py' in name or 'faiss' in name or 'lotus' in name]
print(f"  Relevant modules: {len(ipfs_modules)} - {ipfs_modules}")

start = time.time()
from ipfs_kit_py.core import jit_manager
print(f"Core import took: {time.time() - start:.3f}s")

print("\nModules after core import:")
ipfs_modules = [name for name in sys.modules.keys() if 'ipfs_kit_py' in name or 'faiss' in name or 'lotus' in name]
print(f"  Relevant modules: {len(ipfs_modules)} - {ipfs_modules}")

print("\nTesting feature check...")
start = time.time()
daemon_available = jit_manager.check_feature('daemon')
print(f"check_feature('daemon') took: {time.time() - start:.3f}s, result: {daemon_available}")

print("\nModules after feature check:")
ipfs_modules = [name for name in sys.modules.keys() if 'ipfs_kit_py' in name or 'faiss' in name or 'lotus' in name]
print(f"  Relevant modules: {len(ipfs_modules)}")
if len(ipfs_modules) > 10:
    print("  (showing first 10 only)")
    for module in sorted(ipfs_modules)[:10]:
        print(f"    {module}")
else:
    for module in sorted(ipfs_modules):
        print(f"    {module}")
