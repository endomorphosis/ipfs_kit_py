#!/usr/bin/env python3
"""
Install script for Storacha dependencies.

This script is called from storacha_kit.py to install necessary
dependencies for the Storacha integration.
"""

import os
import sys
import subprocess
import logging
from pathlib import Path

# Set up logging
logger = logging.getLogger(__name__)

def install_w3_cli():
    """Install W3 CLI tool for Storacha integration."""
    logger.info("Installing W3 CLI tool...")
    
    try:
        # Check if npm is available
        subprocess.run(["npm", "--version"], check=True, capture_output=True)
        
        # Install W3 CLI globally
        result = subprocess.run(
            ["npm", "install", "-g", "@web3-storage/w3cli"],
            check=True,
            capture_output=True
        )
        
        logger.info("W3 CLI installation completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error installing W3 CLI: {e}")
        logger.error(f"Command output: {e.output.decode() if e.output else 'No output'}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during W3 CLI installation: {e}")
        return False

def install_storacha_dependencies():
    """Install Python dependencies for Storacha integration."""
    logger.info("Installing Storacha Python dependencies...")
    
    try:
        # Install dependencies using pip
        requirements = [
            "requests>=2.28.0",
            "aiohttp>=3.8.1",
            "pydantic>=1.9.0",
            "anyio>=3.6.1"
        ]
        
        for req in requirements:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", req],
                check=True,
                capture_output=True
            )
        
        logger.info("Storacha Python dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error installing Storacha dependencies: {e}")
        logger.error(f"Command output: {e.output.decode() if e.output else 'No output'}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during dependency installation: {e}")
        return False

def main():
    """Main function to install all Storacha dependencies."""
    logger.info("Starting Storacha dependency installation...")
    
    py_deps_success = install_storacha_dependencies()
    w3_cli_success = install_w3_cli()
    
    if py_deps_success and w3_cli_success:
        logger.info("All Storacha dependencies installed successfully")
        return 0
    else:
        logger.warning("Some Storacha dependencies could not be installed")
        return 1

if __name__ == "__main__":
    # Configure logging to stdout
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)8s] %(name)s: %(message)s",
        datefmt="%H:%M:%S"
    )
    
    sys.exit(main())