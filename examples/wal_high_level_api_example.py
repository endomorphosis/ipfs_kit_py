#!/usr/bin/env python3
# examples/wal_high_level_api_example.py

"""
Example demonstrating integration of the Write-Ahead Log (WAL) with the high-level API.

This example shows how to:
1. Initialize the high-level API with WAL enabled
2. Wrap API methods with WAL decorators
3. Track operations in the WAL
4. Monitor operation status
5. Handle backend outages gracefully
"""

import os
import time
import logging
import tempfile
from typing import Dict, Any

from ipfs_kit_py import IPFSSimpleAPI
from ipfs_kit_py.storage_wal import StorageWriteAheadLog, BackendHealthMonitor, OperationType, BackendType
from ipfs_kit_py.wal_integration import WALIntegration, with_wal

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_example_api():
    """Create an API instance with WAL integration."""
    # Initialize the API
    api = IPFSSimpleAPI()
    
    # Create WAL configuration
    wal_config = {
        "base_path": "~/.ipfs_kit/wal",
        "partition_size": 100,
        "max_retries": 3,
        "retry_delay": 5,
        "archive_completed": True,
        "enable_health_monitoring": True,
        "health_check_interval": 10
    }
    
    # Initialize WAL integration
    wal_integration = WALIntegration(config=wal_config)
    
    # Wrap key API methods with WAL decorators
    # Note: In a real implementation, these would be applied using metaclasses or during 
    # class definition, but for this example we'll monkey patch the instance
    
    # Wrap add() method
    original_add = api.add
    api.add = with_wal(
        operation_type=OperationType.ADD,
        backend=BackendType.IPFS,
        wal_integration=wal_integration
    )(original_add)
    
    # Wrap get() method
    original_get = api.get
    api.get = with_wal(
        operation_type=OperationType.GET,
        backend=BackendType.IPFS,
        wal_integration=wal_integration
    )(original_get)
    
    # Wrap pin() method
    if hasattr(api, 'pin'):
        original_pin = api.pin
        api.pin = with_wal(
            operation_type=OperationType.PIN,
            backend=BackendType.IPFS,
            wal_integration=wal_integration
        )(original_pin)
    
    # Wrap unpin() method
    if hasattr(api, 'unpin'):
        original_unpin = api.unpin
        api.unpin = with_wal(
            operation_type=OperationType.UNPIN,
            backend=BackendType.IPFS,
            wal_integration=wal_integration
        )(original_unpin)
    
    # Add WAL-specific methods to the API
    api.get_wal_operation = wal_integration.get_operation
    api.get_wal_operations_by_status = wal_integration.get_operations_by_status
    api.get_wal_all_operations = wal_integration.get_all_operations
    api.get_wal_statistics = wal_integration.get_statistics
    api.get_wal_backend_health = wal_integration.get_backend_health
    api.wal_cleanup = wal_integration.cleanup
    api.wait_for_operation = wal_integration.wait_for_operation
    
    # Store WAL integration instance
    api.wal_integration = wal_integration
    
    return api

def demonstrate_basic_usage(api):
    """Demonstrate basic WAL usage with the high-level API."""
    logger.info("=== Demonstrating basic WAL usage ===")
    
    # Create a temporary file
    with tempfile.NamedTemporaryFile(delete=False) as temp:
        temp.write(b"Hello, IPFS Kit with Write-Ahead Log!")
        temp_path = temp.name
    
    try:
        # Add file to IPFS with WAL tracking
        logger.info("Adding file to IPFS (tracked by WAL)")
        result = api.add(temp_path)
        
        # The operation is now tracked in the WAL
        operation_id = result["operation_id"]
        logger.info(f"Operation ID: {operation_id}")
        
        # Get the operation status
        operation = api.get_wal_operation(operation_id)
        logger.info(f"Operation status: {operation['status']}")
        
        # Get WAL statistics
        stats = api.get_wal_statistics()
        logger.info(f"WAL statistics: {stats}")
        
        # Get backend health
        health = api.get_wal_backend_health()
        logger.info(f"Backend health: {health}")
        
        # List all operations
        operations = api.get_wal_all_operations()
        logger.info(f"Total operations: {len(operations)}")
        
        # Get pending operations
        pending = api.get_wal_operations_by_status("pending")
        logger.info(f"Pending operations: {len(pending)}")
        
        # Wait for operation to complete if it's still pending
        if operation["status"] in ["pending", "processing"]:
            logger.info(f"Waiting for operation to complete...")
            final_result = api.wait_for_operation(operation_id, timeout=10)
            logger.info(f"Final result: {final_result}")
    
    finally:
        # Clean up
        os.unlink(temp_path)

def simulate_backend_outage(api):
    """Simulate a backend outage to demonstrate WAL behavior."""
    logger.info("=== Simulating backend outage ===")
    
    # Access the health monitor and set IPFS to "offline"
    health_monitor = api.wal_integration.wal.health_monitor
    
    # Store original status check function
    original_check_ipfs = health_monitor._check_ipfs_health
    
    # Replace with a function that always returns False (offline)
    health_monitor._check_ipfs_health = lambda config: False
    
    # Force a manual health check
    health_monitor._check_backend(BackendType.IPFS.value)
    
    try:
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False) as temp:
            temp.write(b"This file will be queued during the outage!")
            temp_path = temp.name
        
        # Add file to IPFS with WAL tracking
        logger.info("Adding file to IPFS during simulated outage")
        result = api.add(temp_path)
        
        # The operation should be queued in the WAL
        operation_id = result["operation_id"]
        logger.info(f"Operation queued in WAL with ID: {operation_id}")
        
        # Check statistics
        stats = api.get_wal_statistics()
        logger.info(f"WAL statistics during outage: {stats}")
        
        # Check backend health
        health = api.get_wal_backend_health()
        logger.info(f"Backend health during outage: {health}")
        
        # Now restore the backend
        logger.info("Restoring backend health...")
        health_monitor._check_ipfs_health = original_check_ipfs
        
        # Force a manual health check
        health_monitor._check_backend(BackendType.IPFS.value)
        
        # Check backend health after restoration
        health = api.get_wal_backend_health()
        logger.info(f"Backend health after restoration: {health}")
        
        # Wait for operation to complete after backend restoration
        logger.info(f"Waiting for queued operation to complete...")
        final_result = api.wait_for_operation(operation_id, timeout=30)
        logger.info(f"Final result after backend restored: {final_result}")
        
        # Check WAL statistics after processing
        stats = api.get_wal_statistics()
        logger.info(f"WAL statistics after processing: {stats}")
        
        # Clean up
        os.unlink(temp_path)
        
    finally:
        # Restore original health check function
        health_monitor._check_ipfs_health = original_check_ipfs

def cleanup_demo(api):
    """Demonstrate WAL cleanup functionality."""
    logger.info("=== Demonstrating WAL cleanup ===")
    
    # Perform cleanup
    cleanup_result = api.wal_cleanup(max_age_days=30)
    logger.info(f"Cleanup result: {cleanup_result}")
    
    # Get statistics after cleanup
    stats = api.get_wal_statistics()
    logger.info(f"WAL statistics after cleanup: {stats}")

def main():
    """Main function to run the example."""
    logger.info("Starting WAL high-level API integration example")
    
    # Create API with WAL integration
    api = create_example_api()
    
    try:
        # Demonstrate basic usage
        demonstrate_basic_usage(api)
        
        # Simulate backend outage
        simulate_backend_outage(api)
        
        # Demonstrate cleanup
        cleanup_demo(api)
        
    finally:
        # Clean up resources
        if hasattr(api, 'wal_integration'):
            api.wal_integration.close()
    
    logger.info("Example completed successfully")

if __name__ == "__main__":
    main()