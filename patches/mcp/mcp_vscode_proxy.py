#!/usr/bin/env python3
"""
Create a VS Code Extension MCP Proxy

This script creates a simple proxy server that intercepts VS Code's
initialization requests to the SSE endpoint and redirects them to
the proper initialization endpoint.
"""

import http.server
import socketserver
import urllib.request
import urllib.error
import urllib.parse
import json
import logging
import threading
import sys
import os

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='mcp_vscode_proxy.log',
    filemode='w'
)
logger = logging.getLogger('mcp_proxy')

# Add console handler for immediate feedback
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console.setFormatter(formatter)
logger.addHandler(console)

# Configuration
PROXY_PORT = 9996
MCP_SERVER_URL = "http://localhost:9994"
MCP_SSE_ENDPOINT = "/api/v0/sse"
MCP_INIT_ENDPOINT = "/api/v0/initialize"

class MCPProxyHandler(http.server.BaseHTTPRequestHandler):
    """Handler for the MCP proxy server."""

    def log_message(self, format, *args):
        """Override log_message to use our logger."""
        logger.info(format % args)

    def do_OPTIONS(self):
        """Handle OPTIONS requests (CORS)."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        """Handle GET requests."""
        # If the request is for the SSE endpoint, proxy it directly
        if self.path == MCP_SSE_ENDPOINT:
            try:
                logger.info(f"Proxying SSE request to {MCP_SERVER_URL + MCP_SSE_ENDPOINT}")
                response = urllib.request.urlopen(MCP_SERVER_URL + MCP_SSE_ENDPOINT)

                # Forward the response
                self.send_response(response.status)
                for header in response.getheaders():
                    self.send_header(header[0], header[1])
                self.end_headers()

                # Stream the response
                self.wfile.write(response.read())
            except Exception as e:
                logger.error(f"Error proxying SSE request: {e}")
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        else:
            # Forward other GET requests directly
            try:
                logger.info(f"Proxying GET request to {MCP_SERVER_URL + self.path}")
                response = urllib.request.urlopen(MCP_SERVER_URL + self.path)

                # Forward the response
                self.send_response(response.status)
                for header in response.getheaders():
                    self.send_header(header[0], header[1])
                self.end_headers()

                self.wfile.write(response.read())
            except Exception as e:
                logger.error(f"Error proxying GET request: {e}")
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())

    def do_POST(self):
        """Handle POST requests."""
        # Intercept initialization requests to SSE endpoint and redirect them
        if self.path == MCP_SSE_ENDPOINT:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 0:
                post_data = self.rfile.read(content_length).decode('utf-8')
                try:
                    request_json = json.loads(post_data)
                    # Check if this is an initialize request
                    if "method" in request_json and request_json["method"] == "initialize":
                        logger.info("Intercepted initialize request to SSE endpoint, redirecting...")

                        # Forward to the initialization endpoint
                        req = urllib.request.Request(
                            url=MCP_SERVER_URL + MCP_INIT_ENDPOINT,
                            data=post_data.encode(),
                            headers={'Content-Type': 'application/json'},
                            method='POST'
                        )

                        try:
                            response = urllib.request.urlopen(req)

                            # Forward the response
                            self.send_response(response.status)
                            for header in response.getheaders():
                                self.send_header(header[0], header[1])
                            self.end_headers()

                            self.wfile.write(response.read())
                        except urllib.error.HTTPError as e:
                            logger.error(f"Error forwarding initialize request: {e}")
                            # If initialization endpoint fails, return a compatible response
                            self.send_response(200)
                            self.send_header('Content-Type', 'application/json')
                            self.end_headers()

                            fallback_response = {
                                "jsonrpc": "2.0",
                                "id": request_json.get("id", 1),
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
                                        "referencesProvider": True
                                    },
                                    "serverInfo": {
                                        "name": "MCP IPFS Tools Server",
                                        "version": "0.3.0"
                                    }
                                }
                            }

                            self.wfile.write(json.dumps(fallback_response).encode())
                        return
                except Exception as e:
                    logger.error(f"Error parsing JSON request: {e}")

        # Forward other POST requests directly
        try:
            logger.info(f"Proxying POST request to {MCP_SERVER_URL + self.path}")
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length) if content_length > 0 else b''

            req = urllib.request.Request(
                url=MCP_SERVER_URL + self.path,
                data=post_data,
                headers={'Content-Type': self.headers.get('Content-Type', 'application/json')},
                method='POST'
            )

            response = urllib.request.urlopen(req)

            # Forward the response
            self.send_response(response.status)
            for header in response.getheaders():
                self.send_header(header[0], header[1])
            self.end_headers()

            self.wfile.write(response.read())
        except Exception as e:
            logger.error(f"Error proxying POST request: {e}")
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

def main():
    """Run the proxy server."""
    try:
        # Create a web server and define the handler
        handler = MCPProxyHandler
        server = socketserver.TCPServer(("", PROXY_PORT), handler)

        print(f"Started MCP VS Code proxy on port {PROXY_PORT}")
        print(f"Redirecting VS Code initialize requests to {MCP_SERVER_URL + MCP_INIT_ENDPOINT}")
        print("Press Ctrl+C to stop")

        # Start the server in a separate thread
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()

        # Keep the main thread running
        while True:
            server_thread.join(1)
    except KeyboardInterrupt:
        print("Stopping MCP VS Code proxy...")
        server.shutdown()
        server.server_close()
        sys.exit(0)

if __name__ == "__main__":
    main()
