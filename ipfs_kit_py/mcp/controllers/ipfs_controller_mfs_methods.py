import logging
import time

# Configure logger
logger = logging.getLogger(__name__)

async def stat_file(self, path: str):
    """
    Get information about a file or directory in MFS.

    Args:
        path: Path in MFS to stat

    Returns:
        Dictionary with file or directory information
    """
    logger.debug(f"Getting stats for MFS path: {path}")

    # Start timing for operation metrics
    start_time = time.time()
    operation_id = f"stat_file_{int(start_time * 1000)}"

    try:
        # Call IPFS model to stat file
        result = self.ipfs_model.files_stat(path=path)

        # Add operation tracking fields for consistency
        if "operation_id" not in result:
            result["operation_id"] = operation_id

        if "duration_ms" not in result:
            result["duration_ms"] = (time.time() - start_time) * 1000

        logger.debug(f"Got stats for path {path}")
        return result

    except Exception as e:
        logger.error(f"Error getting stats for path {path}: {e}")

        # Return error in standardized format
        return {
            "success": False,
            "operation_id": operation_id,
            "duration_ms": (time.time() - start_time) * 1000,
            "error": str(e),
            "error_type": type(e).__name__,
            "path": path
        }

async def make_directory(self, path: str, parents: bool = False):
    """
    Create a directory in the MFS.

    Args:
        path: Path in MFS to create
        parents: Whether to create parent directories if they don't exist

    Returns:
        Dictionary with operation results
    """
    logger.debug(f"Creating directory in MFS: {path}, parents: {parents}")

    # Start timing for operation metrics
    start_time = time.time()
    operation_id = f"mkdir_{int(start_time * 1000)}"

    try:
        # Call IPFS model to create directory
        result = self.ipfs_model.files_mkdir(path=path, parents=parents)

        # Add operation tracking fields for consistency
        if "operation_id" not in result:
            result["operation_id"] = operation_id

        if "duration_ms" not in result:
            result["duration_ms"] = (time.time() - start_time) * 1000

        logger.debug(f"Created directory {path}")
        return result

    except Exception as e:
        logger.error(f"Error creating directory {path}: {e}")

        # Return error in standardized format
        return {
            "success": False,
            "operation_id": operation_id,
            "duration_ms": (time.time() - start_time) * 1000,
            "error": str(e),
            "error_type": type(e).__name__,
            "path": path,
            "parents": parents
        }

async def read_file(self, path: str, offset: int = 0, count: int = None):
    """
    Read content from a file in the MFS.

    Args:
        path: Path in MFS to read
        offset: Offset to start reading from
        count: Number of bytes to read (None means read all)

    Returns:
        Dictionary with file content
    """
    logger.debug(f"Reading file from MFS: {path}, offset: {offset}, count: {count}")

    # Start timing for operation metrics
    start_time = time.time()
    operation_id = f"read_file_{int(start_time * 1000)}"

    try:
        # Call IPFS model to read file
        result = self.ipfs_model.files_read(path=path, offset=offset, count=count)

        # Add operation tracking fields for consistency
        if "operation_id" not in result:
            result["operation_id"] = operation_id

        if "duration_ms" not in result:
            result["duration_ms"] = (time.time() - start_time) * 1000

        logger.debug(f"Read file {path}")
        return result

    except Exception as e:
        logger.error(f"Error reading file {path}: {e}")

        # Return error in standardized format
        return {
            "success": False,
            "operation_id": operation_id,
            "duration_ms": (time.time() - start_time) * 1000,
            "error": str(e),
            "error_type": type(e).__name__,
            "path": path,
            "offset": offset,
            "count": count
        }

async def write_file(self, path: str, content: str, create: bool = True, truncate: bool = True, 
                    offset: int = 0, flush: bool = True):
    """
    Write content to a file in the MFS.

    Args:
        path: Path in MFS to write to
        content: Content to write
        create: Whether to create the file if it doesn't exist
        truncate: Whether to truncate the file before writing
        offset: Offset to start writing at
        flush: Whether to flush changes to disk immediately

    Returns:
        Dictionary with operation results
    """
    logger.debug(f"Writing file to MFS: {path}, create: {create}, truncate: {truncate}, offset: {offset}")

    # Start timing for operation metrics
    start_time = time.time()
    operation_id = f"write_file_{int(start_time * 1000)}"

    try:
        # Call IPFS model to write file
        result = self.ipfs_model.files_write(
            path=path, 
            content=content, 
            create=create, 
            truncate=truncate, 
            offset=offset, 
            flush=flush
        )

        # Add operation tracking fields for consistency
        if "operation_id" not in result:
            result["operation_id"] = operation_id

        if "duration_ms" not in result:
            result["duration_ms"] = (time.time() - start_time) * 1000

        logger.debug(f"Wrote file {path}")
        return result

    except Exception as e:
        logger.error(f"Error writing file {path}: {e}")

        # Return error in standardized format
        return {
            "success": False,
            "operation_id": operation_id,
            "duration_ms": (time.time() - start_time) * 1000,
            "error": str(e),
            "error_type": type(e).__name__,
            "path": path,
            "create": create,
            "truncate": truncate,
            "offset": offset,
            "flush": flush
        }

async def remove_file(self, path: str, recursive: bool = False, force: bool = False):
    """
    Remove a file or directory from the MFS.

    Args:
        path: Path in MFS to remove
        recursive: Whether to remove directories recursively
        force: Whether to force removal

    Returns:
        Dictionary with operation results
    """
    logger.debug(f"Removing from MFS: {path}, recursive: {recursive}, force: {force}")

    # Start timing for operation metrics
    start_time = time.time()
    operation_id = f"remove_file_{int(start_time * 1000)}"

    try:
        # Call IPFS model to remove file
        result = self.ipfs_model.files_rm(path=path, recursive=recursive, force=force)

        # Add operation tracking fields for consistency
        if "operation_id" not in result:
            result["operation_id"] = operation_id

        if "duration_ms" not in result:
            result["duration_ms"] = (time.time() - start_time) * 1000

        logger.debug(f"Removed {path}")
        return result

    except Exception as e:
        logger.error(f"Error removing {path}: {e}")

        # Return error in standardized format
        return {
            "success": False,
            "operation_id": operation_id,
            "duration_ms": (time.time() - start_time) * 1000,
            "error": str(e),
            "error_type": type(e).__name__,
            "path": path,
            "recursive": recursive,
            "force": force
        }

async def publish_name(self, path: str, key: str = "self", resolve: bool = True, lifetime: str = "24h"):
    """
    Publish an IPFS path to IPNS.

    Args:
        path: Path to publish
        key: Name of the key to use
        resolve: Whether to resolve the path before publishing
        lifetime: Lifetime of the record

    Returns:
        Dictionary with operation results
    """
    logger.debug(f"Publishing to IPNS: {path}, key: {key}, resolve: {resolve}, lifetime: {lifetime}")

    # Start timing for operation metrics
    start_time = time.time()
    operation_id = f"publish_name_{int(start_time * 1000)}"

    try:
        # Call IPFS model to publish name
        result = self.ipfs_model.name_publish(path=path, key=key, resolve=resolve, lifetime=lifetime)

        # Add operation tracking fields for consistency
        if "operation_id" not in result:
            result["operation_id"] = operation_id

        if "duration_ms" not in result:
            result["duration_ms"] = (time.time() - start_time) * 1000

        logger.debug(f"Published {path} to IPNS with key {key}")
        return result

    except Exception as e:
        logger.error(f"Error publishing {path} to IPNS: {e}")

        # Return error in standardized format
        return {
            "success": False,
            "operation_id": operation_id,
            "duration_ms": (time.time() - start_time) * 1000,
            "error": str(e),
            "error_type": type(e).__name__,
            "path": path,
            "key": key,
            "resolve": resolve,
            "lifetime": lifetime
        }

async def resolve_name(self, name: str, recursive: bool = True, nocache: bool = False):
    """
    Resolve an IPNS name to an IPFS path.

    Args:
        name: IPNS name to resolve
        recursive: Whether to resolve recursively
        nocache: Whether to avoid using cached entries

    Returns:
        Dictionary with resolved path
    """
    logger.debug(f"Resolving IPNS name: {name}, recursive: {recursive}, nocache: {nocache}")

    # Start timing for operation metrics
    start_time = time.time()
    operation_id = f"resolve_name_{int(start_time * 1000)}"

    try:
        # Call IPFS model to resolve name
        result = self.ipfs_model.name_resolve(name=name, recursive=recursive, nocache=nocache)

        # Add operation tracking fields for consistency
        if "operation_id" not in result:
            result["operation_id"] = operation_id

        if "duration_ms" not in result:
            result["duration_ms"] = (time.time() - start_time) * 1000

        logger.debug(f"Resolved IPNS name {name}")
        return result

    except Exception as e:
        logger.error(f"Error resolving IPNS name {name}: {e}")

        # Return error in standardized format
        return {
            "success": False,
            "operation_id": operation_id,
            "duration_ms": (time.time() - start_time) * 1000,
            "error": str(e),
            "error_type": type(e).__name__,
            "name": name,
            "recursive": recursive,
            "nocache": nocache
        }

async def get_dag_node(self, cid: str, path: str = None):
    """
    Get a DAG node from IPFS.

    Args:
        cid: CID of the DAG node
        path: Optional path within the DAG node

    Returns:
        Dictionary with DAG node data
    """
    logger.debug(f"Getting DAG node: {cid}, path: {path}")

    # Start timing for operation metrics
    start_time = time.time()
    operation_id = f"get_dag_node_{int(start_time * 1000)}"

    try:
        # Call IPFS model to get DAG node
        result = self.ipfs_model.dag_get(cid=cid, path=path)

        # Add operation tracking fields for consistency
        if "operation_id" not in result:
            result["operation_id"] = operation_id

        if "duration_ms" not in result:
            result["duration_ms"] = (time.time() - start_time) * 1000

        logger.debug(f"Got DAG node {cid}")
        return result

    except Exception as e:
        logger.error(f"Error getting DAG node {cid}: {e}")

        # Return error in standardized format
        return {
            "success": False,
            "operation_id": operation_id,
            "duration_ms": (time.time() - start_time) * 1000,
            "error": str(e),
            "error_type": type(e).__name__,
            "cid": cid,
            "path": path
        }

async def put_dag_node(self, object: dict, format: str = "json", pin: bool = True):
    """
    Put a DAG node to IPFS.

    Args:
        object: Object to store as a DAG node
        format: Format to use (json or cbor)
        pin: Whether to pin the node

    Returns:
        Dictionary with operation results, including the CID
    """
    logger.debug(f"Putting DAG node: format: {format}, pin: {pin}")

    # Start timing for operation metrics
    start_time = time.time()
    operation_id = f"put_dag_node_{int(start_time * 1000)}"

    try:
        # Call IPFS model to put DAG node
        result = self.ipfs_model.dag_put(obj=object, format=format, pin=pin)

        # Add operation tracking fields for consistency
        if "operation_id" not in result:
            result["operation_id"] = operation_id

        if "duration_ms" not in result:
            result["duration_ms"] = (time.time() - start_time) * 1000

        logger.debug(f"Put DAG node, CID: {result.get('cid', 'unknown')}")
        return result

    except Exception as e:
        logger.error(f"Error putting DAG node: {e}")

        # Return error in standardized format
        return {
            "success": False,
            "operation_id": operation_id,
            "duration_ms": (time.time() - start_time) * 1000,
            "error": str(e),
            "error_type": type(e).__name__,
            "format": format,
            "pin": pin
        }

async def get_block_json(self, cid: str):
    """
    Get a raw block using query or JSON input.

    Args:
        cid: CID of the block

    Returns:
        Dictionary with block data
    """
    logger.debug(f"Getting block: {cid}")

    # Start timing for operation metrics
    start_time = time.time()
    operation_id = f"get_block_json_{int(start_time * 1000)}"

    try:
        # Call IPFS model to get block
        result = self.ipfs_model.block_get(cid=cid)

        # Add operation tracking fields for consistency
        if "operation_id" not in result:
            result["operation_id"] = operation_id

        if "duration_ms" not in result:
            result["duration_ms"] = (time.time() - start_time) * 1000

        logger.debug(f"Got block {cid}")
        return result

    except Exception as e:
        logger.error(f"Error getting block {cid}: {e}")

        # Return error in standardized format
        return {
            "success": False,
            "operation_id": operation_id,
            "duration_ms": (time.time() - start_time) * 1000,
            "error": str(e),
            "error_type": type(e).__name__,
            "cid": cid
        }

async def stat_block(self, cid: str):
    """
    Get information about a block.

    Args:
        cid: CID of the block

    Returns:
        Dictionary with block information
    """
    logger.debug(f"Getting block stats: {cid}")

    # Start timing for operation metrics
    start_time = time.time()
    operation_id = f"stat_block_{int(start_time * 1000)}"

    try:
        # Call IPFS model to get block stats
        result = self.ipfs_model.block_stat(cid=cid)

        # Add operation tracking fields for consistency
        if "operation_id" not in result:
            result["operation_id"] = operation_id

        if "duration_ms" not in result:
            result["duration_ms"] = (time.time() - start_time) * 1000

        logger.debug(f"Got block stats for {cid}")
        return result

    except Exception as e:
        logger.error(f"Error getting block stats for {cid}: {e}")

        # Return error in standardized format
        return {
            "success": False,
            "operation_id": operation_id,
            "duration_ms": (time.time() - start_time) * 1000,
            "error": str(e),
            "error_type": type(e).__name__,
            "cid": cid
        }
