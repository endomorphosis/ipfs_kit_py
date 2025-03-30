"""
IPFS LibP2P Enhanced Integration Module

This module provides integration between the IPFSKit, IPFSFileSystem and 
enhanced libp2p discovery mechanisms. It enables more efficient peer 
discovery and content routing for direct P2P content retrieval without
relying on the IPFS daemon.

Key features:
- Advanced DHT-based peer discovery with k-bucket optimization
- Provider reputation tracking with adaptive backoff strategies
- Intelligent content routing based on network metrics and availability
- Cache miss handling for seamless integration with the tiered cache system
"""

import os
import time
import json
import uuid
import logging
import asyncio
import threading
from typing import Dict, List, Optional, Any, Set, Tuple

# Import our enhanced discovery classes
from .enhanced_dht_discovery import EnhancedDHTDiscovery, ContentRoutingManager

class LibP2PIntegration:
    """Integration layer between libp2p peer discovery and the filesystem cache."""
    
    def __init__(self, libp2p_peer, ipfs_kit=None, cache_manager=None):
        """Initialize the integration layer.
        
        Args:
            libp2p_peer: An IPFSLibp2pPeer instance
            ipfs_kit: The parent IPFSKit instance
            cache_manager: Optional TieredCacheManager instance
        """
        self.libp2p_peer = libp2p_peer
        self.ipfs_kit = ipfs_kit
        self.cache_manager = cache_manager
        self.logger = logging.getLogger(__name__)
        
        # Create enhanced discovery components
        self.discovery = EnhancedDHTDiscovery(
            libp2p_peer,
            role=libp2p_peer.role,
            bootstrap_peers=libp2p_peer.bootstrap_peers
        )
        
        # Create content routing manager
        self.content_router = ContentRoutingManager(
            self.discovery,
            libp2p_peer
        )
        
        # Start discovery
        self.discovery.start()
        
        # Statistics
        self.stats = {
            'cache_misses': 0,
            'cache_misses_handled': 0,
            'cache_misses_failed': 0,
            'total_bytes_retrieved': 0,
            'retrieve_times': [],
        }
    
    def handle_cache_miss(self, cid):
        """Handle a cache miss by attempting to retrieve content via libp2p.
        
        Args:
            cid: The content ID to retrieve
            
        Returns:
            Content data if found, None otherwise
        """
        self.stats['cache_misses'] += 1
        
        try:
            self.logger.debug(f"Handling cache miss for {cid} via libp2p")
            
            # Create a future for content retrieval
            future = self.content_router.retrieve_content(cid, {
                'timeout': 30,  # 30 second timeout
                'max_size': 50 * 1024 * 1024  # 50MB size limit
            })
            
            # Get result from future
            start_time = time.time()
            content = future.result(timeout=30)
            retrieve_time = time.time() - start_time
            
            if content:
                # Successfully retrieved content
                self.stats['cache_misses_handled'] += 1
                self.stats['total_bytes_retrieved'] += len(content)
                self.stats['retrieve_times'].append(retrieve_time)
                
                # Store a limited number of retrieval times
                if len(self.stats['retrieve_times']) > 100:
                    self.stats['retrieve_times'] = self.stats['retrieve_times'][-100:]
                
                # Update the cache with the retrieved content if possible
                if self.cache_manager:
                    self.cache_manager.put(cid, content)
                
                self.logger.info(
                    f"Successfully retrieved {cid} via libp2p "
                    f"({len(content)} bytes in {retrieve_time:.2f}s)"
                )
                
                return content
            else:
                # Failed to retrieve
                self.stats['cache_misses_failed'] += 1
                self.logger.warning(f"Failed to retrieve {cid} via libp2p")
                return None
                
        except Exception as e:
            self.stats['cache_misses_failed'] += 1
            self.logger.error(f"Error handling cache miss for {cid}: {e}")
            return None
    
    def announce_content(self, cid, data=None, size=None, metadata=None):
        """Announce that we have a specific content.
        
        Args:
            cid: Content ID to announce
            data: The actual content data (optional)
            size: Size of the content in bytes (optional)
            metadata: Additional metadata about the content (optional)
            
        Returns:
            Boolean indicating success
        """
        try:
            # If size is not provided but data is, calculate size
            if size is None and data is not None:
                size = len(data)
            
            # Prepare metadata
            metadata = metadata or {}
            if size is not None:
                metadata['size'] = size
            
            # Announce via content router
            success = self.content_router.announce_content(cid, size, metadata)
            
            self.logger.debug(f"Announced content {cid} (success: {success})")
            return success
            
        except Exception as e:
            self.logger.warning(f"Error announcing content {cid}: {e}")
            return False
    
    def stop(self):
        """Stop the integration layer."""
        try:
            self.discovery.stop()
            self.logger.info("Stopped LibP2P integration layer")
            return True
        except Exception as e:
            self.logger.error(f"Error stopping LibP2P integration: {e}")
            return False
    
    def get_stats(self):
        """Get integration statistics."""
        stats = self.stats.copy()
        
        # Add derived statistics
        if stats['cache_misses'] > 0:
            stats['success_rate'] = stats['cache_misses_handled'] / stats['cache_misses']
        else:
            stats['success_rate'] = 0
            
        if stats['retrieve_times']:
            stats['average_retrieve_time'] = sum(stats['retrieve_times']) / len(stats['retrieve_times'])
        else:
            stats['average_retrieve_time'] = 0
            
        # Add discovery metrics
        stats['discovery_metrics'] = self.content_router.get_metrics()
        
        return stats


def extend_tiered_cache_manager(cache_manager, libp2p_integration):
    """Extend a TieredCacheManager with libp2p integration for cache misses.
    
    Args:
        cache_manager: The TieredCacheManager instance to extend
        libp2p_integration: The LibP2PIntegration instance to use
        
    Returns:
        The extended cache manager
    """
    # Store the original get method
    original_get = cache_manager.get
    
    # Create a new get method that handles misses with libp2p
    def enhanced_get(key):
        # Try to get from cache first
        content = original_get(key)
        
        if content is not None:
            return content
            
        # Cache miss, try to get via libp2p
        if libp2p_integration:
            content = libp2p_integration.handle_cache_miss(key)
            
            if content is not None:
                # We got the content, update cache and return it
                cache_manager.put(key, content)
                return content
                
        # No content found
        return None
    
    # Replace the get method
    cache_manager.get = enhanced_get
    
    # Store the original put method
    original_put = cache_manager.put
    
    # Create a new put method that announces content
    def enhanced_put(key, content, metadata=None):
        # Call the original put method
        result = original_put(key, content, metadata)
        
        # Announce that we have this content
        if libp2p_integration:
            libp2p_integration.announce_content(key, content, metadata=metadata)
            
        return result
    
    # Replace the put method
    cache_manager.put = enhanced_put
    
    return cache_manager


def register_libp2p_with_ipfs_kit(ipfs_kit, libp2p_peer, extend_cache=True):
    """Register a libp2p peer with an IPFSKit instance.
    
    This integrates the libp2p functionality with the IPFSKit by:
    1. Creating a LibP2PIntegration instance
    2. Attaching it to the IPFSKit instance
    3. Optionally extending the TieredCacheManager to handle cache misses
    
    Args:
        ipfs_kit: The IPFSKit instance to extend
        libp2p_peer: The IPFSLibp2pPeer instance to use
        extend_cache: Whether to extend the cache manager
        
    Returns:
        The LibP2PIntegration instance
    """
    # Create the integration layer
    integration = LibP2PIntegration(
        libp2p_peer=libp2p_peer,
        ipfs_kit=ipfs_kit
    )
    
    # Attach to IPFSKit
    ipfs_kit.libp2p_integration = integration
    
    # Extend the cache manager if requested
    if extend_cache and hasattr(ipfs_kit, 'filesystem') and ipfs_kit.filesystem:
        if hasattr(ipfs_kit.filesystem, 'cache'):
            extend_tiered_cache_manager(ipfs_kit.filesystem.cache, integration)
    
    return integration