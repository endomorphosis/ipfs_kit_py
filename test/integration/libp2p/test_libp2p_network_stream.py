"""
Tests for the network stream interface implementation in libp2p.

This module tests the implementation of the libp2p network stream interface, including:
- INetStream interface
- NetStream implementation
- StreamError exception class
- StreamHandler helper class
"""

import asyncio
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import os

# Add the parent directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import the modules to test
from ipfs_kit_py.libp2p.network.stream.net_stream_interface import (
    INetStream, NetStream, StreamError, StreamHandler
)


class TestINetStreamInterface(unittest.TestCase):
    """Test the INetStream interface methods."""

    def test_interface_methods(self):
        """Test that the interface methods raise NotImplementedError."""
        stream = INetStream()
        
        # Create an event loop for testing async methods
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Test read method
            with self.assertRaises(NotImplementedError):
                loop.run_until_complete(stream.read())
            
            # Test write method
            with self.assertRaises(NotImplementedError):
                loop.run_until_complete(stream.write(b"test"))
            
            # Test close method
            with self.assertRaises(NotImplementedError):
                loop.run_until_complete(stream.close())
            
            # Test reset method
            with self.assertRaises(NotImplementedError):
                loop.run_until_complete(stream.reset())
            
            # Test get_protocol method
            with self.assertRaises(NotImplementedError):
                stream.get_protocol()
            
            # Test set_protocol method
            with self.assertRaises(NotImplementedError):
                stream.set_protocol("test")
            
            # Test get_peer method
            with self.assertRaises(NotImplementedError):
                stream.get_peer()
                
        finally:
            loop.close()


class TestNetStream(unittest.TestCase):
    """Test the NetStream implementation."""

    def setUp(self):
        """Set up test environment."""
        # Create mock StreamReader and StreamWriter
        self.reader = AsyncMock(spec=asyncio.StreamReader)
        self.writer = AsyncMock(spec=asyncio.StreamWriter)
        
        # Create a NetStream instance
        self.stream = NetStream(
            self.reader, 
            self.writer, 
            protocol_id="/test/protocol/1.0.0", 
            peer_id="QmTestPeer"
        )
        
        # Create an event loop for testing async methods
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        """Clean up after tests."""
        self.loop.close()

    def test_initialization(self):
        """Test that the NetStream initializes correctly."""
        self.assertEqual(self.stream.reader, self.reader)
        self.assertEqual(self.stream.writer, self.writer)
        self.assertEqual(self.stream._protocol_id, "/test/protocol/1.0.0")
        self.assertEqual(self.stream._peer_id, "QmTestPeer")
        self.assertFalse(self.stream._closed)

    def test_read_with_max_size(self):
        """Test reading with a maximum size."""
        # Set up the mock reader
        self.reader.read.return_value = b"test data"
        
        # Call read with max_size
        result = self.loop.run_until_complete(self.stream.read(max_size=100))
        
        # Verify result and mock calls
        self.assertEqual(result, b"test data")
        self.reader.read.assert_called_once_with(100)

    def test_read_until_eof(self):
        """Test reading until EOF."""
        # Setup the mock reader to simulate multiple chunks
        self.reader.read.side_effect = [b"chunk1", b"chunk2", b"chunk3", b""]
        
        # Call read without max_size
        result = self.loop.run_until_complete(self.stream.read())
        
        # Verify result and mock calls
        self.assertEqual(result, b"chunk1chunk2chunk3")
        self.assertEqual(self.reader.read.call_count, 4)

    def test_read_closed_stream(self):
        """Test reading from a closed stream."""
        # Close the stream
        self.stream._closed = True
        
        # Expect an EOFError when reading
        with self.assertRaises(EOFError):
            self.loop.run_until_complete(self.stream.read())
        
        # Verify the mock was not called
        self.reader.read.assert_not_called()

    def test_read_error(self):
        """Test handling errors during read."""
        # Set up the mock reader to raise an exception
        self.reader.read.side_effect = Exception("Read error")
        
        # Expect a StreamError when reading
        with self.assertRaises(StreamError):
            self.loop.run_until_complete(self.stream.read())
        
        # Verify the mock was called
        self.reader.read.assert_called_once()

    def test_write(self):
        """Test writing to the stream."""
        # Set up test data
        test_data = b"test data"
        
        # Call write
        result = self.loop.run_until_complete(self.stream.write(test_data))
        
        # Verify result and mock calls
        self.assertEqual(result, len(test_data))
        self.writer.write.assert_called_once_with(test_data)
        self.writer.drain.assert_called_once()

    def test_write_closed_stream(self):
        """Test writing to a closed stream."""
        # Close the stream
        self.stream._closed = True
        
        # Expect a StreamError when writing
        with self.assertRaises(StreamError):
            self.loop.run_until_complete(self.stream.write(b"test"))
        
        # Verify the mock was not called
        self.writer.write.assert_not_called()
        self.writer.drain.assert_not_called()

    def test_write_error(self):
        """Test handling errors during write."""
        # Set up the mock writer to raise an exception
        self.writer.drain.side_effect = Exception("Write error")
        
        # Expect a StreamError when writing
        with self.assertRaises(StreamError):
            self.loop.run_until_complete(self.stream.write(b"test"))
        
        # Verify the write was called, but error happened during drain
        self.writer.write.assert_called_once()
        self.writer.drain.assert_called_once()

    def test_close(self):
        """Test closing the stream."""
        # Configure mock
        self.writer.wait_closed = AsyncMock()
        
        # Call close
        self.loop.run_until_complete(self.stream.close())
        
        # Verify mock calls
        self.writer.close.assert_called_once()
        self.writer.wait_closed.assert_called_once()
        self.assertTrue(self.stream._closed)

    def test_close_already_closed(self):
        """Test closing an already closed stream."""
        # Close the stream
        self.stream._closed = True
        
        # Call close again
        self.loop.run_until_complete(self.stream.close())
        
        # Verify the mock was not called
        self.writer.close.assert_not_called()

    def test_close_error(self):
        """Test handling errors during close."""
        # Set up the mock writer to raise an exception
        self.writer.close.side_effect = Exception("Close error")
        
        # Expect a StreamError when closing
        with self.assertRaises(StreamError):
            self.loop.run_until_complete(self.stream.close())
        
        # Verify the mock was called
        self.writer.close.assert_called_once()
        self.assertFalse(self.stream._closed)

    def test_reset(self):
        """Test resetting the stream."""
        # Call reset
        self.loop.run_until_complete(self.stream.reset())
        
        # Verify mock calls
        self.writer.close.assert_called_once()
        self.assertTrue(self.stream._closed)

    def test_reset_error(self):
        """Test handling errors during reset."""
        # Set up the mock writer to raise an exception
        self.writer.close.side_effect = Exception("Reset error")
        
        # Expect a StreamError when resetting
        with self.assertRaises(StreamError):
            self.loop.run_until_complete(self.stream.reset())
        
        # Verify the mock was called
        self.writer.close.assert_called_once()

    def test_get_protocol(self):
        """Test getting the protocol ID."""
        # Call get_protocol
        protocol_id = self.stream.get_protocol()
        
        # Verify result
        self.assertEqual(protocol_id, "/test/protocol/1.0.0")

    def test_set_protocol(self):
        """Test setting the protocol ID."""
        # Call set_protocol
        self.stream.set_protocol("/new/protocol/1.0.0")
        
        # Verify result
        self.assertEqual(self.stream._protocol_id, "/new/protocol/1.0.0")

    def test_get_peer(self):
        """Test getting the peer ID."""
        # Call get_peer
        peer_id = self.stream.get_peer()
        
        # Verify result
        self.assertEqual(peer_id, "QmTestPeer")


class TestStreamError(unittest.TestCase):
    """Test the StreamError exception class."""

    def test_error_instance(self):
        """Test that StreamError is an instance of Exception."""
        error = StreamError("Test error")
        self.assertIsInstance(error, Exception)
        self.assertEqual(str(error), "Test error")


class TestStreamHandler(unittest.TestCase):
    """Test the StreamHandler class."""

    def setUp(self):
        """Set up test environment."""
        # Create a mock handler function
        self.handler_func = AsyncMock()
        
        # Create a StreamHandler instance
        self.stream_handler = StreamHandler("/test/protocol/1.0.0", self.handler_func)
        
        # Create a mock stream
        self.stream = MagicMock(spec=INetStream)
        self.stream.reset = AsyncMock()
        
        # Create an event loop for testing async methods
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        """Clean up after tests."""
        self.loop.close()

    def test_initialization(self):
        """Test that the StreamHandler initializes correctly."""
        self.assertEqual(self.stream_handler.protocol_id, "/test/protocol/1.0.0")
        self.assertEqual(self.stream_handler.handler_func, self.handler_func)

    def test_handle_stream(self):
        """Test handling a stream."""
        # Call handle_stream
        self.loop.run_until_complete(self.stream_handler.handle_stream(self.stream))
        
        # Verify handler_func was called with the stream
        self.handler_func.assert_called_once_with(self.stream)
        
        # Verify reset was not called
        self.stream.reset.assert_not_called()

    def test_handle_stream_error(self):
        """Test handling errors during stream handling."""
        # Set up handler_func to raise an exception
        self.handler_func.side_effect = Exception("Handler error")
        
        # Call handle_stream
        self.loop.run_until_complete(self.stream_handler.handle_stream(self.stream))
        
        # Verify handler_func was called
        self.handler_func.assert_called_once_with(self.stream)
        
        # Verify reset was called
        self.stream.reset.assert_called_once()

    def test_handle_stream_reset_error(self):
        """Test handling errors during stream reset."""
        # Set up handler_func to raise an exception
        self.handler_func.side_effect = Exception("Handler error")
        
        # Set up reset to raise an exception
        self.stream.reset.side_effect = Exception("Reset error")
        
        # Call handle_stream (should not propagate the reset error)
        self.loop.run_until_complete(self.stream_handler.handle_stream(self.stream))
        
        # Verify handler_func was called
        self.handler_func.assert_called_once_with(self.stream)
        
        # Verify reset was called
        self.stream.reset.assert_called_once()


if __name__ == "__main__":
    unittest.main()