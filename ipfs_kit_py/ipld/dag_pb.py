"""
Handler for DAG-PB (Protobuf DAG) format.

This module provides a wrapper around the py-ipld-dag-pb library,
enabling encoding and decoding of the DAG-PB format used in IPFS.
"""

import logging
from typing import Dict, List, Optional, Tuple, Union, Any

# Import py-ipld-dag-pb library
try:
    from ipld_dag_pb import PBNode, PBLink, encode, decode, prepare, code, name
    from multiformats import CID, multihash
    IPLD_DAG_PB_AVAILABLE = True
except ImportError:
    IPLD_DAG_PB_AVAILABLE = False

logger = logging.getLogger(__name__)


class IPLDDagPbHandler:
    """Handler for DAG-PB format operations."""
    
    def __init__(self):
        """Initialize the DAG-PB handler."""
        self.available = IPLD_DAG_PB_AVAILABLE
        if not self.available:
            logger.warning(
                "py-ipld-dag-pb package not available. DAG-PB operations will be disabled. "
                "Install with: pip install ipld-dag-pb"
            )
        # Define constants directly if not available
        self.codec_code = 0x70  # Default code for dag-pb
        self.codec_name = "dag-pb"
        
        # Override with imported values if available
        if IPLD_DAG_PB_AVAILABLE:
            try:
                from ipld_dag_pb import code, name
                self.codec_code = code
                self.codec_name = name
            except ImportError:
                pass  # Use defaults
    
    def create_node(self, data: Optional[bytes] = None, links: Optional[List[Dict]] = None) -> "PBNode":
        """
        Create a DAG-PB node.
        
        Args:
            data: Optional binary data for the node
            links: Optional list of links to other nodes
            
        Returns:
            PBNode object
            
        Raises:
            ImportError: If py-ipld-dag-pb is not available
        """
        if not self.available:
            raise ImportError("py-ipld-dag-pb is not available. Install with: pip install ipld-dag-pb")
        
        # Create node with data
        node = PBNode(data)
        
        # Add links if provided
        if links:
            node_links = []
            for link in links:
                # Link can be dict with 'cid', 'name', and 'size' keys
                # or just a CID / CID string
                if isinstance(link, dict):
                    cid = link.get('cid')
                    if isinstance(cid, str):
                        cid = CID.decode(cid)
                    
                    pb_link = PBLink(cid)
                    if 'name' in link:
                        pb_link.name = link['name']
                    if 'size' in link:
                        pb_link.t_size = link['size']
                    
                    node_links.append(pb_link)
                else:
                    # Assume it's a CID or CID string
                    if isinstance(link, str):
                        link = CID.decode(link)
                    node_links.append(PBLink(link))
            
            node.links = node_links
        
        return node
    
    def prepare_node(self, data: Union[str, bytes, Dict]) -> "PBNode":
        """
        Prepare data for DAG-PB encoding, with flexible input support.
        
        Args:
            data: Data to encode (string, bytes, or dict with 'data' and 'links')
            
        Returns:
            PBNode object ready for encoding
            
        Raises:
            ImportError: If py-ipld-dag-pb is not available
        """
        if not self.available:
            raise ImportError("py-ipld-dag-pb is not available. Install with: pip install ipld-dag-pb")
        
        return prepare(data)
    
    def encode_node(self, node: Union["PBNode", bytes, str, Dict]) -> bytes:
        """
        Encode a DAG-PB node.
        
        Args:
            node: PBNode, bytes, string, or dict to encode
            
        Returns:
            Encoded binary data
            
        Raises:
            ImportError: If py-ipld-dag-pb is not available
            ValueError: If input is invalid
        """
        if not self.available:
            raise ImportError("py-ipld-dag-pb is not available. Install with: pip install ipld-dag-pb")
        
        # If not already a PBNode, prepare it
        if not isinstance(node, PBNode):
            node = prepare(node)
        
        # Encode the node
        encoded_bytes = encode(node)
        return bytes(encoded_bytes)
    
    def decode_node(self, data: bytes) -> "PBNode":
        """
        Decode DAG-PB binary data to a node.
        
        Args:
            data: Binary DAG-PB data
            
        Returns:
            Decoded PBNode
            
        Raises:
            ImportError: If py-ipld-dag-pb is not available
            ValueError: If data is invalid
        """
        if not self.available:
            raise ImportError("py-ipld-dag-pb is not available. Install with: pip install ipld-dag-pb")
        
        return decode(data)
    
    def node_to_cid(self, node: Union["PBNode", bytes, str, Dict], hash_func: str = "sha2-256") -> "CID":
        """
        Generate a CID for a DAG-PB node.
        
        Args:
            node: Node to generate CID for
            hash_func: Hash function to use (default: sha2-256)
            
        Returns:
            CID object
            
        Raises:
            ImportError: If py-ipld-dag-pb is not available
        """
        if not self.available:
            raise ImportError("py-ipld-dag-pb is not available. Install with: pip install ipld-dag-pb")
        
        # Encode the node if needed
        if not isinstance(node, bytes):
            encoded_bytes = self.encode_node(node)
        else:
            encoded_bytes = node
        
        # Generate CID
        digest = multihash.digest(encoded_bytes, hash_func)
        cid = CID("base32", 1, self.codec_code, digest)
        
        return cid