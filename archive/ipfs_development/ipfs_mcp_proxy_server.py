#!/usr/bin/env python3
"""
IPFS MCP Proxy Server

This standalone FastAPI-based server provides a proxy layer between
MCP clients (like VS Code) and the IPFS functionality. It handles
tool requests directly without requiring modifications to the core
MCP server.
"""

import os
import sys
import json
import logging
import anyio
from typing import Dict, Any
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from starlette.responses import JSONResponse
from typing import Dict, Any, List, Optional, AsyncGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='ipfs_mcp_proxy.log'
)
logger = logging.getLogger(__name__)

# Add console handler
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console.setFormatter(formatter)
logger.addHandler(console)

# Ensure the current directory is in the path
sys.path.append(os.getcwd())

# Mark these features as unavailable for initial testing
IPFS_EXTENSIONS_AVAILABLE = False
FS_TOOLS_AVAILABLE = False
logger.info("Using only basic filesystem tools for initial testing")

# Basic tools that can work without IPFS
async def list_files(directory=".", recursive=False, include_hidden=False):
    """List files in the specified directory."""
    try:
        result = []
        items = []
        stats = {}
        
        # List files and directories
        for item in os.listdir(directory):
            if not include_hidden and item.startswith('.'):
                continue
            
            path = os.path.join(directory, item)
            is_dir = os.path.isdir(path)
            
            # Get basic item stats
            item_info = {
                "name": item,
                "path": path,
                "is_directory": is_dir
            }
            
            # Add additional stats
            try:
                stat_info = os.stat(path)
                item_info["size_bytes"] = stat_info.st_size
                item_info["modified_time"] = stat_info.st_mtime
                
                # Count items in directory
                if is_dir:
                    try:
                        item_info["item_count"] = len(os.listdir(path))
                    except:
                        item_info["item_count"] = 0
                
                # Check if it's a binary file
                if not is_dir:
                    try:
                        with open(path, 'r') as f:
                            f.read(1024)
                        item_info["is_binary"] = False
                    except UnicodeDecodeError:
                        item_info["is_binary"] = True
                
            except Exception as e:
                logger.warning(f"Error getting stats for {path}: {e}")
            
            items.append(item_info)
            
            # Recursive listing
            if recursive and is_dir:
                try:
                    # Recursively list subdirectory
                    sub_items = await list_files(path, recursive, include_hidden)
                    if isinstance(sub_items, dict) and "items" in sub_items:
                        result.extend(sub_items["items"])
                except Exception as e:
                    logger.warning(f"Error recursively listing {path}: {e}")
        
        # Create file statistics
        dirs = [item for item in items if item.get("is_directory")]
        files = [item for item in items if not item.get("is_directory")]
        
        # Get extensions
        extensions = {}
        for item in files:
            name = item.get("name", "")
            if "." in name:
                ext = name.split(".")[-1].lower()
                if ext in extensions:
                    extensions[ext]["count"] += 1
                    extensions[ext]["total_size"] += item.get("size_bytes", 0)
                else:
                    extensions[ext] = {
                        "count": 1,
                        "total_size": item.get("size_bytes", 0),
                        "human_readable_size": f"{item.get('size_bytes', 0) / 1024:.2f} KB"
                    }
        
        # Calculate total size
        total_size = sum(item.get("size_bytes", 0) for item in items)
        
        # Construct the result
        return {
            "success": True,
            "base_directory": directory,
            "items": items,
            "statistics": {
                "total_files": len(files),
                "total_directories": len(dirs),
                "total_size_bytes": total_size,
                "extensions": extensions,
                "human_readable_size": f"{total_size / 1024 / 1024:.2f} MB"
            }
        }
    except Exception as e:
        logger.error(f"Error listing files in {directory}: {e}")
        return {
            "success": False,
            "error": str(e),
            "directory": directory
        }

async def read_file(path):
    """Read a file from the filesystem."""
    try:
        # Check if the file exists
        if not os.path.exists(path):
            return {
                "success": False,
                "error": f"File not found: {path}",
                "path": path
            }
        
        # Check if it's a directory
        if os.path.isdir(path):
            return {
                "success": False,
                "error": f"Path is a directory, not a file: {path}",
                "path": path
            }
        
        # Get file stats
        stat_info = os.stat(path)
        file_size = stat_info.st_size
        modified_time = stat_info.st_mtime
        
        # Read the file
        try:
            with open(path, 'r') as f:
                content = f.read()
            is_binary = False
        except UnicodeDecodeError:
            # Try reading as binary
            with open(path, 'rb') as f:
                content = f.read()
            import base64
            content = base64.b64encode(content).decode('utf-8')
            is_binary = True
        
        return {
            "success": True,
            "path": path,
            "content": content,
            "size_bytes": file_size,
            "modified_time": modified_time,
            "is_binary": is_binary
        }
    except Exception as e:
        logger.error(f"Error reading file {path}: {e}")
        return {
            "success": False,
            "error": str(e),
            "path": path
        }

async def write_file(path, content):
    """Write content to a file."""
    try:
        # Create parent directories if they don't exist
        parent_dir = os.path.dirname(path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)
        
        # Check for binary content (base64 encoded)
        if isinstance(content, str) and content.startswith('base64:'):
            import base64
            content = base64.b64decode(content[7:])
            with open(path, 'wb') as f:
                f.write(content)
        else:
            # Write text content
            with open(path, 'w') as f:
                f.write(content)
        
        # Get file stats
        stat_info = os.stat(path)
        file_size = stat_info.st_size
        modified_time = stat_info.st_mtime
        
        return {
            "success": True,
            "path": path,
            "size_bytes": file_size,
            "modified_time": modified_time
        }
    except Exception as e:
        logger.error(f"Error writing to file {path}: {e}")
        return {
            "success": False,
            "error": str(e),
            "path": path
        }

# Initialize FastAPI
app = FastAPI(
    title="IPFS MCP Proxy Server",
    description="Proxy server for IPFS MCP integration",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# SSE connections and events
sse_connections = {}

# Generate unique connection ID
def generate_connection_id():
    return str(uuid.uuid4())

# SSE endpoint for MCP protocol
@app.get("/sse")
async def sse_endpoint(request: Request):
    # Server-Sent Events (SSE) endpoint for MCP protocol.
    connection_id = generate_connection_id()
    
    # Generator for SSE events
    async def event_generator():
        # Initial connection event
        connection_event = {
            "type": "connection",
            "connection_id": connection_id
        }
        yield {
            "event": "connection",
            "id": connection_id,
            "data": json.dumps(connection_event)
        }
        
        # Store connection information
        send_stream, receive_stream = anyio.create_memory_object_stream(0)
        sse_connections[connection_id] = {
            "send_stream": send_stream,
            "last_event_time": time.time()
        }
        
        try:
            # Send heartbeat every 30 seconds to keep connection alive
            while True:
                # Check for new events in the queue
                try:
                    with anyio.fail_after(30):
                        event = await receive_stream.receive()
                    yield event
                except TimeoutError:
                    # Send heartbeat if no events for 30 seconds
                    heartbeat_event = {
                        "type": "heartbeat",
                        "timestamp": time.time()
                    }
                    yield {
                        "event": "heartbeat",
                        "id": f"{connection_id}-heartbeat-{int(time.time())}",
                        "data": json.dumps(heartbeat_event)
                    }
                    # Update last event time
                    if connection_id in sse_connections:
                        sse_connections[connection_id]["last_event_time"] = time.time()
        except Exception as e:
            logger.error(f"SSE connection error: {e}")
        finally:
            # Clean up connection
            if connection_id in sse_connections:
                del sse_connections[connection_id]
            receive_stream.close()
            send_stream.close()
            logger.info(f"SSE connection closed: {connection_id}")
    
    # Return SSE response
    return EventSourceResponse(event_generator())

# Endpoint to send event to a specific connection
@app.post("/internal/send_event/{connection_id}")
async def send_event(connection_id: str, event: Dict[str, Any]):
    # Send an event to a specific SSE connection.
    # This is used internally by the server.
    if connection_id in sse_connections:
        event_id = f"{connection_id}-{int(time.time())}"
        await sse_connections[connection_id]["send_stream"].send({
            "event": event.get("event", "message"),
            "id": event_id,
            "data": json.dumps(event.get("data", {}))
        })
        return {"success": True, "event_id": event_id}
    else:
        return {"success": False, "error": "Connection not found"}

# MCP messages endpoint for compatibility with VSCode extension
@app.post("/messages/")
async def handle_messages(request: Request, background_tasks: BackgroundTasks):
    # Handle MCP messages for compatibility with VSCode extension.
    data = await request.json()
    
    # Extract session ID from query parameters
    session_id = request.query_params.get("session_id")
    if not session_id:
        return JSONResponse(
            status_code=400,
            content={"error": "Session ID is required"}
        )
    
    # Process message in background to allow quick response
    background_tasks.add_task(process_message, session_id, data)
    
    # Return accepted response immediately
    return JSONResponse(
        status_code=202,
        content={"status": "Accepted"}
    )

# Process MCP messages
async def process_message(session_id: str, message: Dict[str, Any]):
    # Process an MCP message from VSCode extension.
    # Log the message
    logger.info(f"Processing MCP message for session {session_id}")
    
    try:
        # Handle different message types
        if "name" in message and "args" in message:
            # This is a tool call
            tool_result = await handle_tool(Request(scope={"type": "http"}))
            
            # Send result back through SSE
            if session_id in sse_connections:
                event_data = {
                    "type": "tool_result",
                    "request_id": message.get("request_id", "unknown"),
                    "result": tool_result
                }
                await send_event(session_id, {
                    "event": "tool_result",
                    "data": event_data
                })
        else:
            # Unknown message type
            logger.warning(f"Unknown message type: {message}")
    except Exception as e:
        logger.error(f"Error processing message: {e}")
# Virtual filesystem components
fs_journal = None
fs_ipfs_bridge = None
virtual_fs = None

# IPFS mock tool implementations
async def add_mock_content(content, filename=None, pin=True):
    """Mock implementation of ipfs_add."""
    logger.info(f"Mock IPFS add: content length {len(content)}, filename {filename}, pin {pin}")
    # Make sure to convert the dict to a coroutine result
    # Use anyio.sleep(0) to ensure it's actually awaitable
    await anyio.sleep(0)
    return {
        "success": True,
        "cid": "QmTestCid",
        "name": filename or "test.txt",
        "size": len(content) if content else 0,
        "pinned": pin
    }

async def cat_mock_content(cid):
    """Mock implementation of ipfs_cat."""
    logger.info(f"Mock IPFS cat: cid {cid}")
    await anyio.sleep(0)
    return {
        "success": True,
        "cid": cid,
        "content": f"Test IPFS content for {cid}",
        "content_encoding": "text",
        "size": 25
    }

async def pin_mock_content(cid, recursive=True):
    """Mock implementation of ipfs_pin."""
    logger.info(f"Mock IPFS pin: cid {cid}, recursive {recursive}")
    await anyio.sleep(0)
    return {
        "success": True,
        "cid": cid,
        "pins": [cid],
        "recursive": recursive
    }

# Map tool names to functions - only basic filesystem operations for now
TOOL_MAP = {
    # Basic Filesystem
    "list_files": list_files,
    "read_file": read_file,
    "write_file": write_file,
    
    # Placeholder stubs for IPFS tools (for testing the MCP integration)
    "ipfs_add": add_mock_content,
    "ipfs_cat": cat_mock_content,
    "ipfs_pin": pin_mock_content
}

# Clean tool map by removing None values
TOOL_MAP = {k: v for k, v in TOOL_MAP.items() if v is not None}

# Get available tools
AVAILABLE_TOOLS = list(TOOL_MAP.keys())

# Health endpoint
@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "success": True,
        "status": "healthy",
        "ipfs_extensions_available": IPFS_EXTENSIONS_AVAILABLE,
        "fs_tools_available": FS_TOOLS_AVAILABLE,
        "available_tools": AVAILABLE_TOOLS
    }

# Initialize endpoint
@app.get("/initialize")
async def initialize():
    """Initialize endpoint for MCP protocol."""
    return {
        "capabilities": {
            "tools": AVAILABLE_TOOLS,
            "resources": [
                "ipfs://info",
                "ipfs://stats",
                "storage://backends",
                "file://",
                "mfs://root"
            ]
        },
        "serverInfo": {
            "name": "IPFS MCP Proxy Server",
            "version": "1.0.0",
            "implementationName": "ipfs-kit-py-proxy"
        }
    }

# Tool Handler
@app.post("/mcp/tools")
async def handle_tool(request: Request):
    """Handle MCP tool requests."""
    data = await request.json()
    
    tool_name = data.get("name")
    args = data.get("args", {})
    
    logger.info(f"Tool request received: {tool_name} with args: {args}")
    
    if not tool_name:
        return JSONResponse(
            status_code=400,
            content={"error": "Tool name is required"}
        )
    
    if tool_name not in TOOL_MAP:
        return JSONResponse(
            status_code=404,
            content={"error": f"Tool '{tool_name}' not found"}
        )
    
    tool_impl = TOOL_MAP[tool_name]
    
    try:
        # Call the tool with args
        result = await tool_impl(**args)
        return result
    except Exception as e:
        logger.error(f"Error executing tool '{tool_name}': {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Error executing tool: {str(e)}"}
        )

# Simplified initialization
async def init_services():
    """Initialize basic services."""
    logger.info("Basic services initialized")

@app.on_event("startup")
async def startup_event():
    """Run initialization on startup."""
    await init_services()
    logger.info(f"IPFS MCP Proxy Server started with {len(AVAILABLE_TOOLS)} tools")
    logger.info(f"Available tools: {', '.join(AVAILABLE_TOOLS)}")

def main():
    """Main function to run the server."""
    # Print server information
    print("=== IPFS MCP Proxy Server ===")
    print(f"IPFS Extensions Available: {IPFS_EXTENSIONS_AVAILABLE}")
    print(f"FS Tools Available: {FS_TOOLS_AVAILABLE}")
    print(f"Available Tools: {len(AVAILABLE_TOOLS)}")
    print("Starting server on http://localhost:8000")
    print("Use this URL in your VS Code MCP extension settings")
    
    # Run the server
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()
