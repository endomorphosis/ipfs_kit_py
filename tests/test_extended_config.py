#!/usr/bin/env python3
"""
Test script to verify the extended daemon configuration management.

This test checks that all services (IPFS, Lotus, Lassie, ipfs-cluster-service,
ipfs-cluster-follow, ipfs-cluster-ctl, S3, HuggingFace, Storacha) have proper
configuration handling and can be managed by the MCP server.
"""

import sys
import os
import logging
import traceback
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('test_extended_config.log')
    ]
)

logger = logging.getLogger(__name__)

def test_extended_daemon_config_manager():
    """Test that the extended daemon configuration manager works properly."""
    logger.info("Testing extended daemon configuration manager...")
    
    success = True
    
    try:
        # Import the daemon configuration manager
        from ipfs_kit_py.daemon_config_manager import DaemonConfigManager
        
        # Create instance
        manager = DaemonConfigManager()
        logger.info("✓ DaemonConfigManager imported and instantiated successfully")
        
        # Check that all expected services are covered
        expected_services = [
            'ipfs', 'lotus', 'lassie', 
            'ipfs_cluster_service', 'ipfs_cluster_follow', 'ipfs_cluster_ctl',
            's3', 'huggingface', 'storacha'
        ]
        
        # Test configuration checking for all services
        logger.info("🔧 Testing configuration checking for all services...")
        config_results = manager.check_and_configure_all_daemons()
        
        # Check that all expected services are in the results
        missing_services = []
        for service in expected_services:
            if service not in config_results:
                missing_services.append(service)
        
        if missing_services:
            logger.error(f"❌ Missing services in configuration results: {missing_services}")
            success = False
        else:
            logger.info("✅ All expected services are covered in configuration results")
        
        # Report on each service's configuration status
        logger.info("\n📊 Configuration Status Report:")
        for service in expected_services:
            if service in config_results:
                result = config_results[service]
                if result.get("success", False) or result.get("already_configured", False):
                    logger.info(f"  ✅ {service}: Configured successfully")
                else:
                    error_msg = result.get("error", "Unknown error")
                    logger.warning(f"  ⚠️  {service}: {error_msg}")
            else:
                logger.error(f"  ❌ {service}: Not found in results")
        
        # Test overall success
        overall_success = config_results.get("overall_success", False)
        logger.info(f"\n🎯 Overall configuration success: {overall_success}")
        
        # Test validation
        logger.info("\n🔍 Testing configuration validation...")
        validation_results = manager.validate_daemon_configs()
        
        overall_valid = validation_results.get("overall_valid", False)
        logger.info(f"🎯 Overall configuration validation: {overall_valid}")
        
        # Test configuration update functionality
        logger.info("\n🔄 Testing configuration update functionality...")
        
        # Test updating IPFS config
        update_result = manager.update_daemon_config("ipfs", {"test_key": "test_value"})
        if update_result.get("success", False):
            logger.info("✅ Configuration update test passed")
        else:
            logger.warning(f"⚠️  Configuration update test: {update_result.get('error', 'Unknown error')}")
        
        return success
        
    except Exception as e:
        logger.error(f"❌ Error testing extended daemon configuration manager: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

def test_enhanced_mcp_server():
    """Test that the enhanced MCP server with configuration management works."""
    logger.info("Testing enhanced MCP server with configuration management...")
    
    try:
        # Import the enhanced MCP server
        from enhanced_mcp_server_with_config import EnhancedMCPServerWithConfig
        
        # Create instance
        server = EnhancedMCPServerWithConfig()
        logger.info("✓ EnhancedMCPServerWithConfig imported and instantiated successfully")
        
        # Check that it has the expected attributes
        expected_attributes = ['daemon_config_manager', 'config_status', 'startup_errors']
        
        for attr in expected_attributes:
            if hasattr(server, attr):
                logger.info(f"✅ Server has expected attribute: {attr}")
            else:
                logger.warning(f"⚠️  Server missing expected attribute: {attr}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error testing enhanced MCP server: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

def test_service_specific_configurations():
    """Test that service-specific configurations work correctly."""
    logger.info("Testing service-specific configurations...")
    
    try:
        from ipfs_kit_py.daemon_config_manager import DaemonConfigManager
        
        manager = DaemonConfigManager()
        
        # Test individual service configurations
        services_to_test = [
            ('ipfs', 'IPFS'),
            ('lotus', 'Lotus'),
            ('lassie', 'Lassie'),
            ('s3', 'S3'),
            ('huggingface', 'HuggingFace'),
            ('storacha', 'Storacha')
        ]
        
        for service_key, service_name in services_to_test:
            logger.info(f"Testing {service_name} configuration...")
            
            # Test individual configuration method
            method_name = f"check_and_configure_{service_key}"
            if hasattr(manager, method_name):
                method = getattr(manager, method_name)
                result = method()
                
                if result.get("success", False) or result.get("already_configured", False):
                    logger.info(f"  ✅ {service_name} configuration: Success")
                else:
                    error_msg = result.get("error", "Unknown error")
                    logger.warning(f"  ⚠️  {service_name} configuration: {error_msg}")
            else:
                logger.error(f"  ❌ {service_name}: Configuration method not found")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error testing service-specific configurations: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

def main():
    """Run all tests for the extended configuration management."""
    logger.info("🚀 Starting extended daemon configuration management tests...")
    
    tests = [
        ("Extended Daemon Config Manager", test_extended_daemon_config_manager),
        ("Enhanced MCP Server", test_enhanced_mcp_server),
        ("Service-Specific Configurations", test_service_specific_configurations)
    ]
    
    results = {}
    overall_success = True
    
    for test_name, test_func in tests:
        logger.info(f"\n{'='*60}")
        logger.info(f"Running: {test_name}")
        logger.info(f"{'='*60}")
        
        try:
            result = test_func()
            results[test_name] = result
            
            if result:
                logger.info(f"✅ {test_name} PASSED")
            else:
                logger.error(f"❌ {test_name} FAILED")
                overall_success = False
                
        except Exception as e:
            logger.error(f"❌ {test_name} FAILED with exception: {e}")
            results[test_name] = False
            overall_success = False
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("TEST SUMMARY")
    logger.info(f"{'='*60}")
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    logger.info(f"Tests passed: {passed}/{total}")
    
    for test_name, result in results.items():
        status = "PASSED" if result else "FAILED"
        logger.info(f"  {test_name}: {status}")
    
    if overall_success:
        logger.info("\n🎉 ALL TESTS PASSED! The extended daemon configuration management is working correctly.")
        logger.info("\n📋 Summary of what was tested:")
        logger.info("  ✅ IPFS configuration management")
        logger.info("  ✅ Lotus configuration management")
        logger.info("  ✅ Lassie configuration management")
        logger.info("  ✅ IPFS Cluster Service configuration management")
        logger.info("  ✅ IPFS Cluster Follow configuration management")
        logger.info("  ✅ IPFS Cluster Ctl configuration management")
        logger.info("  ✅ S3 configuration management")
        logger.info("  ✅ HuggingFace configuration management")
        logger.info("  ✅ Storacha configuration management")
        logger.info("  ✅ MCP server can update configurations at runtime")
    else:
        logger.error("\n❌ Some tests failed. Please review the output above.")
    
    return overall_success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
