#!/usr/bin/env python3
import http.server
import socketserver
import json
import time
import sys
import os
import threading
import uuid

# Configure port
PORT = 1234

class FilecoinMockHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        request = json.loads(post_data.decode('utf-8'))

        # Process JSON-RPC request
        response = self.handle_jsonrpc(request)

        # Send response
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode('utf-8'))

    def handle_jsonrpc(self, request):
        method = request.get('method', '')
        params = request.get('params', [])
        req_id = request.get('id', 0)

        print(f"Received request for method: {method}")

        # Basic structure for JSON-RPC response
        response = {
            "jsonrpc": "2.0",
            "id": req_id
        }

        # Handle different methods
        if method == "Filecoin.ChainHead":
            response["result"] = {
                "Cids": [{"/":{
                    "Data": "mock-data",
                    "Links": []
                }}],
                "Blocks": [],
                "Height": 123456
            }
        elif method == "Filecoin.Version":
            response["result"] = {
                "Version": "1.23.0-dev+mock",
                "APIVersion": "0.0.1",
                "BlockDelay": 30
            }
        elif method == "Filecoin.ClientListDeals":
            response["result"] = []
        elif method == "Filecoin.StateMinerInfo":
            response["result"] = {
                "Owner": "mock-owner-address",
                "Worker": "mock-worker-address",
                "NewWorker": "mock-new-worker-address",
                "ControlAddresses": [],
                "MultiAddresses": [],
                "SectorSize": 34359738368,
                "PeerId": "12D3KooWMockPeerId12345"
            }
        elif method == "Filecoin.ClientStartDeal":
            deal_id = str(uuid.uuid4())
            response["result"] = {
                "/":{
                    "Data": deal_id,
                    "Links": []
                }
            }
        else:
            # Default mock response
            response["result"] = {
                "message": f"Mock response for {method}",
                "timestamp": time.time()
            }

        return response

def run_server():
    with socketserver.TCPServer(("", PORT), FilecoinMockHandler) as httpd:
        print(f"Filecoin mock API server running at port {PORT}")
        httpd.serve_forever()

if __name__ == "__main__":
    # Start the server in a thread
    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()

    print("Mock Filecoin API server started. Press Ctrl+C to stop.")

    try:
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down mock Filecoin API server")
        sys.exit(0)
