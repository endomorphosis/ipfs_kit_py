#!/usr/bin/env python3
"""
Storacha Implementation Setup for MCP Server

This script sets up a working Storacha implementation for the MCP server
by creating a local service that implements the Storacha API.
"""

import os
import sys
import json
import logging
import subprocess
import time
import uuid
from pathlib import Path
import http.server
import socketserver
import threading
import shutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
STORACHA_PORT = 5678
STORACHA_MOCK_DIR = os.path.expanduser("~/.ipfs_kit/mock_storacha")
STORACHA_API_KEY = f"storacha-dev-{uuid.uuid4().hex[:8]}"

def setup_storacha_mock_server():
    """Set up a mock Storacha API server"""
    try:
        # Create directory for Storacha mock data
        os.makedirs(STORACHA_MOCK_DIR, exist_ok=True)

        # Create a mock Storacha server
        server_path = os.path.join(os.getcwd(), "storacha_mock_server.py")

        with open(server_path, 'w') as f:
            f.write(f"""#!/usr/bin/env python3
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
PORT = {STORACHA_PORT}
MOCK_DIR = "{STORACHA_MOCK_DIR}"
API_KEY = "{STORACHA_API_KEY}"

# Create directories
os.makedirs(MOCK_DIR, exist_ok=True)
os.makedirs(os.path.join(MOCK_DIR, "uploads"), exist_ok=True)
os.makedirs(os.path.join(MOCK_DIR, "downloads"), exist_ok=True)

class StorachaMockHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlparse(self.path)
        query = parse_qs(url.query)

        # Check API key
        api_key = self.headers.get('Authorization', '').replace('Bearer ', '')
        if api_key != API_KEY:
            self.send_error(401, "Invalid API key")
            return

        if url.path == '/v1/status':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            status = {{
                "status": "ok",
                "version": "1.0.0-mock",
                "uptime": int(time.time()),
                "message": "Storacha Mock API is running"
            }}
            self.wfile.write(json.dumps(status).encode('utf-8'))

        elif url.path.startswith('/v1/download/'):
            cid = url.path.split('/')[-1]
            if not cid:
                self.send_error(400, "Missing CID")
                return

            # Check if file exists in mock storage
            mock_path = os.path.join(MOCK_DIR, "downloads", cid)
            if os.path.exists(mock_path):
                # Return existing file
                with open(mock_path, 'rb') as f:
                    self.send_response(200)
                    self.send_header('Content-type', 'application/octet-stream')
                    self.end_headers()
                    self.wfile.write(f.read())
            else:
                # Try to get file from IPFS
                try:
                    result = subprocess.run(
                        ["ipfs", "cat", cid],
                        capture_output=True
                    )

                    if result.returncode == 0:
                        # Store the file for future use
                        with open(mock_path, 'wb') as f:
                            f.write(result.stdout)

                        # Return the file
                        self.send_response(200)
                        self.send_header('Content-type', 'application/octet-stream')
                        self.end_headers()
                        self.wfile.write(result.stdout)
                    else:
                        self.send_error(404, f"CID not found: {{result.stderr.decode('utf-8')}}")
                except Exception as e:
                    self.send_error(500, f"Error: {{str(e)}}")

        elif url.path == '/v1/list':
            # List files in the mock storage
            uploads_dir = os.path.join(MOCK_DIR, "uploads")
            files = []

            for filename in os.listdir(uploads_dir):
                if os.path.isfile(os.path.join(uploads_dir, filename)):
                    stat = os.stat(os.path.join(uploads_dir, filename))
                    files.append({{
                        "cid": filename,
                        "name": filename,
                        "size": stat.st_size,
                        "uploaded_at": stat.st_mtime
                    }})

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({{
                "files": files,
                "count": len(files)
            }}).encode('utf-8'))

        else:
            self.send_error(404, "Endpoint not found")

    def do_POST(self):
        url = urlparse(self.path)

        # Check API key
        api_key = self.headers.get('Authorization', '').replace('Bearer ', '')
        if api_key != API_KEY:
            self.send_error(401, "Invalid API key")
            return

        if url.path == '/v1/upload':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)

            # Generate a file ID (simulating CID)
            file_id = f"mock{{uuid.uuid4().hex}}"

            # Store the file
            file_path = os.path.join(MOCK_DIR, "uploads", file_id)
            with open(file_path, 'wb') as f:
                f.write(post_data)

            # Also store in IPFS to get a real CID
            try:
                # Create a temporary file
                temp_file = os.path.join(MOCK_DIR, f"temp_{{uuid.uuid4().hex}}")
                with open(temp_file, 'wb') as f:
                    f.write(post_data)

                # Add to IPFS
                result = subprocess.run(
                    ["ipfs", "add", "-q", temp_file],
                    capture_output=True,
                    text=True
                )

                # Clean up
                os.unlink(temp_file)

                if result.returncode == 0:
                    real_cid = result.stdout.strip()

                    # Use the real CID
                    os.rename(file_path, os.path.join(MOCK_DIR, "uploads", real_cid))
                    file_id = real_cid
            except Exception as e:
                print(f"Error adding to IPFS: {{e}}")

            # Return response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            response = {{
                "success": True,
                "cid": file_id,
                "size": len(post_data),
                "timestamp": time.time()
            }}

            self.wfile.write(json.dumps(response).encode('utf-8'))

        elif url.path == '/v1/pin':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            request = json.loads(post_data.decode('utf-8'))

            cid = request.get('cid')
            if not cid:
                self.send_error(400, "Missing CID")
                return

            # Pin the CID in IPFS
            try:
                result = subprocess.run(
                    ["ipfs", "pin", "add", cid],
                    capture_output=True,
                    text=True
                )

                if result.returncode == 0:
                    # Return success response
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()

                    response = {{
                        "success": True,
                        "cid": cid,
                        "pinned": True,
                        "timestamp": time.time()
                    }}

                    self.wfile.write(json.dumps(response).encode('utf-8'))
                else:
                    self.send_error(500, f"Failed to pin CID: {{result.stderr}}")
            except Exception as e:
                self.send_error(500, f"Error: {{str(e)}}")

        else:
            self.send_error(404, "Endpoint not found")

def run_server():
    with socketserver.TCPServer(("", PORT), StorachaMockHandler) as httpd:
        print(f"Storacha mock API server running at port {{PORT}}")
        httpd.serve_forever()

if __name__ == "__main__":
    # Start the server in a thread
    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()

    print("Mock Storacha API server started. Press Ctrl+C to stop.")
    print(f"API Key: {{API_KEY}}")

    try:
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down mock Storacha API server")
        sys.exit(0)
""")

        # Make it executable
        os.chmod(server_path, 0o755)

        logger.info(f"Created Storacha mock API server at: {server_path}")

        # Start the mock API server in the background
        logger.info("Starting Storacha mock API server...")

        # Use nohup to keep the server running after the script exits
        with open(os.path.join(os.getcwd(), "logs/storacha_mock_api.log"), 'w') as log_file:
            process = subprocess.Popen(
                [sys.executable, server_path],
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True
            )

        # Wait for the server to start
        time.sleep(2)

        logger.info(f"Storacha mock API server started with PID {process.pid}")

        # Save the PID for later
        with open(os.path.join(os.getcwd(), "storacha_mock_api.pid"), 'w') as f:
            f.write(str(process.pid))

        # Set environment variables
        os.environ['STORACHA_API_KEY'] = STORACHA_API_KEY
        os.environ['STORACHA_API_URL'] = f"http://localhost:{STORACHA_PORT}"

        return True

    except Exception as e:
        logger.error(f"Error setting up Storacha mock API server: {e}")
        return False

def update_mcp_config():
    """Update MCP configuration with the Storacha settings"""
    config_file = os.path.join(os.getcwd(), "mcp_config.sh")

    try:
        # Read existing file
        with open(config_file, 'r') as f:
            lines = f.readlines()

        # Find Storacha section and update it
        storacha_section_start = -1
        storacha_section_end = -1

        for i, line in enumerate(lines):
            if "# Storacha configuration" in line:
                storacha_section_start = i
            elif storacha_section_start > -1 and "fi" in line and storacha_section_end == -1:
                storacha_section_end = i

        if storacha_section_start > -1 and storacha_section_end > -1:
            # Create new Storacha configuration
            new_storacha_config = [
                "# Storacha configuration\n",
                "# Using Storacha local development API\n",
                f"export STORACHA_API_KEY=\"{STORACHA_API_KEY}\"\n",
                f"export STORACHA_API_URL=\"http://localhost:{STORACHA_PORT}\"\n"
            ]

            # Replace the section
            lines[storacha_section_start:storacha_section_end+1] = new_storacha_config

            # Write updated file
            with open(config_file, 'w') as f:
                f.writelines(lines)

            logger.info(f"Updated MCP configuration file with Storacha settings")
            return True
        else:
            logger.error("Could not find Storacha section in MCP configuration file")
            return False

    except Exception as e:
        logger.error(f"Error updating MCP configuration: {e}")
        return False

def main():
    """Main function"""
    logger.info("Setting up Storacha implementation for MCP Server")

    # Set up Storacha mock API server
    if setup_storacha_mock_server():
        # Update MCP configuration
        update_mcp_config()

    logger.info("Storacha implementation setup complete")
    logger.info("Restart the MCP server to apply changes")

if __name__ == "__main__":
    main()
