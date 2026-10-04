"""
Test the lock file handling improvements in the ipfs module.

This script verifies that the ipfs module properly handles lock files,
including detecting and removing stale lock files, and handling active lock files.
"""

import os
import sys
import time
import json
import signal
import unittest
import subprocess
import tempfile
import shutil
import logging
import psutil

# Make sure we can find the project modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import ipfs_kit
from ipfs_kit_py.ipfs_kit import ipfs_kit

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("lock_test")

class TestLockFileHandling(unittest.TestCase):
    """Test the lock file handling capabilities."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a temporary directory for test IPFS path
        self.test_dir = tempfile.mkdtemp(prefix="ipfs_test_")
        self.ipfs_path = os.path.join(self.test_dir, "ipfs")
        os.makedirs(self.ipfs_path, exist_ok=True)
        
        # Path to the repo.lock file
        self.lock_file_path = os.path.join(self.ipfs_path, "repo.lock")
        
        # IPFS config directory structure setup
        config_dir = os.path.join(self.ipfs_path, "config")
        with open(config_dir, 'w') as f:
            f.write("{}")  # Minimal config
            
        # Create basic kit instance
        self.kit = ipfs_kit(resources={"ipfs_path": self.ipfs_path})
        
        logger.info(f"Test setup complete with IPFS path: {self.ipfs_path}")
    
    def tearDown(self):
        """Clean up after test."""
        # Clean up temp directory
        shutil.rmtree(self.test_dir, ignore_errors=True)
        
        logger.info("Test environment cleaned up")
    
    def test_01_stale_lock_file(self):
        """Test handling stale lock file."""
        # Create a stale lock file with non-existent PID
        with open(self.lock_file_path, 'w') as f:
            f.write("999999")  # Non-existent PID
            
        logger.info(f"Created stale lock file at {self.lock_file_path} with PID 999999")
        
        # Verify that the lock file exists
        self.assertTrue(os.path.exists(self.lock_file_path), "Lock file should exist")
        
        # Run daemon_start which should handle the stale lock
        try:
            # Call ipfs_add method which should invoke daemon startup internally
            result = self.kit.ipfs_add("test content")
            
            # Check if operation succeeded
            logger.info(f"Add operation result: {result}")
            self.assertTrue(result.get("success", False), "Operation should succeed")
            
            # Verify lock file is either removed or replaced
            if os.path.exists(self.lock_file_path):
                # Check if it's a new lock file (different PID)
                with open(self.lock_file_path, 'r') as f:
                    new_pid = f.read().strip()
                
                logger.info(f"New lock file contains PID: {new_pid}")
                
                # Should be different from our stale PID
                self.assertNotEqual(new_pid, "999999", "Lock file should be updated with new PID")
                
                # Should be a valid process
                if new_pid.isdigit():
                    pid = int(new_pid)
                    try:
                        process = psutil.Process(pid)
                        process_name = process.name()
                        logger.info(f"Process with PID {pid} exists: {process_name}")
                        # Process should exist and be IPFS-related
                        self.assertTrue("ipfs" in process_name.lower(), "Process should be IPFS-related")
                    except psutil.NoSuchProcess:
                        self.fail(f"Process with PID {pid} doesn't exist")
            
        except Exception as e:
            logger.error(f"Error during test: {e}")
            self.fail(f"Exception during test: {e}")
    
    def test_02_active_lock_file(self):
        """Test handling active lock file with existing process."""
        # Start a real process and use its PID
        process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        pid = process.pid
        
        try:
            # Create an active lock file with the real PID
            with open(self.lock_file_path, 'w') as f:
                f.write(str(pid))
                
            logger.info(f"Created active lock file with PID {pid}")
            
            # Try to start IPFS daemon (should detect active lock)
            try:
                # Call ipfs_add method which should invoke daemon startup internally
                result = self.kit.ipfs_add("test content")
                
                # This might succeed or fail depending on implementation
                logger.info(f"Add operation result with active lock: {result}")
                
                # The lock file should still have our test process PID
                with open(self.lock_file_path, 'r') as f:
                    current_pid = f.read().strip()
                    
                logger.info(f"Lock file contains PID: {current_pid}")
                
                # Should still be our test process PID
                self.assertEqual(current_pid, str(pid), "Lock file should still contain test process PID")
                
            except Exception as e:
                logger.error(f"Error during active lock test: {e}")
                self.fail(f"Exception during active lock test: {e}")
                
        finally:
            # Clean up test process
            if process:
                process.terminate()
                process.wait()

if __name__ == "__main__":
    unittest.main()