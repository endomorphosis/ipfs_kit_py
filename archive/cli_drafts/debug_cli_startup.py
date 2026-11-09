#!/usr/bin/env python3
"""
Debug what imports are happening during CLI startup.
"""

import time
import sys
import importlib
import os

# Hook to track all imports
imported_modules = []
original_import = __builtins__.__import__

def debug_import(name, globals=None, locals=None, fromlist=(), level=0):
    start_time = time.time()
    result = original_import(name, globals, locals, fromlist, level)
    duration = time.time() - start_time
    
    if duration > 0.01:  # Only track imports that take more than 10ms
        imported_modules.append((name, duration))
        print(f"Import: {name} took {duration:.3f}s")
    
    return result

# Install the import hook
__builtins__.__import__ = debug_import

print("🔍 Debugging CLI imports during startup...")
print("=" * 60)

start_total = time.time()

# Import the CLI module to see what happens during initialization
try:
    from ipfs_kit_py import cli
    print("✅ CLI module imported successfully")
except Exception as e:
    print(f"❌ Error importing CLI: {e}")

duration_total = time.time() - start_total

print("\n📊 Import Summary")
print("=" * 60)
print(f"Total import time: {duration_total:.3f}s")
print(f"Number of slow imports: {len(imported_modules)}")

# Sort by duration and show top imports
imported_modules.sort(key=lambda x: x[1], reverse=True)

print("\n🐌 Slowest imports:")
for name, duration in imported_modules[:15]:  # Top 15
    print(f"  {duration:.3f}s - {name}")

# Check if any heavyweight modules are being imported
heavyweight_modules = [
    'torch', 'tensorflow', 'transformers', 'datasets', 'sklearn', 
    'pandas', 'numpy', 'ipld_knowledge_graph', 'high_level_api'
]

print("\n⚠️  Heavy modules detected:")
for name, duration in imported_modules:
    for heavy in heavyweight_modules:
        if heavy in name:
            print(f"  {duration:.3f}s - {name} (contains '{heavy}')")
