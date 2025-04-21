#!/usr/bin/env python3
"""
Constants for libp2p tools.

This module provides constants used by various libp2p components.
"""

# Alpha value for Kademlia DHT
ALPHA_VALUE = 3

# Constants for DHT operation
K_VALUE = 20  # k-bucket size
ID_SIZE = 256  # ID size in bits
ROUTING_TABLE_FLUSH_PERIOD = 600  # seconds

# Constants for peer routing
MAX_PROVIDERS_PER_KEY = 20
PROVIDER_RECORD_TTL = 24 * 60 * 60  # 24 hours in seconds

# Constants for protocol negotiation
PROTOCOL_ID_PREFIX = "/ipfs/"
LIB_P2P_CIRCUIT_RELAY = "/libp2p/circuit/relay/0.1.0"

# Constants for stream handling
MAX_BUFFER_SIZE = 1024 * 1024  # 1MB
DEFAULT_STREAM_TIMEOUT = 60  # seconds

# Constants for PubSub
PUBSUB_TOPIC_PREFIX = "/ipfs/pubsub/"
PUBSUB_SIGNATURE_POLICY = "StrictSign"  # StrictSign, StrictNoSign, WarnOnlySign