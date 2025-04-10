"""
Noise Protocol Framework implementation for libp2p secure transport.

This module provides an implementation of the Noise Protocol Framework for libp2p,
offering a modern, secure alternative to existing security transports. It implements
the XX handshake pattern, which provides mutual authentication and is well-suited
for peer-to-peer communications.

References:
- Noise Protocol Framework: http://noiseprotocol.org/
- libp2p Noise spec: https://github.com/libp2p/specs/tree/master/noise

Requirements:
- cryptography: For cryptographic operations
"""

import os
import hashlib
import logging
from typing import Dict, List, Optional, Tuple, Union, Any

try:
    from cryptography.hazmat.primitives.asymmetric import x25519
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    ChaCha20Poly1305 = None

# Protocol ID for Noise in libp2p
PROTOCOL_ID = "/noise"

class NoiseError(Exception):
    """Base exception for Noise protocol errors."""
    pass

class HandshakeError(NoiseError):
    """Error during Noise handshake."""
    pass

class DecryptionError(NoiseError):
    """Error during decryption."""
    pass

class NoiseState:
    """
    State management for Noise Protocol sessions.
    
    This class handles the Noise Protocol state machine, including key derivation,
    encryption/decryption, and handshake message processing.
    """
    
    def __init__(self, name="Noise_XX_25519_ChaChaPoly_SHA256", prologue=b"libp2p"):
        """
        Initialize the Noise state.
        
        Args:
            name: Noise protocol name (handshake pattern, DH, cipher, hash)
            prologue: Protocol-specific prologue data
        """
        if not HAS_CRYPTO:
            raise ImportError("Noise protocol requires the 'cryptography' package")
            
        self.logger = logging.getLogger("NoiseState")
        
        # Parse protocol name
        parts = name.split("_")
        if len(parts) != 4 or parts[0] != "Noise":
            raise ValueError(f"Invalid Noise protocol name: {name}")
            
        self.pattern = parts[1]  # XX
        self.dh = parts[2]       # 25519
        self.cipher = parts[3]   # ChaChaPoly
        self.hash = "SHA256"     # Always SHA256 for now
        
        # Verify supported algorithms
        if self.pattern != "XX":
            raise ValueError(f"Unsupported handshake pattern: {self.pattern}")
        if self.dh != "25519":
            raise ValueError(f"Unsupported DH curve: {self.dh}")
        if self.cipher != "ChaChaPoly":
            raise ValueError(f"Unsupported cipher: {self.cipher}")
            
        # Initialize state variables
        self.handshake_hash = hashlib.sha256(prologue).digest()
        self.chaining_key = hashlib.sha256(f"Noise_{self.pattern}_{self.dh}_{self.cipher}_{self.hash}".encode()).digest()
        
        # Symmetric keys
        self.sending_key = None
        self.receiving_key = None
        
        # Handshake state
        self.handshake_complete = False
        
        # Nonces for sending/receiving after handshake
        self.sending_nonce = 0
        self.receiving_nonce = 0
        
    def mix_hash(self, data):
        """
        Update the handshake hash with new data.
        
        Args:
            data: Data to mix into the hash
        """
        self.handshake_hash = hashlib.sha256(self.handshake_hash + data).digest()
        
    def mix_key(self, input_key_material):
        """
        Derive new keys from input key material.
        
        Args:
            input_key_material: Key material to mix in
        """
        # Derive new chaining key and output key material
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=64,
            salt=self.chaining_key,
            info=b"",
        )
        output = hkdf.derive(input_key_material)
        
        self.chaining_key = output[:32]
        temp_key = output[32:]
        
        return temp_key
        
    def encrypt_and_hash(self, plaintext, associated_data=None):
        """
        Encrypt data and update the handshake hash.
        
        Args:
            plaintext: Data to encrypt
            associated_data: Additional authenticated data
            
        Returns:
            Encrypted data
        """
        if not self.sending_key:
            # Special case for early handshake messages
            self.mix_hash(plaintext)
            return plaintext
            
        # Create nonce
        nonce = self.sending_nonce.to_bytes(12, 'little')
        self.sending_nonce += 1
        
        # Encrypt using ChaCha20Poly1305
        cipher = ChaCha20Poly1305(self.sending_key)
        ciphertext = cipher.encrypt(nonce, plaintext, associated_data or self.handshake_hash)
        
        # Update handshake hash
        self.mix_hash(ciphertext)
        
        return ciphertext
        
    def decrypt_and_hash(self, ciphertext, associated_data=None):
        """
        Decrypt data and update the handshake hash.
        
        Args:
            ciphertext: Data to decrypt
            associated_data: Additional authenticated data
            
        Returns:
            Decrypted data
        """
        if not self.receiving_key:
            # Special case for early handshake messages
            self.mix_hash(ciphertext)
            return ciphertext
            
        # Create nonce
        nonce = self.receiving_nonce.to_bytes(12, 'little')
        self.receiving_nonce += 1
        
        # Decrypt using ChaCha20Poly1305
        cipher = ChaCha20Poly1305(self.receiving_key)
        try:
            plaintext = cipher.decrypt(nonce, ciphertext, associated_data or self.handshake_hash)
        except Exception as e:
            raise DecryptionError(f"Failed to decrypt message: {e}")
            
        # Update handshake hash
        self.mix_hash(ciphertext)
        
        return plaintext
        
    def split(self):
        """
        Split the symmetric state to create transport keys.
        
        Returns:
            Tuple of (sending_key, receiving_key)
        """
        # Derive encryption keys for bidirectional communication
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=64,
            salt=self.chaining_key,
            info=b"",
        )
        output = hkdf.derive(b"")
        
        self.sending_key = output[:32]
        self.receiving_key = output[32:]
        
        # Reset nonces
        self.sending_nonce = 0
        self.receiving_nonce = 0
        
        return (self.sending_key, self.receiving_key)

class NoiseProtocol:
    """
    Noise Protocol Framework implementation for libp2p.
    
    This class implements the XX handshake pattern, which provides mutual
    authentication between parties without requiring them to have prior
    knowledge of each other's static public keys.
    """
    
    PROTOCOL_ID = "/noise/1.0.0"
    
    def __init__(self, private_key=None):
        """
        Initialize Noise protocol with optional private key.
        
        Args:
            private_key: Optional X25519 private key for the local node
        """
        if not HAS_CRYPTO:
            raise ImportError("Noise protocol requires the 'cryptography' package")
            
        self.logger = logging.getLogger("NoiseProtocol")
        
        # Generate or use provided keys
        if private_key:
            if not isinstance(private_key, x25519.X25519PrivateKey):
                raise TypeError("private_key must be an X25519PrivateKey instance")
            self.private_key = private_key
        else:
            self.private_key = x25519.X25519PrivateKey.generate()
            
        self.public_key = self.private_key.public_key()
        
        # Ephemeral key for handshakes
        self.ephemeral_private = None
        self.ephemeral_public = None
        
        # Session tracking
        self.sessions = {}
        
    def _generate_ephemeral_keypair(self):
        """
        Generate a new ephemeral key pair for handshake.
        
        Returns:
            Tuple of (private_key, public_key_bytes)
        """
        private = x25519.X25519PrivateKey.generate()
        public = private.public_key()
        public_bytes = public.public_bytes_raw()
        
        return private, public_bytes
        
    async def handshake_initiator(self, remote_pubkey_bytes, stream):
        """
        Perform handshake as the initiator.
        
        Args:
            remote_pubkey_bytes: Remote peer's static public key bytes
            stream: Stream to perform handshake over
            
        Returns:
            NoiseState for the established secure session
        """
        # Create state
        state = NoiseState()
        
        # Generate ephemeral keypair
        self.ephemeral_private, ephemeral_public_bytes = self._generate_ephemeral_keypair()
        
        # -> e
        # Send initiator's ephemeral public key
        msg1 = state.encrypt_and_hash(ephemeral_public_bytes)
        await stream.write(msg1)
        
        # <- e, ee, s, es
        # Receive responder's ephemeral public key, encrypted static public key
        resp = await stream.read(256)  # Reasonable max size for handshake message
        if not resp:
            raise HandshakeError("No response received from remote peer")
            
        # Process responder's ephemeral key
        e_bytes = state.decrypt_and_hash(resp[:32])
        remote_ephemeral = x25519.X25519PublicKey.from_public_bytes(e_bytes)
        
        # DH operation: ee
        shared_secret = self.ephemeral_private.exchange(remote_ephemeral)
        state.mix_key(shared_secret)
        
        # Process responder's static key
        s_bytes = state.decrypt_and_hash(resp[32:])
        remote_static = x25519.X25519PublicKey.from_public_bytes(s_bytes)
        
        # Verify that the received static key matches the expected one
        if s_bytes != remote_pubkey_bytes:
            raise HandshakeError("Remote static key does not match expected key")
            
        # DH operation: es
        static_shared = self.ephemeral_private.exchange(remote_static)
        state.mix_key(static_shared)
        
        # -> s, se
        # Send initiator's static public key
        static_public_bytes = self.public_key.public_bytes_raw()
        enc_static = state.encrypt_and_hash(static_public_bytes)
        
        # DH operation: se
        remote_ephemeral_key = x25519.X25519PublicKey.from_public_bytes(e_bytes)
        se_shared = self.private_key.exchange(remote_ephemeral_key)
        state.mix_key(se_shared)
        
        # Send encrypted static key
        await stream.write(enc_static)
        
        # Split into transport keys
        state.split()
        state.handshake_complete = True
        
        return state
        
    async def handshake_responder(self, stream):
        """
        Perform handshake as the responder.
        
        Args:
            stream: Stream to perform handshake over
            
        Returns:
            Tuple of (NoiseState, remote_public_key_bytes)
        """
        # Create state
        state = NoiseState()
        
        # Generate ephemeral keypair
        self.ephemeral_private, ephemeral_public_bytes = self._generate_ephemeral_keypair()
        
        # <- e
        # Receive initiator's ephemeral public key
        e_bytes = await stream.read(32)
        if not e_bytes or len(e_bytes) != 32:
            raise HandshakeError("Invalid ephemeral key from initiator")
            
        # Process initiator's ephemeral key
        state.decrypt_and_hash(e_bytes)
        remote_ephemeral = x25519.X25519PublicKey.from_public_bytes(e_bytes)
        
        # -> e, ee, s, es
        # Send responder's ephemeral public key
        await stream.write(state.encrypt_and_hash(ephemeral_public_bytes))
        
        # DH operation: ee
        shared_secret = self.ephemeral_private.exchange(remote_ephemeral)
        state.mix_key(shared_secret)
        
        # Send responder's static public key
        static_public_bytes = self.public_key.public_bytes_raw()
        await stream.write(state.encrypt_and_hash(static_public_bytes))
        
        # DH operation: es
        es_shared = self.private_key.exchange(remote_ephemeral)
        state.mix_key(es_shared)
        
        # <- s, se
        # Receive initiator's encrypted static public key
        enc_static = await stream.read(48)  # 32 bytes key + 16 bytes MAC
        if not enc_static:
            raise HandshakeError("No static key received from initiator")
            
        # Decrypt initiator's static key
        remote_static_bytes = state.decrypt_and_hash(enc_static)
        remote_static = x25519.X25519PublicKey.from_public_bytes(remote_static_bytes)
        
        # DH operation: se
        se_shared = self.ephemeral_private.exchange(remote_static)
        state.mix_key(se_shared)
        
        # Split into transport keys
        state.split()
        state.handshake_complete = True
        
        return state, remote_static_bytes
        
    def encrypt(self, state, data, associated_data=None):
        """
        Encrypt data using established session keys.
        
        Args:
            state: NoiseState from a completed handshake
            data: Data to encrypt
            associated_data: Additional authenticated data
            
        Returns:
            Encrypted data
        """
        if not state.handshake_complete:
            raise NoiseError("Cannot encrypt before handshake is complete")
            
        return state.encrypt_and_hash(data, associated_data)
        
    def decrypt(self, state, data, associated_data=None):
        """
        Decrypt data using established session keys.
        
        Args:
            state: NoiseState from a completed handshake
            data: Data to decrypt
            associated_data: Additional authenticated data
            
        Returns:
            Decrypted data
        """
        if not state.handshake_complete:
            raise NoiseError("Cannot decrypt before handshake is complete")
            
        return state.decrypt_and_hash(data, associated_data)
        
    def create_private_key(self):
        """
        Create a new X25519 private key.
        
        Returns:
            X25519PrivateKey
        """
        return x25519.X25519PrivateKey.generate()
        
    def private_key_to_bytes(self, private_key):
        """
        Convert a private key to bytes.
        
        Args:
            private_key: X25519PrivateKey
            
        Returns:
            Private key bytes
        """
        return private_key.private_bytes_raw()
        
    def public_key_to_bytes(self, public_key):
        """
        Convert a public key to bytes.
        
        Args:
            public_key: X25519PublicKey
            
        Returns:
            Public key bytes
        """
        return public_key.public_bytes_raw()
        
    def private_key_from_bytes(self, key_bytes):
        """
        Load a private key from bytes.
        
        Args:
            key_bytes: Private key bytes
            
        Returns:
            X25519PrivateKey
        """
        return x25519.X25519PrivateKey.from_private_bytes(key_bytes)
        
    def public_key_from_bytes(self, key_bytes):
        """
        Load a public key from bytes.
        
        Args:
            key_bytes: Public key bytes
            
        Returns:
            X25519PublicKey
        """
        return x25519.X25519PublicKey.from_public_bytes(key_bytes)

# Utility function to check if Noise protocol is available
def is_noise_available():
    """Check if Noise protocol support is available."""
    return HAS_CRYPTO