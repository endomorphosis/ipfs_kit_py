"""
Extended MCP server controllers for IPFS Kit SDK features.

This module provides additional controllers to expose all IPFS Kit SDK features
through the MCP server API, ensuring complete functionality is available.
"""

import os
import sys
import logging
import tempfile
import time
import json
import uuid
from fastapi import APIRouter, HTTPException, File, UploadFile, Form, Query, Body, Path, Depends
from fastapi.responses import StreamingResponse, Response, JSONResponse
from typing import Dict, List, Any, Optional, Union, Literal

# Configure logging
logger = logging.getLogger(__name__)

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import IPFS Kit modules
try:
    from ipfs_kit_py.ipfs_kit import ipfs_kit
    from ipfs_kit_py.tiered_cache import TieredCacheManager
    from ipfs_kit_py.mfs_enhanced import MFSEnhanced
    from ipfs_kit_py.ipfs_fsspec import IPFSFileSystem
    from ipfs_kit_py.high_level_api import HighLevelAPI
    from ipfs_kit_py.storacha_kit import storacha_kit
    from ipfs_kit_py.s3_kit import s3_kit
    from ipfs_kit_py.huggingface_kit import huggingface_kit
    from ipfs_kit_py.lotus_kit import lotus_kit
    from ipfs_kit_py.lassie_kit import lassie_kit
    from ipfs_kit_py.migration_tools import ipfs_to_storacha, ipfs_to_s3, s3_to_ipfs, storacha_to_ipfs, s3_to_storacha, storacha_to_s3
    IPFS_KIT_AVAILABLE = True
    logger.info("Successfully imported IPFS Kit modules")
except ImportError as e:
    logger.error(f"Failed to import IPFS Kit modules: {e}")
    IPFS_KIT_AVAILABLE = False

# Create a shared IPFS Kit instance
def get_ipfs_kit_instance():
    """Get or create a shared IPFS Kit instance."""
    if not hasattr(get_ipfs_kit_instance, "instance"):
        # Initialize with real credentials if available
        kit_metadata = {
            "debug": True,
            "auto_pin": True,
        }
        
        # Try to get real credentials from environment
        if os.environ.get("HUGGINGFACE_TOKEN"):
            kit_metadata["huggingface_token"] = os.environ.get("HUGGINGFACE_TOKEN")
        
        if os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY"):
            kit_metadata["s3cfg"] = {
                "accessKey": os.environ.get("AWS_ACCESS_KEY_ID"),
                "secretKey": os.environ.get("AWS_SECRET_ACCESS_KEY"),
                "endpoint": os.environ.get("AWS_ENDPOINT_URL", "https://s3.amazonaws.com"),
                "region": os.environ.get("AWS_REGION", "us-east-1"),
                "bucket": os.environ.get("AWS_S3_BUCKET_NAME", "ipfs-storage-demo")
            }
            
        if os.environ.get("STORACHA_API_KEY"):
            kit_metadata["storacha_token"] = os.environ.get("STORACHA_API_KEY")
            kit_metadata["storacha_api_url"] = os.environ.get("STORACHA_API_URL", "https://up.storacha.network/bridge")
            
        # Create the IPFS Kit instance
        get_ipfs_kit_instance.instance = ipfs_kit(metadata=kit_metadata)
        logger.info("Created IPFS Kit instance with available credentials")
        
    return get_ipfs_kit_instance.instance


def create_extended_routers(api_prefix: str) -> List[APIRouter]:
    """
    Create FastAPI routers for all IPFS Kit SDK features.
    
    Args:
        api_prefix: API prefix for the endpoints
        
    Returns:
        List of API routers
    """
    routers = []
    
    if not IPFS_KIT_AVAILABLE:
        logger.warning("IPFS Kit modules not available, skipping extended routers")
        return routers
        
    # Create routers for different feature groups
    routers.append(create_enhanced_ipfs_router(api_prefix))
    routers.append(create_mfs_router(api_prefix))
    routers.append(create_dag_router(api_prefix))
    routers.append(create_migration_router(api_prefix))
    routers.append(create_cache_router(api_prefix))
    routers.append(create_high_level_router(api_prefix))
    routers.append(create_advanced_storage_router(api_prefix))
    
    return routers

def create_enhanced_ipfs_router(api_prefix: str) -> APIRouter:
    """Create router for enhanced IPFS operations."""
    router = APIRouter(prefix=f"{api_prefix}/ipfs/extended", tags=["Enhanced IPFS"])
    
    @router.get("/ls/{cid}")
    async def ipfs_ls(cid: str, resolve_type: bool = Query(False)):
        """List directory contents by CID."""
        try:
            kit = get_ipfs_kit_instance()
            result = kit.ipfs_ls(cid, resolve_type=resolve_type)
            return {"success": True, "entries": result}
        except Exception as e:
            logger.error(f"Error listing directory: {e}")
            return {"success": False, "error": str(e)}
    
    @router.post("/add-directory")
    async def ipfs_add_directory(
        path: str = Form(...),
        recursive: bool = Form(True),
        wrap_with_directory: bool = Form(True)
    ):
        """Add a directory to IPFS."""
        try:
            kit = get_ipfs_kit_instance()
            result = kit.ipfs_add_directory(path, recursive, wrap_with_directory)
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Error adding directory: {e}")
            return {"success": False, "error": str(e)}
    
    @router.post("/add-json")
    async def ipfs_add_json(data: Dict = Body(...)):
        """Add JSON data to IPFS."""
        try:
            kit = get_ipfs_kit_instance()
            cid = kit.ipfs_add_json(data)
            return {"success": True, "cid": cid}
        except Exception as e:
            logger.error(f"Error adding JSON: {e}")
            return {"success": False, "error": str(e)}
    
    @router.get("/get-json/{cid}")
    async def ipfs_get_json(cid: str):
        """Get JSON data from IPFS."""
        try:
            kit = get_ipfs_kit_instance()
            data = kit.ipfs_get_json(cid)
            return {"success": True, "data": data}
        except Exception as e:
            logger.error(f"Error getting JSON: {e}")
            return {"success": False, "error": str(e)}
    
    @router.post("/name/publish")
    async def ipfs_name_publish(
        cid: str = Form(...),
        key: str = Form("self"),
        lifetime: str = Form("24h"),
        ttl: str = Form(""),
        resolve: bool = Form(True)
    ):
        """Publish an IPNS name."""
        try:
            kit = get_ipfs_kit_instance()
            result = kit.ipns_publish(cid, key=key, lifetime=lifetime, ttl=ttl, resolve=resolve)
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Error publishing name: {e}")
            return {"success": False, "error": str(e)}
    
    @router.get("/name/resolve/{name}")
    async def ipfs_name_resolve(name: str, recursive: bool = Query(True), nocache: bool = Query(False)):
        """Resolve an IPNS name."""
        try:
            kit = get_ipfs_kit_instance()
            result = kit.ipns_resolve(name, recursive=recursive, nocache=nocache)
            return {"success": True, "path": result}
        except Exception as e:
            logger.error(f"Error resolving name: {e}")
            return {"success": False, "error": str(e)}
    
    @router.post("/key/gen")
    async def ipfs_key_gen(key_name: str = Form(...), key_type: str = Form("rsa"), key_size: int = Form(2048)):
        """Generate a new key."""
        try:
            kit = get_ipfs_kit_instance()
            result = kit.ipfs_key_gen(key_name, key_type, key_size)
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Error generating key: {e}")
            return {"success": False, "error": str(e)}
    
    @router.get("/key/list")
    async def ipfs_key_list():
        """List all keys."""
        try:
            kit = get_ipfs_kit_instance()
            result = kit.ipfs_key_list()
            return {"success": True, "keys": result}
        except Exception as e:
            logger.error(f"Error listing keys: {e}")
            return {"success": False, "error": str(e)}
    
    return router

def create_mfs_router(api_prefix: str) -> APIRouter:
    """Create router for MFS (Mutable File System) operations."""
    router = APIRouter(prefix=f"{api_prefix}/mfs", tags=["MFS"])
    
    @router.post("/write")
    async def mfs_write(
        path: str = Form(...),
        file: UploadFile = File(...),
        create: bool = Form(True),
        truncate: bool = Form(True),
        parents: bool = Form(True)
    ):
        """Write to a file in MFS."""
        try:
            # Create a temporary file to store the uploaded content
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                content = await file.read()
                temp_file.write(content)
                temp_file_path = temp_file.name
            
            kit = get_ipfs_kit_instance()
            with open(temp_file_path, 'rb') as f:
                result = kit.mfs_write(path, f, create=create, truncate=truncate, parents=parents)
            
            # Clean up the temporary file
            os.unlink(temp_file_path)
            
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Error writing to MFS: {e}")
            return {"success": False, "error": str(e)}
    
    @router.get("/read/{path:path}")
    async def mfs_read(path: str, offset: int = Query(0), count: int = Query(-1)):
        """Read a file from MFS."""
        try:
            kit = get_ipfs_kit_instance()
            content = kit.mfs_read(path, offset=offset, count=count)
            
            async def content_generator():
                yield content
            
            return StreamingResponse(
                content_generator(),
                media_type="application/octet-stream"
            )
        except Exception as e:
            logger.error(f"Error reading from MFS: {e}")
            return {"success": False, "error": str(e)}
    
    @router.post("/mkdir")
    async def mfs_mkdir(path: str = Form(...), parents: bool = Form(True)):
        """Create a directory in MFS."""
        try:
            kit = get_ipfs_kit_instance()
            result = kit.mfs_mkdir(path, parents=parents)
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Error creating directory in MFS: {e}")
            return {"success": False, "error": str(e)}
    
    @router.post("/rm")
    async def mfs_rm(path: str = Form(...), recursive: bool = Form(False)):
        """Remove a file or directory in MFS."""
        try:
            kit = get_ipfs_kit_instance()
            result = kit.mfs_rm(path, recursive=recursive)
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Error removing from MFS: {e}")
            return {"success": False, "error": str(e)}
    
    @router.post("/cp")
    async def mfs_cp(
        source: str = Form(...),
        dest: str = Form(...),
        parents: bool = Form(True)
    ):
        """Copy files in MFS."""
        try:
            kit = get_ipfs_kit_instance()
            result = kit.mfs_cp(source, dest, parents=parents)
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Error copying in MFS: {e}")
            return {"success": False, "error": str(e)}
    
    @router.post("/mv")
    async def mfs_mv(
        source: str = Form(...),
        dest: str = Form(...),
        parents: bool = Form(True)
    ):
        """Move files in MFS."""
        try:
            kit = get_ipfs_kit_instance()
            result = kit.mfs_mv(source, dest, parents=parents)
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Error moving in MFS: {e}")
            return {"success": False, "error": str(e)}
    
    @router.get("/ls/{path:path}")
    async def mfs_ls(path: str, long: bool = Query(False)):
        """List directory contents in MFS."""
        try:
            kit = get_ipfs_kit_instance()
            result = kit.mfs_ls(path, long=long)
            return {"success": True, "entries": result}
        except Exception as e:
            logger.error(f"Error listing MFS directory: {e}")
            return {"success": False, "error": str(e)}
    
    @router.get("/stat/{path:path}")
    async def mfs_stat(path: str):
        """Get file or directory status in MFS."""
        try:
            kit = get_ipfs_kit_instance()
            result = kit.mfs_stat(path)
            return {"success": True, "stat": result}
        except Exception as e:
            logger.error(f"Error getting MFS stat: {e}")
            return {"success": False, "error": str(e)}
    
    @router.get("/flush/{path:path}")
    async def mfs_flush(path: str):
        """Flush file changes in MFS."""
        try:
            kit = get_ipfs_kit_instance()
            result = kit.mfs_flush(path)
            return {"success": True, "cid": result}
        except Exception as e:
            logger.error(f"Error flushing MFS path: {e}")
            return {"success": False, "error": str(e)}
    
    # Enhanced MFS endpoints
    @router.post("/enhanced/copy-from-fs")
    async def mfs_enhanced_copy_from_fs(
        local_path: str = Form(...),
        mfs_path: str = Form(...),
        recursive: bool = Form(True),
        parents: bool = Form(True)
    ):
        """Copy from local filesystem to MFS with enhanced features."""
        try:
            kit = get_ipfs_kit_instance()
            result = kit.mfs_enhanced.copy_from_filesystem(local_path, mfs_path, recursive=recursive, create_parents=parents)
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Error copying from filesystem to MFS: {e}")
            return {"success": False, "error": str(e)}
    
    @router.post("/enhanced/copy-to-fs")
    async def mfs_enhanced_copy_to_fs(
        mfs_path: str = Form(...),
        local_path: str = Form(...),
        recursive: bool = Form(True),
        parents: bool = Form(True)
    ):
        """Copy from MFS to local filesystem with enhanced features."""
        try:
            kit = get_ipfs_kit_instance()
            result = kit.mfs_enhanced.copy_to_filesystem(mfs_path, local_path, recursive=recursive, create_parents=parents)
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Error copying from MFS to filesystem: {e}")
            return {"success": False, "error": str(e)}
    
    return router

def create_dag_router(api_prefix: str) -> APIRouter:
    """Create router for DAG operations."""
    router = APIRouter(prefix=f"{api_prefix}/dag", tags=["DAG"])
    
    @router.post("/put")
    async def dag_put(data: Dict = Body(...)):
        """Store data as a DAG object."""
        try:
            kit = get_ipfs_kit_instance()
            cid = kit.dag_put(data)
            return {"success": True, "cid": cid}
        except Exception as e:
            logger.error(f"Error putting DAG: {e}")
            return {"success": False, "error": str(e)}
    
    @router.get("/get/{cid}")
    async def dag_get(cid: str, path: str = Query("")):
        """Get a DAG object."""
        try:
            kit = get_ipfs_kit_instance()
            data = kit.dag_get(cid, path=path)
            return {"success": True, "data": data}
        except Exception as e:
            logger.error(f"Error getting DAG: {e}")
            return {"success": False, "error": str(e)}
    
    @router.get("/resolve/{cid}")
    async def dag_resolve(cid: str, path: str = Query("")):
        """Resolve a path in a DAG object."""
        try:
            kit = get_ipfs_kit_instance()
            result = kit.dag_resolve(f"{cid}/{path}" if path else cid)
            return {"success": True, "cid": result["Cid"]["/"]}
        except Exception as e:
            logger.error(f"Error resolving DAG path: {e}")
            return {"success": False, "error": str(e)}
    
    @router.post("/import")
    async def dag_import(file: UploadFile = File(...)):
        """Import a DAG object from a file."""
        try:
            # Create a temporary file to store the uploaded content
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                content = await file.read()
                temp_file.write(content)
                temp_file_path = temp_file.name
            
            kit = get_ipfs_kit_instance()
            result = kit.dag_import(temp_file_path)
            
            # Clean up the temporary file
            os.unlink(temp_file_path)
            
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Error importing DAG: {e}")
            return {"success": False, "error": str(e)}
    
    @router.post("/export")
    async def dag_export(cid: str = Form(...)):
        """Export a DAG object."""
        try:
            kit = get_ipfs_kit_instance()
            
            # Create a temporary file for the export
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_path = temp_file.name
            
            # Export the DAG object
            kit.dag_export(cid, temp_path)
            
            # Read the exported data
            with open(temp_path, 'rb') as f:
                data = f.read()
            
            # Clean up the temporary file
            os.unlink(temp_path)
            
            async def content_generator():
                yield data
            
            return StreamingResponse(
                content_generator(),
                media_type="application/octet-stream",
                headers={"Content-Disposition": f"attachment; filename={cid}.car"}
            )
        except Exception as e:
            logger.error(f"Error exporting DAG: {e}")
            return {"success": False, "error": str(e)}
    
    return router

def create_migration_router(api_prefix: str) -> APIRouter:
    """Create router for data migration between storage backends."""
    router = APIRouter(prefix=f"{api_prefix}/migration", tags=["Migration"])
    
    @router.post("/ipfs-to-storacha")
    async def migrate_ipfs_to_storacha(
        cid: str = Form(...),
        space_did: Optional[str] = Form(None),
        pin_locally: bool = Form(True)
    ):
        """Migrate content from IPFS to Storacha."""
        try:
            kit = get_ipfs_kit_instance()
            result = ipfs_to_storacha.migrate_content(kit, cid, space_did=space_did, pin_locally=pin_locally)
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Error migrating from IPFS to Storacha: {e}")
            return {"success": False, "error": str(e)}
    
    @router.post("/ipfs-to-s3")
    async def migrate_ipfs_to_s3(
        cid: str = Form(...),
        bucket: Optional[str] = Form(None),
        prefix: str = Form("ipfs/"),
        pin_locally: bool = Form(True)
    ):
        """Migrate content from IPFS to S3."""
        try:
            kit = get_ipfs_kit_instance()
            result = ipfs_to_s3.migrate_content(kit, cid, bucket=bucket, prefix=prefix, pin_locally=pin_locally)
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Error migrating from IPFS to S3: {e}")
            return {"success": False, "error": str(e)}
    
    @router.post("/s3-to-ipfs")
    async def migrate_s3_to_ipfs(
        s3_key: str = Form(...),
        bucket: Optional[str] = Form(None),
        pin_locally: bool = Form(True)
    ):
        """Migrate content from S3 to IPFS."""
        try:
            kit = get_ipfs_kit_instance()
            result = s3_to_ipfs.migrate_content(kit, s3_key, bucket=bucket, pin_locally=pin_locally)
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Error migrating from S3 to IPFS: {e}")
            return {"success": False, "error": str(e)}
    
    @router.post("/storacha-to-ipfs")
    async def migrate_storacha_to_ipfs(
        storage_id: str = Form(...),
        space_did: Optional[str] = Form(None),
        pin_locally: bool = Form(True)
    ):
        """Migrate content from Storacha to IPFS."""
        try:
            kit = get_ipfs_kit_instance()
            result = storacha_to_ipfs.migrate_content(kit, storage_id, space_did=space_did, pin_locally=pin_locally)
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Error migrating from Storacha to IPFS: {e}")
            return {"success": False, "error": str(e)}
    
    @router.post("/s3-to-storacha")
    async def migrate_s3_to_storacha(
        s3_key: str = Form(...),
        bucket: Optional[str] = Form(None),
        space_did: Optional[str] = Form(None)
    ):
        """Migrate content from S3 to Storacha."""
        try:
            kit = get_ipfs_kit_instance()
            result = s3_to_storacha.migrate_content(kit, s3_key, bucket=bucket, space_did=space_did)
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Error migrating from S3 to Storacha: {e}")
            return {"success": False, "error": str(e)}
    
    @router.post("/storacha-to-s3")
    async def migrate_storacha_to_s3(
        storage_id: str = Form(...),
        space_did: Optional[str] = Form(None),
        bucket: Optional[str] = Form(None),
        prefix: str = Form("ipfs/")
    ):
        """Migrate content from Storacha to S3."""
        try:
            kit = get_ipfs_kit_instance()
            result = storacha_to_s3.migrate_content(kit, storage_id, space_did=space_did, bucket=bucket, prefix=prefix)
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Error migrating from Storacha to S3: {e}")
            return {"success": False, "error": str(e)}
    
    return router

def create_cache_router(api_prefix: str) -> APIRouter:
    """Create router for cache operations."""
    router = APIRouter(prefix=f"{api_prefix}/cache", tags=["Cache"])
    
    @router.get("/status")
    async def cache_status():
        """Get cache status."""
        try:
            kit = get_ipfs_kit_instance()
            cache_manager = kit.get_cache_manager()
            stats = cache_manager.get_stats()
            return {"success": True, "stats": stats}
        except Exception as e:
            logger.error(f"Error getting cache status: {e}")
            return {"success": False, "error": str(e)}
    
    @router.post("/prefetch")
    async def cache_prefetch(cid: str = Form(...), recursive: bool = Form(False)):
        """Prefetch content into cache."""
        try:
            kit = get_ipfs_kit_instance()
            cache_manager = kit.get_cache_manager()
            result = cache_manager.prefetch(cid, recursive=recursive)
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Error prefetching content: {e}")
            return {"success": False, "error": str(e)}
    
    @router.post("/invalidate")
    async def cache_invalidate(cid: str = Form(...)):
        """Invalidate content from cache."""
        try:
            kit = get_ipfs_kit_instance()
            cache_manager = kit.get_cache_manager()
            result = cache_manager.invalidate(cid)
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Error invalidating cache: {e}")
            return {"success": False, "error": str(e)}
    
    @router.post("/promote")
    async def cache_promote(cid: str = Form(...), tier: str = Form(...)):
        """Promote content to a specific cache tier."""
        try:
            kit = get_ipfs_kit_instance()
            cache_manager = kit.get_cache_manager()
            result = cache_manager.promote_to_tier(cid, tier)
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Error promoting cache content: {e}")
            return {"success": False, "error": str(e)}
    
    @router.post("/demote")
    async def cache_demote(cid: str = Form(...), tier: str = Form(...)):
        """Demote content to a specific cache tier."""
        try:
            kit = get_ipfs_kit_instance()
            cache_manager = kit.get_cache_manager()
            result = cache_manager.demote_to_tier(cid, tier)
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Error demoting cache content: {e}")
            return {"success": False, "error": str(e)}
    
    @router.get("/locate/{cid}")
    async def cache_locate(cid: str):
        """Locate content in cache tiers."""
        try:
            kit = get_ipfs_kit_instance()
            cache_manager = kit.get_cache_manager()
            result = cache_manager.locate(cid)
            return {"success": True, "locations": result}
        except Exception as e:
            logger.error(f"Error locating content in cache: {e}")
            return {"success": False, "error": str(e)}
    
    return router

def create_high_level_router(api_prefix: str) -> APIRouter:
    """Create router for high-level operations."""
    router = APIRouter(prefix=f"{api_prefix}/high-level", tags=["High Level API"])
    
    @router.post("/store-directory")
    async def high_level_store_directory(
        path: str = Form(...),
        recursive: bool = Form(True),
        include_hidden: bool = Form(False),
        cache: bool = Form(True)
    ):
        """Store a directory with high-level API."""
        try:
            kit = get_ipfs_kit_instance()
            api = kit.high_level_api
            result = api.store_directory(path, recursive=recursive, include_hidden=include_hidden, cache=cache)
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Error storing directory: {e}")
            return {"success": False, "error": str(e)}
    
    @router.post("/store-file")
    async def high_level_store_file(
        file: UploadFile = File(...),
        cache: bool = Form(True)
    ):
        """Store a file with high-level API."""
        try:
            # Create a temporary file to store the uploaded content
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                content = await file.read()
                temp_file.write(content)
                temp_file_path = temp_file.name
            
            kit = get_ipfs_kit_instance()
            api = kit.high_level_api
            result = api.store_file(temp_file_path, cache=cache)
            
            # Clean up the temporary file
            os.unlink(temp_file_path)
            
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Error storing file: {e}")
            return {"success": False, "error": str(e)}
    
    @router.post("/retrieve-to-filesystem")
    async def high_level_retrieve_to_filesystem(
        cid: str = Form(...),
        output_dir: str = Form(...),
        create_dir: bool = Form(True)
    ):
        """Retrieve content to filesystem with high-level API."""
        try:
            kit = get_ipfs_kit_instance()
            api = kit.high_level_api
            result = api.retrieve_to_filesystem(cid, output_dir, create_dir=create_dir)
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Error retrieving to filesystem: {e}")
            return {"success": False, "error": str(e)}
    
    @router.post("/store-object")
    async def high_level_store_object(data: Dict = Body(...)):
        """Store an object with high-level API."""
        try:
            kit = get_ipfs_kit_instance()
            api = kit.high_level_api
            result = api.store_object(data)
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Error storing object: {e}")
            return {"success": False, "error": str(e)}
    
    @router.get("/retrieve-object/{cid}")
    async def high_level_retrieve_object(cid: str):
        """Retrieve an object with high-level API."""
        try:
            kit = get_ipfs_kit_instance()
            api = kit.high_level_api
            result = api.retrieve_object(cid)
            return {"success": True, "data": result}
        except Exception as e:
            logger.error(f"Error retrieving object: {e}")
            return {"success": False, "error": str(e)}
    
    return router

def create_advanced_storage_router(api_prefix: str) -> APIRouter:
    """Create router for advanced storage operations."""
    router = APIRouter(prefix=f"{api_prefix}/storage/advanced", tags=["Advanced Storage"])
    
    # Storacha advanced endpoints
    @router.get("/storacha/list")
    async def storacha_list_blobs(
        cursor: Optional[str] = Query(None),
        size: int = Query(100)
    ):
        """List blobs stored in Storacha."""
        try:
            kit = get_ipfs_kit_instance()
            if not hasattr(kit, "storacha_storage"):
                from storacha_storage import StorachaStorage
                kit.storacha_storage = StorachaStorage()
            
            result = kit.storacha_storage.list_blobs(cursor=cursor, size=size)
            return result
        except Exception as e:
            logger.error(f"Error listing Storacha blobs: {e}")
            return {"success": False, "error": str(e)}
    
    @router.get("/storacha/get/{digest}")
    async def storacha_get_blob(digest: str):
        """Get blob info from Storacha."""
        try:
            kit = get_ipfs_kit_instance()
            if not hasattr(kit, "storacha_storage"):
                from storacha_storage import StorachaStorage
                kit.storacha_storage = StorachaStorage()
            
            result = kit.storacha_storage.get_blob(digest)
            return result
        except Exception as e:
            logger.error(f"Error getting Storacha blob: {e}")
            return {"success": False, "error": str(e)}
    
    @router.post("/storacha/remove")
    async def storacha_remove_blob(digest: str = Form(...)):
        """Remove a blob from Storacha."""
        try:
            kit = get_ipfs_kit_instance()
            if not hasattr(kit, "storacha_storage"):
                from storacha_storage import StorachaStorage
                kit.storacha_storage = StorachaStorage()
            
            result = kit.storacha_storage.remove_blob(digest)
            return result
        except Exception as e:
            logger.error(f"Error removing Storacha blob: {e}")
            return {"success": False, "error": str(e)}
    
    # S3 advanced endpoints
    @router.post("/s3/create-bucket")
    async def s3_create_bucket(
        bucket_name: str = Form(...),
        region: str = Form("us-east-1")
    ):
        """Create a new S3 bucket."""
        try:
            kit = get_ipfs_kit_instance()
            result = kit.s3_kit("mk_bucket", bucket_name=bucket_name, region=region)
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Error creating S3 bucket: {e}")
            return {"success": False, "error": str(e)}
    
    @router.get("/s3/list-buckets")
    async def s3_list_buckets():
        """List all S3 buckets."""
        try:
            kit = get_ipfs_kit_instance()
            result = kit.s3_kit("ls_buckets")
            return {"success": True, "buckets": result}
        except Exception as e:
            logger.error(f"Error listing S3 buckets: {e}")
            return {"success": False, "error": str(e)}
    
    @router.get("/s3/list-objects")
    async def s3_list_objects(
        bucket: str = Query(...),
        prefix: Optional[str] = Query(None),
        max_keys: int = Query(1000)
    ):
        """List objects in an S3 bucket."""
        try:
            kit = get_ipfs_kit_instance()
            result = kit.s3_kit("ls_dir", dir=prefix or "", bucket_name=bucket, max_keys=max_keys)
            return {"success": True, "objects": result}
        except Exception as e:
            logger.error(f"Error listing S3 objects: {e}")
            return {"success": False, "error": str(e)}
    
    # HuggingFace advanced endpoints
    @router.get("/huggingface/list-repos")
    async def huggingface_list_repos():
        """List HuggingFace repositories."""
        try:
            kit = get_ipfs_kit_instance()
            result = kit.huggingface_kit.list_repos()
            return {"success": True, "repositories": result}
        except Exception as e:
            logger.error(f"Error listing HuggingFace repositories: {e}")
            return {"success": False, "error": str(e)}
    
    @router.post("/huggingface/create-repo")
    async def huggingface_create_repo(
        repo_name: str = Form(...),
        private: bool = Form(True)
    ):
        """Create a new HuggingFace repository."""
        try:
            kit = get_ipfs_kit_instance()
            result = kit.huggingface_kit.create_repo(repo_name, private=private)
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Error creating HuggingFace repository: {e}")
            return {"success": False, "error": str(e)}
    
    # Filecoin advanced endpoints
    @router.get("/filecoin/status")
    async def filecoin_status():
        """Get Filecoin status."""
        try:
            kit = get_ipfs_kit_instance()
            if hasattr(kit, "lotus_kit"):
                result = kit.lotus_kit.get_status()
            else:
                # Import directly
                from filecoin_storage import FilecoinStorage
                storage = FilecoinStorage()
                result = storage.status()
            return result
        except Exception as e:
            logger.error(f"Error getting Filecoin status: {e}")
            return {"success": False, "error": str(e)}
    
    # Lassie advanced endpoints
    @router.post("/lassie/fetch")
    async def lassie_fetch(
        cid: str = Form(...),
        timeout: int = Form(60)
    ):
        """Fetch content with Lassie from the network."""
        try:
            kit = get_ipfs_kit_instance()
            if hasattr(kit, "lassie_kit"):
                result = kit.lassie_kit.fetch(cid, timeout=timeout)
            else:
                # Import directly
                from lassie_storage import LassieStorage
                storage = LassieStorage()
                result = storage.to_ipfs(cid, timeout=timeout)
            return result
        except Exception as e:
            logger.error(f"Error fetching with Lassie: {e}")
            return {"success": False, "error": str(e)}
    
    return router