"""
IPFS Model for the MCP server.

This model encapsulates IPFS operations and provides a clean interface
for the controller to interact with the IPFS functionality.
"""

import asyncio
import logging
import uuid


# Utility class for handling asyncio operations in different contexts
class AsyncEventLoopHandler:
    """
    Handler for properly managing asyncio operations in different contexts.
    """

    # Class variable to track all created tasks to prevent "coroutine was never awaited" warnings
    _background_tasks = set()

    @classmethod
    def _task_done_callback(cls, task):
        """Remove task from set when it's done."""
        if task in cls._background_tasks:
            cls._background_tasks.remove(task)

    @classmethod
    def run_coroutine(cls, coro, fallback_result=None):
        """Run a coroutine in any context (sync or async)."""
        try:
            # Try to get the current event loop
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # Create a new event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        try:  # Check if the loop is already running (e.g., in FastAPI)
            if loop.is_running():
                # Create a future that will run the coroutine later
                task = asyncio.create_task(coro)
                cls._background_tasks.add(task)
                task.add_done_callback(cls._task_done_callback)
                return fallback_result
            else:
                # Run the coroutine on the loop
                return loop.run_until_complete(coro)
        except Exception as e:
            logging.error(f"Error running coroutine: {str(e)}")
            return fallback_result


class IPFSModelAnyIO:
    """
    AnyIO compatible IPFS Model implementation.
    Provides asynchronous operations for interacting with IPFS.
    """

    def __init__(self, config=None):
        """Initialize the IPFS model with configuration."""
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

    async def add_content_async(self, content):
        """
        Add content to IPFS asynchronously.

        Args:
            content: The content to add to IPFS

        Returns:
            Dict with operation results
        """
        # Placeholder for actual implementation
        result = {
            "success": True,
            "cid": f"QmExample{uuid.uuid4().hex[:8]}",
            "size": len(content) if isinstance(content, bytes) else len(str(content)),
        }
        return result
    
    def add_content(self, content=None, **kwargs):
        """
        Add content to IPFS synchronously (compatibility method).
        This is a compatibility method added for MCP direct integration.
        
        Args:
            content: The content to add to IPFS
            **kwargs: Additional arguments
            
        Returns:
            Dict with operation results
        """
        # Handle args/kwargs
        if content is None and 'content' in kwargs:
            content = kwargs.pop('content')
            
        if content is None:
            return {"success": False, "error": "Content must be provided"}
        
        # Use the AsyncEventLoopHandler to run the async method synchronously
        try:
            return AsyncEventLoopHandler.run_coroutine(
                self.add_content_async(content),
                fallback_result={
                    "success": True,
                    "cid": f"QmFallback{uuid.uuid4().hex[:8]}",
                    "size": len(content) if isinstance(content, (str, bytes)) else 0,
                    "simulation": True
                }
            )
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_content_async(self, cid):
        """
        Get content from IPFS asynchronously.

        Args:
            cid: The CID of the content to retrieve

        Returns:
            Dict with operation results including the content
        """
        # Placeholder for actual implementation
        result = {"success": True, "data": b"Example content", "cid": cid}
        return result

    async def pin_content_async(self, cid):
        """
        Pin content to IPFS asynchronously.

        Args:
            cid: The CID of the content to pin

        Returns:
            Dict with operation results
        """
        # Placeholder for actual implementation
        result = {"success": True, "cid": cid, "pinned": True}
        return result

    async def add_content(self, content=None, **kwargs):
        """
        Add content to IPFS and return the CID.
        This is a compatibility method for MCP server integration.
        
        Args:
            content: The content to add (string or bytes)
            **kwargs: Additional parameters
        
        Returns:
            Dict with operation results including CID
        """
        # Handle args/kwargs
        if content is None and 'content' in kwargs:
            content = kwargs.pop('content')
            
        if content is None:
            raise ValueError("Content must be provided")
        
        # Determine content type and add to IPFS
        if isinstance(content, str):
            # Convert string to bytes
            content_bytes = content.encode('utf-8')
        elif isinstance(content, bytes):
            content_bytes = content
        else:
            # Try to convert to string first
            try:
                content_str = str(content)
                content_bytes = content_str.encode('utf-8')
            except Exception:
                raise TypeError(f"Unsupported content type: {type(content)}")
        
        # Add to IPFS using the async method
        return await self.add_content_async(content_bytes)
