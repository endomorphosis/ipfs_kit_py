"""
IPFS Router for the MCP server.

This module provides a FastAPI router for all IPFS advanced operations controllers.
"""

import logging
from fastapi import APIRouter

from ipfs_kit_py.mcp.controllers.ipfs.dht_controller import DHTController
from ipfs_kit_py.mcp.controllers.ipfs.dag_controller import DAGController
from ipfs_kit_py.mcp.controllers.ipfs.ipns_controller import IPNSController

# Configure logger
logger = logging.getLogger(__name__)

def create_ipfs_router():
    """
    Create a FastAPI router for advanced IPFS operations.
    
    Returns:
        FastAPI router with all IPFS endpoints registered
    """
    # Create the root router
    router = APIRouter(prefix="/api/v0")
    
    # Create controller instances
    dht_controller = DHTController()
    dag_controller = DAGController()
    ipns_controller = IPNSController()
    
    # Register controller routes
    logger.info("Registering DHT controller routes")
    dht_controller.register_routes(router)
    
    logger.info("Registering DAG controller routes")
    dag_controller.register_routes(router)
    
    logger.info("Registering IPNS controller routes")
    ipns_controller.register_routes(router)
    
    logger.info("All IPFS advanced operations routes registered")
    
    return router

def register_with_app(app):
    """
    Register the IPFS router with a FastAPI app.
    
    Args:
        app: FastAPI application to register with
    """
    router = create_ipfs_router()
    app.include_router(router)
    logger.info("IPFS advanced operations router registered with app")

def register_with_mcp(mcp_server):
    """
    Register the IPFS router with an MCP server.
    
    Args:
        mcp_server: MCP server instance to register with
    """
    # For FastMCP, we need to get the underlying FastAPI app
    if hasattr(mcp_server, 'app'):
        app = mcp_server.app
        register_with_app(app)
        logger.info("IPFS advanced operations router registered with MCP server")
    else:
        logger.error("Could not register IPFS router with MCP server: no app attribute found")
