#!/usr/bin/env python3
"""
Enhance MCP Tools for IPFS Kit Python

This script enhances the MCP server by:
1. Adding more IPFS tools to cover all features of ipfs_kit_py
2. Integrating existing tools with virtual filesystem features
3. Exposing MFS (Mutable File System) operations as MCP tools
4. Properly configuring the MCP server to work with all storage backends
"""

import os
import sys
import json
import logging
import argparse
import time
import traceback
from typing import Dict, Any, List, Optional, Union
from fastapi import FastAPI, APIRouter, Request, Response

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='mcp_enhanced_tools.log'
)
logger = logging.getLogger(__name__)

# Add console handler for immediate feedback
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console.setFormatter(formatter)
logger.addHandler(console)

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Enhance MCP tools with all IPFS kit features")
    parser.add_argument("--port", type=int, default=int(os.environ.get("MCP_PORT", "9994")),
                      help="Port to run the server on (default: 9994)")
    parser.add_argument("--host", type=str, default="0.0.0.0",
                      help="Host to bind the server to (default: 0.0.0.0)")
    parser.add_argument("--debug", action="store_true", default=True,
                      help="Enable debug mode")
    parser.add_argument("--log-file", type=str, default="mcp_enhanced_tools.log",
                      help="Log file path (default: mcp_enhanced_tools.log)")
    parser.add_argument("--apply", action="store_true", default=False,
                      help="Apply changes directly to the MCP server")
    return parser.parse_args()

def enhance_mcp_initialize_endpoint():
    """
    Enhance the MCP initialize endpoint to list all available tools and resources.
    
    This includes all IPFS operations, MFS operations, and storage backend operations.
    """
    try:
        # Import the necessary modules
        try:
            from ipfs_kit_py.mcp.server_bridge import MCPServer
            logger.info("Successfully imported MCPServer from server_bridge")
        except ImportError as e:
            logger.error(f"Could not import MCPServer from server_bridge: {e}")
            return False
        
        # Import the necessary MCP modules for tool registration
        try:
            from ipfs_kit_py.mcp.server import register_tool, register_resource
            logger.info("Successfully imported tool registration functions")
        except ImportError:
            logger.warning("Could not import tool registration functions")
        
        # Define a comprehensive list of capabilities
        enhanced_capabilities = {
            "tools": [
                # Core IPFS operations
                "list_files", "file_exists", "get_file_stats", "copy_file", "move_file",  # Current tools
                
                # Extended tools for IPFS operations
                "ipfs_add", "ipfs_cat", "ipfs_pin", "ipfs_unpin", "ipfs_list_pins",
                "ipfs_get", "ipfs_version", "ipfs_id", "ipfs_stat",
                
                # Virtual filesystem (MFS) operations
                "ipfs_files_ls", "ipfs_files_stat", "ipfs_files_mkdir", 
                "ipfs_files_read", "ipfs_files_write", "ipfs_files_rm",
                "ipfs_files_cp", "ipfs_files_mv", "ipfs_files_flush",
                
                # IPNS operations
                "ipfs_name_publish", "ipfs_name_resolve", "ipfs_name_list", 
                
                # DHT operations
                "ipfs_dht_findpeer", "ipfs_dht_findprovs", "ipfs_dht_provide",
                
                # DAG operations
                "ipfs_dag_put", "ipfs_dag_get", "ipfs_dag_resolve",
                
                # Block operations
                "ipfs_block_put", "ipfs_block_get", "ipfs_block_stat",
                
                # Swarm operations
                "ipfs_swarm_peers", "ipfs_swarm_connect", "ipfs_swarm_disconnect",
                
                # Storage backend operations
                "storage_transfer", "storage_status", "storage_backends",
                "storage_huggingface_to_ipfs", "storage_huggingface_from_ipfs",
                "storage_s3_to_ipfs", "storage_s3_from_ipfs",
                "storage_filecoin_to_ipfs", "storage_filecoin_from_ipfs",
                "storage_storacha_to_ipfs", "storage_storacha_from_ipfs",
                "storage_lassie_retrieve",
                
                # Filesystem tools
                "read_file", "write_file", "edit_file", "patch_file", 
                "list_files", "read_file_slice",
                
                # Advanced IPFS operations
                "ipfs_object_get", "ipfs_object_put", "ipfs_object_stat",
                "ipfs_refs", "ipfs_refs_local",
                
                # CID conversion tools
                "ipfs_cid_convert", "ipfs_cid_base32", "ipfs_cid_format"
            ],
            "resources": [
                "ipfs://info", "ipfs://stats", "ipfs://peers",
                "storage://backends", "storage://status", "storage://capabilities",
                "file://ls", "file://system", "file://links",
                "mfs://info", "mfs://root", "mfs://stats"
            ]
        }
        
        # Function to enhance the MCPServer's initialize method
        def enhance_mcp_server_initialize(self):
            """Enhance the initialize method of an MCPServer instance."""
            # Store the original initialize method
            original_initialize = self.initialize
            
            # Define an enhanced initialize method
            async def enhanced_initialize(request=None):
                """Enhanced initialize method with comprehensive capabilities."""
                # Call the original initialize method to get the base response
                original_response = await original_initialize(request)
                
                # Enhance the capabilities section
                original_response["capabilities"] = enhanced_capabilities
                
                # Add extended server info
                original_response["serverInfo"].update({
                    "implementationName": "ipfs-kit-py-enhanced",
                    "version": "2.0.0",
                    "features": ["mfs", "dag", "ipns", "storage_backends", "virtual_filesystem"],
                    "documentation": "https://github.com/endomorphosis/ipfs_kit_py"
                })
                
                logger.info("Enhanced initialize endpoint response with comprehensive capabilities")
                return original_response
            
            # Replace the original initialize method with the enhanced one
            self.initialize = enhanced_initialize
            
            logger.info("Successfully enhanced MCPServer initialize method")
            return True
        
        # Enhance the initialize endpoint in MCPServer class
        setattr(MCPServer, "enhance_initialize", enhance_mcp_server_initialize)
        logger.info("Added enhance_initialize method to MCPServer class")
        
        return True
        
    except Exception as e:
        logger.error(f"Error enhancing MCP initialize endpoint: {e}")
        logger.error(traceback.format_exc())
        return False

def create_mfs_mcp_tools(ipfs_model, ipfs_controller):
    """
    Create enhanced MCP tools for MFS (Mutable File System) operations.
    
    Args:
        ipfs_model: The IPFS model instance
        ipfs_controller: The IPFS controller instance
    
    Returns:
        Dict of MFS tool functions
    """
    tools = {}
    
    # Define MFS list tool
    async def mfs_list_tool(path="/", long=False):
        """
        List files and directories in the IPFS Mutable File System.
        
        Args:
            path: Path in MFS to list (default: "/")
            long: Whether to show detailed file information
        
        Returns:
            List of files/directories with metadata
        """
        try:
            result = await ipfs_controller.list_files(path=path, long=long)
            return {
                "success": result.get("success", False),
                "entries": result.get("entries", []),
                "path": path,
                "count": result.get("count", 0),
                "operation": "ipfs_files_ls",
                "timestamp": time.time()
            }
        except Exception as e:
            logger.error(f"Error in mfs_list_tool: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "path": path,
                "operation": "ipfs_files_ls",
                "timestamp": time.time()
            }
    
    # Define MFS stat tool
    async def mfs_stat_tool(path):
        """
        Get information about a file or directory in MFS.
        
        Args:
            path: Path in MFS to stat
        
        Returns:
            File/directory information
        """
        try:
            result = await ipfs_controller.stat_file(path=path)
            return {
                "success": result.get("success", False),
                "size": result.get("size", 0),
                "cid": result.get("cid", ""),
                "blocks": result.get("blocks", 0),
                "type": result.get("type", ""),
                "path": path,
                "operation": "ipfs_files_stat",
                "timestamp": time.time()
            }
        except Exception as e:
            logger.error(f"Error in mfs_stat_tool: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "path": path,
                "operation": "ipfs_files_stat",
                "timestamp": time.time()
            }
    
    # Define MFS mkdir tool
    async def mfs_mkdir_tool(path, parents=False):
        """
        Create a directory in the MFS.
        
        Args:
            path: Path in MFS to create
            parents: Whether to create parent directories if they don't exist
        
        Returns:
            Operation result
        """
        try:
            result = await ipfs_controller.make_directory(path=path, parents=parents)
            return {
                "success": result.get("success", False),
                "path": path,
                "parents": parents,
                "operation": "ipfs_files_mkdir",
                "timestamp": time.time()
            }
        except Exception as e:
            logger.error(f"Error in mfs_mkdir_tool: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "path": path,
                "operation": "ipfs_files_mkdir",
                "timestamp": time.time()
            }
    
    # Define MFS read tool
    async def mfs_read_tool(path, offset=0, count=None):
        """
        Read content from a file in the MFS.
        
        Args:
            path: Path in MFS to read
            offset: Offset to start reading from
            count: Number of bytes to read (None means read all)
        
        Returns:
            File content
        """
        try:
            result = await ipfs_controller.read_file(path=path, offset=offset, count=count)
            content = result.get("content", "")
            if isinstance(content, bytes):
                # Convert bytes to base64 string for proper JSON transport
                import base64
                content = base64.b64encode(content).decode("utf-8")
                result["content_encoding"] = "base64"
            
            return {
                "success": result.get("success", False),
                "content": content,
                "content_encoding": result.get("content_encoding", "utf-8"),
                "size": result.get("size", 0),
                "path": path,
                "offset": offset,
                "count": count,
                "operation": "ipfs_files_read",
                "timestamp": time.time()
            }
        except Exception as e:
            logger.error(f"Error in mfs_read_tool: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "path": path,
                "operation": "ipfs_files_read",
                "timestamp": time.time()
            }
    
    # Define MFS write tool
    async def mfs_write_tool(path, content, create=True, truncate=True, offset=0, flush=True):
        """
        Write content to a file in the MFS.
        
        Args:
            path: Path in MFS to write to
            content: Content to write
            create: Whether to create the file if it doesn't exist
            truncate: Whether to truncate the file before writing
            offset: Offset to start writing at
            flush: Whether to flush changes to disk immediately
        
        Returns:
            Operation result
        """
        try:
            # Check if content is base64 encoded (e.g. from a client)
            if isinstance(content, str) and content.startswith("base64:"):
                import base64
                content = base64.b64decode(content[7:])  # Strip "base64:" prefix and decode
            
            result = await ipfs_controller.write_file(
                path=path, 
                content=content, 
                create=create, 
                truncate=truncate, 
                offset=offset, 
                flush=flush
            )
            return {
                "success": result.get("success", False),
                "path": path,
                "size": result.get("size", 0),
                "create": create,
                "truncate": truncate,
                "offset": offset,
                "flush": flush,
                "operation": "ipfs_files_write",
                "timestamp": time.time()
            }
        except Exception as e:
            logger.error(f"Error in mfs_write_tool: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "path": path,
                "operation": "ipfs_files_write",
                "timestamp": time.time()
            }
    
    # Define MFS remove tool
    async def mfs_rm_tool(path, recursive=False, force=False):
        """
        Remove a file or directory from the MFS.
        
        Args:
            path: Path in MFS to remove
            recursive: Whether to remove directories recursively
            force: Whether to force removal
        
        Returns:
            Operation result
        """
        try:
            result = await ipfs_controller.remove_file(
                path=path, 
                recursive=recursive, 
                force=force
            )
            return {
                "success": result.get("success", False),
                "path": path,
                "recursive": recursive,
                "force": force,
                "operation": "ipfs_files_rm",
                "timestamp": time.time()
            }
        except Exception as e:
            logger.error(f"Error in mfs_rm_tool: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "path": path,
                "operation": "ipfs_files_rm",
                "timestamp": time.time()
            }
    
    # Add the tools to the dictionary
    tools["ipfs_files_ls"] = mfs_list_tool
    tools["ipfs_files_stat"] = mfs_stat_tool
    tools["ipfs_files_mkdir"] = mfs_mkdir_tool
    tools["ipfs_files_read"] = mfs_read_tool
    tools["ipfs_files_write"] = mfs_write_tool
    tools["ipfs_files_rm"] = mfs_rm_tool
    
    # Add MFS copy and move tools if available in the model
    if hasattr(ipfs_model, "files_cp"):
        async def mfs_cp_tool(source, dest):
            """
            Copy files in the MFS.
            
            Args:
                source: Source path
                dest: Destination path
            
            Returns:
                Operation result
            """
            try:
                if callable(getattr(ipfs_model, "files_cp", None)):
                    result = ipfs_model.files_cp(source=source, dest=dest)
                else:
                    result = {"success": False, "error": "files_cp method not available"}
                return {
                    "success": result.get("success", False),
                    "source": source,
                    "dest": dest,
                    "operation": "ipfs_files_cp",
                    "timestamp": time.time()
                }
            except Exception as e:
                logger.error(f"Error in mfs_cp_tool: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "source": source,
                    "dest": dest,
                    "operation": "ipfs_files_cp",
                    "timestamp": time.time()
                }
        
        tools["ipfs_files_cp"] = mfs_cp_tool
    
    if hasattr(ipfs_model, "files_mv"):
        async def mfs_mv_tool(source, dest):
            """
            Move files in the MFS.
            
            Args:
                source: Source path
                dest: Destination path
            
            Returns:
                Operation result
            """
            try:
                if callable(getattr(ipfs_model, "files_mv", None)):
                    result = ipfs_model.files_mv(source=source, dest=dest)
                else:
                    result = {"success": False, "error": "files_mv method not available"}
                return {
                    "success": result.get("success", False),
                    "source": source,
                    "dest": dest,
                    "operation": "ipfs_files_mv",
                    "timestamp": time.time()
                }
            except Exception as e:
                logger.error(f"Error in mfs_mv_tool: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "source": source,
                    "dest": dest,
                    "operation": "ipfs_files_mv",
                    "timestamp": time.time()
                }
        
        tools["ipfs_files_mv"] = mfs_mv_tool
    
    # Add MFS flush tool if available
    if hasattr(ipfs_model, "files_flush"):
        async def mfs_flush_tool(path="/"):
            """
            Flush changes in MFS to IPFS.
            
            Args:
                path: Path in MFS to flush (default: "/" for entire MFS)
            
            Returns:
                Operation result with CID of the flushed path
            """
            try:
                if callable(getattr(ipfs_model, "files_flush", None)):
                    result = ipfs_model.files_flush(path=path)
                else:
                    result = {"success": False, "error": "files_flush method not available"}
                return {
                    "success": result.get("success", False),
                    "path": path,
                    "cid": result.get("cid", ""),
                    "operation": "ipfs_files_flush",
                    "timestamp": time.time()
                }
            except Exception as e:
                logger.error(f"Error in mfs_flush_tool: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "path": path,
                    "operation": "ipfs_files_flush",
                    "timestamp": time.time()
                }
        
        tools["ipfs_files_flush"] = mfs_flush_tool
    
    return tools

def create_ipfs_basic_tools(ipfs_model, ipfs_controller):
    """
    Create enhanced MCP tools for basic IPFS operations.
    
    Args:
        ipfs_model: The IPFS model instance
        ipfs_controller: The IPFS controller instance
    
    Returns:
        Dict of IPFS tool functions
    """
    tools = {}
    
    # Define IPFS add tool
    async def ipfs_add_tool(content, filename=None, pin=True, wrap_with_directory=False):
        """
        Add content to IPFS.
        
        Args:
            content: Content to add
            filename: Optional filename for the content
            pin: Whether to pin the content
            wrap_with_directory: Whether to wrap the content in a directory
        
        Returns:
            CID of the added content
        """
        try:
            # If content is a string starting with "base64:", decode it
            if isinstance(content, str) and content.startswith("base64:"):
                import base64
                content = base64.b64decode(content[7:])  # Strip "base64:" prefix and decode
            
            # Use appropriate method based on content type
            if hasattr(ipfs_controller, "add_content"):
                # Use controller method if available
                result = await ipfs_controller.add_content({
                    "content": content, 
                    "filename": filename,
                    "pin": pin,
                    "wrap_with_directory": wrap_with_directory
                })
            else:
                # Otherwise use model method directly
                if callable(getattr(ipfs_model, "ipfs_add", None)):
                    opts = {"pin": pin}
                    if wrap_with_directory:
                        opts["wrap_with_directory"] = True
                    
                    result = ipfs_model.ipfs_add(
                        content,
                        filename=filename,
                        **opts
                    )
                else:
                    result = {"success": False, "error": "ipfs_add method not available"}
                
            # Standardize result format
            cid = result.get("cid") or result.get("Hash")
            
            return {
                "success": result.get("success", False),
                "cid": cid,
                "size": result.get("size") or result.get("Size") or 0,
                "filename": filename,
                "pin": pin,
                "wrap_with_directory": wrap_with_directory,
                "operation": "ipfs_add",
                "timestamp": time.time()
            }
        except Exception as e:
            logger.error(f"Error in ipfs_add_tool: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "filename": filename,
                "operation": "ipfs_add",
                "timestamp": time.time()
            }
    
    # Define IPFS cat tool
    async def ipfs_cat_tool(cid, offset=0, length=None):
        """
        Get content from IPFS.
        
        Args:
            cid: Content ID to retrieve
            offset: Offset to start reading from
            length: Number of bytes to read (None means read all)
        
        Returns:
            Content data
        """
        try:
            # Use appropriate method based on what's available
            if hasattr(ipfs_controller, "get_content_json"):
                # Use controller method if available
                result = await ipfs_controller.get_content_json({"cid": cid})
            else:
                # Otherwise use model method directly
                # Make sure to call as method, not attribute
                if callable(getattr(ipfs_model, "ipfs_cat", None)):
                    result = ipfs_model.ipfs_cat(cid=cid, offset=offset, length=length)
                else:
                    result = {"success": False, "error": "ipfs_cat method not available"}
            
            # Get content from result
            content = result.get("data") or result.get("content")
            
            # Convert bytes to base64 for proper JSON transport
            if isinstance(content, bytes):
                import base64
                content = base64.b64encode(content).decode("utf-8")
                content_encoding = "base64"
            else:
                content_encoding = "utf-8"
            
            return {
                "success": result.get("success", False),
                "cid": cid,
                "content": content,
                "content_encoding": content_encoding,
                "size": len(content) if content else 0,
                "operation": "ipfs_cat",
                "timestamp": time.time()
            }
        except Exception as e:
            logger.error(f"Error in ipfs_cat_tool: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "cid": cid,
                "operation": "ipfs_cat",
                "timestamp": time.time()
            }
    
    # Define IPFS pin tool
    async def ipfs_pin_tool(cid, recursive=True):
        """
        Pin content to local IPFS node.
        
        Args:
            cid: Content ID to pin
            recursive: Whether to pin recursively
        
        Returns:
            Pin operation result
        """
        try:
            # Use appropriate method based on what's available
            if hasattr(ipfs_controller, "pin_content"):
                # Use controller method if available
                result = await ipfs_controller.pin_content({"cid": cid})
            else:
                # Otherwise use model method directly
                if callable(getattr(ipfs_model, "ipfs_pin_add", None)):
                    result = ipfs_model.ipfs_pin_add(cid=cid, recursive=recursive)
                else:
                    result = {"success": False, "error": "ipfs_pin_add method not available"}
            
            return {
                "success": result.get("success", False),
                "cid": cid,
                "recursive": recursive,
                "operation": "ipfs_pin",
                "timestamp": time.time()
            }
        except Exception as e:
            logger.error(f"Error in ipfs_pin_tool: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "cid": cid,
                "operation": "ipfs_pin",
                "timestamp": time.time()
            }
    
    # Define IPFS unpin tool
    async def ipfs_unpin_tool(cid, recursive=True):
        """
        Unpin content from local IPFS node.
        
        Args:
            cid: Content ID to unpin
            recursive: Whether to unpin recursively
        
        Returns:
            Unpin operation result
        """
        try:
            # Use appropriate method based on what's available
            if hasattr(ipfs_controller, "unpin_content"):
                # Use controller method if available
                result = await ipfs_controller.unpin_content({"cid": cid})
            else:
                # Otherwise use model method directly
                if callable(getattr(ipfs_model, "ipfs_pin_rm", None)):
                    result = ipfs_model.ipfs_pin_rm(cid=cid, recursive=recursive)
                else:
                    result = {"success": False, "error": "ipfs_pin_rm method not available"}
            
            return {
                "success": result.get("success", False),
                "cid": cid,
                "recursive": recursive,
                "operation": "ipfs_unpin",
                "timestamp": time.time()
            }
        except Exception as e:
            logger.error(f"Error in ipfs_unpin_tool: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "cid": cid,
                "operation": "ipfs_unpin",
                "timestamp": time.time()
            }
    
    # Define IPFS list pins tool
    async def ipfs_list_pins_tool(type="all"):
        """
        List pinned content on local IPFS node.
        
        Args:
            type: Type of pins to list (all, direct, recursive, indirect)
        
        Returns:
            List of pinned content
        """
        try:
            # Use appropriate method based on what's available
            if hasattr(ipfs_controller, "list_pins"):
                # Use controller method if available
                result = await ipfs_controller.list_pins()
            else:
                # Otherwise use model method directly
                if callable(getattr(ipfs_model, "ipfs_pin_ls", None)):
                    result = ipfs_model.ipfs_pin_ls(type=type)
                else:
                    result = {"success": False, "error": "ipfs_pin_ls method not available"}
            
            return {
                "success": result.get("success", False),
                "pins": result.get("pins", []),
                "count": result.get("count", 0),
                "type": type,
                "operation": "ipfs_list_pins",
                "timestamp": time.time()
            }
        except Exception as e:
            logger.error(f"Error in ipfs_list_pins_tool: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "pins": [],
                "count": 0,
                "operation": "ipfs_list_pins",
                "timestamp": time.time()
            }
    
    # Add the tools to the dictionary
    tools["ipfs_add"] = ipfs_add_tool
    tools["ipfs_cat"] = ipfs_cat_tool
    tools["ipfs_pin"] = ipfs_pin_tool
    tools["ipfs_unpin"] = ipfs_unpin_tool
    tools["ipfs_list_pins"] = ipfs_list_pins_tool
    
    # Add version and node ID tools
    async def ipfs_version_tool():
        """
        Get IPFS version information.
        
        Returns:
            Version information
        """
        try:
            if hasattr(ipfs_controller, "get_version"):
                result = await ipfs_controller.get_version()
            else:
                if callable(getattr(ipfs_model, "get_version", None)):
                    result = ipfs_model.get_version()
                else:
                    result = {"success": True, "version": "unknown", "error": "get_version method not available"}
            
            return {
                "success": result.get("success", True),
                "version": result.get("version", ""),
                "commit": result.get("commit", ""),
                "repo": result.get("repo", ""),
                "operation": "ipfs_version",
                "timestamp": time.time()
            }
        except Exception as e:
            logger.error(f"Error in ipfs_version_tool: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "operation": "ipfs_version",
                "timestamp": time.time()
            }
    
    async def ipfs_id_tool():
        """
        Get local node identity information.
        
        Returns:
            Node identity information
        """
        try:
            if hasattr(ipfs_controller, "get_node_id"):
                result = await ipfs_controller.get_node_id()
            else:
                if callable(getattr(ipfs_model, "id", None)):
                    result = ipfs_model.id()
                else:
                    # If id is an attribute, not a method
                    result = {"success": True, "id": getattr(ipfs_model, "id", ""), "addresses": []}
            
            return {
                "success": result.get("success", True),
                "peer_id": result.get("peer_id") or result.get("id", ""),
                "addresses": result.get("addresses", []),
                "agent_version": result.get("agent_version", ""),
                "protocol_version": result.get("protocol_version", ""),
                "operation": "ipfs_id",
                "timestamp": time.time()
            }
        except Exception as e:
            logger.error(f"Error in ipfs_id_tool: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "operation": "ipfs_id",
                "timestamp": time.time()
            }
    
    # Add the tools to the dictionary
    tools["ipfs_version"] = ipfs_version_tool
    tools["ipfs_id"] = ipfs_id_tool
    
    return tools

def create_ipns_tools(ipfs_model, ipfs_controller):
    """
    Create enhanced MCP tools for IPNS operations.
    
    Args:
        ipfs_model: The IPFS model instance
        ipfs_controller: The IPFS controller instance
    
    Returns:
        Dict of IPNS tool functions
    """
    tools = {}
    
    # Define IPNS publish tool
    async def ipns_publish_tool(path, key="self", resolve=True, lifetime="24h"):
        """
        Publish an IPFS path to IPNS.
        
        Args:
            path: Path to publish
            key: Name of the key to use
            resolve: Whether to resolve the path before publishing
            lifetime: Lifetime of the record
        
        Returns:
            Operation result with IPNS name
        """
        try:
            if hasattr(ipfs_controller, "publish_name"):
                result = await ipfs_controller.publish_name(
                    path=path, 
                    key=key,
                    resolve=resolve,
                    lifetime=lifetime
                )
            else:
                if callable(getattr(ipfs_model, "name_publish", None)):
                    result = ipfs_model.name_publish(
                        path=path, 
                        key=key,
                        resolve=resolve,
                        lifetime=lifetime
                    )
                else:
                    result = {"success": False, "error": "name_publish method not available"}
            
            return {
                "success": result.get("success", False),
                "name": result.get("name", ""),
                "value": result.get("value", ""),
                "path": path,
                "key": key,
                "resolve": resolve,
                "lifetime": lifetime,
                "operation": "ipfs_name_publish",
                "timestamp": time.time()
            }
        except Exception as e:
            logger.error(f"Error in ipns_publish_tool: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "path": path,
                "operation": "ipfs_name_publish",
                "timestamp": time.time()
            }
    
    # Define IPNS resolve tool
    async def ipns_resolve_tool(name, recursive=True, nocache=False):
        """
        Resolve an IPNS name to an IPFS path.
        
        Args:
            name: IPNS name to resolve
            recursive: Whether to resolve recursively
            nocache: Whether to avoid using cached entries
        
        Returns:
            Resolved path
        """
        try:
            if hasattr(ipfs_controller, "resolve_name"):
                result = await ipfs_controller.resolve_name(
                    name=name, 
                    recursive=recursive,
                    nocache=nocache
                )
            else:
                if callable(getattr(ipfs_model, "name_resolve", None)):
                    result = ipfs_model.name_resolve(
                        name=name, 
                        recursive=recursive,
                        nocache=nocache
                    )
                else:
                    result = {"success": False, "error": "name_resolve method not available"}
            
            return {
                "success": result.get("success", False),
                "path": result.get("path", ""),
                "name": name,
                "recursive": recursive,
                "nocache": nocache,
                "operation": "ipfs_name_resolve",
                "timestamp": time.time()
            }
        except Exception as e:
            logger.error(f"Error in ipns_resolve_tool: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "name": name,
                "operation": "ipfs_name_resolve",
                "timestamp": time.time()
            }
    
    # Add the tools to the dictionary
    tools["ipfs_name_publish"] = ipns_publish_tool
    tools["ipfs_name_resolve"] = ipns_resolve_tool
    
    # Add IPNS key list tool if available
    if hasattr(ipfs_model, "key_list"):
        async def ipns_key_list_tool():
            """
            List IPNS keys.
            
            Returns:
                List of IPNS keys
            """
            try:
                result = {}
                if callable(getattr(ipfs_model, "key_list", None)):
                    result = ipfs_model.key_list()
                else:
                    result = {"success": False, "error": "key_list method not available"}
                
                return {
                    "success": result.get("success", False),
                    "keys": result.get("keys", []),
                    "count": len(result.get("keys", [])),
                    "operation": "ipfs_name_list",
                    "timestamp": time.time()
                }
            except Exception as e:
                logger.error(f"Error in ipns_key_list_tool: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "keys": [],
                    "count": 0,
                    "operation": "ipfs_name_list",
                    "timestamp": time.time()
                }
        
        tools["ipfs_name_list"] = ipns_key_list_tool
    
    return tools

def register_mcp_tools(mcp_server):
    """
    Register all enhanced MCP tools with the MCP server.
    
    Args:
        mcp_server: The MCP server instance
    
    Returns:
        Dict of registered tool names and handlers
    """
    try:
        # Get IPFS model and controller from the server
        ipfs_model = mcp_server.models.get("ipfs") if hasattr(mcp_server, "models") else None
        ipfs_controller = mcp_server.controllers.get("ipfs") if hasattr(mcp_server, "controllers") else None
        
        if not ipfs_model or not ipfs_controller:
            logger.error("IPFS model or controller not found in MCP server")
            return {}
        
        # Create MFS tools
        mfs_tools = create_mfs_mcp_tools(ipfs_model, ipfs_controller)
        
        # Create basic IPFS tools
        ipfs_tools = create_ipfs_basic_tools(ipfs_model, ipfs_controller)
        
        # Create IPNS tools
        ipns_tools = create_ipns_tools(ipfs_model, ipfs_controller)
        
        # Create a dictionary of all tools
        all_tools = {}
        all_tools.update(mfs_tools)
        all_tools.update(ipfs_tools)
        all_tools.update(ipns_tools)
        
        # Check if MCP server has tool registration capabilities
        registration_successful = False
        
        # Try different methods to register tools
        if hasattr(mcp_server, "register_tool"):
            # Method 1: Direct registration via server instance
            logger.info("Using direct server registration method")
            for tool_name, tool_handler in all_tools.items():
                logger.info(f"Registering tool: {tool_name}")
                try:
                    mcp_server.register_tool(tool_name, tool_handler)
                    registration_successful = True
                except Exception as tool_error:
                    logger.error(f"Error registering tool {tool_name}: {tool_error}")
        else:
            # Method 2: Try using global registration function
            try:
                from ipfs_kit_py.mcp.server import register_tool
                logger.info("Using global registration function")
                for tool_name, tool_handler in all_tools.items():
                    logger.info(f"Registering tool: {tool_name}")
                    try:
                        register_tool(tool_name, tool_handler)
                        registration_successful = True
                    except Exception as tool_error:
                        logger.error(f"Error registering tool {tool_name}: {tool_error}")
            except ImportError:
                logger.error("Could not import register_tool function")
            
            # Method 3: Try adding tools directly to the server's tool registry
            if not registration_successful and hasattr(mcp_server, "tools"):
                logger.info("Adding tools directly to server's tool registry")
                for tool_name, tool_handler in all_tools.items():
                    logger.info(f"Adding tool: {tool_name}")
                    try:
                        mcp_server.tools[tool_name] = tool_handler
                        registration_successful = True
                    except Exception as tool_error:
                        logger.error(f"Error adding tool {tool_name}: {tool_error}")
        
        # Alternatively, override initialize to include additional capabilities
        if hasattr(mcp_server, "enhance_initialize"):
            logger.info("Applying enhanced initialize endpoint")
            mcp_server.enhance_initialize()
        
        return all_tools
        
    except Exception as e:
        logger.error(f"Error registering MCP tools: {e}")
        logger.error(traceback.format_exc())
        return {}

def enhance_existing_server():
    """Enhance an existing running MCP server with more tools."""
    try:
        # Try different import paths
        server_instance = None
        
        # Attempt 1: server_bridge path
        try:
            from ipfs_kit_py.mcp.server_bridge import MCPServer
            logger.info("Successfully imported MCPServer from server_bridge")
            server_instance = MCPServer(debug_mode=True)
            logger.info("Created MCPServer instance via server_bridge")
        except (ImportError, Exception) as e:
            logger.warning(f"Could not create MCPServer from server_bridge: {e}")
        
        # Attempt 2: direct server path
        if server_instance is None:
            try:
                from ipfs_kit_py.mcp.server import MCPServer
                logger.info("Successfully imported MCPServer from server module")
                server_instance = MCPServer(debug_mode=True)
                logger.info("Created MCPServer instance via server module")
            except (ImportError, Exception) as e:
                logger.warning(f"Could not create MCPServer from server module: {e}")
        
        # Attempt 3: try with direct server accessor function
        if server_instance is None:
            try:
                from ipfs_kit_py.mcp.server import get_server_instance
                logger.info("Using get_server_instance function")
                server_instance = get_server_instance()
                logger.info("Got MCPServer via get_server_instance")
            except (ImportError, Exception) as e:
                logger.warning(f"Could not get server instance: {e}")
        
        if server_instance is None:
            logger.error("Could not create or find a MCPServer instance")
            return False
        
        # Enhance the initialize endpoint
        enhance_success = enhance_mcp_initialize_endpoint()
        if not enhance_success:
            logger.warning("Failed to enhance initialize endpoint")
        
        # Update capabilities directly in the server's API description
        try:
            # Try to update capabilities directly in the API
            if hasattr(server_instance, "api_description") and "capabilities" in server_instance.api_description:
                logger.info("Updating capabilities directly in API description")
                enhanced_capabilities = {
                    "tools": [
                        # List all relevant tools
                        "list_files", "file_exists", "get_file_stats", "copy_file", "move_file",
                        "ipfs_add", "ipfs_cat", "ipfs_files_ls", "ipfs_files_mkdir"
                    ],
                    "resources": [
                        "ipfs://info", "storage://backends", "file://ls", "mfs://root"
                    ]
                }
                server_instance.api_description["capabilities"] = enhanced_capabilities
        except Exception as api_error:
            logger.warning(f"Could not update API description: {api_error}")
        
        # Register tools with the running server
        tools = register_mcp_tools(server_instance)
        
        logger.info(f"Successfully registered {len(tools)} tools with the running MCP server")
        return True
        
    except Exception as e:
        logger.error(f"Error enhancing existing server: {e}")
        logger.error(traceback.format_exc())
        return False

def main():
    """Main function to run the script."""
    args = parse_args()
    
    # Configure logging based on args
    if args.debug:
        logger.setLevel(logging.DEBUG)
        console.setLevel(logging.DEBUG)
    
    # Set log file
    if args.log_file:
        file_handler = logging.FileHandler(args.log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    logger.info("Starting enhance_mcp_tools.py")
    
    # Enhance MCP initialize endpoint
    enhance_success = enhance_mcp_initialize_endpoint()
    
    if args.apply:
        # Enhance a running server
        server_enhanced = enhance_existing_server()
        if server_enhanced:
            logger.info("Successfully enhanced the running MCP server")
        else:
            logger.error("Failed to enhance the running MCP server")
    else:
        logger.info("Changes prepared. Run with --apply to apply changes to a running MCP server")
    
    logger.info("enhance_mcp_tools.py completed")

if __name__ == "__main__":
    main()
