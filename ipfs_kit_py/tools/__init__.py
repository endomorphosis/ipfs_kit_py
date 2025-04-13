"""
API Stability and Compatibility Tools.

This package contains tools for checking API stability, versioning, and
compatibility between different versions of IPFS Kit.

Submodules:
- check_api_compatibility: Tools for verifying API compatibility between versions
- protobuf_compat: Compatibility layer for different versions of protobuf
"""

# Import key functionality for direct access
try:
    from .protobuf_compat import (
        get_compatible_message_factory,
        monkey_patch_message_factory,
        CompatMessageFactory,
        PROTOBUF_VERSION,
        PROTOBUF_MAJOR_VERSION,
        PROTOBUF_MINOR_VERSION,
        PROTOBUF_PATCH_VERSION,
        HAS_OLD_MESSAGE_FACTORY,
        HAS_NEW_MESSAGE_FACTORY
    )
except ImportError:
    # Protobuf compat not available - this is fine
    pass

# Define exports
__all__ = [
    'get_compatible_message_factory',
    'monkey_patch_message_factory',
    'CompatMessageFactory',
    'PROTOBUF_VERSION',
    'PROTOBUF_MAJOR_VERSION',
    'PROTOBUF_MINOR_VERSION',
    'PROTOBUF_PATCH_VERSION',
    'HAS_OLD_MESSAGE_FACTORY',
    'HAS_NEW_MESSAGE_FACTORY'
]