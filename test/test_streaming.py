import unittest
import asyncio
import os
import tempfile
from unittest.mock import patch, AsyncMock
import shutil
import pytest
import io
from fastapi.testclient import TestClient

from ipfs_kit_py.high_level_api import IPFSSimpleAPI
from ipfs_kit_py.api import app

class TestStreaming(unittest.TestCase):
    """Test streaming functionality for both HTTP and WebSocket interfaces."""
    
    def setUp(self):
        """Set up test environment."""
        self.api = IPFSSimpleAPI()
        self.test_content = b"Test content for streaming" * 1000  # ~26KB
        self.test_dir = tempfile.mkdtemp()
        self.test_file_path = os.path.join(self.test_dir, "test_file.txt")
        
        # Create test file
        with open(self.test_file_path, "wb") as f:
            f.write(self.test_content)
        
        # Mock CID for testing
        self.test_cid = "QmTestCID123456789"
        
        # Create a FastAPI test client
        self.client = TestClient(app)
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    @patch.object(IPFSSimpleAPI, 'add')
    @patch.object(IPFSSimpleAPI, 'cat')
    def test_stream_media(self, mock_cat, mock_add):
        """Test streaming media content."""
        # Setup mocks
        mock_cat.return_value = self.test_content
        mock_add.return_value = {"Hash": self.test_cid}
        
        # Test the streaming method
        chunks = list(self.api.stream_media(self.test_cid, chunk_size=1024))
        
        # Verify all content was received in chunks
        received_content = b''.join(chunks)
        self.assertEqual(received_content, self.test_content)
        
        # Verify cat was called
        mock_cat.assert_called_once_with(self.test_cid)
    
    @patch.object(IPFSSimpleAPI, 'add')
    def test_stream_to_ipfs(self, mock_add):
        """Test streaming content to IPFS."""
        # Setup mock
        mock_add.return_value = {"Hash": self.test_cid}
        
        # Create a file-like object
        file_obj = io.BytesIO(self.test_content)
        
        # Test the streaming upload method
        result = self.api.stream_to_ipfs(file_obj, chunk_size=1024)
        
        # Verify result
        self.assertEqual(result.get("Hash"), self.test_cid)
        
        # Verify add was called with appropriate content
        mock_add.assert_called_once()
        # The content is processed in chunks, so we can't directly check the call args
    
    @patch.object(IPFSSimpleAPI, 'cat')
    def test_http_stream_endpoint(self, mock_cat):
        """Test HTTP streaming endpoint."""
        # Setup mock
        mock_cat.return_value = self.test_content
        
        # Test the streaming endpoint
        response = self.client.get(f"/api/v0/stream?path={self.test_cid}")
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, self.test_content)
        
        # Verify cat was called
        mock_cat.assert_called_once_with(self.test_cid)
    
    @patch.object(IPFSSimpleAPI, 'cat')
    def test_http_media_stream_endpoint(self, mock_cat):
        """Test HTTP media streaming endpoint with range requests."""
        # Setup mock
        mock_cat.return_value = self.test_content
        
        # Test with range header
        start_byte = 5
        end_byte = 15
        headers = {"Range": f"bytes={start_byte}-{end_byte}"}
        response = self.client.get(
            f"/api/v0/stream/media?path={self.test_cid}",
            headers=headers
        )
        
        # Verify response
        self.assertEqual(response.status_code, 206)  # Partial Content
        self.assertEqual(response.content, self.test_content[start_byte:end_byte+1])
        self.assertEqual(response.headers["Content-Range"], 
                         f"bytes {start_byte}-{end_byte}/{len(self.test_content)}")
        
        # Verify cat was called
        mock_cat.assert_called_once_with(self.test_cid)
    
    @patch.object(IPFSSimpleAPI, 'add')
    def test_http_upload_stream_endpoint(self, mock_add):
        """Test HTTP streaming upload endpoint."""
        # Setup mock
        mock_add.return_value = {"Hash": self.test_cid}
        
        # Create multipart form data for file upload
        files = {"file": ("test_file.txt", io.BytesIO(self.test_content))}
        response = self.client.post("/api/v0/upload/stream", files=files)
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result.get("Hash"), self.test_cid)
        
        # Verify add was called
        mock_add.assert_called_once()


@pytest.mark.asyncio
class TestAsyncStreaming:
    """Test asynchronous streaming functionality."""
    
    @pytest.fixture(autouse=True)
    async def setup_and_cleanup(self):
        """Setup and cleanup fixture that runs for each test."""
        # Create a new event loop for each test
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        yield
        # Clean up the loop
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        await loop.shutdown_asyncgens()
        loop.close()
    
    @pytest.fixture
    async def setup(self):
        """Set up test environment."""
        api = IPFSSimpleAPI()
        test_content = b"Test content for async streaming" * 1000  # ~33KB
        test_dir = tempfile.mkdtemp()
        test_file_path = os.path.join(test_dir, "test_file.txt")
        
        # Create test file
        with open(test_file_path, "wb") as f:
            f.write(test_content)
        
        # Mock CID for testing
        test_cid = "QmTestCID123456789"
        
        yield api, test_content, test_dir, test_file_path, test_cid
        
        # Cleanup
        shutil.rmtree(test_dir)
    
    @patch.object(IPFSSimpleAPI, 'cat')
    async def test_stream_media_async(self, mock_cat, setup):
        """Test async streaming media content."""
        api, test_content, _, _, test_cid = await setup
        
        # Setup mock
        mock_cat.return_value = test_content
        
        # Test the async streaming method
        chunks = []
        async for chunk in api.stream_media_async(test_cid, chunk_size=1024):
            chunks.append(chunk)
        
        # Verify all content was received in chunks
        received_content = b''.join(chunks)
        assert received_content == test_content
        
        # Verify cat was called
        mock_cat.assert_called_once_with(test_cid)
    
    @patch.object(IPFSSimpleAPI, 'add')
    async def test_stream_to_ipfs_async(self, mock_add, setup):
        """Test async streaming content to IPFS."""
        api, test_content, _, _, test_cid = await setup
        
        # Setup mock
        mock_add.return_value = {"Hash": test_cid}
        
        # Create a file-like object for streaming
        file_obj = io.BytesIO(test_content)
        
        # Test the async streaming upload method
        result = await api.stream_to_ipfs_async(file_obj, chunk_size=1024)
        
        # Verify result
        assert result.get("Hash") == test_cid
        
        # Verify add was called
        mock_add.assert_called_once()
@pytest.mark.asyncio
class TestWebSocketStreaming:
    """Test WebSocket streaming functionality."""
    
    @pytest.fixture(autouse=True)
    async def setup_and_cleanup(self, event_loop):
        """Setup and cleanup fixture that runs for each test."""
        # Use the provided event loop
        asyncio.set_event_loop(event_loop)
        yield
        # Clean up the loop
        pending = asyncio.all_tasks(event_loop)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        await event_loop.shutdown_asyncgens()
    
    @pytest.fixture
    async def setup(self):
        """Set up test environment."""
        api = IPFSSimpleAPI()
        test_content = b"Test content for WebSocket streaming" * 1000  # ~38KB
        test_dir = tempfile.mkdtemp()
        test_file_path = os.path.join(test_dir, "test_file.txt")
        
        # Create test file
        with open(test_file_path, "wb") as f:
            f.write(test_content)
        
        # Mock CID for testing
        test_cid = "QmTestCID123456789"
        
        yield api, test_content, test_dir, test_file_path, test_cid
        
        # Cleanup
        shutil.rmtree(test_dir)
    
    @pytest.mark.asyncio
    @patch.object(IPFSSimpleAPI, 'cat')
    async def test_websocket_media_stream(self, mock_cat, setup):
        """Test WebSocket media streaming."""
        api, test_content, _, _, test_cid = await setup
        
        # Setup mock
        mock_cat.return_value = test_content
        
        # Create mock WebSocket
        mock_websocket = AsyncMock()
        mock_websocket.receive_json.return_value = {
            "type": "request",
            "path": test_cid
        }
        
        # Mock the websocket accept method
        mock_websocket.accept = AsyncMock()
        
        # Test the WebSocket streaming handler
        await api.handle_websocket_media_stream(mock_websocket, test_cid)
        
        # Check that send_bytes was called multiple times (for chunked delivery)
        # We can't check exact content due to the async nature
        assert mock_websocket.send_bytes.call_count > 0
        
        # Verify metadata was sent
        mock_websocket.send_json.assert_called()
        # The first call should be metadata
        first_call_args = mock_websocket.send_json.call_args_list[0][0][0]
        assert first_call_args["type"] == "metadata"
        assert "content_length" in first_call_args
        assert first_call_args["content_length"] == len(test_content)
    
    @pytest.mark.asyncio
    @patch.object(IPFSSimpleAPI, 'add')
    async def test_websocket_upload_stream(self, mock_add, setup):
        """Test WebSocket upload streaming."""
        api, test_content, _, _, test_cid = await setup
        
        # Setup mock
        mock_add.return_value = {"Hash": test_cid}
        
        # Create mock WebSocket
        mock_websocket = AsyncMock()
        
        # Setup the receive sequence:
        # 1. First a metadata message
        # 2. Then one or more content chunks
        # 3. Finally a "complete" message
        
        # Create a queue of messages to return
        message_queue = asyncio.Queue()
        
        # Add metadata message
        await message_queue.put({
            "type": "metadata",
            "filename": "test_file.txt",
            "content_type": "text/plain",
            "content_length": len(test_content)
        })
        
        # Add content chunks (simulate chunked delivery)
        chunk_size = 1024
        for i in range(0, len(test_content), chunk_size):
            chunk = test_content[i:i+chunk_size]
            await message_queue.put(chunk)
        
        # Add complete message
        await message_queue.put({
            "type": "complete"
        })
        # Define side effects to simulate receiving messages
        async def receive_json_side_effect():
            if not message_queue.empty():
                item = await message_queue.get()
                if isinstance(item, dict):
                    return item
                else:
                    # If we get bytes, we should return from receive_bytes next time
                    mock_websocket.receive_bytes.return_value = item
                    # And return a placeholder here
                    return {"type": "content_chunk"}
            return {"type": "error", "message": "No more messages"}
        
        mock_websocket.receive_json.side_effect = receive_json_side_effect
        
        # Mock the websocket accept method
        mock_websocket.accept = AsyncMock()
        
        # Test the WebSocket upload handler
        await api.handle_websocket_upload_stream(mock_websocket)
        
        # Verify accept was called
        mock_websocket.accept.assert_called_once()
        
        # Verify add was called
        mock_add.assert_called_once()
        
        # Verify success response was sent
        mock_websocket.send_json.assert_called()
        # The last call should be the success response with CID
        last_call_args = mock_websocket.send_json.call_args_list[-1][0][0]
        assert last_call_args["type"] == "success"
        assert last_call_args["cid"] == test_cid
        api, test_content, _, _, test_cid = setup
        # Verify success response was sent
        mock_websocket.send_json.assert_called()
        # The last call should be the success response with CID
        last_call_args = mock_websocket.send_json.call_args_list[-1][0][0]
        assert last_call_args["type"] == "success"
        assert last_call_args["cid"] == test_cid
        # Use a more robust timeout mechanism
        try:
            async with asyncio.timeout(5):  # 5 seconds timeout
                # Setup mocks
                mock_cat.return_value = test_content
                mock_add.return_value = {"Hash": test_cid}
                
                # Create mock WebSocket with cleanup context
                mock_websocket = AsyncMock()
                mock_websocket.close = AsyncMock()
                
                # Setup the receive sequence for commands
                command_queue = asyncio.Queue()
                
                # Add a 'get' command
                await command_queue.put({
                    "command": "get",
                    "path": test_cid
                })
                
                # Add an 'add' command
                await command_queue.put({
                    "command": "add",
                    "filename": "test_file.txt",
                    "content_type": "text/plain",
                    "content_length": len(test_content)
                })
                
                # Add content chunks for the 'add' command
                chunk_size = 1024
                for i in range(0, len(test_content), chunk_size):
                    chunk = test_content[i:i+chunk_size]
                    await command_queue.put(chunk)
                
                # Add a 'complete' message for the 'add' command
                await command_queue.put({
                    "command": "complete"
                })
                
                # Define side effects to simulate receiving messages
                async def receive_json_side_effect():
                    if not command_queue.empty():
                        item = await command_queue.get()
                        if isinstance(item, dict):
                            return item
                        else:
                            # If we get bytes, we should return from receive_bytes next time
                            mock_websocket.receive_bytes.return_value = item
                            # And return a placeholder here
                            return {"command": "content_chunk"}
                    return {"command": "exit"}
                
                mock_websocket.receive_json.side_effect = receive_json_side_effect
                
                # Mock the websocket accept method
                mock_websocket.accept = AsyncMock()
                
                # Test the WebSocket bidirectional handler
                await api.handle_websocket_bidirectional_stream(mock_websocket)
                
                # Verify accept was called
                mock_websocket.accept.assert_called_once()
                
                # Verify both cat and add were called
                mock_cat.assert_called_once_with(test_cid)
                mock_add.assert_called_once()
                
                # Verify send_json was called multiple times (for responses to commands)
                assert mock_websocket.send_json.call_count > 0
                # Ensure WebSocket is closed and resources are cleaned up
                await mock_websocket.close()
                assert mock_websocket.send_bytes.call_count > 0
        except asyncio.TimeoutError:
            # Handle timeout gracefully
            await mock_websocket.close()
            pytest.fail("Test timed out after 5 seconds")
        finally:
            # Clean up any remaining tasks
            for task in asyncio.all_tasks():
                if task is not asyncio.current_task():
                    task.cancel()
            
            assert mock_websocket.send_bytes.call_count > 0
