"""
Constants for libp2p functionality.

This module re-exports constants from the parent constants module for
backward compatibility with code that imports from this path.
"""

import logging
import sys

# Configure logger
logger = logging.getLogger(__name__)

# Import constants from parent module
try:
    from ..constants import *
except ImportError:
    logger.warning("Could not import constants from parent module")
    
    # Define basic constants for compatibility
    ALPHA_VALUE = 3
    MAX_PROVIDERS_PER_KEY = 20
    CLOSER_PEER_COUNT = 16
    MAX_MESSAGE_SIZE = 1024 * 1024  # 1MB
    DEFAULT_PROTOCOL_TIMEOUT = 10
    PROTOCOL_KAD_DHT = "/ipfs/kad/1.0.0"
    DHT_RECORD_TTL = 24 * 60 * 60  # 24 hours