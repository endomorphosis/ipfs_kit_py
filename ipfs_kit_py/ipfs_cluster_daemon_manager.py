#!/usr/bin/env python3
"""
Enhanced IPFS Cluster Daemon Manager

This module provides comprehensive management for IPFS Cluster services including:
- IPFS Cluster Service daemon management
- IPFS Cluster Follow daemon management
- Health monitoring and API checks
- Port conflict resolution
- Configuration management
- Automatic recovery and healing
"""

import os
import sys
import time
import json
import signal
import psutil
import logging
import subprocess
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import secrets
import json
import hashlib
import socket
import uuid
import shutil
import base64

# Try to import optional dependencies
try:
    import base58
except ImportError:
    base58 = None

try:
    import httpx
except ImportError:
    httpx = None

# Import our API client
try:
    from ipfs_kit_py.ipfs_cluster_api import IPFSClusterAPIClient, IPFSClusterCTLWrapper
except ImportError:
    # Create stub classes if import fails
    class IPFSClusterAPIClient:
        def __init__(self, *args, **kwargs):
            pass
    class IPFSClusterCTLWrapper:
        def __init__(self, *args, **kwargs):
            pass

# Configure logger
logger = logging.getLogger(__name__)

class IPFSClusterConfig:
    """Configuration management for IPFS Cluster."""
    
    def __init__(self, cluster_path: Optional[str] = None):
        """Initialize cluster configuration.
        
        Args:
            cluster_path: Path to cluster configuration directory
        """
        self.cluster_path = Path(cluster_path or os.path.expanduser("~/.ipfs-cluster"))
        self.service_config_path = self.cluster_path / "service.json"
        self.peerstore_path = self.cluster_path / "peerstore"
        self.identity_path = self.cluster_path / "identity.json"
        
        # Default ports
        self.api_port = 9094
        self.proxy_port = 9095
        self.cluster_port = 9096
        
        # Binary paths
        self.cluster_service_bin = self._get_cluster_binary_path()
    
    def config_create(self, overwrite: bool = False, **custom_settings) -> Dict[str, Any]:
        """Create and configure IPFS Cluster service configuration.
        
        Args:
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
            "errors": []
        }
        
        try:
            # Check if config already exists
            if self.service_config_path.exists() and not overwrite:
                result["errors"].append("Configuration already exists. Use overwrite=True to replace.")
                return result
            
            # Ensure directory exists
            self.cluster_path.mkdir(parents=True, exist_ok=True)
            
            # Generate identity configuration
            identity_result = self._generate_identity_config()
            if not identity_result["success"]:
                result["errors"].extend(identity_result["errors"])
                return result
            
            result["identity_created"] = True
            result["identity_config"] = identity_result["identity"]
            
            # Generate service configuration
            service_result = self._generate_service_config(identity_result["identity"], **custom_settings)
            if not service_result["success"]:
                result["errors"].extend(service_result["errors"])
                return result
            
            result["config_created"] = True
            result["service_config"] = service_result["config"]
            result["success"] = True
            
            logger.info(f"IPFS Cluster configuration created at {self.cluster_path}")
            
        except Exception as e:
            result["errors"].append(f"Configuration creation error: {str(e)}")
            logger.error(f"Failed to create cluster configuration: {e}")
            
        return result
    
    def config_get(self) -> Dict[str, Any]:
        """Retrieve current IPFS Cluster configuration.
        
        Returns:
            Dict with current configuration
        """
        result = {
            "success": False,
            "config_exists": False,
            "service_config": {},
            "identity_config": {},
            "errors": []
        }
        
        try:
            # Check if configuration exists
            if not self.service_config_path.exists():
                result["errors"].append("Service configuration file not found")
                return result
            
            # Load service configuration
            with open(self.service_config_path, 'r') as f:
                result["service_config"] = json.load(f)
            
            # Load identity configuration if it exists
            if self.identity_path.exists():
                with open(self.identity_path, 'r') as f:
                    result["identity_config"] = json.load(f)
            
            result["config_exists"] = True
            result["success"] = True
            
        except Exception as e:
            result["errors"].append(f"Configuration retrieval error: {str(e)}")
            logger.error(f"Failed to retrieve cluster configuration: {e}")
            
        return result
    
    def config_set(self, config_updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update IPFS Cluster configuration with new settings.
        
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
            validation_result = self._validate_service_config(service_config)
            if not validation_result["valid"]:
                result["errors"].extend(validation_result["errors"])
                return result
            
            # Save updated configuration
            with open(self.service_config_path, 'w') as f:
                json.dump(service_config, f, indent=2)
            
            result["config_updated"] = True
            result["updated_config"] = service_config
            result["success"] = True
            
            logger.info("IPFS Cluster configuration updated successfully")
            
        except Exception as e:
            result["errors"].append(f"Configuration update error: {str(e)}")
            logger.error(f"Failed to update cluster configuration: {e}")
            
        return result
    
    def _generate_proper_peer_id(self) -> str:
        """Generate a proper IPFS peer ID according to libp2p specification.
        
        IPFS peer IDs are libp2p peer IDs which start with "12D3KooW".
        They follow the format: 0x00 0x24 0x08 0x01 0x12 0x20 <32-byte-hash>
        
        Returns:
            str: Valid IPFS peer ID starting with "12D3KooW"
        """
        
        try:
            # Generate a random Ed25519 public key (32 bytes)
            public_key = secrets.token_bytes(32)
            
            # Create SHA-256 hash of the public key
            sha256_hash = hashlib.sha256(public_key).digest()
            
            # Create libp2p peer ID multihash with exact format:
            # 0x00: multihash type (identity)
            # 0x24: length (36 bytes total)
            # 0x08: key type (Ed25519)  
            # 0x01: key encoding
            # 0x12: hash type (SHA-256)
            # 0x20: hash length (32 bytes)
            # + 32 bytes of hash
            multihash = b'\x00\x24\x08\x01\x12\x20' + sha256_hash
            
            # Encode as base58 to create peer ID
            if base58:
                peer_id = base58.b58encode(multihash).decode('ascii')
                return peer_id
            else:
                # Fallback to manual base58 implementation if library not available
                return self._generate_peer_id_fallback_libp2p(multihash)
            
        except Exception:
            # Fallback to manual base58 implementation if anything fails
            return self._generate_peer_id_fallback_libp2p()
    
    def _generate_peer_id_fallback(self) -> str:
        """Fallback peer ID generation using manual base58 encoding.
        
        Returns:
            str: Valid IPFS peer ID
        """
        return self._generate_peer_id_fallback_libp2p()
    
    def _generate_peer_id_fallback_libp2p(self, multihash_bytes=None) -> str:
        """Fallback libp2p peer ID generation using manual base58 encoding.
        
        Args:
            multihash_bytes: Pre-computed multihash bytes, or None to generate
        
        Returns:
            str: Valid IPFS peer ID starting with "12D3KooW"
        """
        
        # Base58 alphabet
        ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
        
        def base58_encode(data):
            """Manual base58 encoding implementation."""
            # Convert bytes to integer
            num = int.from_bytes(data, 'big')
            
            # Convert to base58
            encoded = ""
            while num > 0:
                num, remainder = divmod(num, 58)
                encoded = ALPHABET[remainder] + encoded
            
            # Handle leading zeros
            for byte in data:
                if byte == 0:
                    encoded = '1' + encoded
                else:
                    break
            
            return encoded
        
        if multihash_bytes is None:
            # Generate a random Ed25519 public key (32 bytes)
            public_key = secrets.token_bytes(32)
            
            # Create SHA-256 hash of the public key
            sha256_hash = hashlib.sha256(public_key).digest()
            
            # Create libp2p peer ID multihash with exact format:
            # 0x00: multihash type (identity)
            # 0x24: length (36 bytes total)
            # 0x08: key type (Ed25519)  
            # 0x01: key encoding
            # 0x12: hash type (SHA-256)
            # 0x20: hash length (32 bytes)
            # + 32 bytes of hash
            multihash_bytes = b'\x00\x24\x08\x01\x12\x20' + sha256_hash
        
        # Encode as base58 to create peer ID
        peer_id = base58_encode(multihash_bytes)
        
        return peer_id
    
    def _generate_identity_config(self) -> Dict[str, Any]:
        """Generate identity configuration for cluster.
        
        Returns:
            Dict with identity generation results
        """
        result = {
            "success": False,
            "identity": {},
            "errors": []
        }
        
        try:
            # Generate proper IPFS peer ID
            peer_id = self._generate_proper_peer_id()
            
            # Generate a proper Ed25519 private key for IPFS Cluster
            # The private key should be the actual Ed25519 private key, not random bytes
            import ed25519
            
            try:
                # Generate Ed25519 keypair
                private_key_obj, public_key_obj = ed25519.create_keypair()
                
                # Get the raw private key bytes (32 bytes)
                private_key_bytes = private_key_obj.to_bytes()
                
                # Encode as base64 for storage
                private_key = base64.b64encode(private_key_bytes).decode('utf-8')
                
            except ImportError:
                # Fallback: generate a 32-byte private key (Ed25519 standard)
                private_key_bytes = secrets.token_bytes(32)
                private_key = base64.b64encode(private_key_bytes).decode('utf-8')
            
            identity = {
                "id": peer_id,
                "private_key": private_key,
                "addresses": [
                    f"/ip4/127.0.0.1/tcp/{self.cluster_port}/p2p/{peer_id}",
                    f"/ip4/0.0.0.0/tcp/{self.cluster_port}/p2p/{peer_id}"
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
    
    def _validate_peer_id(self, peer_id: str) -> bool:
        """Validate if a peer ID follows IPFS multihash specification.
        
        Args:
            peer_id: The peer ID to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        try:
            # Check minimum length (12D3KooW is prefix + base58 encoded multihash)
            if len(peer_id) < 52:  # Minimum length for valid peer ID
                return False
                
            # Check prefix
            if not peer_id.startswith("12D3KooW"):
                return False
                
            # Try to decode the base58 part
            if base58:
                decoded = base58.b58decode(peer_id)
                
                # Check libp2p peer ID multihash format: 0x00 0x24 0x08 0x01 0x12 0x20 <32-byte-hash>
                if len(decoded) < 38:  # 6 bytes header + 32 bytes hash
                    return False
                    
                # Check the exact header sequence
                if (decoded[0] != 0x00 or decoded[1] != 0x24 or decoded[2] != 0x08 or 
                    decoded[3] != 0x01 or decoded[4] != 0x12 or decoded[5] != 0x20):
                    return False
                    
                return True
            else:
                # Fallback validation without base58 library
                import string
                b58_chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
                
                # Check if all characters are valid base58
                for char in peer_id:
                    if char not in b58_chars:
                        return False
                        
                # Length check for base58 encoded 38-byte multihash (should start with "12D3KooW")
                if len(peer_id) < 52:  # Minimum length for libp2p peer ID
                    return False
                    
                return True
                
        except Exception:
            return False
    
    def auto_heal_cluster_config(self) -> Dict[str, Any]:
        """Auto-heal broken cluster configuration by regenerating identity if needed.
        
        Returns:
            Dict with healing results
        """
        result = {
            "success": False,
            "actions_taken": [],
            "errors": []
        }
        
        try:
            # Check if identity file exists and is valid
            needs_regeneration = False
            
            if not os.path.exists(self.identity_path):
                result["actions_taken"].append("Identity file missing - will regenerate")
                needs_regeneration = True
            else:
                try:
                    with open(self.identity_path, 'r') as f:
                        identity = json.load(f)
                        
                    peer_id = identity.get("id")
                    if not peer_id or not self._validate_peer_id(peer_id):
                        result["actions_taken"].append(f"Invalid peer ID detected: {peer_id} - will regenerate")
                        needs_regeneration = True
                        
                except Exception as e:
                    result["actions_taken"].append(f"Corrupted identity file: {str(e)} - will regenerate")
                    needs_regeneration = True
            
            # Regenerate if needed
            if needs_regeneration:
                identity_result = self._generate_identity_config()
                if identity_result["success"]:
                    result["actions_taken"].append("Successfully regenerated identity configuration")
                    result["new_peer_id"] = identity_result["identity"]["id"]
                else:
                    result["errors"].extend(identity_result["errors"])
                    return result
            
            # Check service config
            if not os.path.exists(self.service_config_path):
                result["actions_taken"].append("Service config missing - will regenerate")
                
                # Load identity for service config generation
                with open(self.identity_path, 'r') as f:
                    identity = json.load(f)
                    
                service_result = self._generate_service_config(identity)
                if service_result["success"]:
                    result["actions_taken"].append("Successfully regenerated service configuration")
                else:
                    result["errors"].extend(service_result["errors"])
                    return result
            
            result["success"] = True
            if not result["actions_taken"]:
                result["actions_taken"].append("Configuration is healthy - no action needed")
                
        except Exception as e:
            result["errors"].append(f"Auto-heal error: {str(e)}")
            
        return result
    
    def _generate_service_config(self, identity: Dict[str, Any], **custom_settings) -> Dict[str, Any]:
        """Generate service configuration for cluster.
        
        Args:
            identity: Identity configuration
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
            # Default service configuration
            config = {
                "id": identity["id"],
                "cluster": {
                    "secret": secrets.token_hex(32),
                    "peers": [],
                    "bootstrap": [],
                    "leave_on_shutdown": False,
                    "listen_multiaddress": f"/ip4/0.0.0.0/tcp/{self.cluster_port}",
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
                        "cors_allowed_methods": ["GET", "POST", "PUT", "DELETE"],
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
                        "tags": {"group": "default"}
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
    
    def _validate_service_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate service configuration.
        
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
            required_fields = ["id", "cluster", "api", "ipfs_connector"]
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
        
    def _get_cluster_binary_path(self) -> Path:
        """Get path to IPFS Cluster binary.
        
        Returns:
            Path to cluster binary
        """
        # Check multiple possible locations
        possible_paths = [
            # Project-specific locations
            Path(__file__).parent.parent / "bin" / "ipfs-cluster-service",
            Path(__file__).parent / "bin" / "ipfs-cluster-service",
        ]
        
        for path in possible_paths:
            if path.exists() and path.is_file():
                return path
                
        # Default system path
        return Path("ipfs-cluster-service")
        
    def ensure_config_exists(self) -> Dict[str, Any]:
        """Ensure cluster configuration exists and is valid.
        
        Returns:
            Dict with configuration check results
        """
        result = {
            "success": False,
            "config_exists": False,
            "config_valid": False,
            "created_config": False,
            "errors": []
        }
        
        try:
            # Check if config directory exists
            if not os.path.exists(self.cluster_path):
                os.makedirs(self.cluster_path, exist_ok=True)
                logger.info(f"Created cluster config directory: {self.cluster_path}")
            
            # Check if service config exists
            if not os.path.exists(self.service_config_path):
                logger.info("IPFS Cluster service config not found, initializing...")
                init_result = self._initialize_cluster_config()
                if not init_result["success"]:
                    result["errors"].extend(init_result.get("errors", []))
                    return result
                result["created_config"] = True
            
            result["config_exists"] = True
            
            # Validate configuration
            if self._validate_config():
                result["config_valid"] = True
                result["success"] = True
            else:
                result["errors"].append("Configuration validation failed")
                
        except Exception as e:
            logger.error(f"Error ensuring cluster config: {e}")
            result["errors"].append(str(e))
            
        return result
    
    def _initialize_cluster_config(self) -> Dict[str, Any]:
        """Initialize cluster configuration using ipfs-cluster-service init.
        
        Returns:
            Dict with initialization results
        """
        result = {"success": False, "errors": []}
        
        try:
            # Get the cluster binary path
            cluster_bin = str(self.cluster_service_bin)
            if not cluster_bin or cluster_bin == "ipfs-cluster-service":
                # Try to find the binary
                import shutil
                cluster_bin = shutil.which("ipfs-cluster-service")
                if not cluster_bin:
                    result["errors"].append("IPFS Cluster binary not found")
                    return result
            
            # Set environment
            env = os.environ.copy()
            env["IPFS_CLUSTER_PATH"] = str(self.cluster_path)
            
            # Run initialization
            cmd = [cluster_bin, "init"]
            process = subprocess.run(
                cmd, 
                env=env,
                capture_output=True, 
                text=True, 
                timeout=30,
                input="y\n"  # Auto-confirm overwrite if needed
            )
            
            if process.returncode == 0:
                result["success"] = True
                result["stdout"] = process.stdout
                
                # Ensure the configuration has all required fields
                self._ensure_config_has_id()
                
                # After successful init, check and fix the peer ID if needed
                self._ensure_valid_peer_id()
                
                logger.info("IPFS Cluster configuration initialized successfully")
                
            else:
                result["errors"].append(f"Init failed: {process.stderr}")
                
        except subprocess.TimeoutExpired:
            result["errors"].append("Cluster init timeout")
        except Exception as e:
            result["errors"].append(f"Init error: {str(e)}")
            
        return result
    
    def _ensure_config_has_id(self):
        """Ensure the cluster configuration has a valid ID."""
        try:
            if os.path.exists(self.service_config_path):
                with open(self.service_config_path, 'r') as f:
                    config = json.load(f)
                
                # Check if ID exists, if not generate one
                if "id" not in config or not config["id"]:
                    import uuid
                    config["id"] = str(uuid.uuid4())
                    
                    # Save updated config
                    with open(self.service_config_path, 'w') as f:
                        json.dump(config, f, indent=2)
                    
                    logger.info("Added missing ID to cluster configuration")
                    
        except Exception as e:
            logger.warning(f"Could not ensure ID in cluster config: {e}")
    
    def _ensure_valid_peer_id(self):
        """Ensure the cluster configuration has a valid peer ID, regenerating if necessary."""
        try:
            if os.path.exists(self.identity_path):
                with open(self.identity_path, 'r') as f:
                    identity = json.load(f)
                
                # Check if peer ID is valid
                peer_id = identity.get("id")
                if not peer_id or not self._validate_peer_id(peer_id):
                    logger.info(f"Invalid peer ID detected: {peer_id}, regenerating...")
                    
                    # Generate a new valid peer ID but keep the existing private key
                    new_peer_id = self._generate_proper_peer_id()
                    identity["id"] = new_peer_id
                    
                    # Update addresses with new peer ID
                    identity["addresses"] = [
                        f"/ip4/127.0.0.1/tcp/{self.cluster_port}/p2p/{new_peer_id}",
                        f"/ip4/0.0.0.0/tcp/{self.cluster_port}/p2p/{new_peer_id}"
                    ]
                    
                    # Save updated identity
                    with open(self.identity_path, 'w') as f:
                        json.dump(identity, f, indent=2)
                    
                    logger.info(f"Updated peer ID to: {new_peer_id}")
                    
        except Exception as e:
            logger.warning(f"Could not ensure valid peer ID: {e}")
    
    def _validate_config(self) -> bool:
        """Validate cluster configuration files.
        
        Returns:
            True if configuration is valid
        """
        try:
            # Check service config
            if not os.path.exists(self.service_config_path):
                return False
                
            with open(self.service_config_path, 'r') as f:
                config = json.load(f)
                
            # Basic validation - check required fields
            required_fields = ["id", "cluster", "api", "ipfs_connector"]
            for field in required_fields:
                if field not in config:
                    logger.error(f"Missing required field in config: {field}")
                    return False
                    
            return True
            
        except Exception as e:
            logger.error(f"Error validating cluster config: {e}")
            return False


class IPFSClusterDaemonManager:
    """Enhanced daemon manager for IPFS Cluster services."""
    
    def __init__(self, config: Optional[IPFSClusterConfig] = None):
        """Initialize the cluster daemon manager.
        
        Args:
            config: Cluster configuration instance
        """
        self.config = config or IPFSClusterConfig()
        self.service_process = None
        self.follow_process = None
        
        # API clients for both service and follow
        self.api_client = None
        self.ctl_wrapper = None
        
        # Daemon status tracking
        self.service_status = {
            "running": False,
            "pid": None,
            "api_responsive": False,
            "last_check": None,
            "errors": []
        }
        
        self.follow_status = {
            "running": False,
            "pid": None,
            "last_check": None,
            "errors": []
        }
    
    def _validate_configuration(self) -> Dict[str, Any]:
        """Validate the current cluster configuration.
        
        Returns:
            Dict with validation results
        """
        validation_result = {
            "valid": True,
            "issues": [],
            "warnings": []
        }
        
        try:
            # Check if cluster path exists
            if not self.config.cluster_path.exists():
                validation_result["issues"].append("Cluster directory does not exist")
                validation_result["valid"] = False
            
            # Check if config file exists (for existing installations)
            config_file = self.config.cluster_path / "service.json"
            if not config_file.exists():
                # This might be a new installation, so just warn
                validation_result["warnings"].append("Service config file not found - this might be a new installation")
            
            # Check if ports are available
            port_check = self._check_port_availability()
            if not port_check["api_port_available"]:
                validation_result["issues"].append(f"API port {self.config.api_port} is not available")
                validation_result["valid"] = False
            
            # Check if binary exists
            if not self.config.cluster_service_bin or not Path(self.config.cluster_service_bin).exists():
                validation_result["issues"].append("IPFS Cluster service binary not found")
                validation_result["valid"] = False
            
        except Exception as e:
            validation_result["issues"].append(f"Validation error: {str(e)}")
            validation_result["valid"] = False
            
        return validation_result
    
    def _check_port_availability(self) -> Dict[str, Any]:
        """Check if required ports are available.
        
        Returns:
            Dict with port availability status
        """
        import socket
        
        result = {
            "api_port_available": True,
            "api_port": self.config.api_port,
            "conflicts": []
        }
        
        try:
            # Check API port
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                result_code = s.connect_ex(('127.0.0.1', self.config.api_port))
                if result_code == 0:
                    result["api_port_available"] = False
                    result["conflicts"].append({
                        "port": self.config.api_port,
                        "type": "api",
                        "status": "in_use"
                    })
                    
        except Exception as e:
            result["error"] = str(e)
            result["api_port_available"] = False
            
        return result
    
    async def start_cluster_service(self, force_restart: bool = False) -> Dict[str, Any]:
        """Start IPFS Cluster service daemon.
        
        Args:
            force_restart: Force restart even if already running
            
        Returns:
            Dict with startup results
        """
        result = {
            "success": False,
            "status": "unknown",
            "pid": None,
            "api_responsive": False,
            "errors": []
        }
        
        try:
            # Check if already running
            if not force_restart and await self._is_service_running():
                if await self._check_service_api_health():
                    result["success"] = True
                    result["status"] = "already_running_healthy"
                    result["api_responsive"] = True
                    result["pid"] = self.service_status.get("pid")
                    return result
                else:
                    logger.warning("Cluster service running but API unhealthy, restarting...")
                    await self.stop_cluster_service()
            
            # Auto-heal configuration if needed
            heal_result = self.config.auto_heal_cluster_config()
            if heal_result["actions_taken"]:
                logger.info(f"Configuration auto-healing: {', '.join(heal_result['actions_taken'])}")
            if not heal_result["success"]:
                result["errors"].extend(heal_result["errors"])
                return result
            
            # Ensure configuration exists
            config_result = self.config.ensure_config_exists()
            if not config_result["success"]:
                result["errors"].extend(config_result["errors"])
                return result
            
            # Clean up any stale processes or locks
            cleanup_result = await self._cleanup_cluster_resources()
            if cleanup_result.get("processes_killed"):
                logger.info(f"Cleaned up {len(cleanup_result['processes_killed'])} stale processes")
            
            # Start the service
            start_result = await self._start_cluster_service_daemon()
            if not start_result["success"]:
                result["errors"].extend(start_result.get("errors", []))
                return result
            
            result["pid"] = start_result.get("pid")
            
            # Wait for API to be responsive
            api_ready = await self._wait_for_service_api(timeout=30)
            if api_ready:
                result["success"] = True
                result["status"] = "started_healthy"
                result["api_responsive"] = True
                logger.info("IPFS Cluster service started and API is responsive")
            else:
                result["status"] = "started_unhealthy"
                result["errors"].append("Service started but API not responsive")
                logger.warning("Cluster service started but API not responsive")
                
        except Exception as e:
            logger.error(f"Error starting cluster service: {e}")
            result["errors"].append(str(e))
            
        return result
    
    async def stop_cluster_service(self) -> Dict[str, Any]:
        """Stop IPFS Cluster service daemon.
        
        Returns:
            Dict with stop results
        """
        result = {
            "success": False,
            "status": "unknown",
            "processes_stopped": [],
            "errors": []
        }
        
        try:
            # Find and stop cluster service processes
            processes = await self._find_cluster_service_processes()
            
            if not processes:
                result["success"] = True
                result["status"] = "already_stopped"
                return result
            
            # Graceful shutdown first
            for proc_info in processes:
                try:
                    proc = psutil.Process(proc_info["pid"])
                    proc.terminate()
                    result["processes_stopped"].append({
                        "pid": proc_info["pid"],
                        "method": "terminate"
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                    logger.debug(f"Process {proc_info['pid']} already gone or access denied: {e}")
            
            # Wait for graceful shutdown
            await anyio.sleep(3)
            
            # Force kill if still running
            remaining_processes = await self._find_cluster_service_processes()
            for proc_info in remaining_processes:
                try:
                    proc = psutil.Process(proc_info["pid"])
                    proc.kill()
                    result["processes_stopped"].append({
                        "pid": proc_info["pid"],
                        "method": "kill"
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                    logger.debug(f"Process {proc_info['pid']} already gone or access denied: {e}")
            
            # Clean up resources
            await self._cleanup_cluster_resources()
            
            result["success"] = True
            result["status"] = "stopped"
            logger.info("IPFS Cluster service stopped successfully")
            
        except Exception as e:
            logger.error(f"Error stopping cluster service: {e}")
            result["errors"].append(str(e))
            
        return result
    
    async def restart_cluster_service(self) -> Dict[str, Any]:
        """Restart IPFS Cluster service daemon.
        
        Returns:
            Dict with restart results
        """
        result = {
            "success": False,
            "stop_result": None,
            "start_result": None
        }
        
        try:
            # Stop the service
            stop_result = await self.stop_cluster_service()
            result["stop_result"] = stop_result
            
            # Wait a moment for cleanup
            await anyio.sleep(2)
            
            # Start the service
            start_result = await self.start_cluster_service()
            result["start_result"] = start_result
            
            result["success"] = start_result.get("success", False)
            
        except Exception as e:
            logger.error(f"Error restarting cluster service: {e}")
            result["error"] = str(e)
            
        return result
    
    async def get_cluster_service_status(self) -> Dict[str, Any]:
        """Get comprehensive status of cluster service.
        
        Returns:
            Dict with detailed status information
        """
        status = {
            "running": False,
            "api_responsive": False,
            "pid": None,
            "version": None,
            "peer_count": 0,
            "port_status": {},
            "config_valid": False,
            "last_check": datetime.now().isoformat(),
            "errors": []
        }
        
        try:
            # Check if process is running
            status["running"] = await self._is_service_running()
            
            if status["running"]:
                processes = await self._find_cluster_service_processes()
                if processes:
                    status["pid"] = processes[0]["pid"]
                
                # Check API health
                status["api_responsive"] = await self._check_service_api_health()
                
                if status["api_responsive"]:
                    # Get version info
                    version_info = await self._get_service_version()
                    if version_info:
                        status["version"] = version_info.get("version")
                    
                    # Get peer count
                    peer_info = await self._get_service_peers()
                    if peer_info:
                        status["peer_count"] = len(peer_info) if isinstance(peer_info, list) else 0
            
            # Check port availability
            status["port_status"] = await self._check_cluster_ports()
            
            # Check configuration
            status["config_valid"] = self.config._validate_config()
            
        except Exception as e:
            logger.error(f"Error getting cluster service status: {e}")
            status["errors"].append(str(e))
            
        return status
    
    async def _start_cluster_service_daemon(self) -> Dict[str, Any]:
        """Start the cluster service daemon process.
        
        Returns:
            Dict with start results
        """
        result = {"success": False, "pid": None, "errors": []}
        
        try:
            cluster_bin = self.config._get_cluster_binary_path()
            if not cluster_bin:
                result["errors"].append("IPFS Cluster binary not found")
                return result
            
            # Set environment
            env = os.environ.copy()
            env["IPFS_CLUSTER_PATH"] = str(self.config.cluster_path)
            
            # Start daemon
            cmd = [cluster_bin, "daemon"]
            
            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid  # Create new process group
            )
            
            # Wait a moment for startup
            await anyio.sleep(2)
            
            # Check if process is still running
            if process.poll() is None:
                result["success"] = True
                result["pid"] = process.pid
                self.service_process = process
                logger.info(f"Cluster service daemon started with PID {process.pid}")
            else:
                stdout, stderr = process.communicate()
                result["errors"].append(f"Daemon exited immediately: {stderr.decode()}")
                
        except Exception as e:
            logger.error(f"Error starting cluster daemon: {e}")
            result["errors"].append(str(e))
            
        return result
    
    async def _is_service_running(self) -> bool:
        """Check if cluster service is running.
        
        Returns:
            True if service is running
        """
        try:
            processes = await self._find_cluster_service_processes()
            return len(processes) > 0
        except Exception:
            return False
    
    async def _find_cluster_service_processes(self) -> List[Dict[str, Any]]:
        """Find running cluster service processes.
        
        Returns:
            List of process information dicts
        """
        processes = []
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    pinfo = proc.info
                    if pinfo['name'] and 'ipfs-cluster-service' in pinfo['name']:
                        processes.append({
                            "pid": pinfo['pid'],
                            "name": pinfo['name'],
                            "cmdline": pinfo.get('cmdline', [])
                        })
                    elif pinfo['cmdline'] and any('ipfs-cluster-service' in cmd for cmd in pinfo['cmdline']):
                        processes.append({
                            "pid": pinfo['pid'],
                            "name": pinfo['name'],
                            "cmdline": pinfo['cmdline']
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                    
        except Exception as e:
            logger.error(f"Error finding cluster processes: {e}")
            
        return processes
    
    async def _check_service_api_health(self, timeout: int = 5) -> bool:
        """Check if cluster service API is responsive.
        
        Args:
            timeout: Request timeout in seconds
            
        Returns:
            True if API is responsive
        """
        try:
            import httpx
            
            async with httpx.AsyncClient(timeout=timeout) as client:
                # Use the correct IPFS Cluster API endpoint (no /api/v0/ prefix)
                response = await client.get(f"http://127.0.0.1:{self.config.api_port}/version")
                return response.status_code == 200
                
        except Exception:
            return False
    
    async def _wait_for_service_api(self, timeout: int = 30) -> bool:
        """Wait for cluster service API to become responsive.
        
        Args:
            timeout: Maximum wait time in seconds
            
        Returns:
            True if API becomes responsive within timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if await self._check_service_api_health():
                return True
            await anyio.sleep(1)
            
        return False
    
    async def _get_service_version(self) -> Optional[Dict[str, Any]]:
        """Get cluster service version information.
        
        Returns:
            Version info dict or None if unavailable
        """
        try:
            import httpx
            
            async with httpx.AsyncClient(timeout=5) as client:
                # Use the correct IPFS Cluster API endpoint (no /api/v0/ prefix)
                response = await client.get(f"http://127.0.0.1:{self.config.api_port}/version")
                if response.status_code == 200:
                    return response.json()
                    
        except Exception as e:
            logger.debug(f"Error getting service version: {e}")
            
        return None
    
    async def _get_service_peers(self) -> Optional[List[Dict[str, Any]]]:
        """Get cluster service peer information.
        
        Returns:
            List of peer info dicts or None if unavailable
        """
        try:
            import httpx
            
            async with httpx.AsyncClient(timeout=5) as client:
                # Use the correct IPFS Cluster API endpoint (no /api/v0/ prefix)
                response = await client.get(f"http://127.0.0.1:{self.config.api_port}/peers")
                if response.status_code == 200:
                    return response.json()
                    
        except Exception as e:
            logger.debug(f"Error getting service peers: {e}")
            
        return None
    
    async def _check_cluster_ports(self) -> Dict[str, Dict[str, Any]]:
        """Check status of cluster-related ports.
        
        Returns:
            Dict with port status information
        """
        ports = {
            "api": self.config.api_port,
            "proxy": self.config.proxy_port,
            "cluster": self.config.cluster_port
        }
        
        port_status = {}
        
        for port_name, port_num in ports.items():
            port_status[port_name] = {
                "port": port_num,
                "in_use": False,
                "processes": []
            }
            
            try:
                for conn in psutil.net_connections():
                    if hasattr(conn, 'laddr') and conn.laddr and hasattr(conn.laddr, 'port') and conn.laddr.port == port_num:
                        port_status[port_name]["in_use"] = True
                        
                        if conn.pid:
                            try:
                                proc = psutil.Process(conn.pid)
                                port_status[port_name]["processes"].append({
                                    "pid": conn.pid,
                                    "name": proc.name(),
                                    "cmdline": proc.cmdline()
                                })
                            except psutil.NoSuchProcess:
                                pass
                                
            except Exception as e:
                logger.debug(f"Error checking port {port_num}: {e}")
                
        return port_status
    
    async def _cleanup_cluster_resources(self) -> Dict[str, Any]:
        """Clean up cluster-related resources (lock files, stale processes).
        
        Returns:
            Dict with cleanup results
        """
        result = {
            "processes_killed": [],
            "files_removed": [],
            "ports_cleaned": []
        }
        
        try:
            # Remove lock files
            lock_files = [
                os.path.join(self.config.cluster_path, "cluster.lock"),
                os.path.join(self.config.cluster_path, "api"),
                os.path.join(self.config.cluster_path, ".lock")
            ]
            
            for lock_file in lock_files:
                if os.path.exists(lock_file):
                    try:
                        os.remove(lock_file)
                        result["files_removed"].append(lock_file)
                        logger.info(f"Removed lock file: {lock_file}")
                    except Exception as e:
                        logger.warning(f"Failed to remove lock file {lock_file}: {e}")
            
            # Clean up processes using cluster ports
            port_status = await self._check_cluster_ports()
            for port_name, port_info in port_status.items():
                if port_info["in_use"]:
                    for proc_info in port_info["processes"]:
                        try:
                            proc = psutil.Process(proc_info["pid"])
                            proc.terminate()
                            result["processes_killed"].append(proc_info["pid"])
                            result["ports_cleaned"].append(port_info["port"])
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                            
        except Exception as e:
            logger.error(f"Error cleaning up cluster resources: {e}")
            
        return result
    
    def get_api_client(self, host: str = "127.0.0.1", port: Optional[int] = None, auth: Optional[Dict[str, str]] = None):
        """Get API client for cluster service.
        
        Args:
            host: API host (default: 127.0.0.1)
            port: API port (default: from config)
            auth: Authentication credentials
            
        Returns:
            API client instance
        """
        if port is None:
            port = self.config.api_port
            
        api_url = f"http://{host}:{port}"
        return IPFSClusterAPIClient(api_url, auth)
    
    def get_ctl_wrapper(self, host: str = "127.0.0.1", port: Optional[int] = None):
        """Get cluster-ctl wrapper for command line operations.
        
        Args:
            host: API host (default: 127.0.0.1)
            port: API port (default: from config)
            
        Returns:
            Cluster-ctl wrapper instance
        """
        if port is None:
            port = self.config.api_port
            
        api_url = f"http://{host}:{port}"
        return IPFSClusterCTLWrapper(api_url)
    
    async def connect_to_networked_cluster(self, remote_host: str, remote_port: int = 9094, 
                                         auth: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Connect to a remote IPFS Cluster using REST API.
        
        Args:
            remote_host: Remote cluster host
            remote_port: Remote cluster API port
            auth: Authentication credentials for remote cluster
            
        Returns:
            Connection status and remote cluster info
        """
        result = {
            "success": False,
            "connected": False,
            "remote_info": {},
            "errors": []
        }
        
        try:
            # Create API client for remote cluster
            remote_client = self.get_api_client(remote_host, remote_port, auth)
            
            async with remote_client:
                # Authenticate if credentials provided
                if auth:
                    auth_success = await remote_client.authenticate()
                    if not auth_success:
                        result["errors"].append("Authentication failed")
                        return result
                
                # Get remote cluster info
                id_response = await remote_client.get_id()
                if id_response.get("success"):
                    result["remote_info"]["id"] = id_response
                    result["connected"] = True
                    
                # Get peers
                peers_response = await remote_client.get_peers()
                if peers_response.get("success"):
                    result["remote_info"]["peers"] = peers_response
                    
                # Get version
                version_response = await remote_client.get_version()
                if version_response.get("success"):
                    result["remote_info"]["version"] = version_response
                    
                # Check health
                health_response = await remote_client.health_check()
                if health_response.get("success"):
                    result["remote_info"]["health"] = health_response
                    
                result["success"] = result["connected"]
                
        except Exception as e:
            result["errors"].append(f"Connection error: {str(e)}")
            logger.error(f"Failed to connect to remote cluster {remote_host}:{remote_port}: {e}")
            
        return result
    
    async def add_peer_to_cluster(self, peer_multiaddr: str) -> Dict[str, Any]:
        """Add a peer to the cluster using API.
        
        Args:
            peer_multiaddr: Multiaddr of the peer to add
            
        Returns:
            Operation result
        """
        result = {
            "success": False,
            "peer_added": False,
            "errors": []
        }
        
        try:
            # Use cluster-ctl to add peer
            ctl = self.get_ctl_wrapper()
            cmd_result = await ctl.run_command(["peers", "add", peer_multiaddr])
            
            if cmd_result.get("success"):
                result["success"] = True
                result["peer_added"] = True
                result["output"] = cmd_result.get("stdout", "")
            else:
                result["errors"].append(cmd_result.get("stderr", "Unknown error"))
                
        except Exception as e:
            result["errors"].append(f"Error adding peer: {str(e)}")
            logger.error(f"Failed to add peer {peer_multiaddr}: {e}")
            
        return result
    
    async def pin_content_to_cluster(self, cid: str, **options) -> Dict[str, Any]:
        """Pin content to the cluster using API.
        
        Args:
            cid: Content ID to pin
            **options: Additional pin options (replication-factor, name, etc.)
            
        Returns:
            Pin operation result
        """
        result = {
            "success": False,
            "pinned": False,
            "cid": cid,
            "errors": []
        }
        
        try:
            # Use API client to pin content
            api_client = self.get_api_client()
            
            async with api_client:
                pin_response = await api_client.pin_cid(cid, **options)
                
                if pin_response.get("success"):
                    result["success"] = True
                    result["pinned"] = True
                    result["pin_info"] = pin_response
                else:
                    result["errors"].append(pin_response.get("error", "Unknown pin error"))
                    
        except Exception as e:
            result["errors"].append(f"Error pinning content: {str(e)}")
            logger.error(f"Failed to pin content {cid}: {e}")
            
        return result
    
    async def get_cluster_status_via_api(self) -> Dict[str, Any]:
        """Get comprehensive cluster status using REST API.
        
        Returns:
            Cluster status information
        """
        result = {
            "success": False,
            "api_responsive": False,
            "cluster_info": {},
            "errors": []
        }
        
        try:
            api_client = self.get_api_client()
            
            async with api_client:
                # Test API responsiveness
                health_response = await api_client.health_check()
                if health_response.get("success"):
                    result["api_responsive"] = True
                    
                # Get cluster ID and info
                id_response = await api_client.get_id()
                if id_response.get("success"):
                    result["cluster_info"]["id"] = id_response
                    
                # Get peers
                peers_response = await api_client.get_peers()
                if peers_response.get("success"):
                    result["cluster_info"]["peers"] = peers_response
                    
                # Get pins
                pins_response = await api_client.get_pins()
                if pins_response.get("success"):
                    result["cluster_info"]["pins"] = pins_response
                    
                # Get metrics
                metrics_response = await api_client.get_metrics()
                if metrics_response.get("success"):
                    result["cluster_info"]["metrics"] = metrics_response
                    
                result["success"] = True
                
        except Exception as e:
            result["errors"].append(f"API status check error: {str(e)}")
            logger.error(f"Failed to get cluster status via API: {e}")
            
        return result

    async def _get_cluster_metrics(self) -> Dict[str, Any]:
        """
        Fetch various metrics from the IPFS Cluster API.
        
        Returns:
            A dictionary containing IPFS Cluster metrics.
        """
        metrics = {
            "pin_count": 0,
            "repo_size": 0,
            "peer_count": 0,
            "allocated_space": 0,
            "free_space": 0
        }

        try:
            api_client = self.get_api_client()
            async with api_client:
                # Get pin count
                try:
                    pins_response = await api_client.get_pins()
                    if isinstance(pins_response, dict) and pins_response.get("success"):
                        metrics["pin_count"] = len(pins_response.get("pins", []))
                    else:
                        logger.warning(f"Could not get IPFS Cluster pin count: {pins_response}")
                except Exception as e:
                    logger.warning(f"Could not get IPFS Cluster pin count: {e}")

                # Get metrics (which includes repo size, allocated space, free space)
                try:
                    metrics_response = await api_client.get_metrics()
                    if isinstance(metrics_response, dict) and metrics_response.get("success"):
                        metrics_data = metrics_response.get("metrics", {})
                        metrics["repo_size"] = metrics_data.get("repo_size", 0)
                        metrics["allocated_space"] = metrics_data.get("allocated_space", 0)
                        metrics["free_space"] = metrics_data.get("free_space", 0)
                    else:
                        logger.warning(f"Could not get IPFS Cluster general metrics: {metrics_response}")
                except Exception as e:
                    logger.warning(f"Could not get IPFS Cluster general metrics: {e}")

                # Get peer count
                try:
                    peers_response = await api_client.get_peers()
                    if isinstance(peers_response, dict) and peers_response.get("success"):
                        metrics["peer_count"] = len(peers_response.get("peers", []))
                    else:
                        logger.warning(f"Could not get IPFS Cluster peer count: {peers_response}")
                except Exception as e:
                    logger.warning(f"Could not get IPFS Cluster peer count: {e}")

        except Exception as e:
            logger.error(f"Error fetching IPFS Cluster metrics: {e}")

        return metrics

    async def config_create(self, **config_params) -> Dict[str, Any]:
        """Create cluster configuration.
        
        Args:
            **config_params: Configuration parameters
            
        Returns:
            Dict with creation result
        """
        try:
            return self.config.config_create(**config_params)
        except Exception as e:
            logger.error(f"Error creating config: {e}")
            return {"success": False, "error": str(e)}

    async def config_get(self) -> Dict[str, Any]:
        """Get cluster configuration.
        
        Returns:
            Dict with configuration data
        """
        try:
            return self.config.config_get()
        except Exception as e:
            logger.error(f"Error getting config: {e}")
            return {"success": False, "error": str(e)}

    async def config_set(self, **config_params) -> Dict[str, Any]:
        """Set cluster configuration.
        
        Args:
            **config_params: Configuration parameters
            
        Returns:
            Dict with update result
        """
        try:
            return self.config.config_set(config_params)
        except Exception as e:
            logger.error(f"Error setting config: {e}")
            return {"success": False, "error": str(e)}


# Convenience functions for external use
async def start_cluster_service(**kwargs) -> Dict[str, Any]:
    """Start IPFS Cluster service daemon.
    
    Returns:
        Dict with startup results
    """
    manager = IPFSClusterDaemonManager()
    return await manager.start_cluster_service(**kwargs)

async def stop_cluster_service() -> Dict[str, Any]:
    """Stop IPFS Cluster service daemon.
    
    Returns:
        Dict with stop results
    """
    manager = IPFSClusterDaemonManager()
    return await manager.stop_cluster_service()

async def get_cluster_service_status() -> Dict[str, Any]:
    """Get IPFS Cluster service status.
    
    Returns:
        Dict with status information
    """
    manager = IPFSClusterDaemonManager()
    return await manager.get_cluster_service_status()

async def restart_cluster_service() -> Dict[str, Any]:
    """Restart IPFS Cluster service daemon.
    
    Returns:
        Dict with restart results
    """
    manager = IPFSClusterDaemonManager()
    return await manager.restart_cluster_service()
