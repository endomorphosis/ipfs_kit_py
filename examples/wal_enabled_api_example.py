#!/usr/bin/env python3
# examples/wal_enabled_api_example.py

"""
Example demonstrating the WALEnabledAPI class.

This example shows how to:
1. Initialize the WALEnabledAPI with configuration options
2. Use the API with WAL-backed storage operations
3. Monitor operation status and backend health
4. Test fault tolerance during backend outages
"""

import os
import time
import logging
import tempfile
import yaml
from pathlib import Path

from ipfs_kit_py.wal_api_extension import WALEnabledAPI
from ipfs_kit_py.storage_wal import OperationStatus, BackendType

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_config_file():
    """Create a configuration file for the WALEnabledAPI."""
    config = {
        "role": "worker",
        "resources": {
            "max_memory": "1GB",
            "max_storage": "10GB"
        },
        "wal": {
            "enabled": True,
            "base_path": "~/.ipfs_kit/wal",
            "partition_size": 100,
            "max_retries": 3,
            "retry_delay": 5,
            "archive_completed": True,
            "processing_interval": 1,
            "enable_health_monitoring": True,
            "health_check_interval": 5
        }
    }
    
    # Create config directory
    config_dir = Path.home() / ".ipfs_kit"
    config_dir.mkdir(exist_ok=True)
    
    # Write config file
    config_path = config_dir / "config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f)
    
    return str(config_path)

def basic_operations(api):
    """Demonstrate basic operations with WAL tracking."""
    logger.info("=== Demonstrating Basic Operations ===")
    
    # Create a temporary file
    with tempfile.NamedTemporaryFile(delete=False) as temp:
        temp.write(b"Hello, WALEnabledAPI Example!")
        temp_path = temp.name
    
    try:
        # Add file to IPFS
        logger.info("Adding file to IPFS")
        result = api.add(temp_path)
        logger.info(f"Add result: {result}")
        
        # Get the operation ID from the result
        operation_id = result.get("operation_id")
        
        if operation_id:
            # Get operation details
            operation = api.get_wal_operation(operation_id)
            logger.info(f"Operation details: {operation}")
            
            # If the operation is still pending, wait for it to complete
            if operation["status"] in [OperationStatus.PENDING.value, OperationStatus.PROCESSING.value]:
                logger.info("Waiting for operation to complete...")
                final_result = api.wait_for_operation(operation_id)
                logger.info(f"Final result: {final_result}")
                
                # Once completed, try to retrieve the content
                if operation["status"] == OperationStatus.COMPLETED.value:
                    cid = final_result.get("result", {}).get("cid")
                    if cid:
                        logger.info(f"Retrieving content for CID: {cid}")
                        content = api.cat(cid)
                        logger.info(f"Retrieved content: {content}")
        
    finally:
        # Clean up
        os.unlink(temp_path)

def test_fault_tolerance(api):
    """Test fault tolerance with simulated backend outages."""
    logger.info("=== Testing Fault Tolerance ===")
    
    # Get the health monitor from the API
    health_monitor = api.wal_integration.wal.health_monitor
    
    # Store the original health check function
    original_check_ipfs = health_monitor._check_ipfs_health
    
    try:
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False) as temp:
            temp.write(b"This file will be queued during the outage!")
            temp_path = temp.name
            
        # Simulate backend outage
        logger.info("Simulating backend outage...")
        health_monitor._check_ipfs_health = lambda config: False
        
        # Force a health check
        health_monitor._check_backend(BackendType.IPFS.value)
        
        # Check backend health
        health = api.get_wal_backend_health(BackendType.IPFS.value)
        logger.info(f"IPFS backend health: {health}")
        
        # Try to add a file during the outage
        logger.info("Adding file during simulated outage")
        result = api.add(temp_path)
        logger.info(f"Add operation queued: {result}")
        
        # Get WAL statistics
        stats = api.get_wal_statistics()
        logger.info(f"WAL statistics during outage: {stats}")
        
        # Restore the backend
        logger.info("Restoring backend...")
        health_monitor._check_ipfs_health = original_check_ipfs
        
        # Force health check
        health_monitor._check_backend(BackendType.IPFS.value)
        
        # Check backend health after restoration
        health = api.get_wal_backend_health(BackendType.IPFS.value)
        logger.info(f"IPFS backend health after restoration: {health}")
        
        # Wait for the queued operation to complete
        operation_id = result.get("operation_id")
        if operation_id:
            logger.info(f"Waiting for operation {operation_id} to complete...")
            final_result = api.wait_for_operation(operation_id, 30)
            logger.info(f"Final result: {final_result}")
            
        # Get updated WAL statistics
        stats = api.get_wal_statistics()
        logger.info(f"WAL statistics after processing: {stats}")
        
        # Clean up
        os.unlink(temp_path)
    
    finally:
        # Restore original health check function
        health_monitor._check_ipfs_health = original_check_ipfs

def monitor_wal_status(api):
    """Monitor WAL status and operations."""
    logger.info("=== Monitoring WAL Status ===")
    
    # Get WAL statistics
    stats = api.get_wal_statistics()
    logger.info(f"WAL statistics: {stats}")
    
    # List operations by status
    for status in [OperationStatus.PENDING.value, OperationStatus.PROCESSING.value, 
                   OperationStatus.COMPLETED.value, OperationStatus.FAILED.value, 
                   OperationStatus.RETRYING.value]:
        operations = api.get_wal_operations_by_status(status)
        logger.info(f"{status.capitalize()} operations: {len(operations)}")
        
        # Show details of a few operations for each status
        for op in operations[:2]:  # Show at most 2 operations per status
            logger.info(f"  - Operation {op['operation_id']}: {op.get('operation_type')} ({op.get('backend')})")
    
    # Show backend health status
    health = api.get_wal_backend_health()
    logger.info(f"Backend health: {health}")
    
    # Cleanup operations older than 7 days
    if stats.get("total_operations", 0) > 0:
        logger.info("Cleaning up old operations...")
        cleanup_result = api.wal_cleanup(max_age_days=7)
        logger.info(f"Cleanup result: {cleanup_result}")

def main():
    """Main function to run the example."""
    logger.info("Starting WALEnabledAPI example")
    
    try:
        # Create configuration file
        config_path = create_config_file()
        logger.info(f"Created configuration file at {config_path}")
        
        # Initialize the WALEnabledAPI
        api = WALEnabledAPI(config_path=config_path)
        logger.info("WALEnabledAPI initialized")
        
        # Demonstrate basic operations
        basic_operations(api)
        
        # Test fault tolerance
        test_fault_tolerance(api)
        
        # Monitor WAL status
        monitor_wal_status(api)
        
    except Exception as e:
        logger.error(f"Error running example: {e}", exc_info=True)
    
    logger.info("Example completed")

if __name__ == "__main__":
    main()