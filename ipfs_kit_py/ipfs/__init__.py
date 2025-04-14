"""
IPFS module for ipfs_kit_py.

This module provides access to the ipfs_py client implementation.
"""

# Import the ipfs_py class for direct use
try:
    # Try to import from the parent's ipfs.py file
    from .. import ipfs
    ipfs_py = ipfs.ipfs_py
except (ImportError, AttributeError):
    # Fallback to ipfs_client if direct import fails
    try:
        from .. import ipfs_client
        ipfs_py = ipfs_client.ipfs_py
    except (ImportError, AttributeError):
        import logging
        logging.getLogger(__name__).error("Failed to import ipfs_py from any location")
        # Create minimal placeholder that will be replaced by mock in the backend
        class ipfs_py:
            def __init__(self, *args, **kwargs):
                raise ImportError("ipfs_py implementation not available")

# Expose the class for import
__all__ = ['ipfs_py']