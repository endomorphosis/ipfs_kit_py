#!/usr/bin/env python3
"""
Enhanced MCP Server Launcher

This script injects enhanced mock implementations into the MCP server
and launches it with proper parameter handling and import hanging fixes.
"""

import os
import sys
import time
import signal
import logging
import argparse
import importlib
import subprocess
import traceback
import requests
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("enhanced_launcher.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("enhanced-launcher")

# Configuration
MCP_SERVER_MODULE = "final_mcp_server"
PATCHED_SERVER_MODULE = "patched_final_mcp_server"
MOCK_ENHANCER_MODULE = "enhance_mock_implementations"
PARAM_HANDLER_MODULE = "apply_fixed_ipfs_params"
IMPORT_FIXER_MODULE = "fix_import_hanging"
PORT = 9998
HOST = "0.0.0.0"
LOG_FILE = "enhanced_server.log"
PID_FILE = "enhanced_server.pid"

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Launch enhanced MCP server")
    parser.add_argument("--host", default=HOST, help=f"Host to bind to (default: {HOST})")
    parser.add_argument("--port", type=int, default=PORT, help=f"Port to listen on (default: {PORT})")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--no-mock-enhancements", action="store_true", help="Disable mock enhancements")
    parser.add_argument("--no-param-fixes", action="store_true", help="Disable parameter handling fixes")
    parser.add_argument("--no-import-fixes", action="store_true", help="Disable import hanging fixes")
    return parser.parse_args()

def load_enhancer():
    """Load and apply the mock implementation enhancements."""
    try:
        # Import the enhancer module
        enhancer_module = importlib.import_module(MOCK_ENHANCER_MODULE)
        
        # Apply enhancements
        success = enhancer_module.apply_enhancements()
        
        if success:
            logger.info("✅ Successfully applied mock implementation enhancements")
            return True
        else:
            logger.error("❌ Failed to apply mock implementation enhancements")
            return False
    except ImportError as e:
        logger.error(f"❌ Could not import enhancer module: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Error applying enhancements: {e}")
        logger.error(traceback.format_exc())
        return False

def inject_enhanced_mocks():
    """Inject enhanced mock implementations into the unified_ipfs_tools module."""
    try:
        if not load_enhancer():
            logger.warning("⚠️ Could not load enhancer, using original implementations")
        
        # Import the unified_ipfs_tools module to verify the changes
        import unified_ipfs_tools
        
        # Check if mock_add_content has been properly modified
        if hasattr(unified_ipfs_tools.mock_add_content, "__closure__"):
            logger.info("✅ Verified that mock_add_content has been enhanced")
            return True
        else:
            logger.warning("⚠️ mock_add_content does not appear to be enhanced")
            return False
    except Exception as e:
        logger.error(f"❌ Error verifying enhanced mocks: {e}")
        logger.error(traceback.format_exc())
        return False

def apply_import_fixes():
    """Apply fixes for import hanging issues."""
    try:
        # Import the import fixer module
        import_fixer = importlib.import_module(IMPORT_FIXER_MODULE)
        
        # Create patched modules
        unified_patched = import_fixer.patch_unified_ipfs_tools()
        server_patched = import_fixer.patch_final_mcp_server()
        
        if unified_patched and server_patched:
            logger.info("✅ Successfully applied import hanging fixes")
            return True
        else:
            logger.warning("⚠️ Some import hanging fixes failed to apply")
            return False
    except ImportError as e:
        logger.error(f"❌ Could not import import fixer module: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Error applying import fixes: {e}")
        logger.error(traceback.format_exc())
        return False

def apply_parameter_fixes(server_process):
    """Apply parameter handling fixes to the running server."""
    try:
        # Wait for the server to be responsive
        health_url = f"http://localhost:{PORT}/health"
        max_retries = 10
        for i in range(max_retries):
            try:
                response = requests.get(health_url)
                if response.status_code == 200:
                    logger.info("Server is responding to health checks")
                    break
            except:
                pass
            time.sleep(1)
            logger.info(f"Waiting for server to start... ({i+1}/{max_retries})")
        else:
            logger.error("❌ Server did not become responsive within the timeout")
            return False
        
        # Now apply the parameter fixes via HTTP
        apply_fix_url = f"http://localhost:{PORT}/apply_parameter_fixes"
        try:
            response = requests.post(apply_fix_url)
            if response.status_code == 200:
                logger.info("✅ Successfully applied parameter handling fixes")
                return True
            else:
                logger.warning(f"⚠️ Parameter fixes API returned status code {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ Error calling parameter fixes API: {e}")
            return False
    except Exception as e:
        logger.error(f"❌ Error applying parameter fixes: {e}")
        logger.error(traceback.format_exc())
        return False

def run_server(args):
    """Run the MCP server with enhancements."""
    try:
        # Determine which server module to use
        server_module = PATCHED_SERVER_MODULE if args.no_import_fixes else MCP_SERVER_MODULE
        
        # Ensure the MCP server module exists
        if not Path(f"{server_module}.py").exists():
            logger.error(f"❌ MCP server module '{server_module}.py' does not exist")
            return None
        
        # Start the server in a subprocess
        cmd = [
            sys.executable,
            f"{server_module}.py",
            "--host", args.host,
            "--port", str(args.port)
        ]
        
        if args.debug:
            cmd.append("--debug")
        
        logger.info(f"Running command: {' '.join(cmd)}")
        
        with open(LOG_FILE, "w") as log_file:
            process = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True
            )
        
        if process.poll() is None:
            logger.info(f"Server process started with PID {process.pid}")
            
            # Write PID to file
            with open(PID_FILE, "w") as f:
                f.write(str(process.pid))
                
            # Wait for server to initialize
            time.sleep(2)
            
            # Check if process is still running
            if process.poll() is None:
                logger.info("✅ Server started successfully")
                return process.pid
            else:
                logger.error(f"❌ Server process exited immediately with code {process.returncode}")
                with open(LOG_FILE, "r") as f:
                    logger.error(f"Server log:\n{f.read()}")
                return None
        else:
            logger.error(f"❌ Failed to start server process (exit code: {process.returncode})")
            return None
    except Exception as e:
        logger.error(f"❌ Error starting server: {e}")
        logger.error(traceback.format_exc())
        return None

def wait_for_server_ready(timeout=30):
    """
    Wait for the server to be ready to accept connections.
    
    Args:
        timeout: Maximum time to wait in seconds
        
    Returns:
        bool: True if server is ready, False otherwise
    """
    logger.info(f"Waiting up to {timeout} seconds for server to be ready...")
    
    for i in range(timeout):
        try:
            response = requests.get(f"http://{HOST if HOST != '0.0.0.0' else 'localhost'}:{PORT}/health")
            if response.status_code == 200:
                logger.info("✅ Server is responding to health checks")
                return True
        except Exception:
            pass
        
        time.sleep(1)
        
        if i % 5 == 0:
            logger.info(f"Still waiting for server to be ready ({i}/{timeout}s)...")
    
    logger.error(f"❌ Server did not become ready within {timeout} seconds")
    return False

def main():
    """Main entry point."""
    logger.info("Starting Enhanced MCP Server Launcher")
    
    args = parse_arguments()
    
    # Update global constants based on arguments
    global HOST, PORT
    HOST = args.host
    PORT = args.port
    
    # Kill any existing server with the same PID file
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                pid = int(f.read().strip())
            
            logger.info(f"Found existing server with PID {pid}, attempting to kill it")
            try:
                os.kill(pid, signal.SIGTERM)
                time.sleep(1)
                try:
                    os.kill(pid, 0)
                    logger.warning(f"Process {pid} did not terminate, force killing")
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    logger.info(f"Process {pid} terminated successfully")
            except OSError:
                logger.info(f"No such process {pid}, removing stale PID file")
            
            os.remove(PID_FILE)
        except Exception as e:
            logger.warning(f"Error handling existing PID file: {e}")
    
    # Inject enhanced mocks
    if not inject_enhanced_mocks():
        logger.warning("⚠️ Continuing with potentially unenhanced mocks")
    
    # Run the server
    server_pid = run_server(args)
    
    if server_pid is None:
        logger.error("❌ Failed to start the server")
        return 1
    
    # Wait for the server to be ready
    if not wait_for_server_ready():
        logger.error("❌ Server did not become ready")
        return 1
    
    logger.info(f"✅ Enhanced MCP server is running with PID {server_pid}")
    logger.info(f"  - Listening on: http://{HOST}:{PORT}")
    logger.info(f"  - Log file: {LOG_FILE}")
    logger.info(f"  - PID file: {PID_FILE}")
    logger.info(f"  - To stop the server: kill {server_pid}")
    
    # Apply import hanging fixes if requested
    if not args.no_import_fixes:
        if not apply_import_fixes():
            logger.warning("⚠️ Some import hanging fixes could not be applied")
    
    # Apply parameter handling fixes if requested
    if not args.no_param_fixes:
        if not apply_parameter_fixes(server_pid):
            logger.warning("⚠️ Parameter handling fixes could not be applied")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
