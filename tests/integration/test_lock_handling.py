#!/usr/bin/env python3
"""
Test script for IPFS daemon lock file handling.

This script tests the enhanced lock file handling features added to the 
ipfs_kit SDK, ensuring that:
1. The daemon can detect existing lock files
2. The daemon can identify stale lock files and remove them
3. The daemon correctly handles error scenarios
"""

import os
import sys
import time
import shutil
import tempfile
import subprocess

# Add the parent directory to the path so we can import ipfs_kit_py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ipfs_kit_py.ipfs import ipfs_py
from ipfs_kit_py import ipfs_kit

def run_test():
    """Run a series of tests for lock file handling."""
    print("Starting IPFS lock file handling tests...")
    
    # Create a temporary directory for the IPFS repo
    test_dir = tempfile.mkdtemp(prefix="ipfs_lock_test_")
    print(f"Created temporary IPFS directory: {test_dir}")
    
    try:
        # Initialize IPFS in the temp directory
        init_ipfs(test_dir)
        
        # Test 1: Normal startup (no lock file)
        test_normal_startup(test_dir)
        
        # Test 2: Stale lock file handling
        test_stale_lock_file(test_dir)
        
        # Test 3: Lock file with disable removal
        test_lock_file_no_removal(test_dir)
        
        # Test 4: Active lock file with real process
        test_active_lock_file(test_dir)
        
        print("\nAll tests completed.")
    
    finally:
        # Clean up
        cleanup(test_dir)
        
def init_ipfs(repo_path):
    """Initialize a new IPFS repo in the specified directory."""
    print(f"\nInitializing IPFS repo in {repo_path}...")
    env = os.environ.copy()
    env["IPFS_PATH"] = repo_path
    
    try:
        result = subprocess.run(
            ["ipfs", "init", "--profile=test"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        print(f"IPFS initialized successfully: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error initializing IPFS: {e.stderr}")
        return False

def test_normal_startup(repo_path):
    """Test starting the daemon normally without any lock file."""
    print("\n=== Test 1: Normal Startup (No Lock File) ===")
    
    # Create a new IPFS instance pointing to our test repo
    ipfs = ipfs_py(metadata={"ipfs_path": repo_path})
    
    # Start the daemon
    result = ipfs.daemon_start()
    
    print(f"Start result: success={result['success']}, status={result.get('status')}")
    
    # Stop the daemon if it started
    if result.get('success'):
        stop_result = ipfs.daemon_stop()
        print(f"Stop result: success={stop_result['success']}")
    
    assert result.get('success'), "Normal startup should succeed"

def test_stale_lock_file(repo_path):
    """Test handling of a stale lock file."""
    print("\n=== Test 2: Stale Lock File Handling ===")
    
    # Create a lock file with a non-existent PID
    lock_path = os.path.join(repo_path, "repo.lock")
    with open(lock_path, 'w') as f:
        # Use a very high PID that's unlikely to exist
        f.write("999999")
    
    print(f"Created stale lock file at {lock_path} with non-existent PID")
    
    # Remember the modification time of the lock file
    original_lock_mtime = os.path.getmtime(lock_path) if os.path.exists(lock_path) else None
    print(f"Original lock file mtime: {original_lock_mtime}")
    
    # Create a new IPFS instance
    ipfs = ipfs_py(metadata={"ipfs_path": repo_path})
    
    # Start the daemon with stale lock removal enabled
    result = ipfs.daemon_start(remove_stale_lock=True)
    
    print(f"Start result with stale lock: success={result['success']}, lock_detected={result.get('lock_file_detected', False)}, lock_removed={result.get('lock_file_removed', False)}")
    
    # Stop the daemon if it started
    if result.get('success'):
        stop_result = ipfs.daemon_stop()
        print(f"Stop result: success={stop_result['success']}")
    
    # Check if the lock file exists and print more details
    lock_exists = os.path.exists(lock_path)
    current_lock_mtime = os.path.getmtime(lock_path) if lock_exists else None
    lock_was_recreated = lock_exists and original_lock_mtime != current_lock_mtime
    
    print(f"Lock file still exists? {lock_exists}")
    print(f"Current lock file mtime: {current_lock_mtime}")
    print(f"Lock file was recreated? {lock_was_recreated}")
    
    if lock_exists:
        print(f"Lock file content: {open(lock_path, 'r').read() if os.path.exists(lock_path) else 'N/A'}")
        # Let's check if the daemon is running
        try:
            ps_output = subprocess.check_output(["ps", "-ef"], text=True)
            ipfs_processes = [line for line in ps_output.splitlines() if "ipfs daemon" in line and "grep" not in line]
            print(f"Running IPFS processes:\n{chr(10).join(ipfs_processes) if ipfs_processes else 'None'}")
        except Exception as e:
            print(f"Error checking processes: {e}")
    
    assert result.get('lock_file_detected'), "Should detect the lock file"
    assert result.get('lock_file_removed'), "Should remove the stale lock file"
    assert result.get('success'), "Should successfully start after removing stale lock"
    
    # We've found that the IPFS daemon properly removes the stale lock file
    # but then creates a new lock file during startup. This is expected behavior.
    if lock_exists:
        assert lock_was_recreated, "If lock file exists after startup, it should be a new file (not the original stale one)"

def test_lock_file_no_removal(repo_path):
    """Test the behavior when stale lock file removal is disabled."""
    print("\n=== Test 3: Lock File With Removal Disabled ===")
    
    # Create a lock file with a non-existent PID
    lock_path = os.path.join(repo_path, "repo.lock")
    with open(lock_path, 'w') as f:
        # Use a very high PID that's unlikely to exist
        f.write("999999")
    
    print(f"Created stale lock file at {lock_path} with non-existent PID")
    
    # Create a new IPFS instance
    ipfs = ipfs_py(metadata={"ipfs_path": repo_path})
    
    # Start the daemon with stale lock removal disabled
    result = ipfs.daemon_start(remove_stale_lock=False)
    
    print(f"Start result with no removal: success={result['success']}, lock_detected={result.get('lock_file_detected', False)}, error_type={result.get('error_type')}")
    
    expected_error = "stale_lock_file"
    assert not result.get('success'), "Should fail when removal is disabled"
    assert result.get('error_type') == expected_error, f"Should report error type '{expected_error}'"
    assert os.path.exists(lock_path), "Lock file should still exist"
    
    # Clean up for next test
    os.remove(lock_path)

def test_active_lock_file(repo_path):
    """Test handling when lock file points to a real process."""
    print("\n=== Test 4: Active Lock File Handling ===")
    
    # Get the current process ID
    current_pid = os.getpid()
    
    # Create a lock file with the current process ID (which definitely exists)
    lock_path = os.path.join(repo_path, "repo.lock")
    with open(lock_path, 'w') as f:
        f.write(str(current_pid))
    
    print(f"Created active lock file at {lock_path} with current PID {current_pid}")
    
    # Create a new IPFS instance
    ipfs = ipfs_py(metadata={"ipfs_path": repo_path})
    
    # Start the daemon
    result = ipfs.daemon_start()
    
    print(f"Start result with active lock: success={result['success']}, status={result.get('status')}, lock_is_stale={result.get('lock_is_stale', 'N/A')}")
    
    assert result.get('success'), "Should succeed with active lock file"
    assert result.get('status') == "already_running", "Should report daemon already running"
    assert result.get('lock_is_stale') is False, "Should identify lock as non-stale"
    assert os.path.exists(lock_path), "Lock file should still exist"
    
    # Clean up for next test
    os.remove(lock_path)

def cleanup(repo_path):
    """Clean up the test directory."""
    try:
        shutil.rmtree(repo_path)
        print(f"\nCleaned up test directory: {repo_path}")
    except Exception as e:
        print(f"Error cleaning up test directory: {e}")

if __name__ == "__main__":
    run_test()