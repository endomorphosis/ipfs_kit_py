"""
IPFS Kit MCP Module

This module provides the core components for the IPFS Kit Multi-Cloud Platform (MCP) server,
including backend management, virtual file system (VFS) observation, and API routing.
"""

# Import key classes and functions to make them accessible directly under ipfs_kit
from .backends import BackendHealthMonitor, VFSObservabilityManager
from .api.routes import APIRoutes
from .modular_enhanced_mcp_server import ModularEnhancedMCPServer

# Define __all__ for explicit imports
__all__ = [
    "BackendHealthMonitor",
    "VFSObservabilityManager", 
    "APIRoutes",
    "ModularEnhancedMCPServer",
]
