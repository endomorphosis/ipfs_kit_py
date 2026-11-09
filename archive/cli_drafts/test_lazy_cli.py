#!/usr/bin/env python3
"""
Test script to verify CLI lazy loading performance improvements.
"""

import time
import subprocess
import sys
import os

def time_command(cmd, description):
    """Time a command and return the duration"""
    print(f"\n🔍 Testing: {description}")
    print(f"Command: {cmd}")
    
    start_time = time.time()
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        duration = time.time() - start_time
        
        print(f"⏱️  Duration: {duration:.3f} seconds")
        
        if result.returncode == 0:
            print(f"✅ Success")
            if result.stdout.strip():
                print(f"Output preview: {result.stdout[:200]}...")
        else:
            print(f"❌ Error (exit code {result.returncode})")
            if result.stderr.strip():
                print(f"Error: {result.stderr[:200]}...")
                
        return duration, result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print(f"⏱️  Timeout after 30 seconds")
        return 30.0, False
    except Exception as e:
        print(f"❌ Exception: {e}")
        return float('inf'), False

def main():
    print("🚀 Testing CLI Lazy Loading Performance Improvements")
    print("=" * 60)
    
    # Change to the project directory
    os.chdir("/home/devel/ipfs_kit_py")
    
    # Test commands that should be fast now
    fast_commands = [
        ("python -m ipfs_kit_py.cli --help", "CLI help (should be fast)"),
        ("python -m ipfs_kit_py.cli state --help", "State command help (should be fast)"),
        ("python -m ipfs_kit_py.cli state", "State command execution (should be fast)"),
        ("python -m ipfs_kit_py.cli fs-journal --help", "FS-Journal help (lightweight)"),
        ("python -m ipfs_kit_py.cli bucket --help", "Bucket help (lightweight)"),
    ]
    
    # Test commands that should trigger lazy loading
    lazy_commands = [
        ("python -m ipfs_kit_py.cli wal --help", "WAL command help (should trigger lazy loading)"),
        ("python -m ipfs_kit_py.cli dashboard --help", "Dashboard command help (should trigger lazy loading)"),
    ]
    
    print("\n📈 FAST COMMANDS (No Heavy Imports)")
    print("-" * 50)
    
    fast_times = []
    for cmd, desc in fast_commands:
        duration, success = time_command(cmd, desc)
        if success:
            fast_times.append(duration)
    
    print("\n🐌 LAZY LOADED COMMANDS (Heavy Imports Only When Needed)")
    print("-" * 50)
    
    lazy_times = []
    for cmd, desc in lazy_commands:
        duration, success = time_command(cmd, desc)
        if success:
            lazy_times.append(duration)
    
    # Summary
    print("\n📊 PERFORMANCE SUMMARY")
    print("=" * 60)
    
    if fast_times:
        avg_fast = sum(fast_times) / len(fast_times)
        print(f"🏃 Fast commands average: {avg_fast:.3f} seconds")
        print(f"🏃 Fast commands range: {min(fast_times):.3f} - {max(fast_times):.3f} seconds")
    
    if lazy_times:
        avg_lazy = sum(lazy_times) / len(lazy_times)
        print(f"🐌 Lazy commands average: {avg_lazy:.3f} seconds")
        print(f"🐌 Lazy commands range: {min(lazy_times):.3f} - {max(lazy_times):.3f} seconds")
    
    if fast_times and lazy_times:
        speedup = avg_lazy / avg_fast if avg_fast > 0 else 0
        print(f"📈 Lazy loading overhead: {speedup:.1f}x slower (expected for heavy imports)")
    
    # Check if fast commands are actually fast (under 2 seconds)
    fast_enough = [t for t in fast_times if t < 2.0]
    if len(fast_enough) == len(fast_times):
        print(f"✅ SUCCESS: All fast commands completed under 2 seconds!")
    else:
        print(f"⚠️  WARNING: {len(fast_times) - len(fast_enough)} commands took over 2 seconds")
    
    print(f"\n🎯 Goal: Fast commands should be <1s, lazy commands only load when needed")

if __name__ == "__main__":
    main()
