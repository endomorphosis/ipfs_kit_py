#!/usr/bin/env python3
"""
Minimal test script for testing Filecoin model error handling.
This script avoids importing the full API stack to prevent dependency issues.
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
import tempfile
import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Add the project root to the Python path if needed
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import modules in a way that avoids the full import chain
# Create a test results directory
TEST_RESULTS_DIR = "test_results"
os.makedirs(TEST_RESULTS_DIR, exist_ok=True)
TEST_RESULTS_FILE = os.path.join(TEST_RESULTS_DIR, "filecoin_minimal_test_results.json")

# Try to import both FilecoinModel variants
models_available = {"standard": False, "anyio": False}

try:
    # Import standard FilecoinModel with minimal import tree
    from ipfs_kit_py.mcp.models.storage.filecoin_model import FilecoinModel
    logger.info("Successfully imported FilecoinModel")
    models_available["standard"] = True
    
    # Separately import lotus_kit (avoid cross-module dependencies)
    try:
        from ipfs_kit_py.lotus_kit import lotus_kit
        logger.info("Successfully imported lotus_kit")
    except ImportError as e:
        logger.warning(f"Failed to import lotus_kit: {str(e)}")
except ImportError as e:
    logger.warning(f"Failed to import standard FilecoinModel: {str(e)}")

try:
    # Import AnyIO version if available
    from ipfs_kit_py.mcp.models.storage.filecoin_model_anyio import FilecoinModelAnyIO
    logger.info("Successfully imported FilecoinModelAnyIO")
    models_available["anyio"] = True
except ImportError as e:
    logger.warning(f"Failed to import FilecoinModelAnyIO: {str(e)}")

if not models_available["standard"] and not models_available["anyio"]:
    logger.error("No FilecoinModel variants available. Exiting.")
    sys.exit(1)

def test_standard_filecoin_model():
    """Test graceful error handling in the standard FilecoinModel."""
    if not models_available["standard"]:
        logger.info("Skipping standard FilecoinModel test (not available)")
        return {"success": False, "skipped": True, "reason": "Standard FilecoinModel not available"}
    
    logger.info("===== Testing Standard FilecoinModel =====")
    
    results = {
        "success": True,
        "tests": {},
        "timestamp": time.time()
    }
    
    try:
        # Create lotus_kit with incorrect API URL to force failure
        lotus = lotus_kit(metadata={"api_url": "http://localhost:9999/rpc/v0"})
        
        # Create FilecoinModel instance
        model = FilecoinModel(lotus_kit_instance=lotus)
        
        # Test: Initialization
        results["tests"]["initialization"] = {
            "success": model is not None,
            "message": "FilecoinModel initialized successfully"
        }
        
        # Test: Connection check (should fail)
        connection_result = model.check_connection()
        results["tests"]["connection_check"] = connection_result
        
        # Verify error structure
        if not connection_result.get("success", False):
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
            
            logger.info(f"Error structure validation: {results['tests']['error_structure']['success']}")
        
        # Test selected methods to ensure consistent error handling
        test_methods = [
            ("list_wallets", []),
            ("get_wallet_balance", ["fake_address"]),
            ("create_wallet", ["bls"]),
            ("list_miners", []),
            ("list_deals", [])
        ]
        
        method_results = {}
        for method_name, args in test_methods:
            try:
                if not hasattr(model, method_name):
                    method_results[method_name] = {
                        "success": False,
                        "error": "Method not implemented"
                    }
                    continue
                
                # Call the method
                method = getattr(model, method_name)
                result = method(*args)
                
                # Check if failed with proper error structure
                has_success = "success" in result
                has_error = "error" in result
                has_error_type = "error_type" in result
                has_timestamp = "timestamp" in result
                has_operation = "operation" in result
                
                method_results[method_name] = {
                    "success": not result.get("success", True) and has_success and has_error and has_error_type and has_timestamp and has_operation,
                    "has_proper_error_structure": has_success and has_error and has_error_type and has_timestamp and has_operation,
                    "error_type": result.get("error_type", "missing")
                }
                
                logger.info(f"Method {method_name} handling: {'SUCCESS' if method_results[method_name]['success'] else 'FAILURE'}")
                
            except Exception as e:
                method_results[method_name] = {
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
                logger.error(f"Unexpected exception in {method_name}: {e}")
        
        results["tests"]["methods"] = method_results
        
        # Check if all tests passed
        init_success = results["tests"].get("initialization", {}).get("success", False)
        error_structure_success = results["tests"].get("error_structure", {}).get("success", False)
        
        # Check if all methods have proper error structure
        methods_success = True
        for method_name, method_result in method_results.items():
            if not method_result.get("success", False) and "Method not implemented" not in method_result.get("error", ""):
                methods_success = False
                break
        
        # Overall success requires initialization and proper error handling
        results["success"] = init_success and error_structure_success and methods_success
        
    except Exception as e:
        results["success"] = False
        results["error"] = str(e)
        results["error_type"] = type(e).__name__
        logger.exception("Error in standard FilecoinModel test")
    
    return results

def test_anyio_filecoin_model():
    """Test graceful error handling in the AnyIO FilecoinModel."""
    if not models_available["anyio"]:
        logger.info("Skipping FilecoinModelAnyIO test (not available)")
        return {"success": False, "skipped": True, "reason": "FilecoinModelAnyIO not available"}
    
    logger.info("===== Testing FilecoinModelAnyIO =====")
    
    results = {
        "success": True,
        "tests": {},
        "timestamp": time.time()
    }
    
    try:
        # Create FilecoinModelAnyIO instance
        model = FilecoinModelAnyIO()
        
        # Test: Initialization
        results["tests"]["initialization"] = {
            "success": model is not None,
            "message": "FilecoinModelAnyIO initialized successfully"
        }
        
        # Test: Connection check (should fail)
        connection_result = model.check_connection()
        results["tests"]["connection_check"] = connection_result
        
        # Verify error structure (similar to standard model)
        if not connection_result.get("success", False):
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
            
            logger.info(f"Error structure validation: {results['tests']['error_structure']['success']}")
        
        # Check a subset of methods
        test_methods = [
            ("list_wallets", []),
            ("get_wallet_balance", ["fake_address"]),
            ("list_miners", [])
        ]
        
        method_results = {}
        for method_name, args in test_methods:
            try:
                if not hasattr(model, method_name):
                    method_results[method_name] = {
                        "success": False,
                        "error": "Method not implemented"
                    }
                    continue
                
                # Call the method
                method = getattr(model, method_name)
                result = method(*args)
                
                # Check if failed with proper error structure
                has_success = "success" in result
                has_error = "error" in result
                has_error_type = "error_type" in result
                has_timestamp = "timestamp" in result
                has_operation = "operation" in result
                
                method_results[method_name] = {
                    "success": not result.get("success", True) and has_success and has_error and has_error_type and has_timestamp and has_operation,
                    "has_proper_error_structure": has_success and has_error and has_error_type and has_timestamp and has_operation,
                    "error_type": result.get("error_type", "missing")
                }
                
                logger.info(f"Method {method_name} handling: {'SUCCESS' if method_results[method_name]['success'] else 'FAILURE'}")
                
            except Exception as e:
                method_results[method_name] = {
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
                logger.error(f"Unexpected exception in {method_name}: {e}")
        
        results["tests"]["methods"] = method_results
        
        # Check if all tests passed
        init_success = results["tests"].get("initialization", {}).get("success", False)
        error_structure_success = results["tests"].get("error_structure", {}).get("success", False)
        
        # Check if all methods have proper error structure
        methods_success = True
        for method_name, method_result in method_results.items():
            if not method_result.get("success", False) and "Method not implemented" not in method_result.get("error", ""):
                methods_success = False
                break
        
        # Overall success requires initialization and proper error handling
        results["success"] = init_success and error_structure_success and methods_success
        
    except Exception as e:
        results["success"] = False
        results["error"] = str(e)
        results["error_type"] = type(e).__name__
        logger.exception("Error in FilecoinModelAnyIO test")
    
    return results

def run_all_tests():
    """Run all available Filecoin model tests."""
    test_results = {
        "timestamp": time.time(),
        "standard_model": None,
        "anyio_model": None,
        "success": True
    }
    
    # Test standard model
    if models_available["standard"]:
        standard_results = test_standard_filecoin_model()
        test_results["standard_model"] = standard_results
        test_results["success"] = test_results["success"] and standard_results.get("success", False)
    else:
        test_results["standard_model"] = {"success": False, "skipped": True, "reason": "Standard FilecoinModel not available"}
    
    # Test AnyIO model
    if models_available["anyio"]:
        anyio_results = test_anyio_filecoin_model()
        test_results["anyio_model"] = anyio_results
        test_results["success"] = test_results["success"] and anyio_results.get("success", False)
    else:
        test_results["anyio_model"] = {"success": False, "skipped": True, "reason": "FilecoinModelAnyIO not available"}
    
    # Save results
    with open(TEST_RESULTS_FILE, 'w') as f:
        json.dump(test_results, f, indent=2)
    
    # Print summary
    print("\n===== Filecoin Model Test Summary =====")
    
    # Standard model results
    if test_results["standard_model"].get("skipped", False):
        print("Standard FilecoinModel: ⚠️ SKIPPED")
    else:
        print(f"Standard FilecoinModel: {'✅ PASSED' if test_results['standard_model'].get('success', False) else '❌ FAILED'}")
        
        # Print error structure validation
        error_structure = test_results["standard_model"].get("tests", {}).get("error_structure", {})
        if error_structure:
            print(f"  Error Structure Validation: {'✅ PASSED' if error_structure.get('success', False) else '❌ FAILED'}")
        
        # Print method results
        method_results = test_results["standard_model"].get("tests", {}).get("methods", {})
        for method_name, result in method_results.items():
            status = "✅" if result.get("success", False) else "❌"
            print(f"  Method {method_name}: {status}")
    
    # AnyIO model results
    if test_results["anyio_model"].get("skipped", False):
        print("\nFilecoinModelAnyIO: ⚠️ SKIPPED")
    else:
        print(f"\nFilecoinModelAnyIO: {'✅ PASSED' if test_results['anyio_model'].get('success', False) else '❌ FAILED'}")
        
        # Print error structure validation
        error_structure = test_results["anyio_model"].get("tests", {}).get("error_structure", {})
        if error_structure:
            print(f"  Error Structure Validation: {'✅ PASSED' if error_structure.get('success', False) else '❌ FAILED'}")
        
        # Print method results
        method_results = test_results["anyio_model"].get("tests", {}).get("methods", {})
        for method_name, result in method_results.items():
            status = "✅" if result.get("success", False) else "❌"
            print(f"  Method {method_name}: {status}")
    
    # Overall result
    print(f"\nOverall Test Result: {'✅ PASSED' if test_results['success'] else '❌ FAILED'}")
    print(f"Test results saved to {TEST_RESULTS_FILE}")
    
    return test_results["success"]

if __name__ == "__main__":
    # Run the test
    success = run_all_tests()
    sys.exit(0 if success else 1)