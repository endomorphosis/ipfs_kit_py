#!/usr/bin/env python3
"""
Direct test runner for IPFS Kit Python.

This script bypasses pytest's normal initialization to avoid the terminal writer issues.
"""

import os
import sys
import unittest
import pytest
import importlib
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

def run_tests():
    """Run tests directly using pytest's collection and unittest's test runner."""
    # First import our pytest fixes
    try:
        import pytest_fix_complete
        print("Successfully applied complete pytest fixes")
    except ImportError as e:
        print(f"Error importing pytest_fix_complete: {e}")
    
    # Set environment variables for testing
    os.environ["IPFS_KIT_TESTING"] = "1"
    
    # Discover tests using pytest's collector
    collected_tests = []
    test_path = Path(project_root) / "test"
    
    # Look for test files directly
    test_files = []
    for root, _, files in os.walk(test_path):
        for file in files:
            if file.startswith("test_") and file.endswith(".py"):
                test_files.append(os.path.join(root, file))
    
    print(f"Found {len(test_files)} test files")
    
    # Create a unittest suite to run the tests
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    
    # Track test results
    results = {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
        "failures": []
    }
    
    # Run each test file individually to isolate failures
    for test_file in test_files:
        rel_path = os.path.relpath(test_file, project_root)
        print(f"\nRunning tests from {rel_path}")
        
        # Convert path to module name
        module_name = os.path.splitext(rel_path)[0].replace(os.path.sep, ".")
        
        try:
            # Try to import the module
            module = importlib.import_module(module_name)
            
            # Try to load tests from the module
            try:
                tests = loader.loadTestsFromModule(module)
                if tests.countTestCases() > 0:
                    # Run the tests
                    runner = unittest.TextTestRunner(verbosity=2)
                    result = runner.run(tests)
                    
                    # Update results
                    results["total"] += result.testsRun
                    results["passed"] += result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped)
                    results["failed"] += len(result.failures)
                    results["errors"] += len(result.errors)
                    results["skipped"] += len(getattr(result, 'skipped', []))
                    
                    # Record failures
                    for test, traceback in result.failures:
                        results["failures"].append((module_name, str(test), traceback))
                    for test, traceback in result.errors:
                        results["failures"].append((module_name, str(test), traceback))
                else:
                    print(f"No tests found in {module_name}")
            except Exception as e:
                print(f"Error loading tests from {module_name}: {e}")
                results["errors"] += 1
                results["failures"].append((module_name, "module_load", str(e)))
        except Exception as e:
            print(f"Error importing {module_name}: {e}")
            results["errors"] += 1
            results["failures"].append((module_name, "import", str(e)))
    
    # Print summary
    print("\n" + "=" * 70)
    print(f"SUMMARY: {results['passed']} passed, {results['failed']} failed, "
          f"{results['errors']} errors, {results['skipped']} skipped "
          f"(total: {results['total']})")
    
    # Print failures
    if results["failures"]:
        print("\nFAILURES:")
        for module, test, traceback in results["failures"]:
            print(f"\n{module} :: {test}")
            print("-" * 70)
            print(traceback)
    
    # Return appropriate exit code
    return 0 if results["failed"] == 0 and results["errors"] == 0 else 1

if __name__ == "__main__":
    sys.exit(run_tests())