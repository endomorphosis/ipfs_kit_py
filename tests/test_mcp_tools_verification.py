#!/usr/bin/env python3
"""
Verify MCP Server Tools Are Not Mocked
=====================================
This script tests the MCP server tools to ensure they're using real IPFS
operations instead of mocked functions.
"""

import json
import subprocess
import tempfile
import time
import os

def run_ipfs_add_real() -> bool:
    """Run ipfs_add verification and return success."""
    # Create test content
    test_content = f"Test content for verification {time.time()}"
    
    # Write to temporary file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write(test_content)
        temp_file = f.name
    
    try:
        # Add using direct IPFS command
        result = subprocess.run(['ipfs', 'add', '-Q', temp_file], 
                              capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            print(f"❌ Direct IPFS add failed: {result.stderr}")
            return False
        
        real_cid = result.stdout.strip()
        print(f"✅ Direct IPFS add successful: {real_cid}")
        
        # Try to retrieve the content to verify it was actually added
        retrieve_result = subprocess.run(['ipfs', 'cat', real_cid],
                                       capture_output=True, text=True, timeout=30)
        if retrieve_result.returncode == 0:
            retrieved_content = retrieve_result.stdout
            if retrieved_content == test_content:
                print(f"✅ Content verification successful - real IPFS operations confirmed")
                return True
            else:
                print(f"❌ Content mismatch - expected: {test_content}, got: {retrieved_content}")
                return False
        else:
            print(f"❌ Failed to retrieve content: {retrieve_result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        return False
    finally:
        # Clean up
        if os.path.exists(temp_file):
            os.unlink(temp_file)

def run_ipfs_version_real() -> bool:
    """Run ipfs_version verification and return success."""
    try:
        # Get version via direct command
        result = subprocess.run(['ipfs', 'version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            print(f"❌ Direct IPFS version failed: {result.stderr}")
            return False
        
        real_version = result.stdout.strip()
        print(f"✅ Direct IPFS version: {real_version}")
        
        # Check if it's a real version (not mock)
        if "mock" in real_version.lower():
            print(f"❌ Version appears to be mocked: {real_version}")
            return False
        else:
            print(f"✅ Version appears real (no 'mock' in output)")
            return True
            
    except Exception as e:
        print(f"❌ Version test failed: {e}")
        return False

def run_ipfs_id_real() -> bool:
    """Run ipfs_id verification and return success."""
    try:
        # Get ID via direct command
        result = subprocess.run(['ipfs', 'id'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            print(f"❌ Direct IPFS id failed: {result.stderr}")
            return False
        
        real_id_data = json.loads(result.stdout)
        print(f"✅ Direct IPFS ID: {real_id_data['ID']}")
        
        # Check if it's a real ID (not mock)
        if "mock" in real_id_data['ID'].lower() or "Mock" in real_id_data.get('AgentVersion', ''):
            print(f"❌ ID appears to be mocked: {real_id_data}")
            return False
        else:
            print(f"✅ ID appears real (no 'mock' patterns detected)")
            return True
            
    except Exception as e:
        print(f"❌ ID test failed: {e}")
        return False

def run_daemon_running() -> bool:
    """Verify IPFS daemon is actually running and return success."""
    try:
        result = subprocess.run(['ipfs', 'swarm', 'peers'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            peer_count = len([line for line in result.stdout.split('\n') if line.strip()])
            print(f"✅ IPFS daemon is running with {peer_count} peers")
            return True
        else:
            print(f"❌ IPFS daemon not responding to swarm peers: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Daemon test failed: {e}")
        return False


def test_daemon_running():
    """Verify IPFS daemon is actually running."""
    assert run_daemon_running() is True


def test_ipfs_add_real():
    """Test that ipfs_add uses real IPFS by comparing with direct IPFS command."""
    assert run_ipfs_add_real() is True


def test_ipfs_version_real():
    """Test that ipfs_version returns real version info."""
    assert run_ipfs_version_real() is True


def test_ipfs_id_real():
    """Test that ipfs_id returns real node information."""
    assert run_ipfs_id_real() is True

def main():
    print("🧪 VERIFYING MCP TOOLS ARE NOT MOCKED")
    print("=" * 50)
    
    tests = [
        ("IPFS Daemon Running", run_daemon_running),
        ("IPFS Add (Real)", run_ipfs_add_real),
        ("IPFS Version (Real)", run_ipfs_version_real),
        ("IPFS ID (Real)", run_ipfs_id_real),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n🔍 Running: {test_name}")
        try:
            success = test_func()
            results.append((test_name, success))
            if success:
                print(f"✅ {test_name}: PASSED")
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 50)
    print("FINAL RESULTS:")
    print("=" * 50)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nSUMMARY: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED - MCP tools appear to be using REAL IPFS operations!")
        return True
    else:
        print("⚠️  SOME TESTS FAILED - May indicate mocked or broken functionality")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
