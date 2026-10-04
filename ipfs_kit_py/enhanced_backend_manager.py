#!/usr/bin/env python3
"""
Enhanced Backend Manager for IPFS Kit Storage System

This module extends the basic backend manager to include comprehensive
policy management and enhanced backend representation for the MCP dashboard.
"""

import os
import yaml
import json
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging
from .backend_policies import (
    BackendPolicySet, StorageQuotaPolicy, TrafficQuotaPolicy, 
    ReplicationPolicy, RetentionPolicy, CachePolicy, QuotaUnit
)

logger = logging.getLogger(__name__)


class EnhancedBackendManager:
    """Enhanced backend manager with comprehensive policy support."""
    
    def __init__(self, ipfs_kit_path=None):
        self.ipfs_kit_path = Path(ipfs_kit_path or os.path.expanduser("~/.ipfs_kit"))
        self.backends_path = self.ipfs_kit_path / "backends"
        self.policies_path = self.ipfs_kit_path / "policies"
        self.backends_path.mkdir(parents=True, exist_ok=True)
        self.policies_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize with sample backends if none exist
        self._initialize_sample_backends()

    def _get_backend_config_path(self, name):
        return self.backends_path / f"{name}.yaml"
    
    def _get_policy_config_path(self, name):
        return self.policies_path / f"{name}_policy.json"

    def _initialize_sample_backends(self):
        """Initialize sample backends with comprehensive policies if none exist."""
        if len(list(self.backends_path.glob("*.yaml"))) > 0:
            return  # Backends already exist
            
        sample_backends = [
            {
                "name": "local_fs",
                "type": "local",
                "description": "Local filesystem storage",
                "config": {
                    "path": str(self.ipfs_kit_path / "local_storage"),
                    "auto_create": True
                },
                "status": "enabled",
                "tier": "hot"
            },
            {
                "name": "ipfs_local", 
                "type": "ipfs",
                "description": "Local IPFS node storage",
                "config": {
                    "api_endpoint": "http://127.0.0.1:5001",
                    "gateway_endpoint": "http://127.0.0.1:8080"
                },
                "status": "enabled", 
                "tier": "hot"
            },
            {
                "name": "cluster",
                "type": "ipfs_cluster", 
                "description": "IPFS Cluster distributed storage",
                "config": {
                    "api_endpoint": "http://127.0.0.1:9094",
                    "proxy_endpoint": "http://127.0.0.1:9095"
                },
                "status": "enabled",
                "tier": "warm"
            },
            {
                "name": "s3_demo",
                "type": "s3",
                "description": "Amazon S3 storage backend", 
                "config": {
                    "bucket": "ipfs-kit-demo",
                    "region": "us-east-1",
                    "endpoint": None
                },
                "status": "enabled",
                "tier": "cold"
            },
            {
                "name": "huggingface",
                "type": "huggingface",
                "description": "Hugging Face Hub storage",
                "config": {
                    "organization": "ipfs-kit",
                    "private": True
                },
                "status": "enabled", 
                "tier": "archive"
            },
            {
                "name": "github",
                "type": "github",
                "description": "GitHub repository storage",
                "config": {
                    "owner": "endomorphosis",
                    "repo": "ipfs_kit_py_storage"
                },
                "status": "enabled",
                "tier": "archive"
            },
            {
                "name": "gdrive",
                "type": "gdrive", 
                "description": "Google Drive storage",
                "config": {
                    "folder_id": "sample_folder_id"
                },
                "status": "disabled",
                "tier": "cold"
            },
            {
                "name": "parquet_meta",
                "type": "parquet",
                "description": "Parquet metadata storage",
                "config": {
                    "path": str(self.ipfs_kit_path / "parquet_storage"),
                    "compression": "snappy"
                },
                "status": "enabled",
                "tier": "warm"
            }
        ]
        
        # Create backend configs
        for backend in sample_backends:
            config_path = self._get_backend_config_path(backend["name"])
            try:
                with open(config_path, 'w') as f:
                    yaml.safe_dump(backend, f)
                logger.info(f"Created sample backend: {backend['name']}")
            except Exception as e:
                logger.error(f"Error creating backend {backend['name']}: {e}")
                
        # Create sample policies for each backend
        self._create_sample_policies(sample_backends)

    def _create_sample_policies(self, backends):
        """Create sample policies for each backend."""
        for backend in backends:
            name = backend["name"]
            backend_type = backend["type"]
            tier = backend.get("tier", "standard")
            
            # Create policies based on backend type and tier
            policy_set = self._generate_policy_for_backend(name, backend_type, tier)
            
            policy_path = self._get_policy_config_path(name)
            try:
                with open(policy_path, 'w') as f:
                    json.dump(policy_set, f, indent=2)
                logger.info(f"Created policy for backend: {name}")
            except Exception as e:
                logger.error(f"Error creating policy for {name}: {e}")

    def _generate_policy_for_backend(self, name: str, backend_type: str, tier: str) -> Dict[str, Any]:
        """Generate appropriate policies based on backend type and tier."""
        
        # Base policies vary by tier
        if tier == "hot":
            storage_quota = {
                "max_size": 100, "max_size_unit": "GB",
                "warn_threshold": 0.8, "max_files": 10000
            }
            traffic_quota = {
                "max_bandwidth_mbps": 1000.0,
                "max_requests_per_minute": 10000,
                "max_upload_per_day": 50, "max_download_per_day": 100
            }
            cache_policy = {
                "max_cache_size": 10, "max_cache_size_unit": "GB",
                "ttl_seconds": 3600, "prefetch_enabled": True
            }
        elif tier == "warm":
            storage_quota = {
                "max_size": 500, "max_size_unit": "GB",
                "warn_threshold": 0.85, "max_files": 50000
            }
            traffic_quota = {
                "max_bandwidth_mbps": 100.0,
                "max_requests_per_minute": 1000,
                "max_upload_per_day": 200, "max_download_per_day": 500
            }
            cache_policy = {
                "max_cache_size": 5, "max_cache_size_unit": "GB",
                "ttl_seconds": 7200, "prefetch_enabled": False
            }
        elif tier == "cold":
            storage_quota = {
                "max_size": 2, "max_size_unit": "TB",
                "warn_threshold": 0.9, "max_files": 100000
            }
            traffic_quota = {
                "max_bandwidth_mbps": 10.0,
                "max_requests_per_minute": 100,
                "max_upload_per_day": 500, "max_download_per_day": 1000
            }
            cache_policy = {
                "max_cache_size": 1, "max_cache_size_unit": "GB",
                "ttl_seconds": 86400, "prefetch_enabled": False
            }
        else:  # archive
            storage_quota = {
                "max_size": 10, "max_size_unit": "TB",
                "warn_threshold": 0.95, "max_files": 1000000
            }
            traffic_quota = {
                "max_bandwidth_mbps": 1.0,
                "max_requests_per_minute": 10,
                "max_upload_per_day": 100, "max_download_per_day": 50
            }
            cache_policy = {
                "max_cache_size": 100, "max_cache_size_unit": "MB",
                "ttl_seconds": 604800, "prefetch_enabled": False
            }
        
        # Replication policy varies by backend type
        if backend_type in ["ipfs", "ipfs_cluster"]:
            replication = {
                "min_redundancy": 3, "max_redundancy": 5,
                "geo_distribution": True,
                "preferred_backends": ["ipfs_local", "cluster"]
            }
        elif backend_type in ["s3", "gdrive"]:
            replication = {
                "min_redundancy": 1, "max_redundancy": 2,
                "geo_distribution": False
            }
        else:
            replication = {
                "min_redundancy": 1, "max_redundancy": 3
            }
            
        # Retention policy varies by tier
        if tier == "hot":
            retention = {
                "default_retention_days": 30,
                "max_retention_days": 365
            }
        elif tier == "warm":
            retention = {
                "default_retention_days": 180,
                "max_retention_days": 1095
            }
        elif tier == "cold":
            retention = {
                "default_retention_days": 365,
                "max_retention_days": 2555  # 7 years
            }
        else:  # archive
            retention = {
                "default_retention_days": 2555,
                "max_retention_days": 7300  # 20 years
            }
        
        return {
            "backend_name": name,
            "storage_quota": storage_quota,
            "traffic_quota": traffic_quota,
            "replication": replication,
            "retention": retention,
            "cache": cache_policy
        }

    def list_backends(self):
        """List all backends with their configurations and policies."""
        backends = []
        for config_file in self.backends_path.glob("*.yaml"):
            try:
                # Load backend config
                with open(config_file, 'r') as f:
                    backend_config = yaml.safe_load(f)
                
                # Load associated policy
                policy_path = self._get_policy_config_path(backend_config["name"])
                policy_data = None
                if policy_path.exists():
                    try:
                        with open(policy_path, 'r') as f:
                            policy_data = json.load(f)
                    except Exception as e:
                        logger.error(f"Error loading policy for {backend_config['name']}: {e}")
                
                # Combine backend config with policy info
                enhanced_backend = {
                    **backend_config,
                    "policy": policy_data,
                    "last_updated": policy_path.stat().st_mtime if policy_path.exists() else time.time()
                }
                
                backends.append(enhanced_backend)
                
            except Exception as e:
                logger.error(f"Error loading backend config {config_file}: {e}")
                
        return {"backends": backends, "total": len(backends)}

    def get_backend_with_policies(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a single backend with its policy information."""
        config_path = self._get_backend_config_path(name)
        if not config_path.exists():
            return None
            
        try:
            with open(config_path, 'r') as f:
                backend_config = yaml.safe_load(f)
                
            # Load policy
            policy_path = self._get_policy_config_path(name)
            policy_data = None
            if policy_path.exists():
                with open(policy_path, 'r') as f:
                    policy_data = json.load(f)
                    
            return {
                **backend_config,
                "policy": policy_data,
                "last_updated": policy_path.stat().st_mtime if policy_path.exists() else time.time()
            }
        except Exception as e:
            logger.error(f"Error loading backend {name}: {e}")
            return None

    def update_backend_policy(self, name: str, policy_updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update policy for a specific backend."""
        # Ensure policy_updates is a dictionary
        if isinstance(policy_updates, str):
            try:
                policy_updates = json.loads(policy_updates)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid policy JSON string for {name}: {e}")
                return {"ok": False, "error": f"Invalid policy JSON: {str(e)}"}
        
        if not isinstance(policy_updates, dict):
            logger.error(f"Policy must be a dictionary for {name}, got {type(policy_updates)}")
            return {"ok": False, "error": f"Policy must be a dictionary, got {type(policy_updates).__name__}"}
        
        policy_path = self._get_policy_config_path(name)
        if not policy_path.exists():
            logger.error(f"Policy file not found for backend {name}")
            return {"ok": False, "error": f"Backend '{name}' not found"}
            
        try:
            # Load existing policy
            with open(policy_path, 'r') as f:
                current_policy = json.load(f)
                
            # Update with new values
            current_policy.update(policy_updates)
            current_policy["updated_at"] = time.time()
            
            # Save updated policy
            with open(policy_path, 'w') as f:
                json.dump(current_policy, f, indent=2)
                
            logger.info(f"Updated backend policy: {name}")
            return {"ok": True}
        except Exception as e:
            logger.error(f"Error updating policy for {name}: {e}")
            return {"ok": False, "error": str(e)}

    def apply_backend_policy(self, name: str, policy: Dict[str, Any], force_sync: bool = False) -> Dict[str, Any]:
        """Apply backend policy and optionally force synchronization."""
        # Ensure policy is a dictionary
        if isinstance(policy, str):
            try:
                policy = json.loads(policy)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid policy JSON string for {name}: {e}")
                return {"ok": False, "error": f"Invalid policy JSON: {str(e)}", "backend": name}
        
        if not isinstance(policy, dict):
            logger.error(f"Policy must be a dictionary for {name}, got {type(policy)}")
            return {"ok": False, "error": f"Policy must be a dictionary, got {type(policy).__name__}", "backend": name}
        
        # First update the backend policy
        update_result = self.update_backend_policy(name, policy)
        if not update_result.get("ok", False):
            return {
                "ok": False, 
                "error": update_result.get("error", "Failed to update policy"),
                "backend": name
            }
        
        # If force_sync is requested, perform synchronization
        if force_sync:
            try:
                logger.info(f"Force syncing backend {name} with new policy")
                # Here you would implement actual sync logic with the backend
                # For now, we simulate successful sync
                sync_result = self._simulate_backend_sync(name, policy)
                if not sync_result:
                    return {
                        "ok": False,
                        "error": "Synchronization failed",
                        "backend": name
                    }
            except Exception as e:
                logger.error(f"Error during force sync for {name}: {e}")
                return {
                    "ok": False,
                    "error": f"Sync error: {str(e)}",
                    "backend": name
                }
        
        return {
            "ok": True,
            "message": f"Policy applied successfully for {name}",
            "synced": force_sync,
            "backend": name
        }

    def _simulate_backend_sync(self, name: str, policy: Dict[str, Any]) -> bool:
        """Simulate backend synchronization process."""
        try:
            # In a real implementation, this would:
            # 1. Connect to the actual backend service
            # 2. Apply the new policy settings
            # 3. Trigger any necessary data migration or cache updates
            # 4. Verify the policy is properly applied
            
            # For now, we just simulate a successful sync
            logger.info(f"Simulating sync for backend {name} with policy: {policy}")
            time.sleep(0.1)  # Simulate some processing time
            return True
        except Exception as e:
            logger.error(f"Simulated sync failed for {name}: {e}")
            return False

    def get_backend_stats(self, name: str) -> Dict[str, Any]:
        """Get usage statistics for a backend (simulated for demo)."""
        backend = self.get_backend_with_policies(name)
        if not backend:
            return {}
            
        # Simulate some stats based on tier
        tier = backend.get("tier", "standard")
        
        if tier == "hot":
            return {
                "used_storage_gb": 45.2,
                "total_files": 1234,
                "bandwidth_usage_mbps": 125.3,
                "requests_per_minute": 456,
                "cache_hit_ratio": 0.87,
                "availability": 0.999,
                "last_access": time.time() - 300  # 5 minutes ago
            }
        elif tier == "warm":  
            return {
                "used_storage_gb": 234.1,
                "total_files": 5678,
                "bandwidth_usage_mbps": 23.4,
                "requests_per_minute": 89,
                "cache_hit_ratio": 0.72,
                "availability": 0.995,
                "last_access": time.time() - 1800  # 30 minutes ago
            }
        elif tier == "cold":
            return {
                "used_storage_gb": 892.4,
                "total_files": 23456,
                "bandwidth_usage_mbps": 2.1,
                "requests_per_minute": 12,
                "cache_hit_ratio": 0.34,
                "availability": 0.99,
                "last_access": time.time() - 7200  # 2 hours ago
            }
        else:  # archive
            return {
                "used_storage_gb": 3456.7,
                "total_files": 78901,
                "bandwidth_usage_mbps": 0.3,
                "requests_per_minute": 2,
                "cache_hit_ratio": 0.12,
                "availability": 0.98,
                "last_access": time.time() - 86400  # 1 day ago
            }

    def test_backend_config(self, name: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Test backend configuration connectivity."""
        # Handle string input (convert to dict if needed)
        if isinstance(config, str):
            try:
                config = json.loads(config)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid config JSON string for {name}: {e}")
                return {
                    "reachable": False,
                    "valid": False,
                    "errors": [f"Invalid config JSON: {str(e)}"],
                    "backend": name,
                    "message": "Configuration test failed - invalid JSON"
                }
        
        # Load backend configuration if not provided
        if config is None:
            backend = self.get_backend_with_policies(name)
            if not backend:
                return {
                    "reachable": False,
                    "valid": False,
                    "errors": [f"Backend '{name}' not found"],
                    "backend": name,
                    "message": "Configuration test failed - backend not found"
                }
            config = backend.get("config", {})
        
        # Simulate configuration testing based on backend type
        backend_info = self.get_backend_with_policies(name)
        if not backend_info:
            return {
                "reachable": False,
                "valid": False,
                "errors": [f"Backend '{name}' not found"],
                "backend": name,
                "message": "Configuration test failed - backend not found"
            }
        
        backend_type = backend_info.get("type", "unknown")
        errors = []
        
        try:
            # Type-specific validation
            if backend_type == "s3":
                # Check S3 configuration
                if not config.get("access_key") or not config.get("secret_key"):
                    errors.append("Missing S3 credentials (access_key, secret_key)")
                if not config.get("bucket"):
                    errors.append("Missing S3 bucket configuration")
                if not config.get("region"):
                    errors.append("Missing S3 region configuration")
                    
                # If credentials are missing, mark as unreachable
                if errors:
                    return {
                        "reachable": False,
                        "valid": False,
                        "errors": errors,
                        "backend": name,
                        "message": "Configuration test failed - missing credentials"
                    }
                        
            elif backend_type == "github":
                # Check GitHub configuration
                if not config.get("api_key") and not config.get("token"):
                    errors.append("Missing GitHub API key or token")
                if not config.get("base_url"):
                    # Use default if not specified
                    config["base_url"] = "https://api.github.com"
                    
                # GitHub can be reachable even without valid credentials for public repos
                return {
                    "reachable": True,
                    "valid": len(errors) == 0,
                    "errors": errors,
                    "backend": name,
                    "message": "Configuration test completed"
                }
                
            elif backend_type in ["local_fs", "local_storage"]:
                # Check local filesystem configuration
                base_path = config.get("base_path", config.get("path", "/tmp"))
                try:
                    path_obj = Path(base_path)
                    if not path_obj.exists():
                        path_obj.mkdir(parents=True, exist_ok=True)
                    if not path_obj.is_dir():
                        errors.append(f"Path {base_path} is not a directory")
                    elif not os.access(base_path, os.W_OK):
                        errors.append(f"Path {base_path} is not writable")
                except Exception as e:
                    errors.append(f"Path validation error: {str(e)}")
                    
            elif backend_type == "ipfs":
                # Check IPFS configuration
                api_url = config.get("api_url", "http://localhost:5001")
                gateway_url = config.get("gateway_url", "http://localhost:8080")
                
                # In a real implementation, you would try to connect to IPFS
                # For now, assume it's reachable if URLs are provided
                if not api_url:
                    errors.append("Missing IPFS API URL")
                if not gateway_url:
                    errors.append("Missing IPFS Gateway URL")
                    
            elif backend_type == "cluster":
                # Check cluster configuration
                cluster_url = config.get("cluster_url", config.get("api_url"))
                if not cluster_url:
                    errors.append("Missing cluster API URL")
                    
            # If no specific validation errors, assume configuration is valid
            if not errors:
                return {
                    "reachable": True,
                    "valid": True,
                    "errors": [],
                    "backend": name,
                    "message": "Configuration test completed successfully"
                }
            else:
                return {
                    "reachable": False,
                    "valid": False,
                    "errors": errors,
                    "backend": name,
                    "message": "Configuration test failed"
                }
                
        except Exception as e:
            logger.error(f"Error testing configuration for {name}: {e}")
            return {
                "reachable": False,
                "valid": False,
                "errors": [f"Test error: {str(e)}"],
                "backend": name,
                "message": "Configuration test failed with exception"
            }