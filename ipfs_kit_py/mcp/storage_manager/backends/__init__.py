"""
Storage backend implementations.

This package contains implementations of various storage backends used by the MCP server.
"""

from .ipfs_backend import IPFSBackend

__all__ = [
    "IPFSBackend"
]
