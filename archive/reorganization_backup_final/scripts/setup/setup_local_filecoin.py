#!/usr/bin/env python3
"""
Local Filecoin Node Mock

This script sets up a local mock Filecoin node for development and testing,
which can be used without requiring a real Filecoin node connection.
"""

import os
import sys
import logging
import json
import subprocess
import time
import shutil
import uuid
import socketserver
import threading
import http.server
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Filecoin mock configuration
MOCK_PORT = 7777
MOCK_DATA_DIR = os.path.expanduser("~/.ipfs_kit/filecoin_mock")
MOCK_API_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJBbGxvdyI6WyJyZWFkIiwid3JpdGUiLCJzaWduIiwiYWRtaW4iXX0.hW17uVyqi0eCEpOGNQQ5Go5noTjdZxGYlnJ7Ka_SM_8"

class FilecoinMockHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler for Filecoin mock RPC server."""
    
    def _set_headers(self, content_type="application/json"):
        self.send_response(200)
        self.send_header('Content-type', content_type)
        self.end_headers()
    
    def _handle_error(self, status_code=500, message="Internal Server Error"):
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        response = {
            "jsonrpc": "2.0",
            "error": {
                "code": -32603,
                "message": message
            },
            "id": None
        }
        self.wfile.write(json.dumps(response).encode())
    
    def do_GET(self):
        """Handle GET requests."""
        if self.path == "/health":
            self._set_headers()
            response = {"status": "ok"}
            self.wfile.write(json.dumps(response).encode())
        else:
            self._handle_error(404, "Not Found")
    
    def do_POST(self):
        """Handle POST requests (JSON-RPC)."""
        # Extract token from Authorization header
        auth_header = self.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            self._handle_error(401, "Unauthorized")
            return
        
        token = auth_header[7:]  # Remove 'Bearer ' prefix
        if token != MOCK_API_TOKEN:
            self._handle_error(401, "Invalid token")
            return
        
        # Get request body length
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            self._handle_error(400, "Empty request body")
            return
        
        # Parse request body
        try:
            body = self.rfile.read(content_length)
            request = json.loads(body)
        except json.JSONDecodeError:
            self._handle_error(400, "Invalid JSON")
            return
        
        # Extract method and params
        method = request.get('method', '')
        params = request.get('params', [])
        request_id = request.get('id', 0)
        
        # Handle methods
        if method == "Filecoin.ID":
            # Return node ID
            response = {
                "jsonrpc": "2.0",
                "result": f"12D3KooWMock{uuid.uuid4().hex[:8]}FilecoinMockNode",
                "id": request_id
            }
        elif method == "Filecoin.Version":
            # Return version info
            response = {
                "jsonrpc": "2.0",
                "result": {
                    "Version": "1.21.0-dev+mock",
                    "APIVersion": "v1.10.0",
                    "BlockDelay": 30
                },
                "id": request_id
            }
        elif method == "Filecoin.ChainHead":
            # Return chain head info
            response = {
                "jsonrpc": "2.0",
                "result": {
                    "Height": 12345,
                    "Blocks": [
                        {
                            "Miner": "f0100",
                            "Timestamp": int(time.time()),
                            "Height": 12345
                        }
                    ]
                },
                "id": request_id
            }
        elif method == "Filecoin.ClientImport":
            # Handle file import
            if len(params) > 0 and isinstance(params[0], dict):
                path = params[0].get('Path', 'unknown')
                file_name = os.path.basename(path)
                
                # Create CID for the file
                cid = f"bafy2bzace{uuid.uuid4().hex[:32]}"
                
                # Store in mock data dir
                import_dir = os.path.join(MOCK_DATA_DIR, "imports")
                os.makedirs(import_dir, exist_ok=True)
                
                # Save import record
                import_record = {
                    "path": path,
                    "cid": cid,
                    "timestamp": time.time(),
                    "size": 1024  # Mock size
                }
                
                with open(os.path.join(import_dir, f"{cid}.json"), "w") as f:
                    json.dump(import_record, f)
                
                response = {
                    "jsonrpc": "2.0",
                    "result": {
                        "Root": {
                            "/": cid
                        },
                        "ImportID": uuid.uuid4().int & ((1 << 64) - 1)
                    },
                    "id": request_id
                }
            else:
                self._handle_error(400, "Invalid params for ClientImport")
                return
        elif method == "Filecoin.ClientStartDeal":
            # Handle storage deal creation
            deal_cid = f"bafyrei{uuid.uuid4().hex[:32]}"
            deal_id = uuid.uuid4().int & ((1 << 32) - 1)
            
            # Store deal info
            deals_dir = os.path.join(MOCK_DATA_DIR, "deals")
            os.makedirs(deals_dir, exist_ok=True)
            
            deal_record = {
                "proposal": params[0] if params else {},
                "deal_cid": deal_cid,
                "deal_id": deal_id,
                "timestamp": time.time(),
                "state": "proposed"
            }
            
            with open(os.path.join(deals_dir, f"{deal_id}.json"), "w") as f:
                json.dump(deal_record, f)
            
            response = {
                "jsonrpc": "2.0",
                "result": {
                    "/": deal_cid
                },
                "id": request_id
            }
        elif method == "Filecoin.ClientListDeals":
            # List all deals
            deals_dir = os.path.join(MOCK_DATA_DIR, "deals")
            os.makedirs(deals_dir, exist_ok=True)
            
            deals = []
            for filename in os.listdir(deals_dir):
                if filename.endswith(".json"):
                    try:
                        with open(os.path.join(deals_dir, filename), "r") as f:
                            deal_record = json.load(f)
                        
                        # Generate a mock deal
                        deal = {
                            "ProposalCid": {"/": deal_record.get("deal_cid", "")},
                            "State": 7,  # Active state
                            "Message": "",
                            "Provider": "f0100",
                            "DataRef": {
                                "TransferType": "graphsync",
                                "Root": {"/": deal_record.get("proposal", {}).get("Data", {}).get("/", "")}
                            },
                            "PieceCID": {"/": f"baga6ea4sea{uuid.uuid4().hex[:24]}"},
                            "Size": 1048576,  # 1 MiB
                            "PricePerEpoch": "1000",
                            "Duration": 518400,  # 180 days
                            "DealID": deal_record.get("deal_id", 0),
                            "CreationTime": deal_record.get("timestamp", 0)
                        }
                        deals.append(deal)
                    except Exception as e:
                        logger.error(f"Error loading deal record {filename}: {e}")
            
            response = {
                "jsonrpc": "2.0",
                "result": deals,
                "id": request_id
            }
        elif method.startswith("Filecoin."):
            # Generic mock response for other Filecoin methods
            response = {
                "jsonrpc": "2.0",
                "result": {"mock": True, "method": method},
                "id": request_id
            }
        else:
            # Unknown method
            self._handle_error(400, f"Unknown method: {method}")
            return
        
        # Send response
        self._set_headers()
        self.wfile.write(json.dumps(response).encode())
    
    def log_message(self, format, *args):
        """Customize logging."""
        logger.debug(f"Filecoin Mock: {format % args}")

class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """Threaded HTTP server for handling multiple requests."""
    pass

def create_lotus_mock_binary():
    """Create a mock Lotus binary."""
    # Create bin directory if it doesn't exist
    bin_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin")
    os.makedirs(bin_dir, exist_ok=True)
    
    lotus_path = os.path.join(bin_dir, "lotus")
    
    # Write the shell script with manually formatted content
    with open(lotus_path, "w") as f:
        f.write(f'''#!/bin/bash
# Mock Lotus client for Filecoin

# Configuration
MOCK_API_TOKEN="{MOCK_API_TOKEN}"
MOCK_API_URL="http://localhost:{MOCK_PORT}/rpc/v0"
LOTUS_PATH="$HOME/.ipfs_kit/filecoin_mock/lotus"

# Create LOTUS_PATH directory
mkdir -p "$LOTUS_PATH"

# Export environment for child processes
export LOTUS_PATH

# Store API info
echo "$MOCK_API_URL" > "$LOTUS_PATH/api"
echo "$MOCK_API_TOKEN" > "$LOTUS_PATH/token"

command="$1"
shift

case "$command" in
    daemon)
        echo "Mock Lotus daemon already running at $MOCK_API_URL"
        exit 0
        ;;
    version)
        cat <<EOF
Lotus Mock v1.21.0-dev+mock
Build: mock
System version: go-mock (filecoin-project/lotus)
Commit: mock
EOF
        exit 0
        ;;
    net)
        if [ "$1" == "id" ]; then
            echo "12D3KooWMockFilecoinNodeID"
            exit 0
        fi
        ;;
    client)
        subcmd="$1"
        shift
        case "$subcmd" in
            import)
                file="$1"
                if [ -f "$file" ]; then
                    random=$(cat /dev/urandom | tr -dc 'a-f0-9' | fold -w 32 | head -n 1)
                    echo "{\"Cid\":{\"/\":\"bafy2bzace$random\"},\"Size\":$(stat -c%s "$file")}"
                    exit 0
                else
                    echo "Error: File not found: $file" >&2
                    exit 1
                fi
                ;;
            *)
                # Forward other client commands to the API
                curl -X POST -H "Content-Type: application/json" -H "Authorization: Bearer $MOCK_API_TOKEN" \\
                    -d "{\"jsonrpc\":\"2.0\",\"method\":\"Filecoin.Client$subcmd\",\"params\":[],\"id\":1}" \\
                    "$MOCK_API_URL"
                exit $?
                ;;
        esac
        ;;
    *)
        # Forward other commands to the API
        curl -X POST -H "Content-Type: application/json" -H "Authorization: Bearer $MOCK_API_TOKEN" \\
            -d "{\"jsonrpc\":\"2.0\",\"method\":\"Filecoin.$command\",\"params\":[],\"id\":1}" \\
            "$MOCK_API_URL"
        exit $?
        ;;
esac

echo "Unknown command: $command" >&2
exit 1
''')
    
    # Make executable
    os.chmod(lotus_path, 0o755)
    logger.info(f"Created mock Lotus binary at {lotus_path}")
    
    return lotus_path

def update_filecoin_credentials():
    """Update the Filecoin credentials to use the mock node."""
    creds_file = "local_mcp_credentials.sh"
    
    if not os.path.exists(creds_file):
        logger.warning(f"Credentials file not found: {creds_file}")
        creds_file = "real_mcp_credentials.sh"
    
    try:
        # Read existing content
        if os.path.exists(creds_file):
            with open(creds_file, "r") as f:
                content = f.read()
        else:
            content = "#!/bin/bash\n# MCP Server Credentials for Local Services\n\n"
        
        # Check if Filecoin credentials are already in the file
        if "FILECOIN_API_URL" not in content:
            # Append Filecoin credentials
            with open(creds_file, "a") as f:
                f.write(f"""
# Filecoin credentials (mock node)
export FILECOIN_API_URL="http://localhost:{MOCK_PORT}/rpc/v0"
export FILECOIN_API_TOKEN="{MOCK_API_TOKEN}"
export LOTUS_PATH="{os.path.expanduser("~/.ipfs_kit/filecoin_mock/lotus")}"
export LOTUS_BINARY_PATH="{os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin/lotus")}"
""")
        else:
            # Update existing Filecoin credentials
            lines = content.splitlines()
            new_lines = []
            
            for line in lines:
                if line.startswith("export FILECOIN_API_URL="):
                    new_lines.append(f'export FILECOIN_API_URL="http://localhost:{MOCK_PORT}/rpc/v0"')
                elif line.startswith("export FILECOIN_API_TOKEN="):
                    new_lines.append(f'export FILECOIN_API_TOKEN="{MOCK_API_TOKEN}"')
                elif line.startswith("export LOTUS_PATH="):
                    new_lines.append(f'export LOTUS_PATH="{os.path.expanduser("~/.ipfs_kit/filecoin_mock/lotus")}"')
                elif line.startswith("export LOTUS_BINARY_PATH="):
                    new_lines.append(f'export LOTUS_BINARY_PATH="{os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin/lotus")}"')
                else:
                    new_lines.append(line)
            
            with open(creds_file, "w") as f:
                f.write("\n".join(new_lines))
        
        os.chmod(creds_file, 0o755)
        logger.info(f"Updated Filecoin credentials in {creds_file}")
        
        # Set environment variables
        os.environ["FILECOIN_API_URL"] = f"http://localhost:{MOCK_PORT}/rpc/v0"
        os.environ["FILECOIN_API_TOKEN"] = MOCK_API_TOKEN
        os.environ["LOTUS_PATH"] = os.path.expanduser("~/.ipfs_kit/filecoin_mock/lotus")
        os.environ["LOTUS_BINARY_PATH"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin/lotus")
        
        return True
    except Exception as e:
        logger.error(f"Error updating Filecoin credentials: {e}")
        return False

def start_mock_server():
    """Start the Filecoin mock RPC server."""
    try:
        # Create data directory
        os.makedirs(MOCK_DATA_DIR, exist_ok=True)
        
        # Create LOTUS_PATH directory
        lotus_path = os.path.join(MOCK_DATA_DIR, "lotus")
        os.makedirs(lotus_path, exist_ok=True)
        
        # Write API info
        with open(os.path.join(lotus_path, "api"), "w") as f:
            f.write(f"http://localhost:{MOCK_PORT}/rpc/v0")
        
        with open(os.path.join(lotus_path, "token"), "w") as f:
            f.write(MOCK_API_TOKEN)
        
        # Start server in a separate thread
        server_address = ('localhost', MOCK_PORT)
        httpd = ThreadedHTTPServer(server_address, FilecoinMockHandler)
        
        def run_server():
            logger.info(f"Starting Filecoin mock RPC server on port {MOCK_PORT}")
            httpd.serve_forever()
        
        server_thread = threading.Thread(target=run_server)
        server_thread.daemon = True
        server_thread.start()
        
        # Save thread and server objects for later reference
        with open(os.path.join(MOCK_DATA_DIR, "server.pid"), "w") as f:
            f.write(str(os.getpid()))
        
        # Wait a moment for the server to start
        time.sleep(1)
        
        logger.info("Filecoin mock RPC server started")
        return True
    except Exception as e:
        logger.error(f"Error starting Filecoin mock RPC server: {e}")
        return False

def test_mock_server():
    """Test the Filecoin mock RPC server."""
    try:
        import requests
        
        # Test health endpoint
        health_response = requests.get(f"http://localhost:{MOCK_PORT}/health")
        if health_response.status_code != 200:
            logger.warning(f"Health check failed: HTTP {health_response.status_code}")
            return False
        
        # Test RPC endpoint
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {MOCK_API_TOKEN}"
        }
        
        rpc_payload = {
            "jsonrpc": "2.0",
            "method": "Filecoin.Version",
            "params": [],
            "id": 1
        }
        
        rpc_response = requests.post(
            f"http://localhost:{MOCK_PORT}/rpc/v0",
            headers=headers,
            json=rpc_payload
        )
        
        if rpc_response.status_code != 200:
            logger.warning(f"RPC check failed: HTTP {rpc_response.status_code}")
            return False
        
        try:
            result = rpc_response.json()
            if "result" in result:
                logger.info(f"RPC server test successful: {result['result']}")
                return True
            else:
                logger.warning(f"RPC check failed: {result.get('error')}")
                return False
        except Exception as e:
            logger.error(f"Error parsing RPC response: {e}")
            return False
    except Exception as e:
        logger.error(f"Error testing mock server: {e}")
        return False

def test_mock_lotus():
    """Test the mock Lotus binary."""
    try:
        lotus_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin/lotus")
        
        if not os.path.exists(lotus_path):
            logger.warning(f"Lotus binary not found: {lotus_path}")
            return False
        
        # Test version command
        result = subprocess.run(
            [lotus_path, "version"],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            logger.warning(f"Lotus version check failed: {result.stderr}")
            return False
        
        logger.info(f"Lotus version check successful: {result.stdout}")
        
        # Test net id command
        result = subprocess.run(
            [lotus_path, "net", "id"],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            logger.warning(f"Lotus net id check failed: {result.stderr}")
            return False
        
        logger.info(f"Lotus net id check successful: {result.stdout}")
        
        return True
    except Exception as e:
        logger.error(f"Error testing mock Lotus: {e}")
        return False

def main():
    """Main function to set up the local Filecoin mock node."""
    logger.info("Setting up local Filecoin mock node...")
    
    # Create mock Lotus binary
    lotus_path = create_lotus_mock_binary()
    
    # Start the mock RPC server
    if not start_mock_server():
        logger.error("Failed to start Filecoin mock RPC server")
        return False
    
    # Update credentials
    if not update_filecoin_credentials():
        logger.warning("Failed to update Filecoin credentials")
    
    # Test the mock server
    if not test_mock_server():
        logger.warning("Filecoin mock server test failed")
    
    # Test the mock Lotus binary
    if not test_mock_lotus():
        logger.warning("Mock Lotus binary test failed")
    
    logger.info("Local Filecoin mock node setup complete!")
    logger.info(f"RPC server running on http://localhost:{MOCK_PORT}/rpc/v0")
    logger.info(f"API token: {MOCK_API_TOKEN}")
    logger.info(f"Mock Lotus binary: {lotus_path}")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)