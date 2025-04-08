#!/usr/bin/env python3
"""
Filesystem Journal Integration Example

This example demonstrates how to integrate the Filesystem Journal with IPFS Kit
to ensure data consistency and recovery in case of unexpected shutdowns or power outages.

The filesystem journal provides transaction-based protection for filesystem operations,
working alongside the Write-Ahead Log (WAL) to ensure data integrity.

Key features demonstrated:
1. Creating a journaled filesystem interface
2. Performing filesystem operations with transaction protection
3. Persisting path-to-CID mappings for virtual filesystem support
4. Recovery after unexpected shutdowns
5. Integration between content-addressed storage and path-based filesystem
"""

import os
import time
import json
import logging
import tempfile
import shutil

from ipfs_kit_py.high_level_api import IPFSSimpleAPI
from ipfs_kit_py.wal import WAL  # Import the Write-Ahead Log

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    # Create a temporary directory for the journal
    temp_dir = tempfile.mkdtemp(prefix="ipfs_journal_example_")
    journal_path = os.path.join(temp_dir, "journal")
    
    try:
        logger.info(f"Using temporary directory for journal: {journal_path}")
        
        # Initialize the IPFS Simple API
        ipfs = IPFSSimpleAPI(role="leecher")
        logger.info("Initialized IPFSSimpleAPI")
        
        # Initialize a WAL (Write-Ahead Log)
        wal = WAL(base_path=os.path.join(temp_dir, "wal"))
        logger.info("Initialized Write-Ahead Log")
        
        # Enable filesystem journaling using the method in IPFSSimpleAPI
        # Note: The high_level_api.py implementation automatically uses self.wal if available
        # We're not setting it here to avoid passing the wal parameter twice
        journaled_fs = ipfs.enable_filesystem_journaling(
            journal_base_path=journal_path,
            auto_recovery=True,
            sync_interval=2,  # Sync to disk every 2 seconds
            checkpoint_interval=30  # Create checkpoint every 30 seconds
        )
        
        # Set the wal attribute on the API instance directly
        ipfs.wal = wal
        logger.info("Enabled filesystem journaling")
        
        # Create a complex directory structure with files
        logger.info("\n--- Creating a virtual filesystem structure ---")
        
        # Create the root directory
        root_dir_result = journaled_fs.create_directory(
            "/virtual_fs", 
            metadata={"description": "Root directory for virtual filesystem"}
        )
        logger.info(f"Root directory created: {root_dir_result['success']}")
        
        # Create subdirectories
        for subdir in ["documents", "images", "data"]:
            dir_path = f"/virtual_fs/{subdir}"
            dir_result = journaled_fs.create_directory(
                dir_path,
                metadata={"category": subdir, "created_at": time.time()}
            )
            logger.info(f"Created directory {dir_path}: {dir_result['success']}")
        
        # Create text files in documents directory
        for i, filename in enumerate(["readme.txt", "notes.txt", "todo.txt"]):
            file_path = f"/virtual_fs/documents/{filename}"
            content = f"This is the content of {filename} (file #{i+1})".encode('utf-8')
            file_result = journaled_fs.create_file(
                file_path,
                content,
                metadata={"type": "text", "size": len(content)}
            )
            # Extract the CID for demonstration
            cid = file_result.get("result", {}).get("cid", "unknown")
            logger.info(f"Created file {file_path} with CID: {cid}")
            
        # Create binary files in images directory (simulated images)
        for i in range(1, 4):
            file_path = f"/virtual_fs/images/image{i}.jpg"
            # Create fake image content (just for demonstration)
            content = b'\x89PNG\r\n\x1a\n' + os.urandom(100)  # Fake PNG header + random data
            file_result = journaled_fs.create_file(
                file_path,
                content,
                metadata={"type": "image", "format": "jpg", "size": len(content)}
            )
            # Extract the CID for demonstration
            cid = file_result.get("result", {}).get("cid", "unknown")
            logger.info(f"Created image file {file_path} with CID: {cid}")
            
        # Create data file with JSON content
        data_path = "/virtual_fs/data/config.json"
        data_content = json.dumps({
            "version": "1.0.0",
            "settings": {
                "max_size": 1024,
                "timeout": 30,
                "features": ["sync", "backup", "compression"]
            }
        }, indent=2).encode('utf-8')
        
        data_result = journaled_fs.create_file(
            data_path,
            data_content,
            metadata={"type": "json", "schema": "config-v1"}
        )
        logger.info(f"Created JSON file {data_path}: {data_result['success']}")
        
        # Demonstrate directory listing by examining the virtual filesystem state
        fs_interface = journaled_fs.journal_manager.fs_interface
        logger.info("\n--- Virtual Filesystem Content ---")
        logger.info("Files:")
        for path, cid in fs_interface.path_to_cid.items():
            metadata = fs_interface.path_metadata.get(path, {})
            logger.info(f"  {path} -> CID: {cid}, Metadata: {metadata}")
            
        logger.info("\nDirectories:")
        for dir_path in fs_interface.directories:
            metadata = fs_interface.path_metadata.get(dir_path, {})
            logger.info(f"  {dir_path}, Metadata: {metadata}")
            
        # Demonstrate filesystem operations
        logger.info("\n--- Performing filesystem operations ---")
        
        # Rename a file
        rename_result = journaled_fs.rename(
            "/virtual_fs/documents/todo.txt", 
            "/virtual_fs/documents/done.txt"
        )
        logger.info(f"Renamed file: {rename_result['success']}")
        
        # Update metadata
        metadata_result = journaled_fs.update_metadata(
            "/virtual_fs/images/image1.jpg",
            {"description": "Logo image", "tags": ["logo", "header"]}
        )
        logger.info(f"Updated metadata: {metadata_result['success']}")
        
        # Create a new directory and move files
        journaled_fs.create_directory("/virtual_fs/archive")
        move_result = journaled_fs.rename(
            "/virtual_fs/documents/notes.txt",
            "/virtual_fs/archive/old_notes.txt"
        )
        logger.info(f"Moved file to archive: {move_result['success']}")
        
        # Mount an external CID directly (simulating external content)
        # Use a sample CID or create a fake one if no real CIDs available
        dummy_cid = "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"  # Example CID
        try:
            if fs_interface.path_to_cid:
                # Use a real CID if available
                sample_cid = list(fs_interface.path_to_cid.values())[0]
            else:
                # Use dummy CID if no real CIDs are available (e.g., when IPFS isn't running)
                logger.info("No real CIDs available, using a sample CID for demonstration")
                sample_cid = dummy_cid
                
            mount_result = journaled_fs.mount(
                "/virtual_fs/external_content.txt",
                sample_cid,
                is_directory=False,
                metadata={"source": "external", "imported_at": time.time()}
            )
            logger.info(f"Mounted external CID: {mount_result['success']}")
        except Exception as e:
            logger.error(f"Failed to mount external CID: {e}")
        
        # Delete a file
        delete_result = journaled_fs.delete("/virtual_fs/data/config.json")
        logger.info(f"Deleted file: {delete_result['success']}")
        
        # Create checkpoint to persist all operations
        logger.info("\n--- Creating checkpoint ---")
        checkpoint_result = journaled_fs.create_checkpoint()
        logger.info(f"Created checkpoint: {checkpoint_result['success']}")
        
        # Get journal statistics
        stats = journaled_fs.get_journal_stats()
        logger.info(f"Journal statistics: {json.dumps(stats, indent=2)}")
        
        # Simulate a crash recovery scenario
        logger.info("\n--- Simulating unexpected shutdown and recovery ---")
        
        # Close the journal properly (in a real crash this wouldn't happen)
        journaled_fs.close()
        
        # Re-initialize with the same journal path to test recovery
        logger.info("Re-initializing filesystem with journal recovery...")
        
        # Initialize a new journaled filesystem with the same path
        new_ipfs = IPFSSimpleAPI(role="leecher")
        new_wal = WAL(base_path=os.path.join(temp_dir, "wal"))
        
        # Set the WAL attribute directly
        new_ipfs.wal = new_wal
        
        # Enable filesystem journaling
        recovered_fs = new_ipfs.enable_filesystem_journaling(
            journal_base_path=journal_path,
            auto_recovery=True
        )
        
        # Verify recovery was successful
        logger.info("Checking if filesystem was recovered correctly...")
        
        # Get the recovered filesystem interface
        recovered_interface = recovered_fs.journal_manager.fs_interface
        
        # Check the recovered state
        logger.info("\n--- Recovered Filesystem State ---")
        logger.info(f"Recovered {len(recovered_interface.path_to_cid)} files and {len(recovered_interface.directories)} directories")
        
        logger.info("\nRecovered Files:")
        for path, cid in recovered_interface.path_to_cid.items():
            metadata = recovered_interface.path_metadata.get(path, {})
            logger.info(f"  {path} -> CID: {cid}")
            
        logger.info("\nRecovered Directories:")
        for dir_path in recovered_interface.directories:
            metadata = recovered_interface.path_metadata.get(dir_path, {})
            logger.info(f"  {dir_path}")
        
        # Verify we can perform operations on the recovered filesystem
        logger.info("\n--- Testing operations on recovered filesystem ---")
        
        # Create a new file in the recovered filesystem
        new_file_path = "/virtual_fs/recovery_test.txt"
        new_content = b"This file was created after recovery!"
        new_file_result = recovered_fs.create_file(
            new_file_path,
            new_content,
            metadata={"created_after_recovery": True}
        )
        logger.info(f"Created new file after recovery: {new_file_result['success']}")
        
        # Clean up
        logger.info("\nTest completed, cleaning up...")
        recovered_fs.close()
        
    finally:
        # Clean up temporary directory
        try:
            logger.info(f"Removing temporary directory: {temp_dir}")
            shutil.rmtree(temp_dir)
        except Exception as e:
            logger.error(f"Error cleaning up: {e}")

if __name__ == "__main__":
    main()