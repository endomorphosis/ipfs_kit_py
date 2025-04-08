import os
import tempfile
import shutil
import unittest
from unittest.mock import patch, MagicMock

import pytest

# Tests have been updated to match the current API
# pytestmark = pytest.mark.skip(reason="Tests need updating to match current API")

from ipfs_kit_py.ipfs_kit import IPFSKit
from ipfs_kit_py.cli import main as cli_main


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

    @pytest.mark.parametrize(
        "role,path_exists,binaries_exist,download_success,expected_download",
        [
            # Role doesn't matter when path exists and binaries exist
            (
                "master",
                True,
                True,
                None,
                False,
            ),  # No download needed when binaries exist
            # Download needed when path exists but binaries don't
            (
                "master",
                True,
                False,
                True,
                True,
            ),  # Download needed and succeeds
            (
                "master",
                True,
                False,
                False,
                True,
            ),  # Download needed but fails
            # Create path and download when path doesn't exist
            (
                "master",
                False,
                False,
                True,
                True,
            ),  # Path creation and download succeed
            (
                "master",
                False,
                False,
                False,
                True,
            ),  # Path creation succeeds but download fails
            # Different roles have the same behavior for initialization
            (
                "worker",
                True,
                False,
                True,
                True,
            ),  # Worker role needs download
            (
                "leecher",
                True,
                False,
                True,
                True,
            ),  # Leecher role needs download
        ],
    )
    def test_ipfs_kit_initialization_download(
        self, role, path_exists, binaries_exist, download_success, expected_download
    ):
        """Test initialization with proper binary download."""
        # Reset the class-level flag - this is important for test isolation
        IPFSKit._BINARIES_DOWNLOADED = False

        # Create a mock data directory path
        ipfs_path = os.path.join(self.temp_dir, ".ipfs_kit")

        if path_exists:
            # Create the directory if it should exist
            os.makedirs(ipfs_path, exist_ok=True)

        # Mock binary existence check
        def mock_exists(path):
            if "ipfs" in path or "ipfs-cluster" in path:
                return binaries_exist
            # For other paths, use actual os.path.exists
            return os.path.exists(path)

        # Mock download_binaries function
        def mock_download(target_dir, arch=None, platform=None, force=False):
            """Mock binary download function."""
            # If download should succeed, create dummy binaries
            if download_success:
                os.makedirs(os.path.join(target_dir, "bin"), exist_ok=True)
                open(os.path.join(target_dir, "bin", "ipfs"), "w").close()
                open(os.path.join(target_dir, "bin", "ipfs-cluster-service"), "w").close()
                open(os.path.join(target_dir, "bin", "ipfs-cluster-ctl"), "w").close()

            return download_success

        # Apply patches
        with patch("os.path.exists", side_effect=mock_exists):
            with patch("os.makedirs", wraps=os.makedirs) as mock_makedirs:
                with patch(
                    "ipfs_kit_py.ipfs_kit.download_binaries", side_effect=mock_download
                ) as mock_download:
                    # Initialize IPFS Kit with specified role and directory
                    kit = IPFSKit(role=role, ipfs_path=ipfs_path)

                    # Verify directory creation if path doesn't exist
                    if not path_exists:
                        mock_makedirs.assert_called_with(ipfs_path, exist_ok=True)

                    # Verify download was attempted if expected
                    if expected_download:
                        mock_download.assert_called_once()
                    else:
                        mock_download.assert_not_called()

                    # Check the kit was initialized with appropriate class attributes
                    self.assertEqual(kit.role, role)
                    self.assertEqual(kit.ipfs_path, ipfs_path)

                    # Verify the class-level flag was set based on whether download succeeded
                    # Note that unsuccessful downloads still mark _BINARIES_DOWNLOADED as True
                    # to prevent retrying in the same session
                    if expected_download:
                        self.assertTrue(IPFSKit._BINARIES_DOWNLOADED)

    def test_ipfs_kit_path_creation(self):
        """Test IPFS Kit creates path directory when it doesn't exist."""
        # Reset the class-level flag - this is important for test isolation
        IPFSKit._BINARIES_DOWNLOADED = False

        # Create a mock data directory path
        ipfs_path = os.path.join(self.temp_dir, ".ipfs_kit_nonexistent")

        # Mock binary existence to pretend they exist to avoid download
        def mock_exists(path):
            if "ipfs" in path or "ipfs-cluster" in path:
                return True
            # For other paths, use actual os.path.exists
            return os.path.exists(path)

        # Apply patches
        with patch("os.path.exists", side_effect=mock_exists):
            with patch("os.makedirs", wraps=os.makedirs) as mock_makedirs:
                # Initialize IPFS Kit
                kit = IPFSKit(role="leecher", ipfs_path=ipfs_path)

                # Verify directory creation was attempted
                mock_makedirs.assert_called_with(ipfs_path, exist_ok=True)

                # Verify the directory now exists
                self.assertTrue(os.path.exists(ipfs_path))

    def test_ipfs_kit_uses_existing_path(self):
        """Test IPFS Kit uses existing path directory when it exists."""
        # Reset the class-level flag - this is important for test isolation
        IPFSKit._BINARIES_DOWNLOADED = False

        # Create a mock data directory path and ensure it exists
        ipfs_path = os.path.join(self.temp_dir, ".ipfs_kit_existing")
        os.makedirs(ipfs_path, exist_ok=True)

        # Create a test file in the directory to ensure it's not overwritten
        test_file_path = os.path.join(ipfs_path, "test_file.txt")
        with open(test_file_path, "w") as f:
            f.write("This is a test file")

        # Mock binary existence to pretend they exist to avoid download
        def mock_exists(path):
            if "ipfs" in path or "ipfs-cluster" in path:
                return True
            # For other paths, use actual os.path.exists
            return os.path.exists(path)

        # Apply patches
        with patch("os.path.exists", side_effect=mock_exists):
            with patch("os.makedirs", wraps=os.makedirs) as mock_makedirs:
                # Initialize IPFS Kit
                kit = IPFSKit(role="leecher", ipfs_path=ipfs_path)

                # Verify directory creation was attempted with exist_ok=True
                mock_makedirs.assert_called_with(ipfs_path, exist_ok=True)

                # Verify the directory and test file still exist
                self.assertTrue(os.path.exists(ipfs_path))
                self.assertTrue(os.path.exists(test_file_path))

                # Read the test file to ensure it wasn't modified
                with open(test_file_path, "r") as f:
                    content = f.read()
                self.assertEqual(content, "This is a test file")

    def test_ipfs_kit_binary_path_creation(self):
        """Test IPFS Kit creates binary directory when it doesn't exist."""
        # Reset the class-level flag - this is important for test isolation
        IPFSKit._BINARIES_DOWNLOADED = False

        # Create a mock data directory path
        ipfs_path = os.path.join(self.temp_dir, ".ipfs_kit")
        os.makedirs(ipfs_path, exist_ok=True)

        # Binary path inside ipfs_path
        bin_dir = os.path.join(ipfs_path, "bin")
        # Ensure it doesn't exist
        if os.path.exists(bin_dir):
            shutil.rmtree(bin_dir)

        # Mock download to create directory and binaries
        def mock_download(target_dir, arch=None, platform=None, force=False):
            """Mock binary download function."""
            os.makedirs(os.path.join(target_dir, "bin"), exist_ok=True)
            open(os.path.join(target_dir, "bin", "ipfs"), "w").close()
            return True

        # Apply patches
        with patch("os.path.exists", return_value=False):  # Pretend no binaries exist
            with patch(
                "ipfs_kit_py.ipfs_kit.download_binaries", side_effect=mock_download
            ) as mock_download:
                # Initialize IPFS Kit
                kit = IPFSKit(role="leecher", ipfs_path=ipfs_path)

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