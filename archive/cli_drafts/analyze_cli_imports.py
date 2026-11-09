#!/usr/bin/env python3
"""
Analyze CLI command imports to find heavy ones
"""

import time
import sys
import builtins

# Track import times
import_times = {}
original_import = builtins.__import__

def traced_import(name, *args, **kwargs):
    start = time.time()
    result = original_import(name, *args, **kwargs)
    duration = time.time() - start
    if duration > 0.05:  # Track anything over 50ms
        import_times[name] = duration
        print(f"IMPORT: {name} took {duration:.3f}s")
    return result

builtins.__import__ = traced_import

# Test each CLI command module individually
commands_to_test = {
    "wal": "ipfs_kit_py.wal_cli_integration",
    "fs-journal": "ipfs_kit_py.fs_journal_cli", 
    "bucket": "ipfs_kit_py.bucket_vfs_cli",
    "vfs-version": "ipfs_kit_py.vfs_version_cli",
    "wal-telemetry": "ipfs_kit_py.wal_telemetry_cli",
}

print("Testing individual CLI command module imports...")
print("=" * 60)

for cmd_name, module_path in commands_to_test.items():
    print(f"\nTesting {cmd_name} ({module_path}):")
    start_time = time.time()
    try:
        module = __import__(module_path, fromlist=[''])
        end_time = time.time()
        print(f"✓ {cmd_name}: {end_time - start_time:.3f}s")
    except ImportError as e:
        end_time = time.time()
        print(f"✗ {cmd_name}: {end_time - start_time:.3f}s (ImportError: {e})")
    except Exception as e:
        end_time = time.time()
        print(f"✗ {cmd_name}: {end_time - start_time:.3f}s (Error: {e})")

print(f"\nSlowest imports (> 50ms):")
for name, duration in sorted(import_times.items(), key=lambda x: x[1], reverse=True):
    print(f"  {name}: {duration:.3f}s")

# Restore original import
builtins.__import__ = original_import
