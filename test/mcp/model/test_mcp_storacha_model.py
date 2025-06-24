"""
Test module for StorachaModel in MCP server.

This module tests the StorachaModel class that provides business logic for Storacha (Web3.Storage) operations.
"""

import os
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

import pytest

from ipfs_kit_py.mcp.models.storage.storacha_model import StorachaModel


class TestStorachaModel(unittest.TestCase):
    """Test cases for StorachaModel."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock dependencies
        self.mock_storacha_kit = MagicMock()
        self.mock_ipfs_model = MagicMock()
        self.mock_cache_manager = MagicMock()
        self.mock_credential_manager = MagicMock()

        # Configure credential manager to return test credentials
        self.mock_credential_manager.get_credentials.return_value = {
            "token": "test-token",
            "email": "test@example.com"
        }

        # Create StorachaModel instance with mock dependencies
        self.storacha_model = StorachaModel(
            storacha_kit_instance=self.mock_storacha_kit,
            ipfs_model=self.mock_ipfs_model,
            cache_manager=self.mock_cache_manager,
            credential_manager=self.mock_credential_manager
        )

        # Create temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()

        # Create a test file
        self.test_file_path = os.path.join(self.temp_dir, "test_file.txt")
        with open(self.test_file_path, "w") as f:
            f.write("Test content for Storacha upload")

    def tearDown(self):
        """Clean up test fixtures."""
        # Remove temporary directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initialization(self):
        """Test StorachaModel initialization."""
        # Check that dependencies are properly stored
        self.assertEqual(self.storacha_model.kit, self.mock_storacha_kit)
        self.assertEqual(self.storacha_model.ipfs_model, self.mock_ipfs_model)
        self.assertEqual(self.storacha_model.cache_manager, self.mock_cache_manager)
        self.assertEqual(self.storacha_model.credential_manager, self.mock_credential_manager)

        # Check that backend name is correct
        self.assertEqual(self.storacha_model.backend_name, "Storacha")

        # Check that operation_stats is initialized
        self.assertIsNotNone(self.storacha_model.operation_stats)
        self.assertEqual(self.storacha_model.operation_stats["upload_count"], 0)
        self.assertEqual(self.storacha_model.operation_stats["download_count"], 0)
        self.assertEqual(self.storacha_model.operation_stats["list_count"], 0)
        self.assertEqual(self.storacha_model.operation_stats["delete_count"], 0)

    def test_create_space_success(self):
        """Test successful space creation."""
        # Configure mock response
        self.mock_storacha_kit.w3_create.return_value = {
            "success": True,
            "space_did": "did:web3:test-space-did",
            "name": "test-space",
            "email": "test@example.com",
            "type": "space",
            "space_info": {"additional": "info"}
        }

        # Create space
        result = self.storacha_model.create_space(name="test-space")

        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["space_did"], "did:web3:test-space-did")
        self.assertEqual(result["name"], "test-space")
        self.assertIn("duration_ms", result)

        # Check that storacha_kit was called with correct parameters
        self.mock_storacha_kit.w3_create.assert_called_once_with(name="test-space")

        # Check that operation stats were updated
        self.assertEqual(self.storacha_model.operation_stats["success_count"], 1)

    def test_create_space_error(self):
        """Test space creation with error."""
        # Configure mock response with error
        self.mock_storacha_kit.w3_create.return_value = {
            "success": False,
            "error": "Failed to create space",
            "error_type": "SpaceCreationError"
        }

        # Create space
        result = self.storacha_model.create_space(name="test-space")

        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "SpaceCreationError")

        # Check that operation stats were updated
        self.assertEqual(self.storacha_model.operation_stats["failure_count"], 1)

    def test_list_spaces_success(self):
        """Test successful listing of spaces."""
        # Configure mock response
        self.mock_storacha_kit.w3_list_spaces.return_value = {
            "success": True,
            "spaces": [
                {
                    "did": "did:web3:space1",
                    "name": "Space 1",
                    "current": True
                },
                {
                    "did": "did:web3:space2",
                    "name": "Space 2",
                    "current": False
                }
            ]
        }

        # List spaces
        result = self.storacha_model.list_spaces()

        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)
        self.assertEqual(len(result["spaces"]), 2)
        self.assertIn("duration_ms", result)

        # Check that storacha_kit was called
        self.mock_storacha_kit.w3_list_spaces.assert_called_once()

        # Check that operation stats were updated
        self.assertEqual(self.storacha_model.operation_stats["list_count"], 1)
        self.assertEqual(self.storacha_model.operation_stats["success_count"], 1)

    def test_list_spaces_error(self):
        """Test listing spaces with error."""
        # Configure mock response with error
        self.mock_storacha_kit.w3_list_spaces.return_value = {
            "success": False,
            "error": "Failed to list spaces",
            "error_type": "ListSpacesError"
        }

        # List spaces
        result = self.storacha_model.list_spaces()

        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "ListSpacesError")

        # Check that operation stats were updated
        self.assertEqual(self.storacha_model.operation_stats["list_count"], 1)
        self.assertEqual(self.storacha_model.operation_stats["failure_count"], 1)

    def test_set_current_space_success(self):
        """Test successful setting of current space."""
        # Configure mock response
        self.mock_storacha_kit.w3_use.return_value = {
            "success": True,
            "space_did": "did:web3:test-space-did",
            "space_info": {"name": "Test Space"}
        }

        # Set current space
        result = self.storacha_model.set_current_space("did:web3:test-space-did")

        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["space_did"], "did:web3:test-space-did")
        self.assertIn("space_info", result)
        self.assertIn("duration_ms", result)

        # Check that storacha_kit was called with correct parameters
        self.mock_storacha_kit.w3_use.assert_called_once_with("did:web3:test-space-did")

        # Check that operation stats were updated
        self.assertEqual(self.storacha_model.operation_stats["success_count"], 1)

    def test_set_current_space_validation_error(self):
        """Test setting current space with validation error."""
        # Test with empty space DID
        result = self.storacha_model.set_current_space("")

        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "ValidationError")

    def test_set_current_space_error(self):
        """Test setting current space with error."""
        # Configure mock response with error
        self.mock_storacha_kit.w3_use.return_value = {
            "success": False,
            "error": "Failed to set space",
            "error_type": "SetSpaceError"
        }

        # Set current space
        result = self.storacha_model.set_current_space("did:web3:test-space-did")

        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "SetSpaceError")

        # Check that operation stats were updated
        self.assertEqual(self.storacha_model.operation_stats["failure_count"], 1)

    def test_upload_file_success(self):
        """Test successful file upload to Storacha."""
        # Configure mock response
        self.mock_storacha_kit.w3_up.return_value = {
            "success": True,
            "cid": "bafybeihrldbwbpchjhg56thesoa3vgv2rqnwk6xbwhsefl4pzae6yxhqgq",
            "root_cid": "bafybeihrldbwbpchjhg56thesoa3vgv2rqnwk6xbwhsefl4pzae6yxhqgq",
            "shard_size": 1000,
            "upload_id": "upload-123"
        }

        # Upload file
        result = self.storacha_model.upload_file(
            file_path=self.test_file_path,
            space_did="did:web3:test-space-did"
        )

        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["cid"], "bafybeihrldbwbpchjhg56thesoa3vgv2rqnwk6xbwhsefl4pzae6yxhqgq")
        self.assertEqual(result["space_did"], "did:web3:test-space-did")
        self.assertIn("size_bytes", result)
        self.assertIn("duration_ms", result)

        # Check that storacha_kit was called with correct parameters
        self.mock_storacha_kit.w3_up.assert_called_once_with(self.test_file_path)

        # Check that operation stats were updated
        self.assertEqual(self.storacha_model.operation_stats["upload_count"], 1)
        self.assertEqual(self.storacha_model.operation_stats["success_count"], 1)

    def test_upload_file_validation_error(self):
        """Test file upload with validation error."""
        # Test with non-existent file
        result = self.storacha_model.upload_file(
            file_path="/non/existent/file.txt",
            space_did="did:web3:test-space-did"
        )

        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "FileNotFoundError")

    def test_upload_file_space_error(self):
        """Test file upload with space setting error."""
        # Configure mock space setting response with error
        self.mock_storacha_kit.w3_use.return_value = {
            "success": False,
            "error": "Failed to set space",
            "error_type": "SetSpaceError"
        }

        # Upload file
        result = self.storacha_model.upload_file(
            file_path=self.test_file_path,
            space_did="did:web3:test-space-did"
        )

        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "SetSpaceError")
        self.assertIn("space_result", result)

    def test_upload_file_upload_error(self):
        """Test file upload with upload error."""
        # Configure mock space setting response
        self.mock_storacha_kit.w3_use.return_value = {
            "success": True,
            "space_did": "did:web3:test-space-did"
        }

        # Configure mock upload response with error
        self.mock_storacha_kit.w3_up.return_value = {
            "success": False,
            "error": "Failed to upload file",
            "error_type": "UploadError"
        }

        # Upload file
        result = self.storacha_model.upload_file(
            file_path=self.test_file_path,
            space_did="did:web3:test-space-did"
        )

        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "UploadError")

        # Check that operation stats were updated
        self.assertEqual(self.storacha_model.operation_stats["upload_count"], 1)
        self.assertEqual(self.storacha_model.operation_stats["failure_count"], 1)

    def test_upload_car_success(self):
        """Test successful CAR file upload to Storacha."""
        # Create a test CAR file
        test_car_path = os.path.join(self.temp_dir, "test.car")
        with open(test_car_path, "w") as f:
            f.write("Mock CAR file content")

        # Configure mock response
        self.mock_storacha_kit.w3_up_car.return_value = {
            "success": True,
            "cid": "bafybeihrldbwbpchjhg56thesoa3vgv2rqnwk6xbwhsefl4pzae6yxhqgq",
            "car_cid": "bagbaieraozpkyllj4kxrwfpxip6suqidzfkvsmwhuh3nfpknkwz5ueo3f54a",
            "root_cid": "bafybeihrldbwbpchjhg56thesoa3vgv2rqnwk6xbwhsefl4pzae6yxhqgq",
            "shard_size": 1000,
            "upload_id": "upload-123"
        }

        # Upload CAR file
        result = self.storacha_model.upload_car(
            car_path=test_car_path,
            space_did="did:web3:test-space-did"
        )

        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["cid"], "bafybeihrldbwbpchjhg56thesoa3vgv2rqnwk6xbwhsefl4pzae6yxhqgq")
        self.assertEqual(result["car_cid"], "bagbaieraozpkyllj4kxrwfpxip6suqidzfkvsmwhuh3nfpknkwz5ueo3f54a")
        self.assertEqual(result["space_did"], "did:web3:test-space-did")
        self.assertIn("size_bytes", result)
        self.assertIn("duration_ms", result)

        # Check that storacha_kit was called with correct parameters
        self.mock_storacha_kit.w3_up_car.assert_called_once_with(test_car_path)

        # Check that operation stats were updated
        self.assertEqual(self.storacha_model.operation_stats["upload_count"], 1)
        self.assertEqual(self.storacha_model.operation_stats["success_count"], 1)

    def test_list_uploads_success(self):
        """Test successful listing of uploads."""
        # Configure mock response
        self.mock_storacha_kit.w3_list.return_value = {
            "success": True,
            "uploads": [
                {
                    "cid": "bafybeihdwdcefgh",
                    "name": "file1.txt",
                    "created": time.time()
                },
                {
                    "cid": "bafybeijklmnopqr",
                    "name": "file2.txt",
                    "created": time.time()
                }
            ]
        }

        # List uploads
        result = self.storacha_model.list_uploads(space_did="did:web3:test-space-did")

        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)
        self.assertEqual(len(result["uploads"]), 2)
        self.assertEqual(result["space_did"], "did:web3:test-space-did")
        self.assertIn("duration_ms", result)

        # Check that storacha_kit was called
        self.mock_storacha_kit.w3_list.assert_called_once()

        # Check that operation stats were updated
        self.assertEqual(self.storacha_model.operation_stats["list_count"], 1)
        self.assertEqual(self.storacha_model.operation_stats["success_count"], 1)

    def test_delete_upload_success(self):
        """Test successful deletion of upload."""
        # Configure mock response
        self.mock_storacha_kit.w3_remove.return_value = {
            "success": True,
            "cid": "bafybeihrldbwbpchjhg56thesoa3vgv2rqnwk6xbwhsefl4pzae6yxhqgq"
        }

        # Delete upload
        result = self.storacha_model.delete_upload(
            cid="bafybeihrldbwbpchjhg56thesoa3vgv2rqnwk6xbwhsefl4pzae6yxhqgq",
            space_did="did:web3:test-space-did"
        )

        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["cid"], "bafybeihrldbwbpchjhg56thesoa3vgv2rqnwk6xbwhsefl4pzae6yxhqgq")
        self.assertEqual(result["space_did"], "did:web3:test-space-did")
        self.assertIn("duration_ms", result)

        # Check that storacha_kit was called with correct parameters
        self.mock_storacha_kit.w3_remove.assert_called_once_with("bafybeihrldbwbpchjhg56thesoa3vgv2rqnwk6xbwhsefl4pzae6yxhqgq")

        # Check that operation stats were updated
        self.assertEqual(self.storacha_model.operation_stats["delete_count"], 1)
        self.assertEqual(self.storacha_model.operation_stats["success_count"], 1)

    def test_delete_upload_validation_error(self):
        """Test deletion of upload with validation error."""
        # Test with empty CID
        result = self.storacha_model.delete_upload(
            cid="",
            space_did="did:web3:test-space-did"
        )

        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "ValidationError")

    @patch("tempfile.NamedTemporaryFile")
    @patch("os.unlink")
    def test_ipfs_to_storacha_success(self, mock_unlink, mock_named_temp_file):
        """Test successful transfer from IPFS to Storacha."""
        # Configure mock temporary file
        mock_temp_file = MagicMock()
        mock_temp_file.name = "/tmp/test-temp-file"
        mock_named_temp_file.return_value.__enter__.return_value = mock_temp_file

        # Configure mock IPFS model
        self.mock_ipfs_model.get_content.return_value = {
            "success": True,
            "data": b"Test content from IPFS",
            "cid": "QmTestCid"
        }
        self.mock_ipfs_model.pin_content.return_value = {
            "success": True,
            "cid": "QmTestCid"
        }

        # Mock the upload_file method to return success
        with patch.object(self.storacha_model, "upload_file") as mock_upload:
            mock_upload.return_value = {
                "success": True,
                "cid": "bafybeihrldbwbpchjhg56thesoa3vgv2rqnwk6xbwhsefl4pzae6yxhqgq",
                "size_bytes": 100
            }

            # Transfer from IPFS to Storacha
            result = self.storacha_model.ipfs_to_storacha(
                cid="QmTestCid",
                space_did="did:web3:test-space-did",
                pin=True
            )

            # Check result
            self.assertTrue(result["success"])
            self.assertEqual(result["ipfs_cid"], "QmTestCid")
            self.assertEqual(result["storacha_cid"], "bafybeihrldbwbpchjhg56thesoa3vgv2rqnwk6xbwhsefl4pzae6yxhqgq")
            self.assertEqual(result["space_did"], "did:web3:test-space-did")
            self.assertIn("size_bytes", result)
            self.assertIn("duration_ms", result)

            # Check that IPFS model was called
            self.mock_ipfs_model.get_content.assert_called_once_with("QmTestCid")
            self.mock_ipfs_model.pin_content.assert_called_once_with("QmTestCid")

            # Check that upload_file was called with correct parameters
            mock_upload.assert_called_once_with(
                mock_temp_file.name,
                "did:web3:test-space-did"
            )

            # Check that temporary file was cleaned up
            mock_unlink.assert_called_once_with(mock_temp_file.name)

    @patch("tempfile.NamedTemporaryFile")
    @patch("os.unlink")
    def test_ipfs_to_storacha_ipfs_error(self, mock_unlink, mock_named_temp_file):
        """Test IPFS to Storacha transfer with IPFS error."""
        # Configure mock temporary file
        mock_temp_file = MagicMock()
        mock_temp_file.name = "/tmp/test-temp-file"
        mock_named_temp_file.return_value.__enter__.return_value = mock_temp_file

        # Configure mock IPFS model to return error
        self.mock_ipfs_model.get_content.return_value = {
            "success": False,
            "error": "IPFS get failed",
            "error_type": "IPFSGetError"
        }

        # Transfer from IPFS to Storacha
        result = self.storacha_model.ipfs_to_storacha(
            cid="QmTestCid",
            space_did="did:web3:test-space-did"
        )

        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "IPFSGetError")
        self.assertIn("ipfs_result", result)

        # Check that temporary file was cleaned up
        mock_unlink.assert_called_once_with(mock_temp_file.name)

    @patch("tempfile.NamedTemporaryFile")
    @patch("os.unlink")
    def test_storacha_to_ipfs_success(self, mock_unlink, mock_named_temp_file):
        """Test successful transfer from Storacha to IPFS."""
        # Configure mock temporary file
        mock_temp_file = MagicMock()
        mock_temp_file.name = "/tmp/test-temp-file"
        mock_named_temp_file.return_value.__enter__.return_value = mock_temp_file

        # Configure mock Storacha kit to return space list
        self.mock_storacha_kit.w3_list_spaces.return_value = {
            "success": True,
            "spaces": [
                {
                    "did": "did:web3:test-space-did",
                    "name": "Test Space",
                    "current": True
                }
            ]
        }

        # Configure mock Storacha kit to return download result
        self.mock_storacha_kit.store_get.return_value = {
            "success": True,
            "cid": "bafybeihrldbwbpchjhg56thesoa3vgv2rqnwk6xbwhsefl4pzae6yxhqgq",
            "output_file": mock_temp_file.name
        }

        # Mock file open and read
        mock_file_content = b"Test content from Storacha"
        mock_file = MagicMock()
        mock_file.__enter__.return_value.read.return_value = mock_file_content
        mock_open = MagicMock(return_value=mock_file)

        # Configure mock IPFS model
        self.mock_ipfs_model.add_content.return_value = {
            "success": True,
            "cid": "QmNewTestCid"
        }
        self.mock_ipfs_model.pin_content.return_value = {
            "success": True,
            "cid": "QmNewTestCid"
        }

        with patch("builtins.open", mock_open):
            # Transfer from Storacha to IPFS
            result = self.storacha_model.storacha_to_ipfs(
                cid="bafybeihrldbwbpchjhg56thesoa3vgv2rqnwk6xbwhsefl4pzae6yxhqgq",
                space_did="did:web3:test-space-did",
                pin=True
            )

            # Check result
            self.assertTrue(result["success"])
            self.assertEqual(result["storacha_cid"], "bafybeihrldbwbpchjhg56thesoa3vgv2rqnwk6xbwhsefl4pzae6yxhqgq")
            self.assertEqual(result["ipfs_cid"], "QmNewTestCid")
            self.assertEqual(result["space_did"], "did:web3:test-space-did")
            self.assertIn("size_bytes", result)
            self.assertIn("duration_ms", result)

            # Check that Storacha kit was called with correct parameters
            self.mock_storacha_kit.store_get.assert_called_once_with(
                space_did="did:web3:test-space-did",
                cid="bafybeihrldbwbpchjhg56thesoa3vgv2rqnwk6xbwhsefl4pzae6yxhqgq",
                output_file=mock_temp_file.name
            )

            # Check that IPFS model was called with correct parameters
            self.mock_ipfs_model.add_content.assert_called_once()
            self.mock_ipfs_model.pin_content.assert_called_once_with("QmNewTestCid")

            # Check that file was read and temporary file was cleaned up
            mock_open.assert_called_once_with(mock_temp_file.name, "rb")
            mock_unlink.assert_called_once_with(mock_temp_file.name)

    def test_storacha_to_ipfs_validation_error(self):
        """Test Storacha to IPFS transfer with validation error."""
        # Test with empty CID
        result = self.storacha_model.storacha_to_ipfs(
            cid="",
            space_did="did:web3:test-space-did"
        )

        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "ValidationError")

    def test_get_stats(self):
        """Test getting operation statistics."""
        # Perform some operations to update stats
        self.storacha_model.operation_stats["upload_count"] = 5
        self.storacha_model.operation_stats["download_count"] = 3
        self.storacha_model.operation_stats["list_count"] = 2
        self.storacha_model.operation_stats["delete_count"] = 1
        self.storacha_model.operation_stats["success_count"] = 10
        self.storacha_model.operation_stats["failure_count"] = 1
        self.storacha_model.operation_stats["bytes_uploaded"] = 5000
        self.storacha_model.operation_stats["bytes_downloaded"] = 3000

        # Get stats
        stats = self.storacha_model.get_stats()

        # Check stats
        self.assertEqual(stats["backend_name"], "Storacha")
        self.assertEqual(stats["operation_stats"]["upload_count"], 5)
        self.assertEqual(stats["operation_stats"]["download_count"], 3)
        self.assertEqual(stats["operation_stats"]["list_count"], 2)
        self.assertEqual(stats["operation_stats"]["delete_count"], 1)
        self.assertEqual(stats["operation_stats"]["success_count"], 10)
        self.assertEqual(stats["operation_stats"]["failure_count"], 1)
        self.assertEqual(stats["operation_stats"]["bytes_uploaded"], 5000)
        self.assertEqual(stats["operation_stats"]["bytes_downloaded"], 3000)
        self.assertIn("timestamp", stats)
        self.assertIn("uptime_seconds", stats)

    def test_reset_stats(self):
        """Test resetting operation statistics."""
        # Perform some operations to update stats
        self.storacha_model.operation_stats["upload_count"] = 5
        self.storacha_model.operation_stats["download_count"] = 3
        self.storacha_model.operation_stats["list_count"] = 2
        self.storacha_model.operation_stats["delete_count"] = 1

        # Reset stats
        result = self.storacha_model.reset()

        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "reset_stats")
        self.assertEqual(result["backend_name"], "Storacha")

        # Check that previous stats are included
        self.assertEqual(result["previous_stats"]["upload_count"], 5)
        self.assertEqual(result["previous_stats"]["download_count"], 3)
        self.assertEqual(result["previous_stats"]["list_count"], 2)
        self.assertEqual(result["previous_stats"]["delete_count"], 1)

        # Check that stats were reset
        self.assertEqual(self.storacha_model.operation_stats["upload_count"], 0)
        self.assertEqual(self.storacha_model.operation_stats["download_count"], 0)
        self.assertEqual(self.storacha_model.operation_stats["list_count"], 0)
        self.assertEqual(self.storacha_model.operation_stats["delete_count"], 0)

    def test_health_check(self):
        """Test health check functionality."""
        # Run health check
        result = self.storacha_model.health_check()

        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "health_check")
        self.assertEqual(result["backend_name"], "Storacha")
        self.assertTrue(result["kit_available"])
        self.assertTrue(result["cache_available"])
        self.assertTrue(result["credential_available"])
        self.assertIn("duration_ms", result)

    def test_health_check_no_dependencies(self):
        """Test health check with missing dependencies."""
        # Create model with no dependencies
        model = StorachaModel()

        # Run health check
        result = model.health_check()

        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["operation"], "health_check")
        self.assertEqual(result["backend_name"], "Storacha")
        self.assertFalse(result["kit_available"])
        self.assertFalse(result["cache_available"])
        self.assertFalse(result["credential_available"])


if __name__ == "__main__":
    unittest.main()
