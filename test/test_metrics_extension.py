#!/usr/bin/env python3
"""
Test script for the metrics extension.

This script tests the basic functionality of the metrics and monitoring system.
"""

import os
import sys
import logging
import asyncio
import json
import uuid
import time
import random
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add the parent directory to the path to import modules
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Try to import required modules
try:
    import prometheus_client
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    HAS_REQUIREMENTS = True
except ImportError:
    logger.warning("Missing required packages. Please install: prometheus_client, fastapi")
    HAS_REQUIREMENTS = False

# Import the metrics extension
try:
    from mcp_extensions.metrics_extension import (
        create_metrics_router,
        collect_system_metrics,
        collect_backend_metrics,
        update_metrics_status,
        metrics,
        alerts,
        alert_rules,
        AlertRule,
        evaluate_alert_rules
    )
    HAS_METRICS_EXTENSION = True
except ImportError as e:
    logger.error(f"Failed to import metrics extension: {e}")
    HAS_METRICS_EXTENSION = False

# Mock storage backends for testing
mock_storage_backends = {
    "ipfs": {"available": True, "simulation": False},
    "local": {"available": True, "simulation": False},
    "s3": {"available": True, "simulation": False},
    "filecoin": {"available": True, "simulation": False},
    "storacha": {"available": False, "simulation": True},
    "huggingface": {"available": True, "simulation": False},
    "lassie": {"available": False, "simulation": True}
}

# Test functions
def test_metrics_creation():
    """Test that metrics are correctly created."""
    logger.info("Testing metrics creation")

    if not HAS_METRICS_EXTENSION:
        logger.error("Metrics extension not available")
        return False

    try:
        # Check that core metrics exist
        essential_metrics = [
            "system_cpu_usage",
            "system_memory_usage",
            "system_disk_usage",
            "api_requests_total",
            "api_request_duration",
            "backend_availability",
            "backend_operations_total",
            "error_count"
        ]

        for metric_name in essential_metrics:
            if metric_name not in metrics:
                logger.error(f"Essential metric '{metric_name}' not found")
                return False

        logger.info("All essential metrics exist")
        return True
    except Exception as e:
        logger.error(f"Error testing metrics creation: {e}")
        return False

def test_system_metrics_collection():
    """Test system metrics collection."""
    logger.info("Testing system metrics collection")

    if not HAS_METRICS_EXTENSION:
        logger.error("Metrics extension not available")
        return False

    try:
        # Initial values might be None
        initial_cpu = getattr(metrics["system_cpu_usage"], "_value", None)

        # Collect metrics
        collect_system_metrics()

        # Check that values are updated
        updated_cpu = getattr(metrics["system_cpu_usage"], "_value", None)
        updated_memory = getattr(metrics["system_memory_usage"], "_value", None)
        updated_disk = getattr(metrics["system_disk_usage"], "_value", None)

        if updated_cpu is None or updated_memory is None or updated_disk is None:
            logger.error("System metrics collection failed to update values")
            return False

        logger.info(f"System metrics: CPU={updated_cpu}%, Memory={updated_memory}%, Disk={updated_disk}%")
        return True
    except Exception as e:
        logger.error(f"Error testing system metrics collection: {e}")
        return False

def test_backend_metrics_collection():
    """Test backend metrics collection."""
    logger.info("Testing backend metrics collection")

    if not HAS_METRICS_EXTENSION:
        logger.error("Metrics extension not available")
        return False

    try:
        # Collect backend metrics
        collect_backend_metrics(mock_storage_backends)

        # Check that backend availability metrics are updated
        for backend in mock_storage_backends:
            try:
                availability = metrics["backend_availability"].labels(backend=backend)._value
                if availability is None:
                    logger.warning(f"Backend {backend} availability is None")
                else:
                    expected = 1 if mock_storage_backends[backend]["available"] else 0
                    if availability != expected:
                        logger.error(f"Backend {backend} availability should be {expected}, got {availability}")
                        return False
            except Exception as e:
                logger.error(f"Error checking {backend} availability: {e}")
                return False

        logger.info("Backend metrics collected successfully")
        return True
    except Exception as e:
        logger.error(f"Error testing backend metrics collection: {e}")
        return False

def test_alert_rules():
    """Test alert rules functionality."""
    logger.info("Testing alert rules functionality")

    if not HAS_METRICS_EXTENSION:
        logger.error("Metrics extension not available")
        return False

    try:
        # Create a test alert rule for CPU usage
        rule = AlertRule(
            name="test_cpu_alert",
            description="Test CPU usage alert",
            metric="system_cpu_usage",
            condition="> 90",
            threshold=90.0,
            severity="critical",
            duration=0,
            enabled=True
        )

        # Add rule to the rules dictionary
        alert_rules[rule.name] = rule.dict()

        # Force CPU usage value for testing
        # In a real scenario, this would come from actual system metrics
        if hasattr(metrics["system_cpu_usage"], "_value"):
            original_value = metrics["system_cpu_usage"]._value
            # Set to a high value to trigger the alert
            metrics["system_cpu_usage"].set(95.0)
        else:
            logger.warning("Could not access CPU usage metric value")
            return False

        # Evaluate alert rules
        alerts.clear()  # Clear any existing alerts
        evaluate_alert_rules()

        # Check if our alert was triggered
        alert_found = False
        for alert in alerts:
            if alert["name"] == rule.name and alert["status"] == "firing":
                alert_found = True
                break

        if not alert_found:
            logger.error("Alert was not triggered when condition was met")
            return False

        # Now set CPU to a value that shouldn't trigger the alert
        metrics["system_cpu_usage"].set(50.0)

        # Re-evaluate
        evaluate_alert_rules()

        # Check if our alert was resolved
        for alert in alerts:
            if alert["name"] == rule.name:
                if alert["status"] != "resolved":
                    logger.error("Alert was not resolved when condition was no longer met")
                    return False

        # Restore original value
        metrics["system_cpu_usage"].set(original_value if original_value is not None else 0)

        logger.info("Alert rules functionality working correctly")
        return True
    except Exception as e:
        logger.error(f"Error testing alert rules: {e}")
        return False

def test_prometheus_format():
    """Test Prometheus exposition format generation."""
    logger.info("Testing Prometheus format generation")

    if not HAS_REQUIREMENTS or not HAS_METRICS_EXTENSION:
        logger.error("Required packages not available")
        return False

    try:
        # Generate Prometheus format output
        output = prometheus_client.generate_latest(prometheus_client.REGISTRY)

        # Check if output is valid and contains our metrics
        if not output or len(output) < 100:
            logger.error("Prometheus format output is too short or empty")
            return False

        output_str = output.decode('utf-8')

        # Check for presence of some of our metrics in the output
        if 'mcp_system_cpu_usage' not in output_str:
            logger.error("CPU usage metric not found in Prometheus output")
            return False

        if 'mcp_system_memory_usage' not in output_str:
            logger.error("Memory usage metric not found in Prometheus output")
            return False

        logger.info("Prometheus format generation working correctly")
        return True
    except Exception as e:
        logger.error(f"Error testing Prometheus format: {e}")
        return False

def test_fastapi_integration():
    """Test FastAPI integration."""
    logger.info("Testing FastAPI integration")

    if not HAS_REQUIREMENTS or not HAS_METRICS_EXTENSION:
        logger.error("Required packages not available")
        return False

    try:
        # Create a test FastAPI app
        app = FastAPI()

        # Create and add a metrics router
        metrics_router = create_metrics_router("/api/v0")
        app.include_router(metrics_router)

        # Create a test client
        client = TestClient(app)

        # Test the metrics endpoint
        response = client.get("/api/v0/metrics")
        if response.status_code != 200:
            logger.error(f"Metrics endpoint returned status code {response.status_code}")
            return False

        # Test the metrics status endpoint
        response = client.get("/api/v0/metrics/status")
        if response.status_code != 200:
            logger.error(f"Metrics status endpoint returned status code {response.status_code}")
            return False

        # Check the response JSON
        data = response.json()
        if not data.get("success"):
            logger.error("Metrics status didn't return success=True")
            return False

        logger.info("FastAPI integration working correctly")
        return True
    except Exception as e:
        logger.error(f"Error testing FastAPI integration: {e}")
        return False

def simulate_api_traffic():
    """Simulate API traffic to generate metrics."""
    logger.info("Simulating API traffic")

    if not HAS_METRICS_EXTENSION:
        logger.error("Metrics extension not available")
        return False

    try:
        # Simulate some API requests
        methods = ["GET", "POST", "PUT", "DELETE"]
        endpoints = ["/api/v0/ipfs/add", "/api/v0/ipfs/cat", "/api/v0/storage/health"]
        statuses = ["200", "404", "500"]

        for _ in range(20):
            method = random.choice(methods)
            endpoint = random.choice(endpoints)
            status = random.choice(statuses)

            # Record request in counter
            metrics["api_requests_total"].labels(
                method=method, endpoint=endpoint, status=status
            ).inc()

            # Record request duration
            metrics["api_request_duration"].labels(
                method=method, endpoint=endpoint
            ).observe(random.uniform(0.1, 2.0))

            # Small delay between requests
            time.sleep(0.1)

        # Simulate some backend operations
        backends = ["ipfs", "s3", "filecoin"]
        operations = ["read", "write", "delete"]
        statuses = ["success", "error"]

        for _ in range(15):
            backend = random.choice(backends)
            operation = random.choice(operations)
            status = random.choice(statuses)

            # Record operation in counter
            metrics["backend_operations_total"].labels(
                backend=backend, operation=operation, status=status
            ).inc()

            # Record operation duration
            metrics["backend_operation_duration"].labels(
                backend=backend, operation=operation
            ).observe(random.uniform(0.5, 5.0))

            # Record content size
            metrics["content_size"].labels(
                backend=backend
            ).observe(random.randint(1024, 10*1024*1024))

            # Small delay between operations
            time.sleep(0.1)

        logger.info("API traffic simulation completed")
        return True
    except Exception as e:
        logger.error(f"Error simulating API traffic: {e}")
        return False

def run_all_tests():
    """Run all tests."""
    logger.info("Starting metrics extension tests")

    # Check requirements
    if not HAS_REQUIREMENTS:
        logger.error("Required packages are missing. Please install prometheus_client and fastapi")
        return False

    if not HAS_METRICS_EXTENSION:
        logger.error("Metrics extension not available or could not be imported")
        return False

    # Run tests and collect results
    results = {
        "metrics_creation": test_metrics_creation(),
        "system_metrics_collection": test_system_metrics_collection(),
        "backend_metrics_collection": test_backend_metrics_collection(),
        "alert_rules": test_alert_rules(),
        "prometheus_format": test_prometheus_format(),
        "fastapi_integration": test_fastapi_integration(),
        "simulate_api_traffic": simulate_api_traffic()
    }

    # Check if all tests passed
    all_passed = all(results.values())

    if all_passed:
        logger.info("✅ All tests passed!")
    else:
        logger.error("❌ Some tests failed!")
        failed_tests = [test for test, result in results.items() if not result]
        logger.error(f"Failed tests: {failed_tests}")

    return all_passed

# Main entry point
if __name__ == "__main__":
    run_all_tests()
