#!/usr/bin/env python3
"""
Update libp2p compatibility based on test results.

This script updates our libp2p integration to work better with the current
libp2p 0.2.8 API and protobuf 3.20.3.
"""

import sys
import os

def update_libp2p_compatibility():
    """Update libp2p compatibility layers."""
    
    print("🔧 UPDATING LIBP2P COMPATIBILITY")
    print("=" * 50)
    
    # 1. Update the missing module compatibility in libp2p_peer.py
    libp2p_peer_file = "/home/barberb/ipfs_kit_py/ipfs_kit_py/libp2p_peer.py"
    
    # Read the file
    with open(libp2p_peer_file, 'r') as f:
        content = f.read()
    
    # Fix the stream interface import issue
    old_stream_import = '''        try:
            from libp2p.network.stream.exceptions import StreamError
            from libp2p.network.stream.net_stream_interface import INetStream
        except ImportError as e:
            logger.warning(f"libp2p.network.stream modules not available: {e}. Streaming functionality will be limited.")
            # Define a minimal StreamError class
            class StreamError(Exception):
                """Error in stream operations."""
                pass'''
    
    new_stream_import = '''        try:
            from libp2p.network.stream.net_stream import NetStream as INetStream
            from libp2p.network.stream.exceptions import StreamError
        except ImportError as e:
            logger.warning(f"libp2p.network.stream modules not available: {e}. Streaming functionality will be limited.")
            # Define minimal fallback classes
            class StreamError(Exception):
                """Error in stream operations."""
                pass
            
            class INetStream:
                """Minimal stream interface fallback."""
                pass'''
    
    if old_stream_import in content:
        content = content.replace(old_stream_import, new_stream_import)
        print("✓ Updated stream interface imports")
    
    # Fix pubsub import issues
    old_pubsub_import = '''        # Handle missing pubsub_utils gracefully
        HAS_PUBSUB = True
        try:
            import libp2p.tools.pubsub.utils as pubsub_utils
        except ImportError as e:
            HAS_PUBSUB = False
            logger.warning(f"libp2p.tools.pubsub module not available: {e}. PubSub functionality will be limited.")
            # Import our custom pubsub implementation
            from ipfs_kit_py.libp2p.tools.pubsub.utils import create_pubsub'''
    
    new_pubsub_import = '''        # Handle missing pubsub_utils gracefully
        HAS_PUBSUB = True
        try:
            from libp2p.pubsub.gossipsub import GossipSub
            from libp2p.pubsub.floodsub import FloodSub
            logger.debug("libp2p pubsub modules available")
        except ImportError as e:
            HAS_PUBSUB = False
            logger.warning(f"libp2p.pubsub modules not available: {e}. PubSub functionality will be limited.")
            # Import our custom pubsub implementation
            from ipfs_kit_py.libp2p.tools.pubsub.utils import create_pubsub'''
    
    if old_pubsub_import in content:
        content = content.replace(old_pubsub_import, new_pubsub_import)
        print("✓ Updated pubsub imports")
    
    # Write the updated file
    with open(libp2p_peer_file, 'w') as f:
        f.write(content)
    
    print("✓ Updated libp2p_peer.py compatibility")
    
    # 2. Create a better compatibility module for missing constants
    constants_file = "/home/barberb/ipfs_kit_py/ipfs_kit_py/libp2p/tools/constants.py"
    os.makedirs(os.path.dirname(constants_file), exist_ok=True)
    
    constants_content = '''"""
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

print("✓ libp2p tools.constants module loaded with compatibility values")
'''
    
    with open(constants_file, 'w') as f:
        f.write(constants_content)
    
    print("✓ Created libp2p tools/constants.py")
    
    # 3. Create pubsub compatibility
    pubsub_utils_file = "/home/barberb/ipfs_kit_py/ipfs_kit_py/libp2p/tools/pubsub/utils.py"
    os.makedirs(os.path.dirname(pubsub_utils_file), exist_ok=True)
    
    pubsub_content = '''"""
PubSub utilities for libp2p compatibility.

This module provides pubsub utilities that may be missing from the current libp2p version.
"""

import logging

logger = logging.getLogger(__name__)

def create_pubsub(host, router_type="gossipsub"):
    """Create a pubsub instance with the given router type."""
    try:
        if router_type == "gossipsub":
            from libp2p.pubsub.gossipsub import GossipSub
            return GossipSub(host_id=host.get_id(), router=None)
        elif router_type == "floodsub":
            from libp2p.pubsub.floodsub import FloodSub
            return FloodSub(host_id=host.get_id())
        else:
            logger.warning(f"Unknown router type: {router_type}, falling back to floodsub")
            from libp2p.pubsub.floodsub import FloodSub
            return FloodSub(host_id=host.get_id())
    except Exception as e:
        logger.error(f"Failed to create pubsub: {e}")
        return None

print("✓ libp2p tools.pubsub.utils module loaded")
'''
    
    with open(pubsub_utils_file, 'w') as f:
        f.write(pubsub_content)
    
    print("✓ Created libp2p tools/pubsub/utils.py")
    
    # 4. Create __init__.py files
    init_files = [
        "/home/barberb/ipfs_kit_py/ipfs_kit_py/libp2p/tools/__init__.py",
        "/home/barberb/ipfs_kit_py/ipfs_kit_py/libp2p/tools/pubsub/__init__.py"
    ]
    
    for init_file in init_files:
        os.makedirs(os.path.dirname(init_file), exist_ok=True)
        with open(init_file, 'w') as f:
            f.write('# libp2p tools module\n')
    
    print("✓ Created __init__.py files")
    
    print("\n🎉 LIBP2P COMPATIBILITY UPDATES COMPLETE")
    return True

if __name__ == "__main__":
    success = update_libp2p_compatibility()
    sys.exit(0 if success else 1)
