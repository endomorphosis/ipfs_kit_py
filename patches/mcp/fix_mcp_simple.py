#!/usr/bin/env python3
"""
Simplified script to fix daemon issues and start daemons
for the MCP server without external dependencies.
"""

import os
import sys
import time
import json
import signal
import logging
import subprocess
from pathlib import Path
import shutil

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

def check_daemon_process_by_pid(pid):
    """Check if a process with given PID exists."""
    try:
        # Send signal 0 to check if process exists
        os.kill(pid, 0)
        return True
    except OSError:
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
                    if check_daemon_process_by_pid(pid):
                        logger.info(f"Process with PID {pid} is running, not removing lock file")
                    else:
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
                    if check_daemon_process_by_pid(pid):
                        logger.info(f"Process with PID {pid} is running, not removing lock file")
                    else:
                        logger.info(f"No process with PID {pid}, removing stale lock file")
                        os.remove(cluster_lock)
                        locks_cleaned += 1
                except (ValueError, IOError):
                    logger.warning(f"Invalid content in IPFS Cluster lock file, removing")
                    os.remove(cluster_lock)
                    locks_cleaned += 1
        except Exception as e:
            logger.error(f"Error handling IPFS Cluster lock file: {e}")

    # Lotus lock file
    lotus_lock = os.path.join(get_lotus_path(), "repo.lock")
    if os.path.exists(lotus_lock):
        try:
            with open(lotus_lock, 'r') as f:
                try:
                    pid = int(f.read().strip())
                    logger.info(f"Found Lotus lock file with PID: {pid}")

                    # Check if process is running
                    if check_daemon_process_by_pid(pid):
                        logger.info(f"Process with PID {pid} is running, not removing lock file")
                    else:
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

def check_ipfs_api():
    """Check if IPFS API is responsive."""
    try:
        # Use subprocess to run curl instead of requests library
        result = subprocess.run(
            ["curl", "-s", "http://127.0.0.1:5001/api/v0/version"],
            check=False,
            capture_output=True,
            text=True
        )
        return result.returncode == 0 and len(result.stdout) > 0
    except Exception:
        return False

def check_ipfs_cluster_api():
    """Check if IPFS Cluster API is responsive."""
    try:
        # Use subprocess to run curl instead of requests library
        result = subprocess.run(
            ["curl", "-s", "http://127.0.0.1:9094/id"],
            check=False,
            capture_output=True,
            text=True
        )
        return result.returncode == 0 and len(result.stdout) > 0
    except Exception:
        return False

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

        # Give it a moment to start
        logger.info("Waiting for IPFS daemon to start...")
        time.sleep(5)

        # Check every second for 30 seconds if the daemon is running
        for i in range(30):
            if check_ipfs_api():
                logger.info(f"IPFS daemon started successfully after {i+5} seconds")
                return True
            time.sleep(1)

        # If we get here, daemon didn't start in time
        logger.error("Timeout waiting for IPFS daemon to start")
        return False
    except Exception as e:
        logger.error(f"Error starting IPFS daemon: {e}")
        return False

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

        # Give it a moment to start
        logger.info("Waiting for IPFS Cluster service to start...")
        time.sleep(5)

        # Check every second for 30 seconds if the daemon is running
        for i in range(30):
            if check_ipfs_cluster_api():
                logger.info(f"IPFS Cluster service started successfully after {i+5} seconds")
                return True
            time.sleep(1)

        # If we get here, daemon didn't start in time
        logger.error("Timeout waiting for IPFS Cluster service to start")
        return False
    except Exception as e:
        logger.error(f"Error starting IPFS Cluster service: {e}")
        return False

def check_lotus_api():
    """Check if Lotus API is responsive."""
    # Check if socket exists
    lotus_api_socket = os.path.join(get_lotus_path(), "api")
    if os.path.exists(lotus_api_socket):
        return True

    # Try to run lotus version command
    try:
        result = subprocess.run(
            ["lotus", "version"],
            env={"LOTUS_PATH": get_lotus_path(), "PATH": os.environ["PATH"]},
            check=False,
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception:
        return False

def start_lotus_daemon():
    """Start the Lotus daemon."""
    # Check if daemon is already running
    if check_lotus_api():
        logger.info("Lotus daemon is already running")
        return True

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

        # Give it a moment to start
        logger.info("Waiting for Lotus daemon to start...")
        time.sleep(10)  # Lotus takes longer to start

        # Check every 2 seconds for 60 seconds if the daemon is running
        for i in range(30):
            if check_lotus_api():
                logger.info(f"Lotus daemon started successfully after {i*2+10} seconds")
                return True
            time.sleep(2)

        # If we get here, daemon didn't start in time
        logger.error("Timeout waiting for Lotus daemon to start")
        return False
    except Exception as e:
        logger.error(f"Error starting Lotus daemon: {e}")
        return False

def create_mcp_server_script():
    """Create a script to start MCP server with daemon support."""
    script_path = "run_mcp_with_daemons.py"

    # Write a simpler version of the script without triple quotes
    with open(script_path, "w") as f:
        f.write("#!/usr/bin/env python3\n\n")
        f.write("# MCP server with daemon support enabled\n\n")
        f.write("import os\n")
        f.write("import sys\n")
        f.write("import time\n")
        f.write("import subprocess\n")
        f.write("import logging\n\n")

        f.write("# Import helper functions\n")
        f.write("try:\n")
        f.write("    from fix_mcp_simple import start_ipfs_daemon, start_ipfs_cluster_service, start_lotus_daemon\n")
        f.write("except ImportError:\n")
        f.write("    print('Could not import daemon helper functions')\n")
        f.write("    sys.exit(1)\n\n")

        f.write("# Configure logging\n")
        f.write("logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')\n")
        f.write("logger = logging.getLogger(__name__)\n\n")

        f.write("def setup_daemons():\n")
        f.write("    # Start IPFS daemon\n")
        f.write("    if not start_ipfs_daemon():\n")
        f.write("        logger.error('Failed to start IPFS daemon')\n")
        f.write("        return False\n\n")
        f.write("    # Start IPFS Cluster service\n")
        f.write("    if not start_ipfs_cluster_service():\n")
        f.write("        logger.warning('Failed to start IPFS Cluster service - continuing anyway')\n\n")
        f.write("    # Try to start Lotus daemon\n")
        f.write("    try:\n")
        f.write("        start_lotus_daemon()\n")
        f.write("    except Exception as e:\n")
        f.write("        logger.warning(f'Error starting Lotus daemon: {e} - continuing anyway')\n\n")
        f.write("    return True\n\n")

        f.write("def find_mcp_server_script():\n")
        f.write("    # Order of preference for server scripts\n")
        f.write("    script_candidates = [\n")
        f.write("        'run_mcp_server_anyio.py',\n")
        f.write("        'run_mcp_server_fixed.py',\n")
        f.write("        'run_mcp_server.py'\n")
        f.write("    ]\n\n")
        f.write("    # Check current directory and ipfs_kit_py subdirectory for each script\n")
        f.write("    search_paths = ['.', 'ipfs_kit_py']\n\n")
        f.write("    for path in search_paths:\n")
        f.write("        for script in script_candidates:\n")
        f.write("            script_path = os.path.join(path, script)\n")
        f.write("            if os.path.exists(script_path):\n")
        f.write("                return script_path\n\n")
        f.write("    return None\n\n")

        f.write("def start_mcp_server():\n")
        f.write("    # Find the best server script to use\n")
        f.write("    server_script = find_mcp_server_script()\n")
        f.write("    if not server_script:\n")
        f.write("        logger.error('Could not find an MCP server script to run')\n")
        f.write("        return False\n\n")
        f.write("    logger.info(f'Starting MCP server using {server_script}')\n\n")
        f.write("    # Build command line with appropriate parameters\n")
        f.write("    cmd = ['python', server_script, '--debug', '--isolation', '--port', '8002', '--host', 'localhost']\n\n")
        f.write("    # Start the server\n")
        f.write("    try:\n")
        f.write("        process = subprocess.Popen(\n")
        f.write("            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True\n")
        f.write("        )\n\n")
        f.write("        # Give it a moment to start\n")
        f.write("        logger.info('Waiting for MCP server to start...')\n")
        f.write("        time.sleep(5)\n\n")
        f.write("        # Check if the server started successfully\n")
        f.write("        try:\n")
        f.write("            check_cmd = ['curl', '-s', 'http://localhost:8002/api/v0/mcp/health']\n")
        f.write("            result = subprocess.run(check_cmd, check=False, capture_output=True, text=True)\n\n")
        f.write("            if result.returncode == 0 and 'success' in result.stdout:\n")
        f.write("                logger.info('MCP server started successfully')\n")
        f.write("                return True\n")
        f.write("            else:\n")
        f.write("                logger.warning(f'MCP server may not have started properly: {result.stdout}')\n")
        f.write("                return False\n")
        f.write("        except Exception as e:\n")
        f.write("            logger.warning(f'Error checking MCP server: {e}')\n")
        f.write("            return False\n")
        f.write("    except Exception as e:\n")
        f.write("        logger.error(f'Error starting MCP server: {e}')\n")
        f.write("        return False\n\n")

        f.write("def main():\n")
        f.write("    logger.info('Setting up daemons and MCP server')\n\n")
        f.write("    # Set up daemons\n")
        f.write("    if not setup_daemons():\n")
        f.write("        logger.error('Failed to set up daemons, MCP server may not work properly')\n\n")
        f.write("    # Start MCP server\n")
        f.write("    if start_mcp_server():\n")
        f.write("        logger.info('MCP server is running with daemon support')\n")
        f.write("        print('\\nMCP server is running with daemon support')\n")
        f.write("        print('API URL: http://localhost:8002/api/v0/mcp')\n")
        f.write("        print('Documentation: http://localhost:8002/docs')\n")
        f.write("    else:\n")
        f.write("        logger.error('Failed to start MCP server with daemon support')\n")
        f.write("        return 1\n\n")
        f.write("    return 0\n\n")

        f.write("if __name__ == '__main__':\n")
        f.write("    sys.exit(main())\n")

    os.chmod(script_path, 0o755)  # Make executable

    logger.info(f"Created MCP server script at {script_path}")
    return script_path

def main():
    """Main function to fix and start daemons."""
    # Clean stale lock files first
    locks_cleaned = clean_lock_files()
    logger.info(f"Cleaned {locks_cleaned} stale lock files")

    # Start IPFS daemon
    if start_ipfs_daemon():
        logger.info("IPFS daemon is now running")
    else:
        logger.error("Failed to start IPFS daemon")

    # Start IPFS Cluster service
    if start_ipfs_cluster_service():
        logger.info("IPFS Cluster service is now running")
    else:
        logger.warning("Failed to start IPFS Cluster service")

    # Try to start Lotus daemon
    try:
        if start_lotus_daemon():
            logger.info("Lotus daemon is now running")
        else:
            logger.warning("Failed to start Lotus daemon")
    except Exception as e:
        logger.warning(f"Error starting Lotus daemon: {e}")

    # Create script for running MCP server with daemon support
    server_script = create_mcp_server_script()

    print("\n----------------------------------------------------------")
    print("Daemon setup complete!")
    print("----------------------------------------------------------")
    print(f"To start the MCP server with daemon support, run: python {server_script}")
    print("This will start a new instance of the MCP server on port 8002")
    print("The existing server on port 9990 will continue to run")
    print("----------------------------------------------------------\n")

if __name__ == "__main__":
    main()
