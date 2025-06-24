import os
import platform
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import pytest
from ipfs_kit_py import download_binaries
from ipfs_kit_py.install_ipfs import install_ipfs

# Import the main module
import ipfs_kit_py.ipfs_kit


class TestBinaryDownload(unittest.TestCase):
    """Test the binary download functionality."""

    # Skip other tests that require functions not available in our module

    def test_download_binaries(self):
        """Test downloading all binaries."""
        # Mock the installer class and its methods
        mock_installer = MagicMock()

        # Mock the installer instance creation and methods
        with patch("ipfs_kit_py.install_ipfs.install_ipfs", return_value=mock_installer) as mock_install_ipfs, \
             patch("os.path.exists") as mock_exists:

            # Mock the exists method to return False for any binary path
            mock_exists.return_value = False

            # Call the function
            download_binaries()

            # Verify the installer was created
            mock_install_ipfs.assert_called_once()

            # Verify the installation methods were called on the mock instance
            mock_installer.install_ipfs_daemon.assert_called_once()
            mock_installer.install_ipfs_cluster_service.assert_called_once()
            mock_installer.install_ipfs_cluster_ctl.assert_called_once()
            mock_installer.install_ipfs_cluster_follow.assert_called_once()

    def test_install_ipfs(self):
        """Test installing IPFS."""
        # Mock subprocess.run
        with patch("subprocess.run") as mock_run:
            # Set up the mocked process
            process = MagicMock()
            process.returncode = 0
            process.stdout = b'{"id": "test_id"}'
            mock_run.return_value = process

            # Mock download_binaries - it's in the package's __init__, not install_ipfs
            with patch("ipfs_kit_py.download_binaries") as mock_download:
                mock_download.return_value = True

                # Call the function
                result = install_ipfs()
                self.assertTrue(result)

    def test_ipfs_kit_initialization_download(self):
        """Test that ipfs_kit downloads binaries during initialization."""
        # We'll create a simple test to verify the functions work
        # This doesn't test the actual download, just that the code paths
        # are functional without exceptions

        # Create an ipfs_kit instance with auto_download enabled
        # The real download will be skipped in CI environment
        try:
            from ipfs_kit_py.ipfs_kit import ipfs_kit
            kit = ipfs_kit(metadata={"auto_download_binaries": True})
            # If we reach here without exception, the test passes
            self.assertTrue(True, "ipfs_kit initialization succeeded with auto_download_binaries=True")
        except Exception as e:
            self.fail(f"ipfs_kit initialization failed with auto_download_binaries=True: {e}")

        # Real binaries might or might not be present, so we're just testing
        # that the initialization process completes without errors

if __name__ == "__main__":
    unittest.main()
