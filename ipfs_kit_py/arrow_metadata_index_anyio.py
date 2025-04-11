"""
Arrow-based metadata index for IPFS content with AnyIO support.

This module provides asynchronous versions of the Arrow-based metadata index functions,
supporting both asyncio and trio via AnyIO. It wraps the synchronous ArrowMetadataIndex
methods with async equivalents for better performance in async contexts.
"""

import anyio
import logging
import os
import sniffio
import time
import uuid
import warnings
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Import the synchronous implementation
from ipfs_kit_py.arrow_metadata_index import ArrowMetadataIndex, ARROW_AVAILABLE, PLASMA_AVAILABLE

# Configure logger
logger = logging.getLogger(__name__)


class ArrowMetadataIndexAnyIO(ArrowMetadataIndex):
    """AnyIO-compatible Arrow-based metadata index for IPFS content.
    
    This class extends the synchronous ArrowMetadataIndex with asynchronous versions of
    all methods, ensuring efficient operation in async contexts. It supports both
    asyncio and trio via the AnyIO library.
    """
    
    def __init__(
        self,
        index_dir: str = "~/.ipfs_metadata",
        partition_size: int = 1000000,
        role: str = "leecher",
        sync_interval: int = 300,
        enable_c_interface: bool = True,
        ipfs_client=None,
        node_id: Optional[str] = None,
        cluster_id: str = "default",
    ):
        """Initialize the AnyIO-compatible Arrow-based metadata index.
        
        Args:
            index_dir: Directory to store index partitions
            partition_size: Maximum number of records per partition
            role: Node role (master, worker, or leecher)
            sync_interval: Interval for synchronizing with peers (seconds)
            enable_c_interface: Whether to enable the Arrow C Data Interface
            ipfs_client: IPFS client instance for distributed operations
            node_id: Unique identifier for this node
            cluster_id: Identifier for the cluster this node belongs to
        """
        super().__init__(
            index_dir=index_dir,
            partition_size=partition_size,
            role=role,
            sync_interval=sync_interval,
            enable_c_interface=enable_c_interface,
            ipfs_client=ipfs_client,
            node_id=node_id,
            cluster_id=cluster_id,
        )
        
        logger.info("ArrowMetadataIndexAnyIO initialized")
    
    @staticmethod
    def get_backend():
        """Get the current async backend being used.
        
        Returns:
            String name of the async backend or None if not in an async context
        """
        try:
            return sniffio.current_async_library()
        except sniffio.AsyncLibraryNotFoundError:
            return None
    
    def _warn_if_async_context(self, method_name):
        """Warn if called from async context without using async version.
        
        Args:
            method_name: The name of the method being called
        """
        backend = self.get_backend()
        if backend is not None:
            warnings.warn(
                f"Synchronous method {method_name} called from async context. "
                f"Use {method_name}_async instead for better performance.",
                stacklevel=3
            )
    
    # Override parent methods to add warning in async context
    def add(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Add a metadata record to the index.
        
        Args:
            record: Dictionary with metadata fields
            
        Returns:
            Result dictionary with operation status
        """
        self._warn_if_async_context("add")
        return super().add(record)
    
    async def add_async(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Async version: Add a metadata record to the index.
        
        Args:
            record: Dictionary with metadata fields
            
        Returns:
            Result dictionary with operation status
        """
        result = {"success": False, "operation": "add_metadata_async", "timestamp": time.time()}
        
        if not ARROW_AVAILABLE:
            result["error"] = "PyArrow is not available"
            return result
        
        try:
            # Run the add operation in a thread
            # Pass self explicitly to avoid super() issues in lambda
            result = await anyio.to_thread.run_sync(
                lambda: ArrowMetadataIndex.add(self, record)
            )
            
            return result
            
        except Exception as e:
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.error(f"Error adding record asynchronously: {e}")
            return result
    
    def get_by_cid(self, cid: str) -> Optional[Dict[str, Any]]:
        """Get a metadata record by CID.
        
        Args:
            cid: Content identifier
            
        Returns:
            Metadata record or None if not found
        """
        self._warn_if_async_context("get_by_cid")
        return super().get_by_cid(cid)
    
    async def get_by_cid_async(self, cid: str) -> Optional[Dict[str, Any]]:
        """Async version: Get a metadata record by CID.
        
        Args:
            cid: Content identifier
            
        Returns:
            Metadata record or None if not found
        """
        try:
            # Run the get_by_cid operation in a thread
            return await anyio.to_thread.run_sync(
                lambda: ArrowMetadataIndex.get_by_cid(self, cid)
            )
            
        except Exception as e:
            logger.error(f"Error getting record by CID asynchronously: {e}")
            return None
    
    def update_stats(self, cid: str, access_type: str = "read") -> bool:
        """Update access statistics for a record.
        
        Args:
            cid: Content identifier
            access_type: Type of access (read, write, etc.)
            
        Returns:
            True if successful, False otherwise
        """
        self._warn_if_async_context("update_stats")
        return super().update_stats(cid, access_type)
    
    async def update_stats_async(self, cid: str, access_type: str = "read") -> bool:
        """Async version: Update access statistics for a record.
        
        Args:
            cid: Content identifier
            access_type: Type of access (read, write, etc.)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Run the update_stats operation in a thread
            return await anyio.to_thread.run_sync(
                lambda: ArrowMetadataIndex.update_stats(self, cid, access_type)
            )
            
        except Exception as e:
            logger.error(f"Error updating stats asynchronously for CID {cid}: {e}")
            return False
    
    def delete_by_cid(self, cid: str) -> bool:
        """Delete a record by CID.
        
        Args:
            cid: Content identifier
            
        Returns:
            True if successful, False otherwise
        """
        self._warn_if_async_context("delete_by_cid")
        return super().delete_by_cid(cid)
    
    async def delete_by_cid_async(self, cid: str) -> bool:
        """Async version: Delete a record by CID.
        
        Args:
            cid: Content identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Run the delete_by_cid operation in a thread
            return await anyio.to_thread.run_sync(
                lambda: ArrowMetadataIndex.delete_by_cid(self, cid)
            )
            
        except Exception as e:
            logger.error(f"Error deleting record asynchronously for CID {cid}: {e}")
            return False
    
    def query(
        self,
        filters: Optional[List[Tuple[str, str, Any]]] = None,
        columns: Optional[List[str]] = None,
        limit: Optional[int] = None,
    ) -> Any:
        """Query the metadata index.
        
        Args:
            filters: List of filter conditions as (field, op, value) tuples
            columns: List of columns to include in the result
            limit: Maximum number of rows to return
            
        Returns:
            Arrow Table with query results
        """
        self._warn_if_async_context("query")
        return super().query(filters, columns, limit)
    
    async def query_async(
        self,
        filters: Optional[List[Tuple[str, str, Any]]] = None,
        columns: Optional[List[str]] = None,
        limit: Optional[int] = None,
    ) -> Any:
        """Async version: Query the metadata index.
        
        Args:
            filters: List of filter conditions as (field, op, value) tuples
            columns: List of columns to include in the result
            limit: Maximum number of rows to return
            
        Returns:
            Arrow Table with query results
        """
        try:
            # Run the query operation in a thread
            return await anyio.to_thread.run_sync(
                lambda: ArrowMetadataIndex.query(self, filters, columns, limit)
            )
            
        except Exception as e:
            logger.error(f"Error executing query asynchronously: {e}")
            # Return empty table with schema
            if not ARROW_AVAILABLE:
                return None
                
            import pyarrow as pa
            
            empty_arrays = []
            if columns is not None:
                schema_fields = [field for field in self.schema if field.name in columns]
                schema = pa.schema(schema_fields)
            else:
                schema = self.schema
            
            for field in schema:
                empty_arrays.append(pa.array([], type=field.type))
            
            return pa.Table.from_arrays(empty_arrays, schema=schema)
    
    def search_text(
        self, text: str, fields: Optional[List[str]] = None, limit: Optional[int] = None
    ) -> Any:
        """Search for text across multiple fields.
        
        Args:
            text: Text to search for
            fields: Fields to search in (defaults to all string fields)
            limit: Maximum number of results to return
            
        Returns:
            Arrow Table with search results
        """
        self._warn_if_async_context("search_text")
        return super().search_text(text, fields, limit)
    
    async def search_text_async(
        self, text: str, fields: Optional[List[str]] = None, limit: Optional[int] = None
    ) -> Any:
        """Async version: Search for text across multiple fields.
        
        Args:
            text: Text to search for
            fields: Fields to search in (defaults to all string fields)
            limit: Maximum number of results to return
            
        Returns:
            Arrow Table with search results
        """
        try:
            # Run the search_text operation in a thread
            return await anyio.to_thread.run_sync(
                lambda: ArrowMetadataIndex.search_text(self, text, fields, limit)
            )
            
        except Exception as e:
            logger.error(f"Error executing text search asynchronously: {e}")
            # Return empty table
            if not ARROW_AVAILABLE:
                return None
                
            import pyarrow as pa
            
            empty_arrays = []
            for field in self.schema:
                empty_arrays.append(pa.array([], type=field.type))
            
            return pa.Table.from_arrays(empty_arrays, schema=self.schema)
    
    def count(self, filters: Optional[List[Tuple[str, str, Any]]] = None) -> int:
        """Count records matching filters.
        
        Args:
            filters: List of filter conditions as (field, op, value) tuples
            
        Returns:
            Number of matching records
        """
        self._warn_if_async_context("count")
        return super().count(filters)
    
    async def count_async(self, filters: Optional[List[Tuple[str, str, Any]]] = None) -> int:
        """Async version: Count records matching filters.
        
        Args:
            filters: List of filter conditions as (field, op, value) tuples
            
        Returns:
            Number of matching records
        """
        try:
            # Run the count operation in a thread
            return await anyio.to_thread.run_sync(
                lambda: ArrowMetadataIndex.count(self, filters)
            )
            
        except Exception as e:
            logger.error(f"Error counting records asynchronously: {e}")
            return 0
    
    def _sync_with_peers(self) -> Dict[str, Any]:
        """Synchronize index with peers.
        
        Returns:
            Result dictionary with sync status
        """
        self._warn_if_async_context("_sync_with_peers")
        return super()._sync_with_peers()
    
    async def _sync_with_peers_async(self) -> Dict[str, Any]:
        """Async version: Synchronize index with peers.
        
        Returns:
            Result dictionary with sync status
        """
        result = {
            "success": False,
            "operation": "sync_with_peers_async",
            "timestamp": time.time(),
            "peers_found": 0,
            "partitions_synced": 0,
        }
        
        try:
            # Run the _sync_with_peers operation in a thread
            return await anyio.to_thread.run_sync(
                lambda: ArrowMetadataIndex._sync_with_peers(self)
            )
            
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Error syncing with peers asynchronously: {e}")
            return result
    
    def handle_partition_request(self, request_data: Dict[str, Any]):
        """Handle a request for partition metadata.
        
        Args:
            request_data: Request data including requester ID
        """
        self._warn_if_async_context("handle_partition_request")
        return super().handle_partition_request(request_data)
    
    async def handle_partition_request_async(self, request_data: Dict[str, Any]):
        """Async version: Handle a request for partition metadata.
        
        Args:
            request_data: Request data including requester ID
        """
        try:
            # Run the handle_partition_request operation in a thread
            await anyio.to_thread.run_sync(
                lambda: ArrowMetadataIndex.handle_partition_request(self, request_data)
            )
            
        except Exception as e:
            logger.error(f"Error handling partition request asynchronously: {e}")
    
    def handle_partition_data_request(self, request_data: Dict[str, Any]):
        """Handle a request for partition data.
        
        Args:
            request_data: Request data including requester ID and partition ID
        """
        self._warn_if_async_context("handle_partition_data_request")
        return super().handle_partition_data_request(request_data)
    
    async def handle_partition_data_request_async(self, request_data: Dict[str, Any]):
        """Async version: Handle a request for partition data.
        
        Args:
            request_data: Request data including requester ID and partition ID
        """
        try:
            # Run the handle_partition_data_request operation in a thread
            await anyio.to_thread.run_sync(
                lambda: ArrowMetadataIndex.handle_partition_data_request(self, request_data)
            )
            
        except Exception as e:
            logger.error(f"Error handling partition data request asynchronously: {e}")
    
    def publish_index_dag(self) -> Dict[str, Any]:
        """Publish the metadata index to IPFS DAG for discoverable access.
        
        Returns:
            Dictionary with operation result
        """
        self._warn_if_async_context("publish_index_dag")
        return super().publish_index_dag()
    
    async def publish_index_dag_async(self) -> Dict[str, Any]:
        """Async version: Publish the metadata index to IPFS DAG for discoverable access.
        
        Returns:
            Dictionary with operation result
        """
        try:
            # Run the publish_index_dag operation in a thread
            return await anyio.to_thread.run_sync(
                lambda: ArrowMetadataIndex.publish_index_dag(self)
            )
            
        except Exception as e:
            logger.error(f"Error publishing index DAG asynchronously: {e}")
            return {"success": False, "error": str(e)}
    
    def close(self) -> None:
        """Close the metadata index and clean up resources."""
        self._warn_if_async_context("close")
        return super().close()
    
    async def close_async(self) -> None:
        """Async version: Close the metadata index and clean up resources."""
        try:
            # Run the close operation in a thread
            await anyio.to_thread.run_sync(
                lambda: ArrowMetadataIndex.close(self)
            )
            
        except Exception as e:
            logger.error(f"Error closing metadata index asynchronously: {e}")
    
    @staticmethod
    async def access_via_c_data_interface_async(index_dir: str = "~/.ipfs_metadata") -> Dict[str, Any]:
        """Async version: Access the metadata index from another process via Arrow C Data Interface.
        
        Args:
            index_dir: Directory where the index is stored
            
        Returns:
            Dict with access information and the Arrow table
        """
        try:
            # Run the static method in a thread
            return await anyio.to_thread.run_sync(
                lambda: ArrowMetadataIndex.access_via_c_data_interface(index_dir)
            )
            
        except Exception as e:
            result = {
                "success": False,
                "operation": "access_via_c_data_interface_async",
                "timestamp": time.time(),
                "error": str(e)
            }
            logger.error(f"Error accessing C Data Interface asynchronously: {e}")
            return result


async def create_metadata_from_ipfs_file_async(
    ipfs_client, cid: str, include_content: bool = False
) -> Dict[str, Any]:
    """Async version: Create metadata record from an IPFS file.
    
    Args:
        ipfs_client: IPFS client instance
        cid: Content identifier
        include_content: Whether to include file content in metadata
        
    Returns:
        Metadata record for the file
    """
    # Create a wrapper function that calls the original
    from ipfs_kit_py.arrow_metadata_index import create_metadata_from_ipfs_file
    
    try:
        # Run the create_metadata_from_ipfs_file operation in a thread
        return await anyio.to_thread.run_sync(
            lambda: create_metadata_from_ipfs_file(ipfs_client, cid, include_content)
        )
        
    except Exception as e:
        logger.error(f"Error creating metadata asynchronously for CID {cid}: {e}")
        return {"error": str(e)}


async def find_ai_ml_resources_async(metadata_index, query_params=None):
    """Async version: Find AI/ML resources using the Arrow metadata index.
    
    Args:
        metadata_index: ArrowMetadataIndex instance
        query_params: Dictionary with query parameters
        
    Returns:
        Dictionary with query results and statistics
    """
    # Create a wrapper function that calls the original
    from ipfs_kit_py.arrow_metadata_index import find_ai_ml_resources
    
    try:
        # Run the find_ai_ml_resources operation in a thread
        return await anyio.to_thread.run_sync(
            lambda: find_ai_ml_resources(metadata_index, query_params)
        )
        
    except Exception as e:
        logger.error(f"Error finding AI/ML resources asynchronously: {e}")
        return {
            "success": False,
            "operation": "find_ai_ml_resources_async",
            "timestamp": time.time(),
            "error": str(e),
            "results": [],
            "count": 0
        }


async def find_similar_models_async(metadata_index, model_id, similarity_criteria=None, limit=5):
    """Async version: Find models similar to a reference model using the metadata index.
    
    Args:
        metadata_index: ArrowMetadataIndex instance
        model_id: CID or name of the reference model
        similarity_criteria: List of criteria to consider for similarity
        limit: Maximum number of similar models to return
        
    Returns:
        Dictionary with query results, including similarity scores
    """
    # Create a wrapper function that calls the original
    from ipfs_kit_py.arrow_metadata_index import find_similar_models
    
    try:
        # Run the find_similar_models operation in a thread
        return await anyio.to_thread.run_sync(
            lambda: find_similar_models(metadata_index, model_id, similarity_criteria, limit)
        )
        
    except Exception as e:
        logger.error(f"Error finding similar models asynchronously: {e}")
        return {
            "success": False,
            "operation": "find_similar_models_async",
            "timestamp": time.time(),
            "reference_model": model_id,
            "error": str(e),
            "similar_models": [],
            "count": 0
        }


async def find_datasets_for_task_async(
    metadata_index, task, domain=None, min_rows=None, format=None, limit=10
):
    """Async version: Find datasets suitable for a specific machine learning task.
    
    Args:
        metadata_index: ArrowMetadataIndex instance
        task: ML task type
        domain: Optional domain filter
        min_rows: Minimum number of rows/samples required
        format: Optional format filter
        limit: Maximum number of datasets to return
        
    Returns:
        Dictionary with query results
    """
    # Create a wrapper function that calls the original
    from ipfs_kit_py.arrow_metadata_index import find_datasets_for_task
    
    try:
        # Run the find_datasets_for_task operation in a thread
        return await anyio.to_thread.run_sync(
            lambda: find_datasets_for_task(metadata_index, task, domain, min_rows, format, limit)
        )
        
    except Exception as e:
        logger.error(f"Error finding datasets for task asynchronously: {e}")
        return {
            "success": False,
            "operation": "find_datasets_for_task_async",
            "timestamp": time.time(),
            "task": task,
            "error": str(e),
            "datasets": [],
            "count": 0
        }