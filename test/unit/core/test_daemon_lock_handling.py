"""
Test the lock file handling in daemon_start method.

This script tests the ipfs.py daemon_start method and verifies that it properly
handles lock files (detecting stale locks, handling active locks).
"""

import os
import sys
import time
import json
import logging
import unittest
import subprocess
import tempfile
import shutil
import importlib.util
import pytest
from unittest import mock

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Import ipfs.py directly
def import_module_from_path(path):
    """Import a module from a file path."""
    module_name = os.path.basename(path).replace('.py', '')
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

# Find ipfs.py module path
ipfs_py_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ipfs_kit_py', 'ipfs.py')

# Skip the test if ipfs.py isn't found
ipfs_module = None
if os.path.exists(ipfs_py_path):
    try:
        ipfs_module = import_module_from_path(ipfs_py_path)
        logger.info(f"Imported ipfs module from {ipfs_py_path}")
    except Exception as e:
        logger.error(f"Error importing ipfs module: {e}")
else:
    logger.error(f"Could not find ipfs.py at {ipfs_py_path}")

# Use pytest skip marker if ipfs module not available
pytestmark = pytest.mark.skipif(
    ipfs_module is None,
    reason="ipfs.py module not found or couldn't be imported"
)

# Test daemon_start lock file handling functionality
class TestDaemonLockHandling(unittest.TestCase):
    """Test lock file handling in daemon_start method."""

    def setUp(self):
        """Set up test environment with temporary IPFS path."""
        # Create temporary directory for test
        self.temp_dir = tempfile.mkdtemp(prefix="ipfs_test_")
        self.ipfs_path = os.path.join(self.temp_dir, "ipfs")
        os.makedirs(self.ipfs_path, exist_ok=True)  # Fixed typo: exist_ok instead of exist_errors

        # Path to lock file
        self.lock_file_path = os.path.join(self.ipfs_path, "repo.lock")

        # Skip if ipfs module not available
        if ipfs_module is None:
            pytest.skip("ipfs module not available")

        # Create ipfs object
        # ipfs_module should have all the necessary functions
        self.ipfs = ipfs_module.ipfs(path=self.ipfs_path)

        # Monkey patch ipfs_path
        self.ipfs.ipfs_path = self.ipfs_path

        logger.info(f"Test setup complete with IPFS path: {self.ipfs_path}")

    def tearDown(self):
        """Clean up temporary directories."""
        # Remove temporary directory
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        logger.info("Test environment cleaned up")

    def test_stale_lock_removal(self):
        """Test handling of stale lock file with automatic removal."""
        # Create a stale lock file with non-existent PID
        with open(self.lock_file_path, 'w') as f:
            f.write("999999")  # Non-existent PID

        logger.info(f"Created stale lock file with PID 999999 at {self.lock_file_path}")

        # Call daemon_start with stale lock removal enabled (default)
        # Mock the subprocess to avoid actually starting the daemon
        with mock.patch('subprocess.run') as mock_run:
            # Configure the mock to simulate successful daemon startup
            mock_process = mock.MagicMock()
            mock_process.returncode = 0
            mock_process.stdout = b'{"ID": "test-id"}'
            mock_run.return_value = mock_process

            # Call daemon_start
            result = self.ipfs.daemon_start()

            # Log the result
            logger.info(f"daemon_start result: {result}")

            # Assert that stale lock was detected
            self.assertTrue(result.get("lock_file_detected", False), "Should detect lock file")

            # Assert that it was identified as stale
            self.assertTrue(result.get("lock_is_stale", False), "Should identify lock as stale")

            # Assert that it was removed
            self.assertTrue(result.get("lock_file_removed", False), "Should remove stale lock file")

            # Assert that daemon start was ultimately successful
            self.assertTrue(result.get("success", False), "Daemon start should succeed")

    def test_stale_lock_no_removal(self):
        """Test handling of stale lock file with removal disabled."""
        # Create a stale lock file with non-existent PID
        with open(self.lock_file_path, 'w') as f:
            f.write("999999")  # Non-existent PID

        logger.info(f"Created stale lock file with PID 999999 at {self.lock_file_path}")

        # Call daemon_start with stale lock removal disabled
        # Mock the subprocess to avoid actually starting the daemon
        with mock.patch('subprocess.run') as mock_run:
            # Configure the mock to simulate successful daemon startup
            mock_process = mock.MagicMock()
            mock_process.returncode = 0
            mock_process.stdout = b'{"ID": "test-id"}'
            mock_run.return_value = mock_process

            # Call daemon_start with remove_stale_lock=False
            result = self.ipfs.daemon_start(remove_stale_lock=False)

            # Log the result
            logger.info(f"daemon_start result (no removal): {result}")

            # Assert that stale lock was detected
            self.assertTrue(result.get("lock_file_detected", False), "Should detect lock file")

            # Assert that it was identified as stale
            self.assertTrue(result.get("lock_is_stale", False), "Should identify lock as stale")

            # Assert that it was NOT removed
            self.assertFalse(result.get("lock_file_removed", True), "Should NOT remove stale lock file")

            # Assert that daemon start failed
            self.assertFalse(result.get("success", True), "Daemon start should fail")

            # Assert correct error type
            self.assertEqual(
                result.get("error_type"),
                "stale_lock_file",
                "Error type should be stale_lock_file"
            )

    def test_active_lock_file(self):
        """Test handling of active lock file with real process."""
        # Start a real process
        process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        pid = process.pid

        try:
            # Create lock file with real PID
            with open(self.lock_file_path, 'w') as f:
                f.write(str(pid))

            logger.info(f"Created active lock file with PID {pid} at {self.lock_file_path}")

            # Call daemon_start with active lock file
            # Mock the subprocess to avoid actually starting the daemon
            with mock.patch('subprocess.run') as mock_run:
                # Configure the mock to simulate successful daemon startup
                mock_process = mock.MagicMock()
                mock_process.returncode = 0
                mock_process.stdout = b'{"ID": "test-id"}'
                mock_run.return_value = mock_process

                # Call daemon_start
                result = self.ipfs.daemon_start()

                # Log the result
                logger.info(f"daemon_start result (active lock): {result}")

                # Assert that lock file was detected
                self.assertTrue(result.get("lock_file_detected", False), "Should detect lock file")

                # Assert that it was NOT identified as stale
                self.assertFalse(result.get("lock_is_stale", True), "Should NOT identify lock as stale")

                # Assert that daemon is already running
                self.assertEqual(
                    result.get("status"),
                    "already_running",
                    "Status should be already_running"
                )

        finally:
            # Clean up test process
            process.terminate()
            process.wait()

    def test_no_lock_file(self):
        """Test daemon start with no lock file."""
        # Ensure no lock file exists
        if os.path.exists(self.lock_file_path):
            os.remove(self.lock_file_path)

        logger.info("Removed any existing lock file")

        # Call daemon_start with no lock file
        # Mock the subprocess to avoid actually starting the daemon
        with mock.patch('subprocess.run') as mock_run:
            # Configure the mock to simulate successful daemon startup
            mock_process = mock.MagicMock()
            mock_process.returncode = 0
            mock_process.stdout = b'{"ID": "test-id"}'
            mock_run.return_value = mock_process

            # Call daemon_start
            result = self.ipfs.daemon_start()

            # Log the result
            logger.info(f"daemon_start result (no lock): {result}")

            # Assert that daemon start was successful
            self.assertTrue(result.get("success", False), "Daemon start should succeed")

            # Assert that lock file was not detected
            self.assertFalse(result.get("lock_file_detected", True), "Should not detect lock file")

if __name__ == "__main__":
    unittest.main()
