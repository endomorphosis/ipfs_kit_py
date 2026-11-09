#!/usr/bin/env python3
"""
Enhanced Simple JSON-RPC Server for VS Code Integration

This server implements a simple JSON-RPC protocol that:
1. Responds to VS Code initialize requests
2. Provides proper capabilities for IPFS/MCP tools
3. Handles all required VS Code Language Server Protocol (LSP) methods
4. Has improved error handling and logging
"""

import json
import http.server
import socketserver
import logging
import sys
import os
import argparse
import time
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='vscode_jsonrpc_server.log',
    filemode='a'
)

logger = logging.getLogger('vscode_jsonrpc')
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console.setFormatter(formatter)
logger.addHandler(console)

# Parse arguments
parser = argparse.ArgumentParser(description="Start a simple JSON-RPC server for VS Code integration")
parser.add_argument("--port", type=int, default=9995, help="Port to listen on (default: 9995)")
parser.add_argument("--host", type=str, default="", help="Host to bind to (default: all interfaces)")
parser.add_argument("--debug", action="store_true", help="Enable debug mode")
args = parser.parse_args()

# Constants
SERVER_NAME = "MCP IPFS Tools Server"
SERVER_VERSION = "0.3.0"
START_TIME = time.time()

class VSCodeJSONRPCHandler(http.server.BaseHTTPRequestHandler):
    """Handler for VS Code JSON-RPC requests."""
    
    def log_message(self, format, *args):
        """Override log_message to use our logger."""
        logger.info(format % args)
    
    def send_json_response(self, data, status=200):
        """Send a JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))
    
    def send_error_response(self, request_id, code, message):
        """Send a JSON-RPC error response."""
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message
            }
        }
        self.send_json_response(response)
        
    def handle_initialize(self, request):
        """Handle initialize request."""
        logger.info("Handling initialize request")
        
        # Log client information
        params = request.get("params", {})
        client_info = params.get("clientInfo", {})
        if client_info:
            logger.info(f"Client: {client_info.get('name')} {client_info.get('version')}")
        
        # Create detailed server capabilities
        response = {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": {
                "capabilities": {
                    "textDocumentSync": {
                        "openClose": True,
                        "change": 1,  # Full document sync
                        "willSave": True,
                        "willSaveWaitUntil": True,
                        "save": {
                            "includeText": True
                        }
                    },
                    "completionProvider": {
                        "resolveProvider": True,
                        "triggerCharacters": ["/", ":", "Q", "b"]
                    },
                    "hoverProvider": True,
                    "definitionProvider": True,
                    "referencesProvider": True,
                    "documentSymbolProvider": True,
                    "workspaceSymbolProvider": True,
                    "codeActionProvider": True,
                    "codeLensProvider": {
                        "resolveProvider": True
                    },
                    "documentFormattingProvider": True,
                    "documentRangeFormattingProvider": True,
                    "renameProvider": {
                        "prepareProvider": True
                    }
                },
                "serverInfo": {
                    "name": SERVER_NAME,
                    "version": SERVER_VERSION
                }
            }
        }
        
        logger.debug(f"Sending initialize response: {json.dumps(response)}")
        return response
    
    def handle_shutdown(self, request):
        """Handle shutdown request."""
        logger.info("Handling shutdown request")
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": None
        }
    
    def handle_exit(self, request):
        """Handle exit notification."""
        logger.info("Handling exit notification")
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": None
        }
    
    def handle_text_document_did_open(self, request):
        """Handle textDocument/didOpen notification."""
        logger.info("Handling textDocument/didOpen notification")
        params = request.get("params", {})
        text_document = params.get("textDocument", {})
        logger.info(f"Document opened: {text_document.get('uri')}")
        # No response needed for notifications
        return None
    
    def handle_text_document_did_change(self, request):
        """Handle textDocument/didChange notification."""
        logger.info("Handling textDocument/didChange notification")
        # No response needed for notifications
        return None
    
    def handle_text_document_did_close(self, request):
        """Handle textDocument/didClose notification."""
        logger.info("Handling textDocument/didClose notification")
        # No response needed for notifications
        return None
    
    def handle_completion(self, request):
        """Handle textDocument/completion request."""
        logger.info("Handling completion request")
        
        # Return IPFS-related completion items
        response = {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": [
                {
                    "label": "ipfs add",
                    "kind": 3,  # Function
                    "detail": "Add content to IPFS",
                    "documentation": "Add a file or directory to IPFS."
                },
                {
                    "label": "ipfs cat",
                    "kind": 3,  # Function
                    "detail": "Get content from IPFS",
                    "documentation": "Display the content of a file from IPFS."
                },
                {
                    "label": "ipfs pin",
                    "kind": 3,  # Function
                    "detail": "Pin objects to local storage",
                    "documentation": "Pin objects to local storage to prevent garbage collection."
                }
            ]
        }
        
        return response
    
    def handle_hover(self, request):
        """Handle textDocument/hover request."""
        logger.info("Handling hover request")
        
        # Return minimal hover response
        response = {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": {
                "contents": "MCP IPFS Tools Hover Information"
            }
        }
        
        return response
        
    def do_POST(self):
        """Handle POST requests for JSON-RPC."""
        if self.path == "/jsonrpc":
            try:
                # Get request data
                content_length = int(self.headers.get('Content-Length', 0))
                if content_length == 0:
                    self.send_error_response(None, -32700, "Parse error: no content")
                    return
                
                post_data = self.rfile.read(content_length)
                request = json.loads(post_data.decode('utf-8'))
                request_id = request.get("id")
                method = request.get("method")
                
                logger.info(f"Received JSON-RPC request: {method}")
                logger.debug(f"Request details: {json.dumps(request)}")
                
                # Handle different methods
                handlers = {
                    "initialize": self.handle_initialize,
                    "shutdown": self.handle_shutdown,
                    "exit": self.handle_exit,
                    "textDocument/didOpen": self.handle_text_document_did_open,
                    "textDocument/didChange": self.handle_text_document_did_change,
                    "textDocument/didClose": self.handle_text_document_did_close,
                    "textDocument/completion": self.handle_completion,
                    "textDocument/hover": self.handle_hover,
                }
                
                handler = handlers.get(method)
                if handler:
                    response = handler(request)
                    if response is not None:  # Some notifications don't need responses
                        self.send_json_response(response)
                else:
                    logger.warning(f"Unsupported method: {method}")
                    # Method not found
                    self.send_error_response(request_id, -32601, f"Method not found: {method}")
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
                self.send_error_response(None, -32700, f"Parse error: {str(e)}")
            except Exception as e:
                logger.error(f"Error handling request: {e}", exc_info=True)
                self.send_error_response(None, -32603, f"Internal error: {str(e)}")
        else:
            self.send_error(404)
    
    def do_OPTIONS(self):
        """Handle OPTIONS requests (CORS preflight)."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_GET(self):
        """Handle GET requests."""
        if self.path == "/":
            # Return server info
            response = {
                "message": f"{SERVER_NAME} is running",
                "version": SERVER_VERSION,
                "uptime": time.time() - START_TIME,
                "endpoints": {
                    "jsonrpc": "/jsonrpc"
                },
                "timestamp": datetime.now().isoformat()
            }
            self.send_json_response(response)
        else:
            self.send_error(404)

def main():
    """Run the server."""
    host = args.host
    port = args.port
    
    logger.info(f"Starting {SERVER_NAME} v{SERVER_VERSION} on port {port}")
    logger.info(f"Debug mode: {'enabled' if args.debug else 'disabled'}")
    print(f"Starting JSON-RPC server for VS Code integration on port {port}...")
    
    try:
        with socketserver.TCPServer((host, port), VSCodeJSONRPCHandler) as httpd:
            print(f"Server running at http://localhost:{port}/")
            logger.info(f"Server started successfully")
            httpd.serve_forever()
    except Exception as e:
        logger.error(f"Error starting server: {e}", exc_info=True)
        print(f"Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
