"""
Network stream interface for libp2p.

This module provides interfaces and implementations for working with
network streams in the libp2p networking stack.
"""

# Import anyio first
import anyio
import logging
from typing import Optional, Union, List, Dict, Any, Callable, Awaitable

# Import or define compatibility types if needed
try:
    from anyio import StreamReader, StreamWriter
except ImportError:
    # Define protocol types if not available in anyio
    from typing import Protocol
    
    class StreamReader(Protocol):
        """Protocol for stream reading operations."""
        
        async def read(self, max_bytes: int = -1) -> bytes:
            """Read up to max_bytes from the stream."""
            ...
            
        async def read_exact(self, nbytes: int) -> bytes:
            """Read exactly nbytes from the stream."""
            ...
            
        async def read_until(self, delimiter: bytes, max_bytes: int = -1) -> bytes:
            """Read until delimiter is found."""
            ...
    
    
    class StreamWriter(Protocol):
        """Protocol for stream writing operations."""
        
        def write(self, data: bytes) -> None:
            """Write data to the stream."""
            ...
            
        async def drain(self) -> None:
            """Flush the write buffer."""
            ...
            
        def close(self) -> None:
            """Close the stream."""
            ...
            
        async def wait_closed(self) -> None:
            """Wait until the stream is closed."""
            ...
    
    # Make these types available through anyio module for API compatibility
    anyio.StreamReader = StreamReader
    anyio.StreamWriter = StreamWriter

# Set up logger
logger = logging.getLogger(__name__)

class INetStream:
    """Interface for network streams."""
    
    async def read(self, max_size: Optional[int] = None) -> bytes:
        """
        Read data from the stream.
        
        Args:
            max_size: Optional maximum number of bytes to read
            
        Returns:
            The data read from the stream
            
        Raises:
            EOFError: If the stream is closed
            StreamError: If there's an error reading from the stream
        """
        raise NotImplementedError("read must be implemented by subclass")
        
    async def write(self, data: bytes) -> int:
        """
        Write data to the stream.
        
        Args:
            data: The data to write
            
        Returns:
            The number of bytes written
            
        Raises:
            StreamError: If there's an error writing to the stream
        """
        raise NotImplementedError("write must be implemented by subclass")
        
    async def close(self) -> None:
        """
        Close the stream.
        
        Raises:
            StreamError: If there's an error closing the stream
        """
        raise NotImplementedError("close must be implemented by subclass")
        
    async def reset(self) -> None:
        """
        Reset the stream.
        
        This method abruptly terminates the stream, typically used
        for error scenarios.
        
        Raises:
            StreamError: If there's an error resetting the stream
        """
        raise NotImplementedError("reset must be implemented by subclass")
        
    def get_protocol(self) -> str:
        """
        Get the protocol ID for this stream.
        
        Returns:
            The protocol ID string
        """
        raise NotImplementedError("get_protocol must be implemented by subclass")
        
    def set_protocol(self, protocol_id: str) -> None:
        """
        Set the protocol ID for this stream.
        
        Args:
            protocol_id: The protocol ID string
        """
        raise NotImplementedError("set_protocol must be implemented by subclass")
        
    def get_peer(self) -> str:
        """
        Get the peer ID for this stream.
        
        Returns:
            The peer ID string
        """
        raise NotImplementedError("get_peer must be implemented by subclass")

class NetStream(INetStream):
    """
    Default implementation of a network stream.
    
    This class provides a concrete implementation of the INetStream
    interface using Python's asyncio capabilities.
    """
    
    def __init__(self, reader: anyio.StreamReader, writer: anyio.StreamWriter, 
                 protocol_id: str, peer_id: str):
        """
        Initialize a new network stream.
        
        Args:
            reader: The asyncio StreamReader
            writer: The asyncio StreamWriter
            protocol_id: The protocol ID string
            peer_id: The peer ID string
        """
        self.reader = reader
        self.writer = writer
        self._protocol_id = protocol_id
        self._peer_id = peer_id
        self._closed = False
        
    async def read(self, max_size: Optional[int] = None) -> bytes:
        """
        Read data from the stream.
        
        Args:
            max_size: Optional maximum number of bytes to read
            
        Returns:
            The data read from the stream
            
        Raises:
            EOFError: If the stream is closed
            StreamError: If there's an error reading from the stream
        """
        if self._closed:
            raise EOFError("Stream is closed")
            
        try:
            if max_size is None:
                # Read until EOF with a reasonable chunk size
                chunks = []
                while True:
                    chunk = await self.reader.read(16384)  # 16KB chunks
                    if not chunk:  # EOF
                        break
                    chunks.append(chunk)
                return b''.join(chunks)
            else:
                # Read specified number of bytes
                return await self.reader.read(max_size)
        except Exception as e:
            logger.error(f"Error reading from stream: {e}")
            await self.reset()
            raise StreamError(f"Error reading from stream: {e}")
        
    async def write(self, data: bytes) -> int:
        """
        Write data to the stream.
        
        Args:
            data: The data to write
            
        Returns:
            The number of bytes written
            
        Raises:
            StreamError: If there's an error writing to the stream
        """
        if self._closed:
            raise StreamError("Cannot write to closed stream")
            
        try:
            self.writer.write(data)
            await self.writer.drain()
            return len(data)
        except Exception as e:
            logger.error(f"Error writing to stream: {e}")
            await self.reset()
            raise StreamError(f"Error writing to stream: {e}")
        
    async def close(self) -> None:
        """
        Close the stream.
        
        Raises:
            StreamError: If there's an error closing the stream
        """
        if self._closed:
            return
            
        try:
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except (AttributeError, NotImplementedError):
                # Some asyncio implementations don't have wait_closed
                pass
            self._closed = True
        except Exception as e:
            logger.error(f"Error closing stream: {e}")
            raise StreamError(f"Error closing stream: {e}")
        
    async def reset(self) -> None:
        """
        Reset the stream.
        
        This method abruptly terminates the stream, typically used
        for error scenarios.
        
        Raises:
            StreamError: If there's an error resetting the stream
        """
        try:
            # In asyncio, there's no direct "reset" concept, so we just close
            # the connection abruptly without proper shutdown
            self.writer.close()
            self._closed = True
        except Exception as e:
            logger.error(f"Error resetting stream: {e}")
            raise StreamError(f"Error resetting stream: {e}")
        
    def get_protocol(self) -> str:
        """
        Get the protocol ID for this stream.
        
        Returns:
            The protocol ID string
        """
        return self._protocol_id
        
    def set_protocol(self, protocol_id: str) -> None:
        """
        Set the protocol ID for this stream.
        
        Args:
            protocol_id: The protocol ID string
        """
        self._protocol_id = protocol_id
        
    def get_peer(self) -> str:
        """
        Get the peer ID for this stream.
        
        Returns:
            The peer ID string
        """
        return self._peer_id
        
class StreamError(Exception):
    """Error related to stream operations."""
    pass

class StreamHandler:
    """
    Handler for stream protocol handlers.
    
    This class helps manage protocol-specific handlers for incoming streams.
    """
    
    def __init__(self, protocol_id: str, handler_func: Callable[[INetStream], Awaitable[None]]):
        """
        Initialize a new stream handler.
        
        Args:
            protocol_id: The protocol ID this handler is for
            handler_func: The function to call for incoming streams
        """
        self.protocol_id = protocol_id
        self.handler_func = handler_func
        
    async def handle_stream(self, stream: INetStream) -> None:
        """
        Handle an incoming stream.
        
        Args:
            stream: The stream to handle
        """
        try:
            await self.handler_func(stream)
        except Exception as e:
            logger.error(f"Error in stream handler for protocol {self.protocol_id}: {e}")
            try:
                await stream.reset()
            except:
                # Ignore errors in reset
                pass