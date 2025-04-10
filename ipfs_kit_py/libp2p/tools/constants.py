"""
Constants for libp2p functionality.

This module provides constants used throughout the libp2p ecosystem,
making them available in a central location.
"""

# Alpha value for Kademlia routing
ALPHA_VALUE = 3

# Maximum number of provider peers to return
MAX_PROVIDERS_PER_KEY = 20

# Number of closest peers to return in a DHT query
CLOSER_PEER_COUNT = 16

# Maximum message size for pubsub messages (in bytes)
MAX_MESSAGE_SIZE = 1024 * 1024  # 1MB

# Maximum number of connections to maintain
MAX_CONNECTIONS = 100

# Default protocol timeout (in seconds)
DEFAULT_PROTOCOL_TIMEOUT = 10

# Key protocols
PROTOCOL_BITSWAP = "/ipfs/bitswap/1.2.0"
PROTOCOL_IDENTIFY = "/ipfs/id/1.0.0"
PROTOCOL_KAD_DHT = "/ipfs/kad/1.0.0"
PROTOCOL_PING = "/ipfs/ping/1.0.0"
PROTOCOL_CIRCUIT_RELAY = "/libp2p/circuit/relay/0.1.0"
PROTOCOL_CIRCUIT_HOP = "/libp2p/circuit/relay/hop/1.0.0"

# Default bootstrap nodes
DEFAULT_BOOTSTRAP_PEERS = [
    "/dnsaddr/bootstrap.libp2p.io/p2p/QmNnooDu7bfjPFoTZYxMNLWUQJyrVwtbZg5gBMjTezGAJN",
    "/dnsaddr/bootstrap.libp2p.io/p2p/QmQCU2EcMqAqQPR2i9bChDtGNJchTbq5TbXJJ16u19uLTa",
    "/dnsaddr/bootstrap.libp2p.io/p2p/QmbLHAnMoJPWSCR5Zhtx6BHJX9KiKNN6tpvbUcqanj75Nb",
    "/dnsaddr/bootstrap.libp2p.io/p2p/QmcZf59bWwK5XFi76CZX8cbJ4BhTzzA3gU1ZjYZcYW3dwt"
]

# Values for efficient wire encoding
PROVIDER_PREFIX = b"providers:"
VALUE_PREFIX = b"value:"
PEER_PREFIX = b"peer:"

# DHT record TTL (in seconds)
DHT_RECORD_TTL = 24 * 60 * 60  # 24 hours

# DHT republishing interval (in seconds)
DHT_REPUBLISH_INTERVAL = 23 * 60 * 60  # 23 hours (just under TTL)

# Constants for prioritizing content in bitswap
PRIORITY_CRITICAL = 5
PRIORITY_HIGH = 4
PRIORITY_NORMAL = 3
PRIORITY_LOW = 2
PRIORITY_BACKGROUND = 1