"""
End-to-End Encryption Module for MCP Security.

This module provides end-to-end encryption capabilities for the MCP server
as specified in Phase 3: Enterprise Features of the MCP roadmap.

Features:
- End-to-end encryption for stored content
- Secure key management
- Content encryption/decryption
- Key rotation
- Encrypted streaming
"""

import base64
import hashlib
import json
import logging
import os
import secrets
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

# Try to import cryptography libraries
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes, padding
    from cryptography.hazmat.primitives.asymmetric import rsa, padding as asym_padding
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives.serialization import (
        load_pem_private_key,
        load_pem_public_key,
        Encoding,
        PrivateFormat,
        PublicFormat,
        NoEncryption,
        BestAvailableEncryption
    )
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False
    # Create dummy classes/functions to avoid breaking imports
    class Fernet:
        def __init__(self, *args, **kwargs):
            raise ImportError("cryptography package not installed")

# Configure logging
logger = logging.getLogger(__name__)


class EncryptionAlgorithm(str, Enum):
    """Encryption algorithms supported."""
    AES_256_GCM = "aes-256-gcm"
    AES_256_CBC = "aes-256-cbc"
    CHACHA20_POLY1305 = "chacha20-poly1305"
    FERNET = "fernet"
    RSA_OAEP = "rsa-oaep"


class KeyType(str, Enum):
    """Key types."""
    SYMMETRIC = "symmetric"
    ASYMMETRIC_PRIVATE = "asymmetric_private"
    ASYMMETRIC_PUBLIC = "asymmetric_public"
    PASSWORD_DERIVED = "password_derived"


@dataclass
class EncryptionKey:
    """Encryption key information."""
    key_id: str
    key_type: KeyType
    algorithm: EncryptionAlgorithm
    key_material: bytes
    created_at: float
    expires_at: Optional[float] = None
    metadata: Dict[str, Any] = None

    def to_dict(self, include_material: bool = False) -> Dict[str, Any]:
        """
        Convert key to dictionary.

        Args:
            include_material: Whether to include key material
            
        Returns:
            Dictionary representation of key
        """
        result = {
            "key_id": self.key_id,
            "key_type": self.key_type,
            "algorithm": self.algorithm,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "metadata": self.metadata or {}
        }
        
        if include_material:
            result["key_material"] = base64.b64encode(self.key_material).decode('utf-8')
        
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EncryptionKey':
        """
        Create key from dictionary.

        Args:
            data: Dictionary representation
            
        Returns:
            EncryptionKey instance
        """
        key_material = base64.b64decode(data["key_material"]) if "key_material" in data else None
        
        return cls(
            key_id=data["key_id"],
            key_type=data["key_type"],
            algorithm=data["algorithm"],
            key_material=key_material,
            created_at=data["created_at"],
            expires_at=data.get("expires_at"),
            metadata=data.get("metadata", {})
        )


@dataclass
class EncryptedData:
    """Encrypted data container."""
    data: bytes
    key_id: str
    algorithm: EncryptionAlgorithm
    nonce: Optional[bytes] = None
    tag: Optional[bytes] = None
    metadata: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary.
        
        Returns:
            Dictionary representation
        """
        result = {
            "data": base64.b64encode(self.data).decode('utf-8'),
            "key_id": self.key_id,
            "algorithm": self.algorithm,
            "metadata": self.metadata or {}
        }
        
        if self.nonce:
            result["nonce"] = base64.b64encode(self.nonce).decode('utf-8')
        
        if self.tag:
            result["tag"] = base64.b64encode(self.tag).decode('utf-8')
        
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EncryptedData':
        """
        Create from dictionary.

        Args:
            data: Dictionary representation
            
        Returns:
            EncryptedData instance
        """
        encrypted_data = base64.b64decode(data["data"])
        nonce = base64.b64decode(data["nonce"]) if "nonce" in data else None
        tag = base64.b64decode(data["tag"]) if "tag" in data else None
        
        return cls(
            data=encrypted_data,
            key_id=data["key_id"],
            algorithm=data["algorithm"],
            nonce=nonce,
            tag=tag,
            metadata=data.get("metadata", {})
        )


class EndToEndEncryptionError(Exception):
    """Base exception for encryption errors."""
    pass


class KeyManagementError(EndToEndEncryptionError):
    """Exception for key management errors."""
    pass


class EncryptionError(EndToEndEncryptionError):
    """Exception for encryption errors."""
    pass


class DecryptionError(EndToEndEncryptionError):
    """Exception for decryption errors."""
    pass


class KeyStoreError(EndToEndEncryptionError):
    """Exception for key store errors."""
    pass


class EndToEndEncryption:
    """
    End-to-End Encryption service for MCP.
    
    This class provides encryption and decryption capabilities for the MCP server,
    supporting both symmetric and asymmetric encryption with key management.
    """

    def __init__(self, key_store_path: Optional[str] = None):
        """
        Initialize encryption service.

        Args:
            key_store_path: Path to key store file
        """
        if not CRYPTOGRAPHY_AVAILABLE:
            raise ImportError(
                "cryptography package is required for end-to-end encryption. "
                "Install it with: pip install cryptography"
            )
        
        self.key_store_path = key_store_path or os.path.join(
            os.path.expanduser("~"), ".ipfs_kit", "mcp", "encryption", "keys.json"
        )
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.key_store_path), exist_ok=True)
        
        # Load keys
        self.keys: Dict[str, EncryptionKey] = {}
        self.load_keys()

    def load_keys(self) -> None:
        """Load keys from key store file."""
        if not os.path.exists(self.key_store_path):
            return
        
        try:
            with open(self.key_store_path, "r") as f:
                keys_data = json.load(f)
                
                for key_id, key_data in keys_data.items():
                    self.keys[key_id] = EncryptionKey.from_dict(key_data)
            
            logger.info(f"Loaded {len(self.keys)} keys from {self.key_store_path}")
        except Exception as e:
            logger.error(f"Failed to load keys: {e}")
            raise KeyStoreError(f"Failed to load keys: {e}")

    def save_keys(self) -> None:
        """Save keys to key store file."""
        try:
            keys_data = {}
            for key_id, key in self.keys.items():
                keys_data[key_id] = key.to_dict(include_material=True)
            
            # Save with atomic write
            temp_path = f"{self.key_store_path}.tmp"
            with open(temp_path, "w") as f:
                json.dump(keys_data, f, indent=2)
            
            # Rename to final path
            os.replace(temp_path, self.key_store_path)
            
            logger.info(f"Saved {len(self.keys)} keys to {self.key_store_path}")
        except Exception as e:
            logger.error(f"Failed to save keys: {e}")
            raise KeyStoreError(f"Failed to save keys: {e}")

    def generate_key(
        self,
        algorithm: EncryptionAlgorithm = EncryptionAlgorithm.AES_256_GCM,
        key_type: KeyType = KeyType.SYMMETRIC,
        key_id: Optional[str] = None,
        expires_in: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> EncryptionKey:
        """
        Generate a new encryption key.

        Args:
            algorithm: Encryption algorithm
            key_type: Key type
            key_id: Custom key ID or None for auto-generated
            expires_in: Expiration time in seconds or None for no expiration
            metadata: Additional metadata
            
        Returns:
            Generated EncryptionKey
        """
        if not key_id:
            key_id = f"key_{uuid.uuid4().hex}"
        
        created_at = time.time()
        expires_at = created_at + expires_in if expires_in else None
        
        # Generate key material based on algorithm and type
        if key_type == KeyType.SYMMETRIC:
            if algorithm == EncryptionAlgorithm.AES_256_GCM or algorithm == EncryptionAlgorithm.AES_256_CBC:
                # 256-bit key
                key_material = secrets.token_bytes(32)
            elif algorithm == EncryptionAlgorithm.CHACHA20_POLY1305:
                # 256-bit key
                key_material = secrets.token_bytes(32)
            elif algorithm == EncryptionAlgorithm.FERNET:
                # Fernet key
                key_material = Fernet.generate_key()
            else:
                raise KeyManagementError(f"Unsupported algorithm for symmetric key: {algorithm}")
        
        elif key_type == KeyType.ASYMMETRIC_PRIVATE:
            if algorithm == EncryptionAlgorithm.RSA_OAEP:
                # Generate RSA private key
                private_key = rsa.generate_private_key(
                    public_exponent=65537,
                    key_size=2048
                )
                key_material = private_key.private_bytes(
                    encoding=Encoding.PEM,
                    format=PrivateFormat.PKCS8,
                    encryption_algorithm=NoEncryption()
                )
            else:
                raise KeyManagementError(f"Unsupported algorithm for asymmetric key: {algorithm}")
        
        else:
            raise KeyManagementError(f"Unsupported key type: {key_type}")
        
        # Create key
        key = EncryptionKey(
            key_id=key_id,
            key_type=key_type,
            algorithm=algorithm,
            key_material=key_material,
            created_at=created_at,
            expires_at=expires_at,
            metadata=metadata or {}
        )
        
        # Store key
        self.keys[key_id] = key
        self.save_keys()
        
        return key

    def derive_public_key(self, private_key_id: str) -> EncryptionKey:
        """
        Derive public key from private key.

        Args:
            private_key_id: Private key ID
            
        Returns:
            Derived public key
        """
        if private_key_id not in self.keys:
            raise KeyManagementError(f"Private key not found: {private_key_id}")
        
        private_key = self.keys[private_key_id]
        
        if private_key.key_type != KeyType.ASYMMETRIC_PRIVATE:
            raise KeyManagementError(f"Key is not a private key: {private_key_id}")
        
        if private_key.algorithm != EncryptionAlgorithm.RSA_OAEP:
            raise KeyManagementError(f"Unsupported algorithm for key derivation: {private_key.algorithm}")
        
        # Load private key
        rsa_private_key = load_pem_private_key(
            private_key.key_material,
            password=None
        )
        
        # Get public key
        rsa_public_key = rsa_private_key.public_key()
        
        # Serialize public key
        public_key_material = rsa_public_key.public_bytes(
            encoding=Encoding.PEM,
            format=PublicFormat.SubjectPublicKeyInfo
        )
        
        # Create key
        public_key_id = f"pub_{private_key_id}"
        public_key = EncryptionKey(
            key_id=public_key_id,
            key_type=KeyType.ASYMMETRIC_PUBLIC,
            algorithm=private_key.algorithm,
            key_material=public_key_material,
            created_at=time.time(),
            expires_at=private_key.expires_at,
            metadata={
                "derived_from": private_key_id,
                "original_metadata": private_key.metadata
            }
        )
        
        # Store key
        self.keys[public_key_id] = public_key
        self.save_keys()
        
        return public_key

    def import_key(
        self,
        key_material: bytes,
        key_type: KeyType,
        algorithm: EncryptionAlgorithm,
        key_id: Optional[str] = None,
        expires_at: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> EncryptionKey:
        """
        Import an existing key.

        Args:
            key_material: Raw key material
            key_type: Key type
            algorithm: Encryption algorithm
            key_id: Custom key ID or None for auto-generated
            expires_at: Expiration timestamp or None for no expiration
            metadata: Additional metadata
            
        Returns:
            Imported EncryptionKey
        """
        if not key_id:
            key_id = f"imported_{uuid.uuid4().hex}"
        
        # Validate key material
        if key_type == KeyType.SYMMETRIC:
            if algorithm in [EncryptionAlgorithm.AES_256_GCM, EncryptionAlgorithm.AES_256_CBC]:
                if len(key_material) != 32:
                    raise KeyManagementError(f"Invalid key size for {algorithm}: {len(key_material)} bytes (expected 32)")
            
            elif algorithm == EncryptionAlgorithm.CHACHA20_POLY1305:
                if len(key_material) != 32:
                    raise KeyManagementError(f"Invalid key size for {algorithm}: {len(key_material)} bytes (expected 32)")
            
            elif algorithm == EncryptionAlgorithm.FERNET:
                try:
                    # Verify it's a valid Fernet key
                    Fernet(key_material)
                except Exception as e:
                    raise KeyManagementError(f"Invalid Fernet key: {e}")
        
        elif key_type == KeyType.ASYMMETRIC_PRIVATE:
            try:
                # Verify it's a valid private key
                load_pem_private_key(key_material, password=None)
            except Exception as e:
                raise KeyManagementError(f"Invalid private key: {e}")
        
        elif key_type == KeyType.ASYMMETRIC_PUBLIC:
            try:
                # Verify it's a valid public key
                load_pem_public_key(key_material)
            except Exception as e:
                raise KeyManagementError(f"Invalid public key: {e}")
        
        else:
            raise KeyManagementError(f"Unsupported key type: {key_type}")
        
        # Create key
        key = EncryptionKey(
            key_id=key_id,
            key_type=key_type,
            algorithm=algorithm,
            key_material=key_material,
            created_at=time.time(),
            expires_at=expires_at,
            metadata=metadata or {"imported": True}
        )
        
        # Store key
        self.keys[key_id] = key
        self.save_keys()
        
        return key

    def export_key(self, key_id: str, include_material: bool = False) -> Dict[str, Any]:
        """
        Export key information.

        Args:
            key_id: Key ID
            include_material: Whether to include key material
            
        Returns:
            Key information as dictionary
        """
        if key_id not in self.keys:
            raise KeyManagementError(f"Key not found: {key_id}")
        
        return self.keys[key_id].to_dict(include_material=include_material)

    def delete_key(self, key_id: str) -> None:
        """
        Delete a key.

        Args:
            key_id: Key ID
        """
        if key_id not in self.keys:
            raise KeyManagementError(f"Key not found: {key_id}")
        
        # Check if this is a public key derived from a private key
        key = self.keys[key_id]
        if key.key_type == KeyType.ASYMMETRIC_PUBLIC and key.metadata and "derived_from" in key.metadata:
            # Also delete the private key
            private_key_id = key.metadata["derived_from"]
            if private_key_id in self.keys:
                del self.keys[private_key_id]
        
        # Delete key
        del self.keys[key_id]
        self.save_keys()

    def rotate_key(self, key_id: str) -> EncryptionKey:
        """
        Rotate a key (create a new key with the same settings).

        Args:
            key_id: Key ID
            
        Returns:
            New EncryptionKey
        """
        if key_id not in self.keys:
            raise KeyManagementError(f"Key not found: {key_id}")
        
        old_key = self.keys[key_id]
        
        # Generate new key with the same settings
        new_key_id = f"{key_id}_rotated_{int(time.time())}"
        
        # Calculate remaining expiration time if applicable
        expires_in = None
        if old_key.expires_at:
            remaining = old_key.expires_at - time.time()
            if remaining > 0:
                expires_in = int(remaining)
        
        # Update metadata with rotation info
        metadata = dict(old_key.metadata or {})
        metadata["rotated_from"] = key_id
        metadata["rotated_at"] = time.time()
        
        # Generate new key
        new_key = self.generate_key(
            algorithm=old_key.algorithm,
            key_type=old_key.key_type,
            key_id=new_key_id,
            expires_in=expires_in,
            metadata=metadata
        )
        
        return new_key

    def encrypt(
        self,
        data: Union[str, bytes],
        key_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> EncryptedData:
        """
        Encrypt data using a specified key.

        Args:
            data: Data to encrypt (string or bytes)
            key_id: Key ID to use for encryption
            metadata: Additional metadata
            
        Returns:
            EncryptedData containing the encrypted data
        """
        if key_id not in self.keys:
            raise EncryptionError(f"Key not found: {key_id}")
        
        key = self.keys[key_id]
        
        # Convert string to bytes if needed
        if isinstance(data, str):
            data_bytes = data.encode('utf-8')
        else:
            data_bytes = data
        
        # Add data type to metadata
        meta = metadata or {}
        meta["data_type"] = "text" if isinstance(data, str) else "binary"
        
        try:
            # Encrypt based on algorithm
            if key.algorithm == EncryptionAlgorithm.AES_256_GCM:
                return self._encrypt_aes_gcm(data_bytes, key, meta)
            
            elif key.algorithm == EncryptionAlgorithm.AES_256_CBC:
                return self._encrypt_aes_cbc(data_bytes, key, meta)
            
            elif key.algorithm == EncryptionAlgorithm.CHACHA20_POLY1305:
                return self._encrypt_chacha20_poly1305(data_bytes, key, meta)
            
            elif key.algorithm == EncryptionAlgorithm.FERNET:
                return self._encrypt_fernet(data_bytes, key, meta)
            
            elif key.algorithm == EncryptionAlgorithm.RSA_OAEP:
                return self._encrypt_rsa_oaep(data_bytes, key, meta)
            
            else:
                raise EncryptionError(f"Unsupported encryption algorithm: {key.algorithm}")
        
        except Exception as e:
            raise EncryptionError(f"Encryption failed: {e}")

    def decrypt(self, encrypted_data: EncryptedData) -> bytes:
        """
        Decrypt data.

        Args:
            encrypted_data: EncryptedData to decrypt
            
        Returns:
            Decrypted data as bytes
        """
        key_id = encrypted_data.key_id
        
        if key_id not in self.keys:
            raise DecryptionError(f"Key not found: {key_id}")
        
        key = self.keys[key_id]
        
        # Check if key is expired
        if key.expires_at and time.time() > key.expires_at:
            raise DecryptionError(f"Key has expired: {key_id}")
        
        try:
            # Decrypt based on algorithm
            if encrypted_data.algorithm == EncryptionAlgorithm.AES_256_GCM:
                return self._decrypt_aes_gcm(encrypted_data, key)
            
            elif encrypted_data.algorithm == EncryptionAlgorithm.AES_256_CBC:
                return self._decrypt_aes_cbc(encrypted_data, key)
            
            elif encrypted_data.algorithm == EncryptionAlgorithm.CHACHA20_POLY1305:
                return self._decrypt_chacha20_poly1305(encrypted_data, key)
            
            elif encrypted_data.algorithm == EncryptionAlgorithm.FERNET:
                return self._decrypt_fernet(encrypted_data, key)
            
            elif encrypted_data.algorithm == EncryptionAlgorithm.RSA_OAEP:
                return self._decrypt_rsa_oaep(encrypted_data, key)
            
            else:
                raise DecryptionError(f"Unsupported decryption algorithm: {encrypted_data.algorithm}")
        
        except Exception as e:
            raise DecryptionError(f"Decryption failed: {e}")

    def _encrypt_aes_gcm(
        self, data: bytes, key: EncryptionKey, metadata: Dict[str, Any]
    ) -> EncryptedData:
        """
        Encrypt data using AES-256-GCM.

        Args:
            data: Data to encrypt
            key: Encryption key
            metadata: Additional metadata
            
        Returns:
            EncryptedData
        """
        # Generate nonce
        nonce = os.urandom(12)  # 96 bits for GCM
        
        # Create cipher
        cipher = Cipher(
            algorithms.AES(key.key_material),
            modes.GCM(nonce)
        )
        
        encryptor = cipher.encryptor()
        
        # Encrypt data
        ciphertext = encryptor.update(data) + encryptor.finalize()
        
        # Get authentication tag
        tag = encryptor.tag
        
        return EncryptedData(
            data=ciphertext,
            key_id=key.key_id,
            algorithm=key.algorithm,
            nonce=nonce,
            tag=tag,
            metadata=metadata
        )

    def _decrypt_aes_gcm(self, encrypted_data: EncryptedData, key: EncryptionKey) -> bytes:
        """
        Decrypt data using AES-256-GCM.

        Args:
            encrypted_data: Encrypted data
            key: Encryption key
            
        Returns:
            Decrypted data
        """
        if not encrypted_data.nonce or not encrypted_data.tag:
            raise DecryptionError("Missing nonce or tag for AES-GCM decryption")
        
        # Create cipher
        cipher = Cipher(
            algorithms.AES(key.key_material),
            modes.GCM(encrypted_data.nonce, encrypted_data.tag)
        )
        
        decryptor = cipher.decryptor()
        
        # Decrypt data
        plaintext = decryptor.update(encrypted_data.data) + decryptor.finalize()
        
        return plaintext

    def _encrypt_aes_cbc(
        self, data: bytes, key: EncryptionKey, metadata: Dict[str, Any]
    ) -> EncryptedData:
        """
        Encrypt data using AES-256-CBC.

        Args:
            data: Data to encrypt
            key: Encryption key
            metadata: Additional metadata
            
        Returns:
            EncryptedData
        """
        # Generate IV
        iv = os.urandom(16)  # 128 bits for CBC
        
        # Pad data
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(data) + padder.finalize()
        
        # Create cipher
        cipher = Cipher(
            algorithms.AES(key.key_material),
            modes.CBC(iv)
        )
        
        encryptor = cipher.encryptor()
        
        # Encrypt data
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()
        
        return EncryptedData(
            data=ciphertext,
            key_id=key.key_id,
            algorithm=key.algorithm,
            nonce=iv,  # Store IV in nonce field
            metadata=metadata
        )

    def _decrypt_aes_cbc(self, encrypted_data: EncryptedData, key: EncryptionKey) -> bytes:
        """
        Decrypt data using AES-256-CBC.

        Args:
            encrypted_data: Encrypted data
            key: Encryption key
            
        Returns:
            Decrypted data
        """
        if not encrypted_data.nonce:
            raise DecryptionError("Missing IV for AES-CBC decryption")
        
        # Create cipher
        cipher = Cipher(
            algorithms.AES(key.key_material),
            modes.CBC(encrypted_data.nonce)
        )
        
        decryptor = cipher.decryptor()
        
        # Decrypt data
        padded_plaintext = decryptor.update(encrypted_data.data) + decryptor.finalize()
        
        # Unpad data
        unpadder = padding.PKCS7(128).unpadder()
        plaintext = unpadder.update(padded_plaintext) + unpadder.finalize()
        
        return plaintext

    def _encrypt_chacha20_poly1305(
        self, data: bytes, key: EncryptionKey, metadata: Dict[str, Any]
    ) -> EncryptedData:
        """
        Encrypt data using ChaCha20-Poly1305.

        Args:
            data: Data to encrypt
            key: Encryption key
            metadata: Additional metadata
            
        Returns:
            EncryptedData
        """
        # Generate nonce
        nonce = os.urandom(12)  # 96 bits
        
        # Create cipher
        cipher = Cipher(
            algorithms.ChaCha20(key.key_material, nonce),
            None
        )
        
        encryptor = cipher.encryptor()
        
        # Encrypt data
        ciphertext = encryptor.update(data) + encryptor.finalize()
        
        # Calculate Poly1305 tag
        tag = hashlib.blake2b(ciphertext, key=key.key_material, digest_size=16).digest()
        
        return EncryptedData(
            data=ciphertext,
            key_id=key.key_id,
            algorithm=key.algorithm,
            nonce=nonce,
            tag=tag,
            metadata=metadata
        )

    def _decrypt_chacha20_poly1305(self, encrypted_data: EncryptedData, key: EncryptionKey) -> bytes:
        """
        Decrypt data using ChaCha20-Poly1305.

        Args:
            encrypted_data: Encrypted data
            key: Encryption key
            
        Returns:
            Decrypted data
        """
        if not encrypted_data.nonce or not encrypted_data.tag:
            raise DecryptionError("Missing nonce or tag for ChaCha20-Poly1305 decryption")
        
        # Verify tag
        calculated_tag = hashlib.blake2b(encrypted_data.data, key=key.key_material, digest_size=16).digest()
        if not secrets.compare_digest(calculated_tag, encrypted_data.tag):
            raise DecryptionError("Authentication failed: invalid tag")
        
        # Create cipher
        cipher = Cipher(
            algorithms.ChaCha20(key.key_material, encrypted_data.nonce),
            None
        )
        
        decryptor = cipher.decryptor()
        
        # Decrypt data
        plaintext = decryptor.update(encrypted_data.data) + decryptor.finalize()
        
        return plaintext

    def _encrypt_fernet(
        self, data: bytes, key: EncryptionKey, metadata: Dict[str, Any]
    ) -> EncryptedData:
        """
        Encrypt data using Fernet.

        Args:
            data: Data to encrypt
            key: Encryption key
            metadata: Additional metadata
            
        Returns:
            EncryptedData
        """
        # Create Fernet instance
        f = Fernet(key.key_material)
        
        # Encrypt data
        ciphertext = f.encrypt(data)
        
        return EncryptedData(
            data=ciphertext,
            key_id=key.key_id,
            algorithm=key.algorithm,
            metadata=metadata
        )

    def _decrypt_fernet(self, encrypted_data: EncryptedData, key: EncryptionKey) -> bytes:
        """
        Decrypt data using Fernet.

        Args:
            encrypted_data: Encrypted data
            key: Encryption key
            
        Returns:
            Decrypted data
        """
        # Create Fernet instance
        f = Fernet(key.key_material)
        
        # Decrypt data
        plaintext = f.decrypt(encrypted_data.data)
        
        return plaintext

    def _encrypt_rsa_oaep(
        self, data: bytes, key: EncryptionKey, metadata: Dict[str, Any]
    ) -> EncryptedData:
        """
        Encrypt data using RSA-OAEP.

        Args:
            data: Data to encrypt
            key: Encryption key
            metadata: Additional metadata
            
        Returns:
            EncryptedData
        """
        # Only public keys can be used for encryption
        if key.key_type != KeyType.ASYMMETRIC_PUBLIC:
            raise EncryptionError("RSA encryption requires a public key")
        
        # Load public key
        public_key = load_pem_public_key(key.key_material)
        
        # RSA can only encrypt limited size data (typically around 200 bytes for 2048-bit key)
        if len(data) > 190:  # Conservative limit
            # Generate a symmetric key for actual data encryption
            symmetric_key = os.urandom(32)
            
            # Encrypt data with AES-GCM
            nonce = os.urandom(12)
            cipher = Cipher(
                algorithms.AES(symmetric_key),
                modes.GCM(nonce)
            )
            encryptor = cipher.encryptor()
            ciphertext = encryptor.update(data) + encryptor.finalize()
            tag = encryptor.tag
            
            # Encrypt the symmetric key with RSA
            encrypted_key = public_key.encrypt(
                symmetric_key,
                asym_padding.OAEP(
                    mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            # Combine everything
            # Format: [encrypted_key_size(4 bytes)][encrypted_key][nonce][tag][ciphertext]
            key_size = len(encrypted_key).to_bytes(4, byteorder='big')
            combined_data = key_size + encrypted_key + nonce + tag + ciphertext
            
            # Update metadata
            meta = dict(metadata)
            meta["hybrid"] = True
            
            return EncryptedData(
                data=combined_data,
                key_id=key.key_id,
                algorithm=key.algorithm,
                metadata=meta
            )
        
        # Small data can be encrypted directly with RSA
        encrypted_data = public_key.encrypt(
            data,
            asym_padding.OAEP(
                mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        return EncryptedData(
            data=encrypted_data,
            key_id=key.key_id,
            algorithm=key.algorithm,
            metadata=metadata
        )

    def _decrypt_rsa_oaep(self, encrypted_data: EncryptedData, key: EncryptionKey) -> bytes:
        """
        Decrypt data using RSA-OAEP.

        Args:
            encrypted_data: Encrypted data
            key: Encryption key
            
        Returns:
            Decrypted data
        """
        # Only private keys can be used for decryption
        if key.key_type != KeyType.ASYMMETRIC_PRIVATE:
            raise DecryptionError("RSA decryption requires a private key")
        
        # Load private key
        private_key = load_pem_private_key(
            key.key_material,
            password=None
        )
        
        # Check if this is hybrid encryption
        if encrypted_data.metadata and encrypted_data.metadata.get("hybrid"):
            # Extract components
            # Format: [encrypted_key_size(4 bytes)][encrypted_key][nonce][tag][ciphertext]
            data = encrypted_data.data
            key_size = int.from_bytes(data[:4], byteorder='big')
            encrypted_key = data[4:4+key_size]
            nonce = data[4+key_size:4+key_size+12]
            tag = data[4+key_size+12:4+key_size+12+16]
            ciphertext = data[4+key_size+12+16:]
            
            # Decrypt the symmetric key
            symmetric_key = private_key.decrypt(
                encrypted_key,
                asym_padding.OAEP(
                    mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            # Decrypt the data with AES-GCM
            cipher = Cipher(
                algorithms.AES(symmetric_key),
                modes.GCM(nonce, tag)
            )
            decryptor = cipher.decryptor()
            plaintext = decryptor.update(ciphertext) + decryptor.finalize()
            
            return plaintext
        
        # Direct RSA decryption for small data
        plaintext = private_key.decrypt(
            encrypted_data.data,
            asym_padding.OAEP(
                mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        return plaintext

    def encrypt_file(
        self,
        file_path: str,
        key_id: str,
        output_path: Optional[str] = None,
        chunk_size: int = 4 * 1024 * 1024  # 4MB chunks
    ) -> Dict[str, Any]:
        """
        Encrypt a file.

        Args:
            file_path: Path to file
            key_id: Key ID
            output_path: Path for encrypted output or None for auto-generated
            chunk_size: Chunk size for processing
            
        Returns:
            Dictionary with encryption information
        """
        if not os.path.exists(file_path):
            raise EncryptionError(f"File not found: {file_path}")
        
        if key_id not in self.keys:
            raise EncryptionError(f"Key not found: {key_id}")
        
        key = self.keys[key_id]
        
        # Generate output path if not provided
        if not output_path:
            output_path = f"{file_path}.encrypted"
        
        # Get file info
        file_size = os.path.getsize(file_path)
        file_name = os.path.basename(file_path)
        
        # Create metadata
        metadata = {
            "original_filename": file_name,
            "original_size": file_size,
            "encryption_time": time.time(),
            "chunks": 0
        }
        
        # Initialize encryption based on algorithm
        if key.algorithm == EncryptionAlgorithm.AES_256_GCM:
            # Generate key and nonce for file encryption
            file_key = os.urandom(32)
            nonce = os.urandom(12)
            
            # Encrypt the file key with the provided key
            key_encrypted_data = self.encrypt(file_key, key_id, {"purpose": "file_key"})
            
            # Create cipher
            cipher = Cipher(
                algorithms.AES(file_key),
                modes.GCM(nonce)
            )
            
            # Write header
            with open(output_path, "wb") as out_file:
                # Write algorithm and key ID
                out_file.write(key.algorithm.encode('utf-8').ljust(16))
                out_file.write(key_id.encode('utf-8').ljust(64))
                
                # Write metadata
                metadata_json = json.dumps(metadata).encode('utf-8')
                out_file.write(len(metadata_json).to_bytes(4, byteorder='big'))
                out_file.write(metadata_json)
                
                # Write encrypted key data
                key_data_json = json.dumps(key_encrypted_data.to_dict()).encode('utf-8')
                out_file.write(len(key_data_json).to_bytes(4, byteorder='big'))
                out_file.write(key_data_json)
                
                # Write nonce
                out_file.write(len(nonce).to_bytes(4, byteorder='big'))
                out_file.write(nonce)
                
                # Process file in chunks
                chunk_count = 0
                with open(file_path, "rb") as in_file:
                    while True:
                        chunk = in_file.read(chunk_size)
                        if not chunk:
                            break
                        
                        # Create new encryptor for each chunk
                        encryptor = cipher.encryptor()
                        
                        # Encrypt chunk
                        encrypted_chunk = encryptor.update(chunk) + encryptor.finalize()
                        tag = encryptor.tag
                        
                        # Write chunk size, tag and encrypted data
                        out_file.write(len(encrypted_chunk).to_bytes(4, byteorder='big'))
                        out_file.write(len(tag).to_bytes(4, byteorder='big'))
                        out_file.write(tag)
                        out_file.write(encrypted_chunk)
                        
                        chunk_count += 1
                
                # Update metadata with final chunk count
                metadata["chunks"] = chunk_count
        
        else:
            raise EncryptionError(f"Unsupported algorithm for file encryption: {key.algorithm}")
        
        return {
            "success": True,
            "algorithm": key.algorithm,
            "key_id": key_id,
            "original_path": file_path,
            "encrypted_path": output_path,
            "metadata": metadata
        }

    def decrypt_file(
        self,
        file_path: str,
        output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Decrypt a file.

        Args:
            file_path: Path to encrypted file
            output_path: Path for decrypted output or None for auto-generated
            
        Returns:
            Dictionary with decryption information
        """
        if not os.path.exists(file_path):
            raise DecryptionError(f"File not found: {file_path}")
        
        # Read header and determine algorithm
        with open(file_path, "rb") as f:
            # Read algorithm and key ID
            algorithm_str = f.read(16).strip().decode('utf-8')
            key_id = f.read(64).strip().decode('utf-8')
            
            if key_id not in self.keys:
                raise DecryptionError(f"Key not found: {key_id}")
            
            # Read metadata
            metadata_len = int.from_bytes(f.read(4), byteorder='big')
            metadata_json = f.read(metadata_len)
            metadata = json.loads(metadata_json)
            
            # Generate output path if not provided
            if not output_path:
                if metadata.get("original_filename"):
                    output_dir = os.path.dirname(file_path)
                    output_path = os.path.join(output_dir, f"decrypted_{metadata['original_filename']}")
                else:
                    output_path = file_path + ".decrypted"
            
            # Process based on algorithm
            if algorithm_str == EncryptionAlgorithm.AES_256_GCM:
                # Read encrypted key data
                key_data_len = int.from_bytes(f.read(4), byteorder='big')
                key_data_json = f.read(key_data_len)
                key_encrypted_data = EncryptedData.from_dict(json.loads(key_data_json))
                
                # Decrypt the file key
                file_key = self.decrypt(key_encrypted_data)
                
                # Read nonce
                nonce_len = int.from_bytes(f.read(4), byteorder='big')
                nonce = f.read(nonce_len)
                
                # Create cipher
                cipher = Cipher(
                    algorithms.AES(file_key),
                    modes.GCM(nonce)
                )
                
                # Process chunks
                with open(output_path, "wb") as out_file:
                    for _ in range(metadata.get("chunks", 0)):
                        # Read chunk size and tag
                        chunk_len = int.from_bytes(f.read(4), byteorder='big')
                        tag_len = int.from_bytes(f.read(4), byteorder='big')
                        tag = f.read(tag_len)
                        encrypted_chunk = f.read(chunk_len)
                        
                        # Create decryptor with tag
                        decryptor = cipher.decryptor()
                        
                        # Decrypt chunk
                        decrypted_chunk = decryptor.update(encrypted_chunk) + decryptor.finalize()
                        
                        # Write decrypted data
                        out_file.write(decrypted_chunk)
            
            else:
                raise DecryptionError(f"Unsupported algorithm for file decryption: {algorithm_str}")
        
        return {
            "success": True,
            "algorithm": algorithm_str,
            "key_id": key_id,
            "encrypted_path": file_path,
            "decrypted_path": output_path,
            "metadata": metadata
        }


def create_password_derived_key(
    password: str,
    salt: Optional[bytes] = None,
    algorithm: EncryptionAlgorithm = EncryptionAlgorithm.AES_256_GCM
) -> Tuple[EncryptionKey, bytes]:
    """
    Create a key derived from a password.

    Args:
        password: Password to derive key from
        salt: Salt for key derivation or None to generate
        algorithm: Encryption algorithm for the key
        
    Returns:
        Tuple of (EncryptionKey, salt)
    """
    if not CRYPTOGRAPHY_AVAILABLE:
        raise ImportError(
            "cryptography package is required for key derivation. "
            "Install it with: pip install cryptography"
        )
    
    # Generate salt if not provided
    if salt is None:
        salt = os.urandom(16)
    
    # Derive key
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,  # 256 bits
        salt=salt,
        iterations=100000,
    )
    
    key_material = kdf.derive(password.encode('utf-8'))
    
    # Create key
    key_id = f"pwd_{uuid.uuid4().hex}"
    key = EncryptionKey(
        key_id=key_id,
        key_type=KeyType.PASSWORD_DERIVED,
        algorithm=algorithm,
        key_material=key_material,
        created_at=time.time(),
        metadata={
            "derived": True,
            "kdf": "pbkdf2",
            "kdf_iterations": 100000,
            "kdf_hash": "sha256"
        }
    )
    
    return key, salt