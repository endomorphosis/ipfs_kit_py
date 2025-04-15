#!/usr/bin/env python3
"""
Test and demonstrate the enhanced IPNS operations for IPFS Kit.

This script tests the new IPNS operations functionality, including
key management, name publishing, and resolution. It serves as both
a validation tool and a practical example of how to use the module.
"""

import argparse
import json
import logging
import os
import sys
import time
import uuid
from typing import Any, Dict, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("test_ipns_operations")

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import our modules
from ipfs_connection_pool import IPFSConnectionConfig, get_connection_pool
from ipfs_ipns_operations import (
    IPNSOperations, KeyManager, KeyType, KeyProtectionLevel, IPNSRecord
)

def pretty_print(data: Any) -> None:
    """Print formatted JSON data."""
    if isinstance(data, dict):
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        print(data)

def test_key_management(api_url: str = "http://127.0.0.1:5001/api/v0") -> None:
    """Test key management operations."""
    logger.info("=== Testing Key Management ===")
    logger.info(f"Using API URL: {api_url}")
    
    # Initialize connection and key manager
    config = IPFSConnectionConfig(base_url=api_url)
    pool = get_connection_pool(config)
    key_manager = KeyManager(pool)
    
    # List current keys
    logger.info("Listing existing keys...")
    keys_result = key_manager.list_keys(force_refresh=True)
    if keys_result["success"]:
        logger.info(f"Found {len(keys_result['keys'])} keys:")
        for key in keys_result["keys"]:
            print(f"  - {key['Name']}: {key['Id']}")
    else:
        logger.error(f"Failed to list keys: {keys_result['error']}")
        return
    
    # Generate a unique key name for testing
    test_key_name = f"test-key-{uuid.uuid4().hex[:8]}"
    logger.info(f"Creating new ED25519 key: {test_key_name}")
    
    # Create a new ED25519 key
    create_result = key_manager.create_key(
        name=test_key_name,
        key_type=KeyType.ED25519,
    )
    
    if create_result["success"]:
        key_info = create_result["key"]
        logger.info(f"Created key: {key_info['Name']} with ID: {key_info['Id']}")
    else:
        logger.error(f"Failed to create key: {create_result['error']}")
        return
    
    # Get key details
    logger.info(f"Getting details for key: {test_key_name}")
    key_result = key_manager.get_key(test_key_name)
    if key_result["success"]:
        logger.info("Key details:")
        pretty_print(key_result["key"])
    else:
        logger.error(f"Failed to get key: {key_result['error']}")
    
    # Export the key
    logger.info(f"Exporting key: {test_key_name}")
    export_result = key_manager.export_key(test_key_name)
    if export_result["success"]:
        logger.info("Key exported successfully")
        key_data = export_result["key_data"]
        logger.info(f"Key data (truncated): {key_data[:50]}...")
        
        # Test key renaming
        new_key_name = f"{test_key_name}-renamed"
        logger.info(f"Renaming key from {test_key_name} to {new_key_name}")
        rename_result = key_manager.rename_key(test_key_name, new_key_name)
        
        if rename_result["success"]:
            logger.info(f"Key renamed successfully to: {new_key_name}")
            
            # Import the exported key under the original name
            logger.info(f"Importing key as: {test_key_name}")
            import_result = key_manager.import_key(
                name=test_key_name,
                private_key=key_data,
            )
            
            if import_result["success"]:
                logger.info("Key imported successfully")
                imported_key = import_result["key"]
                logger.info(f"Imported key ID: {imported_key['Id']}")
                
                # List keys again to verify
                logger.info("Listing keys after import...")
                keys_result = key_manager.list_keys(force_refresh=True)
                if keys_result["success"]:
                    logger.info(f"Found {len(keys_result['keys'])} keys:")
                    for key in keys_result["keys"]:
                        print(f"  - {key['Name']}: {key['Id']}")
                
                # Clean up imported key
                logger.info(f"Removing imported key: {test_key_name}")
                remove_result = key_manager.remove_key(test_key_name)
                if remove_result["success"]:
                    logger.info("Key removed successfully")
                else:
                    logger.error(f"Failed to remove key: {remove_result['error']}")
            else:
                logger.error(f"Failed to import key: {import_result['error']}")
        else:
            logger.error(f"Failed to rename key: {rename_result['error']}")
    else:
        logger.error(f"Failed to export key: {export_result['error']}")
    
    # Test key rotation
    logger.info(f"Rotating key: {new_key_name}")
    rotate_result = key_manager.rotate_key(
        name=new_key_name,
        preserve_old=True,
    )
    
    if rotate_result["success"]:
        logger.info("Key rotated successfully")
        logger.info(f"New key ID: {rotate_result['new_key_id']}")
        logger.info(f"Old key preserved as: {rotate_result['old_key_name']}")
        
        # Clean up rotated key
        logger.info(f"Removing rotated key: {new_key_name}")
        remove_result = key_manager.remove_key(new_key_name)
        if remove_result["success"]:
            logger.info("Rotated key removed successfully")
        else:
            logger.error(f"Failed to remove rotated key: {remove_result['error']}")
        
        # Clean up preserved old key
        if rotate_result['old_key_name']:
            logger.info(f"Removing preserved old key: {rotate_result['old_key_name']}")
            remove_result = key_manager.remove_key(rotate_result['old_key_name'])
            if remove_result["success"]:
                logger.info("Preserved old key removed successfully")
            else:
                logger.error(f"Failed to remove preserved old key: {remove_result['error']}")
    else:
        logger.error(f"Failed to rotate key: {rotate_result['error']}")
    
    # Get metrics
    logger.info("Getting key management metrics")
    metrics_result = key_manager.get_metrics()
    pretty_print(metrics_result)
    
    logger.info("Key management tests completed")

def test_ipns_operations(api_url: str = "http://127.0.0.1:5001/api/v0") -> None:
    """Test IPNS publishing and resolution operations."""
    logger.info("=== Testing IPNS Operations ===")
    logger.info(f"Using API URL: {api_url}")
    
    # Initialize connection and IPNS operations
    config = IPFSConnectionConfig(base_url=api_url)
    pool = get_connection_pool(config)
    ipns_ops = IPNSOperations(pool)
    
    # Generate a unique key name for testing
    test_key_name = f"test-ipns-{uuid.uuid4().hex[:8]}"
    logger.info(f"Creating key for IPNS testing: {test_key_name}")
    
    # Create a key for testing
    create_result = ipns_ops.key_manager.create_key(
        name=test_key_name,
        key_type=KeyType.ED25519,
    )
    
    if not create_result["success"]:
        logger.error(f"Failed to create key for IPNS testing: {create_result['error']}")
        return
    
    key_info = create_result["key"]
    key_id = key_info["Id"]
    logger.info(f"Created key with ID: {key_id}")
    
    # Create a test file to publish
    test_content = f"IPNS test content created at {time.time()}".encode()
    test_filename = f"ipns-test-{uuid.uuid4().hex[:8]}.txt"
    
    logger.info(f"Adding test content to IPFS: {test_filename}")
    try:
        # Add content to IPFS
        response = pool.post(
            "add", 
            files={"file": (test_filename, test_content)},
            params={"pin": "true"}
        )
        
        if response.status_code == 200:
            add_result = json.loads(response.text)
            test_cid = add_result.get("Hash")
            logger.info(f"Added content with CID: {test_cid}")
            
            # Publish to IPNS using our test key
            logger.info(f"Publishing CID {test_cid} to IPNS with key: {test_key_name}")
            publish_result = ipns_ops.publish(
                cid=test_cid,
                key_name=test_key_name,
                lifetime="1h",  # Short lifetime for testing
                ttl="5m",       # Short TTL for testing
            )
            
            if publish_result["success"]:
                ipns_name = publish_result["name"]
                logger.info(f"Successfully published to IPNS name: {ipns_name}")
                logger.info("Publication details:")
                pretty_print(publish_result["record"])
                
                # Test resolving the name
                logger.info(f"Resolving IPNS name: {ipns_name}")
                resolve_result = ipns_ops.resolve(ipns_name)
                
                if resolve_result["success"]:
                    resolved_path = resolve_result["value"]
                    logger.info(f"Successfully resolved to: {resolved_path}")
                    
                    # Verify resolved path contains our CID
                    if test_cid in resolved_path:
                        logger.info("✓ Resolution verified: path contains expected CID")
                    else:
                        logger.error(f"✗ Resolution verification failed: {resolved_path} does not contain {test_cid}")
                    
                    # Test republishing
                    logger.info(f"Republishing IPNS name: {ipns_name}")
                    republish_result = ipns_ops.republish(name=ipns_name, key_name=test_key_name)
                    
                    if republish_result["success"]:
                        logger.info("Successfully republished IPNS name")
                    else:
                        logger.error(f"Failed to republish IPNS name: {republish_result['error']}")
                else:
                    logger.error(f"Failed to resolve IPNS name: {resolve_result['error']}")
            else:
                logger.error(f"Failed to publish to IPNS: {publish_result['error']}")
        else:
            logger.error(f"Failed to add test content: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Error during IPNS testing: {str(e)}")
    
    # Get active records
    logger.info("Getting active IPNS records")
    records_result = ipns_ops.get_records()
    
    if records_result["success"]:
        records = records_result["records"]
        logger.info(f"Found {len(records)} active IPNS records:")
        for record in records:
            print(f"  - {record['key_name']}: {record['name']} → {record['value']}")
    else:
        logger.error(f"Failed to get IPNS records: {records_result['error']}")
    
    # Get metrics
    logger.info("Getting IPNS operations metrics")
    metrics_result = ipns_ops.get_metrics()
    pretty_print(metrics_result)
    
    # Clean up the test key
    logger.info(f"Cleaning up test key: {test_key_name}")
    remove_result = ipns_ops.key_manager.remove_key(test_key_name)
    if remove_result["success"]:
        logger.info("Test key removed successfully")
    else:
        logger.error(f"Failed to remove test key: {remove_result['error']}")
    
    logger.info("IPNS operations tests completed")

def test_ipns_workflow(api_url: str = "http://127.0.0.1:5001/api/v0") -> None:
    """Test a complete IPNS workflow with key rotation."""
    logger.info("=== Testing Complete IPNS Workflow ===")
    logger.info(f"Using API URL: {api_url}")
    
    # Initialize connection and IPNS operations
    config = IPFSConnectionConfig(base_url=api_url)
    pool = get_connection_pool(config)
    ipns_ops = IPNSOperations(pool)
    
    # Create a unique namespace (app name) for our test
    app_namespace = f"ipns-app-{uuid.uuid4().hex[:8]}"
    logger.info(f"Creating namespace key: {app_namespace}")
    
    # Create application namespace key
    create_result = ipns_ops.key_manager.create_key(
        name=app_namespace,
        key_type=KeyType.ED25519,
    )
    
    if not create_result["success"]:
        logger.error(f"Failed to create namespace key: {create_result['error']}")
        return
    
    namespace_key = create_result["key"]
    namespace_id = namespace_key["Id"]
    logger.info(f"Created namespace with ID: {namespace_id}")
    
    try:
        # Step 1: Add initial content
        initial_content = f"Initial content for {app_namespace} at {time.time()}".encode()
        logger.info("Adding initial content to IPFS")
        response = pool.post(
            "add", 
            files={"file": ("initial.txt", initial_content)},
            params={"pin": "true"}
        )
        
        if response.status_code != 200:
            logger.error(f"Failed to add initial content: {response.status_code} - {response.text}")
            return
            
        initial_cid = json.loads(response.text).get("Hash")
        logger.info(f"Added initial content with CID: {initial_cid}")
        
        # Step 2: Publish initial content with our namespace key
        logger.info(f"Publishing initial content to IPNS with key: {app_namespace}")
        publish_result = ipns_ops.publish(
            cid=initial_cid,
            key_name=app_namespace,
            lifetime="24h",
            ttl="15m",
        )
        
        if not publish_result["success"]:
            logger.error(f"Failed to publish initial content: {publish_result['error']}")
            return
            
        ipns_name = publish_result["name"]
        logger.info(f"Published initial content to IPNS name: {ipns_name}")
        
        # Step 3: Add updated content
        updated_content = f"Updated content for {app_namespace} at {time.time()}".encode()
        logger.info("Adding updated content to IPFS")
        response = pool.post(
            "add", 
            files={"file": ("updated.txt", updated_content)},
            params={"pin": "true"}
        )
        
        if response.status_code != 200:
            logger.error(f"Failed to add updated content: {response.status_code} - {response.text}")
            return
            
        updated_cid = json.loads(response.text).get("Hash")
        logger.info(f"Added updated content with CID: {updated_cid}")
        
        # Step 4: Update IPNS record with new content
        logger.info(f"Updating IPNS record to point to new content: {updated_cid}")
        update_result = ipns_ops.publish(
            cid=updated_cid,
            key_name=app_namespace,
            lifetime="24h",
            ttl="15m",
        )
        
        if not update_result["success"]:
            logger.error(f"Failed to update IPNS record: {update_result['error']}")
            return
            
        logger.info("Successfully updated IPNS record")
        
        # Step 5: Verify the update
        logger.info(f"Resolving IPNS name to verify update: {ipns_name}")
        resolve_result = ipns_ops.resolve(ipns_name, nocache=True)
        
        if not resolve_result["success"]:
            logger.error(f"Failed to resolve IPNS name: {resolve_result['error']}")
            return
            
        resolved_path = resolve_result["value"]
        logger.info(f"Resolved to: {resolved_path}")
        
        # Verify resolved path contains updated CID
        if updated_cid in resolved_path:
            logger.info("✓ Update verified: path contains updated CID")
        else:
            logger.error(f"✗ Update verification failed: {resolved_path} does not contain {updated_cid}")
        
        # Step 6: Rotate the key for security
        logger.info(f"Rotating namespace key: {app_namespace}")
        rotate_result = ipns_ops.key_manager.rotate_key(
            name=app_namespace,
            preserve_old=True,
        )
        
        if not rotate_result["success"]:
            logger.error(f"Failed to rotate key: {rotate_result['error']}")
            return
            
        old_key_name = rotate_result["old_key_name"]
        logger.info(f"Key rotated successfully, old key preserved as: {old_key_name}")
        
        # Step 7: Republish with new key
        logger.info("Republishing to IPNS with rotated key")
        republish_result = ipns_ops.publish(
            cid=updated_cid,
            key_name=app_namespace,
            lifetime="24h",
            ttl="15m",
        )
        
        if not republish_result["success"]:
            logger.error(f"Failed to republish with rotated key: {republish_result['error']}")
            return
            
        new_ipns_name = republish_result["name"]
        logger.info(f"Successfully republished with new IPNS name: {new_ipns_name}")
        
        # Step 8: Check records to see all active records
        logger.info("Getting all active IPNS records")
        records_result = ipns_ops.get_records()
        
        if records_result["success"]:
            records = records_result["records"]
            logger.info(f"Found {len(records)} active IPNS records:")
            for record in records:
                print(f"  - {record['key_name']}: {record['name']} → {record['value']}")
        else:
            logger.error(f"Failed to get IPNS records: {records_result['error']}")
        
    finally:
        # Clean up our test keys
        logger.info("Cleaning up test keys")
        
        # Clean up the namespace key
        remove_result = ipns_ops.key_manager.remove_key(app_namespace)
        if remove_result["success"]:
            logger.info(f"Removed namespace key: {app_namespace}")
        else:
            logger.error(f"Failed to remove namespace key: {remove_result['error']}")
        
        # Clean up the preserved old key if it exists
        if 'old_key_name' in locals() and old_key_name:
            remove_result = ipns_ops.key_manager.remove_key(old_key_name)
            if remove_result["success"]:
                logger.info(f"Removed old key: {old_key_name}")
            else:
                logger.error(f"Failed to remove old key: {remove_result['error']}")
    
    logger.info("IPNS workflow test completed")

def main():
    """Main entry point for testing."""
    parser = argparse.ArgumentParser(description="Test IPNS operations")
    parser.add_argument("--api", default="http://127.0.0.1:5001/api/v0", help="IPFS API URL")
    parser.add_argument("--test", choices=["keys", "ipns", "workflow", "all"], default="all", help="Test to run")
    args = parser.parse_args()
    
    logger.info(f"Testing with IPFS API: {args.api}")
    
    if args.test in ["keys", "all"]:
        test_key_management(args.api)
    
    if args.test in ["ipns", "all"]:
        test_ipns_operations(args.api)
    
    if args.test in ["workflow", "all"]:
        test_ipns_workflow(args.api)

if __name__ == "__main__":
    main()