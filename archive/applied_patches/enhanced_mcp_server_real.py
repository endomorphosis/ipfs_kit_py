"""
Enhanced MCP server implementation with real storage backends.

This script improves on the previous MCP server by properly integrating
with real storage backends where possible, with graceful fallback to mock mode.
"""

import os
import sys
import logging
import uvicorn
import time
import json
import argparse
import subprocess
import tempfile
import uuid
from fastapi import FastAPI, APIRouter, File, UploadFile, Form, HTTPException, Query, Body
from fastapi.responses import StreamingResponse, Response
from typing import Dict, List, Any, Optional, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='logs/enhanced_mcp_server_real.log'
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logging.getLogger('').addHandler(console)
logger = logging.getLogger(__name__)

# Parse command line arguments
parser = argparse.ArgumentParser(description='Enhanced MCP Server with real implementations')
parser.add_argument('--port', type=int, default=9997, help='Port to run server on')
parser.add_argument('--host', type=str, default='0.0.0.0', help='Host to bind to')
parser.add_argument('--debug', action='store_true', help='Enable debug mode')
args = parser.parse_args()

# Configuration
PORT = args.port
HOST = args.host
API_PREFIX = "/api/v0"
DEBUG_MODE = args.debug
SERVER_ID = str(uuid.uuid4())

# Source environment variables from mcp_credentials.sh
def source_credentials():
    """Source credentials from mcp_credentials.sh script."""
    credentials_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp_credentials.sh")
    if os.path.exists(credentials_file):
        logger.info(f"Sourcing credentials from {credentials_file}")
        try:
            # Execute the credentials script in a subprocess and capture the environment
            cmd = f"source {credentials_file} && env"
            process = subprocess.Popen(['bash', '-c', cmd], stdout=subprocess.PIPE)
            for line in process.stdout:
                line = line.decode().strip()
                if '=' in line:
                    key, value = line.split('=', 1)
                    if key and value and key not in ['_', 'SHLVL', 'PWD']:
                        os.environ[key] = value
            process.communicate()  # Ensure process completes
            logger.info("Credentials loaded into environment")
        except Exception as e:
            logger.error(f"Error sourcing credentials: {e}")
    else:
        logger.warning(f"Credentials file not found: {credentials_file}")

# IPFS daemon management
def check_ipfs_daemon():
    """Check if IPFS daemon is running."""
    try:
        result = subprocess.run(["ipfs", "version"], 
                              capture_output=True, 
                              text=True, 
                              timeout=5)
        return result.returncode == 0
    except Exception as e:
        logger.error(f"Error checking IPFS daemon: {e}")
        return False

def start_ipfs_daemon():
    """Start the IPFS daemon if not running."""
    if not check_ipfs_daemon():
        try:
            # Start daemon in background
            subprocess.Popen(["ipfs", "daemon", "--routing=dhtclient"], 
                           stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
            # Wait a moment for it to initialize
            time.sleep(2)
            return check_ipfs_daemon()
        except Exception as e:
            logger.error(f"Error starting IPFS daemon: {e}")
            return False
    return True

def run_ipfs_command(command, input_data=None):
    """Run an IPFS command and return the result."""
    try:
        full_command = ["ipfs"] + command
        if input_data:
            result = subprocess.run(full_command, 
                                  input=input_data,
                                  capture_output=True)
        else:
            result = subprocess.run(full_command, 
                                  capture_output=True)
        
        if result.returncode == 0:
            return {"success": True, "output": result.stdout}
        else:
            return {"success": False, "error": result.stderr.decode('utf-8', errors='replace')}
    except Exception as e:
        logger.error(f"Error running IPFS command {command}: {e}")
        return {"success": False, "error": str(e)}

# Function to check cloud provider availability
def check_cloud_provider(provider_name, test_command):
    """
    Check if a cloud provider is available by running a test command.
    
    Args:
        provider_name: Name of the cloud provider
        test_command: Command to test availability
        
    Returns:
        bool: True if provider is available
    """
    try:
        logger.info(f"Testing {provider_name} availability...")
        result = subprocess.run(test_command, 
                              shell=True, 
                              capture_output=True, 
                              text=True,
                              timeout=10)
        if result.returncode == 0:
            logger.info(f"{provider_name} is available")
            return True
        else:
            logger.warning(f"{provider_name} test failed: {result.stderr}")
            return False
    except Exception as e:
        logger.warning(f"Error checking {provider_name} availability: {e}")
        return False

# Storage backend status tracking
storage_backends = {
    "ipfs": {"available": True, "simulation": False},
    "local": {"available": True, "simulation": False},
    "huggingface": {"available": False, "simulation": True, "mock": False},
    "s3": {"available": False, "simulation": True, "mock": False},
    "filecoin": {"available": False, "simulation": True, "mock": False},
    "storacha": {"available": False, "simulation": True, "mock": False},
    "lassie": {"available": False, "simulation": True, "mock": False}
}

# Create FastAPI app
app = FastAPI(
    title="Enhanced MCP Server with Real Implementations",
    description="Model-Controller-Persistence Server for IPFS Kit with real storage backends",
    version="1.0.0"
)

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Enhanced MCP Server with Real Implementations is running",
        "debug_mode": DEBUG_MODE,
        "server_id": SERVER_ID,
        "documentation": "/docs",
        "health_endpoint": f"{API_PREFIX}/health",
        "api_version": "v0",
        "uptime": time.time(),
        "available_endpoints": {
            "ipfs": [
                f"{API_PREFIX}/ipfs/add",
                f"{API_PREFIX}/ipfs/cat",
                f"{API_PREFIX}/ipfs/version",
                f"{API_PREFIX}/ipfs/pin/add",
                f"{API_PREFIX}/ipfs/pin/ls"
            ],
            "storage": [
                f"{API_PREFIX}/storage/health", 
                f"{API_PREFIX}/huggingface/status",
                f"{API_PREFIX}/huggingface/from_ipfs",
                f"{API_PREFIX}/huggingface/to_ipfs",
                f"{API_PREFIX}/s3/status",
                f"{API_PREFIX}/s3/from_ipfs",
                f"{API_PREFIX}/s3/to_ipfs",
                f"{API_PREFIX}/filecoin/status",
                f"{API_PREFIX}/filecoin/from_ipfs",
                f"{API_PREFIX}/filecoin/to_ipfs",
                f"{API_PREFIX}/storacha/status",
                f"{API_PREFIX}/storacha/from_ipfs",
                f"{API_PREFIX}/storacha/to_ipfs",
                f"{API_PREFIX}/lassie/status",
                f"{API_PREFIX}/lassie/retrieve"
            ],
            "health": f"{API_PREFIX}/health"
        }
    }

# Create API router for /api/v0 prefix
router = APIRouter()

# Health endpoint
@router.get("/health")
async def health():
    """Health check endpoint."""
    # Update storage backends status with real implementations
    try:
        # Import extension integration module
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        import mcp_extensions
        # Update storage backends with real status
        mcp_extensions.update_storage_backends(storage_backends)
    except Exception as e:
        logger.warning(f"Error updating storage backends status: {e}")
    
    ipfs_running = check_ipfs_daemon()
    
    health_info = {
        "success": True,
        "status": "healthy" if ipfs_running else "degraded",
        "timestamp": time.time(),
        "server_id": SERVER_ID,
        "debug_mode": DEBUG_MODE,
        "ipfs_daemon_running": ipfs_running,
        "controllers": {
            "ipfs": True,
            "storage": True
        },
        "storage_backends": storage_backends
    }
    
    return health_info

# Storage health endpoint
@router.get("/storage/health")
async def storage_health():
    """Storage backends health check."""
    # Update storage backends status with real implementations
    try:
        # Import extension integration module
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        import mcp_extensions
        # Update storage backends with real status
        mcp_extensions.update_storage_backends(storage_backends)
    except Exception as e:
        logger.warning(f"Error updating storage backends status: {e}")
    
    return {
        "success": True,
        "timestamp": time.time(),
        "mode": "hybrid_storage",  # Real, mock, or simulation as needed
        "components": storage_backends,
        "overall_status": "healthy"
    }

# IPFS Version endpoint
@router.get("/ipfs/version")
async def ipfs_version():
    """Get IPFS version information."""
    if not start_ipfs_daemon():
        raise HTTPException(status_code=500, detail="IPFS daemon is not running")
    
    result = run_ipfs_command(["version"])
    if result["success"]:
        try:
            version_str = result["output"].decode('utf-8').strip()
            return {"success": True, "version": version_str}
        except Exception as e:
            logger.error(f"Error parsing IPFS version: {e}")
            return {"success": False, "error": str(e)}
    else:
        return {"success": False, "error": result["error"]}

# IPFS Add endpoint
@router.post("/ipfs/add")
async def ipfs_add(file: UploadFile = File(...)):
    """Add a file to IPFS."""
    if not start_ipfs_daemon():
        raise HTTPException(status_code=500, detail="IPFS daemon is not running")
    
    try:
        # Create a temporary file to store the uploaded content
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            # Write the uploaded file content to the temporary file
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        # Add the file to IPFS
        result = run_ipfs_command(["add", "-q", temp_file_path])
        
        # Clean up the temporary file
        os.unlink(temp_file_path)
        
        if result["success"]:
            cid = result["output"].decode('utf-8').strip()
            return {
                "success": True, 
                "cid": cid,
                "size": len(content),
                "name": file.filename
            }
        else:
            return {"success": False, "error": result["error"]}
    
    except Exception as e:
        logger.error(f"Error adding file to IPFS: {e}")
        return {"success": False, "error": str(e)}

# IPFS Cat endpoint
@router.get("/ipfs/cat/{cid}")
async def ipfs_cat(cid: str):
    """Get content from IPFS by CID."""
    if not start_ipfs_daemon():
        raise HTTPException(status_code=500, detail="IPFS daemon is not running")
    
    result = run_ipfs_command(["cat", cid])
    if result["success"]:
        # Use StreamingResponse to handle large files efficiently
        async def content_generator():
            yield result["output"]
        
        return StreamingResponse(
            content_generator(),
            media_type="application/octet-stream"
        )
    else:
        raise HTTPException(status_code=404, detail=f"Content not found: {result['error']}")

# IPFS Pin Add endpoint
@router.post("/ipfs/pin/add")
async def ipfs_pin_add(cid: str = Form(...)):
    """Pin content in IPFS by CID."""
    if not start_ipfs_daemon():
        raise HTTPException(status_code=500, detail="IPFS daemon is not running")
    
    result = run_ipfs_command(["pin", "add", cid])
    if result["success"]:
        return {"success": True, "cid": cid, "pinned": True}
    else:
        return {"success": False, "error": result["error"]}

# IPFS Pin List endpoint
@router.get("/ipfs/pin/ls")
async def ipfs_pin_list():
    """List pinned content in IPFS."""
    if not start_ipfs_daemon():
        raise HTTPException(status_code=500, detail="IPFS daemon is not running")
    
    result = run_ipfs_command(["pin", "ls", "--type=recursive"])
    if result["success"]:
        try:
            output = result["output"].decode('utf-8').strip()
            pins = {}
            
            for line in output.split('\n'):
                if line:
                    parts = line.split(' ')
                    if len(parts) >= 2:
                        cid = parts[0]
                        pins[cid] = {"type": "recursive"}
            
            return {"success": True, "pins": pins}
        except Exception as e:
            logger.error(f"Error parsing pin list: {e}")
            return {"success": False, "error": str(e)}
    else:
        return {"success": False, "error": result["error"]}

# Register the basic router
app.include_router(router, prefix=API_PREFIX)

# Try to import and use extension implementations, with fallbacks
def setup_extensions():
    """
    Set up storage backend extensions with proper fallbacks.
    
    This function attempts to load real implementations of storage backends,
    and falls back to mock implementations when real ones are not available.
    """
    # Create necessary directories
    os.makedirs("logs", exist_ok=True)
    mock_base_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit")
    os.makedirs(mock_base_dir, exist_ok=True)
    
    extension_success = False
    
    try:
        # Import extension integration module
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        import mcp_extensions
        
        # Try to create and add extension routers
        extension_routers = mcp_extensions.create_extension_routers(API_PREFIX)
        for ext_router in extension_routers:
            app.include_router(ext_router)
            logger.info(f"Added extension router: {ext_router.prefix}")
        
        # Update storage backends status
        mcp_extensions.update_storage_backends(storage_backends)
        extension_success = True
    except Exception as e:
        logger.error(f"Error setting up extensions: {e}")
    
    # Check if we need to add fallback implementations
    if not extension_success:
        logger.warning("Extension setup failed, adding fallback implementations")
        add_fallback_implementations()
    
    # For each storage backend, check if we need to enhance or patch it
    enhance_backend_implementations()

def add_fallback_implementations():
    """Add fallback implementations for all storage backends."""
    from fastapi import APIRouter, Form, HTTPException
    from typing import Optional
    
    for backend in ["huggingface", "s3", "filecoin", "storacha", "lassie"]:
        logger.info(f"Setting up fallback implementation for {backend}")
        mock_router = APIRouter(prefix=f"{API_PREFIX}/{backend}")
        
        @mock_router.get("/status")
        async def status():
            """Get status of the storage backend."""
            return {
                "success": True,
                "available": True,
                "simulation": False,
                "mock": True,
                "fallback": True,
                "message": f"Using fallback {backend} implementation",
                "timestamp": time.time()
            }
        
        # Generic fallback handlers for common endpoints
        if backend != "lassie":  # Lassie has a different API
            @mock_router.post("/from_ipfs")
            async def from_ipfs(cid: str = Form(...), path: Optional[str] = Form(None)):
                """Upload content from IPFS to storage backend."""
                # Create mock storage directory
                mock_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", f"mock_{backend}")
                os.makedirs(mock_dir, exist_ok=True)
                
                # Get content from IPFS
                result = run_ipfs_command(["cat", cid])
                if not result["success"]:
                    return {"success": False, "mock": True, "error": f"Failed to get content from IPFS: {result['error']}"}
                
                # Save to mock storage
                file_path = path or f"ipfs/{cid}"
                full_path = os.path.join(mock_dir, file_path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                
                with open(full_path, "wb") as f:
                    f.write(result["output"])
                
                return {
                    "success": True,
                    "mock": True,
                    "fallback": True,
                    "message": f"Content stored in fallback {backend} storage",
                    "url": f"file://{full_path}",
                    "cid": cid,
                    "path": file_path
                }
            
            @mock_router.post("/to_ipfs")
            async def to_ipfs(file_path: str = Form(...), cid: Optional[str] = Form(None)):
                """Upload content from storage backend to IPFS."""
                # Check if file exists in mock storage
                mock_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", f"mock_{backend}")
                mock_file_path = os.path.join(mock_dir, file_path)
                
                if not os.path.exists(mock_file_path):
                    # Create a dummy file with random content for demonstration
                    os.makedirs(os.path.dirname(mock_file_path), exist_ok=True)
                    with open(mock_file_path, "wb") as f:
                        f.write(os.urandom(1024))  # 1KB random data
                
                # Add to IPFS
                result = run_ipfs_command(["add", "-q", mock_file_path])
                if not result["success"]:
                    return {"success": False, "mock": True, "error": f"Failed to add to IPFS: {result['error']}"}
                
                new_cid = result["output"].decode('utf-8').strip()
                
                return {
                    "success": True,
                    "mock": True,
                    "fallback": True,
                    "message": f"Added content from fallback {backend} storage to IPFS",
                    "cid": new_cid,
                    "source": f"mock_{backend}:{file_path}"
                }
        else:
            # Special case for Lassie which has a different API
            @mock_router.post("/retrieve")
            async def retrieve(cid: str = Form(...), path: Optional[str] = Form(None)):
                """Retrieve content using Lassie."""
                # Create mock storage directory
                mock_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "mock_lassie")
                os.makedirs(mock_dir, exist_ok=True)
                
                # Get content from IPFS as a fallback
                result = run_ipfs_command(["cat", cid])
                if not result["success"]:
                    return {"success": False, "mock": True, "error": f"Failed to get content from IPFS: {result['error']}"}
                
                # Save to mock storage
                file_path = path or f"retrieved/{cid}"
                full_path = os.path.join(mock_dir, file_path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                
                with open(full_path, "wb") as f:
                    f.write(result["output"])
                
                return {
                    "success": True,
                    "mock": True,
                    "fallback": True,
                    "message": "Content retrieved using fallback Lassie implementation",
                    "path": full_path,
                    "cid": cid,
                    "size": len(result["output"])
                }
        
        # Add the router to the app
        app.include_router(mock_router)
        storage_backends[backend]["available"] = True
        storage_backends[backend]["simulation"] = False
        storage_backends[backend]["mock"] = True
        storage_backends[backend]["fallback"] = True
        logger.info(f"Added fallback router for {backend}")

def enhance_backend_implementations():
    """
    Enhance the existing backend implementations.
    
    This function attempts to enhance the storage backends by:
    1. Checking if real implementations can be used
    2. Patching any issues in the implementations
    3. Adding additional features as needed
    """
    # Check and enhance HuggingFace implementation
    try:
        # Check if we have a HuggingFace token from CLI
        import huggingface_hub
        cli_token = huggingface_hub.get_token()
        if cli_token and len(cli_token) > 10:
            logger.info("Found valid HuggingFace token from CLI")
            os.environ["HUGGINGFACE_TOKEN"] = cli_token
            storage_backends["huggingface"]["enhanced"] = True
            storage_backends["huggingface"]["message"] = "Using token from HuggingFace CLI"
    except Exception as e:
        logger.warning(f"Error enhancing HuggingFace implementation: {e}")
    
    # Check and enhance AWS S3 implementation
    try:
        # Check if we can access AWS resources
        if check_cloud_provider("AWS S3", "aws s3 ls 2>&1 >/dev/null || exit 1"):
            logger.info("AWS CLI is configured with valid credentials")
            # Get AWS credentials from CLI config
            aws_config = subprocess.run(
                ["aws", "configure", "list"], 
                capture_output=True, 
                text=True
            )
            if "access_key" in aws_config.stdout:
                storage_backends["s3"]["enhanced"] = True
                storage_backends["s3"]["message"] = "Using credentials from AWS CLI"
            
            # Check for a valid bucket
            try:
                result = subprocess.run(
                    ["aws", "s3", "ls", f"s3://{os.environ.get('AWS_S3_BUCKET_NAME', 'ipfs-storage-demo')}"],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    storage_backends["s3"]["bucket_exists"] = True
                else:
                    # Try to create the bucket
                    create_result = subprocess.run(
                        ["aws", "s3", "mb", f"s3://{os.environ.get('AWS_S3_BUCKET_NAME', 'ipfs-storage-demo')}"],
                        capture_output=True,
                        text=True
                    )
                    if create_result.returncode == 0:
                        storage_backends["s3"]["bucket_exists"] = True
                        storage_backends["s3"]["message"] += ", bucket created"
            except Exception as e:
                logger.warning(f"Error checking S3 bucket: {e}")
    except Exception as e:
        logger.warning(f"Error enhancing AWS S3 implementation: {e}")
    
    # Check and enhance Filecoin implementation
    try:
        # Check if Lotus is installed
        lotus_path = subprocess.run(
            ["which", "lotus"],
            capture_output=True,
            text=True
        )
        if lotus_path.returncode == 0:
            lotus_binary = lotus_path.stdout.strip()
            logger.info(f"Found Lotus binary: {lotus_binary}")
            
            # Check if Lotus daemon is running
            lotus_status = subprocess.run(
                [lotus_binary, "daemon", "--help"],
                capture_output=True,
                text=True
            )
            if lotus_status.returncode == 0:
                storage_backends["filecoin"]["enhanced"] = True
                storage_backends["filecoin"]["message"] = "Found Lotus binary"
                
                # Try to get API info
                os.environ["FILECOIN_API_URL"] = os.environ.get("FILECOIN_API_URL", "http://localhost:1234")
                os.environ["FILECOIN_API_TOKEN"] = os.environ.get("FILECOIN_API_TOKEN", "")
                
                # If we have bin/lotus, use that
                bin_lotus = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin", "lotus")
                if os.path.exists(bin_lotus):
                    logger.info(f"Using local Lotus binary: {bin_lotus}")
                    os.environ["LOTUS_PATH"] = bin_lotus
    except Exception as e:
        logger.warning(f"Error enhancing Filecoin implementation: {e}")
    
    # Check and enhance Lassie implementation
    try:
        # Check if Lassie is installed
        lassie_path = subprocess.run(
            ["which", "lassie"],
            capture_output=True,
            text=True
        )
        if lassie_path.returncode == 0:
            lassie_binary = lassie_path.stdout.strip()
            logger.info(f"Found Lassie binary: {lassie_binary}")
            os.environ["LASSIE_BINARY_PATH"] = lassie_binary
            storage_backends["lassie"]["enhanced"] = True
            storage_backends["lassie"]["message"] = "Found Lassie binary"
            
            # Get Lassie version
            lassie_version = subprocess.run(
                [lassie_binary, "--version"],
                capture_output=True,
                text=True
            )
            if lassie_version.returncode == 0:
                storage_backends["lassie"]["version"] = lassie_version.stdout.strip()
    except Exception as e:
        logger.warning(f"Error enhancing Lassie implementation: {e}")
    
    # Check for custom tools and binaries in the project
    bin_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin")
    if os.path.exists(bin_dir):
        logger.info(f"Found bin directory: {bin_dir}")
        
        # Check for any custom tools
        tools = [f for f in os.listdir(bin_dir) if os.path.isfile(os.path.join(bin_dir, f))]
        logger.info(f"Available tools: {', '.join(tools)}")
        
        # Add bin directory to PATH
        os.environ["PATH"] = f"{bin_dir}:{os.environ.get('PATH', '')}"

# Main function
if __name__ == "__main__":
    # Source credentials
    source_credentials()
    
    # Create necessary directories
    os.makedirs("logs", exist_ok=True)
    
    # Start IPFS daemon if not running
    start_ipfs_daemon()
    
    # Setup extensions with proper fallbacks
    setup_extensions()
    
    # Write PID file
    with open("enhanced_mcp_server_real.pid", "w") as f:
        f.write(str(os.getpid()))
    
    # Run server
    logger.info(f"Starting enhanced MCP server with real implementations on port {PORT}")
    logger.info(f"API prefix: {API_PREFIX}")
    logger.info(f"Debug mode: {DEBUG_MODE}")
    logger.info(f"Server ID: {SERVER_ID}")
    
    uvicorn.run(
        "enhanced_mcp_server_real:app",
        host=HOST,
        port=PORT,
        reload=False
    )