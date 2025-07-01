#!/usr/bin/env python3
"""
Test FastMCP Tool Calling

This script tests how to properly call tools registered with @app.tool decorators
in the FastMCP server. Based on the code analysis, FastMCP tools may be accessible
through direct HTTP endpoints or through the app's internal router.
"""

import asyncio
import aiohttp
import json
import logging
import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("fastmcp-tool-call")

async def test_direct_tool_endpoints():
    """Test direct tool access via HTTP endpoints"""
    try:
        # Based on FastMCP pattern, tools might be accessible at direct endpoints
        tool_names = ['ipfs_add', 'ipfs_cat', 'ipfs_ls', 'ipfs_id', 'ipfs_pin_ls']
        
        async with aiohttp.ClientSession() as session:
            for tool_name in tool_names:
                logger.info(f"Testing direct endpoint for tool: {tool_name}")
                
                # Try different endpoint patterns
                endpoints = [
                    f'/tools/{tool_name}',
                    f'/{tool_name}',
                    f'/ipfs/{tool_name}',
                    f'/api/{tool_name}',
                    f'/v1/{tool_name}'
                ]
                
                for endpoint in endpoints:
                    try:
                        url = f'http://localhost:3001{endpoint}'
                        logger.info(f"  Trying: {url}")
                        
                        # Try GET first
                        async with session.get(url) as response:
                            if response.status != 404:
                                logger.info(f"    GET {response.status}: {await response.text()}")
                        
                        # Try POST with empty data
                        async with session.post(url, json={}) as response:
                            if response.status != 404:
                                logger.info(f"    POST {response.status}: {await response.text()}")
                                
                    except Exception as e:
                        logger.debug(f"    Error testing {endpoint}: {e}")
                        
    except Exception as e:
        logger.error(f"Direct endpoint test failed: {e}")

def test_inspect_server_routes():
    """Try to inspect server routes to see what's available"""
    try:
        # Test if we can get route information
        endpoints_to_check = [
            '/routes',
            '/docs', 
            '/openapi.json',
            '/debug',
            '/info',
            '/__fastapi__',
            '/meta'
        ]
        
        for endpoint in endpoints_to_check:
            try:
                url = f'http://localhost:3001{endpoint}'
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    logger.info(f"✅ Found {endpoint}: {response.text[:200]}")
                elif response.status_code != 404:
                    logger.info(f"ℹ️ {endpoint} returned {response.status_code}")
            except Exception as e:
                logger.debug(f"Error checking {endpoint}: {e}")
                
    except Exception as e:
        logger.error(f"Route inspection failed: {e}")

async def test_fastapi_autodocs():
    """Check if FastAPI automatic documentation is available"""
    try:
        async with aiohttp.ClientSession() as session:
            # Check FastAPI automatic docs
            docs_urls = ['/docs', '/redoc', '/openapi.json']
            
            for docs_url in docs_urls:
                try:
                    async with session.get(f'http://localhost:3001{docs_url}') as response:
                        if response.status == 200:
                            content = await response.text()
                            logger.info(f"✅ Found FastAPI docs at {docs_url}")
                            if docs_url == '/openapi.json':
                                # Parse OpenAPI spec to find tools
                                try:
                                    spec = json.loads(content)
                                    paths = spec.get('paths', {})
                                    logger.info(f"Available paths: {list(paths.keys())}")
                                    
                                    # Look for tool-related paths
                                    tool_paths = [path for path in paths.keys() if 'tool' in path.lower() or 'ipfs' in path.lower()]
                                    if tool_paths:
                                        logger.info(f"Tool-related paths: {tool_paths}")
                                except json.JSONDecodeError:
                                    logger.warning("Could not parse OpenAPI spec")
                            break
                except Exception as e:
                    logger.debug(f"Error checking {docs_url}: {e}")
                    
    except Exception as e:
        logger.error(f"FastAPI docs test failed: {e}")

async def test_call_tool_by_name():
    """Test calling tools by name with proper parameters"""
    try:
        async with aiohttp.ClientSession() as session:
            # Test with the simplest tool first - ipfs_id (no parameters)
            logger.info("Testing ipfs_id tool call...")
            
            # Try different call patterns based on FastMCP analysis
            call_patterns = [
                # Direct function call pattern
                {
                    'url': 'http://localhost:3001/ipfs_id',
                    'method': 'POST',
                    'data': {}
                },
                # Tool execution pattern
                {
                    'url': 'http://localhost:3001/tools/ipfs_id',
                    'method': 'POST', 
                    'data': {}
                },
                # FastMCP execution pattern
                {
                    'url': 'http://localhost:3001/call/ipfs_id',
                    'method': 'POST',
                    'data': {}
                }
            ]
            
            for pattern in call_patterns:
                try:
                    logger.info(f"  Trying {pattern['method']} {pattern['url']}")
                    
                    if pattern['method'] == 'POST':
                        async with session.post(
                            pattern['url'], 
                            json=pattern['data'],
                            headers={'Content-Type': 'application/json'}
                        ) as response:
                            status = response.status
                            text = await response.text()
                            logger.info(f"    Status: {status}")
                            if status != 404:
                                logger.info(f"    Response: {text[:300]}")
                                if status == 200:
                                    logger.info("🎉 Successfully called tool!")
                    else:
                        async with session.get(pattern['url']) as response:
                            status = response.status
                            text = await response.text()
                            logger.info(f"    Status: {status}")
                            if status != 404:
                                logger.info(f"    Response: {text[:300]}")
                                
                except Exception as e:
                    logger.debug(f"    Error: {e}")
                    
    except Exception as e:
        logger.error(f"Tool call test failed: {e}")

async def main():
    """Main test function"""
    logger.info("🔍 Testing FastMCP tool calling mechanisms...")
    
    # Test 1: Check if FastAPI docs are available
    logger.info("\n1. Checking FastAPI automatic documentation...")
    await test_fastapi_autodocs()
    
    # Test 2: Inspect available routes
    logger.info("\n2. Inspecting server routes...")
    test_inspect_server_routes()
    
    # Test 3: Test direct tool endpoints
    logger.info("\n3. Testing direct tool endpoints...")
    await test_direct_tool_endpoints()
    
    # Test 4: Test tool calling by name
    logger.info("\n4. Testing tool calls by name...")
    await test_call_tool_by_name()
    
    logger.info("\n✅ FastMCP tool calling tests completed")

if __name__ == "__main__":
    asyncio.run(main())
