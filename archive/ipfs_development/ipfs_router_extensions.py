"""
IPFS Router Extensions Module

This module provides custom IPFS route extensions for the MCP server.
It's used by the enhanced_mcp_server_fixed.py script to add IPFS endpoints.
"""

import logging
import os
import time
import subprocess
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, File, UploadFile, Form, Response, Path, Query

logger = logging.getLogger(__name__)

def create_ipfs_routers(api_prefix: str) -> List[Any]:
    """
    Create and return FastAPI routers for IPFS extensions.
    
    Args:
        api_prefix: API prefix for endpoints
        
    Returns:
        List of FastAPI routers
    """
    try:
        routers = []
        
        # Create IPFS router
        ipfs_router = APIRouter(prefix=f"{api_prefix}/ipfs")
        
        @ipfs_router.get("/version")
        async def ipfs_version():
            """Get IPFS version information."""
            start_time = time.time()
            try:
                # Run ipfs version command
                result = subprocess.run(
                    ["ipfs", "version"],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode != 0:
                    return {
                        "success": False,
                        "error": f"Failed to get IPFS version: {result.stderr}",
                        "duration_ms": (time.time() - start_time) * 1000
                    }
                
                # Parse version output
                version_str = result.stdout.strip()
                
                return {
                    "success": True,
                    "version": version_str,
                    "duration_ms": (time.time() - start_time) * 1000
                }
            except Exception as e:
                logger.error(f"Error in ipfs_version: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "duration_ms": (time.time() - start_time) * 1000
                }
        
        @ipfs_router.post("/add")
        async def ipfs_add(file: UploadFile = File(...), pin: bool = Form(False)):
            """Add content to IPFS."""
            start_time = time.time()
            try:
                # Create a temporary file
                temp_file = f"/tmp/ipfs_upload_{int(time.time())}"
                with open(temp_file, "wb") as f:
                    content = await file.read()
                    f.write(content)
                
                # Add to IPFS
                pin_arg = ["--pin"] if pin else []
                result = subprocess.run(
                    ["ipfs", "add", "--quiet"] + pin_arg + [temp_file],
                    capture_output=True,
                    text=True
                )
                
                # Clean up
                os.remove(temp_file)
                
                if result.returncode != 0:
                    return {
                        "success": False,
                        "error": f"Failed to add to IPFS: {result.stderr}",
                        "duration_ms": (time.time() - start_time) * 1000
                    }
                
                # Get CID from output
                cid = result.stdout.strip()
                
                return {
                    "success": True,
                    "cid": cid,
                    "filename": file.filename,
                    "size": len(content),
                    "pinned": pin,
                    "duration_ms": (time.time() - start_time) * 1000
                }
            except Exception as e:
                logger.error(f"Error in ipfs_add: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "duration_ms": (time.time() - start_time) * 1000
                }
        
        @ipfs_router.get("/cat/{cid}")
        async def ipfs_cat(cid: str):
            """Get content from IPFS."""
            start_time = time.time()
            try:
                # Run ipfs cat command
                result = subprocess.run(
                    ["ipfs", "cat", cid],
                    capture_output=True
                )
                
                if result.returncode != 0:
                    return Response(
                        content=f"Failed to get content from IPFS: {result.stderr.decode('utf-8')}".encode(),
                        status_code=404
                    )
                
                # Return content
                return Response(content=result.stdout)
            except Exception as e:
                logger.error(f"Error in ipfs_cat: {e}")
                return Response(content=str(e).encode(), status_code=500)
        
        @ipfs_router.post("/pin/add")
        async def ipfs_pin_add(cid: str = Form(...)):
            """Pin content to IPFS."""
            start_time = time.time()
            try:
                # Run ipfs pin add command
                result = subprocess.run(
                    ["ipfs", "pin", "add", cid],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode != 0:
                    return {
                        "success": False,
                        "error": f"Failed to pin content: {result.stderr}",
                        "duration_ms": (time.time() - start_time) * 1000
                    }
                
                return {
                    "success": True,
                    "cid": cid,
                    "duration_ms": (time.time() - start_time) * 1000
                }
            except Exception as e:
                logger.error(f"Error in ipfs_pin_add: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "duration_ms": (time.time() - start_time) * 1000
                }
        
        @ipfs_router.post("/pin/rm")
        async def ipfs_pin_rm(cid: str = Form(...)):
            """Unpin content from IPFS."""
            start_time = time.time()
            try:
                # Run ipfs pin rm command
                result = subprocess.run(
                    ["ipfs", "pin", "rm", cid],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode != 0:
                    return {
                        "success": False,
                        "error": f"Failed to unpin content: {result.stderr}",
                        "duration_ms": (time.time() - start_time) * 1000
                    }
                
                return {
                    "success": True,
                    "cid": cid,
                    "duration_ms": (time.time() - start_time) * 1000
                }
            except Exception as e:
                logger.error(f"Error in ipfs_pin_rm: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "duration_ms": (time.time() - start_time) * 1000
                }
        
        @ipfs_router.get("/pin/ls")
        async def ipfs_pin_ls():
            """List pinned content."""
            start_time = time.time()
            try:
                # Run ipfs pin ls command
                result = subprocess.run(
                    ["ipfs", "pin", "ls", "--type=recursive", "--quiet"],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode != 0:
                    return {
                        "success": False,
                        "error": f"Failed to list pins: {result.stderr}",
                        "duration_ms": (time.time() - start_time) * 1000
                    }
                
                # Parse output
                pins = [pin.strip() for pin in result.stdout.splitlines() if pin.strip()]
                
                return {
                    "success": True,
                    "pins": pins,
                    "count": len(pins),
                    "duration_ms": (time.time() - start_time) * 1000
                }
            except Exception as e:
                logger.error(f"Error in ipfs_pin_ls: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "duration_ms": (time.time() - start_time) * 1000
                }
        
        routers.append(ipfs_router)
        logger.info("Added IPFS router")
        
        return routers
    except Exception as e:
        logger.error(f"Error creating IPFS routers: {e}")
        return []
