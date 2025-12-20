#!/usr/bin/env python3
"""
Test script to verify program state works independently
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ipfs_kit_py'))

def test_state_reader():
    """Test the FastStateReader independently"""
    try:
        from ipfs_kit_py.program_state import FastStateReader
        reader = FastStateReader()
        summary = reader.get_summary()
        print("State Reader Test - SUCCESS")
        print("Summary:", summary)
        return True
    except Exception as e:
        print(f"State Reader Test - FAILED: {e}")
        return False

def test_state_cli():
    """Test the state CLI tool independently"""
    try:
        # Import and run the state CLI directly
        import subprocess
        result = subprocess.run([
            sys.executable, 
            'ipfs_kit_py/state_cli.py', 
            '--summary'
        ], capture_output=True, text=True, cwd=str(Path(__file__).resolve().parents[4]))
        
        if result.returncode == 0:
            print("State CLI Test - SUCCESS")
            print("Output:")
            print(result.stdout)
            return True
        else:
            print(f"State CLI Test - FAILED with return code {result.returncode}")
            print("Error:", result.stderr)
            return False
    except Exception as e:
        print(f"State CLI Test - FAILED: {e}")
        return False

if __name__ == "__main__":
    print("=== IPFS Kit Program State Independence Test ===")
    print()
    
    success1 = test_state_reader()
    print()
    success2 = test_state_cli()
    print()
    
    if success1 and success2:
        print("✅ All tests passed! Program state works independently.")
        sys.exit(0)
    else:
        print("❌ Some tests failed.")
        sys.exit(1)
