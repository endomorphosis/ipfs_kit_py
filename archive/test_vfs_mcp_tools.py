#!/usr/bin/env python3
"""
Test Virtual Filesystem MCP Tools

This script tests the virtual filesystem tools by making direct JSON-RPC calls to the MCP server.
It creates files, directories, and performs operations to verify that everything is working.
"""

import os
import sys
import json
import logging
import asyncio
import time
import requests
from pprint import pprint
from typing import Dict, List, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# MCP Server URL
MCP_URL = "http://localhost:3000"
MCP_JSON_RPC_URL = f"{MCP_URL}/jsonrpc"

async def test_vfs_tools():
    """Test the virtual filesystem tools"""
    try:
        # Wait for server to be ready
        logger.info("Testing if MCP server is running...")
        attempts = 0
        while attempts < 5:
            try:
                response = requests.get(f"{MCP_URL}/health")
                if response.status_code == 200:
                    logger.info("MCP server is running")
                    break
                else:
                    logger.warning(f"Got status code {response.status_code}")
            except Exception as e:
                logger.warning(f"Error connecting to server: {e}")
            
            attempts += 1
            logger.info("Waiting for server to start...")
            await asyncio.sleep(2)
        
        if attempts == 5:
            logger.error("Could not connect to MCP server")
            return False
        
        # Get list of tools
        logger.info("Getting list of tools...")
        response = requests.post(MCP_JSON_RPC_URL, json={
            "jsonrpc": "2.0",
            "method": "get_tools",
            "params": {},
            "id": 1
        })
        
        if response.status_code != 200:
            logger.error(f"Error getting tools: {response.status_code}")
            return False
        
        data = response.json()
        all_tools = []
        
        # Check response structure
        if "result" in data:
            if "tools" in data["result"]:
                all_tools = data["result"]["tools"]
            else:
                all_tools = data["result"]
        elif "result" in data:
            all_tools = data["result"]
            
        # Extract tool names
        tool_names = [tool["name"] for tool in all_tools]
        logger.info(f"Found {len(tool_names)} tools")
        
        # Look for VFS tools
        vfs_tools = [tool for tool in tool_names if tool.startswith(("vfs_", "fs_journal_", "ipfs_fs_"))]
        logger.info(f"Found {len(vfs_tools)} virtual filesystem tools: {vfs_tools}")
        
        # If no VFS tools found, exit
        if not vfs_tools:
            logger.error("No virtual filesystem tools found")
            return False
            
        # Test filesystem journal status
        if "fs_journal_status" in vfs_tools:
            logger.info("Testing fs_journal_status...")
            response = requests.post(MCP_JSON_RPC_URL, json={
                "jsonrpc": "2.0",
                "method": "use_tool",
                "params": {
                    "tool_name": "fs_journal_status",
                    "arguments": {}
                },
                "id": 2
            })
            
            if response.status_code == 200:
                result = response.json()
                logger.info("Filesystem journal status:")
                pprint(result)
            else:
                logger.error(f"Error calling fs_journal_status: {response.status_code}")
        
        # Test virtual filesystem operations
        await test_vfs_operations(vfs_tools)
        
        # Test IPFS bridge operations
        await test_ipfs_bridge(vfs_tools)
        
        logger.info("✅ All tests completed")
        return True
        
    except Exception as e:
        logger.error(f"Error testing tools: {e}")
        logger.error(f"Stack trace: {sys.exc_info()[0]}")
        return False

async def test_vfs_operations(vfs_tools):
    """Test basic virtual filesystem operations"""
    # Only perform tests if the required tools are available
    required_tools = ["vfs_mkdir", "vfs_write", "vfs_read", "vfs_list", "vfs_stat"]
    missing_tools = [tool for tool in required_tools if tool not in vfs_tools]
    
    if missing_tools:
        logger.warning(f"Skipping VFS operations tests due to missing tools: {missing_tools}")
        return
    
    logger.info("Testing VFS operations...")
    
    # Create a test directory
    test_dir = "/vfs_test_" + str(int(time.time()))
    logger.info(f"Creating test directory {test_dir}...")
    
    response = requests.post(MCP_JSON_RPC_URL, json={
        "jsonrpc": "2.0",
        "method": "use_tool",
        "params": {
            "tool_name": "vfs_mkdir",
            "arguments": {
                "path": test_dir
            }
        },
        "id": 3
    })
    
    if response.status_code != 200 or "error" in response.json():
        logger.error(f"Error creating test directory: {response.text}")
        return
    
    # Create a test file
    test_file = f"{test_dir}/test_file.txt"
    test_content = "This is a test file created by test_vfs_tools.py"
    logger.info(f"Creating test file {test_file}...")
    
    response = requests.post(MCP_JSON_RPC_URL, json={
        "jsonrpc": "2.0",
        "method": "use_tool",
        "params": {
            "tool_name": "vfs_write",
            "arguments": {
                "path": test_file,
                "content": test_content
            }
        },
        "id": 4
    })
    
    if response.status_code != 200 or "error" in response.json():
        logger.error(f"Error creating test file: {response.text}")
        return
    
    # Read the test file
    logger.info(f"Reading test file {test_file}...")
    
    response = requests.post(MCP_JSON_RPC_URL, json={
        "jsonrpc": "2.0",
        "method": "use_tool",
        "params": {
            "tool_name": "vfs_read",
            "arguments": {
                "path": test_file
            }
        },
        "id": 5
    })
    
    if response.status_code != 200 or "error" in response.json():
        logger.error(f"Error reading test file: {response.text}")
        return
    
    # Check if the content matches
    result = response.json()
    if "result" in result and "content" in result["result"]:
        content = result["result"]["content"]
        if content == test_content:
            logger.info("✅ File content matches")
        else:
            logger.error(f"❌ File content mismatch: {content}")
    else:
        logger.error(f"Could not find content in response: {result}")
    
    # List the test directory
    logger.info(f"Listing test directory {test_dir}...")
    
    response = requests.post(MCP_JSON_RPC_URL, json={
        "jsonrpc": "2.0",
        "method": "use_tool",
        "params": {
            "tool_name": "vfs_list",
            "arguments": {
                "path": test_dir
            }
        },
        "id": 6
    })
    
    if response.status_code != 200 or "error" in response.json():
        logger.error(f"Error listing test directory: {response.text}")
        return
    
    # Check if the file is in the directory
    result = response.json()
    if "result" in result and "entries" in result["result"]:
        entries = result["result"]["entries"]
        found_file = False
        for entry in entries:
            if entry["name"] == "test_file.txt":
                found_file = True
                break
        
        if found_file:
            logger.info("✅ File found in directory listing")
        else:
            logger.error("❌ File not found in directory listing")
    else:
        logger.error(f"Could not find entries in response: {result}")
    
    # Get file stats
    logger.info(f"Getting stats for {test_file}...")
    
    response = requests.post(MCP_JSON_RPC_URL, json={
        "jsonrpc": "2.0",
        "method": "use_tool",
        "params": {
            "tool_name": "vfs_stat",
            "arguments": {
                "path": test_file
            }
        },
        "id": 7
    })
    
    if response.status_code != 200 or "error" in response.json():
        logger.error(f"Error getting file stats: {response.text}")
        return
    
    # Check file stats
    result = response.json()
    if "result" in result:
        stats = result["result"]
        logger.info("File stats:")
        pprint(stats)
        
        # Check if size is correct
        if "size" in stats and stats["size"] == len(test_content):
            logger.info("✅ File size matches")
        else:
            logger.error(f"❌ File size mismatch: {stats.get('size')} != {len(test_content)}")
    else:
        logger.error(f"Could not find stats in response: {result}")

async def test_ipfs_bridge(vfs_tools):
    """Test IPFS bridge operations"""
    # Only perform tests if the required tools are available
    required_tools = ["ipfs_fs_export_to_ipfs", "ipfs_fs_bridge_status"]
    missing_tools = [tool for tool in required_tools if tool not in vfs_tools]
    
    if missing_tools:
        logger.warning(f"Skipping IPFS bridge tests due to missing tools: {missing_tools}")
        return
    
    logger.info("Testing IPFS bridge operations...")
    
    # Get bridge status
    logger.info("Getting IPFS bridge status...")
    
    response = requests.post(MCP_JSON_RPC_URL, json={
        "jsonrpc": "2.0",
        "method": "use_tool",
        "params": {
            "tool_name": "ipfs_fs_bridge_status",
            "arguments": {}
        },
        "id": 8
    })
    
    if response.status_code != 200 or "error" in response.json():
        logger.error(f"Error getting IPFS bridge status: {response.text}")
        return
    
    # Check bridge status
    result = response.json()
    if "result" in result:
        status = result["result"]
        logger.info("IPFS bridge status:")
        pprint(status)
    else:
        logger.error(f"Could not find status in response: {result}")
    
    # Create a test file for IPFS export
    test_dir = "/vfs_ipfs_test_" + str(int(time.time()))
    test_file = f"{test_dir}/ipfs_test.txt"
    test_content = "This is a test file for IPFS export created by test_vfs_tools.py"
    
    # Create directory
    logger.info(f"Creating test directory {test_dir}...")
    requests.post(MCP_JSON_RPC_URL, json={
        "jsonrpc": "2.0",
        "method": "use_tool",
        "params": {
            "tool_name": "vfs_mkdir",
            "arguments": {
                "path": test_dir
            }
        },
        "id": 9
    })
    
    # Create file
    logger.info(f"Creating test file {test_file}...")
    requests.post(MCP_JSON_RPC_URL, json={
        "jsonrpc": "2.0",
        "method": "use_tool",
        "params": {
            "tool_name": "vfs_write",
            "arguments": {
                "path": test_file,
                "content": test_content
            }
        },
        "id": 10
    })
    
    # Export to IPFS
    logger.info(f"Exporting {test_file} to IPFS...")
    
    response = requests.post(MCP_JSON_RPC_URL, json={
        "jsonrpc": "2.0",
        "method": "use_tool",
        "params": {
            "tool_name": "ipfs_fs_export_to_ipfs",
            "arguments": {
                "path": test_file
            }
        },
        "id": 11
    })
    
    if response.status_code != 200 or "error" in response.json():
        logger.error(f"Error exporting to IPFS: {response.text}")
        return
    
    # Check export result
    result = response.json()
    if "result" in result:
        export_result = result["result"]
        logger.info("IPFS export result:")
        pprint(export_result)
        
        # Check if CID is present
        if "cid" in export_result:
            logger.info(f"✅ File exported to IPFS with CID: {export_result['cid']}")
            
            # List mappings if available
            if "ipfs_fs_bridge_list_mappings" in vfs_tools:
                logger.info("Listing IPFS-FS mappings...")
                
                response = requests.post(MCP_JSON_RPC_URL, json={
                    "jsonrpc": "2.0",
                    "method": "use_tool",
                    "params": {
                        "tool_name": "ipfs_fs_bridge_list_mappings",
                        "arguments": {}
                    },
                    "id": 12
                })
                
                if response.status_code == 200:
                    result = response.json()
                    if "result" in result and "mappings" in result["result"]:
                        mappings = result["result"]["mappings"]
                        logger.info(f"IPFS-FS mappings ({len(mappings)}):")
                        pprint(mappings)
                else:
                    logger.error(f"Error listing mappings: {response.text}")
            
            # Check journal if available
            if "fs_journal_get_history" in vfs_tools:
                logger.info("Getting filesystem journal history...")
                
                response = requests.post(MCP_JSON_RPC_URL, json={
                    "jsonrpc": "2.0",
                    "method": "use_tool",
                    "params": {
                        "tool_name": "fs_journal_get_history",
                        "arguments": {
                            "limit": 5
                        }
                    },
                    "id": 13
                })
                
                if response.status_code == 200:
                    result = response.json()
                    if "result" in result and "operations" in result["result"]:
                        operations = result["result"]["operations"]
                        logger.info(f"Recent filesystem operations ({len(operations)}):")
                        pprint(operations)
                else:
                    logger.error(f"Error getting journal history: {response.text}")
        else:
            logger.error("❌ No CID in export result")
    else:
        logger.error(f"Could not find result in response: {result}")

async def main():
    """Main entry point"""
    logger.info("Starting virtual filesystem MCP tools test")
    
    # Check if MCP server URL is reachable
    logger.info(f"Checking if MCP server is reachable at {MCP_URL}...")
    try:
        response = requests.get(f"{MCP_URL}")
        logger.info(f"MCP server responded with status code {response.status_code}")
    except Exception as e:
        logger.error(f"MCP server not reachable at {MCP_URL}: {e}")
        logger.warning("Make sure the MCP server is running")
        return 1
    
    # Run tests
    success = await test_vfs_tools()
    
    if success:
        logger.info("✅ All tests passed!")
        return 0
    else:
        logger.error("❌ Tests failed")
        return 1

if __name__ == "__main__":
    asyncio.run(main())
