#!/usr/bin/env python3
"""
Test FastMCP Integration Issue

This script demonstrates the core problem: FastMCP tools registered with @app.tool
decorators are not accessible through the Starlette app returned by server.sse_app().
We need to bridge this gap.
"""

import anyio
import aiohttp
import json
import logging
import inspect
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("fastmcp-integration-test")

async def test_fastmcp_server_inspection():
    """Test inspection of the FastMCP server object to see registered tools"""
    try:
        # Import the FastMCP server components
        from fastmcp import FastMCP
        from ipfs_fastmcp_tools import register_ipfs_tools_fastmcp
        
        # Create a test FastMCP server
        logger.info("Creating test FastMCP server...")
        server = FastMCP(name="test-server", instructions="Test server for debugging")
        
        # Register tools
        logger.info("Registering IPFS tools...")
        register_ipfs_tools_fastmcp(server)
        
        # Inspect the server object to see what tools are registered
        logger.info("\n=== FastMCP Server Inspection ===")
        logger.info(f"Server object type: {type(server)}")
        logger.info(f"Server attributes: {dir(server)}")
        
        # Look for tools in different places
        tools_found = {}
        
        # Check if server has a tools attribute
        if hasattr(server, 'tools'):
            tools = getattr(server, 'tools')
            logger.info(f"Server.tools type: {type(tools)}")
            logger.info(f"Server.tools: {tools}")
            tools_found['tools'] = tools
        
        # Check if server has a _tools attribute
        if hasattr(server, '_tools'):
            _tools = getattr(server, '_tools')
            logger.info(f"Server._tools type: {type(_tools)}")
            logger.info(f"Server._tools: {_tools}")
            tools_found['_tools'] = _tools
            
        # Check if server has a tool_registry attribute
        if hasattr(server, 'tool_registry'):
            tool_registry = getattr(server, 'tool_registry')
            logger.info(f"Server.tool_registry type: {type(tool_registry)}")
            logger.info(f"Server.tool_registry: {tool_registry}")
            tools_found['tool_registry'] = tool_registry
            
        # Check the sse_app to see what it contains
        logger.info("\n=== SSE App Inspection ===")
        sse_app = server.sse_app()
        logger.info(f"SSE app type: {type(sse_app)}")
        logger.info(f"SSE app attributes: {dir(sse_app)}")
        
        # Check routes in the SSE app
        if hasattr(sse_app, 'routes'):
            routes = sse_app.routes
            logger.info(f"SSE app routes count: {len(routes)}")
            for i, route in enumerate(routes):
                logger.info(f"Route {i}: {route}")
                if hasattr(route, 'path'):
                    logger.info(f"  Path: {route.path}")
                if hasattr(route, 'methods'):
                    logger.info(f"  Methods: {route.methods}")
                    
        return {
            'server': server,
            'tools_found': tools_found,
            'sse_app': sse_app
        }
        
    except Exception as e:
        logger.error(f"Error during FastMCP server inspection: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

async def test_tool_calling_mechanism():
    """Test how tools should be called based on FastMCP documentation"""
    try:
        logger.info("\n=== Testing Tool Calling Mechanism ===")
        
        # Test against running server
        base_url = "http://localhost:3001"
        
        # Test various potential tool calling endpoints
        test_endpoints = [
            "/tools",
            "/tool",
            "/call_tool", 
            "/mcp/tools",
            "/mcp/call_tool",
            "/api/tools",
            "/api/tool",
            "/api/call_tool"
        ]
        
        async with aiohttp.ClientSession() as session:
            for endpoint in test_endpoints:
                url = f"{base_url}{endpoint}"
                logger.info(f"Testing endpoint: {url}")
                
                try:
                    # Try GET first
                    async with session.get(url) as response:
                        logger.info(f"  GET {url}: {response.status}")
                        if response.status == 200:
                            content = await response.text()
                            logger.info(f"  Response: {content[:200]}...")
                        
                    # Try POST with tool call payload
                    payload = {
                        "tool": "ipfs_id",
                        "params": {}
                    }
                    async with session.post(url, json=payload) as response:
                        logger.info(f"  POST {url}: {response.status}")
                        if response.status == 200:
                            content = await response.text()
                            logger.info(f"  Response: {content[:200]}...")
                            
                except Exception as e:
                    logger.info(f"  Error: {e}")
                    
    except Exception as e:
        logger.error(f"Error testing tool calling mechanism: {e}")

async def test_json_rpc_tool_calls():
    """Test tool calls via JSON-RPC endpoint"""
    try:
        logger.info("\n=== Testing JSON-RPC Tool Calls ===")
        
        base_url = "http://localhost:3001"
        endpoints = ["/jsonrpc", "/api/v0/jsonrpc"]
        
        async with aiohttp.ClientSession() as session:
            for endpoint in endpoints:
                url = f"{base_url}{endpoint}"
                logger.info(f"Testing JSON-RPC endpoint: {url}")
                
                # Test tools list
                tools_payload = {
                    "jsonrpc": "2.0",
                    "method": "tools/list",
                    "id": 1
                }
                
                try:
                    async with session.post(url, json=tools_payload) as response:
                        logger.info(f"  tools/list: {response.status}")
                        if response.status == 200:
                            content = await response.json()
                            logger.info(f"  Tools response: {content}")
                            
                except Exception as e:
                    logger.info(f"  Error with tools/list: {e}")
                
                # Test tool call
                call_payload = {
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {
                        "name": "ipfs_id",
                        "arguments": {}
                    },
                    "id": 2
                }
                
                try:
                    async with session.post(url, json=call_payload) as response:
                        logger.info(f"  tools/call: {response.status}")
                        if response.status == 200:
                            content = await response.json()
                            logger.info(f"  Call response: {content}")
                            
                except Exception as e:
                    logger.info(f"  Error with tools/call: {e}")
                    
    except Exception as e:
        logger.error(f"Error testing JSON-RPC tool calls: {e}")

async def main():
    """Main test function"""
    logger.info("Starting FastMCP Integration Test")
    
    # Test 1: Inspect FastMCP server structure
    inspection_result = await test_fastmcp_server_inspection()
    
    # Test 2: Test tool calling mechanisms
    await test_tool_calling_mechanism()
    
    # Test 3: Test JSON-RPC tool calls
    await test_json_rpc_tool_calls()
    
    logger.info("\n=== Summary ===")
    if inspection_result:
        tools_found = inspection_result['tools_found']
        logger.info(f"Tools found in FastMCP server: {list(tools_found.keys())}")
        for key, value in tools_found.items():
            if value:
                if isinstance(value, dict):
                    logger.info(f"  {key}: {len(value)} tools - {list(value.keys())}")
                else:
                    logger.info(f"  {key}: {type(value)} - {value}")
    
    logger.info("The issue is that FastMCP tools are registered with the server object")
    logger.info("but are not exposed through HTTP endpoints in the Starlette SSE app.")
    logger.info("We need to create a bridge to make these tools accessible via HTTP.")

if __name__ == "__main__":
    anyio.run(main)
