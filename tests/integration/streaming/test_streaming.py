"""
Integration test for MCP Streaming operations.
This test verifies the functionality of the streaming capabilities
including file streaming, WebSocket integration, and WebRTC signaling.
"""

import os
import sys
import unittest
import logging
import tempfile
import time
import uuid
import json
import asyncio
from pathlib import Path

# Add the parent directory to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestStreamingOperations(unittest.TestCase):
    """Integration tests for the MCP streaming operations."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test resources."""
        # Import necessary components conditionally to handle missing dependencies
        try:
            from ipfs_kit_py.mcp.streaming import file_streaming, websocket_manager, webrtc_signaling
            cls.file_streaming = file_streaming
            cls.websocket_manager = websocket_manager
            cls.webrtc_signaling = webrtc_signaling
            cls.import_error = None
        except ImportError as e:
            logger.warning(f"Cannot import streaming modules: {e}")
            cls.import_error = e
            return
        
        # Create a test file for streaming operations
        cls.test_dir = Path(tempfile.mkdtemp())
        cls.test_file_path = cls.test_dir / f"test_file_{uuid.uuid4()}.bin"
        
        # Generate a random file of 1MB
        with open(cls.test_file_path, 'wb') as f:
            f.write(os.urandom(1024 * 1024))  # 1MB random data
        
        logger.info(f"Created test file at: {cls.test_file_path}")
    
    def setUp(self):
        """Set up for each test."""
        if hasattr(self.__class__, 'import_error') and self.__class__.import_error:
            self.skipTest(f"Streaming modules not available: {self.__class__.import_error}")
    
    def test_file_streaming_module_exists(self):
        """Test that the file streaming module exists and can be initialized."""
        self.assertIsNotNone(self.file_streaming)
        logger.info("File streaming module exists")
        
        # Check for expected attributes/methods
        expected_attributes = [
            'ChunkedFileUploader', 'StreamingDownloader', 
            'BackgroundPinningManager', 'ProgressTracker'
        ]
        
        for attr in expected_attributes:
            self.assertTrue(hasattr(self.file_streaming, attr), f"Missing attribute: {attr}")
        
        logger.info("File streaming module has expected components")
    
    def test_websocket_manager_exists(self):
        """Test that the WebSocket manager exists and can be initialized."""
        self.assertIsNotNone(self.websocket_manager)
        logger.info("WebSocket manager module exists")
        
        # Check for expected attributes/methods
        expected_attributes = [
            'get_ws_manager', 'WebSocketManager', 'EventType'
        ]
        
        for attr in expected_attributes:
            self.assertTrue(hasattr(self.websocket_manager, attr), f"Missing attribute: {attr}")
        
        # Try to get the WebSocket manager instance
        ws_manager = self.websocket_manager.get_ws_manager()
        self.assertIsNotNone(ws_manager)
        
        logger.info("WebSocket manager can be instantiated")
    
    def test_webrtc_signaling_exists(self):
        """Test that the WebRTC signaling module exists."""
        self.assertIsNotNone(self.webrtc_signaling)
        logger.info("WebRTC signaling module exists")
        
        # Check for expected attributes/methods
        expected_attributes = [
            'SignalingServer', 'Room'
        ]
        
        for attr in expected_attributes:
            self.assertTrue(hasattr(self.webrtc_signaling, attr), f"Missing attribute: {attr}")
        
        logger.info("WebRTC signaling module has expected components")
    
    def test_chunked_file_uploader(self):
        """Test the chunked file uploader component."""
        if not hasattr(self.file_streaming, 'ChunkedFileUploader'):
            self.skipTest("ChunkedFileUploader not available")
        
        # Create a mock file destination that captures chunks
        class MockDestination:
            def __init__(self):
                self.chunks = []
                
            async def add_chunk(self, chunk):
                self.chunks.append(chunk)
                return {"success": True, "chunk_id": len(self.chunks)}
            
            async def finalize(self, chunk_ids):
                total_size = sum(len(chunk) for chunk in self.chunks)
                return {"success": True, "total_size": total_size}
        
        dest = MockDestination()
        
        # Create uploader with reasonably sized chunks
        uploader = self.file_streaming.ChunkedFileUploader(
            chunk_size=256 * 1024,  # 256KB chunks
            max_concurrent=2
        )
        
        # Run the upload in a synchronous way for testing
        async def run_upload():
            result = await uploader.upload(self.test_file_path, dest)
            return result
            
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(run_upload())
            self.assertTrue(result.get("success", False))
            self.assertEqual(result.get("total_size"), os.path.getsize(self.test_file_path))
            
            # Verify chunks were received
            self.assertGreater(len(dest.chunks), 0)
            total_chunk_size = sum(len(chunk) for chunk in dest.chunks)
            self.assertEqual(total_chunk_size, os.path.getsize(self.test_file_path))
            
            logger.info(f"Chunked upload successful: {result}")
        finally:
            loop.close()
    
    @classmethod
    def tearDownClass(cls):
        """Clean up resources."""
        if hasattr(cls, 'test_dir') and cls.test_dir.exists():
            import shutil
            shutil.rmtree(cls.test_dir)
            logger.info(f"Cleaned up test directory: {cls.test_dir}")

if __name__ == "__main__":
    unittest.main()