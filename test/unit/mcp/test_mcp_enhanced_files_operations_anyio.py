"""
Comprehensive tests for enhanced MFS (Mutable File System) operations in the MCP server with AnyIO support.

This test file provides thorough testing for all MFS operations including the enhanced operations:
- files_write: Write content to a file
- files_read: Read content from a file
- files_rm: Remove files/directories
- files_cp: Copy files/directories
- files_mv: Move/rename files/directories
- files_flush: Flush changes to IPFS
"""

import json
import time
import logging
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import anyio
import sniffio
from fastapi import FastAPI, Body
from fastapi.testclient import TestClient

from ipfs_kit_py.mcp_server.models.ipfs_model import IPFSModel
from ipfs_kit_py.mcp_server.controllers.ipfs_controller_anyio import (
    IPFSControllerAnyIO, WriteFileRequest, ReadFileRequest, 
    RemoveFileRequest, CopyFileRequest, MoveFileRequest, 
    FlushFilesRequest
)
from ipfs_kit_py.mcp_server.controllers.ipfs_controller import MakeDirRequest

# Configure logger
logger = logging.getLogger(__name__)

# Define the minimal controller class for testing enhanced MFS operations
class MinimalIPFSControllerAnyIO:
    """Minimal IPFS controller with enhanced MFS operations for testing."""
    
    def __init__(self, ipfs_model):
        self.ipfs_model = ipfs_model
        logger.info("Minimal IPFS Controller (AnyIO) initialized")
    
    def register_routes(self, router):
        """Register enhanced MFS routes for testing."""
        # Core MFS endpoints
        router.add_api_route(
            "/ipfs/files/ls",
            self.list_files,
            methods=["POST", "GET"],
            summary="List files",
            description="List files in the MFS (Mutable File System) directory"
        )
        
        router.add_api_route(
            "/ipfs/files/stat",
            self.stat_file,
            methods=["POST", "GET"],
            summary="Get file information",
            description="Get information about a file or directory in MFS"
        )
        
        router.add_api_route(
            "/ipfs/files/mkdir",
            self.make_directory,
            methods=["POST"],
            summary="Create directory",
            description="Create a directory in the MFS (Mutable File System)"
        )
        
        # Enhanced MFS endpoints
        router.add_api_route(
            "/ipfs/files/write",
            self.write_file,
            methods=["POST"],
            summary="Write to file",
            description="Write content to a file in the MFS (Mutable File System)"
        )
        
        router.add_api_route(
            "/ipfs/files/read",
            self.read_file,
            methods=["GET", "POST"],
            summary="Read file",
            description="Read content from a file in the MFS (Mutable File System)"
        )
        
        router.add_api_route(
            "/ipfs/files/rm",
            self.remove_file,
            methods=["POST"],
            summary="Remove file",
            description="Remove a file or directory from the MFS (Mutable File System)"
        )
        
        router.add_api_route(
            "/ipfs/files/cp",
            self.copy_file,
            methods=["POST"],
            summary="Copy file",
            description="Copy a file or directory within the MFS (Mutable File System)"
        )
        
        router.add_api_route(
            "/ipfs/files/mv",
            self.move_file,
            methods=["POST"],
            summary="Move file",
            description="Move a file or directory within the MFS (Mutable File System)"
        )
        
        router.add_api_route(
            "/ipfs/files/flush",
            self.flush_files,
            methods=["POST"],
            summary="Flush files",
            description="Flush changes in the MFS (Mutable File System) to IPFS"
        )
        
        logger.info("Enhanced IPFS Controller (AnyIO) routes registered")
    
    @staticmethod
    def get_backend():
        """Get the current async backend being used."""
        try:
            return sniffio.current_async_library()
        except sniffio.AsyncLibraryNotFoundError:
            return None
    
    # Core MFS methods
    async def list_files(self, path: str = "/", long: bool = False):
        """List files in MFS."""
        return await self._call_mfs_method("list_files", self.ipfs_model.ipfs.files_ls, path, long)
    
    async def stat_file(self, path: str):
        """Get file information in MFS."""
        return await self._call_mfs_method("stat_file", self.ipfs_model.ipfs.files_stat, path)
    
    async def make_directory(self, request: MakeDirRequest = Body(...)):
        """Create directory in MFS."""
        path = request.path
        parents = request.parents
        return await self._call_mfs_method("make_directory", self.ipfs_model.ipfs.files_mkdir, path, parents)
    
    # Enhanced MFS methods
    async def write_file(self, request: WriteFileRequest = Body(...)):
        """Write content to a file in MFS."""
        path = request.path
        content = request.content.encode('utf-8') if isinstance(request.content, str) else request.content
        offset = request.offset
        create = request.create
        truncate = request.truncate
        parents = request.parents
        
        return await self._call_mfs_method(
            "write_file", 
            self.ipfs_model.ipfs.files_write, 
            path, content, offset, create, truncate, parents
        )
    
    async def read_file(self, path: str = None, offset: int = 0, count: int = -1, request: ReadFileRequest = None):
        """Read content from a file in MFS."""
        # Use request parameters if provided (POST), otherwise use query parameters (GET)
        if request is not None:
            path = request.path
            offset = request.offset
            count = request.count
        elif path is None:
            # Both request and path are None, return error
            return {
                "success": False,
                "error": "Path is required",
                "error_type": "ValidationError",
                "timestamp": time.time()
            }
            
        return await self._call_mfs_method(
            "read_file", 
            self.ipfs_model.ipfs.files_read, 
            path, offset=offset, count=count
        )
    
    async def remove_file(self, request: RemoveFileRequest = Body(...)):
        """Remove a file or directory from MFS."""
        path = request.path
        recursive = request.recursive
        force = request.force
        
        return await self._call_mfs_method(
            "remove_file", 
            self.ipfs_model.ipfs.files_rm, 
            path, recursive, force
        )
    
    async def copy_file(self, request: CopyFileRequest = Body(...)):
        """Copy a file or directory within MFS."""
        source = request.source
        destination = request.destination
        parents = request.parents
        
        return await self._call_mfs_method(
            "copy_file", 
            self.ipfs_model.ipfs.files_cp, 
            source, destination, parents
        )
    
    async def move_file(self, request: MoveFileRequest = Body(...)):
        """Move/rename a file or directory within MFS."""
        source = request.source
        destination = request.destination
        parents = request.parents
        
        return await self._call_mfs_method(
            "move_file", 
            self.ipfs_model.ipfs.files_mv, 
            source, destination, parents
        )
    
    async def flush_files(self, request: FlushFilesRequest = Body(...)):
        """Flush changes in MFS to IPFS."""
        path = request.path
        
        return await self._call_mfs_method(
            "flush_files", 
            self.ipfs_model.ipfs.files_flush, 
            path
        )
    
    async def _call_mfs_method(self, operation, method, *args, **kwargs):
        """Generic method to call MFS operations with proper error handling."""
        # Start timing for operation metrics
        start_time = time.time()
        operation_id = f"{operation}_{int(start_time * 1000)}"
        
        try:
            # Call the method asynchronously
            if hasattr(method, "__await__"):
                # Method is already async
                result = await method(*args, **kwargs)
            else:
                # Run synchronous method in a thread
                result = await anyio.to_thread.run_sync(method, *args, **kwargs)
            
            # Format the result based on the operation
            if operation == "list_files":
                if isinstance(result, dict) and "Entries" in result:
                    return {
                        "success": True,
                        "operation_id": operation_id,
                        "timestamp": time.time(),
                        "path": args[0],  # path
                        "long": args[1],  # long
                        "entries": result.get("Entries", []),
                        "duration_ms": (time.time() - start_time) * 1000
                    }
            elif operation == "stat_file":
                if isinstance(result, dict) and "Hash" in result:
                    return {
                        "success": True,
                        "operation_id": operation_id,
                        "timestamp": time.time(),
                        "path": args[0],  # path
                        "hash": result.get("Hash"),
                        "size": result.get("Size", 0),
                        "cumulative_size": result.get("CumulativeSize", 0),
                        "blocks": result.get("Blocks", 0),
                        "type": result.get("Type", "unknown"),
                        "with_locality": result.get("WithLocality", False),
                        "duration_ms": (time.time() - start_time) * 1000
                    }
            elif operation == "make_directory":
                # Empty result means success for mkdir
                return {
                    "success": True,
                    "operation_id": operation_id,
                    "timestamp": time.time(),
                    "path": args[0],  # path
                    "parents": args[1],  # parents
                    "duration_ms": (time.time() - start_time) * 1000
                }
            elif operation == "write_file":
                # Format write result
                return {
                    "success": True,
                    "operation_id": operation_id,
                    "timestamp": time.time(),
                    "path": args[0],  # path
                    "size": len(args[1]),  # content
                    "offset": args[2],  # offset
                    "create": args[3],  # create
                    "truncate": args[4],  # truncate
                    "parents": args[5],  # parents
                    "duration_ms": (time.time() - start_time) * 1000
                }
            elif operation == "read_file":
                # Handle binary content
                if isinstance(result, bytes):
                    try:
                        content = result.decode('utf-8')
                    except UnicodeDecodeError:
                        content = str(result)
                        
                    return {
                        "success": True,
                        "operation_id": operation_id,
                        "timestamp": time.time(),
                        "path": args[0],  # path
                        "offset": kwargs.get("offset", 0),
                        "count": kwargs.get("count", -1),
                        "size": len(result),
                        "content": content,
                        "duration_ms": (time.time() - start_time) * 1000
                    }
            elif operation == "remove_file":
                # Format remove result
                return {
                    "success": True,
                    "operation_id": operation_id,
                    "timestamp": time.time(),
                    "path": args[0],  # path
                    "recursive": args[1],  # recursive
                    "force": args[2],  # force
                    "duration_ms": (time.time() - start_time) * 1000
                }
            elif operation == "copy_file":
                # Format copy result
                return {
                    "success": True,
                    "operation_id": operation_id,
                    "timestamp": time.time(),
                    "source": args[0],  # source
                    "destination": args[1],  # destination
                    "parents": args[2],  # parents
                    "duration_ms": (time.time() - start_time) * 1000
                }
            elif operation == "move_file":
                # Format move result
                return {
                    "success": True,
                    "operation_id": operation_id,
                    "timestamp": time.time(),
                    "source": args[0],  # source
                    "destination": args[1],  # destination
                    "parents": args[2],  # parents
                    "duration_ms": (time.time() - start_time) * 1000
                }
            elif operation == "flush_files":
                # Format flush result with CID
                if isinstance(result, str) and result.startswith("Qm"):
                    return {
                        "success": True,
                        "operation_id": operation_id,
                        "timestamp": time.time(),
                        "path": args[0],  # path
                        "cid": result,
                        "duration_ms": (time.time() - start_time) * 1000
                    }
                elif isinstance(result, dict) and "Cid" in result:
                    return {
                        "success": True,
                        "operation_id": operation_id,
                        "timestamp": time.time(),
                        "path": args[0],  # path
                        "cid": result["Cid"],
                        "duration_ms": (time.time() - start_time) * 1000
                    }
            
            # Default return if specific formatting not available
            return {
                "success": True,
                "operation_id": operation_id,
                "timestamp": time.time(),
                "result": result,
                "duration_ms": (time.time() - start_time) * 1000
            }
            
        except Exception as e:
            # Log the error for debugging
            logger.error(f"Error in {operation}: {str(e)}")
            
            # Return error in standard format
            error_result = {
                "success": False,
                "operation_id": operation_id,
                "timestamp": time.time(),
                "error": str(e),
                "error_type": type(e).__name__,
                "duration_ms": (time.time() - start_time) * 1000
            }
            
            # Add operation-specific fields
            if operation == "list_files":
                error_result["path"] = args[0]
                error_result["long"] = args[1]
            elif operation == "stat_file":
                error_result["path"] = args[0]
            elif operation == "make_directory":
                error_result["path"] = args[0]
                error_result["parents"] = args[1]
            elif operation == "write_file":
                error_result["path"] = args[0]
            elif operation == "read_file":
                error_result["path"] = args[0]
            elif operation == "remove_file":
                error_result["path"] = args[0]
            elif operation == "copy_file" or operation == "move_file":
                error_result["source"] = args[0]
                error_result["destination"] = args[1]
            elif operation == "flush_files":
                error_result["path"] = args[0]
            
            return error_result


@pytest.mark.anyio
class TestMCPEnhancedFilesOperationsAnyIO:
    """Comprehensive tests for enhanced Mutable File System (MFS) operations with AnyIO support."""
    
    @pytest.fixture(autouse=True)
    async def setup(self):
        """Set up the test environment with mocked components."""
        # Create mock IPFS kit
        self.mock_ipfs_kit = MagicMock()
        
        # Set up core mock MFS methods
        self.mock_ipfs_kit.files_ls = MagicMock()
        self.mock_ipfs_kit.files_stat = MagicMock()
        self.mock_ipfs_kit.files_mkdir = MagicMock()
        
        # Set up enhanced mock MFS methods
        self.mock_ipfs_kit.files_write = MagicMock()
        self.mock_ipfs_kit.files_read = MagicMock()
        self.mock_ipfs_kit.files_rm = MagicMock()
        self.mock_ipfs_kit.files_cp = MagicMock()
        self.mock_ipfs_kit.files_mv = MagicMock()
        self.mock_ipfs_kit.files_flush = MagicMock()
        
        # Configure core mock responses
        self.mock_ipfs_kit.files_ls.return_value = {
            "Entries": [
                {
                    "Name": "file1.txt",
                    "Type": 0,
                    "Size": 1024,
                    "Hash": "QmFileHash1"
                },
                {
                    "Name": "dir1",
                    "Type": 1,
                    "Size": 0,
                    "Hash": "QmDirHash1"
                }
            ]
        }
        
        self.mock_ipfs_kit.files_stat.return_value = {
            "Hash": "QmTestFileHash",
            "Size": 2048,
            "CumulativeSize": 2100,
            "Blocks": 1,
            "Type": "file",
            "WithLocality": False
        }
        
        self.mock_ipfs_kit.files_mkdir.return_value = {}  # Empty response indicates success
        
        # Configure enhanced mock responses
        self.mock_ipfs_kit.files_write.return_value = {}  # Empty response indicates success
        self.mock_ipfs_kit.files_read.return_value = b"Test file content"
        self.mock_ipfs_kit.files_rm.return_value = {}  # Empty response indicates success
        self.mock_ipfs_kit.files_cp.return_value = {}  # Empty response indicates success
        self.mock_ipfs_kit.files_mv.return_value = {}  # Empty response indicates success
        self.mock_ipfs_kit.files_flush.return_value = "QmFlushResultHash"  # CID as string
        
        # Create IPFS model with mock kit
        self.ipfs_model = IPFSModel(ipfs_kit_instance=self.mock_ipfs_kit)
        
        # Create controller with the model
        self.controller = MinimalIPFSControllerAnyIO(self.ipfs_model)
        
        # Create FastAPI app with router
        self.app = FastAPI()
        self.router = self.app.router
        self.controller.register_routes(self.router)
        
        # Create test client
        self.client = TestClient(self.app)
        
        # Mock the time module to control timestamps
        self.original_time = time.time
        time.time = MagicMock(return_value=1609459200.0)  # 2021-01-01 00:00:00 UTC
        
        yield
        
        # Cleanup after tests
        time.time = self.original_time
    
    @pytest.mark.anyio
    async def test_write_file_success(self):
        """Test successful MFS files_write operation with AnyIO."""
        # Make request to write file endpoint
        request_data = {
            "path": "/test/new_file.txt",
            "content": "This is test content",
            "offset": 0,
            "create": True,
            "truncate": True,
            "parents": True
        }
        response = self.client.post("/ipfs/files/write", json=request_data)
        
        # Validate response
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "operation_id" in data
        assert "timestamp" in data
        assert data["path"] == "/test/new_file.txt"
        assert "size" in data
        assert data["offset"] == 0
        assert data["create"] is True
        assert data["truncate"] is True
        assert data["parents"] is True
        
        # Verify the mock was called with correct arguments
        self.mock_ipfs_kit.files_write.assert_called_once()
        args, kwargs = self.mock_ipfs_kit.files_write.call_args
        assert args[0] == "/test/new_file.txt"  # path
        assert args[1] == b"This is test content"  # content (as bytes)
        assert args[2] == 0  # offset
        assert args[3] is True  # create
        assert args[4] is True  # truncate
        assert args[5] is True  # parents
    
    @pytest.mark.anyio
    async def test_write_file_error(self):
        """Test error handling in MFS files_write operation with AnyIO."""
        # Configure mock to raise exception
        self.mock_ipfs_kit.files_write.side_effect = Exception("Test error writing file")
        
        # Make request to write file endpoint
        request_data = {
            "path": "/test/new_file.txt",
            "content": "This is test content",
            "offset": 0,
            "create": True,
            "truncate": True,
            "parents": True
        }
        response = self.client.post("/ipfs/files/write", json=request_data)
        
        # Validate response
        assert response.status_code == 200  # API still returns 200 for compatibility
        data = response.json()
        
        assert data["success"] is False
        assert "operation_id" in data
        assert "timestamp" in data
        assert data["path"] == "/test/new_file.txt"
        assert "error" in data
        assert "Test error writing file" in data["error"]
    
    @pytest.mark.anyio
    async def test_read_file_success(self):
        """Test successful MFS files_read operation with AnyIO."""
        # Make request to read file endpoint
        response = self.client.get("/ipfs/files/read?path=/test/file.txt")
        
        # Validate response
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "operation_id" in data
        assert "timestamp" in data
        assert data["path"] == "/test/file.txt"
        assert data["content"] == "Test file content"
        assert data["size"] == len(b"Test file content")
        
        # Verify the mock was called with correct arguments
        self.mock_ipfs_kit.files_read.assert_called_once()
    
    @pytest.mark.anyio
    async def test_read_file_with_offset_and_count(self):
        """Test MFS files_read operation with offset and count parameters."""
        # Make request with offset and count
        response = self.client.get("/ipfs/files/read?path=/test/file.txt&offset=5&count=4")
        
        # Validate response
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["path"] == "/test/file.txt"
        assert data["offset"] == 5
        assert data["count"] == 4
        
        # Verify the mock was called with correct keyword arguments
        args, kwargs = self.mock_ipfs_kit.files_read.call_args
        assert args[0] == "/test/file.txt"  # path
        assert kwargs["offset"] == 5
        assert kwargs["count"] == 4
    
    @pytest.mark.anyio
    async def test_read_file_post_request(self):
        """Test MFS files_read operation with POST request."""
        # Make request with POST body
        request_data = {
            "path": "/test/file.txt",
            "offset": 10,
            "count": 20
        }
        response = self.client.post("/ipfs/files/read", json=request_data)
        
        # Validate response
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["path"] == "/test/file.txt"
        assert data["offset"] == 10
        assert data["count"] == 20
        
        # Verify the mock was called with correct keyword arguments
        args, kwargs = self.mock_ipfs_kit.files_read.call_args
        assert args[0] == "/test/file.txt"  # path
        assert kwargs["offset"] == 10
        assert kwargs["count"] == 20
    
    @pytest.mark.anyio
    async def test_read_file_error(self):
        """Test error handling in MFS files_read operation with AnyIO."""
        # Configure mock to raise exception
        self.mock_ipfs_kit.files_read.side_effect = Exception("Test error reading file")
        
        # Make request to read file endpoint
        response = self.client.get("/ipfs/files/read?path=/test/file.txt")
        
        # Validate response
        assert response.status_code == 200  # API still returns 200 for compatibility
        data = response.json()
        
        assert data["success"] is False
        assert "operation_id" in data
        assert "timestamp" in data
        assert data["path"] == "/test/file.txt"
        assert "error" in data
        assert "Test error reading file" in data["error"]
    
    @pytest.mark.anyio
    async def test_remove_file_success(self):
        """Test successful MFS files_rm operation with AnyIO."""
        # Make request to remove file endpoint
        request_data = {
            "path": "/test/file_to_remove.txt",
            "recursive": False,
            "force": False
        }
        response = self.client.post("/ipfs/files/rm", json=request_data)
        
        # Validate response
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "operation_id" in data
        assert "timestamp" in data
        assert data["path"] == "/test/file_to_remove.txt"
        assert data["recursive"] is False
        assert data["force"] is False
        
        # Verify the mock was called with correct arguments
        self.mock_ipfs_kit.files_rm.assert_called_once()
        args, kwargs = self.mock_ipfs_kit.files_rm.call_args
        assert args[0] == "/test/file_to_remove.txt"  # path
        assert args[1] is False  # recursive
        assert args[2] is False  # force
    
    @pytest.mark.anyio
    async def test_remove_directory_recursive(self):
        """Test MFS files_rm operation with recursive flag for directory removal."""
        # Make request with recursive flag
        request_data = {
            "path": "/test/directory_to_remove",
            "recursive": True,
            "force": False
        }
        response = self.client.post("/ipfs/files/rm", json=request_data)
        
        # Validate response
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["path"] == "/test/directory_to_remove"
        assert data["recursive"] is True
        
        # Verify the mock was called with correct arguments
        args, kwargs = self.mock_ipfs_kit.files_rm.call_args
        assert args[0] == "/test/directory_to_remove"  # path
        assert args[1] is True  # recursive
    
    @pytest.mark.anyio
    async def test_remove_file_error(self):
        """Test error handling in MFS files_rm operation with AnyIO."""
        # Configure mock to raise exception
        self.mock_ipfs_kit.files_rm.side_effect = Exception("Test error removing file")
        
        # Make request to remove file endpoint
        request_data = {
            "path": "/test/file_to_remove.txt",
            "recursive": False,
            "force": False
        }
        response = self.client.post("/ipfs/files/rm", json=request_data)
        
        # Validate response
        assert response.status_code == 200  # API still returns 200 for compatibility
        data = response.json()
        
        assert data["success"] is False
        assert "operation_id" in data
        assert "timestamp" in data
        assert data["path"] == "/test/file_to_remove.txt"
        assert "error" in data
        assert "Test error removing file" in data["error"]
    
    @pytest.mark.anyio
    async def test_copy_file_success(self):
        """Test successful MFS files_cp operation with AnyIO."""
        # Make request to copy file endpoint
        request_data = {
            "source": "/test/source.txt",
            "destination": "/test/destination.txt",
            "parents": False
        }
        response = self.client.post("/ipfs/files/cp", json=request_data)
        
        # Validate response
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "operation_id" in data
        assert "timestamp" in data
        assert data["source"] == "/test/source.txt"
        assert data["destination"] == "/test/destination.txt"
        assert data["parents"] is False
        
        # Verify the mock was called with correct arguments
        self.mock_ipfs_kit.files_cp.assert_called_once()
        args, kwargs = self.mock_ipfs_kit.files_cp.call_args
        assert args[0] == "/test/source.txt"  # source
        assert args[1] == "/test/destination.txt"  # destination
        assert args[2] is False  # parents
    
    @pytest.mark.anyio
    async def test_copy_file_with_parents(self):
        """Test MFS files_cp operation with parents flag."""
        # Make request with parents flag
        request_data = {
            "source": "/test/source.txt",
            "destination": "/test/new/path/destination.txt",
            "parents": True
        }
        response = self.client.post("/ipfs/files/cp", json=request_data)
        
        # Validate response
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["source"] == "/test/source.txt"
        assert data["destination"] == "/test/new/path/destination.txt"
        assert data["parents"] is True
        
        # Verify the mock was called with correct arguments
        args, kwargs = self.mock_ipfs_kit.files_cp.call_args
        assert args[0] == "/test/source.txt"  # source
        assert args[1] == "/test/new/path/destination.txt"  # destination
        assert args[2] is True  # parents
    
    @pytest.mark.anyio
    async def test_copy_file_error(self):
        """Test error handling in MFS files_cp operation with AnyIO."""
        # Configure mock to raise exception
        self.mock_ipfs_kit.files_cp.side_effect = Exception("Test error copying file")
        
        # Make request to copy file endpoint
        request_data = {
            "source": "/test/source.txt",
            "destination": "/test/destination.txt",
            "parents": False
        }
        response = self.client.post("/ipfs/files/cp", json=request_data)
        
        # Validate response
        assert response.status_code == 200  # API still returns 200 for compatibility
        data = response.json()
        
        assert data["success"] is False
        assert "operation_id" in data
        assert "timestamp" in data
        assert data["source"] == "/test/source.txt"
        assert data["destination"] == "/test/destination.txt"
        assert "error" in data
        assert "Test error copying file" in data["error"]
    
    @pytest.mark.anyio
    async def test_move_file_success(self):
        """Test successful MFS files_mv operation with AnyIO."""
        # Make request to move file endpoint
        request_data = {
            "source": "/test/source.txt",
            "destination": "/test/new_name.txt",
            "parents": False
        }
        response = self.client.post("/ipfs/files/mv", json=request_data)
        
        # Validate response
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "operation_id" in data
        assert "timestamp" in data
        assert data["source"] == "/test/source.txt"
        assert data["destination"] == "/test/new_name.txt"
        assert data["parents"] is False
        
        # Verify the mock was called with correct arguments
        self.mock_ipfs_kit.files_mv.assert_called_once()
        args, kwargs = self.mock_ipfs_kit.files_mv.call_args
        assert args[0] == "/test/source.txt"  # source
        assert args[1] == "/test/new_name.txt"  # destination
        assert args[2] is False  # parents
    
    @pytest.mark.anyio
    async def test_move_file_with_parents(self):
        """Test MFS files_mv operation with parents flag."""
        # Make request with parents flag
        request_data = {
            "source": "/test/source.txt",
            "destination": "/test/new/path/new_name.txt",
            "parents": True
        }
        response = self.client.post("/ipfs/files/mv", json=request_data)
        
        # Validate response
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["source"] == "/test/source.txt"
        assert data["destination"] == "/test/new/path/new_name.txt"
        assert data["parents"] is True
        
        # Verify the mock was called with correct arguments
        args, kwargs = self.mock_ipfs_kit.files_mv.call_args
        assert args[0] == "/test/source.txt"  # source
        assert args[1] == "/test/new/path/new_name.txt"  # destination
        assert args[2] is True  # parents
    
    @pytest.mark.anyio
    async def test_move_file_error(self):
        """Test error handling in MFS files_mv operation with AnyIO."""
        # Configure mock to raise exception
        self.mock_ipfs_kit.files_mv.side_effect = Exception("Test error moving file")
        
        # Make request to move file endpoint
        request_data = {
            "source": "/test/source.txt",
            "destination": "/test/new_name.txt",
            "parents": False
        }
        response = self.client.post("/ipfs/files/mv", json=request_data)
        
        # Validate response
        assert response.status_code == 200  # API still returns 200 for compatibility
        data = response.json()
        
        assert data["success"] is False
        assert "operation_id" in data
        assert "timestamp" in data
        assert data["source"] == "/test/source.txt"
        assert data["destination"] == "/test/new_name.txt"
        assert "error" in data
        assert "Test error moving file" in data["error"]
    
    @pytest.mark.anyio
    async def test_flush_files_success(self):
        """Test successful MFS files_flush operation with AnyIO."""
        # Make request to flush files endpoint
        request_data = {
            "path": "/test/directory"
        }
        response = self.client.post("/ipfs/files/flush", json=request_data)
        
        # Validate response
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "operation_id" in data
        assert "timestamp" in data
        assert data["path"] == "/test/directory"
        assert "cid" in data
        assert data["cid"] == "QmFlushResultHash"
        
        # Verify the mock was called with correct arguments
        self.mock_ipfs_kit.files_flush.assert_called_once()
        args, kwargs = self.mock_ipfs_kit.files_flush.call_args
        assert args[0] == "/test/directory"  # path
    
    @pytest.mark.anyio
    async def test_flush_root_directory(self):
        """Test MFS files_flush operation on root directory."""
        # Make request for root directory
        request_data = {
            "path": "/"
        }
        response = self.client.post("/ipfs/files/flush", json=request_data)
        
        # Validate response
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["path"] == "/"
        assert "cid" in data
        assert data["cid"] == "QmFlushResultHash"
        
        # Verify the mock was called with correct arguments
        args, kwargs = self.mock_ipfs_kit.files_flush.call_args
        assert args[0] == "/"  # path
    
    @pytest.mark.anyio
    async def test_flush_files_error(self):
        """Test error handling in MFS files_flush operation with AnyIO."""
        # Configure mock to raise exception
        self.mock_ipfs_kit.files_flush.side_effect = Exception("Test error flushing files")
        
        # Make request to flush files endpoint
        request_data = {
            "path": "/test/directory"
        }
        response = self.client.post("/ipfs/files/flush", json=request_data)
        
        # Validate response
        assert response.status_code == 200  # API still returns 200 for compatibility
        data = response.json()
        
        assert data["success"] is False
        assert "operation_id" in data
        assert "timestamp" in data
        assert data["path"] == "/test/directory"
        assert "error" in data
        assert "Test error flushing files" in data["error"]
    
    @pytest.mark.anyio
    async def test_concurrent_file_operations(self):
        """Test running multiple MFS operations concurrently."""
        # Configure mocks with predictable responses
        self.mock_ipfs_kit.files_read.return_value = b"Test file content"
        self.mock_ipfs_kit.files_stat.return_value = {
            "Hash": "QmFileHash",
            "Size": 1024,
            "CumulativeSize": 1100,
            "Blocks": 1,
            "Type": "file"
        }
        self.mock_ipfs_kit.files_ls.return_value = {
            "Entries": [{"Name": "file1.txt", "Type": 0, "Hash": "QmHash1"}]
        }
        
        # Run concurrent operations with anyio
        async def run_concurrent_operations():
            results = {}
            
            async with anyio.create_task_group() as tg:
                # Function to run read operation and store result
                async def run_read(path, results_dict):
                    response = self.client.get(f"/ipfs/files/read?path={path}")
                    results_dict[f"read-{path}"] = response.json()
                
                # Function to run stat operation and store result
                async def run_stat(path, results_dict):
                    response = self.client.get(f"/ipfs/files/stat?path={path}")
                    results_dict[f"stat-{path}"] = response.json()
                
                # Function to run ls operation and store result
                async def run_ls(path, results_dict):
                    response = self.client.get(f"/ipfs/files/ls?path={path}")
                    results_dict[f"ls-{path}"] = response.json()
                
                # Start multiple operations concurrently
                for i in range(3):
                    path = f"/test/path{i}"
                    file_path = f"/test/file{i}.txt"
                    
                    # Start tasks
                    tg.start_soon(run_read, file_path, results)
                    tg.start_soon(run_stat, file_path, results)
                    tg.start_soon(run_ls, path, results)
            
            return results
        
        # Execute concurrent operations
        results = await run_concurrent_operations()
        
        # Verify we got results for all operations
        assert len(results) == 9  # 3 paths x 3 operation types
        
        # Check read results
        for i in range(3):
            path = f"/test/file{i}.txt"
            assert results[f"read-{path}"]["success"] is True
            assert results[f"read-{path}"]["content"] == "Test file content"
            
        # Check stat results
        for i in range(3):
            path = f"/test/file{i}.txt"
            assert results[f"stat-{path}"]["success"] is True
            assert results[f"stat-{path}"]["hash"] == "QmFileHash"
            
        # Check ls results
        for i in range(3):
            path = f"/test/path{i}"
            assert results[f"ls-{path}"]["success"] is True
            assert len(results[f"ls-{path}"]["entries"]) == 1
    
    @pytest.mark.anyio
    async def test_files_operations_with_sync_compatibility(self):
        """Test compatibility between sync and async MFS methods across operations."""
        # Create a test model with both sync and async methods
        test_model = MagicMock()
        
        # Add core sync methods
        test_model.ipfs = MagicMock()
        test_model.ipfs.files_ls = MagicMock(return_value={"Entries": [{"Name": "sync-file.txt"}]})
        test_model.ipfs.files_stat = MagicMock(return_value={"Hash": "QmSyncHash", "Size": 1024})
        test_model.ipfs.files_mkdir = MagicMock(return_value={})
        
        # Add enhanced sync methods
        test_model.ipfs.files_write = MagicMock(return_value={})
        test_model.ipfs.files_read = MagicMock(return_value=b"Sync content")
        test_model.ipfs.files_rm = MagicMock(return_value={})
        test_model.ipfs.files_cp = MagicMock(return_value={})
        test_model.ipfs.files_mv = MagicMock(return_value={})
        test_model.ipfs.files_flush = MagicMock(return_value="QmSyncFlushHash")
        
        # Add core async methods
        test_model.ipfs.files_ls_async = AsyncMock(return_value={"Entries": [{"Name": "async-file.txt"}]})
        test_model.ipfs.files_stat_async = AsyncMock(return_value={"Hash": "QmAsyncHash", "Size": 2048})
        test_model.ipfs.files_mkdir_async = AsyncMock(return_value={})
        
        # Add enhanced async methods
        test_model.ipfs.files_write_async = AsyncMock(return_value={})
        test_model.ipfs.files_read_async = AsyncMock(return_value=b"Async content")
        test_model.ipfs.files_rm_async = AsyncMock(return_value={})
        test_model.ipfs.files_cp_async = AsyncMock(return_value={})
        test_model.ipfs.files_mv_async = AsyncMock(return_value={})
        test_model.ipfs.files_flush_async = AsyncMock(return_value="QmAsyncFlushHash")
        
        # Create our minimal controller with this model
        test_controller = MinimalIPFSControllerAnyIO(test_model)
        
        # Create a test app with just enhanced MFS endpoints
        app = FastAPI()
        
        @app.get("/ipfs/files/read")
        async def read_file_endpoint(path: str = "/"):
            return await test_controller.read_file(path=path)
        
        @app.post("/ipfs/files/write")
        async def write_file_endpoint(request: WriteFileRequest):
            return await test_controller.write_file(request=request)
        
        @app.post("/ipfs/files/cp")
        async def copy_file_endpoint(request: CopyFileRequest):
            return await test_controller.copy_file(request=request)
        
        @app.post("/ipfs/files/flush")
        async def flush_files_endpoint(request: FlushFilesRequest):
            return await test_controller.flush_files(request=request)
        
        # Create test client
        client = TestClient(app)
        
        # Test read method - should use async version
        response = client.get("/ipfs/files/read?path=/test.txt")
        data = response.json()
        assert data["success"] is True
        assert "Async content" in data["content"]
        assert test_model.ipfs.files_read_async.called
        assert not test_model.ipfs.files_read.called
        
        # Test write method - should use async version
        write_data = {"path": "/write.txt", "content": "Test", "offset": 0, "create": True, "truncate": True, "parents": False}
        response = client.post("/ipfs/files/write", json=write_data)
        assert response.status_code == 200
        assert test_model.ipfs.files_write_async.called
        assert not test_model.ipfs.files_write.called
        
        # Test copy method - should use async version
        copy_data = {"source": "/src.txt", "destination": "/dst.txt", "parents": False}
        response = client.post("/ipfs/files/cp", json=copy_data)
        assert response.status_code == 200
        assert test_model.ipfs.files_cp_async.called
        assert not test_model.ipfs.files_cp.called
        
        # Test flush method - should use async version
        flush_data = {"path": "/"}
        response = client.post("/ipfs/files/flush", json=flush_data)
        assert response.status_code == 200
        data = response.json()
        assert data["cid"] == "QmAsyncFlushHash"
        assert test_model.ipfs.files_flush_async.called
        assert not test_model.ipfs.files_flush.called
        
        # Now test fallback to sync methods by removing async methods
        test_model.ipfs.files_read_async = None
        test_model.ipfs.files_write_async = None
        test_model.ipfs.files_cp_async = None
        test_model.ipfs.files_flush_async = None
        
        # Test read method - should fall back to sync version
        response = client.get("/ipfs/files/read?path=/test.txt")
        data = response.json()
        assert data["success"] is True
        assert "Sync content" in data["content"]
        assert test_model.ipfs.files_read.called
        
        # Test write method - should fall back to sync version
        write_data = {"path": "/write2.txt", "content": "Test2", "offset": 0, "create": True, "truncate": True, "parents": False}
        response = client.post("/ipfs/files/write", json=write_data)
        assert response.status_code == 200
        assert test_model.ipfs.files_write.called
        
        # Test copy method - should fall back to sync version
        copy_data = {"source": "/src2.txt", "destination": "/dst2.txt", "parents": False}
        response = client.post("/ipfs/files/cp", json=copy_data)
        assert response.status_code == 200
        assert test_model.ipfs.files_cp.called
        
        # Test flush method - should fall back to sync version
        flush_data = {"path": "/test"}
        response = client.post("/ipfs/files/flush", json=flush_data)
        assert response.status_code == 200
        data = response.json()
        assert data["cid"] == "QmSyncFlushHash"
        assert test_model.ipfs.files_flush.called