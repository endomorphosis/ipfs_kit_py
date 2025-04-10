"""
Test Filecoin integration with the MCP server.

This test focuses on how the FilecoinModel and FilecoinController 
components interact within the MCP server architecture.
"""

import time
import json
import logging
import unittest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mock FilecoinModel class
class MockFilecoinModel:
    """Mock implementation of FilecoinModel for testing."""
    
    def __init__(self, lotus_kit_instance=None, ipfs_model=None, 
                 cache_manager=None, credential_manager=None):
        """Initialize the model with mocks."""
        self.lotus_kit = lotus_kit_instance
        self.ipfs_model = ipfs_model
        self.cache_manager = cache_manager
        self.credential_manager = credential_manager
        self.call_count = {}
        self.response_overrides = {}
        self.operation_stats = {
            "total_operations": 0,
            "successful_operations": 0,
            "failed_operations": 0,
            "bytes_uploaded": 0,
            "bytes_downloaded": 0
        }
        logger.info("MockFilecoinModel initialized")
    
    def _create_result_dict(self, operation_name):
        """Create a standardized result dictionary."""
        return {
            "success": False,  # Default to False, set to True on success
            "operation": operation_name,
            "timestamp": time.time(),
            "correlation_id": "mock-correlation-id"
        }
    
    def _track_call(self, method_name):
        """Track method calls for testing."""
        if method_name not in self.call_count:
            self.call_count[method_name] = 0
        self.call_count[method_name] += 1
        self.operation_stats["total_operations"] += 1
    
    def _get_response_override(self, method_name, default_response=None):
        """Get a response override if configured."""
        if method_name in self.response_overrides:
            return self.response_overrides[method_name]
        return default_response
    
    def check_connection(self):
        """Check connection to Lotus API."""
        self._track_call("check_connection")
        result = self._create_result_dict("check_connection")
        
        override = self._get_response_override("check_connection")
        if override:
            return override
        
        # Simulate success
        result["success"] = True
        result["connected"] = True
        result["version"] = "1.0.0"
        result["api_url"] = "http://localhost:1234/rpc/v0"
        result["duration_ms"] = 10.5
        
        self.operation_stats["successful_operations"] += 1
        return result
    
    def list_wallets(self):
        """List wallet addresses."""
        self._track_call("list_wallets")
        result = self._create_result_dict("list_wallets")
        
        override = self._get_response_override("list_wallets")
        if override:
            return override
        
        # Simulate success
        result["success"] = True
        result["wallets"] = [
            "f1aaa...bbb", 
            "f1ccc...ddd"
        ]
        result["count"] = 2
        result["duration_ms"] = 15.3
        
        self.operation_stats["successful_operations"] += 1
        return result
    
    def get_wallet_balance(self, address):
        """Get wallet balance."""
        self._track_call("get_wallet_balance")
        result = self._create_result_dict("get_wallet_balance")
        
        override = self._get_response_override("get_wallet_balance")
        if override:
            return override
        
        # Simulate success
        result["success"] = True
        result["address"] = address
        result["balance"] = "100.5"
        result["duration_ms"] = 12.1
        
        self.operation_stats["successful_operations"] += 1
        return result
    
    def create_wallet(self, wallet_type="bls"):
        """Create a new wallet."""
        self._track_call("create_wallet")
        result = self._create_result_dict("create_wallet")
        
        override = self._get_response_override("create_wallet")
        if override:
            return override
        
        # Simulate success
        result["success"] = True
        result["address"] = "f1new...wallet"
        result["wallet_type"] = wallet_type
        result["duration_ms"] = 25.7
        
        self.operation_stats["successful_operations"] += 1
        return result
    
    def list_miners(self):
        """List miners."""
        self._track_call("list_miners")
        result = self._create_result_dict("list_miners")
        
        override = self._get_response_override("list_miners")
        if override:
            return override
        
        # Simulate success
        result["success"] = True
        result["miners"] = ["f01234", "f05678"]
        result["count"] = 2
        result["duration_ms"] = 18.2
        
        self.operation_stats["successful_operations"] += 1
        return result
    
    def list_deals(self):
        """List storage deals."""
        self._track_call("list_deals")
        result = self._create_result_dict("list_deals")
        
        override = self._get_response_override("list_deals")
        if override:
            return override
        
        # Simulate success
        result["success"] = True
        result["deals"] = [
            {"id": 1, "state": "active", "size": 1024},
            {"id": 2, "state": "proposed", "size": 2048}
        ]
        result["count"] = 2
        result["duration_ms"] = 22.4
        
        self.operation_stats["successful_operations"] += 1
        return result
    
    def list_imports(self):
        """List imports."""
        self._track_call("list_imports")
        result = self._create_result_dict("list_imports")
        
        override = self._get_response_override("list_imports")
        if override:
            return override
        
        # Simulate success
        result["success"] = True
        result["imports"] = [
            {"cid": "Qm...123", "size": 1024},
            {"cid": "Qm...456", "size": 2048}
        ]
        result["count"] = 2
        result["duration_ms"] = 17.9
        
        self.operation_stats["successful_operations"] += 1
        return result
    
    def ipfs_to_filecoin(self, cid, miner, price, duration, wallet=None, verified=False, fast_retrieval=True, pin=True):
        """Store IPFS content on Filecoin."""
        self._track_call("ipfs_to_filecoin")
        result = self._create_result_dict("ipfs_to_filecoin")
        
        override = self._get_response_override("ipfs_to_filecoin")
        if override:
            return override
        
        # Simulate success
        result["success"] = True
        result["ipfs_cid"] = cid
        result["filecoin_cid"] = "fil-" + cid
        result["deal_cid"] = "bafy..."
        result["miner"] = miner
        result["price"] = price
        result["duration"] = duration
        result["size_bytes"] = 1024 * 1024  # 1MB
        result["duration_ms"] = 125.3
        
        self.operation_stats["successful_operations"] += 1
        self.operation_stats["bytes_uploaded"] += 1024 * 1024
        return result
    
    def filecoin_to_ipfs(self, data_cid, pin=True):
        """Retrieve content from Filecoin and add to IPFS."""
        self._track_call("filecoin_to_ipfs")
        result = self._create_result_dict("filecoin_to_ipfs")
        
        override = self._get_response_override("filecoin_to_ipfs")
        if override:
            return override
        
        # Simulate success
        result["success"] = True
        result["filecoin_cid"] = data_cid
        result["ipfs_cid"] = "ipfs-" + data_cid
        result["size_bytes"] = 1024 * 1024  # 1MB
        result["duration_ms"] = 115.8
        
        self.operation_stats["successful_operations"] += 1
        self.operation_stats["bytes_downloaded"] += 1024 * 1024
        return result
    
    def get_stats(self):
        """Get model statistics."""
        return {
            "operation_stats": self.operation_stats,
            "method_calls": self.call_count
        }
    
    def set_response_override(self, method_name, response):
        """Set a response override for a method."""
        self.response_overrides[method_name] = response
    
    def reset(self):
        """Reset the model state."""
        self.call_count = {}
        self.response_overrides = {}
        self.operation_stats = {
            "total_operations": 0,
            "successful_operations": 0,
            "failed_operations": 0,
            "bytes_uploaded": 0,
            "bytes_downloaded": 0
        }


# Define test cases
class TestFilecoinIntegration(unittest.TestCase):
    """Test the integration of Filecoin components in MCP server."""
    
    def setUp(self):
        """Set up test dependencies."""
        # Import controller class directly
        # This is a direct import to avoid dependency on the entire module chain
        import sys
        import os
        
        # Temporarily add module directory to path if needed
        controller_path = os.path.join('/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/controllers/storage')
        if controller_path not in sys.path:
            sys.path.insert(0, controller_path)
            
        # Import the controller file directly
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "filecoin_controller", 
            "/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/controllers/storage/filecoin_controller.py"
        )
        filecoin_controller_module = importlib.util.module_from_spec(spec)
        
        # Create our mock class
        filecoin_controller_module.FilecoinModel = MockFilecoinModel
        
        # Execute the module to define the controller
        spec.loader.exec_module(filecoin_controller_module)
        
        # Get the controller class
        FilecoinController = filecoin_controller_module.FilecoinController
        
        # Create model instance and controller
        self.model = MockFilecoinModel()
        self.controller = FilecoinController(self.model)
        
        # Create FastAPI app and test client
        self.app = FastAPI()
        self.router = self.app.router.routes
        
        # Register routes
        self.controller.register_routes(self.app)
        
        # Create test client
        self.client = TestClient(self.app)
        
        logger.info("Test setup completed")
    
    def tearDown(self):
        """Clean up test dependencies."""
        # Nothing to clean up since we're not using patches
        logger.info("Test teardown completed")
    
    def test_status_success(self):
        """Test status endpoint with successful connection."""
        # Model returns successful connection
        response = self.client.get("/filecoin/status")
        
        # Debug: print actual response
        print(f"Status success response: {response.json()}")
        
        # Check response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["operation"], "check_connection")
        self.assertTrue("duration_ms" in data)
            
        # Verify model called
        self.assertEqual(self.model.call_count["check_connection"], 1)
    
    def test_status_failure(self):
        """Test status endpoint with failed connection."""
        # Set up model to return failure
        self.model.set_response_override("check_connection", {
            "success": False,
            "operation": "check_connection",
            "timestamp": time.time(),
            "correlation_id": "mock-correlation-id",
            "error": "Failed to connect to Lotus API",
            "error_type": "ConnectionError",
            "duration_ms": 10.5
        })
        
        # Make API request
        response = self.client.get("/filecoin/status")
        
        # Debug: print actual response
        print(f"Status failure response: {response.json()}")
        
        # Check response - note that controller still returns 200 with success=True
        # but includes connection failure information
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])  # This is for the API response itself
        self.assertEqual(data["operation"], "check_connection")
        self.assertTrue("duration_ms" in data)
        
        # Verify model called
        self.assertEqual(self.model.call_count["check_connection"], 1)
    
    def test_list_wallets_success(self):
        """Test list wallets endpoint with successful response."""
        # Make API request
        response = self.client.get("/filecoin/wallets")
        
        # Check response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["operation"], "list_wallets")
        self.assertEqual(len(data["wallets"]), 2)
        self.assertEqual(data["count"], 2)
        
        # Verify model called
        self.assertEqual(self.model.call_count["list_wallets"], 1)
    
    def test_list_wallets_failure(self):
        """Test list wallets endpoint with failure response."""
        # Set up model to return failure
        self.model.set_response_override("list_wallets", {
            "success": False,
            "operation": "list_wallets",
            "timestamp": time.time(),
            "correlation_id": "mock-correlation-id",
            "error": "Failed to list wallets",
            "error_type": "WalletListError",
            "duration_ms": 10.5
        })
        
        # Make API request
        response = self.client.get("/filecoin/wallets")
        
        # Check response - controller should return 500 with error details
        self.assertEqual(response.status_code, 500)
        data = response.json()
        self.assertEqual(data["detail"]["error"], "Failed to list wallets")
        self.assertEqual(data["detail"]["error_type"], "WalletListError")
        
        # Verify model called
        self.assertEqual(self.model.call_count["list_wallets"], 1)
    
    def test_wallet_balance_success(self):
        """Test wallet balance endpoint with successful response."""
        # Make API request
        response = self.client.get("/filecoin/wallet/balance/f1test")
        
        # Check response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["operation"], "get_wallet_balance")
        self.assertEqual(data["address"], "f1test")
        self.assertEqual(data["balance"], "100.5")
        
        # Verify model called
        self.assertEqual(self.model.call_count["get_wallet_balance"], 1)
    
    def test_create_wallet_success(self):
        """Test create wallet endpoint with successful response."""
        # Make API request
        response = self.client.post("/filecoin/wallet/create", json={"wallet_type": "bls"})
        
        # Check response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["operation"], "create_wallet")
        self.assertEqual(data["address"], "f1new...wallet")
        self.assertEqual(data["wallet_type"], "bls")
        
        # Verify model called
        self.assertEqual(self.model.call_count["create_wallet"], 1)
    
    def test_list_miners_success(self):
        """Test list miners endpoint with successful response."""
        # Make API request
        response = self.client.get("/filecoin/miners")
        
        # Check response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["operation"], "list_miners")
        self.assertEqual(len(data["miners"]), 2)
        self.assertEqual(data["count"], 2)
        
        # Verify model called
        self.assertEqual(self.model.call_count["list_miners"], 1)
    
    def test_list_deals_success(self):
        """Test list deals endpoint with successful response."""
        # Make API request
        response = self.client.get("/filecoin/deals")
        
        # Check response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["operation"], "list_deals")
        self.assertEqual(len(data["deals"]), 2)
        self.assertEqual(data["count"], 2)
        
        # Verify model called
        self.assertEqual(self.model.call_count["list_deals"], 1)
    
    def test_ipfs_to_filecoin_success(self):
        """Test IPFS to Filecoin endpoint with successful response."""
        # Make API request
        request_data = {
            "cid": "QmTest",
            "miner": "f01234",
            "price": "0.0000000001",
            "duration": 518400,
            "wallet": "f1test",
            "verified": True,
            "fast_retrieval": True,
            "pin": True
        }
        response = self.client.post("/filecoin/from_ipfs", json=request_data)
        
        # Check response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["operation"], "ipfs_to_filecoin")
        self.assertEqual(data["ipfs_cid"], "QmTest")
        self.assertEqual(data["filecoin_cid"], "fil-QmTest")
        self.assertEqual(data["miner"], "f01234")
        
        # Verify model called
        self.assertEqual(self.model.call_count["ipfs_to_filecoin"], 1)
    
    def test_filecoin_to_ipfs_success(self):
        """Test Filecoin to IPFS endpoint with successful response."""
        # Make API request
        request_data = {
            "data_cid": "filTest",
            "pin": True
        }
        response = self.client.post("/filecoin/to_ipfs", json=request_data)
        
        # Check response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["operation"], "filecoin_to_ipfs")
        self.assertEqual(data["filecoin_cid"], "filTest")
        self.assertEqual(data["ipfs_cid"], "ipfs-filTest")
        
        # Verify model called
        self.assertEqual(self.model.call_count["filecoin_to_ipfs"], 1)
    
    def test_cross_backend_operations(self):
        """Test both cross-backend operations together."""
        # First, IPFS to Filecoin
        ipfs_request = {
            "cid": "QmTest123",
            "miner": "f01234",
            "price": "0.0000000001",
            "duration": 518400
        }
        ipfs_response = self.client.post("/filecoin/from_ipfs", json=ipfs_request)
        self.assertEqual(ipfs_response.status_code, 200)
        ipfs_data = ipfs_response.json()
        filecoin_cid = ipfs_data["filecoin_cid"]
        
        # Then, Filecoin to IPFS
        filecoin_request = {
            "data_cid": filecoin_cid,
            "pin": True
        }
        filecoin_response = self.client.post("/filecoin/to_ipfs", json=filecoin_request)
        self.assertEqual(filecoin_response.status_code, 200)
        filecoin_data = filecoin_response.json()
        new_ipfs_cid = filecoin_data["ipfs_cid"]
        
        # Verify the round trip
        self.assertTrue(filecoin_cid.startswith("fil-"))
        self.assertTrue(new_ipfs_cid.startswith("ipfs-"))
        
        # Check operation stats
        stats = self.model.get_stats()
        self.assertEqual(stats["operation_stats"]["total_operations"], 2)
        self.assertEqual(stats["operation_stats"]["successful_operations"], 2)
        self.assertEqual(stats["operation_stats"]["bytes_uploaded"], 1024 * 1024)
        self.assertEqual(stats["operation_stats"]["bytes_downloaded"], 1024 * 1024)


# Run tests
if __name__ == "__main__":
    # Configure test result output
    test_result_path = "test_results/filecoin_controller_integration_test.json"
    test_result = {
        "timestamp": time.time(),
        "test_module": "test_filecoin_integration.py",
        "test_description": "Test Filecoin integration with MCP server",
        "tests": {},
        "success": True
    }
    
    # Run tests and collect results
    test_loader = unittest.TestLoader()
    test_suite = test_loader.loadTestsFromTestCase(TestFilecoinIntegration)
    test_runner = unittest.TextTestRunner(verbosity=2)
    result = test_runner.run(test_suite)
    
    # Process test results
    test_result["tests"]["total"] = result.testsRun
    test_result["tests"]["failures"] = len(result.failures)
    test_result["tests"]["errors"] = len(result.errors)
    test_result["tests"]["skipped"] = len(result.skipped)
    test_result["success"] = result.wasSuccessful()
    
    # Save test result in structured format
    import os
    os.makedirs(os.path.dirname(test_result_path), exist_ok=True)
    with open(test_result_path, "w") as f:
        json.dump(test_result, f, indent=2)
    
    print(f"\nTest results saved to {test_result_path}")
    print(f"Success: {test_result['success']}")
    print(f"Total tests: {test_result['tests']['total']}")
    print(f"Failures: {test_result['tests']['failures']}")
    print(f"Errors: {test_result['tests']['errors']}")
    print(f"Skipped: {test_result['tests']['skipped']}")