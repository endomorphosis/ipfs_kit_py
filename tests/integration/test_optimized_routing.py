#!/usr/bin/env python3
"""
Test Optimized Data Routing for MCP Storage Manager

This script demonstrates and tests the content-aware routing capabilities
implemented as part of the Phase 1: Core Functionality Enhancements (Q3 2025)
from the MCP roadmap.
"""

import os
import sys
import time
import json
import random
import unittest
import logging
from typing import Dict, List, Any, Optional, Union, BinaryIO, Tuple

# Add parent directory to path for importing
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import relevant modules
from ipfs_kit_py.mcp.storage_types import StorageBackendType
from ipfs_kit_py.mcp.storage_manager.router import get_instance as get_basic_router
from ipfs_kit_py.mcp.storage_manager.router.balanced import get_balanced_instance
from ipfs_kit_py.mcp.storage_manager.router.content_analyzer import get_instance as get_content_analyzer
from ipfs_kit_py.mcp.storage_manager.router.cost_optimizer import get_instance as get_cost_optimizer
from ipfs_kit_py.mcp.storage_manager.router.performance_tracker import get_instance as get_performance_tracker
from ipfs_kit_py.mcp.storage_manager.router_integration import create_router_integration

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("router_test")


class TestContentTypeAnalyzer(unittest.TestCase):
    """Test cases for the ContentTypeAnalyzer."""

    def setUp(self):
        """Set up test environment."""
        self.analyzer = get_content_analyzer()

    def test_content_category_detection(self):
        """Test content category detection from MIME types and filenames."""
        # Test MIME type detection
        self.assertEqual(self.analyzer.get_content_category("image/jpeg"), "image")
        self.assertEqual(self.analyzer.get_content_category("video/mp4"), "video")
        self.assertEqual(self.analyzer.get_content_category("audio/mp3"), "audio")
        self.assertEqual(self.analyzer.get_content_category("application/pdf"), "document")
        self.assertEqual(self.analyzer.get_content_category("text/plain"), "document")
        
        # Test filename detection
        self.assertEqual(self.analyzer.get_content_category(filename="image.jpg"), "image")
        self.assertEqual(self.analyzer.get_content_category(filename="video.mp4"), "video")
        self.assertEqual(self.analyzer.get_content_category(filename="audio.mp3"), "audio")
        self.assertEqual(self.analyzer.get_content_category(filename="document.pdf"), "document")
        self.assertEqual(self.analyzer.get_content_category(filename="model.pth"), "model")
        self.assertEqual(self.analyzer.get_content_category(filename="data.csv"), "dataset")
        self.assertEqual(self.analyzer.get_content_category(filename="archive.zip"), "archive")
        
        # Test both MIME type and filename together (MIME type should take precedence)
        self.assertEqual(self.analyzer.get_content_category("image/jpeg", "video.mp4"), "image")

    def test_content_type_scoring(self):
        """Test content type score calculation for different backends."""
        # Test image scores
        image_scores = {
            backend: self.analyzer.get_content_type_score(backend, "image/jpeg")
            for backend in StorageBackendType
        }
        
        # IPFS should score high for images
        self.assertGreater(image_scores[StorageBackendType.IPFS], 0.8)
        
        # HuggingFace should score high for models
        model_scores = {
            backend: self.analyzer.get_content_type_score(backend, filename="model.h5")
            for backend in StorageBackendType
        }
        self.assertGreater(model_scores[StorageBackendType.HUGGINGFACE], 0.8)
        
        # Test recommendations
        image_recommendations = self.analyzer.get_recommended_backends("image/jpeg")
        self.assertIn(StorageBackendType.IPFS, image_recommendations)
        
        model_recommendations = self.analyzer.get_recommended_backends(filename="model.h5")
        self.assertIn(StorageBackendType.HUGGINGFACE, model_recommendations)


class TestCostOptimizer(unittest.TestCase):
    """Test cases for the CostOptimizer."""

    def setUp(self):
        """Set up test environment."""
        self.optimizer = get_cost_optimizer()

    def test_cost_estimation(self):
        """Test cost estimation for different backends."""
        # Test storage cost estimation
        size_bytes = 100 * 1024 * 1024  # 100 MB
        duration_seconds = 30 * 24 * 60 * 60  # 30 days
        
        for backend in StorageBackendType:
            cost = self.optimizer.estimate_storage_cost(backend, size_bytes, duration_seconds)
            self.assertGreaterEqual(cost, 0.0)
            
            # Also test retrieval cost
            retrieval_cost = self.optimizer.estimate_retrieval_cost(backend, size_bytes)
            self.assertGreaterEqual(retrieval_cost, 0.0)
    
    def test_cost_scoring(self):
        """Test cost score calculation for different backends."""
        size_bytes = 100 * 1024 * 1024  # 100 MB
        
        # Test storage operation
        store_scores = {
            backend: self.optimizer.get_cost_score(backend, size_bytes, "store")
            for backend in StorageBackendType
        }
        
        # All scores should be between 0 and 1
        for backend, score in store_scores.items():
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 1.0)
        
        # Test retrieve operation
        retrieve_scores = {
            backend: self.optimizer.get_cost_score(backend, size_bytes, "retrieve")
            for backend in StorageBackendType
        }
        
        # All scores should be between 0 and 1
        for backend, score in retrieve_scores.items():
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 1.0)
    
    def test_backend_ranking(self):
        """Test backend ranking by cost."""
        size_bytes = 100 * 1024 * 1024  # 100 MB
        
        # Get rankings for storage operation
        store_ranking = self.optimizer.get_backend_ranking(
            list(StorageBackendType),
            size_bytes,
            "store"
        )
        
        # Check that rankings are sorted by cost (cheapest first)
        for i in range(1, len(store_ranking)):
            self.assertLessEqual(
                store_ranking[i-1]["cost"],
                store_ranking[i]["cost"]
            )
        
        # Get rankings for retrieval operation
        retrieve_ranking = self.optimizer.get_backend_ranking(
            list(StorageBackendType),
            size_bytes,
            "retrieve"
        )
        
        # Check that rankings are sorted by cost (cheapest first)
        for i in range(1, len(retrieve_ranking)):
            self.assertLessEqual(
                retrieve_ranking[i-1]["cost"],
                retrieve_ranking[i]["cost"]
            )


class TestPerformanceTracker(unittest.TestCase):
    """Test cases for the PerformanceTracker."""

    def setUp(self):
        """Set up test environment."""
        self.tracker = get_performance_tracker()
        self.tracker.reset()  # Start with a clean state

    def test_operation_recording(self):
        """Test recording of operation performance."""
        # Record some operations
        backends = list(StorageBackendType)
        operations = ["store", "retrieve", "delete", "list"]
        
        # Record 10 operations for each backend
        for _ in range(10):
            for backend in backends:
                for operation in operations:
                    # Simulate some randomness in performance
                    latency = random.uniform(0.1, 2.0)
                    size = random.randint(1024, 10 * 1024 * 1024) if operation in ["store", "retrieve"] else None
                    success = random.random() > 0.1  # 10% error rate
                    
                    self.tracker.record_operation(
                        backend_type=backend,
                        operation_type=operation,
                        latency=latency,
                        size=size,
                        success=success
                    )
        
        # Check that operations were recorded
        stats = self.tracker.get_statistics()
        
        # Each backend should have stats
        for backend in backends:
            self.assertIn(backend.value, stats["backends"])
            
            # Check operation counts
            backend_stats = stats["backends"][backend.value]
            self.assertEqual(backend_stats["operation_count"], 40)  # 10 operations * 4 types

    def test_performance_scoring(self):
        """Test performance score calculation."""
        # Record operations with different performance characteristics
        
        # Backend 1: Fast with low error rate
        for _ in range(10):
            self.tracker.record_operation(
                backend_type=StorageBackendType.IPFS,
                operation_type="retrieve",
                latency=0.1,  # Fast
                size=1024 * 1024,
                success=True  # No errors
            )
        
        # Backend 2: Slow with high error rate
        for _ in range(10):
            self.tracker.record_operation(
                backend_type=StorageBackendType.S3,
                operation_type="retrieve",
                latency=2.0,  # Slow
                size=1024 * 1024,
                success=False  # All errors
            )
        
        # Calculate performance scores
        score1 = self.tracker.get_performance_score(StorageBackendType.IPFS)
        score2 = self.tracker.get_performance_score(StorageBackendType.S3)
        
        # Backend 1 should have a higher score than Backend 2
        self.assertGreater(score1, score2)
        
        # Calculate operation-specific scores
        op_score1 = self.tracker.get_operation_performance_score(
            StorageBackendType.IPFS, "retrieve"
        )
        op_score2 = self.tracker.get_operation_performance_score(
            StorageBackendType.S3, "retrieve"
        )
        
        # Operation-specific scores should also reflect the difference
        self.assertGreater(op_score1, op_score2)


class TestBalancedRouter(unittest.TestCase):
    """Test cases for the BalancedRouter."""

    def setUp(self):
        """Set up test environment."""
        # Reset the performance tracker
        tracker = get_performance_tracker()
        tracker.reset()
        
        # Create a balanced router with all backends available
        self.router = get_balanced_instance(
            config={
                "balance_weights": {
                    "content": 0.25,
                    "performance": 0.20,
                    "cost": 0.15,
                    "reliability": 0.20,
                    "preference": 0.20,
                }
            },
            available_backends=list(StorageBackendType)
        )
        
        # Record some operations to populate performance metrics
        self._populate_performance_metrics()

    def _populate_performance_metrics(self):
        """Populate performance metrics with simulated data."""
        tracker = get_performance_tracker()
        
        # Define performance characteristics for each backend
        performance_profiles = {
            StorageBackendType.IPFS: {"latency": 0.2, "error_rate": 0.05},
            StorageBackendType.S3: {"latency": 0.3, "error_rate": 0.02},
            StorageBackendType.STORACHA: {"latency": 0.4, "error_rate": 0.08},
            StorageBackendType.FILECOIN: {"latency": 1.5, "error_rate": 0.10},
            StorageBackendType.HUGGINGFACE: {"latency": 0.5, "error_rate": 0.05},
            StorageBackendType.LASSIE: {"latency": 0.6, "error_rate": 0.07}
        }
        
        # Record 50 operations for each backend
        for backend, profile in performance_profiles.items():
            for _ in range(50):
                # Add some randomness
                latency = profile["latency"] * random.uniform(0.8, 1.2)
                success = random.random() > profile["error_rate"]
                
                tracker.record_operation(
                    backend_type=backend,
                    operation_type="store",
                    latency=latency,
                    size=1024 * 1024,
                    success=success
                )
                
                tracker.record_operation(
                    backend_type=backend,
                    operation_type="retrieve",
                    latency=latency * 0.8,  # Retrieval is usually faster
                    size=1024 * 1024,
                    success=success
                )

    def test_simple_strategy(self):
        """Test simple routing strategy based on content type and size."""
        # Test image routing
        backend, reason = self.router._simple_strategy({
            "content_type": "image/jpeg",
            "size": 500 * 1024  # 500 KB
        })
        
        # IPFS should be selected for images
        self.assertEqual(backend, StorageBackendType.IPFS)
        
        # Test large file routing
        backend, reason = self.router._simple_strategy({
            "size": 2 * 1024 * 1024 * 1024  # 2 GB
        })
        
        # Filecoin or S3 should be selected for large files
        self.assertIn(backend, [StorageBackendType.FILECOIN, StorageBackendType.S3])

    def test_performance_strategy(self):
        """Test performance-based routing strategy."""
        backend, reason = self.router._performance_strategy({
            "operation": "retrieve"
        })
        
        # Verify result
        self.assertIsNotNone(backend)
        self.assertIn("performance_score", reason)

    def test_cost_strategy(self):
        """Test cost-based routing strategy."""
        backend, reason = self.router._cost_strategy({
            "operation": "store",
            "size": 100 * 1024 * 1024  # 100 MB
        })
        
        # Verify result
        self.assertIsNotNone(backend)
        self.assertIn("cost_score", reason)

    def test_reliability_strategy(self):
        """Test reliability-based routing strategy."""
        backend, reason = self.router._reliability_strategy({})
        
        # Verify result
        self.assertIsNotNone(backend)
        self.assertIn("reliability_score", reason)

    def test_balanced_strategy(self):
        """Test balanced routing strategy."""
        # Test with various content types and sizes
        test_scenarios = [
            {
                "name": "Small image file",
                "request": {
                    "content_type": "image/jpeg",
                    "size": 500 * 1024,  # 500 KB
                    "operation": "store"
                }
            },
            {
                "name": "Large video file",
                "request": {
                    "content_type": "video/mp4",
                    "size": 1.5 * 1024 * 1024 * 1024,  # 1.5 GB
                    "operation": "store"
                }
            },
            {
                "name": "ML model file",
                "request": {
                    "filename": "model.h5",
                    "size": 200 * 1024 * 1024,  # 200 MB
                    "operation": "store"
                }
            },
            {
                "name": "Document retrieval",
                "request": {
                    "content_type": "application/pdf",
                    "size": 10 * 1024 * 1024,  # 10 MB
                    "operation": "retrieve"
                }
            }
        ]
        
        # Run all scenarios
        for scenario in test_scenarios:
            backend, reason = self.router._balanced_strategy(scenario["request"])
            
            # Verify result
            self.assertIsNotNone(backend)
            self.assertIn("balanced_score", reason)
            
            # Print scenario results
            print(f"\n{scenario['name']}:")
            print(f"  Selected backend: {backend.value}")
            print(f"  Reason: {reason}")
            
            # Parse score components
            if "balanced_score" in reason:
                score_str = reason.split("_", 1)[1]
                overall_score = float(score_str.split("_")[0])
                
                components_str = "_".join(score_str.split("_")[1:])
                components = {}
                for comp in components_str.split(","):
                    if ":" in comp:
                        k, v = comp.split(":")
                        components[k] = float(v)
                
                print(f"  Overall score: {overall_score:.2f}")
                print(f"  Score components: {json.dumps(components, indent=2)}")

    def test_router_statistics(self):
        """Test router statistics collection."""
        # Make some routing decisions to generate statistics
        for _ in range(10):
            self.router.select_backend({
                "content_type": "image/jpeg",
                "size": 500 * 1024,
                "operation": "store"
            })
        
        # Get statistics
        stats = self.router.get_statistics()
        
        # Verify statistics
        self.assertIn("router_metrics", stats)
        self.assertIn("decision_counts", stats["router_metrics"])
        self.assertIn("performance_stats", stats)


class TestRouterIntegration(unittest.TestCase):
    """Test cases for the RouterIntegration."""

    def setUp(self):
        """Set up test environment."""
        # Create a router integration
        self.integration = create_router_integration(
            config={"router_type": "balanced"},
            available_backends=list(StorageBackendType)
        )

    def test_backend_selection(self):
        """Test backend selection through the integration."""
        # Test selection for different content types
        test_scenarios = [
            {
                "name": "Image file",
                "request": {
                    "content_type": "image/jpeg",
                    "size": 500 * 1024,  # 500 KB
                    "operation": "store"
                }
            },
            {
                "name": "Large file",
                "request": {
                    "size": 2 * 1024 * 1024 * 1024,  # 2 GB
                    "operation": "store"
                }
            },
            {
                "name": "Model file",
                "request": {
                    "filename": "model.h5",
                    "operation": "store"
                }
            }
        ]
        
        # Run all scenarios
        for scenario in test_scenarios:
            backend, reason = self.integration.select_backend(scenario["request"])
            
            # Verify result
            self.assertIsNotNone(backend)
            
            # Print scenario results
            print(f"\n{scenario['name']}:")
            print(f"  Selected backend: {backend.value}")
            print(f"  Reason: {reason}")


def demonstrate_router_usage():
    """Demonstrate how to use the router in a real application."""
    print("\n=== Optimized Data Routing Demonstration ===\n")
    
    # Create a router integration
    router = create_router_integration(
        config={"router_type": "balanced"},
        available_backends=list(StorageBackendType)
    )
    
    # Define test cases with expected outcomes
    test_cases = [
        {
            "description": "High-resolution image (10 MB)",
            "request": {
                "content_type": "image/jpeg",
                "size": 10 * 1024 * 1024,
                "filename": "high_res_photo.jpg",
                "operation": "store"
            },
            "expected_backends": [StorageBackendType.IPFS, StorageBackendType.S3]
        },
        {
            "description": "Machine learning model (500 MB)",
            "request": {
                "content_type": "application/octet-stream",
                "size": 500 * 1024 * 1024,
                "filename": "transformer_model.pt",
                "operation": "store"
            },
            "expected_backends": [StorageBackendType.HUGGINGFACE, StorageBackendType.S3]
        },
        {
            "description": "Large video file (4 GB)",
            "request": {
                "content_type": "video/mp4",
                "size": 4 * 1024 * 1024 * 1024,
                "filename": "documentary.mp4",
                "operation": "store"
            },
            "expected_backends": [StorageBackendType.FILECOIN, StorageBackendType.S3]
        },
        {
            "description": "Dataset CSV file (50 MB)",
            "request": {
                "content_type": "text/csv",
                "size": 50 * 1024 * 1024,
                "filename": "training_data.csv",
                "operation": "store"
            },
            "expected_backends": [StorageBackendType.HUGGINGFACE, StorageBackendType.IPFS, StorageBackendType.S3]
        },
        {
            "description": "Small text document (100 KB)",
            "request": {
                "content_type": "application/pdf",
                "size": 100 * 1024,
                "filename": "report.pdf",
                "operation": "store"
            },
            "expected_backends": [StorageBackendType.IPFS]
        },
        {
            "description": "Retrieving an image",
            "request": {
                "content_type": "image/png",
                "size": 2 * 1024 * 1024,
                "filename": "diagram.png",
                "operation": "retrieve"
            },
            "expected_backends": [StorageBackendType.IPFS, StorageBackendType.S3]
        }
    ]
    
    # Run all test cases
    for case in test_cases:
        print(f"\n{case['description']}:")
        print(f"  Request: {json.dumps(case['request'], indent=2)}")
        
        # Select backend
        start_time = time.time()
        backend, reason = router.select_backend(case["request"])
        decision_time = (time.time() - start_time) * 1000  # ms
        
        # Print results
        print(f"  Selected: {backend.value}")
        print(f"  Reason: {reason}")
        print(f"  Decision time: {decision_time:.2f} ms")
        
        # Check if result matches expected backends
        if backend in case["expected_backends"]:
            print(f"  ✓ Result matches one of the expected backends")
        else:
            print(f"  ✗ Result does not match expected backends: {[b.value for b in case['expected_backends']]}")
    
    # Print router statistics
    print("\nRouter Statistics:")
    stats = router.get_statistics()
    print(f"  Total decisions: {stats['router_metrics']['total_requests']}")
    print(f"  Decision counts: {stats['router_metrics']['decision_counts']}")


if __name__ == "__main__":
    # Run the demonstration
    demonstrate_router_usage()
    
    # Run the tests
    unittest.main()