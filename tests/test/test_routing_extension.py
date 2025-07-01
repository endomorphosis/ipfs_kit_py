#!/usr/bin/env python3
"""
Test script for the routing extension.

This script tests the basic functionality of the optimized data routing system.
"""

import os
import sys
import logging
import asyncio
import json
import uuid
import time
import random
from typing import Dict, Any, List

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
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    HAS_REQUIREMENTS = True
except ImportError:
    logger.warning("Missing required packages. Please install: fastapi")
    HAS_REQUIREMENTS = False

# Import the routing extension
try:
    from mcp_extensions.routing_extension import (
        create_routing_router,
        initialize,
        make_routing_decision,
        RoutingRequest,
        ContentAttributes,
        update_routing_status,
        routing_config,
        routing_policies
    )
    HAS_ROUTING_EXTENSION = True
except ImportError as e:
    logger.error(f"Failed to import routing extension: {e}")
    HAS_ROUTING_EXTENSION = False

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

# Sample content types for testing
CONTENT_TYPES = {
    "text": "text/plain",
    "html": "text/html",
    "json": "application/json",
    "xml": "application/xml",
    "image": "image/jpeg",
    "video": "video/mp4",
    "audio": "audio/mp3",
    "pdf": "application/pdf",
    "model": "application/octet-stream+model",
    "dataset": "application/octet-stream+dataset"
}

# Test functions
def test_routing_initialization():
    """Test that routing system is correctly initialized."""
    logger.info("Testing routing initialization")
    
    if not HAS_ROUTING_EXTENSION:
        logger.error("Routing extension not available")
        return False
    
    try:
        # Check that routing config exists
        if not routing_config:
            logger.error("Routing configuration not initialized")
            return False
        
        # Check that routing policies exist
        if not routing_policies or len(routing_policies) < 3:  # Should have at least 3 default policies
            logger.error("Routing policies not properly initialized")
            return False
        
        # Verify critical policies exist
        required_policies = ["balanced", "performance", "cost-effective"]
        for policy in required_policies:
            if policy not in routing_policies:
                logger.error(f"Required policy '{policy}' is missing")
                return False
        
        logger.info("Routing initialization successful")
        return True
    except Exception as e:
        logger.error(f"Error testing routing initialization: {e}")
        return False

def test_basic_routing_decision():
    """Test basic routing decision functionality."""
    logger.info("Testing basic routing decision")
    
    if not HAS_ROUTING_EXTENSION:
        logger.error("Routing extension not available")
        return False
    
    try:
        # Update backends status
        update_routing_status(mock_storage_backends)
        
        # Create a basic routing request
        request = RoutingRequest(
            operation="read",
            content_attributes=ContentAttributes(
                content_type=CONTENT_TYPES["text"],
                size_bytes=1024*10
            )
        )
        
        # Make a routing decision
        decision = make_routing_decision(request)
        
        # Check that a decision was made with a primary backend
        if not decision or not decision.primary_backend:
            logger.error("No routing decision was made")
            return False
        
        # Verify primary backend is available
        if decision.primary_backend not in mock_storage_backends or not mock_storage_backends[decision.primary_backend]["available"]:
            logger.error(f"Selected backend {decision.primary_backend} is not available")
            return False
        
        # Verify that backend scores were calculated
        if not decision.backend_scores or len(decision.backend_scores) == 0:
            logger.error("No backend scores were calculated")
            return False
        
        logger.info(f"Routing decision: primary={decision.primary_backend}, replicas={decision.replicas}")
        logger.info(f"Applied policy: {decision.applied_policy}")
        
        return True
    except Exception as e:
        logger.error(f"Error testing basic routing decision: {e}")
        return False

def test_content_type_routing():
    """Test content-type-aware routing."""
    logger.info("Testing content-type-aware routing")
    
    if not HAS_ROUTING_EXTENSION:
        logger.error("Routing extension not available")
        return False
    
    try:
        # Update backends status
        update_routing_status(mock_storage_backends)
        
        # Test routing for different content types
        content_type_results = {}
        
        for content_name, content_type in CONTENT_TYPES.items():
            # Create routing request for this content type
            request = RoutingRequest(
                operation="read",
                content_attributes=ContentAttributes(
                    content_type=content_type,
                    size_bytes=1024*1024*10  # 10MB
                )
            )
            
            # Make routing decision
            decision = make_routing_decision(request)
            
            # Store result
            content_type_results[content_name] = {
                "content_type": content_type,
                "primary_backend": decision.primary_backend,
                "replicas": decision.replicas,
                "applied_policy": decision.applied_policy
            }
        
        # Verify that different content types get different backends
        # For example, models should prefer huggingface if available
        if "model" in content_type_results and "huggingface" in mock_storage_backends and mock_storage_backends["huggingface"]["available"]:
            model_backend = content_type_results["model"]["primary_backend"]
            if model_backend != "huggingface":
                logger.warning(f"Model content type did not select huggingface as primary backend: {model_backend}")
        
        # Video content should prefer high-throughput backends (typically S3)
        if "video" in content_type_results and "s3" in mock_storage_backends and mock_storage_backends["s3"]["available"]:
            video_backend = content_type_results["video"]["primary_backend"]
            if video_backend != "s3":
                logger.warning(f"Video content type did not select S3 as primary backend: {video_backend}")
        
        # Print summary
        logger.info("Content type routing results:")
        for content_name, result in content_type_results.items():
            logger.info(f"  {content_name}: {result['primary_backend']}")
        
        return True
    except Exception as e:
        logger.error(f"Error testing content type routing: {e}")
        return False

def test_policy_based_routing():
    """Test policy-based routing decisions."""
    logger.info("Testing policy-based routing")
    
    if not HAS_ROUTING_EXTENSION:
        logger.error("Routing extension not available")
        return False
    
    try:
        # Update backends status
        update_routing_status(mock_storage_backends)
        
        # Test routing with different policies
        policy_results = {}
        test_policies = ["performance", "cost-effective", "balanced", "archive"]
        
        for policy_name in test_policies:
            if policy_name not in routing_policies:
                logger.warning(f"Policy '{policy_name}' not available for testing")
                continue
            
            # Create routing request with this policy
            request = RoutingRequest(
                operation="read",
                policy_name=policy_name,
                content_attributes=ContentAttributes(
                    content_type=CONTENT_TYPES["image"],
                    size_bytes=1024*1024*50  # 50MB
                )
            )
            
            # Make routing decision
            decision = make_routing_decision(request)
            
            # Store result
            policy_results[policy_name] = {
                "primary_backend": decision.primary_backend,
                "replicas": decision.replicas,
                "decision_time_ms": decision.decision_time_ms,
                "top_scores": [
                    {"backend": score.backend, "score": score.score, "cost": score.cost_score, "perf": score.performance_score} 
                    for score in decision.backend_scores[:3]
                ] if decision.backend_scores else []
            }
        
        # Verify that different policies select different backends
        # Performance policy should value speed over cost
        if "performance" in policy_results and "cost-effective" in policy_results:
            perf_backend = policy_results["performance"]["primary_backend"]
            cost_backend = policy_results["cost-effective"]["primary_backend"]
            
            if perf_backend == cost_backend:
                logger.warning(f"Performance policy and cost-effective policy selected the same backend: {perf_backend}")
        
        # Archive policy should provide more replicas than others
        if "archive" in policy_results and "balanced" in policy_results:
            archive_replicas = len(policy_results["archive"]["replicas"])
            balanced_replicas = len(policy_results["balanced"]["replicas"])
            
            if archive_replicas <= balanced_replicas:
                logger.warning(f"Archive policy ({archive_replicas} replicas) did not provide more replicas than balanced policy ({balanced_replicas} replicas)")
        
        # Print summary
        logger.info("Policy-based routing results:")
        for policy_name, result in policy_results.items():
            logger.info(f"  {policy_name}: primary={result['primary_backend']}, replicas={len(result['replicas'])}")
        
        return True
    except Exception as e:
        logger.error(f"Error testing policy-based routing: {e}")
        return False

def test_geographic_routing():
    """Test geographic-based routing decisions."""
    logger.info("Testing geographic routing")
    
    if not HAS_ROUTING_EXTENSION:
        logger.error("Routing extension not available")
        return False
    
    try:
        # Update backends status
        update_routing_status(mock_storage_backends)
        
        # Test routing with different regions
        region_results = {}
        test_regions = ["us-east", "eu-west", "ap-east"]
        
        for region in test_regions:
            # Create routing request with this region
            request = RoutingRequest(
                operation="read",
                client_region=region,
                content_attributes=ContentAttributes(
                    content_type=CONTENT_TYPES["video"],
                    size_bytes=1024*1024*100  # 100MB
                )
            )
            
            # Make routing decision
            decision = make_routing_decision(request)
            
            # Store result
            region_results[region] = {
                "primary_backend": decision.primary_backend,
                "replicas": decision.replicas,
                "decision_region": decision.client_region
            }
        
        # Print summary
        logger.info("Geographic routing results:")
        for region, result in region_results.items():
            logger.info(f"  {region}: {result['primary_backend']}")
        
        return True
    except Exception as e:
        logger.error(f"Error testing geographic routing: {e}")
        return False

def test_fastapi_integration():
    """Test FastAPI integration."""
    logger.info("Testing FastAPI integration")
    
    if not HAS_REQUIREMENTS or not HAS_ROUTING_EXTENSION:
        logger.error("Required packages not available")
        return False
    
    try:
        # Create a test FastAPI app
        app = FastAPI()
        
        # Create and add a routing router
        routing_router = create_routing_router("/api/v0")
        app.include_router(routing_router)
        
        # Create a test client
        client = TestClient(app)
        
        # Test the routing status endpoint
        response = client.get("/api/v0/routing/status")
        if response.status_code != 200:
            logger.error(f"Routing status endpoint returned status code {response.status_code}")
            return False
        
        # Check the response JSON
        data = response.json()
        if not data.get("success"):
            logger.error("Routing status didn't return success=True")
            return False
        
        # Test the routing decision endpoint
        request_data = {
            "operation": "read",
            "content_attributes": {
                "content_type": "image/jpeg",
                "size_bytes": 1024*1024*5
            }
        }
        
        response = client.post("/api/v0/routing/decision", json=request_data)
        if response.status_code != 200:
            logger.error(f"Routing decision endpoint returned status code {response.status_code}")
            return False
        
        decision_data = response.json()
        if not decision_data.get("success") or not decision_data.get("primary_backend"):
            logger.error("Routing decision failed or didn't return a primary backend")
            return False
        
        logger.info("FastAPI integration working correctly")
        return True
    except Exception as e:
        logger.error(f"Error testing FastAPI integration: {e}")
        return False

def test_simulation():
    """Test routing simulation."""
    logger.info("Testing routing simulation")
    
    if not HAS_REQUIREMENTS or not HAS_ROUTING_EXTENSION:
        logger.error("Required packages not available")
        return False
    
    try:
        # Create a test FastAPI app
        app = FastAPI()
        
        # Create and add a routing router
        routing_router = create_routing_router("/api/v0")
        app.include_router(routing_router)
        
        # Create a test client
        client = TestClient(app)
        
        # Run a simulation with 20 requests
        response = client.post("/api/v0/routing/simulate?num_requests=20")
        
        if response.status_code != 200:
            logger.error(f"Routing simulation endpoint returned status code {response.status_code}")
            return False
        
        data = response.json()
        if not data.get("success") or not data.get("simulation_results"):
            logger.error("Routing simulation failed or didn't return results")
            return False
        
        logger.info(f"Simulation completed with {len(data['simulation_results'])} results")
        logger.info(f"Backend distribution: {data['summary']['backend_distribution']}")
        
        return True
    except Exception as e:
        logger.error(f"Error testing routing simulation: {e}")
        return False

def run_all_tests():
    """Run all tests."""
    logger.info("Starting routing extension tests")
    
    # Check requirements
    if not HAS_REQUIREMENTS:
        logger.error("Required packages are missing. Please install fastapi")
        return False
    
    if not HAS_ROUTING_EXTENSION:
        logger.error("Routing extension not available or could not be imported")
        return False
    
    # Initialize the routing system
    initialize()
    
    # Run tests and collect results
    results = {
        "routing_initialization": test_routing_initialization(),
        "basic_routing_decision": test_basic_routing_decision(),
        "content_type_routing": test_content_type_routing(),
        "policy_based_routing": test_policy_based_routing(),
        "geographic_routing": test_geographic_routing(),
        "fastapi_integration": test_fastapi_integration(),
        "simulation": test_simulation()
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