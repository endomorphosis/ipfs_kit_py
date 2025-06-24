#!/usr/bin/env python3
"""
MCP JSON-RPC Proxy Server

This is a simple proxy server that implements the JSON-RPC protocol required by VS Code.
It runs alongside the MCP server and forwards requests as needed.
"""

import os
import sys
import logging
import argparse
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='jsonrpc_proxy.log'
)
logger = logging.getLogger("jsonrpc_proxy")

# Create FastAPI app
app = FastAPI(
    title="MCP JSON-RPC Proxy",
    description="Proxy server for implementing VS Code JSON-RPC protocol for MCP",
    version="0.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint with proxy info."""
    return {
        "message": "MCP JSON-RPC Proxy is running",
        "endpoints": {
            "jsonrpc": "/jsonrpc"
        }
    }

@app.post("/jsonrpc")
async def jsonrpc_handler(request: Request):
    """JSON-RPC endpoint for VS Code Language Server Protocol."""
    try:
        data = await request.json()
        logger.info(f"Received JSON-RPC request: {data}")

        # Handle 'initialize' request
        if data.get("method") == "initialize":
            logger.info("Processing initialize request from VS Code")
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
                        "referencesProvider": True,
                        "documentSymbolProvider": True,
                        "workspaceSymbolProvider": True,
                        "executeCommandProvider": {
                            "commands": []
                        }
                    },
                    "serverInfo": {
                        "name": "MCP IPFS Tools Server",
                        "version": "0.3.0"
                    }
                }
            }
            return JSONResponse(content=response, status_code=200, media_type="application/vscode-jsonrpc")

        # Handle 'shutdown' request
        elif data.get("method") == "shutdown":
            logger.info("Received shutdown request from VS Code")
            response = {"jsonrpc": "2.0", "id": data.get("id"), "result": None}
            return JSONResponse(content=response, status_code=200, media_type="application/vscode-jsonrpc")

        # Handle 'exit' notification
        elif data.get("method") == "exit":
            logger.info("Received exit notification from VS Code")
            response = {"jsonrpc": "2.0", "id": data.get("id"), "result": None}
            return JSONResponse(content=response, status_code=200, media_type="application/vscode-jsonrpc")

        else:
            logger.warning(f"Unhandled JSON-RPC method: {data.get('method')}")
            error_resp = {"jsonrpc": "2.0", "id": data.get("id"),
                          "error": {"code": -32601, "message": f"Method '{data.get('method')}' not found"}}
            return JSONResponse(content=error_resp, status_code=200, media_type="application/vscode-jsonrpc")
    except Exception as e:
        logger.error(f"Error handling JSON-RPC request: {e}")
        error = {"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": str(e)}}
        return JSONResponse(content=error, status_code=500, media_type="application/vscode-jsonrpc")

# Handle JSON-RPC at API prefix for LSP clients
@app.post("/api/v0/jsonrpc")
async def api_jsonrpc_handler(request: Request):
    """JSON-RPC endpoint at API prefix for VS Code Language Server Protocol."""
    return await jsonrpc_handler(request)

def main():
    """Run the JSON-RPC proxy server."""
    parser = argparse.ArgumentParser(description="Start the MCP JSON-RPC Proxy server")
    parser.add_argument("--port", type=int, default=9995,
                      help="Port number to use (default: 9995)")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    args = parser.parse_args()

    log_level = "debug" if args.debug else "info"

    print(f"Starting MCP JSON-RPC Proxy on port {args.port}...")

    # Run the server
    uvicorn.run(
        "mcp_jsonrpc_proxy:app",
        host="0.0.0.0",
        port=args.port,
        reload=False,
        log_level=log_level
    )

if __name__ == "__main__":
    main()
