#!/usr/bin/env python3
"""
MCP Server AI/ML Integration

This module integrates the AI/ML components with the MCP server.
It provides middleware and route handlers for the AI/ML functionality.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("mcp-ai-integration")

def integrate_ai_ml_with_mcp_server(app: Any, get_current_user=None) -> bool:
    """
    Integrates AI/ML components with the MCP server.
    
    Args:
        app: The FastAPI or Starlette application instance
        get_current_user: Optional dependency for authenticated endpoints
        
    Returns:
        True if integration was successful, False otherwise
    """
    logger.info("Integrating AI/ML components with MCP server...")
    
    try:
        # Import the AI/ML router
        from ipfs_kit_py.mcp.ai.api_router import create_ai_api_router
        
        # Import AI/ML components
        try:
            from ipfs_kit_py.mcp.ai.model_registry import get_instance as get_model_registry
            model_registry = get_model_registry()
            logger.info("Successfully imported Model Registry")
        except ImportError:
            logger.warning("Model Registry not available")
            model_registry = None
        
        # Create the AI/ML API router
        ai_router = create_ai_api_router(
            model_registry=model_registry,
            get_current_user=get_current_user
        )
        
        # Check if the app has the include_router method (FastAPI)
        if hasattr(app, 'include_router'):
            # FastAPI app
            app.include_router(ai_router, prefix="/api/v0/ai")
            logger.info("Added AI/ML router to FastAPI app at /api/v0/ai")
        elif hasattr(app, 'routes'):
            # Starlette app
            from starlette.routing import Mount
            from starlette.applications import Starlette
            
            # Create a sub-application for the AI/ML routes
            ai_app = Starlette()
            ai_app.routes = ai_router.routes
            
            # Mount the sub-application
            app.routes.append(Mount("/api/v0/ai", app=ai_app))
            logger.info("Mounted AI/ML router to Starlette app at /api/v0/ai")
        else:
            logger.error("Unsupported application type. Cannot add AI/ML router.")
            return False
        
        logger.info("AI/ML integration completed successfully")
        return True
    
    except Exception as e:
        logger.error(f"Error integrating AI/ML components: {e}", exc_info=True)
        return False

# Entry point for CLI usage
if __name__ == "__main__":
    print("This module should be imported by the MCP server, not run directly.")
    sys.exit(1)