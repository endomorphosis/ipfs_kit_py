"""
End-to-End Encryption Module for MCP Server

This module provides comprehensive encryption capabilities for the MCP server,
enabling secure storage and transmission of sensitive data across the network.

Key features:
1. End-to-end encryption of data
2. Secure key management
3. Integration with storage backends
4. Compliance audit logging
5. Zero-knowledge architecture options

Part of the MCP Roadmap Phase 3: Enterprise Features (Q1 2026).
"""

import os
import io
import json
import base64
import hashlib
import logging
import secrets
import threading
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Union, BinaryIO, Tuple, Set, Callable
from datetime import datetime, timedelta
import uuid

# Configure logger
logger = logging.getLogger(__name__)

# Try to import cryptography
try:
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.hazmat.primitives.asymmetric.padding import OAEP, MGF1
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.fernet import Fernet
    HAS_CRYPTOGRAPHY = True
except ImportError:
    logger.warning("Cryptography package not available. Encryption capabilities will be limited.")
    HAS_CRYPTOGRAPHY = False

# Try to import secure storage options
try:
    import keyring
    HAS_KEYRING = True
except ImportError:
    logger.warning("Keyring package not available. Secure key storage capabilities will be limited.")
    HAS_KEYRING = False


class EncryptionAlgorithm(str, Enum):
    """Supported encryption algorithms."""
    AES_256_GCM = "aes-256-gcm"
    AES_256_CBC = "aes-256-cbc"
    CHACHA20_POLY1305 = "chacha20-poly1305"
    RSA_OAEP = "rsa-oaep"
    FERNET = "fernet"


class KeyType(str, Enum):
    """Types of encryption keys."""
    SYMMETRIC = "symmetric"
    ASYMMETRIC_PUBLIC = "asymmetric-public"
    ASYMMETRIC_PRIVATE = "asymmetric-private"
    MASTER = "master"
    DATA = "data"
    SESSION = "session"


class KeyStorageType(str, Enum):
    """Types of key storage."""
    FILE = "file"
    ENVIRONMENT = "environment"
    KEYRING = "keyring"
    HSM = "hsm"
    VAULT = "vault"
    TPM = "tpm"
    MEMORY = "memory"


class EncryptionScope(str, Enum):
    """Scopes for encryption policies."""
    GLOBAL = "global"
    REGION = "region"
    NODE = "node"
    USER = "user"
    SERVICE = "service"
    CONTENT = "content"
    METADATA = "metadata"


@dataclass
class EncryptionKey:
    """Represents an encryption key."""
    id: str
    type: KeyType
    algorithm: EncryptionAlgorithm
    created_at: str
    expires_at: Optional[str] = None
    description: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: Dict[str, str] = field(default_factory=dict)
    # The actual key material is not stored in this object
    # for security reasons. It's referenced by the ID and
    # retrieved from secure storage when needed.
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary without sensitive information."""
        return asdict(self)


@dataclass
class EncryptedData:
    """Represents encrypted data with metadata."""
    id: str
    encryption_key_id: str
    algorithm: EncryptionAlgorithm
    initialization_vector: Optional[bytes] = None
    auth_tag: Optional[bytes] = None
    additional_authenticated_data: Optional[bytes] = None
    encrypted_data: Optional[bytes] = None
    content_type: Optional[str] = None
    original_size: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, encoding binary data as base64."""
        result = asdict(self)
        # Convert binary fields to base64
        if self.initialization_vector:
            result['initialization_vector'] = base64.b64encode(self.initialization_vector).decode('utf-8')
        if self.auth_tag:
            result['auth_tag'] = base64.b64encode(self.auth_tag).decode('utf-8')
        if self.additional_authenticated_data:
            result['additional_authenticated_data'] = base64.b64encode(self.additional_authenticated_data).decode('utf-8')
        if self.encrypted_data:
            result['encrypted_data'] = base64.b64encode(self.encrypted_data).decode('utf-8')
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EncryptedData':
        """Create from dictionary, decoding base64 fields."""
        # Make a copy to avoid modifying the input
        data_copy = data.copy()
        
        # Decode base64 fields
        if 'initialization_vector' in data_copy and data_copy['initialization_vector']:
            data_copy['initialization_vector'] = base64.b64decode(data_copy['initialization_vector'])
        if 'auth_tag' in data_copy and data_copy['auth_tag']:
            data_copy['auth_tag'] = base64.b64decode(data_copy['auth_tag'])
        if 'additional_authenticated_data' in data_copy and data_copy['additional_authenticated_data']:
            data_copy['additional_authenticated_data'] = base64.b64decode(data_copy['additional_authenticated_data'])
        if 'encrypted_data' in data_copy and data_copy['encrypted_data']:
            data_copy['encrypted_data'] = base64.b64decode(data_copy['encrypted_data'])
        
        return cls(**data_copy)


@dataclass
class EncryptionPolicy:
    """Defines an encryption policy for specific data types or scopes."""
    id: str
    name: str
    description: Optional[str] = None
    enabled: bool = True
    algorithm: EncryptionAlgorithm = EncryptionAlgorithm.AES_256_GCM
    scope: EncryptionScope = EncryptionScope.GLOBAL
    scope_ids: List[str] = field(default_factory=list)
    content_types: List[str] = field(default_factory=list)
    key_rotation_days: int = 90
    require_perfect_forward_secrecy: bool = False
    require_signed_encryption: bool = False
    tags: Dict[str, str] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class KeyManager:
    """
    Manages encryption keys securely.
    
    This class is responsible for:
    - Generating encryption keys
    - Securely storing keys
    - Retrieving keys for encryption/decryption
    - Key rotation and revocation
    """
    
    def __init__(self, storage_type: KeyStorageType = KeyStorageType.FILE, 
                storage_path: Optional[str] = None):
        """
        Initialize the key manager.
        
        Args:
            storage_type: Type of key storage to use
            storage_path: Path to key storage (for file-based storage)
        """
        if not HAS_CRYPTOGRAPHY:
            raise RuntimeError("Cryptography package is required for key management")
        
        self.storage_type = storage_type
        self.storage_path = storage_path
        
        # For file-based storage, create directory if it doesn't exist
        if storage_type == KeyStorageType.FILE and storage_path:
            os.makedirs(storage_path, exist_ok=True)
        
        # In-memory key cache (for keys that are currently in use)
        self._key_cache: Dict[str, bytes] = {}
        self._key_metadata: Dict[str, EncryptionKey] = {}
        
        # Thread safety
        self._lock = threading.RLock()
        
        logger.info(f"Initialized key manager with {storage_type} storage")
    
    def generate_key(self, key_type: KeyType, 
                    algorithm: EncryptionAlgorithm,
                    description: Optional[str] = None,
                    expires_days: Optional[int] = None,
                    metadata: Optional[Dict[str, Any]] = None,
                    tags: Optional[Dict[str, str]] = None) -> EncryptionKey:
        """
        Generate a new encryption key.
        
        Args:
            key_type: Type of key to generate
            algorithm: Encryption algorithm for the key
            description: Optional description of the key
            expires_days: Optional number of days until the key expires
            metadata: Optional metadata for the key
            tags: Optional tags for the key
            
        Returns:
            EncryptionKey object representing the generated key
        """
        with self._lock:
            # Generate key ID
            key_id = str(uuid.uuid4())
            
            # Generate key material based on algorithm and type
            if algorithm == EncryptionAlgorithm.RSA_OAEP:
                if key_type not in [KeyType.ASYMMETRIC_PUBLIC, KeyType.ASYMMETRIC_PRIVATE]:
                    raise ValueError(f"RSA keys must be asymmetric, got {key_type}")
                
                # Generate RSA key pair
                private_key = rsa.generate_private_key(
                    public_exponent=65537,
                    key_size=2048
                )
                
                # Serialize keys
                if key_type == KeyType.ASYMMETRIC_PRIVATE:
                    key_material = private_key.private_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PrivateFormat.PKCS8,
                        encryption_algorithm=serialization.NoEncryption()
                    )
                else:  # KeyType.ASYMMETRIC_PUBLIC
                    public_key = private_key.public_key()
                    key_material = public_key.public_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PublicFormat.SubjectPublicKeyInfo
                    )
            
            elif algorithm in [EncryptionAlgorithm.AES_256_GCM, 
                              EncryptionAlgorithm.AES_256_CBC,
                              EncryptionAlgorithm.CHACHA20_POLY1305]:
                if key_type not in [KeyType.SYMMETRIC, KeyType.MASTER, KeyType.DATA]:
                    raise ValueError(f"AES and ChaCha20 keys must be symmetric, got {key_type}")
                
                # Generate symmetric key
                key_material = secrets.token_bytes(32)  # 256 bits
            
            elif algorithm == EncryptionAlgorithm.FERNET:
                if key_type not in [KeyType.SYMMETRIC, KeyType.MASTER, KeyType.DATA]:
                    raise ValueError(f"Fernet keys must be symmetric, got {key_type}")
                
                # Generate Fernet key
                key_material = Fernet.generate_key()
            
            else:
                raise ValueError(f"Unsupported algorithm: {algorithm}")
            
            # Create key metadata
            created_at = datetime.utcnow().isoformat()
            expires_at = None
            if expires_days:
                expires_at = (datetime.utcnow() + timedelta(days=expires_days)).isoformat()
            
            key = EncryptionKey(
                id=key_id,
                type=key_type,
                algorithm=algorithm,
                created_at=created_at,
                expires_at=expires_at,
                description=description,
                metadata=metadata or {},
                tags=tags or {}
            )
            
            # Store the key material securely
            self._store_key_material(key_id, key_material)
            
            # Store key metadata
            self._key_metadata[key_id] = key
            
            logger.info(f"Generated {algorithm} {key_type} key: {key_id}")
            
            return key
    
    def get_key(self, key_id: str) -> bytes:
        """
        Get key material for encryption/decryption.
        
        Args:
            key_id: ID of the key to retrieve
            
        Returns:
            Key material as bytes
        """
        with self._lock:
            # Check if key is in cache
            if key_id in self._key_cache:
                return self._key_cache[key_id]
            
            # Retrieve key from storage
            key_material = self._retrieve_key_material(key_id)
            
            # Add to cache
            self._key_cache[key_id] = key_material
            
            return key_material
    
    def get_key_metadata(self, key_id: str) -> Optional[EncryptionKey]:
        """
        Get metadata for a key.
        
        Args:
            key_id: ID of the key
            
        Returns:
            EncryptionKey object or None if not found
        """
        with self._lock:
            # Check in-memory metadata
            if key_id in self._key_metadata:
                return self._key_metadata[key_id]
            
            # Try to load from storage
            metadata = self._load_key_metadata(key_id)
            if metadata:
                self._key_metadata[key_id] = metadata
                return metadata
            
            return None
    
    def list_keys(self, key_type: Optional[KeyType] = None, 
                 algorithm: Optional[EncryptionAlgorithm] = None,
                 tags: Optional[Dict[str, str]] = None) -> List[EncryptionKey]:
        """
        List encryption keys matching the given criteria.
        
        Args:
            key_type: Optional filter by key type
            algorithm: Optional filter by algorithm
            tags: Optional filter by tags (all tags must match)
            
        Returns:
            List of EncryptionKey objects
        """
        with self._lock:
            # Make sure all metadata is loaded
            self._load_all_key_metadata()
            
            # Filter keys
            result = []
            for key in self._key_metadata.values():
                if key_type and key.type != key_type:
                    continue
                if algorithm and key.algorithm != algorithm:
                    continue
                if tags:
                    # Check if all tags match
                    match = True
                    for tag_key, tag_value in tags.items():
                        if tag_key not in key.tags or key.tags[tag_key] != tag_value:
                            match = False
                            break
                    if not match:
                        continue
                
                result.append(key)
            
            return result
    
    def delete_key(self, key_id: str) -> bool:
        """
        Delete a key.
        
        Args:
            key_id: ID of the key to delete
            
        Returns:
            True if key was deleted, False if not found
        """
        with self._lock:
            # Remove from cache
            self._key_cache.pop(key_id, None)
            
            # Remove from metadata
            key = self._key_metadata.pop(key_id, None)
            if not key:
                return False
            
            # Remove from storage
            self._delete_key_material(key_id)
            
            logger.info(f"Deleted key: {key_id}")
            return True
    
    def rotate_key(self, key_id: str) -> Tuple[EncryptionKey, EncryptionKey]:
        """
        Rotate a key by generating a new key with the same properties.
        
        Args:
            key_id: ID of the key to rotate
            
        Returns:
            Tuple of (old_key, new_key)
        """
        with self._lock:
            # Get existing key metadata
            old_key = self.get_key_metadata(key_id)
            if not old_key:
                raise ValueError(f"Key not found: {key_id}")
            
            # Generate new key with same properties
            new_key = self.generate_key(
                key_type=old_key.type,
                algorithm=old_key.algorithm,
                description=old_key.description,
                expires_days=None if not old_key.expires_at else 
                    (datetime.fromisoformat(old_key.expires_at) - datetime.utcnow()).days,
                metadata=old_key.metadata.copy(),
                tags=old_key.tags.copy()
            )
            
            # Update metadata to indicate rotation
            old_key.metadata["rotated_to"] = new_key.id
            new_key.metadata["rotated_from"] = old_key.id
            
            # Update storage
            self._save_key_metadata(old_key.id, old_key)
            
            logger.info(f"Rotated key {key_id} to {new_key.id}")
            
            return old_key, new_key
    
    def _store_key_material(self, key_id: str, key_material: bytes) -> None:
        """Store key material securely."""
        if self.storage_type == KeyStorageType.FILE:
            if not self.storage_path:
                raise ValueError("Storage path must be provided for file-based storage")
            
            # Write key material to file
            key_path = os.path.join(self.storage_path, f"{key_id}.key")
            with open(key_path, 'wb') as f:
                f.write(key_material)
            
            # Write metadata
            metadata_path = os.path.join(self.storage_path, f"{key_id}.json")
            with open(metadata_path, 'w') as f:
                json.dump(self._key_metadata[key_id].to_dict(), f, indent=2)
                
        elif self.storage_type == KeyStorageType.KEYRING and HAS_KEYRING:
            # Store in system keyring
            keyring.set_password("mcp_encryption", key_id, key_material.hex())
            
            # Store metadata in file if path provided
            if self.storage_path:
                metadata_path = os.path.join(self.storage_path, f"{key_id}.json")
                with open(metadata_path, 'w') as f:
                    json.dump(self._key_metadata[key_id].to_dict(), f, indent=2)
                    
        elif self.storage_type == KeyStorageType.ENVIRONMENT:
            # Store in environment variable
            os.environ[f"MCP_KEY_{key_id}"] = key_material.hex()
            
            # Store metadata in file if path provided
            if self.storage_path:
                metadata_path = os.path.join(self.storage_path, f"{key_id}.json")
                with open(metadata_path, 'w') as f:
                    json.dump(self._key_metadata[key_id].to_dict(), f, indent=2)
                    
        elif self.storage_type == KeyStorageType.MEMORY:
            # Only store in memory cache
            self._key_cache[key_id] = key_material
            
        else:
            raise ValueError(f"Unsupported storage type: {self.storage_type}")
    
    def _retrieve_key_material(self, key_id: str) -> bytes:
        """Retrieve key material from secure storage."""
        if self.storage_type == KeyStorageType.FILE:
            if not self.storage_path:
                raise ValueError("Storage path must be provided for file-based storage")
            
            # Read key material from file
            key_path = os.path.join(self.storage_path, f"{key_id}.key")
            if not os.path.exists(key_path):
                raise ValueError(f"Key not found: {key_id}")
            
            with open(key_path, 'rb') as f:
                return f.read()
                
        elif self.storage_type == KeyStorageType.KEYRING and HAS_KEYRING:
            # Retrieve from system keyring
            key_hex = keyring.get_password("mcp_encryption", key_id)
            if not key_hex:
                raise ValueError(f"Key not found: {key_id}")
            
            return bytes.fromhex(key_hex)
                
        elif self.storage_type == KeyStorageType.ENVIRONMENT:
            # Retrieve from environment variable
            key_hex = os.environ.get(f"MCP_KEY_{key_id}")
            if not key_hex:
                raise ValueError(f"Key not found: {key_id}")
            
            return bytes.fromhex(key_hex)
                
        elif self.storage_type == KeyStorageType.MEMORY:
            # Only in memory cache
            if key_id not in self._key_cache:
                raise ValueError(f"Key not found: {key_id}")
            
            return self._key_cache[key_id]
            
        else:
            raise ValueError(f"Unsupported storage type: {self.storage_type}")
    
    def _delete_key_material(self, key_id: str) -> None:
        """Delete key material from secure storage."""
        if self.storage_type == KeyStorageType.FILE:
            if not self.storage_path:
                raise ValueError("Storage path must be provided for file-based storage")
            
            # Delete key material file
            key_path = os.path.join(self.storage_path, f"{key_id}.key")
            if os.path.exists(key_path):
                os.remove(key_path)
            
            # Delete metadata file
            metadata_path = os.path.join(self.storage_path, f"{key_id}.json")
            if os.path.exists(metadata_path):
                os.remove(metadata_path)
                
        elif self.storage_type == KeyStorageType.KEYRING and HAS_KEYRING:
            # Delete from system keyring
            try:
                keyring.delete_password("mcp_encryption", key_id)
            except keyring.errors.PasswordDeleteError:
                pass
            
            # Delete metadata file if path provided
            if self.storage_path:
                metadata_path = os.path.join(self.storage_path, f"{key_id}.json")
                if os.path.exists(metadata_path):
                    os.remove(metadata_path)
                    
        elif self.storage_type == KeyStorageType.ENVIRONMENT:
            # Remove from environment variable
            if f"MCP_KEY_{key_id}" in os.environ:
                del os.environ[f"MCP_KEY_{key_id}"]
            
            # Delete metadata file if path provided
            if self.storage_path:
                metadata_path = os.path.join(self.storage_path, f"{key_id}.json")
                if os.path.exists(metadata_path):
                    os.remove(metadata_path)
                    
        elif self.storage_type == KeyStorageType.MEMORY:
            # Already removed from cache in delete_key
            pass
            
        else:
            raise ValueError(f"Unsupported storage type: {self.storage_type}")
    
    def _load_key_metadata(self, key_id: str) -> Optional[EncryptionKey]:
        """Load key metadata from storage."""
        if self.storage_type in [KeyStorageType.FILE, KeyStorageType.KEYRING, KeyStorageType.ENVIRONMENT]:
            if not self.storage_path:
                return None
            
            # Read metadata from file
            metadata_path = os.path.join(self.storage_path, f"{key_id}.json")
            if not os.path.exists(metadata_path):
                return None
            
            with open(metadata_path, 'r') as f:
                metadata_dict = json.load(f)
                return EncryptionKey(**metadata_dict)
        
        return None
    
    def _save_key_metadata(self, key_id: str, key: EncryptionKey) -> None:
        """Save key metadata to storage."""
        if self.storage_type in [KeyStorageType.FILE, KeyStorageType.KEYRING, KeyStorageType.ENVIRONMENT]:
            if not self.storage_path:
                return
            
            # Write metadata to file
            metadata_path = os.path.join(self.storage_path, f"{key_id}.json")
            with open(metadata_path, 'w') as f:
                json.dump(key.to_dict(), f, indent=2)
    
    def _load_all_key_metadata(self) -> None:
        """Load all key metadata from storage."""
        if self.storage_type in [KeyStorageType.FILE, KeyStorageType.KEYRING, KeyStorageType.ENVIRONMENT]:
            if not self.storage_path or not os.path.exists(self.storage_path):
                return
            
            # List all JSON files in storage directory
            for filename in os.listdir(self.storage_path):
                if filename.endswith(".json"):
                    key_id = filename[:-5]  # Remove .json extension
                    if key_id not in self._key_metadata:
                        metadata = self._load_key_metadata(key_id)
                        if metadata:
                            self._key_metadata[key_id] = metadata


class EncryptionManager:
    """
    Manages encryption and decryption operations.
    
    This class is responsible for:
    - Encrypting and decrypting data
    - Managing encryption policies
    - Integrating with key management
    """
    
    def __init__(self, key_manager: KeyManager):
        """
        Initialize the encryption manager.
        
        Args:
            key_manager: Key manager for key operations
        """
        if not HAS_CRYPTOGRAPHY:
            raise RuntimeError("Cryptography package is required for encryption")
        
        self.key_manager = key_manager
        
        # Encryption policies
        self._policies: Dict[str, EncryptionPolicy] = {}
        
        # Thread safety
        self._lock = threading.RLock()
        
        logger.info("Initialized encryption manager")
    
    def encrypt(self, data: Union[bytes, BinaryIO], 
               key_id: Optional[str] = None,
               algorithm: Optional[EncryptionAlgorithm] = None,
               content_type: Optional[str] = None,
               metadata: Optional[Dict[str, Any]] = None,
               additional_authenticated_data: Optional[bytes] = None) -> EncryptedData:
        """
        Encrypt data using the specified key and algorithm.
        
        Args:
            data: Data to encrypt (bytes or file-like object)
            key_id: ID of the key to use (if None, a policy-based key will be selected)
            algorithm: Encryption algorithm to use (if None, determined by key or policy)
            content_type: Optional content type of the data
            metadata: Optional metadata to include with the encrypted data
            additional_authenticated_data: Optional AAD for authenticated encryption
            
        Returns:
            EncryptedData object containing the encrypted data and metadata
        """
        # Convert file-like object to bytes if needed
        if hasattr(data, 'read'):
            data_bytes = data.read()
            if isinstance(data_bytes, str):
                data_bytes = data_bytes.encode('utf-8')
        else:
            data_bytes = data
        
        # If no key provided, select based on policy
        if not key_id:
            key_id, algorithm = self._select_key_from_policy(content_type)
        
        # If key is provided but no algorithm, get it from the key
        if key_id and not algorithm:
            key_metadata = self.key_manager.get_key_metadata(key_id)
            if not key_metadata:
                raise ValueError(f"Key not found: {key_id}")
            algorithm = key_metadata.algorithm
        
        # Get key material
        key_material = self.key_manager.get_key(key_id)
        
        # Create encrypted data object with ID
        encrypted_data_id = str(uuid.uuid4())
        encrypted_data = EncryptedData(
            id=encrypted_data_id,
            encryption_key_id=key_id,
            algorithm=algorithm,
            content_type=content_type,
            original_size=len(data_bytes),
            metadata=metadata or {},
            created_at=datetime.utcnow().isoformat()
        )
        
        # Perform encryption based on algorithm
        if algorithm == EncryptionAlgorithm.AES_256_GCM:
            # Generate initialization vector
            iv = secrets.token_bytes(12)  # 96 bits for GCM
            encrypted_data.initialization_vector = iv
            
            # Set additional authenticated data if provided
            if additional_authenticated_data:
                encrypted_data.additional_authenticated_data = additional_authenticated_data
            
            # Create encryptor
            encryptor = Cipher(
                algorithms.AES(key_material),
                modes.GCM(iv)
            ).encryptor()
            
            # Update with AAD if provided
            if additional_authenticated_data:
                encryptor.authenticate_additional_data(additional_authenticated_data)
            
            # Encrypt data
            ciphertext = encryptor.update(data_bytes) + encryptor.finalize()
            
            # Get authentication tag
            auth_tag = encryptor.tag
            
            encrypted_data.encrypted_data = ciphertext
            encrypted_data.auth_tag = auth_tag
            
        elif algorithm == EncryptionAlgorithm.AES_256_CBC:
            # Generate initialization vector
            iv = secrets.token_bytes(16)  # 128 bits for CBC
            encrypted_data.initialization_vector = iv
            
            # Create encryptor
            encryptor = Cipher(
                algorithms.AES(key_material),
                modes.CBC(iv)
            ).encryptor()
            
            # Add PKCS7 padding
            padder = padding.PKCS7(algorithms.AES.block_size).padder()
            padded_data = padder.update(data_bytes) + padder.finalize()
            
            # Encrypt data
            ciphertext = encryptor.update(padded_data) + encryptor.finalize()
            
            encrypted_data.encrypted_data = ciphertext
            
        elif algorithm == EncryptionAlgorithm.CHACHA20_POLY1305:
            # Generate initialization vector
            iv = secrets.token_bytes(16)  # 128 bits for nonce
            encrypted_data.initialization_vector = iv
            
            # Set additional authenticated data if provided
            if additional_authenticated_data:
                encrypted_data.additional_authenticated_data = additional_authenticated_data
            
            # Import if available
            try:
                from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
                chacha = ChaCha20Poly1305(key_material)
                
                # Encrypt data
                ciphertext = chacha.encrypt(iv, data_bytes, additional_authenticated_data)
                encrypted_data.encrypted_data = ciphertext
            except ImportError:
                raise ValueError("ChaCha20Poly1305 is not available in this cryptography installation")
            
        elif algorithm == EncryptionAlgorithm.RSA_OAEP:
            # For RSA, we need to ensure we're using the public key for encryption
            key_metadata = self.key_manager.get_key_metadata(key_id)
            if not key_metadata or key_metadata.type != KeyType.ASYMMETRIC_PUBLIC:
                raise ValueError("RSA encryption requires a public key")
            
            # Load public key
            public_key = serialization.load_pem_public_key(key_material)
            
            # RSA can only encrypt small amounts of data, so we use a hybrid approach:
            # 1. Generate a random symmetric key
            symmetric_key = secrets.token_bytes(32)  # 256 bits
            
            # 2. Encrypt the data with the symmetric key using AES-GCM
            iv = secrets.token_bytes(12)  # 96 bits for GCM
            encrypted_data.initialization_vector = iv
            
            # Set additional authenticated data if provided
            if additional_authenticated_data:
                encrypted_data.additional_authenticated_data = additional_authenticated_data
            
            # Create encryptor
            encryptor = Cipher(
                algorithms.AES(symmetric_key),
                modes.GCM(iv)
            ).encryptor()
            
            # Update with AAD if provided
            if additional_authenticated_data:
                encryptor.authenticate_additional_data(additional_authenticated_data)
            
            # Encrypt data
            ciphertext = encryptor.update(data_bytes) + encryptor.finalize()
            
            # Get authentication tag
            auth_tag = encryptor.tag
            
            # 3. Encrypt the symmetric key with the RSA public key
            encrypted_key = public_key.encrypt(
                symmetric_key,
                OAEP(
                    mgf=MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            # 4. Store the encrypted key in the metadata
            encrypted_data.metadata["encrypted_key"] = base64.b64encode(encrypted_key).decode("utf-8")
            encrypted_data.encrypted_data = ciphertext
            encrypted_data.auth_tag = auth_tag
            
        elif algorithm == EncryptionAlgorithm.FERNET:
            # Fernet is a high-level recipe that combines AES-CBC and HMAC
            fernet = Fernet(key_material)
            ciphertext = fernet.encrypt(data_bytes)
            encrypted_data.encrypted_data = ciphertext
            
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
        
        logger.debug(f"Encrypted {len(data_bytes)} bytes using {algorithm}")
        
        return encrypted_data
    
    def decrypt(self, encrypted_data: EncryptedData) -> bytes:
        """
        Decrypt data using the specified key.
        
        Args:
            encrypted_data: EncryptedData object to decrypt
            
        Returns:
            Decrypted data as bytes
        """
        # Get key material
        key_id = encrypted_data.encryption_key_id
        key_material = self.key_manager.get_key(key_id)
        
        algorithm = encrypted_data.algorithm
        
        # Perform decryption based on algorithm
        if algorithm == EncryptionAlgorithm.AES_256_GCM:
            # Get initialization vector and auth tag
            iv = encrypted_data.initialization_vector
            auth_tag = encrypted_data.auth_tag
            
            if not iv or not auth_tag:
                raise ValueError("Missing initialization vector or authentication tag for AES-GCM decryption")
            
            # Create decryptor
            decryptor = Cipher(
                algorithms.AES(key_material),
                modes.GCM(iv, auth_tag)
            ).decryptor()
            
            # Update with AAD if provided
            if encrypted_data.additional_authenticated_data:
                decryptor.authenticate_additional_data(encrypted_data.additional_authenticated_data)
            
            # Decrypt data
            plaintext = decryptor.update(encrypted_data.encrypted_data) + decryptor.finalize()
            
        elif algorithm == EncryptionAlgorithm.AES_256_CBC:
            # Get initialization vector
            iv = encrypted_data.initialization_vector
            
            if not iv:
                raise ValueError("Missing initialization vector for AES-CBC decryption")
            
            # Create decryptor
            decryptor = Cipher(
                algorithms.AES(key_material),
                modes.CBC(iv)
            ).decryptor()
            
            # Decrypt data
            padded_plaintext = decryptor.update(encrypted_data.encrypted_data) + decryptor.finalize()
            
            # Remove PKCS7 padding
            unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
            plaintext = unpadder.update(padded_plaintext) + unpadder.finalize()
            
        elif algorithm == EncryptionAlgorithm.CHACHA20_POLY1305:
            # Get initialization vector
            iv = encrypted_data.initialization_vector
            
            if not iv:
                raise ValueError("Missing initialization vector for ChaCha20Poly1305 decryption")
            
            # Import if available
            try:
                from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
                chacha = ChaCha20Poly1305(key_material)
                
                # Decrypt data
                plaintext = chacha.decrypt(
                    iv, 
                    encrypted_data.encrypted_data, 
                    encrypted_data.additional_authenticated_data
                )
            except ImportError:
                raise ValueError("ChaCha20Poly1305 is not available in this cryptography installation")
            
        elif algorithm == EncryptionAlgorithm.RSA_OAEP:
            # For RSA, we need to ensure we're using the private key for decryption
            key_metadata = self.key_manager.get_key_metadata(key_id)
            if not key_metadata or key_metadata.type != KeyType.ASYMMETRIC_PRIVATE:
                raise ValueError("RSA decryption requires a private key")
            
            # Load private key
            private_key = serialization.load_pem_private_key(
                key_material,
                password=None
            )
            
            # 1. Decrypt the symmetric key with the RSA private key
            encrypted_key_b64 = encrypted_data.metadata.get("encrypted_key")
            if not encrypted_key_b64:
                raise ValueError("Missing encrypted key in metadata for RSA decryption")
            
            encrypted_key = base64.b64decode(encrypted_key_b64)
            
            symmetric_key = private_key.decrypt(
                encrypted_key,
                OAEP(
                    mgf=MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            # 2. Decrypt the data with the symmetric key using AES-GCM
            iv = encrypted_data.initialization_vector
            auth_tag = encrypted_data.auth_tag
            
            if not iv or not auth_tag:
                raise ValueError("Missing initialization vector or authentication tag for hybrid RSA decryption")
            
            # Create decryptor
            decryptor = Cipher(
                algorithms.AES(symmetric_key),
                modes.GCM(iv, auth_tag)
            ).decryptor()
            
            # Update with AAD if provided
            if encrypted_data.additional_authenticated_data:
                decryptor.authenticate_additional_data(encrypted_data.additional_authenticated_data)
            
            # Decrypt data
            plaintext = decryptor.update(encrypted_data.encrypted_data) + decryptor.finalize()
            
        elif algorithm == EncryptionAlgorithm.FERNET:
            # Fernet is a high-level recipe that combines AES-CBC and HMAC
            fernet = Fernet(key_material)
            plaintext = fernet.decrypt(encrypted_data.encrypted_data)
            
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
        
        logger.debug(f"Decrypted {len(encrypted_data.encrypted_data)} bytes using {algorithm}")
        
        return plaintext
    
    def add_policy(self, policy: EncryptionPolicy) -> None:
        """
        Add or update an encryption policy.
        
        Args:
            policy: Policy to add or update
        """
        with self._lock:
            self._policies[policy.id] = policy
            logger.info(f"Added encryption policy: {policy.id} ({policy.name})")
    
    def get_policy(self, policy_id: str) -> Optional[EncryptionPolicy]:
        """
        Get an encryption policy by ID.
        
        Args:
            policy_id: ID of the policy to get
            
        Returns:
            EncryptionPolicy object or None if not found
        """
        with self._lock:
            return self._policies.get(policy_id)
    
    def list_policies(self, enabled_only: bool = True) -> List[EncryptionPolicy]:
        """
        List all encryption policies.
        
        Args:
            enabled_only: Whether to only include enabled policies
            
        Returns:
            List of EncryptionPolicy objects
        """
        with self._lock:
            if enabled_only:
                return [p for p in self._policies.values() if p.enabled]
            else:
                return list(self._policies.values())
    
    def delete_policy(self, policy_id: str) -> bool:
        """
        Delete an encryption policy.
        
        Args:
            policy_id: ID of the policy to delete
            
        Returns:
            True if policy was deleted, False if not found
        """
        with self._lock:
            if policy_id in self._policies:
                del self._policies[policy_id]
                logger.info(f"Deleted encryption policy: {policy_id}")
                return True
            return False
    
    def encrypt_file(self, input_path: str, output_path: str,
                    key_id: Optional[str] = None,
                    algorithm: Optional[EncryptionAlgorithm] = None,
                    content_type: Optional[str] = None,
                    metadata: Optional[Dict[str, Any]] = None,
                    additional_authenticated_data: Optional[bytes] = None) -> EncryptedData:
        """
        Encrypt a file and save the encrypted data to another file.
        
        Args:
            input_path: Path to input file
            output_path: Path to output file
            key_id: ID of the key to use (if None, a policy-based key will be selected)
            algorithm: Encryption algorithm to use (if None, determined by key or policy)
            content_type: Optional content type of the data
            metadata: Optional metadata to include with the encrypted data
            additional_authenticated_data: Optional AAD for authenticated encryption
            
        Returns:
            EncryptedData object containing metadata about the encrypted file
        """
        # Read input file
        with open(input_path, 'rb') as f:
            data = f.read()
        
        # Encrypt data
        encrypted_data = self.encrypt(
            data,
            key_id=key_id,
            algorithm=algorithm,
            content_type=content_type or os.path.basename(input_path),
            metadata=metadata,
            additional_authenticated_data=additional_authenticated_data
        )
        
        # Prepare output data
        output_data = {
            "id": encrypted_data.id,
            "encryption_key_id": encrypted_data.encryption_key_id,
            "algorithm": encrypted_data.algorithm,
            "content_type": encrypted_data.content_type,
            "original_size": encrypted_data.original_size,
            "metadata": encrypted_data.metadata,
            "created_at": encrypted_data.created_at
        }
        
        # Convert binary fields to base64
        if encrypted_data.initialization_vector:
            output_data["initialization_vector"] = base64.b64encode(encrypted_data.initialization_vector).decode('utf-8')
        if encrypted_data.auth_tag:
            output_data["auth_tag"] = base64.b64encode(encrypted_data.auth_tag).decode('utf-8')
        if encrypted_data.additional_authenticated_data:
            output_data["additional_authenticated_data"] = base64.b64encode(encrypted_data.additional_authenticated_data).decode('utf-8')
        
        # Write encrypted data and metadata
        with open(output_path, 'wb') as f:
            # First, write the metadata header
            header = json.dumps(output_data).encode('utf-8')
            header_length = len(header)
            f.write(header_length.to_bytes(4, byteorder='big'))
            f.write(header)
            
            # Then, write the encrypted data
            f.write(encrypted_data.encrypted_data)
        
        logger.info(f"Encrypted file {input_path} to {output_path} using {encrypted_data.algorithm}")
        
        return encrypted_data
    
    def decrypt_file(self, input_path: str, output_path: str) -> Dict[str, Any]:
        """
        Decrypt a file that was encrypted with encrypt_file.
        
        Args:
            input_path: Path to input file
            output_path: Path to output file
            
        Returns:
            Dictionary containing metadata about the decrypted file
        """
        # Read input file
        with open(input_path, 'rb') as f:
            # Read the metadata header length
            header_length_bytes = f.read(4)
            header_length = int.from_bytes(header_length_bytes, byteorder='big')
            
            # Read the metadata header
            header = f.read(header_length)
            header_data = json.loads(header.decode('utf-8'))
            
            # Read the encrypted data
            encrypted_data_bytes = f.read()
        
        # Create EncryptedData object
        encrypted_data = EncryptedData(
            id=header_data["id"],
            encryption_key_id=header_data["encryption_key_id"],
            algorithm=header_data["algorithm"],
            content_type=header_data.get("content_type"),
            original_size=header_data.get("original_size"),
            metadata=header_data.get("metadata", {}),
            created_at=header_data.get("created_at", datetime.utcnow().isoformat())
        )
        
        # Convert base64 fields to binary
        if "initialization_vector" in header_data:
            encrypted_data.initialization_vector = base64.b64decode(header_data["initialization_vector"])
        if "auth_tag" in header_data:
            encrypted_data.auth_tag = base64.b64decode(header_data["auth_tag"])
        if "additional_authenticated_data" in header_data:
            encrypted_data.additional_authenticated_data = base64.b64decode(header_data["additional_authenticated_data"])
        
        # Set encrypted data
        encrypted_data.encrypted_data = encrypted_data_bytes
        
        # Decrypt data
        plaintext = self.decrypt(encrypted_data)
        
        # Write decrypted data
        with open(output_path, 'wb') as f:
            f.write(plaintext)
        
        logger.info(f"Decrypted file {input_path} to {output_path}")
        
        return header_data
    
    def _select_key_from_policy(self, content_type: Optional[str] = None) -> Tuple[str, EncryptionAlgorithm]:
        """
        Select a key based on content type and policies.
        
        Args:
            content_type: Optional content type to match with policies
            
        Returns:
            Tuple of (key_id, algorithm)
        """
        with self._lock:
            # Find matching policies
            matching_policies = []
            
            for policy in self._policies.values():
                if not policy.enabled:
                    continue
                
                if content_type and policy.content_types:
                    # Check if content type matches any policy content types
                    for pattern in policy.content_types:
                        if self._match_content_type(content_type, pattern):
                            matching_policies.append(policy)
                            break
                else:
                    # If no content type specified or policy doesn't specify content types,
                    # include policy if it's global
                    if policy.scope == EncryptionScope.GLOBAL:
                        matching_policies.append(policy)
            
            # If no matching policies, use default
            if not matching_policies:
                # Find a suitable key
                keys = self.key_manager.list_keys(
                    key_type=KeyType.SYMMETRIC,
                    algorithm=EncryptionAlgorithm.AES_256_GCM
                )
                
                if not keys:
                    # Generate a new key
                    key = self.key_manager.generate_key(
                        key_type=KeyType.SYMMETRIC,
                        algorithm=EncryptionAlgorithm.AES_256_GCM,
                        description="Default encryption key"
                    )
                else:
                    key = keys[0]
                
                return key.id, key.algorithm
            
            # Sort policies by specificity (content type > scope)
            matching_policies.sort(key=lambda p: (
                1 if p.content_types else 0,
                0 if p.scope == EncryptionScope.GLOBAL else 1
            ), reverse=True)
            
            # Use the most specific policy
            policy = matching_policies[0]
            
            # Find a suitable key for this policy
            keys = self.key_manager.list_keys(
                key_type=KeyType.SYMMETRIC,
                algorithm=policy.algorithm
            )
            
            if not keys:
                # Generate a new key
                key = self.key_manager.generate_key(
                    key_type=KeyType.SYMMETRIC,
                    algorithm=policy.algorithm,
                    description=f"Key for policy {policy.id} ({policy.name})"
                )
            else:
                key = keys[0]
            
            return key.id, key.algorithm
    
    def _match_content_type(self, content_type: str, pattern: str) -> bool:
        """
        Check if a content type matches a pattern.
        
        Args:
            content_type: Content type to check
            pattern: Pattern to match (can include wildcards)
            
        Returns:
            True if the content type matches the pattern
        """
        # Convert pattern to regex
        pattern_regex = pattern.replace(".", "\\.").replace("*", ".*")
        import re
        return bool(re.match(f"^{pattern_regex}$", content_type))


class BackendEncryptionHandler:
    """
    Handles encryption for storage backends.
    
    This class provides a way to add encryption capabilities to
    storage backends, allowing transparent encryption/decryption
    of data before it's stored or after it's retrieved.
    """
    
    def __init__(self, encryption_manager: EncryptionManager):
        """
        Initialize the backend encryption handler.
        
        Args:
            encryption_manager: Encryption manager to use
        """
        self.encryption_manager = encryption_manager
        
        # Thread safety
        self._lock = threading.RLock()
        
        logger.info("Initialized backend encryption handler")
    
    def encrypt_data_for_storage(self, 
                               data: bytes,
                               key_id: Optional[str] = None,
                               metadata: Optional[Dict[str, Any]] = None,
                               content_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Encrypt data for storage in a backend.
        
        Args:
            data: Data to encrypt
            key_id: Optional key ID to use for encryption
            metadata: Optional metadata to include
            content_type: Optional content type of the data
            
        Returns:
            Dictionary containing encrypted data and metadata
        """
        # Combine user metadata with our encryption metadata
        combined_metadata = metadata.copy() if metadata else {}
        
        # Encrypt the data
        encrypted_data = self.encryption_manager.encrypt(
            data=data,
            key_id=key_id,
            content_type=content_type,
            metadata=combined_metadata
        )
        
        # Convert to a format suitable for storage
        result = {
            "data": encrypted_data.encrypted_data,
            "encryption": {
                "id": encrypted_data.id,
                "key_id": encrypted_data.encryption_key_id,
                "algorithm": encrypted_data.algorithm,
                "iv": base64.b64encode(encrypted_data.initialization_vector).decode('utf-8') if encrypted_data.initialization_vector else None,
                "tag": base64.b64encode(encrypted_data.auth_tag).decode('utf-8') if encrypted_data.auth_tag else None,
                "aad": base64.b64encode(encrypted_data.additional_authenticated_data).decode('utf-8') if encrypted_data.additional_authenticated_data else None,
                "content_type": encrypted_data.content_type,
                "original_size": encrypted_data.original_size,
                "created_at": encrypted_data.created_at
            },
            "metadata": combined_metadata
        }
        
        return result
    
    def decrypt_data_from_storage(self, 
                                encrypted_result: Dict[str, Any]) -> Tuple[bytes, Dict[str, Any]]:
        """
        Decrypt data retrieved from storage.
        
        Args:
            encrypted_result: Result from encrypt_data_for_storage
            
        Returns:
            Tuple of (decrypted_data, metadata)
        """
        # Extract encryption metadata
        encryption_info = encrypted_result.get("encryption", {})
        
        if not encryption_info:
            # Data is not encrypted
            return encrypted_result.get("data", b""), encrypted_result.get("metadata", {})
        
        # Create EncryptedData object
        encrypted_data = EncryptedData(
            id=encryption_info.get("id", str(uuid.uuid4())),
            encryption_key_id=encryption_info.get("key_id"),
            algorithm=encryption_info.get("algorithm"),
            encrypted_data=encrypted_result.get("data"),
            content_type=encryption_info.get("content_type"),
            original_size=encryption_info.get("original_size"),
            metadata=encrypted_result.get("metadata", {}),
            created_at=encryption_info.get("created_at", datetime.utcnow().isoformat())
        )
        
        # Convert base64 fields
        if encryption_info.get("iv"):
            encrypted_data.initialization_vector = base64.b64decode(encryption_info["iv"])
        if encryption_info.get("tag"):
            encrypted_data.auth_tag = base64.b64decode(encryption_info["tag"])
        if encryption_info.get("aad"):
            encrypted_data.additional_authenticated_data = base64.b64decode(encryption_info["aad"])
        
        # Decrypt the data
        decrypted_data = self.encryption_manager.decrypt(encrypted_data)
        
        return decrypted_data, encrypted_result.get("metadata", {})
