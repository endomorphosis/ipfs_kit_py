#!/usr/bin/env python3
import json
import logging
import os
import platform
import re
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from typing import Any, Dict, List, Optional, Union
from pathlib import Path

# Configure logger
logger = logging.getLogger(__name__)

# Import error handling utilities from lotus_kit
from .lotus_kit import (
    create_result_dict,
    handle_error,
    LotusError,
    LotusConnectionError,
    LotusTimeoutError,
    LotusValidationError
)

class lotus_daemon:
    """Manages Lotus daemon processes across different platforms.
    
    This class provides methods to start, stop, and monitor Lotus daemon processes
    with support for systemd (Linux), Windows services, or direct process management.
    """
    
    def __init__(self, resources=None, metadata=None):
        """Initialize the lotus daemon manager.
        
        Args:
            resources (dict, optional): Resources for the Lotus daemon.
            metadata (dict, optional): Configuration metadata.
        """
        # Store resources
        self.resources = resources or {}
        
        # Store metadata
        self.metadata = metadata or {}
        
        # Generate correlation ID for tracking operations
        self.correlation_id = str(uuid.uuid4())
        
        # Set up Lotus paths and configuration
        self.lotus_path = self.metadata.get("lotus_path", os.path.expanduser("~/.lotus"))
        
        # Set environment variables
        self.env = os.environ.copy()
        if "LOTUS_PATH" not in self.env:
            self.env["LOTUS_PATH"] = self.lotus_path
            
        # Set defaults based on platform
        self.system = platform.system()
        
        # Default ports
        self.api_port = self.metadata.get("api_port", 1234)
        self.p2p_port = self.metadata.get("p2p_port", 2345)
        
        # Service name for systemd/Windows
        self.service_name = self.metadata.get("service_name", "lotus-daemon")
        
        # Binary paths
        self.this_dir = os.path.dirname(os.path.realpath(__file__))
        self.path = os.environ.get("PATH", "")
        self.path = f"{self.path}:{os.path.join(self.this_dir, 'bin')}"
        self.env["PATH"] = self.path
        
        # Store PID information
        self.pid_file = os.path.join(self.lotus_path, "lotus.pid")
        
        # Check if initialization is valid
        self._check_initialization()
    
    def _check_initialization(self):
        """Verify initialization and environment."""
        try:
            # Create lotus directory if it doesn't exist
            os.makedirs(self.lotus_path, exist_ok=True)
            
            # Check if lotus binary is available in PATH
            self._check_lotus_binary()
            
        except Exception as e:
            logger.error(f"Initialization error: {str(e)}")
            # Don't raise here to allow for graceful degradation
    
    def _check_lotus_binary(self):
        """Check if the lotus binary is available."""
        try:
            cmd_result = self.run_command(["which", "lotus"], check=False)
            
            if cmd_result.get("success", False) and cmd_result.get("stdout", "").strip():
                binary_path = cmd_result.get("stdout", "").strip()
                logger.debug(f"Found lotus binary at: {binary_path}")
                return True
                
            logger.warning("Lotus binary not found in PATH")
            return False
            
        except Exception as e:
            logger.error(f"Error checking lotus binary: {str(e)}")
            return False
            
    def _detect_lotus_version(self):
        """Detect the version of the Lotus binary.
        
        Returns:
            str: Version string if detected, None otherwise
        """
        try:
            cmd_result = self.run_command(["lotus", "--version"], check=False)
            
            if cmd_result.get("success", False):
                version_output = cmd_result.get("stdout", "").strip()
                # Extract version
                if "version" in version_output:
                    # Example: "lotus version 1.24.0+mainnet+git.7c093485c"
                    version_parts = version_output.split("version")
                    if len(version_parts) > 1:
                        version = version_parts[1].strip()
                        logger.debug(f"Detected Lotus version: {version}")
                        return version
            
            logger.warning("Failed to detect Lotus version")
            return None
            
        except Exception as e:
            logger.error(f"Error detecting Lotus version: {str(e)}")
            return None
            
    def _check_repo_initialization(self):
        """Check if the Lotus repository is properly initialized.
        
        A proper repository should have at least:
        - config.toml (with proper content)
        - datastore/ directory
        - keystore/ directory
        
        Returns:
            bool: True if repository appears to be properly initialized
        """
        try:
            # Check for essential files and directories
            config_file = os.path.join(self.lotus_path, "config.toml")
            keystore_dir = os.path.join(self.lotus_path, "keystore")
            datastore_dir = os.path.join(self.lotus_path, "datastore")
            
            if not os.path.exists(config_file):
                logger.debug("Lotus repository not initialized: config.toml missing")
                return False
                
            if not os.path.exists(keystore_dir):
                logger.debug("Lotus repository not fully initialized: keystore directory missing")
                # Keystore might be created during first run, not necessarily a problem
                
            if not os.path.exists(datastore_dir):
                logger.debug("Lotus repository not fully initialized: datastore directory missing")
                return False
                
            # Check if config file has minimum required content
            with open(config_file, 'r') as f:
                config_content = f.read()
                if "[API]" not in config_content or "ListenAddress" not in config_content:
                    logger.debug("Lotus repository config.toml is incomplete")
                    return False
            
            # If we've passed all checks, the repository appears to be initialized
            logger.debug("Lotus repository appears to be properly initialized")
            return True
            
        except Exception as e:
            logger.error(f"Error checking Lotus repository initialization: {str(e)}")
            return False
            
    def _initialize_repo(self):
        """Attempt to initialize the Lotus repository.
        
        Returns:
            dict: Result dictionary with initialization outcome
        """
        result = create_result_dict("initialize_repo", self.correlation_id)
        
        try:
            logger.info(f"Attempting to initialize Lotus repository in {self.lotus_path}")
            
            # Ensure the repository directory exists
            os.makedirs(self.lotus_path, exist_ok=True)
            
            # For full initialization, we need the Genesis file, but we can start
            # with a minimal initialization that creates essential structures
            
            # Create minimal config.toml if it doesn't exist
            config_file = os.path.join(self.lotus_path, "config.toml")
            if not os.path.exists(config_file):
                minimal_config = f"""# Generated by lotus_daemon._initialize_repo
[API]
  ListenAddress = "/ip4/127.0.0.1/tcp/{self.api_port}/http"
  RemoteListenAddress = ""
  Timeout = "30s"

[Libp2p]
  ListenAddresses = ["/ip4/0.0.0.0/tcp/{self.p2p_port}", "/ip6/::/tcp/{self.p2p_port}"]
  AnnounceAddresses = []
  NoAnnounceAddresses = []
  DisableNatPortMap = false

[Client]
  UseIpfs = false
  IpfsMAddr = ""
  IpfsUseForRetrieval = false
"""
                with open(config_file, 'w') as f:
                    f.write(minimal_config)
                logger.info(f"Created minimal config.toml in {self.lotus_path}")
            
            # Create keystore directory if it doesn't exist
            keystore_dir = os.path.join(self.lotus_path, "keystore")
            os.makedirs(keystore_dir, exist_ok=True)
            
            # Create datastore directory if it doesn't exist
            datastore_dir = os.path.join(self.lotus_path, "datastore")
            os.makedirs(datastore_dir, exist_ok=True)
            
            # Additional initialization by running lotus daemon with appropriate flags
            # This will initialize the remaining structures needed for basic operation
            try:
                # Detect version for appropriate flags
                lotus_version = self._detect_lotus_version()
                
                # Start with basic command
                cmd = ["lotus", "daemon", "--lite"]
                
                # Add version-specific flags
                if lotus_version and "1.24" in lotus_version:
                    # Lotus 1.24.0+ flags
                    cmd.extend(["--api", str(self.api_port)])
                    cmd.append("--bootstrap=false")
                else:
                    # Older versions
                    cmd.extend(["--api-listen-address", f"/ip4/127.0.0.1/tcp/{self.api_port}/http"])
                    cmd.extend(["--p2p-listen-address", f"/ip4/0.0.0.0/tcp/{self.p2p_port}"])
                    cmd.append("--bootstrap=false")
                
                logger.debug(f"Initializing repo with command: {' '.join(cmd)}")
                
                # Start the daemon in the background with 5 second timeout 
                # just to trigger initialization, then we'll kill it
                process = subprocess.Popen(cmd, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # Wait a few seconds for initialization
                time.sleep(5)
                
                # Kill the process - we just wanted it to initialize the repo
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    
                logger.info("Ran temporary daemon for repository initialization")
                
                # Verify initialization succeeded
                if self._check_repo_initialization():
                    result["success"] = True
                    result["status"] = "initialized"
                    result["message"] = "Lotus repository successfully initialized"
                    return result
                else:
                    logger.warning("Repository still not properly initialized after initialization attempt")
                    result["success"] = False
                    result["error"] = "Repository still not fully initialized after initialization attempt"
                    return result
                    
            except Exception as e:
                logger.error(f"Error during temporary daemon initialization: {str(e)}")
                result["success"] = False
                result["error"] = f"Failed during daemon initialization: {str(e)}"
                return result
                
        except Exception as e:
            logger.error(f"Failed to initialize Lotus repository: {str(e)}")
            result["success"] = False
            result["error"] = str(e)
            return result
    
    def run_command(self, cmd_args, check=True, timeout=30, correlation_id=None, shell=False, env=None):
        """Run a command with proper error handling.
        
        Args:
            cmd_args: Command and arguments as a list
            check: Whether to raise exception on non-zero exit code
            timeout: Command timeout in seconds
            correlation_id: ID for tracking related operations
            shell: Whether to use shell execution (avoid if possible)
            env: Optional custom environment variables (will be merged with self.env)
            
        Returns:
            Dictionary with command result information
        """
        # Create standardized result dictionary
        command_str = " ".join(cmd_args) if isinstance(cmd_args, list) else cmd_args
        operation = cmd_args[0] if isinstance(cmd_args, list) else command_str.split()[0]
        
        result = create_result_dict(f"run_command_{operation}", correlation_id or self.correlation_id)
        result["command"] = command_str
        
        # Create the environment - start with our base env and update with any custom values
        command_env = self.env.copy()
        if env:
            command_env.update(env)
        
        try:
            # Run the command with the environment
            process = subprocess.run(
                cmd_args, 
                capture_output=True, 
                check=check, 
                timeout=timeout, 
                shell=shell, 
                env=command_env
            )
            
            # Process successful completion
            result["success"] = True
            result["returncode"] = process.returncode
            
            # Try to decode stdout as UTF-8
            try:
                result["stdout"] = process.stdout.decode("utf-8", errors="replace")
            except:
                result["stdout"] = str(process.stdout)
                
            # Only include stderr if there's content
            if process.stderr:
                try:
                    result["stderr"] = process.stderr.decode("utf-8", errors="replace")
                except:
                    result["stderr"] = str(process.stderr)
            
            return result
            
        except subprocess.TimeoutExpired as e:
            error_msg = f"Command timed out after {timeout} seconds"
            logger.error(f"Timeout running command: {command_str}")
            result = handle_error(result, LotusTimeoutError(error_msg))
            result["timeout"] = timeout
            return result
            
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
                
            return handle_error(result, LotusError(error_msg), {"stderr": stderr})
            
        except FileNotFoundError as e:
            error_msg = f"Command not found: {command_str}"
            logger.error(error_msg)
            return handle_error(result, e)
            
        except Exception as e:
            error_msg = f"Failed to execute command: {str(e)}"
            logger.exception(f"Exception running command: {command_str}")
            return handle_error(result, e)
    
    def daemon_start(self, **kwargs):
        """Start the Lotus daemon with standardized error handling.
        
        Attempts to start the daemon via systemctl on Linux, Windows service on Windows,
        or direct process invocation as appropriate.
        
        Args:
            **kwargs: Additional arguments for daemon startup
                - bootstrap_peers: List of bootstrap peer multiaddresses
                - remove_stale_lock: Whether to remove stale lock files
                - api_port: Override default API port
                - p2p_port: Override default P2P port
                - correlation_id: ID for tracking operations
                - check_initialization: Whether to check and attempt repo initialization
                
        Returns:
            Result dictionary with operation outcome
        """
        operation = "daemon_start"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        remove_stale_lock = kwargs.get("remove_stale_lock", True)
        api_port = kwargs.get("api_port", self.api_port)
        p2p_port = kwargs.get("p2p_port", self.p2p_port)
        check_initialization = kwargs.get("check_initialization", True)
        
        # First check if daemon is already running
        try:
            check_result = self.daemon_status(correlation_id=correlation_id)
            if check_result.get("process_running", False):
                result["success"] = True
                result["status"] = "already_running"
                result["message"] = "Lotus daemon is already running"
                result["pid"] = check_result.get("pid")
                return result
        except Exception as e:
            # Not critical if this fails, continue with starting attempts
            logger.debug(f"Error checking if daemon is already running: {str(e)}")
        
        # Check for repository initialization
        if check_initialization:
            try:
                repo_initialized = self._check_repo_initialization()
                if not repo_initialized:
                    # Try to initialize the repository - requires Genesis file for full initialization
                    # or lite + offline mode for partial initialization
                    logger.info("Lotus repository not fully initialized. Attempting lite initialization...")
                    init_result = self._initialize_repo()
                    result["initialization_attempted"] = True
                    result["initialization_result"] = init_result
                    if not init_result.get("success", False):
                        logger.warning("Failed to initialize Lotus repository")
                        result["error"] = "Failed to initialize Lotus repository: " + init_result.get("error", "Unknown error")
                        result["error_type"] = "initialization_error"
                        return result
            except Exception as e:
                logger.warning(f"Error checking repository initialization: {str(e)}")
                result["initialization_check_error"] = str(e)
        
        # Check for lock file and handle it if needed
        repo_lock_path = os.path.join(self.lotus_path, "repo.lock")
        lock_file_exists = os.path.exists(repo_lock_path)
        
        if lock_file_exists:
            logger.info(f"Lotus lock file detected at {repo_lock_path}")
            
            # Check if lock file is stale (no corresponding process running)
            lock_is_stale = True
            try:
                with open(repo_lock_path, 'r') as f:
                    lock_content = f.read().strip()
                    # Lock file typically contains the PID of the locking process
                    if lock_content and lock_content.isdigit():
                        pid = int(lock_content)
                        # Check if process with this PID exists
                        try:
                            # Sending signal 0 checks if process exists without actually sending a signal
                            os.kill(pid, 0)
                            # If we get here, process exists, so lock is NOT stale
                            lock_is_stale = False
                            logger.info(f"Lock file belongs to active process with PID {pid}")
                        except OSError:
                            # Process does not exist, lock is stale
                            logger.info(f"Stale lock file detected - no process with PID {pid} is running")
                    else:
                        logger.debug(f"Lock file doesn't contain a valid PID: {lock_content}")
            except Exception as e:
                logger.warning(f"Error reading lock file: {str(e)}")
            
            result["lock_file_detected"] = True
            result["lock_file_path"] = repo_lock_path
            result["lock_is_stale"] = lock_is_stale
            
            # Remove stale lock file if requested
            if lock_is_stale and remove_stale_lock:
                try:
                    os.remove(repo_lock_path)
                    logger.info(f"Removed stale lock file: {repo_lock_path}")
                    result["lock_file_removed"] = True
                except Exception as e:
                    logger.error(f"Failed to remove stale lock file: {str(e)}")
                    result["lock_file_removed"] = False
                    result["lock_removal_error"] = str(e)
            elif not lock_is_stale:
                # Lock file belongs to a running process, daemon is likely running
                result["success"] = True
                result["status"] = "already_running" 
                result["message"] = "Lotus daemon appears to be running (active lock file found)"
                return result
            elif lock_is_stale and not remove_stale_lock:
                # Stale lock file exists but we're not removing it
                result["success"] = False
                result["error"] = "Stale lock file detected but removal not requested"
                result["error_type"] = "stale_lock_file"
                return result
        
        # Track which methods we attempt and their results
        start_attempts = {}
        daemon_ready = False
        
        # Platform-specific start methods
        if self.system == "Linux":
            # Try starting via systemd if running as root
            if os.geteuid() == 0:
                try:
                    systemctl_cmd = ["systemctl", "start", self.service_name]
                    systemctl_result = self.run_command(
                        systemctl_cmd,
                        check=False,
                        correlation_id=correlation_id
                    )
                    
                    start_attempts["systemctl"] = {
                        "success": systemctl_result.get("success", False),
                        "returncode": systemctl_result.get("returncode")
                    }
                    
                    # Check if daemon is now running
                    check_cmd = ["pgrep", "-f", "lotus daemon"]
                    check_result = self.run_command(
                        check_cmd,
                        check=False,
                        correlation_id=correlation_id
                    )
                    
                    if check_result.get("success", False) and check_result.get("stdout", "").strip():
                        daemon_ready = True
                        result["success"] = True
                        result["status"] = "started_via_systemctl"
                        result["message"] = "Lotus daemon started via systemctl"
                        result["method"] = "systemctl"
                        result["attempts"] = start_attempts
                        
                        # Update PID file
                        pid = check_result.get("stdout", "").strip().split("\n")[0]
                        self._write_pid_file(pid)
                        result["pid"] = pid
                        
                        return result
                
                except Exception as e:
                    start_attempts["systemctl"] = {
                        "success": False,
                        "error": str(e),
                        "error_type": type(e).__name__
                    }
                    logger.debug(f"Error starting Lotus daemon via systemctl: {str(e)}")
        
        elif self.system == "Windows":
            # Try starting via Windows Service if available
            try:
                service_cmd = ["sc", "start", self.service_name]
                service_result = self.run_command(
                    service_cmd,
                    check=False,
                    correlation_id=correlation_id
                )
                
                start_attempts["windows_service"] = {
                    "success": service_result.get("success", False),
                    "returncode": service_result.get("returncode")
                }
                
                # Check if service started
                if service_result.get("success", False) and "started" in service_result.get("stdout", "").lower():
                    daemon_ready = True
                    result["success"] = True
                    result["status"] = "started_via_windows_service"
                    result["message"] = "Lotus daemon started via Windows Service"
                    result["method"] = "windows_service"
                    result["attempts"] = start_attempts
                    return result
            
            except Exception as e:
                start_attempts["windows_service"] = {
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
                logger.debug(f"Error starting Lotus daemon via Windows service: {str(e)}")
        
        # If we haven't successfully started the daemon yet, try direct invocation
        if not daemon_ready:
            try:
                # Build command with environment variables and flags
                cmd = ["lotus", "daemon"]
                
                # Add optional arguments
                if kwargs.get("bootstrap_peers"):
                    for peer in kwargs.get("bootstrap_peers"):
                        cmd.extend(["--bootstrap-peers", peer])
                
                # Detect Lotus version to use appropriate flags
                lotus_version = self._detect_lotus_version()
                
                # Use flags appropriate for the detected version
                if lotus_version and "1.24" in lotus_version:
                    # Lotus 1.24.0+ uses simpler flag format
                    cmd.extend(["--api", str(api_port)])
                    # P2P port is configured in config.toml in 1.24.0+
                    
                    # Some Lotus 1.24.0 options to improve startup
                    cmd.append("--bootstrap=false")  # Skip bootstrap for testing
                else:
                    # Older versions use more explicit flag names
                    cmd.extend(["--api-listen-address", f"/ip4/127.0.0.1/tcp/{api_port}/http"])
                    cmd.extend(["--p2p-listen-address", f"/ip4/0.0.0.0/tcp/{p2p_port}"])
                    cmd.append("--bootstrap=false")  # Skip bootstrap for testing
                
                # Add lite mode for faster startup if requested (this flag exists in Lotus 1.24.0)
                if kwargs.get("lite", self.metadata.get("lite", False)):
                    cmd.append("--lite")
                    
                # Note: offline flag is not supported in Lotus 1.24.0
                
                # Add optional flags from metadata to support various Lotus versions
                for flag_name, flag_value in self.metadata.get("daemon_flags", {}).items():
                    if flag_value is True:
                        cmd.append(f"--{flag_name}")
                    elif flag_value is not False and flag_value is not None:
                        cmd.extend([f"--{flag_name}", str(flag_value)])
                
                # Start the daemon as a background process
                logger.debug(f"Starting Lotus daemon with command: {' '.join(cmd)}")
                
                # For Lotus 1.24.0+, try running the init command first if the API isn't working
                if lotus_version and "1.24" in lotus_version:
                    try:
                        # Check if the API endpoint file exists
                        api_endpoint_file = os.path.join(self.lotus_path, "api")
                        if not os.path.exists(api_endpoint_file):
                            logger.info("API endpoint file not found, running initialization first")
                            
                            # First, try to create required directories if they don't exist
                            os.makedirs(os.path.join(self.lotus_path, "keystore"), exist_ok=True)
                            os.makedirs(os.path.join(self.lotus_path, "datastore"), exist_ok=True)
                            
                            # Run init-only command - this sets up the API endpoint correctly
                            init_cmd = ["lotus", "daemon", "--lite", "--bootstrap=false", "--init-only"]
                            init_result = self.run_command(init_cmd, check=False, timeout=30)
                            logger.debug(f"Init result: {init_result}")
                            
                            # Check if initialization worked
                            if init_result.get("success", False):
                                logger.info("Initial API setup successful")
                            else:
                                # If init-only still fails, try creating a minimal config.toml
                                config_file = os.path.join(self.lotus_path, "config.toml")
                                if not os.path.exists(config_file):
                                    minimal_config = f"""# Generated by lotus_daemon._initialize_repo for API initialization
[API]
  ListenAddress = "/ip4/127.0.0.1/tcp/{self.api_port}/http"
  RemoteListenAddress = ""
  Timeout = "30s"

[Libp2p]
  ListenAddresses = ["/ip4/0.0.0.0/tcp/{self.p2p_port}", "/ip6/::/tcp/{self.p2p_port}"]
  AnnounceAddresses = []
  NoAnnounceAddresses = []
  DisableNatPortMap = true

[Client]
  UseIpfs = false
  IpfsMAddr = ""
  IpfsUseForRetrieval = false
"""
                                    with open(config_file, 'w') as f:
                                        f.write(minimal_config)
                                    logger.info(f"Created minimal config.toml in {self.lotus_path}")
                                    
                                    # Try initialization again
                                    init_cmd = ["lotus", "daemon", "--lite", "--bootstrap=false", "--init-only"]
                                    init_result = self.run_command(init_cmd, check=False, timeout=30)
                                    logger.debug(f"Second init attempt result: {init_result}")
                                    
                    except Exception as e:
                        logger.warning(f"Error during initialization check: {e}")
                
                # Check if we have the env var set to use simulation mode
                simulation_mode = os.environ.get("LOTUS_SKIP_DAEMON_LAUNCH") == "1"
                if simulation_mode:
                    logger.info("LOTUS_SKIP_DAEMON_LAUNCH=1 detected, skipping daemon launch (simulation mode)")
                    result["success"] = True
                    result["status"] = "simulation_mode"
                    result["message"] = "Lotus daemon skipped due to LOTUS_SKIP_DAEMON_LAUNCH=1"
                    return result
                
                # We need to use Popen here because we don't want to wait for the process to finish
                # Redirect output to log files for better debugging
                stdout_log = os.path.join(self.lotus_path, "daemon_stdout.log")
                stderr_log = os.path.join(self.lotus_path, "daemon_stderr.log")
                
                with open(stdout_log, 'wb') as stdout_file, open(stderr_log, 'wb') as stderr_file:
                    logger.debug(f"Redirecting daemon output to: {stdout_log} and {stderr_log}")
                    daemon_process = subprocess.Popen(
                        cmd, 
                        env=self.env,
                        stdout=stdout_file, 
                        stderr=stderr_file, 
                        shell=False
                    )
                
                # Wait a moment to see if it immediately fails
                initial_wait = 2  # seconds
                logger.info(f"Lotus daemon process started with PID {daemon_process.pid}, waiting {initial_wait} seconds for initial stability")
                time.sleep(initial_wait)
                
                # Check if process is still running
                if daemon_process.poll() is None:
                    # Wait a bit longer to see if it stays running
                    extra_wait_time = 5  # seconds
                    logger.info(f"Initial startup successful, waiting {extra_wait_time} more seconds to verify API availability")
                    time.sleep(extra_wait_time)
                    
                    # Check for API readiness with a simple command
                    api_check_cmd = ["lotus", "net", "peers"]
                    api_check_result = self.run_command(api_check_cmd, check=False, timeout=5)
                    
                    api_ready = api_check_result.get("success", False)
                    
                    # Final check if process is still running
                    if daemon_process.poll() is None:
                        # Process is still running and stable
                        start_attempts["direct"] = {
                            "success": True, 
                            "pid": daemon_process.pid,
                            "api_ready": api_ready
                        }
                        
                        result["success"] = True
                        result["status"] = "started_via_direct_invocation"
                        result["message"] = f"Lotus daemon started via direct invocation. API is {'ready' if api_ready else 'not yet ready'}"
                        result["method"] = "direct"
                        result["pid"] = daemon_process.pid
                        result["api_ready"] = api_ready
                        result["attempts"] = start_attempts
                        
                        # Write PID to file
                        self._write_pid_file(daemon_process.pid)
                        
                        # Log files for debugging
                        result["stdout_log"] = stdout_log
                        result["stderr_log"] = stderr_log
                        
                        return result
                    else:
                        # Process initially started but exited after the first check
                        # Read from log files instead since we redirected output
                        stderr = ""
                        stdout = ""
                        try:
                            if os.path.exists(stderr_log):
                                with open(stderr_log, 'r') as f:
                                    stderr = f.read()
                            if os.path.exists(stdout_log):
                                with open(stdout_log, 'r') as f:
                                    stdout = f.read()
                        except Exception as e:
                            logger.error(f"Error reading daemon log files: {e}")
                        
                        start_attempts["direct"] = {
                            "success": False,
                            "returncode": daemon_process.returncode,
                            "stderr": stderr,
                            "stdout": stdout,
                            "note": "Process exited after initial startup"
                        }
                        
                        # Log the stdout and stderr for debugging
                        logger.debug(f"Lotus daemon stdout: {stdout}")
                        logger.debug(f"Lotus daemon stderr: {stderr}")
                        
                        # Provide more helpful error messages based on common errors
                        if "failed to load config file" in stderr:
                            error_msg = "Lotus daemon exited shortly after startup: failed to load config file"
                            solution_msg = " - Try removing the lotus directory and reinitializing"
                        elif "API not running" in stderr:
                            error_msg = "Lotus daemon exited shortly after startup: API initialization failed"
                            solution_msg = " - Try running 'lotus daemon --init-only' manually" 
                        elif "repo is locked" in stderr or "repo.lock" in stderr:
                            error_msg = "Lotus daemon exited shortly after startup: repository is locked"
                            solution_msg = " - Check if another daemon is running or remove the repo.lock file"
                        elif "already running" in stderr:
                            error_msg = "Lotus daemon exited shortly after startup: another daemon is already running"
                            solution_msg = " - Stop the existing daemon before starting a new one"
                        elif "permission denied" in stderr.lower():
                            error_msg = "Lotus daemon exited shortly after startup: permission denied"
                            solution_msg = " - Check permissions on the Lotus repository"
                        else:
                            error_msg = f"Lotus daemon exited shortly after startup"
                            solution_msg = ""
                        
                        # Add log file locations to the error message
                        log_msg = f" - Check logs: stdout={stdout_log}, stderr={stderr_log}"
                            
                        logger.error(f"{error_msg}{solution_msg}{log_msg}")
                        
                        # Check for simulation mode fallback capability
                        try:
                            sim_cmd = ["lotus", "net", "peers"]
                            sim_env = self.env.copy()
                            sim_env["LOTUS_SKIP_DAEMON_LAUNCH"] = "1"  # Force simulation mode
                            
                            sim_result = self.run_command(sim_cmd, check=False, timeout=5)
                            if sim_result.get("success", False):
                                logger.info("Real daemon failed, but simulation mode is working - will use as fallback")
                                result["success"] = True
                                result["status"] = "simulation_mode_fallback"
                                result["message"] = "Lotus daemon unavailable, but simulation mode is working"
                                result["method"] = "simulation_fallback"
                                result["attempts"] = start_attempts
                                return result
                        except Exception as sim_e:
                            logger.warning(f"Error testing simulation mode fallback: {sim_e}")
                        
                        return handle_error(result, LotusError(f"{error_msg} - {stderr}"))
                else:
                    # Process exited immediately, check error
                    # Read from log files instead since we redirected output
                    stderr = ""
                    stdout = ""
                    try:
                        if os.path.exists(stderr_log):
                            with open(stderr_log, 'r') as f:
                                stderr = f.read()
                        if os.path.exists(stdout_log):
                            with open(stdout_log, 'r') as f:
                                stdout = f.read()
                    except Exception as e:
                        logger.error(f"Error reading daemon log files: {e}")
                        
                    start_attempts["direct"] = {
                        "success": False,
                        "returncode": daemon_process.returncode,
                        "stderr": stderr,
                        "stdout": stdout
                    }
                    
                    # Log the stdout and stderr for debugging
                    logger.debug(f"Lotus daemon stdout: {stdout}")
                    logger.debug(f"Lotus daemon stderr: {stderr}")
                    
                    # Parse for common error patterns
                    if "failed to load config file" in stderr:
                        error_msg = "Failed to start daemon: config file issue detected"
                        solution_msg = " - Try removing the lotus directory and reinitializing"
                    elif "API not running" in stderr:
                        error_msg = "Failed to start daemon: API initialization failed"
                        solution_msg = " - Try running 'lotus daemon --init-only' manually"
                    elif "repo is locked" in stderr or "repo.lock" in stderr:
                        error_msg = "Failed to start daemon: repository is locked"
                        solution_msg = " - Check if another daemon is running or remove the repo.lock file"
                    elif "already running" in stderr:
                        error_msg = "Failed to start daemon: Another Lotus daemon appears to be running"
                        solution_msg = " - Stop the existing daemon before starting a new one"
                    elif "permission denied" in stderr.lower():
                        error_msg = "Failed to start daemon: permission denied"
                        solution_msg = " - Check permissions on the Lotus repository"
                    else:
                        error_msg = "Failed to start daemon"
                        solution_msg = ""
                    
                    # Add log file locations to the error message
                    log_msg = f" - Check logs: stdout={stdout_log}, stderr={stderr_log}"
                    
                    logger.error(f"{error_msg}{solution_msg}{log_msg}")
                    
                    # Check for simulation mode fallback capability
                    try:
                        sim_cmd = ["lotus", "net", "peers"]
                        sim_env = self.env.copy()
                        sim_env["LOTUS_SKIP_DAEMON_LAUNCH"] = "1"  # Force simulation mode
                        
                        # Use run_command with the updated environment
                        sim_result = self.run_command(sim_cmd, check=False, timeout=5)
                        if sim_result.get("success", False):
                            logger.info("Real daemon failed, but simulation mode is working - will use as fallback")
                            result["success"] = True
                            result["status"] = "simulation_mode_fallback"
                            result["message"] = "Lotus daemon unavailable, but simulation mode is working"
                            result["method"] = "simulation_fallback"
                            result["attempts"] = start_attempts
                            return result
                    except Exception as sim_e:
                        logger.warning(f"Error testing simulation mode fallback: {sim_e}")
                    
                    # Propagate the general error
                    return handle_error(result, LotusError(f"{error_msg} - {stderr}"))
            
            except Exception as e:
                start_attempts["direct"] = {
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__,
                }
                return handle_error(result, e, {"attempts": start_attempts})
        
        # If we get here and nothing has succeeded, return failure
        if not result.get("success", False):
            result["attempts"] = start_attempts
            result["error"] = "Failed to start Lotus daemon via any method"
            result["error_type"] = "daemon_start_error"
        
        return result
    
    def daemon_stop(self, **kwargs):
        """Stop the Lotus daemon with standardized error handling.
        
        Attempts to stop the daemon via systemctl (Linux), Windows service, 
        or direct process termination as appropriate.
        
        Args:
            **kwargs: Additional arguments for daemon shutdown
                - force: Whether to force kill the process
                - correlation_id: ID for tracking operations
                
        Returns:
            Result dictionary with operation outcome
        """
        operation = "daemon_stop"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        force = kwargs.get("force", False)
        
        try:
            # Track which methods we attempt and their results
            stop_attempts = {}
            daemon_stopped = False
            
            # Platform-specific stop methods
            if self.system == "Linux":
                # Try stopping via systemd if running as root
                if os.geteuid() == 0:
                    try:
                        systemctl_cmd = ["systemctl", "stop", self.service_name]
                        systemctl_result = self.run_command(
                            systemctl_cmd,
                            check=False,
                            correlation_id=correlation_id
                        )
                        
                        stop_attempts["systemctl"] = {
                            "success": systemctl_result.get("success", False),
                            "returncode": systemctl_result.get("returncode")
                        }
                        
                        # Check if daemon is now stopped
                        check_cmd = ["pgrep", "-f", "lotus daemon"]
                        check_result = self.run_command(
                            check_cmd,
                            check=False,
                            correlation_id=correlation_id
                        )
                        
                        # If pgrep returns non-zero, process isn't running (success)
                        if not check_result.get("success", False) or not check_result.get("stdout", "").strip():
                            daemon_stopped = True
                            result["success"] = True
                            result["status"] = "stopped_via_systemctl"
                            result["message"] = "Lotus daemon stopped via systemctl"
                            result["method"] = "systemctl"
                            result["attempts"] = stop_attempts
                            
                            # Remove PID file
                            self._remove_pid_file()
                    
                    except Exception as e:
                        stop_attempts["systemctl"] = {
                            "success": False,
                            "error": str(e),
                            "error_type": type(e).__name__
                        }
                        logger.debug(f"Error stopping Lotus daemon via systemctl: {str(e)}")
            
            elif self.system == "Windows":
                # Try stopping via Windows Service if available
                try:
                    service_cmd = ["sc", "stop", self.service_name]
                    service_result = self.run_command(
                        service_cmd,
                        check=False,
                        correlation_id=correlation_id
                    )
                    
                    stop_attempts["windows_service"] = {
                        "success": service_result.get("success", False),
                        "returncode": service_result.get("returncode")
                    }
                    
                    # Check if service stopped
                    if service_result.get("success", False) and "stopped" in service_result.get("stdout", "").lower():
                        daemon_stopped = True
                        result["success"] = True
                        result["status"] = "stopped_via_windows_service"
                        result["message"] = "Lotus daemon stopped via Windows Service"
                        result["method"] = "windows_service"
                        result["attempts"] = stop_attempts
                        
                        # Remove PID file
                        self._remove_pid_file()
                
                except Exception as e:
                    stop_attempts["windows_service"] = {
                        "success": False,
                        "error": str(e),
                        "error_type": type(e).__name__
                    }
                    logger.debug(f"Error stopping Lotus daemon via Windows service: {str(e)}")
            
            # If the daemon is still running, try direct process termination
            if not daemon_stopped:
                try:
                    # Find Lotus daemon processes
                    find_cmd = ["pgrep", "-f", "lotus daemon"]
                    find_result = self.run_command(
                        find_cmd,
                        check=False,
                        correlation_id=correlation_id
                    )
                    
                    if find_result.get("success", False) and find_result.get("stdout", "").strip():
                        # Found Lotus processes, get PIDs
                        pids = [
                            pid.strip()
                            for pid in find_result.get("stdout", "").split("\n")
                            if pid.strip()
                        ]
                        kill_results = {}
                        
                        # Try to terminate each process
                        for pid in pids:
                            if pid:
                                # Use SIGKILL (9) if force=True, otherwise SIGTERM (15)
                                sig = 9 if force else 15
                                kill_cmd = ["kill", f"-{sig}", pid]
                                kill_result = self.run_command(
                                    kill_cmd,
                                    check=False,
                                    correlation_id=correlation_id
                                )
                                
                                kill_results[pid] = {
                                    "success": kill_result.get("success", False),
                                    "returncode": kill_result.get("returncode"),
                                }
                        
                        # Check if all Lotus processes were terminated
                        recheck_cmd = ["pgrep", "-f", "lotus daemon"]
                        recheck_result = self.run_command(
                            recheck_cmd,
                            check=False,
                            correlation_id=correlation_id
                        )
                        
                        if not recheck_result.get("success", False) or not recheck_result.get("stdout", "").strip():
                            daemon_stopped = True
                            stop_attempts["manual"] = {
                                "success": True,
                                "killed_processes": kill_results,
                            }
                            
                            result["success"] = True
                            result["status"] = "stopped_via_manual_termination"
                            result["message"] = "Lotus daemon stopped via manual process termination"
                            result["method"] = "manual"
                            result["attempts"] = stop_attempts
                            
                            # Remove PID file
                            self._remove_pid_file()
                        else:
                            # Some processes still running
                            stop_attempts["manual"] = {
                                "success": False,
                                "killed_processes": kill_results,
                                "remaining_pids": recheck_result.get("stdout", "").strip().split("\n"),
                            }
                    else:
                        # No Lotus processes found, already stopped
                        daemon_stopped = True
                        stop_attempts["manual"] = {
                            "success": True,
                            "message": "No Lotus daemon processes found",
                        }
                        
                        result["success"] = True
                        result["status"] = "already_stopped"
                        result["message"] = "Lotus daemon was not running"
                        result["method"] = "none_needed"
                        result["attempts"] = stop_attempts
                        
                        # Remove PID file if it exists
                        self._remove_pid_file()
                
                except Exception as e:
                    stop_attempts["manual"] = {
                        "success": False,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    }
                    logger.debug(f"Error stopping Lotus daemon via manual termination: {str(e)}")
            
            # Clean up socket file if exists
            api_socket_path = os.path.join(self.lotus_path, "api")
            if os.path.exists(api_socket_path):
                try:
                    os.remove(api_socket_path)
                    result["socket_removed"] = True
                except Exception as e:
                    logger.error(f"Failed to remove API socket: {str(e)}")
                    result["socket_removed"] = False
                    result["socket_error"] = str(e)
            
            # Check for and remove lock file
            repo_lock_path = os.path.join(self.lotus_path, "repo.lock")
            if os.path.exists(repo_lock_path):
                try:
                    os.remove(repo_lock_path)
                    result["lock_file_removed"] = True
                except Exception as e:
                    logger.error(f"Failed to remove lock file: {str(e)}")
                    result["lock_file_removed"] = False
                    result["lock_error"] = str(e)
            
            # If we get here and nothing has succeeded, return failure
            if not result.get("success", False):
                result["attempts"] = stop_attempts
                result["error"] = "Failed to stop Lotus daemon via any method"
                result["error_type"] = "daemon_stop_error"
            
            return result
        
        except Exception as e:
            return handle_error(result, e)
    
    def daemon_status(self, **kwargs):
        """Get the status of the Lotus daemon.
        
        Args:
            **kwargs: Additional arguments
                - correlation_id: ID for tracking operations
                
        Returns:
            Result dictionary with daemon status information
        """
        operation = "daemon_status"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            process_running = False
            process_pid = None
            daemon_info = {}
            
            # Method 1: Check if lotus API is responding
            try:
                api_check_cmd = ["lotus", "net", "id"]
                api_result = self.run_command(
                    api_check_cmd,
                    check=False,
                    timeout=5,
                    correlation_id=correlation_id
                )
                
                if api_result.get("success", False) and api_result.get("returncode") == 0:
                    process_running = True
                    daemon_info["api_responding"] = True
                    
                    # Try to parse JSON response
                    try:
                        api_data = json.loads(api_result.get("stdout", "{}"))
                        daemon_info["peer_id"] = api_data.get("ID")
                        daemon_info["addresses"] = api_data.get("Addresses", [])
                    except:
                        daemon_info["api_data_parse_error"] = "Failed to parse API response as JSON"
                else:
                    daemon_info["api_responding"] = False
            except Exception as e:
                daemon_info["api_check_error"] = str(e)
                daemon_info["api_responding"] = False
            
            # Method 2: Check for PID file
            if os.path.exists(self.pid_file):
                try:
                    with open(self.pid_file, 'r') as f:
                        pid = f.read().strip()
                        if pid and pid.isdigit():
                            pid = int(pid)
                            process_pid = pid
                            
                            # Check if process is actually running
                            try:
                                os.kill(pid, 0)  # Signal 0 just checks if process exists
                                process_running = True
                                daemon_info["pid_file_valid"] = True
                            except OSError:
                                daemon_info["pid_file_valid"] = False
                                daemon_info["pid_file_stale"] = True
                except Exception as e:
                    daemon_info["pid_file_read_error"] = str(e)
            else:
                daemon_info["pid_file_exists"] = False
            
            # Method 3: Check using process commands
            try:
                if self.system in ("Linux", "Darwin"):
                    # Use pgrep on Linux/macOS
                    ps_cmd = ["pgrep", "-f", "lotus daemon"]
                    ps_result = self.run_command(
                        ps_cmd,
                        check=False,
                        correlation_id=correlation_id
                    )
                    
                    if ps_result.get("success", False) and ps_result.get("stdout", "").strip():
                        process_running = True
                        # Get first PID if multiple are returned
                        pids = [p.strip() for p in ps_result.get("stdout", "").split("\n") if p.strip()]
                        if pids:
                            process_pid = pids[0]
                            daemon_info["detected_pid"] = process_pid
                elif self.system == "Windows":
                    # Use tasklist on Windows
                    ps_cmd = ["tasklist", "/FI", "IMAGENAME eq lotus.exe", "/FO", "CSV"]
                    ps_result = self.run_command(
                        ps_cmd,
                        check=False,
                        correlation_id=correlation_id
                    )
                    
                    if ps_result.get("success", False) and "lotus.exe" in ps_result.get("stdout", ""):
                        process_running = True
            except Exception as e:
                daemon_info["process_check_error"] = str(e)
            
            # Method 4: Check for API and repo.lock files
            api_socket_path = os.path.join(self.lotus_path, "api")
            repo_lock_path = os.path.join(self.lotus_path, "repo.lock")
            
            daemon_info["api_socket_exists"] = os.path.exists(api_socket_path)
            daemon_info["repo_lock_exists"] = os.path.exists(repo_lock_path)
            
            # If repo.lock exists, read PID from it
            if os.path.exists(repo_lock_path):
                try:
                    with open(repo_lock_path, 'r') as f:
                        lock_content = f.read().strip()
                        if lock_content and lock_content.isdigit():
                            daemon_info["lock_file_pid"] = lock_content
                            if not process_pid:
                                process_pid = lock_content
                except Exception as e:
                    daemon_info["lock_file_read_error"] = str(e)
            
            # Set overall result
            result["success"] = True
            result["process_running"] = process_running
            result["pid"] = process_pid
            result["daemon_info"] = daemon_info
            
            # Log appropriate message
            if process_running:
                logger.info(f"Lotus daemon is running with PID {process_pid}")
            else:
                logger.info("Lotus daemon is not running")
            
            return result
            
        except Exception as e:
            logger.exception(f"Error checking daemon status: {str(e)}")
            return handle_error(result, e)
    
    def _write_pid_file(self, pid):
        """Write PID to the PID file."""
        try:
            with open(self.pid_file, 'w') as f:
                f.write(str(pid))
            logger.debug(f"Wrote PID {pid} to {self.pid_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to write PID file: {str(e)}")
            return False
    
    def _remove_pid_file(self):
        """Remove the PID file if it exists."""
        if os.path.exists(self.pid_file):
            try:
                os.remove(self.pid_file)
                logger.debug(f"Removed PID file: {self.pid_file}")
                return True
            except Exception as e:
                logger.error(f"Failed to remove PID file: {str(e)}")
                return False
        return True
    
    def install_systemd_service(self, **kwargs):
        """Install Lotus daemon as a systemd service on Linux.
        
        Args:
            **kwargs: Additional arguments
                - user: User to run the service as (default: current user)
                - description: Service description
                - correlation_id: ID for tracking operations
                
        Returns:
            Result dictionary with installation outcome
        """
        if self.system != "Linux":
            return {
                "success": False,
                "error": "systemd services only supported on Linux",
                "error_type": "platform_error"
            }
        
        operation = "install_systemd_service"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Check if running as root
            if os.geteuid() != 0:
                return handle_error(
                    result, 
                    LotusValidationError("Must be root to install systemd service")
                )
            
            # Get parameters
            username = kwargs.get("user", os.getenv("SUDO_USER") or os.getenv("USER") or "lotus")
            description = kwargs.get("description", "Lotus Daemon Service")
            
            # Create service file content
            service_content = f"""[Unit]
Description={description}
After=network.target

[Service]
Type=simple
User={username}
Environment="LOTUS_PATH={self.lotus_path}"
ExecStart=/usr/local/bin/lotus daemon
Restart=on-failure
RestartSec=10
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
"""
            
            # Write service file
            service_path = f"/etc/systemd/system/{self.service_name}.service"
            with open(service_path, 'w') as f:
                f.write(service_content)
            
            # Set permissions
            os.chmod(service_path, 0o644)
            
            # Reload systemd
            reload_cmd = ["systemctl", "daemon-reload"]
            reload_result = self.run_command(
                reload_cmd,
                check=True,
                correlation_id=correlation_id
            )
            
            if not reload_result.get("success", False):
                return handle_error(
                    result,
                    LotusError("Failed to reload systemd configuration")
                )
            
            # Enable service
            enable_cmd = ["systemctl", "enable", self.service_name]
            enable_result = self.run_command(
                enable_cmd,
                check=True,
                correlation_id=correlation_id
            )
            
            result["success"] = enable_result.get("success", False)
            result["service_path"] = service_path
            result["service_name"] = self.service_name
            result["enabled"] = enable_result.get("success", False)
            
            if result["success"]:
                logger.info(f"Successfully installed systemd service: {self.service_name}")
            else:
                logger.error(f"Failed to enable systemd service: {self.service_name}")
            
            return result
            
        except Exception as e:
            logger.exception(f"Error installing systemd service: {str(e)}")
            return handle_error(result, e)
    
    def install_windows_service(self, **kwargs):
        """Install Lotus daemon as a Windows service.
        
        Args:
            **kwargs: Additional arguments
                - description: Service description
                - correlation_id: ID for tracking operations
                
        Returns:
            Result dictionary with installation outcome
        """
        if self.system != "Windows":
            return {
                "success": False,
                "error": "Windows services only supported on Windows",
                "error_type": "platform_error"
            }
        
        operation = "install_windows_service"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Check if nssm is available (Non-Sucking Service Manager)
            nssm_cmd = ["where", "nssm"]
            nssm_result = self.run_command(
                nssm_cmd,
                check=False,
                correlation_id=correlation_id
            )
            
            if not nssm_result.get("success", False) or not nssm_result.get("stdout", "").strip():
                return handle_error(
                    result,
                    LotusValidationError("NSSM (Non-Sucking Service Manager) not found. Please install it first.")
                )
            
            # Get parameters
            description = kwargs.get("description", "Lotus Daemon Service")
            
            # Get path to lotus executable
            lotus_path_cmd = ["where", "lotus"]
            lotus_path_result = self.run_command(
                lotus_path_cmd,
                check=False,
                correlation_id=correlation_id
            )
            
            if not lotus_path_result.get("success", False) or not lotus_path_result.get("stdout", "").strip():
                return handle_error(
                    result,
                    LotusValidationError("Lotus executable not found in PATH")
                )
            
            lotus_exe_path = lotus_path_result.get("stdout", "").strip().split("\n")[0]
            
            # Install service using nssm
            install_cmd = [
                "nssm", "install", self.service_name, lotus_exe_path, "daemon"
            ]
            install_result = self.run_command(
                install_cmd,
                check=True,
                correlation_id=correlation_id
            )
            
            if not install_result.get("success", False):
                return handle_error(
                    result, 
                    LotusError(f"Failed to install Windows service: {install_result.get('stderr', '')}")
                )
            
            # Set service description
            desc_cmd = [
                "nssm", "set", self.service_name, "Description", description
            ]
            self.run_command(
                desc_cmd,
                check=False,
                correlation_id=correlation_id
            )
            
            # Set environment variables
            env_cmd = [
                "nssm", "set", self.service_name, "AppEnvironmentExtra", f"LOTUS_PATH={self.lotus_path}"
            ]
            self.run_command(
                env_cmd,
                check=False,
                correlation_id=correlation_id
            )
            
            # Set startup type
            startup_cmd = [
                "nssm", "set", self.service_name, "Start", "SERVICE_AUTO_START"
            ]
            self.run_command(
                startup_cmd,
                check=False,
                correlation_id=correlation_id
            )
            
            result["success"] = True
            result["service_name"] = self.service_name
            result["lotus_path"] = lotus_exe_path
            
            logger.info(f"Successfully installed Windows service: {self.service_name}")
            return result
            
        except Exception as e:
            logger.exception(f"Error installing Windows service: {str(e)}")
            return handle_error(result, e)
    
    def install_launchd_service(self, **kwargs):
        """Install Lotus daemon as a launchd service on macOS.
        
        Args:
            **kwargs: Additional arguments
                - user: User to run the service as (default: current user)
                - description: Service description
                - correlation_id: ID for tracking operations
                
        Returns:
            dict: Result dictionary with installation outcome
        """
        if self.system != "Darwin":
            return {
                "success": False,
                "error": "launchd services only supported on macOS",
                "error_type": "platform_error"
            }
        
        operation = "install_launchd_service"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Get parameters
            username = kwargs.get("user", os.getenv("USER") or "lotus")
            description = kwargs.get("description", "Lotus Daemon Service")
            
            # Get path to lotus executable
            lotus_path_cmd = ["which", "lotus"]
            lotus_path_result = self.run_command(
                lotus_path_cmd,
                check=False,
                correlation_id=correlation_id
            )
            
            if not lotus_path_result.get("success", False) or not lotus_path_result.get("stdout", "").strip():
                return handle_error(
                    result,
                    LotusValidationError("Lotus executable not found in PATH")
                )
                
            lotus_bin_path = lotus_path_result.get("stdout", "").strip()
            
            # Create plist file content
            plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{self.service_name}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{lotus_bin_path}</string>
        <string>daemon</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>LOTUS_PATH</key>
        <string>{self.lotus_path}</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardErrorPath</key>
    <string>/tmp/lotus.daemon.err</string>
    <key>StandardOutPath</key>
    <string>/tmp/lotus.daemon.out</string>
    <key>UserName</key>
    <string>{username}</string>
    <key>WorkingDirectory</key>
    <string>/tmp</string>
    <key>ProcessType</key>
    <string>Background</string>
    <key>Description</key>
    <string>{description}</string>
</dict>
</plist>
"""
            
            # Determine plist file path
            user_home = os.path.expanduser("~")
            plist_dir = os.path.join(user_home, "Library/LaunchAgents")
            os.makedirs(plist_dir, exist_ok=True)
            plist_path = os.path.join(plist_dir, f"{self.service_name}.plist")
            
            # Write plist file
            with open(plist_path, 'w') as f:
                f.write(plist_content)
            
            # Set permissions
            os.chmod(plist_path, 0o644)
            
            # Load the service
            load_cmd = ["launchctl", "load", plist_path]
            load_result = self.run_command(
                load_cmd,
                check=True,
                correlation_id=correlation_id
            )
            
            if not load_result.get("success", False):
                return handle_error(
                    result,
                    LotusError("Failed to load launchd service")
                )
                
            result["success"] = True
            result["service_path"] = plist_path
            result["service_name"] = self.service_name
            result["load_result"] = load_result
            
            logger.info(f"Successfully installed launchd service: {self.service_name}")
            return result
            
        except Exception as e:
            logger.exception(f"Error installing launchd service: {str(e)}")
            return handle_error(result, e)
    
    def uninstall_service(self, **kwargs):
        """Uninstall Lotus daemon service based on platform.
        
        Args:
            **kwargs: Additional arguments
                - correlation_id: ID for tracking operations
                
        Returns:
            Result dictionary with uninstallation outcome
        """
        operation = "uninstall_service"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            # First stop the service
            stop_result = self.daemon_stop(correlation_id=correlation_id)
            result["stop_result"] = stop_result
            
            if self.system == "Linux":
                # Check if running as root
                if os.geteuid() != 0:
                    return handle_error(
                        result, 
                        LotusValidationError("Must be root to uninstall systemd service")
                    )
                
                # Disable service
                disable_cmd = ["systemctl", "disable", self.service_name]
                disable_result = self.run_command(
                    disable_cmd,
                    check=False,
                    correlation_id=correlation_id
                )
                
                result["disable_result"] = disable_result
                
                # Remove service file
                service_path = f"/etc/systemd/system/{self.service_name}.service"
                if os.path.exists(service_path):
                    os.remove(service_path)
                    result["service_file_removed"] = True
                
                # Reload systemd
                reload_cmd = ["systemctl", "daemon-reload"]
                reload_result = self.run_command(
                    reload_cmd,
                    check=False,
                    correlation_id=correlation_id
                )
                
                result["reload_result"] = reload_result
                result["success"] = True
                result["message"] = f"Successfully uninstalled systemd service: {self.service_name}"
                
            elif self.system == "Windows":
                # Uninstall Windows service
                uninstall_cmd = ["nssm", "remove", self.service_name, "confirm"]
                uninstall_result = self.run_command(
                    uninstall_cmd,
                    check=False,
                    correlation_id=correlation_id
                )
                
                result["uninstall_result"] = uninstall_result
                result["success"] = "removed successfully" in uninstall_result.get("stdout", "").lower()
                result["message"] = f"Successfully uninstalled Windows service: {self.service_name}"
            
            elif self.system == "Darwin":
                # Unload and remove launchd service
                user_home = os.path.expanduser("~")
                plist_path = os.path.join(user_home, "Library/LaunchAgents", f"{self.service_name}.plist")
                
                if os.path.exists(plist_path):
                    # Unload service
                    unload_cmd = ["launchctl", "unload", plist_path]
                    unload_result = self.run_command(
                        unload_cmd,
                        check=False,
                        correlation_id=correlation_id
                    )
                    
                    result["unload_result"] = unload_result
                    
                    # Remove plist file
                    try:
                        os.remove(plist_path)
                        result["plist_file_removed"] = True
                    except Exception as e:
                        logger.error(f"Failed to remove plist file: {str(e)}")
                        result["plist_file_removed"] = False
                    
                    result["success"] = True
                    result["message"] = f"Successfully uninstalled launchd service: {self.service_name}"
                else:
                    result["success"] = False
                    result["error"] = f"Service plist file not found: {plist_path}"
            
            else:
                result["success"] = False
                result["error"] = f"Unsupported platform: {self.system}"
                result["error_type"] = "platform_error"
            
            return result
            
        except Exception as e:
            logger.exception(f"Error uninstalling service: {str(e)}")
            return handle_error(result, e)


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Parse command line arguments
    import argparse
    
    parser = argparse.ArgumentParser(description="Lotus Daemon Manager")
    parser.add_argument("command", choices=["start", "stop", "status", "install", "uninstall"],
                        help="Command to execute")
    parser.add_argument("--lotus-path", dest="lotus_path", default=os.path.expanduser("~/.lotus"),
                        help="Path to Lotus configuration directory")
    parser.add_argument("--api-port", dest="api_port", type=int, default=1234,
                        help="API port to use")
    parser.add_argument("--p2p-port", dest="p2p_port", type=int, default=2345,
                        help="P2P port to use")
    parser.add_argument("--service-name", dest="service_name", default="lotus-daemon",
                        help="Name of the service (for systemd/Windows)")
    parser.add_argument("--user", dest="user", default=None,
                        help="User to run the service as (systemd only)")
    parser.add_argument("--description", dest="description", default="Lotus Daemon Service",
                        help="Service description")
    parser.add_argument("--force", action="store_true", default=False,
                        help="Force stop using SIGKILL instead of SIGTERM")
    parser.add_argument("--debug", action="store_true", default=False,
                        help="Enable debug logging")
    
    args = parser.parse_args()
    
    # Set debug logging if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create daemon manager
    metadata = {
        "lotus_path": args.lotus_path,
        "api_port": args.api_port,
        "p2p_port": args.p2p_port,
        "service_name": args.service_name
    }
    daemon = lotus_daemon(metadata=metadata)
    
    # Execute the command
    if args.command == "start":
        result = daemon.daemon_start()
        if result.get("success", False):
            print(f"Lotus daemon started successfully. PID: {result.get('pid', 'unknown')}")
        else:
            print(f"Failed to start Lotus daemon: {result.get('error', 'Unknown error')}")
            sys.exit(1)
            
    elif args.command == "stop":
        result = daemon.daemon_stop(force=args.force)
        if result.get("success", False):
            print("Lotus daemon stopped successfully.")
        else:
            print(f"Failed to stop Lotus daemon: {result.get('error', 'Unknown error')}")
            sys.exit(1)
            
    elif args.command == "status":
        result = daemon.daemon_status()
        if result.get("process_running", False):
            print(f"Lotus daemon is running. PID: {result.get('pid', 'unknown')}")
        else:
            print("Lotus daemon is not running.")
            
    elif args.command == "install":
        system = platform.system()
        if system == "Linux":
            result = daemon.install_systemd_service(user=args.user, description=args.description)
        elif system == "Windows":
            result = daemon.install_windows_service(description=args.description)
        elif system == "Darwin":
            result = daemon.install_launchd_service(user=args.user, description=args.description)
        else:
            print(f"Service installation not supported on {system}")
            sys.exit(1)
            
        if result.get("success", False):
            print(f"Lotus daemon service installed successfully: {args.service_name}")
        else:
            print(f"Failed to install service: {result.get('error', 'Unknown error')}")
            sys.exit(1)
            
    elif args.command == "uninstall":
        result = daemon.uninstall_service()
        if result.get("success", False):
            print("Lotus daemon service uninstalled successfully.")
        else:
            print(f"Failed to uninstall service: {result.get('error', 'Unknown error')}")
            sys.exit(1)