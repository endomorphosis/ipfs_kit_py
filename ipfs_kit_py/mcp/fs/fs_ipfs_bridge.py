#!/usr/bin/env python3
"""
Filesystem IPFS Bridge Module

This module provides integration between the virtual filesystem and IPFS operations.
It ensures that all IPFS operations are properly tracked in the filesystem journal
and that the virtual filesystem stays in sync with the actual IPFS content.
"""

import os
import time
import logging
import asyncio
from typing import Dict, List, Any, Optional, Union, Tuple

# Import local modules
from ipfs_kit_py.mcp.fs.fs_journal import (
    VirtualFS, FSJournal, FSOperation, FSOperationType, FSController
)

# Configure logging
logger = logging.getLogger(__name__)

class IPFSFSBridge:
    """
    Bridge between IPFS and the virtual filesystem.
    
    This class ensures that IPFS operations are properly tracked in the
    filesystem journal and that the virtual filesystem stays in sync
    with the actual IPFS content.
    """
    
    def __init__(self, fs_controller: FSController, ipfs_model=None, ipfs_controller=None):
        self.fs_controller = fs_controller
        self.virtual_fs = fs_controller.virtual_fs
        self.ipfs_model = ipfs_model
        self.ipfs_controller = ipfs_controller
        self.cid_to_path_map: Dict[str, List[str]] = {}
        self.path_to_cid_map: Dict[str, str] = {}
        
        # Track method override status to avoid double-patching
        self.is_patched = False
    
    def map_cid_to_path(self, cid: str, path: str) -> None:
        """Map a CID to a virtual filesystem path."""
        if cid not in self.cid_to_path_map:
            self.cid_to_path_map[cid] = []
        
        if path not in self.cid_to_path_map[cid]:
            self.cid_to_path_map[cid].append(path)
        
        self.path_to_cid_map[path] = cid
    
    def get_paths_for_cid(self, cid: str) -> List[str]:
        """Get all virtual filesystem paths associated with a CID."""
        return self.cid_to_path_map.get(cid, [])
    
    def get_cid_for_path(self, path: str) -> Optional[str]:
        """Get the CID associated with a virtual filesystem path."""
        return self.path_to_cid_map.get(path)
    
    async def import_ipfs_to_vfs(self, cid: str, virtual_path: str) -> bool:
        """
        Import an IPFS object into the virtual filesystem.
        
        Args:
            cid: The CID of the IPFS object to import
            virtual_path: The path in the virtual filesystem to store it
            
        Returns:
            bool: True if the operation succeeded, False otherwise
        """
        if not self.ipfs_model:
            logger.error("No IPFS model available for import operation")
            return False
        
        try:
            # Try to get the content from IPFS
            content = await self._get_ipfs_content(cid)
            if content is None:
                logger.error(f"Failed to get content for CID {cid}")
                return False
            
            # Store in virtual filesystem
            result = self.virtual_fs.write_file(virtual_path, content, cid)
            if result:
                self.map_cid_to_path(cid, virtual_path)
            
            return result
        except Exception as e:
            logger.error(f"Error importing IPFS CID {cid} to {virtual_path}: {e}")
            return False
    
    async def export_vfs_to_ipfs(self, virtual_path: str) -> Optional[str]:
        """
        Export a virtual filesystem file to IPFS.
        
        Args:
            virtual_path: The path in the virtual filesystem to export
            
        Returns:
            str: The CID of the exported object, or None if the operation failed
        """
        if not self.ipfs_model:
            logger.error("No IPFS model available for export operation")
            return None
        
        try:
            # Get content from virtual filesystem
            content = self.virtual_fs.read_file(virtual_path)
            if content is None:
                logger.error(f"Failed to read file {virtual_path} from virtual filesystem")
                return None
            
            # Add to IPFS
            cid = await self._add_ipfs_content(content)
            if cid:
                # Update the file in the virtual filesystem with the new CID
                self.virtual_fs.write_file(virtual_path, content, cid)
                self.map_cid_to_path(cid, virtual_path)
            
            return cid
        except Exception as e:
            logger.error(f"Error exporting {virtual_path} to IPFS: {e}")
            return None
    
    async def synchronize_paths(self, paths: List[str]) -> Tuple[int, int]:
        """
        Synchronize specific paths between IPFS and the virtual filesystem.
        
        Args:
            paths: List of virtual filesystem paths to synchronize
            
        Returns:
            Tuple[int, int]: Number of successful imports and exports
        """
        imports = 0
        exports = 0
        
        for path in paths:
            # Check if the path exists in virtual filesystem
            if self.virtual_fs.exists(path):
                # If it exists in VFS, export to IPFS
                cid = await self.export_vfs_to_ipfs(path)
                if cid:
                    exports += 1
            else:
                # Check if we have a CID mapping
                cid = self.get_cid_for_path(path)
                if cid:
                    # If we have a CID, import from IPFS
                    if await self.import_ipfs_to_vfs(cid, path):
                        imports += 1
        
        return imports, exports
    
    async def _get_ipfs_content(self, cid: str) -> Optional[bytes]:
        """Get content from IPFS."""
        if self.ipfs_model:
            # Use the async API if available
            if hasattr(self.ipfs_model, 'cat_async'):
                return await self.ipfs_model.cat_async(cid)
            
            # Fall back to the synchronous API
            if hasattr(self.ipfs_model, 'cat'):
                # Wrap the synchronous call in a thread
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(None, lambda: self.ipfs_model.cat(cid))
        
        logger.error("IPFS model has no cat or cat_async method")
        return None
    
    async def _add_ipfs_content(self, content: bytes) -> Optional[str]:
        """Add content to IPFS."""
        if self.ipfs_model:
            # Use the async API if available
            if hasattr(self.ipfs_model, 'add_async'):
                return await self.ipfs_model.add_async(content)
            
            # Fall back to the synchronous API
            if hasattr(self.ipfs_model, 'add_content'):
                # Wrap the synchronous call in a thread
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(None, lambda: self.ipfs_model.add_content(content))
        
        logger.error("IPFS model has no add_async or add_content method")
        return None
    
    def patch_ipfs_model(self) -> bool:
        """
        Patch the IPFS model to track operations in the filesystem journal.
        
        Returns:
            bool: True if patching was successful, False otherwise
        """
        if self.is_patched or not self.ipfs_model:
            return False
        
        # Save the original methods
        original_methods = {}
        
        # Methods to patch
        methods_to_patch = [
            ('add_content', FSOperationType.WRITE),
            ('cat', FSOperationType.READ),
            ('pin_add', FSOperationType.PIN),
            ('pin_rm', FSOperationType.UNPIN),
            ('pin_ls', FSOperationType.LIST),
        ]
        
        for method_name, op_type in methods_to_patch:
            if hasattr(self.ipfs_model, method_name):
                # Save the original method
                original_method = getattr(self.ipfs_model, method_name)
                original_methods[method_name] = original_method
                
                # Create a wrapper function that logs operations
                def create_wrapper(original, op_type):
                    def wrapper(*args, **kwargs):
                        # Extract the path or CID from arguments
                        path_or_cid = args[0] if args else kwargs.get('cid', kwargs.get('path', 'unknown'))
                        
                        # Create and record the operation
                        operation = FSOperation(op_type, str(path_or_cid))
                        
                        try:
                            # Call the original method
                            result = original(*args, **kwargs)
                            
                            # Record success
                            self.virtual_fs.journal.record(operation, True)
                            
                            # Special handling for certain operations
                            if op_type == FSOperationType.WRITE and result:
                                # For add_content, record the CID in our mapping
                                cid = result
                                path = f"/ipfs/{cid}"
                                self.map_cid_to_path(cid, path)
                            
                            return result
                        except Exception as e:
                            # Record failure
                            self.virtual_fs.journal.record(operation, False, str(e))
                            raise
                    
                    return wrapper
                
                # Replace the original method with our wrapper
                setattr(self.ipfs_model, method_name, create_wrapper(original_method, op_type))
        
        self.is_patched = True
        logger.info("IPFS model patched to track operations in filesystem journal")
        return True
    
    def create_router(self):
        """Create a FastAPI router for the IPFS-FS bridge."""
        try:
            from fastapi import APIRouter, Query, Path, Body, HTTPException
            
            router = APIRouter()
            
            @router.post("/fs/ipfs/import")
            async def import_ipfs(cid: str = Body(...), path: str = Body(...)):
                """Import an IPFS object into the virtual filesystem."""
                result = await self.import_ipfs_to_vfs(cid, path)
                if not result:
                    raise HTTPException(status_code=400, detail="Failed to import from IPFS")
                
                return {
                    "cid": cid,
                    "path": path,
                    "success": True
                }
            
            @router.post("/fs/ipfs/export")
            async def export_ipfs(path: str = Body(...)):
                """Export a virtual filesystem file to IPFS."""
                cid = await self.export_vfs_to_ipfs(path)
                if not cid:
                    raise HTTPException(status_code=400, detail="Failed to export to IPFS")
                
                return {
                    "path": path,
                    "cid": cid,
                    "success": True
                }
            
            @router.get("/fs/ipfs/mappings")
            async def get_mappings():
                """Get all CID to path mappings."""
                return {
                    "cid_to_path": self.cid_to_path_map,
                    "path_to_cid": self.path_to_cid_map
                }
            
            @router.post("/fs/ipfs/sync")
            async def sync_paths(paths: List[str] = Body(...)):
                """Synchronize paths between IPFS and the virtual filesystem."""
                imports, exports = await self.synchronize_paths(paths)
                return {
                    "imports": imports,
                    "exports": exports,
                    "total": imports + exports,
                    "paths": paths
                }
            
            return router
        except ImportError:
            logger.error("FastAPI not available, router creation skipped")
            return None

def create_fs_ipfs_bridge(mcp_server, fs_controller=None):
    """
    Create and integrate an IPFS-FS bridge with an MCP server.
    
    Args:
        mcp_server: The MCP server instance to integrate with
        fs_controller: Optional filesystem controller to use
        
    Returns:
        IPFSFSBridge: The IPFS-FS bridge instance
    """
    # Get or create the filesystem controller
    if not fs_controller:
        from ipfs_kit_py.mcp.fs.fs_journal import integrate_fs_with_mcp
        fs_controller = integrate_fs_with_mcp(mcp_server)
    
    # Get IPFS model and controller if available
    ipfs_model = None
    ipfs_controller = None
    
    if hasattr(mcp_server, 'models') and 'ipfs' in mcp_server.models:
        ipfs_model = mcp_server.models['ipfs']
    
    if hasattr(mcp_server, 'controllers') and 'ipfs' in mcp_server.controllers:
        ipfs_controller = mcp_server.controllers['ipfs']
    
    # Create the bridge
    bridge = IPFSFSBridge(fs_controller, ipfs_model, ipfs_controller)
    
    # Patch the IPFS model to track operations
    bridge.patch_ipfs_model()
    
    # Create and register the router if possible
    router = bridge.create_router()
    if router and hasattr(mcp_server, 'app'):
        prefix = getattr(mcp_server, 'api_prefix', '/api/v0')
        mcp_server.app.include_router(router, prefix=prefix)
        logger.info(f"Registered IPFS-FS bridge router with MCP server at {prefix}")
    
    return bridge