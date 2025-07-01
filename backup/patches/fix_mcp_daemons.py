#!/usr/bin/env python3
"""
Script to fix daemon management issues and start IPFS, IPFS Cluster, and Lotus daemons
for the MCP server.

This script:
1. Cleans up stale lock files
2. Ensures proper initialization of repositories
3. Starts the daemons manually with proper error handling
4. Implements a verification step to ensure daemons are running
"""

import os
import sys
import time
import json
import signal
import logging
import argparse
import subprocess
from pathlib import Path
import shutil
import requests
import psutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_ipfs_path():
    """Get the IPFS repository path."""
    # Check environment variable first
    ipfs_path = os.environ.get("IPFS_PATH")
    if ipfs_path:
        return os.path.expanduser(ipfs_path)

    # Default path
    return os.path.expanduser("~/.ipfs")

def get_ipfs_cluster_path():
    """Get the IPFS Cluster service repository path."""
    # Check environment variable first
    cluster_path = os.environ.get("IPFS_CLUSTER_PATH")
    if cluster_path:
        return os.path.expanduser(cluster_path)

    # Default path
    return os.path.expanduser("~/.ipfs-cluster")

def get_lotus_path():
    """Get the Lotus repository path."""
    # Check environment variable first
    lotus_path = os.environ.get("LOTUS_PATH")
    if lotus_path:
        return os.path.expanduser(lotus_path)

    # Default path
    return os.path.expanduser("~/.lotus")

def get_ipfs_cluster_follow_path():
    """Get the IPFS Cluster follower repository path."""
    # Check environment variable first
    follower_path = os.environ.get("IPFS_CLUSTER_FOLLOW_PATH")
    if follower_path:
        return os.path.expanduser(follower_path)

    # Default path (using a subdirectory of cluster path)
    cluster_path = get_ipfs_cluster_path()
    return os.path.join(os.path.dirname(cluster_path), ".ipfs-cluster-follow")

def check_daemon_process(process_name):
    """Check if a daemon process is running by name."""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # Check process name
            if process_name in proc.info['name']:
                return True

            # Check command line arguments
            if proc.info['cmdline'] and any(process_name in arg for arg in proc.info['cmdline']):
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return False

def check_ipfs_api():
    """Check if IPFS API is responsive."""
    try:
        response = requests.post("http://127.0.0.1:5001/api/v0/version", timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False

def check_ipfs_cluster_api():
    """Check if IPFS Cluster API is responsive."""
    try:
        response = requests.get("http://127.0.0.1:9094/id", timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False

def check_lotus_api():
    """Check if Lotus API is responsive."""
    try:
        # Try to access the Lotus API
        socket_path = os.path.join(get_lotus_path(), "api")
        if os.path.exists(socket_path):
            return True

        # Check if the daemon is running
        return check_daemon_process("lotus daemon")
    except Exception:
        return False

def clean_lock_files():
    """Clean up any stale lock files."""
    locks_cleaned = 0

    # IPFS lock file
    ipfs_lock = os.path.join(get_ipfs_path(), "repo.lock")
    if os.path.exists(ipfs_lock):
        try:
            with open(ipfs_lock, 'r') as f:
                try:
                    pid = int(f.read().strip())
                    logger.info(f"Found IPFS lock file with PID: {pid}")

                    # Check if process is running
                    try:
                        process = psutil.Process(pid)
                        if "ipfs" in process.name().lower() or any("ipfs" in arg.lower() for arg in process.cmdline()):
                            logger.info(f"IPFS process is still running with PID {pid}, keeping lock file")
                        else:
                            logger.warning(f"Process with PID {pid} exists but isn't IPFS, removing stale lock")
                            os.remove(ipfs_lock)
                            locks_cleaned += 1
                    except psutil.NoSuchProcess:
                        logger.info(f"No process with PID {pid}, removing stale lock file")
                        os.remove(ipfs_lock)
                        locks_cleaned += 1
                except (ValueError, IOError):
                    logger.warning(f"Invalid content in IPFS lock file, removing")
                    os.remove(ipfs_lock)
                    locks_cleaned += 1
        except Exception as e:
            logger.error(f"Error handling IPFS lock file: {e}")

    # IPFS Cluster lock file
    cluster_lock = os.path.join(get_ipfs_cluster_path(), "service.lock")
    if os.path.exists(cluster_lock):
        try:
            with open(cluster_lock, 'r') as f:
                try:
                    pid = int(f.read().strip())
                    logger.info(f"Found IPFS Cluster lock file with PID: {pid}")

                    # Check if process is running
                    try:
                        process = psutil.Process(pid)
                        if "ipfs-cluster" in process.name().lower() or any("ipfs-cluster" in arg.lower() for arg in process.cmdline()):
                            logger.info(f"IPFS Cluster process is still running with PID {pid}, keeping lock file")
                        else:
                            logger.warning(f"Process with PID {pid} exists but isn't IPFS Cluster, removing stale lock")
                            os.remove(cluster_lock)
                            locks_cleaned += 1
                    except psutil.NoSuchProcess:
                        logger.info(f"No process with PID {pid}, removing stale lock file")
                        os.remove(cluster_lock)
                        locks_cleaned += 1
                except (ValueError, IOError):
                    logger.warning(f"Invalid content in IPFS Cluster lock file, removing")
                    os.remove(cluster_lock)
                    locks_cleaned += 1
        except Exception as e:
            logger.error(f"Error handling IPFS Cluster lock file: {e}")

    # IPFS Cluster Follow lock file
    cluster_follow_lock = os.path.join(get_ipfs_cluster_follow_path(), "service.lock")
    if os.path.exists(cluster_follow_lock):
        try:
            with open(cluster_follow_lock, 'r') as f:
                try:
                    pid = int(f.read().strip())
                    logger.info(f"Found IPFS Cluster Follow lock file with PID: {pid}")

                    # Check if process is running
                    try:
                        process = psutil.Process(pid)
                        if "ipfs-cluster" in process.name().lower() or any("ipfs-cluster" in arg.lower() for arg in process.cmdline()):
                            logger.info(f"IPFS Cluster Follow process is still running with PID {pid}, keeping lock file")
                        else:
                            logger.warning(f"Process with PID {pid} exists but isn't IPFS Cluster Follow, removing stale lock")
                            os.remove(cluster_follow_lock)
                            locks_cleaned += 1
                    except psutil.NoSuchProcess:
                        logger.info(f"No process with PID {pid}, removing stale lock file")
                        os.remove(cluster_follow_lock)
                        locks_cleaned += 1
                except (ValueError, IOError):
                    logger.warning(f"Invalid content in IPFS Cluster Follow lock file, removing")
                    os.remove(cluster_follow_lock)
                    locks_cleaned += 1
        except Exception as e:
            logger.error(f"Error handling IPFS Cluster Follow lock file: {e}")

    # Lotus lock file
    lotus_lock = os.path.join(get_lotus_path(), "repo.lock")
    if os.path.exists(lotus_lock):
        try:
            with open(lotus_lock, 'r') as f:
                try:
                    pid = int(f.read().strip())
                    logger.info(f"Found Lotus lock file with PID: {pid}")

                    # Check if process is running
                    try:
                        process = psutil.Process(pid)
                        if "lotus" in process.name().lower() or any("lotus" in arg.lower() for arg in process.cmdline()):
                            logger.info(f"Lotus process is still running with PID {pid}, keeping lock file")
                        else:
                            logger.warning(f"Process with PID {pid} exists but isn't Lotus, removing stale lock")
                            os.remove(lotus_lock)
                            locks_cleaned += 1
                    except psutil.NoSuchProcess:
                        logger.info(f"No process with PID {pid}, removing stale lock file")
                        os.remove(lotus_lock)
                        locks_cleaned += 1
                except (ValueError, IOError):
                    logger.warning(f"Invalid content in Lotus lock file, removing")
                    os.remove(lotus_lock)
                    locks_cleaned += 1
        except Exception as e:
            logger.error(f"Error handling Lotus lock file: {e}")

    return locks_cleaned

def ensure_ipfs_initialized():
    """Ensure IPFS repository is initialized."""
    ipfs_path = get_ipfs_path()
    config_file = os.path.join(ipfs_path, "config")

    if not os.path.exists(config_file):
        logger.info(f"Initializing IPFS repository at {ipfs_path}")
        try:
            os.makedirs(ipfs_path, exist_ok=True)

            # Initialize IPFS with lowpower profile for faster startup
            result = subprocess.run(
                ["ipfs", "init", "--profile=lowpower"],
                env={"IPFS_PATH": ipfs_path, "PATH": os.environ["PATH"]},
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                logger.error(f"Failed to initialize IPFS repository: {result.stderr}")
                return False

            logger.info("IPFS repository initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Error initializing IPFS repository: {e}")
            return False

    logger.info(f"IPFS repository already initialized at {ipfs_path}")
    return True

def ensure_ipfs_cluster_initialized():
    """Ensure IPFS Cluster repository is initialized."""
    cluster_path = get_ipfs_cluster_path()
    identity_file = os.path.join(cluster_path, "identity.json")
    service_file = os.path.join(cluster_path, "service.json")

    if not os.path.exists(identity_file) or not os.path.exists(service_file):
        logger.info(f"Initializing IPFS Cluster repository at {cluster_path}")
        try:
            os.makedirs(cluster_path, exist_ok=True)

            # Initialize IPFS Cluster
            result = subprocess.run(
                ["ipfs-cluster-service", "init"],
                env={"IPFS_CLUSTER_PATH": cluster_path, "PATH": os.environ["PATH"]},
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                logger.error(f"Failed to initialize IPFS Cluster repository: {result.stderr}")
                return False

            logger.info("IPFS Cluster repository initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Error initializing IPFS Cluster repository: {e}")
            return False

    logger.info(f"IPFS Cluster repository already initialized at {cluster_path}")
    return True

def ensure_lotus_initialized():
    """Ensure Lotus repository is initialized."""
    lotus_path = get_lotus_path()
    config_file = os.path.join(lotus_path, "config.toml")

    if not os.path.exists(config_file):
        logger.info(f"Lotus repository not found at {lotus_path}, no automatic initialization available")
        logger.info("You will need to initialize Lotus manually with: lotus daemon --init")
        return False

    logger.info(f"Lotus repository already initialized at {lotus_path}")
    return True

def start_ipfs_daemon():
    """Start the IPFS daemon."""
    # Check if daemon is already running
    if check_ipfs_api():
        logger.info("IPFS daemon is already running")
        return True

    # Ensure repository is initialized
    if not ensure_ipfs_initialized():
        logger.error("Failed to ensure IPFS repository is initialized")
        return False

    # Clean any stale lock files
    clean_lock_files()

    logger.info("Starting IPFS daemon")
    try:
        # Start IPFS daemon with nofuse option (more compatible)
        process = subprocess.Popen(
            ["ipfs", "daemon", "--routing=dhtclient", "--enable-gc"],
            env={"IPFS_PATH": get_ipfs_path(), "PATH": os.environ["PATH"]},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True  # Detach from parent process
        )

        # Wait for daemon to start (look for the "Daemon is ready" message)
        start_time = time.time()
        for _ in range(30):  # Wait up to 30 seconds
            if check_ipfs_api():
                logger.info("IPFS daemon started successfully")
                return True

            # Check if process is still running
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                logger.error(f"IPFS daemon exited prematurely: {stderr}")
                return False

            time.sleep(1)

        # If we get here, daemon didn't start in time
        logger.error("Timeout waiting for IPFS daemon to start")
        return False
    except Exception as e:
        logger.error(f"Error starting IPFS daemon: {e}")
        return False

def start_ipfs_cluster_service():
    """Start the IPFS Cluster service."""
    # Check if daemon is already running
    if check_ipfs_cluster_api():
        logger.info("IPFS Cluster service is already running")
        return True

    # Make sure IPFS is running first
    if not check_ipfs_api():
        logger.warning("IPFS daemon is not running, starting it first")
        if not start_ipfs_daemon():
            logger.error("Failed to start IPFS daemon, cannot start Cluster")
            return False

    # Ensure repository is initialized
    if not ensure_ipfs_cluster_initialized():
        logger.error("Failed to ensure IPFS Cluster repository is initialized")
        return False

    # Clean any stale lock files
    clean_lock_files()

    logger.info("Starting IPFS Cluster service")
    try:
        # Start IPFS Cluster service
        process = subprocess.Popen(
            ["ipfs-cluster-service", "daemon"],
            env={"IPFS_CLUSTER_PATH": get_ipfs_cluster_path(), "PATH": os.environ["PATH"]},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True  # Detach from parent process
        )

        # Wait for daemon to start
        start_time = time.time()
        for _ in range(30):  # Wait up to 30 seconds
            if check_ipfs_cluster_api():
                logger.info("IPFS Cluster service started successfully")
                return True

            # Check if process is still running
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                logger.error(f"IPFS Cluster service exited prematurely: {stderr}")
                return False

            time.sleep(1)

        # If we get here, daemon didn't start in time
        logger.error("Timeout waiting for IPFS Cluster service to start")
        return False
    except Exception as e:
        logger.error(f"Error starting IPFS Cluster service: {e}")
        return False

def start_lotus_daemon():
    """Start the Lotus daemon."""
    # Check if daemon is already running
    if check_lotus_api():
        logger.info("Lotus daemon is already running")
        return True

    # Ensure repository is initialized
    if not ensure_lotus_initialized():
        logger.warning("Lotus repository is not initialized, trying to start anyway")

    # Clean any stale lock files
    clean_lock_files()

    logger.info("Starting Lotus daemon")
    try:
        # Start Lotus daemon
        process = subprocess.Popen(
            ["lotus", "daemon"],
            env={"LOTUS_PATH": get_lotus_path(), "PATH": os.environ["PATH"]},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True  # Detach from parent process
        )

        # Wait for daemon to start
        start_time = time.time()
        for _ in range(60):  # Wait up to 60 seconds (Lotus can take longer)
            if check_lotus_api():
                logger.info("Lotus daemon started successfully")
                return True

            # Check if process is still running
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                logger.error(f"Lotus daemon exited prematurely: {stderr}")
                return False

            time.sleep(1)

        # If we get here, daemon didn't start in time
        logger.error("Timeout waiting for Lotus daemon to start")
        return False
    except Exception as e:
        logger.error(f"Error starting Lotus daemon: {e}")
        return False

def fix_mcp_daemon_configuration():
    """Update MCP server configuration to better handle daemons."""
    # Paths to search for run scripts
    script_paths = [
        ".",
        "ipfs_kit_py"
    ]

    fixed_files = []

    # Files to fix
    files_to_check = [
        "run_mcp_server_anyio.py",
        "run_mcp_server_fixed.py",
        "run_mcp_server.py",
        "start_mcp_server.sh",
        "start_mcp_anyio_server.sh"
    ]

    for script_path in script_paths:
        for filename in files_to_check:
            full_path = os.path.join(script_path, filename)
            if not os.path.exists(full_path):
                continue

            with open(full_path, 'r') as f:
                content = f.read()

            # Check if this file has "--skip-daemon" flag
            if "--skip-daemon" in content:
                # Remove or change the --skip-daemon flag
                updated_content = content.replace("--skip-daemon", "")

                # Write updated content back
                with open(full_path, 'w') as f:
                    f.write(updated_content)

                fixed_files.append(full_path)
                logger.info(f"Removed --skip-daemon flag from {full_path}")

    # Create a new script to patch the server module to allow manual daemon control
    patch_script = """# Apply runtime patch to MCP server to enable manual daemon control
import types
import logging
import time

logger = logging.getLogger(__name__)

def apply_daemon_control_patch():
    # Apply runtime patch to enable manual daemon control.
    try:
        from ipfs_kit_py.mcp.server_anyio import MCPServer

        # Original start_daemon method has a check that prevents manual control
        original_start_daemon = MCPServer.start_daemon

        # Create a new implementation that bypasses the check
        async def patched_start_daemon(self, daemon_type: str):
            # Patched version that allows manual daemon control.
            # Validate daemon type
            valid_types = ['ipfs', 'ipfs_cluster_service', 'ipfs_cluster_follow']
            if daemon_type not in valid_types:
                return {
                    "success": False,
                    "error": f"Invalid daemon type: {daemon_type}. Must be one of: {', '.join(valid_types)}",
                    "error_type": "InvalidDaemonType"
                }

            # Try to start the daemon directly using our helper functions
            if daemon_type == 'ipfs':
                from fix_mcp_daemons import start_ipfs_daemon
                result = start_ipfs_daemon()
                return {
                    "success": result,
                    "message": "IPFS daemon started successfully" if result else "Failed to start IPFS daemon",
                    "timestamp": time.time()
                }
            elif daemon_type == 'ipfs_cluster_service':
                from fix_mcp_daemons import start_ipfs_cluster_service
                result = start_ipfs_cluster_service()
                return {
                    "success": result,
                    "message": "IPFS Cluster service started successfully" if result else "Failed to start IPFS Cluster service",
                    "timestamp": time.time()
                }
            elif daemon_type == 'lotus':
                from fix_mcp_daemons import start_lotus_daemon
                result = start_lotus_daemon()
                return {
                    "success": result,
                    "message": "Lotus daemon started successfully" if result else "Failed to start Lotus daemon",
                    "timestamp": time.time()
                }
            else:
                return {
                    "success": False,
                    "error": f"Daemon type not implemented: {daemon_type}",
                    "error_type": "NotImplemented"
                }

        # Replace the method
        MCPServer.start_daemon = patched_start_daemon
        logger.info("Successfully patched MCPServer.start_daemon to enable manual daemon control")
        return True
    except (ImportError, AttributeError) as e:
        logger.error(f"Failed to patch daemon control: {e}")
        return False

# Apply the patch when this module is imported
apply_daemon_control_patch()
"""

    # Write the patch script
    patch_path = "patch_mcp_daemon_control.py"
    with open(patch_path, 'w') as f:
        f.write(patch_script)

    fixed_files.append(patch_path)
    logger.info(f"Created daemon control patch script at {patch_path}")

    return fixed_files

def main():
    """Main function to fix and start daemons."""
    parser = argparse.ArgumentParser(description="Fix and start daemons for MCP server")
    parser.add_argument("--clean-locks", action="store_true", help="Clean lock files")
    parser.add_argument("--init-only", action="store_true", help="Only initialize repositories, don't start daemons")
    parser.add_argument("--start-all", action="store_true", help="Start all daemons (IPFS, IPFS Cluster, Lotus)")
    parser.add_argument("--fix-config", action="store_true", help="Fix MCP configuration to handle daemons better")
    parser.add_argument("--ipfs", action="store_true", help="Start IPFS daemon")
    parser.add_argument("--ipfs-cluster", action="store_true", help="Start IPFS Cluster service")
    parser.add_argument("--lotus", action="store_true", help="Start Lotus daemon")

    args = parser.parse_args()

    # Default to starting IPFS if no specific action is specified
    if not (args.clean_locks or args.init_only or args.start_all or
            args.fix_config or args.ipfs or args.ipfs_cluster or args.lotus):
        args.ipfs = True

    # Clean lock files if requested
    if args.clean_locks:
        locks_cleaned = clean_lock_files()
        logger.info(f"Cleaned {locks_cleaned} stale lock files")

    # Fix MCP configuration if requested
    if args.fix_config:
        fixed_files = fix_mcp_daemon_configuration()
        logger.info(f"Fixed {len(fixed_files)} configuration files for better daemon handling")

    # Initialize repositories if requested or if starting daemons
    if args.init_only or args.start_all or args.ipfs:
        if ensure_ipfs_initialized():
            logger.info("IPFS repository is ready")
        else:
            logger.error("Failed to initialize IPFS repository")

    if args.init_only or args.start_all or args.ipfs_cluster:
        if ensure_ipfs_cluster_initialized():
            logger.info("IPFS Cluster repository is ready")
        else:
            logger.error("Failed to initialize IPFS Cluster repository")

    if args.init_only or args.start_all or args.lotus:
        if ensure_lotus_initialized():
            logger.info("Lotus repository is ready")
        else:
            logger.warning("Lotus repository initialization may be required")

    # Stop here if only initializing
    if args.init_only:
        logger.info("Initialization complete")
        return

    # Start daemons as requested
    if args.start_all or args.ipfs:
        if start_ipfs_daemon():
            logger.info("IPFS daemon is running")
        else:
            logger.error("Failed to start IPFS daemon")

    if args.start_all or args.ipfs_cluster:
        if start_ipfs_cluster_service():
            logger.info("IPFS Cluster service is running")
        else:
            logger.error("Failed to start IPFS Cluster service")

    if args.start_all or args.lotus:
        if start_lotus_daemon():
            logger.info("Lotus daemon is running")
        else:
            logger.error("Failed to start Lotus daemon")

    logger.info("Daemon management complete")

if __name__ == "__main__":
    main()
