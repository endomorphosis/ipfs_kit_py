#!/usr/bin/env python3
import http.server
import socketserver
import json
import time
import sys
import os
import threading
import uuid
import shutil
from urllib.parse import urlparse, parse_qs
import subprocess

# Configure port
PORT = 5432
MOCK_DIR = "/home/barberb/.ipfs_kit/mock_lassie"

# Create directories
os.makedirs(MOCK_DIR, exist_ok=True)
os.makedirs(os.path.join(MOCK_DIR, "retrievals"), exist_ok=True)

class LassieMockHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlparse(self.path)
        query = parse_qs(url.query)

        if url.path == '/version':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            version = {
                "version": "0.1.0-mock",
                "commit": "mock-commit-6328d713",
                "goVersion": "go1.19.4"
            }
            self.wfile.write(json.dumps(version).encode('utf-8'))

        elif url.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            health = {
                "status": "ok",
                "uptime": int(time.time())
            }
            self.wfile.write(json.dumps(health).encode('utf-8'))

        elif url.path == '/retrievals':
            # List all retrievals
            retrievals = []
            retrievals_dir = os.path.join(MOCK_DIR, "retrievals")

            for filename in os.listdir(retrievals_dir):
                if filename.endswith('.json'):
                    try:
                        with open(os.path.join(retrievals_dir, filename), 'r') as f:
                            retrieval = json.load(f)
                            retrievals.append(retrieval)
                    except:
                        pass

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(retrievals).encode('utf-8'))

        elif url.path.startswith('/retrievals/'):
            # Get specific retrieval
            retrieval_id = url.path.split('/')[-1]
            retrieval_file = os.path.join(MOCK_DIR, "retrievals", f"{retrieval_id}.json")

            if os.path.exists(retrieval_file):
                try:
                    with open(retrieval_file, 'r') as f:
                        retrieval = json.load(f)

                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(retrieval).encode('utf-8'))
                except:
                    self.send_error(500, "Error reading retrieval file")
            else:
                self.send_error(404, "Retrieval not found")

        elif url.path.startswith('/data/'):
            # Get data for a CID
            cid = url.path.split('/')[-1]

            # Try to get from IPFS
            try:
                result = subprocess.run(
                    ["ipfs", "cat", cid],
                    capture_output=True
                )

                if result.returncode == 0:
                    self.send_response(200)
                    self.send_header('Content-type', 'application/octet-stream')
                    self.end_headers()
                    self.wfile.write(result.stdout)
                else:
                    self.send_error(404, f"CID not found: {result.stderr.decode('utf-8')}")
            except Exception as e:
                self.send_error(500, f"Error: {str(e)}")

        else:
            self.send_error(404, "Endpoint not found")

    def do_POST(self):
        url = urlparse(self.path)

        if url.path == '/retrieve':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            request = json.loads(post_data.decode('utf-8'))

            cid = request.get('cid')
            if not cid:
                self.send_error(400, "Missing CID")
                return

            # Create a new retrieval
            retrieval_id = str(uuid.uuid4())

            # Try to fetch from IPFS
            try:
                result = subprocess.run(
                    ["ipfs", "cat", cid],
                    capture_output=True
                )

                status = "Success" if result.returncode == 0 else "Error"
                error = None if result.returncode == 0 else result.stderr.decode('utf-8')

                # Create retrieval record
                retrieval = {
                    "id": retrieval_id,
                    "cid": cid,
                    "status": status,
                    "error": error,
                    "startedAt": time.time(),
                    "completedAt": time.time() + 0.5,
                    "duration": 0.5,
                    "bytes": len(result.stdout) if result.returncode == 0 else 0
                }

                # Save retrieval record
                with open(os.path.join(MOCK_DIR, "retrievals", f"{retrieval_id}.json"), 'w') as f:
                    json.dump(retrieval, f, indent=2)

                # Return response
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(retrieval).encode('utf-8'))

            except Exception as e:
                self.send_error(500, f"Error: {str(e)}")

        else:
            self.send_error(404, "Endpoint not found")

def run_server():
    with socketserver.TCPServer(("", PORT), LassieMockHandler) as httpd:
        print(f"Lassie mock API server running at port {PORT}")
        httpd.serve_forever()

if __name__ == "__main__":
    # Start the server in a thread
    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()

    print("Mock Lassie API server started. Press Ctrl+C to stop.")

    try:
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down mock Lassie API server")
        sys.exit(0)
