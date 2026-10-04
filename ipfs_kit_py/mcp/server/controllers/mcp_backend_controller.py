#!/usr/bin/env python3
"""
MCP Backend Controller - Mirrors CLI backend commands

This controller provides MCP tools that mirror the CLI backend commands,
allowing MCP clients to manage backends with the same functionality as
the command line interface.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from ..models.mcp_metadata_manager import MCPMetadataManager
from ..services.mcp_daemon_service import MCPDaemonService

logger = logging.getLogger(__name__)


class MCPBackendController:
    """
    MCP Backend Controller that mirrors CLI backend commands
    
    Provides MCP tools for:
    - backend list (mirrors 'ipfs-kit backend list')
    - backend status (mirrors 'ipfs-kit backend status') 
    - backend sync (mirrors 'ipfs-kit backend sync')
    - backend migrate-pin-mappings (mirrors 'ipfs-kit backend migrate-pin-mappings')
    """
    
    def __init__(self, metadata_manager: MCPMetadataManager, daemon_service: MCPDaemonService):
        """Initialize the backend controller."""
        self.metadata_manager = metadata_manager
        self.daemon_service = daemon_service
        logger.info("MCP Backend Controller initialized")
    
    async def handle_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle backend tool calls by routing to appropriate methods."""
        try:
            if tool_name == "backend_list":
                return await self.list_backends(arguments)
            elif tool_name == "backend_status":
                return await self.get_backend_status(arguments)
            elif tool_name == "backend_sync":
                return await self.sync_backend(arguments)
            elif tool_name == "backend_migrate_pin_mappings":
                return await self.migrate_pin_mappings(arguments)
            else:
                return {"error": f"Unknown backend tool: {tool_name}"}
        except Exception as e:
            logger.error(f"Error handling backend tool {tool_name}: {e}")
            return {"error": str(e)}
    
    async def list_backends(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        List all configured backends (mirrors 'ipfs-kit backend list')
        
        Arguments:
        - filter: Filter backends by type or name
        - status: Filter by status (healthy, unhealthy, all)
        - detailed: Show detailed information
        """
        filter_param = arguments.get("filter")
        status_filter = arguments.get("status", "all")
        detailed = arguments.get("detailed", False)
        
        try:
            # Get all backend metadata
            backends = await self.metadata_manager.get_backend_metadata()
            
            # Apply filters
            if filter_param:
                filter_lower = filter_param.lower()
                backends = [b for b in backends 
                          if filter_lower in b.name.lower() or filter_lower in b.type.lower()]
            
            if status_filter != "all":
                if status_filter == "healthy":
                    backends = [b for b in backends if b.health_status == "healthy"]
                elif status_filter == "unhealthy":
                    backends = [b for b in backends if b.health_status != "healthy"]
            
            # Format output
            if detailed:
                return {
                    "backends": [
                        {
                            "name": backend.name,
                            "type": backend.type,
                            "health_status": backend.health_status,
                            "pin_count": backend.pin_count,
                            "storage_usage_bytes": backend.storage_usage_bytes,
                            "last_updated": backend.last_updated.isoformat(),
                            "config_path": backend.config_path,
                            "index_path": backend.index_path,
                            "pin_mappings_available": backend.pin_mappings_available,
                            "car_files_available": backend.car_files_available
                        }
                        for backend in backends
                    ],
                    "total_count": len(backends),
                    "filter_applied": filter_param,
                    "status_filter": status_filter
                }
            else:
                return {
                    "backends": [
                        {
                            "name": backend.name,
                            "type": backend.type,
                            "status": backend.health_status,
                            "pins": backend.pin_count
                        }
                        for backend in backends
                    ],
                    "total_count": len(backends)
                }
                
        except Exception as e:
            logger.error(f"Error listing backends: {e}")
            return {"error": str(e)}
    
    async def get_backend_status(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get backend status information (mirrors 'ipfs-kit backend status')
        
        Arguments:
        - backend_name: Specific backend to check
        - check_health: Perform health check
        """
        backend_name = arguments.get("backend_name")
        check_health = arguments.get("check_health", True)
        
        try:
            if backend_name:
                # Get specific backend
                backend = await self.metadata_manager.get_backend_metadata(backend_name)
                if not backend:
                    return {"error": f"Backend '{backend_name}' not found"}
                
                # Get additional status from daemon if health check requested
                daemon_status = None
                if check_health and self.daemon_service.is_running:
                    try:
                        intelligent_status = await self.daemon_service.get_intelligent_status()
                        backend_details = intelligent_status.get("backends", {}).get("details", [])
                        daemon_status = next((d for d in backend_details if d.get("backend_name") == backend_name), None)
                    except Exception as e:
                        logger.warning(f"Could not get daemon status for {backend_name}: {e}")
                
                status = {
                    "backend_name": backend.name,
                    "type": backend.type,
                    "health_status": backend.health_status,
                    "pin_count": backend.pin_count,
                    "storage_usage_bytes": backend.storage_usage_bytes,
                    "last_updated": backend.last_updated.isoformat(),
                    "pin_mappings_available": backend.pin_mappings_available,
                    "car_files_available": backend.car_files_available,
                    "daemon_status": daemon_status
                }
                
                return status
            else:
                # Get summary of all backends
                backends = await self.metadata_manager.get_backend_metadata()
                
                summary = {
                    "total_backends": len(backends),
                    "healthy_backends": sum(1 for b in backends if b.health_status == "healthy"),
                    "unhealthy_backends": sum(1 for b in backends if b.health_status != "healthy"),
                    "total_pins": sum(b.pin_count for b in backends),
                    "total_storage_bytes": sum(b.storage_usage_bytes for b in backends),
                    "backends_with_pin_mappings": sum(1 for b in backends if b.pin_mappings_available),
                    "backends": [
                        {
                            "name": b.name,
                            "type": b.type,
                            "status": b.health_status,
                            "pins": b.pin_count
                        }
                        for b in backends
                    ]
                }
                
                return summary
                
        except Exception as e:
            logger.error(f"Error getting backend status: {e}")
            return {"error": str(e)}
    
    async def sync_backend(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sync backend data (mirrors 'ipfs-kit backend sync')
        
        Arguments:
        - backend_name: Backend to sync
        - force: Force sync even if up to date
        - dry_run: Show what would be synced
        """
        backend_name = arguments.get("backend_name")
        force = arguments.get("force", False)
        dry_run = arguments.get("dry_run", False)
        
        try:
            # Validate backend exists
            if backend_name:
                backend = await self.metadata_manager.get_backend_metadata(backend_name)
                if not backend:
                    return {"error": f"Backend '{backend_name}' not found"}
            
            if dry_run:
                # Show what would be synced
                if backend_name:
                    return {
                        "action": "sync_backend",
                        "backend": backend_name,
                        "dry_run": True,
                        "would_sync": True,
                        "message": f"Would sync backend '{backend_name}'"
                    }
                else:
                    backends = await self.metadata_manager.get_backend_metadata()
                    return {
                        "action": "sync_all_backends",
                        "dry_run": True,
                        "would_sync_count": len(backends),
                        "backends": [b.name for b in backends],
                        "message": f"Would sync {len(backends)} backends"
                    }
            else:
                # Perform actual sync using daemon service
                result = await self.daemon_service.force_sync(backend_name)
                return result
                
        except Exception as e:
            logger.error(f"Error syncing backend: {e}")
            return {"error": str(e)}
    
    async def migrate_pin_mappings(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Migrate backend pin mappings (mirrors 'ipfs-kit backend migrate-pin-mappings')
        
        Arguments:
        - filter: Filter backends to migrate  
        - dry_run: Show what would be migrated
        - verbose: Show detailed migration progress
        """
        filter_backends = arguments.get("filter")
        dry_run = arguments.get("dry_run", False)
        verbose = arguments.get("verbose", False)
        
        try:
            # Use daemon service to perform migration
            result = await self.daemon_service.migrate_pin_mappings(
                filter_backends=filter_backends,
                dry_run=dry_run
            )
            
            # Add verbose information if requested
            if verbose and not dry_run:
                # Get updated backend metadata to show migration results
                backends = await self.metadata_manager.get_backend_metadata(refresh=True)
                result["verbose_details"] = {
                    "migrated_backends": len([b for b in backends if b.pin_mappings_available]),
                    "backends_with_car_files": len([b for b in backends if b.car_files_available]),
                    "total_backends": len(backends)
                }
            
            return result
            
        except Exception as e:
            logger.error(f"Error migrating pin mappings: {e}")
            return {"error": str(e)}
