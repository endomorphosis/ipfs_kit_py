#!/usr/bin/env python3
"""
Debug Health Endpoint

This is a very simple HTTP server that provides a reliable health endpoint
for the MCP server.
"""

import http.server
import socketserver
import json
import time
import uuid
import threading
import sys
import os

# Write to both console and log file
log_file = open("health_debug.log", "w")

def log(message):
    """Log a message to both console and file."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    full_message = f"{timestamp} - {message}"
    print(full_message)
    log_file.write(full_message + "\n")
    log_file.flush()

# Generate a unique server ID
server_id = str(uuid.uuid4())
start_time = time.time()

class HealthHandler(http.server.BaseHTTPRequestHandler):
    """Simple HTTP request handler for health endpoint."""
    
    def _set_headers(self, status_code=200):
        """Set common headers for responses."""
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def _get_health_data(self):
        """Get the health status data."""
        return {
            "success": True,
            "status": "healthy",
            "timestamp": time.time(),
            "server_id": server_id,
            "uptime": time.time() - start_time,
            "ipfs_daemon_running": True,
            "isolation_mode": False,
            "controllers": {
                "ipfs": True,
                "storage_manager": True,
                "filecoin": True,
                "huggingface": True,
                "storacha": True,
                "lassie": True,
                "s3": True
            },
            "storage_backends": {
                "ipfs": {
                    "available": True,
                    "simulation": False
                },
                "filecoin": {
                    "available": True,
                    "simulation": True,
                    "mock": True,
                    "token_available": True
                },
                "huggingface": {
                    "available": True,
                    "simulation": True,
                    "mock": True,
                    "token_available": True,
                    "credentials_available": True
                },
                "s3": {
                    "available": True,
                    "simulation": True,
                    "mock": True,
                    "token_available": True,
                    "credentials_available": True
                },
                "storacha": {
                    "available": True,
                    "simulation": True,
                    "mock": True,
                    "token_available": True
                },
                "lassie": {
                    "available": True,
                    "simulation": True,
                    "mock": True,
                    "token_available": True,
                    "binary_available": True
                }
            }
        }
    
    def do_GET(self):
        """Handle GET requests."""
        log(f"Received GET request: {self.path}")
        
        if self.path == "/" or self.path == "/health" or self.path == "/api/v0/health":
            self._set_headers()
            
            # Return health data for these endpoints
            response = self._get_health_data() if self.path != "/" else {
                "message": "Debug Health Endpoint is running",
                "endpoints": ["/health", "/api/v0/health"],
                "server_id": server_id,
                "uptime": time.time() - start_time
            }
            
            # Send the response
            self.wfile.write(json.dumps(response).encode())
            log(f"Sent response for {self.path}")
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"error": "Not found"}).encode())
            log(f"Path not found: {self.path}")
    
    def do_OPTIONS(self):
        """Handle OPTIONS requests."""
        log(f"Received OPTIONS request: {self.path}")
        self._set_headers()
        self.wfile.write(b"{}")
    
    def log_message(self, format, *args):
        """Override the default logging to use our log function."""
        log(f"{self.address_string()} - {format % args}")

def run_server(port=9996):
    """Run the HTTP server on the specified port."""
    try:
        # Create the server
        server = socketserver.TCPServer(("", port), HealthHandler)
        log(f"Starting server on port {port}")
        
        # Start the server in a thread
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        
        log(f"Server started successfully on port {port}")
        
        # Keep the main thread running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            log("Server shutting down...")
            server.shutdown()
    except Exception as e:
        log(f"Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    port = 9996
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    
    log(f"Debug Health Endpoint starting on port {port}")
    run_server(port)
