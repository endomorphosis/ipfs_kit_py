#!/usr/bin/env python3
"""
Standalone JSON-RPC Language Server for VS Code

This minimal server implements just the necessary Language Server Protocol endpoints
that VS Code needs to function properly.
"""

import os
import sys
import logging
import argparse
import json
import uuid
from typing import Dict, Any, Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='standalone_jsonrpc.log',
    filemode='w'
)
logger = logging.getLogger(__name__)

# Add console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Create FastAPI app
app = FastAPI(
    title="Standalone VS Code JSON-RPC Language Server",
    description="Minimal server implementing just what VS Code needs",
    version="1.0.0"
)

# Add CORS middleware to allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Track client sessions
client_sessions: Dict[int, Dict[str, Any]] = {}

@app.get("/")
async def root():
    """Root endpoint with server info."""
    return {
        "message": "Standalone VS Code JSON-RPC Language Server is running",
        "endpoints": ["/jsonrpc"],
        "version": "1.0.0",
        "server_id": str(uuid.uuid4())
    }

@app.post("/jsonrpc")
async def jsonrpc_handler(request: Request):
    """JSON-RPC endpoint for VS Code Language Server Protocol."""
    try:
        # Get the request body as JSON
        data = await request.json()
        method = data.get("method", "")
        req_id = data.get("id")

        logger.info(f"Received JSON-RPC request: method={method}, id={req_id}")

        # Handle 'initialize' request
        if method == "initialize":
            logger.info(f"Processing initialize request from VS Code: {json.dumps(data)}")

            # Get client info
            params = data.get("params", {})
            process_id = params.get("processId")

            # Store client session
            if process_id:
                client_sessions[process_id] = {
                    "initialized": True,
                    "rootUri": params.get("rootUri"),
                    "capabilities": params.get("capabilities", {})
                }
                logger.info(f"Registered client session for process ID: {process_id}")

            # Return a standard LSP initialize response
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "capabilities": {
                        "textDocumentSync": {
                            "openClose": True,
                            "change": 1  # Full document sync
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
                        "version": "1.0.0"
                    }
                }
            }

        # Handle 'initialized' notification
        elif method == "initialized":
            logger.info("Received initialized notification from client")
            return {"jsonrpc": "2.0", "id": req_id, "result": None}

        # Handle 'shutdown' request
        elif method == "shutdown":
            logger.info("Received shutdown request from VS Code")

            # Get client info from headers
            client_id = None
            for session_id, session in client_sessions.items():
                if session.get("initialized"):
                    client_id = session_id
                    session["initialized"] = False
                    break

            if client_id:
                logger.info(f"Marked session {client_id} as shutdown")

            return {"jsonrpc": "2.0", "id": req_id, "result": None}

        # Handle 'exit' notification
        elif method == "exit":
            logger.info("Received exit notification from VS Code")

            # Clean up client sessions
            to_remove = []
            for session_id, session in client_sessions.items():
                if not session.get("initialized"):
                    to_remove.append(session_id)

            for session_id in to_remove:
                del client_sessions[session_id]
                logger.info(f"Removed session for process ID: {session_id}")

            return {"jsonrpc": "2.0", "id": req_id, "result": None}

        # For any other method, log it and return a stub response
        else:
            logger.info(f"Received unsupported method: {method}")
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": None
            }

    except Exception as e:
        logger.error(f"Error handling JSON-RPC request: {e}", exc_info=True)
        return {
            "jsonrpc": "2.0",
            "id": data.get("id") if "data" in locals() else None,
            "error": {
                "code": -32603,
                "message": f"Internal server error: {str(e)}"
            }
        }

def main():
    """Run the standalone JSON-RPC Language Server."""
    parser = argparse.ArgumentParser(description="Start the standalone JSON-RPC Language Server")
    parser.add_argument("--port", type=int, default=9995,
                      help="Port number to use (default: 9995)")
    parser.add_argument("--host", type=str, default="0.0.0.0",
                      help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    # Set log level based on debug flag
    if args.debug:
        logger.setLevel(logging.DEBUG)
        console_handler.setLevel(logging.DEBUG)

    print(f"Starting Standalone JSON-RPC Language Server on {args.host}:{args.port}...")
    logger.info(f"Starting server on {args.host}:{args.port}")

    # Run the server
    try:
        uvicorn.run(
            "standalone_jsonrpc:app",
            host=args.host,
            port=args.port,
            log_level="debug" if args.debug else "info"
        )
    except Exception as e:
        logger.error(f"Error starting server: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
