"""
Migration tool for transferring content from S3 to Storacha/Web3.Storage.

This module provides utilities to migrate content from S3-compatible storage
to Storacha (Web3.Storage) for content-addressed storage.
"""

import logging
import os
import tempfile
import time
from typing import Any, Dict, List, Optional, Union

# Configure logger
logger = logging.getLogger(__name__)


class s3_to_storacha:
    """Migration tool to transfer content from S3 to Storacha.

    This class provides methods to download content from S3-compatible storage
    and upload it to Storacha (Web3.Storage) for content-addressed storage.
    """

    def __init__(self, resources=None, metadata=None):
        """Initialize the migration tool.

        Args:
            resources: Dictionary of available resources (e.g., memory, CPU limits)
            metadata: Dictionary of configuration metadata
        """
        self.resources = resources or {}
        self.metadata = metadata or {}

        # Import required components
        from ipfs_kit_py.s3_kit import s3_kit
        from ipfs_kit_py.storacha_kit import storacha_kit

        # Initialize components
        self.s3_kit = s3_kit(resources, metadata)
        self.storacha_kit = storacha_kit(resources, metadata)

        # Set up temporary directory for transfers
        self.temp_dir = tempfile.mkdtemp(prefix="s3_to_storacha_")
        logger.info(f"Initialized s3_to_storacha migration tool with temp dir: {self.temp_dir}")

    def migrate_file(self, s3_key: str, space_name: Optional[str] = None) -> Dict[str, Any]:
        """Migrate a single file from S3 to Storacha.

        Args:
            s3_key: The key of the file in S3
            space_name: Optional name of the Storacha space to upload to

        Returns:
            Dictionary with migration results
        """
        logger.info(f"Migrating file from S3: {s3_key}")

        result = {
            "success": False,
            "operation": "migrate_file",
            "s3_key": s3_key,
            "timestamp": time.time(),
        }

        try:
            # Download from S3
            download_result = self.s3_kit.s3_dl_file(
                s3_key, os.path.join(self.temp_dir, os.path.basename(s3_key))
            )

            if not download_result.get("success", False):
                result["error"] = (
                    f"Failed to download from S3: {download_result.get('error', 'Unknown error')}"
                )
                result["error_type"] = "s3_download_error"
                return result

            local_path = download_result.get("local_path")

            # Upload to Storacha
            upload_result = self.storacha_kit.store_add(local_path)

            if not upload_result.get("success", False):
                result["error"] = (
                    f"Failed to upload to Storacha: {upload_result.get('error', 'Unknown error')}"
                )
                result["error_type"] = "storacha_upload_error"
                return result

            # Add to space if specified
            if space_name and upload_result.get("cid"):
                space_result = self.storacha_kit.space_add_cids(space_name, [upload_result["cid"]])

                result["space_result"] = space_result

            # Success!
            result["success"] = True
            result["s3_metadata"] = download_result
            result["storacha_metadata"] = upload_result
            result["cid"] = upload_result.get("cid")

            logger.info(f"Successfully migrated file {s3_key} to CID {result.get('cid')}")

        except Exception as e:
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.error(f"Error migrating file {s3_key}: {e}")

        finally:
            # Clean up the local file
            try:
                local_path = download_result.get("local_path", "")
                if local_path and os.path.exists(local_path):
                    os.unlink(local_path)
            except Exception as e:
                logger.warning(f"Error cleaning up temporary file: {e}")

        return result

    def migrate_directory(self, s3_prefix: str, space_name: Optional[str] = None) -> Dict[str, Any]:
        """Migrate all files under an S3 prefix to Storacha.

        Args:
            s3_prefix: The prefix/directory in S3 to migrate
            space_name: Optional name of the Storacha space to upload to

        Returns:
            Dictionary with migration results
        """
        logger.info(f"Migrating directory from S3: {s3_prefix}")

        result = {
            "success": False,
            "operation": "migrate_directory",
            "s3_prefix": s3_prefix,
            "timestamp": time.time(),
            "files_migrated": 0,
            "files_failed": 0,
            "file_results": {},
        }

        try:
            # List files in S3 directory
            list_result = self.s3_kit.s3_ls_dir(s3_prefix)

            if not isinstance(list_result, list):
                result["error"] = (
                    f"Failed to list S3 directory: {list_result.get('error', 'Invalid response')}"
                )
                result["error_type"] = "s3_list_error"
                return result

            if not list_result:
                result["success"] = True
                result["warning"] = "No files found in S3 directory"
                return result

            # Process each file
            for file_info in list_result:
                if not isinstance(file_info, dict) or "key" not in file_info:
                    result["files_failed"] += 1
                    continue

                s3_key = file_info["key"]
                file_result = self.migrate_file(s3_key, space_name)

                # Store the result
                result["file_results"][s3_key] = file_result

                if file_result.get("success", False):
                    result["files_migrated"] += 1
                else:
                    result["files_failed"] += 1

            # Overall success if any files migrated
            result["success"] = result["files_migrated"] > 0

            logger.info(
                f"Migration complete: {result['files_migrated']} files migrated, "
                f"{result['files_failed']} files failed"
            )

        except Exception as e:
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.error(f"Error migrating directory {s3_prefix}: {e}")

        return result

    def migrate_by_list(
        self, s3_keys: List[str], space_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Migrate a list of files from S3 to Storacha.

        Args:
            s3_keys: List of S3 keys to migrate
            space_name: Optional name of the Storacha space to upload to

        Returns:
            Dictionary with migration results
        """
        logger.info(f"Migrating list of {len(s3_keys)} files from S3")

        result = {
            "success": False,
            "operation": "migrate_by_list",
            "s3_key_count": len(s3_keys),
            "timestamp": time.time(),
            "files_migrated": 0,
            "files_failed": 0,
            "file_results": {},
            "cids": [],
        }

        if not s3_keys:
            result["success"] = True
            result["warning"] = "No files provided in the list"
            return result

        try:
            # Process each file in the list
            for s3_key in s3_keys:
                file_result = self.migrate_file(s3_key, space_name)

                # Store the result
                result["file_results"][s3_key] = file_result

                if file_result.get("success", False):
                    result["files_migrated"] += 1
                    if "cid" in file_result:
                        result["cids"].append(file_result["cid"])
                else:
                    result["files_failed"] += 1

            # Overall success if any files migrated
            result["success"] = result["files_migrated"] > 0

            logger.info(
                f"List migration complete: {result['files_migrated']} files migrated, "
                f"{result['files_failed']} files failed"
            )

        except Exception as e:
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.error(f"Error during list migration: {e}")

        return result

    def cleanup(self):
        """Clean up temporary resources used by the migration tool."""
        try:
            # Remove temporary directory
            import shutil

            if hasattr(self, "temp_dir") and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                logger.info(f"Cleaned up temporary directory: {self.temp_dir}")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def __del__(self):
        """Destructor to ensure cleanup."""
        try:
            self.cleanup()
        except Exception:
            # Suppress exceptions during garbage collection
            pass
