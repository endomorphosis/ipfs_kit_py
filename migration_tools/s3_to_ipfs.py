from ipfs_kit_py import ipfs_kit
from ipfs_kit_py import s3_kit
import os
import tempfile
import logging
import time

logger = logging.getLogger(__name__)

class s3_to_ipfs:
    def __init__(self, resources=None, metadata=None):
        self.metadata = metadata or {}
        self.resources = resources or {}
        self.ipfs = ipfs_kit(resources, metadata)
        self.s3_kit = s3_kit(resources, metadata)

        # Set default values for migration
        self.temp_dir = tempfile.mkdtemp(prefix="s3_to_ipfs_")
        logger.info(f"Created temporary directory: {self.temp_dir}")

    def migrate_file(self, s3_bucket, s3_path, recursive=False, pin=True, **kwargs):
        """
        Migrates a single file from S3 to IPFS.

        Args:
            s3_bucket: The S3 bucket where the file is stored
            s3_path: The path of the file in the S3 bucket
            recursive: Whether to add the file recursively to IPFS
            pin: Whether to pin the file in IPFS
            **kwargs: Additional parameters for the operation

        Returns:
            Dictionary with operation result information
        """
        result = {
            "success": False,
            "operation": "migrate_file",
            "timestamp": time.time(),
            "source": {
                "type": "s3",
                "bucket": s3_bucket,
                "path": s3_path
            },
            "destination": {
                "type": "ipfs"
            }
        }

        try:
            # Step 1: Download the file from S3
            file_name = os.path.basename(s3_path)
            temp_file = os.path.join(self.temp_dir, file_name)
            download_result = self.s3_kit.s3_dl_file(s3_path, temp_file, s3_bucket, **kwargs)

            if not isinstance(download_result, dict) or not download_result.get("key"):
                result["error"] = f"Failed to download from S3: {download_result}"
                result["download_result"] = download_result
                return result

            # Step 2: Add the file to IPFS
            add_result = self.ipfs.ipfs_add(temp_file, recursive=recursive)

            if not add_result.get("success", False):
                result["error"] = f"Failed to add to IPFS: {add_result.get('error', 'Unknown error')}"
                result["add_result"] = add_result
                return result

            ipfs_cid = add_result.get("cid")
            if not ipfs_cid:
                result["error"] = "No CID returned from IPFS add operation"
                result["add_result"] = add_result
                return result

            # Step 3: Pin the file in IPFS if requested
            if pin:
                pin_result = self.ipfs.ipfs_pin_add(ipfs_cid)

                if not pin_result.get("success", False):
                    result["warning"] = f"File added to IPFS but pinning failed: {pin_result.get('error', 'Unknown error')}"
                    result["pin_result"] = pin_result
                else:
                    result["pin_result"] = pin_result

            # Success!
            result["success"] = True
            result["download_result"] = download_result
            result["add_result"] = add_result
            result["ipfs_cid"] = ipfs_cid

            return result

        except Exception as e:
            result["error"] = f"Exception during migration: {str(e)}"
            result["error_type"] = type(e).__name__
            logger.exception(f"Error in migrate_file: {str(e)}")
            return result

    def migrate_directory(self, s3_bucket, s3_dir_path, recursive=True, pin=True, **kwargs):
        """
        Migrates a directory from S3 to IPFS.

        Args:
            s3_bucket: The S3 bucket where the directory is stored
            s3_dir_path: The path of the directory in the S3 bucket
            recursive: Whether to add the directory recursively to IPFS
            pin: Whether to pin the directory in IPFS
            **kwargs: Additional parameters for the operation

        Returns:
            Dictionary with operation result information
        """
        result = {
            "success": False,
            "operation": "migrate_directory",
            "timestamp": time.time(),
            "source": {
                "type": "s3",
                "bucket": s3_bucket,
                "path": s3_dir_path
            },
            "destination": {
                "type": "ipfs"
            }
        }

        try:
            # Create a temporary directory for the downloaded content
            temp_local_dir = os.path.join(self.temp_dir, os.path.basename(s3_dir_path) or "s3_dir")
            os.makedirs(temp_local_dir, exist_ok=True)

            # Step 1: List the files in the S3 directory
            list_result = self.s3_kit.s3_ls_dir(s3_dir_path, s3_bucket, **kwargs)

            if not list_result:
                result["error"] = "Failed to list files in S3 directory"
                result["list_result"] = list_result
                return result

            # Step 2: Download each file
            migrated_files = []
            failed_files = []

            for file_obj in list_result:
                file_key = file_obj.get("key")

                if not file_key:
                    failed_files.append({"error": "Missing key", "file_info": file_obj})
                    continue

                file_name = os.path.basename(file_key)
                if not file_name:  # Skip directories
                    continue

                # Download the file to the temporary directory
                temp_file_path = os.path.join(temp_local_dir, file_name)
                download_result = self.s3_kit.s3_dl_file(file_key, temp_file_path, s3_bucket, **kwargs)

                if not isinstance(download_result, dict) or not download_result.get("key"):
                    failed_files.append({
                        "key": file_key,
                        "error": f"Download failed: {download_result}"
                    })
                    continue

                migrated_files.append({
                    "key": file_key,
                    "local_path": temp_file_path
                })

            # Step 3: Add the entire directory to IPFS
            if migrated_files:
                add_result = self.ipfs.ipfs_add(temp_local_dir, recursive=recursive)

                if not add_result.get("success", False):
                    result["error"] = f"Failed to add directory to IPFS: {add_result.get('error', 'Unknown error')}"
                    result["add_result"] = add_result
                    result["migrated_files"] = migrated_files
                    result["failed_files"] = failed_files
                    return result

                ipfs_cid = add_result.get("cid")
                if not ipfs_cid:
                    result["error"] = "No CID returned from IPFS add operation"
                    result["add_result"] = add_result
                    result["migrated_files"] = migrated_files
                    result["failed_files"] = failed_files
                    return result

                # Step 4: Pin the directory in IPFS if requested
                if pin:
                    pin_result = self.ipfs.ipfs_pin_add(ipfs_cid)

                    if not pin_result.get("success", False):
                        result["warning"] = f"Directory added to IPFS but pinning failed: {pin_result.get('error', 'Unknown error')}"
                        result["pin_result"] = pin_result
                    else:
                        result["pin_result"] = pin_result

                # Success!
                result["success"] = True
                result["add_result"] = add_result
                result["ipfs_cid"] = ipfs_cid
            else:
                result["warning"] = "No files were successfully downloaded from S3"
                result["success"] = False

            result["migrated_files"] = migrated_files
            result["failed_files"] = failed_files
            result["total_files"] = len(list_result)
            result["successful_migrations"] = len(migrated_files)
            result["failed_migrations"] = len(failed_files)

            return result

        except Exception as e:
            result["error"] = f"Exception during directory migration: {str(e)}"
            result["error_type"] = type(e).__name__
            logger.exception(f"Error in migrate_directory: {str(e)}")
            return result

    def migrate_by_list(self, s3_bucket, file_list, recursive=False, pin=True, **kwargs):
        """
        Migrates a list of files from S3 to IPFS.

        Args:
            s3_bucket: The S3 bucket where the files are stored
            file_list: A list of file paths in the S3 bucket
            recursive: Whether to add the files recursively to IPFS
            pin: Whether to pin the files in IPFS
            **kwargs: Additional parameters for the operation

        Returns:
            Dictionary with operation result information
        """
        result = {
            "success": False,
            "operation": "migrate_by_list",
            "timestamp": time.time(),
            "source": {
                "type": "s3",
                "bucket": s3_bucket
            },
            "destination": {
                "type": "ipfs"
            }
        }

        try:
            if not file_list:
                result["warning"] = "Empty file list provided"
                result["success"] = True
                result["migrated_files"] = []
                return result

            # Migrate each file in the list
            migrated_files = []
            failed_files = []

            for file_path in file_list:
                file_result = self.migrate_file(
                    s3_bucket, file_path, recursive=recursive, pin=pin, **kwargs
                )

                if file_result.get("success", False):
                    migrated_files.append({
                        "s3_path": file_path,
                        "ipfs_cid": file_result.get("ipfs_cid")
                    })
                else:
                    failed_files.append({
                        "s3_path": file_path,
                        "error": file_result.get("error", "Unknown error")
                    })

            # Success based on having at least some successful migrations
            result["success"] = len(migrated_files) > 0
            result["migrated_files"] = migrated_files
            result["failed_files"] = failed_files
            result["total_files"] = len(file_list)
            result["successful_migrations"] = len(migrated_files)
            result["failed_migrations"] = len(failed_files)

            return result

        except Exception as e:
            result["error"] = f"Exception during list migration: {str(e)}"
            result["error_type"] = type(e).__name__
            logger.exception(f"Error in migrate_by_list: {str(e)}")
            return result

    def cleanup(self):
        """Clean up temporary resources."""
        import shutil
        try:
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                logger.info(f"Cleaned up temporary directory: {self.temp_dir}")
        except Exception as e:
            logger.error(f"Error cleaning up temporary directory: {str(e)}")
