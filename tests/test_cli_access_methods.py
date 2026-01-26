#!/usr/bin/env python3
"""
CLI Access Methods Test
=======================

Test all different ways to access the IPFS-Kit CLI after reorganization.
"""

import subprocess
import sys
from pathlib import Path
import anyio

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
    except Exception as e:
        return False, "", str(e)

async def test_access_methods():
    """Test all CLI access methods"""
    
    print("🔧 Testing CLI Access Methods")
    print("=" * 50)
    
    project_root = Path(__file__).parent
    
    # Method 1: Module invocation (should always work)
    print("1. Module Invocation:")
    success, stdout, stderr = await run_cmd([sys.executable, "-m", "ipfs_kit_py.cli", "--help"])
    print(f"   python -m ipfs_kit_py.cli --help: {'✅ PASS' if success else '❌ FAIL'}")
    
    # Method 2: Console script (if in venv)
    print("\n2. Console Script:")
    venv_path = project_root / ".venv"
    if venv_path.exists():
        script_path = venv_path / "bin" / "ipfs-kit"
        if not script_path.exists():
            script_path = venv_path / "Scripts" / "ipfs-kit.exe"  # Windows
        
        if script_path.exists():
            success, stdout, stderr = await run_cmd([str(script_path), "--help"])
            print(f"   ipfs-kit --help (from venv): {'✅ PASS' if success else '❌ FAIL'}")
        else:
            print("   ipfs-kit script not found in venv")
    else:
        print("   No .venv directory found")
    
    # Method 3: Direct executable (shell wrapper)
    print("\n3. Direct Executable:")
    executable_path = project_root / "ipfs-kit"
    if executable_path.exists():
        success, stdout, stderr = await run_cmd([str(executable_path), "--help"])
        print(f"   ./ipfs-kit --help: {'✅ PASS' if success else '❌ FAIL'}")
    else:
        print("   ./ipfs-kit not found")
    
    # Method 4: Python script wrapper
    print("\n4. Python Script Wrapper:")
    script_path = project_root / "ipfs_kit_cli.py"
    if script_path.exists():
        success, stdout, stderr = await run_cmd([sys.executable, str(script_path), "--help"])
        print(f"   python ipfs_kit_cli.py --help: {'✅ PASS' if success else '❌ FAIL'}")
    else:
        print("   ipfs_kit_cli.py not found")
    
    # Test specific commands with different methods
    print("\n5. Testing Specific Commands:")
    
    # Test log command with module invocation
    success, stdout, stderr = await run_cmd([sys.executable, "-m", "ipfs_kit_py.cli", "log", "--help"])
    print(f"   Module + log command: {'✅ PASS' if success else '❌ FAIL'}")
    
    # Test daemon command
    success, stdout, stderr = await run_cmd([sys.executable, "-m", "ipfs_kit_py.cli", "daemon", "--help"])
    print(f"   Module + daemon command: {'✅ PASS' if success else '❌ FAIL'}")
    
    # Test config command
    success, stdout, stderr = await run_cmd([sys.executable, "-m", "ipfs_kit_py.cli", "config", "--help"])
    print(f"   Module + config command: {'✅ PASS' if success else '❌ FAIL'}")
    
    print("\n✅ CLI access method testing complete!")

if __name__ == "__main__":
    anyio.run(test_access_methods)
