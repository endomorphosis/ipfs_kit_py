"""
IPFS Kit Daemon Package.

This package provides the daemon architecture for IPFS Kit:
- IPFSKitDaemon: Standalone daemon for backend management
- IPFSKitDaemonClient: Client library for communicating with daemon  
- DaemonAwareComponent: Base class for daemon-aware components
- CLI tools and launchers

Architecture:
- The daemon handles all heavy operations (health monitoring, pin management, etc.)
- MCP servers and CLI tools are lightweight clients that communicate with the daemon
- This separation allows for better scalability and resource management
"""

from .daemon_client import IPFSKitDaemonClient, DaemonAwareComponent
from .daemon_client import check_daemon_health, ensure_daemon_running

__all__ = [
    "IPFSKitDaemonClient",
    "DaemonAwareComponent", 
    "check_daemon_health",
    "ensure_daemon_running"
]

__version__ = "1.0.0"
