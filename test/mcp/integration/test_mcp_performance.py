#!/usr/bin/env python3
"""
Performance tests for the MCP server.

This module implements performance testing, benchmarking and stress testing
for the MCP server to evaluate its behavior under different load conditions.
"""

import os
import sys
import time
import json
import unittest
import statistics
import tempfile
import threading
import anyio
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Any, Optional

# Ensure the package is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    print("FastAPI not available, skipping HTTP tests")

try:
    import anyio
    HAS_ANYIO = True
except ImportError:
    HAS_ANYIO = False
    print("AnyIO not available, skipping async tests")

try:
    # Try to import the MCP server
    from ipfs_kit_py.mcp.server_bridge import MCPServer  # Refactored import
    from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
    HAS_MCP = True
except ImportError:
    HAS_MCP = False
    print("MCP server not available, some tests will be skipped")
    # Create mock classes for testing
    class MCPServer:
        def __init__(self, **kwargs):
            self.debug_mode = kwargs.get('debug_mode', False)

        def register_with_app(self, app, prefix="/mcp"):
            pass


@unittest.skipIf(not HAS_FASTAPI or not HAS_MCP, "FastAPI or MCP server not available")
class TestMCPPerformance(unittest.TestCase):
    """Performance tests for the MCP server."""

    def setUp(self):
        """Set up the test environment."""
        self.temp_dir = tempfile.mkdtemp()

        # Create server with debugging disabled for performance tests
        self.server = MCPServer(
            debug_mode=False,
            log_level="ERROR",  # Minimize logging overhead
            persistence_path=self.temp_dir,
            isolation_mode=True
        )

        # Create FastAPI app
        self.app = FastAPI(title="MCP Performance Test")
        self.server.register_with_app(self.app)

        # Create test client
        self.client = TestClient(self.app)

        # Test data
        self.test_content = "Test content for performance testing" * 100  # ~3KB
        self.medium_content = "Medium content for performance testing" * 10000  # ~300KB
        self.large_content = "Large content for performance testing" * 100000  # ~3MB

        # Performance metrics storage
        self.metrics = {
            "endpoint_latency": {},
            "throughput": {},
            "concurrent_requests": {},
            "memory_usage": {}
        }

    def tearDown(self):
        """Clean up after tests."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def _measure_endpoint_latency(self, endpoint, method="GET", params=None, json_data=None,
                                 iterations=50):
        """Measure latency for a specific endpoint."""
        latencies = []

        for _ in range(iterations):
            start_time = time.time()

            if method.upper() == "GET":
                response = self.client.get(endpoint, params=params)
            elif method.upper() == "POST":
                response = self.client.post(endpoint, params=params, json=json_data)
            else:
                raise ValueError(f"Unsupported method: {method}")

            end_time = time.time()
            latency = (end_time - start_time) * 1000  # Convert to milliseconds
            latencies.append(latency)

            # Ensure request was successful
            self.assertEqual(response.status_code, 200)

        # Calculate statistics
        return {
            "min": min(latencies),
            "max": max(latencies),
            "mean": statistics.mean(latencies),
            "median": statistics.median(latencies),
            "p95": sorted(latencies)[int(iterations * 0.95)],
            "p99": sorted(latencies)[int(iterations * 0.99)],
            "std_dev": statistics.stdev(latencies) if len(latencies) > 1 else 0
        }

    def _measure_throughput(self, endpoint, method="GET", params=None, json_data=None,
                           duration=5, max_workers=10):
        """Measure throughput for a specific endpoint."""
        start_time = time.time()
        end_time = start_time + duration
        request_count = 0

        def make_request():
            nonlocal request_count
            if method.upper() == "GET":
                response = self.client.get(endpoint, params=params)
            elif method.upper() == "POST":
                response = self.client.post(endpoint, params=params, json=json_data)
            else:
                raise ValueError(f"Unsupported method: {method}")

            # Count only successful requests
            if response.status_code == 200:
                request_count += 1

        # Use ThreadPoolExecutor to make concurrent requests
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            while time.time() < end_time:
                # Submit requests continuously
                futures = [executor.submit(make_request) for _ in range(max_workers)]
                # Wait for all requests to complete
                for future in futures:
                    future.result()

        # Calculate throughput (requests per second)
        actual_duration = time.time() - start_time
        throughput = request_count / actual_duration

        return {
            "requests": request_count,
            "duration_seconds": actual_duration,
            "throughput_rps": throughput
        }

    def _test_concurrent_requests(self, endpoint, method="GET", params=None, json_data=None,
                                concurrency_levels=[1, 5, 10, 25, 50]):
        """Test endpoint performance under different concurrency levels."""
        results = {}

        for concurrency in concurrency_levels:
            result = self._measure_throughput(
                endpoint=endpoint,
                method=method,
                params=params,
                json_data=json_data,
                duration=5,
                max_workers=concurrency
            )
            results[concurrency] = result

        return results

    def test_health_endpoint_performance(self):
        """Measure performance of the health endpoint."""
        # Measure latency
        latency_stats = self._measure_endpoint_latency("/mcp/health")
        self.metrics["endpoint_latency"]["health"] = latency_stats

        # Ensure reasonable latency
        self.assertLess(latency_stats["mean"], 50, "Health endpoint has high latency")

        # Measure throughput
        throughput = self._measure_throughput("/mcp/health")
        self.metrics["throughput"]["health"] = throughput

        # Ensure reasonable throughput
        self.assertGreater(throughput["throughput_rps"], 100, "Health endpoint has low throughput")

        # Test concurrency
        concurrency_results = self._test_concurrent_requests("/mcp/health")
        self.metrics["concurrent_requests"]["health"] = concurrency_results

        # Ensure performance scales with concurrency
        self.assertGreater(
            concurrency_results[50]["throughput_rps"],
            concurrency_results[1]["throughput_rps"],
            "Health endpoint doesn't scale with concurrency"
        )

    def test_add_json_performance(self):
        """Measure performance of adding JSON content."""
        # Small content
        small_latency = self._measure_endpoint_latency(
            endpoint="/mcp/ipfs/add_json",
            method="POST",
            json_data={"content": self.test_content},
            iterations=20
        )
        self.metrics["endpoint_latency"]["add_json_small"] = small_latency

        # Medium content
        medium_latency = self._measure_endpoint_latency(
            endpoint="/mcp/ipfs/add_json",
            method="POST",
            json_data={"content": self.medium_content},
            iterations=10
        )
        self.metrics["endpoint_latency"]["add_json_medium"] = medium_latency

        # Large content
        large_latency = self._measure_endpoint_latency(
            endpoint="/mcp/ipfs/add_json",
            method="POST",
            json_data={"content": self.large_content},
            iterations=5
        )
        self.metrics["endpoint_latency"]["add_json_large"] = large_latency

        # Verify latency increases with content size
        self.assertLess(
            small_latency["mean"],
            medium_latency["mean"],
            "Small content should be faster than medium content"
        )
        self.assertLess(
            medium_latency["mean"],
            large_latency["mean"],
            "Medium content should be faster than large content"
        )

        # Throughput for small content
        throughput = self._measure_throughput(
            endpoint="/mcp/ipfs/add_json",
            method="POST",
            json_data={"content": self.test_content},
            duration=5
        )
        self.metrics["throughput"]["add_json"] = throughput

    def test_content_retrieval_performance(self):
        """Measure performance of content retrieval."""
        # First add a content to get a CID
        response = self.client.post(
            "/mcp/ipfs/add_json",
            json={"content": self.test_content}
        )
        self.assertEqual(response.status_code, 200)
        result = response.json()
        test_cid = result["cid"]

        # Measure latency for content retrieval
        latency_stats = self._measure_endpoint_latency(
            endpoint=f"/mcp/ipfs/cat/{test_cid}",
            iterations=30
        )
        self.metrics["endpoint_latency"]["cat"] = latency_stats

        # Ensure reasonable latency
        self.assertLess(latency_stats["p95"], 100, "Content retrieval has high latency")

        # Measure throughput
        throughput = self._measure_throughput(
            endpoint=f"/mcp/ipfs/cat/{test_cid}",
            duration=5
        )
        self.metrics["throughput"]["cat"] = throughput

        # Test concurrency
        concurrency_results = self._test_concurrent_requests(
            endpoint=f"/mcp/ipfs/cat/{test_cid}",
            concurrency_levels=[1, 5, 10, 20]
        )
        self.metrics["concurrent_requests"]["cat"] = concurrency_results

    def test_cache_performance_improvement(self):
        """Test if caching improves performance over time."""
        # First add content to get a CID
        response = self.client.post(
            "/mcp/ipfs/add_json",
            json={"content": self.medium_content}
        )
        self.assertEqual(response.status_code, 200)
        result = response.json()
        test_cid = result["cid"]

        # First request - cold cache
        cold_latencies = []
        for _ in range(5):
            start_time = time.time()
            response = self.client.get(f"/mcp/ipfs/cat/{test_cid}")
            latency = (time.time() - start_time) * 1000
            cold_latencies.append(latency)
            self.assertEqual(response.status_code, 200)

        # Warm the cache with several requests
        for _ in range(10):
            self.client.get(f"/mcp/ipfs/cat/{test_cid}")

        # Measure warm cache latency
        warm_latencies = []
        for _ in range(20):
            start_time = time.time()
            response = self.client.get(f"/mcp/ipfs/cat/{test_cid}")
            latency = (time.time() - start_time) * 1000
            warm_latencies.append(latency)
            self.assertEqual(response.status_code, 200)

        # Calculate statistics
        cold_mean = statistics.mean(cold_latencies)
        warm_mean = statistics.mean(warm_latencies)

        # Store metrics
        self.metrics["cache_performance"] = {
            "cold_mean_ms": cold_mean,
            "warm_mean_ms": warm_mean,
            "improvement_pct": (cold_mean - warm_mean) / cold_mean * 100 if cold_mean > 0 else 0
        }

        # Verify caching improves performance (at least 20% faster)
        self.assertLess(
            warm_mean,
            cold_mean * 0.8,
            "Caching doesn't significantly improve retrieval latency"
        )

    def test_api_operation_stress(self):
        """Test MCP server stability under stress."""
        # Create a large batch of operations to perform in parallel
        operations = []

        # Add various operations
        operations.extend([
            {"endpoint": "/mcp/health", "method": "GET", "data": None},
            {"endpoint": "/mcp/ipfs/add_json", "method": "POST", "data": {"content": self.test_content}},
            {"endpoint": "/mcp/ipfs/pin", "method": "POST", "data": None}  # CID will be filled in later
        ])

        # Initialize counters
        successes = 0
        failures = 0

        # Add content to get a valid CID
        response = self.client.post(
            "/mcp/ipfs/add_json",
            json={"content": "Initial content"}
        )
        test_cid = response.json()["cid"]

        # Run stress test
        stress_duration = 10  # seconds
        num_threads = 25
        start_time = time.time()
        end_time = start_time + stress_duration

        def worker():
            nonlocal successes, failures
            while time.time() < end_time:
                # Select random operation
                import random
                op = random.choice(operations)

                try:
                    if op["method"] == "GET":
                        if op["endpoint"] == "/mcp/ipfs/cat/{cid}":
                            response = self.client.get(op["endpoint"].format(cid=test_cid))
                        else:
                            response = self.client.get(op["endpoint"])
                    elif op["method"] == "POST":
                        if op["endpoint"] == "/mcp/ipfs/pin":
                            response = self.client.post(op["endpoint"], params={"cid": test_cid})
                        else:
                            response = self.client.post(op["endpoint"], json=op["data"])

                    if response.status_code == 200:
                        successes += 1
                    else:
                        failures += 1

                except Exception as e:
                    failures += 1

        # Launch worker threads
        threads = []
        for _ in range(num_threads):
            t = threading.Thread(target=worker)
            t.daemon = True
            t.start()
            threads.append(t)

        # Wait for all threads to complete
        for t in threads:
            t.join()

        # Record metrics
        actual_duration = time.time() - start_time
        self.metrics["stress_test"] = {
            "duration": actual_duration,
            "threads": num_threads,
            "successes": successes,
            "failures": failures,
            "total": successes + failures,
            "success_rate": successes / (successes + failures) if (successes + failures) > 0 else 0,
            "throughput": (successes + failures) / actual_duration
        }

        # Verify high success rate (>95%)
        success_rate = successes / (successes + failures) if (successes + failures) > 0 else 0
        self.assertGreater(
            success_rate,
            0.95,
            f"Low success rate ({success_rate:.2%}) under stress"
        )

    def tearDown(self):
        """Save performance metrics after tests."""
        # Save metrics to a file
        metrics_path = os.path.join(os.path.dirname(__file__), "test-results", "performance_metrics.json")
        os.makedirs(os.path.dirname(metrics_path), exist_ok=True)

        with open(metrics_path, "w") as f:
            json.dump(self.metrics, f, indent=2)


@unittest.skipIf(not HAS_FASTAPI or not HAS_MCP or not HAS_ANYIO,
                "FastAPI, MCP server, or AnyIO not available")
class TestMCPPerformanceAnyIO(unittest.TestCase):
    """Performance tests for the MCP server with AnyIO."""

    def setUp(self):
        """Set up the test environment."""
        self.temp_dir = tempfile.mkdtemp()

        # Create FastAPI app
        self.app = FastAPI(title="MCP Performance Test AnyIO")

        # Create server with AnyIO support
        self.server = MCPServer(
            debug_mode=False,
            log_level="ERROR",
            persistence_path=self.temp_dir,
            isolation_mode=True,
            use_anyio=True
        )

        # Register with app
        self.server.register_with_app(self.app)

        # Create test client
        self.client = TestClient(self.app)

        # Test data
        self.test_content = "Test content for AnyIO performance testing" * 100

        # Performance metrics storage
        self.metrics = {
            "endpoint_latency": {},
            "concurrent_requests": {}
        }

    def tearDown(self):
        """Clean up after tests."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    async def _async_measure_endpoint_latency(self, endpoint, method="GET",
                                            params=None, json_data=None, iterations=20):
        """Measure latency for a specific endpoint with AnyIO."""
        latencies = []

        # Create ClientSession for async requests
        for _ in range(iterations):
            start_time = time.time()

            if method.upper() == "GET":
                response = self.client.get(endpoint, params=params)
            elif method.upper() == "POST":
                response = self.client.post(endpoint, params=params, json=json_data)

            end_time = time.time()
            latency = (end_time - start_time) * 1000  # Convert to milliseconds
            latencies.append(latency)

            # Ensure request was successful
            self.assertEqual(response.status_code, 200)

        # Calculate statistics
        return {
            "min": min(latencies),
            "max": max(latencies),
            "mean": statistics.mean(latencies),
            "median": statistics.median(latencies),
            "p95": sorted(latencies)[int(iterations * 0.95)],
            "std_dev": statistics.stdev(latencies) if len(latencies) > 1 else 0
        }

    async def _async_test_concurrent_performance(self, concurrency=10):
        """Test AnyIO endpoint performance with concurrency."""
        # First get a valid CID by adding content
        response = self.client.post(
            "/mcp/ipfs/add_json",
            json={"content": self.test_content}
        )
        self.assertEqual(response.status_code, 200)
        test_cid = response.json()["cid"]

        # Create tasks for health check
        start_time = time.time()
        tasks = [self._async_request("/mcp/health") for _ in range(concurrency)]
        results = await anyio.gather(*tasks)
        end_time = time.time()

        # Calculate throughput
        total_requests = len([r for r in results if r])
        duration = end_time - start_time
        throughput = total_requests / duration if duration > 0 else 0

        # Store metrics
        self.metrics["concurrent_requests"]["health_anyio"] = {
            "concurrency": concurrency,
            "duration": duration,
            "success_count": total_requests,
            "throughput": throughput
        }

        # Test content retrieval concurrency
        start_time = time.time()
        tasks = [self._async_request(f"/mcp/ipfs/cat/{test_cid}") for _ in range(concurrency)]
        results = await anyio.gather(*tasks)
        end_time = time.time()

        # Calculate throughput
        total_requests = len([r for r in results if r])
        duration = end_time - start_time
        throughput = total_requests / duration if duration > 0 else 0

        # Store metrics
        self.metrics["concurrent_requests"]["cat_anyio"] = {
            "concurrency": concurrency,
            "duration": duration,
            "success_count": total_requests,
            "throughput": throughput
        }

    async def _async_request(self, url):
        """Make an async request and return success status."""
        try:
            response = self.client.get(url)
            return response.status_code == 200
        except Exception:
            return False

    def test_anyio_endpoint_performance(self):
        """Test performance of AnyIO endpoints."""
        # Health endpoint latency
        health_latency = anyio.run(
            self._async_measure_endpoint_latency,
            "/mcp/health"
        )
        self.metrics["endpoint_latency"]["health_anyio"] = health_latency

        # Add JSON latency (small content)
        add_json_latency = anyio.run(
            self._async_measure_endpoint_latency,
            "/mcp/ipfs/add_json",
            method="POST",
            json_data={"content": self.test_content}
        )
        self.metrics["endpoint_latency"]["add_json_anyio"] = add_json_latency

        # Test concurrent performance
        anyio.run(self._async_test_concurrent_performance, 25)

        # Save metrics to a file
        metrics_path = os.path.join(os.path.dirname(__file__), "test-results", "performance_metrics_anyio.json")
        os.makedirs(os.path.dirname(metrics_path), exist_ok=True)

        with open(metrics_path, "w") as f:
            json.dump(self.metrics, f, indent=2)


if __name__ == "__main__":
    unittest.main()
