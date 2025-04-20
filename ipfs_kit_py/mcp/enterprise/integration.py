"""
Enterprise Features Integration Module for MCP Server.

This module integrates Phase 3 Enterprise Features with the MCP server,
including High Availability Architecture, Advanced Security, and
Data Lifecycle Management components.
"""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse

# Import enterprise components
from ipfs_kit_py.mcp.ha.integration import setup_ha, HAConfig, HighAvailabilityIntegration
from ipfs_kit_py.mcp.security.encryption.core import (
    EndToEndEncryption, 
    EncryptionKey, 
    EncryptedData,
    EncryptionAlgorithm,
    KeyType
)
from ipfs_kit_py.mcp.enterprise.encryption import (
    KeyManager,
    EncryptionManager,
    BackendEncryptionHandler,
    KeyStorageType,
    RetentionPolicy
)
from ipfs_kit_py.mcp.enterprise.data_lifecycle import (
    DataLifecycleManager,
    RetentionPolicy,
    ArchivePolicy,
    DataClassification,
    ComplianceRegime,
    StorageTier
)

# Configure logging
logger = logging.getLogger(__name__)


class EnterpriseFeatures:
    """
    Enterprise Features Integration for MCP Server.
    
    This class coordinates the initialization and integration of Phase 3
    Enterprise Features with the MCP server, including:
    
    1. High Availability Architecture
    2. Advanced Security Features 
    3. Data Lifecycle Management
    """
    
    def __init__(self, app: FastAPI):
        """
        Initialize enterprise features integration.
        
        Args:
            app: FastAPI application instance
        """
        self.app = app
        self.ha_integration: Optional[HighAvailabilityIntegration] = None
        self.encryption_manager: Optional[EncryptionManager] = None
        self.key_manager: Optional[KeyManager] = None
        self.backend_encryption: Optional[BackendEncryptionHandler] = None
        self.lifecycle_manager: Optional[DataLifecycleManager] = None
        self.e2e_encryption: Optional[EndToEndEncryption] = None
        
        # Config defaults
        self.config = {
            "enabled": True,
            "data_directory": os.path.join(os.path.expanduser("~"), ".ipfs_kit", "mcp", "enterprise"),
            "ha": {
                "enabled": True,
                "enable_replication": True,
                "consistency_model": "eventual"
            },
            "security": {
                "enabled": True,
                "encryption_enabled": True,
                "key_storage_type": "file",
                "e2e_encryption_enabled": True
            },
            "lifecycle": {
                "enabled": True,
                "auto_classify": True,
                "default_retention_days": 365
            }
        }
        
        # Ensure data directory exists
        os.makedirs(self.config["data_directory"], exist_ok=True)
        
        # Register shutdown handler
        @app.on_event("shutdown")
        async def shutdown_enterprise_features():
            await self.shutdown()
    
    async def initialize(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize enterprise features.
        
        Args:
            config: Optional configuration dictionary to override defaults
        """
        if config:
            # Update config with provided values
            self._update_config(config)
        
        if not self.config["enabled"]:
            logger.info("Enterprise features disabled, skipping initialization")
            return
        
        # Create data directories
        os.makedirs(os.path.join(self.config["data_directory"], "keys"), exist_ok=True)
        os.makedirs(os.path.join(self.config["data_directory"], "policies"), exist_ok=True)
        os.makedirs(os.path.join(self.config["data_directory"], "encryption"), exist_ok=True)
        
        # Initialize components based on config
        await self._init_security()
        await self._init_lifecycle()
        await self._init_ha()
        
        # Register API routes
        self._register_api_routes()
        
        logger.info("Enterprise features initialized successfully")
    
    async def shutdown(self) -> None:
        """Shutdown enterprise features and cleanup resources."""
        if self.ha_integration:
            await self.ha_integration.stop()
        
        if self.lifecycle_manager:
            self.lifecycle_manager.stop()
        
        logger.info("Enterprise features shutdown complete")
    
    async def _init_security(self) -> None:
        """Initialize security features."""
        if not self.config["security"]["enabled"]:
            return
        
        logger.info("Initializing enterprise security features")
        
        # Initialize key manager
        storage_type_str = self.config["security"]["key_storage_type"]
        storage_type = KeyStorageType(storage_type_str)
        
        self.key_manager = KeyManager(
            storage_type=storage_type,
            storage_path=os.path.join(self.config["data_directory"], "keys")
        )
        
        # Initialize encryption manager
        self.encryption_manager = EncryptionManager(self.key_manager)
        
        # Initialize backend encryption handler
        self.backend_encryption = BackendEncryptionHandler(self.encryption_manager)
        
        # Initialize E2E encryption if enabled
        if self.config["security"]["e2e_encryption_enabled"]:
            self.e2e_encryption = EndToEndEncryption(
                key_store_path=os.path.join(self.config["data_directory"], "encryption", "e2e_keys.json")
            )
        
        logger.info("Enterprise security features initialized")
    
    async def _init_lifecycle(self) -> None:
        """Initialize data lifecycle management."""
        if not self.config["lifecycle"]["enabled"]:
            return
        
        logger.info("Initializing enterprise data lifecycle management")
        
        # Initialize data lifecycle manager
        self.lifecycle_manager = DataLifecycleManager(
            storage_path=os.path.join(self.config["data_directory"], "lifecycle")
        )
        
        # Start lifecycle manager
        self.lifecycle_manager.start()
        
        # Create default policies if needed
        if not self.lifecycle_manager.list_retention_policies():
            self._create_default_policies()
        
        logger.info("Enterprise data lifecycle management initialized")
    
    async def _init_ha(self) -> None:
        """Initialize high availability architecture."""
        if not self.config["ha"]["enabled"]:
            return
        
        logger.info("Initializing enterprise high availability architecture")
        
        # Configure HA
        ha_config = HAConfig(
            enabled=True,
            cluster_hosts=os.environ.get("MCP_CLUSTER_HOSTS", ""),
            region=os.environ.get("MCP_REGION", "default"),
            zone=os.environ.get("MCP_ZONE", "default"),
            enable_replication=self.config["ha"]["enable_replication"],
            consistency_model=self.config["ha"]["consistency_model"],
            enable_load_balancing=True
        )
        
        # Set up HA integration
        self.ha_integration = await setup_ha(self.app, ha_config)
        
        logger.info("Enterprise high availability architecture initialized")
    
    def _register_api_routes(self) -> None:
        """Register API routes for enterprise features."""
        # Enterprise status endpoint
        @self.app.get("/api/v0/enterprise/status")
        async def enterprise_status():
            """Get status of enterprise features."""
            status = {
                "enabled": self.config["enabled"],
                "components": {
                    "ha": {
                        "enabled": self.config["ha"]["enabled"],
                        "status": "active" if self.ha_integration else "disabled"
                    },
                    "security": {
                        "enabled": self.config["security"]["enabled"],
                        "encryption": self.config["security"]["encryption_enabled"],
                        "e2e_encryption": self.config["security"]["e2e_encryption_enabled"],
                        "status": "active" if self.encryption_manager else "disabled"
                    },
                    "lifecycle": {
                        "enabled": self.config["lifecycle"]["enabled"],
                        "status": "active" if self.lifecycle_manager else "disabled"
                    }
                }
            }
            
            # Add HA details if available
            if self.ha_integration:
                status["ha"] = self.ha_integration.get_status()
            
            return status
        
        # Register security routes if enabled
        if self.config["security"]["enabled"]:
            self._register_security_routes()
        
        # Register lifecycle routes if enabled
        if self.config["lifecycle"]["enabled"]:
            self._register_lifecycle_routes()
    
    def _register_security_routes(self) -> None:
        """Register security-related API routes."""
        # Encryption key management
        @self.app.get("/api/v0/enterprise/security/keys")
        async def list_encryption_keys():
            """List encryption keys."""
            if not self.key_manager:
                raise HTTPException(status_code=503, detail="Key manager not initialized")
            
            keys = self.key_manager.list_keys()
            return {
                "success": True,
                "keys": [k.to_dict() for k in keys]
            }
        
        @self.app.post("/api/v0/enterprise/security/keys")
        async def create_encryption_key(
            key_type: str,
            algorithm: str,
            description: Optional[str] = None,
            expires_days: Optional[int] = None
        ):
            """Create a new encryption key."""
            if not self.key_manager:
                raise HTTPException(status_code=503, detail="Key manager not initialized")
            
            try:
                key = self.key_manager.generate_key(
                    key_type=key_type,
                    algorithm=algorithm,
                    description=description,
                    expires_days=expires_days
                )
                
                return {
                    "success": True,
                    "key": key.to_dict()
                }
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))
        
        @self.app.delete("/api/v0/enterprise/security/keys/{key_id}")
        async def delete_encryption_key(key_id: str):
            """Delete an encryption key."""
            if not self.key_manager:
                raise HTTPException(status_code=503, detail="Key manager not initialized")
            
            success = self.key_manager.delete_key(key_id)
            if not success:
                raise HTTPException(status_code=404, detail=f"Key not found: {key_id}")
            
            return {
                "success": True,
                "message": f"Key {key_id} deleted"
            }
        
        # End-to-end encryption
        if self.e2e_encryption:
            @self.app.post("/api/v0/enterprise/security/e2e/encrypt")
            async def encrypt_data(
                request: Request,
                algorithm: Optional[str] = None,
                key_id: Optional[str] = None
            ):
                """Encrypt data with end-to-end encryption."""
                if not self.e2e_encryption:
                    raise HTTPException(status_code=503, detail="E2E encryption not initialized")
                
                try:
                    # Read request body
                    body = await request.body()
                    
                    # Set default algorithm if not specified
                    if not algorithm:
                        algorithm = EncryptionAlgorithm.AES_256_GCM
                    else:
                        algorithm = EncryptionAlgorithm(algorithm)
                    
                    # Generate key if not specified
                    if not key_id:
                        key = self.e2e_encryption.generate_key(algorithm=algorithm)
                        key_id = key.key_id
                    
                    # Encrypt data
                    encrypted_data = self.e2e_encryption.encrypt(body, key_id)
                    
                    return {
                        "success": True,
                        "encrypted_data": encrypted_data.to_dict()
                    }
                except Exception as e:
                    raise HTTPException(status_code=400, detail=str(e))
            
            @self.app.post("/api/v0/enterprise/security/e2e/decrypt")
            async def decrypt_data(encrypted_data: Dict[str, Any]):
                """Decrypt data with end-to-end encryption."""
                if not self.e2e_encryption:
                    raise HTTPException(status_code=503, detail="E2E encryption not initialized")
                
                try:
                    # Convert dict to EncryptedData object
                    enc_data = EncryptedData.from_dict(encrypted_data)
                    
                    # Decrypt data
                    decrypted_data = self.e2e_encryption.decrypt(enc_data)
                    
                    return JSONResponse(
                        content={"success": True},
                        headers={"Content-Disposition": "attachment; filename=decrypted_data"},
                        media_type="application/octet-stream",
                        content=decrypted_data
                    )
                except Exception as e:
                    raise HTTPException(status_code=400, detail=str(e))
    
    def _register_lifecycle_routes(self) -> None:
        """Register lifecycle-related API routes."""
        # Retention policies
        @self.app.get("/api/v0/enterprise/lifecycle/retention")
        async def list_retention_policies():
            """List retention policies."""
            if not self.lifecycle_manager:
                raise HTTPException(status_code=503, detail="Lifecycle manager not initialized")
            
            policies = self.lifecycle_manager.list_retention_policies()
            return {
                "success": True,
                "policies": [p.to_dict() for p in policies]
            }
        
        @self.app.post("/api/v0/enterprise/lifecycle/retention")
        async def create_retention_policy(policy: Dict[str, Any]):
            """Create a new retention policy."""
            if not self.lifecycle_manager:
                raise HTTPException(status_code=503, detail="Lifecycle manager not initialized")
            
            try:
                # Convert dict to RetentionPolicy object
                retention_policy = RetentionPolicy.from_dict(policy)
                
                # Add policy
                policy_id = self.lifecycle_manager.add_retention_policy(retention_policy)
                
                return {
                    "success": True,
                    "policy_id": policy_id
                }
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))
        
        @self.app.delete("/api/v0/enterprise/lifecycle/retention/{policy_id}")
        async def delete_retention_policy(policy_id: str):
            """Delete a retention policy."""
            if not self.lifecycle_manager:
                raise HTTPException(status_code=503, detail="Lifecycle manager not initialized")
            
            success = self.lifecycle_manager.delete_retention_policy(policy_id)
            if not success:
                raise HTTPException(status_code=404, detail=f"Policy not found: {policy_id}")
            
            return {
                "success": True,
                "message": f"Policy {policy_id} deleted"
            }
        
        # Data classification
        @self.app.post("/api/v0/enterprise/lifecycle/classify")
        async def classify_object(
            object_id: str,
            object_path: str,
            content_type: str,
            metadata: Dict[str, Any]
        ):
            """Classify an object based on content and metadata."""
            if not self.lifecycle_manager:
                raise HTTPException(status_code=503, detail="Lifecycle manager not initialized")
            
            classification = self.lifecycle_manager.get_object_classification(
                object_id=object_id,
                object_path=object_path,
                metadata=metadata,
                content_type=content_type
            )
            
            return {
                "success": True,
                "object_id": object_id,
                "classification": classification.value
            }
        
        # Lifecycle management operations
        @self.app.post("/api/v0/enterprise/lifecycle/apply")
        async def apply_lifecycle_policies(
            object_id: str,
            object_path: str,
            content_type: str,
            backend: str,
            size_bytes: int,
            metadata: Dict[str, Any],
            background_tasks: BackgroundTasks
        ):
            """Apply lifecycle policies to an object."""
            if not self.lifecycle_manager:
                raise HTTPException(status_code=503, detail="Lifecycle manager not initialized")
            
            # Apply policies in the background
            background_tasks.add_task(
                self.lifecycle_manager.apply_policies_to_object,
                object_id=object_id,
                object_path=object_path,
                metadata=metadata,
                content_type=content_type,
                backend=backend,
                size_bytes=size_bytes
            )
            
            return {
                "success": True,
                "message": f"Lifecycle policies being applied to {object_id}",
                "status": "processing"
            }
    
    def _update_config(self, config: Dict[str, Any]) -> None:
        """
        Update configuration with provided values.
        
        Args:
            config: Configuration dictionary to merge with defaults
        """
        def _deep_update(source, updates):
            for key, value in updates.items():
                if key in source and isinstance(source[key], dict) and isinstance(value, dict):
                    _deep_update(source[key], value)
                else:
                    source[key] = value
        
        _deep_update(self.config, config)
    
    def _create_default_policies(self) -> None:
        """Create default policies for the lifecycle manager."""
        if not self.lifecycle_manager:
            return
        
        # Create a default retention policy
        default_retention = RetentionPolicy(
            id=str(uuid.uuid4()),
            name="Default Retention Policy",
            description="Default policy for all data",
            retention_period_days=self.config["lifecycle"]["default_retention_days"],
            actions=[RetentionAction.ARCHIVE],
            triggers=[RetentionTrigger.AGE]
        )
        
        self.lifecycle_manager.add_retention_policy(default_retention)
        
        # Log creation
        logger.info(f"Created default retention policy: {default_retention.id}")


async def setup_enterprise_features(app: FastAPI, config: Optional[Dict[str, Any]] = None) -> EnterpriseFeatures:
    """
    Set up enterprise features for the MCP server.
    
    Args:
        app: FastAPI application instance
        config: Optional configuration dictionary
        
    Returns:
        EnterpriseFeatures instance
    """
    # Create enterprise features instance
    enterprise = EnterpriseFeatures(app)
    
    # Initialize with config
    await enterprise.initialize(config)
    
    # Store in app state
    app.state.enterprise = enterprise
    
    return enterprise