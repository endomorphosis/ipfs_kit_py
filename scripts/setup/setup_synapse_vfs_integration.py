#!/usr/bin/env python3
"""
Setup script for integrating Synapse SDK with the virtual filesystem.

This script:
1. Installs and configures the Synapse SDK
2. Integrates Synapse storage with the virtual filesystem
3. Registers Synapse as a storage backend in FSSpec
4. Sets up MCP server tools for Synapse operations
5. Creates the necessary configuration files

Usage:
    python setup_synapse_vfs_integration.py
"""

import os
import sys
import json
import logging
from pathlib import Path

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def setup_synapse_installation():
    """Install and configure Synapse SDK."""
    logger.info("Setting up Synapse SDK installation...")
    
    try:
        from ipfs_kit_py.install_synapse_sdk import install_synapse_sdk
        
        # Install with verbose output
        installer = install_synapse_sdk(metadata={'verbose': True})
        success = installer.install()
        
        if success:
            logger.info("✓ Synapse SDK installation completed successfully")
            
            # Verify installation
            verification = installer.verify_installation()
            if verification:
                logger.info("✓ Synapse SDK verification passed")
            else:
                logger.warning("⚠ Synapse SDK verification failed, but installation completed")
        else:
            logger.error("✗ Synapse SDK installation failed")
            return False
            
    except Exception as e:
        logger.error(f"✗ Failed to install Synapse SDK: {e}")
        return False
    
    return True


def setup_synapse_configuration():
    """Configure Synapse SDK for virtual filesystem integration."""
    logger.info("Setting up Synapse SDK configuration...")
    
    try:
        from ipfs_kit_py.config_synapse_sdk import config_synapse_sdk
        
        # Create configuration manager
        config_manager = config_synapse_sdk()
        
        # Setup default configuration
        success = config_manager.setup_synapse_config()
        
        if success:
            logger.info("✓ Synapse SDK configuration completed successfully")
        else:
            logger.error("✗ Synapse SDK configuration failed")
            return False
            
    except Exception as e:
        logger.error(f"✗ Failed to configure Synapse SDK: {e}")
        return False
    
    return True


def register_synapse_fsspec():
    """Register Synapse as a storage backend in FSSpec."""
    logger.info("Registering Synapse with FSSpec...")
    
    try:
        from ipfs_kit_py.enhanced_fsspec import IPFSFileSystem
        import fsspec
        
        # Register the protocols if not already registered
        protocols = ['synapse']
        for protocol in protocols:
            if protocol not in fsspec.registry:
                fsspec.register_implementation(protocol, IPFSFileSystem)
                logger.info(f"✓ Registered '{protocol}' protocol with FSSpec")
            else:
                logger.info(f"✓ Protocol '{protocol}' already registered")
        
        # Test basic functionality
        try:
            fs = IPFSFileSystem(backend="synapse")
            logger.info("✓ Synapse FSSpec backend can be initialized")
        except Exception as e:
            logger.warning(f"⚠ Synapse FSSpec backend initialization failed: {e}")
            
    except Exception as e:
        logger.error(f"✗ Failed to register Synapse with FSSpec: {e}")
        return False
    
    return True


def setup_virtual_filesystem_integration():
    """Integrate Synapse with the virtual filesystem."""
    logger.info("Setting up virtual filesystem integration...")
    
    try:
        # Check if VFS components are available
        vfs_components = [
            "ipfs_kit_py.mcp.fs.fs_journal",
            "ipfs_kit_py.mcp.fs.fs_ipfs_bridge"
        ]
        
        available_components = []
        for component in vfs_components:
            try:
                __import__(component)
                available_components.append(component)
                logger.info(f"✓ VFS component available: {component}")
            except ImportError:
                logger.warning(f"⚠ VFS component not available: {component}")
        
        if available_components:
            logger.info(f"✓ Virtual filesystem integration ready ({len(available_components)} components)")
        else:
            logger.warning("⚠ No VFS components available - basic integration only")
            
    except Exception as e:
        logger.error(f"✗ Failed to setup virtual filesystem integration: {e}")
        return False
    
    return True


def setup_mcp_server_tools():
    """Setup MCP server tools for Synapse operations."""
    logger.info("Setting up MCP server tools...")
    
    try:
        # Create MCP tools configuration for Synapse
        mcp_tools_config = {
            "synapse_tools": {
                "synapse_store_data": {
                    "description": "Store data using Synapse SDK with PDP verification",
                    "parameters": {
                        "data": {"type": "string", "description": "Data to store (base64 encoded)"},
                        "options": {"type": "object", "description": "Storage options"}
                    }
                },
                "synapse_retrieve_data": {
                    "description": "Retrieve data using Synapse SDK",
                    "parameters": {
                        "commp": {"type": "string", "description": "Content identifier (CommP)"},
                        "options": {"type": "object", "description": "Retrieval options"}
                    }
                },
                "synapse_get_balance": {
                    "description": "Get USDFC token balance",
                    "parameters": {
                        "token": {"type": "string", "description": "Token symbol", "default": "USDFC"}
                    }
                },
                "synapse_deposit_funds": {
                    "description": "Deposit funds to Synapse payment contract",
                    "parameters": {
                        "amount": {"type": "string", "description": "Amount to deposit"},
                        "token": {"type": "string", "description": "Token symbol", "default": "USDFC"}
                    }
                },
                "synapse_get_storage_info": {
                    "description": "Get storage service information",
                    "parameters": {}
                },
                "synapse_get_provider_info": {
                    "description": "Get storage provider information",
                    "parameters": {
                        "provider_address": {"type": "string", "description": "Provider address"}
                    }
                }
            }
        }
        
        # Save configuration
        config_dir = os.path.join(project_root, "config")
        os.makedirs(config_dir, exist_ok=True)
        
        config_file = os.path.join(config_dir, "synapse_mcp_tools.json")
        with open(config_file, 'w') as f:
            json.dump(mcp_tools_config, f, indent=2)
        
        logger.info(f"✓ MCP tools configuration saved to {config_file}")
        
    except Exception as e:
        logger.error(f"✗ Failed to setup MCP server tools: {e}")
        return False
    
    return True


def create_integration_test_script():
    """Create a test script to verify the integration."""
    logger.info("Creating integration test script...")
    
    test_script_content = '''#!/usr/bin/env python3
"""
Test script for Synapse SDK virtual filesystem integration.
"""

import os
import sys
import asyncio
import logging

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_synapse_integration():
    """Test Synapse SDK integration with virtual filesystem."""
    logger.info("Testing Synapse SDK integration...")
    
    tests_passed = 0
    total_tests = 0
    
    # Test 1: Import Synapse storage
    total_tests += 1
    try:
        from ipfs_kit_py.synapse_storage import synapse_storage
        logger.info("✓ Test 1: Synapse storage import successful")
        tests_passed += 1
    except Exception as e:
        logger.error(f"✗ Test 1: Synapse storage import failed: {e}")
    
    # Test 2: Import Synapse configuration
    total_tests += 1
    try:
        from ipfs_kit_py.config_synapse_sdk import config_synapse_sdk
        logger.info("✓ Test 2: Synapse configuration import successful")
        tests_passed += 1
    except Exception as e:
        logger.error(f"✗ Test 2: Synapse configuration import failed: {e}")
    
    # Test 3: Test FSSpec integration
    total_tests += 1
    try:
        from ipfs_kit_py.enhanced_fsspec import IPFSFileSystem
        fs = IPFSFileSystem(backend="synapse")
        logger.info("✓ Test 3: Synapse FSSpec backend initialization successful")
        tests_passed += 1
    except Exception as e:
        logger.error(f"✗ Test 3: Synapse FSSpec backend initialization failed: {e}")
    
    # Test 4: Test IPFS Kit integration
    total_tests += 1
    try:
        from ipfs_kit_py.ipfs_kit import ipfs_kit
        kit = ipfs_kit(metadata={"role": "leecher"})
        if hasattr(kit, 'synapse_storage'):
            logger.info("✓ Test 4: IPFS Kit Synapse integration successful")
            tests_passed += 1
        else:
            logger.error("✗ Test 4: IPFS Kit missing synapse_storage attribute")
    except Exception as e:
        logger.error(f"✗ Test 4: IPFS Kit integration failed: {e}")
    
    # Test 5: Test configuration files
    total_tests += 1
    try:
        config_file = os.path.join(project_root, "config", "synapse_config.yaml")
        if os.path.exists(config_file):
            logger.info("✓ Test 5: Synapse configuration file exists")
            tests_passed += 1
        else:
            logger.error("✗ Test 5: Synapse configuration file not found")
    except Exception as e:
        logger.error(f"✗ Test 5: Configuration file check failed: {e}")
    
    # Summary
    logger.info(f"\\nIntegration test completed: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        logger.info("🎉 All tests passed! Synapse SDK integration is ready.")
        return True
    else:
        logger.warning(f"⚠ {total_tests - tests_passed} tests failed. Check the errors above.")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_synapse_integration())
    sys.exit(0 if success else 1)
'''
    
    try:
        test_script_path = os.path.join(project_root, "scripts", "setup", "test_synapse_integration.py")
        with open(test_script_path, 'w') as f:
            f.write(test_script_content)
        
        # Make executable
        os.chmod(test_script_path, 0o755)
        
        logger.info(f"✓ Integration test script created: {test_script_path}")
        
    except Exception as e:
        logger.error(f"✗ Failed to create integration test script: {e}")
        return False
    
    return True


def main():
    """Main setup function."""
    logger.info("Starting Synapse SDK virtual filesystem integration setup...")
    
    steps = [
        ("Installing Synapse SDK", setup_synapse_installation),
        ("Configuring Synapse SDK", setup_synapse_configuration),
        ("Registering FSSpec backend", register_synapse_fsspec),
        ("Setting up VFS integration", setup_virtual_filesystem_integration),
        ("Setting up MCP tools", setup_mcp_server_tools),
        ("Creating test script", create_integration_test_script),
    ]
    
    completed_steps = 0
    
    for step_name, step_function in steps:
        logger.info(f"\n📋 Step {completed_steps + 1}/{len(steps)}: {step_name}")
        
        try:
            success = step_function()
            if success:
                completed_steps += 1
                logger.info(f"✅ {step_name} completed successfully")
            else:
                logger.error(f"❌ {step_name} failed")
                break
        except Exception as e:
            logger.error(f"❌ {step_name} failed with exception: {e}")
            break
    
    # Summary
    logger.info(f"\n{'='*50}")
    logger.info("SYNAPSE SDK VFS INTEGRATION SETUP SUMMARY")
    logger.info(f"{'='*50}")
    logger.info(f"Completed steps: {completed_steps}/{len(steps)}")
    
    if completed_steps == len(steps):
        logger.info("🎉 Synapse SDK virtual filesystem integration setup completed successfully!")
        logger.info("\nNext steps:")
        logger.info("1. Run the integration test: python scripts/setup/test_synapse_integration.py")
        logger.info("2. Configure your private key in environment variables")
        logger.info("3. Test storage operations with the Synapse backend")
        return True
    else:
        logger.error("❌ Setup incomplete. Please check the errors above and try again.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
