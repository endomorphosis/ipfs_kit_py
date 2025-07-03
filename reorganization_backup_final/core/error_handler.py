#!/usr/bin/env python3
"""
Enhanced Error Handling for IPFS Kit MCP Integration

This module provides comprehensive error handling with:
- Consistent error response format
- Error classification and taxonomy
- Error recovery strategies
- Logging and monitoring integration
"""

import json
import logging
import traceback
from typing import Dict, Any, Optional, Union, List, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime
import uuid

# Setup logging
logger = logging.getLogger(__name__)

class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ErrorCategory(Enum):
    """Error category classification"""
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    TIMEOUT = "timeout"
    NETWORK = "network"
    STORAGE = "storage"
    IPFS = "ipfs"
    VFS = "vfs"
    SYSTEM = "system"
    EXTERNAL = "external"
    UNKNOWN = "unknown"

class ErrorCode(Enum):
    """Standardized error codes"""
    # Validation errors (1000-1099)
    INVALID_PARAMETER = "E1001"
    MISSING_PARAMETER = "E1002"
    INVALID_FORMAT = "E1003"
    PARAMETER_OUT_OF_RANGE = "E1004"
    
    # Authentication errors (1100-1199)
    INVALID_CREDENTIALS = "E1101"
    TOKEN_EXPIRED = "E1102"
    TOKEN_INVALID = "E1103"
    
    # Authorization errors (1200-1299)
    ACCESS_DENIED = "E1201"
    INSUFFICIENT_PERMISSIONS = "E1202"
    
    # Resource errors (1300-1399)
    RESOURCE_NOT_FOUND = "E1301"
    RESOURCE_EXISTS = "E1302"
    RESOURCE_LOCKED = "E1303"
    RESOURCE_CORRUPTED = "E1304"
    
    # Network errors (1400-1499)
    CONNECTION_FAILED = "E1401"
    TIMEOUT = "E1402"
    NETWORK_UNAVAILABLE = "E1403"
    
    # IPFS errors (1500-1599)
    IPFS_DAEMON_NOT_RUNNING = "E1501"
    IPFS_API_ERROR = "E1502"
    IPFS_CID_INVALID = "E1503"
    IPFS_PIN_FAILED = "E1504"
    IPFS_ADD_FAILED = "E1505"
    
    # VFS errors (1600-1699)
    VFS_MOUNT_FAILED = "E1601"
    VFS_PATH_NOT_FOUND = "E1602"
    VFS_PERMISSION_DENIED = "E1603"
    VFS_SYNC_FAILED = "E1604"
    
    # System errors (1700-1799)
    INTERNAL_ERROR = "E1701"
    SERVICE_UNAVAILABLE = "E1702"
    CONFIGURATION_ERROR = "E1703"
    DEPENDENCY_ERROR = "E1704"
    
    # Tool errors (1800-1899)
    TOOL_NOT_FOUND = "E1801"
    TOOL_EXECUTION_FAILED = "E1802"
    TOOL_TIMEOUT = "E1803"
    TOOL_DEPENDENCY_MISSING = "E1804"

@dataclass
class ErrorContext:
    """Additional context for errors"""
    tool_name: Optional[str] = None
    operation: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    timestamp: Optional[str] = None
    trace_id: Optional[str] = None

@dataclass
class MCPError:
    """Standardized MCP error structure"""
    status: str = "error"
    error: str = ""
    error_code: str = ""
    category: str = ""
    severity: str = ""
    context: Optional[Dict[str, Any]] = None
    suggestions: Optional[List[str]] = None
    recoverable: bool = True
    retry_after: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response"""
        result: Dict[str, Any] = {
            "status": self.status,
            "error": self.error,
            "error_code": self.error_code
        }
        
        if self.category:
            result["category"] = self.category
        if self.severity:
            result["severity"] = self.severity
        if self.context:
            result["context"] = self.context
        if self.suggestions:
            result["suggestions"] = self.suggestions
        if not self.recoverable:
            result["recoverable"] = self.recoverable
        if self.retry_after:
            result["retry_after"] = self.retry_after
            
        return result

class ErrorHandler:
    """Comprehensive error handling and recovery system"""
    
    def __init__(self):
        self.error_counts: Dict[str, int] = {}
        self.recovery_strategies: Dict[ErrorCode, Callable] = {}
        self.error_templates: Dict[ErrorCode, Dict[str, Any]] = {}
        
        # Initialize error templates
        self._initialize_error_templates()
        
        # Initialize recovery strategies
        self._initialize_recovery_strategies()
    
    def create_error(self, 
                    error_code: ErrorCode,
                    message: str = "",
                    context: Optional[ErrorContext] = None,
                    suggestions: Optional[List[str]] = None) -> MCPError:
        """Create a standardized error"""
        
        # Get template
        template = self.error_templates.get(error_code, {})
        
        # Generate trace ID
        trace_id = str(uuid.uuid4())
        
        # Prepare context
        error_context = {}
        if context:
            error_context.update(asdict(context))
            if not context.trace_id:
                error_context['trace_id'] = trace_id
            if not context.timestamp:
                error_context['timestamp'] = datetime.utcnow().isoformat()
        else:
            error_context = {
                'trace_id': trace_id,
                'timestamp': datetime.utcnow().isoformat()
            }
        
        # Create error
        error = MCPError(
            error=message or template.get('message', 'An error occurred'),
            error_code=error_code.value,
            category=template.get('category', ErrorCategory.UNKNOWN.value),
            severity=template.get('severity', ErrorSeverity.MEDIUM.value),
            context=error_context,
            suggestions=suggestions or template.get('suggestions', []),
            recoverable=template.get('recoverable', True),
            retry_after=template.get('retry_after')
        )
        
        # Log error
        self._log_error(error)
        
        # Update error counts
        self.error_counts[error_code.value] = self.error_counts.get(error_code.value, 0) + 1
        
        return error
    
    def handle_exception(self, 
                        exception: Exception,
                        context: Optional[ErrorContext] = None,
                        tool_name: Optional[str] = None) -> MCPError:
        """Handle an exception and convert to standardized error"""
        
        # Determine error code based on exception type
        error_code = self._classify_exception(exception)
        
        # Create context if not provided
        if not context:
            context = ErrorContext(tool_name=tool_name)
        elif not context.tool_name and tool_name:
            context.tool_name = tool_name
        
        # Add exception details to context
        if context:
            context_dict = asdict(context)
            context_dict.update({
                'exception_type': type(exception).__name__,
                'exception_message': str(exception),
                'traceback': traceback.format_exc()
            })
            context = ErrorContext(**{k: v for k, v in context_dict.items() if k in ErrorContext.__annotations__})
        
        error = self.create_error(
            error_code=error_code,
            message=str(exception),
            context=context
        )
        
        return error
    
    def attempt_recovery(self, error: MCPError) -> Optional[Dict[str, Any]]:
        """Attempt to recover from an error"""
        error_code = ErrorCode(error.error_code)
        
        if error_code in self.recovery_strategies:
            try:
                recovery_func = self.recovery_strategies[error_code]
                return recovery_func(error)
            except Exception as e:
                logger.error(f"Recovery strategy failed for {error_code}: {e}")
        
        return None
    
    def _classify_exception(self, exception: Exception) -> ErrorCode:
        """Classify exception and return appropriate error code"""
        exception_type = type(exception).__name__
        exception_msg = str(exception).lower()
        
        # Network errors
        if any(term in exception_type.lower() for term in ['connection', 'timeout', 'network']):
            if 'timeout' in exception_msg:
                return ErrorCode.TIMEOUT
            return ErrorCode.CONNECTION_FAILED
        
        # File/Resource errors
        if 'notfound' in exception_type.lower() or 'not found' in exception_msg:
            return ErrorCode.RESOURCE_NOT_FOUND
        
        # Permission errors
        if 'permission' in exception_type.lower() or 'access' in exception_msg:
            return ErrorCode.VFS_PERMISSION_DENIED
        
        # Validation errors
        if any(term in exception_type.lower() for term in ['value', 'type', 'attribute']):
            return ErrorCode.INVALID_PARAMETER
        
        # IPFS specific errors
        if 'ipfs' in exception_msg:
            return ErrorCode.IPFS_API_ERROR
        
        # Default to internal error
        return ErrorCode.INTERNAL_ERROR
    
    def _initialize_error_templates(self):
        """Initialize error message templates"""
        self.error_templates = {
            # Validation errors
            ErrorCode.INVALID_PARAMETER: {
                'message': 'Invalid parameter provided',
                'category': ErrorCategory.VALIDATION.value,
                'severity': ErrorSeverity.LOW.value,
                'suggestions': ['Check parameter format and type', 'Refer to API documentation'],
                'recoverable': True
            },
            ErrorCode.MISSING_PARAMETER: {
                'message': 'Required parameter is missing',
                'category': ErrorCategory.VALIDATION.value,
                'severity': ErrorSeverity.LOW.value,
                'suggestions': ['Check required parameters', 'Refer to API documentation'],
                'recoverable': True
            },
            
            # Network errors
            ErrorCode.CONNECTION_FAILED: {
                'message': 'Failed to establish connection',
                'category': ErrorCategory.NETWORK.value,
                'severity': ErrorSeverity.MEDIUM.value,
                'suggestions': ['Check network connectivity', 'Verify service is running'],
                'recoverable': True,
                'retry_after': 5
            },
            ErrorCode.TIMEOUT: {
                'message': 'Operation timed out',
                'category': ErrorCategory.TIMEOUT.value,
                'severity': ErrorSeverity.MEDIUM.value,
                'suggestions': ['Retry the operation', 'Check network stability'],
                'recoverable': True,
                'retry_after': 10
            },
            
            # IPFS errors
            ErrorCode.IPFS_DAEMON_NOT_RUNNING: {
                'message': 'IPFS daemon is not running',
                'category': ErrorCategory.IPFS.value,
                'severity': ErrorSeverity.HIGH.value,
                'suggestions': ['Start IPFS daemon', 'Check IPFS installation'],
                'recoverable': True
            },
            ErrorCode.IPFS_CID_INVALID: {
                'message': 'Invalid IPFS CID format',
                'category': ErrorCategory.IPFS.value,
                'severity': ErrorSeverity.LOW.value,
                'suggestions': ['Check CID format', 'Verify CID exists'],
                'recoverable': True
            },
            
            # VFS errors
            ErrorCode.VFS_MOUNT_FAILED: {
                'message': 'Failed to mount virtual filesystem',
                'category': ErrorCategory.VFS.value,
                'severity': ErrorSeverity.HIGH.value,
                'suggestions': ['Check mount permissions', 'Verify target exists'],
                'recoverable': True
            },
            
            # System errors
            ErrorCode.INTERNAL_ERROR: {
                'message': 'Internal server error',
                'category': ErrorCategory.SYSTEM.value,
                'severity': ErrorSeverity.HIGH.value,
                'suggestions': ['Contact system administrator', 'Check server logs'],
                'recoverable': False
            },
            ErrorCode.SERVICE_UNAVAILABLE: {
                'message': 'Service temporarily unavailable',
                'category': ErrorCategory.SYSTEM.value,
                'severity': ErrorSeverity.MEDIUM.value,
                'suggestions': ['Retry after some time', 'Check service status'],
                'recoverable': True,
                'retry_after': 30
            }
        }
    
    def _initialize_recovery_strategies(self):
        """Initialize automated recovery strategies"""
        
        def recover_ipfs_daemon(error: MCPError) -> Optional[Dict[str, Any]]:
            """Attempt to start IPFS daemon"""
            try:
                from .service_manager import ipfs_manager
                if ipfs_manager.ensure_ipfs_running():
                    return {"recovered": True, "action": "started_ipfs_daemon"}
            except Exception:
                pass
            return None
        
        def recover_network_connection(error: MCPError) -> Optional[Dict[str, Any]]:
            """Attempt network recovery"""
            # Could implement connection retry logic here
            return {"recovered": False, "suggestion": "retry_after_delay"}
        
        self.recovery_strategies = {
            ErrorCode.IPFS_DAEMON_NOT_RUNNING: recover_ipfs_daemon,
            ErrorCode.CONNECTION_FAILED: recover_network_connection,
            ErrorCode.TIMEOUT: recover_network_connection
        }
    
    def _log_error(self, error: MCPError):
        """Log error with appropriate level"""
        severity = error.severity
        message = f"[{error.error_code}] {error.error}"
        
        if severity == ErrorSeverity.CRITICAL.value:
            logger.critical(message, extra={'error_context': error.context})
        elif severity == ErrorSeverity.HIGH.value:
            logger.error(message, extra={'error_context': error.context})
        elif severity == ErrorSeverity.MEDIUM.value:
            logger.warning(message, extra={'error_context': error.context})
        else:
            logger.info(message, extra={'error_context': error.context})
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics"""
        return {
            'total_errors': sum(self.error_counts.values()),
            'error_counts': self.error_counts.copy(),
            'most_common': sorted(self.error_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        }

# Convenience functions for creating common errors
def create_success_response(data: Any = None, message: str = "Operation completed successfully") -> Dict[str, Any]:
    """Create a standardized success response"""
    response = {
        "status": "success",
        "message": message
    }
    if data is not None:
        response["data"] = data
    return response

def create_validation_error(message: str, parameter: Optional[str] = None, context: Optional[ErrorContext] = None) -> MCPError:
    """Create a validation error"""
    if not context:
        context = ErrorContext()
    if parameter:
        context.parameters = {"invalid_parameter": parameter}
    
    return error_handler.create_error(
        ErrorCode.INVALID_PARAMETER,
        message,
        context
    )

def create_ipfs_error(message: str, operation: Optional[str] = None, context: Optional[ErrorContext] = None) -> MCPError:
    """Create an IPFS-related error"""
    if not context:
        context = ErrorContext()
    if operation:
        context.operation = operation
    
    return error_handler.create_error(
        ErrorCode.IPFS_API_ERROR,
        message,
        context
    )

def create_vfs_error(message: str, path: Optional[str] = None, context: Optional[ErrorContext] = None) -> MCPError:
    """Create a VFS-related error"""
    if not context:
        context = ErrorContext()
    if path:
        context.parameters = {"path": path}
    
    return error_handler.create_error(
        ErrorCode.VFS_PATH_NOT_FOUND,
        message,
        context
    )

# Global error handler instance
error_handler = ErrorHandler()
