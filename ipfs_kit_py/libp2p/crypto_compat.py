"""
Compatibility module for libp2p cryptography operations.

This module provides compatibility functions for working with libp2p's 
cryptography components, particularly when there are differences between
the expected and actual API of the libp2p package.
"""

import os
import logging
from typing import Optional, Tuple, Union, Any

# Configure logger
logger = logging.getLogger(__name__)

# Module-level variable to track which key generation method was successful
# This is updated by install_libp2p.py when it successfully verifies key generation
PREFERRED_KEY_GENERATION_METHOD = None

# Import libp2p components with graceful fallbacks
try:
    import libp2p.crypto.keys
    from libp2p.crypto.keys import KeyPair, PrivateKey, PublicKey, KeyType
    HAS_KEYS = True
except ImportError as e:
    logger.warning(f"Failed to import libp2p.crypto.keys: {e}")
    HAS_KEYS = False

try:
    from libp2p.crypto.serialization import deserialize_private_key
    HAS_SERIALIZATION = True
except ImportError as e:
    logger.warning(f"Failed to import libp2p.crypto.serialization: {e}")
    HAS_SERIALIZATION = False

def serialize_private_key(private_key: Any) -> bytes:
    """
    Serialize a private key to bytes format.
    
    This function provides a compatibility layer for the missing
    serialize_private_key function in some libp2p versions.
    
    Args:
        private_key: The PrivateKey object to serialize
        
    Returns:
        The serialized key as bytes
    """
    # First try the object's own serialization methods
    if hasattr(private_key, "serialize"):
        return private_key.serialize()
    elif hasattr(private_key, "to_bytes"):
        return private_key.to_bytes()
    elif hasattr(private_key, "private_key"):
        # Some implementations wrap the actual key
        inner_key = private_key.private_key
        if hasattr(inner_key, "serialize"):
            return inner_key.serialize()
        elif hasattr(inner_key, "to_bytes"):
            return inner_key.to_bytes()
            
    # Last resort, try to serialize through protobuf
    if hasattr(private_key, "__bytes__"):
        return bytes(private_key)
        
    # Handle our custom MockPrivateKey class
    if hasattr(private_key, "key_data"):
        # If key_data is already bytes, return it
        if isinstance(private_key.key_data, bytes):
            return private_key.key_data
        # If key_data is a cryptography key object (from our custom implementation)
        elif hasattr(private_key, "_key_obj") and private_key._key_obj is not None:
            # Try to serialize it using cryptography
            try:
                from cryptography.hazmat.primitives import serialization
                # Handle RSA keys
                if hasattr(private_key._key_obj, "private_bytes"):
                    return private_key._key_obj.private_bytes(
                        encoding=serialization.Encoding.DER,
                        format=serialization.PrivateFormat.PKCS8,
                        encryption_algorithm=serialization.NoEncryption()
                    )
            except ImportError:
                # Fall back to raw key data if available
                return str(private_key).encode()
        
    # If we get here, we don't know how to serialize this key
    raise ValueError(f"Don't know how to serialize key of type {type(private_key)}")

def generate_key_pair(key_type: Optional[str] = None) -> Any:
    """
    Generate a new key pair for use with libp2p.
    
    This function provides a compatibility layer for the missing
    generate_key_pair function in some libp2p versions.
    
    Args:
        key_type: Optional key type ("RSA", "Ed25519", "Secp256k1")
                 If not specified, defaults to "RSA"
                 
    Returns:
        A KeyPair object or equivalent
    """
    if not HAS_KEYS:
        raise ImportError("libp2p.crypto.keys is not available")
    
    # First try to use the method that was previously verified to work
    if PREFERRED_KEY_GENERATION_METHOD:
        try:
            logger.debug(f"Attempting to use preferred method: {PREFERRED_KEY_GENERATION_METHOD}")
            
            # Method: rsa.create_new_key_pair()
            if PREFERRED_KEY_GENERATION_METHOD == "rsa.create_new_key_pair()":
                from libp2p.crypto import rsa
                return rsa.create_new_key_pair()
                
            # Method: secp256k1.create_new_key_pair()
            elif PREFERRED_KEY_GENERATION_METHOD == "secp256k1.create_new_key_pair()":
                from libp2p.crypto import secp256k1
                return secp256k1.create_new_key_pair()
                
            # Method: ed25519.Ed25519PrivateKey.generate()
            elif PREFERRED_KEY_GENERATION_METHOD == "ed25519.Ed25519PrivateKey.generate()":
                from libp2p.crypto import ed25519
                private_key = ed25519.Ed25519PrivateKey.generate()
                public_key = private_key.get_public_key()
                return KeyPair(private_key, public_key)
                
            # Method: generate_key_pair()
            elif PREFERRED_KEY_GENERATION_METHOD == "generate_key_pair()":
                from libp2p.crypto.keys import generate_key_pair as lib_generate_key_pair
                return lib_generate_key_pair()
                
            # Method: KeyPair.generate()
            elif PREFERRED_KEY_GENERATION_METHOD == "KeyPair.generate()":
                return KeyPair.generate()
                
        except Exception as e:
            logger.warning(f"Preferred method {PREFERRED_KEY_GENERATION_METHOD} failed: {e}")
            # Fall back to our custom implementation
    
    # If preferred method failed or isn't set, try other native methods
    # Try all the native methods in order of preference
    try:
        # Try RSA key generation
        try:
            from libp2p.crypto import rsa
            if hasattr(rsa, 'create_new_key_pair'):
                key_pair = rsa.create_new_key_pair()
                logger.debug("Generated key using rsa.create_new_key_pair()")
                return key_pair
        except Exception:
            pass
            
        # Try Secp256k1 key generation
        try:
            from libp2p.crypto import secp256k1
            if hasattr(secp256k1, 'create_new_key_pair'):
                key_pair = secp256k1.create_new_key_pair()
                logger.debug("Generated key using secp256k1.create_new_key_pair()")
                return key_pair
        except Exception:
            pass
            
        # Try Ed25519 key generation
        try:
            from libp2p.crypto import ed25519
            if hasattr(ed25519, 'Ed25519PrivateKey') and hasattr(ed25519.Ed25519PrivateKey, 'generate'):
                private_key = ed25519.Ed25519PrivateKey.generate()
                public_key = private_key.get_public_key()
                key_pair = KeyPair(private_key, public_key)
                logger.debug("Generated key using ed25519.Ed25519PrivateKey.generate()")
                return key_pair
        except Exception:
            pass
            
        # Try legacy module function
        try:
            from libp2p.crypto.keys import generate_key_pair as lib_generate_key_pair
            key_pair = lib_generate_key_pair()
            logger.debug("Generated key using libp2p.crypto.keys.generate_key_pair()")
            return key_pair
        except Exception:
            pass
            
        # Try direct KeyPair class method
        try:
            key_pair = KeyPair.generate()
            logger.debug("Generated key using KeyPair.generate()")
            return key_pair
        except Exception:
            pass
    except Exception as e:
        logger.debug(f"All native key generation methods failed: {e}")
        # Fall back to custom implementation
    
    # Let's create a custom implementation if the libp2p functions aren't available
    logger.debug("Falling back to custom key implementation")
    from cryptography.hazmat.primitives.asymmetric import rsa, ed25519
    from cryptography.hazmat.primitives import serialization
    import hashlib
    
    class MockPrivateKey:
        """Mock implementation of a PrivateKey for compatibility."""
        def __init__(self, key_data, key_type="RSA"):
            self.key_data = key_data
            self.key_type = key_type
            # For RSA private keys, we need to keep the actual key object
            self._key_obj = None
            if key_type == "RSA" and isinstance(key_data, rsa.RSAPrivateKey):
                self._key_obj = key_data
        
        def get_public_key(self):
            """Get the corresponding public key."""
            if self.key_type == "RSA" and self._key_obj:
                public_key = self._key_obj.public_key()
                return MockPublicKey(public_key, "RSA")
            elif self.key_type == "Ed25519":
                # For Ed25519, we'd need the actual key object
                # This is a simplified implementation
                return MockPublicKey(self.key_data[32:], "Ed25519")
            return MockPublicKey(self.key_data, self.key_type)
            
        def __str__(self):
            if isinstance(self.key_data, bytes):
                return f"MockPrivateKey({self.key_type}, {len(self.key_data)} bytes)"
            elif self._key_obj is not None:
                return f"MockPrivateKey({self.key_type}, RSA key object)"
            else:
                return f"MockPrivateKey({self.key_type})"
            
        def __repr__(self):
            return self.__str__()
            
    class MockPublicKey:
        """Mock implementation of a PublicKey for compatibility."""
        def __init__(self, key_data, key_type="RSA"):
            self.key_data = key_data
            self.key_type = key_type
            self._key_obj = None
            if key_type == "RSA" and hasattr(key_data, "public_bytes"):
                self._key_obj = key_data
        
        def serialize(self):
            """Serialize the public key to bytes."""
            try:
                # If we have an actual key object from cryptography, use it
                if self._key_obj and hasattr(self._key_obj, "public_bytes"):
                    from cryptography.hazmat.primitives import serialization
                    return self._key_obj.public_bytes(
                        encoding=serialization.Encoding.DER,
                        format=serialization.PublicFormat.SubjectPublicKeyInfo
                    )
                # Otherwise return the key_data if it's bytes
                elif isinstance(self.key_data, bytes):
                    return self.key_data
                # Last resort: Try converting to bytes if possible
                elif hasattr(self.key_data, "__bytes__"):
                    return bytes(self.key_data)
                else:
                    # Generate some deterministic bytes based on the string representation
                    import hashlib
                    return hashlib.sha256(str(self.key_data).encode()).digest()
            except Exception as e:
                logger.error(f"Error serializing public key: {e}")
                # Return a dummy value to avoid crashing
                return b"MockPublicKeyData"
                
        def __str__(self):
            if isinstance(self.key_data, bytes):
                return f"MockPublicKey({self.key_type}, {len(self.key_data)} bytes)"
            else:
                return f"MockPublicKey({self.key_type})"
            
        def __repr__(self):
            return self.__str__()
    
    # Create a mock KeyPair similar to what libp2p would return
    class MockKeyPair:
        """Mock implementation of a libp2p KeyPair."""
        def __init__(self, private_key, public_key):
            self.private_key = private_key
            self.public_key = public_key
            
        def __str__(self):
            return f"MockKeyPair({self.private_key}, {self.public_key})"
            
        def __repr__(self):
            return self.__str__()
            
    # Now generate a key pair based on the requested type
    if key_type is None or key_type == "RSA" or key_type == 0:
        # Generate RSA key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        
        # Create our mock objects
        priv_key = MockPrivateKey(private_key, "RSA")
        pub_key = priv_key.get_public_key()
        
        logger.warning("Using custom RSA key generation due to missing libp2p functions")
        return MockKeyPair(priv_key, pub_key)
        
    elif key_type == "Ed25519" or key_type == 1:
        # Generate Ed25519 key
        private_key = ed25519.Ed25519PrivateKey.generate()
        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        priv_key = MockPrivateKey(private_bytes, "Ed25519")
        pub_key = priv_key.get_public_key()
        
        logger.warning("Using custom Ed25519 key generation due to missing libp2p functions")
        return MockKeyPair(priv_key, pub_key)
        
    elif key_type == "Secp256k1" or key_type == 2:
        # A simplified implementation without actual Secp256k1
        # In a real implementation, you would use a proper Secp256k1 library
        import secrets
        private_bytes = secrets.token_bytes(32)
        
        # Create a deterministic "public key" from the private bytes
        public_bytes = hashlib.sha256(private_bytes).digest()
        
        priv_key = MockPrivateKey(private_bytes, "Secp256k1")
        pub_key = MockPublicKey(public_bytes, "Secp256k1")
        
        logger.warning("Using simplified Secp256k1 key generation due to missing libp2p functions")
        return MockKeyPair(priv_key, pub_key)
    
    raise ValueError(f"Unsupported key type: {key_type}")

def load_private_key(key_data: bytes) -> Any:
    """
    Load a private key from serialized data.
    
    This function provides a compatibility layer for loading private keys
    from serialized data across different libp2p versions.
    
    Args:
        key_data: The serialized key data
        
    Returns:
        A PrivateKey object or equivalent
    """
    if not HAS_KEYS:
        raise ImportError("libp2p.crypto.keys is not available")
        
    # Try using the deserialize_private_key function if available
    if HAS_SERIALIZATION:
        from libp2p.crypto.serialization import deserialize_private_key
        return deserialize_private_key(key_data)
        
    # If serialization module not available, try direct deserialization
    if hasattr(libp2p.crypto.keys.PrivateKey, "deserialize"):
        return libp2p.crypto.keys.PrivateKey.deserialize(key_data)
        
    # If we get here, we don't know how to load this key
    raise NotImplementedError(f"Don't know how to load private key with this version of libp2p")

def create_key_pair(private_key: Any, public_key: Optional[Any] = None) -> Any:
    """
    Create a KeyPair from private and optional public key.
    
    This function provides a compatibility layer for creating key pairs
    from existing keys across different libp2p versions.
    
    Args:
        private_key: The PrivateKey object
        public_key: Optional PublicKey object. If not provided, will be
                   derived from the private key
                   
    Returns:
        A KeyPair object or equivalent
    """
    if not HAS_KEYS:
        raise ImportError("libp2p.crypto.keys is not available")
        
    # Derive public key if not provided
    if public_key is None:
        if hasattr(private_key, "get_public_key"):
            public_key = private_key.get_public_key()
        else:
            raise ValueError("Cannot derive public key from private key")
            
    # Create KeyPair
    return libp2p.crypto.keys.KeyPair(private_key, public_key)