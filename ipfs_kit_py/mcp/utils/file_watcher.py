"""
File watching utility for MCP server.

This module provides functionality to watch for file changes
and automatically restart the MCP server when changes are detected.
"""

import os
import sys
import time
import threading
import logging
import traceback
import importlib
import subprocess
import py_compile
from typing import List, Set, Dict, Any, Optional, Callable, Type
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Import dashboard
try:
    from ipfs_kit_py.mcp.utils.dashboard import MCPDashboard

    HAS_DASHBOARD = True
except ImportError:
    HAS_DASHBOARD = False

# Configure logger
logger = logging.getLogger(__name__)


class MCPFileHandler(FileSystemEventHandler):
    """
    File system event handler for MCP server files.

    Monitors file changes and triggers server restart when Python files change.
    """
    def __init__(
        self,
        root_dirs: List[str],
        restart_callback: Callable,
        ignore_dirs: Optional[List[str]] = None,
        ignore_patterns: Optional[List[str]] = None,
        error_reporter: Optional[Callable] = None,
    ):
        """
        Initialize the file handler.

        Args:
            root_dirs: List of directories to watch
            restart_callback: Function to call when restart is needed
            ignore_dirs: List of directories to ignore (relative to root_dirs)
            ignore_patterns: List of file patterns to ignore (e.g., ["*.pyc", "*.log"])
            error_reporter: Optional callback to report errors
        """
        self.root_dirs = [os.path.abspath(d) for d in root_dirs]
        self.restart_callback = restart_callback
        self.error_reporter = error_reporter
        self.ignore_dirs = ignore_dirs or [
            "__pycache__",
            ".git",
            "venv",
            "env",
            "cache",
            "dist",
            "build",
            ".pytest_cache",
        ]
        self.ignore_patterns = ignore_patterns or [
            "*.pyc",
            "*.pyo",
            "*.pyd",
            "*.so",
            "*.log",
            "*.tmp",
            ".*",
            "*~",
        ]

        # Debounce mechanism to prevent multiple restart triggers for related changes
        self.last_restart_time = 0
        self.debounce_seconds = 2
        self.restart_lock = threading.Lock()

        # Track files with syntax errors to prevent restart loops
        self.files_with_errors: Set[str] = set()

        logger.info(f"Watching directories: {', '.join(self.root_dirs)}")
        logger.info(f"Ignoring directories: {', '.join(self.ignore_dirs)}")
        logger.info(f"Ignoring patterns: {', '.join(self.ignore_patterns)}")

    def on_modified(self, event):
        """Handle file modification events."""
        if not event.is_directory and self._should_process_file(event.src_path):
            logger.debug(f"Modified file: {event.src_path}")
            self._handle_file_change(event.src_path)

    def on_created(self, event):
        """Handle file creation events."""
        if not event.is_directory and self._should_process_file(event.src_path):
            logger.debug(f"Created file: {event.src_path}")
            self._handle_file_change(event.src_path)

    def _should_process_file(self, file_path: str) -> bool:
        """
        Determine if a file should trigger a restart.

        Args:
            file_path: Path to the file

        Returns:
            True if the file should be processed, False otherwise
        """
        # Skip non-Python files
        if not file_path.endswith(".py"):
            return False

        # Get absolute path
        abs_path = os.path.abspath(file_path)

        # Check if file is in one of the root directories
        in_root_dir = any(abs_path.startswith(root) for root in self.root_dirs)
        if not in_root_dir:
            return False

        # Check if file is in an ignored directory
        rel_path = os.path.relpath(abs_path, self.root_dirs[0])
        for ignore_dir in self.ignore_dirs:
            if f"/{ignore_dir}/" in f"/{rel_path}/":
                return False

        # Check if file matches an ignored pattern
        file_name = os.path.basename(file_path)
        for pattern in self.ignore_patterns:
            if pattern.startswith("*"):
                if file_name.endswith(pattern[1:]):
                    return False
            elif pattern.endswith("*"):
                if file_name.startswith(pattern[:-1]):
                    return False
            elif pattern == file_name:
                return False

        return True

    def _handle_file_change(self, file_path: str):
        """
        Handle a file change event.

        Args:
            file_path: Path to the modified file
        """
        # Apply debounce logic to avoid multiple restarts
        current_time = time.time()
        with self.restart_lock:
            if current_time - self.last_restart_time < self.debounce_seconds:
                logger.debug(f"Debouncing change to {file_path}")
                return

            # Check if file is syntactically valid
            has_syntax_errors, error_info = self._check_syntax(file_path)

            if has_syntax_errors:
                error_msg = f"Syntax error in {file_path}, not restarting server"
                logger.error(error_msg)

                # Report detailed error if available
                if error_info and self.error_reporter:
                    self.error_reporter(error_info, None)

                # Add to files with errors set
                self.files_with_errors.add(file_path)
                return

            # If file had errors before but is now fixed, log it
            if file_path in self.files_with_errors:
                success_msg = f"Syntax errors fixed in {file_path}"
                logger.info(success_msg)

                # Report error resolution
                if self.error_reporter:
                    self.error_reporter(f"✅ {success_msg}", None)

                self.files_with_errors.remove(file_path)

            # Check for dependency graph changes
            affected_modules = self._check_dependencies(file_path)
            if affected_modules:
                logger.info(
                    f"Change to {file_path} affects {len(affected_modules)} module(s): {', '.join(affected_modules)}"
                )

            # Trigger restart
            logger.info(f"File changed: {file_path}, restarting server")
            self.last_restart_time = current_time

            # Call the restart callback
            threading.Thread(
                target=self.restart_callback, args=(file_path, affected_modules)
            ).start()

    def _check_syntax(self, file_path: str) -> tuple:
        """
        Check the syntax of a Python file.

        Args:
            file_path: Path to the Python file

        Returns:
            Tuple of (has_errors, error_info)
        """
        try:
            # First try to compile the file using py_compile
            py_compile.compile(file_path, doraise=True)

            # Then try to import the module to catch import errors
            # This is important for catching missing dependencies
            import_result, import_error = self._can_import(file_path)
            if import_result:
                logger.debug(f"Syntax check passed for {file_path}")
                return False, None
            else:
                logger.warning(f"Import check failed for {file_path}")

                # Format import error information
                if import_error:
                    error_info = self._format_import_error(file_path, import_error)
                    return True, error_info
                return True, f"Unknown import error in {file_path}"

        except py_compile.PyCompileError as e:
            # Extract and format detailed error information
            error_msg = f"Syntax error in {file_path}:"
            logger.error(error_msg)

            # Extract file, line, column, and error message
            if hasattr(e, "file") and hasattr(e, "line") and hasattr(e, "msg"):
                code_context = self._get_code_context(file_path, e.line, context_lines=3)
                error_line = f"Line {e.line}: {e.msg}"
                logger.error(error_line)

                # Format code context with line numbers
                context_lines = []
                if code_context:
                    logger.error("Code context:")
                    for ctx_line_num, ctx_line in code_context:
                        prefix = ">> " if ctx_line_num == e.line else "   "
                        context_line = f"{prefix}{ctx_line_num}: {ctx_line}"
                        logger.error(context_line)
                        context_lines.append(context_line)

                # Construct detailed error information
                error_info = f"{error_msg}\n{error_line}\n\nCode context:\n" + "\n".join(
                    context_lines
                )
            else:
                # Fallback for older Python versions or different error format
                error_info = f"{error_msg}\n{str(e)}"
                logger.error(str(e))

            # Log full traceback at debug level
            

            logger.debug(f"Full traceback:\n{traceback.format_exc()}")

            return True, error_info

        except SyntaxError as e:
            # Handle SyntaxError directly
            error_msg = f"Syntax error in {file_path}:"
            logger.error(error_msg)

            # Format error with context
            formatted_error = self._format_syntax_error(file_path, e)
            return True, formatted_error

        except Exception as e:
            # Handle other exceptions
            error_msg = f"Error checking syntax of {file_path}: {str(e)}"
            logger.error(error_msg)

            # Format traceback and error details
            formatted_error = self._format_exception(file_path, e)
            return True, formatted_error

    def _format_syntax_error(self, file_path: str, error: SyntaxError) -> str:
        """Format a syntax error with context information."""
        error_lines = [f"Syntax error in {file_path}:"]

        if hasattr(error, "lineno") and hasattr(error, "msg"):
            error_lines.append(f"Line {error.lineno}: {error.msg}")

            # Get code context
            code_context = self._get_code_context(file_path, error.lineno, context_lines=3)

            # Format context if available
            if code_context:
                error_lines.append("\nCode context:")
                for ctx_line_num, ctx_line in code_context:
                    prefix = ">> " if ctx_line_num == error.lineno else "   "
                    error_lines.append(f"{prefix}{ctx_line_num}: {ctx_line}")

            # Add position indicator if available
            if hasattr(error, "text") and hasattr(error, "offset") and error.text and error.offset:
                indicator = " " * (error.offset + 3) + "^"  # +3 for the "   " prefix
                error_lines.append(f"   {error.text.rstrip()}")
                error_lines.append(f"{indicator}")

                # Try to suggest a fix
                suggested_fix = self._suggest_syntax_fix(error)
                if suggested_fix:
                    error_lines.append(f"\nSuggested fix: {suggested_fix}")
        else:
            error_lines.append(str(error))

        return "\n".join(error_lines)

    def _format_import_error(self, file_path: str, error_text: str) -> str:
        """Format an import error with helpful information."""
        # Extract useful information from import error text
        lines = [f"Import error in {file_path}:"]

        # Parse and categorize import error
        if "ModuleNotFoundError: No module named" in error_text:
            # Extract module name
            import re

            match = re.search(r"No module named '([^']+)'", error_text)
            if match:
                module_name = match.group(1)
                lines.append(f"Missing module: {module_name}")

                # Suggest pip install if it looks like an external package
                if "." not in module_name:
                    lines.append("\nTry installing the package:")
                    lines.append(f"    pip install {module_name}")
                else:
                    # Check if it might be a relative import issue
                    parts = module_name.split(".")
                    if len(parts) > 1:
                        lines.append("\nThis might be a relative import issue.")
                        lines.append("Check if the module structure matches your import statement.")
        elif "ImportError: cannot import name" in error_text:
            # Extract name being imported
            import re

            match = re.search(r"cannot import name '([^']+)'", error_text)
            if match:
                name = match.group(1)
                lines.append(f"Cannot import name: {name}")
                lines.append("\nMake sure this name exists in the imported module.")
                lines.append("Check for typos or incorrect module references.")

        # Add original error text
        lines.append("\nFull error message:")
        for line in error_text.splitlines():
            lines.append(f"  {line}")

        return "\n".join(lines)

    def _format_exception(self, file_path: str, error: Exception) -> str:
        """Format a generic exception with traceback information."""
        lines = [f"Error in {file_path}: {str(error)}"]

        # Try to extract line number information if available
        

        tb_info = traceback.extract_tb(sys.exc_info()[2])

        # Find traceback entries that reference the target file
        for filename, line, func, text in tb_info:
            if os.path.basename(filename) == os.path.basename(file_path):
                lines.append(f"Error in line {line} in function {func}: {text}")
                code_context = self._get_code_context(file_path, line, context_lines=3)

                # Add context if available
                if code_context:
                    lines.append("\nCode context:")
                    for ctx_line_num, ctx_line in code_context:
                        prefix = ">> " if ctx_line_num == line else "   "
                        lines.append(f"{prefix}{ctx_line_num}: {ctx_line}")
                break

        # Add full traceback
        lines.append("\nTraceback:")
        for line in traceback.format_exc().splitlines():
            lines.append(f"  {line}")

        return "\n".join(lines)

    def _suggest_syntax_fix(self, error: SyntaxError) -> str:
        """Suggest a fix for common syntax errors."""
        if not hasattr(error, "msg") or not error.msg:
            return None

        msg = error.msg.lower()

        # Missing closing parenthesis or bracket
        if "unexpected EOF" in msg and "expecting" in msg:
            if ")" in msg:
                return "Add a closing parenthesis ')'"
            elif "]" in msg:
                return "Add a closing bracket ']'"
            elif "}" in msg:
                return "Add a closing brace '}'"

        # Indentation errors
        if "indentation" in msg:
            if "expected an indented block" in msg:
                return "Add 4 spaces or a tab at the beginning of the line"
            elif "unexpected indent" in msg:
                return "Remove extra spaces/tabs at the beginning of the line"
            elif "unindent does not match" in msg:
                return (
                    "Make sure your indentation is consistent (use either spaces or tabs, not both)"
                )

        # Missing colon
        if "expected ':'" in msg:
            return "Add a colon ':' at the end of the line"

        # Invalid syntax (often missing commas in collections)
        if "invalid syntax" in msg and hasattr(error, "text"):
            if "[" in error.text and "]" in error.text:
                return "Check for missing commas in the list"
            elif "{" in error.text and "}" in error.text:
                return "Check for missing commas in the dictionary or set"

        # Too many/few values to unpack
        if "too many values to unpack" in msg:
            return "Make sure the number of variables on the left matches the number of values on the right"
        elif "not enough values to unpack" in msg:
            return "Make sure the number of variables on the left matches the number of values on the right"

        # Name errors
        if "name" in msg and "is not defined" in msg:
            # Extract the undefined name
            import re

            match = re.search(r"name '([^']+)' is not defined", msg)
            if match:
                name = match.group(1)
                return f"Define the variable '{name}' before using it, or check for typos"

        return None

    def _check_dependencies(self, file_path: str) -> List[str]:
        """
        Check which modules might be affected by changes to this file.
        This performs a simple analysis to identify potential dependencies.

        Args:
            file_path: Path to the changed file

        Returns:
            List of potentially affected module names
        """
        # Convert file path to module name
        try:
            rel_path = os.path.relpath(file_path, self.root_dirs[0])
            module_path = os.path.splitext(rel_path)[0].replace(os.path.sep, ".")
            affected_modules = []

            # List all Python files in the project
            all_py_files = []
            for root_dir in self.root_dirs:
                for root, dirs, files in os.walk(root_dir):
                    # Skip ignored directories
                    dirs[:] = [d for d in dirs if d not in self.ignore_dirs]

                    for file in files:
                        if file.endswith(".py"):
                            all_py_files.append(os.path.join(root, file))

            # Check each file for imports of the changed module
            import_prefixes = [
                f"import {module_path}",
                f"from {module_path} import",
                # Handle parent package imports
                *[
                    f"from {module_path.rsplit('.', i)[0]} import"
                    for i in range(1, module_path.count(".") + 1)
                ],
            ]

            # Check for relative imports
            parts = module_path.split(".")
            if len(parts) > 1:
                ".".join(parts[:-1])
                module_name = parts[-1]
                import_prefixes.append(f"from . import {module_name}")
                import_prefixes.append(f"from .{module_name} import")

            for py_file in all_py_files:
                # Skip the changed file itself
                if py_file == file_path:
                    continue

                try:
                    with open(py_file, "r", encoding="utf-8") as f:
                        content = f.read()

                    # Check for imports
                    for prefix in import_prefixes:
                        if prefix in content:
                            # Convert to module path
                            rel_import_path = os.path.relpath(py_file, self.root_dirs[0])
                            import_module = os.path.splitext(rel_import_path)[0].replace(
                                os.path.sep, "."
                            )
                            affected_modules.append(import_module)
                            break
                except Exception as e:
                    logger.debug(f"Error checking dependencies in {py_file}: {e}")

            return affected_modules

        except Exception as e:
            logger.warning(f"Error analyzing dependencies for {file_path}: {e}")
            return []

    def _can_import(self, file_path: str) -> tuple:
        """
        Try to import a Python file to check for import errors.

        This is done in a subprocess to avoid affecting the main process.

        Args:
            file_path: Path to the Python file

        Returns:
            Tuple of (success_flag, error_message)
        """
        try:
            # Run a subprocess to import the module
            file_dir = os.path.dirname(file_path)
            file_name = os.path.basename(file_path)
            module_name = os.path.splitext(file_name)[0]

            # Create import command
            import_cmd = f"; sys.path.insert(0, '{file_dir}'); import {module_name}"

            # Use subprocess to execute the import
            result = subprocess.run(
                [sys.executable, "-c", import_cmd],
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
                text=True,
                timeout=5,  # Timeout after 5 seconds
            )

            if result.returncode != 0:
                # Return the error output
                return False, result.stderr

            return True, None
        except subprocess.TimeoutExpired:
            error_msg = f"Import check timed out for {file_path}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Error during import check for {file_path}: {e}"
            logger.error(error_msg)
            return False, error_msg

    def _get_code_context(self, file_path: str, line_number: int, context_lines: int = 3) -> list:
        """
        Get code context around a specific line.

        Args:
            file_path: Path to the file
            line_number: Line number to focus on
            context_lines: Number of lines before and after to include

        Returns:
            List of (line_number, line_content) tuples
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Calculate start and end lines with bounds checking
            start_line = max(0, line_number - context_lines - 1)
            end_line = min(len(lines), line_number + context_lines)

            # Extract context with line numbers (1-based)
            return [(i + 1, lines[i].rstrip()) for i in range(start_line, end_line)]
        except Exception as e:
            logger.debug(f"Error getting code context: {e}")
            return []


class MCPFileWatcher:
    """
    File watcher for MCP server.

    Monitors file changes and triggers server restart.
    """
    def __init___v2(
        self,
        project_root: str,
        additional_dirs: Optional[List[str]] = None,
        ignore_dirs: Optional[List[str]] = None,
        ignore_patterns: Optional[List[str]] = None,
        server_class: Optional[Type] = None,
        server_instance = None,
        server_args: Optional[Dict[str, Any]] = None,
        use_dashboard: bool = True,
    ):
        """
        Initialize the file watcher.

        Args:
            project_root: Root directory of the project
            additional_dirs: Additional directories to watch
            ignore_dirs: Directories to ignore
            ignore_patterns: File patterns to ignore
            server_class: Server class to restart
            server_instance: Current server instance
            server_args: Arguments to pass to server constructor on restart
            use_dashboard: Whether to use the dashboard
        """
        self.project_root = os.path.abspath(project_root)
        self.additional_dirs = [os.path.abspath(d) for d in (additional_dirs or [])]
        self.watch_dirs = [self.project_root] + self.additional_dirs
        self.server_class = server_class
        self.server_instance = server_instance
        self.server_args = server_args or {}

        # Observer and handler
        self.observer = None
        self.handler = None

        # Track the current server thread
        self.server_thread = None
        self.shutdown_event = threading.Event()

        # Error reporting
        self.error_log = []
        self.max_error_log_size = 100
        self.has_unresolved_errors = False

        # Dashboard
        self.use_dashboard = use_dashboard and HAS_DASHBOARD
        self.dashboard = None
        if self.use_dashboard:
            try:
                self.dashboard = MCPDashboard()
                logger.info("Dashboard initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize dashboard: {e}")
                self.use_dashboard = False

        # Initialize the handler with error reporter callback
        self.handler = MCPFileHandler(
            root_dirs=self.watch_dirs,
            restart_callback=self.restart_server,
            ignore_dirs=ignore_dirs,
            ignore_patterns=ignore_patterns,
            error_reporter=self.report_error,
        )

        # Configure custom error handler for logger to capture all errors
        self._setup_error_logging()

        logger.info(f"Initialized MCP file watcher with root: {self.project_root}")
        if self.use_dashboard:
            logger.info("Dashboard enabled for live status updates")

    def _setup_error_logging(self):
        """Configure custom error logging to capture all errors."""
        # Create custom handler to capture errors
        class ErrorCaptureHandler(logging.Handler):
            def __init__(self, error_reporter):
                super().__init__()
                self.error_reporter = error_reporter
                # Only capture errors and warnings
                self.setLevel(logging.WARNING)

            def emit(self, record):
                if record.levelno >= logging.ERROR:
                    # Format the error message
                    error_msg = self.format(record)
                    # Report the error
                    self.error_reporter(error_msg, record)

        # Create and add the handler
        error_handler = ErrorCaptureHandler(self.report_error)
        error_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)-8s] [%(name)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logging.getLogger().addHandler(error_handler)

    def report_error(self, error_msg, record = None):
        """
        Report an error to the error log.

        Args:
            error_msg: Error message
            record: Optional logging record with additional information
        """
        error_entry = {
            "timestamp": time.time(),
            "message": error_msg,
            "resolved": False,
        }

        # Extract file and line information if available
        file_path = None
        line_number = None

        if record:
            error_entry.update(
                {
                    "level": record.levelname,
                    "logger": record.name,
                    "filename": record.filename,
                    "lineno": record.lineno,
                    "function": record.funcName,
                }
            )
            file_path = getattr(record, "pathname", None)
            line_number = getattr(record, "lineno", None)

        # Try to extract file info from error message if not in record
        if not file_path:
            import re

            file_match = re.search(r'File\s+"([^"]+)"', error_msg)
            if file_match:
                file_path = file_match.group(1)

            # Try to extract line number
            line_match = re.search(r"line\s+(\d+)", error_msg)
            if line_match:
                line_number = int(line_match.group(1))

        # Add to error log
        self.error_log.append(error_entry)

        # Trim log if needed
        if len(self.error_log) > self.max_error_log_size:
            self.error_log = self.error_log[-self.max_error_log_size :]

        # Update unresolved error flag
        self.has_unresolved_errors = True

        # Update dashboard if enabled
        if self.use_dashboard and self.dashboard and file_path:
            self.dashboard.add_error(file_path, error_msg, line_number)

        # Print the error in a visible way to the console (if not using dashboard)
        if not self.use_dashboard or not self.dashboard:
            divider = "=" * 80
            print(f"\n{divider}")
            print("MCP FILE WATCHER ERROR:")
            print(error_msg)
            print(f"{divider}\n")

    def start(self):
        """Start the file watcher."""
        logger.info("Starting MCP file watcher")
        self.observer = Observer()

        # Watch each directory
        for watch_dir in self.watch_dirs:
            if os.path.exists(watch_dir) and os.path.isdir(watch_dir):
                self.observer.schedule(self.handler, watch_dir, recursive=True)
                logger.info(f"Watching directory: {watch_dir}")
            else:
                logger.warning(f"Directory does not exist or is not a directory: {watch_dir}")

        # Start dashboard if enabled
        if self.use_dashboard and self.dashboard:
            self.dashboard.update_watcher_status("Starting")
            self.dashboard.update_server_status("Ready")
            self.dashboard.start()
            logger.info("Dashboard started")
        else:
            # Print startup message if not using dashboard
            self._print_startup_message()

        # Start the observer
        self.observer.start()

        # Update dashboard status
        if self.use_dashboard and self.dashboard:
            self.dashboard.update_watcher_status("Running")

        logger.info("MCP file watcher started")

    def _print_startup_message(self):
        """Print a formatted startup message."""
        divider = "=" * 80
        print(f"\n{divider}")
        print("MCP FILE WATCHER STARTED")
        print("Watching directories:")
        for watch_dir in self.watch_dirs:
            print(f"  - {watch_dir}")
        print(f"Ignoring directories: {', '.join(self.handler.ignore_dirs)}")
        print(f"Ignoring patterns: {', '.join(self.handler.ignore_patterns)}")
        print(f"{divider}")
        print("Auto-restarting server when Python files change.")
        print("Syntax errors will be shown in the console.")
        print(f"{divider}\n")

    def stop(self):
        """Stop the file watcher."""
        logger.info("Stopping MCP file watcher")

        # Update dashboard
        if self.use_dashboard and self.dashboard:
            self.dashboard.update_watcher_status("Stopping")

        # Stop the observer
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None

        # Stop dashboard
        if self.use_dashboard and self.dashboard:
            self.dashboard.stop()
            logger.info("Dashboard stopped")

        logger.info("MCP file watcher stopped")

    def get_error_summary(self):
        """
        Get a summary of recent errors.

        Returns:
            A formatted string with error summary
        """
        if not self.error_log:
            return "No errors"

        # Get unresolved errors
        unresolved = [e for e in self.error_log if not e.get("resolved", False)]

        # Format summary
        summary = [f"Error Summary ({len(unresolved)} unresolved, {len(self.error_log)} total):"]

        # Group errors by file
        errors_by_file = {}
        for error in unresolved:
            filename = error.get("filename", "unknown")
            if filename not in errors_by_file:
                errors_by_file[filename] = []
            errors_by_file[filename].append(error)

        # Add errors to summary
        for filename, errors in errors_by_file.items():
            summary.append(f"\nFile: {filename}")
            for i, error in enumerate(errors, 1):
                # Format timestamp
                ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(error["timestamp"]))
                # Add line number if available
                line_info = f"Line {error.get('lineno', '?')}: " if "lineno" in error else ""
                # Add error message (first line only for brevity)
                msg = error["message"].split("\n")[0]
                summary.append(f"  {i}. [{ts}] {line_info}{msg}")

        return "\n".join(summary)

    def mark_errors_resolved(self, file_path = None):
        """
        Mark errors as resolved.

        Args:
            file_path: Optional file path to mark errors resolved for only that file
        """
        if file_path:
            # Mark errors resolved only for this file
            for error in self.error_log:
                if error.get("filename") == os.path.basename(file_path):
                    error["resolved"] = True

            # Update dashboard
            if self.use_dashboard and self.dashboard:
                self.dashboard.mark_error_fixed(file_path)
        else:
            # Mark all errors resolved
            for error in self.error_log:
                error["resolved"] = True

        # Update unresolved error flag
        self.has_unresolved_errors = any(not e.get("resolved", False) for e in self.error_log)

    def restart_server(self, changed_file = None, affected_modules = None):
        """
        Restart the server in a new thread.

        Args:
            changed_file: Path to the file that triggered the restart
            affected_modules: List of modules affected by the change
        """
        if not self.server_class and not self.server_instance:
            logger.error("Cannot restart server: no server class or instance provided")
            return

        try:
            # Update dashboard if enabled
            if self.use_dashboard and self.dashboard:
                self.dashboard.update_server_status("Restarting")
                if changed_file:
                    self.dashboard.add_file_change(changed_file, "changed")
                self.dashboard.record_restart()

            # Signal current instance to shut down
            if self.server_thread and self.server_thread.is_alive():
                logger.info("Shutting down current server instance")
                self.shutdown_event.set()

                # Wait for server thread to terminate (with timeout)
                self.server_thread.join(timeout=5)
                if self.server_thread.is_alive():
                    logger.warning("Server thread did not shut down gracefully, continuing anyway")

            # Reset shutdown event
            self.shutdown_event.clear()

            # Print restart banner if not using dashboard
            if not self.use_dashboard or not self.dashboard:
                self._print_restart_banner(changed_file, affected_modules)

                # If there are unresolved errors, print them before restart
                if self.has_unresolved_errors:
                    print(self.get_error_summary())
                    print("\nRestarting server despite unresolved errors...\n")

            # Import server class and reload its module to get the latest changes
            if self.server_class:
                module_name = self.server_class.__module__
                class_name = self.server_class.__name__

                logger.info(f"Reloading module {module_name} for server restart")
                module = importlib.import_module(module_name)
                importlib.reload(module)

                # Also reload dependent modules if specified
                if affected_modules:
                    for module_path in affected_modules:
                        try:
                            if (
                                module_path != module_name
                            ):  # Skip the main module we already reloaded
                                logger.info(f"Reloading affected module: {module_path}")
                                dependent_module = importlib.import_module(module_path)
                                importlib.reload(dependent_module)
                        except (ImportError, ModuleNotFoundError) as e:
                            logger.warning(f"Could not reload affected module {module_path}: {e}")
                        except Exception as e:
                            logger.error(f"Error reloading affected module {module_path}: {e}")

                # Get the updated class from the reloaded module
                updated_server_class = getattr(module, class_name)

                # Instantiate the new server
                logger.info(f"Creating new instance of {class_name}")
                new_server = updated_server_class(**self.server_args)
            else:
                # Use existing server class and args
                logger.info("Creating new server instance based on existing instance")

                # Try to get class and args from existing instance
                instance_class = self.server_instance.__class__
                module_name = instance_class.__module__
                class_name = instance_class.__name__

                # Reload the module
                logger.info(f"Reloading module {module_name} for server restart")
                module = importlib.import_module(module_name)
                importlib.reload(module)

                # Also reload dependent modules if specified
                if affected_modules:
                    for module_path in affected_modules:
                        try:
                            if (
                                module_path != module_name
                            ):  # Skip the main module we already reloaded
                                logger.info(f"Reloading affected module: {module_path}")
                                dependent_module = importlib.import_module(module_path)
                                importlib.reload(dependent_module)
                        except (ImportError, ModuleNotFoundError) as e:
                            logger.warning(f"Could not reload affected module {module_path}: {e}")
                        except Exception as e:
                            logger.error(f"Error reloading affected module {module_path}: {e}")

                # Get the updated class
                updated_server_class = getattr(module, class_name)

                # Try to extract args from current instance
                # This is a best-effort approach and might not always work
                instance_args = {}
                if hasattr(self.server_instance, "__dict__"):
                    # Look for common initialization parameters
                    common_args = [
                        "debug_mode",
                        "log_level",
                        "persistence_path",
                        "isolation_mode",
                        "config",
                        "skip_daemon",
                    ]
                    for arg in common_args:
                        if hasattr(self.server_instance, arg):
                            instance_args[arg] = getattr(self.server_instance, arg)

                # Create new instance
                new_server = updated_server_class(**instance_args)

            # Start server in new thread
            logger.info("Starting new server instance in a new thread")
            self.server_thread = threading.Thread(
                target=self._run_server,
                args=(new_server, self.shutdown_event),
                daemon=True,
            )
            self.server_thread.start()

            # Update server instance reference
            self.server_instance = new_server

            # Mark errors as resolved for the changed file
            if changed_file and changed_file in self.files_with_errors:
                self.mark_errors_resolved(changed_file)

            # Update dashboard status
            if self.use_dashboard and self.dashboard:
                self.dashboard.update_server_status("Running")
                if changed_file:
                    # Mark the file as successfully restarted
                    self.dashboard.add_file_change(changed_file, "restarted")

            logger.info("Server restart complete")
            return True
        except Exception as e:
            logger.error(f"Error restarting server: {e}")
            logger.error(traceback.format_exc())

            # Update dashboard
            if self.use_dashboard and self.dashboard:
                self.dashboard.update_server_status("Error")
                if changed_file:
                    self.dashboard.add_file_change(changed_file, "error")

            # Report the error
            self.report_error(f"Server restart failed: {e}\n{traceback.format_exc()}")
            return False

    def _print_restart_banner(self, changed_file = None, affected_modules = None):
        """
        Print a visible restart banner.

        Args:
            changed_file: File that triggered the restart
            affected_modules: List of modules affected by the change
        """
        divider = "=" * 80
        print(f"\n{divider}")
        print("RESTARTING MCP SERVER")
        print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")

        # Add information about the changed file
        if changed_file:
            print(f"Changed file: {os.path.basename(changed_file)}")

            # Add information about affected modules
            if affected_modules and len(affected_modules) > 0:
                print(f"Affected modules: {len(affected_modules)}")
                for i, module in enumerate(affected_modules[:5], 1):  # Show first 5
                    print(f"  {i}. {module}")
                if len(affected_modules) > 5:
                    print(f"  ... and {len(affected_modules) - 5} more")

        print(f"{divider}\n")

    def _run_server(self, server, shutdown_event):
        """
        Run the server in a thread.

        Args:
            server: Server instance to run
            shutdown_event: Event to signal when server should shut down
        """
        try:
            logger.info("Server thread starting")

            # Update dashboard
            if self.use_dashboard and self.dashboard:
                self.dashboard.update_server_status("Starting")

            # Add shutdown event to server if it has an attribute for it
            if hasattr(server, "shutdown_event"):
                server.shutdown_event = shutdown_event

            # Check for appropriate start method
            if hasattr(server, "start_with_shutdown_event"):
                server.start_with_shutdown_event(shutdown_event)
            elif hasattr(server, "start"):
                # Start the server
                server.start()

                # Update dashboard
                if self.use_dashboard and self.dashboard:
                    self.dashboard.update_server_status("Running")

                # Wait for shutdown event
                while not shutdown_event.is_set():
                    time.sleep(0.5)

                # Update dashboard
                if self.use_dashboard and self.dashboard:
                    self.dashboard.update_server_status("Stopping")

                # Shutdown the server
                logger.info("Shutdown event received, stopping server")
                if hasattr(server, "shutdown"):
                    server.shutdown()
                elif hasattr(server, "stop"):
                    server.stop()
            else:
                logger.error("Server instance does not have a start method")

                # Update dashboard
                if self.use_dashboard and self.dashboard:
                    self.dashboard.update_server_status("Error")

            logger.info("Server thread stopped")
        except Exception as e:
            logger.error(f"Error in server thread: {e}")
            logger.error(traceback.format_exc())

            # Update dashboard
            if self.use_dashboard and self.dashboard:
                self.dashboard.update_server_status("Error")

            # Report the error
            self.report_error(f"Server thread error: {e}\n{traceback.format_exc()}")
