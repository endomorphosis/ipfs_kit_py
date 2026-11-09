"""
IPLD extension for IPFS Kit.

This module extends the IPFS functionality with IPLD-specific operations
including CAR file handling, DAG-PB operations, and UnixFS manipulation.
It provides a higher-level interface to the core IPLD libraries.
"""

import base64
import json
import logging
import os
import time
from typing import Dict, List, Optional, Tuple, Union, Any, BinaryIO

# Import IPLD handlers
from .ipld.car import IPLDCarHandler
from .ipld.dag_pb import IPLDDagPbHandler
from .ipld.unixfs import IPLDUnixFSHandler

# Import error handling
from .error import create_result_dict, handle_error

# Configure logger
logger = logging.getLogger(__name__)


class IPLDExtension:
    """
    Extension for IPFS Kit that provides IPLD-specific functionality.
    
    This class adds support for:
    - CAR file encoding/decoding
    - DAG-PB node creation and manipulation
    - UnixFS file chunking
    - Integration with IPFS operations
    """
    
    def __init__(self, ipfs_client=None):
        """
        Initialize the IPLD extension.
        
        Args:
            ipfs_client: IPFS client to use for IPFS operations
        """
        self.ipfs = ipfs_client
        
        # Initialize handlers
        self.car_handler = IPLDCarHandler()
        self.dag_pb_handler = IPLDDagPbHandler()
        self.unixfs_handler = IPLDUnixFSHandler()
        
        # Check library availability
        if not self.car_handler.available:
            logger.warning("CAR file operations are not available")
        if not self.dag_pb_handler.available:
            logger.warning("DAG-PB operations are not available")
        if not self.unixfs_handler.available:
            logger.warning("UnixFS operations are not available")
    
    # CAR file operations
    
    def create_car(self, roots: List[str], blocks: List[Tuple[str, bytes]]) -> Dict[str, Any]:
        """
        Create a CAR file from roots and blocks.
        
        Args:
            roots: List of root CID strings
            blocks: List of (CID, data) tuples
            
        Returns:
            Dict with operation result and CAR data (base64 encoded)
        """
        result = create_result_dict("create_car")
        
        try:
            if not self.car_handler.available:
                raise ImportError("py-ipld-car package not available")
            
            # Encode CAR file
            car_data = self.car_handler.encode(roots, blocks)
            
            # Base64 encode for result
            car_base64 = base64.b64encode(car_data).decode('utf-8')
            
            result["success"] = True
            result["car_data_base64"] = car_base64
            result["size"] = len(car_data)
            result["roots"] = roots
            result["block_count"] = len(blocks)
            
        except Exception as e:
            handle_error(result, e, logger)
        
        return result
    
    def extract_car(self, car_data: Union[bytes, str]) -> Dict[str, Any]:
        """
        Extract contents of a CAR file.
        
        Args:
            car_data: CAR file data (binary or base64 encoded string)
            
        Returns:
            Dict with operation result, roots and blocks
        """
        result = create_result_dict("extract_car")
        
        try:
            if not self.car_handler.available:
                raise ImportError("py-ipld-car package not available")
            
            # Convert base64 string to bytes if needed
            if isinstance(car_data, str):
                car_data = base64.b64decode(car_data)
            
            # Decode CAR file
            roots, blocks = self.car_handler.decode(car_data)
            
            # Convert CIDs to strings
            root_strs = [root.encode('base32') for root in roots]
            
            # Convert blocks to dict entries
            block_entries = []
            for cid, data in blocks:
                block_entries.append({
                    "cid": cid.encode('base32'),
                    "size": len(data),
                    "data_base64": base64.b64encode(data).decode('utf-8')
                })
            
            result["success"] = True
            result["roots"] = root_strs
            result["blocks"] = block_entries
            result["block_count"] = len(blocks)
            
        except Exception as e:
            handle_error(result, e, logger)
        
        return result
    
    def save_car(self, car_data: Union[bytes, str], file_path: str) -> Dict[str, Any]:
        """
        Save CAR data to a file.
        
        Args:
            car_data: CAR file data (binary or base64 encoded string)
            file_path: Path to save the file
            
        Returns:
            Dict with operation result
        """
        result = create_result_dict("save_car")
        
        try:
            if not self.car_handler.available:
                raise ImportError("py-ipld-car package not available")
            
            # Convert base64 string to bytes if needed
            if isinstance(car_data, str):
                car_data = base64.b64decode(car_data)
            
            # Save to file
            self.car_handler.save_to_file(car_data, file_path)
            
            result["success"] = True
            result["file_path"] = file_path
            result["size"] = len(car_data)
            
        except Exception as e:
            handle_error(result, e, logger)
        
        return result
    
    def load_car(self, file_path: str) -> Dict[str, Any]:
        """
        Load CAR data from a file.
        
        Args:
            file_path: Path to the CAR file
            
        Returns:
            Dict with operation result, roots and blocks
        """
        result = create_result_dict("load_car")
        
        try:
            if not self.car_handler.available:
                raise ImportError("py-ipld-car package not available")
            
            # Load from file
            roots, blocks = self.car_handler.load_from_file(file_path)
            
            # Convert CIDs to strings
            root_strs = [root.encode('base32') for root in roots]
            
            # Convert blocks to dict entries
            block_entries = []
            for cid, data in blocks:
                block_entries.append({
                    "cid": cid.encode('base32'),
                    "size": len(data),
                    "data_base64": base64.b64encode(data).decode('utf-8')
                })
            
            result["success"] = True
            result["roots"] = root_strs
            result["blocks"] = block_entries
            result["block_count"] = len(blocks)
            result["file_path"] = file_path
            
        except Exception as e:
            handle_error(result, e, logger)
        
        return result
    
    # DAG-PB operations
    
    def create_node(self, data: Optional[bytes] = None, links: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """
        Create a DAG-PB node.
        
        Args:
            data: Optional binary data for the node
            links: Optional list of links to other nodes
            
        Returns:
            Dict with operation result and node info
        """
        result = create_result_dict("create_node")
        
        try:
            if not self.dag_pb_handler.available:
                raise ImportError("py-ipld-dag-pb package not available")
            
            # Create node
            node = self.dag_pb_handler.create_node(data, links)
            
            # Encode node
            encoded_node = self.dag_pb_handler.encode_node(node)
            
            # Generate CID
            cid = self.dag_pb_handler.node_to_cid(encoded_node)
            
            result["success"] = True
            result["cid"] = cid.encode('base32')
            result["size"] = len(encoded_node)
            result["has_data"] = node.data is not None
            result["link_count"] = len(node.links) if node.links else 0
            result["encoded_base64"] = base64.b64encode(encoded_node).decode('utf-8')
            
        except Exception as e:
            handle_error(result, e, logger)
        
        return result
    
    def encode_node(self, data: Union[bytes, str, Dict]) -> Dict[str, Any]:
        """
        Encode data as a DAG-PB node.
        
        Args:
            data: Data to encode (binary, string, or dict)
            
        Returns:
            Dict with operation result and encoded node
        """
        result = create_result_dict("encode_node")
        
        try:
            if not self.dag_pb_handler.available:
                raise ImportError("py-ipld-dag-pb package not available")
            
            # Prepare and encode node
            if isinstance(data, str):
                data = data.encode('utf-8')
            
            node = self.dag_pb_handler.prepare_node(data)
            encoded_node = self.dag_pb_handler.encode_node(node)
            
            # Generate CID
            cid = self.dag_pb_handler.node_to_cid(encoded_node)
            
            result["success"] = True
            result["cid"] = cid.encode('base32')
            result["size"] = len(encoded_node)
            result["encoded_base64"] = base64.b64encode(encoded_node).decode('utf-8')
            
        except Exception as e:
            handle_error(result, e, logger)
        
        return result
    
    def decode_node(self, encoded_data: Union[bytes, str]) -> Dict[str, Any]:
        """
        Decode a DAG-PB node.
        
        Args:
            encoded_data: Encoded node data (binary or base64 encoded string)
            
        Returns:
            Dict with operation result and decoded node info
        """
        result = create_result_dict("decode_node")
        
        try:
            if not self.dag_pb_handler.available:
                raise ImportError("py-ipld-dag-pb package not available")
            
            # Convert base64 string to bytes if needed
            if isinstance(encoded_data, str):
                encoded_data = base64.b64decode(encoded_data)
            
            # Decode node
            node = self.dag_pb_handler.decode_node(encoded_data)
            
            # Extract node info
            links_info = []
            if node.links:
                for link in node.links:
                    link_info = {
                        "cid": link.hash.encode('base32'),
                    }
                    if link.name is not None:
                        link_info["name"] = link.name
                    if link.t_size is not None:
                        link_info["size"] = link.t_size
                    links_info.append(link_info)
            
            result["success"] = True
            result["has_data"] = node.data is not None
            if node.data is not None:
                result["data_size"] = len(node.data)
                result["data_base64"] = base64.b64encode(node.data).decode('utf-8')
            result["links"] = links_info
            result["link_count"] = len(links_info)
            
        except Exception as e:
            handle_error(result, e, logger)
        
        return result
    
    # UnixFS operations
    
    def chunk_data(self, data: Union[bytes, str], chunk_size: int = 262144) -> Dict[str, Any]:
        """
        Chunk binary data using fixed-size chunker.
        
        Args:
            data: Binary data or string to chunk
            chunk_size: Size of chunks in bytes (default: 256KB)
            
        Returns:
            Dict with operation result and chunks
        """
        result = create_result_dict("chunk_data")
        
        try:
            if not self.unixfs_handler.available:
                raise ImportError("py-ipld-unixfs package not available")
            
            # Convert string to bytes if needed
            if isinstance(data, str):
                data = data.encode('utf-8')
            
            # Chunk data
            chunks = self.unixfs_handler.chunk_data(data, chunk_size)
            
            # Prepare result
            chunk_entries = []
            for i, chunk in enumerate(chunks):
                chunk_entries.append({
                    "index": i,
                    "size": len(chunk),
                    "data_base64": base64.b64encode(chunk).decode('utf-8')
                })
            
            result["success"] = True
            result["chunks"] = chunk_entries
            result["chunk_count"] = len(chunks)
            result["original_size"] = len(data)
            result["chunk_size"] = chunk_size
            
        except Exception as e:
            handle_error(result, e, logger)
        
        return result
    
    def chunk_file(self, file_path: str, chunk_size: int = 262144) -> Dict[str, Any]:
        """
        Chunk a file using fixed-size chunker.
        
        Args:
            file_path: Path to the file to chunk
            chunk_size: Size of chunks in bytes (default: 256KB)
            
        Returns:
            Dict with operation result and chunk info
        """
        result = create_result_dict("chunk_file")
        
        try:
            if not self.unixfs_handler.available:
                raise ImportError("py-ipld-unixfs package not available")
            
            # Verify file exists
            if not os.path.isfile(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            
            # Get file size
            file_size = os.path.getsize(file_path)
            
            # Open file and count chunks
            chunk_count = 0
            chunk_sizes = []
            
            # Use a generator to avoid loading all chunks into memory
            for chunk in self.unixfs_handler.chunk_file(file_path, chunk_size):
                chunk_count += 1
                chunk_sizes.append(len(chunk))
            
            result["success"] = True
            result["file_path"] = file_path
            result["file_size"] = file_size
            result["chunk_count"] = chunk_count
            result["chunk_size"] = chunk_size
            result["chunks_sizes"] = chunk_sizes
            
        except Exception as e:
            handle_error(result, e, logger)
        
        return result
    
    # Integration with IPFS
    
    def add_car_to_ipfs(self, car_data: Union[bytes, str]) -> Dict[str, Any]:
        """
        Import a CAR file into IPFS.
        
        Args:
            car_data: CAR file data (binary or base64 encoded string)
            
        Returns:
            Dict with operation result and imported roots
        """
        result = create_result_dict("add_car_to_ipfs")
        
        try:
            if not self.car_handler.available:
                raise ImportError("py-ipld-car package not available")
            
            if self.ipfs is None:
                raise ValueError("IPFS client not set")
            
            # Convert base64 string to bytes if needed
            if isinstance(car_data, str):
                car_data = base64.b64decode(car_data)
            
            # Create temporary file for the CAR data
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.car', delete=False) as tmp:
                tmp_path = tmp.name
                tmp.write(car_data)
            
            try:
                # Import CAR file to IPFS
                # We use subprocess directly to avoid API limitations
                if hasattr(self.ipfs, 'run_ipfs_command'):
                    # Use the run_ipfs_command method if available
                    cmd_result = self.ipfs.run_ipfs_command(['dag', 'import', tmp_path])
                    if not cmd_result.get("success", False):
                        raise Exception(f"Failed to import CAR: {cmd_result.get('error')}")
                    
                    # Parse output - this depends on the IPFS version
                    output = cmd_result.get("stdout", b"").decode('utf-8')
                    
                    # Extract the root CIDs if possible
                    # Format might be "Pinned root" or "Root CIDs" or just the CIDs
                    root_cids = []
                    for line in output.split("\n"):
                        if ":" in line and not line.strip().startswith("{"):
                            # Probably a key-value line
                            parts = line.split(":", 1)
                            if "root" in parts[0].lower() and len(parts) > 1:
                                cid_part = parts[1].strip()
                                root_cids.append(cid_part)
                        elif line.strip() and not line.strip().startswith("{"):
                            # Might be just a CID
                            root_cids.append(line.strip())
                    
                    result["success"] = True
                    result["root_cids"] = root_cids
                    
                else:
                    # Fall back to using the HTTP API if we have it
                    import requests
                    
                    # Get API endpoint - might vary based on your IPFS client implementation
                    api_url = getattr(self.ipfs, 'api_base', 'http://127.0.0.1:5001/api/v0')
                    
                    # Make request to import CAR
                    with open(tmp_path, 'rb') as f:
                        response = requests.post(
                            f"{api_url}/dag/import",
                            files={'data': ('car.car', f)}
                        )
                    
                    if response.status_code != 200:
                        raise Exception(f"Failed to import CAR: {response.text}")
                    
                    # Parse response
                    response_data = response.json()
                    root_cids = []
                    if 'Root' in response_data:
                        # This is for older IPFS versions
                        root_cids.append(response_data['Root']['Cid']['/'])
                    elif 'roots' in response_data:
                        # This is for newer versions
                        for root in response_data['roots']:
                            if 'cid' in root:
                                root_cids.append(root['cid']['/'])
                    
                    result["success"] = True
                    result["root_cids"] = root_cids
                    
            finally:
                # Clean up temporary file
                try:
                    os.unlink(tmp_path)
                except:
                    pass
                    
        except Exception as e:
            handle_error(result, e, logger)
        
        return result