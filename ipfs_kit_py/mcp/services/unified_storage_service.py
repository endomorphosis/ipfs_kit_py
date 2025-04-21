"""
Unified Storage Service for MCP server.

This module implements the Unified Data Management functionality
as specified in the MCP roadmap Q2 2025 priorities:
- Single interface for all storage operations
- Content addressing across backends
- Metadata synchronization and consistency
"""

import logging
import time
import asyncio
import io
from typing import Dict, List, Any, Optional, Union, BinaryIO, Tuple

logger = logging.getLogger(__name__)


class UnifiedStorageService:
    """
    Service providing unified access to all storage backends.

    This service implements the Unified Data Management requirement
    from the MCP roadmap.
    """
    def __init__(self, backend_registry):
        """
        Initialize the unified storage service.

        Args:
            backend_registry: Registry of storage backends
        """
        self.backend_registry = backend_registry
        self.metadata_cache = {}  # Simple in-memory cache for metadata
        self.content_location = {}  # Maps CID to backend locations

        # Statistics
        self.operation_stats = {
            "get_content": 0,
            "store_content": 0,
            "get_metadata": 0,
            "set_metadata": 0,
            "remove_content": 0,
            "list_content": 0,
            "get_content_info": 0,
        }

    async def start(self):
        """Start the unified storage service."""
        logger.info("Starting unified storage service")

        # Start background tasks
        asyncio.create_task(self._update_content_location_map())

        logger.info("Unified storage service started")

    async def _update_content_location_map(self):
        """
        Background task to update the content location map.

        This maps CIDs to their backend locations to enable
        transparent content addressing across backends.
        """
        while True:
            try:
                # Get available backends
                backends = self.backend_registry.get_available_backends()

                # Initialize new map
                new_map = {}

                # For each backend, get list of content
                for backend in backends:
                    try:
                        backend_module = self.backend_registry.get_backend(backend)
                        if backend_module and hasattr(backend_module, "list_content"):
                            content_list = await backend_module.list_content()

                            # Add to map
                            for item in content_list:
                                cid = item.get("cid")
                                if cid:
                                    if cid not in new_map:
                                        new_map[cid] = []
                                    new_map[cid].append({"backend": backend, "info": item})
                    except Exception as e:
                        logger.warning(
                            f"Error updating content location map for backend {backend}: {e}"
                        )

                # Update the map
                self.content_location = new_map
                logger.debug(f"Updated content location map, {len(new_map)} CIDs mapped")
            except Exception as e:
                logger.error(f"Error in content location map update task: {e}")

            # Sleep for 5 minutes before updating again
            await asyncio.sleep(300)

    async def get_content(self, backend: str, cid: str) -> Optional[bytes]:
        """
        Get content from a specific backend.

        Args:
            backend: Backend to get content from
            cid: Content identifier

        Returns:
            Content as bytes or None if not found
        """
        self.operation_stats["get_content"] += 1

        # Check if backend is available
        if not self.backend_registry.is_available(backend):
            logger.error(f"Backend {backend} is not available")
            return None

        # Get backend module
        backend_module = self.backend_registry.get_backend(backend)
        if not backend_module:
            logger.error(f"Backend module {backend} not found")
            return None

        try:
            # Call the appropriate method based on backend type
            if hasattr(backend_module, "get_content"):
                content = await backend_module.get_content(cid)
                return content
            elif backend == "ipfs" and hasattr(backend_module, "cat"):
                content = await backend_module.cat(cid)
                return content
            else:
                logger.error(f"Backend {backend} does not support content retrieval")
                return None
        except Exception as e:
            logger.error(f"Error getting content from {backend} for CID {cid}: {e}")
            return None

    async def get_content_from_any(self, cid: str) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Get content from any available backend that has it.

        Args:
            cid: Content identifier

        Returns:
            Tuple of (content, backend) or (None, None) if not found
        """
        # Check content location map
        locations = self.content_location.get(cid, [])

        # If we know where the content is, try those backends first
        for location in locations:
            backend = location.get("backend")
            if backend and self.backend_registry.is_available(backend):
                content = await self.get_content(backend, cid)
                if content:
                    return content, backend

        # If not found or map is not up-to-date, try all available backends
        backends = self.backend_registry.get_available_backends()
        for backend in backends:
            # Skip backends we already tried
            if any(loc.get("backend") == backend for loc in locations):
                continue

            content = await self.get_content(backend, cid)
            if content:
                # Update content location map
                if cid not in self.content_location:
                    self.content_location[cid] = []
                self.content_location[cid].append({"backend": backend, "info": {"cid": cid}})
                return content, backend

        return None, None

    async def store_content(
    self,
    backend: str
        content: Union[bytes, BinaryIO, str]
        cid: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Store content in a specific backend.

        Args:
            backend: Backend to store content in
            content: Content to store
            cid: Optional content identifier

        Returns:
            Dictionary with storage result or None on failure
        """
        self.operation_stats["store_content"] += 1

        # Check if backend is available
        if not self.backend_registry.is_available(backend):
            logger.error(f"Backend {backend} is not available")
            return None

        # Get backend module
        backend_module = self.backend_registry.get_backend(backend)
        if not backend_module:
            logger.error(f"Backend module {backend} not found")
            return None

        try:
            # Call the appropriate method based on backend type
            if hasattr(backend_module, "store_content"):
                result = await backend_module.store_content(content, cid=cid)

                # Update content location map if successful
                if result and "cid" in result:
                    new_cid = result["cid"]
                    if new_cid not in self.content_location:
                        self.content_location[new_cid] = []

                    # Add to location map
                    self.content_location[new_cid].append({"backend": backend, "info": result})

                return result
            elif backend == "ipfs" and hasattr(backend_module, "add"):
                # Convert content to appropriate format
                if isinstance(content, str):
                    content = content.encode("utf-8")

                if isinstance(content, bytes):
                    # For IPFS add, we need to create a file-like object
                    content = io.BytesIO(content)

                result = await backend_module.add(content)

                # Update content location map if successful
                if result and "Hash" in result:
                    new_cid = result["Hash"]
                    if new_cid not in self.content_location:
                        self.content_location[new_cid] = []

                    # Add to location map
                    self.content_location[new_cid].append(
                        {
                            "backend": backend,
                            "info": {"cid": new_cid, "size": result.get("Size", 0)},
                        }
                    )

                # Convert to standardized format
                return {
                    "cid": result.get("Hash"),
                    "size": result.get("Size", 0),
                    "name": result.get("Name", "unknown"),
                }
            else:
                logger.error(f"Backend {backend} does not support content storage")
                return None
        except Exception as e:
            logger.error(f"Error storing content in {backend}: {e}")
            return None

    async def get_metadata(self, backend: str, cid: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata from a specific backend.

        Args:
            backend: Backend to get metadata from
            cid: Content identifier

        Returns:
            Metadata dictionary or None if not found
        """
        self.operation_stats["get_metadata"] += 1

        # Check cache first
        cache_key = f"{backend}:{cid}"
        if cache_key in self.metadata_cache:
            # Check if cache entry is still valid (less than 5 minutes old)
            cache_entry = self.metadata_cache[cache_key]
            if (time.time() - cache_entry["timestamp"]) < 300:
                return cache_entry["metadata"]

        # Check if backend is available
        if not self.backend_registry.is_available(backend):
            logger.error(f"Backend {backend} is not available")
            return None

        # Get backend module
        backend_module = self.backend_registry.get_backend(backend)
        if not backend_module:
            logger.error(f"Backend module {backend} not found")
            return None

        try:
            # Call the appropriate method based on backend type
            if hasattr(backend_module, "get_metadata"):
                metadata = await backend_module.get_metadata(cid)

                # Update cache
                self.metadata_cache[cache_key] = {
                    "metadata": metadata,
                    "timestamp": time.time(),
                }

                return metadata
            else:
                logger.warning(f"Backend {backend} does not support metadata retrieval")
                return None
        except Exception as e:
            logger.error(f"Error getting metadata from {backend} for CID {cid}: {e}")
            return None

    async def set_metadata(self, backend: str, cid: str, metadata: Dict[str, Any]) -> bool:
        """
        Set metadata for content in a specific backend.

        Args:
            backend: Backend to set metadata in
            cid: Content identifier
            metadata: Metadata to set

        Returns:
            True if successful, False otherwise
        """
        self.operation_stats["set_metadata"] += 1

        # Check if backend is available
        if not self.backend_registry.is_available(backend):
            logger.error(f"Backend {backend} is not available")
            return False

        # Get backend module
        backend_module = self.backend_registry.get_backend(backend)
        if not backend_module:
            logger.error(f"Backend module {backend} not found")
            return False

        try:
            # Call the appropriate method based on backend type
            if hasattr(backend_module, "set_metadata"):
                result = await backend_module.set_metadata(cid, metadata)

                # Update cache
                cache_key = f"{backend}:{cid}"
                self.metadata_cache[cache_key] = {
                    "metadata": metadata,
                    "timestamp": time.time(),
                }

                return result
            else:
                logger.warning(f"Backend {backend} does not support metadata storage")
                return False
        except Exception as e:
            logger.error(f"Error setting metadata in {backend} for CID {cid}: {e}")
            return False

    async def remove_content(self, backend: str, cid: str) -> bool:
        """
        Remove content from a specific backend.

        Args:
            backend: Backend to remove content from
            cid: Content identifier

        Returns:
            True if successful, False otherwise
        """
        self.operation_stats["remove_content"] += 1

        # Check if backend is available
        if not self.backend_registry.is_available(backend):
            logger.error(f"Backend {backend} is not available")
            return False

        # Get backend module
        backend_module = self.backend_registry.get_backend(backend)
        if not backend_module:
            logger.error(f"Backend module {backend} not found")
            return False

        try:
            # Call the appropriate method based on backend type
            if hasattr(backend_module, "remove_content"):
                result = await backend_module.remove_content(cid)

                # Update content location map
                if cid in self.content_location:
                    # Remove this backend from the locations
                    self.content_location[cid] = [
                        loc for loc in self.content_location[cid] if loc.get("backend") != backend
                    ]

                    # If no locations remain, remove the CID from the map
                    if not self.content_location[cid]:
                        del self.content_location[cid]

                # Clear cache
                cache_key = f"{backend}:{cid}"
                if cache_key in self.metadata_cache:
                    del self.metadata_cache[cache_key]

                return result
            elif backend == "ipfs" and hasattr(backend_module, "pin_rm"):
                # For IPFS, removing means unpinning
                result = await backend_module.pin_rm(cid)

                # Update content location map
                if cid in self.content_location:
                    # Remove this backend from the locations
                    self.content_location[cid] = [
                        loc for loc in self.content_location[cid] if loc.get("backend") != backend
                    ]

                    # If no locations remain, remove the CID from the map
                    if not self.content_location[cid]:
                        del self.content_location[cid]

                return True
            else:
                logger.warning(f"Backend {backend} does not support content removal")
                return False
        except Exception as e:
            logger.error(f"Error removing content from {backend} for CID {cid}: {e}")
            return False

    async def list_content(
        self, backend: str, prefix: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List content in a specific backend.

        Args:
            backend: Backend to list content from
            prefix: Optional prefix to filter by
            limit: Maximum number of items to return

        Returns:
            List of content items
        """
        self.operation_stats["list_content"] += 1

        # Check if backend is available
        if not self.backend_registry.is_available(backend):
            logger.error(f"Backend {backend} is not available")
            return []

        # Get backend module
        backend_module = self.backend_registry.get_backend(backend)
        if not backend_module:
            logger.error(f"Backend module {backend} not found")
            return []

        try:
            # Call the appropriate method based on backend type
            if hasattr(backend_module, "list_content"):
                items = await backend_module.list_content(prefix=prefix, limit=limit)
                return items
            elif backend == "ipfs" and hasattr(backend_module, "pin_ls"):
                # For IPFS, list pinned items
                pins = await backend_module.pin_ls()

                # Convert to standardized format
                items = []
                for cid, pin_info in pins.items():
                    if prefix and not cid.startswith(prefix):
                        continue

                    items.append(
                        {
                            "cid": cid,
                            "type": pin_info.get("Type", "unknown"),
                            "size": 0,  # Size not available from pin_ls
                        }
                    )

                    if len(items) >= limit:
                        break

                return items
            else:
                logger.warning(f"Backend {backend} does not support content listing")
                return []
        except Exception as e:
            logger.error(f"Error listing content from {backend}: {e}")
            return []

    async def get_content_info(self, backend: str, cid: str) -> Optional[Dict[str, Any]]:
        """
        Get information about content in a specific backend.

        Args:
            backend: Backend to get content info from
            cid: Content identifier

        Returns:
            Content information or None if not found
        """
        self.operation_stats["get_content_info"] += 1

        # Check if backend is available
        if not self.backend_registry.is_available(backend):
            logger.error(f"Backend {backend} is not available")
            return None

        # Get backend module
        backend_module = self.backend_registry.get_backend(backend)
        if not backend_module:
            logger.error(f"Backend module {backend} not found")
            return None

        try:
            # Call the appropriate method based on backend type
            if hasattr(backend_module, "get_content_info"):
                info = await backend_module.get_content_info(cid)
                return info
            elif backend == "ipfs" and hasattr(backend_module, "object_stat"):
                # For IPFS, use object stat
                stats = await backend_module.object_stat(cid)

                # Convert to standardized format
                return {
                    "cid": cid,
                    "size": stats.get("CumulativeSize", 0),
                    "blocks": stats.get("NumLinks", 0),
                    "links": stats.get("Links", []),
                }
            else:
                logger.warning(f"Backend {backend} does not support content info retrieval")
                return None
        except Exception as e:
            logger.error(f"Error getting content info from {backend} for CID {cid}: {e}")
            return None

    async def list_locations(self, cid: str) -> List[Dict[str, Any]]:
        """
        List all backends where a content item is stored.

        Args:
            cid: Content identifier

        Returns:
            List of backend locations
        """
        # Check content location map
        locations = self.content_location.get(cid, [])

        # Return copy of locations
        return [loc.copy() for loc in locations]

    async def replicate_content(self, cid: str, source_backend: str, target_backend: str) -> bool:
        """
        Replicate content from one backend to another.

        Args:
            cid: Content identifier
            source_backend: Source backend
            target_backend: Target backend

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get content from source backend
            content = await self.get_content(source_backend, cid)
            if not content:
                logger.error(f"Content {cid} not found in {source_backend}")
                return False

            # Store in target backend
            result = await self.store_content(target_backend, content, cid)
            if not result:
                logger.error(f"Failed to store content {cid} in {target_backend}")
                return False

            # Get metadata if available
            metadata = await self.get_metadata(source_backend, cid)
            if metadata:
                # Store metadata in target
                await self.set_metadata(target_backend, result.get("cid", cid), metadata)

            return True
        except Exception as e:
            logger.error(
                f"Error replicating content {cid} from {source_backend} to {target_backend}: {e}"
            )
            return False

    async def sync_metadata(
        self, cid: str, source_backend: str, target_backends: List[str]
    ) -> Dict[str, bool]:
        """
        Synchronize metadata from one backend to others.

        Args:
            cid: Content identifier
            source_backend: Source backend for metadata
            target_backends: Target backends to sync to

        Returns:
            Dictionary of backend to success status
        """
        results = {}

        try:
            # Get metadata from source backend
            metadata = await self.get_metadata(source_backend, cid)
            if not metadata:
                logger.error(f"Metadata for {cid} not found in {source_backend}")
                return {backend: False for backend in target_backends}

            # Sync to each target backend
            for backend in target_backends:
                try:
                    # Check if backend has the content
                    info = await self.get_content_info(backend, cid)
                    if not info:
                        logger.warning(
                            f"Content {cid} not found in {backend}, cannot sync metadata"
                        )
                        results[backend] = False
                        continue

                    # Set metadata
                    success = await self.set_metadata(backend, cid, metadata)
                    results[backend] = success
                except Exception as e:
                    logger.error(f"Error syncing metadata to {backend}: {e}")
                    results[backend] = False

            return results
        except Exception as e:
            logger.error(f"Error syncing metadata for {cid} from {source_backend}: {e}")
            return {backend: False for backend in target_backends}

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get storage service statistics.

        Returns:
            Dictionary of statistics
        """
        stats = {
            "operations": self.operation_stats.copy(),
            "content_locations": len(self.content_location),
            "metadata_cache": len(self.metadata_cache),
            "backend_count": len(self.backend_registry.get_available_backends()),
            "backends": self.backend_registry.get_available_backends(),
        }

        return stats
