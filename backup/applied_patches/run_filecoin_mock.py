#!/usr/bin/env python3
"""
Simple Filecoin Mock Server

This script starts a simple HTTP server that mocks the Filecoin JSON-RPC API.
It can be used for development and testing without a real Filecoin node.
"""

import os
import sys
import json
import uuid
import time
import logging
import threading
import http.server
import socketserver
import requests
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
PORT = 7777
API_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJBbGxvdyI6WyJyZWFkIiwid3JpdGUiLCJzaWduIiwiYWRtaW4iXX0.hW17uVyqi0eCEpOGNQQ5Go5noTjdZxGYlnJ7Ka_SM_8"
DATA_DIR = os.path.expanduser("~/.ipfs_kit/filecoin_mock")

class FilecoinMockHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler for Filecoin mock server."""

    def do_GET(self):
        """Handle GET requests."""
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())
        else:
            self.send_response(404)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Not found"}).encode())

    def do_POST(self):
        """Handle POST requests (JSON-RPC)."""
        # Check authorization
        auth_header = self.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer ") or auth_header[7:] != API_TOKEN:
            self.send_response(401)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "jsonrpc": "2.0",
                "error": {"code": -32001, "message": "Unauthorized"},
                "id": None
            }).encode())
            return

        # Parse request
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > 0:
            request_data = self.rfile.read(content_length)
            try:
                request = json.loads(request_data)
                method = request.get("method", "")
                params = request.get("params", [])
                request_id = request.get("id", 0)

                # Handle different methods
                if method == "Filecoin.Version":
                    result = {
                        "Version": "1.21.0-dev+mock",
                        "APIVersion": "v1.10.0",
                        "BlockDelay": 30
                    }
                elif method == "Filecoin.ID":
                    result = "12D3KooWMockFilecoinNodeID"
                elif method == "Filecoin.ChainHead":
                    result = {
                        "Height": 12345,
                        "Blocks": [
                            {
                                "Miner": "f0100",
                                "Timestamp": int(time.time()),
                                "Height": 12345
                            }
                        ]
                    }
                elif method == "Filecoin.ClientImport":
                    # Create a mock import result
                    cid = f"bafy2bzace{uuid.uuid4().hex[:32]}"
                    result = {
                        "Root": {"/": cid},
                        "ImportID": uuid.uuid4().int & ((1 << 64) - 1)
                    }
                elif method == "Filecoin.ClientStartDeal":
                    # Create a mock deal
                    deal_cid = f"bafyrei{uuid.uuid4().hex[:32]}"
                    result = {"/": deal_cid}
                elif method == "Filecoin.ClientListDeals":
                    # Return mock deals
                    result = [
                        {
                            "ProposalCid": {"/": f"bafyrei{uuid.uuid4().hex[:32]}"},
                            "State": 7,  # Active state
                            "Message": "",
                            "Provider": "f0100",
                            "DataRef": {
                                "TransferType": "graphsync",
                                "Root": {"/": f"bafy2bzace{uuid.uuid4().hex[:32]}"}
                            },
                            "PieceCID": {"/": f"baga6ea4sea{uuid.uuid4().hex[:24]}"},
                            "Size": 1048576,  # 1 MiB
                            "PricePerEpoch": "1000",
                            "Duration": 518400,  # 180 days
                            "DealID": 12345,
                            "CreationTime": time.time() - 3600  # 1 hour ago
                        }
                    ]
                else:
                    # Generic mock for any other methods
                    result = {"mock": True, "method": method}

                # Send response
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "jsonrpc": "2.0",
                    "result": result,
                    "id": request_id
                }).encode())

            except json.JSONDecodeError:
                self.send_response(400)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "jsonrpc": "2.0",
                    "error": {"code": -32700, "message": "Parse error"},
                    "id": None
                }).encode())
        else:
            self.send_response(400)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "jsonrpc": "2.0",
                "error": {"code": -32700, "message": "Empty request"},
                "id": None
            }).encode())

    def log_message(self, format, *args):
        """Override to use our logger."""
        logger.debug(f"{self.client_address[0]} - {format % args}")

def main():
    """Main function to start the server."""
    # Create directories
    os.makedirs(DATA_DIR, exist_ok=True)
    lotus_dir = os.path.join(DATA_DIR, "lotus")
    os.makedirs(lotus_dir, exist_ok=True)

    # Save API info
    with open(os.path.join(lotus_dir, "api"), "w") as f:
        f.write(f"http://localhost:{PORT}/rpc/v0")

    with open(os.path.join(lotus_dir, "token"), "w") as f:
        f.write(API_TOKEN)

    # Start server
    server = socketserver.ThreadingTCPServer(("localhost", PORT), FilecoinMockHandler)
    logger.info(f"Starting Filecoin mock server on port {PORT}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down server")
        server.shutdown()

if __name__ == "__main__":
    main()
