"""
Security Dashboard Router Integration for MCP Server

This module integrates the security dashboard with the MCP server:
- Initializes the security analyzer 
- Registers the security dashboard routes

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).
"""

import logging
import asyncio
from fastapi import FastAPI, APIRouter

from ipfs_kit_py.mcp.auth.security_dashboard import router as security_router
from ipfs_kit_py.mcp.auth.security_dashboard import get_security_analyzer

logger = logging.getLogger(__name__)


async def initialize_security_dashboard():
    """Initialize the security dashboard analyzer."""
    analyzer = get_security_analyzer()
    await analyzer.start()
    logger.info("Security dashboard analyzer started")


async def shutdown_security_dashboard():
    """Shutdown the security dashboard analyzer."""
    analyzer = get_security_analyzer()
    await analyzer.stop()
    logger.info("Security dashboard analyzer stopped")


def setup_security_dashboard(app: FastAPI, prefix: str = "/api/v0"):
    """
    Set up the security dashboard with the FastAPI application.
    
    Args:
        app: FastAPI application
        prefix: API prefix
    """
    # Register the security dashboard router
    app.include_router(security_router, prefix=prefix)
    
    # Register startup and shutdown events
    @app.on_event("startup")
    async def startup_security_dashboard():
        asyncio.create_task(initialize_security_dashboard())
    
    @app.on_event("shutdown")
    async def shutdown_security_dashboard_task():
        await shutdown_security_dashboard()
    
    logger.info("Security dashboard setup complete")