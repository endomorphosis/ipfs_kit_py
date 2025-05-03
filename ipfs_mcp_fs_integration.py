#!/usr/bin/env python3
"""
IPFS MCP FS Integration

This module implements the integration between the IPFS components and the
virtual filesystem for MCP protocol. It connects the FS journal, IPFS bridge,
and ensures all tools are properly registered.
"""

import os
import sys
import logging
import asyncio
from typing import Dict, Any, Optional, List, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='ipfs_mcp_fs.log'
)
logger = logging.getLogger(__name__)

# Add console handler
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console.setFormatter(formatter)
logger.addHandler(console)

class IPFSFSIntegration:
    """Integration class between IPFS and virtual filesystem components."""
    
    def __init__(self, ipfs_api_url: str = None, journal_path: str = "fs_journal.json"):
        """Initialize the integration components.
        
        Args:
            ipfs_api_url: URL to IPFS API (default: http://localhost:5001/api/v0)
            journal_path: Path to the filesystem journal file
        """
        self.ipfs_api_url = ipfs_api_url or "http://localhost:5001/api/v0"
        self.journal_path = journal_path
        self.fs_journal = None
        self.fs_ipfs_bridge = None
        self.virtual_fs = None
        self.ipfs_model = None
        
        # Keep track of available components
        self.fs_available = False
        self.ipfs_available = False
        
        # Register tool implementations
        self.tools = {}
    
    async def initialize(self):
        """Initialize all components."""
        # Try to import IPFS components
        try:
            from ipfs_kit_py.mcp.models.storage.ipfs_model import IPFSModel
            from ipfs_kit_py.mcp.fs.fs_journal import FSJournal
            from ipfs_kit_py.mcp.fs.fs_ipfs_bridge import FSIPFSBridge
            from ipfs_kit_py.mcp.fs.virtualfs import VirtualFS
            
            # Initialize IPFS model
            self.ipfs_model = IPFSModel(api_url=self.ipfs_api_url)
            await self.ipfs_model.initialize()
            self.ipfs_available = True
            logger.info(f"Successfully initialized IPFS model with API URL: {self.ipfs_api_url}")
            
            # Initialize filesystem components
            self.fs_journal = FSJournal(journal_path=self.journal_path)
            self.fs_ipfs_bridge = FSIPFSBridge(ipfs_model=self.ipfs_model)
            self.virtual_fs = VirtualFS(
                fs_journal=self.fs_journal,
                fs_ipfs_bridge=self.fs_ipfs_bridge
            )
            self.fs_available = True
            logger.info("Successfully initialized virtual filesystem components")
            
            # Register IPFS tools
            self._register_ipfs_tools()
            
            # Register filesystem tools
            self._register_fs_tools()
            
            return True
            
        except ImportError as e:
            logger.error(f"Failed to import required components: {e}")
            return False
        except Exception as e:
            logger.error(f"Error initializing components: {e}")
            return False
    
    def _register_ipfs_tools(self):
        """Register IPFS tool implementations."""
        if not self.ipfs_available or not self.ipfs_model:
            logger.warning("IPFS model not available, skipping IPFS tool registration")
            return
        
        # Register core IPFS operations
        self.tools["ipfs_add"] = self.ipfs_add
        self.tools["ipfs_cat"] = self.ipfs_cat
        self.tools["ipfs_pin"] = self.ipfs_pin
        self.tools["ipfs_unpin"] = self.ipfs_unpin
        self.tools["ipfs_list_pins"] = self.ipfs_list_pins
        self.tools["ipfs_version"] = self.ipfs_version
        
        # Register MFS operations
        self.tools["ipfs_files_ls"] = self.ipfs_files_ls
        self.tools["ipfs_files_mkdir"] = self.ipfs_files_mkdir
        self.tools["ipfs_files_write"] = self.ipfs_files_write
        self.tools["ipfs_files_read"] = self.ipfs_files_read
        
        logger.info(f"Registered {len(self.tools)} IPFS tools")
    
    def _register_fs_tools(self):
        """Register virtual filesystem tool implementations."""
        if not self.fs_available or not self.virtual_fs:
            logger.warning("Virtual filesystem not available, skipping FS tool registration")
            return
        
        # Import tool implementations from fs_journal_tools if available
        try:
            from fs_journal_tools import (
                fs_read_file_tool, fs_write_file_tool, fs_list_directory_tool,
                fs_create_directory_tool, fs_remove_tool, fs_checkpoint_tool,
                fs_copy_tool, fs_stats_tool
            )
            
            # Register filesystem operations
            self.tools["fs_read_file"] = fs_read_file_tool
            self.tools["fs_write_file"] = fs_write_file_tool
            self.tools["fs_list_directory"] = fs_list_directory_tool
            self.tools["fs_create_directory"] = fs_create_directory_tool
            self.tools["fs_remove"] = fs_remove_tool
            self.tools["fs_checkpoint"] = fs_checkpoint_tool
            self.tools["fs_copy"] = fs_copy_tool
            self.tools["fs_stats"] = fs_stats_tool
            
            logger.info(f"Registered {8} filesystem tools")
            
        except ImportError as e:
            logger.error(f"Failed to import filesystem tools: {e}")
    
    # IPFS Core Tool Implementations
    
    async def ipfs_add(self, content: str, filename: Optional[str] = None, pin: bool = True) -> Dict[str, Any]:
        """Add content to IPFS."""
        try:
            if not self.ipfs_model:
                return {"success": False, "error": "IPFS model not initialized"}
            
            # Determine if content is potentially base64-encoded binary data
            is_binary = False
            if content.startswith("base64:"):
                import base64
                binary_content = base64.b64decode(content[7:])
                is_binary = True
            else:
                binary_content = content.encode('utf-8')
            
            # Add to IPFS
            result = await self.ipfs_model.add_content(
                content=binary_content,
                filename=filename,
                pin=pin
            )
            
            return {
                "success": True,
                "cid": result.get("Hash", ""),
                "name": filename or result.get("Name", ""),
                "size": result.get("Size", len(binary_content)),
                "pinned": pin
            }
            
        except Exception as e:
            logger.error(f"Error adding content to IPFS: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def ipfs_cat(self, cid: str) -> Dict[str, Any]:
        """Retrieve content from IPFS by CID."""
        try:
            if not self.ipfs_model:
                return {"success": False, "error": "IPFS model not initialized"}
            
            # Get from IPFS
            content = await self.ipfs_model.cat(cid)
            
            # Try to decode as text
            try:
                text_content = content.decode('utf-8')
                is_binary = False
                content_to_return = text_content
                content_encoding = "text"
            except UnicodeDecodeError:
                # It's binary data, return as base64
                import base64
                is_binary = True
                content_to_return = "base64:" + base64.b64encode(content).decode('utf-8')
                content_encoding = "base64"
            
            return {
                "success": True,
                "cid": cid,
                "content": content_to_return,
                "content_encoding": content_encoding,
                "is_binary": is_binary,
                "size": len(content)
            }
            
        except Exception as e:
            logger.error(f"Error retrieving content from IPFS: {e}")
            return {
                "success": False,
                "error": str(e),
                "cid": cid
            }
    
    async def ipfs_pin(self, cid: str, recursive: bool = True) -> Dict[str, Any]:
        """Pin a CID in IPFS."""
        try:
            if not self.ipfs_model:
                return {"success": False, "error": "IPFS model not initialized"}
            
            # Pin CID
            result = await self.ipfs_model.pin_add(cid, recursive=recursive)
            pins = result.get("Pins", [])
            
            return {
                "success": True,
                "cid": cid,
                "pins": pins,
                "recursive": recursive
            }
            
        except Exception as e:
            logger.error(f"Error pinning CID {cid}: {e}")
            return {
                "success": False,
                "error": str(e),
                "cid": cid
            }
    
    async def ipfs_unpin(self, cid: str, recursive: bool = True) -> Dict[str, Any]:
        """Unpin a CID in IPFS."""
        try:
            if not self.ipfs_model:
                return {"success": False, "error": "IPFS model not initialized"}
            
            # Unpin CID
            result = await self.ipfs_model.pin_rm(cid, recursive=recursive)
            pins = result.get("Pins", [])
            
            return {
                "success": True,
                "cid": cid,
                "pins": pins,
                "recursive": recursive
            }
            
        except Exception as e:
            logger.error(f"Error unpinning CID {cid}: {e}")
            return {
                "success": False,
                "error": str(e),
                "cid": cid
            }
    
    async def ipfs_list_pins(self, type: str = "all") -> Dict[str, Any]:
        """List pinned items in IPFS."""
        try:
            if not self.ipfs_model:
                return {"success": False, "error": "IPFS model not initialized"}
            
            # Get pins
            result = await self.ipfs_model.pin_ls(type=type)
            pins = result.get("Keys", {})
            
            # Format pins for better readability
            formatted_pins = []
            for cid, pin_info in pins.items():
                formatted_pins.append({
                    "cid": cid,
                    "type": pin_info.get("Type", ""),
                    "recursive": pin_info.get("Type") == "recursive"
                })
            
            return {
                "success": True,
                "pins": formatted_pins,
                "type": type,
                "count": len(formatted_pins)
            }
            
        except Exception as e:
            logger.error(f"Error listing pins: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def ipfs_version(self) -> Dict[str, Any]:
        """Get IPFS version information."""
        try:
            if not self.ipfs_model:
                return {"success": False, "error": "IPFS model not initialized"}
            
            # Get version info
            result = await self.ipfs_model.get_version()
            
            return {
                "success": True,
                "version": result.get("Version", ""),
                "commit": result.get("Commit", ""),
                "repo": result.get("Repo", ""),
                "system": result.get("System", ""),
                "golang": result.get("Golang", "")
            }
            
        except Exception as e:
            logger.error(f"Error getting IPFS version: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # MFS Operations
    
    async def ipfs_files_ls(self, path: str = "/") -> Dict[str, Any]:
        """List files in the MFS."""
        try:
            if not self.ipfs_model:
                return {"success": False, "error": "IPFS model not initialized"}
            
            # List files
            result = await self.ipfs_model.files_ls(path)
            entries = result.get("Entries", [])
            
            # Format entries
            formatted_entries = []
            for entry in entries:
                formatted_entries.append({
                    "name": entry.get("Name", ""),
                    "type": entry.get("Type", 0),
                    "size": entry.get("Size", 0),
                    "is_directory": entry.get("Type") == 1,
                    "cid": entry.get("Hash", "")
                })
            
            return {
                "success": True,
                "path": path,
                "entries": formatted_entries,
                "count": len(formatted_entries)
            }
            
        except Exception as e:
            logger.error(f"Error listing MFS files at {path}: {e}")
            return {
                "success": False,
                "error": str(e),
                "path": path
            }
    
    async def ipfs_files_mkdir(self, path: str, parents: bool = False) -> Dict[str, Any]:
        """Create a directory in the MFS."""
        try:
            if not self.ipfs_model:
                return {"success": False, "error": "IPFS model not initialized"}
            
            # Create directory
            await self.ipfs_model.files_mkdir(path, parents=parents)
            
            return {
                "success": True,
                "path": path,
                "parents": parents
            }
            
        except Exception as e:
            logger.error(f"Error creating MFS directory {path}: {e}")
            return {
                "success": False,
                "error": str(e),
                "path": path
            }
    
    async def ipfs_files_write(self, path: str, content: str, create: bool = True, truncate: bool = True) -> Dict[str, Any]:
        """Write content to a file in the MFS."""
        try:
            if not self.ipfs_model:
                return {"success": False, "error": "IPFS model not initialized"}
            
            # Determine if content is potentially base64-encoded binary data
            is_binary = False
            if content.startswith("base64:"):
                import base64
                binary_content = base64.b64decode(content[7:])
                is_binary = True
            else:
                binary_content = content.encode('utf-8')
            
            # Write file
            await self.ipfs_model.files_write(
                path=path,
                content=binary_content,
                create=create,
                truncate=truncate
            )
            
            # Get stats to confirm
            stat_result = await self.ipfs_model.files_stat(path)
            
            return {
                "success": True,
                "path": path,
                "size": stat_result.get("Size", len(binary_content)),
                "cid": stat_result.get("Hash", "")
            }
            
        except Exception as e:
            logger.error(f"Error writing to MFS file {path}: {e}")
            return {
                "success": False,
                "error": str(e),
                "path": path
            }
    
    async def ipfs_files_read(self, path: str) -> Dict[str, Any]:
        """Read content from a file in the MFS."""
        try:
            if not self.ipfs_model:
                return {"success": False, "error": "IPFS model not initialized"}
            
            # Read file
            content = await self.ipfs_model.files_read(path)
            
            # Try to decode as text
            try:
                text_content = content.decode('utf-8')
                is_binary = False
                content_to_return = text_content
                content_encoding = "text"
            except UnicodeDecodeError:
                # It's binary data, return as base64
                import base64
                is_binary = True
                content_to_return = "base64:" + base64.b64encode(content).decode('utf-8')
                content_encoding = "base64"
            
            # Get stats
            stat_result = await self.ipfs_model.files_stat(path)
            
            return {
                "success": True,
                "path": path,
                "content": content_to_return,
                "content_encoding": content_encoding,
                "is_binary": is_binary,
                "size": stat_result.get("Size", len(content)),
                "cid": stat_result.get("Hash", "")
            }
            
        except Exception as e:
            logger.error(f"Error reading MFS file {path}: {e}")
            return {
                "success": False,
                "error": str(e),
                "path": path
            }

# CLI interface
async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="IPFS MCP FS Integration")
    parser.add_argument("--ipfs-api", default="http://localhost:5001/api/v0", help="IPFS API URL")
    parser.add_argument("--journal", default="fs_journal.json", help="Path to journal file")
    parser.add_argument("--test", action="store_true", help="Run basic tests")
    
    args = parser.parse_args()
    
    integration = IPFSFSIntegration(ipfs_api_url=args.ipfs_api, journal_path=args.journal)
    success = await integration.initialize()
    
    if not success:
        logger.error("Failed to initialize integration")
        return 1
    
    if args.test:
        # Run basic tests
        logger.info("Running basic tests...")
        
        # Test IPFS add
        if "ipfs_add" in integration.tools:
            logger.info("Testing ipfs_add...")
            result = await integration.ipfs_add("Test content from integration test")
            logger.info(f"Result: {result}")
            
            if result.get("success"):
                # Test IPFS cat with the created CID
                cid = result.get("cid")
                logger.info(f"Testing ipfs_cat with CID {cid}...")
                cat_result = await integration.ipfs_cat(cid)
                logger.info(f"Result: {cat_result}")
        
        # Test MFS operations
        if "ipfs_files_mkdir" in integration.tools:
            logger.info("Testing MFS operations...")
            
            # Create test directory
            mkdir_result = await integration.ipfs_files_mkdir("/mcp_test", parents=True)
            logger.info(f"mkdir result: {mkdir_result}")
            
            # Write a test file
            write_result = await integration.ipfs_files_write(
                "/mcp_test/test.txt", 
                "Test content in MFS"
            )
            logger.info(f"write result: {write_result}")
            
            # List files
            ls_result = await integration.ipfs_files_ls("/mcp_test")
            logger.info(f"ls result: {ls_result}")
            
            # Read file
            read_result = await integration.ipfs_files_read("/mcp_test/test.txt")
            logger.info(f"read result: {read_result}")
    
    logger.info("Integration initialized successfully")
    logger.info(f"Available tools: {', '.join(integration.tools.keys())}")
    
    return 0

if __name__ == "__main__":
    asyncio.run(main())
