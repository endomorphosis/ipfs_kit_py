#!/usr/bin/env python3
"""
AES-256-GCM Encryption for Secrets Management

Provides production-grade encryption using AES-256-GCM with proper
key derivation, salt, and authenticated encryption.

Features:
- AES-256-GCM authenticated encryption
- PBKDF2 key derivation with salt
- Random nonce per encryption
- Built-in integrity verification
- Version-tagged format for migration
"""

import os
import base64
import hashlib
import logging
from typing import Tuple, Optional
from dataclasses import dataclass

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class EncryptedData:
    """Container for encrypted data with metadata."""
    version: str
    salt: bytes
    nonce: bytes
    ciphertext: bytes
    
    def serialize(self) -> str:
        """
        Serialize to string format.
        
        Format: version:base64(salt):base64(nonce):base64(ciphertext)
        Example: v2:abc123...:def456...:ghi789...
        """
        parts = [
            self.version,
            base64.b64encode(self.salt).decode('utf-8'),
            base64.b64encode(self.nonce).decode('utf-8'),
            base64.b64encode(self.ciphertext).decode('utf-8'),
        ]
        return ':'.join(parts)
    
    @classmethod
    def deserialize(cls, data: str) -> 'EncryptedData':
        """
        Deserialize from string format.
        
        Args:
            data: Serialized encrypted data
            
        Returns:
            EncryptedData instance
            
        Raises:
            ValueError: If format is invalid
        """
        parts = data.split(':')
        if len(parts) != 4:
            raise ValueError(f"Invalid encrypted data format: expected 4 parts, got {len(parts)}")
        
        version, salt_b64, nonce_b64, ciphertext_b64 = parts
        
        try:
            salt = base64.b64decode(salt_b64)
            nonce = base64.b64decode(nonce_b64)
            ciphertext = base64.b64decode(ciphertext_b64)
        except Exception as e:
            raise ValueError(f"Invalid base64 encoding in encrypted data: {e}")
        
        return cls(
            version=version,
            salt=salt,
            nonce=nonce,
            ciphertext=ciphertext,
        )


class AESEncryption:
    """
    AES-256-GCM encryption with proper key derivation.
    
    This class provides production-grade encryption suitable for
    storing sensitive secrets. It uses:
    - AES-256-GCM for authenticated encryption
    - PBKDF2 for key derivation from passphrase
    - Random salt per secret for key derivation
    - Random nonce per encryption operation
    - Built-in integrity verification
    """
    
    VERSION = "v2"
    SALT_SIZE = 16  # 128 bits
    NONCE_SIZE = 12  # 96 bits (recommended for GCM)
    KEY_SIZE = 32  # 256 bits
    PBKDF2_ITERATIONS = 600000  # OWASP recommended minimum for 2023+
    
    def __init__(self, master_key: bytes):
        """
        Initialize AES encryption.
        
        Args:
            master_key: Master key for key derivation (32 bytes recommended)
            
        Raises:
            ImportError: If cryptography library is not available
        """
        if not CRYPTOGRAPHY_AVAILABLE:
            raise ImportError(
                "cryptography library is required for AES encryption. "
                "Install with: pip install cryptography>=38.0.0"
            )
        
        if len(master_key) < 16:
            raise ValueError("Master key must be at least 16 bytes")
        
        self.master_key = master_key
        
        logger.debug(
            f"Initialized AES-256-GCM encryption "
            f"(iterations={self.PBKDF2_ITERATIONS})"
        )
    
    def _derive_key(self, salt: bytes) -> bytes:
        """
        Derive encryption key from master key and salt using PBKDF2.
        
        Args:
            salt: Salt for key derivation
            
        Returns:
            Derived 256-bit key
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.KEY_SIZE,
            salt=salt,
            iterations=self.PBKDF2_ITERATIONS,
        )
        
        return kdf.derive(self.master_key)
    
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt plaintext using AES-256-GCM.
        
        Args:
            plaintext: String to encrypt
            
        Returns:
            Serialized encrypted data with version, salt, nonce, and ciphertext
            
        Example:
            >>> encryptor = AESEncryption(b"my-master-key")
            >>> encrypted = encryptor.encrypt("secret data")
            >>> print(encrypted)
            v2:abc123...:def456...:ghi789...
        """
        # Generate random salt for this secret
        salt = os.urandom(self.SALT_SIZE)
        
        # Derive encryption key from master key and salt
        key = self._derive_key(salt)
        
        # Generate random nonce for this encryption
        nonce = os.urandom(self.NONCE_SIZE)
        
        # Encrypt with AES-256-GCM
        aesgcm = AESGCM(key)
        plaintext_bytes = plaintext.encode('utf-8')
        ciphertext = aesgcm.encrypt(nonce, plaintext_bytes, None)
        
        # Package encrypted data
        encrypted_data = EncryptedData(
            version=self.VERSION,
            salt=salt,
            nonce=nonce,
            ciphertext=ciphertext,
        )
        
        return encrypted_data.serialize()
    
    def decrypt(self, encrypted_str: str) -> str:
        """
        Decrypt ciphertext using AES-256-GCM.
        
        Args:
            encrypted_str: Serialized encrypted data
            
        Returns:
            Decrypted plaintext string
            
        Raises:
            ValueError: If data format is invalid or version is unsupported
            Exception: If decryption fails (wrong key or corrupted data)
            
        Example:
            >>> encryptor = AESEncryption(b"my-master-key")
            >>> encrypted = encryptor.encrypt("secret data")
            >>> decrypted = encryptor.decrypt(encrypted)
            >>> print(decrypted)
            secret data
        """
        # Deserialize encrypted data
        encrypted_data = EncryptedData.deserialize(encrypted_str)
        
        # Check version
        if encrypted_data.version != self.VERSION:
            raise ValueError(
                f"Unsupported encryption version: {encrypted_data.version} "
                f"(expected {self.VERSION})"
            )
        
        # Derive decryption key from master key and salt
        key = self._derive_key(encrypted_data.salt)
        
        # Decrypt with AES-256-GCM
        aesgcm = AESGCM(key)
        try:
            plaintext_bytes = aesgcm.decrypt(
                encrypted_data.nonce,
                encrypted_data.ciphertext,
                None
            )
            return plaintext_bytes.decode('utf-8')
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise Exception("Decryption failed: invalid key or corrupted data")
    
    def is_encrypted(self, data: str) -> bool:
        """
        Check if data is encrypted with this version.
        
        Args:
            data: Data to check
            
        Returns:
            True if data appears to be encrypted with this version
        """
        try:
            encrypted_data = EncryptedData.deserialize(data)
            return encrypted_data.version == self.VERSION
        except (ValueError, Exception):
            return False


class LegacyXORDecryptor:
    """
    Legacy XOR decryption for backward compatibility.
    
    This class provides decryption of legacy XOR-encrypted secrets
    to support migration to AES-256-GCM.
    
    WARNING: This is for backward compatibility only. Do not use for
    new secrets.
    """
    
    VERSION = "v1"
    
    def __init__(self, key: bytes):
        """
        Initialize XOR decryptor.
        
        Args:
            key: XOR key (same as used for encryption)
        """
        self.key = key
    
    def decrypt(self, encrypted_str: str) -> str:
        """
        Decrypt XOR-encrypted data.
        
        Args:
            encrypted_str: Base64-encoded XOR-encrypted data
            
        Returns:
            Decrypted plaintext
        """
        encrypted_bytes = base64.b64decode(encrypted_str.encode())
        key_bytes = self.key
        
        decrypted = bytearray()
        for i, byte in enumerate(encrypted_bytes):
            decrypted.append(byte ^ key_bytes[i % len(key_bytes)])
        
        return bytes(decrypted).decode('utf-8')
    
    def is_encrypted(self, data: str) -> bool:
        """
        Check if data is XOR-encrypted (legacy format).
        
        Args:
            data: Data to check
            
        Returns:
            True if data appears to be XOR-encrypted (no version prefix)
        """
        # Legacy XOR format has no version prefix
        return not data.startswith('v')


class MultiVersionEncryption:
    """
    Multi-version encryption handler supporting both legacy XOR and AES-256-GCM.
    
    This class provides seamless migration from XOR to AES encryption by:
    - Reading both legacy XOR and new AES-encrypted secrets
    - Always encrypting new secrets with AES-256-GCM
    - Supporting one-time migration of all secrets
    """
    
    def __init__(self, master_key: bytes):
        """
        Initialize multi-version encryption handler.
        
        Args:
            master_key: Master key for encryption
        """
        self.master_key = master_key
        self.aes = AESEncryption(master_key)
        self.xor = LegacyXORDecryptor(master_key)
        
        logger.info("Initialized multi-version encryption (AES-256-GCM + legacy XOR)")
    
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt plaintext using AES-256-GCM.
        
        Always uses the latest encryption method (AES-256-GCM).
        
        Args:
            plaintext: String to encrypt
            
        Returns:
            Encrypted string with version prefix
        """
        return self.aes.encrypt(plaintext)
    
    def decrypt(self, encrypted_str: str) -> str:
        """
        Decrypt ciphertext using appropriate method based on version.
        
        Automatically detects encryption version and uses the correct
        decryption method:
        - v2: AES-256-GCM
        - v1 (no prefix): Legacy XOR
        
        Args:
            encrypted_str: Encrypted string
            
        Returns:
            Decrypted plaintext
            
        Raises:
            ValueError: If encryption version is unsupported
        """
        # Check for AES-256-GCM (v2)
        if self.aes.is_encrypted(encrypted_str):
            return self.aes.decrypt(encrypted_str)
        
        # Check for legacy XOR (v1/no version)
        elif self.xor.is_encrypted(encrypted_str):
            logger.debug("Decrypting legacy XOR-encrypted secret")
            return self.xor.decrypt(encrypted_str)
        
        else:
            raise ValueError("Unknown encryption version or corrupted data")
    
    def get_version(self, encrypted_str: str) -> str:
        """
        Get encryption version of encrypted data.
        
        Args:
            encrypted_str: Encrypted string
            
        Returns:
            Version string (e.g., "v2", "v1")
        """
        if self.aes.is_encrypted(encrypted_str):
            return self.aes.VERSION
        elif self.xor.is_encrypted(encrypted_str):
            return self.xor.VERSION
        else:
            return "unknown"
    
    def needs_migration(self, encrypted_str: str) -> bool:
        """
        Check if encrypted data needs migration to latest version.
        
        Args:
            encrypted_str: Encrypted string
            
        Returns:
            True if data is encrypted with an old version
        """
        version = self.get_version(encrypted_str)
        return version != self.aes.VERSION
    
    def migrate(self, encrypted_str: str) -> str:
        """
        Migrate encrypted data to latest encryption version.
        
        This decrypts using the old method and re-encrypts using
        the latest method (AES-256-GCM).
        
        Args:
            encrypted_str: Encrypted string in old format
            
        Returns:
            Encrypted string in new format
        """
        # Decrypt using appropriate method
        plaintext = self.decrypt(encrypted_str)
        
        # Re-encrypt using latest method
        return self.encrypt(plaintext)


def create_encryption_handler(
    master_key: Optional[bytes] = None,
    encryption_method: str = "aes-gcm"
) -> MultiVersionEncryption:
    """
    Factory function to create encryption handler.
    
    Args:
        master_key: Master key for encryption (auto-generated if None)
        encryption_method: Encryption method (currently only "aes-gcm" supported)
        
    Returns:
        Configured encryption handler
    """
    if master_key is None:
        # Generate key from machine ID (same as legacy implementation)
        try:
            if os.path.exists('/etc/machine-id'):
                with open('/etc/machine-id', 'r') as f:
                    machine_id = f.read().strip()
            else:
                import socket
                machine_id = socket.gethostname()
            
            master_key = hashlib.sha256(machine_id.encode()).digest()
        except Exception as e:
            logger.warning(f"Failed to generate encryption key: {e}")
            master_key = hashlib.sha256(b"ipfs_kit_default_key").digest()
    
    if encryption_method != "aes-gcm":
        raise ValueError(f"Unsupported encryption method: {encryption_method}")
    
    return MultiVersionEncryption(master_key)
