#!/usr/bin/env python3
import json
import logging
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
import uuid
import json
import hashlib
import random
import base64
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin
from importlib import import_module

import requests

# Configure logger
logger = logging.getLogger(__name__)

# Check if Lotus is actually available by trying to run it
try:
    result = subprocess.run(["lotus", "--version"], capture_output=True, timeout=2)
    LOTUS_AVAILABLE = result.returncode == 0
except (subprocess.SubprocessError, FileNotFoundError, OSError):
    LOTUS_AVAILABLE = False

logger.info(f"Lotus binary available: {LOTUS_AVAILABLE}")

# Alias for backwards compatibility
LOTUS_KIT_AVAILABLE = True  # Always true since we now support simulation mode


class LotusValidationError(Exception):
    """Error when input validation fails."""

    pass


class LotusContentNotFoundError(Exception):
    """Content with specified CID not found."""

    pass


class LotusConnectionError(Exception):
    """Error when connecting to Lotus services."""

    pass


class LotusError(Exception):
    """Base class for all Lotus-related exceptions."""

    pass


class LotusTimeoutError(Exception):
    """Timeout when communicating with Lotus services."""

    pass


def create_result_dict(operation, correlation_id=None):
    """Create a standardized result dictionary."""
    return {
        "success": False,
        "operation": operation,
        "timestamp": time.time(),
        "correlation_id": correlation_id,
    }


def handle_error(result, error, message=None):
    """Handle errors in a standardized way."""
    result["success"] = False
    result["error"] = message or str(error)
    result["error_type"] = type(error).__name__
    return result


class lotus_kit:
    def __init__(self, resources=None, metadata=None):
        """Initialize lotus_kit with resources and metadata.
        
        Args:
            resources (dict, optional): Resources for the Lotus client.
            metadata (dict, optional): Metadata containing connection information.
        """
        # Store resources
        self.resources = resources or {}

        # Store metadata
        self.metadata = metadata or {}

        # Generate correlation ID for tracking operations
        self.correlation_id = str(uuid.uuid4())

        # Set up Lotus API connection parameters
        self.api_url = self.metadata.get("api_url", "http://localhost:1234/rpc/v0")
        self.token = self.metadata.get("token", "")
        
        # Set environment variables
        self.env = os.environ.copy()
        if "LOTUS_PATH" not in self.env and "lotus_path" in self.metadata:
            self.env["LOTUS_PATH"] = self.metadata["lotus_path"]
            
        # Initialize daemon manager (lazy loading)
        self._daemon = None
        
        # Initialize monitor (lazy loading)
        self._monitor = None
        
        # Auto-start daemon flag - default to True for automatic daemon management
        self.auto_start_daemon = self.metadata.get("auto_start_daemon", True)
        
        # Track daemon health status
        self._daemon_health_check_interval = self.metadata.get("daemon_health_check_interval", 60)  # seconds
        self._last_daemon_health_check = 0
        self._daemon_started_by_us = False
        
        # Check and install dependencies if needed
        install_deps = self.metadata.get("install_dependencies", True)
        if install_deps and not LOTUS_AVAILABLE:
            self._check_and_install_dependencies()
        
        # Setup simulation mode if Lotus binary is not available or explicitly requested
        self.simulation_mode = self.metadata.get("simulation_mode", not LOTUS_AVAILABLE)
        if self.simulation_mode:
            logger.info("Lotus kit running in simulation mode")
            # Initialize simulation cache for consistent responses
            self.sim_cache = {
                "wallets": {},
                "deals": {},
                "imports": {},
                "miners": {},
                "contents": {}
            }
            # Create a few simulated wallets for testing
            if not self.sim_cache["wallets"]:
                wallet_types = ["bls", "secp256k1"]
                for i in range(3):
                    wallet_type = wallet_types[i % len(wallet_types)]
                    address = f"f1{hashlib.sha256(f'wallet_{i}_{time.time()}'.encode()).hexdigest()[:10]}"
                    self.sim_cache["wallets"][address] = {
                        "type": wallet_type,
                        "balance": str(random.randint(1000000, 1000000000000)),
                        "created_at": time.time()
                    }
            # Create a few simulated miners for testing
            if not self.sim_cache["miners"]:
                for i in range(5):
                    miner_id = f"f0{random.randint(10000, 99999)}"
                    self.sim_cache["miners"][miner_id] = {
                        "power": str(random.randint(1, 1000)) + " TiB",
                        "sector_size": "32 GiB",
                        "sectors_active": random.randint(10, 1000),
                        "price_per_epoch": str(random.randint(1000, 10000)),
                        "peer_id": f"12D3KooW{hashlib.sha256(miner_id.encode()).hexdigest()[:16]}"
                    }
            
            # Set up simulated deals for testing
            if not self.sim_cache["deals"]:
                for i in range(10):
                    deal_id = i + 1
                    data_cid = f"bafyrei{hashlib.sha256(f'dealdata_{i}'.encode()).hexdigest()[:38]}"
                    miner_keys = list(self.sim_cache["miners"].keys())
                    miner = miner_keys[i % len(miner_keys)]
                    wallet_keys = list(self.sim_cache["wallets"].keys())
                    wallet = wallet_keys[i % len(wallet_keys)]
                    
                    # Select a random state from 3 to 7 (ProposalAccepted to Active)
                    state = random.randint(3, 7)
                    
                    self.sim_cache["deals"][deal_id] = {
                        "DealID": deal_id,
                        "Provider": miner,
                        "Client": wallet,
                        "State": state,
                        "PieceCID": {"/" : f"bafyrei{hashlib.sha256(f'piece_{i}'.encode()).hexdigest()[:38]}"},
                        "DataCID": {"/" : data_cid},
                        "Size": random.randint(1, 100) * 1024 * 1024 * 1024,  # 1-100 GiB
                        "PricePerEpoch": str(random.randint(1000, 10000)),
                        "Duration": random.randint(180, 518400),  # Duration in epochs
                        "StartEpoch": random.randint(100000, 200000),
                        "EndEpoch": random.randint(200000, 300000),
                        "SlashEpoch": -1,
                        "Verified": random.choice([True, False]),
                        "FastRetrieval": True
                    }
                    
                    # Also add to imports
                    self.sim_cache["imports"][data_cid] = {
                        "ImportID": uuid.uuid4(),
                        "CID": data_cid,
                        "Root": {"/" : data_cid},
                        "FilePath": f"/tmp/simulated_file_{i}.dat",
                        "Size": self.sim_cache["deals"][deal_id]["Size"],
                        "Status": "Complete",
                        "Created": time.time() - random.randint(3600, 86400),  # 1 hour to 1 day ago
                        "Deals": [deal_id]
                    }
                    
                    # Add to contents
                    self.sim_cache["contents"][data_cid] = {
                        "size": self.sim_cache["deals"][deal_id]["Size"],
                        "deals": [deal_id],
                        "local": True
                    }
        
        # If auto-start is enabled, ensure daemon is running
        if self.auto_start_daemon and not self.simulation_mode:
            # First check if daemon is already running
            try:
                daemon_status = self.daemon_status()
                if daemon_status.get("process_running", False):
                    logger.info(f"Found existing Lotus daemon running (PID: {daemon_status.get('pid')})")
                else:
                    # Start the daemon
                    logger.info("Attempting to start Lotus daemon...")
                    daemon_start_result = self.daemon_start()
                    if not daemon_start_result.get("success", False):
                        logger.warning(f"Failed to auto-start Lotus daemon: {daemon_start_result.get('error', 'Unknown error')}")
                        # If we have a specific error, provide more detailed troubleshooting guidance
                        if "lock" in daemon_start_result.get("error", "").lower():
                            logger.warning("Daemon failed to start due to lock issue. Try manually removing locks with `lotus daemon stop --force`")
                        elif "permission" in daemon_start_result.get("error", "").lower():
                            logger.warning("Daemon failed to start due to permission issues. Check ownership of Lotus directory.")
                    else:
                        self._daemon_started_by_us = True
                        logger.info(f"Lotus daemon started successfully during initialization (PID: {daemon_start_result.get('pid')})")
                        # Record when we started it
                        self._last_daemon_health_check = time.time()
                
                # Store initial daemon health status
                self._record_daemon_health(daemon_status if daemon_status.get("process_running", False) else daemon_start_result)
                
            except Exception as e:
                logger.error(f"Error during daemon auto-start check: {str(e)}")
                # Fall back to basic start attempt
                try:
                    daemon_start_result = self.daemon_start()
                    if daemon_start_result.get("success", False):
                        self._daemon_started_by_us = True
                        logger.info("Lotus daemon started successfully during initialization after error recovery")
                except Exception as start_error:
                    logger.error(f"Failed to start daemon during error recovery: {str(start_error)}")
        
    def __del__(self):
        """Clean up resources when object is garbage collected.
        
        This method ensures proper shutdown of the daemon if we started it
        to maintain a clean system state.
        """
        try:
            # Only attempt to stop the daemon if we started it
            if hasattr(self, '_daemon_started_by_us') and self._daemon_started_by_us:
                # Don't try to do this during interpreter shutdown
                if sys and logging:
                    logger.debug("Shutting down Lotus daemon during cleanup")
                    try:
                        # Stop the daemon gracefully
                        self.daemon_stop(force=False)
                    except Exception as e:
                        if logger:
                            logger.debug(f"Error during daemon shutdown in __del__: {e}")
                            
        except (TypeError, AttributeError, ImportError):
            # These can occur during interpreter shutdown
            pass
        
    def _record_daemon_health(self, status_dict):
        """Record daemon health status for monitoring.
        
        Args:
            status_dict: Status dictionary from daemon_status or daemon_start
        """
        # Store the timestamp of this check
        self._last_daemon_health_check = time.time()
        # We would store more detailed health metrics here if needed
    
    def _check_daemon_health(self):
        """Check daemon health and restart if necessary.
        
        Returns:
            bool: True if daemon is healthy, False otherwise
        """
        # Only check if we're in auto-start mode and not in simulation mode
        if not self.auto_start_daemon or self.simulation_mode:
            return True
            
        # Only check periodically to avoid excessive API calls
        current_time = time.time()
        time_since_last_check = current_time - self._last_daemon_health_check
        
        if time_since_last_check < self._daemon_health_check_interval:
            # Not time to check yet
            return True
            
        # Check daemon status
        try:
            daemon_status = self.daemon_status()
            self._record_daemon_health(daemon_status)
            
            # If not running and we previously started it, try to restart
            if not daemon_status.get("process_running", False) and self._daemon_started_by_us:
                logger.warning("Lotus daemon appears to have stopped unexpectedly, attempting to restart")
                daemon_start_result = self.daemon_start()
                if daemon_start_result.get("success", False):
                    logger.info("Successfully restarted Lotus daemon after unexpected stop")
                    return True
                else:
                    logger.error(f"Failed to restart Lotus daemon: {daemon_start_result.get('error', 'Unknown error')}")
                    return False
                    
            # Return health status
            return daemon_status.get("process_running", False)
            
        except Exception as e:
            logger.error(f"Error checking daemon health: {str(e)}")
            return False
            
    def _ensure_daemon_running(self):
        """Ensure the Lotus daemon is running before API operations.
        
        This method is called before making API requests to ensure
        the daemon is running and healthy. If auto_start_daemon is enabled
        and the daemon isn't running, it will attempt to start it.
        
        Returns:
            bool: True if the daemon is running or in simulation mode, False otherwise
        """
        # Skip check if we're in simulation mode
        if self.simulation_mode:
            return True
            
        # Check daemon health - this includes periodic restart if needed
        daemon_healthy = self._check_daemon_health()
        
        # If not healthy but auto-start is enabled, try to start it
        if not daemon_healthy and self.auto_start_daemon:
            # Try to start the daemon
            logger.info("Daemon not running, attempting to start automatically")
            start_result = self.daemon_start()
            if start_result.get("success", False):
                logger.info("Started Lotus daemon automatically before API operation")
                return True
            else:
                logger.warning(f"Failed to auto-start Lotus daemon: {start_result.get('error', 'Unknown error')}")
                
                # Check if we're in simulation mode fallback
                if start_result.get("status") == "simulation_mode_fallback":
                    logger.info("Using simulation mode as fallback")
                    self.simulation_mode = True
                    return True
                    
                return False
                
        return daemon_healthy
        
    def _with_daemon_check(self, operation):
        """Decorator-like function to run operations with daemon health checks.
        
        This helper method wraps API operations to ensure the daemon is running
        before attempting the operation. For operations that already implement
        simulation mode, it falls back to simulation if the daemon can't be started.
        
        Args:
            operation: Function name to create result dictionary
            
        Returns:
            dict: Result dictionary with appropriate error if daemon not available
        """
        result = create_result_dict(operation, self.correlation_id)
        
        # Skip check if we're in simulation mode - methods will handle appropriately
        if self.simulation_mode:
            return None  # No error, proceed with operation
            
        # Try to ensure daemon is running
        if not self._ensure_daemon_running():
            # Failed to start daemon - return error result
            result["success"] = False
            result["error"] = "Lotus daemon is not running and auto-start failed"
            result["error_type"] = "daemon_not_running"
            result["simulation_mode"] = self.simulation_mode  # Will be false here
            
            logger.error(f"Cannot execute {operation}: daemon not running and auto-start failed")
            return result
            
        # Daemon is running, operation can proceed
        return None
            
    def _check_and_install_dependencies(self):
        """Check if required dependencies are available and install if possible.
        
        This method ensures that required dependencies are available
        and attempts to install them if missing.
        
        Returns:
            bool: True if dependencies are available, False otherwise
        """
        global LOTUS_KIT_AVAILABLE, LOTUS_AVAILABLE
        
        # If already available, no need to install
        if LOTUS_AVAILABLE:
            return True
            
        try:
            # Try to import and use the install_lotus module
            from install_lotus import install_lotus as LotusInstaller
            
            # Create installer with auto_install_deps set to True
            installer_metadata = {
                "auto_install_deps": True,
                "force": False,  # Only install if not already installed
                "skip_params": True,  # Skip parameter download for faster setup,
                "bin_dir": os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "bin")
            }
            
            # If we have any relevant metadata in self.metadata, use it
            if hasattr(self, "metadata") and self.metadata:
                if "lotus_path" in self.metadata:
                    installer_metadata["lotus_path"] = self.metadata["lotus_path"]
                if "version" in self.metadata:
                    installer_metadata["version"] = self.metadata["version"]
                if "bin_dir" in self.metadata:
                    installer_metadata["bin_dir"] = self.metadata["bin_dir"]
                    
            # Create installer with resources and metadata
            try:
                # Debug log the metadata we're using
                logger.debug(f"Creating LotusInstaller with metadata: {installer_metadata}")
                
                # Create installer instance
                installer = LotusInstaller(resources=self.resources, metadata=installer_metadata)
                
                # Debug log the installer attributes
                logger.debug(f"LotusInstaller created, dir(installer): {dir(installer)}")
                
                # Install Lotus daemon
                logger.debug(f"Calling install_lotus_daemon()")
                install_result = installer.install_lotus_daemon()
                logger.debug(f"install_lotus_daemon() result: {install_result}")
            except Exception as e:
                logger.error(f"Detailed error creating/using LotusInstaller: {e}")
                if hasattr(installer, '__dict__'):
                    logger.debug(f"installer.__dict__: {installer.__dict__}")
                raise
            
            if install_result:
                # Update global availability flags
                try:
                    result = subprocess.run(["lotus", "--version"], capture_output=True, timeout=2)
                    LOTUS_AVAILABLE = result.returncode == 0
                except (subprocess.SubprocessError, FileNotFoundError, OSError):
                    LOTUS_AVAILABLE = False
                    
                LOTUS_KIT_AVAILABLE = True  # Always available due to simulation mode
                
                if LOTUS_AVAILABLE:
                    logger.info("Lotus dependencies installed successfully")
                    return True
                else:
                    logger.warning("Lotus dependencies installed but binary check failed")
                    return False
            else:
                logger.warning("Failed to install Lotus dependencies")
                return False
                
        except ImportError:
            logger.warning("Could not import install_lotus module")
            return False
        except Exception as e:
            logger.warning(f"Error installing Lotus dependencies: {e}")
            return False
        
    def check_connection(self) -> Dict[str, Any]:
        """Check connection to the Lotus API.
        
        Returns:
            dict: Result dictionary with success and version information
        """
        operation = "check_connection"
        result = create_result_dict(operation, self.correlation_id)
        
        # If in simulation mode, always return success
        if self.simulation_mode:
            result["success"] = True
            result["simulated"] = True
            result["result"] = "v1.23.0-simulation"
            result["version"] = "v1.23.0-simulation"
            return result
        
        try:
            # Create headers for request
            headers = {
                "Content-Type": "application/json",
            }
            
            # Add authorization token if available
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            
            # Prepare request data for Filecoin.Version RPC call
            request_data = {
                "jsonrpc": "2.0",
                "method": "Filecoin.Version",
                "params": [],
                "id": 1,
            }
            
            # Make the API request
            response = requests.post(
                self.api_url, 
                headers=headers,
                json=request_data,
                timeout=5  # Short timeout for quick response
            )
            
            # Check for successful response
            if response.status_code == 200:
                response_data = response.json()
                
                if "result" in response_data:
                    result["success"] = True
                    result["result"] = response_data["result"]
                    return result
                elif "error" in response_data:
                    result["error"] = f"API error: {response_data['error']['message']}"
                    result["error_type"] = "APIError"
                    return result
            
            # Handle unsuccessful response
            result["error"] = f"API request failed: {response.status_code}"
            result["error_type"] = "ConnectionError"
            
        except requests.exceptions.Timeout:
            result["error"] = "Connection timed out"
            result["error_type"] = "TimeoutError"
            
        except requests.exceptions.ConnectionError:
            result["error"] = "Failed to connect to Lotus API"
            result["error_type"] = "ConnectionError"
            
        except Exception as e:
            return handle_error(result, e)
            
        return result
        
    def list_wallets(self) -> Dict[str, Any]:
        """List all wallet addresses.
        
        Returns:
            dict: Result dictionary with wallet addresses
        """
        operation = "list_wallets"
        result = create_result_dict(operation, self.correlation_id)
        
        # If in simulation mode, return simulated wallets
        if self.simulation_mode:
            result["success"] = True
            result["simulated"] = True
            result["result"] = list(self.sim_cache["wallets"].keys())
            return result
        
        try:
            response = self._make_request("WalletList")
            
            if response.get("success", False):
                result["success"] = True
                result["result"] = response.get("result", [])
            else:
                result["error"] = response.get("error", "Failed to list wallets")
                result["error_type"] = response.get("error_type", "APIError")
                
        except Exception as e:
            return handle_error(result, e)
            
        return result
    
    def wallet_balance(self, address: str) -> Dict[str, Any]:
        """Get wallet balance.
        
        Args:
            address: The wallet address to check balance for
            
        Returns:
            dict: Result dictionary with wallet balance
        """
        operation = "wallet_balance"
        result = create_result_dict(operation, self.correlation_id)
        
        # Validate input
        if not address:
            result["error"] = "Wallet address is required"
            result["error_type"] = "ValidationError"
            return result
        
        # If in simulation mode, return simulated balance
        if self.simulation_mode:
            if address in self.sim_cache["wallets"]:
                result["success"] = True
                result["simulated"] = True
                result["result"] = self.sim_cache["wallets"][address]["balance"]
            else:
                # Create a new wallet on demand
                wallet_type = "bls"  # Default type
                self.sim_cache["wallets"][address] = {
                    "type": wallet_type,
                    "balance": str(random.randint(1000000, 1000000000000)),
                    "created_at": time.time()
                }
                result["success"] = True
                result["simulated"] = True
                result["result"] = self.sim_cache["wallets"][address]["balance"]
            return result
        
        try:
            response = self._make_request("WalletBalance", [address])
            
            if response.get("success", False):
                result["success"] = True
                result["result"] = response.get("result")
            else:
                result["error"] = response.get("error", "Failed to get wallet balance")
                result["error_type"] = response.get("error_type", "APIError")
                
        except Exception as e:
            return handle_error(result, e)
            
        return result
    
    def create_wallet(self, wallet_type: str = "bls") -> Dict[str, Any]:
        """Create a new wallet.
        
        Args:
            wallet_type: The type of wallet to create (bls or secp256k1)
            
        Returns:
            dict: Result dictionary with new wallet address
        """
        operation = "create_wallet"
        result = create_result_dict(operation, self.correlation_id)
        
        # Validate wallet_type
        valid_types = ["bls", "secp256k1"]
        if wallet_type not in valid_types:
            result["error"] = f"Invalid wallet type. Must be one of: {', '.join(valid_types)}"
            result["error_type"] = "ValidationError"
            return result
        
        # If in simulation mode, create a simulated wallet
        if self.simulation_mode:
            address = f"f1{hashlib.sha256(f'wallet_{wallet_type}_{time.time()}'.encode()).hexdigest()[:10]}"
            self.sim_cache["wallets"][address] = {
                "type": wallet_type,
                "balance": "0",
                "created_at": time.time()
            }
            result["success"] = True
            result["simulated"] = True
            result["result"] = address
            return result
        
        try:
            response = self._make_request("WalletNew", [wallet_type])
            
            if response.get("success", False):
                result["success"] = True
                result["result"] = response.get("result")
            else:
                result["error"] = response.get("error", "Failed to create wallet")
                result["error_type"] = response.get("error_type", "APIError")
                
        except Exception as e:
            return handle_error(result, e)
            
        return result
    
    @property
    def daemon(self):
        """Get the daemon manager for this Lotus instance.
        
        This property lazily loads the lotus_daemon module to avoid
        circular imports and allow the daemon manager to be instantiated
        only when needed.
        
        Returns:
            lotus_daemon: Instance of the Lotus daemon manager
        """
        if self._daemon is None:
            try:
                # Import the daemon module
                from .lotus_daemon import lotus_daemon
                
                # Create daemon instance with the same resources/metadata
                self._daemon = lotus_daemon(
                    resources=self.resources,
                    metadata=self.metadata
                )
                
                logger.debug("Initialized Lotus daemon manager")
            except ImportError as e:
                logger.error(f"Failed to import lotus_daemon module: {str(e)}")
                raise LotusError(f"Lotus daemon functionality not available: {str(e)}")
            except Exception as e:
                logger.error(f"Error initializing Lotus daemon manager: {str(e)}")
                raise LotusError(f"Failed to initialize Lotus daemon manager: {str(e)}")
                
        return self._daemon
        
    @property
    def monitor(self):
        """Get the monitor tool for the Lotus daemon.
        
        This property lazily loads the appropriate monitor module based on the platform.
        For macOS, it uses the lotus_macos_monitor module.
        
        Returns:
            LotusMonitor: Instance of the appropriate platform-specific monitor
        """
        if self._monitor is None:
            try:
                current_platform = platform.system()
                
                if current_platform == 'Darwin':  # macOS
                    # Dynamically import the macOS monitor
                    try:
                        import importlib.util
                        spec = importlib.util.spec_from_file_location(
                            "lotus_macos_monitor", 
                            os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                        "tools", "lotus_macos_monitor.py")
                        )
                        monitor_module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(monitor_module)
                        
                        # Create monitor instance with the same resources/metadata
                        self._monitor = monitor_module.LotusMonitor(
                            resources=self.resources,
                            metadata=self.metadata
                        )
                        
                        logger.debug("Initialized Lotus macOS monitor")
                    except Exception as e:
                        logger.error(f"Failed to import macOS monitor module: {str(e)}")
                        raise LotusError(f"Lotus macOS monitor functionality not available: {str(e)}")
                else:
                    # For other platforms, we don't yet have specific monitors
                    # In the future, this could handle Windows or Linux monitors
                    logger.info(f"No specialized monitor available for platform: {current_platform}")
                    return None
                    
            except Exception as e:
                logger.error(f"Error initializing Lotus monitor: {str(e)}")
                raise LotusError(f"Failed to initialize Lotus monitor: {str(e)}")
                
        return self._monitor

    # Daemon management methods
    def daemon_start(self, **kwargs):
        """Start the Lotus daemon.
        
        This method delegates to the lotus_daemon's daemon_start method,
        handling all platform-specific details of starting a Lotus daemon
        (systemd, Windows service, or direct process). It also updates
        internal tracking for automatic daemon management.
        
        Args:
            **kwargs: Additional arguments for daemon startup including:
                - bootstrap_peers: List of bootstrap peer multiaddresses
                - remove_stale_lock: Whether to remove stale lock files
                - api_port: Override default API port
                - p2p_port: Override default P2P port
                - correlation_id: ID for tracking operations
                - check_initialization: Whether to check and attempt repo initialization
                - force_restart: Force restart even if daemon is running
                
        Returns:
            dict: Result dictionary with operation outcome
        """
        operation = "lotus_daemon_start"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        force_restart = kwargs.get("force_restart", False)
        
        try:
            # Check if daemon is already running (unless force_restart is requested)
            if not force_restart:
                try:
                    daemon_status = self.daemon_status()
                    if daemon_status.get("process_running", False):
                        logger.info(f"Lotus daemon already running (PID: {daemon_status.get('pid')})")
                        result.update(daemon_status)
                        result["success"] = True
                        result["status"] = "already_running"
                        result["message"] = "Lotus daemon is already running"
                        return result
                except Exception as check_error:
                    # Just log the error and proceed with start attempt
                    logger.debug(f"Error checking if daemon is running: {str(check_error)}")
            
            # Use the daemon property to ensure it's initialized
            daemon_start_result = self.daemon.daemon_start(**kwargs)
            
            # Update our result with the daemon's result
            result.update(daemon_start_result)
            
            # Update internal tracking if start was successful
            if result.get("success", False):
                self._daemon_started_by_us = True
                self._record_daemon_health(result)
                logger.info(f"Lotus daemon started successfully: {result.get('status', 'running')}")
            else:
                logger.error(f"Failed to start Lotus daemon: {result.get('error', 'Unknown error')}")
                
                # Check if we can operate in simulation mode as a fallback
                if "simulation_mode_fallback" in result.get("status", ""):
                    logger.info("Successfully switched to simulation mode as fallback")
                    # Update simulation mode flag since it will handle subsequent operations
                    self.simulation_mode = True
            
            return result
            
        except Exception as e:
            logger.exception(f"Error starting Lotus daemon: {str(e)}")
            return handle_error(result, e)
            
    def daemon_stop(self, **kwargs):
        """Stop the Lotus daemon.
        
        This method delegates to the lotus_daemon's daemon_stop method,
        handling all platform-specific details of stopping a Lotus daemon
        (systemd, Windows service, or direct process termination).
        
        Args:
            **kwargs: Additional arguments for daemon shutdown including:
                - force: Whether to force kill the process
                - correlation_id: ID for tracking operations
                - clean_environment: Whether to clean environment variables
                
        Returns:
            dict: Result dictionary with operation outcome
        """
        operation = "lotus_daemon_stop"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        clean_environment = kwargs.get("clean_environment", True)
        
        try:
            # First check if daemon is running to avoid unnecessary work
            daemon_status = self.daemon_status()
            if not daemon_status.get("process_running", False):
                logger.info("Lotus daemon is not running, no need to stop")
                result["success"] = True
                result["status"] = "not_running"
                result["message"] = "Lotus daemon is not running"
                return result
            
            # Use the daemon property to ensure it's initialized
            daemon_stop_result = self.daemon.daemon_stop(**kwargs)
            
            # Update our result with the daemon's result
            result.update(daemon_stop_result)
            
            # Update internal tracking if stop was successful
            if result.get("success", False):
                self._daemon_started_by_us = False
                logger.info("Lotus daemon stopped successfully")
                
                # Optionally clean environment variables
                if clean_environment:
                    if "LOTUS_SKIP_DAEMON_LAUNCH" in os.environ:
                        del os.environ["LOTUS_SKIP_DAEMON_LAUNCH"]
                    
            else:
                logger.error(f"Failed to stop Lotus daemon: {result.get('error', 'Unknown error')}")
                
                # If this is a force request and we still failed, try a more aggressive approach
                if kwargs.get("force", False) and not result.get("success", False):
                    logger.warning("Force stop failed, attempting SIGKILL as last resort")
                    # Try with direct SIGKILL approach - modify kwargs in-place to avoid large code duplication
                    kwargs["force"] = "SIGKILL"  # Specific keyword to trigger SIGKILL in daemon implementation
                    last_resort_result = self.daemon.daemon_stop(**kwargs)
                    if last_resort_result.get("success", False):
                        logger.info("Lotus daemon stopped successfully with SIGKILL")
                        result.update(last_resort_result)
                        self._daemon_started_by_us = False
                
            return result
            
        except Exception as e:
            logger.exception(f"Error stopping Lotus daemon: {str(e)}")
            return handle_error(result, e)
            
    def daemon_status(self, **kwargs):
        """Get the status of the Lotus daemon.
        
        This method delegates to the lotus_daemon's daemon_status method,
        checking if the Lotus daemon is running through multiple detection methods.
        
        Args:
            **kwargs: Additional arguments including correlation_id for tracing
                
        Returns:
            dict: Result dictionary with daemon status information
        """
        operation = "lotus_daemon_status"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Use the daemon property to ensure it's initialized
            daemon_status_result = self.daemon.daemon_status(**kwargs)
            
            # Record health check
            self._record_daemon_health(daemon_status_result)
            
            # Update our result with the daemon's result
            result.update(daemon_status_result)
            
            # Log the result
            if result.get("process_running", False):
                logger.debug(f"Lotus daemon is running with PID {result.get('pid', 'unknown')}")
            else:
                logger.debug("Lotus daemon is not running")
                
            return result
            
        except Exception as e:
            logger.exception(f"Error checking Lotus daemon status: {str(e)}")
            return handle_error(result, e)
            
    def install_service(self, **kwargs):
        """Install Lotus daemon as a system service.
        
        This method delegates to the appropriate platform-specific installation method
        in the lotus_daemon module (systemd service on Linux, Windows service, etc.)
        
        Args:
            **kwargs: Additional arguments for service installation including:
                - user: User to run service as (Linux systemd only)
                - description: Service description
                - correlation_id: ID for tracking operations
                
        Returns:
            dict: Result dictionary with installation outcome
        """
        operation = "lotus_install_service"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Get the current system platform
            system = platform.system()
            
            # Call the platform-specific installation method
            if system == "Linux":
                install_result = self.daemon.install_systemd_service(**kwargs)
            elif system == "Windows":
                install_result = self.daemon.install_windows_service(**kwargs)
            else:
                return handle_error(
                    result,
                    LotusError(f"Service installation not supported on {system}")
                )
            
            # Update our result with the installation result
            result.update(install_result)
            
            # Log the result
            if result.get("success", False):
                logger.info(f"Lotus daemon service installed successfully")
            else:
                logger.error(f"Failed to install Lotus daemon service: {result.get('error', 'Unknown error')}")
                
            return result
            
        except Exception as e:
            logger.exception(f"Error installing Lotus daemon service: {str(e)}")
            return handle_error(result, e)
            
    def uninstall_service(self, **kwargs):
        """Uninstall Lotus daemon system service.
        
        This method delegates to the lotus_daemon's uninstall_service method,
        handling all platform-specific details of uninstalling a system service.
        
        Args:
            **kwargs: Additional arguments including correlation_id for tracing
                
        Returns:
            dict: Result dictionary with uninstallation outcome
        """
        operation = "lotus_uninstall_service"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Use the daemon property to ensure it's initialized
            uninstall_result = self.daemon.uninstall_service(**kwargs)
            
            # Update our result with the daemon's result
            result.update(uninstall_result)
            
            # Log the result
            if result.get("success", False):
                logger.info("Lotus daemon service uninstalled successfully")
            else:
                logger.error(f"Failed to uninstall Lotus daemon service: {result.get('error', 'Unknown error')}")
                
            return result
            
        except Exception as e:
            logger.exception(f"Error uninstalling Lotus daemon service: {str(e)}")
            return handle_error(result, e)
            
    def _ensure_daemon_running(self, correlation_id=None):
        """Ensure the Lotus daemon is running, starting it if necessary.
        
        This method checks if the Lotus daemon is running and attempts to
        start it if it's not running and auto_start_daemon is enabled.
        
        Args:
            correlation_id: ID for tracking operations
                
        Returns:
            dict: Result dictionary with daemon status and startup information
        """
        result = create_result_dict("ensure_lotus_daemon_running", correlation_id)
        
        try:
            # Check current daemon status
            daemon_status = self.daemon_status(correlation_id=correlation_id)
            
            # Check if daemon is running
            is_running = daemon_status.get("process_running", False)
            result["was_running"] = is_running
            
            if is_running:
                result["success"] = True
                result["message"] = "Lotus daemon already running"
                return result
            
            # Daemon is not running, check if we should auto-start it
            if not self.auto_start_daemon:
                result["success"] = False
                result["error"] = "Lotus daemon is not running and auto_start_daemon is disabled"
                return result
            
            # Start the daemon
            logger.info("Lotus daemon not running, attempting to start it automatically")
            start_result = self.daemon_start(correlation_id=correlation_id)
            
            if not start_result.get("success", False):
                result["success"] = False
                result["error"] = "Failed to start Lotus daemon"
                result["start_result"] = start_result
                return result
            
            # Daemon started successfully
            result["success"] = True
            result["message"] = "Lotus daemon started automatically"
            result["start_result"] = start_result
            return result
            
        except Exception as e:
            logger.exception(f"Error ensuring Lotus daemon is running: {str(e)}")
            return handle_error(result, e)
    
    def _make_request(self, method, params=None, timeout=60, correlation_id=None):
        """Make a request to the Lotus API.
        
        Args:
            method (str): The API method to call.
            params (list, optional): Parameters for the API call.
            timeout (int, optional): Request timeout in seconds.
            correlation_id (str, optional): Correlation ID for tracking requests.
            
        Returns:
            dict: The result dictionary with the API response or error information.
        """
        result = create_result_dict(method, correlation_id or self.correlation_id)
        
        try:
            headers = {
                "Content-Type": "application/json",
            }
            
            # Add authorization token if available
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            
            # Prepare request data
            request_data = {
                "jsonrpc": "2.0",
                "method": f"Filecoin.{method}",
                "params": params or [],
                "id": 1,
            }
            
            # Make the API request
            response = requests.post(
                self.api_url, 
                headers=headers,
                json=request_data,
                timeout=timeout
            )
            
            # Check for HTTP errors
            response.raise_for_status()
            
            # Parse response
            response_data = response.json()
            
            # Check for JSON-RPC errors
            if "error" in response_data:
                error_msg = response_data["error"].get("message", "Unknown error")
                error_code = response_data["error"].get("code", -1)
                return handle_error(result, LotusError(f"Error {error_code}: {error_msg}"))
            
            # Return successful result
            result["success"] = True
            result["result"] = response_data.get("result")
            return result
            
        except requests.exceptions.Timeout:
            return handle_error(result, LotusTimeoutError(f"Request timed out after {timeout} seconds"))
        
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Failed to connect to Lotus API: {str(e)}"
            
            # Check if auto-start daemon is enabled
            if self.auto_start_daemon:
                logger.info("Connection failed, attempting to start Lotus daemon")
                daemon_result = self._ensure_daemon_running(correlation_id)
                
                if daemon_result.get("success", False):
                    logger.info("Daemon started successfully, retrying request")
                    # Retry the request now that the daemon should be running
                    try:
                        # Make the API request again
                        response = requests.post(
                            self.api_url, 
                            headers=headers,
                            json=request_data,
                            timeout=timeout
                        )
                        
                        # Check for HTTP errors
                        response.raise_for_status()
                        
                        # Parse response
                        response_data = response.json()
                        
                        # Check for JSON-RPC errors
                        if "error" in response_data:
                            error_msg = response_data["error"].get("message", "Unknown error")
                            error_code = response_data["error"].get("code", -1)
                            return handle_error(result, LotusError(f"Error {error_code}: {error_msg}"))
                        
                        # Return successful result
                        result["success"] = True
                        result["result"] = response_data.get("result")
                        result["daemon_restarted"] = True
                        return result
                        
                    except Exception as retry_e:
                        # Retry also failed
                        logger.error(f"Retry failed after starting daemon: {str(retry_e)}")
                        result["daemon_restarted"] = True
                        result["retry_error"] = str(retry_e)
                        return handle_error(result, LotusConnectionError(f"{error_msg} (retry also failed)"))
                else:
                    # Couldn't start daemon
                    result["daemon_start_attempted"] = True
                    result["daemon_start_failed"] = True
                    return handle_error(result, LotusConnectionError(f"{error_msg} (daemon start failed)"))
            
            # No auto-start or other error, just return the connection error
            return handle_error(result, LotusConnectionError(error_msg))
        
        except requests.exceptions.HTTPError as e:
            return handle_error(result, LotusError(f"HTTP error: {str(e)}"))
        
        except Exception as e:
            logger.exception(f"Error in {method}: {str(e)}")
            return handle_error(result, e)

    def check_connection(self, **kwargs):
        """Check connection to the Lotus API.
        
        Returns:
            dict: Result dictionary with connection status.
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        return self._make_request("Version", correlation_id=correlation_id)

    # Chain methods
    def get_chain_head(self, **kwargs):
        """Get the current chain head.
        
        Returns:
            dict: Result dictionary with chain head information.
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        return self._make_request("ChainHead", correlation_id=correlation_id)
    
    def get_block(self, cid, **kwargs):
        """Get a block by CID.
        
        Args:
            cid (str): The CID of the block to retrieve.
            
        Returns:
            dict: Result dictionary with block information.
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        return self._make_request("ChainGetBlock", params=[{"/" : cid}], correlation_id=correlation_id)
    
    def get_message(self, cid, **kwargs):
        """Get a message by CID.
        
        Args:
            cid (str): The CID of the message to retrieve.
            
        Returns:
            dict: Result dictionary with message information.
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        return self._make_request("ChainGetMessage", params=[{"/" : cid}], correlation_id=correlation_id)

    # Wallet methods
    def list_wallets(self, **kwargs):
        """List all wallet addresses.
        
        Returns:
            dict: Result dictionary with wallet addresses.
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        return self._make_request("WalletList", correlation_id=correlation_id)
    
    def wallet_balance(self, address, **kwargs):
        """Get wallet balance.
        
        Args:
            address (str): The wallet address to check balance for.
            
        Returns:
            dict: Result dictionary with wallet balance.
        """
        operation = "wallet_balance"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        # If in simulation mode, return simulated wallet balance
        if self.simulation_mode:
            try:
                # Validate input
                if not address:
                    return handle_error(result, ValueError("Wallet address is required"))
                
                # Generate a deterministic balance based on the address
                # The balance is based on the hash of the address, but will be consistent
                # for the same address across calls
                address_hash = hashlib.sha256(address.encode()).hexdigest()
                
                # Convert first 10 characters of hash to integer and use as base balance
                # Scale to a reasonable FIL amount (between 1-100 FIL)
                base_balance = int(address_hash[:10], 16) % 10000 / 100
                
                # Format as a filecoin balance string (attoFIL)
                balance = str(int(base_balance * 1e18))
                
                result["success"] = True
                result["simulated"] = True
                result["result"] = balance
                return result
                
            except Exception as e:
                return handle_error(result, e, f"Error in simulated wallet_balance: {str(e)}")
        
        return self._make_request("WalletBalance", params=[address], correlation_id=correlation_id)
    
    def create_wallet(self, wallet_type="bls", **kwargs):
        """Create a new wallet.
        
        Args:
            wallet_type (str, optional): The type of wallet to create (bls or secp256k1).
            
        Returns:
            dict: Result dictionary with new wallet address.
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        return self._make_request("WalletNew", params=[wallet_type], correlation_id=correlation_id)

    # Storage methods
    def client_import(self, file_path, **kwargs):
        """Import a file into the Lotus client.
        
        This method imports a file into the Lotus client and ensures
        the daemon is running before attempting the operation.
        
        Args:
            file_path (str): Path to the file to import.
            
        Returns:
            dict: Result dictionary with import information.
        """
        operation = "client_import"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Check if file exists
            if not os.path.isfile(file_path):
                return handle_error(result, LotusValidationError(f"File not found: {file_path}"))
            
            # Ensure daemon is running before proceeding
            daemon_check_result = self._with_daemon_check(operation)
            if daemon_check_result:
                # Daemon check failed, return the error result
                return daemon_check_result
            
            # If in simulation mode, simulate file import
            if self.simulation_mode:
                try:
                    # Get file size and information
                    file_stat = os.stat(file_path)
                    file_size = file_stat.st_size
                    file_name = os.path.basename(file_path)
                    is_car = file_path.endswith(".car")
                    
                    # Generate a deterministic CID based on file path and size
                    # Create a unique hash based on file path and modification time
                    file_hash = hashlib.sha256(f"{file_path}_{file_stat.st_mtime}".encode()).hexdigest()
                    
                    # Format as a CID (simplified for simulation)
                    cid = f"bafyrei{file_hash[:38]}"
                    
                    # Create import record
                    import_id = uuid.uuid4()
                    timestamp = time.time()
                    
                    # Initialize imports in simulation cache if it doesn't exist
                    if "imports" not in self.sim_cache:
                        self.sim_cache["imports"] = {}
                        
                    # Store the import information in simulation cache
                    self.sim_cache["imports"][cid] = {
                        "ImportID": import_id,
                        "CID": {"/" : cid},
                        "Root": {"/" : cid},
                        "FilePath": file_path,
                        "Size": file_size,
                        "IsCAR": is_car,
                        "Timestamp": timestamp,
                        "Created": timestamp,
                        "Deals": [],
                        "Status": "complete"
                    }
                    
                    # Return success result
                    result["success"] = True
                    result["simulated"] = True
                    result["result"] = {
                        "Root": {"/" : cid},
                        "ImportID": str(import_id),
                        "Path": file_path
                    }
                    return result
                    
                except Exception as e:
                    logger.exception(f"Error in simulated client_import: {str(e)}")
                    return handle_error(result, e, f"Error in simulated client_import: {str(e)}")
            
            # Create import parameters
            params = [
                {
                    "Path": file_path,
                    "IsCAR": file_path.endswith(".car"),
                }
            ]
            
            # Make the API request
            return self._make_request("ClientImport", params=params, correlation_id=correlation_id)
            
        except Exception as e:
            logger.exception(f"Error in client_import: {str(e)}")
            return handle_error(result, e)
    
    def client_list_imports(self, **kwargs):
        """List all imported files.
        
        Returns:
            dict: Result dictionary with list of imports.
        """
        operation = "client_list_imports"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        # If in simulation mode, return simulated imports
        if self.simulation_mode:
            try:
                # Get all imports from simulation cache
                imports_list = []
                for cid, import_data in self.sim_cache["imports"].items():
                    # Create a copy to avoid modifying the cache
                    import_entry = dict(import_data)
                    # Add CID if not already present
                    if "CID" not in import_entry:
                        import_entry["CID"] = cid
                    
                    # Convert UUID objects to strings for JSON serialization
                    if "ImportID" in import_entry and isinstance(import_entry["ImportID"], uuid.UUID):
                        import_entry["ImportID"] = str(import_entry["ImportID"])
                        
                    # Ensure all values are JSON serializable
                    for k, v in list(import_entry.items()):
                        if isinstance(v, uuid.UUID):
                            import_entry[k] = str(v)
                            
                    imports_list.append(import_entry)
                    
                # Sort imports by creation time (newest first)
                imports_list.sort(key=lambda x: x.get("Created", 0), reverse=True)
                
                result["success"] = True
                result["simulated"] = True
                result["result"] = imports_list
                return result
                
            except Exception as e:
                return handle_error(result, e, f"Error in simulated list_imports: {str(e)}")
        
        # Real API call for non-simulation mode
        return self._make_request("ClientListImports", correlation_id=correlation_id)
    
    def client_find_data(self, data_cid, **kwargs):
        """Find where data is stored.
        
        Args:
            data_cid (str): The CID of the data to find.
            
        Returns:
            dict: Result dictionary with data location information.
        """
        operation = "client_find_data"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        # If in simulation mode, return simulated data location
        if self.simulation_mode:
            try:
                # Check if the data CID exists in our simulation cache
                if data_cid in self.sim_cache["contents"] or data_cid in self.sim_cache["imports"]:
                    # Get deal IDs associated with this content
                    deals = []
                    if data_cid in self.sim_cache["contents"] and "deals" in self.sim_cache["contents"][data_cid]:
                        deals = self.sim_cache["contents"][data_cid]["deals"]
                    elif data_cid in self.sim_cache["imports"] and "Deals" in self.sim_cache["imports"][data_cid]:
                        deals = self.sim_cache["imports"][data_cid]["Deals"]
                    
                    # Build simulated response with providers from deals
                    providers = []
                    for deal_id in deals:
                        if deal_id in self.sim_cache["deals"]:
                            deal = self.sim_cache["deals"][deal_id]
                            provider = deal.get("Provider")
                            if provider and provider not in [p.get("Provider") for p in providers]:
                                providers.append({
                                    "Provider": provider,
                                    "PieceCID": deal.get("PieceCID", {"/" : ""}),
                                    "DealID": deal_id,
                                    "State": deal.get("State", 0),
                                    "FastRetrieval": deal.get("FastRetrieval", True)
                                })
                    
                    # Add local node if content is available locally
                    if ((data_cid in self.sim_cache["contents"] and self.sim_cache["contents"][data_cid].get("local", False)) or
                        (data_cid in self.sim_cache["imports"])):
                        # Add local node as provider
                        providers.append({
                            "Provider": "local",
                            "PieceCID": {"/" : f"bafyrei{hashlib.sha256(f'local_{data_cid}'.encode()).hexdigest()[:38]}"},
                            "DealID": 0,  # 0 indicates local availability without a deal
                            "State": 7,  # Active state
                            "FastRetrieval": True
                        })
                    
                    result["success"] = True
                    result["simulated"] = True
                    result["result"] = providers
                    return result
                else:
                    # CID not found in simulation cache
                    return handle_error(
                        result,
                        LotusError(f"Data CID {data_cid} not found"),
                        f"Simulated data with CID {data_cid} not found in cache"
                    )
            except Exception as e:
                logger.exception(f"Error in simulated client_find_data: {str(e)}")
                return handle_error(result, e, f"Error in simulated client_find_data: {str(e)}")
                
        # Actual API call for non-simulation mode
        return self._make_request("ClientFindData", params=[{"/" : data_cid}], correlation_id=correlation_id)

    def client_deal_info(self, deal_id, **kwargs):
        """Get information about a specific deal.
        
        Args:
            deal_id (int): ID of the deal to get information about.
            **kwargs: Additional parameters:
                - correlation_id (str): ID for tracking operations
            
        Returns:
            dict: Result dictionary with deal information.
        """
        operation = "client_deal_info"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        # If in simulation mode, return simulated deal info
        if self.simulation_mode:
            try:
                # Check if the deal exists in the simulation cache
                if deal_id in self.sim_cache["deals"]:
                    result["success"] = True
                    result["simulated"] = True
                    result["result"] = self.sim_cache["deals"][deal_id]
                    return result
                else:
                    # If deal doesn't exist, return error
                    return handle_error(
                        result, 
                        LotusError(f"Deal {deal_id} not found"), 
                        f"Simulated deal with ID {deal_id} not found"
                    )
            
            except Exception as e:
                return handle_error(result, e, f"Error in simulated client_deal_info: {str(e)}")
        
        # Actual API call
        return self._make_request("ClientGetDealInfo", params=[deal_id], correlation_id=correlation_id)
    
    def client_list_deals(self, **kwargs):
        """List all deals made by the client.
        
        Args:
            **kwargs: Additional parameters:
                - filter_states (list): Optional list of deal states to filter by
                - correlation_id (str): ID for tracking operations
        
        Returns:
            dict: Result dictionary with list of deals.
        """
        operation = "client_list_deals"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)

        # If in simulation mode, return simulated deals
        if self.simulation_mode:
            try:
                filtered_deals = []
                filter_states = kwargs.get("filter_states", None)
                
                # Apply filters if specified
                for deal_id, deal in self.sim_cache["deals"].items():
                    if filter_states is not None and deal["State"] not in filter_states:
                        continue
                    filtered_deals.append(deal)
                
                result["success"] = True
                result["simulated"] = True
                result["result"] = filtered_deals
                return result
            
            except Exception as e:
                return handle_error(result, e, f"Error in simulated client_list_deals: {str(e)}")
        
        # Actual API call
        return self._make_request("ClientListDeals", correlation_id=correlation_id)
    
    def client_start_deal(self, data_cid, miner, price, duration, **kwargs):
        """Start a storage deal with a miner.
        
        Args:
            data_cid (str): The CID of the data to store.
            miner (str): The miner ID to store with.
            price (str): The price per epoch in attoFIL.
            duration (int): The duration of the deal in epochs.
            **kwargs: Additional parameters:
                - wallet (str): The wallet to use for the deal
                - verified (bool): Whether the deal should be verified
                - fast_retrieval (bool): Whether to enable fast retrieval
                - correlation_id (str): ID for tracking operations
            
        Returns:
            dict: Result dictionary with deal information.
        """
        operation = "client_start_deal"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        # If in simulation mode, create a simulated deal
        if self.simulation_mode:
            try:
                # Check if the data CID exists in the simulation cache
                if data_cid not in self.sim_cache["contents"] and data_cid not in self.sim_cache["imports"]:
                    return handle_error(
                        result,
                        LotusError(f"Data CID {data_cid} not found"),
                        f"Simulated data with CID {data_cid} not found. Import the data first."
                    )
                
                # Check if the miner exists in simulation cache
                if miner not in self.sim_cache["miners"]:
                    # Add miner if it doesn't exist
                    self.sim_cache["miners"][miner] = {
                        "Address": miner,
                        "Power": random.randint(1, 100) * 1024 * 1024 * 1024 * 1024,  # 1-100 TiB
                        "Available": True
                    }
                
                # Get wallet to use
                wallet = kwargs.get("wallet", "")
                if not wallet and self.sim_cache["wallets"]:
                    # Use first wallet if none provided
                    wallet = list(self.sim_cache["wallets"].keys())[0]
                
                # Generate a new deal ID
                deal_id = max(self.sim_cache["deals"].keys() or [0]) + 1
                
                # Get content size
                size = 0
                if data_cid in self.sim_cache["contents"]:
                    size = self.sim_cache["contents"][data_cid].get("size", 0)
                elif data_cid in self.sim_cache["imports"]:
                    size = self.sim_cache["imports"][data_cid].get("Size", 0)
                
                # Create the simulated deal
                start_epoch = random.randint(100000, 200000)
                self.sim_cache["deals"][deal_id] = {
                    "DealID": deal_id,
                    "Provider": miner,
                    "Client": wallet,
                    "State": 3,  # ProposalAccepted initial state
                    "PieceCID": {"/" : f"bafyrei{hashlib.sha256(f'piece_{deal_id}'.encode()).hexdigest()[:38]}"},
                    "DataCID": {"/" : data_cid},
                    "Size": size or random.randint(1, 100) * 1024 * 1024 * 1024,
                    "PricePerEpoch": price,
                    "Duration": duration,
                    "StartEpoch": start_epoch,
                    "EndEpoch": start_epoch + duration,
                    "SlashEpoch": -1,
                    "Verified": kwargs.get("verified", False),
                    "FastRetrieval": kwargs.get("fast_retrieval", True)
                }
                
                # Update content entry to include the deal
                if data_cid in self.sim_cache["contents"]:
                    if "deals" not in self.sim_cache["contents"][data_cid]:
                        self.sim_cache["contents"][data_cid]["deals"] = []
                    self.sim_cache["contents"][data_cid]["deals"].append(deal_id)
                
                # Update import entry to include the deal
                if data_cid in self.sim_cache["imports"]:
                    if "Deals" not in self.sim_cache["imports"][data_cid]:
                        self.sim_cache["imports"][data_cid]["Deals"] = []
                    self.sim_cache["imports"][data_cid]["Deals"].append(deal_id)
                
                # Return success with the new deal ID
                result["success"] = True
                result["simulated"] = True
                result["result"] = {
                    "/" : str(deal_id)  # Match expected API response format
                }
                return result
                
            except Exception as e:
                logger.exception(f"Error in simulated client_start_deal: {str(e)}")
                return handle_error(result, e, f"Error in simulated client_start_deal: {str(e)}")
        
        # Non-simulation mode logic
        try:
            # Create deal parameters
            params = [{
                "Data": {
                    "TransferType": "graphsync",
                    "Root": {"/" : data_cid},
                },
                "Wallet": kwargs.get("wallet", ""),
                "Miner": miner,
                "EpochPrice": price,
                "MinBlocksDuration": duration,
                "VerifiedDeal": kwargs.get("verified", False),
                "FastRetrieval": kwargs.get("fast_retrieval", True),
            }]
            
            # Make the API request
            return self._make_request("ClientStartDeal", params=params, correlation_id=correlation_id)
            
        except Exception as e:
            logger.exception(f"Error in client_start_deal: {str(e)}")
            return handle_error(result, e)
    
    def client_retrieve(self, data_cid, out_file, **kwargs):
        """Retrieve data from the Filecoin network.
        
        Args:
            data_cid (str): The CID of the data to retrieve.
            out_file (str): Path where the retrieved data should be saved.
            **kwargs: Additional options including:
                - is_car (bool): Whether to retrieve as a CAR file
                - timeout (int): Custom timeout in seconds
                - correlation_id (str): ID for tracing this operation
            
        Returns:
            dict: Result dictionary with retrieval information.
        """
        operation = "client_retrieve"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        # If in simulation mode, simulate data retrieval
        if self.simulation_mode:
            try:
                # Check if the data CID exists in our simulation cache
                if data_cid in self.sim_cache["contents"] or data_cid in self.sim_cache["imports"]:
                    # Create directory if it doesn't exist
                    os.makedirs(os.path.dirname(os.path.abspath(out_file)), exist_ok=True)
                    
                    # Determine content size
                    size = 0
                    if data_cid in self.sim_cache["contents"]:
                        size = self.sim_cache["contents"][data_cid].get("size", 1024)
                    elif data_cid in self.sim_cache["imports"]:
                        # Check if we can access the original file
                        orig_path = self.sim_cache["imports"][data_cid].get("FilePath")
                        if orig_path and os.path.exists(orig_path):
                            # Copy the original file
                            try:
                                import shutil
                                shutil.copy2(orig_path, out_file)
                                size = os.path.getsize(out_file)
                                logger.info(f"Successfully copied original file from {orig_path} to {out_file}")
                            except Exception as e:
                                logger.warning(f"Failed to copy original file {orig_path}: {e}")
                                # Fall back to generating content
                                size = self.sim_cache["imports"][data_cid].get("Size", 1024)
                        else:
                            size = self.sim_cache["imports"][data_cid].get("Size", 1024)
                    
                    # If we didn't copy from original or the copy failed (file is empty), generate simulated content
                    if not os.path.exists(out_file) or os.path.getsize(out_file) == 0:
                        # Generate deterministic content based on CID
                        content = f"Simulated Filecoin content for CID: {data_cid}\n".encode()
                        # Pad to approximate original size
                        size = max(size, 1024)  # Ensure minimum size of 1KB
                        if size > len(content):
                            # Use hash of CID to generate deterministic padding
                            seed = int(hashlib.sha256(data_cid.encode()).hexdigest()[:8], 16)
                            random.seed(seed)
                            padding_char = bytes([random.randint(32, 126)])  # ASCII printable chars
                            padding = padding_char * (size - len(content))
                            content += padding
                        
                        # Write to output file
                        with open(out_file, 'wb') as f:
                            f.write(content)
                            logger.info(f"Generated simulated content for {data_cid} to {out_file}, size: {len(content)} bytes")
                    
                    # Return success result
                    result["success"] = True
                    result["simulated"] = True
                    result["cid"] = data_cid
                    result["size"] = os.path.getsize(out_file) if os.path.exists(out_file) else 0
                    result["file_path"] = out_file
                    return result
                else:
                    # CID not found in simulation cache
                    return handle_error(
                        result,
                        LotusError(f"Data CID {data_cid} not found"),
                        f"Simulated data with CID {data_cid} not found in cache"
                    )
            except Exception as e:
                logger.exception(f"Error in simulated client_retrieve: {str(e)}")
                return handle_error(result, e, f"Error in simulated client_retrieve: {str(e)}")
        
        # Real implementation for non-simulation mode
        try:
            # Create retrieval parameters
            params = [
                {"/" : data_cid},
                {
                    "Path": out_file,
                    "IsCAR": kwargs.get("is_car", False),
                }
            ]
            
            # Make the API request
            return self._make_request("ClientRetrieve", 
                                    params=params, 
                                    timeout=kwargs.get("timeout", 60),
                                    correlation_id=correlation_id)
            
        except Exception as e:
            logger.exception(f"Error in client_retrieve: {str(e)}")
            return handle_error(result, e)
            
    def batch_retrieve(self, cid_file_map, **kwargs):
        """Retrieve multiple CIDs in batch, with optional concurrency.
        
        Args:
            cid_file_map (dict): Mapping of CIDs to output file paths
            **kwargs: Additional options including:
                - concurrent (bool): Whether to use concurrent retrieval (default True)
                - max_workers (int): Max number of concurrent workers (default 3)
                - timeout (int): Timeout per retrieval in seconds
                - correlation_id (str): ID for tracing
                
        Returns:
            dict: Result dictionary with retrieval information for all CIDs
        """
        operation = "batch_retrieve"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        # Parse options
        concurrent = kwargs.get("concurrent", True)
        max_workers = kwargs.get("max_workers", 3)
        timeout = kwargs.get("timeout", 60)
        
        # Track results
        results = {}
        successful = 0
        failed = 0
        
        try:
            if not cid_file_map:
                result["error"] = "No CIDs provided for retrieval"
                return result
                
            if concurrent:
                # Use concurrent execution with thread pool
                try:
                    from concurrent.futures import ThreadPoolExecutor
                except ImportError:
                    logger.warning("ThreadPoolExecutor not available, falling back to sequential retrieval")
                    concurrent = False
                    
            if concurrent:
                # Define worker function for each retrieval
                def retrieve_worker(cid, outfile):
                    worker_result = self.client_retrieve(
                        cid, outfile,
                        timeout=timeout,
                        correlation_id=f"{correlation_id}_{cid}"
                    )
                    return cid, worker_result
                    
                # Execute retrievals concurrently
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    # Submit all retrieval tasks
                    future_to_cid = {
                        executor.submit(retrieve_worker, cid, outfile): cid
                        for cid, outfile in cid_file_map.items()
                    }
                    
                    # Process results as they complete
                    for future in future_to_cid:
                        try:
                            cid, retrieval_result = future.result()
                            results[cid] = retrieval_result
                            
                            if retrieval_result.get("success", False):
                                successful += 1
                            else:
                                failed += 1
                                
                        except Exception as exc:
                            cid = future_to_cid[future]
                            logger.error(f"Retrieval for {cid} generated an exception: {exc}")
                            results[cid] = {
                                "success": False,
                                "error": str(exc),
                                "error_type": type(exc).__name__
                            }
                            failed += 1
            else:
                # Sequential retrieval
                for cid, outfile in cid_file_map.items():
                    retrieval_result = self.client_retrieve(
                        cid, outfile,
                        timeout=timeout,
                        correlation_id=f"{correlation_id}_{cid}"
                    )
                    
                    results[cid] = retrieval_result
                    
                    if retrieval_result.get("success", False):
                        successful += 1
                    else:
                        failed += 1
            
            # Compile overall result
            result["success"] = failed == 0  # Overall success if no failures
            result["total"] = len(cid_file_map)
            result["successful"] = successful
            result["failed"] = failed
            result["retrieval_results"] = results
            
            return result
            
        except Exception as e:
            logger.exception(f"Error in batch retrieval: {str(e)}")
            return handle_error(result, e)

    # Market methods
    def market_list_storage_deals(self, **kwargs):
        """List all storage deals in the market.
        
        Returns:
            dict: Result dictionary with list of storage deals.
        """
        operation = "market_list_storage_deals"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        # If in simulation mode, return simulated storage deals
        if self.simulation_mode:
            try:
                storage_deals = []
                
                # Convert client deals to market storage deals format
                for deal_id, deal in self.sim_cache["deals"].items():
                    # Create a market storage deal from the client deal
                    # with additional fields that would be in the market response
                    storage_deal = {
                        "Proposal": {
                            "PieceCID": deal.get("PieceCID", {"/":" "}),
                            "PieceSize": deal.get("Size", 0),
                            "VerifiedDeal": deal.get("Verified", False),
                            "Client": deal.get("Client", ""),
                            "Provider": deal.get("Provider", ""),
                            "Label": deal.get("Label", ""),
                            "StartEpoch": deal.get("StartEpoch", 0),
                            "EndEpoch": deal.get("EndEpoch", 0),
                            "StoragePricePerEpoch": deal.get("PricePerEpoch", "0"),
                            "ProviderCollateral": "0",
                            "ClientCollateral": "0",
                        },
                        "State": {
                            "SectorStartEpoch": deal.get("StartEpoch", 0),
                            "LastUpdatedEpoch": int(time.time() / 30),  # Approximate current epoch
                            "SlashEpoch": deal.get("SlashEpoch", -1),
                            "VerifiedClaim": 0
                        },
                        "DealID": deal_id,
                        "SignedProposalCid": {"/": f"bafyreisimulated{deal_id}"},
                        "Offset": deal_id * 1024 * 1024 * 1024,  # 1 GiB per deal for simulation
                        "Length": deal.get("Size", 0)
                    }
                    storage_deals.append(storage_deal)
                
                result["success"] = True
                result["simulated"] = True
                result["result"] = storage_deals
                return result
                
            except Exception as e:
                return handle_error(result, e, f"Error in simulated market_list_storage_deals: {str(e)}")
        
        # Actual API call
        return self._make_request("MarketListStorageDeals", correlation_id=correlation_id)
    
    def market_list_retrieval_deals(self, **kwargs):
        """List all retrieval deals in the market.
        
        Returns:
            dict: Result dictionary with list of retrieval deals.
        """
        operation = "market_list_retrieval_deals"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        # If in simulation mode, return simulated retrieval deals
        if self.simulation_mode:
            try:
                retrieval_deals = []
                
                # Check if retrievals exists in simulation cache
                if "retrievals" not in self.sim_cache:
                    self.sim_cache["retrievals"] = {}
                    
                # Convert retrieval records to market retrieval deals
                for cid, retrieval in self.sim_cache["retrievals"].items():
                    # Create a retrieval deal record from each retrieval
                    dealer_id = str(uuid.uuid4())
                    
                    # Get deal info if available
                    deal_info = None
                    for deal_id, deal in self.sim_cache["deals"].items():
                        if deal.get("DataCID", {}).get("/") == cid:
                            deal_info = deal
                            break
                    
                    # Create retrieval deal
                    retrieval_deal = {
                        "DealID": dealer_id,
                        "PayloadCID": {"/": cid},
                        "PieceCID": deal_info.get("PieceCID", {"/":" "}) if deal_info else {"/":" "},
                        "Status": 3,  # Completed
                        "Client": retrieval.get("Client", f"f1random{random.randint(10000, 99999)}"),
                        "Provider": retrieval.get("Provider", deal_info.get("Provider", f"f0{random.randint(10000, 99999)}")),
                        "TotalSent": retrieval.get("Size", 1024),
                        "FundsReceived": str(int(retrieval.get("Size", 1024) / 1024 * 10)),  # 10 attoFIL per KB
                        "Message": "Retrieval successful",
                        "Transferred": retrieval.get("Size", 1024),
                        "TransferChannelID": {
                            "Initiator": retrieval.get("Client", f"f1random{random.randint(10000, 99999)}"), 
                            "Responder": retrieval.get("Provider", deal_info.get("Provider", f"f0{random.randint(10000, 99999)}")),
                            "ID": random.randint(10000, 99999)
                        }
                    }
                    retrieval_deals.append(retrieval_deal)
                
                result["success"] = True
                result["simulated"] = True
                result["result"] = retrieval_deals
                return result
                
            except Exception as e:
                return handle_error(result, e, f"Error in simulated market_list_retrieval_deals: {str(e)}")
        
        # Actual API call
        return self._make_request("MarketListRetrievalDeals", correlation_id=correlation_id)
    
    def market_get_deal_updates(self, **kwargs):
        """Get updates about storage deals.
        
        Returns:
            dict: Result dictionary with deal updates.
        """
        operation = "market_get_deal_updates"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        # If in simulation mode, return simulated deal updates
        if self.simulation_mode:
            try:
                deal_updates = []
                
                # Create fake updates for a subset of existing deals
                deals_to_update = []
                for deal_id, deal in self.sim_cache["deals"].items():
                    # Only update about 20% of deals to simulate real-world behavior
                    if random.random() < 0.2:
                        deals_to_update.append((deal_id, deal))
                        
                # Create updates
                for deal_id, deal in deals_to_update:
                    # Randomly select a possible deal state transition
                    current_state = deal.get("State", 0)
                    possible_states = []
                    
                    # Logic for possible state transitions
                    if current_state < 7:  # Not yet complete
                        possible_states.append(current_state + 1)  # Progress to next state
                    if current_state == 7:  # Active
                        possible_states.append(7)  # Stay active
                    if current_state >= 3 and random.random() < 0.05:  # Small chance of failure
                        possible_states.append(10)  # Error state
                    
                    # If no transitions possible, skip this deal
                    if not possible_states:
                        continue
                    
                    # Select a new state
                    new_state = random.choice(possible_states)
                    
                    # Create update record
                    update = {
                        "DealID": deal_id,
                        "State": new_state,
                        "Message": self._get_deal_state_name(new_state),
                        "Proposal": {
                            "PieceCID": deal.get("PieceCID", {"/":" "}),
                            "Client": deal.get("Client", ""),
                            "Provider": deal.get("Provider", ""),
                            "StartEpoch": deal.get("StartEpoch", 0),
                            "EndEpoch": deal.get("EndEpoch", 0)
                        }
                    }
                    
                    # Update the deal in the cache to match
                    self.sim_cache["deals"][deal_id]["State"] = new_state
                    
                    deal_updates.append(update)
                
                result["success"] = True
                result["simulated"] = True
                result["result"] = deal_updates
                return result
                
            except Exception as e:
                return handle_error(result, e, f"Error in simulated market_get_deal_updates: {str(e)}")
        
        # Actual API call
        return self._make_request("MarketGetDealUpdates", correlation_id=correlation_id)
        
    # Payment Channel API methods
    def _parse_fil_amount(self, amount_string):
        """Parse FIL amount from string to attoFIL for API calls.
        
        Args:
            amount_string (str or float or int): String or number with FIL amount (e.g. "1.5", "0.01")
            
        Returns:
            str: attoFIL amount as string
        """
        # Handle different formats: direct FIL amount or with unit
        if isinstance(amount_string, (int, float)):
            fil_float = float(amount_string)
        else:
            amount_string = amount_string.strip().lower()
            if amount_string.endswith(" fil") or amount_string.endswith("fil"):
                amount_string = amount_string.replace("fil", "").strip()
            fil_float = float(amount_string)
        
        # Convert to attoFIL (1 FIL = 10^18 attoFIL)
        attofil = int(fil_float * 10**18)
        return str(attofil)
    
    def paych_fund(self, from_address, to_address, amount, **kwargs):
        """Fund a new or existing payment channel.
        
        Creates a new payment channel if one doesn't exist between from_address and to_address.
        
        Args:
            from_address (str): Sender address
            to_address (str): Recipient address
            amount (str): Amount to add to the channel in FIL
            
        Returns:
            dict: Result dictionary with channel info and operation status
        """
        operation = "paych_fund"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Convert string amount to attoFIL value
            amount_attoFIL = self._parse_fil_amount(amount)
            
            # Call Lotus API
            return self._make_request("PaychFund", params=[from_address, to_address, amount_attoFIL], 
                                     correlation_id=correlation_id)
            
        except Exception as e:
            logger.exception(f"Error funding payment channel: {str(e)}")
            return handle_error(result, e)
    
    def paych_list(self, **kwargs):
        """List all locally tracked payment channels.
        
        Returns:
            dict: Result dictionary with list of channel addresses
        """
        operation = "paych_list"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        # If in simulation mode, return simulated payment channels
        if self.simulation_mode:
            try:
                # Initialize channels list if it doesn't exist in the simulation cache
                if "channels" not in self.sim_cache:
                    self.sim_cache["channels"] = {}
                    
                    # Create a few simulated payment channels for testing
                    # with deterministic addresses based on wallet addresses
                    wallets = []
                    
                    # Get wallets from list_wallets if available
                    wallet_result = self.list_wallets()
                    if wallet_result.get("success", False) and wallet_result.get("result"):
                        wallets = wallet_result.get("result", [])
                    
                    # If no wallets were found, create some simulated ones
                    if not wallets:
                        wallets = [
                            f"t3{hashlib.sha256(f'wallet_{i}'.encode()).hexdigest()[:40]}" 
                            for i in range(3)
                        ]
                    
                    # Create simulated channels between wallets
                    for i in range(min(len(wallets), 2)):
                        for j in range(i+1, min(len(wallets), 3)):
                            from_addr = wallets[i]
                            to_addr = wallets[j]
                            
                            # Create deterministic channel address
                            channel_hash = hashlib.sha256(f"{from_addr}_{to_addr}".encode()).hexdigest()
                            channel_addr = f"t064{channel_hash[:5]}"
                            
                            # Store channel information in simulation cache
                            self.sim_cache["channels"][channel_addr] = {
                                "From": from_addr,
                                "To": to_addr,
                                "Direction": i % 2,  # 0=outbound, 1=inbound
                                "CreateMsg": f"bafy2bzace{channel_hash[:40]}",
                                "Settled": False,
                                "Amount": str(int(int(channel_hash[:8], 16) % 1000) * 1e15)  # Random amount 0-1000 FIL
                            }
                
                # Return channel addresses
                channel_addresses = list(self.sim_cache["channels"].keys())
                
                result["success"] = True
                result["simulated"] = True
                result["result"] = channel_addresses
                return result
                
            except Exception as e:
                return handle_error(result, e, f"Error in simulated paych_list: {str(e)}")
        
        return self._make_request("PaychList", correlation_id=correlation_id)
        
    def paych_status(self, ch_addr, **kwargs):
        """Get the status of a payment channel.
        
        Args:
            ch_addr (str): Payment channel address
            
        Returns:
            dict: Result dictionary with channel status
        """
        operation = "paych_status"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        # If in simulation mode, return simulated payment channel status
        if self.simulation_mode:
            try:
                # Validate input
                if not ch_addr:
                    return handle_error(result, ValueError("Channel address is required"))
                
                # Initialize channels if not already initialized
                if "channels" not in self.sim_cache:
                    # Call paych_list to initialize the channels simulation cache
                    self.paych_list()
                
                # Check if the channel exists in our simulation cache
                if ch_addr in self.sim_cache["channels"]:
                    channel_info = self.sim_cache["channels"][ch_addr]
                    
                    # Create simulated channel status
                    channel_status = {
                        "Channel": ch_addr,
                        "From": channel_info.get("From", ""),
                        "To": channel_info.get("To", ""),
                        "ConfirmedAmt": channel_info.get("Amount", "0"),
                        "PendingAmt": "0",
                        "NonceHighest": 0,
                        "Vouchers": [],
                        "Lanes": [
                            {
                                "ID": 0,
                                "NextNonce": 0,
                                "AmountRedeemed": "0"
                            }
                        ]
                    }
                    
                    result["success"] = True
                    result["simulated"] = True
                    result["result"] = channel_status
                    return result
                else:
                    # Channel not found
                    return handle_error(
                        result, 
                        ValueError(f"Channel {ch_addr} not found"), 
                        f"Simulated channel {ch_addr} not found"
                    )
                
            except Exception as e:
                return handle_error(result, e, f"Error in simulated paych_status: {str(e)}")
        
        return self._make_request("PaychAvailableFunds", params=[ch_addr], 
                                 correlation_id=correlation_id)
                                 
    def paych_voucher_create(self, ch_addr, amount, lane=0, **kwargs):
        """Create a signed payment channel voucher.
        
        Args:
            ch_addr (str): Payment channel address
            amount (str): Voucher amount in FIL
            lane (int, optional): Payment lane number
            
        Returns:
            dict: Result dictionary with voucher information
        """
        operation = "paych_voucher_create"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Convert amount to attoFIL
            amount_attoFIL = self._parse_fil_amount(amount)
            
            # If in simulation mode, simulate voucher creation
            if self.simulation_mode:
                try:
                    # Validate inputs
                    if not ch_addr:
                        return handle_error(result, ValueError("Payment channel address is required"))
                    if not amount_attoFIL:
                        return handle_error(result, ValueError("Voucher amount is required"))
                    
                    # Create deterministic voucher for consistent testing
                    # Generate a deterministic voucher ID based on channel address, amount, and lane
                    import hashlib
                    import time
                    
                    voucher_id = hashlib.sha256(f"{ch_addr}_{amount_attoFIL}_{lane}".encode()).hexdigest()
                    
                    # Create a simulated voucher and signature
                    timestamp = time.time()
                    nonce = int(timestamp * 1000) % 1000000  # Simple nonce generation
                    
                    # Create voucher structure - follows Filecoin PaymentVoucher format
                    simulated_voucher = {
                        "ChannelAddr": ch_addr,
                        "TimeLockMin": 0,
                        "TimeLockMax": 0,
                        "SecretPreimage": "",
                        "Extra": None,
                        "Lane": lane,
                        "Nonce": nonce,
                        "Amount": amount_attoFIL,
                        "MinSettleHeight": 0,
                        "Merges": [],
                        "Signature": {
                            "Type": 1,  # Secp256k1 signature type
                            "Data": "Simulated" + voucher_id[:88]  # 44 byte simulated signature
                        }
                    }
                    
                    # Store in simulation cache for voucher_list and voucher_check
                    if "vouchers" not in self.sim_cache:
                        self.sim_cache["vouchers"] = {}
                    
                    if ch_addr not in self.sim_cache["vouchers"]:
                        self.sim_cache["vouchers"][ch_addr] = []
                    
                    # Add to channel's vouchers if not already present
                    voucher_exists = False
                    for v in self.sim_cache["vouchers"][ch_addr]:
                        if v["Lane"] == lane and v["Nonce"] == nonce:
                            voucher_exists = True
                            break
                    
                    if not voucher_exists:
                        self.sim_cache["vouchers"][ch_addr].append(simulated_voucher)
                    
                    # Create result
                    result["success"] = True
                    result["simulated"] = True
                    result["result"] = {
                        "Voucher": simulated_voucher,
                        "Shortfall": "0"  # No shortfall in simulation
                    }
                    return result
                    
                except Exception as e:
                    logger.exception(f"Error in simulated paych_voucher_create: {str(e)}")
                    return handle_error(result, e, f"Error in simulated paych_voucher_create: {str(e)}")
            
            # Call Lotus API
            return self._make_request("PaychVoucherCreate", 
                                     params=[ch_addr, amount_attoFIL, lane],
                                     correlation_id=correlation_id)
            
        except Exception as e:
            logger.exception(f"Error creating voucher: {str(e)}")
            return handle_error(result, e)
            
    def paych_voucher_check(self, ch_addr, voucher, **kwargs):
        """Check validity of payment channel voucher.
        
        Args:
            ch_addr (str): Payment channel address
            voucher (str): Serialized voucher to check
            
        Returns:
            dict: Result dictionary with validation result
        """
        operation = "paych_voucher_check"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        # If in simulation mode, simulate voucher check
        if self.simulation_mode:
            try:
                # Validate inputs
                if not ch_addr:
                    return handle_error(result, ValueError("Payment channel address is required"))
                if not voucher:
                    return handle_error(result, ValueError("Voucher is required"))
                
                # Initialize vouchers dictionary if not exists
                if "vouchers" not in self.sim_cache:
                    self.sim_cache["vouchers"] = {}
                
                # Parse voucher (in real implementation, this would decode serialized voucher)
                # For simulation, assume voucher is already a dictionary
                if isinstance(voucher, str):
                    # Very basic parsing for simulation
                    voucher_dict = {"ChannelAddr": ch_addr, "Signature": {"Data": voucher}}
                else:
                    voucher_dict = voucher
                
                # Check if this voucher exists in our cache
                voucher_found = False
                if ch_addr in self.sim_cache["vouchers"]:
                    for v in self.sim_cache["vouchers"][ch_addr]:
                        # In a real implementation, more comprehensive matching would be needed
                        if v.get("Signature", {}).get("Data", "") == voucher_dict.get("Signature", {}).get("Data", ""):
                            voucher_found = True
                            # Return the stored voucher amount
                            result["success"] = True
                            result["simulated"] = True
                            result["result"] = {"Amount": v.get("Amount", "0")}
                            return result
                
                # If voucher not found, return dummy result (in real world would be an error)
                result["success"] = True
                result["simulated"] = True
                result["result"] = {"Amount": "0"}
                return result
                
            except Exception as e:
                logger.exception(f"Error in simulated paych_voucher_check: {str(e)}")
                return handle_error(result, e, f"Error in simulated paych_voucher_check: {str(e)}")
                
        return self._make_request("PaychVoucherCheckValid", 
                                 params=[ch_addr, voucher],
                                 correlation_id=correlation_id)
                                 
    def paych_voucher_list(self, ch_addr, **kwargs):
        """List all vouchers for a payment channel.
        
        Args:
            ch_addr (str): Payment channel address
            
        Returns:
            dict: Result dictionary with voucher list
        """
        operation = "paych_voucher_list"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        # If in simulation mode, return simulated voucher list
        if self.simulation_mode:
            try:
                # Validate input
                if not ch_addr:
                    return handle_error(result, ValueError("Payment channel address is required"))
                
                # Initialize vouchers dictionary if not exists
                if "vouchers" not in self.sim_cache:
                    self.sim_cache["vouchers"] = {}
                
                # Return empty list if no vouchers for this channel
                if ch_addr not in self.sim_cache["vouchers"]:
                    result["success"] = True
                    result["simulated"] = True
                    result["result"] = []
                    return result
                
                # Return list of vouchers for this channel
                result["success"] = True
                result["simulated"] = True
                result["result"] = self.sim_cache["vouchers"][ch_addr]
                return result
                
            except Exception as e:
                logger.exception(f"Error in simulated paych_voucher_list: {str(e)}")
                return handle_error(result, e, f"Error in simulated paych_voucher_list: {str(e)}")
                
        return self._make_request("PaychVoucherList", 
                                 params=[ch_addr],
                                 correlation_id=correlation_id)
        
    def paych_voucher_submit(self, ch_addr, voucher, **kwargs):
        """Submit voucher to chain to update payment channel state.
        
        Args:
            ch_addr (str): Payment channel address
            voucher (str): Serialized voucher to submit
            
        Returns:
            dict: Result dictionary with submission result
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        return self._make_request("PaychVoucherSubmit", 
                                 params=[ch_addr, voucher, None, None],
                                 correlation_id=correlation_id)
                                 
    def paych_settle(self, ch_addr, **kwargs):
        """Settle a payment channel.
        
        Starts the settlement period for the channel, after which funds can be collected.
        
        Args:
            ch_addr (str): Payment channel address
            
        Returns:
            dict: Result dictionary with settlement operation result
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        return self._make_request("PaychSettle", 
                                 params=[ch_addr],
                                 correlation_id=correlation_id)
        
    def paych_collect(self, ch_addr, **kwargs):
        """Collect funds from a payment channel.
        
        Channel must be settled and the settlement period expired to collect.
        
        Args:
            ch_addr (str): Payment channel address
            
        Returns:
            dict: Result dictionary with collection operation result
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        return self._make_request("PaychCollect", 
                                 params=[ch_addr],
                                 correlation_id=correlation_id)
                                 
    def _decode_voucher(self, encoded_voucher):
        """Decode a base64-encoded voucher.
        
        Args:
            encoded_voucher (str): Base64-encoded voucher
            
        Returns:
            dict: Decoded voucher data
        """
        operation = "decode_voucher"
        result = create_result_dict(operation)
        
        try:
            import base64
            
            # Decode from base64
            voucher_bytes = base64.b64decode(encoded_voucher)
            
            # Call API to decode from CBOR to JSON
            decode_result = self._make_request("PaychVoucherDecode", 
                                             params=[voucher_bytes.hex()])
            
            if not decode_result.get("success", False):
                return decode_result
                
            result["success"] = True
            result["voucher"] = decode_result.get("result")
            return result
            
        except Exception as e:
            logger.exception(f"Error decoding voucher: {str(e)}")
            return handle_error(result, e)

    # Miner methods
    def miner_get_info(self, miner_address, **kwargs):
        """Get information about a specific miner.
        
        Args:
            miner_address (str): The address of the miner.
            
        Returns:
            dict: Result dictionary with miner information.
        """
        operation = "miner_get_info"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        # If in simulation mode, return simulated miner info
        if self.simulation_mode:
            try:
                # Validate input
                if not miner_address:
                    return handle_error(result, ValueError("Miner address is required"))
                
                # Create a deterministic miner ID based on the address
                miner_hash = hashlib.sha256(miner_address.encode()).hexdigest()
                
                # Generate simulated miner information
                simulated_info = {
                    "Owner": f"t3{miner_hash[:40]}",
                    "Worker": f"t3{miner_hash[1:41]}",
                    "NewWorker": "",
                    "ControlAddresses": [f"t3{miner_hash[2:42]}"],
                    "WorkerChangeEpoch": -1,
                    "PeerId": f"12D3KooW{miner_hash[:36]}",
                    "Multiaddrs": [f"/ip4/203.0.113.{int(miner_hash[:2], 16) % 256}/tcp/24001"],
                    "WindowPoStProofType": 0,
                    "SectorSize": 34359738368,
                    "WindowPoStPartitionSectors": 1,
                    "ConsensusFaultElapsed": -1,
                    "Beneficiary": f"t3{miner_hash[:40]}",
                    "BeneficiaryTerm": {
                        "Quota": "0",
                        "UsedQuota": "0",
                        "Expiration": 0
                    },
                    "PendingBeneficiaryTerm": None
                }
                
                # Add simulated power/capacity based on miner address
                sector_multiplier = int(miner_hash[:4], 16) % 100 + 1  # 1-100 multiplier
                
                result["success"] = True
                result["simulated"] = True
                result["result"] = simulated_info
                return result
                
            except Exception as e:
                return handle_error(result, e, f"Error in simulated miner_get_info: {str(e)}")
        
        # Real API call for non-simulation mode
        return self._make_request("StateMinerInfo", params=[miner_address, []], correlation_id=correlation_id)
    
    def list_miners(self, **kwargs):
        """List all miners in the network.
        
        Returns:
            dict: Result dictionary with list of miners.
        """
        operation = "list_miners"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        # If in simulation mode, return simulated miner list
        if self.simulation_mode:
            try:
                # Generate a list of simulated miners
                # The list is deterministic for consistent testing
                miners = []
                seed = 12345  # Use a fixed seed for deterministic results
                random.seed(seed)
                
                # Generate 50 simulated miners with deterministic addresses
                for i in range(1, 51):
                    # Create deterministic miner IDs
                    miner_id = f"t0{10000 + i}"
                    miners.append(miner_id)
                
                # Add any miners that might be referenced in deals
                for deal_id, deal_data in self.sim_cache["deals"].items():
                    if "Provider" in deal_data and deal_data["Provider"] not in miners:
                        miners.append(deal_data["Provider"])
                
                result["success"] = True
                result["simulated"] = True
                result["result"] = miners
                return result
                
            except Exception as e:
                return handle_error(result, e, f"Error in simulated list_miners: {str(e)}")
        
        # Real API call for non-simulation mode
        return self._make_request("StateListMiners", params=[[]], correlation_id=correlation_id)
    
    def miner_get_power(self, miner_address, **kwargs):
        """Get the power of a specific miner.
        
        Args:
            miner_address (str): The address of the miner.
            
        Returns:
            dict: Result dictionary with miner power information.
        """
        operation = "miner_get_power"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        # If in simulation mode, return simulated miner power
        if self.simulation_mode:
            try:
                # Validate input
                if not miner_address:
                    return handle_error(result, ValueError("Miner address is required"))
                
                # Create deterministic miner power based on the address
                miner_hash = hashlib.sha256(miner_address.encode()).hexdigest()
                
                # Generate sector multiplier from hash (between 1-100)
                sector_multiplier = int(miner_hash[:4], 16) % 100 + 1
                
                # Base sector size: 32 GiB
                sector_size_bytes = 34359738368
                
                # Calculate power based on sectors
                sector_count = int(miner_hash[4:8], 16) % 1000 + sector_multiplier
                raw_byte_power = sector_count * sector_size_bytes
                
                # Calculate quality-adjusted power (higher for verified deals)
                quality_multiplier = 10 if int(miner_hash[8:10], 16) % 100 < 40 else 1
                quality_adjusted_power = raw_byte_power * quality_multiplier
                
                # Calculate network percentages (make them realistic)
                network_raw_power = 100 * raw_byte_power
                network_qa_power = 100 * quality_adjusted_power
                
                # Create simulated result structure
                simulated_power = {
                    "MinerPower": {
                        "RawBytePower": str(raw_byte_power),
                        "QualityAdjPower": str(quality_adjusted_power)
                    },
                    "TotalPower": {
                        "RawBytePower": str(network_raw_power),
                        "QualityAdjPower": str(network_qa_power)
                    },
                    "HasMinPower": sector_count > 10
                }
                
                result["success"] = True
                result["simulated"] = True
                result["result"] = simulated_power
                return result
                
            except Exception as e:
                return handle_error(result, e, f"Error in simulated miner_get_power: {str(e)}")
        
        return self._make_request("StateMinerPower", params=[miner_address, []], correlation_id=correlation_id)

    # Network methods
    def net_peers(self, **kwargs):
        """List all peers connected to the node.
        
        Returns:
            dict: Result dictionary with list of peers.
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        return self._make_request("NetPeers", correlation_id=correlation_id)
    
    def net_info(self, **kwargs):
        """Get network information.
        
        Returns:
            dict: Result dictionary with network information.
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        return self._make_request("NetAddrsListen", correlation_id=correlation_id)
    
    def net_bandwidth(self, **kwargs):
        """Get network bandwidth information.
        
        Returns:
            dict: Result dictionary with bandwidth information.
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        return self._make_request("NetBandwidthStats", correlation_id=correlation_id)

    # Sync methods
    def sync_status(self, **kwargs):
        """Get the sync status of the node.
        
        Returns:
            dict: Result dictionary with sync status.
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        return self._make_request("SyncState", correlation_id=correlation_id)
    
    def sync_check_bad(self, **kwargs):
        """Check for bad blocks in the sync.
        
        Returns:
            dict: Result dictionary with bad blocks information.
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        return self._make_request("SyncCheckBad", correlation_id=correlation_id)
        
    # Message Signing and Verification
    def wallet_sign(self, address, message, **kwargs):
        """Sign a message with the private key of the given address.
        
        Args:
            address (str): Address to sign the message with
            message (str or bytes): Message to sign
            
        Returns:
            dict: Result dictionary with signature
        """
        operation = "wallet_sign"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Convert message to hex if it's not already
            if isinstance(message, str):
                if not message.startswith("0x"):
                    # Assume UTF-8 string
                    message_bytes = message.encode('utf-8')
                    message_hex = "0x" + message_bytes.hex()
                else:
                    # Already hex
                    message_hex = message
            elif isinstance(message, bytes):
                message_hex = "0x" + message.hex()
            else:
                raise ValueError("Message must be a string or bytes")
                
            # Call Lotus API
            sign_result = self._make_request("WalletSign", 
                                           params=[address, message_hex],
                                           correlation_id=correlation_id)
            
            return sign_result
            
        except Exception as e:
            logger.exception(f"Error signing message: {str(e)}")
            return handle_error(result, e)
            
    def wallet_verify(self, address, message, signature, **kwargs):
        """Verify a signature was created by the given address.
        
        Args:
            address (str): Address that allegedly signed the message
            message (str or bytes): Original message
            signature (dict): Signature object
            
        Returns:
            dict: Result dictionary with verification result
        """
        operation = "wallet_verify"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Convert message to hex if needed
            if isinstance(message, str):
                if not message.startswith("0x"):
                    # Assume UTF-8 string
                    message_bytes = message.encode('utf-8')
                    message_hex = "0x" + message_bytes.hex()
                else:
                    # Already hex
                    message_hex = message
            elif isinstance(message, bytes):
                message_hex = "0x" + message.hex()
            else:
                raise ValueError("Message must be a string or bytes")
                
            # Call Lotus API
            verify_result = self._make_request("WalletVerify", 
                                             params=[address, message_hex, signature],
                                             correlation_id=correlation_id)
            
            return verify_result
            
        except Exception as e:
            logger.exception(f"Error verifying signature: {str(e)}")
            return handle_error(result, e)
            
    def wallet_generate_key(self, key_type="bls", **kwargs):
        """Generate a new key in the wallet.
        
        Args:
            key_type (str): Type of key to generate ("bls" or "secp256k1")
            
        Returns:
            dict: Result dictionary with new address
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        return self._make_request("WalletNew", 
                                 params=[key_type],
                                 correlation_id=correlation_id)
    
    def wallet_export(self, address, **kwargs):
        """Export the private key of an address.
        
        Args:
            address (str): Address to export
            
        Returns:
            dict: Result dictionary with private key
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        return self._make_request("WalletExport", 
                                 params=[address],
                                 correlation_id=correlation_id)
        
    def wallet_import(self, key_info, **kwargs):
        """Import a private key into the wallet.
        
        Args:
            key_info (dict): Key information including type and private key
            
        Returns:
            dict: Result dictionary with imported address
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        return self._make_request("WalletImport", 
                                 params=[key_info],
                                 correlation_id=correlation_id)
    
    def wallet_has_key(self, address, **kwargs):
        """Check if the wallet has a key for the given address.
        
        Args:
            address (str): Address to check
            
        Returns:
            dict: Result dictionary with boolean indicating if key exists
        """
        operation = "wallet_has_key"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Get all wallet addresses
            list_result = self._make_request("WalletList", correlation_id=correlation_id)
            
            if not list_result.get("success", False):
                return list_result
                
            addresses = list_result.get("result", [])
            has_key = address in addresses
            
            result["success"] = True
            result["has_key"] = has_key
            return result
            
        except Exception as e:
            logger.exception(f"Error checking for key: {str(e)}")
            return handle_error(result, e)
            
    def wallet_key_info(self, address, **kwargs):
        """Get public key information for an address.
        
        Args:
            address (str): Address to get info for
            
        Returns:
            dict: Result dictionary with key information
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        return self._make_request("WalletInfo", 
                                 params=[address],
                                 correlation_id=correlation_id)
                                 
    def export_storage_deals(self, output_path, include_expired=False, format="json", **kwargs):
        """Export storage deals data to file for analytics or backup.
        
        Args:
            output_path (str): Path to write export file
            include_expired (bool): Whether to include expired deals
            format (str): Output format - "json" or "csv"
            
        Returns:
            dict: Result dictionary with export information
        """
        operation = "export_storage_deals"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Validate format
            if format.lower() not in ["json", "csv"]:
                return handle_error(result, ValueError("Format must be 'json' or 'csv'"))
                
            # Get current storage deals
            deals_result = self.client_list_deals()
            if not deals_result.get("success", False):
                return deals_result
                
            deals = deals_result.get("result", [])
            
            # Filter deals if needed
            if not include_expired:
                deals = [deal for deal in deals if 
                         deal.get("State", 0) not in [8, 9]]  # Filter expired/slashed
            
            # Process deals to make them more useful for export
            processed_deals = []
            for deal in deals:
                processed_deal = {
                    'DealID': deal.get('DealID', 0),
                    'Provider': deal.get('Provider', 'unknown'),
                    'Client': deal.get('Client', 'unknown'),
                    'State': deal.get('State', 0),
                    'StateDesc': self._get_deal_state_name(deal.get('State', 0)),
                    'PieceCID': deal.get('PieceCID', {}).get('/', 'unknown'),
                    'DataCID': deal.get('DataCID', {}).get('/', 'unknown'),
                    'Size': deal.get('Size', 0),
                    'PricePerEpoch': deal.get('PricePerEpoch', '0'),
                    'Duration': deal.get('Duration', 0),
                    'StartEpoch': deal.get('StartEpoch', 0),
                    'EndEpoch': deal.get('StartEpoch', 0) + deal.get('Duration', 0),
                    'SlashEpoch': deal.get('SlashEpoch', -1),
                    'Verified': deal.get('Verified', False),
                    'FastRetrieval': deal.get('FastRetrieval', False),
                }
                processed_deals.append(processed_deal)
            
            # Export to the specified format
            if format.lower() == "json":
                import json
                with open(output_path, 'w') as f:
                    json.dump({
                        "timestamp": time.time(),
                        "export_date": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "deal_count": len(processed_deals),
                        "include_expired": include_expired,
                        "deals": processed_deals
                    }, f, indent=2)
            else:  # CSV
                try:
                    import csv
                    with open(output_path, 'w', newline='') as f:
                        # Determine fields from first deal, or use default list
                        if processed_deals:
                            fieldnames = list(processed_deals[0].keys())
                        else:
                            fieldnames = ['DealID', 'Provider', 'State', 'StateDesc', 'PieceCID', 
                                         'Size', 'PricePerEpoch', 'Duration', 'Verified']
                            
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(processed_deals)
                except ImportError:
                    # Fall back to manual CSV generation
                    with open(output_path, 'w') as f:
                        # Write header
                        if processed_deals:
                            header = ','.join([str(k) for k in processed_deals[0].keys()])
                            f.write(f"{header}\n")
                            
                            # Write rows
                            for deal in processed_deals:
                                row = ','.join([str(v) for v in deal.values()])
                                f.write(f"{row}\n")
                        else:
                            f.write("No deals found\n")
            
            # Success result
            result["success"] = True
            result["deals_exported"] = len(processed_deals)
            result["export_path"] = output_path
            result["format"] = format.lower()
            
            return result
            
        except Exception as e:
            logger.exception(f"Error exporting storage deals: {str(e)}")
            return handle_error(result, e)
            
    def client_import(self, file_path, **kwargs):
        """Import content to Lotus.
        
        Args:
            file_path (str): Path to file to import
            **kwargs: Additional parameters:
                - car (bool): Whether the file is a CAR file
                - local_only (bool): Only import to local node without making deals
                
        Returns:
            dict: Result dictionary with import information
        """
        operation = "client_import"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        # If in simulation mode, return simulated import
        if self.simulation_mode:
            try:
                # Check if file exists - so we can give a real error for non-existent files
                if not os.path.isfile(file_path):
                    return handle_error(result, FileNotFoundError(f"File not found: {file_path}"))
                
                # Create a deterministic CID based on the file path
                file_hash = hashlib.sha256(file_path.encode()).hexdigest()
                data_cid = f"bafyrei{file_hash[:38]}"
                
                # Get file size
                file_size = os.path.getsize(file_path)
                
                # Create simulated import result
                import_id = str(uuid.uuid4())
                
                # Add to simulation cache
                self.sim_cache["imports"][data_cid] = {
                    "ImportID": import_id,
                    "CID": data_cid,
                    "Root": {"/" : data_cid},
                    "FilePath": file_path,
                    "Size": file_size,
                    "Status": "Complete",
                    "Created": time.time(),
                    "Deals": []
                }
                
                # Add to contents cache
                self.sim_cache["contents"][data_cid] = {
                    "size": file_size,
                    "deals": [],
                    "local": True
                }
                
                # Build result
                result["success"] = True
                result["simulated"] = True
                result["result"] = {
                    "Root": {"/" : data_cid},
                    "ImportID": import_id
                }
                
                return result
                
            except Exception as e:
                return handle_error(result, e, f"Error in simulated import: {str(e)}")
        
        try:
            # Verify file exists
            if not os.path.isfile(file_path):
                return handle_error(result, FileNotFoundError(f"File not found: {file_path}"))
                
            # Set up import parameters
            params = [{
                "Path": file_path,
                "IsCAR": kwargs.get("car", file_path.lower().endswith('.car')),
                "LocalOnly": kwargs.get("local_only", False)
            }]
            
            # Call API
            return self._make_request("ClientImport", 
                                     params=params,
                                     correlation_id=correlation_id)
                
        except Exception as e:
            logger.exception(f"Error importing file: {str(e)}")
            return handle_error(result, e)
    
    def import_from_car(self, car_file, **kwargs):
        """Import content from a CAR file into Lotus.
        
        Args:
            car_file (str): Path to CAR file to import
            **kwargs: Additional parameters:
                - local_only (bool): Only import to local node without making deals
                
        Returns:
            dict: Result dictionary with import information
        """
        operation = "import_from_car"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        
        try:
            # Verify file exists
            if not os.path.isfile(car_file):
                result = create_result_dict(operation, correlation_id)
                return handle_error(result, FileNotFoundError(f"CAR file not found: {car_file}"))
                
            # Check if file has .car extension and add warning to kwargs
            if not car_file.lower().endswith('.car'):
                kwargs["warning"] = "File does not have .car extension, but proceeding anyway"
                
            # Call client_import with car=True
            return self.client_import(car_file, car=True, local_only=kwargs.get("local_only", False),
                                     correlation_id=correlation_id)
                
        except Exception as e:
            result = create_result_dict(operation, correlation_id)
            logger.exception(f"Error importing CAR file: {str(e)}")
            return handle_error(result, e)
            
    def export_chain_snapshot(self, output_path, **kwargs):
        """Export a Filecoin chain snapshot for node initialization.
        
        Args:
            output_path (str): Path to save the snapshot
            **kwargs: Additional parameters:
                - height (int): Chain height to snapshot (0 for current)
                
        Returns:
            dict: Result dictionary with export information
        """
        operation = "export_chain_snapshot"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Get parameters
            height = kwargs.get("height", 0)
            
            # Prepare parameters
            params = [output_path]
            if height > 0:
                params.append({"Height": height})
                
            # Call API
            export_result = self._make_request("ChainExport", 
                                            params=params,
                                            timeout=300,  # Longer timeout for export
                                            correlation_id=correlation_id)
            
            if export_result.get("success", False):
                # Add file size information
                if os.path.exists(output_path):
                    export_result["file_size_bytes"] = os.path.getsize(output_path)
                    export_result["file_size_mb"] = os.path.getsize(output_path) / (1024*1024)
                    
                # Get current chain head for reference
                head_result = self.get_chain_head()
                if head_result.get("success", False):
                    head_data = head_result.get("result", {})
                    if "Cids" in head_data and head_data["Cids"]:
                        export_result["chain_head_cid"] = head_data["Cids"][0].get("/")
                    export_result["chain_height"] = head_data.get("Height")
                    
            return export_result
            
        except Exception as e:
            logger.exception(f"Error exporting chain snapshot: {str(e)}")
            return handle_error(result, e)
    
    def export_miner_data(self, output_path, format="json", include_power=True, **kwargs):
        """Export data about miners on the Filecoin network.
        
        Collects comprehensive information about miners including addresses,
        power, peer info, and locations for analysis or visualization.
        
        Args:
            output_path (str): Path to save the exported data
            format (str): Output format - "json" or "csv" 
            include_power (bool): Whether to include detailed power information
            **kwargs: Additional parameters:
                - miner_addresses (list): Specific miners to include (default: all)
                - include_metadata (bool): Whether to include extra metadata
                - correlation_id (str): Operation correlation ID
                
        Returns:
            dict: Result dictionary with export information
        """
        operation = "export_miner_data"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Validate format
            if format.lower() not in ["json", "csv"]:
                return handle_error(result, ValueError("Format must be 'json' or 'csv'"))
                
            # Get miner list if not specified
            miner_addresses = kwargs.get("miner_addresses", None)
            if not miner_addresses:
                miners_result = self.list_miners()
                if not miners_result.get("success", False):
                    return miners_result
                    
                miner_addresses = miners_result.get("result", [])
                
            # Limit to 100 miners if not specifically filtering
            if len(miner_addresses) > 100 and not kwargs.get("miner_addresses"):
                logger.info(f"Limiting export to first 100 miners out of {len(miner_addresses)}")
                miner_addresses = miner_addresses[:100]
                result["limited_miners"] = True
                result["total_miners"] = len(miner_addresses)
                
            # Collect miner data
            miners_data = []
            for miner_addr in miner_addresses:
                try:
                    # Get basic miner info
                    info_result = self.miner_get_info(miner_addr)
                    if not info_result.get("success", False):
                        miners_data.append({
                            "address": miner_addr,
                            "error": "Failed to get miner info"
                        })
                        continue
                        
                    miner_info = info_result.get("result", {})
                    
                    # Prepare miner data entry
                    miner_data = {
                        "address": miner_addr,
                        "peer_id": miner_info.get("PeerId", ""),
                        "owner": miner_info.get("Owner", ""),
                        "worker": miner_info.get("Worker", ""),
                        "sector_size": miner_info.get("SectorSize", 0),
                    }
                    
                    # Add multiaddrs if available
                    if "Multiaddrs" in miner_info and miner_info["Multiaddrs"]:
                        try:
                            miner_data["multiaddrs"] = [
                                bytes.fromhex(addr).decode("utf-8", errors="replace")
                                for addr in miner_info.get("Multiaddrs", [])
                            ]
                        except:
                            miner_data["multiaddrs"] = ["<invalid format>"]
                    
                    # Get power information if requested
                    if include_power:
                        power_result = self.miner_get_power(miner_addr)
                        if power_result.get("success", False):
                            power_info = power_result.get("result", {})
                            miner_power = power_info.get("MinerPower", {})
                            total_power = power_info.get("TotalPower", {})
                            
                            # Add power data
                            miner_data["raw_byte_power"] = miner_power.get("RawBytePower", "0")
                            miner_data["quality_adj_power"] = miner_power.get("QualityAdjPower", "0")
                            
                            # Calculate percentage of network power
                            if "RawBytePower" in total_power and total_power["RawBytePower"] != "0":
                                try:
                                    miner_raw = int(miner_power.get("RawBytePower", "0"))
                                    total_raw = int(total_power.get("RawBytePower", "0"))
                                    if total_raw > 0:
                                        miner_data["power_percentage"] = (miner_raw / total_raw) * 100
                                except (ValueError, TypeError, ZeroDivisionError):
                                    miner_data["power_percentage"] = 0
                    
                    # Add to miners list
                    miners_data.append(miner_data)
                    
                except Exception as e:
                    logger.error(f"Error processing miner {miner_addr}: {str(e)}")
                    miners_data.append({
                        "address": miner_addr,
                        "error": str(e)
                    })
            
            # Export the data in requested format
            if format.lower() == "json":
                with open(output_path, 'w') as f:
                    json.dump({
                        "timestamp": time.time(),
                        "export_date": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "miner_count": len(miners_data),
                        "miners": miners_data
                    }, f, indent=2)
            else:  # CSV
                try:
                    import csv
                    
                    # Determine fields from first miner with successful data
                    fieldnames = []
                    for miner in miners_data:
                        if "error" not in miner:
                            fieldnames = list(miner.keys())
                            break
                            
                    if not fieldnames:
                        fieldnames = ["address", "error"]
                    
                    # Write CSV file
                    with open(output_path, 'w', newline='') as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
                        writer.writeheader()
                        writer.writerows(miners_data)
                        
                except ImportError:
                    # Fallback to manual CSV creation
                    with open(output_path, 'w') as f:
                        # Write header
                        header = ','.join(fieldnames)
                        f.write(f"{header}\n")
                        
                        # Write rows
                        for miner in miners_data:
                            row_values = []
                            for field in fieldnames:
                                value = str(miner.get(field, ""))
                                # Quote values containing commas
                                if ',' in value:
                                    value = f'"{value}"'
                                row_values.append(value)
                            row = ','.join(row_values)
                            f.write(f"{row}\n")
            
            # Success result
            result["success"] = True
            result["miners_exported"] = len(miners_data)
            result["export_path"] = output_path
            result["format"] = format.lower()
            
            return result
            
        except Exception as e:
            logger.exception(f"Error exporting miner data: {str(e)}")
            return handle_error(result, e)
    
    def export_deals_metrics(self, output_path=None, **kwargs):
        """Export comprehensive metrics about storage deals.
        
        Collects and analyzes detailed metrics about storage deals including:
        - Deal size distribution
        - Deal duration statistics
        - Provider distribution
        - Success/failure rates
        - Verification rates
        
        Args:
            output_path (str, optional): Path to save metrics data JSON
            **kwargs: Additional parameters:
                - include_expired (bool): Whether to include expired deals
                - correlation_id (str): Operation correlation ID
                
        Returns:
            dict: Result dictionary with metrics information
        """
        operation = "export_deals_metrics"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Get current storage deals
            deals_result = self.client_list_deals()
            if not deals_result.get("success", False):
                return deals_result
                
            deals = deals_result.get("result", [])
            include_expired = kwargs.get("include_expired", False)
            
            # Filter deals if needed
            if not include_expired:
                deals = [deal for deal in deals if 
                         deal.get("State", 0) not in [8, 9]]  # Filter expired/slashed
            
            # Initialize metrics containers
            metrics = {
                "total_deals": len(deals),
                "total_data_size": 0,
                "active_deals": 0,
                "verified_deals": 0,
                "fast_retrieval_deals": 0,
                "provider_count": 0,
                "deals_by_state": {},
                "deals_by_provider": {},
                "size_distribution": {
                    "0-1GiB": 0,
                    "1-10GiB": 0,
                    "10-100GiB": 0,
                    "100-1000GiB": 0,
                    "1000+GiB": 0
                },
                "duration_distribution": {
                    "0-30days": 0,
                    "30-90days": 0,
                    "90-180days": 0,
                    "180-365days": 0,
                    "365+days": 0
                },
                "price_statistics": {
                    "min": None,
                    "max": None,
                    "average": None,
                    "median": None
                }
            }
            
            # Process each deal
            providers = set()
            deal_states = {}
            deal_sizes = []
            deal_durations = []
            deal_prices = []
            
            for deal in deals:
                # Count by state
                state = deal.get("State", 0)
                state_name = self._get_deal_state_name(state)
                deal_states[state_name] = deal_states.get(state_name, 0) + 1
                
                # Count active deals
                if state == 7:  # Active state
                    metrics["active_deals"] += 1
                
                # Track verified deals
                if deal.get("Verified", False):
                    metrics["verified_deals"] += 1
                
                # Track fast retrieval
                if deal.get("FastRetrieval", False):
                    metrics["fast_retrieval_deals"] += 1
                
                # Count providers
                provider = deal.get("Provider", "unknown")
                providers.add(provider)
                metrics["deals_by_provider"][provider] = metrics["deals_by_provider"].get(provider, 0) + 1
                
                # Track size distribution
                size = deal.get("Size", 0)
                metrics["total_data_size"] += size
                size_gib = size / (1024 * 1024 * 1024)  # Convert to GiB
                deal_sizes.append(size_gib)
                
                if size_gib < 1:
                    metrics["size_distribution"]["0-1GiB"] += 1
                elif size_gib < 10:
                    metrics["size_distribution"]["1-10GiB"] += 1
                elif size_gib < 100:
                    metrics["size_distribution"]["10-100GiB"] += 1
                elif size_gib < 1000:
                    metrics["size_distribution"]["100-1000GiB"] += 1
                else:
                    metrics["size_distribution"]["1000+GiB"] += 1
                
                # Track duration distribution
                duration = deal.get("Duration", 0)
                duration_days = duration / (24 * 2 * 60)  # Convert epochs to days (assuming 30s epochs)
                deal_durations.append(duration_days)
                
                if duration_days < 30:
                    metrics["duration_distribution"]["0-30days"] += 1
                elif duration_days < 90:
                    metrics["duration_distribution"]["30-90days"] += 1
                elif duration_days < 180:
                    metrics["duration_distribution"]["90-180days"] += 1
                elif duration_days < 365:
                    metrics["duration_distribution"]["180-365days"] += 1
                else:
                    metrics["duration_distribution"]["365+days"] += 1
                
                # Track price statistics
                try:
                    price = float(deal.get("PricePerEpoch", "0"))
                    if price > 0:
                        deal_prices.append(price)
                except (ValueError, TypeError):
                    pass
            
            # Set metrics from aggregated data
            metrics["provider_count"] = len(providers)
            metrics["deals_by_state"] = deal_states
            
            # Calculate price statistics
            if deal_prices:
                metrics["price_statistics"]["min"] = min(deal_prices)
                metrics["price_statistics"]["max"] = max(deal_prices)
                metrics["price_statistics"]["average"] = sum(deal_prices) / len(deal_prices)
                metrics["price_statistics"]["median"] = sorted(deal_prices)[len(deal_prices) // 2]
            
            # Calculate size statistics
            if deal_sizes:
                metrics["size_statistics"] = {
                    "min_gib": min(deal_sizes),
                    "max_gib": max(deal_sizes),
                    "avg_gib": sum(deal_sizes) / len(deal_sizes),
                    "median_gib": sorted(deal_sizes)[len(deal_sizes) // 2],
                    "total_gib": sum(deal_sizes)
                }
            
            # Calculate duration statistics
            if deal_durations:
                metrics["duration_statistics"] = {
                    "min_days": min(deal_durations),
                    "max_days": max(deal_durations),
                    "avg_days": sum(deal_durations) / len(deal_durations),
                    "median_days": sorted(deal_durations)[len(deal_durations) // 2]
                }
            
            # Format values for readable output
            metrics["total_data_size_human"] = self._format_size(metrics["total_data_size"])
            metrics["avg_deal_size_human"] = self._format_size(
                metrics["total_data_size"] / len(deals) if deals else 0
            )
            
            # Export to file if requested
            if output_path:
                with open(output_path, 'w') as f:
                    json.dump({
                        "timestamp": time.time(),
                        "export_date": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "metrics": metrics
                    }, f, indent=2)
                result["export_path"] = output_path
            
            # Return success with metrics
            result["success"] = True
            result["metrics"] = metrics
            
            return result
            
        except Exception as e:
            logger.exception(f"Error exporting deals metrics: {str(e)}")
            return handle_error(result, e)
    
    def _format_size(self, size_bytes):
        """Format size in bytes to human-readable string.
        
        Args:
            size_bytes (int): Size in bytes
            
        Returns:
            str: Formatted size string
        """
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024**2:
            return f"{size_bytes/1024:.2f} KiB"
        elif size_bytes < 1024**3:
            return f"{size_bytes/(1024**2):.2f} MiB"
        elif size_bytes < 1024**4:
            return f"{size_bytes/(1024**3):.2f} GiB"
        else:
            return f"{size_bytes/(1024**4):.2f} TiB"
    
    def import_wallet_data(self, wallet_file, **kwargs):
        """Import wallet data from a file.
        
        Imports wallet keys from a backup file, supporting multiple formats:
        - JSON export files
        - Private key files
        - Hex-encoded key strings
        
        Args:
            wallet_file (str): Path to the wallet file to import
            **kwargs: Additional parameters:
                - wallet_type (str): Type of wallet (bls, secp256k1)
                - as_default (bool): Whether to set as the default wallet
                - correlation_id (str): Operation correlation ID
                
        Returns:
            dict: Result dictionary with import information
        """
        operation = "import_wallet_data"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Check if file exists
            if not os.path.isfile(wallet_file):
                return handle_error(result, FileNotFoundError(f"Wallet file not found: {wallet_file}"))
            
            # Try to determine the type of file
            with open(wallet_file, 'r') as f:
                content = f.read().strip()
            
            # Determine wallet type
            wallet_type = kwargs.get("wallet_type", None)
            if not wallet_type:
                # Try to auto-detect
                if content.startswith("{") and content.endswith("}"):
                    # Likely JSON format
                    wallet_type = "json"
                elif content.startswith("0x") or all(c in "0123456789abcdefABCDEF" for c in content):
                    # Hex key format
                    wallet_type = "hex"
                else:
                    # Default to BLS
                    wallet_type = "bls"
            
            imported_addresses = []
            
            if wallet_type == "json":
                # Parse JSON content
                try:
                    wallet_data = json.loads(content)
                    
                    # Handle different JSON formats
                    if isinstance(wallet_data, dict) and "KeyInfo" in wallet_data:
                        # Single key format
                        import_result = self.wallet_import(wallet_data)
                        if import_result.get("success", False):
                            imported_address = import_result.get("result")
                            imported_addresses.append(imported_address)
                            
                    elif isinstance(wallet_data, list):
                        # Multiple keys format
                        for key_info in wallet_data:
                            if isinstance(key_info, dict) and "KeyInfo" in key_info:
                                import_result = self.wallet_import(key_info)
                                if import_result.get("success", False):
                                    imported_address = import_result.get("result")
                                    imported_addresses.append(imported_address)
                except json.JSONDecodeError:
                    return handle_error(result, ValueError("Invalid JSON format in wallet file"))
                    
            elif wallet_type in ["bls", "secp256k1"]:
                # Try to import as raw key with specified type
                key_info = {
                    "Type": wallet_type,
                    "PrivateKey": content
                }
                import_result = self.wallet_import({"KeyInfo": key_info})
                if import_result.get("success", False):
                    imported_address = import_result.get("result")
                    imported_addresses.append(imported_address)
                    
            elif wallet_type == "hex":
                # Try to import hex key, first trying BLS then secp256k1
                for key_type in ["bls", "secp256k1"]:
                    key_info = {
                        "Type": key_type,
                        "PrivateKey": content
                    }
                    import_result = self.wallet_import({"KeyInfo": key_info})
                    if import_result.get("success", False):
                        imported_address = import_result.get("result")
                        imported_addresses.append(imported_address)
                        break
            
            # Check if any addresses were imported
            if not imported_addresses:
                return handle_error(result, LotusError("Failed to import any wallet addresses"))
                
            # Set as default if requested
            if kwargs.get("as_default", False) and imported_addresses:
                default_addr = imported_addresses[0]
                # Currently Lotus doesn't have a direct API to set default,
                # but can be done by storing the address preference
                result["set_as_default"] = True
                result["default_address"] = default_addr
            
            # Success result
            result["success"] = True
            result["imported_addresses"] = imported_addresses
            result["count"] = len(imported_addresses)
            result["wallet_type"] = wallet_type
            
            return result
            
        except Exception as e:
            logger.exception(f"Error importing wallet data: {str(e)}")
            return handle_error(result, e)
    
    def process_chain_messages(self, height=None, count=20, output_path=None, **kwargs):
        """Process and analyze blockchain messages for analytics.
        
        Retrieves and analyzes messages from the blockchain, processing them
        for analytics purposes including:
        - Message volumes and types
        - Gas usage patterns
        - Address interactions
        - Method invocation frequencies
        
        Args:
            height (int, optional): Chain height to start from (default: current head)
            count (int): Number of tipsets to process
            output_path (str, optional): Path to export analysis results
            **kwargs: Additional parameters:
                - filter_methods (list): Only process specific methods
                - filter_addresses (list): Only process messages involving these addresses
                - correlation_id (str): Operation correlation ID
                
        Returns:
            dict: Result dictionary with analysis information
        """
        operation = "process_chain_messages"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Get current chain head if height not specified
            if height is None:
                head_result = self.get_chain_head()
                if not head_result.get("success", False):
                    return head_result
                    
                head_data = head_result.get("result", {})
                current_height = head_data.get("Height", 0)
                head_cids = head_data.get("Cids", [])
                
                if not head_cids:
                    return handle_error(result, LotusError("Failed to get valid chain head"))
                    
                tipset = {"Cids": head_cids, "Height": current_height}
            else:
                # Look up tipset at specified height
                tipset_result = self._make_request("ChainGetTipSetByHeight", 
                                                params=[height, []],
                                                correlation_id=correlation_id)
                if not tipset_result.get("success", False):
                    return tipset_result
                    
                tipset = tipset_result.get("result", {})
                current_height = tipset.get("Height", 0)
            
            # Initialize analytics containers
            analytics = {
                "processed_tipsets": 0,
                "processed_blocks": 0,
                "total_messages": 0,
                "message_types": {},
                "method_calls": {},
                "gas_usage": {
                    "total": 0,
                    "average": 0,
                    "max": 0,
                    "min": float('inf')
                },
                "active_addresses": set(),
                "address_interactions": {},
                "value_transfer": {
                    "total": "0",
                    "max": "0",
                    "transactions": 0
                },
                "blocks_by_miner": {}
            }
            
            # Get filters if specified
            filter_methods = kwargs.get("filter_methods", [])
            filter_addresses = kwargs.get("filter_addresses", [])
            
            # Process tipsets
            remaining_tipsets = count
            current_tipset = tipset
            
            while remaining_tipsets > 0 and current_tipset and "Cids" in current_tipset:
                analytics["processed_tipsets"] += 1
                
                # Process blocks in tipset
                for block_cid in current_tipset.get("Cids", []):
                    block_cid_str = block_cid.get("/")
                    if not block_cid_str:
                        continue
                        
                    # Get block
                    block_result = self.get_block(block_cid_str)
                    if not block_result.get("success", False):
                        logger.warning(f"Failed to get block {block_cid_str}")
                        continue
                        
                    block = block_result.get("result", {})
                    analytics["processed_blocks"] += 1
                    
                    # Track miner statistics
                    miner = block.get("Miner", "unknown")
                    analytics["blocks_by_miner"][miner] = analytics["blocks_by_miner"].get(miner, 0) + 1
                    
                    # Get messages in block
                    messages_result = self._make_request("ChainGetBlockMessages", 
                                                      params=[{"/" : block_cid_str}],
                                                      correlation_id=correlation_id)
                    if not messages_result.get("success", False):
                        continue
                        
                    messages_data = messages_result.get("result", {})
                    
                    # Process all messages
                    for msg_type in ["BlsMessages", "SecpkMessages"]:
                        for msg in messages_data.get(msg_type, []):
                            # Apply filters if specified
                            if filter_addresses and (msg.get("From") not in filter_addresses and 
                                                    msg.get("To") not in filter_addresses):
                                continue
                                
                            if filter_methods and str(msg.get("Method")) not in filter_methods:
                                continue
                                
                            # Count message
                            analytics["total_messages"] += 1
                            
                            # Track message type
                            analytics["message_types"][msg_type] = analytics["message_types"].get(msg_type, 0) + 1
                            
                            # Track method calls
                            method = str(msg.get("Method", "unknown"))
                            analytics["method_calls"][method] = analytics["method_calls"].get(method, 0) + 1
                            
                            # Track gas usage
                            gas_limit = int(msg.get("GasLimit", "0"))
                            gas_fee_cap = int(msg.get("GasFeeCap", "0"))
                            gas_premium = int(msg.get("GasPremium", "0"))
                            
                            analytics["gas_usage"]["total"] += gas_limit
                            analytics["gas_usage"]["max"] = max(analytics["gas_usage"]["max"], gas_limit)
                            analytics["gas_usage"]["min"] = min(analytics["gas_usage"]["min"], gas_limit) if gas_limit > 0 else analytics["gas_usage"]["min"]
                            
                            # Track addresses
                            from_addr = msg.get("From", "")
                            to_addr = msg.get("To", "")
                            
                            if from_addr:
                                analytics["active_addresses"].add(from_addr)
                            if to_addr:
                                analytics["active_addresses"].add(to_addr)
                                
                            # Track address interactions
                            if from_addr and to_addr:
                                interaction_key = f"{from_addr}->{to_addr}"
                                analytics["address_interactions"][interaction_key] = analytics["address_interactions"].get(interaction_key, 0) + 1
                                
                            # Track value transfers
                            value = msg.get("Value", "0")
                            if value and value != "0":
                                analytics["value_transfer"]["transactions"] += 1
                                
                                # Update total (handling as strings to avoid precision issues)
                                try:
                                    current_total = int(analytics["value_transfer"]["total"])
                                    current_max = int(analytics["value_transfer"]["max"])
                                    value_int = int(value)
                                    
                                    analytics["value_transfer"]["total"] = str(current_total + value_int)
                                    analytics["value_transfer"]["max"] = str(max(current_max, value_int))
                                except (ValueError, TypeError):
                                    pass
                
                # Get parent tipset for next iteration
                if current_height <= 1:
                    # Reached genesis, stop processing
                    break
                    
                parent_result = self._make_request("ChainGetTipSet", 
                                               params=[current_tipset.get("Parents", [])],
                                               correlation_id=correlation_id)
                if not parent_result.get("success", False):
                    break
                    
                current_tipset = parent_result.get("result", {})
                current_height = current_tipset.get("Height", 0)
                remaining_tipsets -= 1
            
            # Calculate derived metrics
            if analytics["total_messages"] > 0:
                analytics["gas_usage"]["average"] = analytics["gas_usage"]["total"] / analytics["total_messages"]
            
            if analytics["gas_usage"]["min"] == float('inf'):
                analytics["gas_usage"]["min"] = 0
                
            # Convert sets to lists for JSON serialization
            analytics["active_addresses"] = list(analytics["active_addresses"])
            
            # Export to file if requested
            if output_path:
                with open(output_path, 'w') as f:
                    json.dump({
                        "timestamp": time.time(),
                        "export_date": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "start_height": tipset.get("Height"),
                        "end_height": current_height,
                        "analytics": analytics
                    }, f, indent=2)
                result["export_path"] = output_path
            
            # Success result
            result["success"] = True
            result["analytics"] = analytics
            result["start_height"] = tipset.get("Height")
            result["end_height"] = current_height
            
            return result
            
        except Exception as e:
            logger.exception(f"Error processing chain messages: {str(e)}")
            return handle_error(result, e)
    
    # Advanced Miner Operations
    def connect_miner_api(self, miner_api_url=None, miner_token=None, **kwargs):
        """Connect to a Lotus Miner API.
        
        Args:
            miner_api_url (str, optional): URL of the miner API
            miner_token (str, optional): Auth token for the miner API
            
        Returns:
            dict: Result dictionary with connection status
        """
        operation = "connect_miner_api"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Store miner API connection info
            self.miner_api_url = miner_api_url or os.environ.get("LOTUS_MINER_API", "http://localhost:2345/rpc/v0")
            self.miner_token = miner_token or os.environ.get("LOTUS_MINER_TOKEN", "")
            
            # Test connection
            test_result = self._make_miner_request("ActorAddress")
            
            if not test_result.get("success", False):
                return test_result
                
            result["success"] = True
            result["miner_address"] = test_result.get("result")
            result["message"] = "Successfully connected to miner API"
            return result
            
        except Exception as e:
            logger.exception(f"Error connecting to miner API: {str(e)}")
            return handle_error(result, e)
        
    def _make_miner_request(self, method, params=None, timeout=60, correlation_id=None):
        """Make a request to the Lotus Miner API.
        
        Args:
            method (str): The API method to call
            params (list, optional): Parameters for the API call
            timeout (int, optional): Request timeout in seconds
            correlation_id (str, optional): Correlation ID for tracking
            
        Returns:
            dict: Result dictionary
        """
        result = create_result_dict(method, correlation_id or self.correlation_id)
        
        try:
            # Check if miner API is configured
            if not hasattr(self, "miner_api_url") or not self.miner_api_url:
                return handle_error(result, ValueError("Miner API not configured. Call connect_miner_api first."))
                
            headers = {
                "Content-Type": "application/json",
            }
            
            # Add authorization token if available
            if hasattr(self, "miner_token") and self.miner_token:
                headers["Authorization"] = f"Bearer {self.miner_token}"
            
            # Prepare request data
            request_data = {
                "jsonrpc": "2.0",
                "method": f"Filecoin.{method}",
                "params": params or [],
                "id": 1,
            }
            
            # Make the API request
            response = requests.post(
                self.miner_api_url, 
                headers=headers,
                json=request_data,
                timeout=timeout
            )
            
            # Check for HTTP errors
            response.raise_for_status()
            
            # Parse response
            response_data = response.json()
            
            # Check for JSON-RPC errors
            if "error" in response_data:
                error_msg = response_data["error"].get("message", "Unknown error")
                error_code = response_data["error"].get("code", -1)
                return handle_error(result, LotusError(f"Error {error_code}: {error_msg}"))
            
            # Return successful result
            result["success"] = True
            result["result"] = response_data.get("result")
            return result
            
        except Exception as e:
            logger.exception(f"Error in miner request {method}: {str(e)}")
            return handle_error(result, e)
        
    def miner_get_address(self, **kwargs):
        """Get the miner's actor address.
        
        Returns:
            dict: Result dictionary with miner address
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        return self._make_miner_request("ActorAddress", correlation_id=correlation_id)
    
    def miner_list_sectors(self, **kwargs):
        """List all sectors managed by the miner.
        
        Returns:
            dict: Result dictionary with sector list
        """
        operation = "miner_list_sectors"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        # If in simulation mode, return simulated sector list
        if self.simulation_mode:
            try:
                # Initialize miner sectors if not already in simulation cache
                if "sectors" not in self.sim_cache:
                    self.sim_cache["sectors"] = {}
                    
                    # Get our miner address or use a default
                    miner_address = None
                    try:
                        miner_addr_result = self.miner_get_address()
                        if miner_addr_result.get("success", False):
                            miner_address = miner_addr_result.get("result", "")
                    except Exception:
                        pass
                    
                    if not miner_address:
                        # Use a default miner address
                        miner_address = "t01000"
                    
                    # Generate deterministic sector numbers
                    # We'll create 20 simulated sectors
                    for i in range(1, 21):
                        sector_id = i
                        
                        # Create a deterministic sector hash based on the sector ID
                        sector_hash = hashlib.sha256(f"{miner_address}_sector_{sector_id}".encode()).hexdigest()
                        
                        # Determine sector state (most active, some in other states)
                        sector_status = "Active"
                        if i % 10 == 0:
                            sector_status = "Proving"
                        elif i % 7 == 0:
                            sector_status = "Sealing"
                        
                        # Store sector information
                        self.sim_cache["sectors"][sector_id] = {
                            "SectorID": sector_id,
                            "SectorNumber": sector_id,
                            "SealedCID": {"/" : f"bafy2bzacea{sector_hash[:40]}"},
                            "DealIDs": [int(sector_hash[:8], 16) % 10000 + i for i in range(3)],
                            "Activation": int(time.time()) - (i * 86400),  # Staggered activation times
                            "Expiration": int(time.time()) + (180 * 86400),  # 180 days in the future
                            "SectorStatus": sector_status
                        }
                
                # Get just the sector numbers for the response
                sector_numbers = list(self.sim_cache["sectors"].keys())
                
                result["success"] = True
                result["simulated"] = True
                result["result"] = sector_numbers
                return result
                
            except Exception as e:
                return handle_error(result, e, f"Error in simulated miner_list_sectors: {str(e)}")
        
        return self._make_miner_request("SectorsList", correlation_id=correlation_id)

    def miner_sector_status(self, sector_number, **kwargs):
        """Get detailed information about a sector.
        
        Args:
            sector_number (int): Sector number to query
            
        Returns:
            dict: Result dictionary with sector status
        """
        operation = "miner_sector_status"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        # If in simulation mode, return simulated sector status
        if self.simulation_mode:
            try:
                # Validate sector number
                if sector_number is None:
                    return handle_error(result, ValueError("Sector number is required"))
                
                # Ensure sectors cache is initialized
                if "sectors" not in self.sim_cache:
                    # Initialize sector cache by calling miner_list_sectors
                    self.miner_list_sectors()
                
                # Check if the sector exists in our simulation cache
                if sector_number in self.sim_cache["sectors"]:
                    # Return the sector information
                    sector_info = self.sim_cache["sectors"][sector_number]
                    
                    # Add additional detailed status information
                    detailed_status = dict(sector_info)
                    
                    # Add activation time
                    if "Activation" in detailed_status:
                        activation_time = detailed_status["Activation"]
                        detailed_status["ActivationEpoch"] = activation_time // 30  # Approximate epoch conversion
                    
                    # Add detailed state information
                    base_status = detailed_status.get("SectorStatus", "Active")
                    detailed_status["State"] = {
                        "Active": 7,       # Proving
                        "Proving": 7,      # Proving
                        "Sealing": 3,      # PreCommit1
                        "Expired": 9,      # Expired
                        "Faulty": 8,       # Faulty
                        "Terminated": 10   # Terminated
                    }.get(base_status, 7)
                    
                    # Add sector size (standard 32GiB)
                    detailed_status["SectorSize"] = 34359738368
                    
                    # Add deal weight info
                    detailed_status["DealWeight"] = "0"
                    detailed_status["VerifiedDealWeight"] = "0"
                    
                    # Add piece info if deals exist
                    if "DealIDs" in detailed_status and detailed_status["DealIDs"]:
                        pieces = []
                        for deal_id in detailed_status["DealIDs"]:
                            # Create deterministic piece info for each deal
                            piece_hash = hashlib.sha256(f"piece_{deal_id}".encode()).hexdigest()
                            piece_size = 1 << (27 + (deal_id % 5))  # Random size between 128MiB and 2GiB
                            pieces.append({
                                "PieceCID": {"/" : f"baga6ea4sea{piece_hash[:40]}"},
                                "DealInfo": {
                                    "DealID": deal_id,
                                    "DealProposal": {
                                        "PieceCID": {"/" : f"baga6ea4sea{piece_hash[:40]}"},
                                        "PieceSize": piece_size,
                                        "VerifiedDeal": bool(deal_id % 2),
                                        "Client": f"t3{piece_hash[:40]}",
                                        "Provider": f"t01{1000 + (deal_id % 100)}",
                                        "StartEpoch": detailed_status.get("ActivationEpoch", 0) - 10,
                                        "EndEpoch": detailed_status.get("Expiration", 0) // 30 + 10,
                                        "StoragePricePerEpoch": "0",
                                        "ProviderCollateral": "0",
                                        "ClientCollateral": "0"
                                    },
                                    "DealState": {
                                        "SectorStartEpoch": detailed_status.get("ActivationEpoch", 0),
                                        "LastUpdatedEpoch": int(time.time()) // 30,
                                        "SlashEpoch": -1
                                    }
                                }
                            })
                        detailed_status["Pieces"] = pieces
                    
                    result["success"] = True
                    result["simulated"] = True
                    result["result"] = detailed_status
                    return result
                else:
                    # Sector not found
                    return handle_error(
                        result, 
                        ValueError(f"Sector {sector_number} not found"), 
                        f"Simulated sector {sector_number} not found"
                    )
                
            except Exception as e:
                return handle_error(result, e, f"Error in simulated miner_sector_status: {str(e)}")
        
        return self._make_miner_request("SectorsStatus", 
                                      params=[sector_number],
                                      correlation_id=correlation_id)
                                      
    def miner_add_storage(self, path, **kwargs):
        """Add a storage path to the miner.
        
        Args:
            path (str): Path to add
            
        Returns:
            dict: Result dictionary with operation result
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        return self._make_miner_request("StorageAddLocal", 
                                      params=[path],
                                      correlation_id=correlation_id)

    def miner_pledge_sector(self, **kwargs):
        """Pledge a sector for the miner (CC sector).
        
        Returns:
            dict: Result dictionary with sector information
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        return self._make_miner_request("PledgeSector", correlation_id=correlation_id)
        
    def miner_compute_window_post(self, deadline, sectors, **kwargs):
        """Compute a WindowPoST proof.
        
        Args:
            deadline (int): Deadline index
            sectors (list): List of sector numbers
            
        Returns:
            dict: Result dictionary with proof information
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        return self._make_miner_request("ComputeWindowPoSt", 
                                      params=[deadline, sectors],
                                      correlation_id=correlation_id)
        
    def miner_check_provable(self, sectors, **kwargs):
        """Check if sectors can be proven successfully.
        
        Args:
            sectors (list): List of sector numbers to check
            
        Returns:
            dict: Result dictionary with provable status
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        return self._make_miner_request("CheckProvable", 
                                      params=[sectors],
                                      correlation_id=correlation_id)
                                      
    def miner_withdraw_balance(self, amount, **kwargs):
        """Withdraw funds from the miner actor.
        
        Args:
            amount (str): Amount to withdraw in FIL
            
        Returns:
            dict: Result dictionary with withdrawal information
        """
        operation = "miner_withdraw_balance"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Get miner address
            addr_result = self._make_miner_request("ActorAddress")
            
            if not addr_result.get("success", False):
                return addr_result
                
            miner_addr = addr_result.get("result")
            
            # Convert amount to attoFIL
            amount_attoFIL = self._parse_fil_amount(amount)
            
            # Call node API to withdraw
            withdraw_result = self._make_request("ActorWithdrawBalance", 
                                              params=[miner_addr, amount_attoFIL],
                                              correlation_id=correlation_id)
            
            return withdraw_result
            
        except Exception as e:
            logger.exception(f"Error withdrawing balance: {str(e)}")
            return handle_error(result, e)
    
    # Metrics Integration
    def metrics_info(self, **kwargs):
        """Get information about available metrics.
        
        Returns:
            dict: Result dictionary with metrics information
        """
        operation = "metrics_info"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Call API endpoint directly since there's no RPC method
            metrics_url = self.api_url.replace("/rpc/v0", "/metrics")
            
            response = requests.get(metrics_url, headers={
                "Authorization": f"Bearer {self.token}" if self.token else ""
            })
            
            # Parse Prometheus format
            metrics = {}
            lines = response.text.split("\n")
            
            current_metric = None
            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                    
                # Format is typically: metric_name{labels} value
                parts = line.split(" ")
                if len(parts) < 2:
                    continue
                    
                metric_full = parts[0]
                value = float(parts[1])
                
                # Extract name and labels
                if "{" in metric_full:
                    metric_name = metric_full[:metric_full.find("{")]
                    labels_str = metric_full[metric_full.find("{")+1:metric_full.find("}")]
                    
                    # Parse labels
                    labels = {}
                    for label_pair in labels_str.split(","):
                        if "=" in label_pair:
                            k, v = label_pair.split("=", 1)
                            labels[k] = v.strip('"')
                            
                    if metric_name not in metrics:
                        metrics[metric_name] = []
                        
                    metrics[metric_name].append({
                        "labels": labels,
                        "value": value
                    })
                else:
                    # Simple metric without labels
                    metrics[metric_full] = value
                    
            result["success"] = True
            result["metrics"] = metrics
            return result
            
        except Exception as e:
            logger.exception(f"Error getting metrics: {str(e)}")
            return handle_error(result, e)
            
    def setup_prometheus_config(self, output_path="prometheus.yml", **kwargs):
        """Generate a Prometheus configuration file for monitoring Lotus.
        
        Args:
            output_path (str): Path to save the configuration file
            
        Returns:
            dict: Result dictionary with setup information
        """
        operation = "setup_prometheus"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Create config with proper endpoint
            api_host = self.api_url.split("://")[1].split("/")[0]
            
            config = f"""
# Prometheus configuration for Lotus monitoring
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: "lotus"
    static_configs:
      - targets: ["{api_host}"]
    metrics_path: /metrics
    scheme: http
    authorization:
      credentials: "{self.token}"
"""

            # Write configuration file
            with open(output_path, "w") as f:
                f.write(config)
                
            result["success"] = True
            result["config_path"] = output_path
            result["message"] = f"Prometheus configuration saved to {output_path}"
            return result
            
        except Exception as e:
            logger.exception(f"Error setting up Prometheus: {str(e)}")
            return handle_error(result, e)
            
    def plot_metrics(self, metric_names, output_path=None, **kwargs):
        """Plot metrics data over time.
        
        Args:
            metric_names (list): List of metric names to plot
            output_path (str, optional): Path to save the plot
            
        Returns:
            dict: Result dictionary with plot information
        """
        operation = "plot_metrics"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Try importing matplotlib
            try:
                import matplotlib.pyplot as plt
            except ImportError:
                return handle_error(
                    result, 
                    ImportError("matplotlib is required for plotting. Install with 'pip install matplotlib'")
                )
                
            # Get metrics data
            metrics_result = self.metrics_info()
            if not metrics_result.get("success", False):
                return metrics_result
                
            metrics = metrics_result.get("metrics", {})
            
            # Plot each requested metric
            plt.figure(figsize=(10, 6))
            
            for metric_name in metric_names:
                if metric_name in metrics:
                    if isinstance(metrics[metric_name], list):
                        # Multiple values with labels
                        for i, item in enumerate(metrics[metric_name]):
                            label = "_".join(f"{k}={v}" for k, v in item.get("labels", {}).items())
                            plt.bar(f"{metric_name}_{label}", item["value"])
                    else:
                        # Single value
                        plt.bar(metric_name, metrics[metric_name])
                        
            plt.title("Lotus Metrics")
            plt.xticks(rotation=45, ha="right")
            plt.tight_layout()
            
            if output_path:
                plt.savefig(output_path)
                result["plot_saved"] = output_path
                
            result["success"] = True
            result["metrics_plotted"] = metric_names
            return result
            
        except Exception as e:
            logger.exception(f"Error plotting metrics: {str(e)}")
            return handle_error(result, e)
            
    def visualize_storage_deals(self, output_path=None, **kwargs):
        """Visualize storage deals in a graphical format.
        
        Creates a visualization of storage deals showing providers, sizes,
        and status of all current deals.
        
        Args:
            output_path (str, optional): Path to save the visualization
            **kwargs: Additional parameters like correlation_id
            
        Returns:
            dict: Result dictionary with visualization status
        """
        operation = "visualize_storage_deals"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Try importing required libraries
            try:
                import matplotlib.pyplot as plt
                import pandas as pd
                import numpy as np
            except ImportError as e:
                missing_lib = str(e).split("'")[1]
                return handle_error(
                    result, 
                    ImportError(f"{missing_lib} is required for visualization. Install with 'pip install {missing_lib}'")
                )
                
            # Get deal information
            deals_result = self.client_list_deals()
            if not deals_result.get("success", False):
                return deals_result
                
            deals = deals_result.get("result", [])
            if not deals:
                result["success"] = True
                result["message"] = "No deals to visualize"
                return result
                
            # Create a DataFrame for easier analysis
            deal_data = []
            for deal in deals:
                deal_data.append({
                    'DealID': deal.get('DealID', 0),
                    'Provider': deal.get('Provider', 'unknown'),
                    'State': deal.get('State', 0),
                    'Status': self._get_deal_state_name(deal.get('State', 0)),
                    'PieceCID': deal.get('PieceCID', {}).get('/', 'unknown'),
                    'Size': deal.get('Size', 0),
                    'PricePerEpoch': deal.get('PricePerEpoch', '0'),
                    'Duration': deal.get('Duration', 0),
                    'StartEpoch': deal.get('StartEpoch', 0),
                    'SlashEpoch': deal.get('SlashEpoch', -1),
                    'Verified': deal.get('Verified', False)
                })
                
            df = pd.DataFrame(deal_data)
            
            # Create visualizations
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 8))
            
            # Plot 1: Deal status distribution
            status_counts = df['Status'].value_counts()
            colors = plt.cm.tab10(np.linspace(0, 1, len(status_counts)))
            status_counts.plot.pie(
                ax=ax1, 
                autopct='%1.1f%%', 
                shadow=True, 
                colors=colors,
                title='Deal Status Distribution'
            )
            ax1.set_ylabel('')
            
            # Plot 2: Storage by provider
            provider_storage = df.groupby('Provider')['Size'].sum().sort_values(ascending=False)
            provider_storage = provider_storage / (1024**3)  # Convert to GiB
            provider_storage.plot.bar(
                ax=ax2,
                color=plt.cm.viridis(np.linspace(0, 1, len(provider_storage))),
                title='Storage by Provider (GiB)'
            )
            ax2.set_ylabel('Storage Size (GiB)')
            ax2.tick_params(axis='x', rotation=45)
            
            plt.tight_layout()
            
            # Save or display the figure
            if output_path:
                plt.savefig(output_path, dpi=300, bbox_inches='tight')
                result["saved_to"] = output_path
                plt.close(fig)
            
            result["success"] = True
            result["deal_count"] = len(df)
            result["storage_summary"] = {
                "total_size_bytes": df['Size'].sum(),
                "total_size_gib": df['Size'].sum() / (1024**3),
                "provider_count": df['Provider'].nunique(),
                "verified_deals": df['Verified'].sum()
            }
            
            return result
            
        except Exception as e:
            logger.exception(f"Error visualizing storage deals: {str(e)}")
            return handle_error(result, e)
            
    def _get_deal_state_name(self, state_code):
        """Convert deal state code to human-readable name.
        
        Args:
            state_code (int): The numeric state code from the API
            
        Returns:
            str: Human-readable state name
        """
        states = {
            0: "Unknown",
            1: "ProposalNotFound",
            2: "ProposalRejected",
            3: "ProposalAccepted",
            4: "Staged",
            5: "Sealing",
            6: "Finalizing",
            7: "Active",
            8: "Expired",
            9: "Slashed",
            10: "Rejecting",
            11: "Failing",
            12: "FundsReserved",
            13: "CheckForAcceptance",
            14: "Validating",
            15: "AcceptWait",
            16: "StartDataTransfer",
            17: "Transferring",
            18: "WaitingForData",
            19: "VerifyData",
            20: "EnsureProviderFunds",
            21: "EnsureClientFunds",
            22: "ProviderFunding",
            23: "ClientFunding",
            24: "Publish",
            25: "Publishing",
            26: "Error",
            27: "Completed"
        }
        return states.get(state_code, f"Unknown({state_code})")
        
    def visualize_network_health(self, output_path=None, **kwargs):
        """Visualize Lotus network health metrics.
        
        Creates a comprehensive dashboard of network health including:
        - Bandwidth usage
        - Peer connections
        - Message pool status
        - Chain sync status
        
        Args:
            output_path (str, optional): Path to save the visualization
            **kwargs: Additional parameters like correlation_id
            
        Returns:
            dict: Result dictionary with visualization status
        """
        operation = "visualize_network_health"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Try importing required libraries
            try:
                import matplotlib.pyplot as plt
                import pandas as pd
                import numpy as np
            except ImportError as e:
                missing_lib = str(e).split("'")[1]
                return handle_error(
                    result, 
                    ImportError(f"{missing_lib} is required for visualization. Install with 'pip install {missing_lib}'")
                )
                
            # Collect metrics data
            metrics_result = self.metrics_info()
            if not metrics_result.get("success", False):
                return metrics_result
                
            metrics = metrics_result.get("metrics", {})
            
            # Get bandwidth information
            bandwidth_result = self.net_bandwidth()
            if not bandwidth_result.get("success", False):
                bandwidth_data = {"TotalIn": 0, "TotalOut": 0, "RateIn": 0, "RateOut": 0}
            else:
                bandwidth_data = bandwidth_result.get("result", {})
                
            # Get peer information
            peers_result = self.net_peers()
            if not peers_result.get("success", False):
                peers = []
            else:
                peers = peers_result.get("result", [])
                
            # Get sync status
            sync_result = self.sync_status()
            if not sync_result.get("success", False):
                sync_data = {"Active": False, "Height": 0}
            else:
                sync_data = sync_result.get("result", {})
                
            # Create visualization
            fig = plt.figure(figsize=(15, 10))
            fig.suptitle('Lotus Network Health Dashboard', fontsize=16)
            
            # Setup grid for multiple plots
            gs = fig.add_gridspec(2, 2, hspace=0.3, wspace=0.3)
            ax1 = fig.add_subplot(gs[0, 0])  # Bandwidth
            ax2 = fig.add_subplot(gs[0, 1])  # Peer count
            ax3 = fig.add_subplot(gs[1, 0])  # Geography
            ax4 = fig.add_subplot(gs[1, 1])  # Sync status
            
            # 1. Bandwidth graph
            total_in = bandwidth_data.get("TotalIn", 0) / (1024**2)  # Convert to MiB
            total_out = bandwidth_data.get("TotalOut", 0) / (1024**2)
            rate_in = bandwidth_data.get("RateIn", 0) / 1024  # Convert to KiB/s
            rate_out = bandwidth_data.get("RateOut", 0) / 1024
            
            bandwidth_labels = ['Total In (MiB)', 'Total Out (MiB)', 'Rate In (KiB/s)', 'Rate Out (KiB/s)']
            bandwidth_values = [total_in, total_out, rate_in, rate_out]
            
            ax1.bar(bandwidth_labels, bandwidth_values, color=['green', 'blue', 'lightgreen', 'lightblue'])
            ax1.set_title('Bandwidth Usage')
            ax1.set_ylabel('Value')
            ax1.tick_params(axis='x', rotation=30)
            
            # 2. Peer count
            ax2.pie([len(peers)], labels=['Connected Peers'], autopct='%1.0f', 
                    startangle=90, colors=['lightblue'], wedgeprops={'width': 0.3})
            ax2.text(0, 0, str(len(peers)), ha='center', va='center', fontsize=24)
            ax2.set_title('Peer Connections')
            
            # 3. Geographic distribution (Mocked - would need IP geolocation)
            geolocation = {'North America': 40, 'Europe': 30, 'Asia': 20, 'Other': 10}
            ax3.pie(geolocation.values(), labels=geolocation.keys(), autopct='%1.1f%%',
                    startangle=90, colors=plt.cm.Paired(np.linspace(0, 1, len(geolocation))))
            ax3.set_title('Estimated Peer Geography')
            
            # 4. Sync status
            active = sync_data.get("Active", False)
            height = sync_data.get("Height", 0)
            sync_state = "In Progress" if active else "Up to Date"
            
            # Create status indicator
            status_color = 'orange' if active else 'green'
            ax4.text(0.5, 0.5, sync_state, ha='center', va='center', fontsize=20,
                     bbox=dict(boxstyle='round', facecolor=status_color, alpha=0.3))
            ax4.text(0.5, 0.3, f"Height: {height}", ha='center', va='center', fontsize=14)
            ax4.axis('off')
            ax4.set_title('Chain Sync Status')
            
            plt.tight_layout(rect=[0, 0, 1, 0.95])  # Adjust for title
            
            # Save or display the figure
            if output_path:
                plt.savefig(output_path, dpi=300, bbox_inches='tight')
                result["saved_to"] = output_path
                plt.close(fig)
            
            result["success"] = True
            result["network_summary"] = {
                "peer_count": len(peers),
                "sync_status": sync_state,
                "chain_height": height,
                "bandwidth_in_mib": total_in,
                "bandwidth_out_mib": total_out
            }
            
            return result
            
        except Exception as e:
            logger.exception(f"Error visualizing network health: {str(e)}")
            return handle_error(result, e)
            
    def validate_export_format(self, format, supported_formats=None):
        """Validate the export format and provide fallback if needed.
        
        Args:
            format (str): The requested export format (e.g., 'json', 'csv')
            supported_formats (list, optional): List of supported formats
                                               Default: ['json', 'csv']
        
        Returns:
            tuple: (valid_format, error_message)
                valid_format is None if format is invalid
                error_message is None if format is valid
        """
        if supported_formats is None:
            supported_formats = ['json', 'csv']
            
        format = format.lower() if format else 'json'
        
        if format not in supported_formats:
            error_msg = (f"Unsupported format: {format}. "
                        f"Supported formats: {', '.join(supported_formats)}")
            return None, error_msg
            
        return format, None
        
    def format_bytes(self, size_bytes):
        """Format bytes value to human-readable string with appropriate unit.
        
        Args:
            size_bytes (int): Size in bytes
            
        Returns:
            str: Formatted string (e.g., "1.23 GiB")
        """
        if size_bytes == 0:
            return "0 B"
            
        units = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB']
        i = 0
        while size_bytes >= 1024 and i < len(units) - 1:
            size_bytes /= 1024.0
            i += 1
            
        return f"{size_bytes:.2f} {units[i]}"
        
    def format_timestamp(self, timestamp, format_str=None):
        """Format Unix timestamp to human-readable date format.
        
        Args:
            timestamp (float): Unix timestamp
            format_str (str, optional): Custom strftime format
                                        Default: "%Y-%m-%d %H:%M:%S"
                                        
        Returns:
            str: Formatted timestamp
        """
        import datetime
        
        if format_str is None:
            format_str = "%Y-%m-%d %H:%M:%S"
            
        try:
            # Handle different timestamp formats (seconds vs milliseconds)
            if timestamp > 1e11:  # Likely milliseconds
                timestamp = timestamp / 1000
                
            dt = datetime.datetime.fromtimestamp(timestamp)
            return dt.strftime(format_str)
        except (ValueError, TypeError, OverflowError):
            return "Invalid timestamp"
            
    def parse_wallet_data(self, data, format_type=None):
        """Parse wallet data from different formats.
        
        Args:
            data (str): Wallet data string
            format_type (str, optional): Format type hint ('json', 'key', 'hex')
                                        If None, tries to auto-detect
        
        Returns:
            dict: Parsed wallet data or None if parsing fails
        """
        if not data:
            return None
            
        # Try to determine format if not provided
        if format_type is None:
            # Check if it's JSON
            if data.strip().startswith('{') and data.strip().endswith('}'):
                format_type = 'json'
            # Check if it's a hex string (64 hex chars)
            elif re.match(r'^[0-9a-fA-F]{64}$', data.strip()):
                format_type = 'hex'
            # Check if it's a key file format (multiline with headers)
            elif 'Type:' in data and 'PrivateKey:' in data:
                format_type = 'key'
            else:
                # Default to treating as a private key
                format_type = 'hex'
                
        wallet_data = {}
        
        try:
            if format_type == 'json':
                # Parse JSON format
                import json
                wallet_json = json.loads(data)
                wallet_data = {
                    'type': wallet_json.get('Type', 'unknown'),
                    'private_key': wallet_json.get('PrivateKey', ''),
                    'address': wallet_json.get('Address', ''),
                }
            elif format_type == 'key':
                # Parse key file format
                lines = data.strip().split('\n')
                for line in lines:
                    if ':' in line:
                        key, value = line.split(':', 1)
                        key = key.strip().lower()
                        value = value.strip()
                        
                        if key == 'type':
                            wallet_data['type'] = value
                        elif key == 'privatekey':
                            wallet_data['private_key'] = value
                        elif key == 'address':
                            wallet_data['address'] = value
            elif format_type == 'hex':
                # Treat as a raw hex private key
                wallet_data = {
                    'type': 'secp256k1',  # Default to secp256k1
                    'private_key': data.strip(),
                }
        except Exception:
            return None
            
        return wallet_data
        
    def validate_filepath(self, path, must_exist=False, check_writeable=False):
        """Validate file path and check permissions.
        
        Args:
            path (str): File path to validate
            must_exist (bool): Whether the file must already exist
            check_writeable (bool): Whether to check if path is writeable
            
        Returns:
            tuple: (is_valid, error_message)
                is_valid is False if validation fails
                error_message is None if validation succeeds
        """
        if not path:
            return False, "File path cannot be empty"
            
        try:
            # Convert to absolute path and normalize
            abs_path = os.path.abspath(os.path.expanduser(path))
            
            # Check if file exists (if required)
            if must_exist and not os.path.exists(abs_path):
                return False, f"File does not exist: {abs_path}"
                
            # Check if directory exists for writing
            if check_writeable:
                dir_path = os.path.dirname(abs_path)
                
                # Create directory if it doesn't exist
                if not os.path.exists(dir_path):
                    try:
                        os.makedirs(dir_path, exist_ok=True)
                    except Exception as e:
                        return False, f"Cannot create directory {dir_path}: {str(e)}"
                
                # Check if we can write to the directory
                if not os.access(dir_path, os.W_OK):
                    return False, f"Directory not writeable: {dir_path}"
                    
            return True, None
            
        except Exception as e:
            return False, f"Invalid file path: {str(e)}"
            
    def export_data_to_json(self, data, output_path, pretty=True):
        """Export data to a JSON file.
        
        Args:
            data: Data to export (must be JSON serializable)
            output_path (str): Path to save the JSON file
            pretty (bool): Whether to format JSON for readability
            
        Returns:
            dict: Result with success status and error message if any
        """
        result = {
            "success": False,
            "operation": "export_data_to_json",
            "timestamp": time.time()
        }
        
        try:
            import json
            
            # Validate output path
            is_valid, error_msg = self.validate_filepath(output_path, must_exist=False, check_writeable=True)
            if not is_valid:
                result["error"] = error_msg
                return result
                
            # Create directory if it doesn't exist
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
                
            # Write JSON data
            with open(output_path, 'w') as f:
                if pretty:
                    json.dump(data, f, indent=2, sort_keys=True)
                else:
                    json.dump(data, f)
                    
            result["success"] = True
            result["file_path"] = output_path
            result["file_size"] = os.path.getsize(output_path)
            
            return result
            
        except Exception as e:
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            return result
            
    def export_data_to_csv(self, data, output_path, headers=None):
        """Export data to a CSV file.
        
        Args:
            data (list): List of dictionaries or list of lists
            output_path (str): Path to save the CSV file
            headers (list, optional): List of column headers
                If None, tries to extract from data
            
        Returns:
            dict: Result with success status and error message if any
        """
        result = {
            "success": False,
            "operation": "export_data_to_csv",
            "timestamp": time.time()
        }
        
        try:
            import csv
            
            # Validate output path
            is_valid, error_msg = self.validate_filepath(output_path, must_exist=False, check_writeable=True)
            if not is_valid:
                result["error"] = error_msg
                return result
                
            # Create directory if it doesn't exist
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
                
            # Handle different data formats
            if not data:
                # Empty data, create empty file with headers
                with open(output_path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    if headers:
                        writer.writerow(headers)
                        
                result["success"] = True
                result["row_count"] = 0
                result["file_path"] = output_path
                return result
                
            # Determine if data is list of dicts or list of lists
            first_item = data[0] if data else None
            is_dict_format = isinstance(first_item, dict)
            
            with open(output_path, 'w', newline='') as f:
                if is_dict_format:
                    # Auto-detect headers if not provided
                    if headers is None:
                        headers = list(first_item.keys())
                        
                    writer = csv.DictWriter(f, fieldnames=headers)
                    writer.writeheader()
                    
                    # Write only fields in headers
                    filtered_data = []
                    for row in data:
                        filtered_row = {k: row.get(k, '') for k in headers}
                        filtered_data.append(filtered_row)
                        
                    writer.writerows(filtered_data)
                    
                else:
                    writer = csv.writer(f)
                    
                    # Write headers if provided
                    if headers:
                        writer.writerow(headers)
                        
                    # Write data rows
                    writer.writerows(data)
                    
            result["success"] = True
            result["row_count"] = len(data)
            result["file_path"] = output_path
            result["file_size"] = os.path.getsize(output_path)
            
            return result
            
        except Exception as e:
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            return result
            
    def batch_process_with_throttle(self, items, process_func, batch_size=10, 
                                   delay_seconds=0.5, max_retries=3, **kwargs):
        """Process items in batches with throttling and retries.
        
        Useful for API operations that need rate limiting.
        
        Args:
            items (list): Items to process
            process_func (callable): Function to process each item
            batch_size (int): Number of items to process in each batch
            delay_seconds (float): Delay between batches in seconds
            max_retries (int): Maximum number of retries for failed items
            **kwargs: Additional arguments to pass to process_func
            
        Returns:
            dict: Results of processing with success/failure counts
        """
        result = {
            "success": True,
            "operation": "batch_process",
            "timestamp": time.time(),
            "total_items": len(items),
            "successful": 0,
            "failed": 0,
            "retried": 0,
            "results": []
        }
        
        try:
            # Process in batches
            for i in range(0, len(items), batch_size):
                batch = items[i:i+batch_size]
                
                # Process each item in batch
                for item in batch:
                    retry_count = 0
                    success = False
                    
                    # Try with retries
                    while not success and retry_count <= max_retries:
                        try:
                            item_result = process_func(item, **kwargs)
                            success = item_result.get("success", False)
                            
                            if success:
                                result["successful"] += 1
                            else:
                                if retry_count < max_retries:
                                    # Will retry
                                    retry_count += 1
                                    result["retried"] += 1
                                    time.sleep(delay_seconds * (2 ** retry_count))  # Exponential backoff
                                else:
                                    # Max retries reached
                                    result["failed"] += 1
                                    
                            # Store final result (after retries)
                            if retry_count == max_retries or success:
                                if "retry_count" not in item_result:
                                    item_result["retry_count"] = retry_count
                                result["results"].append(item_result)
                                
                        except Exception as e:
                            if retry_count < max_retries:
                                # Will retry
                                retry_count += 1
                                result["retried"] += 1
                                time.sleep(delay_seconds * (2 ** retry_count))  # Exponential backoff
                            else:
                                # Max retries reached, log error
                                result["failed"] += 1
                                result["results"].append({
                                    "success": False,
                                    "error": str(e),
                                    "error_type": type(e).__name__,
                                    "retry_count": retry_count
                                })
                                
                # Delay between batches
                if i + batch_size < len(items):
                    time.sleep(delay_seconds)
                    
            # Update overall status
            result["success"] = result["failed"] == 0
            
            return result
            
        except Exception as e:
            logger.exception(f"Error in batch processing: {str(e)}")
            result["success"] = False
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            return result
            
    def analyze_chain_data(self, tipsets, **kwargs):
        """Analyze chain data for detailed statistics and patterns.
        
        Args:
            tipsets (list): List of tipset data from chain traversal
            **kwargs: Additional analysis parameters
            
        Returns:
            dict: Analysis results with statistics and patterns
        """
        analysis = {
            "blocks_analyzed": 0,
            "messages_analyzed": 0,
            "timespan": {
                "start_height": None,
                "end_height": None,
                "start_time": None,
                "end_time": None,
                "duration_hours": None
            },
            "miners": {},
            "message_stats": {
                "by_method": {},
                "by_actor_type": {},
                "gas_usage": {
                    "total": 0,
                    "average": 0,
                    "min": float('inf'),
                    "max": 0
                }
            },
            "address_activity": {},
            "value_transfers": {
                "total": 0,
                "average": 0,
                "max": 0,
                "min": float('inf')
            }
        }
        
        if not tipsets:
            return analysis
            
        # Set initial timespan values
        analysis["timespan"]["start_height"] = tipsets[-1]["Height"]
        analysis["timespan"]["end_height"] = tipsets[0]["Height"]
        analysis["timespan"]["start_time"] = tipsets[-1]["Timestamp"]
        analysis["timespan"]["end_time"] = tipsets[0]["Timestamp"]
        
        # Calculate duration in hours
        time_diff = analysis["timespan"]["end_time"] - analysis["timespan"]["start_time"]
        analysis["timespan"]["duration_hours"] = time_diff / 3600 if time_diff else 0
        
        total_gas = 0
        total_value = 0
        value_count = 0
        
        # Process each tipset
        for tipset in tipsets:
            height = tipset.get("Height", 0)
            blocks = tipset.get("Blocks", [])
            analysis["blocks_analyzed"] += len(blocks)
            
            # Analyze blocks (miner distribution)
            for block in blocks:
                miner = block.get("Miner", "")
                if miner:
                    if miner not in analysis["miners"]:
                        analysis["miners"][miner] = {
                            "blocks": 0,
                            "win_count": 0,
                            "messages_included": 0
                        }
                    analysis["miners"][miner]["blocks"] += 1
                    analysis["miners"][miner]["win_count"] += 1
            
            # Process messages
            messages = tipset.get("Messages", [])
            analysis["messages_analyzed"] += len(messages)
            
            for msg in messages:
                # Track gas usage
                gas_used = msg.get("GasUsed", 0)
                total_gas += gas_used
                
                analysis["message_stats"]["gas_usage"]["min"] = min(
                    analysis["message_stats"]["gas_usage"]["min"], gas_used)
                analysis["message_stats"]["gas_usage"]["max"] = max(
                    analysis["message_stats"]["gas_usage"]["max"], gas_used)
                
                # Track method invocations
                method = msg.get("Method", "unknown")
                if method not in analysis["message_stats"]["by_method"]:
                    analysis["message_stats"]["by_method"][method] = 0
                analysis["message_stats"]["by_method"][method] += 1
                
                # Track actor types
                actor_type = self._get_actor_type(msg.get("To", ""))
                if actor_type not in analysis["message_stats"]["by_actor_type"]:
                    analysis["message_stats"]["by_actor_type"][actor_type] = 0
                analysis["message_stats"]["by_actor_type"][actor_type] += 1
                
                # Track address interactions
                from_addr = msg.get("From", "")
                to_addr = msg.get("To", "")
                
                for addr in (from_addr, to_addr):
                    if addr:
                        if addr not in analysis["address_activity"]:
                            analysis["address_activity"][addr] = {
                                "sent": 0,
                                "received": 0,
                                "value_sent": 0,
                                "value_received": 0
                            }
                
                if from_addr:
                    analysis["address_activity"][from_addr]["sent"] += 1
                    
                if to_addr:
                    analysis["address_activity"][to_addr]["received"] += 1
                
                # Track value transfers
                value = int(msg.get("Value", "0"))
                if value > 0:
                    total_value += value
                    value_count += 1
                    
                    analysis["value_transfers"]["min"] = min(
                        analysis["value_transfers"]["min"], value)
                    analysis["value_transfers"]["max"] = max(
                        analysis["value_transfers"]["max"], value)
                    
                    if from_addr:
                        analysis["address_activity"][from_addr]["value_sent"] += value
                    if to_addr:
                        analysis["address_activity"][to_addr]["value_received"] += value
        
        # Calculate averages
        if analysis["messages_analyzed"] > 0:
            analysis["message_stats"]["gas_usage"]["average"] = total_gas / analysis["messages_analyzed"]
            
        if value_count > 0:
            analysis["value_transfers"]["average"] = total_value / value_count
            analysis["value_transfers"]["total"] = total_value
        
        # Fix min values if no values were found
        if analysis["message_stats"]["gas_usage"]["min"] == float('inf'):
            analysis["message_stats"]["gas_usage"]["min"] = 0
            
        if analysis["value_transfers"]["min"] == float('inf'):
            analysis["value_transfers"]["min"] = 0
            
        # Add miner ranking
        miner_list = [(miner, data["blocks"]) for miner, data in analysis["miners"].items()]
        miner_list.sort(key=lambda x: x[1], reverse=True)
        analysis["top_miners"] = [{"miner": m, "blocks": c} for m, c in miner_list[:10]]
        
        # Add active address ranking
        address_activity = []
        for addr, data in analysis["address_activity"].items():
            activity_score = data["sent"] + data["received"]
            address_activity.append((addr, activity_score, data))
            
        address_activity.sort(key=lambda x: x[1], reverse=True)
        analysis["most_active_addresses"] = [
            {"address": a, "activity": s, "details": d} 
            for a, s, d in address_activity[:10]
        ]
        
        return analysis
        
    def _get_actor_type(self, address):
        """Determine actor type from address.
        
        Args:
            address (str): Filecoin address
            
        Returns:
            str: Actor type or 'unknown'
        """
        if not address:
            return "unknown"
            
        # Common actor prefixes
        known_patterns = {
            "f01": "system",
            "f02": "miner",
            "f03": "multisig",
            "f04": "init",
            "f05": "reward",
            "f099": "burnt_funds"
        }
        
        # Check for exact matches or patterns
        for prefix, actor_type in known_patterns.items():
            if address.startswith(prefix):
                return actor_type
                
        # Default categorization based on address prefix
        if address.startswith("f0"):
            return "builtin"
        elif address.startswith("f1"):
            return "account"
        elif address.startswith("f2"):
            return "contract"
        elif address.startswith("f3"):
            return "multisig"
        else:
            return "unknown"
            
    # Monitoring methods
    def monitor_start(self, **kwargs):
        """Start the monitoring service for Lotus daemon.
        
        This method starts the platform-specific monitoring service for the 
        Lotus daemon. On macOS, it starts the LotusMonitor service.
        
        Args:
            **kwargs: Additional arguments for monitor configuration
                - interval: Monitoring interval in seconds
                - auto_restart: Whether to automatically restart crashed daemons
                - report_path: Path to store monitoring reports
                - notification_config: Configuration for monitoring notifications
                - correlation_id: ID for tracking operations
                
        Returns:
            dict: Result dictionary with operation outcome
        """
        operation = "lotus_monitor_start"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Get the platform-specific monitor
            monitor = self.monitor
            
            if monitor is None:
                result["success"] = False
                result["error"] = f"No monitor available for platform: {platform.system()}"
                return result
                
            # Start the monitoring service
            monitor_result = monitor.start_monitoring(**kwargs)
            
            # Update our result with the monitor's result
            result.update(monitor_result)
            
            # Log the result
            if result.get("success", False):
                logger.info(f"Lotus monitor started successfully: {result.get('status', 'running')}")
            else:
                logger.error(f"Failed to start Lotus monitor: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            result = handle_error(result, e, f"Failed to start Lotus monitoring: {str(e)}")
            logger.error(f"Error in monitor_start: {str(e)}", exc_info=True)
            
        return result
        
    def monitor_stop(self, **kwargs):
        """Stop the monitoring service for Lotus daemon.
        
        This method stops the platform-specific monitoring service for the
        Lotus daemon.
        
        Args:
            **kwargs: Additional arguments for stopping the monitor
                - correlation_id: ID for tracking operations
                
        Returns:
            dict: Result dictionary with operation outcome
        """
        operation = "lotus_monitor_stop"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Get the platform-specific monitor
            monitor = self.monitor
            
            if monitor is None:
                result["success"] = False
                result["error"] = f"No monitor available for platform: {platform.system()}"
                return result
                
            # Stop the monitoring service
            monitor_result = monitor.stop_monitoring(**kwargs)
            
            # Update our result with the monitor's result
            result.update(monitor_result)
            
            # Log the result
            if result.get("success", False):
                logger.info(f"Lotus monitor stopped successfully: {result.get('message', '')}")
            else:
                logger.error(f"Failed to stop Lotus monitor: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            result = handle_error(result, e, f"Failed to stop Lotus monitoring: {str(e)}")
            logger.error(f"Error in monitor_stop: {str(e)}", exc_info=True)
            
        return result
        
    def monitor_status(self, **kwargs):
        """Get the status of the Lotus daemon monitoring service.
        
        This method queries the platform-specific monitoring service to get
        the current status of the Lotus daemon.
        
        Args:
            **kwargs: Additional arguments for status query
                - detailed: Whether to return detailed status information
                - correlation_id: ID for tracking operations
                
        Returns:
            dict: Result dictionary with operation outcome and status info
        """
        operation = "lotus_monitor_status"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Get the platform-specific monitor
            monitor = self.monitor
            
            if monitor is None:
                result["success"] = False
                result["error"] = f"No monitor available for platform: {platform.system()}"
                return result
                
            # Get monitor status
            monitor_result = monitor.get_status(**kwargs)
            
            # Update our result with the monitor's result
            result.update(monitor_result)
            
            # Log the result
            if result.get("success", False):
                logger.debug(f"Retrieved Lotus monitor status: {result.get('status', 'unknown')}")
            else:
                logger.error(f"Failed to get Lotus monitor status: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            result = handle_error(result, e, f"Failed to get Lotus monitoring status: {str(e)}")
            logger.error(f"Error in monitor_status: {str(e)}", exc_info=True)
            
        return result
        
    def monitor_optimize(self, **kwargs):
        """Optimize the Lotus daemon configuration for the current platform.
        
        This method uses the platform-specific monitoring tool to optimize
        the Lotus daemon configuration for better performance and reliability.
        
        Args:
            **kwargs: Additional arguments for optimization
                - targets: List of optimization targets (e.g., ["memory", "cpu", "disk"])
                - aggressive: Whether to use aggressive optimization settings
                - correlation_id: ID for tracking operations
                
        Returns:
            dict: Result dictionary with operation outcome and optimization details
        """
        operation = "lotus_monitor_optimize"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Get the platform-specific monitor
            monitor = self.monitor
            
            if monitor is None:
                result["success"] = False
                result["error"] = f"No monitor available for platform: {platform.system()}"
                return result
                
            # Run optimization
            monitor_result = monitor.optimize(**kwargs)
            
            # Update our result with the monitor's result
            result.update(monitor_result)
            
            # Log the result
            if result.get("success", False):
                logger.info(f"Lotus daemon optimization completed: {result.get('message', '')}")
            else:
                logger.error(f"Failed to optimize Lotus daemon: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            result = handle_error(result, e, f"Failed to optimize Lotus daemon: {str(e)}")
            logger.error(f"Error in monitor_optimize: {str(e)}", exc_info=True)
            
        return result
        
    def monitor_report(self, **kwargs):
        """Generate a performance and health report for the Lotus daemon.
        
        This method uses the platform-specific monitoring tool to generate
        a comprehensive report about the Lotus daemon's performance and health.
        
        Args:
            **kwargs: Additional arguments for report generation
                - format: Report format (e.g., "json", "text", "html")
                - period: Period to report on (e.g., "day", "week", "month")
                - output_path: Where to save the report
                - correlation_id: ID for tracking operations
                
        Returns:
            dict: Result dictionary with operation outcome and report data
        """
        operation = "lotus_monitor_report"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Get the platform-specific monitor
            monitor = self.monitor
            
            if monitor is None:
                result["success"] = False
                result["error"] = f"No monitor available for platform: {platform.system()}"
                return result
                
            # Generate report
            monitor_result = monitor.generate_report(**kwargs)
            
            # Update our result with the monitor's result
            result.update(monitor_result)
            
            # Log the result
            if result.get("success", False):
                logger.info(f"Lotus daemon report generated: {result.get('report_path', '')}")
            else:
                logger.error(f"Failed to generate Lotus daemon report: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            result = handle_error(result, e, f"Failed to generate Lotus daemon report: {str(e)}")
            logger.error(f"Error in monitor_report: {str(e)}", exc_info=True)
            
        return result
