"""Tests for the huggingface_kit module.

These tests validate the functionality of the HuggingFace Hub integration
in the ipfs_kit_py package. They include testing of authentication, repository
operations, and file management.
"""

import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import pytest

from ipfs_kit_py.huggingface_kit import HUGGINGFACE_HUB_AVAILABLE, huggingface_kit


# @pytest.mark.skipif(
#     not HUGGINGFACE_HUB_AVAILABLE, reason="HuggingFace Hub package not installed"
# )
class TestHuggingFaceKit(unittest.TestCase):
    """Test cases for the huggingface_kit module."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock IPFS client
        self.mock_ipfs = MagicMock()
        self.mock_ipfs._testing_mode = True
        
        # Create a temporary directory for cache
        self.temp_dir = tempfile.mkdtemp()
        
        # Create the huggingface_kit instance
        self.hf_kit = huggingface_kit(
            resources={"token": "test_token"},
            metadata={"cache_dir": self.temp_dir}
        )
        
        # Mock authentication-related functions
        self.hf_login_patcher = patch('ipfs_kit_py.huggingface_kit.login')
        self.mock_login = self.hf_login_patcher.start()
        
        self.hf_whoami_patcher = patch('ipfs_kit_py.huggingface_kit.whoami')
        self.mock_whoami = self.hf_whoami_patcher.start()
        self.mock_whoami.return_value = {
            "name": "test_user",
            "email": "test@example.com",
            "orgs": ["test_org"]
        }
        
        # Patch _try_authenticate to make it think we're authenticated
        self.auth_patcher = patch.object(huggingface_kit, '_try_authenticate')
        self.mock_try_auth = self.auth_patcher.start()
        self.mock_try_auth.return_value = True
        
        # Set attributes directly for testing
        self.hf_kit.is_authenticated = True
        self.hf_kit.user_info = {
            "name": "test_user",
            "email": "test@example.com",
            "orgs": ["test_org"]
        }
        
        # Mock HfApi methods
        self.hf_api_patcher = patch('ipfs_kit_py.huggingface_kit.HfApi')
        self.mock_hf_api = self.hf_api_patcher.start()
        self.mock_api_instance = MagicMock()
        self.mock_hf_api.return_value = self.mock_api_instance
        
        # Replace the hf_kit's api with our mock
        self.hf_kit.api = self.mock_api_instance
        
        # Set up returns for different API methods
        # Create a proper mock with dict-like access
        repo_mock = MagicMock()
        repo_mock.id = "test_user/test_model"
        repo_mock.name = "test_model"
        repo_mock.namespace = "test_user"
        repo_mock.url = "https://huggingface.co/test_user/test_model"
        repo_mock.private = False
        repo_mock.repo_type = "model"
        repo_mock.lastModified = "2023-01-01T00:00:00.000Z"
        self.mock_api_instance.list_repos.return_value = [repo_mock]
        
        # Create a proper mock with dict-like access
        repo_info_mock = MagicMock()
        repo_info_mock.id = "test_user/test_model"
        repo_info_mock.name = "test_model"
        repo_info_mock.namespace = "test_user"
        repo_info_mock.url = "https://huggingface.co/test_user/test_model"
        repo_info_mock.private = False
        repo_info_mock.repo_type = "model"
        repo_info_mock.lastModified = "2023-01-01T00:00:00.000Z"
        repo_info_mock.tags = ["test_tag"]
        repo_info_mock.siblings = []
        repo_info_mock.card_data = {}
        repo_info_mock.default_branch = "main"
        self.mock_api_instance.repo_info.return_value = repo_info_mock
        
        self.mock_api_instance.list_repo_files.return_value = [
            "README.md",
            "config.json",
            "model/weights.bin"
        ]
        
        # For hf_hub_download, create a proper mock
        self.mock_api_instance.hf_hub_download = MagicMock(side_effect=self._mock_hf_hub_download)
        
    def tearDown(self):
        """Tear down test fixtures."""
        # Remove temporary directory
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            for root, dirs, files in os.walk(self.temp_dir, topdown=False):
                for file in files:
                    os.remove(os.path.join(root, file))
                for dir in dirs:
                    os.rmdir(os.path.join(root, dir))
            os.rmdir(self.temp_dir)
            
        # Stop patchers
        self.hf_login_patcher.stop()
        self.hf_whoami_patcher.stop()
        self.hf_api_patcher.stop()
        self.auth_patcher.stop()
        
    def _mock_hf_hub_download(self, repo_id, filename, revision, repo_type, local_dir, local_dir_use_symlinks):
        """Mock implementation of hf_hub_download."""
        # Create a temp file in the specified directory
        os.makedirs(local_dir, exist_ok=True)
        file_key = f"{repo_id}/{revision}/{filename}".replace("/", "_")
        local_path = os.path.join(local_dir, file_key)
        
        with open(local_path, "w") as f:
            f.write(f"Test content for {repo_id}/{filename} at revision {revision}")
            
        return local_path
        
    def test_initialization(self):
        """Test initialization of huggingface_kit."""
        # Create a new instance to properly test initialization
        with patch.object(huggingface_kit, '_try_authenticate') as mock_init_auth:
            mock_init_auth.return_value = True
            
            # Create a new instance to test initialization
            test_kit = huggingface_kit(
                resources={"token": "test_token2"},
                metadata={"cache_dir": self.temp_dir}
            )
            
            # Verify that the object was created correctly
            self.assertEqual(test_kit.resources.get("token"), "test_token2")
            self.assertEqual(test_kit.metadata.get("cache_dir"), self.temp_dir)
            self.assertTrue(test_kit.api is not None)
            
            # Verify that authentication was attempted during initialization
            mock_init_auth.assert_called_once()
        
    def test_login(self):
        """Test login functionality."""
        # Test login with token from resources
        result = self.hf_kit.login()
        
        # Verify login was called
        self.mock_login.assert_called()
        
        # Verify result structure
        self.assertTrue(result["success"])
        self.assertEqual(result["user"]["name"], "test_user")
        self.assertEqual(result["user"]["email"], "test@example.com")
        self.assertEqual(result["user"]["orgs"], ["test_org"])
        
    def test_whoami(self):
        """Test whoami functionality."""
        # Test whoami function
        result = self.hf_kit.whoami()
        
        # Verify whoami was called
        self.mock_whoami.assert_called()
        
        # Verify result structure
        self.assertTrue(result["success"])
        self.assertEqual(result["user"]["name"], "test_user")
        self.assertEqual(result["user"]["email"], "test@example.com")
        self.assertEqual(result["user"]["orgs"], ["test_org"])
        
    def test_create_repo(self):
        """Test repository creation."""
        # Mock create_repo function
        with patch('ipfs_kit_py.huggingface_kit.create_repo') as mock_create_repo:
            mock_create_repo.return_value = "https://huggingface.co/test_user/new_repo"
            
            # Test create_repo function
            result = self.hf_kit.create_repo(
                repo_id="test_user/new_repo",
                repo_type="model",
                private=False
            )
            
            # Verify create_repo was called with correct parameters
            mock_create_repo.assert_called_once()
            
            # Verify result structure
            self.assertTrue(result["success"])
            self.assertEqual(result["repo_id"], "test_user/new_repo")
            self.assertEqual(result["repo_url"], "https://huggingface.co/test_user/new_repo")
            self.assertEqual(result["private"], False)
            
    def test_list_repos(self):
        """Test listing repositories."""
        # Test list_repos function
        result = self.hf_kit.list_repos(repo_type="model")
        
        # Verify list_repos was called with correct parameters
        self.mock_api_instance.list_repos.assert_called_once()
        
        # Verify result structure
        self.assertTrue(result["success"])
        self.assertEqual(result["repo_type"], "model")
        self.assertEqual(result["count"], 1)
        self.assertEqual(len(result["repos"]), 1)
        self.assertEqual(result["repos"][0]["id"], "test_user/test_model")
        self.assertEqual(result["repos"][0]["name"], "test_model")
        self.assertEqual(result["repos"][0]["owner"], "test_user")
        
    def test_repo_info(self):
        """Test getting repository information."""
        # Test repo_info function
        result = self.hf_kit.repo_info(repo_id="test_user/test_model")
        
        # Verify repo_info was called with correct parameters
        self.mock_api_instance.repo_info.assert_called_once_with(
            repo_id="test_user/test_model",
            repo_type="model"
        )
        
        # Verify result structure
        self.assertTrue(result["success"])
        self.assertEqual(result["repo_id"], "test_user/test_model")
        self.assertEqual(result["info"]["id"], "test_user/test_model")
        self.assertEqual(result["info"]["name"], "test_model")
        self.assertEqual(result["info"]["owner"], "test_user")
        self.assertEqual(result["info"]["tags"], ["test_tag"])
        
    def test_list_files(self):
        """Test listing files in a repository."""
        # Test list_files function
        result = self.hf_kit.list_files(
            repo_id="test_user/test_model",
            path="",
            revision="main"
        )
        
        # Verify list_repo_files was called with correct parameters
        self.mock_api_instance.list_repo_files.assert_called_once_with(
            repo_id="test_user/test_model",
            revision="main",
            repo_type="model"
        )
        
        # Verify result structure
        self.assertTrue(result["success"])
        self.assertEqual(result["repo_id"], "test_user/test_model")
        self.assertEqual(result["path"], "")
        self.assertEqual(result["count"], 3)
        self.assertEqual(len(result["directories"]), 1)  # "model" directory
        self.assertEqual(len(result["files"]), 2)  # README.md and config.json in root
        
    def test_download_file(self):
        """Test downloading a file from a repository."""
        # Test download_file function
        result = self.hf_kit.download_file(
            repo_id="test_user/test_model",
            filename="config.json",
            revision="main"
        )
        
        # Verify hf_hub_download was called with correct parameters
        self.mock_api_instance.hf_hub_download.assert_called_once()
        
        # Verify result structure
        self.assertTrue(result["success"])
        self.assertEqual(result["repo_id"], "test_user/test_model")
        self.assertEqual(result["filename"], "config.json")
        self.assertEqual(result["revision"], "main")
        self.assertTrue(isinstance(result["content"], bytes))
        self.assertTrue(result["size"] > 0)
        self.assertTrue(os.path.exists(result["local_path"]))
        
    def test_upload_file(self):
        """Test uploading a file to a repository."""
        # Create a temporary file to upload
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(b"Test file content")
            temp_file_path = temp_file.name
            
        try:
            # Test upload_file function with file path
            result = self.hf_kit.upload_file(
                repo_id="test_user/test_model",
                local_file=temp_file_path,
                path_in_repo="test_file.txt",
                commit_message="Test commit"
            )
            
            # Verify upload_file was called with correct parameters
            self.mock_api_instance.upload_file.assert_called_once()
            
            # Verify result structure
            self.assertTrue(result["success"])
            self.assertEqual(result["repo_id"], "test_user/test_model")
            self.assertEqual(result["path_in_repo"], "test_file.txt")
            
            # Reset the mock and test with direct content
            self.mock_api_instance.upload_file.reset_mock()
            
            # Test upload_file function with direct content
            result = self.hf_kit.upload_file(
                repo_id="test_user/test_model",
                local_file=b"Direct content",
                path_in_repo="direct_content.txt"
            )
            
            # Verify upload_file was called again
            self.mock_api_instance.upload_file.assert_called_once()
            
            # Verify result structure
            self.assertTrue(result["success"])
            self.assertEqual(result["repo_id"], "test_user/test_model")
            self.assertEqual(result["path_in_repo"], "direct_content.txt")
            
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                
    def test_method_call(self):
        """Test the __call__ method for invoking various huggingface_kit methods."""
        # Test __call__ with login method
        with patch.object(self.hf_kit, 'login') as mock_login:
            mock_login.return_value = {"success": True}
            result = self.hf_kit("login", token="test_token")
            mock_login.assert_called_once_with(token="test_token")
            self.assertEqual(result, {"success": True})
            
        # Test __call__ with list_repos method
        with patch.object(self.hf_kit, 'list_repos') as mock_list_repos:
            mock_list_repos.return_value = {"success": True, "repos": []}
            result = self.hf_kit("list_repos", repo_type="model")
            mock_list_repos.assert_called_once_with(repo_type="model")
            self.assertEqual(result, {"success": True, "repos": []})
            
        # Test __call__ with unknown method
        result = self.hf_kit("unknown_method")
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Unknown method: unknown_method")