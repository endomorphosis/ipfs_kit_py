#!/usr/bin/env python3
"""
Unified Test Runner for IPFS Kit

This file consolidates functionality from:
- run_all_tests.py
- run_direct_tests.py
- run_mcp_tests.py
- run_tests.py
- run_tests_with_fixes.py
- run_s3_test.py
- run_storage_backend_tests.py
- start_and_test_anyio_server.py
- start_test_mcp_server.py

It provides a comprehensive test runner with support for different
test categories, configurations, and reporting.
"""

import os
import sys
import time
import json
import shutil
import logging
import argparse
import unittest
import subprocess
import traceback
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple, Set

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)-8s] [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("test_runner")

# Try to import pytest
try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False
    logger.warning("pytest not found, some test features will be disabled")

# Try to import server runner for integrated testing
try:
    from server_runner import ServerRunner
    HAS_SERVER_RUNNER = True
except ImportError:
    HAS_SERVER_RUNNER = False
    logger.warning("server_runner not found, integrated server testing will be disabled")

# Try to import daemon manager for integrated testing
try:
    from daemon_manager import DaemonManager
    HAS_DAEMON_MANAGER = True
except ImportError:
    HAS_DAEMON_MANAGER = False
    logger.warning("daemon_manager not found, integrated daemon testing will be disabled")

class TestRunner:
    """Unified test runner for IPFS Kit."""
    
    # Test categories
    TEST_CATEGORIES = {
        "unit": "Unit tests",
        "integration": "Integration tests",
        "storage": "Storage backend tests",
        "network": "Network simulation tests",
        "mcp": "MCP server tests",
        "ipfs": "IPFS daemon tests",
        "s3": "S3 backend tests",
        "filecoin": "Filecoin tests",
        "webrtc": "WebRTC tests",
        "stress": "Stress tests"
    }
    
    def __init__(
        self,
        categories: Optional[List[str]] = None,
        test_dir: str = "test",
        output_dir: Optional[str] = None,
        timeout: int = 300,
        junit_xml: bool = False,
        coverage: bool = False,
        verbose: bool = False,
        quiet: bool = False,
        config: Optional[Dict[str, Any]] = None,
        start_server: bool = False,
        server_config: Optional[Dict[str, Any]] = None,
        start_daemons: bool = False,
        daemon_config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the test runner.
        
        Args:
            categories: Test categories to run
            test_dir: Directory containing tests
            output_dir: Directory for test output
            timeout: Test timeout in seconds
            junit_xml: Generate JUnit XML report
            coverage: Generate coverage report
            verbose: Enable verbose output
            quiet: Suppress output
            config: Test configuration
            start_server: Start MCP server for testing
            server_config: Server configuration
            start_daemons: Start daemons for testing
            daemon_config: Daemon configuration
        """
        self.categories = categories or list(self.TEST_CATEGORIES.keys())
        self.test_dir = os.path.abspath(test_dir)
        self.output_dir = output_dir
        self.timeout = timeout
        self.junit_xml = junit_xml
        self.coverage = coverage
        self.verbose = verbose
        self.quiet = quiet
        self.config = config or {}
        self.start_server = start_server
        self.server_config = server_config or {}
        self.start_daemons = start_daemons
        self.daemon_config = daemon_config or {}
        
        # Validate test categories
        for category in self.categories:
            if category not in self.TEST_CATEGORIES:
                raise ValueError(f"Unknown test category: {category}")
        
        # Validate and create output directory
        if self.output_dir:
            os.makedirs(self.output_dir, exist_ok=True)
        
        # Server and daemon managers
        self.server_runner = None
        self.daemon_manager = None
        
        # Test results
        self.results = {}
        
        logger.info(f"Initialized test runner for categories: {', '.join(self.categories)}")
    
    def setup(self) -> bool:
        """
        Set up the test environment.
        
        Returns:
            bool: True if setup was successful, False otherwise
        """
        logger.info("Setting up test environment")
        
        # Start daemons if requested
        if self.start_daemons:
            if not self._start_daemons():
                return False
        
        # Start server if requested
        if self.start_server:
            if not self._start_server():
                return False
        
        return True
    
    def _start_daemons(self) -> bool:
        """
        Start daemons for testing.
        
        Returns:
            bool: True if daemons started successfully, False otherwise
        """
        if not HAS_DAEMON_MANAGER:
            logger.error("Cannot start daemons: daemon_manager module not found")
            return False
            
        logger.info("Starting daemons for testing")
        
        try:
            # Get daemons to start
            daemons = self.daemon_config.get("daemons", ["ipfs"])
            
            # Create daemon manager
            self.daemon_manager = DaemonManager(
                daemon_types=daemons,
                config=self.daemon_config,
                enable_monitoring=True,
                auto_restart=True
            )
            
            # Start daemons
            if not self.daemon_manager.start_all():
                logger.error("Failed to start daemons")
                return False
                
            logger.info(f"Started daemons: {', '.join(daemons)}")
            return True
            
        except Exception as e:
            logger.error(f"Error starting daemons: {e}")
            logger.error(traceback.format_exc())
            return False
    
    def _start_server(self) -> bool:
        """
        Start MCP server for testing.
        
        Returns:
            bool: True if server started successfully, False otherwise
        """
        if not HAS_SERVER_RUNNER:
            logger.error("Cannot start server: server_runner module not found")
            return False
            
        logger.info("Starting MCP server for testing")
        
        try:
            # Get server configuration
            server_type = self.server_config.get("server_type", "anyio")
            port = self.server_config.get("port", 9999)
            
            # Start server in a separate process
            cmd = [
                sys.executable, 
                os.path.join(os.path.dirname(__file__), "server_runner.py"),
                f"--server-type={server_type}",
                f"--port={port}",
                "--debug"
            ]
            
            if self.server_config.get("isolation", True):
                cmd.append("--isolation")
                
            logger.info(f"Starting server with command: {' '.join(cmd)}")
            
            # Start process in background
            with open(os.devnull, 'w') as devnull:
                server_process = subprocess.Popen(
                    cmd,
                    stdout=devnull if self.quiet else None,
                    stderr=subprocess.STDOUT
                )
            
            # Wait for server to start
            time.sleep(2)
            
            # Check if still running
            if server_process.poll() is None:
                logger.info(f"Server started successfully on port {port}")
                
                # Set environment variable for tests
                os.environ["MCP_SERVER_PORT"] = str(port)
                return True
            else:
                logger.error(f"Server failed to start (exit code: {server_process.returncode})")
                return False
                
        except Exception as e:
            logger.error(f"Error starting server: {e}")
            logger.error(traceback.format_exc())
            return False
    
    def discover_tests(self) -> Dict[str, List[str]]:
        """
        Discover tests in each category.
        
        Returns:
            Dict mapping category to list of test files
        """
        logger.info("Discovering tests")
        discovered_tests = {}
        
        for category in self.categories:
            category_dir = os.path.join(self.test_dir, category)
            
            if os.path.isdir(category_dir):
                # Find all test files in category directory
                test_files = []
                
                for root, _, files in os.walk(category_dir):
                    for file in files:
                        if file.startswith("test_") and file.endswith(".py"):
                            test_files.append(os.path.join(root, file))
                
                discovered_tests[category] = sorted(test_files)
                logger.info(f"Discovered {len(test_files)} tests in category '{category}'")
            else:
                logger.warning(f"Test directory not found for category '{category}': {category_dir}")
                discovered_tests[category] = []
        
        return discovered_tests
    
    def run_tests(self) -> bool:
        """
        Run all tests in specified categories.
        
        Returns:
            bool: True if all tests passed, False otherwise
        """
        start_time = time.time()
        logger.info(f"Running tests in categories: {', '.join(self.categories)}")
        
        # Discover tests
        discovered_tests = self.discover_tests()
        
        # Track results
        all_passed = True
        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        skipped_tests = 0
        
        # Run tests for each category
        for category, test_files in discovered_tests.items():
            if not test_files:
                continue
                
            logger.info(f"Running tests in category: {category} ({len(test_files)} files)")
            
            # Run tests in this category
            if self.coverage:
                category_result = self._run_tests_with_coverage(category, test_files)
            else:
                category_result = self._run_tests_with_pytest(category, test_files)
            
            # Update overall results
            self.results[category] = category_result
            
            # Update totals
            total_tests += category_result.get("total", 0)
            passed_tests += category_result.get("passed", 0)
            failed_tests += category_result.get("failed", 0)
            skipped_tests += category_result.get("skipped", 0)
            
            # Update overall status
            if not category_result.get("success", False):
                all_passed = False
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Print summary
        self._print_summary(total_tests, passed_tests, failed_tests, skipped_tests, duration)
        
        return all_passed
    
    def _run_tests_with_pytest(self, category: str, test_files: List[str]) -> Dict[str, Any]:
        """
        Run tests using pytest.
        
        Args:
            category: Test category
            test_files: List of test files
            
        Returns:
            Dict with test results
        """
        if not HAS_PYTEST:
            return self._run_tests_with_unittest(category, test_files)
            
        result = {
            "category": category,
            "success": False,
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "duration": 0,
            "files": len(test_files)
        }
        
        try:
            # Prepare pytest arguments
            pytest_args = []
            
            # Add verbosity
            if self.verbose:
                pytest_args.append("-v")
            elif self.quiet:
                pytest_args.append("-q")
            
            # Add JUnit XML output
            if self.junit_xml and self.output_dir:
                xml_path = os.path.join(self.output_dir, f"{category}_results.xml")
                pytest_args.extend(["--junitxml", xml_path])
            
            # Add test files
            pytest_args.extend(test_files)
            
            # Run pytest
            start_time = time.time()
            logger.info(f"Running pytest with args: {' '.join(pytest_args)}")
            
            # We use pytest.main() to run tests
            exit_code = pytest.main(pytest_args)
            
            # Calculate duration
            result["duration"] = time.time() - start_time
            
            # Interpret result
            result["success"] = exit_code == 0
            
            # Try to get more detailed information if available
            if hasattr(pytest, "_pytest") and hasattr(pytest._pytest, "config"):
                if hasattr(pytest._pytest.config, "get_report_status"):
                    stats = pytest._pytest.config.get_report_status()
                    if stats:
                        result["total"] = sum(stats.values())
                        result["passed"] = stats.get("passed", 0)
                        result["failed"] = stats.get("failed", 0)
                        result["skipped"] = stats.get("skipped", 0)
            
            logger.info(f"Category '{category}' completed with status: {'PASSED' if result['success'] else 'FAILED'}")
            return result
            
        except Exception as e:
            logger.error(f"Error running tests for category '{category}': {e}")
            logger.error(traceback.format_exc())
            result["error"] = str(e)
            return result
    
    def _run_tests_with_coverage(self, category: str, test_files: List[str]) -> Dict[str, Any]:
        """
        Run tests with coverage.
        
        Args:
            category: Test category
            test_files: List of test files
            
        Returns:
            Dict with test results
        """
        # Try to import coverage
        try:
            import coverage
            from coverage.report import get_analysis_to_report
        except ImportError:
            logger.warning("coverage module not found, running without coverage")
            return self._run_tests_with_pytest(category, test_files)
        
        result = {
            "category": category,
            "success": False,
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "duration": 0,
            "files": len(test_files),
            "coverage": 0.0
        }
        
        try:
            # Create coverage object
            cov = coverage.Coverage(
                source=["ipfs_kit_py"],
                omit=["*/test/*", "*/venv/*", "*/build_venv/*", "*/test_venv/*"]
            )
            
            # Start coverage
            cov.start()
            
            # Run tests
            if HAS_PYTEST:
                pytest_result = self._run_tests_with_pytest(category, test_files)
                result.update(pytest_result)
            else:
                unittest_result = self._run_tests_with_unittest(category, test_files)
                result.update(unittest_result)
            
            # Stop coverage
            cov.stop()
            
            # Generate reports
            if self.output_dir:
                # HTML report
                html_dir = os.path.join(self.output_dir, f"{category}_coverage")
                cov.html_report(directory=html_dir)
                
                # XML report
                xml_path = os.path.join(self.output_dir, f"{category}_coverage.xml")
                cov.xml_report(outfile=xml_path)
            
            # Calculate overall coverage
            cov.save()
            
            # Get total coverage percentage
            data = cov.get_data()
            if hasattr(data, 'lines_covered'):
                lines_covered = data.lines_covered()
                lines_total = data.lines_total()
                if lines_total > 0:
                    result["coverage"] = 100 * lines_covered / lines_total
            
            return result
            
        except Exception as e:
            logger.error(f"Error running tests with coverage for category '{category}': {e}")
            logger.error(traceback.format_exc())
            result["error"] = str(e)
            return result
    
    def _run_tests_with_unittest(self, category: str, test_files: List[str]) -> Dict[str, Any]:
        """
        Run tests using unittest.
        
        Args:
            category: Test category
            test_files: List of test files
            
        Returns:
            Dict with test results
        """
        result = {
            "category": category,
            "success": False,
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "duration": 0,
            "files": len(test_files)
        }
        
        try:
            # Create test suite
            suite = unittest.TestSuite()
            
            # Add tests from files
            for test_file in test_files:
                # Convert file path to module name
                # e.g., test/unit/test_storage.py -> test.unit.test_storage
                rel_path = os.path.relpath(test_file, os.path.dirname(self.test_dir))
                module_name = os.path.splitext(rel_path)[0].replace(os.path.sep, '.')
                
                try:
                    # Import module
                    __import__(module_name)
                    module = sys.modules[module_name]
                    
                    # Add all tests in module
                    for name in dir(module):
                        obj = getattr(module, name)
                        if isinstance(obj, type) and issubclass(obj, unittest.TestCase):
                            suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(obj))
                            
                except (ImportError, AttributeError) as e:
                    logger.error(f"Error loading tests from {test_file}: {e}")
            
            # Run tests
            start_time = time.time()
            runner = unittest.TextTestRunner(
                verbosity=2 if self.verbose else 1,
                stream=open(os.devnull, 'w') if self.quiet else sys.stdout
            )
            test_result = runner.run(suite)
            
            # Calculate duration
            result["duration"] = time.time() - start_time
            
            # Interpret result
            result["success"] = test_result.wasSuccessful()
            result["total"] = test_result.testsRun
            result["failed"] = len(test_result.failures) + len(test_result.errors)
            result["passed"] = test_result.testsRun - result["failed"] - len(test_result.skipped)
            result["skipped"] = len(test_result.skipped)
            
            logger.info(f"Category '{category}' completed with status: {'PASSED' if result['success'] else 'FAILED'}")
            return result
            
        except Exception as e:
            logger.error(f"Error running tests for category '{category}': {e}")
            logger.error(traceback.format_exc())
            result["error"] = str(e)
            return result
    
    def _print_summary(self, total: int, passed: int, failed: int, skipped: int, duration: float):
        """Print test summary."""
        print("\n" + "=" * 70)
        print("TEST SUMMARY".center(70))
        print("=" * 70)
        
        # Print category results
        for category, result in self.results.items():
            status = "PASSED" if result.get("success", False) else "FAILED"
            coverage = f" (Coverage: {result.get('coverage', 0):.1f}%)" if "coverage" in result else ""
            print(f"{category}: {status}{coverage}")
            print(f"  Total: {result.get('total', 0)}, "
                  f"Passed: {result.get('passed', 0)}, "
                  f"Failed: {result.get('failed', 0)}, "
                  f"Skipped: {result.get('skipped', 0)}")
            print(f"  Duration: {result.get('duration', 0):.2f}s")
            
            if "error" in result:
                print(f"  Error: {result['error']}")
                
            print()
        
        # Print overall summary
        print("-" * 70)
        print(f"OVERALL: {'PASSED' if failed == 0 else 'FAILED'}")
        print(f"Total: {total}, Passed: {passed}, Failed: {failed}, Skipped: {skipped}")
        
        # Calculate pass rate
        if total > 0:
            pass_rate = 100 * passed / total
            print(f"Pass Rate: {pass_rate:.1f}%")
            
        print(f"Total Duration: {duration:.2f}s")
        print("=" * 70 + "\n")
    
    def cleanup(self):
        """Clean up resources."""
        logger.info("Cleaning up resources")
        
        # Stop server if started
        if self.server_runner:
            logger.info("Stopping MCP server")
            self.server_runner = None
        
        # Stop daemons if started
        if self.daemon_manager:
            logger.info("Stopping daemons")
            self.daemon_manager.stop_all()
            self.daemon_manager = None

def main():
    """Run tests from command line."""
    # Create argument parser
    parser = argparse.ArgumentParser(
        description="Unified Test Runner for IPFS Kit",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Test selection
    parser.add_argument("--categories", nargs="+", choices=list(TestRunner.TEST_CATEGORIES.keys()),
                    help="Test categories to run")
    parser.add_argument("--list-categories", action="store_true",
                    help="List available test categories and exit")
    
    # Test options
    parser.add_argument("--test-dir", default="test",
                    help="Directory containing tests")
    parser.add_argument("--output-dir", help="Directory for test output")
    parser.add_argument("--timeout", type=int, default=300,
                    help="Test timeout in seconds")
    parser.add_argument("--junit-xml", action="store_true",
                    help="Generate JUnit XML report")
    parser.add_argument("--coverage", action="store_true",
                    help="Generate coverage report")
    parser.add_argument("--verbose", action="store_true",
                    help="Enable verbose output")
    parser.add_argument("--quiet", action="store_true",
                    help="Suppress output")
    
    # Server options
    parser.add_argument("--start-server", action="store_true",
                    help="Start MCP server for testing")
    parser.add_argument("--server-type", choices=["sync", "anyio", "real", "storage"],
                    default="anyio", help="Server type to start")
    parser.add_argument("--server-port", type=int, default=9999,
                    help="Port for the test server")
    
    # Daemon options
    parser.add_argument("--start-daemons", action="store_true",
                    help="Start daemons for testing")
    parser.add_argument("--daemons", nargs="+", default=["ipfs"],
                    help="Daemons to start for testing")
    
    # Parse arguments
    args = parser.parse_args()
    
    # List categories if requested
    if args.list_categories:
        print("\nAvailable Test Categories:")
        print("=" * 50)
        for category, description in TestRunner.TEST_CATEGORIES.items():
            print(f"{category}: {description}")
        print()
        return 0
    
    # Configure output directory
    output_dir = args.output_dir
    if not output_dir and (args.junit_xml or args.coverage):
        output_dir = os.path.join(os.getcwd(), "test_results")
        os.makedirs(output_dir, exist_ok=True)
    
    # Create server configuration
    server_config = {
        "server_type": args.server_type,
        "port": args.server_port,
        "isolation": True
    }
    
    # Create daemon configuration
    daemon_config = {
        "daemons": args.daemons
    }
    
    # Create test runner
    runner = TestRunner(
        categories=args.categories,
        test_dir=args.test_dir,
        output_dir=output_dir,
        timeout=args.timeout,
        junit_xml=args.junit_xml,
        coverage=args.coverage,
        verbose=args.verbose,
        quiet=args.quiet,
        start_server=args.start_server,
        server_config=server_config,
        start_daemons=args.start_daemons,
        daemon_config=daemon_config
    )
    
    try:
        # Set up environment
        if not runner.setup():
            logger.error("Failed to set up test environment")
            return 1
        
        # Run tests
        success = runner.run_tests()
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Error: {e}")
        logger.error(traceback.format_exc())
        return 1
    finally:
        # Clean up resources
        runner.cleanup()

if __name__ == "__main__":
    sys.exit(main())