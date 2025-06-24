#!/usr/bin/env python3
"""
Comprehensive integration test for IPFS cluster daemon status functionality.

This script tests:
1. Direct module testing for both ipfs_cluster_service and ipfs_cluster_follow status methods
2. Controller-level integration testing for both daemon types
3. API endpoint testing via HTTP requests (when possible)
"""
import os
import sys
import json
import logging
import unittest
import time
import uuid
import requests
from unittest.mock import patch, MagicMock

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("cluster_status_test")

# MCP Server settings
MCP_SERVER_URL = "http://127.0.0.1:9999"
MCP_SERVER_RUNNING = False  # Will be updated during test

class IPFSClusterStatusTest(unittest.TestCase):
    """Test cases for IPFS cluster daemon status functionality."""

    def setUp(self):
        """Set up test environment."""
        # Check if server is running
        try:
            response = requests.get(f"{MCP_SERVER_URL}/api/v0/health", timeout=2)
            if response.status_code == 200:
                global MCP_SERVER_RUNNING
                MCP_SERVER_RUNNING = True
                logger.info("MCP Server is running, will include API endpoint tests")
            else:
                logger.warning("MCP Server returned non-200 status code")
        except Exception as e:
            logger.warning(f"MCP Server does not appear to be running: {e}")

    def test_ipfs_cluster_service_status_direct(self):
        """Test ipfs_cluster_service_status method directly."""
        try:
            from ipfs_kit_py.ipfs_cluster_service import ipfs_cluster_service

            # Create an instance
            service = ipfs_cluster_service()

            # Call the status method
            result = service.ipfs_cluster_service_status()

            # Verify result structure
            self.assertIsInstance(result, dict)
            self.assertIn("success", result)
            self.assertIn("process_running", result)
            self.assertIn("process_count", result)

            logger.info(f"Direct ipfs_cluster_service_status result: {result}")

        except ImportError as e:
            logger.error(f"Could not import ipfs_cluster_service module: {e}")
            self.fail(f"Import error: {e}")
        except Exception as e:
            logger.error(f"Error testing ipfs_cluster_service_status: {e}")
            self.fail(f"Unexpected error: {e}")

    def test_ipfs_cluster_follow_status_direct(self):
        """Test ipfs_cluster_follow_status method directly."""
        try:
            from ipfs_kit_py.ipfs_cluster_follow import ipfs_cluster_follow

            # Create an instance
            follow = ipfs_cluster_follow()

            # Call the status method
            result = follow.ipfs_cluster_follow_status()

            # Verify result structure
            self.assertIsInstance(result, dict)
            self.assertIn("success", result)
            self.assertIn("process_running", result)
            self.assertIn("process_count", result)

            logger.info(f"Direct ipfs_cluster_follow_status result: {result}")

        except ImportError as e:
            logger.error(f"Could not import ipfs_cluster_follow module: {e}")
            self.fail(f"Import error: {e}")
        except Exception as e:
            logger.error(f"Error testing ipfs_cluster_follow_status: {e}")
            self.fail(f"Unexpected error: {e}")

    def test_controller_integration(self):
        """Test controller integration with both status methods."""
        try:
            # Import controller
            from ipfs_kit_py.mcp.controllers.ipfs_controller import IPFSController

            # Mock the IPFS model for the controller
            mock_model = MagicMock()
            mock_model.check_daemon_status.return_value = {
                "success": True,
                "overall_status": "running",
                "daemons": {
                    "ipfs": {
                        "running": True,
                        "type": "ipfs",
                        "process_count": 1
                    }
                }
            }

            # Create controller with mock model
            controller = IPFSController(mock_model)

            # Test with cluster_service daemon type
            with patch('ipfs_kit_py.ipfs_cluster_service.ipfs_cluster_service') as mock_service:
                # Configure mock service
                mock_service_instance = MagicMock()
                mock_service_instance.ipfs_cluster_service_status.return_value = {
                    "success": True,
                    "process_running": True,
                    "process_count": 1
                }
                mock_service.return_value = mock_service_instance

                # Create request for cluster_service
                class MockRequest:
                    async def json(self):
                        return {"daemon_type": "ipfs_cluster_service"}

                # Test controller method
                import anyio
                loop = anyio.get_event_loop()
                result = loop.run_until_complete(controller.check_daemon_status(MockRequest()))

                # Verify result
                self.assertIsInstance(result, dict)
                self.assertTrue(result.get("success", False))
                self.assertEqual(result.get("overall_status"), "running")
                self.assertIn("ipfs_cluster_service", result.get("daemons", {}))

                logger.info(f"Controller integration test for ipfs_cluster_service: {result}")

            # Test with cluster_follow daemon type
            with patch('ipfs_kit_py.ipfs_cluster_follow.ipfs_cluster_follow') as mock_follow:
                # Configure mock follow
                mock_follow_instance = MagicMock()
                mock_follow_instance.ipfs_cluster_follow_status.return_value = {
                    "success": True,
                    "process_running": True,
                    "process_count": 1
                }
                mock_follow.return_value = mock_follow_instance

                # Create request for cluster_follow
                class MockRequest:
                    async def json(self):
                        return {"daemon_type": "ipfs_cluster_follow"}

                # Test controller method
                loop = anyio.get_event_loop()
                result = loop.run_until_complete(controller.check_daemon_status(MockRequest()))

                # Verify result
                self.assertIsInstance(result, dict)
                self.assertTrue(result.get("success", False))
                self.assertEqual(result.get("overall_status"), "running")
                self.assertIn("ipfs_cluster_follow", result.get("daemons", {}))

                logger.info(f"Controller integration test for ipfs_cluster_follow: {result}")

        except ImportError as e:
            logger.error(f"Could not import controller module: {e}")
            self.fail(f"Import error: {e}")
        except Exception as e:
            logger.error(f"Error testing controller integration: {e}")
            self.fail(f"Unexpected error: {e}")

    def test_api_endpoint_integration(self):
        """Test the API endpoint integration (if server is running)."""
        if not MCP_SERVER_RUNNING:
            logger.warning("Skipping API endpoint test as MCP Server is not running")
            self.skipTest("MCP Server not running")
            return

        # Test cluster_service endpoint
        logger.info("Testing API endpoint for ipfs_cluster_service...")
        try:
            response = requests.post(
                f"{MCP_SERVER_URL}/api/v0/ipfs/daemon/status",
                json={"daemon_type": "ipfs_cluster_service"},
                headers={"Content-Type": "application/json"}
            )

            self.assertEqual(response.status_code, 200, "API returned non-200 status code")
            result = response.json()

            # Verify result structure
            self.assertIsInstance(result, dict)
            self.assertIn("success", result)
            self.assertIn("overall_status", result)
            self.assertIn("daemons", result)

            logger.info(f"API endpoint test for ipfs_cluster_service: {json.dumps(result, indent=2)}")

        except Exception as e:
            logger.error(f"Error testing ipfs_cluster_service API endpoint: {e}")
            self.fail(f"API endpoint error: {e}")

        # Test cluster_follow endpoint
        logger.info("Testing API endpoint for ipfs_cluster_follow...")
        try:
            response = requests.post(
                f"{MCP_SERVER_URL}/api/v0/ipfs/daemon/status",
                json={"daemon_type": "ipfs_cluster_follow"},
                headers={"Content-Type": "application/json"}
            )

            self.assertEqual(response.status_code, 200, "API returned non-200 status code")
            result = response.json()

            # Verify result structure
            self.assertIsInstance(result, dict)
            self.assertIn("success", result)
            self.assertIn("overall_status", result)
            self.assertIn("daemons", result)

            logger.info(f"API endpoint test for ipfs_cluster_follow: {json.dumps(result, indent=2)}")

        except Exception as e:
            logger.error(f"Error testing ipfs_cluster_follow API endpoint: {e}")
            self.fail(f"API endpoint error: {e}")

def run_tests():
    """Run all the tests."""
    logger.info("Starting IPFS cluster daemon status tests...")

    # Create test suite and run
    suite = unittest.TestLoader().loadTestsFromTestCase(IPFSClusterStatusTest)
    result = unittest.TextTestRunner(verbosity=2).run(suite)

    if result.wasSuccessful():
        logger.info("✅ All tests passed successfully!")
        return 0
    else:
        logger.error(f"❌ Tests failed: {len(result.failures)} failures, {len(result.errors)} errors")
        return 1

if __name__ == "__main__":
    sys.exit(run_tests())
