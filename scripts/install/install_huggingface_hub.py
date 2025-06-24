#!/usr/bin/env python3
"""
Hugging Face Hub Dependency Installer

This script installs the required dependencies for Hugging Face Hub functionality in IPFS Kit.
It handles dependency installation, verification, and provides detailed error reporting.

Usage:
    python install_huggingface_hub.py [--force] [--verbose]

Options:
    --force    Force reinstallation even if dependencies are already installed
    --verbose  Enable verbose output for debugging
"""

import os
import sys
import subprocess
import argparse
import importlib
import logging
from importlib.util import find_spec

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# List of required dependencies
REQUIRED_DEPENDENCIES = [
    "huggingface_hub",
    "fsspec",
    "pyyaml",
    "tqdm",
    "requests",
]

# Optional dependencies that enhance functionality
OPTIONAL_DEPENDENCIES = [
    "aiohttp",  # For async operations
    "transformers",  # For working with transformer models
    "safetensors",  # For safely loading models
    "torch",  # For PyTorch models
    "tokenizers",  # For working with tokenizers
]

def check_dependency(package):
    """
    Check if a dependency is installed.

    Args:
        package: Package name to check

    Returns:
        tuple: (is_installed, version)
    """
    try:
        # Handle special cases where package name doesn't match module name
        package_to_module = {
            "pyyaml": "yaml",  # PyYAML's module name is 'yaml'
            "huggingface-hub": "huggingface_hub",
            "huggingface_hub": "huggingface_hub",
        }

        # Get the correct module name for import
        if package in package_to_module:
            module_name = package_to_module[package]
        else:
            module_name = package.replace("-", "_")  # Replace hyphens with underscores for import

        # Try importing the module
        module = importlib.import_module(module_name)

        # Try to get version
        version = getattr(module, "__version__", "unknown")
        return True, version
    except (ImportError, ModuleNotFoundError):
        return False, None

def install_dependencies(force=False, verbose=False):
    """
    Install required and optional Hugging Face Hub dependencies.

    Args:
        force: Force reinstallation even if already installed
        verbose: Enable verbose output

    Returns:
        bool: True if installation was successful, False otherwise
    """
    # Set pip verbosity
    pip_args = ["-v"] if verbose else []

    # Initialize results
    required_results = {}
    optional_results = {}

    # Check current state
    logger.info("Checking current dependency status...")
    all_required_installed = True

    for dep in REQUIRED_DEPENDENCIES:
        installed, version = check_dependency(dep)
        required_results[dep] = {"installed": installed, "version": version}
        if not installed:
            all_required_installed = False

    if all_required_installed and not force:
        logger.info("All required dependencies are already installed.")
        logger.info("Use --force to reinstall.")

        # Display versions
        for dep, result in required_results.items():
            logger.info(f"  {dep}: {result['version']}")

        return True

    # Install required dependencies
    try:
        logger.info("Installing required dependencies...")
        cmd = [sys.executable, "-m", "pip", "install"] + pip_args

        if force:
            cmd.append("--upgrade")

        cmd.extend(REQUIRED_DEPENDENCIES)

        logger.info(f"Running: {' '.join(cmd)}")
        subprocess.check_call(cmd)

        # Verify installation
        all_installed = True
        for dep in REQUIRED_DEPENDENCIES:
            installed, version = check_dependency(dep)
            if not installed:
                logger.error(f"Failed to install {dep}")
                all_installed = False
            else:
                logger.info(f"Successfully installed {dep} {version}")

        # If some dependencies couldn't be installed, report failure
        if not all_installed:
            return False

        # Otherwise, all required dependencies were successfully installed
        logger.info("All required dependencies successfully installed.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error installing required dependencies: {e}")
        return False

    # Install optional dependencies
    try:
        logger.info("Installing optional dependencies...")
        cmd = [sys.executable, "-m", "pip", "install"] + pip_args

        if force:
            cmd.append("--upgrade")

        cmd.extend(OPTIONAL_DEPENDENCIES)

        logger.info(f"Running: {' '.join(cmd)}")
        subprocess.check_call(cmd)

        # Report on optional dependencies
        all_optionals_installed = True
        for dep in OPTIONAL_DEPENDENCIES:
            installed, version = check_dependency(dep)
            if installed:
                logger.info(f"Successfully installed optional dependency {dep} {version}")
            else:
                logger.warning(f"Optional dependency {dep} not installed")
                all_optionals_installed = False

        if all_optionals_installed:
            logger.info("All optional dependencies successfully installed.")
        else:
            logger.warning("Some optional dependencies were not installed. This is not a critical issue.")
    except subprocess.CalledProcessError as e:
        logger.warning(f"Error installing optional dependencies: {e}")
        logger.warning("Some optional functionality may not be available.")

    return True

def verify_huggingface_hub_functionality():
    """
    Verify that Hugging Face Hub is properly installed and functioning.

    Returns:
        bool: True if verification passes, False otherwise
    """
    logger.info("Verifying Hugging Face Hub functionality...")

    # First verify the core module imports
    try:
        # Try to import core modules
        import huggingface_hub
        from huggingface_hub import HfApi, HfFolder

        logger.info("Hugging Face Hub verification: Core imports successful")
        logger.info(f"Hugging Face Hub version: {getattr(huggingface_hub, '__version__', 'unknown')}")

        # Check if credentials configuration is possible
        try:
            token_path = HfFolder.path_token if hasattr(HfFolder, 'path_token') else HfFolder().path_token
            logger.info(f"Hugging Face Hub token path: {token_path}")
        except Exception as e:
            # This is non-critical, may happen with newer versions
            logger.warning(f"Could not determine token path: {e}")
            token_path = "~/.huggingface/token"
            logger.info(f"Default token path should be: {token_path}")

        logger.info("Note: You can set up authentication using `huggingface-cli login`")

        # Verify additional modules
        try:
            from huggingface_hub import Repository
            logger.info("Hugging Face Hub Repository functionality: Available")
        except (ImportError, Exception) as e:
            logger.warning(f"Hugging Face Hub Repository verification: Failed - {e}")

        # Try to verify API access (but don't let this fail verification if network issues)
        try:
            # Verify API access works
            api = HfApi()

            # Try a simple API call that doesn't require authentication
            models = api.list_models(limit=1)
            logger.info("Hugging Face Hub verification: API access successful")
        except Exception as e:
            logger.warning(f"Hugging Face Hub API access verification: Failed - {e}")
            logger.warning("This may be due to network issues and does not indicate an installation problem.")
            # Continue with imports verified

        return True

    except ImportError as e:
        logger.error(f"Hugging Face Hub core imports failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Hugging Face Hub verification failed: {e}")
        return False

def install_dependencies_auto(force=False, verbose=False):
    """
    Install all required dependencies for Hugging Face Hub functionality.

    This function can be imported and called directly by other modules
    to ensure dependencies are installed without running the script.

    Args:
        force: Force reinstallation even if already installed
        verbose: Enable verbose output

    Returns:
        bool: True if installation successful, False otherwise
    """
    # Set log level
    orig_level = logger.level
    if verbose:
        logger.setLevel(logging.DEBUG)

    try:
        # Install dependencies
        install_success = install_dependencies(force=force, verbose=verbose)

        if install_success:
            # Verify installation
            verify_success = verify_huggingface_hub_functionality()

            if verify_success:
                logger.info("Hugging Face Hub installation completed successfully!")
                return True
            else:
                logger.error("Hugging Face Hub installation completed but verification failed.")
                return False
        else:
            logger.error("Hugging Face Hub installation failed.")
            return False
    finally:
        # Restore original log level
        logger.setLevel(orig_level)

def main():
    """
    Main function to parse arguments and install dependencies.
    """
    parser = argparse.ArgumentParser(description="Install Hugging Face Hub dependencies for IPFS Kit")
    parser.add_argument("--force", action="store_true", help="Force reinstallation even if already installed")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    args = parser.parse_args()

    # Set log level
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Print welcome message
    logger.info("IPFS Kit - Hugging Face Hub Dependency Installer")
    logger.info("=============================================")

    # Use the common function for installation
    success = install_dependencies_auto(force=args.force, verbose=args.verbose)

    if success:
        logger.info("=============================================")
        logger.info("Hugging Face Hub installation completed successfully!")
        logger.info("Hugging Face Hub functionality is now available in IPFS Kit.")
        logger.info("")
        logger.info("To authenticate with Hugging Face Hub, run:")
        logger.info("  huggingface-cli login")
        return 0
    else:
        logger.error("=============================================")
        logger.error("Hugging Face Hub installation completed but verification failed.")
        logger.error("Please try installing the dependencies manually:")
        logger.error(f"pip install {' '.join(REQUIRED_DEPENDENCIES)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
