"""Migration tool for transferring content from IPFS to Storacha."""

import logging
import os
import shutil
import tempfile
import time
import uuid

# Configure logger
logger = logging.getLogger(__name__)


class ipfs_to_storacha:
    """Migration tool to transfer content from IPFS to Storacha."""

    def __init__(self, resources=None, metadata=None):
        """Initialize the migration tool.

        Args:
            resources: Dictionary of available resources
            metadata: Additional configuration metadata
        """
        self.resources = resources or {}
        self.metadata = metadata or {}

        # Create temporary directory for file operations
        self.temp_dir = tempfile.mkdtemp(prefix="ipfs_to_storacha_")

        # Import dependencies
        from ipfs_kit_py.ipfs import ipfs_py
        from ipfs_kit_py.s3_kit import s3_kit  # Used for some operations
        from ipfs_kit_py.storacha_kit import storacha_kit

        # Initialize components
        self.ipfs = ipfs_py(resources, metadata)
        self.storacha_kit = storacha_kit(resources, metadata)
        self.s3_kit = s3_kit(resources, metadata)

    def migrate_file(self, space_id, cid, file_name=None):
        """Migrate a single file from IPFS to Storacha.

        Args:
            space_id: Storacha space ID to upload to
            cid: Content ID in IPFS
            file_name: Custom filename to use (optional)

        Returns:
            Dictionary with operation result
        """
        result = {
            "success": False,
            "operation": "migrate_file",
            "timestamp": time.time(),
            "source": {"type": "ipfs", "cid": cid},
            "destination": {"type": "storacha", "space": space_id},
        }

        try:
            # Fetch content from IPFS
            ipfs_result = self.ipfs.ipfs_cat(cid)

            if not ipfs_result or not ipfs_result.get("success", False):
                error_msg = "Failed to retrieve content from IPFS"
                if ipfs_result and "error" in ipfs_result:
                    error_msg = ipfs_result["error"]

                result["error"] = error_msg
                result["error_type"] = "ipfs_error"
                return result

            # Get content data
            data = ipfs_result.get("data")
            if not data:
                result["error"] = "Empty data retrieved from IPFS"
                result["error_type"] = "empty_data"
                return result

            # Use provided filename or derive from CID
            if file_name is None:
                file_name = cid

            # Save to temporary file
            temp_file_path = os.path.join(self.temp_dir, file_name)
            with open(temp_file_path, "wb") as f:
                f.write(data)

            # Upload to Storacha
            storacha_result = self.storacha_kit.store_add(space_id, temp_file_path)

            if not storacha_result or not storacha_result.get("success", False):
                error_msg = "Failed to upload content to Storacha"
                if storacha_result and "error" in storacha_result:
                    error_msg = storacha_result["error"]

                result["error"] = error_msg
                result["error_type"] = "storacha_error"
                return result

            # Get Storacha CID
            storacha_cid = storacha_result.get("cid")

            # Update result with success
            result["success"] = True
            result["storacha_cid"] = storacha_cid
            result["storacha_result"] = storacha_result
            result["local_path"] = temp_file_path

        except Exception as e:
            result["success"] = False
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.exception(f"Failed to migrate file {cid} from IPFS to Storacha: {e}")

        return result

    def migrate_directory(self, space_id, dir_cid):
        """Migrate a directory from IPFS to Storacha.

        Args:
            space_id: Storacha space ID to upload to
            dir_cid: Content ID of the directory in IPFS

        Returns:
            Dictionary with operation result
        """
        result = {
            "success": False,
            "operation": "migrate_directory",
            "timestamp": time.time(),
            "source": {"type": "ipfs", "cid": dir_cid},
            "destination": {"type": "storacha", "space": space_id},
            "migrations": [],
        }

        try:
            # List directory contents
            ls_result = self.ipfs.ipfs_ls_path(dir_cid)

            if not ls_result or not ls_result.get("success", False):
                error_msg = "Failed to list directory contents in IPFS"
                if ls_result and "error" in ls_result:
                    error_msg = ls_result["error"]

                result["error"] = error_msg
                result["error_type"] = "ipfs_list_error"
                return result

            # Get directory items
            items = ls_result.get("links", [])

            # Create a local directory for the files
            dir_name = os.path.basename(dir_cid) or "ipfs_directory"
            local_dir = os.path.join(self.temp_dir, dir_name)
            os.makedirs(local_dir, exist_ok=True)

            # Track migration results
            file_results = []
            successful = 0
            failed = 0
            total = len(items)

            # Download each file and add to Storacha
            for item in items:
                item_name = item.get("Name")
                item_hash = item.get("Hash")
                item_type = item.get("Type")

                # Skip directories for now (could recursively process in future)
                if item_type == 1:  # Directory
                    continue

                # Skip if missing necessary info
                if not item_hash or not item_name:
                    continue

                # Migrate the file
                file_result = self.migrate_file(space_id, item_hash, file_name=item_name)
                file_results.append(file_result)

                if file_result.get("success", False):
                    successful += 1
                else:
                    failed += 1

            # Create a CAR file with all the files (for directories we need a CAR file)
            car_path = os.path.join(self.temp_dir, f"{dir_name}.car")

            # Upload CAR file to Storacha
            storacha_result = self.storacha_kit.store_add(space_id, local_dir)

            if not storacha_result or not storacha_result.get("success", False):
                # Even without the directory, we may have migrated individual files successfully
                result["file_results"] = file_results

                error_msg = "Failed to upload directory to Storacha"
                if storacha_result and "error" in storacha_result:
                    error_msg = storacha_result["error"]

                result["error"] = error_msg
                result["error_type"] = "storacha_error"

                # If we have some successful file migrations, report partial success
                if successful > 0:
                    result["partial_success"] = True

                return result

            # Get directory CID
            storacha_dir_cid = storacha_result.get("cid")

            # Update result with success
            result["success"] = True
            result["storacha_cid"] = storacha_dir_cid
            result["total_files"] = total
            result["successful_migrations"] = successful
            result["failed_migrations"] = failed
            result["file_results"] = file_results

        except Exception as e:
            result["success"] = False
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.exception(f"Failed to migrate directory {dir_cid} from IPFS to Storacha: {e}")

        return result

    def migrate_by_list(self, space_id, cid_list):
        """Migrate a list of files from IPFS to Storacha.

        Args:
            space_id: Storacha space ID to upload to
            cid_list: List of CIDs to migrate (strings or dicts with cid and name)

        Returns:
            Dictionary with operation result
        """
        result = {
            "success": False,
            "operation": "migrate_by_list",
            "timestamp": time.time(),
            "source": {"type": "ipfs", "list_size": len(cid_list)},
            "destination": {"type": "storacha", "space": space_id},
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
                    name = None

                # Skip if no CID
                if not cid:
                    continue

                # Migrate the file
                file_result = self.migrate_file(space_id, cid, file_name=name)
                result["migrated_files"].append(file_result)

                if file_result.get("success", False):
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
            logger.exception(f"Failed to migrate CID list to Storacha: {e}")

        return result

    def cleanup(self):
        """Clean up temporary resources."""
        try:
            if hasattr(self, "temp_dir") and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
        except Exception as e:
            logger.error(f"Failed to clean up temporary directory: {e}")
