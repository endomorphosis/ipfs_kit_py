from ipfs_kit_py import ipfs_kit
from ipfs_kit_py import s3_kit
import os
import tempfile
import logging
import time

logger = logging.getLogger(__name__)

class ipfs_to_s3:
    def __init__(self, resources=None, metadata=None):
        self.metadata = metadata or {}
        self.resources = resources or {}
        self.ipfs = ipfs_kit(resources, metadata)
        self.s3_kit = s3_kit(resources, metadata)
        
        # Set default values for migration
        self.temp_dir = tempfile.mkdtemp(prefix="ipfs_to_s3_")
        logger.info(f"Created temporary directory: {self.temp_dir}")
        
    def migrate_file(self, ipfs_cid, s3_bucket, s3_path, file_name=None, **kwargs):
        """
        Migrates a single file from IPFS to S3.
        
        Args:
            ipfs_cid: The CID of the file in IPFS
            s3_bucket: The destination S3 bucket
            s3_path: The destination path in the S3 bucket
            file_name: Optional file name to use when saving to S3
            **kwargs: Additional parameters for the operation
            
        Returns:
            Dictionary with operation result information
        """
        result = {
            "success": False,
            "operation": "migrate_file",
            "timestamp": time.time(),
            "source": {
                "type": "ipfs",
                "cid": ipfs_cid
            },
            "destination": {
                "type": "s3",
                "bucket": s3_bucket,
                "path": s3_path
            }
        }
        
        try:
            # Step 1: Get the file from IPFS
            cat_result = self.ipfs.ipfs_cat(ipfs_cid)
            
            if not cat_result.get("success", False) or "data" not in cat_result:
                result["error"] = f"Failed to get data from IPFS: {cat_result.get('error', 'Unknown error')}"
                result["cat_result"] = cat_result
                return result
                
            # Step 2: Write to temporary file
            if not file_name:
                file_name = ipfs_cid
                
            temp_file = os.path.join(self.temp_dir, file_name)
            with open(temp_file, 'wb') as f:
                f.write(cat_result["data"])
                
            # Step 3: Upload the file to S3
            s3_dest_path = s3_path
            if os.path.isdir(s3_path):
                s3_dest_path = os.path.join(s3_path, file_name)
                
            upload_result = self.s3_kit.s3_ul_file(temp_file, s3_dest_path, s3_bucket, **kwargs)
            
            if not isinstance(upload_result, dict) or not upload_result.get("key"):
                result["error"] = f"Failed to upload to S3: {upload_result}"
                result["upload_result"] = upload_result
                return result
            
            # Step 4: Verify the upload
            verification_result = self.s3_kit.s3_ls_file(s3_dest_path, s3_bucket, **kwargs)
            
            if not verification_result:
                result["error"] = "Failed to verify S3 upload"
                result["verification_result"] = verification_result
                return result
            
            # Success!
            result["success"] = True
            result["cat_result"] = cat_result
            result["upload_result"] = upload_result
            result["verification_result"] = verification_result
            
            return result
            
        except Exception as e:
            result["error"] = f"Exception during migration: {str(e)}"
            result["error_type"] = type(e).__name__
            logger.exception(f"Error in migrate_file: {str(e)}")
            return result
            
    def migrate_directory(self, ipfs_dir_cid, s3_bucket, s3_dir_path, **kwargs):
        """
        Migrates a directory from IPFS to S3.
        
        Args:
            ipfs_dir_cid: The CID of the directory in IPFS
            s3_bucket: The destination S3 bucket
            s3_dir_path: The destination path in the S3 bucket
            **kwargs: Additional parameters for the operation
            
        Returns:
            Dictionary with operation result information
        """
        result = {
            "success": False,
            "operation": "migrate_directory",
            "timestamp": time.time(),
            "source": {
                "type": "ipfs",
                "cid": ipfs_dir_cid
            },
            "destination": {
                "type": "s3",
                "bucket": s3_bucket,
                "path": s3_dir_path
            }
        }
        
        try:
            # Create a temporary directory for the downloaded content
            temp_local_dir = os.path.join(self.temp_dir, ipfs_dir_cid)
            os.makedirs(temp_local_dir, exist_ok=True)
            
            # Step 1: List the files in the IPFS directory
            list_result = self.ipfs.ipfs_ls_path(ipfs_dir_cid, **kwargs)
            
            if not list_result.get("success", False):
                result["error"] = f"Failed to list files in IPFS: {list_result.get('error', 'Unknown error')}"
                result["list_result"] = list_result
                return result
                
            files = list_result.get("links", [])
            if not files:
                result["warning"] = "No files found in the specified IPFS directory"
                result["success"] = True
                result["list_result"] = list_result
                result["migrated_files"] = []
                return result
                
            # Step 2: Migrate each file
            migrated_files = []
            failed_files = []
            
            for file_info in files:
                file_hash = file_info.get("Hash")
                file_name = file_info.get("Name")
                file_type = file_info.get("Type")
                
                if not file_hash or not file_name:
                    failed_files.append({"error": "Missing hash or name", "file_info": file_info})
                    continue
                    
                # Skip directories for now (could recursively handle them if needed)
                if file_type == 1:  # Directory
                    continue
                    
                # Determine the destination path in S3
                dest_path = os.path.join(s3_dir_path, file_name)
                
                # Migrate the file
                file_result = self.migrate_file(
                    file_hash, s3_bucket, dest_path, file_name=file_name, **kwargs
                )
                
                if file_result.get("success", False):
                    migrated_files.append({
                        "name": file_name,
                        "ipfs_cid": file_hash,
                        "s3_path": dest_path
                    })
                else:
                    failed_files.append({
                        "name": file_name,
                        "ipfs_cid": file_hash,
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
    
    def migrate_by_list(self, cid_list, s3_bucket, s3_base_path, **kwargs):
        """
        Migrates a list of files from IPFS to S3.
        
        Args:
            cid_list: A list of dictionaries containing file information with 'cid' and 'name' keys
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
                "type": "ipfs"
            },
            "destination": {
                "type": "s3",
                "bucket": s3_bucket,
                "base_path": s3_base_path
            }
        }
        
        try:
            if not cid_list:
                result["warning"] = "Empty CID list provided"
                result["success"] = True
                result["migrated_files"] = []
                return result
                
            # Migrate each file in the list
            migrated_files = []
            failed_files = []
            
            for file_info in cid_list:
                if isinstance(file_info, str):
                    # If it's just a string, assume it's a CID
                    file_cid = file_info
                    file_name = file_info
                else:
                    # Otherwise expect a dictionary with 'cid' and 'name' keys
                    file_cid = file_info.get("cid")
                    file_name = file_info.get("name", file_cid)
                
                if not file_cid:
                    failed_files.append({"error": "Missing CID", "file_info": file_info})
                    continue
                    
                dest_path = os.path.join(s3_base_path, file_name)
                
                file_result = self.migrate_file(
                    file_cid, s3_bucket, dest_path, file_name=file_name, **kwargs
                )
                
                if file_result.get("success", False):
                    migrated_files.append({
                        "name": file_name,
                        "ipfs_cid": file_cid,
                        "s3_path": dest_path
                    })
                else:
                    failed_files.append({
                        "name": file_name,
                        "ipfs_cid": file_cid,
                        "error": file_result.get("error", "Unknown error")
                    })
            
            # Success based on having at least some successful migrations
            result["success"] = len(migrated_files) > 0
            result["migrated_files"] = migrated_files
            result["failed_files"] = failed_files
            result["total_files"] = len(cid_list)
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