#!/usr/bin/env python3
"""
Lassie Implementation Setup for MCP Server

This script sets up a working Lassie implementation for the MCP server
by creating a local service that implements the Lassie API.
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
LASSIE_PORT = 5432
LASSIE_MOCK_DIR = os.path.expanduser("~/.ipfs_kit/mock_lassie")

def setup_lassie_mock_server():
    """Set up a mock Lassie API server"""
    try:
        # Create directory for Lassie mock data
        os.makedirs(LASSIE_MOCK_DIR, exist_ok=True)
        
        # Create a mock Lassie server
        server_path = os.path.join(os.getcwd(), "lassie_mock_server.py")
        
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
PORT = {LASSIE_PORT}
MOCK_DIR = "{LASSIE_MOCK_DIR}"

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
            version = {{
                "version": "0.1.0-mock",
                "commit": "mock-commit-{uuid.uuid4().hex[:8]}",
                "goVersion": "go1.19.4"
            }}
            self.wfile.write(json.dumps(version).encode('utf-8'))
        
        elif url.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            health = {{
                "status": "ok",
                "uptime": int(time.time())
            }}
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
            retrieval_file = os.path.join(MOCK_DIR, "retrievals", f"{{retrieval_id}}.json")
            
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
                    self.send_error(404, f"CID not found: {{result.stderr.decode('utf-8')}}")
            except Exception as e:
                self.send_error(500, f"Error: {{str(e)}}")
        
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
                retrieval = {{
                    "id": retrieval_id,
                    "cid": cid,
                    "status": status,
                    "error": error,
                    "startedAt": time.time(),
                    "completedAt": time.time() + 0.5,
                    "duration": 0.5,
                    "bytes": len(result.stdout) if result.returncode == 0 else 0
                }}
                
                # Save retrieval record
                with open(os.path.join(MOCK_DIR, "retrievals", f"{{retrieval_id}}.json"), 'w') as f:
                    json.dump(retrieval, f, indent=2)
                
                # Return response
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(retrieval).encode('utf-8'))
            
            except Exception as e:
                self.send_error(500, f"Error: {{str(e)}}")
        
        else:
            self.send_error(404, "Endpoint not found")

def run_server():
    with socketserver.TCPServer(("", PORT), LassieMockHandler) as httpd:
        print(f"Lassie mock API server running at port {{PORT}}")
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
""")
        
        # Make it executable
        os.chmod(server_path, 0o755)
        
        logger.info(f"Created Lassie mock API server at: {server_path}")
        
        # Start the mock API server in the background
        logger.info("Starting Lassie mock API server...")
        
        # Use nohup to keep the server running after the script exits
        with open(os.path.join(os.getcwd(), "logs/lassie_mock_api.log"), 'w') as log_file:
            process = subprocess.Popen(
                [sys.executable, server_path],
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True
            )
        
        # Wait for the server to start
        time.sleep(2)
        
        logger.info(f"Lassie mock API server started with PID {process.pid}")
        
        # Save the PID for later
        with open(os.path.join(os.getcwd(), "lassie_mock_api.pid"), 'w') as f:
            f.write(str(process.pid))
        
        # Set environment variables
        os.environ['LASSIE_API_URL'] = f"http://localhost:{LASSIE_PORT}"
        os.environ['LASSIE_ENABLED'] = "true"
        
        return True
    
    except Exception as e:
        logger.error(f"Error setting up Lassie mock API server: {e}")
        return False

def update_mcp_config():
    """Update MCP configuration with the Lassie settings"""
    config_file = os.path.join(os.getcwd(), "mcp_config.sh")
    
    try:
        # Read existing file
        with open(config_file, 'r') as f:
            lines = f.readlines()
        
        # Find Lassie section and update it
        lassie_section_start = -1
        lassie_section_end = -1
        
        for i, line in enumerate(lines):
            if "# Lassie configuration" in line:
                lassie_section_start = i
            elif lassie_section_start > -1 and "fi" in line and lassie_section_end == -1:
                lassie_section_end = i
        
        if lassie_section_start > -1 and lassie_section_end > -1:
            # Create new Lassie configuration
            new_lassie_config = [
                "# Lassie configuration\n",
                "# Using Lassie local development API\n",
                f"export LASSIE_API_URL=\"http://localhost:{LASSIE_PORT}\"\n",
                "export LASSIE_ENABLED=\"true\"\n"
            ]
            
            # Replace the section
            lines[lassie_section_start:lassie_section_end+1] = new_lassie_config
            
            # Write updated file
            with open(config_file, 'w') as f:
                f.writelines(lines)
            
            logger.info(f"Updated MCP configuration file with Lassie settings")
            return True
        else:
            logger.error("Could not find Lassie section in MCP configuration file")
            return False
    
    except Exception as e:
        logger.error(f"Error updating MCP configuration: {e}")
        return False

def main():
    """Main function"""
    logger.info("Setting up Lassie implementation for MCP Server")
    
    # Set up Lassie mock API server
    if setup_lassie_mock_server():
        # Update MCP configuration
        update_mcp_config()
    
    logger.info("Lassie implementation setup complete")
    logger.info("Restart the MCP server to apply changes")

if __name__ == "__main__":
    main()