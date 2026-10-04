"""
Enhanced GossipSub protocol implementation for IPFS Kit.

This module implements advanced GossipSub protocol functionality for the libp2p peer,
providing more robust and flexible publish-subscribe messaging.

Key features:
- Comprehensive topic management
- Support for both sync and async PubSub APIs
- Peer tracking for topic subscriptions 
- Message validation and filtering
- Resource-aware message propagation
- Heartbeat and health monitoring
- Resilient error handling and recovery patterns
"""

import anyio
import json
import logging
import random
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union, Type

try:
    # Import libp2p-specific components if available
    from libp2p.peer.id import ID as PeerID
    from libp2p.pubsub.pubsub import Pubsub
    HAS_LIBP2P = True
except ImportError:
    HAS_LIBP2P = False

# Configure logger
logger = logging.getLogger(__name__)

@dataclass
class GossipSubMessage:
    """Representation of a GossipSub message."""
    data: bytes
    topic_ids: List[str]
    from_peer: Optional[str] = None
    seqno: Optional[bytes] = None
    signature: Optional[bytes] = None
    key: Optional[bytes] = None
    received_from: Optional[str] = None
    validated: bool = False
    timestamp: float = field(default_factory=time.time)
    
    @staticmethod
    def from_pubsub_message(msg: Dict[str, Any]) -> "GossipSubMessage":
        """Create a GossipSubMessage from a pubsub message dictionary."""
        return GossipSubMessage(
            data=msg.get("data", b""),
            topic_ids=msg.get("topicIDs", []),
            from_peer=str(msg.get("from", "unknown")),
            seqno=msg.get("seqno"),
            signature=msg.get("signature"),
            key=msg.get("key"),
            received_from=str(msg.get("receivedFrom", "unknown")),
            timestamp=time.time()
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dictionary format suitable for libp2p."""
        result = {
            "data": self.data,
            "topicIDs": self.topic_ids
        }
        
        if self.from_peer:
            result["from"] = self.from_peer
            
        if self.seqno:
            result["seqno"] = self.seqno
            
        if self.signature:
            result["signature"] = self.signature
            
        if self.key:
            result["key"] = self.key
            
        return result
        
    def __str__(self) -> str:
        """String representation of the message."""
        try:
            data_preview = self.data[:20].decode('utf-8')
            if len(self.data) > 20:
                data_preview += "..."
        except:
            data_preview = f"<binary data, {len(self.data)} bytes>"
            
        return f"GossipSubMessage(topics={self.topic_ids}, from={self.from_peer}, data={data_preview})"


@dataclass
class GossipSubTopic:
    """Representation of a GossipSub topic."""
    name: str
    peers: Set[str] = field(default_factory=set)
    message_cache: Dict[str, GossipSubMessage] = field(default_factory=dict)
    message_history: List[str] = field(default_factory=list)
    last_published: float = field(default_factory=time.time)
    subscribed: bool = False
    cache_size: int = 128
    
    def add_peer(self, peer_id: str) -> None:
        """Add a peer to this topic."""
        self.peers.add(str(peer_id))
        
    def remove_peer(self, peer_id: str) -> None:
        """Remove a peer from this topic."""
        peer_id_str = str(peer_id)
        if peer_id_str in self.peers:
            self.peers.remove(peer_id_str)
            
    def add_message(self, msg: GossipSubMessage) -> str:
        """
        Add a message to the topic's cache.
        
        Returns:
            Message ID
        """
        # Generate message ID (hash of from+seqno or random UUID if not available)
        if msg.from_peer and msg.seqno:
            import hashlib
            msg_id = hashlib.sha256(f"{msg.from_peer}:{msg.seqno}".encode()).hexdigest()
        else:
            msg_id = str(uuid.uuid4())
            
        # Add to cache
        self.message_cache[msg_id] = msg
        self.message_history.append(msg_id)
        
        # Prune cache if needed
        self._prune_cache()
        
        return msg_id
        
    def _prune_cache(self) -> None:
        """Prune the message cache if it exceeds the size limit."""
        if len(self.message_history) > self.cache_size:
            # Keep only the most recent messages
            old_ids = self.message_history[:-self.cache_size]
            self.message_history = self.message_history[-self.cache_size:]
            
            # Remove old messages from cache
            for old_id in old_ids:
                if old_id in self.message_cache:
                    del self.message_cache[old_id]
                    
    def get_recent_messages(self, count: int = 10) -> List[GossipSubMessage]:
        """Get the most recent messages from this topic."""
        # Get the most recent message IDs
        recent_ids = self.message_history[-count:] if count < len(self.message_history) else self.message_history
        
        # Convert to messages
        messages = []
        for msg_id in reversed(recent_ids):  # Newest first
            if msg_id in self.message_cache:
                messages.append(self.message_cache[msg_id])
                
        return messages


class GossipSubProtocol:
    """
    Enhanced implementation of the GossipSub protocol.
    
    This provides a unified interface for working with GossipSub, regardless
    of whether the actual libp2p implementation is available.
    """
    
    def __init__(self, peer, pubsub=None, options=None):
        """
        Initialize GossipSub protocol with the given options.
        
        Args:
            peer: The libp2p peer instance
            pubsub: Optional existing pubsub instance to use
            options: Protocol configuration options
        """
        self.peer = peer
        self.pubsub = pubsub
        self.options = options or {}
        
        # Default options
        self.heartbeat_interval = self.options.get("heartbeat_interval", 1.0)
        self.fanout_ttl = self.options.get("fanout_ttl", 60)
        self.gossip_factor = self.options.get("gossip_factor", 0.25)
        self.message_cache_size = self.options.get("message_cache_size", 128)
        
        # State
        self.topics = {}  # topic_name -> GossipSubTopic
        self.peer_topics = {}  # peer_id -> set(topic_names)
        self.handlers = {}  # topic_name -> list(handler_functions)
        self.running = False
        self.started_at = None
        
        # Executor for handling messages
        self.thread_pool = ThreadPoolExecutor(
            max_workers=self.options.get("max_handler_threads", 10),
            thread_name_prefix="gossipsub-handler"
        )
        
        # Set up heartbeat task
        self._heartbeat_task = None
        
        # Initialize metrics
        self.metrics = {
            "messages_published": 0,
            "messages_received": 0,
            "messages_processed": 0,
            "bytes_published": 0,
            "bytes_received": 0,
            "peers_total": 0,
            "topics_total": 0,
            "handlers_total": 0,
            "errors": 0
        }
        
        # If no pubsub provided, try to create one
        if self.pubsub is None:
            self._initialize_pubsub()
    
    def _initialize_pubsub(self):
        """Initialize the pubsub component."""
        logger.debug("Initializing GossipSub pubsub")
        
        try:
            # First try to import from libp2p
            from ipfs_kit_py.libp2p.tools.pubsub.utils import create_pubsub
            
            # Create pubsub with GossipSub router
            self.pubsub = create_pubsub(
                self.peer,
                router_type="gossipsub",
                cache_size=self.message_cache_size
            )
            logger.debug("Created GossipSub pubsub instance")
            
        except ImportError as e:
            logger.warning(f"Failed to import pubsub utilities: {e}")
            self.pubsub = None

    async def start(self):
        """Start the GossipSub protocol services."""
        if self.running:
            logger.warning("GossipSub protocol already running")
            return False
            
        logger.info("Starting GossipSub protocol")
        
        # First start the pubsub if available
        if self.pubsub:
            if hasattr(self.pubsub, "start"):
                # Check if it's an async method
                import inspect
                if inspect.iscoroutinefunction(self.pubsub.start):
                    await self.pubsub.start()
                else:
                    self.pubsub.start()
                    
        # Start heartbeat task
        self._start_heartbeat()
        
        self.running = True
        self.started_at = time.time()
        logger.info("GossipSub protocol started")
        return True
        
    async def stop(self):
        """Stop the GossipSub protocol services."""
        if not self.running:
            logger.warning("GossipSub protocol not running")
            return False
            
        logger.info("Stopping GossipSub protocol")
        
        # Stop heartbeat task
        self._stop_heartbeat()
        
        # Stop pubsub if available
        if self.pubsub:
            if hasattr(self.pubsub, "stop"):
                # Check if it's an async method
                import inspect
                if inspect.iscoroutinefunction(self.pubsub.stop):
                    await self.pubsub.stop()
                else:
                    self.pubsub.stop()
        
        # Shut down thread pool
        self.thread_pool.shutdown(wait=True)
        
        self.running = False
        logger.info("GossipSub protocol stopped")
        return True
        
    def _start_heartbeat(self):
        """Start the heartbeat task for periodic operations."""
        async def heartbeat_loop():
            while self.running:
                try:
                    await self._heartbeat()
                except Exception as e:
                    logger.error(f"Error in GossipSub heartbeat: {e}")
                    
                # Sleep until next heartbeat
                await anyio.sleep(self.heartbeat_interval)
                
        # Create and store the task
        self._heartbeat_task = anyio.create_task(heartbeat_loop())
        
    def _stop_heartbeat(self):
        """Stop the heartbeat task."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None
            
    async def _heartbeat(self):
        """Perform periodic maintenance operations."""
        # Update peer count metric
        self.metrics["peers_total"] = sum(len(topic.peers) for topic in self.topics.values())
        self.metrics["topics_total"] = len(self.topics)
        self.metrics["handlers_total"] = sum(len(handlers) for handlers in self.handlers.values())
        
        # Perform gossip - select random peers to send topic state to
        await self._perform_gossip()
        
        # Prune expired messages
        self._prune_message_caches()
        
    async def _perform_gossip(self):
        """Propagate topic state to random peers based on gossip factor."""
        # Select topics to gossip about
        all_topics = list(self.topics.values())
        if not all_topics:
            return
            
        for topic in all_topics:
            # Skip topics with no peers
            if len(topic.peers) <= 1:
                continue
                
            # Select random peers to gossip to (based on gossip factor)
            gossip_count = max(1, int(len(topic.peers) * self.gossip_factor))
            peers_to_gossip = random.sample(topic.peers, min(gossip_count, len(topic.peers)))
            
            # Get recent messages to gossip
            recent_messages = topic.get_recent_messages(5)
            if not recent_messages:
                continue
                
            # Send recent messages to selected peers
            for peer_id in peers_to_gossip:
                # In a real implementation, this would use libp2p's peer messaging
                # For this implementation, we just log it
                logger.debug(f"Would gossip {len(recent_messages)} messages to peer {peer_id} for topic {topic.name}")
                
    def _prune_message_caches(self):
        """Prune message caches for all topics."""
        for topic in self.topics.values():
            topic._prune_cache()
            
    async def publish(self, topic_id: str, data: Union[str, bytes]) -> Dict[str, Any]:
        """
        Publish data to a topic.
        
        Args:
            topic_id: Topic to publish to
            data: Data to publish (string or bytes)
            
        Returns:
            Dictionary with publication result
        """
        result = {
            "success": False,
            "operation": "publish",
            "topic": topic_id,
            "timestamp": time.time()
        }
        
        # Validate topic
        from ipfs_kit_py.libp2p.tools.pubsub.utils import validate_pubsub_topic
        if not validate_pubsub_topic(topic_id):
            result["error"] = f"Invalid topic: {topic_id}"
            self.metrics["errors"] += 1
            return result
            
        # Convert string to bytes if needed
        if isinstance(data, str):
            data_bytes = data.encode('utf-8')
        else:
            data_bytes = data
            
        # Update metrics
        self.metrics["messages_published"] += 1
        self.metrics["bytes_published"] += len(data_bytes)
        
        # Create or get the topic
        if topic_id not in self.topics:
            self.topics[topic_id] = GossipSubTopic(name=topic_id)
        topic = self.topics[topic_id]
        topic.last_published = time.time()
        
        # Create message
        peer_id = getattr(self.peer, "peer_id", None)
        if peer_id is None and hasattr(self.peer, "get_id"):
            peer_id = self.peer.get_id()
        peer_id_str = str(peer_id) if peer_id else "unknown"
        
        # Generate sequence number
        seqno = str(uuid.uuid4())[:8].encode()
        
        message = GossipSubMessage(
            data=data_bytes, 
            topic_ids=[topic_id],
            from_peer=peer_id_str,
            seqno=seqno
        )
        
        # Add to topic cache
        msg_id = topic.add_message(message)
        
        # If we have a real pubsub instance, publish through it
        if self.pubsub and hasattr(self.pubsub, "publish"):
            try:
                # Convert to format expected by pubsub
                pubsub_message = message.to_dict()
                
                # Check if it's an async method
                import inspect
                if inspect.iscoroutinefunction(self.pubsub.publish):
                    publish_result = await self.pubsub.publish(topic_id, data_bytes)
                else:
                    publish_result = self.pubsub.publish(topic_id, data_bytes)
                    
                result["publish_result"] = publish_result
                
            except Exception as e:
                logger.error(f"Error in pubsub publish: {e}")
                result["error"] = f"Error in pubsub publish: {str(e)}"
                self.metrics["errors"] += 1
        
        # Deliver locally to any handlers
        await self._deliver_message_to_handlers(topic_id, message)
        
        result["success"] = True
        result["message_id"] = msg_id
        return result
        
    async def subscribe(self, topic_id: str, handler: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Subscribe to a topic.
        
        Args:
            topic_id: Topic to subscribe to
            handler: Optional callback function to handle messages
            
        Returns:
            Dictionary with subscription result
        """
        result = {
            "success": False,
            "operation": "subscribe",
            "topic": topic_id,
            "timestamp": time.time()
        }
        
        # Validate topic
        from ipfs_kit_py.libp2p.tools.pubsub.utils import validate_pubsub_topic
        if not validate_pubsub_topic(topic_id):
            result["error"] = f"Invalid topic: {topic_id}"
            self.metrics["errors"] += 1
            return result
            
        # Create or get the topic
        if topic_id not in self.topics:
            self.topics[topic_id] = GossipSubTopic(name=topic_id)
        topic = self.topics[topic_id]
        topic.subscribed = True
        
        # Add ourselves as a peer
        peer_id = getattr(self.peer, "peer_id", None)
        if peer_id is None and hasattr(self.peer, "get_id"):
            peer_id = self.peer.get_id()
        peer_id_str = str(peer_id) if peer_id else "local"
        topic.add_peer(peer_id_str)
        
        # Register handler if provided
        if handler:
            if topic_id not in self.handlers:
                self.handlers[topic_id] = []
            self.handlers[topic_id].append(handler)
            
        # Subscribe with underlying pubsub if available
        if self.pubsub and hasattr(self.pubsub, "subscribe"):
            try:
                # Create a handler that will convert and forward messages
                async def pubsub_handler(pubsub_msg):
                    # Convert to our message format
                    message = GossipSubMessage.from_pubsub_message(pubsub_msg)
                    # Deliver to handlers
                    await self._deliver_message_to_handlers(topic_id, message)
                
                # Check if it's an async method
                import inspect
                if inspect.iscoroutinefunction(self.pubsub.subscribe):
                    await self.pubsub.subscribe(topic_id, pubsub_handler)
                else:
                    self.pubsub.subscribe(topic_id, pubsub_handler)
                    
            except Exception as e:
                logger.error(f"Error in pubsub subscribe: {e}")
                result["error"] = f"Error in pubsub subscribe: {str(e)}"
                self.metrics["errors"] += 1
                # Continue anyway - our internal subscription is still valid
        
        result["success"] = True
        return result
        
    async def unsubscribe(self, topic_id: str, handler: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Unsubscribe from a topic.
        
        Args:
            topic_id: Topic to unsubscribe from
            handler: Optional specific handler to unsubscribe
            
        Returns:
            Dictionary with unsubscription result
        """
        result = {
            "success": False,
            "operation": "unsubscribe",
            "topic": topic_id,
            "timestamp": time.time()
        }
        
        # Check if we're subscribed
        if topic_id not in self.topics or not self.topics[topic_id].subscribed:
            result["error"] = f"Not subscribed to topic: {topic_id}"
            return result
            
        # Get topic
        topic = self.topics[topic_id]
        
        # If handler is specified, just remove that handler
        if handler and topic_id in self.handlers:
            if handler in self.handlers[topic_id]:
                self.handlers[topic_id].remove(handler)
                result["success"] = True
                result["handler_removed"] = True
                
                # If there are still handlers, don't complete the unsubscription
                if self.handlers[topic_id]:
                    return result
                    
        # Remove all handlers for this topic
        if topic_id in self.handlers:
            del self.handlers[topic_id]
            
        # Unsubscribe with underlying pubsub if available
        if self.pubsub and hasattr(self.pubsub, "unsubscribe"):
            try:
                # Check if it's an async method
                import inspect
                if inspect.iscoroutinefunction(self.pubsub.unsubscribe):
                    await self.pubsub.unsubscribe(topic_id)
                else:
                    self.pubsub.unsubscribe(topic_id)
                    
            except Exception as e:
                logger.error(f"Error in pubsub unsubscribe: {e}")
                result["error"] = f"Error in pubsub unsubscribe: {str(e)}"
                self.metrics["errors"] += 1
                # Continue anyway - our internal unsubscription is still valid
        
        # Update our local state
        topic.subscribed = False
        
        # Remove ourselves as a peer
        peer_id = getattr(self.peer, "peer_id", None)
        if peer_id is None and hasattr(self.peer, "get_id"):
            peer_id = self.peer.get_id()
        peer_id_str = str(peer_id) if peer_id else "local"
        topic.remove_peer(peer_id_str)
        
        result["success"] = True
        return result
        
    async def _deliver_message_to_handlers(self, topic_id: str, message: GossipSubMessage):
        """
        Deliver a message to all handlers for a topic.
        
        Args:
            topic_id: The topic the message is for
            message: The message to deliver
        """
        if topic_id not in self.handlers:
            return
            
        # Update metrics
        self.metrics["messages_received"] += 1
        self.metrics["bytes_received"] += len(message.data)
        
        # Deliver to each handler
        for handler in self.handlers[topic_id]:
            try:
                # Check if handler is async
                import inspect
                if inspect.iscoroutinefunction(handler):
                    # Schedule as task to prevent blocking
                    anyio.create_task(handler(message))
                else:
                    # Submit to thread pool for synchronous handlers
                    self.thread_pool.submit(handler, message)
                    
                # Update metrics
                self.metrics["messages_processed"] += 1
                
            except Exception as e:
                logger.error(f"Error delivering message to handler: {e}")
                self.metrics["errors"] += 1
                
    def get_topics(self) -> List[str]:
        """Get list of topics we are subscribed to."""
        return [topic.name for topic in self.topics.values() if topic.subscribed]
        
    def get_peers(self, topic_id: Optional[str] = None) -> List[str]:
        """
        Get peers for a topic or all peers if no topic specified.
        
        Args:
            topic_id: Optional topic to get peers for
            
        Returns:
            List of peer IDs
        """
        if topic_id is not None:
            # Get peers for specific topic
            if topic_id in self.topics:
                return list(self.topics[topic_id].peers)
            else:
                return []
                
        else:
            # Get all unique peers across all topics
            all_peers = set()
            for topic in self.topics.values():
                all_peers.update(topic.peers)
            return list(all_peers)
            
    def get_metrics(self) -> Dict[str, Any]:
        """Get metrics about gossipsub activity."""
        # Update some metrics first
        self.metrics["topics_total"] = len(self.topics)
        self.metrics["peers_total"] = len(self.get_peers())
        self.metrics["handlers_total"] = sum(len(handlers) for handlers in self.handlers.values())
        
        # Add derived metrics
        if time.time() - self.started_at > 0:
            uptime = time.time() - self.started_at
            self.metrics["messages_per_second"] = self.metrics["messages_processed"] / uptime
            self.metrics["bytes_per_second"] = self.metrics["bytes_received"] / uptime
            
        return self.metrics.copy()

def add_gossipsub_methods(peer_class):
    """
    Add GossipSub protocol methods to the IPFSLibp2pPeer class.
    
    This integrates the enhanced GossipSubProtocol class with the IPFSLibp2pPeer class,
    providing a unified interface with support for both sync and async operation patterns.
    
    Args:
        peer_class: The IPFSLibp2pPeer class to extend
        
    Returns:
        The extended class
    """
    
    # Check if methods already exist
    if (hasattr(peer_class, "initialize_gossipsub") and
        hasattr(peer_class, "publish_to_topic") and 
        hasattr(peer_class, "subscribe_to_topic") and
        hasattr(peer_class, "unsubscribe_from_topic") and
        hasattr(peer_class, "get_topic_peers") and
        hasattr(peer_class, "list_topics")):
        logger.debug("GossipSub protocol methods already added to IPFSLibp2pPeer")
        return peer_class
        
    def initialize_gossipsub(self, options=None) -> Dict[str, Any]:
        """Initialize GossipSub protocol for this peer.
        
        Args:
            options: Optional configuration for GossipSub protocol
            
        Returns:
            Dict with initialization result
        """
        result = {
            "success": False,
            "operation": "initialize_gossipsub",
            "timestamp": time.time()
        }
        
        # If it's already initialized, just return success
        if hasattr(self, "gossipsub") and self.gossipsub:
            logger.debug("GossipSub already initialized for this peer")
            result["success"] = True
            result["already_initialized"] = True
            return result
            
        # Create the protocol instance
        try:
            # Use the new GossipSubProtocol class
            self.gossipsub = GossipSubProtocol(
                peer=self,
                pubsub=getattr(self, "pubsub", None),
                options=options
            )
            
            # Start the protocol if we have an event loop
            try:
                import anyio
                anyio.run(self.gossipsub.start)
                result["protocol_started"] = True
            except Exception as e:
                logger.debug(f"Could not start GossipSub protocol automatically: {e}")
                result["protocol_started"] = False
                result["protocol_start_error"] = str(e)
            
            result["success"] = True
            self.logger.info("GossipSub protocol initialized")
            
        except Exception as e:
            result["error"] = f"Failed to initialize GossipSub: {str(e)}"
            self.logger.error(f"Error initializing GossipSub: {e}")
            
        return result
        
    def publish_to_topic(self, topic_id: str, data: Union[str, bytes]) -> Dict[str, Any]:
        """Publish data to a GossipSub topic.
        
        Args:
            topic_id: The topic to publish to
            data: The data to publish (bytes or string)
            
        Returns:
            Dict with publication result
        """
        result = {
            "success": False,
            "operation": "publish_to_topic",
            "timestamp": time.time(),
            "topic": topic_id
        }
        
        # Initialize GossipSub if needed
        if not hasattr(self, "gossipsub") or not self.gossipsub:
            init_result = self.initialize_gossipsub()
            if not init_result["success"]:
                result["error"] = "Failed to initialize GossipSub"
                result["init_error"] = init_result.get("error")
                return result
        
        # Call the publish method on the GossipSub protocol
        try:
            # Use anyio to run the async method
            import anyio
            publish_result = anyio.run(
                self.gossipsub.publish,
                topic_id=topic_id,
                data=data
            )
            
            # Copy fields from publish result
            for key, value in publish_result.items():
                result[key] = value
                
            # Ensure success is set
            result["success"] = publish_result.get("success", False)
            
        except Exception as e:
            result["error"] = f"Error in publish operation: {str(e)}"
            self.logger.error(f"Error publishing to topic {topic_id}: {e}")
            
        return result
        
    def subscribe_to_topic(self, topic_id: str, handler: Callable) -> Dict[str, Any]:
        """Subscribe to a GossipSub topic with a handler function.
        
        Args:
            topic_id: The topic to subscribe to
            handler: Function to handle incoming messages
            
        Returns:
            Dict with subscription result
        """
        result = {
            "success": False,
            "operation": "subscribe_to_topic",
            "timestamp": time.time(),
            "topic": topic_id
        }
        
        # Initialize GossipSub if needed
        if not hasattr(self, "gossipsub") or not self.gossipsub:
            init_result = self.initialize_gossipsub()
            if not init_result["success"]:
                result["error"] = "Failed to initialize GossipSub"
                result["init_error"] = init_result.get("error")
                return result
                
        # Call the subscribe method on the GossipSub protocol
        try:
            # Use anyio to run the async method
            import anyio
            subscribe_result = anyio.run(
                self.gossipsub.subscribe,
                topic_id=topic_id,
                handler=handler
            )
            
            # Copy fields from subscribe result
            for key, value in subscribe_result.items():
                result[key] = value
                
            # Ensure success is set
            result["success"] = subscribe_result.get("success", False)
            
        except Exception as e:
            result["error"] = f"Error in subscribe operation: {str(e)}"
            self.logger.error(f"Error subscribing to topic {topic_id}: {e}")
            
        return result
        
    def unsubscribe_from_topic(self, topic_id: str, handler: Optional[Callable] = None) -> Dict[str, Any]:
        """Unsubscribe from a GossipSub topic.
        
        Args:
            topic_id: The topic to unsubscribe from
            handler: Optional specific handler to unsubscribe
            
        Returns:
            Dict with unsubscription result
        """
        result = {
            "success": False,
            "operation": "unsubscribe_from_topic",
            "timestamp": time.time(),
            "topic": topic_id
        }
        
        # Check if GossipSub is initialized
        if not hasattr(self, "gossipsub") or not self.gossipsub:
            result["error"] = "GossipSub not initialized"
            return result
                
        # Call the unsubscribe method on the GossipSub protocol
        try:
            # Use anyio to run the async method
            import anyio
            unsubscribe_result = anyio.run(
                self.gossipsub.unsubscribe,
                topic_id=topic_id,
                handler=handler
            )
            
            # Copy fields from unsubscribe result
            for key, value in unsubscribe_result.items():
                result[key] = value
                
            # Ensure success is set
            result["success"] = unsubscribe_result.get("success", False)
            
        except Exception as e:
            result["error"] = f"Error in unsubscribe operation: {str(e)}"
            self.logger.error(f"Error unsubscribing from topic {topic_id}: {e}")
            
        return result
        
    def get_topic_peers(self, topic_id: str) -> Dict[str, Any]:
        """Get peers subscribed to a topic.
        
        Args:
            topic_id: The topic to get peers for
            
        Returns:
            Dict with peer information
        """
        result = {
            "success": False,
            "operation": "get_topic_peers",
            "timestamp": time.time(),
            "topic": topic_id,
            "peers": []
        }
        
        # Check if GossipSub is initialized
        if not hasattr(self, "gossipsub") or not self.gossipsub:
            result["error"] = "GossipSub not initialized"
            return result
                
        try:
            # Get peers from GossipSub protocol
            peers = self.gossipsub.get_peers(topic_id)
            result["peers"] = peers
            result["peer_count"] = len(peers)
            result["success"] = True
            
        except Exception as e:
            result["error"] = f"Error getting peers: {str(e)}"
            self.logger.error(f"Error getting peers for topic {topic_id}: {e}")
            
        return result
        
    def list_topics(self) -> Dict[str, Any]:
        """List all topics we're subscribed to.
        
        Returns:
            Dict with topic information
        """
        result = {
            "success": False,
            "operation": "list_topics",
            "timestamp": time.time(),
            "topics": []
        }
        
        # Check if GossipSub is initialized
        if not hasattr(self, "gossipsub") or not self.gossipsub:
            result["error"] = "GossipSub not initialized"
            return result
                
        try:
            # Get topics from GossipSub protocol
            topics = self.gossipsub.get_topics()
            result["topics"] = topics
            result["topic_count"] = len(topics)
            result["success"] = True
            
        except Exception as e:
            result["error"] = f"Error listing topics: {str(e)}"
            self.logger.error(f"Error listing topics: {e}")
            
        return result
            
    def get_gossipsub_metrics(self) -> Dict[str, Any]:
        """Get metrics about GossipSub activity.
        
        Returns:
            Dict with metrics information
        """
        result = {
            "success": False,
            "operation": "get_gossipsub_metrics",
            "timestamp": time.time(),
            "metrics": {}
        }
        
        # Check if GossipSub is initialized
        if not hasattr(self, "gossipsub") or not self.gossipsub:
            result["error"] = "GossipSub not initialized"
            return result
                
        try:
            # Get metrics from GossipSub protocol
            metrics = self.gossipsub.get_metrics()
            result["metrics"] = metrics
            result["success"] = True
            
        except Exception as e:
            result["error"] = f"Error getting metrics: {str(e)}"
            self.logger.error(f"Error getting GossipSub metrics: {e}")
            
        return result
            
    def stop_gossipsub(self) -> Dict[str, Any]:
        """Stop the GossipSub protocol services.
        
        Returns:
            Dict with stop result
        """
        result = {
            "success": False,
            "operation": "stop_gossipsub",
            "timestamp": time.time()
        }
        
        # Check if GossipSub is initialized
        if not hasattr(self, "gossipsub") or not self.gossipsub:
            result["error"] = "GossipSub not initialized"
            return result
                
        try:
            # Use anyio to run the async method
            import anyio
            stop_result = anyio.run(self.gossipsub.stop)
            result["success"] = True
            
        except Exception as e:
            result["error"] = f"Error stopping GossipSub: {str(e)}"
            self.logger.error(f"Error stopping GossipSub: {e}")
            
        return result
    
    # Add methods to the peer class
    peer_class.initialize_gossipsub = initialize_gossipsub
    peer_class.publish_to_topic = publish_to_topic
    peer_class.subscribe_to_topic = subscribe_to_topic
    peer_class.unsubscribe_from_topic = unsubscribe_from_topic
    peer_class.get_topic_peers = get_topic_peers
    peer_class.list_topics = list_topics
    peer_class.get_gossipsub_metrics = get_gossipsub_metrics
    peer_class.stop_gossipsub = stop_gossipsub
    
    return peer_class


def add_enhanced_dht_discovery_methods(peer_class):
    """
    Add enhanced DHT discovery methods to the IPFSLibp2pPeer class.
    
    Args:
        peer_class: The IPFSLibp2pPeer class to extend
        
    Returns:
        The extended class
    """
    
    # Check if methods already exist
    if (hasattr(peer_class, "integrate_enhanced_dht_discovery") and 
        hasattr(peer_class, "find_providers_enhanced")):
        logger.debug("Enhanced DHT discovery methods already added to IPFSLibp2pPeer")
        return peer_class

    def integrate_enhanced_dht_discovery(self):
        """Integrate the enhanced DHT discovery system with this peer.
        
        This adds the more advanced discovery capabilities from enhanced_dht_discovery.py,
        improving content routing, peer discovery, and network metrics.
        
        Returns:
            Dict with integration result
        """
        result = {
            "success": False,
            "operation": "integrate_enhanced_dht_discovery",
            "timestamp": time.time()
        }
        
        try:
            # Import the enhanced discovery classes
            from ipfs_kit_py.libp2p.enhanced_dht_discovery import EnhancedDHTDiscovery, ContentRoutingManager
            
            # Create the enhanced discovery component
            self.enhanced_discovery = EnhancedDHTDiscovery(
                libp2p_peer=self,
                role=self.role,
                bootstrap_peers=self.bootstrap_peers
            )
            
            # Create the content routing manager
            self.content_router = ContentRoutingManager(
                dht_discovery=self.enhanced_discovery,
                libp2p_peer=self
            )
            
            # Start the discovery system
            self.enhanced_discovery.start()
            
            result["success"] = True
            result["message"] = "Successfully integrated enhanced DHT discovery"
            self.logger.info("Enhanced DHT discovery integrated and started")
            
        except ImportError as e:
            result["error"] = f"Failed to import enhanced DHT discovery: {str(e)}"
            self.logger.error(f"Enhanced DHT discovery integration failed - import error: {e}")
        except Exception as e:
            result["error"] = f"Failed to integrate enhanced DHT discovery: {str(e)}"
            self.logger.error(f"Enhanced DHT discovery integration failed: {e}")
            
        return result

    def find_providers_enhanced(self, cid: str, count: int = 5, timeout: int = 30) -> Dict[str, Any]:
        """Find providers for content using the enhanced discovery system.
        
        This method uses the advanced provider tracking and reputation system to find 
        the most reliable sources for specific content.
        
        Args:
            cid: Content ID to find providers for
            count: Maximum number of providers to return
            timeout: Maximum time to wait in seconds
            
        Returns:
            Dict with provider information
        """
        result = {
            "success": False,
            "operation": "find_providers_enhanced",
            "timestamp": time.time(),
            "cid": cid,
            "providers": []
        }
        
        # First check if enhanced discovery is available
        if not hasattr(self, "enhanced_discovery") or not hasattr(self, "content_router"):
            # Try to integrate it
            integration_result = self.integrate_enhanced_dht_discovery()
            if not integration_result["success"]:
                result["error"] = "Enhanced discovery not available"
                # Fall back to regular find_providers
                try:
                    regular_result = self.find_providers(cid, count=count, timeout=timeout)
                    result["providers"] = regular_result.get("providers", [])
                    result["success"] = regular_result.get("success", False)
                    result["fallback_to_standard"] = True
                    return result
                except Exception as e:
                    result["error"] = f"Both enhanced and standard provider search failed: {str(e)}"
                    return result
        
        try:
            # Use the content router to find optimal providers
            future = self.content_router.find_content(
                cid, 
                options={
                    "timeout": timeout,
                    "max_providers": count
                }
            )
            
            # Wait for the result with timeout
            import anyio
            providers = future.result(timeout=timeout)
            
            if providers:
                result["providers"] = providers
                result["provider_count"] = len(providers)
                result["success"] = True
            else:
                result["error"] = "No providers found"
                
            return result
                
        except ImportError as e:
            result["error"] = f"Enhanced DHT discovery not available: {str(e)}"
            self.logger.error(f"Error in enhanced provider search - import error: {e}")
            return result
        except Exception as e:
            result["error"] = f"Error finding providers: {str(e)}"
            self.logger.error(f"Error in enhanced provider search: {e}")
            return result
    
    # Add methods to the peer class
    peer_class.integrate_enhanced_dht_discovery = integrate_enhanced_dht_discovery
    peer_class.find_providers_enhanced = find_providers_enhanced
    
    return peer_class


def enhance_libp2p_peer(peer_class):
    """
    Add all enhanced protocol methods to the IPFSLibp2pPeer class.
    
    Args:
        peer_class: The IPFSLibp2pPeer class to extend
        
    Returns:
        The enhanced peer class
    """
    peer_class = add_gossipsub_methods(peer_class)
    peer_class = add_enhanced_dht_discovery_methods(peer_class)
    
    return peer_class