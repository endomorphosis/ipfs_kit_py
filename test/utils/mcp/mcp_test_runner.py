#!/usr/bin/env python3
"""
Consolidated MCP Test Runner

This script consolidates functionality from all previous test runners:
- run_all_tests.py
- run_direct_tests.py
- run_mcp_tests.py
- run_network_tests.py
- run_mcp_network_tests.py
- run_mcp_communication_test.py
- run_mcp_partition_test.py
- run_mcp_partial_partition_test.py
- run_mcp_intermittent_connectivity_test.py
- run_mcp_time_based_recovery_test.py
- run_storage_backend_tests.py
- run_s3_test.py
- run_streaming_metrics_test.py

It provides a comprehensive solution for running all types of tests with
configurable verbosity and test selection.
"""

import os
import sys
import argparse
import unittest
import logging
import importlib
from typing import List, Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)-8s] [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("mcp_test_runner")

# Test categories
class TestCategories:
    """Constants for test categories."""
    UNIT = "unit"
    INTEGRATION = "integration"
    NETWORK = "network"
    STORAGE = "storage"
    STREAMING = "streaming"
    WEBRTC = "webrtc"
    ALL = "all"

    @classmethod
    def get_all(cls):
        """Get all test categories."""
        return [
            cls.UNIT, cls.INTEGRATION, cls.NETWORK,
            cls.STORAGE, cls.STREAMING, cls.WEBRTC, cls.ALL
        ]

# Network test types
class NetworkTestTypes:
    """Constants for network test types."""
    PARTITION = "partition"
    PARTIAL_PARTITION = "partial_partition"
    INTERMITTENT = "intermittent"
    TIME_BASED = "time_based"
    CASCADING = "cascading"
    ALL = "all"

    @classmethod
    def get_all(cls):
        """Get all network test types."""
        return [
            cls.PARTITION, cls.PARTIAL_PARTITION, cls.INTERMITTENT,
            cls.TIME_BASED, cls.CASCADING, cls.ALL
        ]

# Storage backend test types
class StorageTestTypes:
    """Constants for storage test types."""
    LOCAL = "local"
    S3 = "s3"
    IPFS = "ipfs"
    FILECOIN = "filecoin"
    ALL = "all"

    @classmethod
    def get_all(cls):
        """Get all storage test types."""
        return [cls.LOCAL, cls.S3, cls.IPFS, cls.FILECOIN, cls.ALL]

class TestRunner:
    """Consolidated test runner for all MCP test types."""

    def __init__(
        self,
        categories: List[str] = None,
        verbosity: int = 2,
        log_level: str = "INFO",
        network_test_types: List[str] = None,
        storage_test_types: List[str] = None,
        test_file_pattern: str = None,
        specific_tests: List[str] = None,
        parallel: bool = False,
        num_processes: int = None,
        timeout: int = 300,
        debug: bool = False,
        config: Dict[str, Any] = None
    ):
        """
        Initialize the test runner.

        Args:
            categories: Test categories to run (unit, integration, network, etc.)
            verbosity: Verbosity level (0-3)
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
            network_test_types: Network test types to run
            storage_test_types: Storage test types to run
            test_file_pattern: Pattern for test file names
            specific_tests: Specific test names to run
            parallel: Run tests in parallel
            num_processes: Number of processes for parallel tests
            timeout: Test timeout in seconds
            debug: Enable debug mode
            config: Additional test configuration
        """
        self.categories = categories or [TestCategories.ALL]
        self.verbosity = verbosity
        self.log_level = log_level
        self.network_test_types = network_test_types or [NetworkTestTypes.ALL]
        self.storage_test_types = storage_test_types or [StorageTestTypes.ALL]
        self.test_file_pattern = test_file_pattern
        self.specific_tests = specific_tests or []
        self.parallel = parallel
        self.num_processes = num_processes
        self.timeout = timeout
        self.debug = debug
        self.config = config or {}

        # Set up logging
        self._setup_logging()

        # Test suite
        self.test_suite = unittest.TestSuite()

    def _setup_logging(self):
        """Set up logging configuration."""
        # Set global log level
        logging.getLogger().setLevel(getattr(logging, self.log_level))

        # For network tests, configure special logging
        if TestCategories.NETWORK in self.categories or TestCategories.ALL in self.categories:
            # Set global log level to ERROR to reduce output
            if not self.debug:
                logging.getLogger().setLevel(logging.ERROR)

            # Only show our test logger at INFO level
            test_logger = logging.getLogger("enhanced_mcp_discovery_test")
            test_logger.setLevel(logging.INFO)
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(logging.INFO)
            test_logger.addHandler(handler)

    def discover_tests(self):
        """Discover tests based on configurations."""
        logger.info("Discovering tests...")

        # Determine which test categories to run
        run_all = TestCategories.ALL in self.categories

        # Unit tests
        if run_all or TestCategories.UNIT in self.categories:
            self._discover_unit_tests()

        # Integration tests
        if run_all or TestCategories.INTEGRATION in self.categories:
            self._discover_integration_tests()

        # Network tests
        if run_all or TestCategories.NETWORK in self.categories:
            self._discover_network_tests()

        # Storage tests
        if run_all or TestCategories.STORAGE in self.categories:
            self._discover_storage_tests()

        # Streaming tests
        if run_all or TestCategories.STREAMING in self.categories:
            self._discover_streaming_tests()

        # WebRTC tests
        if run_all or TestCategories.WEBRTC in self.categories:
            self._discover_webrtc_tests()

        # Specific tests if provided
        if self.specific_tests:
            self._discover_specific_tests()

        logger.info(f"Discovered {self.test_suite.countTestCases()} tests")

        return self.test_suite

    def _discover_unit_tests(self):
        """Discover unit tests."""
        logger.info("Discovering unit tests...")

        # Use test discovery with standard unittest
        pattern = self.test_file_pattern or "test_*.py"
        loader = unittest.TestLoader()

        # Add all tests from test directory
        test_dir = os.path.join(os.path.dirname(__file__), "test")
        if os.path.exists(test_dir):
            tests = loader.discover(test_dir, pattern=pattern)
            self.test_suite.addTests(tests)

    def _discover_integration_tests(self):
        """Discover integration tests."""
        logger.info("Discovering integration tests...")

        # Load integration tests
        integration_dir = os.path.join(os.path.dirname(__file__), "test", "integration")
        if os.path.exists(integration_dir):
            pattern = self.test_file_pattern or "test_*.py"
            loader = unittest.TestLoader()
            tests = loader.discover(integration_dir, pattern=pattern)
            self.test_suite.addTests(tests)

        # Try to load from specific integration test modules
        try:
            from test.integration.run_integration_tests import get_integration_test_suite
            self.test_suite.addTests(get_integration_test_suite())
        except (ImportError, AttributeError):
            pass

    def _discover_network_tests(self):
        """Discover network tests."""
        logger.info("Discovering network tests...")

        try:
            # Load from enhanced MCP discovery test
            from test_discovery.enhanced_mcp_discovery_test import EnhancedMCPDiscoveryTest

            # Determine which network tests to run
            run_all_network_tests = NetworkTestTypes.ALL in self.network_test_types
            tests_to_run = []

            if run_all_network_tests or NetworkTestTypes.PARTITION in self.network_test_types:
                tests_to_run.append("test_network_partition")

            if run_all_network_tests or NetworkTestTypes.PARTIAL_PARTITION in self.network_test_types:
                tests_to_run.append("test_partial_network_partition")

            if run_all_network_tests or NetworkTestTypes.INTERMITTENT in self.network_test_types:
                tests_to_run.append("test_intermittent_connectivity")

            if run_all_network_tests or NetworkTestTypes.TIME_BASED in self.network_test_types:
                tests_to_run.append("test_time_based_recovery")

            if run_all_network_tests or NetworkTestTypes.CASCADING in self.network_test_types:
                tests_to_run.append("test_cascading_failures")

            # Add selected tests to suite
            for test_name in tests_to_run:
                self.test_suite.addTest(EnhancedMCPDiscoveryTest(test_name))

        except ImportError:
            logger.warning("Network tests not found or could not be imported")

    def _discover_storage_tests(self):
        """Discover storage backend tests."""
        logger.info("Discovering storage tests...")

        try:
            # Load storage backend tests
            from test.storage.storage_backend_test import StorageBackendTest

            # Determine which storage tests to run
            run_all_storage_tests = StorageTestTypes.ALL in self.storage_test_types
            tests_to_run = []

            if run_all_storage_tests or StorageTestTypes.LOCAL in self.storage_test_types:
                tests_to_run.append("test_local_storage")

            if run_all_storage_tests or StorageTestTypes.S3 in self.storage_test_types:
                tests_to_run.append("test_s3_storage")

            if run_all_storage_tests or StorageTestTypes.IPFS in self.storage_test_types:
                tests_to_run.append("test_ipfs_storage")

            if run_all_storage_tests or StorageTestTypes.FILECOIN in self.storage_test_types:
                tests_to_run.append("test_filecoin_storage")

            # Add selected tests to suite
            for test_name in tests_to_run:
                self.test_suite.addTest(StorageBackendTest(test_name))

        except ImportError:
            logger.warning("Storage tests not found or could not be imported")

    def _discover_streaming_tests(self):
        """Discover streaming and metrics tests."""
        logger.info("Discovering streaming tests...")

        try:
            # Try to load streaming metrics test
            from test.streaming.streaming_metrics_test import StreamingMetricsTest

            # Add all test methods to suite
            loader = unittest.TestLoader()
            tests = loader.loadTestsFromTestCase(StreamingMetricsTest)
            self.test_suite.addTests(tests)

        except ImportError:
            logger.warning("Streaming tests not found or could not be imported")

    def _discover_webrtc_tests(self):
        """Discover WebRTC tests."""
        logger.info("Discovering WebRTC tests...")

        try:
            # Try to load WebRTC test
            from test.webrtc.webrtc_test import WebRTCTest

            # Add all test methods to suite
            loader = unittest.TestLoader()
            tests = loader.loadTestsFromTestCase(WebRTCTest)
            self.test_suite.addTests(tests)

        except ImportError:
            logger.warning("WebRTC tests not found or could not be imported")

    def _discover_specific_tests(self):
        """Discover specific named tests."""
        logger.info(f"Looking for specific tests: {self.specific_tests}")

        # Load all test modules based on pattern
        loader = unittest.TestLoader()
        test_dir = os.path.join(os.path.dirname(__file__), "test")

        if os.path.exists(test_dir):
            for test_name in self.specific_tests:
                try:
                    # Try to find test by name
                    if "." in test_name:
                        # Format is module.Class.method
                        parts = test_name.split(".")
                        if len(parts) == 3:
                            module_name, class_name, method_name = parts

                            # Import module
                            module = importlib.import_module(module_name)

                            # Get class
                            test_class = getattr(module, class_name)

                            # Add specific test method
                            self.test_suite.addTest(test_class(method_name))
                    else:
                        # Treat as a pattern
                        tests = loader.loadTestsFromName(test_name)
                        self.test_suite.addTests(tests)

                except (ImportError, AttributeError) as e:
                    logger.warning(f"Could not find test: {test_name} - {e}")

    def run_tests(self) -> bool:
        """
        Run the tests.

        Returns:
            bool: True if all tests passed, False otherwise
        """
        logger.info("Running tests...")

        # Print banner with test information
        self._print_banner()

        # Discover tests if not already done
        if self.test_suite.countTestCases() == 0:
            self.discover_tests()

        # Check if we have tests to run
        if self.test_suite.countTestCases() == 0:
            logger.warning("No tests found to run")
            return False

        # Run tests
        if self.parallel:
            try:
                import multiprocessing
                from concurrent.futures import ProcessPoolExecutor

                # Determine number of processes to use
                num_processes = self.num_processes or min(multiprocessing.cpu_count(), 4)

                logger.info(f"Running tests in parallel with {num_processes} processes")

                # For parallel tests, we need a special test runner
                from concurrent.futures import ProcessPoolExecutor

                # Convert test suite to list
                tests = list(iter(self.test_suite))

                # Not ideal, but for simplicity we'll just run each test in a separate process
                with ProcessPoolExecutor(max_workers=num_processes) as executor:
                    # Create a simpler runner for each test
                    runners = []
                    for test in tests:
                        runner = TestRunner(
                            categories=[TestCategories.ALL],
                            verbosity=self.verbosity,
                            log_level=self.log_level,
                            debug=self.debug,
                            config=self.config
                        )
                        suite = unittest.TestSuite()
                        suite.addTest(test)
                        runner.test_suite = suite
                        runners.append(runner)

                    # Run tests in parallel
                    results = list(executor.map(lambda r: r.run_tests(), runners))

                    # All tests passed if all results are True
                    return all(results)

            except (ImportError, Exception) as e:
                logger.error(f"Failed to run tests in parallel: {e}")
                logger.info("Falling back to sequential test execution")
                result = unittest.TextTestRunner(verbosity=self.verbosity).run(self.test_suite)
                return result.wasSuccessful()
        else:
            # Run tests sequentially
            result = unittest.TextTestRunner(verbosity=self.verbosity).run(self.test_suite)
            return result.wasSuccessful()

    def _print_banner(self):
        """Print a banner with test information."""
        categories_str = ", ".join(self.categories)

        network_str = ""
        if TestCategories.NETWORK in self.categories or TestCategories.ALL in self.categories:
            network_str = f"Network Tests: {', '.join(self.network_test_types)}"

        storage_str = ""
        if TestCategories.STORAGE in self.categories or TestCategories.ALL in self.categories:
            storage_str = f"Storage Tests: {', '.join(self.storage_test_types)}"

        banner = f"""
╔══════════════════════════════════════════════════════════════════════════╗
║                       IPFS KIT MCP TEST RUNNER                            ║
╠══════════════════════════════════════════════════════════════════════════╣
║  Categories: {categories_str.ljust(60)} ║
"""

        if network_str:
            banner += f"║  {network_str.ljust(70)} ║\n"

        if storage_str:
            banner += f"║  {storage_str.ljust(70)} ║\n"

        if self.specific_tests:
            specific_str = ", ".join(self.specific_tests)
            banner += f"║  Specific Tests: {specific_str.ljust(56)} ║\n"

        banner += f"║  Verbosity: {str(self.verbosity).ljust(6)}   Parallel: {str(self.parallel).ljust(6)}   Debug: {str(self.debug).ljust(6)}        ║\n"
        banner += "╚══════════════════════════════════════════════════════════════════════════╝"

        print(banner)


def main():
    """Run tests based on command-line arguments."""
    # Create argument parser
    parser = argparse.ArgumentParser(
        description="Consolidated MCP Test Runner",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    # Test categories
    category_group = parser.add_argument_group("Test Categories")
    category_group.add_argument("--unit", action="store_true", help="Run unit tests")
    category_group.add_argument("--integration", action="store_true", help="Run integration tests")
    category_group.add_argument("--network", action="store_true", help="Run network tests")
    category_group.add_argument("--storage", action="store_true", help="Run storage tests")
    category_group.add_argument("--streaming", action="store_true", help="Run streaming tests")
    category_group.add_argument("--webrtc", action="store_true", help="Run WebRTC tests")
    category_group.add_argument("--all", action="store_true", help="Run all tests")

    # Network test types
    network_group = parser.add_argument_group("Network Test Types")
    network_group.add_argument("--partition", action="store_true", help="Run partition tests")
    network_group.add_argument("--partial-partition", action="store_true", help="Run partial partition tests")
    network_group.add_argument("--intermittent", action="store_true", help="Run intermittent connectivity tests")
    network_group.add_argument("--time-based", action="store_true", help="Run time-based recovery tests")
    network_group.add_argument("--cascading", action="store_true", help="Run cascading failures tests")
    network_group.add_argument("--all-network", action="store_true", help="Run all network tests")

    # Storage test types
    storage_group = parser.add_argument_group("Storage Test Types")
    storage_group.add_argument("--local-storage", action="store_true", help="Run local storage tests")
    storage_group.add_argument("--s3-storage", action="store_true", help="Run S3 storage tests")
    storage_group.add_argument("--ipfs-storage", action="store_true", help="Run IPFS storage tests")
    storage_group.add_argument("--filecoin-storage", action="store_true", help="Run Filecoin storage tests")
    storage_group.add_argument("--all-storage", action="store_true", help="Run all storage tests")

    # Test configuration
    config_group = parser.add_argument_group("Test Configuration")
    config_group.add_argument("--verbosity", "-v", type=int, default=2, choices=[0, 1, 2, 3],
                       help="Verbosity level (0-3)")
    config_group.add_argument("--log-level", default="INFO",
                       choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                       help="Logging level")
    config_group.add_argument("--pattern", help="Test file pattern")
    config_group.add_argument("--test", action="append", dest="tests",
                       help="Specific test to run (can be specified multiple times)")
    config_group.add_argument("--parallel", action="store_true", help="Run tests in parallel")
    config_group.add_argument("--processes", type=int, help="Number of processes for parallel tests")
    config_group.add_argument("--timeout", type=int, default=300, help="Test timeout in seconds")
    config_group.add_argument("--debug", action="store_true", help="Enable debug mode")
    config_group.add_argument("--config", help="Path to JSON configuration file")

    # Parse arguments
    # Only parse args when running the script directly, not when imported by pytest
    if __name__ == "__main__":
        args = parser.parse_args()
    else:
        # When run under pytest, use default values
        args = parser.parse_args([])

    # Determine which test categories to run
    categories = []
    if args.unit:
        categories.append(TestCategories.UNIT)
    if args.integration:
        categories.append(TestCategories.INTEGRATION)
    if args.network:
        categories.append(TestCategories.NETWORK)
    if args.storage:
        categories.append(TestCategories.STORAGE)
    if args.streaming:
        categories.append(TestCategories.STREAMING)
    if args.webrtc:
        categories.append(TestCategories.WEBRTC)
    if args.all or not categories:
        # Default to all if nothing specified
        categories = [TestCategories.ALL]

    # Determine which network tests to run
    network_test_types = []
    if args.partition:
        network_test_types.append(NetworkTestTypes.PARTITION)
    if args.partial_partition:
        network_test_types.append(NetworkTestTypes.PARTIAL_PARTITION)
    if args.intermittent:
        network_test_types.append(NetworkTestTypes.INTERMITTENT)
    if args.time_based:
        network_test_types.append(NetworkTestTypes.TIME_BASED)
    if args.cascading:
        network_test_types.append(NetworkTestTypes.CASCADING)
    if args.all_network or not network_test_types:
        # Default to all if network tests requested but no specific types
        network_test_types = [NetworkTestTypes.ALL]

    # Determine which storage tests to run
    storage_test_types = []
    if args.local_storage:
        storage_test_types.append(StorageTestTypes.LOCAL)
    if args.s3_storage:
        storage_test_types.append(StorageTestTypes.S3)
    if args.ipfs_storage:
        storage_test_types.append(StorageTestTypes.IPFS)
    if args.filecoin_storage:
        storage_test_types.append(StorageTestTypes.FILECOIN)
    if args.all_storage or not storage_test_types:
        # Default to all if storage tests requested but no specific types
        storage_test_types = [StorageTestTypes.ALL]

    # Load configuration from file if specified
    config = {}
    if args.config and os.path.exists(args.config):
        import json
        try:
            with open(args.config, 'r') as f:
                config = json.load(f)
                logger.info(f"Loaded configuration from {args.config}")
        except Exception as e:
            logger.error(f"Failed to load configuration from {args.config}: {e}")
            return 1

    # Create and run test runner
    runner = TestRunner(
        categories=categories,
        verbosity=args.verbosity,
        log_level=args.log_level,
        network_test_types=network_test_types,
        storage_test_types=storage_test_types,
        test_file_pattern=args.pattern,
        specific_tests=args.tests,
        parallel=args.parallel,
        num_processes=args.processes,
        timeout=args.timeout,
        debug=args.debug,
        config=config
    )

    # Run tests
    success = runner.run_tests()

    # Exit with appropriate status code
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
