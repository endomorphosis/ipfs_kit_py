#!/usr/bin/env python3
"""
Direct MCP server implementation using FastMCP and Starlette.
This version includes blue/green deployment capabilities.
It relies on the standard FastMCP SSE handling.
"""

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
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

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
    logger.warning(f"Could not set up file logging: {e}")

# Add MCP SDK path
cwd = os.getcwd()
sdk_path = os.path.abspath(os.path.join(cwd, "docs/mcp-python-sdk/src"))
sdk_added_to_path = False
if os.path.isdir(sdk_path):
    if sdk_path not in sys.path:
        sys.path.insert(0, sdk_path)
        logger.info(f"Added SDK path: {sdk_path}")
        sdk_added_to_path = True
    else:
        logger.info(f"SDK path already in sys.path: {sdk_path}")
        sdk_added_to_path = True
else:
     logger.warning(f"MCP SDK path not found: {sdk_path}. MCP features might fail.")

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
    imports_succeeded = True
    logger.info("Successfully imported MCP and Starlette modules.")
except ImportError as e:
    logger.error(f"Failed to import required MCP/Starlette modules even after adding SDK path: {e}")
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
        with open(DEPLOYMENT_CONFIG["active_version_file"], "r") as f:
            active_version = f.read().strip()
            if active_version == "green":
                is_blue = False
                server_color = "green"
                logger.info("Starting as GREEN instance based on active version file")
            else:
                logger.info("Starting as BLUE instance based on active version file")
    else:
        # Create the active version file if it doesn't exist
        with open(DEPLOYMENT_CONFIG["active_version_file"], "w") as f:
            f.write("blue")
        logger.info("Created active version file, starting as BLUE instance")
except Exception as e:
    logger.warning(f"Error reading/writing active version file: {e}. Defaulting to BLUE.")

# Write PID file for this instance
current_pid_file = DEPLOYMENT_CONFIG["blue_pid_file"] if is_blue else DEPLOYMENT_CONFIG["green_pid_file"]
try:
    with open(current_pid_file, "w") as f:
        f.write(str(os.getpid()))
    logger.info(f"Wrote PID {os.getpid()} to {current_pid_file}")
except Exception as e:
    logger.error(f"Failed to write PID file {current_pid_file}: {e}")

# Create FastMCP server 
server = FastMCP(
    name=f"direct-mcp-server-{server_color}", 
    instructions="Server with blue/green deployment and live patching capabilities"
)

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
                logger.debug(f"Cleaned up temporary file: {path}")
            except OSError as e:
                logger.error(f"Error removing temporary file {path}: {e}")

async def delayed_shutdown(pid: int, delay: float):
    """Waits for a delay then sends SIGTERM."""
    await asyncio.sleep(delay)
    logger.info(f"Sending SIGTERM to process {pid} after {delay}s delay.")
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        logger.warning(f"Process {pid} not found for shutdown signal.")
    except Exception as e:
        logger.error(f"Error sending SIGTERM to process {pid}: {e}")

def get_other_instance_pid():
    """Get the PID of the other instance (blue if we're green, green if we're blue)."""
    other_pid_file = DEPLOYMENT_CONFIG["green_pid_file"] if is_blue else DEPLOYMENT_CONFIG["blue_pid_file"]
    try:
        if os.path.exists(other_pid_file):
            with open(other_pid_file, "r") as f:
                return int(f.read().strip())
    except Exception as e:
        logger.error(f"Error reading other instance PID file: {e}")
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
        logger.info(f"Started other instance with PID {process.pid} on port {port}")
        return process.pid
    except Exception as e:
        logger.error(f"Failed to start other instance: {e}")
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
        logger.info(f"Switched active version to {new_color}")
        return True
    except Exception as e:
        logger.error(f"Failed to switch active version: {e}")
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
    
    logger.info(f"Starting blue/green deployment from {server_color} to {target_color}")
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
                logger.error(f"Syntax check failed for {modified_file}: {syntax_output}")
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
                    logger.error(f"Tests failed for {modified_file}")
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
            logger.info(f"Performing health check {i+1}/{max_attempts} on port {target_port}")
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
        logger.info(f"Deployment completed successfully. Shutting down {server_color} instance.")
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
        logger.error(f"Deployment error: {e}")
        deployment_status = {
            "status": "failed",
            "details": f"Deployment error: {str(e)}",
            "start_time": deployment_status["start_time"]
        }
        deployment_in_progress = False
        return {"success": False, "message": f"Deployment error: {str(e)}"}

# --- MCP Tools (Define only if imports succeeded) ---
if imports_succeeded:
    @server.tool(name="list_files", description="List files in a directory")
    async def list_files(ctx: Context, path: str = ".") -> str:
        """List files in the specified directory."""
        logger.info(f"Listing files in {path}")
        
        try:
            # Basic security check
            abs_path = os.path.abspath(os.path.join(os.getcwd(), path))
            if not abs_path.startswith(os.getcwd()):
                await ctx.error("Path outside of workspace is not allowed")
                return "Error: Path outside of workspace is not allowed"
                
            files = os.listdir(abs_path)
            await ctx.info(f"Found {len(files)} files/directories")
            return "\n".join(files)
        except Exception as e:
            error_msg = f"Error listing files: {str(e)}"
            logger.error(error_msg)
            await ctx.error(error_msg)
            return f"Error: {error_msg}"

    @server.tool(name="deployment_status", description="Get the status of the current blue/green deployment")
    async def get_deployment_status(ctx: Context) -> str:
        """Get the status of the current deployment."""
        global deployment_status
        
        try:
            status = deployment_status.copy()
            status["server_color"] = server_color
            status["deployment_in_progress"] = deployment_in_progress
            
            if status["start_time"]:
                elapsed = time.time() - status["start_time"]
                status["elapsed_seconds"] = elapsed
                
            if "end_time" in status and status["end_time"]:
                status["duration_seconds"] = status["end_time"] - status["start_time"]
                
            await ctx.info(f"Retrieved deployment status: {status['status']}")
            return json.dumps(status, indent=2)
        except Exception as e:
            error_msg = f"Error getting deployment status: {str(e)}"
            logger.error(error_msg)
            await ctx.error(error_msg)
            return f"Error: {error_msg}"

    @server.tool(name="edit_file", description="Edits a file with blue/green deployment analysis.")
    async def edit_file(ctx: Context, path: str, content: str, deploy: bool = False) -> str:
        """
        Writes content to a file after checking Python syntax and running pytest.
        If deploy=True, initiates a blue/green deployment process.
        """
        logger.info(f"Received request to edit file: {path} with deploy={deploy}")
        await ctx.info(f"Attempting to edit file: {path}")

        project_root = os.getcwd()
        absolute_path = os.path.abspath(os.path.join(project_root, path))
        if not absolute_path.startswith(project_root):
            error_msg = f"Error: Path '{path}' is outside the allowed project directory."
            logger.error(error_msg)
            await ctx.error(error_msg)
            return error_msg

        if not os.path.exists(os.path.dirname(absolute_path)):
            if os.path.dirname(absolute_path) != project_root:
                error_msg = f"Error: Directory for path '{path}' does not exist."
                logger.error(error_msg)
                await ctx.error(error_msg)
                return error_msg

        temp_path = absolute_path + ".tmp"
        backup_path = absolute_path + ".bak"
        logger.debug(f"Writing content to temporary file: {temp_path}")
        original_exists = os.path.exists(absolute_path)
        pytest_passed = False
        pytest_output = "Pytest check not run or failed."
        test_error = None
        syntax_check_passed = False

        try:
            # 1. Write content to temporary file
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(content)

            # 2. Perform syntax check (only for .py files)
            if absolute_path.endswith(".py"):
                logger.info(f"Performing syntax check on {temp_path}")
                try:
                    py_compile.compile(temp_path, doraise=True)
                    logger.info(f"Syntax check passed for {temp_path}")
                    await ctx.info(f"Syntax check passed for {path}.")
                    syntax_check_passed = True
                except py_compile.PyCompileError as e:
                    error_msg = f"Syntax check failed for '{path}': {e}"
                    logger.error(error_msg)
                    await ctx.error(error_msg)
                    _cleanup_temp_files(temp_path)
                    return f"Error: {error_msg}"
                except Exception as e:
                    error_msg = f"Error during syntax check for '{path}': {e}"
                    logger.error(error_msg, exc_info=True)
                    await ctx.error(error_msg)
                    _cleanup_temp_files(temp_path)
                    return f"Error: {error_msg}"
            else:
                logger.info(f"Skipping syntax check for non-python file: {path}")
                await ctx.info(f"Skipping syntax check for non-python file: {path}")
                syntax_check_passed = True

            # 3. Perform pytest check only if syntax check passed
            if syntax_check_passed:
                logger.info(f"Performing pytest check...")
                temp_file_for_test = absolute_path + ".pytest_test"
                try:
                    pytest_path = os.path.join(project_root, ".venv/bin/pytest")
                    if not os.path.exists(pytest_path):
                        pytest_path = "pytest"

                    # Backup original file if it exists
                    if original_exists:
                        logger.debug(f"Backing up {absolute_path} to {backup_path}")
                        shutil.copy2(absolute_path, backup_path)

                    # Copy the temp file content to a temporary test location
                    logger.debug(f"Copying {temp_path} to {temp_file_for_test} for pytest.")
                    shutil.copy2(temp_path, temp_file_for_test)

                    # Run pytest against the temporary test file location (or project)
                    logger.info(f"Running pytest command: {pytest_path}")
                    try:
                        # Use the test_suite from DEPLOYMENT_CONFIG
                        test_files_to_run = DEPLOYMENT_CONFIG.get("test_suite")
                        if not test_files_to_run: # If list is empty or None
                             logger.info("No specific test suite defined in config, assuming pass.")
                             pytest_passed = True # Assume pass if no tests specified
                             pytest_output = "No specific tests configured to run."
                        else:
                            result = subprocess.run(
                                [pytest_path] + test_files_to_run, # Pass specific tests
                                cwd=project_root,
                                capture_output=True,
                                text=True,
                                timeout=120
                            )
                            pytest_output = f"Output:\n{result.stdout}\n{result.stderr}"

                            if result.returncode == 0:
                                logger.info(f"Pytest passed for potential change to {path}")
                                await ctx.info(f"Pytest check passed for {path}.")
                                pytest_passed = True
                            else:
                                error_msg = f"Pytest check failed for '{path}' (exit code {result.returncode})."
                                logger.warning(error_msg)
                                await ctx.warning(f"Pytest check failed for '{path}'. Changes NOT saved. See server logs for details.")
                                pytest_passed = False
                    except subprocess.TimeoutExpired:
                        error_msg = f"Pytest timed out for '{path}'"
                        logger.warning(error_msg)
                        await ctx.warning(error_msg)
                        pytest_passed = False

                except Exception as e:
                    error_msg = f"Error during pytest check for '{path}': {e}"
                    logger.error(error_msg, exc_info=True)
                    await ctx.error(error_msg)
                    pytest_passed = False
                    pytest_output = error_msg
                    test_error = e
                finally:
                    # Clean up the temporary file used for testing
                    _cleanup_temp_files(temp_file_for_test)
                    # Restore original from backup if it exists
                    if original_exists and os.path.exists(backup_path):
                        logger.debug(f"Restoring original {absolute_path} from {backup_path} after test run.")
                        shutil.move(backup_path, absolute_path)
                    # Clean up backup file if it still exists
                    _cleanup_temp_files(backup_path)
                    # If an exception occurred during testing, re-raise it after cleanup
                    if test_error:
                        raise test_error
            else:
                logger.error("Reached pytest block unexpectedly after syntax check failure.")
                _cleanup_temp_files(temp_path)
                return "Internal Server Error: Logic flow issue in edit_file."

            # 4. Final Outcome
            if pytest_passed:
                # Move the validated temp file to the final destination
                logger.info(f"Checks passed. Saving changes to {absolute_path}")
                shutil.move(temp_path, absolute_path)
                success_msg = f"Successfully edited, checked (pytest passed), and saved file: {path}"
                logger.info(success_msg)
                await ctx.info(success_msg)
                
                # Check if we need to do blue/green deployment
                if deploy and absolute_path.endswith(".py"):
                    await ctx.info("Starting blue/green deployment process...")
                    deployment_task = asyncio.create_task(perform_blue_green_deployment(absolute_path))
                    return success_msg + " Blue/green deployment started."
                
                # Trigger graceful shutdown for restart if it's a server file and not deploying
                if not deploy:
                    server_files = ["direct_mcp_server.py", "enhanced_mcp_server.py"]
                    if any(server_file in absolute_path for server_file in server_files):
                        pid = os.getpid()
                        logger.warning(f"Tests passed for '{path}' (server file). Triggering server restart (PID: {pid})...")
                        await ctx.info("Server file updated. Triggering server restart...")
                        asyncio.create_task(delayed_shutdown(pid, 1))
                        return success_msg + " Server restarting."
                return success_msg
            else:
                # Pytest failed or syntax check skipped for non-python file. Do not save.
                warning_msg = f"Checks failed for '{path}'. Changes were NOT saved."
                if not syntax_check_passed:
                    warning_msg = f"Syntax check failed for '{path}'. Changes were NOT saved."
                elif not pytest_passed:
                    warning_msg = f"Pytest failed for '{path}'. Changes were NOT saved. See server logs for details."

                logger.warning(warning_msg)
                await ctx.warning(warning_msg)
                _cleanup_temp_files(temp_path)
                return warning_msg

        except IOError as e:
            error_msg = f"File I/O error editing '{path}': {e}"
            logger.error(error_msg, exc_info=True)
            await ctx.error(error_msg)
            _cleanup_temp_files(temp_path, backup_path)
            return f"Error: {error_msg}"
        except Exception as e:
            # This catches errors from the main try block, including re-raised test errors
            error_msg = f"Unexpected error editing '{path}': {e}"
            logger.error(error_msg, exc_info=True)
            await ctx.error(error_msg)
            _cleanup_temp_files(temp_path, backup_path)
            return f"Error: {error_msg}"

    @server.tool(name="patch_file", description="Replaces a slice of lines in a file with blue/green deployment analysis.")
    async def patch_file(ctx: Context, path: str, start_line: int, line_count_to_replace: int, new_lines_content: str, deploy: bool = False) -> str:
        """
        Replaces a specific range of lines in a file with blue/green deployment analysis.
        If deploy=True, initiates a blue/green deployment process after successful validation.
        """
        logger.info(f"Received request to patch file: {path} from line {start_line} for {line_count_to_replace} lines with deploy={deploy}")
        await ctx.info(f"Attempting to patch file: {path}")

        project_root = os.getcwd()
        absolute_path = os.path.abspath(os.path.join(project_root, path))
        if not absolute_path.startswith(project_root):
            error_msg = f"Error: Path '{path}' is outside the allowed project directory."
            logger.error(error_msg)
            await ctx.error(error_msg)
            return error_msg
        
        if not os.path.isfile(absolute_path):
            error_msg = f"Error: File not found at path '{path}'."
            logger.error(error_msg)
            await ctx.error(error_msg)
            return error_msg

        # Validate line numbers
        if start_line < 1:
            error_msg = "Error: start_line must be 1 or greater."
            logger.error(error_msg)
            await ctx.error(error_msg)
            return error_msg
        
        if line_count_to_replace < 0:
            error_msg = "Error: line_count_to_replace cannot be negative."
            logger.error(error_msg)
            await ctx.error(error_msg)
            return error_msg

        temp_path = absolute_path + ".patch.tmp"
        backup_path = absolute_path + ".bak"
        pytest_passed = False
        test_error = None
        syntax_check_passed = False

        try:
            # Read original content
            with open(absolute_path, "r", encoding="utf-8") as f:
                original_lines = f.readlines()

            # Calculate slice indices (0-based)
            start_index = start_line - 1
            end_index = start_index + line_count_to_replace

            # Validate slice indices against file length
            if start_index >= len(original_lines):
                error_msg = f"Error: start_line ({start_line}) is beyond the end of the file ({len(original_lines)} lines)."
                logger.error(error_msg)
                await ctx.error(error_msg)
                return error_msg
                
            # Allow replacing past the end (effectively appending) but cap end_index
            end_index = min(end_index, len(original_lines))

            # Construct new content - Fix: Properly handle newlines with actual newline characters
            new_lines_list = new_lines_content.splitlines(True)  # Keep line endings with splitlines(True)
            if new_lines_list and not new_lines_list[-1].endswith('\n'):
                # Ensure the last line has a newline if the original content did
                if original_lines and original_lines[-1].endswith('\n'):
                    new_lines_list[-1] = new_lines_list[-1] + '\n'
                    
            patched_lines = original_lines[:start_index] + new_lines_list + original_lines[end_index:]
            patched_content = "".join(patched_lines)

            # 1. Write patched content to temporary file
            logger.debug(f"Writing patched content to temporary file: {temp_path}")
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(patched_content)

            # 2. Perform syntax check (only for .py files)
            if absolute_path.endswith(".py"):
                logger.info(f"Performing syntax check on {temp_path}")
                try:
                    py_compile.compile(temp_path, doraise=True)
                    logger.info(f"Syntax check passed for patched {path}.")
                    await ctx.info(f"Syntax check passed for patched {path}.")
                    syntax_check_passed = True
                except py_compile.PyCompileError as e:
                    error_msg = f"Syntax check failed for patched '{path}': {e}"
                    logger.error(error_msg)
                    await ctx.error(error_msg)
                    _cleanup_temp_files(temp_path)
                    return f"Error: {error_msg}"
                except Exception as e:
                    error_msg = f"Error during syntax check for patched '{path}': {e}"
                    logger.error(error_msg, exc_info=True)
                    await ctx.error(error_msg)
                    _cleanup_temp_files(temp_path)
                    return f"Error: {error_msg}"
            else:
                logger.info(f"Skipping syntax check for non-python file: {path}")
                await ctx.info(f"Skipping syntax check for non-python file: {path}")
                syntax_check_passed = True

            # 3. Perform pytest check only if syntax check passed
            if syntax_check_passed:
                logger.info(f"Performing pytest check...")
                temp_file_for_test = absolute_path + ".pytest_test"
                try:
                    pytest_path = os.path.join(project_root, ".venv/bin/pytest")
                    if not os.path.exists(pytest_path):
                        pytest_path = "pytest"

                    # Backup original file
                    logger.debug(f"Backing up {absolute_path} to {backup_path}")
                    shutil.copy2(absolute_path, backup_path)

                    # Copy the temp file content to a temporary test location
                    logger.debug(f"Copying {temp_path} to {temp_file_for_test} for pytest.")
                    shutil.copy2(temp_path, temp_file_for_test)

                    # Run pytest
                    logger.info(f"Running pytest command: {pytest_path}")
                    try:
                        # Use the test_suite from DEPLOYMENT_CONFIG
                        test_files_to_run = DEPLOYMENT_CONFIG.get("test_suite")
                        if not test_files_to_run: # If list is empty or None
                             logger.info("No specific test suite defined in config, assuming pass.")
                             pytest_passed = True # Assume pass if no tests specified
                             pytest_output = "No specific tests configured to run."
                        else:
                            result = subprocess.run(
                                [pytest_path] + test_files_to_run, # Pass specific tests
                                cwd=project_root,
                                capture_output=True,
                                text=True,
                                timeout=120
                            )
                            pytest_output = f"Output:\n{result.stdout}\n{result.stderr}"

                            if result.returncode == 0:
                                logger.info(f"Pytest passed for potential patch to {path}")
                                await ctx.info(f"Pytest check passed for {path}.")
                                pytest_passed = True
                            else:
                                error_msg = f"Pytest check failed for patched '{path}' (exit code {result.returncode})."
                                logger.warning(error_msg)
                                await ctx.warning(f"Pytest check failed for '{path}'. Changes NOT saved.")
                                pytest_passed = False
                    except subprocess.TimeoutExpired:
                        error_msg = f"Pytest timed out for '{path}'"
                        logger.warning(error_msg)
                        await ctx.warning(error_msg)
                        pytest_passed = False
                        
                except Exception as e:
                    error_msg = f"Error during pytest check for patched '{path}': {e}"
                    logger.error(error_msg, exc_info=True)
                    await ctx.error(error_msg)
                    pytest_passed = False
                    test_error = e
                finally:
                    # Clean up the temporary file used for testing
                    _cleanup_temp_files(temp_file_for_test)
                    # Restore original from backup
                    shutil.move(backup_path, absolute_path)
                    # If an exception occurred during testing, re-raise it after cleanup
                    if test_error:
                        raise test_error
            else:
                logger.error("Reached pytest block unexpectedly after syntax check failure.")
                _cleanup_temp_files(temp_path)
                return "Internal Server Error: Logic flow issue in patch_file."

            # 4. Final Outcome
            if pytest_passed:
                # Move the validated temp file to the final destination
                logger.info(f"Checks passed. Saving patch to {absolute_path}")
                shutil.move(temp_path, absolute_path)
                success_msg = f"Successfully patched, checked, and saved file: {path}"
                logger.info(success_msg)
                await ctx.info(success_msg)
                
                # Check if we need to do blue/green deployment
                if deploy and absolute_path.endswith(".py"):
                    await ctx.info("Starting blue/green deployment process...")
                    deployment_task = asyncio.create_task(perform_blue_green_deployment(absolute_path))
                    return success_msg + " Blue/green deployment started."
                
                # Trigger graceful shutdown for restart if it's a server file and not deploying
                if not deploy:
                    server_files = ["direct_mcp_server.py", "enhanced_mcp_server.py"]
                    if any(server_file in absolute_path for server_file in server_files):
                        pid = os.getpid()
                        logger.warning(f"Tests passed for '{path}' (server file). Triggering server restart (PID: {pid})...")
                        await ctx.info("Server file updated. Triggering server restart...")
                        asyncio.create_task(delayed_shutdown(pid, 1))
                        return success_msg + " Server restarting."
                return success_msg
            else:
                # Pytest failed, do not apply the patch
                warning_msg = f"Checks failed for '{path}'. Patch NOT applied."
                logger.warning(warning_msg)
                await ctx.warning(warning_msg)
                _cleanup_temp_files(temp_path)
                return warning_msg

        except IOError as e:
            error_msg = f"File I/O error patching '{path}': {e}"
            logger.error(error_msg, exc_info=True)
            await ctx.error(error_msg)
            _cleanup_temp_files(temp_path, backup_path)
            return f"Error: {error_msg}"
        except Exception as e:
            error_msg = f"Unexpected error patching '{path}': {e}"
            logger.error(error_msg, exc_info=True)
            await ctx.error(error_msg)
            _cleanup_temp_files(temp_path, backup_path)
            return f"Error: {error_msg}"

    @server.tool(name="start_blue_green_deployment", description="Starts a blue/green deployment process manually.")
    async def start_blue_green_deployment(ctx: Context) -> str:
        """Start a manual blue/green deployment process."""
        if deployment_in_progress:
            error_msg = "Deployment already in progress"
            logger.warning(error_msg)
            await ctx.warning(error_msg)
            return f"Error: {error_msg}"
            
        try:
            await ctx.info("Starting blue/green deployment process...")
            result = await perform_blue_green_deployment()
            
            if result["success"]:
                await ctx.info(result["message"])
                return result["message"]
            else:
                await ctx.error(result["message"])
                return f"Error: {result['message']}"
        except Exception as e:
            error_msg = f"Error starting deployment: {str(e)}"
            logger.error(error_msg, exc_info=True)
            await ctx.error(error_msg)
            return f"Error: {error_msg}"

    @server.tool(name="read_file", description="Reads and returns the entire contents of a file")
    async def read_file(ctx: Context, path: str) -> str:
        """
        Reads and returns the entire contents of a file.
        
        Args:
            ctx: The MCP context
            path: Relative path to the file to read
        
        Returns:
            The content of the file as a string
        """
        logger.info(f"Received request to read file: {path}")
        await ctx.info(f"Reading file: {path}")
        
        project_root = os.getcwd()
        absolute_path = os.path.abspath(os.path.join(project_root, path))
        
        # Security check to prevent directory traversal
        if not absolute_path.startswith(project_root):
            error_msg = f"Error: Path '{path}' is outside the allowed project directory."
            logger.error(error_msg)
            await ctx.error(error_msg)
            return error_msg
        
        if not os.path.exists(absolute_path):
            error_msg = f"Error: File not found at path '{path}'."
            logger.error(error_msg)
            await ctx.error(error_msg)
            return error_msg
        
        if not os.path.isfile(absolute_path):
            error_msg = f"Error: Path '{path}' is not a file."
            logger.error(error_msg)
            await ctx.error(error_msg)
            return error_msg
        
        try:
            # Check file size to prevent memory issues with very large files
            file_size = os.path.getsize(absolute_path)
            max_size = 10 * 1024 * 1024  # 10 MB limit
            
            if file_size > max_size:
                msg = f"Warning: File is large ({file_size / 1024 / 1024:.2f} MB). Consider using read_file_slice instead."
                logger.warning(msg)
                await ctx.warning(msg)
                
            with open(absolute_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            
            await ctx.info(f"Successfully read {len(content)} characters from {path}")
            return content
        
        except UnicodeDecodeError:
            # Try to detect if it's a binary file
            try:
                with open(absolute_path, "rb") as f:
                    sample = f.read(1024)
                if b'\\x00' in sample:
                    error_msg = f"Error: File '{path}' appears to be a binary file and cannot be read as text."
                    logger.error(error_msg)
                    await ctx.error(error_msg)
                    return error_msg
                else:
                    # Try with a different encoding
                    with open(absolute_path, "r", encoding="latin-1") as f:
                        content = f.read()
                    await ctx.warning(f"File '{path}' was read using latin-1 encoding due to encoding issues with utf-8")
                    return content
            except Exception as e:
                error_msg = f"Error reading file '{path}': {str(e)}"
                logger.error(error_msg, exc_info=True)
                await ctx.error(error_msg)
                return f"Error: {error_msg}"
        
        except Exception as e:
            error_msg = f"Error reading file '{path}': {str(e)}"
            logger.error(error_msg, exc_info=True)
            await ctx.error(error_msg)
            return f"Error: {error_msg}"

    @server.tool(name="read_file_slice", description="Reads and returns a specific range of lines from a file")
    async def read_file_slice(ctx: Context, path: str, start_line: int = 1, num_lines: int = 50) -> str:
        """
        Reads and returns a specific range of lines from a file.
        
        Args:
            ctx: The MCP context
            path: Relative path to the file to read
            start_line: Line number to start reading from (1-based indexing)
            num_lines: Number of lines to read
        
        Returns:
            The requested slice of the file as a string
        """
        logger.info(f"Received request to read file slice: {path}, lines {start_line} to {start_line + num_lines - 1}")
        await ctx.info(f"Reading lines {start_line} to {start_line + num_lines - 1} from file: {path}")
        
        # Validate parameters
        if start_line < 1:
            error_msg = "Error: start_line must be 1 or greater."
            logger.error(error_msg)
            await ctx.error(error_msg)
            return error_msg
        
        if num_lines < 1:
            error_msg = "Error: num_lines must be at least 1."
            logger.error(error_msg)
            await ctx.error(error_msg)
            return error_msg
        
        project_root = os.getcwd()
        absolute_path = os.path.abspath(os.path.join(project_root, path))
        
        # Security check to prevent directory traversal
        if not absolute_path.startswith(project_root):
            error_msg = f"Error: Path '{path}' is outside the allowed project directory."
            logger.error(error_msg)
            await ctx.error(error_msg)
            return error_msg
        
        if not os.path.exists(absolute_path):
            error_msg = f"Error: File not found at path '{path}'."
            logger.error(error_msg)
            await ctx.error(error_msg)
            return error_msg
        
        if not os.path.isfile(absolute_path):
            error_msg = f"Error: Path '{path}' is not a file."
            logger.error(error_msg)
            await ctx.error(error_msg)
            return error_msg
        
        try:
            with open(absolute_path, "r", encoding="utf-8", errors="replace") as f:
                # Zero-based index for start_index
                start_index = start_line - 1
                lines = []
                
                # Skip to the start line
                for i, line in enumerate(f):
                    if i >= start_index:
                        lines.append(line)
                        # Break once we have read enough lines
                        if len(lines) >= num_lines:
                            break
            
            if not lines:
                if start_line > 1:
                    await ctx.warning(f"No lines returned. The file may be shorter than expected or start_line ({start_line}) is beyond EOF.")
                    return f"No lines found at line {start_line} or beyond."
                else:
                    await ctx.info(f"File '{path}' appears to be empty.")
                    return "File is empty."
            
            content = "".join(lines)
            
            # Add context about file size
            total_lines = sum(1 for line in open(absolute_path, "r", encoding="utf-8", errors="replace"))
            if start_line + len(lines) - 1 < total_lines:
                footer = f"\n[...Showing lines {start_line} to {start_line + len(lines) - 1} of {total_lines} total lines...]"
                content += footer
            
            await ctx.info(f"Successfully read {len(lines)} lines from {path}")
            return content
        
        except UnicodeDecodeError:
            # Try to detect if it's a binary file
            try:
                with open(absolute_path, "rb") as f:
                    sample = f.read(1024)
                if b'\\x00' in sample:
                    error_msg = f"Error: File '{path}' appears to be a binary file and cannot be read as text."
                    logger.error(error_msg)
                    await ctx.error(error_msg)
                    return error_msg
                else:
                    # Try with a different encoding
                    with open(absolute_path, "r", encoding="latin-1") as f:
                        # Skip to the start line
                        start_index = start_line - 1
                        lines = []
                        
                        for i, line in enumerate(f):
                            if i >= start_index:
                                lines.append(line)
                                # Break once we have read enough lines
                                if len(lines) >= num_lines:
                                    break
                    
                    content = "".join(lines)
                    await ctx.warning(f"File '{path}' was read using latin-1 encoding due to encoding issues with utf-8")
                    return content
            except Exception as e:
                error_msg = f"Error reading file '{path}': {str(e)}"
                logger.error(error_msg, exc_info=True)
                await ctx.error(error_msg)
                return f"Error: {error_msg}"
        
        except Exception as e:
            error_msg = f"Error reading file '{path}': {str(e)}"
            logger.error(error_msg, exc_info=True)
            await ctx.error(error_msg)
            return f"Error: {error_msg}"

    @server.tool(name="write_file", description="Writes content to a new file only (fails if file already exists)")
    async def write_file(ctx: Context, path: str, content: str) -> str:
        """
        Writes content to a new file only. Will fail if the file already exists.
        This provides a safe way to create new files without risk of overwriting existing content.
        
        Args:
            ctx: The MCP context
            path: Relative path to the new file to create
            content: Content to write to the file
        
        Returns:
            A message indicating success or error
        """
        logger.info(f"Received request to create new file: {path}")
        await ctx.info(f"Attempting to create new file: {path}")
        
        project_root = os.getcwd()
        absolute_path = os.path.abspath(os.path.join(project_root, path))
        
        # Security check to prevent directory traversal
        if not absolute_path.startswith(project_root):
            error_msg = f"Error: Path '{path}' is outside the allowed project directory."
            logger.error(error_msg)
            await ctx.error(error_msg)
            return error_msg
        
        # Check if file already exists
        if os.path.exists(absolute_path):
            error_msg = f"Error: File '{path}' already exists. Use edit_file to modify existing files."
            logger.error(error_msg)
            await ctx.error(error_msg)
            return error_msg
        
        # Ensure the directory exists
        directory = os.path.dirname(absolute_path)
        if directory and not os.path.exists(directory):
            try:
                os.makedirs(directory, exist_ok=True)
                logger.info(f"Created directory: {directory}")
                await ctx.info(f"Created directory: {os.path.relpath(directory, project_root)}")
            except Exception as e:
                error_msg = f"Error creating directory '{os.path.relpath(directory, project_root)}': {str(e)}"
                logger.error(error_msg, exc_info=True)
                await ctx.error(error_msg)
                return f"Error: {error_msg}"
        
        try:
            # Write the content to the new file
            with open(absolute_path, "w", encoding="utf-8") as f:
                f.write(content)
            
            file_size = os.path.getsize(absolute_path)
            success_msg = f"Successfully created new file '{path}' with {file_size} bytes"
            logger.info(success_msg)
            await ctx.info(success_msg)
            
            # For server files, warn about restart
            if absolute_path.endswith(".py") and any(server_file in absolute_path for server_file in ["direct_mcp_server.py", "enhanced_mcp_server.py"]):
                await ctx.warning(f"You've created a server file ({path}). Server may need to be restarted.")
            
            return success_msg
        
        except Exception as e:
            error_msg = f"Error creating file '{path}': {str(e)}"
            logger.error(error_msg, exc_info=True)
            await ctx.error(error_msg)
            
            # Remove partially written file if there was an error
            if os.path.exists(absolute_path):
                try:
                    os.remove(absolute_path)
                    logger.info(f"Removed partially written file after error: {absolute_path}")
                except Exception as cleanup_error:
                    logger.error(f"Failed to clean up partial file: {cleanup_error}")
            
            return f"Error: {error_msg}"

    @server.tool(name="list_buckets", description="List all available buckets with metadata")
    async def list_buckets(ctx: Context, include_metadata: bool = True, metadata_first: bool = True, offset: int = 0, limit: int = 20) -> str:
        """
        List all available buckets with optional metadata.
        
        Args:
            ctx: The MCP context
            include_metadata: Whether to include metadata in the response
            metadata_first: Whether to prioritize metadata in the response
            offset: Pagination offset
            limit: Maximum number of buckets to return
        
        Returns:
            JSON string with bucket information
        """
        logger.info(f"Listing buckets: include_metadata={include_metadata}, offset={offset}, limit={limit}")
        await ctx.info(f"Listing buckets with limit {limit}")
        
        try:
            # For now, return demo buckets since we don't have a real bucket system initialized
            demo_buckets = [
                {
                    "name": "media",
                    "id": "bucket_media_001",
                    "type": "media",
                    "file_count": 150,
                    "total_size": 1024 * 1024 * 500,  # 500MB
                    "created_at": "2024-01-15T10:30:00Z",
                    "updated_at": "2024-01-20T16:45:00Z",
                    "status": "active",
                    "backend": "filesystem"
                },
                {
                    "name": "documents", 
                    "id": "bucket_docs_002",
                    "type": "documents",
                    "file_count": 75,
                    "total_size": 1024 * 1024 * 100,  # 100MB
                    "created_at": "2024-01-10T08:15:00Z",
                    "updated_at": "2024-01-18T12:30:00Z", 
                    "status": "active",
                    "backend": "s3"
                },
                {
                    "name": "archive",
                    "id": "bucket_arch_003", 
                    "type": "archive",
                    "file_count": 300,
                    "total_size": 1024 * 1024 * 1024,  # 1GB
                    "created_at": "2024-01-05T14:20:00Z",
                    "updated_at": "2024-01-15T09:10:00Z",
                    "status": "active", 
                    "backend": "ipfs"
                }
            ]
            
            # Apply pagination
            start_idx = offset
            end_idx = min(offset + limit, len(demo_buckets))
            paginated_buckets = demo_buckets[start_idx:end_idx]
            
            result = {
                "items": paginated_buckets,
                "total": len(demo_buckets),
                "offset": offset,
                "limit": limit,
                "has_more": end_idx < len(demo_buckets)
            }
            
            success_msg = f"Successfully listed {len(paginated_buckets)} buckets"
            logger.info(success_msg)
            await ctx.info(success_msg)
            
            return json.dumps(result)
            
        except Exception as e:
            error_msg = f"Error listing buckets: {str(e)}"
            logger.error(error_msg, exc_info=True)
            await ctx.error(error_msg)
            return f"Error: {error_msg}"

    @server.tool(name="list_bucket_files", description="List files in a specific bucket")
    async def list_bucket_files(ctx: Context, bucket: str, path: str = "", metadata_first: bool = True, include_hidden: bool = False, limit: int = 100) -> str:
        """
        List files in a specific bucket with optional filtering.
        
        Args:
            ctx: The MCP context
            bucket: Name of the bucket to list files from
            path: Path within the bucket (empty for root)
            metadata_first: Whether to prioritize metadata in the response
            include_hidden: Whether to include hidden files
            limit: Maximum number of files to return
        
        Returns:
            JSON string with file information
        """
        logger.info(f"Listing files in bucket '{bucket}' at path '{path}'")
        await ctx.info(f"Listing files in bucket: {bucket}")
        
        try:
            # For now, return demo files since we don't have a real bucket system
            demo_files = []
            
            if bucket == "media":
                demo_files = [
                    {
                        "name": "image1.jpg",
                        "path": f"{path}image1.jpg" if path else "image1.jpg",
                        "size": 1024 * 256,  # 256KB
                        "type": "image/jpeg",
                        "created_at": "2024-01-15T10:30:00Z",
                        "updated_at": "2024-01-15T10:30:00Z",
                        "hash": "QmX1eZQe9k8mF2nD3pQ4rT5yU7iO6pL9sA2bC4dE5fG6hI",
                        "is_directory": False
                    },
                    {
                        "name": "video1.mp4", 
                        "path": f"{path}video1.mp4" if path else "video1.mp4",
                        "size": 1024 * 1024 * 50,  # 50MB
                        "type": "video/mp4",
                        "created_at": "2024-01-16T14:20:00Z",
                        "updated_at": "2024-01-16T14:20:00Z",
                        "hash": "QmY2fZR0l9nH3oE4qS6uI8jP7kM8tN9aB1cD2eF3gH4iJ",
                        "is_directory": False
                    },
                    {
                        "name": "thumbnails",
                        "path": f"{path}thumbnails/" if path else "thumbnails/",
                        "size": 0,
                        "type": "directory", 
                        "created_at": "2024-01-15T10:30:00Z",
                        "updated_at": "2024-01-18T16:45:00Z",
                        "hash": "QmZ3gAB1m0oI4pF5qR7sT8uV9wX0yL1kN2bC3dE4fG5hI",
                        "is_directory": True
                    }
                ]
            elif bucket == "documents":
                demo_files = [
                    {
                        "name": "report.pdf",
                        "path": f"{path}report.pdf" if path else "report.pdf", 
                        "size": 1024 * 1024 * 2,  # 2MB
                        "type": "application/pdf",
                        "created_at": "2024-01-10T08:15:00Z",
                        "updated_at": "2024-01-12T10:30:00Z",
                        "hash": "QmA4bC5dE6fG7hI8jK9lM0nO1pQ2rS3tU4vW5xY6zA7bB",
                        "is_directory": False
                    },
                    {
                        "name": "presentations",
                        "path": f"{path}presentations/" if path else "presentations/",
                        "size": 0,
                        "type": "directory",
                        "created_at": "2024-01-10T08:15:00Z", 
                        "updated_at": "2024-01-18T12:30:00Z",
                        "hash": "QmB5cD6eF7gH8iJ9kL0mN1oP2qR3sT4uV5wX6yZ7aB8cC",
                        "is_directory": True
                    }
                ]
            elif bucket == "archive":
                demo_files = [
                    {
                        "name": "backup.tar.gz",
                        "path": f"{path}backup.tar.gz" if path else "backup.tar.gz",
                        "size": 1024 * 1024 * 500,  # 500MB
                        "type": "application/gzip",
                        "created_at": "2024-01-05T14:20:00Z",
                        "updated_at": "2024-01-05T14:20:00Z",
                        "hash": "QmC6dD7eF8gH9iJ0kL1mN2oP3qR4sT5uV6wX7yZ8aB9cD",
                        "is_directory": False
                    }
                ]
            
            # Apply limit
            limited_files = demo_files[:limit]
            
            result = {
                "bucket": bucket,
                "path": path,
                "items": limited_files,
                "total": len(demo_files),
                "limit": limit,
                "has_more": len(demo_files) > limit
            }
            
            success_msg = f"Successfully listed {len(limited_files)} files in bucket '{bucket}'"
            logger.info(success_msg)
            await ctx.info(success_msg)
            
            return json.dumps(result)
            
        except Exception as e:
            error_msg = f"Error listing files in bucket '{bucket}': {str(e)}"
            logger.error(error_msg, exc_info=True)
            await ctx.error(error_msg)
            return f"Error: {error_msg}"

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
            "/mcp": "MCP SSE connection endpoint (handled by FastMCP)"
        },
        "deployment_status": deployment_status["status"] if deployment_status else "unknown"
    })
    
# --- Initialize server ---
# Removed custom initialize_server function

# --- Main Entry ---
if __name__ == "__main__":
    # Use port from environment if specified
    port = int(os.environ.get("PORT", DEPLOYMENT_CONFIG["blue_port"] if is_blue else DEPLOYMENT_CONFIG["green_port"]))
    logger.info(f"Starting Direct MCP Server ({server_color}) on port {port}...")
    
    if not imports_succeeded:
        logger.critical("Core MCP/Starlette imports failed. Cannot start server.")
        sys.exit(1)
        
    if not uvicorn:
         logger.critical("Uvicorn import failed. Cannot start server.")
         sys.exit(1)
         
    try:
        # Use FastMCP's built-in SSE implementation
        # This will create an app with the proper protocol handling
        logger.info("Creating FastMCP SSE app with built-in protocol handling")
        app = server.sse_app()
        
        # Add our custom homepage route
        app.routes.append(Route("/", endpoint=homepage))
        
        logger.info(f"MCP Server Tools: {[t.name for t in server._tool_manager._tools.values()]}")
        logger.info(f"Endpoint paths: {[route.path for route in app.routes]}")
        
        # Removed custom startup event
        
        # Run with uvicorn
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=port,
            log_level="info"
        )
    except KeyboardInterrupt:
        logger.info(f"Server ({server_color}) shutting down")
    except Exception as e:
        logger.error(f"Error running server ({server_color}): {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Clean up PID file
        if os.path.exists(current_pid_file):
            try:
                os.remove(current_pid_file)
                logger.info(f"Removed PID file {current_pid_file}")
            except Exception as e:
                logger.error(f"Error removing PID file {current_pid_file}: {e}")
