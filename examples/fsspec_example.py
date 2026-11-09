#!/usr/bin/env python3
"""
IPFS FSSpec Integration Example

This example demonstrates how to use the FSSpec integration in IPFS Kit
to interact with IPFS content using a standard filesystem-like interface.
"""

import os
import sys
import logging
import tempfile

# Add the parent directory to the path to import ipfs_kit_py
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ipfs_kit_py.ipfs_kit import ipfs_kit

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Main example function."""
    # Create an IPFS Kit instance
    kit = ipfs_kit()
    
    # Check if IPFS daemon is running
    if not kit.daemon_checks():
        logger.error("IPFS daemon is not running. Please start it with 'ipfs daemon'.")
        return
    
    # Create a test file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as temp:
        temp.write(b"Hello, IPFS FSSpec!\nThis is a test file created for the example.")
        test_file_path = temp.name
    
    try:
        logger.info(f"Created test file: {test_file_path}")
        
        # Add the file to IPFS
        add_result = kit.ipfs_add_file(test_file_path)
        if not add_result:
            logger.error("Failed to add file to IPFS")
            return
            
        cid = add_result.get('Hash')
        logger.info(f"Added file to IPFS with CID: {cid}")
        
        # Get a filesystem interface
        fs = kit.get_filesystem()
        if not fs:
            logger.error("Failed to create filesystem interface. Make sure fsspec is installed.")
            return
        
        # Basic operations with the filesystem interface
        logger.info("\n--- Basic Operations ---")
        
        # Check if the file exists
        exists = fs.exists(cid)
        logger.info(f"File exists: {exists}")
        
        # Get information about the file
        info = fs.info(cid)
        logger.info(f"File info: {info}")
        
        # Read the file content
        content = fs.cat(cid)
        logger.info(f"File content: {content.decode()}")
        
        # Open and read the file
        logger.info("\n--- Using File-like Objects ---")
        with fs.open(cid, 'rb') as f:
            # Read all content
            all_content = f.read()
            logger.info(f"Read {len(all_content)} bytes from file")
            
            # Seek and read portions
            f.seek(0)
            first_line = f.readline()
            logger.info(f"First line: {first_line.decode()}")
        
        # Add a directory structure
        logger.info("\n--- Directory Operations ---")
        
        # Create a temporary directory with multiple files
        temp_dir = tempfile.mkdtemp()
        for i in range(3):
            with open(os.path.join(temp_dir, f"file{i}.txt"), 'w') as f:
                f.write(f"This is file {i}")
        
        # Add the directory to IPFS
        dir_result = kit.ipfs_add_path(temp_dir)
        if not dir_result:
            logger.error("Failed to add directory to IPFS")
            return
            
        dir_cid = dir_result.get('Hash')
        logger.info(f"Added directory to IPFS with CID: {dir_cid}")
        
        # List directory contents
        listing = fs.ls(dir_cid, detail=True)
        logger.info("Directory contents:")
        for item in listing:
            logger.info(f"  {item['name']} - {item['type']} - {item['size']} bytes")
        
        # Test caching
        logger.info("\n--- Caching Demonstration ---")
        
        # First access hits the API
        logger.info("First access (uncached)...")
        start_time = time.time()
        content1 = fs.cat(cid)
        elapsed1 = time.time() - start_time
        
        # Second access should be faster
        logger.info("Second access (should be cached)...")
        start_time = time.time()
        content2 = fs.cat(cid)
        elapsed2 = time.time() - start_time
        
        logger.info(f"Uncached access: {elapsed1:.6f} seconds")
        logger.info(f"Cached access: {elapsed2:.6f} seconds")
        logger.info(f"Speedup: {elapsed1/elapsed2:.1f}x faster")
        
    finally:
        # Clean up
        os.unlink(test_file_path)
        
        # Clean up the temp directory
        try:
            import shutil
            shutil.rmtree(temp_dir)
        except Exception:
            pass

if __name__ == "__main__":
    import time  # Import here to avoid shadowing the time in speedup calculation
    main()