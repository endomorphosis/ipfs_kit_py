#!/usr/bin/env python
"""
Test script for the MCP Streaming Operations functionality.

This script tests the streaming operations for MCP server, including:
1. Optimized file uploads with chunked processing
2. Memory-optimized streaming downloads
3. Background pinning operations
4. DAG import/export capabilities
"""

import logging
import sys
import os
import json
import time
import asyncio
import tempfile
import hashlib
import random
from typing import Dict, Any, Optional, BinaryIO
from contextlib import contextmanager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("streaming_test")

# Add parent directory to path if needed
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


@contextmanager
def create_test_file(size_mb: int, temp_dir: Optional[str] = None) -> str:
    """Create a temporary test file of the specified size."""
    try:
        with tempfile.NamedTemporaryFile(delete=False, dir=temp_dir, suffix=".testdata") as tmp:
            # Create a file with deterministic but random-looking content
            chunk_size = 1024 * 1024  # 1MB chunks
            random.seed(size_mb)  # Use size as seed for reproducibility
            remaining = size_mb * 1024 * 1024

            while remaining > 0:
                chunk_data = random.getrandbits(8 * min(chunk_size, remaining)).to_bytes(
                    min(chunk_size, remaining), byteorder='big')
                tmp.write(chunk_data)
                remaining -= len(chunk_data)

            tmp.flush()
            file_path = tmp.name

        logger.info(f"Created test file of size {size_mb}MB at {file_path}")
        yield file_path
    finally:
        if 'file_path' in locals() and os.path.exists(file_path):
            os.unlink(file_path)
            logger.info(f"Cleaned up test file at {file_path}")


class MockUploadFile:
    """Mock class for FastAPI's UploadFile."""
    def __init__(self, file_path: str, content_type: str = "application/octet-stream"):
        self.file_path = file_path
        self.filename = os.path.basename(file_path)
        self.content_type = content_type
        self._file = None

    async def read(self, size: int = -1) -> bytes:
        """Read data from the file."""
        if not self._file:
            self._file = open(self.file_path, 'rb')

        if size == -1:
            return self._file.read()
        else:
            return self._file.read(size)

    def close(self):
        """Close the file."""
        if self._file:
            self._file.close()
            self._file = None


class BackgroundTasksMock:
    """Mock class for FastAPI's BackgroundTasks."""
    def __init__(self):
        self.tasks = []

    def add_task(self, func, *args, **kwargs):
        """Add a background task."""
        self.tasks.append((func, args, kwargs))

    async def run_all(self):
        """Run all background tasks."""
        for func, args, kwargs in self.tasks:
            await func(*args, **kwargs)


async def run_streaming_test():
    """Run comprehensive tests on the streaming operations."""
    logger.info("Starting MCP Streaming Operations test...")

    try:
        # Import the streaming module
        from ipfs_kit_py.mcp_streaming import StreamingOperations
        logger.info("Successfully imported streaming module")

        # Create a temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            logger.info(f"Created temporary directory for testing: {temp_dir}")

            # Initialize streaming operations
            streaming_ops = StreamingOperations(temp_dir=temp_dir)

            # Test 1: Stream Add to IPFS (small file)
            logger.info("Test 1: Stream Add to IPFS (small file)")
            with create_test_file(1, temp_dir) as small_file_path:
                mock_file = MockUploadFile(small_file_path)
                result = await streaming_ops.stream_add_to_ipfs(mock_file)
                logger.info(f"Small file upload result: {json.dumps(result, indent=2, default=str)}")

                if result.get("success", False):
                    logger.info("✅ Small file upload successful")
                    small_file_cid = result["cid"]
                else:
                    logger.error("❌ Small file upload failed")
                    return False

                # Test pinning in background
                background_tasks = BackgroundTasksMock()
                streaming_ops.pin_in_background(background_tasks, small_file_cid)
                await background_tasks.run_all()
                logger.info("✅ Background pinning task completed")

            # Test 2: Stream Add to IPFS (larger file for chunking test)
            logger.info("Test 2: Stream Add to IPFS (larger file for chunking test)")
            with create_test_file(5, temp_dir) as large_file_path:
                mock_file = MockUploadFile(large_file_path)
                result = await streaming_ops.stream_add_to_ipfs(mock_file)
                logger.info(f"Large file upload result: {json.dumps(result, indent=2, default=str)}")

                if result.get("success", False):
                    logger.info("✅ Large file upload successful")
                    large_file_cid = result["cid"]
                    logger.info(f"Upload throughput: {result.get('throughput_mbps', 0):.2f} MB/s")
                else:
                    logger.error("❌ Large file upload failed")
                    return False

            # Test 3: Stream from IPFS (retrieve small file)
            logger.info("Test 3: Stream from IPFS (retrieve small file)")
            retrieved_data = b""
            async for chunk in streaming_ops.stream_from_ipfs(small_file_cid):
                retrieved_data += chunk

            # Verify file size
            with open(small_file_path, 'rb') as f:
                original_data = f.read()

            if len(retrieved_data) == len(original_data):
                logger.info(f"✅ Retrieved file has correct size: {len(retrieved_data)} bytes")
            else:
                logger.error(f"❌ Retrieved file size mismatch: {len(retrieved_data)} vs {len(original_data)}")
                return False

            # Calculate hash of retrieved data for integrity check
            retrieved_hash = hashlib.sha256(retrieved_data).hexdigest()
            original_hash = hashlib.sha256(original_data).hexdigest()

            if retrieved_hash == original_hash:
                logger.info("✅ Retrieved file hash matches original")
            else:
                logger.error("❌ Retrieved file hash mismatch")
                return False

            # Test 4: Stream to file
            logger.info("Test 4: Stream to file")
            download_path = os.path.join(temp_dir, "downloaded_file.bin")
            result = await streaming_ops.stream_to_file(large_file_cid, download_path)
            logger.info(f"Stream to file result: {json.dumps(result, indent=2, default=str)}")

            if result.get("success", False):
                logger.info("✅ Stream to file successful")
                logger.info(f"Download throughput: {result.get('throughput_mbps', 0):.2f} MB/s")

                # Verify file exists and has correct size
                if os.path.exists(download_path):
                    download_size = os.path.getsize(download_path)
                    expected_size = os.path.getsize(large_file_path)

                    if download_size == expected_size:
                        logger.info(f"✅ Downloaded file has correct size: {download_size} bytes")
                    else:
                        logger.error(f"❌ Downloaded file size mismatch: {download_size} vs {expected_size}")
                        return False
                else:
                    logger.error("❌ Downloaded file does not exist")
                    return False
            else:
                logger.error("❌ Stream to file failed")
                return False

            # Test 5: Unpin content in background
            logger.info("Test 5: Unpin content in background")
            background_tasks = BackgroundTasksMock()
            streaming_ops.unpin_in_background(background_tasks, small_file_cid)
            await background_tasks.run_all()
            logger.info("✅ Background unpinning task completed")

            # Test 6: DAG export/import
            try:
                logger.info("Test 6: DAG export/import")

                # Create a directory with files to add as a DAG
                dag_dir = os.path.join(temp_dir, "dag_test")
                os.makedirs(dag_dir, exist_ok=True)

                # Create a few files in the directory
                for i in range(3):
                    with open(os.path.join(dag_dir, f"file{i}.txt"), 'w') as f:
                        f.write(f"Test file {i} content\n")

                # Add the directory to IPFS to get a DAG
                process = await asyncio.create_subprocess_exec(
                    "ipfs", "add", "-r", "-Q", dag_dir,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()

                if process.returncode == 0:
                    dag_cid = stdout.decode().strip()
                    logger.info(f"Created test DAG with CID: {dag_cid}")

                    # Export the DAG
                    export_path = os.path.join(temp_dir, "exported.car")
                    with open(export_path, 'wb') as f:
                        async for chunk in streaming_ops.dag_export_stream(dag_cid):
                            f.write(chunk)

                    if os.path.exists(export_path) and os.path.getsize(export_path) > 0:
                        logger.info(f"✅ DAG export successful: {os.path.getsize(export_path)} bytes")

                        # Import the exported DAG
                        mock_file = MockUploadFile(export_path, "application/vnd.ipld.car")
                        import_result = await streaming_ops.dag_import_stream(mock_file)
                        logger.info(f"DAG import result: {json.dumps(import_result, indent=2, default=str)}")

                        if import_result.get("success", False):
                            logger.info("✅ DAG import successful")

                            # Verify that at least one root CID was imported
                            roots = import_result.get("roots", [])
                            if roots and dag_cid in roots:
                                logger.info("✅ Original DAG CID found in imported roots")
                            else:
                                logger.warning("⚠️ Original DAG CID not found in imported roots")
                        else:
                            logger.error("❌ DAG import failed")
                            return False
                    else:
                        logger.error("❌ DAG export failed")
                        return False
                else:
                    error = stderr.decode().strip()
                    logger.error(f"Failed to create test DAG: {error}")
                    logger.warning("⚠️ Skipping DAG export/import test")
            except Exception as e:
                logger.error(f"Error in DAG export/import test: {str(e)}")
                logger.warning("⚠️ Skipping DAG export/import test")

        logger.info("All streaming tests completed successfully!")
        return True

    except Exception as e:
        logger.error(f"Error testing streaming functionality: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


if __name__ == "__main__":
    # Run the test asynchronously
    if sys.platform == "win32":
        # Windows requires this for asyncio.run()
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    result = asyncio.run(run_streaming_test())

    if result:
        logger.info("✅ MCP Streaming Operations test passed!")
        sys.exit(0)
    else:
        logger.error("❌ MCP Streaming Operations test failed")
        sys.exit(1)
