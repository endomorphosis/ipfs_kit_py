#!/usr/bin/env python3
"""
Enhanced MCP Server Diagnostics

This script provides comprehensive diagnostics for the MCP server and IPFS tools
to help identify and fix issues with the setup.
"""

import os
import sys
import json
import time
import signal
import logging
import importlib
import traceback
import subprocess
import socket
import requests
from pathlib import Path
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    forma    # Save report to file
    timestamp = int(time.time())
    json_report_path = os.path.join(DIAGNOSTICS_DIR, f"diagnostic_report_{timestamp}.json")
    with open(json_report_path, "w") as f:
        json.dump(report, f, indent=2)
    
    # Generate markdown reportsctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("enhanced_diagnostics.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("enhanced-diagnostics")

# Configuration
SERVER_PY = "final_mcp_server.py"
PORT = 9998
HOST = "0.0.0.0"
LOG_FILE = "final_mcp_server.log"
PID_FILE = "final_mcp_server.pid"
DIAGNOSTICS_DIR = "diagnostic_results"
JSON_RPC_ENDPOINT = f"http://localhost:{PORT}/jsonrpc"
HEALTH_ENDPOINT = f"http://localhost:{PORT}/health"

# Create diagnostics directory
Path(DIAGNOSTICS_DIR).mkdir(exist_ok=True)

def check_system_info():
    """Check system information and Python environment."""
    logger.info("---------- System Information ----------")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Python executable: {sys.executable}")
    logger.info(f"Current directory: {os.getcwd()}")
    logger.info(f"System path: {sys.path}")

    # Check for critical packages
    packages = [
        "fastapi", "uvicorn", "jsonrpcserver", 
        "requests", "pytest", "starlette"
    ]
    for package in packages:
        try:
            pkg = importlib.import_module(package)
            version = getattr(pkg, "__version__", "unknown")
            logger.info(f"{package}: {version} ✓")
        except ImportError:
            logger.error(f"{package}: Not installed ✗")

def kill_existing_servers():
    """Kill any existing MCP server processes."""
    logger.info("---------- Checking for Existing Servers ----------")
    
    pid_files = [
        "final_mcp_server.pid",
        "enhanced_mcp_server.pid",
        "mcp_server.pid",
        "direct_mcp_server.pid",
        "unified_mcp_server.pid",
        "fixed_final_mcp_server.pid"
    ]
    
    for pid_file in pid_files:
        if os.path.exists(pid_file):
            try:
                with open(pid_file, 'r') as f:
                    pid = int(f.read().strip())
                    logger.info(f"Found PID file {pid_file} with PID {pid}")
                    try:
                        os.kill(pid, 0)  # Check if process exists
                        logger.info(f"Process {pid} is running, attempting to terminate")
                        os.kill(pid, signal.SIGTERM)
                        time.sleep(2)
                        try:
                            os.kill(pid, 0)  # Check if process still exists
                            logger.info(f"Process {pid} did not terminate, force killing")
                            os.kill(pid, signal.SIGKILL)
                        except OSError:
                            logger.info(f"Process {pid} terminated successfully")
                    except OSError:
                        logger.info(f"No such process {pid}, removing stale PID file")
                os.remove(pid_file)
            except Exception as e:
                logger.error(f"Error handling PID file {pid_file}: {e}")

    # Additional check for any python processes with mcp_server in the name
    try:
        pids = subprocess.check_output(["pgrep", "-f", "python.*mcp_server"], text=True).strip().split("\n")
        for pid in pids:
            if pid:
                try:
                    pid = int(pid)
                    logger.info(f"Found Python MCP server process with PID {pid}, killing")
                    os.kill(pid, signal.SIGTERM)
                    time.sleep(1)
                    try:
                        os.kill(pid, 0)
                        logger.info(f"Process {pid} did not terminate, force killing")
                        os.kill(pid, signal.SIGKILL)
                    except OSError:
                        pass
                except:
                    pass
    except subprocess.CalledProcessError:
        pass  # No processes found

def check_port_availability():
    """Check if the port is available."""
    logger.info(f"---------- Checking Port {PORT} Availability ----------")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((HOST, PORT))
        logger.info(f"Port {PORT} is available ✓")
        s.close()
        return True
    except socket.error as e:
        logger.error(f"Port {PORT} is not available: {e} ✗")
        return False

def test_import_modules():
    """Test importing key modules to identify any issues."""
    logger.info("---------- Testing Module Imports ----------")
    
    modules = [
        ("unified_ipfs_tools", "IPFS Tools Module"),
        ("final_mcp_server", "MCP Server Module"),
        ("fs_journal_tools", "FS Journal Tools"),
        ("ipfs_mcp_fs_integration", "IPFS-FS Bridge"),
        ("mcp_vfs_config", "VFS Config"),
        ("multi_backend_fs_integration", "Multi-Backend FS")
    ]
    
    import_results = {}
    
    for module_name, description in modules:
        logger.info(f"Testing import of {module_name} ({description})...")
        try:
            # Use subprocess to prevent hanging in the current process
            cmd = [sys.executable, "-c", f"import {module_name}; print('{module_name} imported successfully')"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                logger.info(f"{module_name}: ✓ Import successful")
                import_results[module_name] = True
            else:
                logger.error(f"{module_name}: ✗ Import failed: {result.stderr.strip()}")
                import_results[module_name] = False
        except subprocess.TimeoutExpired:
            logger.error(f"{module_name}: ✗ Import timed out (possibly hanging)")
            import_results[module_name] = False
        except Exception as e:
            logger.error(f"{module_name}: ✗ Error testing import: {e}")
            import_results[module_name] = False
    
    return import_results

def start_test_server():
    """Start the server for testing with diagnostic options."""
    logger.info("---------- Starting Test Server ----------")
    
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)
    
    # Prepare command
    cmd = [
        sys.executable, 
        SERVER_PY, 
        "--host", HOST, 
        "--port", str(PORT), 
        "--debug"
    ]
    
    logger.info(f"Running command: {' '.join(cmd)}")
    
    try:
        # Start the server in a subprocess
        with open(LOG_FILE, "w") as log_file:
            process = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True  # This creates a new session for the process
            )
        
        # Check if the process started
        if process.poll() is None:
            logger.info(f"Server process started with PID {process.pid}")
            
            # Write PID to file
            with open(PID_FILE, "w") as f:
                f.write(str(process.pid))
            
            # Wait for server to initialize
            logger.info("Waiting for server to initialize...")
            for i in range(30):  # Wait up to 30 seconds
                time.sleep(1)
                
                # Check if the process is still running
                if process.poll() is not None:
                    logger.error(f"Server process exited with code {process.returncode}")
                    logger.error("Last 20 lines of log file:")
                    output = subprocess.check_output(["tail", "-n", "20", LOG_FILE], text=True)
                    for line in output.splitlines():
                        logger.error(f"  {line}")
                    return None
                
                # Check if server is responding to health checks
                try:
                    response = requests.get(HEALTH_ENDPOINT, timeout=1)
                    if response.status_code == 200:
                        logger.info("Server is up and responding to health checks!")
                        return process
                    else:
                        logger.info(f"Health check status code: {response.status_code} (waiting for 200)")
                except:
                    if i % 5 == 0:
                        logger.info(f"Still waiting for server to start ({i}/30 seconds)")
            
            logger.error("Server failed to respond to health checks within timeout")
            logger.error("Last 20 lines of log file:")
            output = subprocess.check_output(["tail", "-n", "20", LOG_FILE], text=True)
            for line in output.splitlines():
                logger.error(f"  {line}")
            return process  # Return process even though health check failed
        else:
            logger.error(f"Failed to start server process (exit code: {process.returncode})")
            logger.error("Log file contents:")
            with open(LOG_FILE, "r") as f:
                logger.error(f.read())
            return None
    except Exception as e:
        logger.error(f"Error starting server: {e}")
        logger.error(traceback.format_exc())
        return None

def test_jsonrpc_endpoint(process):
    """Test the JSON-RPC endpoint."""
    if not process:
        logger.error("Cannot test JSON-RPC - no server process provided")
        return False
    
    logger.info("---------- Testing JSON-RPC Endpoint ----------")
    
    # Test ping method
    try:
        payload = {
            "jsonrpc": "2.0",
            "method": "ping",
            "params": {},
            "id": int(time.time())
        }
        
        logger.info(f"Sending ping request to {JSON_RPC_ENDPOINT}")
        response = requests.post(
            JSON_RPC_ENDPOINT,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        
        logger.info(f"Response status code: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            logger.info(f"Response: {json.dumps(result, indent=2)}")
            if "result" in result and result["result"] == "pong":
                logger.info("Ping test successful! ✓")
                return True
            else:
                logger.error("Ping test failed - unexpected response ✗")
                return False
        else:
            logger.error("Ping test failed - non-200 status code ✗")
            return False
    except Exception as e:
        logger.error(f"Error testing JSON-RPC endpoint: {e}")
        return False

def check_registered_tools():
    """Check what tools are registered with the server."""
    logger.info("---------- Checking Registered Tools ----------")
    
    try:
        # Query the health endpoint to get number of registered tools
        response = requests.get(HEALTH_ENDPOINT, timeout=5)
        if response.status_code == 200:
            health_data = response.json()
            logger.info(f"Health data: {json.dumps(health_data, indent=2)}")
            
            # Query list_tools method if available
            try:
                payload = {
                    "jsonrpc": "2.0",
                    "method": "list_tools",
                    "params": {},
                    "id": int(time.time())
                }
                
                response = requests.post(
                    JSON_RPC_ENDPOINT,
                    json=payload, 
                    headers={"Content-Type": "application/json"},
                    timeout=5
                )
                
                if response.status_code == 200:
                    tools_data = response.json()
                    if "result" in tools_data:
                        tools = tools_data["result"]
                        logger.info(f"Found {len(tools)} registered tools:")
                        
                        # Group tools by category
                        tools_by_category = {}
                        for tool in tools:
                            category = tool.get("category", "uncategorized")
                            if category not in tools_by_category:
                                tools_by_category[category] = []
                            tools_by_category[category].append(tool)
                        
                        # Log tools by category
                        for category, category_tools in tools_by_category.items():
                            logger.info(f"Category '{category}': {len(category_tools)} tools")
                            for tool in category_tools:
                                logger.info(f"  - {tool['name']}: {tool.get('description', 'No description')}")
                        
                        # Save tools to file
                        with open(os.path.join(DIAGNOSTICS_DIR, "registered_tools.json"), "w") as f:
                            json.dump(tools, f, indent=2)
                        
                        return tools
                    else:
                        logger.warning("list_tools returned no result")
                else:
                    logger.warning(f"list_tools failed with status code {response.status_code}")
            except Exception as e:
                logger.warning(f"Error querying list_tools: {e}")
            
            return health_data.get("tools", [])
        else:
            logger.error(f"Health endpoint returned status code {response.status_code}")
            return []
    except Exception as e:
        logger.error(f"Error checking registered tools: {e}")
        return []

def test_tool_execution():
    """Test execution of basic tools."""
    logger.info("---------- Testing Tool Execution ----------")
    
    # List of tools to test with sample parameters
    test_tools = [
        {
            "name": "ping",
            "params": {},
            "expected_response_contains": "pong"
        },
        {
            "name": "ipfs_version",
            "params": {},
            "expected_response_contains": "version"
        },
        {
            "name": "ipfs_add",
            "params": {"content": "Hello IPFS!"},
            "expected_response_contains": "hash"
        },
        {
            "name": "ipfs_add",
            "params": {"content": "Test with filename", "filename": "test.txt"},
            "expected_response_contains": "hash",
            "description": "ipfs_add with filename parameter test"
        },
        {
            "name": "ipfs_add",
            "params": {"content": "Test with only_hash", "only_hash": True},
            "expected_response_contains": "hash",
            "description": "ipfs_add with only_hash parameter test"
        },
        {
            "name": "ipfs_files_ls",
            "params": {"path": "/"},
            "expected_response_contains": "entries"
        }
    ]
    
    results = []
    
    for test in test_tools:
        tool_name = test["name"]
        params = test["params"]
        expected = test["expected_response_contains"]
        
        logger.info(f"Testing tool: {tool_name}")
        try:
            description = test.get("description", f"Testing {tool_name}")
            logger.info(f"Test: {description}")
            
            payload = {
                "jsonrpc": "2.0",
                "method": tool_name,
                "params": params,
                "id": int(time.time())
            }
            
            response = requests.post(
                JSON_RPC_ENDPOINT,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=5
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Response: {json.dumps(result, indent=2)}")
                
                if "result" in result and expected in str(result):
                    logger.info(f"Tool {tool_name} execution successful ✓")
                    success = True
                else:
                    logger.error(f"Tool {tool_name} execution failed - unexpected response ✗")
                    success = False
            else:
                logger.error(f"Tool {tool_name} execution failed - status code {response.status_code} ✗")
                success = False
                
            results.append({
                "tool": tool_name,
                "description": description,
                "params": params,
                "success": success,
                "response": response.text if response.status_code == 200 else str(response)
            })
            
        except Exception as e:
            logger.error(f"Error testing tool {tool_name}: {e}")
            results.append({
                "tool": tool_name,
                "success": False,
                "error": str(e)
            })
    
    # Save results to file
    with open(os.path.join(DIAGNOSTICS_DIR, "tool_execution_results.json"), "w") as f:
        json.dump(results, f, indent=2)
    
    return results

def generate_diagnostic_report(import_results, tools, tool_execution_results):
    """Generate a comprehensive diagnostic report."""
    logger.info("---------- Generating Diagnostic Report ----------")
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "system_info": {
            "python_version": sys.version,
            "executable": sys.executable,
            "platform": sys.platform
        },
        "import_tests": import_results,
        "registered_tools": tools,
        "tool_execution": tool_execution_results
    }
    
    # Save report to JSON
    report_path = os.path.join(DIAGNOSTICS_DIR, "diagnostic_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    
    # Generate markdown report
    markdown = f"""# MCP Server Diagnostic Report

Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## System Information
- Python Version: {sys.version.splitlines()[0]}
- Python Executable: {sys.executable}
- Platform: {sys.platform}

## Module Import Tests
"""
    
    for module, success in import_results.items():
        status = "✅ Passed" if success else "❌ Failed"
        markdown += f"- {module}: {status}\n"
    
    markdown += "\n## Registered Tools\n"
    if tools:
        if isinstance(tools, list) and len(tools) > 0 and isinstance(tools[0], dict):
            # Group tools by category
            tools_by_category = {}
            for tool in tools:
                category = tool.get("category", "uncategorized")
                if category not in tools_by_category:
                    tools_by_category[category] = []
                tools_by_category[category].append(tool)
            
            for category, category_tools in tools_by_category.items():
                markdown += f"\n### Category: {category}\n"
                markdown += f"- Number of tools: {len(category_tools)}\n"
                markdown += "| Tool | Description |\n"
                markdown += "|------|-------------|\n"
                for tool in category_tools:
                    name = tool.get("name", "Unknown")
                    desc = tool.get("description", "").replace("\n", " ")
                    markdown += f"| `{name}` | {desc} |\n"
        else:
            markdown += f"- Total registered tools: {len(tools)}\n"
    else:
        markdown += "- No tools were registered\n"
    
    markdown += "\n## Tool Execution Tests\n"
    if tool_execution_results:
        markdown += "| Tool | Description | Parameters | Status | Response |\n"
        markdown += "|------|-------------|------------|--------|----------|\n"
        for result in tool_execution_results:
            tool = result.get("tool", "Unknown")
            description = result.get("description", "")
            params = json.dumps(result.get("params", {}))
            if len(params) > 50:
                params = params[:50] + "..."
            success = result.get("success", False)
            status = "✅ Passed" if success else "❌ Failed"
            response = result.get("response", "")
            if isinstance(response, str) and len(response) > 100:
                response = response[:100] + "..."
            markdown += f"| `{tool}` | {description} | `{params}` | {status} | `{response}` |\n"
    else:
        markdown += "- No tool execution tests were performed\n"
    
    # Save markdown report with timestamp
    timestamp = int(time.time())
    md_path = os.path.join(DIAGNOSTICS_DIR, f"diagnostic_report_{timestamp}.md")
    with open(md_path, "w") as f:
        f.write(markdown)
    
    logger.info(f"Diagnostic report saved to {report_path} and {md_path}")
    return report_path, md_path

def print_summary_report(import_results, tools, tool_execution_results, report_paths):
    """
    Print a summary report of all diagnostics to the console.
    
    Args:
        import_results: Results of module import tests
        tools: List of registered tools
        tool_execution_results: Results of tool execution tests
        report_paths: Paths to generated report files
    """
    logger.info("\n\n" + "="*80)
    logger.info(" MCP SERVER DIAGNOSTICS SUMMARY ")
    logger.info("="*80)
    
    # Calculate success rates
    import_success = sum(1 for result in import_results.values() if result) 
    import_total = len(import_results)
    import_rate = f"{import_success}/{import_total} ({import_success/import_total*100:.1f}%)"
    
    tool_count = len(tools) if isinstance(tools, list) else 0
    
    execution_success = sum(1 for result in tool_execution_results if result.get("success", False))
    execution_total = len(tool_execution_results)
    execution_rate = f"{execution_success}/{execution_total} ({execution_success/execution_total*100:.1f}%)" if execution_total > 0 else "N/A"
    
    # Print summary
    logger.info(f"Module Imports: {import_rate} successful")
    logger.info(f"Registered Tools: {tool_count} tools found")
    logger.info(f"Tool Execution: {execution_rate} successful")
    
    # List detailed results
    logger.info("\nModule Import Details:")
    for module, result in import_results.items():
        status = "✅" if result else "❌"
        logger.info(f"  {status} {module}")
    
    # Tool execution results
    if tool_execution_results:
        logger.info("\nTool Execution Details:")
        for result in tool_execution_results:
            tool = result.get("tool", "Unknown")
            status = "✅" if result.get("success", False) else "❌"
            logger.info(f"  {status} {tool}")
    
    # Report paths
    if report_paths:
        logger.info("\nGenerated Reports:")
        json_path, md_path = report_paths
        logger.info(f"  JSON Report: {json_path}")
        logger.info(f"  Markdown Report: {md_path}")
    
    # Overall assessment
    if (import_success == import_total and 
        tool_count > 0 and 
        (execution_total == 0 or execution_success == execution_total)):
        logger.info("\n✅ OVERALL STATUS: HEALTHY")
    else:
        issues = []
        if import_success < import_total:
            issues.append(f"{import_total - import_success} module import issues")
        if tool_count == 0:
            issues.append("no tools registered")
        if execution_total > 0 and execution_success < execution_total:
            issues.append(f"{execution_total - execution_success} tool execution failures")
        
        logger.info(f"\n❌ OVERALL STATUS: ISSUES DETECTED ({', '.join(issues)})")
    
    logger.info("="*80)

def cleanup(process):
    """Clean up resources."""
    logger.info("---------- Cleaning Up ----------")
    
    if process and process.poll() is None:
        try:
            process.terminate()
            time.sleep(2)
            if process.poll() is None:
                process.kill()
                logger.info("Server process forcefully killed")
            else:
                logger.info("Server process terminated gracefully")
        except Exception as e:
            logger.error(f"Error terminating process: {e}")
    
    if os.path.exists(PID_FILE):
        try:
            os.remove(PID_FILE)
            logger.info(f"Removed PID file: {PID_FILE}")
        except Exception as e:
            logger.error(f"Error removing PID file: {e}")

def main():
    """Main function."""
    logger.info("================== Starting Enhanced MCP Server Diagnostics ==================")
    
    try:
        # Check system information
        check_system_info()
        
        # Kill any existing servers
        kill_existing_servers()
        
        # Check port availability
        if not check_port_availability():
            logger.error(f"Port {PORT} is not available, cannot continue with tests")
            return 1
        
        # Test importing modules
        import_results = test_import_modules()
        if not import_results.get("unified_ipfs_tools", False):
            logger.error("Failed to import unified_ipfs_tools, which is critical for the server")
            logger.info("Attempting to continue with other tests...")
        
        # Start test server
        process = start_test_server()
        
        # Test JSON-RPC endpoint if server started
        jsonrpc_working = False
        if process:
            jsonrpc_working = test_jsonrpc_endpoint(process)
        
        # Check registered tools if JSON-RPC is working
        tools = []
        if jsonrpc_working:
            tools = check_registered_tools()
        
        # Test tool execution if JSON-RPC is working
        tool_execution_results = []
        if jsonrpc_working:
            tool_execution_results = test_tool_execution()
        
        # Generate diagnostic report
        report_paths = generate_diagnostic_report(import_results, tools, tool_execution_results)
        
        # Generate summary
        print_summary_report(import_results, tools, tool_execution_results, report_paths)
        
        # Cleanup
        cleanup(process)
        
        logger.info("================== Enhanced MCP Server Diagnostics Completed ==================")
        
        # Return success if all critical checks passed
        critical_checks_passed = (
            import_results.get("unified_ipfs_tools", False) and
            import_results.get("final_mcp_server", False) and
            jsonrpc_working and
            len(tools) > 0
        )
        
        if critical_checks_passed:
            logger.info("All critical checks passed successfully! ✓")
            return 0
        else:
            logger.error("Some critical checks failed. See diagnostic report for details. ✗")
            return 1
    except Exception as e:
        logger.error(f"Unhandled exception in diagnostics: {e}")
        logger.error(traceback.format_exc())
        return 1

if __name__ == "__main__":
    sys.exit(main())
