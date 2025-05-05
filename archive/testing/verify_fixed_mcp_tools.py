#!/usr/bin/env python3
"""
MCP Server Tools Verification

This script checks the health, functionality, and model support of the MCP server.
"""

import os
import sys
import json
import time
import logging
import argparse
import requests
import socket
import subprocess
from urllib.parse import urljoin
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple, Set

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("verification.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("verification")

# Default server URL
DEFAULT_SERVER_URL = "http://localhost:8000"

# Timeout for requests
REQUEST_TIMEOUT = 5.0  # seconds

# Required model count
REQUIRED_MODEL_COUNT = 53

def check_server_running(url: str) -> bool:
    """Check if the server is running."""
    try:
        resp = requests.get(urljoin(url, "/health"), timeout=REQUEST_TIMEOUT)
        return resp.status_code == 200
    except Exception as e:
        logger.error(f"Error checking server status: {e}")
        return False

def check_port_in_use(port: int) -> bool:
    """Check if a port is in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def send_jsonrpc_request(url: str, method: str, params: Any = None) -> Optional[Dict[str, Any]]:
    """Send a JSON-RPC request to the server."""
    try:
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": int(time.time() * 1000)
        }
        
        resp = requests.post(urljoin(url, "/jsonrpc"), json=payload, timeout=REQUEST_TIMEOUT)
        
        if resp.status_code != 200:
            logger.error(f"JSON-RPC request failed with status code {resp.status_code}")
            return None
        
        data = resp.json()
        
        if "error" in data:
            logger.error(f"JSON-RPC error: {data['error']}")
            return None
        
        return data.get("result")
    
    except Exception as e:
        logger.error(f"Error sending JSON-RPC request: {e}")
        return None

def get_available_models(url: str) -> List[Dict[str, Any]]:
    """Get available models from the server."""
    result = send_jsonrpc_request(url, "list_models")
    
    if result is None or not isinstance(result, dict):
        logger.error("Invalid model list returned")
        return []
    
    # Return as list of model objects
    models = [model for _, model in result.items() if isinstance(model, dict)]
    return models

def check_model_support(url: str) -> Tuple[bool, int]:
    """Check if the server supports the required number of models."""
    models = get_available_models(url)
    
    if not models:
        logger.error("Failed to retrieve models")
        return False, 0
    
    model_count = len(models)
    
    # Log model information
    model_providers = {}
    model_types = {}
    
    for model in models:
        if not isinstance(model, dict):
            continue
            
        provider = model.get("provider", "unknown")
        model_type = model.get("type", "unknown")
        
        if provider not in model_providers:
            model_providers[provider] = 0
        model_providers[provider] += 1
        
        if model_type not in model_types:
            model_types[model_type] = 0
        model_types[model_type] += 1
    
    # Log model statistics
    logger.info(f"Found {model_count} models:")
    
    logger.info("Models by provider:")
    for provider, count in sorted(model_providers.items(), key=lambda x: x[1], reverse=True):
        logger.info(f"  - {provider}: {count} models")
    
    logger.info("Models by type:")
    for model_type, count in sorted(model_types.items(), key=lambda x: x[1], reverse=True):
        logger.info(f"  - {model_type}: {count} models")
    
    # Check if we have enough models
    if model_count >= REQUIRED_MODEL_COUNT:
        logger.info(f"✅ Server supports {model_count} models (required: {REQUIRED_MODEL_COUNT})")
        return True, model_count
    else:
        logger.warning(f"❌ Server only supports {model_count} models (required: {REQUIRED_MODEL_COUNT})")
        return False, model_count

def check_tool_availability(url: str) -> Tuple[bool, int]:
    """Check if the server has tools available."""
    result = send_jsonrpc_request(url, "list_tools")
    
    if result is None:
        return False, 0
    
    tool_count = len(result)
    
    if tool_count > 0:
        logger.info(f"✅ Server has {tool_count} tools available")
        
        # Log tool information
        for tool in result:
            logger.info(f"  - {tool.get('name', 'Unknown tool')}: {tool.get('description', 'No description')}")
        
        return True, tool_count
    else:
        logger.warning("❌ Server has no tools available")
        return False, 0

def check_resource_handler(url: str) -> bool:
    """Check if the server has resource handler available."""
    try:
        resp = requests.get(urljoin(url, "/resources"), timeout=REQUEST_TIMEOUT)
        
        if resp.status_code == 200:
            logger.info("✅ Resource handler is available")
            
            # Try getting a list of resources
            data = resp.json()
            
            if data and isinstance(data, list):
                logger.info(f"Found {len(data)} resources")
                
                # Log resource information
                for resource in data[:5]:  # Show at most 5 resources
                    logger.info(f"  - {resource}")
                
                if len(data) > 5:
                    logger.info(f"  - ... and {len(data) - 5} more")
            
            return True
        else:
            logger.warning("❌ Resource handler returned non-200 status code")
            return False
    
    except Exception as e:
        logger.error(f"Error checking resource handler: {e}")
        return False

def check_jsonrpc_handler(url: str) -> bool:
    """Check if the JSON-RPC handler is working."""
    result = send_jsonrpc_request(url, "ping")
    
    if result == "pong":
        logger.info("✅ JSON-RPC handler is working")
        return True
    else:
        logger.warning("❌ JSON-RPC handler is not working properly")
        return False

def start_server(script_path: str) -> Optional[subprocess.Popen]:
    """Start the server using the provided script."""
    try:
        logger.info(f"Starting server using {script_path}")
        
        # Make the script executable
        os.chmod(script_path, 0o755)
        
        # Start the server
        process = subprocess.Popen([script_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Wait for the server to start
        logger.info("Waiting for server to start...")
        time.sleep(5)
        
        return process
    
    except Exception as e:
        logger.error(f"Error starting server: {e}")
        return None

def stop_server(process: subprocess.Popen) -> None:
    """Stop the server."""
    if process:
        try:
            logger.info("Stopping server...")
            process.terminate()
            process.wait(timeout=5)
            logger.info("Server stopped")
        except Exception as e:
            logger.error(f"Error stopping server: {e}")
            process.kill()

def verify_server(url: str) -> bool:
    """Verify the server functionality."""
    if not check_server_running(url):
        logger.error("❌ Server is not running")
        return False
    
    logger.info("✅ Server is running")
    
    # Check JSON-RPC handler
    jsonrpc_ok = check_jsonrpc_handler(url)
    
    # Check model support
    models_ok, model_count = check_model_support(url)
    
    # Check tool availability
    tools_ok, tool_count = check_tool_availability(url)
    
    # Check resource handler
    resources_ok = check_resource_handler(url)
    
    # Overall assessment
    if jsonrpc_ok and models_ok and tools_ok and resources_ok:
        logger.info("🎉 All checks passed! The server is working properly.")
        logger.info(f"✓ JSON-RPC: Working")
        logger.info(f"✓ Models: {model_count} available (>= {REQUIRED_MODEL_COUNT})")
        logger.info(f"✓ Tools: {tool_count} available")
        logger.info(f"✓ Resource handler: Working")
        return True
    else:
        logger.warning("❌ Some checks failed.")
        logger.info(f"{'✓' if jsonrpc_ok else '✗'} JSON-RPC: {'Working' if jsonrpc_ok else 'Not working'}")
        logger.info(f"{'✓' if models_ok else '✗'} Models: {model_count} available {f'(>= {REQUIRED_MODEL_COUNT})' if models_ok else f'(< {REQUIRED_MODEL_COUNT})'}")
        logger.info(f"{'✓' if tools_ok else '✗'} Tools: {tool_count} available")
        logger.info(f"{'✓' if resources_ok else '✗'} Resource handler: {'Working' if resources_ok else 'Not working'}")
        return False

def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Verify MCP server functionality")
    parser.add_argument('--url', default=DEFAULT_SERVER_URL, help="Server URL")
    parser.add_argument('--start', help="Path to server startup script")
    parser.add_argument('--port', type=int, default=8000, help="Server port")
    args = parser.parse_args()
    
    # Override the URL with the port if provided
    if args.port != 8000:
        args.url = f"http://localhost:{args.port}"
    
    logger.info("Starting verification process")
    
    # Check if server is already running
    server_running = check_port_in_use(args.port)
    server_process = None
    
    if not server_running and args.start:
        # Start the server
        server_process = start_server(args.start)
        
        if not server_process:
            logger.error("Failed to start server")
            return 1
    
    # Verify server
    success = verify_server(args.url)
    
    # Stop server if we started it
    if server_process:
        stop_server(server_process)
    
    logger.info("Verification process completed")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
