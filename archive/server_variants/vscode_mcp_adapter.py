#!/usr/bin/env python3
"""
VS Code MCP Adapter

This script creates an adapter for MCP servers to make them compatible with
VS Code's MCP extension by transforming the response format.
"""

import os
import sys
import json
import logging
import argparse
import requests
from flask import Flask, jsonify, request, Response
from flask_cors import CORS
import threading
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("vscode_mcp_adapter.log")
    ]
)
logger = logging.getLogger("vscode-mcp-adapter")

# Create Flask app
app = Flask(__name__)
CORS(app)

# Global variables
backend_url = "http://localhost:9998"
adapter_port = 9999
tool_cache = []
tool_cache_time = 0
CACHE_TTL = 60  # Cache time to live in seconds

def update_tool_cache():
    """Update the tool cache from the backend server."""
    global tool_cache, tool_cache_time
    
    current_time = time.time()
    if current_time - tool_cache_time < CACHE_TTL and tool_cache:
        return tool_cache
    
    try:
        response = requests.get(f"{backend_url}/tools", timeout=5)
        if response.status_code == 200:
            data = response.json()
            
            # Transform response based on format
            if isinstance(data, dict) and 'tools' in data:
                # Handle nested format: {"tools": [...]}
                tools = data['tools']
            elif isinstance(data, list):
                # Handle flat format: [...]
                tools = data
            else:
                logger.error(f"Unexpected tool response format: {data}")
                tools = []
            
            tool_cache = tools
            tool_cache_time = current_time
            logger.info(f"Updated tool cache with {len(tools)} tools")
            return tools
        else:
            logger.error(f"Failed to fetch tools: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        logger.error(f"Error updating tool cache: {e}")
        return []

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    try:
        response = requests.get(f"{backend_url}/health", timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            return jsonify({
                "status": "error",
                "message": f"Backend server returned {response.status_code}"
            }), 500
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/tools', methods=['GET'])
def tools():
    """Get tools in the format expected by VS Code."""
    tools = update_tool_cache()
    
    # Return as a flat array for VS Code
    return jsonify(tools)

@app.route('/sse', methods=['GET'])
def sse():
    """SSE endpoint for VS Code."""
    # Check if backend has an SSE endpoint
    try:
        response = requests.get(f"{backend_url}/sse", stream=True, timeout=2)
        if response.status_code == 200:
            # If backend has SSE, proxy it
            def generate():
                for chunk in response.iter_content(chunk_size=1024):
                    yield chunk
            
            return Response(generate(), mimetype='text/event-stream')
        else:
            # If backend has no SSE, create a simple one
            def generate():
                while True:
                    yield f"data: {json.dumps({'type': 'ping'})}\n\n"
                    time.sleep(30)
            
            return Response(generate(), mimetype='text/event-stream')
    except Exception as e:
        logger.error(f"Error setting up SSE: {e}")
        # Return a simple SSE endpoint
        def generate():
            while True:
                yield f"data: {json.dumps({'type': 'ping', 'error': str(e)})}\n\n"
                time.sleep(30)
        
        return Response(generate(), mimetype='text/event-stream')

@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy(path):
    """Proxy all other requests to the backend server."""
    try:
        # Forward the request to the backend
        backend_path = f"{backend_url}/{path}"
        
        # Create headers dictionary from the request
        headers = {key: value for key, value in request.headers if key != 'Host'}
        
        # Forward the request with the same method, headers and data
        if request.method == 'GET':
            response = requests.get(backend_path, headers=headers, params=request.args, timeout=30)
        elif request.method == 'POST':
            response = requests.post(backend_path, headers=headers, data=request.get_data(), timeout=30)
        elif request.method == 'PUT':
            response = requests.put(backend_path, headers=headers, data=request.get_data(), timeout=30)
        elif request.method == 'DELETE':
            response = requests.delete(backend_path, headers=headers, params=request.args, timeout=30)
        else:
            return jsonify({
                "error": f"Unsupported method: {request.method}"
            }), 400
        
        # Return the response with the same status code and headers
        return Response(
            response.content, 
            status=response.status_code,
            headers={k: v for k, v in response.headers.items() if k != 'Transfer-Encoding'}
        )
    except Exception as e:
        logger.error(f"Error proxying request to {path}: {e}")
        return jsonify({
            "error": str(e)
        }), 500

def run_adapter(backend, port):
    """Run the adapter server."""
    global backend_url, adapter_port
    backend_url = backend
    adapter_port = port
    
    # Update cache before starting
    update_tool_cache()
    
    # Start a thread to periodically update the cache
    def cache_updater():
        while True:
            try:
                update_tool_cache()
            except Exception as e:
                logger.error(f"Error in cache updater: {e}")
            time.sleep(CACHE_TTL)
    
    threading.Thread(target=cache_updater, daemon=True).start()
    
    # Run the Flask app
    logger.info(f"Starting VS Code MCP adapter on port {port} for backend {backend}")
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)

def main():
    """Main function to parse arguments and start the adapter."""
    parser = argparse.ArgumentParser(description="VS Code MCP Adapter")
    parser.add_argument("--backend", default="http://localhost:9998", help="Backend MCP server URL")
    parser.add_argument("--port", type=int, default=9999, help="Port to run the adapter on")
    args = parser.parse_args()
    
    run_adapter(args.backend, args.port)

if __name__ == "__main__":
    main()
