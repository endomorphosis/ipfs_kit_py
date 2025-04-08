"""
Handler for CAR (Content Addressable aRchive) files.

This module provides a wrapper around the py-ipld-car library,
enabling encoding and decoding of CAR files for IPFS.
"""

import logging
import os
from typing import Dict, List, Optional, Tuple, Union, Any, BinaryIO

# Import py-ipld-car library
try:
    import ipld_car
    from multiformats import CID
    IPLD_CAR_AVAILABLE = True
except ImportError:
    IPLD_CAR_AVAILABLE = False

logger = logging.getLogger(__name__)


class IPLDCarHandler:
    """Handler for CAR file operations."""
    
    def __init__(self):
        """Initialize the CAR handler."""
        self.available = IPLD_CAR_AVAILABLE
        if not self.available:
            logger.warning(
                "py-ipld-car package not available. CAR file operations will be disabled. "
                "Install with: pip install ipld-car"
            )
    
    def encode(self, roots: List[Union[str, "CID"]], blocks: List[Tuple[Union[str, "CID"], bytes]]) -> bytes:
        """
        Encode a CAR file from roots and blocks.
        
        Args:
            roots: List of root CIDs (can be string representations or CID objects)
            blocks: List of tuples containing (CID, data) pairs
            
        Returns:
            Binary data of the CAR file
            
        Raises:
            ImportError: If py-ipld-car is not available
            ValueError: If input is invalid
        """
        if not self.available:
            raise ImportError("py-ipld-car is not available. Install with: pip install ipld-car")
        
        # Convert string CIDs to CID objects if needed
        root_cids = []
        for root in roots:
            if isinstance(root, str):
                root_cids.append(CID.decode(root))
            else:
                root_cids.append(root)
        
        # Convert blocks with string CIDs to CID objects if needed
        processed_blocks = []
        for cid, data in blocks:
            if isinstance(cid, str):
                processed_blocks.append((CID.decode(cid), data))
            else:
                processed_blocks.append((cid, data))
        
        # Encode the CAR file
        car_data = ipld_car.encode(root_cids, processed_blocks)
        return bytes(car_data)
    
    def decode(self, car_data: Union[bytes, BinaryIO]) -> Tuple[List["CID"], List[Tuple["CID", bytes]]]:
        """
        Decode a CAR file into roots and blocks.
        
        Args:
            car_data: Binary CAR data or file-like object
            
        Returns:
            Tuple containing (list of root CIDs, list of blocks)
            
        Raises:
            ImportError: If py-ipld-car is not available
            ValueError: If input is invalid
        """
        if not self.available:
            raise ImportError("py-ipld-car is not available. Install with: pip install ipld-car")
        
        # Handle file-like input
        if hasattr(car_data, 'read'):
            car_data = car_data.read()
        
        # Decode the CAR file
        roots, blocks = ipld_car.decode(car_data)
        return roots, blocks
    
    def save_to_file(self, car_data: bytes, file_path: str) -> None:
        """
        Save CAR data to a file.
        
        Args:
            car_data: Binary CAR data
            file_path: Path to save the file
            
        Raises:
            IOError: If writing to file fails
        """
        with open(file_path, 'wb') as f:
            f.write(car_data)
    
    def load_from_file(self, file_path: str) -> Tuple[List["CID"], List[Tuple["CID", bytes]]]:
        """
        Load CAR data from a file.
        
        Args:
            file_path: Path to the CAR file
            
        Returns:
            Tuple containing (list of root CIDs, list of blocks)
            
        Raises:
            ImportError: If py-ipld-car is not available
            FileNotFoundError: If file doesn't exist
            ValueError: If file content is invalid
        """
        if not self.available:
            raise ImportError("py-ipld-car is not available. Install with: pip install ipld-car")
        
        with open(file_path, 'rb') as f:
            return self.decode(f)