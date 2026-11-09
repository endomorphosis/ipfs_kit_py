#!/usr/bin/env python3
# test_wal_file_add.py
"""
Test script to verify that the Write Ahead Log (WAL) can correctly handle file additions.

This script:
1. Creates a test file with random content
2. Adds an 'add' operation to the WAL
3. Processes the operation
4. Verifies the operation completed successfully
"""

import os
import sys
import uuid
import time
import logging
import tempfile
import random
import string
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import the WAL implementations
try:
    from ipfs_kit_py.wal import WAL, OperationType, OperationStatus, BackendType
    from ipfs_kit_py.storage_wal import StorageWriteAheadLog
except ImportError:
    # Try relative imports if running from project directory
    sys.path.append('.')
    from ipfs_kit_py.wal import WAL, OperationType, OperationStatus, BackendType
    from ipfs_kit_py.storage_wal import StorageWriteAheadLog

def generate_random_content(size_kb=10):
    """Generate random file content."""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(size_kb * 1024))

def create_test_file(content=None, size_kb=10):
    """Create a temporary test file with optional content."""
    if content is None:
        content = generate_random_content(size_kb)
    
    # Create a temporary file
    fd, temp_path = tempfile.mkstemp()
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(content)
        return temp_path
    except Exception as e:
        logger.error(f"Error creating test file: {e}")
        os.close(fd)
        os.unlink(temp_path)
        return None

def test_wal_file_add():
    """Test adding a file using the core WAL implementation."""
    logger.info("Testing file addition with core WAL implementation")
    
    # Create a custom operation handler for adding files
    def add_file_handler(operation):
        """Custom handler for the 'add' operation type."""
        try:
            # Get the file path from the operation parameters
            file_path = operation.get("parameters", {}).get("file_path")
            
            if not file_path or not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}")
                return {
                    "success": False,
                    "error": f"File not found: {file_path}",
                    "error_type": "FileNotFound"
                }
            
            # Simulate adding the file to IPFS by generating a fake CID
            file_size = os.path.getsize(file_path)
            fake_cid = f"Qm{''.join(random.choice('abcdef0123456789') for _ in range(44))}"
            
            logger.info(f"Added file {file_path} with CID {fake_cid}")
            
            return {
                "success": True,
                "cid": fake_cid,
                "size": file_size
            }
        except Exception as e:
            logger.error(f"Error in add_file_handler: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    # Initialize the WAL
    wal_dir = os.path.join(tempfile.gettempdir(), f"ipfs_wal_test_{uuid.uuid4()}")
    logger.info(f"Initializing WAL in {wal_dir}")
    
    wal = WAL(base_path=wal_dir)
    
    # Register the custom handler
    wal.register_operation_handler(OperationType.ADD, add_file_handler)
    
    try:
        # Create a test file
        test_file_path = create_test_file()
        logger.info(f"Created test file at {test_file_path}")
        
        # Add the operation to the WAL
        add_result = wal.add_operation(
            operation_type=OperationType.ADD,
            backend=BackendType.IPFS,
            parameters={"file_path": test_file_path}
        )
        
        operation_id = add_result["operation_id"]
        logger.info(f"Added operation {operation_id} to the WAL")
        
        # Execute the operation
        execute_result = wal.execute_operation(operation_id)
        
        # Verify the result
        if execute_result["success"]:
            logger.info(f"Operation {operation_id} completed successfully")
            logger.info(f"CID: {execute_result.get('cid')}")
            logger.info(f"Size: {execute_result.get('size')}")
        else:
            logger.error(f"Operation {operation_id} failed: {execute_result.get('error')}")
            
        # Get the updated operation status
        get_result = wal.get_operation(operation_id)
        if get_result["success"]:
            operation = get_result["operation"]
            logger.info(f"Operation status: {operation['status']}")
            
            # Verify the status is COMPLETED
            assert operation["status"] == OperationStatus.COMPLETED.value, \
                f"Expected status COMPLETED, got {operation['status']}"
            
            logger.info("Test passed: Operation status is COMPLETED")
        else:
            logger.error(f"Failed to get operation {operation_id}: {get_result.get('error')}")
            
        return execute_result["success"]
    finally:
        # Clean up
        wal.close()
        
        # Remove the WAL directory
        try:
            import shutil
            shutil.rmtree(wal_dir, ignore_errors=True)
        except Exception as e:
            logger.warning(f"Error cleaning up WAL directory: {e}")

def test_storage_wal_file_add():
    """Test adding a file using the storage WAL implementation."""
    logger.info("Testing file addition with storage WAL implementation")
    
    # Initialize the storage WAL
    wal_dir = os.path.join(tempfile.gettempdir(), f"ipfs_storage_wal_test_{uuid.uuid4()}")
    logger.info(f"Initializing storage WAL in {wal_dir}")
    
    wal = StorageWriteAheadLog(base_path=wal_dir)
    
    try:
        # Create a test file
        test_file_path = create_test_file()
        logger.info(f"Created test file at {test_file_path}")
        
        # Add the operation to the WAL
        add_result = wal.add_operation(
            operation_type="add",  # Use string instead of enum
            backend="ipfs",        # Use string instead of enum
            parameters={"file_path": test_file_path}
        )
        
        operation_id = add_result["operation_id"]
        logger.info(f"Added operation {operation_id} to the storage WAL")
        
        # Wait for the operation to be processed
        logger.info("Waiting for operation to be processed...")
        start_time = time.time()
        timeout = 30  # 30 seconds timeout
        
        while time.time() - start_time < timeout:
            # Get the operation
            operation = wal.get_operation(operation_id)
            
            if operation is None:
                logger.error(f"Operation {operation_id} not found")
                return False
                
            status = operation.get("status")
            logger.info(f"Current operation status: {status}")
            
            # Check if operation is completed or failed
            if status in ["completed", "failed"]:
                break
                
            # Wait a bit before checking again
            time.sleep(1)
        
        # Verify the result
        if operation.get("status") == "completed":
            logger.info(f"Operation {operation_id} completed successfully")
            result = operation.get("result", {})
            if result:
                logger.info(f"Result: {result}")
            return True
        else:
            logger.error(f"Operation {operation_id} failed: {operation.get('error')}")
            return False
    finally:
        # Clean up
        wal.close()
        
        # Remove the WAL directory
        try:
            import shutil
            shutil.rmtree(wal_dir, ignore_errors=True)
        except Exception as e:
            logger.warning(f"Error cleaning up WAL directory: {e}")

if __name__ == "__main__":
    logger.info("Starting WAL file addition tests")
    
    # Test both WAL implementations
    core_wal_success = test_wal_file_add()
    
    print("\n" + "-" * 80 + "\n")
    
    storage_wal_success = test_storage_wal_file_add()
    
    # Summary
    print("\n" + "=" * 80)
    print("WAL File Addition Test Results:")
    print(f"Core WAL: {'PASSED' if core_wal_success else 'FAILED'}")
    print(f"Storage WAL: {'PASSED' if storage_wal_success else 'FAILED'}")
    print("=" * 80 + "\n")
    
    # Overall success
    if core_wal_success and storage_wal_success:
        print("All tests PASSED")
        sys.exit(0)
    else:
        print("Some tests FAILED")
        sys.exit(1)