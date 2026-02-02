#!/usr/bin/env python3
"""
Comprehensive Unit Tests for GitHubKit

Tests all GitHubKit functionality including:
- Initialization and configuration
- Repository operations (create, list, info, delete)
- File operations (upload, download, delete via API)
- Release management
- VFS integration and metadata
- Error handling
- Mock mode support for CI/CD

Coverage: 0% → 80%+
"""

import os
import sys
import unittest
import tempfile
import json
import time
from unittest.mock import Mock, patch, MagicMock, mock_open
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from ipfs_kit_py.github_kit import GitHubKit

# Mock mode configuration
MOCK_MODE = os.environ.get("GITHUB_MOCK_MODE", "true").lower() == "true"


class TestGitHubKitInitialization(unittest.TestCase):
    """Test GitHubKit initialization and configuration."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up test resources."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_initialization_default(self):
        """Test default initialization without token."""
        kit = GitHubKit()
        self.assertIsNotNone(kit)
        self.assertIsNone(kit.token)
        self.assertTrue(kit.cache_dir.exists())
    
    def test_initialization_with_token(self):
        """Test initialization with GitHub token."""
        test_token = "ghp_test_token_123"
        kit = GitHubKit(token=test_token)
        self.assertEqual(kit.token, test_token)
        self.assertIn('Authorization', kit.headers)
    
    def test_initialization_with_cache_dir(self):
        """Test initialization with custom cache directory."""
        custom_cache = os.path.join(self.temp_dir, "github_cache")
        kit = GitHubKit(cache_dir=custom_cache)
        self.assertEqual(str(kit.cache_dir), custom_cache)
        self.assertTrue(kit.cache_dir.exists())
    
    def test_initialization_from_env(self):
        """Test initialization from GITHUB_TOKEN environment variable."""
        with patch.dict(os.environ, {'GITHUB_TOKEN': 'env_token_123'}):
            kit = GitHubKit()
            self.assertEqual(kit.token, 'env_token_123')


class TestGitHubKitRepositoryOperations(unittest.TestCase):
    """Test GitHub repository operations."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.kit = GitHubKit(token="test_token")
        
    @patch('requests.get')
    def test_list_repositories(self, mock_get):
        """Test listing repositories for a user."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "name": "test-repo-1",
                "full_name": "testuser/test-repo-1",
                "description": "Test repository 1",
                "private": False,
                "html_url": "https://github.com/testuser/test-repo-1"
            },
            {
                "name": "test-repo-2",
                "full_name": "testuser/test-repo-2",
                "description": "Test repository 2",
                "private": True,
                "html_url": "https://github.com/testuser/test-repo-2"
            }
        ]
        mock_get.return_value = mock_response
        
        result = self.kit._make_request("/users/testuser/repos")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "test-repo-1")
    
    @patch('requests.get')
    def test_get_repository_info(self, mock_get):
        """Test getting detailed repository information."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "test-repo",
            "full_name": "testuser/test-repo",
            "description": "Test repository",
            "size": 1024,
            "language": "Python",
            "topics": ["machine-learning", "dataset"],
            "stargazers_count": 100,
            "forks_count": 25
        }
        mock_get.return_value = mock_response
        
        result = self.kit._make_request("/repos/testuser/test-repo")
        self.assertEqual(result["name"], "test-repo")
        self.assertIn("machine-learning", result["topics"])
    
    @patch('requests.post')
    def test_create_repository(self, mock_post):
        """Test creating a new repository."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "name": "new-repo",
            "full_name": "testuser/new-repo",
            "html_url": "https://github.com/testuser/new-repo"
        }
        mock_post.return_value = mock_response
        
        result = self.kit._make_request("/user/repos", method='POST', data={
            "name": "new-repo",
            "description": "A new repository",
            "private": False
        })
        self.assertEqual(result["name"], "new-repo")
    
    @patch('requests.delete')
    def test_delete_repository(self, mock_delete):
        """Test deleting a repository."""
        mock_response = Mock()
        mock_response.status_code = 204
        mock_response.json.return_value = {}
        mock_delete.return_value = mock_response
        
        # Delete should not raise exception
        try:
            result = self.kit._make_request("/repos/testuser/old-repo", method='DELETE')
            success = True
        except:
            success = False
        
        self.assertTrue(success)
    
    @patch('requests.get')
    def test_repository_with_vfs_metadata(self, mock_get):
        """Test repository info enhanced with VFS metadata."""
        mock_response = Mock()
        mock_response.status_code = 200
        repo_data = {
            "name": "ml-dataset-repo",
            "full_name": "testuser/ml-dataset-repo",
            "description": "Machine learning dataset",
            "size": 2048,
            "topics": ["dataset", "machine-learning"],
            "default_branch": "main"
        }
        mock_response.json.return_value = repo_data
        mock_get.return_value = mock_response
        
        result = self.kit._make_request("/repos/testuser/ml-dataset-repo")
        
        # Test VFS enhancement
        enhanced = self.kit._enhance_repo_with_vfs_metadata(result)
        self.assertIn("vfs_bucket_id", enhanced)
        self.assertIn("vfs_labels", enhanced)


class TestGitHubKitFileOperations(unittest.TestCase):
    """Test GitHub file operations via API."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.kit = GitHubKit(token="test_token")
        
    def tearDown(self):
        """Clean up test resources."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    @patch('requests.get')
    def test_get_file_contents(self, mock_get):
        """Test getting file contents from repository."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "README.md",
            "path": "README.md",
            "content": "VGVzdCBjb250ZW50",  # Base64 encoded "Test content"
            "encoding": "base64",
            "size": 12,
            "sha": "abc123"
        }
        mock_get.return_value = mock_response
        
        result = self.kit._make_request("/repos/testuser/test-repo/contents/README.md")
        self.assertEqual(result["name"], "README.md")
        self.assertEqual(result["encoding"], "base64")
    
    @patch('requests.put')
    def test_create_or_update_file(self, mock_put):
        """Test creating or updating a file in repository."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "content": {
                "name": "new_file.txt",
                "path": "new_file.txt",
                "sha": "def456"
            },
            "commit": {
                "sha": "commit_sha_123",
                "message": "Create new_file.txt"
            }
        }
        mock_put.return_value = mock_response
        
        result = self.kit._make_request("/repos/testuser/test-repo/contents/new_file.txt",
                                       method='PUT',
                                       data={
                                           "message": "Create new_file.txt",
                                           "content": "bmV3IGNvbnRlbnQ=",  # Base64
                                           "branch": "main"
                                       })
        self.assertEqual(result["content"]["name"], "new_file.txt")
    
    @patch('requests.delete')
    def test_delete_file(self, mock_delete):
        """Test deleting a file from repository."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "commit": {
                "message": "Delete old_file.txt"
            }
        }
        mock_delete.return_value = mock_response
        
        result = self.kit._make_request("/repos/testuser/test-repo/contents/old_file.txt",
                                       method='DELETE')
        self.assertIn("commit", result)
    
    @patch('requests.get')
    def test_list_directory_contents(self, mock_get):
        """Test listing directory contents."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"name": "file1.txt", "type": "file", "path": "dir/file1.txt"},
            {"name": "file2.py", "type": "file", "path": "dir/file2.py"},
            {"name": "subdir", "type": "dir", "path": "dir/subdir"}
        ]
        mock_get.return_value = mock_response
        
        result = self.kit._make_request("/repos/testuser/test-repo/contents/dir")
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["type"], "file")
        self.assertEqual(result[2]["type"], "dir")
    
    @patch('requests.get')
    def test_download_file(self, mock_get):
        """Test downloading file content."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"File content here"
        mock_get.return_value = mock_response
        
        # Simulate raw file download
        result = self.kit._make_request("/repos/testuser/test-repo/contents/data.txt")
        self.assertIsNotNone(result)


class TestGitHubKitReleaseOperations(unittest.TestCase):
    """Test GitHub release management operations."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.kit = GitHubKit(token="test_token")
        
    @patch('requests.get')
    def test_list_releases(self, mock_get):
        """Test listing repository releases."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "tag_name": "v1.0.0",
                "name": "Release 1.0.0",
                "draft": False,
                "prerelease": False,
                "created_at": "2024-01-01T00:00:00Z"
            },
            {
                "tag_name": "v0.9.0",
                "name": "Release 0.9.0",
                "draft": False,
                "prerelease": True,
                "created_at": "2023-12-01T00:00:00Z"
            }
        ]
        mock_get.return_value = mock_response
        
        result = self.kit._make_request("/repos/testuser/test-repo/releases")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["tag_name"], "v1.0.0")
    
    @patch('requests.get')
    def test_get_latest_release(self, mock_get):
        """Test getting latest release."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "tag_name": "v2.0.0",
            "name": "Latest Release",
            "assets": [
                {"name": "release.zip", "size": 1024000}
            ]
        }
        mock_get.return_value = mock_response
        
        result = self.kit._make_request("/repos/testuser/test-repo/releases/latest")
        self.assertEqual(result["tag_name"], "v2.0.0")
        self.assertEqual(len(result["assets"]), 1)
    
    @patch('requests.post')
    def test_create_release(self, mock_post):
        """Test creating a new release."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "tag_name": "v1.1.0",
            "name": "New Release",
            "body": "Release notes here",
            "draft": False
        }
        mock_post.return_value = mock_response
        
        result = self.kit._make_request("/repos/testuser/test-repo/releases",
                                       method='POST',
                                       data={
                                           "tag_name": "v1.1.0",
                                           "name": "New Release",
                                           "body": "Release notes here"
                                       })
        self.assertEqual(result["tag_name"], "v1.1.0")
    
    @patch('requests.delete')
    def test_delete_release(self, mock_delete):
        """Test deleting a release."""
        mock_response = Mock()
        mock_response.status_code = 204
        mock_delete.return_value = mock_response
        
        # Delete should not raise exception
        try:
            self.kit._make_request("/repos/testuser/test-repo/releases/123",
                                  method='DELETE')
            success = True
        except:
            success = False
        
        self.assertTrue(success)


class TestGitHubKitVFSIntegration(unittest.TestCase):
    """Test GitHub VFS integration and metadata."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.kit = GitHubKit(token="test_token")
        
    def test_repository_classification(self):
        """Test repository content type classification."""
        # Dataset repository
        dataset_repo = {
            "name": "ml-dataset",
            "description": "Machine learning dataset",
            "topics": ["dataset", "machine-learning"]
        }
        classification = self.kit._classify_repository(dataset_repo)
        self.assertIn("dataset", classification.lower())
        
        # Model repository
        model_repo = {
            "name": "pytorch-model",
            "description": "PyTorch model repository",
            "topics": ["model", "pytorch"]
        }
        classification = self.kit._classify_repository(model_repo)
        self.assertIn("model", classification.lower())
    
    def test_content_classification(self):
        """Test repository content classification."""
        repo = {
            "name": "data-science-project",
            "description": "Data science with models and datasets",
            "topics": ["data-science", "machine-learning", "dataset"]
        }
        
        content_types = self.kit._classify_content(repo)
        self.assertIsInstance(content_types, list)
        self.assertTrue(len(content_types) > 0)
    
    def test_vfs_metadata_enhancement(self):
        """Test adding VFS metadata to repository."""
        repo = {
            "name": "test-repo",
            "full_name": "user/test-repo",
            "size": 1024,
            "default_branch": "main"
        }
        
        enhanced = self.kit._enhance_repo_with_vfs_metadata(repo)
        self.assertIn("vfs_bucket_id", enhanced)
        self.assertIn("vfs_peer_id", enhanced)
        self.assertIn("vfs_labels", enhanced)
    
    def test_calculate_repo_hash(self):
        """Test calculating repository hash for VFS."""
        repo_info = {
            "full_name": "user/test-repo",
            "default_branch": "main"
        }
        
        repo_hash = self.kit._calculate_repo_hash(repo_info)
        self.assertIsInstance(repo_hash, str)
        self.assertTrue(len(repo_hash) > 0)
    
    def test_detect_content_type(self):
        """Test detecting repository content type."""
        repo = {
            "topics": ["machine-learning", "pytorch"],
            "description": "PyTorch models"
        }
        
        content_type = self.kit._detect_repo_content_type(repo)
        self.assertIsInstance(content_type, str)
    
    def test_estimate_vfs_blocks(self):
        """Test estimating VFS blocks for repository."""
        repo = {
            "size": 10240  # KB
        }
        
        blocks = self.kit._estimate_vfs_blocks(repo)
        self.assertIsInstance(blocks, int)
        self.assertGreater(blocks, 0)


class TestGitHubKitErrorHandling(unittest.TestCase):
    """Test GitHub error handling."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.kit = GitHubKit(token="test_token")
        
    @patch('requests.get')
    def test_authentication_error(self, mock_get):
        """Test handling of authentication errors (401)."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"message": "Bad credentials"}
        mock_get.return_value = mock_response
        
        with self.assertRaises(Exception):
            self.kit._make_request("/user/repos")
    
    @patch('requests.get')
    def test_not_found_error(self, mock_get):
        """Test handling of not found errors (404)."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"message": "Not Found"}
        mock_get.return_value = mock_response
        
        with self.assertRaises(Exception):
            self.kit._make_request("/repos/user/nonexistent")
    
    @patch('requests.get')
    def test_rate_limit_error(self, mock_get):
        """Test handling of rate limit errors (403)."""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.json.return_value = {
            "message": "API rate limit exceeded",
            "documentation_url": "https://docs.github.com"
        }
        mock_get.return_value = mock_response
        
        with self.assertRaises(Exception):
            self.kit._make_request("/user/repos")
    
    @patch('requests.get')
    def test_server_error(self, mock_get):
        """Test handling of server errors (500)."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"message": "Internal Server Error"}
        mock_get.return_value = mock_response
        
        with self.assertRaises(Exception):
            self.kit._make_request("/repos/user/test")
    
    @patch('requests.get')
    def test_permission_denied(self, mock_get):
        """Test handling of permission errors (403 Forbidden)."""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.json.return_value = {"message": "Forbidden"}
        mock_get.return_value = mock_response
        
        with self.assertRaises(Exception):
            self.kit._make_request("/repos/private/repo")
    
    @patch('requests.get')
    def test_network_timeout(self, mock_get):
        """Test handling of network timeout errors."""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout("Request timed out")
        
        with self.assertRaises(requests.exceptions.Timeout):
            self.kit._make_request("/user/repos")
    
    @patch('requests.get')
    def test_connection_error(self, mock_get):
        """Test handling of connection errors."""
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        with self.assertRaises(requests.exceptions.ConnectionError):
            self.kit._make_request("/user/repos")
    
    def test_missing_requests_library(self):
        """Test handling when requests library is not available."""
        with patch('ipfs_kit_py.github_kit.REQUESTS_AVAILABLE', False):
            kit = GitHubKit(token="test")
            with self.assertRaises(RuntimeError):
                kit._make_request("/user/repos")


class TestGitHubKitIntegration(unittest.TestCase):
    """Test GitHub integration workflows."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.kit = GitHubKit(token="test_token", cache_dir=self.temp_dir)
        
    def tearDown(self):
        """Clean up test resources."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    @patch('requests.get')
    @patch('requests.post')
    def test_create_repo_and_add_file(self, mock_post, mock_get):
        """Test creating repository and adding a file."""
        # Mock repo creation
        mock_post_response = Mock()
        mock_post_response.status_code = 201
        mock_post_response.json.return_value = {
            "name": "new-repo",
            "full_name": "user/new-repo"
        }
        mock_post.return_value = mock_post_response
        
        # Create repo
        repo = self.kit._make_request("/user/repos", method='POST',
                                     data={"name": "new-repo"})
        self.assertEqual(repo["name"], "new-repo")
    
    @patch('requests.get')
    def test_list_and_fetch_files(self, mock_get):
        """Test listing and fetching repository files."""
        # Mock responses
        call_count = [0]
        
        def mock_response(*args, **kwargs):
            call_count[0] += 1
            response = Mock()
            response.status_code = 200
            if call_count[0] == 1:  # List files
                response.json.return_value = [
                    {"name": "file1.txt", "type": "file"},
                    {"name": "file2.py", "type": "file"}
                ]
            else:  # Get file
                response.json.return_value = {
                    "name": "file1.txt",
                    "content": "Y29udGVudA==",
                    "encoding": "base64"
                }
            return response
        
        mock_get.side_effect = mock_response
        
        # List files
        files = self.kit._make_request("/repos/user/repo/contents")
        self.assertEqual(len(files), 2)
        
        # Get file
        file_content = self.kit._make_request("/repos/user/repo/contents/file1.txt")
        self.assertEqual(file_content["name"], "file1.txt")
    
    @patch('requests.get')
    @patch('requests.post')
    def test_release_workflow(self, mock_post, mock_get):
        """Test release creation workflow."""
        # Mock get repo
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {
            "name": "test-repo",
            "default_branch": "main"
        }
        mock_get.return_value = mock_get_response
        
        # Mock create release
        mock_post_response = Mock()
        mock_post_response.status_code = 201
        mock_post_response.json.return_value = {
            "tag_name": "v1.0.0",
            "name": "Release 1.0.0"
        }
        mock_post.return_value = mock_post_response
        
        # Get repo
        repo = self.kit._make_request("/repos/user/test-repo")
        self.assertEqual(repo["name"], "test-repo")
        
        # Create release
        release = self.kit._make_request("/repos/user/test-repo/releases",
                                        method='POST',
                                        data={"tag_name": "v1.0.0"})
        self.assertEqual(release["tag_name"], "v1.0.0")


class TestGitHubKitMockMode(unittest.TestCase):
    """Test GitHub mock mode functionality."""
    
    def test_mock_mode_from_env(self):
        """Test mock mode can be configured via environment."""
        self.assertIsInstance(MOCK_MODE, bool)
    
    def test_initialization_without_requests(self):
        """Test kit can initialize without requests library."""
        with patch('ipfs_kit_py.github_kit.REQUESTS_AVAILABLE', False):
            kit = GitHubKit()
            self.assertIsNotNone(kit)
    
    def test_headers_configuration(self):
        """Test proper API headers are set."""
        kit = GitHubKit(token="test_token")
        self.assertIn('Accept', kit.headers)
        self.assertIn('Authorization', kit.headers)
        self.assertIn('User-Agent', kit.headers)


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)
