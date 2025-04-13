#!/usr/bin/env python3
"""
Simple script to start IPFS daemon for the MCP server.
"""

import os
import sys
import time
import subprocess
import logging

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

def patch_mcp_server():
    """Create a restart script for the MCP server without skip-daemon flag."""
    script_content = """#!/usr/bin/env python3
import subprocess
import os
import time
import sys

print("Starting MCP server with IPFS daemon support...")

# Kill existing instances
subprocess.run(["pkill", "-f", "run_mcp_server"])
time.sleep(2)

# Choose the best server script
server_scripts = [
    "run_mcp_server_anyio.py",
    "run_mcp_server_fixed.py",
    "run_mcp_server.py"
]

server_script = None
for script in server_scripts:
    if os.path.exists(script):
        server_script = script
        break

if not server_script:
    print("Error: Could not find an MCP server script")
    sys.exit(1)

# Run server without skip-daemon
cmd = [
    "python",
    server_script,
    "--debug",
    "--isolation",
    "--port", "8002",
    "--host", "localhost"
]

print(f"Starting MCP server using: {' '.join(cmd)}")
process = subprocess.Popen(cmd)

print("MCP server started with IPFS daemon support")
print("API URL: http://localhost:8002/api/v0/mcp")
print("Documentation: http://localhost:8002/docs")
print()
print("To access original MCP server (if still running):")
print("API URL: http://localhost:9990/api/v0/mcp")
print("Documentation: http://localhost:9990/docs")
"""
    
    script_path = "restart_mcp_with_daemons.py"
    with open(script_path, "w") as f:
        f.write(script_content)
    
    os.chmod(script_path, 0o755)  # Make executable
    
    logger.info(f"Created MCP server restart script at {script_path}")
    return script_path

def main():
    """Main function to start IPFS daemon."""
    print("Setting up IPFS daemon for MCP server...")
    
    # Clean stale lock files
    locks_cleaned = clean_lock_files()
    logger.info(f"Cleaned {locks_cleaned} stale lock files")
    
    # Start IPFS daemon
    if start_ipfs_daemon():
        logger.info("IPFS daemon is now running")
        
        # Create MCP server patch script
        script_path = patch_mcp_server()
        
        print("\n----------------------------------------------------------")
        print("IPFS daemon is running successfully!")
        print("----------------------------------------------------------")
        print(f"To start a new MCP server with daemon support, run: python {script_path}")
        print("This will start a new instance of the MCP server on port 8002")
        print("The existing server on port 9990 will continue to run")
        print("----------------------------------------------------------\n")
        
        # Verify IPFS by adding a test file
        try:
            test_result = subprocess.run(
                ["ipfs", "add", "-q", __file__],
                capture_output=True,
                text=True,
                check=False
            )
            if test_result.returncode == 0 and test_result.stdout.strip():
                print(f"IPFS test successful! Added file with CID: {test_result.stdout.strip()}")
            else:
                print("Warning: IPFS add test failed. Check daemon status.")
        except Exception as e:
            print(f"Warning: Error testing IPFS add: {e}")
    else:
        logger.error("Failed to start IPFS daemon")
        sys.exit(1)

if __name__ == "__main__":
    main()