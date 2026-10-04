import logging
import time

# Configure logger
logger = logging.getLogger(__name__)

async def list_files(self, path: str = "/", long: bool = False):
    """
    List files in the MFS (Mutable File System) directory.

    Args:
        path: Path in MFS to list (default: "/")
        long: Whether to show detailed file information

    Returns:
        Dictionary with list of files and directories
    """
    logger.debug(f"Listing files in MFS path: {path}")

    # Start timing for operation metrics
    start_time = time.time()
    operation_id = f"list_files_{int(start_time * 1000)}"

    try:
        # Call IPFS model to list files
        result = self.ipfs_model.files_ls(path=path, long=long)

        # Add operation tracking fields for consistency
        if "operation_id" not in result:
            result["operation_id"] = operation_id

        if "duration_ms" not in result:
            result["duration_ms"] = (time.time() - start_time) * 1000

        logger.debug(f"Listed files in path {path}")
        return result

    except Exception as e:
        logger.error(f"Error listing files in path {path}: {e}")

        # Return error in standardized format
        return {
            "success": False,
            "operation_id": operation_id,
            "duration_ms": (time.time() - start_time) * 1000,
            "error": str(e),
            "error_type": type(e).__name__,
            "path": path,
            "long": long,
            "entries": []
        }
