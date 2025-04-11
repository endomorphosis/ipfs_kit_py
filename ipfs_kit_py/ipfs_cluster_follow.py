import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
import traceback

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


class ipfs_cluster_follow:
    def __init__(self, resources=None, metadata=None):
        """Initialize IPFS Cluster Follow functionality.

        Args:
            resources: Dictionary containing system resources
            metadata: Dictionary containing configuration metadata
                - config: Configuration settings
                - role: Node role (master, worker, leecher)
                - cluster_name: Name of the IPFS cluster to follow
                - ipfs_path: Path to IPFS configuration
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

            # Extract cluster name
            self.cluster_name = self.metadata.get("cluster_name")

            # Extract IPFS path
            self.ipfs_path = self.metadata.get("ipfs_path", os.path.expanduser("~/.ipfs"))

            # Extract and set IPFS cluster path
            self.ipfs_cluster_path = self.metadata.get(
                "ipfs_cluster_path", os.path.expanduser("~/.ipfs-cluster-follow")
            )

            logger.debug(
                f"Initialized IPFS Cluster Follow with role={self.role}, "
                f"cluster_name={self.cluster_name}, correlation_id={self.correlation_id}"
            )

        except Exception as e:
            logger.error(f"Error initializing IPFS Cluster Follow: {str(e)}")
            if isinstance(e, IPFSValidationError):
                raise
            else:
                raise IPFSConfigurationError(f"Failed to initialize IPFS Cluster Follow: {str(e)}")

    def run_cluster_follow_command(
        self, cmd_args, check=True, timeout=30, correlation_id=None, shell=False
    ):
        """Run IPFS cluster-follow command with proper error handling.

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

    def ipfs_follow_init(self, **kwargs):
        """Initialize the IPFS cluster-follow configuration.

        Args:
            **kwargs: Optional arguments
                - cluster_name: Name of the cluster to follow
                - bootstrap_peer: Multiaddr of the trusted bootstrap peer to follow
                - correlation_id: ID for tracking related operations
                - timeout: Command timeout in seconds
                - service_name: Optional service name for configuration

        Returns:
            Dictionary with operation result information
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict("ipfs_follow_init", correlation_id)

        try:
            # Validate required parameters
            cluster_name = kwargs.get("cluster_name", getattr(self, "cluster_name", None))
            if not cluster_name:
                return handle_error(
                    result, IPFSValidationError("Missing required parameter: cluster_name")
                )

            bootstrap_peer = kwargs.get("bootstrap_peer", None)
            if not bootstrap_peer:
                return handle_error(
                    result, IPFSValidationError("Missing required parameter: bootstrap_peer")
                )

            # Validate cluster name (prevent command injection)
            if not isinstance(cluster_name, str):
                return handle_error(
                    result,
                    IPFSValidationError(
                        f"cluster_name must be a string, got {type(cluster_name).__name__}"
                    ),
                )

            try:
                from .validation import is_safe_command_arg
                if not is_safe_command_arg(cluster_name):
                    return handle_error(
                        result,
                        IPFSValidationError(
                            f"Invalid cluster name contains shell metacharacters: {cluster_name}"
                        ),
                    )
            except ImportError:
                # Fallback if validation module not available
                if re.search(r'[;&|"`\'$<>]', cluster_name):
                    return handle_error(
                        result,
                        IPFSValidationError(
                            f"Invalid cluster name contains shell metacharacters: {cluster_name}"
                        ),
                    )

            # Set timeout for commands
            timeout = kwargs.get("timeout", 60)
            service_name = kwargs.get("service_name", None)

            # Check if ipfs-cluster-follow binary exists
            which_result = self.run_cluster_follow_command(
                ["which", "ipfs-cluster-follow"], check=False, timeout=5, correlation_id=correlation_id
            )
            
            if not which_result.get("success", False) or which_result.get("returncode", 1) != 0:
                logger.error("ipfs-cluster-follow binary not found in PATH")
                return handle_error(
                    result, 
                    IPFSConfigurationError("ipfs-cluster-follow binary not found in PATH. Please install it first.")
                )

            # Setup command for initialization
            cmd_args = ["ipfs-cluster-follow", cluster_name, "init", bootstrap_peer]
            
            # Add service name if provided
            if service_name:
                cmd_args.extend(["--service-name", service_name])

            logger.info(f"Initializing ipfs-cluster-follow configuration for cluster: {cluster_name}")
            
            # Run the initialization command
            cmd_result = self.run_cluster_follow_command(
                cmd_args, check=False, timeout=timeout, correlation_id=correlation_id
            )

            result["command_result"] = cmd_result
            result["success"] = cmd_result.get("success", False) and cmd_result.get("returncode", 1) == 0

            # Verify configuration was created
            config_path = os.path.expanduser(f"~/.ipfs-cluster-follow/{cluster_name}/service.json")
            config_exists = os.path.exists(config_path)
            result["config_created"] = config_exists
            
            if config_exists:
                logger.info(f"Successfully created cluster configuration at: {config_path}")
                
                # Check the configuration contents
                try:
                    with open(config_path, 'r') as f:
                        config_data = json.load(f)
                        result["config_valid"] = True
                        result["config_summary"] = {
                            "id": config_data.get("cluster", {}).get("id", "unknown"),
                            "peers": config_data.get("peers", []),
                            "bootstrap": config_data.get("bootstrap", [])
                        }
                except Exception as e:
                    logger.error(f"Error reading configuration file: {str(e)}")
                    result["config_valid"] = False
                    result["config_error"] = str(e)
            else:
                # Handle failure case
                error_msg = cmd_result.get("stderr", "Unknown error")
                logger.error(f"Failed to initialize cluster configuration: {error_msg}")
                result["error"] = error_msg
                result["success"] = False

            return result

        except Exception as e:
            logger.exception(f"Unexpected error in ipfs_follow_init: {str(e)}")
            return handle_error(result, e)

    def ipfs_follow_start(self, **kwargs):
        """Start the IPFS cluster-follow service.

        Args:
            **kwargs: Optional arguments
                - cluster_name: Name of the cluster to follow
                - correlation_id: ID for tracking related operations
                - timeout: Command timeout in seconds

        Returns:
            Dictionary with operation result information
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict("ipfs_follow_start", correlation_id)

        try:
            # Validate required parameters
            cluster_name = kwargs.get("cluster_name", getattr(self, "cluster_name", None))
            if not cluster_name:
                return handle_error(
                    result, IPFSValidationError("Missing required parameter: cluster_name")
                )

            # Validate cluster name (prevent command injection)
            if not isinstance(cluster_name, str):
                return handle_error(
                    result,
                    IPFSValidationError(
                        f"cluster_name must be a string, got {type(cluster_name).__name__}"
                    ),
                )

            # Check if ipfs-cluster-follow binary exists
            which_result = self.run_cluster_follow_command(
                ["which", "ipfs-cluster-follow"], check=False, timeout=5, correlation_id=correlation_id
            )
            
            if not which_result.get("success", False) or which_result.get("returncode", 1) != 0:
                logger.error("ipfs-cluster-follow binary not found in PATH")
                return handle_error(
                    result, 
                    IPFSConfigurationError("ipfs-cluster-follow binary not found in PATH. Please install it first.")
                )

            try:
                from .validation import is_safe_command_arg
                if not is_safe_command_arg(cluster_name):
                    return handle_error(
                        result,
                        IPFSValidationError(
                            f"Invalid cluster name contains shell metacharacters: {cluster_name}"
                        ),
                    )
            except ImportError:
                # Fallback if validation module not available
                if re.search(r'[;&|"`\'$<>]', cluster_name):
                    return handle_error(
                        result,
                        IPFSValidationError(
                            f"Invalid cluster name contains shell metacharacters: {cluster_name}"
                        ),
                    )

            # Set timeout for commands
            timeout = kwargs.get("timeout", 30)
            
            # Check if configuration exists
            follow_config_path = os.path.expanduser(f"~/.ipfs-cluster-follow/{cluster_name}/service.json")
            if not os.path.exists(follow_config_path):
                logger.error(f"Cluster follow configuration not found at {follow_config_path}")
                return handle_error(
                    result, 
                    IPFSConfigurationError(f"Cluster follow configuration not found for {cluster_name}. Run initialization first.")
                )

            # Different execution paths based on user privileges
            if os.geteuid() == 0:  # Using geteuid() instead of getuid() for consistency
                # Running as root, use systemctl
                logger.debug("Starting ipfs-cluster-follow as root using systemctl")
                
                # Check if service file exists
                service_file_path = "/etc/systemd/system/ipfs-cluster-follow.service"
                if not os.path.exists(service_file_path):
                    logger.error(f"Systemd service file not found: {service_file_path}")
                    return handle_error(
                        result, 
                        IPFSConfigurationError(f"Systemd service file not found: {service_file_path}")
                    )
                
                systemctl_result = self.run_cluster_follow_command(
                    ["systemctl", "start", "ipfs-cluster-follow"],
                    check=False,
                    timeout=timeout,
                    correlation_id=correlation_id,
                )
                result["systemctl_result"] = systemctl_result

                if not systemctl_result.get("success", False):
                    systemctl_error = systemctl_result.get("stderr", "")
                    logger.warning(
                        f"Failed to start ipfs-cluster-follow via systemctl: {systemctl_error}"
                    )
                    result["systemctl_error"] = systemctl_error
            else:
                # Running as non-root user, use direct execution
                logger.debug(
                    f"Starting ipfs-cluster-follow as non-root user for cluster: {cluster_name}"
                )
                # Construct command arguments as a list for security
                cmd_args = ["ipfs-cluster-follow", cluster_name, "run"]

                # Run the command in background with Popen instead of blocking run_cluster_follow_command
                # This allows the process to detach and continue running
                try:
                    env = os.environ.copy()
                    env["PATH"] = self.path
                    if hasattr(self, "ipfs_path"):
                        env["IPFS_PATH"] = self.ipfs_path
                        
                    # Redirect the output to files so we can capture it for debugging
                    logs_dir = os.path.expanduser("~/.ipfs-cluster-follow/logs")
                    os.makedirs(logs_dir, exist_ok=True)
                    stdout_path = os.path.join(logs_dir, f"cluster-follow-{cluster_name}.out")
                    stderr_path = os.path.join(logs_dir, f"cluster-follow-{cluster_name}.err")
                    
                    with open(stdout_path, "wb") as stdout_file, open(stderr_path, "wb") as stderr_file:
                        process = subprocess.Popen(
                            cmd_args,
                            stdout=stdout_file,
                            stderr=stderr_file,
                            env=env,
                            shell=False,  # Never use shell=True
                        )
                        
                        # Store process details
                        result["direct_execution"] = {
                            "pid": process.pid,
                            "stdout_path": stdout_path,
                            "stderr_path": stderr_path
                        }
                        
                        # Wait briefly to see if the process crashes immediately
                        time.sleep(2)
                        return_code = process.poll()
                        
                        if return_code is not None:  # Process already exited
                            result["process_exited_early"] = True
                            result["exit_code"] = return_code
                            
                            # Read the error output to provide useful debugging info
                            with open(stderr_path, "r") as err_file:
                                stderr_content = err_file.read()
                                if stderr_content:
                                    result["stderr"] = stderr_content
                                    logger.error(f"Process exited with error: {stderr_content}")
                        else:
                            result["direct_result"] = {"success": True, "process_running": True}
                            
                except Exception as e:
                    direct_error = str(e)
                    logger.error(f"Error starting cluster follow process: {direct_error}")
                    result["direct_execution_error"] = direct_error
                    return handle_error(result, e)

            # Check if the service is running after start attempts
            process_check_cmd = ["ps", "-ef"]
            ps_result = self.run_cluster_follow_command(
                process_check_cmd, check=False, timeout=10, correlation_id=correlation_id
            )

            # Process ps output to find ipfs-cluster-follow processes
            if ps_result.get("success", False) and ps_result.get("stdout"):
                process_running = False
                for line in ps_result.get("stdout", "").splitlines():
                    if "ipfs-cluster-follow" in line and cluster_name in line and "grep" not in line:
                        process_running = True
                        break

                result["process_running"] = process_running

                # If process is not running, check for stale socket and try one more time
                if not process_running:
                    logger.warning(
                        "ipfs-cluster-follow process not found, checking for stale socket"
                    )

                    # Safely check for api-socket
                    socket_path = os.path.expanduser(
                        f"~/.ipfs-cluster-follow/{cluster_name}/api-socket"
                    )
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

                        # Create logs directory if it doesn't exist
                        logs_dir = os.path.expanduser("~/.ipfs-cluster-follow/logs")
                        os.makedirs(logs_dir, exist_ok=True)
                        stdout_path = os.path.join(logs_dir, f"cluster-follow-retry-{cluster_name}.out")
                        stderr_path = os.path.join(logs_dir, f"cluster-follow-retry-{cluster_name}.err")
                        
                        # Start the process with proper list arguments and redirect output to files
                        with open(stdout_path, "wb") as stdout_file, open(stderr_path, "wb") as stderr_file:
                            cmd_args = ["ipfs-cluster-follow", cluster_name, "run"]
                            process = subprocess.Popen(
                                cmd_args,
                                stdout=stdout_file,
                                stderr=stderr_file,
                                env=env,
                                shell=False,  # Never use shell=True
                            )

                            # Wait briefly to check if the process started
                            time.sleep(2)
                            if process.poll() is None:  # Still running
                                result["background_process_started"] = True
                                result["process_id"] = process.pid
                                result["stdout_path"] = stdout_path
                                result["stderr_path"] = stderr_path
                            else:
                                result["background_process_started"] = False
                                # Read the error output to diagnose issues
                                with open(stderr_path, "r") as err_file:
                                    stderr_content = err_file.read()
                                    if stderr_content:
                                        result["background_stderr"] = stderr_content
                                        logger.error(f"Background process failed with error: {stderr_content}")
                                        # Set error for better diagnosis
                                        result["error"] = stderr_content

                    except Exception as e:
                        logger.error(f"Failed to start background process: {str(e)}")
                        result["background_process_started"] = False
                        result["background_error"] = str(e)

            # Check if the cluster configuration is accessible
            try:
                config_check_cmd = ["ls", "-la", os.path.expanduser(f"~/.ipfs-cluster-follow/{cluster_name}")]
                config_check_result = self.run_cluster_follow_command(
                    config_check_cmd, check=False, timeout=5, correlation_id=correlation_id
                )
                result["config_check"] = config_check_result.get("stdout", "")
            except Exception as config_e:
                logger.warning(f"Could not check cluster config: {str(config_e)}")

            # Determine final success based on results
            result["success"] = result.get("process_running", False) or result.get(
                "background_process_started", False
            )

            if result["success"]:
                logger.info(f"Successfully started ipfs-cluster-follow for cluster: {cluster_name}")
            else:
                # Provide more detailed error information
                error_details = []
                
                # Check for binary issue
                if not which_result.get("success", False):
                    error_details.append("ipfs-cluster-follow binary not found")
                
                # Check for systemctl issues
                systemctl_error = result.get("systemctl_error", "")
                if systemctl_error:
                    error_details.append(f"systemctl error: {systemctl_error}")
                
                # Check for direct execution issues
                direct_error = result.get("direct_execution_error", "")
                if direct_error:
                    error_details.append(f"direct execution error: {direct_error}")
                
                # Check stderr from any attempts
                stderr = result.get("stderr", "")
                if stderr:
                    error_details.append(f"process error: {stderr}")
                
                background_stderr = result.get("background_stderr", "")
                if background_stderr:
                    error_details.append(f"background error: {background_stderr}")
                
                # If we have error details, include them in the result
                if error_details:
                    error_msg = "; ".join(error_details)
                    result["error"] = error_msg
                    logger.error(f"Failed to start ipfs-cluster-follow for cluster: {cluster_name}: {error_msg}")
                else:
                    result["error"] = "Unknown error, check system logs"
                    logger.error(f"Failed to start ipfs-cluster-follow for cluster: {cluster_name}")

            return result

        except Exception as e:
            logger.exception(f"Unexpected error in ipfs_follow_start: {str(e)}")
            return handle_error(result, e)
            
    def ipfs_cluster_follow_status(self, **kwargs):
        """Get the status of the IPFS cluster-follow daemon.

        Args:
            **kwargs: Optional arguments
                - correlation_id: ID for tracking related operations
                - timeout: Command timeout in seconds

        Returns:
            Dictionary with operation result information
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get("correlation_id", getattr(self, "correlation_id", str(uuid.uuid4())))
        result = create_result_dict("ipfs_cluster_follow_status", correlation_id)

        try:
            # Set timeout for commands
            timeout = kwargs.get("timeout", 30)

            # First check if the process is running
            process_check_cmd = ["ps", "-ef"]
            ps_result = self.run_cluster_follow_command(
                process_check_cmd, check=False, timeout=10, correlation_id=correlation_id
            )

            process_running = False
            process_count = 0

            # Process ps output to check for ipfs-cluster-follow processes
            if ps_result.get("success", False) and ps_result.get("stdout"):
                for line in ps_result.get("stdout", "").splitlines():
                    if "ipfs-cluster-follow" in line and "daemon" in line and "grep" not in line:
                        process_running = True
                        process_count += 1

            result["process_running"] = process_running
            result["process_count"] = process_count

            # If process is running, try to get detailed status
            if process_running:
                # Use the ipfs-cluster-follow status command
                status_cmd = ["ipfs-cluster-follow", "status"]
                status_result = self.run_cluster_follow_command(
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
                logger.info(f"IPFS cluster-follow is running with {process_count} process(es)")
            else:
                logger.warning("IPFS cluster-follow is not running")

            return result

        except Exception as e:
            logger.exception(f"Unexpected error in ipfs_cluster_follow_status: {str(e)}")
            return handle_error(result, e)


ipfs_cluster_follow = ipfs_cluster_follow
if __name__ == "__main__":
    metadata = {"cluster_name": "test"}
    resources = {}
    this_ipfs_cluster_follow = ipfs_cluster_follow(resources, metadata)
    results = this_ipfs_cluster_follow.test_ipfs_cluster_follow()
    print(results)
    pass
