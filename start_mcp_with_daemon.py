#!/usr/bin/env python3
"""
Script to start the MCP server with proper daemon integration.
This script will:
1. Use the existing IPFS daemon
2. Attempt to start IPFS Cluster if available
3. Attempt to start Lotus if available
4. Start a new MCP server instance configured to use these daemons
"""

import os
import sys
import time
import subprocess
import logging
import json
import signal
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_free_port(start_port=8000, max_attempts=100):
    """Find a free port starting from start_port."""
    import socket
    port = start_port
    while port < start_port + max_attempts:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.1)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            if result != 0:  # Port is available
                return port
        except:
            pass
        port += 1
    return start_port  # Fallback to original if all are taken

def check_ipfs_daemon():
    """Check if IPFS daemon is running and responsive."""
    try:
        result = subprocess.run(
            ["ipfs", "id", "--format=<id>"],
            check=False,
            capture_output=True,
            text=True
        )
        return result.returncode == 0 and result.stdout.strip() != ""
    except Exception as e:
        logger.error(f"Error checking IPFS daemon: {e}")
        return False

def check_ipfs_cluster():
    """Check if IPFS Cluster is running and responsive."""
    try:
        result = subprocess.run(
            ["ipfs-cluster-ctl", "id"],
            check=False,
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception:
        return False

def check_lotus_daemon():
    """Check if Lotus daemon is running and responsive."""
    try:
        result = subprocess.run(
            ["lotus", "net", "peers"],
            check=False,
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception:
        return False

def kill_process_by_cmdline(search_string):
    """Kill processes that match the given command line string."""
    try:
        # Find process ID
        ps_cmd = f"ps aux | grep '{search_string}' | grep -v grep | awk '{{print $2}}'"
        result = subprocess.run(ps_cmd, shell=True, capture_output=True, text=True)
        
        if not result.stdout.strip():
            logger.info(f"No processes found matching: {search_string}")
            return False
            
        # Kill processes
        killed = 0
        for pid in result.stdout.strip().split('\n'):
            if pid:
                try:
                    logger.info(f"Terminating process {pid}")
                    os.kill(int(pid), signal.SIGTERM)
                    killed += 1
                except Exception as e:
                    logger.error(f"Failed to kill process {pid}: {e}")
                    
        if killed > 0:
            logger.info(f"Killed {killed} processes matching: {search_string}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error killing processes: {e}")
        return False

def find_best_server_script():
    """Find the best MCP server script to run."""
    # Order of preference
    script_candidates = [
        "run_mcp_server_anyio.py",
        "run_mcp_server_fixed.py", 
        "run_mcp_server.py",
        "ipfs_kit_py/run_mcp_server_anyio.py",
        "ipfs_kit_py/run_mcp_server_fixed.py",
        "ipfs_kit_py/run_mcp_server.py"
    ]
    
    for script in script_candidates:
        if os.path.exists(script):
            return script
    
    return None

def start_mcp_server(port=None):
    """Start a new MCP server instance with proper daemon integration."""
    # Find a server script to run
    server_script = find_best_server_script()
    if not server_script:
        logger.error("Could not find an MCP server script to run")
        return False
    
    if port is None:
        port = get_free_port(8002)
    
    logger.info(f"Starting MCP server using {server_script} on port {port}")
    
    # Create a command that explicitly does NOT use --skip-daemon
    cmd = [
        "python",
        server_script,
        "--debug",
        "--port", str(port),
        "--host", "localhost"
    ]
    
    # Don't use isolation mode as it might create a new IPFS repo
    # instead of using the existing daemon
    
    # Start the server
    try:
        # Create a log file for server output
        log_file = open("mcp_daemon_server.log", "w")
        
        process = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=log_file,
            text=True,
            start_new_session=True  # Detach from parent process
        )
        
        # Check if process started
        if process.poll() is not None:
            logger.error("Failed to start MCP server process")
            return False
            
        # Give it a moment to start
        logger.info(f"Waiting for MCP server to start on port {port}...")
        
        # Check if the server is responding
        max_wait = 30  # seconds
        health_url = f"http://localhost:{port}/api/v0/mcp/health"
        
        for i in range(max_wait):
            try:
                # Check if the server is responding to health checks
                curl_cmd = ["curl", "-s", health_url]
                result = subprocess.run(curl_cmd, capture_output=True, text=True)
                
                if result.returncode == 0 and "success" in result.stdout:
                    # Server is running and healthy
                    logger.info(f"MCP server started successfully on port {port}")
                    
                    # Save PID to file for later reference
                    with open("mcp_daemon_server.pid", "w") as f:
                        f.write(str(process.pid))
                    
                    return {
                        "success": True,
                        "port": port,
                        "pid": process.pid,
                        "url": f"http://localhost:{port}/api/v0/mcp",
                        "docs_url": f"http://localhost:{port}/docs"
                    }
            except Exception as e:
                pass
            
            # Check if process is still running
            if process.poll() is not None:
                logger.error("MCP server process exited prematurely")
                return False
                
            # Wait before retrying
            time.sleep(1)
            
        # If we reach here, server didn't respond in time
        logger.error(f"Timeout waiting for MCP server to respond on port {port}")
        
        # Try to find out what happened by checking the log
        try:
            with open("mcp_daemon_server.log", "r") as f:
                log_content = f.read()
                logger.error(f"Last 500 chars of log: {log_content[-500:]}")
        except Exception as e:
            logger.error(f"Error reading log file: {e}")
            
        return False
    except Exception as e:
        logger.error(f"Error starting MCP server: {e}")
        return False

def check_daemon_status():
    """Check and report on the status of all daemons."""
    status = {
        "ipfs": check_ipfs_daemon(),
        "ipfs_cluster": check_ipfs_cluster(),
        "lotus": check_lotus_daemon()
    }
    
    # Log status
    logger.info("=== Daemon Status ===")
    for daemon, running in status.items():
        logger.info(f"{daemon}: {'Running' if running else 'Not running'}")
    logger.info("====================")
    
    return status

def try_to_use_mcp_api(port):
    """Try to use the MCP API to interact with IPFS."""
    try:
        # Try to add a small test string
        test_content = f"Test content {time.time()}"
        curl_cmd = [
            "curl", "-s", "-X", "POST", 
            "-H", "Content-Type: application/json", 
            "--data", f'{{"content": "{test_content}"}}',
            f"http://localhost:{port}/api/v0/mcp/ipfs/add/json"
        ]
        
        result = subprocess.run(curl_cmd, capture_output=True, text=True)
        
        if result.returncode == 0 and "success" in result.stdout:
            try:
                response = json.loads(result.stdout)
                if response.get("success") and response.get("cid"):
                    logger.info(f"Successfully added content to IPFS via MCP API: {response['cid']}")
                    return True
            except json.JSONDecodeError:
                pass
                
        logger.error(f"Failed to add content via MCP API: {result.stdout}")
        return False
    except Exception as e:
        logger.error(f"Error using MCP API: {e}")
        return False

def main():
    """Main function to start MCP server with daemon integration."""
    print("\n=== MCP Server with Daemon Integration ===\n")
    
    # Check if daemons are running
    daemon_status = check_daemon_status()
    
    # Ensure IPFS daemon is running
    if not daemon_status["ipfs"]:
        print("Error: IPFS daemon is not running!")
        print("Please start the IPFS daemon with: ipfs daemon")
        sys.exit(1)
    
    # Try to start a new MCP server
    print("\nStarting a new MCP server instance that will use the existing IPFS daemon...")
    result = start_mcp_server()
    
    if not result:
        print("\nFailed to start MCP server with daemon integration.")
        print("Please check the logs for more information.")
        sys.exit(1)
    
    # Verify MCP API works with IPFS daemon
    if not try_to_use_mcp_api(result["port"]):
        print("\nWarning: MCP server started but might not be properly connected to IPFS daemon.")
        print("Try adding content via the API manually.")
    
    # Success message
    print("\n=== Success! ===")
    print("New MCP server is running with daemon integration:")
    print(f"API URL: {result['url']}")
    print(f"Documentation: {result['docs_url']}")
    print(f"Server PID: {result['pid']}")
    print(f"Log file: {os.path.abspath('mcp_daemon_server.log')}")
    
    print("\nDaemon Status:")
    for daemon, running in daemon_status.items():
        print(f"- {daemon}: {'Running' if running else 'Not running'}")
    
    print("\nTo stop this server: kill", result["pid"])
    print("To verify functionality: try adding content to IPFS using the API")

if __name__ == "__main__":
    main()