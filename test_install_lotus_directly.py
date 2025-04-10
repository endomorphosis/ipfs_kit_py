#!/usr/bin/env python3
"""
Direct test script for install_lotus module.

This script tests the install_lotus module directly to diagnose issues with
the installer object's attributes and methods.
"""

import os
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("test_install_lotus")

def test_install_lotus():
    """Test the install_lotus module directly."""
    try:
        # Import the module
        from install_lotus import install_lotus as LotusInstaller
        logger.info("Successfully imported install_lotus module")
        
        # Create installer metadata with binary dir
        bin_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "bin")
        installer_metadata = {
            "auto_install_deps": True,
            "force": False,
            "skip_params": True,
            "bin_dir": bin_dir
        }
        
        # Log the metadata
        logger.info(f"Creating installer with metadata: {installer_metadata}")
        
        # Create installer instance
        installer = LotusInstaller(metadata=installer_metadata)
        
        # Log installer attributes
        logger.info(f"installer type: {type(installer)}")
        logger.info(f"installer dir(): {dir(installer)}")
        
        # Check for specific attributes
        if hasattr(installer, 'bin_path'):
            logger.info(f"installer.bin_path: {installer.bin_path}")
        else:
            logger.error("installer does not have bin_path attribute!")
            logger.info(f"installer.__dict__: {installer.__dict__}")
        
        # Try to install the Lotus daemon
        if hasattr(installer, 'install_lotus_daemon'):
            logger.info("Calling installer.install_lotus_daemon()")
            result = installer.install_lotus_daemon()
            logger.info(f"install_lotus_daemon result: {result}")
        else:
            logger.error("installer does not have install_lotus_daemon method!")
            
        return True
        
    except Exception as e:
        logger.error(f"Error testing install_lotus: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    print("Starting direct test of install_lotus module...")
    result = test_install_lotus()
    print(f"Test completed with result: {result}")
    sys.exit(0 if result else 1)