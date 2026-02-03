#!/usr/bin/env python3
"""
Enhanced Secrets Management with Rotation and Validation

Production-grade encryption using AES-256-GCM with proper key derivation,
salt, and authenticated encryption.

Provides improved security for credential management through:
- AES-256-GCM authenticated encryption (production-ready)
- Automatic secret rotation
- Secret validation before use
- Audit logging for credential access
- Secret expiration tracking
- Backward compatibility with legacy XOR encryption
"""

import os
import json
import time
import logging
import hashlib
import base64
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum

# Import AES encryption
try:
    from .aes_encryption import (
        create_encryption_handler,
        MultiVersionEncryption,
        CRYPTOGRAPHY_AVAILABLE,
    )
    AES_ENCRYPTION_AVAILABLE = CRYPTOGRAPHY_AVAILABLE
except ImportError:
    AES_ENCRYPTION_AVAILABLE = False
    logger.warning("AES encryption not available, falling back to XOR (not recommended for production)")

logger = logging.getLogger(__name__)


class SecretType(Enum):
    """Types of secrets."""
    API_KEY = "api_key"
    PASSWORD = "password"
    TOKEN = "token"
    CERTIFICATE = "certificate"
    PRIVATE_KEY = "private_key"
    CONNECTION_STRING = "connection_string"


@dataclass
class SecretMetadata:
    """Metadata for a secret."""
    secret_id: str
    service: str
    secret_type: SecretType
    created_at: float
    last_rotated: float
    last_accessed: float
    access_count: int
    expires_at: Optional[float] = None
    rotation_interval: Optional[int] = None  # seconds
    is_encrypted: bool = True


class SecretAuditLog:
    """Audit log for secret access."""
    
    def __init__(self, log_path: str):
        """
        Initialize audit log.
        
        Args:
            log_path: Path to audit log file
        """
        self.log_path = Path(log_path).expanduser()
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
    
    def log_access(
        self, 
        secret_id: str, 
        service: str, 
        action: str,
        success: bool,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Log secret access event.
        
        Args:
            secret_id: ID of the secret
            service: Service name
            action: Action performed (read, write, rotate, delete)
            success: Whether the action succeeded
            metadata: Additional metadata
        """
        log_entry = {
            'timestamp': time.time(),
            'datetime': datetime.now().isoformat(),
            'secret_id': secret_id,
            'service': service,
            'action': action,
            'success': success,
            'metadata': metadata or {}
        }
        
        try:
            with open(self.log_path, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
    
    def get_recent_accesses(
        self, 
        secret_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get recent audit log entries.
        
        Args:
            secret_id: Optional secret ID to filter by
            limit: Maximum number of entries to return
            
        Returns:
            List of audit log entries
        """
        entries = []
        
        try:
            if not self.log_path.exists():
                return entries
            
            with open(self.log_path, 'r') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        
                        if secret_id is None or entry.get('secret_id') == secret_id:
                            entries.append(entry)
                            
                            if len(entries) >= limit:
                                break
                    except json.JSONDecodeError:
                        continue
            
        except Exception as e:
            logger.error(f"Failed to read audit log: {e}")
        
        return entries[-limit:]


class SecretValidator:
    """Validates secrets before use."""
    
    @staticmethod
    def validate_api_key(key: str) -> bool:
        """Validate API key format."""
        if not key or len(key) < 10:
            return False
        
        # Check for common patterns
        if key.startswith('AKIA') and len(key) == 20:
            # AWS access key
            return True
        
        # Generic validation
        return len(key) >= 10 and len(key) <= 256
    
    @staticmethod
    def validate_token(token: str) -> bool:
        """Validate token format."""
        if not token or len(token) < 20:
            return False
        
        return len(token) >= 20 and len(token) <= 2048
    
    @staticmethod
    def validate_connection_string(conn_str: str) -> bool:
        """Validate connection string format."""
        if not conn_str:
            return False
        
        # Check for common connection string patterns
        patterns = ['://', '=', '@']
        return any(pattern in conn_str for pattern in patterns)
    
    @classmethod
    def validate(cls, secret_type: SecretType, value: str) -> bool:
        """
        Validate a secret based on its type.
        
        Args:
            secret_type: Type of secret
            value: Secret value
            
        Returns:
            True if valid, False otherwise
        """
        validators = {
            SecretType.API_KEY: cls.validate_api_key,
            SecretType.TOKEN: cls.validate_token,
            SecretType.CONNECTION_STRING: cls.validate_connection_string,
        }
        
        validator = validators.get(secret_type)
        if validator:
            return validator(value)
        
        # Default validation - just check it's not empty
        return bool(value)


class EnhancedSecretManager:
    """
    Enhanced secret manager with rotation and validation.
    
    Now uses AES-256-GCM encryption by default for production-grade security.
    
    Features:
    - AES-256-GCM authenticated encryption with salt and nonce
    - Automatic secret rotation
    - Secret validation before storage/retrieval
    - Audit logging for all operations
    - Expiration tracking
    - Backward compatibility with legacy XOR encryption
    - Secret lifecycle management
    """
    
    def __init__(
        self,
        storage_path: str = "~/.ipfs_kit/secrets",
        audit_log_path: str = "~/.ipfs_kit/secrets/audit.log",
        encryption_key: Optional[bytes] = None,
        enable_auto_rotation: bool = True,
        default_rotation_interval: int = 86400 * 30,  # 30 days
        encryption_method: str = "aes-gcm",  # "aes-gcm" or "xor" (legacy)
    ):
        """
        Initialize enhanced secret manager.
        
        Args:
            storage_path: Path to secret storage
            audit_log_path: Path to audit log
            encryption_key: Key for encrypting secrets (auto-generated if None)
            enable_auto_rotation: Enable automatic rotation
            default_rotation_interval: Default rotation interval (seconds)
            encryption_method: Encryption method ("aes-gcm" or "xor" for legacy)
        """
        self.storage_path = Path(storage_path).expanduser()
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.secrets_file = self.storage_path / "secrets.enc.json"
        self.metadata_file = self.storage_path / "metadata.json"
        
        self.encryption_key = encryption_key or self._generate_encryption_key()
        self.enable_auto_rotation = enable_auto_rotation
        self.default_rotation_interval = default_rotation_interval
        self.encryption_method = encryption_method
        
        # Initialize encryption handler
        if encryption_method == "aes-gcm" and AES_ENCRYPTION_AVAILABLE:
            self.encryptor = create_encryption_handler(
                master_key=self.encryption_key,
                encryption_method="aes-gcm"
            )
            logger.info("Using AES-256-GCM encryption (production-ready)")
        else:
            if encryption_method == "aes-gcm":
                logger.warning(
                    "AES encryption requested but cryptography library not available. "
                    "Falling back to XOR encryption (NOT RECOMMENDED FOR PRODUCTION)"
                )
            self.encryptor = None  # Will use legacy XOR methods
            logger.warning("Using legacy XOR encryption (NOT RECOMMENDED FOR PRODUCTION)")
        
        # Initialize audit log
        self.audit_log = SecretAuditLog(audit_log_path)
        
        # Initialize validator
        self.validator = SecretValidator()
        
        # Load secrets and metadata
        self.secrets: Dict[str, str] = {}
        self.metadata: Dict[str, SecretMetadata] = {}
        self._load_secrets()
        
        logger.info(
            f"Initialized enhanced secret manager at {storage_path} "
            f"(encryption={encryption_method}, auto_rotation={enable_auto_rotation})"
        )
    
    def _generate_encryption_key(self) -> bytes:
        """Generate encryption key from machine ID."""
        try:
            # Try to get machine ID
            if os.path.exists('/etc/machine-id'):
                with open('/etc/machine-id', 'r') as f:
                    machine_id = f.read().strip()
            else:
                # Fallback to hostname
                import socket
                machine_id = socket.gethostname()
            
            # Derive key from machine ID
            return hashlib.sha256(machine_id.encode()).digest()
            
        except Exception as e:
            logger.warning(f"Failed to generate encryption key: {e}")
            # Fallback to default key (not secure, but better than nothing)
            return hashlib.sha256(b"ipfs_kit_default_key").digest()
    
    def _encrypt(self, data: str) -> str:
        """
        Encrypt data using configured encryption method.
        
        By default uses AES-256-GCM for production-grade security.
        Falls back to legacy XOR if AES is not available (not recommended).
        
        Returns:
            Encrypted string with version prefix for AES, or base64 for legacy XOR
        """
        if self.encryptor:
            # Use AES-256-GCM (production-ready)
            return self.encryptor.encrypt(data)
        else:
            # Fall back to legacy XOR (not recommended)
            return self._encrypt_xor(data)
    
    def _decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt data using appropriate method based on format.
        
        Automatically detects encryption version:
        - v2: AES-256-GCM
        - v1 (no prefix): Legacy XOR
        
        Returns:
            Decrypted plaintext
        """
        if self.encryptor:
            # Use multi-version handler (supports both AES and legacy XOR)
            try:
                return self.encryptor.decrypt(encrypted_data)
            except Exception as e:
                logger.error(f"Failed to decrypt with multi-version handler: {e}")
                # Try XOR as fallback
                try:
                    return self._decrypt_xor(encrypted_data)
                except Exception as e2:
                    logger.error(f"Failed to decrypt with XOR fallback: {e2}")
                    raise Exception(f"Decryption failed with both methods")
        else:
            # Fall back to legacy XOR only
            return self._decrypt_xor(encrypted_data)
    
    def _encrypt_xor(self, data: str) -> str:
        """
        Legacy XOR encryption (backward compatibility only).
        
        WARNING: This is NOT secure. Only use for backward compatibility
        or non-production environments.
        
        Note: Adds v1 version prefix for compatibility with MultiVersionEncryption
        """
        data_bytes = data.encode()
        key_bytes = self.encryption_key
        
        encrypted = bytearray()
        for i, byte in enumerate(data_bytes):
            encrypted.append(byte ^ key_bytes[i % len(key_bytes)])
        
        # Return without version prefix for true legacy compatibility
        return base64.b64encode(bytes(encrypted)).decode()
    
    def _decrypt_xor(self, encrypted_data: str) -> str:
        """
        Legacy XOR decryption (backward compatibility only).
        
        WARNING: This is NOT secure. Only use for backward compatibility
        or non-production environments.
        """
        encrypted_bytes = base64.b64decode(encrypted_data.encode())
        key_bytes = self.encryption_key
        
        decrypted = bytearray()
        for i, byte in enumerate(encrypted_bytes):
            decrypted.append(byte ^ key_bytes[i % len(key_bytes)])
        
        return bytes(decrypted).decode()
    
    def _load_secrets(self):
        """Load secrets from storage."""
        try:
            # Load metadata
            if self.metadata_file.exists():
                with open(self.metadata_file, 'r') as f:
                    metadata_data = json.load(f)
                    
                    for secret_id, meta in metadata_data.items():
                        self.metadata[secret_id] = SecretMetadata(
                            secret_id=meta['secret_id'],
                            service=meta['service'],
                            secret_type=SecretType(meta['secret_type']),
                            created_at=meta['created_at'],
                            last_rotated=meta['last_rotated'],
                            last_accessed=meta['last_accessed'],
                            access_count=meta['access_count'],
                            expires_at=meta.get('expires_at'),
                            rotation_interval=meta.get('rotation_interval'),
                            is_encrypted=meta.get('is_encrypted', True),
                        )
            
            # Load secrets (stored encrypted)
            if self.secrets_file.exists():
                with open(self.secrets_file, 'r') as f:
                    encrypted_secrets = json.load(f)
                    
                    for secret_id, encrypted_value in encrypted_secrets.items():
                        # Store encrypted - will decrypt on retrieval
                        self.secrets[secret_id] = encrypted_value
            
            logger.info(f"Loaded {len(self.secrets)} secrets")
            
        except Exception as e:
            logger.error(f"Failed to load secrets: {e}")
    
    def _save_secrets(self):
        """Save secrets to storage."""
        try:
            # Save metadata
            metadata_data = {
                secret_id: asdict(meta)
                for secret_id, meta in self.metadata.items()
            }
            
            # Convert enum to string for JSON serialization
            for meta in metadata_data.values():
                meta['secret_type'] = meta['secret_type'].value
            
            with open(self.metadata_file, 'w') as f:
                json.dump(metadata_data, f, indent=2)
            
            # Save secrets (already encrypted)
            with open(self.secrets_file, 'w') as f:
                json.dump(self.secrets, f, indent=2)
            
            # Ensure secure permissions
            os.chmod(self.secrets_file, 0o600)
            os.chmod(self.metadata_file, 0o600)
            
            logger.debug("Saved secrets to storage")
            
        except Exception as e:
            logger.error(f"Failed to save secrets: {e}")
            raise
    
    def store_secret(
        self,
        service: str,
        secret_value: str,
        secret_type: SecretType = SecretType.API_KEY,
        expires_in: Optional[int] = None,
        rotation_interval: Optional[int] = None,
    ) -> str:
        """
        Store a secret with metadata.
        
        Args:
            service: Service name
            secret_value: Secret value to store
            secret_type: Type of secret
            expires_in: Expiration time in seconds (optional)
            rotation_interval: Rotation interval in seconds (optional)
            
        Returns:
            Secret ID
        """
        # Validate secret
        if not self.validator.validate(secret_type, secret_value):
            raise ValueError(f"Invalid secret format for type {secret_type}")
        
        # Generate secret ID
        secret_id = hashlib.sha256(
            f"{service}_{secret_type.value}_{time.time()}".encode()
        ).hexdigest()[:16]
        
        # Create metadata
        now = time.time()
        metadata = SecretMetadata(
            secret_id=secret_id,
            service=service,
            secret_type=secret_type,
            created_at=now,
            last_rotated=now,
            last_accessed=now,
            access_count=0,
            expires_at=now + expires_in if expires_in else None,
            rotation_interval=rotation_interval or self.default_rotation_interval,
        )
        
        # Store encrypted secret and metadata
        encrypted_value = self._encrypt(secret_value)
        self.secrets[secret_id] = encrypted_value
        self.metadata[secret_id] = metadata
        
        # Save to storage
        self._save_secrets()
        
        # Audit log
        self.audit_log.log_access(
            secret_id, service, 'store', True,
            {'secret_type': secret_type.value}
        )
        
        logger.info(f"Stored secret for service '{service}' (id={secret_id})")
        
        return secret_id
    
    def retrieve_secret(self, secret_id: str) -> Optional[str]:
        """
        Retrieve a secret by ID.
        
        Args:
            secret_id: Secret ID
            
        Returns:
            Secret value or None if not found/expired
        """
        if secret_id not in self.secrets:
            self.audit_log.log_access(secret_id, 'unknown', 'retrieve', False)
            return None
        
        metadata = self.metadata[secret_id]
        
        # Check expiration
        if metadata.expires_at and time.time() > metadata.expires_at:
            logger.warning(f"Secret {secret_id} has expired")
            self.audit_log.log_access(
                secret_id, metadata.service, 'retrieve', False,
                {'reason': 'expired'}
            )
            return None
        
        # Check for rotation
        if self.enable_auto_rotation and self._needs_rotation(metadata):
            logger.info(f"Secret {secret_id} needs rotation")
            # Note: Actual rotation would need a callback to get new secret
        
        # Update access metadata
        metadata.last_accessed = time.time()
        metadata.access_count += 1
        self._save_secrets()
        
        # Audit log
        self.audit_log.log_access(
            secret_id, metadata.service, 'retrieve', True
        )
        
        # Decrypt and return
        encrypted_value = self.secrets[secret_id]
        try:
            return self._decrypt(encrypted_value)
        except Exception as e:
            logger.error(f"Failed to decrypt secret {secret_id}: {e}")
            self.audit_log.log_access(
                secret_id, metadata.service, 'retrieve', False,
                {'reason': 'decryption_failed', 'error': str(e)}
            )
            return None
    
    def rotate_secret(
        self, 
        secret_id: str, 
        new_value: str,
        on_rotate: Optional[Callable[[str, str], None]] = None
    ) -> bool:
        """
        Rotate a secret.
        
        Args:
            secret_id: Secret ID to rotate
            new_value: New secret value
            on_rotate: Optional callback after rotation
            
        Returns:
            True if successful
        """
        if secret_id not in self.secrets:
            return False
        
        metadata = self.metadata[secret_id]
        
        # Validate new secret
        if not self.validator.validate(metadata.secret_type, new_value):
            logger.error(f"Invalid format for rotated secret {secret_id}")
            return False
        
        # Decrypt old value for callback
        old_encrypted = self.secrets[secret_id]
        try:
            old_value = self._decrypt(old_encrypted)
        except Exception as e:
            logger.error(f"Failed to decrypt old secret during rotation: {e}")
            old_value = None
        
        # Encrypt and update secret
        new_encrypted = self._encrypt(new_value)
        self.secrets[secret_id] = new_encrypted
        metadata.last_rotated = time.time()
        
        # Save changes
        self._save_secrets()
        
        # Call rotation callback if provided
        if on_rotate and old_value:
            try:
                on_rotate(old_value, new_value)
            except Exception as e:
                logger.error(f"Error in rotation callback: {e}")
        
        # Audit log
        self.audit_log.log_access(
            secret_id, metadata.service, 'rotate', True
        )
        
        logger.info(f"Rotated secret {secret_id}")
        
        return True
    
    def _needs_rotation(self, metadata: SecretMetadata) -> bool:
        """Check if a secret needs rotation."""
        if not metadata.rotation_interval:
            return False
        
        age = time.time() - metadata.last_rotated
        return age >= metadata.rotation_interval
    
    def get_expiring_secrets(self, within_days: int = 7) -> List[str]:
        """
        Get secrets expiring within specified days.
        
        Args:
            within_days: Number of days to look ahead
            
        Returns:
            List of secret IDs
        """
        threshold = time.time() + (within_days * 86400)
        
        expiring = []
        for secret_id, metadata in self.metadata.items():
            if metadata.expires_at and metadata.expires_at <= threshold:
                expiring.append(secret_id)
        
        return expiring
    
    def delete_secret(self, secret_id: str) -> bool:
        """
        Delete a secret.
        
        Args:
            secret_id: Secret ID to delete
            
        Returns:
            True if successful
        """
        if secret_id not in self.secrets:
            return False
        
        metadata = self.metadata[secret_id]
        
        # Remove secret and metadata
        del self.secrets[secret_id]
        del self.metadata[secret_id]
        
        # Save changes
        self._save_secrets()
        
        # Audit log
        self.audit_log.log_access(
            secret_id, metadata.service, 'delete', True
        )
        
        logger.info(f"Deleted secret {secret_id}")
        
        return True
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get secret manager statistics."""
        total_secrets = len(self.secrets)
        expired = sum(
            1 for m in self.metadata.values()
            if m.expires_at and time.time() > m.expires_at
        )
        needs_rotation = sum(
            1 for m in self.metadata.values()
            if self._needs_rotation(m)
        )
        
        # Count secrets by encryption version
        encryption_versions = {}
        if self.encryptor:
            for encrypted_value in self.secrets.values():
                try:
                    version = self.encryptor.get_version(encrypted_value)
                    encryption_versions[version] = encryption_versions.get(version, 0) + 1
                except Exception:
                    # If detection fails, assume legacy format
                    encryption_versions['v1'] = encryption_versions.get('v1', 0) + 1
        else:
            # No encryptor - all are legacy XOR
            encryption_versions['v1'] = len(self.secrets)
        
        return {
            'total_secrets': total_secrets,
            'expired_secrets': expired,
            'secrets_needing_rotation': needs_rotation,
            'services': len(set(m.service for m in self.metadata.values())),
            'total_accesses': sum(m.access_count for m in self.metadata.values()),
            'encryption_method': self.encryption_method,
            'encryption_versions': encryption_versions,
            'aes_available': AES_ENCRYPTION_AVAILABLE,
        }
    
    def migrate_all_secrets(self) -> Dict[str, Any]:
        """
        Migrate all secrets to latest encryption version (AES-256-GCM).
        
        This re-encrypts all secrets that are using legacy encryption
        (XOR) to the new AES-256-GCM format.
        
        Returns:
            Dictionary with migration statistics
        """
        if not self.encryptor:
            raise RuntimeError("AES encryption not available for migration")
        
        migrated_count = 0
        already_current = 0
        errors = []
        
        for secret_id, encrypted_value in list(self.secrets.items()):
            try:
                # Check if migration is needed
                if self.encryptor.needs_migration(encrypted_value):
                    # Migrate to latest version
                    new_encrypted = self.encryptor.migrate(encrypted_value)
                    self.secrets[secret_id] = new_encrypted
                    migrated_count += 1
                    logger.info(f"Migrated secret {secret_id} to AES-256-GCM")
                else:
                    already_current += 1
            except Exception as e:
                error_msg = f"Failed to migrate secret {secret_id}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        # Save migrated secrets
        if migrated_count > 0:
            self._save_secrets()
            logger.info(f"Successfully migrated {migrated_count} secrets")
        
        return {
            'migrated': migrated_count,
            'already_current': already_current,
            'errors': errors,
            'total_secrets': len(self.secrets),
        }
    
    def get_encryption_info(self, secret_id: str) -> Optional[Dict[str, Any]]:
        """
        Get encryption information for a specific secret.
        
        Args:
            secret_id: Secret ID
            
        Returns:
            Dictionary with encryption info, or None if secret not found
        """
        if secret_id not in self.secrets:
            return None
        
        encrypted_value = self.secrets[secret_id]
        
        info = {
            'secret_id': secret_id,
            'encryption_method': self.encryption_method,
        }
        
        if self.encryptor:
            version = self.encryptor.get_version(encrypted_value)
            needs_migration = self.encryptor.needs_migration(encrypted_value)
            
            info.update({
                'encryption_version': version,
                'needs_migration': needs_migration,
                'is_aes_encrypted': version == 'v2',
            })
        
        return info
