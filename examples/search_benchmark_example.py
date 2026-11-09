"""
Example demonstrating the search benchmarking capabilities of IPFS Kit.

This example shows how to use the SearchBenchmark class to measure performance
of different search strategies in the integrated search system.
"""

import sys
import os
import time
import argparse
from typing import Dict, Any, List

# Add parent directory to path for direct execution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import the high-level API
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

# Try to import the search benchmark components directly
try:
    from ipfs_kit_py.integrated_search import SearchBenchmark
    BENCHMARK_AVAILABLE = True
except ImportError:
    BENCHMARK_AVAILABLE = False

def setup_example_data(api):
    """Set up example data for the benchmarking."""
    print("Setting up example data...")
    
    # Create some machine learning models with different characteristics
    model_templates = [
        {
            "name": "ResNet50",
            "task": "image-classification",
            "framework": "pytorch",
            "dataset": "ImageNet",
            "accuracy": 0.76,
            "tags": ["computer-vision", "classification", "resnet"]
        },
        {
            "name": "BERT-base",
            "task": "text-embedding",
            "framework": "tensorflow",
            "dataset": "BookCorpus",
            "accuracy": 0.82,
            "tags": ["nlp", "transformer", "embedding"]
        },
        {
            "name": "ViT-B/16",
            "task": "image-classification",
            "framework": "pytorch",
            "dataset": "ImageNet",
            "accuracy": 0.81,
            "tags": ["computer-vision", "transformer", "classification"]
        },
        {
            "name": "GPT-2-small",
            "task": "text-generation",
            "framework": "pytorch",
            "dataset": "WebText",
            "accuracy": 0.74,
            "tags": ["nlp", "transformer", "generation"]
        },
        {
            "name": "EfficientNet-B0",
            "task": "image-classification",
            "framework": "tensorflow",
            "dataset": "ImageNet",
            "accuracy": 0.77,
            "tags": ["computer-vision", "classification", "mobile"]
        },
        {
            "name": "MobileNet-v3",
            "task": "image-classification",
            "framework": "pytorch",
            "dataset": "ImageNet",
            "accuracy": 0.75,
            "tags": ["computer-vision", "classification", "mobile"]
        },
        {
            "name": "RoBERTa-base",
            "task": "text-classification",
            "framework": "pytorch",
            "dataset": "GLUE",
            "accuracy": 0.84,
            "tags": ["nlp", "transformer", "classification"]
        },
        {
            "name": "YOLOv5",
            "task": "object-detection",
            "framework": "pytorch",
            "dataset": "COCO",
            "accuracy": 0.63,
            "tags": ["computer-vision", "detection", "real-time"]
        },
        {
            "name": "U-Net",
            "task": "image-segmentation",
            "framework": "tensorflow",
            "dataset": "Pascal VOC",
            "accuracy": 0.72,
            "tags": ["computer-vision", "segmentation", "medical"]
        },
        {
            "name": "DeepLab-v3",
            "task": "image-segmentation",
            "framework": "tensorflow",
            "dataset": "Cityscapes",
            "accuracy": 0.81,
            "tags": ["computer-vision", "segmentation", "scene-parsing"]
        }
    ]
    
    # Add models to IPFS
    print(f"Adding {len(model_templates)} models to IPFS...")
    
    cids = {}
    for model_metadata in model_templates:
        # Create dummy model data
        model_data = {
            "config": {
                "name": model_metadata["name"],
                "layers": 10  # Simple placeholder
            }
        }
        
        # Add to IPFS through the AI/ML API
        result = api.ai_model_add(model_data, model_metadata)
        
        if result.get("success", False):
            cid = result.get("cid")
            cids[model_metadata["name"]] = cid
            print(f"  Added {model_metadata['name']} with CID: {cid}")
        else:
            print(f"  Failed to add {model_metadata['name']}: {result.get('error', 'Unknown error')}")
    
    # Wait a moment for indexing to complete
    print("Waiting for indexing to complete...")
    time.sleep(3)
    
    return cids

def run_full_benchmark(api, output_dir=None, runs=5):
    """Run a full benchmark suite and display results."""
    if not BENCHMARK_AVAILABLE:
        print("ERROR: Benchmark components not available.")
        return
    
    # Create benchmark instance
    benchmark = SearchBenchmark(api, output_dir=output_dir)
    
    # Run full benchmark suite
    print(f"Running full benchmark suite with {runs} runs per test case...")
    results = benchmark.run_full_benchmark_suite(num_runs=runs)
    
    # Generate and print report
    report = benchmark.generate_benchmark_report(results)
    print("\n" + report)
    
    # Print saved location
    if "saved_to" in results:
        print(f"\nDetailed results saved to: {results['saved_to']}")

def run_custom_benchmark(api, benchmark_type, num_runs=5, output_dir=None):
    """Run a specific benchmark type."""
    if not BENCHMARK_AVAILABLE:
        print("ERROR: Benchmark components not available.")
        return
    
    # Create benchmark instance
    benchmark = SearchBenchmark(api, output_dir=output_dir)
    
    if benchmark_type == "metadata":
        # Custom metadata filters for benchmarking
        filters_list = [
            [("tags", "contains", "computer-vision")],
            [("framework", "==", "pytorch")],
            [("task", "==", "image-classification"), ("accuracy", ">=", 0.75)],
            [("tags", "contains", "transformer")]
        ]
        
        print(f"Running metadata search benchmark with {num_runs} runs per test case...")
        results = benchmark.benchmark_metadata_search(
            filters_list=filters_list,
            num_runs=num_runs
        )
        
    elif benchmark_type == "vector":
        # Custom queries for vector search benchmarking
        queries = [
            "efficient model for image recognition on mobile devices",
            "transformer architecture for natural language processing",
            "real-time object detection for autonomous vehicles",
            "semantic segmentation for medical imaging"
        ]
        
        print(f"Running vector search benchmark with {num_runs} runs per test case...")
        results = benchmark.benchmark_vector_search(
            queries=queries,
            num_runs=num_runs
        )
        
    elif benchmark_type == "hybrid":
        # Custom test cases for hybrid search benchmarking
        test_cases = [
            {
                "query_text": "mobile-friendly computer vision model",
                "metadata_filters": [("framework", "==", "pytorch")]
            },
            {
                "query_text": "transformer for text processing",
                "metadata_filters": [("task", "==", "text-embedding")]
            },
            {
                "query_text": "high accuracy image model",
                "metadata_filters": [("accuracy", ">=", 0.8)]
            },
            {
                "query_text": "segmentation model",
                "metadata_filters": [("tags", "contains", "segmentation")]
            }
        ]
        
        print(f"Running hybrid search benchmark with {num_runs} runs per test case...")
        results = benchmark.benchmark_hybrid_search(
            test_cases=test_cases,
            num_runs=num_runs
        )
        
    else:
        print(f"ERROR: Unknown benchmark type: {benchmark_type}")
        return
    
    # Generate and print report
    report = benchmark.generate_benchmark_report(results)
    print("\n" + report)
    
    # Save results to file
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"{benchmark_type}_search_benchmark_{timestamp}.json"
    filepath = os.path.join(output_dir or os.path.expanduser("~/.ipfs_benchmarks"), filename)
    
    with open(filepath, "w") as f:
        import json
        json.dump(results, f, indent=2)
        
    print(f"\nDetailed results saved to: {filepath}")

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="IPFS Search Benchmark Example")
    parser.add_argument("--type", choices=["full", "metadata", "vector", "hybrid"], 
                        default="full", help="Benchmark type to run")
    parser.add_argument("--runs", type=int, default=5, 
                        help="Number of runs per test case")
    parser.add_argument("--output-dir", type=str, default=None,
                        help="Directory to save benchmark results")
    parser.add_argument("--no-setup", action="store_true",
                        help="Skip data setup (use existing data)")
    args = parser.parse_args()
    
    # Initialize IPFS Kit with high-level API
    print("Initializing IPFS Kit...")
    api = IPFSSimpleAPI(role="worker")
    
    # Set up example data if needed
    if not args.no_setup:
        cids = setup_example_data(api)
    
    # Run the requested benchmark
    if args.type == "full":
        run_full_benchmark(api, output_dir=args.output_dir, runs=args.runs)
    else:
        run_custom_benchmark(api, args.type, num_runs=args.runs, output_dir=args.output_dir)
    
    print("\n=== Benchmark Complete ===")

if __name__ == "__main__":
    main()