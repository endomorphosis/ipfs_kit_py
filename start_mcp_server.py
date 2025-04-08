#!/usr/bin/env python3
"""
Direct script to start the MCP server for testing.
"""

import sys
from mcp_wrapper import start_mcp_server, server_ready

def main():
    """Start the MCP server directly."""
    print("Starting MCP server...")
    start_mcp_server()
    
    if server_ready.is_set():
        print("MCP server started successfully.")
        print("Server is running on port 9999.")
        print("Available endpoints:")
        print("  - http://127.0.0.1:9999/api/v0/mcp/health")
        print("  - http://127.0.0.1:9999/api/v0/mcp/ipfs/add")
        print("  - http://127.0.0.1:9999/api/v0/mcp/ipfs/cat/{cid}")
        print("  - http://127.0.0.1:9999/api/v0/mcp/ipfs/pin/ls")
        print("\nPress Ctrl+C to stop the server.")
        
        # Keep the script running
        try:
            while True:
                pass
        except KeyboardInterrupt:
            print("\nStopping MCP server...")
            return 0
    else:
        print("Failed to start MCP server.")
        return 1

if __name__ == "__main__":
    sys.exit(main())