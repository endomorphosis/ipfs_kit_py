#!/usr/bin/env python3
"""
Quick CLI Validation Script
===========================

This script performs a quick validation of the IPFS-Kit CLI after reorganization
to ensure all commands are accessible and working properly.
"""

import anyio
import subprocess
import sys
import time
from pathlib import Path

async def run_cmd(cmd, timeout=10):
    """Run a command and return success, stdout, stderr"""
    try:
        with anyio.fail_after(timeout):
            result = await anyio.run_process(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        return result.returncode == 0, result.stdout.decode(), result.stderr.decode()
    except TimeoutError:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", str(e)

async def main():
    print("🔍 Quick CLI Validation")
    print("=" * 40)
    
    project_root = Path(__file__).parent
    
    # Test 1: Basic CLI help
    print("1. Testing CLI help...")
    success, stdout, stderr = await run_cmd([
        sys.executable, "-m", "ipfs_kit_py.cli", "--help"
    ])
    
    if success:
        print("   ✅ CLI help working")
    else:
        print(f"   ❌ CLI help failed: {stderr}")
        return False
    
    # Test 2: Log command (new feature)
    print("2. Testing log command...")
    success, stdout, stderr = await run_cmd([
        sys.executable, "-m", "ipfs_kit_py.cli", "log", "--help"
    ])
    
    if success:
        print("   ✅ Log command working")
        
        # Test log subcommands
        for subcmd in ["show", "stats", "clear", "export"]:
            success, _, _ = await run_cmd([
                sys.executable, "-m", "ipfs_kit_py.cli", "log", subcmd, "--help"
            ])
            if success:
                print(f"   ✅ Log {subcmd} working")
            else:
                print(f"   ❌ Log {subcmd} failed")
    else:
        print(f"   ❌ Log command failed: {stderr}")
    
    # Test 3: Other main commands
    print("3. Testing main commands...")
    commands = ["daemon", "config", "pin", "resource", "metrics", "mcp"]
    
    for cmd in commands:
        success, _, stderr = await run_cmd([
            sys.executable, "-m", "ipfs_kit_py.cli", cmd, "--help"
        ])
        
        if success:
            print(f"   ✅ {cmd} command working")
        else:
            print(f"   ❌ {cmd} command failed: {stderr}")
    
    # Test 4: Performance check
    print("4. Testing performance...")
    start_time = time.time()
    success, _, _ = await run_cmd([
        sys.executable, "-m", "ipfs_kit_py.cli", "--help"
    ])
    duration = time.time() - start_time
    
    if success and duration < 1.0:
        print(f"   ✅ Performance good: {duration:.2f}s")
    elif success:
        print(f"   ⚠️  Performance slow: {duration:.2f}s")
    else:
        print("   ❌ Performance test failed")
    
    print("\n✅ Quick validation complete!")
    return True

if __name__ == "__main__":
    anyio.run(main)
