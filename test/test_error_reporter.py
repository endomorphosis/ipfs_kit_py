"""
Tests for the error reporting system.
"""

import os
import json
import sys
import pytest
import tempfile
from unittest.mock import Mock, patch, MagicMock

# Add the parent directory to the path to import modules directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import directly from the module files
from ipfs_kit_py.error_reporter import (
    GitHubIssueReporter,
)


class TestGitHubIssueReporter:
    """Test cases for GitHubIssueReporter."""
    
    def test_initialization(self):
        """Test reporter initialization."""
        reporter = GitHubIssueReporter(
            github_token="test_token",
            repo_owner="test_owner",
            repo_name="test_repo",
            enabled=True,
        )
        
        assert reporter.github_token == "test_token"
        assert reporter.repo_owner == "test_owner"
        assert reporter.repo_name == "test_repo"
        assert reporter.enabled is True
    
    def test_initialization_from_env(self):
        """Test reporter initialization from environment variables."""
        with patch.dict(os.environ, {
            "GITHUB_TOKEN": "env_token",
            "GITHUB_REPO_OWNER": "env_owner",
            "GITHUB_REPO_NAME": "env_repo",
        }):
            reporter = GitHubIssueReporter()
            
            assert reporter.github_token == "env_token"
            assert reporter.repo_owner == "env_owner"
            assert reporter.repo_name == "env_repo"
    
    def test_disabled_when_no_token(self):
        """Test that reporter is disabled when no token is provided."""
        reporter = GitHubIssueReporter(
            github_token=None,
            repo_owner="test_owner",
            repo_name="test_repo",
        )
        
        assert reporter.enabled is False
    
    def test_error_hash_generation(self):
        """Test error hash generation."""
        reporter = GitHubIssueReporter(github_token="test")
        
        error_info1 = {
            "error_type": "ValueError",
            "error_message": "Invalid input",
            "traceback": "line 1\nline 2",
        }
        
        error_info2 = {
            "error_type": "ValueError",
            "error_message": "Invalid input",
            "traceback": "line 1\nline 2",
        }
        
        # Same error should produce same hash
        hash1 = reporter._get_error_hash(error_info1)
        hash2 = reporter._get_error_hash(error_info2)
        assert hash1 == hash2
        
        # Different error should produce different hash
        error_info3 = {
            "error_type": "RuntimeError",
            "error_message": "Different error",
            "traceback": "different traceback",
        }
        hash3 = reporter._get_error_hash(error_info3)
        assert hash1 != hash3
    
    def test_error_cache_loading_and_saving(self):
        """Test error cache loading and saving."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            cache_file = f.name
        
        try:
            # Create reporter with custom cache file
            reporter = GitHubIssueReporter(
                github_token="test",
                error_cache_file=cache_file,
            )
            
            # Add some data to cache
            reporter.error_cache["errors"]["test_hash"] = {
                "count": 1,
                "last_reported": "2025-11-06T00:00:00",
            }
            
            # Save cache
            reporter._save_error_cache()
            
            # Create new reporter and verify cache is loaded
            reporter2 = GitHubIssueReporter(
                github_token="test",
                error_cache_file=cache_file,
            )
            
            assert "test_hash" in reporter2.error_cache["errors"]
            assert reporter2.error_cache["errors"]["test_hash"]["count"] == 1
            
        finally:
            # Clean up
            if os.path.exists(cache_file):
                os.unlink(cache_file)
    
    def test_rate_limiting(self):
        """Test rate limiting functionality."""
        reporter = GitHubIssueReporter(
            github_token="test",
            max_reports_per_hour=2,
        )
        
        # Should be able to report initially
        assert reporter._check_rate_limit() is True
        
        # Increment counter twice
        reporter._increment_rate_limit()
        reporter._increment_rate_limit()
        
        # Should now be rate limited
        assert reporter._check_rate_limit() is False
    
    def test_should_report_error_deduplication(self):
        """Test error deduplication."""
        reporter = GitHubIssueReporter(github_token="test")
        
        # First occurrence should be reported
        assert reporter._should_report_error("test_hash") is True
        
        # Mark as reported
        reporter._mark_error_reported("test_hash", "http://github.com/issue/1")
        
        # Second occurrence within 24 hours should not be reported
        assert reporter._should_report_error("test_hash") is False
    
    def test_format_error_report(self):
        """Test error report formatting."""
        reporter = GitHubIssueReporter(github_token="test")
        
        error_info = {
            "error_type": "ValueError",
            "error_message": "Invalid input provided",
            "timestamp": "2025-11-06T08:00:00",
            "traceback": "Traceback:\n  line 1\n  line 2",
            "environment": {
                "python_version": "3.12.0",
                "platform": "linux",
                "component": "Test Component",
            },
            "details": {
                "user_id": "123",
                "action": "test",
            },
        }
        
        title, body = reporter._format_error_report(error_info, "Test Context")
        
        # Check title
        assert "ValueError" in title
        assert "Invalid input provided" in title
        
        # Check body
        assert "ValueError" in body
        assert "Invalid input provided" in body
        assert "2025-11-06T08:00:00" in body
        assert "Test Context" in body
        assert "3.12.0" in body
        assert "linux" in body
        assert "Traceback" in body
        assert "automatically generated" in body.lower()
    
    @patch('ipfs_kit_py.error_reporter.requests.post')
    def test_create_github_issue_success(self, mock_post):
        """Test successful GitHub issue creation."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "html_url": "https://github.com/test/repo/issues/1"
        }
        mock_post.return_value = mock_response
        
        reporter = GitHubIssueReporter(
            github_token="test_token",
            repo_owner="test_owner",
            repo_name="test_repo",
        )
        
        issue_url = reporter._create_github_issue(
            title="Test Issue",
            body="Test body",
            labels=["bug"],
        )
        
        assert issue_url == "https://github.com/test/repo/issues/1"
        assert mock_post.called
    
    @patch('ipfs_kit_py.error_reporter.requests.post')
    def test_create_github_issue_failure(self, mock_post):
        """Test failed GitHub issue creation."""
        # Mock failed API response
        mock_post.side_effect = Exception("API Error")
        
        reporter = GitHubIssueReporter(
            github_token="test_token",
            repo_owner="test_owner",
            repo_name="test_repo",
        )
        
        issue_url = reporter._create_github_issue(
            title="Test Issue",
            body="Test body",
        )
        
        assert issue_url is None
    
    @patch('ipfs_kit_py.error_reporter.requests.post')
    def test_report_error(self, mock_post):
        """Test reporting an error."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "html_url": "https://github.com/test/repo/issues/1"
        }
        mock_post.return_value = mock_response
        
        reporter = GitHubIssueReporter(
            github_token="test_token",
            repo_owner="test_owner",
            repo_name="test_repo",
        )
        
        # Create an exception
        try:
            raise ValueError("Test error")
        except Exception as e:
            issue_url = reporter.report_error(
                error=e,
                context="Test Context",
                additional_info={"key": "value"}
            )
        
        assert issue_url == "https://github.com/test/repo/issues/1"
        assert mock_post.called
        
        # Check that the error was cached
        error_hash = list(reporter.error_cache["errors"].keys())[0]
        assert reporter.error_cache["errors"][error_hash]["issue_url"] == issue_url
    
    @patch('ipfs_kit_py.error_reporter.requests.post')
    def test_report_error_dict(self, mock_post):
        """Test reporting an error from dictionary."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "html_url": "https://github.com/test/repo/issues/2"
        }
        mock_post.return_value = mock_response
        
        reporter = GitHubIssueReporter(
            github_token="test_token",
            repo_owner="test_owner",
            repo_name="test_repo",
        )
        
        error_info = {
            "error_type": "JavaScriptError",
            "error_message": "Undefined variable",
            "traceback": "at line 10",
        }
        
        issue_url = reporter.report_error_dict(
            error_info=error_info,
            context="JavaScript Dashboard"
        )
        
        assert issue_url == "https://github.com/test/repo/issues/2"
        assert mock_post.called
    
    def test_disabled_reporter_does_not_create_issues(self):
        """Test that disabled reporter does not create issues."""
        reporter = GitHubIssueReporter(
            github_token=None,  # No token = disabled
            repo_owner="test_owner",
            repo_name="test_repo",
        )
        
        try:
            raise ValueError("Test error")
        except Exception as e:
            issue_url = reporter.report_error(error=e)
        
        assert issue_url is None


class TestGlobalFunctions:
    """Test cases for global error reporter functions."""
    
    def test_placeholder(self):
        """Placeholder test to avoid empty test class."""
        assert True
