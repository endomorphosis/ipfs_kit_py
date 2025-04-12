#!/usr/bin/env python3
"""
Test script for the storage status endpoint.
"""

import uvicorn
import anyio
import logging
import aiohttp
from ipfs_kit_py.mcp.server_anyio import MCPServer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("storage_test")

async def test_storage_endpoint():
    # Create MCP server instance
    server = MCPServer(debug_mode=True)
    app = server.create_fastapi_app()
    
    # Start server in the background
    config = uvicorn.Config(app, host='127.0.0.1', port=8000, log_level='info')
    uvicorn_server = uvicorn.Server(config)
    server_task = anyio.create_task(uvicorn_server.serve())
    
    # Wait for server to start
    await anyio.sleep(5)
    
    try:
        # Make a request to the storage status endpoint
        logger.info("Making request to /api/v0/storage/status")
        async with aiohttp.ClientSession() as session:
            async with session.get('http://127.0.0.1:8000/api/v0/storage/status') as response:
                status = response.status
                text = await response.text()
                logger.info(f'Status: {status}')
                logger.info(f'Response: {text}')
                
                return status == 200
    except Exception as e:
        logger.error(f"Error testing endpoint: {e}")
        return False
    finally:
        # Stop the server
        uvicorn_server.should_exit = True
        await server_task

if __name__ == "__main__":
    result = anyio.run(test_storage_endpoint())
    exit(0 if result else 1)