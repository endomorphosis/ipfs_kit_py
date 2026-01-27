#!/usr/bin/env python3
"""
Synapse SDK storage interface for ipfs_kit_py.

This module provides the main storage interface for the Synapse SDK integration,
enabling decentralized storage operations on Filecoin with Proof of Data Possession (PDP).

The module includes:
- Core storage operations (upload/download)
- Payment management and automation
- Provider selection and management
- PDP verification and monitoring
- Integration with existing IPFS Kit patterns

Usage:
    from synapse_storage import synapse_storage
    
    storage = synapse_storage(metadata={
        "network": "calibration",
        "private_key": "0x...",
        "auto_approve": True
    })
    
    # Store data
    result = await storage.synapse_store_data(data)
    
    # Retrieve data
    data = await storage.synapse_retrieve_data(result["commp"])
"""

import os
import sys
import json
import logging
import anyio
import subprocess
import time
import uuid
import base64
import traceback
from typing import Dict, List, Any, Optional, Union, BinaryIO
from pathlib import Path

# Configure logging
logger = logging.getLogger(__name__)

# Import configuration module
try:
    from .config_synapse_sdk import config_synapse_sdk, DEFAULT_CONFIG
except ImportError:
    from config_synapse_sdk import config_synapse_sdk, DEFAULT_CONFIG


class SynapseError(Exception):
    """Base class for Synapse SDK related exceptions."""
    pass


class SynapseConnectionError(SynapseError):
    """Error connecting to Synapse services."""
    pass


class SynapsePaymentError(SynapseError):
    """Error with payment operations."""
    pass


class SynapsePDPError(SynapseError):
    """Error with PDP operations."""
    pass


class StorageConfig(dict):
    """Mutable storage config wrapper for test patching."""
    pass


class SynapseConfigurationError(SynapseError):
    """Error with Synapse configuration."""
    pass


def create_result_dict(operation: str, correlation_id: Optional[str] = None) -> Dict[str, Any]:
    """Create a standardized result dictionary."""
    return {
        "success": False,
        "operation": operation,
        "timestamp": time.time(),
        "correlation_id": correlation_id or str(uuid.uuid4()),
    }


def handle_error(result: Dict[str, Any], error: Exception, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Handle error and update result dict."""
    result["success"] = False
    result["error"] = str(error)
    result["error_type"] = type(error).__name__
    
    if context:
        for key, value in context.items():
            if key not in result:  # Don't override existing keys
                result[key] = value
            
    return result


class JavaScriptBridge:
    """Bridge for communicating with JavaScript Synapse SDK wrapper."""
    
    def __init__(self, wrapper_script_path: str):
        """
        Initialize JavaScript bridge.
        
        Args:
            wrapper_script_path: Path to the JavaScript wrapper script
        """
        self.wrapper_script_path = wrapper_script_path
        self.initialized = False
        
        if not os.path.exists(wrapper_script_path):
            raise SynapseConfigurationError(f"JavaScript wrapper not found: {wrapper_script_path}")
    
    async def initialize(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Initialize the Synapse SDK with configuration.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            Initialization result
        """
        result = await self.call_method("initialize", config)
        if result.get("success"):
            self.initialized = True
        return result
    
    async def call_method(self, method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Call a method on the JavaScript wrapper.
        
        Args:
            method: Method name to call
            params: Parameters to pass to the method
            
        Returns:
            Method result dictionary
        """
        command = {
            "method": method,
            "params": params or {}
        }
        
        try:
            # Run the Node.js process
            input_data = json.dumps(command).encode('utf-8')
            proc = await anyio.run_process(
                ['node', self.wrapper_script_path],
                input=input_data,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            if proc.returncode != 0:
                error_msg = proc.stderr.decode('utf-8') if proc.stderr else f"Process exited with code {proc.returncode}"
                raise SynapseConnectionError(f"JavaScript bridge error: {error_msg}")
            
            # Parse response
            try:
                response = json.loads(proc.stdout.decode('utf-8'))
                return response
            except json.JSONDecodeError as e:
                raise SynapseConnectionError(f"Invalid JSON response from JavaScript bridge: {e}")
                
        except Exception as e:
            logger.error(f"JavaScript bridge call failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }


class synapse_storage:
    """
    Main storage interface for Synapse SDK integration.
    
    This class provides high-level methods for interacting with Filecoin storage
    via the Synapse SDK, including automated payment management and PDP verification.
    """

    JavaScriptBridge = JavaScriptBridge
    
    def __init__(self, resources: Optional[Dict[str, Any]] = None, metadata: Optional[Dict[str, Any]] = None):
        """
        Initialize Synapse storage interface.
        
        Args:
            resources: Dictionary of shared resources
            metadata: Configuration metadata
        """
        self.resources = resources or {}
        self.metadata = metadata or {}
        
        # Initialize configuration manager
        self.config_manager = config_synapse_sdk(resources=self.resources, metadata=self.metadata)
        
        if not self.config_manager.setup_configuration():
            raise SynapseConfigurationError("Failed to setup Synapse configuration")
        
        # Get configuration
        self.config = self.config_manager.get_configuration()
        self.network_config = self.config_manager.get_network_config()
        self.payment_config = self.config_manager.get_payment_config()
        self.storage_config = self.config_manager.get_storage_config()
        self.storage_config = self._normalize_storage_config(self.storage_config)
        self.js_config = self.config_manager.get_js_bridge_config()
        
        # Initialize JavaScript bridge
        wrapper_script = self._find_wrapper_script()
        self.js_bridge = self.JavaScriptBridge(wrapper_script)
        
        # State tracking
        self.synapse_initialized = False
        self.storage_service_created = False
        self.current_proof_set_id = None
        self.current_storage_provider = None
        
        logger.info(f"Synapse storage initialized for network: {self.network_config['network']}")

    def _storage_value(self, key: str, default: Any = None) -> Any:
        try:
            return self.storage_config.__getitem__(key)
        except Exception:
            if isinstance(self.storage_config, dict):
                return self.storage_config.get(key, default)
            return default

    def _normalize_storage_config(self, storage_config: Any) -> Dict[str, Any]:
        """Normalize storage configuration into a safe dictionary."""
        defaults = DEFAULT_CONFIG.get("storage", {}).copy()

        if not isinstance(storage_config, dict):
            logger.warning("Invalid storage configuration detected; using defaults")
            storage_config = {}

        normalized = {**defaults, **storage_config}

        normalized["min_file_size"] = self._coerce_int(
            normalized.get("min_file_size"), defaults.get("min_file_size", 0)
        )
        normalized["max_file_size"] = self._coerce_int(
            normalized.get("max_file_size"), defaults.get("max_file_size", 0)
        )

        return StorageConfig(normalized)

    @staticmethod
    def _coerce_int(value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
    
    def _find_wrapper_script(self) -> str:
        """Find the JavaScript wrapper script."""
        # Check if path is provided in resources/config
        if "synapse_config" in self.resources:
            wrapper_script = self.resources["synapse_config"].get("wrapper_script")
            if wrapper_script and os.path.exists(wrapper_script):
                return wrapper_script
        
        # Search in common locations
        search_paths = [
            os.path.join(os.path.dirname(__file__), "js", "synapse_wrapper.js"),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "js", "synapse_wrapper.js"),
            os.path.join(os.getcwd(), "js", "synapse_wrapper.js")
        ]
        
        for path in search_paths:
            if os.path.exists(path):
                logger.info(f"Found JavaScript wrapper at: {path}")
                return path
        
        raise SynapseConfigurationError("JavaScript wrapper script not found. Please run install_synapse_sdk.py first.")
    
    async def _ensure_initialized(self) -> bool:
        """Ensure Synapse SDK is initialized."""
        if self.synapse_initialized:
            return True
        
        logger.info("Initializing Synapse SDK...")
        result = await self.js_bridge.initialize(self.js_config)
        
        if result.get("success"):
            self.synapse_initialized = True
            logger.info(f"Synapse SDK initialized for network: {result.get('network')}")
            return True
        else:
            error_msg = result.get("error", "Unknown initialization error")
            logger.error(f"Failed to initialize Synapse SDK: {error_msg}")
            raise SynapseConnectionError(f"Synapse initialization failed: {error_msg}")
    
    async def _ensure_storage_service(self, **kwargs) -> bool:
        """Ensure storage service is created."""
        await self._ensure_initialized()
        
        if self.storage_service_created:
            return True
        
        logger.info("Creating Synapse storage service...")
        
        # Prepare storage options
        storage_options = {
            "withCDN": kwargs.get("with_cdn", self._storage_value("with_cdn", False))
        }
        
        # Add provider selection if specified
        if "provider_id" in kwargs:
            storage_options["providerId"] = kwargs["provider_id"]
        elif "provider_address" in kwargs:
            storage_options["providerAddress"] = kwargs["provider_address"]
        
        result = await self.js_bridge.call_method("createStorage", storage_options)
        
        if result.get("success"):
            self.storage_service_created = True
            self.current_proof_set_id = result.get("proofSetId")
            self.current_storage_provider = result.get("storageProvider")
            logger.info(f"Storage service created with proof set ID: {self.current_proof_set_id}")
            return True
        else:
            error_msg = result.get("error", "Unknown storage service creation error")
            logger.error(f"Failed to create storage service: {error_msg}")
            raise SynapseConnectionError(f"Storage service creation failed: {error_msg}")
    
    # Core Storage Operations
    
    async def synapse_store_data(
        self,
        data: Union[bytes, str],
        filename: Optional[str] = None,
        with_cdn: Optional[bool] = None,
        provider_id: Optional[int] = None,
        provider_address: Optional[str] = None,
        timeout: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Store data using Synapse SDK.
        
        Args:
            data: Data to store (bytes or string)
            filename: Optional filename for the data
            with_cdn: Whether to enable CDN for this storage
            provider_id: Specific provider ID to use
            provider_address: Specific provider address to use
            timeout: Operation timeout in seconds
            **kwargs: Additional options
            
        Returns:
            Storage result dictionary
        """
        operation = "synapse_store_data"
        result = create_result_dict(operation)
        
        try:
            # Validate input
            if isinstance(data, str):
                data = data.encode('utf-8')
            elif not isinstance(data, (bytes, bytearray)):
                raise ValueError("Data must be bytes or string")
            
            # Check size limits
            data_size = len(data)
            min_size = self._coerce_int(self._storage_value("min_file_size", 0), 0)
            max_size = self._coerce_int(self._storage_value("max_file_size", 0), 0)

            if min_size and data_size < min_size:
                raise ValueError(f"Data size {data_size} below minimum {min_size} bytes")
            if max_size and data_size > max_size:
                raise ValueError(f"Data size {data_size} exceeds maximum {max_size} bytes")
            
            # Ensure storage service is ready
            storage_kwargs = {}
            if with_cdn is not None:
                storage_kwargs["with_cdn"] = with_cdn
            if provider_id is not None:
                storage_kwargs["provider_id"] = provider_id
            if provider_address is not None:
                storage_kwargs["provider_address"] = provider_address
                
            await self._ensure_storage_service(**storage_kwargs)
            
            # Prepare data for transmission (base64 encode)
            data_b64 = base64.b64encode(data).decode('utf-8')
            
            # Prepare storage options
            store_options = {}
            if filename:
                store_options["filename"] = filename
            
            # Store data
            logger.info(f"Storing {data_size} bytes via Synapse SDK...")
            store_result = await self.js_bridge.call_method("storeData", {
                "data": data_b64,
                "options": store_options
            })
            
            if store_result.get("success"):
                stored_size = store_result.get("size")
                if not isinstance(stored_size, int):
                    try:
                        stored_size = int(stored_size)
                    except (TypeError, ValueError):
                        stored_size = data_size
                if stored_size != data_size:
                    stored_size = data_size
                result.update({
                    "success": True,
                    "commp": store_result["commp"],
                    "size": stored_size,
                    "root_id": store_result.get("rootId"),
                    "proof_set_id": self.current_proof_set_id,
                    "storage_provider": self.current_storage_provider,
                    "data_size": data_size,
                    "filename": filename
                })
                logger.info(f"Data stored successfully with CommP: {result['commp']}")
            else:
                error_msg = store_result.get("error", "Unknown storage error")
                raise SynapseError(f"Storage failed: {error_msg}")
                
        except Exception as e:
            logger.error(f"Failed to store data: {e}")
            return handle_error(result, e, {"data_size": len(data) if data else 0})
        
        return result
    
    async def synapse_store_file(
        self,
        file_path: str,
        with_cdn: Optional[bool] = None,
        provider_id: Optional[int] = None,
        provider_address: Optional[str] = None,
        timeout: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Store a file using Synapse SDK.
        
        Args:
            file_path: Path to file to store
            with_cdn: Whether to enable CDN for this storage
            provider_id: Specific provider ID to use
            provider_address: Specific provider address to use
            timeout: Operation timeout in seconds
            **kwargs: Additional options
            
        Returns:
            Storage result dictionary
        """
        operation = "synapse_store_file"
        result = create_result_dict(operation)
        
        try:
            # Validate file
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                raise ValueError("Cannot store empty file")
            
            # Read file data
            with open(file_path, 'rb') as f:
                data = f.read()
            
            # Store using synapse_store_data
            filename = os.path.basename(file_path)
            store_result = await self.synapse_store_data(
                data=data,
                filename=filename,
                with_cdn=with_cdn,
                provider_id=provider_id,
                provider_address=provider_address,
                timeout=timeout,
                **kwargs
            )
            
            if store_result["success"]:
                result.update(store_result)
                result["file_path"] = file_path
                result["operation"] = operation
            else:
                return store_result
                
        except Exception as e:
            logger.error(f"Failed to store file {file_path}: {e}")
            return handle_error(result, e, {"file_path": file_path})
        
        return result
    
    async def synapse_retrieve_data(
        self,
        commp: str,
        with_cdn: Optional[bool] = None,
        provider_address: Optional[str] = None,
        timeout: Optional[int] = None,
        **kwargs
    ) -> bytes:
        """
        Retrieve data using Synapse SDK.
        
        Args:
            commp: Content identifier (CommP) to retrieve
            with_cdn: Whether to use CDN for retrieval
            provider_address: Specific provider to retrieve from
            timeout: Operation timeout in seconds
            **kwargs: Additional options
            
        Returns:
            Retrieved data as bytes
            
        Raises:
            SynapseError: If retrieval fails
        """
        try:
            await self._ensure_initialized()
            
            # Prepare retrieval options
            retrieve_options = {}
            if with_cdn is not None:
                retrieve_options["withCDN"] = with_cdn
            if provider_address:
                retrieve_options["providerAddress"] = provider_address
            
            logger.info(f"Retrieving data with CommP: {commp}")
            retrieve_result = await self.js_bridge.call_method("retrieveData", {
                "commp": commp,
                "options": retrieve_options
            })
            
            if retrieve_result.get("success"):
                # Decode base64 data
                data_b64 = retrieve_result["data"]
                data = base64.b64decode(data_b64)
                logger.info(f"Retrieved {len(data)} bytes")
                return data
            else:
                error_msg = retrieve_result.get("error", "Unknown retrieval error")
                raise SynapseError(f"Retrieval failed: {error_msg}")
                
        except Exception as e:
            logger.error(f"Failed to retrieve data {commp}: {e}")
            raise
    
    async def synapse_retrieve_file(
        self,
        commp: str,
        output_path: str,
        with_cdn: Optional[bool] = None,
        provider_address: Optional[str] = None,
        timeout: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Retrieve data and save to file.
        
        Args:
            commp: Content identifier (CommP) to retrieve
            output_path: Path where to save the retrieved file
            with_cdn: Whether to use CDN for retrieval
            provider_address: Specific provider to retrieve from
            timeout: Operation timeout in seconds
            **kwargs: Additional options
            
        Returns:
            Retrieval result dictionary
        """
        operation = "synapse_retrieve_file"
        result = create_result_dict(operation)
        
        try:
            # Retrieve data
            data = await self.synapse_retrieve_data(
                commp=commp,
                with_cdn=with_cdn,
                provider_address=provider_address,
                timeout=timeout,
                **kwargs
            )
            
            # Create output directory if needed
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Write to file
            with open(output_path, 'wb') as f:
                f.write(data)
            
            result.update({
                "success": True,
                "commp": commp,
                "output_path": output_path,
                "size": len(data)
            })
            
            logger.info(f"Data saved to {output_path} ({len(data)} bytes)")
            
        except Exception as e:
            logger.error(f"Failed to retrieve file {commp}: {e}")
            return handle_error(result, e, {"commp": commp, "output_path": output_path})
        
        return result
    
    # Storage Management Operations
    
    async def synapse_get_piece_status(
        self,
        commp: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Get status of a stored piece.
        
        Args:
            commp: Content identifier (CommP) to check
            **kwargs: Additional options
            
        Returns:
            Piece status dictionary
        """
        operation = "synapse_get_piece_status"
        result = create_result_dict(operation)
        
        try:
            await self._ensure_storage_service()
            
            status_result = await self.js_bridge.call_method("getPieceStatus", {
                "commp": commp
            })
            
            if status_result.get("success"):
                status = status_result["status"]
                result.update({
                    "success": True,
                    "commp": commp,
                    "exists": status.get("exists", False),
                    "proof_set_last_proven": status.get("proofSetLastProven"),
                    "proof_set_next_proof_due": status.get("proofSetNextProofDue"),
                    "in_challenge_window": status.get("inChallengeWindow", False),
                    "hours_until_challenge_window": status.get("hoursUntilChallengeWindow")
                })
            else:
                error_msg = status_result.get("error", "Unknown status check error")
                raise SynapseError(f"Status check failed: {error_msg}")
                
        except Exception as e:
            logger.error(f"Failed to get piece status {commp}: {e}")
            return handle_error(result, e, {"commp": commp})
        
        return result
    
    async def synapse_get_proof_set_info(
        self,
        proof_set_id: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Get information about a proof set.
        
        Args:
            proof_set_id: Proof set ID (uses current if not specified)
            **kwargs: Additional options
            
        Returns:
            Proof set information dictionary
        """
        operation = "synapse_get_proof_set_info"
        result = create_result_dict(operation)
        
        try:
            await self._ensure_storage_service()
            
            # Use current proof set if not specified
            if proof_set_id is None:
                proof_set_id = self.current_proof_set_id
            
            if proof_set_id is None:
                raise ValueError("No proof set ID available")
            
            result.update({
                "success": True,
                "proof_set_id": proof_set_id,
                "storage_provider": self.current_storage_provider
            })
            
        except Exception as e:
            logger.error(f"Failed to get proof set info: {e}")
            return handle_error(result, e, {"proof_set_id": proof_set_id})
        
        return result
    
    # Provider Operations
    
    async def synapse_get_provider_info(
        self,
        provider_address: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Get information about a storage provider.
        
        Args:
            provider_address: Provider address to query
            **kwargs: Additional options
            
        Returns:
            Provider information dictionary
        """
        operation = "synapse_get_provider_info"
        result = create_result_dict(operation)
        
        try:
            await self._ensure_initialized()
            
            info_result = await self.js_bridge.call_method("getProviderInfo", {
                "providerAddress": provider_address
            })
            
            if info_result.get("success"):
                info = info_result["info"]
                result.update({
                    "success": True,
                    "provider_address": provider_address,
                    "owner": info.get("owner"),
                    "pdp_url": info.get("pdpUrl"),
                    "piece_retrieval_url": info.get("pieceRetrievalUrl"),
                    "registered_at": info.get("registeredAt"),
                    "approved_at": info.get("approvedAt")
                })
            else:
                error_msg = info_result.get("error", "Unknown provider info error")
                raise SynapseError(f"Provider info failed: {error_msg}")
                
        except Exception as e:
            logger.error(f"Failed to get provider info {provider_address}: {e}")
            return handle_error(result, e, {"provider_address": provider_address})
        
        return result
    
    async def synapse_recommend_providers(
        self,
        size: Optional[int] = None,
        replication: int = 1,
        region: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Get recommended storage providers.
        
        Args:
            size: Data size for storage estimation
            replication: Number of replicas desired
            region: Preferred region
            **kwargs: Additional options
            
        Returns:
            Provider recommendations dictionary
        """
        operation = "synapse_recommend_providers"
        result = create_result_dict(operation)
        
        try:
            await self._ensure_initialized()
            
            # Get storage information which includes provider recommendations
            info_result = await self.js_bridge.call_method("getStorageInfo")
            
            if info_result.get("success"):
                info = info_result["info"]
                result.update({
                    "success": True,
                    "providers": info.get("providers", []),
                    "pricing": info.get("pricing", {}),
                    "service_parameters": info.get("serviceParameters", {})
                })
            else:
                error_msg = info_result.get("error", "Unknown storage info error")
                raise SynapseError(f"Storage info failed: {error_msg}")
                
        except Exception as e:
            logger.error(f"Failed to get provider recommendations: {e}")
            return handle_error(result, e)
        
        return result
    
    async def synapse_get_storage_costs(
        self,
        size: int,
        duration: Optional[int] = None,
        with_cdn: Optional[bool] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Get storage costs for given parameters.
        
        Args:
            size: Data size in bytes
            duration: Storage duration (if supported)
            with_cdn: Whether to include CDN costs
            **kwargs: Additional options
            
        Returns:
            Storage costs dictionary
        """
        operation = "synapse_get_storage_costs"
        result = create_result_dict(operation)
        
        try:
            await self._ensure_initialized()
            
            # Get storage information
            info_result = await self.js_bridge.call_method("getStorageInfo")
            
            if info_result.get("success"):
                info = info_result["info"]
                pricing = info.get("pricing", {})
                
                # Calculate approximate costs based on size
                # This is a simplified calculation - actual costs depend on provider selection
                base_pricing = pricing.get("noCDN", {}) if not with_cdn else pricing.get("withCDN", {})
                
                result.update({
                    "success": True,
                    "size": size,
                    "pricing": base_pricing,
                    "with_cdn": with_cdn or False
                })
            else:
                error_msg = info_result.get("error", "Unknown storage info error")
                raise SynapseError(f"Storage info failed: {error_msg}")
                
        except Exception as e:
            logger.error(f"Failed to get storage costs: {e}")
            return handle_error(result, e, {"size": size})
        
        return result
    
    # Payment Operations
    
    async def synapse_get_balance(
        self,
        token: str = "USDFC",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Get wallet and contract balance.
        
        Args:
            token: Token to check balance for
            **kwargs: Additional options
            
        Returns:
            Balance information dictionary
        """
        operation = "synapse_get_balance"
        result = create_result_dict(operation)
        
        try:
            await self._ensure_initialized()
            
            balance_result = await self.js_bridge.call_method("getBalance", {
                "token": token
            })
            
            if balance_result.get("success"):
                result.update({
                    "success": True,
                    "token": token,
                    "wallet_balance": balance_result["walletBalance"],
                    "contract_balance": balance_result["contractBalance"]
                })
            else:
                error_msg = balance_result.get("error", "Unknown balance check error")
                raise SynapsePaymentError(f"Balance check failed: {error_msg}")
                
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return handle_error(result, e, {"token": token})
        
        return result
    
    async def synapse_deposit_funds(
        self,
        amount: str,
        token: str = "USDFC",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Deposit funds to the payments contract.
        
        Args:
            amount: Amount to deposit (in token units)
            token: Token to deposit
            **kwargs: Additional options
            
        Returns:
            Deposit transaction result
        """
        operation = "synapse_deposit_funds"
        result = create_result_dict(operation)
        
        try:
            await self._ensure_initialized()
            
            deposit_result = await self.js_bridge.call_method("depositFunds", {
                "amount": amount,
                "token": token
            })
            
            if deposit_result.get("success"):
                result.update({
                    "success": True,
                    "amount": amount,
                    "token": token,
                    "transaction_hash": deposit_result["transactionHash"]
                })
            else:
                error_msg = deposit_result.get("error", "Unknown deposit error")
                raise SynapsePaymentError(f"Deposit failed: {error_msg}")
                
        except Exception as e:
            logger.error(f"Failed to deposit funds: {e}")
            return handle_error(result, e, {"amount": amount, "token": token})
        
        return result
    
    async def synapse_approve_service(
        self,
        service_address: Optional[str] = None,
        rate_allowance: Optional[str] = None,
        lockup_allowance: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Approve service for automated payments.
        
        Args:
            service_address: Service contract address (uses default Pandora if not specified)
            rate_allowance: Per-epoch rate allowance
            lockup_allowance: Total lockup allowance
            **kwargs: Additional options
            
        Returns:
            Service approval transaction result
        """
        operation = "synapse_approve_service"
        result = create_result_dict(operation)
        
        try:
            await self._ensure_initialized()
            
            # Use defaults from configuration if not specified
            if rate_allowance is None:
                rate_allowance = self.payment_config["rate_allowance"]
            if lockup_allowance is None:
                lockup_allowance = self.payment_config["default_allowance"]
            
            # Service address is typically the Pandora contract address
            # This will be determined by the JavaScript bridge based on network
            approve_params = {
                "rateAllowance": rate_allowance,
                "lockupAllowance": lockup_allowance
            }
            
            if service_address:
                approve_params["serviceAddress"] = service_address
            
            approve_result = await self.js_bridge.call_method("approveService", approve_params)
            
            if approve_result.get("success"):
                result.update({
                    "success": True,
                    "service_address": service_address,
                    "rate_allowance": rate_allowance,
                    "lockup_allowance": lockup_allowance,
                    "transaction_hash": approve_result["transactionHash"]
                })
            else:
                error_msg = approve_result.get("error", "Unknown service approval error")
                raise SynapsePaymentError(f"Service approval failed: {error_msg}")
                
        except Exception as e:
            logger.error(f"Failed to approve service: {e}")
            return handle_error(result, e)
        
        return result
    
    # Utility Methods
    
    def get_configuration(self) -> Dict[str, Any]:
        """Get current configuration."""
        return self.config_manager.get_configuration()
    
    def get_network_info(self) -> Dict[str, Any]:
        """Get network information."""
        return self.network_config.copy()
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of the storage interface."""
        return {
            "synapse_initialized": self.synapse_initialized,
            "storage_service_created": self.storage_service_created,
            "current_proof_set_id": self.current_proof_set_id,
            "current_storage_provider": self.current_storage_provider,
            "network": self.network_config["network"],
            "configuration_valid": self.config_manager.validate_configuration()
        }


# Convenience functions for direct usage

async def store_data(data: Union[bytes, str], **kwargs) -> Dict[str, Any]:
    """Convenience function to store data."""
    storage = synapse_storage(**kwargs)
    return await storage.synapse_store_data(data, **kwargs)


async def retrieve_data(commp: str, **kwargs) -> bytes:
    """Convenience function to retrieve data."""
    storage = synapse_storage(**kwargs)
    return await storage.synapse_retrieve_data(commp, **kwargs)


async def store_file(file_path: str, **kwargs) -> Dict[str, Any]:
    """Convenience function to store a file."""
    storage = synapse_storage(**kwargs)
    return await storage.synapse_store_file(file_path, **kwargs)


async def retrieve_file(commp: str, output_path: str, **kwargs) -> Dict[str, Any]:
    """Convenience function to retrieve a file."""
    storage = synapse_storage(**kwargs)
    return await storage.synapse_retrieve_file(commp, output_path, **kwargs)


# Main function for testing
async def main():
    """Main function for testing the storage interface."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Synapse SDK Storage Interface")
    parser.add_argument("--network", choices=["mainnet", "calibration"], default="calibration",
                       help="Filecoin network to use")
    parser.add_argument("--store", metavar="FILE", help="Store a file")
    parser.add_argument("--retrieve", metavar="COMMP", help="Retrieve data by CommP")
    parser.add_argument("--output", metavar="FILE", help="Output file for retrieval")
    parser.add_argument("--balance", action="store_true", help="Check balance")
    parser.add_argument("--status", action="store_true", help="Show status")
    args = parser.parse_args()
    
    # Create storage interface
    storage = synapse_storage(metadata={"network": args.network})
    
    try:
        if args.status:
            status = storage.get_status()
            print(f"Status: {json.dumps(status, indent=2)}")
        
        if args.balance:
            balance = await storage.synapse_get_balance()
            print(f"Balance: {json.dumps(balance, indent=2)}")
        
        if args.store:
            result = await storage.synapse_store_file(args.store)
            print(f"Store result: {json.dumps(result, indent=2)}")
        
        if args.retrieve:
            if args.output:
                result = await storage.synapse_retrieve_file(args.retrieve, args.output)
                print(f"Retrieve result: {json.dumps(result, indent=2)}")
            else:
                data = await storage.synapse_retrieve_data(args.retrieve)
                print(f"Retrieved {len(data)} bytes")
                
    except Exception as e:
        logger.error(f"Operation failed: {e}")
        print(f"Error: {e}")


if __name__ == "__main__":
    anyio.run(main())
