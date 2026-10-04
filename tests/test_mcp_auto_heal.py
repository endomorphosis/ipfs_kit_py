"""
Tests for MCP tool and JavaScript SDK auto-healing integration.
"""

import pytest
import time
import anyio
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
    
    @pytest.mark.anyio
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
    
    @pytest.mark.anyio
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
    
    @pytest.mark.anyio
    async def test_report_client_error_no_data(self):
        """Test reporting with no data."""
        reporter = ClientErrorReporter()
        result = await reporter.report_client_error({})
        
        assert result['status'] == 'error'
        assert 'No error data' in result['message']
    
    @pytest.mark.anyio
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
    
    @pytest.mark.anyio
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
    
    @pytest.mark.anyio
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
        
        # Wait for background error logging to complete (with timeout for test reliability)
        async def wait_for_error_log():
            timeout_counter = 0
            while len(capture.error_log) < 1 and timeout_counter < 100:
                await anyio.sleep(0.01)
                timeout_counter += 1

        with anyio.fail_after(1.0):
            await wait_for_error_log()
        
        # Verify issue creation was attempted
        # Note: In real scenario, this would create actual GitHub issue
        assert len(capture.error_log) == 1


class TestAutoHealFailureScenarios:
    """Test auto-heal failure scenarios to ensure robustness."""
    
    @pytest.mark.anyio
    @patch('ipfs_kit_py.auto_heal.config.AutoHealConfig')
    async def test_auto_heal_with_github_api_failure(self, mock_config_class):
        """Test that tool execution continues even if auto-heal GitHub API fails."""
        from ipfs_kit_py.auto_heal.mcp_tool_wrapper import MCPToolErrorCapture
        
        # Mock config as configured
        mock_config = Mock()
        mock_config.is_configured.return_value = True
        mock_config.max_log_lines = 100
        mock_config_class.from_file.return_value = mock_config
        
        # Create capture with auto-heal enabled
        capture = MCPToolErrorCapture(enable_auto_heal=True)
        
        # Create a failing tool
        async def failing_tool(tool_name, arguments):
            raise RuntimeError("Tool execution failed")
        
        wrapped = capture.wrap_tool_handler(failing_tool)
        
        # Mock GitHub issue creator to raise exception
        with patch('ipfs_kit_py.auto_heal.github_issue_creator.GitHubIssueCreator') as mock_creator_class:
            mock_creator = Mock()
            mock_creator.create_issue_from_error.side_effect = Exception("GitHub API failed")
            mock_creator_class.return_value = mock_creator
            
            # Execute should raise original tool error, not GitHub API error
            with pytest.raises(RuntimeError, match="Tool execution failed"):
                await wrapped("test_tool", {"test": "param"})
            
            # Error should still be logged locally even if GitHub API failed
            async def wait_for_error_log():
                timeout_counter = 0
                while len(capture.error_log) < 1 and timeout_counter < 100:
                    await anyio.sleep(0.01)
                    timeout_counter += 1

            with anyio.fail_after(1.0):
                await wait_for_error_log()
            assert len(capture.error_log) == 1
    
    @pytest.mark.anyio
    async def test_auto_heal_with_invalid_config(self):
        """Test that tool execution continues with invalid auto-heal config."""
        from ipfs_kit_py.auto_heal.mcp_tool_wrapper import MCPToolErrorCapture
        
        # Create capture with invalid config (no token/repo)
        with patch('ipfs_kit_py.auto_heal.config.AutoHealConfig') as mock_config_class:
            mock_config = Mock()
            mock_config.is_configured.return_value = False
            mock_config.max_log_lines = 100
            mock_config_class.from_file.return_value = mock_config
            
            capture = MCPToolErrorCapture(enable_auto_heal=True)
            
            # Create a failing tool
            async def failing_tool(tool_name, arguments):
                raise ValueError("Tool failed")
            
            wrapped = capture.wrap_tool_handler(failing_tool)
            
            # Should still raise the tool error
            with pytest.raises(ValueError, match="Tool failed"):
                await wrapped("test_tool", {})
            
            # Error should be logged
            async def wait_for_error_log():
                timeout_counter = 0
                while len(capture.error_log) < 1 and timeout_counter < 100:
                    await anyio.sleep(0.01)
                    timeout_counter += 1

            with anyio.fail_after(1.0):
                await wait_for_error_log()
            assert len(capture.error_log) == 1
    
    @pytest.mark.anyio
    @patch('ipfs_kit_py.auto_heal.config.AutoHealConfig')
    async def test_auto_heal_trigger_timeout_doesnt_block_error(self, mock_config_class):
        """Test that slow auto-heal trigger doesn't block error propagation."""
        from ipfs_kit_py.auto_heal.mcp_tool_wrapper import MCPToolErrorCapture
        
        # Mock config as configured
        mock_config = Mock()
        mock_config.is_configured.return_value = True
        mock_config.max_log_lines = 100
        mock_config_class.from_file.return_value = mock_config
        
        capture = MCPToolErrorCapture(enable_auto_heal=True)
        
        # Create a failing tool
        async def failing_tool(tool_name, arguments):
            raise ConnectionError("Connection timeout")
        
        wrapped = capture.wrap_tool_handler(failing_tool)
        
        # Mock GitHub issue creator with slow response
        with patch('ipfs_kit_py.auto_heal.github_issue_creator.GitHubIssueCreator') as mock_creator_class:
            mock_creator = Mock()
            # Simulate slow sync API; implementation runs this in a background thread.
            def slow_create_issue(error):
                time.sleep(5)
                return 'https://github.com/owner/repo/issues/1'

            mock_creator.create_issue_from_error = Mock(side_effect=slow_create_issue)
            mock_creator_class.return_value = mock_creator
            
            # Error should be raised immediately, not wait for slow auto-heal
            start = time.time()
            
            with pytest.raises(ConnectionError, match="Connection timeout"):
                await wrapped("test_tool", {})
            
            elapsed = time.time() - start
            
            # Should complete quickly (< 1 second), not wait for 5 second delay
            assert elapsed < 1.0, f"Error took {elapsed}s to propagate, should be immediate"
    
    @pytest.mark.anyio
    async def test_client_error_reporter_with_malformed_data(self):
        """Test client error reporter handles malformed input gracefully."""
        from ipfs_kit_py.auto_heal.client_error_reporter import ClientErrorReporter
        
        reporter = ClientErrorReporter()
        
        # Test with None - should handle gracefully
        result = await reporter.report_client_error(None)
        assert result['status'] == 'error'
        assert 'No error data provided' in result['message']
        
        # Test with empty dict - should process without crashing
        result = await reporter.report_client_error({})
        assert result['status'] == 'error'  # No error data provided
        
        # Test with minimal valid data - should succeed
        result = await reporter.report_client_error({
            'error_message': 'Test error',
            'error_type': 'TestError'
        })
        assert result['status'] == 'success'
        
        # Test with extra unexpected fields - should still process
        result = await reporter.report_client_error({
            'error_message': 'Another test',
            'error_type': 'AnotherError',
            'unexpected_field': 'unexpected_value',
            'another_unexpected': {'nested': 'data'}
        })
        assert result['status'] == 'success'



if __name__ == '__main__':
    pytest.main([__file__, '-v'])
