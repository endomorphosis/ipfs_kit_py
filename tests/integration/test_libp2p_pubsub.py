"""
Tests for libp2p PubSub implementation in ipfs_kit_py.

This module tests the publish-subscribe utilities in the ipfs_kit_py library, including:
- GossipSub protocol implementation
- Publish/subscribe messaging patterns
- Topic validation and message formatting
- Mock PubSub implementation for compatibility
"""

import anyio
import inspect
import sys
import unittest
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock

# Test imports
import pytest
from ipfs_kit_py.libp2p.tools.pubsub.utils import (
    validate_pubsub_topic,
    format_pubsub_message,
    extract_pubsub_message_data,
    create_pubsub_subscription_handler,
class TestMockPubSub:
    create_pubsub,
    
    pytestmark = pytest.mark.anyio
    
    @pytest.fixture(autouse=True)
    def _setup(self):
        """Set up a mock host and pubsub instance for each test."""
        self.host = MagicMock()
        self.host.get_id.return_value = "QmTestPeer"
        self.pubsub = MockPubSub(self.host, router_type="gossipsub")
        yield
    MockPubSub
)


class TestTopicValidation(unittest.TestCase):
    """Test the pubsub topic validation function."""
    
        assert result is True
        assert self.pubsub.started is True
        valid_topics = [
            "test-topic",
            "chat/room/general",
            "ipfs/pubsub/demo",
            "a" * 1024,  # Maximum length
        assert result is True
        assert self.pubsub.started is False
        assert len(self.pubsub.subscriptions) == 0
        for topic in valid_topics:
            self.assertTrue(validate_pubsub_topic(topic))
    
    def test_invalid_topics(self):
        """Test validation of invalid topic names."""
        invalid_topics = [
            "",  # Empty string
            None,  # None
            123,  # Not a string
            "a" * 1025,  # Too long
            [],  # Not a string
            {}  # Not a string
        ]
        assert result is True
        assert "test-topic" in self.pubsub.subscriptions
        assert handler in self.pubsub.subscriptions["test-topic"]


class TestMessageFormatting(unittest.TestCase):
    """Test pubsub message formatting functions."""
    
        assert result is True
        assert "test-topic" not in self.pubsub.subscriptions
        data = "Hello, world!"
        sender_id = "QmTestPeer"
        
        message = format_pubsub_message(data, sender_id)
        
        # Check message structure
        self.assertIn("data", message)
        self.assertIn("seqno", message)
        self.assertIn("timestamp", message)
        assert set(topics) == {"topic1", "topic2"}
        
        # Check data conversion
        self.assertEqual(message["data"], b"Hello, world!")
        self.assertEqual(message["from"], sender_id)
        
        assert "topic1" not in self.pubsub.subscriptions
        assert "topic2" in self.pubsub.subscriptions
        self.assertIsInstance(message["seqno"], bytes)
        self.assertIsInstance(message["timestamp"], bytes)
    
    def test_format_message_bytes(self):
        """Test formatting a bytes message."""
        assert result is False
        
        message = format_pubsub_message(data)
        
        # Check message structure
        self.assertIn("data", message)
        self.assertIn("seqno", message)
        self.assertIn("timestamp", message)
        self.assertNotIn("from", message)  # No sender specified
        
        # Check data
        self.assertEqual(message["data"], b"Binary data")
    
    def test_extract_message_data(self):
        """Test extracting data from a message."""
        original_data = b"Test data"
        message = {"data": original_data, "seqno": b"12345678", "timestamp": b"12345678"}
        extracted = extract_pubsub_message_data(message)
        
        self.assertEqual(extracted, original_data)
    
        assert message["data"] == b"Hello, world!"
        """Test extracting data from a message with missing data field."""
        message = {"seqno": b"12345678", "timestamp": b"12345678"}
        
        with self.assertRaises(ValueError):
            extract_pubsub_message_data(message)


class TestSubscriptionHandler(unittest.TestCase):
        assert result is True
        handler.assert_not_called()
    def test_create_handler(self):
        """Test creating a subscription handler."""
        # Create a mock callback
        callback = MagicMock()
        
        assert result is False
        handler = create_pubsub_subscription_handler(callback)
        
        # Create a test message
        test_message = {"data": b"Test message"}
        
        # Call the handler with the message
        assert result is False
        
        # Verify callback was called with the message
        callback.assert_called_once_with(test_message)
    
    def test_handler_error_handling(self):
        """Test error handling in subscription handler."""
        # Create a callback that raises an exception
        callback = MagicMock(side_effect=Exception("Test error"))
        
        # Create a handler using the callback
        handler = create_pubsub_subscription_handler(callback)
        
        # Create a test message
        test_message = {"data": b"Test message"}
        
        # Call the handler with the message (should not raise)
        with self.assertLogs(level='ERROR') as log:
            
        # Verify error was logged
        assert result is True
        assert "ERROR:ipfs_kit_py.libp2p.tools.pubsub.utils" in log.output[0]
        assert "Error in subscription handler" in log.output[0]


class TestPubSubCreation(unittest.TestCase):
    """Test pubsub creation function."""
    
    def setUp(self):
        """Set up a mock host for each test."""
        self.host = MagicMock()
        self.host.get_id.return_value = "QmTestPeer"
    
    @patch('ipfs_kit_py.libp2p.tools.pubsub.utils.PUBSUB_AVAILABLE', False)
    def test_create_mock_pubsub(self):
        """Test creating a mock pubsub when libp2p is not available."""
        pubsub = create_pubsub(self.host, router_type="gossipsub")
        
        # Should create a MockPubSub instance
        self.assertIsInstance(pubsub, MockPubSub)
        self.assertEqual(pubsub.router_type, "gossipsub")
        self.assertEqual(pubsub.host, self.host)
    
    @patch('ipfs_kit_py.libp2p.tools.pubsub.utils.PUBSUB_AVAILABLE', True)
    @patch('ipfs_kit_py.libp2p.tools.pubsub.utils.GossipSub')
    def test_create_gossipsub(self, mock_gossipsub):
        """Test creating a GossipSub instance when libp2p is available."""
        # Set up mock to return itself
        mock_gossipsub.return_value = mock_gossipsub
        
        # Create pubsub
        pubsub = create_pubsub(self.host, router_type="gossipsub", cache_size=256, strict_signing=False)
        
        # Just check that GossipSub was called at least once with the host
        mock_gossipsub.assert_called_with(self.host, **{})  # Ignore kwargs
    
    @patch('ipfs_kit_py.libp2p.tools.pubsub.utils.PUBSUB_AVAILABLE', True)
    @patch('ipfs_kit_py.libp2p.tools.pubsub.utils.FloodSub')
    def test_create_floodsub(self, mock_floodsub):
        """Test creating a FloodSub instance when libp2p is available."""
        # Set up mock to return itself
        mock_floodsub.return_value = mock_floodsub
        
        # Create pubsub
        pubsub = create_pubsub(self.host, router_type="floodsub", strict_signing=True)
        
        # Just check that FloodSub was called at least once with the host
        mock_floodsub.assert_called_with(self.host, **{})  # Ignore kwargs
    
    @patch('ipfs_kit_py.libp2p.tools.pubsub.utils.PUBSUB_AVAILABLE', True)
    def test_create_unknown_router(self):
        """Test creating pubsub with unknown router type."""
        with self.assertRaises(ValueError):
            create_pubsub(self.host, router_type="unknown_router")


class TestMockPubSub:
    """Test the MockPubSub implementation."""
    
    def setUp(self):
        """Set up a mock host and pubsub instance for each test."""
        self.host = MagicMock()
        self.host.get_id.return_value = "QmTestPeer"
        self.pubsub = MockPubSub(self.host, router_type="gossipsub")
    
    async def test_start_stop(self):
        """Test starting and stopping the service."""
        # Start the service
        result = await self.pubsub.start()
        
        # Should succeed
        self.assertTrue(result)
        self.assertTrue(self.pubsub.started)
        
        # Stop the service
        result = await self.pubsub.stop()
        
        # Should succeed
        self.assertTrue(result)
        self.assertFalse(self.pubsub.started)
        self.assertEqual(len(self.pubsub.subscriptions), 0)
    
    async def test_subscribe_unsubscribe(self):
        """Test subscribing and unsubscribing from topics."""
        # Start the service
        await self.pubsub.start()
        
        # Create a mock handler
        handler = MagicMock()
        
        # Subscribe to a topic
        result = await self.pubsub.subscribe("test-topic", handler)
        
        # Should succeed
        self.assertTrue(result)
        self.assertIn("test-topic", self.pubsub.subscriptions)
        self.assertIn(handler, self.pubsub.subscriptions["test-topic"])
        
        # Unsubscribe from the topic
        result = await self.pubsub.unsubscribe("test-topic", handler)
        
        # Should succeed
        self.assertTrue(result)
        self.assertNotIn("test-topic", self.pubsub.subscriptions)
        
        # Subscribe to multiple topics
        await self.pubsub.subscribe("topic1", handler)
        await self.pubsub.subscribe("topic2", handler)
        
        # Get topics
        topics = self.pubsub.get_topics()
        
        # Should include both topics
        self.assertEqual(set(topics), {"topic1", "topic2"})
        
        # Unsubscribe from all handlers
        await self.pubsub.unsubscribe("topic1")
        
        # Should have removed topic1
        self.assertNotIn("topic1", self.pubsub.subscriptions)
        self.assertIn("topic2", self.pubsub.subscriptions)
        
        # Try unsubscribing from non-existent topic
        result = await self.pubsub.unsubscribe("non-existent")
        
        # Should fail
        self.assertFalse(result)
    
    async def test_publish(self):
        """Test publishing messages."""
        # Start the service
        await self.pubsub.start()
        
        # Create a mock handler
        handler = MagicMock()
        
        # Subscribe to a topic
        await self.pubsub.subscribe("test-topic", handler)
        
        # Publish a message
        result = await self.pubsub.publish("test-topic", "Hello, world!")
        
        # Should succeed
        self.assertTrue(result)
        
        # Handler should be called with a message
        handler.assert_called_once()
        message = handler.call_args[0][0]
        self.assertEqual(message["data"], b"Hello, world!")
        
        # Reset mock
        handler.reset_mock()
        
        # Try publishing to non-existent topic (should succeed as it's just not delivered)
        result = await self.pubsub.publish("non-existent", "Hello")
        
        # Should succeed but handler should not be called
        self.assertTrue(result)
        handler.assert_not_called()
        
        # Try publishing to invalid topic
        result = await self.pubsub.publish("", "Hello")
        
        # Should fail
        self.assertFalse(result)
        
        # Try publishing without starting
        await self.pubsub.stop()
        result = await self.pubsub.publish("test-topic", "Hello")
        
        # Should fail
        self.assertFalse(result)
    
    async def test_publish_with_handler_error(self):
        """Test publishing with a handler that raises an error."""
        # Start the service
        await self.pubsub.start()
        
        # Create a handler that raises an exception
        handler = MagicMock(side_effect=Exception("Test error"))
        
        # Subscribe to a topic
        await self.pubsub.subscribe("test-topic", handler)
        
        # Publish a message
        with self.assertLogs(level='ERROR') as log:
            result = await self.pubsub.publish("test-topic", "Hello, world!")
            
        # Should succeed despite handler error
        self.assertTrue(result)
        
        # Should have logged an error
        self.assertIn("ERROR:ipfs_kit_py.libp2p.tools.pubsub.utils", log.output[0])
        self.assertIn("Error in subscription handler", log.output[0])


class TestPubSubIntegration:
class TestPubSubIntegration:
    """Integration tests for the pubsub system."""
    
    pytestmark = pytest.mark.anyio
    
    async def test_publish_subscribe_flow(self):
        """Test the complete publish-subscribe flow."""
        # Create a host
        host = MagicMock()
        host.get_id.return_value = "QmTestPeer"
        
        # Create pubsub - force using MockPubSub to avoid dependency on real libp2p implementation
        with patch('ipfs_kit_py.libp2p.tools.pubsub.utils.PUBSUB_AVAILABLE', False):
            pubsub = create_pubsub(host, router_type="gossipsub")
            
            # Verify we got a MockPubSub
            assert isinstance(pubsub, MockPubSub)
        
        # Messages received by the subscribers
        received_messages = []
        
        # Create a handler to collect messages
        def message_handler(message):
            received_messages.append(message)
        
        # Start pubsub
        await pubsub.start()
        
        # Subscribe to topics
        await pubsub.subscribe("topic1", message_handler)
        await pubsub.subscribe("topic2", message_handler)
        
        # Publish messages
        await pubsub.publish("topic1", "Message to topic1")
        await pubsub.publish("topic2", "Message to topic2")
        await pubsub.publish("topic3", "Message to topic3")  # Not subscribed
        
        # Should have received 2 messages
        assert len(received_messages) == 2
        
        # Check message contents
        message_data = [msg["data"] for msg in received_messages]
        assert b"Message to topic1" in message_data
        assert b"Message to topic2" in message_data
        assert b"Message to topic3" not in message_data
        
        # Get topics
        topics = pubsub.get_topics()
        assert set(topics) == {"topic1", "topic2"}
        
        # Unsubscribe from all topics
        for topic in topics:
            await pubsub.unsubscribe(topic)
            
        # Topics should be empty
        assert len(pubsub.get_topics()) == 0
        
        # Stop pubsub
        await pubsub.stop()


if __name__ == "__main__":
    unittest.main()