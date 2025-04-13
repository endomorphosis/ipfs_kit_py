"""
Tools for libp2p implementation.

This module provides utilities and constants for libp2p functionality.
"""

import logging

# Configure logger
logger = logging.getLogger(__name__)

# Import and expose constants
try:
    from .constants import (
        ALPHA_VALUE,
        MAX_PROVIDERS_PER_KEY,
        CLOSER_PEER_COUNT,
        MAX_MESSAGE_SIZE,
        MAX_CONNECTIONS,
        DEFAULT_PROTOCOL_TIMEOUT,
        PROTOCOL_BITSWAP,
        PROTOCOL_IDENTIFY,
        PROTOCOL_KAD_DHT,
        PROTOCOL_PING,
        PROTOCOL_CIRCUIT_RELAY,
        PROTOCOL_CIRCUIT_HOP,
        DEFAULT_BOOTSTRAP_PEERS,
        PROVIDER_PREFIX,
        VALUE_PREFIX,
        PEER_PREFIX,
        DHT_RECORD_TTL,
        DHT_REPUBLISH_INTERVAL,
        PRIORITY_CRITICAL,
        PRIORITY_HIGH,
        PRIORITY_NORMAL,
        PRIORITY_LOW,
        PRIORITY_BACKGROUND
    )
except ImportError:
    logger.warning("Could not import libp2p constants")
    
    # Define basic constants for compatibility
    ALPHA_VALUE = 3
    MAX_PROVIDERS_PER_KEY = 20
    CLOSER_PEER_COUNT = 16
    MAX_MESSAGE_SIZE = 1024 * 1024  # 1MB
    MAX_CONNECTIONS = 100
    DEFAULT_PROTOCOL_TIMEOUT = 10
    PROTOCOL_BITSWAP = "/ipfs/bitswap/1.2.0"
    PROTOCOL_IDENTIFY = "/ipfs/id/1.0.0"
    PROTOCOL_KAD_DHT = "/ipfs/kad/1.0.0"
    PROTOCOL_PING = "/ipfs/ping/1.0.0"
    PROTOCOL_CIRCUIT_RELAY = "/libp2p/circuit/relay/0.1.0"
    PROTOCOL_CIRCUIT_HOP = "/libp2p/circuit/relay/hop/1.0.0"
    DHT_RECORD_TTL = 24 * 60 * 60  # 24 hours
    DHT_REPUBLISH_INTERVAL = 23 * 60 * 60  # 23 hours
    PRIORITY_NORMAL = 3

# Import pubsub utilities
from .pubsub import (
    validate_pubsub_topic,
    format_pubsub_message,
    extract_pubsub_message_data,
    format_message_from_event,
    create_pubsub_subscription_handler,
    create_pubsub,
    MockPubSub
)