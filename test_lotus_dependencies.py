#!/usr/bin/env python3
"""
Test script for Lotus dependency checking and installation.

This script tests the ability of the lotus_kit class to automatically
check for and install dependencies, including the system libraries
required by the Lotus binary.
"""

import logging
import os
import time

from ipfs_kit_py.lotus_kit import lotus_kit, LOTUS_AVAILABLE

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_lotus_dependencies")

def test_lotus_dependencies():
    """Test the automatic dependency installation."""
    logger.info("Starting Lotus dependency test")
    
    # Initial LOTUS_AVAILABLE state
    logger.info(f"Initial Lotus available: {LOTUS_AVAILABLE}")
    
    # Create a lotus_kit instance, which should trigger dependency installation
    logger.info("Creating lotus_kit instance...")
    kit = lotus_kit(metadata={
        "install_dependencies": True,  # Enable auto-dependency installation
        "simulation_mode": False,      # Try to use real Lotus
    })
    
    # Check if Lotus is available after initialization
    logger.info(f"Lotus available after initialization: {LOTUS_AVAILABLE}")
    
    # Test connection to Lotus API
    logger.info("Testing connection to Lotus API...")
    result = kit.check_connection()
    
    if result.get("success", False):
        logger.info("Connection successful!")
        logger.info(f"Lotus version: {result.get('result', 'unknown')}")
    else:
        logger.warning(f"Connection failed: {result.get('error', 'Unknown error')}")
        logger.info("Falling back to simulation mode")
        
    return result

if __name__ == "__main__":
    test_result = test_lotus_dependencies()
    print("\nTest Result:")
    for key, value in test_result.items():
        print(f"  {key}: {value}")