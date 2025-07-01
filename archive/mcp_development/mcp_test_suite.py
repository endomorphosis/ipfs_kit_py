#!/usr/bin/env python3
"""
Comprehensive MCP Server Test Suite

This script provides comprehensive testing for the MCP server and all its tools.
It checks that all components are working correctly and provides detailed diagnostics.
"""

import os
import sys
import json
import time
import logging
import argparse
import subprocess
import socket
import traceback
import requests
from pathlib import Path
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("mcp_test_suite.log", mode="w"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("mcp-test-suite")

# Configuration
SERVER_SCRIPT = "final_mcp_server.py"
FIXED_RUNNER = "fixed_runner.py"
PORT = 9998
HOST = "0.0.0.0"
LOG_FILE = "mcp_test_suite_server.log"
PID_FILE = "mcp_test_suite.pid"
TEST_RESULTS_DIR = "test_results"
CATEGORIES = ["ipfs_tools", "vfs_tools", "fs_journal_tools", "multi_backend_tools"]

# Create test results directory
Path(TEST_RESULTS_DIR).mkdir(exist_ok=True)

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="MCP Server Test Suite")
    parser.add_argument("--skip-server-start", action="store_true", help="Skip starting the server (assume it's already running)")
    parser.add_argument("--port", type=int, default=PORT, help=f"Port to use (default: {PORT})")
    parser.add_argument("--host", type=str, default=HOST, help=f"Host to bind to (default: {HOST})")
    parser.add_argument("--use-fixed-runner", action="store_true", help="Use the fixed runner script instead of direct server script")
    parser.add_argument("--test-categories", nargs="+", choices=CATEGORIES + ["all"], default=["all"], 
                      help="Tool categories to test")
    return parser.parse_args()

def kill_existing_servers():
    """Kill any existing MCP server processes."""
    logger.info("Checking for existing servers...")
    
    # Try to kill processes by PID file
    pid_files = [
        "final_mcp_server.pid",
        "enhanced_mcp_server.pid",
        "mcp_server.pid",
        "direct_mcp_server.pid",
        "unified_mcp_server.pid",
        "fixed_final_mcp_server.pid",
        "mcp_test_suite.pid"
    ]
    
    for pid_file in pid_files:
        if os.path.exists(pid_file):
            try:
                with open(pid_file, 'r') as f:
                    pid = int(f.read().strip())
                    try:
                        os.kill(pid, 0)  # Check if process exists
                        logger.info(f"Found process {pid} from {pid_file}, terminating")
                        os.kill(pid, 15)  # SIGTERM
                        time.sleep(1)
                        try:
                            os.kill(pid, 0)
                            logger.info(f"Process {pid} didn't terminate, force killing")
                            os.kill(pid, 9)  # SIGKILL
                        except OSError:
                            pass
                    except OSError:
                        pass
                os.remove(pid_file)
            except:
                pass
    
    # Try to kill by process name
    try:
        pids = subprocess.check_output(["pgrep", "-f", "python.*mcp_server"], text=True).strip().split('\n')
        for pid in pids:
            if pid:
                try:
                    pid = int(pid)
                    logger.info(f"Killing process {pid} found by pgrep")
                    os.kill(pid, 15)
                    time.sleep(1)
                    try:
                        os.kill(pid, 0)
                        os.kill(pid, 9)
                    except OSError:
                        pass
                except:
                    pass
    except:
        pass

def check_port_availability(host, port):
    """Check if the port is available."""
    logger.info(f"Checking if port {port} is available...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((host, port))
        logger.info(f"Port {port} is available ✓")
        s.close()
        return True
    except socket.error as e:
        logger.error(f"Port {port} is not available: {e} ✗")
        return False

def start_server(args):
    """Start the MCP server."""
    logger.info("Starting MCP server...")
    
    if args.use_fixed_runner:
        # Use fixed runner script
        cmd = [sys.executable, FIXED_RUNNER]
        logger.info(f"Using fixed runner script: {' '.join(cmd)}")
        
        # We let the fixed runner handle everything
        try:
            subprocess.run(cmd, check=True)
            logger.info("Fixed runner executed successfully")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Fixed runner failed with exit code {e.returncode}")
            return False
    else:
        # Start server directly
        cmd = [
            sys.executable,
            SERVER_SCRIPT,
            "--host", args.host,
            "--port", str(args.port),
            "--debug"
        ]
        
        logger.info(f"Starting server with command: {' '.join(cmd)}")
        
        if os.path.exists(LOG_FILE):
            os.remove(LOG_FILE)
        
        try:
            with open(LOG_FILE, "w") as log_file:
                process = subprocess.Popen(
                    cmd,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    start_new_session=True
                )
            
            with open(PID_FILE, "w") as f:
                f.write(str(process.pid))
            
            logger.info(f"Server started with PID {process.pid}")
            
            # Wait for server to initialize
            if wait_for_server_ready(args.host, args.port):
                return True
            else:
                logger.error("Server failed to initialize properly")
                kill_server(process.pid)
                return False
        except Exception as e:
            logger.error(f"Error starting server: {e}")
            logger.error(traceback.format_exc())
            return False

def wait_for_server_ready(host, port, max_wait=60):
    """Wait for the server to be ready to accept requests."""
    logger.info(f"Waiting for server to be ready (up to {max_wait} seconds)...")
    health_url = f"http://{host}:{port}/health"
    
    start_time = time.time()
    while time.time() - start_time < max_wait:
        try:
            response = requests.get(health_url, timeout=2)
            if response.status_code == 200:
                logger.info("Server is ready! ✓")
                return True
        except:
            pass
        
        # Check if process is still running
        if os.path.exists(PID_FILE):
            with open(PID_FILE, "r") as f:
                pid = int(f.read().strip())
                try:
                    os.kill(pid, 0)  # Just checking if process exists
                except OSError:
                    logger.error("Server process died unexpectedly")
                    return False
        
        # Log every 5 seconds
        if int((time.time() - start_time) / 5) * 5 == int(time.time() - start_time):
            elapsed = int(time.time() - start_time)
            logger.info(f"Still waiting for server... ({elapsed}/{max_wait} seconds)")
            
            # Log recent output
            try:
                with open(LOG_FILE, "r") as f:
                    lines = f.readlines()[-10:]
                    logger.info("Recent server output:")
                    for line in lines:
                        logger.info(f"  {line.strip()}")
            except:
                pass
        
        time.sleep(1)
    
    logger.error(f"Server didn't become ready within {max_wait} seconds ✗")
    return False

def kill_server(pid=None):
    """Kill the MCP server."""
    if pid is None and os.path.exists(PID_FILE):
        with open(PID_FILE, "r") as f:
            pid = int(f.read().strip())
    
    if pid:
        logger.info(f"Killing server process (PID {pid})...")
        try:
            os.kill(pid, 15)  # SIGTERM
            time.sleep(2)
            try:
                os.kill(pid, 0)
                logger.info("Server didn't terminate gracefully, force killing...")
                os.kill(pid, 9)  # SIGKILL
            except OSError:
                pass
        except OSError as e:
            logger.info(f"Process already gone: {e}")
    
    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)

def get_server_info():
    """Get information about the running server."""
    logger.info("Getting server information...")
    
    try:
        response = requests.get(f"http://{HOST}:{PORT}/health", timeout=5)
        if response.status_code == 200:
            info = response.json()
            logger.info(f"Server info: {json.dumps(info, indent=2)}")
            return info
        else:
            logger.error(f"Health check failed with status code {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Error getting server info: {e}")
        return None

def get_registered_tools():
    """Get the list of tools registered with the server."""
    logger.info("Getting registered tools...")
    
    try:
        # Try to call list_tools method
        payload = {
            "jsonrpc": "2.0",
            "method": "list_tools",
            "params": {},
            "id": 1
        }
        
        response = requests.post(
            f"http://{HOST}:{PORT}/jsonrpc",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        
        if response.status_code == 200:
            result = response.json()
            if "result" in result:
                tools = result["result"]
                logger.info(f"Found {len(tools)} registered tools")
                
                # Save tools to file
                tools_file = os.path.join(TEST_RESULTS_DIR, "registered_tools.json")
                with open(tools_file, "w") as f:
                    json.dump(tools, f, indent=2)
                
                # Group tools by category
                tools_by_category = {}
                for tool in tools:
                    category = tool.get("category", "uncategorized")
                    if category not in tools_by_category:
                        tools_by_category[category] = []
                    tools_by_category[category].append(tool)
                
                logger.info("Tools by category:")
                for category, category_tools in tools_by_category.items():
                    logger.info(f"  - {category}: {len(category_tools)} tools")
                
                return tools
            else:
                logger.error("Unexpected response format from list_tools")
                return []
        else:
            logger.error(f"list_tools request failed with status {response.status_code}")
            return []
    except Exception as e:
        logger.error(f"Error getting registered tools: {e}")
        return []

def test_tool(tool_name, params=None):
    """Test a specific tool."""
    if params is None:
        params = {}
    
    logger.info(f"Testing tool '{tool_name}' with params {params}...")
    
    try:
        payload = {
            "jsonrpc": "2.0",
            "method": tool_name,
            "params": params,
            "id": int(time.time())
        }
        
        response = requests.post(
            f"http://{HOST}:{PORT}/jsonrpc",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if "error" in result:
                logger.error(f"Tool '{tool_name}' returned an error: {result['error']}")
                return False, result
            elif "result" in result:
                # For some tools, success is embedded in the result
                if isinstance(result["result"], dict) and "success" in result["result"]:
                    success = result["result"]["success"]
                    if not success:
                        logger.error(f"Tool '{tool_name}' execution failed: {result['result'].get('error', 'Unknown error')}")
                    else:
                        logger.info(f"Tool '{tool_name}' executed successfully")
                else:
                    success = True
                    logger.info(f"Tool '{tool_name}' executed successfully")
                
                return success, result
            else:
                logger.error(f"Unexpected response format for tool '{tool_name}'")
                return False, result
        else:
            logger.error(f"Tool '{tool_name}' request failed with status {response.status_code}")
            return False, {"error": f"HTTP {response.status_code}"}
    except Exception as e:
        logger.error(f"Error testing tool '{tool_name}': {e}")
        return False, {"error": str(e)}

def test_tools_by_category(tools, categories):
    """Test tools by category."""
    logger.info("Testing tools by category...")
    
    results = []
    
    # If "all" is specified, test all categories
    if "all" in categories:
        categories = [tool.get("category", "uncategorized") for tool in tools]
        categories = list(set(categories))
    
    logger.info(f"Testing categories: {', '.join(categories)}")
    
    # Standard test parameters for some tools
    test_params = {
        "ipfs_add": {"content": "Hello from MCP test suite!"},
        "ipfs_cat": {"path": "QmY7Yh4UquoXHLPFo2XbhXkhBvFoPwmQUSa92pxnxjQuPU"},
        "ipfs_files_ls": {"path": "/"},
        "ipfs_files_mkdir": {"path": "/test_" + datetime.now().strftime("%Y%m%d_%H%M%S")},
        "ipfs_files_write": {"path": "/test.txt", "content": "Test content from MCP suite"},
        "vfs_read": {"path": "/readme.txt"},
        "vfs_ls": {"path": "/"},
        "fs_journal_list_tracked": {},
        "mbfs_list_backends": {}
    }
    
    # Test each tool
    for tool in tools:
        name = tool.get("name", "unknown")
        category = tool.get("category", "uncategorized")
        
        if category in categories or name in test_params:
            params = test_params.get(name, {})
            success, response = test_tool(name, params)
            
            results.append({
                "name": name,
                "category": category,
                "success": success,
                "params": params,
                "response": response
            })
    
    # Save results to file
    results_file = os.path.join(TEST_RESULTS_DIR, "tool_test_results.json")
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)
    
    # Calculate statistics
    total = len(results)
    successful = sum(1 for r in results if r["success"])
    failed = total - successful
    
    logger.info(f"Tool testing complete: {successful}/{total} successful, {failed} failed")
    
    # Generate markdown report
    report_file = os.path.join(TEST_RESULTS_DIR, "tool_test_report.md")
    with open(report_file, "w") as f:
        f.write(f"# MCP Tool Test Report\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"## Summary\n\n")
        f.write(f"- Total tools tested: {total}\n")
        f.write(f"- Successful: {successful}\n")
        f.write(f"- Failed: {failed}\n\n")
        
        f.write(f"## Results by Category\n\n")
        by_category = {}
        for r in results:
            category = r["category"]
            if category not in by_category:
                by_category[category] = {"total": 0, "success": 0, "fail": 0}
            by_category[category]["total"] += 1
            if r["success"]:
                by_category[category]["success"] += 1
            else:
                by_category[category]["fail"] += 1
        
        for category, stats in by_category.items():
            f.write(f"### {category}\n\n")
            f.write(f"- Total: {stats['total']}\n")
            f.write(f"- Successful: {stats['success']}\n")
            f.write(f"- Failed: {stats['fail']}\n\n")
        
        f.write(f"## Detailed Results\n\n")
        f.write("| Tool | Category | Status | Parameters | Response |\n")
        f.write("|------|----------|--------|------------|----------|\n")
        
        for r in results:
            name = r["name"]
            category = r["category"]
            status = "✅ PASS" if r["success"] else "❌ FAIL"
            params = json.dumps(r["params"])
            response = json.dumps(r["response"])
            if len(response) > 100:
                response = response[:100] + "..."
            
            f.write(f"| {name} | {category} | {status} | `{params}` | `{response}` |\n")
    
    logger.info(f"Test report written to {report_file}")
    
    return results, successful, failed

def generate_summary_report(server_info, tools, test_results):
    """Generate a summary report."""
    logger.info("Generating summary report...")
    
    summary_file = os.path.join(TEST_RESULTS_DIR, "summary_report.md")
    
    with open(summary_file, "w") as f:
        f.write("# MCP Server Test Summary Report\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("## Server Information\n\n")
        if server_info:
            for key, value in server_info.items():
                f.write(f"- **{key}**: {value}\n")
        else:
            f.write("*Failed to retrieve server information*\n")
        
        f.write("\n## Registered Tools\n\n")
        if tools:
            # Group by category
            tools_by_category = {}
            for tool in tools:
                category = tool.get("category", "uncategorized")
                if category not in tools_by_category:
                    tools_by_category[category] = []
                tools_by_category[category].append(tool)
            
            f.write(f"Total: {len(tools)} tools across {len(tools_by_category)} categories\n\n")
            
            for category, category_tools in tools_by_category.items():
                f.write(f"### {category} ({len(category_tools)} tools)\n\n")
                f.write("| Tool | Description |\n")
                f.write("|------|-------------|\n")
                
                for tool in category_tools:
                    name = tool.get("name", "unknown")
                    description = tool.get("description", "").replace("\n", " ")
                    f.write(f"| `{name}` | {description} |\n")
                
                f.write("\n")
        else:
            f.write("*No tools were registered*\n\n")
        
        f.write("## Test Results\n\n")
        if test_results:
            successful_count = sum(1 for r in test_results if r["success"])
            failed_count = len(test_results) - successful_count
            success_rate = successful_count / len(test_results) * 100 if test_results else 0
            
            f.write(f"- **Total tests**: {len(test_results)}\n")
            f.write(f"- **Successful**: {successful_count} ({success_rate:.1f}%)\n")
            f.write(f"- **Failed**: {failed_count}\n\n")
            
            if failed_count > 0:
                f.write("### Failed Tests\n\n")
                f.write("| Tool | Category | Error |\n")
                f.write("|------|----------|-------|\n")
                
                for r in test_results:
                    if not r["success"]:
                        name = r["name"]
                        category = r["category"]
                        error = "Unknown error"
                        if "error" in r["response"]:
                            error = r["response"]["error"]
                        elif "result" in r["response"] and isinstance(r["response"]["result"], dict) and "error" in r["response"]["result"]:
                            error = r["response"]["result"]["error"]
                        
                        f.write(f"| `{name}` | {category} | {error} |\n")
        else:
            f.write("*No tests were performed*\n")
    
    logger.info(f"Summary report written to {summary_file}")
    return summary_file

def main():
    """Main function."""
    logger.info("Starting MCP Server Test Suite...")
    
    args = parse_args()
    
    try:
        # If not skipping server start
        if not args.skip_server_start:
            # Kill any existing servers
            kill_existing_servers()
            
            # Check if port is available
            if not check_port_availability(args.host, args.port):
                logger.error("Port is not available, aborting")
                return 1
            
            # Start server
            if not start_server(args):
                logger.error("Failed to start server")
                return 1
        else:
            logger.info("Skipping server start - assuming server is already running")
        
        # Get server information
        server_info = get_server_info()
        if not server_info:
            logger.error("Failed to get server information")
            if not args.skip_server_start:
                kill_server()
            return 1
        
        # Get registered tools
        tools = get_registered_tools()
        if not tools:
            logger.error("Failed to get registered tools")
            if not args.skip_server_start:
                kill_server()
            return 1
        
        # Test tools by category
        test_results, successful, failed = test_tools_by_category(tools, args.test_categories)
        
        # Generate summary report
        summary_file = generate_summary_report(server_info, tools, test_results)
        
        # Clean up
        if not args.skip_server_start:
            kill_server()
        
        logger.info(f"Test suite complete: {successful}/{len(test_results)} tests passed, {failed} failed")
        logger.info(f"Summary report: {summary_file}")
        
        # Return success if all tests passed
        return 0 if failed == 0 else 1
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        logger.error(traceback.format_exc())
        # Try to clean up
        if not args.skip_server_start:
            kill_server()
        return 1

if __name__ == "__main__":
    sys.exit(main())
