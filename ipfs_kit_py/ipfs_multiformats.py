import hashlib
from multiformats import CID, multihash
import tempfile
import os
import sys
from multiaddr import Multiaddr, protocols
from typing import Dict, List, Optional, Union, Any
import re

# Define custom exceptions
class MultiaddrParseError(Exception):
    """Exception raised when multiaddress parsing fails."""
    pass

class MultiaddrValidationError(Exception):
    """Exception raised when multiaddress validation fails."""
    pass

class ipfs_multiformats_py:
    def __init__(self, resources, metadata): 
        self.multihash = multihash
        return None
    
    # Step 1: Hash the file content with SHA-256
    def get_file_sha256(self, file_path):
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.digest()

    # Step 2: Wrap the hash in Multihash format
    def get_multihash_sha256(self, file_content_hash):
        mh = self.multihash.wrap(file_content_hash, 'sha2-256')
        return mh

    # Step 3: Generate CID from Multihash (CIDv1)
    def get_cid(self, file_data):
        if os.path.isfile(file_data) == True:
            absolute_path = os.path.abspath(file_data)
            file_content_hash = self.get_file_sha256(file_data)
            mh = self.get_multihash_sha256(file_content_hash)
            # cid = CID('base32', 'raw', mh)
            cid = CID('base32', 1, 'raw', mh)
        else:
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
                filename = f.name
                with open(filename, 'w') as f_new:
                    f_new.write(file_data)
                file_content_hash = self.get_file_sha256(filename)
                mh = self.get_multihash_sha256(file_content_hash)
                cid = CID('base32', 1, 'raw', mh)
                os.remove(filename)
        return str(cid)

# Functions for multiaddress handling
def parse_multiaddr(addr_str: str) -> Dict[str, Any]:
    """
    Parse a multiaddress string into its component parts.
    
    Args:
        addr_str: The multiaddress string to parse
        
    Returns:
        Dictionary with parsed components
        
    Raises:
        MultiaddrParseError: If parsing fails
    """
    try:
        # Manual parsing since Multiaddr iteration doesn't work as expected
        result = {
            "original": addr_str,
            "protocols": []
        }
        
        # Simple regex-based parsing for common protocols
        parts = addr_str.split('/')
        i = 1  # Skip the first empty part due to leading /
        
        while i < len(parts):
            if not parts[i]:
                i += 1
                continue
                
            proto = parts[i]
            i += 1
            value = ""
            
            # Handle protocols with values
            if i < len(parts) and proto in ['ip4', 'ip6', 'dns4', 'dns6', 'tcp', 'udp', 'p2p', 'unix']:
                if proto in ['tcp', 'udp']:
                    value = parts[i]
                    i += 1
                elif proto in ['ip4', 'ip6', 'dns4', 'dns6', 'p2p']:
                    value = parts[i]
                    i += 1
                elif proto == 'unix':
                    # Unix paths may contain multiple segments
                    value = '/' + '/'.join(parts[i:])
                    i = len(parts)
            
            # Find protocol code
            proto_code = 0
            for p in protocols.PROTOCOLS:
                if p.name == proto:
                    proto_code = p.code
                    break
                    
            result["protocols"].append({
                "name": proto,
                "code": proto_code,
                "value": value
            })
            
        return result
    except Exception as e:
        raise MultiaddrParseError(f"Failed to parse multiaddress: {e}")

def multiaddr_to_string(components: Dict[str, Any]) -> str:
    """
    Convert parsed multiaddress components back to a string.
    
    Args:
        components: Dictionary of multiaddress components
        
    Returns:
        Multiaddress string
    """
    if "protocols" not in components:
        raise ValueError("Invalid components format: missing 'protocols' key")
    
    addr_parts = []
    for proto in components["protocols"]:
        addr_parts.append(f"/{proto['name']}")
        if proto["value"]:
            addr_parts.append(f"{proto['value']}")
    
    return "".join(addr_parts)

def get_protocol_value(addr_str: str, protocol_name: str) -> Optional[str]:
    """
    Extract the value for a specific protocol from a multiaddress.
    
    Args:
        addr_str: The multiaddress string
        protocol_name: The protocol to extract the value for
        
    Returns:
        The protocol value or None if not found
    """
    try:
        components = parse_multiaddr(addr_str)
        for proto in components["protocols"]:
            if proto["name"] == protocol_name:
                return proto["value"]
        return None
    except MultiaddrParseError:
        return None

def add_protocol(addr_str: str, protocol_name: str, value: str) -> str:
    """
    Add a protocol to a multiaddress.
    
    Args:
        addr_str: The original multiaddress string
        protocol_name: The protocol to add
        value: The value for the protocol
        
    Returns:
        New multiaddress with the protocol added
    """
    try:
        components = parse_multiaddr(addr_str)
        components["protocols"].append({
            "name": protocol_name,
            "code": 0,  # Find actual code if needed
            "value": value
        })
        return multiaddr_to_string(components)
    except MultiaddrParseError as e:
        # If parsing fails, try to append directly
        if value:
            return f"{addr_str}/{protocol_name}/{value}"
        else:
            return f"{addr_str}/{protocol_name}"

def replace_protocol(addr_str: str, protocol_name: str, value: str) -> str:
    """
    Replace a protocol value in a multiaddress.
    
    Args:
        addr_str: The original multiaddress string
        protocol_name: The protocol to replace
        value: The new value for the protocol
        
    Returns:
        New multiaddress with the protocol replaced
    """
    try:
        components = parse_multiaddr(addr_str)
        for proto in components["protocols"]:
            if proto["name"] == protocol_name:
                proto["value"] = value
                return multiaddr_to_string(components)
        
        # If protocol not found, add it
        return add_protocol(addr_str, protocol_name, value)
    except MultiaddrParseError as e:
        raise MultiaddrParseError(f"Failed to replace protocol: {e}")

def remove_protocol(addr_str: str, protocol_name: str) -> str:
    """
    Remove a protocol from a multiaddress.
    
    Args:
        addr_str: The original multiaddress string
        protocol_name: The protocol to remove
        
    Returns:
        New multiaddress with the protocol removed
    """
    try:
        components = parse_multiaddr(addr_str)
        components["protocols"] = [p for p in components["protocols"] if p["name"] != protocol_name]
        return multiaddr_to_string(components)
    except MultiaddrParseError as e:
        raise MultiaddrParseError(f"Failed to remove protocol: {e}")

def is_valid_multiaddr(addr_str: str, context: str = None) -> bool:
    """
    Validate a multiaddress string.
    
    Args:
        addr_str: The multiaddress string to validate
        context: Optional validation context (e.g., "peer", "listen")
        
    Returns:
        True if valid, False otherwise
    """
    try:
        components = parse_multiaddr(addr_str)
        
        # Must have at least one protocol
        if not components["protocols"]:
            return False
            
        # Context-specific validation
        if context == "peer":
            # Peer addresses require p2p protocol component
            has_p2p = any(p["name"] == "p2p" for p in components["protocols"])
            if not has_p2p:
                return False
            
            # Must have a transport protocol (tcp or udp)
            has_transport = any(p["name"] in ["tcp", "udp"] for p in components["protocols"])
            if not has_transport:
                return False
                
        return True
    except MultiaddrParseError:
        return False