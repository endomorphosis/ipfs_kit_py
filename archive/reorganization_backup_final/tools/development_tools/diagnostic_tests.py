#!/usr/bin/env python3
"""
MCP Server Diagnostic Tests

This module contains targeted tests to diagnose specific components of the MCP server
and identify underlying causes of errors.

Usage:
    python diagnostic_tests.py [--server FILE] [--port PORT] [--test TEST_NAME]
"""

import argparse
import json
import logging
import os
import requests
import sys
import time
import uuid
from typing import Dict, Any, List, Tuple, Optional, Union, Callable

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("diagnostic_tests")

# Constants
DEFAULT_SERVER_FILE = "final_mcp_server.py"
DEFAULT_PORT = 9996
TEST_TIMEOUT = 5  # seconds
TEMP_DIR = "diagnostic_temp"
RESULTS_DIR = "diagnostic_results"

# Test results storage
test_results = {
    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    "server_file": DEFAULT_SERVER_FILE,
    "port": DEFAULT_PORT,
    "tests": {},
    "errors": [],
    "summary": {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "skipped": 0,
    }
}

# Ensure directories exist
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

# Helper function for JSON-RPC calls
def call_jsonrpc(method: str, params: Dict = None, port: int = DEFAULT_PORT) -> Dict[str, Any]:
    """Make a JSON-RPC call to the server."""
    if params is None:
        params = {}
    
    try:
        response = requests.post(
            f"http://localhost:{port}/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": method,
                "params": params
            },
            timeout=TEST_TIMEOUT
        )
        
        if response.status_code != 200:
            return {
                "error": f"HTTP error: {response.status_code}",
                "details": response.text
            }
        
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": f"Request exception: {str(e)}"}
    except json.JSONDecodeError as e:
        return {"error": f"JSON decode error: {str(e)}", "details": response.text}

# Helper function for health check
def check_health(port: int = DEFAULT_PORT) -> Dict[str, Any]:
    """Check server health."""
    try:
        response = requests.get(f"http://localhost:{port}/health", timeout=TEST_TIMEOUT)
        
        if response.status_code != 200:
            return {
                "status": "error",
                "error": f"HTTP error: {response.status_code}",
                "details": response.text
            }
        
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"status": "error", "error": f"Request exception: {str(e)}"}
    except json.JSONDecodeError as e:
        return {"status": "error", "error": f"JSON decode error: {str(e)}"}

# Start/stop server functions
def start_server(server_file: str, port: int) -> Tuple[bool, str]:
    """Start the MCP server."""
    logger.info(f"Starting server: {server_file} on port {port}")
    
    # Check if server is already running
    try:
        health_check = check_health(port)
        if health_check.get("status") == "healthy":
            return True, "Server already running"
    except Exception:
        pass
    
    # Start server
    try:
        import subprocess
        
        # Use a temporary log file
        log_file = os.path.join(TEMP_DIR, f"{os.path.basename(server_file)}.log")
        
        # Start server process
        process = subprocess.Popen(
            ["python3", server_file, "--port", str(port)],
            stdout=open(log_file, "w"),
            stderr=subprocess.STDOUT
        )
        
        # Save PID
        pid_file = os.path.join(TEMP_DIR, f"{os.path.basename(server_file)}.pid")
        with open(pid_file, "w") as f:
            f.write(str(process.pid))
        
        # Wait for server to start
        max_attempts = 10
        for i in range(max_attempts):
            time.sleep(1)
            try:
                health_check = check_health(port)
                if health_check.get("status") == "healthy":
                    return True, f"Server started with PID: {process.pid}"
            except Exception as e:
                if i == max_attempts - 1:
                    # Read log file for error details
                    try:
                        with open(log_file, "r") as f:
                            log_content = f.read()
                            error_details = log_content[-1000:] if len(log_content) > 1000 else log_content
                    except Exception:
                        error_details = "Unable to read log file"
                    
                    return False, f"Failed to start server: {str(e)}\nLog details: {error_details}"
        
        return False, "Timeout waiting for server to start"
    except Exception as e:
        return False, f"Error starting server: {str(e)}"

def stop_server(server_file: str) -> Tuple[bool, str]:
    """Stop the MCP server."""
    pid_file = os.path.join(TEMP_DIR, f"{os.path.basename(server_file)}.pid")
    if not os.path.exists(pid_file):
        return True, "Server not running"
    
    try:
        with open(pid_file, "r") as f:
            pid = int(f.read().strip())
        
        import signal, os
        try:
            os.kill(pid, signal.SIGTERM)
            time.sleep(2)
            
            # Check if still running
            try:
                os.kill(pid, 0)
                # Still running, force kill
                os.kill(pid, signal.SIGKILL)
            except OSError:
                # Process is gone
                pass
            
            # Remove PID file
            os.unlink(pid_file)
            return True, f"Server with PID {pid} stopped"
        except OSError as e:
            if e.errno == 3:  # No such process
                os.unlink(pid_file)
                return True, f"Server with PID {pid} was not running"
            return False, f"Error stopping server with PID {pid}: {str(e)}"
    except Exception as e:
        return False, f"Error stopping server: {str(e)}"

# Test decorator
def diagnostic_test(test_fn):
    """Decorator for test functions."""
    def wrapper(*args, **kwargs):
        test_name = test_fn.__name__
        logger.info(f"Running test: {test_name}")
        
        start_time = time.time()
        try:
            result = test_fn(*args, **kwargs)
            end_time = time.time()
            
            if result[0]:  # test passed
                logger.info(f"✅ Test {test_name} PASSED ({end_time - start_time:.2f}s)")
                test_results["tests"][test_name] = {
                    "status": "pass",
                    "message": result[1],
                    "duration": end_time - start_time,
                    "details": result[2] if len(result) > 2 else None
                }
                test_results["summary"]["passed"] += 1
            else:  # test failed
                logger.error(f"❌ Test {test_name} FAILED ({end_time - start_time:.2f}s): {result[1]}")
                test_results["tests"][test_name] = {
                    "status": "fail",
                    "message": result[1],
                    "duration": end_time - start_time,
                    "details": result[2] if len(result) > 2 else None
                }
                test_results["summary"]["failed"] += 1
            
            test_results["summary"]["total"] += 1
            return result
        except Exception as e:
            end_time = time.time()
            logger.exception(f"❌ Test {test_name} ERROR ({end_time - start_time:.2f}s)")
            test_results["tests"][test_name] = {
                "status": "error",
                "message": str(e),
                "duration": end_time - start_time
            }
            test_results["errors"].append({
                "test": test_name,
                "error": str(e),
                "traceback": str(sys.exc_info()[2])
            })
            test_results["summary"]["failed"] += 1
            test_results["summary"]["total"] += 1
            return False, str(e)
    return wrapper

# Define diagnostic tests

@diagnostic_test
def test_server_startup(server_file: str, port: int) -> Tuple[bool, str, Dict]:
    """Test server startup."""
    # Stop server if running
    stop_server(server_file)
    
    # Try to start server
    success, message = start_server(server_file, port)
    
    if not success:
        return False, f"Server startup failed: {message}", {"error": message}
    
    # Check health endpoint
    health_data = check_health(port)
    
    if health_data.get("status") != "healthy":
        return False, "Server started but health check failed", health_data
    
    # Check server info
    server_info = call_jsonrpc("server_info", port=port)
    
    if "error" in server_info:
        return False, "Server info endpoint failed", server_info
    
    return True, "Server started successfully", {
        "health": health_data,
        "server_info": server_info
    }

@diagnostic_test
def test_basic_jsonrpc(port: int) -> Tuple[bool, str, Dict]:
    """Test basic JSON-RPC functionality."""
    # Test system.listMethods
    methods_result = call_jsonrpc("system.listMethods", port=port)
    
    if "error" in methods_result:
        return False, "system.listMethods failed", methods_result
    
    # Test ping
    ping_result = call_jsonrpc("ping", port=port)
    
    if "error" in ping_result:
        return False, "ping failed", ping_result
    
    return True, "Basic JSON-RPC functionality working", {
        "methods": methods_result,
        "ping": ping_result
    }

@diagnostic_test
def test_tool_schemas(port: int) -> Tuple[bool, str, Dict]:
    """Test tool schemas endpoint."""
    schemas_result = call_jsonrpc("get_tools_schema", port=port)
    
    if "error" in schemas_result:
        return False, "get_tools_schema failed", schemas_result
    
    # Check if we have valid schema data
    schemas = schemas_result.get("result", [])
    if not isinstance(schemas, list):
        return False, "Invalid schema format, expected list", schemas_result
    
    return True, f"Tool schemas endpoint working ({len(schemas)} schemas found)", {
        "schemas": schemas
    }

@diagnostic_test
def test_ipfs_tools(port: int) -> Tuple[bool, str, Dict]:
    """Test IPFS tools."""
    # Get version
    version_result = call_jsonrpc("ipfs_version", port=port)
    
    if "error" in version_result:
        return False, "ipfs_version failed", version_result
    
    # Test add and cat
    test_content = f"Test content {uuid.uuid4()}"
    add_result = call_jsonrpc("ipfs_add", {"content": test_content}, port=port)
    
    if "error" in add_result:
        return False, "ipfs_add failed", add_result
    
    # Extract CID
    if "result" in add_result:
        if isinstance(add_result["result"], dict):
            cid = add_result["result"].get("cid")
        else:
            cid = add_result["result"]
    else:
        return False, "Could not extract CID from ipfs_add result", add_result
    
    # Cat the content back
    cat_result = call_jsonrpc("ipfs_cat", {"cid": cid}, port=port)
    
    if "error" in cat_result:
        return False, "ipfs_cat failed", cat_result
    
    # Verify content
    if "result" in cat_result:
        if isinstance(cat_result["result"], dict):
            returned_content = cat_result["result"].get("content")
        else:
            returned_content = cat_result["result"]
    else:
        return False, "Could not extract content from ipfs_cat result", cat_result
    
    if returned_content != test_content:
        return False, "Content mismatch in ipfs_cat", {
            "original": test_content,
            "returned": returned_content
        }
    
    return True, "IPFS tools working correctly", {
        "version": version_result,
        "add": add_result,
        "cat": cat_result
    }

@diagnostic_test
def test_vfs_tools(port: int) -> Tuple[bool, str, Dict]:
    """Test VFS tools."""
    # Create test directory
    test_dir = f"/test-dir-{uuid.uuid4().hex[:8]}"
    mkdir_result = call_jsonrpc("vfs_mkdir", {"path": test_dir}, port=port)
    
    if "error" in mkdir_result:
        return False, "vfs_mkdir failed", mkdir_result
    
    # List directory
    ls_result = call_jsonrpc("vfs_ls", {"path": "/"}, port=port)
    
    if "error" in ls_result:
        return False, "vfs_ls failed", ls_result
    
    # Write a file
    test_file = f"{test_dir}/test-file.txt"
    test_content = f"Test content {uuid.uuid4()}"
    write_result = call_jsonrpc("vfs_write", {"path": test_file, "content": test_content}, port=port)
    
    if "error" in write_result:
        return False, "vfs_write failed", write_result
    
    # Read the file
    read_result = call_jsonrpc("vfs_read", {"path": test_file}, port=port)
    
    if "error" in read_result:
        return False, "vfs_read failed", read_result
    
    # Verify content
    if "result" in read_result:
        if isinstance(read_result["result"], dict):
            returned_content = read_result["result"].get("content")
        else:
            returned_content = read_result["result"]
    else:
        return False, "Could not extract content from vfs_read result", read_result
    
    if returned_content != test_content:
        return False, "Content mismatch in vfs_read", {
            "original": test_content,
            "returned": returned_content
        }
    
    # Clean up
    rm_result = call_jsonrpc("vfs_rm", {"path": test_file}, port=port)
    rmdir_result = call_jsonrpc("vfs_rmdir", {"path": test_dir}, port=port)
    
    return True, "VFS tools working correctly", {
        "mkdir": mkdir_result,
        "ls": ls_result,
        "write": write_result,
        "read": read_result,
        "rm": rm_result,
        "rmdir": rmdir_result
    }

@diagnostic_test
def test_ipfs_vfs_integration(port: int) -> Tuple[bool, str, Dict]:
    """Test IPFS and VFS integration."""
    # Add content to IPFS
    test_content = f"IPFS-VFS integration test content {uuid.uuid4()}"
    add_result = call_jsonrpc("ipfs_add", {"content": test_content}, port=port)
    
    if "error" in add_result:
        return False, "ipfs_add failed", add_result
    
    # Extract CID
    if "result" in add_result:
        if isinstance(add_result["result"], dict):
            cid = add_result["result"].get("cid")
        else:
            cid = add_result["result"]
    else:
        return False, "Could not extract CID from ipfs_add result", add_result
    
    # Create test directory in VFS
    test_dir = f"/ipfs-vfs-test-{int(time.time())}"
    mkdir_result = call_jsonrpc("vfs_mkdir", {"path": test_dir}, port=port)
    
    if "error" in mkdir_result:
        return False, "vfs_mkdir failed", mkdir_result
    
    # Write CID to a file in VFS
    test_file = f"{test_dir}/cid.txt"
    write_result = call_jsonrpc("vfs_write", {"path": test_file, "content": cid}, port=port)
    
    if "error" in write_result:
        return False, "vfs_write failed", write_result
    
    # Read file from VFS
    read_result = call_jsonrpc("vfs_read", {"path": test_file}, port=port)
    
    if "error" in read_result:
        return False, "vfs_read failed", read_result
    
    # Extract read CID
    if "result" in read_result:
        if isinstance(read_result["result"], dict):
            read_cid = read_result["result"].get("content")
        else:
            read_cid = read_result["result"]
    else:
        return False, "Could not extract CID from vfs_read result", read_result
    
    if read_cid != cid:
        return False, "CID mismatch", {
            "original": cid,
            "read": read_cid
        }
    
    # Verify IPFS content using the read CID
    verify_result = call_jsonrpc("ipfs_add", {"content": test_content}, port=port)
    
    if "error" in verify_result:
        return False, "ipfs_add verification failed", verify_result
    
    # Extract verification CID
    if "result" in verify_result:
        if isinstance(verify_result["result"], dict):
            verify_cid = verify_result["result"].get("cid")
        else:
            verify_cid = verify_result["result"]
    else:
        return False, "Could not extract verification CID", verify_result
    
    # Clean up
    rm_result = call_jsonrpc("vfs_rm", {"path": test_file}, port=port)
    rmdir_result = call_jsonrpc("vfs_rmdir", {"path": test_dir}, port=port)
    
    # Final verification
    if verify_cid != cid:
        return False, "Verification CID mismatch", {
            "original": cid,
            "verification": verify_cid
        }
    
    return True, "IPFS-VFS integration working correctly", {
        "cid": cid,
        "verification_cid": verify_cid
    }

@diagnostic_test
def test_error_handling(port: int) -> Tuple[bool, str, Dict]:
    """Test error handling in the server."""
    # Test missing parameter
    missing_param = call_jsonrpc("ipfs_cat", {}, port=port)
    
    if "error" not in missing_param:
        return False, "Missing parameter didn't cause an error", missing_param
    
    # Test non-existent method
    nonexistent = call_jsonrpc("non_existent_method", {}, port=port)
    
    if "error" not in nonexistent:
        return False, "Non-existent method didn't cause an error", nonexistent
    
    # Test invalid CID
    invalid_cid = call_jsonrpc("ipfs_cat", {"cid": "invalid-cid"}, port=port)
    
    if "error" not in invalid_cid:
        return False, "Invalid CID didn't cause an error", invalid_cid
    
    return True, "Error handling working correctly", {
        "missing_param": missing_param,
        "nonexistent": nonexistent,
        "invalid_cid": invalid_cid
    }

@diagnostic_test
def test_handlers_existence(port: int) -> Tuple[bool, str, Dict]:
    """Test if all handlers exist for registered tools."""
    # Get list of tools
    tools_result = call_jsonrpc("system.listMethods", port=port)
    
    if "error" in tools_result:
        return False, "system.listMethods failed", tools_result
    
    # Extract tools list
    if "result" in tools_result:
        tools = tools_result["result"]
    else:
        return False, "Could not extract tools list", tools_result
    
    # Test each tool with minimal params
    missing_handlers = []
    for tool in tools:
        # Skip system methods and core tools that we've already tested
        if tool.startswith("system.") or tool in ["ping", "health", "list_tools", "server_info"]:
            continue
        
        # Call the tool with minimal params
        result = call_jsonrpc(tool, {}, port=port)
        
        # Check if error indicates missing handler
        if "error" in result:
            error_msg = str(result.get("error", ""))
            if "not defined" in error_msg or "no attribute" in error_msg:
                missing_handlers.append(tool)
    
    if missing_handlers:
        return False, f"Missing handlers for {len(missing_handlers)} tools", {
            "missing_handlers": missing_handlers
        }
    
    return True, "All tools have handlers", {
        "tools_count": len(tools)
    }

# Main function
def run_diagnostics(args):
    """Run diagnostic tests."""
    server_file = args.server
    port = args.port
    test_name = args.test
    
    # Update test results
    test_results["server_file"] = server_file
    test_results["port"] = port
    
    logger.info(f"Running diagnostics on {server_file} (port: {port})")
    
    # Start server if needed
    if not args.no_server:
        start_server(server_file, port)
    
    # Get all test functions
    test_functions = [
        (name, func) for name, func in globals().items()
        if name.startswith("test_") and callable(func) and hasattr(func, "__name__")
    ]
    
    try:
        # Run the selected test or all tests
        if test_name:
            for name, func in test_functions:
                if name == test_name:
                    func(server_file=server_file, port=port)
                    break
            else:
                logger.error(f"Test '{test_name}' not found")
                return
        else:
            # First, run server startup test
            test_server_startup(server_file=server_file, port=port)
            
            # Then run all other tests
            for name, func in test_functions:
                if name == "test_server_startup":
                    continue
                
                # Determine function signature
                import inspect
                params = inspect.signature(func).parameters
                
                if "server_file" in params and "port" in params:
                    func(server_file=server_file, port=port)
                elif "server_file" in params:
                    func(server_file=server_file)
                elif "port" in params:
                    func(port=port)
                else:
                    func()
    finally:
        # Save test results
        results_file = os.path.join(RESULTS_DIR, f"diagnostic_results_{time.strftime('%Y%m%d_%H%M%S')}.json")
        with open(results_file, "w") as f:
            json.dump(test_results, f, indent=2)
        
        # Log summary
        logger.info("=" * 50)
        logger.info("DIAGNOSTIC TEST RESULTS")
        logger.info("=" * 50)
        logger.info(f"Total tests: {test_results['summary']['total']}")
        logger.info(f"Passed: {test_results['summary']['passed']}")
        logger.info(f"Failed: {test_results['summary']['failed']}")
        logger.info(f"Skipped: {test_results['summary']['skipped']}")
        logger.info("=" * 50)
        logger.info(f"Results saved to: {results_file}")
        
        # Stop server if we started it
        if not args.no_server and not args.keep_server:
            stop_server(server_file)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MCP Server Diagnostic Tests")
    parser.add_argument("--server", default=DEFAULT_SERVER_FILE, help="MCP server file to test")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to use for testing")
    parser.add_argument("--test", help="Run a specific test by name")
    parser.add_argument("--no-server", action="store_true", help="Don't start/stop the server (assume it's already running)")
    parser.add_argument("--keep-server", action="store_true", help="Don't stop the server after tests")
    
    args = parser.parse_args()
    
    run_diagnostics(args)
