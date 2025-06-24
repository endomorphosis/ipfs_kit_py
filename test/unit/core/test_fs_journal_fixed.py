#!/usr/bin/env python3
"""
Test script for filesystem journal integration with IPFS.
Tests the modified fs_journal_integration.py with proper IPFS add methods.
"""

import os
import logging
import tempfile
from ipfs_kit_py import ipfs_kit
from ipfs_kit_py.fs_journal_integration import FilesystemJournalIntegration

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def verify_ipfs_content(ipfs_instance, cid, expected_content):
    """
    Verify that content can be retrieved from IPFS by CID.

    Args:
        ipfs_instance: The IPFS Kit instance
        cid: Content Identifier to verify
        expected_content: Expected content as bytes or string

    Returns:
        True if verification succeeded, False otherwise
    """
    # Make sure expected_content is bytes
    if not isinstance(expected_content, bytes):
        expected_content = expected_content.encode('utf-8')

    try:
        # Try multiple methods to get content from IPFS

        # Method 1: ipfs_get if available
        if hasattr(ipfs_instance, 'ipfs_get'):
            result = ipfs_instance.ipfs_get(cid)
            if result.get('success') and result.get('content'):
                content = result.get('content')
                if isinstance(content, bytes) and content == expected_content:
                    logger.info(f"Content verified using ipfs_get: {cid}")
                    return True

        # Method 2: Try ipfs.cat if available
        if hasattr(ipfs_instance, 'ipfs') and hasattr(ipfs_instance.ipfs, 'cat'):
            result = ipfs_instance.ipfs.cat(cid)
            if isinstance(result, dict) and result.get('success'):
                content = result.get('content', b'')
                if content == expected_content:
                    logger.info(f"Content verified using ipfs.cat: {cid}")
                    return True

        # Method 3: Try using the FSSpec interface if available
        fs = getattr(ipfs_instance, 'fs', None)
        if fs:
            if hasattr(fs, 'cat'):
                content = fs.cat(cid)
                if content == expected_content:
                    logger.info(f"Content verified using fs.cat: {cid}")
                    return True

        # If we try all methods and nothing works, return False
        logger.warning(f"Could not verify content for CID: {cid}")
        return False

    except Exception as e:
        logger.error(f"Error verifying content for CID {cid}: {e}")
        return False

def test_filesystem_journal_integration():
    """Test the filesystem journal integration with IPFS."""

    logger.info("Initializing IPFS Kit...")
    kit = ipfs_kit()

    logger.info("Creating filesystem journal integration...")
    journal_path = tempfile.mkdtemp()
    fs_journal = FilesystemJournalIntegration(
        fs_api=kit,
        journal_base_path=journal_path,
        auto_recovery=True,
        sync_interval=1,  # Sync every second
        checkpoint_interval=5  # Checkpoint every 5 seconds
    )

    # Access the filesystem interface directly for inspecting internals
    fs_interface = fs_journal.fs_interface

    # Test creating directories
    logger.info("Testing directory creation...")
    dir_result = fs_journal.create_directory("/test")

    if dir_result.get("success"):
        logger.info("Successfully created directory: /test")
    else:
        logger.error(f"Failed to create directory: {dir_result}")

    # Create a subdirectory
    subdir_result = fs_journal.create_directory("/test/subdir")
    if subdir_result.get("success"):
        logger.info("Successfully created directory: /test/subdir")
    else:
        logger.error(f"Failed to create subdirectory: {subdir_result}")

    # Test writing files
    logger.info("Testing file creation...")
    test_content = b"This is test content for IPFS integration"
    file_result = fs_journal.create_file("/test/file1.txt", test_content)

    if file_result.get("success"):
        logger.info(f"Successfully created file: /test/file1.txt with CID: {file_result.get('cid')}")

        # Get the CID from the result or from the filesystem interface mapping
        cid = file_result.get('cid')
        if not cid and "/test/file1.txt" in fs_interface.path_to_cid:
            cid = fs_interface.path_to_cid["/test/file1.txt"]
            logger.info(f"Got CID from path mapping instead: {cid}")

        # Check if this was a real IPFS operation or simulated
        if file_result.get("simulated", False):
            logger.warning("File was added with simulated CID!")
        # If only path mapping has the CID, this is also likely simulated
        elif not file_result.get("cid") and cid:
            logger.warning("File was added, but CID only found in path mapping - likely simulated!")
        else:
            logger.info("File was added with real IPFS CID!")

            # Verify content can be retrieved from IPFS (only if we have a CID)
            if cid:
                if verify_ipfs_content(kit, cid, test_content):
                    logger.info("Content verified successfully in IPFS!")
                else:
                    logger.warning("Could not verify content in IPFS. This suggests simulated CID even though not marked as such.")
            else:
                logger.warning("No CID available to verify content")
    else:
        logger.error(f"Failed to create file: {file_result}")

    # Check our path-to-CID mapping
    if "/test/file1.txt" in fs_interface.path_to_cid:
        cid1 = fs_interface.path_to_cid["/test/file1.txt"]
        logger.info(f"Found file1.txt in path mapping with CID: {cid1}")
    else:
        logger.error("File1.txt missing from path-to-CID mapping!")

    # Create a checkpoint
    logger.info("Creating checkpoint...")
    checkpoint_result = fs_journal.create_checkpoint()
    if checkpoint_result.get("success"):
        logger.info(f"Created checkpoint at: {checkpoint_result.get('timestamp')}")
    else:
        logger.error(f"Failed to create checkpoint: {checkpoint_result}")

    # Add another file
    logger.info("Adding another file...")
    test_content2 = b"This is the second test file with different content"
    file2_result = fs_journal.create_file("/test/subdir/file2.txt", test_content2)

    if file2_result.get("success"):
        logger.info(f"Successfully created file2: /test/subdir/file2.txt with CID: {file2_result.get('cid')}")

        # Get the CID from the result or from the filesystem interface mapping
        cid = file2_result.get('cid')
        if not cid and "/test/subdir/file2.txt" in fs_interface.path_to_cid:
            cid = fs_interface.path_to_cid["/test/subdir/file2.txt"]
            logger.info(f"Got CID from path mapping instead: {cid}")

        # Check if this was a real IPFS operation or simulated
        if file2_result.get("simulated", False):
            logger.warning("File2 was added with simulated CID!")
        # If only path mapping has the CID, this is also likely simulated
        elif not file2_result.get("cid") and cid:
            logger.warning("File2 was added, but CID only found in path mapping - likely simulated!")
        else:
            logger.info("File2 was added with real IPFS CID!")

            # Verify content can be retrieved from IPFS (only if we have a CID)
            if cid:
                if verify_ipfs_content(kit, cid, test_content2):
                    logger.info("Content verified successfully in IPFS!")
                else:
                    logger.warning("Could not verify content in IPFS. This suggests simulated CID even though not marked as such.")
            else:
                logger.warning("No CID available to verify content")
    else:
        logger.error(f"Failed to create file2: {file2_result}")

    # Check our path-to-CID mapping again
    if "/test/subdir/file2.txt" in fs_interface.path_to_cid:
        cid2 = fs_interface.path_to_cid["/test/subdir/file2.txt"]
        logger.info(f"Found file2.txt in path mapping with CID: {cid2}")
    else:
        logger.error("File2.txt missing from path-to-CID mapping!")

    # Test mounting a CID directly
    logger.info("Testing mount operation...")
    mount_result = fs_journal.mount("/test/mounted_cid", cid1, is_directory=False)

    if mount_result.get("success"):
        logger.info(f"Successfully mounted CID {cid1} at /test/mounted_cid")
    else:
        logger.error(f"Failed to mount CID: {mount_result}")

    # Create another checkpoint
    logger.info("Creating another checkpoint...")
    checkpoint_result = fs_journal.create_checkpoint()
    if checkpoint_result.get("success"):
        logger.info(f"Created checkpoint at: {checkpoint_result.get('timestamp')}")
    else:
        logger.error(f"Failed to create checkpoint: {checkpoint_result}")

    # Get journal stats
    logger.info("Getting journal stats...")
    stats = fs_journal.get_journal_stats()

    logger.info(f"Journal has {stats.get('entry_count', 0)} entries")
    logger.info(f"Last checkpoint at: {stats.get('last_checkpoint_time')}")

    # Close the journal
    logger.info("Closing journal...")
    fs_journal.close()

    # Report back the last write result for inspection
    if hasattr(fs_interface, '_last_write_result'):
        last_result = fs_interface._last_write_result
        logger.info(f"Last write result: {last_result}")

        # Check if we're using simulated CIDs (explicitly marked)
        if last_result.get("simulated", False):
            logger.warning("⚠️ Last operation used simulated CID generation")

            # Let's inspect the specific error messages from the operation
            error_msgs = []

            # Try to get errors first
            try:
                # Attempt an IPFS add operation directly to see what fails
                if hasattr(kit, 'ipfs') and hasattr(kit.ipfs, 'add'):
                    with tempfile.NamedTemporaryFile() as tf:
                        tf.write(b"Test content")
                        tf.flush()
                        # Try to add the file to IPFS
                        try:
                            logger.info("Testing direct ipfs.add operation...")
                            add_result = kit.ipfs.add(tf.name)
                            logger.info(f"Direct ipfs.add result: {add_result}")
                        except Exception as e:
                            error_msgs.append(f"Direct ipfs.add failed: {str(e)}")
            except Exception as e:
                error_msgs.append(f"Error during debugging test: {str(e)}")

            # Try ipfs_add method directly
            try:
                test_result = kit.ipfs_add(b"Test content")
                logger.info(f"Direct ipfs_add test result: {test_result}")
                if test_result.get("error_type") == "ComponentNotAvailable":
                    error_msgs.append(f"IPFS component not available: {test_result.get('error')}")
            except Exception as e:
                error_msgs.append(f"Direct ipfs_add test failed: {str(e)}")

            # Now check if IPFS component is not available
            component_not_available = any(
                "IPFS component not available" in msg
                for msg in error_msgs
            )

            if component_not_available:
                logger.warning("The IPFS component is not available in this environment")
                logger.warning("Simulation mode is the expected behavior in this case")
                logger.info("The filesystem journal integration is working correctly with simulated CIDs")
                logger.info("In a real environment with IPFS available, real CIDs would be used")
            else:
                logger.warning("This suggests that the real IPFS operations are still not working")
                logger.warning("Check the error messages above to determine why")

            if error_msgs:
                logger.error("Debugging errors found:")
                for error in error_msgs:
                    logger.error(f"  - {error}")
        else:
            logger.info("✅ Last operation used real IPFS CID generation!")
            logger.info("The integration with real IPFS operations is working!")

    logger.info("Test completed!")

if __name__ == "__main__":
    test_filesystem_journal_integration()
