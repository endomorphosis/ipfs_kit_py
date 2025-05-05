#!/usr/bin/env python3
"""
Direct runner for MCP server with IPFS tool integration
This script directly runs the MCP server with all tools properly registered 
without relying on importing a module.
"""

import os
import sys
import logging
import argparse
import ipfs_kit_py
from ipfs_kit_py.mcp.ipfs_extensions import register_ipfs_tools
from ipfs_kit_py.mcp.controllers.ipfs_controller import IPFSController
import ipfs_kit_py.mcp.models.ipfs_model as ipfs_model

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("mcp_direct_server.log")
    ]
)
logger = logging.getLogger("direct-mcp-runner")

# Set up command line arguments
parser = argparse.ArgumentParser(description="Run MCP server with IPFS tool integration")
parser.add_argument("--host", default="127.0.0.1", help="Host to bind the server to")
parser.add_argument("--port", type=int, default=3001, help="Port to bind the server to")
parser.add_argument("--debug", action="store_true", help="Enable debug logging")
args = parser.parse_args()

def register_tools(mcp_server):
    """Register all IPFS and FS tools with the MCP server"""
    logger.info("Registering IPFS tools with MCP server...")
    
    # Initialize IPFS model
    ipfs = ipfs_model.IPFSModel()
    
    # Register IPFS controller
    controller = IPFSController(ipfs)
    
    # Register IPFS tools
    register_ipfs_tools(mcp_server, controller, ipfs)
    
    # Register filesystem tools
    try:
        from fs_journal_tools import register_fs_journal_tools
        register_fs_journal_tools(mcp_server)
        logger.info("✅ Successfully registered FS Journal tools")
    except ImportError:
        logger.warning("⚠️ FS Journal tools not available")
    
    # Register multi-backend tools
    try:
        from multi_backend_fs_integration import register_multi_backend_tools
        register_multi_backend_tools(mcp_server)
        logger.info("✅ Successfully registered Multi-Backend tools")
    except ImportError:
        logger.warning("⚠️ Multi-Backend tools not available")
    
    logger.info("✅ Tool registration complete")

def main():
    """Run the MCP server with all tools registered"""
    logger.info(f"Starting Direct MCP Server on {args.host}:{args.port}")
    
    try:
        # Import MCP server components
        from mcp.server.fastmcp import FastMCP, Context
        from starlette.applications import Starlette
        from starlette.routing import Route
        from starlette.responses import JSONResponse, Response
        from starlette.middleware.cors import CORSMiddleware
        import uvicorn
        
        # Create MCP server instance
        server = FastMCP()
        
        # Register tools
        register_tools(server)
        
        # Create Starlette app
        app = Starlette(debug=args.debug)
        
        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"]
        )
        
        # Setup basic routes
        @app.route("/")
        async def homepage(request):
            return Response("MCP Server is running", media_type="text/plain")
        
        @app.route("/health")
        async def health(request):
            return JSONResponse({"status": "ok"})
        
        # Setup JSON-RPC endpoint
        @app.route("/jsonrpc", methods=["POST"])
        async def handle_jsonrpc(request):
            req_json = await request.json()
            req_id = req_json.get("id", 0)
            
            try:
                result = await server.handle_jsonrpc(req_json)
                return JSONResponse(result)
            except Exception as e:
                logger.error(f"JSON-RPC request handling error: {e}")
                return JSONResponse({
                    'jsonrpc': '2.0',
                    'error': {'code': -32603, 'message': f'Internal error: {str(e)}'},
                    'id': req_id
                })
        
        logger.info(f"Starting server on {args.host}:{args.port}")
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            log_level="debug" if args.debug else "info"
        )
    
    except ImportError as e:
        logger.error(f"Failed to import required modules: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error starting server: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
