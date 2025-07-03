from ipfs_kit_py import storacha_kit
from ipfs_kit_py import s3_kit
import os
import tempfile
import logging
import time

logger = logging.getLogger(__name__)

class storacha_to_s3:
    def __init__(self, resources=None, metadata=None):
        self.metadata = metadata or {}
        self.resources = resources or {}
        self.storacha_kit = storacha_kit(resources, metadata)
        self.s3_kit = s3_kit(resources, metadata)
        
        # Set default values for migration
        self.temp_dir = tempfile.mkdtemp(prefix="storacha_to_s3_")
        logger.info(f"Created temporary directory: {self.temp_dir}")
        
    def migrate_file(self, storacha_space, storacha_cid, s3_bucket, s3_path, **kwargs):
        """
        Migrates a single file from Storacha to S3.
        
        Args:
            storacha_space: The Storacha space where the file is stored
            storacha_cid: The CID of the file in Storacha
            s3_bucket: The destination S3 bucket
            s3_path: The destination path in the S3 bucket
            **kwargs: Additional parameters for the operation
            
        Returns:
            Dictionary with operation result information
        """
        result = {
            "success": False,
            "operation": "migrate_file",
            "timestamp": time.time(),
            "source": {
                "type": "storacha",
                "space": storacha_space,
                "cid": storacha_cid
            },
            "destination": {
                "type": "s3",
                "bucket": s3_bucket,
                "path": s3_path
            }
        }
        
        try:
            # Step 1: Download the file from Storacha
            temp_file = os.path.join(self.temp_dir, f"{storacha_cid}")
            download_result = self.storacha_kit.store_get(storacha_space, storacha_cid, 
                                                         output_file=temp_file, **kwargs)
            
            if not download_result.get("success", False):
                result["error"] = f"Failed to download from Storacha: {download_result.get('error', 'Unknown error')}"
                result["download_result"] = download_result
                return result
                
            # Step 2: Upload the file to S3
            upload_result = self.s3_kit.s3_ul_file(temp_file, s3_path, s3_bucket, **kwargs)
            
            if not isinstance(upload_result, dict) or not upload_result.get("key"):
                result["error"] = f"Failed to upload to S3: {upload_result}"
                result["upload_result"] = upload_result
                return result
            
            # Step 3: Verify the upload
            verification_result = self.s3_kit.s3_ls_file(s3_path, s3_bucket, **kwargs)
            
            if not verification_result:
                result["error"] = "Failed to verify S3 upload"
                result["verification_result"] = verification_result
                return result
            
            # Success!
            result["success"] = True
            result["download_result"] = download_result
            result["upload_result"] = upload_result
            result["verification_result"] = verification_result
            
            return result
            
        except Exception as e:
            result["error"] = f"Exception during migration: {str(e)}"
            result["error_type"] = type(e).__name__
            logger.exception(f"Error in migrate_file: {str(e)}")
            return result
            
    def migrate_directory(self, storacha_space, storacha_dir_cid, s3_bucket, s3_path, **kwargs):
        """
        Migrates a directory from Storacha to S3.
        
        Args:
            storacha_space: The Storacha space where the directory is stored
            storacha_dir_cid: The CID of the directory in Storacha
            s3_bucket: The destination S3 bucket
            s3_path: The destination path in the S3 bucket
            **kwargs: Additional parameters for the operation
            
        Returns:
            Dictionary with operation result information
        """
        result = {
            "success": False,
            "operation": "migrate_directory",
            "timestamp": time.time(),
            "source": {
                "type": "storacha",
                "space": storacha_space,
                "cid": storacha_dir_cid
            },
            "destination": {
                "type": "s3",
                "bucket": s3_bucket,
                "path": s3_path
            }
        }
        
        try:
            # Create a temporary directory for the downloaded content
            temp_local_dir = os.path.join(self.temp_dir, storacha_dir_cid)
            os.makedirs(temp_local_dir, exist_ok=True)
            
            # Step 1: List the files in the Storacha directory
            list_result = self.storacha_kit.store_ls(storacha_space, storacha_dir_cid, **kwargs)
            
            if not list_result.get("success", False):
                result["error"] = f"Failed to list files in Storacha: {list_result.get('error', 'Unknown error')}"
                result["list_result"] = list_result
                return result
                
            files = list_result.get("files", [])
            if not files:
                result["warning"] = "No files found in the specified Storacha directory"
                result["success"] = True
                result["list_result"] = list_result
                result["migrated_files"] = []
                return result
                
            # Step 2: Migrate each file
            migrated_files = []
            failed_files = []
            
            for file_info in files:
                file_cid = file_info.get("cid")
                file_name = file_info.get("name")
                
                if not file_cid or not file_name:
                    failed_files.append({"error": "Missing CID or name", "file_info": file_info})
                    continue
                    
                dest_path = os.path.join(s3_path, file_name)
                
                file_result = self.migrate_file(
                    storacha_space, file_cid, s3_bucket, dest_path, **kwargs
                )
                
                if file_result.get("success", False):
                    migrated_files.append({
                        "name": file_name,
                        "cid": file_cid,
                        "s3_path": dest_path
                    })
                else:
                    failed_files.append({
                        "name": file_name,
                        "cid": file_cid,
                        "error": file_result.get("error", "Unknown error")
                    })
            
            # Success based on having at least some successful migrations
            result["success"] = len(migrated_files) > 0
            result["migrated_files"] = migrated_files
            result["failed_files"] = failed_files
            result["total_files"] = len(files)
            result["successful_migrations"] = len(migrated_files)
            result["failed_migrations"] = len(failed_files)
            
            return result
            
        except Exception as e:
            result["error"] = f"Exception during directory migration: {str(e)}"
            result["error_type"] = type(e).__name__
            logger.exception(f"Error in migrate_directory: {str(e)}")
            return result
    
    def migrate_by_list(self, storacha_space, file_list, s3_bucket, s3_base_path, **kwargs):
        """
        Migrates a list of files from Storacha to S3.
        
        Args:
            storacha_space: The Storacha space where the files are stored
            file_list: A list of dictionaries containing file information with 'cid' and 'name' keys
            s3_bucket: The destination S3 bucket
            s3_base_path: The base destination path in the S3 bucket
            **kwargs: Additional parameters for the operation
            
        Returns:
            Dictionary with operation result information
        """
        result = {
            "success": False,
            "operation": "migrate_by_list",
            "timestamp": time.time(),
            "source": {
                "type": "storacha",
                "space": storacha_space
            },
            "destination": {
                "type": "s3",
                "bucket": s3_bucket,
                "base_path": s3_base_path
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
            
            for file_info in file_list:
                file_cid = file_info.get("cid")
                file_name = file_info.get("name")
                
                if not file_cid or not file_name:
                    failed_files.append({"error": "Missing CID or name", "file_info": file_info})
                    continue
                    
                dest_path = os.path.join(s3_base_path, file_name)
                
                file_result = self.migrate_file(
                    storacha_space, file_cid, s3_bucket, dest_path, **kwargs
                )
                
                if file_result.get("success", False):
                    migrated_files.append({
                        "name": file_name,
                        "cid": file_cid,
                        "s3_path": dest_path
                    })
                else:
                    failed_files.append({
                        "name": file_name,
                        "cid": file_cid,
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