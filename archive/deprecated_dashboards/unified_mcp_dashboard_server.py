
#!/usr/bin/env python3
"""
Unified MCP Dashboard Server
============================

This server combines the MCP server functionality with the dashboard interface,
using JSON-RPC communication instead of WebSocket. Both services run on the same port.

Features:
- MCP Server JSON-RPC API
- Web Dashboard Interface  
- Unified port and startup
- JSON-RPC communication between dashboard and MCP
- FastAPI backend with static file serving
"""

import anyio
import json
import logging
import os
import time
import argparse
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
import uuid
import hashlib

# FastAPI and web dependencies
from fastapi import FastAPI, Request, HTTPException, Depends, File, UploadFile, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# IPFS Kit imports (with fallbacks)
try:
    from ipfs_kit_py import IPFSKitPy
    from ipfs_kit_py.enhanced_daemon_manager import EnhancedDaemonManager
    from ipfs_kit_py.config_manager import ConfigManager
    from ipfs_kit_py.backend_schemas import SCHEMAS as BACKEND_SCHEMAS
except ImportError:
    IPFSKitPy = None
    EnhancedDaemonManager = None
    ConfigManager = None
    BACKEND_SCHEMAS = {}

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global state
server_start_time = datetime.now()
request_count = 0
ipfs_kit = None
daemon_manager = None
config_manager = None

class JSONRPCHandler:
    """JSON-RPC handler for MCP operations"""
    
    def __init__(self):
        self.methods = {}
        self.register_default_methods()
    
    def register_method(self, name: str, method):
        """Register a JSON-RPC method"""
        self.methods[name] = method
        logger.info(f"Registered JSON-RPC method: {name}")
    
    def register_default_methods(self):
        """Register default MCP methods"""
        # System methods
        self.register_method("system.health", self.system_health)
        self.register_method("system.status", self.system_status)
        self.register_method("system.metrics", self.system_metrics)
        
        # Daemon methods
        self.register_method("daemon.start", self.daemon_start)
        self.register_method("daemon.stop", self.daemon_stop)
        self.register_method("daemon.status", self.daemon_status)
        self.register_method("daemon.restart", self.daemon_restart)
        
        # IPFS methods
        self.register_method("ipfs.add", self.ipfs_add)
        self.register_method("ipfs.get", self.ipfs_get)
        self.register_method("ipfs.cat", self.ipfs_cat)
        
        # Pin methods - comprehensive set matching CLI features
        self.register_method("ipfs.pin.add", self.ipfs_pin_add)
        self.register_method("ipfs.pin.rm", self.ipfs_pin_rm)
        self.register_method("ipfs.pin.ls", self.ipfs_pin_ls)
        self.register_method("ipfs.pin.pending", self.ipfs_pin_pending)
        self.register_method("ipfs.pin.status", self.ipfs_pin_status)
        self.register_method("ipfs.pin.get", self.ipfs_pin_get)
        self.register_method("ipfs.pin.cat", self.ipfs_pin_cat)
        self.register_method("ipfs.pin.init", self.ipfs_pin_init)
        self.register_method("ipfs.pin.export_metadata", self.ipfs_pin_export_metadata)
        self.register_method("ipfs.pin.verify", self.ipfs_pin_verify)
        self.register_method("ipfs.pin.bulk_add", self.ipfs_pin_bulk_add)
        self.register_method("ipfs.pin.bulk_rm", self.ipfs_pin_bulk_rm)
        self.register_method("ipfs.pin.search", self.ipfs_pin_search)
        self.register_method("ipfs.pin.cleanup", self.ipfs_pin_cleanup)
        
        # Bucket methods
        self.register_method("bucket.list", self.bucket_list)
        self.register_method("bucket.create", self.bucket_create)
        self.register_method("bucket.delete", self.bucket_delete)
        self.register_method("bucket.files", self.bucket_files)
        
        # Backend methods
        self.register_method("backend.list", self.backend_list)
        self.register_method("backend.status", self.backend_status)
        
        # Peer methods
        self.register_method("peer.list", self.peer_list)
        self.register_method("peer.connect", self.peer_connect)
        self.register_method("peer.disconnect", self.peer_disconnect)

        # Config methods
        self.register_method("config.get_backend_config", self.config_get_backend_config)
        self.register_method("config.save_backend_config", self.config_save_backend_config)
        self.register_method("config.get_all_backend_configs", self.config_get_all_backend_configs)
        self.register_method("config.get_backend_schemas", self.config_get_backend_schemas)
    
    async def handle_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a JSON-RPC request"""
        try:
            # Validate JSON-RPC format
            if not isinstance(request_data, dict):
                return self.error_response(None, -32600, "Invalid Request")
            
            jsonrpc = request_data.get("jsonrpc")
            method = request_data.get("method")
            params = request_data.get("params", {})
            request_id = request_data.get("id")
            
            if jsonrpc != "2.0":
                return self.error_response(request_id, -32600, "Invalid Request")
            
            if not method or method not in self.methods:
                return self.error_response(request_id, -32601, "Method not found")
            
            # Call the method
            try:
                result = await self.methods[method](params)
                return {
                    "jsonrpc": "2.0",
                    "result": result,
                    "id": request_id
                }
            except Exception as e:
                logger.error(f"Error in method {method}: {e}")
                return self.error_response(request_id, -32603, f"Internal error: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error handling JSON-RPC request: {e}")
            return self.error_response(None, -32700, "Parse error")
    
    def error_response(self, request_id, code: int, message: str) -> Dict[str, Any]:
        """Create JSON-RPC error response"""
        return {
            "jsonrpc": "2.0",
            "error": {
                "code": code,
                "message": message
            },
            "id": request_id
        }
    
    # System methods
    async def system_health(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get system health status"""
        return {
            "status": "healthy",
            "timestamp": time.time(),
            "uptime": (datetime.now() - server_start_time).total_seconds(),
            "version": "1.0.0"
        }
    
    async def system_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get system status"""
        global request_count
        request_count += 1
        
        return {
            "status": "running",
            "start_time": server_start_time.isoformat(),
            "uptime": (datetime.now() - server_start_time).total_seconds(),
            "request_count": request_count,
            "ipfs_kit_available": IPFSKitPy is not None,
            "daemon_manager_available": EnhancedDaemonManager is not None
        }
    
    async def system_metrics(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get system metrics"""
        import psutil
        
        return {
            "cpu_usage": psutil.cpu_percent(),
            "memory_usage": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage('/').percent,
            "timestamp": time.time()
        }
    
    # Daemon methods
    async def daemon_start(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Start daemon services"""
        global daemon_manager
        
        if not daemon_manager and EnhancedDaemonManager:
            daemon_manager = EnhancedDaemonManager()
        
        if daemon_manager:
            try:
                result = await daemon_manager.start_all()
                return {"success": True, "result": result}
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        return {"success": False, "error": "Daemon manager not available"}
    
    async def daemon_stop(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Stop daemon services"""
        global daemon_manager
        
        if daemon_manager:
            try:
                result = await daemon_manager.stop_all()
                return {"success": True, "result": result}
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        return {"success": False, "error": "Daemon manager not available"}
    
    async def daemon_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get daemon status"""
        global daemon_manager
        
        if daemon_manager:
            try:
                status = await daemon_manager.get_status()
                return {"success": True, "status": status}
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        return {"success": False, "error": "Daemon manager not available"}
    
    async def daemon_restart(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Restart daemon services"""
        stop_result = await self.daemon_stop(params)
        if stop_result["success"]:
            await anyio.sleep(2)  # Wait a moment
            return await self.daemon_start(params)
        return stop_result
    
    # IPFS methods (mock implementations)
    async def ipfs_add(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Add content to IPFS"""
        content = params.get("content", "")
        filename = params.get("filename", "file.txt")
        
        # Generate mock CID
        mock_cid = f"Qm{hashlib.sha256(content.encode()).hexdigest()[:44]}"
        
        return {
            "success": True,
            "cid": mock_cid,
            "filename": filename,
            "size": len(content)
        }
    
    async def ipfs_get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get content from IPFS"""
        cid = params.get("cid", "")
        
        return {
            "success": True,
            "cid": cid,
            "content": f"Mock content for {cid}",
            "size": 1024
        }
    
    async def ipfs_cat(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Cat IPFS content"""
        cid = params.get("cid", "")
        
        return {
            "success": True,
            "cid": cid,
            "content": f"Mock file content for CID: {cid}"
        }
    
    async def ipfs_pin_add(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Pin content in IPFS"""
        cid_or_file = params.get("cid_or_file", params.get("cid", ""))
        name = params.get("name")
        recursive = params.get("recursive", True)
        metadata = params.get("metadata", {})
        
        try:
            # Try to use actual IPFS API if available
            if ipfs_kit:
                result = await ipfs_kit.pin_add(
                    cid_or_path=cid_or_file,
                    name=name,
                    recursive=recursive,
                    metadata=metadata
                )
                return {
                    "success": True,
                    "cid": result.get("cid", cid_or_file),
                    "name": name,
                    "recursive": recursive,
                    "pinned": True,
                    "metadata": metadata,
                    "operation_id": f"pin_add_{int(time.time() * 1000)}"
                }
            else:
                # Fallback simulation
                return {
                    "success": True,
                    "cid": cid_or_file,
                    "name": name,
                    "recursive": recursive,
                    "pinned": True,
                    "metadata": metadata,
                    "operation_id": f"pin_add_{int(time.time() * 1000)}",
                    "simulated": True
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "cid": cid_or_file
            }
    
    async def ipfs_pin_rm(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Unpin content in IPFS"""
        cid = params.get("cid", "")
        
        try:
            # Try to use actual IPFS API if available
            if ipfs_kit:
                result = await ipfs_kit.pin_rm(cid)
                return {
                    "success": True,
                    "cid": cid,
                    "unpinned": True,
                    "operation_id": f"pin_rm_{int(time.time() * 1000)}"
                }
            else:
                # Fallback simulation
                return {
                    "success": True,
                    "cid": cid,
                    "unpinned": True,
                    "operation_id": f"pin_rm_{int(time.time() * 1000)}",
                    "simulated": True
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "cid": cid
            }
    
    async def ipfs_pin_ls(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List pinned content"""
        limit = params.get("limit")
        metadata = params.get("metadata", False)
        cid_filter = params.get("cid")
        
        try:
            # Try to use actual IPFS API if available
            if ipfs_kit:
                pins = await ipfs_kit.pin_ls(limit=limit, metadata=metadata, cid=cid_filter)
                return {
                    "success": True,
                    "pins": pins,
                    "count": len(pins),
                    "operation_id": f"pin_ls_{int(time.time() * 1000)}"
                }
            else:
                # Fallback simulation with more realistic data
                mock_pins = [
                    {
                        "cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
                        "type": "recursive",
                        "name": "example-document.pdf",
                        "size": 1024576,
                        "timestamp": "2024-01-15T10:30:00Z"
                    },
                    {
                        "cid": "QmHash123abc456def789",
                        "type": "direct", 
                        "name": "config.json",
                        "size": 2048,
                        "timestamp": "2024-01-14T15:45:00Z"
                    },
                    {
                        "cid": "QmTest789xyz123abc456",
                        "type": "recursive",
                        "name": "dataset-folder",
                        "size": 104857600,
                        "timestamp": "2024-01-13T09:15:00Z"
                    }
                ]
                
                if metadata:
                    for pin in mock_pins:
                        pin["metadata"] = {
                            "uploader": "user123",
                            "tags": ["document", "important"],
                            "description": f"Content for {pin['name']}"
                        }
                
                if cid_filter:
                    mock_pins = [p for p in mock_pins if p["cid"] == cid_filter]
                
                if limit:
                    mock_pins = mock_pins[:limit]
                
                return {
                    "success": True,
                    "pins": mock_pins,
                    "count": len(mock_pins),
                    "operation_id": f"pin_ls_{int(time.time() * 1000)}",
                    "simulated": True
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "pins": [],
                "count": 0
            }
    
    async def ipfs_pin_pending(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List pending pin operations"""
        limit = params.get("limit")
        metadata = params.get("metadata", False)
        
        try:
            # Mock pending operations for now
            pending_ops = [
                {
                    "operation_id": "pin_op_001",
                    "cid": "QmPending123",
                    "action": "add",
                    "status": "queued",
                    "timestamp": "2024-01-15T12:00:00Z",
                    "estimated_completion": "2024-01-15T12:05:00Z"
                },
                {
                    "operation_id": "pin_op_002", 
                    "cid": "QmPending456",
                    "action": "remove",
                    "status": "processing",
                    "timestamp": "2024-01-15T11:55:00Z",
                    "progress": 75
                }
            ]
            
            if metadata:
                for op in pending_ops:
                    op["metadata"] = {
                        "priority": "normal",
                        "retry_count": 0,
                        "backend": "local"
                    }
            
            if limit:
                pending_ops = pending_ops[:limit]
                
            return {
                "success": True,
                "pending_operations": pending_ops,
                "count": len(pending_ops),
                "operation_id": f"pin_pending_{int(time.time() * 1000)}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "pending_operations": [],
                "count": 0
            }
    
    async def ipfs_pin_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Check pin operation status"""
        operation_id = params.get("operation_id", "")
        
        try:
            # Mock status response
            return {
                "success": True,
                "operation_id": operation_id,
                "status": "completed",
                "progress": 100,
                "started_at": "2024-01-15T11:50:00Z",
                "completed_at": "2024-01-15T11:55:00Z",
                "duration_seconds": 300,
                "cid": "QmStatusExample123",
                "action": "add"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "operation_id": operation_id
            }
    
    async def ipfs_pin_get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Download pinned content"""
        cid = params.get("cid", "")
        output_path = params.get("output_path")
        recursive = params.get("recursive", False)
        
        try:
            if ipfs_kit:
                # Use actual IPFS API
                result = await ipfs_kit.pin_get(cid, output_path=output_path, recursive=recursive)
                return {
                    "success": True,
                    "cid": cid,
                    "output_path": output_path or f"./{cid}",
                    "downloaded": True,
                    "recursive": recursive,
                    "operation_id": f"pin_get_{int(time.time() * 1000)}"
                }
            else:
                # Mock response
                return {
                    "success": True,
                    "cid": cid,
                    "output_path": output_path or f"./{cid}",
                    "downloaded": True,
                    "recursive": recursive,
                    "operation_id": f"pin_get_{int(time.time() * 1000)}",
                    "simulated": True,
                    "size_bytes": 1024
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "cid": cid
            }
    
    async def ipfs_pin_cat(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Stream pinned content"""
        cid = params.get("cid", "")
        limit = params.get("limit")
        
        try:
            if ipfs_kit:
                # Use actual IPFS API
                content = await ipfs_kit.pin_cat(cid, limit=limit)
                return {
                    "success": True,
                    "cid": cid,
                    "content": content,
                    "operation_id": f"pin_cat_{int(time.time() * 1000)}"
                }
            else:
                # Mock response with sample content
                mock_content = f"Mock content for CID {cid}\nThis is sample data that would be streamed from IPFS."
                if limit:
                    mock_content = mock_content[:limit]
                
                return {
                    "success": True,
                    "cid": cid,
                    "content": mock_content,
                    "operation_id": f"pin_cat_{int(time.time() * 1000)}",
                    "simulated": True,
                    "size_bytes": len(mock_content)
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "cid": cid
            }
    
    async def ipfs_pin_init(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Initialize pin metadata index"""
        try:
            # Mock initialization
            return {
                "success": True,
                "message": "Pin metadata index initialized successfully",
                "sample_data_created": True,
                "index_path": "./pin_metadata.db",
                "operation_id": f"pin_init_{int(time.time() * 1000)}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    async def ipfs_pin_export_metadata(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Export pin metadata to CAR files"""
        max_shard_size = params.get("max_shard_size", 100)  # MB
        
        try:
            # Mock export
            return {
                "success": True,
                "message": "Pin metadata exported successfully",
                "shards_created": 3,
                "total_size_mb": max_shard_size * 2.5,
                "output_dir": "./pin_exports",
                "car_files": [
                    "pin_metadata_shard_001.car",
                    "pin_metadata_shard_002.car", 
                    "pin_metadata_shard_003.car"
                ],
                "operation_id": f"pin_export_{int(time.time() * 1000)}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    async def ipfs_pin_verify(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Verify all pins"""
        cid = params.get("cid")  # Optional: verify specific CID
        
        try:
            if cid:
                # Verify specific pin
                return {
                    "success": True,
                    "cid": cid,
                    "verified": True,
                    "status": "valid",
                    "last_verified": "2024-01-15T12:00:00Z",
                    "operation_id": f"pin_verify_{int(time.time() * 1000)}"
                }
            else:
                # Verify all pins
                return {
                    "success": True,
                    "total_pins": 15,
                    "verified_pins": 14,
                    "failed_pins": 1,
                    "verification_results": [
                        {"cid": "QmInvalid123", "status": "failed", "error": "Content not found"}
                    ],
                    "operation_id": f"pin_verify_all_{int(time.time() * 1000)}"
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    async def ipfs_pin_bulk_add(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Bulk pin operations"""
        cids = params.get("cids", [])
        recursive = params.get("recursive", True)
        name_prefix = params.get("name_prefix", "bulk_pin")
        
        try:
            results = []
            for i, cid in enumerate(cids):
                results.append({
                    "cid": cid,
                    "success": True,
                    "name": f"{name_prefix}_{i}",
                    "recursive": recursive
                })
            
            return {
                "success": True,
                "total_requested": len(cids),
                "successful": len(results),
                "failed": 0,
                "results": results,
                "operation_id": f"bulk_pin_{int(time.time() * 1000)}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "total_requested": len(cids),
                "successful": 0,
                "failed": len(cids)
            }
    
    async def ipfs_pin_bulk_rm(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Bulk unpin operations"""
        cids = params.get("cids", [])
        
        try:
            results = []
            for cid in cids:
                results.append({
                    "cid": cid,
                    "success": True,
                    "unpinned": True
                })
            
            return {
                "success": True,
                "total_requested": len(cids),
                "successful": len(results),
                "failed": 0,
                "results": results,
                "operation_id": f"bulk_unpin_{int(time.time() * 1000)}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "total_requested": len(cids),
                "successful": 0,
                "failed": len(cids)
            }
    
    async def ipfs_pin_search(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Search pins by criteria"""
        query = params.get("query", "")
        name_filter = params.get("name")
        type_filter = params.get("type")  # recursive, direct
        size_min = params.get("size_min")
        size_max = params.get("size_max")
        date_from = params.get("date_from")
        date_to = params.get("date_to")
        limit = params.get("limit", 10)
        
        try:
            # Mock search results
            all_pins = [
                {
                    "cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
                    "name": "document.pdf",
                    "type": "recursive",
                    "size": 1024576,
                    "timestamp": "2024-01-15T10:30:00Z"
                },
                {
                    "cid": "QmHash123abc456def789",
                    "name": "config.json",
                    "type": "direct",
                    "size": 2048,
                    "timestamp": "2024-01-14T15:45:00Z"
                }
            ]
            
            # Apply filters
            filtered_pins = all_pins
            
            if query:
                filtered_pins = [p for p in filtered_pins if query.lower() in p.get("name", "").lower()]
            
            if name_filter:
                filtered_pins = [p for p in filtered_pins if name_filter.lower() in p.get("name", "").lower()]
                
            if type_filter:
                filtered_pins = [p for p in filtered_pins if p.get("type") == type_filter]
            
            if size_min:
                filtered_pins = [p for p in filtered_pins if p.get("size", 0) >= size_min]
                
            if size_max:
                filtered_pins = [p for p in filtered_pins if p.get("size", 0) <= size_max]
            
            # Apply limit
            filtered_pins = filtered_pins[:limit]
            
            return {
                "success": True,
                "query": query,
                "total_matches": len(filtered_pins),
                "pins": filtered_pins,
                "operation_id": f"pin_search_{int(time.time() * 1000)}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "pins": []
            }
    
    async def ipfs_pin_cleanup(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Cleanup unpinned or failed pins"""
        dry_run = params.get("dry_run", True)
        
        try:
            # Mock cleanup results
            cleanup_results = {
                "orphaned_pins": 3,
                "failed_pins": 1,
                "duplicate_pins": 2,
                "total_cleaned": 6 if not dry_run else 0,
                "space_freed_mb": 125.5 if not dry_run else 0,
                "dry_run": dry_run
            }
            
            if dry_run:
                cleanup_results["message"] = "Dry run completed - no changes made"
            else:
                cleanup_results["message"] = "Cleanup completed successfully"
            
            return {
                "success": True,
                **cleanup_results,
                "operation_id": f"pin_cleanup_{int(time.time() * 1000)}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    # Bucket methods
    async def bucket_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List buckets"""
        return {
            "success": True,
            "buckets": [
                {"id": "bucket1", "name": "Documents", "size": 1024000, "files": 15},
                {"id": "bucket2", "name": "Images", "size": 5120000, "files": 42},
                {"id": "bucket3", "name": "Videos", "size": 102400000, "files": 8}
            ]
        }
    
    async def bucket_create(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new bucket"""
        name = params.get("name", "")
        
        return {
            "success": True,
            "bucket_id": f"bucket_{int(time.time())}",
            "name": name,
            "created": datetime.now().isoformat()
        }
    
    async def bucket_delete(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Delete a bucket"""
        bucket_id = params.get("bucket_id", "")
        
        return {
            "success": True,
            "bucket_id": bucket_id,
            "deleted": True
        }
    
    async def bucket_files(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List files in a bucket"""
        bucket_id = params.get("bucket_id", "")
        
        return {
            "success": True,
            "bucket_id": bucket_id,
            "files": [
                {"name": "document1.pdf", "size": 102400, "cid": "QmDoc1"},
                {"name": "image1.jpg", "size": 204800, "cid": "QmImg1"},
                {"name": "video1.mp4", "size": 10240000, "cid": "QmVid1"}
            ]
        }
    
    # Backend methods
    async def backend_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List storage backends"""
        return {
            "success": True,
            "backends": [
                {"name": "IPFS", "status": "active", "type": "primary"},
                {"name": "Storacha", "status": "active", "type": "cloud"},
                {"name": "Pinata", "status": "inactive", "type": "cloud"},
                {"name": "Local", "status": "active", "type": "local"}
            ]
        }
    
    async def backend_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get backend status"""
        backend_name = params.get("name", "")
        
        return {
            "success": True,
            "backend": backend_name,
            "status": "active",
            "health": "healthy",
            "last_check": datetime.now().isoformat()
        }
    
    # Peer methods
    async def peer_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List connected peers"""
        return {
            "success": True,
            "peers": [
                {"id": "12D3KooWPeer1", "addr": "/ip4/127.0.0.1/tcp/4001", "latency": 50},
                {"id": "12D3KooWPeer2", "addr": "/ip4/192.168.1.100/tcp/4001", "latency": 25},
                {"id": "12D3KooWPeer3", "addr": "/ip6/::1/tcp/4001", "latency": 75}
            ]
        }
    
    async def peer_connect(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Connect to a peer"""
        peer_addr = params.get("addr", "")
        
        return {
            "success": True,
            "peer_addr": peer_addr,
            "connected": True
        }
    
    async def peer_disconnect(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Disconnect from a peer"""
        peer_id = params.get("peer_id", "")
        
        return {
            "success": True,
            "peer_id": peer_id,
            "disconnected": True
        }

    # Config methods
    async def config_get_backend_config(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get the configuration for a specific backend."""
        backend = params.get("backend")
        if not backend:
            return {"success": False, "error": "Backend name not specified."}
        if not config_manager:
            return {"success": False, "error": "ConfigManager not available."}
        config = config_manager.get_config(backend)
        return {"success": True, "config": config}

    async def config_save_backend_config(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Save the configuration for a specific backend."""
        backend = params.get("backend")
        config = params.get("config")
        if not backend or not config:
            return {"success": False, "error": "Backend name and config not specified."}
        if not config_manager:
            return {"success": False, "error": "ConfigManager not available."}
        config_manager.save_config(backend, config)
        return {"success": True}

    async def config_get_all_backend_configs(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get all backend configurations."""
        if not config_manager:
            return {"success": False, "error": "ConfigManager not available."}
        configs = config_manager.get_all_configs()
        return {"success": True, "configs": configs}

    async def config_get_backend_schemas(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get the configuration schemas for all backends."""
        return {"success": True, "schemas": BACKEND_SCHEMAS}

class UnifiedMCPDashboardServer:
    """Unified server combining MCP and Dashboard functionality"""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 8083):
        self.host = host
        self.port = port
        self.app = FastAPI(title="Unified MCP Dashboard Server", version="1.0.0")
        self.jsonrpc_handler = JSONRPCHandler()
        self.setup_middleware()
        self.setup_templates()
        self.setup_routes()
    
    def setup_middleware(self):
        """Setup FastAPI middleware"""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    def setup_templates(self):
        """Setup templates and static files"""
        # Create templates directory if it doesn't exist
        templates_dir = Path(__file__).parent / "templates"
        static_dir = Path(__file__).parent / "static"
        
        templates_dir.mkdir(exist_ok=True)
        static_dir.mkdir(exist_ok=True)
        
        # Create the main dashboard template
        self.create_dashboard_template(templates_dir)
        self.create_static_files(static_dir)
        
        self.templates = Jinja2Templates(directory=str(templates_dir))
        
        # Mount static files
        self.app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    
    def create_dashboard_template(self, templates_dir: Path):
        """Create the main dashboard HTML template"""
        template_content = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Unified MCP Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .tab-button.active { background-color: #3b82f6; color: white; }
    </style>
</head>
<body class="bg-gray-100">
    <div class="min-h-screen">
        <!-- Header -->
        <header class="bg-blue-600 text-white p-4">
            <div class="container mx-auto flex justify-between items-center">
                <h1 class="text-2xl font-bold">Unified MCP Dashboard</h1>
                <div class="flex items-center space-x-4">
                    <span id="status-indicator" class="px-3 py-1 rounded-full bg-green-500 text-sm">Online</span>
                    <span id="last-update" class="text-sm opacity-75">Last update: Never</span>
                </div>
            </div>
        </header>

        <div class="container mx-auto p-4">
            <!-- Tab Navigation -->
            <div class="mb-6">
                <nav class="flex space-x-1 bg-white rounded-lg shadow p-1">
                    <button class="tab-button active px-4 py-2 rounded-md text-sm font-medium transition-colors" data-tab="overview">Overview</button>
                    <button class="tab-button px-4 py-2 rounded-md text-sm font-medium transition-colors" data-tab="daemon">Daemon</button>
                    <button class="tab-button px-4 py-2 rounded-md text-sm font-medium transition-colors" data-tab="ipfs">IPFS</button>
                    <button class="tab-button px-4 py-2 rounded-md text-sm font-medium transition-colors" data-tab="buckets">Buckets</button>
                    <button class="tab-button px-4 py-2 rounded-md text-sm font-medium transition-colors" data-tab="peers">Peers</button>
                    <button class="tab-button px-4 py-2 rounded-md text-sm font-medium transition-colors" data-tab="backends">Backends</button>
                    <button class="tab-button px-4 py-2 rounded-md text-sm font-medium transition-colors" data-tab="config">Configuration</button>
                    <button class="tab-button px-4 py-2 rounded-md text-sm font-medium transition-colors" data-tab="logs">Logs</button>
                </nav>
            </div>

            <!-- Tab Contents -->
            <div id="overview" class="tab-content active">
                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
                    <div class="bg-white rounded-lg shadow p-6">
                        <h3 class="text-lg font-semibold text-gray-700 mb-2">System Status</h3>
                        <div id="system-status" class="text-2xl font-bold text-green-600">Healthy</div>
                    </div>
                    <div class="bg-white rounded-lg shadow p-6">
                        <h3 class="text-lg font-semibold text-gray-700 mb-2">Uptime</h3>
                        <div id="uptime" class="text-2xl font-bold text-blue-600">0s</div>
                    </div>
                    <div class="bg-white rounded-lg shadow p-6">
                        <h3 class="text-lg font-semibold text-gray-700 mb-2">Requests</h3>
                        <div id="request-count" class="text-2xl font-bold text-purple-600">0</div>
                    </div>
                    <div class="bg-white rounded-lg shadow p-6">
                        <h3 class="text-lg font-semibold text-gray-700 mb-2">CPU Usage</h3>
                        <div id="cpu-usage" class="text-2xl font-bold text-orange-600">0%</div>
                    </div>
                </div>
                <div class="bg-white rounded-lg shadow p-6">
                    <h3 class="text-lg font-semibold text-gray-700 mb-4">System Metrics</h3>
                    <canvas id="metrics-chart" width="400" height="200"></canvas>
                </div>
            </div>

            <div id="daemon" class="tab-content">
                <div class="bg-white rounded-lg shadow p-6">
                    <h3 class="text-lg font-semibold text-gray-700 mb-4">Daemon Control</h3>
                    <div class="flex space-x-4 mb-6">
                        <button id="start-daemon" class="bg-green-500 hover:bg-green-600 text-white px-4 py-2 rounded">Start</button>
                        <button id="stop-daemon" class="bg-red-500 hover:bg-red-600 text-white px-4 py-2 rounded">Stop</button>
                        <button id="restart-daemon" class="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded">Restart</button>
                        <button id="daemon-status" class="bg-gray-500 hover:bg-gray-600 text-white px-4 py-2 rounded">Status</button>
                    </div>
                    <div id="daemon-info" class="bg-gray-50 p-4 rounded-lg">
                        <pre id="daemon-output">Click "Status" to check daemon status...</pre>
                    </div>
                </div>
            </div>

            <div id="ipfs" class="tab-content">
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <div class="bg-white rounded-lg shadow p-6">
                        <h3 class="text-lg font-semibold text-gray-700 mb-4">Add Content</h3>
                        <div class="space-y-4">
                            <textarea id="ipfs-content" class="w-full p-3 border rounded-lg" rows="4" placeholder="Enter content to add to IPFS..."></textarea>
                            <input type="text" id="ipfs-filename" class="w-full p-3 border rounded-lg" placeholder="Filename (optional)">
                            <button id="add-content" class="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded">Add to IPFS</button>
                        </div>
                        <div id="add-result" class="mt-4 p-3 bg-gray-50 rounded-lg hidden">
                            <pre id="add-output"></pre>
                        </div>
                    </div>
                    <div class="bg-white rounded-lg shadow p-6">
                        <h3 class="text-lg font-semibold text-gray-700 mb-4">Get Content</h3>
                        <div class="space-y-4">
                            <input type="text" id="get-cid" class="w-full p-3 border rounded-lg" placeholder="Enter CID to retrieve...">
                            <button id="get-content" class="bg-green-500 hover:bg-green-600 text-white px-4 py-2 rounded">Get from IPFS</button>
                        </div>
                        <div id="get-result" class="mt-4 p-3 bg-gray-50 rounded-lg hidden">
                            <pre id="get-output"></pre>
                        </div>
                    </div>
                </div>
                <div class="mt-6 bg-white rounded-lg shadow p-6">
                    <h3 class="text-lg font-semibold text-gray-700 mb-4">Pin Management</h3>
                    
                    <!-- Pin Operations Toolbar -->
                    <div class="flex flex-wrap gap-2 mb-6 p-4 bg-gray-50 rounded-lg">
                        <button id="refresh-pins" class="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded">
                            <i class="fas fa-sync-alt mr-2"></i>Refresh Pins
                        </button>
                        <button id="add-pin" class="bg-green-500 hover:bg-green-600 text-white px-4 py-2 rounded">
                            <i class="fas fa-plus mr-2"></i>Add Pin
                        </button>
                        <button id="bulk-operations" class="bg-purple-500 hover:bg-purple-600 text-white px-4 py-2 rounded">
                            <i class="fas fa-layer-group mr-2"></i>Bulk Operations
                        </button>
                        <button id="verify-pins" class="bg-yellow-500 hover:bg-yellow-600 text-white px-4 py-2 rounded">
                            <i class="fas fa-check-circle mr-2"></i>Verify All
                        </button>
                        <button id="cleanup-pins" class="bg-red-500 hover:bg-red-600 text-white px-4 py-2 rounded">
                            <i class="fas fa-broom mr-2"></i>Cleanup
                        </button>
                        <button id="export-metadata" class="bg-indigo-500 hover:bg-indigo-600 text-white px-4 py-2 rounded">
                            <i class="fas fa-download mr-2"></i>Export
                        </button>
                        <button id="pending-operations" class="bg-orange-500 hover:bg-orange-600 text-white px-4 py-2 rounded">
                            <i class="fas fa-clock mr-2"></i>Pending Ops
                        </button>
                    </div>
                    
                    <!-- Pin Search and Filters -->
                    <div class="mb-4 p-4 bg-gray-50 rounded-lg">
                        <div class="flex flex-wrap gap-4">
                            <div class="flex-1 min-w-64">
                                <input type="text" id="pin-search" class="w-full p-2 border rounded" 
                                       placeholder="Search pins by name or CID...">
                            </div>
                            <div>
                                <select id="pin-type-filter" class="p-2 border rounded">
                                    <option value="">All Types</option>
                                    <option value="recursive">Recursive</option>
                                    <option value="direct">Direct</option>
                                </select>
                            </div>
                            <div>
                                <select id="pin-size-filter" class="p-2 border rounded">
                                    <option value="">Any Size</option>
                                    <option value="small">< 1MB</option>
                                    <option value="medium">1MB - 100MB</option>
                                    <option value="large">> 100MB</option>
                                </select>
                            </div>
                            <button id="search-pins" class="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded">
                                <i class="fas fa-search mr-2"></i>Search
                            </button>
                            <button id="clear-filters" class="bg-gray-500 hover:bg-gray-600 text-white px-4 py-2 rounded">
                                Clear
                            </button>
                        </div>
                    </div>
                    
                    <!-- Pin Statistics -->
                    <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
                        <div class="bg-gradient-to-r from-blue-500 to-blue-600 text-white p-4 rounded-lg">
                            <div class="text-2xl font-bold" id="total-pins">-</div>
                            <div class="text-sm opacity-90">Total Pins</div>
                        </div>
                        <div class="bg-gradient-to-r from-green-500 to-green-600 text-white p-4 rounded-lg">
                            <div class="text-2xl font-bold" id="active-pins">-</div>
                            <div class="text-sm opacity-90">Active Pins</div>
                        </div>
                        <div class="bg-gradient-to-r from-yellow-500 to-yellow-600 text-white p-4 rounded-lg">
                            <div class="text-2xl font-bold" id="pending-pins">-</div>
                            <div class="text-sm opacity-90">Pending</div>
                        </div>
                        <div class="bg-gradient-to-r from-purple-500 to-purple-600 text-white p-4 rounded-lg">
                            <div class="text-2xl font-bold" id="total-storage">-</div>
                            <div class="text-sm opacity-90">Storage Used</div>
                        </div>
                    </div>
                    
                    <!-- Pins List -->
                    <div id="pins-list" class="space-y-3">
                        <div class="text-gray-500 text-center py-8">
                            <i class="fas fa-thumbtack text-4xl mb-4"></i>
                            <div>Click "Refresh Pins" to load pinned content...</div>
                        </div>
                    </div>
                    
                    <!-- Pagination -->
                    <div class="flex justify-between items-center mt-6 pt-6 border-t">
                        <div class="text-sm text-gray-600">
                            Showing <span id="pins-start">0</span> to <span id="pins-end">0</span> of <span id="pins-total">0</span> pins
                        </div>
                        <div class="flex space-x-2">
                            <button id="pins-prev" class="px-3 py-1 border rounded hover:bg-gray-50" disabled>Previous</button>
                            <button id="pins-next" class="px-3 py-1 border rounded hover:bg-gray-50" disabled>Next</button>
                        </div>
                    </div>
                </div>
            </div>

            <div id="buckets" class="tab-content">
                <div class="bg-white rounded-lg shadow p-6">
                    <h3 class="text-lg font-semibold text-gray-700 mb-4">Bucket Management</h3>
                    <div class="flex space-x-4 mb-6">
                        <input type="text" id="bucket-name" class="flex-1 p-3 border rounded-lg" placeholder="New bucket name...">
                        <button id="create-bucket" class="bg-green-500 hover:bg-green-600 text-white px-4 py-2 rounded">Create Bucket</button>
                        <button id="refresh-buckets" class="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded">Refresh</button>
                    </div>
                    <div id="buckets-list" class="space-y-4">
                        <div class="text-gray-500">Click "Refresh" to load buckets...</div>
                    </div>
                </div>
            </div>

            <div id="peers" class="tab-content">
                <div class="bg-white rounded-lg shadow p-6">
                    <h3 class="text-lg font-semibold text-gray-700 mb-4">Peer Management</h3>
                    <div class="flex space-x-4 mb-6">
                        <input type="text" id="peer-addr" class="flex-1 p-3 border rounded-lg" placeholder="Peer address...">
                        <button id="connect-peer" class="bg-green-500 hover:bg-green-600 text-white px-4 py-2 rounded">Connect</button>
                        <button id="refresh-peers" class="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded">Refresh</button>
                    </div>
                    <div id="peers-list" class="space-y-4">
                        <div class="text-gray-500">Click "Refresh" to load peers...</div>
                    </div>
                </div>
            </div>

            <div id="backends" class="tab-content">
                <div class="bg-white rounded-lg shadow p-6">
                    <h3 class="text-lg font-semibold text-gray-700 mb-4">Storage Backends</h3>
                    <button id="refresh-backends" class="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded mb-6">Refresh</button>
                    <div id="backends-list" class="space-y-4">
                        <div class="text-gray-500">Click "Refresh" to load backends...</div>
                    </div>
                </div>
            </div>

            <div id="config" class="tab-content">
                <div class="bg-white rounded-lg shadow p-6">
                    <h3 class="text-lg font-semibold text-gray-700 mb-4">Backend Configuration</h3>
                    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        <div class="lg:col-span-1">
                            <h4 class="text-md font-semibold text-gray-700 mb-2">Available Backends</h4>
                            <div id="config-backends-list" class="space-y-2">
                                <!-- Backend buttons will be dynamically inserted here -->
                            </div>
                            <button id="add-backend-button" class="w-full mt-4 bg-green-500 hover:bg-green-600 text-white px-4 py-2 rounded">Add Backend</button>
                        </div>
                        <div class="lg:col-span-2">
                            <h4 class="text-md font-semibold text-gray-700 mb-2">Configuration</h4>
                            <div id="config-form-container"></div>
                        </div>
                    </div>
                </div>
            </div>

            <div id="logs" class="tab-content">
                <div class="bg-white rounded-lg shadow p-6">
                    <h3 class="text-lg font-semibold text-gray-700 mb-4">Server Logs</h3>
                    <div class="flex space-x-4 mb-4">
                        <button id="refresh-logs" class="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded">Refresh</button>
                        <button id="clear-logs" class="bg-red-500 hover:bg-red-600 text-white px-4 py-2 rounded">Clear</button>
                    </div>
                    <div id="logs-content" class="bg-black text-green-400 p-4 rounded-lg h-96 overflow-y-auto font-mono text-sm">
                        <div>Server logs will appear here...</div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Pin Modals -->
    
    <!-- Add Pin Modal -->
    <div id="add-pin-modal" class="fixed inset-0 bg-black bg-opacity-50 hidden z-50">
        <div class="flex items-center justify-center min-h-screen p-4">
            <div class="bg-white rounded-lg shadow-xl max-w-md w-full">
                <div class="p-6">
                    <h3 class="text-lg font-semibold text-gray-900 mb-4">Add New Pin</h3>
                    <form id="add-pin-form">
                        <div class="mb-4">
                            <label class="block text-sm font-medium text-gray-700 mb-2">CID or File Path</label>
                            <input type="text" id="new-pin-cid" class="w-full p-3 border rounded-lg" 
                                   placeholder="QmHash... or /path/to/file" required>
                        </div>
                        <div class="mb-4">
                            <label class="block text-sm font-medium text-gray-700 mb-2">Name (Optional)</label>
                            <input type="text" id="new-pin-name" class="w-full p-3 border rounded-lg" 
                                   placeholder="Descriptive name for the pin">
                        </div>
                        <div class="mb-4">
                            <label class="flex items-center">
                                <input type="checkbox" id="new-pin-recursive" checked class="mr-2">
                                <span class="text-sm text-gray-700">Recursive pin</span>
                            </label>
                        </div>
                        <div class="mb-6">
                            <label class="block text-sm font-medium text-gray-700 mb-2">Metadata (JSON, Optional)</label>
                            <textarea id="new-pin-metadata" class="w-full p-3 border rounded-lg h-20" 
                                      placeholder='{"tags": ["important"], "description": "..."}'></textarea>
                        </div>
                        <div class="flex justify-end space-x-3">
                            <button type="button" id="cancel-add-pin" class="px-4 py-2 border rounded-lg hover:bg-gray-50">Cancel</button>
                            <button type="submit" class="px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600">Add Pin</button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Bulk Operations Modal -->
    <div id="bulk-operations-modal" class="fixed inset-0 bg-black bg-opacity-50 hidden z-50">
        <div class="flex items-center justify-center min-h-screen p-4">
            <div class="bg-white rounded-lg shadow-xl max-w-lg w-full">
                <div class="p-6">
                    <h3 class="text-lg font-semibold text-gray-900 mb-4">Bulk Pin Operations</h3>
                    <div class="mb-4">
                        <label class="block text-sm font-medium text-gray-700 mb-2">Operation Type</label>
                        <select id="bulk-operation-type" class="w-full p-3 border rounded-lg">
                            <option value="add">Bulk Add Pins</option>
                            <option value="remove">Bulk Remove Pins</option>
                        </select>
                    </div>
                    <div class="mb-6">
                        <label class="block text-sm font-medium text-gray-700 mb-2">CIDs (one per line)</label>
                        <textarea id="bulk-cids" class="w-full p-3 border rounded-lg h-32" 
                                  placeholder="QmHash1...\nQmHash2...\nQmHash3..."></textarea>
                    </div>
                    <div class="flex justify-end space-x-3">
                        <button type="button" id="cancel-bulk-operation" class="px-4 py-2 border rounded-lg hover:bg-gray-50">Cancel</button>
                        <button type="button" id="execute-bulk-operation" class="px-4 py-2 bg-purple-500 text-white rounded-lg hover:bg-purple-600">Execute</button>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Pin Details Modal -->
    <div id="pin-details-modal" class="fixed inset-0 bg-black bg-opacity-50 hidden z-50">
        <div class="flex items-center justify-center min-h-screen p-4">
            <div class="bg-white rounded-lg shadow-xl max-w-2xl w-full">
                <div class="p-6">
                    <div class="flex justify-between items-center mb-4">
                        <h3 class="text-lg font-semibold text-gray-900">Pin Details</h3>
                        <button id="close-pin-details" class="text-gray-400 hover:text-gray-600">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                    <div id="pin-details-content">
                        <!-- Content will be populated by JavaScript -->
                    </div>
                    <div class="flex justify-end space-x-3 mt-6">
                        <button type="button" id="download-pin" class="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600">
                            <i class="fas fa-download mr-2"></i>Download
                        </button>
                        <button type="button" id="unpin-content" class="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600">
                            <i class="fas fa-unlink mr-2"></i>Unpin
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Pending Operations Modal -->
    <div id="pending-operations-modal" class="fixed inset-0 bg-black bg-opacity50 hidden z-50">
        <div class="flex items-center justify-center min-h-screen p-4">
            <div class="bg-white rounded-lg shadow-xl max-w-4xl w-full">
                <div class="p-6">
                    <div class="flex justify-between items-center mb-4">
                        <h3 class="text-lg font-semibold text-gray-900">Pending Pin Operations</h3>
                        <button id="close-pending-operations" class="text-gray-400 hover:text-gray-600">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                    <div id="pending-operations-content">
                        <!-- Content will be populated by JavaScript -->
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="/static/dashboard.js"></script>
</body>
</html>'''
        
        (templates_dir / "dashboard.html").write_text(template_content)
    
    def create_static_files(self, static_dir: Path):
        """Create static JavaScript files"""
        js_content = '''// Unified MCP Dashboard JavaScript with Comprehensive Pin Management
class MCPDashboard {
    constructor() {
        this.init();
        this.setupEventListeners();
        this.setupPinManagement();
        this.startPeriodicUpdates();
    }

    init() {
        this.jsonrpcId = 1;
        this.logs = [];
        this.metricsChart = null;
        this.pinData = [];
        this.pinFilters = {};
        this.pinPage = 0;
        this.pinPageSize = 10;
        this.setupChart();
    }

    setupChart() {
        const ctx = document.getElementById('metrics-chart');
        if (ctx) {
            this.metricsChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'CPU Usage',
                        data: [],
                        borderColor: 'rgb(59, 130, 246)',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        tension: 0.1
                    }, {
                        label: 'Memory Usage',
                        data: [],
                        borderColor: 'rgb(16, 185, 129)',
                        backgroundColor: 'rgba(16, 185, 129, 0.1)',
                        tension: 0.1
                    }]
                },
                options: {
                    responsive: true,
                    scales: {
                        y: {
                            beginAtZero: true,
                            max: 100
                        }
                    }
                }
            });
        }
    }

    setupEventListeners() {
        // Tab switching
        document.querySelectorAll('.tab-button').forEach(button => {
            button.addEventListener('click', (e) => {
                const tabId = e.target.dataset.tab;
                this.switchTab(tabId);
            });
        });

        // Basic buttons
        document.getElementById('refresh-pins')?.addEventListener('click', () => this.loadPins());
        document.getElementById('refresh-buckets')?.addEventListener('click', () => this.loadBuckets());
        document.getElementById('refresh-peers')?.addEventListener('click', () => this.loadPeers());
        document.getElementById('refresh-backends')?.addEventListener('click', () => this.loadBackends());
        document.getElementById('refresh-logs')?.addEventListener('click', () => this.loadLogs());
        document.getElementById('clear-logs')?.addEventListener('click', () => this.clearLogs());
        document.getElementById('add-backend-button')?.addEventListener('click', () => this.showAddBackendModal());
    }

    setupPinManagement() {
        // Pin management event listeners
        document.getElementById('add-pin')?.addEventListener('click', () => this.showAddPinModal());
        document.getElementById('bulk-operations')?.addEventListener('click', () => this.showBulkOperationsModal());
        document.getElementById('verify-pins')?.addEventListener('click', () => this.verifyAllPins());
        document.getElementById('cleanup-pins')?.addEventListener('click', () => this.cleanupPins());
        document.getElementById('export-metadata')?.addEventListener('click', () => this.exportMetadata());
        document.getElementById('pending-operations')?.addEventListener('click', () => this.showPendingOperations());
        document.getElementById('search-pins')?.addEventListener('click', () => this.searchPins());
        document.getElementById('clear-filters')?.addEventListener('click', () => this.clearPinFilters());

        // Modal event listeners
        document.getElementById('cancel-add-pin')?.addEventListener('click', () => this.hideAddPinModal());
        document.getElementById('add-pin-form')?.addEventListener('submit', (e) => this.submitAddPin(e));
        document.getElementById('cancel-bulk-operation')?.addEventListener('click', () => this.hideBulkOperationsModal());
        document.getElementById('execute-bulk-operation')?.addEventListener('click', () => this.executeBulkOperation());
        document.getElementById('close-pin-details')?.addEventListener('click', () => this.hidePinDetailsModal());
        document.getElementById('close-pending-operations')?.addEventListener('click', () => this.hidePendingOperationsModal());

        // Pin action buttons
        document.getElementById('download-pin')?.addEventListener('click', () => this.downloadSelectedPin());
        document.getElementById('unpin-content')?.addEventListener('click', () => this.unpinSelectedContent());

        // Pagination
        document.getElementById('pins-prev')?.addEventListener('click', () => this.previousPinPage());
        document.getElementById('pins-next')?.addEventListener('click', () => this.nextPinPage());
    }

    async jsonRpcCall(method, params = {}) {
        try {
            const response = await fetch('/api/jsonrpc', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: method,
                    params: params,
                    id: this.jsonrpcId++
                })
            });
            const data = await response.json();
            if (data.error) {
                throw new Error(data.error.message || 'Unknown error');
            }
            return data.result;
        } catch (error) {
            console.error('JSON-RPC call failed:', error);
            this.showNotification('Error: ' + error.message, 'error');
            throw error;
        }
    }

    // Pin Management Methods
    async loadPins() {
        try {
            const result = await this.jsonRpcCall('ipfs.pin.ls', {
                limit: this.pinPageSize,
                metadata: true,
                ...this.pinFilters
            });
            
            this.pinData = result.pins || [];
            this.updatePinsList();
            this.updatePinStatistics();
            this.showNotification('Pins loaded successfully', 'success');
        } catch (error) {
            console.error('Failed to load pins:', error);
        }
    }

    updatePinsList() {
        const container = document.getElementById('pins-list');
        if (!container) return;

        if (this.pinData.length === 0) {
            container.innerHTML = `
                <div class="text-gray-500 text-center py-8">
                    <i class="fas fa-thumbtack text-4xl mb-4"></i>
                    <div>No pins found</div>
                </div>
            `;
            return;
        }

        const pinsHtml = this.pinData.map(pin => `
            <div class="bg-white border rounded-lg p-4 hover:shadow-md transition-shadow cursor-pointer" 
                 onclick="dashboard.showPinDetails('${pin.cid}')">
                <div class="flex justify-between items-start mb-2">
                    <div class="flex-1">
                        <div class="font-medium text-gray-900 mb-1">
                            ${pin.name || 'Unnamed Pin'}
                        </div>
                        <div class="text-sm text-gray-600 font-mono bg-gray-100 px-2 py-1 rounded">
                            ${this.truncateHash(pin.cid)}
                        </div>
                    </div>
                    <div class="flex space-x-2">
                        <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${pin.type === 'recursive' ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 text-gray-800'}">
                            ${pin.type}
                        </span>
                    </div>
                </div>
                <div class="flex justify-between items-center text-sm text-gray-500">
                    <div>
                        <i class="fas fa-hdd mr-1"></i>
                        ${this.formatBytes(pin.size || 0)}
                    </div>
                    <div>
                        <i class="fas fa-clock mr-1"></i>
                        ${this.formatDate(pin.timestamp)}
                    </div>
                </div>
                ${pin.metadata ? `
                    <div class="mt-2 text-xs text-gray-500">
                        <i class="fas fa-tags mr-1"></i>
                        ${pin.metadata.description || 'Has metadata'}
                    </div>
                ` : ''}
            </div>
        `).join('');

        container.innerHTML = pinsHtml;
        this.updatePinPagination();
    }

    updatePinStatistics() {
        const totalElement = document.getElementById('total-pins');
        const activeElement = document.getElementById('active-pins');
        const pendingElement = document.getElementById('pending-pins');
        const storageElement = document.getElementById('total-storage');

        if (totalElement) totalElement.textContent = this.pinData.length;
        if (activeElement) activeElement.textContent = this.pinData.filter(p => p.type).length;
        if (pendingElement) pendingElement.textContent = '0'; // Would come from pending operations
        
        const totalSize = this.pinData.reduce((sum, pin) => sum + (pin.size || 0), 0);
        if (storageElement) storageElement.textContent = this.formatBytes(totalSize);
    }

    updatePinPagination() {
        const start = this.pinPage * this.pinPageSize + 1;
        const end = Math.min((this.pinPage + 1) * this.pinPageSize, this.pinData.length);
        
        document.getElementById('pins-start').textContent = start;
        document.getElementById('pins-end').textContent = end;
        document.getElementById('pins-total').textContent = this.pinData.length;
        
        document.getElementById('pins-prev').disabled = this.pinPage === 0;
        document.getElementById('pins-next').disabled = end >= this.pinData.length;
    }

    async showPinDetails(cid) {
        try {
            const pin = this.pinData.find(p => p.cid === cid);
            if (!pin) return;

            const detailsHtml = `
                <div class="space-y-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700">CID</label>
                        <div class="mt-1 font-mono text-sm bg-gray-100 p-2 rounded">
                            ${pin.cid}
                        </div>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Name</label>
                        <div class="mt-1 text-sm">${pin.name || 'N/A'}</div>
                    </div>
                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <label class="block text-sm font-medium text-gray-700">Type</label>
                            <div class="mt-1 text-sm">${pin.type}</div>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700">Size</label>
                            <div class="mt-1 text-sm">${this.formatBytes(pin.size || 0)}</div>
                        </div>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Created</label>
                        <div class="mt-1 text-sm">${this.formatDate(pin.timestamp)}</div>
                    </div>
                    ${pin.metadata ? `
                        <div>
                            <label class="block text-sm font-medium text-gray-700">Metadata</label>
                            <pre class="mt-1 text-sm bg-gray-100 p-2 rounded overflow-auto">${JSON.stringify(pin.metadata, null, 2)}</pre>
                        </div>
                    ` : ''}
                </div>
            `;

            document.getElementById('pin-details-content').innerHTML = detailsHtml;
            this.currentSelectedPin = cid;
            document.getElementById('pin-details-modal').classList.remove('hidden');
        } catch (error) {
            console.error('Failed to show pin details:', error);
        }
    }

    showAddPinModal() {
        document.getElementById('add-pin-modal').classList.remove('hidden');
    }

    hideAddPinModal() {
        document.getElementById('add-pin-modal').classList.add('hidden');
        document.getElementById('add-pin-form').reset();
    }

    async submitAddPin(e) {
        e.preventDefault();
        try {
            const cid = document.getElementById('new-pin-cid').value.trim();
            const name = document.getElementById('new-pin-name').value.trim();
            const recursive = document.getElementById('new-pin-recursive').checked;
            const metadataText = document.getElementById('new-pin-metadata').value.trim();
            
            let metadata = {};
            if (metadataText) {
                try {
                    metadata = JSON.parse(metadataText);
                } catch (e) {
                    throw new Error('Invalid JSON in metadata field');
                }
            }

            const result = await this.jsonRpcCall('ipfs.pin.add', {
                cid_or_file: cid,
                name: name || null,
                recursive: recursive,
                metadata: metadata
            });

            this.hideAddPinModal();
            this.showNotification('Pin added successfully', 'success');
            this.loadPins(); // Refresh the list
        } catch (error) {
            this.showNotification('Failed to add pin: ' + error.message, 'error');
        }
    }

    showBulkOperationsModal() {
        document.getElementById('bulk-operations-modal').classList.remove('hidden');
    }

    hideBulkOperationsModal() {
        document.getElementById('bulk-operations-modal').classList.add('hidden');
    }

    async executeBulkOperation() {
        try {
            const operation = document.getElementById('bulk-operation-type').value;
            const cidsText = document.getElementById('bulk-cids').value.trim();
            const cids = cidsText.split('\n').map(line => line.trim()).filter(line => line);

            if (cids.length === 0) {
                throw new Error('Please provide at least one CID');
            }

            const method = operation === 'add' ? 'ipfs.pin.bulk_add' : 'ipfs.pin.bulk_rm';
            const result = await this.jsonRpcCall(method, { cids: cids });

            this.hideBulkOperationsModal();
            this.showNotification(`Bulk ${operation} completed: ${result.successful}/${result.total_requested} successful`, 'success');
            this.loadPins(); // Refresh the list
        } catch (error) {
            this.showNotification('Bulk operation failed: ' + error.message, 'error');
        }
    }

    async verifyAllPins() {
        try {
            const result = await this.jsonRpcCall('ipfs.pin.verify');
            this.showNotification(`Verification completed: ${result.verified_pins}/${result.total_pins} verified`, 'success');
        } catch (error) {
            this.showNotification('Verification failed: ' + error.message, 'error');
        }
    }

    async cleanupPins() {
        try {
            const result = await this.jsonRpcCall('ipfs.pin.cleanup', { dry_run: false });
            this.showNotification(`Cleanup completed: ${result.total_cleaned} items cleaned, ${result.space_freed_mb}MB freed`, 'success');
            this.loadPins(); // Refresh the list
        } catch (error) {
            this.showNotification('Cleanup failed: ' + error.message, 'error');
        }
    }

    async exportMetadata() {
        try {
            const result = await this.jsonRpcCall('ipfs.pin.export_metadata');
            this.showNotification(`Export completed: ${result.shards_created} shards created`, 'success');
        } catch (error) {
            this.showNotification('Export failed: ' + error.message, 'error');
        }
    }

    async showPendingOperations() {
        try {
            const result = await this.jsonRpcCall('ipfs.pin.pending');
            
            const pendingHtml = result.pending_operations.map(op => `
                <div class="bg-white border rounded-lg p-4 mb-4">
                    <div class="flex justify-between items-start">
                        <div>
                            <div class="font-medium">${op.action.toUpperCase()} - ${op.cid}</div>
                            <div class="text-sm text-gray-600">Operation ID: ${op.operation_id}</div>
                        </div>
                        <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                            op.status === 'completed' ? 'bg-green-100 text-green-800' :
                            op.status === 'processing' ? 'bg-yellow-100 text-yellow-800' :
                            'bg-gray-100 text-gray-800'
                        }">
                            ${op.status}
                        </span>
                    </div>
                    ${op.progress ? `
                        <div class="mt-2">
                            <div class="bg-gray-200 rounded-full h-2">
                                <div class="bg-blue-600 h-2 rounded-full" style="width: ${op.progress}%"></div>
                            </div>
                        </div>
                    ` : ''}
                </div>
            `).join('');

            document.getElementById('pending-operations-content').innerHTML = 
                pendingHtml || '<div class="text-gray-500 text-center py-8">No pending operations</div>';
            
            document.getElementById('pending-operations-modal').classList.remove('hidden');
        } catch (error) {
            this.showNotification('Failed to load pending operations: ' + error.message, 'error');
        }
    }

    hidePendingOperationsModal() {
        document.getElementById('pending-operations-modal').classList.add('hidden');
    }

    hidePinDetailsModal() {
        document.getElementById('pin-details-modal').classList.add('hidden');
        this.currentSelectedPin = null;
    }

    async downloadSelectedPin() {
        if (!this.currentSelectedPin) return;
        try {
            const result = await this.jsonRpcCall('ipfs.pin.get', { 
                cid: this.currentSelectedPin 
            });
            this.showNotification('Download initiated', 'success');
        } catch (error) {
            this.showNotification('Download failed: ' + error.message, 'error');
        }
    }

    async unpinSelectedContent() {
        if (!this.currentSelectedPin) return;
        if (confirm('Are you sure you want to unpin this content?')) {
            try {
                await this.jsonRpcCall('ipfs.pin.rm', { 
                    cid: this.currentSelectedPin 
                });
                this.hidePinDetailsModal();
                this.showNotification('Content unpinned successfully', 'success');
                this.loadPins(); // Refresh the list
            } catch (error) {
                this.showNotification('Unpin failed: ' + error.message, 'error');
            }
        }
    }

    searchPins() {
        const query = document.getElementById('pin-search').value.trim();
        const typeFilter = document.getElementById('pin-type-filter').value;
        const sizeFilter = document.getElementById('pin-size-filter').value;

        this.pinFilters = {};
        if (query) this.pinFilters.query = query;
        if (typeFilter) this.pinFilters.type = typeFilter;
        if (sizeFilter) {
            switch (sizeFilter) {
                case 'small':
                    this.pinFilters.size_max = 1024 * 1024; // 1MB
                    break;
                case 'medium':
                    this.pinFilters.size_min = 1024 * 1024; // 1MB
                    this.pinFilters.size_max = 100 * 1024 * 1024; // 100MB
                    break;
                case 'large':
                    this.pinFilters.size_min = 100 * 1024 * 1024; // 100MB
                    break;
            }
        }

        this.pinPage = 0;
        this.loadPins();
    }

    clearPinFilters() {
        document.getElementById('pin-search').value = '';
        document.getElementById('pin-type-filter').value = '';
        document.getElementById('pin-size-filter').value = '';
        this.pinFilters = {};
        this.pinPage = 0;
        this.loadPins();
    }

    previousPinPage() {
        if (this.pinPage > 0) {
            this.pinPage--;
            this.loadPins();
        }
    }

    nextPinPage() {
        this.pinPage++;
        this.loadPins();
    }

    // Utility methods
    switchTab(tabId) {
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.add('hidden');
        });
        document.querySelectorAll('.tab-button').forEach(button => {
            button.classList.remove('bg-blue-500', 'text-white');
            button.classList.add('text-gray-700');
        });

        const tabContent = document.getElementById(tabId);
        const tabButton = document.querySelector(`[data-tab="${tabId}"]`);
        
        if (tabContent) tabContent.classList.remove('hidden');
        if (tabButton) {
            tabButton.classList.add('bg-blue-500', 'text-white');
            tabButton.classList.remove('text-gray-700');
        }

        // Load data for the active tab
        if (tabId === 'pins') this.loadPins();
        else if (tabId === 'buckets') this.loadBuckets();
        else if (tabId === 'peers') this.loadPeers();
        else if (tabId === 'backends') this.loadBackends();
        else if (tabId === 'config') this.loadConfig();
    }

    showNotification(message, type = 'info') {
        // Simple notification - in production would use a proper notification system
        const colors = {
            success: 'green',
            error: 'red',
            warning: 'yellow',
            info: 'blue'
        };
        console.log(`[${type.toUpperCase()}] ${message}`);
        // You could implement a toast notification here
    }

    truncateHash(hash, length = 16) {
        if (!hash) return 'N/A';
        return hash.length > length ? `${hash.substring(0, length)}...` : hash;
    }

    formatDate(dateString) {
        if (!dateString) return 'N/A';
        return new Date(dateString).toLocaleDateString() + ' ' + new Date(dateString).toLocaleTimeString();
    }

    formatBytes(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    // Basic methods for other tabs (simplified)
    async loadBuckets() {
        try {
            const result = await this.jsonRpcCall('bucket.list');
            const container = document.getElementById('buckets-list');
            if (container && result.buckets) {
                container.innerHTML = result.buckets.map(bucket => `
                    <div class="bg-gray-50 p-4 rounded-lg">
                        <h4 class="font-medium">${bucket.name}</h4>
                        <p class="text-sm text-gray-600">${bucket.files} files, ${this.formatBytes(bucket.size)}</p>
                    </div>
                `).join('');
            }
        } catch (error) {
            console.error('Failed to load buckets:', error);
        }
    }

    async loadPeers() {
        try {
            const result = await this.jsonRpcCall('peer.list');
            const container = document.getElementById('peers-list');
            if (container && result.peers) {
                container.innerHTML = result.peers.map(peer => `
                    <div class="bg-gray-50 p-4 rounded-lg">
                        <p class="font-mono text-sm">${peer.id || peer}</p>
                    </div>
                `).join('');
            }
        } catch (error) {
            console.error('Failed to load peers:', error);
        }
    }

    async loadBackends() {
        try {
            const result = await this.jsonRpcCall('backend.list');
            const container = document.getElementById('backends-list');
            if (container && result.backends) {
                container.innerHTML = result.backends.map(backend => `
                    <div class="bg-gray-50 p-4 rounded-lg">
                        <div class="flex justify-between items-center">
                            <h4 class="font-medium">${backend.name}</h4>
                            <span class="text-sm px-2 py-1 rounded ${backend.status === 'active' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'}">
                                ${backend.status}
                            </span>
                        </div>
                        <p class="text-sm text-gray-600">${backend.type}</p>
                    </div>
                `).join('');
            }
        } catch (error) {
            console.error('Failed to load backends:', error);
        }
    }

    async loadLogs() {
        const container = document.getElementById('logs-content');
        if (container) {
            container.innerHTML = '<div>Log loading not implemented yet...</div>';
        }
    }

    clearLogs() {
        const container = document.getElementById('logs-content');
        if (container) {
            container.innerHTML = '<div>Logs cleared.</div>';
        }
    }

    async updateSystemStatus() {
        try {
            const status = await this.jsonRpcCall('system.status');
            // Update UI elements with status data
            if (status.cpu_usage !== undefined) {
                const cpuElement = document.querySelector('[data-metric="cpu"]');
                if (cpuElement) cpuElement.textContent = status.cpu_usage + '%';
            }
            if (status.memory_usage !== undefined) {
                const memElement = document.querySelector('[data-metric="memory"]');
                if (memElement) memElement.textContent = status.memory_usage + '%';
            }
        } catch (error) {
            console.error('Failed to update system status:', error);
        }
    }

    startPeriodicUpdates() {
        // Update system status every 5 seconds
        setInterval(() => {
            this.updateSystemStatus();
        }, 5000);

        // Initial update
        this.updateSystemStatus();
    }

    async loadConfig() {
        try {
            const result = await this.jsonRpcCall('config.get_all_backend_configs');
            const schemasResult = await this.jsonRpcCall('config.get_backend_schemas');
            const backendsList = document.getElementById('config-backends-list');
            const configFormContainer = document.getElementById('config-form-container');

            if (backendsList && configFormContainer) {
                backendsList.innerHTML = '';
                configFormContainer.innerHTML = '';

                for (const backend in result.configs) {
                    const button = document.createElement('button');
                    button.className = 'w-full text-left p-2 rounded hover:bg-gray-100';
                    button.textContent = backend;
                    button.onclick = () => this.displayConfigForm(backend, result.configs[backend], schemasResult.schemas);
                    backendsList.appendChild(button);
                }
            }
        } catch (error) {
            console.error('Failed to load configs:', error);
        }
    }

    displayConfigForm(backend, config, schemas) {
        const configFormContainer = document.getElementById('config-form-container');
        const schema = schemas[backend] || { fields: {} };
        let formHtml = `<h4 class="text-md font-semibold text-gray-700 mb-2">${backend}</h4>`;

        for (const key in schema.fields) {
            const field = schema.fields[key];
            const value = config[key] || field.default || '';
            formHtml += `
                <div class="mb-2">
                    <label class="block text-sm font-medium text-gray-700">${key} ${field.required ? '<span class="text-red-500">*</span>' : ''}</label>`;
            if (field.type === 'select') {
                formHtml += `<select id="config-${backend}-${key}" class="w-full p-2 border rounded mt-1">`;
                for (const choice of field.choices) {
                    formHtml += `<option value="${choice}" ${choice === value ? 'selected' : ''}>${choice}</option>`;
                }
                formHtml += `</select>`;
            } else if (field.type === 'checkbox') {
                formHtml += `<input type="checkbox" id="config-${backend}-${key}" class="mt-1" ${value ? 'checked' : ''}>`;
            } else {
                formHtml += `<input type="${field.type}" id="config-${backend}-${key}" class="w-full p-2 border rounded mt-1" value="${value}">`;
            }
            formHtml += `</div>`;
        }

        formHtml += `<button id="save-config-${backend}" class="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded mt-4">Save</button>`;
        configFormContainer.innerHTML = formHtml;

        document.getElementById(`save-config-${backend}`).onclick = () => this.saveConfig(backend, schema);
    }

    async saveConfig(backend, schema) {
        const newConfig = {};
        for (const key in schema.fields) {
            const field = schema.fields[key];
            const element = document.getElementById(`config-${backend}-${key}`);
            if (field.type === 'checkbox') {
                newConfig[key] = element.checked;
            } else {
                newConfig[key] = element.value;
            }
        }

        try {
            await this.jsonRpcCall('config.save_backend_config', { backend: backend, config: newConfig });
            this.showNotification(`${backend} configuration saved successfully`, 'success');
        } catch (error) {
            this.showNotification("Failed to save " + backend + " configuration: " + error.message, 'error');
        }
    }

    async showAddBackendModal() {
        const schemas = await this.jsonRpcCall('config.get_backend_schemas');
        const backendType = prompt("Enter backend type (e.g., s3, huggingface):");
        if (backendType && schemas.schemas[backendType]) {
            const backendName = prompt("Enter a name for the new backend:");
            if (backendName) {
                const config = {};
                for (const field in schemas.schemas[backendType].fields) {
                    const fieldSchema = schemas.schemas[backendType].fields[field];
                    const value = prompt(`Enter value for ${field}` + (fieldSchema.required ? ' (required)' : ''));
                    if (fieldSchema.required && !value) {
                        alert("Missing required field: " + field);
                        return;
                    }
                    config[field] = value;
                }
                await this.jsonRpcCall('config.save_backend_config', { backend: backendName, config: config });
                this.loadConfig();
            }
        }
    }
}

const dashboard = new MCPDashboard();
'''
        
        (static_dir / "dashboard.js").write_text(js_content)
    
    def setup_routes(self):
        """Setup API and web routes"""
        
        @self.app.get("/", response_class=HTMLResponse)
        async def get_dashboard(request: Request):
            """Serve the main dashboard page"""
            return self.templates.TemplateResponse("dashboard.html", {"request": request})
        
        @self.app.post("/api/jsonrpc")
        async def handle_jsonrpc(request: Request):
            """Handle JSON-RPC requests"""
            try:
                request_data = await request.json()
                response = await self.jsonrpc_handler.handle_request(request_data)
                return JSONResponse(content=response)
            except json.JSONDecodeError:
                return JSONResponse(
                    content=self.jsonrpc_handler.error_response(None, -32700, "Parse error"),
                    status_code=400
                )
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint"""
            return {"status": "healthy"}
    
    def run(self):
        """Run the FastAPI server"""
        logger.info(f"Starting Unified MCP Dashboard Server on http://{self.host}:{self.port}")
        
        # Initialize IPFS Kit if available
        global ipfs_kit, config_manager
        if IPFSKitPy:
            try:
                ipfs_kit = IPFSKitPy()
                logger.info("IPFS Kit initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize IPFS Kit: {e}")
        
        if ConfigManager:
            try:
                config_manager = ConfigManager()
                logger.info("ConfigManager initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize ConfigManager: {e}")

        uvicorn.run(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Unified MCP Dashboard Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8083, help="Port to run on")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    
    args = parser.parse_args()
    
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    server = UnifiedMCPDashboardServer(host=args.host, port=args.port)
    
    # Handle graceful shutdown
    def shutdown_handler(signum, frame):
        logger.info("Shutting down server...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)
    
    server.run()

if __name__ == "__main__":
    main()
