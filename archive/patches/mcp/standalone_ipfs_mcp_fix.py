#!/usr/bin/env python3
"""
IPFS Daemon Integration Fix for MCP Server

This script:
1. Connects directly to the IPFS daemon via its API
2. Creates a basic standalone MCP server that bypasses the problematic code
3. Provides a minimal implementation for testing IPFS functionality
"""

import os
import sys
import time
import signal
import subprocess
import tempfile
import json
from pathlib import Path

# Create a minimal FastAPI app that interacts directly with IPFS
STANDALONE_API_CODE = """
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
import subprocess
import json
import time
import base64
import os
import anyio
import uvicorn

# Create FastAPI app
app = FastAPI(
    title="IPFS MCP Standalone Server",
    description="Minimal MCP server with IPFS integration",
    version="0.1.0"
)

# Store operations for monitoring
operations = []

@app.get("/api/v0/mcp/health")
async def health_check():
    """Health check endpoint."""
    # Check IPFS daemon is running
    try:
        result = subprocess.run(
            ["ipfs", "id", "--format=<id>"],
            check=False,
            capture_output=True,
            text=True
        )
        ipfs_running = result.returncode == 0 and result.stdout.strip()
    except Exception:
        ipfs_running = False
    
    return {
        "success": True,
        "status": "ok",
        "timestamp": time.time(),
        "server_id": "standalone-mcp-ipfs-fix",
        "debug_mode": True,
        "isolation_mode": False,
        "ipfs_daemon_running": ipfs_running,
        "auto_start_daemons_enabled": False,
        "controllers": {
            "ipfs": True,
            "cli": True
        }
    }

@app.post("/api/v0/mcp/ipfs/add/json")
async def add_content(request: Request):
    """Add content to IPFS and return the CID."""
    try:
        # Get request body
        data = await request.json()
        content = data.get("content", "")
        
        if not content:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "Content is required",
                    "error_type": "ValidationError",
                    "timestamp": time.time()
                }
            )
        
        start_time = time.time()
        operation_id = f"add-{int(start_time * 1000)}"
        
        # Call IPFS directly
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(content.encode('utf-8'))
            tmp.flush()
            
            try:
                # Use IPFS CLI to add the content
                result = subprocess.run(
                    ["ipfs", "add", "-q", tmp.name],
                    check=True,
                    capture_output=True,
                    text=True
                )
                
                # Get the CID from the result
                cid = result.stdout.strip()
                
                # Log the operation
                operations.append({
                    "operation_id": operation_id,
                    "type": "add",
                    "timestamp": start_time,
                    "duration": time.time() - start_time,
                    "cid": cid
                })
                
                # Return success
                return {
                    "success": True,
                    "operation_id": operation_id,
                    "duration_ms": (time.time() - start_time) * 1000,
                    "cid": cid,
                    "Hash": cid,  # For compatibility with older clients
                    "content_size_bytes": len(content.encode('utf-8'))
                }
            finally:
                # Clean up temp file
                os.unlink(tmp.name)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Error adding content: {str(e)}",
                "error_type": type(e).__name__,
                "timestamp": time.time()
            }
        )

@app.get("/api/v0/mcp/ipfs/cat/{cid}")
async def get_content(cid: str):
    """Get content from IPFS by CID."""
    try:
        # Use IPFS CLI to get the content
        result = subprocess.run(
            ["ipfs", "cat", cid],
            check=True,
            capture_output=True
        )
        
        # Return the content directly
        return Response(content=result.stdout)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Error getting content: {str(e)}",
                "error_type": type(e).__name__,
                "timestamp": time.time()
            }
        )

@app.get("/api/v0/mcp/operations")
async def get_operations():
    """Get operation log for debugging."""
    return {
        "success": True,
        "operations": operations,
        "count": len(operations),
        "timestamp": time.time()
    }

@app.post("/api/v0/mcp/ipfs/pin/add")
async def pin_content(request: Request):
    """Pin content to IPFS."""
    try:
        # Get request body
        data = await request.json()
        cid = data.get("cid", "")
        
        if not cid:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "CID is required",
                    "error_type": "ValidationError",
                    "timestamp": time.time()
                }
            )
        
        start_time = time.time()
        operation_id = f"pin-{int(start_time * 1000)}"
        
        # Use IPFS CLI to pin the content
        result = subprocess.run(
            ["ipfs", "pin", "add", cid],
            check=True,
            capture_output=True,
            text=True
        )
        
        # Log the operation
        operations.append({
            "operation_id": operation_id,
            "type": "pin",
            "timestamp": start_time,
            "duration": time.time() - start_time,
            "cid": cid
        })
        
        # Return success
        return {
            "success": True,
            "operation_id": operation_id,
            "duration_ms": (time.time() - start_time) * 1000,
            "cid": cid
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Error pinning content: {str(e)}",
                "error_type": type(e).__name__,
                "timestamp": time.time()
            }
        )

@app.post("/api/v0/mcp/ipfs/pin/rm")
async def unpin_content(request: Request):
    """Unpin content from IPFS."""
    try:
        # Get request body
        data = await request.json()
        cid = data.get("cid", "")
        
        if not cid:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "CID is required",
                    "error_type": "ValidationError",
                    "timestamp": time.time()
                }
            )
        
        start_time = time.time()
        operation_id = f"unpin-{int(start_time * 1000)}"
        
        # Use IPFS CLI to unpin the content
        result = subprocess.run(
            ["ipfs", "pin", "rm", cid],
            check=True,
            capture_output=True,
            text=True
        )
        
        # Log the operation
        operations.append({
            "operation_id": operation_id,
            "type": "unpin",
            "timestamp": start_time,
            "duration": time.time() - start_time,
            "cid": cid
        })
        
        # Return success
        return {
            "success": True,
            "operation_id": operation_id,
            "duration_ms": (time.time() - start_time) * 1000,
            "cid": cid
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Error unpinning content: {str(e)}",
                "error_type": type(e).__name__,
                "timestamp": time.time()
            }
        )

@app.get("/api/v0/mcp/ipfs/pin/ls")
async def list_pins():
    """List pinned content."""
    try:
        start_time = time.time()
        
        # Use IPFS CLI to list pins
        result = subprocess.run(
            ["ipfs", "pin", "ls", "--type=recursive"],
            check=True,
            capture_output=True,
            text=True
        )
        
        # Parse the output to get the pins
        pins = []
        for line in result.stdout.strip().split("\n"):
            if line:
                parts = line.split()
                if len(parts) >= 1:
                    pins.append({
                        "cid": parts[0],
                        "type": "recursive"
                    })
        
        # Return the pins
        return {
            "success": True,
            "operation_id": f"ls-pins-{int(start_time * 1000)}",
            "duration_ms": (time.time() - start_time) * 1000,
            "pins": pins,
            "count": len(pins)
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Error listing pins: {str(e)}",
                "error_type": type(e).__name__,
                "timestamp": time.time()
            }
        )

if __name__ == "__main__":
    import uvicorn
    import argparse
    
    parser = argparse.ArgumentParser(description="IPFS MCP Standalone Server")
    parser.add_argument("--port", type=int, default=8765, help="Port to run the server on")
    parser.add_argument("--host", default="localhost", help="Host to bind to")
    
    args = parser.parse_args()
    
    print(f"Starting IPFS MCP Standalone Server on {args.host}:{args.port}")
    print(f"API URL: http://{args.host}:{args.port}/api/v0/mcp")
    
    uvicorn.run(app, host=args.host, port=args.port)
"""

def check_ipfs_daemon():
    """Check if IPFS daemon is running."""
    try:
        result = subprocess.run(
            ["ipfs", "id", "--format=<id>"],
            check=False,
            capture_output=True,
            text=True
        )
        return result.returncode == 0 and result.stdout.strip()
    except Exception:
        return False

def start_ipfs_daemon():
    """Start IPFS daemon if not already running."""
    if check_ipfs_daemon():
        print("IPFS daemon is already running")
        return True
    
    print("Starting IPFS daemon...")
    try:
        # Start daemon in the background
        process = subprocess.Popen(
            ["ipfs", "daemon"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True  # Detach from parent process
        )
        
        # Wait for daemon to start
        for i in range(30):
            if check_ipfs_daemon():
                print(f"IPFS daemon started successfully after {i+1} seconds")
                return True
            time.sleep(1)
        
        print("Timeout waiting for IPFS daemon to start")
        return False
    except Exception as e:
        print(f"Error starting IPFS daemon: {e}")
        return False

def get_free_port(start=8765, end=8865):
    """Find a free port in the given range."""
    import socket
    
    for port in range(start, end):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return port
        except OSError:
            continue
    
    # Fallback to a random port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

def start_standalone_server():
    """Start the standalone MCP server."""
    # Write the server code to a file
    server_file = "ipfs_mcp_standalone.py"
    with open(server_file, "w") as f:
        f.write(STANDALONE_API_CODE)
    
    # Make it executable
    os.chmod(server_file, 0o755)
    
    # Find a free port
    port = get_free_port()
    
    # Start the server
    print(f"Starting standalone MCP server on port {port}")
    server_process = subprocess.Popen(
        [sys.executable, server_file, "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True  # Detach from parent process
    )
    
    # Wait for server to start
    for i in range(30):
        try:
            # Check server health
            result = subprocess.run(
                ["curl", "-s", f"http://localhost:{port}/api/v0/mcp/health"],
                check=False,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0 and "success" in result.stdout:
                print(f"Standalone MCP server started successfully on port {port}")
                server_info = {
                    "pid": server_process.pid,
                    "port": port,
                    "api_url": f"http://localhost:{port}/api/v0/mcp",
                    "server_file": os.path.abspath(server_file)
                }
                
                # Save server info to file for later
                with open("ipfs_mcp_standalone_info.json", "w") as f:
                    json.dump(server_info, f, indent=2)
                
                return server_info
        except Exception:
            pass
        
        # Check if process is still running
        if server_process.poll() is not None:
            print("Server process exited prematurely")
            stdout, stderr = server_process.communicate()
            print(f"STDOUT: {stdout.decode()}")
            print(f"STDERR: {stderr.decode()}")
            return None
        
        time.sleep(1)
    
    print("Timeout waiting for server to start")
    return None

def test_ipfs_api(port):
    """Test the IPFS API via the standalone MCP server."""
    try:
        # Create a test string
        test_content = f"Test content {time.time()}"
        
        # Try to add the content via the API
        add_command = [
            "curl", "-s",
            "-X", "POST",
            "-H", "Content-Type: application/json",
            "-d", json.dumps({"content": test_content}),
            f"http://localhost:{port}/api/v0/mcp/ipfs/add/json"
        ]
        
        print(f"Testing IPFS API with content: {test_content}")
        result = subprocess.run(add_command, capture_output=True, text=True, check=False)
        
        # Check if the result was successful
        if result.returncode == 0 and "success" in result.stdout:
            try:
                response = json.loads(result.stdout)
                if response.get("success", False) and "cid" in response:
                    cid = response["cid"]
                    print(f"Successfully added content to IPFS with CID: {cid}")
                    
                    # Now try to retrieve the content
                    cat_command = [
                        "curl", "-s",
                        f"http://localhost:{port}/api/v0/mcp/ipfs/cat/{cid}"
                    ]
                    
                    cat_result = subprocess.run(cat_command, capture_output=True, text=True, check=False)
                    
                    if cat_result.returncode == 0 and cat_result.stdout.strip() == test_content:
                        print(f"Successfully retrieved content from IPFS: {cat_result.stdout.strip()}")
                        return {"success": True, "cid": cid, "content": cat_result.stdout.strip()}
                    else:
                        print(f"Failed to retrieve content: {cat_result.stdout}")
                        return False
                else:
                    print(f"Failed to add content: {response}")
                    return False
            except json.JSONDecodeError:
                print(f"Invalid JSON response: {result.stdout}")
                return False
        else:
            print(f"Failed to add content: {result.stdout}")
            return False
    except Exception as e:
        print(f"Error testing IPFS API: {e}")
        return False

def main():
    """Main function to start and test the IPFS MCP integration."""
    print("\n=== IPFS MCP Integration Fix ===\n")
    
    # Step 1: Ensure IPFS daemon is running
    if not start_ipfs_daemon():
        print("Failed to start IPFS daemon")
        return 1
    
    # Step 2: Start standalone MCP server
    server_info = start_standalone_server()
    if not server_info:
        print("Failed to start standalone MCP server")
        return 1
    
    # Step 3: Test IPFS API
    test_result = test_ipfs_api(server_info["port"])
    if not test_result:
        print("\nIPFS API test failed")
        return 1
    
    # Success!
    print("\n=== SUCCESS! ===")
    print("Standalone MCP server is running with IPFS integration")
    print(f"API URL: {server_info['api_url']}")
    print(f"Server PID: {server_info['pid']}")
    print(f"Server script: {server_info['server_file']}")
    print("\nIPFS integration test:")
    print(f"Added content to IPFS with CID: {test_result['cid']}")
    print(f"Retrieved content from IPFS: {test_result['content']}")
    print("\nTo stop this server: kill", server_info["pid"])
    
    # Create a simple script to kill the server later
    with open("stop_mcp_standalone.sh", "w") as f:
        f.write(f"#!/bin/bash\nkill {server_info['pid']}\necho 'Standalone MCP server stopped'\n")
    os.chmod("stop_mcp_standalone.sh", 0o755)
    print("Created stop script: stop_mcp_standalone.sh")
    
    # Instructions on how to start the Lotus and IPFS Cluster daemons
    print("\n=== Other Daemons ===")
    print("To start IPFS Cluster:")
    print("  ipfs-cluster-service daemon")
    print("\nTo start Lotus:")
    print("  lotus daemon")
    print("\nOnce these daemons are running, they can be integrated with the MCP server.")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())