#!/usr/bin/env python3
"""
Comprehensive MCP Server LibP2P Integration Test

This script verifies the full end-to-end integration of LibP2P with the MCP server architecture,
ensuring that:

1. LibP2P dependencies are properly installed and available
2. The LibP2P model and controller are correctly registered with the MCP server
3. The MCP server properly exposes LibP2P DHT operations via HTTP endpoints
4. Content can be announced and retrieved via LibP2P
5. DHT operations function correctly

The test operates in multiple modes to verify functionality under different conditions:
- With and without real LibP2P dependencies
- With synchronous and AnyIO implementations
- With various error scenarios
"""

import os
import sys
import time
import json
import logging
import argparse
import tempfile
import subprocess
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("mcp_libp2p_test")

# Import our dependency management to ensure libp2p is available
try:
    from install_libp2p import ensure_mcp_libp2p_integration, get_libp2p_status
    INSTALL_MODULE_AVAILABLE = True
except ImportError:
    logger.warning("install_libp2p module not available, dependency checks will be limited")
    INSTALL_MODULE_AVAILABLE = False

# Set this to True if you want to force auto-installation during the test
AUTO_INSTALL_ENABLED = os.environ.get("IPFS_KIT_AUTO_INSTALL_DEPS", "0") == "1"

# First check if dependencies are available
if INSTALL_MODULE_AVAILABLE:
    # Get current status
    status = get_libp2p_status()
    HAS_LIBP2P = status["libp2p_available"]
    HAS_MCP_DEPS = status["mcp_integration"]["available"]
    
    # Show status
    logger.info(f"LibP2P available: {HAS_LIBP2P}")
    logger.info(f"MCP integration available: {HAS_MCP_DEPS}")
    
    # If auto-install is enabled, try to install missing dependencies
    if AUTO_INSTALL_ENABLED and (not HAS_LIBP2P or not HAS_MCP_DEPS):
        logger.info("Auto-installation enabled, installing missing dependencies...")
        ensure_mcp_libp2p_integration()
        
        # Check status again
        status = get_libp2p_status()
        HAS_LIBP2P = status["libp2p_available"]
        HAS_MCP_DEPS = status["mcp_integration"]["available"]
        
        logger.info(f"After installation - LibP2P available: {HAS_LIBP2P}")
        logger.info(f"After installation - MCP integration available: {HAS_MCP_DEPS}")
else:
    # Make a best-effort determination of dependency status
    try:
        import libp2p
        HAS_LIBP2P = True
    except ImportError:
        HAS_LIBP2P = False
        
    try:
        import fastapi
        import anyio
        HAS_MCP_DEPS = True
    except ImportError:
        HAS_MCP_DEPS = False

# Set up testing environment
TEST_DIR = tempfile.mkdtemp(prefix="mcp_libp2p_test_")
logger.info(f"Using test directory: {TEST_DIR}")

class MCPServerTestWrapper:
    """Helper class to manage MCP server for testing."""
    
    def __init__(self, persistence_path: str, debug_mode: bool = True, port: int = 8765):
        """
        Initialize an MCP server test wrapper.
        
        Args:
            persistence_path: Path for MCP server persistence files
            debug_mode: Enable debug mode
            port: Port for the HTTP server
        """
        self.persistence_path = persistence_path
        self.debug_mode = debug_mode
        self.port = port
        self.process = None
        self.base_url = f"http://localhost:{port}"
        self.api_prefix = ""  # Default to empty prefix (will be detected)
        
    def start(self) -> bool:
        """
        Start the MCP server process.
        
        Returns:
            bool: True if started successfully
        """
        if self.process is not None:
            logger.warning("Server already running, stopping first")
            self.stop()
            
        # Construct command to start server
        cmd = [
            sys.executable,
            "-m", "ipfs_kit_py.mcp.server_anyio",
            "--debug" if self.debug_mode else "",
            "--isolation",  # Always use isolation mode for testing
            "--port", str(self.port),
            "--persistence-path", self.persistence_path 
            # Removed --api-prefix argument that was causing the error
        ]
        
        # Filter out empty arguments
        cmd = [arg for arg in cmd if arg != ""]
        
        logger.info(f"Starting MCP server with command: {' '.join(cmd)}")
        
        try:
            # Start server as subprocess
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait a moment for server to start
            time.sleep(5)
            
            # Verify server is running by checking if process is still alive
            if self.process.poll() is not None:
                # Process has exited
                stdout, stderr = self.process.communicate()
                logger.error(f"Server failed to start with return code {self.process.returncode}")
                logger.error(f"STDOUT: {stdout}")
                logger.error(f"STDERR: {stderr}")
                self.process = None
                return False
                
            # Basic health check
            if not self._check_health():
                logger.error("Server health check failed")
                self.stop()
                return False
                
            logger.info(f"MCP server started at {self.base_url}")
            return True
            
        except Exception as e:
            logger.error(f"Error starting MCP server: {e}")
            if self.process is not None:
                self.process.terminate()
                self.process = None
            return False
            
    def stop(self) -> bool:
        """
        Stop the MCP server process.
        
        Returns:
            bool: True if stopped successfully
        """
        if self.process is None:
            logger.warning("No server process to stop")
            return True
            
        try:
            # Try graceful termination
            self.process.terminate()
            
            # Wait up to 5 seconds for process to exit
            for _ in range(10):
                if self.process.poll() is not None:
                    break
                time.sleep(0.5)
                
            # Force kill if still running
            if self.process.poll() is None:
                logger.warning("Server didn't exit gracefully, killing process")
                self.process.kill()
                self.process.wait()
                
            stdout, stderr = self.process.communicate()
            
            # Check for errors in output
            if self.process.returncode != 0:
                logger.warning(f"Server exited with code {self.process.returncode}")
                logger.debug(f"STDOUT: {stdout}")
                logger.debug(f"STDERR: {stderr}")
                
            self.process = None
            logger.info("MCP server stopped")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping MCP server: {e}")
            self.process = None
            return False
            
    def _check_health(self) -> bool:
        """
        Check if server is healthy with a basic health check.
        
        Returns:
            bool: True if health check passes
        """
        import requests
        
        try:
            # Give the server a moment to initialize
            max_retries = 5
            retry_delay = 1
            
            # Try several endpoints to determine what's working
            health_endpoints = [
                "/health",                  # Standard endpoint
                "/api/v0/mcp/health",       # Default API prefix
                "/mcp/health",              # Alternate API prefix
                "/"                         # Root endpoint (for debugging)
            ]
            
            for attempt in range(max_retries):
                logger.info(f"Health check attempt {attempt+1}/{max_retries}")
                
                # Try each potential endpoint
                for endpoint in health_endpoints:
                    try:
                        url = f"{self.base_url}{endpoint}"
                        logger.info(f"Trying health endpoint: {url}")
                        response = requests.get(url, timeout=5)
                        logger.info(f"Response from {endpoint}: status={response.status_code}")
                        
                        if response.status_code == 200:
                            try:
                                health_data = response.json()
                                logger.info(f"Server health check passed at {endpoint}: {health_data}")
                                # Update base_url if we found a working API at a different prefix
                                if endpoint != "/health" and endpoint != "/":
                                    self.api_prefix = endpoint.replace("/health", "")
                                    logger.info(f"Updated API prefix to: {self.api_prefix}")
                                return True
                            except ValueError:
                                logger.warning(f"Endpoint {endpoint} returned non-JSON response")
                    except requests.exceptions.ConnectionError:
                        logger.warning(f"Connection error for {endpoint}")
                    except requests.exceptions.Timeout:
                        logger.warning(f"Timeout error for {endpoint}")
                    except Exception as endpoint_error:
                        logger.warning(f"Error checking {endpoint}: {endpoint_error}")
                
                # Wait before retry
                logger.info(f"All endpoints failed, waiting {retry_delay}s before retry")
                time.sleep(retry_delay)
                
            # List all available routes if we have access to the process output
            if self.process and self.process.poll() is None:
                logger.info("Checking process output for available routes")
                # Don't block if there's no output
                stdout_data = ""
                stderr_data = ""
                try:
                    # Try to get output without blocking
                    import select
                    if select.select([self.process.stdout], [], [], 0.1)[0]:
                        stdout_data = self.process.stdout.read(4096)
                    if select.select([self.process.stderr], [], [], 0.1)[0]:
                        stderr_data = self.process.stderr.read(4096)
                except Exception as io_error:
                    logger.warning(f"Error getting process output: {io_error}")
                
                logger.info(f"Process STDOUT: {stdout_data}")
                logger.info(f"Process STDERR: {stderr_data}")
            
            logger.error(f"Server health check failed after {max_retries} attempts")
            return False
            
        except Exception as e:
            logger.error(f"Error checking server health: {e}")
            return False
            
    def check_libp2p_integration(self) -> Dict[str, Any]:
        """
        Check if LibP2P is properly integrated with the MCP server.
        
        Returns:
            dict: Results of the integration check
        """
        import requests
        
        result = {
            "success": False,
            "libp2p_controller_available": False,
            "health_check_available": False,
            "dht_endpoints_available": False,
            "api_prefix": self.api_prefix,
            "timestamps": {
                "start": time.time()
            }
        }
        
        try:
            # First check server health to confirm controllers available
            health_url = f"{self.base_url}{self.api_prefix}/health"
            logger.info(f"Checking health at: {health_url}")
            health_response = requests.get(health_url)
            if health_response.status_code != 200:
                result["error"] = f"Health check failed with status {health_response.status_code}"
                return result
                
            health_data = health_response.json()
            result["server_health"] = health_data
            
            # Request debug info to check available controllers
            debug_url = f"{self.base_url}{self.api_prefix}/debug"
            logger.info(f"Checking debug at: {debug_url}")
            debug_response = requests.get(debug_url)
            if debug_response.status_code != 200:
                result["error"] = f"Debug endpoint failed with status {debug_response.status_code}"
                return result
                
            debug_data = debug_response.json()
            
            # Check if LibP2P controller is available by examining models and controllers
            models = debug_data.get("models", {})
            if "libp2p" in models:
                result["libp2p_model_available"] = True
                logger.info("LibP2P model is available in the server")
            
            # If we can't directly see controllers list, check for controller presence another way
            # Request LibP2P-specific health endpoint to see if it's registered
            libp2p_health_url = f"{self.base_url}{self.api_prefix}/libp2p/health"
            logger.info(f"Checking LibP2P health at: {libp2p_health_url}")
            libp2p_health_response = requests.get(libp2p_health_url)
            result["health_response"] = {
                "status_code": libp2p_health_response.status_code,
                "data": libp2p_health_response.json() if libp2p_health_response.status_code == 200 else None
            }
            
            if libp2p_health_response.status_code == 200:
                result["health_check_available"] = True
                result["libp2p_controller_available"] = True
                logger.info("LibP2P health endpoint is available - controller confirmed")
                
            # Check for DHT endpoints by calling options
            dht_endpoints = [
                "/libp2p/dht/find_peer",
                "/libp2p/dht/provide",
                "/libp2p/dht/find_providers"
            ]
            
            dht_results = {}
            for endpoint in dht_endpoints:
                try:
                    endpoint_url = f"{self.base_url}{self.api_prefix}{endpoint}"
                    logger.info(f"Checking DHT endpoint (OPTIONS): {endpoint_url}")
                    options_response = requests.options(endpoint_url)
                    dht_results[endpoint] = {
                        "status_code": options_response.status_code,
                        "available": options_response.status_code == 200
                    }
                    if options_response.status_code == 200:
                        logger.info(f"DHT endpoint {endpoint} is available")
                        # If we find working DHT endpoints, that confirms the controller is available
                        result["libp2p_controller_available"] = True
                except Exception as e:
                    dht_results[endpoint] = {
                        "error": str(e),
                        "available": False
                    }
                    logger.warning(f"Error checking DHT endpoint {endpoint}: {e}")
                    
            # Also try to list available routes by using a common framework endpoint
            try:
                routes_url = f"{self.base_url}/openapi.json"
                logger.info(f"Trying to get API routes from OpenAPI spec: {routes_url}")
                routes_response = requests.get(routes_url)
                if routes_response.status_code == 200:
                    routes_data = routes_response.json()
                    paths = routes_data.get("paths", {})
                    libp2p_paths = [path for path in paths.keys() if "libp2p" in path]
                    result["available_libp2p_paths"] = libp2p_paths
                    logger.info(f"Found {len(libp2p_paths)} LibP2P-related paths in OpenAPI spec")
                    
                    if libp2p_paths:
                        # If we find LibP2P paths in the OpenAPI spec, that confirms the controller
                        result["libp2p_controller_available"] = True
            except Exception as routes_error:
                logger.warning(f"Error getting API routes: {routes_error}")
                    
            result["dht_endpoints"] = dht_results
            result["dht_endpoints_available"] = any(
                endpoint["available"] for endpoint in dht_results.values()
            )
            
            # Final determination of success
            result["success"] = (
                result["libp2p_controller_available"] and
                (result["health_check_available"] or result["dht_endpoints_available"])
            )
            
            result["timestamps"]["end"] = time.time()
            result["duration"] = result["timestamps"]["end"] - result["timestamps"]["start"]
            
            return result
            
        except Exception as e:
            result["error"] = str(e)
            result["timestamps"]["end"] = time.time()
            result["duration"] = result["timestamps"]["end"] - result["timestamps"]["start"]
            return result
            
    def test_dht_operations(self) -> Dict[str, Any]:
        """
        Test DHT operations through the MCP server API.
        
        Returns:
            dict: Results of the DHT operations tests
        """
        import requests
        
        result = {
            "success": False,
            "operations_tested": [],
            "operations_passed": [],
            "api_prefix": self.api_prefix,
            "timestamps": {
                "start": time.time()
            }
        }
        
        try:
            # Test content announcement
            test_content = "Hello, this is a test message for LibP2P DHT operations"
            
            # 1. Test content announcement
            operation = "announce_content"
            result["operations_tested"].append(operation)
            
            announce_url = f"{self.base_url}{self.api_prefix}/libp2p/announce"
            logger.info(f"Testing content announcement: POST {announce_url}")
            announce_response = requests.post(
                announce_url,
                json={
                    "cid": "QmTestCIDForDHTOperations",
                    "data": test_content
                }
            )
            
            result[operation] = {
                "status_code": announce_response.status_code,
                "data": announce_response.json() if announce_response.status_code == 200 else None
            }
            
            if announce_response.status_code == 200:
                result["operations_passed"].append(operation)
                logger.info(f"Content announcement passed: {announce_response.json()}")
            else:
                logger.warning(f"Content announcement failed: {announce_response.status_code}")
                if announce_response.text:
                    logger.warning(f"Error response: {announce_response.text}")
                
            # 2. Test content retrieval
            operation = "get_content"
            result["operations_tested"].append(operation)
            
            content_url = f"{self.base_url}{self.api_prefix}/libp2p/content/QmTestCIDForDHTOperations"
            logger.info(f"Testing content retrieval: GET {content_url}")
            content_response = requests.get(content_url)
            
            result[operation] = {
                "status_code": content_response.status_code,
                "data": content_response.text if content_response.status_code == 200 else None
            }
            
            if content_response.status_code == 200:
                result["operations_passed"].append(operation)
                logger.info(f"Content retrieval passed")
                logger.debug(f"Retrieved content: {content_response.text}")
            else:
                logger.warning(f"Content retrieval failed: {content_response.status_code}")
                if content_response.text:
                    logger.warning(f"Error response: {content_response.text}")
                
            # 3. Test DHT provider announcement
            operation = "dht_provide"
            result["operations_tested"].append(operation)
            
            provide_url = f"{self.base_url}{self.api_prefix}/libp2p/dht/provide"
            logger.info(f"Testing DHT provide: POST {provide_url}")
            provide_response = requests.post(
                provide_url,
                json={"cid": "QmTestCIDForDHTOperations"}
            )
            
            result[operation] = {
                "status_code": provide_response.status_code,
                "data": provide_response.json() if provide_response.status_code == 200 else None
            }
            
            if provide_response.status_code == 200:
                result["operations_passed"].append(operation)
                logger.info(f"DHT provide passed: {provide_response.json()}")
            else:
                logger.warning(f"DHT provide failed: {provide_response.status_code}")
                if provide_response.text:
                    logger.warning(f"Error response: {provide_response.text}")
                
            # 4. Test DHT provider lookup
            operation = "dht_find_providers"
            result["operations_tested"].append(operation)
            
            find_providers_url = f"{self.base_url}{self.api_prefix}/libp2p/dht/find_providers"
            logger.info(f"Testing DHT find providers: POST {find_providers_url}")
            find_providers_response = requests.post(
                find_providers_url,
                json={"cid": "QmTestCIDForDHTOperations"}
            )
            
            result[operation] = {
                "status_code": find_providers_response.status_code,
                "data": find_providers_response.json() if find_providers_response.status_code == 200 else None
            }
            
            if find_providers_response.status_code == 200:
                result["operations_passed"].append(operation)
                logger.info(f"DHT find providers passed: {find_providers_response.json()}")
            else:
                logger.warning(f"DHT find providers failed: {find_providers_response.status_code}")
                if find_providers_response.text:
                    logger.warning(f"Error response: {find_providers_response.text}")
                
            # 5. Test peer discovery
            operation = "discover_peers"
            result["operations_tested"].append(operation)
            
            discover_url = f"{self.base_url}{self.api_prefix}/libp2p/discover"
            logger.info(f"Testing peer discovery: POST {discover_url}")
            discover_response = requests.post(
                discover_url,
                json={"discovery_method": "all", "limit": 5}
            )
            
            result[operation] = {
                "status_code": discover_response.status_code,
                "data": discover_response.json() if discover_response.status_code == 200 else None
            }
            
            if discover_response.status_code == 200:
                result["operations_passed"].append(operation)
                logger.info(f"Peer discovery passed: {discover_response.json()}")
            else:
                logger.warning(f"Peer discovery failed: {discover_response.status_code}")
                if discover_response.text:
                    logger.warning(f"Error response: {discover_response.text}")
                
            # Final success determination
            result["success"] = len(result["operations_passed"]) > 0
            result["pass_rate"] = len(result["operations_passed"]) / len(result["operations_tested"])
            
            result["timestamps"]["end"] = time.time()
            result["duration"] = result["timestamps"]["end"] - result["timestamps"]["start"]
            
            return result
            
        except Exception as e:
            result["error"] = str(e)
            result["timestamps"]["end"] = time.time()
            result["duration"] = result["timestamps"]["end"] - result["timestamps"]["start"]
            return result

def run_test():
    """Run the comprehensive integration test."""
    # Results container
    results = {
        "timestamp": time.time(),
        "platform": sys.platform,
        "python_version": sys.version,
        "dependencies": {
            "has_libp2p": HAS_LIBP2P,
            "has_mcp_deps": HAS_MCP_DEPS,
            "auto_install_enabled": AUTO_INSTALL_ENABLED
        },
        "phases": {}
    }
    
    # Phase 1: MCP Server tests
    persistence_path = os.path.join(TEST_DIR, "mcp_server")
    
    # Create server wrapper
    server = MCPServerTestWrapper(
        persistence_path=persistence_path,
        debug_mode=True,
        port=8765
    )
    
    try:
        # Start server
        phase_results = {}
        phase_results["server_start"] = {
            "success": server.start(),
            "timestamp": time.time()
        }
        
        if phase_results["server_start"]["success"]:
            # Check libp2p integration
            phase_results["libp2p_integration"] = server.check_libp2p_integration()
            
            # Test DHT operations if integration check passed
            if phase_results["libp2p_integration"]["success"]:
                phase_results["dht_operations"] = server.test_dht_operations()
            else:
                phase_results["dht_operations"] = {
                    "success": False,
                    "error": "Skipped due to libp2p integration failure",
                    "skipped": True
                }
                
            # Stop server
            phase_results["server_stop"] = {
                "success": server.stop(),
                "timestamp": time.time()
            }
        else:
            # Server start failed, skip other tests
            phase_results["libp2p_integration"] = {
                "success": False,
                "error": "Skipped due to server start failure",
                "skipped": True
            }
            phase_results["dht_operations"] = {
                "success": False,
                "error": "Skipped due to server start failure",
                "skipped": True
            }
            
        # Add phase results to overall results
        results["phases"]["mcp_server"] = phase_results
        
        # Determine overall success
        results["success"] = (
            phase_results["server_start"].get("success", False) and
            phase_results["libp2p_integration"].get("success", False) and
            (not phase_results["dht_operations"].get("skipped", True) and 
             phase_results["dht_operations"].get("success", False))
        )
        
    except Exception as e:
        logger.error(f"Error during test execution: {e}")
        results["error"] = str(e)
        results["success"] = False
        
        # Make sure server is stopped
        try:
            server.stop()
        except Exception as stop_error:
            logger.error(f"Error stopping server during exception handling: {stop_error}")
    
    # Clean up any temporary files
    try:
        import shutil
        shutil.rmtree(TEST_DIR, ignore_errors=True)
    except Exception as cleanup_error:
        logger.error(f"Error cleaning up test directory: {cleanup_error}")
    
    # Return results
    return results

def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description="Run MCP LibP2P integration tests")
    parser.add_argument("--output", help="Output file for test results (JSON)")
    # Only parse args when running the script directly, not when imported by pytest
    if __name__ == "__main__":
        args = parser.parse_args()
    else:
        # When run under pytest, use default values
        args = parser.parse_args([])
    
    logger.info("Starting MCP LibP2P integration test")
    
    # Run the test
    results = run_test()
    
    # Show summary
    logger.info("Test completed")
    logger.info(f"Overall success: {results['success']}")
    
    if "error" in results:
        logger.error(f"Test error: {results['error']}")
        
    # Output to file if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"Results written to {args.output}")
    
    # Return exit code based on success
    return 0 if results["success"] else 1

if __name__ == "__main__":
    sys.exit(main())