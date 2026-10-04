#!/usr/bin/env python3
"""
Minimal IPFS Tools Implementation

This module provides a minimal set of IPFS tools for the MCP server
when other implementations are not available or are failing.
"""

import os
import sys
import json
import base64
import hashlib
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Union

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ipfs-tools-minimal")

# Mock implementations for IPFS operations
async def mock_add_content(content, filename=None, pin=True):
    """Mock implementation of add content"""
    logger.info(f"[MOCK] Adding content to IPFS (length: {len(content) if isinstance(content, str) else 'binary'})")
    content_bytes = content.encode() if isinstance(content, str) else content
    content_hash = hashlib.sha256(content_bytes).hexdigest()
    mock_cid = f"Qm{content_hash[:38]}"
    
    return {
        "success": True,
        "cid": mock_cid,
        "name": filename or "unnamed_file",
        "size": len(content_bytes),
        "pinned": pin,
        "mock": True,
        "timestamp": datetime.now().isoformat()
    }

async def mock_cat(cid):
    """Mock implementation of cat"""
    logger.info(f"[MOCK] Retrieving content for CID: {cid}")
    
    mock_content = f"This is mock content for CID: {cid}\nGenerated at {datetime.now().isoformat()}"
    
    return mock_content

async def mock_pin_add(cid, recursive=True):
    """Mock implementation of pin_add"""
    logger.info(f"[MOCK] Pinning CID: {cid} (recursive={recursive})")
    
    return {
        "success": True,
        "cid": cid,
        "pins": [cid],
        "recursive": recursive,
        "mock": True,
        "timestamp": datetime.now().isoformat()
    }

async def mock_pin_rm(cid, recursive=True):
    """Mock implementation of pin_rm"""
    logger.info(f"[MOCK] Unpinning CID: {cid} (recursive={recursive})")
    
    return {
        "success": True,
        "cid": cid,
        "pins": [cid],
        "recursive": recursive,
        "mock": True,
        "timestamp": datetime.now().isoformat()
    }

async def mock_pin_ls(cid=None, type_filter="all"):
    """Mock implementation of pin_ls"""
    logger.info(f"[MOCK] Listing pins (cid={cid}, filter={type_filter})")
    
    pins = [
        f"Qm{'a' * 44}",
        f"Qm{'b' * 44}",
        f"Qm{'c' * 44}"
    ]
    
    if cid:
        # Include the specific CID in the result
        if cid not in pins:
            pins.append(cid)
    
    return {
        "success": True,
        "pins": pins,
        "count": len(pins),
        "filter": type_filter,
        "mock": True,
        "timestamp": datetime.now().isoformat()
    }

def setup_minimal_ipfs_tools(server):
    """Register minimal IPFS tools directly with the MCP server"""
    logger.info("Setting up minimal IPFS tools for MCP server")
    
    # Register essential IPFS tools
    server.register_tool(
        "ipfs_add", 
        mock_add_content, 
        "Add content to IPFS (minimal mock implementation)"
    )
    
    server.register_tool(
        "ipfs_cat", 
        mock_cat, 
        "Retrieve content from IPFS by CID (minimal mock implementation)"
    )
    
    server.register_tool(
        "ipfs_pin_add", 
        mock_pin_add, 
        "Pin content in IPFS (minimal mock implementation)"
    )
    
    server.register_tool(
        "ipfs_pin_ls", 
        mock_pin_ls, 
        "List pinned content in IPFS (minimal mock implementation)"
    )
    
    server.register_tool(
        "ipfs_pin_rm", 
        mock_pin_rm, 
        "Unpin content in IPFS (minimal mock implementation)"
    )
    
    logger.info("Minimal IPFS tools registration complete")
    return True
