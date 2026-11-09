#\!/usr/bin/env python3
"""
Script to enhance AI/ML methods in high_level_api.py with keyword-only parameters,
type annotations, and better simulation handling.
"""

import os
import re
import sys
import time
from typing import List, Dict, Any, Union, Optional, Tuple, Literal

def read_file(path: str) -> str:
    """Read a file and return its content."""
    with open(path, 'r') as f:
        return f.read()

def write_file(path: str, content: str) -> None:
    """Write content to a file."""
    with open(path, 'w') as f:
        f.write(content)

def find_method(content: str, method_name: str) -> tuple:
    """Find a method in the content and return its start index, end index, and the method text."""
    # Regular expression to find the method definition
    pattern = rf'def {method_name}\s*\('
    match = re.search(pattern, content)
    
    if not match:
        return -1, -1, ""
    
    start_idx = match.start()
    
    # Find the method body by counting braces
    idx = match.end()
    brace_count = 1  # We've already found the opening parenthesis
    
    # Find the end of the method signature
    while idx < len(content) and brace_count > 0:
        if content[idx] == '(':
            brace_count += 1
        elif content[idx] == ')':
            brace_count -= 1
        idx += 1
    
    # Now find the docstring
    while idx < len(content) and content[idx].isspace():
        idx += 1
    
    # Check if there's a docstring
    if idx < len(content) and content[idx:idx+3] == '"""':
        # Find the end of the docstring
        idx = content.find('"""', idx + 3)
        if idx != -1:
            idx += 3  # Move past the closing quotes
    
    # Find the method body by tracking indentation
    method_text = content[start_idx:idx]
    lines = content[idx:].split('\n')
    
    method_indent = None
    current_method_text = method_text
    for i, line in enumerate(lines):
        if line.strip() and not line.isspace():
            # Get the indentation of the first non-empty line
            current_indent = len(line) - len(line.lstrip())
            
            if method_indent is None:
                method_indent = current_indent
                current_method_text += '\n' + line
            elif current_indent <= method_indent and not line.strip().startswith(('#', ' ', '\t')):
                # Found a line with less or equal indentation, and it's not a comment or continuation
                # This marks the end of the method
                break
            else:
                current_method_text += '\n' + line
        else:
            # Empty line, keep it as part of the method
            current_method_text += '\n' + line
    
    end_idx = start_idx + len(current_method_text)
    return start_idx, end_idx, current_method_text

def enhance_ai_vector_search(method_text: str) -> str:
    """Enhance the ai_vector_search method with keyword-only parameters and type annotations."""
    enhanced_method = '''def ai_vector_search(
    self, 
    query: Union[str, List[float]], 
    vector_index_cid: str, 
    *, 
    top_k: int = 10, 
    similarity_threshold: float = 0.0, 
    filter: Optional[Dict[str, Any]] = None, 
    embedding_model: Optional[str] = None, 
    search_type: Literal["similarity", "knn", "hybrid"] = "similarity", 
    timeout: int = 30,
    allow_simulation: bool = True,
    **kwargs
) -> Dict[str, Any]:
    """
    Perform vector similarity search using a vector index.

    Args:
        query: Query text or embedding vector to search for
        vector_index_cid: CID of the vector index
        top_k: Number of top results to return
        similarity_threshold: Minimum similarity threshold (0.0-1.0)
        filter: Optional dictionary of metadata filters to apply to search results
        embedding_model: Optional name of embedding model to use (if query is text)
        search_type: Type of search to perform ("similarity", "knn", "hybrid")
        timeout: Operation timeout in seconds
        allow_simulation: Whether to allow simulated results when AI/ML integration is unavailable
        **kwargs: Additional parameters

    Returns:
        Dict[str, Any]: Dictionary with search results containing these keys:
            - "success": bool indicating if the operation succeeded
            - "operation": Name of the operation ("ai_vector_search")
            - "timestamp": Time when the operation was performed
            - "query": The original query (text or vector representation)
            - "results": List of search results with content and similarity scores
            - "total_vectors_searched": Number of vectors searched
            - "search_time_ms": Search time in milliseconds
            - "error": Error message if operation failed (only present on failure)
            - "error_type": Type of error if operation failed (only present on failure)
    """
    from . import validation

    # Build kwargs dictionary
    kwargs_dict = {}
    if filter is not None:
        kwargs_dict["filter"] = filter
    if embedding_model is not None:
        kwargs_dict["embedding_model"] = embedding_model
    kwargs_dict["search_type"] = search_type
    kwargs_dict["timeout"] = timeout
    
    # Add any additional kwargs
    kwargs_dict.update(kwargs)
    
    # Validate parameters
    validation.validate_parameters(
        kwargs_dict,
        {
            "filter": {"type": dict},
            "embedding_model": {"type": str},
            "search_type": {"type": str, "default": "similarity"},
            "timeout": {"type": int, "default": 30},
        },
    )

    # Validate similarity threshold
    if not 0.0 <= similarity_threshold <= 1.0:
        raise ValueError("similarity_threshold must be between 0.0 and 1.0")

    # Check if AI/ML integration is available
    if not AI_ML_AVAILABLE and allow_simulation:
        # Fallback to simulation for demonstration

        # Generate simulated search results
        results = []
        for i in range(min(top_k, 5)):  # Simulate up to 5 results
            results.append(
                {
                    "content": f"This is content {i} that matched the query.",
                    "similarity": 0.95 - (i * 0.05),  # Decreasing similarity
                    "metadata": {
                        "source": f"document_{i}.txt",
                        "cid": f"Qm{os.urandom(16).hex()}",
                    },
                }
            )

        result = {
            "success": True,
            "operation": "ai_vector_search",
            "timestamp": time.time(),
            "simulation_note": "AI/ML integration not available, using simulated response",
            "query": query,
            "results": results,
            "total_vectors_searched": 100,
            "search_time_ms": 8,
        }

        # Add any additional parameters from kwargs
        for key, value in kwargs_dict.items():
            if key not in ["filter", "embedding_model", "search_type", "timeout"]:
                result[key] = value

        return result
    elif not AI_ML_AVAILABLE and not allow_simulation:
        return {
            "success": False,
            "operation": "ai_vector_search",
            "timestamp": time.time(),
            "error": "AI/ML integration not available and simulation not allowed",
            "error_type": "IntegrationError",
            "query": query,
            "vector_index_cid": vector_index_cid,
        }

    # If AI/ML integration is available, use the real implementation
    try:
        # Create vector searcher
        searcher = ai_ml_integration.VectorSearch(self._kit)

        search_result = searcher.search(
            query=query,
            vector_index_cid=vector_index_cid,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
            **kwargs_dict,
        )

        return search_result

    except Exception as e:
        # Return error information
        return {
            "success": False,
            "operation": "ai_vector_search",
            "timestamp": time.time(),
            "error": str(e),
            "error_type": type(e).__name__,
            "query": query,
            "vector_index_cid": vector_index_cid,
        }
'''
    return enhanced_method

def enhance_ai_register_dataset(method_text: str) -> str:
    """Enhance the ai_register_dataset method with better simulation handling."""
    enhanced_method = '''def ai_register_dataset(
    self, 
    dataset_cid: str, 
    metadata: Dict[str, Any],
    *,
    pin: bool = True,
    add_to_index: bool = True,
    overwrite: bool = False,
    register_features: bool = False,
    verify_existence: bool = False,
    allow_simulation: bool = True,
    **kwargs
) -> Dict[str, Any]:
    """
    Register a dataset with metadata in the IPFS Kit registry.

    Args:
        dataset_cid: CID of the dataset to register
        metadata: Dictionary of metadata about the dataset including:
            - name: Name of the dataset (required)
            - description: Description of the dataset
            - features: List of feature names
            - target: Target column name (for supervised learning)
            - rows: Number of rows
            - columns: Number of columns
            - created_at: Timestamp of creation
            - tags: List of tags for categorization
            - license: License information
            - source: Original source of the dataset
            - maintainer: Person or organization maintaining the dataset
        pin: Whether to pin the dataset content to ensure persistence
        add_to_index: Whether to add the dataset to the searchable index
        overwrite: Whether to overwrite existing metadata if dataset is already registered
        register_features: Whether to register dataset features for advanced querying
        verify_existence: Whether to verify the dataset exists before registering
        allow_simulation: Whether to allow simulated results when AI/ML integration is unavailable
        **kwargs: Additional parameters for advanced configuration

    Returns:
        Dict[str, Any]: Dictionary containing operation results with these keys:
            - "success": bool indicating if the operation succeeded
            - "operation": "ai_register_dataset"
            - "dataset_cid": CID of the registered dataset
            - "metadata_cid": CID of the stored metadata
            - "timestamp": Time of registration
            - "features_indexed": Whether features were indexed (if requested)
            - "simulation_note": (optional) Note about simulation if result is simulated
            - "fallback": (optional) True if using fallback implementation
            - "error": (optional) Error message if operation partially failed

    Raises:
        ValueError: If required metadata fields are missing
        IPFSError: If the dataset or metadata cannot be stored in IPFS
    """
    import time
    from . import validation

    # Update kwargs with explicit parameters
    kwargs_with_defaults = {
        "pin": pin,
        "add_to_index": add_to_index,
        "overwrite": overwrite,
        "register_features": register_features,
        "verify_existence": verify_existence,
        **kwargs  # Any additional kwargs override the defaults
    }

    # Validate dataset_cid
    if not dataset_cid:
        return {
            "success": False,
            "operation": "ai_register_dataset",
            "timestamp": time.time(),
            "error": "Dataset CID cannot be empty",
            "error_type": "ValidationError"
        }

    # Validate metadata
    required_fields = ["name"]
    for field in required_fields:
        if field not in metadata:
            raise ValueError(f"Required field '{field}' missing from metadata")

    # Verify dataset existence if requested
    if verify_existence:
        try:
            # Check if the dataset CID resolves
            verify_result = self.kit.ipfs_stat(dataset_cid)
            if not verify_result.get("success", False):
                return {
                    "success": False,
                    "operation": "ai_register_dataset",
                    "timestamp": time.time(),
                    "error": f"Dataset CID cannot be resolved: {dataset_cid}",
                    "error_type": "IPFSContentNotFoundError"
                }
        except Exception as e:
            return {
                "success": False,
                "operation": "ai_register_dataset",
                "timestamp": time.time(),
                "error": f"Failed to verify dataset existence: {str(e)}",
                "error_type": type(e).__name__
            }

    # Check if AI/ML integration is available
    if not AI_ML_AVAILABLE:
        # Only proceed with fallback if simulation is allowed
        if not allow_simulation:
            return {
                "success": False,
                "operation": "ai_register_dataset",
                "timestamp": time.time(),
                "error": "AI/ML integration not available and simulation not allowed",
                "error_type": "ModuleNotFoundError"
            }

        # Fallback to simple metadata registration without advanced features
        logger.warning("AI/ML integration not available, using fallback implementation")
        
        # Generate a simulated metadata CID
        metadata_cid = f"Qm{os.urandom(16).hex()}"
        
        # Create simulated metadata statistics
        num_features = len(metadata.get("features", []))
        num_rows = metadata.get("rows", 1000)  # Default to 1000 rows for simulation
        
        result = {
            "success": True,
            "operation": "ai_register_dataset",
            "dataset_cid": dataset_cid,
            "metadata_cid": metadata_cid,
            "timestamp": time.time(),
            "features_indexed": False,
            "simulation_note": "AI/ML integration not available, using simulated response",
            "fallback": True,
            "dataset_name": metadata.get("name", "Simulated dataset"),
            "dataset_stats": {
                "feature_count": num_features,
                "row_count": num_rows,
                "column_count": num_features + 1,  # Add one for potential target column
                "indexed_properties": [],
                "data_types": {
                    "numeric": int(num_features * 0.6),
                    "categorical": int(num_features * 0.3),
                    "datetime": int(num_features * 0.1)
                }
            }
        }

        # Add pinning information if requested
        if pin:
            result["pinned"] = True
            result["pin_status"] = "simulated"

        return result

    # Use the AI/ML integration module
    try:
        dataset_manager = self.kit.dataset_manager
        if dataset_manager is None:
            dataset_manager = ai_ml_integration.DatasetManager(self.kit)
            self.kit.dataset_manager = dataset_manager

        # Forward allow_simulation parameter to the dataset_manager
        kwargs_with_defaults["allow_simulation"] = allow_simulation
        
        result = dataset_manager.register_dataset(dataset_cid, metadata, **kwargs_with_defaults)
        return result
    except Exception as e:
        # Only use fallback implementation if simulation is allowed
        if not allow_simulation:
            return {
                "success": False,
                "operation": "ai_register_dataset",
                "timestamp": time.time(),
                "error": f"Error in AI/ML integration: {str(e)}",
                "error_type": type(e).__name__
            }
            
        # Fallback to simulation on error
        logger.error(f"Error registering dataset with AI/ML integration: {str(e)}")

        # Generate a simulated metadata CID
        metadata_cid = f"Qm{os.urandom(16).hex()}"
        
        # Create simulated metadata statistics
        num_features = len(metadata.get("features", []))
        num_rows = metadata.get("rows", 1000)  # Default to 1000 rows for simulation
        
        return {
            "success": True,
            "operation": "ai_register_dataset",
            "dataset_cid": dataset_cid,
            "metadata_cid": metadata_cid,
            "timestamp": time.time(),
            "features_indexed": False,
            "simulation_note": "AI/ML integration error, using simulated response",
            "fallback": True,
            "error": str(e),
            "error_type": type(e).__name__,
            "dataset_name": metadata.get("name", "Simulated dataset"),
            "dataset_stats": {
                "feature_count": num_features,
                "row_count": num_rows,
                "column_count": num_features + 1,  # Add one for potential target column
                "indexed_properties": [],
                "data_types": {
                    "numeric": int(num_features * 0.6),
                    "categorical": int(num_features * 0.3),
                    "datetime": int(num_features * 0.1)
                }
            }
        }
'''
    return enhanced_method

def enhance_ai_list_models(method_text: str) -> str:
    """Enhance the ai_list_models method with better simulation handling."""
    enhanced_method = '''def ai_list_models(
    self,
    *,
    framework: Optional[str] = None,
    tags: Optional[List[str]] = None,
    limit: int = 100,
    offset: int = 0,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    include_metrics: bool = False,
    only_local: bool = False,
    allow_simulation: bool = True,
    **kwargs
) -> Dict[str, Any]:
    """
    List machine learning models available in the system.
    
    This method retrieves a list of models from the model registry
    based on the specified filters and sorting parameters.
    
    Args:
        framework: Filter by machine learning framework (e.g., "pytorch", "tensorflow", "sklearn")
        tags: Filter by one or more tags
        limit: Maximum number of models to return
        offset: Number of models to skip (for pagination)
        sort_by: Field to sort by (e.g., "created_at", "name", "framework")
        sort_order: Sort direction, either "asc" or "desc"
        include_metrics: Whether to include performance metrics in the results
        only_local: Whether to include only locally available models
        allow_simulation: Whether to allow simulated results when AI/ML integration is unavailable
        **kwargs: Additional filter parameters
    
    Returns:
        Dict[str, Any]: Dictionary containing operation results with these keys:
            - "success": bool indicating if the operation succeeded
            - "operation": Name of the operation ("ai_list_models")
            - "timestamp": Time when the operation was performed
            - "models": List of model metadata dictionaries
            - "total_count": Total number of models matching the filters (before pagination)
            - "error": Error message if operation failed (only present on failure)
            - "error_type": Type of error if operation failed (only present on failure)
    """
    import time

    # Update kwargs with explicit parameters
    kwargs_with_defaults = {}
    if framework:
        kwargs_with_defaults["framework"] = framework
    if tags:
        kwargs_with_defaults["tags"] = tags
    kwargs_with_defaults["limit"] = limit
    kwargs_with_defaults["offset"] = offset
    kwargs_with_defaults["sort_by"] = sort_by
    kwargs_with_defaults["sort_order"] = sort_order
    kwargs_with_defaults["include_metrics"] = include_metrics
    kwargs_with_defaults["only_local"] = only_local
    
    # Add any additional kwargs
    kwargs_with_defaults.update(kwargs)
    
    # Check if AI/ML integration is available
    if not AI_ML_AVAILABLE:
        if not allow_simulation:
            return {
                "success": False,
                "operation": "ai_list_models",
                "timestamp": time.time(),
                "error": "AI/ML integration not available and simulation not allowed",
                "error_type": "ModuleNotFoundError"
            }
            
        # Simulate model list
        models = []
        total_models = min(limit + offset, 25)  # Simulate at most 25 models
        
        # Create simulated models
        frameworks = ["pytorch", "tensorflow", "sklearn", "onnx", "keras"]
        model_types = ["classification", "regression", "segmentation", "detection", "nlp", "timeseries"]
        architectures = ["resnet", "bert", "gpt", "transformer", "lstm", "vgg", "mobilenet", "efficientnet"]
        
        for i in range(offset, min(offset + limit, total_models)):
            # Use deterministic values based on index to create realistic simulation
            model_idx = i % 25
            framework_idx = model_idx % len(frameworks)
            framework_name = frameworks[framework_idx]
            model_type = model_types[model_idx % len(model_types)]
            architecture = architectures[model_idx % len(architectures)]
            
            # Generate model metadata
            model = {
                "cid": f"Qm{os.urandom(16).hex()}",
                "name": f"{architecture}_{model_type}_{model_idx}",
                "framework": framework_name,
                "version": f"1.{model_idx}.0",
                "created_at": time.time() - (model_idx * 86400),  # Each model created 1 day apart
                "updated_at": time.time() - (model_idx * 43200),  # Last update half as old as creation
                "tags": [model_type, architecture, framework_name],
                "size_bytes": 10000000 + (model_idx * 1000000),  # 10MB + increments
                "is_local": model_idx < 10,  # First 10 are local
                "description": f"Simulated {architecture} model for {model_type} using {framework_name}"
            }
            
            # Add metrics if requested
            if include_metrics:
                model["metrics"] = {
                    "accuracy": 0.85 + ((25 - model_idx) / 100),  # Higher index, slightly lower accuracy
                    "latency_ms": 100 + (model_idx * 10),
                    "parameters": 1000000 + (model_idx * 100000),
                    "memory_mb": 50 + (model_idx * 5)
                }
                
            # Add hyperparameters
            model["hyperparameters"] = {
                "learning_rate": 0.001,
                "batch_size": 32 * (1 + (model_idx % 4)),
                "epochs": 10 + (model_idx % 5),
                "optimizer": ["adam", "sgd", "rmsprop"][model_idx % 3]
            }
            
            models.append(model)
        
        # Apply framework filter if specified
        if framework:
            models = [m for m in models if m["framework"] == framework]
            
        # Apply tags filter if specified
        if tags:
            filtered_models = []
            for model in models:
                if all(tag in model["tags"] for tag in tags):
                    filtered_models.append(model)
            models = filtered_models
            
        # Apply only_local filter if specified
        if only_local:
            models = [m for m in models if m.get("is_local", False)]
            
        # Return the simulated model list
        return {
            "success": True,
            "operation": "ai_list_models",
            "timestamp": time.time(),
            "simulation_note": "AI/ML integration not available, using simulated response",
            "models": models,
            "total_count": len(models),
            "filters_applied": {
                "framework": framework,
                "tags": tags,
                "only_local": only_local
            },
            "pagination": {
                "limit": limit,
                "offset": offset,
                "sort_by": sort_by,
                "sort_order": sort_order
            }
        }
    
    # If AI/ML integration is available, use the real implementation
    try:
        model_manager = self.kit.model_manager
        if model_manager is None:
            model_manager = ai_ml_integration.ModelManager(self.kit)
            self.kit.model_manager = model_manager
        
        result = model_manager.list_models(**kwargs_with_defaults)
        return result
        
    except Exception as e:
        # Return error information
        return {
            "success": False,
            "operation": "ai_list_models",
            "timestamp": time.time(),
            "error": str(e),
            "error_type": type(e).__name__
        }
'''
    return enhanced_method

def create_ai_create_knowledge_graph() -> str:
    """Create the ai_create_knowledge_graph method with keyword-only parameters and type annotations."""
    method = '''def ai_create_knowledge_graph(
    self,
    source_data_cid: str,
    *,
    graph_name: str = "knowledge_graph",
    extraction_model: Optional[str] = None,
    entity_types: Optional[List[str]] = None,
    relationship_types: Optional[List[str]] = None,
    max_entities: int = 1000,
    include_text_context: bool = True,
    extract_metadata: bool = True,
    allow_simulation: bool = True,
    save_intermediate_results: bool = False,
    timeout: int = 120,
    **kwargs
) -> Dict[str, Any]:
    """
    Create a knowledge graph from source data.

    This method extracts entities and relationships from source data and 
    creates a structured knowledge graph stored in IPLD format. The resulting
    graph can be used for semantic search, reasoning, and data exploration.

    Args:
        source_data_cid: CID of the source data to process (document, dataset, etc.)
        graph_name: Name to assign to the created knowledge graph
        extraction_model: Optional name/type of model to use for entity extraction 
            (if None, uses the default model appropriate for the content type)
        entity_types: List of entity types to extract (e.g., ["Person", "Organization", "Location"])
        relationship_types: List of relationship types to extract (e.g., ["worksFor", "locatedIn"])
        max_entities: Maximum number of entities to extract
        include_text_context: Whether to include source text context with entities
        extract_metadata: Whether to extract metadata from source data
        allow_simulation: Whether to allow simulated results when AI/ML integration is unavailable
        save_intermediate_results: Whether to save intermediate extraction results as separate CIDs
        timeout: Operation timeout in seconds
        **kwargs: Additional extraction parameters

    Returns:
        Dict[str, Any]: Dictionary containing operation results with these keys:
            - "success": bool indicating if the operation succeeded
            - "operation": "ai_create_knowledge_graph"
            - "timestamp": Time when the operation was performed
            - "graph_cid": CID of the created knowledge graph
            - "graph_name": Name of the created graph
            - "entities": List of extracted entities with their properties
            - "relationships": List of extracted relationships
            - "entity_count": Total number of extracted entities
            - "relationship_count": Total number of extracted relationships
            - "source_data_cid": Original source data CID
            - "processing_time_ms": Total processing time in milliseconds
            - "intermediate_results_cid": CID of intermediate results (if save_intermediate_results=True)
            - "simulation_note": Note about simulation if result is simulated
            - "error": Error message if operation failed (only present on failure)
            - "error_type": Type of error if operation failed (only present on failure)
    """
    import time
    import uuid
    from . import validation

    # Build kwargs dictionary with explicit parameters
    kwargs_dict = {
        "graph_name": graph_name,
        "max_entities": max_entities,
        "include_text_context": include_text_context,
        "extract_metadata": extract_metadata,
        "save_intermediate_results": save_intermediate_results,
        "timeout": timeout
    }
    
    # Add optional parameters if provided
    if extraction_model is not None:
        kwargs_dict["extraction_model"] = extraction_model
    if entity_types is not None:
        kwargs_dict["entity_types"] = entity_types
    if relationship_types is not None:
        kwargs_dict["relationship_types"] = relationship_types
        
    # Add any additional kwargs
    kwargs_dict.update(kwargs)
    
    # Validate parameters
    validation.validate_parameters(
        kwargs_dict,
        {
            "graph_name": {"type": str, "default": "knowledge_graph"},
            "extraction_model": {"type": str},
            "entity_types": {"type": list},
            "relationship_types": {"type": list},
            "max_entities": {"type": int, "default": 1000},
            "include_text_context": {"type": bool, "default": True},
            "extract_metadata": {"type": bool, "default": True},
            "save_intermediate_results": {"type": bool, "default": False},
            "timeout": {"type": int, "default": 120}
        }
    )
    
    # Validate source_data_cid
    if not source_data_cid:
        return {
            "success": False,
            "operation": "ai_create_knowledge_graph",
            "timestamp": time.time(),
            "error": "Source data CID cannot be empty",
            "error_type": "ValidationError"
        }

    # Check if AI/ML integration is available
    if not AI_ML_AVAILABLE and allow_simulation:
        # Fallback to simulation for demonstration
        start_time = time.time()
        
        # Generate simulated entity types if not provided
        sim_entity_types = entity_types or ["Person", "Organization", "Location", "Event", "Topic", "Product"]
        
        # Generate simulated relationship types if not provided
        sim_relationship_types = relationship_types or ["relatedTo", "partOf", "hasProperty", "locatedIn", "createdBy"]
        
        # Simulate processing delay
        time.sleep(0.5)
        
        # Generate simulated entities
        entities = []
        entity_ids = []
        
        for i in range(min(max_entities, 25)):  # Simulate up to 25 entities
            entity_type = sim_entity_types[i % len(sim_entity_types)]
            entity_id = f"{entity_type.lower()}_{i}"
            entity_ids.append(entity_id)
            
            # Create entity with appropriate properties based on type
            if entity_type == "Person":
                entity = {
                    "id": entity_id,
                    "type": entity_type,
                    "name": f"Person {i}",
                    "properties": {
                        "occupation": ["Researcher", "Engineer", "Scientist"][i % 3],
                        "expertise": ["AI", "Blockchain", "Distributed Systems"][i % 3]
                    }
                }
            elif entity_type == "Organization":
                entity = {
                    "id": entity_id,
                    "type": entity_type,
                    "name": f"Organization {i}",
                    "properties": {
                        "industry": ["Technology", "Research", "Education"][i % 3],
                        "size": ["Small", "Medium", "Large"][i % 3]
                    }
                }
            elif entity_type == "Location":
                entity = {
                    "id": entity_id,
                    "type": entity_type,
                    "name": f"Location {i}",
                    "properties": {
                        "region": ["North", "South", "East", "West"][i % 4],
                        "type": ["City", "Building", "Country"][i % 3]
                    }
                }
            else:
                entity = {
                    "id": entity_id,
                    "type": entity_type,
                    "name": f"{entity_type} {i}",
                    "properties": {
                        "relevance": 0.9 - (i * 0.02),
                        "mentions": i + 1
                    }
                }
                
            # Add text context if requested
            if include_text_context:
                entity["context"] = f"This is a sample text mentioning {entity['name']} in the source document."
                
            entities.append(entity)
            
        # Generate simulated relationships
        relationships = []
        for i in range(min(max_entities * 2, 50)):  # Simulate up to 50 relationships
            # Ensure we have at least 2 entities to create relationships
            if len(entity_ids) < 2:
                continue
                
            # Get random source and target entities (ensure they're different)
            source_idx = i % len(entity_ids)
            target_idx = (i + 1 + (i % 3)) % len(entity_ids)  # Ensure different from source
            
            relationship_type = sim_relationship_types[i % len(sim_relationship_types)]
            
            relationship = {
                "id": f"rel_{i}",
                "type": relationship_type,
                "source": entity_ids[source_idx],
                "target": entity_ids[target_idx],
                "properties": {
                    "confidence": 0.9 - (i * 0.01),
                    "weight": i % 10
                }
            }
            
            # Add text context if requested
            if include_text_context:
                source_name = entities[source_idx]["name"]
                target_name = entities[target_idx]["name"]
                relationship["context"] = f"This is evidence that {source_name} is {relationship_type} {target_name}."
                
            relationships.append(relationship)
            
        # Create simulated graph CID
        graph_cid = f"Qm{os.urandom(16).hex()}"
        
        # Create intermediate results CID if requested
        intermediate_results_cid = None
        if save_intermediate_results:
            intermediate_results_cid = f"Qm{os.urandom(16).hex()}"
            
        # Calculate processing time
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        # Return simulated results
        result = {
            "success": True,
            "operation": "ai_create_knowledge_graph",
            "timestamp": time.time(),
            "simulation_note": "AI/ML integration not available, using simulated response",
            "graph_cid": graph_cid,
            "graph_name": graph_name,
            "entities": entities[:5],  # Just include first 5 for brevity
            "relationships": relationships[:5],  # Just include first 5 for brevity
            "entity_count": len(entities),
            "relationship_count": len(relationships),
            "source_data_cid": source_data_cid,
            "processing_time_ms": processing_time_ms
        }
        
        # Add intermediate results if requested
        if save_intermediate_results:
            result["intermediate_results_cid"] = intermediate_results_cid
            
        # Add entity and relationship type counts
        result["entity_types"] = {
            entity_type: len([e for e in entities if e["type"] == entity_type])
            for entity_type in set(e["type"] for e in entities)
        }
        
        result["relationship_types"] = {
            rel_type: len([r for r in relationships if r["type"] == rel_type])
            for rel_type in set(r["type"] for r in relationships)
        }
        
        return result
        
    elif not AI_ML_AVAILABLE and not allow_simulation:
        return {
            "success": False,
            "operation": "ai_create_knowledge_graph",
            "timestamp": time.time(),
            "error": "AI/ML integration not available and simulation not allowed",
            "error_type": "IntegrationError",
            "source_data_cid": source_data_cid
        }

    # If AI/ML integration is available, use the real implementation
    try:
        # Create knowledge graph manager
        kg_manager = ai_ml_integration.KnowledgeGraphManager(self.kit)
        
        # Create knowledge graph
        result = kg_manager.create_knowledge_graph(
            source_data_cid=source_data_cid,
            **kwargs_dict
        )
        
        return result
        
    except Exception as e:
        # Return error information
        return {
            "success": False,
            "operation": "ai_create_knowledge_graph",
            "timestamp": time.time(),
            "error": str(e),
            "error_type": type(e).__name__,
            "source_data_cid": source_data_cid
        }
'''
    return method

def create_ai_test_inference() -> str:
    """Create the ai_test_inference method with keyword-only parameters and type annotations."""
    method = '''def ai_test_inference(
    self,
    model_cid: str,
    test_data_cid: str,
    *,
    batch_size: int = 32,
    max_samples: Optional[int] = None,
    compute_metrics: bool = True,
    metrics: Optional[List[str]] = None,
    output_format: Literal["json", "csv", "parquet"] = "json",
    save_predictions: bool = True,
    device: Optional[str] = None,
    precision: Literal["float32", "float16", "bfloat16"] = "float32",
    allow_simulation: bool = True,
    timeout: int = 300,
    **kwargs
) -> Dict[str, Any]:
    """
    Run inference on a test dataset using a model and evaluate performance.
    
    This method loads a model and test dataset, performs inference, 
    computes evaluation metrics, and optionally saves the predictions.
    
    Args:
        model_cid: CID of the model to use for inference
        test_data_cid: CID of the test dataset
        batch_size: Batch size for inference
        max_samples: Maximum number of samples to use (None for all)
        compute_metrics: Whether to compute evaluation metrics
        metrics: List of metrics to compute (e.g., ["accuracy", "precision", "recall", "f1"])
        output_format: Format for prediction output ("json", "csv", "parquet")
        save_predictions: Whether to save predictions to IPFS
        device: Device to run inference on ("cpu", "cuda", "cuda:0", etc.)
        precision: Numerical precision for inference
        allow_simulation: Whether to allow simulated results when AI/ML integration is unavailable
        timeout: Operation timeout in seconds
        **kwargs: Additional parameters for inference
    
    Returns:
        Dict[str, Any]: Dictionary containing operation results with these keys:
            - "success": bool indicating if the operation succeeded
            - "operation": "ai_test_inference"
            - "timestamp": Time when the operation was performed
            - "model_cid": CID of the model used
            - "test_data_cid": CID of the test dataset used
            - "metrics": Dictionary of computed metrics
            - "predictions_cid": CID of saved predictions (if save_predictions=True)
            - "samples_processed": Number of samples processed
            - "sample_predictions": Small sample of predictions for preview
            - "processing_time_ms": Total processing time in milliseconds
            - "inference_time_per_sample_ms": Average inference time per sample
            - "simulation_note": Note about simulation if result is simulated
            - "error": Error message if operation failed (only present on failure)
            - "error_type": Type of error if operation failed (only present on failure)
    """
    import time
    import random
    import math
    import json
    import uuid
    from . import validation
    
    # Validate required parameters
    if not model_cid:
        return {
            "success": False,
            "operation": "ai_test_inference",
            "timestamp": time.time(),
            "error": "Model CID cannot be empty",
            "error_type": "ValidationError"
        }
    
    if not test_data_cid:
        return {
            "success": False,
            "operation": "ai_test_inference",
            "timestamp": time.time(),
            "error": "Test data CID cannot be empty",
            "error_type": "ValidationError"
        }
    
    # Build kwargs dictionary with explicit parameters
    kwargs_dict = {
        "batch_size": batch_size,
        "compute_metrics": compute_metrics,
        "output_format": output_format,
        "save_predictions": save_predictions,
        "precision": precision,
        "timeout": timeout
    }
    
    # Add optional parameters if provided
    if max_samples is not None:
        kwargs_dict["max_samples"] = max_samples
    if metrics is not None:
        kwargs_dict["metrics"] = metrics
    if device is not None:
        kwargs_dict["device"] = device
    
    # Add any additional kwargs
    kwargs_dict.update(kwargs)
    
    # Validate parameters
    validation.validate_parameters(
        kwargs_dict,
        {
            "batch_size": {"type": int, "default": 32},
            "max_samples": {"type": int},
            "compute_metrics": {"type": bool, "default": True},
            "metrics": {"type": list},
            "output_format": {"type": str, "default": "json"},
            "save_predictions": {"type": bool, "default": True},
            "device": {"type": str},
            "precision": {"type": str, "default": "float32"},
            "timeout": {"type": int, "default": 300}
        }
    )
    
    # Validate output format
    valid_formats = ["json", "csv", "parquet"]
    if output_format not in valid_formats:
        return {
            "success": False,
            "operation": "ai_test_inference",
            "timestamp": time.time(),
            "error": f"Invalid output format: {output_format}. Valid formats: {', '.join(valid_formats)}",
            "error_type": "ValidationError"
        }
    
    # Check if AI/ML integration is available
    if not AI_ML_AVAILABLE and allow_simulation:
        # Fallback to simulation for demonstration
        start_time = time.time()
        
        # Simulate processing delay
        processing_delay = random.uniform(0.5, 2.0)
        time.sleep(processing_delay)
        
        # Simulate number of samples
        num_samples = max_samples if max_samples is not None else random.randint(100, 1000)
        
        # Simulate metrics
        default_metrics = ["accuracy", "precision", "recall", "f1"]
        metric_names = metrics if metrics else default_metrics
        
        simulated_metrics = {}
        for metric in metric_names:
            # Generate realistic metric values
            if metric == "accuracy":
                simulated_metrics[metric] = round(random.uniform(0.82, 0.96), 4)
            elif metric == "precision":
                simulated_metrics[metric] = round(random.uniform(0.80, 0.95), 4)
            elif metric == "recall":
                simulated_metrics[metric] = round(random.uniform(0.75, 0.92), 4)
            elif metric == "f1":
                # Make F1 consistent with precision and recall if both exist
                if "precision" in simulated_metrics and "recall" in simulated_metrics:
                    p = simulated_metrics["precision"]
                    r = simulated_metrics["recall"]
                    simulated_metrics[metric] = round(2 * p * r / (p + r), 4)
                else:
                    simulated_metrics[metric] = round(random.uniform(0.78, 0.94), 4)
            else:
                # Generic metric
                simulated_metrics[metric] = round(random.uniform(0.7, 0.98), 4)
        
        # Add confusion matrix if requested
        if "confusion_matrix" in metric_names:
            # Simplified 2-class confusion matrix for simulation
            true_pos = int(num_samples * 0.8)
            false_pos = int(num_samples * 0.05)
            false_neg = int(num_samples * 0.10)
            true_neg = num_samples - true_pos - false_pos - false_neg
            
            simulated_metrics["confusion_matrix"] = [
                [true_pos, false_neg],
                [false_pos, true_neg]
            ]
        
        # Simulate predictions
        sample_predictions = []
        for i in range(min(5, num_samples)):  # Show at most 5 sample predictions
            # For classification
            if "classes" in kwargs:
                classes = kwargs["classes"]
                prediction = {
                    "sample_id": i,
                    "prediction": random.choice(classes),
                    "probabilities": {
                        cls: round(random.random(), 4) for cls in classes
                    }
                }
            # For regression
            else:
                prediction = {
                    "sample_id": i,
                    "prediction": round(random.uniform(0, 100), 2)
                }
            
            sample_predictions.append(prediction)
        
        # Generate CID for predictions if saving
        predictions_cid = None
        if save_predictions:
            predictions_cid = f"Qm{os.urandom(16).hex()}"
        
        # Calculate processing time
        processing_time_ms = int((time.time() - start_time) * 1000)
        inference_time_per_sample_ms = round(processing_time_ms / num_samples, 2)
        
        # Return simulated results
        result = {
            "success": True,
            "operation": "ai_test_inference",
            "timestamp": time.time(),
            "simulation_note": "AI/ML integration not available, using simulated response",
            "model_cid": model_cid,
            "test_data_cid": test_data_cid,
            "metrics": simulated_metrics,
            "samples_processed": num_samples,
            "sample_predictions": sample_predictions,
            "processing_time_ms": processing_time_ms,
            "inference_time_per_sample_ms": inference_time_per_sample_ms,
            "batch_size": batch_size
        }
        
        # Add predictions CID if saving
        if save_predictions and predictions_cid:
            result["predictions_cid"] = predictions_cid
            
        # Add device info if provided
        if device:
            result["device"] = device
            
        return result
        
    elif not AI_ML_AVAILABLE and not allow_simulation:
        return {
            "success": False,
            "operation": "ai_test_inference",
            "timestamp": time.time(),
            "error": "AI/ML integration not available and simulation not allowed",
            "error_type": "IntegrationError",
            "model_cid": model_cid,
            "test_data_cid": test_data_cid
        }
    
    # If AI/ML integration is available, use the real implementation
    try:
        # Create inference manager
        inference_manager = ai_ml_integration.InferenceManager(self.kit)
        
        # Run inference
        result = inference_manager.run_inference(
            model_cid=model_cid,
            test_data_cid=test_data_cid,
            **kwargs_dict
        )
        
        return result
        
    except Exception as e:
        # Return error information
        return {
            "success": False,
            "operation": "ai_test_inference",
            "timestamp": time.time(),
            "error": str(e),
            "error_type": type(e).__name__,
            "model_cid": model_cid,
            "test_data_cid": test_data_cid
        }
'''
    return method

def find_methods_in_content(content: str) -> Dict[str, Tuple[int, int]]:
    """Find all AI method definitions in the content and return their locations."""
    methods = {}
    method_pattern = r'def (ai_[a-zA-Z0-9_]+)\s*\('
    for match in re.finditer(method_pattern, content):
        method_name = match.group(1)
        start_idx = match.start()
        
        # Find the method body by tracking its end
        _, end_idx, _ = find_method(content, method_name)
        if end_idx > start_idx:
            methods[method_name] = (start_idx, end_idx)
    
    return methods

def get_last_method_end_position(content: str) -> int:
    """Find the end position of the last method in the class."""
    methods = find_methods_in_content(content)
    
    if not methods:
        # If no methods found, return -1
        return -1
    
    # Find the last method by end position
    last_method_name = max(methods.keys(), key=lambda name: methods[name][1])
    _, last_method_end = methods[last_method_name]
    
    return last_method_end

def add_new_methods(file_path: str, backup_suffix: str = ".bak.3") -> None:
    """Add new AI/ML methods to high_level_api.py."""
    # Read the file content
    content = read_file(file_path)
    
    # Create a backup
    backup_path = f"{file_path}{backup_suffix}"
    write_file(backup_path, content)
    print(f"Backed up original file to {backup_path}")
    
    # Find existing methods
    existing_methods = find_methods_in_content(content)
    
    # Check if the methods already exist
    if "ai_create_knowledge_graph" in existing_methods:
        print("Method ai_create_knowledge_graph already exists, will enhance it")
    else:
        print("Will add new method: ai_create_knowledge_graph")
        
    if "ai_test_inference" in existing_methods:
        print("Method ai_test_inference already exists, will enhance it")
    else:
        print("Will add new method: ai_test_inference")
    
    # Prepare new methods
    ai_create_knowledge_graph_method = create_ai_create_knowledge_graph()
    ai_test_inference_method = create_ai_test_inference()
    
    # Find where to add the new methods - after the last existing method
    last_method_end = get_last_method_end_position(content)
    
    if last_method_end == -1:
        print("Could not find where to add the new methods, aborting")
        return
    
    # Add the new methods after the last existing method
    updated_content = (
        content[:last_method_end] + 
        "\n\n" + ai_create_knowledge_graph_method + 
        "\n\n" + ai_test_inference_method + 
        content[last_method_end:]
    )
    
    # Write the updated content
    write_file(file_path, updated_content)
    print(f"Added new methods to {file_path}")

def main():
    """Main function to enhance methods in high_level_api.py."""
    filepath = '/home/barberb/ipfs_kit_py/ipfs_kit_py/high_level_api.py'
    
    # Backup and add the new methods
    add_new_methods(filepath)
    
    # Add existing enhancement methods with our new ones
    methods_to_enhance = {
        'ai_vector_search': enhance_ai_vector_search,
        'ai_register_dataset': enhance_ai_register_dataset,
        'ai_list_models': enhance_ai_list_models,
        'ai_create_knowledge_graph': lambda _: create_ai_create_knowledge_graph(),
        'ai_test_inference': lambda _: create_ai_test_inference(),
    }
    
    # Read the file again (now with our new methods added)
    content = read_file(filepath)
    backup_filepath = f"{filepath}.bak.enhanced"
    write_file(backup_filepath, content)
    
    # Track methods that were successfully enhanced
    enhanced_methods = []
    
    # Enhance each method
    for method_name, enhance_func in methods_to_enhance.items():
        start_idx, end_idx, method_text = find_method(content, method_name)
        
        if start_idx == -1:
            print(f"Could not find method {method_name}")
            continue
        
        print(f"Enhancing method {method_name} (found at position {start_idx})")
        enhanced_method = enhance_func(method_text)
        content = content[:start_idx] + enhanced_method + content[end_idx:]
        enhanced_methods.append(method_name)
    
    # Write the enhanced content to the original file
    write_file(filepath, content)
    print(f"Enhanced {len(enhanced_methods)} methods in {filepath}: {', '.join(enhanced_methods)}")

if __name__ == '__main__':
    main()
