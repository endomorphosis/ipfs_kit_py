"""
Utility modules for the MCP server.

This package contains various utility modules that provide common functionality
for the MCP server components.
"""

from .method_normalizer import IPFSMethodAdapter, normalize_instance

# For backward compatibility, keep the old class name as well
NormalizedIPFS = IPFSMethodAdapter

__all__ = ["normalize_instance", "IPFSMethodAdapter", "NormalizedIPFS"]
