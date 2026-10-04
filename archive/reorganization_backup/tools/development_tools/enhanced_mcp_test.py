#!/usr/bin/env python3
"""
Enhanced MCP Server Test and Fix

This script addresses common issues with MCP server testing:
1. Tests if server is running on expected ports
2. Manages proper server startup and shutdown
3. Tests JSON-RPC endpoints with better error reporting
4. Fixes common configuration issues automatically

Usage:
  python3 enhanced_mcp_test.py [--port PORT] [--start] [--stop] [--fix]
"""

import os
import sys
import json
import time
import signal
import logging
import argparse
import subprocess
import requests
from typing import Dict, Any, Optional, List, Tuple, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("enhanced_mcp_test.log", mode="w"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("enhanced-mcp-test")

class EnhancedMCPTest:
    """Enhanced MCP server test and management."""

    def __init__(self, host: str = "localhost", port: int = 9998):
        """Initialize the tester."""
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.jsonrpc_url = f"{self.base_url}/jsonrpc"
        self.health_url = f"{self.base_url}/health"
        self.server_process = None
        self.pid_file = "final_mcp_server.pid"
        self.log_file = "final_mcp_server.log"
        self.server_files = {
            "script": ["run_final_mcp_solution.sh", "run_final_solution.sh"],
            "server": "final_mcp_server.py"
        }
        
    def check_port_consistency(self) -> bool:
        """Check if port configuration is consistent across files."""
        logger.info("Checking port consistency across configuration files...")
        
        # Check port in server file
        server_port = None
        try:
            with open(self.server_files["server"], "r") as f:
                for line in f:
                    if "PORT = " in line:
                        try:
                            server_port = int(line.split("=")[1].strip())
                            logger.info(f"Found port in {self.server_files['server']}: {server_port}")
                            break
                        except ValueError:
                            logger.warning(f"Could not parse port in {self.server_files['server']}")
        except Exception as e:
            logger.error(f"Error reading server file: {e}")
        
        # Check port in script files
        script_ports = {}
        for script in self.server_files["script"]:
            if os.path.exists(script):
                try:
                    with open(script, "r") as f:
                        for line in f:
                            if line.strip().startswith("PORT="):
                                try:
                                    script_port = int(line.split("=")[1].strip().split("#")[0].strip())
                                    script_ports[script] = script_port
                                    logger.info(f"Found port in {script}: {script_port}")
                                    break
                                except ValueError:
                                    logger.warning(f"Could not parse port in {script}")
                except Exception as e:
                    logger.error(f"Error reading script file {script}: {e}")
        
        # Compare ports
        consistent = True
        if server_port is not None:
            for script, port in script_ports.items():
                if port != server_port:
                    logger.warning(f"Port mismatch: {script} uses port {port}, but server uses {server_port}")
                    consistent = False
        
        # Check if test port matches
        if server_port is not None and self.port != server_port:
            logger.warning(f"Test port ({self.port}) does not match server port ({server_port})")
            consistent = False
            
        return consistent
    
    def fix_port_consistency(self) -> bool:
        """Fix port consistency issues."""
        logger.info("Fixing port consistency across configuration files...")
        
        # First, determine the server port
        server_port = None
        try:
            with open(self.server_files["server"], "r") as f:
                for line in f:
                    if "PORT = " in line:
                        try:
                            server_port = int(line.split("=")[1].strip())
                            break
                        except ValueError:
                            pass
        except Exception:
            pass
            
        if server_port is None:
            logger.error("Could not determine server port from server file")
            return False
            
        # Update port in script files
        for script in self.server_files["script"]:
            if os.path.exists(script):
                try:
                    with open(script, "r") as f:
                        lines = f.readlines()
                    
                    updated = False
                    for i, line in enumerate(lines):
                        if line.strip().startswith("PORT="):
                            original = line
                            # Preserve any comments after the port number
                            if "#" in line:
                                comment_part = line.split("#", 1)[1]
                                lines[i] = f"PORT={server_port}  # {comment_part}"
                            else:
                                lines[i] = f"PORT={server_port}\n"
                            logger.info(f"Updated port in {script}: {original.strip()} -> {lines[i].strip()}")
                            updated = True
                            break
                    
                    if updated:
                        with open(script, "w") as f:
                            f.writelines(lines)
                except Exception as e:
                    logger.error(f"Error updating port in {script}: {e}")
        
        # Update the port in our own configuration
        self.port = server_port
        self.base_url = f"http://{self.host}:{self.port}"
        self.jsonrpc_url = f"{self.base_url}/jsonrpc"
        self.health_url = f"{self.base_url}/health"
        
        return True
        
    def is_server_running(self) -> bool:
        """Check if the MCP server is already running."""
        # Try to access health endpoint
        try:
            response = requests.get(self.health_url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                logger.info(f"MCP server is running: {data}")
                return True
        except Exception:
            pass
            
        # Check if process is running from PID file
        if os.path.exists(self.pid_file):
            try:
                with open(self.pid_file, "r") as f:
                    pid = int(f.read().strip())
                
                # Check if process is running
                try:
                    os.kill(pid, 0)  # Signal 0 is used to check if process exists
                    logger.info(f"MCP server process with PID {pid} is running but not responding to health checks")
                    return True
                except OSError:
                    logger.warning(f"PID file exists but process {pid} is not running")
                    # Clean up stale PID file
                    try:
                        os.unlink(self.pid_file)
                    except:
                        pass
            except Exception as e:
                logger.error(f"Error checking PID file: {e}")
                
        return False
    
    def start_server(self) -> bool:
        """Start the MCP server."""
        if self.is_server_running():
            logger.info("Server is already running")
            return True
            
        logger.info("Starting MCP server...")
        
        # Try using script first
        script_path = None
        for script in self.server_files["script"]:
            if os.path.exists(script):
                script_path = os.path.abspath(script)
                break
                
        if script_path:
            logger.info(f"Starting server using script: {script_path}")
            try:
                process = subprocess.Popen(
                    ["bash", script_path, "--start-only"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                # Wait a bit for startup
                time.sleep(2)
                
                # Check if process exited immediately (which would indicate failure)
                if process.poll() is not None:
                    stdout, stderr = process.communicate()
                    logger.error(f"Script failed to start server. Exit code: {process.returncode}")
                    logger.error(f"STDOUT: {stdout.decode('utf-8')}")
                    logger.error(f"STDERR: {stderr.decode('utf-8')}")
                    
                    # Try direct start instead
                    logger.info("Trying to start server directly...")
                    return self._start_server_directly()
                    
                # Wait for server to become responsive
                for i in range(30):
                    if self.is_server_running():
                        logger.info("Server started successfully")
                        return True
                    time.sleep(1)
                
                logger.error("Server started but did not become responsive")
                return False
            except Exception as e:
                logger.error(f"Error starting server with script: {e}")
                return self._start_server_directly()
        else:
            logger.warning("No server script found, trying direct start")
            return self._start_server_directly()
    
    def _start_server_directly(self) -> bool:
        """Start the server directly using Python."""
        logger.info(f"Starting server directly: {self.server_files['server']}")
        
        server_path = os.path.abspath(self.server_files["server"])
        if not os.path.exists(server_path):
            logger.error(f"Server file not found: {server_path}")
            return False
            
        try:
            # Build command with proper parameters
            cmd = [
                sys.executable,
                server_path,
                "--host", "0.0.0.0",
                "--port", str(self.port),
                "--debug"
            ]
            
            logger.info(f"Running command: {' '.join(cmd)}")
            
            # Start server process
            process = subprocess.Popen(
                cmd,
                stdout=open(self.log_file, "w"),
                stderr=subprocess.STDOUT
            )
            
            # Save PID
            with open(self.pid_file, "w") as f:
                f.write(str(process.pid))
            
            # Store process for later
            self.server_process = process
            
            # Wait for server to become responsive
            for i in range(30):
                if i > 0 and i % 5 == 0:
                    logger.info(f"Still waiting for server to start (attempt {i}/30)")
                    
                try:
                    response = requests.get(self.health_url, timeout=2)
                    if response.status_code == 200:
                        logger.info("Server started successfully")
                        return True
                except Exception:
                    pass
                
                # Check if process is still running
                if process.poll() is not None:
                    logger.error(f"Server process exited with code {process.returncode}")
                    # Show log file
                    try:
                        with open(self.log_file, "r") as f:
                            log_content = f.read()
                        logger.error(f"Server log:\n{log_content}")
                    except:
                        pass
                    return False
                    
                time.sleep(1)
            
            logger.error("Server started but did not become responsive")
            self.stop_server()  # Clean up
            return False
        except Exception as e:
            logger.error(f"Error starting server directly: {e}")
            return False
    
    def stop_server(self) -> bool:
        """Stop the MCP server."""
        logger.info("Stopping MCP server...")
        
        # Try stopping via PID file first
        if os.path.exists(self.pid_file):
            try:
                with open(self.pid_file, "r") as f:
                    pid = int(f.read().strip())
                
                logger.info(f"Stopping server process with PID {pid}")
                try:
                    os.kill(pid, signal.SIGTERM)
                    
                    # Wait for process to terminate
                    for _ in range(10):
                        try:
                            os.kill(pid, 0)  # Check if process exists
                            time.sleep(0.5)
                        except OSError:
                            break  # Process is gone
                            
                    # If process is still running, force kill
                    try:
                        os.kill(pid, 0)
                        logger.warning(f"Process {pid} did not terminate, sending SIGKILL")
                        os.kill(pid, signal.SIGKILL)
                    except OSError:
                        pass  # Process is gone
                    
                    # Clean up PID file
                    try:
                        os.unlink(self.pid_file)
                    except:
                        pass
                        
                    logger.info("Server stopped successfully")
                    return True
                except Exception as e:
                    logger.error(f"Error killing process {pid}: {e}")
            except Exception as e:
                logger.error(f"Error reading PID file: {e}")
        
        # If we started the server directly, stop it
        if self.server_process is not None:
            try:
                logger.info(f"Terminating server process {self.server_process.pid}")
                self.server_process.terminate()
                try:
                    self.server_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    logger.warning(f"Process did not terminate, killing it")
                    self.server_process.kill()
                
                # Clean up PID file
                try:
                    os.unlink(self.pid_file)
                except:
                    pass
                    
                self.server_process = None
                logger.info("Server stopped successfully")
                return True
            except Exception as e:
                logger.error(f"Error stopping server process: {e}")
        
        logger.info("No running server found to stop")
        return True
    
    def restart_server(self) -> bool:
        """Restart the MCP server."""
        logger.info("Restarting MCP server...")
        self.stop_server()
        time.sleep(2)  # Give it some time to clean up
        return self.start_server()
    
    def call_jsonrpc(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Call a JSON-RPC method on the server."""
        if params is None:
            params = {}
        
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": int(time.time() * 1000)
        }
        
        logger.debug(f"Calling JSON-RPC method: {method}")
        logger.debug(f"Params: {params}")
        
        try:
            response = requests.post(
                self.jsonrpc_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code != 200:
                logger.error(f"HTTP error: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return {"error": {"code": response.status_code, "message": response.text}}
            
            try:
                data = response.json()
                logger.debug(f"Response: {data}")
                
                if "error" in data:
                    logger.error(f"JSON-RPC error: {data['error']}")
                    
                return data
            except Exception as e:
                logger.error(f"Error parsing JSON response: {e}")
                logger.error(f"Raw response: {response.text}")
                return {"error": {"code": -32700, "message": f"Error parsing JSON response: {e}"}}
        except Exception as e:
            logger.error(f"Error making JSON-RPC call to {method}: {e}")
            return {"error": {"code": -32603, "message": str(e)}}
    
    def test_server(self) -> bool:
        """Run tests against the MCP server."""
        logger.info(f"Testing MCP server at {self.base_url}...")
        
        # Check if server is running
        if not self.is_server_running():
            logger.error("Server is not running")
            return False
            
        # Test health endpoint
        try:
            response = requests.get(self.health_url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Health check passed: {data}")
            else:
                logger.error(f"Health check failed: {response.status_code} {response.text}")
                return False
        except Exception as e:
            logger.error(f"Health check failed with exception: {e}")
            return False
            
        # Test ping method
        result = self.call_jsonrpc("ping")
        if "result" in result and result["result"] == "pong":
            logger.info("Ping test passed")
        else:
            logger.error(f"Ping test failed: {result}")
            return False
            
        # Test get_tools method
        result = self.call_jsonrpc("get_tools")
        if "result" in result and "tools" in result["result"]:
            tools = result["result"]["tools"]
            logger.info(f"get_tools test passed: {len(tools)} tools found")
        else:
            # Try list_tools as fallback
            result = self.call_jsonrpc("list_tools")
            if "result" in result and "tools" in result["result"]:
                tools = result["result"]["tools"]
                logger.info(f"list_tools test passed: {len(tools)} tools found")
            else:
                logger.error(f"Tool listing tests failed: {result}")
                return False
                
        # Test get_server_info method
        result = self.call_jsonrpc("get_server_info")
        if "result" in result and "version" in result["result"]:
            logger.info(f"get_server_info test passed: {result['result']}")
        else:
            logger.error(f"get_server_info test failed: {result}")
            return False
            
        logger.info("All tests passed!")
        return True
    
    def diagnose_and_fix(self) -> bool:
        """Diagnose and fix common issues."""
        logger.info("Diagnosing and fixing common issues...")
        
        # Check port consistency
        if not self.check_port_consistency():
            logger.info("Fixing port consistency")
            self.fix_port_consistency()
        
        # Check if server is running
        if not self.is_server_running():
            logger.info("Server is not running, starting it")
            if not self.start_server():
                logger.error("Failed to start server")
                return False
        
        # Test server
        if not self.test_server():
            logger.info("Server tests failed, restarting server")
            if not self.restart_server():
                logger.error("Failed to restart server")
                return False
                
            # Test again after restart
            if not self.test_server():
                logger.error("Server tests still failing after restart")
                return False
        
        logger.info("All issues fixed!")
        return True

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Enhanced MCP Server Test and Fix")
    parser.add_argument("--host", default="localhost", help="Server host")
    parser.add_argument("--port", type=int, default=9998, help="Server port")
    parser.add_argument("--start", action="store_true", help="Start the server")
    parser.add_argument("--stop", action="store_true", help="Stop the server")
    parser.add_argument("--restart", action="store_true", help="Restart the server")
    parser.add_argument("--test", action="store_true", help="Test the server")
    parser.add_argument("--fix", action="store_true", help="Fix common issues")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Initialize test tool
    tester = EnhancedMCPTest(host=args.host, port=args.port)
    
    # Execute requested actions
    if args.stop:
        tester.stop_server()
    
    if args.restart:
        tester.restart_server()
    elif args.start:
        tester.start_server()
    
    if args.fix:
        tester.diagnose_and_fix()
    
    if args.test or (not any([args.start, args.stop, args.restart, args.fix])):
        # Default action is to test
        tester.test_server()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
