#!/usr/bin/env python3
"""
End-to-End Encryption Example for MCP Server

This example demonstrates how to use the encryption module to securely
encrypt data and files, manage encryption keys, and implement policies
for different types of content.

Key features demonstrated:
1. Key generation and management
2. Data encryption and decryption
3. File encryption and decryption
4. Policy-based encryption
5. Integration with storage backends

Usage:
  python encryption_example.py [--config CONFIG_PATH] [--storage-path STORAGE_PATH]
"""

import os
import json
import argparse
import logging
import tempfile
import uuid
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("encryption-example")

# Import encryption components
try:
    from ipfs_kit_py.mcp.enterprise.encryption import (
        KeyManager, EncryptionManager, BackendEncryptionHandler,
        EncryptionPolicy, EncryptionKey, EncryptedData,
        EncryptionAlgorithm, KeyType, KeyStorageType, EncryptionScope
    )
except ImportError:
    logger.error("Failed to import encryption modules. Make sure ipfs_kit_py is installed")
    import sys
    sys.exit(1)


def demonstrate_key_management(storage_path: str):
    """Demonstrate key management features."""
    logger.info("\n=== Key Management Demonstration ===\n")
    
    # Initialize key manager with file-based storage
    key_manager = KeyManager(
        storage_type=KeyStorageType.FILE,
        storage_path=storage_path
    )
    
    # Generate different types of keys
    logger.info("Generating encryption keys...")
    
    # 1. Generate a symmetric AES-256-GCM key
    aes_key = key_manager.generate_key(
        key_type=KeyType.SYMMETRIC,
        algorithm=EncryptionAlgorithm.AES_256_GCM,
        description="AES-256-GCM symmetric key for data encryption",
        expires_days=90,
        tags={"purpose": "data-encryption", "sensitivity": "high"}
    )
    logger.info(f"Generated AES-256-GCM key: {aes_key.id}")
    
    # 2. Generate an RSA key pair
    rsa_private_key = key_manager.generate_key(
        key_type=KeyType.ASYMMETRIC_PRIVATE,
        algorithm=EncryptionAlgorithm.RSA_OAEP,
        description="RSA-2048 private key for asymmetric encryption",
        expires_days=365,
        tags={"purpose": "asymmetric-encryption", "sensitivity": "very-high"}
    )
    logger.info(f"Generated RSA private key: {rsa_private_key.id}")
    
    rsa_public_key = key_manager.generate_key(
        key_type=KeyType.ASYMMETRIC_PUBLIC,
        algorithm=EncryptionAlgorithm.RSA_OAEP,
        description="RSA-2048 public key for asymmetric encryption",
        expires_days=365,
        tags={"purpose": "asymmetric-encryption", "sensitivity": "low"}
    )
    logger.info(f"Generated RSA public key: {rsa_public_key.id}")
    
    # 3. Generate a Fernet key
    fernet_key = key_manager.generate_key(
        key_type=KeyType.SYMMETRIC,
        algorithm=EncryptionAlgorithm.FERNET,
        description="Fernet key for simple encryption",
        expires_days=30,
        tags={"purpose": "simple-encryption", "sensitivity": "medium"}
    )
    logger.info(f"Generated Fernet key: {fernet_key.id}")
    
    # List all keys
    logger.info("\nListing all keys:")
    all_keys = key_manager.list_keys()
    for key in all_keys:
        logger.info(f"  - {key.id}: {key.algorithm}, {key.type}, expires: {key.expires_at or 'never'}")
    
    # Filter keys by type and algorithm
    logger.info("\nFiltering keys by type and algorithm:")
    symmetric_keys = key_manager.list_keys(key_type=KeyType.SYMMETRIC)
    logger.info(f"Found {len(symmetric_keys)} symmetric keys")
    
    aes_keys = key_manager.list_keys(algorithm=EncryptionAlgorithm.AES_256_GCM)
    logger.info(f"Found {len(aes_keys)} AES-256-GCM keys")
    
    # Filter keys by tags
    logger.info("\nFiltering keys by tags:")
    high_sensitivity_keys = key_manager.list_keys(tags={"sensitivity": "high"})
    logger.info(f"Found {len(high_sensitivity_keys)} high sensitivity keys")
    
    # Demonstrate key rotation
    logger.info("\nDemonstrating key rotation:")
    old_key, new_key = key_manager.rotate_key(fernet_key.id)
    logger.info(f"Rotated key {old_key.id} to {new_key.id}")
    
    # Delete a key
    logger.info("\nDemonstrating key deletion:")
    key_to_delete = symmetric_keys[0].id
    success = key_manager.delete_key(key_to_delete)
    logger.info(f"Deleted key {key_to_delete}: {success}")
    
    return key_manager


def demonstrate_encryption(key_manager: KeyManager):
    """Demonstrate encryption and decryption features."""
    logger.info("\n=== Encryption Demonstration ===\n")
    
    # Initialize encryption manager
    encryption_manager = EncryptionManager(key_manager)
    
    # Get a symmetric key for encryption
    symmetric_keys = key_manager.list_keys(
        key_type=KeyType.SYMMETRIC,
        algorithm=EncryptionAlgorithm.AES_256_GCM
    )
    
    if not symmetric_keys:
        logger.info("No symmetric AES keys found, generating one...")
        symmetric_key = key_manager.generate_key(
            key_type=KeyType.SYMMETRIC,
            algorithm=EncryptionAlgorithm.AES_256_GCM,
            description="AES-256-GCM symmetric key for data encryption"
        )
    else:
        symmetric_key = symmetric_keys[0]
    
    # Get an asymmetric key pair
    private_keys = key_manager.list_keys(
        key_type=KeyType.ASYMMETRIC_PRIVATE,
        algorithm=EncryptionAlgorithm.RSA_OAEP
    )
    
    public_keys = key_manager.list_keys(
        key_type=KeyType.ASYMMETRIC_PUBLIC,
        algorithm=EncryptionAlgorithm.RSA_OAEP
    )
    
    if not private_keys or not public_keys:
        logger.info("No RSA key pair found, generating one...")
        private_key = key_manager.generate_key(
            key_type=KeyType.ASYMMETRIC_PRIVATE,
            algorithm=EncryptionAlgorithm.RSA_OAEP,
            description="RSA-2048 private key for asymmetric encryption"
        )
        
        public_key = key_manager.generate_key(
            key_type=KeyType.ASYMMETRIC_PUBLIC,
            algorithm=EncryptionAlgorithm.RSA_OAEP,
            description="RSA-2048 public key for asymmetric encryption"
        )
    else:
        private_key = private_keys[0]
        public_key = public_keys[0]
    
    # 1. Symmetric encryption with AES-256-GCM
    logger.info("\nSymmetric encryption with AES-256-GCM:")
    sample_data = "This is a sample string to encrypt with AES-256-GCM.".encode('utf-8')
    
    encrypted_data = encryption_manager.encrypt(
        data=sample_data,
        key_id=symmetric_key.id,
        content_type="text/plain",
        metadata={"description": "Sample encrypted text"}
    )
    
    logger.info(f"Encrypted data ID: {encrypted_data.id}")
    logger.info(f"Algorithm: {encrypted_data.algorithm}")
    logger.info(f"Original size: {encrypted_data.original_size} bytes")
    logger.info(f"Encrypted size: {len(encrypted_data.encrypted_data)} bytes")
    
    # Decrypt the data
    decrypted_data = encryption_manager.decrypt(encrypted_data)
    logger.info(f"Decrypted data: {decrypted_data.decode('utf-8')}")
    assert decrypted_data == sample_data, "Decrypted data does not match original"
    
    # 2. Asymmetric encryption with RSA-OAEP
    logger.info("\nAsymmetric encryption with RSA-OAEP:")
    sample_data_2 = "This is a sample string to encrypt with RSA-OAEP.".encode('utf-8')
    
    encrypted_data_2 = encryption_manager.encrypt(
        data=sample_data_2,
        key_id=public_key.id,
        content_type="text/plain",
        metadata={"description": "Sample RSA encrypted text"}
    )
    
    logger.info(f"Encrypted data ID: {encrypted_data_2.id}")
    logger.info(f"Algorithm: {encrypted_data_2.algorithm}")
    logger.info(f"Original size: {encrypted_data_2.original_size} bytes")
    logger.info(f"Encrypted size: {len(encrypted_data_2.encrypted_data)} bytes")
    logger.info(f"Encrypted key: {encrypted_data_2.metadata.get('encrypted_key', 'None')[:20]}...")
    
    # Decrypt the data
    decrypted_data_2 = encryption_manager.decrypt(encrypted_data_2)
    logger.info(f"Decrypted data: {decrypted_data_2.decode('utf-8')}")
    assert decrypted_data_2 == sample_data_2, "Decrypted data does not match original"
    
    return encryption_manager


def demonstrate_encryption_policies(encryption_manager: EncryptionManager):
    """Demonstrate encryption policies."""
    logger.info("\n=== Encryption Policies Demonstration ===\n")
    
    # Create different policies for different content types
    logger.info("Creating encryption policies...")
    
    # 1. Default global policy for all content
    global_policy = EncryptionPolicy(
        id=str(uuid.uuid4()),
        name="Default Global Policy",
        description="Default policy for all content types",
        algorithm=EncryptionAlgorithm.AES_256_GCM,
        scope=EncryptionScope.GLOBAL,
        key_rotation_days=90
    )
    encryption_manager.add_policy(global_policy)
    logger.info(f"Added global policy: {global_policy.id}")
    
    # 2. Policy for image content
    image_policy = EncryptionPolicy(
        id=str(uuid.uuid4()),
        name="Image Content Policy",
        description="Policy for image content types",
        algorithm=EncryptionAlgorithm.CHACHA20_POLY1305,
        scope=EncryptionScope.CONTENT,
        content_types=["image/*"],
        key_rotation_days=180
    )
    encryption_manager.add_policy(image_policy)
    logger.info(f"Added image policy: {image_policy.id}")
    
    # 3. Policy for sensitive document content
    document_policy = EncryptionPolicy(
        id=str(uuid.uuid4()),
        name="Document Content Policy",
        description="Policy for document content types",
        algorithm=EncryptionAlgorithm.AES_256_GCM,
        scope=EncryptionScope.CONTENT,
        content_types=["application/pdf", "application/msword", "application/vnd.openxmlformats-officedocument.*"],
        key_rotation_days=30,
        require_perfect_forward_secrecy=True
    )
    encryption_manager.add_policy(document_policy)
    logger.info(f"Added document policy: {document_policy.id}")
    
    # List all policies
    logger.info("\nListing all policies:")
    all_policies = encryption_manager.list_policies()
    for policy in all_policies:
        logger.info(f"  - {policy.name}: {policy.algorithm}, scope: {policy.scope}")
        if policy.content_types:
            logger.info(f"    Content types: {', '.join(policy.content_types)}")
    
    # Try encrypting data with content type matching a policy
    logger.info("\nEncrypting data with content type matching policies:")
    
    # 1. PDF document (should use document policy)
    pdf_data = b"This is pretend PDF content for testing policy-based encryption"
    pdf_encrypted = encryption_manager.encrypt(
        data=pdf_data,
        content_type="application/pdf",
        metadata={"filename": "test_document.pdf"}
    )
    logger.info(f"PDF data encrypted with algorithm: {pdf_encrypted.algorithm}")
    
    # 2. JPEG image (should use image policy)
    image_data = b"This is pretend JPEG content for testing policy-based encryption"
    image_encrypted = encryption_manager.encrypt(
        data=image_data,
        content_type="image/jpeg",
        metadata={"filename": "test_image.jpg"}
    )
    logger.info(f"Image data encrypted with algorithm: {image_encrypted.algorithm}")
    
    # 3. Plain text (should use global policy)
    text_data = b"This is plain text content for testing policy-based encryption"
    text_encrypted = encryption_manager.encrypt(
        data=text_data,
        content_type="text/plain",
        metadata={"filename": "test.txt"}
    )
    logger.info(f"Text data encrypted with algorithm: {text_encrypted.algorithm}")


def demonstrate_file_encryption(encryption_manager: EncryptionManager, temp_dir: str):
    """Demonstrate file encryption and decryption."""
    logger.info("\n=== File Encryption Demonstration ===\n")
    
    # Create sample files
    logger.info("Creating sample files...")
    
    # 1. Text file
    text_file_path = os.path.join(temp_dir, "sample_text.txt")
    with open(text_file_path, 'w') as f:
        f.write("This is a sample text file for encryption testing.\n")
        f.write("It contains multiple lines of text.\n")
        f.write("The file will be encrypted and then decrypted to verify functionality.")
    logger.info(f"Created text file: {text_file_path}")
    
    # 2. JSON file (simulating structured data)
    json_file_path = os.path.join(temp_dir, "sample_data.json")
    sample_data = {
        "user": {
            "id": 12345,
            "name": "John Doe",
            "email": "john.doe@example.com",
            "roles": ["user", "admin"]
        },
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "version": "1.0"
        },
        "settings": {
            "theme": "dark",
            "notifications": True,
            "language": "en-US"
        }
    }
    with open(json_file_path, 'w') as f:
        json.dump(sample_data, f, indent=2)
    logger.info(f"Created JSON file: {json_file_path}")
    
    # 3. Binary file (simulating image data)
    binary_file_path = os.path.join(temp_dir, "sample_binary.dat")
    with open(binary_file_path, 'wb') as f:
        f.write(os.urandom(1024))  # 1KB of random data
    logger.info(f"Created binary file: {binary_file_path}")
    
    # Encrypt the files
    logger.info("\nEncrypting files...")
    
    # 1. Encrypt text file
    text_encrypted_path = os.path.join(temp_dir, "sample_text.encrypted")
    text_metadata = encryption_manager.encrypt_file(
        input_path=text_file_path,
        output_path=text_encrypted_path,
        content_type="text/plain",
        metadata={"description": "Sample text file"}
    )
    logger.info(f"Encrypted text file: {text_encrypted_path}")
    logger.info(f"  Algorithm: {text_metadata['algorithm']}")
    logger.info(f"  Key ID: {text_metadata['encryption_key_id']}")
    
    # 2. Encrypt JSON file
    json_encrypted_path = os.path.join(temp_dir, "sample_data.encrypted")
    json_metadata = encryption_manager.encrypt_file(
        input_path=json_file_path,
        output_path=json_encrypted_path,
        content_type="application/json",
        metadata={"description": "Sample JSON file"}
    )
    logger.info(f"Encrypted JSON file: {json_encrypted_path}")
    logger.info(f"  Algorithm: {json_metadata['algorithm']}")
    
    # 3. Encrypt binary file
    binary_encrypted_path = os.path.join(temp_dir, "sample_binary.encrypted")
    binary_metadata = encryption_manager.encrypt_file(
        input_path=binary_file_path,
        output_path=binary_encrypted_path,
        content_type="application/octet-stream",
        metadata={"description": "Sample binary file"}
    )
    logger.info(f"Encrypted binary file: {binary_encrypted_path}")
    logger.info(f"  Algorithm: {binary_metadata['algorithm']}")
    
    # Decrypt the files
    logger.info("\nDecrypting files...")
    
    # 1. Decrypt text file
    text_decrypted_path = os.path.join(temp_dir, "sample_text.decrypted.txt")
    text_decrypted_metadata = encryption_manager.decrypt_file(
        input_path=text_encrypted_path,
        output_path=text_decrypted_path
    )
    logger.info(f"Decrypted text file: {text_decrypted_path}")
    
    # Verify decrypted content
    with open(text_file_path, 'rb') as f:
        original_text = f.read()
    with open(text_decrypted_path, 'rb') as f:
        decrypted_text = f.read()
    assert original_text == decrypted_text, "Decrypted text does not match original"
    logger.info("Text file decryption verified ✓")
    
    # 2. Decrypt JSON file
    json_decrypted_path = os.path.join(temp_dir, "sample_data.decrypted.json")
    json_decrypted_metadata = encryption_manager.decrypt_file(
        input_path=json_encrypted_path,
        output_path=json_decrypted_path
    )
    logger.info(f"Decrypted JSON file: {json_decrypted_path}")
    
    # Verify decrypted content
    with open(json_file_path, 'rb') as f:
        original_json = f.read()
    with open(json_decrypted_path, 'rb') as f:
        decrypted_json = f.read()
    assert original_json == decrypted_json, "Decrypted JSON does not match original"
    logger.info("JSON file decryption verified ✓")
    
    # 3. Decrypt binary file
    binary_decrypted_path = os.path.join(temp_dir, "sample_binary.decrypted.dat")
    binary_decrypted_metadata = encryption_manager.decrypt_file(
        input_path=binary_encrypted_path,
        output_path=binary_decrypted_path
    )
    logger.info(f"Decrypted binary file: {binary_decrypted_path}")
    
    # Verify decrypted content
    with open(binary_file_path, 'rb') as f:
        original_binary = f.read()
    with open(binary_decrypted_path, 'rb') as f:
        decrypted_binary = f.read()
    assert original_binary == decrypted_binary, "Decrypted binary data does not match original"
    logger.info("Binary file decryption verified ✓")


def demonstrate_backend_integration(encryption_manager: EncryptionManager):
    """Demonstrate integration with storage backends."""
    logger.info("\n=== Storage Backend Integration Demonstration ===\n")
    
    # Initialize the backend encryption handler
    backend_handler = BackendEncryptionHandler(encryption_manager)
    
    # Sample data to store
    logger.info("Preparing sample data for storage...")
    sample_data = json.dumps({
        "user_id": 12345,
        "username": "alice",
        "email": "alice@example.com",
        "attributes": {
            "role": "admin",
            "created_at": datetime.now().isoformat(),
            "last_login": (datetime.now() - timedelta(days=1)).isoformat()
        }
    }).encode('utf-8')
    
    # Encrypt data for storage
    logger.info("Encrypting data for storage backend...")
    encrypted_result = backend_handler.encrypt_data_for_storage(
        data=sample_data,
        content_type="application/json",
        metadata={
            "object_type": "user",
            "object_id": "12345",
            "version": "1.0"
        }
    )
    
    logger.info(f"Data encrypted for storage:")
    logger.info(f"  Encryption ID: {encrypted_result['encryption']['id']}")
    logger.info(f"  Algorithm: {encrypted_result['encryption']['algorithm']}")
    logger.info(f"  Content type: {encrypted_result['encryption']['content_type']}")
    logger.info(f"  Original size: {encrypted_result['encryption']['original_size']} bytes")
    logger.info(f"  Encrypted size: {len(encrypted_result['data'])} bytes")
    
    # In a real application, this encrypted_result would be stored in a backend
    # For example, in S3, IPFS, or a database
    
    # Later, when retrieving the data from the backend:
    logger.info("\nRetrieving and decrypting data from storage backend...")
    decrypted_data, metadata = backend_handler.decrypt_data_from_storage(encrypted_result)
    
    # Verify the decrypted data matches the original
    assert decrypted_data == sample_data, "Decrypted data from backend does not match original"
    
    logger.info(f"Successfully decrypted data from storage:")
    logger.info(f"  Decrypted data (JSON): {json.loads(decrypted_data.decode('utf-8'))}")
    logger.info(f"  Metadata: {metadata}")


def main():
    """Main function."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="End-to-End Encryption Example for MCP Server")
    parser.add_argument("--storage-path", default=None, help="Path for key storage")
    args = parser.parse_args()
    
    # Create a temporary directory for test files and keys
    with tempfile.TemporaryDirectory() as temp_dir:
        storage_path = args.storage_path or os.path.join(temp_dir, "key_storage")
        os.makedirs(storage_path, exist_ok=True)
        
        logger.info(f"Using storage path: {storage_path}")
        
        try:
            # Demonstrate key management
            key_manager = demonstrate_key_management(storage_path)
            
            # Demonstrate encryption and decryption
            encryption_manager = demonstrate_encryption(key_manager)
            
            # Demonstrate encryption policies
            demonstrate_encryption_policies(encryption_manager)
            
            # Demonstrate file encryption
            demonstrate_file_encryption(encryption_manager, temp_dir)
            
            # Demonstrate backend integration
            demonstrate_backend_integration(encryption_manager)
            
            logger.info("\n=== All demonstrations completed successfully! ===")
            
        except Exception as e:
            logger.exception(f"Error during demonstration: {e}")


if __name__ == "__main__":
    main()
