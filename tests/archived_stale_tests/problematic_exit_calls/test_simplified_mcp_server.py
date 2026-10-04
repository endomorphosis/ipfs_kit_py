#!/usr/bin/env python3
"""
Test script for the simplified MCP server with ipfs_kit_py integration.
"""

import subprocess
import sys
import json
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_mcp_server():
    """Test the MCP server by starting it and sending some basic requests."""
    
    from pathlib import Path
    repo_root = Path(__file__).resolve().parents[3]
    server_script = str((repo_root / "mcp" / "enhanced_mcp_server_with_daemon_mgmt.py").resolve())
    
    logger.info("Starting MCP server...")
    
    try:
        # Start the server process
        process = subprocess.Popen(
            [sys.executable, server_script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=0
        )
        
        # Give it time to initialize
        time.sleep(3)
        
        # Test 1: Initialize request
        logger.info("Sending initialize request...")
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        }
        
        process.stdin.write(json.dumps(init_request) + "\n")
        process.stdin.flush()
        
        # Read response
        response_line = process.stdout.readline()
        if response_line:
            init_response = json.loads(response_line.strip())
            logger.info(f"Initialize response: {init_response}")
        else:
            logger.error("No response to initialize request")
        
        # Test 2: Tools list request
        logger.info("Sending tools/list request...")
        tools_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        
        process.stdin.write(json.dumps(tools_request) + "\n")
        process.stdin.flush()
        
        # Read response
        response_line = process.stdout.readline()
        if response_line:
            tools_response = json.loads(response_line.strip())
            logger.info(f"Tools count: {len(tools_response.get('result', {}).get('tools', []))}")
        else:
            logger.error("No response to tools/list request")
        
        # Test 3: Test ipfs_version tool
        logger.info("Testing ipfs_version tool...")
        version_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "ipfs_version",
                "arguments": {}
            }
        }
        
        process.stdin.write(json.dumps(version_request) + "\n")
        process.stdin.flush()
        
        # Read response
        response_line = process.stdout.readline()
        if response_line:
            version_response = json.loads(response_line.strip())
            logger.info(f"IPFS version response: {version_response}")
        else:
            logger.error("No response to ipfs_version request")
        
        # Cleanup
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            
        logger.info("Test completed successfully!")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = test_mcp_server()
    if success:
        print("✓ MCP Server test passed!")
        sys.exit(0)
    else:
        print("✗ MCP Server test failed!")
        sys.exit(1)
