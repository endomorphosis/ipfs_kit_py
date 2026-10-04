"""
Unified Data Management extension for MCP server.

This module provides a single interface for all storage operations across backends
as specified in the MCP roadmap Q2 2025 priorities.

Features:
- Single interface for all storage operations
- Content addressing across backends
- Metadata synchronization and consistency
"""

import base64
import hashlib
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
CONTENT_REGISTRY_FILE = "content_registry.json"
METADATA_REGISTRY_FILE = "metadata_registry.json"
CONTENT_MAP_FILE = "content_map.json"

# Directory for unified data management files
UDM_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "udm_data")
os.makedirs(UDM_DIR, exist_ok=True)

# Full paths
CONTENT_REGISTRY_PATH = os.path.join(UDM_DIR, CONTENT_REGISTRY_FILE)
METADATA_REGISTRY_PATH = os.path.join(UDM_DIR, METADATA_REGISTRY_FILE)
CONTENT_MAP_PATH = os.path.join(UDM_DIR, CONTENT_MAP_FILE)

# Storage backend attributes - will be populated from the MCP server
storage_backends = {
    "ipfs": {"available": True, "simulation": False},
    "local": {"available": True, "simulation": False},
    "huggingface": {"available": False, "simulation": True},
    "s3": {"available": False, "simulation": True},
    "filecoin": {"available": False, "simulation": True},
    "storacha": {"available": False, "simulation": True},
    "lassie": {"available": False, "simulation": True},
}


# Data models
class StoreRequest(BaseModel):
    """Store content request model."""

    content_name: Optional[str] = None
    content_type: Optional[str] = None
    preferred_backend: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = {}
    tags: List[str] = []


class ContentInfo(BaseModel):
    """Content information model."""

    cid: str
    name: Optional[str] = None
    size: Optional[int] = None
    content_type: Optional[str] = None
    created_at: float
    updated_at: float
    backends: Dict[str, str] = {}
    primary_backend: Optional[str] = None
    tags: List[str] = []


class ContentQuery(BaseModel):
    """Content query parameters."""

    tags: Optional[List[str]] = None
    name_contains: Optional[str] = None
    content_type: Optional[str] = None
    limit: int = 100
    offset: int = 0


# Data registries
content_registry = {}
metadata_registry = {}
content_map = {"backend_to_cid": {}, "cid_to_backend": {}}


# Initialization functions
def initialize_content_registry():
    """Initialize content registry from file or create empty."""
    global content_registry
    try:
        if os.path.exists(CONTENT_REGISTRY_PATH):
            with open(CONTENT_REGISTRY_PATH, "r") as f:
                content_registry = json.load(f)
            logger.info(
                f"Loaded {len(content_registry)} content entries from {CONTENT_REGISTRY_PATH}"
            )
        else:
            content_registry = {}
            with open(CONTENT_REGISTRY_PATH, "w") as f:
                json.dump(content_registry, f, indent=2)
            logger.info(f"Created empty content registry in {CONTENT_REGISTRY_PATH}")
    except Exception as e:
        logger.error(f"Error initializing content registry: {e}")
        content_registry = {}


def initialize_metadata_registry():
    """Initialize metadata registry from file or create empty."""
    global metadata_registry
    try:
        if os.path.exists(METADATA_REGISTRY_PATH):
            with open(METADATA_REGISTRY_PATH, "r") as f:
                metadata_registry = json.load(f)
            logger.info(
                f"Loaded {len(metadata_registry)} metadata entries from {METADATA_REGISTRY_PATH}"
            )
        else:
            metadata_registry = {}
            with open(METADATA_REGISTRY_PATH, "w") as f:
                json.dump(metadata_registry, f, indent=2)
            logger.info(f"Created empty metadata registry in {METADATA_REGISTRY_PATH}")
    except Exception as e:
        logger.error(f"Error initializing metadata registry: {e}")
        metadata_registry = {}


def initialize_content_map():
    """Initialize content map from file or create empty."""
    global content_map
    try:
        if os.path.exists(CONTENT_MAP_PATH):
            with open(CONTENT_MAP_PATH, "r") as f:
                content_map = json.load(f)
            logger.info(f"Loaded content map from {CONTENT_MAP_PATH}")
        else:
            content_map = {
                "backend_to_cid": {},  # backend_id -> {backend_cid -> cid}
                "cid_to_backend": {},  # cid -> {backend -> backend_cid}
            }
            with open(CONTENT_MAP_PATH, "w") as f:
                json.dump(content_map, f, indent=2)
            logger.info(f"Created empty content map in {CONTENT_MAP_PATH}")
    except Exception as e:
        logger.error(f"Error initializing content map: {e}")
        content_map = {"backend_to_cid": {}, "cid_to_backend": {}}


# Save functions
def save_content_registry():
    """Save content registry to file."""
    try:
        with open(CONTENT_REGISTRY_PATH, "w") as f:
            json.dump(content_registry, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving content registry: {e}")


def save_metadata_registry():
    """Save metadata registry to file."""
    try:
        with open(METADATA_REGISTRY_PATH, "w") as f:
            json.dump(metadata_registry, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving metadata registry: {e}")


def save_content_map():
    """Save content map to file."""
    try:
        with open(CONTENT_MAP_PATH, "w") as f:
            json.dump(content_map, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving content map: {e}")


# Helper functions
def create_content_id(content):
    """Create a content ID from binary content."""
    content_hash = hashlib.sha256(content).digest()
    cid = "udm_" + base64.urlsafe_b64encode(content_hash).decode("utf-8").rstrip("=")
    return cid


def get_backend_module(backend: str):
    """Get the backend module for a specific backend."""
    try:
        if backend == "ipfs": # Removed comma
            # We'll handle IPFS operations directly
            return None
        elif backend == "local": # Removed comma
            # We'll handle local operations directly
            return None
        elif backend == "huggingface": # Removed comma
            from .huggingface import huggingface_operations # Relative import

            return huggingface_operations
        elif backend == "s3": # Removed comma
            from .s3 import s3_operations # Relative import

            return s3_operations
        elif backend == "filecoin": # Removed comma
            from .filecoin import filecoin_operations # Relative import

            return filecoin_operations
        elif backend == "storacha": # Removed comma
            from .storacha import storacha_operations # Relative import

            return storacha_operations
        elif backend == "lassie": # Removed comma
            from .lassie import lassie_operations # Relative import

            return lassie_operations
    except ImportError as e:
        logger.error(f"Backend module for {backend} not found: {e}")
    return None


def get_available_backends():
    """Get list of available backends."""
    return [name for name, info in storage_backends.items() if info.get("available", False)]


def map_backend_cid(cid, backend, backend_cid):
    """Map a backend-specific CID to the unified CID."""
    # Initialize backend in content_map if not exists
    if backend not in content_map["backend_to_cid"]:
        content_map["backend_to_cid"][backend] = {}

    # Store mapping in both directions
    content_map["backend_to_cid"][backend][backend_cid] = cid

    if cid not in content_map["cid_to_backend"]:
        content_map["cid_to_backend"][cid] = {}

    content_map["cid_to_backend"][cid][backend] = backend_cid

    # Save updated map
    save_content_map()


def get_unified_cid_from_backend(backend, backend_cid):
    """Get the unified CID for a backend-specific CID."""
    if (
        backend in content_map["backend_to_cid"]
        and backend_cid in content_map["backend_to_cid"][backend]
    ):
        return content_map["backend_to_cid"][backend][backend_cid]
    return None


def get_backend_cid(cid, backend):
    """Get the backend-specific CID for a unified CID."""
    if cid in content_map["cid_to_backend"] and backend in content_map["cid_to_backend"][cid]:
        return content_map["cid_to_backend"][cid][backend]
    return None


def filter_content_by_query(query: ContentQuery):
    """Filter content registry based on query parameters."""
    results = []

    for cid, info in content_registry.items():
        # Filter by tags
        if query.tags and not all(tag in info.get("tags", []) for tag in query.tags):
            continue

        # Filter by name
        if query.name_contains and (
            not info.get("name") or query.name_contains.lower() not in info.get("name", "").lower()
        ):
            continue

        # Filter by content type
        if query.content_type and info.get("content_type") != query.content_type:
            continue

        # Add to results
        results.append(info)

    # Sort by creation time (newest first)
    results.sort(key=lambda x: x.get("created_at", 0), reverse=True)

    # Apply pagination
    paginated = results[query.offset : query.offset + query.limit]

    return paginated, len(results)


# Core operations
async def store_content_in_backend(content, content_name, content_type, backend, cid = None):
    """Store content in a specific backend and return backend-specific CID."""
    try:
        backend_module = get_backend_module(backend)

        if backend == "ipfs": # Removed comma
            # Use subprocess to call ipfs add
            import subprocess
            import tempfile

            # Write content to temporary file
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            # Add to IPFS
            result = subprocess.run(["ipfs", "add", "-q", tmp_path], capture_output=True, text=True)

            # Remove temp file

            os.unlink(tmp_path)

            if result.returncode != 0:
                raise Exception(f"IPFS add failed: {result.stderr}")

            backend_cid = result.stdout.strip()
            return backend_cid

        elif backend == "local": # Removed comma
            # Store in a local file repository
            import tempfile

            # Create a local storage directory if it doesn't exist
            local_storage_dir = os.path.join(UDM_DIR, "local_storage")
            os.makedirs(local_storage_dir, exist_ok=True)

            # Use the provided CID or generate one
            backend_cid = cid or create_content_id(content)

            # Create a file with the CID as name
            content_path = os.path.join(local_storage_dir, backend_cid)
            with open(content_path, "wb") as f:
                f.write(content)

            return backend_cid

        elif backend_module and hasattr(backend_module, "store_content"):
            # Use the backend module's store_content function
            result = await backend_module.store_content(content, content_name, content_type)
            return result.get("cid")

        else:
            raise Exception(f"Backend {backend} does not support content storage")

    except Exception as e:
        logger.error(f"Error storing content in {backend}: {e}")
        raise


async def retrieve_content_from_backend(cid, backend):
    """Retrieve content from a specific backend."""
    try:
        # Get backend-specific CID
        backend_cid = get_backend_cid(cid, backend)
        if not backend_cid:
            raise Exception(f"No mapping found for CID {cid} in backend {backend}")

        backend_module = get_backend_module(backend)

        if backend == "ipfs": # Removed comma
            # Use subprocess to call ipfs cat
            import subprocess

            result = subprocess.run(["ipfs", "cat", backend_cid], capture_output=True)

            if result.returncode != 0:
                raise Exception(f"IPFS cat failed: {result.stderr.decode('utf-8')}")

            return result.stdout

        elif backend == "local": # Removed comma
            # Retrieve from local file repository

            local_storage_dir = os.path.join(UDM_DIR, "local_storage")
            content_path = os.path.join(local_storage_dir, backend_cid)

            if not os.path.exists(content_path):
                raise Exception(f"Content not found in local storage: {backend_cid}")

            with open(content_path, "rb") as f:
                return f.read()

        elif backend_module and hasattr(backend_module, "get_content"):
            # Use the backend module's get_content function
            content = await backend_module.get_content(backend_cid)
            return content

        else:
            raise Exception(f"Backend {backend} does not support content retrieval")

    except Exception as e:
        logger.error(f"Error retrieving content from {backend}: {e}")
        raise


# Main operations
async def store_content(content, request: StoreRequest):
    """Store content with the unified data management system."""
    try:
        # Generate a unified content ID
        cid = create_content_id(content)

        # Check if content already exists
        if cid in content_registry:
            return {"success": True, "cid": cid, "already_exists": True}

        # Determine target backend
        target_backend = request.preferred_backend

        # If no specific backend requested, use the routing extension if available
        if not target_backend:
            try:
                from .routing import ( # Relative import
                    ContentAttributes,
                    RoutingRequest,
                    make_routing_decision,
                )

                # Create a routing request
                routing_req = RoutingRequest(
                    operation="write",
                    content_attributes=ContentAttributes(
                        content_type=request.content_type,
                        size_bytes=len(content),
                        filename=request.content_name,
                    ),
                )

                # Get routing decision
                decision = make_routing_decision(routing_req)
                target_backend = decision.primary_backend
                logger.info(f"Routing decision for content: {target_backend}")

            except ImportError:
                # If routing extension not available, use a default backend
                available_backends = get_available_backends()
                if "ipfs" in available_backends:
                    target_backend = "ipfs"
                elif available_backends:
                    target_backend = available_backends[0]
                else:
                    raise Exception("No available storage backends")

        # Verify the target backend is available
        if target_backend not in storage_backends or not storage_backends[target_backend].get(
            "available", False
        ):
            raise Exception(f"Target backend {target_backend} is not available")

        # Store content in the target backend
        backend_cid = await store_content_in_backend(
            content, request.content_name, request.content_type, target_backend, cid
        )

        if not backend_cid:
            raise Exception(f"Failed to store content in {target_backend}")

        # Map the backend CID to our unified CID
        map_backend_cid(cid, target_backend, backend_cid)

        # Create content registry entry
        content_info = {
            "cid": cid,
            "name": request.content_name,
            "size": len(content),
            "content_type": request.content_type,
            "created_at": time.time(),
            "updated_at": time.time(),
            "backends": {target_backend: backend_cid},
            "primary_backend": target_backend,
            "tags": request.tags,
        }

        content_registry[cid] = content_info
        save_content_registry()

        # Create metadata entry if provided
        if request.metadata:
            metadata_registry[cid] = {
                "metadata": request.metadata,
                "updated_at": time.time(),
            }
            save_metadata_registry()

        # Return result
        return {"success": True, "cid": cid, "primary_backend": target_backend}

    except Exception as e:
        logger.error(f"Error storing content: {e}")
        return {"success": False, "error": str(e)}


async def retrieve_content(cid, preferred_backend = None):
    """Retrieve content using the unified data management system."""
    try:
        # Check if content exists in our registry
        if cid not in content_registry:
            raise Exception(f"Content not found: {cid}")

        content_info = content_registry[cid]

        # Determine which backend to use
        source_backend = preferred_backend

        # If no preference, use primary backend
        if not source_backend:
            source_backend = content_info.get("primary_backend")

        # Verify the source backend is available and has the content
        if (
            source_backend not in content_info.get("backends", {})
            or source_backend not in storage_backends
            or not storage_backends[source_backend].get("available", False)
        ):
            # If preferred backend not available, try to find another one
            available_backends = [
                b
                for b in content_info.get("backends", {}).keys()
                if b in storage_backends and storage_backends[b].get("available", False)
            ]

            if not available_backends:
                raise Exception(f"Content {cid} not available in any active backend")

            # Use the first available backend
            source_backend = available_backends[0]

        # Retrieve content from the backend
        content = await retrieve_content_from_backend(cid, source_backend)

        if not content:
            raise Exception(f"Failed to retrieve content from {source_backend}")

        # Return the content and metadata
        return content, {
            "success": True,
            "cid": cid,
            "source_backend": source_backend,
            "content_type": content_info.get("content_type"),
            "name": content_info.get("name"),
            "size": len(content),
        }

    except Exception as e:
        logger.error(f"Error retrieving content: {e}")
        return None, {"success": False, "error": str(e)}


# Create router
def create_udm_router(api_prefix: str) -> APIRouter:
    """Create FastAPI router for unified data management."""
    router = APIRouter(prefix=f"{api_prefix}/udm", tags=["unified_data_management"])

    @router.get("/status")
    async def get_udm_status():
        """Get unified data management status."""
        try:
            # Count content by backend
            backend_counts = {}
            for cid, info in content_registry.items():
                for backend in info.get("backends", {}).keys():
                    if backend not in backend_counts:
                        backend_counts[backend] = 0
                    backend_counts[backend] += 1

            # Get available backends
            available_backends = get_available_backends()

            return {
                "success": True,
                "content_count": len(content_registry),
                "metadata_count": len(metadata_registry),
                "backend_content_counts": backend_counts,
                "available_backends": available_backends,
            }
        except Exception as e:
            logger.error(f"Error getting UDM status: {e}")
            return {"success": False, "error": str(e)}

    @router.post("/store")
    async def store_content_api(request: StoreRequest = Form(...), file: UploadFile = File(...)):
        """Store content with unified data management."""
        try:
            content = await file.read()

            # Use filename from the uploaded file if not specified in request
            if not request.content_name and file.filename:
                request.content_name = file.filename

            # Use content type from the uploaded file if not specified in request
            if not request.content_type and file.content_type:
                request.content_type = file.content_type

            result = await store_content(content, request)
            return result
        except Exception as e:
            logger.error(f"Error in store_content_api: {e}")
            return {"success": False, "error": str(e)}

    @router.get("/retrieve/{cid}")
    async def retrieve_content_api(cid: str, preferred_backend: Optional[str] = None):
        """Retrieve content by CID."""
        try:
            content, metadata = await retrieve_content(cid, preferred_backend)

            if not content:
                return metadata  # This will contain error information

            # Get content info for headers
            content_info = content_registry.get(cid, {})

            # Prepare response with appropriate content type
            content_type = content_info.get("content_type", "application/octet-stream")
            filename = content_info.get("name", cid)

            # Define a generator for streaming the content
            async def content_generator():
                yield content

            # Use StreamingResponse for large file support
            response = StreamingResponse(content_generator(), media_type=content_type)

            # Add content disposition header for downloads
            if filename:
                response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'

            # Add metadata headers
            response.headers["X-UDM-CID"] = cid
            response.headers["X-UDM-Backend"] = metadata.get("source_backend", "")
            response.headers["X-UDM-Size"] = str(metadata.get("size", 0))

            return response
        except Exception as e:
            logger.error(f"Error in retrieve_content_api: {e}")
            return {"success": False, "error": str(e)}

    @router.get("/info/{cid}")
    async def get_content_info(cid: str):
        """Get information about content."""
        try:
            if cid not in content_registry:
                return {"success": False, "error": f"Content not found: {cid}"}

            # Get content info
            content_info = content_registry[cid]

            # Get metadata if available
            metadata = metadata_registry.get(cid, {}).get("metadata", {})

            return {"success": True, "content": content_info, "metadata": metadata}
        except Exception as e:
            logger.error(f"Error getting content info: {e}")
            return {"success": False, "error": str(e)}

    @router.post("/query")
    async def query_content(query: ContentQuery):
        """Query content based on criteria."""
        try:
            results, total_count = filter_content_by_query(query)

            return {
                "success": True,
                "results": results,
                "total_count": total_count,
                "returned_count": len(results),
                "offset": query.offset,
                "limit": query.limit,
            }
        except Exception as e:
            logger.error(f"Error querying content: {e}")
            return {"success": False, "error": str(e)}

    return router


# Update storage backends status
def update_udm_status(storage_backends_info: Dict[str, Any]) -> None:
    """Update the reference to storage backends status."""
    global storage_backends
    storage_backends = storage_backends_info


# Initialize
def initialize():
    """Initialize the unified data management system."""
    initialize_content_registry()
    initialize_metadata_registry()
    initialize_content_map()
    logger.info("Unified data management system initialized")


# Call initialization
initialize()
