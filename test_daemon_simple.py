#!/usr/bin/env python3
"""
Simple test to verify daemon management works correctly.
"""

import subprocess
import sys
import os

def test_ipfs_connection():
    """Test if IPFS daemon is accessible."""
    try:
        result = subprocess.run(['ipfs', 'id'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("✅ IPFS daemon is accessible via 'ipfs id'")
            return True
        else:
            print(f"❌ IPFS 'id' command failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ IPFS connection test failed: {e}")
        return False

def test_ipfs_api_direct():
    """Test if IPFS API is accessible directly via HTTP."""
    try:
        import requests
        response = requests.get('http://localhost:5001/api/v0/id', timeout=3)
        if response.status_code == 200:
            print("✅ IPFS API is accessible via HTTP")
            return True
        else:
            print(f"❌ IPFS API returned status {response.status_code}")
            return False
    except ImportError:
        print("⚠️  requests module not available for HTTP API test")
        return False
    except Exception as e:
        print(f"❌ IPFS API test failed: {e}")
        return False

def find_ipfs_processes():
    """Find existing IPFS daemon processes."""
    try:
        result = subprocess.run(['pgrep', '-f', 'ipfs daemon'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            pids = [int(pid.strip()) for pid in result.stdout.strip().split('\n') if pid.strip()]
            print(f"Found IPFS daemon processes: {pids}")
            return pids
        else:
            print("No IPFS daemon processes found")
            return []
    except Exception as e:
        print(f"❌ Failed to find IPFS processes: {e}")
        return []

def main():
    print("=== IPFS Daemon Test ===")
    
    # Test direct IPFS command
    ipfs_cmd_works = test_ipfs_connection()
    
    # Test HTTP API
    api_works = test_ipfs_api_direct()
    
    # Find existing processes
    processes = find_ipfs_processes()
    
    print("\n=== Summary ===")
    print(f"IPFS command works: {ipfs_cmd_works}")
    print(f"IPFS API works: {api_works}")
    print(f"IPFS processes found: {len(processes)}")
    
    if ipfs_cmd_works or api_works:
        print("✅ IPFS daemon is responsive - should use existing daemon")
    else:
        print("❌ IPFS daemon is not responsive")
        if processes:
            print("⚠️  Found daemon processes but they're not responsive")
        else:
            print("ℹ️  No daemon processes found - would need to start new daemon")

if __name__ == "__main__":
    main()
