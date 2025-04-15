"""
Advanced IPFS Operations Integration Module

This module integrates the advanced IPFS operations into the MCP server:
- Registers the advanced IPFS backend as the default IPFS implementation
- Sets up all the advanced API endpoints
- Provides utilities for working with advanced IPFS features

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).
"""

import logging
import asyncio
from typing import Optional, Dict, Any

from fastapi import FastAPI

from ipfs_kit_py.mcp.storage_manager.backends.ipfs_advanced_backend import IPFSAdvancedBackend
from ipfs_kit_py.mcp.storage_manager.backends.ipfs_advanced_router import create_advanced_ipfs_router

# Configure logging
logger = logging.getLogger(__name__)


def setup_advanced_ipfs_operations(app: FastAPI, backend_manager: Any) -> None:
    """
    Set up advanced IPFS operations in the MCP server.
    
    Args:
        app: FastAPI application
        backend_manager: Storage backend manager
    """
    logger.info("Setting up advanced IPFS operations")
    
    # Check if the IPFS backend exists
    ipfs_backend = backend_manager.get_backend("ipfs")
    if not ipfs_backend:
        logger.warning("IPFS backend not found, skipping advanced operations setup")
        return
    
    # Replace IPFS backend with advanced implementation
    try:
        # Get current configuration
        resources = ipfs_backend.resources
        metadata = ipfs_backend.metadata
        
        # Create advanced backend with same configuration
        advanced_backend = IPFSAdvancedBackend(resources, metadata)
        
        # Replace in backend manager
        backend_manager.add_backend("ipfs", advanced_backend)
        
        logger.info("IPFS backend upgraded to advanced implementation")
    except Exception as e:
        logger.error(f"Failed to upgrade IPFS backend to advanced implementation: {e}")
        logger.info("Continuing with standard IPFS backend")
    
    # Create advanced API endpoints
    try:
        create_advanced_ipfs_router(app, backend_manager)
        logger.info("Advanced IPFS API endpoints registered")
    except Exception as e:
        logger.error(f"Failed to register advanced IPFS API endpoints: {e}")


async def verify_ipfs_advanced_operations(backend_manager: Any) -> Dict[str, Any]:
    """
    Verify that advanced IPFS operations are working.
    
    Args:
        backend_manager: Storage backend manager
        
    Returns:
        Dict with verification results
    """
    logger.info("Verifying advanced IPFS operations")
    
    results = {
        "success": False,
        "operations_tested": 0,
        "operations_succeeded": 0,
        "operations_failed": 0,
        "failures": []
    }
    
    # Get IPFS backend
    ipfs_backend = backend_manager.get_backend("ipfs")
    if not ipfs_backend:
        results["error"] = "IPFS backend not found"
        return results
    
    # Check if we have the advanced implementation
    is_advanced = isinstance(ipfs_backend, IPFSAdvancedBackend)
    results["advanced_implementation"] = is_advanced
    
    # Define operations to test
    operations = [
        # Basic operations (should work with any implementation)
        {"name": "version", "method": "ipfs_version", "args": [], "kwargs": {}},
        {"name": "pin_ls", "method": "pin_ls", "args": [], "kwargs": {}},
        
        # Advanced operations (only work with advanced implementation)
        {"name": "swarm_peers", "method": "ipfs_swarm_peers", "args": [], "kwargs": {}},
        {"name": "files_stat", "method": "ipfs_files_stat", "args": ["/"], "kwargs": {}},
        {"name": "key_list", "method": "ipfs_key_list", "args": [], "kwargs": {}}
    ]
    
    # Run tests
    for op in operations:
        try:
            # Update counter
            results["operations_tested"] += 1
            
            # Skip advanced operations if not using advanced implementation
            if not is_advanced and op["name"] not in ["version", "pin_ls"]:
                logger.info(f"Skipping advanced operation {op['name']} with standard implementation")
                continue
            
            # Get method
            method_name = op["method"]
            method = getattr(ipfs_backend, method_name, None)
            
            if method is None:
                results["operations_failed"] += 1
                results["failures"].append({
                    "operation": op["name"],
                    "error": f"Method {method_name} not found"
                })
                continue
            
            # Execute operation
            logger.info(f"Testing operation: {op['name']}")
            result = await method(*op["args"], **op["kwargs"])
            
            # Check result
            if result.get("success", False):
                results["operations_succeeded"] += 1
                logger.info(f"Operation {op['name']} succeeded")
            else:
                results["operations_failed"] += 1
                results["failures"].append({
                    "operation": op["name"],
                    "error": result.get("error", "Unknown error"),
                    "result": result
                })
                logger.warning(f"Operation {op['name']} failed: {result.get('error', 'Unknown error')}")
        
        except Exception as e:
            results["operations_failed"] += 1
            results["failures"].append({
                "operation": op["name"],
                "error": str(e)
            })
            logger.error(f"Error testing operation {op['name']}: {e}")
    
    # Set overall success
    results["success"] = results["operations_failed"] == 0
    
    if results["success"]:
        logger.info("All advanced IPFS operations verified successfully")
    else:
        logger.warning(f"{results['operations_failed']} out of {results['operations_tested']} operations failed")
    
    return results


async def setup_ipfs_dht(ipfs_backend: Any) -> Dict[str, Any]:
    """
    Set up and verify DHT functionality in IPFS.
    
    Args:
        ipfs_backend: IPFS backend instance
        
    Returns:
        Dict with setup results
    """
    logger.info("Setting up IPFS DHT functionality")
    
    results = {
        "success": False,
        "operations": {}
    }
    
    # Check if we have the advanced implementation
    is_advanced = isinstance(ipfs_backend, IPFSAdvancedBackend)
    if not is_advanced:
        results["error"] = "Advanced IPFS implementation required for DHT operations"
        return results
    
    # Get node ID
    try:
        # Use the id command to get our peer ID
        id_result = await ipfs_backend._execute_ipfs_command(["id"])
        if id_result.get("success", False):
            peer_id = id_result.get("ID", "")
            results["peer_id"] = peer_id
            results["operations"]["id"] = True
        else:
            results["operations"]["id"] = False
            results["error"] = id_result.get("error", "Failed to get node ID")
            return results
    except Exception as e:
        results["operations"]["id"] = False
        results["error"] = f"Error getting node ID: {e}"
        return results
    
    # Test DHT query operation
    try:
        query_result = await ipfs_backend.ipfs_dht_query(peer_id)
        results["operations"]["dht_query"] = query_result.get("success", False)
        
        if not query_result.get("success", False):
            results["error"] = query_result.get("error", "DHT query failed")
            return results
    except Exception as e:
        results["operations"]["dht_query"] = False
        results["error"] = f"Error in DHT query: {e}"
        return results
    
    # Attempt to connect to some bootstrap nodes to populate DHT
    try:
        # First get list of bootstrap nodes
        bootstrap_result = await ipfs_backend._execute_ipfs_command(["bootstrap", "list"])
        if bootstrap_result.get("success", False):
            bootstrap_peers = bootstrap_result.get("Peers", [])
            
            # Try to connect to a few bootstrap nodes
            connected = 0
            for peer in bootstrap_peers[:3]:  # Just try the first 3
                connect_result = await ipfs_backend.ipfs_swarm_connect(peer)
                if connect_result.get("success", False):
                    connected += 1
            
            results["operations"]["bootstrap_connect"] = connected > 0
            
            if connected == 0:
                results["warning"] = "Could not connect to any bootstrap nodes"
        else:
            results["operations"]["bootstrap_connect"] = False
            results["warning"] = "Failed to get bootstrap list"
    except Exception as e:
        results["operations"]["bootstrap_connect"] = False
        results["warning"] = f"Error connecting to bootstrap nodes: {e}"
    
    # Set overall success
    success = all(op for op_name, op in results["operations"].items() if op_name != "bootstrap_connect")
    results["success"] = success
    
    if success:
        logger.info("IPFS DHT functionality set up successfully")
    else:
        logger.warning("Failed to set up IPFS DHT functionality")
    
    return results