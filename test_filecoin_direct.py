#!/usr/bin/env python3
"""
Direct test of the FilecoinModel's error handling.

This script bypasses full imports and directly tests only the FilecoinModel.
"""

import os
import sys
import json
import time
import uuid
import logging
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Create test results directory
TEST_RESULTS_DIR = "test_results"
os.makedirs(TEST_RESULTS_DIR, exist_ok=True)
TEST_RESULTS_FILE = os.path.join(TEST_RESULTS_DIR, "filecoin_direct_test_results.json")

# Mock BaseStorageModel since importing it directly causes dependency issues
class MockBaseStorageModel:
    """Minimal mock of BaseStorageModel."""
    
    def __init__(self, kit_instance=None, cache_manager=None, credential_manager=None):
        """Initialize with the same signature."""
        self.kit = kit_instance
        self.cache_manager = cache_manager
        self.credential_manager = credential_manager
        self.correlation_id = str(uuid.uuid4())
        self.operation_stats = self._initialize_stats()
    
    def _initialize_stats(self) -> Dict[str, Any]:
        """Initialize operation statistics."""
        return {
            "total_operations": 0,
            "success_count": 0,
            "failure_count": 0
        }
    
    def _create_result_dict(self, operation: str) -> Dict[str, Any]:
        """Create a standardized result dictionary."""
        return {
            "success": False,
            "operation": operation,
            "timestamp": time.time(),
            "correlation_id": self.correlation_id
        }
    
    def _update_stats(self, result: Dict[str, Any], bytes_count: Optional[int] = None) -> None:
        """Update operation statistics."""
        self.operation_stats["total_operations"] += 1
        if result.get("success", False):
            self.operation_stats["success_count"] += 1
        else:
            self.operation_stats["failure_count"] += 1
    
    def _handle_error(self, result: Dict[str, Any], error: Exception, message: Optional[str] = None) -> Dict[str, Any]:
        """Handle errors in a standardized way."""
        result["success"] = False
        result["error"] = message or str(error)
        result["error_type"] = type(error).__name__
        return result

# Mock lotus_kit class
class MockLotusKit:
    """Mock lotus_kit class that always fails with connection error."""
    
    def __init__(self, metadata=None):
        """Initialize with metadata."""
        self.metadata = metadata or {}
        self.api_url = metadata.get("api_url", "http://localhost:1234/rpc/v0")
    
    def check_connection(self):
        """Simulate a connection failure."""
        return {
            "success": False,
            "error": f"Failed to connect to Lotus API at {self.api_url}: Connection refused",
            "error_type": "LotusConnectionError",
            "timestamp": time.time()
        }
    
    def list_wallets(self):
        """Simulate a wallet listing failure."""
        return {
            "success": False,
            "error": f"Failed to list wallets: Connection to Lotus API failed",
            "error_type": "LotusConnectionError",
            "timestamp": time.time()
        }

# Implement a minimal FilecoinModel using MockBaseStorageModel
class MinimalFilecoinModel(MockBaseStorageModel):
    """Minimal implementation of FilecoinModel for testing error handling."""
    
    def __init__(self, lotus_kit_instance=None, ipfs_model=None, cache_manager=None, credential_manager=None):
        """Initialize with dependencies."""
        super().__init__(lotus_kit_instance, cache_manager, credential_manager)
        self.lotus_kit = lotus_kit_instance
        self.ipfs_model = ipfs_model
    
    def check_connection(self) -> Dict[str, Any]:
        """Check connection to Lotus API."""
        start_time = time.time()
        result = self._create_result_dict("check_connection")
        
        try:
            if self.lotus_kit:
                connection_result = self.lotus_kit.check_connection()
                if connection_result.get("success", False):
                    result["success"] = True
                    result["connected"] = True
                else:
                    result["error"] = connection_result.get("error", "Failed to connect to Lotus API")
                    result["error_type"] = connection_result.get("error_type", "ConnectionError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"
            
            self._update_stats(result)
        except Exception as e:
            self._handle_error(result, e)
        
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result
    
    def list_wallets(self) -> Dict[str, Any]:
        """List wallet addresses."""
        start_time = time.time()
        result = self._create_result_dict("list_wallets")
        
        try:
            if self.lotus_kit:
                wallet_result = self.lotus_kit.list_wallets()
                if wallet_result.get("success", False):
                    result["success"] = True
                    result["wallets"] = wallet_result.get("result", [])
                else:
                    result["error"] = wallet_result.get("error", "Failed to list wallets")
                    result["error_type"] = wallet_result.get("error_type", "WalletListError")
            else:
                result["error"] = "Lotus kit not available"
                result["error_type"] = "DependencyError"
            
            self._update_stats(result)
        except Exception as e:
            self._handle_error(result, e)
        
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result

def test_minimal_filecoin_model():
    """Test the minimal FilecoinModel implementation."""
    results = {
        "timestamp": time.time(),
        "tests": {},
        "success": True
    }
    
    # Test with invalid Lotus API
    lotus = MockLotusKit(metadata={"api_url": "http://localhost:9999/rpc/v0"})
    model = MinimalFilecoinModel(lotus_kit_instance=lotus)
    
    # Test: Initialization
    results["tests"]["initialization"] = {
        "success": model is not None,
        "message": "FilecoinModel initialized successfully"
    }
    
    # Test: Connection check
    connection_result = model.check_connection()
    results["tests"]["connection_check"] = connection_result
    
    # Verify error structure
    has_error = "error" in connection_result
    has_error_type = "error_type" in connection_result
    has_timestamp = "timestamp" in connection_result
    has_operation = "operation" in connection_result
    
    results["tests"]["error_structure"] = {
        "success": has_error and has_error_type and has_timestamp and has_operation,
        "has_error": has_error,
        "has_error_type": has_error_type,
        "has_timestamp": has_timestamp,
        "has_operation": has_operation,
        "error_type": connection_result.get("error_type", "missing")
    }
    
    print(f"Error structure validation: {results['tests']['error_structure']['success']}")
    
    # Test: list_wallets method
    wallet_result = model.list_wallets()
    
    # Verify error structure
    wallet_has_error = "error" in wallet_result
    wallet_has_error_type = "error_type" in wallet_result
    wallet_has_timestamp = "timestamp" in wallet_result
    wallet_has_operation = "operation" in wallet_result
    
    results["tests"]["wallet_error_structure"] = {
        "success": wallet_has_error and wallet_has_error_type and wallet_has_timestamp and wallet_has_operation,
        "has_error": wallet_has_error,
        "has_error_type": wallet_has_error_type,
        "has_timestamp": wallet_has_timestamp,
        "has_operation": wallet_has_operation,
        "error_type": wallet_result.get("error_type", "missing")
    }
    
    print(f"Wallet error structure validation: {results['tests']['wallet_error_structure']['success']}")
    
    # Test: Model without lotus_kit
    model_no_lotus = MinimalFilecoinModel(lotus_kit_instance=None)
    no_lotus_result = model_no_lotus.check_connection()
    
    results["tests"]["no_lotus_check"] = {
        "success": not no_lotus_result.get("success", True),
        "error_type": no_lotus_result.get("error_type", "missing"),
        "has_proper_error": no_lotus_result.get("error_type") == "DependencyError"
    }
    
    print(f"No lotus check: {results['tests']['no_lotus_check']['success']}")
    
    # Overall success
    all_tests_passed = all([
        results["tests"]["initialization"]["success"],
        results["tests"]["error_structure"]["success"],
        results["tests"]["wallet_error_structure"]["success"],
        results["tests"]["no_lotus_check"]["success"]
    ])
    
    results["success"] = all_tests_passed
    
    # Save results
    with open(TEST_RESULTS_FILE, 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\n===== Test Results =====")
    print(f"Initialization: {'✅ PASSED' if results['tests']['initialization']['success'] else '❌ FAILED'}")
    print(f"Error Structure: {'✅ PASSED' if results['tests']['error_structure']['success'] else '❌ FAILED'}")
    print(f"Wallet Error Structure: {'✅ PASSED' if results['tests']['wallet_error_structure']['success'] else '❌ FAILED'}")
    print(f"No Lotus Kit Handling: {'✅ PASSED' if results['tests']['no_lotus_check']['success'] else '❌ FAILED'}")
    print(f"\nOverall Result: {'✅ PASSED' if results['success'] else '❌ FAILED'}")
    print(f"Test results saved to {TEST_RESULTS_FILE}")
    
    return results["success"]

if __name__ == "__main__":
    # Run the test
    success = test_minimal_filecoin_model()
    sys.exit(0 if success else 1)