"""
Network module for libp2p.

This module provides network-related components for the libp2p networking stack,
including interfaces and implementations for network operations.
"""

import logging

# Configure logger
logger = logging.getLogger(__name__)

# Import and expose stream components
try:
    from .stream import (
        INetStream, NetStream, StreamError, StreamHandler
    )
except ImportError:
    logger.warning("Could not import stream components")
    
    # These will be provided by the placeholder implementations in stream/__init__.py
    from .stream import (
        INetStream, NetStream, StreamError, StreamHandler
    )