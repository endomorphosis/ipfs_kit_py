"""
Handler for UnixFS file format.

This module provides a wrapper around the py-ipld-unixfs library,
enabling file chunking and manipulation in the UnixFS format used by IPFS.
"""

import logging
import os
from typing import Dict, List, Optional, Tuple, Union, Any, BinaryIO, Iterable, Iterator

# Import py-ipld-unixfs library if available
try:
    import ipld_unixfs
    from ipld_unixfs.file.chunker import api as chunker_api
    from ipld_unixfs.file.chunker import fixed as fixed_chunker
    from ipld_unixfs.file.chunker import BufferView
    IPLD_UNIXFS_AVAILABLE = True
except ImportError:
    IPLD_UNIXFS_AVAILABLE = False

logger = logging.getLogger(__name__)


class IPLDUnixFSHandler:
    """Handler for UnixFS operations."""
    
    def __init__(self):
        """Initialize the UnixFS handler."""
        self.available = IPLD_UNIXFS_AVAILABLE
        if not self.available:
            logger.warning(
                "py-ipld-unixfs package not available. UnixFS operations will be disabled. "
                "Install with: pip install ipld-unixfs"
            )
    
    def create_fixed_chunker(self, chunk_size: int = 262144) -> Any:
        """
        Create a fixed-size chunker for file operations.
        
        Args:
            chunk_size: Size of chunks in bytes (default: 256KB)
            
        Returns:
            Fixed-size chunker
            
        Raises:
            ImportError: If py-ipld-unixfs is not available
        """
        if not self.available:
            raise ImportError("py-ipld-unixfs is not available. Install with: pip install ipld-unixfs")
        
        return fixed_chunker.new_chunker(chunk_size)
    
    def chunk_data(self, data: Union[bytes, BinaryIO], chunk_size: int = 262144) -> List[bytes]:
        """
        Chunk binary data or file-like object using fixed-size chunker.
        
        Args:
            data: Binary data or file-like object to chunk
            chunk_size: Size of chunks in bytes (default: 256KB)
            
        Returns:
            List of chunks as bytes
            
        Raises:
            ImportError: If py-ipld-unixfs is not available
        """
        if not self.available:
            raise ImportError("py-ipld-unixfs is not available. Install with: pip install ipld-unixfs")
        
        # If data is file-like, read it first
        if hasattr(data, 'read'):
            data = data.read()
        
        # Create chunker and state
        chunker = self.create_fixed_chunker(chunk_size)
        state = chunker_api.open(chunker)
        
        # Write data to buffer
        buffer_view = BufferView(bytes(data))
        state.buffer = buffer_view
        
        # Chunk data
        result_state = chunker_api.split(chunker, buffer_view, True)
        
        # Extract chunks
        chunks = [bytes(chunk) for chunk in result_state.chunks]
        
        return chunks
    
    def chunk_file(self, file_path: str, chunk_size: int = 262144) -> Iterator[bytes]:
        """
        Chunk a file using fixed-size chunker.
        
        Args:
            file_path: Path to the file to chunk
            chunk_size: Size of chunks in bytes (default: 256KB)
            
        Returns:
            Iterator of chunks as bytes
            
        Raises:
            ImportError: If py-ipld-unixfs is not available
            FileNotFoundError: If file doesn't exist
        """
        if not self.available:
            raise ImportError("py-ipld-unixfs is not available. Install with: pip install ipld-unixfs")
        
        # Verify file exists
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Create chunker
        chunker = self.create_fixed_chunker(chunk_size)
        state = chunker_api.open(chunker)
        
        # Open file and chunk in chunks to avoid loading entire file into memory
        with open(file_path, 'rb') as f:
            while True:
                # Read chunk_size bytes
                file_chunk = f.read(chunk_size)
                if not file_chunk:
                    break
                
                # Add to buffer
                buffer_view = BufferView(file_chunk)
                state.buffer = buffer_view
                
                # Chunk data
                result_state = chunker_api.split(chunker, buffer_view, False)
                
                # Yield chunks
                for chunk in result_state.chunks:
                    yield bytes(chunk)
        
        # Handle final chunk if needed
        if state.buffer:
            result_state = chunker_api.split(chunker, state.buffer, True)
            for chunk in result_state.chunks:
                yield bytes(chunk)