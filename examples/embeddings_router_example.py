#!/usr/bin/env python3
"""
Example: Embeddings Router with IPFS Endpoint Multiplexing

This example demonstrates how to use the embeddings router with IPFS Kit's
endpoint multiplexing to route embeddings requests across peer endpoints.
"""

import sys
import os

# Add ipfs_kit_py to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ipfs_kit_py.embeddings_router import embed_texts, embed_text, get_embeddings_provider, register_embeddings_provider
from ipfs_kit_py.router_deps import RouterDeps


def example_basic_usage():
    """Basic embeddings generation with auto provider selection."""
    print("=" * 60)
    print("Example 1: Basic Embeddings Generation")
    print("=" * 60)
    
    texts = [
        "Hello world",
        "IPFS is a distributed file system",
        "Embeddings are vector representations of text"
    ]
    
    print(f"Generating embeddings for {len(texts)} texts...\n")
    
    try:
        embeddings = embed_texts(texts)
        print(f"✅ Generated {len(embeddings)} embeddings")
        print(f"Dimension: {len(embeddings[0])}")
        print(f"First embedding preview: {embeddings[0][:5]}...\n")
    except Exception as e:
        print(f"Error: {e}\n")


def example_single_text():
    """Generate embedding for single text."""
    print("=" * 60)
    print("Example 2: Single Text Embedding")
    print("=" * 60)
    
    text = "This is a sample text for embedding"
    
    print(f"Text: {text}\n")
    
    try:
        embedding = embed_text(text)
        print(f"✅ Generated embedding")
        print(f"Dimension: {len(embedding)}")
        print(f"Preview: {embedding[:10]}...\n")
    except Exception as e:
        print(f"Error: {e}\n")


def example_custom_provider():
    """Example with a custom embeddings provider."""
    print("=" * 60)
    print("Example 3: Custom Embeddings Provider")
    print("=" * 60)
    
    class SimpleEmbedder:
        """A simple mock embeddings provider for demonstration."""
        
        def embed_texts(self, texts, **kwargs):
            # Generate mock embeddings (dimension 128)
            text_list = list(texts)
            return [[0.1 * (i + 1)] * 128 for i in range(len(text_list))]
    
    # Register the custom provider
    register_embeddings_provider("simple_embedder", lambda: SimpleEmbedder())
    
    texts = ["Text 1", "Text 2"]
    
    print(f"Using custom provider for {len(texts)} texts...\n")
    
    try:
        embeddings = embed_texts(texts, provider="simple_embedder")
        print(f"✅ Generated {len(embeddings)} embeddings")
        print(f"Dimension: {len(embeddings[0])}")
        print(f"First embedding: {embeddings[0][:5]}...")
        print(f"Second embedding: {embeddings[1][:5]}...\n")
    except Exception as e:
        print(f"Error: {e}\n")


def example_with_deps():
    """Example with shared dependencies."""
    print("=" * 60)
    print("Example 4: Using Router Dependencies")
    print("=" * 60)
    
    # Create shared dependencies
    deps = RouterDeps()
    
    batches = [
        ["Batch 1 text 1", "Batch 1 text 2"],
        ["Batch 2 text 1", "Batch 2 text 2"],
        ["Batch 3 text 1", "Batch 3 text 2"]
    ]
    
    print("Generating embeddings with shared dependencies...\n")
    
    for i, batch in enumerate(batches, 1):
        try:
            print(f"Batch {i}: {len(batch)} texts")
            embeddings = embed_texts(batch, deps=deps)
            print(f"   ✅ Generated {len(embeddings)} embeddings (dim {len(embeddings[0])})\n")
        except Exception as e:
            print(f"   Error: {e}\n")


def example_ipfs_peer_multiplexing():
    """Example with IPFS peer endpoint multiplexing."""
    print("=" * 60)
    print("Example 5: IPFS Peer Endpoint Multiplexing")
    print("=" * 60)
    
    # Create deps with mock IPFS backend
    class MockIPFSBackend:
        """Mock IPFS backend for demonstration."""
        
        class MockPeerManager:
            def route_embeddings_request(self, texts, model=None, device=None, **kwargs):
                return {
                    "embeddings": [[0.5] * 256 for _ in texts],
                    "peer_id": "QmExamplePeerID",
                    "model": model or "default"
                }
        
        def __init__(self):
            self.peer_manager = self.MockPeerManager()
    
    deps = RouterDeps()
    deps.ipfs_backend = MockIPFSBackend()
    
    texts = ["Text routed through peer 1", "Text routed through peer 2"]
    
    print(f"Routing {len(texts)} texts through IPFS peer endpoints...\n")
    
    try:
        embeddings = embed_texts(
            texts,
            provider="ipfs_peer",  # Use peer routing
            deps=deps
        )
        print(f"✅ Generated {len(embeddings)} embeddings via IPFS peers")
        print(f"Dimension: {len(embeddings[0])}")
        print(f"Preview: {embeddings[0][:5]}...\n")
    except Exception as e:
        print(f"Error: {e}\n")


def example_semantic_search():
    """Example of using embeddings for semantic search."""
    print("=" * 60)
    print("Example 6: Semantic Search")
    print("=" * 60)
    
    # Documents
    documents = [
        "IPFS is a peer-to-peer distributed file system",
        "Python is a programming language",
        "The sky is blue",
        "Distributed systems enable scalability"
    ]
    
    # Query
    query = "What is IPFS?"
    
    print(f"Documents: {len(documents)}")
    print(f"Query: {query}\n")
    
    try:
        # Embed documents
        print("Embedding documents...")
        doc_embeddings = embed_texts(documents)
        
        # Embed query
        print("Embedding query...")
        query_embedding = embed_text(query)
        
        # Compute similarities (cosine similarity)
        import math
        
        def cosine_similarity(a, b):
            dot_product = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(x * x for x in b))
            return dot_product / (norm_a * norm_b) if (norm_a * norm_b) > 0 else 0
        
        similarities = [
            cosine_similarity(query_embedding, doc_emb)
            for doc_emb in doc_embeddings
        ]
        
        # Rank documents
        ranked = sorted(enumerate(similarities), key=lambda x: x[1], reverse=True)
        
        print("\n📊 Search Results:")
        for idx, (doc_idx, score) in enumerate(ranked[:3], 1):
            print(f"{idx}. (Score: {score:.4f}) {documents[doc_idx]}")
        print()
        
    except Exception as e:
        print(f"Error: {e}\n")


def main():
    """Run all examples."""
    print("\n")
    print("=" * 60)
    print("Embeddings Router Examples")
    print("=" * 60)
    print()
    
    examples = [
        example_basic_usage,
        example_single_text,
        example_custom_provider,
        example_with_deps,
        example_ipfs_peer_multiplexing,
        example_semantic_search,
    ]
    
    for example in examples:
        try:
            example()
        except Exception as e:
            print(f"Example failed: {e}")
            import traceback
            traceback.print_exc()
        
        print()
    
    print("=" * 60)
    print("Examples Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
