#!/usr/bin/env python
"""
Test cases for auto retry functionality in ipfs_kit_py.

This module tests the auto_retry_on_daemon_failure decorator and related
functionality in the ipfs_kit module, verifying that operations automatically
retry when daemons are not running and auto_start_daemons is enabled.
"""

import os
import time
import unittest
import logging
import pytest
from unittest.mock import patch, MagicMock

# Import the ipfs_kit module
from ipfs_kit_py.ipfs_kit import ipfs_kit
from ipfs_kit_py.error import IPFSError, create_result_dict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestAutoRetry(unittest.TestCase):
    """Test cases for automatic daemon retry functionality."""

    # # # # @pytest.mark.skip(reason="Test needs updating for new ipfs_kit structure") - removed by fix_all_tests.py - removed by fix_all_tests.py - removed by fix_all_tests.py - removed by fix_all_tests.py
    @patch('ipfs_kit_py.ipfs.ipfs_py.daemon_start')
    @patch('ipfs_kit_py.ipfs.ipfs_py.run_ipfs_command')
    def test_auto_retry_on_daemon_not_running(self, mock_run_cmd, mock_daemon_start):
        """Test auto retry when daemon is not running."""
        # Mock behavior for checking daemon status (not running)
        def mock_ps_effect(*args, **kwargs):
            return {"success": True, "stdout": "process info without ipfs daemon"}

        # Mock daemon start (successful)
        mock_daemon_start.return_value = {"success": True, "status": "started"}

        # Mock run command for checking status
        mock_run_cmd.side_effect = mock_ps_effect

        # Create ipfs_kit instance with auto_start_daemons=True
        kit = ipfs_kit(auto_start_daemons=True)

        # Mock ipfs.cat to fail first time due to daemon not running, then succeed
        original_cat = kit.ipfs.cat
        call_count = 0

        def mock_cat_with_retry(cid):
            nonlocal call_count
            if call_count == 0:
                call_count += 1
                result = create_result_dict("cat")
                result["error"] = "IPFS daemon is not running"
                return result
            else:
                # Second time succeeds
                result = create_result_dict("cat", success=True)
                result["data"] = b"test content"
                return result

        kit.ipfs.cat = mock_cat_with_retry

        # Call method that should trigger the retry
        result = kit.ipfs_cat("QmTest")

        # Verify daemon_start was called
        mock_daemon_start.assert_called_once()

        # Verify operation succeeded after retry
        self.assertTrue(result["success"])
        self.assertEqual(result.get("data"), b"test content")

        # Restore original method
        kit.ipfs.cat = original_cat

    # # # # @pytest.mark.skip(reason="Test needs updating for new ipfs_kit structure") - removed by fix_all_tests.py - removed by fix_all_tests.py - removed by fix_all_tests.py - removed by fix_all_tests.py
    @patch('ipfs_kit_py.ipfs.ipfs_py.daemon_start')
    @patch('ipfs_kit_py.ipfs.ipfs_py.run_ipfs_command')
    def test_auto_retry_disabled(self, mock_run_cmd, mock_daemon_start):
        """Test behavior when auto_start_daemons is disabled."""
        # Mock behavior for checking daemon status (not running)
        def mock_ps_effect(*args, **kwargs):
            return {"success": True, "stdout": "process info without ipfs daemon"}

        # Mock run command for checking status
        mock_run_cmd.side_effect = mock_ps_effect

        # Create ipfs_kit instance with auto_start_daemons=False
        kit = ipfs_kit(auto_start_daemons=False)

        # Mock ipfs.cat to fail due to daemon not running
        original_cat = kit.ipfs.cat

        def mock_cat_fail(cid):
            result = create_result_dict("cat")
            result["error"] = "IPFS daemon is not running"
            return result

        kit.ipfs.cat = mock_cat_fail

        # Call method that should not trigger retry
        result = kit.ipfs_cat("QmTest")

        # Verify daemon_start was NOT called
        mock_daemon_start.assert_not_called()

        # Verify operation failed
        self.assertFalse(result["success"])
        self.assertTrue("daemon_retry_disabled" in result)

        # Restore original method
        kit.ipfs.cat = original_cat

    # # # # @pytest.mark.skip(reason="Test needs updating for new ipfs_kit structure") - removed by fix_all_tests.py - removed by fix_all_tests.py - removed by fix_all_tests.py - removed by fix_all_tests.py
    @patch('ipfs_kit_py.ipfs.ipfs_py.daemon_start')
    @patch('ipfs_kit_py.ipfs.ipfs_py.run_ipfs_command')
    def test_retry_with_demo_method(self, mock_run_cmd, mock_daemon_start):
        """Test the demo method perform_operation_with_retry."""
        # Mock behavior for checking daemon status (not running)
        def mock_ps_effect(*args, **kwargs):
            return {"success": True, "stdout": "process info without ipfs daemon"}

        # Mock daemon start (successful)
        mock_daemon_start.return_value = {"success": True, "status": "started"}

        # Mock run command for checking status
        mock_run_cmd.side_effect = mock_ps_effect

        # Create ipfs_kit instance with auto_start_daemons=True
        kit = ipfs_kit(auto_start_daemons=True)

        # Mock ipfs.add to fail first time, then succeed
        original_add = kit.ipfs.add
        call_count = 0

        def mock_add_with_retry(path):
            nonlocal call_count
            if call_count == 0:
                call_count += 1
                result = create_result_dict("add")
                result["error"] = "IPFS daemon is not running"
                return result
            else:
                # Second time succeeds
                result = create_result_dict("add", success=True)
                result["Hash"] = "QmTestContent"
                return result

        kit.ipfs.add = mock_add_with_retry

        # Call the demo method
        result = kit.perform_operation_with_retry(
            operation_type="add",
            content="Test content string"
        )

        # Verify daemon_start was called
        mock_daemon_start.assert_called_once()

        # Verify operation succeeded after retry
        self.assertTrue(result["success"])
        self.assertEqual(result.get("Hash"), "QmTestContent")

        # Restore original method
        kit.ipfs.add = original_add

    # # # # @pytest.mark.skip(reason="Test needs updating for new ipfs_kit structure") - removed by fix_all_tests.py - removed by fix_all_tests.py - removed by fix_all_tests.py - removed by fix_all_tests.py
    def test_real_decorator_implementation(self):
        """Test that the decorator has proper function signature preservation."""
        # Get the original function and decorated function
        original_func = ipfs_kit.ipfs_add.__wrapped__
        decorated_func = ipfs_kit.ipfs_add

        # Verify function metadata is preserved
        self.assertEqual(decorated_func.__name__, original_func.__name__)
        self.assertEqual(decorated_func.__doc__, original_func.__doc__)

        # Check if decorator parameters are accessible
        # This is a bit of a hack but works for this test
        decorator_info = decorated_func.__closure__[0].cell_contents
        self.assertEqual(decorator_info.get('daemon_type', None), 'ipfs')
        self.assertEqual(decorator_info.get('max_retries', None), 3)


if __name__ == "__main__":
    unittest.main()
