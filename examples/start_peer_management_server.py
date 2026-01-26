#!/usr/bin/env python3
"""
Start the Enhanced MCP Server with Peer Management
"""
import anyio
import uvicorn
from mcp.ipfs_kit.modular_enhanced_mcp_server import ModularEnhancedMCPServer


async def main():
    print("🚀 Starting IPFS Kit MCP Server with Peer Management...")
    
    # Initialize the server
    server = ModularEnhancedMCPServer()
    
    # Run the FastAPI app
    config = uvicorn.Config(
        server.app,
        host="127.0.0.1",
        port=8765,
        log_level="info"
    )
    server_instance = uvicorn.Server(config)
    
    print("✓ Server ready at http://127.0.0.1:8765")
    print("✓ Dashboard available at http://127.0.0.1:8765/dashboard")
    print("✓ Peer Management available in the dashboard")
    
    await server_instance.serve()


if __name__ == "__main__":
    anyio.run(main)
