"""
Test module for HuggingFaceModel in MCP server.

This module tests the HuggingFaceModel class that implements Hugging Face Hub operations.
"""

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch, mock_open

import pytest

from ipfs_kit_py.mcp.models.storage.huggingface_model import HuggingFaceModel


class TestHuggingFaceModel(unittest.TestCase):
    """Test cases for HuggingFaceModel."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock dependencies
        self.mock_hf_kit = MagicMock()
        self.mock_ipfs_model = MagicMock()
        self.mock_cache_manager = MagicMock()
        self.mock_credential_manager = MagicMock()

        # Create HuggingFaceModel instance with mock dependencies
        self.model = HuggingFaceModel(
            huggingface_kit_instance=self.mock_hf_kit,
            ipfs_model=self.mock_ipfs_model,
            cache_manager=self.mock_cache_manager,
            credential_manager=self.mock_credential_manager
        )

        # Create temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()
        self.test_file_path = os.path.join(self.temp_dir, "test_file.txt")
        with open(self.test_file_path, "w") as f:
            f.write("Test content for Hugging Face model")

    def tearDown(self):
        """Clean up test fixtures."""
        # Remove temporary directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initialization(self):
        """Test HuggingFaceModel initialization."""
        self.assertEqual(self.model.hf_kit, self.mock_hf_kit)
        self.assertEqual(self.model.ipfs_model, self.mock_ipfs_model)

    def test_authenticate_success(self):
        """Test successful authentication."""
        # Configure mock response
        self.mock_hf_kit.login.return_value = {
            "success": True,
            "user_info": {
                "name": "Test User",
                "email": "test@example.com"
            }
        }

        # Call method
        result = self.model.authenticate("test-token")

        # Check result
        self.assertTrue(result["success"])
        self.assertTrue(result["authenticated"])
        self.assertEqual(result["user_info"]["name"], "Test User")

        # Check that mock was called with correct parameters
        self.mock_hf_kit.login.assert_called_once_with(token="test-token")

    def test_authenticate_failure(self):
        """Test failed authentication."""
        # Configure mock response
        self.mock_hf_kit.login.return_value = {
            "success": False,
            "error": "Invalid token",
            "error_type": "AuthenticationError"
        }

        # Call method
        result = self.model.authenticate("invalid-token")

        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Invalid token")
        self.assertEqual(result["error_type"], "AuthenticationError")

    def test_authenticate_missing_token(self):
        """Test authentication with missing token."""
        # Call method with empty token
        result = self.model.authenticate("")

        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Token is required")
        self.assertEqual(result["error_type"], "ValidationError")

        # Check that login was not called
        self.mock_hf_kit.login.assert_not_called()

    def test_authenticate_missing_dependency(self):
        """Test authentication with missing HuggingFace kit."""
        # Create model with missing dependency
        model = HuggingFaceModel(
            huggingface_kit_instance=None,
            ipfs_model=self.mock_ipfs_model
        )

        # Call method
        result = model.authenticate("test-token")

        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Hugging Face kit not available")
        self.assertEqual(result["error_type"], "DependencyError")

    def test_create_repository_success(self):
        """Test successful repository creation."""
        # Configure mock response
        self.mock_hf_kit.create_repo.return_value = {
            "success": True,
            "url": "https://huggingface.co/test-user/test-repo",
            "repo": {
                "id": "test-user/test-repo",
                "name": "test-repo"
            }
        }

        # Call method
        result = self.model.create_repository(
            repo_id="test-user/test-repo",
            repo_type="model",
            private=False
        )

        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["repo_id"], "test-user/test-repo")
        self.assertEqual(result["repo_type"], "model")
        self.assertFalse(result["private"])
        self.assertEqual(result["url"], "https://huggingface.co/test-user/test-repo")
        self.assertEqual(result["repo_details"]["id"], "test-user/test-repo")

        # Check that mock was called with correct parameters
        self.mock_hf_kit.create_repo.assert_called_once_with(
            "test-user/test-repo",
            repo_type="model",
            private=False
        )

    def test_create_repository_failure(self):
        """Test failed repository creation."""
        # Configure mock response
        self.mock_hf_kit.create_repo.return_value = {
            "success": False,
            "error": "Repository already exists",
            "error_type": "RepositoryExistsError"
        }

        # Call method
        result = self.model.create_repository(
            repo_id="test-user/test-repo",
            repo_type="model",
            private=False
        )

        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Repository already exists")
        self.assertEqual(result["error_type"], "RepositoryExistsError")

    def test_create_repository_missing_repo_id(self):
        """Test repository creation with missing repo_id."""
        # Call method with empty repo_id
        result = self.model.create_repository(
            repo_id="",
            repo_type="model",
            private=False
        )

        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Repository ID is required")
        self.assertEqual(result["error_type"], "ValidationError")

        # Check that create_repo was not called
        self.mock_hf_kit.create_repo.assert_not_called()

    def test_create_repository_invalid_repo_type(self):
        """Test repository creation with invalid repo_type."""
        # Call method with invalid repo_type
        result = self.model.create_repository(
            repo_id="test-user/test-repo",
            repo_type="invalid",
            private=False
        )

        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Invalid repository type. Must be one of: model, dataset, space")
        self.assertEqual(result["error_type"], "ValidationError")

        # Check that create_repo was not called
        self.mock_hf_kit.create_repo.assert_not_called()

    def test_upload_file_success(self):
        """Test successful file upload."""
        # Configure mock response
        self.mock_hf_kit.upload_file_to_repo.return_value = {
            "success": True,
            "url": "https://huggingface.co/test-user/test-repo/blob/main/test-file.txt",
            "commit_url": "https://huggingface.co/test-user/test-repo/commit/abc123"
        }

        # Call method
        result = self.model.upload_file(
            file_path=self.test_file_path,
            repo_id="test-user/test-repo",
            path_in_repo="test-file.txt",
            commit_message="Upload test file",
            repo_type="model"
        )

        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["repo_id"], "test-user/test-repo")
        self.assertEqual(result["repo_type"], "model")
        self.assertEqual(result["path_in_repo"], "test-file.txt")
        self.assertGreater(result["size_bytes"], 0)
        self.assertEqual(result["url"], "https://huggingface.co/test-user/test-repo/blob/main/test-file.txt")
        self.assertEqual(result["commit_url"], "https://huggingface.co/test-user/test-repo/commit/abc123")

        # Check that mock was called with correct parameters
        self.mock_hf_kit.upload_file_to_repo.assert_called_once_with(
            repo_id="test-user/test-repo",
            file_path=self.test_file_path,
            path_in_repo="test-file.txt",
            commit_message="Upload test file",
            repo_type="model"
        )

    def test_upload_file_failure(self):
        """Test failed file upload."""
        # Configure mock response
        self.mock_hf_kit.upload_file_to_repo.return_value = {
            "success": False,
            "error": "Permission denied",
            "error_type": "PermissionError"
        }

        # Call method
        result = self.model.upload_file(
            file_path=self.test_file_path,
            repo_id="test-user/test-repo",
            path_in_repo="test-file.txt",
            commit_message="Upload test file",
            repo_type="model"
        )

        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Permission denied")
        self.assertEqual(result["error_type"], "PermissionError")

    def test_upload_file_missing_file(self):
        """Test file upload with missing file."""
        # Call method with non-existent file
        result = self.model.upload_file(
            file_path="/non/existent/file.txt",
            repo_id="test-user/test-repo",
            path_in_repo="test-file.txt",
            commit_message="Upload test file",
            repo_type="model"
        )

        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "File not found: /non/existent/file.txt")
        self.assertEqual(result["error_type"], "FileNotFoundError")

        # Check that upload_file_to_repo was not called
        self.mock_hf_kit.upload_file_to_repo.assert_not_called()

    def test_upload_file_missing_repo_id(self):
        """Test file upload with missing repo_id."""
        # Call method with empty repo_id
        result = self.model.upload_file(
            file_path=self.test_file_path,
            repo_id="",
            path_in_repo="test-file.txt",
            commit_message="Upload test file",
            repo_type="model"
        )

        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Repository ID is required")
        self.assertEqual(result["error_type"], "ValidationError")

        # Check that upload_file_to_repo was not called
        self.mock_hf_kit.upload_file_to_repo.assert_not_called()

    def test_download_file_success(self):
        """Test successful file download."""
        # Configure mock response
        self.mock_hf_kit.download_file_from_repo.return_value = {
            "success": True,
            "local_path": "/tmp/test-download.txt"
        }

        # Mock os.path.getsize to return a fixed size
        with patch('os.path.getsize', return_value=100):
            # Call method
            result = self.model.download_file(
                repo_id="test-user/test-repo",
                filename="test-file.txt",
                destination="/tmp/test-download.txt",
                revision="main",
                repo_type="model"
            )

        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["repo_id"], "test-user/test-repo")
        self.assertEqual(result["repo_type"], "model")
        self.assertEqual(result["filename"], "test-file.txt")
        self.assertEqual(result["destination"], "/tmp/test-download.txt")
        self.assertEqual(result["size_bytes"], 100)
        self.assertEqual(result["revision"], "main")

        # Check that mock was called with correct parameters
        self.mock_hf_kit.download_file_from_repo.assert_called_once_with(
            repo_id="test-user/test-repo",
            filename="test-file.txt",
            local_path="/tmp/test-download.txt",
            revision="main",
            repo_type="model"
        )

    def test_download_file_failure(self):
        """Test failed file download."""
        # Configure mock response
        self.mock_hf_kit.download_file_from_repo.return_value = {
            "success": False,
            "error": "File not found",
            "error_type": "FileNotFoundError"
        }

        # Call method
        result = self.model.download_file(
            repo_id="test-user/test-repo",
            filename="non-existent-file.txt",
            destination="/tmp/test-download.txt",
            revision="main",
            repo_type="model"
        )

        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "File not found")
        self.assertEqual(result["error_type"], "FileNotFoundError")

    def test_download_file_missing_repo_id(self):
        """Test file download with missing repo_id."""
        # Call method with empty repo_id
        result = self.model.download_file(
            repo_id="",
            filename="test-file.txt",
            destination="/tmp/test-download.txt",
            revision="main",
            repo_type="model"
        )

        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Repository ID is required")
        self.assertEqual(result["error_type"], "ValidationError")

        # Check that download_file_from_repo was not called
        self.mock_hf_kit.download_file_from_repo.assert_not_called()

    def test_download_file_missing_filename(self):
        """Test file download with missing filename."""
        # Call method with empty filename
        result = self.model.download_file(
            repo_id="test-user/test-repo",
            filename="",
            destination="/tmp/test-download.txt",
            revision="main",
            repo_type="model"
        )

        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Filename is required")
        self.assertEqual(result["error_type"], "ValidationError")

        # Check that download_file_from_repo was not called
        self.mock_hf_kit.download_file_from_repo.assert_not_called()

    def test_list_models_success(self):
        """Test successful models listing."""
        # Configure mock response
        mock_models = [
            {"id": "test-user/model1", "name": "model1"},
            {"id": "test-user/model2", "name": "model2"}
        ]
        self.mock_hf_kit.list_models.return_value = {
            "success": True,
            "models": mock_models
        }

        # Call method
        result = self.model.list_models(
            author="test-user",
            search="test-query",
            limit=10
        )

        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["author"], "test-user")
        self.assertEqual(result["search"], "test-query")
        self.assertEqual(result["models"], mock_models)

        # Check that mock was called with correct parameters
        self.mock_hf_kit.list_models.assert_called_once_with(
            author="test-user",
            search="test-query",
            limit=10
        )

    def test_list_models_failure(self):
        """Test failed models listing."""
        # Configure mock response
        self.mock_hf_kit.list_models.return_value = {
            "success": False,
            "error": "Failed to list models",
            "error_type": "ListError"
        }

        # Call method
        result = self.model.list_models(
            author="test-user",
            search="test-query",
            limit=10
        )

        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Failed to list models")
        self.assertEqual(result["error_type"], "ListError")

    def test_ipfs_to_huggingface_success(self):
        """Test successful transfer from IPFS to Hugging Face Hub."""
        # Configure mock responses
        self.mock_ipfs_model.get_content.return_value = {
            "success": True,
            "data": b"Test content from IPFS"
        }

        # Mock upload_file to return success
        with patch.object(self.model, 'upload_file') as mock_upload:
            mock_upload.return_value = {
                "success": True,
                "repo_id": "test-user/test-repo",
                "repo_type": "model",
                "path_in_repo": "test-cid",
                "size_bytes": 100,
                "url": "https://huggingface.co/test-user/test-repo/blob/main/test-cid",
                "commit_url": "https://huggingface.co/test-user/test-repo/commit/abc123"
            }

            # Test with tempfile.NamedTemporaryFile context manager
            with patch('tempfile.NamedTemporaryFile') as mock_temp_file, \
                 patch('os.unlink') as mock_unlink:

                # Configure mock temporary file
                mock_file = MagicMock()
                mock_file.name = "/tmp/mock-temp-file"
                mock_temp_file.return_value.__enter__.return_value = mock_file

                # Call method
                result = self.model.ipfs_to_huggingface(
                    cid="test-cid",
                    repo_id="test-user/test-repo",
                    path_in_repo="test-cid",
                    commit_message="Upload from IPFS",
                    repo_type="model",
                    pin=True
                )

                # Check that temporary file was written and removed
                mock_file.write.assert_called_once_with(b"Test content from IPFS")
                mock_unlink.assert_called_once_with("/tmp/mock-temp-file")

        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["ipfs_cid"], "test-cid")
        self.assertEqual(result["repo_id"], "test-user/test-repo")
        self.assertEqual(result["repo_type"], "model")
        self.assertEqual(result["path_in_repo"], "test-cid")
        self.assertEqual(result["size_bytes"], 100)
        self.assertEqual(result["url"], "https://huggingface.co/test-user/test-repo/blob/main/test-cid")

        # Check that mocks were called with correct parameters
        self.mock_ipfs_model.get_content.assert_called_once_with("test-cid")
        self.mock_ipfs_model.pin_content.assert_called_once_with("test-cid")

    def test_ipfs_to_huggingface_missing_cid(self):
        """Test IPFS to Hugging Face Hub transfer with missing CID."""
        # Call method with empty CID
        result = self.model.ipfs_to_huggingface(
            cid="",
            repo_id="test-user/test-repo",
            path_in_repo="test-cid",
            commit_message="Upload from IPFS",
            repo_type="model",
            pin=True
        )

        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "CID is required")
        self.assertEqual(result["error_type"], "ValidationError")

        # Check that get_content was not called
        self.mock_ipfs_model.get_content.assert_not_called()

    def test_ipfs_to_huggingface_missing_repo_id(self):
        """Test IPFS to Hugging Face Hub transfer with missing repo_id."""
        # Call method with empty repo_id
        result = self.model.ipfs_to_huggingface(
            cid="test-cid",
            repo_id="",
            path_in_repo="test-cid",
            commit_message="Upload from IPFS",
            repo_type="model",
            pin=True
        )

        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Repository ID is required")
        self.assertEqual(result["error_type"], "ValidationError")

        # Check that get_content was not called
        self.mock_ipfs_model.get_content.assert_not_called()

    def test_ipfs_to_huggingface_missing_dependency(self):
        """Test IPFS to Hugging Face Hub transfer with missing dependency."""
        # Create model with missing dependencies
        model = HuggingFaceModel(
            huggingface_kit_instance=None,
            ipfs_model=self.mock_ipfs_model
        )

        # Call method
        result = model.ipfs_to_huggingface(
            cid="test-cid",
            repo_id="test-user/test-repo",
            path_in_repo="test-cid",
            commit_message="Upload from IPFS",
            repo_type="model",
            pin=True
        )

        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Hugging Face kit not available")
        self.assertEqual(result["error_type"], "DependencyError")

    def test_ipfs_to_huggingface_ipfs_error(self):
        """Test IPFS to Hugging Face Hub transfer with IPFS error."""
        # Configure mock to return error
        self.mock_ipfs_model.get_content.return_value = {
            "success": False,
            "error": "Content not found",
            "error_type": "IPFSGetError"
        }

        # Test with tempfile.NamedTemporaryFile context manager
        with patch('tempfile.NamedTemporaryFile') as mock_temp_file, \
             patch('os.unlink') as mock_unlink:

            # Configure mock temporary file
            mock_file = MagicMock()
            mock_file.name = "/tmp/mock-temp-file"
            mock_temp_file.return_value.__enter__.return_value = mock_file

            # Call method
            result = self.model.ipfs_to_huggingface(
                cid="test-cid",
                repo_id="test-user/test-repo",
                path_in_repo="test-cid",
                commit_message="Upload from IPFS",
                repo_type="model",
                pin=True
            )

            # Check that temporary file was removed even in error case
            mock_unlink.assert_called_once_with("/tmp/mock-temp-file")

        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Failed to retrieve content from IPFS")
        self.assertEqual(result["error_type"], "IPFSGetError")

    def test_huggingface_to_ipfs_success(self):
        """Test successful transfer from Hugging Face Hub to IPFS."""
        # Configure mock responses
        # Mock download_file to return success
        with patch.object(self.model, 'download_file') as mock_download:
            mock_download.return_value = {
                "success": True,
                "repo_id": "test-user/test-repo",
                "repo_type": "model",
                "filename": "test-file.txt",
                "destination": "/tmp/mock-temp-file",
                "size_bytes": 100,
                "revision": "main"
            }

            # Configure the IPFS add_content mock
            self.mock_ipfs_model.add_content.return_value = {
                "success": True,
                "cid": "test-cid"
            }

            # Mock file operations
            with patch('builtins.open', mock_open(read_data=b"Test content from HF")), \
                 patch('os.path.getsize', return_value=100), \
                 patch('tempfile.NamedTemporaryFile') as mock_temp_file, \
                 patch('os.unlink') as mock_unlink:

                # Configure mock temporary file
                mock_file = MagicMock()
                mock_file.name = "/tmp/mock-temp-file"
                mock_temp_file.return_value.__enter__.return_value = mock_file

                # Call method
                result = self.model.huggingface_to_ipfs(
                    repo_id="test-user/test-repo",
                    filename="test-file.txt",
                    pin=True,
                    revision="main",
                    repo_type="model"
                )

                # Check that temporary file was removed
                mock_unlink.assert_called_once_with("/tmp/mock-temp-file")

        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["repo_id"], "test-user/test-repo")
        self.assertEqual(result["repo_type"], "model")
        self.assertEqual(result["filename"], "test-file.txt")
        self.assertEqual(result["ipfs_cid"], "test-cid")
        self.assertEqual(result["size_bytes"], 100)
        self.assertEqual(result["revision"], "main")

        # Check that pin was called
        self.mock_ipfs_model.pin_content.assert_called_once_with("test-cid")

    def test_huggingface_to_ipfs_missing_repo_id(self):
        """Test Hugging Face Hub to IPFS transfer with missing repo_id."""
        # Call method with empty repo_id
        result = self.model.huggingface_to_ipfs(
            repo_id="",
            filename="test-file.txt",
            pin=True,
            revision="main",
            repo_type="model"
        )

        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Repository ID is required")
        self.assertEqual(result["error_type"], "ValidationError")

    def test_huggingface_to_ipfs_missing_filename(self):
        """Test Hugging Face Hub to IPFS transfer with missing filename."""
        # Call method with empty filename
        result = self.model.huggingface_to_ipfs(
            repo_id="test-user/test-repo",
            filename="",
            pin=True,
            revision="main",
            repo_type="model"
        )

        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Filename is required")
        self.assertEqual(result["error_type"], "ValidationError")

    def test_huggingface_to_ipfs_missing_dependency(self):
        """Test Hugging Face Hub to IPFS transfer with missing dependency."""
        # Create model with missing dependencies
        model = HuggingFaceModel(
            huggingface_kit_instance=self.mock_hf_kit,
            ipfs_model=None
        )

        # Call method
        result = model.huggingface_to_ipfs(
            repo_id="test-user/test-repo",
            filename="test-file.txt",
            pin=True,
            revision="main",
            repo_type="model"
        )

        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "IPFS model not available")
        self.assertEqual(result["error_type"], "DependencyError")

    def test_huggingface_to_ipfs_download_error(self):
        """Test Hugging Face Hub to IPFS transfer with download error."""
        # Mock download_file to return error
        with patch.object(self.model, 'download_file') as mock_download:
            mock_download.return_value = {
                "success": False,
                "error": "Failed to download file",
                "error_type": "HuggingFaceDownloadError"
            }

            # Test with tempfile.NamedTemporaryFile context manager
            with patch('tempfile.NamedTemporaryFile') as mock_temp_file, \
                 patch('os.unlink') as mock_unlink:

                # Configure mock temporary file
                mock_file = MagicMock()
                mock_file.name = "/tmp/mock-temp-file"
                mock_temp_file.return_value.__enter__.return_value = mock_file

                # Call method
                result = self.model.huggingface_to_ipfs(
                    repo_id="test-user/test-repo",
                    filename="test-file.txt",
                    pin=True,
                    revision="main",
                    repo_type="model"
                )

                # Check that temporary file was removed even in error case
                mock_unlink.assert_called_once_with("/tmp/mock-temp-file")

        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Failed to download content from Hugging Face Hub")
        self.assertEqual(result["error_type"], "HuggingFaceDownloadError")

    def test_huggingface_to_ipfs_ipfs_error(self):
        """Test Hugging Face Hub to IPFS transfer with IPFS error."""
        # Mock download_file to return success
        with patch.object(self.model, 'download_file') as mock_download:
            mock_download.return_value = {
                "success": True,
                "repo_id": "test-user/test-repo",
                "repo_type": "model",
                "filename": "test-file.txt",
                "destination": "/tmp/mock-temp-file",
                "size_bytes": 100,
                "revision": "main"
            }

            # Configure the IPFS add_content mock to return error
            self.mock_ipfs_model.add_content.return_value = {
                "success": False,
                "error": "Failed to add content",
                "error_type": "IPFSAddError"
            }

            # Mock file operations
            with patch('builtins.open', mock_open(read_data=b"Test content from HF")), \
                 patch('os.path.getsize', return_value=100), \
                 patch('tempfile.NamedTemporaryFile') as mock_temp_file, \
                 patch('os.unlink') as mock_unlink:

                # Configure mock temporary file
                mock_file = MagicMock()
                mock_file.name = "/tmp/mock-temp-file"
                mock_temp_file.return_value.__enter__.return_value = mock_file

                # Call method
                result = self.model.huggingface_to_ipfs(
                    repo_id="test-user/test-repo",
                    filename="test-file.txt",
                    pin=True,
                    revision="main",
                    repo_type="model"
                )

                # Check that temporary file was removed
                mock_unlink.assert_called_once_with("/tmp/mock-temp-file")

        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Failed to add content to IPFS")
        self.assertEqual(result["error_type"], "IPFSAddError")


if __name__ == "__main__":
    unittest.main()
