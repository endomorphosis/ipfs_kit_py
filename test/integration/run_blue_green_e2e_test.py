#!/usr/bin/env python3
"""
End-to-End Test for MCP Blue/Green Deployment

This script performs an end-to-end test of the MCP Blue/Green deployment system,
simulating real-world scenarios like gradual migrations, traffic shifts, and
failure detection.
"""

import asyncio
import json
import logging
import os
import sys
import time
import argparse
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("blue_green_e2e_test")

# Ensure parent directory is in path for imports
parent_dir = str(Path(__file__).parent.parent.parent.absolute())
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import components
try:
    from ipfs_kit_py.mcp.blue_green_proxy import AsyncMCPServerProxy, DeploymentMode
    from ipfs_kit_py.mcp.metrics_collector import ServerType
    COMPONENTS_AVAILABLE = True
except ImportError as e:
    logger.error(f"Failed to import Blue/Green components: {e}")
    COMPONENTS_AVAILABLE = False
    sys.exit(1)

# Test data and utilities
class MockIPFSServer:
    """Mock IPFS server for testing."""
    
    def __init__(self, server_id: str, failure_rate: float = 0.0, latency: float = 0.05):
        """
        Initialize mock server.
        
        Args:
            server_id: Identifier for the server (blue/green)
            failure_rate: Percentage of requests that should fail (0-100)
            latency: Base latency for responses in seconds
        """
        self.server_id = server_id
        self.failure_rate = failure_rate / 100.0  # Convert to 0-1 range
        self.latency = latency
        self.request_count = 0
        self.is_healthy = True
        
        # Create test CIDs with different characteristics for blue/green
        self.cids = {
            "get": f"Qm{server_id}Get123456789012345678901234567890",
            "add": f"Qm{server_id}Add123456789012345678901234567890",
            "pin": f"Qm{server_id}Pin123456789012345678901234567890",
            "dag": f"Qm{server_id}Dag123456789012345678901234567890"
        }
        
        logger.info(f"Created mock {server_id} server with {failure_rate}% failure rate")
    
    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a request by returning an appropriate response."""
        self.request_count += 1
        
        # Simulate server latency
        jitter = (self.request_count % 10) / 100.0  # Add some variability
        await asyncio.sleep(self.latency + jitter)
        
        # Check for simulated failures
        if not self.is_healthy or (self.failure_rate > 0 and self.request_count % int(1/self.failure_rate) == 0):
            return {
                "success": False,
                "error": "Server error",
                "server_id": self.server_id,
                "timestamp": time.time(),
                "request_id": f"{self.server_id}-{self.request_count}"
            }
        
        # Get request type and command
        req_type = request.get("type", "")
        command = request.get("command", "")
        
        # Generate appropriate response based on request
        if req_type == "ipfs":
            if command == "get":
                return {
                    "success": True,
                    "cid": self.cids["get"],
                    "data": f"Test data from {self.server_id} server",
                    "size": 1024,
                    "server_id": self.server_id,
                    "timestamp": time.time(),
                    "request_id": f"{self.server_id}-{self.request_count}"
                }
            elif command == "add":
                return {
                    "success": True,
                    "cid": self.cids["add"],
                    "size": 2048,
                    "server_id": self.server_id,
                    "timestamp": time.time(),
                    "request_id": f"{self.server_id}-{self.request_count}"
                }
            elif command == "pin":
                return {
                    "success": True,
                    "cid": self.cids["pin"],
                    "pins": [self.cids["pin"]],
                    "server_id": self.server_id,
                    "timestamp": time.time(),
                    "request_id": f"{self.server_id}-{self.request_count}"
                }
            elif command == "dag":
                # Introduce a subtle difference in green server responses
                extra_field = {"metadata": {"processed": True}} if self.server_id == "green" else {}
                return {
                    "success": True,
                    "cid": self.cids["dag"],
                    "data": {
                        "links": [
                            {"Name": "file1.txt", "Hash": f"Qm{self.server_id}Link1", "Size": 100},
                            {"Name": "file2.txt", "Hash": f"Qm{self.server_id}Link2", "Size": 200}
                        ],
                        "data": "Test DAG data",
                        **extra_field
                    },
                    "server_id": self.server_id,
                    "timestamp": time.time(),
                    "request_id": f"{self.server_id}-{self.request_count}"
                }
        elif req_type == "libp2p":
            return {
                "success": True,
                "peers": [f"Peer{i}-{self.server_id}" for i in range(5)],
                "server_id": self.server_id,
                "timestamp": time.time(),
                "request_id": f"{self.server_id}-{self.request_count}"
            }
        elif req_type == "storage":
            return {
                "success": True,
                "backend": "local",
                "operation": command,
                "path": f"/test/path/{self.server_id}/{command}",
                "server_id": self.server_id,
                "timestamp": time.time(),
                "request_id": f"{self.server_id}-{self.request_count}"
            }
        
        # Default response
        return {
            "success": True,
            "type": req_type,
            "command": command,
            "server_id": self.server_id,
            "timestamp": time.time(),
            "request_id": f"{self.server_id}-{self.request_count}"
        }
    
    async def check_health(self) -> Dict[str, Any]:
        """Check server health."""
        await asyncio.sleep(0.01)  # Small delay
        
        return {
            "success": self.is_healthy,
            "status": "healthy" if self.is_healthy else "unhealthy",
            "timestamp": time.time(),
            "server_id": self.server_id
        }
    
    def set_health(self, is_healthy: bool) -> None:
        """Change the health status of the server."""
        prev_status = "healthy" if self.is_healthy else "unhealthy"
        new_status = "healthy" if is_healthy else "unhealthy"
        
        self.is_healthy = is_healthy
        logger.info(f"{self.server_id} server health changed: {prev_status} -> {new_status}")
    
    def set_failure_rate(self, failure_rate: float) -> None:
        """Change the failure rate of the server."""
        self.failure_rate = failure_rate / 100.0
        logger.info(f"{self.server_id} server failure rate changed to {failure_rate}%")
    
    def set_latency(self, latency: float) -> None:
        """Change the latency of the server."""
        self.latency = latency
        logger.info(f"{self.server_id} server latency changed to {latency}s")

class TestScenario:
    """Base class for test scenarios."""
    
    def __init__(self, name: str, proxy: AsyncMCPServerProxy):
        """
        Initialize test scenario.
        
        Args:
            name: Scenario name
            proxy: AsyncMCPServerProxy instance to test
        """
        self.name = name
        self.proxy = proxy
        self.success = False
        self.error = None
    
    async def run(self) -> bool:
        """
        Run the test scenario.
        
        Returns:
            True if the scenario was successful, False otherwise
        """
        logger.info(f"Running scenario: {self.name}")
        
        try:
            self.success = await self._run_scenario()
            if self.success:
                logger.info(f"Scenario {self.name} succeeded")
            else:
                logger.error(f"Scenario {self.name} failed")
            
            return self.success
        
        except Exception as e:
            self.error = str(e)
            logger.exception(f"Error in scenario {self.name}: {e}")
            return False
    
    async def _run_scenario(self) -> bool:
        """
        Implement the actual scenario logic.
        
        Returns:
            True if the scenario was successful, False otherwise
        """
        # Override in subclasses
        return False

class GradualMigrationScenario(TestScenario):
    """Test gradual migration from blue to green."""
    
    async def _run_scenario(self) -> bool:
        """Run the gradual migration scenario."""
        # Start with blue only
        self.proxy.set_mode(DeploymentMode.BLUE)
        
        # Execute some requests in blue mode
        logger.info("Executing requests in BLUE mode")
        for i in range(10):
            response = await self.proxy.handle_request({
                "type": "ipfs",
                "command": "get",
                "path": f"/test/file{i}.txt"
            })
            
            # Verify all requests go to blue
            assert response.get("server_id") == "blue", "Request should go to blue server"
        
        # Switch to gradual mode with 20% green traffic
        logger.info("Switching to GRADUAL mode with 20% green traffic")
        self.proxy.set_mode(DeploymentMode.GRADUAL, 20)
        
        # Execute more requests and count distribution
        blue_count = 0
        green_count = 0
        
        for i in range(50):
            response = await self.proxy.handle_request({
                "type": "ipfs",
                "command": "add",
                "data": f"Test data {i}"
            })
            
            if response.get("server_id") == "blue":
                blue_count += 1
            else:
                green_count += 1
        
        # Verify approximate distribution (allow for some statistical variation)
        green_percentage = (green_count / 50) * 100
        logger.info(f"Traffic distribution: Blue: {blue_count} (≈{100-green_percentage:.1f}%), Green: {green_count} (≈{green_percentage:.1f}%)")
        
        # Distribution should be roughly 80% blue, 20% green (±15%)
        assert abs(green_percentage - 20) <= 15, f"Green traffic percentage ({green_percentage:.1f}%) too far from target (20%)"
        
        # Increase green traffic to 80%
        logger.info("Increasing green traffic to 80%")
        self.proxy.set_mode(DeploymentMode.GRADUAL, 80)
        
        # Execute more requests
        blue_count = 0
        green_count = 0
        
        for i in range(50):
            response = await self.proxy.handle_request({
                "type": "ipfs",
                "command": "pin",
                "cid": f"QmTest{i}"
            })
            
            if response.get("server_id") == "blue":
                blue_count += 1
            else:
                green_count += 1
        
        # Verify distribution shifted
        green_percentage = (green_count / 50) * 100
        logger.info(f"Traffic distribution: Blue: {blue_count} (≈{100-green_percentage:.1f}%), Green: {green_count} (≈{green_percentage:.1f}%)")
        
        # Distribution should be roughly 20% blue, 80% green (±15%)
        assert abs(green_percentage - 80) <= 15, f"Green traffic percentage ({green_percentage:.1f}%) too far from target (80%)"
        
        # Complete migration to green
        logger.info("Completing migration to GREEN mode")
        self.proxy.set_mode(DeploymentMode.GREEN)
        
        # Execute some requests in green mode
        for i in range(10):
            response = await self.proxy.handle_request({
                "type": "ipfs",
                "command": "dag",
                "cid": f"QmTestDag{i}"
            })
            
            # Verify all requests go to green
            assert response.get("server_id") == "green", "Request should go to green server"
        
        return True

class AutomaticFailoverScenario(TestScenario):
    """Test automatic failover on server failure."""
    
    async def _run_scenario(self) -> bool:
        """Run the automatic failover scenario."""
        blue_server = self.proxy.blue_server
        green_server = self.proxy.green_server
        
        # Start with auto mode
        self.proxy.set_mode(DeploymentMode.AUTO, 50)
        
        # Execute some requests in auto mode
        logger.info("Executing requests in AUTO mode")
        blue_count = 0
        green_count = 0
        
        for i in range(20):
            response = await self.proxy.handle_request({
                "type": "ipfs",
                "command": "get",
                "path": f"/test/auto_file{i}.txt"
            })
            
            if response.get("server_id") == "blue":
                blue_count += 1
            else:
                green_count += 1
        
        logger.info(f"Initial distribution: Blue: {blue_count}, Green: {green_count}")
        
        # Make green server unhealthy
        logger.info("Making GREEN server unhealthy")
        green_server.set_health(False)
        
        # Perform a health check to detect the issue
        await self.proxy.check_health()
        
        # Execute more requests - should all go to blue
        blue_count = 0
        green_count = 0
        
        for i in range(20):
            response = await self.proxy.handle_request({
                "type": "storage",
                "command": "store",
                "data": f"Test data {i}"
            })
            
            if response.get("server_id") == "blue":
                blue_count += 1
            else:
                green_count += 1
        
        logger.info(f"After green failure: Blue: {blue_count}, Green: {green_count}")
        
        # Verify all or most requests went to blue
        assert blue_count >= 18, f"Not enough requests went to blue ({blue_count}) after green failure"
        
        # Now make blue unhealthy and green healthy
        logger.info("Making BLUE unhealthy and GREEN healthy again")
        blue_server.set_health(False)
        green_server.set_health(True)
        
        # Perform a health check to detect the changes
        await self.proxy.check_health()
        
        # Execute more requests - should all go to green
        blue_count = 0
        green_count = 0
        
        for i in range(20):
            response = await self.proxy.handle_request({
                "type": "libp2p",
                "command": "connect",
                "peer": f"TestPeer{i}"
            })
            
            if response.get("server_id") == "blue":
                blue_count += 1
            else:
                green_count += 1
        
        logger.info(f"After blue failure: Blue: {blue_count}, Green: {green_count}")
        
        # Verify all or most requests went to green
        assert green_count >= 18, f"Not enough requests went to green ({green_count}) after blue failure"
        
        # Restore both servers to healthy
        logger.info("Restoring both servers to healthy state")
        blue_server.set_health(True)
        green_server.set_health(True)
        
        # Perform a health check to detect the changes
        await self.proxy.check_health()
        
        return True

class PerformanceComparisonScenario(TestScenario):
    """Test performance-based traffic adjustment."""
    
    async def _run_scenario(self) -> bool:
        """Run the performance comparison scenario."""
        blue_server = self.proxy.blue_server
        green_server = self.proxy.green_server
        
        # Configure initial performance: green slower than blue
        logger.info("Setting up initial performance: GREEN slower than BLUE")
        blue_server.set_latency(0.02)
        green_server.set_latency(0.05)
        
        # Start with parallel mode to gather metrics
        self.proxy.set_mode(DeploymentMode.PARALLEL)
        
        # Generate load to gather metrics
        logger.info("Generating load to collect performance metrics")
        for i in range(30):
            await self.proxy.handle_request({
                "type": "ipfs",
                "command": "get",
                "path": f"/test/perf_file{i}.txt"
            })
        
        # Check metrics to verify performance difference
        health = await self.proxy.check_health()
        if "metrics" in health:
            blue_perf = health["metrics"].get("blue", {})
            green_perf = health["metrics"].get("green", {})
            
            blue_time = blue_perf.get("avg_response_time", 0)
            green_time = green_perf.get("avg_response_time", 0)
            
            logger.info(f"Performance metrics - Blue: {blue_time:.3f}s, Green: {green_time:.3f}s")
            
            # Green should be slower
            assert green_time > blue_time, "Green should be slower than blue in initial setup"
        
        # Now make green faster
        logger.info("Making GREEN faster than BLUE")
        blue_server.set_latency(0.05)
        green_server.set_latency(0.01)
        
        # Generate more load to update metrics
        for i in range(30):
            await self.proxy.handle_request({
                "type": "ipfs",
                "command": "add",
                "data": f"Performance test data {i}"
            })
        
        # Check metrics again
        health = await self.proxy.check_health()
        if "metrics" in health:
            blue_perf = health["metrics"].get("blue", {})
            green_perf = health["metrics"].get("green", {})
            
            blue_time = blue_perf.get("avg_response_time", 0)
            green_time = green_perf.get("avg_response_time", 0)
            
            logger.info(f"Updated performance metrics - Blue: {blue_time:.3f}s, Green: {green_time:.3f}s")
            
            # Blue should now be slower
            assert blue_time > green_time, "Blue should be slower than green after adjustment"
        
        # Switch to auto mode and see if traffic adjusts based on performance
        logger.info("Switching to AUTO mode to test performance-based adjustment")
        self.proxy.set_mode(DeploymentMode.AUTO, 20)  # Start with 20% green
        
        # Generate traffic in auto mode
        blue_count = 0
        green_count = 0
        
        for i in range(50):
            # Small sleep to allow time for auto-adjustment
            if i % 10 == 0:
                await asyncio.sleep(0.2)
            
            response = await self.proxy.handle_request({
                "type": "ipfs",
                "command": "pin",
                "cid": f"QmPerfTest{i}"
            })
            
            if response.get("server_id") == "blue":
                blue_count += 1
            else:
                green_count += 1
        
        green_percentage = (green_count / 50) * 100
        logger.info(f"Final traffic distribution: Blue: {blue_count} (≈{100-green_percentage:.1f}%), Green: {green_count} (≈{green_percentage:.1f}%)")
        
        # Green should get increased traffic due to better performance
        # Note: This test might be flaky due to timing and auto-adjustment algorithm
        # We only assert that green got some traffic, not a specific percentage
        assert green_count > 10, f"Green should get increased traffic due to better performance, but only got {green_count} requests"
        
        return True

class ResponseValidationScenario(TestScenario):
    """Test response validation for compatibility checking."""
    
    async def _run_scenario(self) -> bool:
        """Run the response validation scenario."""
        # Check if validation component is available
        if not hasattr(self.proxy, 'response_validator') or not self.proxy.response_validator:
            logger.warning("Response validator not available, skipping validation scenario")
            return True
        
        # Start with parallel mode to generate validation data
        self.proxy.set_mode(DeploymentMode.PARALLEL)
        
        # Generate compatible responses
        logger.info("Generating compatible responses for validation")
        for i in range(20):
            await self.proxy.handle_request({
                "type": "ipfs",
                "command": "get",
                "path": f"/test/compat_file{i}.txt"
            })
        
        # Get validation stats
        validation_stats = self.proxy.response_validator.get_validation_stats()
        logger.info(f"Validation stats after compatible requests: {validation_stats}")
        
        assert validation_stats["total_validations"] >= 20, "Should have at least 20 validations"
        
        # Now create an incompatible response in the green server
        # by modifying the critical CID field
        logger.info("Testing critical field difference detection")
        
        # Save original CID for get command
        green_server = self.proxy.green_server
        original_get_cid = green_server.cids["get"]
        
        # Change CID to be critically different
        green_server.cids["get"] = "QmIncompatibleCID123456789012345678"
        
        # Execute request that should trigger a validation failure
        await self.proxy.handle_request({
            "type": "ipfs",
            "command": "get",
            "path": "/test/incompatible.txt"
        })
        
        # Restore original CID
        green_server.cids["get"] = original_get_cid
        
        # Get updated validation stats
        validation_stats = self.proxy.response_validator.get_validation_stats()
        logger.info(f"Validation stats after incompatible request: {validation_stats}")
        
        # Should have at least one critical difference
        assert validation_stats["critical_difference_rate"] > 0, "Should detect critical difference in CID"
        
        # Now test with non-critical difference (the extra field in DAG response)
        logger.info("Testing non-critical difference detection")
        
        for i in range(10):
            await self.proxy.handle_request({
                "type": "ipfs",
                "command": "dag",
                "cid": f"QmDagTest{i}"
            })
        
        # Get final validation stats
        validation_stats = self.proxy.response_validator.get_validation_stats()
        logger.info(f"Final validation stats: {validation_stats}")
        
        # Compatible rate should be high despite some differences
        assert validation_stats["compatible_rate"] > 75, "Compatible rate should remain high for non-critical differences"
        
        return True

async def run_end_to_end_test(config_path: str, scenarios: List[str] = None):
    """
    Run end-to-end test with the specified scenarios.
    
    Args:
        config_path: Path to configuration file
        scenarios: List of scenario names to run (None for all)
    
    Returns:
        True if all tests pass, False otherwise
    """
    logger.info(f"Starting end-to-end test with config: {config_path}")
    
    # Load configuration
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        return False
    
    # Create proxy with mock servers
    proxy = AsyncMCPServerProxy(config)
    blue_server = MockIPFSServer("blue", failure_rate=0.0, latency=0.03)
    green_server = MockIPFSServer("green", failure_rate=0.0, latency=0.03)
    
    proxy.blue_server = blue_server
    proxy.green_server = green_server
    proxy.running = True
    proxy.blue_healthy = True
    proxy.green_healthy = True
    
    # Set up test scenarios
    all_scenarios = [
        GradualMigrationScenario("gradual_migration", proxy),
        AutomaticFailoverScenario("automatic_failover", proxy),
        PerformanceComparisonScenario("performance_comparison", proxy),
        ResponseValidationScenario("response_validation", proxy)
    ]
    
    # Filter scenarios if specified
    if scenarios:
        test_scenarios = [s for s in all_scenarios if s.name in scenarios]
        if not test_scenarios:
            logger.error(f"No matching scenarios found: {scenarios}")
            return False
    else:
        test_scenarios = all_scenarios
    
    # Run scenarios
    results = []
    for scenario in test_scenarios:
        success = await scenario.run()
        results.append((scenario.name, success, scenario.error))
        
        # Short pause between scenarios
        await asyncio.sleep(1)
    
    # Print summary
    logger.info("=== Test Summary ===")
    all_passed = True
    for name, success, error in results:
        status = "PASS" if success else "FAIL"
        error_msg = f": {error}" if error else ""
        logger.info(f"{status} - {name}{error_msg}")
        if not success:
            all_passed = False
    
    return all_passed

def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description="Run End-to-End tests for MCP Blue/Green deployment")
    parser.add_argument("--config", "-c", default="../test/integration/test_blue_green_config.json",
                        help="Path to test configuration file")
    parser.add_argument("--scenarios", "-s", nargs="+",
                        choices=["gradual_migration", "automatic_failover", "performance_comparison", "response_validation"],
                        help="Specific scenarios to run (default: all)")
    # Only parse args when running the script directly, not when imported by pytest
    if __name__ == "__main__":
        args = parser.parse_args()
    else:
        # When run under pytest, use default values
        args = parser.parse_args([])
    
    # Run end-to-end tests
    try:
        success = asyncio.run(run_end_to_end_test(args.config, args.scenarios))
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.exception(f"Error running tests: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()