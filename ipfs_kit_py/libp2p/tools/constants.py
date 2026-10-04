"""
Constants for libp2p compatibility.

This module provides constants that may be missing from the current libp2p version.
"""

# Default alpha value for DHT operations
ALPHA_VALUE = 3

# Protocol constants
PROTOCOL_PREFIX = "/ipfs/"

# Default timeouts
DEFAULT_TIMEOUT = 30.0
DHT_TIMEOUT = 10.0

# Network constants
DEFAULT_PORT = 4001
MAX_CONNECTIONS = 100

# Content routing constants
MAX_PROVIDERS = 20
PROVIDER_TTL = 3600  # 1 hour

# Avoid printing at import time (breaks CLI JSON output and test parsing).
