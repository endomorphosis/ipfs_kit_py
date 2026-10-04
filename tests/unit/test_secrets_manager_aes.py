#!/usr/bin/env python3
"""
Unit tests for enhanced secrets manager with AES-256-GCM encryption.
"""

import os
import tempfile
import shutil
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ipfs_kit_py.enhanced_secrets_manager import (
    EnhancedSecretManager,
    SecretType,
    AES_ENCRYPTION_AVAILABLE,
)


@unittest.skipUnless(AES_ENCRYPTION_AVAILABLE, "AES encryption not available")
class TestEnhancedSecretManagerAES(unittest.TestCase):
    """Test enhanced secrets manager with AES encryption."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.test_dir, "secrets")
        self.audit_log_path = os.path.join(self.test_dir, "audit.log")
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_aes_encryption_default(self):
        """Test that AES encryption is used by default."""
        manager = EnhancedSecretManager(
            storage_path=self.storage_path,
            audit_log_path=self.audit_log_path,
        )
        
        # Should use AES encryption
        self.assertEqual(manager.encryption_method, "aes-gcm")
        self.assertIsNotNone(manager.encryptor)
        
        # Get statistics
        stats = manager.get_statistics()
        self.assertEqual(stats['encryption_method'], 'aes-gcm')
        self.assertTrue(stats['aes_available'])
    
    def test_store_and_retrieve_with_aes(self):
        """Test storing and retrieving secrets with AES."""
        manager = EnhancedSecretManager(
            storage_path=self.storage_path,
            audit_log_path=self.audit_log_path,
        )
        
        # Store a secret (at least 10 chars for API key validation)
        secret_id = manager.store_secret(
            service="test_service",
            secret_value="my-secret-api-key-12345",
            secret_type=SecretType.API_KEY,
        )
        
        # Retrieve the secret
        retrieved = manager.retrieve_secret(secret_id)
        self.assertEqual(retrieved, "my-secret-api-key-12345")
        
        # Check encryption info
        enc_info = manager.get_encryption_info(secret_id)
        self.assertEqual(enc_info['encryption_version'], 'v2')
        self.assertTrue(enc_info['is_aes_encrypted'])
        self.assertFalse(enc_info['needs_migration'])
    
    def test_aes_encrypted_format(self):
        """Test that secrets are encrypted in AES format."""
        manager = EnhancedSecretManager(
            storage_path=self.storage_path,
            audit_log_path=self.audit_log_path,
        )
        
        secret_id = manager.store_secret(
            service="test",
            secret_value="secret1234567890",  # At least 10 chars for validation
            secret_type=SecretType.API_KEY,
        )
        
        # Check stored format
        encrypted_value = manager.secrets[secret_id]
        
        # Should have v2 prefix (AES-256-GCM)
        self.assertTrue(encrypted_value.startswith('v2:'))
        
        # Should have 4 parts (version:salt:nonce:ciphertext)
        parts = encrypted_value.split(':')
        self.assertEqual(len(parts), 4)
    
    def test_persistence_with_aes(self):
        """Test that AES-encrypted secrets persist correctly."""
        # Create manager and store secret
        manager1 = EnhancedSecretManager(
            storage_path=self.storage_path,
            audit_log_path=self.audit_log_path,
        )
        
        secret_id = manager1.store_secret(
            service="persistent_service",
            secret_value="persistent-secret-123456",  # At least 10 chars
            secret_type=SecretType.TOKEN,  # Token accepts longer strings
        )
        
        # Create new manager instance (simulates restart)
        manager2 = EnhancedSecretManager(
            storage_path=self.storage_path,
            audit_log_path=self.audit_log_path,
        )
        
        # Should be able to retrieve secret
        retrieved = manager2.retrieve_secret(secret_id)
        self.assertEqual(retrieved, "persistent-secret-123456")
    
    def test_multiple_secrets_different_ciphertexts(self):
        """Test that same plaintext produces different ciphertexts."""
        manager = EnhancedSecretManager(
            storage_path=self.storage_path,
            audit_log_path=self.audit_log_path,
        )
        
        # Store same secret value twice (at least 20 chars for token validation)
        secret1_id = manager.store_secret(
            service="service1",
            secret_value="same-value-1234567890",
            secret_type=SecretType.TOKEN,
        )
        
        secret2_id = manager.store_secret(
            service="service2",
            secret_value="same-value-1234567890",
            secret_type=SecretType.TOKEN,
        )
        
        # Encrypted values should be different
        encrypted1 = manager.secrets[secret1_id]
        encrypted2 = manager.secrets[secret2_id]
        self.assertNotEqual(encrypted1, encrypted2)
        
        # But both should decrypt to same value
        self.assertEqual(manager.retrieve_secret(secret1_id), "same-value-1234567890")
        self.assertEqual(manager.retrieve_secret(secret2_id), "same-value-1234567890")


@unittest.skipUnless(AES_ENCRYPTION_AVAILABLE, "AES encryption not available")
class TestSecretMigration(unittest.TestCase):
    """Test migration from XOR to AES encryption."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.test_dir, "secrets")
        self.audit_log_path = os.path.join(self.test_dir, "audit.log")
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_read_legacy_xor_secrets(self):
        """Test reading secrets encrypted with legacy XOR."""
        # Create manager with XOR encryption
        manager_xor = EnhancedSecretManager(
            storage_path=self.storage_path,
            audit_log_path=self.audit_log_path,
            encryption_method="xor",
        )
        
        # Store secret with XOR (at least 20 chars for token)
        secret_id = manager_xor.store_secret(
            service="legacy_service",
            secret_value="legacy-secret-1234567890",
            secret_type=SecretType.TOKEN,
        )
        
        # Create new manager with AES (default)
        manager_aes = EnhancedSecretManager(
            storage_path=self.storage_path,
            audit_log_path=self.audit_log_path,
        )
        
        # Should be able to read legacy secret
        retrieved = manager_aes.retrieve_secret(secret_id)
        self.assertEqual(retrieved, "legacy-secret-1234567890")
        
        # Check encryption info
        enc_info = manager_aes.get_encryption_info(secret_id)
        self.assertEqual(enc_info['encryption_version'], 'v1')
        self.assertFalse(enc_info['is_aes_encrypted'])
        self.assertTrue(enc_info['needs_migration'])
    
    def test_migrate_all_secrets(self):
        """Test migrating all secrets from XOR to AES."""
        # Create manager with XOR and store secrets
        manager_xor = EnhancedSecretManager(
            storage_path=self.storage_path,
            audit_log_path=self.audit_log_path,
            encryption_method="xor",
        )
        
        secret_ids = []
        for i in range(3):
            sid = manager_xor.store_secret(
                service=f"service{i}",
                secret_value=f"secret{i}-12345678901",  # At least 20 chars for TOKEN
                secret_type=SecretType.TOKEN,
            )
            secret_ids.append(sid)
        
        # Create new manager with AES
        manager_aes = EnhancedSecretManager(
            storage_path=self.storage_path,
            audit_log_path=self.audit_log_path,
        )
        
        # Check stats before migration
        stats_before = manager_aes.get_statistics()
        self.assertEqual(stats_before['encryption_versions']['v1'], 3)
        
        # Migrate all secrets
        migration_result = manager_aes.migrate_all_secrets()
        
        # Check migration results
        self.assertEqual(migration_result['migrated'], 3)
        self.assertEqual(migration_result['already_current'], 0)
        self.assertEqual(len(migration_result['errors']), 0)
        
        # Check stats after migration
        stats_after = manager_aes.get_statistics()
        self.assertEqual(stats_after['encryption_versions'].get('v2', 0), 3)
        self.assertEqual(stats_after['encryption_versions'].get('v1', 0), 0)
        
        # Verify all secrets are still retrievable
        for i, secret_id in enumerate(secret_ids):
            retrieved = manager_aes.retrieve_secret(secret_id)
            self.assertEqual(retrieved, f"secret{i}-12345678901")
            
            # Check encryption info
            enc_info = manager_aes.get_encryption_info(secret_id)
            self.assertEqual(enc_info['encryption_version'], 'v2')
            self.assertTrue(enc_info['is_aes_encrypted'])
            self.assertFalse(enc_info['needs_migration'])
    
    def test_migration_persistence(self):
        """Test that migrated secrets persist correctly."""
        # Create XOR-encrypted secret
        manager1 = EnhancedSecretManager(
            storage_path=self.storage_path,
            audit_log_path=self.audit_log_path,
            encryption_method="xor",
        )
        
        secret_id = manager1.store_secret(
            service="migrate_test",
            secret_value="secret-to-migrate-123456",  # At least 20 chars
            secret_type=SecretType.TOKEN,
        )
        
        # Migrate with AES manager
        manager2 = EnhancedSecretManager(
            storage_path=self.storage_path,
            audit_log_path=self.audit_log_path,
        )
        
        manager2.migrate_all_secrets()
        
        # Create new manager instance (simulates restart)
        manager3 = EnhancedSecretManager(
            storage_path=self.storage_path,
            audit_log_path=self.audit_log_path,
        )
        
        # Should retrieve migrated secret
        retrieved = manager3.retrieve_secret(secret_id)
        self.assertEqual(retrieved, "secret-to-migrate-123456")
        
        # Should be in AES format
        enc_info = manager3.get_encryption_info(secret_id)
        self.assertEqual(enc_info['encryption_version'], 'v2')
    
    def test_mixed_encryption_versions(self):
        """Test handling secrets with mixed encryption versions."""
        # Create manager with XOR
        manager_xor = EnhancedSecretManager(
            storage_path=self.storage_path,
            audit_log_path=self.audit_log_path,
            encryption_method="xor",
        )
        
        xor_secret_id = manager_xor.store_secret(
            service="xor_service",
            secret_value="xor-secret-1234567890",  # At least 20 chars
            secret_type=SecretType.TOKEN,
        )
        
        # Switch to AES manager
        manager_aes = EnhancedSecretManager(
            storage_path=self.storage_path,
            audit_log_path=self.audit_log_path,
        )
        
        # Add new AES-encrypted secret
        aes_secret_id = manager_aes.store_secret(
            service="aes_service",
            secret_value="aes-secret-1234567890",  # At least 20 chars
            secret_type=SecretType.TOKEN,
        )
        
        # Should be able to retrieve both
        self.assertEqual(manager_aes.retrieve_secret(xor_secret_id), "xor-secret-1234567890")
        self.assertEqual(manager_aes.retrieve_secret(aes_secret_id), "aes-secret-1234567890")
        
        # Check statistics
        stats = manager_aes.get_statistics()
        self.assertEqual(stats['encryption_versions']['v1'], 1)  # XOR
        self.assertEqual(stats['encryption_versions']['v2'], 1)  # AES


if __name__ == '__main__':
    unittest.main()
