"""
Core Infrastructure Components for IPFS Kit MCP Integration

This package contains the core infrastructure components for Phase 1:
- Tool Registry System
- Service Management
- Error Handling
- Testing Framework
"""

from .tool_registry import ToolRegistry, ToolSchema, ToolCategory, ToolStatus, registry, tool
from .service_manager import ServiceManager, IPFSServiceManager, ServiceConfig, ServiceStatus, service_manager, ipfs_manager
from .error_handler import ErrorHandler, MCPError, ErrorCode, ErrorCategory, ErrorSeverity, error_handler, create_success_response
from .test_framework import TestFramework, TestResult, TestSuite, TestStatus, TestCategory, test_framework

__all__ = [
    # Tool Registry
    'ToolRegistry', 'ToolSchema', 'ToolCategory', 'ToolStatus', 'registry', 'tool',
    
    # Service Manager
    'ServiceManager', 'IPFSServiceManager', 'ServiceConfig', 'ServiceStatus', 'service_manager', 'ipfs_manager',
    
    # Error Handler
    'ErrorHandler', 'MCPError', 'ErrorCode', 'ErrorCategory', 'ErrorSeverity', 'error_handler', 'create_success_response',
    
    # Test Framework
    'TestFramework', 'TestResult', 'TestSuite', 'TestStatus', 'TestCategory', 'test_framework'
]

__version__ = "1.0.0"
__author__ = "IPFS Kit MCP Integration Team"
