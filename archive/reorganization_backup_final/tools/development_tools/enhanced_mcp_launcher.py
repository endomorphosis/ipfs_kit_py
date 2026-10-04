#!/usr/bin/env python3
"""
Enhanced MCP Server Launcher

This script starts an MCP server with enhanced parameter handling for IPFS
and multi-backend tools. It applies all necessary parameter fixes before 
starting the server and provides management capabilities.
"""

import os
import sys
import logging
import argparse
import importlib
import signal
import time
import subprocess
import socket
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("enhanced_mcp_launcher.log")
    ]
)
logger = logging.getLogger("enhanced-mcp-launcher")

# Constants
SERVER_PID_FILE = 'enhanced_mcp_server.pid'
SERVER_LOG_FILE = 'enhanced_mcp_server.log'


def is_port_available(port, host='127.0.0.1'):
    """Check if a port is available."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return True
        except socket.error:
            return False


def stop_existing_server(pid_file=SERVER_PID_FILE):
    """Stop any existing MCP server."""
    if os.path.exists(pid_file):
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            logger.info(f"Stopping existing MCP server with PID: {pid}")
            try:
                os.kill(pid, signal.SIGTERM)
                # Wait for process to terminate
                time.sleep(2)
            except ProcessLookupError:
                logger.info(f"Process {pid} not found, may have already terminated")
            except PermissionError:
                logger.error(f"Permission denied when trying to kill process {pid}")
            except Exception as e:
                logger.error(f"Error stopping process {pid}: {e}")
            
            # Remove PID file
            try:
                os.unlink(pid_file)
            except:
                pass
            
            # Check if port is now available
            if not is_port_available(9998):
                logger.warning("Port 9998 is still in use even after stopping the server")
                return False
            
            return True
        except Exception as e:
            logger.error(f"Error stopping server: {e}")
            return False
    else:
        logger.info("No PID file found, server may not be running")
        return True


def apply_parameter_fixes():
    """Apply parameter fixes to the MCP server tools."""
    logger.info("Applying parameter fixes to MCP server tools...")
    
    fixes_applied = []
    
    # Fix 1: Ensure enhanced parameter adapter is available
    try:
        from enhanced_parameter_adapter import ToolContext, adapt_parameters
        logger.info("✅ Enhanced parameter adapter is available")
        fixes_applied.append("enhanced_parameter_adapter")
    except ImportError:
        logger.error("❌ Enhanced parameter adapter not found")
        return False
    
    # Fix 2: Ensure IPFS tool adapters are available
    try:
        from ipfs_tool_adapters import get_tool_handler
        logger.info("✅ IPFS tool adapters are available")
        fixes_applied.append("ipfs_tool_adapters")
    except ImportError:
        logger.error("❌ IPFS tool adapters not found")
        return False
    
    # Fix 3: Check multi-backend tool adapters
    try:
        from enhanced.multi_backend_tool_adapters import get_tool_handler as get_mbfs_handler
        logger.info("✅ Multi-backend tool adapters are available")
        fixes_applied.append("multi_backend_tool_adapters")
    except ImportError:
        logger.warning("⚠️ Multi-backend tool adapters not found, will use fallback")
    
    # Fix 4: Apply direct parameter fixes
    try:
        import direct_param_fix
        logger.info("✅ Direct parameter fixes are available")
        fixes_applied.append("direct_param_fix")
    except ImportError:
        logger.warning("⚠️ Direct parameter fixes not found")
    
    # Fix 5: Check for tool parameter service
    try:
        import tool_parameter_service
        logger.info("✅ Tool parameter service is available")
        fixes_applied.append("tool_parameter_service")
    except ImportError:
        logger.warning("⚠️ Tool parameter service not found")
    
    logger.info(f"Applied {len(fixes_applied)} parameter fixes: {', '.join(fixes_applied)}")
    return len(fixes_applied) >= 2  # At least the adapter and one implementation


def start_server(host='0.0.0.0', port=9998, debug=False):
    """Start the MCP server with parameter fixes."""
    # Stop any existing server
    stop_existing_server()
    
    # Apply parameter fixes
    if not apply_parameter_fixes():
        logger.error("Failed to apply parameter fixes, aborting server start")
        return False
    
    # Prepare environment
    env = os.environ.copy()
    env['PYTHONPATH'] = os.getcwd() + ':' + env.get('PYTHONPATH', '')
    
    # Start the server
    logger.info(f"Starting enhanced MCP server on {host}:{port}...")
    
    try:
        # Use subprocess to start the server
        cmd = [
            sys.executable,
            "-u",  # Unbuffered output
            "final_mcp_server.py",
            "--host", host,
            "--port", str(port),
        ]
        
        if debug:
            cmd.append("--debug")
        
        # Start the server process
        with open(SERVER_LOG_FILE, 'w') as log_file:
            server_process = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                env=env,
                preexec_fn=os.setsid  # Create new process group
            )
        
        # Check if process started
        if server_process.poll() is None:
            # Write PID file
            with open(SERVER_PID_FILE, 'w') as f:
                f.write(str(server_process.pid))
            
            logger.info(f"MCP server started with PID: {server_process.pid}")
            logger.info(f"Log file: {SERVER_LOG_FILE}")
            
            # Wait a moment for server to initialize
            time.sleep(2)
            
            # Check if process is still running
            if server_process.poll() is None:
                logger.info("MCP server is running")
                return True
            else:
                logger.error(f"MCP server failed to start, exit code: {server_process.returncode}")
                with open(SERVER_LOG_FILE, 'r') as f:
                    logger.error(f"Server log: {f.read()}")
                return False
        else:
            logger.error(f"Failed to start MCP server, exit code: {server_process.returncode}")
            return False
    
    except Exception as e:
        logger.error(f"Error starting MCP server: {e}")
        return False


def is_server_running(pid_file=SERVER_PID_FILE):
    """Check if the MCP server is running."""
    if not os.path.exists(pid_file):
        return False
    
    try:
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())
        
        # Check if process exists
        try:
            os.kill(pid, 0)  # Signal 0 tests if process exists
            return True
        except ProcessLookupError:
            logger.info(f"Process {pid} not found")
            return False
        except PermissionError:
            logger.info(f"Process {pid} exists but permission denied")
            return True  # Process exists but we don't have permission to signal it
    except Exception as e:
        logger.error(f"Error checking server status: {e}")
        return False


def restart_server(host='0.0.0.0', port=9998, debug=False):
    """Restart the MCP server with parameter fixes."""
    logger.info("Restarting MCP server...")
    
    # Stop existing server
    stop_existing_server()
    
    # Start server
    return start_server(host, port, debug)


def register_enhanced_tools():
    """Register enhanced tools with the MCP server."""
    logger.info("Registering enhanced tools with the MCP server...")
    
    try:
        # Import the direct MCP server
        from final_mcp_server import server
        
        # Register IPFS tools with enhanced parameter handling
        try:
            from direct_param_fix import register_ipfs_tools
            logger.info("Registering IPFS tools with direct parameter handling...")
            register_ipfs_tools(server)
        except ImportError:
            logger.warning("Direct parameter fix not available, skipping IPFS tool registration")
        
        # Register multi-backend tools with enhanced parameter handling
        try:
            from register_enhanced_multi_backend_tools import register_multi_backend_tools
            logger.info("Registering multi-backend tools with enhanced parameter handling...")
            register_multi_backend_tools(server)
        except ImportError:
            logger.warning("Enhanced multi-backend tools not available, skipping registration")
        
        logger.info("Tool registration completed")
        return True
    
    except Exception as e:
        logger.error(f"Error registering enhanced tools: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def main():
    """Main function to parse arguments and start/stop the server."""
    parser = argparse.ArgumentParser(description="Enhanced MCP Server Launcher")
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=9998, help='Port to bind to')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--action', choices=['start', 'stop', 'restart', 'status'], 
                        default='start', help='Action to perform')
    
    args = parser.parse_args()
    
    if args.action == 'start':
        if is_server_running():
            logger.info("MCP server is already running")
            return 0
        
        if start_server(args.host, args.port, args.debug):
            logger.info("MCP server started successfully")
            return 0
        else:
            logger.error("Failed to start MCP server")
            return 1
    
    elif args.action == 'stop':
        if stop_existing_server():
            logger.info("MCP server stopped successfully")
            return 0
        else:
            logger.error("Failed to stop MCP server")
            return 1
    
    elif args.action == 'restart':
        if restart_server(args.host, args.port, args.debug):
            logger.info("MCP server restarted successfully")
            return 0
        else:
            logger.error("Failed to restart MCP server")
            return 1
    
    elif args.action == 'status':
        if is_server_running():
            logger.info("MCP server is running")
            
            # Try to get additional status info
            try:
                with open(SERVER_PID_FILE, 'r') as f:
                    pid = int(f.read().strip())
                logger.info(f"Server PID: {pid}")
            except:
                pass
            
            return 0
        else:
            logger.info("MCP server is not running")
            return 0


if __name__ == "__main__":
    sys.exit(main())
