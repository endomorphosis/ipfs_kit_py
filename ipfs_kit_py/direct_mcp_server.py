"""
This module serves as the primary entry point for the MCP server as mentioned in the roadmap.
It implements a FastAPI server with endpoints for all MCP components including storage backends,
authentication, and now AI/ML capabilities.

Updated with AI/ML integration based on MCP Roadmap Phase 2: AI/ML Integration (Q4 2025).
"""

import os
import sys
import logging
import argparse
import uvicorn
from pathlib import Path
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger("mcp_server")

# Try to import AI/ML components
try:
    from ipfs_kit_py.mcp.ai.ai_ml_integrator import get_instance as get_ai_ml_integrator
    HAS_AI_ML = True
    logger.info("AI/ML integration available")
except ImportError:
    HAS_AI_ML = False
    logger.info("AI/ML integration not available")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan event handler.
    
    This function handles startup and shutdown events for the FastAPI app.
    """
    # Startup
    logger.info("MCP server starting up")
    
    # Add any additional startup here
    
    yield
    
    # Shutdown
    logger.info("MCP server shutting down")
    
    # Add any additional cleanup here


def create_app(config_path=None):
    """
    Create and configure the FastAPI application.
    
    Args:
        config_path: Optional path to configuration file
        
    Returns:
        Configured FastAPI application
    """
    # Create app with lifespan handler
    app = FastAPI(
        title="IPFS Kit MCP Server",
        description="Model-Controller-Persistence (MCP) server with AI/ML capabilities",
        version="0.1.0",
        lifespan=lifespan
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Root endpoint
    @app.get("/")
    async def root():
        """Root endpoint with server info."""
        return {
            "name": "IPFS Kit MCP Server",
            "version": "0.1.0",
            "status": "running",
            "features": {
                "ai_ml": HAS_AI_ML
            }
        }
    
    # Health check endpoint
    @app.get("/health")
    async def health():
        """Health check endpoint."""
        import time
        return {
            "status": "healthy",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
    
    # Add main API router
    api_router = APIRouter(prefix="/api/v0")
    app.include_router(api_router)
    
    # If AI/ML is available, initialize and register it
    if HAS_AI_ML:
        try:
            ai_ml_integrator = get_ai_ml_integrator()
            ai_ml_integrator.initialize()
            ai_ml_integrator.register_with_server(app, prefix="/api/v0/ai")
            logger.info("AI/ML components registered with server")
        except Exception as e:
            logger.error(f"Error initializing AI/ML components: {e}")
    
    return app


def parse_args():
    """
    Parse command line arguments.
    
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(description="IPFS Kit MCP Server")
    
    parser.add_argument(
        "--host", 
        type=str, 
        default="0.0.0.0",
        help="Host to bind server to"
    )
    
    parser.add_argument(
        "--port", 
        type=int, 
        default=8000, 
        help="Port to bind server to"
    )
    
    parser.add_argument(
        "--config", 
        type=str, 
        help="Path to configuration file"
    )
    
    parser.add_argument(
        "--log-level", 
        type=str, 
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Logging level"
    )
    
    return parser.parse_args()


def main():
    """Run the MCP server."""
    # Parse command line arguments
    args = parse_args()
    
    # Configure logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Create app
    app = create_app(args.config)
    
    # Run server
    uvicorn.run(
        app, 
        host=args.host, 
        port=args.port,
        log_level=args.log_level.lower()
    )


if __name__ == "__main__":
    main()
