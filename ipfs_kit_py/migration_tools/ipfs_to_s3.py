"""Migration tool for transferring content from IPFS to S3."""

import logging
import os
import shutil
import tempfile
import time
import uuid

# Configure logger
logger = logging.getLogger(__name__)


class ipfs_to_s3:
    """Migration tool to transfer content from IPFS to S3."""

    def __init__(self, resources=None, metadata=None):
        """Initialize the migration tool.

        Args:
            resources: Dictionary of available resources
            metadata: Additional configuration metadata
        """
        self.resources = resources or {}
        self.metadata = metadata or {}

        # Create temporary directory for file operations
        self.temp_dir = tempfile.mkdtemp(prefix="ipfs_to_s3_")

        # Import dependencies
        from ipfs_kit_py.ipfs import ipfs_py
        from ipfs_kit_py.s3_kit import s3_kit

        # Initialize components
        self.ipfs = ipfs_py(resources, metadata)
        self.s3_kit = s3_kit(resources, metadata)

    def migrate_file(self, cid, bucket, s3_path, file_name=None):
        """Migrate a single file from IPFS to S3.

        Args:
            cid: Content ID to migrate
            bucket: S3 bucket to migrate to
            s3_path: Path in S3 bucket
            file_name: Custom filename to use (optional)

        Returns:
            Dictionary with operation result
        """
        result = {
            "success": False,
            "operation": "migrate_file",
            "timestamp": time.time(),
            "source": {"type": "ipfs", "cid": cid},
            "destination": {"type": "s3", "bucket": bucket, "path": s3_path},
        }

        try:
            # Fetch content from IPFS
            ipfs_result = self.ipfs.ipfs_cat(cid)

            if not ipfs_result.get("success", False):
                result["error"] = ipfs_result.get("error", "Failed to retrieve content from IPFS")
                result["error_type"] = ipfs_result.get("error_type", "ipfs_error")
                return result

            # Get content data
            data = ipfs_result.get("data")

            # Use provided filename or derive from CID
            if file_name is None:
                file_name = cid

            # Save to temporary file
            temp_file_path = os.path.join(self.temp_dir, file_name)
            with open(temp_file_path, "wb") as f:
                f.write(data)

            # Upload to S3
            s3_key = s3_path
            if not s3_key.endswith("/"):
                # Use as full path
                pass
            else:
                # Append filename to directory path
                s3_key = os.path.join(s3_path, file_name)

            # Upload file to S3
            s3_result = self.s3_kit.s3_ul_file(temp_file_path, bucket, s3_key)

            # Verify upload by listing the file
            ls_result = self.s3_kit.s3_ls_file(bucket, s3_key)

            # Update result with success
            result["success"] = True
            result["local_path"] = temp_file_path
            result["s3_result"] = s3_result

        except Exception as e:
            result["success"] = False
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.exception(f"Failed to migrate file {cid} to S3: {e}")

        return result

    def migrate_directory(self, cid, bucket, s3_path):
        """Migrate a directory from IPFS to S3.

        Args:
            cid: Content ID of the directory to migrate
            bucket: S3 bucket to migrate to
            s3_path: Base path in S3 bucket

        Returns:
            Dictionary with operation result
        """
        result = {
            "success": False,
            "operation": "migrate_directory",
            "timestamp": time.time(),
            "source": {"type": "ipfs", "cid": cid},
            "destination": {"type": "s3", "bucket": bucket, "path": s3_path},
            "migrations": [],
        }

        try:
            # List directory contents
            ls_result = self.ipfs.ipfs_ls_path(cid)

            if not ls_result.get("success", False):
                result["error"] = ls_result.get("error", "Failed to list directory contents")
                result["error_type"] = ls_result.get("error_type", "ipfs_error")
                return result

            # Get directory items
            items = ls_result.get("links", [])
            result["total_files"] = len(items)

            # Counters for tracking
            successful = 0
            failed = 0

            # Migrate each file in the directory
            for item in items:
                item_name = item.get("Name")
                item_hash = item.get("Hash")
                item_type = item.get("Type")

                # Skip directories for now (could recursively process in future)
                if item_type == 1:  # Directory
                    continue

                # Create S3 path for this item
                item_s3_path = os.path.join(s3_path, item_name)

                # Migrate the file
                migration_result = self.migrate_file(item_hash, bucket, item_s3_path)
                result["migrations"].append(migration_result)

                if migration_result.get("success", False):
                    successful += 1
                else:
                    failed += 1

            # Update overall success and statistics
            result["successful_migrations"] = successful
            result["failed_migrations"] = failed
            result["success"] = failed == 0  # Only success if all migrations succeeded

        except Exception as e:
            result["success"] = False
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.exception(f"Failed to migrate directory {cid} to S3: {e}")

        return result

    def migrate_by_list(self, cid_list, bucket, s3_path):
        """Migrate a list of files from IPFS to S3.

        Args:
            cid_list: List of CIDs to migrate (strings or dicts with cid and name)
            bucket: S3 bucket to migrate to
            s3_path: Base path in S3 bucket

        Returns:
            Dictionary with operation result
        """
        result = {
            "success": False,
            "operation": "migrate_by_list",
            "timestamp": time.time(),
            "source": {"type": "ipfs", "list_size": len(cid_list)},
            "destination": {"type": "s3", "bucket": bucket, "path": s3_path},
            "migrated_files": [],
        }

        if not cid_list:
            result["success"] = True
            result["warning"] = "Empty CID list provided, nothing to migrate"
            return result

        try:
            # Counters for tracking
            total = len(cid_list)
            successful = 0
            failed = 0

            # Process each CID in the list
            for item in cid_list:
                # Handle different item formats
                if isinstance(item, dict):
                    cid = item.get("cid")
                    name = item.get("name")
                else:
                    cid = item
                    name = item  # Use CID as filename

                # Create S3 path for this item
                item_s3_path = os.path.join(s3_path, name)

                # Migrate the file
                migration_result = self.migrate_file(cid, bucket, item_s3_path)
                result["migrated_files"].append(migration_result)

                if migration_result.get("success", False):
                    successful += 1
                else:
                    failed += 1

            # Update overall success and statistics
            result["total_files"] = total
            result["successful_migrations"] = successful
            result["failed_migrations"] = failed
            result["success"] = failed == 0  # Only success if all migrations succeeded

        except Exception as e:
            result["success"] = False
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.exception(f"Failed to migrate CID list to S3: {e}")

        return result

    def cleanup(self):
        """Clean up temporary resources."""
        try:
            if hasattr(self, "temp_dir") and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
        except Exception as e:
            logger.error(f"Failed to clean up temporary directory: {e}")
