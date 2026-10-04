#!/usr/bin/env python3
"""
Trace import behavior to find where the cascade starts
"""

import sys
import os
import builtins
import time

# Add timing to imports
original_import = builtins.__import__

imported_modules = []

def traced_import(name, *args, **kwargs):
    start = time.time()
    result = original_import(name, *args, **kwargs)
    duration = time.time() - start
    if duration > 0.1:  # Only log slow imports
        imported_modules.append((name, duration))
        print(f"SLOW IMPORT: {name} took {duration:.3f}s")
    return result

builtins.__import__ = traced_import

# Now test the CLI import
print("Testing CLI import...")
try:
    start_time = time.time()
    from ipfs_kit_py.cli import main
    end_time = time.time()
    print(f"CLI import took: {end_time - start_time:.3f}s")
    
    print("\nSlowest imports:")
    for name, duration in sorted(imported_modules, key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {name}: {duration:.3f}s")
        
except Exception as e:
    print(f"Error during import: {e}")
    
# Restore original import
builtins.__import__ = original_import
