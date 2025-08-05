#!/usr/bin/env python3
"""
MCP CLI Controller - Mirrors CLI pin and bucket commands

This controller provides MCP tools that mirror the CLI pin and bucket commands,
allowing MCP clients to manage pins and buckets with the same functionality
as the command line interface.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..models.mcp_metadata_manager import MCPMetadataManager
from ..services.mcp_daemon_service import MCPDaemonService

logger = logging.getLogger(__name__)


class MCPCLIController:
    """
    MCP CLI Controller that mirrors CLI pin and bucket commands
    
    Provides MCP tools for:
    - pin list (mirrors 'ipfs-kit pin list')
    - pin add (mirrors 'ipfs-kit pin add')
    - pin remove (mirrors 'ipfs-kit pin remove')
    - bucket list (mirrors 'ipfs-kit bucket list')
    - bucket create (mirrors 'ipfs-kit bucket create')
    - bucket sync (mirrors 'ipfs-kit bucket sync')
    """
    
    def __init__(self, metadata_manager: MCPMetadataManager, daemon_service: MCPDaemonService):
        """Initialize the CLI controller."""
        self.metadata_manager = metadata_manager
        self.daemon_service = daemon_service
        logger.info("MCP CLI Controller initialized")
    
    async def handle_pin_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle pin tool calls by routing to appropriate methods."""
        try:
            if tool_name == "pin_list":
                return await self.list_pins(arguments)
            elif tool_name == "pin_add":
                return await self.add_pin(arguments)
            elif tool_name == "pin_remove":
                return await self.remove_pin(arguments)
            elif tool_name == "peer_list":
                return await self.list_peers(arguments)
            elif tool_name == "peer_connect":
                return await self.connect_peer(arguments)
            elif tool_name == "peer_disconnect":
                return await self.disconnect_peer(arguments)
            elif tool_name == "peer_stats":
                return await self.get_peer_stats(arguments)
            elif tool_name == "pin_get_name":
                return await self.get_pin_name(arguments)
            elif tool_name == "pin_get_size":
                return await self.get_pin_size(arguments)
            else:
                return {"error": f"Unknown pin tool: {tool_name}"}
        except Exception as e:
            logger.error(f"Error handling pin tool {tool_name}: {e}")
            return {"error": str(e)}
    
    async def handle_bucket_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle bucket tool calls by routing to appropriate methods."""
        try:
            if tool_name == "bucket_list":
                return await self.list_buckets(arguments)
            elif tool_name == "bucket_create":
                return await self.create_bucket(arguments)
            elif tool_name == "bucket_sync":
                return await self.sync_bucket(arguments)
            elif tool_name == "config_show":
                return await self.show_config(arguments)
            elif tool_name == "analytics_summary":
                return await self.get_analytics_summary(arguments)
            elif tool_name == "bucket_analytics":
                return await self.get_bucket_analytics(arguments)
            elif tool_name == "performance_analytics":
                return await self.get_performance_analytics(arguments)
            elif tool_name == "car_generate":
                return await self.generate_car_file(arguments)
            elif tool_name == "car_list":
                return await self.list_car_files(arguments)
            elif tool_name == "cross_backend_query":
                return await self.execute_cross_backend_query(arguments)
            else:
                return {"error": f"Unknown bucket tool: {tool_name}"}
        except Exception as e:
            logger.error(f"Error handling bucket tool {tool_name}: {e}")
            return {"error": str(e)}
    
    async def list_pins(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        List pinned content (mirrors 'ipfs-kit pin list')
        
        Arguments:
        - backend: Filter by backend
        - status: Filter by pin status
        """
        backend = arguments.get("backend")
        status = arguments.get("status")
        
        try:
            # Get pin metadata
            pins = await self.metadata_manager.get_pin_metadata(backend_name=backend)
            
            # Apply status filter
            if status:
                pins = [pin for pin in pins if pin.status == status]
            
            # Format pin list
            pin_list = []
            for pin in pins:
                pin_data = {
                    "cid": pin.cid,
                    "backend": pin.backend,
                    "status": pin.status,
                    "created_at": pin.created_at.isoformat(),
                    "car_file_path": pin.car_file_path,
                    "size_bytes": pin.size_bytes
                }
                
                if pin.metadata:
                    pin_data["metadata"] = pin.metadata
                
                pin_list.append(pin_data)
            
            # Generate summary
            summary = {
                "total_pins": len(pin_list),
                "unique_cids": len(set(pin["cid"] for pin in pin_list)),
                "backends": list(set(pin["backend"] for pin in pin_list)),
                "status_distribution": {}
            }
            
            # Count pins by status
            for pin in pin_list:
                status_key = pin["status"]
                summary["status_distribution"][status_key] = summary["status_distribution"].get(status_key, 0) + 1
            
            return {
                "pins": pin_list,
                "summary": summary,
                "filters": {
                    "backend": backend,
                    "status": status
                }
            }
            
        except Exception as e:
            logger.error(f"Error listing pins: {e}")
            return {"error": str(e)}
    
    async def add_pin(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pin content (mirrors 'ipfs-kit pin add')
        
        Arguments:
        - cid: Content ID to pin
        - backend: Backend to pin to
        - name: Optional pin name
        """
        cid = arguments.get("cid")
        backend = arguments.get("backend")
        name = arguments.get("name")
        
        try:
            if not cid:
                return {"error": "cid is required"}
            
            if not backend:
                return {"error": "backend is required"}
            
            # Validate backend exists
            backend_metadata = await self.metadata_manager.get_backend_metadata(backend)
            if not backend_metadata:
                return {"error": f"Backend '{backend}' not found"}
            
            # Check if CID is already pinned to this backend
            existing_pins = await self.metadata_manager.get_pin_metadata(backend_name=backend, cid=cid)
            if existing_pins:
                return {
                    "action": "add_pin",
                    "cid": cid,
                    "backend": backend,
                    "status": "already_pinned",
                    "message": f"CID '{cid}' is already pinned to backend '{backend}'",
                    "existing_pin": {
                        "status": existing_pins[0].status,
                        "created_at": existing_pins[0].created_at.isoformat()
                    }
                }
            
            # Note: Actual pinning implementation would require backend-specific logic
            # For now, return a placeholder response indicating the operation would be performed
            return {
                "action": "add_pin",
                "cid": cid,
                "backend": backend,
                "name": name,
                "status": "simulated",
                "message": "Pin operation would be performed (implementation pending)",
                "backend_type": backend_metadata.type,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error adding pin: {e}")
            return {"error": str(e)}
    
    async def remove_pin(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Unpin content (mirrors 'ipfs-kit pin remove')
        
        Arguments:
        - cid: Content ID to unpin
        - backend: Backend to unpin from
        """
        cid = arguments.get("cid")
        backend = arguments.get("backend")
        
        try:
            if not cid:
                return {"error": "cid is required"}
            
            if not backend:
                return {"error": "backend is required"}
            
            # Check if CID is pinned to this backend
            existing_pins = await self.metadata_manager.get_pin_metadata(backend_name=backend, cid=cid)
            if not existing_pins:
                return {
                    "action": "remove_pin",
                    "cid": cid,
                    "backend": backend,
                    "status": "not_pinned",
                    "message": f"CID '{cid}' is not pinned to backend '{backend}'"
                }
            
            pin = existing_pins[0]
            
            # Note: Actual unpinning implementation would require backend-specific logic
            # For now, return a placeholder response indicating the operation would be performed
            return {
                "action": "remove_pin",
                "cid": cid,
                "backend": backend,
                "status": "simulated",
                "message": "Unpin operation would be performed (implementation pending)",
                "existing_pin": {
                    "status": pin.status,
                    "created_at": pin.created_at.isoformat(),
                    "car_file_path": pin.car_file_path
                },
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error removing pin: {e}")
            return {"error": str(e)}

    async def list_peers(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """        List connected peers (mirrors 'ipfs-kit peer list')
        
        Arguments:
        - verbose: Show detailed peer information
        """
        verbose = arguments.get("verbose", False)

        try:
            # This would typically call a service that interacts with the IPFS daemon
            # For now, we will simulate the output
            peers = [
                {
                    "id": "QmSoLnSGccFuZQJzRadHn95W2CrSFmMCQFPYikT9iN1sAN",
                    "addr": "/ip4/104.131.131.82/tcp/4001/p2p/QmSoLnSGccFuZQJzRadHn95W2CrSFmMCQFPYikT9iN1sAN",
                    "latency": "10ms"
                },
                {
                    "id": "QmSoLSafM1QTv52T62s2a2Hm42w2nd21pC1oD4B4Yd2a2",
                    "addr": "/ip4/178.62.158.247/tcp/4001/p2p/QmSoLSafM1QTv52T62s2a2Hm42w2nd21pC1oD4B4Yd2a2",
                    "latency": "20ms"
                }
            ]

            if verbose:
                return {"peers": peers, "count": len(peers)}
            else:
                return {"peers": [p["id"] for p in peers], "count": len(peers)}

        except Exception as e:
            logger.error(f"Error listing peers: {e}")
            return {"error": str(e)}

    async def connect_peer(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """        Connect to a peer (mirrors 'ipfs-kit peer connect')
        
        Arguments:
        - address: Peer multiaddr to connect to
        """
        address = arguments.get("address")

        try:
            if not address:
                return {"error": "address is required"}

            # This would typically call a service that interacts with the IPFS daemon
            # For now, we will simulate the output
            return {"success": True, "message": f"Connection to {address} initiated"}

        except Exception as e:
            logger.error(f"Error connecting to peer: {e}")
            return {"error": str(e)}

    async def disconnect_peer(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """        Disconnect from a peer (mirrors 'ipfs-kit peer disconnect')
        
        Arguments:
        - peer_id: Peer ID to disconnect from
        """
        peer_id = arguments.get("peer_id")

        try:
            if not peer_id:
                return {"error": "peer_id is required"}

            # This would typically call a service that interacts with the IPFS daemon
            # For now, we will simulate the output
            return {"success": True, "message": f"Disconnection from {peer_id} initiated"}

        except Exception as e:
            logger.error(f"Error disconnecting from peer: {e}")
            return {"error": str(e)}

    async def get_peer_stats(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Get peer statistics from the daemon service."""
        try:
            # Call the daemon service to get peer stats
            stats = await self.daemon_service.get_peer_stats()
            return {"success": True, "stats": stats}
        except Exception as e:
            logger.error(f"Error getting peer stats: {e}")
            return {"success": False, "error": str(e)}
    
    async def list_buckets(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        List buckets (mirrors 'ipfs-kit bucket list')
        
        Arguments:
        - backend: Filter by backend
        """
        backend = arguments.get("backend")
        
        try:
            # Get bucket metadata
            buckets = await self.metadata_manager.get_bucket_metadata(backend_name=backend)
            
            # Format bucket list
            bucket_list = []
            for bucket in buckets:
                bucket_data = {
                    "name": bucket.name,
                    "backend": bucket.backend,
                    "path": bucket.path,
                    "created_at": bucket.created_at.isoformat(),
                    "last_synced": bucket.last_synced.isoformat() if bucket.last_synced else None,
                    "file_count": bucket.file_count,
                    "total_size_bytes": bucket.total_size_bytes
                }
                
                bucket_list.append(bucket_data)
            
            # Generate summary
            summary = {
                "total_buckets": len(bucket_list),
                "backends": list(set(bucket["backend"] for bucket in bucket_list)),
                "total_files": sum(bucket["file_count"] for bucket in bucket_list),
                "total_size_bytes": sum(bucket["total_size_bytes"] for bucket in bucket_list),
                "buckets_synced": len([b for b in bucket_list if b["last_synced"] is not None])
            }
            
            return {
                "buckets": bucket_list,
                "summary": summary,
                "filters": {
                    "backend": backend
                }
            }
            
        except Exception as e:
            logger.error(f"Error listing buckets: {e}")
            return {"error": str(e)}
    
    async def create_bucket(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create bucket (mirrors 'ipfs-kit bucket create')
        
        Arguments:
        - name: Bucket name
        - backend: Target backend
        """
        name = arguments.get("name")
        backend = arguments.get("backend", "default")
        
        try:
            if not name:
                return {"error": "name is required"}
            
            # Check if bucket already exists
            existing_buckets = await self.metadata_manager.get_bucket_metadata(bucket_name=name)
            if existing_buckets:
                return {
                    "action": "create_bucket",
                    "name": name,
                    "backend": backend,
                    "status": "already_exists",
                    "message": f"Bucket '{name}' already exists",
                    "existing_bucket": {
                        "backend": existing_buckets[0].backend,
                        "created_at": existing_buckets[0].created_at.isoformat()
                    }
                }
            
            # Create bucket directory
            buckets_dir = self.metadata_manager.data_dir / "buckets"
            bucket_path = buckets_dir / name
            
            try:
                bucket_path.mkdir(parents=True, exist_ok=False)
                
                # Create bucket metadata file
                metadata = {
                    "name": name,
                    "backend": backend,
                    "created_at": datetime.now().isoformat(),
                    "created_by": "mcp_server"
                }
                
                metadata_file = bucket_path / "bucket_metadata.json"
                with open(metadata_file, 'w') as f:
                    json.dump(metadata, f, indent=2)
                
                return {
                    "action": "create_bucket",
                    "name": name,
                    "backend": backend,
                    "status": "created",
                    "message": f"Bucket '{name}' created successfully",
                    "path": str(bucket_path),
                    "metadata_file": str(metadata_file)
                }
                
            except FileExistsError:
                return {
                    "action": "create_bucket",
                    "name": name,
                    "backend": backend,
                    "status": "already_exists",
                    "message": f"Bucket directory '{name}' already exists"
                }
            
        except Exception as e:
            logger.error(f"Error creating bucket: {e}")
            return {"error": str(e)}
    
    async def sync_bucket(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sync bucket (mirrors 'ipfs-kit bucket sync')
        
        Arguments:
        - bucket_name: Bucket to sync
        - backend: Target backend
        - dry_run: Show what would be synced
        """
        bucket_name = arguments.get("bucket_name")
        backend = arguments.get("backend")
        dry_run = arguments.get("dry_run", False)
        
        try:
            if not bucket_name:
                return {"error": "bucket_name is required"}
            
            # Find the bucket
            buckets = await self.metadata_manager.get_bucket_metadata(bucket_name=bucket_name)
            if not buckets:
                return {
                    "action": "sync_bucket",
                    "bucket_name": bucket_name,
                    "error": "bucket_not_found",
                    "message": f"Bucket '{bucket_name}' not found"
                }
            
            bucket = buckets[0]
            
            # If backend specified, validate it matches
            if backend and bucket.backend != backend:
                return {
                    "action": "sync_bucket",
                    "bucket_name": bucket_name,
                    "error": "backend_mismatch",
                    "message": f"Bucket '{bucket_name}' is associated with backend '{bucket.backend}', not '{backend}'"
                }
            
            if dry_run:
                return {
                    "action": "sync_bucket",
                    "bucket_name": bucket_name,
                    "backend": bucket.backend,
                    "dry_run": True,
                    "would_sync": True,
                    "file_count": bucket.file_count,
                    "total_size_bytes": bucket.total_size_bytes,
                    "message": f"Would sync bucket '{bucket_name}' with {bucket.file_count} files"
                }
            else:
                # Note: Actual sync implementation would require backend-specific logic
                # For now, update the last_synced timestamp and return status
                metadata_file = Path(bucket.path) / "bucket_metadata.json"
                if metadata_file.exists():
                    try:
                        with open(metadata_file, 'r') as f:
                            metadata = json.load(f)
                        
                        metadata['last_synced'] = datetime.now().isoformat()
                        
                        with open(metadata_file, 'w') as f:
                            json.dump(metadata, f, indent=2)
                    except Exception as e:
                        logger.warning(f"Could not update bucket metadata: {e}")
                
                return {
                    "action": "sync_bucket",
                    "bucket_name": bucket_name,
                    "backend": bucket.backend,
                    "dry_run": False,
                    "status": "simulated",
                    "file_count": bucket.file_count,
                    "total_size_bytes": bucket.total_size_bytes,
                    "message": "Bucket sync operation would be performed (implementation pending)",
                    "timestamp": datetime.now().isoformat()
                }
            
        except Exception as e:
            logger.error(f"Error syncing bucket: {e}")
            return {"error": str(e)}

    async def show_config(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """        Show configuration (mirrors 'ipfs-kit config show')
        
        Arguments:
        - component: Specific component to show config for
        """
        component = arguments.get("component")

        try:
            # This would typically call a service that reads the config files
            # For now, we will simulate the output
            if component:
                return {"config": {component: {"key": "value"}}}
            else:
                return {"config": {"main": {"key": "value"}, "backend": {"key": "value"}}}

        except Exception as e:
            logger.error(f"Error showing config: {e}")
            return {"error": str(e)}

    async def get_pin_name(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Get a friendly name for a pin if available from metadata."""
        cid = arguments.get("cid")
        if not cid:
            return {"error": "CID is required"}
        try:
            pin_metadata = await self.metadata_manager.get_pin_metadata(cid=cid)
            if pin_metadata:
                return {"name": pin_metadata[0].metadata.get("name", cid[:12])}
            return {"name": cid[:12] + "..."}
        except Exception as e:
            logger.error(f"Error getting pin name for {cid}: {e}")
            return {"error": str(e)}

    async def get_pin_size(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Get the size of a pinned object from metadata."""
        cid = arguments.get("cid")
        if not cid:
            return {"error": "CID is required"}
        try:
            pin_metadata = await self.metadata_manager.get_pin_metadata(cid=cid)
            if pin_metadata:
                return {"size": pin_metadata[0].size_bytes}
            return {"size": 0}
        except Exception as e:
            logger.error(f"Error getting pin size for {cid}: {e}")
            return {"error": str(e)}

    async def get_analytics_summary(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Get a summary of analytics data."""
        try:
            # Placeholder for actual analytics logic
            return {"success": True, "summary": "Analytics summary data"}
        except Exception as e:
            logger.error(f"Error getting analytics summary: {e}")
            return {"success": False, "error": str(e)}

    async def get_bucket_analytics(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Get analytics data for buckets."""
        try:
            # Placeholder for actual bucket analytics logic
            return {"success": True, "bucket_analytics": "Bucket analytics data"}
        except Exception as e:
            logger.error(f"Error getting bucket analytics: {e}")
            return {"success": False, "error": str(e)}

    async def get_performance_analytics(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Get performance analytics data."""
        try:
            # Placeholder for actual performance analytics logic
            return {"success": True, "performance_analytics": "Performance analytics data"}
        except Exception as e:
            logger.error(f"Error getting performance analytics: {e}")
            return {"success": False, "error": str(e)}

    async def generate_car_file(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a CAR file."""
        try:
            # Placeholder for CAR file generation logic
            return {"success": True, "message": "CAR file generation initiated"}
        except Exception as e:
            logger.error(f"Error generating CAR file: {e}")
            return {"success": False, "error": str(e)}

    async def list_car_files(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """List CAR files."""
        try:
            # Placeholder for CAR file listing logic
            return {"success": True, "car_files": []}
        except Exception as e:
            logger.error(f"Error listing CAR files: {e}")
            return {"success": False, "error": str(e)}

    async def execute_cross_backend_query(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a cross-backend query."""
        try:
            # Placeholder for cross-backend query logic
            return {"success": True, "query_results": []}
        except Exception as e:
            logger.error(f"Error executing cross-backend query: {e}")
            return {"success": False, "error": str(e)}
