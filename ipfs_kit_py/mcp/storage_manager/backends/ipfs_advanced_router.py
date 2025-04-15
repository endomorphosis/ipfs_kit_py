"""
Advanced IPFS Operations Router

This module provides comprehensive IPFS functionality beyond basic operations:
- DHT operations for enhanced network participation
- Object and DAG manipulation endpoints
- Advanced IPNS functionality with key management
- Extended filesystem operations

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).
"""

import os
import json
import logging
import time
from typing import Dict, Any, List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, Body, Path, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from ipfs_kit_py.mcp.auth.models import User
from ipfs_kit_py.mcp.auth.router import get_current_user
from ipfs_kit_py.mcp.rbac import require_permission, Permission

# Configure logging
logger = logging.getLogger(__name__)


# --- Pydantic Models for Request/Response ---

class DHTProvideRequest(BaseModel):
    """Request to provide content to the DHT."""
    cid: str = Field(..., description="CID to provide")
    recursive: bool = Field(False, description="Whether to provide recursively")
    timeout: Optional[int] = Field(None, description="Timeout in seconds")


class DHTFindPeerRequest(BaseModel):
    """Request to find a peer in the DHT."""
    peer_id: str = Field(..., description="Peer ID to find")
    timeout: Optional[int] = Field(None, description="Timeout in seconds")


class DHTFindProvsRequest(BaseModel):
    """Request to find providers for a CID in the DHT."""
    cid: str = Field(..., description="CID to find providers for")
    num_providers: int = Field(20, description="Maximum number of providers to find")
    timeout: Optional[int] = Field(None, description="Timeout in seconds")


class ObjectPatchRequest(BaseModel):
    """Request to patch an IPFS object."""
    cid: str = Field(..., description="Base CID to patch")
    operation: str = Field(..., description="Operation type: add-link, rm-link, set-data, append-data")
    name: Optional[str] = Field(None, description="Link name (for add-link and rm-link)")
    target: Optional[str] = Field(None, description="Target CID (for add-link)")
    data: Optional[str] = Field(None, description="Data (for set-data and append-data)")


class DAGPutRequest(BaseModel):
    """Request to put a DAG node."""
    object_data: Dict[str, Any] = Field(..., description="DAG node data (JSON)")
    pin: bool = Field(True, description="Whether to pin the DAG node")
    hash_algorithm: Optional[str] = Field("sha2-256", description="Hash algorithm to use")
    cid_version: Optional[int] = Field(1, description="CID version to use")
    format: Optional[str] = Field("dag-cbor", description="Format to use (dag-cbor or dag-json)")


class NamePublishRequest(BaseModel):
    """Request to publish an IPNS name."""
    cid: str = Field(..., description="CID to publish")
    key: Optional[str] = Field("self", description="Key to use")
    lifetime: Optional[str] = Field("24h", description="Record lifetime")
    ttl: Optional[str] = Field("1m", description="Record TTL")
    allow_offline: bool = Field(False, description="Whether to allow publishing while offline")


class KeygenRequest(BaseModel):
    """Request to generate a new key."""
    name: str = Field(..., description="Name for the new key")
    type: str = Field("rsa", description="Key type (rsa, ed25519, secp256k1)")
    size: Optional[int] = Field(2048, description="Key size (for RSA)")


# --- Helper Functions ---

def _get_ipfs_backend(backend_manager):
    """Get the IPFS backend from the backend manager."""
    ipfs_backend = backend_manager.get_backend("ipfs")
    if not ipfs_backend:
        raise HTTPException(status_code=404, detail="IPFS backend not found")
    return ipfs_backend


# --- Router Configuration ---

def create_advanced_ipfs_router(app, backend_manager):
    """
    Create and configure the advanced IPFS router.
    
    Args:
        app: FastAPI application
        backend_manager: Storage backend manager
    """
    # --- DHT Operations ---
    
    @app.post("/api/v0/ipfs/dht/provide")
    async def ipfs_dht_provide(
        request: DHTProvideRequest,
        current_user: User = Depends(get_current_user)
    ):
        """
        Announce to the network that you are providing a content.
        
        This makes the content discoverable by other nodes via DHT.
        """
        try:
            ipfs_backend = _get_ipfs_backend(backend_manager)
            
            # Convert to backend-compatible command
            result = await ipfs_backend.ipfs.ipfs_dht_provide(
                request.cid, 
                recursive=request.recursive,
                timeout=request.timeout
            )
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Failed to provide CID to DHT")
                )
            
            return result
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/v0/ipfs/dht/findpeer")
    async def ipfs_dht_find_peer(
        request: DHTFindPeerRequest,
        current_user: User = Depends(get_current_user)
    ):
        """
        Find a specific peer in the DHT network.
        
        Returns the peer's addresses if found.
        """
        try:
            ipfs_backend = _get_ipfs_backend(backend_manager)
            
            result = await ipfs_backend.ipfs.ipfs_dht_findpeer(
                request.peer_id,
                timeout=request.timeout
            )
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Failed to find peer in DHT")
                )
            
            return result
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/v0/ipfs/dht/findprovs")
    async def ipfs_dht_find_providers(
        request: DHTFindProvsRequest,
        current_user: User = Depends(get_current_user)
    ):
        """
        Find providers for a specific CID in the DHT network.
        
        Returns the peers that are providing the content.
        """
        try:
            ipfs_backend = _get_ipfs_backend(backend_manager)
            
            result = await ipfs_backend.ipfs.ipfs_dht_findprovs(
                request.cid,
                num_providers=request.num_providers,
                timeout=request.timeout
            )
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Failed to find providers in DHT")
                )
            
            return result
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/v0/ipfs/dht/query/{peer_id}")
    async def ipfs_dht_query(
        peer_id: str,
        current_user: User = Depends(get_current_user)
    ):
        """
        Find the closest peers to a given peer ID in the DHT.
        
        This is useful for testing DHT connectivity and debugging.
        """
        try:
            ipfs_backend = _get_ipfs_backend(backend_manager)
            
            result = await ipfs_backend.ipfs.ipfs_dht_query(peer_id)
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Failed to query DHT")
                )
            
            return result
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))
    
    # --- Object Operations ---
    
    @app.get("/api/v0/ipfs/object/get/{cid}")
    async def ipfs_object_get(
        cid: str,
        current_user: User = Depends(get_current_user)
    ):
        """
        Get the raw bytes of an IPFS object.
        """
        try:
            ipfs_backend = _get_ipfs_backend(backend_manager)
            
            result = await ipfs_backend.ipfs.ipfs_object_get(cid)
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Failed to get object")
                )
            
            return result
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/v0/ipfs/object/stat/{cid}")
    async def ipfs_object_stat(
        cid: str,
        current_user: User = Depends(get_current_user)
    ):
        """
        Get stats for an IPFS object.
        
        Returns information about the object such as its size.
        """
        try:
            ipfs_backend = _get_ipfs_backend(backend_manager)
            
            result = await ipfs_backend.ipfs.ipfs_object_stat(cid)
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Failed to get object stats")
                )
            
            return result
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/v0/ipfs/object/put")
    async def ipfs_object_put(
        data: UploadFile = File(...),
        input_enc: str = Form("json"),
        current_user: User = Depends(get_current_user)
    ):
        """
        Create a new IPFS object from data.
        
        Supports JSON and protobuf input encoding.
        """
        try:
            ipfs_backend = _get_ipfs_backend(backend_manager)
            
            # Read file content
            content = await data.read()
            
            result = await ipfs_backend.ipfs.ipfs_object_put(content, input_enc=input_enc)
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Failed to put object")
                )
            
            return result
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/v0/ipfs/object/patch")
    async def ipfs_object_patch(
        request: ObjectPatchRequest,
        current_user: User = Depends(get_current_user)
    ):
        """
        Patch an IPFS object.
        
        Supports operations:
        - add-link: Add a link to another object
        - rm-link: Remove a link
        - set-data: Set the object's data
        - append-data: Append to the object's data
        """
        try:
            ipfs_backend = _get_ipfs_backend(backend_manager)
            
            if request.operation == "add-link":
                if not request.name or not request.target:
                    raise HTTPException(
                        status_code=400,
                        detail="Name and target are required for add-link operation"
                    )
                result = await ipfs_backend.ipfs.ipfs_object_patch_add_link(
                    request.cid, request.name, request.target
                )
            elif request.operation == "rm-link":
                if not request.name:
                    raise HTTPException(
                        status_code=400,
                        detail="Name is required for rm-link operation"
                    )
                result = await ipfs_backend.ipfs.ipfs_object_patch_rm_link(
                    request.cid, request.name
                )
            elif request.operation == "set-data":
                if request.data is None:
                    raise HTTPException(
                        status_code=400,
                        detail="Data is required for set-data operation"
                    )
                result = await ipfs_backend.ipfs.ipfs_object_patch_set_data(
                    request.cid, request.data.encode()
                )
            elif request.operation == "append-data":
                if request.data is None:
                    raise HTTPException(
                        status_code=400,
                        detail="Data is required for append-data operation"
                    )
                result = await ipfs_backend.ipfs.ipfs_object_patch_append_data(
                    request.cid, request.data.encode()
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported operation: {request.operation}"
                )
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", f"Failed to patch object with {request.operation}")
                )
            
            return result
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/v0/ipfs/object/new")
    async def ipfs_object_new(
        template: str = Form("unixfs-dir"),
        current_user: User = Depends(get_current_user)
    ):
        """
        Create a new IPFS object from a template.
        
        Supports templates:
        - unixfs-dir: Empty unixfs directory
        """
        try:
            ipfs_backend = _get_ipfs_backend(backend_manager)
            
            result = await ipfs_backend.ipfs.ipfs_object_new(template)
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Failed to create new object")
                )
            
            return result
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/v0/ipfs/object/links/{cid}")
    async def ipfs_object_links(
        cid: str,
        current_user: User = Depends(get_current_user)
    ):
        """
        Get links in an IPFS object.
        """
        try:
            ipfs_backend = _get_ipfs_backend(backend_manager)
            
            result = await ipfs_backend.ipfs.ipfs_object_links(cid)
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Failed to get object links")
                )
            
            return result
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))
    
    # --- DAG Operations ---
    
    @app.post("/api/v0/ipfs/dag/put")
    async def ipfs_dag_put(
        request: DAGPutRequest,
        current_user: User = Depends(get_current_user)
    ):
        """
        Add a DAG node to IPFS.
        
        Allows storing complex data structures in IPFS (JSON, CBOR).
        """
        try:
            ipfs_backend = _get_ipfs_backend(backend_manager)
            
            # Convert object to JSON string
            object_json = json.dumps(request.object_data)
            
            result = await ipfs_backend.ipfs.ipfs_dag_put(
                object_json,
                pin=request.pin,
                hash_algorithm=request.hash_algorithm,
                cid_version=request.cid_version,
                format=request.format
            )
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Failed to put DAG node")
                )
            
            return result
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/v0/ipfs/dag/get/{cid}")
    async def ipfs_dag_get(
        cid: str,
        path: Optional[str] = Query(None, description="Sub-path within the DAG node"),
        current_user: User = Depends(get_current_user)
    ):
        """
        Get a DAG node from IPFS.
        
        Optionally specify a path to get a nested field.
        """
        try:
            ipfs_backend = _get_ipfs_backend(backend_manager)
            
            result = await ipfs_backend.ipfs.ipfs_dag_get(cid, path=path)
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Failed to get DAG node")
                )
            
            return result
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/v0/ipfs/dag/resolve/{cid}")
    async def ipfs_dag_resolve(
        cid: str,
        path: Optional[str] = Query(None, description="Path to resolve"),
        current_user: User = Depends(get_current_user)
    ):
        """
        Resolve a path in a DAG node.
        
        Returns the CID the path resolves to.
        """
        try:
            ipfs_backend = _get_ipfs_backend(backend_manager)
            
            result = await ipfs_backend.ipfs.ipfs_dag_resolve(cid, path=path)
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Failed to resolve DAG path")
                )
            
            return result
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))
    
    # --- IPNS Operations ---
    
    @app.post("/api/v0/ipfs/name/publish")
    async def ipfs_name_publish(
        request: NamePublishRequest,
        current_user: User = Depends(get_current_user)
    ):
        """
        Publish an IPNS name.
        
        Maps a name to a content identifier (CID).
        """
        try:
            ipfs_backend = _get_ipfs_backend(backend_manager)
            
            result = await ipfs_backend.ipfs.ipfs_name_publish(
                request.cid,
                key=request.key,
                lifetime=request.lifetime,
                ttl=request.ttl,
                allow_offline=request.allow_offline
            )
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Failed to publish IPNS name")
                )
            
            return result
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/v0/ipfs/name/resolve/{name}")
    async def ipfs_name_resolve(
        name: str,
        recursive: bool = Query(True, description="Resolve until the result is not an IPNS name"),
        nocache: bool = Query(False, description="Do not use cached entries"),
        current_user: User = Depends(get_current_user)
    ):
        """
        Resolve an IPNS name.
        
        Returns the content identifier (CID) the name points to.
        """
        try:
            ipfs_backend = _get_ipfs_backend(backend_manager)
            
            result = await ipfs_backend.ipfs.ipfs_name_resolve(
                name,
                recursive=recursive,
                nocache=nocache
            )
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Failed to resolve IPNS name")
                )
            
            return result
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/v0/ipfs/name/pubsub/state")
    async def ipfs_name_pubsub_state(
        current_user: User = Depends(get_current_user)
    ):
        """
        Query the state of IPNS pubsub.
        """
        try:
            ipfs_backend = _get_ipfs_backend(backend_manager)
            
            result = await ipfs_backend.ipfs.ipfs_name_pubsub_state()
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Failed to get IPNS pubsub state")
                )
            
            return result
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/v0/ipfs/name/pubsub/{action}")
    async def ipfs_name_pubsub_action(
        action: str = Path(..., description="Action to perform (subs or cancel)"),
        name: Optional[str] = Query(None, description="IPNS name"),
        current_user: User = Depends(get_current_user)
    ):
        """
        Subscribe to or cancel a subscription to an IPNS pubsub topic.
        """
        try:
            ipfs_backend = _get_ipfs_backend(backend_manager)
            
            if action == "subs":
                result = await ipfs_backend.ipfs.ipfs_name_pubsub_subs()
            elif action == "cancel":
                if not name:
                    raise HTTPException(
                        status_code=400,
                        detail="Name is required for cancel action"
                    )
                result = await ipfs_backend.ipfs.ipfs_name_pubsub_cancel(name)
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported action: {action}"
                )
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", f"Failed to perform {action} on IPNS pubsub")
                )
            
            return result
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))
    
    # --- Key Management ---
    
    @app.post("/api/v0/ipfs/key/gen")
    async def ipfs_key_gen(
        request: KeygenRequest,
        current_user: User = Depends(get_current_user)
    ):
        """
        Generate a new key.
        
        These keys can be used for IPNS publishing.
        """
        try:
            ipfs_backend = _get_ipfs_backend(backend_manager)
            
            result = await ipfs_backend.ipfs.ipfs_key_gen(
                request.name,
                type=request.type,
                size=request.size
            )
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Failed to generate key")
                )
            
            return result
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/v0/ipfs/key/list")
    async def ipfs_key_list(
        current_user: User = Depends(get_current_user)
    ):
        """
        List all keys.
        """
        try:
            ipfs_backend = _get_ipfs_backend(backend_manager)
            
            result = await ipfs_backend.ipfs.ipfs_key_list()
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Failed to list keys")
                )
            
            return result
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/v0/ipfs/key/rm/{name}")
    async def ipfs_key_rm(
        name: str,
        current_user: User = Depends(get_current_user)
    ):
        """
        Remove a key.
        """
        try:
            ipfs_backend = _get_ipfs_backend(backend_manager)
            
            result = await ipfs_backend.ipfs.ipfs_key_rm(name)
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Failed to remove key")
                )
            
            return result
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/v0/ipfs/key/rename")
    async def ipfs_key_rename(
        old_name: str = Form(..., description="Old key name"),
        new_name: str = Form(..., description="New key name"),
        force: bool = Form(False, description="Force rename if new name already exists"),
        current_user: User = Depends(get_current_user)
    ):
        """
        Rename a key.
        """
        try:
            ipfs_backend = _get_ipfs_backend(backend_manager)
            
            result = await ipfs_backend.ipfs.ipfs_key_rename(
                old_name,
                new_name,
                force=force
            )
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Failed to rename key")
                )
            
            return result
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/v0/ipfs/key/import")
    async def ipfs_key_import(
        name: str = Form(..., description="Name for the imported key"),
        key_file: UploadFile = File(..., description="Key file to import"),
        current_user: User = Depends(get_current_user)
    ):
        """
        Import a key.
        """
        try:
            ipfs_backend = _get_ipfs_backend(backend_manager)
            
            # Read key data
            key_data = await key_file.read()
            
            result = await ipfs_backend.ipfs.ipfs_key_import(
                name,
                key_data
            )
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Failed to import key")
                )
            
            return result
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/v0/ipfs/key/export/{name}")
    async def ipfs_key_export(
        name: str,
        current_user: User = Depends(get_current_user)
    ):
        """
        Export a key.
        """
        try:
            ipfs_backend = _get_ipfs_backend(backend_manager)
            
            result = await ipfs_backend.ipfs.ipfs_key_export(name)
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Failed to export key")
                )
            
            # If key data is binary, return as file download
            if "key_data" in result and isinstance(result["key_data"], bytes):
                from fastapi.responses import Response
                return Response(
                    content=result["key_data"],
                    media_type="application/octet-stream",
                    headers={"Content-Disposition": f"attachment; filename={name}.key"}
                )
            
            return result
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))
    
    # --- Additional File Operations ---
    
    @app.get("/api/v0/ipfs/ls/{cid}")
    async def ipfs_ls(
        cid: str,
        current_user: User = Depends(get_current_user)
    ):
        """
        List directory contents for Unix filesystem objects.
        """
        try:
            ipfs_backend = _get_ipfs_backend(backend_manager)
            
            result = await ipfs_backend.ipfs.ipfs_ls(cid)
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Failed to list directory")
                )
            
            return result
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/v0/ipfs/files/stat/{path}")
    async def ipfs_files_stat(
        path: str = Path(..., description="Path in the MFS"),
        current_user: User = Depends(get_current_user)
    ):
        """
        Get stats for a file or directory in the MFS (Mutable File System).
        """
        try:
            ipfs_backend = _get_ipfs_backend(backend_manager)
            
            result = await ipfs_backend.ipfs.ipfs_files_stat(path)
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Failed to get file stats")
                )
            
            return result
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/v0/ipfs/files/mkdir")
    async def ipfs_files_mkdir(
        path: str = Form(..., description="Path to create"),
        parents: bool = Form(False, description="Create parent directories if they don't exist"),
        current_user: User = Depends(get_current_user)
    ):
        """
        Create a directory in the MFS (Mutable File System).
        """
        try:
            ipfs_backend = _get_ipfs_backend(backend_manager)
            
            result = await ipfs_backend.ipfs.ipfs_files_mkdir(
                path,
                parents=parents
            )
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Failed to create directory")
                )
            
            return result
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/v0/ipfs/files/write")
    async def ipfs_files_write(
        path: str = Form(..., description="Path to write to"),
        file: UploadFile = File(..., description="File to write"),
        offset: int = Form(0, description="Offset to write at"),
        create: bool = Form(True, description="Create file if it doesn't exist"),
        truncate: bool = Form(True, description="Truncate file before writing"),
        parents: bool = Form(False, description="Create parent directories if they don't exist"),
        current_user: User = Depends(get_current_user)
    ):
        """
        Write to a file in the MFS (Mutable File System).
        """
        try:
            ipfs_backend = _get_ipfs_backend(backend_manager)
            
            # Read file data
            file_data = await file.read()
            
            result = await ipfs_backend.ipfs.ipfs_files_write(
                path,
                file_data,
                offset=offset,
                create=create,
                truncate=truncate,
                parents=parents
            )
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Failed to write file")
                )
            
            return result
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/v0/ipfs/files/read/{path}")
    async def ipfs_files_read(
        path: str,
        offset: int = Query(0, description="Offset to read from"),
        count: Optional[int] = Query(None, description="Maximum bytes to read"),
        current_user: User = Depends(get_current_user)
    ):
        """
        Read a file from the MFS (Mutable File System).
        """
        try:
            ipfs_backend = _get_ipfs_backend(backend_manager)
            
            result = await ipfs_backend.ipfs.ipfs_files_read(
                path,
                offset=offset,
                count=count
            )
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Failed to read file")
                )
            
            # If data is binary, return as file download
            if "data" in result and isinstance(result["data"], bytes):
                # Get filename from path
                filename = os.path.basename(path)
                return StreamingResponse(
                    iter([result["data"]]),
                    media_type="application/octet-stream",
                    headers={"Content-Disposition": f"attachment; filename={filename}"}
                )
            
            return result
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/v0/ipfs/files/rm")
    async def ipfs_files_rm(
        path: str = Form(..., description="Path to remove"),
        recursive: bool = Form(False, description="Recursively remove directories"),
        current_user: User = Depends(get_current_user)
    ):
        """
        Remove a file or directory from the MFS (Mutable File System).
        """
        try:
            ipfs_backend = _get_ipfs_backend(backend_manager)
            
            result = await ipfs_backend.ipfs.ipfs_files_rm(
                path,
                recursive=recursive
            )
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Failed to remove file")
                )
            
            return result
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/v0/ipfs/files/cp")
    async def ipfs_files_cp(
        source: str = Form(..., description="Source path"),
        dest: str = Form(..., description="Destination path"),
        parents: bool = Form(False, description="Create parent directories if they don't exist"),
        current_user: User = Depends(get_current_user)
    ):
        """
        Copy files in the MFS (Mutable File System).
        """
        try:
            ipfs_backend = _get_ipfs_backend(backend_manager)
            
            result = await ipfs_backend.ipfs.ipfs_files_cp(
                source,
                dest,
                parents=parents
            )
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Failed to copy file")
                )
            
            return result
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/v0/ipfs/files/mv")
    async def ipfs_files_mv(
        source: str = Form(..., description="Source path"),
        dest: str = Form(..., description="Destination path"),
        current_user: User = Depends(get_current_user)
    ):
        """
        Move files in the MFS (Mutable File System).
        """
        try:
            ipfs_backend = _get_ipfs_backend(backend_manager)
            
            result = await ipfs_backend.ipfs.ipfs_files_mv(
                source,
                dest
            )
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Failed to move file")
                )
            
            return result
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/v0/ipfs/files/ls")
    async def ipfs_files_ls(
        path: str = Query("/", description="Path to list"),
        long: bool = Query(False, description="Use long listing format"),
        current_user: User = Depends(get_current_user)
    ):
        """
        List files in the MFS (Mutable File System).
        """
        try:
            ipfs_backend = _get_ipfs_backend(backend_manager)
            
            result = await ipfs_backend.ipfs.ipfs_files_ls(
                path,
                long=long
            )
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Failed to list files")
                )
            
            return result
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))
    
    # --- Swarm Operations ---
    
    @app.get("/api/v0/ipfs/swarm/peers")
    async def ipfs_swarm_peers(
        current_user: User = Depends(get_current_user)
    ):
        """
        List peers connected to the local node.
        """
        try:
            ipfs_backend = _get_ipfs_backend(backend_manager)
            
            result = await ipfs_backend.ipfs.ipfs_swarm_peers()
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Failed to list peers")
                )
            
            return result
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/v0/ipfs/swarm/connect")
    async def ipfs_swarm_connect(
        address: str = Form(..., description="Multiaddress to connect to"),
        current_user: User = Depends(get_current_user)
    ):
        """
        Connect to a peer.
        """
        try:
            ipfs_backend = _get_ipfs_backend(backend_manager)
            
            result = await ipfs_backend.ipfs.ipfs_swarm_connect(address)
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Failed to connect to peer")
                )
            
            return result
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/v0/ipfs/swarm/disconnect")
    async def ipfs_swarm_disconnect(
        address: str = Form(..., description="Multiaddress to disconnect from"),
        current_user: User = Depends(get_current_user)
    ):
        """
        Disconnect from a peer.
        """
        try:
            ipfs_backend = _get_ipfs_backend(backend_manager)
            
            result = await ipfs_backend.ipfs.ipfs_swarm_disconnect(address)
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Failed to disconnect from peer")
                )
            
            return result
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/v0/ipfs/swarm/addrs")
    async def ipfs_swarm_addrs(
        current_user: User = Depends(get_current_user)
    ):
        """
        List known addresses.
        
        Returns the addresses known to the local node.
        """
        try:
            ipfs_backend = _get_ipfs_backend(backend_manager)
            
            result = await ipfs_backend.ipfs.ipfs_swarm_addrs()
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Failed to list addresses")
                )
            
            return result
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/v0/ipfs/swarm/addrs/local")
    async def ipfs_swarm_addrs_local(
        current_user: User = Depends(get_current_user)
    ):
        """
        List local addresses.
        
        Returns the addresses of the local node.
        """
        try:
            ipfs_backend = _get_ipfs_backend(backend_manager)
            
            result = await ipfs_backend.ipfs.ipfs_swarm_addrs_local()
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Failed to list local addresses")
                )
            
            return result
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))
    
    # --- Diagnostic Operations ---
    
    @app.get("/api/v0/ipfs/diag/sys")
    async def ipfs_diag_sys(
        current_user: User = Depends(get_current_user)
    ):
        """
        Print system diagnostic information.
        """
        try:
            ipfs_backend = _get_ipfs_backend(backend_manager)
            
            result = await ipfs_backend.ipfs.ipfs_diag_sys()
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Failed to get system diagnostics")
                )
            
            return result
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/v0/ipfs/stats/bw")
    async def ipfs_stats_bw(
        current_user: User = Depends(get_current_user)
    ):
        """
        Get bandwidth statistics.
        """
        try:
            ipfs_backend = _get_ipfs_backend(backend_manager)
            
            result = await ipfs_backend.ipfs.ipfs_stats_bw()
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Failed to get bandwidth stats")
                )
            
            return result
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/v0/ipfs/stats/repo")
    async def ipfs_stats_repo(
        current_user: User = Depends(get_current_user)
    ):
        """
        Get repository statistics.
        """
        try:
            ipfs_backend = _get_ipfs_backend(backend_manager)
            
            result = await ipfs_backend.ipfs.ipfs_stats_repo()
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Failed to get repository stats")
                )
            
            return result
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/v0/ipfs/stats/bitswap")
    async def ipfs_stats_bitswap(
        current_user: User = Depends(get_current_user)
    ):
        """
        Get bitswap statistics.
        """
        try:
            ipfs_backend = _get_ipfs_backend(backend_manager)
            
            result = await ipfs_backend.ipfs.ipfs_stats_bitswap()
            
            if not result.get("success", False):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Failed to get bitswap stats")
                )
            
            return result
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))
    
    logger.info("Advanced IPFS operations router configured")
    return None