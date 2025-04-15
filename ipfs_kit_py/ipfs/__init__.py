"""
IPFS module for ipfs_kit_py.

This module provides access to the ipfs_py client implementation.
"""

# Import the ipfs_py class directly from our reference implementation
try:
    from .ipfs_py import ipfs_py
except ImportError:
    import logging
    logging.getLogger(__name__).error("Failed to import ipfs_py from reference implementation")
    # Create minimal placeholder that will be replaced by mock in the backend
    class ipfs_py:
        def __init__(self, *args, **kwargs):
            raise ImportError("ipfs_py implementation not available")

# Expose the class for import
__all__ = ['ipfs_py']