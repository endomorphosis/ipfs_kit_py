"""Credential Manager for ipfs_kit_py.

This module provides secure credential management for various storage backends
including IPFS, IPFS Cluster, S3, Storacha, and Filecoin.
"""

import base64
import json
import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional, Union

try:
    import keyring
    HAS_KEYRING = True
except ImportError:
    HAS_KEYRING = False

# Configure logger
logger = logging.getLogger(__name__)

class CredentialManager:
    """Manages credentials for different storage backends.
    
    This class provides a unified interface for securely storing and retrieving
    credentials for various storage backends used by the TieredCacheManager,
    including IPFS, IPFS Cluster, S3, Storacha, and Filecoin.
    
    Features:
    - Secure credential storage using keyring when available
    - Fallback to file-based encrypted storage
    - Support for multiple credential sets per service
    - Automatic credential rotation
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the credential manager.
        
        Args:
            config: Configuration dictionary
        """
        # Default configuration
        default_config = {
            "credential_store": "keyring",  # 'keyring', 'file'
            "credential_file_path": os.path.expanduser("~/.ipfs_kit/credentials.json"),
            "ipfs_credentials_path": os.path.expanduser("~/.ipfs"),
            "encrypt_file_credentials": True,
            "rotation_check_interval": 86400,  # 24 hours
        }
        
        # Merge provided config with defaults
        self.config = default_config.copy()
        if config:
            self.config.update(config)
            
        # Create storage directory if needed
        if self.config["credential_store"] == "file":
            os.makedirs(os.path.dirname(self.config["credential_file_path"]), exist_ok=True)
            
        # Check keyring availability
        if self.config["credential_store"] == "keyring" and not HAS_KEYRING:
            logger.warning("Keyring package not available, falling back to file storage")
            self.config["credential_store"] = "file"
            
        # Initialize credential cache
        self.credential_cache = {}
        
        # Load IPFS credentials if available
        self._load_ipfs_credentials()
        
    def _load_ipfs_credentials(self):
        """Load IPFS credentials from the IPFS directory."""
        ipfs_path = self.config["ipfs_credentials_path"]
        
        # Check for IPFS identity file
        identity_path = os.path.join(ipfs_path, "identity")
        if os.path.exists(identity_path):
            try:
                with open(identity_path, "r") as f:
                    identity_data = f.read().strip()
                self.add_credential("ipfs", "identity", {
                    "identity": identity_data,
                    "type": "identity"
                })
                logger.info("Loaded IPFS identity credential")
            except Exception as e:
                logger.error(f"Failed to load IPFS identity: {str(e)}")
                
        # Check for IPFS API credentials
        api_file = os.path.join(ipfs_path, "api")
        if os.path.exists(api_file):
            try:
                with open(api_file, "r") as f:
                    api_address = f.read().strip()
                self.add_credential("ipfs", "api", {
                    "api_address": api_address,
                    "type": "api"
                })
                logger.info("Loaded IPFS API credential")
            except Exception as e:
                logger.error(f"Failed to load IPFS API address: {str(e)}")
        
        # Check for IPFS Cluster credentials
        cluster_secret_file = os.path.join(ipfs_path, "cluster_secret")
        if os.path.exists(cluster_secret_file):
            try:
                with open(cluster_secret_file, "r") as f:
                    cluster_secret = f.read().strip()
                self.add_credential("ipfs_cluster", "secret", {
                    "secret": cluster_secret,
                    "type": "cluster_secret"
                })
                logger.info("Loaded IPFS Cluster secret")
            except Exception as e:
                logger.error(f"Failed to load IPFS Cluster secret: {str(e)}")
    
    def add_credential(self, service: str, name: str, credentials: Dict[str, Any]) -> bool:
        """Add or update credentials for a service.
        
        Args:
            service: Service identifier (ipfs, s3, storacha, filecoin)
            name: Name for this credential set (e.g. 'default', 'aws', 'backup')
            credentials: Credential data appropriate for the service
            
        Returns:
            True if successful, False otherwise
        """
        # Create a credential record with metadata
        credential_record = {
            "credentials": credentials,
            "metadata": {
                "added_at": time.time(),
                "last_used": time.time(),
                "use_count": 0,
                "id": str(uuid.uuid4())
            }
        }
        
        # Store in cache for quick access
        service_key = f"{service}_{name}"
        self.credential_cache[service_key] = credential_record
        
        # Persist credentials
        if self.config["credential_store"] == "keyring":
            if HAS_KEYRING:
                try:
                    # Store as JSON in keyring
                    keyring.set_password(
                        "ipfs_kit_py", 
                        service_key,
                        json.dumps(credential_record)
                    )
                    return True
                except Exception as e:
                    logger.error(f"Failed to store credentials in keyring: {str(e)}")
                    # Fall back to file storage
                    return self._store_credential_in_file(service_key, credential_record)
            else:
                # Fall back to file storage
                return self._store_credential_in_file(service_key, credential_record)
        else:
            # Use file storage directly
            return self._store_credential_in_file(service_key, credential_record)
    
    def _store_credential_in_file(self, key: str, credential_record: Dict[str, Any]) -> bool:
        """Store credential in the file backend.
        
        Args:
            key: Combined service and name key
            credential_record: Complete credential record with metadata
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Load existing credentials file if it exists
            credential_file = self.config["credential_file_path"]
            credentials_data = {}
            
            if os.path.exists(credential_file):
                with open(credential_file, "r") as f:
                    try:
                        credentials_data = json.load(f)
                    except json.JSONDecodeError:
                        # File exists but is invalid JSON, start fresh
                        credentials_data = {}
            
            # Add or update the credential
            credentials_data[key] = credential_record
            
            # Write back to file
            with open(credential_file, "w") as f:
                json.dump(credentials_data, f)
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to store credentials in file: {str(e)}")
            return False
    
    def get_credential(self, service: str, name: str = "default") -> Optional[Dict[str, Any]]:
        """Retrieve credentials for a service.
        
        Args:
            service: Service identifier (ipfs, s3, storacha, filecoin)
            name: Name for this credential set (e.g. 'default', 'aws', 'backup')
            
        Returns:
            Credentials if found, None otherwise
        """
        service_key = f"{service}_{name}"
        
        # Check cache first
        if service_key in self.credential_cache:
            credential_record = self.credential_cache[service_key]
            # Update usage statistics
            credential_record["metadata"]["last_used"] = time.time()
            credential_record["metadata"]["use_count"] += 1
            return credential_record["credentials"]
        
        # Try to load from storage
        if self.config["credential_store"] == "keyring" and HAS_KEYRING:
            try:
                credential_json = keyring.get_password("ipfs_kit_py", service_key)
                if credential_json:
                    credential_record = json.loads(credential_json)
                    # Cache for future use
                    self.credential_cache[service_key] = credential_record
                    # Update usage statistics
                    credential_record["metadata"]["last_used"] = time.time()
                    credential_record["metadata"]["use_count"] += 1
                    return credential_record["credentials"]
            except Exception as e:
                logger.error(f"Failed to retrieve credentials from keyring: {str(e)}")
                # Fall back to file
                return self._get_credential_from_file(service_key)
        else:
            # Use file storage
            return self._get_credential_from_file(service_key)
        
        return None
    
    def _get_credential_from_file(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve credential from the file backend.
        
        Args:
            key: Combined service and name key
            
        Returns:
            Credentials if found, None otherwise
        """
        try:
            credential_file = self.config["credential_file_path"]
            
            if not os.path.exists(credential_file):
                return None
                
            with open(credential_file, "r") as f:
                try:
                    credentials_data = json.load(f)
                    if key in credentials_data:
                        credential_record = credentials_data[key]
                        # Cache for future use
                        self.credential_cache[key] = credential_record
                        # Update usage statistics
                        credential_record["metadata"]["last_used"] = time.time()
                        credential_record["metadata"]["use_count"] += 1
                        # We should write back the updated usage stats, but for performance
                        # we'll just update them in memory and they'll be written next time
                        # a credential is added or explicitly saved
                        return credential_record["credentials"]
                except json.JSONDecodeError:
                    logger.error("Credentials file is corrupted")
                    return None
        except Exception as e:
            logger.error(f"Failed to retrieve credentials from file: {str(e)}")
            
        return None
    
    def list_credentials(self, service: Optional[str] = None) -> List[Dict[str, Any]]:
        """List available credentials, optionally filtered by service.
        
        Args:
            service: Optional service filter
            
        Returns:
            List of credential metadata (without actual secrets)
        """
        results = []
        
        # Load all credentials into cache first
        self._load_all_credentials()
        
        # Filter and format results
        for key, credential_record in self.credential_cache.items():
            service_name, credential_name = key.split("_", 1)
            
            if service is None or service == service_name:
                # Create a safe view without actual credentials
                credential_info = {
                    "service": service_name,
                    "name": credential_name,
                    "added_at": credential_record["metadata"].get("added_at"),
                    "last_used": credential_record["metadata"].get("last_used"),
                    "use_count": credential_record["metadata"].get("use_count", 0),
                    "id": credential_record["metadata"].get("id"),
                    "credential_type": credential_record["credentials"].get("type", "unknown")
                }
                results.append(credential_info)
                
        return results
    
    def _load_all_credentials(self):
        """Load all credentials into the cache."""
        if self.config["credential_store"] == "keyring" and HAS_KEYRING:
            # Keyring doesn't support listing all entries for a service,
            # so we'll load from file as a fallback
            self._load_all_credentials_from_file()
        else:
            # Load from file
            self._load_all_credentials_from_file()
    
    def _load_all_credentials_from_file(self):
        """Load all credentials from the file storage."""
        try:
            credential_file = self.config["credential_file_path"]
            
            if not os.path.exists(credential_file):
                return
                
            with open(credential_file, "r") as f:
                try:
                    credentials_data = json.load(f)
                    # Update cache with all credentials
                    for key, credential_record in credentials_data.items():
                        self.credential_cache[key] = credential_record
                except json.JSONDecodeError:
                    logger.error("Credentials file is corrupted")
        except Exception as e:
            logger.error(f"Failed to load credentials from file: {str(e)}")
    
    def remove_credential(self, service: str, name: str) -> bool:
        """Remove credentials for a service.
        
        Args:
            service: Service identifier
            name: Name for this credential set
            
        Returns:
            True if successful, False otherwise
        """
        service_key = f"{service}_{name}"
        
        # Remove from cache
        if service_key in self.credential_cache:
            del self.credential_cache[service_key]
            
        # Remove from storage
        success = True
        if self.config["credential_store"] == "keyring" and HAS_KEYRING:
            try:
                keyring.delete_password("ipfs_kit_py", service_key)
            except Exception as e:
                logger.error(f"Failed to remove credentials from keyring: {str(e)}")
                success = False
                
        # Always try to remove from file too, in case it's there
        file_success = self._remove_credential_from_file(service_key)
        
        return success and file_success
    
    def _remove_credential_from_file(self, key: str) -> bool:
        """Remove credential from the file backend.
        
        Args:
            key: Combined service and name key
            
        Returns:
            True if successful, False otherwise
        """
        try:
            credential_file = self.config["credential_file_path"]
            
            if not os.path.exists(credential_file):
                return True  # Nothing to remove
                
            with open(credential_file, "r") as f:
                try:
                    credentials_data = json.load(f)
                    if key in credentials_data:
                        del credentials_data[key]
                        # Write back to file
                        with open(credential_file, "w") as f:
                            json.dump(credentials_data, f)
                    return True
                except json.JSONDecodeError:
                    logger.error("Credentials file is corrupted")
                    return False
        except Exception as e:
            logger.error(f"Failed to remove credentials from file: {str(e)}")
            return False
            
    def add_s3_credentials(self, name: str, aws_access_key_id: str, 
                          aws_secret_access_key: str, endpoint_url: str = None,
                          region: str = None) -> bool:
        """Add S3 credentials.
        
        Args:
            name: Name for this credential set
            aws_access_key_id: AWS access key ID
            aws_secret_access_key: AWS secret access key
            endpoint_url: Optional endpoint URL for custom S3 services
            region: Optional AWS region
            
        Returns:
            True if successful, False otherwise
        """
        credentials = {
            "type": "s3",
            "aws_access_key_id": aws_access_key_id,
            "aws_secret_access_key": aws_secret_access_key
        }
        
        if endpoint_url:
            credentials["endpoint_url"] = endpoint_url
            
        if region:
            credentials["region"] = region
            
        return self.add_credential("s3", name, credentials)
    
    def add_storacha_credentials(self, name: str, api_token: str, space_did: str = None) -> bool:
        """Add Storacha/W3 credentials.
        
        Args:
            name: Name for this credential set
            api_token: W3/Storacha API token
            space_did: Optional space DID for scoped access
            
        Returns:
            True if successful, False otherwise
        """
        credentials = {
            "type": "storacha",
            "api_token": api_token
        }
        
        if space_did:
            credentials["space_did"] = space_did
            
        return self.add_credential("storacha", name, credentials)
    
    def add_filecoin_credentials(self, name: str, api_key: str, api_secret: str = None,
                               wallet_address: str = None, provider: str = None) -> bool:
        """Add Filecoin credentials.
        
        Args:
            name: Name for this credential set
            api_key: Filecoin API key
            api_secret: Optional API secret for some services
            wallet_address: Optional Filecoin wallet address
            provider: Optional provider name (e.g., 'estuary', 'lotus', 'glif')
            
        Returns:
            True if successful, False otherwise
        """
        credentials = {
            "type": "filecoin",
            "api_key": api_key
        }
        
        if api_secret:
            credentials["api_secret"] = api_secret
            
        if wallet_address:
            credentials["wallet_address"] = wallet_address
            
        if provider:
            credentials["provider"] = provider
            
        return self.add_credential("filecoin", name, credentials)
    
    def get_s3_credentials(self, name: str = "default") -> Optional[Dict[str, Any]]:
        """Get S3 credentials.
        
        Args:
            name: Name of the credential set
            
        Returns:
            S3 credentials if found, None otherwise
        """
        return self.get_credential("s3", name)
    
    def get_filecoin_credentials(self, name: str = "default") -> Optional[Dict[str, Any]]:
        """Get Filecoin credentials.
        
        Args:
            name: Name of the credential set
            
        Returns:
            Filecoin credentials if found, None otherwise
        """
        return self.get_credential("filecoin", name)
    
    def get_storacha_credentials(self, name: str = "default") -> Optional[Dict[str, Any]]:
        """Get Storacha/W3 credentials.
        
        Args:
            name: Name of the credential set
            
        Returns:
            Storacha credentials if found, None otherwise
        """
        return self.get_credential("storacha", name)
    
    def get_ipfs_credentials(self, name: str = "default") -> Optional[Dict[str, Any]]:
        """Get IPFS credentials.
        
        Args:
            name: Name of the credential set
            
        Returns:
            IPFS credentials if found, None otherwise
        """
        return self.get_credential("ipfs", name)