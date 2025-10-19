#!/usr/bin/env python3
"""
Secure Configuration Storage Module

Provides encrypted storage for sensitive configuration data (credentials, API keys, etc.)
using Fernet symmetric encryption from the cryptography library.

Features:
- Automatic encryption/decryption of sensitive fields
- Secure key management in ~/.ipfs_kit/.keyring/
- Backward compatibility with plain JSON
- Key rotation support
- Automatic migration from plain to encrypted format
- File permissions management (0o600)

Usage:
    from ipfs_kit_py.secure_config import SecureConfigManager
    
    manager = SecureConfigManager()
    
    # Save encrypted config
    config = {
        "backends": {
            "s3_main": {
                "config": {
                    "access_key": "AKIA...",
                    "secret_key": "secret123"
                }
            }
        }
    }
    manager.save_config("backends.json", config)
    
    # Load and decrypt config
    loaded_config = manager.load_config("backends.json")
"""

import os
import json
import base64
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Set
from datetime import datetime, timedelta

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.backends import default_backend
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False
    Fernet = None
    PBKDF2HMAC = None

logger = logging.getLogger(__name__)


class SecureConfigManager:
    """
    Manager for secure configuration storage with encryption.
    
    Automatically encrypts sensitive fields in configuration files and manages
    encryption keys securely.
    """
    
    # Fields that should always be encrypted
    SENSITIVE_FIELDS = {
        'password', 'secret', 'key', 'token', 'credential', 
        'access_key', 'secret_key', 'api_key', 'private_key',
        'client_secret', 'auth_token', 'bearer_token'
    }
    
    # File encryption marker
    ENCRYPTED_MARKER = "__encrypted__"
    ENCRYPTION_VERSION = "v1"
    
    def __init__(
        self, 
        data_dir: Optional[Path] = None,
        enable_encryption: bool = True,
        master_password: Optional[str] = None
    ):
        """
        Initialize secure config manager.
        
        Args:
            data_dir: Directory for config storage (default: ~/.ipfs_kit)
            enable_encryption: Whether to enable encryption (default: True)
            master_password: Optional master password for key derivation
        """
        self.data_dir = Path(data_dir or Path.home() / ".ipfs_kit").expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.keyring_dir = self.data_dir / ".keyring"
        self.keyring_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        
        self.enable_encryption = enable_encryption and CRYPTOGRAPHY_AVAILABLE
        self.master_password = master_password
        
        if self.enable_encryption:
            self._cipher = self._get_or_create_cipher()
        else:
            self._cipher = None
            if enable_encryption and not CRYPTOGRAPHY_AVAILABLE:
                logger.warning(
                    "Encryption requested but 'cryptography' library not available. "
                    "Install with: pip install cryptography"
                )
    
    def _get_or_create_cipher(self) -> Optional[Any]:
        """Get or create encryption cipher."""
        if not CRYPTOGRAPHY_AVAILABLE:
            return None
        
        key_file = self.keyring_dir / "master.key"
        
        if key_file.exists():
            # Load existing key
            try:
                with open(key_file, 'rb') as f:
                    key = f.read()
                return Fernet(key)
            except Exception as e:
                logger.error(f"Failed to load encryption key: {e}")
                raise
        else:
            # Generate new key
            if self.master_password:
                # Derive key from password
                key = self._derive_key_from_password(self.master_password)
            else:
                # Generate random key
                key = Fernet.generate_key()
            
            # Save key securely
            with open(key_file, 'wb') as f:
                f.write(key)
            os.chmod(key_file, 0o600)
            
            logger.info(f"Created new encryption key at {key_file}")
            return Fernet(key)
    
    def _derive_key_from_password(self, password: str, salt: Optional[bytes] = None) -> bytes:
        """Derive encryption key from password using PBKDF2."""
        if salt is None:
            salt_file = self.keyring_dir / "salt"
            if salt_file.exists():
                with open(salt_file, 'rb') as f:
                    salt = f.read()
            else:
                salt = os.urandom(16)
                with open(salt_file, 'wb') as f:
                    f.write(salt)
                os.chmod(salt_file, 0o600)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
    
    def _is_sensitive_field(self, field_name: str) -> bool:
        """Check if a field name indicates sensitive data."""
        field_lower = field_name.lower()
        return any(sensitive in field_lower for sensitive in self.SENSITIVE_FIELDS)
    
    def _encrypt_value(self, value: str) -> str:
        """Encrypt a string value."""
        if not self._cipher:
            return value
        
        try:
            encrypted = self._cipher.encrypt(value.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise
    
    def _decrypt_value(self, encrypted_value: str) -> str:
        """Decrypt an encrypted string value."""
        if not self._cipher:
            return encrypted_value
        
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_value.encode())
            decrypted = self._cipher.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            # Return original value if decryption fails (might be plain text)
            return encrypted_value
    
    def _encrypt_dict(self, data: Dict[str, Any], parent_key: str = "") -> Dict[str, Any]:
        """
        Recursively encrypt sensitive fields in a dictionary.
        
        Args:
            data: Dictionary to encrypt
            parent_key: Parent key path for nested dicts
            
        Returns:
            Dictionary with sensitive fields encrypted
        """
        if not self._cipher:
            return data
        
        result = {}
        for key, value in data.items():
            full_key = f"{parent_key}.{key}" if parent_key else key
            
            if isinstance(value, dict):
                # Recursively encrypt nested dicts
                result[key] = self._encrypt_dict(value, full_key)
            elif isinstance(value, str) and self._is_sensitive_field(key):
                # Encrypt sensitive string fields
                result[key] = {
                    self.ENCRYPTED_MARKER: True,
                    "version": self.ENCRYPTION_VERSION,
                    "value": self._encrypt_value(value)
                }
            elif isinstance(value, list):
                # Handle lists
                result[key] = [
                    self._encrypt_dict(item, full_key) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                # Keep non-sensitive values as-is
                result[key] = value
        
        return result
    
    def _decrypt_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively decrypt encrypted fields in a dictionary.
        
        Args:
            data: Dictionary with potentially encrypted fields
            
        Returns:
            Dictionary with all fields decrypted
        """
        if not self._cipher:
            return data
        
        result = {}
        for key, value in data.items():
            if isinstance(value, dict):
                if self.ENCRYPTED_MARKER in value and value.get(self.ENCRYPTED_MARKER):
                    # Decrypt encrypted field
                    result[key] = self._decrypt_value(value.get("value", ""))
                else:
                    # Recursively decrypt nested dicts
                    result[key] = self._decrypt_dict(value)
            elif isinstance(value, list):
                # Handle lists
                result[key] = [
                    self._decrypt_dict(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                result[key] = value
        
        return result
    
    def save_config(
        self, 
        filename: str, 
        data: Dict[str, Any],
        encrypt: bool = True
    ) -> bool:
        """
        Save configuration to file with optional encryption.
        
        Args:
            filename: Config filename (e.g., "backends.json")
            data: Configuration data to save
            encrypt: Whether to encrypt sensitive fields (default: True)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            config_file = self.data_dir / filename
            
            # Encrypt sensitive fields if enabled
            if encrypt and self.enable_encryption:
                data_to_save = self._encrypt_dict(data)
            else:
                data_to_save = data
            
            # Write to file
            with open(config_file, 'w') as f:
                json.dump(data_to_save, f, indent=2)
            
            # Set secure permissions
            os.chmod(config_file, 0o600)
            
            logger.info(f"Saved {'encrypted ' if encrypt and self.enable_encryption else ''}config to {config_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save config {filename}: {e}")
            return False
    
    def load_config(self, filename: str, decrypt: bool = True) -> Optional[Dict[str, Any]]:
        """
        Load configuration from file with automatic decryption.
        
        Args:
            filename: Config filename (e.g., "backends.json")
            decrypt: Whether to decrypt encrypted fields (default: True)
            
        Returns:
            Configuration data or None if file doesn't exist
        """
        try:
            config_file = self.data_dir / filename
            
            if not config_file.exists():
                logger.debug(f"Config file {filename} does not exist")
                return None
            
            # Read file
            with open(config_file, 'r') as f:
                data = json.load(f)
            
            # Decrypt if needed
            if decrypt and self.enable_encryption:
                data = self._decrypt_dict(data)
            
            return data
            
        except Exception as e:
            logger.error(f"Failed to load config {filename}: {e}")
            return None
    
    def migrate_to_encrypted(self, filename: str) -> bool:
        """
        Migrate a plain JSON config file to encrypted format.
        
        Args:
            filename: Config filename to migrate
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enable_encryption:
            logger.warning("Encryption not enabled, cannot migrate")
            return False
        
        try:
            # Load plain config
            data = self.load_config(filename, decrypt=False)
            if data is None:
                logger.warning(f"Config file {filename} does not exist")
                return False
            
            # Create backup
            backup_file = self.data_dir / f"{filename}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            config_file = self.data_dir / filename
            
            import shutil
            shutil.copy2(config_file, backup_file)
            logger.info(f"Created backup at {backup_file}")
            
            # Save encrypted version
            success = self.save_config(filename, data, encrypt=True)
            
            if success:
                logger.info(f"Successfully migrated {filename} to encrypted format")
            return success
            
        except Exception as e:
            logger.error(f"Migration failed for {filename}: {e}")
            return False
    
    def rotate_key(self) -> bool:
        """
        Rotate encryption key and re-encrypt all config files.
        
        Returns:
            True if successful, False otherwise
        """
        if not self.enable_encryption:
            logger.warning("Encryption not enabled, cannot rotate key")
            return False
        
        try:
            # Load all config files with old key
            configs = {}
            for config_file in self.data_dir.glob("*.json"):
                if config_file.name.startswith('.'):
                    continue
                data = self.load_config(config_file.name, decrypt=True)
                if data:
                    configs[config_file.name] = data
            
            # Backup old key
            old_key_file = self.keyring_dir / "master.key"
            backup_key_file = self.keyring_dir / f"master.key.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            import shutil
            shutil.copy2(old_key_file, backup_key_file)
            logger.info(f"Backed up old key to {backup_key_file}")
            
            # Generate new key
            new_key = Fernet.generate_key()
            with open(old_key_file, 'wb') as f:
                f.write(new_key)
            os.chmod(old_key_file, 0o600)
            
            # Update cipher with new key
            self._cipher = Fernet(new_key)
            
            # Re-encrypt all configs with new key
            for filename, data in configs.items():
                self.save_config(filename, data, encrypt=True)
            
            logger.info(f"Successfully rotated encryption key and re-encrypted {len(configs)} config files")
            return True
            
        except Exception as e:
            logger.error(f"Key rotation failed: {e}")
            return False
    
    def get_encryption_status(self) -> Dict[str, Any]:
        """
        Get status of encryption configuration.
        
        Returns:
            Dictionary with encryption status information
        """
        key_file = self.keyring_dir / "master.key"
        
        return {
            "encryption_enabled": self.enable_encryption,
            "cryptography_available": CRYPTOGRAPHY_AVAILABLE,
            "key_exists": key_file.exists(),
            "key_file": str(key_file) if key_file.exists() else None,
            "data_dir": str(self.data_dir),
            "keyring_dir": str(self.keyring_dir)
        }


# Convenience functions for backward compatibility
def save_secure_config(
    filename: str, 
    data: Dict[str, Any],
    data_dir: Optional[Path] = None,
    encrypt: bool = True
) -> bool:
    """Save configuration with encryption (convenience function)."""
    manager = SecureConfigManager(data_dir=data_dir)
    return manager.save_config(filename, data, encrypt=encrypt)


def load_secure_config(
    filename: str,
    data_dir: Optional[Path] = None,
    decrypt: bool = True
) -> Optional[Dict[str, Any]]:
    """Load configuration with decryption (convenience function)."""
    manager = SecureConfigManager(data_dir=data_dir)
    return manager.load_config(filename, decrypt=decrypt)
