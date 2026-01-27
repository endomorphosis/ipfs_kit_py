#!/usr/bin/env python3
"""
Fix MCP IPFS Extensions

This script adds SSE support to the IPFS MCP Proxy Server to ensure compatibility
with VSCode MCP extension and other MCP clients.
"""

import os
import sys
import re
from pathlib import Path

def read_file(path):
    """Read a file's contents."""
    with open(path, 'r') as f:
        return f.read()

def write_file(path, content):
    """Write content to a file."""
    with open(path, 'w') as f:
        f.write(content)

def add_imports(content):
    """Add required imports for SSE support."""
    # Find the existing imports section
    import_section = re.search(r'import .*?\n\n', content, re.DOTALL)
    if not import_section:
        return content

    # Add our new imports
    new_imports = [
        "from typing import Dict, Any, List, Optional, AsyncGenerator",
        "from fastapi import BackgroundTasks",
        "from sse_starlette.sse import EventSourceResponse",
        "import uuid",
        "import json",
        "import time",
        "import anyio"
    ]

    # Check which imports already exist
    for imp in new_imports:
        if imp not in content:
            content = content.replace(
                import_section.group(0),
                import_section.group(0).rstrip() + f"\n{imp}\n\n"
            )

    return content

def add_sse_endpoint(content):
    """Add SSE endpoint for MCP protocol."""
    # Use a cleaner approach to avoid docstring issues
    sse_code = '''
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
        send_stream, receive_stream = anyio.create_memory_object_stream(100)
        sse_connections[connection_id] = {
            "send_stream": send_stream,
            "receive_stream": receive_stream,
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
'''

    # Check if the SSE endpoint already exists
    if "@app.get(\"/sse\")" in content:
        return content

    # Find a good place to insert the SSE endpoint (after the @app routes)
    routes_section = re.search(r'# Add CORS middleware.*?\n\n', content, re.DOTALL)
    if routes_section:
        position = routes_section.end()
        content = content[:position] + sse_code + content[position:]

    return content

def add_sse_starlette_requirement(content):
    """Add sse-starlette requirement for StreamResponse."""
    if "sse-starlette" not in content:
        requirements = [
            "sse-starlette>=1.0.0"
        ]

        for req in requirements:
            if req not in content:
                content += f"\n{req}"

    return content

def fix_mcp_proxy_server():
    """Apply fixes to the IPFS MCP Proxy Server."""
    proxy_server_path = "ipfs_mcp_proxy_server.py"
    requirements_path = "requirements.txt"

    # Read files
    proxy_server_content = read_file(proxy_server_path)
    requirements_content = read_file(requirements_path) if os.path.exists(requirements_path) else ""

    # Apply fixes
    proxy_server_content = add_imports(proxy_server_content)
    proxy_server_content = add_sse_endpoint(proxy_server_content)
    requirements_content = add_sse_starlette_requirement(requirements_content)

    # Write files back
    write_file(proxy_server_path, proxy_server_content)
    write_file(requirements_path, requirements_content)

    print(f"✅ Added SSE endpoint to {proxy_server_path}")
    print(f"✅ Updated {requirements_path} with sse-starlette requirement")

    # Install sse-starlette
    print("Installing sse-starlette...")
    os.system("pip install sse-starlette>=1.0.0")

    print("\nFixes applied. Please restart the IPFS MCP Proxy Server.")

if __name__ == "__main__":
    fix_mcp_proxy_server()
