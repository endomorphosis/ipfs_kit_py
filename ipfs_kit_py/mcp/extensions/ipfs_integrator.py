"""
Integration module for enhanced IPFS operations.

This module integrates the enhanced IPFS operations into the main MCP server.
"""

import logging
import os
import sys

from fastapi import FastAPI

# Configure logging
logger = logging.getLogger(__name__)


def integrate_enhanced_ipfs(app: FastAPI, api_prefix: str) -> bool:
    """
    Integrate enhanced IPFS operations into the main server.

    Args:
        app: The FastAPI application
        api_prefix: The API prefix for endpoints

    Returns:
        bool: True if integration was successful
    """
    try:
        # Import the enhanced IPFS router using relative import
        from .enhanced_ipfs import create_ipfs_router

        # Create and add the router
        enhanced_router = create_ipfs_router(api_prefix)
        app.include_router(enhanced_router)

        logger.info("Integrated enhanced IPFS operations")
        return True
    except Exception as e:
        logger.error(f"Error integrating enhanced IPFS operations: {e}")
        return False
