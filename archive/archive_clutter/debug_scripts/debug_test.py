#!/usr/bin/env python3
"""
Test debug utility for IPFS Kit Python.

This script provides utilities to debug test failures by setting up the environment
and running specific tests with increased verbosity.
"""

import os
import sys
import argparse
import logging
import subprocess
from pathlib import Path
import tempfile
import traceback
import importlib.util

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_debug")

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Debug tests for IPFS Kit Python")
    parser.add_argument(
        "test_path", 
        help="Path to the test file or test function (e.g., test_file.py::test_function)"
    )
    parser.add_argument(
        "--pdb", 
        action="store_true", 
        help="Run with Python debugger on failure"
    )
    parser.add_argument(
        "--ipdb", 
        action="store_true", 
        help="Run with IPython debugger on failure"
    )
    parser.add_argument(
        "--trace", 
        action="store_true", 
        help="Run with full traceback"
    )
    parser.add_argument(
        "--mock", 
        action="store_true", 
        help="Run with enhanced mock environment"
    )
    parser.add_argument(
        "--setup-only", 
        action="store_true", 
        help="Only set up the environment, don't run tests"
    )
    parser.add_argument(
        "--no-capture", 
        action="store_true", 
        help="Don't capture stdout/stderr"
    )
    return parser.parse_args()

def setup_mock_environment():
    """Set up a mock environment for testing."""
    logger.info("Setting up mock environment")
    
    # Create mock versions of external dependencies
    mock_modules = {
        "libp2p": {},
        "fsspec": {},
        "fastapi": {
            "FastAPI": type("FastAPI", (), {"get": lambda *args, **kwargs: None}),
            "HTTPException": Exception,
        },
        "boto3": {
            "client": lambda *args, **kwargs: None
        }
    }
    
    # Add mocks to sys.modules
    for module_name, module_content in mock_modules.items():
        if module_name not in sys.modules:
            sys.modules[module_name] = type(module_name, (), module_content)
            logger.info(f"Mocked {module_name}")
    
    return True

def run_test_with_pytest(test_path, pdb=False, ipdb=False, trace=False, no_capture=False):
    """Run a test with pytest."""
    cmd = ["python", "-m", "pytest", test_path, "-v"]
    
    if pdb:
        cmd.append("--pdb")
    
    if ipdb:
        cmd.append("--ipdb")
    
    if trace:
        cmd.append("--trace")
    
    if no_capture:
        cmd.append("-s")
    
    logger.info(f"Running: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode == 0
    except Exception as e:
        logger.error(f"Error running pytest: {e}")
        return False

def debug_specific_test(test_path):
    """Debug a specific test by loading it and running it directly."""
    if "::" not in test_path:
        logger.error("Test function not specified (use test_file.py::test_function)")
        return False
    
    file_path, func_name = test_path.split("::")
    
    try:
        # Load the module
        spec = importlib.util.spec_from_file_location("test_module", file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Get the test function
        test_func = getattr(module, func_name)
        
        # Run the test function
        logger.info(f"Running test function {func_name} from {file_path}")
        test_func()
        
        logger.info("Test completed successfully")
        return True
    except Exception as e:
        logger.error(f"Error debugging test: {e}")
        traceback.print_exc()
        return False

def main():
    """Main entry point."""
    args = parse_args()
    
    # Set up mock environment if requested
    if args.mock:
        setup_mock_environment()
    
    # Exit if only setting up the environment
    if args.setup_only:
        logger.info("Environment setup complete")
        return 0
    
    # Run the test with pytest
    success = run_test_with_pytest(
        args.test_path,
        pdb=args.pdb,
        ipdb=args.ipdb,
        trace=args.trace,
        no_capture=args.no_capture
    )
    
    if success:
        logger.info("Test passed")
        return 0
    else:
        logger.error("Test failed")
        
        # If the test failed and we didn't use a debugger, suggest using one
        if not args.pdb and not args.ipdb:
            logger.info("Try running with --pdb or --ipdb to debug the failure")
        
        return 1

if __name__ == "__main__":
    sys.exit(main())
