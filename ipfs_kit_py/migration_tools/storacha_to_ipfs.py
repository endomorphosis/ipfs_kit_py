"""Migration tool for transferring content from Storacha to IPFS."""

import logging
import os
import shutil
import tempfile
import time
import uuid

# Configure logger
logger = logging.getLogger(__name__)


class storacha_to_ipfs:
    """Migration tool to transfer content from Storacha to IPFS."""

    def __init__(self, resources=None, metadata=None):
        """Initialize the migration tool.

        Args:
            resources: Dictionary of available resources
            metadata: Additional configuration metadata
        """
        self.resources = resources or {}
        self.metadata = metadata or {}

        # Create temporary directory for file operations
        self.temp_dir = tempfile.mkdtemp(prefix="storacha_to_ipfs_")

        # Import dependencies
        from ipfs_kit_py.ipfs import ipfs_py
        from ipfs_kit_py.storacha_kit import storacha_kit

        # Initialize components
        self.ipfs = ipfs_py(resources, metadata)
        self.storacha_kit = storacha_kit(resources, metadata)

    def migrate_file(self, space_id, cid, file_name=None, pin=True):
        """Migrate a single file from Storacha to IPFS.

        Args:
            space_id: Storacha space ID
            cid: Content ID in Storacha
            file_name: Custom filename to use (optional)
            pin: Whether to pin the content in IPFS

        Returns:
            Dictionary with operation result
        """
        result = {
            "success": False,
            "operation": "migrate_file",
            "timestamp": time.time(),
            "source": {"type": "storacha", "space": space_id, "cid": cid},
            "destination": {"type": "ipfs"},
        }

        try:
            # Download file from Storacha to temp directory
            dl_result = self.storacha_kit.store_get(space_id, cid, self.temp_dir)

            if not dl_result or not dl_result.get("success", False):
                error_msg = "Failed to download content from Storacha"
                if dl_result and "error" in dl_result:
                    error_msg = dl_result["error"]

                result["error"] = error_msg
                result["error_type"] = "storacha_download_error"
                return result

            # Get local file path
            local_path = dl_result.get("output_file")

            if not local_path or not os.path.exists(local_path):
                result["error"] = "Downloaded file not found at expected location"
                result["error_type"] = "file_not_found"
                return result

            # Use provided filename or extract from path
            if file_name is None:
                file_name = os.path.basename(local_path)

            # Add file to IPFS
            ipfs_result = self.ipfs.ipfs_add(local_path)

            if not ipfs_result.get("success", False):
                result["error"] = ipfs_result.get("error", "Failed to add content to IPFS")
                result["error_type"] = ipfs_result.get("error_type", "ipfs_error")
                return result

            # Get CID
            ipfs_cid = ipfs_result.get("cid")

            # Pin content if requested
            if pin:
                pin_result = self.ipfs.ipfs_pin_add(ipfs_cid)
                result["pin_result"] = pin_result

            # Update result with success
            result["success"] = True
            result["ipfs_cid"] = ipfs_cid
            result["ipfs_result"] = ipfs_result
            result["local_path"] = local_path

        except Exception as e:
            result["success"] = False
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.exception(f"Failed to migrate file {cid} from Storacha to IPFS: {e}")

        return result

    def migrate_directory(self, space_id, dir_cid, pin=True):
        """Migrate a directory from Storacha to IPFS.

        Args:
            space_id: Storacha space ID
            dir_cid: Content ID of the directory in Storacha
            pin: Whether to pin the content in IPFS

        Returns:
            Dictionary with operation result
        """
        result = {
            "success": False,
            "operation": "migrate_directory",
            "timestamp": time.time(),
            "source": {"type": "storacha", "space": space_id, "cid": dir_cid},
            "destination": {"type": "ipfs"},
            "migrations": [],
        }

        try:
            # List directory contents from Storacha
            ls_result = self.storacha_kit.store_ls(space_id, dir_cid)

            if not ls_result or not ls_result.get("success", False):
                error_msg = "Failed to list directory contents in Storacha"
                if ls_result and "error" in ls_result:
                    error_msg = ls_result["error"]

                result["error"] = error_msg
                result["error_type"] = "storacha_list_error"
                return result

            # Get files from directory listing
            files = ls_result.get("files", [])

            # Create a local directory for the files
            dir_name = os.path.basename(dir_cid) or "storacha_directory"
            local_dir = os.path.join(self.temp_dir, dir_name)
            os.makedirs(local_dir, exist_ok=True)

            # Track migration results
            successful = 0
            failed = 0
            total = len(files)

            # Download each file without uploading to IPFS individually
            for file_info in files:
                file_cid = file_info.get("cid")
                file_name = file_info.get("name")

                if not file_cid:
                    continue

                # Download the file to local directory
                dl_result = self.storacha_kit.store_get(space_id, file_cid, local_dir)

                if dl_result and dl_result.get("success", False):
                    successful += 1
                else:
                    failed += 1

            # Add the entire local directory to IPFS at once
            ipfs_result = self.ipfs.ipfs_add(local_dir)

            if not ipfs_result.get("success", False):
                result["error"] = ipfs_result.get("error", "Failed to add directory to IPFS")
                result["error_type"] = ipfs_result.get("error_type", "ipfs_error")
                return result

            # Get directory CID
            dir_cid = ipfs_result.get("cid")

            # Pin directory if requested
            if pin:
                pin_result = self.ipfs.ipfs_pin_add(dir_cid)
                result["pin_result"] = pin_result

            # Update result with success
            result["success"] = True
            result["ipfs_cid"] = dir_cid
            result["total_files"] = total
            result["successful_migrations"] = successful
            result["failed_migrations"] = failed

        except Exception as e:
            result["success"] = False
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.exception(f"Failed to migrate directory {dir_cid} from Storacha to IPFS: {e}")

        return result

    def migrate_by_list(self, space_id, file_list, pin=True):
        """Migrate a list of files from Storacha to IPFS.

        Args:
            space_id: Storacha space ID
            file_list: List of CIDs to migrate from Storacha
            pin: Whether to pin the content in IPFS

        Returns:
            Dictionary with operation result
        """
        result = {
            "success": False,
            "operation": "migrate_by_list",
            "timestamp": time.time(),
            "source": {"type": "storacha", "space": space_id, "list_size": len(file_list)},
            "destination": {"type": "ipfs"},
            "migrated_files": [],
        }

        if not file_list:
            result["success"] = True
            result["warning"] = "Empty file list provided, nothing to migrate"
            return result

        try:
            # Track migration results
            successful = 0
            failed = 0
            total = len(file_list)

            # Process each file in the list
            for item in file_list:
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
                file_result = self.migrate_file(space_id, cid, file_name=name, pin=pin)
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
            logger.exception(f"Failed to migrate file list from Storacha to IPFS: {e}")

        return result

    def cleanup(self):
        """Clean up temporary resources."""
        try:
            if hasattr(self, "temp_dir") and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
        except Exception as e:
            logger.error(f"Failed to clean up temporary directory: {e}")
