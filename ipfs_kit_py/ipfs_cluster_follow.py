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
import anyio
from typing import Dict, Any, Optional

# Import our API clients
try:
    from ipfs_kit_py.ipfs_cluster_api import IPFSClusterFollowAPIClient, IPFSClusterFollowCTLWrapper
except ImportError:
    # Create stub classes if import fails
    class IPFSClusterFollowAPIClient:
        def __init__(self, *args, **kwargs):
            pass
    class IPFSClusterFollowCTLWrapper:
        def __init__(self, *args, **kwargs):
            pass

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
            
            # Configuration file paths
            self.service_config_path = os.path.join(self.ipfs_cluster_path, "service.json")
            self.identity_path = os.path.join(self.ipfs_cluster_path, "identity.json")
            self.cluster_config_path = os.path.join(self.ipfs_cluster_path, "cluster.json")
            
            # Default ports for cluster follow
            self.api_port = 9097
            self.proxy_port = 9098

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
    
    def config_create(self, cluster_name: Optional[str] = None, bootstrap_peer: Optional[str] = None, 
                     overwrite: bool = False, **custom_settings) -> Dict[str, Any]:
        """Create and configure IPFS Cluster Follow configuration.
        
        Args:
            cluster_name: Name of the cluster to follow
            bootstrap_peer: Bootstrap peer multiaddress
            overwrite: Whether to overwrite existing configuration
            **custom_settings: Custom configuration settings to apply
            
        Returns:
            Dict with configuration creation results
        """
        result = {
            "success": False,
            "config_created": False,
            "identity_created": False,
            "service_config": {},
            "identity_config": {},
            "cluster_config": {},
            "errors": []
        }
        
        try:
            # Use provided cluster name or default
            cluster_name = cluster_name or self.cluster_name or "default"
            
            # Check if config already exists
            if os.path.exists(self.service_config_path) and not overwrite:
                result["errors"].append("Configuration already exists. Use overwrite=True to replace.")
                return result
            
            # Ensure directory exists
            os.makedirs(self.ipfs_cluster_path, exist_ok=True)
            
            # Generate identity configuration
            identity_result = self._generate_follow_identity_config()
            if not identity_result["success"]:
                result["errors"].extend(identity_result["errors"])
                return result
            
            result["identity_created"] = True
            result["identity_config"] = identity_result["identity"]
            
            # Generate service configuration
            service_result = self._generate_follow_service_config(
                identity_result["identity"], cluster_name, bootstrap_peer, **custom_settings
            )
            if not service_result["success"]:
                result["errors"].extend(service_result["errors"])
                return result
            
            result["config_created"] = True
            result["service_config"] = service_result["config"]
            
            # Generate cluster-specific configuration
            cluster_result = self._generate_follow_cluster_config(cluster_name, bootstrap_peer)
            if cluster_result["success"]:
                result["cluster_config"] = cluster_result["config"]
            
            result["success"] = True
            
            logger.info(f"IPFS Cluster Follow configuration created for cluster: {cluster_name}")
            
        except Exception as e:
            result["errors"].append(f"Configuration creation error: {str(e)}")
            logger.error(f"Failed to create cluster follow configuration: {e}")
            
        return result
    
    def config_get(self) -> Dict[str, Any]:
        """Retrieve current IPFS Cluster Follow configuration.
        
        Returns:
            Dict with current configuration
        """
        result = {
            "success": False,
            "config_exists": False,
            "service_config": {},
            "identity_config": {},
            "cluster_config": {},
            "errors": []
        }
        
        try:
            # Check if configuration exists
            if not os.path.exists(self.service_config_path):
                result["errors"].append("Service configuration file not found")
                return result
            
            # Load service configuration
            with open(self.service_config_path, 'r') as f:
                result["service_config"] = json.load(f)
            
            # Load identity configuration if it exists
            if os.path.exists(self.identity_path):
                with open(self.identity_path, 'r') as f:
                    result["identity_config"] = json.load(f)
            
            # Load cluster configuration if it exists
            if os.path.exists(self.cluster_config_path):
                with open(self.cluster_config_path, 'r') as f:
                    result["cluster_config"] = json.load(f)
            
            result["config_exists"] = True
            result["success"] = True
            
        except Exception as e:
            result["errors"].append(f"Configuration retrieval error: {str(e)}")
            logger.error(f"Failed to retrieve cluster follow configuration: {e}")
            
        return result
    
    def config_set(self, config_updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update IPFS Cluster Follow configuration with new settings.
        
        Args:
            config_updates: Dictionary of configuration updates
            
        Returns:
            Dict with update results
        """
        result = {
            "success": False,
            "config_updated": False,
            "updated_config": {},
            "errors": []
        }
        
        try:
            # Load current configuration
            current_config = self.config_get()
            if not current_config["success"]:
                result["errors"].append("Cannot update configuration: current config not found")
                return result
            
            # Merge updates
            service_config = current_config["service_config"]
            self._deep_merge_config(service_config, config_updates)
            
            # Validate updated configuration
            validation_result = self._validate_follow_service_config(service_config)
            if not validation_result["valid"]:
                result["errors"].extend(validation_result["errors"])
                return result
            
            # Save updated configuration
            with open(self.service_config_path, 'w') as f:
                json.dump(service_config, f, indent=2)
            
            result["config_updated"] = True
            result["updated_config"] = service_config
            result["success"] = True
            
            logger.info("IPFS Cluster Follow configuration updated successfully")
            
        except Exception as e:
            result["errors"].append(f"Configuration update error: {str(e)}")
            logger.error(f"Failed to update cluster follow configuration: {e}")
            
        return result
    
    def _generate_follow_identity_config(self) -> Dict[str, Any]:
        """Generate identity configuration for cluster follow.
        
        Returns:
            Dict with identity generation results
        """
        result = {
            "success": False,
            "identity": {},
            "errors": []
        }
        
        try:
            import hashlib
            import secrets
            from base64 import b64encode
            
            # Generate peer ID (simplified)
            peer_key = secrets.token_bytes(32)
            peer_id = "12D3KooW" + hashlib.sha256(peer_key).hexdigest()[:50]
            
            # Generate private key (placeholder)
            private_key = b64encode(secrets.token_bytes(64)).decode('utf-8')
            
            identity = {
                "id": peer_id,
                "private_key": private_key,
                "addresses": [
                    f"/ip4/127.0.0.1/tcp/9096/p2p/{peer_id}",
                    f"/ip4/0.0.0.0/tcp/9096/p2p/{peer_id}"
                ]
            }
            
            # Save identity
            with open(self.identity_path, 'w') as f:
                json.dump(identity, f, indent=2)
            
            result["identity"] = identity
            result["success"] = True
            
        except Exception as e:
            result["errors"].append(f"Identity generation error: {str(e)}")
            
        return result
    
    def _generate_follow_service_config(self, identity: Dict[str, Any], cluster_name: str, 
                                       bootstrap_peer: Optional[str] = None, **custom_settings) -> Dict[str, Any]:
        """Generate service configuration for cluster follow.
        
        Args:
            identity: Identity configuration
            cluster_name: Name of the cluster to follow
            bootstrap_peer: Bootstrap peer multiaddress
            **custom_settings: Custom settings to apply
            
        Returns:
            Dict with service config generation results
        """
        result = {
            "success": False,
            "config": {},
            "errors": []
        }
        
        try:
            # Default service configuration for cluster follow
            config = {
                "id": identity["id"],
                "cluster_name": cluster_name,
                "cluster": {
                    "secret": "",  # Will be set by bootstrap peer
                    "peers": [],
                    "bootstrap": [bootstrap_peer] if bootstrap_peer else [],
                    "leave_on_shutdown": True,
                    "listen_multiaddress": "/ip4/0.0.0.0/tcp/9096",
                    "state_sync_interval": "10s",
                    "ipfs_sync_interval": "130s",
                    "replication_factor_min": 1,
                    "replication_factor_max": 3,
                    "monitor_ping_interval": "15s"
                },
                "api": {
                    "restapi": {
                        "listen_multiaddress": f"/ip4/127.0.0.1/tcp/{self.api_port}",
                        "read_timeout": "0s",
                        "read_header_timeout": "5s",
                        "write_timeout": "0s",
                        "idle_timeout": "120s",
                        "max_header_bytes": 4096,
                        "cors_allowed_origins": ["*"],
                        "cors_allowed_methods": ["GET", "POST"],
                        "cors_allowed_headers": ["*"],
                        "cors_exposed_headers": ["*"],
                        "cors_allow_credentials": True,
                        "cors_max_age": "0s"
                    },
                    "ipfsproxy": {
                        "listen_multiaddress": f"/ip4/127.0.0.1/tcp/{self.proxy_port}",
                        "node_multiaddress": "/ip4/127.0.0.1/tcp/5001",
                        "read_timeout": "0s",
                        "read_header_timeout": "5s",
                        "write_timeout": "0s",
                        "idle_timeout": "60s",
                        "max_header_bytes": 4096
                    }
                },
                "ipfs_connector": {
                    "ipfshttp": {
                        "node_multiaddress": "/ip4/127.0.0.1/tcp/5001",
                        "connect_swarms_delay": "30s",
                        "ipfs_request_timeout": "5m",
                        "pin_timeout": "2m",
                        "unpin_timeout": "3m"
                    }
                },
                "pin_tracker": {
                    "stateless": {
                        "concurrent_pins": 10,
                        "priority_pin_max_age": "24h",
                        "priority_pin_max_retries": 5
                    }
                },
                "monitor": {
                    "pubsubmon": {
                        "check_interval": "15s",
                        "failure_threshold": 3
                    }
                },
                "informer": {
                    "disk": {
                        "metric_ttl": "30s",
                        "metric_type": "freespace"
                    },
                    "tags": {
                        "metric_ttl": "30s",
                        "tags": {"group": "follower", "cluster": cluster_name}
                    }
                }
            }
            
            # Apply custom settings
            self._deep_merge_config(config, custom_settings)
            
            # Save configuration
            with open(self.service_config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            result["config"] = config
            result["success"] = True
            
        except Exception as e:
            result["errors"].append(f"Service config generation error: {str(e)}")
            
        return result
    
    def _generate_follow_cluster_config(self, cluster_name: str, bootstrap_peer: Optional[str] = None) -> Dict[str, Any]:
        """Generate cluster-specific configuration for follow service.
        
        Args:
            cluster_name: Name of the cluster to follow
            bootstrap_peer: Bootstrap peer multiaddress
            
        Returns:
            Dict with cluster config generation results
        """
        result = {
            "success": False,
            "config": {},
            "errors": []
        }
        
        try:
            cluster_config = {
                "cluster_name": cluster_name,
                "bootstrap_peer": bootstrap_peer,
                "follow_mode": True,
                "role": self.role,
                "created_at": time.time(),
                "config_version": "1.0"
            }
            
            # Save cluster configuration
            with open(self.cluster_config_path, 'w') as f:
                json.dump(cluster_config, f, indent=2)
            
            result["config"] = cluster_config
            result["success"] = True
            
        except Exception as e:
            result["errors"].append(f"Cluster config generation error: {str(e)}")
            
        return result
    
    def _deep_merge_config(self, base_config: Dict[str, Any], updates: Dict[str, Any]):
        """Deep merge configuration updates into base configuration.
        
        Args:
            base_config: Base configuration to update
            updates: Updates to apply
        """
        for key, value in updates.items():
            if key in base_config and isinstance(base_config[key], dict) and isinstance(value, dict):
                self._deep_merge_config(base_config[key], value)
            else:
                base_config[key] = value
    
    def _validate_follow_service_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate follow service configuration.
        
        Args:
            config: Configuration to validate
            
        Returns:
            Dict with validation results
        """
        result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        try:
            # Check required fields
            required_fields = ["id", "cluster_name", "cluster", "api", "ipfs_connector"]
            for field in required_fields:
                if field not in config:
                    result["errors"].append(f"Missing required field: {field}")
                    result["valid"] = False
            
            # Validate ports
            if "api" in config and "restapi" in config["api"]:
                listen_addr = config["api"]["restapi"].get("listen_multiaddress", "")
                if f"tcp/{self.api_port}" not in listen_addr:
                    result["warnings"].append(f"API port mismatch in configuration")
            
        except Exception as e:
            result["errors"].append(f"Validation error: {str(e)}")
            result["valid"] = False
            
        return result

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
                
                # Update configuration to use different port than cluster service
                try:
                    with open(config_path, 'r') as f:
                        config_data = json.load(f)
                    
                    # Update API listen address to use port 9097 instead of default 9095
                    if "api" in config_data:
                        config_data["api"]["restapi"]["listen_multiaddress"] = "/ip4/127.0.0.1/tcp/9097"
                        config_data["api"]["restapi"]["proxy_listen_multiaddress"] = "/ip4/127.0.0.1/tcp/9098"
                    
                    # Save updated configuration
                    with open(config_path, 'w') as f:
                        json.dump(config_data, f, indent=2)
                    
                    logger.info("Updated cluster follow configuration to use ports 9097-9098")
                    
                    result["config_valid"] = True
                    result["config_summary"] = {
                        "id": config_data.get("cluster", {}).get("id", "unknown"),
                        "peers": config_data.get("peers", []),
                        "bootstrap": config_data.get("bootstrap", []),
                        "api_port": 9097,
                        "proxy_port": 9098
                    }
                except Exception as e:
                    logger.error(f"Error reading/updating configuration file: {str(e)}")
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
    
    def get_follow_api_client(self, host: str = "127.0.0.1", port: int = 9097, 
                            auth: Optional[Dict[str, str]] = None) -> IPFSClusterFollowAPIClient:
        """Get API client for cluster follow service.
        
        Args:
            host: API host (default: 127.0.0.1)
            port: API port (default: 9097)
            auth: Authentication credentials
            
        Returns:
            Follow API client instance
        """
        api_url = f"http://{host}:{port}"
        return IPFSClusterFollowAPIClient(api_url, auth)
    
    def get_follow_ctl_wrapper(self) -> IPFSClusterFollowCTLWrapper:
        """Get cluster-follow-ctl wrapper for command line operations.
        
        Returns:
            Cluster-follow-ctl wrapper instance
        """
        cluster_name = self.cluster_name or "default"
        return IPFSClusterFollowCTLWrapper(cluster_name)
    
    async def connect_to_cluster_leader(self, leader_host: str, leader_port: int = 9094, 
                                      auth: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Connect to a cluster leader using REST API.
        
        Args:
            leader_host: Cluster leader host
            leader_port: Cluster leader API port
            auth: Authentication credentials for leader cluster
            
        Returns:
            Connection status and leader cluster info
        """
        result = {
            "success": False,
            "connected": False,
            "leader_info": {},
            "errors": []
        }
        
        try:
            # Import the main API client for connecting to leader
            from ipfs_kit_py.ipfs_cluster_api import IPFSClusterAPIClient
            
            # Create API client for leader cluster
            leader_client = IPFSClusterAPIClient(f"http://{leader_host}:{leader_port}", auth)
            
            async with leader_client:
                # Authenticate if credentials provided
                if auth:
                    auth_success = await leader_client.authenticate()
                    if not auth_success:
                        result["errors"].append("Authentication with leader failed")
                        return result
                
                # Get leader cluster info
                id_response = await leader_client.get_id()
                if id_response.get("success"):
                    result["leader_info"]["id"] = id_response
                    result["connected"] = True
                    
                # Get peers to understand the cluster
                peers_response = await leader_client.get_peers()
                if peers_response.get("success"):
                    result["leader_info"]["peers"] = peers_response
                    
                # Get pins to understand what content is being managed
                pins_response = await leader_client.get_pins()
                if pins_response.get("success"):
                    result["leader_info"]["pins"] = pins_response
                    
                result["success"] = result["connected"]
                
        except Exception as e:
            result["errors"].append(f"Connection error: {str(e)}")
            logger.error(f"Failed to connect to cluster leader {leader_host}:{leader_port}: {e}")
            
        return result
    
    async def get_follow_status_via_api(self) -> Dict[str, Any]:
        """Get cluster follow status using REST API with enhanced daemon manager.
        
        Returns:
            Cluster follow status information
        """
        result = {
            "success": False,
            "api_responsive": False,
            "follow_info": {},
            "errors": []
        }
        
        try:
            # Use enhanced daemon manager for better API management
            from ipfs_kit_py.ipfs_cluster_follow_daemon_manager import IPFSClusterFollowDaemonManager
            
            # Create enhanced daemon manager
            manager = IPFSClusterFollowDaemonManager(
                cluster_name=self.cluster_name or "default"
            )
            
            # Get comprehensive status via enhanced manager
            status_result = await manager.get_follow_status_via_api()
            
            if status_result.get("success"):
                result.update(status_result)
                result["success"] = True
                logger.info("Retrieved cluster follow status via enhanced daemon manager")
            else:
                # Fallback to basic API client
                follow_client = self.get_follow_api_client()
                
                async with follow_client:
                    # Test API responsiveness
                    health_response = await follow_client.health_check()
                    if health_response.get("success"):
                        result["api_responsive"] = True
                        
                    # Get follow service ID and info
                    id_response = await follow_client.get_id()
                    if id_response.get("success"):
                        result["follow_info"]["id"] = id_response
                        
                    # Get followed pins
                    pins_response = await follow_client.get_pins()
                    if pins_response.get("success"):
                        result["follow_info"]["pins"] = pins_response
                        
                    result["success"] = True
                    
        except ImportError:
            # Enhanced manager not available, use basic approach
            logger.debug("Enhanced daemon manager not available, using basic API client")
            try:
                follow_client = self.get_follow_api_client()
                
                async with follow_client:
                    # Test API responsiveness
                    health_response = await follow_client.health_check()
                    if health_response.get("success"):
                        result["api_responsive"] = True
                        
                    # Get follow service ID and info
                    id_response = await follow_client.get_id()
                    if id_response.get("success"):
                        result["follow_info"]["id"] = id_response
                        
                    # Get followed pins
                    pins_response = await follow_client.get_pins()
                    if pins_response.get("success"):
                        result["follow_info"]["pins"] = pins_response
                        
                    result["success"] = True
                    
            except Exception as basic_e:
                result["errors"].append(f"Basic API check error: {str(basic_e)}")
                logger.error(f"Basic API check failed: {basic_e}")
        except Exception as e:
            result["errors"].append(f"API status check error: {str(e)}")
            logger.error(f"Failed to get follow status via API: {e}")
            
        return result
    
    async def initialize_cluster_follow_via_api(self, bootstrap_peer: str) -> Dict[str, Any]:
        """Initialize cluster follow using enhanced daemon manager and API.
        
        Args:
            bootstrap_peer: Bootstrap peer multiaddr
            
        Returns:
            Initialization result
        """
        result = {
            "success": False,
            "initialized": False,
            "errors": []
        }
        
        try:
            # Use enhanced daemon manager for initialization
            from ipfs_kit_py.ipfs_cluster_follow_daemon_manager import IPFSClusterFollowDaemonManager
            
            # Create enhanced daemon manager
            manager = IPFSClusterFollowDaemonManager(
                cluster_name=self.cluster_name or "default"
            )
            
            # Start the cluster follow with bootstrap peer
            start_result = await manager.start_cluster_follow(bootstrap_peer)
            
            if start_result.get("success"):
                result["success"] = True
                result["initialized"] = True
                result["status"] = start_result.get("status", "unknown")
                result["api_responsive"] = start_result.get("api_responsive", False)
                result["leader_connected"] = start_result.get("leader_connected", False)
                logger.info(f"Cluster follow initialized with bootstrap peer: {bootstrap_peer}")
            else:
                result["errors"].extend(start_result.get("errors", ["Unknown initialization error"]))
                
        except ImportError:
            # Enhanced manager not available, use basic approach
            logger.debug("Enhanced daemon manager not available, using basic initialization")
            try:
                # Use follow ctl wrapper to initialize
                follow_ctl = self.get_follow_ctl_wrapper()
                init_result = await follow_ctl.init(bootstrap_peer)
                
                if init_result.get("success"):
                    result["success"] = True
                    result["initialized"] = True
                    result["init_output"] = init_result.get("stdout", "")
                    logger.info(f"Cluster follow initialized with bootstrap peer: {bootstrap_peer}")
                else:
                    result["errors"].append(init_result.get("stderr", "Unknown initialization error"))
                    
            except Exception as basic_e:
                result["errors"].append(f"Basic initialization error: {str(basic_e)}")
                logger.error(f"Basic initialization failed: {basic_e}")
        except Exception as e:
            result["errors"].append(f"Initialization error: {str(e)}")
            logger.error(f"Failed to initialize cluster follow: {e}")
            
        return result

    async def start_enhanced_follow_daemon(self, bootstrap_peer: str, **kwargs) -> Dict[str, Any]:
        """Start cluster follow daemon using enhanced daemon manager.
        
        Args:
            bootstrap_peer: Bootstrap peer multiaddr
            **kwargs: Additional arguments
            
        Returns:
            Start operation result
        """
        result = {
            "success": False,
            "enhanced_manager_used": False,
            "errors": []
        }
        
        try:
            # Use enhanced daemon manager for starting
            from ipfs_kit_py.ipfs_cluster_follow_daemon_manager import IPFSClusterFollowDaemonManager
            
            # Create enhanced daemon manager
            manager = IPFSClusterFollowDaemonManager(
                cluster_name=self.cluster_name or "default"
            )
            
            # Start the cluster follow
            start_result = await manager.start_cluster_follow(
                bootstrap_peer, 
                force_restart=kwargs.get("force_restart", False)
            )
            
            result.update(start_result)
            result["enhanced_manager_used"] = True
            
            if start_result.get("success"):
                logger.info("Cluster follow started successfully using enhanced daemon manager")
            else:
                logger.error(f"Enhanced manager failed: {start_result.get('errors', [])}")
                
        except ImportError:
            # Enhanced manager not available, fallback to basic start
            logger.debug("Enhanced daemon manager not available, using basic start method")
            try:
                basic_result = self.ipfs_follow_start(
                    cluster_name=self.cluster_name or "default",
                    bootstrap_peer=bootstrap_peer,
                    **kwargs
                )
                result.update(basic_result)
                result["enhanced_manager_used"] = False
                
            except Exception as basic_e:
                result["errors"].append(f"Basic start method failed: {str(basic_e)}")
                logger.error(f"Basic start method failed: {basic_e}")
        except Exception as e:
            result["errors"].append(f"Enhanced start failed: {str(e)}")
            logger.error(f"Enhanced start failed: {e}")
            
        return result


ipfs_cluster_follow = ipfs_cluster_follow


class IPFSClusterFollow:
    """Enhanced IPFS Cluster Follow manager with configuration support."""
    
    def __init__(self, config_dir: Optional[str] = None):
        """Initialize IPFS Cluster Follow manager.
        
        Args:
            config_dir: Configuration directory path
        """
        from pathlib import Path
        
        self.config_dir = Path(config_dir) if config_dir else Path.home() / ".ipfs-cluster" / "follow"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize follow instance
        self.follow_instance = ipfs_cluster_follow()
    
    def config_create(self, **config_params) -> Dict[str, Any]:
        """Create cluster follow configuration.
        
        Args:
            **config_params: Configuration parameters
            
        Returns:
            Dict with creation result
        """
        try:
            # Extract follow-specific parameters
            cluster_name = config_params.get("cluster_name", "ipfs-cluster-follow")
            api_listen = config_params.get("api_listen_multiaddress", "/ip4/127.0.0.1/tcp/9097")
            proxy_listen = config_params.get("proxy_listen_multiaddress", "/ip4/127.0.0.1/tcp/9098")
            trusted_peers = config_params.get("trusted_peers", [])
            
            # Generate peer identity
            import secrets
            import base64
            
            # Generate random peer ID (simplified)
            peer_id = f"12D3KooW{secrets.token_hex(20)}"
            private_key = base64.b64encode(secrets.token_bytes(32)).decode()
            
            # Create service.json
            service_config = {
                "cluster": {
                    "peername": cluster_name,
                    "secret": secrets.token_hex(32),
                    "leave_on_shutdown": False,
                    "disable_repinning": False,
                    "state_sync_interval": "1m0s",
                    "ipfs_sync_interval": "2m10s",
                    "replication_factor_min": -1,
                    "replication_factor_max": -1,
                    "monitor_ping_interval": "15s",
                    "peer_watch_interval": "5s",
                    "mdns_interval": "10s",
                    "trusted_peers": trusted_peers
                },
                "consensus": {
                    "crdt": {
                        "cluster_name": cluster_name,
                        "trusted_peers": trusted_peers
                    }
                },
                "api": {
                    "restapi": {
                        "http_listen_multiaddress": api_listen,
                        "read_timeout": "30s",
                        "read_header_timeout": "5s",
                        "write_timeout": "60s",
                        "idle_timeout": "120s",
                        "max_header_bytes": 4096,
                        "cors_allowed_origins": ["*"],
                        "cors_allowed_methods": ["GET", "POST", "PUT", "DELETE"],
                        "cors_allowed_headers": ["*"],
                        "cors_exposed_headers": ["*"],
                        "cors_allow_credentials": True,
                        "cors_max_age": "0s"
                    }
                },
                "ipfs_connector": {
                    "ipfshttp": {
                        "node_multiaddress": "/ip4/127.0.0.1/tcp/5001",
                        "connect_swarms_delay": "7s",
                        "request_timeout": "5m0s",
                        "pin_timeout": "2m0s",
                        "unpin_timeout": "3m0s"
                    }
                },
                "pin_tracker": {
                    "stateless": {
                        "concurrent_pins": 10,
                        "priority_pin_max_age": "24h0m0s",
                        "priority_pin_max_retries": 5
                    }
                },
                "monitor": {
                    "pubsubmon": {
                        "check_interval": "15s"
                    }
                },
                "allocator": {
                    "balanced": {
                        "allocate_by": ["tag:group", "freespace"]
                    }
                },
                "informer": {
                    "disk": {
                        "metric_ttl": "30s",
                        "metric_type": "freespace"
                    },
                    "tags": {
                        "metric_ttl": "30s",
                        "tags": {
                            "group": "follow"
                        }
                    }
                },
                "observations": {
                    "metrics": {
                        "enable_stats": False
                    },
                    "tracing": {
                        "enable_tracing": False
                    }
                },
                "datastore": {
                    "leveldb": {
                        "folder": str(self.config_dir / "leveldb")
                    }
                }
            }
            
            # Create identity.json
            identity_config = {
                "id": peer_id,
                "private_key": private_key
            }
            
            # Write configuration files
            service_file = self.config_dir / "service.json"
            identity_file = self.config_dir / "identity.json"
            
            with open(service_file, 'w') as f:
                json.dump(service_config, f, indent=2)
            
            with open(identity_file, 'w') as f:
                json.dump(identity_config, f, indent=2)
            
            logger.info(f"✓ Created follow configuration in {self.config_dir}")
            
            return {
                "success": True,
                "config_dir": str(self.config_dir),
                "service_file": str(service_file),
                "identity_file": str(identity_file),
                "config": service_config,
                "identity": identity_config
            }
            
        except Exception as e:
            logger.error(f"Error creating follow config: {e}")
            return {"success": False, "error": str(e)}
    
    def config_get(self) -> Dict[str, Any]:
        """Get cluster follow configuration.
        
        Returns:
            Dict with configuration data
        """
        try:
            service_file = self.config_dir / "service.json"
            identity_file = self.config_dir / "identity.json"
            
            if not service_file.exists():
                return {"success": False, "error": "Configuration not found"}
            
            with open(service_file, 'r') as f:
                service_config = json.load(f)
            
            result = {
                "success": True,
                "config_dir": str(self.config_dir),
                "service_file": str(service_file),
                "config": service_config
            }
            
            if identity_file.exists():
                with open(identity_file, 'r') as f:
                    identity_config = json.load(f)
                result["identity_file"] = str(identity_file)
                result["identity"] = identity_config
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting follow config: {e}")
            return {"success": False, "error": str(e)}
    
    def config_set(self, **config_params) -> Dict[str, Any]:
        """Set cluster follow configuration.
        
        Args:
            **config_params: Configuration parameters to update
            
        Returns:
            Dict with update result
        """
        try:
            # Get current config
            current_result = self.config_get()
            if not current_result.get("success"):
                return current_result
            
            config = current_result["config"]
            
            # Update configuration with provided parameters
            if "cluster_name" in config_params:
                config["cluster"]["peername"] = config_params["cluster_name"]
                config["consensus"]["crdt"]["cluster_name"] = config_params["cluster_name"]
            
            if "api_listen_multiaddress" in config_params:
                config["api"]["restapi"]["http_listen_multiaddress"] = config_params["api_listen_multiaddress"]
            
            if "trusted_peers" in config_params:
                config["cluster"]["trusted_peers"] = config_params["trusted_peers"]
                config["consensus"]["crdt"]["trusted_peers"] = config_params["trusted_peers"]
            
            if "replication_factor_min" in config_params:
                config["cluster"]["replication_factor_min"] = config_params["replication_factor_min"]
            
            if "replication_factor_max" in config_params:
                config["cluster"]["replication_factor_max"] = config_params["replication_factor_max"]
            
            # Write updated config
            service_file = self.config_dir / "service.json"
            with open(service_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            logger.info(f"✓ Updated follow configuration in {self.config_dir}")
            
            return {
                "success": True,
                "config_dir": str(self.config_dir),
                "service_file": str(service_file),
                "config": config,
                "updated_params": list(config_params.keys())
            }
            
        except Exception as e:
            logger.error(f"Error setting follow config: {e}")
            return {"success": False, "error": str(e)}


if __name__ == "__main__":
    metadata = {"cluster_name": "test"}
    resources = {}
    this_ipfs_cluster_follow = ipfs_cluster_follow(resources, metadata)
    print("IPFS Cluster Follow module loaded successfully")
    pass
