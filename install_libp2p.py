#!/usr/bin/env python3
"""
libp2p Dependency Installer

This script installs the required dependencies for libp2p functionality in IPFS Kit.
It handles dependency installation, verification, and provides detailed error reporting.
It also integrates with the MCP server to ensure all necessary dependencies are available.

Usage:
    python install_libp2p.py [--force] [--verbose] [--check-only] [--mcp-integration]

Options:
    --force            Force reinstallation even if dependencies are already installed
    --verbose          Enable verbose output for debugging
    --check-only       Only check if dependencies are installed, don't install anything
    --mcp-integration  Check specifically for MCP server integration requirements
"""

import os
import sys
import subprocess
import argparse
import importlib
import logging
import platform
import time
import json
from importlib.util import find_spec
from typing import Dict, List, Tuple, Any, Optional

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

# MCP integration dependencies
MCP_INTEGRATION_DEPENDENCIES = [
    "fastapi",
    "uvicorn",
    "anyio",
    "pydantic>=2.0.0"
]

# Minimum required versions for key dependencies
MINIMUM_VERSIONS = {
    "libp2p": "0.1.5",
    "multiaddr": "0.0.9",
    "fastapi": "0.100.0",
    "anyio": "3.7.0"
}

# Global flag to determine if we have tried Python development headers
CHECKED_PYTHON_DEV = False

def check_dependency(package: str) -> Tuple[bool, Optional[str]]:
    """
    Check if a dependency is installed and get its version.
    
    Args:
        package: Package name to check (may include version specifier)
        
    Returns:
        tuple: (is_installed, version)
    """
    # Extract the base package name without version specifier
    package_name = package.split('>=')[0].split('==')[0].split('<')[0].strip()
    
    try:
        # Try importing the module
        if package_name == "google-protobuf":
            # Special case for protobuf
            module = importlib.import_module("google.protobuf")
        elif package_name == "eth-hash":
            # Special case for eth-hash
            module = importlib.import_module("eth_hash")
        elif package_name == "eth-keys":
            # Special case for eth-keys
            module = importlib.import_module("eth_keys")
        else:
            module = importlib.import_module(package_name)
            
        # Try to get version
        version = getattr(module, "__version__", None)
        if version is None:
            # Try to get version from other common attributes
            version = getattr(module, "version", None)
            if version is None:
                try:
                    # Try using the package.__version__ pattern
                    version_module = importlib.import_module(f"{package_name}.__version__")
                    version = getattr(version_module, "__version__", "unknown")
                except ImportError:
                    try:
                        # Try using pkg_resources as a fallback
                        import pkg_resources
                        version = pkg_resources.get_distribution(package_name).version
                    except (ImportError, pkg_resources.DistributionNotFound):
                        version = "unknown"
                        
        # Check if version meets minimum requirement
        if package_name in MINIMUM_VERSIONS and version != "unknown":
            try:
                # Simple version comparison (this is a basic implementation)
                installed_parts = [int(x) for x in version.split('.')]
                required_parts = [int(x) for x in MINIMUM_VERSIONS[package_name].split('.')]
                
                # Pad with zeros if needed
                while len(installed_parts) < len(required_parts):
                    installed_parts.append(0)
                while len(required_parts) < len(installed_parts):
                    required_parts.append(0)
                    
                # Compare version components
                for i in range(len(installed_parts)):
                    if installed_parts[i] < required_parts[i]:
                        logger.warning(f"{package_name} version {version} is below minimum required {MINIMUM_VERSIONS[package_name]}")
                        return False, version
                    elif installed_parts[i] > required_parts[i]:
                        break
            except (ValueError, AttributeError, TypeError):
                # If version comparison fails, assume it's installed correctly
                pass
                
        return True, version
    except (ImportError, ModuleNotFoundError):
        return False, None
        
def check_python_dev_headers() -> bool:
    """
    Check if Python development headers are installed.
    These are required for building some libp2p dependencies.
    
    Returns:
        bool: True if development headers are available
    """
    global CHECKED_PYTHON_DEV
    
    if CHECKED_PYTHON_DEV:
        return True
        
    CHECKED_PYTHON_DEV = True
    
    # Different check methods depending on OS
    system = platform.system().lower()
    
    if system == "linux":
        try:
            # Try to find Python.h 
            import distutils.sysconfig
            include_dir = distutils.sysconfig.get_python_inc()
            python_h = os.path.join(include_dir, "Python.h")
            
            if os.path.exists(python_h):
                logger.info("Python development headers found.")
                return True
                
            logger.warning("Python development headers not found.")
            logger.warning("Some dependencies may fail to install.")
            logger.warning("On Debian/Ubuntu, run: sudo apt-get install python3-dev")
            logger.warning("On Fedora/RHEL, run: sudo dnf install python3-devel")
            return False
            
        except Exception as e:
            logger.warning(f"Error checking for Python development headers: {e}")
            return False
    
    # For macOS and Windows, assume headers are available
    return True

def install_dependencies(force=False, verbose=False, mcp_integration=False, check_only=False):
    """
    Install required and optional libp2p dependencies.
    
    Args:
        force: Force reinstallation even if already installed
        verbose: Enable verbose output
        mcp_integration: Install MCP server integration dependencies
        check_only: Only check if dependencies are installed, don't install anything
        
    Returns:
        bool: True if installation was successful, False otherwise
    """
    # Set pip verbosity
    pip_args = ["-v"] if verbose else []
    
    # Initialize results
    required_results = {}
    optional_results = {}
    mcp_results = {}
    
    # Check current state
    logger.info("Checking current dependency status...")
    all_required_installed = True
    
    # Check Python development headers
    check_python_dev_headers()
    
    # Check required dependencies
    for dep in REQUIRED_DEPENDENCIES:
        installed, version = check_dependency(dep)
        required_results[dep] = {"installed": installed, "version": version}
        if not installed:
            all_required_installed = False
    
    # If MCP integration, check those dependencies too
    all_mcp_installed = True
    if mcp_integration:
        logger.info("Checking MCP integration dependencies...")
        for dep in MCP_INTEGRATION_DEPENDENCIES:
            installed, version = check_dependency(dep)
            mcp_results[dep] = {"installed": installed, "version": version}
            if not installed:
                all_mcp_installed = False
    
    # If everything is installed and we're not forcing reinstall, we're done
    if all_required_installed and (not mcp_integration or all_mcp_installed) and not force:
        logger.info("All required dependencies are already installed.")
        logger.info("Use --force to reinstall.")
        
        # Display versions
        logger.info("Required dependencies:")
        for dep, result in required_results.items():
            logger.info(f"  {dep}: {result['version']}")
            
        if mcp_integration:
            logger.info("MCP integration dependencies:")
            for dep, result in mcp_results.items():
                logger.info(f"  {dep}: {result['version']}")
            
        return True
    
    # If check only, return the result without installing
    if check_only:
        if not all_required_installed:
            logger.warning("Some required dependencies are missing:")
            for dep, result in required_results.items():
                if not result["installed"]:
                    logger.warning(f"  {dep}: Not installed")
        
        if mcp_integration and not all_mcp_installed:
            logger.warning("Some MCP integration dependencies are missing:")
            for dep, result in mcp_results.items():
                if not result["installed"]:
                    logger.warning(f"  {dep}: Not installed")
                    
        return all_required_installed and (not mcp_integration or all_mcp_installed)
    
    # Install required dependencies
    if not all_required_installed or force:
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
    
    # Install MCP integration dependencies if needed
    if mcp_integration and (not all_mcp_installed or force):
        try:
            logger.info("Installing MCP integration dependencies...")
            cmd = [sys.executable, "-m", "pip", "install"] + pip_args
            
            if force:
                cmd.append("--upgrade")
                
            cmd.extend(MCP_INTEGRATION_DEPENDENCIES)
            
            logger.info(f"Running: {' '.join(cmd)}")
            subprocess.check_call(cmd)
            
            # Verify installation
            all_mcp_installed = True
            for dep in MCP_INTEGRATION_DEPENDENCIES:
                installed, version = check_dependency(dep)
                if not installed:
                    logger.error(f"Failed to install MCP dependency {dep}")
                    all_mcp_installed = False
                else:
                    logger.info(f"Successfully installed MCP dependency {dep} {version}")
                    
            if not all_mcp_installed:
                logger.warning("Some MCP integration dependencies could not be installed.")
                logger.warning("MCP server with libp2p integration may not work correctly.")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error installing MCP integration dependencies: {e}")
            logger.warning("MCP server with libp2p integration may not work correctly.")
    
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
            return False
            
        return True
    except Exception as e:
        logger.error(f"libp2p verification failed: {e}")
        return False


def verify_mcp_integration():
    """
    Verify that MCP integration dependencies are properly installed and functioning.
    
    Returns:
        bool: True if verification passes, False otherwise
    """
    logger.info("Verifying MCP integration functionality...")
    
    try:
        # Try to import core modules
        import fastapi
        import uvicorn
        import anyio
        import pydantic
        
        # Check pydantic version for v2 compatibility
        pydantic_major = int(pydantic.__version__.split('.')[0])
        if pydantic_major < 2:
            logger.warning(f"Pydantic version {pydantic.__version__} detected, but version 2.0.0+ is recommended")
            logger.warning("The MCP server may not work correctly with older pydantic versions")
        
        logger.info("MCP integration verification: Core imports successful")
        
        # Verify basic anyio functionality
        async def test_anyio():
            return 42
            
        try:
            result = anyio.run(test_anyio)
            assert result == 42
            logger.info("MCP integration verification: AnyIO functionality successful")
        except Exception as e:
            logger.error(f"AnyIO functionality verification failed: {e}")
            return False
            
        logger.info("MCP integration verification completed successfully")
        return True
    except Exception as e:
        logger.error(f"MCP integration verification failed: {e}")
        return False


def install_dependencies_auto(force=False, verbose=False, mcp_integration=False, check_only=False):
    """
    Install all required dependencies for libp2p functionality.
    
    This function can be imported and called directly by other modules
    to ensure dependencies are installed without running the script.
    
    Args:
        force: Force reinstallation even if already installed
        verbose: Enable verbose output
        mcp_integration: Install MCP server integration dependencies
        check_only: Only check if dependencies are installed, don't install
        
    Returns:
        bool: True if installation successful, False otherwise
    """
    # Set log level
    orig_level = logger.level
    if verbose:
        logger.setLevel(logging.DEBUG)
    
    try:
        # Install dependencies
        install_success = install_dependencies(
            force=force, 
            verbose=verbose,
            mcp_integration=mcp_integration,
            check_only=check_only
        )
        
        if check_only:
            return install_success
        
        if install_success:
            # Verify installation
            verify_success = verify_libp2p_functionality()
            
            # If MCP integration is requested, verify that too
            if mcp_integration and verify_success:
                mcp_verify_success = verify_mcp_integration()
                if not mcp_verify_success:
                    logger.error("MCP integration verification failed.")
                    return False
            
            if verify_success:
                logger.info("libp2p installation completed successfully!")
                if mcp_integration:
                    logger.info("MCP integration dependencies installed successfully!")
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


def get_libp2p_status():
    """
    Get the status of libp2p dependencies as a dictionary.
    
    Returns:
        dict: Status information about libp2p dependencies
    """
    status = {
        "timestamp": time.time(),
        "libp2p_available": False,
        "required_dependencies": {},
        "optional_dependencies": {},
        "mcp_integration": {
            "checked": False,
            "available": False,
            "dependencies": {}
        },
        "verification": {
            "performed": False,
            "success": False,
            "errors": []
        }
    }
    
    # Check required dependencies
    all_required_installed = True
    for dep in REQUIRED_DEPENDENCIES:
        installed, version = check_dependency(dep)
        status["required_dependencies"][dep] = {
            "installed": installed,
            "version": version
        }
        if not installed:
            all_required_installed = False
    
    status["libp2p_available"] = all_required_installed
    
    # Check optional dependencies
    for dep in OPTIONAL_DEPENDENCIES:
        installed, version = check_dependency(dep)
        status["optional_dependencies"][dep] = {
            "installed": installed,
            "version": version
        }
    
    # Check MCP integration dependencies
    mcp_available = True
    for dep in MCP_INTEGRATION_DEPENDENCIES:
        installed, version = check_dependency(dep)
        status["mcp_integration"]["dependencies"][dep] = {
            "installed": installed,
            "version": version
        }
        if not installed:
            mcp_available = False
    
    status["mcp_integration"]["checked"] = True
    status["mcp_integration"]["available"] = mcp_available
    
    # Verify functionality if required dependencies are available
    if all_required_installed:
        try:
            status["verification"]["performed"] = True
            status["verification"]["success"] = verify_libp2p_functionality()
        except Exception as e:
            status["verification"]["performed"] = True
            status["verification"]["success"] = False
            status["verification"]["errors"].append(str(e))
    
    return status

def main():
    """
    Main function to parse arguments and install dependencies.
    """
    parser = argparse.ArgumentParser(description="Install libp2p dependencies for IPFS Kit")
    parser.add_argument("--force", action="store_true", help="Force reinstallation even if already installed")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--check-only", action="store_true", help="Only check if dependencies are installed")
    parser.add_argument("--mcp-integration", action="store_true", help="Install MCP server integration dependencies")
    parser.add_argument("--status-json", action="store_true", help="Output detailed status as JSON")
    args = parser.parse_args()
    
    # Set log level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Print welcome message
    logger.info("IPFS Kit - libp2p Dependency Installer")
    logger.info("=====================================")
    
    if args.status_json:
        # Just output the status as JSON
        status = get_libp2p_status()
        print(json.dumps(status, indent=2))
        return 0
    
    # Use the common function for installation
    success = install_dependencies_auto(
        force=args.force, 
        verbose=args.verbose,
        mcp_integration=args.mcp_integration,
        check_only=args.check_only
    )
    
    if success:
        logger.info("=======================================")
        if args.check_only:
            logger.info("All required dependencies are installed.")
            if args.mcp_integration:
                logger.info("MCP integration dependencies are also installed.")
        else:
            logger.info("libp2p installation completed successfully!")
            logger.info("libp2p functionality is now available in IPFS Kit.")
            if args.mcp_integration:
                logger.info("MCP integration is now available.")
        return 0
    else:
        logger.error("=======================================")
        if args.check_only:
            logger.error("Some dependencies are missing.")
            logger.info("Run without --check-only to install the missing dependencies.")
        else:
            logger.error("libp2p installation failed.")
            logger.error("Please try installing the dependencies manually:")
            logger.error(f"pip install {' '.join(REQUIRED_DEPENDENCIES)}")
            if args.mcp_integration:
                logger.error(f"pip install {' '.join(MCP_INTEGRATION_DEPENDENCIES)}")
        return 1


def ensure_mcp_libp2p_integration():
    """
    Ensure that libp2p and MCP server dependencies are installed.
    This is a helper function to be called from the MCP server.
    
    Returns:
        bool: True if all dependencies are available
    """
    # Check if auto-installation is enabled
    auto_install = os.environ.get("IPFS_KIT_AUTO_INSTALL_DEPS", "0") == "1"
    
    if auto_install:
        # Install dependencies
        return install_dependencies_auto(mcp_integration=True)
    else:
        # Just check if dependencies are installed
        return install_dependencies_auto(check_only=True, mcp_integration=True)


if __name__ == "__main__":
    sys.exit(main())