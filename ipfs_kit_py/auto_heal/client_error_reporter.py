"""
Client-Side Error Reporting Endpoint

This module provides an endpoint for the JavaScript SDK to report errors
to the auto-healing system.
"""

import logging
from typing import Dict, Any
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class ClientErrorReporter:
    """Handles client-side error reports from the JavaScript SDK."""
    
    def __init__(self):
        """Initialize the client error reporter."""
        self.error_log = []
    
    async def report_client_error(self, error_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a client-side error report.
        
        Args:
            error_data: Error information from the JavaScript SDK
            
        Returns:
            Response indicating success or failure
        """
        try:
            # Validate error data
            if not error_data:
                return {"status": "error", "message": "No error data provided"}
            
            # Log the error
            logger.error(f"Client-side error reported: {error_data.get('error_type', 'Unknown')}")
            self.error_log.append(error_data)
            
            # Trigger auto-healing if enabled
            await self._trigger_auto_heal(error_data)
            
            return {
                "status": "success",
                "message": "Error reported successfully",
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to process client error report: {e}")
            return {
                "status": "error",
                "message": f"Failed to process error report: {str(e)}"
            }
    
    async def _trigger_auto_heal(self, error_data: Dict[str, Any]) -> None:
        """
        Trigger auto-healing for client-side error.
        
        Args:
            error_data: Error information from client
        """
        try:
            from ipfs_kit_py.auto_heal.config import AutoHealConfig
            from ipfs_kit_py.auto_heal.github_issue_creator import GitHubIssueCreator
            from ipfs_kit_py.auto_heal.error_capture import CapturedError
            
            # Load configuration
            config = AutoHealConfig.from_file()
            
            if not config.is_configured():
                logger.debug("Auto-healing not configured, skipping GitHub issue creation")
                return
            
            # Extract error information
            error_type = error_data.get('error_type', 'ClientError')
            error_message = error_data.get('error_message', 'Unknown client error')
            stack_trace = error_data.get('stack_trace', 'No stack trace available')
            
            # Create command context
            tool_name = error_data.get('tool_name', 'Unknown')
            operation = error_data.get('operation', 'Unknown')
            command = f"MCP SDK: {tool_name} ({operation})"
            
            # Create arguments context
            arguments = {
                'tool_name': tool_name,
                'operation': operation,
                'params': error_data.get('params', {}),
                'browser': error_data.get('browser', 'Unknown'),
                'url': error_data.get('url', 'Unknown'),
                'timestamp': error_data.get('timestamp', datetime.utcnow().isoformat())
            }
            
            # Create environment context from client info
            environment = {
                'USER_AGENT': error_data.get('user_agent', 'Unknown'),
                'BROWSER': error_data.get('browser', 'Unknown'),
                'PLATFORM': error_data.get('platform', 'Unknown'),
                'CLIENT_VERSION': error_data.get('sdk_version', 'Unknown')
            }
            
            # Create log context from client logs
            log_context = error_data.get('console_logs', [])
            
            # Create captured error object
            captured_error = CapturedError(
                error_type=error_type,
                error_message=error_message,
                stack_trace=stack_trace,
                timestamp=datetime.utcnow().isoformat(),
                command=command,
                arguments=arguments,
                environment=environment,
                log_context=log_context if isinstance(log_context, list) else [str(log_context)],
                working_directory='Client-side (Browser)',
                python_version='JavaScript SDK'
            )
            
            # Create GitHub issue
            issue_creator = GitHubIssueCreator(config)
            issue_url = issue_creator.create_issue_from_error(captured_error)
            
            if issue_url:
                logger.info(f"Client-side error reported to GitHub: {issue_url}")
            
        except Exception as heal_error:
            logger.error(f"Failed to trigger auto-heal for client error: {heal_error}")


# Global instance for client error reporting
_client_error_reporter = None


def get_client_error_reporter() -> ClientErrorReporter:
    """
    Get or create the global client error reporter instance.
    
    Returns:
        ClientErrorReporter instance
    """
    global _client_error_reporter
    
    if _client_error_reporter is None:
        _client_error_reporter = ClientErrorReporter()
    
    return _client_error_reporter
