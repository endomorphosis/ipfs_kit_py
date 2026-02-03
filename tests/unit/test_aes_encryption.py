#!/usr/bin/env python3
"""
Unit tests for AES-256-GCM encryption.
"""

import os
import unittest
import base64
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ipfs_kit_py.aes_encryption import (
    AESEncryption,
    LegacyXORDecryptor,
    MultiVersionEncryption,
    EncryptedData,
    create_encryption_handler,
    CRYPTOGRAPHY_AVAILABLE,
)


@unittest.skipUnless(CRYPTOGRAPHY_AVAILABLE, "cryptography library not available")
class TestAESEncryption(unittest.TestCase):
    """Test AES-256-GCM encryption functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.master_key = b"test-master-key-32-bytes-long!!"
        self.aes = AESEncryption(self.master_key)
    
    def test_initialization(self):
        """Test AES encryption initialization."""
        self.assertEqual(self.aes.VERSION, "v2")
        self.assertEqual(self.aes.SALT_SIZE, 16)
        self.assertEqual(self.aes.NONCE_SIZE, 12)
        self.assertEqual(self.aes.KEY_SIZE, 32)
    
    def test_master_key_validation(self):
        """Test master key validation."""
        # Too short key should fail
        with self.assertRaises(ValueError):
            AESEncryption(b"short")
        
        # Minimum length should work
        aes = AESEncryption(b"16-byte-key!!!!!")
        self.assertIsNotNone(aes)
    
    def test_encrypt_decrypt(self):
        """Test basic encryption and decryption."""
        plaintext = "secret data to encrypt"
        
        # Encrypt
        encrypted = self.aes.encrypt(plaintext)
        
        # Should have version prefix
        self.assertTrue(encrypted.startswith('v2:'))
        
        # Should have 4 parts (version:salt:nonce:ciphertext)
        parts = encrypted.split(':')
        self.assertEqual(len(parts), 4)
        
        # Decrypt
        decrypted = self.aes.decrypt(encrypted)
        self.assertEqual(decrypted, plaintext)
    
    def test_different_ciphertexts(self):
        """Test that same plaintext produces different ciphertexts."""
        plaintext = "same data"
        
        encrypted1 = self.aes.encrypt(plaintext)
        encrypted2 = self.aes.encrypt(plaintext)
        
        # Ciphertexts should be different (different salt and nonce)
        self.assertNotEqual(encrypted1, encrypted2)
        
        # But both should decrypt to same plaintext
        self.assertEqual(self.aes.decrypt(encrypted1), plaintext)
        self.assertEqual(self.aes.decrypt(encrypted2), plaintext)
    
    def test_various_plaintexts(self):
        """Test encryption with various types of data."""
        test_cases = [
            "",  # Empty string
            "a",  # Single character
            "short text",  # Short text
            "x" * 1000,  # Long text
            "unicode: 你好世界 🎉",  # Unicode
            "special chars: \n\t\r",  # Special characters
            '{"json": "data", "number": 123}',  # JSON-like
        ]
        
        for plaintext in test_cases:
            with self.subTest(plaintext=plaintext[:50]):
                encrypted = self.aes.encrypt(plaintext)
                decrypted = self.aes.decrypt(encrypted)
                self.assertEqual(decrypted, plaintext)
    
    def test_wrong_key_fails(self):
        """Test that wrong key fails decryption."""
        plaintext = "secret data"
        
        # Encrypt with one key
        encrypted = self.aes.encrypt(plaintext)
        
        # Try to decrypt with different key
        wrong_key_aes = AESEncryption(b"wrong-master-key-32-bytes-long!")
        
        with self.assertRaises(Exception) as context:
            wrong_key_aes.decrypt(encrypted)
        
        self.assertIn("Decryption failed", str(context.exception))
    
    def test_corrupted_data_fails(self):
        """Test that corrupted data fails decryption."""
        plaintext = "secret data"
        encrypted = self.aes.encrypt(plaintext)
        
        # Corrupt the ciphertext part
        parts = encrypted.split(':')
        parts[3] = base64.b64encode(b"corrupted").decode('utf-8')
        corrupted = ':'.join(parts)
        
        with self.assertRaises(Exception):
            self.aes.decrypt(corrupted)
    
    def test_invalid_format_fails(self):
        """Test that invalid format fails decryption."""
        invalid_formats = [
            "not:encrypted",  # Too few parts
            "v2:only:three",  # Too few parts
            "v2:invalid:base64:data:extra",  # Too many parts
            "v2:!!!:!!!:!!!",  # Invalid base64
        ]
        
        for invalid in invalid_formats:
            with self.subTest(invalid=invalid):
                with self.assertRaises((ValueError, Exception)):
                    self.aes.decrypt(invalid)
    
    def test_is_encrypted(self):
        """Test encryption detection."""
        plaintext = "test data"
        encrypted = self.aes.encrypt(plaintext)
        
        # Should detect encrypted data
        self.assertTrue(self.aes.is_encrypted(encrypted))
        
        # Should not detect plaintext
        self.assertFalse(self.aes.is_encrypted(plaintext))
        self.assertFalse(self.aes.is_encrypted("v1:data"))
        self.assertFalse(self.aes.is_encrypted("random string"))


class TestEncryptedData(unittest.TestCase):
    """Test EncryptedData serialization."""
    
    def test_serialize_deserialize(self):
        """Test serialization and deserialization."""
        original = EncryptedData(
            version="v2",
            salt=b"16bytesalt123456",
            nonce=b"12bytesnonce",
            ciphertext=b"encrypted data here",
        )
        
        # Serialize
        serialized = original.serialize()
        
        # Should have 4 parts
        parts = serialized.split(':')
        self.assertEqual(len(parts), 4)
        self.assertEqual(parts[0], "v2")
        
        # Deserialize
        deserialized = EncryptedData.deserialize(serialized)
        
        # Should match original
        self.assertEqual(deserialized.version, original.version)
        self.assertEqual(deserialized.salt, original.salt)
        self.assertEqual(deserialized.nonce, original.nonce)
        self.assertEqual(deserialized.ciphertext, original.ciphertext)
    
    def test_invalid_deserialize(self):
        """Test deserialization with invalid data."""
        invalid_cases = [
            "only:two",  # Too few parts
            "v2:too:many:parts:here",  # Too many parts
            "v2:invalid:base64:!!!",  # Invalid base64
        ]
        
        for invalid in invalid_cases:
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    EncryptedData.deserialize(invalid)


class TestLegacyXORDecryptor(unittest.TestCase):
    """Test legacy XOR decryption."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.key = b"xor-key-for-testing-legacy-compat"
        self.xor = LegacyXORDecryptor(self.key)
    
    def test_decrypt_xor(self):
        """Test XOR decryption."""
        # Create XOR-encrypted data (same as old implementation)
        plaintext = "legacy secret"
        plaintext_bytes = plaintext.encode()
        
        encrypted = bytearray()
        for i, byte in enumerate(plaintext_bytes):
            encrypted.append(byte ^ self.key[i % len(self.key)])
        
        encrypted_b64 = base64.b64encode(bytes(encrypted)).decode()
        
        # Decrypt
        decrypted = self.xor.decrypt(encrypted_b64)
        self.assertEqual(decrypted, plaintext)
    
    def test_is_encrypted(self):
        """Test XOR encryption detection."""
        # Legacy format has no version prefix
        self.assertTrue(self.xor.is_encrypted("base64data"))
        self.assertTrue(self.xor.is_encrypted("YWJjZGVm"))
        
        # New format has version prefix
        self.assertFalse(self.xor.is_encrypted("v2:data"))
        self.assertFalse(self.xor.is_encrypted("v1:data"))


@unittest.skipUnless(CRYPTOGRAPHY_AVAILABLE, "cryptography library not available")
class TestMultiVersionEncryption(unittest.TestCase):
    """Test multi-version encryption handler."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.master_key = b"multi-version-key-32-bytes-lng!!"
        self.multi = MultiVersionEncryption(self.master_key)
    
    def test_initialization(self):
        """Test initialization."""
        self.assertIsNotNone(self.multi.aes)
        self.assertIsNotNone(self.multi.xor)
    
    def test_encrypt_uses_latest(self):
        """Test that encrypt always uses latest version."""
        plaintext = "test data"
        encrypted = self.multi.encrypt(plaintext)
        
        # Should use AES (v2)
        self.assertTrue(encrypted.startswith('v2:'))
        
        # Should be able to decrypt
        decrypted = self.multi.decrypt(encrypted)
        self.assertEqual(decrypted, plaintext)
    
    def test_decrypt_aes(self):
        """Test decrypting AES-encrypted data."""
        plaintext = "aes encrypted data"
        
        # Encrypt with AES directly
        encrypted = self.multi.aes.encrypt(plaintext)
        
        # Should decrypt via multi-version
        decrypted = self.multi.decrypt(encrypted)
        self.assertEqual(decrypted, plaintext)
    
    def test_decrypt_legacy_xor(self):
        """Test decrypting legacy XOR data."""
        plaintext = "legacy data"
        plaintext_bytes = plaintext.encode()
        
        # Create legacy XOR-encrypted data
        encrypted_bytes = bytearray()
        for i, byte in enumerate(plaintext_bytes):
            encrypted_bytes.append(byte ^ self.master_key[i % len(self.master_key)])
        
        encrypted = base64.b64encode(bytes(encrypted_bytes)).decode()
        
        # Should decrypt via multi-version
        decrypted = self.multi.decrypt(encrypted)
        self.assertEqual(decrypted, plaintext)
    
    def test_get_version(self):
        """Test version detection."""
        # AES encrypted
        aes_encrypted = self.multi.encrypt("test")
        self.assertEqual(self.multi.get_version(aes_encrypted), "v2")
        
        # Legacy XOR (no version prefix)
        xor_encrypted = base64.b64encode(b"data").decode()
        self.assertEqual(self.multi.get_version(xor_encrypted), "v1")
        
        # Unknown
        self.assertEqual(self.multi.get_version("v99:data"), "unknown")
    
    def test_needs_migration(self):
        """Test migration detection."""
        # New AES data doesn't need migration
        aes_encrypted = self.multi.encrypt("test")
        self.assertFalse(self.multi.needs_migration(aes_encrypted))
        
        # Legacy XOR data needs migration
        xor_encrypted = base64.b64encode(b"test").decode()
        self.assertTrue(self.multi.needs_migration(xor_encrypted))
    
    def test_migrate(self):
        """Test migration from XOR to AES."""
        plaintext = "data to migrate"
        plaintext_bytes = plaintext.encode()
        
        # Create legacy XOR-encrypted data
        encrypted_bytes = bytearray()
        for i, byte in enumerate(plaintext_bytes):
            encrypted_bytes.append(byte ^ self.master_key[i % len(self.master_key)])
        
        xor_encrypted = base64.b64encode(bytes(encrypted_bytes)).decode()
        
        # Migrate to AES
        aes_encrypted = self.multi.migrate(xor_encrypted)
        
        # Should be in new format
        self.assertTrue(aes_encrypted.startswith('v2:'))
        
        # Should decrypt to same plaintext
        decrypted = self.multi.decrypt(aes_encrypted)
        self.assertEqual(decrypted, plaintext)
        
        # Should not need migration anymore
        self.assertFalse(self.multi.needs_migration(aes_encrypted))


@unittest.skipUnless(CRYPTOGRAPHY_AVAILABLE, "cryptography library not available")
class TestCreateEncryptionHandler(unittest.TestCase):
    """Test factory function."""
    
    def test_create_with_key(self):
        """Test creating handler with explicit key."""
        key = b"explicit-key-32-bytes-long!!!!!"
        handler = create_encryption_handler(master_key=key)
        
        self.assertIsInstance(handler, MultiVersionEncryption)
        
        # Should work for encryption/decryption
        plaintext = "test"
        encrypted = handler.encrypt(plaintext)
        decrypted = handler.decrypt(encrypted)
        self.assertEqual(decrypted, plaintext)
    
    def test_create_with_auto_key(self):
        """Test creating handler with auto-generated key."""
        handler = create_encryption_handler()
        
        self.assertIsInstance(handler, MultiVersionEncryption)
        
        # Should work for encryption/decryption
        plaintext = "test"
        encrypted = handler.encrypt(plaintext)
        decrypted = handler.decrypt(encrypted)
        self.assertEqual(decrypted, plaintext)
    
    def test_invalid_encryption_method(self):
        """Test invalid encryption method."""
        with self.assertRaises(ValueError):
            create_encryption_handler(encryption_method="invalid")


if __name__ == '__main__':
    unittest.main()
