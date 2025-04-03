import sys
import os
import subprocess
import tempfile
import json
import logging
import time
import uuid
import re
from .error import (
    IPFSError, IPFSConnectionError, IPFSTimeoutError, IPFSContentNotFoundError,
    IPFSValidationError, IPFSConfigurationError, IPFSPinningError,
    create_result_dict, handle_error, perform_with_retry
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
        self.correlation_id = self.metadata.get('correlation_id', str(uuid.uuid4()))
        
        # Set up path configuration for binaries
        self.this_dir = os.path.dirname(os.path.realpath(__file__))
        self.path = os.environ.get('PATH', '')
        self.path = f"{self.path}:{os.path.join(self.this_dir, 'bin')}"
        
        # Extract and validate metadata
        try:
            # Extract configuration settings
            self.config = self.metadata.get('config')
            
            # Extract and validate role
            self.role = self.metadata.get('role', 'leecher')
            if self.role not in ["master", "worker", "leecher"]:
                raise IPFSValidationError(f"Invalid role: {self.role}. Must be one of: master, worker, leecher")
            
            # Extract cluster name
            self.cluster_name = self.metadata.get('cluster_name')
            
            # Extract IPFS path
            self.ipfs_path = self.metadata.get('ipfs_path', os.path.expanduser("~/.ipfs"))
            
            # Extract and set IPFS cluster path
            self.ipfs_cluster_path = self.metadata.get('ipfs_cluster_path', 
                                                     os.path.expanduser("~/.ipfs-cluster-follow"))
            
            logger.debug(f"Initialized IPFS Cluster Follow with role={self.role}, "
                         f"cluster_name={self.cluster_name}, correlation_id={self.correlation_id}")
            
        except Exception as e:
            logger.error(f"Error initializing IPFS Cluster Follow: {str(e)}")
            if isinstance(e, IPFSValidationError):
                raise
            else:
                raise IPFSConfigurationError(f"Failed to initialize IPFS Cluster Follow: {str(e)}")
                
    def run_cluster_follow_command(self, cmd_args, check=True, timeout=30, correlation_id=None, shell=False):
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
        
        result = create_result_dict(f"run_command_{operation}", correlation_id or self.correlation_id)
        result["command"] = command_str
        
        try:
            # Add environment variables if needed
            env = os.environ.copy()
            env['PATH'] = self.path
            if hasattr(self, 'ipfs_path'):
                env['IPFS_PATH'] = self.ipfs_path
            if hasattr(self, 'ipfs_cluster_path'):
                env['IPFS_CLUSTER_PATH'] = self.ipfs_cluster_path
            
            # Never use shell=True unless absolutely necessary for security
            process = subprocess.run(
                cmd_args,
                capture_output=True,
                check=check,
                timeout=timeout,
                shell=shell,
                env=env
            )
            
            # Process completed successfully
            result["success"] = True
            result["returncode"] = process.returncode
            
            # Decode stdout and stderr if they exist
            if process.stdout:
                try:
                    result["stdout"] = process.stdout.decode('utf-8')
                except UnicodeDecodeError:
                    result["stdout"] = process.stdout
                    
            if process.stderr:
                try:
                    result["stderr"] = process.stderr.decode('utf-8')
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
                    result["stdout"] = e.stdout.decode('utf-8')
                except UnicodeDecodeError:
                    result["stdout"] = e.stdout
                    
            if e.stderr:
                try:
                    result["stderr"] = e.stderr.decode('utf-8')
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
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = create_result_dict("ipfs_follow_start", correlation_id)
        
        try:
            # Validate required parameters
            cluster_name = kwargs.get('cluster_name', getattr(self, 'cluster_name', None))
            if not cluster_name:
                return handle_error(result, IPFSValidationError("Missing required parameter: cluster_name"))
            
            # Validate cluster name (prevent command injection)
            if not isinstance(cluster_name, str):
                return handle_error(result, IPFSValidationError(f"cluster_name must be a string, got {type(cluster_name).__name__}"))
            
            from .validation import is_safe_command_arg
            if not is_safe_command_arg(cluster_name):
                return handle_error(result, IPFSValidationError(f"Invalid cluster name contains shell metacharacters: {cluster_name}"))
            
            # Set timeout for commands
            timeout = kwargs.get('timeout', 30)
            
            # Different execution paths based on user privileges
            if os.getuid() == 0:
                # Running as root, use systemctl
                logger.debug("Starting ipfs-cluster-follow as root using systemctl")
                systemctl_result = self.run_cluster_follow_command(
                    ["systemctl", "start", "ipfs-cluster-follow"],
                    check=False,
                    timeout=timeout,
                    correlation_id=correlation_id
                )
                result["systemctl_result"] = systemctl_result
                
                if not systemctl_result.get("success", False):
                    logger.warning("Failed to start ipfs-cluster-follow via systemctl, will try direct execution")
            else:
                # Running as non-root user, use direct execution
                logger.debug(f"Starting ipfs-cluster-follow as non-root user for cluster: {cluster_name}")
                # Construct command arguments as a list for security
                cmd_args = ["ipfs-cluster-follow", cluster_name, "run"]
                
                direct_result = self.run_cluster_follow_command(
                    cmd_args,
                    check=False,
                    timeout=timeout,
                    correlation_id=correlation_id
                )
                result["direct_result"] = direct_result
            
            # Check if the service is running after start attempts
            process_check_cmd = ["ps", "-ef"]
            ps_result = self.run_cluster_follow_command(
                process_check_cmd,
                check=False,
                timeout=10,
                correlation_id=correlation_id
            )
            
            # Process ps output to find ipfs-cluster-follow processes
            if ps_result.get("success", False) and ps_result.get("stdout"):
                process_running = False
                for line in ps_result.get("stdout", "").splitlines():
                    if "ipfs-cluster-follow" in line and "grep" not in line:
                        process_running = True
                        break
                
                result["process_running"] = process_running
                
                # If process is not running, check for stale socket and try one more time
                if not process_running:
                    logger.warning("ipfs-cluster-follow process not found, checking for stale socket")
                    
                    # Safely check for api-socket
                    socket_path = os.path.expanduser(f"~/.ipfs-cluster-follow/{cluster_name}/api-socket")
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
                        env['PATH'] = self.path
                        if hasattr(self, 'ipfs_path'):
                            env['IPFS_PATH'] = self.ipfs_path
                        
                        # Start the process with proper list arguments
                        cmd_args = ["ipfs-cluster-follow", cluster_name, "run"]
                        process = subprocess.Popen(
                            cmd_args,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            env=env,
                            shell=False  # Never use shell=True
                        )
                        
                        # Wait briefly to check if the process started
                        time.sleep(1)
                        if process.poll() is None:  # Still running
                            result["background_process_started"] = True
                            result["process_id"] = process.pid
                        else:
                            result["background_process_started"] = False
                            stdout, stderr = process.communicate(timeout=5)
                            result["background_stdout"] = stdout.decode('utf-8', errors='replace') if stdout else ""
                            result["background_stderr"] = stderr.decode('utf-8', errors='replace') if stderr else ""
                    
                    except Exception as e:
                        logger.error(f"Failed to start background process: {str(e)}")
                        result["background_process_started"] = False
                        result["background_error"] = str(e)
            
            # Determine final success based on results
            result["success"] = result.get("process_running", False) or result.get("background_process_started", False)
            
            if result["success"]:
                logger.info(f"Successfully started ipfs-cluster-follow for cluster: {cluster_name}")
            else:
                logger.error(f"Failed to start ipfs-cluster-follow for cluster: {cluster_name}")
            
            return result
            
        except Exception as e:
            logger.exception(f"Unexpected error in ipfs_follow_start: {str(e)}")
            return handle_error(result, e)

    def ipfs_follow_stop(self, **kwargs):
        """Stop the IPFS cluster-follow service.
        
        Args:
            **kwargs: Optional arguments
                - cluster_name: Name of the cluster to stop following
                - correlation_id: ID for tracking related operations
                - timeout: Command timeout in seconds
                - force: Whether to force-kill the process
        
        Returns:
            Dictionary with operation result information
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = create_result_dict("ipfs_follow_stop", correlation_id)
        
        try:
            # Validate required parameters
            cluster_name = kwargs.get('cluster_name', getattr(self, 'cluster_name', None))
            if not cluster_name:
                return handle_error(result, IPFSValidationError("Missing required parameter: cluster_name"))
            
            # Validate cluster name (prevent command injection)
            if not isinstance(cluster_name, str):
                return handle_error(result, IPFSValidationError(f"cluster_name must be a string, got {type(cluster_name).__name__}"))
            
            if re.search(r'[;&|"`\'$<>]', cluster_name):
                return handle_error(result, IPFSValidationError(f"Invalid cluster name contains shell metacharacters: {cluster_name}"))
            
            # Set timeout for commands
            timeout = kwargs.get('timeout', 30)
            force = kwargs.get('force', False)
            
            # Different execution paths based on user privileges
            if os.getuid() == 0:
                # Running as root, use systemctl
                logger.debug("Stopping ipfs-cluster-follow as root using systemctl")
                systemctl_result = self.run_cluster_follow_command(
                    ["systemctl", "stop", "ipfs-cluster-follow"],
                    check=False,
                    timeout=timeout,
                    correlation_id=correlation_id
                )
                result["systemctl_result"] = systemctl_result
            else:
                # Running as non-root user, use direct execution
                logger.debug(f"Stopping ipfs-cluster-follow as non-root user for cluster: {cluster_name}")
                # Construct command arguments as a list for security
                cmd_args = ["ipfs-cluster-follow", cluster_name, "stop"]
                
                direct_result = self.run_cluster_follow_command(
                    cmd_args,
                    check=False,
                    timeout=timeout,
                    correlation_id=correlation_id
                )
                result["direct_result"] = direct_result
            
            # Check for any remaining processes and kill them if needed
            process_check_cmd = ["ps", "-ef"]
            ps_result = self.run_cluster_follow_command(
                process_check_cmd,
                check=False,
                timeout=10,
                correlation_id=correlation_id
            )
            
            # Process ps output to find and kill ipfs-cluster-follow processes
            pids_to_kill = []
            if ps_result.get("success", False) and ps_result.get("stdout"):
                for line in ps_result.get("stdout", "").splitlines():
                    if "ipfs-cluster-follow" in line and "grep" not in line:
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
                    # Use SIGTERM by default, SIGKILL if force=True
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
            socket_path = os.path.expanduser(f"~/.ipfs-cluster-follow/{cluster_name}/api-socket")
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
            ps_result = self.run_cluster_follow_command(
                ["ps", "-ef"],
                check=False,
                timeout=10,
                correlation_id=correlation_id
            )
            
            all_stopped = True
            if ps_result.get("success", False) and ps_result.get("stdout"):
                for line in ps_result.get("stdout", "").splitlines():
                    if "ipfs-cluster-follow" in line and "grep" not in line:
                        all_stopped = False
                        break
            
            result["all_processes_stopped"] = all_stopped
            
            # Determine final success
            result["success"] = (
                (result.get("systemctl_result", {}).get("success", False) or 
                 result.get("direct_result", {}).get("success", False)) and
                all_stopped
            )
            
            if result["success"]:
                logger.info(f"Successfully stopped ipfs-cluster-follow for cluster: {cluster_name}")
            else:
                logger.warning(f"May not have fully stopped ipfs-cluster-follow for cluster: {cluster_name}")
            
            return result
            
        except Exception as e:
            logger.exception(f"Unexpected error in ipfs_follow_stop: {str(e)}")
            return handle_error(result, e)

#    def ipfs_follow_run(self, **kwargs):
#        if "cluster_name" in list(self.keys()):
#            cluster_name = self.cluster_name
#        if "cluster_name" in kwargs:
#            cluster_name = kwargs['cluster_name']
#
#        command = "ipfs cluster-follow " + cluster_name + " run"
#        results = subprocess.check_output(command, shell=True)
#        results = results.decode()
#        return results

    def ipfs_follow_list(self, **kwargs):
        """List trusted peers for the specified cluster.
        
        Args:
            **kwargs: Optional arguments
                - cluster_name: Name of the cluster
                - correlation_id: ID for tracking related operations
                - timeout: Command timeout in seconds
        
        Returns:
            Dictionary with operation result information
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = create_result_dict("ipfs_follow_list", correlation_id)
        
        try:
            # Validate required parameters
            cluster_name = kwargs.get('cluster_name', getattr(self, 'cluster_name', None))
            if not cluster_name:
                return handle_error(result, IPFSValidationError("Missing required parameter: cluster_name"))
            
            # Validate cluster name (prevent command injection)
            if not isinstance(cluster_name, str):
                return handle_error(result, IPFSValidationError(f"cluster_name must be a string, got {type(cluster_name).__name__}"))
            
            if re.search(r'[;&|"`\'$<>]', cluster_name):
                return handle_error(result, IPFSValidationError(f"Invalid cluster name contains shell metacharacters: {cluster_name}"))
            
            # Set timeout for commands
            timeout = kwargs.get('timeout', 30)
            
            # Execute the command with proper arguments
            cmd_args = ["ipfs-cluster-follow", cluster_name, "list"]
            cmd_result = self.run_cluster_follow_command(
                cmd_args,
                check=False,
                timeout=timeout,
                correlation_id=correlation_id
            )
            
            if not cmd_result.get("success", False):
                result["command_result"] = cmd_result
                return result
            
            # Parse the output into a structured format
            stdout = cmd_result.get("stdout", "")
            if not stdout:
                result["success"] = True
                result["peers"] = {}
                return result
            
            # Process the output
            peers = {}
            for line in stdout.split("\n"):
                if not line.strip():
                    continue
                
                # Normalize whitespace
                line = re.sub(r'\s+', ' ', line.strip())
                
                # Split into components (assuming format: "ID NAME")
                parts = line.split(" ", 1)
                if len(parts) >= 2:
                    peer_id = parts[0]
                    peer_name = parts[1]
                    peers[peer_name] = peer_id
            
            result["success"] = True
            result["peers"] = peers
            result["peer_count"] = len(peers)
            
            logger.debug(f"Found {len(peers)} trusted peers for cluster: {cluster_name}")
            return result
            
        except Exception as e:
            logger.exception(f"Unexpected error in ipfs_follow_list: {str(e)}")
            return handle_error(result, e)

    def ipfs_follow_info(self, **kwargs):
        """Get information about the specified cluster.
        
        Args:
            **kwargs: Optional arguments
                - cluster_name: Name of the cluster
                - correlation_id: ID for tracking related operations
                - timeout: Command timeout in seconds
        
        Returns:
            Dictionary with operation result information
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = create_result_dict("ipfs_follow_info", correlation_id)
        
        try:
            # Validate required parameters
            cluster_name = kwargs.get('cluster_name', getattr(self, 'cluster_name', None))
            if not cluster_name:
                return handle_error(result, IPFSValidationError("Missing required parameter: cluster_name"))
            
            # Validate cluster name (prevent command injection)
            if not isinstance(cluster_name, str):
                return handle_error(result, IPFSValidationError(f"cluster_name must be a string, got {type(cluster_name).__name__}"))
            
            if re.search(r'[;&|"`\'$<>]', cluster_name):
                return handle_error(result, IPFSValidationError(f"Invalid cluster name contains shell metacharacters: {cluster_name}"))
            
            # Set timeout for commands
            timeout = kwargs.get('timeout', 30)
            
            # Execute the command with proper arguments
            cmd_args = ["ipfs-cluster-follow", cluster_name, "info"]
            cmd_result = self.run_cluster_follow_command(
                cmd_args,
                check=False,
                timeout=timeout,
                correlation_id=correlation_id
            )
            
            if not cmd_result.get("success", False):
                result["command_result"] = cmd_result
                return result
            
            # Parse the output into a structured format
            stdout = cmd_result.get("stdout", "")
            if not stdout:
                result["success"] = True
                result["info"] = {"cluster_name": cluster_name}
                return result
            
            # Process the output by parsing key-value pairs
            cluster_info = {"cluster_name": cluster_name}
            lines = stdout.strip().split("\n")
            
            # Define expected fields with their labels in the output
            expected_fields = {
                "config_folder": "Configuration folder",
                "config_source": "Configuration source",
                "cluster_peer_online": "Cluster Peer online",
                "ipfs_peer_online": "IPFS Peer online"
            }
            
            # Extract information from the output lines
            for line in lines:
                line = line.strip()
                if not line or ":" not in line:
                    continue
                
                # Split on first colon to handle potential colons in values
                key_label, value = line.split(":", 1)
                key_label = key_label.strip()
                value = value.strip()
                
                # Map the output label to our standardized field names
                for field_name, label in expected_fields.items():
                    if label in key_label:
                        cluster_info[field_name] = value
                        break
            
            result["success"] = True
            result["info"] = cluster_info
            
            # Add some derived fields for convenience
            if "cluster_peer_online" in cluster_info:
                result["is_online"] = cluster_info["cluster_peer_online"].lower() == "yes"
            
            logger.debug(f"Retrieved info for cluster: {cluster_name}")
            return result
            
        except Exception as e:
            logger.exception(f"Unexpected error in ipfs_follow_info: {str(e)}")
            return handle_error(result, e)
        
    
    def ipfs_follow_run(self, **kwargs):
        """Run the IPFS cluster-follow service in the foreground.
        
        Args:
            **kwargs: Optional arguments
                - cluster_name: Name of the cluster to follow
                - correlation_id: ID for tracking related operations
                - timeout: Command timeout in seconds
        
        Returns:
            Dictionary with operation result information
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = create_result_dict("ipfs_follow_run", correlation_id)
        
        try:
            # Validate required parameters
            cluster_name = kwargs.get('cluster_name', getattr(self, 'cluster_name', None))
            if not cluster_name:
                return handle_error(result, IPFSValidationError("Missing required parameter: cluster_name"))
            
            # Validate cluster name (prevent command injection)
            if not isinstance(cluster_name, str):
                return handle_error(result, IPFSValidationError(f"cluster_name must be a string, got {type(cluster_name).__name__}"))
            
            if re.search(r'[;&|"`\'$<>]', cluster_name):
                return handle_error(result, IPFSValidationError(f"Invalid cluster name contains shell metacharacters: {cluster_name}"))
            
            # Set timeout for commands - default is higher for run command as it typically runs until interrupted
            timeout = kwargs.get('timeout', 60)
            
            # Remove stale socket if it exists to avoid bind errors
            socket_path = os.path.expanduser(f"~/.ipfs-cluster-follow/{cluster_name}/api-socket")
            if os.path.exists(socket_path):
                logger.debug(f"Removing stale socket at: {socket_path}")
                try:
                    os.remove(socket_path)
                    result["socket_removed"] = True
                except (PermissionError, OSError) as e:
                    logger.error(f"Failed to remove stale socket: {str(e)}")
                    result["socket_removed"] = False
                    result["socket_error"] = str(e)
            
            # Execute the command with proper arguments
            cmd_args = ["ipfs-cluster-follow", cluster_name, "run"]
            
            logger.info(f"Running ipfs-cluster-follow in foreground for cluster: {cluster_name}")
            logger.warning("This command will block until terminated")
            
            cmd_result = self.run_cluster_follow_command(
                cmd_args,
                check=False,
                timeout=timeout,
                correlation_id=correlation_id
            )
            
            result["command_result"] = cmd_result
            result["success"] = cmd_result.get("success", False)
            
            # Extract output lines for analysis
            if cmd_result.get("stdout"):
                result["output_lines"] = cmd_result.get("stdout", "").strip().split("\n")
                
                # Look for indication of successful startup
                for line in result["output_lines"]:
                    if "Listening on" in line or "Starting IPFS Cluster" in line:
                        result["service_started"] = True
                        break
            
            if not result.get("success", False):
                logger.error(f"Failed to run ipfs-cluster-follow for cluster: {cluster_name}")
                if cmd_result.get("stderr"):
                    logger.error(f"Error output: {cmd_result.get('stderr')}")
            
            return result
            
        except Exception as e:
            logger.exception(f"Unexpected error in ipfs_follow_run: {str(e)}")
            return handle_error(result, e)


    def test_ipfs_cluster_follow(self, **kwargs):
        """Test if ipfs-cluster-follow binary is available in the PATH.
        
        Args:
            **kwargs: Optional arguments
                - correlation_id: ID for tracking related operations
                
        Returns:
            Boolean indicating if ipfs-cluster-follow is available
        """
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = create_result_dict("test_ipfs_cluster_follow", correlation_id)
        
        try:
            # Use the 'which' command to check for binary existence using run_cluster_follow_command
            cmd_result = self.run_cluster_follow_command(
                ["which", "ipfs-cluster-follow"],
                check=False,
                correlation_id=correlation_id
            )
            
            if cmd_result.get("success", False) and cmd_result.get("returncode", 1) == 0:
                detected_path = cmd_result.get("stdout", "").strip()
                if detected_path:
                    logger.debug(f"Found ipfs-cluster-follow at: {detected_path}")
                    result["success"] = True
                    result["binary_path"] = detected_path
                    return True
            
            logger.warning("ipfs-cluster-follow binary not found in PATH")
            return False
            
        except Exception as e:
            logger.exception(f"Error testing for ipfs-cluster-follow: {str(e)}")
            return False
    
    def ipfs_follow_sync(self, **kwargs):
        """Synchronize the worker node with the master's state.
        
        Args:
            **kwargs: Optional arguments
                - cluster_name: Name of the cluster
                - correlation_id: ID for tracking related operations
                - timeout: Command timeout in seconds
        
        Returns:
            Dictionary with operation result information
        """
        # Create standardized result dictionary
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = create_result_dict("ipfs_follow_sync", correlation_id)
        
        try:
            # Validate required parameters
            cluster_name = kwargs.get('cluster_name', getattr(self, 'cluster_name', None))
            if not cluster_name:
                return handle_error(result, IPFSValidationError("Missing required parameter: cluster_name"))
            
            # Validate cluster name (prevent command injection)
            if not isinstance(cluster_name, str):
                return handle_error(result, IPFSValidationError(f"cluster_name must be a string, got {type(cluster_name).__name__}"))
            
            if re.search(r'[;&|"`\'$<>]', cluster_name):
                return handle_error(result, IPFSValidationError(f"Invalid cluster name contains shell metacharacters: {cluster_name}"))
            
            # Set timeout for commands
            timeout = kwargs.get('timeout', 30)
            
            # Execute the command with proper arguments
            cmd_args = ["ipfs-cluster-follow", cluster_name, "sync"]
            cmd_result = self.run_cluster_follow_command(
                cmd_args,
                check=False,
                timeout=timeout,
                correlation_id=correlation_id
            )
            
            if not cmd_result.get("success", False):
                result["command_result"] = cmd_result
                return result
            
            # Parse the output into a structured format
            stdout = cmd_result.get("stdout", "")
            result["command_output"] = stdout
            
            # Success by default
            result["success"] = True
            
            # Parse output to extract metrics
            sync_metrics = {
                "synced": 0,
                "pins_added": 0,
                "pins_removed": 0
            }
            
            # Simple parsing for example metrics - adjust based on actual output format
            if stdout:
                # Parse pins synced
                synced_match = re.search(r'synced (\d+)', stdout)
                if synced_match:
                    sync_metrics["synced"] = int(synced_match.group(1))
                    
                # Parse pins added
                added_match = re.search(r'added (\d+)', stdout)
                if added_match:
                    sync_metrics["pins_added"] = int(added_match.group(1))
                    
                # Parse pins removed
                removed_match = re.search(r'removed (\d+)', stdout)
                if removed_match:
                    sync_metrics["pins_removed"] = int(removed_match.group(1))
            
            # Update result with metrics
            result.update(sync_metrics)
            logger.info(f"Synchronized with cluster: {cluster_name}. Added: {sync_metrics['pins_added']}, Removed: {sync_metrics['pins_removed']}")
            
            return result
            
        except Exception as e:
            logger.exception(f"Unexpected error in ipfs_follow_sync: {str(e)}")
            return handle_error(result, e)

    def test(self, **kwargs):
        """Run all tests for ipfs-cluster-follow functionality.
        
        Args:
            **kwargs: Optional arguments
                - correlation_id: ID for tracking related operations
                
        Returns:
            Dictionary with test results
        """
        correlation_id = kwargs.get('correlation_id', self.correlation_id)
        result = create_result_dict("test", correlation_id)
        
        try:
            # Test if ipfs-cluster-follow binary is available
            follow_available = self.test_ipfs_cluster_follow(correlation_id=correlation_id)
            result["ipfs_cluster_follow_available"] = follow_available
            
            # Set overall success based on test results
            result["success"] = follow_available
            
            # Check environment
            result["environment"] = {
                "path": self.path,
                "role": getattr(self, "role", "unknown"),
                "ipfs_path": getattr(self, "ipfs_path", "not set"),
                "ipfs_cluster_path": getattr(self, "ipfs_cluster_path", "not set")
            }
            
            if follow_available:
                logger.info("IPFS Cluster Follow tests passed")
            else:
                logger.warning("IPFS Cluster Follow tests failed: binary not available")
                
            return result
            
        except Exception as e:
            logger.exception(f"Error during tests: {str(e)}")
            return handle_error(result, e)

ipfs_cluster_follow = ipfs_cluster_follow
if __name__ == "__main__":
    metadata = {
        "cluster_name": "test"
    }
    resources = {
        
    }
    this_ipfs_cluster_follow = ipfs_cluster_follow(resources, metadata)
    results = this_ipfs_cluster_follow.test_ipfs_cluster_follow()
    print(results)
    pass
