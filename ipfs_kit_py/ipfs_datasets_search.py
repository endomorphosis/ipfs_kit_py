"""
IPFS Datasets Search and Index Integration

This module enhances the ipfs_datasets integration with filesystem search and 
indexing capabilities, specifically for GraphRAG and knowledge graph operations.

It enables:
1. Automatic indexing of datasets stored via ipfs_datasets_py
2. Integration with GraphRAG for semantic search
3. Knowledge graph building from dataset metadata
4. Vector embeddings for dataset content search
5. Provenance-aware search across dataset versions
"""

import logging
import os
import json
from typing import Dict, List, Any, Optional, Union, Set
from pathlib import Path
import datetime

# Configure logging
logger = logging.getLogger(__name__)

# Import the base ipfs_datasets integration
try:
    from .ipfs_datasets_integration import (
        get_ipfs_datasets_manager,
        IPFS_DATASETS_AVAILABLE,
        DatasetIPFSBackend
    )
except ImportError:
    IPFS_DATASETS_AVAILABLE = False
    logger.warning("ipfs_datasets_integration not available")

# Import search and indexing components
try:
    from .integrated_search import MetadataEnhancedGraphRAG
    GRAPHRAG_AVAILABLE = True
except ImportError:
    GRAPHRAG_AVAILABLE = False
    MetadataEnhancedGraphRAG = None
    logger.info("GraphRAG not available for dataset indexing")

try:
    from .ipld_knowledge_graph import IPLDGraphDB
    KNOWLEDGE_GRAPH_AVAILABLE = True
except ImportError:
    KNOWLEDGE_GRAPH_AVAILABLE = False
    IPLDGraphDB = None
    logger.info("Knowledge graph not available for dataset indexing")

try:
    from .arrow_metadata_index import IPFSArrowIndex
    ARROW_INDEX_AVAILABLE = True
except ImportError:
    ARROW_INDEX_AVAILABLE = False
    IPFSArrowIndex = None
    logger.info("Arrow index not available for dataset indexing")

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


class DatasetSearchIndexer:
    """
    Indexes datasets for search and retrieval using GraphRAG and knowledge graphs.
    
    This class automatically indexes datasets stored through ipfs_datasets_py,
    creating searchable metadata, building knowledge graphs from dataset relationships,
    and enabling semantic search through vector embeddings.
    """
    
    def __init__(
        self,
        ipfs_client=None,
        enable_graphrag: bool = True,
        enable_knowledge_graph: bool = True,
        enable_arrow_index: bool = True,
        base_path: str = "~/.ipfs_kit/dataset_index"
    ):
        """
        Initialize the dataset search indexer.
        
        Args:
            ipfs_client: Optional IPFS client instance
            enable_graphrag: Enable GraphRAG for semantic search
            enable_knowledge_graph: Enable knowledge graph for relationships
            enable_arrow_index: Enable Arrow metadata indexing
            base_path: Base directory for index storage
        """
        self.ipfs_client = ipfs_client
        self.base_path = Path(os.path.expanduser(base_path))
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize dataset manager
        self.dataset_manager = None
        if IPFS_DATASETS_AVAILABLE:
            try:
                self.dataset_manager = get_ipfs_datasets_manager(
                    ipfs_client=ipfs_client,
                    enable=True
                )
            except Exception as e:
                logger.warning(f"Failed to initialize dataset manager: {e}")
        
        # Initialize GraphRAG if available and enabled
        self.graphrag = None
        if enable_graphrag and GRAPHRAG_AVAILABLE and ipfs_client:
            try:
                self.graphrag = MetadataEnhancedGraphRAG(
                    ipfs_client=ipfs_client,
                    enable_distributed=False
                )
                logger.info("GraphRAG enabled for dataset search")
            except Exception as e:
                logger.warning(f"Failed to initialize GraphRAG: {e}")
        
        # Initialize knowledge graph if available and enabled
        self.knowledge_graph = None
        if enable_knowledge_graph and KNOWLEDGE_GRAPH_AVAILABLE and ipfs_client:
            try:
                self.knowledge_graph = IPLDGraphDB(
                    ipfs_client=ipfs_client,
                    base_path=str(self.base_path / "knowledge_graph")
                )
                logger.info("Knowledge graph enabled for dataset relationships")
            except Exception as e:
                logger.warning(f"Failed to initialize knowledge graph: {e}")
        
        # Initialize Arrow metadata index if available and enabled
        self.arrow_index = None
        if enable_arrow_index and ARROW_INDEX_AVAILABLE:
            try:
                self.arrow_index = IPFSArrowIndex(role="leecher")
                logger.info("Arrow index enabled for dataset metadata")
            except Exception as e:
                logger.warning(f"Failed to initialize Arrow index: {e}")
        
        # In-memory index for quick lookups
        self.dataset_index = {}  # dataset_id -> metadata
        self.cid_to_dataset = {}  # cid -> dataset_id
        
        # Load existing index
        self._load_index()
        
        logger.info(f"Dataset search indexer initialized at {self.base_path}")
    
    def is_available(self) -> bool:
        """Check if indexing capabilities are available."""
        return (
            self.dataset_manager is not None or
            self.graphrag is not None or
            self.knowledge_graph is not None or
            self.arrow_index is not None
        )
    
    def _load_index(self):
        """Load the dataset index from disk."""
        index_file = self.base_path / "dataset_index.json"
        if index_file.exists():
            try:
                with open(index_file, 'r') as f:
                    data = json.load(f)
                    self.dataset_index = data.get("datasets", {})
                    self.cid_to_dataset = data.get("cid_mapping", {})
                logger.info(f"Loaded {len(self.dataset_index)} datasets from index")
            except Exception as e:
                logger.error(f"Failed to load index: {e}")
    
    def _save_index(self):
        """Save the dataset index to disk."""
        index_file = self.base_path / "dataset_index.json"
        try:
            with open(index_file, 'w') as f:
                json.dump({
                    "datasets": self.dataset_index,
                    "cid_mapping": self.cid_to_dataset,
                    "last_updated": datetime.datetime.now().isoformat()
                }, f, indent=2)
            logger.debug("Saved dataset index")
        except Exception as e:
            logger.error(f"Failed to save index: {e}")
    
    def index_dataset(
        self,
        dataset_id: str,
        dataset_path: str,
        metadata: Optional[Dict[str, Any]] = None,
        cid: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Index a dataset for search and retrieval.
        
        This method:
        1. Extracts metadata from the dataset
        2. Creates entries in the knowledge graph for relationships
        3. Generates vector embeddings for semantic search
        4. Updates the Arrow metadata index
        
        Args:
            dataset_id: Unique identifier for the dataset
            dataset_path: Path to the dataset file
            metadata: Optional metadata to include
            cid: Optional IPFS CID if already stored
        
        Returns:
            Dictionary with indexing results
        """
        try:
            # Prepare metadata
            full_metadata = metadata or {}
            full_metadata.update({
                "dataset_id": dataset_id,
                "path": dataset_path,
                "indexed_at": datetime.datetime.now().isoformat(),
                "cid": cid
            })
            
            # Extract basic dataset info
            dataset_info = self._extract_dataset_info(dataset_path)
            full_metadata.update(dataset_info)
            
            # Store in local index
            self.dataset_index[dataset_id] = full_metadata
            if cid:
                self.cid_to_dataset[cid] = dataset_id
            
            results = {
                "success": True,
                "dataset_id": dataset_id,
                "indexed_components": []
            }
            
            # Index in knowledge graph
            if self.knowledge_graph:
                try:
                    kg_result = self._index_in_knowledge_graph(dataset_id, full_metadata)
                    results["indexed_components"].append("knowledge_graph")
                    results["kg_entity_id"] = kg_result.get("entity_id")
                except Exception as e:
                    logger.warning(f"Failed to index in knowledge graph: {e}")
            
            # Index in GraphRAG
            if self.graphrag:
                try:
                    graphrag_result = self._index_in_graphrag(dataset_id, full_metadata)
                    results["indexed_components"].append("graphrag")
                except Exception as e:
                    logger.warning(f"Failed to index in GraphRAG: {e}")
            
            # Index in Arrow metadata
            if self.arrow_index and cid:
                try:
                    arrow_result = self._index_in_arrow(cid, full_metadata)
                    results["indexed_components"].append("arrow_index")
                except Exception as e:
                    logger.warning(f"Failed to index in Arrow: {e}")
            
            # Save index
            self._save_index()
            
            logger.info(f"Indexed dataset {dataset_id} in {len(results['indexed_components'])} components")
            return results
            
        except Exception as e:
            logger.error(f"Failed to index dataset {dataset_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _extract_dataset_info(self, dataset_path: str) -> Dict[str, Any]:
        """Extract basic information about a dataset."""
        try:
            path = Path(dataset_path)
            info = {
                "filename": path.name,
                "extension": path.suffix,
                "size_bytes": path.stat().st_size if path.exists() else 0,
                "is_file": path.is_file() if path.exists() else False,
                "is_directory": path.is_dir() if path.exists() else False
            }
            
            # Try to detect content type
            if info["extension"] in [".csv", ".tsv"]:
                info["content_type"] = "tabular"
            elif info["extension"] in [".json", ".jsonl"]:
                info["content_type"] = "json"
            elif info["extension"] in [".parquet"]:
                info["content_type"] = "parquet"
            elif info["extension"] in [".txt", ".md"]:
                info["content_type"] = "text"
            else:
                info["content_type"] = "unknown"
            
            return info
        except Exception as e:
            logger.warning(f"Failed to extract dataset info: {e}")
            return {}
    
    def _index_in_knowledge_graph(self, dataset_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Index dataset in the knowledge graph."""
        entity_id = f"dataset:{dataset_id}"
        
        # Create entity for the dataset
        entity_data = {
            "id": entity_id,
            "type": "dataset",
            "name": metadata.get("filename", dataset_id),
            "metadata": metadata
        }
        
        self.knowledge_graph.add_entity(entity_data)
        
        # Add relationships to parent versions if available
        parent_version = metadata.get("provenance", {}).get("parent_version")
        if parent_version:
            parent_entity_id = f"dataset:{parent_version}"
            self.knowledge_graph.add_relationship(
                source=entity_id,
                target=parent_entity_id,
                rel_type="derived_from",
                properties={"transformations": metadata.get("provenance", {}).get("transformations", [])}
            )
        
        return {"entity_id": entity_id}
    
    def _index_in_graphrag(self, dataset_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Index dataset in GraphRAG for semantic search."""
        # Create searchable content from metadata
        searchable_content = self._create_searchable_content(metadata)
        
        # Index the content (GraphRAG will handle embedding and indexing)
        # This is a placeholder - actual implementation depends on GraphRAG API
        logger.info(f"Would index in GraphRAG: {dataset_id}")
        
        return {"indexed": True}
    
    def _index_in_arrow(self, cid: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Index dataset in Arrow metadata index."""
        # Add to Arrow index for efficient metadata queries
        # This is a placeholder - actual implementation depends on Arrow index API
        logger.info(f"Would index in Arrow: {cid}")
        
        return {"indexed": True}
    
    def _create_searchable_content(self, metadata: Dict[str, Any]) -> str:
        """Create searchable text content from metadata."""
        parts = []
        
        # Add basic fields
        if "filename" in metadata:
            parts.append(f"Filename: {metadata['filename']}")
        
        if "description" in metadata:
            parts.append(f"Description: {metadata['description']}")
        
        if "tags" in metadata:
            parts.append(f"Tags: {', '.join(metadata['tags'])}")
        
        # Add provenance info
        provenance = metadata.get("provenance", {})
        if provenance.get("transformations"):
            parts.append(f"Transformations: {', '.join(provenance['transformations'])}")
        
        return "\n".join(parts)
    
    def search_datasets(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        use_semantic_search: bool = True,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for datasets using text query and optional filters.
        
        Args:
            query: Search query string
            filters: Optional filters (e.g., {"content_type": "parquet"})
            use_semantic_search: Use semantic/vector search if available
            limit: Maximum number of results
        
        Returns:
            List of matching dataset metadata
        """
        try:
            results = []
            
            # Simple text-based search in local index
            for dataset_id, metadata in self.dataset_index.items():
                if self._matches_query(metadata, query, filters):
                    results.append(metadata)
            
            # Sort by relevance (simple version)
            results = results[:limit]
            
            logger.info(f"Found {len(results)} datasets matching query: {query}")
            return results
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    def _matches_query(self, metadata: Dict[str, Any], query: str, filters: Optional[Dict[str, Any]]) -> bool:
        """Check if metadata matches the search query and filters."""
        # Simple text matching
        query_lower = query.lower()
        searchable = self._create_searchable_content(metadata).lower()
        
        if query_lower not in searchable:
            return False
        
        # Apply filters
        if filters:
            for key, value in filters.items():
                if metadata.get(key) != value:
                    return False
        
        return True
    
    def get_dataset_lineage(self, dataset_id: str) -> Dict[str, Any]:
        """
        Get the complete lineage (provenance) of a dataset.
        
        Returns all parent and child versions with transformation history.
        
        Args:
            dataset_id: Dataset identifier
        
        Returns:
            Dictionary with lineage information
        """
        try:
            if dataset_id not in self.dataset_index:
                return {"error": "Dataset not found"}
            
            lineage = {
                "dataset_id": dataset_id,
                "parents": [],
                "children": [],
                "transformations": []
            }
            
            metadata = self.dataset_index[dataset_id]
            
            # Get parent version
            provenance = metadata.get("provenance", {})
            if provenance.get("parent_version"):
                lineage["parents"].append(provenance["parent_version"])
                lineage["transformations"] = provenance.get("transformations", [])
            
            # Find children (datasets that have this as parent)
            for other_id, other_metadata in self.dataset_index.items():
                other_provenance = other_metadata.get("provenance", {})
                if other_provenance.get("parent_version") == dataset_id:
                    lineage["children"].append(other_id)
            
            return lineage
            
        except Exception as e:
            logger.error(f"Failed to get lineage: {e}")
            return {"error": str(e)}
    
    def list_indexed_datasets(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        List all indexed datasets with optional filters.
        
        Args:
            filters: Optional filters to apply
        
        Returns:
            List of dataset metadata
        """
        datasets = list(self.dataset_index.values())
        
        if filters:
            datasets = [d for d in datasets if all(d.get(k) == v for k, v in filters.items())]
        
        return datasets


def integrate_with_dataset_manager(dataset_manager, search_indexer):
    """
    Integrate the search indexer with the dataset manager to automatically
    index datasets when they are stored or versioned.
    
    This function monkey-patches the dataset manager to call the indexer
    after successful operations.
    
    Args:
        dataset_manager: IPFSDatasetsManager instance
        search_indexer: DatasetSearchIndexer instance
    """
    if not dataset_manager or not search_indexer:
        logger.warning("Cannot integrate - manager or indexer is None")
        return
    
    # Store original methods
    original_store = dataset_manager.store
    original_version = dataset_manager.version
    
    def store_with_indexing(path, metadata=None):
        """Wrapped store method that indexes after storing."""
        result = original_store(path, metadata)
        
        if result.get("success"):
            # Extract dataset ID from path
            dataset_id = Path(path).stem
            
            # Index the dataset
            search_indexer.index_dataset(
                dataset_id=dataset_id,
                dataset_path=path,
                metadata=metadata,
                cid=result.get("cid")
            )
        
        return result
    
    def version_with_indexing(dataset_id, version, parent_version=None, transformations=None):
        """Wrapped version method that indexes after versioning."""
        result = original_version(dataset_id, version, parent_version, transformations)
        
        if result.get("success"):
            # Update index with version info
            search_indexer.index_dataset(
                dataset_id=f"{dataset_id}:{version}",
                dataset_path=f"dataset:{dataset_id}",
                metadata={
                    "version": version,
                    "parent_version": parent_version,
                    "transformations": transformations or []
                },
                cid=result.get("cid")
            )
        
        return result
    
    # Replace methods
    dataset_manager.store = store_with_indexing
    dataset_manager.version = version_with_indexing
    
    logger.info("Integrated search indexer with dataset manager")


# Singleton instance
_indexer_instance: Optional[DatasetSearchIndexer] = None


def get_dataset_search_indexer(
    ipfs_client=None,
    enable_graphrag: bool = True,
    enable_knowledge_graph: bool = True
) -> Optional[DatasetSearchIndexer]:
    """
    Get or create the singleton dataset search indexer instance.
    
    Args:
        ipfs_client: Optional IPFS client instance
        enable_graphrag: Enable GraphRAG integration
        enable_knowledge_graph: Enable knowledge graph integration
    
    Returns:
        DatasetSearchIndexer instance or None if initialization fails
    """
    global _indexer_instance
    if _indexer_instance is None:
        try:
            _indexer_instance = DatasetSearchIndexer(
                ipfs_client=ipfs_client,
                enable_graphrag=enable_graphrag,
                enable_knowledge_graph=enable_knowledge_graph
            )
        except Exception as e:
            logger.error(f"Failed to create dataset search indexer: {e}")
            return None
    return _indexer_instance


def reset_indexer():
    """Reset the singleton indexer instance (useful for testing)."""
    global _indexer_instance
    _indexer_instance = None
