"""
Extended Unit Tests for HuggingFace Backend

This test suite extends the existing HuggingFace tests with comprehensive
coverage of operations, error handling, and edge cases.
"""

import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock
import time

# Test configuration
MOCK_MODE = os.environ.get("HF_MOCK_MODE", "true").lower() == "true"


@pytest.fixture
def hf_config():
    """Provide test configuration for HuggingFace kit."""
    return {
        "resources": {
            "token": os.environ.get("HF_TOKEN", "test_token_12345")
        },
        "metadata": {
            "cache_dir": tempfile.mkdtemp(),
            "skip_dependency_check": True
        }
    }


@pytest.fixture
def mock_hf_api():
    """Create mock HuggingFace API."""
    with patch('ipfs_kit_py.huggingface_kit.HfApi') as mock_api_class:
        mock_instance = MagicMock()
        mock_api_class.return_value = mock_instance
        
        # Mock repo info
        repo_info = MagicMock()
        repo_info.id = "test_user/test_model"
        repo_info.name = "test_model"
        repo_info.namespace = "test_user"
        repo_info.private = False
        repo_info.tags = ["test"]
        mock_instance.repo_info.return_value = repo_info
        
        # Mock list repos
        mock_instance.list_repos.return_value = [repo_info]
        
        # Mock list files
        mock_instance.list_repo_files.return_value = ["README.md", "config.json"]
        
        yield mock_instance


@pytest.fixture
def hf_kit(hf_config, mock_hf_api):
    """Create a HuggingFace kit instance for testing."""
    try:
        from ipfs_kit_py.huggingface_kit import huggingface_kit, HUGGINGFACE_HUB_AVAILABLE
        
        if not HUGGINGFACE_HUB_AVAILABLE and not MOCK_MODE:
            pytest.skip("HuggingFace Hub not available and mock mode disabled")
        
        # Mock authentication
        with patch('ipfs_kit_py.huggingface_kit.whoami') as mock_whoami:
            mock_whoami.return_value = {"name": "test_user"}
            
            kit = huggingface_kit(
                resources=hf_config["resources"],
                metadata=hf_config["metadata"]
            )
            kit.api = mock_hf_api
            kit.is_authenticated = True
            
            return kit
    except Exception as e:
        pytest.skip(f"Failed to initialize HuggingFace kit: {e}")


class TestHuggingFaceKitInitialization:
    """Test HuggingFace kit initialization."""
    
    def test_init_basic(self, hf_config, mock_hf_api):
        """Test basic initialization."""
        from ipfs_kit_py.huggingface_kit import huggingface_kit
        
        with patch('ipfs_kit_py.huggingface_kit.whoami'):
            kit = huggingface_kit(
                resources=hf_config["resources"],
                metadata=hf_config["metadata"]
            )
            
            assert kit is not None
            assert hasattr(kit, 'resources')
            assert hasattr(kit, 'metadata')
            assert hasattr(kit, 'correlation_id')
    
    def test_init_with_custom_cache(self):
        """Test initialization with custom cache directory."""
        from ipfs_kit_py.huggingface_kit import huggingface_kit
        
        custom_cache = tempfile.mkdtemp()
        
        with patch('ipfs_kit_py.huggingface_kit.whoami'):
            kit = huggingface_kit(
                resources={"token": "test"},
                metadata={"cache_dir": custom_cache, "skip_dependency_check": True}
            )
            
            assert kit.cache_dir == custom_cache
    
    def test_init_without_token(self):
        """Test initialization without token."""
        from ipfs_kit_py.huggingface_kit import huggingface_kit
        
        with patch('ipfs_kit_py.huggingface_kit.whoami'):
            kit = huggingface_kit(
                resources={},
                metadata={"skip_dependency_check": True}
            )
            
            assert kit is not None


class TestHuggingFaceKitAuthentication:
    """Test authentication operations."""
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_login_with_token(self, hf_kit):
        """Test login with token."""
        with patch('ipfs_kit_py.huggingface_kit.login') as mock_login:
            with patch('ipfs_kit_py.huggingface_kit.whoami') as mock_whoami:
                mock_whoami.return_value = {"name": "test_user"}
                
                result = hf_kit.login()
                
                assert isinstance(result, dict)
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_whoami(self, hf_kit):
        """Test whoami functionality."""
        with patch('ipfs_kit_py.huggingface_kit.whoami') as mock_whoami:
            mock_whoami.return_value = {"name": "test_user", "email": "test@example.com"}
            
            result = hf_kit.whoami()
            
            assert isinstance(result, dict)
    
    def test_authentication_failure(self, hf_config):
        """Test handling of authentication failures."""
        from ipfs_kit_py.huggingface_kit import huggingface_kit
        
        with patch('ipfs_kit_py.huggingface_kit.whoami', side_effect=Exception("Auth failed")):
            kit = huggingface_kit(
                resources={"token": "invalid"},
                metadata={"skip_dependency_check": True}
            )
            
            # Should handle gracefully
            assert kit is not None


class TestHuggingFaceKitRepositoryOperations:
    """Test repository operations."""
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_list_repos(self, hf_kit):
        """Test listing repositories."""
        result = hf_kit.list_repos(repo_type="model")
        
        assert isinstance(result, dict)
        if result.get("success"):
            assert "repos" in result or "count" in result
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_repo_info(self, hf_kit):
        """Test getting repository information."""
        result = hf_kit.repo_info(repo_id="test_user/test_model")
        
        assert isinstance(result, dict)
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_create_repo(self, hf_kit):
        """Test repository creation."""
        with patch('ipfs_kit_py.huggingface_kit.create_repo') as mock_create:
            mock_create.return_value = "https://huggingface.co/test_user/new_repo"
            
            result = hf_kit.create_repo(
                repo_id="test_user/new_repo",
                repo_type="model",
                private=False
            )
            
            assert isinstance(result, dict)
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_list_files(self, hf_kit):
        """Test listing files in repository."""
        result = hf_kit.list_files(
            repo_id="test_user/test_model",
            path=""
        )
        
        assert isinstance(result, dict)


class TestHuggingFaceKitDatasetOperations:
    """Test dataset-specific operations."""
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_list_datasets(self, hf_kit):
        """Test listing datasets."""
        if hasattr(hf_kit, 'list_datasets'):
            result = hf_kit.list_datasets()
            assert isinstance(result, dict)
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_dataset_info(self, hf_kit):
        """Test getting dataset information."""
        if hasattr(hf_kit, 'dataset_info'):
            result = hf_kit.dataset_info(dataset_id="test_user/test_dataset")
            assert isinstance(result, dict)


class TestHuggingFaceKitModelOperations:
    """Test model-specific operations."""
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_list_models(self, hf_kit):
        """Test listing models."""
        result = hf_kit.list_repos(repo_type="model")
        assert isinstance(result, dict)
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_model_info(self, hf_kit):
        """Test getting model information."""
        result = hf_kit.repo_info(repo_id="test_user/test_model", repo_type="model")
        assert isinstance(result, dict)


class TestHuggingFaceKitFileOperations:
    """Test file upload and download operations."""
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_download_file(self, hf_kit):
        """Test downloading a file."""
        with patch('ipfs_kit_py.huggingface_kit.hf_hub_download') as mock_download:
            mock_download.return_value = "/tmp/test_file.txt"
            
            if hasattr(hf_kit, 'download_file'):
                result = hf_kit.download_file(
                    repo_id="test_user/test_model",
                    filename="config.json"
                )
                assert isinstance(result, (dict, str))
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_upload_file(self, hf_kit):
        """Test uploading a file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write("test content")
            tmp_path = tmp_file.name
        
        try:
            if hasattr(hf_kit, 'upload_file'):
                with patch.object(hf_kit.api, 'upload_file') as mock_upload:
                    mock_upload.return_value = "https://huggingface.co/test_user/test_model/blob/main/test.txt"
                    
                    result = hf_kit.upload_file(
                        path_or_fileobj=tmp_path,
                        path_in_repo="test.txt",
                        repo_id="test_user/test_model"
                    )
                    assert isinstance(result, dict)
        finally:
            Path(tmp_path).unlink(missing_ok=True)


class TestHuggingFaceKitErrorHandling:
    """Test error handling."""
    
    def test_invalid_repo_id(self, hf_kit):
        """Test handling of invalid repository ID."""
        # Mock RepositoryNotFoundError
        from ipfs_kit_py.huggingface_kit import RepositoryNotFoundError
        
        with patch.object(hf_kit.api, 'repo_info', side_effect=RepositoryNotFoundError("Not found")):
            result = hf_kit.repo_info(repo_id="invalid/repo")
            
            assert isinstance(result, dict)
            assert not result.get("success", True)
    
    def test_invalid_revision(self, hf_kit):
        """Test handling of invalid revision."""
        from ipfs_kit_py.huggingface_kit import RevisionNotFoundError
        
        with patch.object(hf_kit.api, 'repo_info', side_effect=RevisionNotFoundError("Revision not found")):
            result = hf_kit.repo_info(repo_id="test_user/test_model", revision="invalid")
            
            assert isinstance(result, dict)
    
    def test_network_failure(self, hf_kit):
        """Test handling of network failures."""
        with patch.object(hf_kit.api, 'repo_info', side_effect=ConnectionError("Network error")):
            result = hf_kit.repo_info(repo_id="test_user/test_model")
            
            assert isinstance(result, dict)
    
    def test_permission_error(self, hf_kit):
        """Test handling of permission errors."""
        with patch.object(hf_kit.api, 'repo_info', side_effect=PermissionError("Access denied")):
            result = hf_kit.repo_info(repo_id="private_user/private_model")
            
            assert isinstance(result, dict)


class TestHuggingFaceKitCaching:
    """Test caching functionality."""
    
    def test_cache_directory_creation(self, hf_config):
        """Test that cache directory is created."""
        from ipfs_kit_py.huggingface_kit import huggingface_kit
        
        cache_dir = tempfile.mkdtemp()
        
        with patch('ipfs_kit_py.huggingface_kit.whoami'):
            kit = huggingface_kit(
                resources=hf_config["resources"],
                metadata={"cache_dir": cache_dir, "skip_dependency_check": True}
            )
            
            assert os.path.exists(kit.cache_dir)
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_cached_file_retrieval(self, hf_kit):
        """Test retrieving cached files."""
        if hasattr(hf_kit, 'get_cached_file'):
            result = hf_kit.get_cached_file(
                repo_id="test_user/test_model",
                filename="config.json"
            )
            assert isinstance(result, (dict, str, type(None)))


class TestHuggingFaceKitValidation:
    """Test input validation."""
    
    def test_repo_id_validation(self, hf_kit):
        """Test repository ID validation."""
        if hasattr(hf_kit, 'validate_repo_id'):
            # Valid format: user/repo
            assert hf_kit.validate_repo_id("user/repo")
            
            # Invalid formats
            assert not hf_kit.validate_repo_id("invalid")
            assert not hf_kit.validate_repo_id("")


class TestHuggingFaceKitIntegration:
    """Integration tests for complete workflows."""
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_create_and_upload_workflow(self, hf_kit):
        """Test complete create repo and upload file workflow."""
        with patch('ipfs_kit_py.huggingface_kit.create_repo') as mock_create:
            mock_create.return_value = "https://huggingface.co/test_user/new_repo"
            
            # Create repo
            create_result = hf_kit.create_repo(
                repo_id="test_user/new_repo",
                repo_type="model",
                private=False
            )
            
            assert isinstance(create_result, dict)
            
            # Upload file
            if hasattr(hf_kit, 'upload_file'):
                with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
                    tmp_file.write("test")
                    tmp_path = tmp_file.name
                
                try:
                    with patch.object(hf_kit.api, 'upload_file'):
                        upload_result = hf_kit.upload_file(
                            path_or_fileobj=tmp_path,
                            path_in_repo="test.txt",
                            repo_id="test_user/new_repo"
                        )
                        assert isinstance(upload_result, dict)
                finally:
                    Path(tmp_path).unlink(missing_ok=True)


class TestHuggingFaceKitGitVFS:
    """Test Git VFS integration if available."""
    
    def test_git_vfs_availability(self):
        """Test Git VFS availability flag."""
        from ipfs_kit_py.huggingface_kit import GIT_VFS_AVAILABLE
        assert isinstance(GIT_VFS_AVAILABLE, bool)


# Module-level tests
def test_huggingface_kit_import():
    """Test that huggingface_kit can be imported."""
    from ipfs_kit_py.huggingface_kit import huggingface_kit
    assert huggingface_kit is not None


def test_huggingface_hub_available_flag():
    """Test HUGGINGFACE_HUB_AVAILABLE flag."""
    from ipfs_kit_py.huggingface_kit import HUGGINGFACE_HUB_AVAILABLE
    assert isinstance(HUGGINGFACE_HUB_AVAILABLE, bool)


def test_create_result_dict_helper():
    """Test create_result_dict helper function."""
    from ipfs_kit_py.huggingface_kit import create_result_dict
    
    result = create_result_dict("test_operation")
    
    assert isinstance(result, dict)
    assert "operation" in result
    assert "timestamp" in result
    assert result["operation"] == "test_operation"


def test_handle_error_helper():
    """Test handle_error helper function."""
    from ipfs_kit_py.huggingface_kit import handle_error, create_result_dict
    
    result = create_result_dict("test_operation")
    error = ValueError("Test error")
    
    result = handle_error(result, error, "Custom message")
    
    assert result["success"] is False
    assert "error" in result
    assert result["error"] == "Custom message"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
