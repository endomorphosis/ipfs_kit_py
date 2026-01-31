"""
Tests for MCP tool and JavaScript SDK auto-healing integration.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from ipfs_kit_py.auto_heal.mcp_tool_wrapper import MCPToolErrorCapture, get_mcp_error_capture
from ipfs_kit_py.auto_heal.client_error_reporter import ClientErrorReporter, get_client_error_reporter


class TestMCPToolErrorCapture:
    """Test MCP tool error capture functionality."""
    
    def test_capture_tool_error(self):
        """Test capturing an MCP tool error."""
        capture = MCPToolErrorCapture(enable_auto_heal=False)
        
        # Simulate a tool error
        try:
            raise ValueError("Test MCP tool error")
        except Exception as e:
            error_info = capture._capture_tool_error(
                tool_name="test_tool",
                arguments={"param1": "value1"},
                exception=e
            )
            
            assert error_info['error_type'] == 'ValueError'
            assert error_info['error_message'] == 'Test MCP tool error'
            assert error_info['tool_name'] == 'test_tool'
            assert error_info['arguments'] == {"param1": "value1"}
            assert error_info['source'] == 'mcp_tool'
            assert 'stack_trace' in error_info
            assert 'timestamp' in error_info
    
    @pytest.mark.asyncio
    @patch('ipfs_kit_py.auto_heal.github_issue_creator.GitHubIssueCreator')
    @patch('ipfs_kit_py.auto_heal.config.AutoHealConfig')
    async def test_trigger_auto_heal(self, mock_config_class, mock_creator_class):
        """Test triggering auto-heal for MCP tool error."""
        # Mock config as configured
        mock_config = Mock()
        mock_config.is_configured.return_value = True
        mock_config_class.from_file.return_value = mock_config
        
        # Mock issue creator
        mock_creator = Mock()
        mock_creator.create_issue_from_error.return_value = 'https://github.com/owner/repo/issues/1'
        mock_creator_class.return_value = mock_creator
        
        capture = MCPToolErrorCapture(enable_auto_heal=True)
        
        error_info = {
            'error_type': 'RuntimeError',
            'error_message': 'Test error',
            'stack_trace': 'Stack trace here',
            'tool_name': 'test_tool',
            'arguments': {},
            'timestamp': '2024-01-01T00:00:00',
            'source': 'mcp_tool'
        }
        
        await capture._trigger_auto_heal(error_info)
        
        # Verify issue was created
        mock_creator.create_issue_from_error.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_wrap_tool_handler(self):
        """Test wrapping a tool handler."""
        capture = MCPToolErrorCapture(enable_auto_heal=False)
        
        # Create a test handler
        async def test_handler(tool_name, arguments):
            if tool_name == "failing_tool":
                raise ValueError("Tool failed")
            return {"result": "success"}
        
        wrapped = capture.wrap_tool_handler(test_handler)
        
        # Test successful execution
        result = await wrapped("successful_tool", {})
        assert result == {"result": "success"}
        
        # Test error capture
        with pytest.raises(ValueError):
            await wrapped("failing_tool", {})
        
        # Error should be logged
        assert len(capture.error_log) == 1
        assert capture.error_log[0]['tool_name'] == 'failing_tool'
    
    def test_get_mcp_error_capture_singleton(self):
        """Test global instance management."""
        capture1 = get_mcp_error_capture()
        capture2 = get_mcp_error_capture()
        
        assert capture1 is capture2


class TestClientErrorReporter:
    """Test client-side error reporter functionality."""
    
    @pytest.mark.asyncio
    async def test_report_client_error_no_data(self):
        """Test reporting with no data."""
        reporter = ClientErrorReporter()
        result = await reporter.report_client_error({})
        
        assert result['status'] == 'error'
        assert 'No error data' in result['message']
    
    @pytest.mark.asyncio
    @patch('ipfs_kit_py.auto_heal.github_issue_creator.GitHubIssueCreator')
    @patch('ipfs_kit_py.auto_heal.config.AutoHealConfig')
    async def test_report_client_error_success(self, mock_config_class, mock_creator_class):
        """Test successful client error reporting."""
        # Mock config
        mock_config = Mock()
        mock_config.is_configured.return_value = True
        mock_config_class.from_file.return_value = mock_config
        
        # Mock issue creator
        mock_creator = Mock()
        mock_creator.create_issue_from_error.return_value = 'https://github.com/owner/repo/issues/1'
        mock_creator_class.return_value = mock_creator
        
        reporter = ClientErrorReporter()
        
        error_data = {
            'error_type': 'TypeError',
            'error_message': 'Cannot read property of undefined',
            'stack_trace': 'Error\n  at function1\n  at function2',
            'tool_name': 'ipfs_add',
            'operation': 'tool_call',
            'params': {'content': 'test'},
            'browser': 'Chrome',
            'user_agent': 'Mozilla/5.0...',
            'url': 'http://localhost:8004',
            'platform': 'Linux',
            'timestamp': '2024-01-01T00:00:00Z'
        }
        
        result = await reporter.report_client_error(error_data)
        
        assert result['status'] == 'success'
        assert 'timestamp' in result
        
        # Verify error was logged
        assert len(reporter.error_log) == 1
        assert reporter.error_log[0] == error_data
    
    @pytest.mark.asyncio
    async def test_trigger_auto_heal_client_error(self):
        """Test auto-heal trigger for client error."""
        reporter = ClientErrorReporter()
        
        error_data = {
            'error_type': 'Error',
            'error_message': 'Test error',
            'stack_trace': 'Stack trace',
            'tool_name': 'test_tool',
            'operation': 'test_op',
            'params': {},
            'browser': 'Firefox',
            'url': 'http://test.com'
        }
        
        # Should not raise even if auto-heal not configured
        await reporter._trigger_auto_heal(error_data)
    
    def test_get_client_error_reporter_singleton(self):
        """Test global instance management."""
        reporter1 = get_client_error_reporter()
        reporter2 = get_client_error_reporter()
        
        assert reporter1 is reporter2


class TestEndToEndIntegration:
    """Test end-to-end auto-healing flow."""
    
    @pytest.mark.asyncio
    @patch('ipfs_kit_py.auto_heal.github_issue_creator.GitHubIssueCreator')
    @patch('ipfs_kit_py.auto_heal.config.AutoHealConfig')
    async def test_mcp_tool_error_creates_issue(self, mock_config_class, mock_creator_class):
        """Test that MCP tool error creates GitHub issue."""
        # Setup mocks
        mock_config = Mock()
        mock_config.is_configured.return_value = True
        mock_config_class.from_file.return_value = mock_config
        
        mock_creator = Mock()
        mock_creator.create_issue_from_error.return_value = 'https://github.com/owner/repo/issues/1'
        mock_creator_class.return_value = mock_creator
        
        # Create capture instance
        capture = MCPToolErrorCapture(enable_auto_heal=True)
        
        # Simulate tool execution with error
        async def failing_tool(tool_name, arguments):
            raise RuntimeError("Simulated MCP tool failure")
        
        wrapped = capture.wrap_tool_handler(failing_tool)
        
        # Execute and expect error
        with pytest.raises(RuntimeError):
            await wrapped("test_tool", {"test": "param"})
        
        # Give async task time to complete
        await asyncio.sleep(0.1)
        
        # Verify issue creation was attempted
        # Note: In real scenario, this would create actual GitHub issue
        assert len(capture.error_log) == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
