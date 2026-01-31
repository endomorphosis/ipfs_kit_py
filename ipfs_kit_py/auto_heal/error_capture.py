"""
Error capture and logging for auto-healing.
"""

import sys
import traceback
import logging
from datetime import datetime
from typing import Optional, Any, Dict, List
from dataclasses import dataclass, asdict
from functools import wraps
import os
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class CapturedError:
    """Represents a captured error with context."""
    
    error_type: str
    error_message: str
    stack_trace: str
    timestamp: str
    command: str
    arguments: Dict[str, Any]
    environment: Dict[str, str]
    log_context: List[str]
    working_directory: str
    python_version: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    def format_for_issue(self, max_log_lines: int = 100) -> str:
        """Format error for GitHub issue creation."""
        log_lines = self.log_context[-max_log_lines:] if len(self.log_context) > max_log_lines else self.log_context
        
        issue_body = f"""## CLI Error Auto-Report

### Error Information
- **Type:** `{self.error_type}`
- **Message:** {self.error_message}
- **Timestamp:** {self.timestamp}
- **Working Directory:** `{self.working_directory}`
- **Python Version:** {self.python_version}

### Command Executed
```bash
{self.command}
```

### Arguments
```json
{self._format_arguments()}
```

### Stack Trace
```python
{self.stack_trace}
```

### Log Context ({len(log_lines)} lines)
```
{chr(10).join(log_lines)}
```

### Environment
```
{self._format_environment()}
```

---
**Note:** This issue was automatically created by the IPFS-Kit auto-healing system.
The system will attempt to create a draft PR with a fix for this error.
"""
        return issue_body
    
    def _format_arguments(self) -> str:
        """Format arguments as JSON string."""
        import json
        try:
            return json.dumps(self.arguments, indent=2, default=str)
        except Exception:
            return str(self.arguments)
    
    def _format_environment(self) -> str:
        """Format relevant environment variables."""
        relevant_vars = {
            k: v for k, v in self.environment.items()
            if any(keyword in k.upper() for keyword in ['IPFS', 'GITHUB', 'PATH', 'HOME', 'USER'])
        }
        return '\n'.join(f"{k}={v}" for k, v in sorted(relevant_vars.items()))


class ErrorCapture:
    """Captures errors with context for auto-healing."""
    
    def __init__(self, max_log_lines: int = 100):
        """Initialize error capture."""
        self.max_log_lines = max_log_lines
        self.log_buffer: List[str] = []
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup logging to capture log context."""
        # Create a custom handler to capture logs
        class LogBufferHandler(logging.Handler):
            def __init__(self, buffer: List[str], max_lines: int):
                super().__init__()
                self.buffer = buffer
                self.max_lines = max_lines
            
            def emit(self, record):
                try:
                    msg = self.format(record)
                    self.buffer.append(msg)
                    # Keep only the last max_lines
                    if len(self.buffer) > self.max_lines:
                        self.buffer.pop(0)
                except Exception:
                    pass
        
        # Add handler to root logger
        handler = LogBufferHandler(self.log_buffer, self.max_log_lines)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        logging.getLogger().addHandler(handler)
    
    def capture_error(
        self,
        exception: Exception,
        command: str,
        arguments: Dict[str, Any]
    ) -> CapturedError:
        """Capture an error with full context."""
        
        # Get stack trace
        tb = traceback.format_exception(type(exception), exception, exception.__traceback__)
        stack_trace = ''.join(tb)
        
        # Capture environment - filter sensitive variables at capture time
        # Only include safe environment variables
        safe_prefixes = ['IPFS', 'GITHUB_REPOSITORY', 'PATH', 'HOME', 'USER', 'LANG', 'LC_', 
                         'SHELL', 'TERM', 'PWD', 'OLDPWD', 'EDITOR', 'PAGER', 'DISPLAY',
                         'XDG_', 'PYTHON', 'NODE', 'GO', 'CARGO', 'GH_CACHE']
        env = {
            k: v for k, v in os.environ.items()
            if any(k.startswith(prefix) for prefix in safe_prefixes) 
            and 'TOKEN' not in k.upper() 
            and 'PASSWORD' not in k.upper()
            and 'SECRET' not in k.upper()
            and 'KEY' not in k.upper()
        }
        
        # Create captured error
        captured = CapturedError(
            error_type=type(exception).__name__,
            error_message=str(exception),
            stack_trace=stack_trace,
            timestamp=datetime.utcnow().isoformat(),
            command=command,
            arguments=arguments,
            environment=env,
            log_context=list(self.log_buffer),
            working_directory=os.getcwd(),
            python_version=sys.version,
        )
        
        return captured


def capture_cli_errors(func):
    """Decorator to capture CLI errors and trigger auto-healing."""
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        from .config import AutoHealConfig
        from .github_issue_creator import GitHubIssueCreator
        
        # Load configuration
        config = AutoHealConfig.from_file()
        
        # Initialize error capture
        error_capture = ErrorCapture(max_log_lines=config.max_log_lines)
        
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # Capture the error
            command = f"ipfs-kit {' '.join(sys.argv[1:])}"
            arguments = {'args': args, 'kwargs': kwargs}
            
            captured_error = error_capture.capture_error(e, command, arguments)
            
            # Log the error
            logger.error(f"Captured error: {captured_error.error_type}: {captured_error.error_message}")
            
            # Create GitHub issue if configured
            if config.is_configured():
                try:
                    issue_creator = GitHubIssueCreator(config)
                    issue_url = issue_creator.create_issue_from_error(captured_error)
                    
                    if issue_url:
                        logger.info(f"Created auto-heal issue: {issue_url}")
                        print(f"\n⚠️  An error occurred and has been automatically reported.")
                        print(f"📋 Issue created: {issue_url}")
                        print(f"🤖 The auto-healing system will attempt to fix this error.\n")
                except Exception as issue_error:
                    logger.error(f"Failed to create GitHub issue: {issue_error}")
            else:
                # Auto-healing not configured, just show the error
                logger.info("Auto-healing not configured. Set IPFS_KIT_AUTO_HEAL=true and provide GITHUB_TOKEN to enable.")
            
            # Re-raise the original exception
            raise
    
    return wrapper


async def capture_cli_errors_async(func):
    """Async decorator to capture CLI errors and trigger auto-healing."""
    
    @wraps(func)
    async def wrapper(*args, **kwargs):
        from .config import AutoHealConfig
        from .github_issue_creator import GitHubIssueCreator
        
        # Load configuration
        config = AutoHealConfig.from_file()
        
        # Initialize error capture
        error_capture = ErrorCapture(max_log_lines=config.max_log_lines)
        
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            # Capture the error
            command = f"ipfs-kit {' '.join(sys.argv[1:])}"
            arguments = {'args': args, 'kwargs': kwargs}
            
            captured_error = error_capture.capture_error(e, command, arguments)
            
            # Log the error
            logger.error(f"Captured error: {captured_error.error_type}: {captured_error.error_message}")
            
            # Create GitHub issue if configured
            if config.is_configured():
                try:
                    issue_creator = GitHubIssueCreator(config)
                    issue_url = issue_creator.create_issue_from_error(captured_error)
                    
                    if issue_url:
                        logger.info(f"Created auto-heal issue: {issue_url}")
                        print(f"\n⚠️  An error occurred and has been automatically reported.")
                        print(f"📋 Issue created: {issue_url}")
                        print(f"🤖 The auto-healing system will attempt to fix this error.\n")
                except Exception as issue_error:
                    logger.error(f"Failed to create GitHub issue: {issue_error}")
            else:
                # Auto-healing not configured, just show the error
                logger.info("Auto-healing not configured. Set IPFS_KIT_AUTO_HEAL=true and provide GITHUB_TOKEN to enable.")
            
            # Re-raise the original exception
            raise
    
    return wrapper
