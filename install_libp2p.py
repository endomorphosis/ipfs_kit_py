#!/usr/bin/env python3
"""
libp2p Dependency Installer

This script installs the required dependencies for libp2p functionality in IPFS Kit.
It handles dependency installation, verification, and provides detailed error reporting.

Usage:
    python install_libp2p.py [--force] [--verbose]

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
    "libp2p",
    "multiaddr",
    "base58",
    "cryptography"
]

# Optional dependencies that enhance functionality
OPTIONAL_DEPENDENCIES = [
    "google-protobuf",
    "eth-hash",
    "eth-keys"
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
        # Try importing the module
        if package == "google-protobuf":
            # Special case for protobuf
            module = importlib.import_module("google.protobuf")
        else:
            module = importlib.import_module(package)
            
        # Try to get version
        version = getattr(module, "__version__", "unknown")
        return True, version
    except (ImportError, ModuleNotFoundError):
        return False, None

def install_dependencies(force=False, verbose=False):
    """
    Install required and optional libp2p dependencies.
    
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
                
        if not all_installed:
            return False
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

def verify_libp2p_functionality():
    """
    Verify that libp2p is properly installed and functioning.
    
    Returns:
        bool: True if verification passes, False otherwise
    """
    logger.info("Verifying libp2p functionality...")
    
    try:
        # Try to import core modules
        import libp2p
        from libp2p import new_host
        from libp2p.crypto.keys import KeyPair
        
        # Verify key generation works
        key_pair = libp2p.crypto.keys.generate_key_pair()
        
        logger.info("libp2p verification: Core imports successful")
        logger.info("libp2p verification: Key generation successful")
        
        # Verify additional modules if available
        try:
            import multiaddr
            ma = multiaddr.Multiaddr("/ip4/127.0.0.1/tcp/4001")
            logger.info("multiaddr verification: Successful")
        except (ImportError, Exception) as e:
            logger.warning(f"multiaddr verification: Failed - {e}")
            
        return True
    except Exception as e:
        logger.error(f"libp2p verification failed: {e}")
        return False

def install_dependencies_auto(force=False, verbose=False):
    """
    Install all required dependencies for libp2p functionality.
    
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
            verify_success = verify_libp2p_functionality()
            
            if verify_success:
                logger.info("libp2p installation completed successfully!")
                return True
            else:
                logger.error("libp2p installation completed but verification failed.")
                return False
        else:
            logger.error("libp2p installation failed.")
            return False
    finally:
        # Restore original log level
        logger.setLevel(orig_level)

def main():
    """
    Main function to parse arguments and install dependencies.
    """
    parser = argparse.ArgumentParser(description="Install libp2p dependencies for IPFS Kit")
    parser.add_argument("--force", action="store_true", help="Force reinstallation even if already installed")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    args = parser.parse_args()
    
    # Set log level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Print welcome message
    logger.info("IPFS Kit - libp2p Dependency Installer")
    logger.info("=====================================")
    
    # Use the common function for installation
    success = install_dependencies_auto(force=args.force, verbose=args.verbose)
    
    if success:
        logger.info("=======================================")
        logger.info("libp2p installation completed successfully!")
        logger.info("libp2p functionality is now available in IPFS Kit.")
        return 0
    else:
        logger.error("=======================================")
        logger.error("libp2p installation failed.")
        logger.error("Please try installing the dependencies manually:")
        logger.error(f"pip install {' '.join(REQUIRED_DEPENDENCIES)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())