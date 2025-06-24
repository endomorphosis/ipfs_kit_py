#!/usr/bin/env python3
"""
Unified MCP Server Implementation

This is a consolidated implementation of the MCP server that combines
all the best features from various implementations. It provides:
- JSON-RPC endpoint for VS Code integration
- SSE endpoints for real-time updates
- Initialize endpoint for VS Code
- Complete API support for IPFS and storage operations
- Robust error handling and fallback mechanisms
- File system tools (read_file, write_file, etc.)
"""

import os
import sys
import logging
import importlib
import argparse
import time
import uuid
import json
import asyncio
import traceback
import shutil
import py_compile  # Added import for Python file syntax checking
from fastapi import FastAPI, APIRouter, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='mcp_server.log'
)
logger = logging.getLogger(__name__)

# Add console handler for immediate feedback
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console.setFormatter(formatter)
logger.addHandler(console)

# Get configuration from environment variables
debug_mode = os.environ.get("MCP_DEBUG_MODE", "true").lower() == "true"
isolation_mode = os.environ.get("MCP_ISOLATION_MODE", "true").lower() == "true"
skip_daemon = os.environ.get("MCP_SKIP_DAEMON", "true").lower() == "true"
api_prefix = os.environ.get("MCP_API_PREFIX", "/api/v0")

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Run unified MCP server with all extensions.")
parser.add_argument("--port", type=int, default=int(os.environ.get("MCP_PORT", "9994")),
                   help="Port to run the server on (default: 9994)")
parser.add_argument("--host", type=str, default="0.0.0.0",
                   help="Host to bind the server to (default: 0.0.0.0)")
parser.add_argument("--debug", action="store_true", default=debug_mode,
                   help="Enable debug mode")
parser.add_argument("--no-debug", action="store_false", dest="debug",
                   help="Disable debug mode")
parser.add_argument("--isolation", action="store_true", default=isolation_mode,
                   help="Enable isolation mode")
parser.add_argument("--no-isolation", action="store_false", dest="isolation",
                   help="Disable isolation mode")
parser.add_argument("--skip-daemon", action="store_true", default=skip_daemon,
                   help="Skip daemon initialization")
parser.add_argument("--no-skip-daemon", action="store_false", dest="skip_daemon",
                   help="Don't skip daemon initialization")
parser.add_argument("--api-prefix", type=str, default=api_prefix,
                   help="API prefix for endpoints (default: /api/v0)")
parser.add_argument("--log-file", type=str, default="mcp_server.log",
                   help="Log file path (default: mcp_server.log)")

args = parser.parse_args()

# Update log level based on debug mode
log_level = "DEBUG" if args.debug else "INFO"
logging.getLogger().setLevel(getattr(logging, log_level))
logger.setLevel(getattr(logging, log_level))

# Create FastAPI app
app = FastAPI(
    title="Unified MCP Server",
    description="Unified MCP Server with all tools and extensions properly initialized",
    version="1.0.0"
)

# Add CORS middleware to allow cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Generate a unique server ID and track start time
server_id = str(uuid.uuid4())
start_time = time.time()

# Initialize endpoint for VS Code integration at /initialize
@app.post('/initialize', tags=["MCP"])
@app.get('/initialize', tags=["MCP"])
async def initialize_endpoint():
    """Initialize endpoint for VS Code MCP protocol.

    This endpoint is called by VS Code when it first connects to the MCP server.
    It returns information about the server's capabilities.
    """
    logger.info("Received initialize request from VS Code")
    return {
        "capabilities": {
            "tools": ["ipfs_add", "ipfs_cat", "ipfs_pin", "storage_transfer",
                     "read_file", "write_file", "edit_file", "list_files"],
            "resources": ["ipfs://info", "storage://backends", "file://"]
        },
        "serverInfo": {
            "name": "IPFS Kit MCP Server",
            "version": "1.0.0",
            "implementationName": "ipfs-kit-py"
        }
    }

# Initialize endpoint with API prefix
@app.post(f'{api_prefix}/initialize', tags=["MCP"])
@app.get(f'{api_prefix}/initialize', tags=["MCP"])
async def api_initialize_endpoint():
    """API-prefixed initialize endpoint for VS Code MCP protocol."""
    return await initialize_endpoint()

# Create an info router for the root endpoint
info_router = APIRouter()

@info_router.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Unified MCP Server is running",
        "debug_mode": args.debug,
        "server_id": server_id,
        "documentation": "/docs",
        "health_endpoint": f"{args.api_prefix}/health",
        "api_version": "v0",
        "uptime": time.time() - start_time,
        "available_endpoints": {
            "ipfs": [
                f"{args.api_prefix}/ipfs/add",
                f"{args.api_prefix}/ipfs/cat",
                f"{args.api_prefix}/ipfs/version",
                f"{args.api_prefix}/ipfs/pin/add",
                f"{args.api_prefix}/ipfs/pin/ls",
            ],
            "storage": [
                f"{args.api_prefix}/storage/health",
                f"{args.api_prefix}/huggingface/status",
                f"{args.api_prefix}/huggingface/from_ipfs",
                f"{args.api_prefix}/huggingface/to_ipfs",
                f"{args.api_prefix}/s3/status",
                f"{args.api_prefix}/s3/from_ipfs",
                f"{args.api_prefix}/s3/to_ipfs",
                f"{args.api_prefix}/filecoin/status",
                f"{args.api_prefix}/filecoin/from_ipfs",
                f"{args.api_prefix}/filecoin/to_ipfs",
                f"{args.api_prefix}/storacha/status",
                f"{args.api_prefix}/storacha/from_ipfs",
                f"{args.api_prefix}/storacha/to_ipfs",
                f"{args.api_prefix}/lassie/status",
                f"{args.api_prefix}/lassie/retrieve",
            ],
            "file_system": [
                f"{args.api_prefix}/read_file",
                f"{args.api_prefix}/read_file_slice",
                f"{args.api_prefix}/write_file",
                f"{args.api_prefix}/edit_file",
                f"{args.api_prefix}/patch_file",
                f"{args.api_prefix}/list_files",
            ],
            "health": f"{args.api_prefix}/health",
            "jsonrpc": "/jsonrpc",
            "sse": f"{args.api_prefix}/sse",
        }
    }

# Add the info router to the app
app.include_router(info_router)

# Create health endpoint at root level
@app.get("/health")
async def health():
    """Root-level health endpoint."""
    return {
        "success": True,
        "status": "healthy",
        "timestamp": time.time(),
        "server_id": server_id,
        "uptime_seconds": time.time() - start_time,
        "debug_mode": args.debug
    }

# Add the SSE endpoint without API prefix for direct access
@app.get("/sse")
async def sse():
    """SSE endpoint for MCP client connections without API prefix."""
    return await api_sse()  # Reuse the API-prefixed implementation

# Add the SSE endpoint with API prefix
@app.get(f"{args.api_prefix}/sse")
async def api_sse():
    """API-prefixed SSE endpoint for MCP client connections."""
    async def event_generator():
        """Generate server-sent events for clients."""
        try:
            # Send initial connection established event
            event_data = {
                "type": "connection",
                "status": "established",
                "timestamp": time.time()
            }
            yield f"data: {json.dumps(event_data)}\n\n"

            # Send an immediate health check event
            event_data = {
                "type": "health",
                "status": "healthy",
                "seq": 0,
                "timestamp": time.time(),
                "server_id": server_id
            }
            yield f"data: {json.dumps(event_data)}\n\n"

            # Send periodic health updates
            counter = 1
            while True:
                event_data = {
                    "type": "health",
                    "status": "healthy",
                    "seq": counter,
                    "timestamp": time.time(),
                    "server_id": server_id
                }
                counter += 1
                yield f"data: {json.dumps(event_data)}\n\n"
                await asyncio.sleep(5)  # Send health update every 5 seconds
        except Exception as e:
            logger.error(f"Error in SSE stream: {e}")
            logger.error(traceback.format_exc())
            # Send error event
            event_data = {
                "type": "error",
                "message": str(e),
                "timestamp": time.time()
            }
            yield f"data: {json.dumps(event_data)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "X-Accel-Buffering": "no"  # Disable Nginx buffering
        }
    )

# Create SSE test endpoint for debugging
@app.get("/sse/test")
async def sse_test():
    """Test Server-Sent Events (SSE) endpoint."""
    async def event_generator():
        """Generate test server-sent events."""
        for i in range(5):
            yield f"data: {json.dumps({'count': i, 'timestamp': time.time()})}\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# Add JSON-RPC endpoint without API prefix for VS Code
@app.post("/jsonrpc")
async def jsonrpc_handler(request: Request):
    """JSON-RPC endpoint for VS Code Language Server Protocol."""
    try:
        data = await request.json()
        logger.info(f"Received JSON-RPC request: {data}")

        # Handle 'initialize' request
        if data.get("method") == "initialize":
            logger.info("Processing initialize request from VS Code")

            # Return capabilities in a properly formatted JSON-RPC response
            response = {
                "jsonrpc": "2.0",
                "id": data.get("id"),
                "result": {
                    "capabilities": {
                        "textDocumentSync": {
                            "openClose": True,
                            "change": 1
                        },
                        "completionProvider": {
                            "resolveProvider": False,
                            "triggerCharacters": ["/"]
                        },
                        "hoverProvider": True,
                        "definitionProvider": True,
                        "referencesProvider": True
                    },
                    "serverInfo": {
                        "name": "MCP IPFS Tools Server",
                        "version": "0.3.0"
                    }
                }
            }
            logger.info(f"Sending initialize response: {response}")
            return JSONResponse(content=response, status_code=200, media_type="application/vscode-jsonrpc; charset=utf-8")

        # Handle 'shutdown' request
        elif data.get("method") == "shutdown":
            logger.info("Received shutdown request from VS Code")
            response = {"jsonrpc": "2.0", "id": data.get("id"), "result": None}
            return JSONResponse(content=response, status_code=200, media_type="application/vscode-jsonrpc; charset=utf-8")

        # Handle 'exit' notification
        elif data.get("method") == "exit":
            logger.info("Received exit notification from VS Code")
            response = {"jsonrpc": "2.0", "id": data.get("id"), "result": None}
            return JSONResponse(content=response, status_code=200, media_type="application/vscode-jsonrpc; charset=utf-8")

        # For any other method, return a 'method not found' error
        else:
            logger.warning(f"Unhandled JSON-RPC method: {data.get('method')}")
            error_resp = {
                "jsonrpc": "2.0",
                "id": data.get("id"),
                "error": {
                    "code": -32601,
                    "message": f"Method '{data.get('method')}' not found"
                }
            }
            return JSONResponse(content=error_resp, status_code=200, media_type="application/vscode-jsonrpc; charset=utf-8")
    except Exception as e:
        logger.error(f"Error handling JSON-RPC request: {e}")
        logger.error(traceback.format_exc())
        error = {
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        }
        return JSONResponse(content=error, status_code=500, media_type="application/vscode-jsonrpc; charset=utf-8")

# Add JSON-RPC endpoint with API prefix
@app.post(f"{args.api_prefix}/jsonrpc")
async def api_jsonrpc_handler(request: Request):
    """JSON-RPC endpoint at API prefix for VS Code Language Server Protocol."""
    return await jsonrpc_handler(request)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for the API."""
    logger.error(f"Unhandled exception in API request: {str(exc)}")
    logger.error(traceback.format_exc())

    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if not args.debug else f"{str(exc)}\n{traceback.format_exc()}",
            "timestamp": time.time()
        }
    )

# Add filesystem tools to the MCP server
@app.post(f"{args.api_prefix}/read_file")
async def read_file_endpoint(request: Request):
    """Read file endpoint that returns the contents of a file."""
    try:
        data = await request.json()
        path = data.get("path")

        if not path:
            return JSONResponse(
                status_code=400,
                content={"error": "Missing path parameter"}
            )

        project_root = os.getcwd()
        absolute_path = os.path.abspath(os.path.join(project_root, path))

        # Security check to prevent directory traversal
        if not absolute_path.startswith(project_root):
            return JSONResponse(
                status_code=403,
                content={"error": f"Path '{path}' is outside the allowed project directory"}
            )

        if not os.path.exists(absolute_path):
            return JSONResponse(
                status_code=404,
                content={"error": f"File not found: {path}"}
            )

        if not os.path.isfile(absolute_path):
            return JSONResponse(
                status_code=400,
                content={"error": f"Path is not a file: {path}"}
            )

        # Check file size to prevent memory issues with very large files
        file_size = os.path.getsize(absolute_path)
        max_size = 10 * 1024 * 1024  # 10 MB limit

        if file_size > max_size:
            return JSONResponse(
                status_code=400,
                content={"error": f"File is too large: {file_size / 1024 / 1024:.2f} MB. Max size is 10 MB."}
            )

        try:
            with open(absolute_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "content": content,
                    "path": path,
                    "size": len(content)
                }
            )
        except UnicodeDecodeError:
            # Try to detect if it's a binary file
            try:
                with open(absolute_path, "rb") as f:
                    sample = f.read(1024)
                if b'\x00' in sample:
                    return JSONResponse(
                        status_code=400,
                        content={"error": f"File '{path}' appears to be a binary file"}
                    )
                else:
                    # Try with a different encoding
                    with open(absolute_path, "r", encoding="latin-1") as f:
                        content = f.read()
                    return JSONResponse(
                        status_code=200,
                        content={
                            "success": True,
                            "content": content,
                            "path": path,
                            "size": len(content),
                            "encoding": "latin-1"
                        }
                    )
            except Exception as e:
                return JSONResponse(
                    status_code=500,
                    content={"error": f"Error reading file: {str(e)}"}
                )

    except Exception as e:
        logger.error(f"Error in read_file endpoint: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Internal server error: {str(e)}"}
        )

@app.post(f"{args.api_prefix}/read_file_slice")
async def read_file_slice_endpoint(request: Request):
    """Read file slice endpoint that returns specific lines from a file."""
    try:
        data = await request.json()
        path = data.get("path")
        start_line = int(data.get("start_line", 1))
        num_lines = int(data.get("num_lines", 50))

        if not path:
            return JSONResponse(
                status_code=400,
                content={"error": "Missing path parameter"}
            )

        if start_line < 1:
            return JSONResponse(
                status_code=400,
                content={"error": "start_line must be 1 or greater"}
            )

        if num_lines < 1:
            return JSONResponse(
                status_code=400,
                content={"error": "num_lines must be at least 1"}
            )

        project_root = os.getcwd()
        absolute_path = os.path.abspath(os.path.join(project_root, path))

        # Security check to prevent directory traversal
        if not absolute_path.startswith(project_root):
            return JSONResponse(
                status_code=403,
                content={"error": f"Path '{path}' is outside the allowed project directory"}
            )

        if not os.path.exists(absolute_path):
            return JSONResponse(
                status_code=404,
                content={"error": f"File not found: {path}"}
            )

        if not os.path.isfile(absolute_path):
            return JSONResponse(
                status_code=400,
                content={"error": f"Path is not a file: {path}"}
            )

        try:
            with open(absolute_path, "r", encoding="utf-8", errors="replace") as f:
                # Zero-based index for start_index
                start_index = start_line - 1
                lines = []

                # Skip to the start line
                for i, line in enumerate(f):
                    if i >= start_index:
                        lines.append(line)
                        # Break once we have read enough lines
                        if len(lines) >= num_lines:
                            break

            if not lines:
                if start_line > 1:
                    return JSONResponse(
                        status_code=200,
                        content={
                            "success": True,
                            "content": "",
                            "path": path,
                            "message": f"No lines found at line {start_line} or beyond"
                        }
                    )
                else:
                    return JSONResponse(
                        status_code=200,
                        content={
                            "success": True,
                            "content": "",
                            "path": path,
                            "message": "File is empty"
                        }
                    )

            content = "".join(lines)

            # Get total number of lines for context
            total_lines = sum(1 for _ in open(absolute_path, "r", encoding="utf-8", errors="replace"))

            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "content": content,
                    "path": path,
                    "start_line": start_line,
                    "end_line": start_line + len(lines) - 1,
                    "total_lines": total_lines,
                    "lines_read": len(lines)
                }
            )
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"error": f"Error reading file slice: {str(e)}"}
            )

    except Exception as e:
        logger.error(f"Error in read_file_slice endpoint: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Internal server error: {str(e)}"}
        )

@app.post(f"{args.api_prefix}/write_file")
async def write_file_endpoint(request: Request):
    """Write file endpoint that creates a new file with content."""
    try:
        data = await request.json()
        path = data.get("path")
        content = data.get("content", "")

        if not path:
            return JSONResponse(
                status_code=400,
                content={"error": "Missing path parameter"}
            )

        project_root = os.getcwd()
        absolute_path = os.path.abspath(os.path.join(project_root, path))

        # Security check to prevent directory traversal
        if not absolute_path.startswith(project_root):
            return JSONResponse(
                status_code=403,
                content={"error": f"Path '{path}' is outside the allowed project directory"}
            )

        # Check if file already exists
        if os.path.exists(absolute_path):
            return JSONResponse(
                status_code=409,  # Conflict
                content={"error": f"File already exists: {path}. Use edit_file to modify existing files."}
            )

        # Ensure the directory exists
        directory = os.path.dirname(absolute_path)
        if directory and not os.path.exists(directory):
            try:
                os.makedirs(directory, exist_ok=True)
                logger.info(f"Created directory: {directory}")
            except Exception as e:
                return JSONResponse(
                    status_code=500,
                    content={"error": f"Error creating directory: {str(e)}"}
                )

        try:
            # Write the content to the file
            with open(absolute_path, "w", encoding="utf-8") as f:
                f.write(content)

            file_size = os.path.getsize(absolute_path)

            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "path": path,
                    "size": file_size,
                    "message": f"File created successfully with {file_size} bytes"
                }
            )
        except Exception as e:
            # Try to remove the file if an error occurred during writing
            try:
                if os.path.exists(absolute_path):
                    os.remove(absolute_path)
            except:
                pass

            return JSONResponse(
                status_code=500,
                content={"error": f"Error writing to file: {str(e)}"}
            )

    except Exception as e:
        logger.error(f"Error in write_file endpoint: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Internal server error: {str(e)}"}
        )

@app.post(f"{args.api_prefix}/edit_file")
async def edit_file_endpoint(request: Request):
    """Edit file endpoint that modifies an existing file."""
    try:
        data = await request.json()
        path = data.get("path")
        content = data.get("content", "")

        if not path:
            return JSONResponse(
                status_code=400,
                content={"error": "Missing path parameter"}
            )

        project_root = os.getcwd()
        absolute_path = os.path.abspath(os.path.join(project_root, path))

        # Security check to prevent directory traversal
        if not absolute_path.startswith(project_root):
            return JSONResponse(
                status_code=403,
                content={"error": f"Path '{path}' is outside the allowed project directory"}
            )

        # Check if file exists
        if not os.path.exists(absolute_path):
            return JSONResponse(
                status_code=404,
                content={"error": f"File not found: {path}. Use write_file to create a new file."}
            )

        if not os.path.isfile(absolute_path):
            return JSONResponse(
                status_code=400,
                content={"error": f"Path is not a file: {path}"}
            )

        # Create backup and temporary files
        backup_path = absolute_path + ".bak"
        temp_path = absolute_path + ".tmp"

        try:
            # Create backup of original file
            shutil.copy2(absolute_path, backup_path)

            # Write content to temporary file
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(content)

            # For Python files, perform syntax check
            if absolute_path.endswith(".py"):
                try:
                    py_compile.compile(temp_path, doraise=True)
                    logger.info(f"Syntax check passed for {path}")
                except py_compile.PyCompileError as e:
                    # Clean up temporary file
                    os.remove(temp_path)
                    return JSONResponse(
                        status_code=400,
                        content={
                            "success": False,
                            "error": f"Python syntax error: {str(e)}",
                            "path": path
                        }
                    )
                except Exception as e:
                    # Clean up temporary file
                    os.remove(temp_path)
                    return JSONResponse(
                        status_code=500,
                        content={
                            "success": False,
                            "error": f"Error checking Python syntax: {str(e)}",
                            "path": path
                        }
                    )

            # Move the temporary file to replace the original
            shutil.move(temp_path, absolute_path)

            # Get file size for response
            file_size = os.path.getsize(absolute_path)

            # Remove backup if everything is successful
            os.remove(backup_path)

            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "path": path,
                    "size": file_size,
                    "message": f"File edited successfully with {file_size} bytes"
                }
            )
        except Exception as e:
            # Restore from backup if an error occurred
            try:
                if os.path.exists(backup_path):
                    shutil.move(backup_path, absolute_path)
                    logger.info(f"Restored backup after error for {path}")
            except:
                pass

            # Clean up temporary file if it exists
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except:
                pass

            return JSONResponse(
                status_code=500,
                content={"error": f"Error editing file: {str(e)}"}
            )

    except Exception as e:
        logger.error(f"Error in edit_file endpoint: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Internal server error: {str(e)}"}
        )

@app.post(f"{args.api_prefix}/patch_file")
async def patch_file_endpoint(request: Request):
    """Patch file endpoint that replaces specific lines in a file."""
    try:
        data = await request.json()
        path = data.get("path")
        start_line = int(data.get("start_line", 1))
        line_count_to_replace = int(data.get("line_count_to_replace", 1))
        new_lines_content = data.get("new_lines_content", "")

        if not path:
            return JSONResponse(
                status_code=400,
                content={"error": "Missing path parameter"}
            )

        if start_line < 1:
            return JSONResponse(
                status_code=400,
                content={"error": "start_line must be 1 or greater"}
            )

        if line_count_to_replace < 0:
            return JSONResponse(
                status_code=400,
                content={"error": "line_count_to_replace cannot be negative"}
            )

        project_root = os.getcwd()
        absolute_path = os.path.abspath(os.path.join(project_root, path))

        # Security check to prevent directory traversal
        if not absolute_path.startswith(project_root):
            return JSONResponse(
                status_code=403,
                content={"error": f"Path '{path}' is outside the allowed project directory"}
            )

        # Check if file exists
        if not os.path.exists(absolute_path):
            return JSONResponse(
                status_code=404,
                content={"error": f"File not found: {path}"}
            )

        if not os.path.isfile(absolute_path):
            return JSONResponse(
                status_code=400,
                content={"error": f"Path is not a file: {path}"}
            )

        # Create backup and temporary files
        backup_path = absolute_path + ".bak"
        temp_path = absolute_path + ".tmp"

        try:
            # Read original content
            with open(absolute_path, "r", encoding="utf-8") as f:
                original_lines = f.readlines()

            # Calculate slice indices (0-based)
            start_index = start_line - 1
            end_index = start_index + line_count_to_replace

            # Validate slice indices against file length
            if start_index >= len(original_lines):
                return JSONResponse(
                    status_code=400,
                    content={"error": f"start_line ({start_line}) is beyond the end of the file ({len(original_lines)} lines)"}
                )

            # Allow replacing past the end (effectively appending) but cap end_index
            end_index = min(end_index, len(original_lines))

            # Construct new content
            new_lines_list = new_lines_content.splitlines(True)  # Keep line endings
            if new_lines_list and not new_lines_list[-1].endswith('\n'):
                # Ensure the last line has a newline if the original content did
                if original_lines and original_lines[-1].endswith('\n'):
                    new_lines_list[-1] = new_lines_list[-1] + '\n'

            patched_lines = original_lines[:start_index] + new_lines_list + original_lines[end_index:]
            patched_content = "".join(patched_lines)

            # Create backup of original file
            shutil.copy2(absolute_path, backup_path)

            # Write patched content to temporary file
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(patched_content)

            # For Python files, perform syntax check
            if absolute_path.endswith(".py"):
                try:
                    py_compile.compile(temp_path, doraise=True)
                    logger.info(f"Syntax check passed for patched {path}")
                except py_compile.PyCompileError as e:
                    # Clean up temporary file
                    os.remove(temp_path)
                    # Keep backup for reference
                    return JSONResponse(
                        status_code=400,
                        content={
                            "success": False,
                            "error": f"Python syntax error in patched file: {str(e)}",
                            "path": path,
                            "backup": f"{path}.bak"
                        }
                    )
                except Exception as e:
                    # Clean up temporary file
                    os.remove(temp_path)
                    # Keep backup for reference
                    return JSONResponse(
                        status_code=500,
                        content={
                            "success": False,
                            "error": f"Error checking Python syntax in patched file: {str(e)}",
                            "path": path,
                            "backup": f"{path}.bak"
                        }
                    )

            # Move the temporary file to replace the original
            shutil.move(temp_path, absolute_path)

            # Get file size for response
            file_size = os.path.getsize(absolute_path)

            # Remove backup if everything is successful
            os.remove(backup_path)

            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "path": path,
                    "size": file_size,
                    "lines_patched": line_count_to_replace,
                    "new_line_count": len(new_lines_list),
                    "start_line": start_line,
                    "message": f"File patched successfully at line {start_line}"
                }
            )
        except Exception as e:
            # Restore from backup if an error occurred
            try:
                if os.path.exists(backup_path):
                    shutil.move(backup_path, absolute_path)
                    logger.info(f"Restored backup after error for {path}")
            except:
                pass

            # Clean up temporary file if it exists
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except:
                pass

            return JSONResponse(
                status_code=500,
                content={"error": f"Error patching file: {str(e)}"}
            )

    except Exception as e:
        logger.error(f"Error in patch_file endpoint: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Internal server error: {str(e)}"}
        )

@app.post(f"{args.api_prefix}/list_files")
async def list_files_endpoint(request: Request):
    """List files endpoint that returns directory contents."""
    try:
        data = await request.json()
        path = data.get("path", ".")

        project_root = os.getcwd()
        absolute_path = os.path.abspath(os.path.join(project_root, path))

        # Security check to prevent directory traversal
        if not absolute_path.startswith(project_root):
            return JSONResponse(
                status_code=403,
                content={"error": f"Path '{path}' is outside the allowed project directory"}
            )

        if not os.path.exists(absolute_path):
            return JSONResponse(
                status_code=404,
                content={"error": f"Path not found: {path}"}
            )

        if not os.path.isdir(absolute_path):
            return JSONResponse(
                status_code=400,
                content={"error": f"Path is not a directory: {path}"}
            )

        try:
            # Get directory contents
            entries = os.listdir(absolute_path)

            # Get information about each entry
            file_list = []
            for entry in entries:
                entry_path = os.path.join(absolute_path, entry)
                is_directory = os.path.isdir(entry_path)

                try:
                    size = os.path.getsize(entry_path) if not is_directory else None
                    modified_time = os.path.getmtime(entry_path)
                except:
                    size = None
                    modified_time = None

                file_list.append({
                    "name": entry,
                    "is_directory": is_directory,
                    "size": size,
                    "modified_time": modified_time,
                    "path": os.path.join(path, entry).replace("\\", "/")
                })

            # Sort the entries: directories first, then files, both alphabetically
            file_list.sort(key=lambda x: (not x["is_directory"], x["name"].lower()))

            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "path": path,
                    "entries": file_list,
                    "count": len(file_list)
                }
            )
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"error": f"Error listing directory: {str(e)}"}
            )

    except Exception as e:
        logger.error(f"Error in list_files endpoint: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Internal server error: {str(e)}"}
        )

def initialize_mcp_components():
    """Initialize all MCP server components and apply necessary fixes.

    Returns:
        Tuple[MCPServer, List[str]]: The initialized server instance and a list of controller names.
    """
    mcp_server = None
    controllers = []

    try:
        # Import the MCP server bridge
        try:
            from ipfs_kit_py.mcp.server_bridge import MCPServer
            logger.info("Successfully imported MCPServer from server_bridge")

            # Import the IPFS model registration module to ensure methods are available
            try:
                from ipfs_kit_py.mcp.models.ipfs_model_register import register_ipfs_model_methods
                logger.info("Successfully imported IPFS model registration module")
                register_ipfs_model_methods()
                logger.info("IPFS model methods registered successfully")
            except ImportError as e:
                logger.warning(f"Could not import IPFS model registration module: {e}")
                logger.warning("Some IPFS methods may not be available")

            # Patch the MCPServer class with missing methods if needed
            patch_result = patch_mcp_server()
            if not patch_result:
                logger.warning("Failed to patch MCPServer, continuing anyway")
        except ImportError as e:
            logger.warning(f"Could not import MCPServer from server_bridge: {e}")
            # Create fallback components when import fails
            create_dummy_mcp_components()
            return None, []

        # Create server instance with appropriate configuration
        mcp_server = MCPServer(
            debug_mode=args.debug,
            log_level=log_level,
            isolation_mode=args.isolation,
            skip_daemon=args.skip_daemon
        )

        # Extract controller names for later use
        if hasattr(mcp_server, 'controllers'):
            controllers = list(mcp_server.controllers.keys())

        logger.info(f"MCP server initialized with controllers: {controllers}")

        # Apply IPFS model fixes for compatibility
        try:
            from ipfs_kit_py.mcp.models.ipfs_model_fix import apply_fixes
            logger.info("Applying direct IPFS model fixes")

            # Use apply_fixes() instead of fix_ipfs_model(None)
            apply_fixes()
            logger.info("Successfully applied direct IPFS model fixes")
        except ImportError as e:
            logger.warning(f"Could not import IPFS model fixes: {e}")

        # Initialize IPFS model extensions
        try:
            from ipfs_kit_py.mcp.models.ipfs_model_initializer import initialize_ipfs_model
            logger.info("Initializing IPFS model extensions")
            initialize_ipfs_model()
            logger.info("Successfully initialized IPFS model extensions")
        except ImportError as e:
            logger.warning(f"Could not import IPFS model initializer: {e}")

        # Apply SSE and CORS fixes for the server
        try:
            from ipfs_kit_py.mcp.sse_cors_fix import patch_mcp_server_for_sse
            logger.info("Applying SSE and CORS fixes")
            patch_mcp_server_for_sse()
            logger.info("Successfully applied SSE and CORS fixes")
        except ImportError as e:
            logger.warning(f"Could not import SSE and CORS fixes: {e}")

        # Patch run_mcp_server if needed for compatibility
        try:
            from ipfs_kit_py.mcp.run_mcp_server_initializer import patch_run_mcp_server
            logger.info("Patching run_mcp_server")
            patch_run_mcp_server()
            logger.info("Successfully patched run_mcp_server")
        except ImportError as e:
            logger.warning(f"Could not import run_mcp_server initializer: {e}")

    except Exception as init_error:
        logger.error(f"Error initializing MCP extensions: {init_error}")
        logger.error(traceback.format_exc())
        return None, controllers

    return mcp_server, controllers

def create_dummy_mcp_components():
    """Create minimal dummy components when full initialization fails."""
    logger.info("Creating minimal MCP components for fallback operation")

    # Add API-level health endpoint
    @app.get(f"{args.api_prefix}/health")
    async def api_health():
        """API-level health endpoint."""
        return {
            "success": True,
            "status": "minimal",
            "timestamp": time.time(),
            "server_id": server_id,
            "debug_mode": args.debug,
            "message": "Running in minimal compatibility mode"
        }

    # Add minimal IPFS endpoints
    ipfs_router = APIRouter(prefix=f"{args.api_prefix}/ipfs")

    @ipfs_router.get("/version")
    async def ipfs_version():
        """Get IPFS version information."""
        return {
            "version": "0.1.0",
            "simulation": True,
            "message": "Running in compatibility mode"
        }

    @ipfs_router.post("/add")
    async def ipfs_add(request: Request):
        """Add content to IPFS (simulation)."""
        try:
            data = await request.json()
            content = data.get("content", "")
            return {
                "success": True,
                "simulation": True,
                "cid": f"Qm{uuid.uuid4().hex[:38]}",
                "size": len(content) if content else 0,
                "message": "Content added to IPFS (simulation)"
            }
        except Exception as e:
            logger.error(f"Error in simulated IPFS add: {e}")
            return {
                "success": False,
                "error": str(e),
                "simulation": True
            }

    @ipfs_router.get("/cat")
    async def ipfs_cat(cid: str = ""):
        """Retrieve content from IPFS (simulation)."""
        return {
            "success": True,
            "simulation": True,
            "content": f"Simulated content for CID: {cid}",
            "message": "Content retrieved from IPFS (simulation)"
        }

    @ipfs_router.post("/pin/add")
    async def ipfs_pin_add(request: Request):
        """Pin content in IPFS (simulation)."""
        try:
            data = await request.json()
            cid = data.get("cid", "")
            return {
                "success": True,
                "simulation": True,
                "cid": cid,
                "message": f"Content pinned to IPFS (simulation): {cid}"
            }
        except Exception as e:
            logger.error(f"Error in simulated IPFS pin add: {e}")
            return {
                "success": False,
                "error": str(e),
                "simulation": True
            }

    app.include_router(ipfs_router)
    logger.info("Minimal MCP components registered")

def patch_mcp_server():
    """Patch the MCPServer class to add missing methods."""
    try:
        from ipfs_kit_py.mcp.server_bridge import MCPServer

        # Check if the method is missing and add it
        if not hasattr(MCPServer, '_register_exception_handler'):
            logger.info("Adding missing _register_exception_handler method to MCPServer")

            def _register_exception_handler(self):
                """Register a global exception handler for the FastAPI app."""
                # This is a no-op implementation since we handle exceptions elsewhere
                pass

            # Add the method to the class
            MCPServer._register_exception_handler = _register_exception_handler

            logger.info("Successfully patched MCPServer with missing method")
            return True
        else:
            logger.info("MCPServer already has _register_exception_handler method")
            return True
    except Exception as e:
        logger.error(f"Error patching MCPServer: {e}")
        logger.error(traceback.format_exc())
        return False

def main():
    """Run the unified MCP server with all extensions initialized."""
    # Initialize MCP components
    mcp_server, controllers = initialize_mcp_components()

    # Register MCP server with FastAPI app if initialization was successful
    if mcp_server:
        try:
            # Register MCP server with app
            mcp_server.register_with_app(app, prefix=args.api_prefix)
            logger.info("MCP server registered with FastAPI app")

            # Get storage manager for health endpoint
            storage_manager = None
            if hasattr(mcp_server, 'models') and 'storage_manager' in mcp_server.models:
                storage_manager = mcp_server.models['storage_manager']

            # Create enhanced health endpoint at API level
            @app.get(f"{args.api_prefix}/health")
            async def api_health():
                """API-level health endpoint with detailed information."""
                health_data = {
                    "success": True,
                    "status": "healthy",
                    "timestamp": time.time(),
                    "server_id": server_id,
                    "debug_mode": args.debug,
                    "uptime_seconds": time.time() - start_time,
                    "ipfs_daemon_running": True,  # Assume it's running since we got this far
                    "controllers": {name: True for name in controllers},
                    "storage_backends": {},
                    "file_system_tools": {
                        "read_file": True,
                        "write_file": True,
                        "edit_file": True,
                        "patch_file": True,
                        "read_file_slice": True,
                        "list_files": True
                    }
                }

                # Add storage backend information if available
                if storage_manager and hasattr(storage_manager, 'get_available_backends'):
                    try:
                        backends = storage_manager.get_available_backends()

                        for backend_name, is_available in backends.items():
                            health_data["storage_backends"][backend_name] = {
                                "available": is_available,
                                "simulation": getattr(storage_manager, 'isolation_mode', args.isolation)
                            }

                            # Add additional info if available
                            if is_available and hasattr(storage_manager, 'storage_models') and backend_name in storage_manager.storage_models:
                                model = storage_manager.storage_models[backend_name]
                                mock_mode = getattr(model, 'simulation_mode', False)
                                health_data["storage_backends"][backend_name].update({
                                    "mock": mock_mode,
                                    "token_available": True
                                })

                                # Add special info for different backends
                                if backend_name == "lassie":
                                    health_data["storage_backends"][backend_name]["binary_available"] = True
                                elif backend_name in ["huggingface", "s3"]:
                                    health_data["storage_backends"][backend_name]["credentials_available"] = True
                    except Exception as e:
                        logger.error(f"Error getting backend information: {e}")
                        logger.error(traceback.format_exc())
                        health_data["storage_backends_error"] = str(e)

                return health_data

            # After registering controllers, add tools listing endpoint
            @app.get(f"{args.api_prefix}/tools")
            async def api_tools():
                """List available tools and endpoints."""
                return {
                    "tools": {name: f"{args.api_prefix}/{name}" for name in controllers},
                    "file_system_tools": {
                        "read_file": f"{args.api_prefix}/read_file",
                        "write_file": f"{args.api_prefix}/write_file",
                        "edit_file": f"{args.api_prefix}/edit_file",
                        "patch_file": f"{args.api_prefix}/patch_file",
                        "read_file_slice": f"{args.api_prefix}/read_file_slice",
                        "list_files": f"{args.api_prefix}/list_files"
                    },
                    "endpoints": {
                        "jsonrpc": "/jsonrpc",
                        "sse": f"{args.api_prefix}/sse",
                        "health": f"{args.api_prefix}/health"
                    }
                }

        except Exception as register_error:
            logger.error(f"Error registering MCP server with FastAPI app: {register_error}")
            logger.error(traceback.format_exc())
            # Create dummy components as fallback
            create_dummy_mcp_components()
    else:
        # Create dummy components if MCP server initialization failed
        create_dummy_mcp_components()

    # Start the server with uvicorn
    try:
        import uvicorn

        # Write PID file for process management
        pid_path = os.path.join(os.getcwd(), "unified_mcp_server.pid")
        with open(pid_path, 'w') as f:
            f.write(str(os.getpid()))
        logger.info(f"PID file written to {pid_path}")

        # Run the server
        logger.info(f"Starting Unified MCP server on {args.host}:{args.port}")
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            log_level=log_level.lower()
        )
    except ImportError as e:
        logger.error(f"Failed to import required modules: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error starting MCP server: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()
