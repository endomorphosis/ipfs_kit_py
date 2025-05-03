#!/usr/bin/env python3
"""
IPFS Extensions for MCP

This module provides IPFS methods for MCP tools.
"""

import os
import json
import base64
import tempfile
import logging
import asyncio
from typing import Dict, Any, List, Optional, Union

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='ipfs_extensions.log'
)
logger = logging.getLogger(__name__)

# Import IPFS model if available
try:
    from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
    IPFS_MODEL_AVAILABLE = True
    logger.info("Successfully imported IPFSModel")
except ImportError:
    logger.warning("Failed to import IPFSModel")
    IPFS_MODEL_AVAILABLE = False

# Global IPFS model instance
ipfs_model = None

def initialize_ipfs_model():
    """Initialize IPFS model."""
    global ipfs_model, IPFS_MODEL_AVAILABLE
    
    if not IPFS_MODEL_AVAILABLE:
        logger.error("IPFSModel not available")
        return False
    
    try:
        if ipfs_model is None:
            ipfs_model = IPFSModel()
            logger.info("Initialized IPFSModel")
        return True
    except Exception as e:
        logger.error(f"Error initializing IPFSModel: {e}")
        IPFS_MODEL_AVAILABLE = False
        return False

# Initialize IPFS model
initialize_ipfs_model()

# Helper functions
def ensure_ipfs_model():
    """Ensure IPFS model is initialized."""
    if ipfs_model is None:
        return initialize_ipfs_model()
    return True

async def add_content(content: str, filename: Optional[str] = None, pin: bool = True) -> Dict[str, Any]:
    """
    Add content to IPFS.
    
    Args:
        content: Content to add
        filename: Optional filename
        pin: Whether to pin the content
        
    Returns:
        Dictionary with CID and other information
    """
    if not ensure_ipfs_model():
        return {
            "success": False,
            "error": "IPFS model not available"
        }
    
    try:
        # Create a temporary file with the content
        with tempfile.NamedTemporaryFile(mode='w+b', delete=False) as temp_file:
            if isinstance(content, str):
                temp_file.write(content.encode('utf-8'))
            else:
                temp_file.write(content)
            temp_path = temp_file.name
        
        # Add the file to IPFS
        result = ipfs_model.ipfs_client.add(temp_path)
        
        # Clean up the temporary file
        os.unlink(temp_path)
        
        # Pin the content if requested
        if pin and 'Hash' in result:
            ipfs_model.ipfs_client.pin.add(result['Hash'])
        
        # Return the result
        return {
            "success": True,
            "cid": result.get('Hash'),
            "name": result.get('Name', filename or 'file'),
            "size": result.get('Size', 0),
            "pinned": pin
        }
    except Exception as e:
        logger.error(f"Error adding content to IPFS: {e}")
        return {
            "success": False,
            "error": str(e)
        }

async def cat(cid: str) -> Dict[str, Any]:
    """
    Retrieve content from IPFS.
    
    Args:
        cid: Content ID to retrieve
        
    Returns:
        Dictionary with content and other information
    """
    if not ensure_ipfs_model():
        return {
            "success": False,
            "error": "IPFS model not available"
        }
    
    try:
        # Get the content from IPFS
        content = ipfs_model.ipfs_client.cat(cid)
        
        # Try to decode as text if possible
        try:
            content_str = content.decode('utf-8')
            content_encoding = "text"
        except UnicodeDecodeError:
            # If not decodable as text, encode as base64
            content_str = base64.b64encode(content).decode('utf-8')
            content_encoding = "base64"
        
        # Return the result
        return {
            "success": True,
            "cid": cid,
            "content": content_str,
            "content_encoding": content_encoding,
            "size": len(content)
        }
    except Exception as e:
        logger.error(f"Error retrieving content from IPFS: {e}")
        return {
            "success": False,
            "error": str(e)
        }

async def pin_add(cid: str, recursive: bool = True) -> Dict[str, Any]:
    """
    Pin content to IPFS.
    
    Args:
        cid: Content ID to pin
        recursive: Whether to pin recursively
        
    Returns:
        Dictionary with pin information
    """
    if not ensure_ipfs_model():
        return {
            "success": False,
            "error": "IPFS model not available"
        }
    
    try:
        # Pin the content
        result = ipfs_model.ipfs_client.pin.add(cid, recursive=recursive)
        
        # Return the result
        return {
            "success": True,
            "cid": cid,
            "pins": result.get('Pins', [cid]),
            "recursive": recursive
        }
    except Exception as e:
        logger.error(f"Error pinning content to IPFS: {e}")
        return {
            "success": False,
            "error": str(e)
        }

async def pin_rm(cid: str, recursive: bool = True) -> Dict[str, Any]:
    """
    Unpin content from IPFS.
    
    Args:
        cid: Content ID to unpin
        recursive: Whether to unpin recursively
        
    Returns:
        Dictionary with unpin information
    """
    if not ensure_ipfs_model():
        return {
            "success": False,
            "error": "IPFS model not available"
        }
    
    try:
        # Unpin the content
        result = ipfs_model.ipfs_client.pin.rm(cid, recursive=recursive)
        
        # Return the result
        return {
            "success": True,
            "cid": cid,
            "pins": result.get('Pins', [cid]),
            "recursive": recursive
        }
    except Exception as e:
        logger.error(f"Error unpinning content from IPFS: {e}")
        return {
            "success": False,
            "error": str(e)
        }

async def pin_ls(cid: Optional[str] = None, type_filter: str = "all") -> Dict[str, Any]:
    """
    List pinned content in IPFS.
    
    Args:
        cid: Optional content ID to filter by
        type_filter: Type of pins to list (all, direct, indirect, recursive)
        
    Returns:
        Dictionary with pin information
    """
    if not ensure_ipfs_model():
        return {
            "success": False,
            "error": "IPFS model not available"
        }
    
    try:
        # List pins
        if cid:
            result = ipfs_model.ipfs_client.pin.ls(cid, type=type_filter)
        else:
            result = ipfs_model.ipfs_client.pin.ls(type=type_filter)
        
        # Format the result
        pins = []
        for pin_cid, pin_type in result.get('Keys', {}).items():
            pins.append({
                "cid": pin_cid,
                "type": pin_type.get('Type', 'unknown')
            })
        
        # Return the result
        return {
            "success": True,
            "pins": pins,
            "count": len(pins),
            "type_filter": type_filter
        }
    except Exception as e:
        logger.error(f"Error listing pins in IPFS: {e}")
        return {
            "success": False,
            "error": str(e)
        }

async def get_version() -> Dict[str, Any]:
    """
    Get IPFS version information.
    
    Returns:
        Dictionary with version information
    """
    if not ensure_ipfs_model():
        return {
            "success": False,
            "error": "IPFS model not available"
        }
    
    try:
        # Get version information
        version = ipfs_model.ipfs_client.version()
        
        # Return the result
        return {
            "success": True,
            "version": version.get('Version', 'unknown'),
            "commit": version.get('Commit', 'unknown'),
            "repo": version.get('Repo', 'unknown'),
            "system": version.get('System', 'unknown'),
            "golang": version.get('Golang', 'unknown')
        }
    except Exception as e:
        logger.error(f"Error getting IPFS version: {e}")
        return {
            "success": False,
            "error": str(e)
        }

# MFS methods
async def files_ls(path: str = '/', long: bool = False) -> Dict[str, Any]:
    """
    List files in MFS.
    
    Args:
        path: Path to list
        long: Whether to show detailed information
        
    Returns:
        Dictionary with file information
    """
    if not ensure_ipfs_model():
        return {
            "success": False,
            "error": "IPFS model not available"
        }
    
    try:
        # List files
        result = ipfs_model.ipfs_client.files.ls(path, long=long)
        
        # Format the result
        entries = []
        for entry in result.get('Entries', []):
            entries.append({
                "name": entry.get('Name', ''),
                "type": entry.get('Type', 0),
                "size": entry.get('Size', 0),
                "hash": entry.get('Hash', '')
            })
        
        # Return the result
        return {
            "success": True,
            "path": path,
            "entries": entries,
            "count": len(entries)
        }
    except Exception as e:
        logger.error(f"Error listing files in MFS: {e}")
        return {
            "success": False,
            "error": str(e),
            "path": path
        }

async def files_mkdir(path: str, parents: bool = True) -> Dict[str, Any]:
    """
    Create a directory in MFS.
    
    Args:
        path: Path to create
        parents: Whether to create parent directories
        
    Returns:
        Dictionary with result information
    """
    if not ensure_ipfs_model():
        return {
            "success": False,
            "error": "IPFS model not available"
        }
    
    try:
        # Create directory
        ipfs_model.ipfs_client.files.mkdir(path, parents=parents)
        
        # Return the result
        return {
            "success": True,
            "path": path,
            "parents": parents
        }
    except Exception as e:
        logger.error(f"Error creating directory in MFS: {e}")
        return {
            "success": False,
            "error": str(e),
            "path": path
        }

async def files_write(path: str, content: str, create: bool = True, truncate: bool = True) -> Dict[str, Any]:
    """
    Write content to a file in MFS.
    
    Args:
        path: Path to write to
        content: Content to write
        create: Whether to create the file if it does not exist
        truncate: Whether to truncate the file before writing
        
    Returns:
        Dictionary with result information
    """
    if not ensure_ipfs_model():
        return {
            "success": False,
            "error": "IPFS model not available"
        }
    
    try:
        # Create content as bytes
        if isinstance(content, str):
            content_bytes = content.encode('utf-8')
        else:
            content_bytes = content
        
        # Write to file
        ipfs_model.ipfs_client.files.write(path, content_bytes, create=create, truncate=truncate)
        
        # Return the result
        return {
            "success": True,
            "path": path,
            "size": len(content_bytes),
            "create": create,
            "truncate": truncate
        }
    except Exception as e:
        logger.error(f"Error writing to file in MFS: {e}")
        return {
            "success": False,
            "error": str(e),
            "path": path
        }

async def files_read(path: str, offset: int = 0, count: int = 0) -> Dict[str, Any]:
    """
    Read content from a file in MFS.
    
    Args:
        path: Path to read
        offset: Offset to start reading from
        count: Number of bytes to read (0 means read all)
        
    Returns:
        Dictionary with content and other information
    """
    if not ensure_ipfs_model():
        return {
            "success": False,
            "error": "IPFS model not available"
        }
    
    try:
        # Read from file
        content = ipfs_model.ipfs_client.files.read(path, offset=offset, count=count)
        
        # Try to decode as text if possible
        try:
            content_str = content.decode('utf-8')
            content_encoding = "text"
        except UnicodeDecodeError:
            # If not decodable as text, encode as base64
            content_str = base64.b64encode(content).decode('utf-8')
            content_encoding = "base64"
        
        # Return the result
        return {
            "success": True,
            "path": path,
            "content": content_str,
            "content_encoding": content_encoding,
            "size": len(content),
            "offset": offset,
            "count": count
        }
    except Exception as e:
        logger.error(f"Error reading from file in MFS: {e}")
        return {
            "success": False,
            "error": str(e),
            "path": path
        }

# Map tool names to functions
TOOL_MAP = {
    "ipfs_add": add_content,
    "ipfs_cat": cat,
    "ipfs_pin": pin_add,
    "ipfs_unpin": pin_rm,
    "ipfs_list_pins": pin_ls,
    "ipfs_version": get_version,
    "ipfs_files_ls": files_ls,
    "ipfs_files_mkdir": files_mkdir,
    "ipfs_files_write": files_write,
    "ipfs_files_read": files_read
}

# Main function for testing
async def main():
    """Test IPFS extensions."""
    # Initialize IPFS model
    if not initialize_ipfs_model():
        print("Failed to initialize IPFS model")
        return 1
    
    # Test add content
    content = "Hello, IPFS from Python extensions!"
    print(f"Adding content: {content}")
    add_result = await add_content(content, filename="hello.txt", pin=True)
    print(f"Add result: {json.dumps(add_result, indent=2)}")
    
    if add_result.get("success"):
        # Get the CID
        cid = add_result.get("cid")
        print(f"Content CID: {cid}")
        
        # Test cat
        print(f"Retrieving content for CID: {cid}")
        cat_result = await cat(cid)
        print(f"Cat result: {json.dumps(cat_result, indent=2)}")
        
        # Test pin operations
        print(f"Pinning CID: {cid}")
        pin_result = await pin_add(cid)
        print(f"Pin result: {json.dumps(pin_result, indent=2)}")
        
        print(f"Listing pins")
        pins_result = await pin_ls()
        print(f"Pins result: {json.dumps(pins_result, indent=2)}")
    
    # Test version
    print("Getting IPFS version")
    version_result = await get_version()
    print(f"Version result: {json.dumps(version_result, indent=2)}")
    
    # Test MFS operations
    print("Creating directory in MFS")
    mkdir_result = await files_mkdir("/test")
    print(f"Mkdir result: {json.dumps(mkdir_result, indent=2)}")
    
    print("Writing file to MFS")
    write_result = await files_write("/test/hello.txt", "Hello, MFS!")
    print(f"Write result: {json.dumps(write_result, indent=2)}")
    
    print("Listing files in MFS")
    ls_result = await files_ls("/test")
    print(f"Ls result: {json.dumps(ls_result, indent=2)}")
    
    print("Reading file from MFS")
    read_result = await files_read("/test/hello.txt")
    print(f"Read result: {json.dumps(read_result, indent=2)}")
    
    return 0

if __name__ == "__main__":
    asyncio.run(main())
