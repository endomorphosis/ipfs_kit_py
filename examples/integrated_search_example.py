"""
Example demonstrating the integrated search capabilities of IPFS Kit.

This example shows how to use the integrated search functionality that combines
the Arrow metadata index with the GraphRAG system for powerful hybrid search
and the integration with AI/ML frameworks.
"""

import sys
import os
import time
import numpy as np
from typing import Dict, Any, List

# Add parent directory to path for direct execution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import the high-level API and AI/ML integration
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

# Try to import the integrated search components directly for advanced usage
try:
    from ipfs_kit_py.integrated_search import MetadataEnhancedGraphRAG, AIMLSearchConnector
    ADVANCED_SEARCH_AVAILABLE = True
except ImportError:
    ADVANCED_SEARCH_AVAILABLE = False

def setup_example_data(api):
    """Set up example data for the search demonstration."""
    print("Setting up example data...")

    # Create some machine learning models with different characteristics

    # ResNet model for image classification
    resnet_model = {
        "weights": np.random.rand(10, 10).tolist(),
        "config": {
            "name": "ResNet50",
            "layers": 50
        }
    }

    resnet_metadata = {
        "name": "ResNet50",
        "version": "1.0.0",
        "task": "image-classification",
        "framework": "pytorch",
        "dataset": "ImageNet",
        "accuracy": 0.76,
        "tags": ["computer-vision", "classification", "resnet"],
        "description": "Deep residual network for image classification"
    }

    # BERT model for NLP
    bert_model = {
        "weights": np.random.rand(10, 10).tolist(),
        "config": {
            "name": "BERT-base",
            "layers": 12
        }
    }

    bert_metadata = {
        "name": "BERT-base",
        "version": "1.0.0",
        "task": "text-embedding",
        "framework": "tensorflow",
        "dataset": "BookCorpus",
        "accuracy": 0.82,
        "tags": ["nlp", "transformer", "embedding"],
        "description": "Bidirectional encoder for text representation"
    }

    # ViT model for vision transformers
    vit_model = {
        "weights": np.random.rand(10, 10).tolist(),
        "config": {
            "name": "ViT-B/16",
            "patch_size": 16
        }
    }

    vit_metadata = {
        "name": "ViT-B/16",
        "version": "1.0.0",
        "task": "image-classification",
        "framework": "pytorch",
        "dataset": "ImageNet",
        "accuracy": 0.81,
        "tags": ["computer-vision", "transformer", "classification"],
        "description": "Vision Transformer model using patch-based approach"
    }

    # Add models to IPFS
    print("Adding models to IPFS...")
    resnet_result = api.ai_model_add(resnet_model, resnet_metadata)
    bert_result = api.ai_model_add(bert_model, bert_metadata)
    vit_result = api.ai_model_add(vit_model, vit_metadata)

    # Print results
    print(f"Added ResNet model with CID: {resnet_result.get('cid')}")
    print(f"Added BERT model with CID: {bert_result.get('cid')}")
    print(f"Added ViT model with CID: {vit_result.get('cid')}")

    # Create relationships between models (for graph traversal)
    # Note: In a real application, these relationships would be added through the graph DB
    print("Setting up relationships between models...")

    # This is a simplification - in a real app you'd use the graph DB directly
    # Here we're just simulating the relationships that would be traversed

    return {
        "resnet": resnet_result.get('cid'),
        "bert": bert_result.get('cid'),
        "vit": vit_result.get('cid')
    }

def demonstrate_metadata_search(api):
    """Demonstrate metadata-based search."""
    print("\n=== Metadata-based Search ===")

    # Search for PyTorch models
    print("\nSearching for PyTorch models:")
    results = api.hybrid_search(
        metadata_filters=[("framework", "==", "pytorch")]
    )

    if results.get("success", False):
        print(f"Found {results.get('result_count', 0)} results:")
        for idx, result in enumerate(results.get("results", []), 1):
            print(f"  {idx}. {result.get('properties', {}).get('name', 'Unknown')} " +
                  f"({result.get('id')})")
    else:
        print(f"Search failed: {results.get('error', 'Unknown error')}")

    # Search for classification models
    print("\nSearching for classification models:")
    results = api.hybrid_search(
        metadata_filters=[("tags", "contains", "classification")]
    )

    if results.get("success", False):
        print(f"Found {results.get('result_count', 0)} results:")
        for idx, result in enumerate(results.get("results", []), 1):
            print(f"  {idx}. {result.get('properties', {}).get('name', 'Unknown')} " +
                  f"({result.get('id')})")
    else:
        print(f"Search failed: {results.get('error', 'Unknown error')}")

def demonstrate_vector_search(api):
    """Demonstrate vector-based semantic search."""
    print("\n=== Vector-based Semantic Search ===")

    # Create a simple vector that should be closer to image classification models
    image_query_vector = np.array([0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.0, 0.0])

    print("\nSearching for models similar to image-related vector:")
    results = api.hybrid_search(
        query_vector=image_query_vector.tolist()
    )

    if results.get("success", False):
        print(f"Found {results.get('result_count', 0)} results:")
        for idx, result in enumerate(results.get("results", []), 1):
            print(f"  {idx}. {result.get('properties', {}).get('name', 'Unknown')} " +
                  f"(score: {result.get('score', 0):.4f})")
    else:
        print(f"Search failed: {results.get('error', 'Unknown error')}")

    # Text-based query
    print("\nSearching for 'transformer models for vision':")
    results = api.hybrid_search(
        query_text="transformer models for vision"
    )

    if results.get("success", False):
        print(f"Found {results.get('result_count', 0)} results:")
        for idx, result in enumerate(results.get("results", []), 1):
            print(f"  {idx}. {result.get('properties', {}).get('name', 'Unknown')} " +
                  f"(score: {result.get('score', 0):.4f})")
    else:
        print(f"Search failed: {results.get('error', 'Unknown error')}")

def demonstrate_hybrid_search(api):
    """Demonstrate hybrid search combining metadata and vectors."""
    print("\n=== Hybrid Search (Metadata + Vector) ===")

    # Search for PyTorch models similar to a vector
    image_query_vector = np.array([0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.0, 0.0])

    print("\nSearching for PyTorch models related to computer vision:")
    results = api.hybrid_search(
        query_vector=image_query_vector.tolist(),
        metadata_filters=[
            ("framework", "==", "pytorch"),
            ("tags", "contains", "computer-vision")
        ]
    )

    if results.get("success", False):
        print(f"Found {results.get('result_count', 0)} results:")
        for idx, result in enumerate(results.get("results", []), 1):
            print(f"  {idx}. {result.get('properties', {}).get('name', 'Unknown')} " +
                  f"(score: {result.get('score', 0):.4f})")
    else:
        print(f"Search failed: {results.get('error', 'Unknown error')}")

def demonstrate_llm_context_generation(api):
    """Demonstrate LLM context generation from search results."""
    print("\n=== LLM Context Generation ===")

    # Search with LLM context generation
    print("\nGenerating LLM context for query 'vision transformer models':")
    results = api.hybrid_search(
        query_text="vision transformer models",
        generate_llm_context=True,
        format_type="markdown"
    )

    if results.get("success", False):
        print("\nLLM Context:")
        print("------------")
        print(results.get("llm_context", "No context generated"))
    else:
        print(f"Search failed: {results.get('error', 'Unknown error')}")

def demonstrate_aiml_integration():
    """Demonstrate the AI/ML search connector functionality."""
    if not ADVANCED_SEARCH_AVAILABLE:
        print("\n=== AI/ML Integration Demonstration ===")
        print("Advanced search components not available.")
        return

    print("\n=== AI/ML Integration Demonstration ===")

    # Initialize IPFS Kit
    print("Initializing IPFS Kit with AI/ML integration...")
    api = IPFSSimpleAPI(role="worker")

    # Create AI/ML search connector
    connector = AIMLSearchConnector(api)

    # Set up example data if needed
    setup_example_data(api)

    # Wait a moment for indexing to complete
    print("Waiting for indexing to complete...")
    time.sleep(2)

    # Demonstrate model search
    print("\nSearching for PyTorch models for computer vision:")
    results = connector.search_models(
        query_text="computer vision transformer",
        framework="pytorch",
        min_accuracy=0.75
    )

    if results.get("success", False):
        print(f"Found {results.get('result_count', 0)} results:")
        for idx, result in enumerate(results.get("results", []), 1):
            print(f"  {idx}. {result.get('properties', {}).get('name', 'Unknown')} " +
                  f"(score: {result.get('score', 0):.4f})")
            # Print model-specific information
            if "model_info" in result:
                info = result["model_info"]
                print(f"     Task: {info.get('task', 'Unknown')}")
                print(f"     Accuracy: {info.get('accuracy', 'Unknown')}")
    else:
        print(f"Search failed: {results.get('error', 'Unknown error')}")

    # Demonstrate dataset search
    print("\nSearching for image datasets:")
    results = connector.search_datasets(
        query_text="image classification dataset",
        domain="vision"
    )

    if results.get("success", False):
        print(f"Found {results.get('result_count', 0)} results:")
        for idx, result in enumerate(results.get("results", []), 1):
            print(f"  {idx}. {result.get('properties', {}).get('name', 'Unknown')} " +
                  f"(score: {result.get('score', 0):.4f})")
    else:
        print(f"Search failed: {results.get('error', 'Unknown error')}")

    # Demonstrate Langchain integration
    print("\nCreating Langchain retriever with hybrid search:")
    try:
        retriever = connector.create_langchain_retriever(
            retriever_type="hybrid",
            metadata_filters=[("tags", "contains", "computer-vision")]
        )
        print("Successfully created Langchain retriever")

        # Example retriever usage
        print("\nRetrieving documents with query 'vision transformers':")
        docs = retriever.get_relevant_documents("vision transformers")
        print(f"Retrieved {len(docs)} documents")

        # Show first document
        if docs:
            print("\nFirst document:")
            print(f"Content: {docs[0]['page_content'][:100]}...")
            print("Metadata:")
            for key, value in docs[0]["metadata"].items():
                print(f"  {key}: {value}")
    except Exception as e:
        print(f"Langchain integration demo error: {str(e)}")

def main():
    # Initialize IPFS Kit with high-level API
    print("Initializing IPFS Kit...")
    api = IPFSSimpleAPI(role="worker")

    # Set up example data
    cids = setup_example_data(api)

    # Wait a moment for indexing to complete
    print("Waiting for indexing to complete...")
    time.sleep(2)

    # Demonstrate different search types
    demonstrate_metadata_search(api)
    demonstrate_vector_search(api)
    demonstrate_hybrid_search(api)
    demonstrate_llm_context_generation(api)

    # Demonstrate AI/ML integration
    demonstrate_aiml_integration()

    print("\n=== Example Complete ===")

if __name__ == "__main__":
    main()
