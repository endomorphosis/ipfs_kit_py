"""
Advanced IPFS Integration for MCP

This module integrates the advanced IPFS operations into the MCP server framework.
It provides FastAPI route handlers and necessary glue code.
"""

import logging
from typing import Any, Dict, List, Optional, Union
from fastapi import APIRouter, Body, Query, Path, HTTPException, Depends, File, UploadFile

from ipfs_kit_py.mcp.extensions.ipfs_advanced import AdvancedIPFSOperations
from ipfs_kit_py.mcp.mcp_error_handling import handle_operation_error, MCPErrorResponse

logger = logging.getLogger("ipfs_advanced_integration")

# Create router for advanced IPFS operations
router = APIRouter(prefix="/api/v0/ipfs/advanced")

# Cached instance of the AdvancedIPFSOperations class
_advanced_ipfs_instance = None

def get_advanced_ipfs() -> AdvancedIPFSOperations:
    """
    Get or create an instance of the AdvancedIPFSOperations class.
    
    Returns:
        AdvancedIPFSOperations: The AdvancedIPFSOperations instance
    """
    global _advanced_ipfs_instance
    if _advanced_ipfs_instance is None:
        # Import here to avoid circular imports
        from ipfs_kit_py.mcp.storage_manager.instance_manager import get_storage_backend
        ipfs_backend = get_storage_backend("ipfs")
        if ipfs_backend is None:
            raise HTTPException(status_code=500, detail="IPFS backend not available")
        _advanced_ipfs_instance = AdvancedIPFSOperations(ipfs_backend)
    return _advanced_ipfs_instance

# DHT Operations Routes

@router.get("/dht/findpeer/{peer_id}", summary="Find a specific peer in the DHT")
async def dht_find_peer(
    peer_id: str = Path(..., description="The peer ID to find"),
    timeout: int = Query(30, description="Operation timeout in seconds")
):
    """
    Find a specific peer in the DHT network.
    
    Returns addresses where the peer can be reached.
    """
    try:
        ipfs_adv = get_advanced_ipfs()
        result = ipfs_adv.dht_find_peer(peer_id, options={"timeout": timeout})
        if not result.get("success", False):
            return handle_operation_error(result)
        return result
    except Exception as e:
        logger.error(f"Error finding peer: {str(e)}")
        return MCPErrorResponse.from_exception(e)

@router.get("/dht/findproviders/{cid}", summary="Find providers for a CID")
async def dht_find_providers(
    cid: str = Path(..., description="The CID to find providers for"),
    num_providers: int = Query(20, description="Maximum number of providers to find"),
    timeout: int = Query(30, description="Operation timeout in seconds")
):
    """
    Find peers in the network that can provide a specific content (CID).
    
    Returns a list of provider peer IDs.
    """
    try:
        ipfs_adv = get_advanced_ipfs()
        result = ipfs_adv.dht_find_providers(cid, num_providers=num_providers, 
                                           options={"timeout": timeout})
        if not result.get("success", False):
            return handle_operation_error(result)
        return result
    except Exception as e:
        logger.error(f"Error finding providers: {str(e)}")
        return MCPErrorResponse.from_exception(e)

@router.get("/dht/get/{key}", summary="Get a value from the DHT")
async def dht_get(
    key: str = Path(..., description="The key to get the value for"),
    timeout: int = Query(30, description="Operation timeout in seconds")
):
    """
    Get a value from the DHT for a given key.
    """
    try:
        ipfs_adv = get_advanced_ipfs()
        result = ipfs_adv.dht_get(key, options={"timeout": timeout})
        if not result.get("success", False):
            return handle_operation_error(result)
        return result
    except Exception as e:
        logger.error(f"Error getting DHT value: {str(e)}")
        return MCPErrorResponse.from_exception(e)

@router.post("/dht/provide/{cid}", summary="Announce that we are providing a CID")
async def dht_provide(
    cid: str = Path(..., description="The CID to announce"),
    recursive: bool = Query(False, description="Whether to recursively provide the entire DAG"),
    timeout: int = Query(30, description="Operation timeout in seconds")
):
    """
    Announce to the network that we are providing a given CID.
    
    This allows other peers to find us when they search for this content.
    """
    try:
        ipfs_adv = get_advanced_ipfs()
        result = ipfs_adv.dht_provide(cid, recursive=recursive, 
                                    options={"timeout": timeout})
        if not result.get("success", False):
            return handle_operation_error(result)
        return result
    except Exception as e:
        logger.error(f"Error providing content: {str(e)}")
        return MCPErrorResponse.from_exception(e)

@router.post("/dht/put", summary="Put a value into the DHT")
async def dht_put(
    key: str = Body(..., description="The key to store the value under"),
    value: str = Body(..., description="The value to store"),
    timeout: int = Query(30, description="Operation timeout in seconds")
):
    """
    Put a value into the DHT for a given key.
    """
    try:
        ipfs_adv = get_advanced_ipfs()
        result = ipfs_adv.dht_put(key, value, options={"timeout": timeout})
        if not result.get("success", False):
            return handle_operation_error(result)
        return result
    except Exception as e:
        logger.error(f"Error putting DHT value: {str(e)}")
        return MCPErrorResponse.from_exception(e)

@router.get("/dht/query/{peer_id}", summary="Find the closest peers to a given peer")
async def dht_query(
    peer_id: str = Path(..., description="The peer ID to find closest peers to"),
    timeout: int = Query(30, description="Operation timeout in seconds")
):
    """
    Find the closest peers to a given peer by querying the DHT.
    """
    try:
        ipfs_adv = get_advanced_ipfs()
        result = ipfs_adv.dht_query(peer_id, options={"timeout": timeout})
        if not result.get("success", False):
            return handle_operation_error(result)
        return result
    except Exception as e:
        logger.error(f"Error querying DHT: {str(e)}")
        return MCPErrorResponse.from_exception(e)

# DAG Operations Routes

@router.get("/dag/get/{cid}", summary="Get a DAG node from IPFS")
async def dag_get(
    cid: str = Path(..., description="The CID of the DAG node"),
    path: str = Query("", description="Optional path within the DAG to retrieve"),
    timeout: int = Query(30, description="Operation timeout in seconds")
):
    """
    Get a DAG node from IPFS.
    
    This can retrieve a complex data structure from IPFS with full IPLD support.
    """
    try:
        ipfs_adv = get_advanced_ipfs()
        result = ipfs_adv.dag_get(cid, path=path, options={"timeout": timeout})
        if not result.get("success", False):
            return handle_operation_error(result)
        return result
    except Exception as e:
        logger.error(f"Error getting DAG node: {str(e)}")
        return MCPErrorResponse.from_exception(e)

@router.post("/dag/put", summary="Put a DAG node into IPFS")
async def dag_put(
    data: Any = Body(..., description="The data to store as a DAG node"),
    format: str = Query("dag-cbor", description="Format of serialization (dag-cbor, dag-json)"),
    timeout: int = Query(30, description="Operation timeout in seconds")
):
    """
    Put a DAG node into IPFS.
    
    This allows storing complex data structures in IPFS with IPLD support.
    """
    try:
        ipfs_adv = get_advanced_ipfs()
        result = ipfs_adv.dag_put(data, options={"format": format, "timeout": timeout})
        if not result.get("success", False):
            return handle_operation_error(result)
        return result
    except Exception as e:
        logger.error(f"Error putting DAG node: {str(e)}")
        return MCPErrorResponse.from_exception(e)

@router.get("/dag/resolve/{cid_path}", summary="Resolve a CID path")
async def dag_resolve(
    cid_path: str = Path(..., description="The CID path to resolve"),
    timeout: int = Query(30, description="Operation timeout in seconds")
):
    """
    Resolve a CID path to its target CID.
    """
    try:
        ipfs_adv = get_advanced_ipfs()
        result = ipfs_adv.dag_resolve(cid_path, options={"timeout": timeout})
        if not result.get("success", False):
            return handle_operation_error(result)
        return result
    except Exception as e:
        logger.error(f"Error resolving DAG path: {str(e)}")
        return MCPErrorResponse.from_exception(e)

@router.post("/dag/import", summary="Import a DAG from a .car file")
async def dag_import(
    file: UploadFile = File(..., description="The CAR file to import"),
    timeout: int = Query(60, description="Operation timeout in seconds")
):
    """
    Import a DAG from a .car (Content Addressable aRchive) file.
    """
    try:
        ipfs_adv = get_advanced_ipfs()
        result = ipfs_adv.dag_import(file.file, options={"timeout": timeout})
        if not result.get("success", False):
            return handle_operation_error(result)
        return result
    except Exception as e:
        logger.error(f"Error importing DAG: {str(e)}")
        return MCPErrorResponse.from_exception(e)

@router.get("/dag/export/{cid}", summary="Export a DAG to a .car file")
async def dag_export(
    cid: str = Path(..., description="The CID of the DAG root to export"),
    timeout: int = Query(60, description="Operation timeout in seconds")
):
    """
    Export a DAG to a .car (Content Addressable aRchive) file.
    
    Returns the CAR file content as a binary response.
    """
    try:
        ipfs_adv = get_advanced_ipfs()
        result = ipfs_adv.dag_export(cid, options={"timeout": timeout})
        if not result.get("success", False):
            return handle_operation_error(result)
        
        # Return binary response
        from fastapi.responses import Response
        return Response(
            content=result["data"],
            media_type="application/vnd.ipld.car",
            headers={"Content-Disposition": f"attachment; filename={cid}.car"}
        )
    except Exception as e:
        logger.error(f"Error exporting DAG: {str(e)}")
        return MCPErrorResponse.from_exception(e)

# IPNS Operations Routes

@router.post("/name/publish/{cid}", summary="Publish a CID to IPNS")
async def name_publish(
    cid: str = Path(..., description="The CID to publish"),
    key: str = Query("self", description="The key to use for publishing"),
    lifetime: str = Query("24h", description="Duration for which the record will be valid"),
    ttl: str = Query("1h", description="Duration for which the record should be cached"),
    timeout: int = Query(60, description="Operation timeout in seconds")
):
    """
    Publish a CID to IPNS.
    
    This creates a mutable pointer to the immutable CID.
    """
    try:
        ipfs_adv = get_advanced_ipfs()
        result = ipfs_adv.name_publish(cid, key=key, lifetime=lifetime, ttl=ttl, 
                                     options={"timeout": timeout})
        if not result.get("success", False):
            return handle_operation_error(result)
        return result
    except Exception as e:
        logger.error(f"Error publishing to IPNS: {str(e)}")
        return MCPErrorResponse.from_exception(e)

@router.get("/name/resolve/{name}", summary="Resolve an IPNS name")
async def name_resolve(
    name: str = Path(..., description="The IPNS name to resolve"),
    recursive: bool = Query(True, description="Whether to recursively resolve the name"),
    nocache: bool = Query(False, description="Whether to bypass the cache"),
    timeout: int = Query(30, description="Operation timeout in seconds")
):
    """
    Resolve an IPNS name to its current value.
    """
    try:
        ipfs_adv = get_advanced_ipfs()
        result = ipfs_adv.name_resolve(name, recursive=recursive, nocache=nocache, 
                                     options={"timeout": timeout})
        if not result.get("success", False):
            return handle_operation_error(result)
        return result
    except Exception as e:
        logger.error(f"Error resolving IPNS name: {str(e)}")
        return MCPErrorResponse.from_exception(e)

@router.get("/key/list", summary="List all IPNS keys")
async def key_list(
    timeout: int = Query(30, description="Operation timeout in seconds")
):
    """
    List all IPNS keys.
    """
    try:
        ipfs_adv = get_advanced_ipfs()
        result = ipfs_adv.key_list(options={"timeout": timeout})
        if not result.get("success", False):
            return handle_operation_error(result)
        return result
    except Exception as e:
        logger.error(f"Error listing keys: {str(e)}")
        return MCPErrorResponse.from_exception(e)

@router.post("/key/gen/{name}", summary="Generate a new IPNS key")
async def key_gen(
    name: str = Path(..., description="The name for the new key"),
    type: str = Query("rsa", description="The type of key to generate (e.g., 'rsa', 'ed25519')"),
    size: int = Query(2048, description="The size of the key in bits"),
    timeout: int = Query(30, description="Operation timeout in seconds")
):
    """
    Generate a new IPNS key.
    """
    try:
        ipfs_adv = get_advanced_ipfs()
        result = ipfs_adv.key_gen(name, type_str=type, size=size, 
                                options={"timeout": timeout})
        if not result.get("success", False):
            return handle_operation_error(result)
        return result
    except Exception as e:
        logger.error(f"Error generating key: {str(e)}")
        return MCPErrorResponse.from_exception(e)

@router.delete("/key/rm/{name}", summary="Remove an IPNS key")
async def key_rm(
    name: str = Path(..., description="The name of the key to remove"),
    timeout: int = Query(30, description="Operation timeout in seconds")
):
    """
    Remove an IPNS key.
    """
    try:
        ipfs_adv = get_advanced_ipfs()
        result = ipfs_adv.key_rm(name, options={"timeout": timeout})
        if not result.get("success", False):
            return handle_operation_error(result)
        return result
    except Exception as e:
        logger.error(f"Error removing key: {str(e)}")
        return MCPErrorResponse.from_exception(e)

@router.post("/key/rename/{old_name}/{new_name}", summary="Rename an IPNS key")
async def key_rename(
    old_name: str = Path(..., description="The current name of the key"),
    new_name: str = Path(..., description="The new name for the key"),
    timeout: int = Query(30, description="Operation timeout in seconds")
):
    """
    Rename an IPNS key.
    """
    try:
        ipfs_adv = get_advanced_ipfs()
        result = ipfs_adv.key_rename(old_name, new_name, options={"timeout": timeout})
        if not result.get("success", False):
            return handle_operation_error(result)
        return result
    except Exception as e:
        logger.error(f"Error renaming key: {str(e)}")
        return MCPErrorResponse.from_exception(e)

@router.post("/key/import/{name}", summary="Import an IPNS key")
async def key_import(
    name: str = Path(..., description="The name for the imported key"),
    key_data: str = Body(..., description="The PEM encoded key data"),
    timeout: int = Query(30, description="Operation timeout in seconds")
):
    """
    Import an IPNS key.
    """
    try:
        ipfs_adv = get_advanced_ipfs()
        result = ipfs_adv.key_import(name, key_data, options={"timeout": timeout})
        if not result.get("success", False):
            return handle_operation_error(result)
        return result
    except Exception as e:
        logger.error(f"Error importing key: {str(e)}")
        return MCPErrorResponse.from_exception(e)

# Object Operations Routes

@router.post("/object/new", summary="Create a new IPFS object")
async def object_new(
    template: str = Query("unixfs-dir", description="The template to use"),
    timeout: int = Query(30, description="Operation timeout in seconds")
):
    """
    Create a new IPFS object.
    """
    try:
        ipfs_adv = get_advanced_ipfs()
        result = ipfs_adv.object_new(template=template, options={"timeout": timeout})
        if not result.get("success", False):
            return handle_operation_error(result)
        return result
    except Exception as e:
        logger.error(f"Error creating object: {str(e)}")
        return MCPErrorResponse.from_exception(e)

@router.post("/object/put", summary="Put a data blob into IPFS as an object")
async def object_put(
    data: Any = Body(..., description="The data to store"),
    timeout: int = Query(30, description="Operation timeout in seconds")
):
    """
    Put a data blob into IPFS as an object.
    """
    try:
        ipfs_adv = get_advanced_ipfs()
        result = ipfs_adv.object_put(data, options={"timeout": timeout})
        if not result.get("success", False):
            return handle_operation_error(result)
        return result
    except Exception as e:
        logger.error(f"Error putting object: {str(e)}")
        return MCPErrorResponse.from_exception(e)

@router.get("/object/get/{cid}", summary="Get an IPFS object")
async def object_get(
    cid: str = Path(..., description="The CID of the object to get"),
    timeout: int = Query(30, description="Operation timeout in seconds")
):
    """
    Get an IPFS object.
    """
    try:
        ipfs_adv = get_advanced_ipfs()
        result = ipfs_adv.object_get(cid, options={"timeout": timeout})
        if not result.get("success", False):
            return handle_operation_error(result)
        return result
    except Exception as e:
        logger.error(f"Error getting object: {str(e)}")
        return MCPErrorResponse.from_exception(e)

@router.get("/object/links/{cid}", summary="Get the links from an IPFS object")
async def object_links(
    cid: str = Path(..., description="The CID of the object"),
    timeout: int = Query(30, description="Operation timeout in seconds")
):
    """
    Get the links from an IPFS object.
    """
    try:
        ipfs_adv = get_advanced_ipfs()
        result = ipfs_adv.object_links(cid, options={"timeout": timeout})
        if not result.get("success", False):
            return handle_operation_error(result)
        return result
    except Exception as e:
        logger.error(f"Error getting object links: {str(e)}")
        return MCPErrorResponse.from_exception(e)

@router.post("/object/patch/add-link/{cid}/{name}/{link_cid}", summary="Add a link to an IPFS object")
async def object_patch_add_link(
    cid: str = Path(..., description="The CID of the object to modify"),
    name: str = Path(..., description="The name of the link"),
    link_cid: str = Path(..., description="The CID of the object to link to"),
    timeout: int = Query(30, description="Operation timeout in seconds")
):
    """
    Add a link to an IPFS object.
    """
    try:
        ipfs_adv = get_advanced_ipfs()
        result = ipfs_adv.object_patch_add_link(cid, name, link_cid, 
                                              options={"timeout": timeout})
        if not result.get("success", False):
            return handle_operation_error(result)
        return result
    except Exception as e:
        logger.error(f"Error adding link to object: {str(e)}")
        return MCPErrorResponse.from_exception(e)

@router.post("/object/patch/rm-link/{cid}/{name}", summary="Remove a link from an IPFS object")
async def object_patch_rm_link(
    cid: str = Path(..., description="The CID of the object to modify"),
    name: str = Path(..., description="The name of the link to remove"),
    timeout: int = Query(30, description="Operation timeout in seconds")
):
    """
    Remove a link from an IPFS object.
    """
    try:
        ipfs_adv = get_advanced_ipfs()
        result = ipfs_adv.object_patch_rm_link(cid, name, options={"timeout": timeout})
        if not result.get("success", False):
            return handle_operation_error(result)
        return result
    except Exception as e:
        logger.error(f"Error removing link from object: {str(e)}")
        return MCPErrorResponse.from_exception(e)

@router.get("/stats", summary="Get advanced IPFS operation statistics")
async def get_stats():
    """
    Get performance statistics for advanced IPFS operations.
    """
    try:
        ipfs_adv = get_advanced_ipfs()
        result = ipfs_adv.get_stats()
        return result
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}")
        return MCPErrorResponse.from_exception(e)

# Function to include the router in the MCP server
def register_advanced_ipfs_routes(app):
    """
    Register the advanced IPFS routes with the FastAPI application.
    
    Args:
        app: The FastAPI application instance
    """
    app.include_router(router, tags=["ipfs-advanced"])
    logger.info("Advanced IPFS operations routes registered")