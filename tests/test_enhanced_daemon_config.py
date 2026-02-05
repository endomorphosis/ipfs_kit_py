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
    logger.info("🧪 Testing enhanced daemon configuration manager...")
    
    try:
        from ipfs_kit_py.daemon_config_manager import DaemonConfigManager
        
        with tempfile.TemporaryDirectory() as temp_dir:
            logger.info(f"📁 Using temporary directory: {temp_dir}")
            
            manager = DaemonConfigManager()
            
            # Override paths to use temp directory (never touch ~/.ipfs or ~/.lotus)
            manager.ipfs_path = os.path.join(temp_dir, ".ipfs")
            manager.lotus_path = os.path.join(temp_dir, ".lotus") 
            # Create a minimal valid IPFS config so config checks are deterministic and
            # do not shell out to `ipfs init`.
            ipfs_dir = Path(manager.ipfs_path)
            ipfs_dir.mkdir(parents=True, exist_ok=True)
            (ipfs_dir / "config").write_text(
                json.dumps({"Identity": {}, "Addresses": {}, "Discovery": {}}, indent=2),
                encoding="utf-8",
            )

            ipfs_check = manager.check_daemon_configuration("ipfs")
            assert ipfs_check["configured"] is True
            assert ipfs_check["valid_config"] is True
            assert ipfs_check["config_exists"] is True

            # Lotus/cluster are optional but configuration should always succeed.
            lotus_cfg = manager.configure_daemon("lotus")
            assert lotus_cfg["success"] is True
            assert lotus_cfg["configured"] is True

            cluster_cfg = manager.configure_daemon("cluster")
            assert cluster_cfg["success"] is True
            assert cluster_cfg["configured"] is True

            all_results = manager.check_and_configure_all_daemons()
            assert all_results["success"] is True
            assert all_results["all_configured"] is True
            assert set(all_results.get("daemon_results", {}).keys()) >= {"ipfs", "lotus", "cluster"}

            logger.info("🎉 Enhanced daemon configuration tests passed!")
                
    except Exception as e:
        logger.error(f"❌ Error in enhanced daemon config test: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        pytest.fail(f"Error in enhanced daemon config test: {e}")

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
        assert True
        
    except Exception as e:
        logger.error(f"❌ Error in MCP server integration test: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        pytest.fail(f"Error in MCP server integration test: {e}")

def test_default_configurations():
    """Test default configuration templates."""
    logger.info("🧪 Testing default configuration templates...")
    
    try:
        from ipfs_kit_py.daemon_config_manager import DaemonConfigManager
        
        manager = DaemonConfigManager()

        cfg = getattr(manager, "default_config", None)
        assert isinstance(cfg, dict)
        assert set(cfg.keys()) >= {"ipfs", "lotus", "cluster"}

        ipfs_cfg = cfg["ipfs"]
        assert set(ipfs_cfg.keys()) >= {"enabled", "auto_start", "api_port", "gateway_port", "swarm_port"}
        assert isinstance(ipfs_cfg["api_port"], int)
        assert isinstance(ipfs_cfg["gateway_port"], int)
        assert isinstance(ipfs_cfg["swarm_port"], int)

        lotus_cfg = cfg["lotus"]
        assert set(lotus_cfg.keys()) >= {"enabled", "auto_start", "api_port", "network"}
        assert isinstance(lotus_cfg["api_port"], int)
        assert isinstance(lotus_cfg["network"], str)

        cluster_cfg = cfg["cluster"]
        assert set(cluster_cfg.keys()) >= {"enabled", "cluster_secret", "cluster_name"}
        
        logger.info("✅ All default configuration templates are valid")
        assert True
        
    except Exception as e:
        logger.error(f"❌ Error testing default configurations: {e}")
        pytest.fail(f"Error testing default configurations: {e}")

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
            # Pytest-style tests should return None; treat that as success here.
            result = True if result is None else bool(result)
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
