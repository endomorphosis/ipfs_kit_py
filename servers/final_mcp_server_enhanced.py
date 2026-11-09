#!/usr/bin/env python3
"""
FINAL MCP SERVER - PRODUCTION READY VERSION
===========================================

The definitive, production-ready MCP server for ipfs_kit_py.
This is the ONLY server needed for Docker, CI/CD, and VS Code integration.

Key Features:
- FastAPI-based REST API
- Mock IPFS implementation for reliable testing
- Comprehensive error handling and logging
- Health monitoring and metrics
- Command-line interface
- Docker and CI/CD ready
- VS Code MCP integration compatible
"""

import os
import sys
import json
import logging
import anyio
import argparse
import traceback
import hashlib
import signal
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from datetime import datetime

# Configure comprehensive logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("final_mcp_server.log", mode='w'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("final-mcp")

# Server metadata
__version__ = "2.1.0"
__author__ = "ipfs_kit_py"
__description__ = "Production-ready MCP server for IPFS operations"

# Global state
server_start_time = datetime.now()
request_count = 0

import ipfshttpclient
import requests
from ipfs_kit_py.install_lassie import install_lassie
from ipfs_kit_py.install_ipfs import install_ipfs

# Configure comprehensive logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("final_mcp_server.log", mode='w'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("final-mcp")

# Server metadata
__version__ = "2.1.0"
__author__ = "ipfs_kit_py"
__description__ = "Production-ready MCP server for IPFS operations"

# Global state
server_start_time = datetime.now()
request_count = 0

# Global IPFS and Lassie client instances
ipfs = None
lassie_installer = None
lassie_client = None

IPFS_PATH = os.path.join(os.path.expanduser("~"), ".ipfs")
IPFS_BIN_PATH = shutil.which("ipfs") or "ipfs"

async def _check_and_install_ipfs_daemon():
    """
    Checks for IPFS daemon and installs it if not found.
    """
    global IPFS_BIN_PATH

    existing = shutil.which("ipfs")
    if existing:
        IPFS_BIN_PATH = existing
        logger.info(f"✅ IPFS binary found at {IPFS_BIN_PATH}")
        return

    logger.warning("IPFS binary not found. Attempting to install Kubo via ipfs_kit_py installer...")
    try:
        installer = install_ipfs(metadata={"role": "leecher"})
        installer.install_ipfs_daemon()

        # Prefer the installer-managed bin directory if present.
        import ipfs_kit_py as _ipfs_kit_py

        pkg_dir = Path(_ipfs_kit_py.__file__).resolve().parent
        bin_dir = pkg_dir / "bin"
        candidate = bin_dir / ("ipfs.exe" if sys.platform == "win32" else "ipfs")
        if candidate.exists():
            IPFS_BIN_PATH = str(candidate)
            os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"
            logger.info(f"✅ Installed IPFS binary at {IPFS_BIN_PATH}")
            return

        # Fallback: search PATH again.
        existing = shutil.which("ipfs")
        if existing:
            IPFS_BIN_PATH = existing
            logger.info(f"✅ Installed IPFS binary found at {IPFS_BIN_PATH}")
            return

        logger.error("❌ IPFS install attempted, but binary still not found")
    except Exception as e:
        logger.error(f"❌ Failed to install IPFS via installer: {e}")

async def _initialize_ipfs_repo():
    """
    Initializes IPFS repository if it doesn't exist.
    """
    if not Path(IPFS_PATH).is_dir():
        logger.info(f"IPFS_PATH {IPFS_PATH} does not exist. Creating...")
        Path(IPFS_PATH).mkdir(parents=True, exist_ok=True)

    if not (Path(IPFS_PATH) / "api").is_dir(): # Check for a common repo file/dir
        logger.warning("IPFS repository not initialized. Running ipfs init...")
        try:
            result = await anyio.run_process(
                [IPFS_BIN_PATH, "init"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            if result.returncode == 0:
                logger.info(f"✅ IPFS repository initialized: {result.stdout.decode().strip()}")
            else:
                logger.error(f"❌ Failed to initialize IPFS repository: {result.stderr.decode().strip()}")
        except Exception as e:
            logger.error(f"❌ Error running ipfs init: {e}")
    else:
        logger.info("✅ IPFS repository already initialized.")

async def _connect_to_ipfs():
    """
    Connects to the IPFS daemon with retries.
    """
    global ipfs
    retries = 5
    delay = 2
    for i in range(retries):
        try:
            # Start IPFS daemon if not running
            # This part needs to be robust enough not to fail if daemon is already running
            # or to handle its startup in a non-blocking way.
            # For simplicity, we'll just try to connect and assume it's handled externally or by previous steps.
            
            # Connect to IPFS daemon
            ipfs = ipfshttpclient.connect('/ip4/127.0.0.1/tcp/5001')
            ipfs.id() # Test connection
            logger.info("✅ Connected to IPFS daemon.")
            return
        except ipfshttpclient.exceptions.ConnectionError as e:
            logger.warning(f"Attempt {i+1}/{retries}: IPFS daemon connection failed: {e}")
            await anyio.sleep(delay)
        except Exception as e:
            logger.error(f"❌ Failed to connect to IPFS daemon: {e}")
            break
    logger.error("❌ All retries failed. Could not connect to IPFS daemon.")
    ipfs = None

# ============================================================================
# FASTAPI APPLICATION WITH ENHANCED FEATURES
# ============================================================================

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel, Field
    import uvicorn
    
    # Enhanced request models
    class AddRequest(BaseModel):
        content: str = Field(..., description="Content to add to IPFS")
        
        class Config:
            json_schema_extra = {
                "example": {"content": "Hello, IPFS!"}
            }
    
    class PinRequest(BaseModel):
        recursive: bool = Field(default=True, description="Pin recursively")
    
    # Create FastAPI application with comprehensive configuration
    app = FastAPI(
        title="Final MCP Server",
        description=__description__,
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json"
    )
    
    # Add CORS middleware for cross-origin requests
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Request counter middleware
    @app.middleware("http")
    async def count_requests(request: Request, call_next):
        global request_count
        request_count += 1
        response = await call_next(request)
        response.headers["X-Request-Count"] = str(request_count)
        return response
    
    # Error handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"❌ Unhandled error in {request.url.path}: {exc}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "message": str(exc),
                "path": str(request.url.path)
            }
        )
    
    # ========================================================================
    # API ENDPOINTS
    # ========================================================================
    
    @app.get("/", summary="Server Information")
    async def root():
        """Get server information and status"""
        return {
            "name": "Final MCP Server",
            "version": __version__,
            "description": __description__,
            "status": "running",
            "uptime": str(datetime.now() - server_start_time),
            "requests_served": request_count,
            "endpoints": {
                "health": "/health",
                "tools": "/mcp/tools", 
                "docs": "/docs",
                "ipfs": "/ipfs/*"
            }
        }
    
    @app.get("/health", summary="Health Check")
    async def health():
        """Comprehensive health check endpoint"""
        ipfs_status = "disconnected"
        ipfs_version_info = {}
        if ipfs:
            try:
                ipfs_version_info = ipfs.version()
                ipfs_status = "connected"
            except Exception as e:
                logger.warning(f"Could not get IPFS version: {e}")
                ipfs_status = "error"

        return {
            "status": "healthy",
            "version": __version__,
            "timestamp": datetime.now().isoformat(),
            "uptime": str(datetime.now() - server_start_time),
            "ipfs_connection": ipfs_status,
            "ipfs_version_info": ipfs_version_info,
            "system": {
                "python_version": sys.version,
                "platform": sys.platform
            }
        }
    
    @app.get("/mcp/tools", summary="List MCP Tools")
    async def list_tools():
        """List all available MCP tools"""
        return {
            "tools": [
                {
                    "name": "ipfs_add",
                    "description": "Add content to IPFS",
                    "method": "POST",
                    "endpoint": "/ipfs/add"
                },
                {
                    "name": "ipfs_cat", 
                    "description": "Get content from IPFS",
                    "method": "GET",
                    "endpoint": "/ipfs/cat/{cid}"
                },
                {
                    "name": "ipfs_pin_add",
                    "description": "Pin content in IPFS", 
                    "method": "POST",
                    "endpoint": "/ipfs/pin/add/{cid}"
                },
                {
                    "name": "ipfs_pin_rm",
                    "description": "Unpin content in IPFS",
                    "method": "DELETE", 
                    "endpoint": "/ipfs/pin/rm/{cid}"
                },
                {
                    "name": "ipfs_version",
                    "description": "Get IPFS version information",
                    "method": "GET",
                    "endpoint": "/ipfs/version"
                }
            ],
            "total_tools": 5,
            "server_version": __version__
        }
    
    @app.post("/ipfs/add", summary="Add Content to IPFS")
    async def add_content(request: AddRequest):
        """Add content to IPFS and return CID"""
        if not ipfs:
            raise HTTPException(status_code=503, detail="IPFS daemon not connected")
        try:
            # ipfshttpclient's add method expects bytes or a file-like object
            content_bytes = request.content.encode('utf-8')
            result = ipfs.add(content_bytes, pin=True)
            cid = result["Hash"]
            return {
                "success": True,
                "cid": cid,
                "size": len(content_bytes),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"❌ Add content failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/ipfs/cat/{cid}", summary="Get Content from IPFS")
    async def get_content(cid: str):
        """Retrieve content from IPFS by CID"""
        if not ipfs:
            raise HTTPException(status_code=503, detail="IPFS daemon not connected")
        try:
            content = ipfs.cat(cid)
            # content is a generator, so read it all
            full_content = b''.join(content)
            return {
                "success": True,
                "content": full_content.decode('utf-8', errors='replace'),
                "cid": cid,
                "size": len(full_content),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"❌ Get content failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/ipfs/pin/add/{cid}", summary="Pin Content")
    async def pin_content(cid: str, pin_request: PinRequest = PinRequest()):
        """Pin content in IPFS"""
        if not ipfs:
            raise HTTPException(status_code=503, detail="IPFS daemon not connected")
        try:
            result = ipfs.pin.add(cid)
            return {
                "success": True,
                "result": result,
                "cid": cid,
                "recursive": pin_request.recursive,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"❌ Pin content failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.delete("/ipfs/pin/rm/{cid}", summary="Unpin Content")
    async def unpin_content(cid: str):
        """Remove pin from content in IPFS"""
        if not ipfs:
            raise HTTPException(status_code=503, detail="IPFS daemon not connected")
        try:
            result = ipfs.pin.rm(cid)
            return {
                "success": True,
                "result": result,
                "cid": cid,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"❌ Unpin content failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/ipfs/version", summary="Get IPFS Version")
    async def get_ipfs_version():
        """Get IPFS version information"""
        if not ipfs:
            raise HTTPException(status_code=503, detail="IPFS daemon not connected")
        try:
            result = ipfs.version()
            return {
                "success": True,
                "version": result,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"❌ Get version failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/stats", summary="Server Statistics")
    async def get_stats():
        """Get detailed server statistics"""
        ipfs_stats = {}
        if ipfs:
            try:
                ipfs_stats = ipfs.stats.repo()
            except Exception as e:
                logger.warning(f"Could not get IPFS repo stats: {e}")

        return {
            "success": True,
            "ipfs_stats": ipfs_stats,
            "server": {
                "version": __version__,
                "uptime": str(datetime.now() - server_start_time),
                "requests_served": request_count,
                "start_time": server_start_time.isoformat()
            }
        }

    @app.get("/lassie/fetch/{cid}", summary="Fetch Content with Lassie")
    async def lassie_fetch_content(cid: str):
        """Fetch content using Lassie and return it."""
        if not lassie_client:
            raise HTTPException(status_code=503, detail="Lassie client not initialized")
        try:
            # Assuming Lassie daemon runs on default port 41443
            lassie_url = f"http://localhost:41443/ipfs/{cid}"
            response = lassie_client.get(lassie_url, timeout=30)
            response.raise_for_status()
            return {"success": True, "cid": cid, "content": response.content.decode('utf-8', errors='replace')}
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Lassie fetch failed for {cid}: {e}")
            raise HTTPException(status_code=500, detail=f"Lassie fetch failed: {e}")

except ImportError as e:
    logger.error(f"❌ FastAPI dependencies not available: {e}")
    logger.error("Please install: pip install fastapi uvicorn pydantic")
    app = None

# ============================================================================
# SIGNAL HANDLERS FOR GRACEFUL SHUTDOWN
# ============================================================================

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info(f"🛑 Received signal {signum}, shutting down gracefully...")
    # Cleanup PID file
    pid_file = Path("final_mcp_server.pid")
    if pid_file.exists():
        pid_file.unlink()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# ============================================================================
# COMMAND-LINE INTERFACE
# ============================================================================

def main():
    """Main entry point with comprehensive CLI"""
    parser = argparse.ArgumentParser(
        description="Final MCP Server - Production Ready IPFS MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  {sys.argv[0]} --port 9998 --debug          # Start in debug mode
  {sys.argv[0]} --host 0.0.0.0 --port 8080   # Bind to all interfaces
  {sys.argv[0]} --help                        # Show this help

Version: {__version__}
Author: {__author__}
        """
    )
    
    parser.add_argument(
        "--host", 
        default="0.0.0.0", 
        help="Host to bind (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", 
        type=int, 
        default=9998, 
        help="Port to bind (default: 9998)"
    )
    parser.add_argument(
        "--debug", 
        action="store_true", 
        help="Enable debug logging"
    )
    parser.add_argument(
        "--version", 
        action="version", 
        version=f"Final MCP Server {__version__}"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level (default: INFO)"
    )
    
    args = parser.parse_args()
    
    # Configure logging level
    log_level = logging.DEBUG if args.debug else getattr(logging, args.log_level)
    logging.getLogger().setLevel(log_level)
    
    # Startup banner
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                    🚀 FINAL MCP SERVER 🚀                    ║
║                                                              ║
║  Version: {__version__:<10}                                        ║
║  Host: {args.host:<15}                                     ║
║  Port: {args.port:<10}                                           ║
║  Debug: {str(args.debug):<10}                                    ║
║                                                              ║
║  📚 API Documentation: http://{args.host}:{args.port}/docs          ║
║  🏥 Health Check: http://{args.host}:{args.port}/health           ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    logger.info(f"🚀 Final MCP Server v{__version__} starting...")
    logger.info(f"📍 Binding to {args.host}:{args.port}")
    logger.info(f"🔍 Debug mode: {args.debug}")

    # Check and install IPFS daemon
    anyio.run(_check_and_install_ipfs_daemon)
    anyio.run(_initialize_ipfs_repo)
    anyio.run(_connect_to_ipfs)

    # Initialize Lassie installer and run installation/configuration
    global lassie_installer, lassie_client
    lassie_installer = install_lassie()
    logger.info("🚀 Lassie installer initialized.")
    
    if lassie_installer.install_lassie_daemon():
        logger.info("✅ Lassie daemon installed.")
        if lassie_installer.config_lassie():
            logger.info("✅ Lassie configured.")
            # Connect to Lassie daemon
            try:
                # Assuming Lassie daemon runs on default port 41443
                lassie_client = requests.Session()
                lassie_client.mount("http://", requests.adapters.HTTPAdapter(max_retries=3))
                lassie_client.mount("https://", requests.adapters.HTTPAdapter(max_retries=3))
                logger.info("✅ Lassie client initialized.")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Lassie client: {e}")
        else:
            logger.error("❌ Failed to configure Lassie.")
    else:
        logger.error("❌ Failed to install Lassie daemon.")
    
    if app is None:
        logger.error("❌ FastAPI not available - cannot start server")
        logger.error("💡 Install dependencies: pip install fastapi uvicorn pydantic")
        return 1
    
    try:
        # Write PID file for process management
        pid_file = Path("final_mcp_server.pid")
        pid_file.write_text(str(os.getpid()))
        logger.info(f"📝 PID file written: {pid_file.absolute()}")
        
        # Start the server
        logger.info("🎯 Server is ready to accept connections!")
        
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            log_level="debug" if args.debug else "info",
            access_log=True,
            reload=args.debug
        )
        
    except KeyboardInterrupt:
        logger.info("⏹️ Server stopped by user")
        return 0
    except Exception as e:
        logger.error(f"💥 Server error: {e}")
        logger.error(traceback.format_exc())
        return 1
    finally:
        # Cleanup
        pid_file = Path("final_mcp_server.pid")
        if pid_file.exists():
            pid_file.unlink()
            logger.info("🧹 Cleaned up PID file")

if __name__ == "__main__":
    sys.exit(main())
