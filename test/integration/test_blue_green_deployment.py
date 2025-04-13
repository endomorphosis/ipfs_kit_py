"""
Integration Tests for MCP Blue/Green Deployment

This module provides comprehensive integration tests for the MCP Blue/Green
deployment system, verifying that all components work together correctly.
"""

import asyncio
import json
import logging
import os
import pytest
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Generator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("blue_green_integration_tests")

# Ensure parent directory is in path for imports
parent_dir = str(Path(__file__).parent.parent.parent.absolute())
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import components to test
try:
    from ipfs_kit_py.mcp_server.blue_green_proxy import AsyncMCPServerProxy, DeploymentMode
    from ipfs_kit_py.mcp_server.metrics_collector import MetricsCollector, ServerType
    from ipfs_kit_py.mcp_server.response_validator import ResponseValidator
    from ipfs_kit_py.mcp_server.traffic_controller import TrafficController, TrafficAction
    COMPONENTS_AVAILABLE = True
except ImportError as e:
    logger.error(f"Failed to import Blue/Green components: {e}")
    COMPONENTS_AVAILABLE = False

# Test fixtures
@pytest.fixture
async def config() -> Dict[str, Any]:
    """Fixture that provides test configuration."""
    # Create a test-specific configuration
    return {
        "blue": {
            "ipfs": {
                "api_url": "http://localhost:5001",
                "gateway_url": "http://localhost:8080"
            },
            "storage": {
                "backends": ["local"],
                "default_backend": "local",
                "local": {
                    "path": "test/data/storage_blue"
                }
            }
        },
        "green": {
            "ipfs": {
                "api_url": "http://localhost:5001",
                "gateway_url": "http://localhost:8080"
            },
            "storage": {
                "backends": ["local"],
                "default_backend": "local",
                "local": {
                    "path": "test/data/storage_green"
                }
            }
        },
        "deployment": {
            "mode": "gradual",
            "green_percentage": 50,
            "step_size": 10,
            "evaluation_interval": 5
        },
        "validation": {
            "enabled": True,
            "similarity_threshold": 90.0
        },
        "monitoring": {
            "enabled": True,
            "logging": {
                "level": "INFO"
            }
        },
        "stats_dir": "test/data/stats"
    }

@pytest.fixture
async def mock_blue_response() -> Dict[str, Any]:
    """Fixture that provides a mock blue server response."""
    return {
        "success": True,
        "cid": "QmTest123Blue",
        "data": {
            "name": "test-file",
            "size": 1024,
            "type": "document"
        },
        "timestamp": time.time(),
        "response_id": "blue-1"
    }

@pytest.fixture
async def mock_green_response() -> Dict[str, Any]:
    """Fixture that provides a mock green server response."""
    return {
        "success": True,
        "cid": "QmTest123Green",
        "data": {
            "name": "test-file",
            "size": 1024,
            "type": "document",
            "additional_field": "extra info"
        },
        "timestamp": time.time(),
        "response_id": "green-1"
    }

@pytest.fixture
async def metrics_collector(config) -> Generator[MetricsCollector, None, None]:
    """Fixture that provides a metrics collector instance."""
    collector = MetricsCollector(config.get("monitoring", {}))
    yield collector

@pytest.fixture
async def response_validator(config) -> Generator[ResponseValidator, None, None]:
    """Fixture that provides a response validator instance."""
    validator = ResponseValidator(config.get("validation", {}))
    yield validator

@pytest.fixture
async def traffic_controller(config) -> Generator[TrafficController, None, None]:
    """Fixture that provides a traffic controller instance."""
    controller = TrafficController(config.get("deployment", {}))
    yield controller

@pytest.fixture
async def proxy(config) -> Generator[AsyncMCPServerProxy, None, None]:
    """Fixture that provides a proxy instance with mocked servers."""
    proxy = AsyncMCPServerProxy(config)
    
    # Don't actually start real servers in tests
    proxy.running = True
    proxy.blue_healthy = True
    proxy.green_healthy = True
    
    yield proxy
    
    # Clean up
    proxy.running = False

# Mock classes for testing without actual server implementations
class MockServer:
    """Mock server that returns predefined responses."""
    
    def __init__(self, responses: Dict[str, Any]):
        self.responses = responses
        self.requests = []
    
    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a request by returning a predefined response."""
        self.requests.append(request)
        # Add a small delay to simulate processing time
        await asyncio.sleep(0.01)
        return self.responses.get(request.get("type", "default"), 
                                 self.responses.get("default", {"success": True}))
    
    async def check_health(self) -> Dict[str, Any]:
        """Return a mock health check response."""
        return {"success": True, "status": "healthy"}

# Test cases

@pytest.mark.asyncio
async def test_metrics_collector_records_requests(metrics_collector):
    """Test that metrics collector correctly records request metrics."""
    # Record some test metrics
    metrics_collector.record_request(ServerType.BLUE, True, 0.1, "test_endpoint")
    metrics_collector.record_request(ServerType.BLUE, False, 0.2, "test_endpoint")
    metrics_collector.record_request(ServerType.GREEN, True, 0.15, "test_endpoint")
    
    # Get metrics summary
    summary = metrics_collector.get_metrics_summary()
    
    # Verify metrics were recorded
    assert summary["blue"]["requests"] == 2
    assert summary["blue"]["success_rate"] == 50.0  # 1 of 2 requests successful
    assert summary["green"]["requests"] == 1
    assert summary["green"]["success_rate"] == 100.0  # 1 of 1 requests successful
    
    # Verify detailed metrics
    detailed = metrics_collector.get_detailed_metrics()
    assert detailed["blue"]["requests"]["by_endpoint"]["test_endpoint"]["total"] == 2
    assert detailed["blue"]["requests"]["by_endpoint"]["test_endpoint"]["successes"] == 1
    assert detailed["blue"]["requests"]["by_endpoint"]["test_endpoint"]["failures"] == 1

@pytest.mark.asyncio
async def test_response_validator_compares_responses(response_validator, mock_blue_response, mock_green_response):
    """Test that response validator correctly compares responses."""
    # Compare identical responses
    identical_result = response_validator.validate(mock_blue_response, mock_blue_response)
    assert identical_result["identical"] == True
    assert identical_result["compatible"] == True
    
    # Compare different responses
    different_result = response_validator.validate(mock_blue_response, mock_green_response)
    assert different_result["identical"] == False
    
    # Check if the CID difference was detected (it's in critical fields)
    assert "cid" in different_result.get("critical_fields", [])
    
    # Create more compatible responses for testing
    compatible_blue = mock_blue_response.copy()
    compatible_green = compatible_blue.copy()
    compatible_green["response_id"] = "green-2"  # This is in ignored fields
    
    compatible_result = response_validator.validate(compatible_blue, compatible_green)
    assert compatible_result["identical"] == False
    assert compatible_result["compatible"] == True
    assert compatible_result["critical_difference"] == False

@pytest.mark.asyncio
async def test_traffic_controller_adjusts_traffic(traffic_controller):
    """Test that traffic controller correctly adjusts traffic distribution."""
    # Check initial state
    assert traffic_controller.green_percentage == 50  # From fixture config
    
    # Test traffic increase
    result = traffic_controller.adjust_traffic(TrafficAction.INCREASE_GREEN)
    assert result["green_percentage"] > 50
    assert result["changed"] == True
    
    # Test traffic decrease
    prev_percentage = traffic_controller.green_percentage
    result = traffic_controller.adjust_traffic(TrafficAction.DECREASE_GREEN)
    assert result["green_percentage"] < prev_percentage
    assert result["changed"] == True
    
    # Test all blue
    result = traffic_controller.adjust_traffic(TrafficAction.ALL_BLUE)
    assert result["green_percentage"] == 0
    assert result["changed"] == True
    
    # Test all green
    result = traffic_controller.adjust_traffic(TrafficAction.ALL_GREEN)
    assert result["green_percentage"] == 100
    assert result["changed"] == True

@pytest.mark.asyncio
async def test_traffic_controller_evaluates_metrics(traffic_controller):
    """Test that traffic controller correctly evaluates metrics."""
    # Create some test metrics
    metrics = {
        "blue": {
            "success_rate": 99.9,
            "avg_response_time": 0.1,
            "health": {"status": True}
        },
        "green": {
            "success_rate": 99.8,
            "avg_response_time": 0.12,
            "health": {"status": True}
        }
    }
    
    # Create validation stats
    validation_stats = {
        "total_validations": 100,
        "identical_rate": 95.0,
        "compatible_rate": 99.5,
        "critical_difference_rate": 0.0,
        "recommendations": {
            "action": "increase_green_traffic",
            "confidence": "high"
        }
    }
    
    # Set up traffic controller for testing
    traffic_controller.green_percentage = 50
    traffic_controller.state["promotion_eligible"] = True
    
    # Evaluate metrics
    action = traffic_controller.evaluate(metrics, validation_stats)
    
    # Verify action is to increase green traffic
    assert action == TrafficAction.INCREASE_GREEN
    
    # Test with poor green performance
    bad_metrics = {
        "blue": {
            "success_rate": 99.9,
            "avg_response_time": 0.1,
            "health": {"status": True}
        },
        "green": {
            "success_rate": 95.0,  # Below threshold
            "avg_response_time": 0.3,  # Much slower
            "health": {"status": True}
        }
    }
    
    # Evaluate bad metrics
    action = traffic_controller.evaluate(bad_metrics, validation_stats)
    
    # Verify action is to decrease green traffic
    assert action == TrafficAction.DECREASE_GREEN

@pytest.mark.asyncio
async def test_proxy_route_selection(proxy, config):
    """Test that proxy correctly routes requests based on mode."""
    # Set up mock servers
    blue_responses = {"default": {"success": True, "server": "blue"}}
    green_responses = {"default": {"success": True, "server": "green"}}
    
    proxy.blue_server = MockServer(blue_responses)
    proxy.green_server = MockServer(green_responses)
    
    # Test blue mode
    proxy.mode = DeploymentMode.BLUE
    response = await proxy.handle_request({"type": "test"})
    assert response["server"] == "blue"
    
    # Test green mode
    proxy.mode = DeploymentMode.GREEN
    response = await proxy.handle_request({"type": "test"})
    assert response["server"] == "green"
    
    # Test parallel mode
    proxy.mode = DeploymentMode.PARALLEL
    response = await proxy.handle_request({"type": "test"})
    assert response["server"] == "green"  # Parallel returns green response
    
    # Verify both servers were called in parallel mode
    assert len(proxy.blue_server.requests) == 2  # Blue mode + Parallel mode
    assert len(proxy.green_server.requests) == 2  # Green mode + Parallel mode

@pytest.mark.asyncio
async def test_proxy_gradual_routing(proxy, config):
    """Test gradual traffic routing distribution."""
    # Set up mock servers
    blue_responses = {"default": {"success": True, "server": "blue"}}
    green_responses = {"default": {"success": True, "server": "green"}}
    
    proxy.blue_server = MockServer(blue_responses)
    proxy.green_server = MockServer(green_responses)
    
    # Force gradual mode with fixed green percentage for testing
    proxy.mode = DeploymentMode.GRADUAL
    proxy.green_percentage = 100  # All requests should go to green
    
    # Make multiple requests
    results = []
    for _ in range(10):
        response = await proxy.handle_request({"type": "test"})
        results.append(response["server"])
    
    # All should be routed to green
    assert all(r == "green" for r in results)
    
    # Now test with 0% green
    proxy.green_percentage = 0
    
    results = []
    for _ in range(10):
        response = await proxy.handle_request({"type": "test"})
        results.append(response["server"])
    
    # All should be routed to blue
    assert all(r == "blue" for r in results)

@pytest.mark.asyncio
async def test_integrated_components(config, mock_blue_response, mock_green_response):
    """Test integration between all components."""
    # Create instances
    metrics_collector = MetricsCollector(config.get("monitoring", {}))
    response_validator = ResponseValidator(config.get("validation", {}))
    traffic_controller = TrafficController(config.get("deployment", {}))
    
    # Create proxy with mock servers
    proxy = AsyncMCPServerProxy(config)
    proxy.metrics_collector = metrics_collector
    proxy.response_validator = response_validator
    proxy.traffic_controller = traffic_controller
    
    # Set up mock servers
    blue_responses = {"test": mock_blue_response, "default": {"success": True, "server": "blue"}}
    green_responses = {"test": mock_green_response, "default": {"success": True, "server": "green"}}
    
    proxy.blue_server = MockServer(blue_responses)
    proxy.green_server = MockServer(green_responses)
    proxy.running = True
    
    # Force parallel mode to test validation
    proxy.mode = DeploymentMode.PARALLEL
    
    # Make a request that should be validated
    response = await proxy.handle_request({"type": "test"})
    
    # Verify the response came from green (parallel mode returns green)
    assert response.get("cid") == mock_green_response.get("cid")
    
    # Wait for async processing
    await asyncio.sleep(0.1)
    
    # Verify metrics were collected
    metrics_summary = metrics_collector.get_metrics_summary()
    assert metrics_summary["blue"]["requests"] == 1
    assert metrics_summary["green"]["requests"] == 1
    
    # Verify validation occurred
    validation_stats = response_validator.get_validation_stats()
    assert validation_stats["total_validations"] == 1
    
    # Test auto mode
    proxy.mode = DeploymentMode.AUTO
    
    # Create an evaluation task function
    async def evaluation_task():
        action = traffic_controller.evaluate(
            metrics_collector.get_metrics_summary(),
            response_validator.get_validation_stats()
        )
        result = traffic_controller.adjust_traffic(action)
        return result
    
    # Run evaluation
    result = await evaluation_task()
    
    # Verify that traffic was adjusted based on metrics and validation
    assert "green_percentage" in result
    assert "action" in result
    assert "changed" in result

@pytest.mark.asyncio
async def test_health_checks(proxy):
    """Test health checking functionality."""
    # Set up mock servers with specific health responses
    class MockHealthServer:
        def __init__(self, healthy: bool):
            self.healthy = healthy
        
        async def check_health(self):
            return {"success": self.healthy, "status": "healthy" if self.healthy else "unhealthy"}
    
    proxy.blue_server = MockHealthServer(True)
    proxy.green_server = MockHealthServer(False)
    
    # Perform health check
    health = await proxy.check_health()
    
    # Verify health status
    assert health["components"]["blue"]["success"] == True
    assert health["components"]["green"]["success"] == False
    assert health["status"] == "degraded"  # One server is unhealthy

if __name__ == "__main__":
    # This allows running the tests directly
    pytest.main(["-xvs", __file__])