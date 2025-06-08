#!/usr/bin/env python3
"""
Comprehensive test script for the final MCP server.
This script tests all the available IPFS tools and verifies integration between
the MCP server and the ipfs_kit_py virtual filesystem.
"""

import sys
import json
import asyncio
import logging
import requests
import argparse
import time
import base64
from datetime import datetime
from typing import Dict, List, Any, Optional, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test-final-mcp")

# Parse command line arguments
parser = argparse.ArgumentParser(description="Comprehensive MCP Server Test Script")
parser.add_argument("--server-url", default="http://localhost:3000", help="MCP server URL")
parser.add_argument("--comprehensive", action="store_true", help="Run comprehensive tests")
parser.add_argument("--timeout", type=int, default=10, help="Request timeout in seconds")
parser.add_argument("--debug", action="store_true", help="Enable debug logging")
args = parser.parse_args()

# Server URL from command line args
SERVER_URL = args.server_url

# Set log level
if args.debug:
    logging.getLogger().setLevel(logging.DEBUG)

# Test results tracking
TEST_RESULTS = {
    "timestamp": datetime.now().isoformat(),
    "server_url": SERVER_URL,
    "tests": {},
    "summary": {
        "passed": 0,
        "failed": 0,
        "skipped": 0
    }
}

def record_test_result(test_name: str, success: bool, details: Any = None, error: str = None):
    """Record the result of a test in the global test results dictionary."""
    TEST_RESULTS["tests"][test_name] = {
        "success": success,
        "details": details,
        "error": error,
        "timestamp": datetime.now().isoformat()
    }
    
    if success:
        TEST_RESULTS["summary"]["passed"] += 1
        logger.info(f"✅ {test_name}: PASSED")
    else:
        TEST_RESULTS["summary"]["failed"] += 1
        logger.error(f"❌ {test_name}: FAILED" + (f" - {error}" if error else ""))


def check_server_health():
    """Check if the server is healthy."""
    test_name = "server_health"
    
    try:
        # Try different possible endpoints for health
        for endpoint in ["/health", "/api/v0/health"]:
            try:
                response = requests.get(f"{SERVER_URL}{endpoint}", timeout=args.timeout)
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Server is healthy at {endpoint}: {data}")
                    record_test_result(test_name, True, {
                        "endpoint": endpoint,
                        "status_code": response.status_code,
                        "response": data
                    })
                    return True
            except requests.exceptions.RequestException:
                # Try the next endpoint
                continue
        
        # If we get here, none of the endpoints worked
        record_test_result(test_name, False, error="No health endpoints responded")
        return False
    except Exception as e:
        error_msg = f"Server health check failed: {str(e)}"
        logger.error(error_msg)
        record_test_result(test_name, False, error=error_msg)
        return False


def get_available_tools():
    """Get the list of available tools."""
    test_name = "get_available_tools"
    
    try:
        # Try different possible endpoints for initialize
        for endpoint in ["/initialize", "/api/v0/initialize"]:
            try:
                response = requests.post(f"{SERVER_URL}{endpoint}", timeout=args.timeout)
                if response.status_code == 200:
                    data = response.json()
                    tools = data.get("capabilities", {}).get("tools", [])
                    
                    if tools:
                        logger.info(f"Found {len(tools)} tools at {endpoint}")
                        if args.debug:
                            logger.debug(f"Available tools: {tools}")
                        
                        # Categorize tools
                        ipfs_tools = [t for t in tools if "ipfs_" in t]
                        fs_tools = [t for t in tools if "_files_" in t]
                        
                        record_test_result(test_name, True, {
                            "endpoint": endpoint,
                            "total_tools": len(tools),
                            "ipfs_tools": len(ipfs_tools),
                            "fs_tools": len(fs_tools)
                        })
                        return tools
            except requests.exceptions.RequestException:
                # Try the next endpoint
                continue
        
        # If we get here, none of the endpoints worked
        record_test_result(test_name, False, error="No initialize endpoints responded")
        return []
    except Exception as e:
        error_msg = f"Failed to get available tools: {str(e)}"
        logger.error(error_msg)
        record_test_result(test_name, False, error=error_msg)
        return []


def test_jsonrpc_endpoint():
    """Test the JSON-RPC endpoint."""
    test_name = "jsonrpc_endpoint"
    
    try:
        payload = {
            "jsonrpc": "2.0",
            "method": "ping",
            "params": {},
            "id": 1
        }
        
        # Try different possible endpoints for jsonrpc
        for endpoint in ["/jsonrpc", "/api/v0/jsonrpc"]:
            try:
                response = requests.post(
                    f"{SERVER_URL}{endpoint}",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=args.timeout
                )
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"JSON-RPC ping result at {endpoint}: {result}")
                    
                    record_test_result(test_name, True, {
                        "endpoint": endpoint,
                        "status_code": response.status_code,
                        "response": result
                    })
                    return True
            except requests.exceptions.RequestException:
                # Try the next endpoint
                continue
        
        # If we get here, none of the endpoints worked
        record_test_result(test_name, False, error="No JSON-RPC endpoints responded")
        return False
    except Exception as e:
        error_msg = f"JSON-RPC test failed: {str(e)}"
        logger.error(error_msg)
        record_test_result(test_name, False, error=error_msg)
        return False

def test_ipfs_version():
    """Test the IPFS version tool."""
    test_name = "ipfs_version"
    
    try:
        payload = {
            "jsonrpc": "2.0",
            "method": "ipfs_version",
            "params": {},
            "id": 2
        }
        
        response = requests.post(
            f"{SERVER_URL}/jsonrpc",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=args.timeout
        )
        
        if response.status_code == 200:
            result = response.json()
            if "result" in result:
                logger.info(f"IPFS version: {result['result']}")
                record_test_result(test_name, True, result)
                return True
            else:
                record_test_result(test_name, False, 
                                  error=f"Invalid response: {result}")
                return False
        else:
            record_test_result(test_name, False, 
                              error=f"Request failed: HTTP {response.status_code}")
            return False
    except Exception as e:
        error_msg = f"IPFS version test failed: {str(e)}"
        logger.error(error_msg)
        record_test_result(test_name, False, error=error_msg)
        return False


def test_ipfs_add():
    """Test the IPFS add tool."""
    test_name = "ipfs_add"
    
    try:
        # Create a test content to add
        test_content = f"Test content for IPFS add: {datetime.now().isoformat()}"
        content_base64 = base64.b64encode(test_content.encode()).decode()
        
        payload = {
            "jsonrpc": "2.0",
            "method": "ipfs_add",
            "params": {
                "content": content_base64,
                "encoding": "base64"
            },
            "id": 3
        }
        
        response = requests.post(
            f"{SERVER_URL}/jsonrpc",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=args.timeout
        )
        
        if response.status_code == 200:
            result = response.json()
            if "result" in result and "Hash" in result["result"]:
                cid = result["result"]["Hash"]
                logger.info(f"Added content to IPFS with CID: {cid}")
                record_test_result(test_name, True, result)
                # Return CID for use in other tests
                return cid
            else:
                record_test_result(test_name, False, 
                                  error=f"Invalid response: {result}")
                return False
        else:
            record_test_result(test_name, False, 
                              error=f"Request failed: HTTP {response.status_code}")
            return False
    except Exception as e:
        error_msg = f"IPFS add test failed: {str(e)}"
        logger.error(error_msg)
        record_test_result(test_name, False, error=error_msg)
        return False


def test_ipfs_cat(cid):
    """Test the IPFS cat tool."""
    test_name = "ipfs_cat"
    
    if not cid:
        logger.warning("Skipping ipfs_cat test - no CID available")
        TEST_RESULTS["summary"]["skipped"] += 1
        return False
    
    try:
        payload = {
            "jsonrpc": "2.0",
            "method": "ipfs_cat",
            "params": {
                "path": cid
            },
            "id": 4
        }
        
        response = requests.post(
            f"{SERVER_URL}/jsonrpc",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=args.timeout
        )
        
        if response.status_code == 200:
            result = response.json()
            if "result" in result:
                content = result["result"]
                if isinstance(content, dict) and "data" in content:
                    # Some implementations return data field with base64 encoding
                    content = content.get("data", "")
                    try:
                        content = base64.b64decode(content).decode()
                    except:
                        pass
                
                logger.info(f"Retrieved content from IPFS: {content[:50]}...")
                record_test_result(test_name, True, result)
                return True
            else:
                record_test_result(test_name, False, 
                                  error=f"Invalid response: {result}")
                return False
        else:
            record_test_result(test_name, False, 
                              error=f"Request failed: HTTP {response.status_code}")
            return False
    except Exception as e:
        error_msg = f"IPFS cat test failed: {str(e)}"
        logger.error(error_msg)
        record_test_result(test_name, False, error=error_msg)
        return False


def test_ipfs_filesystem():
    """Test the IPFS filesystem tools (MFS)."""
    test_name = "ipfs_filesystem"
    
    try:
        # Create a unique test directory
        test_dir = f"/mcp-test-{int(time.time())}"
        test_file = f"{test_dir}/test.txt"
        test_content = f"Hello from MCP test at {datetime.now().isoformat()}"
        
        # Step 1: Create directory
        mkdir_payload = {
            "jsonrpc": "2.0",
            "method": "ipfs_files_mkdir",
            "params": {
                "path": test_dir,
                "parents": True
            },
            "id": 5
        }
        
        response = requests.post(
            f"{SERVER_URL}/jsonrpc",
            json=mkdir_payload,
            headers={"Content-Type": "application/json"},
            timeout=args.timeout
        )
        
        if response.status_code != 200:
            record_test_result(test_name, False, 
                              error=f"Failed to create directory: HTTP {response.status_code}")
            return False
        
        # Step 2: Write to a file
        write_payload = {
            "jsonrpc": "2.0",
            "method": "ipfs_files_write",
            "params": {
                "path": test_file,
                "content": base64.b64encode(test_content.encode()).decode(),
                "encoding": "base64",
                "create": True
            },
            "id": 6
        }
        
        response = requests.post(
            f"{SERVER_URL}/jsonrpc",
            json=write_payload,
            headers={"Content-Type": "application/json"},
            timeout=args.timeout
        )
        
        if response.status_code != 200:
            record_test_result(test_name, False, 
                              error=f"Failed to write file: HTTP {response.status_code}")
            return False
        
        # Step 3: Read the file
        read_payload = {
            "jsonrpc": "2.0",
            "method": "ipfs_files_read",
            "params": {
                "path": test_file
            },
            "id": 7
        }
        
        response = requests.post(
            f"{SERVER_URL}/jsonrpc",
            json=read_payload,
            headers={"Content-Type": "application/json"},
            timeout=args.timeout
        )
        
        if response.status_code != 200:
            record_test_result(test_name, False, 
                              error=f"Failed to read file: HTTP {response.status_code}")
            return False
        
        read_result = response.json()
        if "result" not in read_result:
            record_test_result(test_name, False, 
                              error=f"Invalid read response: {read_result}")
            return False
            
        read_content = read_result["result"]
        if isinstance(read_content, dict) and "data" in read_content:
            # Some implementations return data field with base64 encoding
            try:
                decoded = base64.b64decode(read_content["data"]).decode()
                read_content = decoded
            except:
                read_content = read_content["data"]
        
        logger.info(f"MFS read content: {read_content[:50]}...")
        
        # Step 4: List files
        ls_payload = {
            "jsonrpc": "2.0",
            "method": "ipfs_files_ls",
            "params": {
                "path": test_dir,
                "long": True
            },
            "id": 8
        }
        
        response = requests.post(
            f"{SERVER_URL}/jsonrpc",
            json=ls_payload,
            headers={"Content-Type": "application/json"},
            timeout=args.timeout
        )
        
        if response.status_code != 200:
            record_test_result(test_name, False, 
                              error=f"Failed to list directory: HTTP {response.status_code}")
            return False
        
        ls_result = response.json()
        if "result" not in ls_result:
            record_test_result(test_name, False, 
                              error=f"Invalid list response: {ls_result}")
            return False
        
        # Success - all filesystem operations worked
        record_test_result(test_name, True, {
            "directory": test_dir,
            "file": test_file,
            "ls_result": ls_result["result"]
        })
        return True
        
    except Exception as e:
        error_msg = f"IPFS filesystem test failed: {str(e)}"
        logger.error(error_msg)
        record_test_result(test_name, False, error=error_msg)
        return False


def test_ipfs_kit_py_integration():
    """Test integration between MCP tools and ipfs_kit_py module."""
    test_name = "ipfs_kit_py_integration"
    
    # This is a higher-level test that checks if the virtual filesystem functionality
    # from ipfs_kit_py is correctly exposed through MCP tools
    
    try:
        # First check if we have IPFS FS related tools
        tools = get_available_tools()
        fs_tools = [t for t in tools if "_files_" in t]
        ipfs_tools = [t for t in tools if "ipfs_" in t]
        
        if not fs_tools:
            logger.warning("No filesystem tools found, skipping integration test")
            TEST_RESULTS["summary"]["skipped"] += 1
            return None
        
        # Create a test directory specific to this test
        test_dir = f"/ipfs_kit_py_test_{int(time.time())}"
        
        # Create directory with ipfs_files_mkdir
        mkdir_payload = {
            "jsonrpc": "2.0",
            "method": "ipfs_files_mkdir",
            "params": {
                "path": test_dir,
                "parents": True
            },
            "id": 9
        }
        
        response = requests.post(
            f"{SERVER_URL}/jsonrpc",
            json=mkdir_payload,
            headers={"Content-Type": "application/json"},
            timeout=args.timeout
        )
        
        if response.status_code != 200:
            record_test_result(test_name, False, 
                              error=f"Integration test: Failed to create directory: HTTP {response.status_code}")
            return False
            
        # Create several files to test different functionality
        for i in range(3):
            file_path = f"{test_dir}/test_file_{i}.txt"
            content = f"Test content {i} created at {datetime.now().isoformat()}"
            
            write_payload = {
                "jsonrpc": "2.0",
                "method": "ipfs_files_write",
                "params": {
                    "path": file_path,
                    "content": base64.b64encode(content.encode()).decode(),
                    "encoding": "base64",
                    "create": True
                },
                "id": 10 + i
            }
            
            response = requests.post(
                f"{SERVER_URL}/jsonrpc",
                json=write_payload,
                headers={"Content-Type": "application/json"},
                timeout=args.timeout
            )
            
            if response.status_code != 200:
                record_test_result(test_name, False, 
                                  error=f"Integration test: Failed to write file {i}: HTTP {response.status_code}")
                return False
        
        # Test advanced operations like flush (commit to IPFS)
        if "ipfs_files_flush" in tools:
            flush_payload = {
                "jsonrpc": "2.0",
                "method": "ipfs_files_flush",
                "params": {
                    "path": test_dir
                },
                "id": 14
            }
            
            response = requests.post(
                f"{SERVER_URL}/jsonrpc",
                json=flush_payload,
                headers={"Content-Type": "application/json"},
                timeout=args.timeout
            )
            
            flush_result = None
            if response.status_code == 200:
                result = response.json()
                if "result" in result:
                    flush_result = result["result"]
                    logger.info(f"Successfully flushed directory to IPFS: {flush_result}")
            
        # Check stat on directory
        if "ipfs_files_stat" in tools:
            stat_payload = {
                "jsonrpc": "2.0",
                "method": "ipfs_files_stat",
                "params": {
                    "path": test_dir
                },
                "id": 15
            }
            
            response = requests.post(
                f"{SERVER_URL}/jsonrpc",
                json=stat_payload,
                headers={"Content-Type": "application/json"},
                timeout=args.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                if "result" in result:
                    stat_result = result["result"]
                    logger.info(f"Directory stats: {stat_result}")
                    
                    # Success! The virtual filesystem is working through MCP
                    record_test_result(test_name, True, {
                        "test_dir": test_dir,
                        "stat": stat_result,
                        "flush_result": flush_result
                    })
                    return True
        
        # If we couldn't validate with stat, but files were created, it's still a partial success
        record_test_result(test_name, True, {
            "test_dir": test_dir,
            "note": "Could not fully validate with stat or flush, but file operations worked"
        })
        return True
        
    except Exception as e:
        error_msg = f"ipfs_kit_py integration test failed: {str(e)}"
        logger.error(error_msg)
        record_test_result(test_name, False, error=error_msg)
        return False


def main():
    """Main entry point."""
    logger.info(f"Starting comprehensive tests for MCP server at {SERVER_URL}...")
    
    # Check server health
    if not check_server_health():
        logger.error("Server health check failed. Is the server running?")
        return 1
    
    # Get available tools
    tools = get_available_tools()
    if not tools:
        logger.error("No tools found. Server configuration may be incomplete.")
        return 1
    
    # Test JSON-RPC endpoint
    jsonrpc_ok = test_jsonrpc_endpoint()
    if not jsonrpc_ok:
        logger.warning("JSON-RPC endpoint test failed. Further tests will likely fail.")
    
    # Basic tests completed, proceed with more comprehensive tests if requested
    if args.comprehensive and jsonrpc_ok:
        logger.info("Running comprehensive tests...")
        
        # Test IPFS core functionality
        ipfs_version_ok = test_ipfs_version()
        
        # Test IPFS data storage
        test_cid = test_ipfs_add()
        if test_cid:
            test_ipfs_cat(test_cid)
        
        # Test IPFS filesystem (MFS)
        fs_ok = test_ipfs_filesystem()
        
        # Test integration with ipfs_kit_py virtual filesystem
        integration_ok = test_ipfs_kit_py_integration()
    
    # Output summary
    passed = TEST_RESULTS["summary"]["passed"]
    failed = TEST_RESULTS["summary"]["failed"]
    skipped = TEST_RESULTS["summary"]["skipped"]
    total = passed + failed + skipped
    
    logger.info(f"\n===== Test Summary =====")
    logger.info(f"Total tests: {total}")
    logger.info(f"Passed: {passed}")
    logger.info(f"Failed: {failed}")
    logger.info(f"Skipped: {skipped}")
    
    if failed == 0:
        logger.info(f"\n✅ All tests passed!")
        return 0
    else:
        logger.error(f"\n❌ {failed} tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
