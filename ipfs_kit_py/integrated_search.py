"""Integrated search combining Arrow metadata index with GraphRAG capabilities.

This module provides the integration between the Arrow metadata index and the
GraphRAG system, offering a unified search interface that combines the strengths
of both components. It also provides integration with AI/ML components like
Langchain and LlamaIndex.
"""

import logging
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np

# Core components that may be used
try:
    from .ipld_knowledge_graph import IPLDGraphDB
except ImportError:
    IPLDGraphDB = None

try:
    from .arrow_metadata_index import IPFSArrowIndex
except ImportError:
    IPFSArrowIndex = None

# AI/ML integration components
try:
    from .ai_ml_integration import (
        CustomEmbeddingModel,
        DatasetManager,
        LangchainIntegration,
        LlamaIndexIntegration,
        ModelRegistry,
    )

    AI_ML_AVAILABLE = True
except ImportError:
    AI_ML_AVAILABLE = False
    ModelRegistry = None
    DatasetManager = None
    LangchainIntegration = None
    LlamaIndexIntegration = None
    CustomEmbeddingModel = None

# Set up logging
logger = logging.getLogger(__name__)


class MetadataEnhancedGraphRAG:
    """GraphRAG system enhanced with Arrow metadata index capabilities.

    This class integrates the Arrow metadata index with the IPLD Knowledge Graph
    to provide a unified search experience that combines the strengths of both
    systems: efficient metadata filtering and vector similarity search.
    """

    def __init__(
        self,
        ipfs_client,
        graph_db=None,
        metadata_index=None,
        query_optimizer=None,
        cluster_manager=None,
        enable_distributed=True,
    ):
        """Initialize the enhanced GraphRAG system.

        Args:
            ipfs_client: The IPFS client instance
            graph_db: Optional existing IPLD Knowledge Graph instance
            metadata_index: Optional existing Arrow metadata index instance
            query_optimizer: Optional existing DistributedQueryOptimizer instance
            cluster_manager: Optional cluster manager for distributed queries
            enable_distributed: Whether to enable distributed query execution
        """
        self.ipfs = ipfs_client

        # Check for required components
        if IPLDGraphDB is None:
            raise ImportError("IPLDGraphDB not available. Install the required dependencies.")

        if IPFSArrowIndex is None:
            raise ImportError("IPFSArrowIndex not available. Install the required dependencies.")

        # Initialize or use provided components
        self.graph_db = graph_db or IPLDGraphDB(ipfs_client)

        if metadata_index is not None:
            self.metadata_index = metadata_index
        elif hasattr(ipfs_client, "metadata_index") and ipfs_client.metadata_index is not None:
            self.metadata_index = ipfs_client.metadata_index
        else:
            # Create a new metadata index if none exists
            self.metadata_index = IPFSArrowIndex(role=getattr(ipfs_client, "role", "leecher"))

        # Initialize distributed query optimization if enabled
        self.enable_distributed = enable_distributed
        self.cluster_manager = cluster_manager

        if query_optimizer is not None:
            self.query_optimizer = query_optimizer
        elif enable_distributed and 'DistributedQueryOptimizer' in globals():
            self.query_optimizer = DistributedQueryOptimizer(
                ipfs_client=ipfs_client, cluster_manager=cluster_manager
            )
        else:
            self.query_optimizer = None

    def hybrid_search(
        self,
        query_text=None,
        query_vector=None,
        metadata_filters=None,
        entity_types=None,
        hop_count=1,
        top_k=10,
    ):
        """Perform a hybrid search combining metadata filtering and vector similarity.

        This method supports multiple search strategies:
        1. Metadata-first: Filter content by metadata, then perform vector search
        2. Vector-first: Perform vector search, then filter by metadata
        3. Pure hybrid: Execute both searches and merge results

        Args:
            query_text: Text query (will be converted to vector if query_vector not provided)
            query_vector: Vector representation for similarity search
            metadata_filters: List of filters for Arrow index in format [(field, op, value),...]
            entity_types: List of entity types to include in results
            hop_count: Number of graph traversal hops for related entities
            top_k: Maximum number of results to return

        Returns:
            List of search results with combined scores
        """
        # Input validation
        if not (query_text or query_vector or metadata_filters):
            raise ValueError(
                "At least one of query_text, query_vector, or metadata_filters must be provided"
            )

        # Strategy determination based on inputs
        if metadata_filters and not (query_text or query_vector):
            # Metadata-only search
            return self._metadata_only_search(metadata_filters, top_k)

        elif (query_text or query_vector) and not metadata_filters:
            # Vector-only search
            return self._vector_only_search(
                query_text, query_vector, entity_types, hop_count, top_k
            )

        else:
            # Hybrid search combining both approaches
            return self._combined_search(
                query_text, query_vector, metadata_filters, entity_types, hop_count, top_k
            )

    def _metadata_only_search(self, metadata_filters, top_k):
        """Execute a search using only metadata filters."""
        # Query the Arrow index with filters
        try:
            filtered_table = self.metadata_index.query(metadata_filters)

            # Convert to result format
            results = []
            for row in filtered_table.to_pylist()[:top_k]:
                # Check if this entity exists in the knowledge graph
                entity_id = row.get("cid")
                entity = self.graph_db.get_entity(entity_id)

                result = {
                    "id": entity_id,
                    "score": 1.0,  # No relevance score for metadata-only search
                    "metadata": row,
                    "properties": entity["properties"] if entity else {},
                    "source": "metadata",
                }
                results.append(result)

            return results
        except Exception as e:
            logger.error(f"Metadata search error: {str(e)}")
            return []

    def _vector_only_search(self, query_text, query_vector, entity_types, hop_count, top_k):
        """Execute a search using only vector similarity."""
        try:
            # Convert text to vector if needed
            if query_text and not query_vector:
                query_vector = self.graph_db.generate_embedding(query_text)

            # Perform graph vector search
            results = self.graph_db.graph_vector_search(
                query_vector=query_vector, hop_count=hop_count, top_k=top_k
            )

            # Filter by entity type if specified
            if entity_types:
                filtered_results = []
                for result in results:
                    entity = self.graph_db.get_entity(result["entity_id"])
                    if entity and entity.get("properties", {}).get("type") in entity_types:
                        filtered_results.append(result)
                results = filtered_results[:top_k]

            # Enhance with metadata if available
            enhanced_results = []
            for result in results:
                entity_id = result["entity_id"]
                metadata = self._get_metadata_for_entity(entity_id)

                enhanced_result = {
                    "id": entity_id,
                    "score": result["score"],
                    "metadata": metadata if metadata else {},
                    "properties": self.graph_db.get_entity(entity_id)["properties"],
                    "path": result.get("path", []),
                    "distance": result.get("distance", 0),
                    "source": "vector",
                }
                enhanced_results.append(enhanced_result)

            return enhanced_results
        except Exception as e:
            logger.error(f"Vector search error: {str(e)}")
            return []

    def _combined_search(
        self, query_text, query_vector, metadata_filters, entity_types, hop_count, top_k
    ):
        """Execute a hybrid search combining metadata filtering and vector similarity."""
        try:
            # Strategy: Filter by metadata first, then rank by vector similarity

            # 1. Get candidate set from metadata filtering
            filtered_table = self.metadata_index.query(metadata_filters)
            candidate_cids = [row["cid"] for row in filtered_table.to_pylist()]

            # Short circuit if no candidates match metadata filters
            if not candidate_cids:
                return []

            # 2. Convert text to vector if needed
            if query_text and not query_vector:
                query_vector = self.graph_db.generate_embedding(query_text)

            # 3. For each candidate, compute vector similarity and add to results
            results = []
            for cid in candidate_cids:
                # Check if entity exists in graph
                entity = self.graph_db.get_entity(cid)
                if not entity:
                    continue

                # Check entity type filter
                if entity_types and entity.get("properties", {}).get("type") not in entity_types:
                    continue

                # Get vector and compute similarity
                vector = entity.get("vector")
                if vector is not None:
                    # Use the graph DB's similarity function if available
                    if hasattr(self.graph_db, "compute_similarity"):
                        similarity = self.graph_db.compute_similarity(query_vector, vector)
                    else:
                        # Fallback to cosine similarity
                        similarity = self._compute_cosine_similarity(query_vector, vector)

                    # Find related entities through graph traversal
                    related_entities = []
                    if hasattr(self.graph_db, "find_related_entities"):
                        related_entities = self.graph_db.find_related_entities(
                            cid, max_hops=hop_count, include_properties=True
                        )

                    # Get metadata for this entity
                    metadata = self._get_metadata_for_entity(cid)

                    results.append(
                        {
                            "id": cid,
                            "score": similarity,
                            "metadata": metadata if metadata else {},
                            "properties": entity["properties"],
                            "related_entities": related_entities,
                            "source": "combined",
                        }
                    )

            # Sort by similarity score and return top results
            sorted_results = sorted(results, key=lambda x: x["score"], reverse=True)
            return sorted_results[:top_k]
        except Exception as e:
            logger.error(f"Combined search error: {str(e)}")
            return []

    def _compute_cosine_similarity(self, vec1, vec2):
        """Compute cosine similarity between two vectors."""
        try:
            # Convert to numpy arrays if necessary
            if not isinstance(vec1, np.ndarray):
                vec1 = np.array(vec1)
            if not isinstance(vec2, np.ndarray):
                vec2 = np.array(vec2)

            # Compute cosine similarity
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            return float(np.dot(vec1, vec2) / (norm1 * norm2))
        except Exception as e:
            logger.error(f"Similarity computation error: {str(e)}")
            return 0.0

    def _get_metadata_for_entity(self, entity_id):
        """Retrieve metadata for an entity from the Arrow index."""
        try:
            # Check if the entity exists in the metadata index
            if hasattr(self.metadata_index, "get_by_cid"):
                metadata_record = self.metadata_index.get_by_cid(entity_id)
                return metadata_record
            else:
                # Fallback to query
                filters = [("cid", "==", entity_id)]
                results = self.metadata_index.query(filters)
                if results.num_rows > 0:
                    return results.to_pylist()[0]
                return None
        except Exception as e:
            logger.debug(f"Metadata retrieval error for {entity_id}: {str(e)}")
            return None

    def index_entity(self, entity_id, properties, vector=None, relationships=None, metadata=None):
        """Index an entity in both the knowledge graph and metadata index.

        This method ensures that entities are properly indexed in both systems,
        maintaining consistency between the knowledge graph and metadata index.

        Args:
            entity_id: Unique identifier for the entity
            properties: Dictionary of entity properties
            vector: Optional embedding vector for similarity search
            relationships: Optional list of relationships to other entities
            metadata: Optional additional metadata for the Arrow index

        Returns:
            Dictionary with indexing results for both systems
        """
        result = {"success": False, "graph_result": None, "metadata_result": None, "errors": []}

        try:
            # 1. Add to knowledge graph
            graph_result = self.graph_db.add_entity(
                entity_id=entity_id, properties=properties, vector=vector
            )
            result["graph_result"] = graph_result

            # 2. Add relationships if provided
            if relationships:
                for rel in relationships:
                    self.graph_db.add_relationship(
                        from_entity=entity_id,
                        to_entity=rel["target"],
                        relationship_type=rel["type"],
                        properties=rel.get("properties", {}),
                    )

            # 3. Prepare metadata record
            if metadata is None:
                metadata = {}

            # Extract basic metadata from properties
            metadata_record = {
                "cid": entity_id,
                "size_bytes": metadata.get("size_bytes", 0),
                "mime_type": metadata.get("mime_type", "application/json"),
                "added_timestamp": metadata.get("added_timestamp", int(time.time() * 1000)),
                "tags": metadata.get("tags", []) + [properties.get("type", "entity")],
                "properties": {},
            }

            # Add embedding metadata if vector is provided
            if vector is not None:
                metadata_record["embedding_available"] = True
                metadata_record["embedding_dimensions"] = len(vector)
                metadata_record["embedding_type"] = "float32"

            # 4. Add to metadata index
            metadata_result = self.metadata_index.add_record(metadata_record)
            result["metadata_result"] = metadata_result

            # 5. Set overall success based on both operations
            result["success"] = graph_result is not None and metadata_result.get("success", False)

        except Exception as e:
            result["errors"].append(str(e))
            result["success"] = False
            logger.error(f"Failed to index entity {entity_id}: {str(e)}")

        return result

    def generate_llm_context(self, query, search_results, format_type="text"):
        """Generate formatted context for LLM consumption based on search results.

        Args:
            query: Original query string
            search_results: Results from hybrid_search
            format_type: Output format ("text", "json", or "markdown")

        Returns:
            Formatted context string ready for LLM prompt
        """
        try:
            # Use the GraphRAG's context generation with enhanced metadata
            enhanced_results = []

            for result in search_results:
                # Combine metadata and properties for richer context
                combined_properties = {**result.get("properties", {})}

                # Add metadata fields that aren't in properties
                metadata = result.get("metadata", {})
                for key, value in metadata.items():
                    if key not in combined_properties and key not in ("cid", "size_bytes"):
                        combined_properties[key] = value

                # Create enhanced result object
                enhanced_result = {
                    "entity_id": result["id"],
                    "score": result["score"],
                    "properties": combined_properties,
                    "source": result.get("source", "unknown"),
                }

                # Add path and distance if available (from graph traversal)
                if "path" in result:
                    enhanced_result["path"] = result["path"]
                if "distance" in result:
                    enhanced_result["distance"] = result["distance"]

                enhanced_results.append(enhanced_result)

            # Call the original GraphRAG context generation with enhanced results
            if hasattr(self.graph_db, "generate_llm_prompt"):
                return self.graph_db.generate_llm_prompt(query, enhanced_results, format_type)
            else:
                # Fallback to basic formatting if method not available
                return self._generate_basic_context(query, enhanced_results, format_type)
        except Exception as e:
            logger.error(f"Error generating LLM context: {str(e)}")
            return self._generate_basic_context(query, search_results, "text")

    def _generate_basic_context(self, query, results, format_type="text"):
        """Generate basic context when advanced formatting is not available."""
        if format_type == "markdown":
            context = f"## Context for query: {query}\n\n"
            for idx, result in enumerate(results, 1):
                context += f"### Result {idx}: {result.get('id')}\n"
                context += f"**Score:** {result.get('score', 0):.4f}\n\n"
                context += "**Properties:**\n"
                for key, value in result.get("properties", {}).items():
                    if isinstance(value, str) and len(value) > 100:
                        value = value[:100] + "..."
                    context += f"- {key}: {value}\n"
                context += "\n"
            return context
        elif format_type == "json":
            return str(results)
        else:  # text format
            context = f"Context for query: {query}\n\n"
            for idx, result in enumerate(results, 1):
                context += f"Result {idx}: {result.get('id')}\n"
                context += f"Score: {result.get('score', 0):.4f}\n"
                context += "Properties:\n"
                for key, value in result.get("properties", {}).items():
                    if isinstance(value, str) and len(value) > 100:
                        value = value[:100] + "..."
                    context += f"  {key}: {value}\n"
                context += "\n"
            return context


class AIMLSearchConnector:
    """Connects the hybrid search capabilities with AI/ML frameworks.

    This class provides integration between our hybrid search system and
    AI/ML frameworks like Langchain and LlamaIndex. It extends search
    capabilities to include model and dataset registries, and provides
    adapters for using hybrid search results with LLM frameworks.
    """

    def __init__(
        self,
        ipfs_client,
        hybrid_search=None,
        model_registry=None,
        dataset_manager=None,
        embedding_model=None,
        embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        embedding_model_type: str = "sentence-transformer",
    ):
        """Initialize the AI/ML search connector.

        Args:
            ipfs_client: The IPFS client instance
            hybrid_search: Optional existing MetadataEnhancedGraphRAG instance
            model_registry: Optional existing ModelRegistry instance
            dataset_manager: Optional existing DatasetManager instance
            embedding_model: Optional custom embedding model instance
            embedding_model_name: Name of the Hugging Face model to use for embeddings
            embedding_model_type: Type of model to use ("sentence-transformer", "transformers", "clip")
        """
        self.ipfs = ipfs_client

        # Check for AI/ML integration availability
        if not AI_ML_AVAILABLE:
            raise ImportError("AI/ML integration components not available")

        # Initialize or use provided hybrid search
        if hybrid_search is not None:
            self.hybrid_search = hybrid_search
        else:
            # Create a new hybrid search instance
            self.hybrid_search = MetadataEnhancedGraphRAG(ipfs_client)

        # Initialize or use provided model registry
        if model_registry is not None:
            self.model_registry = model_registry
        elif hasattr(ipfs_client, "model_registry"):
            self.model_registry = ipfs_client.model_registry
        else:
            self.model_registry = ModelRegistry(ipfs_client)

        # Initialize or use provided dataset manager
        if dataset_manager is not None:
            self.dataset_manager = dataset_manager
        elif hasattr(ipfs_client, "dataset_manager"):
            self.dataset_manager = ipfs_client.dataset_manager
        else:
            self.dataset_manager = DatasetManager(ipfs_client)

        # Initialize Langchain and LlamaIndex integrations
        self.langchain = LangchainIntegration(ipfs_client)
        self.llamaindex = LlamaIndexIntegration(ipfs_client)

        # Initialize or use provided custom embedding model
        if embedding_model is not None:
            self.custom_embedding_model = embedding_model
        elif hasattr(ipfs_client, "custom_embedding_model"):
            self.custom_embedding_model = ipfs_client.custom_embedding_model
        elif CustomEmbeddingModel is not None:
            try:
                logger.info(f"Initializing custom embedding model: {embedding_model_name}")
                self.custom_embedding_model = CustomEmbeddingModel(
                    ipfs_client=ipfs_client,
                    model_name=embedding_model_name,
                    model_type=embedding_model_type,
                )
                logger.info("Custom embedding model initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize custom embedding model: {e}")
                self.custom_embedding_model = None
        else:
            logger.warning("CustomEmbeddingModel not available, using default embeddings")
            self.custom_embedding_model = None

    def search_models(
        self,
        query_text=None,
        query_vector=None,
        metadata_filters=None,
        framework=None,
        task=None,
        min_accuracy=None,
        top_k=10,
    ):
        """Search for models using hybrid search capabilities.

        Args:
            query_text: Text query for semantic search
            query_vector: Vector embedding for similarity search
            metadata_filters: List of filters in format [(field, op, value)]
            framework: Specific framework filter (PyTorch, TensorFlow, etc.)
            task: Specific task filter (classification, segmentation, etc.)
            min_accuracy: Minimum model accuracy to include in results
            top_k: Maximum number of results to return

        Returns:
            Dictionary with search results
        """
        # Build metadata filters
        filters = metadata_filters or []

        # Add model-specific filters
        filters.append(("properties.type", "==", "model"))

        if framework:
            filters.append(("framework", "==", framework))

        if task:
            filters.append(("task", "==", task))

        if min_accuracy is not None:
            filters.append(("accuracy", ">=", min_accuracy))

        # Perform hybrid search
        results = self.hybrid_search.hybrid_search(
            query_text=query_text, query_vector=query_vector, metadata_filters=filters, top_k=top_k
        )

        # Enhance results with model registry information
        for result in results:
            model_id = result["id"]
            model_info = self.model_registry.get_model_metadata(model_id)
            if model_info:
                result["model_info"] = model_info

        return {
            "success": True,
            "results": results,
            "result_count": len(results),
            "query": query_text,
        }

    def search_datasets(
        self,
        query_text=None,
        query_vector=None,
        metadata_filters=None,
        domain=None,
        format=None,
        min_size=None,
        top_k=10,
    ):
        """Search for datasets using hybrid search capabilities.

        Args:
            query_text: Text query for semantic search
            query_vector: Vector embedding for similarity search
            metadata_filters: List of filters in format [(field, op, value)]
            domain: Specific domain filter (vision, nlp, etc.)
            format: Specific format filter (csv, parquet, etc.)
            min_size: Minimum dataset size to include in results
            top_k: Maximum number of results to return

        Returns:
            Dictionary with search results
        """
        # Build metadata filters
        filters = metadata_filters or []

        # Add dataset-specific filters
        filters.append(("properties.type", "==", "dataset"))

        if domain:
            filters.append(("domain", "==", domain))

        if format:
            filters.append(("format", "==", format))

        if min_size is not None:
            filters.append(("size_bytes", ">=", min_size))

        # Perform hybrid search
        results = self.hybrid_search.hybrid_search(
            query_text=query_text, query_vector=query_vector, metadata_filters=filters, top_k=top_k
        )

        # Enhance results with dataset manager information
        for result in results:
            dataset_id = result["id"]
            dataset_info = self.dataset_manager.get_dataset_metadata(dataset_id)
            if dataset_info:
                result["dataset_info"] = dataset_info

        return {
            "success": True,
            "results": results,
            "result_count": len(results),
            "query": query_text,
        }

    def create_langchain_retriever(
        self, retriever_type="hybrid", metadata_filters=None, search_kwargs=None
    ):
        """Create a Langchain retriever using hybrid search capabilities.

        Args:
            retriever_type: Type of retriever ("hybrid", "metadata", "vector")
            metadata_filters: Default metadata filters to apply
            search_kwargs: Additional search parameters

        Returns:
            Langchain retriever object
        """
        if retriever_type == "hybrid":
            # Create a wrapped hybrid retriever
            retriever = self._create_hybrid_langchain_retriever(
                metadata_filters=metadata_filters, search_kwargs=search_kwargs
            )
        elif retriever_type == "metadata":
            # Create a metadata-only retriever
            retriever = self._create_metadata_langchain_retriever(metadata_filters=metadata_filters)
        elif retriever_type == "vector":
            # Create a vector-only retriever
            retriever = self._create_vector_langchain_retriever(search_kwargs=search_kwargs)
        else:
            raise ValueError(f"Unknown retriever type: {retriever_type}")

        return retriever

    def _create_hybrid_langchain_retriever(self, metadata_filters=None, search_kwargs=None):
        """Create a Langchain retriever that uses hybrid search."""
        # Default search parameters
        search_kwargs = search_kwargs or {}

        # Define the search function for the retriever
        def hybrid_search_fn(query_text, **kwargs):
            # Combine search parameters
            combined_kwargs = {**search_kwargs, **kwargs}

            # Apply metadata filters
            filters = metadata_filters or []
            if "metadata_filters" in combined_kwargs:
                filters.extend(combined_kwargs["metadata_filters"])

            # Run hybrid search
            results = self.hybrid_search.hybrid_search(
                query_text=query_text,
                metadata_filters=filters,
                top_k=combined_kwargs.get("top_k", 4),
            )

            # Convert to Langchain documents
            documents = []
            for result in results:
                # Extract content from properties or metadata
                content = result.get("properties", {}).get("description", "")
                if not content:
                    content = result.get("metadata", {}).get("description", "")

                # Create metadata from properties and metadata
                metadata = {
                    "id": result["id"],
                    "score": result["score"],
                    "source": result.get("source", "hybrid"),
                }

                # Add properties and metadata
                properties = result.get("properties", {})
                for key, value in properties.items():
                    if isinstance(value, (str, int, float, bool)):
                        metadata[f"prop_{key}"] = value

                result_metadata = result.get("metadata", {})
                for key, value in result_metadata.items():
                    if isinstance(value, (str, int, float, bool)):
                        metadata[f"meta_{key}"] = value

                # Create document
                documents.append({"page_content": content, "metadata": metadata})

            return documents

        # Create a retriever using the Langchain integration
        retriever = self.langchain.create_custom_retriever(hybrid_search_fn)
        return retriever

    def _create_metadata_langchain_retriever(self, metadata_filters=None):
        """Create a Langchain retriever that uses metadata-only search."""
        # Implementation similar to hybrid but with metadata-only search
        pass

    def _create_vector_langchain_retriever(self, search_kwargs=None):
        """Create a Langchain retriever that uses vector-only search."""
        # Implementation similar to hybrid but with vector-only search
        pass

    def create_llamaindex_retriever(
        self, retriever_type="hybrid", metadata_filters=None, search_kwargs=None
    ):
        """Create a LlamaIndex retriever using hybrid search capabilities.

        Args:
            retriever_type: Type of retriever ("hybrid", "metadata", "vector")
            metadata_filters: Default metadata filters to apply
            search_kwargs: Additional search parameters

        Returns:
            LlamaIndex retriever object
        """
        # Implementation similar to Langchain retriever but for LlamaIndex
        pass

    def generate_embedding(self, text):
        """Generate embeddings for text using the best available embedding model.

        Prioritizes:
        1. Custom Hugging Face embedding model if available (best quality)
        2. Langchain embeddings as fallback
        3. Empty embedding vector if no embedding capability is available

        Args:
            text: Text to generate embeddings for

        Returns:
            Embedding vector as list of floats
        """
        try:
            # Use custom embedding model if available (best quality)
            if hasattr(self, "custom_embedding_model") and self.custom_embedding_model is not None:
                logger.debug(
                    f"Generating embedding using custom model: {self.custom_embedding_model.model_name}"
                )
                return self.custom_embedding_model.generate_embedding(text)

            # Fall back to Langchain embeddings if available
            elif hasattr(self, "langchain") and self.langchain is not None:
                logger.debug("Generating embedding using Langchain")
                return self.langchain.embed_texts([text])[0]

            # Fall back to empty vector as last resort
            else:
                logger.warning("No embedding model available, using empty vector")
                return [0.0] * 384  # Standard dimension for sentence-transformers/all-MiniLM-L6-v2

        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            # Return empty vector of standard size
            return [0.0] * 384


class DistributedQueryOptimizer:
    """Distributed query optimization for integrated search.

    This class enables distributing complex search operations across worker nodes
    to improve performance and scalability for large datasets. It uses a MapReduce-style
    pattern to split queries, execute them in parallel, and combine the results.
    """

    def __init__(self, ipfs_client, cluster_manager=None, max_workers=None):
        """Initialize the distributed query optimizer.

        Args:
            ipfs_client: The IPFS client instance
            cluster_manager: Optional cluster manager for node coordination
            max_workers: Maximum number of worker nodes to use (None for all available)
        """
        self.ipfs = ipfs_client
        self.cluster_manager = cluster_manager
        self.max_workers = max_workers

        # Get role from IPFS client
        self.role = getattr(ipfs_client, "role", "leecher")

        # Check if we're in a master role
        if self.role != "master" and not self.cluster_manager:
            logger.warning(
                "DistributedQueryOptimizer initialized without master role or cluster manager. "
                "Some functionality may be limited."
            )

        # Statistics tracking
        self.stats = {
            "queries_processed": 0,
            "distributed_operations": 0,
            "local_operations": 0,
            "worker_usage": {},
        }

    def get_available_workers(self):
        """Get list of available worker nodes for distributed operations.

        Returns:
            List of worker node information (IDs and capabilities)
        """
        workers = []

        # If cluster manager is available, get worker nodes
        if self.cluster_manager and hasattr(self.cluster_manager, "get_worker_nodes"):
            all_workers = self.cluster_manager.get_worker_nodes()

            # Filter for active workers with search capabilities
            for worker in all_workers:
                if worker.get("status") == "online" and "search" in worker.get("capabilities", []):
                    workers.append(worker)

            # Limit workers if max_workers is set
            if self.max_workers is not None and len(workers) > self.max_workers:
                workers = workers[: self.max_workers]

        return workers

    def is_query_distributable(self, query_params):
        """Determine if a query can be distributed across nodes.

        Args:
            query_params: The query parameters to evaluate

        Returns:
            Boolean indicating if the query can be distributed
        """
        # Queries that can be distributed:
        # 1. Metadata filters that don't require global knowledge
        # 2. Vector searches that can be run independently
        # 3. Hybrid searches where vector part is expensive

        # Check if we have any workers to distribute to
        if not self.get_available_workers():
            return False

        # Check query specifics
        query_type = self._determine_query_type(query_params)

        if query_type == "metadata":
            # Metadata queries are distributable if they have partitionable filters
            filters = query_params.get("metadata_filters", [])
            return self._are_filters_distributable(filters)

        elif query_type == "vector":
            # Vector queries are distributable if they're computationally expensive
            # (approximated by using a high value of top_k)
            top_k = query_params.get("top_k", 10)
            return top_k > 50  # Arbitrary threshold, could be tuned

        elif query_type == "hybrid":
            # Hybrid queries are distributable if both parts are distributable
            metadata_distributable = self._are_filters_distributable(
                query_params.get("metadata_filters", [])
            )

            # Vector part is complex enough to distribute
            vector_part_complex = (
                query_params.get("hop_count", 1) > 1 or query_params.get("top_k", 10) > 20
            )

            return metadata_distributable and vector_part_complex

        return False

    def _determine_query_type(self, query_params):
        """Determine the type of query based on parameters."""
        has_query_text = "query_text" in query_params or "query_vector" in query_params
        has_metadata_filters = (
            "metadata_filters" in query_params and query_params["metadata_filters"]
        )

        if has_query_text and has_metadata_filters:
            return "hybrid"
        elif has_query_text:
            return "vector"
        elif has_metadata_filters:
            return "metadata"
        else:
            return "unknown"

    def _are_filters_distributable(self, filters):
        """Check if metadata filters can be distributed."""
        if not filters:
            return False

        # Filters that require global knowledge can't be effectively distributed
        # Examples: sorting by global rank, percentile calculations
        non_distributable_operations = ["global_rank", "percentile", "nth_highest"]

        for filter_item in filters:
            if len(filter_item) >= 3:
                field, op, value = filter_item[:3]
                if any(term in field.lower() for term in non_distributable_operations):
                    return False

        return True

    def distribute_query(self, query_params, hybrid_search_instance):
        """Distribute a query across worker nodes.

        Args:
            query_params: Parameters defining the search query
            hybrid_search_instance: MetadataEnhancedGraphRAG instance for local execution

        Returns:
            Combined search results
        """
        # Update stats
        self.stats["queries_processed"] += 1

        # Check if query can be distributed
        if not self.is_query_distributable(query_params):
            # Run locally if not distributable
            self.stats["local_operations"] += 1

            if "query_text" in query_params or "query_vector" in query_params:
                if "metadata_filters" in query_params and query_params["metadata_filters"]:
                    return hybrid_search_instance._combined_search(**query_params)
                else:
                    return hybrid_search_instance._vector_only_search(**query_params)
            else:
                return hybrid_search_instance._metadata_only_search(
                    query_params.get("metadata_filters", []), query_params.get("top_k", 10)
                )

        # If we get here, the query is distributable
        self.stats["distributed_operations"] += 1

        # Get available workers
        workers = self.get_available_workers()
        if not workers:
            # Fallback to local execution if no workers
            self.stats["local_operations"] += 1
            logger.warning("No workers available for distributed query. Running locally.")
            return hybrid_search_instance.hybrid_search(**query_params)

        # Determine query type and create distribution plan
        query_type = self._determine_query_type(query_params)
        distribution_plan = self._create_distribution_plan(query_type, query_params, workers)

        # Execute the distributed query
        worker_results = self._execute_distribution_plan(distribution_plan)

        # Combine results
        combined_results = self._combine_results(worker_results, query_params)

        return combined_results

    def _create_distribution_plan(self, query_type, query_params, workers):
        """Create a plan for distributing the query across workers.

        Args:
            query_type: Type of query (metadata, vector, hybrid)
            query_params: Parameters defining the search query
            workers: Available worker nodes

        Returns:
            Distribution plan with worker assignments
        """
        plan = {
            "query_type": query_type,
            "worker_assignments": [],
            "original_params": query_params.copy(),
        }

        # Number of workers to use
        worker_count = len(workers)

        if query_type == "metadata":
            # For metadata queries, each worker searches a different partition
            filters = query_params.get("metadata_filters", [])
            top_k = query_params.get("top_k", 10)

            # Each worker gets same filters but increased top_k to ensure coverage
            worker_top_k = min(top_k * 2, top_k + 20)  # Heuristic

            for worker in workers:
                assignment = {
                    "worker": worker,
                    "params": {"metadata_filters": filters, "top_k": worker_top_k},
                }
                plan["worker_assignments"].append(assignment)

        elif query_type == "vector":
            # For vector queries, split by vector space regions or by top_k
            query_text = query_params.get("query_text")
            query_vector = query_params.get("query_vector")
            top_k = query_params.get("top_k", 10)
            hop_count = query_params.get("hop_count", 1)

            # Increase top_k for workers to ensure coverage
            worker_top_k = min(top_k * 2, top_k + 20)  # Heuristic

            for worker in workers:
                assignment = {
                    "worker": worker,
                    "params": {
                        "query_text": query_text,
                        "query_vector": query_vector,
                        "top_k": worker_top_k,
                        "hop_count": hop_count,
                    },
                }
                plan["worker_assignments"].append(assignment)

        elif query_type == "hybrid":
            # For hybrid queries, split both vector and metadata components
            query_text = query_params.get("query_text")
            query_vector = query_params.get("query_vector")
            filters = query_params.get("metadata_filters", [])
            top_k = query_params.get("top_k", 10)
            hop_count = query_params.get("hop_count", 1)

            # Increase top_k for workers to ensure coverage
            worker_top_k = min(top_k * 2, top_k + 20)  # Heuristic

            for worker in workers:
                assignment = {
                    "worker": worker,
                    "params": {
                        "query_text": query_text,
                        "query_vector": query_vector,
                        "metadata_filters": filters,
                        "top_k": worker_top_k,
                        "hop_count": hop_count,
                    },
                }
                plan["worker_assignments"].append(assignment)

        return plan

    def _execute_distribution_plan(self, plan):
        """Execute the distributed query plan across workers.

        Args:
            plan: Distribution plan with worker assignments

        Returns:
            Results from all workers
        """
        worker_results = []

        # For true distributed execution, we'd use async execution here
        # This simplified version uses sequential execution for now
        for assignment in plan["worker_assignments"]:
            worker = assignment["worker"]
            params = assignment["params"]

            try:
                # In a real implementation, this would be a network call or message to worker
                # For now, we simulate worker execution
                result = self._simulate_worker_execution(worker, params, plan["query_type"])

                # Track worker usage
                worker_id = worker.get("id", "unknown")
                if worker_id not in self.stats["worker_usage"]:
                    self.stats["worker_usage"][worker_id] = 0
                self.stats["worker_usage"][worker_id] += 1

                # Add to results
                worker_results.append({"worker": worker, "results": result, "success": True})

            except Exception as e:
                logger.error(f"Error executing query on worker {worker.get('id', 'unknown')}: {e}")
                worker_results.append({"worker": worker, "error": str(e), "success": False})

        return worker_results

    def _simulate_worker_execution(self, worker, params, query_type):
        """Simulate execution of query on a worker node.

        In a real implementation, this would be a remote procedure call.
        This simulation simply creates plausible results.

        Args:
            worker: Worker node information
            params: Query parameters
            query_type: Type of query

        Returns:
            Simulated search results
        """
        # Create a MetadataEnhancedGraphRAG instance for simulation
        # In a real implementation, this would be on the worker node
        hybrid_search = MetadataEnhancedGraphRAG(self.ipfs)

        # Execute query based on type
        if query_type == "metadata":
            return hybrid_search._metadata_only_search(
                params.get("metadata_filters", []), params.get("top_k", 10)
            )
        elif query_type == "vector":
            return hybrid_search._vector_only_search(
                query_text=params.get("query_text"),
                query_vector=params.get("query_vector"),
                entity_types=params.get("entity_types"),
                hop_count=params.get("hop_count", 1),
                top_k=params.get("top_k", 10),
            )
        elif query_type == "hybrid":
            return hybrid_search._combined_search(
                query_text=params.get("query_text"),
                query_vector=params.get("query_vector"),
                metadata_filters=params.get("metadata_filters"),
                entity_types=params.get("entity_types"),
                hop_count=params.get("hop_count", 1),
                top_k=params.get("top_k", 10),
            )
        else:
            raise ValueError(f"Unknown query type: {query_type}")

    def _combine_results(self, worker_results, original_params):
        """Combine results from all workers into a unified result set.

        Args:
            worker_results: Results from all workers
            original_params: Original query parameters

        Returns:
            Combined search results
        """
        # Extract results from successful workers
        all_results = []
        for worker_result in worker_results:
            if worker_result["success"]:
                all_results.extend(worker_result["results"])

        if not all_results:
            return []

        # Group by ID to eliminate duplicates
        grouped_results = {}
        for result in all_results:
            result_id = result["id"]

            if result_id not in grouped_results:
                grouped_results[result_id] = result
            else:
                # Keep the result with higher score if duplicate
                if result["score"] > grouped_results[result_id]["score"]:
                    grouped_results[result_id] = result

        # Sort by score
        sorted_results = sorted(grouped_results.values(), key=lambda x: x["score"], reverse=True)

        # Limit to requested top_k
        top_k = original_params.get("top_k", 10)
        return sorted_results[:top_k]

    def get_optimization_stats(self):
        """Get statistics about distributed query optimization.

        Returns:
            Dictionary with optimization statistics
        """
        total_ops = self.stats["distributed_operations"] + self.stats["local_operations"]
        distribution_ratio = 0
        if total_ops > 0:
            distribution_ratio = self.stats["distributed_operations"] / total_ops

        # Calculate worker load balance (if any distributed operations)
        worker_balance = 0
        if self.stats["worker_usage"] and self.stats["distributed_operations"] > 0:
            usages = list(self.stats["worker_usage"].values())
            avg_usage = sum(usages) / len(usages)
            max_dev = max(abs(u - avg_usage) for u in usages)
            worker_balance = 1 - (max_dev / avg_usage if avg_usage > 0 else 0)

        return {
            "queries_processed": self.stats["queries_processed"],
            "distributed_operations": self.stats["distributed_operations"],
            "local_operations": self.stats["local_operations"],
            "distribution_ratio": distribution_ratio,
            "worker_usage": dict(
                sorted(self.stats["worker_usage"].items(), key=lambda x: x[1], reverse=True)
            ),
            "worker_balance": worker_balance,
        }


class SearchBenchmark:
    """Performance benchmarking tools for integrated search functionality.

    This class provides comprehensive benchmarking capabilities for measuring
    the performance characteristics of the integrated search system across
    different configurations, query types, and workloads.
    """

    def __init__(self, ipfs_client, search_connector=None, output_dir=None):
        """Initialize the search benchmarking tools.

        Args:
            ipfs_client: The IPFS client instance
            search_connector: Optional existing AIMLSearchConnector instance
            output_dir: Directory for benchmark results (default: ~/.ipfs_benchmarks)
        """
        self.ipfs = ipfs_client
        self.output_dir = output_dir or os.path.expanduser("~/.ipfs_benchmarks")
        os.makedirs(self.output_dir, exist_ok=True)

        # Initialize search connector if not provided
        if search_connector is not None:
            self.search_connector = search_connector
        elif AI_ML_AVAILABLE:
            self.search_connector = AIMLSearchConnector(ipfs_client)
        else:
            self.search_connector = None

        # Initialize hybrid search instance
        self.hybrid_search = MetadataEnhancedGraphRAG(ipfs_client)

        # Statistics tracking
        self.stats = {"runs": [], "aggregates": {}}

    def benchmark_metadata_search(self, filters_list=None, num_runs=10, warm_cache=True):
        """Benchmark metadata-only search performance.

        Args:
            filters_list: List of metadata filter sets to benchmark
            num_runs: Number of times to run each benchmark
            warm_cache: Whether to warm the cache before benchmarking

        Returns:
            Dictionary with benchmark results
        """
        filters_list = filters_list or [
            [("tags", "contains", "model")],
            [("framework", "==", "pytorch")],
            [("task", "==", "classification"), ("accuracy", ">=", 0.8)],
        ]

        results = {
            "benchmark_type": "metadata_search",
            "filters_tested": filters_list,
            "num_runs": num_runs,
            "warm_cache": warm_cache,
            "runs": [],
        }

        # Optional cache warming
        if warm_cache:
            for filters in filters_list:
                self.hybrid_search._metadata_only_search(filters, top_k=10)

        # Run benchmarks
        for filters in filters_list:
            filter_results = {"filters": filters, "latencies_ms": [], "result_counts": []}

            for _ in range(num_runs):
                start_time = time.time()
                search_results = self.hybrid_search._metadata_only_search(filters, top_k=10)
                end_time = time.time()

                latency_ms = (end_time - start_time) * 1000
                filter_results["latencies_ms"].append(latency_ms)
                filter_results["result_counts"].append(len(search_results))

            # Calculate statistics
            latencies = filter_results["latencies_ms"]
            filter_results["min_latency_ms"] = min(latencies)
            filter_results["max_latency_ms"] = max(latencies)
            filter_results["avg_latency_ms"] = sum(latencies) / len(latencies)
            filter_results["median_latency_ms"] = sorted(latencies)[len(latencies) // 2]

            results["runs"].append(filter_results)

        # Calculate overall statistics
        all_latencies = [latency for run in results["runs"] for latency in run["latencies_ms"]]
        results["overall_stats"] = {
            "min_latency_ms": min(all_latencies),
            "max_latency_ms": max(all_latencies),
            "avg_latency_ms": sum(all_latencies) / len(all_latencies),
            "median_latency_ms": sorted(all_latencies)[len(all_latencies) // 2],
            "total_queries": len(all_latencies),
        }

        # Store results
        self.stats["runs"].append(results)
        return results

    def benchmark_vector_search(
        self, queries=None, vector_dimensions=None, num_runs=10, warm_cache=True
    ):
        """Benchmark vector search performance.

        Args:
            queries: List of text queries to convert to vectors
            vector_dimensions: Dimensionality of random vectors if queries not provided
            num_runs: Number of times to run each benchmark
            warm_cache: Whether to warm the cache before benchmarking

        Returns:
            Dictionary with benchmark results
        """
        # Generate queries if not provided
        if queries is None:
            queries = [
                "machine learning model for image classification",
                "transformer architecture for natural language processing",
                "graph neural network for recommendation systems",
            ]

        # Generate random vectors for testing if no queries
        vectors = []
        if vector_dimensions is not None:
            import numpy as np

            vectors = [np.random.rand(vector_dimensions).tolist() for _ in range(3)]

        results = {
            "benchmark_type": "vector_search",
            "queries": queries,
            "vectors": vectors,
            "num_runs": num_runs,
            "warm_cache": warm_cache,
            "runs": [],
        }

        # Prepare test cases - either text queries or vectors
        test_cases = []
        if queries:
            test_cases.extend([{"query_text": q} for q in queries])
        if vectors:
            test_cases.extend([{"query_vector": v} for v in vectors])

        # Optional cache warming
        if warm_cache:
            for case in test_cases:
                self.hybrid_search._vector_only_search(
                    **case, entity_types=None, hop_count=1, top_k=10
                )

        # Run benchmarks
        for case in test_cases:
            case_results = {"case": case, "latencies_ms": [], "result_counts": []}

            for _ in range(num_runs):
                start_time = time.time()
                search_results = self.hybrid_search._vector_only_search(
                    **case, entity_types=None, hop_count=1, top_k=10
                )
                end_time = time.time()

                latency_ms = (end_time - start_time) * 1000
                case_results["latencies_ms"].append(latency_ms)
                case_results["result_counts"].append(len(search_results))

            # Calculate statistics
            latencies = case_results["latencies_ms"]
            case_results["min_latency_ms"] = min(latencies)
            case_results["max_latency_ms"] = max(latencies)
            case_results["avg_latency_ms"] = sum(latencies) / len(latencies)
            case_results["median_latency_ms"] = sorted(latencies)[len(latencies) // 2]

            results["runs"].append(case_results)

        # Calculate overall statistics
        all_latencies = [latency for run in results["runs"] for latency in run["latencies_ms"]]
        results["overall_stats"] = {
            "min_latency_ms": min(all_latencies),
            "max_latency_ms": max(all_latencies),
            "avg_latency_ms": sum(all_latencies) / len(all_latencies),
            "median_latency_ms": sorted(all_latencies)[len(all_latencies) // 2],
            "total_queries": len(all_latencies),
        }

        # Store results
        self.stats["runs"].append(results)
        return results

    def benchmark_hybrid_search(self, test_cases=None, num_runs=10, warm_cache=True):
        """Benchmark hybrid search performance.

        Args:
            test_cases: List of test cases with query_text/query_vector and metadata_filters
            num_runs: Number of times to run each benchmark
            warm_cache: Whether to warm the cache before benchmarking

        Returns:
            Dictionary with benchmark results
        """
        # Generate test cases if not provided
        if test_cases is None:
            test_cases = [
                {
                    "query_text": "image classification model",
                    "metadata_filters": [("framework", "==", "pytorch")],
                },
                {"query_text": "transformer model", "metadata_filters": [("task", "==", "nlp")]},
                {
                    "query_text": "recommendation system",
                    "metadata_filters": [("accuracy", ">=", 0.8)],
                },
            ]

        results = {
            "benchmark_type": "hybrid_search",
            "test_cases": test_cases,
            "num_runs": num_runs,
            "warm_cache": warm_cache,
            "runs": [],
        }

        # Optional cache warming
        if warm_cache:
            for case in test_cases:
                self.hybrid_search._combined_search(
                    query_text=case.get("query_text"),
                    query_vector=case.get("query_vector"),
                    metadata_filters=case.get("metadata_filters"),
                    entity_types=case.get("entity_types"),
                    hop_count=case.get("hop_count", 1),
                    top_k=case.get("top_k", 10),
                )

        # Run benchmarks
        for case in test_cases:
            case_results = {"case": case, "latencies_ms": [], "result_counts": []}

            for _ in range(num_runs):
                start_time = time.time()
                search_results = self.hybrid_search._combined_search(
                    query_text=case.get("query_text"),
                    query_vector=case.get("query_vector"),
                    metadata_filters=case.get("metadata_filters"),
                    entity_types=case.get("entity_types"),
                    hop_count=case.get("hop_count", 1),
                    top_k=case.get("top_k", 10),
                )
                end_time = time.time()

                latency_ms = (end_time - start_time) * 1000
                case_results["latencies_ms"].append(latency_ms)
                case_results["result_counts"].append(len(search_results))

            # Calculate statistics
            latencies = case_results["latencies_ms"]
            case_results["min_latency_ms"] = min(latencies) if latencies else 0
            case_results["max_latency_ms"] = max(latencies) if latencies else 0
            case_results["avg_latency_ms"] = sum(latencies) / len(latencies) if latencies else 0
            case_results["median_latency_ms"] = (
                sorted(latencies)[len(latencies) // 2] if latencies else 0
            )

            results["runs"].append(case_results)

        # Calculate overall statistics
        all_latencies = [latency for run in results["runs"] for latency in run["latencies_ms"]]
        results["overall_stats"] = {
            "min_latency_ms": min(all_latencies) if all_latencies else 0,
            "max_latency_ms": max(all_latencies) if all_latencies else 0,
            "avg_latency_ms": sum(all_latencies) / len(all_latencies) if all_latencies else 0,
            "median_latency_ms": (
                sorted(all_latencies)[len(all_latencies) // 2] if all_latencies else 0
            ),
            "total_queries": len(all_latencies),
        }

        # Store results
        self.stats["runs"].append(results)
        return results

    def run_full_benchmark_suite(self, num_runs=10, save_results=True):
        """Run the complete benchmark suite with all test types.

        Args:
            num_runs: Number of times to run each benchmark
            save_results: Whether to save results to disk

        Returns:
            Dictionary with complete benchmark results
        """
        start_time = time.time()

        # Run individual benchmarks
        metadata_results = self.benchmark_metadata_search(num_runs=num_runs)
        vector_results = self.benchmark_vector_search(num_runs=num_runs)
        hybrid_results = self.benchmark_hybrid_search(num_runs=num_runs)

        # Compile overall results
        results = {
            "benchmark_timestamp": time.time(),
            "benchmark_duration_s": time.time() - start_time,
            "num_runs": num_runs,
            "metadata_search": metadata_results,
            "vector_search": vector_results,
            "hybrid_search": hybrid_results,
            "comparison": {
                "avg_latency_ms": {
                    "metadata_search": metadata_results["overall_stats"]["avg_latency_ms"],
                    "vector_search": vector_results["overall_stats"]["avg_latency_ms"],
                    "hybrid_search": hybrid_results["overall_stats"]["avg_latency_ms"],
                }
            },
        }

        # Save results if requested
        if save_results:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"search_benchmark_{timestamp}.json"
            filepath = os.path.join(self.output_dir, filename)

            with open(filepath, "w") as f:
                import json

                json.dump(results, f, indent=2)

            results["saved_to"] = filepath

        return results

    def generate_benchmark_report(self, results=None, format="markdown"):
        """Generate a human-readable report from benchmark results.

        Args:
            results: Benchmark results (uses last run if None)
            format: Output format ("markdown", "text", or "html")

        Returns:
            Formatted benchmark report
        """
        # Use provided results or last run
        if results is None:
            if not self.stats["runs"]:
                return "No benchmark results available"
            results = self.stats["runs"][-1]

        # Generate report header
        if format == "markdown":
            report = "# IPFS Integrated Search Benchmark Report\n\n"
            report += f"Benchmark conducted at: {time.ctime(results.get('benchmark_timestamp', time.time()))}\n"
            report += f"Total benchmark duration: {results.get('benchmark_duration_s', 0):.2f} seconds\n\n"

            # Add comparison table
            report += "## Performance Comparison\n\n"
            report += "| Search Type | Avg Latency (ms) | Min Latency (ms) | Max Latency (ms) | Median Latency (ms) |\n"
            report += "|-------------|-----------------|-----------------|------------------|--------------------|\n"

            for search_type in ["metadata_search", "vector_search", "hybrid_search"]:
                if search_type in results:
                    stats = results[search_type]["overall_stats"]
                    report += f"| {search_type.replace('_', ' ').title()} | "
                    report += f"{stats['avg_latency_ms']:.2f} | "
                    report += f"{stats['min_latency_ms']:.2f} | "
                    report += f"{stats['max_latency_ms']:.2f} | "
                    report += f"{stats['median_latency_ms']:.2f} |\n"

            # Add detailed sections
            for search_type in ["metadata_search", "vector_search", "hybrid_search"]:
                if search_type in results:
                    report += f"\n## {search_type.replace('_', ' ').title()} Results\n\n"

                    # Add test case details
                    for i, run in enumerate(results[search_type]["runs"]):
                        report += f"### Test Case {i+1}\n\n"

                        # Format test case parameters
                        if "filters" in run:
                            filters_str = ", ".join(
                                [f"{f[0]} {f[1]} {f[2]}" for f in run["filters"]]
                            )
                            report += f"Filters: `{filters_str}`\n\n"
                        elif "case" in run:
                            case_str = ""
                            if "query_text" in run["case"]:
                                case_str += f"Query: \"{run['case']['query_text']}\"\n\n"
                            if "query_vector" in run["case"]:
                                case_str += (
                                    f"Vector dimensions: {len(run['case']['query_vector'])}\n\n"
                                )
                            if "metadata_filters" in run["case"]:
                                filters_str = ", ".join(
                                    [
                                        f"{f[0]} {f[1]} {f[2]}"
                                        for f in run["case"]["metadata_filters"]
                                    ]
                                )
                                case_str += f"Filters: `{filters_str}`\n\n"
                            report += case_str

                        # Add performance metrics
                        report += "**Performance Metrics:**\n\n"
                        report += f"- **Minimum Latency**: {run['min_latency_ms']:.2f} ms\n"
                        report += f"- **Maximum Latency**: {run['max_latency_ms']:.2f} ms\n"
                        report += f"- **Average Latency**: {run['avg_latency_ms']:.2f} ms\n"
                        report += f"- **Median Latency**: {run['median_latency_ms']:.2f} ms\n"
                        report += f"- **Average Results**: {sum(run['result_counts']) / len(run['result_counts']):.1f}\n\n"

            # Add summary and recommendations
            report += "\n## Summary and Recommendations\n\n"

            # Identify slowest and fastest operations
            search_types = ["metadata_search", "vector_search", "hybrid_search"]
            latencies = {
                st: results[st]["overall_stats"]["avg_latency_ms"]
                for st in search_types
                if st in results
            }

            fastest = min(latencies.items(), key=lambda x: x[1])
            slowest = max(latencies.items(), key=lambda x: x[1])

            report += f"- Fastest search type: **{fastest[0].replace('_', ' ').title()}** ({fastest[1]:.2f} ms)\n"
            report += f"- Slowest search type: **{slowest[0].replace('_', ' ').title()}** ({slowest[1]:.2f} ms)\n"

            # Calculate overhead of hybrid search
            if (
                "metadata_search" in latencies
                and "vector_search" in latencies
                and "hybrid_search" in latencies
            ):
                separate_total = latencies["metadata_search"] + latencies["vector_search"]
                hybrid_overhead = (latencies["hybrid_search"] / separate_total - 1) * 100
                report += f"- Hybrid search overhead: **{hybrid_overhead:.1f}%** over running metadata and vector searches separately\n\n"

                if hybrid_overhead < 0:
                    report += "**Recommendation**: Hybrid search is more efficient than running separate searches. "
                    report += "Prefer combined queries when both metadata and vector search are needed.\n\n"
                else:
                    report += "**Recommendation**: For maximum performance, consider running metadata filters first to "
                    report += (
                        "narrow the candidate set before running vector similarity search.\n\n"
                    )

            return report

        elif format == "text":
            # Simplified text format implementation
            return "Text format report not implemented yet"

        elif format == "html":
            # HTML format implementation
            return "HTML format report not implemented yet"

        else:
            return f"Unsupported format: {format}"
