"""
Enhanced streaming operations for MCP server.

This module implements optimized streaming operations for handling large files,
including efficient uploads, downloads, and chunked processing.
"""

import os
import time
import anyio
import logging
import tempfile
import hashlib
from typing import Dict, Any, Optional, List, AsyncGenerator, Union, BinaryIO
from fastapi import FastAPI, APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, Response
from starlette.requests import Request
from starlette.responses import FileResponse
import aiofiles
import aiohttp
import subprocess

# Configure logging
logger = logging.getLogger(__name__)

# Default chunk size for streaming (1MB)
DEFAULT_CHUNK_SIZE = 1024 * 1024

class StreamingOperations:
    """
    Class for handling streaming operations with IPFS.

    This class provides optimized methods for streaming large files to and from IPFS,
    with efficient memory usage and progress tracking.
    """

    def __init__(self, temp_dir: Optional[str] = None, chunk_size: int = DEFAULT_CHUNK_SIZE):
        """
        Initialize the streaming operations.

        Args:
            temp_dir: Directory for temporary files (uses system temp if None)
            chunk_size: Chunk size for streaming operations in bytes
        """
        self.temp_dir = temp_dir
        self.chunk_size = chunk_size

        # Create temp dir if specified and doesn't exist
        if self.temp_dir and not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir, exist_ok=True)

    async def stream_add_to_ipfs(self, file: UploadFile) -> Dict[str, Any]:
        """
        Stream a file to IPFS with optimized memory usage.

        Args:
            file: The file to upload

        Returns:
            Dict with upload results including CID
        """
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False, dir=self.temp_dir) as temp:
            temp_path = temp.name

        try:
            # Stream the file to disk in chunks
            size = 0
            hash_obj = hashlib.sha256()  # For integrity verification

            async with aiofiles.open(temp_path, 'wb') as f:
                while chunk := await file.read(self.chunk_size):
                    await f.write(chunk)
                    size += len(chunk)
                    hash_obj.update(chunk)

            file_hash = hash_obj.hexdigest()

            # Add the file to IPFS
            start_time = time.time()
            process = await anyio.open_process(
                ["ipfs", "add", "-Q", temp_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error = stderr.decode().strip()
                logger.error(f"Error adding file to IPFS: {error}")
                raise Exception(f"Failed to add file to IPFS: {error}")

            cid = stdout.decode().strip()
            duration = time.time() - start_time

            # Return detailed information
            return {
                "success": True,
                "cid": cid,
                "size": size,
                "name": file.filename,
                "content_type": file.content_type,
                "hash": file_hash,
                "duration": duration,
                "throughput_mbps": (size / duration) / (1024 * 1024) if duration > 0 else 0
            }
        finally:
            # Clean up the temporary file
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    async def stream_from_ipfs(self, cid: str) -> AsyncGenerator[bytes, None]:
        """
        Stream content from IPFS with optimized memory usage.

        Args:
            cid: Content identifier to retrieve

        Yields:
            Chunks of binary data
        """
        # Create a subprocess to stream data directly from IPFS
        process = await anyio.open_process(
            ["ipfs", "cat", cid],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Check if the process started successfully
        if process.stdout is None:
            stderr = await process.stderr.read() if process.stderr else b""
            error = stderr.decode().strip()
            logger.error(f"Error starting IPFS cat: {error}")
            raise Exception(f"Failed to retrieve content from IPFS: {error}")

        # Stream the output in chunks
        while True:
            chunk = await process.stdout.read(self.chunk_size)
            if not chunk:
                break
            yield chunk

        # Check if the process completed successfully
        await process.wait()
        if process.returncode != 0:
            stderr = await process.stderr.read() if process.stderr else b""
            error = stderr.decode().strip()
            logger.error(f"Error in IPFS cat: {error}")
            # We already yielded some data, so we can't raise an exception here
            # The response might be incomplete, but we've already started streaming

    async def stream_to_file(self, cid: str, file_path: str) -> Dict[str, Any]:
        """
        Stream content from IPFS to a file with progress tracking.

        Args:
            cid: Content identifier to retrieve
            file_path: Path to save the file to

        Returns:
            Dict with download results
        """
        start_time = time.time()
        size = 0
        hash_obj = hashlib.sha256()  # For integrity verification

        # Ensure the directory exists
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)

        async with aiofiles.open(file_path, 'wb') as f:
            async for chunk in self.stream_from_ipfs(cid):
                await f.write(chunk)
                size += len(chunk)
                hash_obj.update(chunk)

        duration = time.time() - start_time
        file_hash = hash_obj.hexdigest()

        return {
            "success": True,
            "cid": cid,
            "file_path": file_path,
            "size": size,
            "hash": file_hash,
            "duration": duration,
            "throughput_mbps": (size / duration) / (1024 * 1024) if duration > 0 else 0
        }

    def pin_in_background(self, background_tasks: BackgroundTasks, cid: str) -> None:
        """
        Add a background task to pin content.

        Args:
            background_tasks: FastAPI BackgroundTasks
            cid: Content identifier to pin
        """
        background_tasks.add_task(self._pin_content, cid)

    async def _pin_content(self, cid: str) -> Dict[str, Any]:
        """
        Pin content in IPFS asynchronously.

        Args:
            cid: Content identifier to pin

        Returns:
            Dict with pin results
        """
        start_time = time.time()

        process = await anyio.open_process(
            ["ipfs", "pin", "add", cid],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        duration = time.time() - start_time

        if process.returncode != 0:
            error = stderr.decode().strip()
            logger.error(f"Error pinning content {cid}: {error}")
            return {
                "success": False,
                "cid": cid,
                "error": error,
                "duration": duration
            }

        return {
            "success": True,
            "cid": cid,
            "pinned": True,
            "duration": duration
        }

    async def unpin_in_background(self, background_tasks: BackgroundTasks, cid: str) -> None:
        """
        Add a background task to unpin content.

        Args:
            background_tasks: FastAPI BackgroundTasks
            cid: Content identifier to unpin
        """
        background_tasks.add_task(self._unpin_content, cid)

    async def _unpin_content(self, cid: str) -> Dict[str, Any]:
        """
        Unpin content from IPFS asynchronously.

        Args:
            cid: Content identifier to unpin

        Returns:
            Dict with unpin results
        """
        process = await anyio.open_process(
            ["ipfs", "pin", "rm", cid],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error = stderr.decode().strip()
            logger.error(f"Error unpinning content {cid}: {error}")
            return {
                "success": False,
                "cid": cid,
                "error": error
            }

        return {
            "success": True,
            "cid": cid,
            "unpinned": True
        }

    async def dag_export_stream(self, cid: str) -> AsyncGenerator[bytes, None]:
        """
        Stream a DAG export from IPFS.

        Args:
            cid: Root CID of the DAG to export

        Yields:
            Chunks of the CAR file
        """
        process = await anyio.open_process(
            ["ipfs", "dag", "export", cid],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        if process.stdout is None:
            stderr = await process.stderr.read() if process.stderr else b""
            error = stderr.decode().strip()
            logger.error(f"Error starting DAG export: {error}")
            raise Exception(f"Failed to export DAG from IPFS: {error}")

        # Stream the output in chunks
        while True:
            chunk = await process.stdout.read(self.chunk_size)
            if not chunk:
                break
            yield chunk

        # Check if the process completed successfully
        await process.wait()
        if process.returncode != 0:
            stderr = await process.stderr.read() if process.stderr else b""
            error = stderr.decode().strip()
            logger.error(f"Error in DAG export: {error}")

    async def dag_import_stream(self, file: UploadFile) -> Dict[str, Any]:
        """
        Stream a CAR file import to IPFS.

        Args:
            file: CAR file to import

        Returns:
            Dict with import results
        """
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False, dir=self.temp_dir) as temp:
            temp_path = temp.name

        try:
            # Stream the file to disk in chunks
            size = 0
            async with aiofiles.open(temp_path, 'wb') as f:
                while chunk := await file.read(self.chunk_size):
                    await f.write(chunk)
                    size += len(chunk)

            # Import the DAG
            start_time = time.time()
            process = await anyio.open_process(
                ["ipfs", "dag", "import", temp_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error = stderr.decode().strip()
                logger.error(f"Error importing DAG: {error}")
                raise Exception(f"Failed to import DAG to IPFS: {error}")

            output = stdout.decode().strip()
            duration = time.time() - start_time

            # Parse the output to get root CIDs
            roots = []
            for line in output.split('\n'):
                if line and "root" in line:
                    parts = line.split()
                    if len(parts) >= 3:
                        roots.append(parts[2])

            return {
                "success": True,
                "imported": True,
                "roots": roots,
                "size": size,
                "duration": duration,
                "throughput_mbps": (size / duration) / (1024 * 1024) if duration > 0 else 0
            }
        finally:
            # Clean up the temporary file
            if os.path.exists(temp_path):
                os.unlink(temp_path)

# Create FastAPI router for streaming endpoints

def create_streaming_router(api_prefix: str) -> APIRouter:
    """
    Create a FastAPI router with optimized streaming endpoints.

    Args:
        api_prefix: The API prefix for the endpoints

    Returns:
        FastAPI router
    """
    router = APIRouter(prefix=f"{api_prefix}/stream")
    streaming_ops = StreamingOperations()

    @router.post("/add")
    async def stream_add(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
        """
        Stream a file to IPFS with optimized memory usage.

        Args:
            file: The file to upload
            background_tasks: Optional background tasks for pinning
        """
        result = await streaming_ops.stream_add_to_ipfs(file)

        # Pin the content in the background if requested
        if background_tasks:
            streaming_ops.pin_in_background(background_tasks, result["cid"])
            result["pinning"] = "in_progress"

        return result

    @router.get("/cat/{cid}")
    async def stream_cat(cid: str, filename: Optional[str] = None):
        """
        Stream content from IPFS with optimized memory usage.

        Args:
            cid: Content identifier to retrieve
            filename: Optional filename for the content disposition header
        """
        # Determine the filename
        if not filename:
            filename = f"{cid}.bin"

        # Create the response headers
        headers = {
            "Content-Disposition": f"attachment; filename=\"{filename}\""
        }

        # Return a streaming response
        return StreamingResponse(
            streaming_ops.stream_from_ipfs(cid),
            media_type="application/octet-stream",
            headers=headers
        )

    @router.post("/download")
    async def stream_download(cid: str = Form(...), path: str = Form(...)):
        """
        Stream content from IPFS to a file with progress tracking.

        Args:
            cid: Content identifier to retrieve
            path: Path to save the file to
        """
        # Validate the path to prevent directory traversal
        abs_path = os.path.abspath(path)
        if not abs_path.startswith(os.path.abspath(os.getcwd())):
            raise HTTPException(status_code=400, detail="Path must be within the current directory")

        result = await streaming_ops.stream_to_file(cid, abs_path)
        return result

    @router.post("/pin")
    async def stream_pin(cid: str = Form(...), background_tasks: BackgroundTasks = None):
        """
        Pin content in IPFS.

        Args:
            cid: Content identifier to pin
            background_tasks: Optional background tasks for pinning
        """
        if background_tasks:
            streaming_ops.pin_in_background(background_tasks, cid)
            return {
                "success": True,
                "cid": cid,
                "pinning": "in_progress"
            }
        else:
            # Do it synchronously if no background tasks
            return await streaming_ops._pin_content(cid)

    @router.post("/unpin")
    async def stream_unpin(cid: str = Form(...), background_tasks: BackgroundTasks = None):
        """
        Unpin content from IPFS.

        Args:
            cid: Content identifier to unpin
            background_tasks: Optional background tasks for unpinning
        """
        if background_tasks:
            streaming_ops.unpin_in_background(background_tasks, cid)
            return {
                "success": True,
                "cid": cid,
                "unpinning": "in_progress"
            }
        else:
            # Do it synchronously if no background tasks
            return await streaming_ops._unpin_content(cid)

    @router.get("/dag/export/{cid}")
    async def stream_dag_export(cid: str, filename: Optional[str] = None):
        """
        Stream a DAG export from IPFS.

        Args:
            cid: Root CID of the DAG to export
            filename: Optional filename for the content disposition header
        """
        # Determine the filename
        if not filename:
            filename = f"{cid}.car"

        # Create the response headers
        headers = {
            "Content-Disposition": f"attachment; filename=\"{filename}\""
        }

        # Return a streaming response
        return StreamingResponse(
            streaming_ops.dag_export_stream(cid),
            media_type="application/vnd.ipld.car",
            headers=headers
        )

    @router.post("/dag/import")
    async def stream_dag_import(file: UploadFile = File(...)):
        """
        Stream a CAR file import to IPFS.

        Args:
            file: CAR file to import
        """
        result = await streaming_ops.dag_import_stream(file)
        return result

    return router
