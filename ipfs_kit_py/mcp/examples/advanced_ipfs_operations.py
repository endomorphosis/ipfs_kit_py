#!/usr/bin/env python3
"""
Example script showing how to integrate the advanced IPFS operations with the MCP server.

This demonstrates how to use the DHT, DAG, and IPNS operations through the MCP API.
"""

import os
import sys
import logging
import asyncio
import argparse
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("advanced-ipfs-operations")

# Add parent directory to path
current_dir = Path(__file__).parent
parent_dir = current_dir.parent.parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))
    logger.info(f"Added parent directory to path: {parent_dir}")

try:
    # Import FastAPI
    from fastapi import FastAPI
    import uvicorn
    
    # Import IPFS controllers
    from ipfs_kit_py.mcp.controllers.ipfs.router import create_ipfs_router, register_with_app
    
    # Import operations for direct usage
    import ipfs_dht_operations
    import ipfs_dag_operations
    import ipfs_ipns_operations
    
    imports_succeeded = True
    logger.info("Successfully imported required modules")
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    imports_succeeded = False

def setup_api():
    """Set up a FastAPI application with IPFS advanced operations."""
    app = FastAPI(
        title="Advanced IPFS Operations API",
        description="API for advanced IPFS operations including DHT, DAG, and IPNS",
        version="1.0.0",
    )
    
    # Register IPFS router with app
    register_with_app(app)
    
    # Add a simple home route
    @app.get("/")
    async def home():
        return {
            "message": "IPFS Advanced Operations API",
            "endpoints": {
                "/api/v0/dht/...": "DHT operations",
                "/api/v0/dag/...": "DAG operations",
                "/api/v0/key/...": "IPNS key operations",
                "/api/v0/name/...": "IPNS name operations",
                "/docs": "API documentation",
            }
        }
    
    return app

async def run_dht_example():
    """Run some example DHT operations directly."""
    logger.info("Running DHT operations example...")
    
    # Create a DHT operations instance
    dht_ops = ipfs_dht_operations.get_instance()
    
    # Example 1: Store a value in the DHT
    logger.info("Storing a value in the DHT...")
    store_result = dht_ops.put_value("test-key", "Hello, DHT world!")
    logger.info(f"Store result: {store_result}")
    
    # Example 2: Retrieve a value from the DHT
    logger.info("Retrieving a value from the DHT...")
    retrieve_result = dht_ops.get_value("test-key")
    logger.info(f"Retrieve result: {retrieve_result}")
    
    # Example 3: Get some network diagnostics
    logger.info("Getting DHT network diagnostics...")
    diagnostics = dht_ops.get_network_diagnostics()
    logger.info(f"DHT network diagnostics: {diagnostics}")
    
    return {"dht_examples_completed": True}

async def run_dag_example():
    """Run some example DAG operations directly."""
    logger.info("Running DAG operations example...")
    
    # Create a DAG operations instance
    dag_ops = ipfs_dag_operations.get_instance()
    
    # Example 1: Store a complex object in the DAG
    test_object = {
        "name": "Test DAG Node",
        "values": [1, 2, 3, 4, 5],
        "nested": {
            "a": "apple",
            "b": "banana",
            "c": "cherry"
        }
    }
    
    logger.info("Storing a complex object in the DAG...")
    put_result = dag_ops.put(data=test_object)
    
    if put_result.get("success", False):
        cid = put_result.get("cid")
        logger.info(f"Successfully stored object with CID: {cid}")
        
        # Example 2: Retrieve the DAG node
        logger.info(f"Retrieving DAG node with CID: {cid}...")
        get_result = dag_ops.get(cid=cid)
        
        if get_result.get("success", False):
            logger.info(f"Successfully retrieved DAG node: {get_result.get('data')}")
            
            # Example 3: Access a specific path within the DAG node
            logger.info("Accessing a specific path within the DAG node...")
            path_result = dag_ops.get(cid=cid, path="/nested/b")
            
            if path_result.get("success", False):
                logger.info(f"Path result: {path_result.get('data')}")
            else:
                logger.error(f"Failed to access path: {path_result.get('error')}")
        else:
            logger.error(f"Failed to retrieve DAG node: {get_result.get('error')}")
    else:
        logger.error(f"Failed to store object in DAG: {put_result.get('error')}")
    
    return {"dag_examples_completed": True}

async def run_ipns_example():
    """Run some example IPNS operations directly."""
    logger.info("Running IPNS operations example...")
    
    # Create an IPNS operations instance
    ipns_ops = ipfs_ipns_operations.get_instance()
    
    # Example 1: Create a new key
    key_name = "test-key"
    logger.info(f"Creating a new IPNS key: {key_name}...")
    create_result = ipns_ops.key_manager.create_key(
        name=key_name,
        key_type="ed25519"
    )
    
    if create_result.get("success", False):
        key_info = create_result.get("key", {})
        logger.info(f"Successfully created key: {key_info}")
        
        # Example 2: List all keys
        logger.info("Listing all IPNS keys...")
        list_result = ipns_ops.key_manager.list_keys()
        
        if list_result.get("success", False):
            keys = list_result.get("keys", [])
            logger.info(f"Found {len(keys)} keys: {keys}")
            
            # Example 3: Publish an IPNS name
            # We need a valid CID to publish - for this example, we'll use a sample CID
            sample_cid = "QmXG8yk8UJjMT6qtE2zSxzz3U7z5jSYRgzWRYHHEvfJAVY"
            logger.info(f"Publishing IPNS name with key {key_name} for CID {sample_cid}...")
            
            publish_result = ipns_ops.publish(
                cid=sample_cid,
                key_name=key_name
            )
            
            if publish_result.get("success", False):
                name = publish_result.get("name")
                value = publish_result.get("value")
                logger.info(f"Successfully published name {name} with value {value}")
                
                # Example 4: Resolve an IPNS name
                logger.info(f"Resolving IPNS name: {name}...")
                resolve_result = ipns_ops.resolve(name=name)
                
                if resolve_result.get("success", False):
                    resolved_value = resolve_result.get("value")
                    logger.info(f"Successfully resolved name to: {resolved_value}")
                else:
                    logger.error(f"Failed to resolve name: {resolve_result.get('error')}")
            else:
                logger.error(f"Failed to publish name: {publish_result.get('error')}")
        else:
            logger.error(f"Failed to list keys: {list_result.get('error')}")
    else:
        logger.error(f"Failed to create key: {create_result.get('error')}")
    
    return {"ipns_examples_completed": True}

async def main():
    """Run the example script."""
    parser = argparse.ArgumentParser(description="Advanced IPFS Operations Example")
    parser.add_argument("--start-api", action="store_true", help="Start the API server")
    parser.add_argument("--run-examples", action="store_true", help="Run the example operations")
    parser.add_argument("--port", type=int, default=8000, help="Port for the API server")
    args = parser.parse_args()
    
    if not imports_succeeded:
        logger.error("Required modules could not be imported. Exiting...")
        sys.exit(1)
    
    if args.run_examples:
        logger.info("Running example operations...")
        try:
            # Run examples
            await run_dht_example()
            await run_dag_example()
            await run_ipns_example()
            
            logger.info("All examples completed successfully!")
        except Exception as e:
            logger.error(f"Error running examples: {e}", exc_info=True)
    
    if args.start_api:
        logger.info(f"Starting API server on port {args.port}...")
        app = setup_api()
        
        # Run the API server
        uvicorn.run(app, host="0.0.0.0", port=args.port)
    
    if not args.run_examples and not args.start_api:
        logger.info("No actions specified. Use --start-api to start the API server or --run-examples to run examples.")
        parser.print_help()

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
