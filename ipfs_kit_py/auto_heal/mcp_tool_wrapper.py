"""
MCP Tool Error Wrapper for Auto-Healing

This module wraps MCP tool execution to capture errors and trigger auto-healing.
"""

import logging
import traceback
from typing import Dict, Any, Optional, Callable
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)


class MCPToolErrorCapture:
    """Captures errors from MCP tool execution for auto-healing."""
    
    def __init__(self, enable_auto_heal: bool = True):
        """Initialize MCP tool error capture."""
        self.enable_auto_heal = enable_auto_heal
        self.error_log = []
        
    def wrap_tool_handler(self, handler: Callable) -> Callable:
        """
        Wrap a tool handler to capture errors.
        
        Args:
            handler: The original tool handler function
            
        Returns:
            Wrapped handler with error capture
        """
        async def wrapped_handler(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
            try:
                # Execute the original handler
                result = await handler(tool_name, arguments)
                return result
                
            except Exception as e:
                # Capture the error
                error_info = self._capture_tool_error(tool_name, arguments, e)
                
                # Log locally
                logger.error(f"MCP tool error: {tool_name}", exc_info=True)
                self.error_log.append(error_info)
                
                # Trigger auto-healing if enabled
                if self.enable_auto_heal:
                    # Fire-and-forget: auto-heal should never block tool error propagation.
                    try:
                        asyncio.create_task(self._trigger_auto_heal(error_info))
                    except RuntimeError:
                        # If the event loop is unavailable for some reason, fall back to best-effort.
                        # This should be rare since we're inside an async handler.
                        await self._trigger_auto_heal(error_info)
                
                # Re-raise with enhanced context
                raise
        
        return wrapped_handler
    
    def _capture_tool_error(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        exception: Exception
    ) -> Dict[str, Any]:
        """
        Capture detailed error information from MCP tool execution.
        
        Args:
            tool_name: Name of the MCP tool that failed
            arguments: Arguments passed to the tool
            exception: The exception that was raised
            
        Returns:
            Dictionary with error details
        """
        return {
            'error_type': type(exception).__name__,
            'error_message': str(exception),
            'stack_trace': traceback.format_exc(),
            'tool_name': tool_name,
            'arguments': arguments,
            'timestamp': datetime.utcnow().isoformat(),
            'source': 'mcp_tool'
        }
    
    async def _trigger_auto_heal(self, error_info: Dict[str, Any]) -> None:
        """
        Trigger auto-healing process for MCP tool error.
        
        Args:
            error_info: Error information dictionary
        """
        try:
            # Import auto-heal modules
            from ipfs_kit_py.auto_heal.config import AutoHealConfig
            from ipfs_kit_py.auto_heal.github_issue_creator import GitHubIssueCreator
            from ipfs_kit_py.auto_heal.error_capture import CapturedError
            
            # Load configuration
            config = AutoHealConfig.from_file()
            
            if not config.is_configured():
                logger.debug("Auto-healing not configured, skipping GitHub issue creation")
                return
            
            # Create captured error object
            captured_error = CapturedError(
                error_type=error_info['error_type'],
                error_message=error_info['error_message'],
                stack_trace=error_info['stack_trace'],
                timestamp=error_info['timestamp'],
                command=f"MCP Tool: {error_info['tool_name']}",
                arguments=error_info['arguments'],
                environment={},  # MCP tools run server-side
                log_context=[],  # Could be enhanced with server logs
                working_directory='MCP Server',
                python_version='Server-side execution'
            )
            
            # Create GitHub issue
            issue_creator = GitHubIssueCreator(config)
            # Run sync API call off the event loop with a conservative timeout.
            try:
                issue_url = await asyncio.wait_for(
                    asyncio.to_thread(issue_creator.create_issue_from_error, captured_error),
                    timeout=2.0,
                )
            except asyncio.TimeoutError:
                logger.warning("Auto-heal issue creation timed out")
                return
            
            if issue_url:
                logger.info(f"MCP tool error reported: {issue_url}")
            
        except Exception as heal_error:
            logger.error(f"Failed to trigger auto-heal for MCP tool error: {heal_error}")


# Global instance for MCP tool error capture
_mcp_error_capture = None


def get_mcp_error_capture(enable_auto_heal: bool = True) -> MCPToolErrorCapture:
    """
    Get or create the global MCP error capture instance.
    
    Args:
        enable_auto_heal: Whether to enable auto-healing
        
    Returns:
        MCPToolErrorCapture instance
    """
    global _mcp_error_capture
    
    if _mcp_error_capture is None:
        _mcp_error_capture = MCPToolErrorCapture(enable_auto_heal=enable_auto_heal)
    
    return _mcp_error_capture


def wrap_mcp_tool_handler(handler: Callable, enable_auto_heal: bool = True) -> Callable:
    """
    Convenience function to wrap an MCP tool handler with error capture.
    
    Args:
        handler: The tool handler to wrap
        enable_auto_heal: Whether to enable auto-healing
        
    Returns:
        Wrapped handler
    """
    capture = get_mcp_error_capture(enable_auto_heal)
    return capture.wrap_tool_handler(handler)
