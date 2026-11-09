"""
Enhanced IPNS Operations Module for IPFS Kit.

This module provides advanced InterPlanetary Name System (IPNS) functionality with
comprehensive key management capabilities. It enables sophisticated name publishing
and resolution with support for multiple keys, key rotation, and expiration controls.

Key features:
- Advanced key management (create, import, export, rotate)
- Enhanced IPNS publishing with custom TTL and priority
- Multi-key publishing strategies
- IPNS resolution with verification
- Key permissions and protection levels
- Performance metrics for IPNS operations
"""

import base64
import json
import logging
import os
import time
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from ipfs_connection_pool import get_connection_pool # type: ignore

# Set up logging
logger = logging.getLogger("ipfs_ipns_operations")

class KeyType(Enum):
    """Types of keys supported for IPNS operations."""
    RSA = "rsa"      # RSA keys (default in IPFS)
    ED25519 = "ed25519"  # ED25519 keys (faster)
    SECP256K1 = "secp256k1"  # SECP256K1 keys (compatible with Ethereum)

class KeyProtectionLevel(Enum):
    """Protection levels for IPNS keys."""
    STANDARD = "standard"  # Standard key storage
    PROTECTED = "protected"  # Enhanced protection (password required for use)
    HARDWARE = "hardware"  # Hardware-backed (if supported)

class IPNSRecord:
    """Represents an IPNS record with metadata."""

    def __init__(
        self,
        name: str,
        value: str,  # Usually a CID
        key_name: str = "self",
        sequence: int = 0,
        ttl: int = 24 * 60 * 60,  # 24 hours in seconds
        validity: int = 48 * 60 * 60,  # 48 hours in seconds
        signature: Optional[str] = None,
        expiration: Optional[float] = None,
    ):
        """
        Initialize an IPNS record.

        Args:
            name: The IPNS name (typically a peer ID hash)
            value: The value (typically a CID) this name points to
            key_name: Name of the key used to publish this record
            sequence: Sequence number for versioning
            ttl: Record time-to-live in seconds (for caching)
            validity: How long the record is valid in seconds
            signature: Optional signature validating the record
            expiration: Optional timestamp when record expires
        """
        self.name = name
        self.value = value
        self.key_name = key_name
        self.sequence = sequence
        self.ttl = ttl
        self.validity = validity
        self.signature = signature

        # Set expiration time if not provided
        if expiration is None and validity:
            self.expiration = time.time() + validity
        else:
            self.expiration = expiration

    def is_expired(self) -> bool:
        """Check if the record has expired."""
        if self.expiration is None:
            return False
        return time.time() > self.expiration

    def to_dict(self) -> Dict[str, Any]:
        """Convert record to a dictionary."""
        result = {
            "name": self.name,
            "value": self.value,
            "key_name": self.key_name,
            "sequence": self.sequence,
            "ttl": self.ttl,
            "validity": self.validity,
        }

        if self.signature:
            result["signature"] = self.signature

        if self.expiration:
            result["expiration"] = self.expiration
            result["expires_at"] = datetime.fromtimestamp(self.expiration).isoformat()

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IPNSRecord":
        """Create a record from a dictionary."""
        return cls(
            name=data["name"],
            value=data["value"],
            key_name=data.get("key_name", "self"),
            sequence=data.get("sequence", 0),
            ttl=data.get("ttl", 24 * 60 * 60),
            validity=data.get("validity", 48 * 60 * 60),
            signature=data.get("signature"),
            expiration=data.get("expiration"),
        )

class KeyManager:
    """
    Manages cryptographic keys used for IPNS record signing and verification.

    This class interacts with the IPFS daemon's key management API (`ipfs key`)
    to provide functionalities such as:
    - Listing available keys (`list_keys`).
    - Generating new cryptographic keys (`create_key`) of types RSA, Ed25519, Secp256k1.
    - Importing (`import_key`) and exporting (`export_key`) keys, typically in PEM format.
    - Renaming (`rename_key`) and removing (`remove_key`) keys.
    - Rotating keys (`rotate_key`), which involves generating a new key while optionally
      preserving the old one under a timestamped name.
    - Caching key information (`_key_cache`) to reduce API calls.
    - Tracking performance metrics (`performance_metrics`) for key operations.

    It requires an `ipfs_connection_pool` instance (or fetches the default one)
    to communicate with the IPFS daemon's HTTP API. Configuration options can
    be passed via the `config` dictionary.
    """

    def __init__(self, connection_pool=None, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the key manager.

        Args:
            connection_pool: Optional connection pool instance. If None, fetches
                             the default pool using `get_connection_pool`.
            config (Optional[Dict[str, Any]]): Configuration dictionary. Can include:
                - `key_cache_ttl` (int): Time-to-live for the key cache in seconds (default: 300).
                - `key_store_path` (str): Optional path to a custom keystore (not fully implemented).
        """
        self.config = config or {}
        self.connection_pool = connection_pool or get_connection_pool()

        # Key metadata cache
        self._key_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_timestamp = 0
        self._cache_ttl = self.config.get("key_cache_ttl", 300)  # 5 minutes default

        # Optional: Custom key store location
        self.key_store_path = self.config.get("key_store_path")

        # Track performance
        self.performance_metrics = {
            "create_key": {"count": 0, "total_time": 0, "avg_time": 0, "success_rate": 1.0},
            "import_key": {"count": 0, "total_time": 0, "avg_time": 0, "success_rate": 1.0},
            "export_key": {"count": 0, "total_time": 0, "avg_time": 0, "success_rate": 1.0},
            "rename_key": {"count": 0, "total_time": 0, "avg_time": 0, "success_rate": 1.0},
            "remove_key": {"count": 0, "total_time": 0, "avg_time": 0, "success_rate": 1.0},
            "rotate_key": {"count": 0, "total_time": 0, "avg_time": 0, "success_rate": 1.0},
        }

    def _update_metrics(self, operation: str, duration: float, success: bool) -> None:
        """
        Update performance metrics for a specific key management operation.

        Uses an exponential moving average for the success rate.

        Args:
            operation (str): The name of the operation (e.g., 'create_key').
            duration (float): The time taken for the operation in seconds.
            success (bool): Whether the operation completed successfully.
        """
        if operation in self.performance_metrics:
            metrics = self.performance_metrics[operation]
            metrics["count"] += 1
            metrics["total_time"] += duration
            metrics["avg_time"] = metrics["total_time"] / metrics["count"]

            # Update success rate using exponential moving average
            alpha = 0.1  # Weight for new observations
            metrics["success_rate"] = (
                (1 - alpha) * metrics["success_rate"] +
                alpha * (1.0 if success else 0.0)
            )

    def list_keys(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        List all available IPNS keys known to the IPFS daemon.

        Uses a cache to avoid frequent API calls unless `force_refresh` is True
        or the cache is expired.

        Args:
            force_refresh (bool): If True, bypass the cache and query the daemon directly.

        Returns:
            Dict[str, Any]: A dictionary containing:
                - 'success' (bool): True if the operation succeeded.
                - 'keys' (List[Dict]): A list of key information dictionaries
                  (each containing 'Name' and 'Id').
                - 'from_cache' (bool): True if the result was served from the cache.
                - 'error' (str, optional): Error message on failure.
                - 'details' (str, optional): Raw API response text on failure.
                - 'exception' (str, optional): String representation of exception on failure.
        """
        current_time = time.time()

        # Check if we can use cached data
        if (not force_refresh and
            self._key_cache and
            (current_time - self._cache_timestamp) < self._cache_ttl):
            logger.debug("Serving list_keys from cache.")
            return {
                "success": True,
                "keys": list(self._key_cache.values()),
                "from_cache": True,
            }

        logger.debug("Fetching key list from IPFS daemon.")
        try:
            # Call the IPFS API
            response = self.connection_pool.post("key/list")

            if response.status_code == 200:
                response_json = response.json()
                keys = response_json.get("Keys", [])

                # Update cache
                self._key_cache = {}
                for key in keys:
                    name = key.get("Name")
                    if name:
                        self._key_cache[name] = key

                self._cache_timestamp = current_time
                logger.info(f"Refreshed key cache with {len(keys)} keys.")

                return {
                    "success": True,
                    "keys": keys,
                    "from_cache": False,
                }
            else:
                logger.error(f"Failed to list keys from daemon: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"Failed to list keys: {response.status_code}",
                    "details": response.text,
                }

        except Exception as e:
            logger.error(f"Exception during list_keys: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Error listing keys: {str(e)}",
                "exception": str(e),
            }

    def get_key(self, name: str) -> Dict[str, Any]:
        """
        Get information about a specific key by its name.

        Checks the local cache first before potentially refreshing the list from the daemon.

        Args:
            name (str): The name of the key to retrieve information for.

        Returns:
            Dict[str, Any]: A dictionary containing:
                - 'success' (bool): True if the key was found.
                - 'key' (Dict): The key information dictionary if found.
                - 'from_cache' (bool): True if the result was served from the cache.
                - 'error' (str, optional): Error message if the key was not found.
        """
        # First check cache
        if name in self._key_cache:
            logger.debug(f"Serving get_key('{name}') from cache.")
            return {
                "success": True,
                "key": self._key_cache[name],
                "from_cache": True,
            }

        # If not in cache, refresh and try again
        logger.debug(f"Key '{name}' not in cache, refreshing list.")
        list_result = self.list_keys(force_refresh=True)

        if list_result["success"] and name in self._key_cache:
            logger.debug(f"Found key '{name}' after cache refresh.")
            return {
                "success": True,
                "key": self._key_cache[name],
                "from_cache": False,
            }

        logger.warning(f"Key '{name}' not found even after cache refresh.")
        return {
            "success": False,
            "error": f"Key not found: {name}",
        }

    def create_key(
        self,
        name: str,
        key_type: Union[KeyType, str] = KeyType.ED25519,
        size: int = 2048,
        protection: Union[KeyProtectionLevel, str] = KeyProtectionLevel.STANDARD,
        password: Optional[str] = None, # Currently unused, for future protection implementation
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new cryptographic key in the IPFS keystore.

        Args:
            name (str): A unique name for the new key.
            key_type (Union[KeyType, str]): The type of key to generate. Defaults to ED25519.
                                            See `KeyType` enum.
            size (int): The key size in bits, primarily relevant for RSA keys (default: 2048).
            protection (Union[KeyProtectionLevel, str]): The desired protection level.
                                                         Currently only STANDARD is fully supported here.
            password (Optional[str]): Password for PROTECTED level (feature not fully implemented here).
            options (Optional[Dict[str, Any]]): Additional options for the `key/gen` API call.

        Returns:
            Dict[str, Any]: A dictionary summarizing the outcome.
                            On success:
                                {'success': True, 'key': <key_info_dict>, 'duration': <float_seconds>}
                            On failure:
                                {'success': False, 'error': <error_message>, ...}
        """
        options = options or {}
        start_time = time.time()

        # Convert enum to string if needed
        if isinstance(key_type, KeyType):
            key_type = key_type.value

        if isinstance(protection, KeyProtectionLevel):
            protection = protection.value

        # Create the request parameters
        params = {
            "arg": name,
            "type": key_type,
        }

        # Add size only for RSA keys
        if key_type.lower() == "rsa":
            params["size"] = str(size)

        logger.info(f"Attempting to generate key '{name}' of type '{key_type}'...")
        try:
            # Call the IPFS API
            response = self.connection_pool.post("key/gen", params=params)

            success = response.status_code == 200

            # Update metrics
            duration = time.time() - start_time
            self._update_metrics("create_key", duration, success)

            if success:
                response_json = response.json()
                key_id = response_json.get("Id")
                logger.info(f"Successfully generated key '{name}' with ID: {key_id}")

                # Add to cache
                key_info = {
                    "Name": name,
                    "Id": key_id,
                    "Type": key_type,
                    "Size": size if key_type.lower() == "rsa" else None,
                    "Created": datetime.now().isoformat(),
                    "Protection": protection, # Store intended protection level
                }

                self._key_cache[name] = key_info

                # Handle protected keys if needed (Placeholder for future implementation)
                if protection != "standard" and password:
                    logger.warning(f"Password provided for key '{name}', but password protection logic is not fully implemented in this client.")
                    # Future: Implement encryption/decryption logic here or rely on daemon features if available.
                    pass

                return {
                    "success": True,
                    "key": key_info,
                    "duration": duration,
                }
            else:
                logger.error(f"Failed to create key '{name}': {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"Failed to create key: {response.status_code}",
                    "details": response.text,
                    "duration": duration,
                }

        except Exception as e:
            duration = time.time() - start_time
            self._update_metrics("create_key", duration, False)
            logger.error(f"Exception during create_key('{name}'): {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Error creating key: {str(e)}",
                "exception": str(e),
                "duration": duration,
            }

    def import_key(
        self,
        name: str,
        private_key: Union[str, bytes],
        format_type: str = "pem", # 'pem' is expected by the API via file upload
        protection: Union[KeyProtectionLevel, str] = KeyProtectionLevel.STANDARD,
        password: Optional[str] = None, # Currently unused
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Import an existing private key into the IPFS keystore.

        The key data is written to a temporary file and uploaded via multipart/form-data
        as expected by the `key/import` API endpoint.

        Args:
            name (str): The name to assign to the imported key.
            private_key (Union[str, bytes]): The private key data, typically a PEM-encoded string or bytes.
            format_type (str): The format of the key. Currently, only 'pem' is effectively
                               supported via the file upload method used here.
            protection (Union[KeyProtectionLevel, str]): Desired protection level (currently informational).
            password (Optional[str]): Password if the key is encrypted (feature not fully implemented here).
            options (Optional[Dict[str, Any]]): Additional options, e.g., `{'ipns_base': 'base32'}`.

        Returns:
            Dict[str, Any]: A dictionary summarizing the outcome.
        """
        options = options or {}
        start_time = time.time()

        # Convert enum to string if needed
        if isinstance(protection, KeyProtectionLevel):
            protection = protection.value

        # Ensure the private key is bytes
        if isinstance(private_key, str):
            private_key = private_key.encode('utf-8')

        key_path = None # Initialize key_path
        logger.info(f"Attempting to import key '{name}'...")
        try:
            # Create a temporary file for the key
            import tempfile
            # Use delete=False to manage deletion manually in finally block
            with tempfile.NamedTemporaryFile(mode='wb', delete=False) as key_file:
                key_path = key_file.name
                key_file.write(private_key)
                logger.debug(f"Wrote private key to temporary file: {key_path}")

            # Create the request parameters
            params = {
                "arg": name,
                "ipns-base": options.get("ipns_base", "base36"), # Default base36
                # Note: 'format' param might be needed depending on daemon version, but often inferred
            }

            # Use multipart/form-data to upload the key file
            with open(key_path, 'rb') as f:
                files = {'key': (os.path.basename(key_path), f)} # Provide filename
                logger.debug(f"Calling key/import API for key '{name}' with file {key_path}")
                response = self.connection_pool.post("key/import", params=params, files=files)

            success = response.status_code == 200

            # Update metrics
            duration = time.time() - start_time
            self._update_metrics("import_key", duration, success)

            if success:
                response_json = response.json()
                key_id = response_json.get("Id")
                logger.info(f"Successfully imported key '{name}' with ID: {key_id}")

                # Add to cache
                key_info = {
                    "Name": name,
                    "Id": key_id,
                    "Type": "imported", # Type might not be easily determinable post-import
                    "Created": datetime.now().isoformat(),
                    "Protection": protection,
                }
                self._key_cache[name] = key_info

                # Handle protected keys if needed (Placeholder)
                if protection != "standard" and password:
                    logger.warning(f"Password provided for imported key '{name}', but protection logic is not fully implemented.")
                    pass

                return {
                    "success": True,
                    "key": key_info,
                    "duration": duration,
                }
            else:
                logger.error(f"Failed to import key '{name}': {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"Failed to import key: {response.status_code}",
                    "details": response.text,
                    "duration": duration,
                }
        except Exception as e:
            duration = time.time() - start_time
            self._update_metrics("import_key", duration, False)
            logger.error(f"Exception during import_key('{name}'): {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Error importing key: {str(e)}",
                "exception": str(e),
                "duration": duration,
            }
        finally:
            # Clean up the temporary file if it was created
            if key_path and os.path.exists(key_path):
                try:
                    os.unlink(key_path)
                    logger.debug(f"Cleaned up temporary key file: {key_path}")
                except Exception as unlink_e:
                    logger.error(f"Failed to clean up temporary key file {key_path}: {unlink_e}")


    def export_key(
        self,
        name: str,
        output_format: str = "pem", # API usually exports PEM by default
        password: Optional[str] = None, # For potential future decryption
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Export a private key from the IPFS keystore.

        Warning: Exporting private keys should be done with extreme caution.

        Args:
            name (str): The name of the key to export.
            output_format (str): The desired format (currently informational, API typically returns PEM).
            password (Optional[str]): Password if the key is protected (feature not fully implemented here).
            options (Optional[Dict[str, Any]]): Additional options, e.g., `{'output_file': '/path/to/save'}`.

        Returns:
            Dict[str, Any]: A dictionary containing the outcome and exported key data.
        """
        options = options or {}
        start_time = time.time()

        # Check if key exists (optional, API call will fail anyway)
        # key_result = self.get_key(name)
        # if not key_result["success"]:
        #     duration = time.time() - start_time
        #     self._update_metrics("export_key", duration, False)
        #     return key_result

        # Check protection if password is required (Placeholder)
        # key_info = key_result["key"]
        # protection = key_info.get("Protection", "standard")
        # if protection != "standard" and not password:
        #     # ... (error handling as before) ...

        logger.warning(f"Attempting to export private key '{name}'. Ensure this is intended.")
        try:
            # Create the request parameters
            params = {
                "arg": name,
                # 'output' param tells daemon to write to file instead of returning data
                "output": options.get("output_file"),
            }

            # Call the IPFS API
            response = self.connection_pool.post("key/export", params=params)

            success = response.status_code == 200

            # Update metrics
            duration = time.time() - start_time
            self._update_metrics("export_key", duration, success)

            if success:
                if options.get("output_file"):
                    logger.info(f"Successfully exported key '{name}' to file: {options['output_file']}")
                    return {
                        "success": True,
                        "key_name": name,
                        "output_file": options['output_file'],
                        "duration": duration,
                    }
                else:
                    # The response body contains the exported key data (usually PEM)
                    key_data = response.text
                    logger.info(f"Successfully exported key '{name}'.")
                    return {
                        "success": True,
                        "key_name": name,
                        "key_data": key_data, # Contains the private key! Handle with care.
                        "format": output_format, # Informational
                        "duration": duration,
                    }
            else:
                logger.error(f"Failed to export key '{name}': {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"Failed to export key: {response.status_code}",
                    "details": response.text,
                    "duration": duration,
                }

        except Exception as e:
            duration = time.time() - start_time
            self._update_metrics("export_key", duration, False)
            logger.error(f"Exception during export_key('{name}'): {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Error exporting key: {str(e)}",
                "exception": str(e),
                "duration": duration,
            }

    def rename_key(
        self,
        old_name: str,
        new_name: str,
        force: bool = False,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Rename a key in the IPFS keystore.

        Args:
            old_name (str): The current name of the key.
            new_name (str): The desired new name for the key.
            force (bool): If True, allows overwriting an existing key with `new_name`. Defaults to False.
            options (Optional[Dict[str, Any]]): Additional options for the `key/rename` API call.

        Returns:
            Dict[str, Any]: A dictionary summarizing the outcome.
        """
        options = options or {}
        start_time = time.time()

        # Check if old key exists (optional, API handles this)
        # old_key_result = self.get_key(old_name)
        # if not old_key_result["success"]:
        #     # ... (error handling) ...

        # Check if new name already exists if force is False (optional, API handles this)
        # if not force:
        #     new_key_result = self.get_key(new_name)
        #     if new_key_result["success"]:
        #         # ... (error handling) ...

        logger.info(f"Attempting to rename key '{old_name}' to '{new_name}' (force={force})...")
        try:
            # Create the request parameters - NOTE: API expects two 'arg' parameters
            params = [
                ("arg", old_name),
                ("arg", new_name),
                ("force", "true" if force else "false"),
            ]

            # Call the IPFS API
            response = self.connection_pool.post("key/rename", params=params)

            success = response.status_code == 200

            # Update metrics
            duration = time.time() - start_time
            self._update_metrics("rename_key", duration, success)

            if success:
                response_json = response.json()
                new_id = response_json.get("Id")
                logger.info(f"Successfully renamed key '{old_name}' to '{new_name}' (ID: {new_id}).")

                # Update cache
                key_info = None
                if old_name in self._key_cache:
                    key_info = self._key_cache.pop(old_name)
                elif force and new_name in self._key_cache: # If overwriting, old info might not be cached
                     key_info = self._key_cache.get(new_name) # Get existing info to update ID

                if key_info:
                    key_info["Name"] = new_name
                    key_info["Id"] = new_id # Update ID based on response
                    self._key_cache[new_name] = key_info
                else: # If neither old nor new was cached, refresh might be needed later
                    self.list_keys(force_refresh=True) # Refresh cache proactively


                return {
                    "success": True,
                    "old_name": old_name,
                    "new_name": new_name,
                    "id": new_id,
                    "was_renamed": response_json.get("Was", old_name),
                    "now_renamed": response_json.get("Now", new_name),
                    "overwritten": response_json.get("Overwritten", False),
                    "duration": duration,
                }
            else:
                logger.error(f"Failed to rename key '{old_name}': {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"Failed to rename key: {response.status_code}",
                    "details": response.text,
                    "duration": duration,
                }

        except Exception as e:
            duration = time.time() - start_time
            self._update_metrics("rename_key", duration, False)
            logger.error(f"Exception during rename_key('{old_name}', '{new_name}'): {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Error renaming key: {str(e)}",
                "exception": str(e),
                "duration": duration,
            }

    def remove_key(
        self,
        name: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Remove a key from the IPFS keystore.

        Args:
            name (str): The name of the key to remove.
            options (Optional[Dict[str, Any]]): Additional options for the `key/rm` API call.

        Returns:
            Dict[str, Any]: A dictionary summarizing the outcome.
        """
        options = options or {}
        start_time = time.time()

        # Check if key exists (optional, API handles this)
        # key_result = self.get_key(name)
        # if not key_result["success"]:
        #     # ... (error handling) ...

        logger.info(f"Attempting to remove key '{name}'...")
        try:
            # Create the request parameters
            params = {
                "arg": name,
            }

            # Call the IPFS API
            response = self.connection_pool.post("key/rm", params=params)

            success = response.status_code == 200

            # Update metrics
            duration = time.time() - start_time
            self._update_metrics("remove_key", duration, success)

            if success:
                response_json = response.json()
                removed_keys = response_json.get("Keys", [])
                logger.info(f"Successfully removed key '{name}'. Response: {removed_keys}")

                # Update cache
                if name in self._key_cache:
                    del self._key_cache[name]

                return {
                    "success": True,
                    "keys_removed": removed_keys, # API returns list of removed keys
                    "duration": duration,
                }
            else:
                logger.error(f"Failed to remove key '{name}': {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"Failed to remove key: {response.status_code}",
                    "details": response.text,
                    "duration": duration,
                }

        except Exception as e:
            duration = time.time() - start_time
            self._update_metrics("remove_key", duration, False)
            logger.error(f"Exception during remove_key('{name}'): {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Error removing key: {str(e)}",
                "exception": str(e),
                "duration": duration,
            }

    def rotate_key(
        self,
        name: str,
        new_key_type: Optional[Union[KeyType, str]] = None,
        size: Optional[int] = None,
        preserve_old: bool = True,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Rotate an IPNS key by creating a new one under the same name.

        This involves:
        1. Optionally renaming the existing key to `name-<timestamp>` if `preserve_old` is True.
        2. If not preserving, removing the existing key.
        3. Generating a new key with the original `name`.

        Note: This client-side rotation doesn't automatically update IPNS records
              pointing to the old key's ID. Records must be republished using the new key.

        Args:
            name (str): The name of the key to rotate.
            new_key_type (Optional[Union[KeyType, str]]): Type for the new key. If None,
                                                          uses the type of the old key.
            size (Optional[int]): Size for the new key. If None, uses the size of the old key.
            preserve_old (bool): If True (default), rename the old key to `name-<timestamp>`.
                                 If False, remove the old key permanently.
            options (Optional[Dict[str, Any]]): Additional options passed to underlying methods.

        Returns:
            Dict[str, Any]: A dictionary summarizing the outcome.
        """
        options = options or {}
        start_time = time.time()
        old_name_preserved: Optional[str] = None # Explicitly initialize and type hint
        old_id: Optional[str] = None # Initialize old_id

        logger.info(f"Attempting to rotate key '{name}' (preserve_old={preserve_old})...")

        # Check if key exists
        key_result = self.get_key(name)
        if not key_result["success"]:
            # If key doesn't exist, we might just want to create it
            logger.warning(f"Key '{name}' not found for rotation. Attempting to create it.")
            # Proceed to create key directly
            old_id = None
            # Ensure defaults are assigned if new_key_type/size are None initially
            old_type: Union[KeyType, str] = new_key_type if new_key_type is not None else KeyType.ED25519
            old_size: int = size if size is not None else 2048
            preserve_old = False # Cannot preserve if it doesn't exist
        else:
            old_key = key_result["key"]
            old_id = old_key.get("Id")
            old_type = old_key.get("Type", "ed25519") # Default if type unknown
            old_size = old_key.get("Size", 2048) # Default if size unknown

        # Determine new key parameters
        # Determine final new key parameters, ensuring they are not None
        final_new_key_type: str
        if new_key_type:
             final_new_key_type = new_key_type.value if isinstance(new_key_type, KeyType) else new_key_type
        else:
             final_new_key_type = old_type.value if isinstance(old_type, KeyType) else old_type

        final_size: int = size if size is not None else old_size

        try:
            # Step 1: Handle the old key (rename or remove) if it existed
            if old_id: # Only if the key actually existed
                if preserve_old:
                    timestamp = int(time.time())
                    old_name_preserved = f"{name}-{timestamp}"
                    logger.debug(f"Renaming old key '{name}' to '{old_name_preserved}'")
                    rename_result = self.rename_key(name, old_name_preserved, force=True) # Force overwrite if somehow exists
                    if not rename_result["success"]:
                        duration = time.time() - start_time
                        self._update_metrics("rotate_key", duration, False)
                        return {
                            "success": False,
                            "error": f"Failed to rename old key during rotation: {rename_result['error']}",
                            "details": rename_result,
                            "duration": duration,
                        }
                else:
                    logger.debug(f"Removing old key '{name}' before creating new one.")
                    remove_result = self.remove_key(name)
                    if not remove_result["success"]:
                        # Log warning but proceed, maybe key was already gone
                        logger.warning(f"Failed to remove old key '{name}' during rotation (maybe already gone?): {remove_result.get('error')}")
                        # Allow proceeding to create the new key anyway

            # Step 2: Create the new key with the original name
            logger.debug(f"Creating new key '{name}' of type {final_new_key_type}...")
            create_result = self.create_key(
                name=name,
                key_type=final_new_key_type, # Use guaranteed string
                size=final_size,             # Use guaranteed int
                # Inherit protection level? For now, default to standard.
                protection=KeyProtectionLevel.STANDARD, # Assuming standard for rotation simplicity
            )

            if not create_result["success"]:
                duration = time.time() - start_time
                self._update_metrics("rotate_key", duration, False)
                # Attempt to restore old key if renamed? Complex recovery logic needed.
                logger.error(f"Failed to create new key '{name}' during rotation.")
                return {
                    "success": False,
                    "error": f"Failed to create new key during rotation: {create_result['error']}",
                    "details": create_result,
                    "duration": duration,
                }

            new_key = create_result["key"]
            new_id = new_key.get("Id")

            # Update metrics
            duration = time.time() - start_time
            self._update_metrics("rotate_key", duration, True)
            logger.info(f"Successfully rotated key '{name}'. New ID: {new_id}. Old key preserved as: {old_name_preserved if preserve_old else 'Removed'}")

            return {
                "success": True,
                "key_name": name,
                "old_key_id": old_id,
                "new_key_id": new_id,
                "old_key_preserved": preserve_old,
                "old_key_name": old_name_preserved,
                "key_type": final_new_key_type,
                "size": final_size,
                "duration": duration,
            }

        except Exception as e:
            duration = time.time() - start_time
            self._update_metrics("rotate_key", duration, False)
            logger.error(f"Exception during rotate_key('{name}'): {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Error rotating key: {str(e)}",
                "exception": str(e),
                "duration": duration,
            }

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics for key operations.

        Returns:
            Dict[str, Any]: Dictionary containing performance metrics.
        """
        return {
            "success": True,
            "metrics": self.performance_metrics,
        }

class IPNSOperations:
    """
    Provides methods for interacting with the InterPlanetary Name System (IPNS).

    IPNS enables creating mutable pointers (names) in the IPFS network that can be
    updated to point to different immutable IPFS content CIDs over time. This is
    achieved by publishing signed records to the Distributed Hash Table (DHT).
    The name itself is typically the hash of the public key used for signing.

    This class interacts with the IPFS daemon's `/api/v0/name` endpoint and uses
    an instance of `KeyManager` to handle the necessary cryptographic keys.

    Core functionalities:
    - `publish`: Creates or updates an IPNS record, linking an IPNS name (key) to
                 an IPFS path (CID). Allows setting record lifetime and TTL.
    - `resolve`: Looks up the current value (IPFS path) associated with an IPNS name
                 by querying the DHT.
    - `republish`: Extends the lifetime of existing IPNS records by republishing them.
    - `get_records`: Attempts to list all IPNS records currently published by the node's keys.

    Includes performance tracking and caching mechanisms.
    """

    def __init__(self, connection_pool=None, key_manager=None, config: Optional[Dict[str, Any]] = None):
        """
        Initialize IPNS operations.

        Args:
            connection_pool: Optional connection pool instance. If None, fetches
                             the default pool using `get_connection_pool`.
            key_manager: Optional `KeyManager` instance. If None, a new one is created.
            config (Optional[Dict[str, Any]]): Configuration dictionary. Can include:
                - `default_ttl` (int): Default TTL for published records in seconds (default: 24h).
                - `default_lifetime` (int): Default validity for published records in seconds (default: 48h).
                - Inherited configs for `KeyManager` if `key_manager` is None.
        """
        self.config = config or {}
        self.connection_pool = connection_pool or get_connection_pool()
        self.key_manager = key_manager or KeyManager(self.connection_pool, self.config)

        # Default values
        self.default_ttl = self.config.get("default_ttl", 24 * 60 * 60)  # 24 hours
        self.default_lifetime = self.config.get("default_lifetime", 48 * 60 * 60)  # 48 hours

        # Record cache (simple in-memory cache)
        self._record_cache: Dict[str, IPNSRecord] = {}

        # Performance metrics
        self.performance_metrics = {
            "publish": {"count": 0, "total_time": 0, "avg_time": 0, "success_rate": 1.0},
            "resolve": {"count": 0, "total_time": 0, "avg_time": 0, "success_rate": 1.0},
            "republish": {"count": 0, "total_time": 0, "avg_time": 0, "success_rate": 1.0},
            "records": {"count": 0, "total_time": 0, "avg_time": 0, "success_rate": 1.0},
        }

    def _update_metrics(self, operation: str, duration: float, success: bool) -> None:
        """
        Update performance metrics for a specific IPNS operation.

        Uses an exponential moving average for the success rate.

        Args:
            operation (str): The name of the operation (e.g., 'publish').
            duration (float): The time taken for the operation in seconds.
            success (bool): Whether the operation completed successfully.
        """
        if operation in self.performance_metrics:
            metrics = self.performance_metrics[operation]
            metrics["count"] += 1
            metrics["total_time"] += duration
            metrics["avg_time"] = metrics["total_time"] / metrics["count"]

            # Update success rate using exponential moving average
            alpha = 0.1  # Weight for new observations
            metrics["success_rate"] = (
                (1 - alpha) * metrics["success_rate"] +
                alpha * (1.0 if success else 0.0)
            )

    def publish(
        self,
        cid: str,
        key_name: str = "self",
        lifetime: Optional[str] = None,
        ttl: Optional[str] = None,
        resolve: bool = True,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Publish an IPNS name record, associating a name with an IPFS path (CID).

        This method updates the IPNS record linked to the specified `key_name`.
        The record points the IPNS name (derived from the key) to the provided
        IPFS path (`cid`). The operation involves signing the record with the
        private key corresponding to `key_name` and publishing it to the IPFS
        Distributed Hash Table (DHT).

        Args:
            cid (str): The IPFS path (typically a Content Identifier, CID) that the
                       IPNS name should point to. Can be prefixed with `/ipfs/` or not.
                       Example: "QmR7GSQM93Cx5eAg6a6yRzNde1FQv7uL6X1o4k7zrJa3LX"
                                or "/ipfs/QmR7GSQM93Cx5eAg6a6yRzNde1FQv7uL6X1o4k7zrJa3LX".
            key_name (str): The name of the cryptographic key within the IPFS keystore
                            to use for signing the record. The IPNS name resolved by
                            others will be the hash of this key's public component.
                            Defaults to "self", which uses the node's primary identity key.
            lifetime (Optional[str]): Specifies the duration for which the published
                                      record should be considered valid by the network.
                                      Uses time duration format (e.g., "300s", "1.5h",
                                      "2h45m", "7d"). If None, uses the node's default
                                      (typically 24 hours).
            ttl (Optional[str]): Specifies the suggested Time-To-Live (TTL) for the
                                 record when cached by other nodes in the DHT.
                                 Uses time duration format (e.g., "30s", "5m").
                                 If None, uses the node's default. Shorter TTLs lead
                                 to faster propagation of updates but increase network load.
            resolve (bool): If True (default), the IPFS daemon will first attempt to
                            resolve the provided `cid` to ensure it's a valid and
                            available IPFS path before publishing. Setting to False
                            allows publishing records pointing to potentially invalid
                            or non-IPFS paths, which is generally not recommended.
            options (Optional[Dict[str, Any]]): A dictionary for any additional,
                                                less common parameters accepted by the
                                                `ipfs name publish` API endpoint.

        Returns:
            Dict[str, Any]: A dictionary summarizing the outcome.
                            On success:
                                {'success': True, 'name': <PeerID>, 'value': <IPFS_Path>,
                                 'key_name': <key_name_used>, 'record': <IPNSRecord_dict>,
                                 'duration': <float_seconds>}
                            On failure:
                                {'success': False, 'error': <error_message>,
                                 'details': <API_response_text>, 'duration': <float_seconds>}
                                or
                                {'success': False, 'error': <exception_message>,
                                 'exception': <str(exception)>, 'duration': <float_seconds>}

        Raises:
            Exception: Can raise exceptions from the underlying HTTP request library
                       (e.g., `requests.exceptions.RequestException`) if connection fails.

        Example Usage:
            ```python
            # Assuming 'ipns_ops' is an initialized IPNSOperations instance
            # and 'my_website_cid' holds the CID of the website content

            # Publish using the default 'self' key with a 48-hour lifetime
            result = ipns_ops.publish(cid=my_website_cid, lifetime="48h")
            if result['success']:
                print(f"Published successfully! Name: {result['name']}")
            else:
                print(f"Publish failed: {result['error']}")

            # Publish using a specific key named 'blog-key' with a short TTL
            result_blog = ipns_ops.publish(cid=blog_cid, key_name="blog-key", ttl="10m")
            ```
        """
        options = options or {}
        start_time = time.time()

        # Validate key exists
        logger.debug(f"Validating key '{key_name}' before publishing.")
        key_result = self.key_manager.get_key(key_name)
        if not key_result["success"]:
            duration = time.time() - start_time
            self._update_metrics("publish", duration, False)
            logger.error(f"Publish failed: Key '{key_name}' not found.")
            return key_result # Return the error from get_key

        # Create the request parameters
        params = {
            "arg": cid,
            "key": key_name,
            "resolve": "true" if resolve else "false",
        }

        # Add optional parameters
        effective_lifetime_str = lifetime
        if lifetime:
            params["lifetime"] = lifetime
        else:
            # Use default if not provided, format it for logging/record
            effective_lifetime_str = f"{self.default_lifetime}s"

        effective_ttl_str = ttl
        if ttl:
            params["ttl"] = ttl
        else:
            # Use default if not provided, format it for logging/record
            effective_ttl_str = f"{self.default_ttl}s"

        logger.info(f"Publishing IPNS name for key '{key_name}' -> '{cid}' (lifetime: {effective_lifetime_str}, ttl: {effective_ttl_str})")
        try:
            # Call the IPFS API
            response = self.connection_pool.post("name/publish", params=params)

            success = response.status_code == 200

            # Update metrics
            duration = time.time() - start_time
            self._update_metrics("publish", duration, success)

            if success:
                response_json = response.json()
                name = response_json.get("Name") # This is the PeerID (hash of public key)
                value = response_json.get("Value") # This is the /ipfs/CID path

                logger.info(f"Successfully published IPNS record: {name} -> {value}")

                # Create and cache the record
                # Use parsed durations for the record object
                record = IPNSRecord(
                    name=name,
                    value=value,
                    key_name=key_name,
                    ttl=self._parse_duration(ttl) if ttl else self.default_ttl,
                    validity=self._parse_duration(lifetime) if lifetime else self.default_lifetime,
                    # Sequence number is managed by the daemon, not easily available here
                )

                self._record_cache[name] = record
                logger.debug(f"Cached IPNS record for {name}")

                return {
                    "success": True,
                    "name": name,
                    "value": value,
                    "key_name": key_name,
                    "record": record.to_dict(),
                    "duration": duration,
                }
            else:
                logger.error(f"Failed to publish IPNS name for key '{key_name}': {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"Failed to publish name: {response.status_code}",
                    "details": response.text,
                    "duration": duration,
                }

        except Exception as e:
            duration = time.time() - start_time
            self._update_metrics("publish", duration, False)
            logger.error(f"Exception during publish for key '{key_name}': {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Error publishing name: {str(e)}",
                "exception": str(e),
                "duration": duration,
            }

    def resolve(
        self,
        name: str,
        recursive: bool = True,
        dht_record: bool = False,
        nocache: bool = False,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Resolve an IPNS name to its value.

        Args:
            name: The IPNS name to resolve (can be a peer ID or domain with dnslink)
            recursive: Whether to recursively resolve until reaching a non-IPNS result
            dht_record: Whether to fetch the complete DHT record
            nocache: Whether to bypass cache for resolution
            options: Additional options for resolution

        Returns:
            Dictionary with operation results
        """
        options = options or {}
        start_time = time.time()

        # Create the request parameters
        params = {
            "arg": name,
            "recursive": "true" if recursive else "false",
            "dht-record": "true" if dht_record else "false",
            "nocache": "true" if nocache else "false",
        }

        logger.info(f"Resolving IPNS name '{name}' (recursive={recursive}, nocache={nocache})...")
        try:
            # Call the IPFS API
            response = self.connection_pool.post("name/resolve", params=params)

            success = response.status_code == 200

            # Update metrics
            duration = time.time() - start_time
            self._update_metrics("resolve", duration, success)

            if success:
                response_json = response.json()
                path = response_json.get("Path")
                logger.info(f"Successfully resolved IPNS name '{name}' to: {path}")

                result = {
                    "success": True,
                    "name": name,
                    "value": path, # The resolved IPFS path (e.g., /ipfs/CID)
                    "duration": duration,
                }

                # If DHT record was requested, parse it
                if dht_record and "DhtRecord" in response_json:
                    # The DhtRecord field is typically base64 encoded protobuf data
                    # Decoding it fully requires protobuf definitions, which might be complex.
                    # For now, just return the base64 string.
                    dht_record_data = response_json["DhtRecord"]
                    result["dht_record_base64"] = dht_record_data
                    logger.debug(f"Included base64 DHT record for '{name}'.")

                return result
            else:
                logger.error(f"Failed to resolve IPNS name '{name}': {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"Failed to resolve name: {response.status_code}",
                    "details": response.text,
                    "duration": duration,
                }

        except Exception as e:
            duration = time.time() - start_time
            self._update_metrics("resolve", duration, False)
            logger.error(f"Exception during resolve for name '{name}': {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Error resolving name: {str(e)}",
                "exception": str(e),
                "duration": duration,
            }

    def republish(
        self,
        name: str = None,
        key_name: str = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Republish an IPNS record to extend its lifetime.

        This resolves the current value associated with the name/key and then
        re-publishes it, effectively resetting its validity period on the DHT.

        Args:
            name (Optional[str]): The IPNS name (PeerID) to republish. If None,
                                  `key_name` must be provided to derive the name.
            key_name (Optional[str]): The key name associated with the IPNS record.
                                      If None, defaults to "self". Used to derive
                                      `name` if `name` is not provided, and used
                                      for signing the republished record.
            options (Optional[Dict[str, Any]]): Additional options passed to the
                                                underlying `publish` call (e.g.,
                                                'lifetime', 'ttl').

        Returns:
            Dict[str, Any]: A dictionary summarizing the outcome.
        """
        options = options or {}
        start_time = time.time()

        # Determine key and name to use
        effective_key_name = key_name or "self"
        effective_name = name

        logger.info(f"Attempting to republish IPNS record (key: '{effective_key_name}', name: {name or 'derived'})")

        # If name is not provided, derive it from the key
        if effective_name is None:
            logger.debug(f"Deriving IPNS name from key '{effective_key_name}'.")
            key_result = self.key_manager.get_key(effective_key_name)
            if not key_result["success"]:
                duration = time.time() - start_time
                self._update_metrics("republish", duration, False)
                logger.error(f"Republish failed: Cannot find key '{effective_key_name}' to derive name.")
                return key_result # Return error from get_key
            effective_name = key_result["key"].get("Id")
            if not effective_name:
                duration = time.time() - start_time
                self._update_metrics("republish", duration, False)
                logger.error(f"Republish failed: Could not get PeerID (name) from key '{effective_key_name}'.")
                return {
                    "success": False,
                    "error": f"Could not determine IPNS name (PeerID) for key: {effective_key_name}",
                    "duration": duration,
                }
            logger.debug(f"Derived IPNS name: {effective_name}")

        # Resolve the current value - use nocache to ensure we get the latest for republishing
        logger.debug(f"Resolving current value for name '{effective_name}' before republishing.")
        resolve_result = self.resolve(effective_name, nocache=True)
        if not resolve_result["success"]:
            duration = time.time() - start_time
            self._update_metrics("republish", duration, False)
            logger.error(f"Republish failed: Cannot resolve current value for name '{effective_name}'.")
            return {
                "success": False,
                "error": f"Failed to resolve name '{effective_name}' for republishing: {resolve_result.get('error', 'Unknown resolve error')}",
                "details": resolve_result,
                "duration": duration,
            }

        # Get the current value (CID path)
        current_value_path = resolve_result["value"]
        if not current_value_path or not current_value_path.startswith("/ipfs/"):
             duration = time.time() - start_time
             self._update_metrics("republish", duration, False)
             logger.error(f"Republish failed: Resolved value for '{effective_name}' is not a valid IPFS path ('{current_value_path}').")
             return {
                 "success": False,
                 "error": f"Resolved value for name '{effective_name}' is not a valid IPFS path: {current_value_path}",
                 "duration": duration,
             }
        current_cid = current_value_path[6:]  # Extract CID part

        # Republish with the resolved CID
        logger.debug(f"Republishing name '{effective_name}' with CID '{current_cid}' using key '{effective_key_name}'.")
        # Ensure lifetime and ttl passed to publish are strings or None, not potentially other types from options
        publish_lifetime = options.get("lifetime") if isinstance(options.get("lifetime"), str) else None
        publish_ttl = options.get("ttl") if isinstance(options.get("ttl"), str) else None

        publish_result = self.publish(
            cid=current_cid,
            key_name=effective_key_name,
            lifetime=publish_lifetime,
            ttl=publish_ttl,
            resolve=options.get("resolve", True), # Pass through options
        )

        # Update metrics based on the final publish result
        duration = time.time() - start_time
        self._update_metrics("republish", duration, publish_result["success"])

        if publish_result["success"]:
            logger.info(f"Successfully republished IPNS record for name '{effective_name}'.")
            return {
                "success": True,
                "name": effective_name,
                "value": current_value_path, # Return the full path
                "key_name": effective_key_name,
                "republished": True,
                "publish_details": publish_result, # Include details from the publish call
                "duration": duration,
            }
        else:
            logger.error(f"Republish failed during the final publish step for name '{effective_name}'.")
            return {
                "success": False,
                "error": f"Failed to republish name '{effective_name}': {publish_result.get('error', 'Unknown publish error')}",
                "details": publish_result,
                "duration": duration,
            }

    def get_records(
        self,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Get all IPNS records currently published by the keys managed by this node.

        This iterates through all keys known to the KeyManager, resolves the
        corresponding IPNS name for each key's ID, and collects the results
        for successfully resolved names.

        Args:
            options (Optional[Dict[str, Any]]): Additional options (currently unused).

        Returns:
            Dict[str, Any]: A dictionary containing:
                - 'success' (bool): True if the operation completed (even if some resolves failed).
                - 'records' (List[Dict]): A list of dictionaries, each representing a
                  successfully resolved IPNS record associated with a local key.
                  Each record includes 'name' (PeerID), 'value' (/ipfs/CID), 'key_name',
                  'last_resolved' (timestamp), and potentially 'details' from cache.
                - 'count' (int): The number of successfully resolved records found.
                - 'duration' (float): Operation time in seconds.
                - 'error' (str, optional): Error message if listing keys failed initially.
        """
        options = options or {}
        start_time = time.time()
        records = []
        logger.info("Getting locally published IPNS records by resolving keys...")

        try:
            # First get all our keys
            keys_result = self.key_manager.list_keys(force_refresh=True) # Refresh to be sure
            if not keys_result["success"]:
                duration = time.time() - start_time
                self._update_metrics("records", duration, False)
                logger.error(f"Failed to list keys while getting records: {keys_result.get('error')}")
                return keys_result # Return the error from list_keys

            keys = keys_result.get("keys", [])
            logger.debug(f"Found {len(keys)} keys to check.")

            # For each key, try to resolve its name (which is its ID)
            for key in keys:
                key_name = key.get("Name")
                key_id = key.get("Id") # The PeerID is the IPNS name

                if key_id:
                    logger.debug(f"Attempting to resolve IPNS name for key '{key_name}' (ID: {key_id})...")
                    try:
                        # Try to resolve the name to see if it's published
                        # Use nocache to get potentially updated value, but might be slower
                        resolve_result = self.resolve(key_id, nocache=True)

                        if resolve_result.get("success"):
                            logger.debug(f"Successfully resolved {key_id} -> {resolve_result.get('value')}")
                            # Create a record entry
                            record = {
                                "name": key_id,
                                "value": resolve_result["value"],
                                "key_name": key_name,
                                "last_resolved": datetime.now().isoformat(),
                            }

                            # If we have it in cache, add more details
                            if key_id in self._record_cache:
                                cached_record = self._record_cache[key_id]
                                record["details"] = cached_record.to_dict()

                            records.append(record)
                        else:
                             logger.debug(f"Could not resolve IPNS name for key '{key_name}' (ID: {key_id}). Maybe not published or expired.")

                    except Exception as resolve_e:
                        # Ignore errors for individual keys, log them
                        logger.warning(f"Error resolving IPNS name for key '{key_name}' (ID: {key_id}): {resolve_e}")
                        pass # Continue to the next key

            # Update metrics (success is true if the overall process didn't fail)
            duration = time.time() - start_time
            self._update_metrics("records", duration, True)
            logger.info(f"Finished getting records. Found {len(records)} published names.")

            return {
                "success": True,
                "records": records,
                "count": len(records),
                "duration": duration,
            }

        except Exception as e:
            duration = time.time() - start_time
            self._update_metrics("records", duration, False)
            logger.error(f"Exception during get_records: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Error getting records: {str(e)}",
                "exception": str(e),
                "duration": duration,
            }

    def _parse_duration(self, duration_str: str) -> int:
        """
        Parse a time duration string (e.g., "24h", "15m", "30s") into seconds.

        Args:
            duration_str (str): The duration string to parse.

        Returns:
            int: The duration in seconds. Returns 0 if the string is empty or invalid,
                 or the default TTL if parsing fails unexpectedly.
        """
        if not duration_str:
            return 0

        duration_str = duration_str.strip().lower()

        # Check for simple number (assume seconds)
        if duration_str.isdigit():
            return int(duration_str)

        # Handle units
        unit_multipliers = {
            "s": 1,
            "m": 60,
            "h": 3600,
            "d": 86400,
            "w": 604800, # Week
        }

        number_str = ""
        unit = ""

        for i, char in enumerate(reversed(duration_str)):
            if char.isalpha():
                unit = char
                number_str = duration_str[:-i-1]
                break
        else: # No unit found, might be just a number
             try:
                 return int(duration_str)
             except ValueError:
                 logger.warning(f"Could not parse duration string '{duration_str}', falling back to default TTL.")
                 return self.default_ttl # Fallback

        if unit in unit_multipliers:
            try:
                # Handle potential float values like "1.5h"
                number = float(number_str)
                return int(number * unit_multipliers[unit])
            except ValueError:
                logger.warning(f"Could not parse number part '{number_str}' in duration '{duration_str}', falling back to default TTL.")
                return self.default_ttl # Fallback
        else:
             logger.warning(f"Unknown unit '{unit}' in duration '{duration_str}', falling back to default TTL.")
             return self.default_ttl # Fallback

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics for IPNS and associated KeyManager operations.

        Returns:
            Dict[str, Any]: Dictionary containing performance metrics.
        """
        key_metrics = {}
        if self.key_manager:
            key_metrics_result = self.key_manager.get_metrics()
            if key_metrics_result.get("success"):
                key_metrics = key_metrics_result.get("metrics", {})

        return {
            "success": True,
            "metrics": self.performance_metrics,
            "key_metrics": key_metrics,
        }

# Global instance
_instance = None

def get_instance(connection_pool=None, key_manager=None, config=None) -> IPNSOperations:
    """Get or create a singleton instance of the IPNS operations."""
    global _instance
    if _instance is None:
        logger.debug("Creating new IPNSOperations instance.")
        _instance = IPNSOperations(connection_pool, key_manager, config)
    return _instance
