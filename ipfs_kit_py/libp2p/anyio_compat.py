"""
AnyIO compatibility module to provide missing StreamReader and StreamWriter classes.

This module adds backward compatibility for code expecting anyio.StreamReader
and anyio.StreamWriter attributes that may not be present in newer anyio versions.
"""

import anyio
import sys
from typing import Protocol, Any, Optional


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


# Monkey patch anyio module if attributes are missing
if not hasattr(anyio, 'StreamReader'):
    anyio.StreamReader = StreamReader

if not hasattr(anyio, 'StreamWriter'):
    anyio.StreamWriter = StreamWriter

# Add the module to sys.modules so it can be imported
sys.modules['anyio_compat'] = sys.modules[__name__]