"""
Enterprise Security Module for MCP Server

This module provides advanced security features for the MCP server, including:
- End-to-end encryption
- Secure key management
- Cryptographic operations
- Security policy enforcement

Part of the MCP Roadmap Phase 3: Enterprise Features (Q1 2026).
"""

import os
import logging
import importlib
from enum import Enum
from typing import Dict, List, Optional, Any, Union

# Configure logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Try importing optional dependencies
try:
    import cryptography
    from cryptography.fernet import Fernet
    HAS_CRYPTOGRAPHY = True
except ImportError:
    logger.warning("Cryptography library not available. Install with: pip install cryptography")
    HAS_CRYPTOGRAPHY = False

class SecurityFeature(str, Enum):
    """Supported security features."""
    ENCRYPTION = "encryption"
    KEY_MANAGEMENT = "key_management"
    AUDIT_LOGGING = "audit_logging"
    ACCESS_CONTROL = "access_control"
    VAULT = "vault"
    COMPLIANCE = "compliance"


class SecurityLevel(str, Enum):
    """Security levels for the MCP server."""
    BASIC = "basic"  # Basic security features
    STANDARD = "standard"  # Standard security features
    ENHANCED = "enhanced"  # Enhanced security features
    ENTERPRISE = "enterprise"  # Full enterprise security features


class SecurityManager:
    """
    Main class for managing security features in the MCP server.
    
    The SecurityManager provides a unified interface for all security-related
    operations, including encryption, key management, audit logging, and
    access control.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the security manager.
        
        Args:
            config: Optional configuration dictionary for security features
        """
        self.config = config or {}
        self.security_level = SecurityLevel(self.config.get("security_level", "standard"))
        self.enabled_features = set(self.config.get("enabled_features", [
            SecurityFeature.ENCRYPTION,
            SecurityFeature.KEY_MANAGEMENT,
            SecurityFeature.AUDIT_LOGGING
        ]))
        
        # Initialize components
        self._encryption_manager = None
        self._key_manager = None
        self._audit_logger = None
        self._access_control = None
        self._vault = None
        self._compliance_manager = None
        
        # Try to initialize enabled components
        self._initialize_components()
        
        logger.info(f"Security Manager initialized with security level: {self.security_level}")
        logger.info(f"Enabled features: {', '.join(f.value for f in self.enabled_features)}")
    
    def _initialize_components(self):
        """Initialize security components based on enabled features."""
        # Initialize encryption manager if enabled
        if SecurityFeature.ENCRYPTION in self.enabled_features:
            try:
                from .encryption import EncryptionManager
                self._encryption_manager = EncryptionManager(self.config.get("encryption", {}))
                logger.info("Encryption Manager initialized")
            except ImportError:
                logger.warning("Failed to import Encryption Manager")
                
        # Initialize key manager if enabled
        if SecurityFeature.KEY_MANAGEMENT in self.enabled_features:
            try:
                from .key_management import KeyManager
                self._key_manager = KeyManager(self.config.get("key_management", {}))
                logger.info("Key Manager initialized")
            except ImportError:
                logger.warning("Failed to import Key Manager")
                
        # Initialize audit logger if enabled
        if SecurityFeature.AUDIT_LOGGING in self.enabled_features:
            try:
                from .audit_logging import AuditLogger
                self._audit_logger = AuditLogger(self.config.get("audit_logging", {}))
                logger.info("Audit Logger initialized")
            except ImportError:
                logger.warning("Failed to import Audit Logger")
                
        # Initialize access control if enabled
        if SecurityFeature.ACCESS_CONTROL in self.enabled_features:
            try:
                from .access_control import AccessControl
                self._access_control = AccessControl(self.config.get("access_control", {}))
                logger.info("Access Control initialized")
            except ImportError:
                logger.warning("Failed to import Access Control")
                
        # Initialize vault if enabled
        if SecurityFeature.VAULT in self.enabled_features:
            try:
                from .vault import Vault
                self._vault = Vault(self.config.get("vault", {}))
                logger.info("Vault initialized")
            except ImportError:
                logger.warning("Failed to import Vault")
                
        # Initialize compliance manager if enabled
        if SecurityFeature.COMPLIANCE in self.enabled_features:
            try:
                from .compliance import ComplianceManager
                self._compliance_manager = ComplianceManager(self.config.get("compliance", {}))
                logger.info("Compliance Manager initialized")
            except ImportError:
                logger.warning("Failed to import Compliance Manager")
    
    @property
    def encryption(self):
        """Get the encryption manager."""
        if self._encryption_manager is None:
            raise NotImplementedError("Encryption is not enabled or could not be initialized")
        return self._encryption_manager
    
    @property
    def key_management(self):
        """Get the key manager."""
        if self._key_manager is None:
            raise NotImplementedError("Key management is not enabled or could not be initialized")
        return self._key_manager
    
    @property
    def audit_logging(self):
        """Get the audit logger."""
        if self._audit_logger is None:
            raise NotImplementedError("Audit logging is not enabled or could not be initialized")
        return self._audit_logger
    
    @property
    def access_control(self):
        """Get the access control."""
        if self._access_control is None:
            raise NotImplementedError("Access control is not enabled or could not be initialized")
        return self._access_control
    
    @property
    def vault(self):
        """Get the vault."""
        if self._vault is None:
            raise NotImplementedError("Vault is not enabled or could not be initialized")
        return self._vault
    
    @property
    def compliance(self):
        """Get the compliance manager."""
        if self._compliance_manager is None:
            raise NotImplementedError("Compliance management is not enabled or could not be initialized")
        return self._compliance_manager
    
    def is_feature_enabled(self, feature: SecurityFeature) -> bool:
        """
        Check if a security feature is enabled.
        
        Args:
            feature: The feature to check
            
        Returns:
            True if the feature is enabled, False otherwise
        """
        return feature in self.enabled_features
    
    def enable_feature(self, feature: SecurityFeature) -> bool:
        """
        Enable a security feature.
        
        Args:
            feature: The feature to enable
            
        Returns:
            True if the feature was enabled successfully, False otherwise
        """
        if feature in self.enabled_features:
            return True
        
        self.enabled_features.add(feature)
        self._initialize_components()
        
        # Check if the feature was successfully enabled
        if feature == SecurityFeature.ENCRYPTION and self._encryption_manager is None:
            self.enabled_features.remove(feature)
            return False
        elif feature == SecurityFeature.KEY_MANAGEMENT and self._key_manager is None:
            self.enabled_features.remove(feature)
            return False
        elif feature == SecurityFeature.AUDIT_LOGGING and self._audit_logger is None:
            self.enabled_features.remove(feature)
            return False
        elif feature == SecurityFeature.ACCESS_CONTROL and self._access_control is None:
            self.enabled_features.remove(feature)
            return False
        elif feature == SecurityFeature.VAULT and self._vault is None:
            self.enabled_features.remove(feature)
            return False
        elif feature == SecurityFeature.COMPLIANCE and self._compliance_manager is None:
            self.enabled_features.remove(feature)
            return False
        
        return True
    
    def disable_feature(self, feature: SecurityFeature) -> bool:
        """
        Disable a security feature.
        
        Args:
            feature: The feature to disable
            
        Returns:
            True if the feature was disabled successfully, False otherwise
        """
        if feature not in self.enabled_features:
            return True
        
        self.enabled_features.remove(feature)
        
        # Clean up the component
        if feature == SecurityFeature.ENCRYPTION:
            self._encryption_manager = None
        elif feature == SecurityFeature.KEY_MANAGEMENT:
            self._key_manager = None
        elif feature == SecurityFeature.AUDIT_LOGGING:
            self._audit_logger = None
        elif feature == SecurityFeature.ACCESS_CONTROL:
            self._access_control = None
        elif feature == SecurityFeature.VAULT:
            self._vault = None
        elif feature == SecurityFeature.COMPLIANCE:
            self._compliance_manager = None
        
        return True
    
    def encrypt_data(self, data: bytes, key_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Encrypt data using the encryption manager.
        
        Args:
            data: Data to encrypt
            key_id: Optional ID of the key to use
            
        Returns:
            Dictionary with the encrypted data and metadata
        """
        if not self.is_feature_enabled(SecurityFeature.ENCRYPTION):
            raise NotImplementedError("Encryption is not enabled")
        
        try:
            result = self.encryption.encrypt(data, key_id)
            
            # Audit the operation if audit logging is enabled
            if self.is_feature_enabled(SecurityFeature.AUDIT_LOGGING):
                self.audit_logging.log_event(
                    event_type="encryption",
                    resource_id=key_id or "default",
                    operation="encrypt",
                    status="success"
                )
            
            return result
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            
            # Audit the failure if audit logging is enabled
            if self.is_feature_enabled(SecurityFeature.AUDIT_LOGGING):
                self.audit_logging.log_event(
                    event_type="encryption",
                    resource_id=key_id or "default",
                    operation="encrypt",
                    status="failure",
                    details=str(e)
                )
            
            raise
    
    def decrypt_data(self, encrypted_data: Dict[str, Any]) -> bytes:
        """
        Decrypt data using the encryption manager.
        
        Args:
            encrypted_data: Dictionary with encrypted data and metadata
            
        Returns:
            Decrypted data
        """
        if not self.is_feature_enabled(SecurityFeature.ENCRYPTION):
            raise NotImplementedError("Encryption is not enabled")
        
        try:
            key_id = encrypted_data.get("key_id", "default")
            result = self.encryption.decrypt(encrypted_data)
            
            # Audit the operation if audit logging is enabled
            if self.is_feature_enabled(SecurityFeature.AUDIT_LOGGING):
                self.audit_logging.log_event(
                    event_type="encryption",
                    resource_id=key_id,
                    operation="decrypt",
                    status="success"
                )
            
            return result
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            
            # Audit the failure if audit logging is enabled
            if self.is_feature_enabled(SecurityFeature.AUDIT_LOGGING):
                self.audit_logging.log_event(
                    event_type="encryption",
                    resource_id=encrypted_data.get("key_id", "default"),
                    operation="decrypt",
                    status="failure",
                    details=str(e)
                )
            
            raise
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get the status of the security manager.
        
        Returns:
            Dictionary with status information
        """
        status = {
            "security_level": self.security_level.value,
            "enabled_features": [f.value for f in self.enabled_features],
            "components": {}
        }
        
        # Add component status
        if self._encryption_manager:
            status["components"]["encryption"] = {
                "enabled": True,
                "status": "healthy"
            }
        else:
            status["components"]["encryption"] = {
                "enabled": SecurityFeature.ENCRYPTION in self.enabled_features,
                "status": "not_initialized"
            }
        
        if self._key_manager:
            status["components"]["key_management"] = {
                "enabled": True,
                "status": "healthy"
            }
        else:
            status["components"]["key_management"] = {
                "enabled": SecurityFeature.KEY_MANAGEMENT in self.enabled_features,
                "status": "not_initialized"
            }
        
        if self._audit_logger:
            status["components"]["audit_logging"] = {
                "enabled": True,
                "status": "healthy"
            }
        else:
            status["components"]["audit_logging"] = {
                "enabled": SecurityFeature.AUDIT_LOGGING in self.enabled_features,
                "status": "not_initialized"
            }
        
        if self._access_control:
            status["components"]["access_control"] = {
                "enabled": True,
                "status": "healthy"
            }
        else:
            status["components"]["access_control"] = {
                "enabled": SecurityFeature.ACCESS_CONTROL in self.enabled_features,
                "status": "not_initialized"
            }
        
        if self._vault:
            status["components"]["vault"] = {
                "enabled": True,
                "status": "healthy"
            }
        else:
            status["components"]["vault"] = {
                "enabled": SecurityFeature.VAULT in self.enabled_features,
                "status": "not_initialized"
            }
        
        if self._compliance_manager:
            status["components"]["compliance"] = {
                "enabled": True,
                "status": "healthy"
            }
        else:
            status["components"]["compliance"] = {
                "enabled": SecurityFeature.COMPLIANCE in self.enabled_features,
                "status": "not_initialized"
            }
        
        return status


# Singleton instance
_security_manager_instance = None

def get_security_manager(config: Dict[str, Any] = None) -> SecurityManager:
    """
    Get the singleton instance of the security manager.
    
    Args:
        config: Optional configuration for the security manager
        
    Returns:
        The security manager instance
    """
    global _security_manager_instance
    if _security_manager_instance is None:
        _security_manager_instance = SecurityManager(config)
    return _security_manager_instance