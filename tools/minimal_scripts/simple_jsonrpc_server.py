#!/usr/bin/env python3
import json
import http.server
import socketserver

PORT = 9995

class JSONRPCHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/jsonrpc":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            request = json.loads(post_data.decode('utf-8'))
            
            # Create a response based on the request method
            if request.get("method") == "initialize":
                response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
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
            elif request.get("method") == "shutdown":
                response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "result": None
                }
            elif request.get("method") == "exit":
                response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "result": None
                }
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "error": {
                        "code": -32601,
                        "message": f"Method '{request.get('method')}' not found"
                    }
                }
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {
                "message": "Simple MCP JSON-RPC Server is running",
                "endpoints": {
                    "jsonrpc": "/jsonrpc"
                }
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

print(f"Starting simple JSON-RPC server on port {PORT}...")
with socketserver.TCPServer(("", PORT), JSONRPCHandler) as httpd:
    print(f"Server running at http://localhost:{PORT}/")
    httpd.serve_forever()
