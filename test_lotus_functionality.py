#!/usr/bin/env python3
"""
Test script to verify the functionality of the Lotus client.

This script tests the basic functionality of the lotus_kit module,
including initialization, simulation mode, and basic operations.
"""

import os
import sys
import logging
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("test_lotus_functionality")

def test_lotus_kit_initialization():
    """Test basic initialization of lotus_kit."""
    logger.info("Testing lotus_kit initialization...")
    
    try:
        from ipfs_kit_py.lotus_kit import lotus_kit
        
        # Create a lotus kit instance with simulation mode for Filecoin
        resources = {}
        metadata = {
            "filecoin_simulation": True,  # Enable simulation mode for Filecoin
            "role": "leecher"             # Use leecher role for minimal setup
        }
        
        client = lotus_kit(resources=resources, metadata=metadata)
        
        # Check if lotus kit is properly initialized
        logger.info(f"Lotus kit client created")
        
        # Check if simulation is enabled by checking the simulation_mode attribute
        simulation_mode = hasattr(client, "simulation_mode") and client.simulation_mode
        logger.info(f"Simulation mode: {simulation_mode}")
        
        # Check daemon availability
        daemon_available = hasattr(client, "daemon") and client.daemon is not None
        logger.info(f"Lotus daemon initialized: {daemon_available}")
        
        # Check if we can get the daemon status (should work in simulation mode)
        daemon_status = client.daemon_status()
        logger.info(f"Lotus daemon status: {daemon_status}")
        
        return True, client
        
    except ImportError as e:
        logger.error(f"Error importing lotus_kit: {e}")
        return False, None
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False, None

def test_lotus_operations(client):
    """Test basic Lotus operations."""
    logger.info("\nTesting lotus operations with simulation mode...")
    
    try:
        # Test chain head
        chain_head = client.get_chain_head()
        logger.info(f"Chain head result: {chain_head}")
        
        # Test wallet list
        wallet_list = client.list_wallets()
        logger.info(f"Wallet list result: {wallet_list}")
        
        # Test net info
        net_info = client.net_info()
        logger.info(f"Net info result: {net_info}")
        
        # Test sync status
        sync_status = client.sync_status()
        logger.info(f"Sync status result: {sync_status}")
        
        # Test wallet balance
        # Use a sample wallet address or generate one
        sample_address = "t1abjxfbp274xpdqcpuaykwkfb43omjotacm2p3za"  # Sample address for testing
        balance = client.wallet_balance(sample_address)
        logger.info(f"Wallet balance result: {balance}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error during operations test: {e}")
        return False

def test_dependency_installation():
    """Test dependency installation functionality."""
    logger.info("\nTesting dependency installation...")
    
    try:
        # Import the install module
        from install_lotus import install_lotus
        
        # Create installer with check-only mode
        resources = {}
        metadata = {
            "auto_install_deps": False,  # Don't actually install, just check
            "force": False,
            "skip_params": True
        }
        
        installer = install_lotus(resources=resources, metadata=metadata)
        
        # Check hwloc library availability
        hwloc_available = installer._check_hwloc_library_direct()
        logger.info(f"HWLOC library available: {hwloc_available}")
        
        # Check system package manager and dependencies - directly use the installer methods
        if hasattr(installer, "_detect_linux_distribution"):
            # Get Linux distribution info
            distro_info = installer._detect_linux_distribution()
            if isinstance(distro_info, dict):
                # Extract information
                package_manager = distro_info.get("package_manager", "unknown")
                packages = distro_info.get("packages", [])
                
                logger.info(f"Detected package manager: {package_manager}")
                logger.info(f"Required system packages: {packages}")
                
                # Check package manager availability
                if hasattr(installer, "_check_package_manager_available"):
                    try:
                        pkg_mgr_available, lock_info = installer._check_package_manager_available(distro_info)
                        logger.info(f"Package manager available: {pkg_mgr_available}")
                        if not pkg_mgr_available and lock_info:
                            logger.info(f"Lock info: {lock_info}")
                    except Exception as e:
                        logger.warning(f"Error checking package manager: {e}")
        
        return True, installer
        
    except ImportError as e:
        logger.error(f"Error importing install_lotus: {e}")
        return False, None
    except Exception as e:
        logger.error(f"Unexpected error during dependency test: {e}")
        return False, None

def test_actual_lotus_binary():
    """Test if the actual Lotus binary is available."""
    logger.info("\nTesting actual Lotus binary availability...")
    
    try:
        import subprocess
        
        # Try to run the lotus version command
        try:
            result = subprocess.run(
                ["lotus", "--version"], 
                capture_output=True, 
                text=True, 
                timeout=5
            )
            
            lotus_available = result.returncode == 0
            version_output = result.stdout.strip() if lotus_available else None
            
            logger.info(f"Lotus binary available: {lotus_available}")
            if version_output:
                logger.info(f"Lotus version: {version_output}")
                
            return lotus_available, version_output
            
        except (subprocess.SubprocessError, FileNotFoundError):
            logger.info("Lotus binary not found in PATH")
            return False, None
            
    except Exception as e:
        logger.error(f"Unexpected error testing binary: {e}")
        return False, None

if __name__ == "__main__":
    print("\n=== Testing Lotus Kit Functionality ===\n")
    
    # Test initialization
    init_success, client = test_lotus_kit_initialization()
    
    # Test operations if initialization succeeded
    ops_success = False
    if init_success and client:
        ops_success = test_lotus_operations(client)
    
    # Test dependency installation
    dep_success, _ = test_dependency_installation()
    
    # Test binary availability
    bin_success, _ = test_actual_lotus_binary()
    
    # Print summary
    print("\n=== Test Results Summary ===")
    print(f"Lotus kit initialization: {'Succeeded' if init_success else 'Failed'}")
    print(f"Lotus operations test: {'Succeeded' if ops_success else 'Failed or skipped'}")
    print(f"Dependency installation test: {'Succeeded' if dep_success else 'Failed'}")
    print(f"Lotus binary availability: {'Succeeded' if bin_success else 'Failed'}")
    print(f"Overall result: {'Succeeded' if init_success and ops_success and dep_success else 'Partially failed'}")