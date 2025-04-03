import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid

from .error import (
    IPFSConfigurationError,
    IPFSConnectionError,
    IPFSContentNotFoundError,
    IPFSError,
    IPFSPinningError,
    IPFSTimeoutError,
    IPFSValidationError,
    create_result_dict,
    handle_error,
    perform_with_retry,
)

# Configure logger
logger = logging.getLogger(__name__)


class ipfs_cluster_ctl:
    def __init__(self, resources=None, metadata=None):
        """Initialize ipfs_cluster_ctl with the specified resources and metadata.

        Args:
            resources: Dictionary of available resources
            metadata: Additional configuration metadata
        """
        # Initialize logger
        self.logger = logger

        # Store resources and metadata
        self.resources = resources
        self.metadata = metadata

        # Set up method aliases
        self.ipfs_cluster_ctl_add_pin = self.ipfs_cluster_ctl_add_pin
        self.ipfs_cluster_ctl_remove_pin = self.ipfs_cluster_ctl_remove_pin
        self.ipfs_cluster_ctl_add_pin_recursive = self.ipfs_cluster_ctl_add_pin_recursive
        self.ipfs_cluster_ctl_execute = self.ipfs_cluster_ctl_execute
        self.ipfs_cluster_get_pinset = self.ipfs_cluster_get_pinset
        self.ipfs_cluster_ctl_status = self.ipfs_cluster_ctl_status

        # Initialize paths
        self.this_dir = os.path.dirname(os.path.realpath(__file__))
        self.path = os.environ["PATH"]
        self.path = self.path + ":" + os.path.join(self.this_dir, "bin")
        self.path_string = "PATH=" + self.path

        # Set default role
        self.role = "leecher"

        # Process metadata if provided
        if metadata is not None:
            # Extract configuration if available
            if "config" in metadata and metadata["config"] is not None:
                self.config = metadata["config"]

            # Extract and validate role
            if "role" in metadata and metadata["role"] is not None:
                if metadata["role"] not in ["master", "worker", "leecher"]:
                    raise IPFSValidationError(
                        f"Invalid role: {metadata['role']}. Must be one of: master, worker, leecher"
                    )
                self.role = metadata["role"]

            # Extract other metadata as needed
            if "ipfs_cluster_path" in metadata and metadata["ipfs_cluster_path"] is not None:
                self.ipfs_cluster_path = metadata["ipfs_cluster_path"]

    def run_cluster_command(
        self, cmd_args, check=True, timeout=30, correlation_id=None, shell=False
    ):
        """Run IPFS cluster command with proper error handling.

        Args:
            cmd_args: Command and arguments as a list or string
            check: Whether to raise exception on non-zero exit code
            timeout: Command timeout in seconds
            correlation_id: ID for tracking related operations
            shell: Whether to use shell execution (avoid if possible)

        Returns:
            Dictionary with command result information
        """
        # Create standardized result dictionary
        command_str = cmd_args if isinstance(cmd_args, str) else " ".join(cmd_args)
        operation = command_str.split()[0] if isinstance(command_str, str) else cmd_args[0]

        result = create_result_dict(f"run_command_{operation}", correlation_id)
        result["command"] = command_str

        try:
            # Add environment variables if needed
            env = os.environ.copy()
            if hasattr(self, "ipfs_cluster_path"):
                env["IPFS_CLUSTER_PATH"] = self.ipfs_cluster_path
            env["PATH"] = self.path

            # Never use shell=True unless absolutely necessary for security
            process = subprocess.run(
                cmd_args, capture_output=True, check=check, timeout=timeout, shell=shell, env=env
            )

            # Process successful completion
            result["success"] = True
            result["returncode"] = process.returncode

            # Try to decode stdout as JSON if possible
            stdout = process.stdout.decode("utf-8", errors="replace")
            result["stdout_raw"] = stdout

            try:
                if stdout.strip() and stdout.strip()[0] in "{[":
                    result["stdout_json"] = json.loads(stdout)
                else:
                    result["stdout"] = stdout
            except json.JSONDecodeError:
                result["stdout"] = stdout

            # Only include stderr if there's content
            if process.stderr:
                result["stderr"] = process.stderr.decode("utf-8", errors="replace")

            return result

        except subprocess.TimeoutExpired as e:
            error_msg = f"Command timed out after {timeout} seconds"
            logger.error(f"Timeout running command: {command_str}")
            return handle_error(result, IPFSTimeoutError(error_msg), {"timeout": timeout})

        except subprocess.CalledProcessError as e:
            error_msg = f"Command failed with return code {e.returncode}"
            stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""

            logger.error(
                f"Command failed: {command_str}\n"
                f"Return code: {e.returncode}\n"
                f"Stderr: {stderr}"
            )

            result["returncode"] = e.returncode
            if e.stdout:
                result["stdout"] = e.stdout.decode("utf-8", errors="replace")
            if e.stderr:
                result["stderr"] = stderr

            return handle_error(result, IPFSError(error_msg), {"stderr": stderr})

        except FileNotFoundError as e:
            error_msg = f"Command not found: {command_str}"
            logger.error(error_msg)
            return handle_error(result, e)

        except Exception as e:
            error_msg = f"Failed to execute command: {str(e)}"
            logger.exception(f"Exception running command: {command_str}")
            return handle_error(result, e)

    def ipfs_cluster_ctl_add_pin(self, path=None, **kwargs):
        """Add a pin to IPFS cluster with standardized error handling.

        Args:
            path: Path to the file or CID to pin
            **kwargs: Additional arguments for the pin operation including
                      'metadata' for pin metadata and 'correlation_id' for tracing

        Returns:
            Result dictionary with operation outcome
        """
        operation = "ipfs_cluster_ctl_add_pin"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)

        try:
            # Validate required parameters
            if path is None:
                return handle_error(result, IPFSValidationError("Missing required parameter: path"))

            # Validate command arguments for security
            try:
                from .validation import (
                    validate_command_args,
                    validate_parameter_type,
                    validate_required_parameter,
                )

                validate_command_args(kwargs)
                validate_required_parameter(path, "path")
                validate_parameter_type(path, str, "path")

                # For file paths, check if the file exists
                if not path.startswith("Qm") and not path.startswith("baf"):
                    # Likely a file path - check existence
                    if not os.path.exists(path):
                        return handle_error(result, IPFSValidationError(f"Path not found: {path}"))
            except ImportError:
                # If validation module is not fully available, check path existence
                if not os.path.exists(path):
                    return handle_error(result, IPFSError(f"Path not found: {path}"))
            except IPFSValidationError as e:
                return handle_error(result, e)

            # For directory paths, get the list of files
            files_to_pin = []
            if os.path.isdir(path):
                # Walk the directory tree
                try:
                    for root, dirs, files in os.walk(path):
                        for file in files:
                            files_to_pin.append(os.path.join(root, file))
                except Exception as e:
                    return handle_error(result, IPFSError(f"Failed to walk directory: {str(e)}"))
            else:
                # Single file or CID
                files_to_pin.append(path)

            # Process each file
            pin_results = []
            success_count = 0

            for file_path in files_to_pin:
                try:
                    # Build the command for this file
                    cmd = ["ipfs-cluster-ctl", "pin", "add"]

                    # Add metadata from path if specified
                    if kwargs.get("metadata"):
                        cmd.extend(["--metadata", kwargs.get("metadata")])

                    # Add custom name if specified
                    if kwargs.get("name"):
                        cmd.extend(["--name", kwargs.get("name")])

                    # Add replication factor if specified
                    if kwargs.get("replication"):
                        cmd.extend(["--replication", str(kwargs.get("replication"))])

                    # Add the path/CID as the last argument
                    cmd.append(file_path)

                    # Execute the command
                    pin_result = self.run_cluster_command(cmd, correlation_id=correlation_id)

                    # Add this result to the list
                    if pin_result["success"]:
                        success_count += 1

                    pin_results.append(
                        {
                            "path": file_path,
                            "success": pin_result["success"],
                            "output": pin_result.get("stdout", ""),
                            "error": pin_result.get("error"),
                        }
                    )

                except Exception as e:
                    pin_results.append(
                        {
                            "path": file_path,
                            "success": False,
                            "error": str(e),
                            "error_type": type(e).__name__,
                        }
                    )

            # Update result with overall success and pin results
            result["success"] = len(pin_results) > 0 and success_count > 0
            result["path"] = path
            result["pin_results"] = pin_results
            result["total_files"] = len(pin_results)
            result["successful_pins"] = success_count
            result["failed_pins"] = len(pin_results) - success_count

            return result

        except Exception as e:
            return handle_error(result, e)

    def ipfs_cluster_ctl_remove_pin(self, pin=None, **kwargs):
        """Remove a pin from IPFS cluster with standardized error handling.

        Args:
            pin: CID to unpin from the cluster
            **kwargs: Additional arguments including 'correlation_id' for tracing

        Returns:
            Result dictionary with operation outcome
        """
        operation = "ipfs_cluster_ctl_remove_pin"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)

        try:
            # Validate required parameters
            if pin is None:
                return handle_error(result, IPFSValidationError("Missing required parameter: pin"))

            # Validate command arguments for security
            try:
                from .validation import (
                    validate_command_args,
                    validate_parameter_type,
                    validate_required_parameter,
                )

                validate_command_args(kwargs)
                validate_required_parameter(pin, "pin")
                validate_parameter_type(pin, str, "pin")

                # Validate CID format if possible
                try:
                    from .validation import is_valid_cid

                    if (
                        not pin.startswith("Qm")
                        and not pin.startswith("baf")
                        and not is_valid_cid(pin)
                    ):
                        return handle_error(
                            result, IPFSValidationError(f"Invalid CID format: {pin}")
                        )
                except ImportError:
                    # If validation module is not fully available, continue with basic checks
                    pass
            except IPFSValidationError as e:
                return handle_error(result, e)

            # Build the command
            cmd = ["ipfs-cluster-ctl", "pin", "rm"]

            # Add any optional flags
            if kwargs.get("force", False):
                cmd.append("--force")
            if kwargs.get("no-status", False):
                cmd.append("--no-status")

            # Add the CID to unpin
            cmd.append(pin)

            # Execute the command
            unpin_result = self.run_cluster_command(cmd, correlation_id=correlation_id)

            if unpin_result["success"]:
                # Command succeeded
                result["success"] = True
                result["cid"] = pin

                # Check if unpinned successfully
                stdout = unpin_result.get("stdout", "")
                if "unpinned" in stdout:
                    result["unpinned"] = True
                else:
                    result["unpinned"] = False
                    result["warning"] = (
                        "Unpin command succeeded but unpin confirmation not found in output"
                    )

                # Include the raw output for additional information
                result["output"] = stdout
            else:
                # Check for common errors
                stderr = unpin_result.get("stderr", "")

                if "not pinned" in stderr or "not found" in stderr:
                    # Not an error if already not pinned
                    result["success"] = True
                    result["cid"] = pin
                    result["unpinned"] = False
                    result["note"] = "CID was not pinned in cluster"
                else:
                    # Propagate error information
                    return handle_error(
                        result,
                        IPFSError(
                            f"Failed to remove cluster pin: {unpin_result.get('error', 'Unknown error')}"
                        ),
                        {"unpin_result": unpin_result},
                    )

            return result

        except Exception as e:
            return handle_error(result, e)

    def ipfs_cluster_ctl_add_pin_recursive(self, path=None, **kwargs):
        """Add a recursive pin to IPFS cluster with standardized error handling.

        This method pins a directory and all its contents recursively.

        Args:
            path: Path to the directory or CID to pin recursively
            **kwargs: Additional arguments for the pin operation including
                      'metadata' for pin metadata and 'correlation_id' for tracing

        Returns:
            Result dictionary with operation outcome
        """
        operation = "ipfs_cluster_ctl_add_pin_recursive"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)

        try:
            # Validate required parameters
            if path is None:
                return handle_error(result, IPFSValidationError("Missing required parameter: path"))

            # Validate command arguments for security
            try:
                from .validation import (
                    validate_command_args,
                    validate_parameter_type,
                    validate_required_parameter,
                )

                validate_command_args(kwargs)
                validate_required_parameter(path, "path")
                validate_parameter_type(path, str, "path")

                # For file paths, check if the path exists
                if not path.startswith("Qm") and not path.startswith("baf"):
                    # Likely a file path - check existence
                    if not os.path.exists(path):
                        return handle_error(result, IPFSValidationError(f"Path not found: {path}"))
            except ImportError:
                # If validation module is not fully available, check path existence
                if not os.path.exists(path):
                    return handle_error(result, IPFSError(f"Path not found: {path}"))
            except IPFSValidationError as e:
                return handle_error(result, e)

            # Build the command for recursive pinning
            cmd = ["ipfs-cluster-ctl", "pin", "add", "--recursive"]

            # Add metadata if specified
            if kwargs.get("metadata"):
                cmd.extend(["--metadata", kwargs.get("metadata")])

            # Add custom name if specified
            if kwargs.get("name"):
                cmd.extend(["--name", kwargs.get("name")])

            # Add replication factor if specified
            if kwargs.get("replication"):
                cmd.extend(["--replication", str(kwargs.get("replication"))])

            # Add the path/CID as the last argument
            cmd.append(path)

            # Execute the command
            pin_result = self.run_cluster_command(cmd, correlation_id=correlation_id)

            if pin_result["success"]:
                # Command succeeded
                result["success"] = True
                result["path"] = path

                # Extract pinned CID from output if possible
                stdout = pin_result.get("stdout", "")
                if "added" in stdout:
                    # Try to extract the CID from the output
                    parts = stdout.split(" ")
                    if len(parts) > 2:
                        result["cid"] = parts[2].strip()  # Format: "added: <CID>"

                # Include the raw output for additional information
                result["output"] = stdout
            else:
                # Propagate error information
                return handle_error(
                    result,
                    IPFSError(
                        f"Failed to add recursive pin: {pin_result.get('error', 'Unknown error')}"
                    ),
                    {"pin_result": pin_result},
                )

            return result

        except Exception as e:
            return handle_error(result, e)

    def ipfs_cluster_ctl_execute(self, args=None, **kwargs):
        """Execute an arbitrary ipfs-cluster-ctl command with standardized error handling.

        Args:
            args: List of command arguments
            **kwargs: Additional arguments including 'correlation_id' for tracing

        Returns:
            Result dictionary with operation outcome
        """
        operation = "ipfs_cluster_ctl_execute"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)

        try:
            # Validate required parameters
            if args is None or not isinstance(args, list) or len(args) == 0:
                return handle_error(
                    result,
                    IPFSValidationError(
                        "Missing or invalid required parameter: args (must be a non-empty list)"
                    ),
                )

            # Validate command arguments for security
            try:
                from .validation import validate_command_args

                validate_command_args(kwargs)

                # Additional validation for the command arguments
                valid_commands = [
                    "id",
                    "peers",
                    "add",
                    "pin",
                    "status",
                    "recover",
                    "version",
                    "health",
                    "ipfs",
                ]

                if args[0] not in valid_commands:
                    return handle_error(
                        result,
                        IPFSValidationError(
                            f"Invalid command: {args[0]}. Must be one of: {', '.join(valid_commands)}"
                        ),
                    )

                # Validate subcommands for specific commands
                if len(args) > 1:
                    if args[0] == "peers" and args[1] not in ["ls", "rm"]:
                        return handle_error(
                            result,
                            IPFSValidationError(
                                f"Invalid peers subcommand: {args[1]}. Must be one of: ls, rm"
                            ),
                        )

                    if args[0] == "pin" and args[1] not in ["add", "rm", "ls", "update"]:
                        return handle_error(
                            result,
                            IPFSValidationError(
                                f"Invalid pin subcommand: {args[1]}. Must be one of: add, rm, ls, update"
                            ),
                        )

                    if args[0] == "health" and args[1] not in ["graph", "metrics", "alerts"]:
                        return handle_error(
                            result,
                            IPFSValidationError(
                                f"Invalid health subcommand: {args[1]}. Must be one of: graph, metrics, alerts"
                            ),
                        )

                    if args[0] == "ipfs" and args[1] not in ["gc"]:
                        return handle_error(
                            result,
                            IPFSValidationError(
                                f"Invalid ipfs subcommand: {args[1]}. Must be one of: gc"
                            ),
                        )
            except ImportError:
                # If validation module is not fully available, perform basic validation
                if not args or not isinstance(args, list) or not args[0]:
                    return handle_error(result, IPFSError("Invalid or missing command arguments"))
            except IPFSValidationError as e:
                return handle_error(result, e)

            # Build the command
            cmd = ["ipfs-cluster-ctl"]
            cmd.extend(args)

            # Execute the command
            cmd_result = self.run_cluster_command(cmd, correlation_id=correlation_id)

            if cmd_result["success"]:
                # Command succeeded
                result["success"] = True
                result["command"] = " ".join(cmd)
                result["output"] = cmd_result.get("stdout", "")

                # Try to extract structured data if available
                if "stdout_json" in cmd_result:
                    result["data"] = cmd_result["stdout_json"]
            else:
                # Propagate error information
                return handle_error(
                    result,
                    IPFSError(f"Command failed: {cmd_result.get('error', 'Unknown error')}"),
                    {"cmd_result": cmd_result},
                )

            return result

        except Exception as e:
            return handle_error(result, e)

    def ipfs_cluster_get_pinset(self, **kwargs):
        """Get the set of pinned content in the IPFS cluster with standardized error handling.

        Args:
            **kwargs: Additional arguments including 'correlation_id' for tracing

        Returns:
            Result dictionary with operation outcome and pinned content
        """
        operation = "ipfs_cluster_get_pinset"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)

        try:
            # Validate command arguments for security
            try:
                from .validation import validate_command_args

                validate_command_args(kwargs)
            except IPFSValidationError as e:
                return handle_error(result, e)

            # Build the command to list pins
            cmd = ["ipfs-cluster-ctl", "pin", "ls"]

            # Add any filtering arguments
            if kwargs.get("filter"):
                cmd.append(kwargs.get("filter"))

            # Add any format arguments
            if kwargs.get("format"):
                cmd.extend(["--format", kwargs.get("format")])

            # Execute the command
            cmd_result = self.run_cluster_command(cmd, correlation_id=correlation_id)

            if not cmd_result["success"]:
                # Command failed, propagate error information
                return handle_error(
                    result,
                    IPFSError(
                        f"Failed to get cluster pinset: {cmd_result.get('error', 'Unknown error')}"
                    ),
                    {"cmd_result": cmd_result},
                )

            # Parse the output to build pinset
            output = cmd_result.get("stdout", "")
            if not output.strip():
                # Empty pinset
                result["success"] = True
                result["pins"] = {}
                result["pin_count"] = 0
                return result

            # Parse the pin listing
            pinset = {}
            parse_results = output.split("\n")

            for line in parse_results:
                if not line.strip():
                    continue

                # Split the line by the delimiter (usually " | ")
                results_list = line.split(" | ")
                if not results_list:
                    continue

                result_dict = {}

                # Extract CID from the first column
                cid = results_list[0].strip() if results_list else None
                if not cid:
                    continue

                # Process remaining columns
                for column in results_list[1:]:
                    # Split by colon to get key-value pairs
                    cell_split = column.split(":")
                    if len(cell_split) > 1:
                        key = cell_split[0].strip()
                        value = cell_split[1].strip()
                        result_dict[key] = value

                # Only add to pinset if we have valid data
                if len(result_dict) > 0:
                    pinset[cid] = result_dict

            # Store for future reference
            self.cluster_pinset = pinset

            # Update result with success and parsed pins
            result["success"] = True
            result["pins"] = pinset
            result["pin_count"] = len(pinset)

            return result

        except Exception as e:
            return handle_error(result, e)

    def ipfs_cluster_ctl_peers_ls(self, **kwargs):
        """List all peers in the IPFS cluster with standardized error handling.

        Args:
            **kwargs: Additional arguments including 'correlation_id' for tracing

        Returns:
            Result dictionary with operation outcome and peer information
        """
        operation = "ipfs_cluster_ctl_peers_ls"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)

        try:
            # Validate command arguments for security
            try:
                from .validation import validate_command_args

                validate_command_args(kwargs)
            except IPFSValidationError as e:
                return handle_error(result, e)

            # Build the command
            cmd = ["ipfs-cluster-ctl", "peers", "ls"]

            # Execute the command
            cmd_result = self.run_cluster_command(cmd, correlation_id=correlation_id)

            if not cmd_result["success"]:
                # Command failed, propagate error information
                return handle_error(
                    result,
                    IPFSError(
                        f"Failed to list cluster peers: {cmd_result.get('error', 'Unknown error')}"
                    ),
                    {"cmd_result": cmd_result},
                )

            # Parse the output to build peers list
            output = cmd_result.get("stdout", "")

            peers_data = []

            if output.strip():
                lines = output.strip().split("\n")
                current_peer = None

                for line in lines:
                    # Skip empty lines
                    if not line.strip():
                        continue

                    # Check if this is a peer ID line
                    if not line.startswith(" "):
                        # Start a new peer entry
                        if current_peer:
                            peers_data.append(current_peer)

                        current_peer = {"id": line.strip(), "addresses": [], "cluster_peers": []}
                        continue

                    # Check if this is an address line
                    if line.strip().startswith("-") and current_peer:
                        addr = line.strip()[2:].strip()  # Remove "- " prefix
                        current_peer["addresses"].append(addr)
                        continue

                    # Check if this is a cluster peer line
                    if line.strip().startswith(">") and current_peer:
                        peer = line.strip()[2:].strip()  # Remove "> " prefix
                        current_peer["cluster_peers"].append(peer)

                # Add the last peer if any
                if current_peer:
                    peers_data.append(current_peer)

            result["success"] = True
            result["peers"] = peers_data
            return result

        except Exception as e:
            return handle_error(result, e)

    def ipfs_cluster_ctl_health(self, **kwargs):
        """Check the health status of all peers in the IPFS cluster with standardized error handling.

        Args:
            **kwargs: Additional arguments including 'correlation_id' for tracing

        Returns:
            Result dictionary with health status information for each peer
        """
        operation = "ipfs_cluster_ctl_health"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)

        try:
            # Validate command arguments for security
            try:
                from .validation import validate_command_args

                validate_command_args(kwargs)
            except IPFSValidationError as e:
                return handle_error(result, e)

            # Build the command
            cmd = ["ipfs-cluster-ctl", "health"]

            # Execute the command
            cmd_result = self.run_cluster_command(cmd, correlation_id=correlation_id)

            if not cmd_result["success"]:
                # Command failed, propagate error information
                return handle_error(
                    result,
                    IPFSError(
                        f"Failed to check cluster health: {cmd_result.get('error', 'Unknown error')}"
                    ),
                    {"cmd_result": cmd_result},
                )

            # Parse the output to extract health information
            output = cmd_result.get("stdout", "")

            # Process the output into structured format
            health_data = []

            if output:
                lines = output.strip().split("\n")
                for line in lines:
                    # Skip empty lines
                    if not line.strip():
                        continue

                    # Extract peer ID and status information
                    parts = re.split(r"\s+", line.strip(), maxsplit=1)
                    if len(parts) >= 2:
                        peer_id = parts[0]
                        status_info = parts[1]

                        # Determine status and optional message
                        if " - " in status_info:
                            status, message = status_info.split(" - ", 1)
                            peer_info = {
                                "peer_id": peer_id,
                                "status": status.lower(),
                                "message": message.strip(),
                            }
                        else:
                            peer_info = {"peer_id": peer_id, "status": status_info.lower()}

                        health_data.append(peer_info)

            result["success"] = True
            result["health"] = health_data
            return result

        except Exception as e:
            return handle_error(result, e)

    def ipfs_cluster_ctl_status(self, **kwargs):
        """Get status of all pinned content in the IPFS cluster with standardized error handling.

        Args:
            **kwargs: Additional arguments including 'correlation_id' for tracing

        Returns:
            Result dictionary with operation outcome and pin status
        """
        operation = "ipfs_cluster_ctl_status"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)

        try:
            # Validate command arguments for security
            try:
                from .validation import validate_command_args

                validate_command_args(kwargs)
            except IPFSValidationError as e:
                return handle_error(result, e)

            # Build the command
            cmd = ["ipfs-cluster-ctl", "status"]

            # Add filter if specified
            if kwargs.get("filter"):
                cmd.append(kwargs.get("filter"))

            # Add other optional flags
            if kwargs.get("local", False):
                cmd.append("--local")
            if kwargs.get("filter-string"):
                cmd.extend(["--filter-string", kwargs.get("filter-string")])

            # Execute the command
            cmd_result = self.run_cluster_command(cmd, correlation_id=correlation_id)

            if not cmd_result["success"]:
                # Command failed, propagate error information
                return handle_error(
                    result,
                    IPFSError(
                        f"Failed to get cluster status: {cmd_result.get('error', 'Unknown error')}"
                    ),
                    {"cmd_result": cmd_result},
                )

            # Parse the output to build status map
            output = cmd_result.get("stdout", "")
            if not output.strip():
                # Empty status
                result["success"] = True
                result["pins"] = {}
                result["pin_count"] = 0
                return result

            # Parse the status output
            status_map = {}
            parse_results = output.split("\n")

            for line in parse_results:
                if not line.strip():
                    continue

                # Split the line by the delimiter (usually " | ")
                parts = line.split(" | ")
                if len(parts) < 2:
                    continue

                # Extract CID from the first part
                cid = parts[0].strip()
                if not cid:
                    continue

                # Process the status information
                status_info = {}

                # Extract allocation and status information
                for part in parts[1:]:
                    # Skip empty parts
                    if not part.strip():
                        continue

                    # Handle allocation information (peer: status)
                    if ":" in part:
                        peer_status = part.split(":", 1)
                        if len(peer_status) == 2:
                            peer = peer_status[0].strip()
                            status = peer_status[1].strip()

                            if "allocations" not in status_info:
                                status_info["allocations"] = {}

                            status_info["allocations"][peer] = status
                    else:
                        # Other information
                        status_info["general_status"] = part.strip()

                # Add status info to the map
                status_map[cid] = status_info

            # Update result with success and parsed status
            result["success"] = True
            result["pins"] = status_map
            result["pin_count"] = len(status_map)

            return result

        except Exception as e:
            return handle_error(result, e)

    def test_ipfs_cluster_ctl(self, **kwargs):
        """Test if ipfs-cluster-ctl is installed and available with standardized error handling.

        Args:
            **kwargs: Additional arguments including 'correlation_id' for tracing

        Returns:
            Result dictionary with test outcome
        """
        operation = "test_ipfs_cluster_ctl"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)

        try:
            # Validate command arguments for security
            try:
                from .validation import validate_command_args

                validate_command_args(kwargs)
            except IPFSValidationError as e:
                return handle_error(result, e)

            # Build the command to check if ipfs-cluster-ctl is installed
            cmd = ["which", "ipfs-cluster-ctl"]

            # Execute the command
            cmd_result = self.run_cluster_command(cmd, check=False, correlation_id=correlation_id)

            # Process result
            if cmd_result["success"] and cmd_result.get("stdout", "").strip():
                result["success"] = True
                result["available"] = True
                result["path"] = cmd_result.get("stdout", "").strip()

                # Try to get version information
                try:
                    version_cmd = ["ipfs-cluster-ctl", "version"]
                    version_result = self.run_cluster_command(
                        version_cmd, correlation_id=correlation_id
                    )

                    if version_result["success"]:
                        result["version"] = version_result.get("stdout", "").strip()
                except Exception as version_err:
                    result["version_error"] = str(version_err)
            else:
                result["success"] = (
                    True  # The test itself succeeded even if cluster-ctl isn't available
                )
                result["available"] = False
                result["error"] = "ipfs-cluster-ctl binary not found in PATH"
                result["error_type"] = "binary_not_found"

            return result

        except Exception as e:
            return handle_error(result, e)

    def test(self, **kwargs):
        """Run comprehensive tests for ipfs-cluster-ctl functionality.

        Args:
            **kwargs: Additional arguments including 'correlation_id' for tracing

        Returns:
            Result dictionary with all test outcomes
        """
        operation = "test"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)

        try:
            # Test if ipfs-cluster-ctl binary is available
            binary_test = self.test_ipfs_cluster_ctl(correlation_id=correlation_id)

            # Update result with test outcomes
            result["success"] = True  # Overall test operation succeeded
            result["cluster_ctl_available"] = binary_test.get("available", False)
            result["tests"] = {"binary_test": binary_test}

            # Attempt to get cluster status if binary is available
            if binary_test.get("available", False):
                try:
                    status_test = self.ipfs_cluster_ctl_status(correlation_id=correlation_id)
                    result["tests"]["status_test"] = {
                        "success": status_test.get("success", False),
                        "pin_count": status_test.get("pin_count", 0),
                    }
                except Exception as e:
                    result["tests"]["status_test"] = {
                        "success": False,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    }

                # Test peer list
                try:
                    peer_args = ["peers", "ls"]
                    peer_test = self.ipfs_cluster_ctl_execute(
                        peer_args, correlation_id=correlation_id
                    )
                    result["tests"]["peer_test"] = {
                        "success": peer_test.get("success", False),
                        "output": peer_test.get("output", ""),
                    }
                except Exception as e:
                    result["tests"]["peer_test"] = {
                        "success": False,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    }

            return result

        except Exception as e:
            return handle_error(result, e)


if __name__ == "__main__":
    resources = {}
    metadata = {}
    this_ipfs_cluster_ctl = ipfs_cluster_ctl(resources, metadata)
    results = this_ipfs_cluster_ctl.test()
    print(results)
    pass
