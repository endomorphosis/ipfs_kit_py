#!/usr/bin/env python3
"""
Comprehensive test script for Filecoin in MCP server.

This test script covers:
1. FilecoinModel direct testing (without requiring Lotus daemon)
2. MCP server integration with FilecoinModel
3. Cross-backend operations between IPFS and Filecoin
4. Standard MCP patterns and error handling verification
"""

import os
import sys
import json
import time
import tempfile
import anyio
import logging
from pathlib import Path
from typing import Dict, Any, List

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("filecoin_test")

# Import MCP components
try:
    # Start with just the essential components to avoid libp2p issues
    print("Importing lotus_kit...")
    from ipfs_kit_py.lotus_kit import lotus_kit
    print("Importing FilecoinModel...")
    from ipfs_kit_py.mcp.models.storage.filecoin_model import FilecoinModel
    print("Successfully imported core modules")

    # Try to import MCPServer but don't exit if it fails
    try:
        print("Importing MCPServer...")
        from ipfs_kit_py.mcp.server_bridge import MCPServer  # Refactored import
        print("Successfully imported MCPServer")
        HAVE_MCP_SERVER = True
    except ImportError as e:
        print(f"Warning: Could not import MCPServer: {e}")
        HAVE_MCP_SERVER = False

    # Try to import ipfs_kit but don't exit if it fails
    try:
        print("Importing ipfs_kit...")
        from ipfs_kit_py.ipfs_kit import ipfs_kit
        print("Successfully imported ipfs_kit")
        HAVE_IPFS_KIT = True
    except ImportError as e:
        print(f"Warning: Could not import ipfs_kit: {e}")
        HAVE_IPFS_KIT = False

except ImportError as e:
    print(f"Error importing core modules: {e}")
    sys.exit(1)

# Constants
TEST_RESULTS_DIR = "test_results"
TEST_RESULTS_FILE = os.path.join(TEST_RESULTS_DIR, "filecoin_comprehensive_test_results.json")

# Create results directory if it doesn't exist
os.makedirs(TEST_RESULTS_DIR, exist_ok=True)

def test_filecoin_model_direct():
    """Test FilecoinModel directly without MCP server."""
    logger.info("===== Testing FilecoinModel Directly =====")
    results = {
        "success": True,
        "tests": {}
    }

    try:
        # Create lotus_kit instance with incorrect API URL to force failure
        lotus_kit_instance = lotus_kit(metadata={"api_url": "http://localhost:9999/rpc/v0"})

        # Create FilecoinModel with the lotus_kit instance
        model = FilecoinModel(lotus_kit_instance=lotus_kit_instance)

        # Test: Model initialization
        results["tests"]["initialization"] = {
            "success": model is not None,
            "message": "FilecoinModel initialized successfully"
        }

        # Test: Connection checking
        connection_result = model.check_connection()
        results["tests"]["connection_check"] = connection_result
        logger.info(f"Connection check result: {connection_result.get('success', False)}, Error: {connection_result.get('error', 'None')}")

        # Verify error handling pattern
        if not connection_result.get("success", False):
            # Check for proper error structure
            has_error_msg = "error" in connection_result
            has_error_type = "error_type" in connection_result
            has_timestamp = "timestamp" in connection_result
            has_operation = "operation" in connection_result

            results["tests"]["error_pattern"] = {
                "success": has_error_msg and has_error_type and has_timestamp and has_operation,
                "has_error_msg": has_error_msg,
                "has_error_type": has_error_type,
                "has_timestamp": has_timestamp,
                "has_operation": has_operation,
                "error_type": connection_result.get("error_type", "missing")
            }
            logger.info(f"Error pattern validation: {results['tests']['error_pattern']['success']}")

        # Test a selection of methods to ensure consistent interface
        test_methods = [
            ("list_wallets", []),
            ("get_wallet_balance", ["fake_address"]),
            ("create_wallet", ["bls"]),
            ("list_miners", []),
            ("list_deals", []),
            ("list_imports", [])
        ]

        method_results = {}
        for method_name, args in test_methods:
            try:
                # Get and call the method
                method = getattr(model, method_name)
                result = method(*args)

                # Check result structure
                has_success = "success" in result
                has_operation = "operation" in result
                has_timestamp = "timestamp" in result

                # For failed operations, check error structure
                if not result.get("success", False):
                    has_error = "error" in result
                    has_error_type = "error_type" in result

                    # Method interface is consistent if it has all these fields
                    is_consistent = has_success and has_operation and has_timestamp and has_error and has_error_type
                else:
                    # Method succeeded (unlikely with invalid Lotus API)
                    is_consistent = has_success and has_operation and has_timestamp

                method_results[method_name] = {
                    "success": is_consistent,
                    "has_proper_interface": is_consistent,
                    "operation": result.get("operation", "missing")
                }

                logger.info(f"Method {method_name} interface validation: {is_consistent}")

            except AttributeError:
                method_results[method_name] = {
                    "success": False,
                    "error": "Method not implemented"
                }
                logger.warning(f"Method {method_name} not implemented")

            except Exception as e:
                method_results[method_name] = {
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
                logger.error(f"Error testing method {method_name}: {e}")

        # Add method test results
        results["tests"]["method_interface"] = method_results

        # Test cross-backend operation interface (without executing)
        try:
            # Create method arguments
            ipfs_model = None  # This will cause ipfs_to_filecoin to fail with "IPFS model not available"

            # Try the method (it should fail gracefully)
            ipfs_to_filecoin_result = model.ipfs_to_filecoin(
                cid="QmTest123",
                miner="t01000",
                price="0",
                duration=1000,
                wallet=None,
                verified=False,
                fast_retrieval=True,
                pin=True
            )

            # Check if failed with proper error message
            expected_error = "IPFS model not available"
            has_expected_error = ipfs_to_filecoin_result.get("error", "") == expected_error
            has_expected_error_type = ipfs_to_filecoin_result.get("error_type", "") == "DependencyError"

            results["tests"]["cross_backend_validation"] = {
                "success": not ipfs_to_filecoin_result.get("success", False) and has_expected_error and has_expected_error_type,
                "has_expected_error": has_expected_error,
                "has_expected_error_type": has_expected_error_type,
                "actual_error": ipfs_to_filecoin_result.get("error", "missing"),
                "actual_error_type": ipfs_to_filecoin_result.get("error_type", "missing")
            }
            logger.info(f"Cross-backend validation: {results['tests']['cross_backend_validation']['success']}")

        except Exception as e:
            results["tests"]["cross_backend_validation"] = {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
            logger.error(f"Error in cross-backend validation: {e}")

        # Overall success - model works correctly even without Lotus
        # Define critical tests that must pass
        critical_tests = {
            "initialization": results["tests"].get("initialization", {"success": False}),
            "error_pattern": results["tests"].get("error_pattern", {"success": False}),
            "method_interface": results["tests"].get("method_interface", {}),
            "cross_backend_validation": results["tests"].get("cross_backend_validation", {"success": False})
        }

        # Method interface is successful if all methods have proper interfaces
        method_interface_success = True
        if "method_interface" in results["tests"]:
            method_results = results["tests"]["method_interface"]
            method_interface_success = all(
                method_info.get("success", False)
                for method_name, method_info in method_results.items()
            )
        critical_tests["method_interface"] = {"success": method_interface_success}

        # Only check critical tests for overall success (excluding connection_check)
        all_critical_tests_passed = all(test.get("success", False) for test in critical_tests.values())

        # Log test status
        logger.info("Critical test results:")
        for name, test in critical_tests.items():
            logger.info(f"  {name}: {'PASSED' if test.get('success', False) else 'FAILED'}")

        results["success"] = all_critical_tests_passed
        results["message"] = "FilecoinModel direct tests completed successfully" if all_critical_tests_passed else "Some critical FilecoinModel direct tests failed"

        # Add test categorization for reporting
        results["critical_tests"] = {k: v.get("success", False) for k, v in critical_tests.items()}

    except Exception as e:
        results["success"] = False
        results["error"] = str(e)
        results["error_type"] = type(e).__name__
        logger.exception("Error in direct FilecoinModel tests")

    return results

async def test_mcp_server_integration():
    """Test FilecoinModel integration with MCP server."""
    logger.info("===== Testing FilecoinModel Integration with MCP Server =====")
    results = {
        "success": True,
        "tests": {}
    }

    # Create temp directory for MCP server persistence
    with tempfile.TemporaryDirectory() as temp_dir:
        logger.info(f"Created temporary directory for MCP server: {temp_dir}")

        try:
            # Create MCP server with debug mode enabled
            logger.info("Initializing MCP server...")
            mcp_server = MCPServer(
                debug_mode=True,
                log_level="INFO",
                persistence_path=temp_dir,
                isolation_mode=True  # Use isolation mode to avoid affecting the host system
            )

            # Test: MCP Server initialized
            results["tests"]["server_initialization"] = {
                "success": mcp_server is not None,
                "message": "MCP server initialized successfully"
            }
            logger.info("MCP server initialized successfully")

            # Check if Filecoin model exists in MCP server
            filecoin_model = mcp_server.models.get("storage_filecoin")
            has_filecoin_model = filecoin_model is not None

            results["tests"]["has_filecoin_model"] = {
                "success": has_filecoin_model,
                "message": "Filecoin model found in MCP server" if has_filecoin_model else "Filecoin model not found in MCP server"
            }

            if not has_filecoin_model:
                logger.warning("Filecoin model not found in MCP server")
                results["success"] = False
                return results

            logger.info("Filecoin model found in MCP server")

            # Test: Filecoin model connection check
            connection_result = filecoin_model.check_connection()
            results["tests"]["server_connection_check"] = connection_result

            # Since we expect this to fail (no Lotus daemon), check if error handling is consistent
            if not connection_result.get("success", False):
                # Verify proper error structure as before
                has_error_msg = "error" in connection_result
                has_error_type = "error_type" in connection_result
                has_timestamp = "timestamp" in connection_result
                has_operation = "operation" in connection_result

                results["tests"]["server_error_pattern"] = {
                    "success": has_error_msg and has_error_type and has_timestamp and has_operation,
                    "has_error_msg": has_error_msg,
                    "has_error_type": has_error_type,
                    "has_timestamp": has_timestamp,
                    "has_operation": has_operation,
                    "error_type": connection_result.get("error_type", "missing")
                }
                logger.info(f"Server error pattern validation: {results['tests']['server_error_pattern']['success']}")

            # Check if IPFS model exists for cross-backend operations
            ipfs_model = mcp_server.models.get("ipfs")
            has_ipfs_model = ipfs_model is not None

            results["tests"]["has_ipfs_model"] = {
                "success": has_ipfs_model,
                "message": "IPFS model found in MCP server" if has_ipfs_model else "IPFS model not found in MCP server"
            }

            if has_ipfs_model:
                logger.info("IPFS model found in MCP server")

                # Test cross-model integration (will fail but with proper error)
                # Create a test file
                with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as temp_file:
                    temp_path = temp_file.name
                    content = f"Test file for Filecoin integration, generated at {time.time()}"
                    temp_file.write(content.encode('utf-8'))
                    temp_file.flush()

                try:
                    # Check which IPFS method is available for adding content
                    logger.info("Checking IPFS model methods for adding content...")
                    ipfs_add_methods = [
                        method for method in dir(ipfs_model)
                        if callable(getattr(ipfs_model, method, None))
                        and (method.startswith("add") or "add" in method)
                    ]
                    logger.info(f"Available IPFS add methods: {ipfs_add_methods}")

                    # Choose appropriate method if available
                    if "add_file" in ipfs_add_methods:
                        logger.info(f"Adding test file to IPFS using add_file: {temp_path}")
                        add_result = ipfs_model.add_file(temp_path)
                    elif "add_content" in ipfs_add_methods:
                        logger.info(f"Adding test file to IPFS using add_content: {temp_path}")
                        with open(temp_path, "rb") as f:
                            content_bytes = f.read()
                        add_result = ipfs_model.add_content(content_bytes)
                    elif "add" in ipfs_add_methods:
                        logger.info(f"Adding test file to IPFS using add: {temp_path}")
                        add_result = ipfs_model.add(temp_path)
                    else:
                        logger.warning("No suitable IPFS add method found")
                        add_result = {"success": False, "error": "No suitable IPFS add method found"}

                    results["tests"]["ipfs_add_file"] = add_result

                    if add_result.get("success", False):
                        # Get CID field (could be named differently)
                        cid = add_result.get("cid", add_result.get("Hash", None))
                        if not cid and "hash" in add_result:
                            cid = add_result.get("hash")

                        logger.info(f"Successfully added file to IPFS with CID: {cid}")

                        # Now test IPFS to Filecoin integration
                        ipfs_to_filecoin_result = filecoin_model.ipfs_to_filecoin(
                            cid=cid,
                            miner="t01000",  # Fake miner address
                            price="0",
                            duration=1000,
                            wallet=None,
                            verified=False,
                            fast_retrieval=True,
                            pin=True
                        )

                        results["tests"]["server_ipfs_to_filecoin"] = ipfs_to_filecoin_result

                        # This should fail because Lotus is not available, but fail gracefully
                        if not ipfs_to_filecoin_result.get("success", False):
                            has_error = "error" in ipfs_to_filecoin_result
                            has_error_type = "error_type" in ipfs_to_filecoin_result

                            results["tests"]["server_cross_backend_error"] = {
                                "success": has_error and has_error_type,
                                "has_error": has_error,
                                "has_error_type": has_error_type,
                                "error": ipfs_to_filecoin_result.get("error", "missing"),
                                "error_type": ipfs_to_filecoin_result.get("error_type", "missing")
                            }
                            logger.info(f"Server cross-backend error validation: {results['tests']['server_cross_backend_error']['success']}")
                    else:
                        logger.warning(f"Failed to add file to IPFS: {add_result.get('error', 'unknown error')}")
                        results["tests"]["ipfs_add_error"] = {
                            "success": False,
                            "error": add_result.get("error", "Unknown error"),
                            "available_methods": ipfs_add_methods
                        }

                except Exception as e:
                    logger.exception(f"Error during IPFS content addition: {e}")
                    results["tests"]["ipfs_add_error"] = {
                        "success": False,
                        "error": str(e),
                        "error_type": type(e).__name__
                    }

                finally:
                    # Clean up the temporary file
                    try:
                        os.unlink(temp_path)
                    except Exception as e:
                        logger.warning(f"Failed to delete temporary file: {e}")
            else:
                logger.warning("IPFS model not found in MCP server, skipping cross-backend tests")

            # Check if FilecoinController exists and is registered with FastAPI
            mcp_router = getattr(mcp_server, "router", None)
            has_router = mcp_router is not None

            if has_router:
                # Check if filecoin routes are registered (by checking route paths)
                all_routes = mcp_router.routes
                filecoin_routes = [route for route in all_routes if hasattr(route, "path") and "filecoin" in str(route.path)]

                results["tests"]["has_filecoin_routes"] = {
                    "success": len(filecoin_routes) > 0,
                    "route_count": len(filecoin_routes),
                    "routes": [str(route.path) for route in filecoin_routes]
                }

                if len(filecoin_routes) > 0:
                    logger.info(f"Found {len(filecoin_routes)} Filecoin routes in MCP server")
                else:
                    logger.warning("No Filecoin routes found in MCP server")
            else:
                logger.warning("MCP server router not found, skipping route check")
                results["tests"]["has_filecoin_routes"] = {
                    "success": False,
                    "error": "MCP server router not found"
                }

            # Overall success - server integration works correctly
            # Define critical tests that must pass
            critical_tests = {
                "server_initialization": results["tests"].get("server_initialization", {"success": False}),
                "has_filecoin_model": results["tests"].get("has_filecoin_model", {"success": False}),
                "server_error_pattern": results["tests"].get("server_error_pattern", {"success": True})  # This one's optional
            }

            # Non-critical tests that provide additional information but shouldn't fail the whole test
            non_critical_tests = {
                "ipfs_add_file": results["tests"].get("ipfs_add_file", {"success": True}),
                "server_cross_backend_error": results["tests"].get("server_cross_backend_error", {"success": True})
            }

            # Only check critical tests for overall success
            all_critical_tests_passed = all(test.get("success", False) for test in critical_tests.values())

            # Log test status
            logger.info("Critical test results:")
            for name, test in critical_tests.items():
                logger.info(f"  {name}: {'PASSED' if test.get('success', False) else 'FAILED'}")

            logger.info("Non-critical test results:")
            for name, test in non_critical_tests.items():
                if name in results["tests"]:
                    logger.info(f"  {name}: {'PASSED' if test.get('success', False) else 'FAILED'}")

            results["success"] = all_critical_tests_passed
            results["message"] = "MCP server integration tests completed successfully" if all_critical_tests_passed else "Some critical MCP server integration tests failed"

            # Add test categorization for reporting
            results["critical_tests"] = {k: v.get("success", False) for k, v in critical_tests.items()}
            results["non_critical_tests"] = {k: results["tests"].get(k, {}).get("success", False)
                                          for k in non_critical_tests.keys()
                                          if k in results["tests"]}

        except Exception as e:
            results["success"] = False
            results["error"] = str(e)
            results["error_type"] = type(e).__name__
            logger.exception("Error in MCP server integration tests")

        finally:
            # Clean up MCP server
            try:
                logger.info("Shutting down MCP server...")
                if 'mcp_server' in locals():
                    mcp_server.shutdown()
            except Exception as e:
                logger.error(f"Error shutting down MCP server: {e}")

    return results

async def main():
    """Run all tests and generate report."""
    logger.info("Starting comprehensive Filecoin test")

    test_results = {
        "success": True,
        "direct_tests": None,
        "server_tests": None,
        "timestamp": time.time()
    }

    try:
        # Run direct FilecoinModel tests
        logger.info("Running direct FilecoinModel tests...")
        direct_results = test_filecoin_model_direct()
        test_results["direct_tests"] = direct_results
        test_results["success"] = test_results["success"] and direct_results.get("success", False)

        # Run MCP server integration tests only if MCPServer is available
        if HAVE_MCP_SERVER:
            logger.info("Running MCP server integration tests...")
            server_results = await test_mcp_server_integration()
            test_results["server_tests"] = server_results
            test_results["success"] = test_results["success"] and server_results.get("success", False)
        else:
            logger.info("Skipping MCP server integration tests (MCPServer not available).")
            test_results["server_tests"] = {
                "success": True,
                "skipped": True,
                "reason": "MCPServer not available"
            }

        # Save the test results
        with open(TEST_RESULTS_FILE, 'w') as f:
            json.dump(test_results, f, indent=2)

        # Print summary
        print("\n===== Test Summary =====")
        print("Direct FilecoinModel Tests:")
        if "critical_tests" in direct_results:
            for name, passed in direct_results["critical_tests"].items():
                print(f"  - {name}: {'✅ PASSED' if passed else '❌ FAILED'}")
        print(f"Overall Direct Tests: {'✅ PASSED' if direct_results.get('success', False) else '❌ FAILED'}")

        # Print server test results if they were run
        if not test_results["server_tests"].get("skipped", False):
            print("\nMCP Server Integration Tests:")
            server_results = test_results["server_tests"]
            if "critical_tests" in server_results:
                for name, passed in server_results.get("critical_tests", {}).items():
                    print(f"  - {name}: {'✅ PASSED' if passed else '❌ FAILED'}")
            print(f"Overall Server Tests: {'✅ PASSED' if server_results.get('success', False) else '❌ FAILED'}")
        else:
            print("\nMCP Server Integration Tests: ⚠️ SKIPPED (MCPServer not available)")

        print(f"\nOverall Result: {'✅ PASSED' if test_results['success'] else '❌ FAILED'}")
        print(f"Test results saved to {TEST_RESULTS_FILE}")

        return test_results["success"]

    except Exception as e:
        logger.exception("Error in main test sequence")
        test_results["success"] = False
        test_results["error"] = str(e)
        test_results["error_type"] = type(e).__name__

        # Save the test results
        with open(TEST_RESULTS_FILE, 'w') as f:
            json.dump(test_results, f, indent=2)

        print(f"\n❌ Test failed with error: {e}")
        print(f"Test results saved to {TEST_RESULTS_FILE}")

        return False

if __name__ == "__main__":
    # Run the test
    success = anyio.run(main())
    sys.exit(0 if success else 1)
