#!/usr/bin/env python3
"""
Direct MCP server implementation using FastMCP and Starlette.
This version includes blue/green deployment capabilities.
It relies on the standard FastMCP SSE handling.
"""

__version__ = "0.1.0"

import os
import sys
import logging
import json
import tempfile
import asyncio
import signal
import shutil
import py_compile
import subprocess
import time
import uuid
import threading
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
import fnmatch
from ipfs_mcp_tools_integration import register_ipfs_tools
# FS Journal and IPFS Bridge integration
import ipfs_mcp_fs_integration
from register_all_backend_tools import register_all_tools
# Store global port
global PORT
# --- Global Variables ---
PORT = 3000  # Default port, will be overridden by args.port in main

# --- Early Setup: Logging and Path ---

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("direct-mcp")

# Add a file handler for more persistent logging
try:
    file_handler = logging.FileHandler('direct_mcp_server.log')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(file_handler)
    logger.info("File logging initialized to direct_mcp_server.log")
except Exception as e:
    logger.warning("Could not set up file logging: %s", e)

# Add MCP SDK path
cwd = os.getcwd()
sdk_path = os.path.abspath(os.path.join(cwd, "docs/mcp-python-sdk/src"))
sdk_added_to_path = False
if os.path.isdir(sdk_path):
    if sdk_path not in sys.path:
        sys.path.insert(0, sdk_path)
        logger.info("Added SDK path: %s", sdk_path)
        sdk_added_to_path = True
    else:
        logger.info("SDK path already in sys.path: %s", sdk_path)
        sdk_added_to_path = True
else:
     logger.warning("MCP SDK path not found: %s. MCP features might fail.", sdk_path)

# --- Import Modules (AFTER adding SDK path) ---
imports_succeeded = False
try:
    import uvicorn
    from mcp.server.fastmcp import FastMCP, Context
    from starlette.applications import Starlette
    from starlette.routing import Route
    from starlette.responses import JSONResponse, StreamingResponse, Response
    from starlette.middleware.cors import CORSMiddleware
    from starlette.requests import Request
    from mcp import types as mcp_types
    import json
    # Import JSON-RPC libraries
    # Import removed: # Import removed: # Import removed: # Import removed: # Import removed: from jsonrpc.dispatcher import Dispatcher
    # Import removed: # Import removed: # Import removed: # Import removed: # Import removed: from jsonrpc.exceptions import JSONRPCDispatchException 
    imports_succeeded = True
    logger.info("Successfully imported MCP and Starlette modules.")
except ImportError as e:
    logger.error("Failed to import required MCP/Starlette modules even after adding SDK path: %s", e)
    # Exit if core imports fail
    sys.exit(1)

# --- Blue/Green Deployment Configuration ---
DEPLOYMENT_CONFIG = {
    "blue_pid_file": "direct_mcp_server_blue.pid",
    "green_pid_file": "direct_mcp_server_green.pid",
    "active_version_file": "direct_mcp_server_active.txt",
    "blue_port": 8000,
    "green_port": 8001,
    "test_suite": [], # Removed non-existent test files
    "max_deployment_time": 300,  # 5 minutes max for deployment process
    "health_check_interval": 5,  # Check health every 5 seconds during rollout
}

# Deployment status
is_blue = True  # Default to blue instance
server_color = "blue"
deployment_in_progress = False
deployment_status = {"status": "idle", "details": None, "start_time": None}

# Read the active version file if it exists
try:
    if os.path.exists(DEPLOYMENT_CONFIG["active_version_file"]):
        with open(DEPLOYMENT_CONFIG["active_version_file"], "r", encoding="utf-8") as f:
            active_version = f.read().strip()
            if active_version == "green":
                is_blue = False
                server_color = "green"
                logger.info("Starting as GREEN instance based on active version file")
            else:
                logger.info("Starting as BLUE instance based on active version file")
    else:
        # Create the active version file if it doesn't exist
        with open(DEPLOYMENT_CONFIG["active_version_file"], "w", encoding="utf-8") as f:
            f.write("blue")
        logger.info("Created active version file, starting as BLUE instance")
except OSError as e:
    logger.warning("Error reading/writing active version file: %s. Defaulting to BLUE.", e)

# Write PID file for this instance
current_pid_file = DEPLOYMENT_CONFIG["blue_pid_file"] if is_blue else DEPLOYMENT_CONFIG["green_pid_file"]
try:
    with open(current_pid_file, "w") as f:
        f.write(str(os.getpid()))
    logger.info("Wrote PID %s to %s", os.getpid(), current_pid_file)
except Exception as e:
    logger.error("Failed to write PID file %s: %s", current_pid_file, e)

# Create FastMCP server
server = FastMCP(
    name=f"direct-mcp-server-{server_color}",
    instructions="Server with blue/green deployment and live patching capabilities",
)


# Register all IPFS tools and backend integrations
logger.info("Registering all IPFS, FS Journal, and Multi-Backend tools...")
register_all_tools(server)
logger.info("✅ Tool registration complete")





# Server initialization state 
server_initialized = False
initialization_lock = asyncio.Lock()
initialization_event = asyncio.Event()

# --- Utility Functions ---
def _cleanup_temp_files(*paths):
    """Safely remove temporary files."""
    for path in paths:
        if path and os.path.exists(path):
            try:
                os.remove(path)
                logger.debug("Cleaned up temporary file: %s", path)
            except OSError as e:
                logger.error("Error removing temporary file %s: %s", path, e)

async def delayed_shutdown(pid: int, delay: float):
    """Waits for a delay then sends SIGTERM."""
    await asyncio.sleep(delay)
    logger.info("Sending SIGTERM to process %s after %ss delay.", pid, delay)
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        logger.warning("Process %s not found for shutdown signal.", pid)
    except Exception as e:
        logger.error("Error sending SIGTERM to process %s: %s", pid, e)

def get_other_instance_pid():
    """Get the PID of the other instance (blue if we're green, green if we're blue)."""
    other_pid_file = DEPLOYMENT_CONFIG["green_pid_file"] if is_blue else DEPLOYMENT_CONFIG["blue_pid_file"]
    try:
        if os.path.exists(other_pid_file):
            with open(other_pid_file, "r") as f:
                return int(f.read().strip())
    except Exception as e:
        logger.error("Error reading other instance PID file: %s", e)
    return None

def is_process_running(pid):
    """Check if a process with the given PID is running."""
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False
    except Exception:
        return False

def run_syntax_check(file_path):
    """Run syntax check on the given Python file."""
    try:
        py_compile.compile(file_path, doraise=True)
        return True, None
    except py_compile.PyCompileError as e:
        return False, str(e)
    except Exception as e:
        return False, str(e)

def run_pytest(test_paths=None):
    """Run pytest on specific test paths or all tests."""
    try:
        cmd = ["pytest", "-xvs"]
        if test_paths:
            cmd.extend(test_paths)
        
        result = subprocess.run(
            cmd,
            cwd=os.getcwd(),
            capture_output=True,
            text=True,
            timeout=120
        )
        return result.returncode == 0, f"Output:\n{result.stdout}\n{result.stderr}"
    except Exception as e:
        return False, str(e)

async def start_other_instance(port):
    """Start the other instance of the server."""
    script_path = os.path.abspath(__file__)
    cmd = [sys.executable, script_path]
    env = os.environ.copy()
    env["PORT"] = str(port)
    
    try:
        process = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        logger.info("Started other instance with PID %s on port %s", process.pid, port)
        return process.pid
    except Exception as e:
        logger.error("Failed to start other instance: %s", e)
        return None

async def perform_health_check(port):
    """Check if the server on the given port is healthy."""
    url = f"http://localhost:{port}/"
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5) as response:
                if response.status == 200:
                    return True, await response.text()
                else:
                    return False, f"HTTP {response.status}"
    except Exception as e:
        return False, str(e)

async def switch_active_version(new_color):
    """Switch the active version to the given color."""
    try:
        with open(DEPLOYMENT_CONFIG["active_version_file"], "w") as f:
            f.write(new_color)
        logger.info("Switched active version to %s", new_color)
        return True
    except Exception as e:
        logger.error("Failed to switch active version: %s", e)
        return False

async def perform_blue_green_deployment(modified_file=None):
    """
    Perform a blue/green deployment.
    
    1. Start the inactive instance
    2. Run health checks on the new instance
    3. If healthy, switch the active version
    4. Shutdown the old instance
    """
    global deployment_in_progress, deployment_status
    
    if deployment_in_progress:
        logger.warning("Deployment already in progress, cannot start another")
        return {"success": False, "message": "Deployment already in progress"}
    
    deployment_in_progress = True
    deployment_status = {
        "status": "starting",
        "details": f"Starting deployment of {modified_file if modified_file else 'server'}",
        "start_time": time.time()
    }
    
    # Determine the target color and port
    target_color = "green" if is_blue else "blue"
    target_port = DEPLOYMENT_CONFIG["green_port"] if is_blue else DEPLOYMENT_CONFIG["blue_port"]
    
    logger.info("Starting blue/green deployment from %s to %s", server_color, target_color)
    deployment_status["status"] = "testing"
    
    try:
        # Run tests before starting the new instance
        if modified_file and modified_file.endswith(".py"):
            syntax_ok, syntax_output = run_syntax_check(modified_file)
            if not syntax_ok:
                deployment_status = {
                    "status": "failed",
                    "details": f"Syntax check failed: {syntax_output}",
                    "start_time": deployment_status["start_time"]
                }
                logger.error("Syntax check failed for %s: %s", modified_file, syntax_output)
                deployment_in_progress = False
                return {"success": False, "message": f"Syntax check failed: {syntax_output}"}
            
            # Run specific test suite if defined
            if DEPLOYMENT_CONFIG["test_suite"]:
                pytest_ok, pytest_output = run_pytest(DEPLOYMENT_CONFIG["test_suite"])
                if not pytest_ok:
                    deployment_status = {
                        "status": "failed",
                        "details": f"Tests failed: {pytest_output[:500]}...",
                        "start_time": deployment_status["start_time"]
                    }
                    logger.error("Tests failed for %s", modified_file)
                    deployment_in_progress = False
                    return {"success": False, "message": f"Tests failed: {pytest_output[:500]}..."}
        
        # Start the new instance
        deployment_status["status"] = "starting_instance"
        pid = await start_other_instance(target_port)
        if not pid:
            deployment_status = {
                "status": "failed",
                "details": "Failed to start new instance",
                "start_time": deployment_status["start_time"]
            }
            deployment_in_progress = False
            return {"success": False, "message": "Failed to start new instance"}
        
        # Wait for the new instance to start and perform health checks
        deployment_status["status"] = "health_checks"
        max_attempts = 10
        for i in range(max_attempts):
            logger.info("Performing health check %s/%s on port %s", i+1, max_attempts, target_port)
            health_ok, health_output = await perform_health_check(target_port)
            if health_ok:
                break
            if i == max_attempts - 1:
                deployment_status = {
                    "status": "failed",
                    "details": f"Health checks failed: {health_output}",
                    "start_time": deployment_status["start_time"]
                }
                deployment_in_progress = False
                return {"success": False, "message": f"Health checks failed: {health_output}"}
            await asyncio.sleep(DEPLOYMENT_CONFIG["health_check_interval"])
        
        # Switch the active version
        deployment_status["status"] = "switching"
        switch_ok = await switch_active_version(target_color)
        if not switch_ok:
            deployment_status = {
                "status": "failed",
                "details": "Failed to switch active version",
                "start_time": deployment_status["start_time"]
            }
            deployment_in_progress = False
            return {"success": False, "message": "Failed to switch active version"}
        
        # Shutdown this instance
        deployment_status["status"] = "completing"
        logger.info("Deployment completed successfully. Shutting down %s instance.", server_color)
        asyncio.create_task(delayed_shutdown(os.getpid(), 3))
        
        deployment_status = {
            "status": "succeeded",
            "details": f"Deployment completed successfully. Switched from {server_color} to {target_color}.",
            "start_time": deployment_status["start_time"],
            "end_time": time.time()
        }
        
        return {
            "success": True, 
            "message": f"Deployment completed successfully. Switched from {server_color} to {target_color}."
        }
        
    except Exception as e:
        logger.error("Deployment error: %s", e)
        deployment_status = {
            "status": "failed",
            "details": f"Deployment error: {str(e)}",
            "start_time": deployment_status["start_time"]
        }
        deployment_in_progress = False
        return {"success": False, "message": f"Deployment error: {str(e)}"}

# --- MCP Tools (Define only if imports succeeded) ---
if imports_succeeded:
    @server.tool(name="list_files", description="Lists files and directories with detailed information")
    async def list_files(ctx: Context, directory: str = ".", recursive: bool = False, 
                        include_hidden: bool = False, filter_pattern: str = None) -> Dict[str, Any]:
        """
        Lists files and directories with detailed information.
        
        Args:
            ctx: The MCP context
            directory: Relative path to the directory to list
            recursive: If True, list files recursively in subdirectories
            include_hidden: If True, include hidden files (starting with .)
            filter_pattern: Optional glob pattern to filter files (e.g., "*.py")
            
        Returns:
            A dictionary containing file listing information and statistics
        """
        logger.info("Received request to list files in %s (recursive=%s, include_hidden=%s, filter_pattern=%s)", directory, recursive, include_hidden, filter_pattern)
        await ctx.info(f"Listing files in {directory}")
        
        project_root = os.getcwd()
        absolute_dir = os.path.abspath(os.path.join(project_root, directory))
        
        # Security check to prevent directory traversal
        if not absolute_dir.startswith(project_root):
            error_msg = f"Error: Directory path '{directory}' is outside the allowed project directory."
            logger.error(error_msg)
            await ctx.error(error_msg)
            return {"error": error_msg}
            
        # Check if directory exists
        if not os.path.exists(absolute_dir):
            error_msg = f"Error: Directory '{directory}' does not exist."
            logger.error(error_msg)
            await ctx.error(error_msg)
            return {"error": error_msg}
            
        if not os.path.isdir(absolute_dir):
            error_msg = f"Error: Path '{directory}' is not a directory."
            logger.error(error_msg)
            await ctx.error(error_msg)
            return {"error": error_msg}
        
        try:
            result = {
                "base_directory": directory,
                "items": [],
                "statistics": {
                    "total_files": 0,
                    "total_directories": 0,
                    "total_size_bytes": 0,
                    "extensions": {}
                }
            }
            
            # Function to process a file or directory
            def process_item(path, rel_path):
                is_directory = os.path.isdir(path)
                item = {
                    "name": os.path.basename(path),
                    "path": rel_path,
                    "is_directory": is_directory,
                }
                
                # Skip hidden files if not include_hidden
                if not include_hidden and os.path.basename(path).startswith('.'):
                    return None
                    
                # Apply filter pattern if specified
                if filter_pattern and not is_directory:
                    if not fnmatch.fnmatch(os.path.basename(path), filter_pattern):
                        return None
                
                if is_directory:
                    result["statistics"]["total_directories"] += 1
                    item["item_count"] = len(os.listdir(path))
                else:
                    result["statistics"]["total_files"] += 1
                    size = os.path.getsize(path)
                    result["statistics"]["total_size_bytes"] += size
                    item["size_bytes"] = size
                    
                    # Add file modification time
                    mtime = os.path.getmtime(path)
                    item["modified_time"] = datetime.fromtimestamp(mtime).isoformat()
                    
                    # Track extension statistics
                    _, ext = os.path.splitext(path)
                    if ext:
                        ext = ext.lower()
                        if ext not in result["statistics"]["extensions"]:
                            result["statistics"]["extensions"][ext] = {
                                "count": 0,
                                "total_size": 0
                            }
                        result["statistics"]["extensions"][ext]["count"] += 1
                        result["statistics"]["extensions"][ext]["total_size"] += size
                    
                    # Try to detect if binary file
                    try:
                        if size > 0:
                            with open(path, 'rb') as f:
                                # Read first 1024 bytes or entire file if smaller
                                sample = f.read(min(1024, size))
                                # Check for null bytes or high ratio of non-printable chars
                                null_count = sample.count(0)
                                binary_threshold = 0.3  # 30% binary characters threshold
                                is_likely_binary = null_count / len(sample) > 0.01 if sample else False
                                item["is_binary"] = is_likely_binary
                    except Exception as e:
                        logger.warning("Error checking if file is binary: %s", str(e))
                        item["is_binary"] = None
                
                return item
                
            # Walk directory and collect information
            if recursive:
                for root, dirs, files in os.walk(absolute_dir):
                    # Calculate relative path from project root
                    rel_root = os.path.relpath(root, project_root)
                    
                    # Process directories
                    for d in dirs:
                        item = process_item(os.path.join(root, d), os.path.join(rel_root, d))
                        if item:
                            result["items"].append(item)
                    
                    # Process files
                    for f in files:
                        item = process_item(os.path.join(root, f), os.path.join(rel_root, f))
                        if item:
                            result["items"].append(item)
            else:
                # Only list items in the specified directory
                for item_name in os.listdir(absolute_dir):
                    item_path = os.path.join(absolute_dir, item_name)
                    rel_path = os.path.relpath(item_path, project_root)
                    item = process_item(item_path, rel_path)
                    if item:
                        result["items"].append(item)
            
            # Sort items alphabetically, directories first
            result["items"].sort(key=lambda x: (not x["is_directory"], x["name"].lower()))
            
            # Calculate human-readable size
            total_size = result["statistics"]["total_size_bytes"]
            size_units = ["B", "KB", "MB", "GB", "TB"]
            size_index = 0
            while total_size > 1024 and size_index < len(size_units) - 1:
                total_size /= 1024
                size_index += 1
                
            result["statistics"]["human_readable_size"] = f"{total_size:.2f} {size_units[size_index]}"
            
            # Format the extensions in a more readable way
            for ext in result["statistics"]["extensions"]:
                ext_data = result["statistics"]["extensions"][ext]
                ext_size = ext_data["total_size"]
                ext_size_index = 0
                while ext_size > 1024 and ext_size_index < len(size_units) - 1:
                    ext_size /= 1024
                    ext_size_index += 1
                ext_data["human_readable_size"] = f"{ext_size:.2f} {size_units[ext_size_index]}"
            
            await ctx.info(f"Found {result['statistics']['total_files']} files and {result['statistics']['total_directories']} directories in {directory}")
            logger.info("Successfully listed files in %s with %s files", directory, result['statistics']['total_files'])
            return result
            
        except Exception as e:
            error_msg = f"Error listing files in '{directory}': {str(e)}"
            logger.error(error_msg, exc_info=True)
            await ctx.error(error_msg)
            return {"error": error_msg}

    @server.tool(name="file_exists", description="Check if a file or directory exists")
    async def file_exists(ctx: Context, path: str) -> Dict[str, Any]:
        """
        Checks if a file or directory exists.
        
        Args:
            ctx: The MCP context
            path: Path to check (relative to project root)
            
        Returns:
            A dictionary containing existence information
        """
        project_root = os.getcwd()
        abs_path = os.path.abspath(os.path.join(project_root, path))
        
        logger.info("Received request to check if path %s exists", path)
        await ctx.info(f"Checking if {path} exists")
        
        # Security check to prevent directory traversal
        if not abs_path.startswith(project_root):
            error_msg = f"Error: Path must be within the project directory."
            logger.error(error_msg)
            await ctx.error(error_msg)
            return {"error": error_msg}
            
        try:
            exists = os.path.exists(abs_path)
            is_dir = os.path.isdir(abs_path) if exists else False
            is_file = os.path.isfile(abs_path) if exists else False
            is_symlink = os.path.islink(abs_path) if exists else False
            
            result = {
                "path": path,
                "exists": exists,
                "is_directory": is_dir,
                "is_file": is_file,
                "is_symlink": is_symlink
            }
            
            # Add additional information if file exists
            if exists:
                if is_file:
                    result["size_bytes"] = os.path.getsize(abs_path)
                    result["size_human"] = f"{result['size_bytes'] / 1024:.1f} KB" if result['size_bytes'] < 1024 * 1024 else f"{result['size_bytes'] / (1024 * 1024):.1f} MB"
                elif is_dir:
                    result["is_empty"] = not bool(os.listdir(abs_path))
                
                result["modified_time"] = datetime.fromtimestamp(os.path.getmtime(abs_path)).isoformat()
                
            await ctx.info(f"Path {path} {'exists' if exists else 'does not exist'}" + 
                          (f" (is a {'directory' if is_dir else 'file'})" if exists else ""))
            logger.info("Checked existence for %s: %s", path, exists)
            return result
            
        except Exception as e:
            error_msg = f"Error checking existence of '{path}': {str(e)}"
            logger.error(error_msg, exc_info=True)
            await ctx.error(error_msg)
            return {"error": error_msg}

    @server.tool(name="get_file_stats", description="Get detailed statistics about a file or directory")
    async def get_file_stats(ctx: Context, path: str) -> Dict[str, Any]:
        """
        Gets detailed statistics about a file or directory.
        
        Args:
            ctx: The MCP context
            path: Path to the file or directory (relative to project root)
            
        Returns:
            A dictionary containing comprehensive file or directory statistics
        """
        project_root = os.getcwd()
        abs_path = os.path.abspath(os.path.join(project_root, path))
        
        logger.info("Received request to get stats for %s", path)
        await ctx.info(f"Getting statistics for {path}")
        
        # Security check to prevent directory traversal
        if not abs_path.startswith(project_root):
            error_msg = f"Error: Path must be within the project directory."
            logger.error(error_msg)
            await ctx.error(error_msg)
            return {"error": error_msg}
            
        if not os.path.exists(abs_path):
            error_msg = f"Error: Path '{path}' does not exist."
            logger.error(error_msg)
            await ctx.error(error_msg)
            return {"error": error_msg}
            
        try:
            stats = os.stat(abs_path)
            is_dir = os.path.isdir(abs_path)
            
            result = {
                "path": path,
                "absolute_path": abs_path,
                "exists": True,
                "is_directory": is_dir,
                "is_file": os.path.isfile(abs_path),
                "is_symlink": os.path.islink(abs_path),
                "size_bytes": stats.st_size,
                "mode_octal": f"{stats.st_mode & 0o777:o}",  # Permission bits in octal
                "uid": stats.st_uid,
                "gid": stats.st_gid,
                "access_time": datetime.fromtimestamp(stats.st_atime).isoformat(),
                "modify_time": datetime.fromtimestamp(stats.st_mtime).isoformat(),
                "create_time": datetime.fromtimestamp(stats.st_ctime).isoformat()
            }
            
            # Format size in human-readable form
            size = stats.st_size
            size_units = ["B", "KB", "MB", "GB", "TB"]
            size_index = 0
            while size > 1024 and size_index < len(size_units) - 1:
                size /= 1024
                size_index += 1
            result["size_human"] = f"{size:.2f} {size_units[size_index]}"
            
            # Add file extension and type detection for files
            if not is_dir:
                _, ext = os.path.splitext(abs_path)
                result["extension"] = ext.lower() if ext else ""
                
                # Try to detect file type
                try:
                    import magic
                    result["mime_type"] = magic.from_file(abs_path, mime=True)
                except ImportError:
                    # Fallback to basic binary detection if python-magic isn't installed
                    if stats.st_size > 0:
                        with open(abs_path, 'rb') as f:
                            sample = f.read(min(1024, stats.st_size))
                            null_count = sample.count(0)
                            result["is_binary"] = null_count > 0
                            if null_count > 0:
                                result["binary_hint"] = "Contains null bytes"
            
            # Add directory-specific information
            if is_dir:
                contents = os.listdir(abs_path)
                result["item_count"] = len(contents)
                result["file_count"] = len([i for i in contents if os.path.isfile(os.path.join(abs_path, i))])
                result["dir_count"] = len([i for i in contents if os.path.isdir(os.path.join(abs_path, i))])
                result["is_empty"] = len(contents) == 0
                
                # For small directories, include item list
                if len(contents) <= 100:
                    result["contents"] = contents
            
            # Get owner/group names if possible
            try:
                import pwd
                import grp
                result["owner"] = pwd.getpwuid(stats.st_uid).pw_name
                result["group"] = grp.getgrgid(stats.st_gid).gr_name
            except ImportError:
                # Skip if the modules aren't available (Windows)
                result["owner"] = str(stats.st_uid)
                result["group"] = str(stats.st_gid)
            except KeyError:
                # Skip if the UID/GID doesn't exist
                result["owner"] = str(stats.st_uid)
                result["group"] = str(stats.st_gid)
            
            await ctx.info(f"Retrieved statistics for {path}")
            logger.info("Successfully got file stats for %s", path)
            return result
            
        except Exception as e:
            error_msg = f"Error getting statistics for '{path}': {str(e)}"
            logger.error(error_msg, exc_info=True)
            await ctx.error(error_msg)
            return {"error": error_msg}

    @server.tool(name="copy_file", description="Copy a file from one location to another")
    async def copy_file(ctx: Context, source_path: str, destination_path: str, 
                      overwrite: bool = False) -> Dict[str, Any]:
        """
        Copies a file from source path to destination path.
        
        Args:
            ctx: The MCP context
            source_path: Path to the source file (relative to project root)
            destination_path: Path to the destination file (relative to project root)
            overwrite: If True, overwrite the destination file if it exists
            
        Returns:
            A dictionary containing operation status and information
        """
        project_root = os.getcwd()
        abs_source = os.path.abspath(os.path.join(project_root, source_path))
        abs_destination = os.path.abspath(os.path.join(project_root, destination_path))
        
        logger.info("Received request to copy file from %s to %s (overwrite=%s)", source_path, destination_path, overwrite)
        await ctx.info(f"Copying file from {source_path} to {destination_path}")
        
        # Security check to prevent directory traversal
        if not abs_source.startswith(project_root):
            error_msg = f"Error: Source path must be within the project directory."
            logger.error(error_msg)
            await ctx.error(error_msg)
            return {"error": error_msg}
            
        if not abs_destination.startswith(project_root):
            error_msg = f"Error: Destination path must be within the project directory."
            logger.error(error_msg)
            await ctx.error(error_msg)
            return {"error": error_msg}
            
        if not os.path.exists(abs_source):
            error_msg = f"Error: Source file '{source_path}' does not exist."
            logger.error(error_msg)
            await ctx.error(error_msg)
            return {"error": error_msg}
            
        if not os.path.isfile(abs_source):
            error_msg = f"Error: Source path '{source_path}' is not a file."
            logger.error(error_msg)
            await ctx.error(error_msg)
            return {"error": error_msg}
            
        if os.path.exists(abs_destination) and not overwrite:
            error_msg = f"Error: Destination file '{destination_path}' already exists and overwrite is False."
            logger.error(error_msg)
            await ctx.error(error_msg)
            return {"error": error_msg}
            
        # Create destination directory if it doesn't exist
        dest_dir = os.path.dirname(abs_destination)
        if dest_dir and not os.path.exists(dest_dir):
            try:
                os.makedirs(dest_dir, exist_ok=True)
                logger.info("Created destination directory: %s", dest_dir)
            except Exception as e:
                error_msg = f"Error creating destination directory: {str(e)}"
                logger.error(error_msg)
                return {"error": error_msg}
                
        try:
            # Copy the file
            shutil.copy2(abs_source, abs_destination)
            
            # Get file size and other stats
            file_size = os.path.getsize(abs_destination)
            file_stats = os.stat(abs_destination)
            
            result = {
                "success": True,
                "source_path": source_path,
                "destination_path": destination_path,
                "size_bytes": file_size,
                "size_human": f"{file_size / 1024:.1f} KB" if file_size < 1024 * 1024 else f"{file_size / (1024 * 1024):.1f} MB",
                "created": datetime.fromtimestamp(file_stats.st_ctime).isoformat(),
                "overwritten": os.path.exists(abs_destination) and overwrite
            }
            
            logger.info("Successfully copied file from %s to %s", source_path, destination_path)
            await ctx.info(f"Successfully copied file ({result['size_human']})")
            return result
            
        except Exception as e:
            error_msg = f"Error copying file from '{source_path}' to '{destination_path}': {str(e)}"
            logger.error(error_msg, exc_info=True)
            await ctx.error(error_msg)
            return {"error": error_msg}

    @server.tool(name="move_file", description="Move a file from one location to another")
    async def move_file(ctx: Context, source_path: str, destination_path: str, 
                      overwrite: bool = False) -> Dict[str, Any]:
        """
        Moves a file from source path to destination path.
        
        Args:
            ctx: The MCP context
            source_path: Path to the source file (relative to project root)
            destination_path: Path to the destination file (relative to project root)
            overwrite: If True, overwrite the destination file if it exists
            
        Returns:
            A dictionary containing operation status and information
        """
        project_root = os.getcwd()
        abs_source = os.path.abspath(os.path.join(project_root, source_path))
        abs_destination = os.path.abspath(os.path.join(project_root, destination_path))
        
        logger.info("Received request to move file from %s to %s (overwrite=%s)", source_path, destination_path, overwrite)
        await ctx.info(f"Moving file from {source_path} to {destination_path}")
        
        # Security check to prevent directory traversal
        if not abs_source.startswith(project_root):
            error_msg = f"Error: Source path must be within the project directory."
            logger.error(error_msg)
            await ctx.error(error_msg)
            return {"error": error_msg}
            
        if not abs_destination.startswith(project_root):
            error_msg = f"Error: Destination path must be within the project directory."
            logger.error(error_msg)
            await ctx.error(error_msg)
            return {"error": error_msg}
            
        if not os.path.exists(abs_source):
            error_msg = f"Error: Source file '{source_path}' does not exist."
            logger.error(error_msg)
            await ctx.error(error_msg)
            return {"error": error_msg}
            
        if os.path.exists(abs_destination) and not overwrite:
            error_msg = f"Error: Destination file '{destination_path}' already exists and overwrite is False."
            logger.error(error_msg)
            await ctx.error(error_msg)
            return {"error": error_msg}
            
        # Create destination directory if it doesn't exist
        dest_dir = os.path.dirname(abs_destination)
        if dest_dir and not os.path.exists(dest_dir):
            try:
                os.makedirs(dest_dir, exist_ok=True)
                logger.info("Created destination directory: %s", dest_dir)
            except Exception as e:
                error_msg = f"Error creating destination directory: {str(e)}"
                logger.error(error_msg)
                await ctx.error(error_msg)
                return {"error": error_msg}
                
        try:
            # Create backup if destination exists and overwrite is True
            backup_path = None
            if os.path.exists(abs_destination) and overwrite:
                backup_path = abs_destination + ".bak"
                shutil.copy2(abs_destination, backup_path)
                logger.info("Created backup of destination file: %s", backup_path)
                
            # Move the file
            shutil.move(abs_source, abs_destination)
            
            # Get file size and other stats
            file_size = os.path.getsize(abs_destination)
            file_stats = os.stat(abs_destination)
            
            # Remove backup if everything was successful
            if backup_path and os.path.exists(backup_path):
                os.remove(backup_path)
                logger.info("Removed backup file: %s", backup_path)
            
            result = {
                "success": True,
                "source_path": source_path,
                "destination_path": destination_path,
                "size_bytes": file_size,
                "size_human": f"{file_size / 1024:.1f} KB" if file_size < 1024 * 1024 else f"{file_size / (1024 * 1024):.1f} MB",
                "created": datetime.fromtimestamp(file_stats.st_ctime).isoformat(),
                "overwritten": os.path.exists(abs_destination) and overwrite,
                "source_removed": not os.path.exists(abs_source)
            }
            
            logger.info("Successfully moved file from %s to %s", source_path, destination_path)
            await ctx.info(f"Successfully moved file ({result['size_human']})")
            return result
            
        except Exception as e:
            # Restore from backup if an error occurred and backup exists
            if backup_path and os.path.exists(backup_path):
                try:
                    shutil.copy2(backup_path, abs_destination)
                    os.remove(backup_path)
                    logger.info("Restored destination from backup after error")
                except:
                    logger.error("Failed to restore from backup after error")
                    
            error_msg = f"Error moving file from '{source_path}' to '{destination_path}': {str(e)}"
            logger.error(error_msg, exc_info=True)
            await ctx.error(error_msg)
            return {"error": error_msg}

# --- Custom Raw SSE Implementation ---
# Removed custom SSE implementation to rely on FastMCP default

# --- Homepage ---
async def homepage(request):
    """Simple homepage handler."""
    return JSONResponse({
        "message": f"Direct MCP Server ({server_color}) is running",
        "version": "unknown" if not imports_succeeded else (server._mcp_server.version or "dev"),
        "color": server_color,
        "pid": os.getpid(),
        "endpoints": {
            "/": "This homepage",
            "/mcp": "MCP SSE connection endpoint (handled by FastMCP)",
            "/jsonrpc": "JSON-RPC endpoint for VS Code integration",
            "/api/v0/jsonrpc": "Alternative JSON-RPC endpoint",
            "/api/v0/health": "Health check endpoint",
            "/api/v0/initialize": "VS Code initialize endpoint"
        },
        "deployment_status": deployment_status["status"] if deployment_status else "unknown"
    })

# --- JSON-RPC Implementation ---
# Initialize JSON-RPC dispatcher
# Removed: # Removed: # Removed: # Removed: # Removed: jsonrpc_dispatcher = Dispatcher()

# Removed: # Removed: # Removed: # Removed: # Removed: @jsonrpc_dispatcher.add_method
async def ping(**kwargs):
    """Simple ping method to test JSON-RPC connection."""
    return {"status": "ok", "server": f"direct-mcp-{server_color}", "timestamp": datetime.now().isoformat()}

# Removed: # Removed: # Removed: # Removed: # Removed: @jsonrpc_dispatcher.add_method
async def initialize(client_info=None, **kwargs):
    """Initialize the connection with VS Code."""
    logger.info("Received initialize request from client: %s", client_info)
    return {
        "server": f"direct-mcp-{server_color}",
        "version": server._mcp_server.version if hasattr(server, '_mcp_server') and hasattr(server._mcp_server, 'version') else "dev",
        "supported_models": ["default"],
        "capabilities": {
            "streaming": True,
            "jsonrpc": True,
            "tooling": True,
            "ipfs": True
        }
    }

# Removed: # Removed: # Removed: # Removed: # Removed: @jsonrpc_dispatcher.add_method
async def shutdown(**kwargs):
    """Handle shutdown request from client."""
    logger.info("Received shutdown request, will continue running but client is disconnecting")
    return {"status": "ok"}

# JSON-RPC request handler
async def handle_jsonrpc(request):
    """Handle JSON-RPC requests."""
    try:
        request_json = await request.json()
        logger.debug("Received JSON-RPC request: %s", request_json)

        method = request_json.get('method')
        params = request_json.get('params', {})
        req_id = request_json.get('id', None)

        if not method:
            return JSONResponse({
                'jsonrpc': '2.0',
                'error': {'code': -32600, 'message': 'Invalid Request - method missing'},
                'id': req_id
            })

        # Handle specific methods
        if method == 'get_tools':
            # Get all registered tools
            # Enhanced IPFS tools registered
            tools = [
                {
                "name": "ipfs_add",
                "description": "Add content to IPFS",
                "schema": {
                "type": "object",
                "properties": {
                "content": {
                "type": "string",
                "description": "Content to add to IPFS"
                },
                "filename": {
                "type": "string",
                "description": "Optional filename for the content"
                },
                "pin": {
                "type": "boolean",
                "description": "Whether to pin the content",
                "default": true
                }
                },
                "required": [
                "content"
            ]
        }
    },
    {
        "name": "ipfs_cat",
        "description": "Retrieve content from IPFS",
        "schema": {
            "type": "object",
            "properties": {
                "cid": {
                    "type": "string",
                    "description": "CID of the content to retrieve"
                }
            },
            "required": [
                "cid"
            ]
        }
    },
    {
        "name": "ipfs_ls",
        "description": "List directory contents in IPFS",
        "schema": {
            "type": "object",
            "properties": {
                "cid": {
                    "type": "string",
                    "description": "CID of the directory to list"
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Whether to list recursively",
                    "default": false
                }
            },
            "required": [
                "cid"
            ]
        }
    },
    {
        "name": "ipfs_files_ls",
        "description": "List files in the MFS",
        "schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path in the MFS to list",
                    "default": "/"
                },
                "long": {
                    "type": "boolean",
                    "description": "Whether to use long listing format",
                    "default": false
                }
            }
        }
    },
    {
        "name": "ipfs_files_mkdir",
        "description": "Create a directory in the MFS",
        "schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path in the MFS to create"
                },
                "parents": {
                    "type": "boolean",
                    "description": "Whether to create parent directories",
                    "default": true
                }
            },
            "required": [
                "path"
            ]
        }
    },
    {
        "name": "ipfs_files_write",
        "description": "Write to a file in the MFS",
        "schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path in the MFS to write to"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write"
                },
                "create": {
                    "type": "boolean",
                    "description": "Whether to create the file if it doesn't exist",
                    "default": true
                },
                "truncate": {
                    "type": "boolean",
                    "description": "Whether to truncate the file",
                    "default": true
                }
            },
            "required": [
                "path",
                "content"
            ]
        }
    },
    {
        "name": "ipfs_files_read",
        "description": "Read a file from the MFS",
        "schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path in the MFS to read"
                },
                "offset": {
                    "type": "integer",
                    "description": "Offset to start reading from",
                    "default": 0
                },
                "count": {
                    "type": "integer",
                    "description": "Number of bytes to read",
                    "default": -1
                }
            },
            "required": [
                "path"
            ]
        }
    },
    {
        "name": "ipfs_files_rm",
        "description": "Remove a file or directory from the MFS",
        "schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path in the MFS to remove"
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Whether to remove recursively",
                    "default": false
                }
            },
            "required": [
                "path"
            ]
        }
    },
    {
        "name": "ipfs_files_stat",
        "description": "Get stats for a file or directory in the MFS",
        "schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path in the MFS to get stats for"
                }
            },
            "required": [
                "path"
            ]
        }
    },
    {
        "name": "ipfs_files_cp",
        "description": "Copy files in the MFS",
        "schema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Source path in the MFS"
                },
                "dest": {
                    "type": "string",
                    "description": "Destination path in the MFS"
                }
            },
            "required": [
                "source",
                "dest"
            ]
        }
    },
    {
        "name": "ipfs_files_mv",
        "description": "Move files in the MFS",
        "schema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Source path in the MFS"
                },
                "dest": {
                    "type": "string",
                    "description": "Destination path in the MFS"
                }
            },
            "required": [
                "source",
                "dest"
            ]
        }
    },
    {
        "name": "ipfs_files_flush",
        "description": "Flush the MFS",
        "schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path in the MFS to flush",
                    "default": "/"
                }
            }
        }
    },
    {
        "name": "ipfs_pubsub_publish",
        "description": "Publish a message to a pubsub topic",
        "schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Topic to publish to"
                },
                "message": {
                    "type": "string",
                    "description": "Message to publish"
                }
            },
            "required": [
                "topic",
                "message"
            ]
        }
    },
    {
        "name": "ipfs_pubsub_subscribe",
        "description": "Subscribe to messages on a pubsub topic",
        "schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Topic to subscribe to"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds",
                    "default": 10
                }
            },
            "required": [
                "topic"
            ]
        }
    },
    {
        "name": "ipfs_dht_findpeer",
        "description": "Find a peer in the DHT",
        "schema": {
            "type": "object",
            "properties": {
                "peer_id": {
                    "type": "string",
                    "description": "Peer ID to find"
                }
            },
            "required": [
                "peer_id"
            ]
        }
    },
    {
        "name": "ipfs_dht_findprovs",
        "description": "Find providers for a CID in the DHT",
        "schema": {
            "type": "object",
            "properties": {
                "cid": {
                    "type": "string",
                    "description": "CID to find providers for"
                },
                "num_providers": {
                    "type": "integer",
                    "description": "Number of providers to find",
                    "default": 20
                }
            },
            "required": [
                "cid"
            ]
        }
    },
    {
        "name": "fs_journal_get_history",
        "description": "Get the operation history for a path in the virtual filesystem",
        "schema": {
            "type": "object",
            "properties": {
                "ctx": {
                    "type": "string",
                    "description": "Context for the operation"
                },
                "path": {
                    "type": "string",
                    "description": "Path to get history for",
                    "default": null
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of operations to return",
                    "default": 100
                }
            },
            "required": [
                "ctx"
            ]
        }
    },
    {
        "name": "fs_journal_sync",
        "description": "Force synchronization between virtual filesystem and actual storage",
        "schema": {
            "type": "object",
            "properties": {
                "ctx": {
                    "type": "string",
                    "description": "Context for the operation"
                },
                "path": {
                    "type": "string",
                    "description": "Path to synchronize",
                    "default": null
                }
            },
            "required": [
                "ctx"
            ]
        }
    },
    {
        "name": "ipfs_fs_bridge_status",
        "description": "Get the status of the IPFS-FS bridge",
        "schema": {
            "type": "object",
            "properties": {
                "ctx": {
                    "type": "string",
                    "description": "Context for the operation"
                }
            },
            "required": [
                "ctx"
            ]
        }
    },
    {
        "name": "ipfs_fs_bridge_sync",
        "description": "Sync between IPFS and virtual filesystem",
        "schema": {
            "type": "object",
            "properties": {
                "ctx": {
                    "type": "string",
                    "description": "Context for the operation"
                },
                "direction": {
                    "type": "string",
                    "description": "Direction of synchronization (ipfs_to_fs, fs_to_ipfs, or both)",
                    "default": "both"
                }
            },
            "required": [
                "ctx"
            ]
        }
    },
    {
        "name": "init_huggingface_backend",
        "description": "Initialize HuggingFace backend for the virtual filesystem",
        "schema": {
            "type": "object",
            "properties": {
                "ctx": {
                    "type": "string",
                    "description": "Context for the operation"
                },
                "name": {
                    "type": "string",
                    "description": "Name for the backend",
                    "default": "huggingface"
                },
                "root_path": {
                    "type": "string",
                    "description": "Root path for the backend",
                    "default": "/hf"
                }
            },
            "required": [
                "ctx"
            ]
        }
    },
    {
        "name": "init_filecoin_backend",
        "description": "Initialize Filecoin backend for the virtual filesystem",
        "schema": {
            "type": "object",
            "properties": {
                "ctx": {
                    "type": "string",
                    "description": "Context for the operation"
                },
                "name": {
                    "type": "string",
                    "description": "Name for the backend",
                    "default": "filecoin"
                },
                "root_path": {
                    "type": "string",
                    "description": "Root path for the backend",
                    "default": "/fil"
                }
            },
            "required": [
                "ctx"
            ]
        }
    },
    {
        "name": "init_s3_backend",
        "description": "Initialize S3 backend for the virtual filesystem",
        "schema": {
            "type": "object",
            "properties": {
                "ctx": {
                    "type": "string",
                    "description": "Context for the operation"
                },
                "name": {
                    "type": "string",
                    "description": "Name for the backend",
                    "default": "s3"
                },
                "root_path": {
                    "type": "string",
                    "description": "Root path for the backend",
                    "default": "/s3"
                },
                "bucket": {
                    "type": "string",
                    "description": "S3 bucket to use",
                    "default": null
                }
            },
            "required": [
                "ctx"
            ]
        }
    },
    {
        "name": "init_storacha_backend",
        "description": "Initialize Storacha backend for the virtual filesystem",
        "schema": {
            "type": "object",
            "properties": {
                "ctx": {
                    "type": "string",
                    "description": "Context for the operation"
                },
                "name": {
                    "type": "string",
                    "description": "Name for the backend",
                    "default": "storacha"
                },
                "root_path": {
                    "type": "string",
                    "description": "Root path for the backend",
                    "default": "/storacha"
                }
            },
            "required": [
                "ctx"
            ]
        }
    },
    {
        "name": "init_ipfs_cluster_backend",
        "description": "Initialize IPFS Cluster backend for the virtual filesystem",
        "schema": {
            "type": "object",
            "properties": {
                "ctx": {
                    "type": "string",
                    "description": "Context for the operation"
                },
                "name": {
                    "type": "string",
                    "description": "Name for the backend",
                    "default": "ipfs_cluster"
                },
                "root_path": {
                    "type": "string",
                    "description": "Root path for the backend",
                    "default": "/ipfs_cluster"
                }
            },
            "required": [
                "ctx"
            ]
        }
    },
    {
        "name": "multi_backend_map",
        "description": "Map a backend path to a local filesystem path",
        "schema": {
            "type": "object",
            "properties": {
                "ctx": {
                    "type": "string",
                    "description": "Context for the operation"
                },
                "backend_path": {
                    "type": "string",
                    "description": "Path in the backend"
                },
                "local_path": {
                    "type": "string",
                    "description": "Path in the local filesystem"
                }
            },
            "required": [
                "ctx",
                "backend_path",
                "local_path"
            ]
        }
    },
    {
        "name": "multi_backend_unmap",
        "description": "Remove a mapping between backend and local filesystem",
        "schema": {
            "type": "object",
            "properties": {
                "ctx": {
                    "type": "string",
                    "description": "Context for the operation"
                },
                "backend_path": {
                    "type": "string",
                    "description": "Path in the backend"
                }
            },
            "required": [
                "ctx",
                "backend_path"
            ]
        }
    },
    {
        "name": "multi_backend_list_mappings",
        "description": "List all mappings between backends and local filesystem",
        "schema": {
            "type": "object",
            "properties": {
                "ctx": {
                    "type": "string",
                    "description": "Context for the operation"
                }
            },
            "required": [
                "ctx"
            ]
        }
    },
    {
        "name": "multi_backend_status",
        "description": "Get status of the multi-backend filesystem",
        "schema": {
            "type": "object",
            "properties": {
                "ctx": {
                    "type": "string",
                    "description": "Context for the operation"
                }
            },
            "required": [
                "ctx"
            ]
        }
    },
    {
        "name": "multi_backend_sync",
        "description": "Synchronize all mapped paths",
        "schema": {
            "type": "object",
            "properties": {
                "ctx": {
                    "type": "string",
                    "description": "Context for the operation"
                }
            },
            "required": [
                "ctx"
            ]
        }
    },
    {
        "name": "multi_backend_search",
        "description": "Search indexed content",
        "schema": {
            "type": "object",
            "properties": {
                "ctx": {
                    "type": "string",
                    "description": "Context for the operation"
                },
                "query": {
                    "type": "string",
                    "description": "Search query"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results to return",
                    "default": 100
                }
            },
            "required": [
                "ctx",
                "query"
            ]
        }
    }
]
# Removed unmatched parenthesis
    except Exception as e:
        logger.error(f"JSON-RPC request handling error: {e}")
        return JSONResponse({
            'jsonrpc': '2.0',
            'error': {'code': -32603, 'message': f'Internal error: {str(e)}'},
            'id': req_id if 'req_id' in locals() else None
        })

    

    PORT = args.port
    
    # Write PID file
    with open(args.pid_file, 'w') as f:
        f.write(str(os.getpid()))
    
    # Initialize services
    app = server.sse_app()
    
    # Add CORS middleware for VS Code integration
    app.add_middleware(CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
)
# Removed unmatched parenthesis
    
    # Setup routes - Core API endpoints
    app.routes.append(Route("/", endpoint=homepage))
    app.routes.append(Route("/api/v0/health", endpoint=health_check))
    app.routes.append(Route("/api/v0/initialize", endpoint=vs_code_initialize, methods=["POST"]))
    app.routes.append(Route("/health", endpoint=health_endpoint))
    app.routes.append(Route("/initialize", endpoint=initialize_endpoint, methods=["POST"]))
    
    # JSON-RPC endpoints
    app.routes.append(Route("/jsonrpc", endpoint=handle_jsonrpc, methods=["POST"]))
    app.routes.append(Route("/api/v0/jsonrpc", endpoint=handle_jsonrpc, methods=["POST"]))
    
    # IPFS API endpoints
    app.routes.append(Route("/api/v0/ipfs/add", endpoint=ipfs_add, methods=["POST"]))
    app.routes.append(Route("/api/v0/ipfs/cat", endpoint=ipfs_cat))
    app.routes.append(Route("/api/v0/ipfs/pin/add", endpoint=ipfs_pin_add))
    
    # Update VS Code settings if requested
    if args.update_vscode:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(update_vscode_settings())
    
    # Register startup and shutdown handlers
    @app.on_event("startup")
    async def on_startup():
        logger.info("Starting MCP server services...")
        global server_initialized
        try:
            await update_vscode_settings()
            server_initialized = True
            initialization_event.set()
            logger.info("MCP server services started")
        except Exception as e:
            logger.error("Error during server initialization: %s", e, exc_info=True)
            server_initialized = True
            initialization_event.set()

    @app.on_event("shutdown")
    async def on_shutdown():
        logger.info("Shutting down MCP server services...")
        try:
            os.remove(args.pid_file)
        except OSError:
            pass
        logger.info("MCP server services stopped")
    
    logger.info("Starting MCP server on %s:%s", args.host, args.port)
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="debug" if args.debug else "info"
    )
