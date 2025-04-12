"""
PubSub utilities for libp2p.

This module provides compatibility functions that might be missing in the installed version of libp2p.
It implements a robust PubSub system with support for both GossipSub and FloodSub protocols,
suitable for direct inclusion in the libp2p-py library.
"""

import logging
import time
import uuid
import anyio
from typing import Callable, Dict, List, Any, Optional, Union, Type, Set

try:
    # Try importing libp2p components
    from libp2p.pubsub.pubsub import Pubsub
    from libp2p.pubsub.floodsub import FloodSub
    from libp2p.pubsub.gossipsub import GossipSub
    PUBSUB_AVAILABLE = True
except ImportError:
    PUBSUB_AVAILABLE = False

logger = logging.getLogger(__name__)

def validate_pubsub_topic(topic: str) -> bool:
    """
    Validate that a pubsub topic name is valid.
    
    Args:
        topic: The topic name to validate
        
    Returns:
        True if the topic is valid, False otherwise
    """
    # Basic validation - topics should be non-empty strings
    if not topic or not isinstance(topic, str):
        return False
        
    # Topics shouldn't be excessively long (arbitrary limit of 1024 chars)
    if len(topic) > 1024:
        return False
        
    # Check for invalid characters (simplified validation)
    import re
    if not re.match(r'^[a-zA-Z0-9_\-\.\/]+$', topic):
        return False
        
    return True
    
def format_pubsub_message(data: Union[str, bytes], sender_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Format a message for publishing to a pubsub topic according to libp2p specs.
    
    Args:
        data: The message data (string or bytes)
        sender_id: Optional sender identifier
        
    Returns:
        A formatted message dictionary
    """
    # Ensure data is bytes
    if isinstance(data, str):
        data_bytes = data.encode('utf-8')
    else:
        data_bytes = data
        
    # Create standard libp2p message format
    message = {
        "data": data_bytes,
        "seqno": str(uuid.uuid4())[:8].encode(),  # Generate a simple sequence number
        "timestamp": int(time.time() * 1000).to_bytes(8, 'big'),  # Timestamp as bytes
    }
    
    if sender_id:
        message["from"] = sender_id
        
    return message
    
def extract_pubsub_message_data(message: Dict[str, Any]) -> bytes:
    """
    Extract the data from a pubsub message.
    
    Args:
        message: The pubsub message
        
    Returns:
        The message data as bytes
    """
    data = message.get("data")
    if data is None:
        raise ValueError("Message does not contain data field")
    
    return data
    
def format_message_from_event(topic: str, data: bytes, sender_id: str) -> Dict[str, Any]:
    """
    Format a message from a network event for consistent subscription handling.
    
    This helps maintain a consistent message format across different PubSub implementations.
    
    Args:
        topic: The topic the message was received on
        data: The raw message data
        sender_id: The sender's peer ID
        
    Returns:
        A formatted message dictionary
    """
    return {
        "data": data,
        "from": sender_id,
        "topicIDs": [topic],
        "seqno": str(uuid.uuid4())[:8].encode(),  # Generate a sequence number if missing
        "timestamp": int(time.time() * 1000).to_bytes(8, 'big'),  # Add timestamp if missing
    }
    
def create_pubsub_subscription_handler(callback: Callable) -> Callable:
    """
    Create a handler function for pubsub subscriptions with error handling.
    
    This creates a handler that can be used with both async and sync callbacks.
    
    Args:
        callback: The callback function to invoke with the message data
        
    Returns:
        A handler function suitable for use with pubsub subscriptions
    """
    # Check if the callback is async
    is_async = anyio.iscoroutinefunction(callback)
    
    if is_async:
        async def async_handler(message):
            try:
                # Pass the full message to the callback
                await callback(message)
            except Exception as e:
                logger.error(f"Error in async pubsub subscription handler: {e}")
        return async_handler
    else:
        def sync_handler(message):
            try:
                # Pass the full message to the callback
                callback(message)
            except Exception as e:
                logger.error(f"Error in pubsub subscription handler: {e}")
        return sync_handler

def create_pubsub(host, router_type="gossipsub", cache_size=None, strict_signing=True, sign_key=None):
    """
    Create a pubsub instance with the given configuration.

    This function gracefully handles different versions of libp2p-py, adapting to
    the available constructor parameters and features. If libp2p is not available,
    it falls back to a robust mock implementation.

    Args:
        host: The libp2p host to use
        router_type: The pubsub router type to use ("gossipsub" or "floodsub")
        cache_size: Size of the message cache (if applicable)
        strict_signing: Whether to require message signing
        sign_key: Key to use for signing messages

    Returns:
        A pubsub instance
    """
    if not PUBSUB_AVAILABLE:
        # Create a mock pubsub implementation
        return MockPubSub(host, router_type, cache_size, strict_signing, sign_key)
    
    # If real libp2p pubsub is available, create the appropriate type
    if router_type == "gossipsub":
        # Inspect GossipSub.__init__ parameters first
        import inspect
        sig = None
        try:
            sig = inspect.signature(GossipSub.__init__)
        except (ValueError, TypeError):
            # Fallback if we can't get signature
            logger.warning("Could not inspect GossipSub signature, using default parameters")
        
        if sig:
            # Normalize parameter name variations across versions
            param_names = list(sig.parameters.keys())
            
            # Create kwargs based on available parameters
            kwargs = {}
            
            # Check for message_cache_size / cache_size parameter
            if cache_size is not None:
                if 'message_cache_size' in param_names:
                    kwargs['message_cache_size'] = cache_size
                elif 'cache_size' in param_names:
                    kwargs['cache_size'] = cache_size
                    
            # Check for strict_signing parameter
            if 'strict_signing' in param_names:
                kwargs['strict_signing'] = strict_signing
                
            # Check for sign_key parameter
            if 'sign_key' in param_names and sign_key is not None:
                kwargs['sign_key'] = sign_key
            
            # Create GossipSub with appropriate parameters
            try:
                logger.debug(f"Creating GossipSub with params: {kwargs}")
                return GossipSub(host, **kwargs)
            except TypeError as e:
                logger.warning(f"Error creating GossipSub with parameters {kwargs}: {e}")
                try:
                    # Retry with just the host parameter
                    logger.debug("Retrying with just the host parameter")
                    return GossipSub(host)
                except Exception as e2:
                    logger.warning(f"Error creating GossipSub with just host: {e2}")
                    logger.warning("Falling back to MockPubSub implementation")
                    return MockPubSub(host, router_type, cache_size, strict_signing, sign_key)
        else:
            # No signature available, try with minimal parameters
            try:
                return GossipSub(host)
            except Exception as e:
                logger.warning(f"Error creating GossipSub: {e}")
                logger.warning("Falling back to MockPubSub implementation")
                return MockPubSub(host, router_type, cache_size, strict_signing, sign_key)
                
    elif router_type == "floodsub":
        # Inspect FloodSub.__init__ parameters
        import inspect
        sig = None
        try:
            sig = inspect.signature(FloodSub.__init__)
        except (ValueError, TypeError):
            # Fallback if we can't get signature
            logger.warning("Could not inspect FloodSub signature, using default parameters")
        
        if sig:
            # Create kwargs based on available parameters
            param_names = list(sig.parameters.keys())
            kwargs = {}
            
            # Check for strict_signing parameter
            if 'strict_signing' in param_names:
                kwargs['strict_signing'] = strict_signing
                
            # Check for sign_key parameter
            if 'sign_key' in param_names and sign_key is not None:
                kwargs['sign_key'] = sign_key
            
            # Create FloodSub with appropriate parameters
            try:
                logger.debug(f"Creating FloodSub with params: {kwargs}")
                return FloodSub(host, **kwargs)
            except TypeError as e:
                logger.warning(f"Error creating FloodSub with parameters {kwargs}: {e}")
                try:
                    # Retry with just the host parameter
                    logger.debug("Retrying with just the host parameter")
                    return FloodSub(host)
                except Exception as e2:
                    logger.warning(f"Error creating FloodSub with just host: {e2}")
                    logger.warning("Falling back to MockPubSub implementation")
                    return MockPubSub(host, router_type, cache_size, strict_signing, sign_key)
        else:
            # No signature available, try with minimal parameters
            try:
                return FloodSub(host)
            except Exception as e:
                logger.warning(f"Error creating FloodSub: {e}")
                logger.warning("Falling back to MockPubSub implementation")
                return MockPubSub(host, router_type, cache_size, strict_signing, sign_key)
    else:
        raise ValueError(f"Unknown router type: {router_type}")

class MockPubSub:
    """
    Mock implementation of libp2p PubSub for when the real version is not available.
    
    This implementation provides a fully functional PubSub system that can be used
    for testing and development when the actual libp2p implementation is not available.
    It follows the same interface as the real PubSub implementations to ensure
    compatibility.
    """
    
    def __init__(self, host, router_type="gossipsub", cache_size=None, strict_signing=True, sign_key=None):
        """Initialize the mock PubSub implementation."""
        self.host = host
        self.router_type = router_type
        self.cache_size = cache_size or 128
        self.strict_signing = strict_signing
        self.sign_key = sign_key
        
        # Subscription management
        self.subscriptions = {}  # topic -> [handlers]
        self.topics = {}         # topic -> Set(peer_ids)
        self.topics_by_peer = {} # peer_id -> Set(topics)
        
        # Message cache for deduplication and history
        self.message_cache = {}  # msg_id -> { message, topics, timestamp }
        self.message_history = {} # topic -> [msg_ids]
        
        self.started = False
        logger.warning("Using mock PubSub implementation - limited functionality")
        
    async def start(self):
        """Start the pubsub service."""
        self.started = True
        logger.debug(f"Started mock {self.router_type} pubsub service")
        return True
        
    async def stop(self):
        """Stop the pubsub service."""
        self.started = False
        self.subscriptions.clear()
        self.topics.clear()
        self.topics_by_peer.clear()
        self.message_cache.clear()
        self.message_history.clear()
        logger.debug("Stopped mock pubsub service")
        return True
        
    async def publish(self, topic_id, data):
        """Publish data to a topic (async interface).
        
        Args:
            topic_id: The topic to publish to
            data: The data to publish (bytes or string)
            
        Returns:
            True if published successfully, False otherwise
        """
        if not self.started:
            logger.warning("Cannot publish: pubsub service not started")
            return False
            
        if not validate_pubsub_topic(topic_id):
            logger.warning(f"Invalid topic: {topic_id}")
            return False
            
        # Format message
        peer_id = str(self.host.get_id()) if hasattr(self.host, "get_id") else "unknown"
        message = format_pubsub_message(data, peer_id)
        
        # Add topicIDs field for compatibility with libp2p message format
        message["topicIDs"] = [topic_id]
        
        # Generate message ID
        import hashlib
        msg_id = hashlib.sha256(message["data"] + message["seqno"]).hexdigest()
        
        # Store in message cache
        self.message_cache[msg_id] = {
            "message": message,
            "topics": [topic_id],
            "timestamp": time.time()
        }
        
        # Add to message history for the topic
        if topic_id not in self.message_history:
            self.message_history[topic_id] = []
        self.message_history[topic_id].append(msg_id)
        
        # Trim message history if it exceeds cache size
        if len(self.message_history[topic_id]) > self.cache_size:
            # Remove oldest messages
            old_msg_ids = self.message_history[topic_id][:-self.cache_size]
            self.message_history[topic_id] = self.message_history[topic_id][-self.cache_size:]
            
            # Clean up message cache
            for old_id in old_msg_ids:
                if old_id in self.message_cache:
                    del self.message_cache[old_id]
        
        # Call local subscribers
        if topic_id in self.subscriptions:
            for handler in self.subscriptions[topic_id]:
                try:
                    # Check if handler is async
                    if anyio.iscoroutinefunction(handler):
                        # Schedule as task to prevent blocking
                        anyio.create_task(handler(message))
                    else:
                        # Call synchronously
                        handler(message)
                except Exception as e:
                    logger.error(f"Error in subscription handler: {e}")
        
        logger.debug(f"Published message to topic: {topic_id}")
        return True
        
    async def subscribe(self, topic_id, handler):
        """Subscribe to a topic with a handler function (async interface).
        
        This method supports both async and sync usage patterns.
        
        Args:
            topic_id: The topic to subscribe to
            handler: Function to handle incoming messages
            
        Returns:
            True if subscription was successful, False otherwise
        """
        if not validate_pubsub_topic(topic_id):
            logger.warning(f"Invalid topic: {topic_id}")
            return False
            
        # Add to subscriptions
        if topic_id not in self.subscriptions:
            self.subscriptions[topic_id] = []
            
        self.subscriptions[topic_id].append(handler)
        
        # Update topic tracking for this peer
        local_peer_id = str(self.host.get_id()) if hasattr(self.host, "get_id") else "local"
        
        if topic_id not in self.topics:
            self.topics[topic_id] = set()
        self.topics[topic_id].add(local_peer_id)
        
        if local_peer_id not in self.topics_by_peer:
            self.topics_by_peer[local_peer_id] = set()
        self.topics_by_peer[local_peer_id].add(topic_id)
        
        logger.debug(f"Subscribed to topic: {topic_id}")
        return True
        
    async def unsubscribe(self, topic_id, handler=None):
        """Unsubscribe from a topic (async interface).
        
        Args:
            topic_id: The topic to unsubscribe from
            handler: Optional specific handler to unsubscribe
            
        Returns:
            True if unsubscribed successfully, False otherwise
        """
        if topic_id not in self.subscriptions:
            logger.warning(f"Not subscribed to topic: {topic_id}")
            return False
            
        if handler is None:
            # Unsubscribe from all handlers for this topic
            del self.subscriptions[topic_id]
        else:
            # Unsubscribe from specific handler
            if handler in self.subscriptions[topic_id]:
                self.subscriptions[topic_id].remove(handler)
                
            # Clean up empty subscription list
            if not self.subscriptions[topic_id]:
                del self.subscriptions[topic_id]
        
        # If we have no more handlers for this topic, update peer tracking
        if topic_id not in self.subscriptions:
            local_peer_id = str(self.host.get_id()) if hasattr(self.host, "get_id") else "local"
            
            # Remove peer from topic
            if topic_id in self.topics and local_peer_id in self.topics[topic_id]:
                self.topics[topic_id].remove(local_peer_id)
                
                # Clean up empty topics
                if not self.topics[topic_id]:
                    del self.topics[topic_id]
            
            # Remove topic from peer
            if local_peer_id in self.topics_by_peer and topic_id in self.topics_by_peer[local_peer_id]:
                self.topics_by_peer[local_peer_id].remove(topic_id)
                
                # Clean up empty peer entries
                if not self.topics_by_peer[local_peer_id]:
                    del self.topics_by_peer[local_peer_id]
                
        logger.debug(f"Unsubscribed from topic: {topic_id}")
        return True
        
    def get_topics(self):
        """Get list of subscribed topics."""
        return list(self.subscriptions.keys())
    
    def get_peers(self, topic_id=None):
        """
        Get peers subscribed to a topic or all peers if topic is None.
        
        Args:
            topic_id: Optional topic to get peers for
            
        Returns:
            List of peer IDs
        """
        if topic_id is None:
            # Get all peers across all topics
            all_peers = set()
            for topic, peers in self.topics.items():
                all_peers.update(peers)
            return list(all_peers)
        elif topic_id in self.topics:
            return list(self.topics[topic_id])
        else:
            return []
            
    def get_peers_subscribed(self, topic_id):
        """
        Get peers subscribed to a topic.
        
        This is an alias for get_peers with a specific topic,
        provided for compatibility with libp2p PubSub.
        
        Args:
            topic_id: The topic to get peers for
            
        Returns:
            List of peer IDs
        """
        return self.get_peers(topic_id)
        
    def get_topics_for_peer(self, peer_id):
        """
        Get topics a peer is subscribed to.
        
        Args:
            peer_id: The peer ID to get topics for
            
        Returns:
            List of topics
        """
        if peer_id in self.topics_by_peer:
            return list(self.topics_by_peer[peer_id])
        else:
            return []
            
    def add_peer_to_topic(self, topic_id, peer_id):
        """
        Add a peer to a topic's subscriber list.
        
        This is used for tracking remote peers' topic subscriptions.
        
        Args:
            topic_id: The topic to add the peer to
            peer_id: The peer ID to add
            
        Returns:
            True if added, False otherwise
        """
        if not validate_pubsub_topic(topic_id):
            return False
            
        # Add peer to topic
        if topic_id not in self.topics:
            self.topics[topic_id] = set()
        self.topics[topic_id].add(peer_id)
        
        # Add topic to peer
        if peer_id not in self.topics_by_peer:
            self.topics_by_peer[peer_id] = set()
        self.topics_by_peer[peer_id].add(topic_id)
        
        return True
        
    def remove_peer_from_topic(self, topic_id, peer_id):
        """
        Remove a peer from a topic's subscriber list.
        
        Args:
            topic_id: The topic to remove the peer from
            peer_id: The peer ID to remove
            
        Returns:
            True if removed, False otherwise
        """
        # Remove peer from topic
        if topic_id in self.topics and peer_id in self.topics[topic_id]:
            self.topics[topic_id].remove(peer_id)
            
            # Clean up empty topics
            if not self.topics[topic_id]:
                del self.topics[topic_id]
                
            # Remove topic from peer
            if peer_id in self.topics_by_peer and topic_id in self.topics_by_peer[peer_id]:
                self.topics_by_peer[peer_id].remove(topic_id)
                
                # Clean up empty peer entries
                if not self.topics_by_peer[peer_id]:
                    del self.topics_by_peer[peer_id]
                    
            return True
        
        return False
        
    def get_message_history(self, topic_id, limit=None):
        """
        Get recent messages for a topic.
        
        Args:
            topic_id: The topic to get messages for
            limit: Maximum number of messages to return
            
        Returns:
            List of messages, newest first
        """
        if topic_id not in self.message_history:
            return []
            
        # Get message IDs from history, newest first
        msg_ids = list(reversed(self.message_history[topic_id]))
        
        # Apply limit if specified
        if limit is not None:
            msg_ids = msg_ids[:limit]
            
        # Retrieve messages from cache
        messages = []
        for msg_id in msg_ids:
            if msg_id in self.message_cache:
                messages.append(self.message_cache[msg_id]["message"])
                
        return messages