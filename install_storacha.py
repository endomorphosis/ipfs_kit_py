#!/usr/bin/env python3
"""
Storacha/Web3.Storage Dependency Installer

This script installs the required dependencies for storacha_kit functionality in IPFS Kit.
It handles dependency installation, verification, and provides detailed error reporting.

Usage:
    python install_storacha.py [--force] [--verbose]

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
import json
import platform
import tempfile
from importlib.util import find_spec

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# List of required Python dependencies
REQUIRED_DEPENDENCIES = [
    "requests",
    "urllib3",
]

# Optional Python dependencies that enhance functionality
OPTIONAL_DEPENDENCIES = [
    "pyyaml",
    "ujson",
]

# NPM dependencies for the W3 CLI
W3_CLI_DEPENDENCY = "@web3-storage/w3cli"

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

def check_npm_installed():
    """
    Check if npm is installed and available.
    
    Returns:
        bool: True if npm is installed, False otherwise
    """
    try:
        subprocess.run(
            ["npm", "--version"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            check=True
        )
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False

def check_w3_cli_installed():
    """
    Check if the W3 CLI is installed globally.
    
    Returns:
        tuple: (is_installed, version)
    """
    try:
        # Windows needs special handling
        cmd = ["npx", "--no", "w3", "--version"] if platform.system() == "Windows" else ["w3", "--version"]
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            encoding="utf-8"
        )
        
        # Extract version from output
        version = result.stdout.strip()
        return True, version
    except (subprocess.SubprocessError, FileNotFoundError):
        return False, None

def install_python_dependencies(force=False, verbose=False):
    """
    Install required and optional Python dependencies.
    
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
    
    # Check current state
    logger.info("Checking current Python dependency status...")
    all_required_installed = True
    
    for dep in REQUIRED_DEPENDENCIES:
        installed, version = check_dependency(dep)
        required_results[dep] = {"installed": installed, "version": version}
        if not installed:
            all_required_installed = False
            
    if all_required_installed and not force:
        logger.info("All required Python dependencies are already installed.")
        if force:
            logger.info("Will reinstall due to --force flag.")
        else:
            # Display versions
            for dep, result in required_results.items():
                logger.info(f"  {dep}: {result['version']}")
            return True
    
    # Install required dependencies
    try:
        logger.info("Installing required Python dependencies...")
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
                
        if not all_installed:
            return False
    except subprocess.CalledProcessError as e:
        logger.error(f"Error installing required dependencies: {e}")
        return False
    
    # Install optional dependencies
    try:
        logger.info("Installing optional Python dependencies...")
        cmd = [sys.executable, "-m", "pip", "install"] + pip_args
        
        if force:
            cmd.append("--upgrade")
            
        cmd.extend(OPTIONAL_DEPENDENCIES)
        
        logger.info(f"Running: {' '.join(cmd)}")
        subprocess.check_call(cmd)
        
        # Report on optional dependencies
        for dep in OPTIONAL_DEPENDENCIES:
            installed, version = check_dependency(dep)
            if installed:
                logger.info(f"Successfully installed optional dependency {dep} {version}")
            else:
                logger.warning(f"Optional dependency {dep} not installed")
    except subprocess.CalledProcessError as e:
        logger.warning(f"Error installing optional dependencies: {e}")
        logger.warning("Some optional functionality may not be available.")
    
    return True

def install_w3_cli(force=False, verbose=False):
    """
    Install the W3 CLI tool via npm.
    
    Args:
        force: Force reinstallation even if already installed
        verbose: Enable verbose output
        
    Returns:
        bool: True if installation was successful, False otherwise
    """
    # Check if npm is installed
    if not check_npm_installed():
        logger.error("npm is not installed. Please install Node.js and npm first.")
        logger.error("Visit https://nodejs.org/ for installation instructions.")
        return False
    
    # Check if W3 CLI is already installed
    w3_installed, w3_version = check_w3_cli_installed()
    
    if w3_installed and not force:
        logger.info(f"W3 CLI is already installed (version: {w3_version})")
        logger.info("Use --force to reinstall.")
        return True
    
    # Install W3 CLI
    try:
        logger.info(f"Installing {W3_CLI_DEPENDENCY} globally...")
        
        # Build npm command
        npm_args = []
        if verbose:
            npm_args.append("--loglevel=verbose")
            
        install_cmd = ["npm", "install", "-g", W3_CLI_DEPENDENCY] + npm_args
        
        logger.info(f"Running: {' '.join(install_cmd)}")
        subprocess.check_call(install_cmd)
        
        # Verify installation
        w3_installed, w3_version = check_w3_cli_installed()
        
        if w3_installed:
            logger.info(f"Successfully installed W3 CLI {w3_version}")
            return True
        else:
            logger.error("W3 CLI installation verification failed")
            return False
            
    except subprocess.CalledProcessError as e:
        logger.error(f"Error installing W3 CLI: {e}")
        return False

def verify_storacha_functionality():
    """
    Verify that storacha_kit dependencies are properly installed and functioning.
    
    Returns:
        bool: True if verification passes, False otherwise
    """
    logger.info("Verifying storacha_kit functionality...")
    
    # Verify Python dependencies
    try:
        import requests
        logger.info("requests verification: Successful")
    except ImportError:
        logger.error("requests verification: Failed - module could not be imported")
        return False
        
    # Verify W3 CLI
    w3_installed, w3_version = check_w3_cli_installed()
    if w3_installed:
        logger.info(f"W3 CLI verification: Successful (version: {w3_version})")
    else:
        logger.error("W3 CLI verification: Failed - command not found")
        return False
        
    # Test basic functionality
    try:
        # Try to run a simple w3 command to check if it works
        cmd = ["npx", "w3", "--help"] if platform.system() == "Windows" else ["w3", "--help"]
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            encoding="utf-8"
        )
        
        if "Usage" in result.stdout:
            logger.info("W3 CLI command execution: Successful")
        else:
            logger.warning("W3 CLI command execution: Output doesn't contain expected content")
            
        return True
    except Exception as e:
        logger.error(f"W3 CLI command execution failed: {e}")
        return False

def install_dependencies_auto(force=False, verbose=False):
    """
    Install all required dependencies for storacha functionality.
    
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
        # Install Python dependencies
        python_success = install_python_dependencies(force=force, verbose=verbose)
        
        if not python_success:
            logger.error("Failed to install required Python dependencies.")
            return False
            
        # Install W3 CLI
        w3_success = install_w3_cli(force=force, verbose=verbose)
        
        if not w3_success:
            logger.error("Failed to install W3 CLI.")
            logger.error(f"You may need to install it manually: npm install -g {W3_CLI_DEPENDENCY}")
            return False
        
        # Verify installation
        if python_success and w3_success:
            verify_success = verify_storacha_functionality()
            
            if verify_success:
                logger.info("Storacha installation completed successfully!")
                return True
            else:
                logger.error("Storacha installation completed but verification failed.")
                return False
        else:
            logger.error("Storacha installation failed.")
            return False
    finally:
        # Restore original log level
        logger.setLevel(orig_level)

def main():
    """
    Main function to parse arguments and install dependencies.
    """
    parser = argparse.ArgumentParser(description="Install storacha/web3.storage dependencies for IPFS Kit")
    parser.add_argument("--force", action="store_true", help="Force reinstallation even if already installed")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    args = parser.parse_args()
    
    # Set log level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Print welcome message
    logger.info("IPFS Kit - Storacha/Web3.Storage Dependency Installer")
    logger.info("=================================================")
    
    # Use the common function for installation
    success = install_dependencies_auto(force=args.force, verbose=args.verbose)
    
    if success:
        logger.info("=================================================")
        logger.info("Storacha installation completed successfully!")
        logger.info("Storacha functionality is now available in IPFS Kit.")
        return 0
    else:
        logger.error("=================================================")
        logger.error("Storacha installation failed.")
        logger.error("Please check the logs and try installing the dependencies manually.")
        return 1

if __name__ == "__main__":
    sys.exit(main())