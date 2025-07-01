#!/usr/bin/env python3
"""
FINAL MCP SERVER - Simplified Version
=====================================

A simplified, unified MCP server that works reliably with the virtual environment.
This serves as the definitive entrypoint for Docker and CI/CD.
"""

import os
import sys
import json
import logging
import asyncio
import argparse
import traceback
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("final_mcp_server.log", mode='w'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("final-mcp")

# Constants
__version__ = "2.0.0-final"
DEFAULT_PORT = 9998
DEFAULT_HOST = "0.0.0.0"

# ============================================================================
# SIMPLIFIED IPFS MOCK FOR TESTING
# ============================================================================

class SimplifiedIPFSKit:
    """Simplified IPFS Kit for reliable operation"""
    
    def __init__(self, mock_mode=True):
        self.mock_mode = mock_mode
        logger.info(f"Initialized SimplifiedIPFSKit (mock_mode={mock_mode})")
    
    async def add(self, content: Union[str, bytes], **kwargs) -> str:
        """Add content to IPFS (mock)"""
        import hashlib
        if isinstance(content, str):
            content = content.encode('utf-8')
        hash_obj = hashlib.sha256(content)
        cid = f"Qm{hash_obj.hexdigest()[:44]}"
        logger.info(f"Mock IPFS add: {len(content)} bytes -> {cid}")
        return cid
    
    async def cat(self, cid: str, **kwargs) -> bytes:
        """Get content from IPFS (mock)"""
        content = f"Mock content for CID: {cid} (timestamp: {asyncio.get_event_loop().time()})".encode('utf-8')
        logger.info(f"Mock IPFS cat: {cid} -> {len(content)} bytes")
        return content
    
    async def pin_add(self, cid: str, **kwargs) -> Dict[str, Any]:
        """Pin content (mock)"""
        result = {"Pins": [cid]}
        logger.info(f"Mock IPFS pin add: {cid}")
        return result
    
    async def pin_rm(self, cid: str, **kwargs) -> Dict[str, Any]:
        """Unpin content (mock)"""
        result = {"Pins": [cid]}
        logger.info(f"Mock IPFS pin rm: {cid}")
        return result
    
    async def version(self, **kwargs) -> Dict[str, Any]:
        """Get IPFS version (mock)"""
        result = {
            "Version": "0.20.0-mock",
            "Commit": "mock-commit",
            "Repo": "15",
            "System": "amd64/linux",
            "Golang": "go1.19.1"
        }
        logger.info("Mock IPFS version called")
        return result

# Global IPFS instance
ipfs_kit = SimplifiedIPFSKit()

# ============================================================================
# MCP TOOL IMPLEMENTATIONS
# ============================================================================

async def ipfs_add_tool(content: str, **kwargs) -> Dict[str, Any]:
    """Add content to IPFS"""
    try:
        cid = await ipfs_kit.add(content)
        return {
            "success": True,
            "cid": cid,
            "size": len(content.encode('utf-8'))
        }
    except Exception as e:
        logger.error(f"IPFS add error: {e}")
        return {"success": False, "error": str(e)}

async def ipfs_cat_tool(cid: str, **kwargs) -> Dict[str, Any]:
    """Get content from IPFS"""
    try:
        content = await ipfs_kit.cat(cid)
        return {
            "success": True,
            "content": content.decode('utf-8', errors='replace'),
            "size": len(content)
        }
    except Exception as e:
        logger.error(f"IPFS cat error: {e}")
        return {"success": False, "error": str(e)}

async def ipfs_pin_add_tool(cid: str, **kwargs) -> Dict[str, Any]:
    """Pin content in IPFS"""
    try:
        result = await ipfs_kit.pin_add(cid)
        return {"success": True, "result": result}
    except Exception as e:
        logger.error(f"IPFS pin add error: {e}")
        return {"success": False, "error": str(e)}

async def ipfs_pin_rm_tool(cid: str, **kwargs) -> Dict[str, Any]:
    """Unpin content in IPFS"""
    try:
        result = await ipfs_kit.pin_rm(cid)
        return {"success": True, "result": result}
    except Exception as e:
        logger.error(f"IPFS pin rm error: {e}")
        return {"success": False, "error": str(e)}

async def ipfs_version_tool(**kwargs) -> Dict[str, Any]:
    """Get IPFS version information"""
    try:
        result = await ipfs_kit.version()
        return {"success": True, "version": result}
    except Exception as e:
        logger.error(f"IPFS version error: {e}")
        return {"success": False, "error": str(e)}

# ============================================================================
# FASTAPI SERVER
# ============================================================================

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import JSONResponse
    import uvicorn
    
    app = FastAPI(
        title="Final MCP Server",
        description="Unified IPFS MCP Server",
        version=__version__
    )
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint"""
        return {
            "status": "healthy",
            "version": __version__,
            "timestamp": asyncio.get_event_loop().time()
        }
    
    @app.get("/")
    async def root():
        """Root endpoint"""
        return {
            "message": "Final MCP Server",
            "version": __version__,
            "endpoints": [
                "/health",
                "/mcp/tools",
                "/ipfs/add",
                "/ipfs/cat/{cid}",
                "/ipfs/pin/add/{cid}",
                "/ipfs/pin/rm/{cid}",
                "/ipfs/version"
            ]
        }
    
    @app.get("/mcp/tools")
    async def list_tools():
        """List available MCP tools"""
        return {
            "tools": [
                {
                    "name": "ipfs_add",
                    "description": "Add content to IPFS",
                    "parameters": {"content": "string"}
                },
                {
                    "name": "ipfs_cat",
                    "description": "Get content from IPFS",
                    "parameters": {"cid": "string"}
                },
                {
                    "name": "ipfs_pin_add",
                    "description": "Pin content in IPFS",
                    "parameters": {"cid": "string"}
                },
                {
                    "name": "ipfs_pin_rm",
                    "description": "Unpin content in IPFS",
                    "parameters": {"cid": "string"}
                },
                {
                    "name": "ipfs_version",
                    "description": "Get IPFS version",
                    "parameters": {}
                }
            ]
        }
    
    @app.post("/ipfs/add")
    async def ipfs_add_endpoint(request: Dict[str, Any]):
        """Add content to IPFS endpoint"""
        content = request.get("content", "")
        if not content:
            raise HTTPException(status_code=400, detail="Content is required")
        
        result = await ipfs_add_tool(content)
        if result.get("success"):
            return result
        else:
            raise HTTPException(status_code=500, detail=result.get("error"))
    
    @app.get("/ipfs/cat/{cid}")
    async def ipfs_cat_endpoint(cid: str):
        """Get content from IPFS endpoint"""
        result = await ipfs_cat_tool(cid)
        if result.get("success"):
            return result
        else:
            raise HTTPException(status_code=500, detail=result.get("error"))
    
    @app.post("/ipfs/pin/add/{cid}")
    async def ipfs_pin_add_endpoint(cid: str):
        """Pin content endpoint"""
        result = await ipfs_pin_add_tool(cid)
        if result.get("success"):
            return result
        else:
            raise HTTPException(status_code=500, detail=result.get("error"))
    
    @app.delete("/ipfs/pin/rm/{cid}")
    async def ipfs_pin_rm_endpoint(cid: str):
        """Unpin content endpoint"""
        result = await ipfs_pin_rm_tool(cid)
        if result.get("success"):
            return result
        else:
            raise HTTPException(status_code=500, detail=result.get("error"))
    
    @app.get("/ipfs/version")
    async def ipfs_version_endpoint():
        """Get IPFS version endpoint"""
        result = await ipfs_version_tool()
        if result.get("success"):
            return result
        else:
            raise HTTPException(status_code=500, detail=result.get("error"))

except ImportError as e:
    logger.error(f"Failed to import FastAPI: {e}")
    app = None

# ============================================================================
# COMMAND LINE INTERFACE
# ============================================================================

def create_parser():
    """Create command line argument parser"""
    parser = argparse.ArgumentParser(
        description="Final MCP Server - Unified IPFS MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s                          # Start server with defaults
    %(prog)s --port 8080              # Start on port 8080
    %(prog)s --host 127.0.0.1         # Start on localhost only
    %(prog)s --debug                  # Enable debug logging
        """
    )
    
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"Host to bind to (default: {DEFAULT_HOST})"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Port to bind to (default: {DEFAULT_PORT})"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}"
    )
    
    return parser

def main():
    """Main entry point"""
    parser = create_parser()
    args = parser.parse_args()
    
    # Set logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")
    
    logger.info(f"🚀 Final MCP Server v{__version__}")
    logger.info("=" * 50)
    
    if app is None:
        logger.error("❌ FastAPI not available, cannot start server")
        return 1
    
    try:
        # Create PID file
        pid_file = Path("final_mcp_server.pid")
        pid_file.write_text(str(os.getpid()))
        
        logger.info(f"🌐 Starting server on {args.host}:{args.port}")
        logger.info(f"📋 PID: {os.getpid()}")
        logger.info(f"📝 Log file: final_mcp_server.log")
        logger.info(f"🔗 Health check: http://{args.host}:{args.port}/health")
        
        # Start server
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            log_level="debug" if args.debug else "info",
            access_log=args.debug
        )
        
    except KeyboardInterrupt:
        logger.info("👋 Server stopped by user")
        return 0
    except Exception as e:
        logger.error(f"❌ Server failed: {e}")
        logger.error(traceback.format_exc())
        return 1
    finally:
        # Cleanup
        try:
            if pid_file.exists():
                pid_file.unlink()
                logger.info("🧹 Cleaned up PID file")
        except Exception as e:
            logger.error(f"⚠️ Error during cleanup: {e}")
        
        logger.info("👋 Final MCP Server shutdown complete")

if __name__ == "__main__":
    sys.exit(main())
