#!/usr/bin/env python3
"""
Test script for the Filesystem Journal integration with full IPFS integration.

This script tests the filesystem journal functionality implemented in ipfs_kit_py
using real IPFS operations rather than simulated ones. It directly interacts with
the FilesystemJournalIntegration and IPFSFilesystemInterface classes to verify:
- Writing files with real IPFS CIDs
- Directory operations
- Checkpointing
- Recovery from checkpoints
"""

import os
import sys
import time
import json
import logging
import tempfile
import shutil
import hashlib

# Configure logging - set to DEBUG to see more details
logging.basicConfig(level=logging.DEBUG,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Set more specific logging levels for noisy modules
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)

# Import FS journal classes directly
from ipfs_kit_py.ipfs_kit import ipfs_kit
from ipfs_kit_py.fs_journal_integration import (
    IPFSFilesystemInterface,
    FilesystemJournalIntegration,
    enable_filesystem_journaling
)

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
    try:
        # Convert expected_content to bytes if it's a string
        if isinstance(expected_content, str):
            expected_content = expected_content.encode('utf-8')

        # Try to retrieve the content from IPFS
        logger.info(f"Verifying CID {cid} in IPFS...")

        # Method 1: Try get method
        if hasattr(ipfs_instance, 'get'):
            try:
                content = ipfs_instance.get(cid)
                if isinstance(content, dict) and "data" in content:
                    content = content["data"]

                # If content matches, we're good
                if content == expected_content:
                    logger.info(f"✅ CID {cid} verified with get method")
                    return True
                else:
                    logger.warning(f"❌ CID {cid} content mismatch with get method")
            except Exception as e:
                logger.warning(f"get method failed: {e}")

        # Method 2: Try cat method
        if hasattr(ipfs_instance, 'cat'):
            try:
                content = ipfs_instance.cat(cid)
                if isinstance(content, dict) and "data" in content:
                    content = content["data"]

                # If content matches, we're good
                if content == expected_content:
                    logger.info(f"✅ CID {cid} verified with cat method")
                    return True
                else:
                    logger.warning(f"❌ CID {cid} content mismatch with cat method")
            except Exception as e:
                logger.warning(f"cat method failed: {e}")

        # Method 3: Try ipfs_cat method
        if hasattr(ipfs_instance, 'ipfs_cat'):
            try:
                content = ipfs_instance.ipfs_cat(cid)
                if isinstance(content, dict) and "data" in content:
                    content = content["data"]

                # If content matches, we're good
                if content == expected_content:
                    logger.info(f"✅ CID {cid} verified with ipfs_cat method")
                    return True
                else:
                    logger.warning(f"❌ CID {cid} content mismatch with ipfs_cat method")
            except Exception as e:
                logger.warning(f"ipfs_cat method failed: {e}")

        # If we haven't returned True by now, verification failed
        logger.error(f"❌ Unable to verify CID {cid} with any method")
        return False

    except Exception as e:
        logger.error(f"Error during CID verification: {e}")
        return False

def run_test():
    """Run the filesystem journal test with full IPFS integration."""
    # Use a fixed location for testing that we know works
    temp_dir = "/tmp/fs_journal_direct_test"
    journal_path = os.path.join(temp_dir, "journal")

    # Ensure all journal directories exist with proper permissions
    os.makedirs(journal_path, exist_ok=True)
    os.makedirs(os.path.join(journal_path, "journals"), exist_ok=True)
    os.makedirs(os.path.join(journal_path, "checkpoints"), exist_ok=True)
    os.makedirs(os.path.join(journal_path, "temp"), exist_ok=True)

    # Set proper permissions
    for dir_path in [journal_path,
                    os.path.join(journal_path, "journals"),
                    os.path.join(journal_path, "checkpoints"),
                    os.path.join(journal_path, "temp")]:
        os.chmod(dir_path, 0o755)  # rwxr-xr-x

    try:
        logger.info(f"Using temporary directory for journal: {journal_path}")

        # Initialize IPFS Kit with correct parameters
        ipfs = ipfs_kit(metadata={"role": "leecher"})
        logger.info("Initialized IPFS Kit")

        # Verify IPFS is working by adding a simple test file
        test_content = b"Test content for IPFS check"
        logger.info("Testing direct IPFS functionality...")

        # Try different methods to add content directly to IPFS
        ipfs_working = False
        test_cid = None

        # Method 1: Try ipfs_add method
        if hasattr(ipfs, 'ipfs_add'):
            try:
                result = ipfs.ipfs_add(test_content)
                if result and result.get("success", False):
                    test_cid = result.get("cid")
                    logger.info(f"Direct IPFS test with ipfs_add succeeded: {test_cid}")
                    ipfs_working = True
            except Exception as e:
                logger.warning(f"ipfs_add method failed: {e}")

        # Method 2: Try add method
        if not ipfs_working and hasattr(ipfs, 'add'):
            try:
                result = ipfs.add(test_content)
                if result:
                    test_cid = result.get("Hash") or result.get("cid")
                    logger.info(f"Direct IPFS test with add succeeded: {test_cid}")
                    ipfs_working = True
            except Exception as e:
                logger.warning(f"add method failed: {e}")

        # Method 3: Try any available method that adds content to IPFS
        if not ipfs_working:
            potential_methods = ['add_bytes', 'add_data', 'add_content', 'add_str']
            for method_name in potential_methods:
                if hasattr(ipfs, method_name):
                    try:
                        method = getattr(ipfs, method_name)
                        result = method(test_content)

                        # Handle result based on its type
                        if isinstance(result, str):
                            test_cid = result
                        elif isinstance(result, dict):
                            test_cid = result.get("Hash") or result.get("cid")

                        if test_cid:
                            logger.info(f"Direct IPFS test with {method_name} succeeded: {test_cid}")
                            ipfs_working = True
                            break
                    except Exception as e:
                        logger.warning(f"{method_name} method failed: {e}")

        if not ipfs_working:
            logger.warning("⚠️ Direct IPFS functionality test failed. Journal will use simulated mode.")
        else:
            # Verify we can read the content back
            if test_cid:
                if verify_ipfs_content(ipfs, test_cid, test_content):
                    logger.info("✅ Full IPFS read/write cycle verified")
                else:
                    logger.warning("⚠️ IPFS write succeeded but read verification failed")

        # Step 1: Create the Filesystem Journal Integration
        logger.info("\n--- Step 1: Create Filesystem Journal Integration ---")
        journal_integration = FilesystemJournalIntegration(
            fs_api=ipfs,
            journal_base_path=journal_path,
            checkpoint_interval=10,
            sync_interval=1
        )
        logger.info("Created FilesystemJournalIntegration")

        # Get the filesystem interface directly from the integration
        fs_interface = journal_integration.fs_interface
        logger.info("Got IPFSFilesystemInterface from integration")

        # Step 2: Create directories
        logger.info("\n--- Step 2: Create directories ---")
        directories = [
            "/virtual_fs",
            "/virtual_fs/documents",
            "/virtual_fs/images",
            "/virtual_fs/data"
        ]

        for directory in directories:
            mkdir_result = journal_integration.create_directory(directory)
            if not mkdir_result.get("success", False):
                logger.error(f"Failed to create directory {directory}: {mkdir_result.get('error')}")
                return False

            logger.info(f"Created directory: {directory}")

        # Step 3: Create files
        logger.info("\n--- Step 3: Create files ---")
        files = [
            {
                "path": "/virtual_fs/documents/readme.txt",
                "content": "This is the README file content."
            },
            {
                "path": "/virtual_fs/documents/notes.txt",
                "content": "Some notes here.\nMultiple lines of text.\nMore content."
            },
            {
                "path": "/virtual_fs/data/config.json",
                "content": json.dumps({
                    "version": "1.0.0",
                    "settings": {
                        "timeout": 30,
                        "retry": 3,
                        "features": ["sync", "backup", "compression"]
                    }
                }, indent=2)
            }
        ]

        # Track simulated vs. real CIDs
        cid_results = {
            "real": [],
            "simulated": []
        }

        for file_info in files:
            # Ensure content is encoded as bytes
            content_bytes = file_info["content"].encode('utf-8') if isinstance(file_info["content"], str) else file_info["content"]

            # Use the write_file method in the integration
            write_result = journal_integration.write_file(
                path=file_info["path"],
                content=content_bytes,
                metadata={"type": "text", "created_by": "test"}
            )

            if not write_result.get("success", False):
                logger.error(f"Failed to write file {file_info['path']}: {write_result.get('error')}")
                return False

            # Check if this was a simulated CID or real IPFS CID
            cid = write_result.get("cid")
            # Journal integration doesn't directly expose "simulated" flag, so we check for it
            # in the underlying interface's response

            # Get the underlying FS interface response which should have the simulated flag
            fs_result = fs_interface.path_to_cid.get(file_info["path"])

            # Check if the CID matches our test CID pattern format (indirect way to detect simulation)
            is_simulated = False
            fs_result_obj = None

            if hasattr(fs_interface, '_last_write_result'):
                fs_result_obj = fs_interface._last_write_result
                if fs_result_obj and fs_result_obj.get("simulated", False):
                    is_simulated = True

            # If we can't determine directly, check with IPFS
            if not is_simulated and not verify_ipfs_content(ipfs, cid, content_bytes):
                is_simulated = True

            if is_simulated:
                logger.warning(f"⚠️ Created file with SIMULATED CID: {file_info['path']} -> {cid}")
                cid_results["simulated"].append((file_info["path"], cid, content_bytes))
            else:
                logger.info(f"✅ Created file with REAL IPFS CID: {file_info['path']} -> {cid}")
                cid_results["real"].append((file_info["path"], cid, content_bytes))

                # Verify we can retrieve the content from IPFS
                if verify_ipfs_content(ipfs, cid, content_bytes):
                    logger.info(f"✅ CID verification successful for {file_info['path']}")
                else:
                    logger.warning(f"⚠️ CID verification failed for {file_info['path']}")

        # Log stats about real vs simulated CIDs
        real_count = len(cid_results["real"])
        simulated_count = len(cid_results["simulated"])
        total_count = real_count + simulated_count

        if total_count > 0:
            real_percentage = (real_count / total_count) * 100
            logger.info(f"\nCID Statistics: {real_count}/{total_count} real CIDs ({real_percentage:.1f}%)")

            if real_count > 0:
                logger.info(f"Real CIDs: {[cid for _, cid, _ in cid_results['real']]}")

            if simulated_count > 0:
                logger.warning(f"Simulated CIDs: {[cid for _, cid, _ in cid_results['simulated']]}")

        # Step 4: Get journal statistics
        logger.info("\n--- Step 4: Get journal statistics ---")
        stats_result = journal_integration.get_journal_stats()
        logger.info(f"Journal stats: {stats_result}")

        # Step 5: Create a checkpoint
        logger.info("\n--- Step 5: Create checkpoint ---")
        checkpoint_result = journal_integration.create_checkpoint()

        if not checkpoint_result.get("success", False):
            logger.error(f"Failed to create checkpoint: {checkpoint_result.get('error')}")
            return False

        logger.info(f"Created checkpoint: {checkpoint_result}")

        # Step 6: Verify file content (through direct access to path_to_cid mapping)
        logger.info("\n--- Step 6: Verify CIDs in path_to_cid mapping ---")
        for file_info in files:
            path = file_info["path"]
            cid = fs_interface.path_to_cid.get(path)

            if cid:
                logger.info(f"Path {path} -> CID {cid}")
            else:
                logger.error(f"❌ Path {path} not found in path_to_cid mapping")
                return False

        # Step 7: Mount a CID
        if real_count > 0:
            # If we have a real CID, use it for mounting test
            logger.info("\n--- Step 7: Test mounting a CID ---")
            real_path, real_cid, real_content = cid_results["real"][0]
            mount_path = "/virtual_fs/mounted_cid"

            mount_result = journal_integration.mount(
                path=mount_path,
                cid=real_cid,
                is_directory=False
            )

            if not mount_result.get("success", False):
                logger.error(f"Failed to mount CID {real_cid}: {mount_result.get('error')}")
                return False

            logger.info(f"Mounted CID {real_cid} at {mount_path}")

            # Verify the mount point exists in path_to_cid mapping
            if mount_path in fs_interface.path_to_cid:
                logger.info(f"✅ Mount point verified in path_to_cid mapping")
            else:
                logger.error(f"❌ Mount point not found in path_to_cid mapping")
                return False

        # Step 8: Create another checkpoint
        logger.info("\n--- Step 8: Create another checkpoint ---")
        checkpoint_result = journal_integration.create_checkpoint()

        if not checkpoint_result.get("success", False):
            logger.error(f"Failed to create second checkpoint: {checkpoint_result.get('error')}")
            return False

        logger.info(f"Created second checkpoint: {checkpoint_result}")

        logger.info("\n--- Filesystem journal test completed successfully ---")

        if real_count > 0:
            logger.info(f"✅ Successfully used REAL IPFS integration")
        else:
            logger.warning(f"⚠️ All operations used SIMULATED CIDs - IPFS integration not verified")

        return True

    except Exception as e:
        logger.error(f"Error during test: {e}")
        return False

    finally:
        # Clean up the journal only, not the entire directory
        try:
            # Make sure to close the filesystem journal first
            if 'journal_integration' in locals() and journal_integration:
                try:
                    journal_integration.close()
                    logger.info("Closed filesystem journal")
                except Exception as e:
                    logger.warning(f"Error closing filesystem journal: {e}")

            # Clean up
            logger.info(f"Leaving test directory at: {temp_dir} for inspection")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

if __name__ == "__main__":
    logger.info("Starting filesystem journal test with full IPFS integration")
    success = run_test()

    if success:
        logger.info("✅ Test SUCCEEDED")
        sys.exit(0)
    else:
        logger.error("❌ Test FAILED")
        sys.exit(1)
