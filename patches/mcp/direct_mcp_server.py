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
import os
import sys
import logging
import json
import importlib
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mcp-server")

# Import IPFS extensions
try:
    from ipfs_mcp_tools import register_ipfs_tools
    from ipfs_kit_py.mcp.controllers.ipfs_controller import IPFSController
    import ipfs_kit_py.mcp.models.ipfs_model as ipfs_model
    IPFS_AVAILABLE = True
except ImportError:
    logger.warning("IPFS extensions not available")
    IPFS_AVAILABLE = False

# Import FS Journal tools
try:
    from fs_journal_tools import register_fs_journal_tools
    FS_JOURNAL_AVAILABLE = True
except ImportError:
    logger.warning("FS Journal tools not available")
    FS_JOURNAL_AVAILABLE = False

# Import IPFS-FS Bridge
try:
    from ipfs_mcp_fs_integration import register_integration_tools
    IPFS_FS_BRIDGE_AVAILABLE = True
except ImportError:
    logger.warning("IPFS-FS Bridge not available")
    IPFS_FS_BRIDGE_AVAILABLE = False

# Import Multi-Backend FS
try:
    from multi_backend_fs_integration import register_multi_backend_tools
    MULTI_BACKEND_FS_AVAILABLE = True
except ImportError:
    logger.warning("Multi-Backend FS not available")
    MULTI_BACKEND_FS_AVAILABLE = False


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

# IPFS and filesystem integration
try:
    import ipfs_mcp_tools
    import fs_journal_tools
    import multi_backend_fs_integration
    HAS_IPFS_TOOLS = True
except ImportError as e:
    logger.warning(f"Could not import IPFS tools: {e}")
    HAS_IPFS_TOOLS = False

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
    instructions="Server with blue/green deployment and live patching capabilities"
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
            tools = []
            for tool_name, tool in server._tool_manager._tools.items():
                # Ensure all data is serializable
                tool_info = {
                    'name': tool_name,
                    'description': str(tool.description) if hasattr(tool, 'description') else '',
                    'schema': {}
                }

                # Handle schema serialization
                if hasattr(tool, 'schema'):
                    if callable(tool.schema):
                        try:
                            schema = tool.schema()
                            if isinstance(schema, dict):
                                tool_info['schema'] = schema
                            else:
                                tool_info['schema'] = {'properties': {}}
                        except Exception as e:
                            logger.error(f"Error getting schema for {tool_name}: {e}")
                            tool_info['schema'] = {'properties': {}}
                    elif isinstance(tool.schema, dict):
                        tool_info['schema'] = tool.schema
                    else:
                        tool_info['schema'] = {'properties': {}}

                tools.append(tool_info)

            return JSONResponse({
                'jsonrpc': '2.0',
                'result': tools,
                'id': req_id
            })
        elif method == 'use_tool':
            tool_name = params.get('tool_name', '')
            arguments = params.get('arguments', {})

            if not tool_name:
                return JSONResponse({
                    'jsonrpc': '2.0',
                    'error': {'code': -32602, 'message': 'Invalid params - tool_name missing'},
                    'id': req_id
                })

            # Find the tool
            tool = server._tool_manager.get_tool(tool_name)
            if not tool:
                return JSONResponse({
                    'jsonrpc': '2.0',
                    'error': {'code': -32601, 'message': f'Method {tool_name} not found'},
                    'id': req_id
                })

            # Use the tool
            try:
                result = await tool.run(arguments)
                # Ensure the result is serializable
                if not isinstance(result, (dict, list, str, int, float, bool, type(None))):
                    result = str(result)
                return JSONResponse({
                    'jsonrpc': '2.0',
                    'result': result,
                    'id': req_id
                })
            except Exception as e:
                logger.error(f"Error using tool {tool_name}: {e}")
                return JSONResponse({
                    'jsonrpc': '2.0',
                    'error': {'code': -32603, 'message': str(e)},
                    'id': req_id
                })
        else:
            return JSONResponse({
                'jsonrpc': '2.0',
                'error': {'code': -32601, 'message': f'Method {method} not found'},
                'id': req_id
            })
    except json.JSONDecodeError:
        return JSONResponse({
            'jsonrpc': '2.0',
            'error': {'code': -32700, 'message': 'Parse error'},
            'id': None
        }, status_code=400)
    except Exception as e:
        logger.error("Error handling JSON-RPC request: %s", e, exc_info=True)
        return JSONResponse({
            'jsonrpc': '2.0',
            'error': {'code': -32603, 'message': str(e)},
            'id': None
        }, status_code=500)
# --- Health Check Endpoint ---
async def health_check(request):
    """Health check endpoint handler."""
    # Check if we're the active instance
    is_active = False
    try:
        if os.path.exists(DEPLOYMENT_CONFIG["active_version_file"]):
            with open(DEPLOYMENT_CONFIG["active_version_file"], "r") as f:
                active_version = f.read().strip()
                is_active = (active_version == server_color)
    except Exception as e:
        logger.error("Error checking active version: %s", e)

    # Basic health status
    status = {
        "status": "healthy",
        "instance": server_color,
        "active": is_active,
        "pid": os.getpid(),
        "uptime": time.time() - server._mcp_server._start_time if hasattr(server, "_mcp_server") and hasattr(server._mcp_server, "_start_time") else 0,
        "deployment_status": deployment_status["status"] if deployment_status else "unknown"
    }

    # Check if MCP server is initialized
    if server_initialized:
        status["mcp_status"] = "initialized"
    else:
        status["mcp_status"] = "initializing"

    return JSONResponse(status)

# --- VS Code Initialize Endpoint ---
async def vs_code_initialize(request):
    """VS Code initialization endpoint handler."""
    try:
        request_data = await request.json()
        logger.info("Received VS Code initialization request: %s", request_data)

        client_info = request_data.get("client", {})
        client_name = client_info.get("name", "unknown")
        client_version = client_info.get("version", "unknown")

        # Ensure the server is initialized
        global server_initialized, initialization_event
        if not server_initialized:
            await initialization_event.wait()

        response = {
            "status": "ok",
            "server": f"direct-mcp-{server_color}",
            "version": server._mcp_server.version if hasattr(server, '_mcp_server') and hasattr(server._mcp_server, 'version') else "dev",
            "endpoints": {
                "mcp": "/mcp",
                "jsonrpc": "/jsonrpc",
                "health": "/api/v0/health"
            },
            "capabilities": {
                "streaming": True,
                "jsonrpc": True,
                "tooling": True,
                "ipfs": True
            }
        }

        logger.info("Initialization successful for client: %s %s", client_name, client_version)
        return JSONResponse(response)

    except Exception as e:
        logger.error("Error handling VS Code initialization: %s", e, exc_info=True)
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

# --- VS Code Settings Update ---
async def update_vscode_settings():
    """Update VS Code settings to point to this server."""
    try:
        home_dir = os.path.expanduser("~")
        vscode_settings_dir = os.path.join(home_dir, ".vscode")
        settings_path = os.path.join(vscode_settings_dir, "settings.json")

        # Ensure directory exists
        os.makedirs(vscode_settings_dir, exist_ok=True)

        # Read existing settings if available
        settings = {}
        if os.path.exists(settings_path):
            try:
                with open(settings_path, 'r') as f:
                    settings = json.load(f)
            except json.JSONDecodeError:
                logger.warning("Could not parse settings file %s, creating new one", settings_path)
                settings = {}

        # Determine server URL
        server_url = f"http://localhost:{PORT}"

        # Update settings
        settings.setdefault("mcp", {})
        settings["mcp"]["endpoint"] = f"{server_url}/api/v0/jsonrpc"
        settings["mcp"]["jsonRpcEndpoint"] = f"{server_url}/jsonrpc"
        settings["mcp"].setdefault("capabilities", {})
        settings["mcp"]["capabilities"]["storage"] = {
            "ipfs": True,
            "filecoin": True,
            "huggingface": True
        }

        # Write updated settings
        with open(settings_path, 'w') as f:
            json.dump(settings, f, indent=2)

        logger.info("Updated VS Code settings at %s to use MCP server at %s", settings_path, server_url)
        return True
    except Exception as e:
        logger.error("Error updating VS Code settings: %s", e, exc_info=True)
        return False

# --- IPFS API Endpoints ---
async def ipfs_add(request):
    """Handle IPFS add requests."""
    try:
        # Check if form data with file
        if request.headers.get("content-type", "").startswith("multipart/form-data"):
            form = await request.form()
            file_obj = form.get("file")
            if not file_obj:
                return JSONResponse({"error": "No file provided"}, status_code=400)

            # Save uploaded file to temporary location
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_path = temp_file.name
                content = await file_obj.read()
                temp_file.write(content)

            try:
                # Mock IPFS response with dummy CID
                dummy_cid = f"Qm{''.join(str(uuid.uuid4()).split('-'))[:44]}"

                return JSONResponse({
                    "Hash": dummy_cid,
                    "Size": len(content),
                    "Name": file_obj.filename
                })
            finally:
                # Clean up temporary file
                _cleanup_temp_files(temp_path)

        # Handle JSON request with content as string
        else:
            data = await request.json()
            content = data.get("content", "")
            filename = data.get("filename", "file.txt")

            if not content:
                return JSONResponse({"error": "No content provided"}, status_code=400)

            # Mock IPFS response with dummy CID
            dummy_cid = f"Qm{''.join(str(uuid.uuid4()).split('-'))[:44]}"

            return JSONResponse({
                "Hash": dummy_cid,
                "Size": len(content),
                "Name": filename
            })

    except Exception as e:
        logger.error("Error handling IPFS add: %s", e, exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)

async def ipfs_cat(request):
    """Handle IPFS cat requests."""
    try:
        cid = request.query_params.get("cid")
        if not cid:
            data = await request.json()
            cid = data.get("cid")

        if not cid:
            return JSONResponse({"error": "No CID provided"}, status_code=400)

        # Mock IPFS response with dummy content
        content = f"Content for CID: {cid}\nGenerated at {datetime.now().isoformat()}\n"

        return Response(
            content=content.encode("utf-8"),
            media_type="application/octet-stream"
        )

    except Exception as e:
        logger.error("Error handling IPFS cat: %s", e, exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)

async def ipfs_pin_add(request):
    """Handle IPFS pin add requests."""
    try:
        cid = request.query_params.get("cid")
        if not cid:
            data = await request.json()
            cid = data.get("cid")

        if not cid:
            return JSONResponse({"error": "No CID provided"}, status_code=400)

        # Mock IPFS pin response
        return JSONResponse({
            "Pins": [cid]
        })

    except Exception as e:
        logger.error("Error handling IPFS pin add: %s", e, exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)

async def storage_status(request):
    """Handle storage status requests."""
    storage_type = "filecoin"
    path_parts = request.url.path.split("/")
    if len(path_parts) >= 3 and path_parts[-2] in ["huggingface", "filecoin", "ipfs"]:
        storage_type = path_parts[-2]

    try:
        # Mock storage status response
        return JSONResponse({
            "status": "ok",
            "type": storage_type,
            "connected": True,
            "timestamp": datetime.now().isoformat(),
            "instance": server_color,
            "details": {
                "version": "0.1.0",
                "api_version": "v0",
                "features": ["add", "get", "pin"]
            }
        })

    except Exception as e:
        logger.error("Error handling storage status: %s", e, exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)

# --- Health and Initialize Endpoints ---
async def health_endpoint(request):
    """Health check endpoint for the MCP server"""
    health_status = {
        "status": "ok",
        "version": __version__,
        "timestamp": datetime.now().isoformat(),
        "services": {}
    }

    # Check IPFS service if available
    if hasattr(request.app.ctx, 'ipfs_service'):
        try:
            ipfs_status = await request.app.ctx.ipfs_service.check_health()
            health_status["services"]["ipfs"] = {
                "status": "ok" if ipfs_status else "error",
                "details": ipfs_status
            }
        except Exception as e:
            health_status["services"]["ipfs"] = {
                "status": "error",
                "message": str(e)
            }

    return JSONResponse(health_status)

async def initialize_endpoint(request):
    """Initialize endpoint for VS Code Model Context Protocol integration"""
    logger.info("Received initialize request")

    server_info = {
        "id": "ipfs-mcp-server",
        "name": "IPFS MCP Server",
        "version": __version__,
        "status": "ready",
        "vendor": "IPFS Kit",
        "capabilities": {
            "jsonrpc": True,
            "ipfs": True,
            "filecoin": False,
            "huggingface": False,
            "streaming": True,
            "blueGreenDeployment": True
        },
        "endpoints": {
            "jsonrpc": f"http://localhost:{PORT}/jsonrpc",
            "health": f"http://localhost:{PORT}/health",
            "ipfs": {
                "add": f"http://localhost:{PORT}/api/v0/ipfs/add",
                "cat": f"http://localhost:{PORT}/api/v0/ipfs/cat",
                "pin": {
                    "add": f"http://localhost:{PORT}/api/v0/ipfs/pin/add"
                }
            }
        }
    }

    return JSONResponse(server_info)

# --- Main Entry ---
if __name__ == "__main__":
    # Clean up IPFS connections
    if "HAS_IPFS_TOOLS" in globals() and HAS_IPFS_TOOLS:
        logger.info("Shutting down IPFS connections...")
        try:
            # Any cleanup needed for IPFS connections
            pass
        except Exception as e:
            logger.error(f"Error shutting down IPFS connections: {e}")

    # Clean up IPFS connections
    if "HAS_IPFS_TOOLS" in globals() and HAS_IPFS_TOOLS:
        logger.info("Shutting down IPFS connections...")
        try:
            # Any cleanup needed for IPFS connections
            pass
        except Exception as e:
            logger.error(f"Error shutting down IPFS connections: {e}")

    # Clean up IPFS connections
    if "HAS_IPFS_TOOLS" in globals() and HAS_IPFS_TOOLS:
        logger.info("Shutting down IPFS connections...")
        try:
            # Any cleanup needed for IPFS connections
            pass
        except Exception as e:
            logger.error(f"Error shutting down IPFS connections: {e}")

    parser = argparse.ArgumentParser(description="IPFS MCP Server with Blue/Green Deployment Support")
    parser.add_argument("--port", type=int, default=3000, help="Port to run the server on")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind the server to")
    parser.add_argument("--debug", action="store_true", help="Run in debug mode")
    parser.add_argument("--log-level", type=str, choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                       default="INFO", help="Set logging level")
    parser.add_argument("--log-file", type=str, default="mcp_server.log", help="Log file path")
    parser.add_argument("--pid-file", type=str, default="mcp_server.pid", help="PID file path")
    parser.add_argument("--update-vscode", action="store_true", help="Update VS Code settings to point to this server")
    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(args.log_file),
            logging.StreamHandler()
        ]
    )


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


def register_all_tools(mcp_server):
    """Register all available tools with the MCP server."""
    logger.info("Registering all available tools with MCP server...")

    # Register IPFS tools if available
    if IPFS_AVAILABLE:
        try:
            # Initialize IPFS model
            ipfs = ipfs_model.IPFSModel()

            # Initialize IPFS controller
            controller = IPFSController(ipfs)

            # Register IPFS tools
            register_ipfs_tools(mcp_server, controller, ipfs)
            logger.info("✅ Successfully registered IPFS tools")
        except Exception as e:
            logger.error(f"Failed to register IPFS tools: {e}")

    # Register FS Journal tools if available
    if FS_JOURNAL_AVAILABLE:
        try:
            register_fs_journal_tools(mcp_server)
            logger.info("✅ Successfully registered FS Journal tools")
        except Exception as e:
            logger.error(f"Failed to register FS Journal tools: {e}")

    # Register IPFS-FS Bridge tools if available
    if IPFS_FS_BRIDGE_AVAILABLE:
        try:
            register_integration_tools(mcp_server)
            logger.info("✅ Successfully registered IPFS-FS Bridge tools")
        except Exception as e:
            logger.error(f"Failed to register IPFS-FS Bridge tools: {e}")

    # Register Multi-Backend FS tools if available
    if MULTI_BACKEND_FS_AVAILABLE:
        try:
            register_multi_backend_tools(mcp_server)
            logger.info("✅ Successfully registered Multi-Backend FS tools")
        except Exception as e:
            logger.error(f"Failed to register Multi-Backend FS tools: {e}")

    logger.info("Tool registration complete")
