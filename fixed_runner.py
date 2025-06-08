#!/usr/bin/env python3
"""
Fixed MCP Server Runner

This script loads the final_mcp_server module dynamically to avoid
import hanging issues and starts the server with proper parameters.
"""

import os
import sys
import importlib.util
import subprocess
import logging
import signal
import time
import socket
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("fixed-runner")

def check_port_available(host, port):
    """Check if a port is available."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((host, port))
        s.close()
        return True
    except socket.error:
        return False

def kill_existing_servers():
    """Kill any existing MCP server processes."""
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
                    try:
                        os.kill(pid, signal.SIGTERM)
                        logger.info(f"Terminated process with PID {pid} from {pid_file}")
                    except OSError:
                        pass
                os.remove(pid_file)
            except:
                pass

def run_server_process(host="0.0.0.0", port=9998, debug=True):
    """Run the server as a subprocess to avoid import hanging."""
    server_script = "final_mcp_server.py"
    pid_file = "fixed_final_mcp_server.pid"
    log_file = "fixed_final_mcp_server.log"
    
    # Remove old log file
    if os.path.exists(log_file):
        os.remove(log_file)
    
    # Start server process
    cmd = [
        sys.executable,
        server_script,
        "--host", host,
        "--port", str(port),
    ]
    
    if debug:
        cmd.append("--debug")
    
    logger.info(f"Starting server with command: {' '.join(cmd)}")
    with open(log_file, "w") as f:
        process = subprocess.Popen(
            cmd,
            stdout=f,
            stderr=subprocess.STDOUT,
            start_new_session=True
        )
    
    # Write PID to file
    with open(pid_file, "w") as f:
        f.write(str(process.pid))
    
    logger.info(f"Server started with PID {process.pid}")
    return process, log_file

def wait_for_server(max_wait=60, check_interval=1):
    """Wait for server to be ready."""
    import requests
    
    logger.info(f"Waiting up to {max_wait} seconds for server to be ready...")
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        try:
            health_resp = requests.get("http://localhost:9998/health", timeout=1)
            if health_resp.status_code == 200:
                logger.info("Server is ready!")
                return True
            else:
                logger.info(f"Health check returned status {health_resp.status_code}, waiting...")
        except requests.RequestException:
            if int((time.time() - start_time) / 5) * 5 == int(time.time() - start_time):
                logger.info(f"Still waiting for server... ({int(time.time() - start_time)}/{max_wait} seconds)")
        
        time.sleep(check_interval)
    
    logger.error(f"Server didn't become ready within {max_wait} seconds")
    return False

def run_tests(mode="basic"):
    """Run tests against the server."""
    import json
    import requests
    
    logger.info("Running basic server tests...")
    tests = [
        {"name": "Health check", "request": {"method": "GET", "url": "http://localhost:9998/health"}},
        {
            "name": "Ping", 
            "request": {
                "method": "POST", 
                "url": "http://localhost:9998/jsonrpc",
                "json": {"jsonrpc": "2.0", "method": "ping", "params": {}, "id": 1}
            }
        },
        {
            "name": "ipfs_files_ls", 
            "request": {
                "method": "POST", 
                "url": "http://localhost:9998/jsonrpc",
                "json": {"jsonrpc": "2.0", "method": "ipfs_files_ls", "params": {"path": "/"}, "id": 2}
            }
        }
    ]
    
    results = []
    for test in tests:
        try:
            logger.info(f"Running test: {test['name']}")
            if test["request"]["method"] == "GET":
                resp = requests.get(test["request"]["url"], timeout=5)
            elif test["request"]["method"] == "POST":
                resp = requests.post(
                    test["request"]["url"],
                    json=test["request"].get("json", {}),
                    headers={"Content-Type": "application/json"},
                    timeout=5
                )
            
            status = "PASS" if resp.status_code == 200 else "FAIL"
            logger.info(f"  Status: {status} ({resp.status_code})")
            
            results.append({
                "name": test["name"],
                "status": status,
                "response": resp.json() if resp.status_code == 200 else None,
                "status_code": resp.status_code
            })
        except Exception as e:
            logger.error(f"  Error: {e}")
            results.append({
                "name": test["name"],
                "status": "ERROR",
                "error": str(e)
            })
    
    # Save results to file
    with open("test_results/basic_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    # Print summary
    logger.info("\nTest Summary:")
    for result in results:
        status_icon = "✅" if result["status"] == "PASS" else "❌"
        logger.info(f"{status_icon} {result['name']}: {result['status']}")
    
    # Return True if all tests passed
    return all(r["status"] == "PASS" for r in results)

def main():
    """Main function."""
    # Create test results directory if it doesn't exist
    os.makedirs("test_results", exist_ok=True)
    
    # Check if port is available
    if not check_port_available("0.0.0.0", 9998):
        # Try to kill existing servers
        kill_existing_servers()
        
        # Check again
        if not check_port_available("0.0.0.0", 9998):
            logger.error("Port 9998 is still in use. Please free up the port before continuing.")
            return 1
    
    # Start server
    process, log_file = run_server_process()
    
    try:
        # Wait for server to be ready
        if wait_for_server(max_wait=60):
            # Run tests
            tests_passed = run_tests()
            
            if tests_passed:
                logger.info("All tests passed! Server is working correctly.")
                return 0
            else:
                logger.error("Some tests failed. Check test_results/basic_test_results.json for details.")
                return 1
        else:
            logger.error("Server failed to start or respond to health checks.")
            logger.error("Last 20 lines of log file:")
            with open(log_file, "r") as f:
                lines = f.readlines()[-20:]
                for line in lines:
                    logger.error(line.strip())
            return 1
    finally:
        # Terminate server
        try:
            if process and process.poll() is None:
                logger.info("Terminating server...")
                process.terminate()
                time.sleep(2)
                if process.poll() is None:
                    logger.info("Server didn't terminate gracefully, force killing...")
                    process.kill()
        except:
            pass
        
        # Remove PID file
        pid_file = "fixed_final_mcp_server.pid"
        if os.path.exists(pid_file):
            os.remove(pid_file)

if __name__ == "__main__":
    sys.exit(main())
