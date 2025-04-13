"""
PubSub utilities for libp2p.

This is a custom implementation of the missing libp2p.tools.pubsub module.
It provides compatibility functions that might be missing in the installed version of libp2p.
"""

import logging

# Configure logger
logger = logging.getLogger(__name__)

# Import and expose utility functions
try:
    from .utils import (
        validate_pubsub_topic,
        format_pubsub_message,
        extract_pubsub_message_data,
        format_message_from_event,
        create_pubsub_subscription_handler,
        create_pubsub,
        MockPubSub
    )
except ImportError:
    logger.warning("Could not import PubSub utility functions, using placeholders")
    
    # Define basic placeholders
    def validate_pubsub_topic(topic):
        """Placeholder validation function."""
        return isinstance(topic, str)
        
    def format_pubsub_message(data, sender_id=None):
        """Placeholder formatting function."""
        return {"data": data, "from": sender_id}
        
    def extract_pubsub_message_data(message):
        """Placeholder extraction function."""
        return message.get("data", b"")
        
    def format_message_from_event(topic, data, sender_id):
        """Placeholder event formatting function."""
        return {"data": data, "from": sender_id, "topicIDs": [topic]}
        
    def create_pubsub_subscription_handler(callback):
        """Placeholder handler creation function."""
        return callback
        
    def create_pubsub(host, router_type="gossipsub", **kwargs):
        """Placeholder pubsub creation function."""
        logger.warning("Using placeholder pubsub implementation")
        return MockPubSub(host, router_type, **kwargs)
        
    class MockPubSub:
        """Placeholder MockPubSub implementation."""
        
        def __init__(self, host, router_type="gossipsub", **kwargs):
            self.host = host
            self.router_type = router_type
            self.subscriptions = {}
            
        async def start(self):
            """Start the pubsub service."""
            return True
            
        async def stop(self):
            """Stop the pubsub service."""
            return True
            
        async def publish(self, topic_id, data):
            """Publish data to a topic."""
            logger.warning(f"Mock publish to {topic_id}")
            return True
            
        async def subscribe(self, topic_id, handler):
            """Subscribe to a topic."""
            if topic_id not in self.subscriptions:
                self.subscriptions[topic_id] = []
            self.subscriptions[topic_id].append(handler)
            return True
            
        async def unsubscribe(self, topic_id, handler=None):
            """Unsubscribe from a topic."""
            if topic_id in self.subscriptions:
                if handler is None:
                    del self.subscriptions[topic_id]
                elif handler in self.subscriptions[topic_id]:
                    self.subscriptions[topic_id].remove(handler)
            return True
            
        def get_topics(self):
            """Get list of subscribed topics."""
            return list(self.subscriptions.keys())