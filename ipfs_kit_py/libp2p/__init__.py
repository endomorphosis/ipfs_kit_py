"""
libp2p package for ipfs_kit_py.

This package provides enhanced libp2p functionality for the ipfs_kit_py project,
including advanced peer discovery, content routing, and direct peer-to-peer
communication without requiring the full IPFS daemon.

Components:
- enhanced_dht_discovery: Advanced DHT-based peer discovery with k-bucket optimization
- content_routing: Intelligent content routing based on peer statistics
- p2p_integration: Integration with IPFSKit and IPFSFileSystem
- ipfs_kit_integration: Extend IPFSKit with libp2p functionality
"""

# Import core components
from .enhanced_dht_discovery import EnhancedDHTDiscovery, ContentRoutingManager
from .p2p_integration import LibP2PIntegration, register_libp2p_with_ipfs_kit
from .ipfs_kit_integration import extend_ipfs_kit_class, apply_ipfs_kit_integration

# Apply integration to ipfs_kit (optional, can also be explicitly called)
try:
    apply_ipfs_kit_integration()
except Exception:
    # Defer integration for explicit application later
    pass

__all__ = [
    'EnhancedDHTDiscovery',
    'ContentRoutingManager',
    'LibP2PIntegration',
    'register_libp2p_with_ipfs_kit',
    'extend_ipfs_kit_class',
    'apply_ipfs_kit_integration',
]