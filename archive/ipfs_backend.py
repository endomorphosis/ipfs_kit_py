"""IPFS Backend

This module provides a simplified interface to the IPFS backend.
"""

from ipfs_kit_py.ipfs_backend import IPFSBackend, get_instance

# Re-export everything from the full module
__all__ = ['IPFSBackend', 'get_instance']