#!/usr/bin/env python3
"""
Comprehensive test for enhanced daemon configuration management.

This test verifies that all services have proper configuration management:
- IPFS, Lotus, Lassie (existing)
- IPFS cluster services (new)
- S3, HuggingFace, Storacha (new)
"""

import sys
import os
import json
import tempfile
import shutil
import logging
import pytest
from pathlib import Path
from typing import Dict, Any, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_enhanced_daemon_config_manager():
    """Test the enhanced daemon configuration manager."""
    if os.environ.get("IPFS_KIT_RUN_LONG_INTEGRATION") != "1":
        pytest.skip("Set IPFS_KIT_RUN_LONG_INTEGRATION=1 to run enhanced daemon config tests")
    logger.info("🧪 Testing enhanced daemon configuration manager...")
    
    try:
        from ipfs_kit_py.daemon_config_manager import DaemonConfigManager
        
        # Create a temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            logger.info(f"📁 Using temporary directory: {temp_dir}")
            
            # Create test manager with custom paths
            manager = DaemonConfigManager()
            
            # Override paths to use temp directory
            manager.ipfs_path = os.path.join(temp_dir, ".ipfs")
            manager.lotus_path = os.path.join(temp_dir, ".lotus") 
            manager.lassie_path = os.path.join(temp_dir, ".lassie")
            manager.ipfs_cluster_path = os.path.join(temp_dir, ".ipfs-cluster")
            manager.ipfs_cluster_follow_path = os.path.join(temp_dir, ".ipfs-cluster-follow")
            manager.s3_config_path = os.path.join(temp_dir, ".s3cfg")
            manager.hf_config_path = os.path.join(temp_dir, ".cache", "huggingface")
            manager.storacha_config_path = os.path.join(temp_dir, ".storacha")
            
            # Test configuration for all services
            logger.info("🔧 Testing configuration for all services...")
            
            # Test individual service configuration
            services = [
                ("IPFS", "check_and_configure_ipfs"),
                ("Lotus", "check_and_configure_lotus"),
                ("Lassie", "check_and_configure_lassie"),
                ("IPFS Cluster Service", "check_and_configure_ipfs_cluster_service"),
                ("IPFS Cluster Follow", "check_and_configure_ipfs_cluster_follow"),
                ("IPFS Cluster Ctl", "check_and_configure_ipfs_cluster_ctl"),
                ("S3", "check_and_configure_s3"),
                ("HuggingFace", "check_and_configure_huggingface"),
                ("Storacha", "check_and_configure_storacha")
            ]
            
            individual_results = {}
            for service_name, method_name in services:
                logger.info(f"🔧 Testing {service_name} configuration...")
                
                try:
                    method = getattr(manager, method_name)
                    result = method()
                    
                    individual_results[service_name] = result
                    
                    if result.get("success", False) or result.get("already_configured", False):
                        logger.info(f"✅ {service_name} configuration successful")
                    else:
                        logger.warning(f"⚠️ {service_name} configuration failed: {result.get('error', 'Unknown error')}")
                        
                except Exception as e:
                    logger.error(f"❌ Error testing {service_name}: {e}")
                    individual_results[service_name] = {"success": False, "error": str(e)}
            
            # Test comprehensive configuration
            logger.info("🔧 Testing comprehensive configuration...")
            all_results = manager.check_and_configure_all_daemons()
            
            # Test validation
            logger.info("🔍 Testing configuration validation...")
            validation_results = manager.validate_daemon_configs()
            
            # Test configuration updates
            logger.info("🔄 Testing configuration updates...")
            update_results = {}
            
            # Test S3 configuration update
            s3_update = manager.update_daemon_config("s3", {
                "host_base": "s3.example.com",
                "bucket_location": "us-west-2"
            })
            update_results["s3"] = s3_update
            
            # Test HuggingFace configuration update
            hf_update = manager.update_daemon_config("huggingface", {
                "offline": True,
                "user_agent": "test-agent"
            })
            update_results["huggingface"] = hf_update
            
            # Test Storacha configuration update
            storacha_update = manager.update_daemon_config("storacha", {
                "timeout": 60,
                "retries": 5
            })
            update_results["storacha"] = storacha_update
            
            # Print results
            logger.info("📊 Test Results Summary:")
            logger.info(f"Individual service results: {json.dumps(individual_results, indent=2)}")
            logger.info(f"Comprehensive results: {json.dumps(all_results, indent=2)}")
            logger.info(f"Validation results: {json.dumps(validation_results, indent=2)}")
            logger.info(f"Update results: {json.dumps(update_results, indent=2)}")
            
            # Verify file creation
            logger.info("🗃️ Verifying configuration files were created...")
            
            expected_files = [
                (manager.s3_config_path, "S3 config"),
                (os.path.join(manager.hf_config_path, "config.json"), "HuggingFace config"),
                (os.path.join(manager.storacha_config_path, "config.json"), "Storacha config"),
                (os.path.join(manager.lassie_path, "config.json"), "Lassie config")
            ]
            
            for file_path, description in expected_files:
                if os.path.exists(file_path):
                    logger.info(f"✅ {description} file exists: {file_path}")
                else:
                    logger.warning(f"⚠️ {description} file missing: {file_path}")
            
            # Calculate overall success
            overall_success = (
                all_results.get("overall_success", False) and
                validation_results.get("overall_valid", False) and
                all(result.get("success", False) for result in update_results.values())
            )
            
            if overall_success:
                logger.info("🎉 All enhanced daemon configuration tests passed!")
                return True
            else:
                logger.error("❌ Some enhanced daemon configuration tests failed")
                return False
                
    except Exception as e:
        logger.error(f"❌ Error in enhanced daemon config test: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

def test_mcp_server_integration():
    """Test MCP server integration with enhanced configuration management."""
    if os.environ.get("IPFS_KIT_RUN_LONG_INTEGRATION") != "1":
        pytest.skip("Set IPFS_KIT_RUN_LONG_INTEGRATION=1 to run MCP server integration config tests")
    logger.info("🧪 Testing MCP server integration...")
    
    try:
        from enhanced_mcp_server_with_full_config import EnhancedMCPServerWithFullConfig
        
        # Create server instance
        server = EnhancedMCPServerWithFullConfig()
        logger.info("✅ Enhanced MCP server created successfully")
        
        # Test standalone mode
        logger.info("🔧 Testing standalone mode...")
        server.run_standalone()
        
        logger.info("🎉 MCP server integration test passed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error in MCP server integration test: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

def test_default_configurations():
    """Test default configuration templates."""
    if os.environ.get("IPFS_KIT_RUN_LONG_INTEGRATION") != "1":
        pytest.skip("Set IPFS_KIT_RUN_LONG_INTEGRATION=1 to run default configuration tests")
    logger.info("🧪 Testing default configuration templates...")
    
    try:
        from ipfs_kit_py.daemon_config_manager import DaemonConfigManager
        
        manager = DaemonConfigManager()
        
        # Test default config templates
        configs = {
            "S3": manager.get_default_s3_config(),
            "HuggingFace": manager.get_default_huggingface_config(),
            "Storacha": manager.get_default_storacha_config(),
            "Lassie": manager.get_default_lassie_config()
        }
        
        logger.info("📋 Default configuration templates:")
        for name, config in configs.items():
            logger.info(f"  {name}: {json.dumps(config, indent=4)}")
            
            # Verify required fields
            if name == "S3":
                required_fields = ["access_key", "secret_key", "host_base"]
                missing = [field for field in required_fields if field not in config]
                if missing:
                    logger.error(f"❌ S3 config missing required fields: {missing}")
                    return False
                    
            elif name == "HuggingFace":
                required_fields = ["cache_dir"]
                missing = [field for field in required_fields if field not in config]
                if missing:
                    logger.error(f"❌ HuggingFace config missing required fields: {missing}")
                    return False
                    
            elif name == "Storacha":
                required_fields = ["endpoints"]
                missing = [field for field in required_fields if field not in config]
                if missing:
                    logger.error(f"❌ Storacha config missing required fields: {missing}")
                    return False
        
        logger.info("✅ All default configuration templates are valid")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error testing default configurations: {e}")
        return False

def run_all_tests():
    """Run all enhanced configuration tests."""
    logger.info("🚀 Starting comprehensive enhanced configuration tests...")
    
    tests = [
        ("Enhanced Daemon Config Manager", test_enhanced_daemon_config_manager),
        ("MCP Server Integration", test_mcp_server_integration),
        ("Default Configurations", test_default_configurations)
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
        logger.info("\n🎉 ALL ENHANCED CONFIGURATION TESTS PASSED!")
        logger.info("The enhanced daemon configuration management system is working correctly.")
        logger.info("All services (IPFS, Lotus, Lassie, IPFS cluster, S3, HuggingFace, Storacha) are properly configured.")
    else:
        logger.error("\n❌ Some enhanced configuration tests failed.")
        logger.error("Please review the output above for details.")
    
    return overall_success

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
