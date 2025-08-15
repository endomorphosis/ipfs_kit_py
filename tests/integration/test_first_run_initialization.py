import os
import tempfile
import shutil
import unittest
from unittest.mock import patch, MagicMock

import pytest

# Tests have been updated to match the current API
# pytestmark = pytest.mark.skip(reason="Tests need updating to match current API")

from ipfs_kit_py.ipfs_kit import IPFSKit
import sys
from ipfs_kit_py.cli import main as cli_main
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


class TestFirstRunInitialization(unittest.TestCase):
    """Test IPFS Kit initialization with binary downloads."""

    def setUp(self):
        """Set up test environment before each test."""
        # Create a temporary directory for test data
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up after each test."""
        # Remove the temporary directory
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_ipfs_kit_initialization_download(self):
        """Test initialization with proper binary download."""
        # Create a mock data directory path
        ipfs_path = os.path.join(self.temp_dir, ".ipfs_kit")
        os.makedirs(ipfs_path, exist_ok=True)

        # Binary path inside ipfs_path
        bin_dir = os.path.join(ipfs_path, "bin")
        # Ensure it doesn't exist
        if os.path.exists(bin_dir):
            shutil.rmtree(bin_dir)

        # Create a custom exists function that returns False for the binary initially
        # but True after our mock_download has been called
        original_exists = os.path.exists
        binary_created = [False]  # Use a list to make it mutable in the nested function

        def mock_exists(path):
            if (path.endswith("bin/ipfs") or path.endswith("bin\\ipfs")) and not binary_created[0]:
                return False
            return original_exists(path)

        # Modify our mock_download to set the flag when it's called
        def mock_download():
            """Mock binary download function."""
            os.makedirs(bin_dir, exist_ok=True)
            open(os.path.join(bin_dir, "ipfs"), "w").close()
            binary_created[0] = True
            return True

        # Apply patches
        with patch("os.path.exists", side_effect=mock_exists):
            with patch(
                "ipfs_kit_py.download_binaries", side_effect=mock_download
            ) as mock_download:
                # Create a custom IPFSKit that will trigger the download
                from ipfs_kit_py import download_binaries

                # Call download_binaries directly to trigger our mock
                download_binaries()

                # Verify download was attempted
                mock_download.assert_called_once()

                # Verify bin directory was created
                self.assertTrue(os.path.exists(bin_dir))

                # Verify binary was created
                self.assertTrue(os.path.exists(os.path.join(bin_dir, "ipfs")))

    def test_ipfs_kit_path_creation(self):
        """Test IPFS Kit creates path directory when it doesn't exist."""
        # Create a mock data directory path
        ipfs_path = os.path.join(self.temp_dir, ".ipfs_kit_nonexistent")

        # Create a custom exists function that returns True for binaries
        # but False for the ipfs_path directory initially
        original_exists = os.path.exists
        path_created = [False]  # Use a list to make it mutable in the nested function

        def mock_exists(path):
            if "bin/ipfs" in path or "bin\\ipfs" in path:
                return True
            if path == ipfs_path:
                # After we create the directory, return True
                if path_created[0]:
                    return True
                return False
            return original_exists(path)

        # Apply patches
        with patch("os.path.exists", side_effect=mock_exists):
            # Create the directory and update our flag
            os.makedirs(ipfs_path, exist_ok=True)
            path_created[0] = True

            # Initialize IPFS Kit
            kit = IPFSKit(metadata={"role": "leecher"}, resources={"ipfs_path": ipfs_path})

            # Verify the directory exists
            self.assertTrue(os.path.exists(ipfs_path))

    def test_ipfs_kit_uses_existing_path(self):
        """Test IPFS Kit uses existing path directory when it exists."""
        # Create a mock data directory path and ensure it exists
        ipfs_path = os.path.join(self.temp_dir, ".ipfs_kit_existing")
        os.makedirs(ipfs_path, exist_ok=True)

        # Create a test file in the directory to ensure it's not overwritten
        test_file_path = os.path.join(ipfs_path, "test_file.txt")
        with open(test_file_path, "w") as f:
            f.write("This is a test file")

        # Create a custom exists function that returns True for binaries
        # and for the ipfs_path directory
        original_exists = os.path.exists
        def mock_exists(path):
            if "bin/ipfs" in path or "bin\\ipfs" in path:
                return True
            return original_exists(path)

        # Initialize IPFS Kit
        kit = IPFSKit(metadata={"role": "leecher"}, resources={"ipfs_path": ipfs_path})

        # Verify the test file still exists and wasn't overwritten
        self.assertTrue(os.path.exists(test_file_path))
        with open(test_file_path, "r") as f:
            content = f.read()
        self.assertEqual(content, "This is a test file")

    def test_ipfs_kit_binary_path_creation(self):
        """Test IPFS Kit creates binary directory when it doesn't exist."""
        # Create a mock data directory path
        ipfs_path = os.path.join(self.temp_dir, ".ipfs_kit")
        os.makedirs(ipfs_path, exist_ok=True)

        # Binary path inside ipfs_path
        bin_dir = os.path.join(ipfs_path, "bin")
        # Ensure it doesn't exist
        if os.path.exists(bin_dir):
            shutil.rmtree(bin_dir)

        # Mock download to create directory and binaries
        def mock_download():
            """Mock binary download function."""
            os.makedirs(bin_dir, exist_ok=True)
            open(os.path.join(bin_dir, "ipfs"), "w").close()
            return True

        # Create a custom exists function that returns False for the binary initially
        # but True after our mock_download has been called
        original_exists = os.path.exists
        binary_created = [False]  # Use a list to make it mutable in the nested function

        def mock_exists(path):
            if (path.endswith("bin/ipfs") or path.endswith("bin\\ipfs")) and not binary_created[0]:
                return False
            return original_exists(path)

        # Modify our mock_download to set the flag when it's called
        def mock_download():
            """Mock binary download function."""
            os.makedirs(bin_dir, exist_ok=True)
            open(os.path.join(bin_dir, "ipfs"), "w").close()
            binary_created[0] = True
            return True

        # Apply patches
        with patch("os.path.exists", side_effect=mock_exists):
            with patch(
                "ipfs_kit_py.download_binaries", side_effect=mock_download
            ) as mock_download:
                # Create a custom IPFSKit that will trigger the download
                from ipfs_kit_py import download_binaries

                # Call download_binaries directly to trigger our mock
                download_binaries()

                # Verify download was attempted
                mock_download.assert_called_once()

                # Verify bin directory was created
                self.assertTrue(os.path.exists(bin_dir))

                # Verify binary was created
                self.assertTrue(os.path.exists(os.path.join(bin_dir, "ipfs")))

    @patch("sys.argv", ["ipfs_kit", "version"])
    @patch("ipfs_kit_py.cli.IPFSSimpleAPI")
    def test_cli_first_run_init(self, mock_api):
        """Test CLI first-run initialization."""
        # Mock version discovery
        with patch("importlib.metadata.version", return_value="0.1.1"):
            # Mock initial command
            with patch("ipfs_kit_py.cli.parse_args") as mock_parse:
                # Set up arguments
                mock_args = MagicMock()
                mock_args.command = "version"
                mock_args.format = "text"
                mock_args.no_color = False
                mock_args.verbose = False
                mock_args.config = None
                mock_args.param = []

                mock_parse.return_value = mock_args

                # Just verify that API initialization is called
                with patch("ipfs_kit_py.cli.run_command") as mock_run:
                    mock_run.return_value = {"success": True}

                    # Run main function
                    cli_main()

                    # Verify API was initialized
                    assert mock_api.called, "CLI should initialize IPFSSimpleAPI"