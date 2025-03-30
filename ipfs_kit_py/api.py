"""
FastAPI server for IPFS Kit.

This module provides a FastAPI server that exposes the High-Level API
for IPFS Kit over HTTP, enabling remote access to IPFS functionality.
"""

import os
import sys
import json
import base64
import logging
from typing import Dict, List, Optional, Union, Any

# Import FastAPI and related
try:
    import uvicorn
    from fastapi import FastAPI, HTTPException, Request, Response, Depends, Query
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel, Field
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    # Create placeholder class for type checking
    class BaseModel:
        pass
    class Field:
        pass

# Import IPFS Kit
try:
    # First try relative imports (when used as a package)
    from .high_level_api import IPFSSimpleAPI
    from .error import IPFSError
except ImportError:
    # For development/testing
    import os
    import sys
    # Add parent directory to path
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from ipfs_kit_py.high_level_api import IPFSSimpleAPI
    from ipfs_kit_py.error import IPFSError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Check if FastAPI is available
if not FASTAPI_AVAILABLE:
    logger.error("FastAPI not available. Please install with 'pip install fastapi uvicorn'")
    sys.exit(1)

# Create API models
class APIRequest(BaseModel):
    """API request model."""
    args: List[Any] = Field(default_factory=list, description="Positional arguments")
    kwargs: Dict[str, Any] = Field(default_factory=dict, description="Keyword arguments")

class ErrorResponse(BaseModel):
    """Error response model."""
    success: bool = Field(False, description="Operation success status")
    error: str = Field(..., description="Error message")
    error_type: str = Field(..., description="Error type")
    status_code: int = Field(..., description="HTTP status code")

# Initialize FastAPI app
app = FastAPI(
    title="IPFS Kit API",
    description="API for IPFS Kit with comprehensive IPFS functionality",
    version="0.1.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins in development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize IPFS Kit with default configuration
# This can be customized with environment variables or config file
ipfs_api = IPFSSimpleAPI()

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}

# API method dispatcher
@app.post("/api/{method_name}")
async def api_method(method_name: str, request: APIRequest):
    """
    Dispatch API method call.
    
    Args:
        method_name: Name of the method to call
        request: API request with arguments
        
    Returns:
        API response
    """
    try:
        # Call method on IPFS API
        result = ipfs_api(method_name, *request.args, **request.kwargs)
        
        # If result is bytes, encode as base64
        if isinstance(result, bytes):
            return {
                "success": True,
                "data": base64.b64encode(result).decode('utf-8'),
                "encoding": "base64"
            }
            
        return result
    except IPFSError as e:
        logger.error(f"IPFS error in method {method_name}: {str(e)}")
        return ErrorResponse(
            error=str(e),
            error_type=type(e).__name__,
            status_code=400
        )
    except Exception as e:
        logger.exception(f"Unexpected error in method {method_name}: {str(e)}")
        return ErrorResponse(
            error=str(e),
            error_type=type(e).__name__,
            status_code=500
        )

# File upload endpoint
@app.post("/api/upload")
async def upload_file(request: Request):
    """
    Upload file to IPFS.
    
    Args:
        request: FastAPI request with file content
        
    Returns:
        API response with CID
    """
    try:
        form = await request.form()
        file = form.get("file")
        
        if not file:
            raise ValueError("No file provided")
            
        # Get optional parameters
        pin = form.get("pin", "true").lower() == "true"
        wrap_with_directory = form.get("wrap_with_directory", "false").lower() == "true"
        
        # Add file to IPFS
        result = ipfs_api.add(
            await file.read(),
            pin=pin,
            wrap_with_directory=wrap_with_directory
        )
        
        return result
    except Exception as e:
        logger.exception(f"Error uploading file: {str(e)}")
        return ErrorResponse(
            error=str(e),
            error_type=type(e).__name__,
            status_code=500
        )

# File download endpoint
@app.get("/api/download/{cid}")
async def download_file(cid: str, filename: Optional[str] = None):
    """
    Download file from IPFS.
    
    Args:
        cid: Content identifier
        filename: Optional filename for download
        
    Returns:
        File content with appropriate headers
    """
    try:
        # Get content from IPFS
        content = ipfs_api.get(cid)
        
        # Set filename if provided, otherwise use CID
        content_disposition = f"attachment; filename=\"{filename or cid}\""
        
        return Response(
            content=content,
            media_type="application/octet-stream",
            headers={"Content-Disposition": content_disposition}
        )
    except Exception as e:
        logger.exception(f"Error downloading file: {str(e)}")
        return ErrorResponse(
            error=str(e),
            error_type=type(e).__name__,
            status_code=500
        )

# Configuration endpoint
@app.get("/api/config")
async def get_config():
    """Get server configuration."""
    # Return safe subset of configuration
    safe_config = {
        "role": ipfs_api.config.get("role"),
        "version": "0.1.0",
        "features": {
            "cluster": ipfs_api.config.get("role") != "leecher",
            "ai_ml": hasattr(ipfs_api, "ai_model_add"),
        },
        "timeouts": ipfs_api.config.get("timeouts", {}),
    }
    
    return safe_config

# List available methods
@app.get("/api/methods")
async def list_methods():
    """List available API methods."""
    methods = []
    
    # Get all methods from IPFS API
    for method_name in dir(ipfs_api):
        if not method_name.startswith('_') and callable(getattr(ipfs_api, method_name)):
            method = getattr(ipfs_api, method_name)
            if method.__doc__:
                methods.append({
                    "name": method_name,
                    "doc": method.__doc__.strip(),
                })
    
    # Add extensions
    for extension_name in ipfs_api.extensions:
        extension = ipfs_api.extensions[extension_name]
        if extension.__doc__:
            methods.append({
                "name": extension_name,
                "doc": extension.__doc__.strip(),
                "type": "extension"
            })
    
    return {"methods": methods}

def run_server(host="127.0.0.1", port=8000, reload=False):
    """
    Run the API server.
    
    Args:
        host: Host to bind to
        port: Port to bind to
        reload: Whether to enable auto-reload
    """
    uvicorn.run("ipfs_kit_py.api:app", host=host, port=port, reload=reload)

if __name__ == "__main__":
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="IPFS Kit API Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--config", help="Path to configuration file")
    
    args = parser.parse_args()
    
    # Initialize API with configuration file if provided
    if args.config:
        ipfs_api = IPFSSimpleAPI(config_path=args.config)
    
    # Run server
    run_server(host=args.host, port=args.port, reload=args.reload)