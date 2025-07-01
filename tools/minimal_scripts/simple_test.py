#!/usr/bin/env python3
"""
Simple test runner for IPFS Kit Python.

This test runner discovers and runs tests without depending on pytest internals,
making it compatible with Python 3.12.
"""

import os
import sys
import time
import importlib
import inspect
import traceback
import logging
import argparse
from pathlib import Path
from typing import List, Dict, Any, Callable, Optional, Union, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)8s] %(name)s: %(message)s'
)
logger = logging.getLogger("simple_test_runner")

# Colors for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"

# Global test statistics
stats = {
    "total": 0,
    "passed": 0,
    "failed": 0,
    "skipped": 0,
    "error": 0,
    "start_time": 0,
    "end_time": 0,
}

class TestResult:
    """Represents the result of running a test."""
    
    def __init__(self, name, module_name, file_path):
        self.name = name
        self.module_name = module_name
        self.file_path = file_path
        self.status = "unknown"
        self.duration = 0.0
        self.error = None
        self.traceback = None
        
    def __str__(self):
        return f"{self.module_name}.{self.name}"
        
    def short_status(self):
        """Get a color-coded short status string."""
        if self.status == "passed":
            return f"{GREEN}PASS{RESET}"
        elif self.status == "failed":
            return f"{RED}FAIL{RESET}"
        elif self.status == "skipped":
            return f"{YELLOW}SKIP{RESET}"
        elif self.status == "error":
            return f"{RED}ERROR{RESET}"
        else:
            return self.status

def is_test_function(name, obj):
    """Check if an object is a test function."""
    return (
        callable(obj) and
        (name.startswith('test_') or name.endswith('_test')) and
        not name.startswith('_')
    )

def is_test_class(name, obj):
    """Check if an object is a test class."""
    return (
        inspect.isclass(obj) and
        (name.startswith('Test') or name.endswith('Test')) and
        not name.startswith('_')
    )

def discover_tests_in_module(module, module_file):
    """Discover test functions and methods in a module."""
    test_functions = []
    
    # Find test functions directly in the module
    for name, obj in inspect.getmembers(module):
        if is_test_function(name, obj):
            test_functions.append({
                "name": name,
                "function": obj,
                "module": module.__name__,
                "file": module_file,
                "class": None
            })
    
    # Find test methods in test classes
    for name, obj in inspect.getmembers(module):
        if is_test_class(name, obj):
            for method_name, method_obj in inspect.getmembers(obj):
                if is_test_function(method_name, method_obj):
                    # Create an instance of the class for the test method
                    instance = obj()
                    bound_method = getattr(instance, method_name)
                    
                    test_functions.append({
                        "name": f"{name}.{method_name}",
                        "function": bound_method,
                        "module": module.__name__,
                        "file": module_file,
                        "class": name
                    })
    
    return test_functions

def discover_tests(test_path, pattern="test_*.py"):
    """Discover test modules and functions in a directory or file."""
    test_path = Path(test_path)
    test_functions = []
    
    if test_path.is_file():
        # Single test file
        if test_path.name.startswith("test_") or test_path.name.endswith("_test.py"):
            try:
                # Convert file path to module path
                module_name = str(test_path.with_suffix("")).replace(os.sep, ".")
                module_name = module_name.lstrip(".")
                
                # Import the module
                spec = importlib.util.spec_from_file_location(module_name, test_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Find test functions in the module
                module_tests = discover_tests_in_module(module, test_path)
                test_functions.extend(module_tests)
            except Exception as e:
                logger.error(f"Error importing {test_path}: {e}")
                traceback.print_exc()
    else:
        # Directory - walk and find test files
        for root, _, files in os.walk(test_path):
            for filename in files:
                if filename.startswith("test_") and filename.endswith(".py"):
                    file_path = Path(root) / filename
                    
                    try:
                        # Convert file path to module path
                        module_path = file_path.relative_to(Path.cwd())
                        module_name = str(module_path.with_suffix("")).replace(os.sep, ".")
                        
                        # Import the module
                        spec = importlib.util.spec_from_file_location(module_name, file_path)
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        
                        # Find test functions in the module
                        module_tests = discover_tests_in_module(module, file_path)
                        test_functions.extend(module_tests)
                    except Exception as e:
                        logger.error(f"Error importing {file_path}: {e}")
    
    return test_functions

def run_test(test_info):
    """Run a single test and return the result."""
    test_name = test_info["name"]
    test_func = test_info["function"]
    module_name = test_info["module"]
    file_path = test_info["file"]
    
    result = TestResult(test_name, module_name, file_path)
    
    # Run the test
    start_time = time.time()
    try:
        # Check if it's an async function
        if inspect.iscoroutinefunction(test_func):
            import asyncio
            asyncio.run(test_func())
        else:
            test_func()
        
        # If we got here, the test passed
        result.status = "passed"
        stats["passed"] += 1
    except Exception as e:
        # Check for skips (common pytest patterns)
        if (
            "pytest.skip" in str(e) or 
            "SkipTest" in str(e) or
            "skipTest" in str(e) or
            "unittest.case.SkipTest" in str(e)
        ):
            result.status = "skipped"
            result.error = str(e)
            stats["skipped"] += 1
        else:
            # Regular test failure
            result.status = "failed"
            result.error = str(e)
            result.traceback = traceback.format_exc()
            stats["failed"] += 1
    finally:
        end_time = time.time()
        result.duration = end_time - start_time
    
    return result

def run_all_tests(test_functions, verbose=False):
    """Run all discovered tests and return results."""
    results = []
    
    # Update stats
    stats["total"] = len(test_functions)
    stats["start_time"] = time.time()
    
    # Print header
    print(f"\n{BOLD}Running {len(test_functions)} tests{RESET}\n")
    
    # Run each test
    for i, test_info in enumerate(test_functions):
        test_name = test_info["name"]
        module_name = test_info["module"]
        
        # Print test info
        if verbose:
            print(f"[{i+1}/{len(test_functions)}] {module_name}.{test_name}")
        else:
            # Simple progress indicator
            sys.stdout.write(f"\r[{i+1}/{len(test_functions)}] Running tests...")
            sys.stdout.flush()
        
        # Run the test
        result = run_test(test_info)
        results.append(result)
        
        # Print detailed result in verbose mode
        if verbose:
            print(f"  {result.short_status()} ({result.duration:.3f}s)")
            if result.error:
                print(f"  {RED}Error: {result.error}{RESET}")
            if result.traceback and verbose > 1:
                print(f"  {YELLOW}Traceback:{RESET}\n{result.traceback}")
    
    # Clear progress line
    if not verbose:
        sys.stdout.write("\r" + " " * 80 + "\r")
        
    # Update end time
    stats["end_time"] = time.time()
    
    return results

def print_summary(results):
    """Print a summary of test results."""
    duration = stats["end_time"] - stats["start_time"]
    
    # Calculate success rate
    success_rate = 0
    if stats["total"] > 0:
        success_rate = (stats["passed"] / stats["total"]) * 100
    
    # Print separator
    print("\n" + "=" * 70)
    
    # Print summary header
    print(f"{BOLD}TEST SUMMARY ({duration:.2f}s){RESET}")
    print("=" * 70)
    
    # Print statistics
    print(f"Total:   {stats['total']}")
    print(f"Passed:  {GREEN}{stats['passed']}{RESET}")
    if stats['failed'] > 0:
        print(f"Failed:  {RED}{stats['failed']}{RESET}")
    else:
        print(f"Failed:  {stats['failed']}")
    if stats['skipped'] > 0:
        print(f"Skipped: {YELLOW}{stats['skipped']}{RESET}")
    else:
        print(f"Skipped: {stats['skipped']}")
    if stats['error'] > 0:
        print(f"Error:   {RED}{stats['error']}{RESET}")
    else:
        print(f"Error:   {stats['error']}")
    
    # Print success rate
    if success_rate == 100:
        print(f"\nSuccess rate: {GREEN}{success_rate:.1f}%{RESET}")
    elif success_rate >= 80:
        print(f"\nSuccess rate: {YELLOW}{success_rate:.1f}%{RESET}")
    else:
        print(f"\nSuccess rate: {RED}{success_rate:.1f}%{RESET}")
    
    # Print separator
    print("=" * 70)
    
    # Print failed tests if any
    failed_results = [r for r in results if r.status == "failed"]
    if failed_results:
        print(f"\n{BOLD}FAILED TESTS:{RESET}")
        for result in failed_results:
            print(f"  {RED}{result}{RESET}")
            if result.error:
                print(f"    Error: {result.error}")
        print("")

def main():
    """Main function to run the test runner."""
    parser = argparse.ArgumentParser(description="Simple Test Runner for IPFS Kit Python")
    parser.add_argument("test_path", nargs="?", default="test", help="Directory or file containing tests")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase verbosity (can use multiple times)")
    parser.add_argument("-k", "--keyword", help="Only run tests matching the keyword")
    
    args = parser.parse_args()
    
    # Add project root to sys.path
    sys.path.insert(0, os.path.abspath("."))
    
    # Import our fix to add LOTUS_KIT_AVAILABLE
    try:
        import ipfs_test_fix
        logger.info("Successfully loaded test fixes")
    except ImportError:
        try:
            # Try to import LOTUS_KIT_AVAILABLE and add it if missing
            import ipfs_kit_py.lotus_kit
            if not hasattr(ipfs_kit_py.lotus_kit, 'LOTUS_KIT_AVAILABLE'):
                ipfs_kit_py.lotus_kit.LOTUS_KIT_AVAILABLE = True
                logger.info("Added LOTUS_KIT_AVAILABLE=True to lotus_kit module")
        except ImportError:
            logger.warning("Could not import ipfs_kit_py.lotus_kit")
    
    # Discover tests
    logger.info(f"Discovering tests in {args.test_path}")
    test_functions = discover_tests(args.test_path)
    
    # Filter by keyword if provided
    if args.keyword:
        logger.info(f"Filtering tests by keyword: {args.keyword}")
        filtered_tests = [t for t in test_functions 
                          if args.keyword.lower() in t["name"].lower() or
                             args.keyword.lower() in t["module"].lower()]
        
        # Print matching tests in verbose mode
        if args.verbose and filtered_tests:
            print("\nMatching tests:")
            for test in filtered_tests:
                print(f"  {test['module']}.{test['name']}")
            print("")
        
        # Update test list
        test_functions = filtered_tests
        logger.info(f"Found {len(test_functions)} tests matching keyword")
    
    # Check if we found any tests
    if not test_functions:
        logger.error("No tests found!")
        return 1
    
    # Run the tests
    results = run_all_tests(test_functions, verbose=args.verbose)
    
    # Print results summary
    print_summary(results)
    
    # Return exit code based on test results
    if stats["failed"] > 0 or stats["error"] > 0:
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())