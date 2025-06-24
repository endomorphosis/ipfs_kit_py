#!/usr/bin/env python3
"""
Debug script for the Filesystem Journal integration in the IPFS Kit.

This script isolates the issue with writing files to the filesystem journal.
"""

import os
import time
import json
import logging
from typing import Dict, Any, Optional, Union

# Configure logging
logging.basicConfig(level=logging.DEBUG,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import the necessary modules
from ipfs_kit_py.ipfs_kit import ipfs_kit
from ipfs_kit_py.fs_journal_integration import FilesystemJournalIntegration, IPFSFilesystemInterface
from ipfs_kit_py.filesystem_journal import FilesystemJournal, FilesystemJournalManager

def debug_fs_journal():
    """Debug the filesystem journal integration."""
    # Create directories for the journal
    journal_path = "/tmp/fs_journal_debug"
    os.makedirs(journal_path, exist_ok=True)
    os.makedirs(os.path.join(journal_path, "journals"), exist_ok=True)
    os.makedirs(os.path.join(journal_path, "checkpoints"), exist_ok=True)
    os.makedirs(os.path.join(journal_path, "temp"), exist_ok=True)

    # Initialize IPFS Kit
    api = ipfs_kit(metadata={"role": "leecher"})
    logger.info("Initialized IPFS Kit")

    # Create the filesystem journal
    journal = FilesystemJournal(
        base_path=journal_path,
        sync_interval=5,
        checkpoint_interval=60,
        max_journal_size=1000,
        auto_recovery=True
    )
    logger.info("Created FilesystemJournal")

    # Create the filesystem interface
    fs_interface = IPFSFilesystemInterface(api)
    logger.info("Created IPFSFilesystemInterface")

    # Create the journal manager
    journal_manager = FilesystemJournalManager(
        journal=journal,
        fs_interface=fs_interface
    )
    logger.info("Created FilesystemJournalManager")

    try:
        # Debug the journal manager operations
        logger.info("Testing write_file operation...")

        # Try writing with string content
        string_content = "This is a test string"
        logger.info(f"Writing string content (type: {type(string_content)})")

        # Debug the IPFSFilesystemInterface.write_file method directly
        result1 = fs_interface.write_file(
            path="/test/file1.txt",
            content=string_content.encode('utf-8'),
            metadata={"type": "text"}
        )
        logger.info(f"Direct fs_interface.write_file result: {result1}")

        # Try writing with bytes content directly
        bytes_content = b"This is a test bytes content"
        logger.info(f"Writing bytes content (type: {type(bytes_content)})")
        result2 = fs_interface.write_file(
            path="/test/file2.txt",
            content=bytes_content,
            metadata={"type": "text"}
        )
        logger.info(f"Direct fs_interface.write_file with bytes result: {result2}")

        # Test through the journal manager
        logger.info("Testing writing through journal manager...")
        result3 = journal_manager.write_file(
            path="/test/file3.txt",
            content="This is a test through journal manager".encode('utf-8'),
            metadata={"type": "text"}
        )
        logger.info(f"Journal manager write_file result: {result3}")

        # Create a directory
        logger.info("Testing create_directory...")
        result4 = journal_manager.create_directory(
            path="/test/subdir",
            metadata={"type": "directory"}
        )
        logger.info(f"Create directory result: {result4}")

        # Create a checkpoint
        logger.info("Creating a checkpoint...")
        checkpoint_success = journal.create_checkpoint()
        logger.info(f"Checkpoint created: {checkpoint_success}")

        return True

    except Exception as e:
        logger.error(f"Error during debug: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

    finally:
        # Close resources
        if journal:
            journal.close()
            logger.info("Closed journal")

if __name__ == "__main__":
    success = debug_fs_journal()
    exit(0 if success else 1)
