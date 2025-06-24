"""
Direct test of lock file handling functionality.

This script tests the improvements made to the daemon_start method in ipfs.py
to properly handle lock files (detect stale locks, handle active locks).
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

# Make sure we can find the project modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import necessary modules
import ipfs_kit_py.ipfs
from ipfs_kit_py.ipfs_kit import ipfs_kit

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("lock_test")

class TestLockFileHandling(unittest.TestCase):
    """Test the lock file handling capabilities in ipfs.py."""

    def setUp(self):
        """Set up test environment."""
        # Create a temporary directory for test IPFS path
        self.test_dir = tempfile.mkdtemp(prefix="ipfs_test_")
        self.ipfs_path = os.path.join(self.test_dir, "ipfs")
        os.makedirs(self.ipfs_path, exist_ok=True)

        # Path to the repo.lock file
        self.lock_file_path = os.path.join(self.ipfs_path, "repo.lock")

        # Create ipfs module instance directly
        self.ipfs = ipfs_kit_py.ipfs.ipfs(ipfs_path=self.ipfs_path)

        # Configure test path (need to monkey patch)
        self.ipfs.ipfs_path = self.ipfs_path

        logger.info(f"Test setup complete with IPFS path: {self.ipfs_path}")

    def tearDown(self):
        """Clean up after test."""
        # Make sure any daemons are stopped
        try:
            self.ipfs.daemon_stop()
        except Exception:
            pass

        # Clean up temp directory
        shutil.rmtree(self.test_dir)

        logger.info("Test environment cleaned up")

    def test_01_no_lock_file(self):
        """Test daemon start with no lock file (clean state)."""
        # Make sure lock file doesn't exist
        if os.path.exists(self.lock_file_path):
            os.remove(self.lock_file_path)

        # Start daemon
        result = self.ipfs.daemon_start()

        # Check result
        logger.info(f"Daemon start result (no lock): {result}")
        self.assertTrue(result.get("success", False))

        # Verify daemon is running (result should be already_running or success)
        status_result = self.ipfs.daemon_status()
        logger.info(f"Daemon status: {status_result}")

        self.assertTrue(
            status_result.get("success", False) or
            status_result.get("status") == "already_running"
        )

    def test_02_stale_lock_file_removal(self):
        """Test detection and removal of stale lock file."""
        # Make sure daemon is stopped
        self.ipfs.daemon_stop()
        time.sleep(1)

        # Create a stale lock file with non-existent PID
        with open(self.lock_file_path, 'w') as f:
            f.write("999999")  # Non-existent PID

        # Start daemon with stale lock removal enabled (default)
        result = self.ipfs.daemon_start()

        # Check result
        logger.info(f"Daemon start result (stale lock): {result}")

        # Should detect lock file
        self.assertTrue(result.get("lock_file_detected", False))

        # Should identify it as stale
        self.assertTrue(result.get("lock_is_stale", False))

        # Should have removed it
        self.assertTrue(result.get("lock_file_removed", False))

        # And ultimately succeeded
        self.assertTrue(result.get("success", False))

        # Verify daemon is running
        status_result = self.ipfs.daemon_status()
        logger.info(f"Daemon status after stale lock: {status_result}")
        self.assertTrue(status_result.get("success", False))

    def test_03_stale_lock_file_no_removal(self):
        """Test handling stale lock file without removal."""
        # Make sure daemon is stopped
        self.ipfs.daemon_stop()
        time.sleep(1)

        # Create a stale lock file with non-existent PID
        with open(self.lock_file_path, 'w') as f:
            f.write("999999")  # Non-existent PID

        # Start daemon with stale lock removal disabled
        result = self.ipfs.daemon_start(remove_stale_lock=False)

        # Check result
        logger.info(f"Daemon start result (stale lock, no removal): {result}")

        # Should detect lock file
        self.assertTrue(result.get("lock_file_detected", False))

        # Should identify it as stale
        self.assertTrue(result.get("lock_is_stale", False))

        # Should NOT have removed it
        self.assertFalse(result.get("lock_file_removed", True))

        # And should have failed
        self.assertFalse(result.get("success", True))

        # Error type should be stale_lock_file
        self.assertEqual(result.get("error_type"), "stale_lock_file")

    def test_04_active_lock_file(self):
        """Test handling an active lock file with real process."""
        # Make sure daemon is stopped
        self.ipfs.daemon_stop()
        time.sleep(1)

        # Start a dummy process and get its PID
        process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        pid = process.pid

        try:
            # Create lock file with actual process PID
            with open(self.lock_file_path, 'w') as f:
                f.write(str(pid))

            # Start daemon (should detect active lock)
            result = self.ipfs.daemon_start()

            # Check result
            logger.info(f"Daemon start result (active lock): {result}")

            # Should detect lock file
            self.assertTrue(result.get("lock_file_detected", False))

            # Should NOT identify it as stale
            self.assertFalse(result.get("lock_is_stale", True))

            # Should NOT have removed it
            self.assertFalse(result.get("lock_file_removed", True))

            # Should report already_running
            self.assertEqual(result.get("status"), "already_running")

        finally:
            # Clean up test process
            if process:
                process.terminate()
                process.wait()

    def test_05_lock_file_after_start(self):
        """Test that daemon creates a new lock file on start."""
        # Make sure daemon is stopped
        self.ipfs.daemon_stop()
        time.sleep(1)

        # Make sure lock file doesn't exist
        if os.path.exists(self.lock_file_path):
            os.remove(self.lock_file_path)

        # Start daemon
        result = self.ipfs.daemon_start()

        # Check result
        logger.info(f"Daemon start result: {result}")
        self.assertTrue(result.get("success", False))

        # Verify that a new lock file was created
        self.assertTrue(
            os.path.exists(self.lock_file_path),
            "Lock file should be created after daemon start"
        )

        # Verify the lock file contains a valid PID
        with open(self.lock_file_path, 'r') as f:
            lock_content = f.read().strip()

        # Should be a valid integer
        self.assertTrue(
            lock_content.isdigit(),
            f"Lock file should contain a valid PID, got: {lock_content}"
        )

        # And the process should exist
        pid = int(lock_content)
        process_exists = False
        try:
            # Send signal 0 to check if process exists
            os.kill(pid, 0)
            process_exists = True
        except OSError:
            pass

        self.assertTrue(
            process_exists,
            f"Process {pid} from lock file should exist"
        )

if __name__ == "__main__":
    unittest.main()
