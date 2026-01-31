"""
Tests for the auto-healing module.
"""

import pytest
import json
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile

from ipfs_kit_py.auto_heal.config import AutoHealConfig
from ipfs_kit_py.auto_heal.error_capture import ErrorCapture, CapturedError
from ipfs_kit_py.auto_heal.github_issue_creator import GitHubIssueCreator


class TestAutoHealConfig:
    """Test auto-healing configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = AutoHealConfig()
        
        assert config.enabled == False
        assert config.max_log_lines == 100
        assert config.include_stack_trace == True
        assert config.auto_create_issues == True
        assert 'auto-heal' in config.issue_labels
        assert 'cli-error' in config.issue_labels
    
    def test_config_from_environment(self):
        """Test configuration from environment variables."""
        with patch.dict(os.environ, {
            'IPFS_KIT_AUTO_HEAL': 'true',
            'GITHUB_TOKEN': 'test_token',
            'GITHUB_REPOSITORY': 'owner/repo'
        }):
            config = AutoHealConfig()
            
            assert config.enabled == True
            assert config.github_token == 'test_token'
            assert config.github_repo == 'owner/repo'
    
    def test_is_configured(self):
        """Test configuration validation."""
        # Not configured
        config = AutoHealConfig()
        assert config.is_configured() == False
        
        # Partially configured - has token but no repo
        config.enabled = True
        config.github_token = 'token'
        config.github_repo = None  # Explicitly set to None to override environment
        assert config.is_configured() == False
        
        # Fully configured
        config.github_repo = 'owner/repo'
        assert config.is_configured() == True
    
    def test_save_and_load_config(self):
        """Test saving and loading configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / 'config.json'
            
            # Create and save config
            config1 = AutoHealConfig(
                enabled=True,
                github_repo='test/repo',
                max_log_lines=50
            )
            config1.save_to_file(config_path)
            
            # Load config
            config2 = AutoHealConfig.from_file(config_path)
            
            assert config2.enabled == True
            assert config2.github_repo == 'test/repo'
            assert config2.max_log_lines == 50


class TestErrorCapture:
    """Test error capture functionality."""
    
    def test_capture_error(self):
        """Test capturing an error with context."""
        error_capture = ErrorCapture(max_log_lines=10)
        
        try:
            # Trigger an error
            raise ValueError("Test error message")
        except Exception as e:
            captured = error_capture.capture_error(
                e,
                command="ipfs-kit test",
                arguments={'arg1': 'value1'}
            )
            
            assert captured.error_type == 'ValueError'
            assert captured.error_message == 'Test error message'
            assert 'Test error message' in captured.stack_trace
            assert captured.command == 'ipfs-kit test'
            assert captured.arguments == {'arg1': 'value1'}
            assert captured.working_directory == os.getcwd()
    
    def test_format_for_issue(self):
        """Test formatting error for GitHub issue."""
        error_capture = ErrorCapture(max_log_lines=10)
        
        try:
            raise RuntimeError("Test runtime error")
        except Exception as e:
            captured = error_capture.capture_error(
                e,
                command="ipfs-kit mcp start",
                arguments={}
            )
            
            issue_body = captured.format_for_issue(max_log_lines=50)
            
            # Check that issue body contains expected sections
            assert '## CLI Error Auto-Report' in issue_body
            assert 'RuntimeError' in issue_body
            assert 'Test runtime error' in issue_body
            assert '### Stack Trace' in issue_body
            assert '### Command Executed' in issue_body
            assert 'ipfs-kit mcp start' in issue_body
    
    def test_log_buffer(self):
        """Test log buffer capture."""
        import logging
        
        error_capture = ErrorCapture(max_log_lines=5)
        logger = logging.getLogger('test')
        
        # Generate some log messages
        for i in range(10):
            logger.info(f"Log message {i}")
        
        # Buffer should only contain last 5 messages
        assert len(error_capture.log_buffer) <= 5


class TestGitHubIssueCreator:
    """Test GitHub issue creation."""
    
    def test_format_issue_title(self):
        """Test issue title formatting."""
        config = AutoHealConfig(
            enabled=True,
            github_token='token',
            github_repo='owner/repo'
        )
        creator = GitHubIssueCreator(config)
        
        # Create a mock captured error
        error = CapturedError(
            error_type='ValueError',
            error_message='This is a test error message',
            stack_trace='',
            timestamp='2024-01-01T00:00:00',
            command='ipfs-kit test',
            arguments={},
            environment={},
            log_context=[],
            working_directory='/tmp',
            python_version='3.12.0'
        )
        
        title = creator._format_issue_title(error)
        
        assert '[Auto-Heal]' in title
        assert 'ValueError' in title
        assert 'This is a test error message' in title
    
    def test_format_long_issue_title(self):
        """Test issue title truncation for long messages."""
        config = AutoHealConfig(
            enabled=True,
            github_token='token',
            github_repo='owner/repo'
        )
        creator = GitHubIssueCreator(config)
        
        long_message = 'A' * 200  # Very long message
        error = CapturedError(
            error_type='ValueError',
            error_message=long_message,
            stack_trace='',
            timestamp='2024-01-01T00:00:00',
            command='ipfs-kit test',
            arguments={},
            environment={},
            log_context=[],
            working_directory='/tmp',
            python_version='3.12.0'
        )
        
        title = creator._format_issue_title(error)
        
        # Title should be truncated
        assert len(title) < len(long_message) + 50  # Account for [Auto-Heal] and error type
        assert '...' in title
    
    @patch('ipfs_kit_py.auto_heal.github_issue_creator.requests.post')
    def test_create_github_issue_success(self, mock_post):
        """Test successful GitHub issue creation."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            'html_url': 'https://github.com/owner/repo/issues/123'
        }
        mock_post.return_value = mock_response
        
        config = AutoHealConfig(
            enabled=True,
            github_token='test_token',
            github_repo='owner/repo'
        )
        creator = GitHubIssueCreator(config)
        
        issue_url = creator._create_github_issue(
            title='Test Issue',
            body='Test body',
            labels=['auto-heal', 'cli-error']
        )
        
        assert issue_url == 'https://github.com/owner/repo/issues/123'
        
        # Verify API was called correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert 'https://api.github.com/repos/owner/repo/issues' in call_args[0]
    
    @patch('ipfs_kit_py.auto_heal.github_issue_creator.requests.post')
    def test_create_github_issue_failure(self, mock_post):
        """Test failed GitHub issue creation."""
        # Mock failed API response
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = 'Unauthorized'
        mock_post.return_value = mock_response
        
        config = AutoHealConfig(
            enabled=True,
            github_token='invalid_token',
            github_repo='owner/repo'
        )
        creator = GitHubIssueCreator(config)
        
        issue_url = creator._create_github_issue(
            title='Test Issue',
            body='Test body',
            labels=['auto-heal']
        )
        
        assert issue_url is None


class TestErrorCaptureDecorator:
    """Test error capture decorator functionality."""
    
    @patch('ipfs_kit_py.auto_heal.github_issue_creator.GitHubIssueCreator')
    @patch('ipfs_kit_py.auto_heal.config.AutoHealConfig')
    def test_capture_cli_errors_decorator_not_configured(self, mock_config_class, mock_creator_class):
        """Test decorator when auto-healing is not configured."""
        from ipfs_kit_py.auto_heal.error_capture import capture_cli_errors
        
        # Mock config as not configured
        mock_config = Mock()
        mock_config.is_configured.return_value = False
        mock_config.max_log_lines = 100
        mock_config_class.from_file.return_value = mock_config
        
        @capture_cli_errors
        def failing_function():
            raise ValueError("Test error")
        
        # Should raise the original exception
        with pytest.raises(ValueError, match="Test error"):
            failing_function()
        
        # Should not create issue
        mock_creator_class.assert_not_called()
    
    @patch('ipfs_kit_py.auto_heal.github_issue_creator.GitHubIssueCreator')
    @patch('ipfs_kit_py.auto_heal.config.AutoHealConfig')
    def test_capture_cli_errors_decorator_configured(self, mock_config_class, mock_creator_class):
        """Test decorator when auto-healing is configured."""
        from ipfs_kit_py.auto_heal.error_capture import capture_cli_errors
        
        # Mock config as configured
        mock_config = Mock()
        mock_config.is_configured.return_value = True
        mock_config.max_log_lines = 100
        mock_config_class.from_file.return_value = mock_config
        
        # Mock issue creator
        mock_creator = Mock()
        mock_creator.create_issue_from_error.return_value = 'https://github.com/owner/repo/issues/1'
        mock_creator_class.return_value = mock_creator
        
        @capture_cli_errors
        def failing_function():
            raise ValueError("Test error")
        
        # Should raise the original exception
        with pytest.raises(ValueError, match="Test error"):
            failing_function()
        
        # Should create issue
        mock_creator.create_issue_from_error.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
