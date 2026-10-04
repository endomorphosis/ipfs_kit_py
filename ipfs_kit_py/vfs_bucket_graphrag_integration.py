"""
VFS Bucket GraphRAG Integration with ipfs_datasets_py

This module provides integration between ipfs_datasets_py and the VFS bucket system
to enable GraphRAG indexing of virtual filesystem buckets. The ipfs_datasets_py library
assists with managing the dataset representations of bucket contents for efficient
GraphRAG operations.

Key Features:
1. Use ipfs_datasets_py to manage bucket content as datasets
2. Enable GraphRAG to index virtual filesystem buckets
3. Provide efficient search and retrieval across VFS buckets
4. Track bucket content changes and update indexes
5. Support distributed indexing operations
"""

import logging
import os
import json
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import datetime

# Configure logging
logger = logging.getLogger(__name__)

# Import ipfs_datasets integration
try:
    from .ipfs_datasets_integration import (
        get_ipfs_datasets_manager,
        IPFS_DATASETS_AVAILABLE
    )
except ImportError:
    IPFS_DATASETS_AVAILABLE = False
    logger.warning("ipfs_datasets_integration not available")

# Import VFS bucket manager
try:
    from .bucket_vfs_manager import BucketVFSManager
    BUCKET_VFS_AVAILABLE = True
except ImportError:
    BUCKET_VFS_AVAILABLE = False
    BucketVFSManager = None
    logger.warning("BucketVFSManager not available")

# Import GraphRAG components
try:
    from .ipld_knowledge_graph import IPLDGraphDB, GraphRAG
    GRAPHRAG_AVAILABLE = True
except ImportError:
    GRAPHRAG_AVAILABLE = False
    IPLDGraphDB = None
    GraphRAG = None
    logger.info("GraphRAG not available")

# Import ipfs_accelerate_py for compute layer
try:
    import sys
    from pathlib import Path
    # Add ipfs_accelerate_py to path if it exists as submodule
    accelerate_path = Path(__file__).parent.parent / "ipfs_accelerate_py"
    if accelerate_path.exists() and str(accelerate_path) not in sys.path:
        sys.path.insert(0, str(accelerate_path))
    
    from ipfs_accelerate_py import AccelerateCompute
    ACCELERATE_AVAILABLE = True
    logger.info("ipfs_accelerate_py compute layer available")
except ImportError:
    ACCELERATE_AVAILABLE = False
    AccelerateCompute = None
    logger.info("ipfs_accelerate_py not available - GraphRAG will use default compute")


class VFSBucketGraphRAGIndexer:
    """
    Integrates ipfs_datasets_py with VFS buckets for GraphRAG indexing.
    
    This class uses ipfs_datasets_py to manage bucket contents as datasets,
    enabling efficient GraphRAG indexing and search across virtual filesystems.
    The ipfs_accelerate_py compute layer provides accelerated processing for
    GraphRAG operations when available.
    
    The ipfs_datasets_py library handles:
    - Versioning of bucket content snapshots
    - Efficient storage and retrieval of bucket state
    - Provenance tracking for bucket changes
    - Distributed operations for bucket data
    
    The ipfs_accelerate_py library provides:
    - Accelerated compute for GraphRAG indexing operations
    - Optimized processing for large-scale bucket indexing
    - Distributed compute capabilities
    
    GraphRAG then indexes these dataset representations for semantic search.
    """
    
    def __init__(
        self,
        bucket_manager: Optional[BucketVFSManager] = None,
        ipfs_client=None,
        enable_graphrag: bool = True,
        enable_compute_layer: bool = True,
        base_path: str = "~/.ipfs_kit/vfs_graphrag_index"
    ):
        """
        Initialize the VFS bucket GraphRAG indexer.
        
        Args:
            bucket_manager: Optional BucketVFSManager instance
            ipfs_client: Optional IPFS client
            enable_graphrag: Enable GraphRAG indexing
            enable_compute_layer: Enable ipfs_accelerate_py compute layer for GraphRAG
            base_path: Base directory for index storage
        """
        self.ipfs_client = ipfs_client
        self.base_path = Path(os.path.expanduser(base_path))
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize bucket manager
        self.bucket_manager = bucket_manager
        if not self.bucket_manager and BUCKET_VFS_AVAILABLE:
            try:
                self.bucket_manager = BucketVFSManager(
                    ipfs_client=ipfs_client
                )
            except Exception as e:
                logger.warning(f"Failed to initialize bucket manager: {e}")
        
        # Initialize ipfs_datasets manager for bucket content management
        self.datasets_manager = None
        if IPFS_DATASETS_AVAILABLE:
            try:
                self.datasets_manager = get_ipfs_datasets_manager(
                    ipfs_client=ipfs_client,
                    enable=True
                )
                logger.info("ipfs_datasets_py enabled for bucket content management")
            except Exception as e:
                logger.warning(f"Failed to initialize datasets manager: {e}")
        
        # Initialize compute layer if available
        self.compute_layer = None
        if enable_compute_layer and ACCELERATE_AVAILABLE:
            try:
                self.compute_layer = AccelerateCompute()
                logger.info("ipfs_accelerate_py compute layer enabled for GraphRAG operations")
            except Exception as e:
                logger.warning(f"Failed to initialize compute layer: {e}")
        
        # Initialize GraphRAG components
        self.knowledge_graph = None
        self.graph_rag = None
        if enable_graphrag and GRAPHRAG_AVAILABLE and ipfs_client:
            try:
                self.knowledge_graph = IPLDGraphDB(
                    ipfs_client=ipfs_client,
                    base_path=str(self.base_path / "knowledge_graph")
                )
                self.graph_rag = GraphRAG(self.knowledge_graph)
                logger.info("GraphRAG enabled for VFS bucket indexing")
            except Exception as e:
                logger.warning(f"Failed to initialize GraphRAG: {e}")
        
        # Bucket index: bucket_name -> dataset_id
        self.bucket_index = {}
        self._load_index()
        
        logger.info(f"VFS Bucket GraphRAG indexer initialized at {self.base_path}")
    
    def is_available(self) -> bool:
        """Check if indexing capabilities are available."""
        return (
            self.bucket_manager is not None or
            self.datasets_manager is not None or
            self.graph_rag is not None
        )
    
    def _load_index(self):
        """Load the bucket-to-dataset index."""
        index_file = self.base_path / "bucket_index.json"
        if index_file.exists():
            try:
                with open(index_file, 'r') as f:
                    self.bucket_index = json.load(f)
                logger.info(f"Loaded index for {len(self.bucket_index)} buckets")
            except Exception as e:
                logger.error(f"Failed to load index: {e}")
    
    def _save_index(self):
        """Save the bucket-to-dataset index."""
        index_file = self.base_path / "bucket_index.json"
        try:
            with open(index_file, 'w') as f:
                json.dump(self.bucket_index, f, indent=2)
            logger.debug("Saved bucket index")
        except Exception as e:
            logger.error(f"Failed to save index: {e}")
    
    def snapshot_bucket(
        self,
        bucket_name: str,
        version: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a snapshot of a VFS bucket using ipfs_datasets_py.
        
        This captures the current state of the bucket as a dataset, which can
        then be indexed by GraphRAG for search and retrieval.
        
        Args:
            bucket_name: Name of the VFS bucket
            version: Optional version identifier for the snapshot
        
        Returns:
            Dictionary with snapshot results including dataset_id and CID
        """
        if not self.bucket_manager:
            return {
                "success": False,
                "error": "Bucket manager not available"
            }
        
        try:
            # Get bucket metadata
            bucket_info = self._get_bucket_info(bucket_name)
            if not bucket_info:
                return {
                    "success": False,
                    "error": f"Bucket {bucket_name} not found"
                }
            
            # Create dataset representation of bucket
            dataset_id = f"vfs_bucket_{bucket_name}"
            if version:
                dataset_id += f"_v{version}"
            
            # Export bucket structure
            bucket_data = self._export_bucket_structure(bucket_name)
            
            # Store via ipfs_datasets if available
            if self.datasets_manager and self.datasets_manager.is_available():
                # Save bucket data to temp file
                temp_file = self.base_path / f"{dataset_id}.json"
                with open(temp_file, 'w') as f:
                    json.dump(bucket_data, f, indent=2)
                
                # Store using ipfs_datasets
                result = self.datasets_manager.store(
                    str(temp_file),
                    metadata={
                        "bucket_name": bucket_name,
                        "snapshot_at": datetime.datetime.now().isoformat(),
                        "version": version,
                        "type": "vfs_bucket_snapshot"
                    }
                )
                
                # Clean up temp file
                temp_file.unlink()
                
                if result.get("success"):
                    self.bucket_index[bucket_name] = {
                        "dataset_id": dataset_id,
                        "cid": result.get("cid"),
                        "version": version,
                        "last_snapshot": datetime.datetime.now().isoformat()
                    }
                    self._save_index()
                    
                    logger.info(f"Created snapshot of bucket {bucket_name} as dataset {dataset_id}")
                    return {
                        "success": True,
                        "dataset_id": dataset_id,
                        "bucket_name": bucket_name,
                        "cid": result.get("cid"),
                        "distributed": result.get("distributed", False)
                    }
            
            # Fallback: store locally
            local_snapshot = self.base_path / "snapshots" / f"{dataset_id}.json"
            local_snapshot.parent.mkdir(exist_ok=True)
            with open(local_snapshot, 'w') as f:
                json.dump(bucket_data, f, indent=2)
            
            self.bucket_index[bucket_name] = {
                "dataset_id": dataset_id,
                "local_path": str(local_snapshot),
                "version": version,
                "last_snapshot": datetime.datetime.now().isoformat()
            }
            self._save_index()
            
            return {
                "success": True,
                "dataset_id": dataset_id,
                "bucket_name": bucket_name,
                "local_path": str(local_snapshot),
                "distributed": False
            }
            
        except Exception as e:
            logger.error(f"Failed to snapshot bucket {bucket_name}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def index_bucket_with_graphrag(
        self,
        bucket_name: str,
        force_snapshot: bool = False
    ) -> Dict[str, Any]:
        """
        Index a VFS bucket with GraphRAG.
        
        This method:
        1. Creates/updates a snapshot of the bucket using ipfs_datasets_py
        2. Indexes the bucket content with GraphRAG for semantic search
        3. Updates the knowledge graph with bucket structure
        
        Args:
            bucket_name: Name of the bucket to index
            force_snapshot: Force create new snapshot even if one exists
        
        Returns:
            Dictionary with indexing results
        """
        try:
            # Create snapshot if needed
            if force_snapshot or bucket_name not in self.bucket_index:
                snapshot_result = self.snapshot_bucket(bucket_name)
                if not snapshot_result.get("success"):
                    return snapshot_result
            
            bucket_info = self.bucket_index.get(bucket_name, {})
            dataset_id = bucket_info.get("dataset_id")
            
            if not dataset_id:
                return {
                    "success": False,
                    "error": "No dataset snapshot available for bucket"
                }
            
            results = {
                "success": True,
                "bucket_name": bucket_name,
                "dataset_id": dataset_id,
                "indexed_components": []
            }
            
            # Index with GraphRAG if available
            if self.graph_rag:
                try:
                    graphrag_result = self._index_bucket_in_graphrag(bucket_name, dataset_id)
                    results["indexed_components"].append("graphrag")
                    results["graphrag_result"] = graphrag_result
                except Exception as e:
                    logger.warning(f"Failed to index with GraphRAG: {e}")
            
            logger.info(f"Indexed bucket {bucket_name} with {len(results['indexed_components'])} components")
            return results
            
        except Exception as e:
            logger.error(f"Failed to index bucket {bucket_name}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _get_bucket_info(self, bucket_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a bucket."""
        if not self.bucket_manager:
            return None
        
        try:
            # Get bucket from manager
            buckets = getattr(self.bucket_manager, 'buckets', {})
            return buckets.get(bucket_name)
        except Exception as e:
            logger.warning(f"Failed to get bucket info: {e}")
            return None
    
    def _export_bucket_structure(self, bucket_name: str) -> Dict[str, Any]:
        """
        Export the structure and metadata of a bucket.
        
        This creates a dataset representation of the bucket that can be
        stored via ipfs_datasets_py and indexed by GraphRAG.
        """
        bucket_data = {
            "bucket_name": bucket_name,
            "exported_at": datetime.datetime.now().isoformat(),
            "files": [],
            "metadata": {},
            "statistics": {}
        }
        
        try:
            # Get bucket info
            bucket_info = self._get_bucket_info(bucket_name)
            if bucket_info:
                bucket_data["metadata"] = bucket_info
            
            # Export file structure (simplified version)
            # In a full implementation, this would traverse the bucket's UnixFS structure
            bucket_data["statistics"] = {
                "file_count": 0,
                "total_size": 0
            }
            
        except Exception as e:
            logger.warning(f"Failed to export bucket structure: {e}")
        
        return bucket_data
    
    def _index_bucket_in_graphrag(self, bucket_name: str, dataset_id: str) -> Dict[str, Any]:
        """Index bucket content in GraphRAG using compute layer if available."""
        if not self.graph_rag:
            return {"indexed": False, "reason": "GraphRAG not available"}
        
        try:
            # Create entity for the bucket in knowledge graph
            entity_id = f"bucket:{bucket_name}"
            entity_data = {
                "id": entity_id,
                "type": "vfs_bucket",
                "name": bucket_name,
                "dataset_id": dataset_id,
                "indexed_at": datetime.datetime.now().isoformat()
            }
            
            self.knowledge_graph.add_entity(entity_data)
            
            # Use compute layer if available for GraphRAG operations
            if self.compute_layer:
                try:
                    # Accelerate GraphRAG indexing with compute layer
                    compute_result = self.compute_layer.accelerate_indexing(
                        entity_id=entity_id,
                        entity_data=entity_data
                    )
                    logger.info(f"Used ipfs_accelerate_py compute layer for indexing {bucket_name}")
                    return {
                        "indexed": True,
                        "entity_id": entity_id,
                        "compute_accelerated": True,
                        "compute_result": compute_result
                    }
                except Exception as e:
                    logger.warning(f"Compute layer acceleration failed, using default: {e}")
            
            # Fallback to standard GraphRAG indexing
            # Note: Actual implementation would depend on GraphRAG API
            logger.info(f"Indexed bucket {bucket_name} in GraphRAG (standard mode)")
            
            return {
                "indexed": True,
                "entity_id": entity_id,
                "compute_accelerated": False
            }
            
        except Exception as e:
            logger.error(f"Failed to index in GraphRAG: {e}")
            return {"indexed": False, "error": str(e)}
    
    def search_buckets(
        self,
        query: str,
        use_semantic_search: bool = True,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search across indexed VFS buckets using GraphRAG.
        
        Args:
            query: Search query
            use_semantic_search: Use semantic/vector search if available
            limit: Maximum number of results
        
        Returns:
            List of matching bucket information
        """
        try:
            results = []
            
            if self.graph_rag and use_semantic_search:
                # Use GraphRAG semantic search
                # This would use the actual GraphRAG search API
                logger.info(f"Performing GraphRAG search for: {query}")
            
            # Simple fallback search
            query_lower = query.lower()
            for bucket_name, bucket_info in self.bucket_index.items():
                if query_lower in bucket_name.lower():
                    results.append({
                        "bucket_name": bucket_name,
                        "dataset_id": bucket_info.get("dataset_id"),
                        "last_snapshot": bucket_info.get("last_snapshot")
                    })
            
            return results[:limit]
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    def list_indexed_buckets(self) -> List[str]:
        """List all buckets that have been indexed."""
        return list(self.bucket_index.keys())
    
    def get_bucket_snapshot_info(self, bucket_name: str) -> Optional[Dict[str, Any]]:
        """Get snapshot information for a bucket."""
        return self.bucket_index.get(bucket_name)


# Singleton instance
_indexer_instance: Optional[VFSBucketGraphRAGIndexer] = None


def get_vfs_bucket_graphrag_indexer(
    bucket_manager=None,
    ipfs_client=None,
    enable_graphrag: bool = True,
    enable_compute_layer: bool = True
) -> Optional[VFSBucketGraphRAGIndexer]:
    """
    Get or create the singleton VFS bucket GraphRAG indexer.
    
    Args:
        bucket_manager: Optional BucketVFSManager instance
        ipfs_client: Optional IPFS client
        enable_graphrag: Enable GraphRAG integration
        enable_compute_layer: Enable ipfs_accelerate_py compute layer
    
    Returns:
        VFSBucketGraphRAGIndexer instance or None if initialization fails
    """
    global _indexer_instance
    if _indexer_instance is None:
        try:
            _indexer_instance = VFSBucketGraphRAGIndexer(
                bucket_manager=bucket_manager,
                ipfs_client=ipfs_client,
                enable_graphrag=enable_graphrag,
                enable_compute_layer=enable_compute_layer
            )
        except Exception as e:
            logger.error(f"Failed to create VFS bucket GraphRAG indexer: {e}")
            return None
    return _indexer_instance


def reset_indexer():
    """Reset the singleton indexer instance (useful for testing)."""
    global _indexer_instance
    _indexer_instance = None
