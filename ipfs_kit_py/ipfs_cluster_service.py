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


class ipfs_cluster_service:
    def __init__(self, resources=None, metadata=None):
        """Initialize IPFS Cluster Service functionality.

        Args:
            resources: Dictionary containing system resources
            metadata: Dictionary containing configuration metadata
                - config: Configuration settings
                - role: Node role (master, worker, leecher)
                - ipfs_path: Path to IPFS configuration
                - ipfs_cluster_path: Path to IPFS cluster configuration
        """
        # Initialize basic attributes
        self.resources = resources if resources is not None else {}
        self.metadata = metadata if metadata is not None else {}
        self.correlation_id = self.metadata.get("correlation_id", str(uuid.uuid4()))

        # Set up path configuration for binaries
        self.this_dir = os.path.dirname(os.path.realpath(__file__))
        self.path = os.environ.get("PATH", "")
        self.path = f"{self.path}:{os.path.join(self.this_dir, 'bin')}"

        # Extract and validate metadata
        try:
            # Extract configuration settings
            self.config = self.metadata.get("config")

            # Extract and validate role
            self.role = self.metadata.get("role", "leecher")
            if self.role not in ["master", "worker", "leecher"]:
                raise IPFSValidationError(
                    f"Invalid role: {self.role}. Must be one of: master, worker, leecher"
                )

            # Extract IPFS path
            self.ipfs_path = self.metadata.get("ipfs_path", os.path.expanduser("~/.ipfs"))

            # Extract and set IPFS cluster path
            self.ipfs_cluster_path = self.metadata.get(
                "ipfs_cluster_path", os.path.expanduser("~/.ipfs-cluster")
            )

            # Extract bootstrap peers for IPFS cluster
            self.bootstrap_peers = self.metadata.get("bootstrap_peers", [])

            logger.debug(
                f"Initialized IPFS Cluster Service with role={self.role}, "
                f"correlation_id={self.correlation_id}"
            )

        except Exception as e:
            logger.error(f"Error initializing IPFS Cluster Service: {str(e)}")
            if isinstance(e, IPFSValidationError):
                raise
            else:
                raise IPFSConfigurationError(f"Failed to initialize IPFS Cluster Service: {str(e)}")

    def run_cluster_service_command(
        self, cmd_args, check=True, timeout=30, correlation_id=None, shell=False
    ):
        """Run IPFS cluster-service command with proper error handling.

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

        result = create_result_dict(
            f"run_command_{operation}", correlation_id or self.correlation_id
        )
        result["command"] = command_str

        try:
            # Add environment variables if needed
            env = os.environ.copy()
            env["PATH"] = self.path
            if hasattr(self, "ipfs_path"):
                env["IPFS_PATH"] = self.ipfs_path
            if hasattr(self, "ipfs_cluster_path"):
                env["IPFS_CLUSTER_PATH"] = self.ipfs_cluster_path

            # Never use shell=True unless absolutely necessary for security
            process = subprocess.run(
                cmd_args, capture_output=True, check=check, timeout=timeout, shell=shell, env=env
            )

            # Process completed successfully
            result["success"] = True
            result["returncode"] = process.returncode

            # Decode stdout and stderr if they exist
            if process.stdout:
                try:
                    result["stdout"] = process.stdout.decode("utf-8")
                except UnicodeDecodeError:
                    result["stdout"] = process.stdout

            if process.stderr:
                try:
                    result["stderr"] = process.stderr.decode("utf-8")
                except UnicodeDecodeError:
                    result["stderr"] = process.stderr

            return result

        except subprocess.TimeoutExpired as e:
            error_msg = f"Command timed out after {timeout} seconds: {command_str}"
            logger.error(error_msg)
            return handle_error(result, IPFSTimeoutError(error_msg))

        except subprocess.CalledProcessError as e:
            error_msg = f"Command failed with return code {e.returncode}: {command_str}"
            result["returncode"] = e.returncode

            # Try to decode stdout and stderr
            if e.stdout:
                try:
                    result["stdout"] = e.stdout.decode("utf-8")
                except UnicodeDecodeError:
                    result["stdout"] = e.stdout

            if e.stderr:
                try:
                    result["stderr"] = e.stderr.decode("utf-8")
                except UnicodeDecodeError:
                    result["stderr"] = e.stderr

            logger.error(f"{error_msg}\nStderr: {result.get('stderr', '')}")
            return handle_error(result, IPFSError(error_msg))

        except FileNotFoundError as e:
            error_msg = f"Command binary not found: {command_str}"
            logger.error(error_msg)
            return handle_error(result, IPFSConfigurationError(error_msg))

        except Exception as e:
            error_msg = f"Failed to execute command: {str(e)}"
            logger.exception(f"Exception running command: {command_str}")
            return handle_error(result, e)

    def test_ipfs_cluster_service(self, **kwargs):
        """Test if ipfs-cluster-service binary is available in the PATH.

        Args:
            **kwargs: Optional arguments
                - correlation_id: ID for tracking related operations

        Returns:
            Boolean indicating if ipfs-cluster-service is available
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict("test_ipfs_cluster_service", correlation_id)

        try:
            # Use the 'which' command to check for binary existence using run_cluster_service_command
            cmd_result = self.run_cluster_service_command(
                ["which", "ipfs-cluster-service"], check=False, correlation_id=correlation_id
            )

            if cmd_result.get("success", False) and cmd_result.get("returncode", 1) == 0:
                detected_path = cmd_result.get("stdout", "").strip()
                if detected_path:
                    logger.debug(f"Found ipfs-cluster-service at: {detected_path}")
                    result["success"] = True
                    result["binary_path"] = detected_path
                    return True

            logger.warning("ipfs-cluster-service binary not found in PATH")
            return False

        except Exception as e:
            logger.exception(f"Error testing for ipfs-cluster-service: {str(e)}")
            return False

    def ipfs_cluster_service_start(self, **kwargs):
        """Start the IPFS cluster-service daemon.

        Args:
            **kwargs: Optional arguments
                - bootstrap_peers: List of bootstrap peer multiaddresses
                - correlation_id: ID for tracking related operations
                - timeout: Command timeout in seconds

        Returns:
            Dictionary with operation result information
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict("ipfs_cluster_service_start", correlation_id)

        try:
            # Set timeout for commands
            timeout = kwargs.get("timeout", 30)

            # Get bootstrap peers from kwargs or instance attribute
            bootstrap_peers = kwargs.get("bootstrap_peers", getattr(self, "bootstrap_peers", []))

            # Different execution paths based on user privileges
            if os.getuid() == 0:
                # Running as root, use systemctl
                logger.debug("Starting ipfs-cluster-service as root using systemctl")
                systemctl_result = self.run_cluster_service_command(
                    ["systemctl", "start", "ipfs-cluster-service"],
                    check=False,
                    timeout=timeout,
                    correlation_id=correlation_id,
                )
                result["systemctl_result"] = systemctl_result

                if not systemctl_result.get("success", False):
                    logger.warning(
                        "Failed to start ipfs-cluster-service via systemctl, will try direct execution"
                    )
            else:
                # Running as non-root user, use direct execution
                logger.debug(f"Starting ipfs-cluster-service as non-root user")

                # Construct command arguments as a list for security
                cmd_args = ["ipfs-cluster-service", "daemon"]

                # Add bootstrap peers if provided
                if bootstrap_peers:
                    # Validate bootstrap peers to prevent command injection
                    validated_peers = []
                    for peer in bootstrap_peers:
                        if not isinstance(peer, str):
                            logger.warning(f"Skipping non-string bootstrap peer: {peer}")
                            continue

                        # Basic validation of multiaddress format
                        if not re.match(r"^/(?:ip[46]|dns[46]?|unix|p2p)/", peer):
                            logger.warning(f"Skipping invalid multiaddress format: {peer}")
                            continue

                        # Check for shell metacharacters and unsafe command arguments
                        from .validation import is_safe_command_arg

                        if not is_safe_command_arg(peer):
                            logger.warning(
                                f"Skipping bootstrap peer with unsafe characters: {peer}"
                            )
                            continue

                        validated_peers.append(peer)

                    # Add validated bootstrap peers
                    for peer in validated_peers:
                        cmd_args.extend(["--bootstrap", peer])

                    logger.debug(f"Using bootstrap peers: {validated_peers}")
                    result["bootstrap_peers"] = validated_peers

                # Run the daemon command
                direct_result = self.run_cluster_service_command(
                    cmd_args, check=False, timeout=timeout, correlation_id=correlation_id
                )
                result["direct_result"] = direct_result

            # Check if the service is running after start attempts
            process_check_cmd = ["ps", "-ef"]
            ps_result = self.run_cluster_service_command(
                process_check_cmd, check=False, timeout=10, correlation_id=correlation_id
            )

            # Process ps output to find ipfs-cluster-service processes
            if ps_result.get("success", False) and ps_result.get("stdout"):
                process_running = False
                for line in ps_result.get("stdout", "").splitlines():
                    if "ipfs-cluster-service" in line and "daemon" in line and "grep" not in line:
                        process_running = True
                        break

                result["process_running"] = process_running

                # If process is not running, check for stale socket and try one more time
                if not process_running:
                    logger.warning(
                        "ipfs-cluster-service process not found, checking for stale socket"
                    )

                    # Safely check for api-socket
                    socket_path = os.path.expanduser(f"~/.ipfs-cluster/api-socket")
                    if os.path.exists(socket_path):
                        logger.debug(f"Removing stale socket at: {socket_path}")
                        try:
                            os.remove(socket_path)
                            result["socket_removed"] = True
                        except (PermissionError, OSError) as e:
                            logger.error(f"Failed to remove stale socket: {str(e)}")
                            result["socket_removed"] = False
                            result["socket_error"] = str(e)

                    # Try starting one more time with Popen for background execution
                    try:
                        logger.debug("Attempting final start with background execution")
                        env = os.environ.copy()
                        env["PATH"] = self.path
                        if hasattr(self, "ipfs_path"):
                            env["IPFS_PATH"] = self.ipfs_path
                        if hasattr(self, "ipfs_cluster_path"):
                            env["IPFS_CLUSTER_PATH"] = self.ipfs_cluster_path

                        # Build command arguments
                        cmd_args = ["ipfs-cluster-service", "daemon"]

                        # Add bootstrap peers
                        for peer in validated_peers:
                            cmd_args.extend(["--bootstrap", peer])

                        # Start the process
                        process = subprocess.Popen(
                            cmd_args,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            env=env,
                            shell=False,  # Never use shell=True
                        )

                        # Wait briefly to check if the process started
                        time.sleep(1)
                        if process.poll() is None:  # Still running
                            result["background_process_started"] = True
                            result["process_id"] = process.pid
                        else:
                            result["background_process_started"] = False
                            stdout, stderr = process.communicate(timeout=5)
                            result["background_stdout"] = (
                                stdout.decode("utf-8", errors="replace") if stdout else ""
                            )
                            result["background_stderr"] = (
                                stderr.decode("utf-8", errors="replace") if stderr else ""
                            )

                    except Exception as e:
                        logger.error(f"Failed to start background process: {str(e)}")
                        result["background_process_started"] = False
                        result["background_error"] = str(e)

            # Determine final success based on results
            result["success"] = result.get("process_running", False) or result.get(
                "background_process_started", False
            )

            if result["success"]:
                logger.info(f"Successfully started ipfs-cluster-service")
            else:
                logger.error(f"Failed to start ipfs-cluster-service")

            return result

        except Exception as e:
            logger.exception(f"Unexpected error in ipfs_cluster_service_start: {str(e)}")
            return handle_error(result, e)

    def ipfs_cluster_service_stop(self, **kwargs):
        """Stop the IPFS cluster-service daemon.

        Args:
            **kwargs: Optional arguments
                - correlation_id: ID for tracking related operations
                - timeout: Command timeout in seconds
                - force: Whether to force-kill the process

        Returns:
            Dictionary with operation result information
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict("ipfs_cluster_service_stop", correlation_id)

        try:
            # Set timeout for commands
            timeout = kwargs.get("timeout", 30)
            force = kwargs.get("force", False)

            # Different execution paths based on user privileges
            if os.getuid() == 0:
                # Running as root, use systemctl
                logger.debug("Stopping ipfs-cluster-service as root using systemctl")
                systemctl_result = self.run_cluster_service_command(
                    ["systemctl", "stop", "ipfs-cluster-service"],
                    check=False,
                    timeout=timeout,
                    correlation_id=correlation_id,
                )
                result["systemctl_result"] = systemctl_result

            # Check for any remaining processes and kill them if needed
            process_check_cmd = ["ps", "-ef"]
            ps_result = self.run_cluster_service_command(
                process_check_cmd, check=False, timeout=10, correlation_id=correlation_id
            )

            # Process ps output to find and kill ipfs-cluster-service processes
            pids_to_kill = []
            if ps_result.get("success", False) and ps_result.get("stdout"):
                for line in ps_result.get("stdout", "").splitlines():
                    if "ipfs-cluster-service" in line and "grep" not in line:
                        # Extract PID (assumes standard ps output format)
                        parts = line.split()
                        if len(parts) > 1:
                            try:
                                pid = int(parts[1])
                                pids_to_kill.append(pid)
                            except (ValueError, IndexError):
                                continue

            # Kill any remaining processes if found
            killed_pids = []
            kill_errors = []

            for pid in pids_to_kill:
                try:
                    # Use SIGKILL (9) if force=True, otherwise SIGTERM (15)
                    sig = 9 if force else 15
                    os.kill(pid, sig)
                    killed_pids.append(pid)
                except ProcessLookupError:
                    # Process already gone
                    pass
                except Exception as e:
                    kill_errors.append({"pid": pid, "error": str(e)})

            result["killed_processes"] = killed_pids
            if kill_errors:
                result["kill_errors"] = kill_errors

            # Clean up socket file
            socket_path = os.path.expanduser(f"~/.ipfs-cluster/api-socket")
            if os.path.exists(socket_path):
                try:
                    os.remove(socket_path)
                    result["socket_removed"] = True
                except (PermissionError, OSError) as e:
                    logger.error(f"Failed to remove socket file: {str(e)}")
                    result["socket_removed"] = False
                    result["socket_error"] = str(e)
            else:
                result["socket_removed"] = False
                result["socket_exists"] = False

            # Check if the service is truly stopped
            time.sleep(1)  # Brief wait to allow processes to terminate

            # Verify all processes are stopped
            ps_result = self.run_cluster_service_command(
                ["ps", "-ef"], check=False, timeout=10, correlation_id=correlation_id
            )

            all_stopped = True
            if ps_result.get("success", False) and ps_result.get("stdout"):
                for line in ps_result.get("stdout", "").splitlines():
                    if "ipfs-cluster-service" in line and "grep" not in line:
                        all_stopped = False
                        break

            result["all_processes_stopped"] = all_stopped

            # Determine final success
            result["success"] = all_stopped

            if result["success"]:
                logger.info("Successfully stopped ipfs-cluster-service")
            else:
                logger.warning("May not have fully stopped ipfs-cluster-service")

            return result

        except Exception as e:
            logger.exception(f"Unexpected error in ipfs_cluster_service_stop: {str(e)}")
            return handle_error(result, e)

    def ipfs_cluster_service_status(self, **kwargs):
        """Get the status of the IPFS cluster-service daemon.

        Args:
            **kwargs: Optional arguments
                - correlation_id: ID for tracking related operations
                - timeout: Command timeout in seconds

        Returns:
            Dictionary with operation result information
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict("ipfs_cluster_service_status", correlation_id)

        try:
            # Set timeout for commands
            timeout = kwargs.get("timeout", 30)

            # First check if the process is running
            process_check_cmd = ["ps", "-ef"]
            ps_result = self.run_cluster_service_command(
                process_check_cmd, check=False, timeout=10, correlation_id=correlation_id
            )

            process_running = False
            process_count = 0

            # Process ps output to check for ipfs-cluster-service processes
            if ps_result.get("success", False) and ps_result.get("stdout"):
                for line in ps_result.get("stdout", "").splitlines():
                    if "ipfs-cluster-service" in line and "daemon" in line and "grep" not in line:
                        process_running = True
                        process_count += 1

            result["process_running"] = process_running
            result["process_count"] = process_count

            # If process is running, try to get detailed status
            if process_running:
                # Use the ipfs-cluster-service status command
                status_cmd = ["ipfs-cluster-service", "status"]
                status_result = self.run_cluster_service_command(
                    status_cmd, check=False, timeout=timeout, correlation_id=correlation_id
                )

                if status_result.get("success", False):
                    result["detailed_status"] = status_result.get("stdout", "")
                    result["success"] = True
                else:
                    # If status command fails, at least we know process is running
                    result["detailed_status_error"] = status_result.get("stderr", "")
                    result["detailed_status_failed"] = True
                    result["success"] = (
                        True  # Service is running even if we can't get detailed status
                    )
            else:
                # Check socket file to see if it's stale
                socket_path = os.path.expanduser(f"~/.ipfs-cluster/api-socket")
                result["socket_exists"] = os.path.exists(socket_path)
                result["success"] = False

            # Log appropriate message
            if result["success"]:
                logger.info(f"IPFS cluster-service is running with {process_count} process(es)")
            else:
                logger.warning("IPFS cluster-service is not running")

            return result

        except Exception as e:
            logger.exception(f"Unexpected error in ipfs_cluster_service_status: {str(e)}")
            return handle_error(result, e)

    def test(self, **kwargs):
        """Run all tests for ipfs-cluster-service functionality.

        Args:
            **kwargs: Optional arguments
                - correlation_id: ID for tracking related operations

        Returns:
            Dictionary with test results
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict("test", correlation_id)

        try:
            # Test if ipfs-cluster-service binary is available
            service_available = self.test_ipfs_cluster_service(correlation_id=correlation_id)
            result["ipfs_cluster_service_available"] = service_available

            # Get service status if binary is available
            if service_available:
                status_result = self.ipfs_cluster_service_status(correlation_id=correlation_id)
                result["service_status"] = status_result
                result["service_running"] = status_result.get("process_running", False)

            # Set overall success based on test results
            result["success"] = service_available

            # Check environment
            result["environment"] = {
                "path": self.path,
                "role": getattr(self, "role", "unknown"),
                "ipfs_path": getattr(self, "ipfs_path", "not set"),
                "ipfs_cluster_path": getattr(self, "ipfs_cluster_path", "not set"),
            }

            if service_available:
                logger.info("IPFS Cluster Service tests passed")
            else:
                logger.warning("IPFS Cluster Service tests failed: binary not available")

            return result

        except Exception as e:
            logger.exception(f"Error during tests: {str(e)}")
            return handle_error(result, e)


if __name__ == "__main__":
    resources = {}
    metadata = {}
    this_ipfs_cluster_service = ipfs_cluster_service(resources, metadata)
    results = this_ipfs_cluster_service.test()
    print(results)
    pass
