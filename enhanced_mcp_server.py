#!/usr/bin/env python3
"""
Enhanced MCP server refactored to use the FastMCP SDK.

This script starts an MCP server using the FastMCP library, aiming for
better compatibility with standard MCP clients.
Implements explicit restart logic within tools.
"""

import os
import sys
import logging
import time
import asyncio
import subprocess
import shutil  # For file moving
import py_compile # For syntax checking
import signal # For triggering restart
import tempfile # For ipfs add tool
import base64 # For ipfs add tool content decoding
import json # For list_ipfs_pins
from typing import Dict, List, Any, Optional, Union  # For type hints
from urllib.parse import urlparse # For CORS check
from starlette.responses import JSONResponse  # Add import for JSONResponse

# Add SDK path and import necessary components
# Construct path relative to the current working directory
cwd = os.getcwd()
sdk_path = os.path.abspath(os.path.join(cwd, "docs/mcp-python-sdk/src"))
if os.path.isdir(sdk_path):
    if sdk_path not in sys.path:
        sys.path.insert(0, sdk_path)
        print(f"INFO: Added SDK path to sys.path: {sdk_path}")
else:
    print(f"ERROR: SDK path not found: {sdk_path}")
    SDK_AVAILABLE = False
    sys.exit(1)

try:
    import uvicorn
    from mcp.server.fastmcp import FastMCP, Context
    from mcp.server.fastmcp.exceptions import ResourceError # Corrected import
    from mcp.types import Tool, Resource, ResourceTemplate # Import specific types if needed later
    from starlette.routing import Route # No longer needed
    from mcp.types import Tool, Resource, ResourceTemplate # For type hinting
    SDK_AVAILABLE = True
    print("INFO: MCP SDK (FastMCP) imported successfully.")
except ImportError as e:
    # Need to configure logging before using logger
    logging.basicConfig(level=logging.ERROR) # Basic config for error logging
    temp_logger = logging.getLogger(__name__)
    temp_logger.error(f"Failed to import MCP SDK (FastMCP) or Starlette: {e}. Cannot run server.")
    print(f"ERROR: Failed to import MCP SDK (FastMCP) or Starlette: {e}. Cannot run server.")
    SDK_AVAILABLE = False
    sys.exit(1) # Exit if SDK is crucial and not found

# Configure logging (using standard logging, FastMCP might reconfigure)
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "enhanced_mcp_server_sdk.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout) # Also log to console
    ],
    force=True # Force reconfiguration if basicConfig was called earlier
)
logger = logging.getLogger(__name__) # Get logger after basicConfig

# --- IPFS Helper Functions (Keep for potential use in tools/resources) ---
def check_ipfs_daemon():
    """Check if IPFS daemon is running."""
    try:
        # Use absolute path if necessary, assuming ipfs is in PATH
        result = subprocess.run(["ipfs", "version"],
                              capture_output=True,
                              text=True,
                              timeout=5)
        is_running = result.returncode == 0
        logger.debug(f"IPFS daemon check: {'Running' if is_running else 'Not Running'} (Code: {result.returncode})")
        return is_running
    except FileNotFoundError:
        logger.error("IPFS command not found. Make sure IPFS is installed and in PATH.")
        return False
    except Exception as e:
        logger.error(f"Error checking IPFS daemon: {e}")
        return False

def start_ipfs_daemon():
    """Start the IPFS daemon if not running."""
    if not check_ipfs_daemon():
        logger.info("IPFS daemon not running, attempting to start...")
        try:
            # Use absolute path if necessary
            # Start daemon in background
            process = subprocess.Popen(["ipfs", "daemon", "--routing=dhtclient"],
                           stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
            logger.info(f"IPFS daemon process started (PID: {process.pid}). Waiting for initialization...")
            # Wait a moment for it to initialize
            time.sleep(5) # Increased wait time
            if check_ipfs_daemon():
                logger.info("IPFS daemon started successfully.")
                return True
            else:
                logger.error("IPFS daemon failed to start or initialize correctly.")
                # Log stderr if available
                stderr_output = process.stderr.read().decode('utf-8', errors='replace') if process.stderr else "N/A"
                logger.error(f"IPFS daemon stderr: {stderr_output}")
                return False
        except FileNotFoundError:
             logger.error("IPFS command not found. Cannot start daemon.")
             return False
        except Exception as e:
            logger.error(f"Error starting IPFS daemon: {e}")
            return False
    else:
        logger.info("IPFS daemon already running.")
        return True

def run_ipfs_command(command, input_data=None):
    """Run an IPFS command and return the result."""
    logger.debug(f"Running IPFS command: {' '.join(command)}")
    try:
        full_command = ["ipfs"] + command
        if input_data:
            result = subprocess.run(full_command,
                                  input=input_data,
                                  capture_output=True,
                                  timeout=60) # Increased timeout for potentially long ops
        else:
            result = subprocess.run(full_command,
                                  capture_output=True,
                                  timeout=60) # Increased timeout

        if result.returncode == 0:
            logger.debug(f"IPFS command successful. Output: {result.stdout[:100]}...") # Log truncated output
            return {"success": True, "output": result.stdout}
        else:
            error_output = result.stderr.decode('utf-8', errors='replace')
            logger.error(f"IPFS command failed (Code: {result.returncode}). Error: {error_output}")
            return {"success": False, "error": error_output}
    except subprocess.TimeoutExpired:
        logger.error(f"IPFS command {' '.join(command)} timed out.")
        return {"success": False, "error": "IPFS command timed out"}
    except Exception as e:
        logger.error(f"Error running IPFS command {' '.join(command)}: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


# --- FastMCP Server Definition ---
if not SDK_AVAILABLE:
    logger.critical("Exiting because MCP SDK is not available.")
    sys.exit(1)

# Instantiate FastMCP server
# Name and version can be set here. Settings like host/port/debug come from env vars (FASTMCP_*) or defaults.
server = FastMCP(
    name="enhanced-mcp-server-sdk",
    instructions="MCP server refactored using FastMCP SDK."
    # Add other settings if needed, e.g., debug=True
)
logger.info(f"FastMCP server '{server.name}' instantiated.")
logger.info(f"FastMCP settings: {server.settings.model_dump()}")


# --- MCP Tools ---

@server.tool(name="sdk_dummy_tool", description="A placeholder tool via SDK.")
def sdk_dummy_tool_handler(message: str = "default message") -> str:
    """A simple dummy tool implementation."""
    logger.info(f"Executing sdk_dummy_tool with message: {message}")
    return f"Dummy tool executed with message: {message}"

@server.tool(name="hello_world_tool", description="A simple hello world tool.")
def hello_world_tool_handler(name: str = "World") -> str:
    """Returns a greeting."""
    logger.info(f"Executing hello_world_tool with name: {name}")
    return f"Hello, {name}!"

@server.tool(name="list_directory", description="Lists files and directories in a given path.")
async def list_directory(ctx: Context, path: str = ".") -> str:
    """Lists directory contents."""
    logger.info(f"Executing list_directory for path: {path}")
    await ctx.info(f"Listing directory: {path}")
    try:
        # Basic security check: ensure path is relative and within project
        project_root = os.getcwd()
        absolute_path = os.path.abspath(os.path.join(project_root, path))
        if not absolute_path.startswith(project_root):
             error_msg = f"Error: Path '{path}' is outside the allowed project directory."
             logger.error(error_msg)
             await ctx.error(error_msg)
             return error_msg

        if not os.path.isdir(absolute_path):
            error_msg = f"Error: Path '{path}' is not a valid directory."
            logger.error(error_msg)
            await ctx.error(error_msg)
            return error_msg

        entries = os.listdir(absolute_path)
        result_str = f"Contents of '{path}':\n" + "\n".join(entries)
        await ctx.info(f"Found {len(entries)} entries in '{path}'.")
        return result_str
    except Exception as e:
        error_msg = f"Error listing directory '{path}': {e}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return f"Error: {error_msg}"

@server.tool(name="ipfs_version_tool", description="Gets the version of the connected IPFS daemon.")
async def get_ipfs_version(ctx: Context) -> str:
    """Tool to get IPFS version using helper function."""
    logger.info("Executing ipfs_version_tool")
    if not check_ipfs_daemon():
         await ctx.error("IPFS daemon is not running.")
         return "Error: IPFS daemon not running."
    try:
        result = run_ipfs_command(["version"])
        if result["success"]:
            version_str = result["output"].decode('utf-8').strip()
            await ctx.info(f"IPFS Version: {version_str}")
            return version_str
        else:
            error_msg = f"Failed to get IPFS version. Error: {result['error']}"
            await ctx.error(error_msg)
            return f"Error: {error_msg}"
    except Exception as e:
        error_msg = f"Exception getting IPFS version: {e}"
        await ctx.error(error_msg)
        logger.error(error_msg, exc_info=True)
        return f"Error: {error_msg}"

@server.tool(name="edit_file", description="Edits a file after performing syntax and pytest checks.")
async def edit_file(ctx: Context, path: str, content: str) -> str:
    """
    Writes content to a file after checking Python syntax and running pytest.
    Performs checks using a temporary file.
    If py_compile fails, returns error and does not save.
    If pytest fails, returns warning and does NOT save changes or restart.
    If pytest passes, saves file and triggers server restart via SIGTERM.
    Restricted to local origins.
    """
    logger.info(f"Received request to edit file: {path}")

    # --- CORS Check ---
    origin = None
    is_local = False
    try:
        # Attempt to access headers from context metadata
        if ctx._request_context and hasattr(ctx._request_context, 'meta') and ctx._request_context.meta:
             headers = ctx._request_context.meta.get("headers", {})
             origin = headers.get("origin")
             if origin:
                 parsed_origin = urlparse(origin)
                 if parsed_origin.hostname in ["localhost", "127.0.0.1"]:
                     is_local = True
                 elif origin == "null":
                      is_local = True
             else:
                 is_local = True
                 logger.warning("No Origin header found, assuming local request for edit_file.")
        else:
             is_local = True
             logger.warning("Could not access request metadata for origin check, assuming local.")
    except Exception as e:
        logger.warning(f"Could not determine request origin: {e}. Assuming local for safety.")
        is_local = True

    if not is_local:
        error_msg = f"Error: File editing is restricted to local origins. Origin: {origin}"
        logger.error(error_msg)
        await ctx.error(error_msg)
        return error_msg
    # --- End CORS Check ---

    await ctx.info(f"Attempting to edit file: {path} (Origin: {origin or 'Unknown'})")

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
    backup_path = absolute_path + ".bak" # Keep backup logic for safety during test run
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
            temp_file_for_test = absolute_path + ".pytest_test" # Use a different temp name
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
                # Modify command to potentially target the specific test file if applicable
                # For now, running all tests
                result = subprocess.run(
                    [pytest_path],
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
                    logger.error(error_msg + "\n" + pytest_output)
                    await ctx.warning(f"Pytest check failed for '{path}'. Changes NOT saved. See server logs for details.")
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
                # Restore original from backup if it exists (regardless of test outcome now)
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
            # Trigger graceful shutdown for restart
            pid = os.getpid()
            logger.warning(f"Tests passed for '{path}'. Triggering server restart (PID: {pid})...")
            await ctx.info("Tests passed. Triggering server restart...")
            asyncio.create_task(delayed_shutdown(pid, 1)) # Use original restart logic
            return success_msg + " Server restarting."
        else:
            # Pytest failed or syntax check skipped for non-python file. Do not save.
            warning_msg = f"Checks failed for '{path}'. Changes were NOT saved."
            if not syntax_check_passed: # Should not happen due to earlier return
                 warning_msg = f"Syntax check failed for '{path}'. Changes were NOT saved."
            elif not pytest_passed:
                 warning_msg = f"Pytest failed for '{path}'. Changes were NOT saved. See server logs for details."

            logger.warning(warning_msg)
            # Warning already sent via ctx.warning if pytest failed
            if syntax_check_passed and not pytest_passed:
                 pass # Warning already sent
            else: # Send warning if only syntax check was skipped or if internal error
                 await ctx.warning(warning_msg)
            _cleanup_temp_files(temp_path) # Ensure temp file is removed
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

@server.tool(name="patch_file", description="Replaces a slice of lines in a file after checks.")
async def patch_file(ctx: Context, path: str, start_line: int, line_count_to_replace: int, new_lines_content: str) -> str:
    """
    Replaces a specific range of lines in a file.
    Performs syntax and pytest checks before saving.
    Restricted to local origins.
    """
    logger.info(f"Received request to patch file: {path} from line {start_line} for {line_count_to_replace} lines.")
    await ctx.info(f"Attempting to patch file: {path}")

    # --- CORS Check (same as edit_file) ---
    origin = None
    is_local = False
    try:
        if ctx._request_context and hasattr(ctx._request_context, 'meta') and ctx._request_context.meta:
             headers = ctx._request_context.meta.get("headers", {})
             origin = headers.get("origin")
             if origin:
                 parsed_origin = urlparse(origin)
                 if parsed_origin.hostname in ["localhost", "127.0.0.1"]:
                     is_local = True
                 elif origin == "null":
                      is_local = True
             else:
                 is_local = True
                 logger.warning("No Origin header found, assuming local request for patch_file.")
        else:
             is_local = True
             logger.warning("Could not access request metadata for origin check, assuming local.")
    except Exception as e:
        logger.warning(f"Could not determine request origin: {e}. Assuming local for safety.")
        is_local = True

    if not is_local:
        error_msg = f"Error: File patching is restricted to local origins. Origin: {origin}"
        logger.error(error_msg)
        await ctx.error(error_msg)
        return error_msg
    # --- End CORS Check ---

    project_root = os.getcwd()
    absolute_path = os.path.abspath(os.path.join(project_root, path))
    if not absolute_path.startswith(project_root):
        error_msg = f"Error: Path '{path}' is outside the allowed project directory."
        logger.error(error_msg); await ctx.error(error_msg); return error_msg
    if not os.path.isfile(absolute_path):
        error_msg = f"Error: File not found at path '{path}'."
        logger.error(error_msg); await ctx.error(error_msg); return error_msg

    # Validate line numbers
    if start_line < 1:
        error_msg = "Error: start_line must be 1 or greater."
        logger.error(error_msg); await ctx.error(error_msg); return error_msg
    if line_count_to_replace < 0:
        error_msg = "Error: line_count_to_replace cannot be negative."
        logger.error(error_msg); await ctx.error(error_msg); return error_msg

    temp_path = absolute_path + ".patch.tmp"
    backup_path = absolute_path + ".bak"
    pytest_passed = False
    test_error = None
    syntax_check_passed = False
    original_exists = os.path.exists(absolute_path) # Check before try block

    try:
        # Read original content
        with open(absolute_path, "r", encoding="utf-8") as f:
            original_lines = f.readlines()

        # Calculate slice indices (0-based)
        start_index = start_line - 1
        end_index = start_index + line_count_to_replace

        # Validate slice indices against file length
        if start_index > len(original_lines):
             error_msg = f"Error: start_line ({start_line}) is beyond the end of the file ({len(original_lines)} lines)."
             logger.error(error_msg); await ctx.error(error_msg); return error_msg
        # Allow replacing past the end (effectively appending) but cap end_index
        end_index = min(end_index, len(original_lines))

        # Construct new content
        new_lines_list = new_lines_content.splitlines(keepends=True)
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
                logger.error(error_msg); await ctx.error(error_msg); _cleanup_temp_files(temp_path); return f"Error: {error_msg}"
            except Exception as e:
                error_msg = f"Error during syntax check for patched '{path}': {e}"
                logger.error(error_msg, exc_info=True); await ctx.error(error_msg); _cleanup_temp_files(temp_path); return f"Error: {error_msg}"
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
                if not os.path.exists(pytest_path): pytest_path = "pytest"

                logger.debug(f"Backing up {absolute_path} to {backup_path}")
                shutil.copy2(absolute_path, backup_path) # Backup original

                logger.debug(f"Copying {temp_path} to {temp_file_for_test} for pytest.")
                shutil.copy2(temp_path, temp_file_for_test) # Test on a separate copy

                logger.info(f"Running pytest command: {pytest_path}")
                result = subprocess.run([pytest_path], cwd=project_root, capture_output=True, text=True, timeout=120)
                pytest_output = f"Output:\n{result.stdout}\n{result.stderr}"

                if result.returncode == 0:
                    logger.info(f"Pytest passed for potential patch to {path}"); await ctx.info(f"Pytest check passed for {path}."); pytest_passed = True
                else:
                    error_msg = f"Pytest check failed for patched '{path}' (exit code {result.returncode})."
                    logger.error(error_msg + "\n" + pytest_output); await ctx.warning(f"Pytest check failed for '{path}'. Changes NOT saved. See server logs."); pytest_passed = False
            except Exception as e:
                error_msg = f"Error during pytest check for patched '{path}': {e}"
                logger.error(error_msg, exc_info=True); await ctx.error(error_msg); pytest_passed = False; test_error = e
            finally:
                _cleanup_temp_files(temp_file_for_test)
                if os.path.exists(backup_path): shutil.move(backup_path, absolute_path) # Always restore original after test
                _cleanup_temp_files(backup_path)
                if test_error: raise test_error
        else:
             logger.error("Reached pytest block unexpectedly after syntax check failure.")
             _cleanup_temp_files(temp_path); return "Internal Server Error: Logic flow issue in patch_file."

        # 4. Final Outcome
        if pytest_passed:
            logger.info(f"Checks passed. Saving patch to {absolute_path}")
            shutil.move(temp_path, absolute_path) # Apply the patch
            success_msg = f"Successfully patched, checked, and saved file: {path}"
            logger.info(success_msg); await ctx.info(success_msg)
            # Trigger graceful shutdown for restart
            pid = os.getpid()
            logger.warning(f"Tests passed for '{path}'. Triggering server restart (PID: {pid})...")
            await ctx.info("Tests passed. Triggering server restart...")
            asyncio.create_task(delayed_shutdown(pid, 1)) # Use original restart logic
            return success_msg + " Server restarting."
        else:
            warning_msg = f"Checks failed for '{path}'. Patch NOT applied."
            logger.warning(warning_msg)
            if syntax_check_passed and not pytest_passed: pass # Warning already sent
            else: await ctx.warning(warning_msg)
            _cleanup_temp_files(temp_path) # Remove the temp file with the patch
            return warning_msg

    except IOError as e:
        error_msg = f"File I/O error patching '{path}': {e}"
        logger.error(error_msg, exc_info=True); await ctx.error(error_msg); _cleanup_temp_files(temp_path, backup_path); return f"Error: {error_msg}"
    except Exception as e:
        error_msg = f"Unexpected error patching '{path}': {e}"
        logger.error(error_msg, exc_info=True); await ctx.error(error_msg); _cleanup_temp_files(temp_path, backup_path); return f"Error: {error_msg}"


@server.tool(name="add_ipfs_file", description="Adds a file to IPFS.")
async def add_ipfs_file(ctx: Context, filename: str, content_b64: str) -> str:
    """Adds file content (base64 encoded) to IPFS."""
    logger.info(f"Executing add_ipfs_file for filename: {filename}")
    if not check_ipfs_daemon():
         await ctx.error("IPFS daemon is not running.")
         return "Error: IPFS daemon not running."

    try:
        content_bytes = base64.b64decode(content_b64)
        logger.debug(f"Decoded {len(content_bytes)} bytes for {filename}")
    except Exception as e:
        error_msg = f"Error decoding base64 content for {filename}: {e}"
        logger.error(error_msg)
        await ctx.error(error_msg)
        return f"Error: {error_msg}"

    # Write to a temporary file to use ipfs add command
    temp_file_path = None # Initialize in case of early error
    try:
        # Use mkstemp for better temp file handling
        fd, temp_file_path = tempfile.mkstemp(prefix=f"mcp_ipfs_add_{filename}_")
        logger.debug(f"Created temporary file: {temp_file_path}")
        with os.fdopen(fd, "wb") as temp_file:
            temp_file.write(content_bytes)

        result = run_ipfs_command(["add", "-q", temp_file_path])

        if result["success"]:
            cid = result["output"].decode('utf-8').strip()
            success_msg = f"Successfully added '{filename}' to IPFS. CID: {cid}"
            logger.info(success_msg)
            await ctx.info(success_msg)
            return success_msg
        else:
            error_msg = f"Failed to add '{filename}' to IPFS. Error: {result['error']}"
            logger.error(error_msg)
            await ctx.error(error_msg)
            return f"Error: {error_msg}"
    except Exception as e:
        error_msg = f"Error during IPFS add process for {filename}: {e}"
        logger.error(error_msg, exc_info=True)
        await ctx.error(error_msg)
        return f"Error: {error_msg}"
    finally:
        _cleanup_temp_files(temp_file_path) # Ensure cleanup

@server.tool(name="pin_ipfs_cid", description="Pins a CID recursively in IPFS.")
async def pin_ipfs_cid(ctx: Context, cid: str) -> str:
    """Pins the given CID in IPFS."""
    logger.info(f"Executing pin_ipfs_cid for CID: {cid}")
    if not check_ipfs_daemon():
         await ctx.error("IPFS daemon is not running.")
         return "Error: IPFS daemon not running."

    try:
        result = run_ipfs_command(["pin", "add", cid])
        if result["success"]:
            success_msg = f"Successfully pinned CID: {cid}"
            logger.info(success_msg)
            await ctx.info(success_msg)
            # The output of pin add often includes 'pinned <cid> recursively'
            return result["output"].decode('utf-8').strip()
        else:
            error_msg = f"Failed to pin CID {cid}. Error: {result['error']}"
            logger.error(error_msg)
            await ctx.error(error_msg)
            return f"Error: {error_msg}"
    except Exception as e:
        error_msg = f"Exception pinning CID {cid}: {e}"
        await ctx.error(error_msg)
        logger.error(error_msg, exc_info=True)
        return f"Error: {error_msg}"

@server.tool(name="list_ipfs_pins", description="Lists recursively pinned CIDs in IPFS.")
async def list_ipfs_pins(ctx: Context) -> str:
    """Lists recursively pinned CIDs."""
    logger.info("Executing list_ipfs_pins")
    if not check_ipfs_daemon():
         await ctx.error("IPFS daemon is not running.")
         return "Error: IPFS daemon not running."

    try:
        result = run_ipfs_command(["pin", "ls", "--type=recursive", "-q"]) # Quiet mode for just CIDs
        if result["success"]:
            pins = result["output"].decode('utf-8').strip().split('\\n')
            pins = [p for p in pins if p] # Remove empty lines if any
            success_msg = f"Found {len(pins)} pinned items."
            logger.info(success_msg)
            await ctx.info(success_msg)
            return json.dumps({"pinned_cids": pins}) # Return as JSON string
        else:
            error_msg = f"Failed to list pins. Error: {result['error']}"
            logger.error(error_msg)
            await ctx.error(error_msg)
            return f"Error: {error_msg}"
    except Exception as e:
        error_msg = f"Exception listing pins: {e}"
        await ctx.error(error_msg)
        logger.error(error_msg, exc_info=True)
        return f"Error: {error_msg}"


# --- MCP Resources ---

@server.resource(uri="ipfs://{cid}", name="IPFS Content", description="Retrieves content from IPFS using CID.")
async def ipfs_cat_resource(cid: str) -> bytes:
    """Resource handler to get content from IPFS."""
    logger.info(f"Reading IPFS resource for CID: {cid}")
    if not check_ipfs_daemon():
        logger.error("IPFS daemon not running for ipfs_cat_resource")
        raise ResourceError("IPFS daemon is not running.")

    try:
        result = run_ipfs_command(["cat", cid])
        if result["success"]:
            logger.info(f"Successfully retrieved content for CID: {cid}")
            return result["output"] # Return raw bytes
        else:
            error_msg = f"Failed to retrieve content for CID {cid}. Error: {result['error']}"
            logger.error(error_msg)
            raise ResourceError(error_msg)
    except Exception as e:
        error_msg = f"Exception retrieving content for CID {cid}: {e}"
        logger.error(error_msg, exc_info=True)
        raise ResourceError(error_msg)


# --- End FastMCP Server Definition ---

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

def _cleanup_temp_files(*paths):
    """Safely remove temporary files."""
    for path in paths:
        if path and os.path.exists(path):
            try:
                os.remove(path)
                logger.debug(f"Cleaned up temporary file: {path}")
            except OSError as e:
                logger.error(f"Error removing temporary file {path}: {e}")


# --- Add Root Route Handler ---
async def homepage(request):
    """Simple handler for the root path."""
    logger.info("Received request for root path /")
    # Access server name and version via the global 'server' instance
    return JSONResponse({'message': f'{server.name} is running', 'version': server._mcp_server.version or 'dev'})

# --- App Factory for Uvicorn Reload ---
def create_app():
    """Factory function to create the Starlette app for Uvicorn."""
    from starlette.middleware.cors import CORSMiddleware
    from starlette.responses import JSONResponse
    
    logger.info("Creating Starlette app instance via factory...")
    
    # Create SSE app without the cors_origins parameter that was causing the error
    starlette_app = server.sse_app()
    
    # Add the custom root route
    starlette_app.routes.insert(0, Route("/", endpoint=homepage))
    logger.info("Added custom root route to Starlette app.")
    
    # Add CORS middleware separately
    starlette_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*", "http://localhost:*", "http://127.0.0.1:*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.info("Added CORS middleware to Starlette app.")
    
    # Add middleware to ensure proper SSE content type
    @starlette_app.middleware("http")
    async def ensure_sse_content_type(request, call_next):
        response = await call_next(request)
        # Check if the path is for SSE endpoints
        if request.url.path.startswith("/mcp"):
            # Ensure SSE content type is properly set
            response.headers.setdefault("Content-Type", "text/event-stream")
            response.headers.setdefault("Cache-Control", "no-cache")
            response.headers.setdefault("Connection", "keep-alive")
            logger.debug(f"Ensured SSE headers for path: {request.url.path}")
        return response
        
    return starlette_app

# --- Main execution block ---
if __name__ == "__main__":
    logger.info("Starting MCP Server script...")

    # Ensure IPFS daemon is running (optional, but good practice if tools need it)
    logger.info("Checking IPFS daemon status before starting server...")
    if not start_ipfs_daemon():
        logger.warning("IPFS daemon could not be started. Some tools/resources might fail.")

    # Run server using Uvicorn with the factory function and reload disabled
    logger.info(f"Starting FastMCP server '{server.name}' with SSE transport via Uvicorn...")
    try:
        # Use the app factory directly with uvicorn
        uvicorn.run(
            "enhanced_mcp_server:create_app",
            host=server.settings.host,
            port=server.settings.port,
            log_level=server.settings.log_level.lower(),
            reload=False, # Explicitly disable reload
            factory=True
        )
        # If uvicorn.run exits cleanly, it might be unexpected unless stopped manually
        logger.info("Uvicorn server run() method finished.")
    except (SystemExit, KeyboardInterrupt):
        # Expected exit path when SIGTERM is received by FastMCP/Uvicorn
        logger.info("Server received shutdown signal (SystemExit/KeyboardInterrupt). Exiting cleanly.")
        sys.exit(0) # Ensure clean exit code
    except Exception as e:
        sys.exit(1)

    logger.info("MCP server finished (unexpectedly?).")
