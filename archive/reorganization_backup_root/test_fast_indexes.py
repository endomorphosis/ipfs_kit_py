#!/usr/bin/env python3
"""
Test script to verify WAL and FS Journal fast indexes are working efficiently.
"""

import time
import subprocess
import sys

def time_command(cmd, description):
    """Time a command and return the duration"""
    print(f"\n🔍 Testing: {description}")
    print(f"Command: {cmd}")
    
    start_time = time.time()
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        duration = time.time() - start_time
        
        print(f"⏱️  Duration: {duration:.3f} seconds")
        
        if result.returncode == 0:
            print(f"✅ Success")
            # Show first few lines of output
            lines = result.stdout.strip().split('\n')[:5]
            for line in lines:
                print(f"  {line}")
            if len(result.stdout.strip().split('\n')) > 5:
                print("  ...")
        else:
            print(f"❌ Error (exit code {result.returncode})")
            if result.stderr.strip():
                print(f"Error: {result.stderr[:200]}...")
                
        return duration, result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print(f"⏱️  Timeout after 10 seconds")
        return 10.0, False
    except Exception as e:
        print(f"❌ Exception: {e}")
        return float('inf'), False

def main():
    print("🚀 Testing WAL and FS Journal Fast Index Performance")
    print("=" * 70)
    
    # Test WAL commands
    wal_commands = [
        ("python wal_cli_fast.py wal status", "WAL Status"),
        ("python wal_cli_fast.py wal pending --limit 10", "WAL Pending Operations"),
        ("python wal_cli_fast.py wal health", "WAL Health Check"),
        ("python wal_fast_index.py status", "WAL Direct Index Status"),
    ]
    
    # Test FS Journal commands
    fs_commands = [
        ("python fs_journal_cli_fast.py fs-journal status", "FS Journal Status"),
        ("python fs_journal_cli_fast.py fs-journal files --limit 10", "FS Journal Files"),
        ("python fs_journal_cli_fast.py fs-journal recent --limit 5", "FS Journal Recent Ops"),
        ("python fs_journal_cli_fast.py fs-journal health", "FS Journal Health Check"),
        ("python fs_journal_fast_index.py status", "FS Journal Direct Index Status"),
    ]
    
    print("\n📊 WAL FAST INDEX TESTS")
    print("-" * 40)
    
    wal_times = []
    for cmd, desc in wal_commands:
        duration, success = time_command(cmd, desc)
        if success:
            wal_times.append(duration)
    
    print("\n📁 FS JOURNAL FAST INDEX TESTS")
    print("-" * 40)
    
    fs_times = []
    for cmd, desc in fs_commands:
        duration, success = time_command(cmd, desc)
        if success:
            fs_times.append(duration)
    
    # Summary
    print("\n📈 PERFORMANCE SUMMARY")
    print("=" * 70)
    
    if wal_times:
        avg_wal = sum(wal_times) / len(wal_times)
        print(f"📊 WAL Commands Average: {avg_wal:.3f} seconds")
        print(f"📊 WAL Commands Range: {min(wal_times):.3f} - {max(wal_times):.3f} seconds")
    
    if fs_times:
        avg_fs = sum(fs_times) / len(fs_times)
        print(f"📁 FS Journal Commands Average: {avg_fs:.3f} seconds")
        print(f"📁 FS Journal Commands Range: {min(fs_times):.3f} - {max(fs_times):.3f} seconds")
    
    # Check if all commands are fast (under 1 second)
    all_times = wal_times + fs_times
    fast_enough = [t for t in all_times if t < 1.0]
    
    if len(fast_enough) == len(all_times):
        print(f"✅ SUCCESS: All commands completed under 1 second!")
        print(f"🎯 ACHIEVEMENT: Fast index system is working as designed")
    else:
        slow_commands = len(all_times) - len(fast_enough)
        print(f"⚠️  WARNING: {slow_commands} commands took over 1 second")
    
    if all_times:
        overall_avg = sum(all_times) / len(all_times)
        print(f"\n⭐ Overall Average Response Time: {overall_avg:.3f} seconds")
        
        if overall_avg < 0.5:
            print("🚀 EXCELLENT: Ultra-fast response times!")
        elif overall_avg < 1.0:
            print("✅ GOOD: Fast response times suitable for CLI/MCP")
        else:
            print("⚠️  NEEDS OPTIMIZATION: Response times could be improved")

if __name__ == "__main__":
    main()
