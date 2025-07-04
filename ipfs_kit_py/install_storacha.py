#!/usr/bin/env python3
"""
Storacha installation script for ipfs_kit_py.

This script handles the installation of Storacha/Web3.Storage dependencies and CLI tools
for the ipfs_kit_py package. It provides a comprehensive, class-based implementation for 
installing and configuring Storacha components on multiple platforms.

Usage:
    As a module: from install_storacha import install_storacha
                 installer = install_storacha(resources=None, metadata={"force": True})
                 installer.install_storacha_dependencies()
                 installer.install_w3_cli()

    As a script: python install_storacha.py [--force] [--verbose]
"""

import argparse
import hashlib
import json
import logging
import os
import platform
import random
import shutil
import subprocess
import sys
import tempfile
import importlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("install_storacha")

# List of required Python dependencies
REQUIRED_DEPENDENCIES = [
    "requests>=2.28.0",
    "urllib3>=1.26.0",
]

# Optional Python dependencies that enhance functionality
OPTIONAL_DEPENDENCIES = [
    "pyyaml>=6.0",
    "ujson>=5.0.0",
]

# NPM dependencies for the W3 CLI
W3_CLI_DEPENDENCY = "@web3-storage/w3cli"
DEFAULT_W3_VERSION = "latest"

class install_storacha:
    """Class for installing and configuring Storacha components."""
    
    def __init__(self, resources=None, metadata=None):
        """
        Initialize Storacha installer with resources and metadata.
        
        Args:
            resources: Dictionary of resources that may be shared between components
            metadata: Dictionary of metadata for configuration
                Supported metadata:
                    - force: Force reinstallation even if already installed
                    - verbose: Enable verbose output
                    - auto_install_deps: Automatically install dependencies (default: True)
                    - skip_npm: Skip NPM dependencies installation
                    - w3_version: Specific W3 CLI version to install
        """
        # Initialize basic properties
        self.resources = resources or {}
        self.metadata = metadata or {}
        
        # Setup environment
        self.this_dir = os.path.dirname(os.path.realpath(__file__))
        self.env_path = os.environ.get("PATH", "")
        
        # Configuration options
        self.force = self.metadata.get("force", False)
        self.verbose = self.metadata.get("verbose", False)
        self.skip_npm = self.metadata.get("skip_npm", False)
        self.w3_version = self.metadata.get("w3_version", DEFAULT_W3_VERSION)
        
        # Set up logging level
        if self.verbose:
            logger.setLevel(logging.DEBUG)
            
        # Auto install dependencies if requested
        auto_install = self.metadata.get("auto_install_deps", True)
        if auto_install:
            try:
                self._install_system_dependencies()
            except Exception as e:
                logger.warning(f"Failed to auto-install system dependencies: {e}")
    
    def _install_system_dependencies(self):
        """Install or verify system dependencies."""
        logger.info("Checking for required system dependencies...")
        
        # Check for Node.js/npm if we're not skipping npm
        if not self.skip_npm:
            if not self._check_npm_installed():
                logger.warning("npm is not installed. W3 CLI installation will be skipped.")
                logger.info("To install Node.js and npm, visit: https://nodejs.org/")
                self.skip_npm = True
        
        logger.info("System dependency check complete")
    
    def _check_npm_installed(self) -> bool:
        """
        Check if npm is installed and available.
        
        Returns:
            bool: True if npm is installed, False otherwise
        """
        try:
            result = subprocess.run(
                ["npm", "--version"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                check=True,
                timeout=10
            )
            version = result.stdout.decode().strip()
            logger.info(f"Found npm version: {version}")
            return True
        except (subprocess.SubprocessError, subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def _check_dependency(self, package: str) -> Tuple[bool, Optional[str]]:
        """
        Check if a Python dependency is installed.
        
        Args:
            package: Package name to check (may include version requirements)
            
        Returns:
            tuple: (is_installed, version)
        """
        try:
            # Extract package name from version requirements
            package_name = package.split(">=")[0].split("==")[0].split(">")[0].split("<")[0]
            
            # Handle special cases where package name doesn't match module name
            package_to_module = {
                "pyyaml": "yaml",
            }
            
            # Get the correct module name for import
            if package_name in package_to_module:
                module_name = package_to_module[package_name]
            else:
                module_name = package_name.replace("-", "_")
                
            # Try importing the module
            module = importlib.import_module(module_name)
                
            # Try to get version
            version = getattr(module, "__version__", "unknown")
            return True, version
        except (ImportError, ModuleNotFoundError):
            return False, None
    
    def _check_w3_cli_installed(self) -> Tuple[bool, Optional[str]]:
        """
        Check if the W3 CLI is installed.
        
        Returns:
            tuple: (is_installed, version)
        """
        try:
            # Try different commands based on platform
            if platform.system() == "Windows":
                cmd = ["npx", "--no", "w3", "--version"]
            else:
                cmd = ["w3", "--version"]
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                encoding="utf-8",
                timeout=10
            )
            
            # Extract version from output
            version = result.stdout.strip()
            return True, version
        except (subprocess.SubprocessError, subprocess.TimeoutExpired, FileNotFoundError):
            return False, None
    
    def install_python_dependencies(self) -> bool:
        """
        Install required and optional Python dependencies.
        
        Returns:
            bool: True if installation was successful, False otherwise
        """
        # Check current state
        logger.info("Checking current Python dependency status...")
        all_required_installed = True
        
        required_results = {}
        for dep in REQUIRED_DEPENDENCIES:
            installed, version = self._check_dependency(dep)
            required_results[dep] = {"installed": installed, "version": version}
            if not installed:
                all_required_installed = False
                
        if all_required_installed and not self.force:
            logger.info("All required Python dependencies are already installed.")
            for dep, result in required_results.items():
                logger.info(f"  {dep}: {result['version']}")
            return True
        
        # Install required dependencies
        try:
            logger.info("Installing required Python dependencies...")
            cmd = [sys.executable, "-m", "pip", "install"]
            
            if self.verbose:
                cmd.append("-v")
            if self.force:
                cmd.append("--upgrade")
                
            cmd.extend(REQUIRED_DEPENDENCIES)
            
            logger.info(f"Running: {' '.join(cmd)}")
            subprocess.check_call(cmd)
            
            # Verify installation
            all_installed = True
            for dep in REQUIRED_DEPENDENCIES:
                installed, version = self._check_dependency(dep)
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
            cmd = [sys.executable, "-m", "pip", "install"]
            
            if self.verbose:
                cmd.append("-v")
            if self.force:
                cmd.append("--upgrade")
                
            cmd.extend(OPTIONAL_DEPENDENCIES)
            
            logger.info(f"Running: {' '.join(cmd)}")
            subprocess.check_call(cmd)
            
            # Report on optional dependencies
            for dep in OPTIONAL_DEPENDENCIES:
                installed, version = self._check_dependency(dep)
                if installed:
                    logger.info(f"Successfully installed optional dependency {dep} {version}")
                else:
                    logger.warning(f"Optional dependency {dep} not installed")
        except subprocess.CalledProcessError as e:
            logger.warning(f"Error installing optional dependencies: {e}")
            logger.warning("Some optional functionality may not be available.")
        
        return True
    
    def install_w3_cli(self) -> bool:
        """
        Install the W3 CLI tool via npm.
        
        Returns:
            bool: True if installation was successful, False otherwise
        """
        if self.skip_npm:
            logger.warning("Skipping W3 CLI installation (npm not available)")
            return False
        
        # Check if npm is installed
        if not self._check_npm_installed():
            logger.error("npm is not installed. Please install Node.js and npm first.")
            logger.error("Visit https://nodejs.org/ for installation instructions.")
            return False
        
        # Check if W3 CLI is already installed
        w3_installed, w3_version = self._check_w3_cli_installed()
        
        if w3_installed and not self.force:
            logger.info(f"W3 CLI is already installed (version: {w3_version})")
            logger.info("Use force=True to reinstall.")
            return True
        
        # Install W3 CLI
        try:
            w3_package = f"{W3_CLI_DEPENDENCY}@{self.w3_version}"
            logger.info(f"Installing {w3_package} globally...")
            
            # Build npm command
            npm_args = []
            if self.verbose:
                npm_args.append("--loglevel=verbose")
                
            install_cmd = ["npm", "install", "-g", w3_package] + npm_args
            
            logger.info(f"Running: {' '.join(install_cmd)}")
            subprocess.check_call(install_cmd, timeout=300)  # 5 minute timeout
            
            # Verify installation
            w3_installed, w3_version = self._check_w3_cli_installed()
            
            if w3_installed:
                logger.info(f"Successfully installed W3 CLI {w3_version}")
                return True
            else:
                logger.error("W3 CLI installation verification failed")
                return False
                
        except subprocess.CalledProcessError as e:
            logger.error(f"Error installing W3 CLI: {e}")
            return False
        except subprocess.TimeoutExpired:
            logger.error("W3 CLI installation timed out")
            return False
    
    def verify_storacha_functionality(self) -> bool:
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
            
        # Verify W3 CLI (only if npm is available)
        if not self.skip_npm:
            w3_installed, w3_version = self._check_w3_cli_installed()
            if w3_installed:
                logger.info(f"W3 CLI verification: Successful (version: {w3_version})")
            else:
                logger.error("W3 CLI verification: Failed - command not found")
                return False
                
            # Set up environment for W3 CLI
            w3_config_dir = os.path.expanduser("~/.w3")
            if not os.path.exists(w3_config_dir):
                try:
                    os.makedirs(w3_config_dir, exist_ok=True)
                    logger.info(f"Created W3 configuration directory at {w3_config_dir}")
                except Exception as e:
                    logger.warning(f"Failed to create W3 configuration directory: {e}")
            
            # Test basic functionality
            try:
                env = os.environ.copy()
                env['W3_AGENT_DIR'] = w3_config_dir
                
                cmd = ["npx", "w3", "--help"] if platform.system() == "Windows" else ["w3", "--help"]
                
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                    encoding="utf-8",
                    env=env,
                    timeout=10
                )
                
                if "Usage" in result.stdout:
                    logger.info("W3 CLI command execution: Successful")
                else:
                    logger.warning("W3 CLI command execution: Output doesn't contain expected content")
                    
            except Exception as e:
                logger.error(f"W3 CLI command execution failed: {e}")
                return False
        else:
            logger.info("W3 CLI verification skipped (npm not available)")
        
        return True
    
    def install_storacha_dependencies(self) -> bool:
        """
        Install all required dependencies for storacha functionality.
        
        Returns:
            bool: True if installation successful, False otherwise
        """
        logger.info("Installing Storacha dependencies...")
        
        # Install Python dependencies
        python_success = self.install_python_dependencies()
        
        if not python_success:
            logger.error("Failed to install required Python dependencies.")
            return False
            
        # Install W3 CLI (if npm is available)
        w3_success = True
        if not self.skip_npm:
            w3_success = self.install_w3_cli()
            
            if not w3_success:
                logger.error("Failed to install W3 CLI.")
                logger.error(f"You may need to install it manually: npm install -g {W3_CLI_DEPENDENCY}")
        
        # Verify installation
        verify_success = self.verify_storacha_functionality()
        
        if verify_success:
            logger.info("Storacha installation completed successfully!")
            
            # Create marker file to indicate successful installation
            try:
                bin_dir = os.path.join(os.path.dirname(__file__), "bin")
                os.makedirs(bin_dir, exist_ok=True)
                marker_file = os.path.join(bin_dir, ".storacha_installed")
                with open(marker_file, "w") as f:
                    import datetime
                    f.write(f"Storacha dependencies installed successfully at {datetime.datetime.now().isoformat()}\n")
                    f.write(f"Python dependencies: {', '.join(REQUIRED_DEPENDENCIES)}\n")
                    if not self.skip_npm:
                        f.write(f"W3 CLI: {W3_CLI_DEPENDENCY}\n")
                logger.info(f"Created installation marker file: {marker_file}")
            except Exception as e:
                logger.warning(f"Failed to create installation marker file: {e}")
            
            return True
        else:
            logger.error("Storacha installation completed but verification failed.")
            return False


def main():
    """Main function to parse arguments and install dependencies."""
    parser = argparse.ArgumentParser(description="Install storacha/web3.storage dependencies for IPFS Kit")
    parser.add_argument("--force", action="store_true", help="Force reinstallation even if already installed")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--skip-npm", action="store_true", help="Skip NPM dependencies installation")
    parser.add_argument("--w3-version", default=DEFAULT_W3_VERSION, help="W3 CLI version to install")
    args = parser.parse_args()
    
    # Create installer instance
    metadata = {
        "force": args.force,
        "verbose": args.verbose,
        "skip_npm": args.skip_npm,
        "w3_version": args.w3_version
    }
    
    installer = install_storacha(metadata=metadata)
    
    # Print welcome message
    logger.info("IPFS Kit - Storacha/Web3.Storage Dependency Installer")
    logger.info("=================================================")
    
    # Install dependencies
    success = installer.install_storacha_dependencies()
    
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
