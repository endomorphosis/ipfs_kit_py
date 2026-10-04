"""Migration tool for transferring content from Storacha to S3."""

import logging
import os
import shutil
import tempfile
import time
from typing import Any, Dict, List, Optional

# Import dependencies at module level for easier testing
from ipfs_kit_py.s3_kit import s3_kit
from ipfs_kit_py.storacha_kit import storacha_kit

# Set up logging
logger = logging.getLogger(__name__)


class storacha_to_s3:
    """Migration tool to transfer content from Storacha to S3."""

    def __init__(self, resources=None, metadata=None):
        """Initialize the migration tool.

        Args:
            resources: Dictionary of resource constraints
            metadata: Dictionary of metadata for operation
        """
        self.resources = resources or {}
        self.metadata = metadata or {}

        # Initialize components
        self.s3_kit = s3_kit(resources, metadata)
        self.storacha_kit = storacha_kit(resources, metadata)

        # Create temporary directory for file operations
        self.temp_dir = tempfile.mkdtemp(prefix="storacha_to_s3_")
        logger.debug(f"Created temporary directory: {self.temp_dir}")

    def migrate_file(self, space_id: str, cid: str, bucket: str, s3_path: str) -> Dict[str, Any]:
        """Migrate a single file from Storacha to S3.

        Args:
            space_id: Storacha space ID
            cid: Content identifier of the file in Storacha
            bucket: S3 bucket to store the file
            s3_path: Path within the S3 bucket

        Returns:
            Dictionary with operation status and details
        """
        result = {
            "success": False,
            "operation": "migrate_file",
            "timestamp": time.time(),
            "source": {"type": "storacha", "space": space_id, "cid": cid},
            "destination": {"type": "s3", "bucket": bucket, "path": s3_path},
        }

        try:
            # Fetch the file from Storacha
            storacha_result = self.storacha_kit.store_get(space_id, cid)

            if not storacha_result.get("success", False):
                error_msg = storacha_result.get("error", "Unknown error downloading from Storacha")
                result["error"] = error_msg
                result["error_type"] = "storacha_download_failed"
                logger.error(f"Failed to download from Storacha: {error_msg}")
                return result

            # Get the local file path
            local_file_path = storacha_result.get("output_file")
            if not local_file_path or not os.path.exists(local_file_path):
                result["error"] = "Downloaded file not found"
                result["error_type"] = "file_not_found"
                logger.error("File downloaded from Storacha not found")
                return result

            # Upload the file to S3
            s3_result = self.s3_kit.s3_ul_file(bucket, local_file_path, s3_path)

            if not s3_result:
                result["error"] = "Failed to upload file to S3"
                result["error_type"] = "s3_upload_failed"
                logger.error(f"Failed to upload {s3_path} to S3")
                return result

            # Verify the file was uploaded
            s3_verify = self.s3_kit.s3_ls_file(bucket, s3_path)

            if not s3_verify:
                result["error"] = "Failed to verify file in S3"
                result["error_type"] = "s3_verification_failed"
                logger.error(f"Failed to verify {s3_path} in S3")
                return result

            # Update result with success information
            result["success"] = True
            result["s3_file_info"] = s3_result

        except Exception as e:
            result["success"] = False
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.exception(f"Failed to migrate file from Storacha to S3: {e}")

        return result

    def migrate_directory(
        self, space_id: str, cid: str, bucket: str, s3_prefix: str = ""
    ) -> Dict[str, Any]:
        """Migrate a directory from Storacha to S3.

        Args:
            space_id: Storacha space ID
            cid: Content identifier of the directory in Storacha
            bucket: S3 bucket to store the files
            s3_prefix: Prefix path within the S3 bucket

        Returns:
            Dictionary with operation status and details
        """
        result = {
            "success": False,
            "operation": "migrate_directory",
            "timestamp": time.time(),
            "source": {"type": "storacha", "space": space_id, "directory_cid": cid},
            "destination": {"type": "s3", "bucket": bucket, "prefix": s3_prefix},
            "file_results": [],
            "total_files": 0,
            "successful_migrations": 0,
            "failed_migrations": 0,
        }

        try:
            # List files in the Storacha directory
            storacha_ls_result = self.storacha_kit.store_ls(space_id, cid)

            if not storacha_ls_result.get("success", False):
                error_msg = storacha_ls_result.get(
                    "error", "Unknown error listing files in Storacha"
                )
                result["error"] = error_msg
                result["error_type"] = "storacha_list_failed"
                logger.error(f"Failed to list files in Storacha: {error_msg}")
                return result

            files = storacha_ls_result.get("files", [])
            result["total_files"] = len(files)

            if not files:
                result["success"] = True
                result["warning"] = "No files found in directory"
                return result

            # Migrate each file
            for file_info in files:
                file_cid = file_info.get("cid")
                file_name = file_info.get("name")

                if not file_cid or not file_name:
                    result["failed_migrations"] += 1
                    result["file_results"].append(
                        {
                            "success": False,
                            "error": "Invalid file info (missing cid or name)",
                            "file_info": file_info,
                        }
                    )
                    continue

                # Construct S3 path for this file
                s3_file_path = os.path.join(s3_prefix, file_name) if s3_prefix else file_name

                # Migrate the file
                file_result = self.migrate_file(space_id, file_cid, bucket, s3_file_path)
                result["file_results"].append(file_result)

                if file_result.get("success", False):
                    result["successful_migrations"] += 1
                else:
                    result["failed_migrations"] += 1

            # Overall success if at least one file was migrated successfully
            result["success"] = result["successful_migrations"] > 0

        except Exception as e:
            result["success"] = False
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.exception(f"Failed to migrate directory from Storacha to S3: {e}")

        return result

    def migrate_by_list(
        self, space_id: str, file_list: List[Dict[str, str]], bucket: str, s3_prefix: str = ""
    ) -> Dict[str, Any]:
        """Migrate a list of files from Storacha to S3.

        Args:
            space_id: Storacha space ID
            file_list: List of dictionaries with file info (cid, name)
            bucket: S3 bucket to store the files
            s3_prefix: Prefix path within the S3 bucket

        Returns:
            Dictionary with operation status and details
        """
        result = {
            "success": False,
            "operation": "migrate_by_list",
            "timestamp": time.time(),
            "source": {"type": "storacha", "space": space_id},
            "destination": {"type": "s3", "bucket": bucket, "prefix": s3_prefix},
            "file_results": [],
            "migrated_files": [],
            "total_files": len(file_list),
            "successful_migrations": 0,
            "failed_migrations": 0,
        }

        try:
            if not file_list:
                result["success"] = True
                result["warning"] = "Empty file list provided"
                return result

            # Migrate each file in the list
            for file_info in file_list:
                file_cid = file_info.get("cid")
                file_name = file_info.get("name")

                if not file_cid or not file_name:
                    result["failed_migrations"] += 1
                    result["file_results"].append(
                        {
                            "success": False,
                            "error": "Invalid file info (missing cid or name)",
                            "file_info": file_info,
                        }
                    )
                    continue

                # Construct S3 path for this file
                s3_file_path = os.path.join(s3_prefix, file_name) if s3_prefix else file_name

                # Migrate the file
                file_result = self.migrate_file(space_id, file_cid, bucket, s3_file_path)
                result["file_results"].append(file_result)

                if file_result.get("success", False):
                    result["successful_migrations"] += 1
                    result["migrated_files"].append(
                        {"cid": file_cid, "name": file_name, "s3_path": s3_file_path}
                    )
                else:
                    result["failed_migrations"] += 1

            # Overall success if at least one file was migrated successfully
            result["success"] = result["successful_migrations"] > 0 or len(file_list) == 0

        except Exception as e:
            result["success"] = False
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.exception(f"Failed to migrate file list from Storacha to S3: {e}")

        return result

    def cleanup(self) -> Dict[str, Any]:
        """Clean up temporary resources.

        Returns:
            Dictionary with cleanup status
        """
        result = {"success": False, "operation": "cleanup", "timestamp": time.time()}

        try:
            if self.temp_dir and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                result["success"] = True
                logger.debug(f"Cleaned up temporary directory: {self.temp_dir}")
            else:
                result["success"] = True
                result["warning"] = "No temporary directory to clean up"

        except Exception as e:
            result["success"] = False
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.exception(f"Failed to clean up temporary resources: {e}")

        return result
