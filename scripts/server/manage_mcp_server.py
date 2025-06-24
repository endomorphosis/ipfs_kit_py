#!/usr/bin/env python3
"""
MCP Server Manager

This script manages the MCP server by:
1. Checking if it's already running
2. Starting it if it's not running
3. Verifying all features work properly
4. Fixing any issues with non-working features
5. Implementing real backends where possible
"""

import os
import sys
import logging
import json
import subprocess
import time
import signal
import requests
import argparse
import psutil
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_MCP_PORT = 9997
DEFAULT_TIMEOUT = 30
PID_FILE = "enhanced_mcp_server.pid"

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="MCP Server Manager")
    parser.add_argument("--port", type=int, default=DEFAULT_MCP_PORT,
                        help=f"Port to run the MCP server on (default: {DEFAULT_MCP_PORT})")
    parser.add_argument("--debug", action="store_true",
                        help="Run the MCP server in debug mode")
    parser.add_argument("--real-implementations", action="store_true",
                        help="Attempt to set up and use real (non-mock) implementations")
    return parser.parse_args()

def is_port_in_use(port: int) -> bool:
    """Check if a port is already in use."""
    try:
        for conn in psutil.net_connections():
            if conn.laddr.port == port and conn.status == 'LISTEN':
                return True
        return False
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        # Fallback method
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) == 0

def find_mcp_process() -> Optional[psutil.Process]:
    """Find a running MCP server process."""
    # First check PID file
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                pid = int(f.read().strip())
            try:
                process = psutil.Process(pid)
                if "mcp_server" in " ".join(process.cmdline()) or "enhanced_mcp_server" in " ".join(process.cmdline()):
                    logger.info(f"Found MCP server process with PID {pid} from PID file")
                    return process
            except psutil.NoSuchProcess:
                logger.warning(f"PID file exists but process {pid} not found, removing stale PID file")
                os.remove(PID_FILE)
        except Exception as e:
            logger.warning(f"Error reading PID file: {e}")

    # Search for MCP server processes
    for process in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = " ".join(process.cmdline()) if process.cmdline() else ""
            if ("enhanced_mcp_server.py" in cmdline or
                "fixed_mcp_server.py" in cmdline or
                "real_mcp_server.py" in cmdline):
                logger.info(f"Found MCP server process: {process.pid}: {cmdline}")
                return process
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    return None

def check_mcp_server_health(port: int = DEFAULT_MCP_PORT) -> Dict[str, Any]:
    """Check the health of the MCP server."""
    try:
        response = requests.get(f"http://localhost:{port}/api/v0/health", timeout=DEFAULT_TIMEOUT)
        if response.status_code == 200:
            return response.json()
        else:
            logger.warning(f"MCP server health check returned status code {response.status_code}")
            return {"success": False, "error": f"HTTP {response.status_code}"}
    except requests.exceptions.RequestException as e:
        logger.warning(f"Error checking MCP server health: {e}")
        return {"success": False, "error": str(e)}

def check_storage_backends(port: int = DEFAULT_MCP_PORT) -> Dict[str, Dict[str, Any]]:
    """Check the status of all storage backends."""
    try:
        response = requests.get(f"http://localhost:{port}/api/v0/storage/health", timeout=DEFAULT_TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            return data.get("components", {})
        else:
            logger.warning(f"Storage backends check returned status code {response.status_code}")
            return {}
    except requests.exceptions.RequestException as e:
        logger.warning(f"Error checking storage backends: {e}")
        return {}

def kill_mcp_server(process: psutil.Process) -> bool:
    """Kill a running MCP server process."""
    try:
        logger.info(f"Terminating MCP server process {process.pid}")
        process.terminate()

        # Wait for the process to terminate
        gone, alive = psutil.wait_procs([process], timeout=DEFAULT_TIMEOUT)
        if alive:
            logger.warning(f"Process {process.pid} did not terminate, forcing kill")
            process.kill()

        logger.info(f"MCP server process {process.pid} terminated")

        # Remove PID file if it exists
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)

        return True
    except Exception as e:
        logger.error(f"Error killing MCP server process: {e}")
        return False

def setup_real_implementations() -> bool:
    """Set up real implementations for all storage backends."""
    logger.info("Setting up real implementations for storage backends...")

    # Source the real credentials file
    try:
        if os.path.exists("real_mcp_credentials.sh"):
            # Execute the script and capture the environment variables
            logger.info("Sourcing real_mcp_credentials.sh")
            output = subprocess.check_output(
                ["bash", "-c", "source ./real_mcp_credentials.sh && env"],
                universal_newlines=True
            )

            # Parse the output and set environment variables
            for line in output.splitlines():
                if "=" in line:
                    key, value = line.split("=", 1)
                    if key.startswith(("HUGGINGFACE_", "AWS_", "FILECOIN_", "STORACHA_", "LASSIE_")):
                        os.environ[key] = value
                        logger.debug(f"Set environment variable: {key}")
        else:
            logger.warning("real_mcp_credentials.sh not found, using default credentials")
    except Exception as e:
        logger.error(f"Error sourcing real_mcp_credentials.sh: {e}")

    # Run setup scripts for each storage backend
    setup_results = {}

    # HuggingFace setup
    if os.path.exists("setup_huggingface.py"):
        logger.info("Running HuggingFace setup script")
        try:
            result = subprocess.run(
                [sys.executable, "setup_huggingface.py"],
                capture_output=True,
                text=True
            )
            setup_results["huggingface"] = result.returncode == 0
            if result.returncode == 0:
                logger.info("HuggingFace setup completed successfully")
            else:
                logger.warning(f"HuggingFace setup failed: {result.stderr}")
        except Exception as e:
            logger.error(f"Error running HuggingFace setup: {e}")
            setup_results["huggingface"] = False

    # S3 setup
    if os.path.exists("setup_s3.py"):
        logger.info("Running S3 setup script")
        try:
            result = subprocess.run(
                [sys.executable, "setup_s3.py"],
                capture_output=True,
                text=True
            )
            setup_results["s3"] = result.returncode == 0
            if result.returncode == 0:
                logger.info("S3 setup completed successfully")
            else:
                logger.warning(f"S3 setup failed: {result.stderr}")
        except Exception as e:
            logger.error(f"Error running S3 setup: {e}")
            setup_results["s3"] = False

    # Filecoin setup
    if os.path.exists("setup_filecoin.py"):
        logger.info("Running Filecoin setup script")
        try:
            result = subprocess.run(
                [sys.executable, "setup_filecoin.py"],
                capture_output=True,
                text=True
            )
            setup_results["filecoin"] = result.returncode == 0
            if result.returncode == 0:
                logger.info("Filecoin setup completed successfully")
            else:
                logger.warning(f"Filecoin setup failed: {result.stderr}")
        except Exception as e:
            logger.error(f"Error running Filecoin setup: {e}")
            setup_results["filecoin"] = False

    # Storacha setup
    if os.path.exists("setup_storacha.py"):
        logger.info("Running Storacha setup script")
        try:
            result = subprocess.run(
                [sys.executable, "setup_storacha.py"],
                capture_output=True,
                text=True
            )
            setup_results["storacha"] = result.returncode == 0
            if result.returncode == 0:
                logger.info("Storacha setup completed successfully")
            else:
                logger.warning(f"Storacha setup failed: {result.stderr}")
        except Exception as e:
            logger.error(f"Error running Storacha setup: {e}")
            setup_results["storacha"] = False

    # Lassie setup
    if os.path.exists("setup_lassie.py"):
        logger.info("Running Lassie setup script")
        try:
            result = subprocess.run(
                [sys.executable, "setup_lassie.py"],
                capture_output=True,
                text=True
            )
            setup_results["lassie"] = result.returncode == 0
            if result.returncode == 0:
                logger.info("Lassie setup completed successfully")
            else:
                logger.warning(f"Lassie setup failed: {result.stderr}")
        except Exception as e:
            logger.error(f"Error running Lassie setup: {e}")
            setup_results["lassie"] = False

    # Run the fix_storage_backends script to handle any remaining issues
    if os.path.exists("fix_storage_backends.py"):
        logger.info("Running fix_storage_backends.py to handle any remaining issues")
        try:
            result = subprocess.run(
                [sys.executable, "fix_storage_backends.py"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                logger.info("Storage backend fixes applied successfully")
            else:
                logger.warning(f"Storage backend fixes failed: {result.stderr}")
        except Exception as e:
            logger.error(f"Error running storage backend fixes: {e}")

    # Check overall results
    success_count = sum(1 for result in setup_results.values() if result)
    total_count = len(setup_results)

    logger.info(f"Real implementation setup complete: {success_count}/{total_count} backends set up successfully")
    return success_count > 0

def start_mcp_server(port: int, debug: bool = False, real_implementations: bool = False) -> Optional[psutil.Process]:
    """Start the MCP server."""
    logger.info(f"Starting MCP server on port {port} (debug={debug}, real_implementations={real_implementations})")

    # First check if port is already in use
    if is_port_in_use(port):
        logger.warning(f"Port {port} is already in use")

        # Try to find the process using this port
        for process in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                for conn in process.connections(kind='inet'):
                    if conn.laddr.port == port and conn.status == 'LISTEN':
                        logger.info(f"Process using port {port}: {process.pid} {process.name()} {' '.join(process.cmdline())}")

                        # Check if it's an MCP server process
                        cmdline = " ".join(process.cmdline())
                        if "enhanced_mcp_server.py" in cmdline or "fixed_mcp_server.py" in cmdline or "real_mcp_server.py" in cmdline:
                            logger.info(f"Found an MCP server already running on port {port}")
                            return process
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        # If we reached here, the port is in use but not by an MCP server
        logger.error(f"Port {port} is in use by another application, cannot start MCP server")
        return None

    # Set up real implementations if requested
    if real_implementations:
        setup_real_implementations()

    # Determine which MCP server script to use
    if os.path.exists("enhanced_mcp_server.py"):
        mcp_script = "enhanced_mcp_server.py"
    elif os.path.exists("fixed_mcp_server.py"):
        mcp_script = "fixed_mcp_server.py"
    else:
        logger.error("No MCP server script found")
        return None

    # Start the MCP server
    cmd = [sys.executable, mcp_script, "--port", str(port)]
    if debug:
        cmd.append("--debug")

    try:
        logger.info(f"Executing: {' '.join(cmd)}")
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )

        # Wait a moment for the server to start
        time.sleep(2)

        # Check if the process is still running
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            logger.error(f"MCP server process exited with code {process.returncode}")
            logger.error(f"STDOUT: {stdout}")
            logger.error(f"STDERR: {stderr}")
            return None

        logger.info(f"Started MCP server process with PID {process.pid}")

        # Check health to confirm it's working
        health_check_attempts = 5
        for attempt in range(health_check_attempts):
            logger.info(f"Checking MCP server health (attempt {attempt+1}/{health_check_attempts})")
            health = check_mcp_server_health(port)
            if health.get("success", False):
                logger.info("MCP server is healthy")
                return psutil.Process(process.pid)
            else:
                logger.warning(f"MCP server not healthy yet: {health.get('error', 'Unknown error')}")
                time.sleep(2)

        logger.error("MCP server did not become healthy within timeout")
        return psutil.Process(process.pid)
    except Exception as e:
        logger.error(f"Error starting MCP server: {e}")
        return None

def fix_storage_backend(backend_name: str, backend_status: Dict[str, Any], port: int) -> bool:
    """Fix a specific storage backend."""
    logger.info(f"Fixing storage backend: {backend_name}")

    # Implement specific fixes based on backend type and status
    if backend_name == "huggingface":
        # Fix HuggingFace backend
        if os.path.exists("setup_huggingface.py"):
            try:
                result = subprocess.run(
                    [sys.executable, "setup_huggingface.py"],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    logger.info("Fixed HuggingFace backend")
                    return True
                else:
                    logger.warning(f"Failed to fix HuggingFace backend: {result.stderr}")
            except Exception as e:
                logger.error(f"Error fixing HuggingFace backend: {e}")

    elif backend_name == "s3":
        # Fix S3 backend
        if os.path.exists("setup_s3.py"):
            try:
                result = subprocess.run(
                    [sys.executable, "setup_s3.py"],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    logger.info("Fixed S3 backend")
                    return True
                else:
                    logger.warning(f"Failed to fix S3 backend: {result.stderr}")
            except Exception as e:
                logger.error(f"Error fixing S3 backend: {e}")

    elif backend_name == "filecoin":
        # Fix Filecoin backend
        if os.path.exists("setup_filecoin.py"):
            try:
                result = subprocess.run(
                    [sys.executable, "setup_filecoin.py"],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    logger.info("Fixed Filecoin backend")
                    return True
                else:
                    logger.warning(f"Failed to fix Filecoin backend: {result.stderr}")
            except Exception as e:
                logger.error(f"Error fixing Filecoin backend: {e}")

    elif backend_name == "storacha":
        # Fix Storacha backend
        if os.path.exists("setup_storacha.py"):
            try:
                result = subprocess.run(
                    [sys.executable, "setup_storacha.py"],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    logger.info("Fixed Storacha backend")
                    return True
                else:
                    logger.warning(f"Failed to fix Storacha backend: {result.stderr}")
            except Exception as e:
                logger.error(f"Error fixing Storacha backend: {e}")

    elif backend_name == "lassie":
        # Fix Lassie backend
        if os.path.exists("setup_lassie.py"):
            try:
                result = subprocess.run(
                    [sys.executable, "setup_lassie.py"],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    logger.info("Fixed Lassie backend")
                    return True
                else:
                    logger.warning(f"Failed to fix Lassie backend: {result.stderr}")
            except Exception as e:
                logger.error(f"Error fixing Lassie backend: {e}")

    # If we've reached here, we couldn't fix the backend with a specific setup script
    # Try to fix it with the general fix_storage_backends.py script
    if os.path.exists("fix_storage_backends.py"):
        try:
            logger.info(f"Attempting general fix for {backend_name} backend")
            result = subprocess.run(
                [sys.executable, "fix_storage_backends.py"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                logger.info(f"Applied general fixes to {backend_name} backend")
                return True
            else:
                logger.warning(f"Failed to apply general fixes to {backend_name} backend: {result.stderr}")
        except Exception as e:
            logger.error(f"Error applying general fixes to {backend_name} backend: {e}")

    return False

def verify_and_fix_storage_backends(port: int) -> Dict[str, bool]:
    """Verify and fix all storage backends."""
    logger.info("Verifying and fixing storage backends...")

    # Check current status
    backends = check_storage_backends(port)

    if not backends:
        logger.warning("Could not retrieve storage backends status")
        return {}

    # Track fixes applied
    fixes_applied = {}

    # Check each backend
    for backend_name, backend_status in backends.items():
        # Skip IPFS and local backends as they should work natively
        if backend_name in ["ipfs", "local"]:
            fixes_applied[backend_name] = True
            continue

        # Check if backend needs fixing
        needs_fixing = False

        # Backend is not available
        if not backend_status.get("available", False):
            logger.warning(f"Backend {backend_name} is not available")
            needs_fixing = True

        # Backend is in simulation mode
        elif backend_status.get("simulation", False):
            logger.warning(f"Backend {backend_name} is in simulation mode")
            needs_fixing = True

        # Backend has an error
        elif "error" in backend_status and backend_status["error"]:
            logger.warning(f"Backend {backend_name} has an error: {backend_status['error']}")
            needs_fixing = True

        # Apply fixes if needed
        if needs_fixing:
            fixes_applied[backend_name] = fix_storage_backend(backend_name, backend_status, port)
        else:
            logger.info(f"Backend {backend_name} is working correctly")
            fixes_applied[backend_name] = True

    return fixes_applied

def restart_mcp_server(process: psutil.Process, port: int, debug: bool = False, real_implementations: bool = False) -> Optional[psutil.Process]:
    """Restart the MCP server."""
    logger.info(f"Restarting MCP server (PID: {process.pid})")

    # Kill the existing process
    if not kill_mcp_server(process):
        logger.error("Failed to kill existing MCP server")
        return None

    # Wait a moment for the port to be released
    time.sleep(2)

    # Start a new server
    return start_mcp_server(port, debug, real_implementations)

def check_mcp_server_features(port: int) -> Dict[str, Any]:
    """Check all MCP server features to ensure they're working."""
    features = {}

    # Check general health
    health = check_mcp_server_health(port)
    features["health"] = health.get("success", False)

    # Check storage backends
    storage_backends = check_storage_backends(port)
    features["storage"] = {name: backend.get("available", False) for name, backend in storage_backends.items()}

    # Check IPFS features
    try:
        # Check version endpoint
        version_response = requests.get(f"http://localhost:{port}/api/v0/ipfs/version", timeout=DEFAULT_TIMEOUT)
        features["ipfs_version"] = version_response.status_code == 200

        # Try to add a small file
        test_data = b"Test data for IPFS add"
        files = {'file': ('test.txt', test_data)}
        add_response = requests.post(f"http://localhost:{port}/api/v0/ipfs/add", files=files, timeout=DEFAULT_TIMEOUT)
        if add_response.status_code == 200:
            add_result = add_response.json()
            features["ipfs_add"] = add_result.get("success", False)

            # If add was successful, try to retrieve the content
            if features["ipfs_add"] and "cid" in add_result:
                cid = add_result["cid"]
                cat_response = requests.get(f"http://localhost:{port}/api/v0/ipfs/cat/{cid}", timeout=DEFAULT_TIMEOUT)
                features["ipfs_cat"] = cat_response.status_code == 200 and cat_response.content == test_data
            else:
                features["ipfs_cat"] = False
        else:
            features["ipfs_add"] = False
            features["ipfs_cat"] = False
    except requests.exceptions.RequestException as e:
        logger.warning(f"Error checking IPFS features: {e}")
        features["ipfs_version"] = False
        features["ipfs_add"] = False
        features["ipfs_cat"] = False

    return features

def main():
    """Main function."""
    args = parse_arguments()

    logger.info("MCP Server Manager")
    logger.info(f"Port: {args.port}")
    logger.info(f"Debug mode: {args.debug}")
    logger.info(f"Real implementations: {args.real_implementations}")

    # First, check if MCP server is already running
    process = find_mcp_process()

    if process:
        logger.info(f"Found MCP server process: {process.pid}")

        # Check health to see if it's responsive
        health = check_mcp_server_health(args.port)

        if health.get("success", False):
            logger.info("MCP server is healthy")

            # Check features
            logger.info("Checking MCP server features")
            features = check_mcp_server_features(args.port)

            all_features_working = all(features.values()) and all(features.get("storage", {}).values())

            if all_features_working:
                logger.info("All MCP server features are working correctly")
            else:
                logger.warning("Some MCP server features are not working correctly")
                logger.warning(f"Features status: {json.dumps(features, indent=2)}")

                # Check storage backends
                logger.info("Checking storage backends")
                storage_backends = check_storage_backends(args.port)

                # Apply fixes to storage backends if needed
                if args.real_implementations:
                    logger.info("Setting up real implementations for storage backends")
                    setup_real_implementations()

                logger.info("Verifying and fixing storage backends")
                fixes = verify_and_fix_storage_backends(args.port)

                # If we applied any fixes, restart the server to apply them
                if any(not status for status in fixes.values()):
                    logger.info("Restarting MCP server to apply fixes")
                    process = restart_mcp_server(process, args.port, args.debug, args.real_implementations)

                    if not process:
                        logger.error("Failed to restart MCP server")
                        sys.exit(1)

                    # Check features again
                    logger.info("Checking MCP server features after restart")
                    features = check_mcp_server_features(args.port)

                    all_features_working = all(features.values()) and all(features.get("storage", {}).values())

                    if all_features_working:
                        logger.info("All MCP server features are now working correctly")
                    else:
                        logger.warning("Some MCP server features are still not working correctly")
                        logger.warning(f"Features status: {json.dumps(features, indent=2)}")
        else:
            logger.warning(f"MCP server is not healthy: {health.get('error', 'Unknown error')}")

            # Restart the server
            logger.info("Restarting MCP server")
            process = restart_mcp_server(process, args.port, args.debug, args.real_implementations)

            if not process:
                logger.error("Failed to restart MCP server")
                sys.exit(1)

            # Check health again
            health = check_mcp_server_health(args.port)

            if health.get("success", False):
                logger.info("MCP server is now healthy")
            else:
                logger.error(f"MCP server is still not healthy after restart: {health.get('error', 'Unknown error')}")
                sys.exit(1)
    else:
        logger.info("No MCP server process found, starting new server")

        # Start new server
        process = start_mcp_server(args.port, args.debug, args.real_implementations)

        if not process:
            logger.error("Failed to start MCP server")
            sys.exit(1)

        logger.info(f"Started MCP server process: {process.pid}")

        # Check health
        health = check_mcp_server_health(args.port)

        if health.get("success", False):
            logger.info("MCP server is healthy")

            # Verify and fix storage backends
            logger.info("Verifying and fixing storage backends")
            fixes = verify_and_fix_storage_backends(args.port)

            # If we applied any fixes, restart the server to apply them
            if any(not status for status in fixes.values()):
                logger.info("Restarting MCP server to apply fixes")
                process = restart_mcp_server(process, args.port, args.debug, args.real_implementations)

                if not process:
                    logger.error("Failed to restart MCP server")
                    sys.exit(1)
        else:
            logger.error(f"MCP server is not healthy after start: {health.get('error', 'Unknown error')}")
            sys.exit(1)

    # Final check
    logger.info("Final MCP server status:")
    health = check_mcp_server_health(args.port)

    if health.get("success", False):
        logger.info("MCP server is healthy")
        logger.info(f"Storage backends: {json.dumps(health.get('storage_backends', {}), indent=2)}")
        logger.info(f"Server is running at http://localhost:{args.port}")
        logger.info(f"API documentation: http://localhost:{args.port}/docs")
        logger.info(f"Process ID: {process.pid}")
    else:
        logger.error(f"MCP server is not healthy: {health.get('error', 'Unknown error')}")
        sys.exit(1)

if __name__ == "__main__":
    main()
