#!/usr/bin/env python3
"""
Test FastMCP Protocol Communication

This script tests the actual protocol communication with the FastMCP server
to understand how tools are exposed and accessed.
"""

import anyio
import aiohttp
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("fastmcp-test")

async def test_sse_connection():
    """Test SSE connection to see what the server sends"""
    try:
        async with aiohttp.ClientSession() as session:
            logger.info("Testing SSE endpoint...")
            async with session.get('http://localhost:3001/sse') as response:
                logger.info(f"SSE Response status: {response.status}")
                logger.info(f"SSE Response headers: {dict(response.headers)}")
                
                if response.status == 200:
                    logger.info("Reading SSE stream...")
                    async for line in response.content:
                        line_str = line.decode('utf-8').strip()
                        if line_str:
                            logger.info(f"SSE Line: {line_str}")
                            # Break after a few lines to avoid infinite loop
                            break
                else:
                    text = await response.text()
                    logger.error(f"SSE failed: {text}")
    except Exception as e:
        logger.error(f"SSE connection failed: {e}")

async def test_mcp_initialize():
    """Test MCP initialize protocol via HTTP POST"""
    try:
        async with aiohttp.ClientSession() as session:
            logger.info("Testing MCP initialize...")
            
            # Standard MCP initialize request
            initialize_request = {
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
            
            # Try different endpoints
            endpoints = ['/jsonrpc', '/initialize', '/mcp']
            
            for endpoint in endpoints:
                try:
                    logger.info(f"Trying endpoint: {endpoint}")
                    async with session.post(
                        f'http://localhost:3001{endpoint}',
                        json=initialize_request,
                        headers={'Content-Type': 'application/json'}
                    ) as response:
                        logger.info(f"Response status: {response.status}")
                        text = await response.text()
                        logger.info(f"Response: {text[:500]}")
                        
                        if response.status == 200:
                            try:
                                data = json.loads(text)
                                logger.info(f"Parsed response: {json.dumps(data, indent=2)}")
                            except json.JSONDecodeError:
                                logger.info("Response is not JSON")
                        
                except Exception as e:
                    logger.error(f"Error with endpoint {endpoint}: {e}")
                    
    except Exception as e:
        logger.error(f"Initialize test failed: {e}")

async def test_tools_list():
    """Test tools/list method"""
    try:
        async with aiohttp.ClientSession() as session:
            logger.info("Testing tools/list...")
            
            tools_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {}
            }
            
            endpoints = ['/jsonrpc', '/tools', '/api/v0/tools']
            
            for endpoint in endpoints:
                try:
                    logger.info(f"Trying tools endpoint: {endpoint}")
                    async with session.post(
                        f'http://localhost:3001{endpoint}',
                        json=tools_request,
                        headers={'Content-Type': 'application/json'}
                    ) as response:
                        logger.info(f"Response status: {response.status}")
                        text = await response.text()
                        logger.info(f"Response: {text[:500]}")
                        
                        if response.status == 200:
                            try:
                                data = json.loads(text)
                                logger.info(f"Tools response: {json.dumps(data, indent=2)}")
                                
                                # If we get tools, try to call one
                                if 'result' in data and 'tools' in data['result']:
                                    tools = data['result']['tools']
                                    if tools:
                                        logger.info(f"Found {len(tools)} tools!")
                                        for tool in tools[:3]:  # Show first 3 tools
                                            logger.info(f"Tool: {tool.get('name', 'unknown')} - {tool.get('description', '')}")
                                        return tools
                            except json.JSONDecodeError:
                                logger.info("Response is not JSON")
                        
                except Exception as e:
                    logger.error(f"Error with tools endpoint {endpoint}: {e}")
                    
    except Exception as e:
        logger.error(f"Tools test failed: {e}")
    
    return None

async def test_tool_call(tools=None):
    """Test calling a tool"""
    if not tools:
        logger.info("No tools available to test")
        return
        
    try:
        async with aiohttp.ClientSession() as session:
            # Try to call the first tool
            tool = tools[0]
            tool_name = tool.get('name', 'unknown')
            
            logger.info(f"Testing tool call: {tool_name}")
            
            tool_request = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": {}
                }
            }
            
            endpoints = ['/jsonrpc', f'/tools/{tool_name}', '/api/v0/tools/call']
            
            for endpoint in endpoints:
                try:
                    logger.info(f"Trying tool call endpoint: {endpoint}")
                    async with session.post(
                        f'http://localhost:3001{endpoint}',
                        json=tool_request,
                        headers={'Content-Type': 'application/json'}
                    ) as response:
                        logger.info(f"Response status: {response.status}")
                        text = await response.text()
                        logger.info(f"Response: {text[:500]}")
                        
                        if response.status == 200:
                            try:
                                data = json.loads(text)
                                logger.info(f"Tool call response: {json.dumps(data, indent=2)}")
                            except json.JSONDecodeError:
                                logger.info("Response is not JSON")
                        
                except Exception as e:
                    logger.error(f"Error with tool call endpoint {endpoint}: {e}")
                    
    except Exception as e:
        logger.error(f"Tool call test failed: {e}")

async def main():
    """Main test function"""
    logger.info("Starting FastMCP protocol tests...")
    
    # Test 1: SSE connection
    await test_sse_connection()
    
    # Test 2: MCP initialize
    await test_mcp_initialize()
    
    # Test 3: Tools list
    tools = await test_tools_list()
    
    # Test 4: Tool call
    await test_tool_call(tools)
    
    logger.info("FastMCP protocol tests completed")

if __name__ == "__main__":
    anyio.run(main)
