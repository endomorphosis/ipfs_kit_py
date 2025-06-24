"""
Example demonstrating the Custom Embedding Models integration with Hugging Face.

This example shows how to:
1. Load a custom embedding model from Hugging Face Hub
2. Generate embeddings for text using the model
3. Use the model with hybrid search
4. Compare different embedding models
5. Use the embeddings with Langchain and LlamaIndex
"""

import sys
import os
import time
import numpy as np
from typing import List, Dict

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import from ipfs_kit_py
from ipfs_kit_py.high_level_api import IPFSSimpleAPI
from ipfs_kit_py.ai_ml_integration import CustomEmbeddingModel

def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    if not vec1 or not vec2:
        return 0.0

    vec1_array = np.array(vec1)
    vec2_array = np.array(vec2)

    dot_product = np.dot(vec1_array, vec2_array)
    norm1 = np.linalg.norm(vec1_array)
    norm2 = np.linalg.norm(vec2_array)

    # Avoid division by zero
    if norm1 == 0 or norm2 == 0:
        return 0.0

    return dot_product / (norm1 * norm2)

def print_section(title: str):
    """Print a section title with formatting."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def compare_texts(model, texts: List[str], reference_text: str):
    """Compare a list of texts to a reference text using embeddings."""
    print(f"\nComparing texts to reference: '{reference_text}'\n")

    # Generate embeddings
    text_embeddings = model.generate_embeddings(texts)
    reference_embedding = model.generate_embedding(reference_text)

    # Calculate similarities
    results = []
    for i, text in enumerate(texts):
        similarity = cosine_similarity(text_embeddings[i], reference_embedding)
        results.append((text, similarity))

    # Sort by similarity
    results.sort(key=lambda x: x[1], reverse=True)

    # Print results
    for text, similarity in results:
        print(f"{similarity:.4f}: {text}")

def main():
    # Initialize high-level API
    api = IPFSSimpleAPI()

    print_section("1. Loading Custom Embedding Models from Hugging Face Hub")

    # Load a small, efficient model
    print("\nLoading sentence-transformers/all-MiniLM-L6-v2 (small model)...")
    model_result = api.load_embedding_model(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        use_ipfs_cache=True
    )

    if not model_result["success"]:
        print(f"Error loading model: {model_result.get('error')}")
        return

    small_model = model_result["model"]
    print(f"Model loaded successfully with dimension: {model_result['model_info']['vector_dimension']}")

    # Also try a larger, more powerful model if available
    print("\nLoading sentence-transformers/all-mpnet-base-v2 (larger model)...")
    try:
        large_model_result = api.load_embedding_model(
            model_name="sentence-transformers/all-mpnet-base-v2",
            use_ipfs_cache=True
        )
        large_model = large_model_result["model"] if large_model_result["success"] else None
        if large_model:
            print(f"Larger model loaded successfully with dimension: {large_model_result['model_info']['vector_dimension']}")
        else:
            print(f"Could not load larger model: {large_model_result.get('error')}")
            large_model = None
    except Exception as e:
        print(f"Error loading larger model: {e}")
        large_model = None

    print_section("2. Generating Embeddings for Text")

    # Sample texts for semantic comparison
    texts = [
        "The quick brown fox jumps over the lazy dog",
        "A fast auburn canine leaps above the sleepy hound",
        "The weather is sunny and warm today",
        "Python is a versatile programming language",
        "The Internet was created to share research data",
        "IPFS is a distributed file system for content-addressed storage",
        "Machine learning models are trained on large datasets",
        "Vector embeddings represent semantic meaning in a high-dimensional space"
    ]

    # Generate embeddings for a single text
    print("\nGenerating embedding for a single text:")
    single_result = api.generate_embeddings(
        texts="IPFS provides content-addressed storage",
        model=small_model
    )

    if single_result["success"]:
        embedding = single_result["embedding"]
        print(f"Generated embedding with dimension: {single_result['dimension']}")
        print(f"First few values: {embedding[:5]}...")
    else:
        print(f"Error generating embedding: {single_result.get('error')}")

    # Generate embeddings for multiple texts
    print("\nGenerating embeddings for multiple texts:")
    batch_result = api.generate_embeddings(
        texts=texts,
        model=small_model
    )

    if batch_result["success"]:
        embeddings = batch_result["embeddings"]
        print(f"Generated {len(embeddings)} embeddings with dimension: {batch_result['dimension']}")
    else:
        print(f"Error generating embeddings: {batch_result.get('error')}")

    print_section("3. Semantic Similarity with Embeddings")

    # Compare semantic similarity between texts
    reference_text = "IPFS implements content-addressed storage for the web"
    compare_texts(small_model, texts, reference_text)

    # Compare with larger model if available
    if large_model:
        print("\nUsing larger model for comparison:")
        compare_texts(large_model, texts, reference_text)

    print_section("4. Using Custom Embeddings with Hybrid Search")

    # Create search connector with custom embedding model
    print("\nCreating search connector with custom embedding model...")

    try:
        connector_result = api.create_search_connector(
            embedding_model=small_model
        )

        if connector_result["success"]:
            search_connector = connector_result["connector"]
            print("Search connector created successfully")

            # Use the search connector to generate embeddings
            sample_text = "Content-addressed storage for versioned data"
            print(f"\nGenerating embedding for: '{sample_text}'")
            embedding = search_connector.generate_embedding(sample_text)
            print(f"Generated embedding with dimension: {len(embedding)}")
            print(f"First few values: {embedding[:5]}...")
        else:
            print(f"Error creating search connector: {connector_result.get('error')}")
            search_connector = None

    except Exception as e:
        print(f"Error using search connector: {e}")
        search_connector = None

    print_section("5. Integration with Langchain and LlamaIndex")

    # Convert to Langchain embedding model
    try:
        langchain_embeddings = small_model.to_langchain()
        if langchain_embeddings:
            print("\nConverted to Langchain embeddings interface")

            # Test Langchain integration
            query = "How does IPFS store data?"
            langchain_result = langchain_embeddings.embed_query(query)
            print(f"Generated Langchain embedding with dimension: {len(langchain_result)}")
        else:
            print("Could not create Langchain embeddings (Langchain may not be installed)")

    except Exception as e:
        print(f"Error with Langchain integration: {e}")

    # Convert to LlamaIndex embedding model
    try:
        llamaindex_embeddings = small_model.to_llama_index()
        if llamaindex_embeddings:
            print("\nConverted to LlamaIndex embeddings interface")

            # Test LlamaIndex integration
            query = "How does IPFS store data?"
            llamaindex_result = llamaindex_embeddings._get_text_embedding(query)
            print(f"Generated LlamaIndex embedding with dimension: {len(llamaindex_result)}")
        else:
            print("Could not create LlamaIndex embeddings (LlamaIndex may not be installed)")

    except Exception as e:
        print(f"Error with LlamaIndex integration: {e}")

    print_section("6. Performance Benchmarking")

    # Benchmark embedding generation performance
    print("\nBenchmarking embedding generation performance...")

    # Create large text batch
    benchmark_texts = ["This is benchmark text " + str(i) for i in range(100)]

    # Measure performance
    start_time = time.time()
    benchmark_result = small_model.generate_embeddings(benchmark_texts)
    end_time = time.time()

    print(f"Generated {len(benchmark_texts)} embeddings in {end_time - start_time:.2f} seconds")
    print(f"Average time per embedding: {(end_time - start_time) * 1000 / len(benchmark_texts):.2f} ms")

if __name__ == "__main__":
    main()
