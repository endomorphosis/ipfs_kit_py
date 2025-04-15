#!/usr/bin/env python3
"""
Advanced IPFS Operations API router.

This module provides FastAPI routes for the advanced IPFS operations including:
- DAG (Directed Acyclic Graph) operations
- Object manipulation
- IPNS and key management
- Swarm and network management

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements.
"""

import os
import json
import base64
from typing import Any, Dict, List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Body, File, UploadFile, Form, Query, Path
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

# Import the advanced IPFS operations module
from ipfs_kit_py.mcp.extensions.ipfs_advanced import get_instance as get_ipfs_advanced

# Create API router
router = APIRouter(prefix="/api/v0/ipfs/advanced", tags=["ipfs-advanced"])

# --- Pydantic models for request/response validation ---

class StatusResponse(BaseModel):
    """Standard response model with operation status."""
    success: bool
    message: str = ""
    error: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

class DagGetRequest(BaseModel):
    """Request model for DAG get operation."""
    cid: str
    path: str = ""
    output_codec: str = "json"

class DagPutRequest(BaseModel):
    """Request model for DAG put operation."""
    data: Dict[str, Any]
    input_codec: str = "json"
    store_codec: str = "dag-cbor"
    pin: bool = False
    hash_alg: str = "sha2-256"

class DagResolveRequest(BaseModel):
    """Request model for DAG resolve operation."""
    path: str

class ObjectNewRequest(BaseModel):
    """Request model for object new operation."""
    template: str = "unixfs-dir"

class ObjectPutRequest(BaseModel):
    """Request model for object put operation."""
    data: Dict[str, Any]
    input_codec: str = "json"
    pin: bool = False

class ObjectPatchAddLinkRequest(BaseModel):
    """Request model for object patch add-link operation."""
    cid: str
    link_name: str
    link_cid: str

class ObjectPatchRmLinkRequest(BaseModel):
    """Request model for object patch rm-link operation."""
    cid: str
    link_name: str

class ObjectPatchSetDataRequest(BaseModel):
    """Request model for object patch set-data operation."""
    cid: str
    data: str

class NamePublishRequest(BaseModel):
    """Request model for name publish operation."""
    cid: str
    key: str = "self"
    lifetime: str = "24h"
    allow_offline: bool = False
    ttl: str = ""

class NameResolveRequest(BaseModel):
    """Request model for name resolve operation."""
    name: str
    recursive: bool = True
    nocache: bool = False

class KeyGenRequest(BaseModel):
    """Request model for key gen operation."""
    name: str
    type: str = "rsa"
    size: int = 2048

class KeyRenameRequest(BaseModel):
    """Request model for key rename operation."""
    old_name: str
    new_name: str

class KeyImportRequest(BaseModel):
    """Request model for key import operation."""
    name: str
    key_data: str

class SwarmConnectRequest(BaseModel):
    """Request model for swarm connect operation."""
    address: str

class BootstrapAddRequest(BaseModel):
    """Request model for bootstrap add operation."""
    address: str

# --- API Routes ---

# --- DAG Operations ---

@router.post("/dag/get", response_model=Dict[str, Any], summary="Get a DAG node from IPFS")
async def dag_get(request: DagGetRequest):
    """
    Get a DAG node from IPFS, optionally traversing a path within the node.
    
    - **cid**: The CID of the DAG node to retrieve
    - **path**: Optional path within the DAG node (e.g., "/a/b/c")
    - **output_codec**: Format to output the node in (json, raw, etc.)
    """
    ipfs_advanced = get_ipfs_advanced()
    result = ipfs_advanced.dag_get(
        cid=request.cid,
        path=request.path,
        output_codec=request.output_codec
    )
    
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to get DAG node"))
    
    return result

@router.post("/dag/put", response_model=Dict[str, Any], summary="Put a DAG node into IPFS")
async def dag_put(request: DagPutRequest):
    """
    Put a DAG node into IPFS.
    
    - **data**: The data to store in the DAG node
    - **input_codec**: Format of the input data (json, raw, etc.)
    - **store_codec**: Format to store the node in (dag-cbor, dag-json, etc.)
    - **pin**: Whether to pin the added node
    - **hash_alg**: Hash algorithm to use (sha2-256, sha2-512, etc.)
    """
    ipfs_advanced = get_ipfs_advanced()
    result = ipfs_advanced.dag_put(
        data=request.data,
        input_codec=request.input_codec,
        store_codec=request.store_codec,
        pin=request.pin,
        hash_alg=request.hash_alg
    )
    
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to put DAG node"))
    
    return result

@router.post("/dag/resolve", response_model=Dict[str, Any], summary="Resolve an IPFS path to a DAG node")
async def dag_resolve(request: DagResolveRequest):
    """
    Resolve an IPFS path to a DAG node.
    
    - **path**: IPFS path to resolve (e.g., /ipfs/QmXYZ/file)
    """
    ipfs_advanced = get_ipfs_advanced()
    result = ipfs_advanced.dag_resolve(path=request.path)
    
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to resolve DAG path"))
    
    return result

@router.get("/dag/stat/{cid}", response_model=Dict[str, Any], summary="Get statistics about a DAG node")
async def dag_stat(cid: str = Path(..., description="The CID of the DAG node")):
    """
    Get statistics about a DAG node.
    
    - **cid**: The CID of the DAG node
    """
    ipfs_advanced = get_ipfs_advanced()
    result = ipfs_advanced.dag_stat(cid=cid)
    
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to get DAG stats"))
    
    return result

# --- Object Operations ---

@router.post("/object/new", response_model=Dict[str, Any], summary="Create a new IPFS object")
async def object_new(request: ObjectNewRequest):
    """
    Create a new IPFS object.
    
    - **template**: Template to use (unixfs-dir, etc.)
    """
    ipfs_advanced = get_ipfs_advanced()
    result = ipfs_advanced.object_new(template=request.template)
    
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to create new object"))
    
    return result

@router.get("/object/get/{cid}", response_model=Dict[str, Any], summary="Get an IPFS object")
async def object_get(cid: str = Path(..., description="The CID of the object")):
    """
    Get an IPFS object.
    
    - **cid**: The CID of the object
    """
    ipfs_advanced = get_ipfs_advanced()
    result = ipfs_advanced.object_get(cid=cid)
    
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to get object"))
    
    return result

@router.post("/object/put", response_model=Dict[str, Any], summary="Put data into IPFS as an object")
async def object_put(request: ObjectPutRequest):
    """
    Put data into IPFS as an object.
    
    - **data**: The data to store
    - **input_codec**: Format of the input data (json, raw, etc.)
    - **pin**: Whether to pin the added object
    """
    ipfs_advanced = get_ipfs_advanced()
    result = ipfs_advanced.object_put(
        data=request.data,
        input_codec=request.input_codec,
        pin=request.pin
    )
    
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to put object"))
    
    return result

@router.get("/object/stat/{cid}", response_model=Dict[str, Any], summary="Get statistics about an IPFS object")
async def object_stat(cid: str = Path(..., description="The CID of the object")):
    """
    Get statistics about an IPFS object.
    
    - **cid**: The CID of the object
    """
    ipfs_advanced = get_ipfs_advanced()
    result = ipfs_advanced.object_stat(cid=cid)
    
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to get object stats"))
    
    return result

@router.get("/object/links/{cid}", response_model=Dict[str, Any], summary="Get links from an IPFS object")
async def object_links(cid: str = Path(..., description="The CID of the object")):
    """
    Get links from an IPFS object.
    
    - **cid**: The CID of the object
    """
    ipfs_advanced = get_ipfs_advanced()
    result = ipfs_advanced.object_links(cid=cid)
    
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to get object links"))
    
    return result

@router.post("/object/patch/add-link", response_model=Dict[str, Any], summary="Add a link to an IPFS object")
async def object_patch_add_link(request: ObjectPatchAddLinkRequest):
    """
    Add a link to an IPFS object.
    
    - **cid**: The CID of the object to modify
    - **link_name**: Name of the link to add
    - **link_cid**: CID that the link points to
    """
    ipfs_advanced = get_ipfs_advanced()
    result = ipfs_advanced.object_patch_add_link(
        cid=request.cid,
        link_name=request.link_name,
        link_cid=request.link_cid
    )
    
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to add link to object"))
    
    return result

@router.post("/object/patch/rm-link", response_model=Dict[str, Any], summary="Remove a link from an IPFS object")
async def object_patch_rm_link(request: ObjectPatchRmLinkRequest):
    """
    Remove a link from an IPFS object.
    
    - **cid**: The CID of the object to modify
    - **link_name**: Name of the link to remove
    """
    ipfs_advanced = get_ipfs_advanced()
    result = ipfs_advanced.object_patch_rm_link(
        cid=request.cid,
        link_name=request.link_name
    )
    
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to remove link from object"))
    
    return result

@router.post("/object/patch/set-data", response_model=Dict[str, Any], summary="Set the data field of an IPFS object")
async def object_patch_set_data(request: ObjectPatchSetDataRequest):
    """
    Set the data field of an IPFS object.
    
    - **cid**: The CID of the object to modify
    - **data**: New data for the object
    """
    ipfs_advanced = get_ipfs_advanced()
    result = ipfs_advanced.object_patch_set_data(
        cid=request.cid,
        data=request.data
    )
    
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to set data on object"))
    
    return result

# --- IPNS Operations ---

@router.post("/name/publish", response_model=Dict[str, Any], summary="Publish a name (IPNS) pointing to an IPFS path")
async def name_publish(request: NamePublishRequest):
    """
    Publish a name (IPNS) pointing to an IPFS path.
    
    - **cid**: The CID to point to
    - **key**: Name of the key to use (default: "self")
    - **lifetime**: How long the record will be valid for
    - **allow_offline**: Allow publishing when offline
    - **ttl**: Time-to-live for the record
    """
    ipfs_advanced = get_ipfs_advanced()
    result = ipfs_advanced.name_publish(
        cid=request.cid,
        key=request.key,
        lifetime=request.lifetime,
        allow_offline=request.allow_offline,
        ttl=request.ttl
    )
    
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to publish name"))
    
    return result

@router.post("/name/resolve", response_model=Dict[str, Any], summary="Resolve an IPNS name to its IPFS path")
async def name_resolve(request: NameResolveRequest):
    """
    Resolve an IPNS name to its IPFS path.
    
    - **name**: IPNS name to resolve
    - **recursive**: Resolve through chains of IPNS entries
    - **nocache**: Do not use cached entries
    """
    ipfs_advanced = get_ipfs_advanced()
    result = ipfs_advanced.name_resolve(
        name=request.name,
        recursive=request.recursive,
        nocache=request.nocache
    )
    
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to resolve name"))
    
    return result

# --- Key Management ---

@router.post("/key/gen", response_model=Dict[str, Any], summary="Generate a new keypair for IPNS")
async def key_gen(request: KeyGenRequest):
    """
    Generate a new keypair for IPNS.
    
    - **name**: Name of the key
    - **type**: Type of the key (rsa, ed25519, etc.)
    - **size**: Size of the key in bits (for RSA)
    """
    ipfs_advanced = get_ipfs_advanced()
    result = ipfs_advanced.key_gen(
        name=request.name,
        type=request.type,
        size=request.size
    )
    
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to generate key"))
    
    return result

@router.get("/key/list", response_model=Dict[str, Any], summary="List all keys")
async def key_list():
    """
    List all keys.
    """
    ipfs_advanced = get_ipfs_advanced()
    result = ipfs_advanced.key_list()
    
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to list keys"))
    
    return result

@router.post("/key/rename", response_model=Dict[str, Any], summary="Rename a key")
async def key_rename(request: KeyRenameRequest):
    """
    Rename a key.
    
    - **old_name**: Current name of the key
    - **new_name**: New name for the key
    """
    ipfs_advanced = get_ipfs_advanced()
    result = ipfs_advanced.key_rename(
        old_name=request.old_name,
        new_name=request.new_name
    )
    
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to rename key"))
    
    return result

@router.delete("/key/rm/{name}", response_model=Dict[str, Any], summary="Remove a key")
async def key_rm(name: str = Path(..., description="Name of the key to remove")):
    """
    Remove a key.
    
    - **name**: Name of the key to remove
    """
    ipfs_advanced = get_ipfs_advanced()
    result = ipfs_advanced.key_rm(name=name)
    
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to remove key"))
    
    return result

@router.post("/key/import", response_model=Dict[str, Any], summary="Import a key")
async def key_import(request: KeyImportRequest):
    """
    Import a key.
    
    - **name**: Name for the imported key
    - **key_data**: The key data to import (as a string)
    """
    ipfs_advanced = get_ipfs_advanced()
    result = ipfs_advanced.key_import(
        name=request.name,
        key_data=request.key_data
    )
    
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to import key"))
    
    return result

@router.get("/key/export/{name}", response_model=Dict[str, Any], summary="Export a key")
async def key_export(name: str = Path(..., description="Name of the key to export")):
    """
    Export a key.
    
    - **name**: Name of the key to export
    """
    ipfs_advanced = get_ipfs_advanced()
    result = ipfs_advanced.key_export(name=name)
    
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to export key"))
    
    return result

# --- Swarm/Network Operations ---

@router.get("/swarm/peers", response_model=Dict[str, Any], summary="List peers connected to the IPFS node")
async def swarm_peers():
    """
    List peers connected to the IPFS node.
    """
    ipfs_advanced = get_ipfs_advanced()
    result = ipfs_advanced.swarm_peers()
    
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to list peers"))
    
    return result

@router.post("/swarm/connect", response_model=Dict[str, Any], summary="Connect to a peer")
async def swarm_connect(request: SwarmConnectRequest):
    """
    Connect to a peer.
    
    - **address**: Multiaddr of the peer to connect to
    """
    ipfs_advanced = get_ipfs_advanced()
    result = ipfs_advanced.swarm_connect(address=request.address)
    
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to connect to peer"))
    
    return result

@router.delete("/swarm/disconnect/{address}", response_model=Dict[str, Any], summary="Disconnect from a peer")
async def swarm_disconnect(address: str = Path(..., description="Multiaddr of the peer to disconnect from")):
    """
    Disconnect from a peer.
    
    - **address**: Multiaddr of the peer to disconnect from
    """
    ipfs_advanced = get_ipfs_advanced()
    result = ipfs_advanced.swarm_disconnect(address=address)
    
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to disconnect from peer"))
    
    return result

@router.get("/bootstrap/list", response_model=Dict[str, Any], summary="List bootstrap nodes")
async def bootstrap_list():
    """
    List bootstrap nodes.
    """
    ipfs_advanced = get_ipfs_advanced()
    result = ipfs_advanced.bootstrap_list()
    
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to list bootstrap nodes"))
    
    return result

@router.post("/bootstrap/add", response_model=Dict[str, Any], summary="Add a bootstrap node")
async def bootstrap_add(request: BootstrapAddRequest):
    """
    Add a bootstrap node.
    
    - **address**: Multiaddr of the bootstrap node to add
    """
    ipfs_advanced = get_ipfs_advanced()
    result = ipfs_advanced.bootstrap_add(address=request.address)
    
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to add bootstrap node"))
    
    return result

@router.delete("/bootstrap/rm/{address}", response_model=Dict[str, Any], summary="Remove a bootstrap node")
async def bootstrap_rm(address: str = Path(..., description="Multiaddr of the bootstrap node to remove")):
    """
    Remove a bootstrap node.
    
    - **address**: Multiaddr of the bootstrap node to remove
    """
    ipfs_advanced = get_ipfs_advanced()
    result = ipfs_advanced.bootstrap_rm(address=address)
    
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to remove bootstrap node"))
    
    return result

@router.get("/stats", response_model=Dict[str, Any], summary="Get performance statistics for advanced operations")
async def get_stats():
    """
    Get performance statistics for advanced IPFS operations.
    """
    ipfs_advanced = get_ipfs_advanced()
    return ipfs_advanced.get_stats()