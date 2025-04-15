"""
Advanced IPFS Operations Integration Example.

This module demonstrates how to integrate and use the enhanced IPFS operations
in the MCP server ecosystem, including connection pooling, DHT operations,
IPNS key management, and DAG manipulations.
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel, Field

# Import our advanced IPFS modules
from ipfs_kit_py.mcp.extensions.ipfs_advanced_init import init_advanced_ipfs, shutdown_advanced_ipfs
from ipfs_kit_py.mcp.extensions.advanced_ipfs_operations import get_instance as get_advanced_ipfs

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ipfs_advanced_integration")

# Sample model for demo requests
class DemoRequest(BaseModel):
    """Sample request model for the demo."""
    cid: Optional[str] = Field(None, description="Content identifier to use in the demo")
    peer_id: Optional[str] = Field(None, description="Peer ID to use in the demo")
    data: Optional[Dict[str, Any]] = Field(None, description="Sample data for the demo")
    operation: str = Field(..., description="Operation to demonstrate: 'dht', 'ipns', 'dag'")

class DemoResponse(BaseModel):
    """Sample response model for the demo."""
    success: bool = Field(..., description="Whether the operation was successful")
    operation: str = Field(..., description="The operation that was performed")
    result: Dict[str, Any] = Field(..., description="Result of the operation")
    duration_ms: float = Field(..., description="Duration of the operation in milliseconds")

# Create a FastAPI app for the demo
app = FastAPI(
    title="IPFS Advanced Operations Demo",
    description="Demonstration of enhanced IPFS operations in MCP",
    version="1.0.0"
)

# Initialize advanced IPFS operations with the app
init_result = init_advanced_ipfs(app, {
    "api_url": "http://127.0.0.1:5001/api/v0",  # Change this to your IPFS API URL
    "max_connections": 10,
    "connection_timeout": 30,
    "idle_timeout": 300,
})

if not init_result["success"]:
    logger.error(f"Failed to initialize Advanced IPFS Operations: {init_result.get('error')}")

# Create a router for the demo
demo_router = APIRouter(prefix="/demo", tags=["Demo"])

# Register demo endpoints
@demo_router.post("/run_demo", response_model=DemoResponse)
async def run_demo(request: DemoRequest):
    """
    Run a demonstration of advanced IPFS operations.
    
    This endpoint runs a selected demo operation to showcase the advanced IPFS functionality.
    
    Args:
        request: The demo request parameters
        
    Returns:
        Results of the demo operation
    """
    start_time = time.time()
    
    # Get the advanced IPFS operations instance
    advanced_ipfs = get_advanced_ipfs()
    
    # Dispatch to the appropriate demo based on the requested operation
    if request.operation == "dht":
        return await run_dht_demo(advanced_ipfs, request, start_time)
    elif request.operation == "ipns":
        return await run_ipns_demo(advanced_ipfs, request, start_time)
    elif request.operation == "dag":
        return await run_dag_demo(advanced_ipfs, request, start_time)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported operation: {request.operation}")

async def run_dht_demo(advanced_ipfs, request: DemoRequest, start_time: float) -> DemoResponse:
    """Run a DHT operations demo."""
    logger.info("Running DHT operations demo")
    
    # For the demo, we'll try to discover peers
    max_peers = 5  # Keep small for the demo
    timeout = 10  # Short timeout for the demo
    
    # If a peer ID was provided, use it for a targeted query
    if request.peer_id:
        # Try to find the specified peer
        result = advanced_ipfs.dht_find_peer(request.peer_id)
        operation = "dht_find_peer"
    elif request.cid:
        # Try to find providers for the specified CID
        result = advanced_ipfs.dht_find_providers(request.cid, max_peers)
        operation = "dht_find_providers"
    else:
        # Discover random peers
        result = advanced_ipfs.dht_discover_peers(max_peers=max_peers, timeout=timeout)
        operation = "dht_discover_peers"
    
    duration_ms = (time.time() - start_time) * 1000
    
    return DemoResponse(
        success=result.get("success", False),
        operation=operation,
        result=result,
        duration_ms=duration_ms
    )

async def run_ipns_demo(advanced_ipfs, request: DemoRequest, start_time: float) -> DemoResponse:
    """Run an IPNS operations demo."""
    logger.info("Running IPNS operations demo")
    
    # For the demo, we'll do a basic key operation and IPNS publish/resolve
    
    # Generate a unique test key name
    import uuid
    test_key_name = f"demo-key-{uuid.uuid4().hex[:8]}"
    
    try:
        # Create a new key
        create_result = advanced_ipfs.create_key(test_key_name)
        if not create_result.get("success", False):
            return DemoResponse(
                success=False,
                operation="ipns_create_key",
                result=create_result,
                duration_ms=(time.time() - start_time) * 1000
            )
        
        # If a CID was provided, publish it with the new key
        if request.cid:
            publish_result = advanced_ipfs.publish(
                cid=request.cid,
                key_name=test_key_name,
                lifetime="1h",  # Short lifetime for demo
                ttl="5m",       # Short TTL for demo
            )
            
            if publish_result.get("success", False):
                # Resolve the name we just published
                name_to_resolve = publish_result.get("name")
                resolve_result = advanced_ipfs.resolve(name_to_resolve)
                
                # Return the combined results
                result = {
                    "key_creation": create_result,
                    "publishing": publish_result,
                    "resolution": resolve_result
                }
                operation = "ipns_publish_resolve"
            else:
                # Return results up to publishing
                result = {
                    "key_creation": create_result,
                    "publishing": publish_result
                }
                operation = "ipns_publish"
        else:
            # Just return the key creation result
            result = create_result
            operation = "ipns_create_key"
        
    finally:
        # Clean up by removing the test key (don't impact operation success)
        try:
            advanced_ipfs.remove_key(test_key_name)
        except Exception as e:
            logger.warning(f"Failed to clean up test key {test_key_name}: {e}")
    
    duration_ms = (time.time() - start_time) * 1000
    
    return DemoResponse(
        success=True,
        operation=operation,
        result=result,
        duration_ms=duration_ms
    )

async def run_dag_demo(advanced_ipfs, request: DemoRequest, start_time: float) -> DemoResponse:
    """Run a DAG operations demo."""
    logger.info("Running DAG operations demo")
    
    # If data was provided, use it for the demo
    if request.data:
        test_data = request.data
    else:
        # Create sample data for the demo
        test_data = {
            "name": "DAG Demo Node",
            "created": time.time(),
            "demo": True,
            "nested": {
                "items": [1, 2, 3, 4, 5],
                "flag": True,
                "metadata": {
                    "type": "test",
                    "version": "1.0.0"
                }
            }
        }
    
    # Store the data in the DAG
    put_result = advanced_ipfs.dag_put(test_data)
    
    if not put_result.get("success", False):
        return DemoResponse(
            success=False,
            operation="dag_put",
            result=put_result,
            duration_ms=(time.time() - start_time) * 1000
        )
    
    cid = put_result.get("cid")
    
    # Retrieve the data we just stored
    get_result = advanced_ipfs.dag_get(cid)
    
    # Get stats about the node
    stat_result = advanced_ipfs.dag_stat(cid)
    
    # Retrieve a nested path
    nested_path_result = advanced_ipfs.dag_get(cid, path="/nested/metadata")
    
    # Update the data with a new field
    update_data = {"updated": time.time(), "demo_completed": True}
    update_result = advanced_ipfs.dag_update_node(cid, update_data)
    
    # Combine all results
    result = {
        "put": put_result,
        "get": get_result,
        "stat": stat_result,
        "nested_path": nested_path_result,
        "update": update_result
    }
    
    duration_ms = (time.time() - start_time) * 1000
    
    return DemoResponse(
        success=True,
        operation="dag_operations",
        result=result,
        duration_ms=duration_ms
    )

# Include the demo router in the app
app.include_router(demo_router)

# Add shutdown event handler to clean up resources
@app.on_event("shutdown")
async def on_shutdown():
    """Clean up resources when the app shuts down."""
    shutdown_result = shutdown_advanced_ipfs(app)
    if not shutdown_result["success"]:
        logger.error(f"Failed to shut down Advanced IPFS Operations: {shutdown_result.get('error')}")

# Example usage in a script
if __name__ == "__main__":
    import uvicorn
    
    # Run the demo app
    uvicorn.run("ipfs_advanced_integration:app", host="0.0.0.0", port=8000, reload=True)
    
    # Alternatively, you could use the modules directly without FastAPI:
    """
    # Direct usage example (uncomment to use)
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Initialize advanced IPFS operations
    from ipfs_kit_py.mcp.extensions.advanced_ipfs_operations import get_instance
    
    # Get the advanced IPFS operations instance with custom configuration
    advanced_ipfs = get_instance({
        "api_url": "http://127.0.0.1:5001/api/v0",
        "max_connections": 5,
    })
    
    # Use DHT operations
    peer_id = "QmYourPeerID"  # Replace with a real peer ID
    print(f"Finding peer {peer_id}...")
    result = advanced_ipfs.dht_find_peer(peer_id)
    print(f"Result: {json.dumps(result, indent=2)}")
    
    # Use IPNS operations
    print("Creating a new IPNS key...")
    key_result = advanced_ipfs.create_key("test-key")
    print(f"Key created: {json.dumps(key_result, indent=2)}")
    
    # Use DAG operations
    test_data = {"name": "Test Node", "value": 42}
    print(f"Storing data in DAG: {test_data}")
    put_result = advanced_ipfs.dag_put(test_data)
    print(f"DAG node created: {json.dumps(put_result, indent=2)}")
    
    # Clean up
    print("Shutting down...")
    advanced_ipfs.shutdown()
    """